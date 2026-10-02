"""NHL goals by period from the league's own score feed, for the games the archive does not cover.

WHY. `nhl_period_scores` held 5,134 games, 2018-10-03 to 2022-11-27, all from
the Sportsbook Reviews archive, which stopped there. First-period prices were
bought on 2026-10-01 for 2023-24 onward (data/ingestors/nhl_totals_odds_history.py)
and a first-period total cannot be graded without first-period goals.

SOURCE. `https://api-web.nhle.com/v1/score/<date>`: free, no key, one call a
date, every goal of every game that day with the period it was scored in. Our
game id comes from `nhl_team_game_log`, which already maps the league's game id
to ours.

WHAT IS WRITTEN. One row per finished game into `nhl_period_scores` with
`source = 'nhl_api_score'` (the table's key is (game_id, source), so the
archive's rows are left alone and a re-run writes nothing twice). A game whose
three period sums do not agree with the stored final -- the final may exceed
them by one overtime or shootout goal, never trail them -- is skipped and
counted, not written.

    python -m data.ingestors.nhl_period_scores_api --from 2022-11-28                 # count what is missing, write nothing
    python -m data.ingestors.nhl_period_scores_api --from 2022-11-28 --apply
    python -m data.ingestors.nhl_period_scores_api --recent 5 --apply               # a top-up
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict
from datetime import date, timedelta

import requests
from loguru import logger

from data.db import get_connection

URL = "https://api-web.nhle.com/v1/score/{date}"
SOURCE = "nhl_api_score"
FINAL_STATES = {"OFF", "FINAL"}


def period_goals(game: dict) -> tuple[list[int], list[int]] | None:
    """(home goals in periods 1-3, away goals in periods 1-3) for one finished game of the feed, else None."""
    if game.get("gameState") not in FINAL_STATES:
        return None
    home, away = (game.get("homeTeam") or {}).get("abbrev"), (game.get("awayTeam") or {}).get("abbrev")
    if not home or not away or "goals" not in game:
        return None
    hp, ap = [0, 0, 0], [0, 0, 0]
    for goal in game["goals"]:
        period, team = goal.get("period"), goal.get("teamAbbrev")
        if isinstance(team, dict):
            team = team.get("default")
        if not period or period > 3:
            continue                                   # period 4 and up is overtime or the shootout: no period's goal
        if team == home:
            hp[period - 1] += 1
        elif team == away:
            ap[period - 1] += 1
        else:
            return None                                # a goal for neither side: do not guess
    return hp, ap


def agrees(hp: list[int], ap: list[int], home_final, away_final) -> bool:
    """The final may exceed the regulation sums by ONE goal for ONE side (overtime / shootout), never trail them."""
    if home_final is None or away_final is None:
        return False
    dh, da = int(home_final) - sum(hp), int(away_final) - sum(ap)
    if (dh, da) == (0, 0):
        return sum(hp) != sum(ap)                      # decided in regulation, so not level after three
    return (dh, da) in ((1, 0), (0, 1)) and sum(hp) == sum(ap)


def fetch(day: str) -> list[dict]:
    for attempt in range(4):
        try:
            r = requests.get(URL.format(date=day), timeout=30)
            if r.status_code == 200:
                return r.json().get("games", [])
            logger.warning(f"{day}: HTTP {r.status_code}")
        except requests.RequestException as exc:
            logger.warning(f"{day}: {exc}")
        time.sleep(2 * (attempt + 1))
    return []


def run(first: str, last: str, apply: bool) -> dict:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT DISTINCT t.nhl_game_id, t.game_id, g.game_date, g.season, g.home_score, g.away_score
            FROM nhl_team_game_log t JOIN games g ON g.game_id = t.game_id
            WHERE t.game_date BETWEEN %s AND %s AND g.home_score IS NOT NULL
        """, (first, last)).fetchall()
        ours = {int(r[0]): {"game_id": r[1], "game_date": str(r[2])[:10], "season": int(r[3]),
                            "home": r[4], "away": r[5]} for r in rows}
        stored = {r[0] for r in conn.execute(
            "SELECT game_id FROM nhl_period_scores WHERE game_date BETWEEN %s AND %s", (first, last)).fetchall()}
        by_date: dict[str, list[int]] = defaultdict(list)
        for nhl_id, g in ours.items():
            if g["game_id"] not in stored:
                by_date[g["game_date"]].append(nhl_id)
        out = {"games_in_range": len(ours), "already_stored": len(ours) - sum(map(len, by_date.values())),
               "dates_to_read": len(by_date), "written": 0, "disagree": 0, "not_in_feed": 0}
        if not apply:
            return out
        payload, seen = [], {}

        def day_feed(d: str) -> list[dict]:
            if d not in seen:
                seen[d] = fetch(d)
                time.sleep(0.15)
            return seen[d]

        for day in sorted(by_date):
            # A late game is listed under the league's date, which can be ours or the day before.
            feed = {int(g["id"]): g for d in (day, (date.fromisoformat(day) - timedelta(days=1)).isoformat())
                    for g in day_feed(d) if g.get("id") is not None}
            for nhl_id in by_date[day]:
                got = period_goals(feed[nhl_id]) if nhl_id in feed else None
                if got is None:
                    out["not_in_feed"] += 1
                    continue
                hp, ap = got
                g = ours[nhl_id]
                if not agrees(hp, ap, g["home"], g["away"]):
                    out["disagree"] += 1
                    continue
                payload.append((g["game_id"], g["game_date"], g["season"], *hp, *ap, SOURCE))
            if len(payload) >= 500:
                out["written"] += _write(conn, payload)
                payload = []
        out["written"] += _write(conn, payload)
        return out
    finally:
        conn.close()


def _write(conn, payload: list[tuple]) -> int:
    if not payload:
        return 0
    conn.executemany("""INSERT INTO nhl_period_scores (game_id, game_date, season, home_p1, home_p2, home_p3,
                            away_p1, away_p2, away_p3, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""", payload)
    conn.commit()
    return len(payload)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="first", default=None, help="first game date, YYYY-MM-DD")
    ap.add_argument("--to", dest="last", default=None)
    ap.add_argument("--recent", type=int, default=None, help="the last N days instead of --from")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    last = a.last or date.today().isoformat()
    first = (date.today() - timedelta(days=a.recent)).isoformat() if a.recent else a.first
    if not first:
        ap.error("give --from DATE or --recent N")
    print(run(first, last, a.apply))


if __name__ == "__main__":
    main()

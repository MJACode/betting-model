"""NHL goals by period from the league's own score feed.

WHY. `nhl_period_scores` has two sources. `sbr_archive_nhl` stops on
2022-11-27. `nhl_api_score` was written once, on 2026-10-02, by the loader
that lived only on `origin/nhl-totals-derivatives` (commit ac2a29c1). That
file was never on master, and nothing in the scheduler called it, so the
table's newest `game_date` stayed 2026-09-30 while the season continued.
`step_nhl_results` already fetches `https://api-web.nhle.com/v1/score/<date>`
for final scores and drops the `goals` array. That array is the period.

WHAT IS WRITTEN. One row per finished regular-season or playoff game into
`nhl_period_scores` with `source = 'nhl_api_score'`. The key is
(game_id, source), so the archive's rows are left alone and a re-run writes
nothing twice. A game whose three period sums do not agree with its final —
the final may exceed them by one overtime or shootout goal, never trail
them — is skipped. `top_up` reads dates of NHL finals that still have no
`nhl_api_score` row, at most 40 dates a pass, and `step_nhl_results` calls
it after the score upsert.

    python -m data.ingestors.nhl_period_scores_api --through 2026-10-21
"""
from __future__ import annotations

import argparse
import time
from datetime import date

import requests
from loguru import logger

from data.db import get_connection
from data.ingestors.nhl_stats_ingestor import parse_nhl_game

URL = "https://api-web.nhle.com/v1/score/{date}"
SOURCE = "nhl_api_score"
FINAL_STATES = {"OFF", "FINAL"}
# The hole measured on 2026-10-21 was 20 dates. A pass that finds more than
# this finishes on the next nhl-results run rather than holding the refresh.
MAX_DATES = 40


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


def rows_for_feed(games: list[dict]) -> list[tuple]:
    """One `nhl_api_score` row per finished feed game whose periods agree with its final.

    The game id is `parse_nhl_game`'s, the same id `games` and the Eggz legs
    use. Preseason is skipped there. Two feed rows for one id keep the first.
    """
    out = []
    seen = set()
    for game in games:
        parsed = parse_nhl_game(game)
        got = period_goals(game) if parsed and parsed.get("home_score") is not None else None
        if parsed is None or got is None:
            continue
        hp, ap = got
        if parsed["game_id"] in seen or not agrees(hp, ap, parsed["home_score"], parsed["away_score"]):
            continue
        seen.add(parsed["game_id"])
        out.append((parsed["game_id"], parsed["game_date"], parsed["season"], *hp, *ap, SOURCE))
    return out


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


def missing_dates(conn, through: str) -> list[str]:
    """NHL finals on or before `through` that have no `nhl_api_score` row."""
    rows = conn.execute(
        "SELECT DISTINCT g.game_date FROM games g "
        "WHERE g.sport = 'NHL' AND g.home_score IS NOT NULL "
        "AND g.game_date >= '2022-11-28' AND g.game_date <= %s "
        "AND NOT EXISTS (SELECT 1 FROM nhl_period_scores p "
        "WHERE p.game_id = g.game_id AND p.source = %s) "
        "ORDER BY g.game_date",
        (through, SOURCE)).fetchall()
    return [str(r[0])[:10] for r in rows][:MAX_DATES]


def top_up(through: str | None = None, conn=None) -> int:
    """Write period rows for finals that do not have one yet. Returns how many rows were sent."""
    through = through or date.today().isoformat()
    own = conn is None
    if own:
        conn = get_connection()
    try:
        dates = missing_dates(conn, through)
        written = 0
        for day in dates:
            written += _write(conn, rows_for_feed(fetch(day)))
            time.sleep(0.15)
        if dates:
            logger.info(f"NHL period scores: {written} rows over {len(dates)} dates through {through}")
        return written
    finally:
        if own:
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
    ap.add_argument("--through", default=None, help="last game date, YYYY-MM-DD (default today)")
    a = ap.parse_args()
    print({"written": top_up(a.through)})


if __name__ == "__main__":
    main()

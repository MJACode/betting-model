"""NBA points by quarter from the ESPN scoreboard: what settles a first-half or
first-quarter bet, and a team total's overtime.

WHY. A first-half spread, first-quarter total or team total can only be graded
on the period line score, and `games` holds only the final. The NHL derivative
totals graded a team total on regulation goals and a push as an under win
(docs/nhl_derivative_totals.md); this table exists so NBA period markets are
graded on the number the book settles, not a stand-in.

ESPN's scoreboard (site.api, no key, reachable from the worker and from here)
lists every game on an ET date with `linescores` per competitor: one entry per
period, overtimes after the fourth. One call per date.

    nba_period_scores (game_id, period, home_points, away_points, source)

period 1-4 are the quarters; 5+ the overtimes. A first half is periods 1-2.

    python -m data.ingestors.nba_period_scores --start 2023-10-24 --end 2026-04-12
    python -m data.ingestors.nba_period_scores --days 3          # the worker path
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from loguru import logger

from data.anon_readable import lock_down
from data.db import get_connection
from data.ingestors.nba_espn_box import ESPN_NBA_SCOREBOARD_URL, et_date, nba_team

ET = ZoneInfo("America/New_York")
SOURCE = "espn_scoreboard"

DDL = """
CREATE TABLE IF NOT EXISTS nba_period_scores (
    game_id      TEXT NOT NULL,
    period       INTEGER NOT NULL,
    home_points  INTEGER NOT NULL,
    away_points  INTEGER NOT NULL,
    source       TEXT NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, period)
)
"""


def _int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def parse_period_rows(data: dict) -> list[dict]:
    """One row per (game, period) for every COMPLETED game between two NBA teams.

    A game whose two competitors list a different number of periods, or whose
    periods do not sum to the final, is skipped and logged: a wrong quarter
    score would grade a bet wrong, and a missing one only leaves it unsettled.
    """
    out = []
    for ev in (data or {}).get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        if not bool(((ev.get("status") or {}).get("type") or {}).get("completed")):
            continue
        sides = {}
        for c in comp.get("competitors") or []:
            team = c.get("team") or {}
            code = nba_team(team.get("abbreviation"), team.get("displayName"))
            lines = [_int(x.get("value")) for x in (c.get("linescores") or [])]
            sides[c.get("homeAway")] = (code, lines, _int(c.get("score")))
        if "home" not in sides or "away" not in sides:
            continue
        (home, hl, hs), (away, al, as_) = sides["home"], sides["away"]
        if not home or not away or not hl or len(hl) != len(al) or None in hl + al:
            continue
        if hs is not None and as_ is not None and (sum(hl) != hs or sum(al) != as_):
            logger.warning(f"{away}@{home} {ev.get('date')}: quarters do not sum to the final; skipped")
            continue
        gd = et_date(ev.get("date"))
        if not gd:
            continue
        gid = f"NBA_{gd}_{away}_{home}"
        for i, (h, a) in enumerate(zip(hl, al), start=1):
            out.append({"game_id": gid, "period": i, "home_points": h, "away_points": a,
                        "source": SOURCE})
    return out


def fetch_date(d: str, get=requests.get) -> dict | None:
    for attempt in range(4):
        try:
            r = get(ESPN_NBA_SCOREBOARD_URL, params={"dates": d.replace("-", ""), "limit": 50},
                    timeout=30)
            if r.status_code == 200:
                return r.json()
            logger.warning(f"scoreboard {d}: HTTP {r.status_code}")
            return None
        except requests.RequestException as exc:
            logger.warning(f"scoreboard {d}: {type(exc).__name__}; retry {attempt + 1}")
            time.sleep(2 * (attempt + 1))
    return None


def write(conn, rows: list[dict]) -> int:
    """Only for games we hold, and never over a stored period."""
    if not rows:
        return 0
    ids = sorted({r["game_id"] for r in rows})
    have = {x[0] for x in conn.execute(
        "SELECT game_id FROM games WHERE game_id = ANY(%s)", (ids,)).fetchall()}
    keep = [r for r in rows if r["game_id"] in have]
    conn.executemany("""
        INSERT INTO nba_period_scores (game_id, period, home_points, away_points, source)
        VALUES (%(game_id)s, %(period)s, %(home_points)s, %(away_points)s, %(source)s)
        ON CONFLICT (game_id, period) DO NOTHING
    """, keep)
    conn.commit()
    return len(keep)


def ensure_table(conn) -> None:
    conn.execute(DDL)
    lock_down(conn, "nba_period_scores")
    conn.commit()


def run(start: str, end: str) -> dict:
    conn = get_connection()
    try:
        ensure_table(conn)
        game_dates = {r[0] for r in conn.execute(
            "SELECT DISTINCT game_date FROM games WHERE sport = 'NBA' "
            "AND game_date BETWEEN %s AND %s AND home_score IS NOT NULL", (start, end)).fetchall()}
        done = {r[0] for r in conn.execute(
            "SELECT DISTINCT g.game_date FROM nba_period_scores p JOIN games g USING (game_id) "
            "WHERE g.game_date BETWEEN %s AND %s", (start, end)).fetchall()}
        todo = sorted(game_dates - done, reverse=True)
        stats = {"dates": len(todo), "rows": 0}
        for d in todo:
            data = fetch_date(d)
            if data is None:
                continue
            stats["rows"] += write(conn, parse_period_rows(data))
            time.sleep(0.3)
        return stats
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--days", type=int, help="the last N ET dates (the worker path)")
    a = ap.parse_args()
    if a.days:
        today = datetime.now(ET).date()
        start, end = (today - timedelta(days=a.days)).isoformat(), today.isoformat()
    else:
        start, end = a.start, a.end or date.today().isoformat()
    print(run(start, end))


if __name__ == "__main__":
    main()

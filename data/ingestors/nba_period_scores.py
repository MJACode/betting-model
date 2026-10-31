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

ROWS THAT DISAGREE WITH THE FINAL. first_half_from_periods is the one check a
first-half settlement trusts. A pick whose game fails it stays pending, and nothing
else could change that: both pulls below ask only for games with no row, and
write() never overwrites a stored period. So ensure_first_half_period_scores asks
ESPN again for such a game on every settle pass, and replaces its rows only with
rows that agree with the stored final. If ESPN's own quarters still disagree, it is
the final that does (data/ingestors/nba_stats_ingestor.py overwrites it on the local
job; nba_results_ingestor.py logs a differing ESPN score without writing it). Then
the rows and the pick are left alone, and tracking/system_health's settlement_lag
and settlement_stranded keep reporting the pick.

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


def first_half_from_periods(rows, home_score, away_score) -> tuple[int, int] | None:
    """(home, away) points in the first half from (period, home_points, away_points)
    rows, or None when a settlement cannot trust them.

    The rule is the first search's, which the graded bets were settled on
    (scripts/nba_derivative_lab.build_outcomes, read through
    scripts/nba_game_harness.with_periods): the periods sum to the stored final,
    are numbered 1..n with n >= 4, and periods 1 and 2 are both there. Overtime is a
    period, so it counts in the sum and never in the first half."""
    if not rows:
        return None
    per = {int(r[0]): (r[1], r[2]) for r in rows}
    n = max(per)
    if (n < 4 or set(per) != set(range(1, n + 1))
            or any(v is None for pts in per.values() for v in pts)
            or sum(p[0] for p in per.values()) != home_score
            or sum(p[1] for p in per.values()) != away_score):
        return None
    return per[1][0] + per[2][0], per[1][1] + per[2][1]


def replace_game(conn, game_id: str, rows: list[dict]) -> None:
    """Swap one game's stored periods for `rows`, in ONE transaction: a failure
    keeps the old rows, it cannot leave the game with no quarters."""
    conn.execute("DELETE FROM nba_period_scores WHERE game_id = %s", (game_id,))
    conn.executemany("""
        INSERT INTO nba_period_scores (game_id, period, home_points, away_points, source)
        VALUES (%(game_id)s, %(period)s, %(home_points)s, %(away_points)s, %(source)s)
    """, rows)
    conn.commit()


COLS = ("game_id", "period", "home_points", "away_points", "source", "fetched_at")


def ensure_table(conn) -> None:
    """Create once. A no-op CREATE still fires PostgREST's schema reload
    (data/ddl_guard.py), and the worker now calls this every day."""
    from data.anon_readable import API_ROLES
    from data.ddl_guard import schema_is_current
    if schema_is_current(conn, "nba_period_scores", columns=COLS, rls=True,
                         revoked_from=API_ROLES):
        return
    conn.execute(DDL)
    lock_down(conn, "nba_period_scores")
    conn.commit()


def run(start: str, end: str) -> dict:
    conn = get_connection()
    try:
        ensure_table(conn)
        # Per GAME, not per date: a date with one stored game is not done
        # while a later game on it still lacks its quarters (an evening pass
        # runs while the late games are being played).
        todo = sorted({r[0] for r in conn.execute(
            "SELECT DISTINCT g.game_date FROM games g WHERE g.sport = 'NBA' "
            "AND g.game_date BETWEEN %s AND %s AND g.home_score IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM nba_period_scores p WHERE p.game_id = g.game_id)",
            (start, end)).fetchall()}, reverse=True)
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


# The model whose picks settle on these rows, and how many of its dates one pass
# may fetch: one scoreboard call a date, newest first.
FIRST_HALF_MODEL = "nba_first_half_total_luck"
MAX_PENDING_DATES = 20


def _stored_periods(conn, game_id: str) -> list:
    return conn.execute(
        "SELECT period, home_points, away_points FROM nba_period_scores WHERE game_id = %s",
        (game_id,)).fetchall()


def _refused_games(conn) -> dict[str, dict]:
    """{game_id: {date, home, away}} for every game holding a pending first-half
    BET with a final and period rows that first_half_from_periods refuses."""
    rows = conn.execute(
        "SELECT DISTINCT p.game_id, p.game_date, g.home_score, g.away_score "
        "FROM picks p JOIN games g ON g.game_id = p.game_id "
        "WHERE p.model_id = %s AND p.signal_type = 'BET' AND p.result IS NULL "
        "AND g.home_score IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM nba_period_scores s WHERE s.game_id = p.game_id) "
        "ORDER BY p.game_date DESC LIMIT %s",
        (FIRST_HALF_MODEL, MAX_PENDING_DATES)).fetchall()
    return {gid: {"date": str(d), "home": home, "away": away} for gid, d, home, away in rows
            if first_half_from_periods(_stored_periods(conn, gid), home, away) is None}


def _repair(conn, gid: str, game: dict, fresh: list[dict]) -> bool:
    """Replace a refused game's stored rows, only with rows that agree with the
    stored final. -> whether the game's rows now agree."""
    if first_half_from_periods(_stored_periods(conn, gid), game["home"], game["away"]) is not None:
        return True          # write() filled in the period it was missing
    rows = [r for r in fresh if r["game_id"] == gid]
    agree = first_half_from_periods(
        [(r["period"], r["home_points"], r["away_points"]) for r in rows],
        game["home"], game["away"])
    if agree is None:
        logger.error(f"{gid}: ESPN's quarters do not add up to the stored final "
                     f"({game['away']}-{game['home']}) either"
                     f"{'' if rows else ' (the scoreboard did not return the game)'}, so the "
                     f"rows are left as they are and its first-half pick stays pending. "
                     f"Check the final.")
        return False
    logger.warning(f"{gid}: replacing its period rows {_stored_periods(conn, gid)} with ESPN's "
                   f"{[(r['period'], r['home_points'], r['away_points']) for r in rows]}, which "
                   f"add up to the stored final ({game['away']}-{game['home']})")
    replace_game(conn, gid, rows)
    return True


def ensure_first_half_period_scores(get=requests.get) -> dict:
    """Fetch the quarters of every game holding a pending first-half BET that has
    a final and no period row, or period rows that disagree with the final (repaired
    per game, module docstring), on this connection's own commits, for
    tracking/paper_tracker.settle_picks. One scoreboard call per such date; none
    when no pick waits, so it costs two reads on every other pass. The connection
    holds no transaction across a call."""
    conn = get_connection()
    try:
        ensure_table(conn)
        todo = [str(r[0]) for r in conn.execute(
            "SELECT DISTINCT p.game_date FROM picks p JOIN games g ON g.game_id = p.game_id "
            "WHERE p.model_id = %s AND p.signal_type = 'BET' AND p.result IS NULL "
            "AND g.home_score IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM nba_period_scores s WHERE s.game_id = p.game_id) "
            "ORDER BY p.game_date DESC LIMIT %s",
            (FIRST_HALF_MODEL, MAX_PENDING_DATES)).fetchall()]
        refused = _refused_games(conn)
        conn.rollback()
        dates = sorted({*todo, *(g["date"] for g in refused.values())}, reverse=True)
        stats = {"dates": len(dates), "rows": 0}
        if refused:
            stats.update(repaired=0, still_refused=0)
        for d in dates:
            data = fetch_date(d, get=get)
            parsed = parse_period_rows(data) if data is not None else []
            if data is not None:
                stats["rows"] += write(conn, parsed)
            for gid, game in refused.items():
                if game["date"] == d:
                    stats["repaired" if _repair(conn, gid, game, parsed) else "still_refused"] += 1
                    conn.rollback()      # the reads above: no transaction across a call
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

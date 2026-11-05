"""Is the NBA in-play loop doing its job? An output check, not a liveness one.

A loop that runs and decides nothing reads healthy on its heartbeat
(operations review, 2026-11-04). So system_health asks two questions of the
loop's OUTPUTS for a finished slate, and reads STALE when either fails:

  1. Every NBA game that went final has at least one row in
     nba_live_decisions. The loop writes a row at every attempt it makes on a
     game -- a decision, a skip with its reason, or 'carried' (no eligible
     quote) -- so a game with none is a game the loop never looked at.
  2. Every fetch window that needed a fetch has an Odds API call from the
     loop's source ('nba-live' in api_call_log). A window needed one when some
     game was within its first DECISION_SPAN_MIN minutes after its listed tip
     (quarters 1-3; the rules decide nothing later) and had not yet had all
     three rules decided before the window opened.

Pure helpers below; `check` runs them on a connection.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

LOOP_SOURCE = "nba-live"
ODDS_API = "The Odds API"
FETCH_OFFSET_SEC = 264.0
DECISION_SPAN_MIN = 100.0         # tip to the end of quarter 3, generously
CALL_SLACK_SEC = 600.0            # a call this long after the window opened still counts
DECIDED = ("bet", "no_bet", "declined")
N_RULES = 3


def windows_between(start: datetime, end: datetime, offset_s: float = FETCH_OFFSET_SEC) -> list[datetime]:
    """Every hour-minus-offset instant in [start, end]."""
    out = []
    h = (start + timedelta(seconds=offset_s)).replace(minute=0, second=0, microsecond=0)
    while True:
        inst = h - timedelta(seconds=offset_s)
        if inst > end:
            return out
        if inst >= start:
            out.append(inst)
        h += timedelta(hours=1)


def games_without_rows(final_games: list[str], ledger_games: set) -> list[str]:
    return sorted(g for g in final_games if g not in ledger_games)


def windows_without_calls(tips: dict, decided_at: dict, call_times: list[datetime],
                          span_min: float = DECISION_SPAN_MIN) -> list[datetime]:
    """Windows that needed a fetch and have no loop call.

    tips: {game_id: listed tip}; decided_at: {game_id: [decision times]};
    call_times: the loop's Odds API calls."""
    calls = sorted(call_times)
    need = set()
    for gid, tip in tips.items():
        for inst in windows_between(tip, tip + timedelta(minutes=span_min)):
            done = sum(1 for t in decided_at.get(gid, []) if t < inst)
            if done < N_RULES:
                need.add(inst)
    missing = []
    for inst in sorted(need):
        hi = inst + timedelta(seconds=CALL_SLACK_SEC)
        if not any(inst - timedelta(seconds=60) <= t <= hi for t in calls):
            missing.append(inst)
    return missing


def _ts(v) -> datetime | None:
    t = pd.to_datetime(str(v), utc=True, format="mixed", errors="coerce") if v is not None else None
    return None if t is None or pd.isna(t) else t.to_pydatetime()


def check(conn, game_date: str) -> tuple[str, str]:
    """('ok' | 'stale' | 'skipped', detail) for the slate of `game_date`."""
    rows = conn.execute("""
        SELECT game_id, commence_time FROM games
        WHERE sport = 'NBA' AND game_date = ? AND home_score IS NOT NULL
    """, (game_date,)).fetchall()
    if not rows:
        return "skipped", f"no final NBA game on {game_date}"
    tips = {str(g): t for g, ct in rows if (t := _ts(ct)) is not None}
    led = conn.execute("""
        SELECT game_id, outcome, decided_at FROM nba_live_decisions WHERE game_date = ?
    """, (game_date,)).fetchall()
    ledger_games = {str(r[0]) for r in led}
    decided_at: dict = {}
    for gid, outcome, at in led:
        if outcome in DECIDED and (t := _ts(at)) is not None:
            decided_at.setdefault(str(gid), []).append(t)
    start = min(tips.values()) - timedelta(minutes=10)
    end = max(tips.values()) + timedelta(minutes=DECISION_SPAN_MIN + 20)
    calls = conn.execute("""
        SELECT ts FROM api_call_log
        WHERE api = ? AND ts >= ? AND ts <= ? AND source = ?
    """, (ODDS_API, start.isoformat(), end.isoformat(), LOOP_SOURCE)).fetchall()
    call_times = [t for (v,) in calls if (t := _ts(v)) is not None]
    no_rows = games_without_rows(list(tips), ledger_games)
    no_calls = windows_without_calls(tips, decided_at, call_times)
    if not no_rows and not no_calls:
        return "ok", (f"{len(tips)} final game(s) on {game_date}, each with a row in nba_live_decisions; "
                      f"every window that needed a fetch made one")
    parts = []
    if no_rows:
        parts.append(f"{len(no_rows)} of {len(tips)} final game(s) with no row in nba_live_decisions: "
                     f"{', '.join(no_rows[:6])}")
    if no_calls:
        parts.append(f"{len(no_calls)} fetch window(s) with a game to decide and no Odds API call from "
                     f"'{LOOP_SOURCE}': {', '.join(t.strftime('%H:%M:%SZ') for t in no_calls[:6])}")
    return "stale", "; ".join(parts)

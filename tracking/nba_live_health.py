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
     (a quarters 1-2 quote can still sit in a fetch early in quarter 3; the
     loop fetches for nothing later) and had not yet had every live rule
     (models/nba_live_ig2.RULES) decided before the window opened.

The loop's first supervisor tick is GO_LIVE (2026-11-05 11:00
America/New_York). #1180 / #1184 reached production that morning inside the
cron's 3am-11am ET gap, so a game whose decision span ended before that tick,
and a fetch window that opened before it, are not an outage: the loop could
not have covered them. A slate with nothing left to score returns skipped.
Anything the loop could have covered is scored exactly as above.

Pure helpers below; `check` runs them on a connection.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from models.nba_live_ig2 import RULES as LIVE_RULES

LOOP_SOURCE = "nba-live"
ODDS_API = "The Odds API"
FETCH_OFFSET_SEC = 264.0
DECISION_SPAN_MIN = 100.0         # tip into quarter 3, generously
CALL_SLACK_SEC = 600.0            # a call this long after the window opened still counts
DECIDED = ("bet", "no_bet", "declined")
N_RULES = len(LIVE_RULES)        # the rules the loop decides; held-out ones never

# First nba_live tick after the loop shipped. scheduler.py runs it at
# minute */10 during hours 0-2 and 11-23 America/New_York. The deploy landed
# 2026-11-05 ~13:11-13:25 UTC (08:11-08:25 ET), so the next tick is 11:00 ET,
# which is 16:00 UTC (EST; DST ended 2026-11-01).
GO_LIVE = datetime(2026, 11, 5, 11, 0, tzinfo=ZoneInfo("America/New_York"))
GO_LIVE_LABEL = "2026-11-05 11:00 America/New_York"


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


def span_ended_before_go_live(tip: datetime, go_live: datetime = GO_LIVE,
                              span_min: float = DECISION_SPAN_MIN) -> bool:
    """True when tip + the decision span is already over before `go_live`.

    The loop writes a row only while a game is inside that span, so a game
    that finished the span earlier is one it could not have looked at."""
    return tip + timedelta(minutes=span_min) < go_live


def windows_without_calls(tips: dict, decided_at: dict, call_times: list[datetime],
                          span_min: float = DECISION_SPAN_MIN,
                          go_live: datetime | None = None) -> list[datetime]:
    """Windows that needed a fetch and have no loop call.

    tips: {game_id: listed tip}; decided_at: {game_id: [decision times]};
    call_times: the loop's Odds API calls. A window that opened before
    `go_live` is not missing: the loop was not running yet. `go_live` None
    keeps every window (the arithmetic, with no cutoff)."""
    calls = sorted(call_times)
    need = set()
    for gid, tip in tips.items():
        for inst in windows_between(tip, tip + timedelta(minutes=span_min)):
            if go_live is not None and inst < go_live:
                continue
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
    # A finished span is not the loop's. Drop those games before the row
    # check; their windows are dropped below with the same cutoff.
    uncovered = [g for g, t in tips.items() if span_ended_before_go_live(t)]
    covered = {g: t for g, t in tips.items() if g not in uncovered}
    if tips and not covered:
        return "skipped", (
            f"{len(tips)} final game(s) on {game_date} finished their decision span "
            f"before NBA in-play go-live ({GO_LIVE_LABEL}); the loop could not have "
            f"covered them, so they are not scored")
    note = ""
    if uncovered:
        note = (f"; {len(uncovered)} earlier final game(s) finished before NBA in-play "
                f"go-live ({GO_LIVE_LABEL}) and were not scored")
    led = conn.execute("""
        SELECT game_id, outcome, decided_at FROM nba_live_decisions WHERE game_date = ?
    """, (game_date,)).fetchall()
    ledger_games = {str(r[0]) for r in led}
    decided_at: dict = {}
    for gid, outcome, at in led:
        if outcome in DECIDED and (t := _ts(at)) is not None:
            decided_at.setdefault(str(gid), []).append(t)
    start = min(covered.values()) - timedelta(minutes=10)
    end = max(covered.values()) + timedelta(minutes=DECISION_SPAN_MIN + 20)
    calls = conn.execute("""
        SELECT ts FROM api_call_log
        WHERE api = ? AND ts >= ? AND ts <= ? AND source = ?
    """, (ODDS_API, start.isoformat(), end.isoformat(), LOOP_SOURCE)).fetchall()
    call_times = [t for (v,) in calls if (t := _ts(v)) is not None]
    no_rows = games_without_rows(list(covered), ledger_games)
    no_calls = windows_without_calls(covered, decided_at, call_times, go_live=GO_LIVE)
    if not no_rows and not no_calls:
        return "ok", (f"{len(covered)} final game(s) on {game_date}, each with a row in nba_live_decisions; "
                      f"every window that needed a fetch made one{note}")
    parts = []
    if no_rows:
        parts.append(f"{len(no_rows)} of {len(covered)} final game(s) with no row in nba_live_decisions: "
                     f"{', '.join(no_rows[:6])}")
    if no_calls:
        parts.append(f"{len(no_calls)} fetch window(s) with a game to decide and no Odds API call from "
                     f"'{LOOP_SOURCE}': {', '.join(t.strftime('%H:%M:%SZ') for t in no_calls[:6])}")
    return "stale", "; ".join(parts) + note

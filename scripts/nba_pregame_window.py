"""The NBA totals window's plan: ONE database read a tick for the three NBA game
total models.

scheduler.run_nba_total_luck_window runs every minute, 24x7, for
nba_total_luck (the full-game total, decided 61-66 minutes before tip:
scripts/nba_total_luck_window.py), nba_team_total_luck (the home team
total, fetched and decided 45-56 minutes out, its close 12-25 minutes out:
scripts/nba_team_total_luck_window.py) and nba_first_half_total_luck (the first
half's total, the same window as the team total:
scripts/nba_first_half_total_luck_window.py). One connection plans all three:
the slate is read once and handed to each model's plan.

WHY ONE JOB. Every scheduled job beats its heartbeat on every tick, on a
connection of its own (scheduler._with_heartbeat -> tracking/job_heartbeat
.beat), so a second every-minute job would cost 1,440 more connection opens a
day before its plan read anything; and every-minute connections are what
strained a Supabase session pool of 15 (scheduler.py, the note above
_nfl_lead_hours). A tick with nothing near any tip costs exactly what
nba_total_luck's tick cost alone: one connection, one slate read.

ONE MODEL'S PLAN CANNOT STOP ANOTHER'S. Each model's plan is read on its
own: one that raises is logged and recorded in `errors`, and the tick still
runs the other models' steps, then fails (the scheduler raises after
publishing, so the heartbeat records an error).

THE GAME NOBODY DECIDED (undecided_games). The job's own failure signal is its
heartbeat's last status, one row a job, which the next idle tick overwrites with
'ok', and it names no game. So what a real-money model must not do silently is
read from what it wrote: a regular-season game that has tipped with no decision
from a model is a game that model lost. tracking/failure_alerter reports it.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import scripts.nba_first_half_total_luck_card as h1card  # noqa: E402
import scripts.nba_first_half_total_luck_window as h1w  # noqa: E402
import scripts.nba_team_total_luck_card as ttcard  # noqa: E402
import scripts.nba_team_total_luck_window as ttw  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
import scripts.nba_total_luck_window as tlw  # noqa: E402
from data.db import get_connection  # noqa: E402

# The slate's horizon: the far end of any model's window.
HORIZON_MIN = max(tlw.LOOK_AHEAD_MIN[1], ttw.PLAN_HORIZON_MIN, h1w.PLAN_HORIZON_MIN)


@dataclass
class PregamePlan:
    # nba_total_luck: the games to fetch the board for and decide.
    total_luck: list[str] = field(default_factory=list)
    # nba_team_total_luck: the games to fetch and decide, and the bet games
    # owed their closing snapshot.
    team_total: ttw.Plan = field(default_factory=ttw.Plan)
    # nba_first_half_total_luck: the same two lists.
    first_half: ttw.Plan = field(default_factory=ttw.Plan)
    # {model id: the error} for a model whose plan raised this tick.
    errors: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.total_luck or self.team_total.decide or self.team_total.close
                    or self.first_half.decide or self.first_half.close or self.errors)


def plan(conn, now: datetime) -> PregamePlan:
    """Every model's plan from one slate read. Reads only."""
    games = tlcard.slate(conn, now, horizon_min=HORIZON_MIN)
    out = PregamePlan()
    for model, read in (("nba_total_luck", lambda: tlw.plan(conn, now, games=games)),
                        ("nba_team_total_luck", lambda: ttw.plan(conn, now, games=games)),
                        ("nba_first_half_total_luck", lambda: h1w.plan(conn, now, games=games))):
        try:
            got = read()
        except Exception as exc:  # noqa: BLE001 - the other models still run this tick
            logger.exception(f"NBA totals window: the {model} plan failed")
            out.errors[model] = repr(exc)
            try:
                conn.rollback()  # a failed read leaves the transaction unusable
            except Exception:  # noqa: BLE001
                pass
            continue
        if model == "nba_total_luck":
            out.total_luck = got
        elif model == "nba_team_total_luck":
            out.team_total = got
        else:
            out.first_half = got
    return out


# How far back a tipped game is looked for: long enough to outlast a night's
# outage, short enough that a lost game stops being named the next day.
UNDECIDED_LOOKBACK_HOURS = 24.0
# Each model's own reading of "decided", the one its plan skips a game on: a
# decision row, or any BET of that model on the game.
DECIDED_BY = (("nba_total_luck", tlcard.decided_games),
              ("nba_team_total_luck", ttcard.decided_games),
              ("nba_first_half_total_luck", h1card.decided_games))


def undecided_games(conn, now: datetime,
                    hours: float = UNDECIDED_LOOKBACK_HOURS) -> dict[str, list[str]]:
    """{model id: the regular-season games that tipped in the last `hours` with no
    decision from that model}. Models with none are left out. Reads only. A model
    whose decisions table does not exist yet has decided nothing, so every tipped
    game is named: the table is created by the model's first card."""
    tipped = tlcard.tipped_games(conn, now, hours)
    # A placeholder with no teams has no feed event, and is never planned.
    ids = sorted(g for g, v in tipped.items() if tlw.has_teams(v))
    out: dict[str, list[str]] = {}
    if not ids:
        return out
    for model, decided in DECIDED_BY:
        if model in config.RETIRED_MODELS:
            continue
        done = decided(conn, ids)
        lost = [g for g in ids if g not in done]
        if lost:
            out[model] = lost
    return out


def plan_tick(now: datetime | None = None) -> PregamePlan:
    conn = get_connection()
    try:
        return plan(conn, now or datetime.now(timezone.utc))
    finally:
        conn.close()


if __name__ == "__main__":
    print(plan_tick())

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

nba_prop_market gets the same watch (undecided_rule_games), over its regular-season
games and the play-in, playoff and Cup final games only it bets. It is a warning
there, not a page: the rule writes no decision when Pinnacle has no price in its
window (2 of 272 games for points, rebounds and assists in the search), so a game
it did not decide is not always a failure. It decided all 92 regular-season games
of 2026-10-20..11-01, so it stays quiet and has run live before the first of the
others. stranded_prop_bets names the worse case: a bet whose game has no final.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402
import scripts.nba_first_half_total_luck_card as h1card  # noqa: E402
import scripts.nba_first_half_total_luck_window as h1w  # noqa: E402
import scripts.nba_prop_market_card as rule_card  # noqa: E402
import scripts.nba_q1_trend_card as q1card  # noqa: E402
import scripts.nba_q1_trend_window as q1w  # noqa: E402
import scripts.nba_team_total_luck_card as ttcard  # noqa: E402
import scripts.nba_team_total_luck_window as ttw  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
import scripts.nba_total_luck_window as tlw  # noqa: E402
from data.db import get_connection  # noqa: E402
from models.nba_prop_market import parse_ts  # noqa: E402

_ET = ZoneInfo("America/New_York")

# The slate's horizon: the far end of any model's window.
HORIZON_MIN = max(tlw.LOOK_AHEAD_MIN[1], ttw.PLAN_HORIZON_MIN, h1w.PLAN_HORIZON_MIN, q1w.PLAN_HORIZON_MIN)


@dataclass
class PregamePlan:
    # nba_total_luck: the games to fetch the board for and decide.
    total_luck: list[str] = field(default_factory=list)
    # nba_team_total_luck: the games to fetch and decide, and the bet games
    # owed their closing snapshot.
    team_total: ttw.Plan = field(default_factory=ttw.Plan)
    # nba_first_half_total_luck: the same two lists.
    first_half: ttw.Plan = field(default_factory=ttw.Plan)
    # nba_q1_trend (the first-quarter spread): the same two lists.
    first_quarter: ttw.Plan = field(default_factory=ttw.Plan)
    # {model id: the error} for a model whose plan raised this tick.
    errors: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.total_luck or self.team_total.decide or self.team_total.close
                    or self.first_half.decide or self.first_half.close
                    or self.first_quarter.decide or self.first_quarter.close or self.errors)


def plan(conn, now: datetime) -> PregamePlan:
    """Every model's plan from one slate read. Reads only."""
    games = tlcard.slate(conn, now, horizon_min=HORIZON_MIN)
    out = PregamePlan()
    for model, read in (("nba_total_luck", lambda: tlw.plan(conn, now, games=games)),
                        ("nba_team_total_luck", lambda: ttw.plan(conn, now, games=games)),
                        ("nba_first_half_total_luck", lambda: h1w.plan(conn, now, games=games)),
                        ("nba_q1_trend", lambda: q1w.plan(conn, now, games=games))):
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
        elif model == "nba_first_half_total_luck":
            out.first_half = got
        else:
            out.first_quarter = got
    return out


# How far back a tipped game is looked for: long enough to outlast a night's
# outage, short enough that a lost game stops being named the next day.
UNDECIDED_LOOKBACK_HOURS = 24.0
# Each model's own reading of "decided", the one its plan skips a game on: a
# decision row, or any BET of that model on the game.
DECIDED_BY = (("nba_total_luck", tlcard.decided_games),
              ("nba_team_total_luck", ttcard.decided_games),
              ("nba_first_half_total_luck", h1card.decided_games),
              ("nba_q1_trend", q1card.decided_games))


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


def _listed_without_a_row(conn, now: datetime, hours: float) -> dict[str, str]:
    """{game_id: type} for postseason games the schedule lists that tipped in the last `hours` and
    have no `games` row, so nothing could price them.

    A row the schedule holds is not a game someone owes. The refresh never deletes, so a Game 6
    of a series that ended stays listed, and the feed never writes it. So a row counts only if the
    refresh confirmed it on the game's own date (updated_at: it stamps only what ESPN still
    lists), it is not postponed and it has two real teams. A row with no tip yet counts once
    its date is over. And not when the feed holds the game the other way round: that row is the
    game, and the rule's own read looks at it."""
    today = now.astimezone(_ET).date()
    oldest = now - timedelta(hours=hours)
    first_day = oldest.astimezone(_ET).date().isoformat()
    rows = conn.execute("""
        SELECT s.game_id, s.game_date, s.game_type, s.commence_time, s.home_team, s.away_team,
               s.status_text, s.updated_at
        FROM nba_schedule s
        LEFT JOIN games g ON g.game_id = s.game_id
        WHERE s.game_type = ANY(%s) AND s.game_date = ANY(%s) AND g.game_id IS NULL
    """, (list(tl.POSTSEASON_TYPES),
          [(today + timedelta(days=d)).isoformat() for d in (-2, -1, 0)])).fetchall()
    found: dict[str, tuple[str, str]] = {}
    for gid, gd, kind, ct, home, away, status, updated in rows:
        day = str(gd)[:10]
        if not tlw.has_teams({"home": home, "away": away}) or re.search(tl._POSTPONED, str(status or "")):
            continue
        y, m, d = (int(x) for x in day.split("-"))
        stamped = parse_ts(updated)
        if stamped is None or stamped < datetime(y, m, d, tzinfo=_ET):
            continue
        tip = parse_ts(ct)
        tipped = oldest <= tip <= now if tip is not None else first_day <= day < today.isoformat()
        if tipped:
            found[gid] = (kind, f"NBA_{day}_{home}_{away}")
    if not found:
        return {}
    flipped = {r[0] for r in conn.execute("SELECT game_id FROM games WHERE game_id = ANY(%s)",
                                          ([f for _, f in found.values()],)).fetchall()}
    return {g: kind for g, (kind, f) in found.items() if f not in flipped}


def undecided_rule_games(conn, now: datetime, hours: float = UNDECIDED_LOOKBACK_HOURS) -> dict:
    """nba_prop_market's games that tipped in the last `hours` with no decision.

    -> {"lost": {game_id: 'regular', its postseason type or 'unlisted'},
        "refused": {game_id: the id the schedule lists the game under}}. Reads only. A refused
    row is not a lost game, because the real game has its own id, which is named if it was lost;
    it is reported apart, because a bet could have been left on it had it not been refused. A
    placeholder with no teams is never planned, so never lost."""
    refused: dict[str, str] = {}
    tipped = rule_card.tipped_rule_games(conn, now, hours, refused)
    kinds = {g: (v.get("game_type") or "unlisted") if v.get("postseason") else "regular"
             for g, v in tipped.items() if tlw.has_teams(v)}
    kinds.update(_listed_without_a_row(conn, now, hours))
    ids = sorted(kinds)
    done = (rule_card.decided_games(conn, ids) | rule_card.games_with_a_bet(conn, ids)) if ids else set()
    return {"lost": {g: kinds[g] for g in ids if g not in done}, "refused": refused}


# A bet whose game has no final never settles, and nothing else says so: settlement and the two
# settlement health checks all start from a final score. 12 hours outlasts any game and the results
# step's next passes. 30 days keeps a stranded bet named until someone acts on it.
STRANDED_AFTER_HOURS = 12.0
STRANDED_LOOKBACK_DAYS = 30


def stranded_prop_bets(conn, now: datetime) -> dict[str, int]:
    """{game_id: open bets} for NBA prop bets, of either model, whose tip is over
    STRANDED_AFTER_HOURS old with no final on their game. It takes a person, and the alert names both
    cases: a played game whose final landed on another row gets that final and box written onto
    this row, never a void; a postponed or cancelled game settles NO_ACTION by scripts/void_picks.py."""
    from scripts.nba_props_card import PROP_MODEL_IDS
    since = (now - timedelta(days=STRANDED_LOOKBACK_DAYS)).astimezone(_ET).date().isoformat()
    rows = conn.execute("""
        SELECT p.game_id, p.game_date, p.game_time, g.commence_time
        FROM picks p
        JOIN games g ON g.game_id = p.game_id
        WHERE p.model_id = ANY(%s) AND p.game_date >= %s AND p.signal_type = 'BET'
          AND p.result IS NULL AND p.condition_status IS DISTINCT FROM 'VOID'
          AND g.home_score IS NULL
    """, (list(PROP_MODEL_IDS), since)).fetchall()
    cut = now - timedelta(hours=STRANDED_AFTER_HOURS)
    out: dict[str, int] = {}
    for gid, gd, game_time, ct in rows:
        tip = parse_ts(game_time) or parse_ts(ct)
        if tip is None:                     # no start stored anywhere: its date, ET, is over
            y, m, d = (int(x) for x in str(gd)[:10].split("-"))
            tip = datetime(y, m, d, 23, 59, tzinfo=_ET)
        if tip < cut:
            out[gid] = out.get(gid, 0) + 1
    return out


def plan_tick(now: datetime | None = None) -> PregamePlan:
    conn = get_connection()
    try:
        return plan(conn, now or datetime.now(timezone.utc))
    finally:
        conn.close()


if __name__ == "__main__":
    print(plan_tick())

"""The NHL goalie window: decide each NHL game soon after both goalies are confirmed.

WHY. mike, 2026-10-20: "We should absolutely always know the goalie matchup
before making a bet as well." No NHL model bets until both starting goalies
are confirmed (models/nhl_goalie_gate.py), so a game's decision moment is now
the confirmation, and confirmations land at no fixed time: after the morning
skate for most games, at warmups (about 25 minutes before puck drop) for some.
The refresh passes run hourly at :17 from 7am to 5pm ET and every ten minutes
from 6 to 11pm, so a matinee confirmed at warmups could fall between two
hourly passes and never be decided. This job puts a look every five minutes
over the hours NHL games are confirmed and played.

WHAT A TICK DOES (scheduler.run_nhl_goalie_window, every five minutes from
11:00 to 23:55 ET):
  1. today_slate(): today's unstarted NHL games, the same slate the prop cards
     use (scripts/nhl_prop_card.slate). None: the tick returns, no call made.
  2. The goalie poll for today's games (run_pipeline step
     nhl-goalie-designations-today: ESPN, DailyFaceoff, and the rewrite of a
     goalie row ESPN's confirmation contradicts).
  3. plan(): the games whose matchup is known and that this process has not
     decided at that matchup yet. A restart forgets, and the next tick runs
     the deciders once more for every known game; each of them is insert-once,
     so the re-run writes nothing already written.
  4. If any: the NHL game odds (run_pipeline step nhl-odds), so the side
     models and the totals card price a fetch taken after the confirmation
     (each refuses a game whose newest fetch predates it); the NHL prop odds
     step (it buys only what is owed, including the snapshot a game owes once
     its goalies are confirmed, data/ingestors/nhl_prop_odds_ingestor.due);
     the two side models for exactly those games (`--score`, below), the
     totals card, the prop cards, then publish. No game odds: the side models
     and the totals card wait for the next tick.

A tick does nothing at all, the poll included, while a refresh pass or the
daily run is in progress (each polls and runs the same deciders itself), and
it holds its lock from the poll to the publish, so a goalie row is never
rewritten in the middle of a pass's scoring.

`--score` is models.scorer.run_scorer with `only_games` and
`game_models_only=True`: the pre-game line poller's own entry point, the one
scoring implementation, restricted to the NHL games named. It clears and
rewrites only those games' game-model rows.

    python -m scripts.nhl_goalie_window                 # print what a tick would decide
    python -m scripts.nhl_goalie_window --score G1 G2   # score exactly these NHL games
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nhl_goalie_gate as goalie_gate  # noqa: E402
from data.db import get_connection  # noqa: E402
from scripts.nhl_prop_card import slate  # noqa: E402

_ET = ZoneInfo("America/New_York")


@dataclass
class Plan:
    games: list[str] = field(default_factory=list)       # today's unstarted NHL games
    decide: dict = field(default_factory=dict)          # game_id -> known_at, not yet decided here
    held: dict = field(default_factory=dict)            # game_id -> why it is not known


def today_slate(conn, now: datetime) -> dict[str, dict]:
    return slate(conn, now.astimezone(_ET).date().isoformat(), now)


def plan(conn, now: datetime, decided: dict | None = None) -> Plan:
    """What this tick has to decide, from what is stored. No network call.

    `decided` is {game_id: known_at} for the games this process has already
    run the deciders on; a game whose matchup became known again at a new
    moment (a different goalie confirmed) is decided again.
    """
    decided = decided or {}
    games = today_slate(conn, now)
    states = goalie_gate.matchup_states(conn, list(games), now=now)
    known = {g: m.known_at for g, m in states.items() if m.reason is None}
    held = {g: m.reason for g, m in states.items() if m.reason is not None}
    due = {g: t for g, t in known.items() if g not in decided or decided[g] != t}
    return Plan(games=sorted(games), decide=dict(sorted(due.items())), held=held)


def plan_tick(decided: dict | None = None, now: datetime | None = None) -> Plan:
    conn = get_connection()
    try:
        return plan(conn, now or datetime.now(timezone.utc), decided)
    finally:
        conn.close()


def has_games_today(now: datetime | None = None) -> bool:
    conn = get_connection()
    try:
        return bool(today_slate(conn, now or datetime.now(timezone.utc)))
    finally:
        conn.close()


def score(game_ids: list[str]) -> dict:
    """The NHL side models for exactly these games, through the one scorer."""
    import config
    from models.scorer import run_scorer
    ids = {g for g in game_ids if str(g).startswith("NHL_")}
    if not ids:
        return {"total_picks": 0, "scored_games": 0}
    return run_scorer(target_date=config.today_et(), only_games=ids, game_models_only=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--score", nargs="+", metavar="GAME_ID",
                    help="score exactly these NHL games with the NHL game models")
    a = ap.parse_args()
    if a.score:
        logger.info(f"NHL goalie window scoring: {score(a.score)}")
        return
    print(plan_tick())


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/): the scorer can call the
    # MLB schedule for postponements. Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nhl-goalie-window")
    except Exception:  # noqa: BLE001
        pass

    main()

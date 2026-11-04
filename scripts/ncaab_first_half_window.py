"""The NCAAB first-half window: the first-half fetches and the runs of the
ncaab_first_half_spread and ncaab_first_half_total cards.

Planned every minute (scheduler.run_ncaab_first_half_window, 24x7). A tick:
  1. plan(): the NCAAB games dated today or tomorrow (Eastern) that have not
     tipped and whose full-game spread the feed lists (a stored bettable-book
     spread in latest_odds: the capture job stores one within five minutes of
     a game appearing on the board; a game the feed does not list has no
     first-half market and no event to call). For each, the newest fetch time
     that has passed (data/ingestors/ncaab_first_half_odds.MARKS: 15:00 UTC on
     its date, then 180, 120, 60, 50, 40, 30, 20 and 10 minutes before tip)
     with no ok call since is due. And the games each card must look at: not
     decided by it, ten minutes or less from tip for the spread card, sixty
     for the total card. Reads only; no API call.
  2. --fetch G...: one event call per due game, the decision fetches first
     (data/ingestors/ncaab_first_half_odds.py). Exit 1 when a call failed, not
     when the books offered nothing.
  3. The spread card (scripts/ncaab_first_half_spread_card.py) decides each
     game on its tip-minus-10 fetch, the total card
     (scripts/ncaab_first_half_total_card.py) on its tip-minus-60 fetch; each
     writes its bets, and the job publishes them.

THE DECISION FETCH, AND WHAT HAPPENS WHEN IT FAILS. The research graded one
instant: the purchase ten minutes before tip. The tick at tip minus 10 makes
the call; when it fails, the next tick (a minute later) calls again, because
that time stays due until an ok call lands. The card decides on a call made
for that time that landed 5 to 10 minutes before tip
(scripts/ncaab_first_half_spread_card.DECISION_LEAD_MIN). If none has
landed by 5 minutes before tip the game is not decided and the run reports it:
the 20-minute fetch is NOT used instead. It is ten minutes further from the
graded instant than any retry inside the window, and the research only
supports tip minus 10. The total's decision fetch is the call at tip minus 60,
retried the same way; it decides on one that landed 55 to 60.5 minutes before
tip (scripts/ncaab_first_half_total_card.DECISION_LEAD_MIN), and the 50-minute
fetch is not used instead.

    python -m scripts.ncaab_first_half_window                 # print what a tick would do
    python -m scripts.ncaab_first_half_window --fetch G1 G2   # fetch these games now
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.ingestors.ncaab_first_half_odds as feed  # noqa: E402
import models.ncaab_first_half_spread as fh  # noqa: E402
from data.db import get_connection  # noqa: E402

_ET = ZoneInfo("America/New_York")
# The card is run once a game is this close to tip and not decided.
CARD_LEAD_MIN = 10.5
# The first-half total card, the same way, at its own decision time.
TOTAL_CARD_LEAD_MIN = 60.5


def enabled() -> bool:
    """The kill switch: RUN_NCAAB_FIRST_HALF=0 (or false/off/no) stops the
    fetches and the card before anything is read or bought. Default on."""
    return (os.environ.get("RUN_NCAAB_FIRST_HALF", "1").strip().lower()
            not in ("0", "false", "off", "no"))


@dataclass
class Plan:
    fetch: list = field(default_factory=list)       # game ids due a call
    marks: dict = field(default_factory=dict)       # game id -> mark
    card: list = field(default_factory=list)        # undecided games <= CARD_LEAD_MIN out
    total_card: list = field(default_factory=list)  # undecided by the total card, <= TOTAL_CARD_LEAD_MIN

    def __bool__(self) -> bool:
        return bool(self.fetch or self.card or self.total_card)


def slate(conn, now: datetime) -> dict[str, dict]:
    """NCAAB games dated today or tomorrow (Eastern) that have not tipped."""
    today = now.astimezone(_ET).date()
    dates = [(today + timedelta(days=d)).isoformat() for d in (0, 1)]
    rows = conn.execute("""
        SELECT game_id, season, game_date, commence_time, home_team, away_team
        FROM games WHERE sport = 'NCAAB' AND game_date = ANY(%s)
    """, (dates,)).fetchall()
    out = {}
    for gid, season, gd, ct, home, away in rows:
        tip = feed._when(ct) if ct else None
        if tip is None or tip <= now:
            continue
        out[gid] = {"season": int(season), "game_date": str(gd)[:10], "tip": tip,
                    "commence_time": ct, "home": home, "away": away}
    return out


def listed(conn, game_ids: list[str]) -> set[str]:
    """Games with a bettable book's full-game spread stored (latest_odds, one
    row per game, market and book)."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM latest_odds
        WHERE game_id = ANY(%s) AND market = 'spreads' AND bookmaker = ANY(%s)
    """, (list(game_ids), list(fh.BOOKS))).fetchall()}


def lead_minutes(tip: datetime, t: datetime) -> float:
    return (tip - t).total_seconds() / 60.0


def plan(conn, now: datetime) -> Plan:
    """What this tick has to do, from what is stored. Reads only."""
    from scripts.ncaab_first_half_spread_card import decided_games
    from scripts.ncaab_first_half_total_card import decided_games as total_decided
    games = slate(conn, now)
    if not games:
        return Plan()
    games = {g: v for g, v in games.items() if g in listed(conn, sorted(games))}
    if not games:
        return Plan()
    last = feed.last_fetches(conn, sorted(games))
    tried = feed.last_fetches(conn, sorted(games), ok_only=False)
    p = Plan()
    for gid, g in sorted(games.items()):
        due = feed.due_mark(g["game_date"], g["tip"], now, last.get(gid), tried.get(gid))
        if due is not None:
            p.fetch.append(gid)
            p.marks[gid] = due[0]
    near = sorted(g for g, v in games.items() if lead_minutes(v["tip"], now) <= CARD_LEAD_MIN)
    if near:
        done = decided_games(conn, near)
        p.card = [g for g in near if g not in done]
    near = sorted(g for g, v in games.items()
                  if lead_minutes(v["tip"], now) <= TOTAL_CARD_LEAD_MIN)
    if near:
        done = total_decided(conn, near)
        p.total_card = [g for g in near if g not in done]
    return p


UNDECIDED_LOOKBACK_HOURS = 24.0


SPREAD_MODEL = "ncaab_first_half_spread"
TOTAL_MODEL = "ncaab_first_half_total"


def undecided_games(conn, now: datetime,
                    hours: float = UNDECIDED_LOOKBACK_HOURS,
                    model: str = SPREAD_MODEL) -> list[str]:
    """The listed NCAAB games that tipped in the last `hours` with no decision
    from `model` (ncaab_first_half_spread or ncaab_first_half_total), for the
    failure alerter. Reads only.

    Only games that tipped after this feed's first call are counted (the
    ledger's oldest row): before it, the model did not exist. The total model
    came later, so for it only games that tipped after its own first decision
    (its ledger's oldest row) count; with none yet, nothing is named. No feed
    ledger yet, nothing named; a job that never ran is the heartbeat check's to
    report. The window job's own error beat is overwritten by the next idle
    tick a minute later, so this is what names a game the model lost."""
    if model == TOTAL_MODEL:
        from scripts.ncaab_first_half_total_card import decided_games, first_decision
    else:
        from scripts.ncaab_first_half_spread_card import decided_games
        first_decision = None
    if not feed.ledger_exists(conn):
        return []
    row = conn.execute(f"SELECT MIN(fetch_at) FROM {feed.LEDGER_TABLE}").fetchone()
    first = feed._aware(row[0]) if row else None
    if first is None:
        return []
    if first_decision is not None:
        began = first_decision(conn)
        if began is None:
            return []
        first = max(first, began)
    today = now.astimezone(_ET).date()
    dates = [(today - timedelta(days=d)).isoformat() for d in (0, 1, 2)]
    rows = conn.execute("""
        SELECT game_id, commence_time FROM games WHERE sport = 'NCAAB' AND game_date = ANY(%s)
    """, (dates,)).fetchall()
    since = max(first, now - timedelta(hours=hours))
    tipped = sorted(g for g, ct in rows
                    if (t := feed._when(ct) if ct else None) is not None and since <= t <= now)
    if not tipped:
        return []
    have = listed(conn, tipped)
    tipped = [g for g in tipped if g in have]
    done = decided_games(conn, tipped)
    return [g for g in tipped if g not in done]


def plan_tick(now: datetime | None = None) -> Plan:
    """This tick's plan on its own connection (the scheduler's call)."""
    if not enabled():
        return Plan()
    conn = get_connection()
    try:
        return plan(conn, now or datetime.now(timezone.utc))
    finally:
        conn.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", nargs="+", metavar="GAME_ID",
                    help="fetch and store the first-half lines of exactly these games")
    a = ap.parse_args(argv)
    if a.fetch:
        if not enabled():
            logger.info("NCAAB first half: RUN_NCAAB_FIRST_HALF is off; nothing bought")
            return
        result = feed.fetch_first_half(a.fetch)
        logger.info(f"NCAAB first-half fetch: {result}")
        if result.get("failed"):
            # A failed call is logged and the run goes on to the next game; a
            # run with one must say so, so the job's heartbeat records an
            # error. A game whose books offered no first-half line is not one.
            logger.error(f"NCAAB first-half window: the call failed for {result['failed']}")
            sys.exit(1)
        return
    print(plan_tick())


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/): the fetch is a paid
    # Odds API call. Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-first-half-window")
    except Exception:  # noqa: BLE001
        pass
    main()

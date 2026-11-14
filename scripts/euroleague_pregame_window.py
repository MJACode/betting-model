"""The EuroLeague pre-game window: the period-and-full-game fetches and the
runs of the EuroLeague pre-game card (five rules, models/euroleague_pregame.py).

Planned every minute (scheduler.run_euroleague_pregame_window, 24x7). A tick:
  1. plan(): the EuroLeague games tipping in the next 70 minutes, and, for
     each, the newest fetch time that has passed
     (data/ingestors/euroleague_period_odds.MARKS: 60, 10 and 2 minutes before
     tip) with no ok call since; and whether the card has a game to look at
     (10.5 minutes or less from tip, or tipped in the last 3 hours, with a
     switched-on model undecided). Reads only; no API call.
  2. --fetch G...: one event call per due game, the decision fetch first
     (data/ingestors/euroleague_period_odds.py). Exit 1 when a call failed, not
     when the books offered nothing. RUN_EUROLEAGUE_PERIOD_FEED=0 stops the
     calls alone.
  3. The card (scripts/euroleague_pregame_card.py) decides each game once per
     model on its tip-minus-10 fetch, writes its bets and NONE rows, and the
     job publishes them.

THE DECISION FETCH, AND WHAT HAPPENS WHEN IT FAILS. The tick at tip minus 10
makes the call; when it fails the next tick (a minute later) calls again,
because that time stays due until an ok call lands. The card decides on a
call that landed 5 to 10.5 minutes before tip. If none has by 5 minutes before
tip, the full-game rules decide on the stored board as of tip minus 10 and the
period rules record `missed` (scripts/euroleague_pregame_card.py).

    python -m scripts.euroleague_pregame_window                 # print what a tick would do
    python -m scripts.euroleague_pregame_window --fetch G1 G2   # fetch these games now
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.ingestors.euroleague_period_odds as feed  # noqa: E402
import scripts.euroleague_pregame_card as card  # noqa: E402
from data.db import get_connection  # noqa: E402

# Games this far from tip are planned (the first fetch is at tip minus 60).
PLAN_LEAD_MIN = 70.0


def enabled() -> bool:
    """RUN_EUROLEAGUE_PREGAME=0 (or false/off/no) stops the fetches and the
    card before anything is read or bought. Default on."""
    return card.enabled()


@dataclass
class Plan:
    fetch: list = field(default_factory=list)       # game ids due a call
    marks: dict = field(default_factory=dict)       # game id -> mark
    card: list = field(default_factory=list)        # games the card must look at

    def __bool__(self) -> bool:
        return bool(self.fetch or self.card)


def slate(conn, now: datetime) -> dict[str, dict]:
    """EuroLeague games tipping in the next PLAN_LEAD_MIN minutes."""
    days = [(now + timedelta(days=d)).date().isoformat() for d in (-1, 0, 1)]
    rows = conn.execute("""
        SELECT game_id, commence_time FROM games WHERE sport = %s AND game_date = ANY(%s)
    """, (feed.SPORT, days)).fetchall()
    out = {}
    for gid, ct in rows:
        tip = feed._when(ct) if ct else None
        if tip is None or tip <= now or (tip - now).total_seconds() / 60.0 > PLAN_LEAD_MIN:
            continue
        out[gid] = {"tip": tip}
    return out


def plan(conn, now: datetime) -> Plan:
    """What this tick has to do, from what is stored. Reads only."""
    p = Plan()
    games = slate(conn, now)
    if games and feed.enabled():
        last = feed.last_fetches(conn, sorted(games))
        tried = feed.last_fetches(conn, sorted(games), ok_only=False)
        for gid, g in sorted(games.items()):
            due = feed.due_mark(g["tip"], now, last.get(gid), tried.get(gid))
            if due is not None:
                p.fetch.append(gid)
                p.marks[gid] = due[0]
    near = card.slate(conn, now)
    on = card.models_on()
    if near and on:
        done = card.decided(conn, sorted(near))
        p.card = sorted(g for g in near if any((g, m) not in done for m in on))
    return p


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
                    help="fetch and store the period and full-game lines of exactly these games")
    a = ap.parse_args(argv)
    if a.fetch:
        if not enabled() or not feed.enabled():
            logger.info("EuroLeague periods: the feed is switched off; nothing bought")
            return
        result = feed.fetch_periods(a.fetch)
        logger.info(f"EuroLeague period fetch: {result}")
        if result.get("failed"):
            logger.error(f"EuroLeague pre-game window: the call failed for {result['failed']}")
            sys.exit(1)
        return
    print(plan_tick())


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/): the fetch is a paid
    # Odds API call. Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("euroleague-pregame-window")
    except Exception:  # noqa: BLE001
        pass
    main()

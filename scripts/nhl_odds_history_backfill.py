"""Buy historical NHL game lines: DraftKings + Pinnacle (+8 books), open and near-close.

Approved by mike 2026-09-20 ("about 200,000 credits"). This is the measuring
stick docs/nhl_market_research.md §7 asks for: without past prices no NHL idea
can be graded against a line, and `odds` holds none before 2026-07-19.

WHAT IT PULLS. Moneyline, puck line and total for every game date 2020-21 ->
2025-26 (the feed has no NHL before 2020-06, and Pinnacle from ~2020-09):

  * one OPEN snapshot per game date, at 16:00Z (noon ET), and
  * one NEAR-CLOSE snapshot at the top of every hour in which a game that day
    STARTS — read from `games.commence_time`, so a 7:07pm ET game is priced at
    7:00pm and a day with three start hours costs three calls, not eight.

TEN BOOKS, NOT FOURTEEN. `config.ODDS_HISTORY_BOOKMAKERS` names 14, and the
feed bills "every group of 10 bookmakers" as one region — 14 would double every
call to 60 credits. BOOKS below is ten: 30 credits a call.

It drives `odds_ingestor.run_historical_odds_range`, one date at a time, so it
inherits the pull LEDGER (a re-run costs nothing for what is stored), the
in-play relabel, and the `source` stamp. The credit guard is
`odds_quota.plan_credit_budget`: the ceiling is this run's own printed plan,
the floor is measured burn x reserve days, and it REFUSES rather than guesses.

    python -m scripts.nhl_odds_history_backfill                 # the plan, no spend
    python -m scripts.nhl_odds_history_backfill --apply
    python -m scripts.nhl_odds_history_backfill --apply --reserve-days 0   # operator's call
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, ".")

from loguru import logger

from data.db import get_connection
from data.ingestors import odds_quota
from data.ingestors.odds_ingestor import run_historical_odds_range

BOOKS = ["draftkings", "pinnacle", "fanduel", "betmgm", "williamhill_us",
         "espnbet", "fanatics", "bovada", "betrivers", "hardrockbet"]
MARKETS = ["h2h", "spreads", "totals"]
CREDITS_PER_CALL = 10 * len(MARKETS)        # <= 10 named books = one region
OPEN_HOUR_UTC = 16
SEASONS = (2021, 2026)


def plan(conn, first_season: int, last_season: int) -> dict[str, list[int]]:
    """UTC date -> the hours to snapshot on it."""
    rows = conn.execute("""
        SELECT game_date, commence_time FROM games
        WHERE sport = 'NHL' AND season BETWEEN ? AND ?
          AND home_score IS NOT NULL AND commence_time IS NOT NULL
    """, (first_season, last_season)).fetchall()
    hours: dict[str, set[int]] = defaultdict(set)
    for game_date, commence in rows:
        hours[game_date[:10]].add(OPEN_HOUR_UTC)
        t = datetime.fromisoformat(str(commence).replace("Z", "+00:00")).astimezone(timezone.utc)
        hours[t.date().isoformat()].add(t.hour)      # late ET starts fall on the next UTC date
    return {d: sorted(h) for d, h in sorted(hours.items())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--seasons", nargs=2, type=int, default=list(SEASONS))
    ap.add_argument("--max-credits", type=int, default=None,
                    help="ceiling for the whole pull (default: this run's own plan)")
    ap.add_argument("--reserve-days", type=int, default=odds_quota.DEFAULT_RESERVE_DAYS)
    a = ap.parse_args()

    conn = get_connection()
    try:
        schedule = plan(conn, *a.seasons)
        calls = sum(len(h) for h in schedule.values())
        print(f"{len(schedule):,} dates, {calls:,} snapshots, "
              f"{calls * CREDITS_PER_CALL:,} credits at {CREDITS_PER_CALL} a call "
              f"({len(BOOKS)} books, {', '.join(MARKETS)})")
        budget, problems = odds_quota.plan_credit_budget(
            conn, shard_calls=calls, total_calls=calls,
            credits_per_call=CREDITS_PER_CALL, max_credits=a.max_credits,
            reserve_days=a.reserve_days)
        print(budget)
    finally:
        conn.close()
    for p in problems:
        print("REFUSED:", p)
    if not a.apply or problems:
        print("nothing spent." + ("" if a.apply else " Re-run with --apply."))
        return

    spent = 0
    for day, hrs in schedule.items():
        left = budget.ceiling - spent
        if left < CREDITS_PER_CALL:
            logger.warning(f"ceiling of {budget.ceiling:,} reached at {day}")
            break
        s = run_historical_odds_range("NHL", day, day, hours_utc=hrs, bookmakers=BOOKS,
                                      credit_cap=left, markets=MARKETS)
        spent += s["credits_spent"]
    print(f"spent {spent:,} credits")


if __name__ == "__main__":
    main()

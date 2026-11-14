"""Where the tennis build stands: every collector's progress, read from
Supabase. Read-only.

    python C:/Users/micha/tennis_research/run_with_db.py scripts.tennis_progress
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

WINDOWS = r"C:\Users\micha\tennis_research\coverage_windows.json"
PLAN_CREDITS = 2_292_240
FLOOR = 2_099_550          # mike, 2026-11-13: "lower the floor" (no reserve days)


def main() -> int:
    from data.db import get_connection
    from data.ingestors import tennis_odds_history as toh
    conn = get_connection()
    q = lambda sql, *p: conn.execute(sql, p).fetchone()
    now = datetime.now(timezone.utc)

    # 1. The odds history purchase.
    windows = toh.load_windows(WINDOWS)
    done = partial = 0
    for w in windows:
        last = q("SELECT max(asked_ts) FROM tennis_odds_fetches WHERE source = %s AND sport_key = %s "
                 "AND asked_ts BETWEEN %s AND %s", toh.SOURCE, w["key"], w["start"], w["end"])[0]
        if last is None:
            continue
        if last >= w["end"] - timedelta(hours=1):
            done += 1
        else:
            partial += 1
    calls, spent, left = q("SELECT count(*), coalesce(sum(credits), 0), min(remaining) FROM "
                           "tennis_odds_fetches WHERE source = %s", toh.SOURCE)
    hour = q("SELECT coalesce(sum(credits), 0) FROM tennis_odds_fetches WHERE source = %s "
             "AND asked_at > now() - interval '30 minutes'", toh.SOURCE)[0] * 2
    quotes, matches = q("SELECT count(*), count(DISTINCT event_id) FROM tennis_odds_quotes")
    print("ODDS HISTORY PURCHASE (the 53 top-tier tournaments, 2020 to now)")
    print(f"  tournament windows finished   {done} of {len(windows)}  ({partial} part-way)")
    print(f"  credits spent                 {spent:,} of at most {PLAN_CREDITS:,}")
    print(f"  spending now                  {hour:,} credits an hour")
    print(f"  prices stored                 {quotes:,} on {matches:,} matches")
    print(f"  account balance               {left:,}  (the purchase stops at {FLOOR:,})")
    if hour:
        remaining_plan = max(PLAN_CREDITS - spent, 0)
        print(f"  finish, at this rate          about {remaining_plan / hour:.1f} hours "
              f"(at most; skipped quiet hours make it sooner)")

    # 2. Results at every level.
    first, n_te = q("SELECT min(page_date), count(*) FROM tennis_te_matches")
    days_total = (date.today() - date(2020, 1, 1)).days + 1
    days_done = (date.today() - first).days + 1 if first else 0
    print("\nTENNISEXPLORER BACKFILL (every level's results and one price a match, 2020 on)")
    print(f"  reached back to               {first}  ({days_done:,} of {days_total:,} days, "
          f"{100 * days_done / days_total:.0f}%)")
    print(f"  matches stored                {n_te:,}")

    # 3. The forward logs.
    print("\nFORWARD LOGS (every 20 or 30 minutes from 2026-11-13)")
    p_n, p_last = q("SELECT count(*), max(seen_at) FROM tennis_pinnacle_prices")
    print(f"  Pinnacle, every level         {p_n:,} prices, last pass {p_last:%Y-%m-%d %H:%M} UTC")
    d_n, d_ev, d_last, d_pass = q("SELECT count(*), count(DISTINCT dk_event_id), max(seen_at), "
                                  "count(DISTINCT seen_at) FROM tennis_dk_selections")
    print(f"  DraftKings, every level       {d_n:,} prices on {d_ev:,} matches, {d_pass} passes, "
          f"last {d_last:%Y-%m-%d %H:%M} UTC")
    f_last = q("SELECT max(asked_ts) FROM tennis_odds_fetches WHERE endpoint = 'live'")[0]
    print(f"  odds feed, the active keys    last pass {f_last:%Y-%m-%d %H:%M} UTC")

    # 4. Stored once.
    print("\nSTORED ONCE")
    print(f"  match archive 2000-2026       {q('SELECT count(*) FROM tennis_archive_matches')[0]:,} matches")
    print(f"  ESPN results 2020-2026        {q('SELECT count(*) FROM tennis_espn_matches')[0]:,} matches")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

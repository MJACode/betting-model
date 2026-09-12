"""
Do the bookmakers we never request post NCAAF lines BEFORE DraftKings?

Session 280 (2026-09-10). The live feed asks fourteen books
(config.ODDS_API_BOOKMAKERS_PARAM); on it every book's first NCAAF number
lands a median 5.4-5.9 days out and DK is first or tied on almost every game.
Five US-region books are never requested -- betonlineag, lowvig, mybookieag,
betus, betanysports -- so their posting time has never been observed. One
historical snapshot answers it: 2 markets x 10 credits = 20 credits, approved
by mike 2026-09-10.

DEFINITIONS
- Instant: the Monday before a slate at 12:00Z, before DK's own first
  snapshot for most of that week's games (DK first-priced the 09-05/06 slate
  at 2026-09-01T16:22Z on our feed). Default 2026-08-31.
- Books: the fourteen we request plus the five we never have. The
  `bookmakers` param counts as one region, so the extra names cost nothing.
- Stored, not just printed: every row lands in `odds` with
  source = HISTORICAL_ODDS_SOURCE through the same path run_historical_odds
  uses, so the snapshot is queryable beside everything else.

    python -m scripts.ncaaf_search.book_timing_snapshot --date 2026-08-31 --hour 12
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import config                                                    # noqa: E402
from data.db import get_connection                              # noqa: E402
from data.ingestors import odds_ingestor as oi                   # noqa: E402

NEVER_REQUESTED = ["betonlineag", "lowvig", "mybookieag", "betus", "betanysports"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--date", default="2026-08-31")
    ap.add_argument("--hour", type=int, default=12)
    ap.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    args = ap.parse_args()

    books = list(dict.fromkeys(list(config.ODDS_HISTORY_BOOKMAKERS) + NEVER_REQUESTED))
    markets = ["spreads", "totals"]
    print(f"snapshot {args.date}T{args.hour:02d}:00Z  books {len(books)}  "
          f"markets {markets}  cost {len(markets) * 10} credits")
    events = oi._get_historical_odds(oi.SPORT_KEYS["NCAAF"], markets, args.date,
                                     hour_utc=args.hour, bookmakers=books)
    print(f"events returned: {len(events)}")

    # Per book: how many events carry each market, and how many of those DK lacks.
    per_book = defaultdict(lambda: defaultdict(int))
    dk_has = defaultdict(set)
    for ev in events:
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                per_book[bk["key"]][mk["key"]] += 1
                if bk["key"] == "draftkings":
                    dk_has[mk["key"]].add(ev["id"])
    ahead = defaultdict(lambda: defaultdict(int))
    for ev in events:
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                if ev["id"] not in dk_has[mk["key"]]:
                    ahead[bk["key"]][mk["key"]] += 1

    print(f"\n{'book':16s} {'spreads':>8s} {'totals':>8s} {'spreads_noDK':>13s} {'totals_noDK':>12s}")
    for bk in sorted(per_book, key=lambda b: -per_book[b]["spreads"]):
        flag = "  (never requested)" if bk in NEVER_REQUESTED else ""
        print(f"{bk:16s} {per_book[bk]['spreads']:8d} {per_book[bk]['totals']:8d} "
              f"{ahead[bk]['spreads']:13d} {ahead[bk]['totals']:12d}{flag}")
    for bk in NEVER_REQUESTED:
        if bk not in per_book:
            print(f"{bk:16s} {'-':>8s} {'-':>8s}   not in the response  (never requested)")

    # Kickoff dates covered, so the reader knows which slate this was.
    dates = defaultdict(int)
    for ev in events:
        dates[str(ev.get("commence_time", ""))[:10]] += 1
    print("\nkickoff dates in the snapshot:", dict(sorted(dates.items())))

    if args.dry_run:
        return
    snapshot_at = f"{args.date}T{args.hour:02d}:00:00Z"
    game_rows, odds_rows = oi._process_events(events, "NCAAF", "open", snapshot_at)
    for r in odds_rows:
        r["source"] = oi.HISTORICAL_ODDS_SOURCE
    conn = get_connection()
    try:
        n_games = oi._upsert_games(conn, game_rows)
        n_odds = oi._insert_odds(conn, odds_rows)
        conn.commit()
        print(f"stored: {n_games} games, {n_odds} odds rows (source={oi.HISTORICAL_ODDS_SOURCE})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

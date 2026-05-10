"""
diagnose_f5_odds.py — Standalone diagnostic for MLB F5 markets via The Odds API.

Confirms which F5 market keys (h2h_1st_5_innings, spreads_1st_5_innings,
totals_1st_5_innings) are actually returned by each US bookmaker — including
DraftKings — for today's MLB events. The production ingestor restricts the
per-event call to bookmakers=draftkings, which silently hides whether a market
is missing because DK doesn't carry it or because some other code-side issue.

Usage:
    python -m scripts.diagnose_f5_odds                # all US books, first event
    python -m scripts.diagnose_f5_odds --all-events   # every event today
    python -m scripts.diagnose_f5_odds --book draftkings  # restrict to DK only

Cost: 1 credit per market per region per book per per-event call. With the
default (no bookmaker filter) and us region, expect ~3 markets * N books credits
per event. Use --all-events sparingly.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ODDS_API_BASE, ODDS_API_KEY, ODDS_API_REGIONS

F5_MARKETS = ["h2h_1st_5_innings", "spreads_1st_5_innings", "totals_1st_5_innings"]
SPORT_KEY = "baseball_mlb"


def list_events() -> list[dict]:
    url = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events"
    resp = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_event_odds(event_id: str, book: str | None) -> dict:
    url = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{event_id}/odds"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    ODDS_API_REGIONS,
        "markets":    ",".join(F5_MARKETS),
        "oddsFormat": "american",
    }
    if book:
        params["bookmakers"] = book
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code in (404, 422):
        return {"_error": f"HTTP {resp.status_code}", "_body": resp.text[:500]}
    resp.raise_for_status()
    return resp.json()


def render_event_summary(event: dict) -> None:
    away = event.get("away_team", "?")
    home = event.get("home_team", "?")
    commence = event.get("commence_time", "?")
    print(f"\n=== {away} @ {home}  ({commence})  event_id={event.get('id')}")

    if "_error" in event:
        print(f"   API error: {event['_error']}  body={event.get('_body')}")
        return

    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        print("   (no bookmakers in response)")
        return

    print(f"   {'bookmaker':<22} | {' | '.join(m[:24] for m in F5_MARKETS)}")
    print(f"   {'-' * 22} | {' | '.join('-' * 24 for _ in F5_MARKETS)}")
    for b in sorted(bookmakers, key=lambda x: x.get("key", "")):
        key = b.get("key", "?")
        markets = {m.get("key"): m for m in b.get("markets", [])}
        cells = []
        for mk in F5_MARKETS:
            if mk not in markets:
                cells.append("(missing)".ljust(24))
            else:
                outcomes = markets[mk].get("outcomes", [])
                if mk == "h2h_1st_5_innings":
                    cells.append(("ML " + " / ".join(
                        f"{o.get('name','?')[:4]}={o.get('price','?')}"
                        for o in outcomes
                    ))[:24].ljust(24))
                elif mk == "spreads_1st_5_innings":
                    pts = sorted({o.get("point") for o in outcomes if o.get("point") is not None})
                    cells.append(f"SP pts={pts}"[:24].ljust(24))
                elif mk == "totals_1st_5_innings":
                    pts = sorted({o.get("point") for o in outcomes if o.get("point") is not None})
                    cells.append(f"TO pts={pts}"[:24].ljust(24))
        print(f"   {key:<22} | {' | '.join(cells)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", default=None,
                        help="Restrict to this bookmaker key (e.g. draftkings). "
                             "Default: no filter (all US books).")
    parser.add_argument("--all-events", action="store_true",
                        help="Probe every event today. Default: only the first one.")
    parser.add_argument("--raw", action="store_true",
                        help="Dump the full JSON response for the first event.")
    args = parser.parse_args()

    if not ODDS_API_KEY:
        sys.exit("ODDS_API_KEY not set in env or .env")

    events = list_events()
    print(f"Found {len(events)} upcoming MLB events. region={ODDS_API_REGIONS} "
          f"book_filter={args.book or '(none)'}")

    if not events:
        return

    target = events if args.all_events else events[:1]

    for ev in target:
        ev_id = ev["id"]
        odds = fetch_event_odds(ev_id, args.book)
        odds.setdefault("away_team", ev.get("away_team"))
        odds.setdefault("home_team", ev.get("home_team"))
        odds.setdefault("commence_time", ev.get("commence_time"))
        odds.setdefault("id", ev_id)
        render_event_summary(odds)
        if args.raw:
            print("\n--- RAW JSON ---")
            print(json.dumps(odds, indent=2)[:6000])

    # Per-market roll-up across all probed events
    if args.all_events:
        per_market = {mk: {} for mk in F5_MARKETS}
        for ev in target:
            odds = fetch_event_odds(ev["id"], args.book)
            for b in odds.get("bookmakers", []):
                key = b.get("key", "?")
                returned = {m.get("key") for m in b.get("markets", [])}
                for mk in F5_MARKETS:
                    per_market[mk][key] = per_market[mk].get(key, 0) + (1 if mk in returned else 0)

        print("\n\n=== Per-market coverage across all events ===")
        for mk in F5_MARKETS:
            print(f"\n{mk}:")
            for book, cnt in sorted(per_market[mk].items()):
                print(f"   {book:<22} {cnt}/{len(target)} events")


if __name__ == "__main__":
    main()

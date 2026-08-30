"""
Which MMA markets does The Odds API actually expose for DraftKings?

WHY THIS EXISTS. ufc_method_of_victory has been prob-only since session 49 on
the strength of one claim -- "The Odds API has no method odds" -- that was
never tested. We have only ever REQUESTED h2h (bulk) and totals (per-event)
for MMA, so the absence of method odds in our `odds` table is a consequence of
never asking, not evidence that they don't exist. DraftKings prices method of
victory on its own product, so the open question is purely whether our data
provider exposes it.

This asks the API directly. It costs a handful of credits and settles it.

    export ODDS_API_KEY=...
    python -m scripts.probe_ufc_markets            # next UFC event
    python -m scripts.probe_ufc_markets --all      # every candidate, one by one

The per-event endpoint 422s on an unsupported market key and names it, so
candidates are probed ONE AT A TIME: a single bad key in a combined request
would take the whole call down and make every market look unavailable. That is
the exact failure mode that hid NHL h2h_3way for months (see docs/sports/nhl.md).
"""
from __future__ import annotations
import argparse, os, sys, requests

BASE = "https://api.the-odds-api.com/v4"
SPORT = "mma_mixed_martial_arts"

# Every plausible spelling. The Odds API names markets inconsistently across
# sports, so guessing one and concluding from its absence is not sound.
CANDIDATES = [
    "h2h", "totals", "spreads",
    "method_of_victory", "fight_result_method", "win_method", "method",
    "h2h_3_way", "h2h_3way", "fight_outcome", "outcome_method",
    "to_win_by_ko", "to_win_by_submission", "to_win_by_decision",
    "go_the_distance", "fight_to_go_the_distance", "round_betting",
    "exact_rounds", "winning_round", "total_rounds",
]


def _key() -> str:
    k = os.environ.get("ODDS_API_KEY", "").strip()
    if not k:
        sys.exit("ODDS_API_KEY is not set — run this where the key lives "
                 "(Railway worker shell, or your machine with .env loaded).")
    return k


def next_event(key: str) -> tuple[str, str]:
    r = requests.get(f"{BASE}/sports/{SPORT}/events",
                     params={"apiKey": key}, timeout=20)
    r.raise_for_status()
    events = r.json()
    if not events:
        sys.exit("No upcoming MMA events on the feed.")
    # NOTE: events[0] is whatever the feed lists first, and the MMA feed carries
    # EVERY promotion (see the phantom-event filter in odds_ingestor) — the
    # 2026-08-28 run landed on a regional card for which DK listed nothing at
    # all, making every "DK lists no line" row uninformative. The 422 results
    # are unaffected (they reject the key name, not the event), but pass
    # --event-id for a real UFC card when the "no line" rows matter.
    e = events[0]
    print(f"event: {e['away_team']} vs {e['home_team']}  ({e['commence_time']})")
    print(f"remaining credits: {r.headers.get('x-requests-remaining')}\n")
    return e["id"], e["commence_time"]


def probe(key: str, event_id: str, markets: list[str]) -> None:
    found: list[tuple[str, list[str]]] = []
    for m in markets:
        r = requests.get(
            f"{BASE}/sports/{SPORT}/events/{event_id}/odds",
            params={"apiKey": key, "regions": "us", "markets": m,
                    "oddsFormat": "american", "bookmakers": "draftkings"},
            timeout=20)
        if r.status_code == 422:
            print(f"  {m:28} unsupported market key (422)")
            continue
        if r.status_code != 200:
            print(f"  {m:28} HTTP {r.status_code}: {r.text[:120]}")
            continue
        books = r.json().get("bookmakers", [])
        dk = next((b for b in books if b["key"] == "draftkings"), None)
        if not dk or not dk.get("markets"):
            print(f"  {m:28} valid key, but DK lists no line for this event")
            continue
        for mk in dk["markets"]:
            names = [o.get("name") or o.get("description") for o in mk.get("outcomes", [])]
            print(f"  {m:28} DK PRICES IT -> {mk['key']}: {names[:6]}")
            found.append((mk["key"], names))

    print()
    if found:
        print("RESULT: DraftKings prices these via The Odds API:")
        for k, names in found:
            print(f"  - {k}  ({len(names)} outcomes)")
        print("\nNext step: add the confirmed key to UFC_EVENT_MARKETS in\n"
              "data/ingestors/odds_ingestor.py, teach _parse_outcomes its\n"
              "outcome names, and ufc_method_of_victory starts pricing against\n"
              "a real market instead of a 1/3 prior.")
    else:
        print("RESULT: no method/round market returned a DK line for this event.\n"
              "That is evidence, but not proof — re-run closer to the card, since\n"
              "DK posts derivative markets later than the moneyline.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="probe every candidate (default: skip h2h/totals, already known)")
    ap.add_argument("--event-id", help="probe a specific event id")
    a = ap.parse_args()
    key = _key()
    eid = a.event_id or next_event(key)[0]
    markets = CANDIDATES if a.all else [m for m in CANDIDATES if m not in ("h2h", "totals", "spreads")]
    print(f"probing {len(markets)} market key(s) against DraftKings:\n")
    probe(key, eid, markets)


if __name__ == "__main__":
    main()

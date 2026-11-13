"""Measure what the odds feed serves for MMA: market keys per event, books, and
history depth. PAID: each call prints its x-requests-last (measured 2026-11-13:
2 credits a market live, 20 a market in history, two regions). Run with
ODDS_API_KEY in the environment. Writes nothing.

    python feed_probe.py events | markets <event id> | history <iso time> ...
"""
import os, sys, json, requests
from pathlib import Path

# Every Odds API call is logged to api_call_log however the process started
# (tests/test_odds_call_log_everywhere.py); config installs the logger on import.
sys.path.append(str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402,F401

BASE = "https://api.the-odds-api.com/v4"
SPORT = "mma_mixed_martial_arts"
BOOKS = ("draftkings,fanduel,betmgm,williamhill_us,betrivers,hardrockbet,"
         "fliff,ballybet,betparx,pinnacle,bovada,rebet")
CANDIDATES = [
    "h2h", "totals", "spreads", "alternate_totals", "h2h_lay",
    "method_of_victory", "fight_result_method", "win_method", "method",
    "h2h_3_way", "fight_outcome", "to_win_by_ko", "to_win_by_submission",
    "to_win_by_decision", "go_the_distance", "fight_to_go_the_distance",
    "round_betting", "exact_rounds", "winning_round", "total_rounds",
    "fight_goes_distance", "draw_no_bet",
]


def get(path, **params):
    params["apiKey"] = os.environ["ODDS_API_KEY"]
    r = requests.get(f"{BASE}{path}", params=params, timeout=30)
    return r, r.headers.get("x-requests-last"), r.headers.get("x-requests-remaining")


def main():
    mode = sys.argv[1]
    if mode == "events":
        r, last, rem = get(f"/sports/{SPORT}/events")
        ev = r.json()
        print("bill", last, "remaining", rem, "events", len(ev))
        for e in ev[:60]:
            print(e["id"], e["commence_time"], e["away_team"], "|", e["home_team"])
    elif mode == "markets":
        eid = sys.argv[2]
        for m in CANDIDATES:
            r, last, rem = get(f"/sports/{SPORT}/events/{eid}/odds", regions="us,eu",
                               markets=m, oddsFormat="american", bookmakers=BOOKS)
            if r.status_code != 200:
                print(f"{m:26} HTTP {r.status_code} bill={last} {r.text[:90]}")
                continue
            bks = r.json().get("bookmakers", [])
            got = {b["key"]: [mk["key"] for mk in b["markets"]] for b in bks if b.get("markets")}
            print(f"{m:26} 200 bill={last} books={sorted(got)}")
            if got and m not in ("h2h",):
                b0 = next(b for b in bks if b.get("markets"))
                print("    sample", b0["key"], json.dumps(b0["markets"][0]["outcomes"][:6]))
        print("remaining", rem)
    elif mode == "history":
        for date in sys.argv[2:]:
            r, last, rem = get(f"/historical/sports/{SPORT}/odds", regions="us,eu",
                               markets="h2h", oddsFormat="american", date=date,
                               bookmakers=BOOKS)
            if r.status_code != 200:
                print(date, "HTTP", r.status_code, "bill", last, r.text[:120]); continue
            j = r.json()
            data = j.get("data", [])
            books = sorted({b["key"] for e in data for b in e.get("bookmakers", [])})
            print(date, "bill", last, "snapshot", j.get("timestamp"), "prev", j.get("previous_timestamp"),
                  "next", j.get("next_timestamp"), "events", len(data), "books", books)
        print("remaining", rem)
    elif mode == "hist_event":
        # per-event history for a market list: sys.argv[2]=event id, [3]=date, [4]=markets
        eid, date, mkts = sys.argv[2], sys.argv[3], sys.argv[4]
        for m in mkts.split(","):
            r, last, rem = get(f"/historical/sports/{SPORT}/events/{eid}/odds", regions="us,eu",
                               markets=m, oddsFormat="american", date=date, bookmakers=BOOKS)
            if r.status_code != 200:
                print(m, "HTTP", r.status_code, "bill", last, r.text[:120]); continue
            d = r.json().get("data", {})
            got = {b["key"]: [mk["key"] for mk in b["markets"]] for b in d.get("bookmakers", []) if b.get("markets")}
            print(m, "bill", last, "books", sorted(got))
        print("remaining", rem)


if __name__ == "__main__":
    main()

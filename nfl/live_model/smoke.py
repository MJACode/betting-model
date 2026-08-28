"""
End to end smoke test of the live pipe, run days before it matters.

WHAT THIS PROVES, and what it cannot. It proves the plumbing: ESPN answers and
parses, the Odds API answers and its payload parses into Quotes, the lane
prices a quote, and the recorder persists a decision and reads it back. It
proves NONE of the edge, because there is no live game to price.

That distinction is the reason to run it in August. The plumbing failures worth
catching are the silent ones: a renamed ESPN field, a market key the book
stopped posting, a decision log written somewhere the next redeploy wipes. Each
is cheap to find now and expensive to find at kickoff.

    python -m live_model.smoke            # ~2 credits
    python -m live_model.smoke --no-odds  # free, ESPN and recorder only
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from .feeds import espn
from .feeds.odds_live import CreditMeter, LiveOddsClient
from .models import pass_attempt_bias as pab
from .recorder import JsonlRecorder

LANE_MARKET = pab.MARKET


def _ok(label: str, detail: str = "") -> bool:
    print(f"  PASS  {label}" + (f"  {detail}" if detail else ""))
    return True


def _fail(label: str, detail: str = "") -> bool:
    print(f"  FAIL  {label}" + (f"  {detail}" if detail else ""))
    return False


# ESPN hosts, in the order live_events tries them. site.api has 403d the
# Railway worker before, which is why the core host is preferred.
ESPN_PROBES = (
    ("sports.core",
     "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events?limit=1"),
    ("site.api",
     "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"),
)


def check_espn() -> bool:
    """
    Prove the feed ANSWERS, not merely that the helper returned a list.

    live_events swallows a transport failure and returns an empty list, which
    is indistinguishable from "no game is on right now". In August those look
    identical and the test passes on a completely dead feed. It has to probe
    the hosts itself.
    """
    print("ESPN")
    import requests

    reachable = []
    for name, url in ESPN_PROBES:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and isinstance(r.json(), dict):
                reachable.append(name)
                _ok(f"{name} reachable")
            else:
                _fail(f"{name} reachable", f"HTTP {r.status_code}")
        except Exception as e:                          # noqa: BLE001
            _fail(f"{name} reachable", type(e).__name__)
    if not reachable:
        return _fail("ESPN", "NEITHER host answered; the state feed is dead")

    try:
        events, host = espn.live_events()
    except Exception as e:                              # noqa: BLE001
        return _fail("live_events", repr(e))
    _ok("live_events", f"host={host}, {len(events)} live event(s)")
    if not events:
        print("        No live NFL game right now, which is expected in August.")
        print("        The state parser is covered by the test suite instead.")
    return True


def check_odds(client: LiveOddsClient) -> bool:
    print("Odds API")
    try:
        # The anchor is the cheapest call that proves auth, and the worker
        # needs it regardless: no anchor means no state, so no prop decision.
        anchor = client.fetch_anchor()
    except Exception as e:                              # noqa: BLE001
        return _fail("fetch_anchor", repr(e))
    _ok("fetch_anchor", f"{len(anchor)} quote(s)")
    if not anchor:
        return _fail("fetch_anchor", "no quotes; is the season on the board?")

    games = sorted({q.game_id for q in anchor})
    print(f"        {len(games)} game(s) on the board")
    spreads = [q for q in anchor if q.market == "spreads" and q.line is not None]
    totals = [q for q in anchor if q.market == "totals" and q.line is not None]
    if not spreads or not totals:
        return _fail("anchor shape",
                     "state needs BOTH a spread and a total; one is missing")
    _ok("anchor shape", f"{len(spreads)} spread, {len(totals)} total quote(s)")

    eid = games[0]
    try:
        quotes = client.fetch_event_markets(eid, (LANE_MARKET,))
    except Exception as e:                              # noqa: BLE001
        return _fail("fetch_event_markets", repr(e))
    lane = [q for q in quotes if q.market == LANE_MARKET]
    _ok("fetch_event_markets", f"{len(quotes)} quote(s), {len(lane)} on the lane")
    if not lane:
        print(f"        {LANE_MARKET} not posted for {eid} yet. Pregame prop")
        print("        boards fill in closer to kickoff; not a failure.")
    else:
        q = lane[0]
        print(f"        sample: {q.player} {q.side} {q.line} @ {q.price} "
              f"({q.bookmaker})")
    return True


def check_lane_and_recorder() -> bool:
    print("Lane and recorder")
    read = pab.over_prob(32.5, 17.0, 1800)
    if read.over_prob is None:
        return _fail("lane prices a mid game quote", read.reason)
    _ok("lane prices a mid game quote", f"p={read.over_prob:.4f}")
    if pab.over_prob(32.5, 30.0, 60).over_prob is not None:
        return _fail("lane refuses the end of the game")
    _ok("lane refuses the end of the game")

    rec = JsonlRecorder(day="smoke")

    class _D:
        def to_row(self):
            return {"ts": datetime.now(timezone.utc).isoformat(),
                    "game_id": "smoke", "bet": False, "reason": "smoke_test",
                    "context": {"arm": "priced"}}

    before = len(rec.read_back())
    rec(_D())
    after = rec.read_back()
    if len(after) != before + 1:
        return _fail("recorder round trip", f"{before} -> {len(after)}")
    _ok("recorder round trip", str(rec.path))
    # The log must sit on the mounted volume or a redeploy eats the slate.
    print(f"        writing to {rec.path.parent}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-odds", action="store_true",
                    help="skip the paid calls; ESPN and recorder only")
    args = ap.parse_args()

    print(f"live pipe smoke test  {datetime.now(timezone.utc).isoformat()}\n")
    results = [check_espn(), check_lane_and_recorder()]

    if not args.no_odds:
        key = os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
        if not key:
            results.append(_fail("Odds API", "no key in the environment"))
        else:
            meter = CreditMeter()
            results.append(check_odds(LiveOddsClient(key, meter)))
            print(f"\nspent {getattr(meter, 'spent', 0)} credit(s)")

    print()
    if all(results):
        print("PIPE OK")
    else:
        print("PIPE BROKEN — see the FAIL lines above")
        sys.exit(1)


if __name__ == "__main__":
    main()

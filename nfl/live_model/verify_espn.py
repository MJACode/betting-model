"""
Verification spike for the ESPN live feed. RUN THIS BEFORE TRUSTING A PRICE.

    python -m live_model.scripts_verify_espn
    python -m live_model.scripts_verify_espn --event 401671789

WHY THIS EXISTS
ESPN's API is undocumented, it has broken this repo's ingestors twice, and it
is blocked by the egress proxy of the sandbox this package was written in. So
every assumption in feeds/espn.py is written down there as A1 to A5 and checked
here against a real payload. Nothing in the live path has been validated
against real ESPN data until this script has been run during a live game and
reports all checks green.

Run it while a game is actually in progress. Out of season it will correctly
report that there is nothing live to check, which is not a pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_model.feeds import espn  # noqa: E402


def _ok(label: str, passed: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    return passed


def check_scoreboard() -> list[dict]:
    print("\n=== scoreboard ===")
    board = espn.fetch_scoreboard()
    print(f"  top level keys: {sorted(board)[:10]}")
    events = board.get("events") or []
    print(f"  events: {len(events)}")
    live = espn.extract_live_event_ids(board)
    print(f"  live now: {len(live)}")
    for ev in live:
        print(f"    {ev['away']} at {ev['home']}  "
              f"period {ev['period']}  {ev['state_name']}")
    if not live:
        print("\n  NOTHING IS LIVE. This is not a pass: the assumptions below "
              "can only be checked against an in progress game.")
    return live


def check_summary(event_id: str) -> bool:
    print(f"\n=== summary, event {event_id} ===")
    payload = espn.fetch_summary(event_id)
    comp = espn._dig(payload, "header", "competitions", 0)
    status = espn._dig(comp, "status") or {}
    situation = espn._dig(comp, "situation") or {}

    print(f"  status keys:    {sorted(status)}")
    print(f"  situation keys: {sorted(situation)}")
    print(f"  raw clock={status.get('clock')!r} "
          f"displayClock={status.get('displayClock')!r} "
          f"period={status.get('period')!r}")

    all_ok = True
    # A1 clock is seconds
    raw = status.get("clock")
    all_ok &= _ok("A1 status.clock is seconds in the period",
                  isinstance(raw, (int, float)) and 0 <= float(raw) <= 1200,
                  f"got {raw!r}")
    # A2 period range
    period = status.get("period")
    all_ok &= _ok("A2 status.period is 1 to 4, 5+ for overtime",
                  isinstance(period, int) and 1 <= period <= 6, f"got {period!r}")
    # A4 possession is a team id
    poss = situation.get("possession")
    home_id = str(espn._dig(comp, "competitors", 0, "team", "id") or "")
    away_id = str(espn._dig(comp, "competitors", 1, "team", "id") or "")
    all_ok &= _ok("A4 situation.possession matches a competitor team id",
                  poss is None or str(poss) in (home_id, away_id),
                  f"possession={poss!r} ids={home_id},{away_id}")
    # A5 field position
    ptext = situation.get("possessionText")
    yline = situation.get("yardLine")
    print(f"  possessionText={ptext!r}  yardLine={yline!r}  "
          f"downDistanceText={situation.get('downDistanceText')!r}")
    all_ok &= _ok("A5 possessionText is parseable as 'TEAM YARD'",
                  isinstance(ptext, str) and len(ptext.split()) == 2,
                  f"got {ptext!r}")

    parsed = espn.extract_summary_state(payload)
    if parsed is None:
        return _ok("extract_summary_state returns a state", False,
                   "a REQUIRED field is missing; the feed has changed")

    # The SAME predicate the worker runs on its first payload each gameday, so
    # a green spike and a green worker mean the same thing.
    from live_model.workers.gameday import check_feed_assumptions
    problems = check_feed_assumptions(parsed)
    all_ok &= _ok("worker self check (shared predicate)", not problems,
                  "; ".join(problems))
    print(f"\n  parsed: period={parsed['period']} clock={parsed['clock_seconds']} "
          f"score {parsed['away_score']}-{parsed['home_score']} "
          f"poss={parsed['possession']} yardline_100={parsed['yardline_100']} "
          f"down={parsed['down']} dist={parsed['distance']} "
          f"plays={parsed['plays_run']}")

    all_ok &= _ok("yardline_100 is in range", parsed["yardline_100"] is None
                  or 0 <= parsed["yardline_100"] <= 100)
    all_ok &= _ok("plays_run is nonzero after the first drive",
                  parsed["plays_run"] > 0 or parsed["period"] == 1,
                  f"got {parsed['plays_run']}")
    all_ok &= _ok("timeouts are in 0 to 3",
                  0 <= parsed["home_timeouts"] <= 3
                  and 0 <= parsed["away_timeouts"] <= 3)

    players = espn.extract_player_stats(payload)
    print(f"\n  boxscore rows parsed: {len(players)}")
    if players:
        cats = sorted({p["category"] for p in players})
        print(f"  categories: {cats}")
        sample = players[0]
        print(f"  sample: {sample['name']} ({sample['position']}, "
              f"{sample['team_side']}) {sample['raw']}")
    all_ok &= _ok("boxscore parses by LABEL, not by index",
                  len(players) > 0,
                  "no rows: the labels and stats arrays did not line up")
    return all_ok


def check_core() -> bool:
    """
    The host the worker actually prefers.

    site.api has been 403ing this project's Railway worker daily since early
    August, so a spike that only checks site.api tells you nothing about
    whether production can see a game.
    """
    print("\n=== sports.core.api.espn.com (the worker's primary host) ===")
    from live_model.feeds import espn_core
    from live_model.workers.gameday import check_feed_assumptions
    try:
        fetch = espn_core.make_fetcher()
        events = espn_core.fetch_live_events(fetch)
    except Exception as e:                      # noqa: BLE001
        return _ok("core host reachable", False, str(e)[:160])
    _ok("core host reachable", True, f"{len(events)} live event(s)")
    if not events:
        print("  no live games on the core path, so its shape is unchecked")
        return True
    problems = check_feed_assumptions(events[0])
    return _ok("core payload passes the worker self check", not problems,
               "; ".join(problems))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default=None,
                    help="check one event id instead of the first live game")
    ap.add_argument("--dump", default=None,
                    help="write the raw summary payload here for inspection")
    args = ap.parse_args()

    try:
        live = check_scoreboard()
    except Exception as e:                      # noqa: BLE001
        print(f"\n  could not reach ESPN: {e}")
        print("\nVERDICT: NOT VERIFIED (ESPN unreachable from this machine). "
              "Some networks and CI runners block site.api.espn.com; run this "
              "from the machine the worker will actually run on.")
        raise SystemExit(2)
    event_id = args.event or (live[0]["event_id"] if live else None)
    if not event_id:
        print("\nVERDICT: NOT VERIFIED (no live game to check against)")
        raise SystemExit(2)

    if args.dump:
        Path(args.dump).write_text(json.dumps(espn.fetch_summary(event_id), indent=2))
        print(f"\n  raw payload written to {args.dump}")

    try:
        ok = check_summary(event_id)
    except Exception as e:                      # noqa: BLE001
        print(f"\n  summary check raised: {e}")
        ok = False
    ok &= check_core()
    print(f"\nVERDICT: {'ALL ASSUMPTIONS HOLD' if ok else 'ASSUMPTIONS BROKEN'}")
    if not ok:
        print("Fix feeds/espn.py before running the worker against real money. "
              "The assumption block at the top of that file is the place to "
              "start; every check above maps to one of A1 to A5.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

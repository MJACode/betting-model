#!/usr/bin/env python3
"""
Offline self-test for the wind poller.

The poller is the one component here that spends credits and tells you to put
money down, so its gating and its fire-once behaviour need a test that does not
depend on the live board. This drives `wind_poller.tick` against a synthetic
schedule and a synthetic odds feed, in its own scratch state directory.

    python scripts/selftest_poller.py

Zero credits, zero network. Exits non-zero on the first failed assertion.

Scenarios
  1. no Pinnacle quote            -> holds fire, reports the game as waiting
  2. Pinnacle appears, qualifying -> fires exactly once, writes the bet
  3. same board again             -> does not re-fire
  4. lead beyond the calibration  -> qualifies but is sized at zero, no fire
  5. thin wind                    -> no odds call at all
  6. cadence                      -> 60 min far out, 10 min inside 3 hours
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wind_poller as wp

FAILS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


class Args:
    days = 10
    threshold = 11.0
    buffer = 3.0
    regions = "us,eu"
    min_edge = 0.03
    min_edge_vs_pinnacle = None
    bankroll = 10_000.0
    require_pinnacle = True
    once = True
    dry_run = False
    max_credits = 1500
    quota_guard = 200
    notify_cmd = None


def board(now, specs) -> pd.DataFrame:
    """specs: (game_id, hours_to_kick, wind, best_total, under_px, over_px, pin)"""
    rows = []
    for gid, hrs, wind, total, upx, opx, pin in specs:
        kick = now + pd.Timedelta(hours=hrs)
        rows.append(dict(
            game_id=gid, matchup=f"{gid}_AWAY @ {gid}_HOME", kick_utc=kick,
            home_team=f"{gid}H", away_team=f"{gid}A", stadium_id="BUF00",
            roof="outdoors", lead_days=hrs / 24, forecast_wind=wind,
            exp_true_wind=wind - 1.5, best_book="draftkings", best_total=total,
            best_under_px=upx, best_over_px=opx, n_books=8,
            pin_total=total if pin else pd.NA,
            pin_under_px=upx if pin else pd.NA,
            pin_over_px=opx if pin else pd.NA,
            pin_prob=0.5 if pin else pd.NA,
        ))
    return pd.DataFrame(rows)


def install(now, specs, cost=2):
    """Patch the poller's three outward-facing calls with fixtures."""
    b = board(now, specs)
    wp.load_schedule = lambda days: b.drop(columns=[c for c in b.columns if c.startswith(
        ("best_", "pin_", "n_books", "forecast_wind", "exp_true_wind"))])
    wp.attach_forecast = lambda g, days=9: b[b.game_id.isin(g.game_id)].drop(
        columns=["best_book", "best_total", "best_under_px", "best_over_px",
                 "n_books", "pin_total", "pin_under_px", "pin_over_px", "pin_prob"])
    wp.attach_odds = lambda g, regions, quota_guard: (
        b[b.game_id.isin(g.game_id)].copy(), cost)
    return b


def main() -> int:
    now = pd.Timestamp.now(tz="UTC")
    tmp = Path(tempfile.mkdtemp(prefix="poller_selftest_"))
    wp.CARDS = tmp
    wp.STATE_PATH = tmp / "poll_state.json"
    wp.FIRED_PATH = tmp / "fired_bets.csv"
    wp.LOG_PATH = tmp / "poll_log.csv"

    a = Args()
    state = {"fired": {}, "first_pinnacle": {}, "ticks": 0, "credits": 0}

    try:
        print("\n1. Pinnacle not up yet")
        install(now, [("G1", 60, 15.0, 41.5, -110, -110, False)])
        wp.tick(a, state)
        check("no fire without pinnacle", not state["fired"])
        check("nothing written", not wp.FIRED_PATH.exists())

        print("\n2. Pinnacle appears on a qualifying game")
        install(now, [("G1", 60, 15.0, 41.5, -110, -110, True)])
        wp.tick(a, state)
        check("fired once", list(state["fired"]) == ["G1"], str(list(state["fired"])))
        check("bet row written", wp.FIRED_PATH.exists())
        if wp.FIRED_PATH.exists():
            f = pd.read_csv(wp.FIRED_PATH)
            check("one row", len(f) == 1)
            check("sized above zero", f.units.iloc[0] > 0, f"{f.units.iloc[0]} units")
            check("stake is units x unit_pct",
                  abs(f.stake_pct.iloc[0] - f.units.iloc[0] * wp.UNIT_PCT * 100) < 1e-6)
            check("pinnacle recorded", pd.notna(f.pin_total.iloc[0]))

        print("\n3. same board again")
        install(now, [("G1", 60, 15.0, 41.5, -110, -110, True)])
        wp.tick(a, state)
        f = pd.read_csv(wp.FIRED_PATH)
        check("no second fire", len(f) == 1, f"{len(f)} rows")

        print("\n4. lead past the calibrated range")
        state2 = {"fired": {}, "first_pinnacle": {}, "ticks": 0, "credits": 0}
        install(now, [("G2", 24 * 9, 16.0, 41.5, -110, -110, True)])
        wp.tick(a, state2)
        check("uncalibrated lead not fired", not state2["fired"])

        print("\n5. wind well under the threshold")
        state3 = {"fired": {}, "first_pinnacle": {}, "ticks": 0, "credits": 0}
        install(now, [("G3", 48, 6.0, 41.5, -110, -110, True)])
        wp.tick(a, state3)
        check("no odds call on a thin board", state3["credits"] == 0,
              f"{state3['credits']} credits")

        print("\n6. cadence")
        far = board(now, [("A", 60, 15.0, 41.5, -110, -110, True)])
        near = board(now, [("B", 2, 15.0, 41.5, -110, -110, True)])
        edge = board(now, [("C", 3.5, 15.0, 41.5, -110, -110, True)])
        w_far, _ = wp.next_wait(far, now)
        w_near, _ = wp.next_wait(near, now)
        w_edge, _ = wp.next_wait(edge, now)
        check("60 min far out", w_far == wp.SLOW_SECONDS, f"{w_far}s")
        check("10 min inside 3h", w_near == wp.FAST_SECONDS, f"{w_near}s")
        check("wakes at the 3h boundary", 1700 <= w_edge <= 1900, f"{w_edge}s")
        check("never oversleeps the boundary", w_edge <= 0.5 * 3600 + 1)

        print("\n7. pinnacle gate can be turned off")
        a2 = Args()
        a2.require_pinnacle = False
        state4 = {"fired": {}, "first_pinnacle": {}, "ticks": 0, "credits": 0}
        install(now, [("G4", 60, 15.0, 41.5, -110, -110, False)])
        wp.tick(a2, state4)
        check("fires without pinnacle when told to", list(state4["fired"]) == ["G4"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'ALL PASS' if not FAILS else 'FAILED: ' + ', '.join(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())

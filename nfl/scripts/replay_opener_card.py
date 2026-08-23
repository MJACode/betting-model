#!/usr/bin/env python3
"""
Replay the opener card against a completed week, from the cached snapshots.

    python scripts/replay_opener_card.py --season 2025 --week 1
    python scripts/replay_opener_card.py --season 2025 --week 1 --settle

The wind model has had `replay_wind_card.py` since the start; the opener never
had an equivalent, so "what would this actually have picked" could only be
answered by rebuilding the walk by hand. This does it properly.

WHAT IT DOES
------------
Walks the cached spread snapshots forward through the validated T-7..T-2 window
in real time order and fires each game at the FIRST moment it qualifies, which
is exactly what the live poller does. It calls the production selection
function (`models/opener_spread.select_opener_bets`) rather than a copy, so a
change to the rule shows up here immediately.

Costs zero Odds API credits: everything comes from data/odds_cache/.

WHAT IT IS NOT
--------------
Not a backtest. `scripts/backtest_opener.py` is the backtest, with the placebo
and the confidence intervals. This shows one week's card as it would have been
printed, which is the thing worth eyeballing before trusting the live path.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import sys

import pandas as pd
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from data_ingest.parse import snapshot_to_frame


def _load_model():
    """Load by path — the platform's `models` package shadows nfl/models."""
    spec = importlib.util.spec_from_file_location(
        "nfl_model_opener_spread", os.path.join(PKG, "models", "opener_spread.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def week_schedule(season: int, week: int) -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    g = g[(g.season == season) & (g.week == week)].copy()
    if g.empty:
        raise SystemExit(f"no games for {season} week {week} in data/games.csv")
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    g["matchup"] = g.away_team + " @ " + g.home_team
    return g


def cached_snapshots(lo: pd.Timestamp, hi: pd.Timestamp) -> list:
    out = []
    for f in glob.glob("data/odds_cache/*.json"):
        try:
            d = json.load(open(f))
        except (json.JSONDecodeError, OSError):
            continue
        t = d.get("timestamp")
        if not t:
            continue
        ts = pd.Timestamp(t)
        if not (lo <= ts <= hi):
            continue
        has_spreads = any(
            m.get("key") == "spreads"
            for ev in (d.get("data") or [])
            for b in (ev.get("bookmakers") or [])
            for m in (b.get("markets") or []))
        if has_spreads:
            out.append((ts, d))
    out.sort(key=lambda x: x[0])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--settle", action="store_true", help="grade against the result")
    a = ap.parse_args()

    op = _load_model()
    threshold = a.threshold if a.threshold is not None else op.DEPLOY_THRESHOLD

    g = week_schedule(a.season, a.week)
    first_kick = g.kick_utc.min()
    lo = first_kick - pd.Timedelta(days=op.LEAD_HI_DAYS)
    hi = first_kick - pd.Timedelta(days=op.LEAD_LO_DAYS)
    snaps = cached_snapshots(lo, hi)

    print(f"--- {a.season} week {a.week}: {len(g)} games, "
          f"first kickoff {first_kick:%Y-%m-%d %H:%MZ} ---")
    print(f"{len(snaps)} cached spread snapshot(s) in T-{op.LEAD_HI_DAYS:.0f}"
          f"..T-{op.LEAD_LO_DAYS:.0f} ({lo:%m-%d %HZ} -> {hi:%m-%d %HZ})")
    if not snaps:
        print("nothing cached in the window — cannot replay this week")
        return 0

    fired: dict[str, dict] = {}
    for ts, payload in snaps:
        sched = g.copy()
        sched["lead_days"] = (sched.kick_utc - ts).dt.total_seconds() / 86400
        sched = sched[sched.lead_days.between(op.LEAD_LO_DAYS, op.LEAD_HI_DAYS)]
        if sched.empty:
            continue
        bets = op.select_opener_bets(snapshot_to_frame(payload, str(ts)), sched,
                                     threshold=threshold)
        if bets is None or bets.empty:
            continue
        for _, b in bets.iterrows():
            # FIRST qualifying moment only — a later snapshot never re-prices.
            if b.game_id not in fired:
                fired[b.game_id] = dict(b, fired_at=ts)

    if not fired:
        print(f"\nNo qualifying opener bets at |dev| >= {threshold}.")
        return 0

    out = pd.DataFrame(fired.values()).sort_values("fired_at")
    print(f"\n=== OPENER CARD  {a.season} week {a.week} "
          f"(first qualifying moment per game) ===")
    cols = ["matchup", "fired_at", "lead_days", "bet_team", "side_line", "book",
            "price", "dev", "pin_home_line", "model_prob", "edge_pp", "edge_tier"]
    print(out[cols].to_string(index=False))
    tiers = out.edge_tier.value_counts().to_dict()
    print("edge size: " + ", ".join(f"{tiers.get(t, 0)} {t}"
                                    for _, t in op.EDGE_TIERS))

    if a.settle:
        res = g.set_index("game_id")[["result"]]
        s = out.join(res, on="game_id")
        # scored_line convention: the pick's own side line, home-relative margin.
        cover = s.result + s.side_line
        s["graded"] = ["WIN" if c > 0 else ("PUSH" if c == 0 else "LOSS") for c in cover]
        s["pnl"] = [
            (p / 100 if p > 0 else 100 / -p) if gr == "WIN" else (0.0 if gr == "PUSH" else -1.0)
            for p, gr in zip(s.price, s.graded)]
        print("\n=== settled ===")
        print(s[["matchup", "bet_team", "side_line", "price", "result",
                 "graded", "pnl"]].to_string(index=False))
        w = (s.graded == "WIN").sum()
        l = (s.graded == "LOSS").sum()
        print(f"\nweek total: {s.pnl.sum():+.2f} units flat on {len(s)} bet(s) ({w}-{l})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

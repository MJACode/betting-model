#!/usr/bin/env python3
"""
Daily opener-spread bet card — the LIVE deployment of `models/opener_spread.py`.

This module is plumbing: fetch the board, hand it to the model, print the card
and write the CSV the platform publisher reads. THE RULE, the evidence, the
per-bet win probability and the selection all live in `models/opener_spread.py`
— change them there, not here.

    python scripts/daily_opener_card.py            # scan the T-2..T-7 window
    python scripts/daily_opener_card.py --threshold 1.5

Cost: 2 credits per run (regions=us,eu x markets=spreads — eu is required,
that's where Pinnacle lives). Zero cost when no games are in the window.
Output: printed card + data/cards/opener_card_YYYY-MM-DD.csv.

EVIDENCE, RESTATED 2026-08-23 ON SIX SEASONS
--------------------------------------------
A 27,300-credit scan added 2020-2022 at the same 6-hourly resolution the
2023-2025 result was built on. The edge did not survive it:

  |dev| >= 1.0 : n=1,178, ATS 56.88% vs 54.60% expected from the number bought,
  +2.27pp excess [95% CI -0.6, +5.1]; ROI +1.34% [-3.9, +6.4]. Both span zero.
  Season ROI 2020..2025: -2.62 / -1.78 / -2.80 / +4.72 / +10.86 / +0.32. The
  three seasons added are all negative and the profit is nearly all 2024. The
  DraftKings placebo returns +0.95pp against the model's +2.27pp.

  Previously published as +6.82% on 2023-2025 alone. Two corrections rather
  than new information: backtest_opener had never excluded EXCHANGES though
  this card always has (that alone takes 2023-2025 to +5.37%), plus three
  worse seasons.

LIVE by explicit decision (2026-08-23), and sized to survive being wrong: the
six-season probabilities are ~2.8pp below the three-season table, and the
publisher stakes Kelly-proportionally per bet rather than 1u flat. Over
2020-2025 that is +5.45% on units staked against +1.28% flat, because 89% of
picks carry ~+1.6pp of edge and return -0.30% while the rare big deviations
carry +3.7 to +11pp. A quote whose juice has eaten the edge is staked at ZERO.

Retire it on a 2026 season at or below flat.

Each pick carries `edge_pp` and an `edge_tier` of SMALL / MEDIUM / LARGE, so
the size of the predicted edge is visible rather than implied. The tier moves
with the juice as well as the deviation, which is the useful part: a 2-point
deviation at -140 is a smaller edge than a 1-pointer at -110.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_nfl_model(name: str):
    """
    Import a sibling module from nfl/models/ by absolute path.

    A bare `from models.opener_spread import ...` is NOT safe here. The
    platform repo has its own top-level `models` package with an __init__.py,
    so whenever both roots are on sys.path — running from the repo root, or
    under pytest — that package wins and this one becomes invisible; the import
    does not fall back, it raises. Loading by path is unambiguous regardless of
    sys.path order, and is what tests/test_nfl_opener.py already does.
    """
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "models" / f"{name}.py"
    mod_name = f"nfl_model_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: a module using @dataclass under
    # `from __future__ import annotations` resolves annotations through
    # sys.modules[cls.__module__] and raises without this.
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


opener_spread = _load_nfl_model("opener_spread")

# Re-exported so this module stays the single entry point for callers and
# tests. The definitions live in models/opener_spread.py.
american_to_prob = opener_spread.american_to_prob
model_prob_for_dev = opener_spread.model_prob_for_dev
edge_tier = opener_spread.edge_tier
select_opener_bets = opener_spread.select_opener_bets

DEFECTIVE_BOOKS = opener_spread.DEFECTIVE_BOOKS
EXCHANGES = opener_spread.EXCHANGES
REFERENCE = opener_spread.REFERENCE
DEPLOY_THRESHOLD = opener_spread.DEPLOY_THRESHOLD
LEAD_LO_DAYS = opener_spread.LEAD_LO_DAYS
LEAD_HI_DAYS = opener_spread.LEAD_HI_DAYS
POOLED_MODEL_PROB = opener_spread.POOLED_MODEL_PROB
DEV_WIN_PROB = opener_spread.DEV_WIN_PROB
EDGE_TIERS = opener_spread.EDGE_TIERS


def load_window_schedule(lo_days: float = LEAD_LO_DAYS,
                         hi_days: float = LEAD_HI_DAYS) -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    now = pd.Timestamp.now(tz="UTC")
    g = g[(g.kick_utc > now + pd.Timedelta(days=lo_days))
          & (g.kick_utc <= now + pd.Timedelta(days=hi_days))].copy()
    g["matchup"] = g.away_team + " @ " + g.home_team
    g["lead_days"] = (g.kick_utc - now).dt.total_seconds() / 86400
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=DEPLOY_THRESHOLD)
    ap.add_argument("--regions", default="us,eu",
                    help="must include eu — that's where Pinnacle lives")
    ap.add_argument("--watch-days", type=float, default=10.0,
                    help="observe games this far out (firing stays in T-7..T-2)")
    a = ap.parse_args()

    # Two windows, deliberately different.
    #
    # WATCH from 10 days out: the poller ticks hourly from there, and every
    # observation of every game is recorded so a locked pick's history is
    # continuous rather than starting when the bet fires.
    #
    # FIRE only inside the VALIDATED T-7..T-2 window. Polling early is not
    # betting early. Pinnacle does not post until ~T-6.5, so there is usually
    # nothing to compare against before T-7 anyway, and the backtest measured
    # deviations only inside T-7..T-2 — firing outside it would be
    # extrapolation dressed up as a signal.
    watch = load_window_schedule(lo_days=0.0, hi_days=a.watch_days)
    sched = load_window_schedule()
    if watch.empty:
        print(f"No games inside the {a.watch_days:.0f}-day watch horizon.")
        return 0

    key = os.environ.get("THE_ODDS_API_KEY")
    if not key:
        # Scheduled runs must not go red weekly on a missing key: the opener
        # has no weather-only dry-run side — without odds there is no card.
        print("THE_ODDS_API_KEY not set — opener card needs live odds; skipping.")
        return 0

    from data_ingest.odds_api import OddsAPIClient, ledger_status
    from data_ingest.parse import snapshot_to_frame

    client = OddsAPIClient(key, quota_guard=200)
    res = client.live_odds(regions=a.regions, markets="spreads")
    print(f"odds pulled, cost {res.cost} credit(s), ledger now {ledger_status()}",
          file=sys.stderr)
    frame = snapshot_to_frame(res.payload, "live")

    # Dump DraftKings' spreads for every upcoming game (wider than the card's
    # own T-2..T-7 window — this daily dump is what carries snapshot coverage
    # through game day for already-locked opener picks, so the app can show
    # how far the market has moved off the locked number). Enrichment only —
    # never sink the card. Runs BEFORE the no-qualifying-bets early exit.
    try:
        from data_ingest.line_snapshots import dump_dk_lines
        dump_dk_lines(frame, "spreads")
    except Exception as exc:
        print(f"WARNING: line snapshot dump failed: {exc}", file=sys.stderr)

    # Record the model's view of EVERY game on the board, qualifying or not.
    # This is what lets a locked pick be told "the deviation is gone" without
    # anything being able to retract the bet. Enrichment only, never fatal.
    try:
        from data_ingest.pick_eval import dump_eval_rows
        dump_eval_rows(opener_spread.evaluate_board(frame, watch, a.threshold))
    except Exception as exc:                                   # noqa: BLE001
        print(f"WARNING: opener pick-eval dump failed: {exc}", file=sys.stderr)

    bets = select_opener_bets(frame, sched, threshold=a.threshold)
    if bets is None or len(bets) == 0:
        print(f"No qualifying opener bets at |dev| >= {a.threshold} "
              f"({len(watch)} game(s) watched, {len(sched)} inside T-7..T-2).")
        return 0

    print(f"\n=== OPENER SPREAD CARD  {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ} ===")
    cols = ["matchup", "kick_utc", "bet_team", "side_line", "book", "price",
            "dev", "pin_home_line", "model_prob", "edge_pp", "edge_tier"]
    print(bets[cols].to_string(index=False))
    tiers = bets.edge_tier.value_counts().to_dict()
    print("edge size: " + ", ".join(f"{tiers.get(t, 0)} {t}"
                                    for _, t in EDGE_TIERS) +
          "  (SMALL <3pp, MEDIUM 3-5.5pp, LARGE 5.5pp+ over the quoted price)")
    print(f"\n{len(bets)} bet(s). NOTE: already-taken games are locked by the "
          "publisher — a game reappearing here does NOT re-price its bet.")

    out = Path("data/cards"); out.mkdir(parents=True, exist_ok=True)
    p = out / f"opener_card_{datetime.now(timezone.utc):%Y-%m-%d}.csv"
    bets.to_csv(p, index=False)
    print(f"\nwritten: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

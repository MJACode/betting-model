"""Re-sweep the NCAAF live lanes wider and finer than the shipped grid.

mike, 2026-09-12: *"resweep, nothing is paused, you have backtesting results."*

The first grid (`scripts/ncaaf_inplay_history_backtest.py`) stopped at EV 0.34
and swept only probability x EV. It found two cells positive in both season
halves, and both are ISLANDS: one grid step away in any direction the sign
flips. That fails the house plateau rule, so this re-sweep goes wider on EV,
adds the two structural dimensions the grid never had, and reports only cells
that survive the season split.

DEFINITIONS (fixed before any number was looked at)
- Input: the cached candidates of the production pricing path over the 2025
  season's bought DK in-play snapshots (that harness builds them; this reads
  its cache). FRESH quotes only (`points_since_update == 0`) — the honest read,
  and what the loop can actually take.
- First-signal lock: one bet per (game, lane) per cell, the earliest crossing
  (CLAUDE.md 1c). Same as the first harness.
- `pregame_spread` is home-relative and comes from the states parquet, the same
  column the engine feeds the model. `dog_points` for a moneyline candidate is
  how many points the BACKED side was getting pregame: positive = the pick is
  on the pregame underdog. Totals candidates carry it too (for splitting), but
  a total has no side to be a dog.
- Season half: the median kickoff date of the graded games, so both halves hold
  a comparable number of games rather than a comparable number of days.
- A cell is REPORTED only if it clears `--min-bets` and is positive in BOTH
  halves. Everything else is noise by the rule that killed every previous
  NCAAF false positive.
- Breakeven is the mean DK implied probability of the bets the cell actually
  takes, not a fixed 52.4%: these lanes bet at prices from +101 to -200.

    python -m scripts.ncaaf_live_resweep --season 2025
    python -m scripts.ncaaf_live_resweep --season 2025 --min-bets 25
"""
from __future__ import annotations

import argparse
import math
import pickle
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

LANES = ("ncaaf_live_win_prob", "ncaaf_live_total")
PROB_GRID = [0.55, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.72, 0.75]
EV_GRID = [0.22, 0.26, 0.30, 0.34, 0.38, 0.42, 0.46, 0.50]
# "Do not back a team that was getting more than N points pregame." inf = off.
DOG_CAPS = [float("inf"), 21.0, 14.0, 10.0, 7.0, 3.0]
PERIOD_FLOORS = [1, 2]          # 1 = every period; 2 = skip the first quarter


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (float("nan"), float("nan"))
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def summarise(bets: list[dict]) -> dict:
    n = len(bets)
    graded = [b for b in bets if b["result"] in ("WIN", "LOSS")]
    w = sum(1 for b in graded if b["result"] == "WIN")
    units = sum(b["units"] for b in bets)
    lo, hi = wilson(w, len(graded))
    breakeven = (sum(b["dk_implied_prob"] for b in graded) / len(graded)) if graded else float("nan")
    return {
        "n": n, "w": w, "l": len(graded) - w, "units": units,
        "roi": 100 * units / n if n else float("nan"),
        "win": 100 * w / len(graded) if graded else float("nan"),
        "lo": 100 * lo, "hi": 100 * hi, "breakeven": 100 * breakeven,
        "clears": (lo > breakeven) if graded else False,
    }


def first_signals(cands, *, pmin, ev_min, dog_cap, period_floor, edge_floor, cap):
    """One bet per (game, lane): the earliest candidate that crosses the cell."""
    seen: set = set()
    out: list[dict] = []
    for c in cands:                                   # already sorted by served
        if c["game_id"] in seen:
            continue
        if c["period"] < period_floor:
            continue
        if c["model_probability"] < pmin:
            continue
        if abs(c["edge"]) > cap or c["edge"] < edge_floor:
            continue
        if c["ev"] < ev_min:
            continue
        if c["dog_points"] is not None and c["dog_points"] > dog_cap:
            continue
        seen.add(c["game_id"])
        out.append(c)
    return out


def load(season: int) -> list[dict]:
    cache = Path(tempfile.gettempdir()) / f"ncaaf_inplay_candidates_{season}.pkl"
    if not cache.exists():
        raise SystemExit(f"no candidate cache at {cache} — run "
                         f"scripts/ncaaf_inplay_history_backtest.py --season {season} first")
    cands = pickle.loads(cache.read_bytes())
    print(f"loaded {len(cands):,} candidates from {cache}")
    return cands


def attach(cands: list[dict], states_path: Path) -> list[dict]:
    """Add `ev` and `dog_points`, and keep only fresh, graded candidates."""
    import pandas as pd

    st = pd.read_parquet(states_path, columns=["game_id", "pregame_spread"])
    spread = st.drop_duplicates("game_id").set_index("game_id")["pregame_spread"].to_dict()

    out = []
    missing = 0
    for c in cands:
        if c["points_since_update"] != 0 or c["result"] not in ("WIN", "LOSS"):
            continue
        price = c["dk_odds"]
        p = c["model_probability"]
        profit = (price / 100.0) if price > 0 else (100.0 / abs(price))
        c["ev"] = p * profit - (1 - p)
        sp = spread.get(c["game_id"])
        if sp is None or (isinstance(sp, float) and math.isnan(sp)):
            missing += 1
            c["dog_points"] = None
        elif c["model_id"] == "ncaaf_live_win_prob":
            # home-relative: +7 means the HOME side was getting 7.
            c["dog_points"] = float(sp) if c["pick_side"] == "home" else -float(sp)
        else:
            c["dog_points"] = None
        out.append(c)
    print(f"fresh graded candidates: {len(out):,}  (no pregame spread: {missing:,})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--min-bets", type=int, default=20)
    ap.add_argument("--states", default="ncaaf_live/data/artifacts/states_all.parquet")
    args = ap.parse_args()

    from ncaaf_live.serve import MAX_EDGE_CAP as cap

    cands = attach(load(args.season), ROOT / args.states)

    # Season halves by median kickoff date of the graded games.
    dates = sorted({c["served"].date() for c in cands})
    mid = dates[len(dates) // 2]
    print(f"season halves split at {mid} ({len(dates)} game days)\n")

    for lane in LANES:
        lane_c = [c for c in cands if c["model_id"] == lane]
        edge_floor = config.ACTION_THRESHOLDS[lane]["min_edge"]
        p_now = config.ACTION_THRESHOLDS[lane]["min_prob"]
        ev_now = config.MODEL_MIN_EV.get(lane)
        print(f"=== {lane}: {len(lane_c):,} fresh graded candidates "
              f"(shipped cut prob>={p_now} ev>={ev_now}) ===")

        rows = []
        for pmin in PROB_GRID:
            for ev_min in EV_GRID:
                for dog_cap in DOG_CAPS:
                    for period_floor in PERIOD_FLOORS:
                        if lane != "ncaaf_live_win_prob" and dog_cap != float("inf"):
                            continue          # a total has no side to be a dog
                        bets = first_signals(
                            lane_c, pmin=pmin, ev_min=ev_min, dog_cap=dog_cap,
                            period_floor=period_floor, edge_floor=edge_floor, cap=cap)
                        s = summarise(bets)
                        if s["n"] < args.min_bets:
                            continue
                        h1 = summarise([b for b in bets if b["served"].date() <= mid])
                        h2 = summarise([b for b in bets if b["served"].date() > mid])
                        rows.append((s, h1, h2, pmin, ev_min, dog_cap, period_floor))

        both = [r for r in rows if r[1]["n"] and r[2]["n"]
                and r[1]["roi"] > 0 and r[2]["roi"] > 0]
        both.sort(key=lambda r: -r[0]["roi"])
        print(f"  {len(rows)} cells at >= {args.min_bets} bets; "
              f"{len(both)} positive in BOTH halves\n")
        if not both:
            print("  NO CELL survives the season split at this bet floor.\n")
            continue
        print(f"  {'prob':>5} {'ev':>5} {'dogcap':>7} {'perF':>5} "
              f"{'bets':>5} {'units':>8} {'roi':>7} {'win%':>6} {'CI':>14} "
              f"{'brkevn':>7} {'clears':>6} {'H1 roi':>7} {'H2 roi':>7}")
        for s, h1, h2, pmin, ev_min, dog_cap, pf in both[:18]:
            dc = "-" if dog_cap == float("inf") else f"{dog_cap:g}"
            print(f"  {pmin:>5.2f} {ev_min:>5.2f} {dc:>7} {pf:>5} "
                  f"{s['n']:>5} {s['units']:>+8.2f} {s['roi']:>+6.1f}% {s['win']:>5.1f}% "
                  f"[{s['lo']:>4.1f},{s['hi']:>5.1f}] {s['breakeven']:>6.1f}% "
                  f"{('YES' if s['clears'] else 'no'):>6} "
                  f"{h1['roi']:>+6.1f}% {h2['roi']:>+6.1f}%")
        print()


if __name__ == "__main__":
    main()

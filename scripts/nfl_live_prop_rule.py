"""The feasibility rule with no fitting at all, one bet per player, season by season.

WHY THIS EXISTS BESIDE THE FITTED MODEL. Section 5 of
`nfl_live_prop_feasibility.py` fitted six coefficients per market and produced
+13.4% on 2025 carries and +0.8% on 2024 carries off the same construction.
When two out-of-sample seasons disagree by twelve points, the honest next step
is to remove the degrees of freedom rather than to pick the season that agreed:
a rule with one threshold and no fitted parameters cannot have found the 2025
number by searching, so whether it survives is informative.

TWO CORRECTIONS THIS MAKES TO THE EARLIER GRADING.

  ONE BET PER PLAYER PER GAME. The archive holds a quote about every five
  minutes, so a single player in a single game appears ~40 times. Grading all
  of them counts one opinion forty times and reports it as forty bets.
  Production cannot place them either: CLAUDE.md section 1c locks the first BET
  per lane and never re-prices it. So this takes the FIRST quote that qualifies
  and ignores the rest, which is both the honest unit of analysis and what the
  live worker would actually do.

  ONE THRESHOLD, NO FITTED PARAMETERS. The rule is a single cut on a single
  quantity, applied identically to 2023, 2024 and 2025.

WHAT THIS IS NOT, STATED PLAINLY. **There is no holdout here.** The threshold
of 1.25 does predate the archive -- it came from bucketing the 2026 production
bets in `docs/nfl_live_prop_assessment.md` -- but the MARKET (carries) and the
SIDE (under) were both chosen by reading the pooled table over all three
seasons. So the per-season split below is a consistency check on data the rule
has already seen, not an out-of-sample test, and the three seasons agreeing is
weaker evidence than three independent seasons would be. The first genuine
out-of-sample test is 2026, and it has not happened: the live worker has only
ever bought `player_pass_attempts`, so no 2026 carries quote exists to grade.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

STATE = "nfl/data/live_model/_quotes_state.parquet"
MARKETS = ["attempts", "completions", "receptions", "carries"]
MIN_SECONDS = 240
MAX_SECONDS = 3600


def american_b(a):
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, a / 100.0, 100.0 / np.abs(np.where(a == 0, -100.0, a)))


def boot_roi(profit, games, draws: int = 4000, seed: int = 0):
    rng = np.random.default_rng(seed)
    uniq = pd.unique(games)
    by = {g: profit[games == g] for g in uniq}
    out = np.empty(draws)
    for i in range(draws):
        s = np.concatenate([by[g] for g in rng.choice(uniq, len(uniq), True)])
        out[i] = s.mean() if len(s) else 0.0
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def load() -> pd.DataFrame:
    d = pd.read_parquet(STATE)
    d = d[d["secs"].between(MIN_SECONDS, MAX_SECONDS)].copy()
    d = d[d["accrued"] <= d["line"]]              # the over is not already decided
    d["pace_so_far"] = d["accrued"] / d["elapsed_min"].clip(lower=1.0)
    d = d[d["pace_so_far"] > 0]                   # a pace has to exist to compare to
    d["pace_needed"] = d["slack"] / d["min_left"].clip(lower=1e-9)
    d["pace_ratio"] = d["pace_needed"] / d["pace_so_far"]
    need = ["over_price", "under_price", "went_over", "push", "pace_ratio"]
    return d[d[need].notna().all(axis=1)].sort_values("ts")


def first_per_player(g: pd.DataFrame) -> pd.DataFrame:
    """One bet per player per market per game -- the first quote that qualified."""
    return g.drop_duplicates(subset=["game_id", "stat", "join_name"], keep="first")


def grade(g: pd.DataFrame, side: str) -> pd.DataFrame:
    g = g.copy()
    g["side"] = side
    price = g["over_price"] if side == "over" else g["under_price"]
    won = (g["went_over"] == 1) if side == "over" else (g["went_over"] == 0)
    g["profit"] = np.where(g["push"] == 1, 0.0,
                           np.where(won, american_b(price), -1.0))
    return g


def report(d: pd.DataFrame, ratio_cut: float, max_price: float) -> pd.DataFrame:
    """Bet the UNDER when the over needs a pace the player has not been managing."""
    rows = []
    for stat in MARKETS:
        for season in (2023, 2024, 2025):
            s = d[(d["stat"] == stat) & (d["season"] == season)
                  & (d["pace_ratio"] >= ratio_cut)
                  & (d["under_price"] >= max_price)]
            s = first_per_player(s)
            if s.empty:
                rows.append({"stat": stat, "season": season, "bets": 0})
                continue
            g = grade(s, "under")
            prof = g["profit"].to_numpy()
            lo, hi = boot_roi(prof, g["game_id"].to_numpy())
            rows.append({
                "stat": stat, "season": season, "bets": len(g),
                "games": g["game_id"].nunique(),
                "under_hit": float((g["went_over"] == 0).mean()),
                "units": prof.sum(), "roi": prof.mean(),
                "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratio", type=float, default=1.25,
                    help="bet the under above this required-pace ratio")
    ap.add_argument("--max-price", type=float, default=-140.0,
                    help="refuse an under priced worse than this")
    a = ap.parse_args()
    d = load()
    print(f"{len(d):,} live quotes with a usable pace, "
          f"{d['game_id'].nunique():,} games, 2023-2025.\n")

    print("=" * 84)
    print(f"THE UNDER WHEN THE OVER NEEDS A SURGE  "
          f"(pace ratio >= {a.ratio}, price >= {a.max_price:.0f})")
    print("=" * 84)
    print("One bet per player per game. ROI interval resamples games.\n")
    t = report(d, a.ratio, a.max_price)
    print(t.to_string(index=False, float_format=lambda x: f"{x:8.4f}"))

    print("\n" + "=" * 84)
    print("POOLED ACROSS SEASONS, AND THE THRESHOLD NEIGHBOURHOOD")
    print("=" * 84)
    rows = []
    for ratio in (1.0, 1.1, 1.25, 1.4, 1.6, 2.0):
        s = first_per_player(d[(d["pace_ratio"] >= ratio)
                               & (d["under_price"] >= a.max_price)])
        for stat in MARKETS:
            p = s[s["stat"] == stat]
            if len(p) < 30:
                rows.append({"ratio": ratio, "stat": stat, "bets": len(p)})
                continue
            g = grade(p, "under")
            prof = g["profit"].to_numpy()
            lo, hi = boot_roi(prof, g["game_id"].to_numpy())
            rows.append({"ratio": ratio, "stat": stat, "bets": len(g),
                         "units": prof.sum(), "roi": prof.mean(),
                         "ci_lo": lo, "ci_hi": hi})
    print(pd.DataFrame(rows).pivot(index="ratio", columns="stat").to_string(
        float_format=lambda x: f"{x:8.3f}"))


if __name__ == "__main__":
    main()

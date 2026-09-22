"""Is the carries edge a real mispricing, or is it catching prices mid-move?

THE WORRY. The archive stores a snapshot about every five minutes, so a quote
graded here can be up to five minutes stale. If DraftKings starts marking a
running back's line down the moment his pace lags, then "the first quote where
the over needed a surge" is systematically a price the book had ALREADY begun
to abandon -- and a live worker reading fresh prices would never be offered it.
That would make the measured +11% stale-line capture rather than a mispricing,
and it would not survive contact with production.

THREE TESTS, EACH OF WHICH THE EDGE HAS TO PASS.

  1. TAKE THE SECOND QUALIFYING QUOTE, NOT THE FIRST. Five minutes later, on a
     line the book has had another cycle to correct. If the edge is staleness
     it decays; if it is a mispricing the book is not correcting, it holds.
  2. SPLIT ON WHETHER THE BOOK HAD JUST MOVED. For each bet, compare the line
     to the same player's previous snapshot. Profit that lives only in the
     "the number just moved" bucket is profit taken from a price in motion.
  3. HOLD THE QUOTE AND RE-PRICE IT LATER. Waiting five and ten minutes is the
     same question asked a third way, and it is the one a slow worker actually
     faces.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import scripts.nfl_live_prop_rule as R

RATIO = 1.25
MAX_PRICE = -140.0


def qualifying(d: pd.DataFrame) -> pd.DataFrame:
    return d[(d["stat"] == "carries") & (d["pace_ratio"] >= RATIO)
             & (d["under_price"] >= MAX_PRICE)
             & (d["book"] == "draftkings")].sort_values("ts")


def nth_per_player(g: pd.DataFrame, n: int) -> pd.DataFrame:
    """The n-th qualifying quote for each player-game, 0-indexed."""
    r = g.groupby(["game_id", "stat", "join_name"]).cumcount()
    return g[r == n]


def summarise(g: pd.DataFrame, label: str) -> dict:
    if g.empty:
        return {"which": label, "bets": 0}
    gr = R.grade(g, "under")
    prof = gr["profit"].to_numpy()
    lo, hi = R.boot_roi(prof, gr["game_id"].to_numpy())
    return {"which": label, "bets": len(gr), "games": gr["game_id"].nunique(),
            "under_hit": float((gr["went_over"] == 0).mean()),
            "units": prof.sum(), "roi": prof.mean(), "ci_lo": lo, "ci_hi": hi}


def main() -> None:
    d = R.load()
    q = qualifying(d)

    print("=" * 84)
    print("1. THE FIRST QUALIFYING QUOTE, THE SECOND, THE THIRD")
    print("=" * 84)
    print("   Each is ~5 minutes later on a line the book has had another")
    print("   cycle to correct. Staleness decays; a mispricing does not.\n")
    print(pd.DataFrame([summarise(nth_per_player(q, n), f"quote #{n + 1}")
                        for n in range(4)]).to_string(
        index=False, float_format=lambda x: f"{x:8.4f}"))

    # --- 2. had the book just moved this player's number?
    print("\n" + "=" * 84)
    print("2. DID THE PROFIT COME FROM A NUMBER THAT HAD JUST MOVED?")
    print("=" * 84)
    print("   The same player's previous snapshot, whatever it was, against")
    print("   the line we bet. Profit confined to the moved bucket would be")
    print("   profit taken from a price in motion.\n")
    all_c = d[(d["stat"] == "carries") & (d["book"] == "draftkings")].sort_values("ts")
    key = ["game_id", "stat", "join_name"]
    all_c["prev_line"] = all_c.groupby(key)["line"].shift(1)
    all_c["prev_ts"] = all_c.groupby(key)["ts"].shift(1)
    first = nth_per_player(qualifying(all_c), 0).copy()
    first["moved"] = (first["line"] - first["prev_line"]).abs()
    first["gap_min"] = (first["ts"] - first["prev_ts"]).dt.total_seconds() / 60.0
    rows = [summarise(first[first["prev_line"].isna()], "no previous snapshot"),
            summarise(first[first["moved"] == 0], "line unchanged"),
            summarise(first[first["moved"].between(0.01, 0.5)], "moved <= 0.5"),
            summarise(first[first["moved"] > 0.5], "moved > 0.5")]
    print(pd.DataFrame(rows).to_string(
        index=False, float_format=lambda x: f"{x:8.4f}"))

    # --- 3. wait, then bet whatever the book is showing later
    print("\n" + "=" * 84)
    print("3. WAIT, THEN TAKE WHATEVER PRICE IS ON THE BOARD")
    print("=" * 84)
    print("   The question a slow worker actually faces. The bet is placed on")
    print("   the LATER quote's own price, not the one that triggered it.\n")
    trig = nth_per_player(qualifying(all_c), 0)[["game_id", "stat", "join_name", "ts"]]
    trig = trig.rename(columns={"ts": "trig_ts"})
    later = all_c.merge(trig, on=["game_id", "stat", "join_name"], how="inner")
    later["wait_min"] = (later["ts"] - later["trig_ts"]).dt.total_seconds() / 60.0
    rows = []
    for lo_m, hi_m in ((0, 0), (1, 6), (6, 12), (12, 20)):
        w = later[(later["wait_min"] > lo_m - 0.01) & (later["wait_min"] <= hi_m)] \
            if hi_m else later[later["wait_min"] == 0]
        w = w[w["under_price"] >= MAX_PRICE]
        w = w.sort_values("ts").drop_duplicates(
            subset=["game_id", "stat", "join_name"], keep="first")
        rows.append(summarise(w, f"{lo_m}-{hi_m} min later" if hi_m else "at once"))
    print(pd.DataFrame(rows).to_string(
        index=False, float_format=lambda x: f"{x:8.4f}"))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Is DraftKings' alternate ladder calibrated? Graded before any model touches it.

    python -m scripts.nfl_prop_ladder_calibration
    python -m scripts.nfl_prop_ladder_calibration --book fanduel

WHY THIS RUNS FIRST (docs/nfl_prop_method_search.md §3-4, 2026-09-11, mike:
"1 and 2"). The method left for the stat models is to anchor the median to the
market and sell the SHAPE at alternate lines. That only has somewhere to go if
the book's own ladder is mispriced somewhere. So before building a simulator,
measure the ladder itself: every alternate OVER price DraftKings quoted in the
`open` series, 2023-25, against the realised outcome, bucketed by where the
strike sits relative to the main line and by the implied probability.

If the ladder is calibrated everywhere (realised ≈ fair at every strike), no
pooled shape can beat it and only a per-player shape could -- which is the §4
experiment. If it is miscalibrated in a band, that band is a MECHANICAL edge
that needs no player model at all, and the experiment's placebo would have
found it. Either way this is the number the experiment is read against.

THE LADDER IS OVER-ONLY. DraftKings quotes no under on 2025 alternates (15% of
2023 rows, 4% of 2024 carry one), so the ladder cannot be de-vigged two-way.
Two readings are reported and the gap between them is the uncertainty:

  raw       the over price's implied probability, vig included
  adjusted  the same, scaled by the proposition's MAIN line: fair_over_main /
            implied_over_main from the two-way main quote at the same snapshot.
            This is the multiplicative de-vig, which is known to UNDER-correct
            longshots (the favourite-longshot bias runs the other way), so at
            high strikes the true fair probability is if anything lower than
            "adjusted". A tail that reads under-priced on "adjusted" is a real
            finding; one that reads under-priced only on "raw" is the vig.

One ladder per proposition: the LATEST pre-kickoff `open` snapshot for the
(game, player, market), compared as timestamps (the string-compare trap of
2026-09-11 is not repeated here). Pushes (actual == strike) are skipped.

"ROI blind" is the return of betting EVERY over in the bucket at the quoted
price, one unit each -- the number a mechanical edge would have to show.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import models.nfl_prop_market as mk
from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name
from models.market_relative import devig, implied

ALT_MARKETS = {
    "player_reception_yds_alternate": "player_reception_yds",
    "player_rush_yds_alternate": "player_rush_yds",
    "player_pass_yds_alternate": "player_pass_yds",
    "player_receptions_alternate": "player_receptions",
    "player_rush_attempts_alternate": "player_rush_attempts",
    "player_pass_completions_alternate": "player_pass_completions",
    "player_pass_tds_alternate": "player_pass_tds",
    "player_rush_reception_yds_alternate": "player_rush_reception_yds",
}
REL_BUCKETS = ((0.0, 0.6), (0.6, 0.85), (0.85, 1.15), (1.15, 1.5), (1.5, 2.0), (2.0, 99.0))
PROB_BUCKETS = ((0.0, 0.15), (0.15, 0.3), (0.3, 0.45), (0.45, 0.6), (0.6, 0.75), (0.75, 1.01))


def actual_for(row, base: str):
    stat = mk.MARKET_STAT[base]
    if stat == "DERIVED_rush_rec_yds":
        return float(row.rushing_yards or 0) + float(row.receiving_yards or 0)
    v = getattr(row, stat, None)
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def profit(price: float, won: bool) -> float:
    return (price / 100.0 if price > 0 else 100.0 / abs(price)) if won else -1.0


def load(book: str) -> pd.DataFrame:
    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    odds = odds[(odds.bookmaker == book) & (odds.snapshot_type == "open")
                & (~odds.game_id.astype(str).str.startswith("NFL_2026"))].copy()
    ko = (local_store.read_table("nfl_team_game_stats", columns=["game_id", "commence_time"])
          .dropna(subset=["commence_time"]).drop_duplicates("game_id"))
    ko["kick"] = pd.to_datetime(ko.commence_time, utc=True)
    odds = odds.merge(ko[["game_id", "kick"]], on="game_id", how="inner")
    odds["ts"] = pd.to_datetime(odds.snapshot_at, utc=True, format="mixed")
    odds = odds[odds.ts <= odds.kick].copy()
    odds["norm"] = odds.player_name.map(norm_player_name)
    return odds


def build(book: str) -> pd.DataFrame:
    odds = load(book)
    log = local_store.read_table("nfl_player_game_log")
    act = {(r.norm_name, r.game_id): r for r in log.itertuples(index=False)}

    main = odds[odds.market.isin(ALT_MARKETS.values())]
    alt = odds[odds.market.isin(ALT_MARKETS.keys())].copy()
    alt["base"] = alt.market.map(ALT_MARKETS)

    # latest pre-kickoff snapshot per proposition, main and ladder separately
    main_latest = (main.sort_values("ts").groupby(["game_id", "norm", "market"], as_index=False)
                   .last()[["game_id", "norm", "market", "line", "over_price", "under_price", "ts"]]
                   .rename(columns={"market": "base", "line": "main_line",
                                    "over_price": "main_over", "under_price": "main_under",
                                    "ts": "main_ts"}))
    alt_last_ts = alt.groupby(["game_id", "norm", "base"]).ts.transform("max")
    alt = alt[alt.ts == alt_last_ts]
    alt = alt.merge(main_latest, on=["game_id", "norm", "base"], how="inner")

    rows = []
    for r in alt.itertuples(index=False):
        if r.over_price is None or not np.isfinite(float(r.over_price)):
            continue
        a = act.get((r.norm, r.game_id))
        if a is None:
            continue
        actual = actual_for(a, r.base)
        if actual is None or actual == float(r.line):
            continue
        fo, _fu = devig(r.main_over, r.main_under)
        imp_main = implied(r.main_over)
        raw = implied(r.over_price)
        if raw is None or fo is None or imp_main is None or imp_main <= 0:
            continue
        rows.append(dict(
            season=int(r.season), base=r.base, game_id=r.game_id, player=r.norm,
            strike=float(r.line), main_line=float(r.main_line),
            rel=float(r.line) / max(float(r.main_line), 0.5),
            price=float(r.over_price), raw=raw, adj=min(raw * (fo / imp_main), 0.999),
            over=bool(actual > float(r.line)),
        ))
    return pd.DataFrame(rows)


def _table(df: pd.DataFrame, key: str, buckets, label: str) -> None:
    print(f"    {label:>11} {'n':>6} {'raw':>6} {'adj':>6} {'real':>6} {'real-adj':>9} "
          f"{'ROI blind':>9}  seasons (real-adj)")
    for lo, hi in buckets:
        b = df[(df[key] >= lo) & (df[key] < hi)]
        if len(b) < 100:
            continue
        prof = np.array([profit(p, w) for p, w in zip(b.price, b.over)])
        per = " ".join(f"{s}:{100*(g.over.mean()-g.adj.mean()):+.1f}({len(g)})"
                       for s, g in b.groupby("season"))
        print(f"    {lo:>4.2f}-{hi:<5.2f} {len(b):>6} {100*b.raw.mean():>5.1f}% "
              f"{100*b.adj.mean():>5.1f}% {100*b.over.mean():>5.1f}% "
              f"{100*(b.over.mean()-b.adj.mean()):>+8.1f}pp {100*prof.mean():>+8.2f}%  {per}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="draftkings")
    a = ap.parse_args()
    df = build(a.book)
    print(f"\n{a.book} alternate ladder, `open` series 2023-25, latest pre-kickoff snapshot "
          f"per proposition: {len(df):,} (strike) rows over "
          f"{df.groupby(['game_id','player','base']).ngroups:,} propositions\n")
    print("ALL MARKETS, by strike position (strike / main line):")
    _table(df, "rel", REL_BUCKETS, "strike/line")
    print("\nALL MARKETS, by adjusted implied probability:")
    _table(df, "adj", PROB_BUCKETS, "adj prob")
    for base, g in df.groupby("base"):
        print(f"\n{base}: {len(g):,} rows, {g.groupby(['game_id','player']).ngroups:,} props")
        _table(g, "rel", REL_BUCKETS, "strike/line")
    print("\nRead `real-adj`: positive means the over hit MORE often than the vig-adjusted "
          "price said, i.e. the over was under-priced there. Multiplicative adjustment "
          "under-corrects longshots, so a positive reading at high strikes is conservative; "
          "a negative one is the favourite-longshot bias doing what it always does.")


if __name__ == "__main__":
    main()

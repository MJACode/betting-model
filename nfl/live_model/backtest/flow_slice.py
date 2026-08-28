"""
Is the pass attempt bias structural, or does it live in one slice?

THE QUESTION THIS DECIDES. The lane's whole case is that DK posts the live
pass attempt line about 2.33 attempts BELOW the eventual final, in 2023, in
2024, and again out of sample in 2025. If that is uniform across game states
it is a structural centring error and an over bettor harvests it all game. If
instead it is concentrated -- only in blowouts, only in the fourth quarter,
only when a team is already throwing -- then the +28% backtest ROI is the
average of one profitable slice and several dead ones, the lane is far
narrower than it looks, and sizing off the pooled number would be sizing off
a figure that does not describe most of the bets.

It also tests the stated MECHANISM against itself. The explanation on record
is that late passing volume arrives at a low completion rate: hurry-up,
sideline throws, spikes, desperation deep balls. That makes a falsifiable
prediction -- the bias must be LARGER where a team is throwing more than the
league norm. If the bias is flat across pass rate, the mechanism is a story
told after the fact and the number is uninterpreted.

No model is trained here. Only the posted line and the actual final are
compared, so nothing below can be an artifact of a fit.

    python -m live_model.backtest.flow_slice --market player_pass_attempts
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from .flow_eval import load_rows
from .flow_validate import (
    attach_ids, load_snapshots, match_to_flow, resolve_snaps,
)

BOOT_DRAWS = 2000
# A bucket thinner than this cannot separate signal from noise and is reported
# but never allowed to drive the verdict.
MIN_QUOTES = 60


def _clustered_ci(err: np.ndarray, games: np.ndarray,
                  draws: int = BOOT_DRAWS) -> tuple[float, float]:
    """
    Bootstrap the mean bias by RESAMPLING GAMES, not quotes.

    Every quote in a game shares one actual final, so quotes are not
    independent draws. Resampling quotes would shrink the interval by roughly
    the square root of quotes per game and would manufacture significance in
    every bucket. Resampling whole games keeps the correlation intact.
    """
    uniq = np.unique(games)
    if len(uniq) < 3:
        return (float("nan"), float("nan"))
    by_game = {g: err[games == g] for g in uniq}
    rng = np.random.default_rng(11)
    means = np.empty(draws)
    for i in range(draws):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        means[i] = np.concatenate([by_game[g] for g in pick]).mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _rows_for(d: pd.DataFrame, dim: str, labels: pd.Series) -> list[dict]:
    out = []
    err = (d["line"] - d["actual_final"]).to_numpy()
    games = d["game_id"].to_numpy()
    for name, idx in labels.groupby(labels).groups.items():
        m = labels.index.isin(idx)
        e, g = err[m], games[m]
        if len(e) == 0:
            continue
        lo, hi = _clustered_ci(e, g)
        out.append({
            "dimension": dim,
            "bucket": str(name),
            "quotes": int(len(e)),
            "games": int(pd.unique(g).size),
            "bias": float(e.mean()),
            "median": float(np.median(e)),
            "ci_lo": lo,
            "ci_hi": hi,
            "over_rate": float((d["actual_final"].to_numpy()[m]
                                > d["line"].to_numpy()[m]).mean()),
        })
    return out


def _qcut(s: pd.Series, n: int, prefix: str) -> pd.Series:
    """Quartile labels that survive ties and degenerate columns."""
    try:
        q = pd.qcut(s, n, duplicates="drop")
    except (ValueError, IndexError):
        return pd.Series([f"{prefix} all"] * len(s), index=s.index)
    return q.astype(str)


def slice_table(d: pd.DataFrame) -> pd.DataFrame:
    d = d.dropna(subset=["line", "actual_final"]).copy()
    rows: list[dict] = []

    rows += _rows_for(d, "pooled", pd.Series(["ALL"] * len(d), index=d.index))

    if "period" in d:
        rows += _rows_for(d, "quarter",
                          d["period"].astype("Int64").astype(str))

    if "team_margin" in d:
        def _state(m):
            if m <= -9:
                return "trailing 2+ scores"
            if m <= -1:
                return "trailing 1 score"
            if m == 0:
                return "tied"
            if m <= 8:
                return "leading 1 score"
            return "leading 2+ scores"
        rows += _rows_for(d, "score state", d["team_margin"].map(_state))

    if "seconds_remaining" in d:
        rows += _rows_for(d, "time left",
                          _qcut(d["seconds_remaining"], 4, "secs"))

    # THE MECHANISM TEST. If late volume at a low completion rate is really
    # what the book is missing, the bias must deepen where a team is already
    # throwing more than the league.
    if "pass_rate_vs_league" in d:
        rows += _rows_for(d, "pass rate vs league",
                          _qcut(d["pass_rate_vs_league"], 4, "prvl"))

    if "line" in d:
        rows += _rows_for(d, "line size", _qcut(d["line"], 4, "line"))
    if "accrued_vs_expected" in d:
        rows += _rows_for(d, "player running hot",
                          _qcut(d["accrued_vs_expected"], 4, "ave"))
    if "is_home" in d:
        rows += _rows_for(d, "home or away",
                          d["is_home"].map({1: "home", 0: "away",
                                            True: "home", False: "away"})
                          .fillna("unknown"))
    if "season" in d:
        rows += _rows_for(d, "season", d["season"].astype(int).astype(str))

    return pd.DataFrame(rows)


def verdict(t: pd.DataFrame) -> list[str]:
    """
    Structural or concentrated, stated plainly.

    Only buckets with enough quotes vote. A bucket whose interval crosses zero
    is not evidence of a bias there, and a bucket on the WRONG side of zero is
    evidence against the lane holding everywhere.
    """
    out = []
    solid = t[(t.quotes >= MIN_QUOTES) & t.ci_hi.notna()
              & (t.dimension != "pooled")]
    if solid.empty:
        return ["not enough quotes in any bucket to judge"]

    neg = solid[solid.ci_hi < 0]
    straddle = solid[(solid.ci_lo < 0) & (solid.ci_hi >= 0)]
    pos = solid[solid.ci_lo > 0]

    out.append(f"{len(neg)}/{len(solid)} buckets are negative with the whole "
               f"interval below zero, {len(straddle)} straddle zero, "
               f"{len(pos)} are POSITIVE (wrong side).")

    share = len(neg) / len(solid)
    if len(pos):
        out.append("CONCENTRATED, and worse than narrow: some game states "
                   "have the bias running the OTHER way, so an all-game over "
                   "rule is betting into them.")
        for _, r in pos.iterrows():
            out.append(f"    wrong side: {r.dimension} = {r.bucket} "
                       f"bias {r.bias:+.2f} [{r.ci_lo:+.2f}, {r.ci_hi:+.2f}]")
    elif share >= 0.8:
        out.append("STRUCTURAL: the bias holds in nearly every game state, "
                   "which is what an all-game over rule needs.")
    elif share >= 0.5:
        out.append("MIXED: real in most states, absent in a meaningful "
                   "minority. Gate the lane on the states where it holds "
                   "rather than sizing off the pooled number.")
    else:
        out.append("CONCENTRATED: most buckets cannot show the bias at all. "
                   "The pooled figure is carried by a slice, and sizing off "
                   "it would size off a number that does not describe most "
                   "bets.")

    # POWER, stated before anyone reads "MIXED" as "the bias is absent".
    # A per game miss of a few attempts means a bucket with a handful of games
    # cannot resolve a 2.33 bias whether or not it is there. Silence in a thin
    # bucket is not evidence of absence and must not be reported as if it were.
    # Ask it of the buckets that actually failed to show the bias, not of the
    # slice as a whole: a median dragged up by one well populated dimension
    # hides that the straddlers are the small ones.
    if len(straddle):
        thin = float(straddle["games"].median())
        firm = float(neg["games"].median()) if len(neg) else float("nan")
        if thin < 40 or (pd.notna(firm) and thin < 0.6 * firm):
            out.append(
                f"POWER WARNING: the buckets that failed to show the bias hold "
                f"a median of {thin:.0f} games, against {firm:.0f} for the "
                f"buckets that showed it. At that size a bucket cannot resolve "
                f"a 2.33 bias whether or not it is present, so their silence "
                f"is not evidence of absence. Treat the verdict as provisional "
                f"until a denser pull lands.")

    # The mechanism has its own verdict, because it is falsifiable on its own.
    mech = t[(t.dimension == "pass rate vs league") & (t.quotes >= MIN_QUOTES)]
    if len(mech) >= 2:
        lo_b = mech.iloc[0]["bias"]
        hi_b = mech.iloc[-1]["bias"]
        if hi_b < lo_b - 0.25:
            out.append(f"MECHANISM HOLDS: bias deepens {lo_b:+.2f} to "
                       f"{hi_b:+.2f} as a team throws more than the league, "
                       "which is what late low-completion volume predicts.")
        else:
            out.append(f"MECHANISM NOT SUPPORTED: bias is flat across pass "
                       f"rate ({lo_b:+.2f} to {hi_b:+.2f}). The explanation "
                       "on record does not describe the data, so the number "
                       "is real but uninterpreted.")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="player_pass_attempts")
    ap.add_argument("--seasons", type=int, nargs="+", default=None)
    args = ap.parse_args()

    flow = load_rows()
    if args.seasons:
        flow = flow[flow.season.isin(args.seasons)]
    flow = flow[flow.market == args.market]
    if flow.empty:
        raise SystemExit(f"no flow rows for {args.market}")

    snaps = load_snapshots()
    if snaps.empty:
        raise SystemExit("no prop snapshots parsed")
    snaps, dropped = attach_ids(snaps, set(flow["player_id"].unique()))
    snaps = resolve_snaps(snaps)
    snaps = snaps[snaps.market == args.market]

    flow = flow.copy()
    flow["arm"] = "book"
    m = match_to_flow(snaps, flow)
    if m.empty:
        raise SystemExit("nothing matched")
    m = m.drop_duplicates(subset=["quote_id"])

    print(f"market {args.market}: {len(m):,} quotes over "
          f"{m.game_id.nunique():,} games, {dropped:,} names dropped\n")
    print("book line minus actual final. NEGATIVE means the book posts LOW,")
    print("which is what an over bettor harvests. Intervals are 95% and are")
    print("bootstrapped by RESAMPLING GAMES, since quotes inside one game")
    print("share a single final and are not independent.\n")

    t = slice_table(m)
    hdr = (f"{'dimension':22s} {'bucket':22s} {'n':>6s} {'gms':>5s} "
           f"{'bias':>7s} {'med':>7s} {'95% CI':>18s} {'over%':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for dim, sub in t.groupby("dimension", sort=False):
        for _, r in sub.iterrows():
            ci = (f"[{r.ci_lo:+6.2f},{r.ci_hi:+6.2f}]"
                  if pd.notna(r.ci_lo) else "        thin      ")
            flag = "" if r.quotes >= MIN_QUOTES else "  (thin)"
            print(f"{r.dimension:22s} {r.bucket:22s} {r.quotes:6d} "
                  f"{r.games:5d} {r.bias:+7.2f} {r['median']:+7.2f} {ci:>18s} "
                  f"{100 * r.over_rate:5.1f}%{flag}")
        print()

    print("VERDICT")
    for line in verdict(t):
        print(" ", line)


if __name__ == "__main__":
    main()

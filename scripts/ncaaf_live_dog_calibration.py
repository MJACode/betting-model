"""Is the live win-probability model WRONG when it backs a big pregame underdog?

mike, 2026-09-12: *"I don't want a cap, you're not thinking. If Oklahoma State
is a 24 point dog, then they are up by only a TD in the second quarter and you
say bet them live at even money, that is just retarded. Give me an actual
statistical model."*

He is right that a cap is a patch. A cap says "do not bet here"; it does not
say whether the NUMBER is wrong. This measures the number.

THE QUESTION, stated so it can only have one answer: conditional on the backed
side having been an N-point pregame underdog, does the model's claimed win
probability match the rate those sides actually won? Pooled calibration
(already in the first harness) cannot see this -- a model can be perfectly
calibrated overall and badly wrong inside one slice, because the slices cancel.

DEFINITIONS (fixed before any number was looked at)
- Population: every fresh, graded candidate the production pricing path
  produced over the 2025 season's DK in-play snapshots -- NOT just the ones
  that cleared a cut, so the table sees the whole conditional distribution and
  not the tail a threshold already selected.
- ONE ROW PER (game, dog bucket, lead bucket): the earliest such candidate.
  Without this a single blowout contributes hundreds of near-identical states
  and the "actual" rate becomes a statement about that one game.
- `dog_points`: how many points the BACKED side was getting pregame. The
  stored spread is home-relative, so the away side's value is its negation.
- `claimed`: mean model_probability. `actual`: the rate those sides won.
  `gap` = claimed - actual; POSITIVE means the model is OVERCONFIDENT.
- Wilson interval on `actual`; a bucket is only called wrong when the interval
  excludes the claim.

    python -m scripts.ncaaf_live_dog_calibration --season 2025
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

LANE = "ncaaf_live_win_prob"
# "the backed side was getting more than X points pregame"
DOG_BUCKETS = [(-99, -14), (-14, -7), (-7, 0), (0, 7), (7, 14), (14, 21), (21, 99)]
# current lead of the backed side, in points
LEAD_BUCKETS = [(-99, -14), (-14, -7), (-7, 0), (0, 7), (7, 14), (14, 99)]


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (float("nan"), float("nan"))
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def bucket(v: float, buckets) -> tuple[float, float] | None:
    for lo, hi in buckets:
        if lo <= v < hi:
            return (lo, hi)
    return None


def label(b: tuple[float, float], unit: str = "") -> str:
    lo, hi = b
    if lo <= -99:
        return f"<{hi:+g}{unit}"
    if hi >= 99:
        return f">={lo:+g}{unit}"
    return f"{lo:+g}..{hi:+g}{unit}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--states", default="ncaaf_live/data/artifacts/states_2025.parquet")
    ap.add_argument("--min-n", type=int, default=15)
    args = ap.parse_args()

    import pandas as pd

    cache = Path(tempfile.gettempdir()) / f"ncaaf_inplay_candidates_{args.season}.pkl"
    cands = pickle.loads(cache.read_bytes())
    st = pd.read_parquet(ROOT / args.states, columns=["game_id", "pregame_spread"])
    spread = st.drop_duplicates("game_id").set_index("game_id")["pregame_spread"].to_dict()

    rows = []
    for c in cands:
        if c["model_id"] != LANE or c["points_since_update"] != 0:
            continue
        if c["result"] not in ("WIN", "LOSS"):
            continue
        sp = spread.get(c["game_id"])
        if sp is None or (isinstance(sp, float) and math.isnan(sp)):
            continue
        sp = float(sp)
        dog = sp if c["pick_side"] == "home" else -sp
        # score_diff is home-relative in the state; the candidate carries the
        # finals, and the backed side's CURRENT lead is what a reader means.
        lead_home = None
        rows.append({**c, "dog": dog, "lead_home": lead_home})

    # The candidate does not carry the live score, so recover the backed side's
    # lead from the states parquet by game and served time is unnecessary:
    # `seconds_remaining` + the graded result is enough for the dog table, and
    # the lead table needs the score, which we pull from the full states frame.
    full = pd.read_parquet(ROOT / args.states,
                           columns=["game_id", "wall_ts", "home_score", "away_score",
                                    "period", "seconds_remaining"])
    full = full.sort_values(["game_id", "wall_ts"])
    by_game = {g: d.reset_index(drop=True) for g, d in full.groupby("game_id", sort=False)}

    import numpy as np
    for r in rows:
        g = by_game.get(r["game_id"])
        if g is None:
            r["lead"] = None
            continue
        ts = pd.Timestamp(r["served"])
        if ts.tzinfo is not None and g["wall_ts"].dt.tz is None:
            ts = ts.tz_localize(None)
        idx = int(np.searchsorted(g["wall_ts"].values, ts.to_datetime64(), side="right")) - 1
        if idx < 0:
            r["lead"] = None
            continue
        hs, as_ = float(g["home_score"].iloc[idx]), float(g["away_score"].iloc[idx])
        r["lead"] = (hs - as_) if r["pick_side"] == "home" else (as_ - hs)

    print(f"fresh graded {LANE} candidates with a pregame spread: {len(rows):,}")

    def table(title, keyfn, buckets, unit=""):
        seen: dict = {}
        for r in sorted(rows, key=lambda r: r["served"]):
            v = keyfn(r)
            if v is None:
                continue
            b = bucket(v, buckets)
            if b is None:
                continue
            k = (r["game_id"], b)
            if k in seen:
                continue
            seen[k] = r
        agg = defaultdict(list)
        for (gid, b), r in seen.items():
            agg[b].append(r)
        print(f"\n{title}")
        print(f"  {'bucket':>14} {'n':>5} {'claimed':>8} {'actual':>8} {'gap':>7} "
              f"{'95% CI on actual':>18}  verdict")
        for b in buckets:
            rs = agg.get(b, [])
            if len(rs) < args.min_n:
                continue
            n = len(rs)
            w = sum(1 for r in rs if r["result"] == "WIN")
            claimed = sum(r["model_probability"] for r in rs) / n
            actual = w / n
            lo, hi = wilson(w, n)
            wrong = claimed > hi or claimed < lo
            verdict = ("OVERCONFIDENT" if claimed > hi else
                       "underconfident" if claimed < lo else "ok")
            print(f"  {label(b, unit):>14} {n:>5} {claimed:>8.3f} {actual:>8.3f} "
                  f"{claimed - actual:>+7.3f} [{lo:>6.3f},{hi:>6.3f}]  {verdict}")

    table("A. BY PREGAME STATUS OF THE BACKED SIDE (positive = was getting points)",
          lambda r: r["dog"], DOG_BUCKETS, "pt")
    table("B. BY THE BACKED SIDE'S CURRENT LEAD",
          lambda r: r["lead"], LEAD_BUCKETS, "pt")

    # The cell mike named: a big pregame dog that is now AHEAD.
    print("\nC. THE CASE IN QUESTION: backed side was a >=14-point pregame dog "
          "AND is now ahead")
    seen = {}
    for r in sorted(rows, key=lambda r: r["served"]):
        if r["dog"] < 14 or r["lead"] is None or r["lead"] <= 0:
            continue
        seen.setdefault(r["game_id"], r)
    rs = list(seen.values())
    if rs:
        n = len(rs)
        w = sum(1 for r in rs if r["result"] == "WIN")
        claimed = sum(r["model_probability"] for r in rs) / n
        lo, hi = wilson(w, n)
        print(f"  n={n}  claimed {claimed:.3f}  actual {w / n:.3f}  "
              f"gap {claimed - w / n:+.3f}  95% CI [{lo:.3f}, {hi:.3f}]")
        print(f"  {'OVERCONFIDENT' if claimed > hi else 'not separable at this n'}")
        hi_p = [r for r in rs if r["model_probability"] >= 0.60]
        if hi_p:
            n2 = len(hi_p)
            w2 = sum(1 for r in hi_p if r["result"] == "WIN")
            lo2, hi2 = wilson(w2, n2)
            c2 = sum(r["model_probability"] for r in hi_p) / n2
            print(f"  of those, the ones it claimed >= 0.60: n={n2}  "
                  f"claimed {c2:.3f}  actual {w2 / n2:.3f}  gap {c2 - w2 / n2:+.3f}  "
                  f"CI [{lo2:.3f}, {hi2:.3f}]")
    else:
        print("  no such states in the season")


if __name__ == "__main__":
    main()

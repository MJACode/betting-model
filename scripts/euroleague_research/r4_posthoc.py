"""Round 4, rule P1 (registered after experiment 4, before it was run; section
0.11 of the results file): fade the book's stray from the mechanical halftime
total. Chosen WITH the deviation table in view, so it is labelled after the
fact and counted in Benjamini-Hochberg."""
from __future__ import annotations

import numpy as np
import pandas as pd

import r4_lib as L
import r3_lib as L3
from r4_structure import shares

DS = [1.0, 1.5, 2.0, 3.0]
HEAD = 2.0


def best_p1(Q: pd.DataFrame) -> pd.DataFrame:
    """Per game: the eligible total quote with the largest |dev| at the first read holding one (no D cut)."""
    x = Q[(Q.market == "totals") & Q.wf].merge(shares(), on="season", how="left")
    x = x.assign(mech=x.ht_t + x.prior_t * x.share2)
    x["dev"] = x.line - x.mech
    x["side"] = np.where(x.dev > 0, "under", "over")
    x["price"] = np.where(x.dev > 0, x.pb, x.pa)
    x["other_price"] = np.where(x.dev > 0, x.pa, x.pb)
    x["fav"] = False
    e = x[L.eligible(x)]
    e = e.assign(_r=e.bookmaker.map(L.RANK), _a=e.dev.abs())
    ts = e.groupby("game_id").snapshot_ts.transform("min")
    e = e[e.snapshot_ts == ts].sort_values(["game_id", "_a", "_r"], ascending=[True, False, True], kind="mergesort")
    return e.drop_duplicates("game_id", keep="first").reset_index(drop=True)


def decide_p1(Q: pd.DataFrame, D: float) -> pd.DataFrame:
    best = best_p1(Q)
    return L.grade(best[best._a >= D])


def placebo(best: pd.DataFrame, n: int = 200) -> tuple[np.ndarray, list]:
    """Each game gets another game's decision (side and |dev|) from the same
    season, bet at this game's own quote; same side mix and bet count."""
    rng = np.random.default_rng(20261113)
    rets, nb = [], []
    for _ in range(n):
        perm = best.copy()
        for s, idx in best.groupby("season").groups.items():
            idx = np.asarray(idx)
            donor = rng.permutation(idx)
            perm.loc[idx, "side"] = best.loc[donor, "side"].to_numpy()
            perm.loc[idx, "_a"] = best.loc[donor, "_a"].to_numpy()
        perm["price"] = np.where(perm.side == "under", perm.pb, perm.pa)
        perm["other_price"] = np.where(perm.side == "under", perm.pa, perm.pb)
        pb = L.grade(perm[(perm._a >= HEAD) & perm.price.between(*L.PRICE_BAND)])
        nb.append(len(pb))
        rets.append(100 * pb.units.sum() / pb.risk.sum() if len(pb) and pb.risk.sum() > 0 else np.nan)
    return np.array(rets), nb


def run() -> str:
    P = L._C.get("P")
    if P is None:
        P = L.priced_wf()
    out = []
    rows = []
    for D in DS:
        b = decide_p1(P, D)
        r = L.reg("P1 after-the-fact: fade the stray from the mechanical total", f"D {D}", b)
        rows.append({"D": D, **{k: r[k] for k in ("bets", "W", "L", "P", "units", "ret%", "lo%", "hi%")}})
        for s, xs in b.groupby("season"):
            rr = L.row({}, xs)
            rows.append({"D": f"{D} {L.SEASON_NAME[s]}", **{k: rr[k] for k in ("bets", "W", "L", "P", "units", "ret%", "lo%", "hi%")}})
    out.append("### P1 (after the fact): fade the book's stray from the mechanical halftime total, walk-forward\n\n"
               + L.md(rows))
    b = decide_p1(P, HEAD)
    kr = L3.kill_rows(f"P1 D {HEAD}", b, side_cols=("side", "bookmaker"), fav_col=None)
    for r in kr:
        r.pop("p_one", None)
    out.append(f"### P1 at D = {HEAD}: the kill-test splits\n\nPrice range: {L.price_range(b)}.\n\n" + L.md(kr))
    rets, nb = placebo(best_p1(P))
    real = 100 * b.units.sum() / b.risk.sum()
    out.append(f"Placebo for P1 at D = {HEAD} (200 draws: each game gets another game's side and stray size from the "
               f"same season, bet at its own quote): mean {np.nanmean(rets):+.2f}%, 5th-95th percentile "
               f"{np.nanpercentile(rets, 5):+.2f}% to {np.nanpercentile(rets, 95):+.2f}% (median {int(np.median(nb))} "
               f"bets); real {real:+.2f}% on {len(b)}; share of draws at or above the real result "
               f"{100 * np.nanmean(rets >= real):.1f}%.")
    return "\n\n".join(out)


if __name__ == "__main__":
    print(run())

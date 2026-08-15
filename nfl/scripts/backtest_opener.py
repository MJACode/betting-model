#!/usr/bin/env python3
"""
Opener sharp-vs-soft backtest, priced at what the books actually quoted.

    python scripts/backtest_opener.py
    python scripts/backtest_opener.py --variant per_book --placebo draftkings

Rule: in the T-7 to T-2 window, wherever a soft book and Pinnacle both have a
live spread, define dev = soft_line - pinnacle_line and bet the side Pinnacle
favours, at the soft book's number. One bet per game.

Three things this script does that the original analysis did not:

  1. Selects at the FIRST qualifying moment, not the largest deviation in the
     window. The latter needs to know which snapshot will turn out most
     extreme, which is a look-ahead. (It turns out not to matter much, but it
     is not implementable.)

  2. Benchmarks ATS against the cover probability implied by the line advantage
     ALONE, computed from the empirical margin-versus-close residual
     distribution. Beating 50% is not the bar. Beating the number you bought is.

  3. Prices bets at the actual quoted juice. Books charge for a better line:
     the mean price on selected bets is about -124, not -110. This is the
     difference between a settled edge and one whose interval touches zero.

Zero Odds API credits: everything comes from the snapshot cache.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RNG = np.random.default_rng(20260815)
DEFECTIVE_BOOKS = {"betanysports", "betsson", "nordicbet", "tipico_de"}
DEV_LONG = "data/processed/dev_long.parquet"


def residuals() -> np.ndarray:
    g = pd.read_csv("data/games.csv")
    g = g[g.season.between(1999, 2025) & g.result.notna() & g.spread_line.notna()]
    return (g.result - g.spread_line).values


RESID = None


def exp_win(adv: np.ndarray) -> np.ndarray:
    """P(cover) from the line advantage alone, empirical, with key-number atoms."""
    e = RESID[None, :] + adv[:, None]
    return (e > 0).mean(1) + 0.5 * (e == 0).mean(1)


def boot(d: pd.DataFrame, col: str, b: int = 4000) -> tuple[float, float]:
    gs = d.game_id.unique()
    grp = {g: d.loc[d.game_id == g, col].values for g in gs}
    s = [np.concatenate([grp[g] for g in RNG.choice(gs, len(gs), True)]).mean() for _ in range(b)]
    return tuple(np.percentile(s, [2.5, 97.5]))


def load(reference: str, lo: float, hi: float, seasons) -> pd.DataFrame:
    if not os.path.exists(DEV_LONG):
        raise SystemExit(f"{DEV_LONG} missing. Run scripts/screen_books.py --rebuild first.")
    m = pd.read_parquet(DEV_LONG)
    ref = (m[m.book == reference].groupby(["snap_ts", "game_id"], as_index=False)
           .point.median().rename(columns={"point": "ref"}))
    w = m[m.lead_h.between(lo, hi) & (~m.book.isin(DEFECTIVE_BOOKS))
          & (m.book != reference) & m.season.between(*seasons) & m.result.notna()]
    w = w.merge(ref, on=["snap_ts", "game_id"], how="inner").copy()
    w["dev"] = w.point - w.ref
    w["adev"] = w.dev.abs()
    w["bet_home"] = w.dev > 0
    edge = w.result.values + w.point.values
    s = np.where(w.bet_home, edge, -edge)
    w["win"] = np.select([s > 0, s == 0], [1.0, 0.5], 0.0)

    close = (m[m.lead_h.between(0, 6) & (m.book == "pinnacle")]
             .groupby("game_id").point.median().rename("close_pt"))
    w = w.merge(close, on="game_id", how="left")
    w["close_pt"] = w.close_pt.fillna(-w.spread_line)
    w["clv"] = np.where(w.bet_home, w.point - w.close_pt, w.close_pt - w.point)
    return w


def price(w: pd.DataFrame) -> pd.DataFrame:
    """Actual quoted price on the side taken. Both sides, or the ROI is biased."""
    if not {"px_home", "px_away"} <= set(w.columns):
        raise SystemExit(
            "dev_long.parquet predates the both-sides price fix. "
            "Rerun: python scripts/screen_books.py --rebuild")
    w = w.copy()
    w["px"] = np.where(w.bet_home, w.px_home, w.px_away)
    return w


def report(w: pd.DataFrame, variant: str, thresholds) -> pd.DataFrame:
    rows = []
    for t in thresholds:
        q = w[w.adev >= t]
        if variant == "first":
            s = (q.sort_values(["game_id", "snap_ts", "adev"], ascending=[True, True, False])
                 .groupby("game_id", as_index=False).first())
        elif variant == "maxdev":
            s = q.sort_values("adev").groupby("game_id", as_index=False).last()
        else:
            s = (q.sort_values(["game_id", "book", "snap_ts"])
                 .groupby(["game_id", "book"], as_index=False).first())
        s = s.copy()
        s["exp"] = exp_win(s.clv.values)
        d = s[s.win != 0.5].reset_index(drop=True)
        if len(d) < 10:
            continue
        d["excess"] = d.win - d["exp"]
        lo, hi = boot(d, "excess")
        wr = d.win.mean()
        row = dict(thr=t, n=len(d), games=s.game_id.nunique(), mean_clv=round(s.clv.mean(), 2),
                   ats=round(wr * 100, 2), exp_from_line=round(d["exp"].mean() * 100, 2),
                   excess=round(d.excess.mean() * 100, 2),
                   excess_ci=f"[{lo*100:+.1f},{hi*100:+.1f}]",
                   roi110=round((wr * (100 / 110) - (1 - wr)) * 100, 2))
        if "px" in d and d.px.notna().any():
            p = d[d.px.notna()].copy()
            p["ret"] = np.where(p.win == 1, np.where(p.px > 0, p.px / 100, 100 / -p.px), -1.0)
            rlo, rhi = boot(p, "ret")
            row.update(median_px=int(p.px.median()), mean_px=round(p.px.mean(), 1),
                       roi_actual=round(p.ret.mean() * 100, 2),
                       roi_ci=f"[{rlo*100:+.1f},{rhi*100:+.1f}]")
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    global RESID
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["first", "maxdev", "per_book"], default="first")
    ap.add_argument("--reference", default="pinnacle")
    ap.add_argument("--placebo", default=None, help="rerun with this book as the reference")
    ap.add_argument("--lead-lo", type=float, default=48.0)
    ap.add_argument("--lead-hi", type=float, default=168.0)
    ap.add_argument("--seasons", type=int, nargs=2, default=[2023, 2025])
    a = ap.parse_args()

    RESID = residuals()
    print(f"margin-vs-close residuals: n={len(RESID)} mean={RESID.mean():+.3f} sd={RESID.std():.2f}")

    w = price(load(a.reference, a.lead_lo, a.lead_hi, a.seasons))
    print(f"\n=== reference={a.reference}, variant={a.variant}, "
          f"seasons {a.seasons[0]}-{a.seasons[1]}, {w.game_id.nunique()} games, "
          f"{w.book.nunique()} clean books ===")
    print(report(w, a.variant, (0.5, 1.0, 1.5, 2.0)).to_string(index=False))

    if a.placebo:
        p = price(load(a.placebo, a.lead_lo, a.lead_hi, a.seasons))
        print(f"\n=== PLACEBO: reference={a.placebo} (expect no excess) ===")
        print(report(p, a.variant, (0.5, 1.0, 1.5, 2.0)).to_string(index=False))

    print("\nRead the `excess` column, not `ats` and not `mean_clv`. CLV here is close to "
          "mechanical, and ATS is mostly the value of the number you bought.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

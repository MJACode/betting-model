#!/usr/bin/env python3
"""
Opener sharp-vs-soft backtest, priced at what the books actually quoted.

    python scripts/backtest_opener.py                          # spreads
    python scripts/backtest_opener.py --market totals
    python scripts/backtest_opener.py --market h2h
    python scripts/backtest_opener.py --market all --placebo draftkings

Rule: in the T-7 to T-2 window, wherever a soft book and Pinnacle both have a
live number, bet the side Pinnacle favours, at the soft book's number. One bet
per game.

Three things this script does that the original analysis did not:

  1. Selects at the FIRST qualifying moment, not the largest deviation in the
     window. The latter needs to know which snapshot will turn out most
     extreme, which is a look-ahead. (It turns out not to matter much, but it
     is not implementable.)

  2. Benchmarks against the win probability implied by the number bought
     ALONE, computed from the empirical outcome-versus-close residual
     distribution. Beating 50% is not the bar. Beating the number you bought is.

  3. Prices bets at the actual quoted juice. Books charge for a better line:
     the mean price on selected bets is about -124, not -110. This is the
     difference between a settled edge and one whose interval touches zero.

THREE MARKETS, THREE DIFFERENT SIGNALS
--------------------------------------
spreads  dev = soft handicap - pinnacle handicap, in points. Bet the side
         Pinnacle favours. Win on the number bought.
totals   dev = soft total - pinnacle total, in points. A soft book hanging a
         HIGHER total than Pinnacle is selling a cheap under, so the sign
         flips relative to spreads: dev > 0 means bet the UNDER.
h2h      A moneyline has no handicap, so there is nothing to difference in
         points. The signal is in probability: dev = soft de-vigged P(home) -
         pinnacle de-vigged P(home), and the benchmark is Pinnacle's closing
         probability rather than a residual distribution. De-vig is POWER, not
         multiplicative: proportional de-vig is badly wrong wherever the
         favourite-longshot bias bites, and on a moneyline it bites hard.

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

# Deviation thresholds are in points for the handicap markets and in
# probability for the moneyline. A 2-point spread deviation and a 2-point
# probability deviation are not remotely the same bet.
MARKETS = {
    "spreads": dict(thresholds=(0.5, 1.0, 1.5, 2.0), unit="pts"),
    "totals": dict(thresholds=(0.5, 1.0, 1.5, 2.0), unit="pts"),
    "h2h": dict(thresholds=(0.01, 0.02, 0.03, 0.05), unit="prob"),
}

RESID: dict[str, np.ndarray] = {}


def residuals() -> dict[str, np.ndarray]:
    g = pd.read_csv("data/games.csv")
    g = g[g.season.between(1999, 2025)]
    s = g[g.result.notna() & g.spread_line.notna()]
    t = g[g.total.notna() & g.total_line.notna()]
    return {"spreads": (s.result - s.spread_line).values,
            "totals": (t.total - t.total_line).values}


def exp_win(adv: np.ndarray, market: str, positive: np.ndarray) -> np.ndarray:
    """
    P(win) from the number bought alone, empirical, with key-number atoms.

    `positive` marks the side that wins when the residual is LARGE: the home
    side for spreads, the Over for totals. The distinction matters because the
    residual is not centred on zero. The margin residual is nearly symmetric
    (mean +0.09) so it barely moved the spread numbers, but the total residual
    has mean +0.70 - overs land above the closing total more often than unders
    land below it - and scoring an under with the over's formula quietly
    credits it with about 1.5pp of win probability it does not have.
    """
    r = RESID[market]
    pos = np.asarray(positive, dtype=bool)[:, None]
    e = np.where(pos, r[None, :] + adv[:, None], adv[:, None] - r[None, :])
    return (e > 0).mean(1) + 0.5 * (e == 0).mean(1)


def boot(d: pd.DataFrame, col: str, b: int = 4000) -> tuple[float, float]:
    gs = d.game_id.unique()
    grp = {g: d.loc[d.game_id == g, col].values for g in gs}
    s = [np.concatenate([grp[g] for g in RNG.choice(gs, len(gs), True)]).mean() for _ in range(b)]
    return tuple(np.percentile(s, [2.5, 97.5]))


def load(market: str, reference: str, lo: float, hi: float, seasons) -> pd.DataFrame:
    if not os.path.exists(DEV_LONG):
        raise SystemExit(f"{DEV_LONG} missing. Run scripts/screen_books.py --rebuild first.")
    m = pd.read_parquet(DEV_LONG)
    if "market" not in m.columns:
        raise SystemExit("dev_long.parquet predates the multi-market rebuild. "
                         "Rerun: python scripts/screen_books.py --rebuild")
    m = m[m.market == market]
    if m.empty:
        raise SystemExit(
            f"no {market} rows in the snapshot cache. The opener scan has only ever "
            f"pulled spreads; run:\n"
            f"    python scripts/scan_opener_window.py --markets {market} 2024 2025")

    sig = "point" if market != "h2h" else "p_home"
    ref = (m[m.book == reference].groupby(["snap_ts", "game_id"], as_index=False)[sig]
           .median().rename(columns={sig: "ref"}))
    w = m[m.lead_h.between(lo, hi) & (~m.book.isin(DEFECTIVE_BOOKS))
          & (m.book != reference) & m.season.between(*seasons)]
    w = w.dropna(subset=[sig])
    w = w.merge(ref, on=["snap_ts", "game_id"], how="inner").copy()
    w["dev"] = w[sig] - w.ref
    w["adev"] = w.dev.abs()

    close = (m[m.lead_h.between(0, 6) & (m.book == reference)]
             .groupby("game_id")[sig].median().rename("close_pt"))
    w = w.merge(close, on="game_id", how="left")

    if market == "spreads":
        w = w[w.result.notna()]
        # point is the HOME handicap: a bigger number means more points for home.
        w["bet_home"] = w.dev > 0
        edge = w.result.values + w.point.values
        s = np.where(w.bet_home, edge, -edge)
        w["win"] = np.select([s > 0, s == 0], [1.0, 0.5], 0.0)
        w["close_pt"] = w.close_pt.fillna(-w.spread_line)
        w["clv"] = np.where(w.bet_home, w.point - w.close_pt, w.close_pt - w.point)
        w["side"] = np.where(w.bet_home, "home", "away")
    elif market == "totals":
        w = w[w.total.notna()]
        # A soft book hanging a HIGHER total than Pinnacle sells a cheap under.
        w["bet_over"] = w.dev < 0
        edge = w.total.values - w.point.values          # >0 means the over cashed
        s = np.where(w.bet_over, edge, -edge)
        w["win"] = np.select([s > 0, s == 0], [1.0, 0.5], 0.0)
        w["close_pt"] = w.close_pt.fillna(w.total_line)
        w["clv"] = np.where(w.bet_over, w.close_pt - w.point, w.point - w.close_pt)
        w["side"] = np.where(w.bet_over, "over", "under")
    else:
        w = w[w.result.notna()]
        # Soft rates home BELOW Pinnacle -> the home price is too long -> bet home.
        w["bet_home"] = w.dev < 0
        home_won = np.select([w.result.values > 0, w.result.values == 0], [1.0, 0.5], 0.0)
        w["win"] = np.where(w.bet_home, home_won, 1.0 - home_won)
        # "CLV" for a moneyline is a probability advantage, not points: how much
        # cheaper the price bought was than the same side at the close.
        w = w[w.close_pt.notna()]
        w["clv"] = np.where(w.bet_home, w.close_pt - w.p_home,
                            (1 - w.close_pt) - (1 - w.p_home))
        w["side"] = np.where(w.bet_home, "home", "away")
    return w


def price(w: pd.DataFrame, market: str) -> pd.DataFrame:
    """Actual quoted price on the side taken. Both sides, or the ROI is biased."""
    if not {"px_home", "px_away"} <= set(w.columns):
        raise SystemExit(
            "dev_long.parquet predates the both-sides price fix. "
            "Rerun: python scripts/screen_books.py --rebuild")
    w = w.copy()
    take_first = w.bet_over if market == "totals" else w.bet_home
    w["px"] = np.where(take_first, w.px_home, w.px_away)
    return w


def report(w: pd.DataFrame, market: str, variant: str, thresholds) -> pd.DataFrame:
    rows = []
    for t in thresholds:
        q = w[w.adev >= t]
        # `book` is a tie-break, not a preference. Without it, two books quoting
        # the same deviation at the same snapshot are separated by whatever order
        # the rows happened to arrive in, so the selected bet changed when totals
        # were added to dev_long and nothing about the spread data moved at all.
        # Any deterministic rule will do; this one is reproducible.
        if variant == "first":
            s = (q.sort_values(["game_id", "snap_ts", "adev", "book"],
                               ascending=[True, True, False, True])
                 .groupby("game_id", as_index=False).first())
        elif variant == "maxdev":
            s = (q.sort_values(["game_id", "adev", "snap_ts", "book"])
                 .groupby("game_id", as_index=False).last())
        else:
            s = (q.sort_values(["game_id", "book", "snap_ts", "adev"],
                               ascending=[True, True, True, False])
                 .groupby(["game_id", "book"], as_index=False).first())
        s = s.copy()
        # The benchmark differs by market. For the handicap markets it is the
        # win probability the bought number implies on its own. For a moneyline
        # there is no number to imply anything, so the benchmark is the sharp
        # book's closing probability on the same side.
        if market == "h2h":
            s["exp"] = np.where(s.bet_home, s.close_pt, 1 - s.close_pt)
        else:
            pos = s.bet_over.values if market == "totals" else s.bet_home.values
            s["exp"] = exp_win(s.clv.values, market, pos)
        d = s[s.win != 0.5].reset_index(drop=True)
        if len(d) < 10:
            continue
        d["excess"] = d.win - d["exp"]
        lo, hi = boot(d, "excess")
        wr = d.win.mean()
        row = dict(thr=t, n=len(d), games=s.game_id.nunique(), mean_clv=round(s.clv.mean(), 3),
                   win_rate=round(wr * 100, 2), exp_from_line=round(d["exp"].mean() * 100, 2),
                   excess=round(d.excess.mean() * 100, 2),
                   excess_ci=f"[{lo*100:+.1f},{hi*100:+.1f}]",
                   roi110=round((wr * (100 / 110) - (1 - wr)) * 100, 2))
        if "px" in d and d.px.notna().any():
            p = d[d.px.notna()].copy()
            p["ret"] = np.where(p.win == 1, np.where(p.px > 0, p.px / 100, 100 / -p.px), -1.0)
            rlo, rhi = boot(p, "ret")
            # Averaging American odds across favourites and dogs is meaningless:
            # +150 and -400 average to -125, which is not a price anyone quoted.
            # Fine where quotes cluster near -110, nonsense on a moneyline, so
            # h2h reports mean DECIMAL odds instead.
            dec = np.where(p.px > 0, 1 + p.px / 100, 1 + 100 / -p.px)
            row.update(median_px=int(p.px.median()), mean_dec=round(float(dec.mean()), 3),
                       roi_actual=round(p.ret.mean() * 100, 2),
                       roi_ci=f"[{rlo*100:+.1f},{rhi*100:+.1f}]")
            if market != "h2h":
                row["mean_px"] = round(p.px.mean(), 1)
        rows.append(row)
    return pd.DataFrame(rows)


def by_season(w: pd.DataFrame, market: str, variant: str, thr: float) -> pd.DataFrame:
    """
    Season-by-season at one threshold. This project has been burned by a single
    season carrying a finding - the spread edge is roughly 70% one season - so
    the split is not optional reading.
    """
    q = w[w.adev >= thr]
    if variant == "first":
        s = (q.sort_values(["game_id", "snap_ts", "adev", "book"],
                           ascending=[True, True, False, True])
             .groupby("game_id", as_index=False).first())
    else:
        s = (q.sort_values(["game_id", "book", "snap_ts", "adev"],
                           ascending=[True, True, True, False])
             .groupby(["game_id", "book"], as_index=False).first())
    s = s.copy()
    if market == "h2h":
        s["exp"] = np.where(s.bet_home, s.close_pt, 1 - s.close_pt)
    else:
        pos = s.bet_over.values if market == "totals" else s.bet_home.values
        s["exp"] = exp_win(s.clv.values, market, pos)
    s["ret"] = np.where(s.win == 1, np.where(s.px > 0, s.px / 100, 100 / -s.px),
                        np.where(s.win == 0.5, 0.0, -1.0))
    rows = []
    for ssn, g in s.groupby("season"):
        d = g[g.win != 0.5]
        if not len(d):
            continue
        rows.append(dict(season=int(ssn), n=len(d), win_rate=round(d.win.mean() * 100, 2),
                         excess=round((d.win - d["exp"]).mean() * 100, 2),
                         units=round(g.ret.sum(), 2),
                         roi_actual=round(g.ret.mean() * 100, 2)))
    return pd.DataFrame(rows)


def run_market(market: str, a) -> None:
    cfg = MARKETS[market]
    try:
        w = price(load(market, a.reference, a.lead_lo, a.lead_hi, a.seasons), market)
    except SystemExit as exc:
        print(f"\n=== {market.upper()}: SKIPPED ===\n{exc}")
        return
    if w.empty:
        print(f"\n=== {market.upper()}: no rows in the window ===")
        return
    print(f"\n=== {market.upper()}  reference={a.reference}, variant={a.variant}, "
          f"seasons {a.seasons[0]}-{a.seasons[1]}, {w.game_id.nunique()} games, "
          f"{w.book.nunique()} clean books, threshold in {cfg['unit']} ===")
    r = report(w, market, a.variant, cfg["thresholds"])
    print(r.to_string(index=False) if len(r) else "  no threshold retained 10+ decided bets")

    if a.by_season:
        t = by_season(w, market, a.variant, a.season_thr)
        print(f"\n--- {market.upper()} by season at threshold {a.season_thr} ---")
        print(t.to_string(index=False) if len(t) else "  nothing to split")

    if a.placebo:
        try:
            p = price(load(market, a.placebo, a.lead_lo, a.lead_hi, a.seasons), market)
        except SystemExit as exc:
            print(f"  placebo skipped: {exc}")
            return
        print(f"\n--- {market.upper()} PLACEBO: reference={a.placebo} (expect no excess) ---")
        pr = report(p, market, a.variant, cfg["thresholds"])
        print(pr.to_string(index=False) if len(pr) else "  insufficient placebo bets")


def main() -> int:
    global RESID
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["spreads", "totals", "h2h", "all"], default="spreads")
    ap.add_argument("--variant", choices=["first", "maxdev", "per_book"], default="first")
    ap.add_argument("--reference", default="pinnacle")
    ap.add_argument("--placebo", default=None, help="rerun with this book as the reference")
    ap.add_argument("--lead-lo", type=float, default=48.0)
    ap.add_argument("--lead-hi", type=float, default=168.0)
    ap.add_argument("--seasons", type=int, nargs=2, default=[2023, 2025])
    ap.add_argument("--by-season", action="store_true",
                    help="split one threshold by season; a single season carrying "
                         "the whole result is the standing failure mode here")
    ap.add_argument("--season-thr", type=float, default=1.0)
    a = ap.parse_args()

    RESID = residuals()
    print(f"margin-vs-close residuals: n={len(RESID['spreads'])} "
          f"mean={RESID['spreads'].mean():+.3f} sd={RESID['spreads'].std():.2f}")
    print(f"total-vs-close residuals:  n={len(RESID['totals'])} "
          f"mean={RESID['totals'].mean():+.3f} sd={RESID['totals'].std():.2f}")

    for mk in (["spreads", "totals", "h2h"] if a.market == "all" else [a.market]):
        run_market(mk, a)

    print("\nRead the `excess` column, not `win_rate` and not `mean_clv`. CLV here is "
          "close to mechanical, and the win rate is mostly the value of the number "
          "bought. For h2h, `excess` is measured against Pinnacle's closing "
          "probability, which is a harder benchmark than the other two.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Market-anchored SHAPE simulation against the DraftKings alternate ladder.

    python -m scripts.nfl_prop_shape_sim --market player_reception_yds
    python -m scripts.nfl_prop_shape_sim --market player_rush_yds --draws 20000

THE EXPERIMENT (docs/nfl_prop_method_search.md §3-4, pre-registered; mike
2026-09-11: "1 and 2"). The information test says our projections add nothing
to the line's MIDDLE. This does not touch the middle. Per proposition:

  1. ANCHOR. The sharp main line L and its de-vigged P(over L) = p_L
     (Pinnacle, else betonlineag, else DraftKings' own two-way main). The
     simulated distribution is forced to satisfy P(X > L) = p_L exactly.
  2. SHAPE, from the player's own usage, not from the stat. Trailing games
     strictly before this one (up to 16, at least 6):
       touches  ~ negative binomial (targets for receiving, carries for
                  rushing), moments from the trailing window;
       catches  ~ Binomial(touches, catch rate)   [receiving only]
       yards    = sum over catches of log-normal per-touch yards, the player's
                  own mean per touch and a per-touch variance pooled from the
                  PRIOR season (game logs carry totals, not per-touch yards, so
                  the variance is recovered by decomposition: Var(Y) =
                  E[c]·Var(per) + Var(c)·mean(per)²).
     `--draws` games are simulated; a single multiplier on yards is then
     solved so P(a·X > L) = p_L. The zero mass (no catches) is untouched by the
     multiplier, so the anchor keeps the player's chance of a blank game.
  3. LADDER. P_sim(a·X > s) at every DraftKings alternate strike s, against the
     ladder's fair price (the over price's implied probability scaled by the
     main line's two-way de-vig factor, the same reading as
     scripts/nfl_prop_ladder_calibration.py). The ladder is OVER-ONLY, so the
     only bet is an over; edge = P_sim − fair. ONE bet per proposition: the
     strike with the largest edge above the cut.
  4. PLACEBO. Same anchor, same ladder, same grading, but the shape is a
     POOLED zero-inflated gamma for the market fitted on the prior season --
     no player in it. If the placebo grades the same, the edge is the ladder,
     not the player's shape (the 2024 DK error of profitability_search §7c).

Walk-forward: pooled parameters (per-touch variance, placebo gamma) come from
the season BEFORE the one graded, never the same season. Per-player windows
are strictly past games. Nothing is tuned on the graded rows.

THE BARS, fixed before the first run (method memo §4): positive in each graded
season; 90% CI on ROI excluding zero at a cut with ≥ 200 bets and both
neighbouring cuts positive; the placebo does NOT reproduce it; direction bar
is moot on an over-only ladder and is stated as such; CLV is not measurable
(no closing ladder is held) and is stated as such.

Zero credits. Everything is in data/local.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from scipy import stats as sps

from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name
from models.market_relative import devig, implied

MARKETS = {
    # market: (touch column, catch column or None, yards column, alt market)
    "player_reception_yds": ("targets", "receptions", "receiving_yards",
                             "player_reception_yds_alternate"),
    "player_rush_yds": ("carries", None, "rushing_yards", "player_rush_yds_alternate"),
}
ANCHOR_BOOKS = ("pinnacle", "betonlineag", "draftkings")
WINDOW = 16
MIN_GAMES = 6
MAX_CATCHES = 40


def profit(price: float, won: bool) -> float:
    return (price / 100.0 if price > 0 else 100.0 / abs(price)) if won else -1.0


# ── data ────────────────────────────────────────────────────────────────────

def load_odds() -> pd.DataFrame:
    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    odds = odds[(odds.snapshot_type == "open")
                & (~odds.game_id.astype(str).str.startswith("NFL_2026"))].copy()
    ko = (local_store.read_table("nfl_team_game_stats", columns=["game_id", "commence_time"])
          .dropna(subset=["commence_time"]).drop_duplicates("game_id"))
    ko["kick"] = pd.to_datetime(ko.commence_time, utc=True)
    odds = odds.merge(ko[["game_id", "kick"]], on="game_id", how="inner")
    odds["ts"] = pd.to_datetime(odds.snapshot_at, utc=True, format="mixed")
    odds = odds[odds.ts <= odds.kick].copy()
    odds["norm"] = odds.player_name.map(norm_player_name)
    return odds


def latest(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return df.sort_values("ts").groupby(keys, as_index=False).last()


def pooled_params(log: pd.DataFrame, season: int, touch: str, catch: str | None,
                  yards: str, population: set | None = None) -> dict:
    """Prior-season pooled per-touch variance and placebo gamma.

    `population` restricts the pool to players who carried a line in this
    market that season. Without it the zero mass is ~76% (every roster row
    that never saw a target -- linemen, backups, QBs on a receiving market)
    and the placebo anchor is unreachable for every real proposition, which is
    exactly what the first run produced: a placebo with zero bets.
    """
    g = log[log.season == season]
    if population:
        g = g[g.norm_name.isin(population)]
    c = g[catch if catch else touch].fillna(0).astype(float)
    y = g[yards].fillna(0).astype(float)
    played = g[c > 0]
    cc = played[catch if catch else touch].astype(float)
    yy = played[yards].astype(float)
    per_mean = float(yy.sum() / max(cc.sum(), 1.0))
    var_y, var_c, ec = float(yy.var()), float(cc.var()), float(cc.mean())
    var_per = (var_y - var_c * per_mean ** 2) / max(ec, 1e-6)
    cv = float(np.sqrt(max(var_per, 1e-6)) / max(per_mean, 1e-6))
    cv = float(np.clip(cv, 0.3, 2.0))
    pos = yy[yy > 0]
    k = float(pos.mean() ** 2 / max(pos.var(), 1e-6))          # gamma shape, MoM
    return dict(per_cv=cv, gamma_k=float(np.clip(k, 0.3, 10.0)),
                p_zero=float((y <= 0).mean()))


# ── the simulation ──────────────────────────────────────────────────────────

def simulate(hist: pd.DataFrame, touch: str, catch: str | None, yards: str,
             per_cv: float, draws: int, rng: np.random.Generator) -> np.ndarray | None:
    t = hist[touch].fillna(0).astype(float).values
    if len(t) < MIN_GAMES or t.mean() <= 0:
        return None
    m, v = t.mean(), max(t.var(ddof=1), 1e-6)
    if v > m:                                                  # negative binomial
        r = m * m / (v - m)
        n = rng.negative_binomial(r, r / (r + m), size=draws)
    else:
        n = rng.poisson(m, size=draws)
    if catch:
        c_hist = hist[catch].fillna(0).astype(float).values
        q = float(np.clip(c_hist.sum() / max(t.sum(), 1.0), 0.05, 0.98))
        c = rng.binomial(n, q)
        per_mean = float(hist[yards].fillna(0).sum() / max(c_hist.sum(), 1.0))
    else:
        c = n
        per_mean = float(hist[yards].fillna(0).sum() / max(t.sum(), 1.0))
    if per_mean <= 0:
        return None
    c = np.minimum(c, MAX_CATCHES)
    sigma2 = np.log(1.0 + per_cv ** 2)
    mu = np.log(per_mean) - sigma2 / 2.0
    per = rng.lognormal(mu, np.sqrt(sigma2), size=(draws, MAX_CATCHES))
    cum = np.concatenate([np.zeros((draws, 1)), np.cumsum(per, axis=1)], axis=1)
    return cum[np.arange(draws), c]


def player_gamma(hist: pd.DataFrame, yards: str, pooled_k: float) -> tuple[float, float] | None:
    """(shape k, zero mass) of a zero-inflated gamma on the player's own game totals.

    The plainer arm: no usage decomposition, just the dispersion of this
    player's recent games. Shape is shrunk halfway to the pooled prior when
    fewer than 12 positive games are available, because a 2-parameter fit on
    six games is noise."""
    y = hist[yards].fillna(0).astype(float).values
    if len(y) < MIN_GAMES:
        return None
    p0 = float((y <= 0).mean())
    pos = y[y > 0]
    if len(pos) < 3 or pos.var() <= 0:
        return None
    k = float(pos.mean() ** 2 / pos.var())
    if len(pos) < 12:
        k = 0.5 * (k + pooled_k)
    return float(np.clip(k, 0.2, 20.0)), min(p0, 0.9)


def anchor_scale(x: np.ndarray, line: float, p_line: float) -> float | None:
    """Multiplier a with mean(a*x > line) == p_line, by bisection; None if unreachable."""
    p_nonzero = float((x > 0).mean())
    if p_line >= p_nonzero or p_line <= 0.0:
        return None
    lo, hi = 0.05, 20.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if float((mid * x > line).mean()) < p_line:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def placebo_sf(k: float, p_zero: float, line: float, p_line: float, strikes) -> list[float] | None:
    """Pooled zero-inflated gamma, scale solved so P(X > line) == p_line."""
    if p_line >= 1.0 - p_zero or p_line <= 0:
        return None
    target = p_line / (1.0 - p_zero)
    # gamma sf(line; k, scale) == target  ->  scale by bisection
    lo, hi = 1e-3, 1e4
    for _ in range(80):
        mid = np.sqrt(lo * hi)
        if sps.gamma.sf(line, a=k, scale=mid) < target:
            lo = mid
        else:
            hi = mid
    scale = np.sqrt(lo * hi)
    return [float((1.0 - p_zero) * sps.gamma.sf(s, a=k, scale=scale)) for s in strikes]


# ── the run ─────────────────────────────────────────────────────────────────

def run(market: str, draws: int, seed: int) -> pd.DataFrame:
    touch, catch, yards, alt_market = MARKETS[market]
    rng = np.random.default_rng(seed)
    odds = load_odds()
    log = local_store.read_table("nfl_player_game_log")
    log["gdate"] = pd.to_datetime(log.game_date)
    by_player = {n: g.sort_values("gdate") for n, g in log.groupby("norm_name")}
    actual = {(r.norm_name, r.game_id): float(getattr(r, yards) or 0.0)
              for r in log.itertuples(index=False)}
    gdate = {r.game_id: r.gdate for r in log.drop_duplicates("game_id").itertuples(index=False)}

    mains = {b: latest(odds[(odds.bookmaker == b) & (odds.market == market)],
                       ["game_id", "norm"]).set_index(["game_id", "norm"])
             for b in ANCHOR_BOOKS}
    dk_main = mains["draftkings"]
    alt = odds[(odds.bookmaker == "draftkings") & (odds.market == alt_market)].copy()
    alt_last = alt.groupby(["game_id", "norm"]).ts.transform("max")
    alt = alt[alt.ts == alt_last]
    ladders = {k: g for k, g in alt.groupby(["game_id", "norm"], sort=False)}

    lined = {s: set(odds[(odds.market == market) & (odds.season == s)].norm) for s in (2022, 2023, 2024)}
    pooled = {s: pooled_params(log, s - 1, touch, catch, yards, lined.get(s - 1) or None)
              for s in (2023, 2024, 2025)}
    print(f"pooled prior-season params: {pooled}")

    rows, skipped = [], defaultdict(int)
    for (gid, norm), lad in ladders.items():
        season = int(str(gid).split("_")[1])
        if season not in pooled:
            continue
        # anchor
        anc = None
        for b in ANCHOR_BOOKS:
            if (gid, norm) in mains[b].index:
                q = mains[b].loc[(gid, norm)]
                fo, _ = devig(q.over_price, q.under_price)
                if fo is not None and np.isfinite(float(q.line)):
                    anc = (b, float(q.line), float(fo))
                    break
        if anc is None:
            skipped["no_anchor"] += 1
            continue
        if (gid, norm) not in dk_main.index:
            skipped["no_dk_main"] += 1
            continue
        dkq = dk_main.loc[(gid, norm)]
        dk_fo, _ = devig(dkq.over_price, dkq.under_price)
        dk_imp = implied(dkq.over_price)
        if dk_fo is None or not dk_imp:
            skipped["dk_main_oneway"] += 1
            continue
        vig_factor = dk_fo / dk_imp
        act = actual.get((norm, gid))
        if act is None:
            skipped["no_actual"] += 1
            continue
        gd = gdate.get(gid)
        hist = by_player.get(norm)
        if hist is None or gd is None:
            skipped["no_history"] += 1
            continue
        hist = hist[hist.gdate < gd].tail(WINDOW)
        x = simulate(hist, touch, catch, yards, pooled[season]["per_cv"], draws, rng)
        if x is None:
            skipped["thin_history"] += 1
            continue
        book, line, p_line = anc
        a = anchor_scale(x, line, p_line)
        if a is None:
            skipped["anchor_unreachable"] += 1
            continue
        xs = a * x
        strikes = sorted(float(s) for s in lad.line.unique() if np.isfinite(float(s)))
        pl = placebo_sf(pooled[season]["gamma_k"], pooled[season]["p_zero"], line, p_line, strikes)
        pg = player_gamma(hist, yards, pooled[season]["gamma_k"])
        gm = placebo_sf(pg[0], pg[1], line, p_line, strikes) if pg else None
        prices = lad.drop_duplicates("line").set_index("line").over_price
        for i, s in enumerate(strikes):
            price = prices.get(s)
            if price is None or not np.isfinite(float(price)) or act == s:
                continue
            fair = min(implied(float(price)) * vig_factor, 0.999)
            rows.append(dict(season=season, game_id=gid, player=norm, book=book,
                             line=line, strike=s, rel=s / max(line, 0.5), price=float(price),
                             fair=fair, p_sim=float((xs > s).mean()),
                             p_gam=(gm[i] if gm else np.nan),
                             p_plc=(pl[i] if pl else np.nan), over=bool(act > s)))
    print(f"skipped: {dict(skipped)}")
    return pd.DataFrame(rows)


def grade(df: pd.DataFrame, pcol: str, cuts, rng) -> None:
    df = df.copy()
    df["edge"] = df[pcol] - df.fair
    print(f"\n  {'cut':>5} {'seas':>5} {'bets':>5} {'win%':>6} {'units':>8} {'ROI':>8} {'90% CI':>16}")
    for cut in cuts:
        sel = df[df.edge >= cut]
        # one bet per proposition: the largest edge
        sel = sel.sort_values("edge", ascending=False).drop_duplicates(["game_id", "player"])
        for season in sorted(sel.season.unique()) + ["all"]:
            g = sel if season == "all" else sel[sel.season == season]
            if len(g) < 5:
                print(f"  {cut:>5.0%} {season:>5} {len(g):>5}   (thin)")
                continue
            prof = np.array([profit(p, w) for p, w in zip(g.price, g.over)])
            idx = rng.integers(0, len(prof), (5000, len(prof)))
            roi = 100 * prof[idx].mean(axis=1)
            lo, hi = np.percentile(roi, 5), np.percentile(roi, 95)
            print(f"  {cut:>5.0%} {season:>5} {len(g):>5} {100*(prof>0).mean():>5.1f}% "
                  f"{prof.sum():>+8.2f} {100*prof.mean():>+7.2f}% "
                  f"{'('+format(lo,'+.1f')+', '+format(hi,'+.1f')+')':>16}")


def calibration(df: pd.DataFrame, pcol: str) -> None:
    print(f"\n  calibration of {pcol} by its own probability bucket:")
    for lo, hi in ((0, .15), (.15, .3), (.3, .45), (.45, .6), (.6, .75), (.75, 1.01)):
        b = df[(df[pcol] >= lo) & (df[pcol] < hi)]
        if len(b) >= 100:
            print(f"    {lo:.2f}-{hi:.2f}: n={len(b):6d}  {pcol} {100*b[pcol].mean():5.1f}%  "
                  f"fair {100*b.fair.mean():5.1f}%  realised {100*b.over.mean():5.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="player_reception_yds", choices=list(MARKETS))
    ap.add_argument("--draws", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260911)
    ap.add_argument("--cuts", nargs="+", type=float, default=[0.02, 0.03, 0.04, 0.05, 0.07, 0.10])
    ap.add_argument("--out", default=None, help="write the (row, strike) table to this CSV")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    df = run(a.market, a.draws, a.seed)
    if a.out:
        df.to_csv(a.out, index=False)
    print(f"\n=== {a.market}: {len(df):,} (proposition, strike) rows, "
          f"{df.groupby(['game_id','player']).ngroups:,} propositions, "
          f"anchor books {df.book.value_counts().to_dict()} ===")
    calibration(df, "p_sim")
    calibration(df, "p_gam")
    calibration(df, "p_plc")
    print("\nPLAYER SHAPE, usage compound (the hypothesis):")
    grade(df, "p_sim", a.cuts, rng)
    print("\nPLAYER SHAPE, gamma on own game totals (the plainer arm):")
    grade(df.dropna(subset=["p_gam"]), "p_gam", a.cuts, rng)
    print("\nPLACEBO — pooled gamma, same anchor (must NOT reproduce it):")
    grade(df.dropna(subset=["p_plc"]), "p_plc", a.cuts, rng)
    print("\nBars: each season positive; CI excludes zero at >= 200 bets with positive "
          "neighbours; placebo does not reproduce. Over-only ladder, so the direction bar "
          "is moot and no closing ladder exists for CLV.")


if __name__ == "__main__":
    main()

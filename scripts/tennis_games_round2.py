"""Tennis total games and games spreads, round 2: does the two players' serve
dominance carry information the book's own line lacks, and does a bet on it
make money at the US books we can bet? Reads the local cache
(scripts/tennis_cache.py) and the spooled match archive; writes nothing but its
own report and, with --save, every scored quote (outside the repo). No network,
no database, no paid call.

WHY A ROUND 2. Round 1 (scripts/tennis_serve_study.py) built a hold-and-tiebreak
game model anchored to the match price; its LEVEL was wrong (its mean total sat
2.6 to 3.6 games over the line), so every bet lost, but the coefficient on what
the players' serve statistics add over the book's own line was positive (z 2.0
to 2.7 on totals, 1.9 to 2.2 on spreads). This round keeps the line's own level
(weight 1, no intercept) and asks only whether ONE number from the statistics
moves it the right way.

FIXED BEFORE ANY RESULT WAS READ (none is changed after):

  population   round 1's, unchanged: scripts/tennis_serve_study.events_table
               (feed events linked to their ESPN result, ESPN start before
               2026-06-01, both players matched to the archive; best of, surface,
               the event date and the 52-week window exactly as there). Pre-match
               quotes only (tennis_market_study.pre_match)
  statistics   round 1's per-player relSPW and relRPW (serve and return points
               won over the previous 52 weeks against the tour-and-surface
               average, shrunk by 1000 points; 0 for a player with no row)
  features     dominance = relSPW - relRPW, per player
               TOTALS   D_sum = dominance(home) + dominance(away): two dominant
                        servers mean more holds, more games
               SPREADS  strength = relSPW + relRPW, per player. The favourite is
                        the side Pinnacle's h2h pair, power de-vigged
                        (tennis_shop_checks.power_side), gives over 0.5, from
                        Pinnacle's h2h row standing at the quote's own snapshot
                        (latest pre-match row at or before it, no age cap; none,
                        or exactly 0.5: the quote is OUT, counted). gap = the
                        favourite's strength minus the dog's. The gap the price
                        implies: gap_hat = m_g * logit(p_fav), a line through the
                        origin (an even price implies no gap), m_g fitted by least
                        squares per group g = (tour, best of) on the MAPPING ROWS;
                        a group with under 100 mapping rows uses m fitted on all
                        groups pooled. G_resid = gap - gap_hat
  mapping rows every population event with a pre-match Pinnacle h2h pair, at its
               latest pre-match h2h row (completed or not: no outcome is used),
               favourite and p_fav from that row
  model        TOTALS   logit P(over at L) = logit(p_line) + b * D_sum
               SPREADS  logit P(favourite covers its line) = logit(p_line) + c *
                        G_resid
               p_line = the power de-vigged chance of the over (of the
               favourite's side) from the pair of the book whose line it is, at
               that snapshot, clipped to [1e-4, 1 - 1e-4]. One coefficient, no
               intercept, the line's own logit at weight 1 (an offset). The other
               side's chance is 1 - P
  fit rows     Pinnacle only: per event and market its LATEST pre-match row
               (tennis_market_study.decision_quotes(..., "close")), completed
               matches, half lines only (a whole line is skipped, counted). For
               spreads the favourite and G_resid come from Pinnacle's h2h standing
               at that row's snapshot
  walk-forward season S (ESPN's season) is scored with b_S, c_S and m_g,S fitted on
               seasons before S only, maximum likelihood (Newton) for b and c.
               The first season has no fit and no bet; the decidable books' first
               season with a fit is 2023
  bet          at each decidable book's quote (BetMGM, Caesars, BetRivers) at each
               decision (first, t12, close: tennis_market_study.decision_quotes),
               P from the model with THAT book's own power de-vigged line chance
               as p_line. EV = P_win (d - 1) - P_loss. Whole-number lines are
               skipped (the push is not modelled), counted per market, decision
               and book. One bet per event, market and decision: the best EV
               across the three books and both sides (ties: book name, then side
               name). Cuts EV >= 0.00, 0.01, 0.02, 0.03, 0.05; the BANDED table is
               the one-bet-per-event set by its EV, [k, k + 0.01) for k = -0.03 to
               0.07, with the two tails
  grade        completed matches only, a retirement or walkover VOID (counted as a
               bet, 0 units); over wins on total > line; the favourite covers on
               its own margin + its own point > 0. Units at the published stake:
               risk min(1/(d - 1), 3) to win risk (d - 1). Units, never dollars
  multiple     2 markets x 3 decisions x 5 cuts = 30 cells. Per cell a one-sided
  testing      bootstrap p-value: the cell's bets (one per event) resampled with
               replacement 2,000 times, p = (1 + #{resampled units <= 0}) / 2,001;
               a cell with no bet has p = 1. Benjamini-Hochberg q-values over all
               30. Seed 20261114, cells in the order market, decision, cut

  information  on every Pinnacle fit row, per season S after the first: b_S (or
  test         c_S) fitted on the seasons before S, its maximum-likelihood SE and
               its SE clustered by tournament edition (sport key x edition, round
               1's edition rule); the same coefficient fitted on S alone (the
               independent read); the change in mean log-loss and Brier on S
               against p_line alone (model minus line, negative = the model is
               better), with an SE clustered by edition. Pooled over the scored
               seasons: the calibration slope k of the out-of-sample shift (y ~
               offset logit(p_line) + k * b_S * feature, no intercept), SE
               clustered by season and by edition; k excluding 0 is the pass.
               REPORTED ONLY (no decision rests on them): the feature's mean, sd
               and correlation with logit(p_line); the line's own calibration (mean
               outcome against mean p_line, per season); the same fit with an
               intercept; the out-of-sample log-loss change on the decidable
               books' own quotes (one row per event and book, over / favourite
               side, completed, half lines), SE clustered by event
  kill tests   on every cell with positive units: by season; early and late halves
               (bets sorted by start, split at the middle bet); side (over / under;
               favourite / dog, and home / away); price band (<= -130, -129 to
               -111, -110 to -101, +100 and up); book; best of 5 and best of 3; the
               five best days' share; the plateau (the cell's neighbours in the
               3 x 5 decision-by-cut grid, decisions ordered first, t12, close: at
               least half of them positive); a PLACEBO: 200 shuffles (seed
               20261114), each a permutation within season, over every population
               event, of the event's statistics, then everything refitted
               walk-forward (b, or m and c) and every cell re-scored. TOTALS: the
               event's D_sum given to another event. SPREADS: the event's strength
               gap oriented to its own favourite at its latest pre-match Pinnacle
               h2h row, given to another event with such a row (re-oriented to the
               receiving event's home side by the receiver's own favourite at that
               row); events without a Pinnacle h2h are not in the spreads shuffle
               (they have no spreads row). Reported: the shuffled units' mean, sd,
               5/50/95th percentiles and the share at or above the real units
  the bar      a cell CLEARS only with all of: positive units with the 90% interval
               above 0; the plateau; both halves positive; every season with 10+
               bets positive; no side over 70% of the bets and units still positive
               without the best price band; the placebo share at or above the real
               units under 0.05; BH q < 0.10; 25+ graded bets

    python -m scripts.tennis_games_round2 --cache C:/Users/micha/tennis_research/cache \\
        --spool C:/Users/micha/tennis_research/spool \\
        --save C:/Users/micha/tennis_research/cache/games_round2_quotes.parquet
    python -m scripts.tennis_games_round2 --self-test
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from models import tennis_common as tc
from scripts import tennis_market_study as st
from scripts import tennis_serve_study as ss
from scripts.tennis_games_study import GAMES_BOOKS, outcomes
from scripts.tennis_shop_checks import power_side
from scripts.tennis_shop_study import load, table

CUTS = (0.0, 0.01, 0.02, 0.03, 0.05)
BANDS = [round(k / 100, 2) for k in range(-3, 8)]
P_CLIP = 1e-4
SEED = 20261114
N_BOOT = 2000
N_SHUFFLE = 200
MAP_MIN_ROWS = 100
MARKETS = ("totals", "spreads")


# ── small maths ──────────────────────────────────────────────────────────────

def _dec(p) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(p > 0, 1 + p / 100, 1 + 100 / np.abs(p))


def logit(p):
    p = np.clip(np.asarray(p, float), P_CLIP, 1 - P_CLIP)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1 / (1 + np.exp(-np.asarray(z, float)))


def p_power(price_a, price_b) -> np.ndarray:
    """The power de-vigged chance of side a from an American pair."""
    ia, ib = 1 / _dec(price_a), 1 / _dec(price_b)
    return power_side(ia, ib)


def cluster_var(score_i: np.ndarray, groups: np.ndarray) -> float:
    """Sum over clusters of (sum of the score in the cluster)^2, with G/(G-1)."""
    codes, _ = pd.factorize(groups)
    s = np.bincount(codes, weights=score_i)
    G = len(s)
    return float((s ** 2).sum() * (G / (G - 1) if G > 1 else np.nan))


def fit_offset(y, off, x, groups=None) -> dict:
    """logit P(y=1) = off + b x, no intercept, by Newton. b, the ML SE, the SE
    clustered by `groups` (sandwich, G/(G-1))."""
    y, off, x = (np.asarray(v, float) for v in (y, off, x))
    out = {"n": len(y), "b": math.nan, "se": math.nan, "se_cl": math.nan}
    if len(y) < 2 or not np.any(x != 0):
        return out
    b = 0.0
    for _ in range(100):
        p = sigmoid(off + b * x)
        g = float((x * (y - p)).sum())
        H = float((p * (1 - p) * x * x).sum())
        if H <= 0:
            return out
        step = g / H
        b += step
        if abs(step) < 1e-12:
            break
    p = sigmoid(off + b * x)
    H = float((p * (1 - p) * x * x).sum())
    out.update(b=b, se=1 / math.sqrt(H))
    if groups is not None:
        out["se_cl"] = math.sqrt(cluster_var(x * (y - p), groups)) / H
    return out


def logloss(y, p) -> np.ndarray:
    p = np.clip(p, P_CLIP, 1 - P_CLIP)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def mean_diff_se(d: np.ndarray, groups) -> float:
    """SE of the mean of d, clustered by groups."""
    if len(d) < 2:
        return math.nan
    return math.sqrt(cluster_var(d - d.mean(), groups)) / len(d)


def bh(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg q-values (step-up, monotone)."""
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    q = p[o] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[o] = np.minimum(q, 1.0)
    return out


def boot_p(units: np.ndarray, rng, B: int = N_BOOT) -> float:
    n = len(units)
    if n == 0:
        return 1.0
    sums = units[rng.integers(0, n, size=(B, n))].sum(axis=1)
    return float((1 + (sums <= 0).sum()) / (B + 1))


def units_of(won: np.ndarray, void: np.ndarray, price: np.ndarray):
    d = _dec(price)
    risk = np.minimum(1 / (d - 1), 3.0)
    u = np.where(void, 0.0, np.where(won, risk * (d - 1), -risk))
    return u, risk


# ── the rows: Pinnacle fit rows, mapping rows, decidable quotes ──────────────

def market_rows(q: pd.DataFrame, fe: pd.DataFrame, pin_h2h: pd.DataFrame, market: str) -> pd.DataFrame:
    """One row per quote: the 'a' side is the over (totals) or the favourite
    (spreads). Columns: event, book, snapshot, point, price_a, price_b,
    p_line (power, side a), whole, y_a (1/0, NaN when not complete), and for
    spreads fav_home, p_fav. Quotes of spreads with no standing Pinnacle h2h
    or an even one are kept with fav_home NaN (counted, then dropped)."""
    x = q.merge(fe[["event_id", "status", "total", "margin"]], on="event_id")
    done = (x.status == "complete").values
    if market == "totals":
        out = pd.DataFrame({"event_id": x.event_id.values, "bookmaker": x.bookmaker.values,
                            "snapshot_ts": x.snapshot_ts.values, "point": x.total_point.values.astype(float),
                            "price_a": x.over_price.values.astype(float), "price_b": x.under_price.values.astype(float)})
        out["y_a"] = np.where(done, (x.total.values > out.point.values).astype(float), np.nan)
        out["side_a_home"] = np.nan
    else:
        x = x.sort_values("snapshot_ts")
        m = pd.merge_asof(x, pin_h2h[["event_id", "snapshot_ts", "p_home"]].rename(columns={"snapshot_ts": "h_ts"}),
                          left_on="snapshot_ts", right_on="h_ts", by="event_id", direction="backward")
        ph = m.p_home.values
        fav_home = np.where(np.isnan(ph) | (ph == 0.5), np.nan, (ph > 0.5).astype(float))
        fh = fav_home == 1
        out = pd.DataFrame({"event_id": m.event_id.values, "bookmaker": m.bookmaker.values,
                            "snapshot_ts": m.snapshot_ts.values,
                            "point": np.where(fh, m.home_point, m.away_point).astype(float),
                            "price_a": np.where(fh, m.home_price, m.away_price).astype(float),
                            "price_b": np.where(fh, m.away_price, m.home_price).astype(float)})
        out["side_a_home"] = fav_home
        out["p_fav"] = np.where(np.isnan(ph), np.nan, np.maximum(ph, 1 - ph))
        mg = m.margin.values.astype(float)
        cover = np.where(fh, mg + m.home_point.values, -mg + m.away_point.values) > 0
        out["y_a"] = np.where((m.status == "complete").values, cover.astype(float), np.nan)
    out["whole"] = out.point.values == np.floor(out.point.values)
    out["p_line"] = p_power(out.price_a.values, out.price_b.values)
    return out.merge(fe[["event_id", "season", "start", "tour", "bo", "status", "cl", "eidx"]], on="event_id")


def build(q, lk, res, ev) -> dict:
    pm = st.pre_match(q, lk, res)
    pm = pm[pm.event_id.isin(ev.event_id)]
    fe = ev.copy()
    h2 = pm[(pm.market == "h2h") & (pm.bookmaker == "pinnacle")].dropna(subset=["home_price", "away_price"])
    h2 = h2.sort_values("snapshot_ts").assign(p_home=lambda f: p_power(f.home_price.values, f.away_price.values))
    close_h2h = h2.groupby("event_id").tail(1)[["event_id", "p_home"]]
    fe = fe.merge(close_h2h.rename(columns={"p_home": "p_home_close"}), on="event_id", how="left")
    fe["eidx"] = np.arange(len(fe))
    data = {"fe": fe, "pin_h2h": h2, "rows": {}, "counts": {}}
    for market in MARKETS:
        pt_a, pr_a, pr_b = (("total_point", "over_price", "under_price") if market == "totals"
                            else ("home_point", "home_price", "away_price"))
        h = pm[pm.market == market].dropna(subset=[pt_a, pr_a, pr_b])
        if market == "spreads":
            h = h.dropna(subset=["away_point"])
        fit = st.decision_quotes(h[h.bookmaker == "pinnacle"], "close")
        data["rows"][(market, "fit")] = market_rows(fit, fe, h2, market)
        for dec in st.DECISIONS:
            dq = st.decision_quotes(h, dec)          # all books, as round 1 (t12 reads the listed start)
            dq = dq[dq.bookmaker.isin(GAMES_BOOKS)]
            data["rows"][(market, dec)] = market_rows(dq, fe, h2, market)
    return data


# ── features, fits and scoring, for one set of per-event statistics ──────────

def per_event_features(fe: pd.DataFrame, D_sum: np.ndarray, d_str: np.ndarray) -> dict:
    return {"D_sum": np.asarray(D_sum, float), "d_str": np.asarray(d_str, float)}


def mapping_fit(fe: pd.DataFrame, d_str: np.ndarray, seasons_lt) -> dict:
    """m per (tour, best of) on the mapping rows of the given seasons."""
    ph = fe.p_home_close.values
    ok = ~np.isnan(ph) & (ph != 0.5) & fe.season.isin(seasons_lt).values
    fav_home = ph > 0.5
    gap = np.where(fav_home, d_str, -d_str)
    xl = logit(np.maximum(ph, 1 - ph))
    grp = (fe.tour + ":" + fe.bo.astype(str)).values
    out = {}
    pooled_x, pooled_g = xl[ok], gap[ok]
    m_pool = float((pooled_x * pooled_g).sum() / (pooled_x ** 2).sum()) if ok.sum() else math.nan
    out["_pooled"] = (m_pool, int(ok.sum()))
    for g in np.unique(grp):
        k = ok & (grp == g)
        if k.sum() >= MAP_MIN_ROWS:
            out[g] = (float((xl[k] * gap[k]).sum() / (xl[k] ** 2).sum()), int(k.sum()))
        else:
            out[g] = (m_pool, int(k.sum()))
    return out


def feature_for_rows(r: pd.DataFrame, market: str, feats: dict, mp: dict | None) -> np.ndarray:
    if market == "totals":
        return feats["D_sum"][r.eidx.values]
    d = feats["d_str"][r.eidx.values]
    gap = np.where(r.side_a_home.values == 1, d, -d)
    grp = (r.tour + ":" + r.bo.astype(str)).values
    m = np.array([mp.get(g, mp["_pooled"])[0] for g in grp]) if len(r) else np.zeros(0)
    return gap - m * logit(r.p_fav.values)


def usable(r: pd.DataFrame, market: str) -> np.ndarray:
    ok = ~r.whole.values
    if market == "spreads":
        ok &= ~np.isnan(r.side_a_home.values)
    return ok


def season_fits(data: dict, market: str, feats: dict) -> dict:
    """{S: (coef, fit dict, mapping)} for every season after the first."""
    fe = data["fe"]
    r = data["rows"][(market, "fit")]
    r = r[usable(r, market) & ~np.isnan(r.y_a.values)]
    seasons = sorted(fe.season.unique())
    out = {}
    for S in seasons[1:]:
        prior = [s for s in seasons if s < S]
        mp = mapping_fit(fe, feats["d_str"], prior) if market == "spreads" else None
        k = r.season.isin(prior).values
        rk = r[k]
        x = feature_for_rows(rk, market, feats, mp)
        f = fit_offset(rk.y_a.values, logit(rk.p_line.values), x, rk.cl.values)
        out[S] = (f["b"], f, mp)
    return out


def score_rows(r: pd.DataFrame, market: str, feats: dict, fits: dict) -> pd.DataFrame:
    """P, EV both sides for the usable rows in a season with a fit."""
    r = r[usable(r, market) & r.season.isin(list(fits)).values].copy()
    if r.empty:
        return r.assign(x=[], P_a=[], ev_a=[], ev_b=[])
    xs = np.zeros(len(r))
    coef = np.zeros(len(r))
    for S, (b, f, mp) in fits.items():
        k = (r.season == S).values
        if k.any():
            xs[k] = feature_for_rows(r[k], market, feats, mp)
            coef[k] = b
    r["x"] = xs
    r["P_a"] = sigmoid(logit(r.p_line.values) + coef * xs)
    r["ev_a"] = r.P_a.values * (_dec(r.price_a.values) - 1) - (1 - r.P_a.values)
    r["ev_b"] = (1 - r.P_a.values) * (_dec(r.price_b.values) - 1) - r.P_a.values
    return r


def best_bets(s: pd.DataFrame, market: str) -> pd.DataFrame:
    """One bet per event: the best EV across books and both sides, every
    event (the cut is applied by the caller: the best EV is the same at any
    cut, so the set at cut c is the events whose best EV is >= c)."""
    na, nb = ("over", "under") if market == "totals" else ("fav", "dog")
    a = s.assign(side=na, ev=s.ev_a, price=s.price_a, won=s.y_a == 1)
    b = s.assign(side=nb, ev=s.ev_b, price=s.price_b, won=s.y_a == 0)
    x = pd.concat([a, b], ignore_index=True)
    x = x.sort_values(["ev", "bookmaker", "side"], ascending=[False, True, True]).drop_duplicates("event_id")
    void = x.status.values != "complete"
    x["grade"] = np.where(void, tc.VOID, np.where(x.won.values, tc.WIN, tc.LOSS))
    x["units"], x["risk"] = units_of(x.won.values, void, x.price.values)
    if market == "spreads":
        x["home_away"] = np.where((x.side == "fav") == (x.side_a_home == 1), "home", "away")
    return x


def all_cells(data: dict, feats: dict) -> dict:
    """{(market, dec): best-bet frame}, {market: fits}."""
    cells, fits_all = {}, {}
    for market in MARKETS:
        fits = season_fits(data, market, feats)
        fits_all[market] = fits
        for dec in st.DECISIONS:
            s = score_rows(data["rows"][(market, dec)], market, feats, fits)
            cells[(market, dec)] = (s, best_bets(s, market) if len(s) else s)
    return cells, fits_all


# ── reports ──────────────────────────────────────────────────────────────────

def line(t: dict) -> str:
    return (f"bets {t['bets']:5,} won {t['won']:5,} void {t['void']:3}  units {t['units']:+8.2f}  "
            f"roi {t['roi']:+.4f}  ci90 ({float(t['ci90'][0]):+.4f}, {float(t['ci90'][1]):+.4f})")


def population_report(data: dict) -> None:
    fe = data["fe"]
    print(f"  population events by season: {fe.season.value_counts().sort_index().to_dict()}")
    print(f"  with a pre-match Pinnacle h2h row: {int(fe.p_home_close.notna().sum()):,} of {len(fe):,}; "
          f"even (0.5) at the latest: {int((fe.p_home_close == 0.5).sum())}")
    for market in MARKETS:
        r = data["rows"][(market, "fit")]
        comp = ~np.isnan(r.y_a.values)
        print(f"\n  {market} Pinnacle fit rows (one per event, latest pre-match): {len(r):,}; completed {int(comp.sum()):,}; "
              f"whole-number lines {int(r.whole.sum()):,} (completed {int((r.whole & comp).sum()):,})"
              + (f"; no / even Pinnacle h2h at the snapshot {int(np.isnan(r.side_a_home.values).sum()):,}"
                 if market == "spreads" else ""))
        ok = usable(r, market) & comp
        print("    usable (completed, half line" + (", favourite known" if market == "spreads" else "") + ") by season: "
              f"{r[ok].season.value_counts().sort_index().to_dict()}")
        for dec in st.DECISIONS:
            r = data["rows"][(market, dec)]
            parts = []
            for bk, g in r.groupby("bookmaker"):
                parts.append(f"{bk} {len(g):,} (whole {int(g.whole.sum()):,}"
                             + (f", no fav {int(np.isnan(g.side_a_home.values).sum()):,}" if market == "spreads" else "")
                             + f", by season {g.season.value_counts().sort_index().to_dict()})")
            print(f"    decidable {dec:5s}: quotes {len(r):,} on {r.event_id.nunique():,} events; " + "; ".join(parts))


def info_report(data: dict, market: str, feats: dict, fits: dict, cells: dict) -> None:
    import statsmodels.api as sm
    r = data["rows"][(market, "fit")]
    r = r[usable(r, market) & ~np.isnan(r.y_a.values)]
    name = "b (D_sum)" if market == "totals" else "c (G_resid)"
    print(f"\n  INFORMATION TEST, {market}: Pinnacle's latest pre-match line, one row per match, walk-forward")
    seasons = sorted(fits)
    if market == "spreads":
        for S in seasons:
            mp = fits[S][2]
            print(f"    mapping for {S}: " + "; ".join(f"{g} m {v[0]:.5f} (n {v[1]:,})" for g, v in sorted(mp.items())))
    oos = []
    for S in seasons:
        b, f, mp = fits[S]
        rs = r[r.season == S]
        if rs.empty:
            print(f"    {S}: no rows")
            continue
        x = feature_for_rows(rs, market, feats, mp)
        y, off = rs.y_a.values, logit(rs.p_line.values)
        p0, p1 = sigmoid(off), sigmoid(off + b * x)
        dll = logloss(y, p1) - logloss(y, p0)
        dbr = (p1 - y) ** 2 - (p0 - y) ** 2
        own = fit_offset(y, off, x, rs.cl.values)
        try:
            ri = sm.GLM(y, sm.add_constant(x), family=sm.families.Binomial(), offset=off).fit()
            ic = f"with an intercept (season {S} alone): a {ri.params[0]:+.4f} ({ri.bse[0]:.4f}) b {ri.params[1]:+.3f} ({ri.bse[1]:.3f})"
        except Exception as exc:        # a failed diagnostic is reported, not hidden
            ic = f"intercept fit failed: {exc}"
        print(f"    {S}: fit on <{S} n {f['n']:,}: {name} {b:+.3f} se {f['se']:.3f} se_cl(edition) {f['se_cl']:.3f} "
              f"z {b / f['se_cl']:+.2f} | on {S} alone n {own['n']:,}: {own['b']:+.3f} se {own['se']:.3f} "
              f"se_cl {own['se_cl']:.3f} z {own['b'] / own['se_cl']:+.2f}")
        print(f"          OOS on {S}: d_logloss {dll.mean():+.6f} (se_cl {mean_diff_se(dll, rs.cl.values):.6f}) "
              f"d_brier {dbr.mean():+.6f} (se_cl {mean_diff_se(dbr, rs.cl.values):.6f}); "
              f"line calibration: mean y {y.mean():.4f} mean p_line {p0.mean():.4f}; feature mean {x.mean():+.4f} "
              f"sd {x.std():.4f} corr(x, logit p_line) {np.corrcoef(x, off)[0, 1]:+.3f}")
        print(f"          {ic}")
        oos.append(rs.assign(x=x, z=b * x, dll=dll, dbr=dbr))
    if not oos:
        return
    o = pd.concat(oos)
    y, off = o.y_a.values, logit(o.p_line.values)
    k1 = fit_offset(y, off, o.z.values, o.season.values)
    k2 = fit_offset(y, off, o.z.values, o.cl.values)
    print(f"    POOLED OOS ({', '.join(str(s) for s in sorted(o.season.unique()))}): n {len(o):,}; d_logloss "
          f"{o.dll.mean():+.6f} (se_cl {mean_diff_se(o.dll.values, o.cl.values):.6f}); d_brier {o.dbr.mean():+.6f} "
          f"(se_cl {mean_diff_se(o.dbr.values, o.cl.values):.6f})")
    print(f"      calibration slope of the OOS shift k {k1['b']:+.3f}: se_cl(season) {k1['se_cl']:.3f} "
          f"z {k1['b'] / k1['se_cl']:+.2f}; se_cl(edition) {k2['se_cl']:.3f} z {k2['b'] / k2['se_cl']:+.2f}; ML se {k1['se']:.3f}")
    print(f"    REPORTED ONLY: the decidable books' own quotes, out of sample (the walk-forward coefficient on "
          f"each book's own p_line), one row per event and book, completed, half lines")
    for dec in st.DECISIONS:
        s, _ = cells[(market, dec)]
        g = s[~np.isnan(s.y_a.values)]
        if g.empty:
            continue
        y, p0, p1 = g.y_a.values, g.p_line.values, g.P_a.values
        dll = logloss(y, p1) - logloss(y, p0)
        kk = fit_offset(y, logit(p0), logit(p1) - logit(p0), g.event_id.values)
        print(f"      {dec:5s} n {len(g):,} events {g.event_id.nunique():,}: d_logloss {dll.mean():+.6f} "
              f"(se_cl event {mean_diff_se(dll, g.event_id.values):.6f}); slope k {kk['b']:+.3f} se_cl {kk['se_cl']:.3f}; "
              f"mean y {y.mean():.4f} mean p_line {p0.mean():.4f} mean P {p1.mean():.4f}")


def grid(cells: dict, rng) -> dict:
    res = {}
    for market in MARKETS:
        for dec in st.DECISIONS:
            _, b = cells[(market, dec)]
            for cut in CUTS:
                x = b[b.ev >= cut] if len(b) else b
                t = table(x) if len(x) else {"bets": 0, "won": 0, "void": 0, "units": 0.0, "roi": math.nan,
                                             "ci90": (math.nan, math.nan), "graded": 0}
                p = boot_p(x.units.values, rng) if len(x) else 1.0
                res[(market, dec, cut)] = {"t": t, "p": p, "b": x}
    q = bh(np.array([v["p"] for v in res.values()]))
    for (k, v), qq in zip(res.items(), q):
        v["q"] = float(qq)
    return res


def banded(b: pd.DataFrame) -> None:
    g = b[b.ev < BANDS[0]]
    if len(g):
        print(f"    EV < {BANDS[0]:+.2f}          {line(table(g))}")
    for k in BANDS:
        g = b[(b.ev >= k) & (b.ev < k + 0.01)]
        if len(g):
            print(f"    EV [{k:+.2f}, {k + 0.01:+.2f})  {line(table(g))}")
    g = b[b.ev >= BANDS[-1] + 0.01]
    if len(g):
        print(f"    EV >= {BANDS[-1] + 0.01:+.2f}         {line(table(g))}")


def price_band(p):
    p = np.asarray(p, float)
    return np.select([p <= -130, p <= -111, p <= -101], ["<=-130", "-129..-111", "-110..-101"], "+100 up")


def splits(b: pd.DataFrame, market: str) -> dict:
    b = b.sort_values("start").reset_index(drop=True)
    half = np.where(np.arange(len(b)) < len(b) // 2, "early", "late")
    groups = {"season": b.season, "half": pd.Series(half), "side": b.side, "book": b.bookmaker,
              "best_of": b.bo, "price": pd.Series(price_band(b.price))}
    if market == "spreads":
        groups["home/away"] = b.home_away
    out = {}
    for name, key in groups.items():
        parts, d = [], {}
        for k, g in b.groupby(key.values):
            t = table(g)
            d[k] = t
            parts.append(f"{k}: {t['bets']} / {t['units']:+.2f}u / {t['roi']:+.3f}")
        out[name] = d
        print(f"      by {name:9s} " + " | ".join(parts))
    day = b.groupby(b.start.dt.date).units.sum().sort_values(ascending=False)
    print(f"      five best days {day.head(5).sum():+.2f}u of {b.units.sum():+.2f}u; without them "
          f"{b.units.sum() - day.head(5).sum():+.2f}u over {b.start.dt.date.nunique()} days")
    return out


def plateau(res: dict, market: str, dec: str, cut: float) -> tuple[int, int]:
    di, ci = st.DECISIONS.index(dec), CUTS.index(cut)
    pos = tot = 0
    for dd in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dd == dc == 0:
                continue
            i, j = di + dd, ci + dc
            if 0 <= i < 3 and 0 <= j < len(CUTS):
                tot += 1
                pos += res[(market, st.DECISIONS[i], CUTS[j])]["t"]["units"] > 0
    return pos, tot


def placebo(data: dict, feats: dict, rng) -> dict:
    """{(market, dec, cut): array of shuffled units}."""
    fe = data["fe"]
    seas = fe.season.values
    ph = fe.p_home_close.values
    has = ~np.isnan(ph) & (ph != 0.5)
    o = np.where(ph > 0.5, 1.0, -1.0)
    gap_close = o * feats["d_str"]
    out = {}
    t0 = time.time()
    for i in range(N_SHUFFLE):
        D = feats["D_sum"].copy()
        dstr = feats["d_str"].copy()
        for S in np.unique(seas):
            k = np.flatnonzero(seas == S)
            D[k] = feats["D_sum"][k[rng.permutation(len(k))]]
            k2 = np.flatnonzero((seas == S) & has)
            dstr[k2] = o[k2] * gap_close[k2[rng.permutation(len(k2))]]
        cells, _ = all_cells(data, {"D_sum": D, "d_str": dstr})
        for (market, dec), (_, b) in cells.items():
            for cut in CUTS:
                out.setdefault((market, dec, cut), []).append(float(b.units[b.ev >= cut].sum()) if len(b) else 0.0)
        if i == 0:
            print(f"    placebo: first shuffle {time.time() - t0:.1f}s")
    return {k: np.array(v) for k, v in out.items()}


# ── self-test ────────────────────────────────────────────────────────────────

def self_test() -> int:
    import statsmodels.api as sm
    ok = True

    def check(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'ok ' if cond else 'FAIL'} {name}")

    rng = np.random.default_rng(7)
    n = 40000
    off = rng.normal(0, 0.6, n)
    x = rng.normal(0, 0.08, n)
    grp = rng.integers(0, 300, n)
    y = (rng.random(n) < sigmoid(off + 2.5 * x)).astype(float)
    f = fit_offset(y, off, x, grp)
    r = sm.GLM(y, x[:, None], family=sm.families.Binomial(), offset=off).fit()
    check(f"offset MLE recovers b = 2.5: {f['b']:.3f} se {f['se']:.3f}", abs(f["b"] - 2.5) < 4 * f["se"])
    check(f"offset MLE equals statsmodels GLM ({r.params[0]:.6f}, se {r.bse[0]:.6f})",
          abs(f["b"] - r.params[0]) < 1e-6 and abs(f["se"] - r.bse[0]) < 1e-6)
    rc = sm.GLM(y, x[:, None], family=sm.families.Binomial(), offset=off).fit(
        cov_type="cluster", cov_kwds={"groups": grp})
    check(f"clustered SE near statsmodels' ({f['se_cl']:.5f} vs {rc.bse[0]:.5f})", abs(f["se_cl"] / rc.bse[0] - 1) < 0.01)
    y0 = (rng.random(n) < sigmoid(off)).astype(float)
    f0 = fit_offset(y0, off, x, grp)
    check(f"b = 0 truth: {f0['b']:+.3f} within 3 se", abs(f0["b"]) < 3 * f0["se"])

    from scipy.stats import false_discovery_control
    p = rng.random(30) ** 3
    check("BH equals scipy's false_discovery_control", np.allclose(bh(p), false_discovery_control(p, method="bh")))
    check("bootstrap p of all-winning bets = 1/2001", boot_p(np.ones(40), rng) == 1 / 2001)
    check("bootstrap p of all-losing bets = 1", boot_p(-np.ones(40), rng) == 1.0)

    pa = p_power(np.array([-120.0, 150.0]), np.array([100.0, -180.0]))
    pb = p_power(np.array([100.0, -180.0]), np.array([-120.0, 150.0]))
    check(f"power de-vig pair sums to 1 ({pa + pb})", np.allclose(pa + pb, 1, atol=1e-9))
    P = 0.5
    ev = P * (_dec(-110) - 1) - (1 - P)
    check(f"EV at P 0.5, -110 = {float(ev):.4f} (-0.0455)", abs(float(ev) + 0.04545) < 1e-4)
    u, risk = units_of(np.array([True, False, True, False]), np.array([False, False, True, False]),
                       np.array([-150.0, -150.0, 200.0, 300.0]))
    check(f"units at the published stake: {u} risk {risk}",
          np.allclose(u, [1.0, -1.5, 0.0, -1 / 3]) and np.allclose(risk, [1.5, 1.5, 0.5, 1 / 3]))

    # the mapping through the origin recovers its slope
    k = 5000
    ph_ = rng.uniform(0.3, 0.97, k)
    xl = logit(np.maximum(ph_, 1 - ph_))
    gap = 0.03 * xl + rng.normal(0, 0.02, k)
    d_str = np.where(ph_ > 0.5, gap, -gap)
    fe = pd.DataFrame({"p_home_close": ph_, "season": 2021, "tour": "ATP", "bo": 3})
    mp = mapping_fit(fe, d_str, [2021])
    check(f"mapping slope recovered: {mp['ATP:3'][0]:.4f} (0.03)", abs(mp["ATP:3"][0] - 0.03) < 0.002)

    # grading orientation on the favourite
    q = pd.DataFrame({"event_id": ["h", "a", "h2"], "bookmaker": "betmgm",
                      "snapshot_ts": pd.to_datetime(["2024-01-02"] * 3, utc=True),
                      "home_point": [-3.5, 3.5, -3.5], "away_point": [3.5, -3.5, 3.5],
                      "home_price": [-110.0, -110.0, -110.0], "away_price": [-110.0, -110.0, -110.0]})
    fe2 = pd.DataFrame({"event_id": ["h", "a", "h2"], "status": "complete", "total": [20, 20, 20],
                        "margin": [4, -4, 3], "season": 2024, "start": pd.to_datetime(["2024-01-03"] * 3, utc=True),
                        "tour": "ATP", "bo": 3, "cl": "x", "eidx": [0, 1, 2]})
    h2h = pd.DataFrame({"event_id": ["h", "a", "h2"], "snapshot_ts": pd.to_datetime(["2024-01-01"] * 3, utc=True),
                        "p_home": [0.7, 0.3, 0.7]})
    rr = market_rows(q, fe2, h2h, "spreads").set_index("event_id")
    check(f"home favourite -3.5 by 4 covers; away favourite -3.5 by 4 covers; home -3.5 by 3 does not: "
          f"{rr.y_a.to_dict()}", rr.y_a["h"] == 1 and rr.y_a["a"] == 1 and rr.y_a["h2"] == 0)
    check("favourite side and point oriented", rr.side_a_home["h"] == 1 and rr.side_a_home["a"] == 0
          and rr.point["a"] == -3.5 and rr.point["h"] == -3.5)
    print("SELF-TEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--spool")
    ap.add_argument("--save", type=Path)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-placebo", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    pd.set_option("display.width", 220)
    t0 = time.time()
    arch = ss.load_archive(a.spool)
    avg = ss.averages(arch)
    q, res = load(a.cache)
    lk = st.link(q, res)
    oc = outcomes(lk, res)
    ev, info = ss.events_table(q, lk, res, oc, arch, avg)
    print("POPULATION (round 1's events_table)")
    for k in ("linked_with_result", "before_cutoff", "both_matched", "player_slots", "player_slots_matched"):
        print(f"  {k}: {info[k]}")
    ev["cl"] = ev.sport_key + ":" + ev.edition.astype(str)
    data = build(q, lk, res, ev)
    fe = data["fe"]
    feats = per_event_features(fe, (fe.h_spw - fe.h_rpw + fe.a_spw - fe.a_rpw).values,
                               ((fe.h_spw + fe.h_rpw) - (fe.a_spw + fe.a_rpw)).values)
    print(f"  D_sum over the population: mean {feats['D_sum'].mean():+.4f} sd {feats['D_sum'].std():.4f}; "
          f"home-minus-away strength: mean {feats['d_str'].mean():+.4f} sd {feats['d_str'].std():.4f}")
    population_report(data)
    print(f"  [{time.time() - t0:.0f}s]")

    cells, fits = all_cells(data, feats)
    for market in MARKETS:
        info_report(data, market, feats, fits[market], cells)

    rng = np.random.default_rng(SEED)
    res_ = grid(cells, rng)
    print("\n===================== GRID (one bet per event: best EV across books and sides) =====================")
    print("  p = one-sided bootstrap (2,000, events resampled); q = Benjamini-Hochberg over the 30 cells")
    for market in MARKETS:
        for dec in st.DECISIONS:
            s, b = cells[(market, dec)]
            print(f"\n  {market} {dec}: scored quotes {len(s):,} on {s.event_id.nunique() if len(s) else 0:,} events; "
                  f"median EV of the best per event {b.ev.median() if len(b) else math.nan:+.4f}; "
                  f"bets by season at EV>=0: {b[b.ev >= 0].season.value_counts().sort_index().to_dict() if len(b) else {}}")
            for cut in CUTS:
                v = res_[(market, dec, cut)]
                print(f"    EV>={cut:.2f}  {line(v['t'])}  p {v['p']:.4f} q {v['q']:.4f}")
            print("   BANDED")
            if len(b):
                banded(b)

    pos = [k for k, v in res_.items() if v["t"]["units"] > 0]
    print("\n===================== KILL TESTS ON EVERY POSITIVE CELL =====================")
    if not pos:
        print("  none")
    sp = {}
    for k in pos:
        market, dec, cut = k
        v = res_[k]
        print(f"\n  {market} {dec} EV>={cut:.2f}: {line(v['t'])}  p {v['p']:.4f} q {v['q']:.4f}")
        sp[k] = splits(v["b"], market)
        pp, tt = plateau(res_, market, dec, cut)
        print(f"      plateau: {pp} of {tt} neighbouring cells positive")
    if pos and not a.no_placebo:
        print("\n  PLACEBO (200 within-season shuffles, everything refitted walk-forward)")
        pl = placebo(data, feats, np.random.default_rng(SEED))
        for k in pos:
            r = pl[k]
            real = res_[k]["t"]["units"]
            share = float(np.mean(r >= real))
            res_[k]["placebo_share"] = share
            print(f"    {k[0]} {k[1]} EV>={k[2]:.2f}: mean {r.mean():+.2f} sd {r.std(ddof=1):.2f} p5 {np.percentile(r, 5):+.2f} "
                  f"p50 {np.percentile(r, 50):+.2f} p95 {np.percentile(r, 95):+.2f}; real {real:+.2f}; share >= real {share:.3f}")
    if pos:
        print("\n  THE BAR, per positive cell")
        for k in pos:
            v, s_ = res_[k], sp[k]
            t = v["t"]
            pp, tt = plateau(res_, *k)
            halves = all(x["units"] > 0 for x in s_["half"].values())
            seasons_ok = all(x["units"] > 0 for x in s_["season"].values() if x["bets"] >= 10)
            side_share = max(x["bets"] for x in s_["side"].values()) / t["bets"]
            best_band = max(s_["price"].items(), key=lambda kv: kv[1]["units"])
            wo_band = t["units"] - best_band[1]["units"]
            checks = {"ci90 above 0": t["ci90"][0] > 0, "plateau": pp * 2 >= tt, "both halves": halves,
                      "every season 10+ positive": seasons_ok, f"side share {side_share:.2f} <= 0.70": side_share <= 0.70,
                      f"without best band ({best_band[0]}) {wo_band:+.2f}u > 0": wo_band > 0,
                      f"placebo share {v.get('placebo_share', math.nan):.3f} < 0.05": v.get("placebo_share", 1.0) < 0.05,
                      f"BH q {v['q']:.4f} < 0.10": v["q"] < 0.10, f"graded {t['graded']} >= 25": t["graded"] >= 25}
            verdict = "CLEARS" if all(checks.values()) else "MISSES on " + ", ".join(c for c, okk in checks.items() if not okk)
            print(f"    {k[0]} {k[1]} EV>={k[2]:.2f}: {verdict}")
    if a.save:
        parts = []
        for (market, dec), (s, _) in cells.items():
            if len(s):
                parts.append(s.assign(market=market, decision=dec)[
                    ["market", "decision", "event_id", "bookmaker", "snapshot_ts", "season", "start", "tour", "bo",
                     "status", "point", "price_a", "price_b", "p_line", "x", "P_a", "ev_a", "ev_b", "y_a"]])
        pd.concat(parts, ignore_index=True).to_parquet(a.save, index=False)
        print(f"\nsaved scored quotes to {a.save}")
    print(f"done [{time.time() - t0:.0f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

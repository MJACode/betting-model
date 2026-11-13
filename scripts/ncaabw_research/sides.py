"""Women's spread and moneyline off the team ratings, at DraftKings' first
posted line.

The totals model's ratings (models/ncaabw_total_blend.py) hold each team's
offence, defence and tempo as of an hour. The same ratings give a home margin:
    margin = (eff_home - eff_away) x possessions / 100
This script asks whether that margin beats DraftKings' first posted spread and
moneyline, the way the predicted total beats its first posted total.

  the quote   DraftKings' earliest pre-game spread row by its own time (the
              home number; 1,771 of 1,772 carry the same stamp as its first
              total), and its earliest moneyline row
  the blend   actual margin - L = c + beta x (model margin - L), sd sigma,
              where L = -spread_home is the margin the line implies; fitted on
              earlier priced seasons only
  the price   P(cover, push left out) at DraftKings' two spread prices;
              P(win) at its two moneyline prices from the same blended margin
  the grade   one unit to win, risk capped at 3, 95% interval resampled by date

Folds, as for the totals: 2025-26 on numbers fitted on 2024-25 (walk-forward),
2024-25 on 2025-26 (a second look, not walk-forward), and the two pooled.

    python -m scripts.ncaabw_research.sides            (reads the cache only)
    python -m scripts.ncaabw_research.sides grid       (the ratings' settings moved)
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE  # noqa: E402
import models.ncaabw_quote_bounds as qb  # noqa: E402
import models.ncaabw_total_blend as nb  # noqa: E402
import scripts.ncaabw_total_blend_build as mb  # noqa: E402

CUTS = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10)
BOOK = "draftkings"


class MarginRatings(nb.SeasonRatings):
    """The totals model's ratings, read as a home margin: predict() returns
    (margin, possessions) so season_pass() can be reused unchanged."""

    def predict(self, beta, tau, hid, aid, loc):
        nt = self.nt
        i = np.array([self.ix[int(t)] for t in hid]); j = np.array([self.ix[int(t)] for t in aid])
        l = np.asarray(loc, float)
        O = beta[:nt]; D = beta[nt:2 * nt]; mu = beta[2 * nt]; h = beta[2 * nt + 1]
        T = tau[:nt]; tmu = tau[nt]; htp = tau[nt + 1]
        eh = mu + O[i] + D[j] + h * l
        ea = mu + O[j] + D[i] - h * l
        pp = tmu + T[i] + T[j] + htp * l
        return (eh - ea) * pp / 100.0, pp


def margins(g, cut, settings=None):
    """Model home margin per game as of its quote hour (season_pass's strict
    rule), every other game from finals dated before it."""
    keep = nb.SeasonRatings
    nb.SeasonRatings = MarginRatings
    try:
        preds, _ = mb.ratings_chain(g, cut, nb.Params.from_dict(settings or mb.SETTINGS), log=lambda *_: None)
    finally:
        nb.SeasonRatings = keep
    return preds.rename(columns={"pt_s1": "m_model"})


def grid(g, sp):
    """Is it the ratings' settings? The same test with the shrinkage, the
    carry-over from last season and the half-life moved: the blend's beta
    (how much of the model's disagreement with the line comes true) and the
    walk-forward bets."""
    cut = dict(zip(sp["game_id"], sp["quote_ns"]))
    base = dict(mb.SETTINGS)
    tests = [("the totals model's settings", {}),
             ("less shrinkage, K 4", {"K": 4.0}), ("least shrinkage, K 1.5", {"K": 1.5}),
             ("more shrinkage, K 16", {"K": 16.0}),
             ("full carry-over, a 1.0", {"a": 1.0}), ("K 4 and a 0.9", {"K": 4.0, "a": 0.9}),
             ("half-life 90 days", {"half_life": 90.0}),
             ("K 4, a 0.9, half-life 90", {"K": 4.0, "a": 0.9, "half_life": 90.0})]
    print("SETTINGS GRID (spread): margin error against the line's, the blend's beta by season, "
          "and 2025-26 on numbers from 2024-25")
    for label, over in tests:
        t = time.time()
        d = margins(g, cut, {**base, **over}).merge(g[["game_id", "home_score", "away_score"]], on="game_id")
        d["margin"] = d["home_score"] - d["away_score"]
        x = d.merge(sp[["game_id", "spread_home", "home_price", "away_price"]], on="game_id")
        x["L"] = -x["spread_home"]
        x = x[x["m_model"].notna() & x["margin"].notna()]
        s25, s26 = x[x["season"] == 2025], x[x["season"] == 2026]
        b25, b26 = fit(s25), fit(s26)
        wf = score_spread(s26, b25)
        err = {s: (round(float((xs["margin"] - xs["L"]).abs().mean()), 2),
                   round(float((xs["margin"] - xs["m_model"]).abs().mean()), 2))
               for s, xs in ((2025, s25), (2026, s26))}
        z1, z2 = wf[wf["edge"] > 0.01], wf[wf["edge"] > 0.02]
        print(f"  {label:30s} error line/model 2024-25 {err[2025][0]}/{err[2025][1]}, 2025-26 "
              f"{err[2026][0]}/{err[2026][1]} | beta {b25['all']['beta']:+.3f} / {b26['all']['beta']:+.3f} | "
              f"walk-forward > 0.01: {len(z1)} bets {z1['units'].sum():+.2f}u; > 0.02: {len(z2)} bets "
              f"{z2['units'].sum():+.2f}u ({time.time() - t:.0f}s)")


def moneyline_bands(xm):
    """The market's own shape: every underdog and every favourite by price
    band and season, no model."""
    print("MONEYLINE BY PRICE BAND, no model (DraftKings' first posted moneyline)")
    for name, pick in (("underdog", lambda z: np.where(z["ml_home"] < z["ml_away"], "away", "home")),
                       ("favourite", lambda z: np.where(z["ml_home"] < z["ml_away"], "home", "away"))):
        z = xm.copy(); z["side"] = pick(z)
        z["price"] = np.where(z["side"] == "home", z["ml_home"], z["ml_away"])
        z = grade_cols(z, np.where(z["side"] == "home", z["margin"], -z["margin"]))
        bands = ([(-111, 150), (150, 300), (300, 700), (700, 1500), (1500, 10 ** 6)] if name == "underdog"
                 else [(-200, -100), (-400, -200), (-1000, -400), (-3000, -1000), (-10 ** 6, -3000)])
        for lo, hi in bands:
            zz = z[(z["price"] > lo) & (z["price"] <= hi)]
            parts = " | ".join(f"{s}: {len(q)} bets {int((q['won'] == 1).sum())}-{int((q['won'] == 0).sum())} "
                               f"{q['units'].sum():+.2f}u" for s, q in zz.groupby("season") if s in (2025, 2026))
            print(line_of(zz[zz["season"].isin([2025, 2026])], f"{name} {lo:+d} to {hi:+d}", clv=False)
                  + "  || " + parts)


def dk_first(P, market, cols):
    """DraftKings' first usable pre-game row per game for a market, its next
    change, and its last row."""
    t = P[(P["market"] == market) & (P["bookmaker"] == BOOK)].dropna(subset=cols).copy()
    line = "spread_home" if market == "spreads" else None
    bad = [qb.problem(market, (r[line] if line else None), (r[cols[-2]], r[cols[-1]])) for _, r in t.iterrows()]
    t = t[[b is None for b in bad]]
    print(f"DraftKings {market} rows {len(t):,}; dropped as data errors {sum(b is not None for b in bad)}")
    t = t.sort_values(["game_id", "last_update", "snapshot_ts"], kind="stable")
    first = t.groupby("game_id").head(1).copy()
    nxt = t.groupby("game_id").nth(1)[["game_id", "last_update"]].rename(columns={"last_update": "next_change"})
    first = first.merge(nxt, on="game_id", how="left")
    first["quote_ns"] = first["last_update"].dt.as_unit("ns").astype("int64")
    return first


def consensus_close(P):
    """Median of every book's last pre-game spread (home number), per game."""
    t = P[P["market"] == "spreads"].dropna(subset=["spread_home"])
    t = t[t["spread_home"].abs() <= qb.LINE_RANGE["spreads"][1]]
    last = t.sort_values("last_update").groupby(["game_id", "bookmaker"]).tail(1)
    return last.groupby("game_id")["spread_home"].median().rename("close_spread")


def score_spread(te, blends):
    """Each game priced on the spread: 'over' in nb.price is the home side."""
    rows = []
    for r in te.itertuples(index=False):
        b = nb.blend_for(blends, r.game_date)
        pz = nb.price(r.m_model, r.L, r.home_price, r.away_price, b)
        side = "home" if pz.side == "over" else "away"
        rows.append((side, pz.price, pz.edge, pz.prob, pz.mean))
    out = te.copy()
    out[["side", "price", "edge", "prob", "mean"]] = pd.DataFrame(rows, index=out.index)
    return grade_cols(out, np.where(out["side"] == "home", out["margin"] - out["L"], out["L"] - out["margin"]))


def score_moneyline(te, blends, floor=None):
    """Each game priced on the moneyline from the same blended margin: the
    win probability is P(margin > 0), the tie bin left out."""
    rows = []
    for r in te.itertuples(index=False):
        b = nb.blend_for(blends, r.game_date)
        mean = r.L + b["c"] + b["beta"] * (r.m_model - r.L)
        pw, _pp, pl = nb.outcome_probs(mean, b["sigma"], 0.0)
        ph = pw / (pw + pl)
        cands = [("home", ph, r.ml_home), ("away", 1 - ph, r.ml_away)]
        if floor is not None:
            cands = [c for c in cands if c[2] >= floor]
        if not cands:
            rows.append((None, np.nan, np.nan, np.nan, mean))
            continue
        side, p, pr = max(cands, key=lambda c: c[1] - 1.0 / nb.dec(c[2]))
        rows.append((side, float(pr), p - 1.0 / nb.dec(pr), p, mean))
    out = te.copy()
    out[["side", "price", "edge", "prob", "mean"]] = pd.DataFrame(rows, index=out.index)
    out = out[out["side"].notna()].copy()
    return grade_cols(out, np.where(out["side"] == "home", out["margin"], -out["margin"]))


def grade_cols(out, res):
    dd = out["price"].map(nb.dec)
    out["risk"] = np.minimum(1.0 / (dd - 1.0), 3.0)
    out["units"] = np.where(res > 0, out["risk"] * (dd - 1.0), np.where(res < 0, -out["risk"], 0.0))
    out["won"] = np.where(res > 0, 1.0, np.where(res < 0, 0.0, np.nan))
    return out


def line_of(b, label, clv=True):
    if not len(b):
        return f"  {label:34s}    0 bets"
    ud = b.groupby("game_date")["units"].sum().values
    rd = b.groupby("game_date")["risk"].sum().values
    # its own seeded draw, so a line's interval does not depend on what was printed before it
    idx = np.random.default_rng(20261111).integers(0, len(ud), size=(3000, len(ud)))
    lo, hi = np.percentile(ud[idx].sum(axis=1) / rd[idx].sum(axis=1) * 100, [2.5, 97.5])
    w = int((b["won"] == 1).sum()); l = int((b["won"] == 0).sum())
    s = (f"  {label:34s} {len(b):4d} bets {w}-{l}  {b['units'].sum():+7.2f}u {b['units'].sum() / b['risk'].sum() * 100:+6.2f}% "
         f"[{lo:+5.1f}, {hi:+5.1f}]  prices {b['price'].min():+.0f}..{b['price'].max():+.0f}")
    if clv and "clv" in b:
        s += f"  close {b['clv'].mean():+.2f} pts"
    return s


def fit(tr):
    return nb.fit_blends(tr.assign(pt=tr["m_model"], line=tr["L"], total=tr["margin"]))


def show_blend(bl, label):
    print(f"  {label}: " + ", ".join(
        f"{k} c {v['c']:+.2f} beta {v['beta']:.3f} sigma {v['sigma']:.2f} n {v['n']}" for k, v in bl.items() if v))


def report(sc, label, floors=False):
    print(f"\n{label}")
    for c in CUTS:
        print(line_of(sc[sc["edge"] > c], f"edge > {c:.2f}"))


if __name__ == "__main__":
    t0 = time.time()
    P = pd.read_parquet(CACHE / "pregame_quotes.parquet")
    g, box, _dk_totals = mb.load(CACHE, 2027)
    g, b = mb.prepare(g, box)
    sp = dk_first(P, "spreads", ["spread_home", "home_price", "away_price"])
    ml = dk_first(P, "h2h", ["home_price", "away_price"])
    sp = sp[sp["game_id"].isin(set(g["game_id"]))]
    if len(sys.argv) > 1 and sys.argv[1] == "grid":
        grid(g, sp)
        sys.exit(0)
    cut = dict(zip(sp["game_id"], sp["quote_ns"]))
    preds = margins(g, cut)
    d = preds.merge(g[["game_id", "home_score", "away_score"]], on="game_id")
    d["margin"] = d["home_score"] - d["away_score"]
    x = d.merge(sp[["game_id", "spread_home", "home_price", "away_price", "last_update", "next_change"]], on="game_id")
    x = x.merge(consensus_close(P), on="game_id", how="left")
    x["L"] = -x["spread_home"]                       # the home margin the line implies
    x = x[x["m_model"].notna() & x["margin"].notna()].copy()
    x["stood_min"] = (x["next_change"] - x["last_update"]).dt.total_seconds() / 60
    print(f"priced games (a model margin and a DraftKings first spread): {len(x):,} "
          f"{x.groupby('season').size().to_dict()} ({time.time() - t0:.0f}s)")
    for s, xs in x.groupby("season"):
        e_line = xs["margin"] - xs["L"]; e_mod = xs["margin"] - xs["m_model"]
        print(f"  {s}: n {len(xs)}  line error {e_line.abs().mean():.2f} (bias {e_line.mean():+.2f}) | "
              f"model error {e_mod.abs().mean():.2f} (bias {e_mod.mean():+.2f}) | model - line sd "
              f"{(xs['m_model'] - xs['L']).std():.2f}")
    s25, s26, s27 = (x[x["season"] == s] for s in (2025, 2026, 2027))
    b25, b26, b_live = fit(s25), fit(s26), fit(pd.concat([s25, s26]))
    print("\nBLENDS (actual margin - line on model margin - line)")
    show_blend(b25, "fitted on 2024-25"); show_blend(b26, "fitted on 2025-26"); show_blend(b_live, "both seasons")

    def with_clv(sc):
        # home bet at spread s against the close c: s - c points of line value
        sc["clv"] = np.where(sc["side"] == "home", sc["spread_home"] - sc["close_spread"],
                             sc["close_spread"] - sc["spread_home"])
        return sc

    print("\n================ SPREAD ================")
    wf = with_clv(score_spread(s26, b25)); sl = with_clv(score_spread(s25, b26))
    pooled = pd.concat([wf, sl])
    report(wf, "2025-26 on numbers from 2024-25 (walk-forward)")
    report(sl, "2024-25 on numbers from 2025-26 (second look)")
    report(pooled, "each season on the other's numbers, pooled")
    live = with_clv(score_spread(pd.concat([s25, s26]), b_live))
    report(live, "both seasons on the two-season blend (in sample)")
    if len(s27):
        w27 = with_clv(score_spread(s27, b_live))
        print("\n2026-27 to 2026-11-08 on the two-season blend (every team pooled then: not usable)")
    print("\nblind baselines, every priced game of both seasons:")
    base = pd.concat([s25, s26])
    for name, side in (("every home side", np.full(len(base), "home")),
                       ("every away side", np.full(len(base), "away")),
                       ("every favourite", np.where(base["spread_home"] < 0, "home", "away")),
                       ("every underdog", np.where(base["spread_home"] < 0, "away", "home"))):
        z = base.copy(); z["side"] = side
        z["price"] = np.where(z["side"] == "home", z["home_price"], z["away_price"])
        z = grade_cols(z, np.where(z["side"] == "home", z["margin"] - z["L"], z["L"] - z["margin"]))
        print(line_of(z, name, clv=False))
    print("\nsplits, each season on the other's numbers:")
    for c in (0.02, 0.04):
        z = pooled[pooled["edge"] > c]
        ph = np.array([nb.phase_of(v) for v in z["game_date"]])
        fav = np.where(z["spread_home"] < 0, "home", "away")
        a = z["spread_home"].abs()
        for label, m in (("November", ph == "Nov"), ("December on", ph != "Nov"),
                         ("bet the favourite", z["side"].values == fav), ("bet the underdog", z["side"].values != fav),
                         ("bet the home side", z["side"].values == "home"), ("bet the away side", z["side"].values == "away"),
                         ("spread under 10", (a < 10).values), ("spread 10 to 25", ((a >= 10) & (a < 25)).values),
                         ("spread 25 or more", (a >= 25).values),
                         ("first post stood 10+ min", (z["stood_min"].fillna(1e9) >= 10).values),
                         ("stood under 10 min", (z["stood_min"].fillna(1e9) < 10).values)):
            print(line_of(z[m], f"> {c:.2f} {label}"))
    print("\nclaimed against realised (each season on the other's numbers, every priced game):")
    for lo, hi in ((0.5, 0.52), (0.52, 0.55), (0.55, 0.58), (0.58, 0.62), (0.62, 1.0)):
        z = pooled[(pooled["prob"] >= lo) & (pooled["prob"] < hi) & pooled["won"].notna()]
        if len(z):
            print(f"  claimed {lo:.2f}-{hi:.2f}: n {len(z):4d}  claimed {z['prob'].mean():.3f}  won {z['won'].mean():.3f}")
    pooled.to_parquet(CACHE / "sides_spread_scored.parquet", index=False)

    print("\n================ MONEYLINE ================")
    xm = x.merge(ml[["game_id", "home_price", "away_price"]].rename(
        columns={"home_price": "ml_home", "away_price": "ml_away"}), on="game_id")
    m25, m26 = xm[xm["season"] == 2025], xm[xm["season"] == 2026]
    print(f"priced games with a DraftKings first moneyline: {len(xm):,} {xm.groupby('season').size().to_dict()}")
    for floor, name in ((None, "any price"), (-200.0, "nothing shorter than -200")):
        wf = score_moneyline(m26, b25, floor); sl = score_moneyline(m25, b26, floor)
        pooled_m = pd.concat([wf, sl])
        report(wf, f"MONEYLINE, {name}: 2025-26 on numbers from 2024-25 (walk-forward), {len(wf)} games priced")
        report(sl, f"MONEYLINE, {name}: 2024-25 on numbers from 2025-26 (second look), {len(sl)} games priced")
        report(pooled_m, f"MONEYLINE, {name}: pooled")
        z = pooled_m[pooled_m["edge"] > 0.03]
        fav = np.where(z["ml_home"] < z["ml_away"], "home", "away")
        print(line_of(z[z["side"].values == fav], "> 0.03 bet the favourite", clv=False))
        print(line_of(z[z["side"].values != fav], "> 0.03 bet the underdog", clv=False))
        pooled_m.to_parquet(CACHE / f"sides_moneyline_scored_{'any' if floor is None else 'floor200'}.parquet", index=False)
    print()
    moneyline_bands(xm)
    base = pd.concat([m25, m26])
    print("\nblind moneyline baselines, both seasons:")
    for name, side in (("every home side", np.full(len(base), "home")),
                       ("every favourite", np.where(base["ml_home"] < base["ml_away"], "home", "away")),
                       ("every underdog", np.where(base["ml_home"] < base["ml_away"], "away", "home"))):
        z = base.copy(); z["side"] = side
        z["price"] = np.where(z["side"] == "home", z["ml_home"], z["ml_away"])
        z = grade_cols(z, np.where(z["side"] == "home", z["margin"], -z["margin"]))
        print(line_of(z, name, clv=False))
    print(f"\ndone ({time.time() - t0:.0f}s)")

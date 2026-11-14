"""Round 2, experiment B: the market-anchored models (pre-registration:
section 0.3 of euroleague_round2.md). Returns / prints markdown.

  Moneyline  logit P(home) = logit(Pinnacle power no-vig home at the close)
             [offset, fixed at 1] + X b, ridge (every coefficient penalised).
  Spread     predicted home margin = -(Pinnacle closing home spread) + X d,
             ridge least squares on margin + Pinnacle spread; P(home covers at
             L) = Phi((pred + L) / sigma), sigma the training SD.
  Penalty    {0.3, 1, 3, 10, 30, 100, 300, 1000}, leave-one-season-out on the
             training seasons; graded 2023-24 .. 2026-27, each fitted on every
             earlier season from 2021-22.
  Bet        edge = model P(side) - the book's no-vig P(side); DraftKings close
             (moneyline -200 floor before the pick), the best decidable close
             as the second moneyline read; cuts 0.00 .. 0.05, headline 0.02.

    python scripts/euroleague_research/r3_b_anchored.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from scipy.stats import norm

import r2_lib as L2
import r3_lib as R

EXP = "B"
LAMS = [0.3, 1, 3, 10, 30, 100, 300, 1000]
CUTS = [0.00, 0.01, 0.02, 0.03, 0.04, 0.05]
HEAD = 0.02
GRADED = [2024, 2025, 2026, 2027]
R1 = {("TEL", "ALEKSANDAR NIKOLIC HALL"), ("TEL", "BELGRADE ARENA"), ("TEL", "SPYROS KYPRIANOU ATHLETIC CENTER"),
      ("HTA", "ARENA 8888 SOFIA"), ("HTA", "ARENA BOTEVGRAD"),
      ("DUB", "ZETRA ARENA"), ("DUB", "ARENA HUSEJIN SMAJLOVIC ZENICA")}
R2 = {("IST", "MORACA"), ("IST", "ARENA RIGA"), ("ULK", "SAP GARDEN"), ("ULK", "KALNAPILIO ARENA"),
      ("ULK", "ZALGIRIO ARENA"), ("PAR", "BMW PARK")}
GROUPS = {
    "home": ["const"],
    "home underdog": ["hdog"],
    "attendance": ["log_att", "att_missing"],
    "venue": ["reloc_season", "reloc_list"],
    "rest": ["rest_diff", "home_short", "away_short", "first_game"],
    "double week": ["dbl_week", "dbl2_home", "dbl2_away"],
}


# ── features (prior-games only, except the venue-schedule flag noted in 0.3) ─

def features(g_all: pd.DataFrame) -> pd.DataFrame:
    g = g_all.sort_values("tip").reset_index(drop=True).copy()
    g["venue"] = g.venue_name.fillna("").str.strip()
    # attendance: home club's earlier home games, this season and last, audience > 0
    idx = R.prior_index(g.tip)
    att_sum, att_n = {}, {}
    log_att = np.full(len(g), np.nan)
    hist = []           # (pos, club, season, audience)
    ptr = 0
    for i in range(len(g)):
        while ptr < idx[i]:
            r = g.iloc[ptr]
            if (not r.neutral_site) and r.audience > 0:
                key = (r.home_code, int(r.season))
                att_sum[key] = att_sum.get(key, 0.0) + float(r.audience)
                att_n[key] = att_n.get(key, 0) + 1
            ptr += 1
        c, s = g.home_code.iloc[i], int(g.season.iloc[i])
        n = att_n.get((c, s), 0) + att_n.get((c, s - 1), 0)
        if n:
            log_att[i] = np.log1p((att_sum.get((c, s), 0.0) + att_sum.get((c, s - 1), 0.0)) / n)
    g["log_att_raw"] = log_att
    g["att_missing"] = np.isnan(log_att).astype(float)
    # venue
    home = g[~g.neutral_site]
    mode = home.groupby(["home_code", "season"]).venue.agg(lambda v: v.value_counts().index[0])
    g["reloc_season"] = [float(v != mode.get((c, s), v)) for c, s, v in zip(g.home_code, g.season, g.venue)]
    g["reloc_list"] = [float((c, v) in R1 or (c, v) in R2) for c, v in zip(g.home_code, g.venue)]
    # rest, double-round weeks
    d = pd.to_datetime(g.game_date)
    iso = d.dt.isocalendar()
    g["wk"] = iso.year.astype(int) * 100 + iso.week.astype(int)
    rs = g[g.phase == "RS"].groupby(["season", "wk"])["round"].nunique()
    g["dbl_week"] = [float(rs.get((s, w), 0) >= 2) for s, w in zip(g.season, g.wk)]
    long = pd.concat([
        pd.DataFrame({"pos": g.index, "club": g.home_code, "season": g.season, "tip": g.tip, "wk": g.wk, "is_home": True}),
        pd.DataFrame({"pos": g.index, "club": g.away_code, "season": g.season, "tip": g.tip, "wk": g.wk, "is_home": False}),
    ]).sort_values(["club", "season", "tip"])
    long["prev_tip"] = long.groupby(["club", "season"]).tip.shift()
    long["prev_wk"] = long.groupby(["club", "season"]).wk.shift()
    long["rest"] = ((long.tip - long.prev_tip).dt.total_seconds() / 86400).round()
    long["second"] = (long.prev_wk == long.wk).astype(float)
    for side, pre in ((True, "home"), (False, "away")):
        x = long[long.is_home == side].set_index("pos")
        g[f"{pre}_rest"] = x.rest.reindex(g.index)
        g[f"dbl2_{pre}"] = x.second.reindex(g.index).fillna(0.0)
    g["first_game"] = (g.home_rest.isna() | g.away_rest.isna()).astype(float)
    hr = g.home_rest.fillna(7.0)
    ar = g.away_rest.fillna(7.0)
    g["rest_diff"] = hr.clip(2, 8) - ar.clip(2, 8)
    g["home_short"] = (hr <= 3).astype(float)
    g["away_short"] = (ar <= 3).astype(float)
    g["const"] = 1.0
    return g


# ── fits ─────────────────────────────────────────────────────────────────────

def standardise(tr: pd.DataFrame, te: pd.DataFrame, cols):
    Xtr, Xte = [], []
    for c in cols:
        if c == "log_att":
            ra, rb = tr["log_att_raw"].to_numpy(float), te["log_att_raw"].to_numpy(float)
            m = np.nanmean(ra)
            a = np.where(np.isnan(ra), m, ra)
            b = np.where(np.isnan(rb), m, rb)
        else:
            a = tr[c].to_numpy(float)
            b = te[c].to_numpy(float)
        if c == "const":
            Xtr.append(a)
            Xte.append(b)
            continue
        mu, sd = a.mean(), a.std()
        sd = sd if sd > 0 else 1.0
        Xtr.append((a - mu) / sd)
        Xte.append((b - mu) / sd)
    return np.column_stack(Xtr), np.column_stack(Xte)


def ridge_logit(X, y, off, lam):
    def f(b):
        z = off + X @ b
        p = expit(z)
        ll = -np.sum(y * np.log(np.clip(p, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-12, 1)))
        grad = X.T @ (p - y) + lam * b
        return ll + 0.5 * lam * b @ b, grad
    r = minimize(f, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B")
    return r.x


def ridge_ls(X, y, lam):
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)


def logloss(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def choose_lam(tr: pd.DataFrame, cols, kind: str):
    seasons = sorted(tr.season.unique())
    best = None
    for lam in LAMS:
        loss = []
        for s in seasons:
            a, b = tr[tr.season != s], tr[tr.season == s]
            Xa, Xb = standardise(a, b, cols)
            if kind == "ml":
                coef = ridge_logit(Xa, a.y.to_numpy(float), a.off.to_numpy(float), lam)
                loss.append(logloss(b.y.to_numpy(float), expit(b.off.to_numpy(float) + Xb @ coef)) * len(b))
            else:
                coef = ridge_ls(Xa, a.y.to_numpy(float), lam)
                loss.append(float(np.sum((b.y.to_numpy(float) - Xb @ coef) ** 2)))
        tot = sum(loss)
        if best is None or tot < best[1]:
            best = (lam, tot)
    return best[0]


def walk_forward(T: pd.DataFrame, cols, kind: str) -> pd.DataFrame:
    """Per graded season: the shift X b (logit, moneyline) or X d (points,
    spread) for each graded game, fitted on every earlier season."""
    out = []
    for s in GRADED:
        tr = T[T.season < s]
        te = T[T.season == s].copy()
        if not len(te):
            continue
        if not cols:
            te["shift"], te["lam"] = 0.0, np.nan
        else:
            lam = choose_lam(tr, cols, kind)
            Xtr, Xte = standardise(tr, te, cols)
            if kind == "ml":
                coef = ridge_logit(Xtr, tr.y.to_numpy(float), tr.off.to_numpy(float), lam)
            else:
                coef = ridge_ls(Xtr, tr.y.to_numpy(float), lam)
            te["shift"] = Xte @ coef
            te["lam"] = lam
            te["coefs"] = ", ".join(f"{c} {v:+.3f}" for c, v in zip(cols, coef))
        if kind == "sp":
            te["sigma"] = float(tr.y.std())
        out.append(te)
    return pd.concat(out, ignore_index=True)


# ── bets ─────────────────────────────────────────────────────────────────────

def ml_bets(P: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    """P: game_id, p_model (home). quotes: the decidable h2h quotes at the close
    (one or many books). One bet a game: the largest edge over (book, side),
    a side shorter than -200 never considered."""
    z = R.ml_sides(quotes).merge(P[["game_id", "p_model"]], on="game_id")
    z["pm"] = np.where(z.side == "home", z.p_model, 1 - z.p_model)
    z["edge"] = z.pm - z.fair
    z = z[z.price >= -200]
    z = z.sort_values(["game_id", "edge", "bookmaker"], ascending=[True, False, True]).drop_duplicates("game_id")
    return L2.grade(z)


def sp_bets(P: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    z = L2.sides_long(quotes[quotes.market == "spreads"]).merge(P[["game_id", "pred", "sigma"]], on="game_id")
    ph = norm.cdf((z.pred + z.line) / z.sigma)
    z["pm"] = np.where(z.side == "home", ph, 1 - ph)
    z["edge"] = z.pm - z.fair
    z["fav"] = np.where(z.side == "home", z.line < 0, z.line > 0)
    z = z.sort_values(["game_id", "edge", "bookmaker"], ascending=[True, False, True]).drop_duplicates("game_id")
    return L2.grade(z)


def build():
    g, q, dt, cb, fp = R.fullgame()
    F = features(g)
    F = F[~F.neutral_site & (F.season >= 2022)]
    pin_ml = R.one_book(cb, "h2h", "pinnacle", cols=("pa_pow",), prefix="pin_")
    pin_sp = R.one_book(cb, "spreads", "pinnacle", cols=("line",), prefix="pin_")
    F = F.merge(pin_ml, on="game_id", how="left").merge(pin_sp, on="game_id", how="left")
    dk_ml = cb[(cb.market == "h2h") & (cb.bookmaker == "draftkings") & cb.game_id.isin(F.game_id)]
    dec_ml = cb[(cb.market == "h2h") & cb.bookmaker.isin(R.DECIDABLE) & cb.game_id.isin(F.game_id)]
    dk_sp = cb[(cb.market == "spreads") & (cb.bookmaker == "draftkings") & cb.game_id.isin(F.game_id)]
    return F, dk_ml, dec_ml, dk_sp


def tables_ml(F, dk_ml, dec_ml, md):
    T = F[F.pin_pa_pow.notna()].copy()
    T["off"] = logit(T.pin_pa_pow.clip(1e-6, 1 - 1e-6))
    T["y"] = (T.margin > 0).astype(float)
    T["hdog"] = (T.pin_pa_pow < 0.5).astype(float)
    md.append("\n### B1. Moneyline: market-anchored logit, walk-forward (r3_b_anchored.py)\n")
    md.append(f"Games (neutral out, 2021-22 on): {len(F)}; with a Pinnacle close moneyline: {len(T)}; dropped: {len(F) - len(T)}. "
              f"By season with Pinnacle: {T.groupby('season').size().to_dict()}.\n")
    allcols = [c for v in GROUPS.values() for c in v]
    variants = {"market alone (offset only)": [], "full model": allcols}
    for gname, cols in GROUPS.items():
        variants[f"full minus {gname}"] = [c for c in allcols if c not in cols]
    variants["home dummy only"] = ["const"]
    res = {}
    for name, cols in variants.items():
        W = walk_forward(T, cols, "ml")
        W["p_model"] = expit(W.off + W["shift"])
        res[name] = W
    # coefficients of the full model
    W = res["full model"]
    md.append("Full-model coefficients by graded season (standardised inputs; the penalty chosen on the training seasons):\n")
    md.append(R.table([{"graded season": int(s), "penalty": float(x.lam.iloc[0]), "coefficients": x.coefs.iloc[0]}
                       for s, x in W.groupby("season")]))
    md.append("\nAccuracy on the graded games (log loss / Brier; lower is better):\n")
    rows = []
    for name, W in res.items():
        y = W.y.to_numpy(float)
        rows.append({"variant": name, "games": len(W), "log loss": round(logloss(y, W.p_model.to_numpy()), 5),
                     "brier": round(float(np.mean((W.p_model - y) ** 2)), 5),
                     "log loss vs market": round(logloss(y, W.p_model.to_numpy()) - logloss(y, expit(W.off.to_numpy())), 5)})
    md.append(R.table(rows))
    bets = {}
    md.append("\nCut grid, DraftKings close (main price), -200 floor, graded 2023-24 .. 2026-27:\n")
    rows = []
    for name in ("market alone (offset only)", "full model"):
        B = ml_bets(res[name], dk_ml)
        bets[("dk", name)] = B
        for c in CUTS:
            rows.append(R.reg(EXP, f"B1 ML {name}, DK close, cut {c:.2f}", B[B.edge > c]) | {"cut": c})
    md.append(R.table(rows))
    md.append("\nAblation at the headline cut 0.02, DraftKings close:\n")
    rows = []
    for name in variants:
        if name in ("market alone (offset only)", "full model"):
            B = bets[("dk", name)]
            rows.append(R.row({"variant": name, "cut": HEAD}, B[B.edge > HEAD]))
            continue
        B = ml_bets(res[name], dk_ml)
        bets[("dk", name)] = B
        rows.append(R.reg(EXP, f"B1 ML {name}, DK close, cut 0.02", B[B.edge > HEAD]) | {"variant": name})
    md.append(R.table(rows))
    md.append("\nSecond read: the best decidable close (largest edge over the decidable books), full model:\n")
    B = ml_bets(res["full model"], dec_ml)
    bets[("dec", "full model")] = B
    rows = [R.reg(EXP, f"B1 ML full model, best decidable close, cut {c:.2f}", B[B.edge > c]) | {"cut": c} for c in CUTS]
    md.append(R.table(rows))
    B0 = ml_bets(res["market alone (offset only)"], dec_ml)
    md.append("\nThe market-alone row at the best decidable close (not counted; the second read's control):\n")
    md.append(R.table([R.row({"cut": c}, B0[B0.edge > c]) for c in CUTS]))
    return res, bets


def tables_sp(F, dk_sp, md):
    T = F[F.pin_line.notna()].copy()
    T["y"] = T.margin + T.pin_line
    T = T[T.y != 0]
    T["hdog"] = (T.pin_line > 0).astype(float)
    md.append("\n### B2. Spread: market-anchored residual model, walk-forward (r3_b_anchored.py)\n")
    md.append(f"Games with a Pinnacle closing spread (pushes on Pinnacle's number out of the fit): {len(T)}; "
              f"by season {T.groupby('season').size().to_dict()}.\n")
    allcols = [c for v in GROUPS.values() for c in v]
    variants = {"market alone (offset only)": [], "full model": allcols}
    for gname, cols in GROUPS.items():
        variants[f"full minus {gname}"] = [c for c in allcols if c not in cols]
    variants["home dummy only"] = ["const"]
    res = {}
    for name, cols in variants.items():
        W = walk_forward(T, cols, "sp")
        W["pred"] = -W.pin_line + W["shift"]
        res[name] = W
    W = res["full model"]
    md.append("Full-model coefficients by graded season (points per standard deviation):\n")
    md.append(R.table([{"graded season": int(s), "penalty": float(x.lam.iloc[0]), "sigma": round(float(x.sigma.iloc[0]), 2),
                        "coefficients": x.coefs.iloc[0]} for s, x in W.groupby("season")]))
    md.append("\nAccuracy on the graded games (mean squared error of the residual; market alone predicts 0):\n")
    rows = []
    for name, W in res.items():
        rows.append({"variant": name, "games": len(W), "mse": round(float(np.mean((W.y - W["shift"]) ** 2)), 3),
                     "mse vs market": round(float(np.mean((W.y - W["shift"]) ** 2) - np.mean(W.y ** 2)), 3)})
    md.append(R.table(rows))
    bets = {}
    md.append("\nCut grid, DraftKings close spread:\n")
    rows = []
    for name in ("market alone (offset only)", "full model"):
        B = sp_bets(res[name], dk_sp)
        bets[name] = B
        for c in CUTS:
            rows.append(R.reg(EXP, f"B2 spread {name}, DK close, cut {c:.2f}", B[B.edge > c]) | {"cut": c})
    md.append(R.table(rows))
    md.append("\nAblation at the headline cut 0.02:\n")
    rows = []
    for name in variants:
        if name in bets:
            rows.append(R.row({"variant": name}, bets[name][bets[name].edge > HEAD]))
            continue
        B = sp_bets(res[name], dk_sp)
        bets[name] = B
        rows.append(R.reg(EXP, f"B2 spread {name}, DK close, cut 0.02", B[B.edge > HEAD]) | {"variant": name})
    md.append(R.table(rows))
    return res, bets


def placebo_ml(W: pd.DataFrame, quotes, real: float, n=200, seed=11):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        X = W.copy()
        X["shift"] = X.groupby("season")["shift"].transform(lambda v: rng.permutation(v.to_numpy()))
        X["p_model"] = expit(X.off + X["shift"])
        B = ml_bets(X, quotes)
        B = B[B.edge > HEAD]
        out.append(100 * B.units.sum() / B.risk.sum() if B.risk.sum() > 0 else np.nan)
    o = np.array(out)
    return {"placebo runs": n, "real ret%": round(real, 2), "placebo mean ret%": round(float(np.nanmean(o)), 2),
            "placebo 95th pct": round(float(np.nanpercentile(o, 95)), 2), "share >= real": round(float(np.nanmean(o >= real)), 3)}


def placebo_sp(W: pd.DataFrame, quotes, real: float, n=200, seed=11):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        X = W.copy()
        X["shift"] = X.groupby("season")["shift"].transform(lambda v: rng.permutation(v.to_numpy()))
        X["pred"] = -X.pin_line + X["shift"]
        B = sp_bets(X, quotes)
        B = B[B.edge > HEAD]
        out.append(100 * B.units.sum() / B.risk.sum() if B.risk.sum() > 0 else np.nan)
    o = np.array(out)
    return {"placebo runs": n, "real ret%": round(real, 2), "placebo mean ret%": round(float(np.nanmean(o)), 2),
            "placebo 95th pct": round(float(np.nanpercentile(o, 95)), 2), "share >= real": round(float(np.nanmean(o >= real)), 3)}


def run():
    md = ["\n## B. Market-anchored models (r3_b_anchored.py)\n"]
    F, dk_ml, dec_ml, dk_sp = build()
    md.append("Input coverage (neutral out, 2021-22 on): attendance missing "
              f"{100 * F.att_missing.mean():.1f}%, venue differs from the club-season's usual {100 * F.reloc_season.mean():.1f}%, "
              f"on the relocated lists {100 * F.reloc_list.mean():.1f}%, home short rest {100 * F.home_short.mean():.1f}%, "
              f"away short rest {100 * F.away_short.mean():.1f}%, double-round week {100 * F.dbl_week.mean():.1f}%, "
              f"first game of a season {100 * F.first_game.mean():.1f}%. Travel: not derivable (no coordinates stored).\n")
    res_ml, bets_ml = tables_ml(F, dk_ml, dec_ml, md)
    res_sp, bets_sp = tables_sp(F, dk_sp, md)
    md.append("\n### B3. Kill tests on the headline cells (r3_b_anchored.py)\n")
    for lab, B in (("B1 ML full model, DK close, cut 0.02", bets_ml[("dk", "full model")]),
                   ("B1 ML market alone, DK close, cut 0.02", bets_ml[("dk", "market alone (offset only)")]),
                   ("B1 ML full model, best decidable close, cut 0.02", bets_ml[("dec", "full model")]),
                   ("B2 spread full model, DK close, cut 0.02", bets_sp["full model"]),
                   ("B2 spread market alone, DK close, cut 0.02", bets_sp["market alone (offset only)"])):
        x = B[B.edge > HEAD]
        md.append(f"\n{lab}: price range {R.price_range(x)}\n")
        md.append(R.table(R.kill_rows(lab, x)))
    x = bets_ml[("dk", "full model")]
    x = x[x.edge > HEAD]
    real = 100 * x.units.sum() / x.risk.sum() if x.risk.sum() > 0 else np.nan
    md.append("\nPlacebo, moneyline full model at the DraftKings close (the model's shift shuffled across each season's games):\n")
    md.append(R.table([placebo_ml(res_ml["full model"], dk_ml, real)]))
    x = bets_sp["full model"]
    x = x[x.edge > HEAD]
    real = 100 * x.units.sum() / x.risk.sum() if x.risk.sum() > 0 else np.nan
    md.append("\nPlacebo, spread full model at the DraftKings close:\n")
    md.append(R.table([placebo_sp(res_sp["full model"], dk_sp, real)]))
    return "\n".join(md)


if __name__ == "__main__":
    print(run())

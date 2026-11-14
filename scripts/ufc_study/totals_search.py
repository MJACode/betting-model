"""UFC round totals, the full method search on the bought history
(docs/ufc_market_audit.md section 4).

Fixed before looking: decisions only on the noon pulls (the bought history's
daily pull, served at 11:00 UTC; the live card decides at 12:00), any lead of
at least an hour unless a table says otherwise; the first pull that clears
locks the fight; graded at the quoted price of a book a pick may name (only
DraftKings carries totals in the bought history, from late 2023), at the SAME
line as the Pinnacle quote it is compared with; closing-line value against
Pinnacle's last pre-fight no-vig price at that line. Bet lines: 1.5, 2.5, 4.5
(0.5 and 3.5 are under 50 fights each).

1. Pinnacle-anchored, walk-forward by year, three nested models:
   (a) Pinnacle's no-vig over price as it stands;
   (b) (a) plus one free intercept per line (the market's bias by line);
   (c) (b) plus fighter, bout and moneyline inputs, ridge.
   logit P(over) = logit(no-vig) + intercept[line] + b.z
2. Market structure: margins, blind sides by line, first and last pull;
   DraftKings against Pinnacle's fair price at the same line in the same pull.
3. Three mechanisms of this study's own (M1-M3).
4. Is the data right: our over rate against the no-vig over rate.

Run from the study folder (feed_quotes.parquet, fights.parquet).
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ml_base import ci, dec, novig, units

pd.set_option("display.width", 250)
LINES = (1.5, 2.5, 4.5)
RIDGE = 30.0
CUTS = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
REPORT_CUT = 0.04

Q = pd.read_parquet("feed_quotes.parquet")
Q["served_at"] = pd.to_datetime(Q.served_at, utc=True)
Q["commence"] = pd.to_datetime(Q.commence, utc=True)
Q["start"] = Q.game_id.map(Q.groupby("game_id").commence.max())
Q = Q[Q.served_at < Q.start].copy()
Q["lead_h"] = (Q.start - Q.served_at).dt.total_seconds() / 3600
Q = Q[Q.lead_h >= 1.0]

F = pd.read_parquet("fights.parquet").set_index("game_id")
F["year"] = pd.to_datetime(F.date).dt.year
for c in ("fin_rate", "dec_rate", "ko_loss", "kd15", "sub15", "td15", "avg_mins", "slpm", "sapm", "ko_win", "sub_win"):
    F[f"s_{c}"] = pd.to_numeric(F[f"a_{c}"], errors="coerce") + pd.to_numeric(F[f"b_{c}"], errors="coerce")
F["five"] = (F.sched == 5).astype(float)
F["women_f"] = F.women.astype(float)


def wclass(w):
    w = str(w).lower()
    if "light heavyweight" in w:
        return "lhw"
    for k, v in (("heavyweight", "hw"), ("middleweight", "mw"), ("welterweight", "ww"), ("lightweight", "lw"),
                 ("featherweight", "fw"), ("bantamweight", "bw"), ("flyweight", "flw"), ("strawweight", "sw")):
        if k in w:
            return v
    return "other"


F["wc"] = F.weight_class.map(wclass)
for w in ("hw", "lhw", "mw", "ww", "fw", "bw", "flw", "sw"):
    F[f"wc_{w}"] = (F.wc == w).astype(float)
FIGHT_Z = ["s_fin_rate", "s_dec_rate", "s_ko_loss", "s_kd15", "s_sub15", "s_td15", "s_avg_mins", "s_slpm",
           "s_sapm", "s_ko_win", "s_sub_win", "five", "women_f", "wc_hw", "wc_lhw", "wc_mw", "wc_ww", "wc_fw",
           "wc_bw", "wc_flw", "wc_sw"]
Z = FIGHT_Z + ["mismatch"]
FREE = ["d15", "d25", "d45"]

T_all = Q[(Q.market == "totals") & Q.line.isin((0.5, 1.5, 2.5, 3.5, 4.5)) & Q.over.notna() & Q.under.notna()].copy()
T_all = T_all[(T_all.over.abs() >= 100) & (T_all.under.abs() >= 100)]
H = Q[(Q.market == "h2h") & Q.pa.notna() & Q.pb.notna()]
F_ok = F[F.rounds_done.notna()]
T_all = T_all[T_all.game_id.isin(F_ok.index)]
T_all = T_all.join(F_ok[["rounds_done", "year", "date", "sched", "wc"] + FIGHT_Z], on="game_id")
T_all = T_all[T_all.rounds_done != T_all.line]
T_all["over_won"] = T_all.rounds_done > T_all.line
T = T_all[T_all.line.isin(LINES)].copy()


def pinnacle(X):
    pin_h = H[H.book == "pinnacle"][["game_id", "served_at", "pa", "pb"]].rename(columns={"pa": "hpa", "pb": "hpb"})
    P = X[X.book == "pinnacle"].merge(pin_h, on=["game_id", "served_at"], how="left")
    P["mismatch"] = np.abs(novig(P.hpa, P.hpb) - 0.5)
    P["fair_over"] = novig(P.over, P.under)
    for L, col in ((1.5, "d15"), (2.5, "d25"), (4.5, "d45")):
        P[col] = (P.line == L).astype(float)
    return P


P = pinnacle(T)
P_all = pinnacle(T_all)
# Pinnacle's close at each line: its last pre-fight quote at that line
pclose = (T[T.book == "pinnacle"].sort_values("served_at").groupby(["game_id", "line"]).tail(1)
          .set_index(["game_id", "line"]))
pclose_fair = pd.Series(novig(pclose.over, pclose.under), index=pclose.index)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sig(s):
    return 1 / (1 + np.exp(-s))


def fit(Xp, Xf, off, y, lam):
    """Ridge on Xp, free (unpenalised) on Xf, the market as offset."""
    X = np.hstack([Xp, Xf])
    pen = np.r_[np.ones(Xp.shape[1]), np.zeros(Xf.shape[1])]

    def nll(b):
        s = off + X @ b
        return np.sum(np.logaddexp(0, s) - y * s) + lam * np.sum(pen * b ** 2)

    def grad(b):
        s = off + X @ b
        return X.T @ (sig(s) - y) + 2 * lam * pen * b
    b = minimize(nll, np.zeros(X.shape[1]), jac=grad, method="L-BFGS-B").x
    return b[:Xp.shape[1]], b[Xp.shape[1]:]


FITS = {}


def walk_forward(kind, lam=RIDGE):
    """xb for every Pinnacle pull of each year, fitted on the years before it.
    Training rows: each fight's last noon Pinnacle pull at each line.
    kind 'b' = intercepts by line only, 'c' = intercepts + fighter inputs."""
    out = []
    daily = P[P.stage == "daily"].sort_values("served_at")
    for Y in sorted(P.year.dropna().unique().astype(int)):
        tr = daily[daily.year < Y].groupby(["game_id", "line"]).tail(1)
        te = P[P.year == Y]
        if tr.game_id.nunique() < 300 or te.empty:
            continue
        mu, sd = tr[Z].mean(), tr[Z].std().replace(0, 1)
        Xp = ((tr[Z] - mu) / sd).fillna(0.0).to_numpy() if kind == "c" else np.zeros((len(tr), 0))
        bp, bf = fit(Xp, tr[FREE].to_numpy(), logit(tr.fair_over), tr.over_won.to_numpy(float), lam)
        FITS[(kind, lam, Y)] = (bp, bf, mu, sd)
        xb = te[FREE].to_numpy() @ bf
        if kind == "c":
            xb = xb + ((te[Z] - mu) / sd).fillna(0.0).to_numpy() @ bp
        out.append(te.assign(xb=xb))
    return pd.concat(out)


def grade(K):
    won = np.where(K.side == "over", K.over_won, ~K.over_won.astype(bool))
    u, r = units(K.price.to_numpy(), won)
    return u, r, won


def report(label, K, clv_col=True):
    if len(K) < 10:
        print(f"{label:60} {len(K):4d} bets")
        return
    u, r, won = grade(K)
    lo, hi = ci(u, r)
    cf = np.array([pclose_fair.get((g, l), np.nan) for g, l in zip(K.game_id, K.line)])
    side_fair = np.where(K.side == "over", cf, 1 - cf)
    clv = np.nanmean(side_fair * dec(K.price.to_numpy()) - 1)
    d = pd.to_datetime(K.date).astype("int64").to_numpy()
    e = d <= np.median(d)
    yrs = K.year.to_numpy()
    by = pd.Series(u).groupby(yrs).sum() / pd.Series(r).groupby(yrs).sum()
    ov = (K.side == "over").to_numpy()
    side = "".join(f" {nm} {m.sum()} {100*u[m].sum()/r[m].sum():+.1f}%" for nm, m in (("over", ov), ("under", ~ov))
                   if m.sum())
    clv_s = f"CLV {100*clv:+5.2f}% " if clv_col else ""
    print(f"{label:60} {len(u):4d} bets {u.sum():+7.1f}u {100*u.sum()/r.sum():+6.2f}% [{lo:+5.1f},{hi:+5.1f}] "
          f"{clv_s}early {100*u[e].sum()/r[e].sum():+6.1f}% late {100*u[~e].sum()/r[~e].sum():+6.1f}% "
          f"years+ {(by>0).sum()}/{len(by)} |{side}")
    return u, r


def lock_model(W, books, cut, min_lead=1.0, stage="daily", xb=None, sides=("over", "under")):
    """At each pull, the model's P(over) from Pinnacle's no-vig; the quote at
    `books` at the same line in the same pull; first clearing pull locks."""
    keep = ((W.stage == stage) & (W.lead_h >= min_lead)).to_numpy()
    xb = W.xb.to_numpy()[keep] if xb is None else xb
    W = W[keep]
    W = W.assign(p_over=sig(logit(W.fair_over) + xb))
    S = T[T.book.isin(books) & (T.stage == stage)][["game_id", "served_at", "book", "line", "over", "under"]]
    J = W[["game_id", "served_at", "line", "p_over", "over_won", "year", "date", "lead_h", "five", "women_f"]].merge(
        S, on=["game_id", "served_at", "line"])
    eo = J.p_over * dec(J.over) - 1
    eu = (1 - J.p_over) * dec(J.under) - 1
    if sides == ("over",):
        eu = eu * 0 - 9
    J = J.assign(side=np.where(eo >= eu, "over", "under"), ev=np.maximum(eo, eu),
                 price=np.where(eo >= eu, J.over, J.under))
    J = J[(J.ev >= cut) & (J.price >= -300)]
    return J.sort_values(["served_at", "ev"], ascending=[True, False]).groupby("game_id").head(1)


def logloss(y, p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()


if __name__ == "__main__":
    print("noon pulls: served_at hour (UTC) of daily rows",
          T[T.stage == "daily"].served_at.dt.hour.value_counts().head(2).to_dict(),
          "| fights with a Pinnacle total", T[T.book == "pinnacle"].game_id.nunique(),
          "| with a DraftKings total", T[T.book == "draftkings"].game_id.nunique())

    print("\n== 4. Is the data right: how often the over won against Pinnacle's no-vig over, last pull")
    last = P_all.sort_values("served_at").groupby(["game_id", "line"]).tail(1)
    agg = dict(n=("over_won", "size"), over_won=("over_won", "mean"), no_vig_over=("fair_over", "mean"))
    print(last.groupby("line").agg(**agg).round(3).to_string())
    print(last[last.line.isin(LINES)].groupby(["line", "year"]).agg(**agg).round(3).unstack(0).to_string())
    print(last[last.line.isin(LINES)].assign(rounds=last.sched).groupby(["line", "rounds"]).agg(**agg).round(3)
          .to_string())

    print("\n== 2. Market structure")
    print("   margin (sum of implied probabilities - 1), mean over every pull:")
    for book in ("pinnacle", "draftkings"):
        X = T[T.book == book]
        m = (1 / dec(X.over) + 1 / dec(X.under) - 1)
        print("   ", book, pd.Series(m, index=X.index).groupby(X.line).mean().round(4).to_dict())
    D = T[T.book == "draftkings"][["game_id", "served_at", "line", "over", "under", "over_won", "year", "date",
                                   "stage", "lead_h", "five", "women_f"]]
    J = D.merge(P[["game_id", "served_at", "line", "fair_over"]], on=["game_id", "served_at", "line"])
    eo = J.fair_over * dec(J.over) - 1
    eu = (1 - J.fair_over) * dec(J.under) - 1
    print(f"   DraftKings and Pinnacle at one line in the same pull: {len(J):,} pulls on {J.game_id.nunique()} "
          f"fights; DraftKings priced better than Pinnacle's no-vig on either side in {int(((eo > 0) | (eu > 0)).sum())}"
          f" pulls ({int((((eo > 0) | (eu > 0)) & (J.stage == 'daily')).sum())} of them noon pulls); "
          f"median DraftKings EV on its better side at Pinnacle's fair {100*np.median(np.maximum(eo, eu)):+.2f}%")
    J = J.assign(side=np.where(eo >= eu, "over", "under"), ev=np.maximum(eo, eu),
                 price=np.where(eo >= eu, J.over, J.under))
    for stage in ("daily", "cards"):
        K = J[(J.stage == stage) & (J.ev >= 0)].sort_values("served_at").groupby("game_id").head(1)
        report(f"2b DraftKings above Pinnacle's no-vig, {stage} pulls, EV>=0", K)
    print("   blind sides by line (CLV omitted: for a blind side it is only that side's margin)")
    for book in ("pinnacle", "draftkings"):
        X = T[T.book == book].sort_values("served_at")
        for when, Xw in (("first", X.groupby(["game_id", "line"]).head(1)),
                         ("last", X.groupby(["game_id", "line"]).tail(1))):
            for L, XL in Xw.groupby("line"):
                for side in ("over", "under"):
                    report(f"2a {book} {when} pull, {L} blind {side}", XL.assign(side=side, price=XL[side]),
                           clv_col=False)

    print(f"\n== 1. Pinnacle-anchored, walk-forward; ridge {RIDGE}")
    Wb, Wc = walk_forward("b"), walk_forward("c")
    print(f"   test years {sorted(Wb.year.unique().astype(int))}; log loss on the same Pinnacle pulls:")
    for nm, Wx in (("every pull", None), ("noon pulls", "daily"), ("last noon pull per fight and line", "last")):
        if Wx is None:
            m = np.ones(len(Wb), bool)
        elif Wx == "daily":
            m = (Wb.stage == "daily").to_numpy()
        else:
            m = Wb.index.isin(Wb[Wb.stage == "daily"].sort_values("served_at").groupby(["game_id", "line"])
                              .tail(1).index)
        y = Wb.over_won.to_numpy(float)[m]
        a = Wb.fair_over.to_numpy()[m]
        pb = sig(logit(a) + Wb.xb.to_numpy()[m])
        pc = sig(logit(a) + Wc.xb.to_numpy()[m])
        print(f"   {nm:36} n {m.sum():6d}  (a) no-vig {logloss(y, a):.5f}  (b) + intercepts {logloss(y, pb):.5f}"
              f"  (c) + fighter inputs {logloss(y, pc):.5f}")
        for L in LINES:
            mL = (Wb.line.to_numpy()[m] == L)
            print(f"      line {L}: n {mL.sum():6d}  (a) {logloss(y[mL], a[mL]):.5f}  (b) {logloss(y[mL], pb[mL]):.5f}"
                  f"  (c) {logloss(y[mL], pc[mL]):.5f}")
    bf = {Y: FITS[("b", RIDGE, Y)][1].round(3).tolist() for Y in sorted(Wb.year.unique().astype(int))}
    print("   intercepts by line (1.5, 2.5, 4.5) fitted for each test year:", bf)

    for kind, W in (("b", Wb), ("c", Wc)):
        print(f"   model ({kind}) at DraftKings, cut grid (noon pulls, first clearing pull locks):")
        for cut in CUTS:
            report(f"     ({kind}) EV>={cut:.2f}", lock_model(W, ["draftkings"], cut))
        report(f"     ({kind}) at Pinnacle's own price, not bettable, EV>={REPORT_CUT:.2f}",
               lock_model(W, ["pinnacle"], REPORT_CUT))
        K = lock_model(W, ["draftkings"], REPORT_CUT)
        print(f"     ({kind}) at DraftKings EV>={REPORT_CUT:.2f}, split:")
        for name, grp in (("line", K.line), ("rounds", K.five.map({1.0: "five", 0.0: "three"})),
                          ("lead days", pd.cut(K.lead_h / 24, [0, 1, 3, 7, 400]))):
            for k, Kg in K.groupby(grp, observed=True):
                report(f"       {name} {k}", Kg)

    K = lock_model(Wc, ["draftkings"], REPORT_CUT)
    real_u, real_r, _ = grade(K)
    rng = np.random.default_rng(5)
    keep = ((Wc.stage == "daily") & (Wc.lead_h >= 1.0)).to_numpy()
    Wd = Wc[keep]
    fights = Wd.groupby("game_id")[FIGHT_Z + ["year"]].first()
    pl = []
    for _ in range(50):
        donor = fights.copy()
        for yy in fights.year.unique():
            ids = fights.index[fights.year == yy]
            donor.loc[ids, FIGHT_Z] = fights.loc[rng.permutation(ids), FIGHT_Z].to_numpy()
        Zp = Wd[["game_id", "year", "mismatch"] + FREE].join(donor[FIGHT_Z], on="game_id")
        xb = np.zeros(len(Zp))
        for yy in Zp.year.unique():
            bp, bfr, mu, sd = FITS[("c", RIDGE, int(yy))]
            m = (Zp.year == yy).to_numpy()
            xb[m] = ((Zp.loc[m, Z] - mu) / sd).fillna(0.0).to_numpy() @ bp + Zp.loc[m, FREE].to_numpy() @ bfr
        up, rp, _ = grade(lock_model(Wd, ["draftkings"], REPORT_CUT, xb=xb))
        pl.append(100 * up.sum() / rp.sum() if len(up) else np.nan)
    pl = np.array(pl)
    print(f"   (c) placebo, each fight's inputs from another fight of the same year, 50 draws: real "
          f"{100*real_u.sum()/real_r.sum():+.2f}% on {len(real_u)}; placebo median {np.nanmedian(pl):+.2f}%, "
          f"p95 {np.nanpercentile(pl, 95):+.2f}%, max {np.nanmax(pl):+.2f}%")
    bp = FITS[("c", RIDGE, int(max(Wc.year)))][0]
    print("   (c) inputs, last fit, standardised:",
          ", ".join(f"{z} {v:+.3f}" for z, v in sorted(zip(Z, bp), key=lambda t: -abs(t[1]))[:10]))
    for lam in (3.0, 300.0):
        report(f"   (c) ridge {lam:g} at DraftKings, EV>={REPORT_CUT:.2f}",
               lock_model(walk_forward("c", lam), ["draftkings"], REPORT_CUT))

    print("\n   the 4.5 over as a walk-forward rule: the line-4.5 bias from earlier years only, over side only")
    W45 = Wb[Wb.line == 4.5]
    for cut in (0.0, 0.02, 0.04, 0.06):
        for books in (["draftkings"], ["pinnacle"]):
            out = report(f"     over 4.5 at {books[0]}{' (not bettable)' if books[0] == 'pinnacle' else ''}, "
                         f"EV>={cut:.2f}", lock_model(W45, books, cut, sides=("over",)))
            if out is not None and cut == 0.0:
                u, r = out
                lo, hi = ci(u, r)
                ret = u.sum() / r.sum()
                need = len(u) * ((hi - lo) / 2 / 100 / ret) ** 2 if ret > 0 else np.inf
                print(f"       at this return the 90% interval clears zero at about {need:.0f} bets "
                      f"(has {len(u)})")

    print("\n== 3. Mechanisms of this study's own")
    dk_t = T[T.book == "draftkings"][["game_id", "served_at", "line", "over", "under", "over_won", "year", "date",
                                     "lead_h", "five"]]
    dk_h = H[H.book == "draftkings"][["game_id", "served_at", "pa", "pb"]]
    M = dk_t.merge(dk_h, on=["game_id", "served_at"]).sort_values(["game_id", "line", "served_at"])
    M["mis"] = np.abs(novig(M.pa, M.pb) - 0.5)
    g = M.groupby(["game_id", "line"])
    M["d_mis"] = M.mis - g.mis.shift(1)
    M["same_total"] = (M.over == g.over.shift(1)) & (M.under == g.under.shift(1))
    print(f"   M1: DraftKings pulls with the total unchanged from its previous pull and the moneyline moved "
          f"3+ points: {int((M.same_total & (M.d_mis.abs() >= 0.03)).sum())}")
    for thr in (0.02, 0.03, 0.05):
        S = M[M.same_total & (M.d_mis.abs() >= thr)]
        K = S.assign(side=np.where(S.d_mis > 0, "under", "over"))
        K = K.assign(price=np.where(K.side == "under", K.under, K.over))
        report(f"M1 DraftKings total stale after a {thr:.2f} moneyline move",
               K.sort_values("served_at").groupby("game_id").head(1))
    for book in ("pinnacle", "draftkings"):
        X = T[T.book == book].sort_values("served_at").groupby(["game_id", "line"]).tail(1)
        for name, m in (("women", X.women_f == 1.0), ("men's flyweight", (X.wc == "flw") & (X.women_f == 0.0)),
                        ("heavyweight", X.wc == "hw")):
            report(f"M2 {book} last pull, {name}, blind over", X[m].assign(side="over", price=X[m].over),
                   clv_col=False)
    for book in ("pinnacle", "draftkings"):
        X = T[(T.book == book) & (T.sched == 5)].sort_values("served_at").groupby(["game_id", "line"]).tail(1)
        for side in ("over", "under"):
            report(f"M3 {book} last pull, five-round fights, blind {side}", X.assign(side=side, price=X[side]),
                   clv_col=False)

    print("\n== Stuck ladder, the rungs that run on stored prices")
    # rung 4, the moment: model (b) decided on the card-day pulls instead of noon
    for cut in (0.0, 0.02, 0.04):
        report(f"rung 4: (b) at DraftKings on card-day pulls, EV>={cut:.2f}",
               lock_model(Wb, ["draftkings"], cut, stage="cards"))
    # rung 5, the hindsight ceiling: had we known Pinnacle's close, what DraftKings' noon price earned
    Dn = T[(T.book == "draftkings") & (T.stage == "daily")].copy()
    cf = np.array([pclose_fair.get((g, l), np.nan) for g, l in zip(Dn.game_id, Dn.line)])
    eo, eu = cf * dec(Dn.over) - 1, (1 - cf) * dec(Dn.under) - 1
    Dn = Dn.assign(side=np.where(eo >= eu, "over", "under"), ev=np.maximum(eo, eu),
                   price=np.where(eo >= eu, Dn.over, Dn.under))
    print(f"   rung 5: DraftKings noon pulls priced above Pinnacle's own close: "
          f"{int((Dn.ev > 0).sum())} of {len(Dn):,} pulls, on {Dn[Dn.ev > 0].game_id.nunique()} fights")
    report("rung 5: hindsight ceiling, first such DraftKings noon pull", Dn[Dn.ev > 0].sort_values("served_at")
           .groupby("game_id").head(1))
    # rung 3, the information: a short-notice bout (first listed under 7 days out) finishes more than priced
    fq = Q.groupby("game_id").lead_h.max() / 24
    for book in ("pinnacle", "draftkings"):
        X = T[T.book == book].sort_values("served_at").groupby(["game_id", "line"]).tail(1)
        X = X.assign(first_seen=X.game_id.map(fq))
        for nm, m in (("first listed under 7 days out", X.first_seen < 7), ("listed 7+ days out", X.first_seen >= 7)):
            for side in ("over", "under"):
                report(f"M4 {book} last pull, {nm}, blind {side}", X[m].assign(side=side, price=X[m][side]),
                       clv_col=False)

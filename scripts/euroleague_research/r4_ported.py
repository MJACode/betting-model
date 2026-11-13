"""Round 4, experiment 3: the halftime game-state method, ported unchanged
(walk-forward by season), on the total, then the spread and the moneyline;
then the pre-registered variants V1-V4, and V5 (fresh rule removed) as a kill
test. Every pooled walk-forward cell (market x cut x rule) is registered."""
from __future__ import annotations

import numpy as np
import pandas as pd

import r4_lib as L

MKTS = ["totals", "spreads", "h2h"]
NAME = {"totals": "total", "spreads": "spread", "h2h": "moneyline"}


def fitted_constants() -> str:
    rows = []
    for s in [2022] + L.WF_SEASONS:
        m = L.model_for(s)
        bt, st = m["t"]["b"], m["t"]["s"]
        bm, sm = m["m"]["b"], m["m"]["s"]
        rows.append({"graded season": L.SEASON_NAME[s], "fitted on": ",".join(L.SEASON_NAME[x] for x in m["train"]),
                     "states": m["n_states"],
                     "total: share of prior still to come at the half": round(0.5 * bt[0], 4),
                     "total: share of the surprise carried": round(0.5 * bt[1] + 0.25 * bt[2], 4),
                     "total: sd at the half": round(float(np.sqrt(st[0] + 0.5 * st[1] + 0.25 * st[2])), 2),
                     "margin: share of prior still to come": round(0.5 * bm[0], 4),
                     "margin: share of the surprise carried": round(0.5 * bm[1] + 0.25 * bm[2], 4),
                     "margin: sd at the half": round(float(np.sqrt(sm[0] + 0.5 * sm[1] + 0.25 * sm[2])), 2)})
    return L.md(rows)


def oos_check() -> str:
    """Out of sample at the break: the model's second-half mean and sd against what happened."""
    g = L.games()
    rows = []
    for s in [2022] + L.WF_SEASONS:
        x = g[g.qual & (g.season == s)]
        m = L.model_for(s)
        f = np.full(len(x), 0.5)
        mt, sdt = L.predict(m, "t", f, x.ht_m, x.ht_t, x.prior_m, x.prior_t)
        mm, sdm = L.predict(m, "m", f, x.ht_m, x.ht_t, x.prior_m, x.prior_t)
        et = (x.total - x.ht_t) - mt
        em = (x.margin - x.ht_m) - mm
        rows.append({"season": L.SEASON_NAME[s], "games": len(x),
                     "total: mean error": round(et.mean(), 2), "total: sd ratio": round((et / sdt).std(), 3),
                     "margin: mean error": round(em.mean(), 2), "margin: sd ratio": round((em / sdm).std(), 3)})
    return L.md(rows)


def counts(P: pd.DataFrame, min_others=L.MIN_OTHERS, need_fresh=True) -> str:
    rows = []
    for mkt in MKTS:
        for s in [2022] + L.WF_SEASONS:
            x = P[(P.market == mkt) & (P.season == s)]
            el = L.eligible(x, min_others, need_fresh)
            dec_g = x[el].game_id.nunique()
            # what blocks the rest: price band alone (every other condition met)
            base = x.decidable & x.inplay & x.priced & (x.fresh if need_fresh else True) & (x.others >= min_others)
            band = (x.price >= L.PRICE_BAND[0]) & (x.price <= L.PRICE_BAND[1])
            rows.append({"market": mkt, "season": L.SEASON_NAME[s], "games with a read in the break": x.game_id.nunique(),
                         "decided (an eligible quote)": dec_g,
                         "games with a fresh decidable quote but none in the price band": int(
                             len(set(x[base & ~band].game_id) - set(x[base & band].game_id))),
                         "games where fewer than 2 other books quote": int(
                             len(set(x[x.decidable & x.fresh & x.priced].game_id) - set(x[base].game_id)))})
    return L.md(rows)


def grid(P: pd.DataFrame, rule: str, how="first", min_others=L.MIN_OTHERS, need_fresh=True,
         register=True) -> tuple[list, dict]:
    rows, keep = [], {}
    for mkt in MKTS:
        x = P[P.market == mkt]
        for cut in L.CUTS:
            b = L.grade(L.decide(x, cut, how, min_others, need_fresh))
            wf = b[b.wf]
            lab = {"rule": rule, "market": NAME[mkt], "cut": cut}
            r = L.reg("3 " + rule, f"{NAME[mkt]} cut {cut}", wf) if register else L.row({}, wf)
            d = dict(lab)
            d.update({"seasons": "walk-forward 2022-23 to 2026-27"})
            d.update({k: r[k] for k in ("bets", "W", "L", "P", "units", "ret%", "lo%", "hi%")})
            rows.append(d)
            for s, xs in b.groupby("season"):
                rr = L.row({}, xs)
                d = dict(lab)
                d.update({"seasons": L.SEASON_NAME[s] + ("" if s != 2022 else " (second look, not walk-forward)")})
                d.update({k: rr[k] for k in ("bets", "W", "L", "P", "units", "ret%", "lo%", "hi%")})
                rows.append(d)
            keep[(mkt, cut)] = b
    return rows, keep


def ev_bands(P: pd.DataFrame) -> str:
    """Every decided game (no cut), by claimed EV band, walk-forward seasons."""
    rows = []
    d = L.grade(L.decided_games(P))
    d = d[d.wf]
    edges = [-np.inf, 0, 0.02, 0.05, 0.08, 0.12, 0.20, np.inf]
    labs = ["< 0", "0-0.02", "0.02-0.05", "0.05-0.08", "0.08-0.12", "0.12-0.20", ">= 0.20"]
    d["band"] = pd.cut(d.ev, edges, labels=labs, right=False)
    for mkt in MKTS:
        for bnd, x in d[d.market == mkt].groupby("band", observed=True):
            r = L.row({"market": NAME[mkt], "claimed EV band": str(bnd)}, x)
            r.pop("p_one", None)
            rows.append(r)
    return L.md(rows)


def calib(P: pd.DataFrame) -> str:
    d = L.grade(L.decided_games(P))
    d = d[d.wf & (d.res != 0)]
    rows = []
    edges = [0, 0.52, 0.55, 0.58, 0.62, 0.70, 1.01]
    d["pb"] = pd.cut(d.prob, edges, right=False)
    for mkt in MKTS:
        for b, x in d[d.market == mkt].groupby("pb", observed=True):
            rows.append({"market": NAME[mkt], "claimed band": str(b), "games": len(x),
                         "claimed": round(x.prob.mean(), 3), "won": round((x.res > 0).mean(), 3)})
    return L.md(rows)


def run() -> str:
    out = []
    P = L.priced_wf()
    out.append("### The fitted constants per walk-forward fold (read at the half, f = 0.5)\n\n" + fitted_constants())
    out.append("### Out of sample at the break: the model against what happened in the second half\n\n"
               "`mean error` = actual second-half points (or margin) minus the model's mean; `sd ratio` = the "
               "standard deviation of (error / the model's sd), 1.0 when the stated spread is right.\n\n" + oos_check())
    out.append("### How many games the ported rule can decide\n\n" + counts(P))
    rows, keep = grid(P, "ported unchanged")
    L._C["ported_keep"] = keep
    L._C["P"] = P
    out.append("### The ported rule, unchanged: first read in the break with an eligible quote, best EV there\n\n"
               "Walk-forward rows pool 2022-23 to 2026-27; 2021-22 is a second look (fitted on 2022-23) and is "
               "not pooled.\n\n" + L.md(rows))
    out.append("### Return by claimed EV band, every decided game, walk-forward seasons (bands, not nested cuts)\n\n"
               + ev_bands(P))
    out.append("### Claimed chance against won, every decided game (pushes out), walk-forward seasons\n\n" + calib(P))

    # variants
    vrows = []
    r, k = grid(P, "V1 no minimum of other books", min_others=0)
    vrows += [x for x in r if x["seasons"].startswith("walk")]
    L._C["V1_keep"] = k
    P2 = L.priced_wf(prior=("pin_m", "pin_t"))
    r, k = grid(P2, "V2 Pinnacle's close as the prior")
    vrows += [x for x in r if x["seasons"].startswith("walk")]
    L._C["V2_keep"] = k
    r, k = grid(P, "V3 last read of the break decides", how="last")
    vrows += [x for x in r if x["seasons"].startswith("walk")]
    L._C["V3_keep"] = k
    r, k = grid(P, "V4 first crossing", how="crossing")
    vrows += [x for x in r if x["seasons"].startswith("walk")]
    L._C["V4_keep"] = k
    out.append("### Variants V1-V4, pooled walk-forward 2022-23 to 2026-27\n\n" + L.md(vrows))
    r, k = grid(P, "V5 fresh rule removed (kill test)", need_fresh=False, register=False)
    L._C["V5_keep"] = k
    out.append("### V5, a kill test: the fresh rule removed, pooled walk-forward (not registered)\n\n"
               + L.md([x for x in r if x["seasons"].startswith("walk")]))
    return "\n\n".join(out)


if __name__ == "__main__":
    print(run())

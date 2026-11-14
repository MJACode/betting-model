"""Round 4: the kill tests on what read positive in experiment 3.

Candidates (pooled walk-forward 2022-23 to 2026-27, headline cut 0.05):
  A  the halftime spread, ported unchanged
  B  the halftime spread, variant V2 (Pinnacle's close as the prior)
Also run on the ported total at 0.12 (the one total cell above +5%) so its
read is on record.

Tests: by season, early/late, side split (home/away, favourite/underdog,
leader/trailer at the half, the side behind its expected first half), book,
price band, without its 10 best dates, the cut neighbourhood, the rule's bets
turned round, the market-alone control (every decided game bet blind on the
side the rule's mechanism favours, no EV cut), the fresh rule removed (V5),
the last read (V3), and a placebo: (ht_home, ht_away) shuffled across games
within each season, 200 times, re-priced and re-decided. Sub-rows are not
registered for Benjamini-Hochberg (their parent cell is)."""
from __future__ import annotations

import numpy as np
import pandas as pd

import r4_lib as L
import r3_lib as L3

N_SHUFFLE = 200


def add_cols(b: pd.DataFrame) -> pd.DataFrame:
    b = b.copy()
    prior_m = b["pin_m"] if b["_prior"].iloc[0] == "pinnacle" else b["prior_m"]
    sur = b.ht_m - 0.5 * prior_m                      # the home side's first-half surprise
    home = b.side == "home"
    b["behind_expectation"] = np.where(home, sur < 0, sur > 0)
    b["leader_at_half"] = np.where(b.ht_m == 0, "level", np.where(home == (b.ht_m > 0), "leader", "trailer"))
    return b


def kill_block(name: str, b: pd.DataFrame) -> list[dict]:
    rows = L3.kill_rows(name, b, side_cols=("side", "leader_at_half", "behind_expectation", "bookmaker"), fav_col="fav")
    for r in rows:
        r.pop("p_one", None)
    return rows


def turned_round(b: pd.DataFrame) -> pd.DataFrame:
    t = b.copy()
    sw = {"home": "away", "away": "home", "over": "under", "under": "over"}
    t["side"] = t.side.map(sw)
    t["price"] = b.other_price
    return L.grade(t)


def placebo(P: pd.DataFrame, market: str, cut: float, prior) -> np.ndarray:
    x = P[(P.market == market) & P.wf].copy()
    gm = x[["game_id", "season", "ht_home", "ht_away"]].drop_duplicates("game_id")
    rng = np.random.default_rng(20261113)
    models = {s: L.model_for(s, prior) for s in L.WF_SEASONS}
    rets = []
    for _ in range(N_SHUFFLE):
        perm = gm.copy()
        for s, idx in perm.groupby("season").groups.items():
            v = perm.loc[idx, ["ht_home", "ht_away"]].to_numpy()
            perm.loc[idx, ["ht_home", "ht_away"]] = v[rng.permutation(len(v))]
        mp = perm.set_index("game_id")
        hh, aa = x.game_id.map(mp.ht_home).to_numpy(float), x.game_id.map(mp.ht_away).to_numpy(float)
        parts = []
        for s in L.WF_SEASONS:
            k = (x.season == s).to_numpy()
            if k.any():
                parts.append(L.price(x[k], models[s], hh[k], aa[k], prior=prior))
        y = pd.concat(parts, ignore_index=True)
        b = L.grade(L.decide(y, cut))
        rets.append(100 * b.units.sum() / b.risk.sum() if len(b) and b.risk.sum() > 0 else np.nan)
    return np.array(rets)


def control_blind(P: pd.DataFrame, market: str, prior_col: str = "prior_m", which: str = "behind") -> pd.DataFrame:
    """Every decided game, no EV cut, bet blind at the deciding quote's book and
    line on: 'behind' / 'ahead' = the side behind / ahead of its expected first
    half (surprise = half-time margin - half the prior margin, home view);
    'underdog' = the side getting points at the half."""
    d = L.decided_games(P[(P.market == market) & P.wf])
    sur = d.ht_m - 0.5 * d[prior_col]
    if which == "behind":
        side, keep = np.where(sur < 0, "home", "away"), sur != 0
    elif which == "ahead":
        side, keep = np.where(sur > 0, "home", "away"), sur != 0
    else:
        side, keep = np.where(d.line > 0, "home", "away"), d.line != 0
    t = d.copy()
    flip = t.side != side
    t["price"] = np.where(flip, d.other_price, d.price)
    t["other_price"] = np.where(flip, d.price, d.other_price)
    t["side"] = side
    t = t[keep]
    t["fav"] = L.fav_flag(t)
    return L.grade(t)


def run() -> str:
    out = []
    P = L._C.get("P")
    if P is None:
        P = L.priced_wf()
    P = P.assign(_prior="median")
    P2 = L.priced_wf(prior=("pin_m", "pin_t")).assign(_prior="pinnacle")
    cands = [("A spread, ported unchanged, cut 0.05", P, "spreads", 0.05, ("prior_m", "prior_t")),
             ("B spread, V2 Pinnacle prior, cut 0.05", P2, "spreads", 0.05, ("pin_m", "pin_t")),
             ("C total, ported unchanged, cut 0.12", P, "totals", 0.12, ("prior_m", "prior_t")),
             # the null headline cells, so every experiment carries the same splits
             ("D total, ported unchanged, cut 0.05 (null; splits for the record)", P, "totals", 0.05, ("prior_m", "prior_t")),
             ("E moneyline, ported margin model, cut 0.05 (null; splits for the record)", P, "h2h", 0.05,
              ("prior_m", "prior_t"))]
    summary_lines = []
    for name, PP, mkt, cut, prior in cands:
        x = PP[PP.market == mkt]
        b = L.grade(L.decide(x, cut))
        b = add_cols(b[b.wf])
        rows = kill_block(name, b)
        # neighbourhood
        for c in L.CUTS:
            bb = L.grade(L.decide(x, c))
            r = L.row({"rule": name, "subset": f"neighbour cut {c}"}, bb[bb.wf])
            r.pop("p_one", None)
            rows.append(r)
        # turned round
        r = L.row({"rule": name, "subset": "the rule's bets turned round (other side, same quote)"}, turned_round(b))
        r.pop("p_one", None)
        rows.append(r)
        # V5 / V3 at the same cut
        for lab, kw in (("fresh rule removed (V5)", {"need_fresh": False}), ("last read decides (V3)", {"how": "last"})):
            bb = L.grade(L.decide(x, cut, **kw))
            r = L.row({"rule": name, "subset": lab}, bb[bb.wf])
            r.pop("p_one", None)
            rows.append(r)
        # 2021-22 second look
        r = L.row({"rule": name, "subset": "2021-22 second look (fitted on 2022-23)"},
                  L.grade(L.decide(x[x.season == 2022], cut)))
        r.pop("p_one", None)
        rows.append(r)
        if mkt == "spreads":
            for which, lab in (("behind", "behind its expected first half"), ("ahead", "ahead of its expected first half"),
                               ("underdog", "getting points at the half (the underdog)")):
                cb = control_blind(PP, mkt, prior[0], which)
                r = L.row({"rule": name, "subset": f"control: every decided game, blind on the side {lab}"}, cb)
                r.pop("p_one", None)
                rows.append(r)
            
        out.append(f"### {name}\n\nPrice range of the bets: {L.price_range(b)}.\n\n" + L.md(rows))
        pl = placebo(PP, mkt, cut, prior)
        real = 100 * b.units.sum() / b.risk.sum()
        out.append(f"Placebo for {name} ({N_SHUFFLE} shuffles of the half-time score across games within each "
                   f"season, re-priced and re-decided): mean {np.nanmean(pl):+.2f}%, 5th-95th percentile "
                   f"{np.nanpercentile(pl, 5):+.2f}% to {np.nanpercentile(pl, 95):+.2f}%; real {real:+.2f}%; "
                   f"share of shuffles at or above the real result {100 * np.nanmean(pl >= real):.1f}%.")
        best = b.groupby("game_date").units.sum().sort_values(ascending=False).head(10).index
        wo = b[~b.game_date.isin(best)]
        summary_lines.append({"rule": name, "bets": len(b), "units": round(b.units.sum(), 2),
                              "ret%": round(real, 2),
                              "placebo p95%": round(float(np.nanpercentile(pl, 95)), 2),
                              "share of shuffles >= real": round(float(np.nanmean(pl >= real)), 3),
                              "without 10 best dates ret%": round(100 * wo.units.sum() / wo.risk.sum(), 2),
                              "share on one side (max of home/away)": round(float(b.side.value_counts(normalize=True).max()), 3)})
    import r4_ported
    out.append("### Does return rise with the claimed edge? Every decided game under V2 (Pinnacle prior), by claimed "
               "EV band, walk-forward seasons\n\n" + r4_ported.ev_bands(P2))
    out.insert(0, "### The kill tests at a glance\n\n" + L.md(summary_lines))
    return "\n\n".join(out)


if __name__ == "__main__":
    print(run())

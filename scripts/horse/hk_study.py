"""Hong Kong win and place pools, 1997-2005: data checks, baselines, the
win-against-place pool test, and Bolton-Chapman plus Benter, walk-forward.

Reads the CC0 Kaggle set `gdaley/hkracing` (`scripts/horse/fetch_datasets.py`
downloads it; `scripts/horse/store_files.py` stores it in Supabase under source
`horse_racing|gdaley_hkracing`).

WHAT THESE PRICES ARE. `win_odds` and `place_odds` are the FINAL tote odds:
the price a pool bet is paid at, and the price a pool bet placed through a US
ADW that commingles with the Hong Kong Jockey Club would be paid at. They are
not what a bettor sees when deciding (the pools keep moving to the off and a
little after). So:
  * a rule graded at final odds is graded at the price the bet is paid at, and
  * a rule that DECIDES on final odds has seen the close. Every result here
    that conditions on final odds is an UPPER BOUND, an information test,
    not a units claim. The fundamentals-only stage-1 model decides on nothing
    from the race's own pool.

Dates in this set are obscured by its author, but race order and the gaps
between races are kept (checked: race_id order equals date order). Seasons are
cut at 1 September.

    python scripts/horse/hk_study.py [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
from scripts.horse.anz_study import harville_top, stake_units  # noqa: E402
from scripts.horse.clogit import fit_clogit, softmax_by_race, starts_of  # noqa: E402

DATA = ROOT_DIR / "data" / "horse" / "gdaley-hkracing"
BANDS = [1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 51.0, 1000.0]


def load(root: Path = DATA) -> tuple[pd.DataFrame, pd.DataFrame]:
    races = pd.read_csv(root / "races.csv")
    runs = pd.read_csv(root / "runs.csv")
    races["date"] = pd.to_datetime(races["date"])
    races["season"] = np.where(races.date.dt.month >= 9, races.date.dt.year, races.date.dt.year - 1)
    runs = runs.merge(races[["race_id", "date", "season", "venue", "surface", "distance", "going",
                             "race_class", "win_dividend1", "win_combination2"]], on="race_id")
    runs = runs.sort_values(["race_id", "horse_no"]).reset_index(drop=True)
    g = runs.groupby("race_id")
    runs["field"] = g["horse_id"].transform("size")
    runs["n_won"] = g["won"].transform("sum")
    runs["book"] = g["win_odds"].transform(lambda s: (1.0 / s).sum())
    runs["p_pub"] = (1.0 / runs.win_odds) / runs.book
    runs["places"] = np.where(runs.field >= 7, 3, np.where(runs.field >= 4, 2, 1))
    runs["placed"] = (runs.result <= runs.places).astype(int)
    return races, runs


def clean(runs: pd.DataFrame) -> pd.DataFrame:
    """Races fit to grade: one winner, every runner priced, a pool book in the
    normal range (the few with a book under 1.1 or over 1.35 are data errors)."""
    ok = (runs.n_won == 1) & runs.book.between(1.10, 1.35)
    return runs[ok].copy()


def summarise(f: pd.DataFrame, price: str, won: str) -> dict:
    f = f[f[price].notna() & (f[price] > 1.0)]
    if f.empty:
        return {"bets": 0}
    profit, risk = stake_units(f[price].to_numpy(), f[won].to_numpy(float), 0.0)
    by = pd.DataFrame({"m": f.race_id.to_numpy(), "p": profit, "r": risk}).groupby("m").sum()
    roi = by.p.sum() / by.r.sum()
    se = math.sqrt(((by.p - roi * by.r) ** 2).sum()) / by.r.sum()
    flat = np.where(f[won] > 0, f[price] - 1.0, -1.0).mean()
    return {"bets": int(len(f)), "wins": int(f[won].sum()), "units": float(profit.sum()),
            "risk": float(risk.sum()), "roi": float(roi), "lo": float(roi - 1.96 * se),
            "hi": float(roi + 1.96 * se), "flat_roi": float(flat)}


def fmt(r: dict) -> str:
    if not r.get("bets"):
        return "0 bets"
    return (f"{r['bets']:>7,} bets {r['units']:>+9.1f}u  return {100 * r['roi']:+6.2f}% "
            f"[{100 * r['lo']:+6.2f}, {100 * r['hi']:+6.2f}]  flat {100 * r['flat_roi']:+6.2f}%")


# ---------------------------------------------------------------- features

GROUPS = {
    "form": ["last_pos", "avg_pos3", "last_lb", "n_prev_log", "debut"],
    "rating_weight": ["rating", "rating_chg", "act_wt", "decl_wt_chg"],
    "draw": ["draw_n", "draw_hv"],
    "connections": ["jockey_rate", "trainer_rate"],
    "speed": ["last_speed", "best_speed3"],
    "layoff_trip": ["days_log", "dist_chg", "surf_chg", "age"],
    "past_odds": ["last_logodds"],
}


def features(runs: pd.DataFrame) -> pd.DataFrame:
    """Everything is known the morning of the race: built only from earlier rows."""
    r = runs.copy()
    r["pos_n"] = (r.result - 1) / (r.field - 1).clip(lower=1)
    # par time per (venue, surface, distance), from EARLIER races only
    r = r.sort_values(["race_id", "horse_no"]).reset_index(drop=True)
    key = r.venue.astype(str) + "|" + r.surface.astype(str) + "|" + r.distance.astype(str)
    winners = r[r.won == 1][["race_id", "finish_time"]].assign(key=key[r.won == 1].values)
    winners = winners.sort_values("race_id")
    gk = winners.groupby("key").finish_time
    winners["par"] = gk.transform(lambda s: s.shift().expanding().mean())
    winners["par_sd"] = gk.transform(lambda s: s.shift().expanding().std())
    r = r.merge(winners[["race_id", "par", "par_sd"]], on="race_id", how="left")
    r["speed"] = -(r.finish_time - r.par) / r.par_sd.clip(lower=0.3)

    h = r.groupby("horse_id")
    r["n_prev"] = h.cumcount()
    r["debut"] = (r.n_prev == 0).astype(float)
    r["n_prev_log"] = np.log1p(r.n_prev)
    r["last_pos"] = h.pos_n.shift()
    r["avg_pos3"] = h.pos_n.transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
    r["last_lb"] = h.lengths_behind.shift().clip(upper=30)
    r["rating"] = r.horse_rating
    r["rating_chg"] = r.horse_rating - h.horse_rating.shift()
    r["act_wt"] = r.actual_weight
    r["decl_wt_chg"] = r.declared_weight - h.declared_weight.shift()
    r["draw_n"] = (r.draw - 1) / (r.field - 1).clip(lower=1)
    r["draw_hv"] = r.draw_n * (r.venue == "HV")
    r["last_speed"] = h.speed.shift()
    r["best_speed3"] = h.speed.transform(lambda s: s.shift().rolling(3, min_periods=1).max())
    r["days_log"] = np.log1p((r.date - h.date.shift()).dt.days)
    r["dist_chg"] = np.log(r.distance / h.distance.shift())
    r["surf_chg"] = (r.surface != h.surface.shift()).astype(float)
    r["age"] = r.horse_age
    r["last_logodds"] = np.log(h.win_odds.shift())
    for who in ("jockey", "trainer"):
        g = r.groupby(f"{who}_id")
        wins = g.won.transform(lambda s: s.shift().fillna(0).cumsum())
        rides = g.cumcount()
        r[f"{who}_rate"] = (wins + 20 * 0.08) / (rides + 20)
    # within-race standardisation; a missing value is the race mean, and the
    # debut flag carries the fact that it was missing (never filled as 0)
    cols = [c for gs in GROUPS.values() for c in gs if c != "debut"]
    for c in cols:
        gm = r.groupby("race_id")[c]
        mu = gm.transform("mean")
        sd = gm.transform("std").replace(0, np.nan)
        r[c] = ((r[c] - mu) / sd).fillna(0.0)
    r["debut"] = r.debut - r.groupby("race_id").debut.transform("mean")
    return r


# ---------------------------------------------------------------- conditional logit

def race_ll(p: np.ndarray, won: np.ndarray) -> float:
    return float(np.log(np.clip(p[won == 1], 1e-12, 1)).mean())


def walk_forward(r: pd.DataFrame, cols: list[str], seasons: list[int]) -> pd.DataFrame:
    """For each graded season s: stage 1 on seasons <= s-2, stage 2 (Benter) on
    s-1, applied to s. Returns the graded rows with p_model, p_pubcal, p_star."""
    out = []
    for s in seasons:
        tr = r[r.season <= s - 2]
        ho = r[r.season == s - 1]
        te = r[r.season == s]
        if tr.race_id.nunique() < 500 or ho.empty or te.empty:
            continue
        b1 = fit_clogit(tr[cols].to_numpy(), tr.won.to_numpy(), starts_of(tr))
        for d in (ho, te):
            d.loc[:, "p_model"] = softmax_by_race(d[cols].to_numpy() @ b1, starts_of(d))
        Z_ho = np.c_[np.log(ho.p_model), np.log(ho.p_pub)]
        b2 = fit_clogit(Z_ho, ho.won.to_numpy(), starts_of(ho), l2=1e-3)
        bp = fit_clogit(np.log(ho.p_pub.to_numpy())[:, None], ho.won.to_numpy(), starts_of(ho), l2=1e-3)
        te = te.copy()
        te["p_model"] = softmax_by_race(te[cols].to_numpy() @ b1, starts_of(te))
        te["p_star"] = softmax_by_race(np.c_[np.log(te.p_model), np.log(te.p_pub)] @ b2, starts_of(te))
        te["p_pubcal"] = softmax_by_race(np.log(te.p_pub.to_numpy()) * bp[0], starts_of(te))
        te["b_model"], te["b_public"], te["b_pub_only"] = b2[0], b2[1], bp[0]
        out.append(te)
    return pd.concat(out) if out else pd.DataFrame()


def recent_check(root: Path) -> dict:
    """Blind win bets at final odds, 2014-2017 (lantanacamara set, licence
    unknown, research only). The site this set was taken from shows odds
    above 99 as 99, so longshot prices are a floor, not the price paid."""
    if not (root / "race-result-horse.csv").exists():
        return {"skipped": "file not on disk"}
    h = pd.read_csv(root / "race-result-horse.csv", dtype=str)
    h["pos"] = pd.to_numeric(h.finishing_position.str.extract(r"^(\d+)")[0], errors="coerce")
    h["dh"] = h.finishing_position.str.contains("DH", na=False)
    h["win_odds"] = pd.to_numeric(h.win_odds, errors="coerce")
    h = h[h.pos.notna() & h.win_odds.notna()].copy()
    h["won"] = (h.pos == 1).astype(int)
    nw = h.groupby("race_id").won.transform("sum")
    h = h[nw == 1].copy()
    out = {"races": int(h.race_id.nunique()), "runners": int(len(h)),
           "share_at_99": float((h.win_odds >= 99).mean()), "bands": []}
    print(f"\n== Hong Kong 2014-2017, blind win bets at final odds ({out['races']:,} races; "
          f"{100 * out['share_at_99']:.1f}% of runners shown at the 99 cap)")
    h["band"] = pd.cut(h.win_odds, BANDS)
    for k, g in h.groupby("band", observed=True):
        rr = summarise(g, "win_odds", "won")
        out["bands"].append({"band": str(k), **rr})
        print(f"  {str(k):14s} {fmt(rr)}")
    fav = h[h.groupby("race_id").win_odds.rank(method="first") == 1]
    out["favourite"] = summarise(fav, "win_odds", "won")
    print(f"  favourite      {fmt(out['favourite'])}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    ap.add_argument("--root", type=Path, default=DATA)
    a = ap.parse_args(argv)
    races, runs = load(a.root)
    out: dict = {}

    print("== data checks")
    rid_order = (races.sort_values("race_id").date.diff().dt.days.fillna(0) >= 0).mean()
    w = runs[runs.won == 1]
    chk = {"races": int(runs.race_id.nunique()), "runners": int(len(runs)),
           "race_id_in_date_order": float(rid_order),
           "races_not_one_winner": int((runs.groupby("race_id").won.sum() != 1).sum()),
           "book_median": float(runs.groupby("race_id").book.first().median()),
           "book_outside_1.10_1.35": int((~runs.groupby("race_id").book.first().between(1.10, 1.35)).sum()),
           "winner_odds_x10_over_dividend_median": float((w.win_odds * 10 / w.win_dividend1).median()),
           "place_odds_missing": float(runs.place_odds.isna().mean()),
           "seasons": {int(k): int(v) for k, v in races.season.value_counts().sort_index().items()}}
    chk["takeout_implied_by_median_book"] = 1 - 1 / chk["book_median"]
    out["checks"] = chk
    print(json.dumps(chk, indent=1))
    c = clean(runs)
    out["clean"] = {"races": int(c.race_id.nunique()), "runners": int(len(c))}

    print("\n== calibration of the final win pool (pool share against the win rate)")
    b = pd.cut(c.p_pub, [0, .02, .05, .1, .2, .3, .4, .5, 1.0])
    cal = c.groupby(b, observed=True).agg(n=("won", "size"), said=("p_pub", "mean"), won=("won", "mean"))
    out["calibration"] = [{"band": str(k), "n": int(v.n), "said": float(v.said), "won": float(v.won)}
                          for k, v in cal.iterrows()]
    for k, v in cal.iterrows():
        print(f"  {str(k):12s} n={int(v.n):>6,} said {v.said:.4f} won {v.won:.4f} gap {100 * (v.won - v.said):+.2f}pt")

    print("\n== blind win bets at final odds, by odds band")
    c["band"] = pd.cut(c.win_odds, BANDS)
    out["blind_by_band"] = []
    for k, g in c.groupby("band", observed=True):
        rr = summarise(g, "win_odds", "won")
        out["blind_by_band"].append({"band": str(k), **rr})
        print(f"  {str(k):14s} {fmt(rr)}")
    fav = c[c.groupby("race_id").win_odds.rank(method="first") == 1]
    out["favourite"] = summarise(fav, "win_odds", "won")
    print(f"  favourite      {fmt(out['favourite'])}")
    # Happy Valley's pools are the smaller meeting; a thinner pool is where a
    # longshot bias would show if it shows anywhere.
    out["by_venue"] = {}
    for v, gv in c.groupby("venue"):
        out["by_venue"][v] = {"favourite": summarise(gv[gv.groupby("race_id").win_odds.rank(method="first") == 1],
                                                     "win_odds", "won"),
                              "under_5": summarise(gv[gv.win_odds <= 5], "win_odds", "won"),
                              "over_20": summarise(gv[gv.win_odds > 20], "win_odds", "won")}
        for k, r in out["by_venue"][v].items():
            print(f"  {v} {k:10s} {fmt(r)}")

    print("\n== place pool against the win pool (Harville from final win shares; final-odds upper bound)")
    pl = c[c.place_odds.notna() & (c.place_odds > 1.0) & (c.field >= 7)].copy()
    pl = pl[pl.groupby("race_id").place_odds.transform("count") == pl.field]
    hv = pd.Series(np.nan, index=pl.index)
    for _, idx in pl.groupby("race_id").indices.items():
        hv.iloc[idx] = harville_top(pl.p_pub.to_numpy()[idx], 3)
    pl["p_place"] = hv
    pl["ev_place"] = pl.p_place * pl.place_odds - 1
    out["place"] = []
    for cut in [-1.0, 0.0, 0.05, 0.10, 0.15, 0.20, 0.30]:
        g = pl[pl.ev_place > cut]
        rr = summarise(g, "place_odds", "placed")
        out["place"].append({"ev_cut": cut, **rr})
        print(f"  Harville EV > {cut:+.2f}  {fmt(rr)}")
    calp = pl.groupby(pd.cut(pl.p_place, [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1]), observed=True).agg(
        n=("placed", "size"), said=("p_place", "mean"), placed=("placed", "mean"))
    out["harville_calibration"] = [{"band": str(k), "n": int(v.n), "said": float(v.said), "placed": float(v.placed)}
                                   for k, v in calp.iterrows()]
    for k, v in calp.iterrows():
        print(f"  Harville {str(k):12s} n={int(v.n):>6,} said {v.said:.3f} placed {v.placed:.3f}")

    # Harville over-rates short horses for a place (above). Calibrate it on the
    # early seasons, grade the later ones: logistic on logit(Harville), field size.
    from sklearn.linear_model import LogisticRegression
    pl["lh"] = np.log(pl.p_place.clip(1e-4, 1 - 1e-4) / (1 - pl.p_place.clip(1e-4, 1 - 1e-4)))
    pl["lf"] = np.log(pl.field)
    cut_season = 2000
    fit = pl[pl.season <= cut_season]
    test = pl[pl.season > cut_season].copy()
    lr = LogisticRegression(C=1e6).fit(fit[["lh", "lf"]], fit.placed)
    test["p_place_cal"] = lr.predict_proba(test[["lh", "lf"]])[:, 1]
    test["ev_cal"] = test.p_place_cal * test.place_odds - 1
    out["place_calibrated"] = {"fit_seasons": f"<= {cut_season}", "coef": lr.coef_.tolist(),
                               "intercept": float(lr.intercept_[0]), "rows": []}
    print(f"  calibrated on seasons <= {cut_season}, graded on later seasons "
          f"({test.race_id.nunique():,} races)")
    for cut in [0.0, 0.05, 0.10, 0.15, 0.20]:
        g = test[test.ev_cal > cut]
        rr = summarise(g, "place_odds", "placed")
        yrs = {int(s): summarise(gg, "place_odds", "placed") for s, gg in g.groupby("season")}
        out["place_calibrated"]["rows"].append({"ev_cut": cut, **rr, "by_season": yrs})
        print(f"  calibrated EV > {cut:+.2f}  {fmt(rr)}")
        for s, v in yrs.items():
            print(f"      {s}  {fmt(v)}")
    pbook = pl.groupby("race_id").apply(lambda g: (1 / g.place_odds).sum() / g.places.iloc[0])
    out["place_book_median"] = float(pbook.median())
    print(f"  place pool: median sum(1/place_odds)/places = {pbook.median():.4f}")

    # The 7-runner boundary: three places are paid from 7 runners, two below,
    # so a 7-runner field is the most generous place contract on the card.
    # Every runner, at final place odds, by field size (both terms).
    pf = c[c.place_odds.notna() & (c.place_odds > 1.0) & (c.field >= 4)]
    out["place_by_field"] = {}
    print("  blind place bets at final place odds, by field size")
    for n, g in pf.groupby(pf.field.clip(upper=14)):
        rr = summarise(g, "place_odds", "placed")
        short = summarise(g[g.win_odds <= 5], "place_odds", "placed")
        out["place_by_field"][int(n)] = {"all": rr, "win_odds_5_or_shorter": short}
        print(f"  {int(n):>2} runners  all {fmt(rr)}")
        print(f"  {'':11} win odds <= 5 {fmt(short)}")

    print("\n== Bolton-Chapman (fundamentals) + Benter blend, walk-forward by season")
    f = features(c)
    cols = [x for gs in GROUPS.values() for x in gs]
    seasons = sorted(f.season.unique())
    graded_seasons = [s for s in seasons if s >= seasons[0] + 3]
    wf = walk_forward(f, cols, graded_seasons)
    res = {"graded_seasons": [int(s) for s in sorted(wf.season.unique())],
           "races": int(wf.race_id.nunique())}
    for col in ["p_pub", "p_pubcal", "p_model", "p_star"]:
        res[f"ll_{col}"] = race_ll(wf[col].to_numpy(), wf.won.to_numpy())
    res["coef_by_season"] = wf.groupby("season")[["b_model", "b_public", "b_pub_only"]].first().round(4).to_dict("index")
    print(json.dumps({k: v for k, v in res.items() if k != "coef_by_season"}, indent=1))
    for s, v in res["coef_by_season"].items():
        print(f"  season {s}: b_model {v['b_model']:+.3f}  b_public {v['b_public']:+.3f}  public-only {v['b_pub_only']:+.3f}")

    # betting: one bet per race, the runner with the largest EV, at final odds
    wf["ev"] = wf.p_star * wf.win_odds - 1
    wf["ev_cal"] = wf.p_pubcal * wf.win_odds - 1
    top = wf.loc[wf.groupby("race_id").ev.idxmax()]
    top_cal = wf.loc[wf.groupby("race_id").ev_cal.idxmax()]
    res["bets"] = []
    for cut in [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50]:
        g = top[top.ev > cut]
        gc = top_cal[top_cal.ev_cal > cut]
        rr = summarise(g, "win_odds", "won")
        rc = summarise(gc, "win_odds", "won")
        half = sorted(g.season.unique())
        early = summarise(g[g.season <= half[len(half) // 2 - 1]], "win_odds", "won") if len(half) > 1 else {}
        late = summarise(g[g.season > half[len(half) // 2 - 1]], "win_odds", "won") if len(half) > 1 else {}
        res["bets"].append({"ev_cut": cut, "blend": rr, "public_calibrated_only": rc,
                            "early": early, "late": late})
        print(f"  EV > {cut:.2f} blend  {fmt(rr)}")
        print(f"  {'':10} early  {fmt(early)}")
        print(f"  {'':10} late   {fmt(late)}")
        print(f"  {'':10} public-calibrated only {fmt(rc)}")
    out["benter"] = res

    print("\n== ablation: remove one feature group, out-of-sample log-likelihood of the blend")
    abl = {}
    for gname, gcols in GROUPS.items():
        keep = [x for x in cols if x not in gcols]
        w2 = walk_forward(f, keep, graded_seasons)
        abl[gname] = {"ll_p_model": race_ll(w2.p_model.to_numpy(), w2.won.to_numpy()),
                      "ll_p_star": race_ll(w2.p_star.to_numpy(), w2.won.to_numpy())}
        print(f"  without {gname:14s} model {abl[gname]['ll_p_model']:.5f}  blend {abl[gname]['ll_p_star']:.5f}")
    out["ablation"] = abl

    # The harness has to catch a leak, or its null means nothing. Add the
    # race's OWN speed figure (from its own finish time) and the same
    # walk-forward must light up: the model beats the pool and b_model jumps.
    print("\n== leak check: the race's own speed figure added (must look far too good)")
    f["own_speed_leak"] = f.groupby("race_id").speed.transform(
        lambda s: (s - s.mean()) / (s.std() if s.std() > 0 else 1.0)).fillna(0.0)
    wl = walk_forward(f, cols + ["own_speed_leak"], graded_seasons)
    leak = {"ll_p_model": race_ll(wl.p_model.to_numpy(), wl.won.to_numpy()),
            "ll_p_star": race_ll(wl.p_star.to_numpy(), wl.won.to_numpy()),
            "b_model_by_season": wl.groupby("season").b_model.first().round(3).to_dict()}
    out["leak_check"] = leak
    print(f"  model {leak['ll_p_model']:.4f}  blend {leak['ll_p_star']:.4f}  "
          f"b_model {leak['b_model_by_season']}")

    out["recent_2014_2017"] = recent_check(a.root.parent / "lantanacamara-hong-kong-horse-racing")

    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

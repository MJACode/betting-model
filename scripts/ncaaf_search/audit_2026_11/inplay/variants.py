"""Two follow-ups, BOTH DEFINED AFTER the plain grid (grid.py) had been read.
They are robustness reads, not selections: no cut, band or window in here was
moved after its own result was seen, and each is run once.

V3, "SETTLED" (test A only; no look-ahead at all). Why: V2 waits 240 s for a
  score to show up, which conditions a bet on nothing being scored in the next
  few minutes and grades it at a price that would by then be gone. V3 asks the
  same question using only the past. V1, plus at the quote's stamp:
    - no score became known in the 240 s BEFORE the stamp (V1 says 60 s);
    - DraftKings did not jump in those 240 s: no step UP of 2.0 points or more
      in its total, and no step of 0.08 or more in its no-vig moneyline
      probability, between consecutive quotes of that game (a jump with no
      score in our log is the book knowing something our state does not);
    - the quote is no older than 90 s at the fetch, unless at halftime.
  Graded at the quote's own price. 2025's replay holds one snapshot every five
  minutes, so the book's last 240 s are not observable there: test A only.

FB, the "football-shaped" model. Why: the plain port's out-of-sample
  calibration (both halves of 2025 and 2026) runs high on the total in the
  third quarter and low in the second, the shape a clock-linear model has in a
  sport that scores more late in each half; and a total's distribution is
  right-skewed, so a symmetric Normal around an unbiased MEAN leans over
  against a line set at the MEDIAN. Both are fixed from TRAINING states only:
    - time is the SHARE OF SCORING left, h(clock) = mean points still to come /
      mean final total at each 30 s of the training games, used wherever the
      plain model uses the share of the clock left;
    - a total's probability is read off the training states' own standardised
      errors (four bands of h), not off the Normal; the margin stays Normal.
  Same rules, cuts, eligibility, grade and placebo as grid.py.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import grid as G

OUT = WORK / "inplay"
SETTLED_S = 240.0
JUMP_TOTAL = 2.0
JUMP_NOVIG = 0.08
BANDS = np.array([0.0, 0.25, 0.5, 0.75, 1.0001])


def grade_variant(name: str, label: str, xv: pd.DataFrame, split: str, tag: str, store: dict) -> None:
    xv = xv.reset_index(drop=True)
    d = G.pick_sides(xv)
    counts = xv.groupby("rule").agg(quotes=("game_id", "size"), games=("game_id", "nunique"))
    bl, pl, cells = G.blind(xv), G.placebo(xv), []
    for rule in G.RULES:
        dr = d[d["rule"] == rule]
        for c in G.CUTS:
            b = G.first_signal(dr, c)
            s = G.summarise(b, split)
            s.update({"rule": rule, "cut": c})
            if s["bets"]:
                s["blind_same_side"] = bl.get(f"{rule}|{s['dominant']}", {}).get("roi")
                pr = pl.get(rule, {}).get(c)
                if pr is not None:
                    s["placebo_mean"] = round(float(np.nanmean(pr)), 4)
                    s["placebo_p95"] = round(float(np.nanpercentile(pr, 95)), 4)
                    s["placebo_runs_above"] = int(np.nansum(pr >= s["roi"]))
            cells.append(s)
            b.assign(test=name, variant=label, cut=c).to_parquet(
                OUT / f"bets_{tag}_{name}_{label}_{rule}_{c:.2f}.parquet", index=False)
    store.setdefault(name, {})[label] = {
        "eligible": {r: {"quotes": int(counts.loc[r, "quotes"]), "games": int(counts.loc[r, "games"])} for r in counts.index},
        "blind": bl, "cells": cells}
    tab = pd.DataFrame(cells)
    cols = [c for c in ("rule", "cut", "bets", "w", "l", "p", "units", "risked", "roi", "ci_lo", "ci_hi",
                        "early_n", "early_roi", "late_n", "late_roi", "price_min", "price_med", "price_max",
                        "dominant", "blind_same_side", "placebo_mean", "placebo_p95", "placebo_runs_above",
                        "mean_ev") if c in tab.columns]
    print(f"\n=== {tag} / TEST {name} / {label} ===")
    print("eligible:", {r: (int(counts.loc[r, 'quotes']), int(counts.loc[r, 'games'])) for r in counts.index})
    print("blind:", {k: (v_["bets"], v_["roi"]) for k, v_ in bl.items()})
    print("sides:", {f"{c['rule']}@{c['cut']}": c.get("sides") for c in cells if c["bets"]})
    print(tab[cols].to_string(index=False))


# ── V3 flags ─────────────────────────────────────────────────────────────────

def v3_flags(px: pd.DataFrame) -> np.ndarray:
    q = pd.read_parquet(OUT / "quotes.parquet")
    q = q[q["season"] == 2026].copy()
    q["stamp_s"] = G.secs(q["stamp"])
    q = q.sort_values(["game_id", "market", "stamp_s", "odds_id"], kind="stable")
    tot = q[q["market"] == "totals"].copy()
    tot["step"] = tot.groupby("game_id")["total_line"].diff()
    jt = tot.loc[tot["step"] >= JUMP_TOTAL, ["game_id", "stamp_s"]]
    ml = q[q["market"] == "h2h"].copy()
    with np.errstate(invalid="ignore", divide="ignore"):
        ph, pa = 1.0 / G.dec(ml["home_price"]), 1.0 / G.dec(ml["away_price"])
    ml["nv"] = ph / (ph + pa)
    ml["step"] = ml.groupby("game_id")["nv"].diff().abs()
    jm = ml.loc[ml["step"] >= JUMP_NOVIG, ["game_id", "stamp_s"]]
    jumps = pd.concat([jt, jm]).rename(columns={"stamp_s": "last_jump"})
    print(f"2026 DraftKings jumps: total up >= {JUMP_TOTAL}: {len(jt):,}; moneyline no-vig >= {JUMP_NOVIG}: {len(jm):,}")
    x = px[["game_id", "stamp_s"]].reset_index().rename(columns={"index": "row"})
    x = G.asof(x, jumps, "stamp_s", "last_jump", "backward").set_index("row").reindex(px.index)
    no_jump = x["last_jump"].isna() | ((px["stamp_s"] - x["last_jump"]) > SETTLED_S)
    no_score = px["last_chg"].isna() | ((px["stamp_s"] - px["last_chg"]) > SETTLED_S)
    age_ok = (px["age"] <= G.AGE_MAX_S) | px["is_break"]
    print(f"V1-eligible {len(px):,}; a score known in the last 240 s: {int((~no_score).sum()):,}; "
          f"a DraftKings jump in the last 240 s (and no such score): {int((no_score & ~no_jump).sum()):,}; "
          f"too old: {int((no_score & no_jump & ~age_ok).sum()):,}; V3-eligible: {int((no_score & no_jump & age_ok).sum()):,}")
    return (no_score & no_jump & age_ok).to_numpy(bool)


# ── the football-shaped model ────────────────────────────────────────────────

class FB:
    def __init__(self, train: pd.DataFrame):
        by = train.groupby("secs_left").agg(rem=("final_total", "mean"), t=("t", "mean"))
        rem = (by["rem"] - by["t"]) / train.drop_duplicates("cfbd")["final_total"].mean()
        xs = by.index.to_numpy(float)                       # ascending seconds left
        ys = rem.to_numpy(float)
        slope0 = (ys[1] - ys[0]) / (xs[1] - xs[0])
        y0 = max(ys[0] - slope0 * xs[0], 0.001)             # at 0:00 (overtime's share)
        self.xs = np.concatenate([[0.0], xs, [G.REG_S]])
        self.ys = np.clip(np.concatenate([[y0], ys, [1.0]]), 0.001, 1.0)
        tr = self.shape(train)
        x = G.features(tr)
        self.models = {t: G.StateModel(t).fit(x) for t in ("margin", "total")}
        mean, sd = self.models["total"].predict(x)
        z = (x["final_total"].to_numpy(float) - mean) / sd
        band = np.digitize(x["f"].to_numpy(float), BANDS) - 1
        self.z = [np.sort(z[band == k]) for k in range(4)]

    def h(self, secs_left):
        return np.interp(np.asarray(secs_left, float), self.xs, self.ys)

    def shape(self, st: pd.DataFrame) -> pd.DataFrame:
        return st.assign(f_clock=st["f"], f=self.h(st["secs_left"]))

    def surv(self, band, x):
        """P(z > x) from the training states' standardised errors in the band."""
        out = np.empty(len(x))
        for k in range(4):
            mk = band == k
            if mk.any():
                zs = self.z[k]
                out[mk] = 1.0 - np.searchsorted(zs, x[mk], side="right") / len(zs)
        return np.clip(out, 0.001, 0.999)

    def price(self, e: pd.DataFrame) -> pd.DataFrame:
        x = G.features(self.shape(e))
        mu_m, sd_m = self.models["margin"].predict(x)
        mu_t, sd_t = self.models["total"].predict(x)
        tot = (x["market"] == "totals").to_numpy()
        line = np.where(tot, x["total_line"], 0.0).astype(float)
        band = np.clip(np.digitize(x["f"].to_numpy(float), BANDS) - 1, 0, 3)
        is_int = np.isclose(line, np.round(line))
        p_over = self.surv(band, (np.floor(line) + 0.5 - mu_t) / sd_t)
        p_push = np.where(is_int, np.clip(self.surv(band, (line - 0.5 - mu_t) / sd_t) - p_over, 0.0, 1.0), 0.0)
        pa = np.where(tot, p_over, G.prob_home(mu_m, sd_m))
        push = np.where(tot, p_push, 0.0)
        pb = 1.0 - pa - push
        x = x.assign(mu_m=mu_m, sd_m=sd_m, mu_t=mu_t, sd_t=sd_t, p_a=pa, p_push=push, p_b=pb)
        x["ev_a"] = G.ev_of(x["price_a"], pa, push)
        x["ev_b"] = G.ev_of(x["price_b"], pb, push)
        x["h"] = x["f"]
        x["f"] = x["f_clock"]                                # the placebo bands on the clock share
        return x.sort_values(["rule", "game_id", "fetch_s", "stamp_s", "odds_id"], kind="stable").reset_index(drop=True)

    def calibration(self, st: pd.DataFrame) -> pd.DataFrame:
        x = G.features(self.shape(st))
        rows = []
        for t, mdl in self.models.items():
            mean, sd = mdl.predict(x)
            y = x["final_margin" if t == "margin" else "final_total"].to_numpy(float)
            z = (y - mean) / sd
            fb = pd.cut(x["f_clock"], [0, 0.1, 0.25, 0.5, 0.75, 1.0], include_lowest=True)
            d = pd.DataFrame({"fb": fb, "err": y - mean, "z": z, "sd": sd, "over": y > mean})
            for b, gg in d.groupby("fb", observed=True):
                rows.append({"target": t, "share_left": str(b), "states": len(gg),
                             "mean_err": round(gg["err"].mean(), 3), "realised_sd": round(gg["err"].std(), 2),
                             "model_sd": round(gg["sd"].mean(), 2), "spread_ratio": round(gg["z"].std(), 3),
                             "final_above_mean": round(gg["over"].mean(), 3)})
        return pd.DataFrame(rows)


def main() -> int:
    pd.set_option("display.width", 320)
    pd.set_option("display.max_columns", 60)
    res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    store: dict = {"plain": {}, "fb": {}}

    # V3 on the plain model, test A
    pA = pd.read_parquet(OUT / "priced_A.parquet")
    pA["v3"] = v3_flags(pA)
    pA.to_parquet(OUT / "priced_A.parquet", index=False)
    grade_variant("A", "V3", pA[pA["v3"]], res["A"]["split_date"], "plain", store["plain"])

    # how often the plain model's final lands above its own mean (the skew), training states
    tr = pd.read_parquet(OUT / "train_states.parquet")
    plain = G.fit_models(tr)
    xm = G.features(tr)
    mean, _ = plain["total"].predict(xm)
    fb_ = pd.cut(xm["f"], [0, 0.25, 0.5, 0.75, 1.0], include_lowest=True)
    sk = pd.DataFrame({"fb": fb_, "above": xm["final_total"].to_numpy(float) > mean}).groupby("fb", observed=True)["above"].agg(["mean", "size"])
    print("\nplain model, 2025 training states: share of finals ABOVE the model's mean total, by clock share left:\n",
          sk.round(3).to_string())
    store["plain_skew"] = sk.round(4).reset_index().astype({"fb": str}).to_dict(orient="records")

    # FB
    fbs = {"A": FB(tr), "B1": FB(tr[tr["block"] == "early"]), "B2": FB(tr[tr["block"] == "late"])}
    print("\nFB scoring share left h at clock share left 0.875 / 0.75 / 0.625 / 0.5 / 0.375 / 0.25 / 0.125 (fit A):",
          np.round(fbs["A"].h(np.array([3150, 2700, 2250, 1800, 1350, 900, 450.0])), 4).tolist())
    store["fb_fits"] = {k: {t: m.describe() for t, m in v.models.items()} for k, v in fbs.items()}
    ginfo = pd.read_parquet(OUT / "ginfo.parquet")
    st26 = pd.read_parquet(OUT / "st_2026.parquet").merge(ginfo[["game_id", "fh", "fa", "sp_pre", "T_pre"]], on="game_id")
    st26 = st26[st26["period"].between(1, 4) & st26["fh"].notna() & st26["T_pre"].notna()].copy()
    st26["f"] = st26["secs_left"] / G.REG_S
    st26["m"], st26["t"] = st26["home_score"] - st26["away_score"], st26["home_score"] + st26["away_score"]
    st26["mu_pre"] = -st26["sp_pre"]
    st26["final_margin"], st26["final_total"] = st26["fh"] - st26["fa"], st26["fh"] + st26["fa"]
    cal = {"B1 (fit weeks 1-7, read on weeks 8+)": fbs["B1"].calibration(tr[tr["block"] == "late"]),
           "B2 (fit weeks 8+, read on weeks 1-7)": fbs["B2"].calibration(tr[tr["block"] == "early"]),
           "A (fit 2025, read on the 2026 logged states)": fbs["A"].calibration(st26)}
    store["fb_calibration"] = {k: v.to_dict(orient="records") for k, v in cal.items()}
    for k, v in cal.items():
        print(f"\nFB calibration, {k}:\n{v.to_string(index=False)}")
    for name in ("A", "B1", "B2"):
        base = pA if name == "A" else pd.read_parquet(OUT / f"priced_{name}.parquet")
        px = fbs[name].price(base)
        px.to_parquet(OUT / f"priced_fb_{name}.parquet", index=False)
        tot = px[px["market"] == "totals"]
        print(f"\nFB {name}: model mean total minus DraftKings' line, V1-eligible quotes, by clock share left: "
              f"{(tot['mu_t'] - tot['total_line']).groupby(pd.cut(tot['f'], [0, .25, .5, .75, 1.0], include_lowest=True), observed=True).mean().round(3).to_dict()}; "
              f"mean P(over) {tot['p_a'].mean():.4f}")
        split = res[name]["split_date"]
        grade_variant(name, "V1", px, split, "fb", store["fb"])
        grade_variant(name, "V2", px[px["v2"]], split, "fb", store["fb"])
        if name == "A":
            grade_variant(name, "V3", px[px["v3"]], split, "fb", store["fb"])
    (OUT / "variants.json").write_text(json.dumps(store, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

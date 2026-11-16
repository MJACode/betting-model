"""UK and Ireland at starting price: fundamentals (Bolton-Chapman), the Benter blend with
SP, and one decidable rule. Walk-forward by year, 1995-2026.

Reads the deltaromeo UK/Ireland results through `scripts/horse/uk_sp_data.load` (stored in
Supabase as source `horse_racing|deltaromeo_uk_ireland_1988_2026`; the CSVs on disk are the
cache). No database writes, no network.

STAGE 1, decidable. A conditional logit (one softmax per race) on facts known before the
off: official rating and its change (split handicap / non-handicap), weight against the race,
age, draw (Flat), days since the last run, the last three finishing positions in the same
code (Flat or jumps), lengths beaten last time, the racing-post rating (rpr) and topspeed
(ts) of EARLIER runs, course / distance / course-and-distance wins in EARLIER runs, and
jockey and trainer actual-over-expected wins over the previous 730 days, shrunk to the base
rate. A missing value is the race mean of the runners that have it, plus a flag; every
column is then centred in its race (a no-op for the conditional logit) and divided by one
global standard deviation (a unit, not an outcome). Flat and jumps are fitted separately;
one pooled fit is reported beside them. History is every GB/IRE run with a result (days
since the last run also counts foreign runs); a fit uses complete single-winner races.

  * "stage 1" for year Y is fitted on the five years Y-6..Y-2 (never before 1990: 1988-1989
    are the history warm-up) and predicts Y-1 and Y; it feeds stage 2.
  * "stage 1 fresh" is fitted on Y-5..Y-1 and drives the decidable rule.
  * COVERAGE GATE: a column that is non-zero in under 2% of a fit's own training rows gets
    coefficient 0 (the files carry non-handicap ratings only from 1998 and Irish ratings
    only from 1998; a coefficient fitted on a near-empty column wrecked those years).
  * FROM 2026-05-01 the source has no rpr or ts, so those races take every probability from
    the same walk-forward fitted without the figures group.
  Both switches are triggered by coverage and format, not by outcomes; they were added after
  a first full run showed the 1998-1999 and 2026 May-Oct collapse.

STAGE 2, Benter. softmax(b log p_model + c log p_SP), fitted on year Y-1 per region and code
group, applied to year Y. p_SP is SP de-vigged by proportion. SP is the close: stage 2 is an
INFORMATION TEST and an UPPER BOUND on what a bettor deciding before the off could have,
never a rule. "Calibrated SP" is softmax(c' log p_SP) fitted the same way.

THE DECIDABLE RULE never reads SP: back stage 1's top-rated runner when its probability is
over a cut and its margin over the second-rated runner is over a cut, graded at SP (a bet
at SP is executable at UK bookmakers). Units: 1 unit to win, risk 1/(SP-1) capped at 3
(anz_study.stake_units), no commission. Return = units / units risked, 95% interval
clustered by race. GB and Ireland are always reported separately. A naive decidable
baseline (the highest earlier-run figure, four variants, no fit) is printed beside it.

ROW ORDER CARRIES THE RESULT. Inside a race the files list runners in finishing order (the
first row wins 99.7-99.8% of 1988-2014 races and 41.7% of 2015-2026 ones). Rows are shuffled
inside each race with a fixed seed before anything is built, so a tie in any selection is
broken at random; the script prints the check.

    python -I scripts/horse/uk_sp_fundamentals.py [--json OUT] [--years 1995-2026]
           [--ablation-years 1995-2026] [--leak-years 2010-2025] [--no-ablation] [--no-leak]
           [--jobs 4] [--checks-only]

--checks-only loads, shuffles and builds the features, prints the row-order check, the frame
counts and the naive baseline, and stops (no fits).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
from scripts.horse.anz_study import devig, stake_units  # noqa: E402
from scripts.horse.clogit import fit_clogit, softmax_by_race, starts_of  # noqa: E402

RAW_COLS = ["dist", "draw", "wgt", "or", "rpr", "ts", "ovr_btn"]
SEED = 20261115
FIRST_FIT_YEAR = 1990          # 1988-1989 are the history warm-up
WINDOW = 5                     # stage-1 years: Y-6 .. Y-2
PERSON_DAYS = 730              # jockey / trainer window
PERSON_K = 5.0                 # shrinkage, in expected wins
PERSON_GAP_MIN = 30            # a race counts for a person only if it went off 30+ min earlier
MIN_STAGE2_RACES = 300
MIN_COVERAGE = 0.02            # a column non-zero in under 2% of a window's rows is not fitted
CG_NAMES = {0: "Flat", 1: "Jumps"}
REG_NAMES = {0: "GB", 1: "IRE"}

GROUPS = {
    "rating": ["or_hc", "or_nh", "or_miss_hc", "or_miss_nh", "or_chg_hc", "or_chg_nh",
               "or_chg_miss_hc", "or_chg_miss_nh"],
    "weight": ["wgt_d", "wgt_h"],
    "age": ["age_d", "age_sq"],
    "draw": ["draw_n", "draw_sq", "draw_miss"],
    "layoff": ["days_log", "days_sq", "debut", "nprev_log"],
    "form": ["pos1", "pos3", "nf1", "btn1", "form_miss"],
    "figures": ["rpr1", "rpr3", "rpr_miss", "ts1", "ts3", "ts_miss"],
    "course_dist": ["c_win", "d_win", "cd_win"],
    "connections": ["jock_ae", "trn_ae"],
}
ALL_COLS = [c for g in GROUPS.values() for c in g]
NOFIG = [c for c in ALL_COLS if c not in GROUPS["figures"]]
LEAK_COLS = ["own_rpr", "own_rpr_miss"]


# ================================================================== small helpers

def gshift(x: np.ndarray, keys, k: int = 1) -> np.ndarray:
    return pd.Series(x).groupby(keys, sort=False).shift(k).to_numpy()


def race_fill(x: np.ndarray, starts: np.ndarray, sizes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """A missing value becomes the race mean of the runners that have it; the result is
    centred in the race. Returns (centred values, missing flag as float)."""
    x = np.asarray(x, float)
    m = ~np.isfinite(x)
    s = np.add.reduceat(np.where(m, 0.0, x), starts)
    n = np.add.reduceat((~m).astype(float), starts)
    mu = np.repeat(np.where(n > 0, s / np.maximum(n, 1.0), 0.0), sizes)
    return np.where(m, mu, x) - mu, m.astype(float)


def centre(x: np.ndarray, starts: np.ndarray, sizes: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    return x - np.repeat(np.add.reduceat(x, starts) / sizes, sizes)


def power_devig(q: np.ndarray, starts: np.ndarray, sizes: np.ndarray) -> np.ndarray:
    """anz_study.devig(method='power') for every race at once (same bracket and steps).
    Checked against devig race by race in the output."""
    lq = np.log(q)
    lo = np.full(len(starts), 0.2)
    hi = np.full(len(starts), 5.0)
    for _ in range(60):
        k = 0.5 * (lo + hi)
        s = np.add.reduceat(np.exp(lq * np.repeat(k, sizes)), starts)
        lo = np.where(s > 1.0, k, lo)
        hi = np.where(s > 1.0, hi, k)
    p = np.exp(lq * np.repeat(0.5 * (lo + hi), sizes))
    return p / np.repeat(np.add.reduceat(p, starts), sizes)


def sub_starts(rk: np.ndarray) -> np.ndarray:
    return np.flatnonzero(np.r_[True, rk[1:] != rk[:-1]]) if len(rk) else np.zeros(0, int)


def grade(sp, share, race, w=None) -> dict:
    """Units at SP: 1 unit to win, risk 1/(SP-1) capped at 3, no commission. w scales a
    bet's stake (a split joint favourite). 95% interval clustered by race."""
    sp = np.asarray(sp, float)
    share = np.asarray(share, float)
    if len(sp) == 0:
        return {"bets": 0}
    w = np.ones(len(sp)) if w is None else np.asarray(w, float)
    profit, risk = stake_units(sp, share, 0.0)
    profit, risk = profit * w, risk * w
    by = pd.DataFrame({"m": np.asarray(race), "p": profit, "r": risk}).groupby("m").sum()
    roi = by.p.sum() / by.r.sum()
    se = math.sqrt(((by.p - roi * by.r) ** 2).sum()) / by.r.sum()
    fp = w * (share * (sp - 1.0) - (1.0 - share))
    flat = fp.sum() / w.sum()
    fb = pd.DataFrame({"m": np.asarray(race), "p": fp, "r": w}).groupby("m").sum()
    fse = math.sqrt(((fb.p - flat * fb.r) ** 2).sum()) / fb.r.sum()
    return {"bets": int(round(w.sum())) if np.allclose(w, 1) else round(float(w.sum()), 1),
            "races": int(len(by)), "wins": float((w * share).sum()), "units": float(profit.sum()),
            "risk": float(risk.sum()), "roi": float(roi), "lo": float(roi - 1.96 * se),
            "hi": float(roi + 1.96 * se), "flat": float(flat),
            "flat_lo": float(flat - 1.96 * fse), "flat_hi": float(flat + 1.96 * fse),
            "avg_sp": float(np.exp(np.log(sp).mean()))}


def _spans(ys: list[int]) -> str:
    ys = sorted(set(ys))
    out, a = [], None
    for i, y in enumerate(ys):
        if a is None:
            a = y
        if i == len(ys) - 1 or ys[i + 1] != y + 1:
            out.append(f"{a}" if a == y else f"{a}-{y}")
            a = None
    return ", ".join(out)


def md(rows: list[dict], cols: list[str] | None = None) -> str:
    if not rows:
        return "(none)"
    cols = cols or list(rows[0].keys())
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out)


def gcells(r: dict) -> dict:
    """A graded set as table cells."""
    if not r.get("bets"):
        return {"bets": 0, "units": "", "risked": "", "return": "", "95% CI": "", "flat": "",
                "flat 95% CI": ""}
    return {"bets": f"{r['bets']:,}", "wins": f"{r['wins']:,.0f}", "units": f"{r['units']:+.1f}",
            "risked": f"{r['risk']:.1f}", "return": f"{100 * r['roi']:+.2f}%",
            "95% CI": f"[{100 * r['lo']:+.2f}, {100 * r['hi']:+.2f}]",
            "flat": f"{100 * r['flat']:+.2f}%",
            "flat 95% CI": f"[{100 * r['flat_lo']:+.2f}, {100 * r['flat_hi']:+.2f}]",
            "avg SP": f"{r['avg_sp']:.2f}"}


# ================================================================== data

def prepare(df: pd.DataFrame, out: dict) -> pd.DataFrame:
    """Shuffle runners inside each race (row order carries the result), keep runs with a
    result, and build every feature from earlier runs only."""
    P = print
    from scripts.horse.uk_sp_data import parse_num
    t0 = time.time()
    rk = df["race_key"].to_numpy()
    if not (np.diff(rk) >= 0).all():
        raise SystemExit("loader rows are not in race_key order")
    def order_check(d: pd.DataFrame) -> list[dict]:
        """Per file: Pearson of (row index / (rows-1)) with ((pos-1) / (ran-1)) over GB/IRE
        finishers (both scaled by field size, so 0 means unordered), and how often the first
        row of a GB/IRE race with a result is the winner, against 1/runners."""
        ri = d.groupby("race_key").cumcount().to_numpy()
        x = ri / np.maximum(d["rows"].to_numpy() - 1.0, 1.0)
        y = (d["pos"].to_numpy() - 1.0) / np.maximum(d["ran"].to_numpy() - 1.0, 1.0)
        gb = (d["region"] != "OTHER").to_numpy()
        fin = d["finished"].to_numpy() & gb
        first = (ri == 0) & gb & (d["n_first"].to_numpy() > 0)
        rows = []
        for f in ("1988-2004", "2005-2014", "2015-2026"):
            fm = (d["file"] == f).to_numpy()
            m, r1 = fin & fm, first & fm
            rows.append({"file": f, "corr(row index, position), field-scaled": f"{np.corrcoef(x[m], y[m])[0, 1]:+.4f}",
                         "first row won": f"{100 * np.nanmean(d['won'].to_numpy()[r1]):.1f}%",
                         "1/runners": f"{100 * np.mean(1.0 / d['ran'].to_numpy()[r1]):.1f}%"})
        return rows

    pre = order_check(df)
    rng = np.random.default_rng(SEED)
    order = np.lexsort((rng.random(len(df)), rk))
    df = df.iloc[order].reset_index(drop=True)
    post = order_check(df)
    out["row_order"] = {"before_shuffle": pre, "after_shuffle": post}
    P("\n## 0. Row order inside a race (selection ties must not read it)")
    P("Before the shuffle:")
    P(md(pre))
    P(f"\nAfter a shuffle inside each race (seed {SEED}):")
    P(md(post))

    day_all = ((df["date"] - pd.Timestamp("1988-01-01")).dt.days).to_numpy()
    res = df["n_first"].to_numpy() > 0
    hc_all = df["horse_id"].cat.codes.to_numpy().astype(np.int64)
    # days since the last run: any region, any run with a result
    R = np.flatnonzero(res)
    prev_day = np.full(len(df), np.nan)
    prev_day[R] = gshift(day_all[R].astype(float), hc_all[R], 1)
    keep = res & (df["region"] != "OTHER").to_numpy()
    H = df.loc[keep, ["race_key", "date", "year", "new_format", "off_min", "region", "code", "jumps",
                      "handicap", "ran", "rows", "complete", "pos", "finished", "won", "n_first",
                      "sp", "book", "gradeable", "gradeable_raw", "course_base", "dist_f", "wgt_lbs",
                      "or_num", "draw_num", "rpr_num", "ts_num", "age", "horse_id", "jockey_id",
                      "trainer_id", "file"]].reset_index(drop=True)
    H["ovr_btn_num"] = parse_num(df.loc[keep, "ovr_btn"])
    H["day"] = day_all[keep]
    H["prev_day"] = prev_day[keep]
    del df
    n = len(H)
    out["frame"] = {"gb_ire_runs_with_result": n, "races": int(H.race_key.nunique())}
    rkH = H["race_key"].to_numpy()
    starts = sub_starts(rkH)
    sizes = np.diff(np.append(starts, n))
    hc = H["horse_id"].cat.codes.to_numpy().astype(np.int64)
    jumps = H["jumps"].to_numpy().astype(np.int64)
    codec = H["code"].cat.codes.to_numpy().astype(np.int64)
    fin = H["finished"].to_numpy()
    pos = H["pos"].to_numpy(float)
    ran = H["ran"].to_numpy(float)
    won = H["won"].to_numpy(float)
    F = {}

    # ---- layoff
    days = H["day"].to_numpy() - H["prev_day"].to_numpy()
    dl = np.log1p(days)
    F["days_log"], F["debut"] = race_fill(dl, starts, sizes)
    F["days_sq"], _ = race_fill(dl ** 2, starts, sizes)
    F["nprev_log"] = centre(np.log1p(pd.Series(hc).groupby(hc).cumcount().to_numpy()), starts, sizes)
    F["debut"] = centre(F["debut"], starts, sizes)

    # ---- form inside the code group (Flat or jumps)
    kg = hc * 2 + jumps
    pos_n = np.where(fin, np.clip((pos - 1.0) / np.maximum(ran - 1.0, 1.0), 0.0, 1.0), 1.0)
    nf = (~fin).astype(float)
    ob = H["ovr_btn_num"].to_numpy(float)
    sec = pd.Series(np.where(pos == 2, ob, np.nan)).groupby(rkH).transform("min").to_numpy()
    btn = np.where(fin, ob, np.nan)
    btn = np.where(pos == 1, np.where(np.isfinite(sec), -sec, 0.0), btn)
    btn = np.clip(btn, -10.0, 30.0)
    p1, p2, p3 = (gshift(pos_n, kg, k) for k in (1, 2, 3))
    with np.errstate(invalid="ignore"):
        cnt = np.isfinite(p1) * 1.0 + np.isfinite(p2) + np.isfinite(p3)
        avg3 = np.where(cnt > 0, (np.nan_to_num(p1) + np.nan_to_num(p2) + np.nan_to_num(p3)) / np.maximum(cnt, 1), np.nan)
    F["pos1"], fm = race_fill(p1, starts, sizes)
    F["pos3"], _ = race_fill(avg3, starts, sizes)
    F["nf1"], _ = race_fill(gshift(nf, kg, 1), starts, sizes)
    F["btn1"], _ = race_fill(gshift(btn, kg, 1), starts, sizes)
    F["form_miss"] = centre(fm, starts, sizes)

    # ---- earlier runs' rpr and ts, same code group, last three runs
    for nm, col in (("rpr", "rpr_num"), ("ts", "ts_num")):
        v = H[col].to_numpy(float)
        a1, a2, a3 = (gshift(v, kg, k) for k in (1, 2, 3))
        last = np.where(np.isfinite(a1), a1, np.where(np.isfinite(a2), a2, a3))
        best = np.fmax(np.fmax(a1, a2), a3)
        F[f"{nm}1"], _ = race_fill(last, starts, sizes)
        F[f"{nm}3"], mm = race_fill(best, starts, sizes)
        F[f"{nm}_miss"] = centre(mm, starts, sizes)

    # ---- official rating and its change (inside the same code: Flat, hurdle, chase marks differ)
    orv = H["or_num"].to_numpy(float)
    ko = hc * 4 + codec
    prev_or = pd.Series(gshift(orv, ko, 1)).groupby(ko).ffill().to_numpy()
    hcap = H["handicap"].to_numpy().astype(float)
    # Split by handicap or not: before 1998 the files carry an official rating only in
    # handicaps (0.0-1.2% of non-handicap GB/IRE runners, 17-39% from 1998), and Ireland none
    # before 1998. A shared coefficient would carry a handicap-only fit into non-handicaps
    # the year they gain ratings; split, a column that is all zero in a window gets ~0.
    od, om = race_fill(orv, starts, sizes)
    om = centre(om, starts, sizes)
    oc, ocm = race_fill(orv - prev_or, starts, sizes)
    ocm = centre(ocm, starts, sizes)
    for nm, v in (("or", od), ("or_miss", om), ("or_chg", oc), ("or_chg_miss", ocm)):
        F[f"{nm}_hc"] = v * hcap
        F[f"{nm}_nh"] = v * (1.0 - hcap)

    # ---- weight, age, draw
    F["wgt_d"], _ = race_fill(H["wgt_lbs"].to_numpy(float), starts, sizes)
    F["wgt_h"] = F["wgt_d"] * hcap
    age = H["age"].to_numpy(float)
    age = np.where((age >= 2) & (age <= 20), age, np.nan)
    F["age_d"], _ = race_fill(age, starts, sizes)
    F["age_sq"], _ = race_fill(age ** 2, starts, sizes)
    dr = H["draw_num"].to_numpy(float)
    dn = np.clip((dr - 1.0) / np.maximum(ran - 1.0, 1.0), 0.0, 1.0)
    flat = jumps == 0
    dn = np.where(flat, dn, 0.0)                       # jumps: no draw, and not "missing"
    F["draw_n"], dm = race_fill(dn, starts, sizes)
    F["draw_sq"], _ = race_fill(np.where(flat, dn ** 2, 0.0), starts, sizes)
    F["draw_miss"] = centre(dm, starts, sizes)

    # ---- course / distance wins in earlier runs
    w1 = (won > 0).astype(float)
    crs = H["course_base"].cat.codes.to_numpy().astype(np.int64)
    dist_r = np.floor(H["dist_f"].to_numpy(float) + 0.5)
    dist_r = np.where(np.isfinite(dist_r), dist_r, -1).astype(np.int64)
    def prior_wins(*keys):
        s = pd.Series(w1).groupby(list(keys), sort=False).cumsum().to_numpy()
        return ((s - w1) > 0).astype(float)
    F["c_win"] = centre(prior_wins(hc, crs, jumps), starts, sizes)
    F["d_win"] = centre(prior_wins(hc, jumps, dist_r), starts, sizes)
    F["cd_win"] = centre(prior_wins(hc, crs, jumps, dist_r), starts, sizes)

    # ---- jockey and trainer: wins over expected (sum 1/runners), previous 730 days
    t_min = H["day"].to_numpy().astype(np.int64) * 1440 + np.nan_to_num(H["off_min"].to_numpy(float)).astype(np.int64)
    for nm, col in (("jock_ae", "jockey_id"), ("trn_ae", "trainer_id")):
        F[nm] = centre(person_ae(H[col].cat.codes.to_numpy().astype(np.int64), rkH, t_min, won, ran),
                       starts, sizes)

    # ---- the leak (this race's own rpr), for the harness check only
    F["own_rpr"], lm = race_fill(H["rpr_num"].to_numpy(float), starts, sizes)
    F["own_rpr_miss"] = centre(lm, starts, sizes)

    # global unit scale (no outcome information), one float32 matrix
    fit_rows = H["complete"].to_numpy() & (H["n_first"].to_numpy() == 1)
    names = ALL_COLS + LEAK_COLS
    M = np.empty((n, len(names)), np.float32)
    scale = {}
    for j, c in enumerate(names):
        sd = float(np.std(F[c][fit_rows]))
        scale[c] = sd if sd > 0 else 1.0
        M[:, j] = F[c] / scale[c]
        if not np.isfinite(M[:, j]).all():
            raise SystemExit(f"feature {c} has a non-finite value after filling")
    out["feature_scale"] = scale
    del F
    out["timing_features_s"] = round(time.time() - t0, 1)
    return H, M, {c: j for j, c in enumerate(names)}


def person_ae(pid, rk, t_min, won, ran) -> np.ndarray:
    """log((W + k) / (E + k)): W wins and E expected wins (sum of 1/runners) in the
    person's races that went off at least PERSON_GAP_MIN minutes earlier and within
    PERSON_DAYS days. A trainer's several runners in one race are one race."""
    d = pd.DataFrame({"p": pid, "r": rk, "t": t_min, "w": won, "e": 1.0 / ran})
    g = d.groupby(["p", "r"], sort=True)
    a = g.agg(t=("t", "first"), w=("w", "sum"), e=("e", "sum"))
    grp = g.ngroup().to_numpy()
    p = a.index.get_level_values(0).to_numpy().astype(np.int64)
    t = a["t"].to_numpy().astype(np.int64)
    BIG = 10 ** 8                                       # minutes since 1988 < 2.1e7
    key = p * BIG + t
    lo = np.searchsorted(key, key - PERSON_DAYS * 1440, side="left")
    hi = np.searchsorted(key, key - PERSON_GAP_MIN, side="right")
    hi = np.maximum(hi, lo)
    Cw = np.r_[0.0, np.cumsum(a["w"].to_numpy())]
    Ce = np.r_[0.0, np.cumsum(a["e"].to_numpy())]
    W = Cw[hi] - Cw[lo]
    E = Ce[hi] - Ce[lo]
    ae = np.log((W + PERSON_K) / (E + PERSON_K))
    return ae[grp]


# ================================================================== walk-forward

class Frame:
    """Numpy views of the prepared frame used by every walk-forward."""

    def __init__(self, H: pd.DataFrame, M: np.ndarray, colix: dict):
        self.H = H
        self.M = M
        self.colix = colix
        self.n = len(H)
        self.rk = H["race_key"].to_numpy()
        self.year = H["year"].to_numpy().astype(int)
        self.cg = H["jumps"].to_numpy().astype(int)
        self.reg = np.where(H["region"].to_numpy() == "GB", 0, 1)
        self.won = H["won"].to_numpy(float)
        self.nfirst = H["n_first"].to_numpy()
        self.fit = H["complete"].to_numpy() & (self.nfirst == 1) & (H["rows"].to_numpy() > 1)
        self.ev = H["gradeable"].to_numpy()
        self.ev1 = self.ev & (self.nfirst == 1)
        sp = H["sp"].to_numpy(float)
        self.sp = sp
        st = sub_starts(self.rk)
        sz = np.diff(np.append(st, self.n))
        q = np.where(self.ev, 1.0 / sp, 1.0)
        self.p_sp = np.where(self.ev, q / np.repeat(np.add.reduceat(q, st), sz), np.nan)
        self.p_pow = np.where(self.ev, power_devig(q, st, sz), np.nan)
        self.ran = H["ran"].to_numpy(float)
        self.fit_log: list = []

    def X(self, cols: list[str], idx: np.ndarray) -> np.ndarray:
        j = [self.colix[c] for c in cols]
        return self.M[idx][:, j].astype(np.float64)


def _fit_job(d: str, j: list, lo: int, hi: int, g):
    """One stage-1 fit in a worker process. Reads the memory-mapped arrays in directory d:
    complete single-winner races of years lo..hi, code group g (None = pooled)."""
    W = {k: np.load(f"{d}/{k}.npy", mmap_mode="r") for k in ("M", "year", "cg", "fit", "won", "rk")}
    m = np.asarray(W["fit"]) & (np.asarray(W["year"]) >= lo) & (np.asarray(W["year"]) <= hi)
    if g is not None:
        m &= np.asarray(W["cg"]) == g
    idx = np.flatnonzero(m)
    won = np.asarray(W["won"][idx])
    st = sub_starts(np.asarray(W["rk"][idx]))
    if not ((won == 1).sum() == len(st) and np.isin(won, (0.0, 1.0)).all()):
        raise ValueError("a stage-1 fit set must hold exactly one winner per race")
    X = np.asarray(W["M"][idx][:, j], dtype=np.float64)
    del W
    # Coverage gate, from the training rows only: a column that is (almost) always the race
    # mean in this window has no stable coefficient, and applying one when the column fills
    # in later (non-handicap ratings from 1998, Irish ratings from 1998) wrecks the forecast.
    keep = (X != 0).mean(axis=0) >= MIN_COVERAGE
    b = np.zeros(X.shape[1])
    b[keep] = fit_clogit(X[:, keep], won, st)
    return b, int(len(st)), np.flatnonzero(~keep).tolist()


def stage1_specs(cols: list[str], years: list[int], lag: int, tag: str, pooled: bool = False) -> list:
    """Stage 1 for year Y is fitted on the WINDOW years ending Y-lag (never before
    FIRST_FIT_YEAR), one fit per code group (or one pooled fit)."""
    return [{"tag": tag, "Y": Y, "g": g, "cols": cols,
             "lo": max(FIRST_FIT_YEAR, Y - lag - WINDOW + 1), "hi": Y - lag}
            for Y in years for g in ([None] if pooled else [0, 1])]


def run_fits(Fr: "Frame", specs: list, n_jobs: int, d: str) -> dict:
    """All stage-1 fits, in parallel worker processes. Returns {(tag, Y, g): coefficients}."""
    from joblib import Parallel, delayed
    t0 = time.time()
    calls = [(d, [Fr.colix[c] for c in s["cols"]], s["lo"], s["hi"], s["g"]) for s in specs]
    if n_jobs == 1:
        res = [_fit_job(*c) for c in calls]
    else:
        res = Parallel(n_jobs=n_jobs, backend="loky")(delayed(_fit_job)(*c) for c in calls)
    for s, (_, nr, gated) in zip(specs, res):
        s["races"] = nr
        s["gated"] = [s["cols"][k] for k in gated]
    Fr.fit_log.append({"fits": len(specs), "seconds": round(time.time() - t0, 1)})
    return {(s["tag"], s["Y"], s["g"]): b for s, (b, _, _) in zip(specs, res)}


def predict(Fr: Frame, cols, b, mask) -> tuple[np.ndarray, np.ndarray]:
    idx = np.flatnonzero(mask)
    return idx, softmax_by_race(Fr.X(cols, idx) @ b, sub_starts(Fr.rk[idx]))


def walk(Fr: Frame, cols: list[str], years: list[int], b1: dict, tag=None, pooled: bool = False,
         stage2: bool = True, lag: int = 2) -> dict:
    """Apply fitted stage-1 coefficients b1[(tag, Y, g)] to Y-1 and Y; then, if stage2, fit
    stage 2 (Benter) and calibrated SP on Y-1 per region x code group and apply them to Y."""
    n = Fr.n
    pm = np.full(n, np.nan)
    pcal = np.full(n, np.nan)
    pstar = np.full(n, np.nan)
    coefs, b1s = [], {}
    for Y in years:
        both = ((Fr.year == Y - 1) | (Fr.year == Y)) if stage2 else (Fr.year == Y)
        tmp = np.full(n, np.nan)
        for g in ([None] if pooled else [0, 1]):
            gm = np.ones(n, bool) if g is None else (Fr.cg == g)
            b = b1[(tag, Y, g)]
            idx, p = predict(Fr, cols, b, both & gm & Fr.ev)
            tmp[idx] = p
            b1s[(Y, g)] = b
        cur = (Fr.year == Y) & Fr.ev
        pm[cur] = tmp[cur]
        if not stage2:
            continue
        for r in (0, 1):
            for g in (0, 1):
                cell = (Fr.reg == r) & (Fr.cg == g)
                fm = cell & Fr.ev1 & (Fr.year == Y - 1)
                am = cell & cur
                idx = np.flatnonzero(fm)
                st = sub_starts(Fr.rk[idx])
                if len(st) < MIN_STAGE2_RACES or not am.any():
                    coefs.append({"Y": Y, "reg": r, "cg": g, "races": int(len(st)), "b": np.nan, "c": np.nan,
                                  "c_sp_only": np.nan})
                    continue
                Z = np.c_[np.log(tmp[idx]), np.log(Fr.p_sp[idx])]
                b2 = fit_clogit(Z, Fr.won[idx], st, l2=1e-3)
                bp = fit_clogit(np.log(Fr.p_sp[idx])[:, None], Fr.won[idx], st, l2=1e-3)
                ia = np.flatnonzero(am)
                sa = sub_starts(Fr.rk[ia])
                pstar[ia] = softmax_by_race(np.c_[np.log(tmp[ia]), np.log(Fr.p_sp[ia])] @ b2, sa)
                pcal[ia] = softmax_by_race(np.log(Fr.p_sp[ia]) * bp[0], sa)
                coefs.append({"Y": Y, "reg": r, "cg": g, "races": int(len(st)), "b": float(b2[0]),
                              "c": float(b2[1]), "c_sp_only": float(bp[0])})
    return {"pm": pm, "pcal": pcal, "pstar": pstar, "coefs": coefs, "b1": b1s}


# ================================================================== evaluation

def race_ll(Fr: Frame, p: np.ndarray, mask: np.ndarray) -> pd.Series:
    """log p(winner) per race, single-winner gradeable races in `mask`."""
    m = mask & Fr.ev1 & (Fr.won == 1)
    return pd.Series(np.log(np.clip(p[m], 1e-12, 1.0)), index=Fr.rk[m])


def ll_table(Fr: Frame, cols: dict, mask: np.ndarray, by) -> list[dict]:
    """Mean log-likelihood per race for each probability column, by group."""
    m = mask & Fr.ev1 & (Fr.won == 1)
    for c, p in cols.items():
        m &= np.isfinite(p)
    keys = by(m)
    d = pd.DataFrame({"k": keys})
    for c, p in cols.items():
        d[c] = np.log(np.clip(p[m], 1e-12, 1.0))
    d["unif"] = -np.log(Fr.ran[m])
    rows = []
    for k, g in d.groupby("k", sort=True):
        r = {"group": k, "races": f"{len(g):,}", "uniform": f"{g.unif.mean():.4f}"}
        for c in cols:
            r[c] = f"{g[c].mean():.4f}"
        rows.append(r)
    return rows, d


def paired(d: pd.DataFrame, a: str, b: str) -> str:
    x = (d[a] - d[b]).to_numpy()
    if len(x) < 2:
        return ""
    se = x.std(ddof=1) / math.sqrt(len(x))
    return f"{1000 * x.mean():+.2f} [{1000 * (x.mean() - 1.96 * se):+.2f}, {1000 * (x.mean() + 1.96 * se):+.2f}]"


def tops(Fr: Frame, p: np.ndarray, mask: np.ndarray) -> pd.DataFrame:
    """Per race: the top-rated runner by p (ties broken by the shuffled order, i.e. at
    random), its p, the second-highest p, and the race facts."""
    idx = np.flatnonzero(mask & np.isfinite(p))
    o = idx[np.lexsort((-p[idx], Fr.rk[idx]))]
    rk = Fr.rk[o]
    st = sub_starts(rk)
    sz = np.diff(np.append(st, len(o)))
    top = o[st]
    sec = np.where(sz > 1, p[o[np.minimum(st + 1, len(o) - 1)]], 0.0)
    H = Fr.H
    t = pd.DataFrame({"row": top, "race": Fr.rk[top], "year": Fr.year[top], "reg": Fr.reg[top],
                      "cg": Fr.cg[top], "p1": p[top], "p2": sec, "sp": Fr.sp[top],
                      "won": Fr.won[top], "ran": Fr.ran[top]})
    t["margin"] = t.p1 - t.p2
    t["code"] = H["code"].to_numpy()[top].astype(str)
    t["handicap"] = H["handicap"].to_numpy()[top]
    t["newf"] = H["new_format"].to_numpy()[top]
    t["period"] = np.where(t.newf, "2026 May-Oct", t.year.astype(str))
    t.loc[(t.year == 2026) & ~t.newf, "period"] = "2026 Jan-Apr"
    # SP favourite marker read only for descriptive tables
    minsp = pd.Series(Fr.sp[o]).groupby(rk).transform("min").to_numpy()
    nfav = pd.Series((Fr.sp[o] == minsp).astype(int)).groupby(rk).transform("sum").to_numpy()
    t["is_sp_fav"] = (Fr.sp[top] == minsp[st])
    t["n_sp_fav"] = nfav[st]
    return t


NAIVE_VARIANTS = (("best rpr, last three runs", "rpr3", "rpr_miss"),
                  ("latest rpr, last three runs", "rpr1", "rpr_miss"),
                  ("best topspeed, last three runs", "ts3", "ts_miss"),
                  ("latest topspeed, last three runs", "ts1", "ts_miss"))


def naive_baseline(Fr: "Frame", years: list[int], out: dict) -> None:
    """Decidable and fit-free: back the runner with the highest earlier-run figure in the
    same code group, at SP. All four variants are printed (best or last, rpr or topspeed),
    so no one of them is reported alone. "Latest" is the most recent of the last three runs
    that has a figure (rpr1 / ts1 fall back to the run before when the last run has none).
    A race is bet only when at least two of its runners have earlier figures and they
    differ (a lone figure is centred to the race mean, so its spread is 0); ties are broken
    by the shuffled order (at random)."""
    P = print
    st = sub_starts(Fr.rk)
    sz = np.diff(np.append(st, Fr.n))
    mid = (years[0] + years[-1]) // 2
    rows = []
    for label, col, miss_col in NAIVE_VARIANTS:
        x = Fr.M[:, Fr.colix[col]].astype(float)
        miss = Fr.M[:, Fr.colix[miss_col]] > 1e-6      # centred flag > 0: this runner has none
        spread = np.repeat(np.maximum.reduceat(x, st) - np.minimum.reduceat(x, st), sz)
        m = np.isin(Fr.year, years) & Fr.ev & ~miss & (spread > 0)
        t = tops(Fr, np.where(m, x, np.nan), m)
        for reg_i, reg in REG_NAMES.items():
            for lab, g in ((f"{years[0]}-{years[-1]}", t[t.reg == reg_i]),
                           (f"early {years[0]}-{mid}", t[(t.reg == reg_i) & (t.year <= mid)]),
                           (f"late {mid + 1}-{years[-1]}", t[(t.reg == reg_i) & (t.year > mid)])):
                rows.append({"pick": label, "region": reg, "period": lab,
                             **gcells(grade(g.sp, g.won, g.race))})
    out["naive_figures"] = rows
    P("\n## Naive decidable baselines: back the highest earlier-run figure (same code) at SP")
    P("No fit and no SP in the choice. Four variants, all printed. A race needs two runners with "
      "different earlier figures. Whether the stored figures are the ones published on the day "
      "cannot be shown from these files.")
    P(md(rows))


def main(argv: list[str] | None = None, df: pd.DataFrame | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    ap.add_argument("--years", default="1995-2026")
    ap.add_argument("--ablation-years", default="1995-2026")
    ap.add_argument("--leak-years", default="2010-2025")
    ap.add_argument("--no-ablation", action="store_true")
    ap.add_argument("--no-leak", action="store_true")
    ap.add_argument("--jobs", type=int, default=4, help="worker processes for the stage-1 fits")
    ap.add_argument("--checks-only", action="store_true",
                    help="load, shuffle and build the features (section 0 and the frame counts), then stop")
    a = ap.parse_args(argv)
    yr = lambda s: list(range(int(s.split("-")[0]), int(s.split("-")[1]) + 1))
    years = yr(a.years)
    P = print
    T0 = time.time()
    out: dict = {"command": "python -I scripts/horse/uk_sp_fundamentals.py " + " ".join(argv or sys.argv[1:])}
    P("# UK/IRE at SP: fundamentals, the Benter blend, a decidable rule")
    P(f"`{out['command'].strip()}`")
    if df is None:
        from scripts.horse.uk_sp_data import load
        df = load(cols=RAW_COLS)
    out["loaded"] = {"rows": int(len(df)), "races": int(df["race_key"].nunique()),
                     "load_s": round(time.time() - T0, 1)}
    P(f"\nLoaded {len(df):,} runner rows in {out['loaded']['races']:,} races "
      f"(all three files, 1988-2026) in {out['loaded']['load_s']} s.")
    H, M, colix = prepare(df, out)
    del df
    Fr = Frame(H, M, colix)
    P(f"\nGB/IRE runs with a result (history and stage-1 universe): {Fr.n:,} rows, "
      f"{out['frame']['races']:,} races. Stage-1 fit rows (complete field, one winner): "
      f"{int(Fr.fit.sum()):,}. Gradeable rows: {int(Fr.ev.sum()):,}. Features built in "
      f"{out['timing_features_s']} s.")
    if a.checks_only:
        naive_baseline(Fr, years, out)
        if a.json:
            a.json.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
        return 0

    # devig check against anz_study.devig on a sample of races
    rng = np.random.default_rng(1)
    st_all = sub_starts(Fr.rk)
    sz_all = np.diff(np.append(st_all, Fr.n))
    evr = np.flatnonzero(Fr.ev[st_all])
    samp = rng.choice(evr, size=min(2000, len(evr)), replace=False)
    worst = 0.0
    for s in samp:
        i0, i1 = st_all[s], st_all[s] + sz_all[s]
        worst = max(worst, float(np.abs(devig(1.0 / Fr.sp[i0:i1], "power") - Fr.p_pow[i0:i1]).max()))
    out["power_devig_check_max_abs_diff"] = worst
    P(f"Vectorised power de-vig against anz_study.devig on {len(samp):,} random gradeable races: "
      f"largest difference {worst:.2e}.")

    # ---------------------------------------------------------------- every stage-1 fit
    ly = [y for y in yr(a.leak_years) if y in years] if not a.no_leak else []
    ay = [y for y in yr(a.ablation_years) if y in years] if not a.no_ablation else []
    newf = Fr.H["new_format"].to_numpy()
    nf_years = sorted(int(y) for y in set(Fr.year[newf]) if int(y) in years)
    specs = (stage1_specs(ALL_COLS, years, 2, "base") + stage1_specs(ALL_COLS, years, 1, "fresh")
             + stage1_specs(NOFIG, nf_years, 2, "nofig") + stage1_specs(NOFIG, nf_years, 1, "fresh_nofig")
             + stage1_specs(ALL_COLS, years, 2, "pooled", pooled=True)
             + stage1_specs(ALL_COLS + LEAK_COLS, ly, 2, "leak"))
    for gname, gcols in GROUPS.items():
        specs += stage1_specs([c for c in ALL_COLS if c not in gcols], ay, 2, f"abl:{gname}")
    tmpdir = tempfile.mkdtemp(prefix="uk_sp_fund_")
    try:
        for k, v in (("M", Fr.M), ("year", Fr.year), ("cg", Fr.cg), ("fit", Fr.fit), ("won", Fr.won), ("rk", Fr.rk)):
            np.save(f"{tmpdir}/{k}.npy", v)
        B1 = run_fits(Fr, specs, a.jobs, tmpdir)
    finally:
        try:
            from joblib.externals.loky import get_reusable_executor
            get_reusable_executor().shutdown(wait=True)
        except Exception:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)
    out["stage1_fits"] = {"fits": len(specs), "seconds": Fr.fit_log[-1]["seconds"], "workers": a.jobs,
                          "temp_dir_removed": not Path(tmpdir).exists()}
    P(f"\nStage-1 fits: {len(specs)} in {Fr.fit_log[-1]['seconds']} s on {a.jobs} worker processes "
      f"(base and pooled: years Y-6..Y-2; fresh: Y-5..Y-1; never before {FIRST_FIT_YEAR}). "
      f"Memory-mapped temp copy removed: {out['stage1_fits']['temp_dir_removed']}.")
    tr_rows = [{"graded year": s["Y"], "code group": CG_NAMES[s["g"]], "years fitted": f"{s['lo']}-{s['hi']}",
                "races": f"{s['races']:,}"} for s in specs if s["tag"] in ("base",) and s["Y"] in (years[0], years[-1])]
    P(md(tr_rows))
    gat: dict = {}
    for sp_ in specs:
        if sp_["tag"] in ("base", "fresh"):
            for c in sp_["gated"]:
                gat.setdefault((sp_["tag"], c, CG_NAMES[sp_["g"]]), []).append(sp_["Y"])
    out["coverage_gate"] = {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in gat.items()}
    P(f"\nCoverage gate (a column non-zero in under {100 * MIN_COVERAGE:.0f}% of the window's rows gets "
      "coefficient 0), base and fresh fits:")
    P(md([{"fit": k[0], "column": k[1], "code group": k[2], "graded years gated": _spans(v)}
          for k, v in sorted(gat.items())]))
    base = walk(Fr, ALL_COLS, years, B1, tag="base")
    fresh = walk(Fr, ALL_COLS, years, B1, tag="fresh", stage2=False)
    pooled = walk(Fr, ALL_COLS, years, B1, tag="pooled", pooled=True, stage2=False)
    # From 2026-05-01 the source has no rpr or ts, so every earlier-run figure goes stale and
    # "missing" stops meaning what it meant in training. Those races take every probability
    # from the same walk-forward fitted without the figures group (stage 1 and stage 2 both).
    sub = newf & np.isin(Fr.year, nf_years)
    nofig = walk(Fr, NOFIG, nf_years, B1, tag="nofig") if nf_years else None
    if nf_years:
        nfr = walk(Fr, NOFIG, nf_years, B1, tag="fresh_nofig", stage2=False)
        for k in ("pm", "pcal", "pstar"):
            base[k][sub] = nofig[k][sub]
        fresh["pm"][sub] = nfr["pm"][sub]
        pooled["pm"][sub] = np.nan                      # the pooled check stops at 2026-04-30
    P(f"Races from 2026-05-01 ({len(np.unique(Fr.rk[sub & Fr.ev])):,} gradeable) use the walk-forward "
      "without the figures group; the pooled-fit check and the ablation stop at 2026-04-30.")
    graded = np.isin(Fr.year, years) & Fr.ev
    have_all = graded & np.isfinite(base["pm"]) & np.isfinite(base["pstar"]) & np.isfinite(base["pcal"])
    out["universe"] = {"graded_years": f"{years[0]}-{years[-1]}",
                       "gradeable_races": int(len(np.unique(Fr.rk[graded]))),
                       "races_with_stage2": int(len(np.unique(Fr.rk[have_all])))}
    no2 = [c for c in base["coefs"] if not np.isfinite(c["b"])
           and ((Fr.year == c["Y"]) & (Fr.reg == c["reg"]) & (Fr.cg == c["cg"]) & Fr.ev).any()]
    P(f"Graded years {years[0]}-{years[-1]}: {out['universe']['gradeable_races']:,} gradeable races; "
      f"{out['universe']['races_with_stage2']:,} have a stage-2 fit. Ireland has no races in "
      "2000-2002. Cells with races in Y but no stage-2 fit "
      f"(under {MIN_STAGE2_RACES} single-winner races in Y-1): "
      + (", ".join(f"{c['Y']} {REG_NAMES[c['reg']]} {CG_NAMES[c['cg']]} ({c['races']})" for c in no2) or "none"))

    # stage-1 coefficients, the latest fit, as a sign check
    P("\n## 1. Stage-1 coefficients (fit for the last graded year; per global sd of each column)")
    Ylast = years[-1]
    rows = []
    for c_i, c in enumerate(ALL_COLS):
        grp = [g for g, cs in GROUPS.items() if c in cs][0]
        rows.append({"group": grp, "feature": c, "Flat": f"{base['b1'][(Ylast, 0)][c_i]:+.3f}",
                     "Jumps": f"{base['b1'][(Ylast, 1)][c_i]:+.3f}"})
    P(f"Trained on {max(FIRST_FIT_YEAR, Ylast - 1 - WINDOW)}-{Ylast - 2} (the stage 1 that feeds the blend). "
      "Positive = more likely to win. Columns are race-centred; rating columns are split into "
      "handicap (`_hc`) and non-handicap (`_nh`); `wgt_h` is the handicap interaction on weight.")
    P(md(rows))
    out["stage1_coef_last"] = rows

    # ---------------------------------------------------------------- log-likelihood
    P("\n## 2. Out-of-sample log-likelihood per race (single-winner gradeable races with every column)")
    P("SP is the close: every column but stage 1 has seen it. Stage 2 (blend) and calibrated SP are "
      "fitted on year Y-1 and applied to Y. Higher is better. Differences are x1000 per race with a 95% CI.")
    probs = {"sp_devig": Fr.p_sp, "sp_power": Fr.p_pow, "sp_calibrated": base["pcal"],
             "stage1": base["pm"], "stage1_pooled": pooled["pm"], "stage1_fresh": fresh["pm"],
             "blend": base["pstar"]}
    rows, d = ll_table(Fr, probs, graded, lambda m: np.char.add(
        np.array([REG_NAMES[r] for r in Fr.reg[m]]), np.array([" " + CG_NAMES[g] for g in Fr.cg[m]])))
    d2 = d.copy()
    for r in rows:
        g = d2[d2.k == r["group"]]
        r["blend - cal SP (x1000)"] = paired(g, "blend", "sp_calibrated")
        r["stage1 sep - pooled (x1000)"] = paired(g, "stage1", "stage1_pooled")
        r["fresh - stage1 (x1000)"] = paired(g, "stage1_fresh", "stage1")
        r["R2 stage1"] = f"{1 - g.stage1.mean() / g.unif.mean():.4f}"
        r["R2 cal SP"] = f"{1 - g.sp_calibrated.mean() / g.unif.mean():.4f}"
        r["R2 blend"] = f"{1 - g.blend.mean() / g.unif.mean():.4f}"
    for reg in ("GB", "IRE"):
        g = d2[d2.k.str.startswith(reg)]
        rows.append({"group": f"{reg} all", "races": f"{len(g):,}", "uniform": f"{g.unif.mean():.4f}",
                     **{c: f"{g[c].mean():.4f}" for c in probs},
                     "blend - cal SP (x1000)": paired(g, "blend", "sp_calibrated"),
                     "stage1 sep - pooled (x1000)": paired(g, "stage1", "stage1_pooled"),
                     "fresh - stage1 (x1000)": paired(g, "stage1_fresh", "stage1"),
                     "R2 stage1": f"{1 - g.stage1.mean() / g.unif.mean():.4f}",
                     "R2 cal SP": f"{1 - g.sp_calibrated.mean() / g.unif.mean():.4f}",
                     "R2 blend": f"{1 - g.blend.mean() / g.unif.mean():.4f}"})
    P(md(rows))
    out["ll"] = rows
    P("\nR2 = 1 - LL/LL(uniform), McFadden's pseudo-R2 against 1/runners. stage1 = fitted on Y-6..Y-2 "
      "(feeds the blend); stage1_fresh = fitted on Y-5..Y-1 (drives the decidable rule); stage1_pooled = "
      "one fit for Flat and jumps together on Y-6..Y-2. Dead-heat races are left out of every "
      "log-likelihood (they are still graded, by share).")

    # by year, per region
    P("\n## 3. By year: log-likelihood per race and the blend coefficients (b on stage 1, c on SP)")
    cf = pd.DataFrame(base["coefs"])
    cf_nf = pd.DataFrame(nofig["coefs"]) if nofig is not None else cf.iloc[0:0]
    mfull = have_all
    for reg_i, reg in REG_NAMES.items():
        rows = []
        m = mfull & (Fr.reg == reg_i)
        sel = m & Fr.ev1 & (Fr.won == 1)
        dd = pd.DataFrame({"y": np.where(Fr.H["new_format"].to_numpy()[sel], "2026 May-Oct",
                                         Fr.year[sel].astype(str)),
                           "sp": np.log(Fr.p_sp[sel]), "cal": np.log(base["pcal"][sel]),
                           "s1": np.log(base["pm"][sel]), "s1f": np.log(fresh["pm"][sel]),
                           "bl": np.log(base["pstar"][sel])})
        dd.loc[(dd.y == "2026"), "y"] = "2026 Jan-Apr"
        for y, g in dd.groupby("y", sort=True):
            yy = int(y[:4])
            cc = cf_nf if y.endswith("May-Oct") else cf
            c0 = cc[(cc.Y == yy) & (cc.reg == reg_i) & (cc.cg == 0)]
            c1 = cc[(cc.Y == yy) & (cc.reg == reg_i) & (cc.cg == 1)]
            rows.append({"year": y, "races": f"{len(g):,}", "SP devig": f"{g.sp.mean():.4f}",
                         "cal SP": f"{g.cal.mean():.4f}", "stage 1": f"{g.s1.mean():.4f}",
                         "stage 1 fresh": f"{g.s1f.mean():.4f}",
                         "blend": f"{g.bl.mean():.4f}",
                         "blend-cal x1000": paired(g.rename(columns={"bl": "blend", "cal": "c"}), "blend", "c"),
                         "Flat b": f"{c0.b.iloc[0]:+.3f}" if len(c0) else "", "Flat c": f"{c0.c.iloc[0]:+.3f}" if len(c0) else "",
                         "Jumps b": f"{c1.b.iloc[0]:+.3f}" if len(c1) else "", "Jumps c": f"{c1.c.iloc[0]:+.3f}" if len(c1) else "",
                         "SP-only c' Flat/Jumps": (f"{c0.c_sp_only.iloc[0]:.3f} / {c1.c_sp_only.iloc[0]:.3f}"
                                                   if len(c0) and len(c1) else "")})
        P(f"\n### {reg}")
        P("2026 is split at 2026-05-01, where the source changes format (no rpr/ts after it; "
          "the horse-id bridge links about 80% of rows, so some horses look like debutants). "
          "b and c are the Y-1 fits applied to Y. 2026 May-Oct uses the walk-forward without the "
          "figures group (its own b, c, fitted on 2025 with that stage 1).")
        P(md(rows))
        out[f"by_year_{reg}"] = rows

    # ---------------------------------------------------------------- the decidable rule
    P("\n## 4. DECIDABLE RULE: back stage 1's top-rated runner at SP (never reads SP to choose)")
    P("One bet per race. p = stage-1 probability of the top-rated runner; margin = its p minus the "
      "second-rated runner's. Stage 1 here is the fresh fit (years Y-5..Y-1, no SP anywhere in it). "
      "Graded at SP. Ties in the top spot are broken at random (shuffled rows). Units: 1 unit to win, "
      "risk 1/(SP-1) capped at 3; return = units / units risked; flat = 1 unit risked per bet.")
    tp = tops(Fr, fresh["pm"], graded)
    out["rule"] = {}
    PC = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6]
    MC = [0.0, 0.05, 0.10, 0.20]
    for reg_i, reg in REG_NAMES.items():
        rows = []
        t = tp[tp.reg == reg_i]
        for pc in PC:
            for mc in MC:
                g = t[(t.p1 > pc) & (t.margin > mc)] if pc > 0 or mc > 0 else t
                r = grade(g.sp, g.won, g.race)
                rows.append({"p >": pc, "margin >": mc, **gcells(r)})
                out["rule"][f"{reg}|{pc}|{mc}"] = r
        P(f"\n### {reg}, {years[0]}-{years[-1]}, neighbourhood of cuts")
        P(md(rows))

    CELLS = [(0.0, 0.0), (0.3, 0.1), (0.5, 0.2)]
    def cellmask(t, pc, mc):
        return (t.p1 > pc) & (t.margin > mc) if (pc > 0 or mc > 0) else np.ones(len(t), bool)
    for reg_i, reg in REG_NAMES.items():
        t = tp[tp.reg == reg_i]
        rows = []
        for per, g0 in t.groupby("period", sort=True):
            r = {"year": per}
            for pc, mc in CELLS:
                g = g0[cellmask(g0, pc, mc)]
                x = grade(g.sp, g.won, g.race)
                r[f"p>{pc},m>{mc} bets"] = f"{x.get('bets', 0):,}"
                r[f"p>{pc},m>{mc} units"] = f"{x['units']:+.1f}" if x.get("bets") else ""
                r[f"p>{pc},m>{mc} return"] = f"{100 * x['roi']:+.1f}%" if x.get("bets") else ""
            rows.append(r)
        P(f"\n### {reg} by year (three cells)")
        P(md(rows))
        out[f"rule_by_year_{reg}"] = rows
        rows = []
        mid = (years[0] + years[-1]) // 2
        for lab, g0 in (("early " + f"{years[0]}-{mid}", t[t.year <= mid]), ("late " + f"{mid + 1}-{years[-1]}", t[t.year > mid])):
            for pc, mc in CELLS:
                g = g0[cellmask(g0, pc, mc)]
                rows.append({"split": lab, "cell": f"p>{pc}, m>{mc}", **gcells(grade(g.sp, g.won, g.race))})
        for code, g0 in t.groupby("code", sort=True):
            for pc, mc in CELLS:
                g = g0[cellmask(g0, pc, mc)]
                rows.append({"split": code, "cell": f"p>{pc}, m>{mc}", **gcells(grade(g.sp, g.won, g.race))})
        for hc_, g0 in t.groupby("handicap", sort=True):
            for pc, mc in CELLS:
                g = g0[cellmask(g0, pc, mc)]
                rows.append({"split": "handicap" if hc_ else "non-handicap", "cell": f"p>{pc}, m>{mc}",
                             **gcells(grade(g.sp, g.won, g.race))})
        for hc_, g0 in t.groupby("handicap", sort=True):
            for lab, g1 in ((f"early {years[0]}-{mid}", g0[g0.year <= mid]), (f"late {mid + 1}-{years[-1]}", g0[g0.year > mid])):
                for pc, mc in CELLS:
                    g = g1[cellmask(g1, pc, mc)]
                    rows.append({"split": ("handicap " if hc_ else "non-handicap ") + lab, "cell": f"p>{pc}, m>{mc}",
                                 **gcells(grade(g.sp, g.won, g.race))})
        P(f"\n### {reg}: early/late, by code, handicap or not")
        P(md(rows))
        out[f"rule_splits_{reg}"] = rows

    # Every cut in each era, per region, on both stakes (the late grid is the test).
    mid = (years[0] + years[-1]) // 2
    late_mid = (mid + 1 + years[-1]) // 2
    for reg_i, reg in REG_NAMES.items():
        t = tp[tp.reg == reg_i]
        for lab, g0 in ((f"early {years[0]}-{mid}", t[t.year <= mid]),
                        (f"late {mid + 1}-{years[-1]}", t[t.year > mid])):
            rows = []
            for pc in PC:
                for mc in MC:
                    g = g0[cellmask(g0, pc, mc)]
                    rows.append({"p >": pc, "margin >": mc, **gcells(grade(g.sp, g.won, g.race))})
            P(f"\n### {reg}, {lab}: every cut")
            P(md(rows))
            out[f"rule_grid_{reg}_{lab.split()[0]}"] = rows

    # Race type is known before the race, so it is a legitimate split. It is printed by era,
    # with the late era also in halves, so a subgroup that looks good is judged as a
    # neighbourhood and over time, not picked out of a pooled table.
    for reg_i, reg in REG_NAMES.items():
        t = tp[tp.reg == reg_i]
        rows = []
        for code, gc in t.groupby("code", sort=True):
            for lab, g0 in ((f"early {years[0]}-{mid}", gc[gc.year <= mid]),
                            (f"late {mid + 1}-{years[-1]}", gc[gc.year > mid]),
                            (f"late half {mid + 1}-{late_mid}", gc[(gc.year > mid) & (gc.year <= late_mid)]),
                            (f"late half {late_mid + 1}-{years[-1]}", gc[gc.year > late_mid])):
                for pc in PC:
                    for mc in (0.0, 0.2):
                        g = g0[cellmask(g0, pc, mc)]
                        rows.append({"code": code, "era": lab, "p >": pc, "margin >": mc,
                                     **gcells(grade(g.sp, g.won, g.race))})
        P(f"\n### {reg}: race type by era (split after the pooled results were seen; every cell printed)")
        P(md(rows))
        out[f"rule_code_era_{reg}"] = rows

    # the same rule on gradeable_raw (keeps the races excluded for a low SP book / bad marker)
    # stage 1 predicted only gradeable races; predict the extra raw races with each year's fit
    pm_raw = fresh["pm"].copy()
    ex_rows = np.flatnonzero(np.isin(Fr.year, years) & Fr.H["gradeable_raw"].to_numpy() & ~Fr.ev)
    for Y in years:
        for g in (0, 1):
            msk = np.zeros(Fr.n, bool)
            msk[ex_rows] = True
            msk &= (Fr.year == Y) & (Fr.cg == g)
            if msk.any():
                old = msk & ~newf
                if old.any():
                    idx, p = predict(Fr, ALL_COLS, fresh["b1"][(Y, g)], old)
                    pm_raw[idx] = p
                if (msk & newf).any():
                    idx, p = predict(Fr, NOFIG, nfr["b1"][(Y, g)], msk & newf)
                    pm_raw[idx] = p
    rawm = np.isin(Fr.year, years) & Fr.H["gradeable_raw"].to_numpy()
    tr_ = tops(Fr, pm_raw, rawm)
    rows = []
    for reg_i, reg in REG_NAMES.items():
        t = tr_[tr_.reg == reg_i]
        for lab, g0 in ((f"{years[0]}-{years[-1]}", t), (f"early {years[0]}-{mid}", t[t.year <= mid]),
                        (f"late {mid + 1}-{years[-1]}", t[t.year > mid])):
            for pc, mc in CELLS:
                g = g0[cellmask(g0, pc, mc)]
                rows.append({"region": reg, "period": lab, "cell": f"p>{pc}, m>{mc}",
                             **gcells(grade(g.sp, g.won, g.race))})
    P("\n### The same rule on `gradeable_raw` (adds back races with an SP book under 1.0 or a bad favourite marker)")
    P(md(rows))
    out["rule_gradeable_raw"] = rows

    naive_baseline(Fr, years, out)

    # tie check
    ties = tp[np.isclose(tp.p1, tp.p2, rtol=0, atol=1e-12)]
    ex = float((1.0 / ties.ran).mean()) if len(ties) else float("nan")
    out["ties"] = {"races": int(len(ties)), "top_won": float(ties.won.mean()) if len(ties) else None,
                   "expected_1_over_n": ex}
    P(f"\nTie check: {len(ties):,} graded races where the top two stage-1 probabilities are equal. "
      f"The picked runner won {100 * out['ties']['top_won']:.1f}% of them; 1/runners averages "
      f"{100 * ex:.1f}%." if len(ties) else "\nTie check: no exactly tied tops.")
    near = tp[tp.margin < 0.005]
    out["near_ties"] = {"races": int(len(near)), "top_won": float(near.won.mean()),
                        "mean_p1": float(near.p1.mean()), "mean_p2": float(near.p2.mean())}
    P(f"Near-ties (top two within 0.005): {len(near):,} races; the picked runner won "
      f"{100 * near.won.mean():.2f}% against a stage-1 probability of {100 * near.p1.mean():.2f}% "
      f"(second {100 * near.p2.mean():.2f}%). A pick that read the row order would win far more.")

    # descriptive tables that read SP (labelled)
    P("\n## 5. DESCRIPTIVE ONLY (reads SP, which is the close): favourites and the top-rated runner")
    rows = []
    for reg_i, reg in REG_NAMES.items():
        t = tp[tp.reg == reg_i]
        m = graded & (Fr.reg == reg_i)
        idx = np.flatnonzero(m)
        minsp = pd.Series(Fr.sp[idx]).groupby(Fr.rk[idx]).transform("min").to_numpy()
        fav = idx[Fr.sp[idx] == minsp]
        nf = pd.Series(np.ones(len(fav))).groupby(Fr.rk[fav]).transform("sum").to_numpy()
        rows.append({"region": reg, "set": "SP favourite (joint favourites split)",
                     **gcells(grade(Fr.sp[fav], Fr.won[fav], Fr.rk[fav], 1.0 / nf))})
        for lab, g in (("top-rated AND SP favourite", t[t.is_sp_fav]), ("top-rated, NOT SP favourite", t[~t.is_sp_fav])):
            rows.append({"region": reg, "set": lab, **gcells(grade(g.sp, g.won, g.race))})
        rows.append({"region": reg, "set": f"share of top-rated that are SP favourite: {100 * t.is_sp_fav.mean():.1f}%"})
    P(md(rows))
    out["descriptive"] = rows

    # upper bound: blend overlay
    P("\n## 6. UPPER BOUND (conditions on SP): one bet per race on the blend's best EV = p_blend x SP - 1")
    rows = []
    out["blend_ev"] = {}
    for reg_i, reg in REG_NAMES.items():
        m = have_all & (Fr.reg == reg_i)
        ev = base["pstar"] * Fr.sp - 1.0
        tb = tops(Fr, np.where(m, ev, np.nan), m)
        for cut in [0.0, 0.05, 0.10, 0.20, 0.30, 0.50]:
            g = tb[tb.p1 > cut]
            r = grade(g.sp, g.won, g.race)
            out["blend_ev"][f"{reg}|{cut}"] = r
            mid = (years[0] + years[-1]) // 2
            e = grade(g[g.year <= mid].sp, g[g.year <= mid].won, g[g.year <= mid].race)
            l_ = grade(g[g.year > mid].sp, g[g.year > mid].won, g[g.year > mid].race)
            rows.append({"region": reg, "EV >": cut, **gcells(r),
                         "early return": f"{100 * e['roi']:+.2f}%" if e.get("bets") else "",
                         "late return": f"{100 * l_['roi']:+.2f}%" if l_.get("bets") else ""})
    P(md(rows))

    # ---------------------------------------------------------------- leak check
    if not a.no_leak:
        P(f"\n## 7. Leak check: add THIS race's own rpr (a post-race figure) to stage 1, {ly[0]}-{ly[-1]}")
        P("Dates from 2026-05-01 have no rpr, so the check stops at 2025. The harness must light up.")
        lk = walk(Fr, ALL_COLS + LEAK_COLS, ly, B1, tag="leak")
        ref_m = np.isin(Fr.year, ly) & np.isfinite(base["pstar"]) & np.isfinite(lk["pstar"])
        rows = []
        for reg_i, reg in REG_NAMES.items():
            sel = ref_m & (Fr.reg == reg_i) & Fr.ev1 & (Fr.won == 1)
            ll = lambda p: f"{np.log(np.clip(p[sel], 1e-12, 1)).mean():.4f}"
            cfl = pd.DataFrame(lk["coefs"])
            cfl = cfl[cfl.reg == reg_i]
            cfb = cf[(cf.reg == reg_i) & cf.Y.isin(ly)]
            t_l = tops(Fr, lk["pm"], ref_m & (Fr.reg == reg_i))
            t_b = tops(Fr, base["pm"], ref_m & (Fr.reg == reg_i))
            rl, rb = grade(t_l.sp, t_l.won, t_l.race), grade(t_b.sp, t_b.won, t_b.race)
            rows.append({"region": reg, "races": f"{int(sel.sum()):,}", "LL cal SP": ll(base["pcal"]),
                         "LL stage1": ll(base["pm"]), "LL stage1 + own rpr": ll(lk["pm"]),
                         "LL blend": ll(base["pstar"]), "LL blend + own rpr": ll(lk["pstar"]),
                         "median b": f"{cfb.b.median():+.3f}", "median b + own rpr": f"{cfl.b.median():+.3f}",
                         "median c": f"{cfb.c.median():+.3f}", "median c + own rpr": f"{cfl.c.median():+.3f}",
                         "top-rated return": f"{100 * rb['roi']:+.2f}% ({rb['bets']:,} bets, {rb['units']:+.1f}u)",
                         "top-rated return + own rpr": f"{100 * rl['roi']:+.2f}% ({rl['bets']:,} bets, {rl['units']:+.1f}u)"})
        P(md(rows))
        out["leak_check"] = rows

    # ---------------------------------------------------------------- ablation
    if not a.no_ablation:
        P(f"\n## 8. Ablation: remove one feature group, {ay[0]}-{ay[-1]} (to 2026-04-30); paired change per race x1000 (95% CI)")
        P("Negative = the model is worse without the group. Same races as the full model.")
        ref = np.isin(Fr.year, ay) & have_all & ~newf
        rows = []
        for gname, gcols in GROUPS.items():
            keep = [c for c in ALL_COLS if c not in gcols]
            t0 = time.time()
            w2 = walk(Fr, keep, ay, B1, tag=f"abl:{gname}")
            m = ref & np.isfinite(w2["pstar"])
            for reg_i, reg in REG_NAMES.items():
                for cg_i, cgn in CG_NAMES.items():
                    sel = m & (Fr.reg == reg_i) & (Fr.cg == cg_i) & Fr.ev1 & (Fr.won == 1)
                    dd = pd.DataFrame({"s1": np.log(base["pm"][sel]), "s1x": np.log(w2["pm"][sel]),
                                       "bl": np.log(base["pstar"][sel]), "blx": np.log(w2["pstar"][sel])})
                    rows.append({"group removed": gname, "cell": f"{reg} {cgn}", "races": f"{len(dd):,}",
                                 "stage 1 (x1000)": paired(dd, "s1x", "s1"),
                                 "blend (x1000)": paired(dd, "blx", "bl")})
            P(f"  (ablation {gname}: {time.time() - t0:.0f} s)", file=sys.stderr)
        P(md(rows))
        out["ablation"] = rows

    out["total_s"] = round(time.time() - T0, 1)
    P(f"\nTotal {out['total_s']} s.")
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
        P(f"wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

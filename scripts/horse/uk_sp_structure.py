"""UK and Ireland at starting price: market structure, 1988-2026.

Four questions, all on the GB and Irish races `uk_sp_data.load` marks gradeable:

  1. Is SP calibrated? De-vigged chance (proportional and power) against the win
     rate by SP band, by period and by code, Britain and Ireland apart. This is the
     favourite-longshot table. DESCRIPTIVE.
  2. Blind win bets at SP: by SP band and SP rank (DESCRIPTIVE: the band is read from
     the SP), and by things known before the race (year, code, handicap, field size,
     the official-rating rank within the race, the top-rated horse's rating margin),
     which are RULES.
  3. Each-way at SP under the standard terms (an ASSUMPTION; books often paid more):
        2-4 runners           win only (no place part, so no each-way bet here)
        5-7 runners           2 places at 1/4 the odds
        8+ runners            3 places at 1/5
        handicap 12-15        3 places at 1/4
        handicap 16+          4 places at 1/4
     The place part is graded at 1 + (SP - 1) x fraction. The whole each-way bet is two
     bets, the win part at SP and the place part at its odds, each sized by the stake
     rule. Flat equal stakes on both halves is the real bookmaker each-way bet and is
     printed beside it. A calibrated place model (a conditional logit on SP, a Harville
     discount and a recalibration by places paid, all fitted on 1988-2004, tested on
     2005-2026) shows where the place part is under- or over-priced.
  4. Year-by-year stability of anything that looks positive on 1988-2004, and the
     split 2005-2014 against 2015-2026.

WHAT IS DECIDABLE. A bet at SP is executable at a UK bookmaker, so every rule is GRADED
at SP. Anything that CONDITIONS on a runner's SP, its SP rank, the race's favourite
price or the model's EV (which is built from SP) has seen the close: those tables are
labelled UPPER BOUND / DESCRIPTIVE. The official rating ("or"), field size, code,
handicap and places paid are known before the race. (The loader's notes say "or" is
blank from 2026-05-01; Table 0b measured 99.8% of GB and 100% of Irish handicaps fully
rated in May-Oct 2026, so the rating rules do run after 2026-04.)

UNITS. The repo's published stake: 1 unit to win, risk min(1/(decimal-1), 3)
(`anz_study.stake_units`, no commission). Return = units / units risked, 95% interval
clustered by race. Note the stake rule sizes each bet off the SP itself, which a bettor
at SP cannot know when placing; the flat-stake return is the executable figure.

CANDIDATES. Every rule or structure cell is graded on 1988-2004 (the training window),
2005-2014 and 2015-2026. A cell is a candidate when it has at least --min-bets bets on
1988-2004 and a positive return there (units or flat). It CLEARS when, on 2005-2026
pooled, the flat return's lower 95% bound is above 0, the units return is above 0, and
both halves are positive on flat. Section 4 prints every candidate, its year-by-year
record, and the cells that look positive only in 2005-2026 ("selected in sample").

    python -I scripts/horse/uk_sp_structure.py
    python -I scripts/horse/uk_sp_structure.py --years 2005-2012 --train-end 2007 --split 2010   # dev window

A window that reaches before 2005 loads every year and filters afterwards. That was a
workaround for a loader bug (its `years` filter failed on any window touching 1988-2004),
fixed 2026-11-16 and pinned by tests/test_uk_sp_data.py; it gives the same rows.
"""
from __future__ import annotations

import argparse
import itertools
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
from scripts.horse.anz_study import devig, harville_top, stake_units  # noqa: E402
from scripts.horse.clogit import fit_clogit, softmax_by_race, starts_of  # noqa: E402
from scripts.horse.uk_sp_data import load, place_terms, placed  # noqa: E402

REG = ["GB", "IRE"]
CODES = ["Flat", "Hurdle", "Chase", "NH Flat"]
SP_EDGES = [1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 34.0, 51.0, 101.0, np.inf]
SP_LAB = ["under 1/2 (<1.5)", "1/2 to <Evs (1.5-2)", "Evs to <2/1 (2-3)", "2/1 to <4/1 (3-5)",
          "4/1 to <7/1 (5-8)", "7/1 to <12/1 (8-13)", "12/1 to <20/1 (13-21)",
          "20/1 to <33/1 (21-34)", "33/1 to <50/1 (34-51)", "50/1 to <100/1 (51-101)", "100/1+ (101+)"]
EW_EDGES = [1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 34.0, np.inf]
EW_LAB = ["under Evs (<2)", "Evs to <2/1 (2-3)", "2/1 to <4/1 (3-5)", "4/1 to <7/1 (5-8)",
          "7/1 to <12/1 (8-13)", "12/1 to <20/1 (13-21)", "20/1 to <33/1 (21-34)", "33/1+ (34+)"]
CAL_PERIODS = [(1988, 1999), (2000, 2009), (2010, 2019), (2020, 2026)]
LAM_GRID = np.round(np.arange(0.60, 1.1001, 0.05), 2)
CHUNK = 4_000_000

OUT: list[str] = []


def P(s: str = "") -> None:
    print(s, flush=True)
    OUT.append(s)


def table(headers: list[str], rows: list[list]) -> None:
    P("| " + " | ".join(headers) + " |")
    P("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        P("| " + " | ".join(str(x) for x in r) + " |")
    P()


def band(x: np.ndarray, edges) -> np.ndarray:
    return np.digitize(x, edges[1:-1], right=False)


# ================================================================== grading

def grade(dec, share, rix, n_races: int, parts: int = 1) -> dict:
    """Stake-rule units and flat return for a bet set, both clustered by race."""
    dec = np.asarray(dec, float)
    share = np.asarray(share, float)
    if len(dec) == 0:
        return {"bets": 0}
    profit, risk = stake_units(dec, share, 0.0)
    flat = share * (dec - 1.0) - (1.0 - share)
    Pp = np.bincount(rix, profit, minlength=n_races)
    Rr = np.bincount(rix, risk, minlength=n_races)
    Ff = np.bincount(rix, flat, minlength=n_races)
    Nn = np.bincount(rix, minlength=n_races).astype(float)
    k = Nn > 0
    Pp, Rr, Ff, Nn = Pp[k], Rr[k], Ff[k], Nn[k]
    roi = Pp.sum() / Rr.sum()
    se = math.sqrt(((Pp - roi * Rr) ** 2).sum()) / Rr.sum()
    fr = Ff.sum() / Nn.sum()
    fse = math.sqrt(((Ff - fr * Nn) ** 2).sum()) / Nn.sum()
    return {"bets": int(len(dec) // parts), "races": int(k.sum()), "units": float(Pp.sum()),
            "risk": float(Rr.sum()), "roi": roi, "lo": roi - 1.96 * se, "hi": roi + 1.96 * se,
            "flat": fr, "flo": fr - 1.96 * fse, "fhi": fr + 1.96 * fse}


def gcols(r: dict) -> list[str]:
    if not r.get("bets"):
        return ["0", "", "", ""]
    return [f"{r['bets']:,}", f"{r['units']:+,.1f}",
            f"{100 * r['roi']:+.2f} [{100 * r['lo']:+.2f}, {100 * r['hi']:+.2f}]",
            f"{100 * r['flat']:+.2f} [{100 * r['flo']:+.2f}, {100 * r['fhi']:+.2f}]"]


GHEAD = ["bets", "units", "return % [95% CI]", "flat % [95% CI]"]


def gcell(r: dict) -> str:
    if not r.get("bets"):
        return "0 bets"
    return (f"{r['bets']:,}; {r['units']:+,.1f}u; {100 * r['roi']:+.1f}% "
            f"[{100 * r['lo']:+.1f},{100 * r['hi']:+.1f}]; f {100 * r['flat']:+.1f}%")


def gshort(r: dict) -> str:
    if not r.get("bets"):
        return "0"
    return f"{r['bets']:,}: f {100 * r['flat']:+.1f}% / u {100 * r['roi']:+.1f}%"


# ================================================================== the frame

KEEP = ["race_key", "year", "region", "code", "handicap", "ran", "pos", "dh_n", "n_first", "won",
        "sp", "book", "gradeable", "or_num", "new_format"]


def race_starts(r: np.ndarray) -> np.ndarray:
    return starts_of(pd.DataFrame({"race_key": r}), "race_key")


def power_devig(q: np.ndarray, starts: np.ndarray, sizes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """anz_study.devig(q, 'power') for every race at once: the same 60-step bisection
    on the exponent k in [0.2, 5] so that sum q**k = 1."""
    lq = np.log(q)
    lo = np.full(len(starts), 0.2)
    hi = np.full(len(starts), 5.0)
    for _ in range(60):
        k = 0.5 * (lo + hi)
        s = np.add.reduceat(np.exp(lq * np.repeat(k, sizes)), starts)
        gt = s > 1.0
        lo = np.where(gt, k, lo)
        hi = np.where(gt, hi, k)
    k = 0.5 * (lo + hi)
    p = np.exp(lq * np.repeat(k, sizes))
    p = p / np.repeat(np.add.reduceat(p, starts), sizes)
    return p, k


def build(years) -> tuple[dict, dict]:
    t0 = time.time()
    log: dict = {}
    if years is not None and min(years) >= 2005:
        df = load(cols=["or"], years=years, log=log)
    else:
        df = load(cols=["or"], years=None, log=log)
    keep = df["gradeable_raw"].to_numpy() & (df["ran"].to_numpy() >= 2)
    if years is not None:
        keep &= np.isin(df["year"].to_numpy(), list(years))
    d = df.loc[keep, KEEP].reset_index(drop=True)
    del df
    info = {"load_seconds": round(time.time() - t0, 1)}
    starts = race_starts(d["race_key"].to_numpy())
    sizes = np.diff(np.append(starts, len(d)))
    nr = len(starts)
    ridx = np.repeat(np.arange(nr), sizes).astype(np.int64)
    ran = d["ran"].to_numpy().astype(int)
    assert (ran[starts] == sizes).all(), "a gradeable race holds a different number of rows than runners"
    F: dict = {"ridx": ridx, "starts": starts, "sizes": sizes, "n_races": nr}
    F["year"] = d["year"].to_numpy().astype(int)
    F["reg"] = d["region"].cat.codes.to_numpy().astype(int)        # 0 GB, 1 IRE
    assert set(np.unique(F["reg"])) <= {0, 1}
    F["code"] = d["code"].cat.codes.to_numpy().astype(int)         # 0 Flat .. 3 NH Flat
    assert (F["code"] >= 0).all()
    F["hcp"] = d["handicap"].to_numpy().astype(bool)
    F["ran"] = ran
    F["clean"] = d["gradeable"].to_numpy().astype(bool)
    F["new"] = d["new_format"].to_numpy().astype(bool)
    F["n_first"] = d["n_first"].to_numpy().astype(int)
    sp = d["sp"].to_numpy().astype(float)
    F["sp"] = sp
    F["won"] = d["won"].to_numpy().astype(float)
    places, frac = place_terms(ran, F["hcp"])
    F["places"], F["frac"] = places, frac
    F["pshare"] = placed(d)
    F["pdec"] = 1.0 + (sp - 1.0) * frac
    q = 1.0 / sp
    F["q"] = q
    F["book"] = d["book"].to_numpy().astype(float)
    F["p_prop"] = q / F["book"]
    F["p_pow"], kexp = power_devig(q, starts, sizes)
    F["k_pow"] = kexp
    F["sprank"] = pd.Series(sp).groupby(ridx).rank(method="min").to_numpy()
    fav = np.minimum.reduceat(sp, starts)
    F["fav_sp"] = np.repeat(fav, sizes)
    # official rating: rank within the race (1 = highest), share rated, top-two margin
    orr = d["or_num"].to_numpy().astype(float)
    rated = np.isfinite(orr) & (orr > 0)
    orr = np.where(rated, orr, np.nan)
    F["or"] = orr
    F["or_rank"] = pd.Series(orr).groupby(ridx).rank(method="min", ascending=False).to_numpy()
    n_rated = np.add.reduceat(rated.astype(int), starts)
    F["all_rated"] = np.repeat(n_rated == sizes, sizes)
    F["any_rated"] = np.repeat(n_rated > 0, sizes)
    of = np.where(rated, orr, -1.0)
    order = np.lexsort((-of, ridx))
    top = of[order[starts]]
    second = np.where(sizes >= 2, of[order[np.minimum(starts + 1, len(of) - 1)]], -1.0)
    gap = np.where((n_rated == sizes) & (sizes >= 2), top - second, np.nan)
    F["or_gap"] = np.repeat(gap, sizes)
    info["build_seconds"] = round(time.time() - t0, 1)
    return F, info


# ================================================================== Harville to 4 places

def harville_batch(Pm: np.ndarray, Qm: np.ndarray, k: int) -> np.ndarray:
    """P(each runner in the first k), k <= 4, for R races of n runners at once.
    Pm: win probabilities (R, n). Qm: the distribution later places are drawn from
    (p**lam renormalised), as in anz_study.harville_top."""
    R, n = Pm.shape
    out = Pm.copy()
    if k < 2:
        return out
    a = Pm / (1.0 - Qm)                                   # p_j / (1 - q_j)
    out = out + Qm * (a.sum(1, keepdims=True) - a)        # second place
    if k < 3:
        return np.minimum(out, 1.0)
    eye = np.eye(n, dtype=bool)
    D = 1.0 - Qm[:, :, None] - Qm[:, None, :]
    D = np.where(eye[None], 1.0, D)
    A = a[:, :, None] * Qm[:, None, :] / D                # A[j,l] = p_j q_l / ((1-q_j)(1-q_j-q_l))
    A[:, eye] = 0.0
    totA = A.sum((1, 2))
    out = out + Qm * (totA[:, None] - A.sum(2) - A.sum(1))  # third place
    if k < 4:
        return np.minimum(out, 1.0)
    D3 = D[:, :, :, None] - Qm[:, None, None, :]           # 1 - q_j - q_l - q_m
    distinct = ~(eye[:, :, None] | eye[:, None, :] | eye[None, :, :])
    W = np.where(distinct[None], A[:, :, :, None] * Qm[:, None, None, :]
                 / np.where(distinct[None], D3, 1.0), 0.0)
    totW = W.sum((1, 2, 3))
    cont = W.sum((2, 3)) + W.sum((1, 3)) + W.sum((1, 2))
    out = out + Qm * (totW[:, None] - cont)               # fourth place
    return np.minimum(out, 1.0)


def harville_rows(p: np.ndarray, lam_row: np.ndarray, F: dict, races: np.ndarray) -> np.ndarray:
    """Top-k chance (k = places paid) for every runner of the given races."""
    starts, sizes = F["starts"], F["sizes"]
    qq = p ** lam_row
    qq = qq / np.repeat(np.add.reduceat(qq, starts), sizes)
    out = np.full(len(p), np.nan)
    kr = F["places"][starts]
    key = sizes[races] * 8 + kr[races]
    for kv in np.unique(key):
        rs = races[key == kv]
        n, k = int(kv // 8), int(kv % 8)
        idx = starts[rs][:, None] + np.arange(n)[None, :]
        per = n ** max(k - 1, 1)
        step = max(1, CHUNK // per)
        for c in range(0, len(rs), step):
            ii = idx[c:c + step]
            out[ii] = harville_batch(p[ii], qq[ii], k)
    return out


def check_harville(rng) -> dict:
    """Batch Harville against anz_study.harville_top (k <= 3) and brute force (k = 4)."""
    res = {}
    for k in (2, 3):
        for lam in (1.0, 0.8):
            worst = 0.0
            for n in (5, 8, 12, 17):
                Pm = rng.dirichlet(np.ones(n) * 0.7, size=40)
                Qm = Pm ** lam
                Qm = Qm / Qm.sum(1, keepdims=True)
                b = harville_batch(Pm, Qm, k)
                ref = np.vstack([harville_top(Pm[i], k, lam) for i in range(len(Pm))])
                worst = max(worst, float(np.abs(b - ref).max()))
            res[f"k={k} lam={lam} vs harville_top"] = worst
    for lam in (1.0, 0.8):
        worst = 0.0
        for n in (5, 6, 7, 9):
            Pm = rng.dirichlet(np.ones(n) * 0.7, size=15)
            Qm = Pm ** lam
            Qm = Qm / Qm.sum(1, keepdims=True)
            b = harville_batch(Pm, Qm, 4)
            for i in range(len(Pm)):
                p, q = Pm[i], Qm[i]
                bf = np.zeros(n)
                for t in itertools.permutations(range(n), 4):
                    pr = p[t[0]] * q[t[1]] / (1 - q[t[0]]) * q[t[2]] / (1 - q[t[0]] - q[t[1]]) \
                        * q[t[3]] / (1 - q[t[0]] - q[t[1]] - q[t[2]])
                    for j in t:
                        bf[j] += pr
                worst = max(worst, float(np.abs(b[i] - bf).max()))
        res[f"k=4 lam={lam} vs brute force"] = worst
    return res


# ================================================================== small models

def fit_logistic(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Logistic regression (first column of X is the intercept) by cross-entropy with a
    fractional target y."""
    def f(w):
        pz = 1.0 / (1.0 + np.exp(-(X @ w)))
        pz = np.clip(pz, 1e-12, 1 - 1e-12)
        ll = -(y * np.log(pz) + (1 - y) * np.log(1 - pz)).mean()
        return ll, X.T @ (pz - y) / len(y)
    w0 = np.zeros(X.shape[1])
    w0[1] = 1.0
    return minimize(f, w0, jac=True, method="BFGS").x


def recal_design(ph: np.ndarray) -> np.ndarray:
    z = logit(ph)
    return np.column_stack([np.ones(len(z)), z, z * z / 10.0])


def logit(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def ce(p, y):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def win_features(F: dict) -> np.ndarray:
    # On the power-devigged chance, so each race's own book is taken out first: the Irish
    # book fell from about 1.4 to 1.2 over the period, and a fixed map from raw 1/SP
    # fitted on the fat-book years does not transfer.
    lp = np.log(F["p_pow"])
    lb = np.log(F["book"]) * 10.0
    return np.column_stack([lp, lp * lp / 10.0, lp * (F["ran"] - 10) / 10.0, lp * (F["code"] != 0),
                            lp * lb, lp * lp * lb / 10.0])


# ================================================================== main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default=None, help="dev window, e.g. 2005-2012 (default: every year)")
    ap.add_argument("--train-end", type=int, default=2004, help="last year of the fitting window")
    ap.add_argument("--split", type=int, default=2015, help="first year of the late test half")
    ap.add_argument("--min-bets", type=int, default=200)
    ap.add_argument("--md", type=Path, default=None, help="also write the markdown here")
    a = ap.parse_args(argv)
    years = None
    if a.years:
        lo, _, hi = a.years.partition("-")
        years = list(range(int(lo), int(hi or lo) + 1))
    T0 = time.time()
    rng = np.random.default_rng(20261115)
    F, info = build(years)
    nr = F["n_races"]
    yr, reg, ridx = F["year"], F["reg"], F["ridx"]
    starts, sizes = F["starts"], F["sizes"]
    ry = yr[starts]
    TE, SPL = a.train_end, a.split
    y0, y1 = int(yr.min()), int(yr.max())
    PER = {"train": yr <= TE, "a": (yr > TE) & (yr < SPL), "b": yr >= SPL, "test": yr > TE}
    PLAB = {"train": f"{y0}-{TE}", "a": f"{TE + 1}-{SPL - 1}", "b": f"{SPL}-{y1}", "test": f"{TE + 1}-{y1}"}
    clean = F["clean"]

    P(f"# UK and Ireland at SP: market structure ({y0}-{y1})")
    P()
    P(f"Command: `python -I scripts/horse/uk_sp_structure.py"
      + (f" --years {a.years} --train-end {TE} --split {SPL}" if a.years else "") + "`")
    P(f"Load {info['load_seconds']} s, frame built {info['build_seconds']} s.")
    P()

    # ------------------------------------------------------------ 0. universe and checks
    P("## 0. Universe and checks")
    P()
    rows = []
    for r in (0, 1):
        for pk in ("train", "a", "b"):
            m = clean & (reg == r) & PER[pk]
            mr = (F["reg"][starts] == r) & (PER[pk][starts])
            rows.append([REG[r], PLAB[pk], f"{int((clean[starts] & mr).sum()):,}", f"{int(m.sum()):,}",
                         f"{int(mr.sum()):,}",
                         f"{np.median(F['book'][starts][clean[starts] & mr]):.3f}" if (clean[starts] & mr).any() else ""])
    P("Table 0a. Gradeable races (the analysis set) and gradeable_raw races (before the two SP-hygiene filters), "
      "fields of 2+ runners.")
    table(["region", "years", "races", "runners", "races incl. hygiene-excluded", "median SP book"], rows)

    smp = rng.choice(nr, size=min(2000, nr), replace=False)
    worst = 0.0
    for i in smp:
        s, n = starts[i], sizes[i]
        worst = max(worst, float(np.abs(devig(F["q"][s:s + n], "power") - F["p_pow"][s:s + n]).max()))
    hv = check_harville(rng)
    P("Checks:")
    P(f"- vectorised power de-vig against `anz_study.devig(q, 'power')` on {len(smp):,} random races: "
      f"max abs difference {worst:.2e}")
    for k_, v in hv.items():
        P(f"- batch Harville, {k_}: max abs difference {v:.2e}")
    sh = F["pshare"][clean & (F["ran"] >= 5)]
    P(f"- place shares sum per race to places paid: "
      f"{100 * np.mean(np.isclose(np.add.reduceat(F['pshare'], starts), np.minimum(F['places'][starts], sizes))[clean[starts] & (sizes >= 5)]):.2f}% "
      f"of gradeable races of 5+ runners; mean place share {sh.mean():.4f}")
    P()

    # OR coverage
    rows = []
    cov_periods = [(1988, 1994), (1995, 2004), (2005, 2014), (2015, 2025)]
    for r in (0, 1):
        for h in (False, True):
            row = [REG[r], "handicap" if h else "non-handicap"]
            for (lo, hi) in cov_periods + [(2026, 2026)]:
                mr = clean[starts] & (reg[starts] == r) & (F["hcp"][starts] == h) & (ry >= lo) & (ry <= hi)
                if lo == 2026:
                    old = mr & ~F["new"][starts]
                    new = mr & F["new"][starts]
                    row.append(f"{100 * F['all_rated'][starts][old].mean():.1f} / {100 * F['all_rated'][starts][new].mean():.1f}"
                               if old.any() and new.any() else "")
                else:
                    row.append(f"{100 * F['all_rated'][starts][mr].mean():.1f} ({int(mr.sum()):,})" if mr.any() else "")
            rows.append(row)
    P("Table 0b. Share of gradeable races in which every runner has an official rating, % (races). "
      "The rating rules below run only on these races; for non-handicaps that is a selected subset "
      "(rated conditions and pattern races, not maidens or bumpers).")
    table(["region", "race", "1988-1994", "1995-2004", "2005-2014", "2015-2025", "2026 Jan-Apr / May-Oct"], rows)

    # ------------------------------------------------------------ 1. calibration
    won = F["won"]
    Xw = win_features(F)
    pmod = np.full(len(won), np.nan)
    coefs = {}
    for r in (0, 1):
        fitr = clean[starts] & (reg[starts] == r) & (ry <= TE) & (F["n_first"][starts] == 1)
        rows_fit = np.repeat(fitr, sizes)
        st = race_starts(ridx[rows_fit])
        b = fit_clogit(Xw[rows_fit], won[rows_fit], st, l2=1.0)
        coefs[REG[r]] = b
        allr = np.repeat(reg[starts] == r, sizes)
        pmod[allr] = softmax_by_race(Xw[allr] @ b, race_starts(ridx[allr]))
    F["p_mod"] = pmod

    P("## 1. Calibration of SP (DESCRIPTIVE: banded by SP)")
    P()
    P("A/E = actual wins / expected wins. Band by the runner's decimal SP. `prop` divides 1/SP by the "
      "race's book; `power` raises 1/SP to the per-race power that makes the book 1 (`anz_study.devig`). "
      f"`model` is a conditional logit on log p, (log p)^2/10, log p x (runners-10)/10, log p x jumps, and log p and "
      f"(log p)^2/10 times 10 log(book), with p the power-devigged chance, "
      f"fitted per region on {y0}-{TE} with `clogit.fit_clogit`, shown on {PLAB['test']} only.")
    P()
    for r in (0, 1):
        P(f"- win model coefficients {REG[r]}: " + ", ".join(f"{v:+.4f}" for v in coefs[REG[r]]))
    P()
    sb = band(F["sp"], SP_EDGES)
    rows = []
    for r in (0, 1):
        for bi, lab in enumerate(SP_LAB):
            m = clean & (reg == r) & (sb == bi)
            mt = m & PER["test"]
            if not m.any():
                continue
            rows.append([REG[r], lab, f"{int(m.sum()):,}", f"{won[m].mean():.4f}", f"{F['q'][m].mean():.4f}",
                         f"{F['p_prop'][m].mean():.4f}", f"{F['p_pow'][m].mean():.4f}",
                         f"{won[m].sum() / F['p_prop'][m].sum():.3f}", f"{won[m].sum() / F['p_pow'][m].sum():.3f}",
                         f"{won[mt].sum() / pmod[mt].sum():.3f}" if mt.any() else ""])
    P(f"Table 1a. Win rate against SP chance by SP band, {y0}-{y1}.")
    table(["region", "SP band", "runners", "win rate", "mean 1/SP", "mean prop", "mean power",
           "A/E prop", "A/E power", f"A/E model {PLAB['test']}"], rows)

    def ae_grid(groups, glabs, title):
        rows = []
        for r in (0, 1):
            for bi, lab in enumerate(SP_LAB):
                row = [REG[r], lab]
                for gm in groups:
                    m = clean & (reg == r) & (sb == bi) & gm
                    row.append(f"{won[m].sum() / F['p_prop'][m].sum():.2f} / {won[m].sum() / F['p_pow'][m].sum():.2f} "
                               f"({int(m.sum()):,})" if m.sum() >= 50 else "")
                rows.append(row)
        P(title)
        table(["region", "SP band"] + glabs, rows)

    ae_grid([(yr >= lo) & (yr <= hi) for lo, hi in CAL_PERIODS], [f"{lo}-{hi}" for lo, hi in CAL_PERIODS],
            "Table 1b. A/E prop / A/E power (runners) by SP band and period. Blank: under 50 runners.")
    ae_grid([F["code"] == c for c in range(4)], CODES,
            f"Table 1c. A/E prop / A/E power (runners) by SP band and code, {y0}-{y1}.")

    rows = []
    one = (F["n_first"] == 1) & (won == 1) & clean
    for r in (0, 1):
        for lo, hi in CAL_PERIODS:
            m = one & (reg == r) & (yr >= lo) & (yr <= hi)
            if not m.any():
                continue
            mr = clean[starts] & (reg[starts] == r) & (ry >= lo) & (ry <= hi)
            rows.append([REG[r], f"{lo}-{hi}", f"{int(m.sum()):,}", f"{np.median(F['book'][starts][mr]):.3f}",
                         f"{np.median(F['k_pow'][mr]):.3f}",
                         f"{-np.log(F['p_prop'][m]).mean():.4f}", f"{-np.log(F['p_pow'][m]).mean():.4f}",
                         f"{-np.log(pmod[m]).mean():.4f}",
                         "in" if hi <= TE else ("out" if lo > TE else "mixed")])
    P("Table 1d. Mean negative log chance of the winner per race (lower is better), one-winner races. "
      f"`model` is fitted on {y0}-{TE}; the last column says whether a row is in-sample, out-of-sample "
      "or mixed for it. Power exponent: the per-race k with sum (1/SP)^k = 1.")
    table(["region", "years", "races", "median book", "median power exponent", "prop", "power", "model",
           "model sample"], rows)

    # ------------------------------------------------------------ grading machinery
    CANDS: list[dict] = []
    pdec, psh, sp = F["pdec"], F["pshare"], F["sp"]
    ew_ok = F["ran"] >= 5

    def bets(m, kind, base=None):
        m = m & (clean if base is None else base)
        if kind == "win":
            return grade(sp[m], won[m], ridx[m], nr)
        m = m & ew_ok
        if kind == "place":
            return grade(pdec[m], psh[m], ridx[m], nr)
        return grade(np.r_[sp[m], pdec[m]], np.r_[won[m], psh[m]], np.r_[ridx[m], ridx[m]], nr, parts=2)

    def cand(tab, label, m, kind, decidable):
        res = {pk: bets(m & PER[pk], kind) for pk in ("train", "a", "b", "test")}
        tr = res["train"]
        flagged = bool(tr.get("bets", 0) >= a.min_bets and (tr["roi"] > 0 or tr["flat"] > 0))
        te = res["test"]
        clears = bool(te.get("bets", 0) and te["flo"] > 0 and te["roi"] > 0
                      and res["a"].get("bets", 0) and res["a"]["flat"] > 0
                      and res["b"].get("bets", 0) and res["b"]["flat"] > 0)
        CANDS.append({"table": tab, "label": label, "kind": kind, "decidable": decidable, "mask": m,
                      "res": res, "flagged": flagged, "clears": clears,
                      "examined": tr.get("bets", 0) >= a.min_bets})
        return res

    def period_table(tab, title, rowspecs, kind, decidable, labels):
        rows = []
        for lab, m in rowspecs:
            res = cand(tab, " / ".join(lab), m, kind, decidable)
            rows.append(list(lab) + [gcell(res["train"]), gcell(res["a"]), gcell(res["b"])])
        P(title)
        table(labels + [PLAB["train"], PLAB["a"], PLAB["b"]], rows)

    def ew_table(tab, title, rowspecs, decidable, labels):
        rows = []
        for lab, m in rowspecs:
            rp = cand(tab, " / ".join(lab), m, "place", decidable)
            re_ = cand(tab, " / ".join(lab), m, "ew", decidable)
            rows.append(list(lab) + [gcell(rp["train"]), gcell(rp["test"]), gshort(re_["train"]), gcell(re_["test"])])
        P(title)
        table(labels + [f"place part {PLAB['train']}", f"place part {PLAB['test']}",
                        f"each-way {PLAB['train']} (short)", f"each-way {PLAB['test']}"], rows)

    CELL = ("Each cell: bets; units; return on units risked [95% CI, clustered by race]; f = flat-stake return. "
            "A short cell is bets: f flat return / u units return.")

    # ------------------------------------------------------------ 2. win bets
    P("## 2. Blind win bets at SP")
    P()
    P(CELL)
    P()
    period_table("2a SP band (desc.)", "Table 2a. Every runner in an SP band, win at SP. DESCRIPTIVE (banded by SP).",
                 [((REG[r], SP_LAB[bi]), (reg == r) & (sb == bi)) for r in (0, 1) for bi in range(len(SP_LAB))],
                 "win", False, ["region", "SP band"])
    rk = F["sprank"]
    rkb = np.select([rk == 1, rk == 2, rk == 3, rk == 4, rk <= 6], [0, 1, 2, 3, 4], 5)
    RKL = ["favourite (incl. joint)", "2nd in betting", "3rd", "4th", "5th-6th", "7th or longer"]
    period_table("2b SP rank (desc.)", "Table 2b. By position in the betting (SP rank; joint prices share the lower rank). "
                 "DESCRIPTIVE.", [((REG[r], RKL[i]), (reg == r) & (rkb == i)) for r in (0, 1) for i in range(6)],
                 "win", False, ["region", "SP rank"])

    rows = []
    for y in range(y0, y1 + 1):
        row = [str(y)]
        for r in (0, 1):
            m = (reg == r) & (yr == y)
            res = bets(m, "win")
            fv = bets(m & (rk == 1), "win")
            row += gcols(res)[:3] + [gcols(res)[3], f"{100 * fv['flat']:+.1f}" if fv.get("bets") else ""]
        rows.append(row)
    P("Table 2c. Every runner, by year (a RULE: bet everything). Last column per region: favourites' flat return "
      "(DESCRIPTIVE).")
    table(["year"] + [f"{R_} {h}" for R_ in REG for h in GHEAD + ["favs flat %"]], rows)

    period_table("2d code x handicap", "Table 2d. Every runner by code and handicap (a RULE).",
                 [((REG[r], CODES[c], "handicap" if h else "non-handicap"),
                   (reg == r) & (F["code"] == c) & (F["hcp"] == h))
                  for r in (0, 1) for c in range(4) for h in (False, True)],
                 "win", True, ["region", "code", "race"])
    fb = np.select([F["ran"] <= 4, F["ran"] <= 7, F["ran"] <= 11, F["ran"] <= 15], [0, 1, 2, 3], 4)
    FBL = ["2-4 runners", "5-7", "8-11", "12-15", "16+"]
    period_table("2e field x handicap", "Table 2e. Every runner by field size and handicap (a RULE).",
                 [((REG[r], FBL[f], "handicap" if h else "non-handicap"), (reg == r) & (fb == f) & (F["hcp"] == h))
                  for r in (0, 1) for f in range(5) for h in (False, True)],
                 "win", True, ["region", "field", "race"])

    orank = F["or_rank"]
    ar = F["all_rated"]
    orb = np.select([orank == 1, orank == 2, orank == 3, orank == 4, orank <= 6], [0, 1, 2, 3, 4], 5)
    ORL = ["top-rated (incl. tied)", "2nd-rated", "3rd", "4th", "5th-6th", "7th or lower"]
    period_table("2f OR rank", "Table 2f. By official-rating rank within the race, races where every runner is rated "
                 "(a RULE: the rating is known before the race).",
                 [((REG[r], "handicap" if h else "non-handicap", ORL[i]), (reg == r) & (F["hcp"] == h) & ar & (orb == i))
                  for r in (0, 1) for h in (False, True) for i in range(6)],
                 "win", True, ["region", "race", "OR rank"])
    gap = F["or_gap"]
    GAPE = [1, 6, 12, 20, np.inf]
    GAPL = ["clear by 1-5 lb", "6-11 lb", "12-19 lb", "20+ lb"]
    gb = np.digitize(gap, GAPE[1:-1])
    nonh_rated_unique = (~F["hcp"]) & ar & (gap >= 1)
    fb3 = np.select([F["ran"] <= 4, F["ran"] <= 7], [0, 1], 2)
    FB3 = ["2-4 runners", "5-7", "8+"]
    period_table("2g top-rated by margin", "Table 2g. The top-rated horse in non-handicaps where every runner is rated "
                 "and the top rating is unique, by its margin over the second-rated and by field (a RULE).",
                 [((REG[r], FB3[f], GAPL[g]), (reg == r) & nonh_rated_unique & (orank == 1) & (fb3 == f) & (gb == g))
                  for r in (0, 1) for f in range(3) for g in range(4)],
                 "win", True, ["region", "field", "top-rated margin"])

    # ------------------------------------------------------------ 3. each-way
    P("## 3. Each-way at SP")
    P()
    P("ASSUMED terms (standard UK/Irish; books often paid extra places, not modelled): 2-4 runners win only; "
      "5-7 runners 2 places at 1/4; 8+ runners 3 places at 1/5; handicaps of 12-15 runners 3 places at 1/4; "
      "handicaps of 16+ 4 places at 1/4. Place part graded at 1 + (SP-1) x fraction; a dead heat over the "
      "last paid place pays its share. Each-way = the win part at SP plus the place part, each sized by the "
      "stake rule (units), or 1 unit on each half (flat, the real bookmaker bet; flat return is per unit "
      "staked across both halves). Fields of 2-4 are left out (no place part). "
      "Rule 4 deductions and non-runners are not modelled (non-runners are not in the files).")
    P()
    P(CELL)
    P()
    eb = band(F["sp"], EW_EDGES)
    ew_table("3a SP band (desc.)", "Table 3a. Every runner in an SP band, fields of 5+. UPPER BOUND / DESCRIPTIVE.",
             [((REG[r], EW_LAB[bi]), (reg == r) & (eb == bi)) for r in (0, 1) for bi in range(len(EW_LAB))],
             False, ["region", "SP band"])
    shape = np.select([F["ran"] <= 4, F["ran"] <= 7,
                       (~F["hcp"]) & (F["ran"] <= 11), (~F["hcp"]) & (F["ran"] <= 15), ~F["hcp"],
                       F["ran"] <= 11, F["ran"] <= 15], [-1, 0, 1, 2, 3, 4, 5], 6)
    SHL = ["5-7 runners, 2 places at 1/4", "non-handicap 8-11, 3 at 1/5", "non-handicap 12-15, 3 at 1/5",
           "non-handicap 16+, 3 at 1/5", "handicap 8-11, 3 at 1/5", "handicap 12-15, 3 at 1/4",
           "handicap 16+, 4 at 1/4"]
    ew_table("3b race shape", "Table 3b. Every runner by race shape (a RULE: runners, handicap and places are "
             "known before the race).",
             [((REG[r], SHL[s]), (reg == r) & (shape == s)) for r in (0, 1) for s in range(7)],
             True, ["region", "shape"])
    ew_table("3b' exact field", "Table 3b'. Exact field sizes 5-8 by handicap (a RULE). 8 runners pay 3 places "
             "at 1/5, 5-7 pay 2 at 1/4.",
             [((REG[r], f"{n} runners", "handicap" if h else "non-handicap"), (reg == r) & (F["ran"] == n) & (F["hcp"] == h))
              for r in (0, 1) for n in (5, 6, 7, 8) for h in (False, True)],
             True, ["region", "field", "race"])

    # ---- the calibrated place model
    P("### The place model: Harville from SP, calibrated on the training years")
    P()
    trr = np.flatnonzero(clean[starts] & (ry <= TE) & (sizes >= 5))
    allr = np.flatnonzero(sizes >= 5)
    tr_rows = np.repeat(np.isin(np.arange(nr), trr), sizes)
    rows = []
    best = {}
    losses = {r: [] for r in (0, 1)}
    for lam in LAM_GRID:
        ph = harville_rows(pmod, np.full(len(pmod), lam), F, trr)
        for r in (0, 1):
            m = tr_rows & (reg == r)
            losses[r].append(ce(ph[m], psh[m]))
    for r in (0, 1):
        best[r] = float(LAM_GRID[int(np.argmin(losses[r]))])
    P(f"Table 3c. Place log loss on {y0}-{TE} (fields of 5+) by the Harville discount lambda "
      "(later places drawn from p^lambda; 1 = plain Harville). Win chance from the fitted win model.")
    table(["lambda"] + REG, [[f"{lam:.2f}"] + [f"{losses[r][i]:.5f}" for r in (0, 1)] for i, lam in enumerate(LAM_GRID)])
    P(f"Chosen lambda: GB {best[0]:.2f}, IRE {best[1]:.2f}.")
    P()
    lam_row = np.where(reg == 0, best[0], best[1])
    ph = harville_rows(pmod, lam_row, F, allr)
    pcal = np.full(len(ph), np.nan)
    rows_rc = []
    for r in (0, 1):
        for k in (2, 3, 4):
            m_all = (reg == r) & (F["places"] == k) & (F["ran"] >= 5)
            m_fit = m_all & tr_rows
            if m_fit.sum() < 1000:
                continue
            w = fit_logistic(recal_design(ph[m_fit]), psh[m_fit])
            pcal[m_all] = 1.0 / (1.0 + np.exp(-(recal_design(ph[m_all]) @ w)))
            rows_rc.append([REG[r], k, f"{w[0]:+.4f}", f"{w[1]:+.4f}", f"{w[2]:+.4f}", f"{int(m_fit.sum()):,}"])
    P(f"Recalibration logit(P) = a + b z + c z^2/10 with z = logit(P_harville), per region and places paid, "
      f"fitted on {y0}-{TE}:")
    table(["region", "places", "a", "b", "c", "train runners"], rows_rc)
    rows = []
    for r in (0, 1):
        for k in (2, 3, 4):
            for pk in ("train", "test"):
                m = clean & (reg == r) & (F["places"] == k) & (F["ran"] >= 5) & PER[pk] & np.isfinite(pcal)
                if not m.any():
                    continue
                rows.append([REG[r], k, PLAB[pk], f"{int(m.sum()):,}", f"{psh[m].mean():.4f}", f"{ph[m].mean():.4f}",
                             f"{pcal[m].mean():.4f}", f"{psh[m].sum() / ph[m].sum():.3f}",
                             f"{psh[m].sum() / pcal[m].sum():.3f}", f"{ce(ph[m], psh[m]):.5f}", f"{ce(pcal[m], psh[m]):.5f}"])
    P("Table 3d. Place model calibration, train (in-sample) and test.")
    table(["region", "places", "years", "runners", "place rate", "mean Harville", "mean calibrated",
           "A/E Harville", "A/E calibrated", "log loss Harville", "log loss calibrated"], rows)
    rows = []
    for r in (0, 1):
        m = clean & (reg == r) & (F["ran"] >= 5) & PER["test"] & np.isfinite(pcal)
        qs = np.quantile(pcal[m], np.linspace(0, 1, 11))
        dq = np.clip(np.digitize(pcal[m], qs[1:-1]), 0, 9)
        for i in range(10):
            s = dq == i
            rows.append([REG[r], i + 1, f"{qs[i]:.3f}-{qs[i + 1]:.3f}", f"{int(s.sum()):,}", f"{pcal[m][s].mean():.4f}",
                         f"{psh[m][s].mean():.4f}", f"{psh[m][s].sum() / pcal[m][s].sum():.3f}"])
    P(f"Table 3e. Calibrated place chance by decile, test years {PLAB['test']}.")
    table(["region", "decile", "range", "runners", "mean predicted", "place rate", "A/E"], rows)

    ev = pcal * pdec - 1.0
    F["ev"] = ev
    EVC = [0.0, 0.03, 0.05, 0.10, 0.15, 0.20]
    rows = []
    for r in (0, 1):
        for c in EVC:
            m = (reg == r) & np.isfinite(ev) & (ev > c)
            rp = cand("3f model EV (upper)", f"{REG[r]} / place EV > {c:.2f}", m, "place", False)
            re_ = cand("3f model EV (upper)", f"{REG[r]} / place EV > {c:.2f}", m, "ew", False)
            mt = m & clean & PER["test"] & ew_ok
            rows.append([REG[r], f"> {c:.2f}", f"{ev[mt].mean():+.3f}" if mt.any() else "",
                         gcell(rp["train"]), gcell(rp["a"]), gcell(rp["b"]), gcell(re_["test"])])
    P("Table 3f. Place part where the calibrated model's EV (P_place x place odds - 1) is above a cut. "
      f"UPPER BOUND: the EV is built from SP. {PLAB['train']} is in-sample for the model.")
    table(["region", "model EV", f"mean model EV {PLAB['test']}", f"place {PLAB['train']} (in-sample)",
           f"place {PLAB['a']}", f"place {PLAB['b']}", f"each-way {PLAB['test']}"], rows)
    rows = []
    for r in (0, 1):
        for s in range(7):
            m = (reg == r) & (shape == s) & np.isfinite(ev)
            row = [REG[r], SHL[s]]
            for c in (0.0, 0.10):
                rp = cand("3g model EV x shape (upper)", f"{REG[r]} / {SHL[s]} / EV > {c:.2f}", m & (ev > c), "place", False)
                row += [gcell(rp["test"])]
            mt = m & clean & PER["test"]
            row.append(f"{ev[mt].mean():+.3f}" if mt.any() else "")
            row.append(f"{psh[mt].sum() / pcal[mt].sum():.3f}" if mt.any() else "")
            rows.append(row)
    P(f"Table 3g. Place part by shape where model EV > 0 and > 0.10, test years {PLAB['test']}. UPPER BOUND. "
      "Last two columns: the shape's mean model EV over every runner, and place A/E of the calibrated model.")
    table(["region", "shape", "EV > 0.00", "EV > 0.10", "mean model EV", "A/E calibrated"], rows)

    # ---- the structural case: short favourite, small non-handicap field
    FAVE = [1.0, 1.5, 2.0, 3.0, np.inf]
    FAVL = ["fav under 1/2", "fav 1/2 to <Evs", "fav Evs to <2/1", "fav 2/1+"]
    fvb = np.digitize(F["fav_sp"], FAVE[1:-1])
    nh_small = (~F["hcp"]) & (F["ran"] >= 5) & (F["ran"] <= 11)
    fld2 = np.where(F["ran"] <= 7, 0, 1)
    FL2 = ["5-7 runners (2 at 1/4)", "8-11 runners (3 at 1/5)"]
    rkr = np.select([rk == 1, rk == 2, rk == 3], [0, 1, 2], 3)
    RRL = ["the favourite", "2nd in betting", "3rd in betting", "4th or longer"]
    ew_table("3h short fav (upper)", "Table 3h. Non-handicaps of 5-11 runners by the favourite's SP and the runner's "
             "place in the betting. UPPER BOUND (the favourite's price and the rank are the close).",
             [((REG[r], FL2[f], FAVL[g], RRL[i]), (reg == r) & nh_small & (fld2 == f) & (fvb == g) & (rkr == i))
              for r in (0, 1) for f in (0, 1) for g in range(4) for i in range(4)],
             False, ["region", "field", "favourite", "runner"])
    ORR3 = ["top-rated", "2nd-rated", "3rd-rated", "4th-rated or lower"]
    orr4 = np.select([orank == 1, orank == 2, orank == 3], [0, 1, 2], 3)
    ew_table("3i rating margin", "Table 3i. Non-handicaps of 5-11 runners, every runner rated and the top rating "
             "unique, by the top-rated horse's margin and the runner's rating rank. A RULE (the decidable stand-in "
             "for a short favourite).",
             [((REG[r], FL2[f], GAPL[g], ORR3[i]), (reg == r) & nh_small & ar & (gap >= 1) & (fld2 == f) & (gb == g)
               & (orr4 == i))
              for r in (0, 1) for f in (0, 1) for g in range(4) for i in range(4)],
             True, ["region", "field", "top-rated margin", "runner"])

    # ------------------------------------------------------------ 4. stability
    P("## 4. Stability: what looked positive on the training years")
    P()
    ex = [c for c in CANDS if c["examined"]]
    fl = [c for c in CANDS if c["flagged"]]
    cl = [c for c in fl if c["clears"]]
    P(f"Cells examined (at least {a.min_bets} bets on {PLAB['train']}): {len(ex):,} "
      f"({sum(c['decidable'] for c in ex):,} rules, {sum(not c['decidable'] for c in ex):,} upper-bound). "
      f"Positive on {PLAB['train']} (units or flat): {len(fl):,} "
      f"({sum(c['decidable'] for c in fl):,} rules). Clear on {PLAB['test']}: {len(cl):,} "
      f"({sum(c['decidable'] for c in cl):,} rules).")
    P()
    rows = []
    for c in sorted(fl, key=lambda c: (not c["decidable"], c["table"], c["label"])):
        sens = bets(c["mask"] & PER["test"], c["kind"], base=np.ones(len(clean), bool))
        rows.append([c["table"], c["label"], c["kind"], "rule" if c["decidable"] else "UPPER BOUND",
                     gcell(c["res"]["train"]), gshort(c["res"]["a"]), gshort(c["res"]["b"]), gcell(c["res"]["test"]),
                     f"f {100 * sens['flat']:+.1f}% / u {100 * sens['roi']:+.1f}%" if sens.get("bets") else "",
                     "yes" if c["clears"] else "no"])
    P(f"Table 4a. Every cell positive on {PLAB['train']}, graded on the later years. Sensitivity column: "
      f"{PLAB['test']} flat / units return including the hygiene-excluded races (gradeable_raw).")
    table(["table", "cell", "bet", "type", PLAB["train"], PLAB["a"], PLAB["b"], PLAB["test"],
           "incl. excluded races", "clears"], rows)

    pos = [c for c in fl if c["res"]["test"].get("bets") and (c["res"]["test"]["flat"] > 0 or c["res"]["test"]["roi"] > 0)]
    pos = sorted(pos, key=lambda c: -c["res"]["test"]["bets"])[:10]
    if pos:
        P(f"Table 4b. Year by year for the cells positive on {PLAB['train']} that stay positive on {PLAB['test']} "
          f"(units or flat), up to 10. Cell: bets; units; flat return.")
        for i, c in enumerate(pos):
            P(f"- C{i + 1}: {c['table']} / {c['label']} / {c['kind']} ({'rule' if c['decidable'] else 'UPPER BOUND'})")
        P()
        rows = []
        for y in range(TE + 1, y1 + 1):
            row = [str(y)]
            for c in pos:
                r_ = bets(c["mask"] & (yr == y), c["kind"])
                row.append(f"{r_['bets']:,}; {r_['units']:+.1f}u; {100 * r_['flat']:+.1f}%" if r_.get("bets") else "")
            rows.append(row)
        table(["year"] + [f"C{i + 1}" for i in range(len(pos))], rows)
    else:
        P(f"Table 4b. No cell positive on {PLAB['train']} stays positive on {PLAB['test']}.")
        P()

    rp_ = [c for c in CANDS if c["decidable"] and c["res"]["test"].get("bets", 0) >= a.min_bets
           and (c["res"]["test"]["flat"] > 0 or c["res"]["test"]["roi"] > 0)]
    P(f"Table 4c. Every RULE cell (decidable) with a positive return on {PLAB['test']} by units or flat, whatever "
      f"it did on {PLAB['train']}: {len(rp_):,} of {sum(c['decidable'] and c['res']['test'].get('bets', 0) >= a.min_bets for c in CANDS):,} "
      f"rule cells with {a.min_bets}+ test bets. Chosen by looking at the test years. The flat return is the "
      "executable figure; the units return sizes each bet off the SP itself, so it is SP-weighted (an upper "
      "bound). 'years flat > 0' counts test years from the unrounded flat return.")
    P()
    if rp_:
        def _pos_years(c):
            n = k = 0
            for y in range(TE + 1, y1 + 1):
                r_ = bets(c["mask"] & (yr == y), c["kind"])
                if r_.get("bets"):
                    n += 1
                    k += r_["flat"] > 0
            return f"{k} of {n}"

        def _raw(c):
            r_ = bets(c["mask"] & PER["test"], c["kind"], base=np.ones(len(clean), bool))
            return f"f {100 * r_['flat']:+.1f}% / u {100 * r_['roi']:+.1f}%" if r_.get("bets") else ""

        table(["table", "cell", "bet", PLAB["train"], PLAB["a"], PLAB["b"],
               PLAB["test"] + " (units are SP-weighted)", "incl. excluded races", "years flat > 0"],
              [[c["table"], c["label"], c["kind"], gcell(c["res"]["train"]), gshort(c["res"]["a"]),
                gshort(c["res"]["b"]), gcell(c["res"]["test"]), _raw(c), _pos_years(c)]
               for c in sorted(rp_, key=lambda c: -c["res"]["test"]["bets"])])
        top = sorted(rp_, key=lambda c: -c["res"]["test"]["bets"])[:6]
        for i, c in enumerate(top):
            P(f"- R{i + 1}: {c['table']} / {c['label']} / {c['kind']}")
        P()
        rows = []
        for y in range(TE + 1, y1 + 1):
            row = [str(y)]
            for c in top:
                r_ = bets(c["mask"] & (yr == y), c["kind"])
                row.append(f"{r_['bets']:,}; {r_['units']:+.1f}u; {100 * r_['flat']:+.1f}%" if r_.get("bets") else "")
            rows.append(row)
        P("Year by year for those rules (up to 6, most bets first). Cell: bets; units; flat return.")
        table(["year"] + [f"R{i + 1}" for i in range(len(top))], rows)

    ins = [c for c in CANDS if not c["flagged"] and c["res"]["test"].get("bets", 0) >= a.min_bets
           and c["res"]["test"]["flo"] > 0]
    P(f"Selected in sample: {len(ins):,} cells NOT positive on {PLAB['train']} have a flat-return lower bound above 0 "
      f"on {PLAB['test']} ({sum(c['decidable'] for c in ins):,} rules). Listed with both halves; chosen by looking at "
      "the test years, so they are not evidence.")
    P()
    rows = [[c["table"], c["label"], c["kind"], "rule" if c["decidable"] else "UPPER BOUND",
             gcell(c["res"]["train"]), gshort(c["res"]["a"]), gshort(c["res"]["b"])]
            for c in sorted(ins, key=lambda c: -c["res"]["test"]["flat"])[:15]]
    if rows:
        table(["table", "cell", "bet", "type", PLAB["train"], PLAB["a"], PLAB["b"]], rows)
    P(f"Total run {time.time() - T0:.0f} s.")
    if a.md:
        a.md.write_text("\n".join(OUT) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

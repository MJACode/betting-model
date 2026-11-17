"""Australia/NZ thoroughbreds on the Betfair exchange: data checks, baselines, structure rules.

Reads the Betfair Australia monthly CSVs that `scripts/horse/fetch_datasets.py`
downloads and `scripts/horse/store_files.py` stores in Supabase
(`nfl_research_data_backup`, source `horse_racing|betfair_anz_thoroughbreds`).
The files on disk are a cache of those rows; `store_files --verify` proves it.

WHAT IS DECIDABLE IN THESE FILES (docs/horse_racing_market_audit.md §2):
  * BEST_AVAIL_BACK_AT_SCHEDULED_OFF / ..._LAY_... and the two market
    percentages are one snapshot, at the scheduled start. That is the only
    moment a rule may decide at.
  * WIN_PREPLAY_* and PLACE_*_PRICE_TAKEN and every volume run to the actual
    off, after that snapshot. They are hindsight: never an input.
  * WIN_BSP / PLACE_BSP are the closes. A bet "at BSP" is executable, so a rule
    may be GRADED at BSP; no rule may condition on a BSP value.

Units are the repo's published stake: 1 unit to win, risk 1/(d-1) capped at 3,
net of exchange commission on a winning bet. Return is units over units
risked, with a 95% interval clustered by race.

    python scripts/horse/anz_study.py [--commission 0.08] [--json OUT]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
DATA = ROOT_DIR / "data" / "horse"

NUM = ["WIN_BSP", "PLACE_BSP", "BEST_AVAIL_BACK_AT_SCHEDULED_OFF",
       "BEST_AVAIL_LAY_AT_SCHEDULED_OFF", "BACK_MARKET_PERCENTAGE_AT_SCHEDULED_OFF",
       "LAY_MARKET_PERCENTAGE_AT_SCHEDULED_OFF", "WIN_BSP_VOLUME", "WIN_PREPLAY_VOLUME",
       "DISTANCE"]
BANDS = [1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 51.0, 1001.0]


def month_files(paths: list[str]) -> list[str]:
    """One file per month. The daily store (scripts/horse/betfair_monthly.py) keeps a
    republished month beside the original as `<stem>.v<UTC stamp>-<sha 8>.csv`;
    the newest stamp wins, else the original. Two files for one month at the same
    stamp (two unversioned copies) stop the load rather than count the month twice."""
    from scripts.horse.betfair_monthly import MONTH_FILE
    best: dict[tuple[int, int], tuple[str, str]] = {}
    for p in paths:
        m = MONTH_FILE.match(Path(p).name)
        if not m:
            raise SystemExit(f"{p}: not a Betfair month file name")
        key, stamp = (int(m.group(1)), int(m.group(2))), m.group(3) or ""
        if key in best and best[key][0] == stamp:
            raise SystemExit(f"two copies of {key[0]}-{key[1]:02d}: {best[key][1]} and {p}")
        if key not in best or stamp > best[key][0]:
            best[key] = (stamp, p)
    return [best[k][1] for k in sorted(best)]


def load(root: Path = DATA) -> pd.DataFrame:
    files = month_files(sorted(glob.glob(str(root / "betfair-*" / "*.csv"))))
    if not files:
        raise SystemExit(f"no Betfair CSVs under {root}")
    parts = []
    for f in files:
        d = pd.read_csv(f, dtype=str)
        d["file"] = Path(f).name
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    for c in NUM:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # ANZ_Thoroughbreds_2025_04.csv alone writes its dates day-first
    # (1/04/2025); every other file is ISO. Each file must land in its own month.
    iso = pd.to_datetime(df["LOCAL_MEETING_DATE"], format="%Y-%m-%d", errors="coerce")
    dmy = pd.to_datetime(df["LOCAL_MEETING_DATE"], format="%d/%m/%Y", errors="coerce")
    df["date"] = iso.fillna(dmy)
    if df["date"].isna().any():
        raise SystemExit(f"{int(df['date'].isna().sum())} rows with an unreadable date")
    named = df["file"].str.extract(r"_(\d{4})_(\d{2})(?:\.v[0-9TZ]+-[0-9a-f]{8})?\.csv$").astype(int)
    off = (df["date"].dt.year != named[0]) | (df["date"].dt.month != named[1])
    if off.any():
        raise SystemExit(f"{int(off.sum())} rows dated outside their file's month")
    df["year"] = df["date"].dt.year
    df["won"] = (df["WIN_RESULT"] == "WINNER").astype(int)
    df["placed"] = (df["PLACE_RESULT"] == "WINNER").astype(int)
    df["mkt"] = df["WIN_MARKET_ID"]
    g = df.groupby("mkt")
    df["field"] = g["SELECTION_ID"].transform("size")
    df["n_win"] = g["won"].transform("sum")
    df["n_place_win"] = g["placed"].transform("sum")
    df["region"] = np.where(df["STATE_CODE"] == "NZ", "NZ", "AU")
    return df


# ---------------------------------------------------------------- grading

def stake_units(d: np.ndarray, won_share: np.ndarray, comm: float) -> tuple[np.ndarray, np.ndarray]:
    """(profit, risk) per bet at decimal d. won_share is 1 for a win, 1/n for an
    n-way dead heat, 0 for a loss. Commission is charged on a net win only."""
    d = np.asarray(d, float)
    risk = np.minimum(1.0 / (d - 1.0), 3.0)
    gross = risk * won_share * (d - 1.0) - risk * (1.0 - won_share)
    profit = np.where(gross > 0, gross * (1.0 - comm), gross)
    return profit, risk


def commission_schedule(df: pd.DataFrame) -> np.ndarray:
    """Betfair Australia's market base rate on a net win, by state and date.

    NSW and ACT 10%. Every other Australian state 7% until 2025-03-24 and 8%
    from 2025-03-25. New Zealand racing is charged as non-Australian racing,
    5% then 6% from the same date. Source: The Straight, 2025-03-04, on the
    March 2025 change (docs/horse_racing_market_audit.md, "Commission").
    The New Zealand line is the article's non-Australian rate; Betfair's own
    commission page returned 404 on 2026-11-15.
    """
    after = (df["date"] >= "2025-03-25").to_numpy()
    st = df["STATE_CODE"].to_numpy()
    return np.where(np.isin(st, ["NSW", "ACT"]), 0.10,
                    np.where(st == "NZ", np.where(after, 0.06, 0.05),
                             np.where(after, 0.08, 0.07)))


def summarise(frame: pd.DataFrame, price: str, won_col: str, comm) -> dict:
    """Units, risk, return and a race-clustered 95% interval for one bet set.
    comm is a rate, or None to use each row's scheduled rate (column comm)."""
    f = frame[frame[price].notna() & (frame[price] > 1.0) & np.isfinite(frame[price])
              & (frame[price] <= 1000.0)]
    if f.empty:
        return {"bets": 0}
    if comm is None:
        comm = f["comm"].to_numpy()
    share = f[won_col].to_numpy(float)
    if won_col == "won":
        share = share / np.maximum(f["n_win"].to_numpy(float), 1.0)
    profit, risk = stake_units(f[price].to_numpy(), share, comm)
    by = pd.DataFrame({"m": f["mkt"].to_numpy(), "p": profit, "r": risk}).groupby("m").sum()
    roi = by.p.sum() / by.r.sum()
    se = math.sqrt(((by.p - roi * by.r) ** 2).sum()) / by.r.sum()
    flat = np.where(share > 0, share * (f[price].to_numpy() - 1) * (1 - comm) - (1 - share), -1.0)
    return {"bets": int(len(f)), "wins": int((share > 0).sum()), "units": float(profit.sum()),
            "risk": float(risk.sum()), "roi": float(roi), "lo": float(roi - 1.96 * se),
            "hi": float(roi + 1.96 * se), "flat_roi": float(flat.mean())}


def fmt(r: dict) -> str:
    if not r.get("bets"):
        return "0 bets"
    return (f"{r['bets']:>8,} bets {r['units']:>+10.1f}u  risk {r['risk']:>9.1f}  "
            f"return {100 * r['roi']:+6.2f}% [{100 * r['lo']:+6.2f}, {100 * r['hi']:+6.2f}]  "
            f"flat {100 * r['flat_roi']:+6.2f}%")


# ---------------------------------------------------------------- probabilities

def devig(q: np.ndarray, method: str = "power") -> np.ndarray:
    """Implied chances to probabilities summing to 1, by proportion or by power."""
    q = np.asarray(q, float)
    if method == "prop":
        return q / q.sum()
    lo, hi = 0.2, 5.0
    for _ in range(60):
        k = 0.5 * (lo + hi)
        s = (q ** k).sum()
        if s > 1.0:
            lo = k
        else:
            hi = k
    p = q ** (0.5 * (lo + hi))
    return p / p.sum()


def harville_top(p: np.ndarray, k: int, lam: float = 1.0) -> np.ndarray:
    """P(runner finishes in the first k), Harville, with later positions drawn
    from p**lam renormalised (lam=1 is Harville; lam<1 is the Lo and
    Bacon-Shone discount that flattens later places)."""
    p = np.asarray(p, float)
    n = len(p)
    out = p.copy()
    if k == 1 or n <= 1:
        return out
    q = p ** lam
    q = q / q.sum()
    # second place: sum_j p_j * q_i / (1 - q_j)
    denom1 = 1.0 - q
    A = np.outer(p, q) / denom1[:, None]          # A[j, i] = p_j q_i / (1 - q_j)
    np.fill_diagonal(A, 0.0)
    out = out + A.sum(axis=0)
    if k == 2 or n <= 2:
        return np.minimum(out, 1.0)
    # third place: sum_{j != l} p_j q_l/(1-q_j) * q_i/(1-q_j-q_l)
    B = np.outer(p, q) / denom1[:, None]          # B[j, l]
    np.fill_diagonal(B, 0.0)
    D = 1.0 - q[:, None] - q[None, :]
    np.fill_diagonal(D, 1.0)
    M = B / D                                     # M[j, l] = B[j,l] / (1 - q_j - q_l)
    np.fill_diagonal(M, 0.0)
    total = M.sum()
    third = q * (total - M.sum(axis=1) - M.sum(axis=0))
    return np.minimum(out + third, 1.0)


def race_probs(df: pd.DataFrame, price: str, method: str) -> pd.Series:
    """Per-race de-vigged probability from one price column (NaN if any runner
    in the race lacks that price)."""
    out = pd.Series(np.nan, index=df.index)
    for _, idx in df.groupby("mkt").indices.items():
        d = df[price].to_numpy()[idx]
        if np.isnan(d).any() or (d <= 1.0).any():
            continue
        out.iloc[idx] = devig(1.0 / d, method)
    return out


# ---------------------------------------------------------------- report

def data_checks(df: pd.DataFrame) -> dict:
    res = {}
    for y, g in df.groupby("year"):
        m = g.groupby("mkt").agg(field=("field", "first"), n_win=("n_win", "first"),
                                 n_pw=("n_place_win", "first"),
                                 bsp_sum=("WIN_BSP", lambda s: (1 / s).sum()),
                                 back_sum=("BEST_AVAIL_BACK_AT_SCHEDULED_OFF", lambda s: (1 / s).sum()),
                                 has_place=("PLACE_MARKET_ID", lambda s: s.notna().all()))
        res[int(y)] = {
            "runners": int(len(g)), "races": int(len(m)),
            "nz_share": float((g.region == "NZ").mean()),
            "bsp_missing": float(g.WIN_BSP.isna().mean()),
            "back_missing": float(g.BEST_AVAIL_BACK_AT_SCHEDULED_OFF.isna().mean()),
            "place_bsp_missing": float(g.PLACE_BSP.isna().mean()),
            "races_0_winners": int((m.n_win == 0).sum()), "races_dead_heat": int((m.n_win > 1).sum()),
            "bsp_book_median": float(m.bsp_sum.median()),
            "back_book_median": float(m.back_sum.median()),
            "place_winners": {int(k): int(v) for k, v in m.n_pw.value_counts().sort_index().items()},
        }
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commission", default="0",
                    help="a rate on a net win (0.08), or 'state' for Betfair Australia's schedule")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--root", type=Path, default=DATA)
    a = ap.parse_args(argv)
    df = load(a.root)
    if a.commission == "state":
        df["comm"] = commission_schedule(df)
        c = None
    else:
        c = float(a.commission)
    out: dict = {"commission": a.commission}

    print("== data checks by year")
    chk = data_checks(df)
    out["checks"] = chk
    for y, r in chk.items():
        print(y, json.dumps(r))

    # One-winner races with every runner priced at both moments: the graded universe.
    ok = df[(df.n_win >= 1)].copy()
    back, lay = ok.BEST_AVAIL_BACK_AT_SCHEDULED_OFF, ok.BEST_AVAIL_LAY_AT_SCHEDULED_OFF
    bad = (ok.WIN_BSP.isna() | ~(ok.WIN_BSP > 1) | ~np.isfinite(ok.WIN_BSP) | (ok.WIN_BSP > 1000)
           | back.isna() | ~(back > 1))
    # A broken snapshot at the scheduled off (13.1% of races): a back book
    # outside 0.98-1.06, a lay book outside 0.90-1.02, a missing lay, or a lay
    # under the back. Visible at the moment of decision, so a live rule skips
    # the same races ("Is the data right?", docs/horse_racing_market_audit.md).
    broken = (~ok.BACK_MARKET_PERCENTAGE_AT_SCHEDULED_OFF.between(0.98, 1.06)
              | ~ok.LAY_MARKET_PERCENTAGE_AT_SCHEDULED_OFF.between(0.90, 1.02)
              | lay.isna() | (lay < back))
    priced = ~bad.groupby(ok.mkt).transform("any")
    sane = ~broken.groupby(ok.mkt).transform("any")
    out["universe_filter"] = {"races_with_winner": int(ok.mkt.nunique()),
                              "every_runner_priced": int(ok[priced].mkt.nunique()),
                              "and_snapshot_sane": int(ok[priced & sane].mkt.nunique())}
    full = ok[priced & sane].copy()
    print(f"\nraces with a winner: {ok.mkt.nunique():,}; every runner priced at BSP and at the "
          f"scheduled-off back: {ok[priced].mkt.nunique():,}; and a sane scheduled-off book: "
          f"{full.mkt.nunique():,} ({len(full):,} runners)")
    out["universe"] = {"races": int(full.mkt.nunique()), "runners": int(len(full))}

    full["p_bsp"] = race_probs(full, "WIN_BSP", "power")
    full["p_back_prop"] = race_probs(full, "BEST_AVAIL_BACK_AT_SCHEDULED_OFF", "prop")
    full["p_back"] = race_probs(full, "BEST_AVAIL_BACK_AT_SCHEDULED_OFF", "power")
    full["p_bsp_prop"] = race_probs(full, "WIN_BSP", "prop")

    print("\n== market accuracy: log loss of the winner's probability, per race (lower is better)")
    win = full[full.won == 1]
    win1 = win[win.n_win == 1]
    acc = {}
    for col in ["p_back_prop", "p_back", "p_bsp_prop", "p_bsp"]:
        ll = float(-np.log(win1[col].clip(1e-9)).mean())
        acc[col] = ll
        print(f"  {col:12s} {ll:.4f}")
    out["logloss"] = acc

    print("\n== calibration: realised win rate against the de-vigged chance, by band")
    cal = []
    for col in ["p_back", "p_bsp", "p_bsp_prop"]:
        b = pd.cut(full[col], [0, .02, .05, .1, .2, .3, .4, .5, .6, .8, 1.0])
        t = full.groupby(b, observed=True).agg(n=("won", "size"), said=(col, "mean"), won=("won", "mean"))
        for k, r in t.iterrows():
            cal.append({"price": col, "band": str(k), "n": int(r.n), "said": float(r.said), "won": float(r.won)})
            print(f"  {col:10s} {str(k):14s} n={int(r.n):>8,}  said {r.said:.4f}  won {r.won:.4f}  "
                  f"gap {100 * (r.won - r.said):+.2f}pt")
    out["calibration"] = cal

    print(f"\n== blind win bets by scheduled-off back price band (commission {a.commission})")
    print("   decided on the scheduled-off back; graded at that back price, and at BSP")
    full["band"] = pd.cut(full.BEST_AVAIL_BACK_AT_SCHEDULED_OFF, BANDS)
    blind = []
    for k, g in full.groupby("band", observed=True):
        r_back = summarise(g, "BEST_AVAIL_BACK_AT_SCHEDULED_OFF", "won", c)
        r_bsp = summarise(g, "WIN_BSP", "won", c)
        blind.append({"band": str(k), "at_back": r_back, "at_bsp": r_bsp})
        print(f"  {str(k):14s} back {fmt(r_back)}")
        print(f"  {'':14s} BSP  {fmt(r_bsp)}")
    out["blind_by_band"] = blind

    print("\n== favourites (shortest scheduled-off back in the race), by year, at BSP and at the back")
    full["rank"] = full.groupby("mkt").BEST_AVAIL_BACK_AT_SCHEDULED_OFF.rank(method="first")
    fav = full[full["rank"] == 1]
    favs = {}
    for y, g in fav.groupby("year"):
        favs[int(y)] = {"bsp": summarise(g, "WIN_BSP", "won", c),
                        "back": summarise(g, "BEST_AVAIL_BACK_AT_SCHEDULED_OFF", "won", c)}
        print(f"  {y} BSP  {fmt(favs[int(y)]['bsp'])}")
        print(f"  {'':4} back {fmt(favs[int(y)]['back'])}")
    out["favourites_by_year"] = favs

    print("\n== BSP against the scheduled-off back, same runner (BSP/back - 1), by band")
    full["bsp_vs_back"] = full.WIN_BSP / full.BEST_AVAIL_BACK_AT_SCHEDULED_OFF - 1
    t = full.groupby("band", observed=True).bsp_vs_back.agg(["median", "mean", "size"])
    out["bsp_vs_back"] = {str(k): {"median": float(r["median"]), "mean": float(r["mean"]), "n": int(r["size"])}
                          for k, r in t.iterrows()}
    for k, r in t.iterrows():
        print(f"  {str(k):14s} median {100 * r['median']:+6.2f}%  mean {100 * r['mean']:+6.2f}%  n={int(r['size']):,}")

    # ------------------------------------------------ win against place
    print("\n== place market against the win market (Harville from the scheduled-off win back)")
    pbad = full.PLACE_BSP.isna() | ~(full.PLACE_BSP > 1)
    pl = full[~pbad.groupby(full.mkt).transform("any") & full.n_place_win.between(2, 3)].copy()
    hv = pd.Series(np.nan, index=pl.index)
    hv_l = pd.Series(np.nan, index=pl.index)
    for _, idx in pl.groupby("mkt").indices.items():
        p = pl["p_back"].to_numpy()[idx]
        k = int(pl["n_place_win"].to_numpy()[idx][0])
        hv.iloc[idx] = harville_top(p, k)
        hv_l.iloc[idx] = harville_top(p, k, lam=0.76)
    pl["p_place_h"] = hv
    pl["p_place_l"] = hv_l
    pl["p_place_bsp"] = 1.0 / pl.PLACE_BSP
    out["place_universe"] = {"races": int(pl.mkt.nunique()), "runners": int(len(pl))}
    print(f"  races with 2 or 3 place winners and every runner place-priced: {pl.mkt.nunique():,}")
    pres = []
    for col in ["p_place_h", "p_place_l"]:
        b = pd.cut(pl[col], [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0])
        for k, g in pl.groupby(b, observed=True):
            r = summarise(g, "PLACE_BSP", "placed", c)
            pres.append({"model": col, "band": str(k), "said": float(g[col].mean()),
                         "placed": float(g.placed.mean()), "place_bsp_implied": float(g.p_place_bsp.mean()),
                         "at_place_bsp": r})
            print(f"  {col} {str(k):12s} said {g[col].mean():.3f} placed {g.placed.mean():.3f} "
                  f"1/placeBSP {g.p_place_bsp.mean():.3f}  {fmt(r)}")
    out["place_by_band"] = pres

    # Decidable place rule: calibrate Harville (from the scheduled-off win
    # backs) on 2020-2022, predict the place BSP from the same inputs on the
    # same years, and bet the place at BSP on 2023-2026 when the predicted EV
    # clears a cut. Nothing here reads a BSP of the race being bet.
    from sklearn.linear_model import LinearRegression, LogisticRegression
    eps = 1e-4
    pl["lh"] = np.log(pl.p_place_h.clip(eps, 1 - eps) / (1 - pl.p_place_h.clip(eps, 1 - eps)))
    pl["lf"] = np.log(pl.field)
    pl["k3"] = (pl.n_place_win == 3).astype(float)
    pl["lwin"] = np.log(pl.BEST_AVAIL_BACK_AT_SCHEDULED_OFF)
    X = ["lh", "lf", "k3"]
    fit, test = pl[pl.year <= 2022], pl[pl.year >= 2023].copy()
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(fit[X], fit.placed)
    lin = LinearRegression().fit(fit[X + ["lwin"]], np.log(fit.PLACE_BSP - 1))
    test["p_cal"] = lr.predict_proba(test[X])[:, 1]
    test["placebsp_hat"] = 1 + np.exp(lin.predict(test[X + ["lwin"]]))
    cm = test["comm"].to_numpy() if c is None else c
    test["ev_hat"] = test.p_cal * (1 + (test.placebsp_hat - 1) * (1 - cm)) - 1
    print("\n== decidable place rule: calibrated Harville x predicted place BSP, fit 2020-22, graded 2023-26")
    rows = []
    for cut in [-0.05, 0.0, 0.02, 0.05, 0.10]:
        g = test[test.ev_hat > cut]
        rr = summarise(g, "PLACE_BSP", "placed", c)
        yrs = {int(y): summarise(gg, "PLACE_BSP", "placed", c) for y, gg in g.groupby("year")}
        rows.append({"ev_cut": cut, **rr, "by_year": yrs})
        print(f"  EV_hat > {cut:+.2f}  {fmt(rr)}")
        for y, v in yrs.items():
            print(f"      {y}  {fmt(v)}")
    calt = test.groupby(pd.cut(test.p_cal, [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1]), observed=True).agg(
        n=("placed", "size"), said=("p_cal", "mean"), placed=("placed", "mean"))
    out["place_rule"] = {"rows": rows, "calibration_2023_26": [
        {"band": str(k), "n": int(v.n), "said": float(v.said), "placed": float(v.placed)} for k, v in calt.iterrows()]}
    for k, v in calt.iterrows():
        print(f"  calibrated {str(k):12s} n={int(v.n):>7,} said {v.said:.3f} placed {v.placed:.3f}")

    # Track tier: a track's mean matched volume per race in the PREVIOUS
    # calendar year (decidable), quartiles; favourites at BSP, net.
    print("\n== favourites at BSP by track tier (prior-year matched volume per race), net")
    rv = full.groupby(["mkt", "TRACK", "year"]).WIN_PREPLAY_VOLUME.sum().reset_index()
    tv = rv.groupby(["TRACK", "year"]).WIN_PREPLAY_VOLUME.mean().rename("vol").reset_index()
    tv["year"] = tv["year"] + 1
    fav2 = fav.merge(tv, on=["TRACK", "year"], how="inner")
    fav2["tier"] = pd.qcut(fav2.vol, 4, labels=["q1_smallest", "q2", "q3", "q4_largest"])
    tiers = {}
    for t, g in fav2.groupby("tier", observed=True):
        tiers[str(t)] = {"all": summarise(g, "WIN_BSP", "won", c),
                         "by_year": {int(y): summarise(gg, "WIN_BSP", "won", c) for y, gg in g.groupby("year")}}
        print(f"  {t:12s} {fmt(tiers[str(t)]['all'])}")
    out["favourites_by_tier"] = tiers

    # A back book under 100% at the scheduled off: backing every runner in
    # proportion locks a profit, if the best backs can be filled (no size in
    # the file). Count only.
    bm = full.groupby("mkt").BACK_MARKET_PERCENTAGE_AT_SCHEDULED_OFF.first()
    out["back_book_under_100"] = {"races": int((bm < 1.0).sum()), "of": int(len(bm)),
                                  "median_when_under": float(bm[bm < 1.0].median()) if (bm < 1.0).any() else None}
    print(f"\n== back book under 100% at the scheduled off: {out['back_book_under_100']}")

    # Place by field size: the place terms step at field-size boundaries
    # (2 places for small fields, 3 for 8+), so a boundary field is where a
    # generous or a mean place market would show. Every runner, at place BSP.
    print("\n== place bets at place BSP by field size (every runner; and calibrated place chance > 0.5)")
    fs = {}
    for n, g in pl.groupby(pl.field.clip(upper=16)):
        top = test[(test.field.clip(upper=16) == n) & (test.p_cal > 0.5)]
        fs[int(n)] = {"all": summarise(g, "PLACE_BSP", "placed", c),
                      "cal_over_half_2023_26": summarise(top, "PLACE_BSP", "placed", c)}
        print(f"  {int(n):>2} runners all {fmt(fs[int(n)]['all'])}")
        print(f"  {'':10} p>0.5 {fmt(fs[int(n)]['cal_over_half_2023_26'])}")
    out["place_by_field"] = fs

    # A conditional logit on the prices visible at the scheduled start only
    # (after Sung and Johnson 2010, who fit one on market prices): the de-vigged
    # back, the back-lay spread, the book and the field. Fit 2020-2023, graded
    # 2024-2026. The bet is a win at BSP; its EV uses a BSP predicted from the
    # same snapshot (fit on 2020-2023), never the BSP itself.
    from scripts.horse.clogit import fit_clogit, softmax_by_race, starts_of
    print("\n== conditional logit on the scheduled-start prices, fit 2020-23, graded 2024-26, bet at BSP")
    m = full.sort_values(["mkt", "SELECTION_ID"]).copy()
    m["lp"] = np.log(m.p_back)
    m["spread"] = np.log(m.BEST_AVAIL_LAY_AT_SCHEDULED_OFF / m.BEST_AVAIL_BACK_AT_SCHEDULED_OFF)
    m["lp_x_spread"] = m.lp * m.spread
    m["lp_x_field"] = m.lp * np.log(m.field)
    m["lp_x_book"] = m.lp * (m.BACK_MARKET_PERCENTAGE_AT_SCHEDULED_OFF - 1.0)
    feats = ["lp", "spread", "lp_x_spread", "lp_x_field", "lp_x_book"]
    # one-winner races only: a dead heat has two winners and the softmax one
    m = m[m.n_win == 1]
    tr, te = m[m.year <= 2023], m[m.year >= 2024].copy()
    beta = fit_clogit(tr[feats].to_numpy(), tr.won.to_numpy(), starts_of(tr, "mkt"), l2=1e-3)
    te["p_cl"] = softmax_by_race(te[feats].to_numpy() @ beta, starts_of(te, "mkt"))
    te1 = te[te.n_win == 1]
    ll = {k: float(-np.log(te1[te1.won == 1][k].clip(1e-9)).mean()) for k in ["p_back", "p_cl", "p_bsp"]}
    reg = LinearRegression().fit(tr[["lp", "spread", "lp_x_field"]], np.log(tr.WIN_BSP - 1))
    te["bsp_hat"] = 1 + np.exp(reg.predict(te[["lp", "spread", "lp_x_field"]]))
    cm2 = te["comm"].to_numpy() if c is None else c
    te["ev"] = te.p_cl * (1 + (te.bsp_hat - 1) * (1 - cm2)) - 1
    best = te.loc[te.groupby("mkt").ev.idxmax()]
    cl = {"coef": dict(zip(feats, map(float, beta))), "logloss_2024_26": ll, "rows": []}
    print(f"  coefficients {cl['coef']}")
    print(f"  log loss 2024-26: back {ll['p_back']:.4f}  model {ll['p_cl']:.4f}  BSP {ll['p_bsp']:.4f}")
    for cut in [0.0, 0.02, 0.05, 0.10]:
        g = best[best.ev > cut]
        rr = summarise(g, "WIN_BSP", "won", c)
        cl["rows"].append({"ev_cut": cut, **rr,
                           "by_year": {int(y): summarise(gg, "WIN_BSP", "won", c) for y, gg in g.groupby("year")}})
        print(f"  EV > {cut:.2f}  {fmt(rr)}")
    out["clogit_scheduled_prices"] = cl

    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Hong Kong, 2016-09-28 to 2018-06-27: Benter's two-stage model against the
PRE-RACE win pool, graded at the final win dividend.

Stage 1 is a Bolton-Chapman conditional logit (one softmax per race) on runner
facts known before the race, built only from EARLIER rows of performances
(Hong Kong, 1979 to 2018). Stage 2 is Benter's blend,
softmax(b * log p_model + c * log p_pool), where p_pool is the win pool at a
fixed lead before the scheduled start (the live-odds snapshots), de-vigged in
proportion.

Walk-forward. Stage 1 is fit once, on the ten seasons 2006/07 to 2015/16
(the last ten before S-1 for the graded season S = 2017/18). That one fit is
out of sample for both seasons with pool snapshots.
  * fold A: stage 2 fit on 2016/17, graded on 2017/18 (the forward fold).
  * fold B: stage 2 fit on 2017/18, graded on 2016/17. This is a cross-fold:
    its stage 2 is fit on the LATER season.

What a rule may decide on. A bet is decided at the snapshot `snapshot_at(L)`
returns (a capture L to L+6 minutes before the scheduled start), on that
snapshot's displayed odds and on facts from earlier races. It is sized at the
displayed decision price (1 unit to win, risk 1/(d-1) capped at 3) and paid at
the final dividend / 10 (`hk_preoff_data.pool_bet_units`). A runner priced at
the decision and scratched later is a refund (0 units out of 0 risked).

Things the features must NOT see, and how they are kept out:
  * the race's own result, finish time, lengths, sectionals and final odds: the
    history state of a horse is attached with merge_asof on STRICTLY earlier
    dates (allow_exact_matches=False), and only rating, weights, draw,
    distance, venue, track, jockey and trainer are taken from the current row;
  * same-day results for jockey and trainer rates (keyed by name: the ids are
    null for anyone without a current HKJC profile): rides are aggregated per
    (person, day) and only strictly earlier days count, so a trainer's second
    runner in a race (or later the same day) never sees the first one's result;
  * age: horses.csv gives an age only for horses still active when it was
    scraped (2016-09-27 to 2018-07-01). Every retired horse has none, so in the
    training seasons a known age would mean "kept racing past 2016": a survivor
    leak. Seasons since the first Hong Kong start stand in for it;
  * pool runners missing from performances (dnf, no_sections, scratched later)
    have no current-row rating, weight, draw or jockey. They are kept in the
    choice set and get the race mean, with NO missing flag (that flag would
    encode "did not finish").

A missing value is the race mean (after within-race standardisation, 0) plus a
flag where the flag is a pre-race fact (debut, unrated, no speed figure).

    python -I scripts/horse/hk_preoff_benter.py [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
from scripts.horse import hk_preoff_data as H  # noqa: E402
from scripts.horse.clogit import fit_clogit, softmax_by_race, starts_of  # noqa: E402

LEADS = [10, 5, 2]
STAGE1_SEASONS = list(range(2006, 2016))      # 2006/07 .. 2015/16
FOLDS = {"A": (2016, 2017), "B": (2017, 2016)}  # (stage-2 fit season, graded season)
EV_CUTS = [0.0, 0.05, 0.10, 0.20, 0.30]
LONGSHOT_P = 0.04
SHRINK_K = 30.0      # jockey / trainer rides of prior weight
BASE_RATE = 0.08     # prior win rate per ride (about 1 / 12.5 runners)
TEST_FROM = pd.Timestamp("2016-09-28")

GROUPS = {
    "form": ["last_pos", "avg_pos3", "last_margin", "avg_margin3", "n_prev_log", "debut"],
    "rating_weight": ["rating", "rating_chg", "act_wt", "act_wt_chg", "decl_wt", "decl_wt_chg", "no_rating"],
    "draw": ["draw", "draw_hv"],
    "connections": ["jockey_rate", "trainer_rate"],
    "speed": ["last_speed", "best_speed3", "no_speed"],
    "layoff_trip": ["days_log", "dist_chg", "surf_chg", "career_log"],
    "past_odds": ["last_logodds", "avg_logodds3"],
}
FLAGS = {"debut", "no_rating", "no_speed"}
COLS = [c for g in GROUPS.values() for c in g]

LBW_WORDS = {"NOSE": 0.05, "SH": 0.1, "HD": 0.2, "H": 0.2, "N": 0.3, "NK": 0.3, "DH": 0.0,
             "ML": 30.0, "M.L.": 30.0, "T.O.": 30.0, "TO": 30.0}


# ---------------------------------------------------------------- parsing

def parse_lbw(s: pd.Series) -> np.ndarray:
    """Lengths from HKJC's notation (1-3/4, 3/4, SH, N, ML ...). For the winner
    the column holds the winning margin, for the rest the distance behind."""
    t = s.fillna("").astype(str).str.strip().str.upper()
    words = t.map(LBW_WORDS).astype(float)
    m = t.str.extract(r"^(\d+)?(?:[- ]?(\d+)/(\d+))?$")
    whole = pd.to_numeric(m[0], errors="coerce")
    frac = pd.to_numeric(m[1], errors="coerce") / pd.to_numeric(m[2], errors="coerce")
    num = (whole.fillna(0) + frac.fillna(0)).where(whole.notna() | frac.notna())
    return words.where(words.notna(), num).clip(upper=30.0).to_numpy(float)


def parse_time(s: pd.Series) -> np.ndarray:
    m = s.fillna("").astype(str).str.extract(r"^(\d+)\.(\d{2})\.(\d{2})$").astype(float)
    return (m[0] * 60 + m[1] + m[2] / 100).to_numpy(float)


# ---------------------------------------------------------------- history

def load_history() -> pd.DataFrame:
    """Every Hong Kong performances row (finishers), typed, with this run's own
    outcome columns. Those columns are only ever read as PAST runs."""
    p = H.load_performances()
    p = p[p.horse_id.notna()].copy()
    p["race_date"] = p.race_date.astype("datetime64[ns]")
    for c in ["rating", "actual_weight", "on_date_weight", "draw", "distance"]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p.sort_values(["race_date", "race_no", "horse_id"]).reset_index(drop=True)
    if p.duplicated(["race_date", "race_no", "horse_id"]).any():
        raise SystemExit("performances: (race_date, race_no, horse_id) not unique")
    p["season"] = H.season_of(p.race_date)
    p["venue"] = p.race_location.astype(str)
    p["track"] = p.track.astype(str)
    rk = p.race_date.dt.strftime("%Y-%m-%d") + "|" + p.race_no.astype(str)
    p["rkey"] = pd.factorize(rk)[0]
    p["won1"] = (p.final_placing == 1).astype(int)
    # jockey_id / trainer_id are null for people with no current HKJC profile
    # (54% of 2006/07 jockey rows, 0% from 2016/17); the names are never null
    # and map one-to-one onto the ids where both exist, so the name is the key.
    p["jockey_key"] = p.jockey_name.astype(str)
    p["trainer_key"] = p.trainer_name.astype(str)
    g = p.groupby("rkey")
    p["n_first"] = g.won1.transform("sum")
    fld = np.maximum(g.horse_id.transform("size"), g.final_placing.transform("max"))
    # a field with fewer rows than its highest placing is missing runners (most in 2006-2008)
    p["complete"] = g.horse_id.transform("size") >= g.final_placing.transform("max")
    p["pos_n"] = (p.final_placing - 1) / (fld - 1).clip(lower=1)
    lbw = parse_lbw(p.length_behind_winner)
    p["margin"] = np.clip(np.where(p.final_placing == 1, -lbw, lbw), -10, 30)
    p["time_s"] = parse_time(p.finish_time)
    p["logodds"] = np.log(p.winning_odds.clip(lower=1.0))   # that past race's final odds (capped at 99)
    return add_speed(p)


def add_speed(p: pd.DataFrame) -> pd.DataFrame:
    """Speed figure of each run: finish time against the par for (venue, track,
    distance) from winners on STRICTLY earlier dates, less the day's variant
    (median of that day's winners against par). Read only as a past run."""
    p = p.copy()
    p["ckey"] = p.venue + "|" + p.track + "|" + p.distance.round().astype("Int64").astype(str)
    w = p[(p.final_placing == 1) & np.isfinite(p.time_s)].assign(t2=lambda x: x.time_s ** 2)
    d = w.groupby(["ckey", "race_date"]).agg(s=("time_s", "sum"), ss=("t2", "sum"), n=("time_s", "size")).reset_index()
    d = d.sort_values(["ckey", "race_date"])
    gk = d.groupby("ckey")
    d["cs"], d["css"], d["cn"] = gk.s.cumsum(), gk.ss.cumsum(), gk.n.cumsum()
    left = p[["ckey", "race_date"]].drop_duplicates().sort_values("race_date")
    m = pd.merge_asof(left, d[["ckey", "race_date", "cs", "css", "cn"]].sort_values("race_date"),
                      on="race_date", by="ckey", allow_exact_matches=False)
    m["par"] = (m.cs / m.cn).where(m.cn >= 5)
    var = (m.css / m.cn - (m.cs / m.cn) ** 2) * m.cn / (m.cn - 1)
    m["par_sd"] = np.sqrt(var.clip(lower=0)).where(m.cn >= 5)
    p = p.merge(m[["ckey", "race_date", "par", "par_sd"]], on=["ckey", "race_date"], how="left")
    p["tz"] = (p.time_s - p.par) / p.par_sd.clip(lower=0.3)
    var_day = p[p.final_placing == 1].groupby(["race_date", "venue", "track"]).tz.median().rename("variant")
    p = p.merge(var_day.reset_index(), on=["race_date", "venue", "track"], how="left")
    p["speed"] = -(p.tz - p.variant)
    return p.sort_values(["race_date", "race_no", "horse_id"]).reset_index(drop=True)


def horse_state(p: pd.DataFrame) -> pd.DataFrame:
    """A horse's state AFTER each run (including it). Attached to a later race
    with merge_asof on strictly earlier dates."""
    s = p.sort_values(["horse_id", "race_date"]).copy()
    g = s.groupby("horse_id", sort=False)

    def roll(col: str, fn: str) -> np.ndarray:
        r = getattr(g[col].rolling(3, min_periods=1), fn)()
        return r.reset_index(level=0, drop=True).reindex(s.index).to_numpy(float)

    st = pd.DataFrame({
        "horse_id": s.horse_id.to_numpy(), "st_date": s.race_date.to_numpy(),
        "st_pos": s.pos_n.to_numpy(float), "st_pos3": roll("pos_n", "mean"),
        "st_margin": s.margin.to_numpy(float), "st_margin3": roll("margin", "mean"),
        "st_speed": s.speed.to_numpy(float), "st_speed3": roll("speed", "max"),
        "st_rating": s.rating.to_numpy(float), "st_actwt": s.actual_weight.to_numpy(float),
        "st_declwt": s.on_date_weight.to_numpy(float), "st_dist": s.distance.to_numpy(float),
        "st_track": s.track.to_numpy(), "st_logodds": s.logodds.to_numpy(float),
        "st_logodds3": roll("logodds", "mean"), "st_n": g.cumcount().to_numpy() + 1,
        "st_first": g.race_date.transform("min").to_numpy(),
    })
    return st.sort_values("st_date").reset_index(drop=True)


def connection_rate(p: pd.DataFrame, T: pd.DataFrame, who: str) -> np.ndarray:
    """Win rate over the previous 365 days of rides, strictly earlier DAYS only,
    shrunk toward BASE_RATE with SHRINK_K rides of prior weight."""
    col = f"{who}_key"
    d = p[p[col].notna()].groupby([col, "race_date"]).agg(r=("won1", "size"), w=("won1", "sum")).reset_index()
    d = d.sort_values([col, "race_date"])
    d["cr"], d["cw"] = d.groupby(col).r.cumsum(), d.groupby(col).w.cumsum()
    d = d.sort_values("race_date")
    left = T.loc[T[col].notna(), ["ix", col, "race_date"]].sort_values("race_date")
    now = pd.merge_asof(left, d[[col, "race_date", "cr", "cw"]], on="race_date", by=col,
                        allow_exact_matches=False)
    left2 = left.assign(t=left.race_date - pd.Timedelta(days=365)).sort_values("t")
    ago = pd.merge_asof(left2, d[[col, "race_date", "cr", "cw"]].rename(columns={"race_date": "t"}),
                        on="t", by=col, allow_exact_matches=True)
    now = now.set_index("ix")
    ago = ago.set_index("ix").reindex(now.index)
    rides = now.cr.fillna(0) - ago.cr.fillna(0)
    wins = now.cw.fillna(0) - ago.cw.fillna(0)
    rate = (wins + SHRINK_K * BASE_RATE) / (rides + SHRINK_K)
    out = np.full(len(T), BASE_RATE)
    out[rate.index.to_numpy()] = rate.to_numpy()
    return out


def build_targets(p: pd.DataFrame, checks: dict) -> pd.DataFrame:
    """One row per runner to score: every performances row, plus every pool
    runner missing from performances (scratched, dnf, no_sections). Features
    come from strictly earlier rows only."""
    cur = ["horse_id", "race_date", "race_no", "horse_no", "season", "venue", "track", "distance",
           "rating", "actual_weight", "on_date_weight", "draw", "jockey_key", "trainer_key",
           "rkey", "won1", "n_first", "pos_n", "complete"]
    perf = p[cur].assign(in_perf=True)
    res = H.load_results()
    races = H.load_races().set_index("race_id")
    ex = res[res.status.isin(["scratched", "dnf", "no_sections"]) & res.horse_id.notna()].copy()
    ex["venue"] = ex.race_id.map(races.venue).astype(str)
    ex["track"] = ex.race_id.map(races.track).astype(str)
    ex["distance"] = ex.race_id.map(races.distance).astype(float)
    ex = ex[["horse_id", "race_date", "race_no", "horse_no", "season", "venue", "track", "distance"]].copy()
    ex["race_date"] = ex.race_date.astype("datetime64[ns]")
    ex["horse_no"] = ex.horse_no.astype("Int64")
    ex["in_perf"] = False
    checks["pool_runners_not_in_performances"] = res[res.status.isin(["scratched", "dnf", "no_sections"])] \
        .status.value_counts().to_dict()
    T = pd.concat([perf, ex], ignore_index=True)
    T["ix"] = np.arange(len(T))
    st = horse_state(p)
    m = pd.merge_asof(T[["ix", "horse_id", "race_date"]].sort_values("race_date"), st,
                      left_on="race_date", right_on="st_date", by="horse_id",
                      allow_exact_matches=False).set_index("ix").reindex(T.ix)
    m.index = T.index
    bad = (m.st_date.notna() & (m.st_date >= T.race_date)).sum()
    if bad:
        raise SystemExit(f"{bad} history states not strictly before their race")
    checks["history_state_strictly_earlier"] = True
    T["debut"] = m.st_n.isna().astype(float)
    T["last_pos"], T["avg_pos3"] = m.st_pos, m.st_pos3
    T["last_margin"], T["avg_margin3"] = m.st_margin, m.st_margin3
    T["n_prev_log"] = np.log1p(m.st_n.fillna(0))
    T["rating"] = T.rating.astype(float)
    T["no_rating"] = (T.in_perf & T.rating.isna()).astype(float)
    T["rating_chg"] = T.rating - m.st_rating
    T["act_wt"] = T.actual_weight.astype(float)
    T["act_wt_chg"] = T.act_wt - m.st_actwt
    T["decl_wt"] = T.on_date_weight.astype(float)
    T["decl_wt_chg"] = T.decl_wt - m.st_declwt
    T["draw"] = T.draw.astype(float)
    T["draw_hv"] = T.draw * (T.venue == "HV")
    T["last_speed"], T["best_speed3"] = m.st_speed, m.st_speed3
    T["no_speed"] = (m.st_n.notna() & m.st_speed.isna()).astype(float)
    T["days_log"] = np.log1p((T.race_date - m.st_date).dt.days)
    T["dist_chg"] = np.log(T.distance / m.st_dist)
    T["surf_chg"] = (T.track != m.st_track).astype(float).where(m.st_n.notna())
    T["career_log"] = np.log1p((T.race_date - m.st_first).dt.days / 365.25)
    T["last_logodds"], T["avg_logodds3"] = m.st_logodds, m.st_logodds3
    T["jockey_rate"] = np.where(T.jockey_key.notna(), connection_rate(p, T, "jockey"), np.nan)
    T["trainer_rate"] = np.where(T.trainer_key.notna(), connection_rate(p, T, "trainer"), np.nan)
    T["own_pos_leak"] = T.pos_n          # the race's OWN finish: used by the leak check only
    dup_tr = p.groupby(["rkey", "trainer_key"]).size()
    checks["history_race_trainer_pairs_with_2plus_runners"] = int((dup_tr > 1).sum())
    return T


# ---------------------------------------------------------------- design and fits

def design(frame: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """Within-race standardisation. A missing value becomes the race mean (0);
    a flag is centred within the race."""
    X = np.zeros((len(frame), len(cols)))
    g = frame.groupby("race_id", sort=False)
    for j, c in enumerate(cols):
        x = frame[c].astype(float)
        mu = g[c].transform("mean")
        if c in FLAGS:
            X[:, j] = (x - mu).fillna(0.0).to_numpy()
        else:
            sd = g[c].transform("std")
            X[:, j] = ((x - mu) / sd.where(sd > 1e-12)).fillna(0.0).to_numpy()
    return X


def assert_one_winner(frame: pd.DataFrame, what: str) -> None:
    n = frame.groupby("race_id", sort=False).won.sum()
    if not (n == 1).all():
        raise SystemExit(f"{what}: {int((n != 1).sum())} races without exactly one winner")


def clogit_se(X: np.ndarray, won: np.ndarray, starts: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Standard errors from the inverse information matrix of the conditional
    logit at b: sum over races of X'(diag p - p p')X."""
    p = softmax_by_race(X @ b, starts)
    M = np.add.reduceat(p[:, None] * X, starts)
    info = (X * p[:, None]).T @ X - M.T @ M
    return np.sqrt(np.diag(np.linalg.inv(info)))


def fit_stage1(T: pd.DataFrame, cols: list[str], seasons: list[int],
               complete_only: bool = False) -> tuple[np.ndarray, int]:
    tr = T[T.in_perf & T.season.isin(seasons) & (T.n_first == 1)].copy()
    if complete_only:
        tr = tr[tr.complete.astype(bool)]
    tr = tr.sort_values(["rkey", "horse_id"]).reset_index(drop=True)
    tr["race_id"], tr["won"] = tr.rkey, tr.won1
    if tr.season.max() >= min(s for s, _ in FOLDS.values()):
        raise SystemExit("stage 1 training reaches a season with pool snapshots")
    assert_one_winner(tr, "stage 1 training")
    st = starts_of(tr)
    b = fit_clogit(design(tr, cols), tr.won.to_numpy(), st, l2=1.0)
    return b, int(len(st))


def add_model(frame: pd.DataFrame, cols: list[str], b: np.ndarray) -> np.ndarray:
    return softmax_by_race(design(frame, cols) @ b, starts_of(frame))


def benter(frame: pd.DataFrame, fit_season: int, grade_season: int) -> tuple[pd.DataFrame, dict]:
    """Stage 2 on fit_season (one-winner races), applied to grade_season.
    frame carries p_model, p_pool, won, ll_ok, season, race_id (sorted)."""
    fit = frame[(frame.season == fit_season) & frame.ll_ok]
    assert_one_winner(fit, "stage 2 fit")
    sf, wf = starts_of(fit), fit.won.to_numpy()
    Zf = np.c_[np.log(fit.p_model.to_numpy()), np.log(fit.p_pool.to_numpy())]
    b2 = fit_clogit(Zf, wf, sf, l2=1e-3)
    se2 = clogit_se(Zf, wf, sf, b2)
    Pf = np.log(fit.p_pool.to_numpy())[:, None]
    bp = fit_clogit(Pf, wf, sf, l2=1e-3)
    sep = clogit_se(Pf, wf, sf, bp)
    gr = frame[frame.season == grade_season].copy()
    sg = starts_of(gr)
    gr["p_star"] = softmax_by_race(np.c_[np.log(gr.p_model.to_numpy()), np.log(gr.p_pool.to_numpy())] @ b2, sg)
    gr["p_cal"] = softmax_by_race(np.log(gr.p_pool.to_numpy()) * bp[0], sg)
    ev = gr[gr.ll_ok]
    assert_one_winner(ev, "graded log-likelihood set")
    w = ev.won.to_numpy() == 1
    nfield = ev.groupby("race_id", sort=False).won.transform("size").to_numpy()
    ll = {"uniform": -np.log(nfield[w])}
    for k, c in [("pool", "p_pool"), ("pool_cal", "p_cal"), ("stage1", "p_model"), ("blend", "p_star")]:
        ll[k] = np.log(np.clip(ev[c].to_numpy()[w], 1e-12, 1.0))
    info = {"fit_races": int(len(sf)), "graded_races": int(w.sum()),
            "b": float(b2[0]), "b_se": float(se2[0]), "c": float(b2[1]), "c_se": float(se2[1]),
            "c_pool_only": float(bp[0]), "c_pool_only_se": float(sep[0]),
            "ll": {k: float(v.mean()) for k, v in ll.items()}}
    for k in ("pool", "pool_cal"):
        d = ll["blend"] - ll[k]
        info[f"blend_minus_{k}"] = float(d.mean())
        info[f"blend_minus_{k}_se"] = float(d.std(ddof=1) / math.sqrt(len(d)))
    return gr, info


# ---------------------------------------------------------------- frames

def lead_frame(L: float, T: pd.DataFrame, checks: dict) -> pd.DataFrame:
    df = H.decision_frame(L)
    races_all = df.race_id.nunique()
    df = df[df.bettable].copy()
    df["race_date"] = df.race_date.astype("datetime64[ns]")
    tt = T[(T.race_date >= TEST_FROM) & T.horse_no.notna()].copy()
    tt["horse_no"] = tt.horse_no.astype(int)
    if tt.duplicated(["race_date", "race_no", "horse_no"]).any():
        raise SystemExit("test targets: (race_date, race_no, horse_no) not unique")
    keep = ["race_date", "race_no", "horse_no", "in_perf"] + COLS + ["own_pos_leak"]
    df = df.drop(columns=[c for c in keep[3:] if c in df.columns])
    df = df.merge(tt[keep], on=["race_date", "race_no", "horse_no"], how="left", indicator=True)
    miss = int((df.pop("_merge") != "both").sum())
    if miss:
        raise SystemExit(f"lead {L}: {miss} bettable runners with no feature row")
    df = df.sort_values(["race_id", "horse_no"]).reset_index(drop=True)
    df["dec_price"] = df.win_at_snap
    q = pd.Series(1.0 / H.unfloor(df.win_at_snap.to_numpy()), index=df.index)
    df["p_pool"] = (q / q.groupby(df.race_id).transform("sum")).to_numpy()   # de-vigged in proportion
    nw = df.groupby("race_id").won.transform("sum")
    df["ll_ok"] = (nw == 1) & (df.n_win_div == 1)
    r1 = df.drop_duplicates("race_id")
    checks[f"lead_{L}"] = {
        "graded_races_in_snapshot": int(races_all), "races_with_bettable_runners": int(r1.race_id.nunique()),
        "bettable_runners": int(len(df)),
        "snap_lead_median": float(r1.snap_lead.median()), "snap_lead_p90": float(r1.snap_lead.quantile(.9)),
        "snap_lead_max": float(r1.snap_lead.max()),
        "races_winner_not_bettable": int((r1.race_id.map(df.groupby("race_id").won.sum()) == 0).sum()),
        "dead_heat_races": int((r1.n_win_div > 1).sum()),
        "ll_races_by_season": df[df.ll_ok].drop_duplicates("race_id").season.value_counts().sort_index().to_dict(),
        "runners_without_current_card": df[~df.in_perf.astype(bool)].final_status.value_counts().to_dict(),
        "refunds_bettable": int(df.refund.sum()),
    }
    return df


def final_frame(T: pd.DataFrame, checks: dict) -> pd.DataFrame:
    """Starters at the off with a post-off capture: the FINAL pool. An
    information test only: a rule that decides on it has seen the close."""
    res = H.load_results()
    f = res[res.graded & res.status.isin(["ran", "dnf", "no_sections"])].copy()
    full = f.groupby("race_id").final_win_disp.transform(lambda s: s.notna().all())
    f = f[full].copy()
    f["race_date"] = f.race_date.astype("datetime64[ns]")
    tt = T[(T.race_date >= TEST_FROM) & T.horse_no.notna()].copy()
    tt["horse_no"] = tt.horse_no.astype(int)
    keep = ["race_date", "race_no", "horse_no", "in_perf"] + COLS + ["own_pos_leak"]
    f = f.drop(columns=[c for c in keep[3:] if c in f.columns])   # results' own rating, draw, ... columns
    f = f.merge(tt[keep], on=["race_date", "race_no", "horse_no"], how="left", indicator=True)
    if (f.pop("_merge") != "both").any():
        raise SystemExit("final frame: starters with no feature row")
    f = f.sort_values(["race_id", "horse_no"]).reset_index(drop=True)
    f["dec_price"] = f.final_win_disp
    f["refund"] = False
    q = pd.Series(1.0 / H.unfloor(f.final_win_disp.to_numpy()), index=f.index)
    f["p_pool"] = (q / q.groupby(f.race_id).transform("sum")).to_numpy()
    nw = f.groupby("race_id").won.transform("sum")
    f["ll_ok"] = (nw == 1) & (f.n_win_div == 1)
    checks["final"] = {"races": int(f.race_id.nunique()), "runners": int(len(f)),
                       "ll_races_by_season": f[f.ll_ok].drop_duplicates("race_id").season.value_counts()
                       .sort_index().to_dict()}
    return f


# ---------------------------------------------------------------- bets

def pick(gr: pd.DataFrame, pcol: str, cut: float, min_p: float | None = None) -> pd.DataFrame:
    """The runner with the largest EV in each race (EV at the decision price),
    bet when EV > cut. min_p excludes runners BEFORE the best one is chosen."""
    d = gr.copy()
    d["ev"] = d[pcol] * d.dec_price - 1.0
    if min_p is not None:
        d = d[d[pcol] >= min_p]
    top = d.loc[d.groupby("race_id").ev.idxmax()]
    return top[top.ev > cut]


def summarise(b: pd.DataFrame) -> dict:
    if b.empty:
        return {"bets": 0}
    profit, risk = H.pool_bet_units(b.dec_price.to_numpy(), b.win_dec.to_numpy(), b.won.to_numpy(),
                                    b.refund.to_numpy(bool))
    live = risk > 0
    if not live.any():
        return {"bets": 0, "refunds": int((~live).sum())}
    by = pd.DataFrame({"r": b.race_id.to_numpy(), "p": profit, "k": risk}).groupby("r").sum()
    by = by[by.k > 0]
    roi = by.p.sum() / by.k.sum()
    se = math.sqrt(((by.p - roi * by.k) ** 2).sum()) / by.k.sum()
    won = (b.won.to_numpy() > 0)
    flat = np.where(won, b.win_dec.to_numpy() - 1.0, -1.0)[live]
    drift = np.log(b.final_win_disp / b.dec_price).to_numpy()[live]
    return {"bets": int(live.sum()), "refunds": int((~live).sum()), "wins": int(won[live].sum()),
            "units": float(profit.sum()), "risk": float(risk.sum()), "roi": float(roi),
            "lo": float(roi - 1.96 * se), "hi": float(roi + 1.96 * se),
            "flat_units": float(flat.sum()), "flat_roi": float(flat.mean()),
            "mean_dec_price": float(b.dec_price.to_numpy()[live].mean()),
            "median_log_final_over_decision": float(np.nanmedian(drift)) if np.isfinite(drift).any() else float("nan")}


def cell(r: dict) -> str:
    """bets (wins) | units / risked | return [CI] | flat units (return)"""
    if not r.get("bets"):
        return f"0 ({r.get('refunds', 0)} ref.) | | | "
    return (f"{r['bets']:,} ({r['wins']}) | {r['units']:+.2f} / {r['risk']:.2f} | "
            f"{100 * r['roi']:+.1f}% [{100 * r['lo']:+.1f}, {100 * r['hi']:+.1f}] | "
            f"{r['flat_units']:+.1f} ({100 * r['flat_roi']:+.1f}%)")


def half(r: dict) -> str:
    if not r.get("bets"):
        return "0"
    return f"{r['bets']} ({r['wins']}), {r['units']:+.2f}u / {r['risk']:.2f}, {100 * r['roi']:+.1f}%"


BET_HEAD = ("| EV cut | blend: bets (wins) | units / risked | return [95% CI] | flat 1u: units (return) | "
            "median odds; log(final/decision) | blend, p >= 0.04: bets (wins) | units / risked | return [95% CI] | "
            "flat 1u: units (return) | early half | late half | calibrated pool alone: bets |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def bet_table(gr: pd.DataFrame, title: str, controls: bool = True) -> tuple[str, list]:
    lines, out = [f"\n{title}\n", BET_HEAD], []
    mid = gr.race_date.drop_duplicates().sort_values().iloc[gr.race_date.nunique() // 2]
    for cut in EV_CUTS:
        b = pick(gr, "p_star", cut)
        bl = pick(gr, "p_star", cut, LONGSHOT_P)
        rb, rl = summarise(b), summarise(bl)
        re_, rlate = summarise(b[b.race_date < mid]), summarise(b[b.race_date >= mid])
        rc = summarise(pick(gr, "p_cal", cut)) if controls else {"bets": None}
        for name, r in (("blend", rb), (f"blend p>={LONGSHOT_P}", rl), ("blend early", re_),
                        ("blend late", rlate), ("calibrated pool", rc)):
            out.append({"ev_cut": cut, "set": name, **r})
        live = b[~b.refund.astype(bool)]
        odds = (f"{live.dec_price.median():.1f}; {rb['median_log_final_over_decision']:+.3f}"
                if rb.get("bets") else "")
        lines.append(f"| > {cut:.2f} | {cell(rb)} | {odds} | {cell(rl)} | {half(re_)} | {half(rlate)} | "
                     f"{'' if rc['bets'] is None else rc['bets']} |")
    lines.append(f"\nEarly half = race dates before {mid.date()}; late half = from it. "
                 "Refunds (priced at the decision, scratched later) are 0 units out of 0 and not counted as bets.")
    return "\n".join(lines), out


# ---------------------------------------------------------------- main

def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return o


def ll_line(tag: str, info: dict) -> str:
    ll = info["ll"]
    return (f"| {tag} | {info['graded_races']} | {ll['uniform']:.4f} | {ll['pool']:.4f} | {ll['pool_cal']:.4f} | "
            f"{ll['stage1']:.4f} | {ll['blend']:.4f} | {info['blend_minus_pool']:+.4f} ± {info['blend_minus_pool_se']:.4f} | "
            f"{info['blend_minus_pool_cal']:+.4f} ± {info['blend_minus_pool_cal_se']:.4f} |")


LL_HEAD = ("| pool / fold (graded season) | races | uniform | pool | calibrated pool | stage 1 alone | blend | "
           "blend − pool (± SE) | blend − calibrated pool (± SE) |\n|---|---|---|---|---|---|---|---|---|")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    t0 = time.time()
    checks: dict = {}
    out: dict = {"checks": checks}

    p = load_history()
    one = p.drop_duplicates("rkey")
    checks["history"] = {"rows": int(len(p)), "races": int(len(one)),
                         "first": str(p.race_date.min().date()), "last": str(p.race_date.max().date()),
                         "races_by_first_count": one.n_first.value_counts().sort_index().to_dict(),
                         "winner_margin_parsed": float(np.isfinite(p.margin[p.final_placing == 1]).mean()),
                         "speed_figure_coverage_2006_on": float(p[p.season >= 2006].speed.notna().mean())}
    # is one horse_id one horse? (a recycled brand would hand a new horse a dead one's form)
    nm = p.groupby("horse_id").horse_name.nunique()
    span = p.groupby("horse_id").race_date.agg(lambda x: (x.max() - x.min()).days / 365.25)
    gap = p.sort_values(["horse_id", "race_date"]).groupby("horse_id").race_date.diff().dt.days / 365.25
    checks["horse_identity"] = {"horse_ids_with_2plus_names": int((nm > 1).sum()), "horse_ids": int(len(nm)),
                                "max_career_span_years": round(float(span.max()), 2),
                                "gaps_between_runs_over_4_years": int((gap > 4).sum())}
    tr_races = p[p.season.isin(STAGE1_SEASONS)].drop_duplicates("rkey")
    checks["history"]["training_races_with_missing_runners_by_season"] = (
        tr_races[~tr_races.complete].season.value_counts().sort_index().to_dict())
    T = build_targets(p, checks)
    tr_mask = T.in_perf & T.season.isin(STAGE1_SEASONS) & (T.n_first == 1)
    checks["stage1_training"] = {"seasons": f"{H.season_label(STAGE1_SEASONS[0])} to {H.season_label(STAGE1_SEASONS[-1])}",
                                 "runners": int(tr_mask.sum()),
                                 "races": int(T[tr_mask].rkey.nunique()),
                                 "races_dropped_not_one_winner": int(T[T.in_perf & T.season.isin(STAGE1_SEASONS)
                                                                      & (T.n_first != 1)].rkey.nunique()),
                                 "feature_missing_share": {c: round(float(T.loc[tr_mask, c].isna().mean()), 4)
                                                           for c in COLS if c not in FLAGS}}
    print(f"[{time.time() - t0:.0f}s] history and targets built", file=sys.stderr)

    frames = {L: lead_frame(L, T, checks) for L in LEADS}
    frames["final"] = final_frame(T, checks)
    print(f"[{time.time() - t0:.0f}s] frames built", file=sys.stderr)

    print("# Hong Kong pre-race pool: Benter two-stage, walk-forward\n")
    print("## Data checks\n")
    print("```\n" + json.dumps(jsonable(checks), indent=1, default=str) + "\n```")

    # ---- stage 1
    b1, n1 = fit_stage1(T, COLS, STAGE1_SEASONS)
    tr = T[tr_mask].sort_values(["rkey", "horse_id"]).reset_index(drop=True).assign(race_id=lambda x: x.rkey, won=lambda x: x.won1)
    se1 = clogit_se(design(tr, COLS), tr.won.to_numpy(), starts_of(tr), b1)
    print(f"\n## Stage 1 coefficients (fit on {n1:,} races, {checks['stage1_training']['seasons']}; "
          f"within-race z-scores, L2 = 1)\n")
    print("| group | feature | coef | se |\n|---|---|---|---|")
    for gname, gcols in GROUPS.items():
        for c in gcols:
            j = COLS.index(c)
            print(f"| {gname} | {c} | {b1[j]:+.4f} | {se1[j]:.4f} |")
    out["stage1"] = {c: [float(b1[i]), float(se1[i])] for i, c in enumerate(COLS)}

    def run_all(cols: list[str], coef: np.ndarray, tags=("10", "5", "2", "final"), folds=("A", "B")):
        res = {}
        for key in LEADS + ["final"]:
            if str(key) not in tags:
                continue
            fr = frames[key].copy()
            fr["p_model"] = add_model(fr, cols, coef)
            for fold in folds:
                fs, gs = FOLDS[fold]
                gr, info = benter(fr, fs, gs)
                res[(key, fold)] = (gr, info)
        return res

    full = run_all(COLS, b1)
    print(f"[{time.time() - t0:.0f}s] main fits done", file=sys.stderr)

    print("\n## Out-of-sample log-likelihood per race (mean log p of the winner)\n")
    print("Same race set within each row: one-winner graded races whose winner was priced at the decision.\n")
    print(LL_HEAD)
    out["ll"], out["coef"] = {}, {}
    for (key, fold), (gr, info) in full.items():
        fs, gs = FOLDS[fold]
        tag = (f"lead {key} min" if key != "final" else "FINAL pool (information test)") + \
              f", fold {fold}: fit {H.season_label(fs)}, graded {H.season_label(gs)}"
        print(ll_line(tag, info))
        out["ll"][f"{key}|{fold}"] = info
    print("\n## Stage 2 coefficients (fit season's one-winner races; SE from the inverse information matrix)\n")
    print("| pool / fold | fit races | b (stage 1) | c (pool) | calibrated pool alone: c |\n|---|---|---|---|---|")
    for (key, fold), (gr, info) in full.items():
        tag = (f"lead {key} min" if key != "final" else "FINAL pool") + f", fold {fold}"
        print(f"| {tag} | {info['fit_races']} | {info['b']:+.3f} ± {info['b_se']:.3f} | "
              f"{info['c']:+.3f} ± {info['c_se']:.3f} | {info['c_pool_only']:+.3f} ± {info['c_pool_only_se']:.3f} |")

    print("\n## Bets: the largest-EV runner per race, EV at the decision odds, paid at the final dividend\n")
    print("Units: 1 unit to win at the decision price, risk capped at 3, paid at dividend / 10. "
          f"The p >= {LONGSHOT_P} rows drop runners under it BEFORE the best runner is chosen. "
          "Median odds are the blend bets' decision odds; log(final/decision) is their median move to the "
          "final displayed odds (hindsight, shown only to say how the price moved after the decision; "
          "+ means the price drifted out).")
    out["bets"] = {}
    for (key, fold), (gr, info) in full.items():
        fs, gs = FOLDS[fold]
        if key == "final":
            title = (f"### FINAL pool, fold {fold} (graded {H.season_label(gs)}): UPPER BOUND, decides on the "
                     f"closing odds, not a bettable rule")
        else:
            title = f"### Lead {key} min, fold {fold}: stage 2 fit {H.season_label(fs)}, graded {H.season_label(gs)}"
        txt, rows = bet_table(gr, title, controls=True)
        print(txt)
        out["bets"][f"{key}|{fold}"] = rows

    # ---- ablation
    print("\n## Ablation: one feature group removed (stage 1 refit, stage 2 refit; fold A, graded 2017/2018)\n")
    print("| removed | stage-1 LL (lead 5 set) | blend LL lead 10 | blend LL lead 5 | blend LL lead 2 | "
          "blend LL final | b at lead 5 |\n|---|---|---|---|---|---|---|")
    out["ablation"] = {}

    def abl_row(name: str, res: dict) -> None:
        i5 = res[(5, "A")][1]
        vals = [res[(k, "A")][1]["ll"]["blend"] for k in (10, 5, 2, "final")]
        print(f"| {name} | {i5['ll']['stage1']:.4f} | " + " | ".join(f"{v:.4f}" for v in vals) +
              f" | {i5['b']:+.3f} ± {i5['b_se']:.3f} |")
        out["ablation"][name] = {"stage1_ll_lead5": i5["ll"]["stage1"], "blend_ll": vals, "b5": i5["b"]}

    abl_row("nothing (full model)", {k: v for k, v in full.items()})
    for gname, gcols in GROUPS.items():
        keep = [c for c in COLS if c not in gcols]
        bg, _ = fit_stage1(T, keep, STAGE1_SEASONS)
        abl_row(gname, run_all(keep, bg, folds=("A",)))
    ball, nall = fit_stage1(T, COLS, sorted(T[T.in_perf & (T.season < 2016)].season.unique().tolist()))
    abl_row(f"(window) stage 1 on every season to 2015/2016 ({nall:,} races)", run_all(COLS, ball, folds=("A",)))
    bcf, ncf = fit_stage1(T, COLS, STAGE1_SEASONS, complete_only=True)
    abl_row(f"(fields) stage 1 on complete fields only, 2006/2007 to 2015/2016 ({ncf:,} races)",
            run_all(COLS, bcf, folds=("A",)))
    print(f"[{time.time() - t0:.0f}s] ablation done", file=sys.stderr)

    # ---- leak check
    print("\n## Leak check: the race's OWN finishing position (normalised) added to stage 1\n")
    lcols = COLS + ["own_pos_leak"]
    bl, _ = fit_stage1(T, lcols, STAGE1_SEASONS)
    leak = run_all(lcols, bl, tags=("5", "final"), folds=("A",))
    print(f"stage-1 coefficient on own_pos_leak: {bl[-1]:+.3f}\n")
    print(LL_HEAD)
    for (key, fold), (gr, info) in leak.items():
        print(ll_line(f"LEAK, {'lead ' + str(key) + ' min' if key != 'final' else 'FINAL pool'}, fold {fold}", info))
    i5 = leak[(5, "A")][1]
    print(f"\nb at lead 5 with the leak: {i5['b']:+.3f} ± {i5['b_se']:.3f} (without: "
          f"{full[(5, 'A')][1]['b']:+.3f}); c: {i5['c']:+.3f} ± {i5['c_se']:.3f}")
    txt, rows = bet_table(leak[(5, "A")][0], "### LEAK bets, lead 5 min, fold A", controls=False)
    print(txt)
    out["leak"] = {"coef": float(bl[-1]), "lead5": i5, "final": leak[("final", "A")][1], "bets": rows}

    print(f"\n[{time.time() - t0:.0f}s] done", file=sys.stderr)
    if a.json:
        a.json.write_text(json.dumps(jsonable(out), indent=1, default=str), encoding="utf-8")
        print(f"\nwrote {a.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

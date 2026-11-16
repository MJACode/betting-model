"""Hong Kong pre-race POOL study, 2016-09-28 to 2018-06-27: is there a rule,
decided on the HKJC pools as they stood minutes before the start, that wins at
the final dividend?

The question is the one a US bettor faces in the commingled HKJC pools: the
bet is placed on what the screen shows a few minutes out and paid at the final
dividend, which keeps moving to the off and a few minutes after it.

Reads the nch015 scrape through `scripts/horse/hk_preoff_data.py` (the time
base, joins and grading are established there; the files on disk are a cache
of rows stored in Supabase). No network, no database.

DECISION AND PAYMENT
  * Decided at a fixed lead L before the SCHEDULED start (30, 15, 10, 5, 2
    minutes): the last capture taken at least L minutes out
    (`hk_preoff_data.snapshot_at`). The capture cadence is 6 minutes, so the
    real lead of the capture is L to L+6.5 minutes; part 0 prints it.
  * Sized at the screen price at the decision (1 unit to win, risk 1/(d-1)
    capped at 3) and paid at the final dividend / 10
    (`hk_preoff_data.pool_bet_units`). A runner priced at the decision and
    scratched later is a refund: 0 units out of 0 risked, counted separately.
  * won / placed come from the dividends. A dead-heat dividend is already split.
  * Pool shares are de-vigged in proportion (it is a pool), from un-floored
    display odds (`hk_preoff_data.unfloor`), over the runners priced at that
    moment.
  * Nothing a rule decides on is from after its capture: no final odds, no
    result, no sectional of the race. The "close" rows are hindsight references
    (decided on the final pool), labelled so, never a rule.
  * Anything fitted is fitted on 2016/2017 and graded on 2017/2018.

    python -I scripts/horse/hk_preoff_pool_study.py [--md OUT]
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
from scripts.horse import hk_preoff_data as H  # noqa: E402
from scripts.horse.anz_study import harville_top  # noqa: E402
from scripts.horse.clogit import fit_clogit, softmax_by_race, starts_of  # noqa: E402

LEADS = [30, 15, 10, 5, 2]
BANDS = [0.99, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 51.0, 1000.0]   # left edge under 1.0 keeps odds of 1.0
SHARE_BANDS = [0.0, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0]
MOVE_BINS = [-np.inf, -0.4, -0.2, -0.1, -0.03, 0.03, 0.1, 0.2, 0.4, np.inf]   # fixed before looking
# Every lead pair the study has graded, kept in full: 30->5 and 15->2 were
# dropped from a draft after their results were read and are restored here
# (the reviewer's finding, 2026-11-15), so the count of rules tested is honest.
PAIRS = [(30, 15), (15, 5), (10, 2), (30, 5), (15, 2), (30, 2)]
PLACE_CUTS = [-0.20, -0.10, -0.05, 0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30]
STARTERS = ["ran", "dnf", "no_sections"]
FIT, GRADE = 2016, 2017

OUT: list[str] = []
CELLS: list[tuple[str, dict]] = []   # every decidable rule graded on its full sample


def tally(label: str, r: dict, moment: str = "") -> None:
    if "hindsight" not in moment:
        CELLS.append((label, r))


def emit(s: str = "") -> None:
    print(s)
    OUT.append(s)


def table(headers: list[str], rows: list[list]) -> None:
    emit("| " + " | ".join(headers) + " |")
    emit("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        emit("| " + " | ".join(str(x) for x in r) + " |")
    emit()


# ---------------------------------------------------------------- grading

def grade(f: pd.DataFrame, stake: str, paid: str, won: str) -> dict:
    """Units for one bet set: sized at `stake` (the screen price at the
    decision), paid at `paid` (dividend / 10), 95% interval clustered by race.
    Refunds are 0 out of 0 and counted apart from bets."""
    f = f[np.isfinite(f[stake].to_numpy(float)) & (f[stake].to_numpy(float) >= 1.0)]
    if f.empty:
        return {"bets": 0}
    ref = f["refund"].to_numpy(bool)
    w = f[won].to_numpy(float) > 0
    pd_ = f[paid].to_numpy(float)
    profit, risk = H.pool_bet_units(f[stake].to_numpy(float), pd_, w, ref)
    nb = int((~ref).sum())
    if nb == 0:
        return {"bets": 0, "refunds": int(ref.sum())}
    by = pd.DataFrame({"m": f.race_id.to_numpy(), "p": profit, "r": risk}).groupby("m").sum()
    roi = by.p.sum() / by.r.sum()
    se = math.sqrt(((by.p - roi * by.r) ** 2).sum()) / by.r.sum()
    flat = np.where(w, pd_ - 1.0, -1.0)[~ref].mean()
    return {"bets": nb, "refunds": int(ref.sum()), "wins": int((w & ~ref).sum()),
            "units": float(profit.sum()), "risk": float(risk.sum()), "roi": float(roi),
            "lo": float(roi - 1.96 * se), "hi": float(roi + 1.96 * se), "flat": float(flat)}


def cells(r: dict) -> list:
    if not r.get("bets"):
        return [0, "", "", "", "", "", ""]
    return [f"{r['bets']:,}", f"{r['wins']:,}", f"{r['units']:+.1f}", f"{r['risk']:.1f}",
            f"{100 * r['roi']:+.1f}%", f"[{100 * r['lo']:+.1f}, {100 * r['hi']:+.1f}]",
            f"{100 * r['flat']:+.1f}%"]


GH = ["bets", "wins", "units", "risked", "return", "95% CI", "flat return"]


def short(r: dict) -> str:
    if not r.get("bets"):
        return "0 bets"
    return f"{100 * r['roi']:+.1f}% [{100 * r['lo']:+.1f}, {100 * r['hi']:+.1f}] ({r['bets']:,} bets, {r['units']:+.1f}u)"


def clears(r: dict) -> bool:
    return bool(r.get("bets")) and r["lo"] > 0


# ---------------------------------------------------------------- frames

def shares(df: pd.DataFrame, odds_col: str) -> np.ndarray:
    """Pool share in proportion from un-floored display odds, per race over the rows given."""
    q = 1.0 / H.unfloor(df[odds_col].to_numpy(float))
    s = pd.Series(q, index=df.index).groupby(df.race_id.to_numpy()).transform("sum").to_numpy()
    return q / s


def lead_frame(L: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = H.decision_frame(L)
    if not (d.snap_lead >= L - 1e-9).all():
        raise AssertionError(f"lead {L}: a capture later than the decision moment")
    b = d[d.bettable].copy()
    if b.win_at_snap.isna().any() or not b.won.isin([0.0, 1.0]).all():
        raise AssertionError(f"lead {L}: unpriced or ungraded bettable rows")
    if (b.won.eq(1) & b.win_dec.isna()).any() or (b.placed.eq(1) & b.pla_dec.isna()).any():
        raise AssertionError(f"lead {L}: a winner or placer without a dividend")
    if (b.refund & (b.won.eq(1) | b.placed.eq(1))).any():
        raise AssertionError(f"lead {L}: a refunded runner was paid")
    b["share"] = shares(b, "win_at_snap")
    b["band"] = pd.cut(b.win_at_snap, BANDS)
    return d, b.sort_values(["race_id", "horse_no"]).reset_index(drop=True)


def close_frame(res: pd.DataFrame) -> pd.DataFrame:
    """Starters of graded races with a post-off capture, at the final pool (hindsight)."""
    c = res[res.graded & res.final_win_disp.notna()].copy()
    if not c.status.isin(STARTERS).all():
        raise AssertionError("close frame holds a scratched runner")
    c["refund"] = False
    c["share"] = shares(c, "final_win_disp")
    c["band"] = pd.cut(c.final_win_disp, BANDS)
    return c.sort_values(["race_id", "horse_no"]).reset_index(drop=True)


def half_of(frame: pd.DataFrame, mid: dict) -> np.ndarray:
    m = frame.season.map(mid)
    return np.where(frame.race_date <= m, "H1", "H2")


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, help="also write the markdown tables here")
    a = ap.parse_args(argv)
    t0 = time.time()
    res = H.load_results()
    D, B = {}, {}
    for L in LEADS:
        D[L], B[L] = lead_frame(L)
    C = close_frame(res)
    races = H.load_races()
    # season halves: split each season at its median meeting date (graded races)
    gdates = res[res.graded].drop_duplicates("race_id")
    mid = {s: g.race_date.drop_duplicates().sort_values().iloc[len(g.race_date.drop_duplicates()) // 2 - 1]
           for s, g in gdates.groupby("season")}
    for f in list(B.values()) + [C]:
        f["half"] = half_of(f, mid)

    # ------------------------------------------------ 0. the frames and the clock
    emit("## 0. Decision frames, the real lead, and the grading check")
    emit()
    emit(f"Season halves split at the median meeting: {', '.join(f'{H.season_label(s)} at {d.date()}' for s, d in mid.items())}.")
    emit()
    rows = []
    for L in LEADS:
        d, b = D[L], B[L]
        rl = d.drop_duplicates("race_id").snap_lead
        rows.append([L, f"{d.race_id.nunique():,}", f"{len(b):,}", f"{int(b.refund.sum())}",
                     f"{rl.quantile(.1):.2f}", f"{rl.median():.2f}", f"{rl.quantile(.9):.2f}", f"{rl.max():.2f}",
                     f"{b.drop_duplicates('race_id').season.eq(FIT).sum()} / {b.drop_duplicates('race_id').season.eq(GRADE).sum()}"])
    table(["nominal lead (min)", "graded races", "bettable runners", "refunds (priced, scratched later)",
           "real lead p10", "real lead median", "real lead p90", "real lead max", "races 2016/17 / 2017/18"], rows)
    rows = []
    for e, l in [(15, 10), (10, 5), (5, 2), (15, 5), (10, 2), (30, 15)]:
        x = D[e].drop_duplicates("race_id")[["race_id", "snap_no", "snap_lead"]].merge(
            D[l].drop_duplicates("race_id")[["race_id", "snap_no", "snap_lead"]], on="race_id", suffixes=("_e", "_l"))
        same = x.snap_no_e == x.snap_no_l
        gap = (x.snap_lead_e - x.snap_lead_l)[~same]
        rows.append([f"{e} -> {l}", f"{len(x):,}", f"{int(same.sum()):,}", f"{gap.median():.2f}",
                     f"{gap.quantile(.1):.2f}", f"{gap.quantile(.9):.2f}"])
    table(["leads", "races at both", "races where both leads pick ONE capture", "real gap median (min)",
           "gap p10", "gap p90"], rows)
    w1 = C[(C.won == 1) & (C.n_win_div == 1)]
    chk = w1.share * w1.win_dec
    emit(f"Grading check: the winner's final pool share x its dividend/10, over {len(w1):,} single-winner races "
         f"with a post-off capture: median {chk.median():.4f} (p5 {chk.quantile(.05):.4f}, p95 {chk.quantile(.95):.4f}); "
         f"1 - takeout = {1 - H.WIN_TAKEOUT:.4f}. Winners per graded race in the close frame equal the win dividends "
         f"in {int((C.groupby('race_id').won.sum() == C.groupby('race_id').n_win_div.first()).sum()):,} of "
         f"{C.race_id.nunique():,} races.")
    emit()

    # ------------------------------------------------ 1. calibration and log loss
    emit("## 1. Calibration of the win pool at each lead and at the close")
    emit()
    common = set.intersection(*[set(b.race_id) for b in B.values()]) & set(C.race_id)
    n_before = len(common)
    late_scr = set().union(*[set(b[b.refund].race_id) for b in B.values()])
    common -= late_scr
    mism = 0
    for L in LEADS:
        bl = B[L][B[L].race_id.isin(common)]
        cl = C[C.race_id.isin(common)]
        mism += len(set(zip(bl.race_id, bl.horse_no)) ^ set(zip(cl.race_id, cl.horse_no)))
    emit(f"Common race set: graded races present at all five leads and with a post-off capture: {n_before:,}; "
         f"less {n_before - len(common)} races with a runner priced at some lead and scratched later "
         f"(its share would inflate every other runner's final share): {len(common):,} races. "
         f"Runner sets at the leads and at the close differ in {mism} (race, runner) pairs.")
    emit()
    moments = [(f"{L} min", B[L][B[L].race_id.isin(common)]) for L in LEADS] + \
              [("close (hindsight)", C[C.race_id.isin(common)])]
    rows = []
    for name, f in moments:
        bb = pd.cut(f.share, SHARE_BANDS)
        t = f.groupby(bb, observed=True).agg(n=("won", "size"), said=("share", "mean"), won=("won", "mean"))
        for k, v in t.iterrows():
            z = (v.won - v.said) / math.sqrt(v.said * (1 - v.said) / v.n)
            rows.append([name, str(k), f"{int(v.n):,}", f"{v.said:.4f}", f"{v.won:.4f}",
                         f"{100 * (v.won - v.said):+.2f}", f"{z:+.1f}"])
    table(["moment", "pool share band", "runners", "pool share (mean)", "win rate", "gap (points)", "z"], rows)

    single = set(C[C.race_id.isin(common)].groupby("race_id").n_win_div.first().loc[lambda s: s == 1].index)
    emit(f"Log loss per race (minus log of the winner's pool share; lower is better) on the {len(single):,} "
         f"single-winner races of the common set. beta is a one-parameter conditional logit, p proportional to "
         f"share^beta, fitted per season (beta > 1: favourites win more often than their share says). "
         f"The last column applies the 2016/17 beta to 2017/18.")
    emit()
    cl_close = C[C.race_id.isin(single)].sort_values(["race_id", "horse_no"])
    llc = cl_close[cl_close.won == 1].set_index("race_id").share.pipe(lambda s: -np.log(s))
    rows = []
    for name, f in moments:
        f = f[f.race_id.isin(single)].sort_values(["race_id", "horse_no"]).reset_index(drop=True)
        llr = f[f.won == 1].set_index("race_id").share.pipe(lambda s: -np.log(s))
        seas = f.drop_duplicates("race_id").set_index("race_id").season
        dlt = (llr - llc.reindex(llr.index))
        betas = {}
        for s in (FIT, GRADE):
            g = f[f.season == s]
            betas[s] = fit_clogit(np.log(g.share.to_numpy())[:, None], g.won.to_numpy(), starts_of(g), l2=1e-3)[0]
        g = f[f.season == GRADE]
        pc = softmax_by_race(betas[FIT] * np.log(g.share.to_numpy()), starts_of(g))
        ll_cal = float(-np.log(pc[g.won.to_numpy() == 1]).mean())
        rows.append([name, f"{len(llr):,}", f"{llr.mean():.4f}", f"{llr[seas == FIT].mean():.4f}",
                     f"{llr[seas == GRADE].mean():.4f}", f"{dlt.mean():+.4f} ({dlt.std() / math.sqrt(len(dlt)):.4f})",
                     f"{betas[FIT]:.3f}", f"{betas[GRADE]:.3f}", f"{ll_cal:.4f}"])
    fu = C[C.race_id.isin(single)].groupby("race_id").size()
    rows.append(["uniform (1/field)", f"{len(fu):,}", f"{np.log(fu).mean():.4f}", "", "", "", "", "", ""])
    table(["moment", "races", "log loss", "2016/17", "2017/18", "minus close (SE)", "beta 2016/17",
           "beta 2017/18", "2017/18 with 2016/17 beta"], rows)

    # ------------------------------------------------ 2. blind win bets by band
    emit("## 2. Blind win bets by odds band at each lead, graded at the final win dividend")
    emit()
    emit("Band read on the screen at the lead; sized at that price; paid at the dividend. Every bettable runner, "
         "both seasons. The close rows decide on the final pool (hindsight, a reference only).")
    emit()
    band_roi: dict = {}
    rows, flag2 = [], []
    for name, f, stake in [(f"{L} min", B[L], "win_at_snap") for L in LEADS] + [("close (hindsight)", C, "final_win_disp")]:
        groups = [(str(k), g) for k, g in f.groupby("band", observed=True)] + [("all runners", f)]
        for k, g in groups:
            r = grade(g, stake, "win_dec", "won")
            rs = {s: grade(g[g.season == s], stake, "win_dec", "won") for s in (FIT, GRADE)}
            band_roi[(name, k)] = r.get("roi", np.nan)
            rows.append([name, k] + cells(r) + [short(rs[FIT]), short(rs[GRADE])])
            tally(f"part 2 {name} band {k}", r, name)
            if clears(r) and all(x.get("roi", -1) > 0 for x in rs.values()):
                flag2.append(f"{name} {k}")
    table(["moment", "odds band at the moment", *GH, "2016/17", "2017/18"], rows)
    emit("The favourite at each lead (shortest screen price; a tie is broken by the lower saddle-cloth number):")
    emit()
    rows = []
    for name, f, stake in [(f"{L} min", B[L], "win_at_snap") for L in LEADS] + [("close (hindsight)", C, "final_win_disp")]:
        o = f.sort_values(["race_id", stake, "horse_no"])
        fav = o.drop_duplicates("race_id")
        ties = int((o.groupby("race_id")[stake].transform("min").eq(o[stake]).groupby(o.race_id).sum() > 1).sum())
        r = grade(fav, stake, "win_dec", "won")
        rs = {s: grade(fav[fav.season == s], stake, "win_dec", "won") for s in (FIT, GRADE)}
        rows.append([name, ties] + cells(r) + [short(rs[FIT]), short(rs[GRADE])])
        tally(f"part 2 {name} favourite", r, name)
        if clears(r) and all(x.get("roi", -1) > 0 for x in rs.values()):
            flag2.append(f"{name} favourite")
    table(["moment", "races with tied favourites", *GH, "2016/17", "2017/18"], rows)
    emit(f"Cells with the 95% interval above 0 and both seasons positive: {flag2 or 'none'}.")
    emit()

    # ------------------------------------------------ 3. late money
    emit("## 3. Late money: the change in pool share between two leads")
    emit()
    emit("move = log(share at the later lead / share at the earlier lead), both shares taken over the runners "
         "priced at BOTH captures. Decided and sized at the later lead, paid at the final dividend. Races where "
         "the two leads pick the same capture are dropped. A pool only takes backing bets, so fading a steamer "
         "is backing the drifters and vice versa: both directions are rows of the same table. "
         "'band-matched blind' is the return the same bets would be expected to make from their odds band "
         "alone (each bet's risk times the blind return of its band at the later lead, part 2, both seasons): "
         "a move bin adds information only if it beats that.")
    emit()
    rows, rows_x, flag3, dropped = [], [], [], []
    lbl =["<= -0.4", "-0.4 to -0.2", "-0.2 to -0.1", "-0.1 to -0.03", "-0.03 to 0.03", "0.03 to 0.1",
           "0.1 to 0.2", "0.2 to 0.4", "> 0.4"]
    for e, l in PAIRS:
        early = B[e][["race_id", "horse_no", "snap_no", "snap_lead", "win_at_snap"]].rename(
            columns={"snap_no": "snap_no_e", "snap_lead": "snap_lead_e", "win_at_snap": "win_e"})
        m = B[l].merge(early, on=["race_id", "horse_no"])
        same = m.snap_no == m.snap_no_e
        n_same = m[same].race_id.nunique()
        m = m[~same].copy()
        if not (m.snap_lead_e > m.snap_lead).all():
            raise AssertionError(f"{e}->{l}: the earlier capture is not earlier")
        m["share_l"] = shares(m, "win_at_snap")
        m["share_e"] = shares(m, "win_e")
        m["move"] = np.log(m.share_l / m.share_e)
        m["mbin"] = pd.cut(m.move, MOVE_BINS, labels=lbl)
        _, risk = H.pool_bet_units(m.win_at_snap.to_numpy(float), m.win_dec.to_numpy(float),
                                   m.won.to_numpy(float), m.refund.to_numpy(bool))
        m["risk"] = risk
        m["ctrl"] = [band_roi.get((f"{l} min", str(k)), np.nan) for k in m.band]
        pname = f"{e} -> {l}"
        dropped.append(f"{e} -> {l}: {n_same} races dropped, {m.race_id.nunique():,} kept, real gap median "
                       f"{(m.drop_duplicates('race_id').snap_lead_e - m.drop_duplicates('race_id').snap_lead).median():.2f} min")

        def ctrl_of(g):
            return f"{100 * (g.risk * g.ctrl).sum() / g.risk.sum():+.1f}%" if g.risk.sum() > 0 else ""

        for k, g in m.groupby("mbin", observed=True):
            r = grade(g, "win_at_snap", "win_dec", "won")
            rs = {s: grade(g[g.season == s], "win_at_snap", "win_dec", "won") for s in (FIT, GRADE)}
            rows.append([pname, str(k)] + cells(r) + [ctrl_of(g), short(rs[FIT]), short(rs[GRADE])])
            tally(f"part 3 {e}->{l} move {k}", r)
            if clears(r) and all(x.get("roi", -1) > 0 for x in rs.values()):
                flag3.append(f"{e}->{l} {k}")
        for rule, idx in [("biggest steamer in the race", m.groupby("race_id").move.idxmax()),
                          ("biggest drifter in the race", m.groupby("race_id").move.idxmin())]:
            g = m.loc[idx]
            r = grade(g, "win_at_snap", "win_dec", "won")
            rs = {s: grade(g[g.season == s], "win_at_snap", "win_dec", "won") for s in (FIT, GRADE)}
            rows.append([pname, rule] + cells(r) + [ctrl_of(g), short(rs[FIT]), short(rs[GRADE])])
            tally(f"part 3 {e}->{l} {rule}", r)
            if clears(r) and all(x.get("roi", -1) > 0 for x in rs.values()):
                flag3.append(f"{e}->{l} {rule}")
        if (e, l) in [(15, 5), (10, 2)]:
            og = pd.cut(m.win_at_snap, [0.99, 5, 15, 1000], labels=["<= 5", "5 to 15", "> 15"])
            mg = pd.cut(m.move, [-np.inf, -0.1, 0.1, np.inf], labels=["drift (< -0.1)", "flat", "steam (> 0.1)"])
            for (ko, km), g in m.groupby([og, mg], observed=True):
                r = grade(g, "win_at_snap", "win_dec", "won")
                rs = {s: grade(g[g.season == s], "win_at_snap", "win_dec", "won") for s in (FIT, GRADE)}
                rows_x.append([f"{e} -> {l}", ko, km] + cells(r) + [ctrl_of(g), short(rs[FIT]), short(rs[GRADE])])
                tally(f"part 3 {e}->{l} odds {ko} {km}", r)
    emit(f"Races where both leads pick the same capture: {'; '.join(dropped)}.")
    emit()
    table(["leads", "move (log share ratio)", *GH, "band-matched blind", "2016/17", "2017/18"], rows)
    emit("The same moves split by the odds at the later lead:")
    emit()
    table(["leads", "odds at the later lead", "move", *GH, "band-matched blind", "2016/17", "2017/18"], rows_x)
    emit(f"Cells with the 95% interval above 0 and both seasons positive: {flag3 or 'none'}.")
    emit()

    # ------------------------------------------------ 4. win pool against place pool
    emit("## 4. Win pool against place pool at the lead (the Dr Z test on live pools)")
    emit()
    emit("Harville top-3 probability from the win pool share at the lead, over the runners priced then; "
         "calibrated by a logistic on logit(Harville) and log(field at the lead), fitted on 2016/17 (refunds "
         "left out of the fit). Bet the place when calibrated chance x the place odds on the screen at the "
         "lead - 1 exceeds the cut; sized at that place price, paid at the FINAL place dividend; graded on "
         "2017/18. 3-place races only (place terms from the field when the pool opened): the 2-place races "
         "are too few to fit.")
    emit()
    from sklearn.linear_model import LogisticRegression
    n2 = res[res.graded].drop_duplicates("race_id").places_paid.value_counts().to_dict()
    emit(f"Graded races by place terms: {n2} (3 = three places paid).")
    emit()

    def place_frame(f: pd.DataFrame, pla_col: str) -> pd.DataFrame:
        f = f[f.places_paid == 3].sort_values(["race_id", "horse_no"]).copy()
        hv = np.full(len(f), np.nan)
        for _, idx in f.groupby("race_id").indices.items():
            hv[idx] = harville_top(f.share.to_numpy()[idx], 3)
        f["hv"] = hv
        f = f[f[pla_col].notna()].copy()
        f["lh"] = np.log(f.hv.clip(1e-4, 1 - 1e-4) / (1 - f.hv.clip(1e-4, 1 - 1e-4)))
        f["lf"] = np.log(f.groupby("race_id").race_id.transform("size"))
        q = 1.0 / H.unfloor(f[pla_col].to_numpy(float))
        f["pl_share"] = 3 * q / pd.Series(q, index=f.index).groupby(f.race_id.to_numpy()).transform("sum").to_numpy()
        return f

    rows, rows_raw, coefs, flag4 = [], [], [], []
    cal_rows = []
    pla_res = res[["race_id", "horse_no", "final_pla_disp"]]
    for name, f, pla in [(f"{L} min", B[L], "pla_at_snap") for L in LEADS] + \
                        [("close (hindsight)", C, "final_pla_disp")]:
        p = place_frame(f, pla)
        fit = p[(p.season == FIT) & ~p.refund]
        lr = LogisticRegression(C=1e6, max_iter=1000).fit(fit[["lh", "lf"]], fit.placed)
        p["p_cal"] = lr.predict_proba(p[["lh", "lf"]])[:, 1]
        p["ev"] = p.p_cal * p[pla] - 1
        p["ev_raw"] = p.hv * p[pla] - 1
        coefs.append([name, f"{len(fit):,}", f"{lr.intercept_[0]:+.3f}", f"{lr.coef_[0][0]:+.3f}",
                      f"{lr.coef_[0][1]:+.3f}", f"{p[p.season == GRADE].race_id.nunique():,}"])
        te = p[p.season == GRADE]
        for cut in PLACE_CUTS:
            g = te[te.ev > cut]
            r = grade(g, pla, "pla_dec", "placed")
            h1 = grade(g[g.half == "H1"], pla, "pla_dec", "placed")
            h2 = grade(g[g.half == "H2"], pla, "pla_dec", "placed")
            ins = grade(p[(p.season == FIT) & (p.ev > cut)], pla, "pla_dec", "placed")
            rows.append([name, f"{cut:+.2f}"] + cells(r) + [short(h1), short(h2), short(ins)])
            tally(f"part 4 {name} EV > {cut:+.2f}", r, name)
            if clears(r) and h1.get("roi", -1) > 0 and h2.get("roi", -1) > 0 and name != "close (hindsight)":
                flag4.append(f"{name} EV > {cut:+.2f}")
        for cut in (0.0, 0.10, 0.20):
            rs = {s: grade(p[(p.season == s) & (p.ev_raw > cut)], pla, "pla_dec", "placed") for s in (FIT, GRADE)}
            rows_raw.append([name, f"{cut:+.2f}", short(rs[FIT]), short(rs[GRADE])])
        if name in ("5 min", "close (hindsight)"):
            bb = pd.cut(te.hv, [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0])
            t = te[~te.refund].groupby(bb, observed=True).agg(
                n=("placed", "size"), hv=("hv", "mean"), cal=("p_cal", "mean"),
                pool=("pl_share", "mean"), placed=("placed", "mean"))
            for k, v in t.iterrows():
                cal_rows.append([name, str(k), f"{int(v.n):,}", f"{v.hv:.3f}", f"{v.cal:.3f}", f"{v.pool:.3f}",
                                 f"{v.placed:.3f}"])
    table(["moment", "fit rows (2016/17)", "intercept", "logit(Harville)", "log(field)", "graded races 2017/18"], coefs)
    table(["moment", "EV cut", *GH, "2017/18 first half", "2017/18 second half", "2016/17 (in-sample fit)"], rows)
    emit("Uncalibrated Harville (nothing fitted, so both seasons are out of sample):")
    emit()
    table(["moment", "EV cut", "2016/17", "2017/18"], rows_raw)
    emit("Calibration on 2017/18 by raw Harville band (place pool share = 3 x the place pool's de-vigged share):")
    emit()
    table(["moment", "Harville band", "runners", "Harville", "calibrated", "place pool share", "placed rate"], cal_rows)
    emit(f"Decidable cells (not the close) with the 95% interval above 0 and both halves of 2017/18 positive: {flag4 or 'none'}.")
    emit()

    # ------------------------------------------------ 5. drift from lead to final
    emit("## 5. Drift from the lead to the final odds")
    emit()
    emit("r = log(final odds / odds at the lead), both un-floored display odds, over runners priced at the lead "
         "and in the pool at the close (races with a post-off capture). r < 0: the runner shortened. The last "
         "two columns are for winners only: what a winner was PAID (dividend/10) over the screen price it was "
         "sized at.")
    emit()
    rows, allr, books = [], [], []
    fbook = C.groupby("race_id").final_win_disp.apply(lambda s: (1.0 / H.unfloor(s)).sum())
    for L in LEADS:
        b = B[L]
        f = b[b.final_status.isin(STARTERS) & b.final_win_disp.notna()].copy()
        sf = shares(f, "final_win_disp") / shares(f, "win_at_snap")
        books.append(f"{L} min: book {b.drop_duplicates('race_id').book_mid_at_snap.median():.4f}, "
                     f"runners whose share fell to the close {(sf < 1).mean():.1%}")
        f["r"] = np.log(H.unfloor(f.final_win_disp) / H.unfloor(f.win_at_snap))
        f["same"] = np.isclose(f.final_win_disp, f.win_at_snap)
        f["wr"] = np.log(f.win_dec / f.win_at_snap)
        allr.append(f[["race_id", "horse_no", "snap_no", "snap_lead", "r"]])
        for k, g in [(str(k), g) for k, g in f.groupby("band", observed=True)] + [("all", f)]:
            w = g[g.won == 1]
            rows.append([f"{L} min", k, f"{len(g):,}", f"{g.r.median():+.3f}", f"{g.r.mean():+.3f}",
                         f"{g.r.quantile(.1):+.3f}", f"{g.r.quantile(.9):+.3f}", f"{g.r.abs().median():.3f}",
                         f"{g.same.mean():.1%}", f"{(g.final_win_disp < g.win_at_snap).mean():.1%}",
                         f"{(g.final_win_disp > g.win_at_snap).mean():.1%}", f"{len(w):,}",
                         f"{np.exp(w.wr.median()):.3f}" if len(w) else ""])
    table(["lead", "odds band at the lead", "runners", "median r", "mean r", "p10 r", "p90 r", "median abs(r)",
           "unchanged", "shortened", "drifted", "winners", "winners: paid / screen price (median)"], rows)
    emit(f"Win book (sum of 1/un-floored odds, median per race) at each lead against the close "
         f"{fbook.median():.4f}: {'; '.join(books)}. The book does not move, so the drift is money moving "
         f"between runners: most runners lose share and a few gain a lot.")
    emit()
    a_ = pd.concat(allr).drop_duplicates(["race_id", "horse_no", "snap_no"])
    bk = pd.cut(a_.snap_lead, [2, 4, 6, 8, 12, 16, 24, 40])
    t = a_.groupby(bk, observed=True).r.agg(n="size", med="median", mabs=lambda x: x.abs().median())
    emit("The same drift by the REAL lead of the capture (each capture counted once across the five frames):")
    emit()
    table(["real lead (min)", "runners", "median r", "median abs(r)"],
          [[str(k), f"{int(v['n']):,}", f"{v['med']:+.3f}", f"{v['mabs']:.3f}"] for k, v in t.iterrows()])
    rows = []
    for L in LEADS:
        b = B[L].merge(pla_res, on=["race_id", "horse_no"], how="left")
        f = b[b.final_status.isin(STARTERS) & b.final_pla_disp.notna() & b.pla_at_snap.notna()]
        rp = pd.Series(np.log(H.unfloor(f.final_pla_disp) / H.unfloor(f.pla_at_snap)))
        w = f[f.placed == 1]
        rows.append([f"{L} min", f"{len(f):,}", f"{rp.median():+.3f}", f"{rp.abs().median():.3f}",
                     f"{np.isclose(f.final_pla_disp, f.pla_at_snap).mean():.1%}", f"{len(w):,}",
                     f"{np.exp(np.log(w.pla_dec / w.pla_at_snap).median()):.3f}"])
    table(["lead", "runners", "median r (place odds)", "median abs(r)", "unchanged", "placers",
           "placers: paid / screen place price (median)"], rows)

    emit("## Verdict lines")
    emit()
    pos = [(lab, r) for lab, r in CELLS if r.get("bets") and r["roi"] > 0]
    above = [(lab, r) for lab, r in CELLS if clears(r)]
    emit(f"Decidable bet sets graded on their full sample (parts 2-4, hindsight rows excluded): {len(CELLS)}. "
         f"With a positive return: {len(pos)} "
         f"({'; '.join(f'{lab}: {short(r)}' for lab, r in pos) or 'none'}). "
         f"With the 95% interval above 0: {len(above)} "
         f"({'; '.join(f'{lab}: {short(r)}' for lab, r in above) or 'none'}).")
    emit()
    emit(f"Blind win bets and favourites (part 2): {flag2 or 'no cell clears'}.")
    emit(f"Late money (part 3): {flag3 or 'no cell clears'}.")
    emit(f"Win pool against place pool (part 4): {flag4 or 'no cell clears'}.")
    emit()
    emit(f"(run time {time.time() - t0:.0f} s)")
    if a.md:
        a.md.write_text("\n".join(OUT) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

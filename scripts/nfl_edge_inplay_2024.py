"""
In-game NFL game lines, the SECOND season: 2024, graded with the identical
construction of scripts/nfl_edge_inplay_2025.py, then 2024 + 2025 pooled.

Run from the worktree root:
    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_inplay_2024
    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_inplay_2024 --repro2025
The second form re-runs 2025 with the ORIGINAL rules (no fixes) and checks
every one of the 132 primary cells against the 2025 study's own output file
(inplay2025_out.txt): it is the proof that this file's re-implementation of H1-H6
is the same construction. It reads no 2024 price.

No database, no network, no Odds API call. Reads the local cache only
(scripts/nfl_edge_lib.CACHE): inplay_2024.parquet, inplay_2025.parquet,
pbp_<season>.parquet, nflverse_games.parquet, era5_kick_1999_2025.parquet,
odds_hist_2020_2025.parquet, and inplay2025_out.txt (the 2025 result, read only
for the replication list and the --repro2025 check). Writes
inplay_2024_cells.csv and inplay_2024_lagbook.csv to the cache. Results are
UNITS: one unit = one flat bet.

CONSTRUCTION - written before any 2024 price was compared with any outcome.

H1-H6, the cut grids, the windows, the state-at-snapshot rule, the venues, the
best-price rule, the grading and the inference are those of
scripts/nfl_edge_inplay_2025.py (its docstring is the specification; its helper
functions are imported unchanged). The 132-cell family is the same 66 cell
definitions x {DK, best}. What differs:

REFIT.  Each season is graded with a fit that never saw it.
  2024 is graded with every model fitted on 2016-2023 play-by-play only:
    H1  the 13 per-lead logistic win-probability regressions (lead 4..16);
    H2  the 4 per-window remaining-points least-squares fits (endQ1, midQ2,
        half, endQ3);
    H3  the 4 per-window final-margin least-squares fits;
    H5  the pooled all-states totals fit (its model-move measure).
  2025 is graded with the same four sets fitted on 2016-2024 (the 2025 study's
  own fit). Nothing else is fitted: the cuts, windows, lead range, wind
  thresholds and the possession rule are constants; H4 and H6 fit nothing.
  The nflverse vegas WP (H1 ref=nflverse) is nflverse's own model and is a
  measured one-row look-ahead (2025 study); it is reported, not trusted.

THREE FIXES from the 2025 verifiers, applied to BOTH seasons:
  (1) Play-end fallback.  A play with no end_clock_time ended at its snap
      time_of_day + D(play type) instead of + 5 s. D was set from 2022-2023
      plays carrying both times (95th percentile of end - snap, rounded up):
      pass / run / no_play 8 s, punt 13 s, kickoff 10 s, field goal / extra
      point 5 s, kneel / spike 2 s, other 8 s; any non-offensive or return
      touchdown 25 s (2022-23 return TDs: kickoff max 19.7 s, punt 23.0 s,
      interception return 18.7 s). The fallback end is capped at the next
      play's snap where that is earlier (a play cannot end after the next
      snap).
  (2) Game-over flag on the SERVED time: over = snapshot_at >= the final
      play's known end (it was t_state, which in the 60 s lag check counted
      snapshots up to 60 s after the final play as live).
  (3) H5: the post-TD snapshot is the first snapshot served >= 60 s after the
      TD play ended (snapshots inside 60 s are dropped: the 2025 verifier
      measured that DK had not yet moved its total in them). Pre = the last
      snapshot before the TD ended, as before.

MEDIAN-BOOK PRICE.  At one snapshot, for one side, the bettable offers are
  ranked the way the best price ranks them (line first, then price) and the
  median book is the offer at 0-based rank n // 2 from the best (n = 5 -> the
  3rd; n = 4 -> the 3rd, i.e. the worse of the two middle books; n = 3 -> the
  2nd; n = 2 -> the worse; n = 1 -> the only one). It is a real quote at a
  real line. Two uses:
    "median"       a third venue: the trigger is evaluated and the bet graded
                   at the median offer (its own entries). Its 66 cells are
                   their own BH family, never added to the 132.
    "best@median"  the best cell's own bets re-graded at the median offer of
                   the same side at the same snapshot (the 2025 decomposition).
                   Descriptive. NOTE: 2025's +1.1% figure used the numeric
                   median of the five h2h prices; with five books the two
                   definitions agree, with four this one is slightly worse.
  2024 book count differs from 2025: fanatics quotes 2024 only from week 16,
  so 2024 is mostly a four-book market (DK, FanDuel, BetMGM, William Hill).

FAMILIES (BH q = 0.10, the zero-EV null of the 2025 study, which is generous
  for DK / median cells and anti-conservative for best-price cells):
  per season and pooled: 132 (DK + best, the pre-registered family); 66 DK;
  66 median venue; 132 DK + median venue; 66 best@median (descriptive).
  POOLED = the two seasons' bets for the same cell concatenated, 2024 bets
  from the 2016-2023 fit and 2025 bets from the 2016-2024 fit; CI clustered by
  game. REPLICATION = every 2025 cell with p < 0.10 in the 2025 output, shown
  for 2025 (original and re-run with the fixes) and 2024.

LAGGING-BOOK (CROSS-BOOK LATENCY) CONSTRUCTION - its own pre-registration, not
  in any BH family, and not a model: it is a stale-book effect, reported so it
  is understood, not proposed.
  Snapshots: a game state exists, regulation (qtr <= 4), not after the final
  play. Markets h2h, spreads, totals. A GROUP = one snapshot x one market x
  (spreads / totals) one exact line; at least 3 bettable books quoting it.
  Per side: gap = median implied probability of the books in the group (the
  best book included) minus the best implied probability. Trigger gap >= .02 /
  .03 / .04; if both sides trigger, the larger gap; an exact tie is skipped.
  Per snapshot and market, the group with the largest gap. Bet the outlier
  side AT THE OUTLIER BOOK'S PRICE. Readings: (a) one bet per game x market,
  the first qualifying snapshot (one-sided p by market); (b) every qualifying
  snapshot (game-clustered CI only, no p: repeated bets on one game are not
  independent). Also: the same bets at the group's median price, the ROI the
  median consensus expected (its de-vigged two-way probability x the outlier
  price - 1), the outlier book counts, and (h2h, score unchanged until the next
  snapshot) whether the outlier book moved to the others by the next snapshot.
  Snapshots are 5 minutes apart and books suspend during plays: whether any of
  these quotes could have been bet is unknown.

ORDER OF RUNS.  --repro2025 first (2025 only, original rules). Then one full
  run, its output kept under a run-numbered name, never overwritten.
"""
from __future__ import annotations

import hashlib
import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import nfl_edge_inplay_2025 as P
from scripts.nfl_edge_inplay_2025 import (
    CALM_LT, H1_CUTS, H1_WINDOWS, H2_CUTS, H3_CUTS, LAG_S, VENUES, WIND_MAX_VALID, WIND_T, WINDOWS,
    attach_games, attach_state, best_by, bh, boot, check_possession, cp_roi, fit_totals_margin, fit_wp,
    grade_spread, grade_total, leader_view, line_quotes, p_null, play_states, profit_of, two_sided_bets,
    venue_quotes, window_snaps, wp_lookup, x_margin, x_total)
from scripts.nfl_edge_lib import CACHE, am_to_dec, devig2, games, odds_hist

pd.set_option("display.width", 320)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 1000)
pd.set_option("display.max_colwidth", 60)

FIXES = True
KEYS = ["game_id", "snapshot_at"]
VEN3 = ("DK", "best", "median")
PLAY_DUR = {"pass": 8.0, "run": 8.0, "no_play": 8.0, "qb_kneel": 2.0, "qb_spike": 2.0,
            "extra_point": 5.0, "field_goal": 5.0, "kickoff": 10.0, "punt": 13.0}
PLAY_DUR_DEFAULT = 8.0
PLAY_DUR_NONOFF_TD = 25.0
H5_POST_MIN_S = 60
LB_GAPS = (0.02, 0.03, 0.04)
LB_MIN_BOOKS = 3
ML_HYPS = {"H1"}

ROWS: list[dict] = []
STORE: dict = {}
LB_ROWS: list[dict] = []
HOLD: dict = {}


# ─── cells ─────────────────────────────────────────────────────────────────

def summ(b, ml=False, halves=True, with_p=True):
    if b is None or len(b) == 0:
        return {"bets": 0, "games": 0, "units": 0.0, "roi": np.nan, "lo": np.nan, "hi": np.nan,
                "win": np.nan, "push": 0, "p": np.nan, "e_bets": 0, "e_units": 0.0, "e_roi": np.nan,
                "l_bets": 0, "l_units": 0.0, "l_roi": np.nan, "avg_dec": np.nan, "e_p": np.nan,
                "l_p": np.nan, "sd_bet": np.nan}
    v = b.v.values.astype(float)
    d = b.dec.values.astype(float)
    pr = profit_of(v, d)
    roi, lo, hi = boot(pr, b.game_id.values)
    early = b.week.values <= 9
    r = {"bets": len(b), "games": int(b.game_id.nunique()), "units": round(pr.sum(), 2),
         "roi": round(100 * roi, 1), "lo": round(100 * lo, 1), "hi": round(100 * hi, 1),
         "win": round(100 * (v == 1).mean(), 1), "push": int((v == 0.5).sum()),
         "p": round(p_null(v, d), 4) if with_p else np.nan,
         "e_bets": int(early.sum()), "e_units": round(pr[early].sum(), 2),
         "e_roi": round(100 * pr[early].mean(), 1) if early.any() else np.nan,
         "l_bets": int((~early).sum()), "l_units": round(pr[~early].sum(), 2),
         "l_roi": round(100 * pr[~early].mean(), 1) if (~early).any() else np.nan,
         "avg_dec": round(float(d.mean()), 3),
         "sd_bet": float(np.std(pr, ddof=1)) if len(pr) > 1 else np.nan}
    if halves and with_p:
        r["e_p"] = p_null(v[early], d[early]) if early.any() else np.nan
        r["l_p"] = p_null(v[~early], d[~early]) if (~early).any() else np.nan
    if ml:
        cl, ch = cp_roi(v, d)
        r["cp_lo"], r["cp_hi"] = round(100 * cl, 1), round(100 * ch, 1)
    if "edge" in b:
        r["avg_edge"] = round(float(b.edge.mean()), 3)
    return r


def cell(b, season, hyp, label, venue, fam="primary", ml=False, extra=None):
    if b is None:
        b = pd.DataFrame(columns=["game_id", "week", "v", "dec"])
    b = b.copy()
    b["season"] = season
    STORE[(season, fam, hyp, label, venue)] = b
    r = {"season": season, "fam": fam, "hyp": hyp, "cell": label, "venue": venue}
    r.update(summ(b, ml=ml, halves=(fam != "robust")))
    if extra:
        r.update(extra)
    ROWS.append(r)
    return r


SHOW = ["hyp", "cell", "venue", "bets", "units", "roi", "lo", "hi", "win", "push", "p",
        "e_bets", "e_units", "e_roi", "l_bets", "l_units", "l_roi", "avg_dec"]


def show(rows, title, extra_cols=()):
    t = pd.DataFrame(rows)
    if t.empty:
        print(f"\n{title}\n  (no cells)")
        return t
    t["lowN"] = np.where(t.bets < 30, "LOW-N", "")
    cols = [c for c in SHOW + list(extra_cols) if c in t.columns] + ["lowN"]
    print(f"\n{title}")
    print(t[cols].to_string(index=False))
    return t


def median_by(q, keys, line_col=None, line_high=True, dec_col="dec"):
    """One row per key: the offer at 0-based rank n // 2 from the best, ranked
    exactly as best_by ranks (best line first, then best decimal price)."""
    order, asc = [], []
    if line_col is not None:
        order.append(line_col)
        asc.append(not line_high)
    order.append(dec_col)
    asc.append(False)
    s = q[q[dec_col].notna()]
    s = s.sort_values(list(keys) + order, ascending=[True] * len(keys) + asc, kind="mergesort")
    g = s.groupby(list(keys), sort=False)
    rk = g.cumcount().values
    n = g[dec_col].transform("size").values
    return s[rk == n // 2]


# ─── states and quotes ─────────────────────────────────────────────────────

def finalize_states(p):
    n0 = len(p)
    p = p[p.t_end.notna()].copy()
    n_nt = n0 - len(p)
    tn = (p.t_end - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
    med = tn.groupby(p.game_id).transform(lambda s: s.rolling(9, center=True, min_periods=1).median())
    bad = (tn - med).abs() > 900
    p = p[~bad].copy()
    p["t_known"] = p.groupby("game_id").t_end.cummax()
    return p, n0, n_nt, int(bad.sum())


def states(season, g):
    p = play_states([season], timed=True)
    if FIXES:
        te = pd.to_datetime(p.end_clock_time, utc=True, errors="coerce", format="mixed") \
            .astype("datetime64[ns, UTC]")
        dur = p.play_type.map(PLAY_DUR).fillna(PLAY_DUR_DEFAULT).astype(float)
        dur = dur.where(~p.nonoff_td.astype(bool), PLAY_DUR_NONOFF_TD)
        fb = p.t_snap + pd.to_timedelta(dur, unit="s")
        nxt = p.groupby("game_id").t_snap.shift(-1)
        cap = nxt.notna() & (nxt > p.t_snap) & (nxt < fb)
        fb = fb.where(~cap, nxt)
        use_fb = te.isna() & p.t_snap.notna()
        p["t_end"] = te.fillna(fb)
        td = p.touchdown.fillna(0) == 1
        print(f"PLAY-END FALLBACK ({season}): {int(use_fb.sum()):,} plays have a snap time but no end "
              f"time and use snap + D(play type); of them TDs {int((use_fb & td).sum())}, non-offensive "
              f"or return TDs {int((use_fb & p.nonoff_td.astype(bool)).sum())}; fallback capped at the "
              f"next snap on {int((use_fb & cap).sum()):,}; by type "
              f"{p[use_fb].play_type.value_counts().to_dict()}")
    p = attach_games(p, g)
    st, n0, n_nt, nbad = finalize_states(p)
    print(f"{season} play states: {n0:,} plays with a posteam; {n_nt:,} with no time at all "
          f"(dropped; their score shows in the next timed play's post-play total); {nbad} clock-entry "
          f"outliers dropped; {len(st):,} timed states, {st.game_id.nunique()} games")
    st_old = None
    if FIXES:
        # the 2025 study's rule (+5 s), rebuilt on the same rows, to count what fix (1) changed
        po = p.copy()
        po["t_end"] = pd.to_datetime(po.end_clock_time, utc=True, errors="coerce", format="mixed") \
            .astype("datetime64[ns, UTC]").fillna(po.t_snap + pd.Timedelta(seconds=5))
        st_old = finalize_states(po)[0]
    return st, st_old


def load_inplay(season, g):
    d = pd.read_parquet(CACHE / f"inplay_{season}.parquet")
    d["snapshot_at"] = d.snapshot_at.astype("datetime64[ns, UTC]")
    d["commence_time"] = d.commence_time.astype("datetime64[ns, UTC]")
    return d[d.game_id.isin(g.game_id)]


def snapshot_frame(d, g, st, lag_s=0):
    snaps = d[["game_id", "snapshot_at", "commence_time"]].drop_duplicates(KEYS)
    x = attach_state(snaps, st, lag_s)
    tf = st.groupby("game_id").t_known.max().rename("t_final")
    x = x.join(tf, on="game_id")
    served = x.snapshot_at if FIXES else x.t_state
    x["over"] = (served >= x.t_final).fillna(False)
    gg = g[["game_id", "week", "game_type", "home_score", "away_score", "result", "total",
            "spread_line", "total_line", "roof", "wind", "home_team", "away_team"]]
    return x.merge(gg, on="game_id", how="left")


def median_table(q):
    k = KEYS
    cols = k + ["point", "dec", "bookmaker"]
    h = q[q.market == "h2h"]
    s = q[q.market == "spreads"].dropna(subset=["point"])
    t = q[q.market == "totals"].dropna(subset=["point"])
    parts = [median_by(h.assign(dec=h.dec_h), k)[cols].assign(market="h2h", side="home"),
             median_by(h.assign(dec=h.dec_a), k)[cols].assign(market="h2h", side="away"),
             median_by(s.assign(dec=s.dec_h), k, "point", True)[cols].assign(market="spreads", side="home"),
             median_by(s.assign(dec=s.dec_a), k, "point", False)[cols].assign(market="spreads", side="away"),
             median_by(t.assign(dec=t.dec_h), k, "point", False)[cols].assign(market="totals", side="over"),
             median_by(t.assign(dec=t.dec_a), k, "point", True)[cols].assign(market="totals", side="under")]
    return pd.concat(parts, ignore_index=True)


def regrade(b, offers, keys):
    drop = [c for c in ("dec", "point", "line", "bookmaker") if c in b.columns]
    z = b.drop(columns=drop).merge(offers[keys + ["side", "point", "dec", "bookmaker"]],
                                   on=keys + ["side"], how="left")
    miss = int(z.dec.isna().sum())
    z = z[z.dec.notna()].copy()
    mk = z.market.values
    v = z.v.values.astype(float).copy()
    sp, tt = mk == "spreads", mk == "totals"
    if sp.any():
        v[sp] = grade_spread(z.result.values[sp], z.point.values[sp], z.side.values[sp])
    if tt.any():
        v[tt] = grade_total(z.total.values[tt], z.point.values[tt], z.side.values[tt])
    z["v"] = v
    return z, miss


# ─── H1 ────────────────────────────────────────────────────────────────────

def h1_frame(sf, est):
    s0 = sf[(sf.qtr <= 4) & (sf.secs <= 600) & sf.spread_line.notna()]
    s = s0[~s0.over].copy()
    s = s.join(leader_view(s))
    s = s[(s.lead >= 4) & (s.lead <= 16)].copy()
    s["wp"] = wp_lookup(est, s.lead, s.ball, s.band, s.secs)
    s["vwp"] = np.where(s.lead_home, s.vwp_post, 1 - s.vwp_post)
    fin = np.where(s.lead_home, s.result, -s.result)
    s["v"] = np.where(fin > 0, 1.0, np.where(fin < 0, 0.0, 0.5))
    return s0, s


def h1(season, sf, q, est, tag="", fam="primary"):
    s0, s = h1_frame(sf, est)
    if not tag:
        print(f"H1: regulation snapshots with <= 600 s left {len(s0):,}; at/after the final play "
              f"(game over, excluded) {int(s0.over.sum()):,}")
    h = q[q.market == "h2h"].merge(s[KEYS + ["lead_home"]], on=KEYS)
    h["dec"] = np.where(h.lead_home, h.dec_h, h.dec_a)
    cols = KEYS + ["dec", "bookmaker"]
    pqs = {"DK": h[h.bookmaker == "draftkings"][cols], "best": best_by(h, KEYS)[cols],
           "median": median_by(h, KEYS)[cols]}
    rows = []
    for venue in VEN3:
        x = s.merge(pqs[venue], on=KEYS).sort_values(KEYS)
        x["imp"] = 1 / x.dec
        for ref in ("pbp", "nflverse"):
            x["edge"] = (x.wp if ref == "pbp" else x.vwp) - x.imp
            for S in H1_WINDOWS:
                for c in H1_CUTS:
                    e = x[(x.secs <= S) & (x.edge >= c)].groupby("game_id", as_index=False).head(1)
                    e = e.assign(market="h2h", side=np.where(e.lead_home, "home", "away"))
                    rows.append(cell(e, season, "H1", f"{tag}leader ref={ref} secs<={S} edge>={c:.2f}",
                                     venue, fam=fam, ml=True, extra={"ref": ref, "S": S, "cut": c}))
                    if venue == "best" and not tag and S == 600 and c in (0.02, 0.06):
                        P.async_check(e, h, f"H1 best ref={ref} secs<=600 edge>={c:.2f}")
    return rows


def h1_calibration(season, sf, q, est):
    _, s = h1_frame(sf, est)
    hh = q[(q.market == "h2h") & (q.bookmaker == "draftkings")][KEYS + ["price_home", "price_away",
                                                                         "dec_h", "dec_a"]]
    x = s.merge(hh, on=KEYS)
    ph, pa = devig2(x.price_home.values, x.price_away.values)
    x["dk_fair"] = np.where(x.lead_home, ph, pa)
    x["imp"] = 1 / np.where(x.lead_home, x.dec_h, x.dec_a)
    print(f"\nH1 CALIBRATION, every {season} snapshot with <= 600 s left and the leader up 4-16 (DK "
          f"quoted). Means; 'realised' = leader win share (tie 0.5); game-clustered CI on model - realised:")
    for lab, sub in (("<=600 s", x), ("<=300 s", x[x.secs <= 300])):
        m, lo, hi = boot(sub.wp - sub.v, sub.game_id)
        print(f"  {lab}: snapshots {len(sub):,}, games {sub.game_id.nunique()}, model WP {sub.wp.mean():.4f}, "
              f"nflverse {sub.vwp.mean():.4f}, DK fair {sub.dk_fair.mean():.4f}, DK implied (with vig) "
              f"{sub.imp.mean():.4f}, realised {sub.v.mean():.4f}; model - realised {m:+.4f} "
              f"[90% {lo:+.4f}, {hi:+.4f}]")
    for nm, col in (("model", "wp"), ("nflverse", "vwp"), ("DK fair", "dk_fair")):
        pp = np.clip(x[col].values, 1e-4, 1 - 1e-4)
        yv = x.v.values
        print(f"  {nm:9s} Brier {np.mean((pp - yv) ** 2):.5f}  log-loss "
              f"{-np.mean(yv * np.log(pp) + (1 - yv) * np.log(1 - pp)):.5f}")
    d = (np.clip(x.wp.values, 1e-4, 1 - 1e-4) - x.v.values) ** 2 - (x.dk_fair.values - x.v.values) ** 2
    m, lo, hi = boot(d, x.game_id.values)
    print(f"  Brier model minus DK fair, paired, game-clustered: {m:+.5f} [90% {lo:+.5f}, {hi:+.5f}]")


# ─── H2 / H3 ───────────────────────────────────────────────────────────────

def tot_offers(q, ws):
    m = line_quotes(q, "totals", ws).dropna(subset=["point"])
    dk = m[m.bookmaker == "draftkings"][KEYS + ["point", "dec_h", "dec_a"]]
    o, u = m.assign(dec=m.dec_h), m.assign(dec=m.dec_a)
    c = KEYS + ["point", "dec"]
    off = {"best": (best_by(o, KEYS, "point", line_high=False)[c], best_by(u, KEYS, "point", line_high=True)[c]),
           "median": (median_by(o, KEYS, "point", line_high=False)[c],
                      median_by(u, KEYS, "point", line_high=True)[c])}
    return dk, off


def spr_offers(q, ws):
    m = line_quotes(q, "spreads", ws).dropna(subset=["point"])
    dk = m[m.bookmaker == "draftkings"][KEYS + ["point", "dec_h", "dec_a"]]
    hh, aa = m.assign(dec=m.dec_h), m.assign(dec=m.dec_a)
    c = KEYS + ["point", "dec"]
    off = {"best": (best_by(hh, KEYS, "point", line_high=True)[c], best_by(aa, KEYS, "point", line_high=False)[c]),
           "median": (median_by(hh, KEYS, "point", line_high=True)[c],
                      median_by(aa, KEYS, "point", line_high=False)[c])}
    return dk, off


def h2(season, sf, st, q, btw, tag="", fam="primary", lag_s=0):
    W = window_snaps(sf, st, lag_s)
    rows, keep = [], {}
    for w in WINDOWS:
        ws = W[w].dropna(subset=["total_line", "home_sc"]).copy()
        ws["F"] = ws.home_sc + ws.away_sc + x_total(ws) @ btw[w]
        dk, off = tot_offers(q, ws)
        keep[w] = (ws, dk, off)
        for venue in VEN3:
            bA, bB = off.get(venue, (None, None))
            for c in H2_CUTS:
                b = two_sided_bets(ws, dk, bA, bB, lambda x, L: x.F - L, lambda x, L: L - x.F,
                                   "over", "under", c, venue,
                                   lambda b, L, s: grade_total(b.total.values, L, s))
                b = b.assign(market="totals")
                rows.append(cell(b, season, "H2", f"{tag}totals {w} |F-line|>={c}", venue, fam=fam,
                                 extra={"window": w, "cut": c,
                                        "overs": int((b.side == "over").sum()) if len(b) else 0}))
    return rows, keep


def h2_accuracy(season, keep):
    print(f"\nH2 ACCURACY at the window snapshots, {season} (out of sample): final total minus the "
          f"model's F and minus DK's live total")
    for w in WINDOWS:
        ws, dk, _ = keep[w]
        x = ws.merge(dk, on=KEYS)
        em, ek = x.total - x.F, x.total - x.point
        print(f"  {w}: games {len(x)}, model mean err {em.mean():+.2f} RMSE {np.sqrt((em ** 2).mean()):.2f}"
              f" | DK mean err {ek.mean():+.2f} RMSE {np.sqrt((ek ** 2).mean()):.2f} | model - DK line: "
              f"mean {(x.F - x.point).mean():+.2f}, SD {(x.F - x.point).std():.2f}")


def h3(season, sf, st, q, bmw, tag="", fam="primary", lag_s=0):
    W = window_snaps(sf, st, lag_s)
    rows, keep = [], {}
    for w in WINDOWS:
        ws = W[w].dropna(subset=["spread_line", "home_sc"]).copy()
        ws["M"] = ws.home_sc - ws.away_sc + x_margin(ws) @ bmw[w]
        dk, off = spr_offers(q, ws)
        keep[w] = (ws, dk)
        for venue in VEN3:
            bA, bB = off.get(venue, (None, None))
            for c in H3_CUTS:
                b = two_sided_bets(ws, dk, bA, bB, lambda x, Pt: x.M + Pt, lambda x, Pt: -(x.M + Pt),
                                   "home", "away", c, venue,
                                   lambda b, Pt, s: grade_spread(b.result.values, Pt, s))
                b = b.assign(market="spreads")
                rows.append(cell(b, season, "H3", f"{tag}spread {w} |M+point|>={c}", venue, fam=fam,
                                 extra={"window": w, "cut": c}))
    return rows, keep


def h3_accuracy(season, keep):
    print(f"\nH3 ACCURACY at the window snapshots, {season}: final margin minus the model's M and minus "
          f"DK's implied margin (-point)")
    for w in WINDOWS:
        ws, dk = keep[w]
        x = ws.merge(dk, on=KEYS)
        em, ek = x.result - x.M, x.result + x.point
        print(f"  {w}: games {len(x)}, model mean err {em.mean():+.2f} RMSE {np.sqrt((em ** 2).mean()):.2f}"
              f" | DK mean err {ek.mean():+.2f} RMSE {np.sqrt((ek ** 2).mean()):.2f} | model - DK: mean "
              f"{(x.M + x.point).mean():+.2f}, SD {(x.M + x.point).std():.2f}")


# ─── H4 ────────────────────────────────────────────────────────────────────

def wind_frame(season, g):
    from zoneinfo import ZoneInfo
    x = g[g.season == season].copy()
    out_roof = x.roof.isin(["outdoors", "open"])
    x["wind_nv"] = np.where(out_roof & (x.wind <= WIND_MAX_VALID), x.wind, np.nan)
    dt = pd.to_datetime(x.gameday + " " + x.gametime.fillna("13:00"), errors="coerce")
    x["hr"] = dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                nonexistent="shift_forward").dt.tz_convert("UTC").dt.floor("h")
    e = pd.read_parquet(CACHE / "era5_kick_1999_2025.parquet")
    e["ts"] = e.ts.astype("datetime64[us, UTC]")
    x["hr"] = x.hr.astype("datetime64[us, UTC]")
    x = x.merge(e[["stadium_id", "ts", "era5_wind"]].rename(columns={"ts": "hr"}),
                on=["stadium_id", "hr"], how="left")
    x["wind_era5"] = np.where(x.roof.isin(["outdoors", "open"]) & (x.location == "Home"), x.era5_wind, np.nan)
    both = x[["wind_nv", "wind_era5"]].dropna()
    print(f"\nH4 wind: {season} open-air games {int(out_roof.sum())}; nflverse wind "
          f"{int(x.wind_nv.notna().sum())}, ERA5 {int(x.wind_era5.notna().sum())}, both {len(both)}; corr "
          f"{both.corr().iloc[0, 1]:.2f}; mean nflverse {both.wind_nv.mean():.1f} vs ERA5 "
          f"{both.wind_era5.mean():.1f} mph")
    for src in ("wind_nv", "wind_era5"):
        print(f"  {src}: games >= 12 {int((x[src] >= 12).sum())}, >= 15 {int((x[src] >= 15).sum())}, "
              f">= 18 {int((x[src] >= 18).sum())}, calm < {CALM_LT} {int((x[src] < CALM_LT).sum())}")
    return x[["game_id", "wind_nv", "wind_era5"]]


def pregame_totals(season):
    o = odds_hist(["totals"])
    o = o[(o.season == season) & o.bookmaker.isin(VENUES) & (o.lead_hours >= 0)].dropna(
        subset=["point", "price_home", "price_away"])
    o = o.sort_values("snapshot_at").groupby(["game_id", "bookmaker"]).tail(1).copy()
    o["dec_h"] = am_to_dec(o.price_home.values)
    o["dec_a"] = am_to_dec(o.price_away.values)
    o["dec"] = o.dec_a
    c = ["game_id", "point", "dec"]
    dk = o[o.bookmaker == "draftkings"][c]
    bu = best_by(o, ["game_id"], "point", line_high=True)[c]
    mu = median_by(o, ["game_id"], "point", line_high=True)
    print(f"pre-game totals {season}: games with a pre-kick venue quote {o.game_id.nunique()}; lead hours "
          f"of the last DK snapshot: "
          f"{o[o.bookmaker == 'draftkings'].lead_hours.quantile([.1, .5, .9]).round(2).to_dict()}; "
          f"venues per game {o.groupby('game_id').bookmaker.nunique().value_counts().sort_index().to_dict()}")
    pre_med = mu[["game_id", "point", "dec", "bookmaker"]].assign(side="under")
    return dk, bu, mu[c], pre_med


def h4(season, keep2, g, wf, pre):
    ws, dk, off = keep2["endQ1"]
    pdk, pbu, pmu, _ = pre
    base = g[g.season == season][["game_id", "week", "total", "result"]].merge(wf, on="game_id")
    lv = {"DK": ws.merge(dk, on=KEYS)[["game_id", "snapshot_at", "point", "dec_a", "F"]]
          .rename(columns={"dec_a": "dec"}),
          "best": ws.merge(off["best"][1], on=KEYS)[["game_id", "snapshot_at", "point", "dec", "F"]],
          "median": ws.merge(off["median"][1], on=KEYS)[["game_id", "snapshot_at", "point", "dec", "F"]]}
    pg = {"DK": pdk, "best": pbu, "median": pmu}
    rows = []
    for src in ("wind_nv", "wind_era5"):
        sets = [(f">={T}", base[base[src] >= T]) for T in WIND_T] + \
               [(f"PLACEBO calm<{CALM_LT}", base[base[src] < CALM_LT])]
        for lab, gs in sets:
            for venue in VEN3:
                for when, src_tab in (("live endQ1", lv[venue]), ("pre-kick", pg[venue])):
                    b = gs.merge(src_tab, on="game_id")
                    b["v"] = grade_total(b.total.values, b.point.values, np.array(["under"] * len(b)))
                    b = b.assign(market="totals", side="under")
                    rows.append(cell(b, season, "H4", f"{when} UNDER {src} {lab}", venue,
                                     extra={"src": src, "set": lab, "when": when}))
    x = base.merge(lv["DK"], on="game_id").merge(pdk.rename(columns={"point": "pre_pt", "dec": "pre_dec"}),
                                                 on="game_id")
    print(f"\nH4 context {season}, DK, games with both a live endQ1 and a pre-kick total:")
    for src in ("wind_nv", "wind_era5"):
        for lab, m in ((">=15", x[src] >= 15), (">=12", x[src] >= 12), (f"<{CALM_LT}", x[src] < CALM_LT)):
            z = x[m]
            if len(z) == 0:
                continue
            print(f"  {src} {lab}: games {len(z)}, pre-kick total {z.pre_pt.mean():.1f}, live endQ1 total "
                  f"{z.point.mean():.1f}, final {z.total.mean():.1f}; final - pre-kick "
                  f"{(z.total - z.pre_pt).mean():+.1f}; final - live {(z.total - z.point).mean():+.1f}; "
                  f"windless model F - live {(z.F - z.point).mean():+.2f}")
    return rows


# ─── H5 ────────────────────────────────────────────────────────────────────

def h5(season, sf, st, q, bt):
    ev = st[st.nonoff_td & (st.qtr <= 4)][["game_id", "t_known", "qtr", "play_type", "week"]].rename(
        columns={"t_known": "t_td"})
    s = sf[["game_id", "snapshot_at", "qtr", "secs", "home_sc", "away_sc", "home_ball", "total_line",
            "total", "week", "over"]].dropna(subset=["home_sc", "total_line"]).copy()
    s["F"] = s.home_sc + s.away_sc + x_total(s) @ bt
    s["pts"] = s.home_sc + s.away_sc
    tq = q[q.market == "totals"].dropna(subset=["point"])
    dkt = tq[tq.bookmaker == "draftkings"][KEYS + ["point"]].rename(columns={"point": "dk_pt"})
    med = tq.groupby(KEYS).point.median().rename("med_pt").reset_index()
    s = s.merge(dkt, on=KEYS, how="left").merge(med, on=KEYS, how="left")
    min_s = pd.Timedelta(seconds=H5_POST_MIN_S if FIXES else 0)
    rows_ev, n_inside = [], 0
    for r in ev.itertuples():
        z = s[s.game_id == r.game_id]
        pre = z[z.snapshot_at < r.t_td].tail(1)
        n_inside += int(((z.snapshot_at >= r.t_td) & (z.snapshot_at < r.t_td + min_s)).sum())
        post = z[z.snapshot_at >= r.t_td + min_s].head(1)
        if len(pre) == 0 or len(post) == 0:
            continue
        a, b = pre.iloc[0], post.iloc[0]
        rows_ev.append({"game_id": r.game_id, "week": r.week, "play_type": r.play_type,
                        "snapshot_at": b.snapshot_at, "post_qtr": b.qtr, "post_over": b.over,
                        "dpts": b.pts - a.pts, "mkt_dk": b.dk_pt - a.dk_pt, "mkt_med": b.med_pt - a.med_pt,
                        "model": b.F - a.F, "secs_after": (b.snapshot_at - r.t_td).total_seconds()})
    e = pd.DataFrame(rows_ev)
    clean = e[(e.dpts - 6).isin([0, 1, 2]) & (e.post_qtr <= 4) & ~e.post_over.astype(bool)].copy()
    clean["excess_dk"] = clean.mkt_dk - clean.model
    print(f"\nH5 {season}: non-offensive TDs in regulation {len(ev)}; snapshots dropped for being served "
          f"< {int(min_s.total_seconds())} s after the TD ended {n_inside}; with a snapshot on both sides "
          f"{len(e)}; clean (only the TD and its try between the two states, post state in regulation) "
          f"{len(clean)}; seconds from TD end to the post snapshot q10/q50/q90 "
          f"{clean.secs_after.quantile([.1, .5, .9]).round(0).tolist() if len(clean) else []}")
    if len(clean):
        m, lo, hi = boot(clean.excess_dk.dropna(), clean.dropna(subset=["excess_dk"]).game_id)
        print(f"  market move DK mean {clean.mkt_dk.mean():+.2f}, venue-median line move "
              f"{clean.mkt_med.mean():+.2f}; model move mean {clean.model.mean():+.2f}; DK excess (market - "
              f"model) mean {clean.excess_dk.mean():+.2f} [90% {lo:+.2f}, {hi:+.2f}], share > 0 "
              f"{100 * (clean.excess_dk > 0).mean():.0f}%; games with 2+ events {int((clean.game_id.value_counts() > 1).sum())}")
    ws = clean.merge(s[KEYS + ["total"]], on=KEYS).drop_duplicates(KEYS)
    dk, off = tot_offers(q, ws)
    rows = []
    for venue in VEN3:
        if venue == "DK":
            xo = ws.merge(dk, on=KEYS).assign(dec=lambda d_: d_.dec_h)
            xu = ws.merge(dk, on=KEYS).assign(dec=lambda d_: d_.dec_a)
        else:
            xo = ws.merge(off[venue][0], on=KEYS)
            xu = ws.merge(off[venue][1], on=KEYS)
        for lab, x, side, m in (("UNDER every event", xu, "under", None),
                                ("OVER every event", xo, "over", None),
                                ("UNDER when market move > model move", xu, "under", "pos"),
                                ("OVER when market move < model move", xo, "over", "neg")):
            b = x.copy()
            if m == "pos":
                b = b[b.excess_dk > 0]
            elif m == "neg":
                b = b[b.excess_dk < 0]
            b["v"] = grade_total(b.total.values, b.point.values, np.array([side] * len(b)))
            b = b.assign(market="totals", side=side)
            rows.append(cell(b, season, "H5", lab, venue))
    return rows


# ─── H6 ────────────────────────────────────────────────────────────────────

def h6(season, sf, q):
    s = sf[sf.snapshot_at >= sf.commence_time + pd.Timedelta(minutes=30)]
    s = s.sort_values(KEYS).groupby("game_id", as_index=False).head(1)
    rows = []
    m = q.merge(s[KEYS + ["total", "result"]], on=KEYS)
    sp = m[m.market == "spreads"].dropna(subset=["point"])
    ref_pt = sp[sp.bookmaker == "draftkings"].set_index("game_id").point
    ref_pt = ref_pt.combine_first(sp.groupby("game_id").point.median())
    ml = m[m.market == "h2h"]
    ref_ml = ml[ml.bookmaker == "draftkings"].set_index("game_id").eval("dec_h - dec_a")
    ref_ml = ref_ml.combine_first(ml.groupby("game_id").apply(lambda z: (z.dec_h - z.dec_a).median(),
                                                               include_groups=False))
    tt = m[m.market == "totals"].dropna(subset=["point"])
    for venue in VEN3:
        src = (lambda z: z[z.bookmaker == "draftkings"]) if venue == "DK" else (lambda z: z)
        pick = {"best": best_by, "median": median_by}.get(venue)
        for side in ("under", "over"):
            z = src(tt).assign(dec=lambda d_: d_.dec_a if side == "under" else d_.dec_h)
            if pick is not None:
                z = pick(z, ["game_id"], "point", line_high=(side == "under"))
            z = z.copy()
            z["v"] = grade_total(z.total.values, z.point.values, np.array([side] * len(z)))
            z["side"] = side
            rows.append(cell(z, season, "H6", f"kick+30m totals {side.upper()}", venue))
        z = src(sp).copy()
        z["fav_home"] = z.game_id.map(ref_pt) < 0
        z = z[z.game_id.map(ref_pt) != 0]
        for who in ("FAV", "DOG"):
            home_side = z.fav_home if who == "FAV" else ~z.fav_home
            y = z.assign(side=np.where(home_side, "home", "away"), dec=np.where(home_side, z.dec_h, z.dec_a),
                         line=np.where(home_side, z.point, -z.point))
            if pick is not None:
                y = pick(y, ["game_id"], "line", line_high=True)
            y = y.copy()
            y["v"] = grade_spread(y.result.values, y.point.values, y.side.values)
            rows.append(cell(y, season, "H6", f"kick+30m spread {who}", venue))
        z = src(ml).copy()
        z["fav_home"] = z.game_id.map(ref_ml) < 0
        z = z[z.game_id.map(ref_ml) != 0]
        for who in ("FAV", "DOG"):
            home_side = z.fav_home if who == "FAV" else ~z.fav_home
            y = z.assign(home=home_side, dec=np.where(home_side, z.dec_h, z.dec_a))
            if pick is not None:
                y = pick(y, ["game_id"])
            y = y.copy()
            fin = np.where(y.home, y.result, -y.result)
            y["v"] = np.where(fin > 0, 1.0, np.where(fin < 0, 0.0, 0.5))
            y["side"] = np.where(y.home, "home", "away")
            rows.append(cell(y, season, "H6", f"kick+30m moneyline {who}", venue, ml=True))
    return rows, s


def hold_table(season, q, sf, h6_snaps):
    z = q.merge(sf[KEYS + ["qtr", "over"]], on=KEYS)
    z = z[(z.qtr <= 4) & ~z.over.astype(bool)].copy()
    z["ovr"] = 1 / z.dec_h + 1 / z.dec_a - 1
    t = z.groupby(["bookmaker", "market"]).ovr.mean().unstack().round(4)
    h = z.merge(h6_snaps[KEYS], on=KEYS)
    t6 = h.groupby(["bookmaker", "market"]).ovr.mean().unstack().round(4)
    o = odds_hist(["h2h", "spreads", "totals"])
    o = o[(o.season == season) & o.bookmaker.isin(VENUES) & (o.lead_hours >= 0)]
    o = o.sort_values("snapshot_at").groupby(["game_id", "bookmaker", "market"]).tail(1)
    o["ovr"] = 1 / am_to_dec(o.price_home.values) + 1 / am_to_dec(o.price_away.values) - 1
    tp = o.groupby(["bookmaker", "market"]).ovr.mean().unstack().round(4)
    print(f"\nLIVE HOLD {season} (mean overround = sum of implied probs - 1), every regulation in-play "
          f"snapshot before the final play, by book x market:")
    print(t.to_string())
    print(f"LIVE HOLD {season} at the H6 snapshot (kickoff + 30 min):")
    print(t6.to_string())
    print(f"PRE-GAME HOLD {season}, last pre-kick snapshot (odds_hist):")
    print(tp.to_string())
    HOLD[season] = {"live_all": t.loc["draftkings"].to_dict() if "draftkings" in t.index else {},
                    "live_k30": t6.loc["draftkings"].to_dict() if "draftkings" in t6.index else {},
                    "pregame": tp.loc["draftkings"].to_dict() if "draftkings" in tp.index else {}}


# ─── lagging-book (cross-book latency) construction ───────────────────────

def lagbook_groups(q, sf):
    # q already carries week (in-play file) and home_sc / away_sc (venue_quotes)
    z = q.merge(sf[KEYS + ["qtr", "over", "result", "total"]], on=KEYS)
    z = z[(z.qtr <= 4) & ~z.over.astype(bool)].dropna(subset=["dec_h", "dec_a"]).copy()
    z["imp_h"] = 1 / z.dec_h
    z["imp_a"] = 1 / z.dec_a
    out = []
    for m in ("h2h", "spreads", "totals"):
        y = z[z.market == m].copy()
        if m == "h2h":
            y["point"] = 0.0
        else:
            y = y.dropna(subset=["point"])
        gk = KEYS + ["point"]
        g = y.groupby(gk, sort=False)
        a = g.agg(n=("bookmaker", "size"), med_h=("imp_h", "median"), med_a=("imp_a", "median"),
                  best_h=("imp_h", "min"), best_a=("imp_a", "min"), week=("week", "first"),
                  result=("result", "first"), total=("total", "first"), home_sc=("home_sc", "first"),
                  away_sc=("away_sc", "first"))
        ih = y.loc[g.imp_h.idxmin().values, gk + ["bookmaker", "dec_h"]].set_index(gk) \
            .rename(columns={"bookmaker": "book_h"})
        ia = y.loc[g.imp_a.idxmin().values, gk + ["bookmaker", "dec_a"]].set_index(gk) \
            .rename(columns={"bookmaker": "book_a"})
        a = a.join(ih).join(ia)
        a = a[a.n >= LB_MIN_BOOKS].reset_index()
        a["gap_h"] = a.med_h - a.best_h
        a["gap_a"] = a.med_a - a.best_a
        a["market"] = m
        if m == "h2h":
            a["point"] = np.nan
        out.append(a)
    return pd.concat(out, ignore_index=True)


def lagbook_bets(c, thr):
    th, ta = c.gap_h >= thr, c.gap_a >= thr
    sh = th & (c.gap_h > c.gap_a)
    sa = ta & (c.gap_a > c.gap_h)
    b = c[sh | sa].copy()
    sh = sh[sh | sa].values
    sideA = np.where(b.market == "totals", "over", "home")
    sideB = np.where(b.market == "totals", "under", "away")
    b["side"] = np.where(sh, sideA, sideB)
    b["gap"] = np.where(sh, b.gap_h, b.gap_a)
    b["dec"] = np.where(sh, b.dec_h, b.dec_a)
    b["book"] = np.where(sh, b.book_h, b.book_a)
    b["med_imp"] = np.where(sh, b.med_h, b.med_a)
    b["fair"] = b.med_imp / (b.med_h + b.med_a)
    b = b.sort_values(KEYS + ["market", "gap"], ascending=[True, True, True, False]) \
        .groupby(KEYS + ["market"], as_index=False).head(1).copy()
    v = np.full(len(b), np.nan)
    mk = b.market.values
    hm = mk == "h2h"
    fin = np.where(b.side.values == "home", b.result.values, -b.result.values)
    v[hm] = np.where(fin > 0, 1.0, np.where(fin < 0, 0.0, 0.5))[hm]
    sp = mk == "spreads"
    v[sp] = grade_spread(b.result.values[sp], b.point.values[sp], b.side.values[sp])
    tt = mk == "totals"
    v[tt] = grade_total(b.total.values[tt], b.point.values[tt], b.side.values[tt])
    b["v"] = v
    b["dec_med"] = 1 / b.med_imp
    return b.sort_values(KEYS)


def lagbook_catchup(first_h2h, q, sf):
    """h2h first entries whose score did not change before the next snapshot:
    did the outlier book move to the others, or the others to it?"""
    nx = sf[KEYS + ["home_sc", "away_sc"]].sort_values(KEYS).copy()
    nx["next_at"] = nx.groupby("game_id").snapshot_at.shift(-1)
    nx["nh"] = nx.groupby("game_id").home_sc.shift(-1)
    nx["na"] = nx.groupby("game_id").away_sc.shift(-1)
    e = first_h2h.merge(nx[KEYS + ["next_at", "nh", "na"]], on=KEYS)
    e = e[(e.nh == e.home_sc) & (e.na == e.away_sc) & e.next_at.notna()].copy()
    h = q[q.market == "h2h"][KEYS + ["bookmaker", "dec_h", "dec_a"]].copy()
    h["imp_h"], h["imp_a"] = 1 / h.dec_h, 1 / h.dec_a
    hb = h.rename(columns={"snapshot_at": "next_at", "bookmaker": "book"})
    e = e.merge(hb[["game_id", "next_at", "book", "imp_h", "imp_a"]].rename(
        columns={"imp_h": "o_h", "imp_a": "o_a"}), on=["game_id", "next_at", "book"])
    mm = h.groupby(KEYS)[["imp_h", "imp_a"]].median().reset_index().rename(
        columns={"snapshot_at": "next_at", "imp_h": "m_h", "imp_a": "m_a"})
    e = e.merge(mm, on=["game_id", "next_at"])
    if len(e) == 0:
        return "no h2h entries with an unchanged score and a next quote"
    home = e.side.values == "home"
    out_now = e.med_imp - e.gap
    out_next = np.where(home, e.o_h, e.o_a)
    med_next = np.where(home, e.m_h, e.m_a)
    d_out, d_med = out_next - out_now, med_next - e.med_imp
    gap_next = med_next - out_next
    toward = np.abs(d_out) > np.abs(d_med)
    return (f"{len(e)} h2h entries with the score unchanged until the next snapshot: outlier book's "
            f"implied prob moved {np.mean(d_out):+.4f} on average, the median of all books "
            f"{np.mean(d_med):+.4f}; gap at the next snapshot {np.mean(gap_next):+.4f} (was "
            f"{e.gap.mean():+.4f}); gap closed below 0.01 in {100 * np.mean(gap_next < 0.01):.0f}%; the "
            f"outlier moved more than the median in {100 * np.mean(toward):.0f}%")


def lagbook(season, q, sf):
    c = lagbook_groups(q, sf)
    print(f"\n=== LAGGING-BOOK (CROSS-BOOK LATENCY) {season}: a stale-book effect, NOT a model ===")
    print(f"groups (snapshot x market x line) with >= {LB_MIN_BOOKS} bettable books: "
          f"{c.groupby('market').size().to_dict()}; median gap best vs median (home/over side) "
          f"{c.groupby('market').gap_h.median().round(4).to_dict()}")
    rows = []
    for thr in LB_GAPS:
        b = lagbook_bets(c, thr)
        first = b.sort_values(KEYS).groupby(["game_id", "market"], as_index=False).head(1)
        for reading, bb in (("first per game x market", first), ("every qualifying snapshot", b)):
            for mk in ("h2h", "spreads", "totals", "all"):
                z = bb if mk == "all" else bb[bb.market == mk]
                with_p = reading.startswith("first") and mk != "all"
                r = {"season": season, "construction": "lagging-book", "reading": reading, "market": mk,
                     "gap_min": thr}
                r.update(summ(z, halves=False, with_p=with_p))
                if len(z):
                    pm = profit_of(z.v.values, z.dec_med.values)
                    r["med_units"] = round(pm.sum(), 2)
                    r["med_roi"] = round(100 * pm.mean(), 1)
                    r["consensus_exp_roi"] = round(100 * float((z.fair * z.dec - 1).mean()), 1)
                    r["avg_gap"] = round(float(z.gap.mean()), 4)
                    r["books"] = z.book.value_counts().to_dict()
                    r["bets_per_game_max"] = int(z.groupby("game_id").size().max())
                rows.append(r)
                LB_ROWS.append(r)
        if thr == 0.03:
            print("  catch-up, gap >= .03, first per game:", lagbook_catchup(first[first.market == "h2h"], q, sf))
    t = pd.DataFrame(rows)
    cols = ["reading", "market", "gap_min", "bets", "games", "units", "roi", "lo", "hi", "p", "win", "push",
            "avg_dec", "avg_gap", "consensus_exp_roi", "med_units", "med_roi", "bets_per_game_max"]
    print(t[[c_ for c_ in cols if c_ in t.columns]].to_string(index=False))
    print("outlier book counts (first per game x market, all markets):")
    for r in rows:
        if r["reading"].startswith("first") and r["market"] == "all":
            print(f"  gap >= {r['gap_min']:.2f}: {r.get('books')}")


# ─── season run ────────────────────────────────────────────────────────────

def fit_models(tr_all, season):
    tr = tr_all[tr_all.season < season]
    yrs = sorted(int(s) for s in tr.season.unique())
    gid_years = tr.game_id.str[:4].astype(int)
    print(f"\n=== FIT FOR GRADING {season}: training seasons {yrs}; training states {len(tr):,}; games "
          f"{tr.game_id.nunique():,}; latest game-id season {int(gid_years.max())}; game ids starting "
          f"'{season}_': {int(tr.game_id.str.startswith(f'{season}_').sum())} ===")
    print("refit: H1 13 per-lead logistic WP regressions; H2 4 per-window totals least squares; H3 4 "
          "per-window margin least squares; H5 the pooled totals least squares. Nothing else is fitted.")
    buf = io.StringIO()
    with redirect_stdout(buf):
        check_possession(tr)
        est = fit_wp(tr)
        bt, bm, btw, bmw = fit_totals_margin(tr)
    print(buf.getvalue().replace("2016-2024", f"{yrs[0]}-{yrs[-1]}"))
    return est, bt, bm, btw, bmw


def books_per_snapshot(q, sf):
    z = q.merge(sf[KEYS + ["qtr", "over"]], on=KEYS)
    z = z[(z.qtr <= 4) & ~z.over.astype(bool)]
    for m in ("h2h", "spreads", "totals"):
        n = z[z.market == m].groupby(KEYS).bookmaker.nunique()
        print(f"  bettable books per in-play regulation snapshot, {m}: {n.value_counts().sort_index().to_dict()}")
    print(f"  bettable rows by book: {z.bookmaker.value_counts().to_dict()}")


def run_season(season, fit, g, robust=True):
    est, bt, bm, btw, bmw = fit
    print(f"\n\n{'#' * 100}\n# SEASON {season}: graded with the fit printed above for {season}; fixes "
          f"{'ON' if FIXES else 'OFF (original 2025 rules)'}\n{'#' * 100}")
    d = load_inplay(season, g)
    print(f"in-play rows {len(d):,}, games {d.game_id.nunique()}, price NaN rows "
          f"{int(d.price_home.isna().sum() + d.price_away.isna().sum())}")
    st, st_old = states(season, g)
    sf = snapshot_frame(d, g, st, 0)
    if st_old is not None:
        so = snapshot_frame(d, g, st_old, 0)
        k = ["home_sc", "away_sc", "qtr", "secs", "home_ball"]
        a = sf.set_index(KEYS)[k]
        b = so.set_index(KEYS)[k].reindex(a.index)
        diff = ~((a == b) | (a.isna() & b.isna())).all(axis=1)
        print(f"FIX (1) effect: snapshots whose attached state differs from the +5 s rule: {int(diff.sum())} of "
              f"{len(a):,}; of them with a score difference "
              f"{int(((a.home_sc != b.home_sc) | (a.away_sc != b.away_sc))[diff].sum())}")
        ov_old = (sf.t_state - pd.Timedelta(seconds=LAG_S) >= sf.t_final)
        print(f"FIX (2) effect (60 s lag cells only): snapshots served within 60 s after the final play, "
              f"now 'over' in the lagged frame: {int(((sf.snapshot_at >= sf.t_final) & ~ov_old).sum())}")
    sf_lag = snapshot_frame(d, g, st, LAG_S) if robust else None
    q = venue_quotes(d, sf)
    q_fresh = venue_quotes(d, sf, stale_filter=True) if robust else None
    books_per_snapshot(q, sf)
    if robust:
        P.diagnostics(d, sf, st, q, g)
        P.dispersion(q, sf)
    med_tab = median_table(q)

    print(f"\n=== H1 {season}: late-game leader, live moneyline vs the out-of-sample WP model ===")
    r1 = h1(season, sf, q, est)
    show(r1, f"H1 cells {season}", extra_cols=["cp_lo", "cp_hi", "avg_edge"])
    if robust:
        h1_calibration(season, sf, q, est)
        rr = h1(season, sf_lag, q, est, tag="LAG60 ", fam="robust") + \
            h1(season, sf, q_fresh, est, tag="FRESH ", fam="robust")
        show(rr, f"H1 ROBUSTNESS {season} (not in BH): state lagged 60 s | stale quotes removed")

    print(f"\n=== H2 {season}: live totals vs the out-of-sample remaining-points model ===")
    W = window_snaps(sf, st)
    for k_ in WINDOWS:
        print(f"  {k_}: games {len(W[k_])}, secs {W[k_].secs.quantile([.1, .5, .9]).round(0).tolist()}")
    r2, keep2 = h2(season, sf, st, q, btw)
    h2_accuracy(season, keep2)
    show(r2, f"H2 cells {season}", extra_cols=["overs", "avg_edge"])
    if robust:
        rr = h2(season, sf_lag, st, q, btw, tag="LAG60 ", fam="robust", lag_s=LAG_S)[0] + \
            h2(season, sf, st, q_fresh, btw, tag="FRESH ", fam="robust")[0]
        show(rr, f"H2 ROBUSTNESS {season} (not in BH)")

    print(f"\n=== H3 {season}: live spread vs the out-of-sample margin model ===")
    r3, keep3 = h3(season, sf, st, q, bmw)
    h3_accuracy(season, keep3)
    show(r3, f"H3 cells {season}", extra_cols=["avg_edge"])
    if robust:
        rr = h3(season, sf_lag, st, q, bmw, tag="LAG60 ", fam="robust", lag_s=LAG_S)[0] + \
            h3(season, sf, st, q_fresh, bmw, tag="FRESH ", fam="robust")[0]
        show(rr, f"H3 ROBUSTNESS {season} (not in BH)")

    print(f"\n=== H4 {season}: in-play wind under ===")
    wf = wind_frame(season, g)
    pre = pregame_totals(season)
    r4 = h4(season, keep2, g, wf, pre)
    show(r4, f"H4 cells {season} (live = the endQ1 snapshot; pre-kick = last odds_hist snapshot)")

    print(f"\n=== H5 {season}: non-offensive touchdowns ===")
    r5 = h5(season, sf, st, q, bt)
    show(r5, f"H5 cells {season} (bet at the post-TD snapshot)")

    print(f"\n=== H6 {season}: broad null control ===")
    r6, s6 = h6(season, sf, q)
    show(r6, f"H6 cells {season} (first snapshot at/after kickoff + 30 min, every game)",
         extra_cols=["cp_lo", "cp_hi"])
    hold_table(season, q, sf, s6)

    # best entries re-graded at the median book (same bets)
    miss_tot = 0
    for key in [k_ for k_ in STORE if k_[0] == season and k_[1] == "primary" and k_[4] == "best"]:
        b = STORE[key]
        if len(b) == 0:
            cell(b, season, key[2], key[3], "best@median", fam="regrade", ml=key[2] in ML_HYPS)
            continue
        if key[2] == "H4" and key[3].startswith("pre-kick"):
            z, miss = regrade(b.drop(columns=["season"]), pre[3], ["game_id"])
        else:
            z, miss = regrade(b.drop(columns=["season"]), med_tab, KEYS + ["market"])
        miss_tot += miss
        cell(z, season, key[2], key[3], "best@median", fam="regrade",
             ml=(key[2] in ML_HYPS or "moneyline" in key[3]))
    print(f"\nbest-entry re-grade at the median book: bets with no median offer {miss_tot}")
    if robust:
        lagbook(season, q, sf)


# ─── tables across seasons ─────────────────────────────────────────────────

def fmt(r, short=False):
    if r is None or r.get("bets", 0) == 0:
        return "   0"
    if short:
        return f"{r['bets']:>3d} {r['units']:+7.2f}u {r['roi']:+6.1f}%"
    return (f"{r['bets']:>3d} {r['units']:+7.2f}u {r['roi']:+6.1f}% [{r['lo']:+6.1f},{r['hi']:+6.1f}] "
            f"p{r['p']:.3f}")


def row_of(season, fam, hyp, label, venue):
    for r in ROWS:
        if (r["season"], r["fam"], r["hyp"], r["cell"], r["venue"]) == (season, fam, hyp, label, venue):
            return r
    return None


def wide(season):
    defs = []
    for r in ROWS:
        if r["season"] == season and r["fam"] == "primary" and (r["hyp"], r["cell"]) not in defs:
            defs.append((r["hyp"], r["cell"]))
    out = []
    for hyp, lab in defs:
        out.append({"hyp": hyp, "cell": lab,
                    "DK": fmt(row_of(season, "primary", hyp, lab, "DK")),
                    "BEST": fmt(row_of(season, "primary", hyp, lab, "best")),
                    "MEDIAN venue": fmt(row_of(season, "primary", hyp, lab, "median")),
                    "best bets @ median": fmt(row_of(season, "regrade", hyp, lab, "best@median"), short=True)})
    print(f"\n=== {season}: ALL 66 DEFINITIONS x DK / BEST / MEDIAN BOOK (bets, units, ROI [90% CI by game], "
          f"one-sided p) ===")
    print(pd.DataFrame(out).to_string(index=False))


def pool_all():
    keys = []
    for k in STORE:
        if k[1] in ("primary", "regrade") and k[1:] not in keys:
            keys.append(k[1:])
    for fam, hyp, lab, venue in keys:
        parts = [STORE[(s, fam, hyp, lab, venue)] for s in (2024, 2025) if (s, fam, hyp, lab, venue) in STORE]
        if len(parts) < 2:
            continue
        b = pd.concat(parts, ignore_index=True)
        r = {"season": "pooled", "fam": fam, "hyp": hyp, "cell": lab, "venue": venue}
        r.update(summ(b, ml=(hyp in ML_HYPS or "moneyline" in lab)))
        ROWS.append(r)


def families(season):
    t = pd.DataFrame([r for r in ROWS if r["season"] == season])
    pr = t[t.fam == "primary"]
    fams = {"132 pre-registered (DK + best)": pr[pr.venue.isin(["DK", "best"])],
            "66 DK only": pr[pr.venue == "DK"],
            "66 best only": pr[pr.venue == "best"],
            "66 median-book venue (own entries)": pr[pr.venue == "median"],
            "132 DK + median-book venue": pr[pr.venue.isin(["DK", "median"])],
            "66 best entries re-graded at the median book (descriptive)": t[t.fam == "regrade"]}
    print(f"\n--- BH q=0.10 families, season {season} ---")
    surv = {}
    for name, f in fams.items():
        f = f.copy()
        f["bh"] = bh(f.p.values)
        print(f"  {name}: cells {len(f)}, with bets {int((f.bets > 0).sum())}, p<.05 {int((f.p < .05).sum())}, "
              f"p<.01 {int((f.p < .01).sum())}, smallest p {f.p.min():.4f} (rank-1 threshold "
              f"{0.10 / len(f):.5f}), BH survivors {int(f.bh.sum())}")
        if f.bh.any():
            print(f[f.bh][["hyp", "cell", "venue", "bets", "units", "roi", "lo", "hi", "p"]]
                  .to_string(index=False).replace("\n", "\n      "))
        sv = f[f.bh]
        surv[name] = list(zip(sv.hyp, sv.cell, sv.venue))
    f = fams["132 pre-registered (DK + best)"]
    print(f"  12 lowest-p cells of the 132, season {season}:")
    print(f[f.bets > 0].sort_values("p").head(12)[["hyp", "cell", "venue", "bets", "units", "roi", "lo", "hi",
                                                   "p", "e_roi", "l_roi"]].to_string(index=False))
    pos = f[(f.bets >= 30) & (f.lo > 0)]
    print(f"  cells of the 132 with >= 30 bets and the 90% CI lower bound above 0: {len(pos)} "
          f"({pos.venue.value_counts().to_dict()})")
    return surv


def pooled_table(surv):
    out = []
    for r in ROWS:
        if r["season"] != "pooled" or r["fam"] != "primary":
            continue
        k = (r["hyp"], r["cell"], r["venue"])
        a = row_of(2024, "primary", *k)
        b = row_of(2025, "primary", *k)
        flag = "BH" if any(k in v for v in surv.values()) else ""
        out.append({"hyp": r["hyp"], "cell": r["cell"], "venue": r["venue"], "2024": fmt(a, True),
                    "2025": fmt(b, True), "POOLED": fmt(r), "bh": flag})
    print("\n=== POOLED 2024 + 2025, by season (each season graded with its own out-of-sample fit; "
          "pooled CI clustered by game; 'BH' = survives some pooled family below) ===")
    print(pd.DataFrame(out).to_string(index=False))


# ─── replication ───────────────────────────────────────────────────────────

def parse_2025_output():
    path = CACHE / "inplay2025_out.txt"
    L = path.read_text(encoding="utf-8").splitlines()
    prim, hdr, out = False, None, []
    for s in (x.strip() for x in L):
        if re.match(r"^H[1-6] cells", s):
            prim, hdr = True, None
            continue
        if "ROBUSTNESS" in s or s.startswith("==="):
            prim = False
            continue
        if prim and s.startswith("hyp "):
            hdr = s.split()
            continue
        if prim and hdr and re.match(r"^H[1-6] ", s):
            toks = s.split()
            vi = [j for j, t in enumerate(toks) if t in ("DK", "best")][0]
            n = toks[vi + 1:]
            out.append({"hyp": toks[0], "cell": " ".join(toks[1:vi]), "venue": toks[vi], "bets": int(n[0]),
                        "units": float(n[1]), "roi": float(n[2]), "lo": float(n[3]), "hi": float(n[4]),
                        "p": float(n[7])})
    return out


def replication(orig):
    sel = sorted([o for o in orig if o["p"] < 0.10], key=lambda o: o["p"])
    print(f"\n=== REPLICATION: every 2025 primary cell with p < 0.10 in the 2025 output ({len(sel)} of "
          f"{len(orig)}), the same cell in 2024 ===")
    out, same, p10, n_sim = [], 0, 0, 0
    for o in sel:
        k = (o["hyp"], o["cell"], o["venue"])
        r25 = row_of(2025, "primary", *k)
        r24 = row_of(2024, "primary", *k)
        r24m = row_of(2024, "primary", o["hyp"], o["cell"], "median")
        r24bm = row_of(2024, "regrade", o["hyp"], o["cell"], "best@median") if o["venue"] == "best" else None
        sgn = (r24 is not None and r24["bets"] > 0 and np.sign(r24["roi"]) == np.sign(o["roi"]))
        same += int(sgn)
        p10 += int(r24 is not None and r24["p"] < 0.10)
        sim = sgn and r24["roi"] >= 0.5 * o["roi"]
        n_sim += int(sim)
        out.append({"hyp": o["hyp"], "cell": o["cell"], "venue": o["venue"],
                    "look-ahead": "nflverse WP" if "ref=nflverse" in o["cell"] else "",
                    "2025 original": f"{o['bets']:>3d} {o['units']:+6.2f}u {o['roi']:+6.1f}% p{o['p']:.3f}",
                    "2025 re-run (fixes)": fmt(r25, True) + (f" p{r25['p']:.3f}" if r25 and r25["bets"] else ""),
                    "2024 same cell": fmt(r24),
                    "2024 median venue": fmt(r24m, True),
                    "2024 best bets @ median": fmt(r24bm, True) if r24bm else "",
                    "same sign": "yes" if sgn else "no",
                    ">= half the size": "yes" if sim else "no"})
    print(pd.DataFrame(out).to_string(index=False))
    print(f"of {len(sel)}: same sign in 2024 {same}; at least half the 2025 ROI in 2024 {n_sim}; 2024 p < 0.10 "
          f"{p10} (about {0.10 * len(sel):.0f} expected by chance if none were real, cells are correlated)")


# ─── reproduction check ────────────────────────────────────────────────────

def repro_check(orig):
    bad = []
    for o in orig:
        r = row_of(2025, "primary", o["hyp"], o["cell"], o["venue"])
        if r is None or r["bets"] != o["bets"] or abs(r["units"] - o["units"]) > 0.011 or \
                (r["bets"] and abs(r["p"] - o["p"]) > 0.0001):
            bad.append((o, None if r is None else (r["bets"], r["units"], r["p"])))
    print(f"\n=== REPRODUCTION of the 2025 study (original rules, 2016-2024 fit): {len(orig) - len(bad)} of "
          f"{len(orig)} primary cells identical in bets, units and p ===")
    for o, r in bad:
        print("  MISMATCH", o["hyp"], o["cell"], o["venue"], "orig", (o["bets"], o["units"], o["p"]), "here", r)


# ─── main ──────────────────────────────────────────────────────────────────

def main():
    global FIXES
    repro = "--repro2025" in sys.argv
    FIXES = not repro
    src = Path(__file__).read_bytes()
    print(f"script md5 {hashlib.md5(src).hexdigest()}; mode {'REPRO 2025 (original rules)' if repro else 'FULL'}")
    g = games()
    orig = parse_2025_output()
    tr_all = attach_games(play_states(range(2016, 2025)), g)
    seasons = [2025] if repro else [2024, 2025]
    fits = {s: fit_models(tr_all, s) for s in seasons}
    del tr_all
    for s in seasons:
        run_season(s, fits[s], g, robust=not repro)
    if repro:
        repro_check(orig)
        return

    for s in seasons:
        wide(s)
    surv24 = families(2024)
    surv25 = families(2025)
    pool_all()
    survp = families("pooled")
    pooled_table(survp)
    replication(orig)

    print("\n=== LIVE HOLD AT DRAFTKINGS BY MARKET (mean overround) ===")
    for s in seasons:
        print(f"  {s}: every regulation in-play snapshot {HOLD[s]['live_all']}; at kickoff + 30 min "
              f"{HOLD[s]['live_k30']}; last pre-kick {HOLD[s]['pregame']}")

    print("\n=== LAGGING-BOOK, BOTH SEASONS (cross-book latency; first bet per game x market) ===")
    t = pd.DataFrame(LB_ROWS)
    t = t[t.reading.str.startswith("first")]
    print(t[["season", "market", "gap_min", "bets", "units", "roi", "lo", "hi", "p", "avg_gap",
             "consensus_exp_roi", "med_roi"]].to_string(index=False))

    print("\n=== ANSWER INPUTS ===")
    for nm, sv in (("2024", surv24), ("2025 re-run", surv25), ("pooled", survp)):
        print(f"  {nm}: BH survivors by family: " + "; ".join(f"{k}: {len(v)}" for k, v in sv.items()))

    pd.DataFrame(ROWS).to_csv(CACHE / "inplay_2024_cells.csv", index=False)
    pd.DataFrame(LB_ROWS).to_csv(CACHE / "inplay_2024_lagbook.csv", index=False)
    print(f"\nwrote {CACHE / 'inplay_2024_cells.csv'} ({len(ROWS)} rows) and "
          f"{CACHE / 'inplay_2024_lagbook.csv'} ({len(LB_ROWS)} rows)")


if __name__ == "__main__":
    main()

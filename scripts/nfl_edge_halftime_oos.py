"""
NFL halftime second-half lines, 2023-2025, at REAL bought prices: the first
out-of-sample read of the SBR study (scripts/nfl_edge_halftime.py).

    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_halftime_oos      (worktree root)

Reads ONLY the local cache (scripts/nfl_edge_lib.CACHE) and the repo's SBR
archive nfl/data/sbr_nfl.json (to replay the frozen 2011-16 fit). No database,
no Odds API call, no paid endpoint. Units: 1 unit = 1 flat bet. A 2H wager
includes overtime (US book convention): 2H margin = final margin - 1H margin.

CONSTRUCTION - written before any 2023-25 second-half outcome was read
=====================================================================

Lines (h2_2023_2025.parquet, the bought Odds API spreads_h2 / totals_h2)
  * spreads_h2 `point` = the HOME team's 2H handicap (home covers when
    2H margin + point > 0); totals_h2 `point` = the 2H total; price_home /
    price_away = home/away (spreads) or over/under (totals), American.
  * Bettable books = scripts.nfl_edge_lib.BETTABLE present in the file:
    draftkings, fanduel, williamhill_us. Bovada is a reference, not a venue
    (lib comment): shown in coverage only, never graded.
  * Halftime window per game from nflverse pbp time_of_day:
    open  = latest Q1-Q2 row time + 60 s;  close = first Q3 row time (the
    third-quarter kickoff). DECISION quote = per game x market x book the LAST
    snapshot with open <= snapshot_at < close. ROBUSTNESS quote = the FIRST
    snapshot in the same window. A book with no snapshot in the window is
    absent for that game: a Q2 quote is never carried forward (it does not know
    the final 1H score the rule states use), a post-kickoff quote is in-play.
  * Quote screen: a quote whose two implied probabilities sum to < 1.00 or
    > 1.15 is dropped (printed).
  * Modal line = the most common decision point across the bettable books
    present; a tie goes to DraftKings' point if DK is in the tie, else
    FanDuel's, else William Hill's (BETTABLE order; side-neutral). BEST price
    = the best price for the bet side among the books posting the modal point.
    DK-only = DraftKings' own point and price, for selection (R4 reads DK's
    own line) and grading. SHOP (robustness) = the best line for the bet side
    across bettable books, best price at that line; selection still on the
    modal line.
  * Truth: nflverse final home/away score. 1H EPA/play and 1H giveaways from
    pbp via the earlier study's own pbp_halftime(). 1H SCORE = the maximum of
    the running score over the Q1-Q2 rows (pbp scores are post-play and never
    fall). pbp_halftime() takes the LAST Q1-Q2 row by play_id, which misses a
    late-Q2 score in games whose rows are out of order; the earlier study
    removed such games through its SBR 1H cross-check (48 dropped), and no SBR
    exists for 2023-25. (Changed after the first run, on a data audit that
    found 10 games where the two readings differ; printed below.)

Frozen state and rules: REPLAYED, not refit on 2023-25
  The earlier study's functions are IMPORTED (load_sbr, pbp_halftime,
  clean_2h, ols, RULES, bets, stats, FIT, HOLD, WIND_MAX_VALID) and its
  section-3 fit is replayed on the SBR archive 2011-16; the result is
  asserted equal to the values that study printed
  (Temp/nfl_edge/halftime_statcheck_rerun.txt lines 71-73 and section 5):
    exp_m1 = +0.542 - 0.546*hp            hp = -spread_line (nflverse close)
    exp_t1 = +1.097 + 0.480*total_line    dev1 = 1H home margin - exp_m1
    luck   = dev1 - (-0.297 + 24.17*eff)  totdev1 = 1H points - exp_t1
    eff = home - away 1H offensive EPA/play; to_m = away - home 1H giveaways;
    wind = nflverse `wind`, outdoors/open roof, <= 45 mph.
  Primary cells, fit-chosen directions (asserted from the replay):
    R1 FADE |dev1|>=7   R2a UNDER totdev1>=+7   R2b OVER totdev1<=-7
    R3 UNDER wind>=15   R4 DOG |2H line|>=7     R5 FADE |luck|>=7
    R6 FOLLOW |to_m|>=2
  The grader here is ASSERTED to select the same games with the same won/push
  as the earlier bets() on the 2023-25 frame (modal line); only the price
  differs (bets() is fixed at -110).

Published practitioner rules, unchanged
  P1 the team trailing at the half, any deficit, a tied half is no bet
     (Action Network, Evan Abrams 2025-09-24: 464-361-12, 2022 - 2025 wk 3.
     That record contains 2023, 2024 and 2025 weeks 1-3 of this sample: only
     2025 weeks 4+ are out of sample for it.)
  P2 the leader by 14+ at the half (Action Network, John Ewing 2021:
     425-354-17 since 2003).
  P3 the 2H dog of +7 or more (Action Network 147-98-25 since 2005) - this IS
     R4's primary cell and is counted once.
  P3 placebo (the research pre-registration): 2H dogs +3 to +6.5; and the
  earlier study's control, +0.5 to +3.

Family and inference
  Primary family = R1-R6 (7) + P1 + P2 = 9 tests, Benjamini-Hochberg q=0.10;
  BH over the 7 alone is printed for comparison with the earlier study.
  p = one-sided cluster-bootstrap share of ROI draws <= 0 (10,000 draws; one
  bet per game per rule, so the cluster is the game). The exact binomial vs
  52.38% of the earlier study does not apply at varying real prices.
  90% CI = the same cluster bootstrap. Each season, early (weeks 1-9) vs late
  (weeks 10+ incl. playoffs), DK-only vs best price.
  Secondary family = every neighbourhood cell in the frozen direction (the
  earlier grids; P1 by deficit >= 1/4/7/10/14; P2 at 10/14/17/20), BH too.
  '*' = a strict low-volume cell, <= 10 bets per season.

Mechanism (3), on 2023-25 decision lines (modal; DK as robustness)
  market: 2H home point ~ hp + dev1      outcome: -(2H margin) ~ hp + dev1
  gap = dev1 coefficient of (point + 2H margin) on the same X = market minus
  outcome reaction; HC1 SE and a 2,000-draw game bootstrap CI.
  Totals: 2H total ~ total_line + totdev1 vs 2H points on the same X.
  The same regressions on the SBR replay (2011-16, 2017-21) for comparison.
  With hp in X, the dev1 coefficient equals the 1H-margin coefficient, so the
  frozen exp_m1 does not move it.

The ONE extra rule, fixed from the SBR era before 2023-25 is graded
  SBR 2017-21 spreads gap > 0 (market +0.157 vs outcome +0.112): the market
  moved the 2H line against the 1H over-performer further than outcomes did,
  an over-reaction, so the bet against it is the team that beat expectation
  (FOLLOW, R1's unchosen direction).
  Cut: |dev1| >= z * sigma / gap, z = Phi^-1(110/210) (the -110 break-even),
  sigma = residual SD of the SBR 2017-21 2H-margin regression: the |dev1| at
  which the SBR-era gap is worth the vig under a normal 2H margin. Computed in
  the replay, printed, graded ONCE at best price and DK. Not flipped if the
  2023-25 sign disagrees; the 2023-25 gap and its CI are reported beside it.
  Totals get the measurement only: the SBR-era totals gap was +0.041 in
  2011-16 and -0.011 in 2017-21, so no direction can be fixed from that era.

Wind (4)
  Two sources, outdoor/open roofs only: nflverse `wind` (<= 45 mph, the
  earlier study's) and ERA5 10 m wind at the kickoff hour
  (era5_kick_1999_2025.parquet, joined on stadium_id and the kickoff hour
  built as nfl_edge_weather_fetch.game_hours: ET wall clock -> UTC -> floor),
  ERA5 only at location == 'Home' (nflverse files neutral-site games under a
  US stadium_id). Cuts 12/15/18/20 as a neighbourhood, 2H UNDER at best price
  and DK. Placebos: 2H UNDER in calm games (< 10 mph) and 2H OVER in the
  windy games at each cut. Weeks 10+ split.
"""
from __future__ import annotations

import contextlib
import io
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts import nfl_edge_halftime as H
from scripts.nfl_edge_lib import BETTABLE, CACHE, am_to_prob, games, profit_units

SEASONS = [2023, 2024, 2025]
NS = len(SEASONS)
WINDOW_OPEN_S = 60
OVR_MIN, OVR_MAX = 1.00, 1.15
N_BOOT = 10000
N_BOOT_REG = 2000
LOWVOL = 10
CALM = 10.0
WIND_CUTS = [12, 15, 18, 20]

PRINTED = {"c1": (0.542, -0.546), "c2": (1.097, 0.480), "c3": (-0.297, 24.17)}
FROZEN_DIR = {"R1_side_dev": "fade", "R2a_fast_1H": "under", "R2b_slow_1H": "over",
              "R3_wind_under": "under", "R4_2H_dog": "dog", "R5_luck": "fade",
              "R6_turnovers": "follow"}
PRACT = {"P1_trailing": dict(grid=[1, 4, 7, 10, 14], primary=1, dir="trailer"),
         "P2_leader14": dict(grid=[10, 14, 17, 20], primary=14, dir="leader")}
KIND = {"R1_side_dev": "side", "R2a_fast_1H": "total", "R2b_slow_1H": "total",
        "R3_wind_under": "total", "R4_2H_dog": "side", "R5_luck": "side", "R6_turnovers": "side",
        "P1_trailing": "side", "P2_leader14": "side", "X_follow_dev": "side",
        "R4_band": "side", "WIND_under": "total", "WIND_over": "total", "CALM_under": "total"}


def hdr(t):
    print("\n" + "=" * 110 + "\n" + t + "\n" + "=" * 110, flush=True)


def fmt(df):
    return df.to_string(index=False)


# ─── statistics ─────────────────────────────────────────────────────────────

def boot(profit, cluster, n=N_BOOT, seed=7):
    profit = np.asarray(profit, float)
    if len(profit) == 0:
        return np.nan, np.nan, np.nan, np.nan
    uniq, inv = np.unique(np.asarray(cluster), return_inverse=True)
    sums = np.bincount(inv, weights=profit)
    cnts = np.bincount(inv)
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for a in range(0, n, 2000):
        idx = rng.integers(0, len(uniq), size=(min(2000, n - a), len(uniq)))
        out[a:a + len(idx)] = sums[idx].sum(1) / cnts[idx].sum(1)
    lo, hi = np.quantile(out, [0.05, 0.95])
    return profit.mean(), lo, hi, float(np.mean(out <= 0))


def summ(x: pd.DataFrame, n_seasons=NS) -> dict:
    if len(x) == 0:
        return dict(bets=0, per_season=0.0, units=0.0, roi=np.nan, lo=np.nan, hi=np.nan,
                    win=np.nan, p=1.0, med_price=np.nan)
    roi, lo, hi, p = boot(x.profit.values, x.game_id.values)
    dec = x[x.push == 0]
    return dict(bets=len(x), per_season=round(len(x) / n_seasons, 1), units=round(x.profit.sum(), 2),
                roi=round(100 * roi, 1), lo=round(100 * lo, 1), hi=round(100 * hi, 1),
                win=round(100 * dec.won.mean(), 1) if len(dec) else np.nan, p=round(p, 4),
                med_price=float(np.median(x.price)))


def ci(r):
    return f"[{r['lo']:+.1f},{r['hi']:+.1f}]" if r["bets"] else ""


def bh(p, q=0.10):
    return H.bh(np.asarray(p, float), q)


def ols_gap(y, X):
    """OLS with HC1 SE via statsmodels (the earlier study's ols)."""
    m, c, se = H.ols(y, X, list(X.columns))
    return m, c, se


def boot_coef(y, X, col, n=N_BOOT_REG, seed=11):
    y = np.asarray(y, float)
    Xa = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    j = 1 + list(X.columns).index(col)
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, len(y), len(y))
        b, *_ = np.linalg.lstsq(Xa[idx], y[idx], rcond=None)
        out[i] = b[j]
    return np.quantile(out, [0.05, 0.95])


# ─── 0. replay the frozen SBR fit ───────────────────────────────────────────

def replay_sbr(g):
    hdr("0. FROZEN PARAMETERS: the earlier study's section-3 fit REPLAYED on SBR 2011-16 (its own imported code)")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        m = H.load_sbr(g)
        ph = H.pbp_halftime(range(2011, 2022))
        m = m.merge(ph.drop(columns="season"), on="game_id", how="left")
        have = m.h1_home.notna()
        ok1 = (m.h1_home == (m.home_1stQtr + m.home_2ndQtr)) & (m.h1_away == (m.away_1stQtr + m.away_2ndQtr))
        m = m[~(have & ~ok1)].copy()
        m = H.clean_2h(m)
    f = m[m.season.isin(H.FIT)]
    _, c1, _ = H.ols(f.m1, f[["hp"]], ["hp"])
    _, c2, _ = H.ols(f.t1, f[["total_line"]], ["total_line"])
    m["exp_m1"] = c1["const"] + c1["hp"] * m.hp
    m["dev1"] = m.m1 - m.exp_m1
    m["exp_t1"] = c2["const"] + c2["total_line"] * m.total_line
    m["totdev1"] = m.t1 - m.exp_t1
    ff = m[m.season.isin(H.FIT) & m.eff.notna()]
    _, c3, _ = H.ols(ff.dev1, ff[["eff"]], ["eff"])
    m["luck"] = m.dev1 - (c3["const"] + c3["eff"] * m.eff)
    m["wind_out"] = np.where(m.roof.isin(["outdoors", "open"]) & (m.wind <= H.WIND_MAX_VALID), m.wind, np.nan)
    d = m[m.keep].copy()
    fitd = d[d.season.isin(H.FIT)]
    got = {"c1": (c1["const"], c1["hp"]), "c2": (c2["const"], c2["total_line"]), "c3": (c3["const"], c3["eff"])}
    for k, v in PRINTED.items():
        dp = 2 if k == "c3" else 3
        assert round(got[k][0], 3) == v[0] and round(got[k][1], dp) == v[1], (k, got[k], v)
    chosen = {}
    for rule, spec in H.RULES.items():
        u = {dr: H.stats(H.bets(fitd, rule, spec["primary"], dr), len(H.FIT))["units"] for dr in spec["dirs"]}
        chosen[rule] = max(u, key=u.get)
    assert chosen == FROZEN_DIR, chosen
    print(f"SBR graded games {len(d)} (fit {len(fitd)}) - identical to the earlier study's 2846 / 1548: "
          f"{len(d) == 2846 and len(fitd) == 1548}")
    print(f"exp_m1 = {c1['const']:+.4f} + {c1['hp']:.4f}*hp      (printed +0.542 - 0.546)  ASSERTED")
    print(f"exp_t1 = {c2['const']:+.4f} + {c2['total_line']:.4f}*total_line  (printed +1.097 + 0.480)  ASSERTED")
    print(f"luck   = dev1 - ({c3['const']:+.4f} + {c3['eff']:.3f}*eff)   (printed -0.297, 24.17)  ASSERTED")
    print("fit-chosen directions at the primary cell (replayed, ASSERTED):",
          ", ".join(f"{k} {v.upper()}" for k, v in chosen.items()))

    rows = []
    sbr_mech = {}
    for per, seas in (("SBR 2011-16", H.FIT), ("SBR 2017-21", H.HOLD)):
        x = d[d.season.isin(seas)]
        sbr_mech[per] = mech_rows(x, per, rows, s2="s2", t2="t2")
    sig = sbr_mech["SBR 2017-21"]["sigma_m2"]
    gap = sbr_mech["SBR 2017-21"]["gap_s"]
    z = norm.ppf(110 / 210)
    cut = z * sig / gap if gap > 0 else np.nan
    params = dict(c1=c1, c2=c2, c3=c3, gap=gap, sigma=sig, z=z, xcut=cut, sbr_rows=rows,
                  gap_t_fit=sbr_mech["SBR 2011-16"]["gap_t"], gap_t_hold=sbr_mech["SBR 2017-21"]["gap_t"],
                  gap_s_pooled=None)
    xp = d.copy()
    _, cp, _ = H.ols(xp.s2 + xp.m2, xp[["hp", "dev1"]], ["hp", "dev1"])
    params["gap_s_pooled"] = cp["dev1"]
    print(f"\nTHE ONE EXTRA RULE (fixed here, before 2023-25 is graded):")
    print(f"  SBR 2017-21 spreads gap (market minus outcome dev1 coefficient) = {gap:+.4f}; "
          f"residual SD of the 2H margin = {sig:.3f}; z(-110 break-even) = {z:.4f}")
    print(f"  -> FOLLOW the team that beat expectation when |dev1| >= {cut:.2f}  "
          f"(for reference: the pooled 2011-21 gap {cp['dev1']:+.4f} would give |dev1| >= "
          f"{z * sig / cp['dev1'] if cp['dev1'] > 0 else float('nan'):.1f}; not used)")
    print(f"  totals gap 2011-16 {params['gap_t_fit']:+.4f}, 2017-21 {params['gap_t_hold']:+.4f}: "
          f"sign changes -> no totals rule")
    return params


def mech_rows(x, per, rows, s2="s2", t2="t2"):
    """Market vs outcome reaction to the 1H, appended to rows; returns the gaps."""
    out = {}
    X = x[["hp", "dev1"]]
    for lab, y in (("market 2H home point", x[s2]), ("outcome -(2H margin)", -x.m2),
                   ("GAP market - outcome", x[s2] + x.m2)):
        mm, cc, se = H.ols(y, X, ["hp", "dev1"])
        r = dict(period=per, market="spread", y=lab, n=len(x),
                 b_pregame=f"{cc['hp']:+.3f} ({se['hp']:.3f})",
                 b_1H_dev=f"{cc['dev1']:+.4f} ({se['dev1']:.4f})", ci90_boot="", R2=round(mm.rsquared, 3))
        if lab.startswith("GAP"):
            lo, hi = boot_coef(y, X, "dev1")
            r["ci90_boot"] = f"[{lo:+.4f},{hi:+.4f}]"
            out.update(gap_s=cc["dev1"], gap_s_lo=lo, gap_s_hi=hi, gap_s_se=se["dev1"])
        if lab.startswith("outcome"):
            out["sigma_m2"] = float(np.sqrt(mm.scale))
        rows.append(r)
    X = x[["total_line", "totdev1"]]
    for lab, y in (("market 2H total", x[t2]), ("outcome 2H points", x.t2_act),
                   ("GAP market - outcome", x[t2] - x.t2_act)):
        mm, cc, se = H.ols(y, X, ["total_line", "totdev1"])
        r = dict(period=per, market="total", y=lab, n=len(x),
                 b_pregame=f"{cc['total_line']:+.3f} ({se['total_line']:.3f})",
                 b_1H_dev=f"{cc['totdev1']:+.4f} ({se['totdev1']:.4f})", ci90_boot="", R2=round(mm.rsquared, 3))
        if lab.startswith("GAP"):
            lo, hi = boot_coef(y, X, "totdev1")
            r["ci90_boot"] = f"[{lo:+.4f},{hi:+.4f}]"
            out.update(gap_t=cc["totdev1"], gap_t_lo=lo, gap_t_hi=hi)
        rows.append(r)
    return out


# ─── 1. 2023-25 halftime state ──────────────────────────────────────────────

def halftime_frame(g, P):
    with contextlib.redirect_stdout(io.StringIO()):
        ph = H.pbp_halftime(SEASONS)
    wins = []
    for s in SEASONS:
        p = pd.read_parquet(CACHE / f"pbp_{s}.parquet",
                            columns=["game_id", "play_id", "qtr", "time_of_day", "total_home_score", "total_away_score"])
        p["t"] = pd.to_datetime(p.time_of_day, utc=True, errors="coerce", format="mixed")
        p = p.sort_values(["game_id", "play_id"])
        w = p[p.qtr <= 2].groupby("game_id").t.max().rename("q2_last").to_frame()
        w["q3_kick"] = p[p.qtr == 3].groupby("game_id").t.min()
        w["pbp_fin_h"] = p.groupby("game_id").total_home_score.last()
        w["pbp_fin_a"] = p.groupby("game_id").total_away_score.last()
        w["h1h_max"] = p[p.qtr <= 2].groupby("game_id").total_home_score.max()
        w["h1a_max"] = p[p.qtr <= 2].groupby("game_id").total_away_score.max()
        w["q3h_first"] = p[p.qtr == 3].groupby("game_id").total_home_score.first()
        w["q3a_first"] = p[p.qtr == 3].groupby("game_id").total_away_score.first()
        wins.append(w.reset_index())
    win = pd.concat(wins, ignore_index=True)
    gg = g[g.season.isin(SEASONS) & g.result.notna()][
        ["game_id", "season", "week", "game_type", "gameday", "gametime", "location", "home_team", "away_team",
         "home_score", "away_score", "spread_line", "total_line", "roof", "wind", "stadium_id"]].copy()
    x = gg.merge(ph.drop(columns="season"), on="game_id", how="left").merge(win, on="game_id", how="left")
    x["hp"] = -x.spread_line
    dis = x[(x.h1_home != x.h1h_max) | (x.h1_away != x.h1a_max)]
    print(f"\n1H score: the earlier pbp_halftime() last-row reading differs from the max-over-Q1-Q2 reading in "
          f"{len(dis)} games (the max is used); max-over-Q1-Q2 differs from the first Q3 row in "
          f"{int(((x.h1h_max != x.q3h_first) | (x.h1a_max != x.q3a_first)).sum())} games (a score on the Q3 kickoff):")
    print(dis[["game_id", "h1_home", "h1_away", "h1h_max", "h1a_max", "q3h_first", "q3a_first"]].to_string(index=False))
    x["h1_home"], x["h1_away"] = x.h1h_max, x.h1a_max
    x["m1"] = x.h1_home - x.h1_away
    x["t1"] = x.h1_home + x.h1_away
    x["margin"] = x.home_score - x.away_score
    x["total_pts"] = x.home_score + x.away_score
    x["m2"] = x.margin - x.m1
    x["t2_act"] = x.total_pts - x.t1
    c1, c2, c3 = P["c1"], P["c2"], P["c3"]
    x["exp_m1"] = c1["const"] + c1["hp"] * x.hp
    x["dev1"] = x.m1 - x.exp_m1
    x["exp_t1"] = c2["const"] + c2["total_line"] * x.total_line
    x["totdev1"] = x.t1 - x.exp_t1
    x["luck"] = x.dev1 - (c3["const"] + c3["eff"] * x.eff)
    out_roof = x.roof.isin(["outdoors", "open"])
    x["wind_out"] = np.where(out_roof & (x.wind <= H.WIND_MAX_VALID), x.wind, np.nan)
    # ERA5 at the kickoff hour (nfl_edge_weather_fetch.game_hours construction)
    dt = pd.to_datetime(x.gameday + " " + x.gametime.fillna("13:00"), errors="coerce")
    x["hr"] = dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                nonexistent="shift_forward").dt.tz_convert("UTC").dt.floor("h")
    e = pd.read_parquet(CACHE / "era5_kick_1999_2025.parquet")
    e["ts"] = e.ts.astype("datetime64[us, UTC]")
    x["hr"] = x.hr.astype("datetime64[us, UTC]")
    x = x.merge(e[["stadium_id", "ts", "era5_wind"]].rename(columns={"ts": "hr"}), on=["stadium_id", "hr"], how="left")
    x["era5_out"] = np.where(out_roof & (x.location == "Home"), x.era5_wind, np.nan)
    x["late"] = x.week >= 10
    return x


# ─── 2. quotes ──────────────────────────────────────────────────────────────

def load_quotes(ht):
    hdr("1. THE BOUGHT 2H LINES: coverage, decision quote, books' agreement")
    h = pd.read_parquet(CACHE / "h2_2023_2025.parquet")
    print(f"rows {len(h)}, games {h.game_id.nunique()} "
          f"({', '.join(f'{s}: {n}' for s, n in h.groupby('season').game_id.nunique().items())}); "
          f"played games in nflverse 2023-25: {len(ht)}; not in the purchase: "
          f"{len(set(ht.game_id) - set(h.game_id))} "
          f"(by season {pd.Series([s[:4] for s in sorted(set(ht.game_id) - set(h.game_id))]).value_counts().to_dict()})")
    print("rows by market x book:\n" + h.groupby(["market", "bookmaker"]).size().unstack().to_string())
    print("games per season x book:\n" + h.groupby(["season", "bookmaker"]).game_id.nunique().unstack().fillna(0).astype(int).to_string())
    h["ovr"] = am_to_prob(h.price_home) + am_to_prob(h.price_away)
    bad = (h.ovr < OVR_MIN) | (h.ovr > OVR_MAX) | h[["point", "price_home", "price_away"]].isna().any(axis=1)
    print(f"\nquote screen: implied-probability sum by book (median / 1st / 99th pct):")
    print(h.groupby(["market", "bookmaker"]).ovr.describe(percentiles=[.01, .5, .99])[["1%", "50%", "99%"]].round(3).to_string())
    print(f"dropped quotes (sum < {OVR_MIN} or > {OVR_MAX} or missing): {int(bad.sum())}")
    if bad.any():
        print(h[bad][["game_id", "bookmaker", "market", "snapshot_at", "point", "price_home", "price_away", "ovr"]]
              .head(20).to_string(index=False))
    h = h[~bad].copy()

    w = ht[["game_id", "q2_last", "q3_kick", "pbp_fin_h", "pbp_fin_a", "home_score", "away_score"]]
    mis = w[(w.pbp_fin_h != w.home_score) | (w.pbp_fin_a != w.away_score)]
    print(f"\npbp final score disagrees with nflverse in {len(mis)} games (graded on nflverse finals):")
    if len(mis):
        print(mis.to_string(index=False))
    hw = (w.q3_kick - w.q2_last).dt.total_seconds() / 60
    print(f"halftime window (last Q2 row to Q3 kickoff, minutes): median {hw.median():.1f}, "
          f"min {hw.min():.1f}, max {hw.max():.1f} ({w.game_id[hw.idxmax()]}); missing {int(hw.isna().sum())}")
    x = h.merge(w[["game_id", "q2_last", "q3_kick"]], on="game_id", how="left")
    x["open"] = x.q2_last + pd.Timedelta(seconds=WINDOW_OPEN_S)
    x["pos"] = np.select([x.snapshot_at < x.open, x.snapshot_at < x.q3_kick], ["Q2 or first 60s", "in window"],
                         "after Q3 kickoff")
    print("snapshot rows by position vs the halftime window:\n" + x.pos.value_counts().to_string())
    allk = x.groupby(["game_id", "market", "bookmaker"]).ngroups
    inw = x[x.pos == "in window"].sort_values("snapshot_at")
    gk = inw.groupby(["game_id", "market", "bookmaker"])
    print(f"game x market x book with any snapshot {allk}; with an in-window snapshot {gk.ngroups}; "
          f"dropped (only Q2 / post-kickoff snapshots) {allk - gk.ngroups}")
    last = gk.tail(1).copy()
    first = gk.head(1).copy()
    last["min_before_kick"] = (last.q3_kick - last.snapshot_at).dt.total_seconds() / 60
    first["min_after_q2"] = (first.snapshot_at - first.q2_last).dt.total_seconds() / 60
    print(f"decision quote: minutes before the Q3 kickoff median {last.min_before_kick.median():.1f} "
          f"(10-90%: {last.min_before_kick.quantile(.1):.1f}-{last.min_before_kick.quantile(.9):.1f}); "
          f"first in-window quote: minutes after the last Q2 row median {first.min_after_q2.median():.1f}; "
          f"decision != first snapshot for {(gk.size() > 1).mean():.0%} of game x market x book")
    return last, first


def coverage(last, ht):
    bk = [b for b in BETTABLE if b in set(last.bookmaker)]
    print(f"\nbettable books in the file (BETTABLE order = tie-break order): {bk}; reference only: "
          f"{sorted(set(last.bookmaker) - set(bk))}")
    rows = []
    for (s, mk), z in last.groupby(["season", "market"]):
        zb = z[z.bookmaker.isin(bk)]
        nb = zb.groupby("game_id").bookmaker.nunique()
        dis = zb.groupby("game_id").point.nunique()
        dis_all = z.groupby("game_id").point.nunique()
        rng_ = zb.groupby("game_id").point.agg(lambda v: v.max() - v.min())
        r = dict(season=s, market=mk, games=int(len(nb)), dk=int(zb[zb.bookmaker == "draftkings"].game_id.nunique()))
        for b in bk[1:]:
            r[b] = int(zb[zb.bookmaker == b].game_id.nunique())
        r.update(two_plus=int((nb >= 2).sum()),
                 disagree_pct=round(100 * (dis[nb >= 2] > 1).mean(), 1),
                 disagree_incl_bovada_pct=round(100 * (dis_all > 1)[z.groupby("game_id").bookmaker.nunique() >= 2].mean(), 1),
                 median_spread_of_lines=float(rng_[nb >= 2].median()), max_spread=float(rng_.max()))
        rows.append(r)
    print("decision-quote coverage (games with a bettable in-window quote) and books' disagreement on the line:")
    print(fmt(pd.DataFrame(rows)))
    return bk


def views(q, bk):
    """Per game: selection line + side-specific (point, price) for modal-best, DK, shop."""
    q = q[q.bookmaker.isin(bk)]
    rank = {b: i for i, b in enumerate(bk)}
    out = {"best": [], "dk": [], "shop": []}
    for (gid, mk), z in q.groupby(["game_id", "market"], sort=False):
        z = z.assign(r=z.bookmaker.map(rank)).sort_values("r")
        vc = z.point.value_counts()
        top = set(vc[vc == vc.max()].index)
        modal = next(p for p in z.point if p in top)
        zz = z[z.point == modal]
        pre = "s" if mk == "spreads_h2" else "t"
        a, b = ("h", "a") if pre == "s" else ("o", "u")
        rec = {"game_id": gid, f"{pre}2": modal, f"{pre}_{a}_pt": modal, f"{pre}_{a}_pr": zz.price_home.max(),
               f"{pre}_{b}_pt": modal, f"{pre}_{b}_pr": zz.price_away.max(), f"{pre}_nb": len(z),
               f"{pre}_dis": z.point.nunique() > 1}
        out["best"].append(rec)
        d = z[z.bookmaker == "draftkings"]
        if len(d):
            dp = d.point.iloc[0]
            out["dk"].append({"game_id": gid, f"{pre}2": dp, f"{pre}_{a}_pt": dp, f"{pre}_{a}_pr": d.price_home.iloc[0],
                              f"{pre}_{b}_pt": dp, f"{pre}_{b}_pr": d.price_away.iloc[0]})
        # shop: home/over side wants the highest home point / lowest total; away/under the opposite
        if pre == "s":
            hs = z.sort_values(["point", "price_home"], ascending=[False, False]).iloc[0]
            as_ = z.sort_values(["point", "price_away"], ascending=[True, False]).iloc[0]
            out["shop"].append({"game_id": gid, "s2": modal, "s_h_pt": hs.point, "s_h_pr": hs.price_home,
                                "s_a_pt": as_.point, "s_a_pr": as_.price_away})
        else:
            os_ = z.sort_values(["point", "price_home"], ascending=[True, False]).iloc[0]
            us = z.sort_values(["point", "price_away"], ascending=[False, False]).iloc[0]
            out["shop"].append({"game_id": gid, "t2": modal, "t_o_pt": os_.point, "t_o_pr": os_.price_home,
                                "t_u_pt": us.point, "t_u_pr": us.price_away})
    res = {}
    for k, recs in out.items():
        df = pd.DataFrame(recs)
        res[k] = df.groupby("game_id").first().reset_index()
    return res


def build(ht, v):
    return ht.merge(v, on="game_id", how="left")


# ─── 3. selection and grading ───────────────────────────────────────────────

def pick(df, rule, cut, direction=None):
    """Mask and side (True = home / over) for one rule cell. Identical state logic to H.bets()."""
    t = pd.Series(True, index=df.index)
    if rule == "R1_side_dev" or rule == "X_follow_dev":
        dr = direction or ("follow" if rule == "X_follow_dev" else FROZEN_DIR["R1_side_dev"])
        msk, side = df.dev1.abs() >= cut, (df.dev1 > 0) if dr == "follow" else (df.dev1 < 0)
    elif rule == "R2a_fast_1H":
        msk, side = df.totdev1 >= cut, t & ((direction or FROZEN_DIR[rule]) == "over")
    elif rule == "R2b_slow_1H":
        msk, side = df.totdev1 <= -cut, t & ((direction or FROZEN_DIR[rule]) == "over")
    elif rule in ("R3_wind_under", "WIND_under", "WIND_over"):
        col = "wind_out" if rule == "R3_wind_under" else direction
        msk, side = df[col] >= cut, t & (rule == "WIND_over")
    elif rule == "CALM_under":
        msk, side = df[direction] < cut, t & False
    elif rule == "R4_2H_dog":
        msk, side = df.s2.abs() >= cut, df.s2 > 0
    elif rule == "R4_band":
        msk, side = (df.s2.abs() >= cut[0]) & (df.s2.abs() <= cut[1]), df.s2 > 0
    elif rule == "R5_luck":
        dr = direction or FROZEN_DIR[rule]
        msk, side = df.luck.abs() >= cut, (df.luck > 0) if dr == "follow" else (df.luck < 0)
    elif rule == "R6_turnovers":
        dr = direction or FROZEN_DIR[rule]
        msk, side = df.to_m.abs() >= cut, (df.to_m > 0) if dr == "follow" else (df.to_m < 0)
    elif rule == "P1_trailing":
        msk, side = (df.m1 != 0) & (df.m1.abs() >= cut), df.m1 < 0
    elif rule == "P2_leader14":
        msk, side = df.m1.abs() >= cut, df.m1 > 0
    else:
        raise ValueError(rule)
    return msk.fillna(False).values.astype(bool), np.asarray(side, bool)


def grade(df, rule, cut, direction=None):
    kind = KIND[rule]
    msk, side = pick(df, rule, cut, direction)
    pre = "s" if kind == "side" else "t"
    a, b = ("h", "a") if pre == "s" else ("o", "u")
    avail = df[f"{pre}_{a}_pr"].notna().values & df[f"{pre}_{b}_pr"].notna().values
    msk = msk & avail
    x = df[msk].copy()
    sd = side[msk]
    pt = np.where(sd, x[f"{pre}_{a}_pt"], x[f"{pre}_{b}_pt"])
    pr = np.where(sd, x[f"{pre}_{a}_pr"], x[f"{pre}_{b}_pr"])
    if kind == "side":
        c = x.m2.values + pt
        won, push = np.where(sd, c > 0, c < 0), c == 0
    else:
        c = x.t2_act.values - pt
        won, push = np.where(sd, c > 0, c < 0), c == 0
    x["side"], x["line"], x["price"] = sd, pt, pr
    x["won"], x["push"] = won.astype(int), push.astype(int)
    x["profit"] = profit_units(x.won, x.price, x.push)
    return x


def assert_same_as_earlier(df):
    """My selection + won/push == the earlier study's bets() on the modal line."""
    for rule, spec in H.RULES.items():
        for cut in spec["grid"]:
            mine = grade(df, rule, cut)
            pre = "s" if KIND[rule] == "side" else "t"
            sub = df[df[f"{pre}2"].notna()].copy()
            if pre == "s":
                sub = sub[sub.s_h_pr.notna() & sub.s_a_pr.notna()]
            else:
                sub = sub[sub.t_o_pr.notna() & sub.t_u_pr.notna()]
            theirs = H.bets(sub.reset_index(drop=True), rule, cut, FROZEN_DIR[rule])
            a = mine.set_index("game_id")[["won", "push"]].sort_index()
            b = theirs.set_index("game_id")[["won", "push"]].sort_index()
            assert a.index.equals(b.index) and (a.values == b.values).all(), (rule, cut, len(a), len(b))


# ─── main ───────────────────────────────────────────────────────────────────

def main():
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 60)
    g = games()
    P = replay_sbr(g)
    ht = halftime_frame(g, P)
    last, first = load_quotes(ht)
    bk = coverage(last, ht)
    V = {}
    for tag, q in (("last", last), ("first", first)):
        v = views(q, bk)
        for k in v:
            V[(tag, k)] = v[k]
    D = {}
    for (tag, k), v in V.items():
        sp = v[[c for c in v.columns if c == "game_id" or c.startswith("s")]]
        tt = v[[c for c in v.columns if c == "game_id" or c.startswith("t")]]
        D[(tag, k)] = build(ht, sp.merge(tt, on="game_id", how="outer"))
    best, dk = D[("last", "best")], D[("last", "dk")]
    print(f"\ngames with a modal decision spread {int(best.s2.notna().sum())}, total {int(best.t2.notna().sum())}; "
          f"DK decision spread {int(dk.s2.notna().sum())}, total {int(dk.t2.notna().sum())}")
    both = best.merge(dk[["game_id", "s2", "t2"]], on="game_id", suffixes=("", "_dk"))
    for c in ("s2", "t2"):
        z = both[both[c].notna() & both[c + "_dk"].notna()]
        print(f"  {c}: DK's line differs from the modal line in {100 * (z[c] != z[c + '_dk']).mean():.1f}% of "
              f"{len(z)} games")
    price_orientation()
    print("orientation check (2H home point should RISE with the 1H home margin and with the pregame home point):")
    z = best[best.s2.notna()]
    _, cc, se = H.ols(z.s2, z[["hp", "m1"]], ["hp", "m1"])
    print(f"  2H home point = {cc['const']:+.3f} + {cc['hp']:.3f}*hp + {cc['m1']:+.3f}*1H home margin  "
          f"(SBR 2011-16 line model: +0.384 + 0.604*hp + 0.136*m1)")
    print(z.sample(6, random_state=3)[["game_id", "hp", "m1", "s2", "s_h_pr", "s_a_pr", "total_line", "t1", "t2",
                                        "t_o_pr", "t_u_pr"]].to_string(index=False))
    assert_same_as_earlier(best)
    print("ASSERTED: this script's selection and won/push are identical to the earlier study's bets() on the "
          "modal 2023-25 line, every rule, every neighbourhood cell.")

    # ── 2. primary family
    hdr("2. PRIMARY FAMILY: the 7 frozen rules + 2 published practitioner rules, graded ONCE, 2023-25, real prices")
    fam = [(r, H.RULES[r]["primary"], FROZEN_DIR[r]) for r in H.RULES] + \
          [(r, s["primary"], s["dir"]) for r, s in PRACT.items()]
    rows = []
    for rule, cut, dr in fam:
        r = dict(rule=rule, dir=dr.upper(), cut=cut)
        sb = summ(grade(best, rule, cut))
        sd = summ(grade(dk, rule, cut))
        ss = summ(grade(D[("last", "shop")], rule, cut))
        sf = summ(grade(D[("first", "best")], rule, cut))
        r.update(bets=sb["bets"], per_season=sb["per_season"], units=sb["units"], roi=sb["roi"], ci90=ci(sb),
                 win=sb["win"], med_price=sb["med_price"], p=sb["p"],
                 dk_bets=sd["bets"], dk_units=sd["units"], dk_roi=sd["roi"], dk_ci90=ci(sd), dk_p=sd["p"],
                 shop_roi=ss["roi"], first_snap_roi=sf["roi"], first_snap_bets=sf["bets"])
        rows.append(r)
    pf = pd.DataFrame(rows)
    pf["BH9"] = bh(pf.p.values)
    pf["BH9_dk"] = bh(pf.dk_p.values)
    pf["BH7"] = list(bh(pf.p.values[:7])) + ["", ""]
    print("best = best bettable price at the modal line; dk = DraftKings only; shop = best line for the side (robustness);\n"
          "first_snap = first in-window snapshot (robustness). p = one-sided cluster-bootstrap share of ROI <= 0.")
    print(fmt(pf[["rule", "dir", "cut", "bets", "per_season", "units", "roi", "ci90", "win", "med_price", "p", "BH9", "BH7",
                  "dk_bets", "dk_units", "dk_roi", "dk_ci90", "dk_p", "BH9_dk", "shop_roi", "first_snap_bets",
                  "first_snap_roi"]]))
    print("\nSBR-era result of the same cell at -110 (the earlier study, for comparison): R1 -7.7, R2a +1.5, R2b -6.0, "
          "R3 +10.1, R4 -13.8, R5 +3.8, R6 +7.3 (2017-21 hold-out ROI %).")

    hdr("2b. EVERY SEASON and EARLY (wk 1-9) / LATE (wk 10+ incl. playoffs), primary cells, best price and DK")
    rows = []
    for rule, cut, dr in fam:
        for vname, df in (("best", best), ("dk", dk)):
            x = grade(df, rule, cut)
            r = dict(rule=rule, view=vname)
            for s in SEASONS:
                st = summ(x[x.season == s], 1)
                r[f"{s}"] = f"{st['bets']}b {st['units']:+.1f}u {st['roi']:+.0f}%" if st["bets"] else "0b"
            for lab, msk in (("early", ~x.late), ("late", x.late)):
                st = summ(x[msk])
                r[lab] = f"{st['bets']}b {st['units']:+.1f}u {st['roi']:+.0f}% {ci(st)}" if st["bets"] else "0b"
            x25 = x[(x.season == 2025) & (x.week >= 4)]
            st = summ(x25, 1)
            r["2025_wk4+"] = f"{st['bets']}b {st['units']:+.1f}u {st['roi']:+.0f}%" if st["bets"] else "0b"
            rows.append(r)
    print(fmt(pd.DataFrame(rows)))
    print("(2025_wk4+ = the only part of this sample outside the Action Network trailing-team record.)")

    hdr("2c. CONTROLS at real prices (best price at the modal line): blanket 2H bets and the P3/R4 placebos")
    rows = []
    for s_, z in best[best.s2.notna() & best.t2.notna()].groupby("season"):
        dd = z.t2_act - z.t2
        cv = z.m2 + z.s2
        rows.append(dict(season=s_, games=len(z), mean_2H_pts_minus_total=round(dd.mean(), 2),
                         over_pct=round(100 * (dd > 0).mean(), 1), under_pct=round(100 * (dd < 0).mean(), 1),
                         mean_home_cover_margin=round(cv.mean(), 2), home_cover_pct=round(100 * (cv > 0).mean(), 1)))
    print("2H base rates at the modal decision line, by season:")
    print(fmt(pd.DataFrame(rows)))
    rows = []
    for lab, kind, fn in (
            ("every 2H under", "total", lambda d: (d.t2.notna(), np.zeros(len(d), bool))),
            ("every 2H over", "total", lambda d: (d.t2.notna(), np.ones(len(d), bool))),
            ("every 2H home side", "side", lambda d: (d.s2.notna(), np.ones(len(d), bool))),
            ("every 2H away side", "side", lambda d: (d.s2.notna(), np.zeros(len(d), bool))),
            ("every 2H favourite", "side", lambda d: (d.s2.notna() & (d.s2 != 0), (d.s2 < 0).values)),
            ("every 2H underdog", "side", lambda d: (d.s2.notna() & (d.s2 != 0), (d.s2 > 0).values))):
        for vname, df in (("best", best), ("dk", dk)):
            msk, sd = fn(df)
            x = grade_generic(df, np.asarray(msk, bool), np.asarray(sd, bool), kind)
            st = summ(x)
            rows.append(dict(control=lab, view=vname, bets=st["bets"], units=st["units"], roi=st["roi"], ci90=ci(st),
                             win=st["win"], med_price=st["med_price"]))
    for lab, cut in (("P3 placebo: 2H dogs +3 to +6.5", (3, 6.5)), ("R4 control: 2H dogs +0.5 to +3", (0.5, 3))):
        for vname, df in (("best", best), ("dk", dk)):
            st = summ(grade(df, "R4_band", cut))
            rows.append(dict(control=lab, view=vname, bets=st["bets"], units=st["units"], roi=st["roi"], ci90=ci(st),
                             win=st["win"], med_price=st["med_price"]))
    print(fmt(pd.DataFrame(rows)))

    # ── 3. mechanism
    hdr("3. MECHANISM: does the 2H line react to the 1H like the 2H outcome does? (OLS HC1; gap CI = game bootstrap)")
    rows = list(P["sbr_rows"])
    mech = {}
    for vname, df in (("2023-25 modal", best), ("2023-25 DK", dk)):
        z = df[df.s2.notna() & df.t2.notna()]
        mech[vname] = mech_rows(z, vname, rows)
        for s in SEASONS:
            zz = z[z.season == s]
            tmp = []
            mm = mech_rows(zz, f"{vname} {s}", tmp)
            rows += [r for r in tmp if r["y"].startswith("GAP")]
    print(fmt(pd.DataFrame(rows)))
    m0 = mech["2023-25 modal"]
    print(f"\nspreads: 2023-25 gap {m0['gap_s']:+.4f}, 90% CI [{m0['gap_s_lo']:+.4f},{m0['gap_s_hi']:+.4f}]  "
          f"(SBR 2017-21 {P['gap']:+.4f}). A positive gap = the market moves the 2H line against the team that beat "
          f"expectation by more than the outcome does (over-reaction).")
    print(f"totals : 2023-25 gap {m0['gap_t']:+.4f}, 90% CI [{m0['gap_t_lo']:+.4f},{m0['gap_t_hi']:+.4f}]  "
          f"(SBR 2011-16 {P['gap_t_fit']:+.4f}, 2017-21 {P['gap_t_hold']:+.4f}). Positive = the 2H total rises "
          f"with a fast 1H by more than 2H scoring does.")

    hdr(f"3b. THE ONE EXTRA RULE (fixed in section 0 from SBR 2017-21): FOLLOW the 1H over-performer, "
        f"|dev1| >= {P['xcut']:.2f}, graded once")
    rows = []
    for vname, df in (("best", best), ("dk", dk), ("shop", D[("last", "shop")]), ("first_snap", D[("first", "best")])):
        x = grade(df, "X_follow_dev", P["xcut"])
        st = summ(x)
        r = dict(view=vname, bets=st["bets"], per_season=st["per_season"], units=st["units"], roi=st["roi"],
                 ci90=ci(st), win=st["win"], p=st["p"])
        for s in SEASONS:
            ss = summ(x[x.season == s], 1)
            r[str(s)] = f"{ss['bets']}b {ss['units']:+.1f}u"
        for lab, msk in (("early", ~x.late), ("late", x.late)):
            ss = summ(x[msk])
            r[lab] = f"{ss['bets']}b {ss['units']:+.1f}u {ss['roi']:+.0f}%"
        rows.append(r)
    print(fmt(pd.DataFrame(rows)))
    gate = "CI excludes 0" if (m0["gap_s_lo"] > 0 or m0["gap_s_hi"] < 0) else "CI includes 0"
    print(f"2023-25 spreads gap {m0['gap_s']:+.4f} ({gate}); the rule's direction (FOLLOW) "
          f"{'agrees' if m0['gap_s'] > 0 else 'DISAGREES'} with the 2023-25 sign.")

    # ── 4. neighbourhoods
    hdr("4. NEIGHBOURHOODS (secondary family): every cell in the frozen direction, best price and DK. '*' <= 10 bets/season")
    rows = []
    cells = [(r, c, FROZEN_DIR[r]) for r, spec in H.RULES.items() for c in spec["grid"]] + \
            [(r, c, s["dir"]) for r, s in PRACT.items() for c in s["grid"]]
    for rule, cut, dr in cells:
        xb, xd = grade(best, rule, cut), grade(dk, rule, cut)
        sb, sd = summ(xb), summ(xd)
        per = xb.groupby("season").size().reindex(SEASONS, fill_value=0)
        rows.append(dict(rule=rule, dir=dr.upper(), cut=cut,
                         P="P" if cut == (H.RULES[rule]["primary"] if rule in H.RULES else PRACT[rule]["primary"]) else "",
                         bets=sb["bets"], **{f"b{s}": int(per[s]) for s in SEASONS},
                         units=sb["units"], roi=sb["roi"], ci90=ci(sb), win=sb["win"], p=sb["p"],
                         dk_bets=sd["bets"], dk_units=sd["units"], dk_roi=sd["roi"], dk_ci90=ci(sd),
                         strict="*" if sb["per_season"] <= LOWVOL else ""))
    nb = pd.DataFrame(rows)
    nb["BH_sec"] = bh(nb.p.values)
    print(fmt(nb))
    print(f"secondary family: {len(nb)} cells; BH q=0.10 rejections {int(nb.BH_sec.sum())}; smallest p {nb.p.min():.4f}")

    # ── 5. wind
    hdr("5. R3 WIND IN DETAIL: 2H UNDER by wind source and cut; calm and windy-over placebos; weeks 10+ split")
    both_w = best[["wind_out", "era5_out"]].dropna()
    print(f"outdoor/open games with nflverse wind {int(best.wind_out.notna().sum())}, with ERA5 (home venues) "
          f"{int(best.era5_out.notna().sum())}, both {len(both_w)}; corr {both_w.corr().iloc[0, 1]:.2f}; "
          f"mean nflverse {both_w.wind_out.mean():.1f} vs ERA5 {both_w.era5_out.mean():.1f} mph")
    print("outdoor/open games by season: " + str(best[best.roof.isin(['outdoors', 'open'])].groupby('season').size().to_dict())
          + "; with nflverse wind: " + str(best[best.wind_out.notna()].groupby('season').size().to_dict())
          + "; with ERA5: " + str(best[best.era5_out.notna()].groupby('season').size().to_dict()))
    rows = []
    for src in ("wind_out", "era5_out"):
        for lab, rule, cut in ([("UNDER", "WIND_under", c) for c in WIND_CUTS] +
                               [("placebo OVER", "WIND_over", c) for c in WIND_CUTS] +
                               [("placebo calm UNDER", "CALM_under", CALM)]):
            for vname, df in (("best", best), ("dk", dk)):
                x = grade(df, rule, cut, src)
                st = summ(x)
                per = x.groupby("season").size().reindex(SEASONS, fill_value=0)
                r = dict(source="nflverse" if src == "wind_out" else "ERA5", bet=lab,
                         cut=(f">={cut}" if rule != "CALM_under" else f"<{cut}"), view=vname,
                         bets=st["bets"], **{f"b{s}": int(per[s]) for s in SEASONS}, units=st["units"],
                         roi=st["roi"], ci90=ci(st), win=st["win"], p=st["p"])
                for h_, msk in (("wk1-9", ~x.late), ("wk10+", x.late)):
                    ss = summ(x[msk])
                    r[h_] = f"{ss['bets']}b {ss['units']:+.1f}u {ss['roi']:+.0f}% {ci(ss)}" if ss["bets"] else "0b"
                r["strict"] = "*" if st["per_season"] <= LOWVOL else ""
                rows.append(r)
    wt = pd.DataFrame(rows)
    print(fmt(wt))
    print("SBR era (earlier study, -110): R3 nflverse wind >= 15 pooled 2011-21 249 bets +10.9%; weeks 10+ in "
          "2017-21 61 bets +30.1%, weeks 1-9 51 bets -13.9%.")

    # ── 6. low-volume cells
    hdr("6. LOW-VOLUME EXTREME CELLS inside the neighbourhoods (<= 10 bets/season at the best price), marked *")
    lv = nb[nb.strict == "*"][["rule", "dir", "cut", "bets", "b2023", "b2024", "b2025", "units", "roi", "ci90", "p",
                               "dk_bets", "dk_units", "dk_roi"]]
    print(fmt(lv) if len(lv) else "none in the rule neighbourhoods")
    lw = wt[(wt.strict == "*") & (wt.bet == "UNDER")]
    print("\nwind UNDER cells with <= 10 bets/season:")
    print(fmt(lw[["source", "cut", "view", "bets", "b2023", "b2024", "b2025", "units", "roi", "ci90", "p", "wk10+"]])
          if len(lw) else "none")

    # ── 7. volume
    hdr("7. VOLUME: bets per season each primary cell would have produced (best price), and positive-ROI cells")
    print(fmt(pf[["rule", "dir", "cut", "bets", "per_season", "units", "roi", "ci90", "p", "BH9"]]))
    pos = nb[(nb.roi > 0)].sort_values("p")
    print("\nneighbourhood cells with positive ROI at the best price (sorted by p):")
    print(fmt(pos[["rule", "dir", "cut", "bets", "b2023", "b2024", "b2025", "units", "roi", "ci90", "p", "dk_roi",
                   "strict", "BH_sec"]]))


def price_orientation():
    """Two books, same snapshot, different points: which column gets dearer at the higher point?"""
    h = pd.read_parquet(CACHE / "h2_2023_2025.parquet")
    a = h.merge(h, on=["game_id", "market", "snapshot_at"], suffixes=("", "_b"))
    a = a[(a.bookmaker < a.bookmaker_b) & (a.point != a.point_b)]
    hi = (a.point > a.point_b).values
    for mk, exp in (("spreads_h2", "home side dearer at a higher home point"),
                    ("totals_h2", "over cheaper at a higher total")):
        m = (a.market == mk).values
        p_hi = am_to_prob(np.where(hi[m], a.price_home[m], a.price_home_b[m]))
        p_lo = am_to_prob(np.where(hi[m], a.price_home_b[m], a.price_home[m]))
        print(f"price orientation, {mk}: price_home implied prob higher at the higher point in "
              f"{100 * np.mean(p_hi > p_lo):.0f}%, lower in {100 * np.mean(p_hi < p_lo):.0f}% of {int(m.sum())} "
              f"book pairs (expected if price_home = home / over: {exp})")


def grade_generic(df, msk, side, kind):
    pre = "s" if kind == "side" else "t"
    a, b = ("h", "a") if pre == "s" else ("o", "u")
    avail = df[f"{pre}_{a}_pr"].notna().values & df[f"{pre}_{b}_pr"].notna().values
    msk = msk & avail
    x = df[msk].copy()
    sd = side[msk]
    pt = np.where(sd, x[f"{pre}_{a}_pt"], x[f"{pre}_{b}_pt"])
    pr = np.where(sd, x[f"{pre}_{a}_pr"], x[f"{pre}_{b}_pr"])
    c = (x.m2.values + pt) if kind == "side" else (x.t2_act.values - pt)
    x["side"], x["line"], x["price"] = sd, pt, pr
    x["won"] = np.where(sd, c > 0, c < 0).astype(int)
    x["push"] = (c == 0).astype(int)
    x["profit"] = profit_units(x.won, x.price, x.push)
    return x


if __name__ == "__main__":
    main()

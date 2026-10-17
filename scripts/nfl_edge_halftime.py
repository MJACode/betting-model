"""
NFL halftime second-half lines: are they mis-set relative to the first half?

    python -m scripts.nfl_edge_halftime              (from the worktree root)

Reads ONLY the local cache (scripts/nfl_edge_lib.CACHE) plus the repo's SBR
archive nfl/data/sbr_nfl.json. No database, no Odds API call, no paid endpoint.
nflverse play-by-play 2011-2015 (free GitHub release) was fetched into the cache
dir as pbp_2011..2015.parquet so the efficiency/turnover rules have a fit window.

CONSTRUCTION — written before any second-half outcome was read
==============================================================

Data and cleaning (no 2H outcome is used anywhere in cleaning)
  * Full-game lines come from nflverse (spread_line, total_line), never from
    SBR: SBR's own full-game close columns are transposed in some rows.
    SBR is joined to nflverse on (season, gameday, home_score, away_score), the
    crosscheck_sbr.py key; a swapped-orientation join is tried for the rest.
  * SBR contributes the 2H line and the quarter scores. 1H scores are
    validated against nflverse pbp end-of-Q2 scores; a game whose SBR 1H score
    disagrees with pbp is dropped.
  * SBR 2H defect — mechanism READ FROM THE SCRAPER SOURCE that wrote the
    file (github.com/flancast90/sportsbookreview-scraper, scrapers/
    sportsbookreview.py, NFLOddsScraper._to_schema; same key names). SBR puts
    a line's SPREAD on the favourite's row and its TOTAL on the other row. The
    scraper (a) picks the row with the smaller OPEN number (the open
    favourite's row) and reads open, close AND 2H "spread" from that row, the
    other row's numbers as totals; (b) signs every spread by the CLOSE
    MONEYLINE favourite. So:
      - when the 2H favourite is not the open favourite, the 2H spread and
        total are transposed (|home_2H_spread| > 2H_total), and
      - the sign is the moneyline favourite's, not the 2H favourite's.
    Repair (rule fixed before grading):
      open-favourite side  = moneyline favourite, or the OTHER team when SBR's
                             full-game close is itself transposed (that is the
                             signature of an open favourite that lost favouritism
                             by the close; validated against nflverse below)
      class N  |home_2H_spread| < 2H_total : 2H favourite = open favourite,
               spread = |home_2H_spread|, total = 2H_total
      class S  |home_2H_spread| > 2H_total : 2H favourite = the other team,
               spread = 2H_total, total = |home_2H_spread|
      class E  |home_2H_spread| == 2H_total, or 2H_total < 0 : dropped.
    A first plan - pick the S-row sign that agrees with a line model fitted
    on class N rows - was ABANDONED before grading: by the defect's own
    mechanism the N rows are a selected sample (they never hold a 2H line
    whose favourite differs from the open favourite), so that test leans
    towards the scraped sign by construction.
    Validation: the same scraper logic applied to the FULL-GAME close is
    checked against nflverse's closing spread (an independent source). A
    line-model coherence check and a class-level slope of 2H margin on the
    repaired 2H line (fit seasons only; never used to keep or drop a row) are
    printed as diagnostics. A sensitivity run keeps only rows needing no repair.
    Plausibility (all classes): |2H spread| <= 14; 0.30 <= 2H total /
    full-game total <= 0.70; |2H spread - line model| <= 7, |2H total - line
    model| <= 7; a 2H pick'em (a scraped 0, which is also how the scraper
    stores a blank) is kept only where the line model says |line| <= 3.
    Only games that pass all of these are graded.

Decision time and information
  * Decision time = halftime. Known then: pregame close, 1H score, 1H pbp
    (turnovers, EPA), and OBSERVED game wind (nflverse `wind`, outdoor/open
    roofs only; a recorded wind above 45 mph is treated as missing — one game,
    71 mph) — at halftime the wind has been observed for a half, so it is
    legitimate here (it is NOT legitimate for a pregame bet).
  * Price: the SBR archive carries NO 2H price. Every bet is graded at -110
    (break-even 52.38%); EV is also shown at -105/-115/-120.
  * One bet per proposition: one 2H side or one 2H total per game per rule.
    A 2H wager includes overtime (US book convention): 2H margin = final
    margin - 1H margin.

Halftime state
  exp_m1  = a + b * (home expected margin = -home_point_close), fitted 2011-2016
  dev1    = 1H home margin - exp_m1                 (+ = home beat expectation)
  exp_t1  = c + d * total_line, fitted 2011-2016;  totdev1 = 1H points - exp_t1
  eff     = home offensive EPA/play - away offensive EPA/play, 1H, pass+run plays
  luck    = dev1 - (e + f * eff), fitted 2011-2016  (+ = home scored more than
            its efficiency supports)
  to_m    = away 1H giveaways - home 1H giveaways  (+ = home won the TO battle)

Pre-registered rules (grid; PRIMARY cell in brackets; direction)
  R1  side, |dev1| >= X      X in 3,5,[7],10,14   follow or fade the team that
                                                  beat expectation (chosen on fit)
  R2a total, totdev1 >= +X   X in 3,5,[7],10,14   over or under (chosen on fit)
  R2b total, totdev1 <= -X   X in 3,5,[7],10,14   over or under (chosen on fit)
  R3  2H UNDER, outdoor wind >= W   W in 10,12,[15],18,20   published as stated
  R4  2H DOG, |2H spread| >= D      D in 3.5,5.5,[7],10      published as stated
  R5  side, |luck| >= X      X in 3,5,[7],10      follow or fade (chosen on fit)
  R6  side, |to_m| >= T      T in 1,[2],3         follow or fade (chosen on fit)
  Fit seasons 2011-2016 choose the direction at the primary cell (larger fit
  units). Hold-out seasons 2017-2021 are graded ONCE with that direction.
  Family = the 7 primary hold-out tests, one-sided exact binomial vs 52.38%,
  Benjamini-Hochberg at q = 0.10; the 31 hold-out neighbourhood cells are a
  secondary family, BH reported too.

Controls
  * Placebo: the halftime state (dev1, totdev1, luck, to_m, wind) is permuted
    across games within a season, keeping each game's 2H line and result; 500
    draws per rule. A real mechanism must beat that distribution; the placebo
    itself should sit near the -4.5% vig.
  * R4 control: small 2H dogs (+0.5 to +3) — a big-dog effect should not show.

Forward check (2026 weeks 1-5)
  Halftime window per game = last Q2 play to first Q3 play (pbp time_of_day).
  The in-play full-game spread quotes inside that window at BETTABLE books are
  converted to an implied 2H home line (= live home point + 1H home margin);
  R1 is run with the fit-chosen direction at the modal live point and the best
  bettable price at that point. A sign check only: tens of games at most.

Units: 1 unit = 1 flat bet. Spreads home-relative (home covers when
margin + home_point > 0).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import binomtest

from scripts.nfl_edge_lib import BETTABLE, CACHE, boot_ci, games, profit_units

REPO = Path(__file__).resolve().parents[1]
SBR_PATH = REPO / "nfl" / "data" / "sbr_nfl.json"
FIT = list(range(2011, 2017))
HOLD = list(range(2017, 2022))
PRICE = -110
BE = 110 / 210
PRICE_GRID = (-105, -110, -115, -120)
N_PLACEBO = 500
LOWVOL_PER_SEASON = 10          # a cell averaging <= this many bets/season is "strict"
WIND_MAX_VALID = 45             # nflverse records 71 mph for 2016_13_NYG_PIT: a typo, treated as missing

RULES = {
    "R1_side_dev":      dict(kind="side",  grid=[3, 5, 7, 10, 14], primary=7,  dirs=("follow", "fade")),
    "R2a_fast_1H":      dict(kind="total", grid=[3, 5, 7, 10, 14], primary=7,  dirs=("over", "under")),
    "R2b_slow_1H":      dict(kind="total", grid=[3, 5, 7, 10, 14], primary=7,  dirs=("over", "under")),
    "R3_wind_under":    dict(kind="total", grid=[10, 12, 15, 18, 20], primary=15, dirs=("under",)),
    "R4_2H_dog":        dict(kind="side",  grid=[3.5, 5.5, 7, 10], primary=7,  dirs=("dog",)),
    "R5_luck":          dict(kind="side",  grid=[3, 5, 7, 10], primary=7,      dirs=("follow", "fade")),
    "R6_turnovers":     dict(kind="side",  grid=[1, 2, 3], primary=2,          dirs=("follow", "fade")),
}

# SBR nicknames -> franchise (validation only; the join key is date + score).
NICK = {
    "Cardinals": "ARI", "Arizona": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "BuffaloBills": "BUF",
    "Panthers": "CAR", "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE",
    "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB",
    "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX",
    "Chiefs": "KC", "KCChiefs": "KC", "Kansas": "KC", "KansasCity": "KC",
    "Raiders": "LV", "LVRaiders": "LV", "Oakland": "LV", "LasVegas": "LV",
    "Chargers": "LAC", "SanDiego": "LAC", "LAChargers": "LAC",
    "Rams": "LA", "St.Louis": "LA", "LARams": "LA", "LosAngeles": "LA",
    "Dolphins": "MIA", "Vikings": "MIN",
    "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
    "Eagles": "PHI", "Steelers": "PIT",
    "Fortyniners": "SF", "49ers": "SF", "SanFrancisco": "SF",
    "Seahawks": "SEA", "Buccaneers": "TB", "Tampa": "TB", "TampaBay": "TB",
    "Titans": "TEN", "Tennessee": "TEN",
    "Commanders": "WAS", "Washingtom": "WAS", "Washington": "WAS",
    "Redskins": "WAS", "FootballTeam": "WAS",
}
FRANCHISE = {"STL": "LA", "SD": "LAC", "OAK": "LV", "LAR": "LA"}


def hdr(t):
    print("\n" + "=" * 100 + "\n" + t + "\n" + "=" * 100)


def ols(y, X, names):
    m = sm.OLS(np.asarray(y, float), sm.add_constant(np.asarray(X, float))).fit(cov_type="HC1")
    return m, dict(zip(["const"] + names, m.params)), dict(zip(["const"] + names, m.bse))


# ─── 1. SBR load, join, quarter validation ────────────────────────────────

def load_sbr(g: pd.DataFrame) -> pd.DataFrame:
    d = pd.DataFrame(json.load(open(SBR_PATH, encoding="utf-8")))
    n0 = len(d)
    num = [c for c in d.columns if c not in ("home_team", "away_team")]
    for c in num:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    bad = (~d.home_team.map(lambda x: isinstance(x, str)) |
           ~d.away_team.map(lambda x: isinstance(x, str)) | d.date.isna())
    d = d[~bad].copy()
    d["sbr_row"] = np.arange(len(d))
    n_struct = int(bad.sum())
    d["gameday"] = pd.to_datetime(d.date.astype(int).astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
    q_h = d[["home_1stQtr", "home_2ndQtr", "home_3rdQtr", "home_4thQtr"]].sum(axis=1)
    q_a = d[["away_1stQtr", "away_2ndQtr", "away_3rdQtr", "away_4thQtr"]].sum(axis=1)
    qbad = ((d.home_final - q_h) < 0) | ((d.away_final - q_a) < 0) | q_h.isna() | q_a.isna()
    d = d[~qbad].copy()

    gg = g[(g.season >= 2011) & (g.season <= 2021)][
        ["game_id", "season", "week", "game_type", "gameday", "home_team", "away_team",
         "home_score", "away_score", "spread_line", "total_line", "roof", "wind"]].copy()
    key = ["season", "gameday", "home_score", "away_score"]
    a = d.rename(columns={"home_final": "home_score", "away_final": "away_score"})
    m1 = gg.merge(a, on=key, how="inner", suffixes=("", "_sbr"))
    m1["flip"] = False
    rest = a[~a.set_index(key).index.isin(m1.set_index(key).index)].copy()
    # swapped orientation: SBR home = nflverse away
    sw = rest.rename(columns={"home_score": "away_score", "away_score": "home_score"})
    for x, y in (("home_1stQtr", "away_1stQtr"), ("home_2ndQtr", "away_2ndQtr"),
                 ("home_3rdQtr", "away_3rdQtr"), ("home_4thQtr", "away_4thQtr"),
                 ("home_team", "away_team")):
        sw[x], sw[y] = rest[y].values, rest[x].values
    m2 = gg.merge(sw, on=key, how="inner", suffixes=("", "_sbr"))
    m2["flip"] = True
    m = pd.concat([m1, m2], ignore_index=True)
    fr = lambda s: s.map(lambda t: FRANCHISE.get(t, t))
    agree = (fr(m.home_team) == m.home_team_sbr.map(NICK)) & (fr(m.away_team) == m.away_team_sbr.map(NICK))
    # same date + same score in two games: keep the nickname-confirmed pairing, drop the rest
    multi = m.game_id.duplicated(keep=False) | m.sbr_row.duplicated(keep=False)
    m, agree = m[~multi | agree].copy(), agree[~multi | agree]
    dup = m.game_id.duplicated(keep=False) | m.sbr_row.duplicated(keep=False)
    m, agree = m[~dup].copy(), agree[~dup]
    unm = sorted(set(m.home_team_sbr[m.home_team_sbr.map(NICK).isna()]) |
                 set(m.away_team_sbr[m.away_team_sbr.map(NICK).isna()]))

    hdr("1. SBR ARCHIVE: load and join (full-game lines taken from nflverse, never SBR)")
    print(f"SBR rows {n0} | structurally corrupt dropped {n_struct} | quarter sums exceed final, dropped {int(qbad.sum())}")
    print(f"joined to nflverse on (season, gameday, home_score, away_score): {len(m1)} direct + "
          f"{len(m2)} swapped orientation; same-date-same-score multi-matches {int(multi.sum())} resolved by nickname, unresolved dropped {int(dup.sum())}; "
          f"nflverse 2011-2021 games {len(gg)}")
    print(f"nickname agreement on joined rows (franchise-normalised): {agree.mean():.1%} "
          f"({int((~agree).sum())} disagree); SBR names not in map: {unm}")
    m = m[agree | m.home_team_sbr.map(NICK).isna() | m.away_team_sbr.map(NICK).isna()].copy()
    print(f"kept after nickname check: {len(m)}")
    m["m1"] = (m.home_1stQtr + m.home_2ndQtr) - (m.away_1stQtr + m.away_2ndQtr)
    m["t1"] = m.home_1stQtr + m.home_2ndQtr + m.away_1stQtr + m.away_2ndQtr
    m["margin"] = m.home_score - m.away_score
    m["total_pts"] = m.home_score + m.away_score
    m["m2"] = m.margin - m.m1
    m["t2_act"] = m.total_pts - m.t1
    m["hp"] = -m.spread_line                     # pregame close, home-relative point
    # raw 2H columns in nflverse orientation (a flipped SBR row flips the spread sign)
    m["a_raw"] = np.where(m.flip, -m.home_2H_spread, m.home_2H_spread)
    m["b_raw"] = m["2H_total"]
    return m


def pbp_halftime(seasons) -> pd.DataFrame:
    cols = ["game_id", "season", "play_id", "qtr", "posteam", "home_team", "away_team",
            "play_type", "epa", "interception", "fumble_lost", "fumbled_1_team",
            "total_home_score", "total_away_score"]
    out = []
    for s in seasons:
        p = pd.read_parquet(CACHE / f"pbp_{s}.parquet", columns=cols)
        p = p.sort_values(["game_id", "play_id"])
        h = p[p.qtr <= 2].copy()
        last = h.groupby("game_id").agg(h1_home=("total_home_score", "last"),
                                         h1_away=("total_away_score", "last"),
                                         home_team=("home_team", "first"),
                                         away_team=("away_team", "first"))
        off = h[h.play_type.isin(["pass", "run"]) & h.epa.notna()]
        e = off.groupby(["game_id", "posteam"]).epa.mean().rename("epa_pp").reset_index()
        gv_int = h[h.interception == 1].groupby(["game_id", "posteam"]).size().rename("n").reset_index()
        fl = h[h.fumble_lost == 1].copy()
        fl["team"] = fl.fumbled_1_team.fillna(fl.posteam)
        gv_fum = fl.groupby(["game_id", "team"]).size().rename("n").reset_index()
        gv = pd.concat([gv_int.rename(columns={"posteam": "team"}), gv_fum]).groupby(
            ["game_id", "team"]).n.sum().reset_index()
        last = last.reset_index()
        for side in ("home", "away"):
            ee = e.rename(columns={"posteam": f"{side}_team", "epa_pp": f"epa_{side}"})
            last = last.merge(ee, on=["game_id", f"{side}_team"], how="left")
            gg = gv.rename(columns={"team": f"{side}_team", "n": f"gv_{side}"})
            last = last.merge(gg, on=["game_id", f"{side}_team"], how="left")
        last[["gv_home", "gv_away"]] = last[["gv_home", "gv_away"]].fillna(0)
        last["eff"] = last.epa_home - last.epa_away
        last["to_m"] = last.gv_away - last.gv_home
        last["season"] = s
        out.append(last[["game_id", "season", "h1_home", "h1_away", "eff", "to_m"]])
        del p, h, off
    return pd.concat(out, ignore_index=True)


# ─── 2. 2H line repair ────────────────────────────────────────────────────

def _line_models(x: pd.DataFrame):
    ms, cs, _ = ols(x.s2, x[["hp", "m1"]], ["hp", "m1"])
    mt, ct, _ = ols(x.t2, x[["total_line", "t1"]], ["total_line", "t1"])
    return ms, cs, mt, ct


def clean_2h(m: pd.DataFrame) -> pd.DataFrame:
    a, b = m.a_raw, m.b_raw
    m["cls"] = np.select([b < 0, a.abs() == b, a.abs() < b, a.abs() > b], ["E", "E", "N", "S"], "E")
    # scraper sign = close-moneyline favourite (home_ml < away_ml -> home favoured -> negative)
    s_ml = np.where(m.home_close_ml < m.away_close_ml, -1.0, 1.0)
    s_ml = np.where(m.flip, -s_ml, s_ml)
    sbr_close = pd.Series(np.where(m.flip, -m.home_close_spread, m.home_close_spread), index=m.index)
    close_T = sbr_close.abs() > m.close_over_under
    m["close_T"] = close_T

    hdr("2. SBR 2H LINE REPAIR (the scraper's own logic; no 2H outcome decides any row)")
    print("class counts (N = 2H columns as labelled, S = 2H spread/total transposed, E = unusable)\n"
          "x whether SBR's FULL-GAME close is itself transposed (close_T):")
    print(pd.crosstab(m.cls, m.close_T, margins=True).to_string())
    print(f"share of raw |home_2H_spread| > 14: {(a.abs() > 14).mean():.1%}")

    print("\nVALIDATION on the full-game close vs nflverse closing spread "
          "(rows with |nflverse| >= 1 and a non-zero SBR number):")
    rows = []
    for lab, msk, cand in (
            ("close not transposed: SBR sign as scraped", ~close_T, sbr_close),
            ("close transposed: magnitude = SBR 'total', sign as scraped (ML favourite)", close_T,
             np.sign(sbr_close) * m.close_over_under),
            ("close transposed: same, sign flipped", close_T, -np.sign(sbr_close) * m.close_over_under)):
        cand = pd.Series(cand, index=m.index)
        x = msk & (m.hp.abs() >= 1) & (cand != 0)
        c = cand[x]
        rows.append(dict(rows=lab, n=int(x.sum()),
                         sign_agrees_with_nflverse_pct=round(100 * (np.sign(c) == np.sign(m.hp[x])).mean(), 1),
                         median_abs_diff=round((c - m.hp[x]).abs().median(), 2)))
    print(fmt(pd.DataFrame(rows)))
    print("=> the scraper signs by the moneyline favourite, and a transposed close marks an open favourite that\n"
          "   lost favouritism by the close, exactly as the source reads. The 2H column passes through the same code.")

    s_of = np.where(close_T, -s_ml, s_ml)            # open-favourite side (-1 = home)
    s2_rule = pd.Series(np.where(m.cls == "N", s_of * a.abs(), np.where(m.cls == "S", -s_of * b, np.nan)), index=m.index)
    t2_rule = pd.Series(np.where(m.cls == "N", b, np.where(m.cls == "S", a.abs(), np.nan)), index=m.index)
    s2_asis = pd.Series(np.where(m.cls == "N", a, np.where(m.cls == "S", np.sign(a) * b, np.nan)), index=m.index)
    m["s2"], m["t2"] = s2_rule, t2_rule
    changed = (np.sign(s2_rule) != np.sign(s2_asis)) & (m.cls != "E")
    print(f"\n2H favourite changed by the repair vs the scraped sign: {int(changed.sum())} rows "
          f"(N & close transposed {int((changed & (m.cls == 'N') & close_T).sum())}, "
          f"S & close not transposed {int((changed & (m.cls == 'S') & ~close_T).sum())})")

    fit = m.season.isin(FIT) & (m.cls != "E")
    print("\nDIAGNOSTIC 1 - line-model coherence, fit seasons, all N+S rows, 2H home point ~ pregame point + 1H margin:")
    for lab, s2 in (("repair rule", s2_rule), ("scraped sign kept", s2_asis)):
        x = m[fit].assign(s2=s2[fit])
        ms, cs, _, _ = _line_models(x)
        print(f"  {lab:18s} R2={ms.rsquared:.3f} resid sd={np.sqrt(ms.scale):.2f}  "
              f"coef pregame {cs['hp']:.3f}  coef 1H margin {cs['m1']:+.3f}")
    print("DIAGNOSTIC 2 - class-level slope of 2H home margin on -(2H home point), fit seasons, HC1\n"
          "  (a correct line has slope near 1; printed only, never used to keep or drop a row):")
    for lab, msk in (("N, close not transposed (no repair)", (m.cls == "N") & ~close_T),
                     ("N, close transposed (sign flipped)", (m.cls == "N") & close_T),
                     ("S, close not transposed (sign flipped)", (m.cls == "S") & ~close_T),
                     ("S, close transposed (sign kept)", (m.cls == "S") & close_T)):
        for lab2, s2 in (("repair", s2_rule), ("scraped", s2_asis)):
            x = fit & msk
            if x.sum() < 20:
                continue
            _, c, se = ols(m.m2[x], -s2[x], ["line"])
            print(f"  {lab:40s} {lab2:8s} n={int(x.sum()):4d} slope={c['line']:+.2f} ({se['line']:.2f})")

    ms, cs, mt, ct = _line_models(m[fit & m.s2.notna()])
    m["pred_s"] = cs["const"] + cs["hp"] * m.hp + cs["m1"] * m.m1
    m["pred_t"] = ct["const"] + ct["total_line"] * m.total_line + ct["t1"] * m.t1
    print(f"\nline model on repaired rows, fit seasons (used by the plausibility screen):\n"
          f"  2H home point = {cs['const']:+.3f} + {cs['hp']:.3f}*pregame_home_point + {cs['m1']:+.3f}*1H_home_margin"
          f"   R2={ms.rsquared:.3f}  resid sd={np.sqrt(ms.scale):.2f}\n"
          f"  2H total      = {ct['const']:+.3f} + {ct['total_line']:.3f}*full_total + {ct['t1']:+.3f}*1H_points"
          f"   R2={mt.rsquared:.3f}  resid sd={np.sqrt(mt.scale):.2f}")
    r = pd.DataFrame(index=m.index)
    r["unusable_E"] = m.cls == "E"
    r["no_line"] = (m.cls != "E") & (m.total_line.isna() | m.spread_line.isna())
    r["abs_spread_gt14"] = m.s2.abs() > 14
    ratio = m.t2 / m.total_line
    r["total_ratio_out"] = (ratio < 0.30) | (ratio > 0.70)
    r["spread_vs_model_gt7"] = (m.s2 - m.pred_s).abs() > 7
    r["total_vs_model_gt7"] = (m.t2 - m.pred_t).abs() > 7
    r["pickem_but_model_gt3"] = (m.s2 == 0) & (m.pred_s.abs() > 3)
    keep = ~r.any(axis=1)
    print("\nplausibility screen (a row can fail several):")
    print(r.sum().to_string())
    by = pd.DataFrame({"season": m.season, "keep": keep}).groupby("season").keep.agg(["size", "sum"])
    by.columns = ["joined", "kept"]
    print("\nkept per season:\n" + by.T.to_string())
    m["keep"] = keep
    m["no_repair"] = (m.cls == "N") & ~close_T
    print(f"kept rows needing no repair (sensitivity subset): {int((keep & m.no_repair).sum())} of {int(keep.sum())}")
    return m


# ─── 3. rules and grading ─────────────────────────────────────────────────

def bets(df: pd.DataFrame, rule: str, cut, direction: str, st=None) -> pd.DataFrame:
    """One bet per game. st: optional replacement state frame (placebo)."""
    s = df if st is None else st
    kind = RULES[rule]["kind"] if rule in RULES else "side"
    if rule == "R1_side_dev":
        msk = s.dev1.abs() >= cut
        bet_home = (s.dev1 > 0) if direction == "follow" else (s.dev1 < 0)
    elif rule == "R2a_fast_1H":
        msk = s.totdev1 >= cut
        over = pd.Series(direction == "over", index=df.index)
    elif rule == "R2b_slow_1H":
        msk = s.totdev1 <= -cut
        over = pd.Series(direction == "over", index=df.index)
    elif rule == "R3_wind_under":
        msk = s.wind_out >= cut
        over = pd.Series(False, index=df.index)
    elif rule == "R4_2H_dog":
        msk = df.s2.abs() >= cut
        bet_home = df.s2 > 0
    elif rule == "R4_control_small_dog":
        msk = (df.s2.abs() >= 0.5) & (df.s2.abs() <= 3)
        bet_home = df.s2 > 0
    elif rule == "R5_luck":
        msk = s.luck.abs() >= cut
        bet_home = (s.luck > 0) if direction == "follow" else (s.luck < 0)
    elif rule == "R6_turnovers":
        msk = s.to_m.abs() >= cut
        bet_home = (s.to_m > 0) if direction == "follow" else (s.to_m < 0)
    else:
        raise ValueError(rule)
    msk = msk.fillna(False).values
    x = df[msk].copy()
    if kind == "side" or rule == "R4_control_small_dog":
        bh = np.asarray(bet_home)[msk]
        cov = x.m2 + x.s2
        x["won"] = np.where(bh, cov > 0, cov < 0).astype(int)
        x["push"] = (cov == 0).astype(int)
    else:
        ov = np.asarray(over)[msk]
        dd = x.t2_act - x.t2
        x["won"] = np.where(ov, dd > 0, dd < 0).astype(int)
        x["push"] = (dd == 0).astype(int)
    x["profit"] = profit_units(x.won, PRICE, x.push)
    return x


def stats(x: pd.DataFrame, n_seasons: int) -> dict:
    if len(x) == 0:
        return dict(bets=0, units=0.0, roi=np.nan, lo=np.nan, hi=np.nan, win=np.nan, per_season=0.0, p=np.nan)
    roi, (lo, hi) = boot_ci(x.profit, x.game_id)
    dec = x[x.push == 0]
    p = binomtest(int(dec.won.sum()), len(dec), BE, alternative="greater").pvalue if len(dec) else np.nan
    return dict(bets=len(x), units=round(x.profit.sum(), 2), roi=round(100 * roi, 1),
                lo=round(100 * lo, 1), hi=round(100 * hi, 1),
                win=round(100 * dec.won.mean(), 1) if len(dec) else np.nan,
                per_season=round(len(x) / n_seasons, 1), p=p)


def bh(p: np.ndarray, q=0.10) -> np.ndarray:
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    thr = q * np.arange(1, n + 1) / n
    ok = p[o] <= thr
    k = np.max(np.where(ok)[0]) + 1 if ok.any() else 0
    rej = np.zeros(n, bool)
    rej[o[:k]] = True
    return rej


def fmt(df):
    return df.to_string(index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-only", action="store_true")
    args = ap.parse_args()
    pd.set_option("display.width", 250)

    g = games()
    m = load_sbr(g)

    # 1H scores: SBR quarters vs pbp end of Q2
    ph = pbp_halftime(range(2011, 2022))
    m = m.merge(ph.drop(columns="season"), on="game_id", how="left")
    have = m.h1_home.notna()
    ok1 = (m.h1_home == (m.home_1stQtr + m.home_2ndQtr)) & (m.h1_away == (m.away_1stQtr + m.away_2ndQtr))
    print(f"\n1H score check vs nflverse pbp: {int(have.sum())} games with pbp; SBR 1H score agrees in "
          f"{ok1[have].mean():.1%}; disagreeing games dropped: {int((have & ~ok1).sum())}; "
          f"games without pbp: {int((~have).sum())}")
    m = m[~(have & ~ok1)].copy()

    m = clean_2h(m)

    # expectations, fitted on 2011-2016 joined games (state only, outcome-free)
    f = m[m.season.isin(FIT)]
    _, c1, _ = ols(f.m1, f[["hp"]], ["hp"])
    _, c2, _ = ols(f.t1, f[["total_line"]], ["total_line"])
    global _EXP_M1
    _EXP_M1 = (c1["const"], c1["hp"])
    m["exp_m1"] = c1["const"] + c1["hp"] * m.hp
    m["dev1"] = m.m1 - m.exp_m1
    m["exp_t1"] = c2["const"] + c2["total_line"] * m.total_line
    m["totdev1"] = m.t1 - m.exp_t1
    ff = m[m.season.isin(FIT) & m.eff.notna()]
    _, c3, _ = ols(ff.dev1, ff[["eff"]], ["eff"])
    m["luck"] = m.dev1 - (c3["const"] + c3["eff"] * m.eff)
    m["wind_out"] = np.where(m.roof.isin(["outdoors", "open"]) & (m.wind <= WIND_MAX_VALID), m.wind, np.nan)
    hdr("3. HALFTIME STATE (fits on 2011-2016)")
    print(f"expected 1H home margin = {c1['const']:+.3f} + {c1['hp']:.3f}*pregame_home_point  "
          f"(i.e. {-c1['hp']:.3f} of the full-game expected margin)")
    print(f"expected 1H points      = {c2['const']:+.3f} + {c2['total_line']:.3f}*full_total")
    print(f"1H deviation explained by EPA/play margin: dev1 = {c3['const']:+.3f} + {c3['eff']:.2f}*eff")
    d = m[m.keep]
    print(f"graded games: {len(d)}  (fit {int(d.season.isin(FIT).sum())}, hold-out {int(d.season.isin(HOLD).sum())})")
    print("state distribution on graded games:")
    print(d[["dev1", "totdev1", "eff", "luck", "to_m", "wind_out", "s2", "t2"]].describe().round(2).to_string())
    if args.clean_only:
        return

    # ── mechanism: does the market's 2H line react to the 1H like the outcome does?
    hdr("4. MECHANISM: 2H line vs 2H outcome on the same halftime state (OLS, HC1 SE)")
    rows = []
    for per, seas in (("fit 2011-16", FIT), ("hold 2017-21", HOLD)):
        x = d[d.season.isin(seas)]
        for lab, y, X, nm in (
                ("market 2H home point", x.s2, x[["hp", "dev1"]], ["hp", "dev1"]),
                ("fair 2H home point = -(2H margin)", -x.m2, x[["hp", "dev1"]], ["hp", "dev1"]),
                ("market 2H total", x.t2, x[["total_line", "totdev1"]], ["total_line", "totdev1"]),
                ("2H points scored", x.t2_act, x[["total_line", "totdev1"]], ["total_line", "totdev1"])):
            mm, cc, se = ols(y, X, nm)
            rows.append(dict(period=per, y=lab, n=len(x),
                             b_pregame=f"{cc[nm[0]]:+.3f} ({se[nm[0]]:.3f})",
                             b_1H_dev=f"{cc[nm[1]]:+.3f} ({se[nm[1]]:.3f})", R2=round(mm.rsquared, 3)))
        mm0, _, _ = ols(x.s2, x[["hp"]], ["hp"])
        rows.append(dict(period=per, y="market 2H home point on pregame only", n=len(x),
                         b_pregame="", b_1H_dev="", R2=round(mm0.rsquared, 3)))
    print(fmt(pd.DataFrame(rows)))
    print("Read: if market b_1H_dev differs from fair b_1H_dev, the 2H line mis-reacts to the 1H score.\n"
          "A fair b_1H_dev more negative than the market's = the team that beat expectation keeps covering (market under-reacts).")

    # ── neighbourhoods, directions
    fitd, hold = d[d.season.isin(FIT)], d[d.season.isin(HOLD)]
    chosen = {}
    hdr(f"5. NEIGHBOURHOODS — every cell, at -110 (SBR has NO 2H price). "
        f"'*' = strict low-volume cell (<= {LOWVOL_PER_SEASON} bets/season)")
    allrows = []
    for rule, spec in RULES.items():
        for direction in spec["dirs"]:
            for cut in spec["grid"]:
                for per, x, ns in (("fit", fitd, len(FIT)), ("hold", hold, len(HOLD))):
                    s = stats(bets(x, rule, cut, direction), ns)
                    allrows.append(dict(rule=rule, dir=direction, cut=cut, period=per, **s))
    nb = pd.DataFrame(allrows)
    for rule, spec in RULES.items():
        pf = nb[(nb.rule == rule) & (nb.period == "fit") & (nb.cut == spec["primary"])]
        chosen[rule] = pf.sort_values("units", ascending=False).iloc[0].dir
    nb["chosen_dir"] = nb.apply(lambda r: r.dir == chosen[r.rule], axis=1)
    nb["strict"] = np.where(nb.per_season <= LOWVOL_PER_SEASON, "*", "")
    nb["primary"] = nb.apply(lambda r: "P" if r.cut == RULES[r.rule]["primary"] else "", axis=1)
    show = nb.copy()
    show["ci90"] = show.apply(lambda r: f"[{r.lo:+.1f},{r.hi:+.1f}]", axis=1)
    show["p_1s"] = show.p.map(lambda v: f"{v:.3f}" if pd.notna(v) else "")
    for rule in RULES:
        print(f"\n{rule}   fit-chosen direction at primary cell: {chosen[rule].upper()}")
        sub = show[show.rule == rule]
        w = sub.pivot_table(index=["dir", "cut", "primary"], columns="period",
                            values=["bets", "units", "roi", "ci90", "win", "strict"], aggfunc="first")
        w.columns = [f"{b}_{a}" for a, b in w.columns]
        order = [f"{p}_{k}" for p in ("fit", "hold") for k in ("bets", "units", "roi", "ci90", "win", "strict")]
        print(w[order].reset_index().to_string(index=False))

    # ── primary family + BH
    hdr("6. PRIMARY HOLD-OUT TESTS (2017-2021, graded once, fit-chosen direction), BH q=0.10")
    prim = nb[(nb.primary == "P") & nb.chosen_dir & (nb.period == "hold")].copy()
    prim["BH_reject"] = bh(prim.p.fillna(1).values)
    prim["p_1s"] = prim.p.round(4)
    print(fmt(prim[["rule", "dir", "cut", "bets", "per_season", "units", "roi", "lo", "hi", "win", "p_1s", "BH_reject"]]))
    sec = nb[nb.chosen_dir & (nb.period == "hold")].copy()
    sec["BH_reject"] = bh(sec.p.fillna(1).values)
    print(f"secondary family: {len(sec)} hold-out cells in the fit-chosen direction; BH q=0.10 rejections: "
          f"{int(sec.BH_reject.sum())}; smallest p {sec.p.min():.4f}")
    print(f"comparisons examined in total (all cells, both periods, every direction): {len(nb)}")

    # ── price grid on the primary cells
    hdr("7. PRICE GRID, primary cells (break-even win% at -105/-110/-115/-120 = 51.2/52.4/53.5/54.5)")
    rows = []
    for rule, spec in RULES.items():
        for per, x in (("fit", fitd), ("hold", hold)):
            b = bets(x, rule, spec["primary"], chosen[rule])
            r = dict(rule=rule, dir=chosen[rule], period=per, bets=len(b),
                     win_pct_ex_push=round(100 * b[b.push == 0].won.mean(), 1) if len(b) else np.nan)
            for pr in PRICE_GRID:
                r[f"roi_{pr}"] = round(100 * profit_units(b.won, pr, b.push).mean(), 1) if len(b) else np.nan
            rows.append(r)
    print(fmt(pd.DataFrame(rows)))

    hdr("7b. SENSITIVITY: primary cells on the rows that needed NO repair (2H columns as labelled, close not transposed)")
    rows = []
    for rule, spec in RULES.items():
        for per, x, ns in (("fit", fitd[fitd.no_repair], len(FIT)), ("hold", hold[hold.no_repair], len(HOLD))):
            st = stats(bets(x, rule, spec["primary"], chosen[rule]), ns)
            rows.append(dict(rule=rule, dir=chosen[rule], period=per, bets=st["bets"], units=st["units"],
                             roi=st["roi"], ci90=f"[{st['lo']:+.1f},{st['hi']:+.1f}]", win=st["win"]))
    print(fmt(pd.DataFrame(rows)))
    print("(this subset is selected on the 2H line itself - it under-samples games where the 2H favourite is not the\n"
          " open favourite - so it is a robustness read, not the primary sample)")

    # ── per season, early/late, bets per season per cut
    hdr("8. EVERY SEASON, primary cell, fit-chosen direction (2011-16 fit, 2017-21 hold-out)")
    rows = []
    for rule, spec in RULES.items():
        b = bets(d, rule, spec["primary"], chosen[rule])
        for s in range(2011, 2022):
            x = b[b.season == s]
            st = stats(x, 1)
            rows.append(dict(rule=rule, season=s, bets=st["bets"], units=st["units"], roi=st["roi"],
                             ci90=f"[{st['lo']:+.1f},{st['hi']:+.1f}]" if st["bets"] else ""))
    ps = pd.DataFrame(rows)
    print(ps.pivot(index="season", columns="rule", values="units").to_string())
    print("\nbets:")
    print(ps.pivot(index="season", columns="rule", values="bets").to_string())
    print("\nROI % with 90% CI per season:")
    for rule in RULES:
        x = ps[ps.rule == rule]
        print(f"  {rule:16s} " + "  ".join(f"{r.season}:{r.roi:+.0f}{r.ci90}" if r.bets else f"{r.season}:-" for r in x.itertuples()))

    hdr("9. EARLY (weeks 1-9) vs LATE (weeks 10+ incl. playoffs), primary cell")
    rows = []
    for rule, spec in RULES.items():
        b = bets(d, rule, spec["primary"], chosen[rule])
        b["half"] = np.where(b.week <= 9, "early", "late")
        b["per"] = np.where(b.season.isin(FIT), "fit", "hold")
        for (per, h), x in b.groupby(["per", "half"]):
            st = stats(x, len(FIT) if per == "fit" else len(HOLD))
            rows.append(dict(rule=rule, period=per, half=h, bets=st["bets"], units=st["units"], roi=st["roi"],
                             ci90=f"[{st['lo']:+.1f},{st['hi']:+.1f}]"))
    print(fmt(pd.DataFrame(rows)))

    hdr("10. BETS PER SEASON AT EACH CUT (same count in either direction)")
    rows = []
    for rule, spec in RULES.items():
        for cut in spec["grid"]:
            b = bets(d, rule, cut, spec["dirs"][0])
            c = b.groupby("season").size().reindex(range(2011, 2022), fill_value=0)
            rows.append(dict(rule=rule, cut=cut, **{str(k): int(v) for k, v in c.items()}))
    print(fmt(pd.DataFrame(rows)))

    # ── placebo
    hdr(f"11. PLACEBO: halftime state permuted within season ({N_PLACEBO} draws), primary cell, hold-out")
    rng = np.random.default_rng(11)
    rows = []
    hd = hold.reset_index(drop=True)
    for rule, spec in RULES.items():
        if rule == "R4_2H_dog":
            continue
        real = stats(bets(hd, rule, spec["primary"], chosen[rule]), len(HOLD))
        sims = []
        for _ in range(N_PLACEBO):
            st = hd[["dev1", "totdev1", "luck", "to_m", "wind_out", "season"]].copy()
            for s, idx in st.groupby("season").groups.items():
                idx = np.asarray(idx)
                perm = rng.permutation(idx)
                st.loc[idx, ["dev1", "totdev1", "luck", "to_m"]] = st.loc[perm, ["dev1", "totdev1", "luck", "to_m"]].values
                o = idx[hd.loc[idx, "wind_out"].notna().values]
                st.loc[o, "wind_out"] = st.loc[rng.permutation(o), "wind_out"].values
            b = bets(hd, rule, spec["primary"], chosen[rule], st=st)
            sims.append(b.profit.mean() if len(b) else np.nan)
        sims = np.array(sims)
        rows.append(dict(rule=rule, dir=chosen[rule], real_bets=real["bets"], real_roi=real["roi"],
                         placebo_mean_roi=round(100 * np.nanmean(sims), 1),
                         placebo_p05=round(100 * np.nanquantile(sims, .05), 1),
                         placebo_p95=round(100 * np.nanquantile(sims, .95), 1),
                         share_placebo_ge_real=round(np.mean(sims >= real["roi"] / 100), 3)))
    print(fmt(pd.DataFrame(rows)))
    print("\nR4 control — small 2H dogs (+0.5..+3), bet the dog, at -110:")
    for per, x, ns in (("fit", fitd, len(FIT)), ("hold", hold, len(HOLD))):
        st = stats(bets(x, "R4_control_small_dog", None, "dog"), ns)
        print(f"  {per:4s} bets {st['bets']:4d}  units {st['units']:+7.2f}  ROI {st['roi']:+5.1f}%  "
              f"CI90 [{st['lo']:+.1f},{st['hi']:+.1f}]  win {st['win']}%")

    hdr("11a. PUBLISHED RULES AS STATED, POOLED 2011-2021 (no parameter is fitted for R3/R4, so every season is out-of-sample)")
    rows = []
    for rule in ("R3_wind_under", "R4_2H_dog"):
        st = stats(bets(d, rule, RULES[rule]["primary"], chosen[rule]), len(FIT) + len(HOLD))
        rows.append(dict(rule=rule, dir=chosen[rule], cut=RULES[rule]["primary"], bets=st["bets"],
                         per_season=st["per_season"], units=st["units"], roi=st["roi"],
                         ci90=f"[{st['lo']:+.1f},{st['hi']:+.1f}]", win=st["win"], p_1s=round(st["p"], 4)))
    print(fmt(pd.DataFrame(rows)))
    print("BH over the 7 primary rules at q=0.10 needs the smallest p <= 0.0143 to reject anything.")
    rng0 = np.random.default_rng(13)
    dd0 = d.reset_index(drop=True)
    real = bets(dd0, "R3_wind_under", 15, "under").profit.mean()
    sims = []
    for _ in range(N_PLACEBO):
        st = dd0[["dev1", "totdev1", "luck", "to_m", "wind_out", "season"]].copy()
        for _, idx in st.groupby("season").groups.items():
            idx = np.asarray(idx)
            o = idx[dd0.loc[idx, "wind_out"].notna().values]
            st.loc[o, "wind_out"] = st.loc[rng0.permutation(o), "wind_out"].values
        sims.append(bets(dd0, "R3_wind_under", 15, "under", st=st).profit.mean())
    sims = np.array(sims)
    print(f"R3 pooled placebo (wind permuted among outdoor games within season, {N_PLACEBO} draws): "
          f"mean {100 * sims.mean():+.1f}%, 5-95% [{100 * np.quantile(sims, .05):+.1f}, {100 * np.quantile(sims, .95):+.1f}], "
          f"share >= real ({100 * real:+.1f}%): {np.mean(sims >= real):.3f}")

    print("\nSame R3 games, the FULL-GAME under at the nflverse closing total (-110): does halftime add anything\n"
          "beyond the pregame wind effect the repo's full-game wind model already bets?")
    rows = []
    for per, x, ns in (("fit", fitd, len(FIT)), ("hold", hold, len(HOLD)), ("pooled", d, len(FIT) + len(HOLD))):
        b = bets(x, "R3_wind_under", 15, "under")
        fg = b.total_pts - b.total_line
        y = b.assign(won=(fg < 0).astype(int), push=(fg == 0).astype(int))
        y["profit"] = profit_units(y.won, PRICE, y.push)
        st_fg = stats(y, ns)
        st_2h = stats(b, ns)
        rows.append(dict(period=per, bets=len(b), roi_2H_under=st_2h["roi"],
                         roi_full_game_under=st_fg["roi"],
                         ci90_full_game=f"[{st_fg['lo']:+.1f},{st_fg['hi']:+.1f}]",
                         both_won=int(((b.won == 1) & (y.won == 1)).sum())))
    print(fmt(pd.DataFrame(rows)))

    hdr("11b. HOME/AWAY MIX of the side rules at the primary cell (2H home sides covered 46% in 2017-21; see 11c)")
    rows = []
    for rule in ("R1_side_dev", "R4_2H_dog", "R5_luck", "R6_turnovers"):
        for per, x in (("fit", fitd), ("hold", hold)):
            b = bets(x, rule, RULES[rule]["primary"], chosen[rule])
            cov = b.m2 + b.s2
            won_home = (cov > 0)
            # a bet is on the home side when winning it means the home side covered
            on_home = (b.won.astype(bool) == won_home) & (cov != 0)
            dec = cov != 0
            rows.append(dict(rule=rule, dir=chosen[rule], period=per, bets=len(b),
                             away_share_pct=round(100 * (1 - on_home[dec].mean()), 1)))
    print(fmt(pd.DataFrame(rows)))

    hdr("11c. CONTROL: blanket 2H bets at -110 (every game), the base rate each rule must beat")
    rows = []
    for per, x, ns in (("fit", fitd, len(FIT)), ("hold", hold, len(HOLD))):
        cov = x.m2 + x.s2
        dd = x.t2_act - x.t2
        outdoor = x.wind_out.notna()
        for lab, won, push, msk in (
                ("every 2H under", dd < 0, dd == 0, np.ones(len(x), bool)),
                ("every 2H under, outdoor games", dd < 0, dd == 0, outdoor.values),
                ("every 2H over", dd > 0, dd == 0, np.ones(len(x), bool)),
                ("every 2H home side", cov > 0, cov == 0, np.ones(len(x), bool)),
                ("every 2H favourite", np.where(x.s2 < 0, cov > 0, cov < 0), cov == 0, (x.s2 != 0).values),
                ("every 2H underdog", np.where(x.s2 > 0, cov > 0, cov < 0), cov == 0, (x.s2 != 0).values)):
            y = x[msk].copy()
            y["won"] = np.asarray(won)[msk].astype(int)
            y["push"] = np.asarray(push)[msk].astype(int)
            y["profit"] = profit_units(y.won, PRICE, y.push)
            st = stats(y, ns)
            rows.append(dict(control=lab, period=per, bets=st["bets"], units=st["units"], roi=st["roi"],
                             ci90=f"[{st['lo']:+.1f},{st['hi']:+.1f}]", win=st["win"]))
    print(fmt(pd.DataFrame(rows)))

    forward_2026(g, chosen["R1_side_dev"])
    backfill_cost(g)


# ─── 4. 2026 forward check on the live full-game spread at halftime ───────

def forward_2026(g: pd.DataFrame, direction: str):
    hdr(f"12. 2026 FORWARD CHECK: R1 ({direction.upper()}) on the LIVE FULL-GAME spread at halftime")
    p = pd.read_parquet(CACHE / "pbp_2026.parquet",
                        columns=["game_id", "play_id", "qtr", "time_of_day", "total_home_score", "total_away_score"])
    p["t"] = pd.to_datetime(p.time_of_day, utc=True, errors="coerce", format="mixed")
    p = p.sort_values(["game_id", "play_id"])
    h = p[p.qtr <= 2]
    ht = h.groupby("game_id").agg(h1_home=("total_home_score", "last"), h1_away=("total_away_score", "last"),
                                  ht_start=("t", "max"))
    ht["ht_end"] = p[p.qtr == 3].groupby("game_id").t.min()
    ht = ht.reset_index()
    gg = g[g.season == 2026][["game_id", "week", "spread_line", "home_score", "away_score"]]
    ht = ht.merge(gg, on="game_id", how="left")
    ht = ht[ht.home_score.notna() & ht.ht_start.notna() & ht.ht_end.notna()].copy()
    ht["m1"] = ht.h1_home - ht.h1_away
    ht["result"] = ht.home_score - ht.away_score
    ht["hp"] = -ht.spread_line
    print(f"2026 games with complete pbp and a final score: {len(ht)} (weeks {sorted(ht.week.unique().tolist())}); "
          f"median halftime window {((ht.ht_end - ht.ht_start).dt.total_seconds() / 60).median():.1f} min")

    o = pd.read_parquet(CACHE / "odds_2026.parquet", filters=[("bookmaker", "in", BETTABLE)])
    o = o[o.snapshot_at > o.commence_time]
    o["game_id"] = o.game_id.str.replace("^NFL_", "", regex=True)
    for c in ("point", "price_home", "price_away"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    print(f"in-play spread quotes at bettable books: {len(o)} rows, {o.game_id.nunique()} games, "
          f"books {sorted(o.bookmaker.unique())}")
    o = o.merge(ht[["game_id", "ht_start", "ht_end"]], on="game_id", how="inner")
    w = o[(o.snapshot_at >= o.ht_start) & (o.snapshot_at <= o.ht_end)]
    last = w.sort_values("snapshot_at").groupby(["game_id", "bookmaker"]).tail(1)
    print(f"games with >=1 bettable quote INSIDE the halftime window: {last.game_id.nunique()} of {len(ht)}; "
          f"quotes {len(last)}; books per game median {last.groupby('game_id').size().median() if len(last) else 0}")
    if last.empty:
        print("no halftime quotes -> forward check not possible")
        return
    # exp_m1 from the same fit as section 3 is not available here without re-fitting; reuse the 2011-16
    # SBR fit printed above via the coefficients stored on the module.
    c0, c1 = _EXP_M1
    rows = []
    for gid, q in last.groupby("game_id"):
        r = ht[ht.game_id == gid].iloc[0]
        modal = q.point.mode().iloc[0]
        qq = q[q.point == modal]
        dev1 = r.m1 - (c0 + c1 * r.hp)
        rows.append(dict(game_id=gid, week=r.week, m1=r.m1, pregame_hp=r.hp, live_hp=modal,
                         implied_2H_hp=modal + r.m1, dev1=round(dev1, 2), result=r.result,
                         best_home=qq.price_home.max(), best_away=qq.price_away.max(), books=len(qq)))
    f = pd.DataFrame(rows)
    print("\nper game (live_hp = modal live home point at the bettable books; implied 2H home line = live_hp + 1H margin):")
    print(f[["game_id", "m1", "pregame_hp", "live_hp", "implied_2H_hp", "dev1", "result", "best_home", "best_away", "books"]]
          .to_string(index=False))
    out = []
    for cut in RULES["R1_side_dev"]["grid"]:
        x = f[f.dev1.abs() >= cut].copy()
        if x.empty:
            out.append(dict(cut=cut, bets=0))
            continue
        bet_home = (x.dev1 > 0) if direction == "follow" else (x.dev1 < 0)
        cov = x.result + x.live_hp
        won = np.where(bet_home, cov > 0, cov < 0).astype(int)
        push = (cov == 0).astype(int)
        price = np.where(bet_home, x.best_home, x.best_away)
        pr_real = profit_units(won, price, push)
        pr_110 = profit_units(won, -110, push)
        out.append(dict(cut=cut, bets=len(x), wins=int(won.sum()), pushes=int(push.sum()),
                        units_best_price=round(pr_real.sum(), 2), roi_best_price=round(100 * pr_real.mean(), 1),
                        units_at_110=round(pr_110.sum(), 2), median_price=float(np.median(price))))
    print("\nR1 on 2026 halftime live spreads (real best bettable price at the modal live line):")
    print(fmt(pd.DataFrame(out)))


_EXP_M1 = (np.nan, np.nan)


# ─── 5. what a paid halftime backfill would cost and add ──────────────────

def backfill_cost(g: pd.DataFrame):
    hdr("13. PAID HALFTIME BACKFILL (NOT bought): cost computed from the schedule")
    rows = []
    for s in (2023, 2024, 2025):
        x = g[(g.season == s) & g.kick.notna() & g.home_score.notna()]
        stamps = set()
        for k in x.kick:
            st = k + pd.Timedelta(minutes=85)
            for i in range(6):
                t = st + pd.Timedelta(minutes=5 * i)
                stamps.add(t.floor("5min"))
        rows.append(dict(season=s, games=len(x), distinct_5min_stamps=len(stamps),
                         slate_call_credits=len(stamps) * 20, per_event_credits=len(x) * 6 * 20))
    t = pd.DataFrame(rows)
    print(fmt(t))
    print(f"total 2023-25: slate-level {t.slate_call_credits.sum():,} credits, per-event {t.per_event_credits.sum():,} credits")
    print("slate-level = what nfl/live_model/README.md assumes (1,152 stamps x 20 = 23,040 for 2023-25).\n"
          "per-event   = 6 snapshots x 2 markets x 10 credits per game; this is the ~34,200/season figure.\n"
          "The Odds API bulk odds endpoint accepts only h2h/spreads/totals/outrights, so spreads_h2/totals_h2\n"
          "need the per-event endpoint; historical period markets exist only after 2023-05-03 (5-min snapshots).")


if __name__ == "__main__":
    main()

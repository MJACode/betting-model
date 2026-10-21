"""
Six cheap, published, low-volume NFL game-line rules, tested together with one
multiplicity correction (docs/nfl_edge_search.md bundle).

Run:  PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_gameline_rules
Reads only the local cache via scripts.nfl_edge_lib plus the repo SBR archive
nfl/data/sbr_nfl.json. No database, no network, no Odds API credits. Every
printed line is also written to %TEMP%/nfl_edge/nfl_edge_gameline_rules_out.txt.

CONSTRUCTION (written before any outcome was read)
==================================================
Conventions. Units: 1 unit = 1 flat bet. result = home_score - away_score.
Home point = -spread_line (nflverse spread_line > 0 when HOME is favoured).
A side's point x: home x = home point, away x = -home point; the side covers
when side margin + x > 0, pushes at 0. Moneyline ties are graded as a push.
One bet per proposition (game x market x side); no game is bet twice inside
one table cell. Every table says which line/price it grades at:
  CLOSE -110   nflverse closing line, price ASSUMED -110 (there is no bettable
               price in the data before 2020). This is a closing-line study:
               the closing line is not a quote you could have bet earlier.
               ATS close tables also print ROI at -105 and -115 (price grid)
               and the -110 break-even is 52.38% of decided bets.
  POSTED ML    nflverse posted closing moneyline (2006+; coverage printed).
               Also a closing study.
  BETTABLE     odds_hist (2020-2025), books in BETTABLE_HIST only, EXCLUDED
               books removed by the loader. Quotes are cleaned first: both
               prices present, |price| >= 100, |price| < 300 (spreads/totals)
               or < 5000 (h2h), two-way implied sum in [1.00, 1.12]; a quote
               > 2 points (spreads) / 3 points (totals) from the board median
               is dropped. BOARD at decision lead L = each book's latest quote
               with lead_hours >= L, kept only if within 6h of the game's
               latest such snapshot. OPENER board = each book's first quote in
               the first 6h of the game's first bettable snapshot (optionally
               bounded to lead <= a cap, stated where used).
               SELECTION uses the board MEDIAN line (rounded to the half
               point). PRICE: best point for the side among the board's books,
               then the best price at that point (teaser-script convention).
               Moneylines: best price for the side among the board's books.
               Snapshot cadence means the realised lead is longer than L; the
               median realised lead is printed for every board.
               Market coverage: spreads 2020-2025; h2h and usable totals only
               2023-2025 (2020-22 totals are one ~120h snapshot per game).
Inference. Every cell prints bets, bets per season, W-L-P, units, ROI, a 90%
cluster-bootstrap CI (2,000 resamples of games; one bet per game in every
cell, so game = week-free cluster), and a two-sided bootstrap p (2*min share
of resampled ROI <= 0 / >= 0). LOW marks <= 10 bets per season. Every cell
with a p enters ONE Benjamini-Hochberg family (q = 0.10) across all six
rules, placebos, controls and splits; the hold-out-only family is also
printed. Per-season rows are descriptive (no p, not in the family).
Early/late: REG weeks 1-9 / REG weeks 10+ / postseason unless stated.

(a) WEEK-1 HOLDOVER (Fodor, DiFilippo, Krieger & Davis 2013, Appl. Fin. Econ.
    23(17)). Published: prior-season playoff teams covered 35.6% of opening-week
    games against prior-season non-playoff teams, 2004-2012 (so the other side
    64.4%). Rule: Week 1 REG, exactly one team made the prior postseason; bet
    the OTHER team ATS. Prior-postseason set = teams in a non-REG game of
    season-1 (franchise-normalised STL->LA, SD->LAC, OAK->LV); 1999 uses the
    1998 playoff field (DEN NYJ JAX MIA BUF NE MIN ATL DAL SF GB ARI, from the
    public 1998-99 playoff bracket). Decision time: the rule is known in
    January, so the earliest quote is legitimate.
    Grade: CLOSE -110 for 2004-2012 (reproduction), 1999-2003 and 2013-2025
    (out of sample), 2026 week 1; BETTABLE 2020-2025 at the week-1 OPENER
    board (first bettable quote; the archive's first week-1 quote is ~230h
    before kickoff, not the true May opener) and at T-3h.
    Placebo: the same rule in week 9.
    Refinement (one, fit 1999-2012, graded 2013-2025 once): split by the
    playoff team's closing role (favourite by >= 3 / favourite by 0.5-2.5 /
    underdog or pick'em); keep every role with fit ROI > 0 and >= 20 fit bets.
    Early/late: 1999-2012 vs 2013-2025 (one week per season, so no in-season
    split exists).

(b) SMALL MONEYLINE UNDERDOGS (Krieger & Shank 2026, J. Prediction Markets
    19(2)). Published: underdog moneyline earns +6.55% when the closing spread
    is <= 3 and +2.17% when 3 < spread <= 7. Sample seasons not stated in the
    abstract. Underdog = the side getting points; at a pick'em the side with
    the longer moneyline (skipped if equal). Rule cells B<=3 and B3.5-7.
    Grade: POSTED ML 2006-2019 (discovery), POSTED ML 2020-2025 (hold-out,
    closing study), BETTABLE 2023-2025 at T-3h (bucket from the T-3h spread
    board median; dog price = best bettable h2h at T-3h).
    Neighbourhood: |spread| cells 0-1 / 1.5-2.5 / 3 / 3.5-4.5 / 5-6.5 / 7 /
    7.5-10 / 10.5+.
    Placebo (as asked): the FAVOURITE moneyline in the same games. This is the
    mechanical complement of the dog bet after vig, so it is expected to be
    negative whenever the dog bet is positive; it is printed as asked, not as
    an independent test. Controls: dogs at 7.5-10 (outside the rule) and the
    same dogs ATS at CLOSE -110 (is it a moneyline effect or a dog effect?).
    Refinement (fit 2006-2019): keep the |spread| cells inside <= 7 with fit
    ROI > 0 and >= 100 fit bets; the union is graded on 2020-2025 once.

(c) BIG UNDERDOGS IN LOW-TOTAL GAMES (practitioner rule). Published forms:
    C1 dog >= +7 and total <= 41; C2 dog points / total >= 0.20. Bet the dog
    ATS. Grade: CLOSE -110, fit 1999-2014, hold-out 2015-2025; BETTABLE
    2020-2025 at T-3h (dog size from the T-3h spread board median; total from
    the latest bettable totals board >= 3h before kickoff, which for 2020-22
    is the ~120h snapshot - earlier information, still pre-decision).
    Neighbourhood: dog >= {6.5, 7, 8, 10} x total <= {39, 41, 43, 45}; ratio
    >= {0.15, 0.175, 0.20, 0.225, 0.25}.
    Placebo: dog >= +7 with total >= 48 (if the low total is the mechanism,
    big dogs in high totals should not cover).
    Refinement (fit 1999-2014): the ratio cut r* in the ratio grid with the
    best fit ROI among cuts carrying >= 5 fit bets per season; graded
    2015-2025 once.

(d) LATE-SEASON SPOILER (published claim 108-69-4 since 2009, grade C).
    Standings entering week w are built from nflverse REG results of weeks
    < w (ties = half a win). Conferences hard-coded (SEA in the AFC through
    2001, HOU from 2002); divisions from nflverse div_game pairs. K = 6 seeds
    through 2019, 7 from 2020. Season length 16 games through 2020, 17 after.
    ELIMINATED proxy = STRICT or NEAR:
      STRICT (sufficient for mathematical elimination, ignores tiebreakers):
        max possible wins < division leader's current wins AND at least K
        conference teams already have more wins than the team's maximum.
      NEAR (the brief's proxy): losing record AND (wins of the K-th best team
        in the conference - team's wins) >= 3 AND <= 4 games remaining.
    Rule: REG weeks 13-18, the dog gets >= +7 at the close, the dog is
    eliminated (proxy), the favourite is not. Bet the dog ATS.
    Grade: CLOSE -110, fit 1999-2014, hold-out 2015-2025, the published window
    2009-2025 for reference; BETTABLE 2020-2025 at T-3h (standings are known
    before the week; dog size from the T-3h board median).
    Neighbourhood: dog >= {6, 7, 8.5, 10} x proxy {STRICT only, STRICT|NEAR}.
    Placebos: P1 the dog is ALIVE (not flagged) vs an alive favourite, same
    weeks and spread (is it elimination or just big late-season dogs?);
    P2 both teams eliminated, dog >= +7 (no motivation gap).
    Refinement (fit 1999-2014): split by dog home/away; keep a side with fit
    ROI > 0 and >= 30 fit bets. Early/late: weeks 13-15 vs 16-18.

(e) FADE LARGE OPEN-TO-CLOSE MOVES (Moskowitz 2021: overreaction reverses;
    "large moves only" untested). The honest prior is negative: the close is
    the sharpest line in the market.
    Discovery (CLOSE -110, 2011-2019): open = SBR open (home handicap sign,
    already the home point; the SBR open columns are clean), close = nflverse
    close (SBR's own close columns are scrambled in ~9% of rows and are only
    used to print an agreement check on their clean rows). SBR is joined to
    nflverse on (season, date, home score, away score); names validate only.
    Move = close - open (home point; total). Fade: bet the side the line
    moved AWAY from, at the close (home point fell -> bet away; total rose ->
    bet under). KEY = the move goes through 3 or 7 (open and close strictly
    straddle +-3 or +-7) or off it (open on +-3/+-7, close not).
    Neighbourhood: spreads |move| >= {1.5, 2, 2.5, 3, 3.5} x {all, KEY};
    totals |move| >= {2, 2.5, 3, 3.5, 4}. Published cells: spreads 2, 2.5, 3;
    totals 2.5, 3.5. Placebo: small moves 0.5 <= |move| <= 1.
    Hold-out: SBR 2020-2021 (CLOSE -110) and BETTABLE 2020-2025 (totals
    2023-2025): open = OPENER board bounded to lead <= 160h (the week's
    reopen, about Sunday 9pm ET for a Sunday 1pm game; without the bound the
    2023-25 first quote is a summer lookahead line), decision board T-1h
    (realised lead printed), move = T-1h median - opener median, bet the fade
    side at the T-1h best point and price.
    Refinement (fit SBR 2011-2019): the single grid cell (market, cut, KEY)
    with the best fit ROI among cells with >= 10 fit bets per season; graded
    on the BETTABLE hold-out once.
    ADDED AFTER THE FIRST RUN (labelled in the output, NOT registered, kind
    'posthoc'): the 2020-21 overlap showed SBR opens that disagree with the
    odds_hist opener (some are sign flips). A data-only flag, no outcome used:
    open and close on opposite sides of zero with both |.| >= 2.5, or
    |close - open| > 7. The flag is validated on the 2020-21 overlap and the
    discovery spread grid is re-printed without flagged rows. The registered
    refinement and its hold-out read are unchanged.

(f) MONEYLINE vs SPREAD AT EXTREME TOTALS. No exact published rule; this is
    the brief's construction. P(home win) is fitted on 1999-2014 results
    (ties dropped) by logistic regression: FULL = s + tc + s*tc with
    s = spread_line, tc = total_line - 44; control SPREAD-ONLY = s. Bet the
    moneyline side with the larger EV = p*decimal - 1 when EV > m.
    Neighbourhood: m in {0, .02, .04, .06} x total <= 39.5 / 40-49.5 / >= 50
    (the middle bucket is the placebo: the total term should do nothing
    there). As stated: FULL, m = 0, both extreme buckets.
    Grade: POSTED ML 2006-2014 (discovery for m), 2015-2025 (hold-out,
    closing study), BETTABLE 2023-2025 at T-3h (model inputs from the T-3h
    spread and totals board medians, price = best bettable h2h at T-3h).
    Refinement (fit 2006-2014): the (bucket in {low, high, both}, m) cell with
    the best fit ROI among cells with >= 5 fit bets per season; graded
    2015-2025 once. Mechanism check printed: mean p_full - p_spread_only for
    the favourite by total bucket (the lumpy-margin story says the favourite
    is MORE likely to win at a given spread when the total is low).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from scripts.nfl_edge_lib import (BETTABLE_HIST, CACHE, am_to_dec, am_to_prob,
                                  games, odds_hist, profit_units)

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 500)

OUTFILE = CACHE / "nfl_edge_gameline_rules_out.txt"
SBR_PATH = Path(__file__).resolve().parents[1] / "nfl" / "data" / "sbr_nfl.json"
NB = 2000
LOW = 10
REGISTRY: list[dict] = []
SIX = pd.Timedelta(hours=6)

FR = {"STL": "LA", "SD": "LAC", "OAK": "LV"}
AFC = {"BAL", "BUF", "CIN", "CLE", "DEN", "HOU", "IND", "JAX", "KC", "LAC", "LV",
       "MIA", "NE", "NYJ", "PIT", "TEN"}
PLAYOFF_1998 = {"DEN", "NYJ", "JAX", "MIA", "BUF", "NE", "MIN", "ATL", "DAL", "SF", "GB", "ARI"}
NICK = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF",
    "Panthers": "CAR", "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE",
    "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB",
    "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX",
    "Chiefs": "KC", "KCChiefs": "KC", "Kansas": "KC",
    "Raiders": "LV", "LVRaiders": "LV", "Oakland": "LV",
    "Chargers": "LAC", "Rams": "LA", "Dolphins": "MIA", "Vikings": "MIN",
    "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
    "Eagles": "PHI", "Steelers": "PIT", "Fortyniners": "SF", "49ers": "SF",
    "Seahawks": "SEA", "Buccaneers": "TB", "Tampa": "TB", "Titans": "TEN",
    "Commanders": "WAS", "Washingtom": "WAS", "Washington": "WAS",
    "Redskins": "WAS", "FootballTeam": "WAS", "SanDiego": "LAC", "StLouis": "LA",
    "LARams": "LA", "LAChargers": "LAC",
}


class Tee:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")
        self.o = sys.stdout

    def write(self, s):
        self.o.write(s)
        self.f.write(s)

    def flush(self):
        self.o.flush()
        self.f.flush()


def hdr(s):
    print("\n" + "=" * 110 + "\n" + s + "\n" + "=" * 110)


def show(rows, cols=None):
    df = pd.DataFrame(rows)
    if df.empty:
        print("  (no rows)")
        return df
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    print(df.to_string(index=False))
    return df


# ─── inference ─────────────────────────────────────────────────────────────

def bstat(profit, cluster, nb=NB, seed=7):
    profit = np.asarray(profit, dtype=float)
    cluster = np.asarray(cluster)
    uniq, inv = np.unique(cluster, return_inverse=True)
    sums = np.bincount(inv, weights=profit)
    cnts = np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    k = len(uniq)
    out = []
    for st in range(0, nb, 250):
        m = min(250, nb - st)
        idx = rng.integers(0, k, size=(m, k))
        out.append(sums[idx].sum(1) / cnts[idx].sum(1))
    r = np.concatenate(out)
    lo, hi = np.quantile(r, [0.05, 0.95])
    le = (np.sum(r <= 0) + 1) / (nb + 1)
    ge = (np.sum(r >= 0) + 1) / (nb + 1)
    return profit.mean(), lo, hi, min(1.0, 2 * min(le, ge))


def cell(df, label, hyp, era, kind, nseas, extra=None, grid=False, register=True):
    """df needs columns profit, res (W/L/P), game_id. One row of a table."""
    n = len(df)
    r = {"cell": label, "era": era}
    if extra:
        r.update(extra)
    if n == 0:
        r.update({"bets": 0})
        return r
    w = int((df["res"] == "W").sum()); l = int((df["res"] == "L").sum()); p = int((df["res"] == "P").sum())
    roi, lo, hi, pv = bstat(df["profit"].values, df["game_id"].values)
    r.update({"bets": n, "/szn": round(n / nseas, 1), "W-L-P": f"{w}-{l}-{p}",
              "win%": round(100 * w / max(w + l, 1), 1), "units": round(df["profit"].sum(), 2),
              "roi%": round(100 * roi, 1), "ci90": f"[{100*lo:+.1f},{100*hi:+.1f}]",
              "p": round(pv, 3)})
    if grid:
        for pr in (-105, -115):
            d = float(am_to_dec(pr))
            r[f"roi@{pr}"] = round(100 * (w * (d - 1) - l) / n, 1)
    r["low"] = "LOW" if n / nseas <= LOW else ""
    if register:
        REGISTRY.append({"hyp": hyp, "kind": kind, "cell": label, "era": era,
                         "bets": n, "roi%": round(100 * roi, 1), "p": pv})
    return r


def season_rows(df, label):
    rows = []
    for s, x in df.groupby("season"):
        w = int((x["res"] == "W").sum()); l = int((x["res"] == "L").sum()); p = int((x["res"] == "P").sum())
        rows.append({"rule": label, "season": s, "bets": len(x), "W-L-P": f"{w}-{l}-{p}",
                     "units": round(x["profit"].sum(), 2), "roi%": round(100 * x["profit"].mean(), 1)})
    return rows


def res_of(win, push):
    return np.where(push == 1, "P", np.where(win == 1, "W", "L"))


def ats(df, x_col="x", margin_col="margin", price=-110):
    s = df[margin_col].values + df[x_col].values
    win = (s > 0).astype(int); push = (s == 0).astype(int)
    pr = df[price].values if isinstance(price, str) else price
    out = df.copy()
    out["profit"] = profit_units(win, pr, push)
    out["res"] = res_of(win, push)
    return out


def nseasons(a, b):
    return b - a + 1


def phase(df):
    return np.where(df["game_type"] != "REG", "post",
                    np.where(df["week"] <= 9, "REG wk1-9", "REG wk10+"))


# ─── data ──────────────────────────────────────────────────────────────────

def load_games():
    g = games()
    g = g[g["result"].notna() & g["spread_line"].notna()].copy()
    g["hf"] = g["home_team"].replace(FR)
    g["af"] = g["away_team"].replace(FR)
    g["phase"] = phase(g)
    return g


def load_odds():
    o = odds_hist(["spreads", "totals", "h2h"])
    o = o[o["bookmaker"].isin(BETTABLE_HIST) & (o["lead_hours"] >= 0)].copy()
    ph, pa = o["price_home"], o["price_away"]
    ok = ph.notna() & pa.notna() & (ph.abs() >= 100) & (pa.abs() >= 100)
    lim = np.where(o["market"] == "h2h", 5000, 300)
    ok &= (ph.abs() < lim) & (pa.abs() < lim)
    with np.errstate(all="ignore"):
        imp = am_to_prob(ph.fillna(-110).values) + am_to_prob(pa.fillna(-110).values)
    ok &= (imp >= 1.0) & (imp <= 1.12)
    ok &= (o["market"] == "h2h") | o["point"].notna()
    print(f"odds_hist bettable rows={len(o):,}; dropped by price/point sanity={int((~ok).sum()):,}")
    return o[ok]


def board_at(o, market, lead):
    x = o[(o["market"] == market) & (o["lead_hours"] >= lead)]
    x = x.sort_values("snapshot_at").groupby(["game_id", "bookmaker"], as_index=False).tail(1)
    s = x.groupby("game_id")["snapshot_at"].transform("max")
    return x[x["snapshot_at"] >= s - SIX]


def board_open(o, market, max_lead=np.inf):
    x = o[(o["market"] == market) & (o["lead_hours"] <= max_lead)]
    f = x.groupby("game_id")["snapshot_at"].transform("min")
    x = x[x["snapshot_at"] <= f + SIX]
    return x.sort_values("snapshot_at").groupby(["game_id", "bookmaker"], as_index=False).head(1)


def summ_points(x, outlier):
    x = x.copy()
    x["med0"] = x.groupby("game_id")["point"].transform("median")
    x = x[(x["point"] - x["med0"]).abs() <= outlier]
    g = x.groupby("game_id")
    out = pd.DataFrame({"med": (g["point"].median() * 2).round() / 2,
                        "hi": g["point"].max(), "lo": g["point"].min(),
                        "books": g["bookmaker"].nunique(), "lead": g["lead_hours"].min()})
    x = x.join(out[["hi", "lo"]], on="game_id")
    out["ph_hi"] = x[x["point"] == x["hi"]].groupby("game_id")["price_home"].max()
    out["pa_hi"] = x[x["point"] == x["hi"]].groupby("game_id")["price_away"].max()
    out["ph_lo"] = x[x["point"] == x["lo"]].groupby("game_id")["price_home"].max()
    out["pa_lo"] = x[x["point"] == x["lo"]].groupby("game_id")["price_away"].max()
    return out


def summ_h2h(x):
    g = x.groupby("game_id")
    return pd.DataFrame({"ml_h": g["price_home"].max(), "ml_a": g["price_away"].max(),
                         "ml_h_med": g["price_home"].median(), "ml_a_med": g["price_away"].median(),
                         "books": g["bookmaker"].nunique(), "lead": g["lead_hours"].min()})


def spread_side(board, side):
    """best point and price for a side from a spread board summary (home-relative points)."""
    if side == "home":
        return board["hi"], board["ph_hi"]
    return -board["lo"], board["pa_lo"]


def lead_note(name, b):
    print(f"  board {name}: games={len(b)}, books median={b['books'].median():.0f}, "
          f"realised lead hours median={b['lead'].median():.1f} (p10 {b['lead'].quantile(.1):.1f}, "
          f"p90 {b['lead'].quantile(.9):.1f})")


def bettable_ats(bets, sb, side_col="side", hyp="", label="", era="", kind="", nseas=6, extra=None):
    """Grade bets (game_id, side, margin) at a spread board's best point/price."""
    cols = ["hi", "lo", "ph_hi", "pa_lo"]
    b = bets.drop(columns=[c for c in cols if c in bets.columns]).join(sb[cols], on="game_id", how="inner")
    if b.empty:
        return cell(b.assign(profit=[], res=[]), label, hyp, era, kind, nseas, extra), b
    hx, hp = spread_side(b, "home")
    ax, ap = spread_side(b, "away")
    b["xb"] = np.where(b[side_col] == "home", hx, ax)
    b["pb"] = np.where(b[side_col] == "home", hp, ap)
    b = b[b["pb"].notna()]
    g = ats(b, "xb", "margin", "pb")
    return cell(g, label, hyp, era, kind, nseas, extra), g


# ─── (a) week-1 holdover ───────────────────────────────────────────────────

def prior_playoffs(gall):
    P = {1999: set(PLAYOFF_1998)}
    post = gall[gall["game_type"] != "REG"]
    for s in sorted(gall["season"].unique()):
        x = post[post["season"] == s]
        P[s + 1] = set(x["hf"]) | set(x["af"])
    return P


def holdover(g, week, P):
    x = g[(g["game_type"] == "REG") & (g["week"] == week)].copy()
    hp = np.array([h in P.get(s, set()) for h, s in zip(x["hf"], x["season"])])
    ap = np.array([a in P.get(s, set()) for a, s in zip(x["af"], x["season"])])
    x = x[hp ^ ap].copy()
    hp = hp[hp ^ ap]
    x["side"] = np.where(hp, "away", "home")          # bet the NON-playoff team
    x["x"] = np.where(hp, -x["home_point_close"], x["home_point_close"])
    x["margin"] = np.where(hp, -x["result"], x["result"])
    po_pt = -x["x"]                                    # the playoff team's own point
    x["role"] = np.select([po_pt <= -3, po_pt < 0], ["PO fav>=3", "PO fav<3"], "PO dog/pk")
    return ats(x)


def run_a(g, o, sb_t3):
    hdr("(a) WEEK-1 HOLDOVER: bet against the prior-season playoff team vs a non-playoff team (Fodor et al. 2013)")
    P = prior_playoffs(load_games_all())
    print("prior-postseason set sizes:", {s: len(P[s]) for s in (1999, 2004, 2013, 2020, 2021, 2026)})
    H = "a"
    A1 = holdover(g, 1, P)
    A9 = holdover(g, 9, P)
    eras = [("1999-2003", 1999, 2003, "oos"), ("2004-2012 PUBLISHED", 2004, 2012, "pub-in"),
            ("2013-2025", 2013, 2025, "oos"), ("2020-2025", 2020, 2025, "oos"),
            ("1999-2025", 1999, 2025, "pooled"), ("2026", 2026, 2026, "oos")]
    print("\nCLOSE -110 (closing-line study). Published: 64.4% ATS for this side, 2004-2012.")
    rows = []
    for name, a, b, kind in eras:
        rows.append(cell(A1[A1.season.between(a, b)], "WEEK 1 (rule)", H, name, kind, nseasons(a, b), grid=True))
    for name, a, b, kind in eras:
        rows.append(cell(A9[A9.season.between(a, b)], "WEEK 9 (placebo)", H, name, "placebo", nseasons(a, b), grid=True))
    show(rows)
    print("\nPer season, week-1 rule, CLOSE -110:")
    show(season_rows(A1, "wk1"))
    # bettable
    print("\nBETTABLE 2020-2025 (best point then best price among bettable books):")
    sb_open = summ_points(board_open(o, "spreads"), 2.0)
    lead_note("week-1 opener (first bettable quote)", sb_open.loc[sb_open.index.isin(A1.game_id)])
    lead_note("T-3h", sb_t3.loc[sb_t3.index.isin(A1.game_id)])
    bets = A1[A1.season.between(2020, 2025)][["game_id", "season", "week", "side", "margin", "role"]].set_index("game_id", drop=False)
    rows = []
    for nm, sb in (("opener", sb_open), ("T-3h", sb_t3)):
        r, gg = bettable_ats(bets.reset_index(drop=True), sb, hyp=H, label=f"WEEK 1 @ {nm}", era="2020-2025", kind="oos", nseas=6)
        rows.append(r)
    bets9 = A9[A9.season.between(2020, 2025)][["game_id", "season", "week", "side", "margin"]]
    r, _ = bettable_ats(bets9, sb_t3, hyp=H, label="WEEK 9 placebo @ T-3h", era="2020-2025", kind="placebo", nseas=6)
    rows.append(r)
    show(rows)
    # refinement
    print("\nREFINEMENT (registered): playoff team's closing role, fit 1999-2012, keep ROI>0 & >=20 bets; grade 2013-2025 once.")
    rows = []
    fit = A1[A1.season.between(1999, 2012)]
    keep = []
    for role, x in fit.groupby("role"):
        r = cell(x, role, H, "FIT 1999-2012", "fit", 14, grid=True)
        rows.append(r)
        if r["bets"] >= 20 and r["roi%"] > 0:
            keep.append(role)
    hold = A1[A1.season.between(2013, 2025)]
    for role, x in hold.groupby("role"):
        rows.append(cell(x, role, H, "2013-2025", "oos-cell", 13, grid=True))
    show(rows)
    print(f"  kept roles: {keep}")
    rows = [cell(hold[hold.role.isin(keep)], f"REFINED {keep}", H, "HOLD 2013-2025", "hold", 13, grid=True)]
    r, _ = bettable_ats(bets[bets.role.isin(keep)].reset_index(drop=True), sb_t3, hyp=H,
                        label=f"REFINED @ T-3h", era="2020-2025", kind="hold", nseas=6)
    rows.append(r)
    show(rows)


_GALL = None


def load_games_all():
    global _GALL
    if _GALL is None:
        _GALL = load_games()
    return _GALL


# ─── (b) small moneyline underdogs ─────────────────────────────────────────

B_CELLS = [("0-1", 0, 1), ("1.5-2.5", 1.5, 2.5), ("3", 3, 3), ("3.5-4.5", 3.5, 4.5),
           ("5-6.5", 5, 6.5), ("7", 7, 7), ("7.5-10", 7.5, 10), ("10.5+", 10.5, 99)]


def mag_cell(m):
    for nm, a, b in B_CELLS:
        if a <= m <= b:
            return nm
    return None


def dog_frame(df, s_col, mlh, mla):
    """dog side by spread (s_col in spread_line orientation), pick'em by longer ML."""
    x = df.copy()
    s = x[s_col]
    dog_home = (s < 0) | ((s == 0) & (x[mlh] > x[mla]))
    pk_eq = (s == 0) & (x[mlh] == x[mla])
    x = x[~pk_eq].copy(); dog_home = dog_home[~pk_eq]
    x["side"] = np.where(dog_home, "home", "away")
    x["mag"] = s.abs()
    x["dog_ml"] = np.where(dog_home, x[mlh], x[mla])
    x["fav_ml"] = np.where(dog_home, x[mla], x[mlh])
    x["margin"] = np.where(dog_home, x["result"], -x["result"])
    x["mcell"] = x["mag"].map(mag_cell)
    x["pub"] = np.select([x["mag"] <= 3, x["mag"] <= 7], ["B<=3", "B3.5-7"], "out")
    return x


def ml_grade(x, price_col, fav=False):
    m = -x["margin"] if fav else x["margin"]
    win = (m > 0).astype(int).values; push = (m == 0).astype(int).values
    out = x.copy()
    out["profit"] = profit_units(win, x[price_col].values, push)
    out["res"] = res_of(win, push)
    return out


def run_b(g, o, sb_t3, hb_t3):
    hdr("(b) SMALL MONEYLINE UNDERDOGS: dog ML when |closing spread| <= 3 (+6.55% published) or 3.5-7 (+2.17%) (Krieger & Shank 2026)")
    H = "b"
    x = g[g.season >= 2006].copy()
    cov = x.groupby("season").apply(lambda d: f"{d.home_moneyline.notna().sum()}/{len(d)}")
    print("posted ML coverage (games with ML / games):", dict(cov))
    x = x[x.home_moneyline.notna() & x.away_moneyline.notna()]
    D = dog_frame(x, "spread_line", "home_moneyline", "away_moneyline")
    Dd = ml_grade(D, "dog_ml"); Df = ml_grade(D, "fav_ml", fav=True)
    Dx = D.copy(); Dx["x"] = Dx["mag"]; Da = ats(Dx)
    eras = [("DISC 2006-2019", 2006, 2019, "disc"), ("HOLD 2020-2025", 2020, 2025, "oos")]
    print("\nPOSTED ML (closing study). Published rule cells, placebo and controls:")
    rows = []
    for name, a, b, kind in eras:
        for pc in ("B<=3", "B3.5-7"):
            sel = lambda d: d[d.season.between(a, b) & (d.pub == pc)]
            rows.append(cell(sel(Dd), f"{pc} dog ML", H, name, kind, nseasons(a, b)))
            rows.append(cell(sel(Df), f"{pc} FAV ML (placebo, complement)", H, name, "placebo", nseasons(a, b)))
            rows.append(cell(sel(Da), f"{pc} dog ATS close -110 (control)", H, name, "control", nseasons(a, b)))
        c = Dd[Dd.season.between(a, b) & (Dd.mcell == "7.5-10")]
        rows.append(cell(c, "7.5-10 dog ML (control)", H, name, "control", nseasons(a, b)))
    show(rows)
    print("\nNeighbourhood: dog ML by |closing spread| cell, POSTED ML:")
    rows = []
    for name, a, b, kind in eras:
        for nm, _, _ in B_CELLS:
            c = Dd[Dd.season.between(a, b) & (Dd.mcell == nm)]
            rows.append(cell(c, nm, H, name, "grid-" + kind, nseasons(a, b),
                             extra={"mean_ml": round(float(c.dog_ml.mean()), 0) if len(c) else np.nan}))
    show(rows)
    print("\nPer season, B<=3 dog ML, POSTED ML:")
    show(season_rows(Dd[Dd.pub == "B<=3"], "B<=3"))
    print("\nPer season, B3.5-7 dog ML, POSTED ML:")
    show(season_rows(Dd[Dd.pub == "B3.5-7"], "B3.5-7"))
    print("\nEarly/late split, published cells, POSTED ML 2006-2025:")
    rows = []
    for pc in ("B<=3", "B3.5-7"):
        for ph, c in Dd[Dd.pub == pc].groupby("phase"):
            rows.append(cell(c, f"{pc} {ph}", H, "2006-2025", "split", 20))
    show(rows)
    # bettable 2023-2025
    print("\nBETTABLE 2023-2025 at T-3h (bucket from T-3h spread board median; best bettable dog ML):")
    lead_note("spreads T-3h", sb_t3); lead_note("h2h T-3h", hb_t3)
    gb = g[g.season.between(2023, 2025)].set_index("game_id", drop=False)
    gb = gb.join(sb_t3[["med"]], how="inner").join(hb_t3[["ml_h", "ml_a"]], how="inner")
    gb["s_b"] = -gb["med"]
    Db = dog_frame(gb.reset_index(drop=True), "s_b", "ml_h", "ml_a")
    Dbd = ml_grade(Db, "dog_ml"); Dbf = ml_grade(Db, "fav_ml", fav=True)
    rows = []
    for pc in ("B<=3", "B3.5-7"):
        rows.append(cell(Dbd[Dbd.pub == pc], f"{pc} dog ML @T-3h", H, "2023-2025", "oos", 3))
        rows.append(cell(Dbf[Dbf.pub == pc], f"{pc} FAV ML @T-3h (placebo)", H, "2023-2025", "placebo", 3))
    rows.append(cell(Dbd[Dbd.mcell == "7.5-10"], "7.5-10 dog ML @T-3h (control)", H, "2023-2025", "control", 3))
    show(rows)
    # refinement
    print("\nREFINEMENT (registered): |spread| cells inside <=7 with DISC ROI>0 and >=100 bets; union graded once.")
    disc = Dd[Dd.season.between(2006, 2019)]
    keep = []
    for nm, _, _ in B_CELLS[:6]:
        c = disc[disc.mcell == nm]
        if len(c) >= 100 and c.profit.mean() > 0:
            keep.append(nm)
    print(f"  kept cells: {keep}")
    rows = [cell(Dd[Dd.season.between(2020, 2025) & Dd.mcell.isin(keep)], f"REFINED {keep}", H,
                 "HOLD 2020-2025 posted", "hold", 6),
            cell(Dbd[Dbd.mcell.isin(keep)], f"REFINED {keep} @T-3h", H, "2023-2025 bettable", "hold", 3)]
    show(rows)


# ─── (c) big dogs in low totals ────────────────────────────────────────────

def dog_ats_frame(df, s_col, t_col):
    x = df[df[s_col] != 0].copy()
    dog_home = x[s_col] < 0
    x["side"] = np.where(dog_home, "home", "away")
    x["mag"] = x[s_col].abs()
    x["x"] = x["mag"]
    x["tot"] = x[t_col]
    x["ratio"] = x["mag"] / x["tot"]
    x["margin"] = np.where(dog_home, x["result"], -x["result"])
    return x


def run_c(g, sb_t3, tb_t3):
    hdr("(c) BIG UNDERDOGS IN LOW-TOTAL GAMES: dog ATS (practitioner rule)")
    H = "c"
    C = ats(dog_ats_frame(g, "spread_line", "total_line"))
    eras = [("FIT 1999-2014", 1999, 2014, "fit"), ("HOLD 2015-2025", 2015, 2025, "oos"),
            ("2020-2025 close", 2020, 2025, "oos")]
    rules = [("C1 dog>=7 & tot<=41", lambda d: (d.mag >= 7) & (d.tot <= 41), None),
             ("C2 ratio>=0.20", lambda d: d.ratio >= 0.20, None),
             ("PLACEBO dog>=7 & tot>=48", lambda d: (d.mag >= 7) & (d.tot >= 48), "placebo")]
    print("CLOSE -110 (closing-line study). Published forms and placebo:")
    rows = []
    for name, a, b, kind in eras:
        for lab, f, k2 in rules:
            c = C[C.season.between(a, b)]
            rows.append(cell(c[f(c)], lab, H, name, k2 or kind, nseasons(a, b), grid=True))
    show(rows)
    print("\nNeighbourhood: dog >= D x total <= T, CLOSE -110:")
    rows = []
    for name, a, b, kind in eras[:2]:
        c0 = C[C.season.between(a, b)]
        for D in (6.5, 7, 8, 10):
            for T in (39, 41, 43, 45):
                c = c0[(c0.mag >= D) & (c0.tot <= T)]
                rows.append(cell(c, f"dog>={D} tot<={T}", H, name, "grid-" + kind, nseasons(a, b), grid=True))
    show(rows)
    print("\nNeighbourhood: dog points / total >= r, CLOSE -110:")
    rows = []
    fitroi = {}
    for name, a, b, kind in eras[:2]:
        c0 = C[C.season.between(a, b)]
        for r_ in (0.15, 0.175, 0.20, 0.225, 0.25):
            c = c0[c0.ratio >= r_]
            rr = cell(c, f"ratio>={r_}", H, name, "grid-" + kind, nseasons(a, b), grid=True)
            rows.append(rr)
            if kind == "fit":
                fitroi[r_] = (rr.get("roi%", -999), rr.get("/szn", 0))
    show(rows)
    print("\nPer season, C1 (dog>=7 & tot<=41) and C2 (ratio>=0.20), CLOSE -110:")
    show(season_rows(C[(C.mag >= 7) & (C.tot <= 41)], "C1") + season_rows(C[C.ratio >= 0.2], "C2"))
    print("\nEarly/late split, C1 and C2, CLOSE -110, 1999-2025:")
    rows = []
    for lab, f, _ in rules[:2]:
        for ph, c in C[f(C)].groupby("phase"):
            rows.append(cell(c, f"{lab} {ph}", H, "1999-2025", "split", 27, grid=True))
    show(rows)
    print("\nBETTABLE 2020-2025 at T-3h (dog size from spread board median; total from latest totals board >= 3h):")
    lead_note("spreads T-3h", sb_t3); lead_note("totals >=3h", tb_t3)
    gb = g[g.season.between(2020, 2025)].set_index("game_id", drop=False)
    gb = gb.join(sb_t3[["med"]], how="inner").join(tb_t3[["med"]].rename(columns={"med": "tmed"}), how="inner")
    gb["s_b"] = -gb["med"]
    Cb = dog_ats_frame(gb.reset_index(drop=True), "s_b", "tmed")
    rows = []
    for lab, f, k2 in rules:
        r, _ = bettable_ats(Cb[f(Cb)], sb_t3, hyp=H, label=lab + " @T-3h", era="2020-2025", kind=k2 or "oos", nseas=6)
        rows.append(r)
    show(rows)
    rows = []
    elig = {k: v for k, v in fitroi.items() if v[1] >= 5}
    rstar = max(elig, key=lambda k: elig[k][0]) if elig else 0.2
    print(f"\nREFINEMENT (registered): ratio cut with best FIT ROI among cuts with >=5 fit bets/season -> r*={rstar}")
    c = C[C.season.between(2015, 2025) & (C.ratio >= rstar)]
    rows.append(cell(c, f"REFINED ratio>={rstar}", H, "HOLD 2015-2025 close", "hold", 11, grid=True))
    r, _ = bettable_ats(Cb[Cb.ratio >= rstar], sb_t3, hyp=H, label=f"REFINED ratio>={rstar} @T-3h",
                        era="2020-2025", kind="hold", nseas=6)
    rows.append(r)
    show(rows)


# ─── (d) late-season spoiler ───────────────────────────────────────────────

def conference(team, season):
    if team == "SEA":
        return "AFC" if season <= 2001 else "NFC"
    return "AFC" if team in AFC else "NFC"


def divisions(gs):
    """union-find on div_game pairs within one season."""
    par = {}

    def f(a):
        par.setdefault(a, a)
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for h, a in gs.loc[gs["div_game"] == 1, ["hf", "af"]].itertuples(index=False):
        ra, rb = f(h), f(a)
        if ra != rb:
            par[ra] = rb
    teams = set(gs["hf"]) | set(gs["af"])
    return {t: f(t) for t in teams}


def standings_flags(g):
    """per (season, week, team) entering standings and elimination flags, weeks 13+."""
    reg = g[g["game_type"] == "REG"]
    long = pd.concat([
        pd.DataFrame({"season": reg.season, "week": reg.week, "team": reg.hf,
                      "we": np.where(reg.result > 0, 1.0, np.where(reg.result == 0, 0.5, 0.0))}),
        pd.DataFrame({"season": reg.season, "week": reg.week, "team": reg.af,
                      "we": np.where(reg.result < 0, 1.0, np.where(reg.result == 0, 0.5, 0.0))})])
    rows = []
    bad_div = 0
    for s, gs in reg.groupby("season"):
        dv = divisions(gs)
        K = 6 if s <= 2019 else 7
        NG = 16 if s <= 2020 else 17
        ls = long[long.season == s]
        teams = sorted(dv)
        conf = {t: conference(t, s) for t in teams}
        for d in set(dv.values()):
            if len({conf[t] for t in teams if dv[t] == d}) != 1:
                bad_div += 1
        for w in range(13, int(gs.week.max()) + 1):
            prev = ls[ls.week < w]
            we = prev.groupby("team")["we"].sum().reindex(teams).fillna(0)
            n = prev.groupby("team")["we"].count().reindex(teams).fillna(0)
            rem = NG - n
            mx = we + rem
            for t in teams:
                cteams = [u for u in teams if conf[u] == conf[t]]
                cw = we[cteams].sort_values(ascending=False)
                lead = max(we[u] for u in teams if dv[u] == dv[t])
                n_above = int((we[[u for u in cteams if u != t]] > mx[t]).sum())
                strict = (mx[t] < lead) and (n_above >= K)
                kth = cw.iloc[K - 1]
                near = (we[t] < n[t] / 2) and (kth - we[t] >= 3) and (rem[t] <= 4)
                rows.append((s, w, t, we[t], n[t], rem[t], strict, near))
    print(f"  division/conference consistency violations: {bad_div}")
    return pd.DataFrame(rows, columns=["season", "week", "team", "we", "n", "rem", "strict", "near"])


def spoiler_frame(g, s_col, F):
    """REG weeks 13+; dog/favourite from s_col (spread_line orientation); flags from F."""
    x = g[(g.game_type == "REG") & (g.week >= 13) & (g[s_col] != 0)].copy()
    dog_home = x[s_col] < 0
    x["side"] = np.where(dog_home, "home", "away")
    x["dog"] = np.where(dog_home, x.hf, x.af)
    x["fav"] = np.where(dog_home, x.af, x.hf)
    x["mag"] = x[s_col].abs(); x["x"] = x["mag"]
    x["margin"] = np.where(dog_home, x.result, -x.result)
    kd = list(zip(x.season, x.week, x.dog)); kf = list(zip(x.season, x.week, x.fav))
    x["d_strict"] = F.loc[kd, "strict"].values.astype(bool); x["d_near"] = F.loc[kd, "near"].values.astype(bool)
    x["f_strict"] = F.loc[kf, "strict"].values.astype(bool); x["f_near"] = F.loc[kf, "near"].values.astype(bool)
    x["d_flag"] = x.d_strict | x.d_near; x["f_flag"] = x.f_strict | x.f_near
    x["late"] = np.where(x.week <= 15, "wk13-15", "wk16-18")
    return x


def run_d(g, sb_t3):
    hdr("(d) LATE-SEASON SPOILER: eliminated dog getting >= +7 vs an alive favourite, weeks 13-18, dog ATS")
    H = "d"
    fl = standings_flags(g)
    fl["either"] = fl.strict | fl.near
    print("  flagged team-weeks (entering weeks 13+) by season: STRICT / NEAR / either")
    print(fl.groupby("season")[["strict", "near", "either"]].sum().T.to_string())
    F = fl.set_index(["season", "week", "team"])
    x = spoiler_frame(g, "spread_line", F)
    X = ats(x)
    eras = [("FIT 1999-2014", 1999, 2014, "fit"), ("HOLD 2015-2025", 2015, 2025, "oos"),
            ("PUB WINDOW 2009-2025", 2009, 2025, "pub-in"), ("2020-2025 close", 2020, 2025, "oos")]
    rules = [("RULE dog>=7 elim(S|N) vs alive", lambda d: (d.mag >= 7) & d.d_flag & ~d.f_flag, None),
             ("P1 dog>=7 ALIVE vs alive", lambda d: (d.mag >= 7) & ~d.d_flag & ~d.f_flag, "placebo"),
             ("P2 dog>=7 both eliminated", lambda d: (d.mag >= 7) & d.d_flag & d.f_flag, "placebo")]
    print("\nCLOSE -110 (closing-line study). Published claim 108-69-4 (61.0%) since 2009:")
    rows = []
    for name, a, b, kind in eras:
        for lab, f, k2 in rules:
            c = X[X.season.between(a, b)]
            rows.append(cell(c[f(c)], lab, H, name, k2 or kind, nseasons(a, b), grid=True))
    show(rows)
    print("\nNeighbourhood: dog >= D x proxy, eliminated dog vs alive favourite, CLOSE -110:")
    rows = []
    for name, a, b, kind in eras[:2]:
        c0 = X[X.season.between(a, b)]
        for D in (6, 7, 8.5, 10):
            for pn, pf in (("STRICT", lambda d: d.d_strict & ~d.f_flag), ("STRICT|NEAR", lambda d: d.d_flag & ~d.f_flag)):
                c = c0[(c0.mag >= D) & pf(c0)]
                rows.append(cell(c, f"dog>={D} {pn}", H, name, "grid-" + kind, nseasons(a, b), grid=True))
    show(rows)
    R = X[(X.mag >= 7) & X.d_flag & ~X.f_flag]
    print("\nPer season, RULE, CLOSE -110:")
    show(season_rows(R, "spoiler"))
    print("\nEarly/late split (weeks 13-15 vs 16-18), RULE, CLOSE -110, 1999-2025:")
    show([cell(c, f"RULE {lt}", H, "1999-2025", "split", 27, grid=True) for lt, c in R.groupby("late")])
    print("\nBETTABLE 2020-2025 at T-3h (dog and dog size from the T-3h spread board median):")
    gb = g[g.season.between(2020, 2025)].join(sb_t3[["med"]], on="game_id", how="inner")
    gb["s_b"] = -gb["med"]
    xb = spoiler_frame(gb, "s_b", F)
    rows = []
    for lab, f, k2 in rules:
        r, _ = bettable_ats(xb[f(xb)], sb_t3, hyp=H, label=lab + " @T-3h", era="2020-2025", kind=k2 or "oos", nseas=6)
        rows.append(r)
    show(rows)
    print("\nREFINEMENT (registered): dog home/away, fit 1999-2014, keep side with ROI>0 & >=30 bets; graded once.")
    rows = []
    keep = []
    for sd, c in R[R.season.between(1999, 2014)].groupby("side"):
        rr = cell(c, f"dog {sd}", H, "FIT 1999-2014", "fit", 16, grid=True)
        rows.append(rr)
        if rr["bets"] >= 30 and rr["roi%"] > 0:
            keep.append(sd)
    rows.append(cell(R[R.season.between(2015, 2025) & R.side.isin(keep)], f"REFINED dog {keep}", H,
                     "HOLD 2015-2025 close", "hold", 11, grid=True))
    c = xb[(xb.mag >= 7) & xb.d_flag & ~xb.f_flag & xb.side.isin(keep)]
    r, _ = bettable_ats(c, sb_t3, hyp=H, label=f"REFINED dog {keep} @T-3h", era="2020-2025", kind="hold", nseas=6)
    rows.append(r)
    show(rows)


# ─── (e) fade large moves ──────────────────────────────────────────────────

def load_sbr(g):
    s = pd.DataFrame(json.load(open(SBR_PATH, encoding="utf-8")))
    n0 = len(s)
    for c in ["home_final", "away_final", "home_open_spread", "home_close_spread",
              "open_over_under", "close_over_under", "date"]:
        s[c] = pd.to_numeric(s[c], errors="coerce")
    bad = s.home_team.map(lambda v: not isinstance(v, str)) | s.away_team.map(lambda v: not isinstance(v, str)) | s.date.isna()
    s = s[~bad].copy()
    s["gameday"] = pd.to_datetime(s.date.astype(int).astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
    j = g.merge(s.rename(columns={"home_final": "home_score", "away_final": "away_score", "season": "sbr_season"}),
                left_on=["season", "gameday", "home_score", "away_score"],
                right_on=["sbr_season", "gameday", "home_score", "away_score"], how="inner")
    dup = int(j.game_id.duplicated().sum())
    j = j.drop_duplicates("game_id")
    j["nm_ok"] = (j.home_team_y.map(NICK) == j.hf) & (j.away_team_y.map(NICK) == j.af)
    print(f"SBR rows={n0}, structurally corrupt dropped={int(bad.sum())}, joined to nflverse={len(j)} "
          f"(dupes dropped {dup}); nickname agreement={100*j.nm_ok.mean():.1f}%")
    j["open_hp"] = j["home_open_spread"]
    j["open_t"] = j["open_over_under"]
    okc = (j.home_close_spread.abs() <= 25) & (j.close_over_under >= 30)
    d = (j.loc[okc, "home_close_spread"] - j.loc[okc, "home_point_close"])
    dt = (j.loc[okc, "close_over_under"] - j.loc[okc, "total_line"])
    print(f"  SBR close vs nflverse close on SBR's clean-close rows (n={int(okc.sum())}): spread exact "
          f"{100*(d==0).mean():.1f}%, |d|<=0.5 {100*(d.abs()<=0.5).mean():.1f}%, |d|<=1 {100*(d.abs()<=1).mean():.1f}%; "
          f"total exact {100*(dt==0).mean():.1f}%, |d|<=1 {100*(dt.abs()<=1).mean():.1f}%; scrambled close rows "
          f"{int((~okc).sum())}")
    ok_s = j.open_hp.abs() <= 25
    ok_t = (j.open_t >= 30) & (j.open_t <= 70)
    j.loc[~ok_s, "open_hp"] = np.nan
    j.loc[~ok_t, "open_t"] = np.nan
    print(f"  SBR open dropped as implausible: spreads {int((~ok_s).sum())}, totals {int((~ok_t).sum())}")
    return j[["game_id", "season", "week", "game_type", "phase", "result", "total", "home_point_close",
              "total_line", "open_hp", "open_t", "nm_ok"]]


def key_move(o, c):
    out = np.zeros(len(o), dtype=bool)
    for k in (-7, -3, 3, 7):
        through = (np.minimum(o, c) < k) & (k < np.maximum(o, c))
        off = (o == k) & (c != k)
        out |= through | off
    return out


def fade_frames(df, o_hp, c_hp, o_t, c_t):
    """spread and total fade bets: columns game_id, season, mv, key, side, x (close), margin."""
    sp = df[df[o_hp].notna() & df[c_hp].notna()].copy()
    sp["mv"] = sp[c_hp] - sp[o_hp]
    sp = sp[sp.mv != 0]
    sp["key"] = key_move(sp[o_hp].values, sp[c_hp].values)
    sp["side"] = np.where(sp.mv < 0, "away", "home")
    sp["x"] = np.where(sp.side == "home", sp[c_hp], -sp[c_hp])
    sp["margin"] = np.where(sp.side == "home", sp.result, -sp.result)
    sp["amv"] = sp.mv.abs()
    tt = df[df[o_t].notna() & df[c_t].notna()].copy()
    tt["mv"] = tt[c_t] - tt[o_t]
    tt = tt[tt.mv != 0]
    tt["side"] = np.where(tt.mv > 0, "under", "over")
    tt["amv"] = tt.mv.abs()
    tt["line"] = tt[c_t]
    return sp, tt


def tot_grade(tt, line_col="line", price=-110):
    d = np.where(tt.side == "under", tt[line_col] - tt.total, tt.total - tt[line_col])
    win = (d > 0).astype(int); push = (d == 0).astype(int)
    pr = tt[price].values if isinstance(price, str) else price
    out = tt.copy()
    out["profit"] = profit_units(win, pr, push)
    out["res"] = res_of(win, push)
    return out


SP_CUTS = (1.5, 2, 2.5, 3, 3.5)
T_CUTS = (2, 2.5, 3, 3.5, 4)


def run_e(g, o):
    hdr("(e) FADE LARGE OPEN-TO-CLOSE MOVES (Moskowitz 2021 overreaction; 'large moves only')")
    H = "e"
    S = load_sbr(g)
    sp, tt = fade_frames(S, "open_hp", "home_point_close", "open_t", "total_line")
    SP = ats(sp); TT = tot_grade(tt)
    print(f"  SBR spread moves != 0: {len(sp)}; |move| quantiles 50/90/99: "
          f"{sp.amv.quantile(.5)}/{sp.amv.quantile(.9)}/{sp.amv.quantile(.99)}; total moves != 0: {len(tt)}")
    eras = [("DISC SBR 2011-2019", 2011, 2019, "fit"), ("SBR 2020-2021", 2020, 2021, "oos")]
    print("\nCLOSE -110 (SBR open -> nflverse close; closing-line study). Spreads, fade the move:")
    rows = []
    fit_cells = {}
    for name, a, b, kind in eras:
        c0 = SP[SP.season.between(a, b)]
        for cut in SP_CUTS:
            for kn, kf in (("all", lambda d: d.amv >= 0), ("KEY", lambda d: d.key)):
                c = c0[(c0.amv >= cut) & kf(c0)]
                pub = cut in (2, 2.5, 3)
                rr = cell(c, f"spread |mv|>={cut} {kn}{' (pub)' if pub else ''}", H, name,
                          ("grid-" + kind) if not pub else kind, nseasons(a, b), grid=True)
                rows.append(rr)
                if kind == "fit":
                    fit_cells[("spreads", cut, kn)] = (rr.get("roi%", -999), rr.get("/szn", 0))
        c = c0[c0.amv.between(0.5, 1.0)]
        rows.append(cell(c, "spread 0.5<=|mv|<=1 (placebo)", H, name, "placebo", nseasons(a, b), grid=True))
    show(rows)
    print("\nCLOSE -110 totals, fade the move:")
    rows = []
    for name, a, b, kind in eras:
        c0 = TT[TT.season.between(a, b)]
        for cut in T_CUTS:
            c = c0[c0.amv >= cut]
            pub = cut in (2.5, 3.5)
            rr = cell(c, f"total |mv|>={cut}{' (pub)' if pub else ''}", H, name,
                      ("grid-" + kind) if not pub else kind, nseasons(a, b), grid=True)
            rows.append(rr)
            if kind == "fit":
                fit_cells[("totals", cut, "all")] = (rr.get("roi%", -999), rr.get("/szn", 0))
        c = c0[c0.amv.between(0.5, 1.0)]
        rows.append(cell(c, "total 0.5<=|mv|<=1 (placebo)", H, name, "placebo", nseasons(a, b), grid=True))
    show(rows)
    print("\nPer season, spread |mv|>=2.5 all and total |mv|>=2.5, CLOSE -110 (SBR):")
    show(season_rows(SP[SP.amv >= 2.5], "spr>=2.5") + season_rows(TT[TT.amv >= 2.5], "tot>=2.5"))
    print("\nEarly/late split, spread |mv|>=2.5 and total |mv|>=2.5, SBR 2011-2021:")
    rows = [cell(c, f"spr>=2.5 {ph}", H, "2011-2021", "split", 11, grid=True) for ph, c in SP[SP.amv >= 2.5].groupby("phase")]
    rows += [cell(c, f"tot>=2.5 {ph}", H, "2011-2021", "split", 11, grid=True) for ph, c in TT[TT.amv >= 2.5].groupby("phase")]
    show(rows)
    # bettable hold-out
    print("\nBETTABLE hold-out: opener board (lead <= 160h) -> T-1h board; bet the fade side at T-1h best point/price.")
    so = summ_points(board_open(o, "spreads", 160.0), 2.0)
    s1 = summ_points(board_at(o, "spreads", 1.0), 2.0)
    to = summ_points(board_open(o[o.season >= 2023], "totals", 160.0), 3.0)
    t1 = summ_points(board_at(o[o.season >= 2023], "totals", 1.0), 3.0)
    lead_note("spreads opener<=160h", so); lead_note("spreads T-1h", s1)
    lead_note("totals opener<=160h (2023-25)", to); lead_note("totals T-1h (2023-25)", t1)
    lit = summ_points(board_open(o, "spreads"), 2.0)
    print(f"  (literal first bettable spread quote: realised lead median {lit['lead'].median():.0f}h; "
          f"not used - 2023-25 first quotes are summer lookahead lines)")
    # SBR open vs odds_hist opener, 2020-2021
    chk = S[S.season.between(2020, 2021)].join(so[["med"]], on="game_id", how="inner")
    dd = (chk.open_hp - chk.med).dropna()
    print(f"  SBR open vs odds_hist opener median, 2020-21 (n={len(dd)}): exact {100*(dd==0).mean():.1f}%, "
          f"|d|<=0.5 {100*(dd.abs()<=0.5).mean():.1f}%, |d|<=1 {100*(dd.abs()<=1).mean():.1f}%")
    gb = g[g.season.between(2020, 2025)].set_index("game_id", drop=False)
    gb = gb.join(so[["med"]].rename(columns={"med": "o_hp"})).join(s1[["med"]].rename(columns={"med": "c_hp"}))
    gb = gb.join(to[["med"]].rename(columns={"med": "o_t"})).join(t1[["med"]].rename(columns={"med": "c_t"}))
    gb = gb.reset_index(drop=True)
    bsp, btt = fade_frames(gb, "o_hp", "c_hp", "o_t", "c_t")
    rows = []
    gr = {}
    for cut in SP_CUTS:
        for kn, kf in (("all", lambda d: d.amv >= 0), ("KEY", lambda d: d.key)):
            c = bsp[(bsp.amv >= cut) & kf(bsp)]
            pub = cut in (2, 2.5, 3)
            r, gg = bettable_ats(c, s1, hyp=H, label=f"spread |mv|>={cut} {kn} @T-1h", era="2020-2025",
                                 kind="oos" if pub else "grid-oos", nseas=6, extra=None)
            rows.append(r); gr[("spreads", cut, kn)] = r
            if cut == 2.5 and kn == "all":
                per_sp = gg
    r, _ = bettable_ats(bsp[bsp.amv.between(0.5, 1.0)], s1, hyp=H, label="spread 0.5<=|mv|<=1 @T-1h (placebo)",
                        era="2020-2025", kind="placebo", nseas=6)
    rows.append(r)
    # totals at T-1h best point/price
    bt = btt.join(t1[["hi", "lo", "ph_lo", "pa_hi"]], on="game_id", how="inner")
    bt["line_b"] = np.where(bt.side == "under", bt.hi, bt.lo)
    bt["pr_b"] = np.where(bt.side == "under", bt.pa_hi, bt.ph_lo)
    bt = bt[bt.pr_b.notna()]
    BT = tot_grade(bt, "line_b", "pr_b")
    for cut in T_CUTS:
        pub = cut in (2.5, 3.5)
        rr = cell(BT[BT.amv >= cut], f"total |mv|>={cut} @T-1h", H, "2023-2025", "oos" if pub else "grid-oos", 3)
        rows.append(rr); gr[("totals", cut, "all")] = rr
    rows.append(cell(BT[BT.amv.between(0.5, 1.0)], "total 0.5<=|mv|<=1 @T-1h (placebo)", H, "2023-2025", "placebo", 3))
    show(rows)
    print("\nPer season, BETTABLE hold-out: spread |mv|>=2.5 all @T-1h (2020-2025) and total |mv|>=2.5 @T-1h (2023-2025):")
    show(season_rows(per_sp, "spr>=2.5 @T-1h") + season_rows(BT[BT.amv >= 2.5], "tot>=2.5 @T-1h"))
    elig = {k: v for k, v in fit_cells.items() if v[1] >= 10}
    best = max(elig, key=lambda k: elig[k][0])
    print(f"\nREFINEMENT (registered): best FIT cell with >=10 fit bets/season = {best} "
          f"(fit ROI {elig[best][0]}%); its BETTABLE hold-out row above is the single graded read:")
    hr = dict(gr[best]); hr["cell"] = "REFINED " + hr["cell"]
    show([hr])
    REGISTRY.append({"hyp": H, "kind": "hold", "cell": hr["cell"], "era": hr["era"], "bets": hr.get("bets", 0),
                     "roi%": hr.get("roi%", np.nan), "p": hr.get("p", np.nan)})
    # ADDED AFTER THE FIRST RUN (not registered): the 2020-21 overlap showed SBR opens that disagree with
    # the odds_hist opener. A data-only flag (no outcome used): open and close on opposite sides of zero
    # with both |.| >= 2.5, or |close - open| > 7.
    print("\nPOST-HOC DATA CHECK (added after the first run; not registered): SBR open quality.")
    S2 = S.copy()
    S2["mv"] = S2.home_point_close - S2.open_hp
    S2["suspect"] = (((np.sign(S2.open_hp) != np.sign(S2.home_point_close)) & (S2.open_hp.abs() >= 2.5)
                      & (S2.home_point_close.abs() >= 2.5)) | (S2.mv.abs() > 7))
    ck = S2[S2.season.between(2020, 2021)].join(so[["med"]], on="game_id", how="inner")
    ck["d"] = (ck.open_hp - ck.med).abs()
    print(f"  suspect SBR rows: {int(S2.suspect.sum())} of {len(S2)}; by season {S2.groupby('season').suspect.sum().to_dict()}")
    for k, x in ck.groupby("suspect"):
        print(f"  2020-21 suspect={k}: n={len(x)}, share |SBR open - odds_hist opener| >= 3 = {100*(x.d >= 3).mean():.1f}%, "
              f"exact = {100*(x.d == 0).mean():.1f}%")
    for cut in (2, 2.5, 3, 3.5):
        x = S2[S2.mv.abs() >= cut]
        print(f"  share of SBR |move| >= {cut} rows flagged suspect: {100*x.suspect.mean():.1f}% (n={len(x)})")
    to = summ_points(board_open(o[o.season <= 2021], "totals"), 3.0)
    ct = S2[S2.season.between(2020, 2021)].join(to[["med", "lead"]], on="game_id", how="inner")
    dt = (ct.open_t - ct.med).abs()
    print(f"  totals: SBR open vs the single odds_hist 2020-21 totals snapshot (lead median {ct.lead.median():.0f}h): "
          f"n={len(dt)}, exact {100*(dt == 0).mean():.1f}%, |d|<=1 {100*(dt <= 1).mean():.1f}%, |d|>=3 {100*(dt >= 3).mean():.1f}%")
    sp2, _ = fade_frames(S2[~S2.suspect], "open_hp", "home_point_close", "open_t", "total_line")
    SP2 = ats(sp2)
    print("  SBR DISC 2011-2019 spreads with suspect rows removed (post-hoc sensitivity, CLOSE -110):")
    rows = []
    c0 = SP2[SP2.season.between(2011, 2019)]
    for cut in SP_CUTS:
        for kn, kf in (("all", lambda d: d.amv >= 0), ("KEY", lambda d: d.key)):
            c = c0[(c0.amv >= cut) & kf(c0)]
            rows.append(cell(c, f"CLEAN spread |mv|>={cut} {kn}", H, "DISC SBR 2011-2019", "posthoc", 9, grid=True))
    show(rows)


# ─── (f) moneyline vs spread at extreme totals ─────────────────────────────

def tbucket(t):
    return np.select([t <= 39.5, t >= 50], ["tot<=39.5", "tot>=50"], "tot40-49.5")


def run_f(g, sb_t3, tb_t3, hb_t3):
    hdr("(f) MONEYLINE vs SPREAD AT EXTREME TOTALS: bet the ML side priced better than a spread+total win model")
    H = "f"
    fit = g[g.season.between(1999, 2014) & (g.result != 0) & g.total_line.notna()].copy()
    y = (fit.result > 0).astype(int)
    s = fit.spread_line; tc = fit.total_line - 44
    Xf = sm.add_constant(pd.DataFrame({"s": s, "tc": tc, "s_tc": s * tc}))
    Xs = sm.add_constant(pd.DataFrame({"s": s}))
    mf = sm.Logit(y, Xf).fit(disp=0); ms = sm.Logit(y, Xs).fit(disp=0)
    print(f"FIT 1999-2014 games n={len(fit)}")
    print("FULL logit coefficients (coef, se):", {k: (round(float(v), 5), round(float(mf.bse[k]), 5)) for k, v in mf.params.items()})
    print("SPREAD-ONLY logit coefficients:", {k: (round(float(v), 5), round(float(ms.bse[k]), 5)) for k, v in ms.params.items()})
    print(f"  log-lik FULL {mf.llf:.1f} vs SPREAD-ONLY {ms.llf:.1f}; LR stat {2*(mf.llf-ms.llf):.2f} on 2 df")

    def predict(sv, tv):
        sv = np.asarray(sv, float); tv = np.asarray(tv, float) - 44
        pf = mf.predict(np.column_stack([np.ones_like(sv), sv, tv, sv * tv]))
        ps = ms.predict(np.column_stack([np.ones_like(sv), sv]))
        return pf, ps

    for sv in (3, 7):
        for tv in (37, 44, 51):
            pf, ps = predict([sv], [tv])
            print(f"  home fav by {sv} at total {tv}: p_full={pf[0]:.3f} p_spread_only={ps[0]:.3f}")

    def bets(df, s_col, t_col, mlh, mla, model):
        x = df[df[mlh].notna() & df[mla].notna() & df[t_col].notna()].copy()
        pf, ps = predict(x[s_col], x[t_col])
        p = pf if model == "FULL" else ps
        dh = am_to_dec(x[mlh].values); da = am_to_dec(x[mla].values)
        evh = p * dh - 1; eva = (1 - p) * da - 1
        x["side"] = np.where(evh >= eva, "home", "away")
        x["ev"] = np.maximum(evh, eva)
        x["price"] = np.where(x.side == "home", x[mlh], x[mla])
        x["margin"] = np.where(x.side == "home", x.result, -x.result)
        x["is_dog"] = np.where(x.side == "home", x[s_col] < 0, x[s_col] > 0)
        x["tb"] = tbucket(x[t_col].values)
        x["pdiff_fav"] = np.where(x[s_col] >= 0, pf - ps, (1 - pf) - (1 - ps))
        return ml_grade(x, "price")

    gp = g[g.season >= 2006]
    eras = [("DISC 2006-2014", 2006, 2014, "fit"), ("HOLD 2015-2025", 2015, 2025, "oos")]
    out = {}
    for model in ("FULL", "SPREAD-ONLY"):
        out[model] = bets(gp, "spread_line", "total_line", "home_moneyline", "away_moneyline", model)
    F = out["FULL"]
    print("\nMechanism check, POSTED games 2006-2025: mean (p_full - p_spread_only) for the FAVOURITE, by total bucket:")
    print("  " + str(F.groupby("tb")["pdiff_fav"].agg(["count", "mean"]).round(4).to_dict()))
    print("\nPOSTED ML (closing study). Rule as stated (FULL, m=0, extreme totals), placebo (middle totals), control (SPREAD-ONLY):")
    rows = []
    for name, a, b, kind in eras:
        for model in ("FULL", "SPREAD-ONLY"):
            X = out[model][out[model].season.between(a, b)]
            ext = X[(X.tb != "tot40-49.5") & (X.ev > 0)]
            mid = X[(X.tb == "tot40-49.5") & (X.ev > 0)]
            k1 = kind if model == "FULL" else "control"
            rows.append(cell(ext, f"{model} m=0 extreme totals", H, name, k1, nseasons(a, b),
                             extra={"dog%": round(100 * ext.is_dog.mean(), 0) if len(ext) else np.nan}))
            rows.append(cell(mid, f"{model} m=0 middle totals (placebo)", H, name, "placebo", nseasons(a, b),
                             extra={"dog%": round(100 * mid.is_dog.mean(), 0) if len(mid) else np.nan}))
    show(rows)
    print("\nNeighbourhood: m x total bucket, POSTED ML:")
    rows = []
    fitc = {}
    for name, a, b, kind in eras:
        for model in ("FULL", "SPREAD-ONLY"):
            X = out[model][out[model].season.between(a, b)]
            for tb in ("tot<=39.5", "tot40-49.5", "tot>=50", "both-extreme"):
                Xb = X[X.tb != "tot40-49.5"] if tb == "both-extreme" else X[X.tb == tb]
                for m in (0, .02, .04, .06):
                    c = Xb[Xb.ev > m]
                    rr = cell(c, f"{model} {tb} m>{m}", H, name,
                              ("grid-" + kind) if model == "FULL" else "control", nseasons(a, b),
                              extra={"dog%": round(100 * c.is_dog.mean(), 0) if len(c) else np.nan})
                    rows.append(rr)
                    if kind == "fit" and model == "FULL":
                        fitc[(tb, m)] = (rr.get("roi%", -999), rr.get("/szn", 0))
    show(rows)
    R = F[(F.tb != "tot40-49.5") & (F.ev > 0)]
    print("\nPer season, FULL m=0 extreme totals, POSTED ML:")
    show(season_rows(R, "f-rule"))
    print("\nEarly/late split, FULL m=0 extreme totals, POSTED ML 2006-2025:")
    show([cell(c, f"f-rule {ph}", H, "2006-2025", "split", 20) for ph, c in R.groupby("phase")])
    print("\nBETTABLE 2023-2025 at T-3h (model inputs from T-3h spread/total board medians, best bettable h2h):")
    gb = g[g.season.between(2023, 2025)].set_index("game_id", drop=False)
    gb = gb.join(sb_t3[["med"]], how="inner").join(tb_t3[["med"]].rename(columns={"med": "tmed"}), how="inner")
    gb = gb.join(hb_t3[["ml_h", "ml_a"]], how="inner").reset_index(drop=True)
    gb["s_b"] = -gb["med"]
    rows = []
    for model in ("FULL", "SPREAD-ONLY"):
        X = bets(gb, "s_b", "tmed", "ml_h", "ml_a", model)
        ext = X[(X.tb != "tot40-49.5") & (X.ev > 0)]
        mid = X[(X.tb == "tot40-49.5") & (X.ev > 0)]
        rows.append(cell(ext, f"{model} m=0 extreme @T-3h", H, "2023-2025", "oos" if model == "FULL" else "control", 3,
                         extra={"dog%": round(100 * ext.is_dog.mean(), 0) if len(ext) else np.nan}))
        rows.append(cell(mid, f"{model} m=0 middle @T-3h (placebo)", H, "2023-2025", "placebo", 3,
                         extra={"dog%": round(100 * mid.is_dog.mean(), 0) if len(mid) else np.nan}))
        if model == "FULL":
            XB = X
    show(rows)
    rows = []
    elig = {k: v for k, v in fitc.items() if v[1] >= 5 and k[0] != "tot40-49.5"}
    best = max(elig, key=lambda k: elig[k][0])
    print(f"\nREFINEMENT (registered): best DISC (bucket, m) among extreme buckets with >=5 bets/season = {best} "
          f"(disc ROI {elig[best][0]}%)")
    tb, m = best
    sel = lambda X: (X[X.tb != "tot40-49.5"] if tb == "both-extreme" else X[X.tb == tb]).pipe(lambda d: d[d.ev > m])
    for X, lab, era, ns in ((F[F.season.between(2015, 2025)], f"REFINED {tb} m>{m}", "HOLD 2015-2025 posted", 11),
                            (XB, f"REFINED {tb} m>{m} @T-3h", "2023-2025 bettable", 3)):
        c = sel(X)
        rows.append(cell(c, lab, H, era, "hold", ns, extra={"dog%": round(100 * c.is_dog.mean(), 0) if len(c) else np.nan}))
    show(rows)


# ─── multiplicity ──────────────────────────────────────────────────────────

def bh(p, q=0.10):
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    ranked = p[o] * n / (np.arange(n) + 1)
    qv = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n); out[o] = np.minimum(qv, 1.0)
    return out


def run_bh():
    hdr("MULTIPLICITY: Benjamini-Hochberg (q = 0.10) over every cell with a p-value")
    R = pd.DataFrame(REGISTRY)
    R = R[R.p.notna() & (R.bets > 0)].copy()
    n0 = len(R)
    R = R.drop_duplicates(["hyp", "era", "bets", "roi%", "p"])
    print(f"registered cells {n0}; identical duplicates removed (same cell printed in two tables) {n0 - len(R)}")
    R["q_all"] = bh(R.p.values)
    hold = R.kind.isin(["oos", "hold", "oos-cell", "grid-oos"])
    R["q_holdout"] = np.nan
    R.loc[hold, "q_holdout"] = bh(R.loc[hold, "p"].values)
    print(f"comparisons in the family: {len(R)} (hold-out / out-of-sample subset: {int(hold.sum())})")
    print("by rule and kind:")
    print(R.groupby(["hyp", "kind"]).size().unstack(fill_value=0).to_string())
    print(f"\ncells with q_all <= 0.10: {int((R.q_all <= 0.10).sum())}; hold-out cells with q_holdout <= 0.10: "
          f"{int((R.q_holdout <= 0.10).sum())}")
    print("\nsmallest 25 raw p-values (sign of ROI shown):")
    print(R.sort_values("p").head(25)[["hyp", "kind", "cell", "era", "bets", "roi%", "p", "q_all", "q_holdout"]]
          .round(4).to_string(index=False))
    print("\nevery hold-out / out-of-sample cell:")
    print(R[hold].sort_values(["hyp", "p"])[["hyp", "kind", "cell", "era", "bets", "roi%", "p", "q_all", "q_holdout"]]
          .round(4).to_string(index=False))


def main():
    sys.stdout = Tee(OUTFILE)
    g = load_games_all()
    print(f"nflverse games with result and closing spread: {len(g)} ({g.season.min()}-{g.season.max()})")
    o = load_odds()
    sb_t3 = summ_points(board_at(o, "spreads", 3.0), 2.0)
    tb_t3 = summ_points(board_at(o, "totals", 3.0), 3.0)
    hb_t3 = summ_h2h(board_at(o, "h2h", 3.0))
    lead_note("spreads T-3h (all 2020-25)", sb_t3)
    lead_note("totals >=3h (all 2020-25)", tb_t3)
    lead_note("h2h T-3h (2023-25)", hb_t3)
    run_a(g, o, sb_t3)
    run_b(g, o, sb_t3, hb_t3)
    run_c(g, sb_t3, tb_t3)
    run_d(g, sb_t3)
    run_e(g, o)
    run_f(g, sb_t3, tb_t3, hb_t3)
    run_bh()
    sys.stdout.flush()


if __name__ == "__main__":
    main()

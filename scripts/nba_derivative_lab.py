"""NBA derivative markets lab: first half, first quarter and team totals, graded at real prices.

WHAT. Eight markets -- h2h_h1, spreads_h1, totals_h1, h2h_q1, spreads_q1, totals_q1,
team_totals_home, team_totals_away -- priced once per game about an hour before tip
(the Odds API per-event history, `odds.source = 'odds_api_nba_derivative_history'`),
2024-25 and 2025-26. Three families are graded against the pre-registered bars in
docs/nba_models_2026.md §1:

  1. BLIND baselines, per market and side, at DraftKings and at the best bettable
     price at DraftKings' number.
  2. SHARP vs SOFT inside the one snapshot: Pinnacle's proportional no-vig against
     every bettable book at the SAME number (`sharp_strict`), and a labelled
     variant that also converts Pinnacle across one half point with a fitted
     push mass (`sharp_halfpt` -- it has a model in it, so it is not the NHL rule).
  3. DERIVED fair value: Pinnacle's full-game spread and total from the game-line
     fetch at or before the derivative snapshot, mapped to a fair first-half /
     first-quarter / team-total distribution with a linear map fit on 2020-21 ..
     2023-24 (seasons never graded here), discrete normal around it.

HOW A BET IS GRADED. Best price among config.BEST_LINE_BOOKMAKERS in the same
fetch at the same number (Pinnacle and Bovada are never a deciding price),
DraftKings-only beside it. Two-way implied sum must sit in 1.00-1.15. One unit to
win, risk = 1/(decimal-1) capped at 3 (tracking/discord_notifier.stake_for). A
push returns the stake and is left out of units risked. EV is conditional on no
push: p_win/(p_win+p_loss) * decimal - 1.

SETTLEMENT. First half = periods 1-2, first quarter = period 1 (nba_period_scores).
A 1H/1Q two-way moneyline tie is a push (every book's two-way implied sum sits
near 1.04, which is impossible if a tie lost both sides -- measured in the report).
Team totals settle on the final score including overtime.

DATA. The parquet cache only (scripts/nba_research_cache.py); Supabase is never
read here. Every candidate pool and every chosen bet list is written to --out.

    PYTHONPATH=. python -m scripts.nba_derivative_lab
    PYTHONPATH=. python -m scripts.nba_derivative_lab --cache <dir> --out <dir> --fit-seasons 2021 2022 2023 2024
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr, ndtri

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import config  # noqa: E402

BETTABLE = list(config.BEST_LINE_BOOKMAKERS)
SHARP = "pinnacle"
DERIV_SOURCE = "odds_api_nba_derivative_history"
LINES_SOURCE = "odds_api_historical"
MARKETS = ["h2h_h1", "spreads_h1", "totals_h1", "h2h_q1", "spreads_q1", "totals_q1",
           "team_totals_home", "team_totals_away"]
# stat that settles the market, and its kind. Side A = home (ml/spread) or over
# (total); side A wins when stat > thr, side B when stat < thr, equal is a push.
SPEC = {
    "h2h_h1": ("m1h", "ml"), "spreads_h1": ("m1h", "spread"), "totals_h1": ("t1h", "total"),
    "h2h_q1": ("m1q", "ml"), "spreads_q1": ("m1q", "spread"), "totals_q1": ("t1q", "total"),
    "team_totals_home": ("hpts", "total"), "team_totals_away": ("apts", "total"),
}
# the full-game input each derived stat is mapped from (league share), and the
# team-share variant: the first-half / first-quarter share of points and the
# half-margin tendency of the two teams, from their previous games only
MAP_X = {"t1h": "mu_T", "t1q": "mu_T", "m1h": "mu_M", "m1q": "mu_M", "hpts": "mu_H", "apts": "mu_A"}
MAPS = {
    "league": {"t1h": ["mu_T"], "t1q": ["mu_T"], "m1h": ["mu_M"], "m1q": ["mu_M"],
               "hpts": ["mu_H"], "apts": ["mu_A"]},
    "team": {"t1h": ["x_t1h"], "t1q": ["x_t1q"], "m1h": ["mu_M", "r_h1"], "m1q": ["mu_M", "r_q1"],
             "hpts": ["mu_H"], "apts": ["mu_A"]},
}
TEAM_WINDOW, TEAM_SHRINK = 82, 30
LADDER_CHECK = ["spreads_h1", "totals_h1", "spreads_q1", "totals_q1"]
GRADED = (2025, 2026)
CHOOSE_SEASON, CONFIRM_SEASON = 2025, 2026
EV_CUTS = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15)
PRICE_FLOORS = (None, -250, -200, -150)
SIDES = ("all", "A", "B")
# (family, second grid axis). The sharp families sweep a price floor, the derived
# ones a side; both sweep the EV cut.
FAMILIES = (("sharp_strict", "floor"), ("sharp_halfpt", "floor"), ("derived", "side"), ("derived_team", "side"))
COHERENT = (1.00, 1.15)
OFF_MED_PTS = 1.0          # a h1/q1 spread or total this far from the bettable median is a ladder rung
MAX_LEAD_MIN = 180.0       # derivative snapshot more than 3h before the listed start: excluded
STALE_MIN = 180.0          # a full-game quote older than this at its fetch is not used
FIT_TARGET_LEAD_MIN = 55.0 # fit seasons: the full-game fetch at or before tip-55m (the derivative stamp)
MIN_CHOOSE_BETS = 30       # a cell needs this many 2024-25 bets to be choosable (bar 5's floor)
N_BOOT, SEED = 4000, 7
N_PLACEBO = 20
DEFAULT_SIG = {"M": 12.5, "T": 18.5}


# ── helpers ────────────────────────────────────────────────────────────────

def to_utc(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True, format="mixed").astype("datetime64[ns, UTC]")


def am_to_dec(a) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    return np.where(a < 0, 1.0 + 100.0 / np.abs(a), 1.0 + a / 100.0)


def risk_for(dec) -> np.ndarray:
    """stake_for: one unit to win, risk capped at 3."""
    return np.minimum(1.0 / (np.asarray(dec, dtype=float) - 1.0), 3.0)


def thr_for(market: pd.Series, num: pd.Series) -> np.ndarray:
    kind = market.map(lambda m: SPEC[m][1])
    return np.where(kind == "ml", 0.0, np.where(kind == "spread", -num.astype(float), num.astype(float)))


def cond_pa(thr, mu, sd):
    """Discrete normal on the integers: P(A wins | no push) and P(push)."""
    thr, mu, sd = (np.asarray(x, dtype=float) for x in (thr, mu, sd))
    k_hi = np.floor(thr) + 1.0
    k_lo = np.ceil(thr) - 1.0
    p_gt = 1.0 - ndtr((k_hi - 0.5 - mu) / sd)
    p_lt = ndtr((k_lo + 0.5 - mu) / sd)
    return p_gt / (p_gt + p_lt), 1.0 - p_gt - p_lt


def solve_mu(thr, target, sd, iters: int = 60):
    """mu such that cond_pa(thr, mu, sd) == target (monotone in mu; bisection)."""
    thr, target, sd = (np.asarray(x, dtype=float) for x in (thr, target, sd))
    lo, hi = thr - 6 * sd, thr + 6 * sd
    for _ in range(iters):
        mid = (lo + hi) / 2
        p, _ = cond_pa(thr, mid, sd)
        up = p < target
        lo = np.where(up, mid, lo)
        hi = np.where(up, hi, mid)
    return (lo + hi) / 2


def boot_ci(day: np.ndarray, profit: np.ndarray, risk: np.ndarray) -> tuple[float, float]:
    """Whole-day bootstrap 90% CI of ROI (units won / units risked)."""
    if len(profit) == 0:
        return (np.nan, np.nan)
    _, inv = np.unique(np.asarray(day).astype(str), return_inverse=True)
    P = np.bincount(inv, weights=np.asarray(profit, dtype=float))
    R = np.bincount(inv, weights=np.asarray(risk, dtype=float))
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(P), size=(N_BOOT, len(P)))
    with np.errstate(invalid="ignore", divide="ignore"):
        roi = P[idx].sum(1) / R[idx].sum(1)
    return (float(np.nanpercentile(roi, 5)), float(np.nanpercentile(roi, 95)))


def roi(p, r) -> float:
    r = float(np.sum(r))
    return float(np.sum(p)) / r if r > 0 else np.nan


def md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    if df is None or len(df) == 0:
        return "(no rows)\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if pd.isna(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


# ── load ───────────────────────────────────────────────────────────────────

def load(cache: Path, games_cache: Path):
    games = pd.read_parquet(games_cache / "nba_games.parquet")
    games = games[["game_id", "season", "game_date", "home_team", "away_team", "home_score",
                   "away_score", "went_to_ot", "commence_time"]].copy()
    games["ct"] = to_utc(games.commence_time)
    per = pd.read_parquet(cache / "nba_period_scores.parquet")
    odds = pd.read_parquet(cache / "nba_odds.parquet", columns=[
        "game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "source", "created_at",
        "home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"])
    odds = odds[odds.source.isin([DERIV_SOURCE, LINES_SOURCE])]
    return games, per, odds


def build_outcomes(games: pd.DataFrame, per: pd.DataFrame, checks: dict) -> pd.DataFrame:
    agg = per.groupby("game_id").agg(h_sum=("home_points", "sum"), a_sum=("away_points", "sum"),
                                     nper=("period", "max"), nuniq=("period", "nunique"))
    q1 = per[per.period == 1].set_index("game_id")[["home_points", "away_points"]]
    q1.columns = ["hq1", "aq1"]
    h1 = per[per.period.isin([1, 2])].groupby("game_id").agg(
        hh1=("home_points", "sum"), ah1=("away_points", "sum"), h1n=("period", "nunique"))
    o = games.merge(agg, on="game_id", how="left").join(q1, on="game_id").join(h1, on="game_id")
    o["m1q"], o["t1q"] = o.hq1 - o.aq1, o.hq1 + o.aq1
    o["m1h"], o["t1h"] = o.hh1 - o.ah1, o.hh1 + o.ah1
    o["hpts"], o["apts"] = o.home_score, o.away_score
    has = o.nper.notna()
    o["ok"] = (has & o.home_score.notna() & (o.h_sum == o.home_score) & (o.a_sum == o.away_score)
               & (o.nuniq == o.nper) & (o.nper >= 4) & (o.h1n == 2))
    o["ot_mismatch"] = has & ((o.nper > 4).astype(int) != o.went_to_ot.fillna(-1).astype(int))
    rows = []
    for s, g in o.groupby("season"):
        rows.append({"season": int(s), "games": len(g), "with_periods": int(g.nper.notna().sum()),
                     "sum_matches_final": int(g.ok.sum()),
                     "mismatch": int((g.nper.notna() & ~g.ok).sum()),
                     "ot_flag_mismatch": int(g.ot_mismatch.sum()),
                     "ot_games": int((g.nper > 4).sum()),
                     "tie_rate_q1": float((g.m1q[g.ok] == 0).mean()) if g.ok.any() else np.nan,
                     "tie_rate_h1": float((g.m1h[g.ok] == 0).mean()) if g.ok.any() else np.nan})
    checks["outcomes"] = pd.DataFrame(rows)
    # the Voulgaris number: first-half and first-quarter share of scoring
    v = o[o.ok].copy()
    v["reg"] = v.t1h + per[per.period.isin([3, 4])].groupby("game_id")[["home_points", "away_points"]] \
        .sum().sum(axis=1).reindex(v.game_id).to_numpy()
    v["fin"] = v.home_score + v.away_score
    sh = []
    for s, g in v.groupby("season"):
        sh.append({"season": int(s), "games": len(g), "h1_share_of_final": g.t1h.sum() / g.fin.sum(),
                   "h1_share_of_regulation": g.t1h.sum() / g.reg.sum(),
                   "q1_share_of_final": g.t1q.sum() / g.fin.sum(),
                   "mean_1h_minus_half_final": (g.t1h - g.fin / 2).mean(),
                   "mean_final": g.fin.mean(), "mean_1h": g.t1h.mean(), "mean_1q": g.t1q.mean()})
    g = v[v.season.between(2019, 2023)]
    if len(g):
        sh.append({"season": "2019-2023", "games": len(g), "h1_share_of_final": g.t1h.sum() / g.fin.sum(),
                   "h1_share_of_regulation": g.t1h.sum() / g.reg.sum(),
                   "q1_share_of_final": g.t1q.sum() / g.fin.sum(),
                   "mean_1h_minus_half_final": (g.t1h - g.fin / 2).mean(),
                   "mean_final": g.fin.mean(), "mean_1h": g.t1h.mean(), "mean_1q": g.t1q.mean()})
    checks["shares"] = pd.DataFrame(sh)
    return o


# ── derivative quotes ──────────────────────────────────────────────────────

def build_quotes(odds: pd.DataFrame, games: pd.DataFrame, checks: dict) -> pd.DataFrame:
    d = odds[(odds.source == DERIV_SOURCE) & odds.market.isin(MARKETS)].copy()
    d = d.merge(games[["game_id", "season", "game_date", "ct"]], on="game_id", how="inner")
    d = d[d.season.isin(GRADED)]
    d["snap"] = to_utc(d.snapshot_at)
    d["lead_min"] = (d.ct - d.snap).dt.total_seconds() / 60.0
    inplay = d.snapshot_type.eq("in_play")
    bad = (d.lead_min <= 0) | (d.lead_min > MAX_LEAD_MIN)
    per_game = d.groupby("game_id").agg(lead=("lead_min", "first"), nsnap=("snap", "nunique"),
                                        season=("season", "first"))
    checks["lead"] = per_game.lead.describe(percentiles=[.01, .05, .5, .95, .99]).to_frame().T
    checks["lead_excl"] = {"rows_in_play": int(inplay.sum()), "rows_bad_lead": int(bad.sum()),
                           "games_bad_lead": int(d.loc[bad, "game_id"].nunique()),
                           "games_multi_snapshot": int((per_game.nsnap > 1).sum())}
    d = d[~inplay & ~bad].copy()
    is_tot = d.market.str.startswith("totals") | d.market.str.startswith("team_totals")
    is_spr = d.market.str.startswith("spreads")
    d["num"] = np.where(is_spr, d.spread_home, np.where(is_tot, d.total_line, 0.0)).astype(float)
    d["pa"] = np.where(is_tot, d.over_price, d.home_price).astype(float)
    d["pb"] = np.where(is_tot, d.under_price, d.away_price).astype(float)
    n_before = len(d)
    d = d.dropna(subset=["pa", "pb", "num"]).copy()
    checks["lead_excl"]["rows_missing_price_or_number"] = int(n_before - len(d))
    d["deca"], d["decb"] = am_to_dec(d.pa), am_to_dec(d.pb)
    d["isum"] = 1 / d.deca + 1 / d.decb
    d["coherent"] = d.isum.between(*COHERENT)
    sub = d[d.bookmaker.isin(BETTABLE) & d.market.isin(LADDER_CHECK) & d.coherent]
    med = sub.groupby(["game_id", "market"]).num.median().rename("bet_med")
    d = d.join(med, on=["game_id", "market"])
    d["off_med"] = d.market.isin(LADDER_CHECK) & ((d.num - d.bet_med).abs() > OFF_MED_PTS)
    d["even_gap"] = (1 / d.deca - 1 / d.decb).abs()
    d["main"] = d.groupby(["game_id", "market", "bookmaker"]).even_gap.rank(method="first").eq(1)
    dup = d.duplicated(["game_id", "market", "bookmaker", "num"], keep=False)
    checks["dup_rows"] = int(dup.sum())
    d = d.drop_duplicates(["game_id", "market", "bookmaker", "num"], keep="first")
    d["thr"] = thr_for(d.market, d.num)
    d["decision_snap"] = d.snap
    return d


def quote_checks(d: pd.DataFrame, games: pd.DataFrame, checks: dict) -> None:
    ng = d.groupby("season").game_id.nunique()          # games with any derivative quote
    rows = []
    for (m, b), g in d.groupby(["market", "bookmaker"]):
        r = {"market": m, "book": b}
        for s in GRADED:
            r[f"pct_games_{s}"] = g[g.season == s].game_id.nunique() / ng.get(s, np.nan)
        r.update({"rows": len(g), "lines_per_game": len(g) / g.game_id.nunique(),
                  "median_isum": g.isum.median(), "incoherent": int((~g.coherent).sum()),
                  "off_median_rungs": int(g.off_med.sum()),
                  "off_median_share": float(g.off_med.mean())})
        rows.append(r)
    checks["books"] = pd.DataFrame(rows)
    gm = d.groupby(["season", "market"]).game_id.nunique().unstack(0)
    checks["games_per_market"] = gm.reset_index()
    pin = d[(d.bookmaker == SHARP) & d.main & ~d.market.str.startswith("h2h")]
    checks["pin_whole"] = pin.groupby("market").num.apply(lambda s: float((s % 1 == 0).mean())) \
        .rename("pinnacle_share_whole_number").reset_index()
    # strict same-number availability: bettable book quote at Pinnacle's number
    pn = pin[["game_id", "market", "num"]].assign(pin=1)
    soft = d[d.bookmaker.isin(BETTABLE) & d.coherent & ~d.off_med & ~d.market.str.startswith("h2h")]
    j = soft.merge(pn, on=["game_id", "market", "num"], how="left")
    checks["same_number"] = j.groupby(["market", "bookmaker"]).pin.apply(lambda s: s.notna().mean()) \
        .unstack(0).reset_index()
    # 1H/1Q moneyline tie settlement: two-way implied sums per book
    ml = d[d.market.isin(["h2h_h1", "h2h_q1"])]
    checks["ml_isum"] = ml.groupby(["market", "bookmaker"]).isum.describe(percentiles=[.05, .5, .95])[
        ["count", "5%", "50%", "95%"]].reset_index()


# ── full-game fair value from the game-line fetches ────────────────────────

def build_line_rows(odds: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    gl = odds[(odds.source == LINES_SOURCE) & odds.market.isin(["spreads", "totals"])].copy()
    gl["snap"] = to_utc(gl.snapshot_at)
    gl["cat"] = to_utc(gl.created_at)
    gl["fetch_time"] = gl.groupby("cat").snap.transform("max")   # the fetch's own data time
    gl = gl.merge(games[["game_id", "ct", "season"]], on="game_id", how="inner")
    gl = gl[(gl.snapshot_type != "in_play") & (gl.snap <= gl.ct)].copy()
    gl["age_min"] = (gl.fetch_time - gl.snap).dt.total_seconds() / 60.0
    gl = gl[gl.age_min <= STALE_MIN]
    tot = gl.market.eq("totals")
    gl["num"] = np.where(tot, gl.total_line, gl.spread_home).astype(float)
    gl["pa"] = np.where(tot, gl.over_price, gl.home_price).astype(float)
    gl["pb"] = np.where(tot, gl.under_price, gl.away_price).astype(float)
    gl = gl.dropna(subset=["num", "pa", "pb"])
    gl["isum"] = 1 / am_to_dec(gl.pa) + 1 / am_to_dec(gl.pb)
    gl = gl[gl.isum.between(*COHERENT)].copy()
    gl["pA"] = (1 / am_to_dec(gl.pa)) / gl.isum
    return gl[["game_id", "season", "ct", "market", "bookmaker", "cat", "fetch_time", "snap", "num", "pA"]]


def fair_at(gl: pd.DataFrame, targets: pd.DataFrame, sig: dict) -> pd.DataFrame:
    """Full-game fair margin (mu_M) and total (mu_T) from the latest fetch at or
    before each game's target time. Pinnacle when it quotes in that fetch, else the
    median over the bettable books in that fetch."""
    gl = gl.copy()
    gl["mu"] = np.where(gl.market == "spreads",
                        -gl.num + sig["M"] * ndtri(gl.pA.clip(0.02, 0.98)),
                        gl.num + sig["T"] * ndtri(gl.pA.clip(0.02, 0.98)))
    gl["src"] = np.where(gl.bookmaker == SHARP, "pinnacle", "bettable_median")
    pin = gl[gl.bookmaker == SHARP].groupby(["game_id", "cat", "market"]).agg(
        fetch_time=("fetch_time", "first"), mu=("mu", "first"), raw=("num", "first"))
    pin["src"] = "pinnacle"
    bet = gl[gl.bookmaker.isin(BETTABLE)].groupby(["game_id", "cat", "market"]).agg(
        fetch_time=("fetch_time", "first"), mu=("mu", "median"), raw=("num", "median"))
    bet["src"] = "bettable_median"
    f = pd.concat([pin, bet[~bet.index.isin(pin.index)]]).reset_index()
    out = targets[["game_id", "tau"]].copy()
    for mk, tag in (("spreads", "M"), ("totals", "T")):
        x = f[f.market == mk].sort_values("fetch_time")
        t = out.sort_values("tau")
        m = pd.merge_asof(t, x[["game_id", "fetch_time", "mu", "raw", "src"]], left_on="tau",
                          right_on="fetch_time", by="game_id", direction="backward")
        m = m.set_index("game_id")
        out[f"mu_{tag}"] = out.game_id.map(m.mu)
        out[f"raw_{tag}"] = out.game_id.map(m.raw)
        out[f"src_{tag}"] = out.game_id.map(m.src)
        out[f"fetch_{tag}"] = out.game_id.map(m.fetch_time)
    out["mu_H"] = (out.mu_T + out.mu_M) / 2
    out["mu_A"] = (out.mu_T - out.mu_M) / 2
    return out


def team_tendencies(outc: pd.DataFrame) -> pd.DataFrame:
    """Per game, each team's period tendencies from its previous TEAM_WINDOW games
    with period scores (strictly earlier games only -- shift(1) -- so a night-one
    result counts for night two, whose decision is ~55 minutes before its own tip).
    s_h1 / s_q1: the game's first-half / first-quarter share of points, the two
    teams' shrunk shares averaged. r_h1 / r_q1: home minus away tendency to win the
    first half (quarter) by more than half (a quarter) of its final margin."""
    o = outc[outc.ok].sort_values("ct")
    fin, mfin = o.home_score + o.away_score, o.home_score - o.away_score
    h = pd.DataFrame({"game_id": o.game_id, "ct": o.ct, "team": o.home_team, "t1h": o.t1h, "t1q": o.t1q,
                      "fin": fin, "dh1": o.m1h - mfin / 2, "dq1": o.m1q - mfin / 4, "is_home": 1})
    a = pd.DataFrame({"game_id": o.game_id, "ct": o.ct, "team": o.away_team, "t1h": o.t1h, "t1q": o.t1q,
                      "fin": fin, "dh1": -o.m1h + mfin / 2, "dq1": -o.m1q + mfin / 4, "is_home": 0})
    lg = pd.concat([h, a], ignore_index=True).sort_values(["team", "ct"]).reset_index(drop=True)
    g = lg.groupby("team")
    for c in ("t1h", "t1q", "fin", "dh1", "dq1"):
        lg[f"s_{c}"] = g[c].transform(lambda s: s.shift(1).rolling(TEAM_WINDOW, min_periods=1).sum())
    lg["n"] = g.cumcount().clip(upper=TEAM_WINDOW)
    k = lg.n / (lg.n + TEAM_SHRINK)
    lg["sh_h1"] = 0.5 + k * (lg.s_t1h / lg.s_fin - 0.5).fillna(0)
    lg["sh_q1"] = 0.25 + k * (lg.s_t1q / lg.s_fin - 0.25).fillna(0)
    lg["rr_h1"] = (k * lg.s_dh1 / lg.n).fillna(0)
    lg["rr_q1"] = (k * lg.s_dq1 / lg.n).fillna(0)
    H = lg[lg.is_home == 1].set_index("game_id")
    A = lg[lg.is_home == 0].set_index("game_id")
    t = pd.DataFrame({"s_h1": (H.sh_h1 + A.sh_h1.reindex(H.index)) / 2,
                      "s_q1": (H.sh_q1 + A.sh_q1.reindex(H.index)) / 2,
                      "r_h1": H.rr_h1 - A.rr_h1.reindex(H.index),
                      "r_q1": H.rr_q1 - A.rr_q1.reindex(H.index),
                      "n_hist": np.minimum(H.n, A.n.reindex(H.index))})
    return t.reset_index()


def add_team(fr: pd.DataFrame, tend: pd.DataFrame) -> pd.DataFrame:
    fr = fr.merge(tend, on="game_id", how="left")
    fr["x_t1h"] = fr.mu_T * fr.s_h1
    fr["x_t1q"] = fr.mu_T * fr.s_q1
    return fr


def map_mu(df: pd.DataFrame, cf: dict) -> np.ndarray:
    mu = np.full(len(df), cf["a"])
    for b, x in zip(cf["b"], cf["x"]):
        mu = mu + b * df[x].to_numpy(dtype=float)
    return mu


def fit_map(outc: pd.DataFrame, gl: pd.DataFrame, tend: pd.DataFrame, fit_seasons: list[int], checks: dict):
    """Fit the full-game -> derivative maps (league share, team share) on seasons never graded here."""
    fo = outc[outc.season.isin(fit_seasons) & outc.ok].copy()
    fo["tau"] = fo.ct - pd.Timedelta(minutes=FIT_TARGET_LEAD_MIN)
    sig = dict(DEFAULT_SIG)
    for _ in range(2):   # full-game residual SDs, then recompute the price adjustment with them
        fr = fair_at(gl[gl.season.isin(fit_seasons)], fo, sig).merge(
            fo[["game_id", "season", "home_score", "away_score"] + list(MAP_X)], on="game_id")
        fr = fr.dropna(subset=["mu_M", "mu_T"])
        sig = {"M": float(np.std(fr.home_score - fr.away_score - fr.mu_M)),
               "T": float(np.std(fr.home_score + fr.away_score - fr.mu_T))}
    fr = add_team(fr, tend)
    coefs, rows = {}, []
    for variant, spec in MAPS.items():
        coefs[variant] = {}
        for y, xs in spec.items():
            a = fr.dropna(subset=[y] + xs)
            X = np.column_stack([np.ones(len(a))] + [a[x].to_numpy(dtype=float) for x in xs])
            beta, *_ = np.linalg.lstsq(X, a[y].to_numpy(dtype=float), rcond=None)
            cf = {"x": xs, "a": float(beta[0]), "b": [float(v) for v in beta[1:]], "n": int(len(a))}
            res = a[y].to_numpy(dtype=float) - map_mu(a, cf)
            cf["sd"] = float(res.std())
            coefs[variant][y] = cf
            row = {"variant": variant, "stat": y, "from": "+".join(xs), "n": len(a), "intercept": cf["a"],
                   "slopes": ", ".join(f"{v:.4f}" for v in cf["b"]), "resid_sd": cf["sd"],
                   "r2": 1 - res.var() / a[y].var(), "mean_y": a[y].mean()}
            if xs == ["mu_T"]:
                row["share_no_intercept"] = float((a[y] * a.mu_T).sum() / (a.mu_T ** 2).sum())
            if y in ("m1q", "m1h"):   # does the discrete normal reproduce ties?
                _, pp = cond_pa(np.zeros(len(a)), map_mu(a, cf), np.full(len(a), cf["sd"]))
                row["model_tie_rate"], row["actual_tie_rate"] = float(pp.mean()), float((a[y] == 0).mean())
            rows.append(row)
    checks["fit"] = pd.DataFrame(rows)
    checks["fit_sig_full"] = sig
    checks["fit_src"] = fr.src_T.value_counts(dropna=False).to_dict()
    checks["fit_n_games"] = {int(k): int(v) for k, v in fr.season.value_counts().sort_index().items()}
    return coefs, sig


# ── candidate pools ────────────────────────────────────────────────────────

def to_long(df: pd.DataFrame, pa_col: str, extra: list[str]) -> pd.DataFrame:
    base = ["game_id", "season", "game_date", "market", "bookmaker", "num", "thr", "decision_snap",
            "off_med", "main"] + extra
    a = df[base].copy()
    a["side"], a["price"], a["dec"], a["p"] = "A", df.pa.to_numpy(), df.deca.to_numpy(), df[pa_col].to_numpy()
    b = df[base].copy()
    b["side"], b["price"], b["dec"], b["p"] = "B", df.pb.to_numpy(), df.decb.to_numpy(), 1 - df[pa_col].to_numpy()
    out = pd.concat([a, b], ignore_index=True)
    out["ev"] = out.p * out.dec - 1
    return out


def grade(c: pd.DataFrame, outc: pd.DataFrame) -> pd.DataFrame:
    stat_val = np.full(len(c), np.nan)
    o = outc.set_index("game_id")
    for m, (stat, _) in SPEC.items():
        mask = (c.market == m).to_numpy()
        if mask.any():
            stat_val[mask] = c.loc[mask, "game_id"].map(o[stat]).to_numpy(dtype=float)
    ok = c.game_id.map(o.ok).fillna(False).astype(bool).to_numpy()
    s = np.where(ok, stat_val, np.nan)
    a_win, b_win, push = s > c.thr.to_numpy(), s < c.thr.to_numpy(), s == c.thr.to_numpy()
    sideA = (c.side == "A").to_numpy()
    win = np.where(sideA, a_win, b_win)
    res = np.where(np.isnan(s), "", np.where(push, "P", np.where(win, "W", "L")))
    c = c.copy()
    c["result"] = res
    r = risk_for(c.dec)
    c["risk"] = np.where(res == "P", 0.0, r)
    c["units"] = np.where(res == "W", r * (c.dec - 1), np.where(res == "L", -r, 0.0))
    c["side_label"] = np.where(c.market.str.startswith("h2h") | c.market.str.startswith("spreads"),
                               np.where(sideA, "home", "away"), np.where(sideA, "over", "under"))
    c["line"] = np.where(c.market.str.startswith("spreads"), np.where(sideA, c.num, -c.num),
                         np.where(c.market.str.startswith("h2h"), np.nan, c.num))
    return c[c.result != ""]


def sharp_pool(d: pd.DataFrame, coef: dict, halfpt: bool) -> pd.DataFrame:
    pin = d[(d.bookmaker == SHARP) & d.coherent & d.main].copy()
    pin["pin_pA"] = (1 / pin.deca) / pin.isum
    soft = d[d.bookmaker.isin(BETTABLE) & d.coherent].copy()
    strict = soft.merge(pin[["game_id", "market", "num", "pin_pA"]], on=["game_id", "market", "num"])
    strict["pA_fair"] = strict.pin_pA
    strict["match"] = "same_number"
    parts = [strict]
    if halfpt:
        sd_by_market = {m: coef[SPEC[m][0]]["sd"] for m in MARKETS}
        pin["sd"] = pin.market.map(sd_by_market)
        pin["mu_pin"] = solve_mu(pin.thr, pin.pin_pA, pin.sd)
        x = soft[~soft.market.str.startswith("h2h")].merge(
            pin[["game_id", "market", "num", "mu_pin", "sd"]].rename(columns={"num": "pin_num"}),
            on=["game_id", "market"])
        x = x[(x.num - x.pin_num).abs() == 0.5].copy()
        x["pA_fair"], _ = cond_pa(x.thr, x.mu_pin, x.sd)
        x["match"] = "half_point"
        parts.append(x.drop(columns=["pin_num", "mu_pin", "sd"]))
    allq = pd.concat(parts, ignore_index=True)
    return to_long(allq, "pA_fair", ["match"])


def derived_pool(d: pd.DataFrame, fair: pd.DataFrame, coef: dict) -> pd.DataFrame:
    soft = d[d.bookmaker.isin(BETTABLE) & d.coherent].merge(fair, on="game_id", how="inner")
    mu = np.full(len(soft), np.nan)
    sd = np.full(len(soft), np.nan)
    for m, (stat, _) in SPEC.items():
        k = (soft.market == m).to_numpy()
        cf = coef[stat]
        mu[k] = map_mu(soft.loc[k], cf)
        sd[k] = cf["sd"]
    soft["mu"], soft["sd"] = mu, sd
    soft = soft.dropna(subset=["mu"])
    soft["pA_fair"], soft["p_push"] = cond_pa(soft.thr, soft.mu, soft.sd)
    soft["match"] = "derived"
    return to_long(soft, "pA_fair", ["match", "mu", "sd", "fetch_M", "fetch_T", "src_M", "src_T"])


# ── grids ──────────────────────────────────────────────────────────────────

def select(pool: pd.DataFrame, ev_cut: float, floor, side: str, books=None, per: str = "market",
           rungs: bool = False) -> pd.DataFrame:
    c = pool
    if not rungs:
        c = c[~c.off_med]
    if books is not None:
        c = c[c.bookmaker.isin(books)]
    if side != "all":
        c = c[c.side == side]
    if floor is not None:
        c = c[c.price >= floor]
    c = c[c.ev >= ev_cut]
    key = ["game_id", "market"] if per == "market" else ["game_id"]
    return c.drop_duplicates(key, keep="first")   # pool is pre-sorted by ev desc


def summarize(b: pd.DataFrame, ci: bool = True) -> dict:
    out = {"bets": len(b), "W": int((b.result == "W").sum()), "L": int((b.result == "L").sum()),
           "P": int((b.result == "P").sum()), "units": float(b.units.sum()), "risk": float(b.risk.sum()),
           "roi": roi(b.units, b.risk)}
    for s in GRADED:
        x = b[b.season == s]
        out[f"n_{s}"], out[f"u_{s}"], out[f"roi_{s}"] = len(x), float(x.units.sum()), roi(x.units, x.risk)
        if ci and len(x):   # within-season early / late
            sm = x.game_date.sort_values().iloc[len(x) // 2]
            out[f"roi_{s}_early"] = roi(x.units[x.game_date < sm], x.risk[x.game_date < sm])
            out[f"roi_{s}_late"] = roi(x.units[x.game_date >= sm], x.risk[x.game_date >= sm])
    out["units_per_season"] = out["units"] / len(GRADED)
    if len(b):
        dmed = b.game_date.sort_values().iloc[len(b) // 2]
        e, l = b[b.game_date < dmed], b[b.game_date >= dmed]
        out["roi_early"], out["roi_late"] = roi(e.units, e.risk), roi(l.units, l.risk)
        out["split_date"] = str(dmed)
        out["side_A_share"] = float((b.side == "A").mean())
    if ci:
        out["ci_lo"], out["ci_hi"] = boot_ci(b.game_date.to_numpy(), b.units.to_numpy(), b.risk.to_numpy())
    return out


def run_grid(pool: pd.DataFrame, family: str, axis2: str, books=None, tag: str = "best") -> pd.DataFrame:
    """axis2 = 'floor' (price floor) or 'side'. One bet a game per market, and one
    a game across all markets ('ALL')."""
    rows = []
    a2 = PRICE_FLOORS if axis2 == "floor" else SIDES
    for scope in MARKETS + ["ALL"]:
        p = pool if scope == "ALL" else pool[pool.market == scope]
        per = "game" if scope == "ALL" else "market"
        for j, v in enumerate(a2):
            kw = {"floor": v, "side": "all"} if axis2 == "floor" else {"floor": None, "side": v}
            # the best-EV quote per key, once; a cut then keeps the keys whose best clears it
            # (identical to filtering on the cut first, because the pool is sorted by EV)
            top = select(p, -np.inf, books=books, per=per, **kw)
            for i, ev in enumerate(EV_CUTS):
                b = top[top.ev >= ev]
                r = summarize(b, ci=len(b) >= MIN_CHOOSE_BETS)
                r.update({"family": family, "books": tag, "market": scope, "ev_cut": ev,
                          axis2: "none" if v is None else str(v), "i": i, "j": j})
                rows.append(r)
    return pd.DataFrame(rows)


def choose(grid: pd.DataFrame, axis2: str) -> pd.DataFrame:
    """Per scope: the cell with the most 2024-25 units among cells with >= 30
    2024-25 bets. 2025-26 is never read by this choice."""
    out = []
    for scope, g in grid.groupby("market", sort=False):
        e = g[g[f"n_{CHOOSE_SEASON}"] >= MIN_CHOOSE_BETS]
        if not len(e):
            continue
        best = e.sort_values(f"u_{CHOOSE_SEASON}", ascending=False).iloc[0]
        nb = g[((g.i - best.i).abs() <= 1) & ((g.j - best.j).abs() <= 1) & ~((g.i == best.i) & (g.j == best.j))]
        r = best.to_dict()
        r["neighbours"] = len(nb)
        r["neighbours_pos"] = int((nb.units > 0).sum())
        r["neighbour_min_roi"] = float(nb.roi.min()) if len(nb) else np.nan
        r["neighbours_pos_2026"] = int((nb[f"u_{CONFIRM_SEASON}"] > 0).sum())
        out.append(r)
    return pd.DataFrame(out)


def placebo(pool: pd.DataFrame, ev_cut, floor, side, per, n=N_PLACEBO) -> dict:
    """Shuffle the fair probabilities within (date, market, side); re-select; grade."""
    rng = np.random.default_rng(SEED)
    rois, bets = [], []
    base = pool[~pool.off_med].reset_index(drop=True)
    grp = base.groupby(["game_date", "market", "side"]).ngroup().to_numpy()
    pv = base.p.to_numpy()
    o1 = np.lexsort((np.arange(len(base)), grp))
    for _ in range(n):
        o2 = np.lexsort((rng.random(len(base)), grp))
        newp = np.empty(len(base))
        newp[o2] = pv[o1]          # a permutation of p inside each (date, market, side) group
        x = base.copy()
        x["p"] = newp
        x["ev"] = x.p * x.dec - 1
        x = x.sort_values(["ev", "bookmaker"], ascending=[False, True])
        b = select(x, ev_cut, floor, side, per=per)
        rois.append(roi(b.units, b.risk))
        bets.append(len(b))
    return {"placebo_mean_roi": float(np.nanmean(rois)), "placebo_p95_roi": float(np.nanpercentile(rois, 95)),
            "placebo_mean_bets": float(np.mean(bets)), "placebo_rois": [round(v, 4) for v in rois]}


# ── baselines ──────────────────────────────────────────────────────────────

def blind(d: pd.DataFrame, outc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    q = d[d.coherent & d.main & ~d.off_med]
    dk = q[q.bookmaker == "draftkings"][["game_id", "market", "num"]]
    soft = d[d.bookmaker.isin(BETTABLE) & d.coherent].merge(dk, on=["game_id", "market", "num"])
    soft = soft.assign(pA_fair=np.nan)
    lg = to_long(soft, "pA_fair", [])
    lg = grade(lg, outc)
    lg = lg.sort_values(["dec", "bookmaker"], ascending=[False, True])
    best = lg.drop_duplicates(["game_id", "market", "side"]).assign(price_at="best_bettable_at_DK_number")
    dkb = lg[lg.bookmaker == "draftkings"].assign(price_at="draftkings")
    allb = pd.concat([dkb, best], ignore_index=True)
    rows = []
    for (pa, m, sl, s), g in allb.groupby(["price_at", "market", "side_label", "season"]):
        rows.append({"price_at": pa, "market": m, "side": sl, "season": s, "bets": len(g),
                     "W": int((g.result == "W").sum()), "L": int((g.result == "L").sum()),
                     "P": int((g.result == "P").sum()), "units": g.units.sum(), "roi": roi(g.units, g.risk),
                     "win_rate_ex_push": (g.result == "W").sum() / max(1, (g.result != "P").sum())})
    return pd.DataFrame(rows), allb


def bars_for(r: dict) -> dict:
    """docs/nba_models_2026.md §1, bars 4-10, on one chosen cell. Bars 1-3 hold by
    construction (best bettable price at the same number, units to win, every
    priced quote in the pool); 11 has no later derivative price to measure; 12 is
    enforced in the loaders (snapshot before tip, full-game fetch at or before the
    snapshot); 13 does not apply to team markets."""
    pos = lambda v: bool(pd.notna(v) and v > 0)  # noqa: E731
    b = {}
    b["4_confirmed_on_2025_26"] = pos(r.get(f"roi_{CONFIRM_SEASON}")) and r.get(f"n_{CONFIRM_SEASON}", 0) >= MIN_CHOOSE_BETS
    big = [s for s in GRADED if r.get(f"n_{s}", 0) >= MIN_CHOOSE_BETS]
    b["5_every_season_positive"] = bool(big) and all(pos(r.get(f"roi_{s}")) for s in big)
    b["6_200_bets_ci_above_0"] = r.get("bets", 0) >= 200 and pos(r.get("ci_lo"))
    b["7_plateau"] = r.get("neighbours", 0) > 0 and r.get("neighbours_pos", 0) == r.get("neighbours", 0)
    b["8_both_date_halves"] = pos(r.get("roi_early")) and pos(r.get("roi_late"))
    share = r.get("side_A_share", 0.5)
    lopsided = share > 0.7 or share < 0.3
    b["9_beats_blind_same_side"] = (pd.notna(r.get("roi")) and r["roi"] > r.get("blind_same_side_roi", np.inf)) \
        if lopsided else True
    b["10_placebo_loses"] = (pd.notna(r.get("placebo_mean_roi")) and r["placebo_mean_roi"] < 0
                             and pd.notna(r.get("roi")) and r["roi"] > r.get("placebo_p95_roi", np.inf))
    failed = [k for k, v in b.items() if not v]
    return {"bars_failed": ",".join(failed) if failed else "", "passes_bars_4_10": not failed,
            "bar_11_clv": "not measurable: one derivative snapshot, no later derivative price"}


def regrade_check(pool: pd.DataFrame, per: pd.DataFrame, games: pd.DataFrame, n: int = 3000) -> dict:
    """Re-grade a random sample row by row from the raw period rows, written the
    way a bettor reads the ticket (own line, own margin), and count disagreements
    with the vectorised grade."""
    s = pool.sample(min(n, len(pool)), random_state=SEED)
    pp: dict = {}
    for r in per[per.game_id.isin(set(s.game_id))].itertuples():
        pp.setdefault(r.game_id, {})[r.period] = (r.home_points, r.away_points)
    fin = games.set_index("game_id")[["home_score", "away_score"]]
    bad = 0
    for r in s.itertuples():
        P = pp[r.game_id]
        if r.market.endswith("_q1"):
            h, a = P[1]
        elif r.market.endswith("_h1"):
            h, a = P[1][0] + P[2][0], P[1][1] + P[2][1]
        else:
            h, a = fin.loc[r.game_id, "home_score"], fin.loc[r.game_id, "away_score"]
        home = r.side == "A"
        if r.market.startswith("h2h"):
            mine = (h - a) if home else (a - h)
            x = mine
        elif r.market.startswith("spreads"):
            my_line = r.num if home else -r.num          # spread_home is the HOME number
            x = ((h - a) if home else (a - h)) + my_line
        elif r.market.startswith("totals"):
            x = (h + a - r.num) if home else (r.num - (h + a))
        elif r.market == "team_totals_home":
            x = (h - r.num) if home else (r.num - h)
        else:
            x = (a - r.num) if home else (r.num - a)
        res = "P" if x == 0 else ("W" if x > 0 else "L")
        bad += res != r.result
    return {"rows_checked": len(s), "disagreements": int(bad)}


# ── main ───────────────────────────────────────────────────────────────────

BETCOLS = ["game_id", "game_date", "season", "market", "side_label", "line", "bookmaker", "price", "p",
           "ev", "decision_snap", "result", "units", "risk", "close_fair_prob", "match"]


def bet_list(b: pd.DataFrame) -> pd.DataFrame:
    x = b.copy()
    if "close_fair_prob" not in x:
        x["close_fair_prob"] = np.nan
    x = x[[c for c in BETCOLS if c in x.columns]].rename(columns={
        "side_label": "side", "bookmaker": "book", "p": "fair_prob", "decision_snap": "decision_fetch"})
    return x


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", default=str(ROOT / "data" / "local" / "nba"))
    ap.add_argument("--games-cache", default=None)
    ap.add_argument("--out", default="C:/Users/micha/AppData/Local/Temp/nba_rebuild/results")
    ap.add_argument("--fit-seasons", nargs="+", type=int, default=[2021, 2022, 2023, 2024])
    ap.add_argument("--tag", default="derivatives")
    a = ap.parse_args()
    t0 = time.time()
    cache, out = Path(a.cache), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    games, per, odds = load(cache, Path(a.games_cache or a.cache))
    checks: dict = {}
    outc = build_outcomes(games, per, checks)
    d = build_quotes(odds, games, checks)
    quote_checks(d, games, checks)
    gl = build_line_rows(odds, games)
    checks["line_rows_by_season"] = gl.groupby("season").game_id.nunique().to_dict()
    tend = team_tendencies(outc)
    coefs, sig = fit_map(outc, gl, tend, a.fit_seasons, checks)
    coef = coefs["league"]
    print(f"[{time.time()-t0:.0f}s] loaded; fit {json.dumps(coefs)[:400]}")

    # derived fair at the decision snapshot (latest game-line fetch at or before it),
    # and the derived CLOSE proxy (latest pre-tip fetch)
    tg = d.groupby("game_id").agg(tau=("decision_snap", "min"), ct=("ct", "first")).reset_index()
    fair = add_team(fair_at(gl, tg, sig), tend)
    fair_close = add_team(fair_at(gl, tg.assign(tau=tg.ct), sig), tend)
    checks["team_hist"] = fair.n_hist.describe().round(1).to_dict()
    # same-moment full-game fair, used only by the post-hoc robustness check: Pinnacle's
    # home and away team totals in the derivative fetch (they sum to the full-game total,
    # overtime included -- measured below), de-vigged to a mean with the fitted team-points SD
    ptt = d[(d.bookmaker == SHARP) & d.main & d.coherent & d.market.str.startswith("team_totals")].copy()
    ptt["fair_mean"] = ptt.num + coef["hpts"]["sd"] * ndtri(((1 / ptt.deca) / ptt.isum).clip(0.02, 0.98))
    pv = ptt.pivot_table(index="game_id", columns="market", values="fair_mean", aggfunc="first").dropna()
    same_moment = pd.DataFrame({"game_id": pv.index, "mu_H": pv.team_totals_home.to_numpy(),
                                "mu_A": pv.team_totals_away.to_numpy()})
    same_moment["mu_T"] = same_moment.mu_H + same_moment.mu_A
    same_moment["mu_M"] = same_moment.mu_H - same_moment.mu_A
    same_moment["fetch_T"] = same_moment.game_id.map(tg.set_index("game_id").tau)
    same_moment["fetch_M"] = same_moment.fetch_T
    same_moment["src_T"] = same_moment["src_M"] = "pinnacle_team_totals_same_fetch"
    checks["same_moment_games"] = int(len(same_moment))
    fair["gap_min_T"] = (fair.tau - pd.to_datetime(fair.fetch_T, utc=True)).dt.total_seconds() / 60.0
    checks["fair_cov"] = {"games": int(len(tg)), "with_mu_T": int(fair.mu_T.notna().sum()),
                          "with_mu_M": int(fair.mu_M.notna().sum()),
                          "src_T": fair.src_T.value_counts(dropna=False).to_dict(),
                          "gap_min_T": fair.gap_min_T.describe().round(1).to_dict()}
    # OT inclusion check: DK home TT + away TT main lines vs the full-game total
    tt = d[(d.bookmaker == "draftkings") & d.main & d.market.str.startswith("team_totals")]
    tts = tt.pivot_table(index="game_id", columns="market", values="num", aggfunc="first").dropna()
    tts = tts.join(fair.set_index("game_id")[["raw_T"]]).dropna()
    checks["tt_sum_vs_total"] = {"games": len(tts), "mean_tt_sum_minus_total":
                                 float((tts.team_totals_home + tts.team_totals_away - tts.raw_T).mean()),
                                 "median": float((tts.team_totals_home + tts.team_totals_away - tts.raw_T).median())}

    def close_prob(b: pd.DataFrame, cfs: dict, frame: pd.DataFrame | None = None) -> np.ndarray:
        """The bet side's probability through the map, from the full-game fair in
        `frame` (default: the last pre-tip fetch, the proxy close)."""
        f = b[["game_id"]].merge(fair_close if frame is None else frame, on="game_id", how="left")
        mu = np.full(len(b), np.nan)
        sd = np.full(len(b), np.nan)
        for m, (stat, _) in SPEC.items():
            k = (b.market == m).to_numpy()
            if k.any():
                mu[k] = map_mu(f.loc[k], cfs[stat])
                sd[k] = cfs[stat]["sd"]
        pa, _ = cond_pa(b.thr, mu, sd)
        return np.where(b.side == "A", pa, 1 - pa)

    # pools
    pools = {
        "sharp_strict": sharp_pool(d, coef, halfpt=False),
        "sharp_halfpt": sharp_pool(d, coef, halfpt=True),
        "derived": derived_pool(d, fair, coefs["league"]),
        "derived_team": derived_pool(d, fair, coefs["team"]),
    }
    for k in pools:
        p = grade(pools[k], outc).reset_index(drop=True)
        # the proxy close is read through the same map the family decides on (league for the sharp
        # families); map_p_decision is the same map at the decision fetch, so their difference is
        # the full-game line's movement between the decision and the last pre-tip fetch
        cfs = coefs["team"] if k == "derived_team" else coefs["league"]
        p["close_fair_prob"] = close_prob(p, cfs)
        p["map_p_decision"] = close_prob(p, cfs, fair)
        p["gap_min"] = p.game_id.map(fair.set_index("game_id").gap_min_T)
        p = p.sort_values(["ev", "bookmaker"], ascending=[False, True]).reset_index(drop=True)
        pools[k] = p
        p.drop(columns=[c for c in p.columns if p[c].dtype == object and c not in BETCOLS + ["side", "src_M", "src_T"]],
               errors="ignore").to_parquet(out / f"{a.tag}_pool_{k}.parquet", index=False)
    # Pinnacle's simultaneous no-vig, same number, on every derived quote (sharp agreement)
    sp = pools["sharp_strict"][["game_id", "market", "num", "side", "p"]].drop_duplicates(
        ["game_id", "market", "num", "side"]).rename(columns={"p": "pin_p"})
    for k in ("derived", "derived_team"):
        x = pools[k].merge(sp, on=["game_id", "market", "num", "side"], how="left")
        x["pin_ev"] = x.pin_p * x.dec - 1
        pools[k] = x.sort_values(["ev", "bookmaker"], ascending=[False, True]).reset_index(drop=True)
    print(f"[{time.time()-t0:.0f}s] pools: " + ", ".join(f"{k} {len(v):,}" for k, v in pools.items()))
    checks["regrade"] = {k: regrade_check(v, per, games) for k, v in pools.items()}
    print("regrade", checks["regrade"])

    # blind baselines
    blind_tab, blind_bets = blind(d, outc)
    blind_bets_out = bet_list(blind_bets.assign(match="blind"))
    blind_bets_out["price_at"] = blind_bets.price_at.to_numpy()
    blind_bets_out.to_parquet(out / f"{a.tag}_bets_blind.parquet", index=False)

    # grids
    grids, chosen = {}, {}
    for fam, axis2 in FAMILIES:
        g_best = run_grid(pools[fam], fam, axis2, books=BETTABLE, tag="best")
        g_dk = run_grid(pools[fam], fam, axis2, books=["draftkings"], tag="draftkings")
        grids[fam] = pd.concat([g_best, g_dk], ignore_index=True)
        grids[fam].to_parquet(out / f"{a.tag}_grid_{fam}.parquet", index=False)
        chosen[fam] = choose(g_best, axis2)
        print(f"[{time.time()-t0:.0f}s] grid {fam}: {len(g_best)} cells (+{len(g_dk)} DraftKings-only)")

    # the chosen cells, in full
    detail, breakdown = {}, {}
    for fam, axis2 in FAMILIES:
        rows = []
        for _, c in chosen[fam].iterrows():
            scope = c.market
            p = pools[fam] if scope == "ALL" else pools[fam][pools[fam].market == scope]
            per = "game" if scope == "ALL" else "market"
            floor = None if axis2 == "side" or c[axis2] == "none" else int(c[axis2])
            side = c[axis2] if axis2 == "side" else "all"
            b = select(p, c.ev_cut, floor, side, per=per)
            name = f"{fam}__{scope}__ev{c.ev_cut:.2f}__{axis2}{c[axis2]}"
            bl = bet_list(b)
            bl.to_parquet(out / f"{a.tag}_bets_{name}.parquet", index=False)
            dk = select(p, c.ev_cut, floor, side, per=per, books=["draftkings"])
            rg = select(p, c.ev_cut, floor, side, per=per, rungs=True)
            r = {"name": name, "family": fam, "market": scope, "ev_cut": c.ev_cut, axis2: c[axis2]}
            r.update(summarize(b))
            r.update({f"dk_{k}": v for k, v in summarize(dk, ci=False).items() if k in ("bets", "units", "roi")})
            r.update({f"rungs_{k}": v for k, v in summarize(rg, ci=False).items() if k in ("bets", "units", "roi")})
            r.update({k: c[k] for k in ("neighbours", "neighbours_pos", "neighbour_min_roi", "neighbours_pos_2026")})
            r.update(placebo(p, c.ev_cut, floor, side, per))
            # blind same side, same population (every game in scope with a quote passing the price floor)
            dom = "A" if r.get("side_A_share", 0.5) >= 0.5 else "B"
            bp = p[~p.off_med & (p.side == dom)]
            if floor is not None:
                bp = bp[bp.price >= floor]
            bp = bp.sort_values(["dec", "bookmaker"], ascending=[False, True]).drop_duplicates(
                ["game_id"] if per == "game" else ["game_id", "market"])
            r.update({"dominant_side": dom, "blind_same_side_bets": len(bp),
                      "blind_same_side_roi": roi(bp.units, bp.risk)})
            # CLV proxies
            r["proxy_close_ev_mean"] = float((b.close_fair_prob * b.dec - 1).mean()) if len(b) else np.nan
            mv = (b.close_fair_prob - b.map_p_decision).dropna()
            r["proxy_move_n"] = len(mv)
            r["proxy_move_toward"] = float((mv > 0.0005).mean()) if len(mv) else np.nan
            r["proxy_move_unchanged"] = float((mv.abs() <= 0.0005).mean()) if len(mv) else np.nan
            r["proxy_move_against"] = float((mv < -0.0005).mean()) if len(mv) else np.nan
            r["proxy_move_median"] = float(mv.median()) if len(mv) else np.nan
            r["proxy_move_mean"] = float(mv.mean()) if len(mv) else np.nan
            if fam.startswith("derived") and len(b):
                r["pin_quoted_share"] = float(b.pin_ev.notna().mean())
                r["pin_ev_median"] = float(b.pin_ev.median())
                dis = b[b.pin_ev < 0]   # the map says bet, Pinnacle's simultaneous no-vig says no
                r["disagree_bets"], r["disagree_units"], r["disagree_roi"] = len(dis), float(dis.units.sum()), roi(dis.units, dis.risk)
                ss = select(pools["sharp_strict"] if scope == "ALL" else pools["sharp_strict"][pools["sharp_strict"].market == scope],
                            0.0, None, "all", per=per)
                k = ["game_id"] if per == "game" else ["game_id", "market"]
                r["overlap_with_sharp_ev0"] = float(b.merge(ss[k + ["side"]], on=k + ["side"]).shape[0] / len(b))
            r.update(bars_for(r))
            # where the result comes from: book, price band, market (ALL scope)
            bb = b.assign(price_band=pd.cut(b.price, [-10000, -200, -150, -110, 100, 150, 250, 10000]).astype(str),
                          fetch_gap_min=pd.cut(b.gap_min, [-1, 15, 45, 100000],
                                               labels=["<=15", "15-45", ">45"]).astype(str))
            parts = []
            for col in ("bookmaker", "price_band", "market", "side_label", "fetch_gap_min"):
                t = bb.groupby(col, observed=True).agg(bets=("units", "size"), units=("units", "sum"),
                                                       risk=("risk", "sum")).reset_index()
                t["roi"] = t.units / t.risk
                t.insert(0, "by", col)
                parts.append(t.rename(columns={col: "value"}))
            breakdown[name] = pd.concat(parts, ignore_index=True)
            # POST-HOC, only for a derived cell that passes bars 4-10: the same cell with the
            # full-game fair taken from Pinnacle's two team totals in the derivative fetch itself
            # (same moment as the quote). Edge survives -> not a stale full-game fetch.
            if fam.startswith("derived") and r["passes_bars_4_10"]:
                sm_pool = derived_pool(d, add_team(same_moment, tend),
                                       coefs["team"] if fam == "derived_team" else coefs["league"])
                sm_pool = grade(sm_pool, outc).sort_values(["ev", "bookmaker"], ascending=[False, True])
                sp_ = sm_pool if scope == "ALL" else sm_pool[sm_pool.market == scope]
                sb = select(sp_, c.ev_cut, floor, side, per=per)
                s = summarize(sb)
                r.update({f"same_moment_{k}": s.get(k) for k in
                          ("bets", "units", "roi", "ci_lo", "ci_hi", f"roi_{CHOOSE_SEASON}", f"roi_{CONFIRM_SEASON}")})
                bet_list(sb).to_parquet(out / f"{a.tag}_bets_{name}__same_moment.parquet", index=False)
            rows.append(r)
        detail[fam] = pd.DataFrame(rows)
        detail[fam].to_parquet(out / f"{a.tag}_chosen_{fam}.parquet", index=False)

    # model diagnostics on graded seasons: derived p vs Pinnacle p vs DK no-vig, same quotes
    key = ["game_id", "market", "num", "side", "bookmaker"]
    dg = pools["derived"][(pools["derived"].bookmaker == "draftkings") & pools["derived"].pin_p.notna()
                          & (pools["derived"].result != "P") & (pools["derived"].side == "A")].copy()
    dg = dg.merge(pools["derived_team"][key + ["p"]].rename(columns={"p": "p_team"}), on=key, how="left")
    dkq = d[d.bookmaker == "draftkings"][["game_id", "market", "num", "deca", "decb"]]
    dg = dg.merge(dkq, on=["game_id", "market", "num"], how="left")
    dg["dk_p"] = (1 / dg.deca) / (1 / dg.deca + 1 / dg.decb)
    dg["y"] = (dg.result == "W").astype(float)
    diag = []
    for m, g in dg.groupby("market"):
        def ll(p):
            p = np.clip(p, 1e-4, 1 - 1e-4)
            return float(-(g.y * np.log(p) + (1 - g.y) * np.log(1 - p)).mean())
        diag.append({"market": m, "n": len(g), "logloss_league_map": ll(g.p), "logloss_team_map": ll(g.p_team),
                     "logloss_pinnacle": ll(g.pin_p), "logloss_dk_novig": ll(g.dk_p),
                     "mean_abs_league_minus_pin": float((g.p - g.pin_p).abs().mean()),
                     "mean_abs_team_minus_pin": float((g.p_team - g.pin_p).abs().mean())})
    checks["diag"] = pd.DataFrame(diag)

    n_cells = {fam: int(len(g)) for fam, g in grids.items()}
    checks["cells_searched"] = {**n_cells, "total": int(sum(n_cells.values()))}
    write_report(out / f"{a.tag}.md", checks, blind_tab, grids, chosen, detail, coef, sig, a, pools, breakdown)
    with open(out / f"{a.tag}_checks.json", "w", encoding="utf-8") as fh:
        json.dump({k: (v.to_dict(orient="records") if isinstance(v, pd.DataFrame) else v)
                   for k, v in checks.items()}, fh, default=str, indent=1)
    print(f"[{time.time()-t0:.0f}s] done -> {out / (a.tag + '.md')}")


def write_report(path, checks, blind_tab, grids, chosen, detail, coef, sig, a, pools, breakdown) -> None:
    L = []
    w = L.append
    w("# NBA derivative markets (first half, first quarter, team totals) -- auto-generated tables\n")
    w(f"Generated by `scripts/nba_derivative_lab.py` (cache `{a.cache}`), fit seasons {a.fit_seasons}, "
      f"graded seasons {list(GRADED)}; cut chosen on {CHOOSE_SEASON} (2024-25), confirmed on {CONFIRM_SEASON} (2025-26).\n")
    w("## A. Data checks\n")
    w("### Period scores against the final score\n")
    w(md_table(checks["outcomes"]))
    w("### First-half and first-quarter share of scoring (the Voulgaris number)\n")
    w(md_table(checks["shares"], "{:.4f}"))
    w("### Derivative snapshot lead (minutes before the listed start), per game\n")
    w(md_table(checks["lead"].round(1)))
    w("Exclusions: " + json.dumps(checks["lead_excl"]) + f"; duplicate rows dropped: {checks['dup_rows']}\n")
    w("### Games with at least one quote, per market and season\n")
    w(md_table(checks["games_per_market"], "{:.0f}"))
    w("### Books per market (coverage, ladder size, implied sum, incoherent, off-median rungs)\n")
    w(md_table(checks["books"]))
    w("### 1H/1Q two-way moneyline implied sums per book (tie settlement)\n")
    w(md_table(checks["ml_isum"]))
    w("### Pinnacle whole-number share, and how often a bettable quote sits at Pinnacle's exact number\n")
    w(md_table(checks["pin_whole"]))
    w(md_table(checks["same_number"]))
    w("### Full-game -> derivative map (fit seasons only)\n")
    w(md_table(checks["fit"], "{:.4f}"))
    w(f"Full-game residual SDs: {json.dumps(checks['fit_sig_full'])}; fit games by season "
      f"{json.dumps(checks['fit_n_games'])}; fit fair source {json.dumps(checks['fit_src'])}\n")
    w(f"Graded fair coverage: {json.dumps(checks['fair_cov'], default=str)}\n")
    w(f"Team-share map: prior games with period scores behind the thinner of the two teams, graded games: "
      f"{json.dumps(checks['team_hist'])}\n")
    w(f"Team totals vs full-game total (DraftKings home TT + away TT - full total): {json.dumps(checks['tt_sum_vs_total'])}\n")
    w(f"Independent row-by-row re-grade from raw period rows: {json.dumps(checks['regrade'])}\n")
    w("### Diagnostic: derived probability vs Pinnacle no-vig vs DraftKings no-vig, same DraftKings quotes (side A)\n")
    w(md_table(checks["diag"], "{:.4f}"))
    w("## B. Blind baselines (per market, side, season)\n")
    w(md_table(blind_tab.sort_values(["market", "side", "price_at", "season"])))
    for fam in grids:
        g = grids[fam]
        axis2 = "floor" if "floor" in g.columns else "side"
        w(f"## C. Grid: {fam} (EV cut x {axis2}); one bet a game per market, ALL = one a game across markets\n")
        for books in ("best", "draftkings"):
            for scope in MARKETS + ["ALL"]:
                x = g[(g.books == books) & (g.market == scope)]
                if not len(x):
                    continue
                w(f"#### {fam} / {scope} / price at {books}: ROI (units) [bets], pooled 2024-25 + 2025-26\n")
                piv = x.assign(cell=x.apply(lambda r: "" if r.bets == 0 else
                                            f"{r.roi*100:+.1f}% ({r.units:+.1f}) [{r.bets}]", axis=1)) \
                    .pivot(index="ev_cut", columns=axis2, values="cell").reset_index()
                w(md_table(piv))
                if books == "best":
                    piv2 = x.assign(cell=x.apply(lambda r: f"{r[f'roi_{CHOOSE_SEASON}']*100:+.1f}%/{r[f'n_{CHOOSE_SEASON}']} | "
                                                 f"{r[f'roi_{CONFIRM_SEASON}']*100:+.1f}%/{r[f'n_{CONFIRM_SEASON}']}"
                                                 if r.bets else "", axis=1)) \
                        .pivot(index="ev_cut", columns=axis2, values="cell").reset_index()
                    w("By season (2024-25 ROI/bets | 2025-26 ROI/bets):\n")
                    w(md_table(piv2))
    w("## D. Chosen cells (chosen on 2024-25 units, >= 30 bets), with every bar's inputs\n")
    w(f"Cells searched (each counted once; best price and DraftKings-only both included): "
      f"{json.dumps(checks['cells_searched'])}\n")
    for fam, t in detail.items():
        w(f"### {fam}\n")
        if len(t):
            cols = [c for c in t.columns if c not in ("placebo_rois",)]
            w(md_table(t[cols].T.reset_index().rename(columns={"index": "field"}).astype(str)))
    w("## E. Where each chosen cell's result comes from (book, price band, market, side)\n")
    for name, t in breakdown.items():
        w(f"#### {name}\n")
        w(md_table(t))
    path.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()

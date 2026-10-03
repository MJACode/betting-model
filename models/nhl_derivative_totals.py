"""NHL derivative totals: team goals, the alternate ladder, and the first period.

ONE MODULE, THREE MARKETS. The full-game total was graded four times and the
margin sits on both sides (docs/nhl_market_lab.md). These three are the markets
that were bought instead (`odds.source = odds_api_nhl_totals_history`). The
backtest and the card call the functions here; a side is published only by
being named in `PUBLISHED`, and that tuple stays empty unless a walk-forward
record clears `publishable`.

THE MODEL. A gradient-boosted Poisson mean of a team's goals (and, separately,
its first-period goals) from that team's own earlier games and its opponent's:

    goals for, half-lives 20 and 6 games
    shots for, half-life 20
    the opponent's goals against and shots for, half-life 20
    home or road, days of rest, games already played

Every input is strictly before the game: the weighted mean of EARLIER rows.
A game total is the sum of the two teams' means (independent Poisson counts
add). P(over the line) is the Poisson tail above floor(line), widened to a
negative binomial when the training rows are wider than Poisson — the same
rule models/nhl_props.py uses for saves.

SETTLEMENT. Alternate totals and the full-game score include overtime and the
shootout (one goal to the winner). The first period is the period score.
Team totals are graded on the three periods, which is what DraftKings' 2024
house rules said a pre-game team total does; the full-game score (overtime
included) is reported beside it because the current rule is unverified
(docs/nhl_market_research.md). A side that only wins on one of the two is not
publishable.

NOTHING IN `PUBLISHED` IS LIVE. Registering a side is a config change made
after `publishable` says yes. This module does not write a pick.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from models.nhl_props import PARAMS, excess_variance, p_over

FIRST_TRAIN_SEASON = 2018
MIN_PRIOR = 3
GOAL_FEATURES = ["gf_l", "gf_s", "sf_l", "opp_ga", "opp_sf", "is_home", "rest", "gp"]
P1_FEATURES = ["p1_l", "p1_s", "opp_p1a", "is_home", "rest", "gp"]
# Shots are the group an ablation drops. Rest is the other.
SHOT_FEATURES = ("sf_l", "opp_sf")
REST_FEATURES = ("rest",)
TEST_SEASONS = (2024, 2025, 2026)
# The price floor production would apply to an unregistered model
# (config.DEFAULT_MIN_ODDS). Longshot alternate rungs are a different bet.
PRICE_FLOOR = -200
EV_CUTS = (0.0, 0.03, 0.06, 0.08, 0.10, 0.12, 0.15)
# A side is published at this cut only when it, and both neighbours, clear.
PUBLISH_CUT = 0.10
COHERENT_SUM = (1.00, 1.15)

# (model_id, side). Empty: the walk-forward did not clear. The card reads this
# and writes nothing while it is empty.
PUBLISHED: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Market:
    model_id: str
    label: str
    # How a quote is keyed once prices are joined to a prediction.
    unit: str                 # 'team' (one bet per team) or 'game'


MARKETS = {
    "team_total": Market("nhl_team_total", "team total", "team"),
    "alternate_total": Market("nhl_alternate_total", "alternate total", "game"),
    "p1_total": Market("nhl_p1_total", "1st-period total", "game"),
}


def _ew(g, col: str, halflife: float, min_periods: int = MIN_PRIOR):
    return g[col].transform(lambda s: s.shift(1).ewm(halflife=halflife, min_periods=min_periods).mean())


def _rest_and_gp(df: pd.DataFrame, group: str) -> pd.DataFrame:
    df = df.sort_values([group, "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = df.groupby(group, sort=False)
    df["rest"] = (pd.to_datetime(df.game_date) - g.game_date.transform(
        lambda s: pd.to_datetime(s).shift(1))).dt.days.clip(upper=6).fillna(6)
    df["gp"] = g.cumcount()
    return df


def build_team_frame(logs: pd.DataFrame) -> pd.DataFrame:
    """One row per team-game. Goals and shots are the weighted mean of earlier games only."""
    d = logs.copy()
    for c in ("goals_for", "goals_against", "shots_for", "shots_against", "is_home"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = _rest_and_gp(d, "team")
    g = d.groupby("team", sort=False)
    d["gf_l"], d["gf_s"] = _ew(g, "goals_for", 20), _ew(g, "goals_for", 6)
    d["sf_l"] = _ew(g, "shots_for", 20)
    d["ga_l"] = _ew(g, "goals_against", 20)
    opp = d[["nhl_game_id", "team", "ga_l", "sf_l"]].rename(
        columns={"team": "opponent", "ga_l": "opp_ga", "sf_l": "opp_sf"})
    d = d.merge(opp, on=["nhl_game_id", "opponent"], how="left")
    return d


def _teams_from_game_id(game_id: str) -> tuple[str, str] | None:
    """`NHL_YYYY-MM-DD_AWAY_HOME` → (away, home). The period table has no teams."""
    parts = str(game_id).split("_")
    if len(parts) != 4 or parts[0] != "NHL":
        return None
    return parts[2], parts[3]


def build_p1_frame(periods: pd.DataFrame, games: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per team-game of first-period goals, from the period score.

    Where both sources have the game, the NHL API row wins: it covers the
    seasons the prices do, and the archive stops in 2022. Teams come from the
    game id (`NHL_date_AWAY_HOME`), so the frame does not depend on which
    seasons `games` happens to hold and the earlier seasons stay trainable.
    `games` is accepted so a caller can pass the same pair the team frame uses;
    it is not read.
    """
    del games
    p = periods.copy()
    p["rank"] = np.where(p["source"].eq("nhl_api_score"), 0, 1)
    p = p.sort_values("rank").drop_duplicates("game_id", keep="first")
    parsed = p.game_id.map(_teams_from_game_id)
    p = p[parsed.notna()].copy()
    parsed = parsed.dropna()
    p["away_team"] = [t[0] for t in parsed]
    p["home_team"] = [t[1] for t in parsed]
    home = p.assign(team=p.home_team, opponent=p.away_team, is_home=1,
                    p1_for=p.home_p1, p1_against=p.away_p1, nhl_game_id=p.game_id)
    away = p.assign(team=p.away_team, opponent=p.home_team, is_home=0,
                    p1_for=p.away_p1, p1_against=p.home_p1, nhl_game_id=p.game_id)
    cols = ["game_id", "nhl_game_id", "team", "opponent", "season", "game_date",
            "is_home", "p1_for", "p1_against"]
    d = pd.concat([home[cols], away[cols]], ignore_index=True)
    for c in ("p1_for", "p1_against", "is_home", "season"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = _rest_and_gp(d, "team")
    grp = d.groupby("team", sort=False)
    d["p1_l"], d["p1_s"] = _ew(grp, "p1_for", 20), _ew(grp, "p1_for", 6)
    d["p1a_l"] = _ew(grp, "p1_against", 20)
    opp = d[["nhl_game_id", "team", "p1a_l"]].rename(columns={"team": "opponent", "p1a_l": "opp_p1a"})
    # Two teams share a game_id, so the opponent join is on game_id + opponent name.
    opp = opp.rename(columns={"nhl_game_id": "game_id"})
    d = d.merge(opp, on=["game_id", "opponent"], how="left")
    return d


def usable(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    return frame.dropna(subset=features)


def fit(frame: pd.DataFrame, target: str, features: list[str], through_season: int,
        overdispersed: bool = True) -> dict:
    """Fit on played rows from FIRST_TRAIN_SEASON through `through_season`."""
    from xgboost import XGBRegressor
    tr = usable(frame, features).dropna(subset=[target])
    tr = tr[tr.season.between(FIRST_TRAIN_SEASON, through_season)]
    model = XGBRegressor(**PARAMS)
    y = tr[target].values.astype(float)
    x = tr[features].values.astype(float)
    model.fit(x, y)
    mu = np.clip(model.predict(x), 1e-3, None)
    alpha = excess_variance(y, mu) if overdispersed else 0.0
    return {"model": model, "dispersion": alpha, "n_train": len(tr), "features": list(features)}


def predict_mean(fitted: dict, rows: pd.DataFrame) -> np.ndarray:
    return np.clip(fitted["model"].predict(rows[fitted["features"]].values.astype(float)), 1e-3, None)


def walk_forward(team: pd.DataFrame, p1: pd.DataFrame,
                 seasons: tuple[int, ...] = TEST_SEASONS,
                 goal_features: list[str] | None = None,
                 p1_features: list[str] | None = None) -> pd.DataFrame:
    """Out-of-sample means for every test-season team-game, and the game sum."""
    goal_features = list(goal_features or GOAL_FEATURES)
    p1_features = list(p1_features or P1_FEATURES)
    parts = []
    for season in seasons:
        gfit = fit(team, "goals_for", goal_features, season - 1)
        te = usable(team[team.season == season], goal_features).copy()
        te["mu"] = predict_mean(gfit, te)
        te["dispersion"] = gfit["dispersion"]
        te["n_train"] = gfit["n_train"]
        if p1 is not None and len(p1):
            pfit = fit(p1, "p1_for", p1_features, season - 1)
            pe = usable(p1[p1.season == season], p1_features).copy()
            pe["mu_p1"] = predict_mean(pfit, pe)
            pe["p1_dispersion"] = pfit["dispersion"]
            te = te.merge(pe[["game_id", "team", "p1_for", "mu_p1", "p1_dispersion"]],
                          on=["game_id", "team"], how="left")
        parts.append(te)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def game_means(team_pred: pd.DataFrame) -> pd.DataFrame:
    """One row per game: the sum of the two teams' means."""
    t = team_pred.copy()
    t["is_home"] = pd.to_numeric(t["is_home"], errors="coerce")
    cols_h = ["game_id", "season", "game_date", "mu", "goals_for", "dispersion"]
    if "mu_p1" in t.columns:
        cols_h.append("mu_p1")
    home = t[t.is_home == 1][cols_h].drop_duplicates("game_id").rename(
        columns={"mu": "mu_home", "mu_p1": "mu_p1_home", "goals_for": "gf_home"})
    away_cols = ["game_id", "mu", "goals_for"] + (["mu_p1"] if "mu_p1" in t.columns else [])
    away = t[t.is_home == 0][away_cols].drop_duplicates("game_id").rename(
        columns={"mu": "mu_away", "mu_p1": "mu_p1_away", "goals_for": "gf_away"})
    g = home.merge(away, on="game_id", how="inner")
    g["mu_total"] = g.mu_home + g.mu_away
    if "mu_p1_home" in g.columns and "mu_p1_away" in g.columns:
        g["mu_p1"] = g.mu_p1_home + g.mu_p1_away
    return g


def _payout(price) -> np.ndarray:
    price = np.asarray(price, dtype=float)
    return np.where(price > 0, price / 100.0, 100.0 / np.abs(price))


def _implied_vec(price) -> np.ndarray:
    price = np.asarray(price, dtype=float)
    return np.where(price > 0, 100.0 / (price + 100.0), np.abs(price) / (np.abs(price) + 100.0))


def profit(actual, line, price, side: str) -> np.ndarray:
    """Flat-bet units for one side. A push (the count lands on the line) is 0.

    An over wins when the count is above the line. An under wins when it is
    below. A missing price or count is NaN, which is not a bet.
    """
    actual = np.asarray(actual, dtype=float)
    line = np.asarray(line, dtype=float)
    price = np.asarray(price, dtype=float)
    won = actual > line if side == "over" else actual < line
    out = np.where(won, _payout(price), np.where(actual == line, 0.0, -1.0))
    return np.where(np.isnan(price) | np.isnan(actual) | np.isnan(line), np.nan, out)


def side_frame(df: pd.DataFrame, mu: np.ndarray, line, over, under, actual,
               dispersion: float = 0.0) -> pd.DataFrame:
    """Both sides of every quote, with the model's probability and the flat profit."""
    mu = np.asarray(mu, dtype=float)
    line = np.asarray(line, dtype=float)
    po = p_over(mu, line, dispersion)
    base = df.reset_index(drop=True).copy()
    base["mu"] = mu
    base["line"] = line
    base["actual"] = np.asarray(actual, dtype=float)
    over_p = np.asarray(over, dtype=float)
    under_p = np.asarray(under, dtype=float)
    rows = []
    for side, price, prob in (("over", over_p, po), ("under", under_p, 1.0 - po)):
        s = base.copy()
        s["side"] = side
        s["price"] = price
        s["p"] = prob
        s["profit"] = profit(s["actual"], s["line"], price, side)
        pay = _payout(price)
        s["ev"] = np.where(np.isfinite(price), prob * (1.0 + pay) - 1.0, np.nan)
        rows.append(s)
    out = pd.concat(rows, ignore_index=True)
    two = np.isfinite(over_p) & np.isfinite(under_p)
    # The coherent-sum check is on the quote, so it applies to both of its sides.
    total = np.where(two, _implied_vec(over_p) + _implied_vec(under_p), np.nan)
    bad = two & ~((total >= COHERENT_SUM[0]) & (total <= COHERENT_SUM[1]))
    out["coherent"] = np.concatenate([~bad, ~bad])
    return out[out.coherent & out.price.notna() & out.profit.notna()].reset_index(drop=True)


def select_bets(sides: pd.DataFrame, *, side: str, cut: float, floor: float | None,
                keys: list[str]) -> pd.DataFrame:
    """One bet per key: the line on `side` with the best EV, at or above the floor."""
    b = sides[(sides.side == side) & (sides.ev >= cut)]
    if floor is not None:
        b = b[b.price >= floor]
    if b.empty:
        return b
    return (b.sort_values("ev", ascending=False, kind="mergesort")
            .drop_duplicates(keys)
            .sort_values(["game_date", *keys]))


def day_interval(bets: pd.DataFrame, n: int = 4000) -> tuple[float, float]:
    """95% interval on the mean return, resampling whole game days. Fractions, not percent.

    Seeded, so the same bets always give the same interval.
    """
    if bets.empty:
        return float("nan"), float("nan")
    g = bets.groupby(pd.to_datetime(bets.game_date).dt.date).profit.agg(["sum", "count"])
    if len(g) < 2:
        return float("nan"), float("nan")
    tot, cnt = g["sum"].values, g["count"].values
    idx = np.random.default_rng(7).integers(0, len(g), size=(n, len(g)))
    means = tot[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def publishable(bets: pd.DataFrame) -> bool:
    """True only when the record is not a one-season or one-half fluke.

    All of: at least two seasons with 30 or more bets and every one of those
    seasons has a positive mean; the early half and the late half (by date)
    are both positive; the day-resampled 95% interval lies entirely above zero.
    """
    if bets is None or len(bets) < 200:
        return False
    seasons = []
    for _, q in bets.groupby("season"):
        if len(q) >= 30:
            seasons.append(float(q.profit.mean()) > 0)
    if len(seasons) < 2 or not all(seasons):
        return False
    ordered = bets.sort_values(["game_date", "game_id"])
    half = len(ordered) // 2
    if half < 30:
        return False
    if float(ordered.profit.iloc[:half].mean()) <= 0 or float(ordered.profit.iloc[half:].mean()) <= 0:
        return False
    lo, _hi = day_interval(ordered)
    return bool(np.isfinite(lo) and lo > 0)


def neighbour_clears(by_cut: dict[float, pd.DataFrame], cut: float = PUBLISH_CUT) -> bool:
    """The cut and the cuts on either side of it in EV_CUTS all publishable.

    A lone peak is not a rule. The neighbours only have to be positive in
    `publishable`'s full sense too — a neighbour that fails the interval is
    not a plateau.
    """
    cuts = list(EV_CUTS)
    if cut not in cuts:
        return False
    i = cuts.index(cut)
    if i == 0 or i == len(cuts) - 1:
        return False
    return all(publishable(by_cut.get(cuts[j], pd.DataFrame())) for j in (i - 1, i, i + 1))

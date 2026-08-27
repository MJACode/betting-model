"""
NCAAF search — feature registry (spec section "Feature search space").

LEAKAGE CONTRACT (the hard constraint — everything here obeys it):
  Every feature for a game played on date D is computed from games played
  strictly BEFORE D. The opponent adjustment is refit per (season, week) on
  games with week < w only; no ridge fit ever sees the week it rates. Prior
  seasons are allowed (they are strictly prior), and the carryover blend uses
  the PRIOR season's final ratings, never the current season's end state.

Groups (registry keys map to `FEATURE_GROUPS`):
  A_adj    opponent-adjusted efficiency, built here by strictly-prior ridge
  A_raw    CFBD's own season-to-date columns — RAW, not opponent-adjusted
           (only SP+ is). Registered separately so "adjusted vs raw" is a
           measurable ablation instead of an assumption.
  B_decay  same signals under STD / EWM(hl=2,4,8) / prior-season carryover
  C_roster returning production + talent composite. QB continuity, QB-isolated
           EPA and the backup-QB flag need player-level CFBD ingestion that
           does not exist yet — this group is PARTIAL and labelled as such.
  D_market closing line anchor + open->close movement (Bovada 2021+ only)
  E_pace   tempo + weather (weather is totals-facing; wind is the live one)
  F_situ   HFA, rest, travel, altitude, neutral/conference/bowl/bye

Nothing in this module writes to the database.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Ridge strength on the TEAM columns. Lowered from an arbitrary initial 25.0.
# The trigger was a synthetic case that recovered HFA = -0.06 against a known
# +0.05 effect, but that turned out to need TWO conditions together: home
# assignment correlated with team strength AND team coefficients crushed hard
# enough that the imbalance could not be represented, leaving the unpenalised
# HFA column to absorb it. Balanced hosting alone removes the inversion, so
# 25.0 was not "broken" — it was simply unjustified. 5.0 is a defensible
# default and alpha is exposed as a search parameter, per the spec's
# hyperparameter budget, rather than being a magic constant either way.
# See tests/test_ncaaf_search_features.py for both cases pinned.
RIDGE_ALPHA = 5.0
# A within-season ridge over ~135 teams needs real volume before it says
# anything. Below this we return None and the caller falls back to the prior
# season, which is the correct answer in week 1-3 anyway.
MIN_PRIOR_GAMES = 60
CARRYOVER_K = 4.0           # w = g / (g + k), the shrinkage from the model plan doc
_HFA_SCALE = 100.0          # see fit_opponent_adjustment: keeps ridge from shrinking HFA

# Metrics the ridge adjusts. Each is a per-play (or per-opportunity) rate so
# that pace does not contaminate efficiency.
ADJ_METRICS = [
    "points_per_play",
    "yards_per_play",
    "rush_yards_per_play",
    "pass_yards_per_play",
    "third_down_rate",
    "turnovers_per_play",
    "havoc_per_play",
]


# ── Raw team-game frame ───────────────────────────────────────────────────────

def load_team_games(conn=None, seasons: list[int] | None = None) -> pd.DataFrame:
    """
    One row per (game, team) with per-play rates. The log stores exactly two
    rows per game, so a team's DEFENSE is its opponent's offensive row — we
    self-join to attach it rather than trusting a separate defensive column.
    """
    from data.db import get_connection
    owned = conn is None
    conn = conn or get_connection()
    try:
        where = ""
        params: list = []
        if seasons:
            where = f"WHERE season IN ({','.join(['%s'] * len(seasons))})"
            params = list(seasons)
        rows = conn.execute(f"""
            SELECT game_id, team, opponent, season, week, game_date,
                   is_home, is_neutral_site, is_conference_game,
                   points, points_allowed, total_yards, rushing_yards,
                   passing_yards, plays, possession_seconds, first_downs,
                   third_down_conv, third_down_att, turnovers,
                   sacks, tackles_for_loss
            FROM ncaaf_team_game_log {where}
            ORDER BY game_date, game_id
        """, params).fetchall()
    finally:
        if owned:
            conn.close()

    cols = ["game_id", "team", "opponent", "season", "week", "game_date",
            "is_home", "is_neutral_site", "is_conference_game",
            "points", "points_allowed", "total_yards", "rushing_yards",
            "passing_yards", "plays", "possession_seconds", "first_downs",
            "third_down_conv", "third_down_att", "turnovers",
            "sacks", "tackles_for_loss"]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df

    num = ["points", "points_allowed", "total_yards", "rushing_yards",
           "passing_yards", "plays", "possession_seconds", "first_downs",
           "third_down_conv", "third_down_att", "turnovers", "sacks",
           "tackles_for_loss", "week", "season"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Opponent's plays — needed to turn defensive counting stats into rates.
    opp = df[["game_id", "team", "plays"]].rename(
        columns={"team": "opponent", "plays": "opp_plays"})
    df = df.merge(opp, on=["game_id", "opponent"], how="left")

    p = df["plays"].replace(0, np.nan)
    op = df["opp_plays"].replace(0, np.nan)
    df["points_per_play"] = df["points"] / p
    df["yards_per_play"] = df["total_yards"] / p
    df["rush_yards_per_play"] = df["rushing_yards"] / p
    df["pass_yards_per_play"] = df["passing_yards"] / p
    df["third_down_rate"] = df["third_down_conv"] / df["third_down_att"].replace(0, np.nan)
    df["turnovers_per_play"] = df["turnovers"] / p
    # Havoc is a DEFENSIVE act: sacks + TFL charged against opponent plays.
    df["havoc_per_play"] = (df["sacks"].fillna(0) + df["tackles_for_loss"].fillna(0)) / op
    df.loc[df["sacks"].isna() & df["tackles_for_loss"].isna(), "havoc_per_play"] = np.nan

    df["seconds_per_play"] = df["possession_seconds"] / p
    df["game_date"] = df["game_date"].astype(str)
    return df


FCS_POOL = "__FCS__"


def load_fbs_membership(conn=None) -> set:
    """
    {(team, season)} for FBS teams. `ncaaf_team_stats.classification` only ever
    carries 'fbs', so absence from that set IS the non-FBS signal.
    """
    from data.db import get_connection
    owned = conn is None
    conn = conn or get_connection()
    try:
        rows = conn.execute("""
            SELECT DISTINCT team, season FROM ncaaf_team_stats
            WHERE lower(classification) = 'fbs'
        """).fetchall()
    finally:
        if owned:
            conn.close()
    return {(t, int(s)) for t, s in rows}


def pool_fcs_opponents(tg: pd.DataFrame, fbs: set) -> pd.DataFrame:
    """
    Collapse every non-FBS opponent into ONE pooled pseudo-team, and drop rows
    whose subject team is non-FBS.

    Why pooling beats dropping (the spec allows either): an FBS team's game
    against an FCS side still carries information about that FBS team, so
    dropping it throws away ~10% of the sample. Pooling keeps the game while
    (a) removing per-FCS-team coefficients estimated from one or two games --
    which put Stephen F. Austin in the 2024 top-8 offences -- and (b) giving
    the blowout mismatch somewhere to live other than the home-field term.

    Measured on 2023-24: unpooled HFA came out at +0.10 pts/play (~+6.9
    pts/game, roughly double the real CFB home edge) because FBS teams host
    FCS teams and bury them, so "home" partly encoded "massive mismatch".
    Restricting to FBS-vs-FBS put it at ~+3.8 pts/game.
    """
    out = tg.copy()
    team_is_fbs = [(t, s) in fbs for t, s in zip(out["team"], out["season"])]
    opp_is_fbs = [(o, s) in fbs for o, s in zip(out["opponent"], out["season"])]
    out = out[pd.Series(team_is_fbs, index=out.index)].copy()
    opp_is_fbs = pd.Series(opp_is_fbs, index=tg.index).loc[out.index]
    out.loc[~opp_is_fbs, "opponent"] = FCS_POOL
    out["opponent_is_fcs"] = (~opp_is_fbs).astype(int)
    return out


# ── Strictly-prior opponent adjustment ────────────────────────────────────────

@dataclass
class AdjRatings:
    """Opponent-adjusted offence/defence ratings as of a cut point."""
    offense: dict
    defense: dict
    hfa: float
    n_games: int
    league_mean: float


def fit_opponent_adjustment(prior: pd.DataFrame, metric: str,
                            alpha: float = RIDGE_ALPHA) -> AdjRatings | None:
    """
    Ridge-adjust `metric` for opponent quality on a STRICTLY PRIOR frame.

        metric ~ mu + off[team] + def[opponent] + hfa * is_home

    Higher offense coef = better offence. Higher defense coef = the defence
    ALLOWS more, i.e. worse — callers must subtract, not add.

    `prior` must already be filtered to games before the target week; this
    function does no filtering of its own on purpose, so the caller owns the
    leakage boundary and it is visible at the call site.
    """
    from sklearn.linear_model import Ridge

    sub = prior.dropna(subset=[metric, "team", "opponent"])
    if len(sub) < MIN_PRIOR_GAMES:
        return None

    teams = sorted(set(sub["team"]) | set(sub["opponent"]))
    idx = {t: i for i, t in enumerate(teams)}
    n, k = len(sub), len(teams)

    X = np.zeros((n, 2 * k + 1), dtype=np.float64)
    rows = np.arange(n)
    X[rows, [idx[t] for t in sub["team"]]] = 1.0            # offence
    X[rows, [k + idx[o] for o in sub["opponent"]]] = 1.0    # defence
    home = sub["is_home"].fillna(0).astype(float).to_numpy()
    neutral = sub["is_neutral_site"].fillna(0).astype(float).to_numpy()
    # Home-field is ONE globally-identified parameter estimated from every
    # game, not a noisy per-team effect, so it must not be shrunk toward zero
    # the way team columns are. sklearn's Ridge applies one alpha to all
    # columns, so we scale this column up by _HFA_SCALE and divide the
    # coefficient back out: scaling a column by c leaves the fit unchanged but
    # weakens its effective penalty by c**2. Without this, alpha=25 drove HFA
    # to the wrong SIGN on synthetic data with a known +0.05 home effect.
    X[:, 2 * k] = np.where(neutral > 0, 0.0, home) * _HFA_SCALE

    y = sub[metric].astype(float).to_numpy()
    model = Ridge(alpha=alpha, fit_intercept=True)
    model.fit(X, y)
    c = model.coef_
    return AdjRatings(
        offense={t: float(c[idx[t]]) for t in teams},
        defense={t: float(c[k + idx[t]]) for t in teams},
        hfa=float(c[2 * k] * _HFA_SCALE),
        n_games=n,
        league_mean=float(np.nanmean(y)),
    )


def build_adjusted_ratings(tg: pd.DataFrame,
                           metrics: list[str] | None = None,
                           alpha: float = RIDGE_ALPHA) -> dict:
    """
    Ratings for every (season, week) cut, fit ONLY on strictly prior games.

    Returns {(season, week, metric): AdjRatings}. Cut (s, w) uses games from
    season s with week < w. The week being rated never enters its own fit.
    """
    metrics = metrics or ADJ_METRICS
    out: dict = {}
    for season, sdf in tg.groupby("season"):
        weeks = sorted(w for w in sdf["week"].dropna().unique())
        for w in weeks:
            prior = sdf[sdf["week"] < w]
            if prior.empty:
                continue
            for m in metrics:
                r = fit_opponent_adjustment(prior, m, alpha)
                if r is not None:
                    out[(int(season), int(w), m)] = r
    return out


def build_prior_season_ratings(tg: pd.DataFrame,
                               metrics: list[str] | None = None,
                               alpha: float = RIDGE_ALPHA) -> dict:
    """Final full-season ratings, used as the PRIOR-season carryover term."""
    metrics = metrics or ADJ_METRICS
    out: dict = {}
    for season, sdf in tg.groupby("season"):
        for m in metrics:
            r = fit_opponent_adjustment(sdf, m, alpha)
            if r is not None:
                out[(int(season), m)] = r
    return out


def blended_rating(adj: dict, prior_season: dict, season: int, week: int,
                   metric: str, team: str, side: str,
                   games_played: float | None,
                   k: float = CARRYOVER_K) -> float | None:
    """
    Shrink the in-season rating toward the prior season's final rating:

        w = g / (g + k);   rating = w * in_season + (1 - w) * prior_season

    This is the model-plan fix for CFB's tiny per-team sample (12-13 games).
    With g=0 the value is purely last year; by g=8 it is ~2/3 this year.
    """
    cur = adj.get((season, week, metric))
    prev = prior_season.get((season - 1, metric))
    get = (lambda r: r.offense.get(team)) if side == "off" else (lambda r: r.defense.get(team))

    cur_v = get(cur) if cur else None
    prev_v = get(prev) if prev else None
    if cur_v is None and prev_v is None:
        return None
    if cur_v is None:
        return prev_v
    if prev_v is None:
        return cur_v

    g = float(games_played or 0.0)
    w = g / (g + k)
    return w * cur_v + (1.0 - w) * prev_v


# ── Recency variants (Group B) ────────────────────────────────────────────────

def rolling_variants(tg: pd.DataFrame, metrics: list[str] | None = None,
                     half_lives: tuple[float, ...] = (2.0, 4.0, 8.0)) -> pd.DataFrame:
    """
    Per (team, season, game) STD and exponentially-decayed means, all SHIFTED
    so a game never sees itself. Returns one row per (game_id, team).
    """
    metrics = metrics or ADJ_METRICS
    tg = tg.sort_values(["season", "team", "game_date", "game_id"]).copy()
    g = tg.groupby(["season", "team"], sort=False)

    out = tg[["game_id", "team", "season", "week", "game_date"]].copy()
    out["prior_games"] = g.cumcount()

    for m in metrics:
        shifted = g[m].shift(1)                      # strictly prior
        keyed = shifted.groupby([tg["season"], tg["team"]], sort=False)
        out[f"{m}__std"] = keyed.expanding().mean().reset_index(level=[0, 1], drop=True)
        for hl in half_lives:
            out[f"{m}__ewm{int(hl)}"] = (
                keyed.apply(lambda s: s.ewm(halflife=hl, ignore_na=True).mean())
                     .reset_index(level=[0, 1], drop=True))
    return out


# ── Registry ──────────────────────────────────────────────────────────────────

FEATURE_GROUPS: dict[str, list[str]] = {
    "A_adj": [
        "d_adj_points_per_play", "d_adj_yards_per_play",
        "d_adj_rush_yards_per_play", "d_adj_pass_yards_per_play",
        "d_adj_third_down_rate", "d_adj_turnovers_per_play",
        "d_adj_havoc_per_play",
    ],
    "A_raw": [
        "d_epa_per_play_off", "d_epa_per_play_def",
        "d_success_rate_off", "d_success_rate_def",
        "d_explosiveness_off", "d_explosiveness_def",
        "d_havoc_rate", "d_third_down_rate_off", "d_turnover_margin_pg",
        "d_sp_overall", "d_sp_offense", "d_sp_defense", "d_srs",
    ],
    "B_decay": [
        "d_points_per_play__std", "d_points_per_play__ewm2",
        "d_points_per_play__ewm4", "d_points_per_play__ewm8",
        "d_yards_per_play__ewm4", "d_havoc_per_play__ewm4",
        "d_turnovers_per_play__ewm4",
    ],
    "C_roster": ["d_returning_ppa", "d_talent"],
    # QB continuity/quality from ncaaf_qb_game. NOT "is the starter out this
    # week" -- that is unknowable pre-kickoff without an injury feed CFB does
    # not publish. See scripts/ncaaf_search/qb.py for the full framing.
    "C_qb": [
        "d_qb_prior_starts", "d_qb_changed", "d_qb_is_new",
        "d_qb_share_recent", "d_qb_ypa_recent", "d_qb_int_rate_recent",
        "d_qb_rush_ypg_recent", "qb_either_changed",
    ],
    "D_market": ["close_spread", "close_total", "line_move", "abs_line_move"],
    "E_pace": [
        "d_plays_per_game", "d_seconds_per_play", "sum_plays_per_game",
        "wx_wind_mph", "wx_temp_f", "wx_precip_mm", "is_dome_game",
    ],
    "F_situ": [
        "d_rest_days", "is_bye_advantage", "is_neutral_site",
        "is_conference_game", "venue_elevation_ft", "d_travel_miles",
        "week",
    ],
}

# The mandatory sanity baseline: market number + a home constant. Per the spec
# this MUST land near 50% against the close; if it does not, the harness is
# broken and every other number is meaningless.
MARKET_ONLY = ["close_spread", "close_total", "is_neutral_site"]

GROUP_ORDER = ["A_adj", "A_raw", "B_decay", "C_roster", "C_qb", "D_market",
               "E_pace", "F_situ"]


def features_for(groups: list[str]) -> list[str]:
    """Flatten a group selection into a column list, de-duplicated, in order."""
    seen, out = set(), []
    for g in groups:
        for c in FEATURE_GROUPS.get(g, []):
            if c not in seen:
                seen.add(c)
                out.append(c)
    return out

"""
nfl_prop_feature_engine.py — feature builder for the NFL player-prop models.

Twelve models across four response families (see docs/nfl_props_model.md):

  negative binomial  pass attempts / completions, carries, receptions,
                     tackles+assists          — overdispersed counts
  Poisson            pass TDs, sacks          — var/mean ~ 1
  zero-inf. Gamma    pass / rush / receiving / rush+rec yards
  logistic           anytime TD

ONE feature builder, per-market response heads. That split is the architecture
decision and it is measured, not stylistic: NFL yardage has a variance-to-mean
ratio of 27-36, so the platform's usual `count:poisson` head would be
catastrophically overconfident, while pass TDs really are Poisson. The obvious
alternative — a compound volume x per-play-efficiency model sharing a usage core
— was implemented and REJECTED on CRPS and log-loss (it loses outright on
rushing); the efficiency term is close to unforecastable, so the extra structure
buys estimation error.

Sources, all in Supabase, all free:
  nfl_player_game_log   outcomes + usage (targets, shares, air yards, EPA)
  nfl_team_game_stats   team volume (the share denominator + pace proxy),
                        opponent-defence-allowed, and the pre-game market and
                        environment context (spread, total, roof, wind)
  nfl_snap_counts       snap share — availability, and the main driver of the
                        tackles+assists market

Public API (parallels the NBA/WNBA prop engines):
  • build_nfl_prop_training_dataset(model_id, seasons) → DataFrame
  • build_nfl_prop_scoring_rows(game_date, model_id)   → DataFrame
  • NFL_PROP_FEATURE_MAP                                → {model_id: [cols]}

Look-ahead safety. Every rolling feature is `shift(1)` within the player (or
team) BEFORE the window, so a row can never see its own game. The scoring path
runs the SAME `_add_features` over history plus a synthesised row for the
upcoming game, which is what guarantees train/serve parity — there is no second
feature implementation to drift. The only pre-game inputs taken from the target
game itself are the schedule and the market context (spread, total, roof, wind),
all of which are genuinely known before kickoff.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from data.db import get_connection, DBConnection

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


ROLL_WINDOWS = (3, 8)

# Rolling means are taken over these player columns. `_r3` is form, `_r8` is
# roughly half a season — long enough to be stable, short enough that a role
# change (a traded WR1, an injured starter's backup) is reflected within a month.
_PLAYER_ROLL_COLS = [
    "attempts", "completions", "passing_yards", "passing_tds", "interceptions",
    "sacks_suffered", "passing_air_yards",
    "carries", "rushing_yards", "rushing_tds",
    "targets", "receptions", "receiving_yards", "receiving_tds",
    "receiving_air_yards", "receiving_yac",
    "target_share", "air_yards_share", "wopr",
    "def_tackles_solo", "def_tackle_assists", "def_sacks", "def_qb_hits",
    "offense_pct", "defense_pct", "st_pct",
]
# Season-to-date expanding means — a slower signal than r8 that resets each year.
_PLAYER_STD_COLS = ["attempts", "completions", "carries", "targets", "receptions",
                    "passing_yards", "rushing_yards", "receiving_yards"]


def _f(cols: list[str], windows=ROLL_WINDOWS) -> list[str]:
    return [f"{c}_r{n}" for c in cols for n in windows]


BASE_CTX = [
    "is_home", "spread_team", "implied_team_total", "implied_opp_total", "total_line",
    "is_dome", "wind", "temp", "rest_days", "div_game", "week", "games_played_prior",
    "tm_plays_r3", "tm_plays_r8", "tm_passrate_r3", "tm_passrate_r8",
    "opp_pass_yds_allow_r3", "opp_pass_yds_allow_r8",
    "opp_rush_yds_allow_r3", "opp_rush_yds_allow_r8",
    "opp_plays_allow_r3", "opp_plays_allow_r8",
]
POS_FLAGS = ["is_qb", "is_rb", "is_wr", "is_te"]
SNAP_OFF = ["offense_pct_r3", "offense_pct_r8", "st_pct_r3"]
SNAP_DEF = ["defense_pct_r3", "defense_pct_r8", "st_pct_r3"]

_PASS_F = SNAP_OFF + _f(["attempts", "completions", "passing_yards", "passing_tds",
                         "interceptions", "sacks_suffered", "passing_air_yards"]) + \
    ["attempts_std", "completions_std", "passing_yards_std"]
_RUSH_F = SNAP_OFF + _f(["carries", "rushing_yards", "rushing_tds",
                         "targets", "receptions"]) + \
    ["carries_std", "rushing_yards_std"]
_RECV_F = SNAP_OFF + _f(["targets", "receptions", "receiving_yards", "receiving_tds",
                         "receiving_air_yards", "receiving_yac", "target_share",
                         "air_yards_share", "wopr"]) + \
    ["targets_std", "receptions_std", "receiving_yards_std"]
_DEF_F = SNAP_DEF + _f(["def_tackles_solo", "def_tackle_assists", "def_sacks",
                        "def_qb_hits"])


def _cols(*groups: list[str]) -> list[str]:
    """Concatenate feature groups, de-duplicating while preserving order."""
    out: list[str] = []
    for g in groups:
        out.extend(g)
    return list(dict.fromkeys(out))


NFL_PROP_FEATURE_MAP: dict[str, list[str]] = {
    "nfl_prop_pass_yards":       _cols(_PASS_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_pass_attempts":    _cols(_PASS_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_pass_completions": _cols(_PASS_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_pass_tds":         _cols(_PASS_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_rush_yards":       _cols(_RUSH_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_rush_attempts":    _cols(_RUSH_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_rec_yards":        _cols(_RECV_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_receptions":       _cols(_RECV_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_rush_rec_yards":   _cols(_RUSH_F, _RECV_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_anytime_td":       _cols(_RUSH_F, _RECV_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_tackles_assists":  _cols(_DEF_F, BASE_CTX, POS_FLAGS),
    "nfl_prop_sacks":            _cols(_DEF_F, BASE_CTX, POS_FLAGS),
}

# model_id → (target expression, pool gate). The pool approximates "a book would
# hang a line on this player this week", using PRIOR usage only. Getting this
# wrong in the permissive direction is a survivorship trap: conditioning on
# players who ended up playing is a look-ahead if inactives were not known at
# bet time, so the gate is deliberately built from r3 history, never from the
# target game.
_TARGET: dict[str, str] = {
    "nfl_prop_pass_yards": "passing_yards",
    "nfl_prop_pass_attempts": "attempts",
    "nfl_prop_pass_completions": "completions",
    "nfl_prop_pass_tds": "passing_tds",
    "nfl_prop_rush_yards": "rushing_yards",
    "nfl_prop_rush_attempts": "carries",
    "nfl_prop_rec_yards": "receiving_yards",
    "nfl_prop_receptions": "receptions",
    "nfl_prop_rush_rec_yards": "rush_rec_yards",
    "nfl_prop_anytime_td": "any_td",
    "nfl_prop_tackles_assists": "tackles_assists",
    "nfl_prop_sacks": "def_sacks",
}
_POOL: dict[str, tuple[str, float]] = {
    "nfl_prop_pass_yards": ("attempts_r3", 20.0),
    "nfl_prop_pass_attempts": ("attempts_r3", 20.0),
    "nfl_prop_pass_completions": ("attempts_r3", 20.0),
    "nfl_prop_pass_tds": ("attempts_r3", 20.0),
    "nfl_prop_rush_yards": ("carries_r3", 8.0),
    "nfl_prop_rush_attempts": ("carries_r3", 8.0),
    "nfl_prop_rec_yards": ("targets_r3", 4.0),
    "nfl_prop_receptions": ("targets_r3", 4.0),
    "nfl_prop_tackles_assists": ("def_tackles_solo_r3", 3.0),
    "nfl_prop_sacks": ("def_sacks_r3", 0.2),
}


def _pool_mask(model_id: str, df: pd.DataFrame) -> pd.Series:
    """Boolean gate for the players a book would plausibly price this week."""
    if model_id in ("nfl_prop_rush_rec_yards", "nfl_prop_anytime_td"):
        # flex pool: anyone with a real running or receiving role
        return (df["carries_r3"].fillna(0) >= 5) | (df["targets_r3"].fillna(0) >= 3)
    col, thresh = _POOL[model_id]
    return df[col].fillna(0) >= thresh


# ── Loading ───────────────────────────────────────────────────────────────────

_PLAYER_SQL = """
    SELECT player_id, player_name, norm_name, pos, team, opponent, game_id,
           game_date, season, week, season_type,
           completions, attempts, passing_yards, passing_tds, interceptions,
           sacks_suffered, passing_air_yards,
           carries, rushing_yards, rushing_tds,
           receptions, targets, receiving_yards, receiving_tds,
           receiving_air_yards, receiving_yac,
           target_share, air_yards_share, wopr,
           def_tackles_solo, def_tackle_assists, def_sacks, def_qb_hits
    FROM nfl_player_game_log
    WHERE season = ANY(%s) AND season_type = 'REG'
"""
_TEAM_SQL = """
    SELECT game_id, team, opponent, game_date, season, week, is_home,
           pass_attempts, carries, plays, pass_yards, rush_yards,
           spread_line, total_line, roof, temp, wind, div_game
    FROM nfl_team_game_stats
    WHERE season = ANY(%s)
"""
_SNAP_SQL = """
    SELECT game_id, team, norm_name, offense_pct, defense_pct, st_pct
    FROM nfl_snap_counts
    WHERE season = ANY(%s)
"""


# The DB wrapper hands back plain tuples, so every query names its columns here
# rather than relying on cursor.description.
_PLAYER_COLS = ["player_id", "player_name", "norm_name", "pos", "team", "opponent",
                "game_id", "game_date", "season", "week", "season_type",
                "completions", "attempts", "passing_yards", "passing_tds",
                "interceptions", "sacks_suffered", "passing_air_yards",
                "carries", "rushing_yards", "rushing_tds",
                "receptions", "targets", "receiving_yards", "receiving_tds",
                "receiving_air_yards", "receiving_yac",
                "target_share", "air_yards_share", "wopr",
                "def_tackles_solo", "def_tackle_assists", "def_sacks", "def_qb_hits"]
_TEAM_COLS = ["game_id", "team", "opponent", "game_date", "season", "week", "is_home",
              "pass_attempts", "carries", "plays", "pass_yards", "rush_yards",
              "spread_line", "total_line", "roof", "temp", "wind", "div_game"]
_SNAP_COLS = ["game_id", "team", "norm_name", "offense_pct", "defense_pct", "st_pct"]


def _read(conn: DBConnection, sql: str, cols: list[str],
          seasons: list[int]) -> pd.DataFrame:
    rows = conn.execute(sql, (list(seasons),)).fetchall()
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)


def _roll(df: pd.DataFrame, key: str, cols: list[str], n: int) -> pd.DataFrame:
    """Shifted rolling mean of `cols` within `key` groups. `df` must be sorted."""
    sh = df.groupby(key, sort=False)[cols].shift(1)
    out = sh.groupby(df[key], sort=False).rolling(n, min_periods=1).mean()
    out.index = out.index.droplevel(0)
    return out.reindex(df.index).add_suffix(f"_r{n}")


def _team_features(team: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rolling team-offence and opponent-defence-allowed frames."""
    t = team.copy()
    for c in ("plays", "pass_attempts", "pass_yards", "rush_yards"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["team_pass_rate"] = t["pass_attempts"] / t["plays"].replace(0, np.nan)
    t = t.sort_values(["team", "game_date"]).reset_index(drop=True)
    for n in ROLL_WINDOWS:
        r = _roll(t, "team", ["plays", "team_pass_rate"], n)
        t[f"tm_plays_r{n}"] = r[f"plays_r{n}"]
        t[f"tm_passrate_r{n}"] = r[f"team_pass_rate_r{n}"]

    # what a DEFENCE gave up: same rows, keyed by the defending team
    d = t.rename(columns={"team": "off_team", "opponent": "def_team"})
    d = d.sort_values(["def_team", "game_date"]).reset_index(drop=True)
    for n in ROLL_WINDOWS:
        r = _roll(d, "def_team", ["pass_yards", "rush_yards", "plays"], n)
        d[f"opp_pass_yds_allow_r{n}"] = r[f"pass_yards_r{n}"]
        d[f"opp_rush_yds_allow_r{n}"] = r[f"rush_yards_r{n}"]
        d[f"opp_plays_allow_r{n}"] = r[f"plays_r{n}"]

    off = t[["game_id", "team", "game_date", "week", "is_home", "spread_line",
             "total_line", "roof", "temp", "wind", "div_game"]
            + [c for c in t.columns if c.startswith("tm_")]]
    def_ = d[["game_id", "def_team"] + [c for c in d.columns if c.startswith("opp_")]]
    return off, def_.rename(columns={"def_team": "opponent"})


def _add_features(player: pd.DataFrame, team: pd.DataFrame,
                  snaps: pd.DataFrame) -> pd.DataFrame:
    """The single feature implementation, shared by training and scoring."""
    df = player.copy()
    numeric = [c for c in _PLAYER_ROLL_COLS if c in df.columns and c not in
               ("offense_pct", "defense_pct", "st_pct")]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["game_date"] = pd.to_datetime(df["game_date"])

    if not snaps.empty:
        df = df.merge(snaps, on=["game_id", "team", "norm_name"], how="left")
    for c in ("offense_pct", "defense_pct", "st_pct"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce")

    off, dfn = _team_features(team)
    off["game_date"] = pd.to_datetime(off["game_date"])
    df = df.drop(columns=[c for c in ("week", "is_home") if c in df.columns])
    df = df.merge(off.drop(columns=["game_date"]), on=["game_id", "team"], how="left")
    df = df.merge(dfn, on=["game_id", "opponent"], how="left")

    df = df.sort_values(["player_id", "game_date"]).reset_index(drop=True)
    roll_cols = [c for c in _PLAYER_ROLL_COLS if c in df.columns]
    for n in ROLL_WINDOWS:
        df = pd.concat([df, _roll(df, "player_id", roll_cols, n)], axis=1)
    df["games_played_prior"] = df.groupby("player_id", sort=False).cumcount()

    std_cols = [c for c in _PLAYER_STD_COLS if c in df.columns]
    sh = df.groupby(["player_id", "season"], sort=False)[std_cols].shift(1)
    exp = sh.groupby([df["player_id"], df["season"]], sort=False).expanding().mean()
    exp.index = exp.index.droplevel([0, 1])
    exp = exp.reindex(df.index).add_suffix("_std")
    df = pd.concat([df, exp], axis=1)
    # Season-to-date resets every September, so in week 1 it is null for EVERY
    # player. Left alone the scorer's nan→0 would tell the model a starting QB
    # averages zero attempts — the "null filled with 0.0 sends the model
    # out-of-distribution" bug this repo has already shipped once. Fall back to
    # the cross-season r8, which is the same quantity over a longer window.
    for c in std_cols:
        df[f"{c}_std"] = df[f"{c}_std"].fillna(df[f"{c}_r8"])

    # game context. spread_line is home-relative as nflverse publishes it, so it
    # is flipped to the player's team; implied team total is the game-script
    # driver and one of the strongest features for every volume market.
    df["spread_line"] = pd.to_numeric(df["spread_line"], errors="coerce")
    df["total_line"] = pd.to_numeric(df["total_line"], errors="coerce")
    df["is_home"] = pd.to_numeric(df["is_home"], errors="coerce").fillna(0).astype(int)
    df["spread_team"] = np.where(df["is_home"] == 1, df["spread_line"], -df["spread_line"])
    df["implied_team_total"] = df["total_line"] / 2 + df["spread_team"] / 2
    df["implied_opp_total"] = df["total_line"] / 2 - df["spread_team"] / 2
    df["is_dome"] = df["roof"].isin(["dome", "closed"]).astype(int)
    df["wind"] = pd.to_numeric(df["wind"], errors="coerce").fillna(0.0)
    df["temp"] = pd.to_numeric(df["temp"], errors="coerce")
    df["temp"] = df["temp"].fillna(df["temp"].median() if df["temp"].notna().any() else 60.0)
    df["div_game"] = pd.to_numeric(df["div_game"], errors="coerce").fillna(0)
    df["week"] = pd.to_numeric(df["week"], errors="coerce").fillna(0)
    df["rest_days"] = (df.groupby("player_id")["game_date"].diff()
                       .dt.days.fillna(7).clip(3, 21))
    for pos, flag in (("QB", "is_qb"), ("RB", "is_rb"), ("WR", "is_wr"), ("TE", "is_te")):
        df[flag] = (df["pos"] == pos).astype(int)

    # derived targets
    df["rush_rec_yards"] = df["rushing_yards"] + df["receiving_yards"]
    df["any_td"] = ((df["rushing_tds"] + df["receiving_tds"]) >= 1).astype(int)
    df["tackles_assists"] = df["def_tackles_solo"] + df["def_tackle_assists"]
    return df


def _load(conn: DBConnection, seasons: list[int]) -> pd.DataFrame:
    player = _read(conn, _PLAYER_SQL, _PLAYER_COLS, seasons)
    if player.empty:
        return pd.DataFrame()
    team = _read(conn, _TEAM_SQL, _TEAM_COLS, seasons)
    snaps = _read(conn, _SNAP_SQL, _SNAP_COLS, seasons)
    if team.empty:
        raise ValueError(
            "nfl_team_game_stats is empty for these seasons — run "
            "`python -m data.ingestors.nfl_props_data_ingestor --backfill` first. "
            "Without it every game-context feature would be null and the null "
            "drop would zero the training matrix.")
    return _add_features(player, team, snaps)


# ── Public API ────────────────────────────────────────────────────────────────

def build_nfl_prop_training_dataset(model_id: str, seasons: list[int]) -> pd.DataFrame:
    """Feature matrix + `target` for one NFL prop model over `seasons`."""
    if model_id not in NFL_PROP_FEATURE_MAP:
        raise ValueError(f"Unknown NFL prop model_id '{model_id}'")
    conn = get_connection()
    try:
        df = _load(conn, list(seasons))
    finally:
        conn.close()
    if df.empty:
        logger.warning(f"{model_id}: no NFL player rows for seasons {seasons}")
        return pd.DataFrame()

    df = df[_pool_mask(model_id, df)].copy()
    df["target"] = pd.to_numeric(df[_TARGET[model_id]], errors="coerce")
    feature_cols = NFL_PROP_FEATURE_MAP[model_id]
    keep = ["player_id", "player_name", "team", "opponent", "game_id", "game_date",
            "season", "week", "target"] + feature_cols
    df = df[[c for c in keep if c in df.columns]]

    before = len(df)
    df = df.dropna(subset=["target"] + [c for c in feature_cols if c in BASE_CTX])
    if before and (before - len(df)) / before > 0.25:
        logger.warning(f"{model_id}: dropped {before - len(df)}/{before} rows on null "
                       "context features — check the team-game backfill")
    logger.info(f"{model_id}: {len(df)} training rows over seasons {seasons}")
    return df.reset_index(drop=True)


def build_nfl_prop_scoring_rows(game_date: str, model_id: str) -> pd.DataFrame:
    """
    Feature rows for players in games ON `game_date`.

    Candidates are the players who have appeared for that team in the trailing
    weeks and clear the market's pool gate on PRIOR usage — never on anything
    from the target game. The synthesised upcoming row is appended to the real
    history and run through the SAME `_add_features`, so scoring features are
    computed by identical code to training features.
    """
    if model_id not in NFL_PROP_FEATURE_MAP:
        raise ValueError(f"Unknown NFL prop model_id '{model_id}'")

    season = _nfl_season(game_date)
    seasons = [season - 1, season]     # prior season carries early-week rollings
    conn = get_connection()
    try:
        player = _read(conn, _PLAYER_SQL, _PLAYER_COLS, seasons)
        team = _read(conn, _TEAM_SQL, _TEAM_COLS, seasons)
        snaps = _read(conn, _SNAP_SQL, _SNAP_COLS, seasons)
    finally:
        conn.close()
    return _score_rows(player, team, snaps, game_date, model_id)


def _score_rows(player: pd.DataFrame, team: pd.DataFrame, snaps: pd.DataFrame,
                game_date: str, model_id: str) -> pd.DataFrame:
    if player.empty or team.empty:
        return pd.DataFrame()
    team["game_date"] = pd.to_datetime(team["game_date"]).dt.strftime("%Y-%m-%d")
    player["game_date"] = pd.to_datetime(player["game_date"]).dt.strftime("%Y-%m-%d")

    slate = team[team["game_date"] == game_date]
    if slate.empty:
        return pd.DataFrame()

    # candidates: players with a real appearance for that team in the trailing
    # 6 weeks. Wider than the pool gate on purpose — the gate is applied after
    # the rolling features exist, so it uses the same numbers training did.
    hist = player[player["game_date"] < game_date]
    if hist.empty:
        return pd.DataFrame()
    cutoff = (pd.to_datetime(game_date) - pd.Timedelta(days=45)).strftime("%Y-%m-%d")
    recent = hist[hist["game_date"] >= cutoff]
    if recent.empty:
        # Week 1: the 45-day window cannot bridge the off-season, so fall back
        # to each player's LAST appearance in the prior season. Off-season
        # roster moves mean some of these carry the wrong team — which costs a
        # missed pick, never a wrong one: the scorer looks a prop price up by
        # (game_id, player), so a moved player simply has no line in his old
        # team's game and is skipped. Nflverse rosters would remove the guess
        # entirely; that is the documented follow-up.
        recent = hist[hist["season"] >= _nfl_season(game_date) - 1]

    synth = []
    for _, g in slate.iterrows():
        for _, p in recent[recent["team"] == g["team"]].sort_values(
                "game_date").drop_duplicates("player_id", keep="last").iterrows():
            row = {c: 0.0 for c in player.columns}
            row.update({
                "player_id": p["player_id"], "player_name": p["player_name"],
                "norm_name": p["norm_name"], "pos": p["pos"], "team": g["team"],
                "opponent": g["opponent"], "game_id": g["game_id"],
                "game_date": game_date, "season": g["season"], "week": g["week"],
                "season_type": "REG",
            })
            synth.append(row)
    if not synth:
        return pd.DataFrame()

    combined = pd.concat([hist, pd.DataFrame(synth)], ignore_index=True)
    df = _add_features(combined, team, snaps)
    df = df[df["game_date"] == pd.Timestamp(game_date)]
    df = df[_pool_mask(model_id, df)].copy()

    feature_cols = NFL_PROP_FEATURE_MAP[model_id]
    worst = df[feature_cols].isna().mean()
    if len(df) and worst.max() > 0.5:
        # A feature that is null for most of the slate means the scorer will
        # feed the model zeros for it. Loud, because it is silent otherwise.
        logger.warning(f"{model_id} {game_date}: mostly-null features "
                       f"{worst[worst > 0.5].round(3).to_dict()}")
    keep = ["player_id", "player_name", "team", "opponent", "game_id",
            "game_date", "season", "week"] + feature_cols
    return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


def _nfl_season(game_date: str) -> int:
    """nflverse season label for a date — Jan/Feb belong to the prior season."""
    year, month = int(game_date[:4]), int(game_date[5:7])
    return year if month >= 3 else year - 1

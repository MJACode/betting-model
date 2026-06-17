"""
feature_engine.py — Master feature builder for all sports and markets.

Orchestrates MLB and NHL feature extractors, applies injury adjustments,
and assembles the final feature matrix used by model training and scoring.

Usage:
    from features.feature_engine import build_features_for_game
    from features.feature_engine import build_training_dataset
"""

import bisect
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MIN_GAMES_BASELINE, SPORTS
from data.db import get_connection, DBConnection
# Golf feature lists live in the golf engine (single source of truth — the engine
# derives matchup diffs from them). Safe top-level import: golf_feature_engine
# imports feature_engine only lazily inside functions, so there is no cycle.
from features.golf_feature_engine import GOLF_PLAYER_FEATURES, GOLF_MATCHUP_FEATURES


# ── Feature Column Groups ─────────────────────────────────────────────────────
# These define what goes into each model's feature matrix.
# Expanding or removing columns here flows through to training automatically.

MLB_H2H_FEATURES = [
    # Offense differentials (home − away)
    "d_runs_last_5", "d_runs_last_10",
    "d_ops", "d_wrc_plus", "d_woba", "d_iso",
    "d_k_pct", "d_bb_pct",
    # Starter differentials (MLB Stats API + Savant — per-game rows via backfill)
    "d_starter_era", "d_starter_k9", "d_starter_bb9",
    "d_starter_era_last3", "d_starter_k9_last3",
    # Team pitching differentials
    "d_team_era", "d_bullpen_era", "d_team_whip", "d_team_fip",
    # Context
    "home_win_pct", "away_win_pct", "d_run_differential",
    # Bullpen workload (IP by relievers in last 1/3 days — fatigue signal)
    "d_bullpen_ip_last3",
    "home_bullpen_ip_last1", "away_bullpen_ip_last1",
    # Injury adjustments
    "home_injury_adj", "away_injury_adj",
    "home_starter_out", "away_starter_out",
    "home_has_returnee", "away_has_returnee",
    # Early season flag
    "is_early_season",
]

MLB_TOTALS_FEATURES = [
    # Absolute values (not differentials) for totals
    "home_runs_last_5", "away_runs_last_5",
    "home_runs_last_10", "away_runs_last_10",
    "home_team_era", "away_team_era",
    "home_bullpen_era", "away_bullpen_era",
    # Starter stats (per-game rows via backfill)
    "home_starter_era", "away_starter_era",
    "home_starter_k9", "away_starter_k9",
    "home_k_pct", "away_k_pct",
    "total_line",    # market-implied line (informative)
    # Bullpen workload (both teams — more combined IP = higher scoring variance)
    "home_bullpen_ip_last3", "away_bullpen_ip_last3",
    "home_injury_adj", "away_injury_adj",
    # Weather (primary signal for totals — wind blowing out raises run totals)
    "wind_out_component", "temp_f", "is_dome_game",
    "is_early_season",
]

# Spreads uses same features as H2H plus market line and wind/dome
# (wind has moderate effect on run-scoring margin; temp omitted for runline)
MLB_SPREADS_FEATURES = MLB_H2H_FEATURES + ["spread_home", "wind_out_component", "is_dome_game"]

# ── F5 (First 5 Innings) Feature Groups ──────────────────────────────────────
# F5 models are starter-dominant: no bullpen features, heavier starter weight.
# The first 5 innings are almost entirely about the starting pitcher matchup.

MLB_F5_H2H_FEATURES = [
    # Offense differentials (home - away)
    "d_runs_last_5", "d_runs_last_10",
    "d_ops", "d_wrc_plus", "d_woba", "d_iso",
    "d_k_pct", "d_bb_pct",
    # Starter differentials (primary signal for F5)
    "d_starter_era", "d_starter_k9", "d_starter_bb9",
    "d_starter_era_last3", "d_starter_k9_last3",
    # Team pitching (no bullpen for F5)
    "d_team_era", "d_team_whip",
    # Context
    "home_win_pct", "away_win_pct", "d_run_differential",
    # Injury adjustments
    "home_injury_adj", "away_injury_adj",
    "home_starter_out", "away_starter_out",
    "home_has_returnee", "away_has_returnee",
    # Early season flag
    "is_early_season",
]

MLB_F5_TOTALS_FEATURES = [
    # Absolute values for totals
    "home_runs_last_5", "away_runs_last_5",
    "home_runs_last_10", "away_runs_last_10",
    "home_team_era", "away_team_era",
    # Starter stats (primary for F5 totals)
    "home_starter_era", "away_starter_era",
    "home_starter_k9", "away_starter_k9",
    "home_k_pct", "away_k_pct",
    "total_line",    # market-implied F5 total
    "home_injury_adj", "away_injury_adj",
    # Weather (still relevant for F5 scoring)
    "wind_out_component", "temp_f", "is_dome_game",
    "is_early_season",
]

MLB_F5_SPREADS_FEATURES = MLB_F5_H2H_FEATURES + ["spread_home", "wind_out_component", "is_dome_game"]


NHL_H2H_FEATURES = [
    "d_goals_per_game", "d_goals_last_5", "d_goals_last_10",
    "d_corsi_for_pct", "d_xgf_pct", "d_power_play_pct",
    "d_goals_against_pg", "d_penalty_kill_pct",
    "d_goalie_save_pct", "d_goalie_gaa", "d_goalie_gsaa",
    "d_goalie_save_pct_last5", "d_goalie_gaa_last5",
    "home_goals_home_avg", "away_goals_away_avg",
    "home_win_pct", "away_win_pct", "d_goal_differential",
    "home_injury_adj", "away_injury_adj",
    "home_goalie_out", "away_goalie_out",
    "home_has_returnee", "away_has_returnee",
    "is_early_season",
]

NHL_TOTALS_FEATURES = [
    "home_goals_per_game", "away_goals_per_game",
    "home_goals_last_5", "away_goals_last_5",
    "home_goalie_save_pct", "away_goalie_save_pct",
    "home_goalie_gaa", "away_goalie_gaa",
    "home_power_play_pct", "away_power_play_pct",
    "home_penalty_kill_pct", "away_penalty_kill_pct",
    "total_line",
    "home_injury_adj", "away_injury_adj",
    "is_early_season",
]

NHL_REG_FEATURES = NHL_H2H_FEATURES  # regulation moneyline uses same inputs

NHL_PUCKLINE_FEATURES = NHL_H2H_FEATURES + ["spread_home"]

# ── WNBA Feature Groups ───────────────────────────────────────────────────────
# Basketball: pace + efficiency drive scoring; rest/back-to-back is a real signal.
# Stats come from wnba_team_stats (ASOF) + rolling points from the games table.

WNBA_H2H_FEATURES = [
    # Efficiency + pace differentials (home − away)
    "d_off_rating", "d_def_rating", "d_net_rating", "d_pace",
    "d_efg_pct", "d_fg3_pct", "d_ft_pct",
    "d_reb_per_game", "d_ast_per_game", "d_tov_pct",
    "d_points_per_game", "d_points_allowed_pg",
    # Rolling form (from games table)
    "d_points_last_3", "d_points_last_5",
    # Context
    "home_win_pct", "away_win_pct", "d_point_differential",
    # Rest / schedule (basketball-specific)
    "d_rest_days", "home_b2b", "away_b2b",
    # Injuries
    "home_injury_adj", "away_injury_adj",
    "home_has_returnee", "away_has_returnee",
    # Early season flag
    "is_early_season",
]

WNBA_TOTALS_FEATURES = [
    # Absolute values for totals
    "home_points_per_game", "away_points_per_game",
    "home_points_allowed_pg", "away_points_allowed_pg",
    "home_pace", "away_pace",
    "home_off_rating", "away_off_rating",
    "home_def_rating", "away_def_rating",
    "home_efg_pct", "away_efg_pct",
    "home_points_last_5", "away_points_last_5",
    "total_line",
    "home_b2b", "away_b2b",
    "home_injury_adj", "away_injury_adj",
    "is_early_season",
]

WNBA_SPREAD_FEATURES = WNBA_H2H_FEATURES + ["spread_home"]

# ── NBA Feature Groups ────────────────────────────────────────────────────────
# Identical basketball metric set to WNBA (same nba_team_stats columns + rolling
# points from the games table). Aliased to the WNBA lists so the two never drift.
NBA_H2H_FEATURES    = WNBA_H2H_FEATURES
NBA_TOTALS_FEATURES = WNBA_TOTALS_FEATURES
NBA_SPREAD_FEATURES = WNBA_SPREAD_FEATURES

# ── UFC Feature Groups ────────────────────────────────────────────────────────
# Career/rolling stats ASOF the fight date from ufc_fight_log + static fighter
# attributes (age/height/reach/stance). Built by features/ufc_feature_engine.py.
# No early-season concept; the gate is MIN_UFC_FIGHTS prior fights per fighter.

UFC_H2H_FEATURES = [
    # Record / form differentials (home − away)
    "d_career_win_pct", "d_win_streak", "d_experience",
    "d_finish_rate", "d_ko_rate", "d_sub_rate",
    # Striking differentials
    "d_slpm", "d_sapm", "d_str_acc", "d_str_def",
    # Grappling differentials
    "d_td_avg", "d_td_acc", "d_td_def", "d_sub_att_rate",
    # Physical / schedule
    "d_age", "d_height_in", "d_reach_in", "d_layoff_days",
    "stance_mismatch",
    # Bout context (inferred from the DK round-total line at score time)
    "is_five_rounds",
]

UFC_TOTALS_FEATURES = [
    # How each fighter's fights tend to end
    "home_finish_rate", "away_finish_rate",
    "home_ko_rate", "away_ko_rate",
    "home_sub_rate", "away_sub_rate",
    "home_dec_rate", "away_dec_rate",
    "home_avg_fight_rounds", "away_avg_fight_rounds",
    # Volume / danger
    "home_slpm", "away_slpm", "home_sapm", "away_sapm",
    "home_td_avg", "away_td_avg",
    # Bout context
    "is_five_rounds", "total_line",
]

UFC_METHOD_FEATURES = [
    "home_finish_rate", "away_finish_rate",
    "home_ko_rate", "away_ko_rate",
    "home_sub_rate", "away_sub_rate",
    "home_dec_rate", "away_dec_rate",
    "home_avg_fight_rounds", "away_avg_fight_rounds",
    "home_slpm", "away_slpm", "home_sapm", "away_sapm",
    "home_td_avg", "away_td_avg",
    "home_sub_att_rate", "away_sub_att_rate",
    "is_five_rounds",
]

FEATURE_MAP = {
    "mlb_moneyline":            MLB_H2H_FEATURES,
    "mlb_over_under":           MLB_TOTALS_FEATURES,
    "mlb_runline":              MLB_SPREADS_FEATURES,
    "mlb_f5_moneyline":         MLB_F5_H2H_FEATURES,
    "mlb_f5_over_under":        MLB_F5_TOTALS_FEATURES,
    "mlb_f5_runline":           MLB_F5_SPREADS_FEATURES,
    "nhl_moneyline":            NHL_H2H_FEATURES,
    "nhl_moneyline_regulation": NHL_REG_FEATURES,
    "nhl_over_under":           NHL_TOTALS_FEATURES,
    "nhl_puckline":             NHL_PUCKLINE_FEATURES,
    "wnba_moneyline":           WNBA_H2H_FEATURES,
    "wnba_over_under":          WNBA_TOTALS_FEATURES,
    "wnba_spread":              WNBA_SPREAD_FEATURES,
    "nba_moneyline":            NBA_H2H_FEATURES,
    "nba_over_under":           NBA_TOTALS_FEATURES,
    "nba_spread":               NBA_SPREAD_FEATURES,
    "ufc_moneyline":            UFC_H2H_FEATURES,
    "ufc_total_rounds":         UFC_TOTALS_FEATURES,
    "ufc_method_of_victory":    UFC_METHOD_FEATURES,
    # GOLF — per-player rolling strokes-gained + form + course history. The four
    # per-player markets share one feature list; matchups use pairwise diffs.
    # Lists live in features/golf_feature_engine.py to avoid a heavy import here.
    "golf_outright":            GOLF_PLAYER_FEATURES,
    "golf_top10":               GOLF_PLAYER_FEATURES,
    "golf_top20":               GOLF_PLAYER_FEATURES,
    "golf_make_cut":            GOLF_PLAYER_FEATURES,
    "golf_matchup":             GOLF_MATCHUP_FEATURES,
}


# ── Rolling Stat Helpers ──────────────────────────────────────────────────────

def _rolling_runs_from_games(conn: DBConnection,
                              team: str, as_of_date: str,
                              window: int) -> float | None:
    """
    Average runs scored per game in the last N games before as_of_date.
    Computed directly from the games table so it is accurate for each game date,
    not the stale end-of-season snapshot stored in mlb_team_stats.
    """
    rows = conn.execute("""
        SELECT CASE WHEN home_team = ? THEN home_score ELSE away_score END
        FROM games
        WHERE sport = 'MLB'
          AND (home_team = ? OR away_team = ?)
          AND game_date < ?
          AND home_score IS NOT NULL
        ORDER BY game_date DESC
        LIMIT ?
    """, (team, team, team, as_of_date, window)).fetchall()

    scores = [r[0] for r in rows if r[0] is not None]
    return round(float(np.mean(scores)), 3) if len(scores) >= 3 else None


def _season_runs_by_location(conn: DBConnection,
                              team: str, as_of_date: str,
                              location: str) -> float | None:
    """Average runs scored at home or away this season, up to as_of_date."""
    year = as_of_date[:4]
    if location == "home":
        score_col, team_cond = "home_score", "home_team = ?"
    else:
        score_col, team_cond = "away_score", "away_team = ?"

    rows = conn.execute(f"""
        SELECT {score_col}
        FROM games
        WHERE sport = 'MLB'
          AND {team_cond}
          AND game_date >= '{year}-01-01'
          AND game_date < ?
          AND home_score IS NOT NULL
    """, (team, as_of_date)).fetchall()

    scores = [r[0] for r in rows if r[0] is not None]
    return round(float(np.mean(scores)), 3) if scores else None


# ── Injury Feature Helpers ────────────────────────────────────────────────────

def _compute_injury_adjustment(injuries: list[dict]) -> float:
    """
    Aggregate injury severity into a single team penalty score.
    Higher score = more impacted team.
    Range: 0.0 (healthy) to ~3.0+ (multiple key players out)

    Formula: sum(severity_weight × return_ramp_penalty)
      where return_ramp_penalty = 1.0 - return_ramp_factor for scenario B
      and   return_ramp_penalty = severity_weight            for scenario A
    """
    total = 0.0
    for inj in injuries:
        scenario = inj.get("scenario", "A")
        weight   = inj.get("severity_weight", 0.7)
        if scenario == "B":
            ramp   = inj.get("return_ramp_factor", 1.0) or 1.0
            # If fully back (ramp=1.0) → 0 penalty; if at 0.70 → 0.30 penalty
            total += (1.0 - ramp)
        elif scenario == "A":
            total += weight
        # Scenario C (opponent edge) is handled separately at game level

    return round(total, 3)


def _has_starter_out(injuries: list[dict], sport: str) -> int:
    """1 if a confirmed starter (pitcher/goalie) is in the IL."""
    out_statuses = {"IL60", "IL15", "IL10", "Out"}
    for inj in injuries:
        if inj.get("status") in out_statuses and inj.get("scenario") == "A":
            # We don't have position data in injury table yet;
            # use severity as proxy (IL = likely starter)
            if inj.get("severity_weight", 0) >= 0.8:
                return 1
    return 0


def _has_returnee(injuries: list[dict]) -> int:
    """1 if any player is currently on the return ramp (scenario B)."""
    return int(any(inj.get("scenario") == "B" for inj in injuries))


# ── MLB Feature Builder ───────────────────────────────────────────────────────

def _get_mlb_team_stats(conn: DBConnection,
                         team: str, season: int, as_of_date: str) -> dict:
    """Pull most recent mlb_team_stats for team before as_of_date."""
    row = conn.execute("""
        SELECT games_played, ops, wrc_plus, woba, k_pct, bb_pct, iso, babip,
               runs_per_game, runs_last_5, runs_last_10, runs_last_15,
               runs_per_game_home, runs_per_game_away,
               team_era, bullpen_era, team_whip, team_fip,
               wins, losses, run_differential
        FROM mlb_team_stats
        WHERE team = ?
          AND season = ?
          AND as_of_date <= ?
        ORDER BY as_of_date DESC
        LIMIT 1
    """, (team, season, as_of_date)).fetchone()

    cols = [
        "games_played", "ops", "wrc_plus", "woba", "k_pct", "bb_pct",
        "iso", "babip", "runs_per_game", "runs_last_5", "runs_last_10",
        "runs_last_15", "runs_per_game_home", "runs_per_game_away",
        "team_era", "bullpen_era", "team_whip", "team_fip",
        "wins", "losses", "run_differential"
    ]
    if row:
        return dict(zip(cols, row))

    # Fallback: try prior season
    row_prev = conn.execute("""
        SELECT games_played, ops, wrc_plus, woba, k_pct, bb_pct, iso, babip,
               runs_per_game, runs_last_5, runs_last_10, runs_last_15,
               runs_per_game_home, runs_per_game_away,
               team_era, bullpen_era, team_whip, team_fip,
               wins, losses, run_differential
        FROM mlb_team_stats
        WHERE team = ? AND season = ?
        ORDER BY as_of_date DESC
        LIMIT 1
    """, (team, season - 1)).fetchone()

    if row_prev:
        logger.debug(f"MLB {team}: using prior-season ({season-1}) stats as baseline")
        return dict(zip(cols, row_prev))

    return {}


def _get_mlb_pitcher_stats(conn: DBConnection,
                            team: str, game_date: str, season: int) -> dict:
    """Pull pitcher stats for today's probable starter."""
    row = conn.execute("""
        SELECT era, xfip, whip, k9, bb9, swstr_pct, csw_pct,
               era_last3, k9_last3, xfip_last3
        FROM mlb_pitcher_stats
        WHERE team = ?
          AND game_date = ?
          AND season = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (team, game_date, season)).fetchone()

    cols = ["era", "xfip", "whip", "k9", "bb9", "swstr_pct", "csw_pct",
            "era_last3", "k9_last3", "xfip_last3"]

    if row:
        return dict(zip(cols, row))
    return {}


def _get_bullpen_workload(conn: DBConnection,
                          team: str, game_date: str,
                          days: int = 3) -> float:
    """
    Sum of innings pitched by relievers for `team` in the `days` calendar days
    immediately before `game_date` (exclusive).

    Returns 0.0 when no appearances exist — this is the correct value: a team
    with no games (off days) or no relievers used has zero bullpen fatigue.
    Unlike pitcher ERA (where 0 is impossible), bullpen IP of 0 is legitimate.
    """
    cutoff = (datetime.strptime(game_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    row = conn.execute("""
        SELECT SUM(ip)
        FROM mlb_bullpen_stats
        WHERE team = ?
          AND game_date < ?
          AND game_date >= ?
    """, (team, game_date, cutoff)).fetchone()

    val = row[0] if row else None
    return round(float(val), 2) if val is not None else 0.0


def _get_game_weather(conn: DBConnection, game_id: str) -> dict:
    """
    Pull weather context for a game from game_weather table.
    Returns empty dict if no row exists (dome games, missing data, or backfill not run).
    Callers should treat missing weather as None (not 0) except is_dome_game.
    """
    row = conn.execute("""
        SELECT temp_f, wind_mph, wind_out_component, precip_mm, is_dome_game
        FROM game_weather
        WHERE game_id = ?
        LIMIT 1
    """, (game_id,)).fetchone()

    cols = ["temp_f", "wind_mph", "wind_out_component", "precip_mm", "is_dome_game"]
    if row:
        return dict(zip(cols, row))
    return {}


def build_mlb_game_features(conn: DBConnection,
                              game_id: str,
                              game_date: str,
                              home_team: str,
                              away_team: str,
                              season: int,
                              odds_row: dict = None) -> dict:
    """
    Build the full feature row for one MLB game.
    Returns a flat dict with all feature columns.
    """
    from data.ingestors.injury_ingestor import query_injuries_for_game

    home_stats   = _get_mlb_team_stats(conn, home_team, season, game_date)
    away_stats   = _get_mlb_team_stats(conn, away_team, season, game_date)
    home_pitcher = _get_mlb_pitcher_stats(conn, home_team, game_date, season)
    away_pitcher = _get_mlb_pitcher_stats(conn, away_team, game_date, season)
    weather      = _get_game_weather(conn, game_id)

    # Bullpen workload — IP by relievers in last 1/3 days before this game
    home_bp_ip1 = _get_bullpen_workload(conn, home_team, game_date, days=1)
    home_bp_ip3 = _get_bullpen_workload(conn, home_team, game_date, days=3)
    away_bp_ip1 = _get_bullpen_workload(conn, away_team, game_date, days=1)
    away_bp_ip3 = _get_bullpen_workload(conn, away_team, game_date, days=3)

    injuries = query_injuries_for_game(conn, "MLB", home_team, away_team, game_date)
    home_inj = injuries["home_injuries"]
    away_inj = injuries["away_injuries"]

    def _gp(team_stats: dict) -> int:
        return team_stats.get("games_played") or 0

    is_early = int(_gp(home_stats) < MIN_GAMES_BASELINE or
                   _gp(away_stats) < MIN_GAMES_BASELINE)

    def diff(key: str):
        h = home_stats.get(key)
        a = away_stats.get(key)
        if h is None or a is None:
            return None
        return round(h - a, 4)

    def pitcher_diff(key: str):
        h = home_pitcher.get(key)
        a = away_pitcher.get(key)
        if h is None or a is None:
            return None
        # For ERA/FIP: lower = better, so away's advantage if away_era < home_era
        # We store as home − away so positive = home pitcher advantage
        return round(a - h, 4) if key in ("era", "xfip", "bb9", "era_last3", "xfip_last3") else round(h - a, 4)

    home_wins   = home_stats.get("wins") or 0
    home_losses = home_stats.get("losses") or 0
    away_wins   = away_stats.get("wins") or 0
    away_losses = away_stats.get("losses") or 0

    home_win_pct = home_wins / max(home_wins + home_losses, 1)
    away_win_pct = away_wins / max(away_wins + away_losses, 1)

    features = {
        "game_id":   game_id,
        "game_date": game_date,
        "sport":     "MLB",
        "season":    season,
        "home_team": home_team,
        "away_team": away_team,
        "is_early_season": is_early,

        # Differentials (home − away, or pitcher: away − home for ERA-type)
        "d_runs_per_game":    diff("runs_per_game"),
        "d_runs_last_5":      diff("runs_last_5"),
        "d_runs_last_10":     diff("runs_last_10"),
        "d_ops":              diff("ops"),
        "d_wrc_plus":         diff("wrc_plus"),
        "d_woba":             diff("woba"),
        "d_iso":              diff("iso"),
        "d_k_pct":            diff("k_pct"),
        "d_bb_pct":           diff("bb_pct"),
        "d_team_era":         away_stats.get("team_era", 0) - home_stats.get("team_era", 0) if home_stats.get("team_era") and away_stats.get("team_era") else None,
        "d_bullpen_era":      away_stats.get("bullpen_era", 0) - home_stats.get("bullpen_era", 0) if home_stats.get("bullpen_era") and away_stats.get("bullpen_era") else None,
        "d_team_whip":        away_stats.get("team_whip", 0) - home_stats.get("team_whip", 0) if home_stats.get("team_whip") and away_stats.get("team_whip") else None,
        "d_team_fip":         away_stats.get("team_fip", 0) - home_stats.get("team_fip", 0) if home_stats.get("team_fip") and away_stats.get("team_fip") else None,
        "d_run_differential": diff("run_differential"),

        # Pitcher differentials
        "d_starter_era":       pitcher_diff("era"),
        "d_starter_xfip":      pitcher_diff("xfip"),
        "d_starter_k9":        pitcher_diff("k9"),
        "d_starter_bb9":       pitcher_diff("bb9"),
        "d_starter_era_last3": pitcher_diff("era_last3"),
        "d_starter_k9_last3":  pitcher_diff("k9_last3"),
        "d_starter_xfip_last3": pitcher_diff("xfip_last3"),

        # Absolute values for totals model
        "home_runs_per_game":  home_stats.get("runs_per_game"),
        "away_runs_per_game":  away_stats.get("runs_per_game"),
        "home_runs_last_5":    home_stats.get("runs_last_5"),
        "away_runs_last_5":    away_stats.get("runs_last_5"),
        "home_runs_last_10":   home_stats.get("runs_last_10"),
        "away_runs_last_10":   away_stats.get("runs_last_10"),
        "home_team_era":       home_stats.get("team_era"),
        "away_team_era":       away_stats.get("team_era"),
        "home_bullpen_era":    home_stats.get("bullpen_era"),
        "away_bullpen_era":    away_stats.get("bullpen_era"),
        "home_starter_era":    home_pitcher.get("era"),
        "away_starter_era":    away_pitcher.get("era"),
        "home_starter_k9":     home_pitcher.get("k9"),
        "away_starter_k9":     away_pitcher.get("k9"),
        "home_starter_xfip":   home_pitcher.get("xfip"),
        "away_starter_xfip":   away_pitcher.get("xfip"),
        "home_k_pct":          home_stats.get("k_pct"),
        "away_k_pct":          away_stats.get("k_pct"),

        # Home/away splits
        "home_runs_home_avg":  home_stats.get("runs_per_game_home"),
        "away_runs_away_avg":  away_stats.get("runs_per_game_away"),

        # Win/loss context
        "home_win_pct":        round(home_win_pct, 4),
        "away_win_pct":        round(away_win_pct, 4),

        # Injury features
        "home_injury_adj":    _compute_injury_adjustment(home_inj),
        "away_injury_adj":    _compute_injury_adjustment(away_inj),
        "home_starter_out":   _has_starter_out(home_inj, "MLB"),
        "away_starter_out":   _has_starter_out(away_inj, "MLB"),
        "home_has_returnee":  _has_returnee(home_inj),
        "away_has_returnee":  _has_returnee(away_inj),

        # Bullpen workload (IP by relievers in last N days — higher = more fatigued)
        "home_bullpen_ip_last1": home_bp_ip1,
        "home_bullpen_ip_last3": home_bp_ip3,
        "away_bullpen_ip_last1": away_bp_ip1,
        "away_bullpen_ip_last3": away_bp_ip3,
        "d_bullpen_ip_last3":    round(home_bp_ip3 - away_bp_ip3, 2)
                                 if home_bp_ip3 is not None and away_bp_ip3 is not None
                                 else None,
    }

    # Override rolling stats with game-date-accurate values computed from the
    # games table. The mlb_team_stats snapshot (used above) is stored at
    # end-of-season, so runs_last_5/10 from that snapshot reflect the final
    # games of the year, not the games immediately before each training game.
    home_rl5  = _rolling_runs_from_games(conn, home_team, game_date, 5)
    home_rl10 = _rolling_runs_from_games(conn, home_team, game_date, 10)
    away_rl5  = _rolling_runs_from_games(conn, away_team, game_date, 5)
    away_rl10 = _rolling_runs_from_games(conn, away_team, game_date, 10)

    features["home_runs_last_5"]  = home_rl5
    features["home_runs_last_10"] = home_rl10
    features["away_runs_last_5"]  = away_rl5
    features["away_runs_last_10"] = away_rl10
    features["d_runs_last_5"]  = (
        round(home_rl5 - away_rl5, 4)
        if home_rl5 is not None and away_rl5 is not None else None
    )
    features["d_runs_last_10"] = (
        round(home_rl10 - away_rl10, 4)
        if home_rl10 is not None and away_rl10 is not None else None
    )

    # Home/away splits — also computed from games table for accuracy
    features["home_runs_home_avg"] = _season_runs_by_location(
        conn, home_team, game_date, "home"
    )
    features["away_runs_away_avg"] = _season_runs_by_location(
        conn, away_team, game_date, "away"
    )

    # Weather context (from game_weather table — populated by weather_ingestor)
    # is_dome_game defaults to 0 (outdoors) when no weather row exists
    features["wind_out_component"] = weather.get("wind_out_component")
    features["temp_f"]             = weather.get("temp_f")
    features["is_dome_game"]       = int(weather.get("is_dome_game") or 0)

    # Market context (if odds available)
    if odds_row:
        features["total_line"] = odds_row.get("total_line")
        features["spread_home"] = odds_row.get("spread_home")
    else:
        features["total_line"]  = None
        features["spread_home"] = None

    return features


# ── NHL Feature Builder ───────────────────────────────────────────────────────

def _get_nhl_team_stats(conn: DBConnection,
                         team: str, season: int, as_of_date: str) -> dict:
    row = conn.execute("""
        SELECT games_played, goals_per_game, shots_per_game,
               corsi_for_pct, xgf_pct, power_play_pct,
               goals_last_5, goals_last_10, goals_home, goals_away,
               goals_against_pg, shots_against_pg, penalty_kill_pct, xga_pct,
               wins, losses, ot_losses, goal_differential,
               regulation_wins, regulation_losses, regulation_ties
        FROM nhl_team_stats
        WHERE team = ?
          AND season = ?
          AND as_of_date <= ?
        ORDER BY as_of_date DESC
        LIMIT 1
    """, (team, season, as_of_date)).fetchone()

    cols = [
        "games_played", "goals_per_game", "shots_per_game",
        "corsi_for_pct", "xgf_pct", "power_play_pct",
        "goals_last_5", "goals_last_10", "goals_home", "goals_away",
        "goals_against_pg", "shots_against_pg", "penalty_kill_pct", "xga_pct",
        "wins", "losses", "ot_losses", "goal_differential",
        "regulation_wins", "regulation_losses", "regulation_ties",
    ]
    if row:
        return dict(zip(cols, row))

    # Prior season fallback
    row_prev = conn.execute("""
        SELECT games_played, goals_per_game, shots_per_game,
               corsi_for_pct, xgf_pct, power_play_pct,
               goals_last_5, goals_last_10, goals_home, goals_away,
               goals_against_pg, shots_against_pg, penalty_kill_pct, xga_pct,
               wins, losses, ot_losses, goal_differential,
               regulation_wins, regulation_losses, regulation_ties
        FROM nhl_team_stats
        WHERE team = ? AND season = ?
        ORDER BY as_of_date DESC
        LIMIT 1
    """, (team, season - 1)).fetchone()

    if row_prev:
        return dict(zip(cols, row_prev))
    return {}


def _get_nhl_goalie_stats(conn: DBConnection,
                           team: str, game_date: str, season: int) -> dict:
    row = conn.execute("""
        SELECT save_pct, gaa, gsaa, save_pct_last5, gaa_last5, gsaa_last5
        FROM nhl_goalie_stats
        WHERE team = ?
          AND game_date = ?
          AND season = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (team, game_date, season)).fetchone()

    cols = ["save_pct", "gaa", "gsaa", "save_pct_last5", "gaa_last5", "gsaa_last5"]
    if row:
        return dict(zip(cols, row))
    return {}


def build_nhl_game_features(conn: DBConnection,
                              game_id: str,
                              game_date: str,
                              home_team: str,
                              away_team: str,
                              season: int,
                              odds_row: dict = None) -> dict:
    """Build the full feature row for one NHL game."""
    from data.ingestors.injury_ingestor import query_injuries_for_game

    home_stats  = _get_nhl_team_stats(conn, home_team, season, game_date)
    away_stats  = _get_nhl_team_stats(conn, away_team, season, game_date)
    home_goalie = _get_nhl_goalie_stats(conn, home_team, game_date, season)
    away_goalie = _get_nhl_goalie_stats(conn, away_team, game_date, season)

    injuries = query_injuries_for_game(conn, "NHL", home_team, away_team, game_date)
    home_inj = injuries["home_injuries"]
    away_inj = injuries["away_injuries"]

    def _gp(s: dict) -> int:
        return s.get("games_played") or 0

    is_early = int(_gp(home_stats) < MIN_GAMES_BASELINE or
                   _gp(away_stats) < MIN_GAMES_BASELINE)

    def diff(key: str, stats_h: dict = home_stats, stats_a: dict = away_stats):
        h = stats_h.get(key)
        a = stats_a.get(key)
        if h is None or a is None:
            return None
        return round(h - a, 4)

    def goalie_diff(key: str):
        h = home_goalie.get(key)
        a = away_goalie.get(key)
        if h is None or a is None:
            return None
        # save_pct: higher=better → home − away (positive = home advantage)
        # gaa: lower=better → away − home
        if key in ("gaa", "gaa_last5"):
            return round(a - h, 4)
        return round(h - a, 4)

    home_wins   = (home_stats.get("wins") or 0) + (home_stats.get("ot_losses") or 0)
    home_losses = home_stats.get("losses") or 0
    away_wins   = (away_stats.get("wins") or 0) + (away_stats.get("ot_losses") or 0)
    away_losses = away_stats.get("losses") or 0
    home_win_pct = home_wins / max(home_wins + home_losses, 1)
    away_win_pct = away_wins / max(away_wins + away_losses, 1)

    features = {
        "game_id":   game_id,
        "game_date": game_date,
        "sport":     "NHL",
        "season":    season,
        "home_team": home_team,
        "away_team": away_team,
        "is_early_season": is_early,

        # Differentials
        "d_goals_per_game":    diff("goals_per_game"),
        "d_goals_last_5":      diff("goals_last_5"),
        "d_goals_last_10":     diff("goals_last_10"),
        "d_corsi_for_pct":     diff("corsi_for_pct"),
        "d_xgf_pct":           diff("xgf_pct"),
        "d_power_play_pct":    diff("power_play_pct"),
        "d_goals_against_pg":  diff("goals_against_pg"),
        "d_penalty_kill_pct":  diff("penalty_kill_pct"),
        "d_goal_differential": diff("goal_differential"),

        # Goalie differentials
        "d_goalie_save_pct":      goalie_diff("save_pct"),
        "d_goalie_gaa":           goalie_diff("gaa"),
        "d_goalie_gsaa":          goalie_diff("gsaa"),
        "d_goalie_save_pct_last5": goalie_diff("save_pct_last5"),
        "d_goalie_gaa_last5":     goalie_diff("gaa_last5"),

        # Absolute values for totals model
        "home_goals_per_game": home_stats.get("goals_per_game"),
        "away_goals_per_game": away_stats.get("goals_per_game"),
        "home_goals_last_5":   home_stats.get("goals_last_5"),
        "away_goals_last_5":   away_stats.get("goals_last_5"),
        "home_goalie_save_pct": home_goalie.get("save_pct"),
        "away_goalie_save_pct": away_goalie.get("save_pct"),
        "home_goalie_gaa":     home_goalie.get("gaa"),
        "away_goalie_gaa":     away_goalie.get("gaa"),
        "home_power_play_pct": home_stats.get("power_play_pct"),
        "away_power_play_pct": away_stats.get("power_play_pct"),
        "home_penalty_kill_pct": home_stats.get("penalty_kill_pct"),
        "away_penalty_kill_pct": away_stats.get("penalty_kill_pct"),

        # Home/away splits
        "home_goals_home_avg": home_stats.get("goals_home"),
        "away_goals_away_avg": away_stats.get("goals_away"),

        # Win context
        "home_win_pct": round(home_win_pct, 4),
        "away_win_pct": round(away_win_pct, 4),

        # Injury features
        "home_injury_adj":  _compute_injury_adjustment(home_inj),
        "away_injury_adj":  _compute_injury_adjustment(away_inj),
        "home_goalie_out":  _has_starter_out(home_inj, "NHL"),
        "away_goalie_out":  _has_starter_out(away_inj, "NHL"),
        "home_has_returnee": _has_returnee(home_inj),
        "away_has_returnee": _has_returnee(away_inj),
    }

    if odds_row:
        features["total_line"]  = odds_row.get("total_line")
        features["spread_home"] = odds_row.get("spread_home")
    else:
        features["total_line"]  = None
        features["spread_home"] = None

    return features


# ── Unified Game Feature Builder ──────────────────────────────────────────────

def build_features_for_game(conn: DBConnection,
                              game_id: str,
                              odds_row: dict = None) -> dict | None:
    """
    Build features for a single game. Auto-detects sport.
    Returns None if the game isn't found in the DB.
    """
    row = conn.execute("""
        SELECT sport, season, game_date, home_team, away_team
        FROM games WHERE game_id = ?
    """, (game_id,)).fetchone()

    if not row:
        logger.warning(f"Game {game_id} not found in DB")
        return None

    sport, season, game_date, home_team, away_team = row

    if sport == "MLB":
        return build_mlb_game_features(conn, game_id, game_date,
                                        home_team, away_team, season, odds_row)
    elif sport == "NHL":
        return build_nhl_game_features(conn, game_id, game_date,
                                        home_team, away_team, season, odds_row)
    elif sport == "WNBA":
        from features.wnba_feature_engine import build_wnba_game_features
        return build_wnba_game_features(conn, game_id, game_date,
                                         home_team, away_team, season, odds_row)
    elif sport == "NBA":
        from features.nba_feature_engine import build_nba_game_features
        return build_nba_game_features(conn, game_id, game_date,
                                        home_team, away_team, season, odds_row)
    elif sport == "UFC":
        from features.ufc_feature_engine import build_ufc_game_features
        return build_ufc_game_features(conn, game_id, game_date,
                                        home_team, away_team, season, odds_row)
    else:
        logger.error(f"Unknown sport '{sport}' for game {game_id}")
        return None


# ── Bulk Training Feature Builder (MLB) ──────────────────────────────────────
# During build_training_dataset, per-game DB round trips to Supabase are replaced
# with 8 bulk queries + fast in-memory dict/bisect lookups.
# The live scoring path (build_mlb_game_features) is unchanged.

def _build_bulk_mlb_lookups(conn: DBConnection, seasons: list[int]) -> dict:
    """
    Bulk-load all tables needed for MLB training features in ~8 queries.
    Returns a dict of lookup structures keyed for fast ASOF / exact access.
    """
    all_seasons = sorted(set(seasons))
    load_seasons = list(range(min(all_seasons) - 1, max(all_seasons) + 2))
    sp_load = ','.join(['%s'] * len(load_seasons))
    sp_all  = ','.join(['%s'] * len(all_seasons))

    # ── Team stats ────────────────────────────────────────────────────────────
    ts_cols = ['team', 'season', 'as_of_date', 'games_played', 'ops', 'wrc_plus', 'woba',
               'k_pct', 'bb_pct', 'iso', 'babip', 'runs_per_game', 'runs_last_5', 'runs_last_10',
               'runs_last_15', 'runs_per_game_home', 'runs_per_game_away',
               'team_era', 'bullpen_era', 'team_whip', 'team_fip', 'wins', 'losses', 'run_differential']
    ts_rows = conn.execute(f"""
        SELECT {', '.join(ts_cols)}
        FROM mlb_team_stats WHERE season IN ({sp_load})
        ORDER BY team, season, as_of_date
    """, load_seasons).fetchall()

    # (team, season) → (sorted_dates, stats_list) for ASOF lookup
    team_stats: dict = {}
    for r in ts_rows:
        d = dict(zip(ts_cols, r))
        k = (d['team'], d['season'])
        if k not in team_stats:
            team_stats[k] = ([], [])
        team_stats[k][0].append(d['as_of_date'])
        team_stats[k][1].append(d)

    # ── Pitcher stats ─────────────────────────────────────────────────────────
    ps_cols = ['team', 'game_date', 'season', 'era', 'xfip', 'whip', 'k9', 'bb9',
               'swstr_pct', 'csw_pct', 'era_last3', 'k9_last3', 'xfip_last3']
    ps_rows = conn.execute(f"""
        SELECT {', '.join(ps_cols)}
        FROM mlb_pitcher_stats WHERE season IN ({sp_all})
    """, all_seasons).fetchall()
    # (team, game_date, season) → dict
    pitcher: dict = {(r[0], r[1], r[2]): dict(zip(ps_cols, r)) for r in ps_rows}

    # ── Bullpen workload ──────────────────────────────────────────────────────
    bp_rows = conn.execute(f"""
        SELECT team, game_date, ip FROM mlb_bullpen_stats WHERE season IN ({sp_all})
        ORDER BY team, game_date
    """, all_seasons).fetchall()
    # team → (sorted_dates, ip_values)
    bullpen: dict = {}
    for team, gdate, ip in bp_rows:
        if team not in bullpen:
            bullpen[team] = ([], [])
        bullpen[team][0].append(gdate)
        bullpen[team][1].append(float(ip) if ip is not None else 0.0)

    # ── Rolling runs from games table ─────────────────────────────────────────
    # Load ALL historical MLB games so rolling windows at season starts are accurate
    hist_rows = conn.execute("""
        SELECT game_date, home_team, away_team, home_score, away_score
        FROM games WHERE sport = 'MLB' AND home_score IS NOT NULL
        ORDER BY game_date
    """).fetchall()

    runs: dict = {}       # team → (sorted dates, runs) — all games
    home_runs: dict = {}  # team → (sorted dates, runs) — home games only
    away_runs: dict = {}  # team → (sorted dates, runs) — away games only
    for gdate, ht, at, hs, as_ in hist_rows:
        if hs is not None:
            runs.setdefault(ht, ([], []))[0].append(gdate)
            runs[ht][1].append(float(hs))
            home_runs.setdefault(ht, ([], []))[0].append(gdate)
            home_runs[ht][1].append(float(hs))
        if as_ is not None:
            runs.setdefault(at, ([], []))[0].append(gdate)
            runs[at][1].append(float(as_))
            away_runs.setdefault(at, ([], []))[0].append(gdate)
            away_runs[at][1].append(float(as_))

    # ── Weather ───────────────────────────────────────────────────────────────
    w_rows = conn.execute("""
        SELECT game_id, temp_f, wind_mph, wind_out_component, precip_mm, is_dome_game
        FROM game_weather
    """).fetchall()
    weather: dict = {
        r[0]: dict(zip(['temp_f', 'wind_mph', 'wind_out_component', 'precip_mm', 'is_dome_game'], r[1:]))
        for r in w_rows
    }

    # ── Injuries ──────────────────────────────────────────────────────────────
    inj_cols = ['team', 'report_date', 'scenario', 'severity_weight', 'return_ramp_factor', 'status']
    inj_rows = conn.execute("""
        SELECT team, report_date, scenario, severity_weight, return_ramp_factor, status
        FROM injuries WHERE sport = 'MLB'
        ORDER BY team, report_date
    """).fetchall()
    injuries: dict = {}   # team → {report_date: [inj_dict, ...]}
    inj_dates: dict = {}  # team → sorted list of report_dates
    for r in inj_rows:
        d = dict(zip(inj_cols, r))
        team, rdate = d['team'], d['report_date']
        if team not in injuries:
            injuries[team] = {}
            inj_dates[team] = []
        if rdate not in injuries[team]:
            injuries[team][rdate] = []
            inj_dates[team].append(rdate)
        injuries[team][rdate].append(d)
    for t in inj_dates:
        inj_dates[t].sort()

    # ── Odds ──────────────────────────────────────────────────────────────────
    o_cols = ['game_id', 'market', 'bookmaker', 'home_price', 'away_price', 'draw_price',
              'spread_home', 'total_line', 'over_price', 'under_price', 'snapshot_type', 'snapshot_at']
    o_rows = conn.execute("""
        SELECT game_id, market, bookmaker, home_price, away_price, draw_price,
               spread_home, total_line, over_price, under_price, snapshot_type, snapshot_at
        FROM odds
        WHERE bookmaker IN ('draftkings', 'sbr_consensus')
          AND snapshot_type != 'in_play'
        ORDER BY game_id, market,
                 CASE bookmaker WHEN 'draftkings' THEN 0 ELSE 1 END,
                 snapshot_at DESC
    """).fetchall()
    # (game_id, market) → best/latest odds dict (draftkings preferred over sbr_consensus)
    odds_lookup: dict = {}
    for r in o_rows:
        d = dict(zip(o_cols, r))
        k = (d['game_id'], d['market'])
        if k not in odds_lookup:
            odds_lookup[k] = d

    logger.debug(
        f"Bulk loads: {len(ts_rows)} team-stat rows, {len(ps_rows)} pitcher rows, "
        f"{len(bp_rows)} bullpen rows, {len(hist_rows)} hist games, "
        f"{len(w_rows)} weather rows, {len(inj_rows)} injury rows, {len(o_rows)} odds rows"
    )

    return dict(team_stats=team_stats, pitcher=pitcher, bullpen=bullpen,
                runs=runs, home_runs=home_runs, away_runs=away_runs,
                weather=weather, injuries=injuries, inj_dates=inj_dates,
                odds=odds_lookup)


def _blk_team_stats(bulk: dict, team: str, season: int, game_date: str) -> dict:
    """ASOF lookup: latest team stats row where as_of_date <= game_date."""
    ts = bulk['team_stats']
    for s in (season, season - 1):
        k = (team, s)
        if k in ts:
            dates, stats = ts[k]
            idx = bisect.bisect_right(dates, game_date) - 1
            if idx >= 0:
                if s == season - 1:
                    logger.debug(f"MLB {team}: using prior-season ({s}) stats as baseline")
                return stats[idx]
    return {}


def _blk_pitcher(bulk: dict, team: str, game_date: str, season: int) -> dict:
    return bulk['pitcher'].get((team, game_date, season), {})


def _blk_bullpen_ip(bulk: dict, team: str, game_date: str, days: int) -> float:
    """Sum of bullpen IP in the `days` calendar days strictly before game_date."""
    bp = bulk['bullpen']
    if team not in bp:
        return 0.0
    dates, ips = bp[team]
    cutoff = (datetime.strptime(game_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
    lo = bisect.bisect_left(dates, cutoff)
    hi = bisect.bisect_left(dates, game_date)
    return round(sum(ips[lo:hi]), 2)


def _blk_rolling_runs(bulk: dict, team: str, game_date: str, window: int) -> float | None:
    """Average runs scored in the last `window` games strictly before game_date."""
    if team not in bulk['runs']:
        return None
    dates, runs_list = bulk['runs'][team]
    hi = bisect.bisect_left(dates, game_date)
    recent = runs_list[max(0, hi - window):hi]
    return round(float(np.mean(recent)), 3) if len(recent) >= 3 else None


def _blk_season_loc_runs(bulk: dict, team: str, game_date: str, location: str) -> float | None:
    """Season average runs at home or away, up to (not including) game_date."""
    src = bulk['home_runs'] if location == 'home' else bulk['away_runs']
    if team not in src:
        return None
    dates, runs_list = src[team]
    season_start = f"{game_date[:4]}-01-01"
    lo = bisect.bisect_left(dates, season_start)
    hi = bisect.bisect_left(dates, game_date)
    season_runs = runs_list[lo:hi]
    return round(float(np.mean(season_runs)), 3) if season_runs else None


def _blk_injuries(bulk: dict, team: str, game_date: str) -> list[dict]:
    """Injuries for team from the most recent report on or before game_date."""
    if team not in bulk['inj_dates']:
        return []
    dates = bulk['inj_dates'][team]
    idx = bisect.bisect_right(dates, game_date) - 1
    if idx < 0:
        return []
    return bulk['injuries'][team].get(dates[idx], [])


def _build_mlb_features_from_bulk(bulk: dict,
                                    game_id: str, game_date: str,
                                    home_team: str, away_team: str,
                                    season: int,
                                    odds_row: dict | None) -> dict:
    """
    Build the full MLB feature row using pre-loaded bulk data.
    Equivalent to build_mlb_game_features but with in-memory lookups.
    """
    home_stats   = _blk_team_stats(bulk, home_team, season, game_date)
    away_stats   = _blk_team_stats(bulk, away_team, season, game_date)
    home_pitcher = _blk_pitcher(bulk, home_team, game_date, season)
    away_pitcher = _blk_pitcher(bulk, away_team, game_date, season)
    weather      = bulk['weather'].get(game_id, {})

    home_bp_ip1 = _blk_bullpen_ip(bulk, home_team, game_date, 1)
    home_bp_ip3 = _blk_bullpen_ip(bulk, home_team, game_date, 3)
    away_bp_ip1 = _blk_bullpen_ip(bulk, away_team, game_date, 1)
    away_bp_ip3 = _blk_bullpen_ip(bulk, away_team, game_date, 3)

    home_inj = _blk_injuries(bulk, home_team, game_date)
    away_inj = _blk_injuries(bulk, away_team, game_date)

    def _gp(s): return s.get("games_played") or 0
    is_early = int(_gp(home_stats) < MIN_GAMES_BASELINE or _gp(away_stats) < MIN_GAMES_BASELINE)

    def diff(key):
        h, a = home_stats.get(key), away_stats.get(key)
        return round(h - a, 4) if h is not None and a is not None else None

    def pitcher_diff(key):
        h, a = home_pitcher.get(key), away_pitcher.get(key)
        if h is None or a is None:
            return None
        return round(a - h, 4) if key in ("era", "xfip", "bb9", "era_last3", "xfip_last3") else round(h - a, 4)

    hw, hl = home_stats.get("wins") or 0, home_stats.get("losses") or 0
    aw, al = away_stats.get("wins") or 0, away_stats.get("losses") or 0
    home_win_pct = hw / max(hw + hl, 1)
    away_win_pct = aw / max(aw + al, 1)

    home_rl5  = _blk_rolling_runs(bulk, home_team, game_date, 5)
    home_rl10 = _blk_rolling_runs(bulk, home_team, game_date, 10)
    away_rl5  = _blk_rolling_runs(bulk, away_team, game_date, 5)
    away_rl10 = _blk_rolling_runs(bulk, away_team, game_date, 10)

    return {
        "game_id":   game_id,
        "game_date": game_date,
        "sport":     "MLB",
        "season":    season,
        "home_team": home_team,
        "away_team": away_team,
        "is_early_season": is_early,

        "d_runs_per_game":    diff("runs_per_game"),
        "d_runs_last_5":      round(home_rl5  - away_rl5,  4) if home_rl5  is not None and away_rl5  is not None else None,
        "d_runs_last_10":     round(home_rl10 - away_rl10, 4) if home_rl10 is not None and away_rl10 is not None else None,
        "d_ops":              diff("ops"),
        "d_wrc_plus":         diff("wrc_plus"),
        "d_woba":             diff("woba"),
        "d_iso":              diff("iso"),
        "d_k_pct":            diff("k_pct"),
        "d_bb_pct":           diff("bb_pct"),
        "d_team_era":         round(away_stats.get("team_era", 0) - home_stats.get("team_era", 0), 4)
                              if home_stats.get("team_era") and away_stats.get("team_era") else None,
        "d_bullpen_era":      round(away_stats.get("bullpen_era", 0) - home_stats.get("bullpen_era", 0), 4)
                              if home_stats.get("bullpen_era") and away_stats.get("bullpen_era") else None,
        "d_team_whip":        round(away_stats.get("team_whip", 0) - home_stats.get("team_whip", 0), 4)
                              if home_stats.get("team_whip") and away_stats.get("team_whip") else None,
        "d_team_fip":         round(away_stats.get("team_fip", 0) - home_stats.get("team_fip", 0), 4)
                              if home_stats.get("team_fip") and away_stats.get("team_fip") else None,
        "d_run_differential": diff("run_differential"),

        "d_starter_era":        pitcher_diff("era"),
        "d_starter_xfip":       pitcher_diff("xfip"),
        "d_starter_k9":         pitcher_diff("k9"),
        "d_starter_bb9":        pitcher_diff("bb9"),
        "d_starter_era_last3":  pitcher_diff("era_last3"),
        "d_starter_k9_last3":   pitcher_diff("k9_last3"),
        "d_starter_xfip_last3": pitcher_diff("xfip_last3"),

        "home_runs_per_game":  home_stats.get("runs_per_game"),
        "away_runs_per_game":  away_stats.get("runs_per_game"),
        "home_runs_last_5":    home_rl5,
        "away_runs_last_5":    away_rl5,
        "home_runs_last_10":   home_rl10,
        "away_runs_last_10":   away_rl10,
        "home_team_era":       home_stats.get("team_era"),
        "away_team_era":       away_stats.get("team_era"),
        "home_bullpen_era":    home_stats.get("bullpen_era"),
        "away_bullpen_era":    away_stats.get("bullpen_era"),
        "home_starter_era":    home_pitcher.get("era"),
        "away_starter_era":    away_pitcher.get("era"),
        "home_starter_k9":     home_pitcher.get("k9"),
        "away_starter_k9":     away_pitcher.get("k9"),
        "home_starter_xfip":   home_pitcher.get("xfip"),
        "away_starter_xfip":   away_pitcher.get("xfip"),
        "home_k_pct":          home_stats.get("k_pct"),
        "away_k_pct":          away_stats.get("k_pct"),

        "home_runs_home_avg":  _blk_season_loc_runs(bulk, home_team, game_date, 'home'),
        "away_runs_away_avg":  _blk_season_loc_runs(bulk, away_team, game_date, 'away'),

        "home_win_pct":       round(home_win_pct, 4),
        "away_win_pct":       round(away_win_pct, 4),

        "home_injury_adj":   _compute_injury_adjustment(home_inj),
        "away_injury_adj":   _compute_injury_adjustment(away_inj),
        "home_starter_out":  _has_starter_out(home_inj, "MLB"),
        "away_starter_out":  _has_starter_out(away_inj, "MLB"),
        "home_has_returnee": _has_returnee(home_inj),
        "away_has_returnee": _has_returnee(away_inj),

        "home_bullpen_ip_last1": home_bp_ip1,
        "home_bullpen_ip_last3": home_bp_ip3,
        "away_bullpen_ip_last1": away_bp_ip1,
        "away_bullpen_ip_last3": away_bp_ip3,
        "d_bullpen_ip_last3":    round(home_bp_ip3 - away_bp_ip3, 2),

        "wind_out_component": weather.get("wind_out_component"),
        "temp_f":             weather.get("temp_f"),
        "is_dome_game":       int(weather.get("is_dome_game") or 0),

        "total_line":  odds_row.get("total_line")  if odds_row else None,
        "spread_home": odds_row.get("spread_home") if odds_row else None,
    }


# ── Training Dataset Builder ──────────────────────────────────────────────────

def build_training_dataset(model_id: str,
                             seasons: list[int],
                             db_path: str = None) -> pd.DataFrame:
    """
    Build the full historical feature matrix for training.
    Pulls all completed games for the given seasons, builds features,
    and attaches the appropriate target variable.

    Args:
        model_id: e.g. 'mlb_moneyline', 'nhl_over_under'
        seasons:  list of seasons to include
        db_path:  ignored (kept for backwards compat); uses DATABASE_URL

    Returns:
        DataFrame with feature columns + 'target' column + metadata.
        Rows where target is NULL are dropped.
    """
    from config import MODELS
    if model_id not in MODELS:
        raise ValueError(f"Unknown model_id: {model_id}")

    sport, market, _ = MODELS[model_id]
    feature_cols = FEATURE_MAP[model_id]

    # GOLF rows are per-player (or per-pair) — not per-game — so golf has its own
    # builder (the prop-model precedent). Delegate and return early.
    if sport == "GOLF":
        from features.golf_feature_engine import build_golf_training_dataset
        return build_golf_training_dataset(model_id, seasons)

    conn = get_connection()

    # Pull all completed games for the requested seasons
    is_f5_model = market.endswith("_1st_5_innings")
    placeholders = ",".join(["%s"] * len(seasons))
    games = conn.execute(f"""
        SELECT game_id, sport, season, game_date, home_team, away_team,
               home_score, away_score, home_win, home_win_reg, went_to_ot,
               regulation_tie, home_score_f5, away_score_f5
        FROM games
        WHERE sport = %s
          AND season IN ({placeholders})
          AND home_score IS NOT NULL
        ORDER BY game_date
    """, [sport] + seasons).fetchall()

    logger.info(f"Building {model_id} training set: {len(games)} games "
                f"across seasons {seasons}")

    rows = []
    from data.ingestors.odds_ingestor import get_latest_odds_for_game

    # For MLB and WNBA, bulk-load all lookup tables upfront to avoid per-game DB
    # round trips. For NHL, fall back to the per-game path (no data loaded yet).
    bulk = None
    wnba_bulk = None
    nba_bulk = None
    ufc_bulk = None
    if sport == "MLB":
        bulk = _build_bulk_mlb_lookups(conn, seasons)
    elif sport == "WNBA":
        from features.wnba_feature_engine import (
            build_bulk_wnba_lookups, build_wnba_features_from_bulk,
        )
        wnba_bulk = build_bulk_wnba_lookups(conn, seasons)
    elif sport == "NBA":
        from features.nba_feature_engine import (
            build_bulk_nba_lookups, build_nba_features_from_bulk,
        )
        nba_bulk = build_bulk_nba_lookups(conn, seasons)
    elif sport == "UFC":
        from features.ufc_feature_engine import (
            build_bulk_ufc_lookups, build_ufc_features_from_bulk,
            compute_ufc_target,
        )
        ufc_bulk = build_bulk_ufc_lookups(conn, seasons)

    for game in games:
        (game_id, sp, season, game_date, home_team, away_team,
         home_score, away_score, home_win, home_win_reg,
         went_to_ot, reg_tie, home_score_f5, away_score_f5) = game

        # F5 models require F5 scores for target computation
        if is_f5_model and (home_score_f5 is None or away_score_f5 is None):
            continue

        if sp == "MLB":
            # F5 models use full-game features but F5 odds for context (total_line, spread)
            odds_market = _market_for_odds(market)
            odds = bulk['odds'].get((game_id, odds_market))
            # For F5 models, also fetch the full-game h2h odds for feature building
            feat_odds = odds if not is_f5_model else bulk['odds'].get((game_id, 'h2h'))
            feat = _build_mlb_features_from_bulk(bulk, game_id, game_date,
                                                  home_team, away_team, season, feat_odds)
            # For F5 totals/spreads, inject the F5 line into features
            if is_f5_model and odds:
                if "total_line" in FEATURE_MAP[model_id] and odds.get("total_line") is not None:
                    feat["total_line"] = odds["total_line"]
                if "spread_home" in FEATURE_MAP[model_id] and odds.get("spread_home") is not None:
                    feat["spread_home"] = odds["spread_home"]
        elif sp == "WNBA":
            odds = wnba_bulk['odds'].get((game_id, _market_for_odds(market)))
            feat = build_wnba_features_from_bulk(wnba_bulk, game_id, game_date,
                                                 home_team, away_team, season, odds)
        elif sp == "NBA":
            odds = nba_bulk['odds'].get((game_id, _market_for_odds(market)))
            feat = build_nba_features_from_bulk(nba_bulk, game_id, game_date,
                                                home_team, away_team, season, odds)
        elif sp == "UFC":
            odds = ufc_bulk['odds'].get((game_id, _market_for_odds(market)))
            feat = build_ufc_features_from_bulk(ufc_bulk, game_id, game_date,
                                                home_team, away_team, season, odds)
        else:
            odds = get_latest_odds_for_game(conn, game_id, _market_for_odds(market))
            feat = build_nhl_game_features(conn, game_id, game_date,
                                            home_team, away_team, season, odds)

        if feat is None:
            continue

        # Attach target
        if sp == "UFC":
            # Fight outcomes (method / round / time) live in ufc_fight_log,
            # not the games row — UFC has its own target helper. The totals
            # line the target settles against is the one the feature row
            # carries (real DK line when present, synthetic otherwise).
            target = compute_ufc_target(
                model_id, market,
                ufc_bulk['results'].get(game_id),
                home_win,
                feat.get("total_line") if market == "totals" else None,
            )
        else:
            target = _compute_target(model_id, market,
                                      home_score, away_score,
                                      home_win, home_win_reg,
                                      went_to_ot, reg_tie,
                                      odds,
                                      home_score_f5=home_score_f5,
                                      away_score_f5=away_score_f5)
        if target is None:
            continue   # can't compute target, skip

        feat["target"] = target
        rows.append(feat)

    conn.close()

    if not rows:
        logger.warning(f"No training rows generated for {model_id}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Keep only feature columns + metadata + target
    meta_cols = ["game_id", "game_date", "sport", "season", "home_team", "away_team"]
    keep_cols = meta_cols + [c for c in feature_cols if c in df.columns] + ["target"]
    df = df[[c for c in keep_cols if c in df.columns]]

    # Drop rows with any null feature values. We do not impute — a missing
    # feature means we didn't have the data for that game, and training on
    # fabricated values teaches the model nothing real.
    num_cols = [c for c in df.columns if c not in meta_cols + ["target"]]
    before = len(df)
    df = df.dropna(subset=num_cols)
    dropped = before - len(df)
    if dropped:
        logger.info(f"  Dropped {dropped} rows with null features ({dropped/before:.1%})")

    logger.success(f"{model_id}: {len(df)} training rows, "
                   f"{df['target'].sum():.0f} positives "
                   f"({df['target'].mean():.1%} win rate)")
    return df


def _market_for_odds(market: str) -> str:
    """Map model market to odds table market key."""
    mapping = {
        "h2h":                    "h2h",
        "h2h_3way":               "h2h_3way",
        "totals":                 "totals",
        "spreads":                "spreads",
        "h2h_1st_5_innings":      "h2h_1st_5_innings",
        "totals_1st_5_innings":   "totals_1st_5_innings",
        "spreads_1st_5_innings":  "spreads_1st_5_innings",
    }
    return mapping.get(market, market)


def _compute_target(model_id: str, market: str,
                     home_score: float, away_score: float,
                     home_win: int, home_win_reg: int,
                     went_to_ot: int, reg_tie: int,
                     odds: dict | None,
                     home_score_f5: float = None,
                     away_score_f5: float = None) -> int | None:
    """
    Compute the binary (or ternary for 3-way) target variable.
    Returns None if target cannot be computed.
    """
    if home_score is None or away_score is None:
        return None

    # F5 (first 5 innings) markets use F5 scores
    if market == "h2h_1st_5_innings":
        if home_score_f5 is None or away_score_f5 is None:
            return None
        if home_score_f5 == away_score_f5:
            return None   # tie after 5 (no winner)
        return int(home_score_f5 > away_score_f5)

    elif market == "totals_1st_5_innings":
        if home_score_f5 is None or away_score_f5 is None:
            return None
        if odds and odds.get("total_line") is not None:
            total = home_score_f5 + away_score_f5
            line = odds["total_line"]
            if total == line:
                return None   # push
            return int(total > line)
        return None

    elif market == "spreads_1st_5_innings":
        if home_score_f5 is None or away_score_f5 is None:
            return None
        if odds and odds.get("spread_home") is not None:
            margin = home_score_f5 - away_score_f5
            spread = odds["spread_home"]
            covered = margin + spread
            if covered == 0:
                return None   # push
            return int(covered > 0)
        return None

    # Full-game markets
    if market == "h2h":
        return int(home_win == 1) if home_win is not None else None

    elif market == "h2h_3way":
        if home_win_reg is not None:
            return int(home_win_reg == 1)
        return None

    elif market == "totals":
        if odds and odds.get("total_line") is not None:
            total = home_score + away_score
            line  = odds["total_line"]
            if total == line:
                return None   # push
            return int(total > line)
        return None

    elif market == "spreads":
        if odds and odds.get("spread_home") is not None:
            margin = home_score - away_score
            spread = odds["spread_home"]
            covered = margin + spread
            if covered == 0:
                return None   # push
            return int(covered > 0)
        return None

    return None


# ── CLI Helper ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build training dataset")
    parser.add_argument("model_id", help="e.g. mlb_moneyline")
    parser.add_argument("--seasons", nargs="+", type=int,
                        default=[2019, 2020, 2021, 2022, 2023])
    parser.add_argument("--out", default=None, help="Output CSV path")
    args = parser.parse_args()

    df = build_training_dataset(args.model_id, args.seasons)
    if not df.empty:
        if args.out:
            df.to_csv(args.out, index=False)
            logger.info(f"Saved to {args.out}")
        else:
            logger.info(f"Shape: {df.shape}")
            logger.info(df.describe())

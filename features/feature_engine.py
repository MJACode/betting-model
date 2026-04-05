"""
feature_engine.py — Master feature builder for all sports and markets.

Orchestrates MLB and NHL feature extractors, applies injury adjustments,
and assembles the final feature matrix used by model training and scoring.

Usage:
    from features.feature_engine import build_features_for_game
    from features.feature_engine import build_training_dataset
"""

from datetime import date, datetime
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MIN_GAMES_BASELINE, SPORTS
from data.db import get_connection, DBConnection


# ── Feature Column Groups ─────────────────────────────────────────────────────
# These define what goes into each model's feature matrix.
# Expanding or removing columns here flows through to training automatically.

MLB_H2H_FEATURES = [
    # Offense differentials (home − away)
    # d_runs_per_game removed: mlb_team_stats.runs_per_game never populated; use rolling below
    "d_runs_last_5", "d_runs_last_10",
    "d_ops", "d_wrc_plus", "d_woba", "d_iso",
    "d_k_pct", "d_bb_pct",
    # Starter differentials (home − away; from mlb_pitcher_stats backfill)
    "d_starter_era", "d_starter_k9", "d_starter_bb9",
    "d_starter_era_last3", "d_starter_k9_last3",
    # Team pitching differentials
    "d_team_era", "d_bullpen_era", "d_team_whip", "d_team_fip",
    # Home/away splits
    "home_runs_home_avg", "away_runs_away_avg",
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
    # home/away_runs_per_game removed: column never populated in mlb_team_stats
    "home_runs_last_5", "away_runs_last_5",
    "home_runs_last_10", "away_runs_last_10",
    "home_team_era", "away_team_era",
    "home_bullpen_era", "away_bullpen_era",
    # Starter stats (from mlb_pitcher_stats backfill)
    "home_starter_era", "away_starter_era",
    "home_starter_k9", "away_starter_k9",
    "home_k_pct", "away_k_pct",
    "total_line",    # market-implied line (informative)
    # Bullpen workload (both teams — more combined IP = higher scoring variance)
    "home_bullpen_ip_last3", "away_bullpen_ip_last3",
    "home_injury_adj", "away_injury_adj",
    "is_early_season",
]

# Spreads uses same features as H2H (same drivers)
MLB_SPREADS_FEATURES = MLB_H2H_FEATURES + ["spread_home"]

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

FEATURE_MAP = {
    "mlb_moneyline":            MLB_H2H_FEATURES,
    "mlb_over_under":           MLB_TOTALS_FEATURES,
    "mlb_runline":              MLB_SPREADS_FEATURES,
    "nhl_moneyline":            NHL_H2H_FEATURES,
    "nhl_moneyline_regulation": NHL_REG_FEATURES,
    "nhl_over_under":           NHL_TOTALS_FEATURES,
    "nhl_puckline":             NHL_PUCKLINE_FEATURES,
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
    from datetime import timedelta
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
    else:
        logger.error(f"Unknown sport '{sport}' for game {game_id}")
        return None


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

    conn = get_connection()

    # Pull all completed games for the requested seasons
    placeholders = ",".join(["%s"] * len(seasons))
    games = conn.execute(f"""
        SELECT game_id, sport, season, game_date, home_team, away_team,
               home_score, away_score, home_win, home_win_reg, went_to_ot,
               regulation_tie
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

    for game in games:
        (game_id, sp, season, game_date, home_team, away_team,
         home_score, away_score, home_win, home_win_reg,
         went_to_ot, reg_tie) = game

        # Get odds context for this game
        odds = get_latest_odds_for_game(conn, game_id, _market_for_odds(market))

        # Build features
        if sp == "MLB":
            feat = build_mlb_game_features(conn, game_id, game_date,
                                            home_team, away_team, season, odds)
        else:
            feat = build_nhl_game_features(conn, game_id, game_date,
                                            home_team, away_team, season, odds)

        if feat is None:
            continue

        # Attach target
        target = _compute_target(model_id, market,
                                  home_score, away_score,
                                  home_win, home_win_reg,
                                  went_to_ot, reg_tie,
                                  odds)
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
        "h2h":      "h2h",
        "h2h_3way": "h2h_3way",
        "totals":   "totals",
        "spreads":  "spreads",
    }
    return mapping.get(market, market)


def _compute_target(model_id: str, market: str,
                     home_score: float, away_score: float,
                     home_win: int, home_win_reg: int,
                     went_to_ot: int, reg_tie: int,
                     odds: dict | None) -> int | None:
    """
    Compute the binary (or ternary for 3-way) target variable.
    Returns None if target cannot be computed.
    """
    if home_score is None or away_score is None:
        return None

    if market == "h2h":
        # Full-game: home wins (incl. OT/SO for NHL)
        return int(home_win == 1) if home_win is not None else None

    elif market == "h2h_3way":
        # NHL regulation: 1=home win, 0=draw, -1=away win
        # For training we'll binarize: 1 if home wins in regulation
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
        return None   # can't compute without a line

    elif market == "spreads":
        if odds and odds.get("spread_home") is not None:
            margin = home_score - away_score
            spread = odds["spread_home"]
            covered = margin + spread  # positive = home covered
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

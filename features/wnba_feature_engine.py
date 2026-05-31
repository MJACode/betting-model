"""
wnba_feature_engine.py — WNBA game feature builder (moneyline / totals / spread).

Mirrors the MLB/NHL builders in feature_engine.py:
  • build_wnba_game_features      — live scoring (per-game DB lookups)
  • build_bulk_wnba_lookups       — bulk-load tables for training/backtest
  • build_wnba_features_from_bulk  — fast in-memory ASOF lookups

Feature lists (WNBA_H2H_FEATURES / WNBA_TOTALS_FEATURES / WNBA_SPREAD_FEATURES)
and FEATURE_MAP entries live in feature_engine.py alongside MLB/NHL. The unified
dispatcher build_features_for_game() and build_training_dataset() call into here.

Data sources:
  • wnba_team_stats       — ASOF season-to-date team metrics (off/def rating, pace,
                            eFG%, FG3%, FT%, reb/ast/TOV%, ppg, pts allowed, W/L,
                            home/away pts, point differential)
  • games (sport='WNBA')  — rolling points + rest-days / back-to-back signal
  • injuries (sport='WNBA') — shared injury-adjustment helpers
"""

import bisect
from datetime import datetime, timedelta
from pathlib import Path
import sys

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MIN_GAMES_BASELINE
from data.db import DBConnection
# Shared injury helpers (one-way import — feature_engine imports the builders here
# only lazily, inside functions, so there is no circular import at module load).
from features.feature_engine import (
    _compute_injury_adjustment,
    _has_returnee,
)

# WNBA teams reach ~10 games much faster than the 10-game MLB/NHL baseline, but we
# keep the same gate for consistency — short seasons make early stats noisy too.
WNBA_MIN_GAMES = MIN_GAMES_BASELINE


# ── Rest / schedule helper ─────────────────────────────────────────────────────

def _rest_days(prior_dates: list[str], game_date: str) -> int | None:
    """Days since the team's most recent prior game (None if no prior game)."""
    idx = bisect.bisect_left(prior_dates, game_date)
    if idx == 0:
        return None
    last = prior_dates[idx - 1]
    try:
        d0 = datetime.strptime(last, "%Y-%m-%d")
        d1 = datetime.strptime(game_date, "%Y-%m-%d")
        return (d1 - d0).days
    except ValueError:
        return None


# ── Shared row assembly (works for both live and bulk paths) ───────────────────

def _assemble_wnba_features(game_id: str, game_date: str,
                            home_team: str, away_team: str, season: int,
                            home_stats: dict, away_stats: dict,
                            home_pts_l3: float | None, home_pts_l5: float | None,
                            away_pts_l3: float | None, away_pts_l5: float | None,
                            home_rest: int | None, away_rest: int | None,
                            home_inj: list, away_inj: list,
                            odds_row: dict | None) -> dict:
    """Build the feature dict from already-resolved stat inputs."""

    def _gp(s: dict) -> int:
        return s.get("games_played") or 0

    is_early = int(_gp(home_stats) < WNBA_MIN_GAMES or _gp(away_stats) < WNBA_MIN_GAMES)

    def diff(key: str):
        h, a = home_stats.get(key), away_stats.get(key)
        if h is None or a is None:
            return None
        return round(float(h) - float(a), 4)

    # net rating = off − def, computed per team then differenced
    def _net(s: dict):
        o, d = s.get("off_rating"), s.get("def_rating")
        return (float(o) - float(d)) if (o is not None and d is not None) else None

    home_net, away_net = _net(home_stats), _net(away_stats)
    d_net = round(home_net - away_net, 4) if (home_net is not None and away_net is not None) else None

    def _diff_vals(h, a):
        return round(float(h) - float(a), 4) if (h is not None and a is not None) else None

    home_w = home_stats.get("wins") or 0
    home_l = home_stats.get("losses") or 0
    away_w = away_stats.get("wins") or 0
    away_l = away_stats.get("losses") or 0
    home_win_pct = home_w / max(home_w + home_l, 1)
    away_win_pct = away_w / max(away_w + away_l, 1)

    d_rest = _diff_vals(home_rest, away_rest)

    features = {
        "game_id":   game_id,
        "game_date": game_date,
        "sport":     "WNBA",
        "season":    season,
        "home_team": home_team,
        "away_team": away_team,
        "is_early_season": is_early,

        # Differentials
        "d_off_rating":        diff("off_rating"),
        "d_def_rating":        diff("def_rating"),
        "d_net_rating":        d_net,
        "d_pace":              diff("pace"),
        "d_efg_pct":           diff("efg_pct"),
        "d_fg3_pct":           diff("fg3_pct"),
        "d_ft_pct":            diff("ft_pct"),
        "d_reb_per_game":      diff("reb_per_game"),
        "d_ast_per_game":      diff("ast_per_game"),
        "d_tov_pct":           diff("tov_pct"),
        "d_points_per_game":   diff("points_per_game"),
        "d_points_allowed_pg": diff("points_allowed_pg"),
        "d_points_last_3":     _diff_vals(home_pts_l3, away_pts_l3),
        "d_points_last_5":     _diff_vals(home_pts_l5, away_pts_l5),
        "d_point_differential": diff("point_differential"),

        # Absolutes (totals)
        "home_points_per_game":   home_stats.get("points_per_game"),
        "away_points_per_game":   away_stats.get("points_per_game"),
        "home_points_allowed_pg": home_stats.get("points_allowed_pg"),
        "away_points_allowed_pg": away_stats.get("points_allowed_pg"),
        "home_pace":              home_stats.get("pace"),
        "away_pace":              away_stats.get("pace"),
        "home_off_rating":        home_stats.get("off_rating"),
        "away_off_rating":        away_stats.get("off_rating"),
        "home_def_rating":        home_stats.get("def_rating"),
        "away_def_rating":        away_stats.get("def_rating"),
        "home_efg_pct":           home_stats.get("efg_pct"),
        "away_efg_pct":           away_stats.get("efg_pct"),
        "home_points_last_5":     home_pts_l5,
        "away_points_last_5":     away_pts_l5,

        # Win context
        "home_win_pct": round(home_win_pct, 4),
        "away_win_pct": round(away_win_pct, 4),

        # Rest / schedule
        "d_rest_days": d_rest,
        "home_b2b":    int(home_rest == 1) if home_rest is not None else 0,
        "away_b2b":    int(away_rest == 1) if away_rest is not None else 0,

        # Injuries (shared helpers)
        "home_injury_adj":   _compute_injury_adjustment(home_inj),
        "away_injury_adj":   _compute_injury_adjustment(away_inj),
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


# ── Live scoring path (per-game DB lookups) ────────────────────────────────────

def _get_wnba_team_stats(conn: DBConnection, team: str, season: int,
                         as_of_date: str) -> dict:
    cols = [
        "games_played", "points_per_game", "points_allowed_pg", "pace",
        "off_rating", "def_rating", "efg_pct", "fg_pct", "fg3_pct", "ft_pct",
        "reb_per_game", "ast_per_game", "tov_pct", "points_last_3", "points_last_5",
        "points_home", "points_away", "wins", "losses", "point_differential",
    ]
    sel = ", ".join(cols)
    row = conn.execute(f"""
        SELECT {sel} FROM wnba_team_stats
        WHERE team = ? AND season = ? AND as_of_date <= ?
        ORDER BY as_of_date DESC LIMIT 1
    """, (team, season, as_of_date)).fetchone()
    if row:
        return dict(zip(cols, row))
    # Prior-season fallback
    row_prev = conn.execute(f"""
        SELECT {sel} FROM wnba_team_stats
        WHERE team = ? AND season = ?
        ORDER BY as_of_date DESC LIMIT 1
    """, (team, season - 1)).fetchone()
    return dict(zip(cols, row_prev)) if row_prev else {}


def _rolling_points_live(conn: DBConnection, team: str, as_of_date: str,
                         window: int) -> float | None:
    rows = conn.execute("""
        SELECT CASE WHEN home_team = ? THEN home_score ELSE away_score END AS pts
        FROM games
        WHERE sport = 'WNBA'
          AND (home_team = ? OR away_team = ?)
          AND game_date < ?
          AND home_score IS NOT NULL
        ORDER BY game_date DESC
        LIMIT ?
    """, (team, team, team, as_of_date, window)).fetchall()
    pts = [r[0] for r in rows if r[0] is not None]
    return round(float(np.mean(pts)), 2) if len(pts) >= 3 else None


def _rest_days_live(conn: DBConnection, team: str, as_of_date: str) -> int | None:
    row = conn.execute("""
        SELECT game_date FROM games
        WHERE sport = 'WNBA'
          AND (home_team = ? OR away_team = ?)
          AND game_date < ?
          AND home_score IS NOT NULL
        ORDER BY game_date DESC LIMIT 1
    """, (team, team, as_of_date)).fetchone()
    if not row:
        return None
    try:
        d0 = datetime.strptime(row[0], "%Y-%m-%d")
        d1 = datetime.strptime(as_of_date, "%Y-%m-%d")
        return (d1 - d0).days
    except (ValueError, TypeError):
        return None


def build_wnba_game_features(conn: DBConnection, game_id: str, game_date: str,
                             home_team: str, away_team: str, season: int,
                             odds_row: dict = None) -> dict:
    """Build the full feature row for one WNBA game (live scoring path)."""
    from data.ingestors.injury_ingestor import query_injuries_for_game

    home_stats = _get_wnba_team_stats(conn, home_team, season, game_date)
    away_stats = _get_wnba_team_stats(conn, away_team, season, game_date)

    injuries = query_injuries_for_game(conn, "WNBA", home_team, away_team, game_date)
    home_inj = injuries["home_injuries"]
    away_inj = injuries["away_injuries"]

    return _assemble_wnba_features(
        game_id, game_date, home_team, away_team, season,
        home_stats, away_stats,
        _rolling_points_live(conn, home_team, game_date, 3),
        _rolling_points_live(conn, home_team, game_date, 5),
        _rolling_points_live(conn, away_team, game_date, 3),
        _rolling_points_live(conn, away_team, game_date, 5),
        _rest_days_live(conn, home_team, game_date),
        _rest_days_live(conn, away_team, game_date),
        home_inj, away_inj, odds_row,
    )


# ── Bulk training/backtest path ────────────────────────────────────────────────

def build_bulk_wnba_lookups(conn: DBConnection, seasons: list[int]) -> dict:
    """Bulk-load WNBA tables for fast in-memory ASOF lookups (training/backtest)."""
    all_seasons  = sorted(set(seasons))
    load_seasons = list(range(min(all_seasons) - 1, max(all_seasons) + 2))
    sp_load = ','.join(['%s'] * len(load_seasons))

    # ── Team stats ─────────────────────────────────────────────────────────────
    ts_cols = [
        "team", "season", "as_of_date", "games_played",
        "points_per_game", "points_allowed_pg", "pace", "off_rating", "def_rating",
        "efg_pct", "fg_pct", "fg3_pct", "ft_pct", "reb_per_game", "ast_per_game",
        "tov_pct", "points_last_3", "points_last_5", "points_home", "points_away",
        "wins", "losses", "point_differential",
    ]
    ts_rows = conn.execute(f"""
        SELECT {', '.join(ts_cols)}
        FROM wnba_team_stats WHERE season IN ({sp_load})
        ORDER BY team, season, as_of_date
    """, load_seasons).fetchall()
    team_stats: dict = {}
    for r in ts_rows:
        d = dict(zip(ts_cols, r))
        k = (d['team'], d['season'])
        if k not in team_stats:
            team_stats[k] = ([], [])
        team_stats[k][0].append(d['as_of_date'])
        team_stats[k][1].append(d)

    # ── Rolling points + rest from games ───────────────────────────────────────
    hist_rows = conn.execute("""
        SELECT game_date, home_team, away_team, home_score, away_score
        FROM games WHERE sport = 'WNBA' AND home_score IS NOT NULL
        ORDER BY game_date
    """).fetchall()
    points: dict = {}      # team → (sorted dates, points scored)
    play_dates: dict = {}  # team → sorted list of game dates (for rest)
    for gdate, ht, at, hs, as_ in hist_rows:
        if hs is not None:
            points.setdefault(ht, ([], []))[0].append(gdate)
            points[ht][1].append(float(hs))
            play_dates.setdefault(ht, []).append(gdate)
        if as_ is not None:
            points.setdefault(at, ([], []))[0].append(gdate)
            points[at][1].append(float(as_))
            play_dates.setdefault(at, []).append(gdate)
    for t in play_dates:
        play_dates[t].sort()

    # ── Injuries ───────────────────────────────────────────────────────────────
    inj_cols = ['team', 'report_date', 'scenario', 'severity_weight',
                'return_ramp_factor', 'status']
    inj_rows = conn.execute("""
        SELECT team, report_date, scenario, severity_weight, return_ramp_factor, status
        FROM injuries WHERE sport = 'WNBA'
        ORDER BY team, report_date
    """).fetchall()
    injuries: dict = {}
    inj_dates: dict = {}
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

    # ── Odds ───────────────────────────────────────────────────────────────────
    o_cols = ['game_id', 'market', 'home_price', 'away_price', 'draw_price',
              'spread_home', 'total_line', 'over_price', 'under_price',
              'snapshot_type', 'snapshot_at']
    o_rows = conn.execute("""
        SELECT o.game_id, o.market, o.home_price, o.away_price, o.draw_price,
               o.spread_home, o.total_line, o.over_price, o.under_price,
               o.snapshot_type, o.snapshot_at
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'WNBA'
          AND o.bookmaker IN ('draftkings', 'sbr_consensus')
        ORDER BY o.game_id, o.market,
                 CASE o.bookmaker WHEN 'draftkings' THEN 0 ELSE 1 END,
                 o.snapshot_at DESC
    """).fetchall()
    odds_lookup: dict = {}
    for r in o_rows:
        d = dict(zip(o_cols, r))
        k = (d['game_id'], d['market'])
        if k not in odds_lookup:
            odds_lookup[k] = d

    logger.debug(
        f"WNBA bulk loads: {len(ts_rows)} team-stat rows, {len(hist_rows)} hist games, "
        f"{len(inj_rows)} injury rows, {len(o_rows)} odds rows"
    )

    return dict(team_stats=team_stats, points=points, play_dates=play_dates,
                injuries=injuries, inj_dates=inj_dates, odds=odds_lookup)


def _blk_wnba_team_stats(bulk: dict, team: str, season: int, game_date: str) -> dict:
    ts = bulk['team_stats']
    for s in (season, season - 1):
        k = (team, s)
        if k in ts:
            dates, stats = ts[k]
            idx = bisect.bisect_right(dates, game_date) - 1
            if idx >= 0:
                return stats[idx]
    return {}


def _blk_wnba_rolling_points(bulk: dict, team: str, game_date: str,
                             window: int) -> float | None:
    if team not in bulk['points']:
        return None
    dates, pts = bulk['points'][team]
    hi = bisect.bisect_left(dates, game_date)
    recent = pts[max(0, hi - window):hi]
    return round(float(np.mean(recent)), 2) if len(recent) >= 3 else None


def _blk_wnba_rest(bulk: dict, team: str, game_date: str) -> int | None:
    if team not in bulk['play_dates']:
        return None
    return _rest_days(bulk['play_dates'][team], game_date)


def _blk_wnba_injuries(bulk: dict, team: str, game_date: str) -> list:
    if team not in bulk['inj_dates']:
        return []
    dates = bulk['inj_dates'][team]
    idx = bisect.bisect_right(dates, game_date) - 1
    if idx < 0:
        return []
    return bulk['injuries'][team].get(dates[idx], [])


def build_wnba_features_from_bulk(bulk: dict, game_id: str, game_date: str,
                                  home_team: str, away_team: str, season: int,
                                  odds_row: dict | None) -> dict:
    """Build a WNBA feature row from pre-loaded bulk data (training/backtest)."""
    return _assemble_wnba_features(
        game_id, game_date, home_team, away_team, season,
        _blk_wnba_team_stats(bulk, home_team, season, game_date),
        _blk_wnba_team_stats(bulk, away_team, season, game_date),
        _blk_wnba_rolling_points(bulk, home_team, game_date, 3),
        _blk_wnba_rolling_points(bulk, home_team, game_date, 5),
        _blk_wnba_rolling_points(bulk, away_team, game_date, 3),
        _blk_wnba_rolling_points(bulk, away_team, game_date, 5),
        _blk_wnba_rest(bulk, home_team, game_date),
        _blk_wnba_rest(bulk, away_team, game_date),
        _blk_wnba_injuries(bulk, home_team, game_date),
        _blk_wnba_injuries(bulk, away_team, game_date),
        odds_row,
    )

"""
ncaaf_feature_engine.py — NCAAF game features (spread / totals / moneyline).

Mirrors nba_feature_engine.py structurally:
  • build_ncaaf_game_features       — live scoring (per-game DB lookups)
  • build_bulk_ncaaf_lookups        — bulk-load for training/backtest
  • build_ncaaf_features_from_bulk  — fast in-memory ASOF lookups

Feature lists (NCAAF_H2H_FEATURES / NCAAF_TOTALS_FEATURES /
NCAAF_SPREAD_FEATURES) and the FEATURE_MAP entries live in feature_engine.py
alongside every other sport; the dispatcher calls in here.

Data sources
    ncaaf_team_stats      — ASOF snapshots already shrunk toward the prior
                            season by the ingestor (see cfbd_ingestor)
    games (sport='NCAAF')  — rolling form, rest days, and the schedule context
                            (week / neutral site / conference game)

────────────────────────────────────────────────────────────────────────────
TWO THINGS HERE ARE LOAD-BEARING
────────────────────────────────────────────────────────────────────────────
1. FBS GATE. build_*_features returns None when either team has no
   ncaaf_team_stats row. An FCS opponent has no row by construction, so
   FBS-vs-FCS games are excluded from both training and scoring without a
   separate classification check. Returning None (rather than a row of nulls)
   makes the skip explicit at score time instead of silently producing a
   feature vector the model was never trained on.

2. BOWL EXCLUSION. Bowls and the playoff are flagged `is_bowl` and dropped
   from TRAINING: opt-outs, interim coaches and month-long layoffs make them a
   different sport. They are still ingested and still settle — they are simply
   not learned from, and not bet in v1.

Injuries are deliberately absent. College injury reporting is voluntary and
unreliable; wiring it in now would add noise, not signal. Revisit once the
model validates.
"""

import bisect
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from data.db import DBConnection
from features.feature_engine import _is_pregame_snapshot

SPORT = "NCAAF"

# Regular-season weeks run 1..15ish; anything in the postseason season_type or
# played after this cutoff week is treated as a bowl.
_BOWL_WEEK_FLOOR = 16

# When a team has no prior game (season opener) both sides are equally rested,
# so the differential is genuinely 0 — not a fabricated fill. Without this,
# every week-1 row would carry a null and be dropped from the matrix.
_DEFAULT_REST_DAYS = 7


def _rest_days(prior_dates: list[str], game_date: str) -> int | None:
    idx = bisect.bisect_left(prior_dates, game_date)
    if idx == 0:
        return None
    try:
        d0 = datetime.strptime(prior_dates[idx - 1], "%Y-%m-%d")
        d1 = datetime.strptime(game_date, "%Y-%m-%d")
        return (d1 - d0).days
    except (ValueError, TypeError):
        return None


def is_bowl_game(week: int | None, season_type: str | None,
                 game_date: str | None, season: int | None) -> int:
    """
    True for bowls and the playoff.

    Three independent signals because none is reliable alone: an explicit
    postseason season_type, a week past the regular-season floor, or a
    January/February date (which by our season convention is always postseason).
    """
    if season_type and str(season_type).lower().startswith("post"):
        return 1
    if week is not None and week >= _BOWL_WEEK_FLOOR:
        return 1
    if game_date and season is not None:
        try:
            if int(game_date[:4]) > int(season):
                return 1
        except (ValueError, TypeError):
            pass
    return 0


# ── Shared row assembly (live + bulk both land here) ──────────────────────────

def _assemble_ncaaf_features(game_id: str, game_date: str,
                             home_team: str, away_team: str, season: int,
                             home_stats: dict, away_stats: dict,
                             home_pts_l3: float | None, away_pts_l3: float | None,
                             home_rest: int | None, away_rest: int | None,
                             sched: dict, odds_row: dict | None) -> dict | None:
    # FBS gate — see the module docstring.
    if not home_stats or not away_stats:
        return None

    def diff(key: str):
        h, a = home_stats.get(key), away_stats.get(key)
        if h is None or a is None:
            return None
        return round(float(h) - float(a), 6)

    def diff_vals(h, a):
        return round(float(h) - float(a), 6) if (h is not None and a is not None) else None

    def gp(s: dict) -> int:
        return int(s.get("games_played") or 0)

    def win_pct(s: dict) -> float:
        w, l = int(s.get("wins") or 0), int(s.get("losses") or 0)
        return round(w / max(w + l, 1), 4)

    week = sched.get("week")
    features = {
        "game_id":   game_id,
        "game_date": game_date,
        "sport":     SPORT,
        "season":    season,
        "home_team": home_team,
        "away_team": away_team,

        # Program strength — prior-season ratings, the backbone in a 12-game sport
        "d_sp_overall":  diff("sp_overall"),
        "d_sp_offense":  diff("sp_offense"),
        "d_sp_defense":  diff("sp_defense"),
        "d_srs":         diff("srs"),
        "d_talent":      diff("talent"),

        # Efficiency (already shrunk toward the prior season by the ingestor)
        "d_epa_per_play_off":  diff("epa_per_play_off"),
        "d_epa_per_play_def":  diff("epa_per_play_def"),
        "d_success_rate_off":  diff("success_rate_off"),
        "d_success_rate_def":  diff("success_rate_def"),
        "d_explosiveness_off": diff("explosiveness_off"),

        # Tempo — the dominant totals signal in college football
        "d_plays_per_game": diff("plays_per_game"),

        # Scoring / form
        "d_points_per_game":    diff("points_per_game"),
        "d_points_allowed_pg":  diff("points_allowed_pg"),
        "d_point_differential": diff("point_differential"),
        "d_points_last_3":      diff_vals(home_pts_l3, away_pts_l3),

        "home_win_pct": win_pct(home_stats),
        "away_win_pct": win_pct(away_stats),

        # Absolutes for the totals model
        "home_points_per_game":   home_stats.get("points_per_game"),
        "away_points_per_game":   away_stats.get("points_per_game"),
        "home_points_allowed_pg": home_stats.get("points_allowed_pg"),
        "away_points_allowed_pg": away_stats.get("points_allowed_pg"),
        "home_plays_per_game":    home_stats.get("plays_per_game"),
        "away_plays_per_game":    away_stats.get("plays_per_game"),
        "home_epa_per_play_off":  home_stats.get("epa_per_play_off"),
        "away_epa_per_play_off":  away_stats.get("epa_per_play_off"),
        "home_epa_per_play_def":  home_stats.get("epa_per_play_def"),
        "away_epa_per_play_def":  away_stats.get("epa_per_play_def"),
        "home_sp_offense":        home_stats.get("sp_offense"),
        "away_sp_offense":        away_stats.get("sp_offense"),
        "home_sp_defense":        home_stats.get("sp_defense"),
        "away_sp_defense":        away_stats.get("sp_defense"),

        # Schedule context
        "d_rest_days": diff_vals(
            home_rest if home_rest is not None else _DEFAULT_REST_DAYS,
            away_rest if away_rest is not None else _DEFAULT_REST_DAYS),
        "week":                int(week) if week is not None else 0,
        "is_neutral_site":     int(sched.get("neutral_site") or 0),
        "is_conference_game":  int(sched.get("conference_game") or 0),
        # P4-vs-P4 games are priced as sharply as the NFL; midweek G5 numbers
        # are soft. Thresholds are expected to differ by tier.
        "game_tier":           _game_tier(home_stats, away_stats),
        # FLAGGED, not gated: a >=10-game rule (the MLB convention) would blank
        # three quarters of a 12-game season. The ingestor's prior-shrinkage is
        # what actually makes these rows usable.
        "is_early_season": int(gp(home_stats) < config.NCAAF_MIN_GAMES
                               or gp(away_stats) < config.NCAAF_MIN_GAMES),
        "is_bowl": is_bowl_game(week, sched.get("season_type"), game_date, season),
    }

    features["total_line"]  = (odds_row or {}).get("total_line")
    features["spread_home"] = (odds_row or {}).get("spread_home")
    return features


def _game_tier(home_stats: dict, away_stats: dict) -> int:
    """2 = both Power-4, 1 = mixed, 0 = neither."""
    p4 = config.NCAAF_POWER_CONFERENCES
    return int(home_stats.get("conference") in p4) + int(away_stats.get("conference") in p4)


_STAT_COLS = [
    "games_played", "sp_overall", "sp_offense", "sp_defense", "srs", "talent",
    "epa_per_play_off", "epa_per_play_def", "success_rate_off", "success_rate_def",
    "explosiveness_off", "plays_per_game", "points_per_game", "points_allowed_pg",
    "points_last_3", "point_differential", "wins", "losses", "conference",
]


# ── Live scoring path ─────────────────────────────────────────────────────────

def _get_ncaaf_team_stats(conn: DBConnection, team: str, season: int,
                          as_of_date: str) -> dict:
    sel = ", ".join(_STAT_COLS)
    row = conn.execute(f"""
        SELECT {sel} FROM ncaaf_team_stats
        WHERE team = ? AND season = ? AND as_of_date <= ?
        ORDER BY as_of_date DESC LIMIT 1
    """, (team, season, as_of_date)).fetchone()
    if row:
        return dict(zip(_STAT_COLS, row))
    # Prior-season fallback keeps a team scoreable if this season's snapshots
    # have not been built yet (e.g. a mid-week manual run before the refresh).
    prev = conn.execute(f"""
        SELECT {sel} FROM ncaaf_team_stats
        WHERE team = ? AND season = ?
        ORDER BY as_of_date DESC LIMIT 1
    """, (team, season - 1)).fetchone()
    return dict(zip(_STAT_COLS, prev)) if prev else {}


def _rolling_points_live(conn: DBConnection, team: str, as_of_date: str,
                         window: int = 3) -> float | None:
    rows = conn.execute("""
        SELECT CASE WHEN home_team = ? THEN home_score ELSE away_score END AS pts
        FROM games
        WHERE sport = 'NCAAF' AND (home_team = ? OR away_team = ?)
          AND game_date < ? AND home_score IS NOT NULL
        ORDER BY game_date DESC LIMIT ?
    """, (team, team, team, as_of_date, window)).fetchall()
    pts = [r[0] for r in rows if r[0] is not None]
    return round(float(np.mean(pts)), 2) if pts else None


def _rest_days_live(conn: DBConnection, team: str, as_of_date: str) -> int | None:
    row = conn.execute("""
        SELECT game_date FROM games
        WHERE sport = 'NCAAF' AND (home_team = ? OR away_team = ?)
          AND game_date < ? AND home_score IS NOT NULL
        ORDER BY game_date DESC LIMIT 1
    """, (team, team, as_of_date)).fetchone()
    return _rest_days([row[0]], as_of_date) if row else None


def build_ncaaf_game_features(conn: DBConnection, game_id: str, game_date: str,
                              home_team: str, away_team: str, season: int,
                              odds_row: dict = None) -> dict | None:
    """Full feature row for one NCAAF game (live scoring path)."""
    home_stats = _get_ncaaf_team_stats(conn, home_team, season, game_date)
    away_stats = _get_ncaaf_team_stats(conn, away_team, season, game_date)
    if not home_stats or not away_stats:
        logger.debug(f"{game_id}: missing NCAAF stats (likely an FCS opponent) — skipping")
        return None

    row = conn.execute("""
        SELECT week, neutral_site, conference_game FROM games WHERE game_id = ?
    """, (game_id,)).fetchone()
    sched = dict(zip(("week", "neutral_site", "conference_game"), row)) if row else {}

    return _assemble_ncaaf_features(
        game_id, game_date, home_team, away_team, season,
        home_stats, away_stats,
        _rolling_points_live(conn, home_team, game_date),
        _rolling_points_live(conn, away_team, game_date),
        _rest_days_live(conn, home_team, game_date),
        _rest_days_live(conn, away_team, game_date),
        sched, odds_row,
    )


# ── Bulk training/backtest path ───────────────────────────────────────────────

def build_bulk_ncaaf_lookups(conn: DBConnection, seasons: list[int]) -> dict:
    """Bulk-load every NCAAF table in a handful of queries for ASOF lookups."""
    all_seasons  = sorted(set(seasons))
    load_seasons = list(range(min(all_seasons) - 1, max(all_seasons) + 2))
    ph = ",".join(["%s"] * len(load_seasons))

    cols = ["team", "season", "as_of_date"] + _STAT_COLS
    ts_rows = conn.execute(f"""
        SELECT {', '.join(cols)} FROM ncaaf_team_stats
        WHERE season IN ({ph}) ORDER BY team, season, as_of_date
    """, load_seasons).fetchall()
    team_stats: dict = {}
    for r in ts_rows:
        d = dict(zip(cols, r))
        k = (d["team"], d["season"])
        team_stats.setdefault(k, ([], []))
        team_stats[k][0].append(d["as_of_date"])
        team_stats[k][1].append(d)

    # Rolling form + rest come from COMPLETED games only...
    hist = conn.execute("""
        SELECT game_date, home_team, away_team, home_score, away_score
        FROM games WHERE sport = 'NCAAF' AND home_score IS NOT NULL
        ORDER BY game_date
    """).fetchall()
    points: dict = {}
    play_dates: dict = {}
    for gdate, ht, at, hs, as_ in hist:
        for team, pts in ((ht, hs), (at, as_)):
            if pts is None:
                continue
            points.setdefault(team, ([], []))[0].append(gdate)
            points[team][1].append(float(pts))
            play_dates.setdefault(team, []).append(gdate)
    for t in play_dates:
        play_dates[t].sort()

    # ...but schedule context is loaded for EVERY game, played or not. Keying it
    # off the completed-games query would leave an unplayed game with no week /
    # neutral-site / conference flag, so a backtest or look-ahead scoring pass
    # would silently treat a neutral-site game as a home game.
    sched = {r[0]: {"week": r[1], "neutral_site": r[2], "conference_game": r[3]}
             for r in conn.execute("""
        SELECT game_id, week, neutral_site, conference_game
        FROM games WHERE sport = 'NCAAF'
    """).fetchall()}

    # Historical lines land as cfbd_consensus; live DK rows are also accepted so
    # an in-season backtest can use whichever exists. The DraftKings-only
    # invariant is untouched — that governs SCORING, and this is training data.
    o_cols = ["game_id", "market", "home_price", "away_price", "spread_home",
              "total_line", "over_price", "under_price", "snapshot_at", "commence_time"]
    o_rows = conn.execute(f"""
        SELECT o.game_id, o.market, o.home_price, o.away_price, o.spread_home,
               o.total_line, o.over_price, o.under_price, o.snapshot_at, g.commence_time
        FROM odds o JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'NCAAF'
          AND o.bookmaker IN ('draftkings', %s)
          AND o.snapshot_type != 'in_play'
        ORDER BY o.game_id, o.market,
                 CASE o.bookmaker WHEN %s THEN 0 ELSE 1 END,
                 o.snapshot_at ASC
    """, [config.CFBD_LINES_BOOKMAKER, config.CFBD_LINES_BOOKMAKER]).fetchall()
    odds_lookup: dict = {}
    for r in o_rows:
        d = dict(zip(o_cols, r))
        if not _is_pregame_snapshot(d["snapshot_at"], d["commence_time"]):
            continue
        odds_lookup.setdefault((d["game_id"], d["market"]), d)

    logger.debug(f"NCAAF bulk loads: {len(ts_rows)} stat rows, {len(hist)} games, "
                 f"{len(o_rows)} odds rows")
    return dict(team_stats=team_stats, points=points, play_dates=play_dates,
                sched=sched, odds=odds_lookup)


def _blk_stats(bulk: dict, team: str, season: int, game_date: str) -> dict:
    ts = bulk["team_stats"]
    for s in (season, season - 1):
        k = (team, s)
        if k in ts:
            dates, rows = ts[k]
            idx = bisect.bisect_right(dates, game_date) - 1
            if idx >= 0:
                return rows[idx]
    return {}


def _blk_points_l3(bulk: dict, team: str, game_date: str) -> float | None:
    if team not in bulk["points"]:
        return None
    dates, pts = bulk["points"][team]
    hi = bisect.bisect_left(dates, game_date)
    recent = pts[max(0, hi - 3):hi]
    return round(float(np.mean(recent)), 2) if recent else None


def build_ncaaf_features_from_bulk(bulk: dict, game_id: str, game_date: str,
                                   home_team: str, away_team: str, season: int,
                                   odds_row: dict | None) -> dict | None:
    home_stats = _blk_stats(bulk, home_team, season, game_date)
    away_stats = _blk_stats(bulk, away_team, season, game_date)
    if not home_stats or not away_stats:
        return None                       # FBS gate
    hd = bulk["play_dates"].get(home_team, [])
    ad = bulk["play_dates"].get(away_team, [])
    return _assemble_ncaaf_features(
        game_id, game_date, home_team, away_team, season,
        home_stats, away_stats,
        _blk_points_l3(bulk, home_team, game_date),
        _blk_points_l3(bulk, away_team, game_date),
        _rest_days(hd, game_date), _rest_days(ad, game_date),
        bulk["sched"].get(game_id, {}), odds_row,
    )

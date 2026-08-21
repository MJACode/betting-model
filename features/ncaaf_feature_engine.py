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
1. FBS GATE. build_*_features returns None unless BOTH teams are FBS (see
   _is_fbs). Row existence alone is not the test: CFBD's ratings and talent
   endpoints cover FCS programs, so the backfill writes snapshots for them too.
   Returning None rather than a row of nulls makes the skip explicit at score
   time instead of silently pricing a game off a feature vector the model was
   never trained on.

2. BOWL EXCLUSION. Bowls and the playoff are flagged `is_bowl` and dropped
   from TRAINING: opt-outs, interim coaches and month-long layoffs make them a
   different sport. They are still ingested and still settle — they are simply
   not learned from, and not bet in v1.

Injuries are deliberately absent. College injury reporting is voluntary and
unreliable; wiring it in now would add noise, not signal. Revisit once the
model validates.
"""

import bisect
import math
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


def _is_fbs(stats: dict) -> bool:
    """
    Is this snapshot an FBS team?

    Mere row EXISTENCE is not enough. CFBD's ratings and talent endpoints cover
    FCS programs too, so the backfill writes snapshots for them — 162 such teams
    in our data, none of which we can model. Verified against the loaded data:
    every one of those rows is missing sp_overall (SP+ is FBS-only), so SP+ is
    itself proof of FBS membership and serves as the fallback when the
    classification column was never populated.

    Training was already protected by dropna; this protects LIVE SCORING, which
    would otherwise happily price an FBS-vs-FCS game off a row of nulls.
    """
    if not stats:
        return False
    cls = stats.get("classification")
    if cls is not None:
        return str(cls).lower() == "fbs"
    return stats.get("sp_overall") is not None


# ══════════════════════════════════════════════════════════════════════════════
# Situational geography — the features the market prices LEAST efficiently
# ══════════════════════════════════════════════════════════════════════════════
# The v1 feature set was almost entirely team-strength differentials, which is
# exactly what a closing spread already encodes — hence AUC ~0.49. These
# features are deliberately ORTHOGONAL to team strength: where the game is
# played, how far the visitor came, and how much this specific venue is worth.

_EARTH_RADIUS_MI = 3958.8

# League-average home-field edge in points, used as the shrinkage prior for a
# team's own measured HFA. ~2.5 is the long-run CFB consensus and our own data
# agrees (home teams win 63.75% of games).
LEAGUE_HFA_POINTS = 2.5
HFA_SHRINKAGE_K = 20          # home games before a team's own HFA outweighs the prior


def haversine_miles(lat1, lon1, lat2, lon2) -> float | None:
    """Great-circle distance in miles. None if any coordinate is missing."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = p2 - p1
    dlam = math.radians(float(lon2) - float(lon1))
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2)
    return round(2 * _EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(a))), 1)


def tz_offset_from_lon(lon) -> float | None:
    """
    Approximate timezone offset (hours from UTC) from longitude.

    Deliberately geometric rather than a timezone database: what matters for a
    body clock is solar time, and the continental US has no longitude where the
    15-degree approximation is off by more than an hour. Avoids a dependency
    and a per-venue lookup table for a feature measured in whole hours.
    """
    return None if lon is None else round(float(lon) / 15.0, 2)


def shrink_hfa(home_margin_avg, away_margin_avg, home_games: int) -> float:
    """
    A team's own home-field advantage in points, shrunk toward the league mean.

    HFA is not uniform: altitude, crowd, travel burden on visitors and surface
    make some venues worth several points more than others. But a single season
    of home games is far too few to measure it, so this blends the observed
    split with LEAGUE_HFA_POINTS by games played — the same prior-shrinkage
    logic the ingestor applies to rate stats, for the same reason.
    """
    if home_margin_avg is None or away_margin_avg is None:
        return LEAGUE_HFA_POINTS
    observed = float(home_margin_avg) - float(away_margin_avg)
    n = max(int(home_games or 0), 0)
    w = n / (n + HFA_SHRINKAGE_K)
    return round(w * observed + (1 - w) * LEAGUE_HFA_POINTS, 4)


def _venue_features(venue: dict, home_venue: dict, away_venue: dict,
                    neutral: int) -> dict:
    """
    Travel, altitude, surface and crowd for one game.

    At a normal home game the host travels zero by construction; at a neutral
    site BOTH teams travel, which is precisely when these features carry the
    most information and when a naive is_home flag carries the least.
    """
    v_lat, v_lon = (venue or {}).get("latitude"), (venue or {}).get("longitude")
    v_elev = (venue or {}).get("elevation_ft")

    def trip(team_venue: dict, is_host: bool):
        if not neutral and is_host:
            return 0.0, 0.0, 0.0
        miles = haversine_miles(team_venue.get("latitude"), team_venue.get("longitude"),
                                v_lat, v_lon)
        t_from = tz_offset_from_lon(team_venue.get("longitude"))
        t_to   = tz_offset_from_lon(v_lon)
        tz = round(t_to - t_from, 2) if (t_from is not None and t_to is not None) else None
        home_elev = team_venue.get("elevation_ft")
        climb = (round(float(v_elev) - float(home_elev), 1)
                 if (v_elev is not None and home_elev is not None) else None)
        return miles, tz, climb

    h_miles, h_tz, h_climb = trip(home_venue or {}, True)
    a_miles, a_tz, a_climb = trip(away_venue or {}, False)

    def _d(x, y):
        return round(float(x) - float(y), 2) if (x is not None and y is not None) else None

    return {
        "venue_elevation_ft":  v_elev,
        "is_dome_game":        int(bool((venue or {}).get("dome"))) if venue else 0,
        "is_grass":            int(bool((venue or {}).get("grass"))) if venue else 0,
        "venue_capacity":      (venue or {}).get("capacity"),
        "travel_miles_home":   h_miles,
        "travel_miles_away":   a_miles,
        "d_travel_miles":      _d(a_miles, h_miles),
        # Signed: positive means the visitor moved EAST, which costs a body
        # clock more than moving west for a night kickoff.
        "tz_shift_away":       a_tz,
        "d_altitude_climb":    _d(a_climb, h_climb),
    }


# ── Shared row assembly (live + bulk both land here) ──────────────────────────

def _assemble_ncaaf_features(game_id: str, game_date: str,
                             home_team: str, away_team: str, season: int,
                             home_stats: dict, away_stats: dict,
                             home_pts_l3: float | None, away_pts_l3: float | None,
                             home_rest: int | None, away_rest: int | None,
                             sched: dict, odds_row: dict | None,
                             venue_ctx: dict | None = None,
                             home_hfa: float | None = None,
                             away_hfa: float | None = None) -> dict | None:
    # FBS gate — see the module docstring and _is_fbs.
    if not _is_fbs(home_stats) or not _is_fbs(away_stats):
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

        # Empirical, venue-specific home-field edge. is_neutral_site alone says
        # nothing about HOW MUCH a particular home field is worth; these do.
        "home_hfa": LEAGUE_HFA_POINTS if home_hfa is None else home_hfa,
        "away_hfa": LEAGUE_HFA_POINTS if away_hfa is None else away_hfa,
        "d_hfa": (round(float(home_hfa) - float(away_hfa), 4)
                  if (home_hfa is not None and away_hfa is not None) else 0.0),
    }
    features.update(venue_ctx or {})

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
    if not _is_fbs(home_stats) or not _is_fbs(away_stats):
        logger.debug(f"{game_id}: not an FBS-vs-FBS matchup — skipping")
        return None

    row = conn.execute("""
        SELECT week, neutral_site, conference_game, venue_id
        FROM games WHERE game_id = ?
    """, (game_id,)).fetchone()
    sched = dict(zip(("week", "neutral_site", "conference_game", "venue_id"), row)) if row else {}

    venue_ctx = _venue_features(
        _venue_live(conn, sched.get("venue_id")),
        _home_venue_live(conn, home_team),
        _home_venue_live(conn, away_team),
        int(sched.get("neutral_site") or 0),
    )

    return _assemble_ncaaf_features(
        game_id, game_date, home_team, away_team, season,
        home_stats, away_stats,
        _rolling_points_live(conn, home_team, game_date),
        _rolling_points_live(conn, away_team, game_date),
        _rest_days_live(conn, home_team, game_date),
        _rest_days_live(conn, away_team, game_date),
        sched, odds_row, venue_ctx,
        _hfa_live(conn, home_team, season),
        _hfa_live(conn, away_team, season),
    )


_V_COLS = ["venue_id", "latitude", "longitude", "elevation_ft", "capacity",
           "grass", "dome"]


def _venue_live(conn: DBConnection, venue_id) -> dict:
    if venue_id is None:
        return {}
    row = conn.execute(
        f"SELECT {', '.join(_V_COLS)} FROM ncaaf_venues WHERE venue_id = ?",
        (venue_id,)).fetchone()
    return dict(zip(_V_COLS, row)) if row else {}


def _home_venue_live(conn: DBConnection, team: str) -> dict:
    row = conn.execute("""
        SELECT venue_id FROM games
        WHERE sport='NCAAF' AND home_team = ? AND venue_id IS NOT NULL
          AND (neutral_site IS NULL OR neutral_site = 0)
        ORDER BY game_date DESC LIMIT 1
    """, (team,)).fetchone()
    return _venue_live(conn, row[0]) if row else {}


def _hfa_live(conn: DBConnection, team: str, season: int) -> float:
    """Empirical HFA from PRIOR seasons only — leak-free and barely moves."""
    row = conn.execute("""
        SELECT
          AVG(CASE WHEN home_team = ? THEN home_score - away_score END),
          AVG(CASE WHEN away_team = ? THEN away_score - home_score END),
          COUNT(CASE WHEN home_team = ? THEN 1 END)
        FROM games
        WHERE sport='NCAAF' AND season < ? AND home_score IS NOT NULL
          AND (neutral_site IS NULL OR neutral_site = 0)
          AND (home_team = ? OR away_team = ?)
    """, (team, team, team, season, team, team)).fetchone()
    return shrink_hfa(row[0], row[1], row[2]) if row else LEAGUE_HFA_POINTS


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
    sched = {r[0]: {"week": r[1], "neutral_site": r[2], "conference_game": r[3],
                    "venue_id": r[4]}
             for r in conn.execute("""
        SELECT game_id, week, neutral_site, conference_game, venue_id
        FROM games WHERE sport = 'NCAAF'
    """).fetchall()}

    # No single CFBD provider covers 2015-2025, so the backfill stores every
    # provider it finds and the preference is resolved HERE: the CASE below
    # ranks bookmakers by config.NCAAF_LINE_BOOKMAKER_PRIORITY and the first
    # row per (game, market) wins. Live DraftKings rows rank last — in season a
    # game has both, and the archive line is the one the historical target was
    # computed from, so preferring it keeps training and backtesting consistent.
    # The DraftKings-only invariant is untouched: that governs SCORING; this is
    # training data.
    priority = list(config.NCAAF_LINE_BOOKMAKER_PRIORITY)
    in_ph   = ",".join(["%s"] * len(priority))
    case_ph = " ".join(f"WHEN %s THEN {i}" for i in range(len(priority)))
    o_cols = ["game_id", "market", "home_price", "away_price", "spread_home",
              "total_line", "over_price", "under_price", "snapshot_at", "commence_time"]
    o_rows = conn.execute(f"""
        SELECT o.game_id, o.market, o.home_price, o.away_price, o.spread_home,
               o.total_line, o.over_price, o.under_price, o.snapshot_at, g.commence_time
        FROM odds o JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'NCAAF'
          AND o.bookmaker IN ({in_ph})
          AND o.snapshot_type != 'in_play'
        ORDER BY o.game_id, o.market,
                 CASE o.bookmaker {case_ph} ELSE {len(priority)} END,
                 o.snapshot_at ASC
    """, priority + priority).fetchall()
    odds_lookup: dict = {}
    for r in o_rows:
        d = dict(zip(o_cols, r))
        if not _is_pregame_snapshot(d["snapshot_at"], d["commence_time"]):
            continue
        odds_lookup.setdefault((d["game_id"], d["market"]), d)

    # ── Venue geography ───────────────────────────────────────────────────────
    v_cols = ["venue_id", "latitude", "longitude", "elevation_ft", "capacity",
              "grass", "dome"]
    venues = {r[0]: dict(zip(v_cols, r)) for r in conn.execute(
        f"SELECT {', '.join(v_cols)} FROM ncaaf_venues").fetchall()}

    # Each team's HOME venue = the venue of its most recent non-neutral home
    # game. Needed to measure how far the VISITOR travelled, and (at a neutral
    # site) how far both did.
    # Deliberately ANSI SQL rather than Postgres DISTINCT ON: the SQLite-backed
    # tests run this exact query, and a portable one is actually exercised
    # instead of merely being read.
    home_venue: dict = {}
    for team, vid in conn.execute("""
        SELECT g1.home_team, g1.venue_id
        FROM games g1
        WHERE g1.sport = 'NCAAF' AND g1.venue_id IS NOT NULL
          AND (g1.neutral_site IS NULL OR g1.neutral_site = 0)
          AND g1.game_date = (
              SELECT MAX(g2.game_date) FROM games g2
              WHERE g2.sport = 'NCAAF' AND g2.home_team = g1.home_team
                AND g2.venue_id IS NOT NULL
                AND (g2.neutral_site IS NULL OR g2.neutral_site = 0))
    """).fetchall():
        home_venue[team] = venues.get(vid, {})

    # ── Empirical home-field advantage, from PRIOR seasons only ───────────────
    # Prior seasons only: leak-free by construction, and HFA is a venue/program
    # property that barely moves year to year, so nothing is lost by ignoring
    # the current one.
    hfa_raw: dict = {}
    for season_, team, is_home, margin in conn.execute("""
        SELECT season, home_team, 1, home_score - away_score FROM games
        WHERE sport='NCAAF' AND home_score IS NOT NULL
          AND (neutral_site IS NULL OR neutral_site = 0)
        UNION ALL
        SELECT season, away_team, 0, away_score - home_score FROM games
        WHERE sport='NCAAF' AND home_score IS NOT NULL
          AND (neutral_site IS NULL OR neutral_site = 0)
    """).fetchall():
        if margin is None:
            continue
        d = hfa_raw.setdefault(team, {})
        e = d.setdefault(int(season_), {"h": [], "a": []})
        e["h" if is_home else "a"].append(float(margin))

    hfa: dict = {}          # (team, season) -> shrunk HFA in points
    for team, by_season in hfa_raw.items():
        seasons_sorted = sorted(by_season)
        for target in seasons_sorted:
            h, a = [], []
            for s_ in seasons_sorted:
                if s_ >= target:
                    break
                h.extend(by_season[s_]["h"])
                a.extend(by_season[s_]["a"])
            hfa[(team, target)] = shrink_hfa(
                (sum(h) / len(h)) if h else None,
                (sum(a) / len(a)) if a else None,
                len(h))

    logger.debug(f"NCAAF bulk loads: {len(ts_rows)} stat rows, {len(hist)} games, "
                 f"{len(o_rows)} odds rows, {len(venues)} venues, "
                 f"{len(hfa)} team-season HFA values")
    return dict(team_stats=team_stats, points=points, play_dates=play_dates,
                sched=sched, odds=odds_lookup, venues=venues,
                home_venue=home_venue, hfa=hfa)


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
    if not _is_fbs(home_stats) or not _is_fbs(away_stats):
        return None                       # FBS gate
    hd = bulk["play_dates"].get(home_team, [])
    ad = bulk["play_dates"].get(away_team, [])
    sched = bulk["sched"].get(game_id, {})
    venue_ctx = _venue_features(
        bulk.get("venues", {}).get(sched.get("venue_id"), {}),
        bulk.get("home_venue", {}).get(home_team, {}),
        bulk.get("home_venue", {}).get(away_team, {}),
        int(sched.get("neutral_site") or 0),
    )
    return _assemble_ncaaf_features(
        game_id, game_date, home_team, away_team, season,
        home_stats, away_stats,
        _blk_points_l3(bulk, home_team, game_date),
        _blk_points_l3(bulk, away_team, game_date),
        _rest_days(hd, game_date), _rest_days(ad, game_date),
        sched, odds_row, venue_ctx,
        bulk.get("hfa", {}).get((home_team, season)),
        bulk.get("hfa", {}).get((away_team, season)),
    )

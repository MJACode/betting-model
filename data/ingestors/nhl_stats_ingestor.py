"""
nhl_stats_ingestor.py — NHL team and goalie stats via nhl-api-py.

What it builds:
  • nhl_team_stats   — Season-to-date team offensive/defensive stats
  • nhl_goalie_stats — Per-start goalie stats for today's probable starters

Data sources:
  • nhl-api-py  — Official NHL API wrapper (standings, team stats, game logs)
  • NHL API v1  — Direct endpoints for goalie stats and game data

Usage:
    python -m data.ingestors.nhl_stats_ingestor           # today
    python -m data.ingestors.nhl_stats_ingestor --season 2024
    python -m data.ingestors.nhl_stats_ingestor --backfill 2019 2024
"""

import argparse
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
import sys

import numpy as np
import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import DB_PATH, SPORTS

# ── Safe Imports ──────────────────────────────────────────────────────────────

try:
    from nhl_api import teams as nhl_teams_api
    from nhl_api import stats as nhl_stats_api
    NHL_API_AVAILABLE = True
except ImportError:
    try:
        import nhl_api_py as nhl_teams_api
        NHL_API_AVAILABLE = True
    except ImportError:
        NHL_API_AVAILABLE = False
        logger.warning("nhl-api-py not installed — run: pip install nhl-api-py --break-system-packages")

# ── NHL API Direct Endpoints ──────────────────────────────────────────────────
# The nhl-api-py wrapper may not cover all endpoints we need,
# so we also call the NHL API directly for some data.

NHL_API_BASE = "https://api-web.nhle.com/v1"
NHL_STATS_BASE = "https://api.nhle.com/stats/rest/en"

NHL_HEADERS = {
    "User-Agent": "BettingModel/1.0 (personal research project)",
    "Accept": "application/json",
}

# ── Team Abbreviation Maps ────────────────────────────────────────────────────
# NHL API uses 3-letter triCodes that largely match ours, but a few differ.

NHL_API_ABBREV_MAP = {
    "ANA": "ANA", "ARI": "ARI", "BOS": "BOS", "BUF": "BUF",
    "CGY": "CGY", "CAR": "CAR", "CHI": "CHI", "COL": "COL",
    "CBJ": "CBJ", "DAL": "DAL", "DET": "DET", "EDM": "EDM",
    "FLA": "FLA", "LAK": "LAK", "MIN": "MIN", "MTL": "MTL",
    "NSH": "NSH", "NJD": "NJD", "NYI": "NYI", "NYR": "NYR",
    "OTT": "OTT", "PHI": "PHI", "PIT": "PIT", "SJS": "SJS",
    "SEA": "SEA", "STL": "STL", "TBL": "TBL", "TOR": "TOR",
    "UTA": "ARI",  # Utah Hockey Club — same franchise as old ARI Coyotes
    "VAN": "VAN", "VGK": "VGK", "WSH": "WSH", "WPG": "WPG",
    # Legacy
    "LA":  "LAK", "TB":  "TBL", "SJ":  "SJS", "NJ":  "NJD",
}

# All active NHL team abbreviations (our standard)
ALL_NHL_TEAMS = list(set(NHL_API_ABBREV_MAP.values()))


def _norm_nhl(abbrev: str) -> str:
    return NHL_API_ABBREV_MAP.get(abbrev.upper(), abbrev.upper())


# ── NHL Season Helpers ────────────────────────────────────────────────────────

def _nhl_season_id(season_end_year: int) -> str:
    """
    NHL API season IDs are formatted as YYYYYYYY (start+end concatenated).
    E.g., 2024 season = '20232024'
    """
    return f"{season_end_year - 1}{season_end_year}"


# ── Team Stats from NHL API ───────────────────────────────────────────────────

def _fetch_nhl_team_stats(season: int) -> dict:
    """
    Fetch NHL team stats for the season via the NHL stats REST API.
    Returns dict keyed by team abbrev.
    """
    season_id = _nhl_season_id(season)

    # Team summary stats — offensive and defensive
    url = f"{NHL_STATS_BASE}/team/summary"
    params = {
        "isAggregate": "false",
        "isGame": "false",
        "factCayenneExp": "gamesPlayed>=1",
        "cayenneExp": f"gameTypeId=2 and seasonId={season_id}",
        "sort": "points",
        "start": 0,
        "limit": 50,
    }

    try:
        resp = requests.get(url, params=params, headers=NHL_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error(f"NHL team summary API failed for {season}: {exc}")
        return {}

    team_data = {}
    for row in data.get("data", []):
        abbrev = _norm_nhl(row.get("teamAbbrev", ""))
        if not abbrev:
            continue
        team_data[abbrev] = {
            "games_played":     row.get("gamesPlayed"),
            "goals_per_game":   _safe(row.get("goalsForPerGame")),
            "goals_against_pg": _safe(row.get("goalsAgainstPerGame")),
            "shots_per_game":   _safe(row.get("shotsForPerGame")),
            "shots_against_pg": _safe(row.get("shotsAgainstPerGame")),
            "power_play_pct":   _safe(row.get("powerPlayPct")),
            "penalty_kill_pct": _safe(row.get("penaltyKillPct")),
            "wins":             row.get("wins"),
            "losses":           row.get("losses"),
            "ot_losses":        row.get("otLosses"),
            "goal_differential": _safe(row.get("goalDifferential")),
        }

    return team_data


def _fetch_nhl_advanced_stats(season: int) -> dict:
    """
    Fetch Corsi (CF%), xGF% from NHL advanced stats endpoint.
    """
    season_id = _nhl_season_id(season)
    url = f"{NHL_STATS_BASE}/team/advanced"
    params = {
        "isAggregate": "false",
        "cayenneExp": f"gameTypeId=2 and seasonId={season_id}",
        "sort": "corsiForPct",
        "start": 0,
        "limit": 50,
    }

    try:
        resp = requests.get(url, params=params, headers=NHL_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning(f"NHL advanced stats API failed for {season}: {exc}")
        return {}

    adv = {}
    for row in data.get("data", []):
        abbrev = _norm_nhl(row.get("teamAbbrev", ""))
        if not abbrev:
            continue
        adv[abbrev] = {
            "corsi_for_pct": _safe(row.get("corsiForPct")),
            "xgf_pct":       _safe(row.get("xGoalsForPct")),
            "xga_pct":       _safe(row.get("xGoalsAgainstPct")),
        }

    return adv


def _fetch_nhl_standings(season: int) -> dict:
    """
    Fetch regulation win/loss/tie breakdown from NHL standings.
    """
    try:
        # Current standings
        url = f"{NHL_API_BASE}/standings/now"
        resp = requests.get(url, headers=NHL_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning(f"NHL standings API failed: {exc}")
        return {}

    standings = {}
    for record in data.get("standings", []):
        abbrev = _norm_nhl(record.get("teamAbbrev", {}).get("default", ""))
        if not abbrev:
            continue
        standings[abbrev] = {
            "regulation_wins":   record.get("regulationWins", 0),
            "regulation_losses": record.get("regulationLosses", 0),
            "regulation_ties":   record.get("regulationTies", 0),
        }

    return standings


def _rolling_goals(conn: sqlite3.Connection, team: str, as_of_date: str,
                   window: int) -> float | None:
    """Average goals scored in last N games."""
    rows = conn.execute("""
        SELECT CASE WHEN home_team = ? THEN home_score ELSE away_score END as scored
        FROM games
        WHERE sport = 'NHL'
          AND (home_team = ? OR away_team = ?)
          AND game_date < ?
          AND home_score IS NOT NULL
        ORDER BY game_date DESC
        LIMIT ?
    """, (team, team, team, as_of_date, window)).fetchall()

    if not rows:
        return None
    scores = [r[0] for r in rows if r[0] is not None]
    return round(float(np.mean(scores)), 3) if scores else None


def _home_away_goals(conn: sqlite3.Connection, team: str, as_of_date: str,
                     location: str) -> float | None:
    col  = "home_score" if location == "home" else "away_score"
    cond = "home_team = ?" if location == "home" else "away_team = ?"
    year = as_of_date[:4]

    rows = conn.execute(f"""
        SELECT {col}
        FROM games
        WHERE sport = 'NHL'
          AND {cond}
          AND game_date >= '{int(year)-1}-10-01'
          AND game_date < ?
          AND home_score IS NOT NULL
    """, (team, as_of_date)).fetchall()

    if not rows:
        return None
    scores = [r[0] for r in rows if r[0] is not None]
    return round(float(np.mean(scores)), 3) if scores else None


def _build_nhl_team_rows(season: int, as_of_date: str,
                          conn: sqlite3.Connection) -> list[dict]:
    """Combine all NHL team stat sources into mlb_team_stats rows."""
    basic    = _fetch_nhl_team_stats(season)
    advanced = _fetch_nhl_advanced_stats(season)
    standings = _fetch_nhl_standings(season)

    rows = []
    all_teams = set(basic.keys()) | set(advanced.keys()) | set(standings.keys())

    for team in all_teams:
        b = basic.get(team, {})
        a = advanced.get(team, {})
        s = standings.get(team, {})

        row = {
            "team":             team,
            "season":           season,
            "as_of_date":       as_of_date,
            "games_played":     b.get("games_played"),
            "goals_per_game":   b.get("goals_per_game"),
            "shots_per_game":   b.get("shots_per_game"),
            "corsi_for_pct":    a.get("corsi_for_pct"),
            "xgf_pct":          a.get("xgf_pct"),
            "power_play_pct":   b.get("power_play_pct"),
            "goals_against_pg": b.get("goals_against_pg"),
            "shots_against_pg": b.get("shots_against_pg"),
            "penalty_kill_pct": b.get("penalty_kill_pct"),
            "xga_pct":          a.get("xga_pct"),
            "wins":             b.get("wins"),
            "losses":           b.get("losses"),
            "ot_losses":        b.get("ot_losses"),
            "goal_differential": b.get("goal_differential"),
            "regulation_wins":   s.get("regulation_wins"),
            "regulation_losses": s.get("regulation_losses"),
            "regulation_ties":   s.get("regulation_ties"),
        }

        # Rolling windows from games table
        row["goals_last_5"]  = _rolling_goals(conn, team, as_of_date, 5)
        row["goals_last_10"] = _rolling_goals(conn, team, as_of_date, 10)
        row["goals_home"]    = _home_away_goals(conn, team, as_of_date, "home")
        row["goals_away"]    = _home_away_goals(conn, team, as_of_date, "away")

        rows.append(row)

    return rows


# ── Goalie Stats ──────────────────────────────────────────────────────────────

def _fetch_goalie_season_stats(season: int) -> list[dict]:
    """
    Fetch all goalie season stats from NHL stats API.
    Returns list of goalie dicts.
    """
    season_id = _nhl_season_id(season)
    url = f"{NHL_STATS_BASE}/goalie/summary"
    params = {
        "isAggregate": "false",
        "cayenneExp": f"gameTypeId=2 and seasonId={season_id}",
        "sort": "savePct",
        "start": 0,
        "limit": 200,
    }

    try:
        resp = requests.get(url, params=params, headers=NHL_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:
        logger.error(f"NHL goalie summary API failed for {season}: {exc}")
        return []


def _fetch_today_schedule(game_date: str) -> list[dict]:
    """Fetch today's NHL schedule to identify probable starters."""
    url = f"{NHL_API_BASE}/schedule/{game_date}"
    try:
        resp = requests.get(url, headers=NHL_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error(f"NHL schedule API failed for {game_date}: {exc}")
        return []

    games = []
    for game_week in data.get("gameWeek", []):
        if game_week.get("date") == game_date:
            games.extend(game_week.get("games", []))

    return games


def _build_goalie_rows(season: int, as_of_date: str,
                        conn: sqlite3.Connection) -> list[dict]:
    """
    Build nhl_goalie_stats rows for today's probable starters.
    Matches goalies to their season stats.
    """
    goalie_stats = _fetch_goalie_season_stats(season)
    schedule     = _fetch_today_schedule(as_of_date)

    if not schedule:
        logger.info(f"No NHL games scheduled for {as_of_date}")
        return []

    # Build lookup: team abbrev → starting goalie name
    # NHL API schedule includes probable starter info in game objects
    goalie_lookup: dict[str, dict] = {}
    for row in goalie_stats:
        name = row.get("goalieFullName", "")
        team = _norm_nhl(row.get("teamAbbrev", ""))
        if name and team:
            goalie_lookup[team] = row

    rows = []
    for game in schedule:
        game_date_api = game.get("gameDate", as_of_date)[:10]
        home_abbrev = _norm_nhl(game.get("homeTeam", {}).get("abbrev", ""))
        away_abbrev = _norm_nhl(game.get("awayTeam", {}).get("abbrev", ""))

        for team_abbrev in [home_abbrev, away_abbrev]:
            # Try to get probable starter from game data
            team_key = "homeTeam" if team_abbrev == home_abbrev else "awayTeam"
            probable = game.get(team_key, {}).get("probableGoalie", {})
            goalie_name = probable.get("fullName", "")
            goalie_id   = str(probable.get("playerId", ""))

            # Fall back to team's season leader if no probable listed
            if not goalie_name and team_abbrev in goalie_lookup:
                g = goalie_lookup[team_abbrev]
                goalie_name = g.get("goalieFullName", "")
                goalie_id   = str(g.get("goalieId", ""))

            if not goalie_name:
                continue

            # Season stats from lookup
            g_stats = {}
            for g in goalie_stats:
                if str(g.get("goalieId", "")) == goalie_id or \
                   g.get("goalieFullName", "").lower() == goalie_name.lower():
                    g_stats = g
                    break

            # Match game_id from our DB
            game_db = conn.execute("""
                SELECT game_id FROM games
                WHERE sport = 'NHL'
                  AND game_date = ?
                  AND (home_team = ? OR away_team = ?)
                LIMIT 1
            """, (as_of_date, team_abbrev, team_abbrev)).fetchone()

            # Last 5 starts from our DB
            last5 = conn.execute("""
                SELECT AVG(save_pct), AVG(gaa), AVG(gsaa)
                FROM (
                    SELECT save_pct, gaa, gsaa
                    FROM nhl_goalie_stats
                    WHERE player_name = ?
                      AND season = ?
                      AND game_date < ?
                    ORDER BY game_date DESC
                    LIMIT 5
                )
            """, (goalie_name, season, as_of_date)).fetchone()

            row = {
                "player_name":    goalie_name,
                "player_id":      goalie_id or None,
                "team":           team_abbrev,
                "season":         season,
                "game_date":      as_of_date,
                "game_id":        game_db[0] if game_db else None,
                # Per-game (filled post-game)
                "saves":          None,
                "shots_faced":    None,
                "goals_allowed":  None,
                # Season rolling
                "save_pct":       _safe(g_stats.get("savePct")),
                "gaa":            _safe(g_stats.get("goalsAgainstAverage")),
                "gsaa":           _safe(g_stats.get("goalsAgainstAverage")),  # placeholder
                "xga":            None,
                # Last 5 starts
                "save_pct_last5": _safe(last5[0]) if last5 and last5[0] else None,
                "gaa_last5":      _safe(last5[1]) if last5 and last5[1] else None,
                "gsaa_last5":     _safe(last5[2]) if last5 and last5[2] else None,
            }
            rows.append(row)

    return rows


# ── DB Writers ────────────────────────────────────────────────────────────────

def _upsert_nhl_team_stats(conn: sqlite3.Connection, rows: list[dict]) -> int:
    sql = """
        INSERT INTO nhl_team_stats (
            team, season, as_of_date, games_played,
            goals_per_game, shots_per_game, corsi_for_pct, xgf_pct,
            power_play_pct, goals_last_5, goals_last_10, goals_home, goals_away,
            goals_against_pg, shots_against_pg, penalty_kill_pct, xga_pct,
            wins, losses, ot_losses, goal_differential,
            regulation_wins, regulation_losses, regulation_ties
        ) VALUES (
            :team, :season, :as_of_date, :games_played,
            :goals_per_game, :shots_per_game, :corsi_for_pct, :xgf_pct,
            :power_play_pct, :goals_last_5, :goals_last_10, :goals_home, :goals_away,
            :goals_against_pg, :shots_against_pg, :penalty_kill_pct, :xga_pct,
            :wins, :losses, :ot_losses, :goal_differential,
            :regulation_wins, :regulation_losses, :regulation_ties
        )
        ON CONFLICT(team, season, as_of_date) DO UPDATE SET
            games_played      = excluded.games_played,
            goals_per_game    = excluded.goals_per_game,
            shots_per_game    = excluded.shots_per_game,
            corsi_for_pct     = excluded.corsi_for_pct,
            xgf_pct           = excluded.xgf_pct,
            power_play_pct    = excluded.power_play_pct,
            goals_last_5      = excluded.goals_last_5,
            goals_last_10     = excluded.goals_last_10,
            goals_home        = excluded.goals_home,
            goals_away        = excluded.goals_away,
            goals_against_pg  = excluded.goals_against_pg,
            shots_against_pg  = excluded.shots_against_pg,
            penalty_kill_pct  = excluded.penalty_kill_pct,
            xga_pct           = excluded.xga_pct,
            wins              = excluded.wins,
            losses            = excluded.losses,
            ot_losses         = excluded.ot_losses,
            goal_differential = excluded.goal_differential,
            regulation_wins   = excluded.regulation_wins,
            regulation_losses = excluded.regulation_losses,
            regulation_ties   = excluded.regulation_ties
    """
    defaults = {
        "games_played": None, "goals_per_game": None, "shots_per_game": None,
        "corsi_for_pct": None, "xgf_pct": None, "power_play_pct": None,
        "goals_last_5": None, "goals_last_10": None, "goals_home": None,
        "goals_away": None, "goals_against_pg": None, "shots_against_pg": None,
        "penalty_kill_pct": None, "xga_pct": None, "wins": None, "losses": None,
        "ot_losses": None, "goal_differential": None, "regulation_wins": None,
        "regulation_losses": None, "regulation_ties": None,
    }
    filled = [{**defaults, **r} for r in rows]
    conn.executemany(sql, filled)
    return len(rows)


def _upsert_goalie_stats(conn: sqlite3.Connection, rows: list[dict]) -> int:
    sql = """
        INSERT INTO nhl_goalie_stats (
            player_name, player_id, team, season, game_date, game_id,
            saves, shots_faced, goals_allowed,
            save_pct, gaa, gsaa, xga,
            save_pct_last5, gaa_last5, gsaa_last5
        ) VALUES (
            :player_name, :player_id, :team, :season, :game_date, :game_id,
            :saves, :shots_faced, :goals_allowed,
            :save_pct, :gaa, :gsaa, :xga,
            :save_pct_last5, :gaa_last5, :gsaa_last5
        )
        ON CONFLICT(player_id, game_date) DO UPDATE SET
            save_pct      = excluded.save_pct,
            gaa           = excluded.gaa,
            gsaa          = excluded.gsaa,
            save_pct_last5 = excluded.save_pct_last5,
            gaa_last5     = excluded.gaa_last5,
            gsaa_last5    = excluded.gsaa_last5
    """
    defaults = {
        "player_id": None, "game_id": None, "saves": None, "shots_faced": None,
        "goals_allowed": None, "save_pct": None, "gaa": None, "gsaa": None,
        "xga": None, "save_pct_last5": None, "gaa_last5": None, "gsaa_last5": None,
    }

    with_id    = [r for r in rows if r.get("player_id")]
    without_id = [r for r in rows if not r.get("player_id")]

    if with_id:
        conn.executemany(sql, [{**defaults, **r} for r in with_id])

    if without_id:
        simple_sql = sql.replace(
            "ON CONFLICT(player_id, game_date) DO UPDATE SET",
            "ON CONFLICT DO NOTHING --"
        )
        # Simpler: just INSERT OR IGNORE
        insert_sql = """
            INSERT OR IGNORE INTO nhl_goalie_stats (
                player_name, player_id, team, season, game_date, game_id,
                saves, shots_faced, goals_allowed,
                save_pct, gaa, gsaa, xga,
                save_pct_last5, gaa_last5, gsaa_last5
            ) VALUES (
                :player_name, :player_id, :team, :season, :game_date, :game_id,
                :saves, :shots_faced, :goals_allowed,
                :save_pct, :gaa, :gsaa, :xga,
                :save_pct_last5, :gaa_last5, :gsaa_last5
            )
        """
        conn.executemany(insert_sql, [{**defaults, **r} for r in without_id])

    return len(rows)


def _log_pipeline(conn, run_date, status, records_in, records_out, duration_s, error_msg=None):
    conn.execute("""
        INSERT INTO pipeline_log (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (?, 'nhl_stats', ?, ?, ?, ?, ?)
    """, (run_date, status, records_in, records_out, duration_s, error_msg))


def _safe(val) -> float | None:
    try:
        f = float(val)
        return None if (f != f) else round(f, 4)
    except (TypeError, ValueError):
        return None


# ── Main Entry Point ──────────────────────────────────────────────────────────

def run_nhl_stats_ingestor(season: int = None, as_of_date: str = None) -> dict:
    """
    Pull and store NHL team + goalie stats.

    Args:
        season:     NHL season end year (e.g. 2024 = 2023-24 season)
        as_of_date: ISO date (default: today)
    """
    today = date.today()
    if as_of_date is None:
        as_of_date = today.isoformat()
    if season is None:
        year  = today.year
        month = today.month
        # NHL seasons run October–June; before October, we're in prior season
        season = year if month >= 10 else year

    logger.info(f"NHL stats ingestor — season={season}, as_of={as_of_date}")
    start = datetime.now()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        # ── Team stats ────────────────────────────────────────────────────────
        team_rows = _build_nhl_team_rows(season, as_of_date, conn)
        n_teams   = _upsert_nhl_team_stats(conn, team_rows)
        logger.success(f"NHL team stats: {n_teams} rows upserted")

        # ── Goalie stats ──────────────────────────────────────────────────────
        goalie_rows = _build_goalie_rows(season, as_of_date, conn)
        n_goalies   = _upsert_goalie_stats(conn, goalie_rows)
        logger.success(f"NHL goalie stats: {n_goalies} probable starters stored")

        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, as_of_date, "success",
                      records_in=n_teams + n_goalies,
                      records_out=n_teams + n_goalies,
                      duration_s=duration)
        conn.commit()

    except Exception as exc:
        conn.rollback()
        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, as_of_date, "error", 0, 0, duration, str(exc))
        conn.commit()
        logger.error(f"NHL stats ingestor failed: {exc}")
        raise
    finally:
        conn.close()

    return {
        "season":      season,
        "as_of_date":  as_of_date,
        "team_rows":   n_teams,
        "goalie_rows": n_goalies,
        "duration_s":  (datetime.now() - start).total_seconds(),
    }


def backfill_nhl_stats(start_season: int, end_season: int) -> None:
    """Backfill NHL stats for seasons start_season through end_season."""
    for season in range(start_season, end_season + 1):
        snap = f"{season}-04-15"  # mid-playoffs snapshot
        logger.info(f"Backfilling NHL stats for {season} → {snap}")
        try:
            result = run_nhl_stats_ingestor(season=season, as_of_date=snap)
            logger.success(f"  Season {season}: {result}")
        except Exception as exc:
            logger.error(f"  Season {season} failed: {exc}")
        time.sleep(2)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run NHL stats ingestor")
    parser.add_argument("--season", type=int, help="NHL season end year")
    parser.add_argument("--date",   dest="as_of_date", help="As-of date YYYY-MM-DD")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill seasons START through END")
    args = parser.parse_args()

    if args.backfill:
        backfill_nhl_stats(args.backfill[0], args.backfill[1])
    else:
        result = run_nhl_stats_ingestor(season=args.season, as_of_date=args.as_of_date)
        logger.info(f"Done: {result}")

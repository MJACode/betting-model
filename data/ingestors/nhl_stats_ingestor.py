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
from config import SPORTS
from data.db import get_connection, DBConnection

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
    "ANA": "ANA", "BOS": "BOS", "BUF": "BUF",
    "CGY": "CGY", "CAR": "CAR", "CHI": "CHI", "COL": "COL",
    "CBJ": "CBJ", "DAL": "DAL", "DET": "DET", "EDM": "EDM",
    "FLA": "FLA", "LAK": "LAK", "MIN": "MIN", "MTL": "MTL",
    "NSH": "NSH", "NJD": "NJD", "NYI": "NYI", "NYR": "NYR",
    "OTT": "OTT", "PHI": "PHI", "PIT": "PIT", "SJS": "SJS",
    "SEA": "SEA", "STL": "STL", "TBL": "TBL", "TOR": "TOR",
    # Canonical id for the relocated franchise is UTA (Utah Mammoth, formerly
    # Utah Hockey Club, formerly Arizona Coyotes). Historical ARI rows fold
    # into UTA so the franchise has one identity across seasons — same
    # convention as the odds ingestor and SBR loader.
    "ARI": "UTA", "UTA": "UTA",
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


# ── Games / Results (scores + regulation outcome) ────────────────────────────
# The games table is the training backbone (targets) AND the settlement source
# (paper_tracker requires home_score). SBR historical odds files are optional —
# the NHL API alone provides every game, final score, and OT/SO outcome, which
# is all the moneyline + regulation models need.

def parse_nhl_game(g: dict, default_date: str | None = None) -> dict | None:
    """
    Parse one game object from the NHL API (/v1/schedule/{date} or
    /v1/score/{date}) into a games-table row.

    The /score endpoint games carry `gameDate` (the ET game date); the
    /schedule endpoint games do NOT — there the date lives on the enclosing
    `gameWeek` day, so callers pass it as `default_date`. (startTimeUTC is the
    next calendar day for evening ET games, so it must NOT be used for the date.)

    Returns None for non-regular/playoff games (preseason, All-Star) or rows
    missing teams/date. Scores and outcome fields are None until the game is
    final ('OFF' / 'FINAL' gameState).

    Regulation encoding (must match paper_tracker._compute_result and
    feature_engine._compute_target):
      went_to_ot   = 1 when the game ended in OT or SO
      home_win_reg = 1 home won in regulation; 0 otherwise (away reg win OR
                     any OT/SO game — the draw case is signalled by went_to_ot)
      regulation_tie = went_to_ot (NHL: tied after 60 min iff OT/SO)
    """
    # Reject preseason/All-Star ONLY when gameType is present and not regular
    # season (2) or playoffs (3). The /score endpoint may omit gameType; don't
    # drop those games (it returns only real games for the date) — dropping
    # them would silently block all NHL settlement.
    gt = g.get("gameType")
    if gt is not None and gt not in (2, 3):
        return None

    game_date = (g.get("gameDate") or default_date or "")[:10]
    home_raw = (g.get("homeTeam") or {}).get("abbrev") or ""
    away_raw = (g.get("awayTeam") or {}).get("abbrev") or ""
    if not game_date or not home_raw or not away_raw:
        return None

    home = _norm_nhl(home_raw)
    away = _norm_nhl(away_raw)

    # NHL API season is YYYYYYYY; our label is the ending year
    season_raw = g.get("season")
    try:
        season = int(str(season_raw)[-4:])
    except (TypeError, ValueError):
        year, month = int(game_date[:4]), int(game_date[5:7])
        season = year + 1 if month >= 10 else year

    state = (g.get("gameState") or "").upper()
    is_final = state in ("OFF", "FINAL")

    home_score = away_score = None
    home_win = home_win_reg = None
    went_to_ot = reg_tie = None
    if is_final:
        home_score = (g.get("homeTeam") or {}).get("score")
        away_score = (g.get("awayTeam") or {}).get("score")
        if home_score is not None and away_score is not None:
            last_period = ((g.get("gameOutcome") or {}).get("lastPeriodType") or "REG").upper()
            went_to_ot = int(last_period != "REG")
            reg_tie    = went_to_ot
            home_win   = int(home_score > away_score)
            home_win_reg = int(home_win == 1 and went_to_ot == 0)
        else:
            home_score = away_score = None   # final without scores — treat as not final

    return {
        "game_id":        f"NHL_{game_date}_{away}_{home}",
        "sport":          "NHL",
        "season":         season,
        "game_date":      game_date,
        "home_team":      home,
        "away_team":      away,
        "home_score":     home_score,
        "away_score":     away_score,
        "home_win":       home_win,
        "home_win_reg":   home_win_reg,
        "went_to_ot":     went_to_ot,
        "regulation_tie": reg_tie,
        "commence_time":  g.get("startTimeUTC"),
        "data_source":    "nhl_api",
    }


def _upsert_nhl_games(conn: DBConnection, rows: list[dict]) -> int:
    """
    Upsert games rows. Scores/outcomes only overwrite when the incoming row
    has them (a schedule fetch for an upcoming game never NULLs out a final).
    """
    sql = """
        INSERT INTO games (
            game_id, sport, season, game_date, home_team, away_team,
            home_score, away_score, home_win, home_win_reg,
            went_to_ot, regulation_tie, commence_time, data_source
        ) VALUES (
            %(game_id)s, %(sport)s, %(season)s, %(game_date)s, %(home_team)s, %(away_team)s,
            %(home_score)s, %(away_score)s, %(home_win)s, %(home_win_reg)s,
            %(went_to_ot)s, %(regulation_tie)s, %(commence_time)s, %(data_source)s
        )
        ON CONFLICT(game_id) DO UPDATE SET
            home_score     = COALESCE(EXCLUDED.home_score,     games.home_score),
            away_score     = COALESCE(EXCLUDED.away_score,     games.away_score),
            home_win       = COALESCE(EXCLUDED.home_win,       games.home_win),
            home_win_reg   = COALESCE(EXCLUDED.home_win_reg,   games.home_win_reg),
            went_to_ot     = COALESCE(EXCLUDED.went_to_ot,     games.went_to_ot),
            regulation_tie = COALESCE(EXCLUDED.regulation_tie, games.regulation_tie),
            commence_time  = COALESCE(EXCLUDED.commence_time,  games.commence_time),
            updated_at     = NOW()::TEXT
    """
    if not rows:
        return 0
    conn.executemany(sql, rows)
    return len(rows)


def backfill_nhl_games(start_season: int, end_season: int) -> None:
    """
    Backfill all NHL games (regular season + playoffs) for the given seasons
    by walking the league-wide week schedule endpoint (~27 calls/season).
    Writes scores, home_win, went_to_ot, home_win_reg — the full target set
    for nhl_moneyline and nhl_moneyline_regulation.
    """
    conn = get_connection()
    try:
        for season in range(start_season, end_season + 1):
            cursor = f"{season - 1}-09-20"
            stop   = f"{season}-07-15"
            season_rows: dict[str, dict] = {}
            calls = 0
            while cursor and cursor < stop and calls < 60:
                try:
                    resp = requests.get(f"{NHL_API_BASE}/schedule/{cursor}",
                                        headers=NHL_HEADERS, timeout=20)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.error(f"NHL schedule fetch failed for {cursor}: {exc}")
                    break
                calls += 1
                for week_day in data.get("gameWeek", []):
                    for g in week_day.get("games", []):
                        row = parse_nhl_game(g, default_date=week_day.get("date"))
                        if row and row["season"] == season:
                            season_rows[row["game_id"]] = row
                nxt = data.get("nextStartDate")
                if not nxt or nxt <= cursor:
                    break
                cursor = nxt
                time.sleep(0.25)

            n = _upsert_nhl_games(conn, list(season_rows.values()))
            conn.commit()
            finals = sum(1 for r in season_rows.values() if r["home_score"] is not None)
            logger.success(f"NHL games {season}: {n} games upserted "
                           f"({finals} final) in {calls} schedule calls")
    finally:
        conn.close()


def ingest_nhl_scores_for_date(game_date: str = None, window_days: int = 3) -> int:
    """
    Daily results step: fetch final scores for game_date and the trailing
    window (catches postponements / late finishes), upsert into games.
    Runs before settlement in the 7am pipeline — the NHL analog of the MLB
    statsapi score fetch in paper_tracker.
    """
    from datetime import timedelta
    if game_date is None:
        game_date = (date.today() - timedelta(days=1)).isoformat()

    conn = get_connection()
    total = 0
    try:
        base = date.fromisoformat(game_date)
        for offset in range(window_days):
            d = (base - timedelta(days=offset)).isoformat()
            try:
                resp = requests.get(f"{NHL_API_BASE}/score/{d}",
                                    headers=NHL_HEADERS, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning(f"NHL score fetch failed for {d}: {exc}")
                continue
            rows = []
            for g in data.get("games", []):
                row = parse_nhl_game(g)
                if row and row["home_score"] is not None:
                    rows.append(row)
            total += _upsert_nhl_games(conn, rows)
            time.sleep(0.25)
        conn.commit()
        if total:
            logger.success(f"NHL scores: {total} final games upserted "
                           f"(window {window_days}d back from {game_date})")
        else:
            logger.info(f"NHL scores: no finals in window (offseason or no games)")
    finally:
        conn.close()
    return total


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

def _upsert_nhl_team_stats(conn: DBConnection, rows: list[dict]) -> int:
    sql = """
        INSERT INTO nhl_team_stats (
            team, season, as_of_date, games_played,
            goals_per_game, shots_per_game, corsi_for_pct, xgf_pct,
            power_play_pct, goals_last_5, goals_last_10, goals_home, goals_away,
            goals_against_pg, shots_against_pg, penalty_kill_pct, xga_pct,
            wins, losses, ot_losses, goal_differential,
            regulation_wins, regulation_losses, regulation_ties
        ) VALUES (
            %(team)s, %(season)s, %(as_of_date)s, %(games_played)s,
            %(goals_per_game)s, %(shots_per_game)s, %(corsi_for_pct)s, %(xgf_pct)s,
            %(power_play_pct)s, %(goals_last_5)s, %(goals_last_10)s, %(goals_home)s, %(goals_away)s,
            %(goals_against_pg)s, %(shots_against_pg)s, %(penalty_kill_pct)s, %(xga_pct)s,
            %(wins)s, %(losses)s, %(ot_losses)s, %(goal_differential)s,
            %(regulation_wins)s, %(regulation_losses)s, %(regulation_ties)s
        )
        ON CONFLICT(team, season, as_of_date) DO UPDATE SET
            games_played      = EXCLUDED.games_played,
            goals_per_game    = EXCLUDED.goals_per_game,
            shots_per_game    = EXCLUDED.shots_per_game,
            corsi_for_pct     = EXCLUDED.corsi_for_pct,
            xgf_pct           = EXCLUDED.xgf_pct,
            power_play_pct    = EXCLUDED.power_play_pct,
            goals_last_5      = EXCLUDED.goals_last_5,
            goals_last_10     = EXCLUDED.goals_last_10,
            goals_home        = EXCLUDED.goals_home,
            goals_away        = EXCLUDED.goals_away,
            goals_against_pg  = EXCLUDED.goals_against_pg,
            shots_against_pg  = EXCLUDED.shots_against_pg,
            penalty_kill_pct  = EXCLUDED.penalty_kill_pct,
            xga_pct           = EXCLUDED.xga_pct,
            wins              = EXCLUDED.wins,
            losses            = EXCLUDED.losses,
            ot_losses         = EXCLUDED.ot_losses,
            goal_differential = EXCLUDED.goal_differential,
            regulation_wins   = EXCLUDED.regulation_wins,
            regulation_losses = EXCLUDED.regulation_losses,
            regulation_ties   = EXCLUDED.regulation_ties
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


def _upsert_goalie_stats(conn: DBConnection, rows: list[dict]) -> int:
    sql = """
        INSERT INTO nhl_goalie_stats (
            player_name, player_id, team, season, game_date, game_id,
            saves, shots_faced, goals_allowed,
            save_pct, gaa, gsaa, xga,
            save_pct_last5, gaa_last5, gsaa_last5
        ) VALUES (
            %(player_name)s, %(player_id)s, %(team)s, %(season)s, %(game_date)s, %(game_id)s,
            %(saves)s, %(shots_faced)s, %(goals_allowed)s,
            %(save_pct)s, %(gaa)s, %(gsaa)s, %(xga)s,
            %(save_pct_last5)s, %(gaa_last5)s, %(gsaa_last5)s
        )
        ON CONFLICT(player_id, game_date) DO UPDATE SET
            save_pct      = EXCLUDED.save_pct,
            gaa           = EXCLUDED.gaa,
            gsaa          = EXCLUDED.gsaa,
            save_pct_last5 = EXCLUDED.save_pct_last5,
            gaa_last5     = EXCLUDED.gaa_last5,
            gsaa_last5    = EXCLUDED.gsaa_last5
    """
    no_conflict_sql = """
        INSERT INTO nhl_goalie_stats (
            player_name, player_id, team, season, game_date, game_id,
            saves, shots_faced, goals_allowed,
            save_pct, gaa, gsaa, xga,
            save_pct_last5, gaa_last5, gsaa_last5
        ) VALUES (
            %(player_name)s, %(player_id)s, %(team)s, %(season)s, %(game_date)s, %(game_id)s,
            %(saves)s, %(shots_faced)s, %(goals_allowed)s,
            %(save_pct)s, %(gaa)s, %(gsaa)s, %(xga)s,
            %(save_pct_last5)s, %(gaa_last5)s, %(gsaa_last5)s
        )
        ON CONFLICT DO NOTHING
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
        conn.executemany(no_conflict_sql, [{**defaults, **r} for r in without_id])

    return len(rows)


def _log_pipeline(conn, run_date, status, records_in, records_out, duration_s, error_msg=None):
    conn.execute("""
        INSERT INTO pipeline_log (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (%s, 'nhl_stats', %s, %s, %s, %s, %s)
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
        # NHL seasons run October–June, labeled by ENDING year: Oct–Dec games
        # belong to next year's label (Nov 2026 → season 2027).
        season = year + 1 if month >= 10 else year

    logger.info(f"NHL stats ingestor — season={season}, as_of={as_of_date}")
    start = datetime.now()

    conn = get_connection()

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


def _goalie_team(row: dict) -> str:
    """
    Resolve a goalie-summary row to one of our team abbrevs. The summary
    endpoint reports traded goalies as comma-separated abbrevs ('TOR, EDM') —
    take the most recent (last) team.
    """
    raw = row.get("teamAbbrevs") or row.get("teamAbbrev") or ""
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    return _norm_nhl(parts[-1]) if parts else ""


def backfill_nhl_goalies(season: int, as_of_date: str,
                         conn: DBConnection) -> int:
    """
    Write one season-snapshot goalie row per team: the team's primary goalie
    (most games played) with their season stats. Uses the season-start
    snapshot date so the feature engine's ASOF lookup (game_date <= ?) finds
    it for every game in the season.

    Look-ahead caveat: these are full-season stats, same accepted limitation
    as the MLB pitcher backfill — goalie quality is stable enough within a
    season for v1. Live scoring overrides with the daily probable-starter row.
    """
    goalies = _fetch_goalie_season_stats(season)
    primary: dict[str, dict] = {}
    for g in goalies:
        team = _goalie_team(g)
        if not team:
            continue
        gp = g.get("gamesPlayed") or 0
        if team not in primary or gp > (primary[team].get("gamesPlayed") or 0):
            primary[team] = g

    rows = []
    for team, g in primary.items():
        rows.append({
            "player_name":    g.get("goalieFullName", ""),
            "player_id":      str(g.get("goalieId") or g.get("playerId") or "") or None,
            "team":           team,
            "season":         season,
            "game_date":      as_of_date,
            "game_id":        None,
            "saves":          None,
            "shots_faced":    None,
            "goals_allowed":  None,
            "save_pct":       _safe(g.get("savePct")),
            "gaa":            _safe(g.get("goalsAgainstAverage")),
            "gsaa":           _safe(g.get("goalsAgainstAverage")),  # placeholder, matches daily path
            "xga":            None,
            "save_pct_last5": None,
            "gaa_last5":      None,
            "gsaa_last5":     None,
        })
    if rows:
        _upsert_goalie_stats(conn, rows)
    return len(rows)


def backfill_nhl_stats(start_season: int, end_season: int) -> None:
    """
    Backfill NHL team + goalie season snapshots.

    Snapshot date is the season START ({season-1}-10-01), not season end —
    the feature engine queries as_of_date <= game_date, so an end-of-season
    snapshot would never match in-season games (the same bug the MLB backfill
    had with Oct 1 snapshots). Stats are full-season totals — documented
    look-ahead, same as the MLB pitcher and WNBA team backfills. Rolling
    goals features are recomputed per game date by the bulk feature path.

    Run backfill_nhl_games() FIRST — rolling-goal windows read the games table.
    """
    for season in range(start_season, end_season + 1):
        snap = f"{season - 1}-10-01"  # season start — before any game
        logger.info(f"Backfilling NHL stats for {season} → {snap}")
        try:
            result = run_nhl_stats_ingestor(season=season, as_of_date=snap)
            conn = get_connection()
            try:
                n_goalies = backfill_nhl_goalies(season, snap, conn)
                conn.commit()
            finally:
                conn.close()
            logger.success(f"  Season {season}: {result} + {n_goalies} goalie snapshots")
        except Exception as exc:
            logger.error(f"  Season {season} failed: {exc}")
        time.sleep(2)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run NHL stats ingestor")
    parser.add_argument("--season", type=int, help="NHL season end year")
    parser.add_argument("--date",   dest="as_of_date", help="As-of date YYYY-MM-DD")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill team+goalie season snapshots START through END")
    parser.add_argument("--backfill-games", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill games + scores + regulation outcomes START through END")
    parser.add_argument("--scores", nargs="?", const="", metavar="DATE",
                        help="Ingest final scores for DATE (default: yesterday)")
    args = parser.parse_args()

    if args.backfill_games:
        backfill_nhl_games(args.backfill_games[0], args.backfill_games[1])
    elif args.scores is not None:
        ingest_nhl_scores_for_date(args.scores or None)
    elif args.backfill:
        backfill_nhl_stats(args.backfill[0], args.backfill[1])
    else:
        result = run_nhl_stats_ingestor(season=args.season, as_of_date=args.as_of_date)
        logger.info(f"Done: {result}")

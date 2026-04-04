"""
mlb_stats_ingestor.py — MLB team and pitcher stats via pybaseball + MLB Stats API.

What it builds:
  • mlb_team_stats   — Season-to-date team batting/pitching stats, updated daily
  • mlb_pitcher_stats — Per-start pitcher performance (starters only)

Data sources:
  • pybaseball.team_batting()    — FanGraphs batting (wRC+, wOBA, K%, BB%, ISO, BABIP)
  • pybaseball.team_pitching()   — FanGraphs pitching (ERA, FIP, WHIP, K/9, BB/9)
  • pybaseball.pitching_stats()  — FanGraphs pitcher-level (xFIP, SwStr%, CSW%)
  • statsapi (MLB Stats API)     — Probable starters, scheduled games

Usage:
    python -m data.ingestors.mlb_stats_ingestor           # today, all teams
    python -m data.ingestors.mlb_stats_ingestor --season 2024
    python -m data.ingestors.mlb_stats_ingestor --backfill 2019 2024
"""

import argparse
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import SPORTS, MIN_GAMES_BASELINE
from data.db import get_connection, DBConnection

# ── Safe Imports (pybaseball is optional at import time) ─────────────────────

try:
    import pybaseball as pb
    pb.cache.enable()
    PYBASEBALL_AVAILABLE = True
except ImportError:
    PYBASEBALL_AVAILABLE = False
    logger.warning("pybaseball not installed — run: pip install pybaseball --break-system-packages")

try:
    import statsapi
    STATSAPI_AVAILABLE = True
except ImportError:
    STATSAPI_AVAILABLE = False
    logger.warning("MLB-StatsAPI not installed — run: pip install MLB-StatsAPI --break-system-packages")

# ── Team Name Maps ───────────────────────────────────────────────────────────
# FanGraphs uses team abbreviations that sometimes differ from ours

FG_TO_ABBREV = {
    "ARI": "ARI", "ATL": "ATL", "BAL": "BAL", "BOS": "BOS",
    "CHC": "CHC", "CHW": "CWS", "CIN": "CIN", "CLE": "CLE",
    "COL": "COL", "DET": "DET", "HOU": "HOU", "KCR": "KC",
    "LAA": "LAA", "LAD": "LAD", "MIA": "MIA", "MIL": "MIL",
    "MIN": "MIN", "NYM": "NYM", "NYY": "NYY", "OAK": "OAK",
    "PHI": "PHI", "PIT": "PIT", "SDP": "SD",  "SEA": "SEA",
    "SFG": "SF",  "STL": "STL", "TBR": "TB",  "TEX": "TEX",
    "TOR": "TOR", "WSN": "WSH",
    # Alternate FG codes
    "KC":  "KC",  "SD":  "SD",  "SF":  "SF",  "TB":  "TB",
    "WSH": "WSH", "CWS": "CWS",
}

# StatsAPI team IDs → our abbrevs
STATSAPI_TEAM_IDS = {
    109: "ARI", 144: "ATL", 110: "BAL", 111: "BOS", 112: "CHC",
    145: "CWS", 113: "CIN", 114: "CLE", 115: "COL", 116: "DET",
    117: "HOU", 118: "KC",  108: "LAA", 119: "LAD", 146: "MIA",
    158: "MIL", 142: "MIN", 121: "NYM", 147: "NYY", 133: "OAK",
    143: "PHI", 134: "PIT", 135: "SD",  136: "SEA", 137: "SF",
    138: "STL", 139: "TB",  140: "TEX", 141: "TOR", 120: "WSH",
}
ABBREV_TO_STATSAPI = {v: k for k, v in STATSAPI_TEAM_IDS.items()}

# ── Rolling Window Helpers ────────────────────────────────────────────────────

def _rolling_runs(conn: sqlite3.Connection, team: str, sport: str,
                  as_of_date: str, window: int) -> float | None:
    """Average runs scored per game in last N games before as_of_date."""
    rows = conn.execute("""
        SELECT CASE WHEN home_team = ? THEN home_score ELSE away_score END as scored
        FROM games
        WHERE sport = ?
          AND (home_team = ? OR away_team = ?)
          AND game_date < ?
          AND home_score IS NOT NULL
        ORDER BY game_date DESC
        LIMIT ?
    """, (team, sport, team, team, as_of_date, window)).fetchall()

    if not rows:
        return None
    scores = [r[0] for r in rows if r[0] is not None]
    return round(float(np.mean(scores)), 3) if scores else None


def _home_away_runs(conn: sqlite3.Connection, team: str, as_of_date: str,
                    location: str) -> float | None:
    """Average runs in home or away games this season."""
    year = as_of_date[:4]
    col  = "home_score" if location == "home" else "away_score"
    cond = "home_team = ?" if location == "home" else "away_team = ?"

    rows = conn.execute(f"""
        SELECT {col}
        FROM games
        WHERE sport = 'MLB'
          AND {cond}
          AND game_date >= '{year}-01-01'
          AND game_date < ?
          AND home_score IS NOT NULL
    """, (team, as_of_date)).fetchall()

    if not rows:
        return None
    scores = [r[0] for r in rows if r[0] is not None]
    return round(float(np.mean(scores)), 3) if scores else None


# ── FanGraphs Team Stats ──────────────────────────────────────────────────────

def _fetch_fg_team_batting(season: int) -> pd.DataFrame:
    """Pull FanGraphs team batting via pybaseball."""
    if not PYBASEBALL_AVAILABLE:
        return pd.DataFrame()
    try:
        df = pb.team_batting(season, season)
        return df
    except Exception as exc:
        logger.error(f"pybaseball team_batting {season} failed: {exc}")
        return pd.DataFrame()


def _fetch_fg_team_pitching(season: int) -> pd.DataFrame:
    """Pull FanGraphs team pitching via pybaseball."""
    if not PYBASEBALL_AVAILABLE:
        return pd.DataFrame()
    try:
        df = pb.team_pitching(season, season)
        return df
    except Exception as exc:
        logger.error(f"pybaseball team_pitching {season} failed: {exc}")
        return pd.DataFrame()


def _build_team_stats_rows(season: int, as_of_date: str,
                            conn: sqlite3.Connection) -> list[dict]:
    """
    Combine batting + pitching FanGraphs data into mlb_team_stats rows.
    One row per team per as_of_date.
    """
    bat_df  = _fetch_fg_team_batting(season)
    pitch_df = _fetch_fg_team_pitching(season)

    if bat_df.empty and pitch_df.empty:
        logger.warning(f"No FanGraphs data for MLB {season}")
        return []

    # Normalize team abbreviation
    def _norm(df: pd.DataFrame) -> pd.DataFrame:
        if "Team" in df.columns:
            df = df.copy()
            df["team"] = df["Team"].map(lambda x: FG_TO_ABBREV.get(str(x).upper(), str(x).upper()))
        return df

    bat_df   = _norm(bat_df)
    pitch_df = _norm(pitch_df)

    rows = []
    all_teams = set()
    if not bat_df.empty and "team" in bat_df.columns:
        all_teams.update(bat_df["team"].tolist())
    if not pitch_df.empty and "team" in pitch_df.columns:
        all_teams.update(pitch_df["team"].tolist())

    for team in all_teams:
        row = {
            "team":       team,
            "season":     season,
            "as_of_date": as_of_date,
        }

        # ── Batting ──────────────────────────────────────────────────────────
        if not bat_df.empty:
            b = bat_df[bat_df["team"] == team]
            if not b.empty:
                b = b.iloc[0]
                row["games_played"]    = int(b.get("G",    0))
                row["ops"]             = _safe(b.get("OPS"))
                row["wrc_plus"]        = _safe(b.get("wRC+"))
                row["woba"]            = _safe(b.get("wOBA"))
                row["k_pct"]           = _safe(b.get("K%"))
                row["bb_pct"]          = _safe(b.get("BB%"))
                row["iso"]             = _safe(b.get("ISO"))
                row["babip"]           = _safe(b.get("BABIP"))
                row["runs_per_game"]   = _safe(b.get("R/G"))

        # ── Pitching ─────────────────────────────────────────────────────────
        if not pitch_df.empty:
            p = pitch_df[pitch_df["team"] == team]
            if not p.empty:
                p = p.iloc[0]
                row["team_era"]     = _safe(p.get("ERA"))
                row["team_whip"]    = _safe(p.get("WHIP"))
                row["team_fip"]     = _safe(p.get("FIP"))
                # Bullpen ERA: not directly available; use team ERA as proxy
                row["bullpen_era"]  = _safe(p.get("ERA"))  # refined in Phase 2

        # ── Rolling windows from games table ─────────────────────────────────
        row["runs_last_5"]  = _rolling_runs(conn, team, "MLB", as_of_date, 5)
        row["runs_last_10"] = _rolling_runs(conn, team, "MLB", as_of_date, 10)
        row["runs_last_15"] = _rolling_runs(conn, team, "MLB", as_of_date, 15)

        # ── Home/Away splits ──────────────────────────────────────────────────
        row["runs_per_game_home"] = _home_away_runs(conn, team, as_of_date, "home")
        row["runs_per_game_away"] = _home_away_runs(conn, team, as_of_date, "away")

        # ── Win/loss record ───────────────────────────────────────────────────
        wl = conn.execute("""
            SELECT
                SUM(CASE WHEN (home_team = ? AND home_win = 1)
                           OR (away_team = ? AND home_win = 0) THEN 1 ELSE 0 END),
                SUM(CASE WHEN (home_team = ? AND home_win = 0)
                           OR (away_team = ? AND home_win = 1) THEN 1 ELSE 0 END),
                SUM(CASE WHEN home_team = ? THEN home_score - away_score
                         WHEN away_team = ? THEN away_score - home_score
                         ELSE 0 END)
            FROM games
            WHERE sport = 'MLB'
              AND (home_team = ? OR away_team = ?)
              AND game_date >= '{year}-01-01'
              AND game_date < ?
              AND home_score IS NOT NULL
        """.format(year=season), (
            team, team, team, team, team, team, team, team, as_of_date
        )).fetchone()

        if wl:
            row["wins"]             = int(wl[0] or 0)
            row["losses"]           = int(wl[1] or 0)
            row["run_differential"] = int(wl[2] or 0)

        rows.append(row)

    return rows


def _normalize_name(name: str) -> str:
    """Strip accents and lowercase for fuzzy name matching."""
    return unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode().lower()


def _safe(val) -> float | None:
    """Safely convert FanGraphs value to float, returning None for NaN/missing."""
    try:
        f = float(val)
        return None if (f != f) else round(f, 4)  # NaN check
    except (TypeError, ValueError):
        return None


# ── FanGraphs Pitcher Stats ───────────────────────────────────────────────────

def _fetch_fg_pitcher_stats(season: int) -> pd.DataFrame:
    """Pull FanGraphs pitcher-level stats (starters only, min 1 IP)."""
    if not PYBASEBALL_AVAILABLE:
        return pd.DataFrame()
    try:
        df = pb.pitching_stats(season, season, qual=1)
        return df
    except Exception as exc:
        logger.error(f"pybaseball pitching_stats {season} failed: {exc}")
        return pd.DataFrame()


def _build_pitcher_rows(season: int, as_of_date: str,
                         conn: sqlite3.Connection) -> list[dict]:
    """
    Build mlb_pitcher_stats rows for today's probable starters.
    Season stats come from FanGraphs; per-game details filled from StatsAPI.
    """
    if not STATSAPI_AVAILABLE:
        logger.warning("MLB-StatsAPI not available — skipping pitcher rows")
        return []

    df = _fetch_fg_pitcher_stats(season)

    # Get today's probable starters from StatsAPI
    try:
        schedule = statsapi.schedule(date=as_of_date, sportId=1)
    except Exception as exc:
        logger.error(f"StatsAPI schedule {as_of_date} failed: {exc}")
        return []

    rows = []
    for game in schedule:
        game_id_mlb = game.get("game_id")
        home_abbrev = STATSAPI_TEAM_IDS.get(game.get("home_id"), "")
        away_abbrev = STATSAPI_TEAM_IDS.get(game.get("away_id"), "")

        for role, team_abbrev in [("home", home_abbrev), ("away", away_abbrev)]:
            prob_key = f"{role}_probable_pitcher"
            pitcher_name = game.get(prob_key, "")
            if not pitcher_name or pitcher_name == "TBD":
                continue

            norm_pitcher = _normalize_name(pitcher_name)

            # Match to FanGraphs data
            pitcher_row: dict = {
                "player_name": pitcher_name,
                "player_id":   None,
                "team":        team_abbrev,
                "season":      season,
                "game_date":   as_of_date,
                "game_id":     None,   # will fill from games table
                # Per-game stats not available pre-game; filled after game
                "innings_pitched": None,
                "strikeouts":      None,
                "walks":           None,
                "hits_allowed":    None,
                "earned_runs":     None,
                "home_runs_allowed": None,
            }

            # Season rolling from FanGraphs
            if not df.empty:
                fg_norm = df["Name"].apply(_normalize_name)
                match = df[fg_norm == norm_pitcher]
                if not match.empty:
                    p = match.iloc[0]
                    pitcher_row.update({
                        "era":       _safe(p.get("ERA")),
                        "xfip":      _safe(p.get("xFIP")),
                        "whip":      _safe(p.get("WHIP")),
                        "k9":        _safe(p.get("K/9")),
                        "bb9":       _safe(p.get("BB/9")),
                        "hr9":       _safe(p.get("HR/9")),
                        "swstr_pct": _safe(p.get("SwStr%")),
                        "csw_pct":   _safe(p.get("CSW%")),
                        "player_id": str(int(p.get("IDfg", 0) or 0)) or None,
                    })

            # Last 3 starts rolling (computed from our DB if we have history)
            last3 = conn.execute("""
                SELECT AVG(era), AVG(k9), AVG(xfip)
                FROM (
                    SELECT era, k9, xfip
                    FROM mlb_pitcher_stats
                    WHERE player_name = ?
                      AND season = ?
                      AND game_date < ?
                    ORDER BY game_date DESC
                    LIMIT 3
                )
            """, (pitcher_name, season, as_of_date)).fetchone()

            if last3 and last3[0] is not None:
                pitcher_row["era_last3"]  = _safe(last3[0])
                pitcher_row["k9_last3"]   = _safe(last3[1])
                pitcher_row["xfip_last3"] = _safe(last3[2])
            else:
                pitcher_row["era_last3"]  = None
                pitcher_row["k9_last3"]   = None
                pitcher_row["xfip_last3"] = None

            # Try to match game_id from games table
            game_db = conn.execute("""
                SELECT game_id FROM games
                WHERE sport = 'MLB'
                  AND game_date = ?
                  AND (home_team = ? OR away_team = ?)
                LIMIT 1
            """, (as_of_date, team_abbrev, team_abbrev)).fetchone()
            if game_db:
                pitcher_row["game_id"] = game_db[0]

            rows.append(pitcher_row)

    return rows


# ── DB Writers ────────────────────────────────────────────────────────────────

def _upsert_team_stats(conn: DBConnection, rows: list[dict]) -> int:
    sql = """
        INSERT INTO mlb_team_stats (
            team, season, as_of_date, games_played,
            ops, wrc_plus, woba, k_pct, bb_pct, iso, babip, runs_per_game,
            runs_last_5, runs_last_10, runs_last_15,
            runs_per_game_home, runs_per_game_away,
            team_era, bullpen_era, team_whip, team_fip,
            wins, losses, run_differential
        ) VALUES (
            %(team)s, %(season)s, %(as_of_date)s, %(games_played)s,
            %(ops)s, %(wrc_plus)s, %(woba)s, %(k_pct)s, %(bb_pct)s, %(iso)s, %(babip)s, %(runs_per_game)s,
            %(runs_last_5)s, %(runs_last_10)s, %(runs_last_15)s,
            %(runs_per_game_home)s, %(runs_per_game_away)s,
            %(team_era)s, %(bullpen_era)s, %(team_whip)s, %(team_fip)s,
            %(wins)s, %(losses)s, %(run_differential)s
        )
        ON CONFLICT(team, season, as_of_date) DO UPDATE SET
            games_played      = EXCLUDED.games_played,
            ops               = EXCLUDED.ops,
            wrc_plus          = EXCLUDED.wrc_plus,
            woba              = EXCLUDED.woba,
            k_pct             = EXCLUDED.k_pct,
            bb_pct            = EXCLUDED.bb_pct,
            iso               = EXCLUDED.iso,
            babip             = EXCLUDED.babip,
            runs_per_game     = EXCLUDED.runs_per_game,
            runs_last_5       = EXCLUDED.runs_last_5,
            runs_last_10      = EXCLUDED.runs_last_10,
            runs_last_15      = EXCLUDED.runs_last_15,
            runs_per_game_home = EXCLUDED.runs_per_game_home,
            runs_per_game_away = EXCLUDED.runs_per_game_away,
            team_era          = EXCLUDED.team_era,
            bullpen_era       = EXCLUDED.bullpen_era,
            team_whip         = EXCLUDED.team_whip,
            team_fip          = EXCLUDED.team_fip,
            wins              = EXCLUDED.wins,
            losses            = EXCLUDED.losses,
            run_differential  = EXCLUDED.run_differential
    """
    # Fill missing keys with None
    defaults = {
        "games_played": None, "ops": None, "wrc_plus": None, "woba": None,
        "k_pct": None, "bb_pct": None, "iso": None, "babip": None,
        "runs_per_game": None, "runs_last_5": None, "runs_last_10": None,
        "runs_last_15": None, "runs_per_game_home": None, "runs_per_game_away": None,
        "team_era": None, "bullpen_era": None, "team_whip": None, "team_fip": None,
        "wins": None, "losses": None, "run_differential": None,
    }
    filled = [{**defaults, **r} for r in rows]
    conn.executemany(sql, filled)
    return len(rows)


def _upsert_pitcher_stats(conn: DBConnection, rows: list[dict]) -> int:
    sql = """
        INSERT INTO mlb_pitcher_stats (
            player_name, player_id, team, season, game_date, game_id,
            innings_pitched, strikeouts, walks, hits_allowed, earned_runs, home_runs_allowed,
            era, xfip, whip, k9, bb9, hr9, swstr_pct, csw_pct,
            era_last3, k9_last3, xfip_last3
        ) VALUES (
            %(player_name)s, %(player_id)s, %(team)s, %(season)s, %(game_date)s, %(game_id)s,
            %(innings_pitched)s, %(strikeouts)s, %(walks)s, %(hits_allowed)s, %(earned_runs)s, %(home_runs_allowed)s,
            %(era)s, %(xfip)s, %(whip)s, %(k9)s, %(bb9)s, %(hr9)s, %(swstr_pct)s, %(csw_pct)s,
            %(era_last3)s, %(k9_last3)s, %(xfip_last3)s
        )
        ON CONFLICT(player_id, game_date) DO UPDATE SET
            era        = EXCLUDED.era,
            xfip       = EXCLUDED.xfip,
            whip       = EXCLUDED.whip,
            k9         = EXCLUDED.k9,
            bb9        = EXCLUDED.bb9,
            hr9        = EXCLUDED.hr9,
            swstr_pct  = EXCLUDED.swstr_pct,
            csw_pct    = EXCLUDED.csw_pct,
            era_last3  = EXCLUDED.era_last3,
            k9_last3   = EXCLUDED.k9_last3,
            xfip_last3 = EXCLUDED.xfip_last3
    """
    defaults = {
        "player_id": None, "game_id": None, "innings_pitched": None,
        "strikeouts": None, "walks": None, "hits_allowed": None,
        "earned_runs": None, "home_runs_allowed": None,
        "era": None, "xfip": None, "whip": None, "k9": None, "bb9": None,
        "hr9": None, "swstr_pct": None, "csw_pct": None,
        "era_last3": None, "k9_last3": None, "xfip_last3": None,
    }
    # Rows with a player_id use the ON CONFLICT upsert.
    # Rows without player_id get a plain insert (no conflict target available).
    with_id    = [r for r in rows if r.get("player_id")]
    without_id = [r for r in rows if not r.get("player_id")]

    if with_id:
        conn.executemany(sql, [{**defaults, **r} for r in with_id])

    if without_id:
        simple_sql = """
            INSERT INTO mlb_pitcher_stats (
                player_name, player_id, team, season, game_date, game_id,
                innings_pitched, strikeouts, walks, hits_allowed, earned_runs, home_runs_allowed,
                era, xfip, whip, k9, bb9, hr9, swstr_pct, csw_pct,
                era_last3, k9_last3, xfip_last3
            ) VALUES (
                %(player_name)s, %(player_id)s, %(team)s, %(season)s, %(game_date)s, %(game_id)s,
                %(innings_pitched)s, %(strikeouts)s, %(walks)s, %(hits_allowed)s, %(earned_runs)s, %(home_runs_allowed)s,
                %(era)s, %(xfip)s, %(whip)s, %(k9)s, %(bb9)s, %(hr9)s, %(swstr_pct)s, %(csw_pct)s,
                %(era_last3)s, %(k9_last3)s, %(xfip_last3)s
            )
            ON CONFLICT DO NOTHING
        """
        conn.executemany(simple_sql, [{**defaults, **r} for r in without_id])

    return len(rows)


def _log_pipeline(conn, run_date, status, records_in, records_out, duration_s, error_msg=None):
    conn.execute("""
        INSERT INTO pipeline_log (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (%s, 'mlb_stats', %s, %s, %s, %s, %s)
    """, (run_date, status, records_in, records_out, duration_s, error_msg))


# ── Main Entry Points ─────────────────────────────────────────────────────────

def run_mlb_stats_ingestor(season: int = None, as_of_date: str = None) -> dict:
    """
    Pull and store MLB team + pitcher stats for the given season/date.

    Args:
        season:     MLB season year (default: current year)
        as_of_date: ISO date (default: today)
    """
    today = date.today()
    if as_of_date is None:
        as_of_date = today.isoformat()
    if season is None:
        season = today.year

    logger.info(f"MLB stats ingestor — season={season}, as_of={as_of_date}")
    start = datetime.now()

    conn = get_connection()

    try:
        # ── Team stats ────────────────────────────────────────────────────────
        team_rows = _build_team_stats_rows(season, as_of_date, conn)
        n_teams   = _upsert_team_stats(conn, team_rows)
        logger.success(f"MLB team stats: {n_teams} rows upserted")

        # ── Pitcher stats (today's probable starters) ─────────────────────────
        pitcher_rows = _build_pitcher_rows(season, as_of_date, conn)
        n_pitchers   = _upsert_pitcher_stats(conn, pitcher_rows)
        logger.success(f"MLB pitcher stats: {n_pitchers} probable starters stored")

        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, as_of_date, "success",
                      records_in=n_teams + n_pitchers,
                      records_out=n_teams + n_pitchers,
                      duration_s=duration)
        conn.commit()

    except Exception as exc:
        conn.rollback()
        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, as_of_date, "error", 0, 0, duration, str(exc))
        conn.commit()
        logger.error(f"MLB stats ingestor failed: {exc}")
        raise
    finally:
        conn.close()

    return {
        "season":       season,
        "as_of_date":   as_of_date,
        "team_rows":    n_teams,
        "pitcher_rows": n_pitchers,
        "duration_s":   (datetime.now() - start).total_seconds(),
    }


def backfill_mlb_stats(start_season: int, end_season: int) -> None:
    """
    Backfill team stats for each season in range [start_season, end_season].
    Uses July 1 as a mid-season snapshot date for historical seasons.
    For the current/last season uses the actual final date.
    """
    current_year = date.today().year
    for season in range(start_season, end_season + 1):
        if season < current_year:
            snap = f"{season}-10-01"  # end-of-season snapshot
        else:
            snap = date.today().isoformat()

        logger.info(f"Backfilling MLB stats for {season} → {snap}")
        try:
            result = run_mlb_stats_ingestor(season=season, as_of_date=snap)
            logger.success(f"  Season {season}: {result}")
        except Exception as exc:
            logger.error(f"  Season {season} failed: {exc}")

        time.sleep(2)   # be polite to FanGraphs


def backfill_pitcher_stats(start_season: int, end_season: int) -> dict:
    """
    Backfill historical per-start pitcher stats for seasons start_season–end_season.

    For each completed game in our DB:
      1. Calls statsapi.schedule(date) to identify the actual starters (1 call per date).
      2. Looks up each starter's season stats from FanGraphs (1 call per season).
      3. Computes rolling last-3 ERA/K9/xFIP from rows already stored for that pitcher.
      4. Stores into mlb_pitcher_stats.

    Safe to re-run: dates that already have pitcher rows are skipped.

    Note on look-ahead bias: FanGraphs returns full-season stats, not stats as of game
    date. This is acceptable for v1 — established starters don't swing dramatically
    mid-season, and prior-season stats are the primary signal the market uses.

    Usage:
        python -m data.ingestors.mlb_stats_ingestor --backfill-pitchers 2019 2024
    """
    if not STATSAPI_AVAILABLE:
        logger.error("MLB-StatsAPI not available — install it first")
        return {}

    conn = get_connection()
    total_stored = 0
    total_skipped_dates = 0
    total_no_match = 0

    for season in range(start_season, end_season + 1):
        logger.info(f"\nSeason {season}: fetching FanGraphs pitcher stats...")
        fg_df = _fetch_fg_pitcher_stats(season)
        if fg_df.empty:
            logger.warning(f"  No FanGraphs data for {season} — names only, no advanced stats")

        # All completed game dates for this season
        dates = [r[0] for r in conn.execute("""
            SELECT DISTINCT game_date FROM games
            WHERE sport='MLB' AND season=? AND home_score IS NOT NULL
            ORDER BY game_date
        """, (season,)).fetchall()]

        logger.info(f"  {len(dates)} game dates to process")
        n_stored = 0

        for i, date_str in enumerate(dates, 1):
            # Skip if this date is already fully processed
            existing = conn.execute("""
                SELECT COUNT(*) FROM mlb_pitcher_stats
                WHERE season=? AND game_date=?
            """, (season, date_str)).fetchone()[0]
            if existing >= 2:   # at least home + away starter stored
                total_skipped_dates += 1
                continue

            # Get actual starters from MLB schedule API
            try:
                schedule = statsapi.schedule(date=date_str, sportId=1)
                time.sleep(0.3)
            except Exception as exc:
                logger.warning(f"  Schedule API failed {date_str}: {exc}")
                continue

            rows = []
            for game in schedule:
                if game.get("game_type") != "R":
                    continue   # regular season only

                home_abbrev = STATSAPI_TEAM_IDS.get(game.get("home_id"), "")
                away_abbrev = STATSAPI_TEAM_IDS.get(game.get("away_id"), "")

                # Match to our game_id
                game_db = conn.execute("""
                    SELECT game_id FROM games
                    WHERE sport='MLB' AND game_date=?
                      AND home_team=? AND away_team=?
                    LIMIT 1
                """, (date_str, home_abbrev, away_abbrev)).fetchone()
                game_id = game_db[0] if game_db else None

                for role, team_abbrev in [("home", home_abbrev), ("away", away_abbrev)]:
                    pitcher_name = game.get(f"{role}_probable_pitcher", "")
                    if not pitcher_name or pitcher_name == "TBD":
                        continue

                    row: dict = {
                        "player_name":      pitcher_name,
                        "player_id":        None,
                        "team":             team_abbrev,
                        "season":           season,
                        "game_date":        date_str,
                        "game_id":          game_id,
                        "innings_pitched":  None,
                        "strikeouts":       None,
                        "walks":            None,
                        "hits_allowed":     None,
                        "earned_runs":      None,
                        "home_runs_allowed": None,
                        "era": None, "xfip": None, "whip": None,
                        "k9": None,  "bb9": None,  "hr9": None,
                        "swstr_pct": None, "csw_pct": None,
                        "era_last3": None, "k9_last3": None, "xfip_last3": None,
                    }

                    # Season stats from FanGraphs
                    if not fg_df.empty:
                        # Normalize both sides to handle accented characters
                        norm_name = _normalize_name(pitcher_name)
                        fg_norm   = fg_df["Name"].apply(_normalize_name)
                        match = fg_df[fg_norm == norm_name]
                        if match.empty:
                            last = norm_name.split()[-1]
                            match = fg_df[fg_norm.str.split().str[-1] == last]
                        if not match.empty:
                            p = match.iloc[0]
                            row.update({
                                "era":       _safe(p.get("ERA")),
                                "xfip":      _safe(p.get("xFIP")),
                                "whip":      _safe(p.get("WHIP")),
                                "k9":        _safe(p.get("K/9")),
                                "bb9":       _safe(p.get("BB/9")),
                                "hr9":       _safe(p.get("HR/9")),
                                "swstr_pct": _safe(p.get("SwStr%")),
                                "csw_pct":   _safe(p.get("CSW%")),
                                "player_id": str(int(p.get("IDfg", 0) or 0)) or None,
                            })
                        else:
                            total_no_match += 1

                    # Rolling last-3 from rows already stored for this pitcher this season
                    last3 = conn.execute("""
                        SELECT AVG(era), AVG(k9), AVG(xfip)
                        FROM (
                            SELECT era, k9, xfip FROM mlb_pitcher_stats
                            WHERE player_name=? AND season=? AND game_date<?
                            ORDER BY game_date DESC LIMIT 3
                        )
                    """, (pitcher_name, season, date_str)).fetchone()

                    if last3 and last3[0] is not None:
                        row["era_last3"]  = _safe(last3[0])
                        row["k9_last3"]   = _safe(last3[1])
                        row["xfip_last3"] = _safe(last3[2])

                    rows.append(row)

            if rows:
                stored = _upsert_pitcher_stats(conn, rows)
                conn.commit()
                n_stored += stored

            if i % 50 == 0:
                logger.info(f"  {date_str} — {i}/{len(dates)} dates, {n_stored} rows so far")

        total_stored += n_stored
        logger.success(f"  Season {season}: stored {n_stored} pitcher-start rows "
                       f"({total_skipped_dates} dates already done, "
                       f"{total_no_match} name misses)")

    conn.close()
    logger.success(f"\nBackfill complete: {total_stored} total pitcher rows stored")
    return {"total_stored": total_stored}


# ── Bullpen Workload Backfill ─────────────────────────────────────────────────

def backfill_bullpen_stats(start_season: int, end_season: int) -> dict:
    """
    Backfill mlb_bullpen_stats with all reliever appearances 2019–2024.

    For each completed game:
      - Calls statsapi.boxscore_data(game_pk) to get pitcher appearance order
      - pitchers[0] = starter, pitchers[1:] = relievers (by appearance order)
      - Stores one row per reliever per team per game

    Used by feature_engine.py to compute rolling bullpen workload (IP last 1/2/3 days).
    ~13,000 boxscore API calls total; takes ~90 minutes with rate limiting.
    """
    import time as _time
    conn = get_connection()

    total_stored = 0
    total_skipped = 0

    for season in range(start_season, end_season + 1):
        logger.info(f"\nSeason {season}: fetching bullpen data...")

        # Get all unique game dates that have completed MLB games this season
        rows = conn.execute("""
            SELECT DISTINCT game_date FROM games
            WHERE sport = 'MLB' AND season = ? AND home_score IS NOT NULL
            ORDER BY game_date
        """, (season,)).fetchall()
        dates = [r[0] for r in rows]
        logger.info(f"  {len(dates)} game dates to process")

        season_stored = 0
        season_skipped = 0

        for idx, date_str in enumerate(dates, 1):
            # Check if this date is already fully processed
            existing = conn.execute(
                "SELECT COUNT(*) FROM mlb_bullpen_stats WHERE game_date = ? AND season = ?",
                (date_str, season)
            ).fetchone()[0]
            if existing > 0:
                season_skipped += 1
                continue

            # Get games on this date from the MLB Stats API
            try:
                games_on_date = statsapi.schedule(date=date_str, sportId=1)
            except Exception as exc:
                logger.warning(f"  schedule() failed for {date_str}: {exc}")
                continue

            date_rows = []
            for game in games_on_date:
                if game.get("status") != "Final":
                    continue

                game_pk = game["game_id"]
                home_id = game.get("home_id")
                away_id = game.get("away_id")
                home_abbrev = STATSAPI_TEAM_IDS.get(home_id, "")
                away_abbrev = STATSAPI_TEAM_IDS.get(away_id, "")

                if not home_abbrev or not away_abbrev:
                    continue

                try:
                    box = statsapi.boxscore_data(game_pk)
                    _time.sleep(0.15)  # rate limit
                except Exception as exc:
                    logger.debug(f"  boxscore_data({game_pk}) failed: {exc}")
                    continue

                for side, team_abbrev in [("home", home_abbrev), ("away", away_abbrev)]:
                    pitcher_ids = box[side].get("pitchers", [])
                    players = box[side].get("players", {})

                    # Skip starter (index 0); rest are relievers
                    for pid in pitcher_ids[1:]:
                        player_key = f"ID{pid}"
                        pdata = players.get(player_key, {})
                        person = pdata.get("person", {})
                        stats = pdata.get("stats", {}).get("pitching", {})

                        ip_str = stats.get("inningsPitched", "0.0")
                        try:
                            ip = float(ip_str)
                        except (ValueError, TypeError):
                            ip = 0.0

                        if ip <= 0:
                            continue  # did not record an out

                        date_rows.append({
                            "game_date":   date_str,
                            "season":      season,
                            "team":        team_abbrev,
                            "game_pk":     game_pk,
                            "player_id":   pid,
                            "player_name": person.get("fullName", ""),
                            "ip":          ip,
                            "er":          stats.get("earnedRuns", 0) or 0,
                            "k":           stats.get("strikeOuts", 0) or 0,
                            "bb":          stats.get("baseOnBalls", 0) or 0,
                            "pitches":     stats.get("pitchesThrown", 0) or 0,
                        })

            # Insert all rows for this date
            for row in date_rows:
                try:
                    conn.execute("""
                        INSERT INTO mlb_bullpen_stats
                            (game_date, season, team, game_pk, player_id, player_name,
                             ip, er, k, bb, pitches)
                        VALUES (%(game_date)s, %(season)s, %(team)s, %(game_pk)s, %(player_id)s,
                                %(player_name)s, %(ip)s, %(er)s, %(k)s, %(bb)s, %(pitches)s)
                        ON CONFLICT (player_id, game_date, team) DO NOTHING
                    """, row)
                    season_stored += 1
                except Exception as exc:
                    logger.debug(f"  Insert failed: {exc}")

            conn.commit()

            if idx % 50 == 0:
                logger.info(f"  {date_str} — {idx}/{len(dates)} dates, "
                            f"{season_stored} rows so far")

        total_stored += season_stored
        total_skipped += season_skipped
        logger.success(f"  Season {season}: stored {season_stored} reliever rows "
                       f"({season_skipped} dates already done)")

    conn.close()
    logger.success(f"\nBullpen backfill complete: {total_stored} total rows stored")
    return {"total_stored": total_stored}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MLB stats ingestor")
    parser.add_argument("--season", type=int, help="MLB season year (default: current)")
    parser.add_argument("--date",   dest="as_of_date", help="As-of date YYYY-MM-DD")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill team stats for seasons START through END")
    parser.add_argument("--backfill-pitchers", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill per-start pitcher stats for seasons START through END")
    parser.add_argument("--backfill-bullpen", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill bullpen workload for seasons START through END")
    args = parser.parse_args()

    if args.backfill:
        backfill_mlb_stats(args.backfill[0], args.backfill[1])
    elif args.backfill_pitchers:
        backfill_pitcher_stats(args.backfill_pitchers[0], args.backfill_pitchers[1])
    elif args.backfill_bullpen:
        backfill_bullpen_stats(args.backfill_bullpen[0], args.backfill_bullpen[1])
    else:
        result = run_mlb_stats_ingestor(season=args.season, as_of_date=args.as_of_date)
        logger.info(f"Done: {result}")

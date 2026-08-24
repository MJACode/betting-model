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
import requests
import sqlite3
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


# ── MLB Stats API Team Stats (replaces FanGraphs for team batting/pitching) ───

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
MLB_API_HEADERS = {"User-Agent": "betting-model/1.0"}
# FIP constant (normalizes FIP to ERA scale; varies ~3.0-3.2 by season)
_FIP_CONSTANT = 3.1


def _fetch_mlb_api_batting(season: int) -> dict[str, dict]:
    """
    Pull team batting stats from MLB Stats API for the given season.
    Returns {team_abbrev: stat_dict} for all 30 MLB teams.
    """
    url = (
        f"{MLB_API_BASE}/teams/stats"
        f"?season={season}&stats=season&group=hitting&gameType=R&leagueIds=103,104"
    )
    try:
        resp = requests.get(url, headers=MLB_API_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        logger.error(f"MLB Stats API batting {season} failed: {exc}")
        return {}

    splits = resp.json().get("stats", [{}])[0].get("splits", [])
    result: dict[str, dict] = {}

    # Compute league-average wOBA for wRC+ approximation
    woba_list: list[float] = []
    for s in splits:
        st = s["stat"]
        pa = int(st.get("plateAppearances") or 0)
        if pa < 10:
            continue
        bb  = int(st.get("baseOnBalls") or 0)
        hbp = int(st.get("hitByPitch") or 0)
        h   = int(st.get("hits") or 0)
        d   = int(st.get("doubles") or 0)
        t   = int(st.get("triples") or 0)
        hr  = int(st.get("homeRuns") or 0)
        singles = max(h - d - t - hr, 0)
        woba = (0.69*bb + 0.72*hbp + 0.89*singles + 1.27*d + 1.62*t + 2.10*hr) / pa
        woba_list.append(woba)

    league_woba = float(np.mean(woba_list)) if woba_list else 0.320

    for s in splits:
        team_id   = s.get("team", {}).get("id")
        team_abbr = STATSAPI_TEAM_IDS.get(team_id)
        if not team_abbr:
            continue

        st  = s["stat"]
        pa  = int(st.get("plateAppearances") or 0)
        ab  = int(st.get("atBats") or 0)
        h   = int(st.get("hits") or 0)
        d   = int(st.get("doubles") or 0)
        t   = int(st.get("triples") or 0)
        hr  = int(st.get("homeRuns") or 0)
        bb  = int(st.get("baseOnBalls") or 0)
        hbp = int(st.get("hitByPitch") or 0)
        k   = int(st.get("strikeOuts") or 0)
        r   = int(st.get("runs") or 0)
        gp  = int(st.get("gamesPlayed") or 0)
        singles = max(h - d - t - hr, 0)

        slg_raw = st.get("slg", "0") or "0"
        avg_raw = st.get("avg", "0") or "0"
        slg = float(slg_raw) if slg_raw != ".---" else 0.0
        avg = float(avg_raw) if avg_raw != ".---" else 0.0

        woba = None
        wrc_plus = None
        if pa > 0:
            woba = round((0.69*bb + 0.72*hbp + 0.89*singles + 1.27*d + 1.62*t + 2.10*hr) / pa, 4)
            wrc_plus = round(100.0 * woba / league_woba, 1) if league_woba > 0 else None

        result[team_abbr] = {
            "games_played":  gp,
            "ops":           _safe(st.get("ops")),
            "wrc_plus":      wrc_plus,
            "woba":          woba,
            "k_pct":         round(k / pa, 4) if pa > 0 else None,
            "bb_pct":        round(bb / pa, 4) if pa > 0 else None,
            "iso":           round(slg - avg, 4) if slg and avg else None,
            "babip":         _safe(st.get("babip")),
            "runs_per_game": round(r / gp, 3) if gp > 0 else None,
        }

    return result


def _fetch_mlb_api_pitching(season: int) -> dict[str, dict]:
    """
    Pull team pitching stats from MLB Stats API for the given season.
    Returns {team_abbrev: stat_dict} for all 30 MLB teams.
    Computes FIP from components: (13*HR + 3*(BB+HBP) - 2*K) / IP + FIP_constant.
    """
    url = (
        f"{MLB_API_BASE}/teams/stats"
        f"?season={season}&stats=season&group=pitching&gameType=R&leagueIds=103,104"
    )
    try:
        resp = requests.get(url, headers=MLB_API_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        logger.error(f"MLB Stats API pitching {season} failed: {exc}")
        return {}

    splits = resp.json().get("stats", [{}])[0].get("splits", [])
    result: dict[str, dict] = {}

    for s in splits:
        team_id   = s.get("team", {}).get("id")
        team_abbr = STATSAPI_TEAM_IDS.get(team_id)
        if not team_abbr:
            continue

        st  = s["stat"]
        hr  = int(st.get("homeRuns") or 0)
        bb  = int(st.get("baseOnBalls") or 0)
        hbp = int(st.get("hitBatsmen") or 0)
        k   = int(st.get("strikeOuts") or 0)
        ip_str = st.get("inningsPitched") or "0"
        # Convert "119.1" style IP to decimal innings
        try:
            ip_parts = str(ip_str).split(".")
            ip = int(ip_parts[0]) + (int(ip_parts[1]) / 3 if len(ip_parts) > 1 else 0)
        except (ValueError, IndexError):
            ip = 0.0

        fip = None
        if ip > 0:
            fip = round((13*hr + 3*(bb + hbp) - 2*k) / ip + _FIP_CONSTANT, 4)

        result[team_abbr] = {
            "team_era":    _safe(st.get("era")),
            "bullpen_era": _safe(st.get("era")),   # team ERA proxy (no split available)
            "team_whip":   _safe(st.get("whip")),
            "team_fip":    fip,
        }

    return result


def _build_team_stats_rows(season: int, as_of_date: str,
                            conn: sqlite3.Connection) -> list[dict]:
    """
    Build mlb_team_stats rows using MLB Stats API (team batting + pitching).
    One row per team per as_of_date.
    """
    bat_data   = _fetch_mlb_api_batting(season)
    pitch_data = _fetch_mlb_api_pitching(season)

    if not bat_data and not pitch_data:
        logger.error(f"MLB Stats API returned no data for {season} — skipping team stats")
        return []

    all_teams = set(bat_data) | set(pitch_data)
    rows = []

    for team in sorted(all_teams):
        row: dict = {
            "team":       team,
            "season":     season,
            "as_of_date": as_of_date,
        }
        row.update(bat_data.get(team, {}))
        row.update(pitch_data.get(team, {}))

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


# ── Individual Pitcher Stats (MLB Stats API + Baseball Savant) ────────────────
# FanGraphs is permanently blocked. These two functions replace it.

def _fetch_mlb_api_pitcher_stats(season: int) -> dict[str, dict]:
    """
    Pull individual pitcher season stats from MLB Stats API.
    Returns {normalized_name: {player_id, player_name, era, k9, bb9, whip, hr9}}.
    Uses the /stats endpoint with playerPool=ALL which returns all pitchers.
    """
    url = (
        f"{MLB_API_BASE}/stats"
        f"?stats=season&season={season}&group=pitching&gameType=R"
        f"&playerPool=ALL&leagueIds=103,104&limit=2000"
    )
    try:
        resp = requests.get(url, headers=MLB_API_HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        logger.error(f"MLB Stats API individual pitching {season} failed: {exc}")
        return {}

    splits = resp.json().get("stats", [{}])[0].get("splits", [])
    result: dict[str, dict] = {}

    for s in splits:
        player = s.get("player", {})
        pid    = player.get("id")
        name   = player.get("fullName", "")
        if not name or not pid:
            continue

        st = s.get("stat", {})
        ip_str = st.get("inningsPitched", "0") or "0"
        # inningsPitched is like "127.2" — convert .1 = 1/3 IP, .2 = 2/3 IP
        try:
            parts = str(ip_str).split(".")
            ip = int(parts[0]) + int(parts[1]) / 3 if len(parts) == 2 else float(ip_str)
        except (ValueError, IndexError):
            ip = 0.0

        if ip < 1:
            continue

        k  = int(st.get("strikeOuts") or 0)
        bb = int(st.get("baseOnBalls") or 0)
        h  = int(st.get("hits") or 0)
        hr = int(st.get("homeRuns") or 0)

        era_raw = st.get("era", None)
        era     = _safe(era_raw)
        k9      = round(k / ip * 9, 3)   if ip > 0 else None
        bb9     = round(bb / ip * 9, 3)  if ip > 0 else None
        whip    = round((h + bb) / ip, 3) if ip > 0 else None
        hr9     = round(hr / ip * 9, 3)  if ip > 0 else None

        norm = _normalize_name(name)
        result[norm] = {
            "player_id":   str(pid),
            "player_name": name,
            "era":         era,
            "k9":          k9,
            "bb9":         bb9,
            "whip":        whip,
            "hr9":         hr9,
        }

    logger.debug(f"MLB API pitcher stats {season}: {len(result)} pitchers")
    return result


def _fetch_savant_pitcher_stats(season: int) -> dict[str, dict]:
    """
    Pull advanced pitcher stats (SwStr%, CSW%, xERA) from Baseball Savant.
    Returns {player_id_str: {swstr_pct, csw_pct, xfip}}.

    Baseball Savant uses MLBAM player IDs — same as MLB Stats API.
    xERA is used as the xFIP proxy (both capture expected ERA; scale is similar).
    """
    url = (
        "https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={season}&type=pitcher&filter=&sort=5&sortDir=desc"
        "&min=1&selections=whiff_percent,csw_percent,xera&chart=false&csv=true"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; betting-model/1.0)",
        "Accept":     "text/csv,application/json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        text = resp.text
    except Exception as exc:
        logger.warning(f"Baseball Savant pitcher stats {season} failed: {exc}")
        return {}

    result: dict[str, dict] = {}
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return {}

    header = [h.strip().strip('"') for h in lines[0].split(",")]
    try:
        id_col     = header.index("player_id")
        whiff_col  = header.index("whiff_percent")
        csw_col    = header.index("csw_percent")
        xera_col   = header.index("xera")
    except ValueError:
        logger.warning(f"Baseball Savant CSV missing expected columns for {season}: {header[:10]}")
        return {}

    for line in lines[1:]:
        cols = line.split(",")
        if len(cols) <= max(id_col, whiff_col, csw_col, xera_col):
            continue
        pid = cols[id_col].strip().strip('"')
        result[pid] = {
            "swstr_pct": _safe(cols[whiff_col]),
            "csw_pct":   _safe(cols[csw_col]),
            "xfip":      _safe(cols[xera_col]),   # xERA as xFIP proxy
        }

    logger.debug(f"Baseball Savant pitcher stats {season}: {len(result)} pitchers")
    return result


def _build_pitcher_rows(season: int, as_of_date: str,
                         conn) -> list[dict]:
    """
    Build mlb_pitcher_stats rows for today's probable starters.
    Season stats come from MLB Stats API + Baseball Savant.
    """
    if not STATSAPI_AVAILABLE:
        logger.warning("MLB-StatsAPI not available — skipping pitcher rows")
        return []

    mlb_stats    = _fetch_mlb_api_pitcher_stats(season)
    savant_stats = _fetch_savant_pitcher_stats(season)
    if not mlb_stats:
        # Early season: try prior season as baseline for pitcher stats
        fallback = season - 1
        logger.warning(
            f"No MLB API pitcher data for {season} — falling back to {fallback}"
        )
        mlb_stats    = _fetch_mlb_api_pitcher_stats(fallback)
        savant_stats = _fetch_savant_pitcher_stats(fallback)

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

            # Season stats from MLB Stats API, enriched by Baseball Savant
            if mlb_stats:
                p = mlb_stats.get(norm_pitcher)
                if p is None:
                    # Last-name fallback for hyphenated / suffix differences
                    last = norm_pitcher.split()[-1] if norm_pitcher else ""
                    p = next((v for k, v in mlb_stats.items()
                              if k.split()[-1] == last), None)
                if p:
                    pitcher_row.update({
                        "era":       p.get("era"),
                        "whip":      p.get("whip"),
                        "k9":        p.get("k9"),
                        "bb9":       p.get("bb9"),
                        "hr9":       p.get("hr9"),
                        "player_id": p.get("player_id"),
                    })
                    # Savant advanced stats (xFIP proxy, SwStr%, CSW%)
                    pid = p.get("player_id")
                    if pid and savant_stats:
                        sv = savant_stats.get(str(pid))
                        if sv:
                            pitcher_row.update({
                                "xfip":      sv.get("xfip"),
                                "swstr_pct": sv.get("swstr_pct"),
                                "csw_pct":   sv.get("csw_pct"),
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
            snap = f"{season}-01-01"  # Jan 1 so as_of_date <= any game_date is always true
        else:
            snap = date.today().isoformat()

        logger.info(f"Backfilling MLB stats for {season} → {snap}")
        try:
            result = run_mlb_stats_ingestor(season=season, as_of_date=snap)
            logger.success(f"  Season {season}: {result}")
        except Exception as exc:
            logger.error(f"  Season {season} failed: {exc}")

        time.sleep(2)   # rate limit between seasons


def backfill_pitcher_stats(start_season: int, end_season: int) -> dict:
    """
    Backfill historical per-start pitcher stats for seasons start_season–end_season.

    For each completed game in our DB:
      1. Calls statsapi.schedule(date) to identify the actual starters (1 call per date).
      2. Looks up each starter's season stats from MLB Stats API + Baseball Savant (1 call per season each).
      3. Computes rolling last-3 ERA/K9/xFIP from rows already stored for that pitcher.
      4. Stores into mlb_pitcher_stats.

    Safe to re-run: dates that already have pitcher rows are skipped.

    Note on look-ahead bias: MLB Stats API returns full-season stats, not stats as of game
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
        logger.info(f"\nSeason {season}: fetching MLB API + Baseball Savant pitcher stats...")
        mlb_stats    = _fetch_mlb_api_pitcher_stats(season)
        savant_stats = _fetch_savant_pitcher_stats(season)
        if not mlb_stats:
            logger.warning(f"  No MLB API data for {season} — names only, no advanced stats")

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

                    # Season stats from MLB Stats API + Baseball Savant
                    if mlb_stats:
                        norm_name = _normalize_name(pitcher_name)
                        p = mlb_stats.get(norm_name)
                        if p is None:
                            # Last-name fallback
                            last = norm_name.split()[-1] if norm_name else ""
                            p = next((v for k, v in mlb_stats.items()
                                      if k.split()[-1] == last), None)
                        if p:
                            row.update({
                                "era":       p.get("era"),
                                "whip":      p.get("whip"),
                                "k9":        p.get("k9"),
                                "bb9":       p.get("bb9"),
                                "hr9":       p.get("hr9"),
                                "player_id": p.get("player_id"),
                            })
                            # Savant advanced stats
                            pid = p.get("player_id")
                            if pid and savant_stats:
                                sv = savant_stats.get(str(pid))
                                if sv:
                                    row.update({
                                        "xfip":      sv.get("xfip"),
                                        "swstr_pct": sv.get("swstr_pct"),
                                        "csw_pct":   sv.get("csw_pct"),
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

def _ingest_bullpen_for_date(conn, date_str: str, season: int) -> int:
    """
    Fetch and store all reliever appearances for one game date.

    For each Final game on the date:
      - Calls statsapi.boxscore_data(game_pk) to get pitcher appearance order
      - pitchers[0] = starter, pitchers[1:] = relievers (by appearance order)
      - Stores one row per reliever per team per game

    Idempotent via ON CONFLICT DO NOTHING. Returns rows inserted (attempted).
    Shared by backfill_bullpen_stats and run_bullpen_ingestor.
    """
    import time as _time

    try:
        games_on_date = statsapi.schedule(date=date_str, sportId=1)
    except Exception as exc:
        logger.warning(f"  schedule() failed for {date_str}: {exc}")
        return 0

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

    stored = 0
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
            stored += 1
        except Exception as exc:
            logger.debug(f"  Insert failed: {exc}")

    conn.commit()
    return stored


def backfill_bullpen_stats(start_season: int, end_season: int) -> dict:
    """
    Backfill mlb_bullpen_stats with all reliever appearances for the seasons.

    Used by feature_engine.py to compute rolling bullpen workload (IP last 1/2/3 days).
    ~13,000 boxscore API calls total; takes ~90 minutes with rate limiting.
    """
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

            season_stored += _ingest_bullpen_for_date(conn, date_str, season)

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


def run_bullpen_ingestor(run_date: str | None = None,
                         max_catchup_days: int = 120) -> dict:
    """
    Daily bullpen workload ingestion — SELF-HEALING.

    Processes every completed MLB game date from the latest date already in
    mlb_bullpen_stats through yesterday (relative to run_date), bounded by
    max_catchup_days. A missed day — or a long outage like Apr–Jul 2026, when
    no daily bullpen step existed and the table silently froze at 2026-04-14 —
    backfills automatically on the next pipeline run.

    The boundary date (= current max) is re-processed each run so a partially
    ingested date completes; ON CONFLICT DO NOTHING makes that safe.

    Feature impact: home/away_bullpen_ip_last1/3 and d_bullpen_ip_last3 read
    this table via _get_bullpen_workload, which returns 0.0 when rows are
    missing — i.e. a stale table silently tells the model every bullpen is
    fully rested, biasing totals predictions low.
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        yesterday = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        cutoff = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=max_catchup_days)).strftime("%Y-%m-%d")

        max_done = conn.execute(
            "SELECT MAX(game_date) FROM mlb_bullpen_stats"
        ).fetchone()[0]
        start_from = max(str(max_done), cutoff) if max_done else cutoff

        rows = conn.execute("""
            SELECT DISTINCT game_date, season FROM games
            WHERE sport = 'MLB'
              AND home_score IS NOT NULL
              AND game_date >= ?
              AND game_date <= ?
            ORDER BY game_date
        """, (start_from, yesterday)).fetchall()

        if not rows:
            logger.info(f"Bullpen ingest: no completed game dates in "
                        f"[{start_from} .. {yesterday}] — nothing to do")
            return {"dates": 0, "stored": 0}

        logger.info(f"Bullpen ingest: {len(rows)} game date(s) "
                    f"[{rows[0][0]} .. {rows[-1][0]}]")
        total = 0
        for date_str, season in rows:
            total += _ingest_bullpen_for_date(conn, str(date_str), int(season))

        logger.success(f"Bullpen ingest complete: {total} reliever rows "
                       f"across {len(rows)} date(s)")
        return {"dates": len(rows), "stored": total}
    finally:
        conn.close()


# ── F5 Linescore Backfill ─────────────────────────────────────────────────

def backfill_f5_scores(start_season: int, end_season: int) -> dict:
    """
    Backfill first-5-innings scores (home_score_f5, away_score_f5) for all
    MLB games in the given season range.

    Uses the MLB Stats API schedule endpoint with hydrate=linescore to get
    inning-by-inning run data. Sums runs through innings 1-5 for each team.

    Games that already have F5 scores populated are skipped (idempotent).
    Games with fewer than 5 complete innings (rain-shortened, etc.) are skipped.

    Usage:
        python -m data.ingestors.mlb_stats_ingestor --backfill-f5 2019 2025
    """
    conn = get_connection()
    total_updated = 0

    for season in range(start_season, end_season + 1):
        logger.info(f"\n{'─'*40}")
        logger.info(f"F5 linescore backfill: season {season}")

        # Find games that need F5 scores
        games = conn.execute("""
            SELECT game_id, game_date, home_team, away_team
            FROM games
            WHERE sport = 'MLB'
              AND season = %s
              AND home_score IS NOT NULL
              AND home_score_f5 IS NULL
            ORDER BY game_date
        """, (season,)).fetchall()

        if not games:
            logger.info(f"  Season {season}: all games already have F5 scores")
            continue

        logger.info(f"  {len(games)} games need F5 scores")

        # Group games by date for batch API calls
        dates = sorted(set(g[1] for g in games))
        season_updated = 0

        for idx, date_str in enumerate(dates):
            try:
                url = (
                    f"https://statsapi.mlb.com/api/v1/schedule"
                    f"?sportId=1&date={date_str}&hydrate=linescore"
                )
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning(f"  {date_str}: API call failed: {exc}")
                continue

            api_games = []
            for d in data.get("dates", []):
                api_games.extend(d.get("games", []))

            for api_game in api_games:
                home_id = api_game.get("teams", {}).get("home", {}).get("team", {}).get("id")
                away_id = api_game.get("teams", {}).get("away", {}).get("team", {}).get("id")
                home_abbrev = STATSAPI_TEAM_IDS.get(home_id, "")
                away_abbrev = STATSAPI_TEAM_IDS.get(away_id, "")

                if not home_abbrev or not away_abbrev:
                    continue

                game_id = f"MLB_{date_str}_{away_abbrev}_{home_abbrev}"

                linescore = api_game.get("linescore", {})
                innings = linescore.get("innings", [])

                # Need at least 5 complete innings
                if len(innings) < 5:
                    continue

                home_f5 = 0
                away_f5 = 0
                valid = True
                for inn in innings[:5]:
                    h_runs = inn.get("home", {}).get("runs")
                    a_runs = inn.get("away", {}).get("runs")
                    if h_runs is None or a_runs is None:
                        valid = False
                        break
                    home_f5 += h_runs
                    away_f5 += a_runs

                if not valid:
                    continue

                try:
                    conn.execute("""
                        UPDATE games
                        SET home_score_f5 = %s, away_score_f5 = %s
                        WHERE game_id = %s AND home_score_f5 IS NULL
                    """, (home_f5, away_f5, game_id))
                    season_updated += 1
                except Exception as exc:
                    logger.debug(f"  Update failed for {game_id}: {exc}")

            conn.commit()

            if idx % 50 == 0:
                logger.info(f"  {date_str} — {idx+1}/{len(dates)} dates, "
                            f"{season_updated} games updated")

            # Brief sleep to avoid hammering the API
            time.sleep(0.1)

        total_updated += season_updated
        logger.success(f"  Season {season}: updated {season_updated} games with F5 scores")

    conn.close()
    logger.success(f"\nF5 backfill complete: {total_updated} games updated")
    return {"total_updated": total_updated}


# ── Player Game Log Backfill ──────────────────────────────────────────────────

def _safe_int(val) -> int | None:
    """Convert a value to int, returning None on failure."""
    try:
        return int(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    """Convert a value to float, returning None on failure."""
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def _upsert_player_game_log(conn: DBConnection, rows: list[dict]) -> int:
    """Upsert rows into player_game_log. UNIQUE(player_id, game_id, player_type)."""
    if not rows:
        return 0
    sql = """
        INSERT INTO player_game_log (
            player_id, player_name, team, player_type, game_id, game_date, season,
            innings_pitched, pitches, is_starter,
            p_strikeouts, p_walks, p_hits_allowed, p_earned_runs, p_home_runs,
            at_bats, hits, doubles, triples, home_runs, rbi, runs,
            walks, strikeouts, stolen_bases, total_bases, batting_order
        ) VALUES (
            %(player_id)s, %(player_name)s, %(team)s, %(player_type)s,
            %(game_id)s, %(game_date)s, %(season)s,
            %(innings_pitched)s, %(pitches)s, %(is_starter)s,
            %(p_strikeouts)s, %(p_walks)s, %(p_hits_allowed)s,
            %(p_earned_runs)s, %(p_home_runs)s,
            %(at_bats)s, %(hits)s, %(doubles)s, %(triples)s,
            %(home_runs)s, %(rbi)s, %(runs)s,
            %(walks)s, %(strikeouts)s, %(stolen_bases)s,
            %(total_bases)s, %(batting_order)s
        )
        ON CONFLICT (player_id, game_id, player_type) DO NOTHING
    """
    conn.executemany(sql, rows)
    return len(rows)


def backfill_player_game_log(start_season: int, end_season: int) -> dict:
    """
    Backfill player_game_log with per-game pitcher and batter stats for all
    completed MLB games in the given season range.

    For each game:
      - Calls statsapi.boxscore_data(game_pk) — same call as bullpen backfill
      - Extracts starter + reliever stats (IP, K, BB, H, ER, HR, pitches)
      - Extracts batter stats (AB, H, 2B, 3B, HR, RBI, R, BB, K, SB, TB)
      - Stores batting_order position from the lineup

    Idempotent: games that already have player_game_log rows are skipped.
    Rate: ~0.15s per boxscore call. With ~2,000 games/season × 7 seasons
    = ~14,000 calls, ~35 minutes total.

    Usage:
        python -m data.ingestors.mlb_stats_ingestor --backfill-game-log 2019 2025
    """
    import time as _time
    total_stored = 0
    total_skipped = 0

    for season in range(start_season, end_season + 1):
        logger.info(f"\nSeason {season}: building player game log...")

        # Open a fresh connection per season — Supabase drops long-lived connections
        # when a season takes 15–30 minutes to process.
        conn = get_connection()
        try:
            # All completed game dates this season
            dates = [r[0] for r in conn.execute("""
                SELECT DISTINCT game_date FROM games
                WHERE sport = 'MLB' AND season = %s AND home_score IS NOT NULL
                ORDER BY game_date
            """, (season,)).fetchall()]

            logger.info(f"  {len(dates)} game dates to process")

            # Build set of game_ids actually in our DB for this season
            # (some MLB API games — Tokyo series, international — won't be in our table)
            valid_game_ids = set(r[0] for r in conn.execute(
                "SELECT game_id FROM games WHERE sport = 'MLB' AND season = %s",
                (season,)
            ).fetchall())

            season_stored = 0
            season_skipped = 0

            for idx, date_str in enumerate(dates, 1):
                # Skip if we already have rows for this date
                existing = conn.execute(
                    "SELECT COUNT(*) FROM player_game_log WHERE game_date = %s AND season = %s",
                    (date_str, season)
                ).fetchone()[0]
                if existing > 0:
                    season_skipped += 1
                    continue

                try:
                    games_on_date = statsapi.schedule(date=date_str, sportId=1)
                except Exception as exc:
                    logger.warning(f"  schedule() failed {date_str}: {exc}")
                    continue

                date_rows = []

                for game in games_on_date:
                    if game.get("status") != "Final":
                        continue

                    game_pk     = game["game_id"]
                    home_abbrev = STATSAPI_TEAM_IDS.get(game.get("home_id"), "")
                    away_abbrev = STATSAPI_TEAM_IDS.get(game.get("away_id"), "")
                    if not home_abbrev or not away_abbrev:
                        continue

                    game_id = f"MLB_{date_str}_{away_abbrev}_{home_abbrev}"

                    try:
                        box = statsapi.boxscore_data(game_pk)
                        _time.sleep(0.15)
                    except Exception as exc:
                        logger.debug(f"  boxscore_data({game_pk}) failed: {exc}")
                        continue

                    for side, team_abbrev in [("home", home_abbrev), ("away", away_abbrev)]:
                        players           = box[side].get("players", {})
                        pitcher_ids       = box[side].get("pitchers", [])
                        batter_ids        = box[side].get("batters", [])
                        batting_order_ids = box[side].get("battingOrder", [])

                        # ── Pitcher rows ──────────────────────────────────────
                        for order_idx, pid in enumerate(pitcher_ids):
                            player_key = f"ID{pid}"
                            pdata  = players.get(player_key, {})
                            person = pdata.get("person", {})
                            stats  = pdata.get("stats", {}).get("pitching", {})

                            ip_str = stats.get("inningsPitched", "0.0") or "0.0"
                            try:
                                ip = float(ip_str)
                            except (ValueError, TypeError):
                                ip = 0.0

                            if ip <= 0:
                                continue  # didn't record an out

                            date_rows.append({
                                "player_id":      str(pid),
                                "player_name":    person.get("fullName", ""),
                                "team":           team_abbrev,
                                "player_type":    "pitcher",
                                "game_id":        game_id,
                                "game_date":      date_str,
                                "season":         season,
                                "innings_pitched": round(ip, 2),
                                "pitches":        _safe_int(stats.get("numberOfPitches")),
                                "is_starter":     order_idx == 0,
                                "p_strikeouts":   _safe_int(stats.get("strikeOuts")),
                                "p_walks":        _safe_int(stats.get("baseOnBalls")),
                                "p_hits_allowed": _safe_int(stats.get("hits")),
                                "p_earned_runs":  _safe_int(stats.get("earnedRuns")),
                                "p_home_runs":    _safe_int(stats.get("homeRuns")),
                                "at_bats": None, "hits": None, "doubles": None,
                                "triples": None, "home_runs": None, "rbi": None,
                                "runs": None, "walks": None, "strikeouts": None,
                                "stolen_bases": None, "total_bases": None,
                                "batting_order": None,
                            })

                        # ── Batter rows ───────────────────────────────────────
                        for pid in batter_ids:
                            player_key = f"ID{pid}"
                            pdata  = players.get(player_key, {})
                            person = pdata.get("person", {})
                            stats  = pdata.get("stats", {}).get("batting", {})

                            ab = _safe_int(stats.get("atBats"))
                            if ab is None:
                                continue

                            h  = _safe_int(stats.get("hits")) or 0
                            d  = _safe_int(stats.get("doubles")) or 0
                            t  = _safe_int(stats.get("triples")) or 0
                            hr = _safe_int(stats.get("homeRuns")) or 0
                            tb = h + d + (2 * t) + (3 * hr)

                            try:
                                order_pos = batting_order_ids.index(pid) + 1
                            except ValueError:
                                order_pos = None

                            date_rows.append({
                                "player_id":   str(pid),
                                "player_name": person.get("fullName", ""),
                                "team":        team_abbrev,
                                "player_type": "batter",
                                "game_id":     game_id,
                                "game_date":   date_str,
                                "season":      season,
                                "innings_pitched": None, "pitches": None,
                                "is_starter": None, "p_strikeouts": None,
                                "p_walks": None, "p_hits_allowed": None,
                                "p_earned_runs": None, "p_home_runs": None,
                                "at_bats":      ab,
                                "hits":         h,
                                "doubles":      d,
                                "triples":      t,
                                "home_runs":    hr,
                                "rbi":          _safe_int(stats.get("rbi")),
                                "runs":         _safe_int(stats.get("runs")),
                                "walks":        _safe_int(stats.get("baseOnBalls")),
                                "strikeouts":   _safe_int(stats.get("strikeOuts")),
                                "stolen_bases": _safe_int(stats.get("stolenBases")),
                                "total_bases":  tb,
                                "batting_order": order_pos,
                            })

                # Only insert rows for games that are in our games table
                valid_rows = [r for r in date_rows if r["game_id"] in valid_game_ids]
                if valid_rows:
                    stored = _upsert_player_game_log(conn, valid_rows)
                    conn.commit()
                    season_stored += stored

                if idx % 50 == 0:
                    logger.info(f"  {date_str} — {idx}/{len(dates)} dates, "
                                f"{season_stored} rows so far")

            total_stored  += season_stored
            total_skipped += season_skipped
            logger.success(f"  Season {season}: {season_stored} rows stored "
                           f"({season_skipped} dates already done)")
        finally:
            conn.close()

    logger.success(f"\nGame log backfill complete: {total_stored} total rows")
    return {"total_stored": total_stored}


def ingest_game_log_for_date(game_date: str) -> dict:
    """
    Ingest player_game_log rows for a single completed game date.

    Designed for daily pipeline use — call with yesterday's date after
    games are final so that rolling stats are current for today's prop scoring.

    Idempotent per GAME: a game already in player_game_log costs no boxscore
    call, so this is safe to run repeatedly through a slate and will fill in
    each game as it goes final.

    Args:
        game_date: ISO date string YYYY-MM-DD

    Returns:
        {"game_date": str, "stored": int, "skipped": bool}
        ("skipped" is retained for callers; it is now always False — the
         skipping happens per game inside the loop.)
    """
    import time as _time

    season = int(game_date[:4])
    conn = get_connection()
    try:
        # Skip PER GAME, not per date. The old check bailed out whenever the date
        # had any rows at all, which is correct for a next-morning run but
        # poisons the date if this is ever called mid-slate: the three games that
        # were final at 7pm would land, and every later call — including the next
        # morning's — would skip the date and permanently strand the other
        # twelve, taking their prop settlement with them.
        done_game_ids = {r[0] for r in conn.execute(
            "SELECT DISTINCT game_id FROM player_game_log WHERE game_date = %s AND season = %s",
            (game_date, season)
        ).fetchall()}

        # Build set of valid game_ids for dedup
        valid_game_ids = set(r[0] for r in conn.execute(
            "SELECT game_id FROM games WHERE sport = 'MLB' AND season = %s",
            (season,)
        ).fetchall())

        try:
            games_on_date = statsapi.schedule(date=game_date, sportId=1)
        except Exception as exc:
            logger.warning(f"Game log {game_date}: schedule() failed — {exc}")
            return {"game_date": game_date, "stored": 0, "skipped": False}

        date_rows = []

        for game in games_on_date:
            if game.get("status") != "Final":
                continue

            game_pk     = game["game_id"]
            home_abbrev = STATSAPI_TEAM_IDS.get(game.get("home_id"), "")
            away_abbrev = STATSAPI_TEAM_IDS.get(game.get("away_id"), "")
            if not home_abbrev or not away_abbrev:
                continue

            game_id = f"MLB_{game_date}_{away_abbrev}_{home_abbrev}"
            if game_id in done_game_ids:
                continue          # already ingested — costs no boxscore call

            try:
                box = statsapi.boxscore_data(game_pk)
                _time.sleep(0.15)
            except Exception as exc:
                logger.debug(f"  boxscore_data({game_pk}) failed: {exc}")
                continue

            for side, team_abbrev in [("home", home_abbrev), ("away", away_abbrev)]:
                players           = box[side].get("players", {})
                pitcher_ids       = box[side].get("pitchers", [])
                batter_ids        = box[side].get("batters", [])
                batting_order_ids = box[side].get("battingOrder", [])

                for order_idx, pid in enumerate(pitcher_ids):
                    player_key = f"ID{pid}"
                    pdata  = players.get(player_key, {})
                    person = pdata.get("person", {})
                    stats  = pdata.get("stats", {}).get("pitching", {})

                    ip_str = stats.get("inningsPitched", "0.0") or "0.0"
                    try:
                        ip = float(ip_str)
                    except (ValueError, TypeError):
                        ip = 0.0

                    if ip <= 0:
                        continue

                    date_rows.append({
                        "player_id":      str(pid),
                        "player_name":    person.get("fullName", ""),
                        "team":           team_abbrev,
                        "player_type":    "pitcher",
                        "game_id":        game_id,
                        "game_date":      game_date,
                        "season":         season,
                        "innings_pitched": round(ip, 2),
                        "pitches":        _safe_int(stats.get("numberOfPitches")),
                        "is_starter":     order_idx == 0,
                        "p_strikeouts":   _safe_int(stats.get("strikeOuts")),
                        "p_walks":        _safe_int(stats.get("baseOnBalls")),
                        "p_hits_allowed": _safe_int(stats.get("hits")),
                        "p_earned_runs":  _safe_int(stats.get("earnedRuns")),
                        "p_home_runs":    _safe_int(stats.get("homeRuns")),
                        "at_bats": None, "hits": None, "doubles": None,
                        "triples": None, "home_runs": None, "rbi": None,
                        "runs": None, "walks": None, "strikeouts": None,
                        "stolen_bases": None, "total_bases": None,
                        "batting_order": None,
                    })

                for pid in batter_ids:
                    player_key = f"ID{pid}"
                    pdata  = players.get(player_key, {})
                    person = pdata.get("person", {})
                    stats  = pdata.get("stats", {}).get("batting", {})

                    ab = _safe_int(stats.get("atBats"))
                    if ab is None:
                        continue

                    h  = _safe_int(stats.get("hits")) or 0
                    d  = _safe_int(stats.get("doubles")) or 0
                    t  = _safe_int(stats.get("triples")) or 0
                    hr = _safe_int(stats.get("homeRuns")) or 0
                    tb = h + d + (2 * t) + (3 * hr)

                    try:
                        order_pos = batting_order_ids.index(pid) + 1
                    except ValueError:
                        order_pos = None

                    date_rows.append({
                        "player_id":   str(pid),
                        "player_name": person.get("fullName", ""),
                        "team":        team_abbrev,
                        "player_type": "batter",
                        "game_id":     game_id,
                        "game_date":   game_date,
                        "season":      season,
                        "innings_pitched": None, "pitches": None,
                        "is_starter": None, "p_strikeouts": None,
                        "p_walks": None, "p_hits_allowed": None,
                        "p_earned_runs": None, "p_home_runs": None,
                        "at_bats":      ab,
                        "hits":         h,
                        "doubles":      d,
                        "triples":      t,
                        "home_runs":    hr,
                        "rbi":          _safe_int(stats.get("rbi")),
                        "runs":         _safe_int(stats.get("runs")),
                        "walks":        _safe_int(stats.get("baseOnBalls")),
                        "strikeouts":   _safe_int(stats.get("strikeOuts")),
                        "stolen_bases": _safe_int(stats.get("stolenBases")),
                        "total_bases":  tb,
                        "batting_order": order_pos,
                    })

        valid_rows = [r for r in date_rows if r["game_id"] in valid_game_ids]
        stored = 0
        if valid_rows:
            stored = _upsert_player_game_log(conn, valid_rows)
            conn.commit()

        logger.info(f"Game log {game_date}: {stored} rows stored "
                    f"({len(games_on_date)} games on slate)")
        return {"game_date": game_date, "stored": stored, "skipped": False}

    finally:
        conn.close()


def backfill_player_handedness() -> dict:
    """
    Populate player_handedness for every unique player_id in player_game_log.

    Phase 1: fetch all player IDs from DB (quick, close connection).
    Phase 2: fetch bat/throw hand from MLB Stats API /people endpoint in batches
             of 50 — no DB connection held open during slow HTTP calls.
    Phase 3: bulk insert all results in a single fast DB session.

    Safe to re-run (INSERT ... ON CONFLICT DO UPDATE).
    """
    # Phase 1: get unique player IDs
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT player_id FROM player_game_log"
        ).fetchall()
    finally:
        conn.close()

    player_ids = [str(r[0]) for r in rows]
    logger.info(f"Fetching handedness for {len(player_ids)} unique players "
                f"via MLB Stats API /people endpoint...")

    # Phase 2: fetch handedness from MLB API (no DB connection held)
    hand_data: list[tuple] = []   # [(player_id, bat_hand, throw_hand), ...]
    batch_size = 50
    fetch_failed = 0

    for i in range(0, len(player_ids), batch_size):
        batch   = player_ids[i: i + batch_size]
        ids_csv = ",".join(batch)
        try:
            resp = requests.get(
                "https://statsapi.mlb.com/api/v1/people",
                params={"personIds": ids_csv},
                timeout=20,
            )
            if resp.status_code != 200:
                logger.warning(f"  Batch {i//batch_size}: HTTP {resp.status_code}")
                fetch_failed += len(batch)
                continue
            for person in resp.json().get("people", []):
                pid        = str(person.get("id", ""))
                bat_hand   = (person.get("batSide")   or {}).get("code")
                throw_hand = (person.get("pitchHand") or {}).get("code")
                hand_data.append((pid, bat_hand, throw_hand))
        except Exception as exc:
            logger.warning(f"  Batch {i//batch_size} fetch failed: {exc}")
            fetch_failed += len(batch)

        if (i // batch_size) % 10 == 0:
            logger.info(f"  API progress: {len(hand_data)} fetched, "
                        f"batch {i//batch_size+1}/{(len(player_ids)-1)//batch_size+1}")

    logger.info(f"API phase complete: {len(hand_data)} players fetched, "
                f"{fetch_failed} failed")

    # Phase 3: insert in committed chunks of 200 rows to stay under Supabase statement timeout.
    # execute_values generates one multi-row VALUES statement per chunk — much faster than
    # execute_batch, and each chunk commits immediately so no single statement times out.
    from psycopg2.extras import execute_values
    CHUNK = 200
    inserted = 0
    insert_failed = 0
    conn = get_connection()
    try:
        for chunk_start in range(0, len(hand_data), CHUNK):
            chunk = hand_data[chunk_start: chunk_start + CHUNK]
            cur = conn._conn.cursor()
            execute_values(cur, """
                INSERT INTO player_handedness (player_id, bat_hand, throw_hand)
                VALUES %s
                ON CONFLICT (player_id) DO UPDATE SET
                    bat_hand   = EXCLUDED.bat_hand,
                    throw_hand = EXCLUDED.throw_hand,
                    updated_at = NOW()::TEXT
            """, chunk)
            cur.close()
            conn.commit()
            inserted += len(chunk)
            if inserted % 1000 == 0 or inserted == len(hand_data):
                logger.info(f"  Insert progress: {inserted}/{len(hand_data)}")
    except Exception as exc:
        conn.rollback()
        logger.error(f"Bulk insert failed at row {inserted}: {exc}")
        insert_failed = len(hand_data) - inserted
    finally:
        conn.close()

    logger.success(f"player_handedness: {inserted} upserted, "
                   f"{fetch_failed + insert_failed} failed")
    return {"inserted": inserted, "failed": fetch_failed + insert_failed}


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
    parser.add_argument("--backfill-f5", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill first-5-innings scores for seasons START through END")
    parser.add_argument("--backfill-game-log", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill player_game_log (pitcher + batter per-game stats)")
    parser.add_argument("--backfill-hands", action="store_true",
                        help="Populate player_handedness (bat/throw hand) for all known players")
    args = parser.parse_args()

    if args.backfill:
        backfill_mlb_stats(args.backfill[0], args.backfill[1])
    elif args.backfill_pitchers:
        backfill_pitcher_stats(args.backfill_pitchers[0], args.backfill_pitchers[1])
    elif args.backfill_bullpen:
        backfill_bullpen_stats(args.backfill_bullpen[0], args.backfill_bullpen[1])
    elif args.backfill_f5:
        backfill_f5_scores(args.backfill_f5[0], args.backfill_f5[1])
    elif args.backfill_game_log:
        backfill_player_game_log(args.backfill_game_log[0], args.backfill_game_log[1])
    elif args.backfill_hands:
        backfill_player_handedness()
    else:
        result = run_mlb_stats_ingestor(season=args.season, as_of_date=args.as_of_date)

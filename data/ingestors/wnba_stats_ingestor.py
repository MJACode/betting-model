"""
wnba_stats_ingestor.py — WNBA team + player stats via nba_api (LeagueID='10').

What it builds:
  • games                 — one row per WNBA game with final scores + home_win
  • wnba_player_game_log   — per-player per-game box score (feeds prop models)
  • wnba_team_stats        — season-to-date team stats snapshot (feeds game models)

Data source:
  • nba_api (https://github.com/swar/nba_api) wraps stats.nba.com. WNBA data is
    exposed via league_id='10'. Free, no API key. The LeagueGameLog endpoint
    returns every team-game (player_or_team='T') or player-game (='P') for a
    season in a single call.

NOTE: stats.nba.com is not reachable from the sandbox allowlist, and nba_api is
not installed here — run the backfill / daily refresh on an open-network machine
(Matt's laptop or GitHub Actions), same as the MLB/NHL backfills.

Usage:
    python -m data.ingestors.wnba_stats_ingestor --backfill 2019 2025
    python -m data.ingestors.wnba_stats_ingestor --season 2025
    python -m data.ingestors.wnba_stats_ingestor --date 2025-06-01
"""

import argparse
import time
from datetime import date, datetime
from pathlib import Path
import sys

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.db import get_connection, DBConnection

# ── Safe Imports ──────────────────────────────────────────────────────────────

try:
    from nba_api.stats.endpoints import leaguegamelog
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False
    logger.warning("nba_api not installed — run: pip install nba_api")

WNBA_LEAGUE_ID = "10"

# Be polite to stats.nba.com — it rate-limits aggressively.
REQUEST_SLEEP = 0.6  # seconds between season calls
NBA_TIMEOUT = 60

# ── Team Abbreviation Normalization ───────────────────────────────────────────
# stats.nba.com uses its own WNBA abbreviations; normalise to our canonical set
# (config.WNBA_TEAMS). Covers 2019-2025 franchises incl. the 2025 Golden State
# Valkyries expansion. TEAM_NAME fallback handles anything missed here.

_WNBA_ABBREV_MAP = {
    "ATL": "ATL",
    "CHI": "CHI",
    "CON": "CON", "CONN": "CON",
    "DAL": "DAL",
    "GSV": "GSV", "GS": "GSV",
    "IND": "IND",
    "LAS": "LA",  "LA": "LA",            # Los Angeles Sparks
    "LVA": "LV",  "LV": "LV",  "VEG": "LV",  # Las Vegas Aces
    "MIN": "MIN",
    "NYL": "NY",  "NY": "NY",            # New York Liberty
    "PHO": "PHX", "PHX": "PHX",          # Phoenix Mercury
    "SEA": "SEA",
    "WAS": "WAS", "WSH": "WAS",          # Washington Mystics
}

_WNBA_NAME_MAP = {
    "Atlanta Dream": "ATL",
    "Chicago Sky": "CHI",
    "Connecticut Sun": "CON",
    "Dallas Wings": "DAL",
    "Golden State Valkyries": "GSV",
    "Indiana Fever": "IND",
    "Las Vegas Aces": "LV",
    "Los Angeles Sparks": "LA",
    "Minnesota Lynx": "MIN",
    "New York Liberty": "NY",
    "Phoenix Mercury": "PHX",
    "Seattle Storm": "SEA",
    "Washington Mystics": "WAS",
}


def _norm_wnba(abbrev: str, name: str = "") -> str | None:
    a = (abbrev or "").upper().strip()
    if a in _WNBA_ABBREV_MAP:
        return _WNBA_ABBREV_MAP[a]
    if name and name in _WNBA_NAME_MAP:
        return _WNBA_NAME_MAP[name]
    if a:
        logger.warning(f"Unknown WNBA team abbrev '{abbrev}' (name='{name}') — using '{a}'")
        return a
    return None


def _build_game_id(game_date: str, away: str, home: str) -> str:
    """Same format as odds_ingestor / sbr_loader: WNBA_{date}_{away}_{home}."""
    return f"WNBA_{game_date}_{away}_{home}"


def _safe(val, ndigits: int = 4) -> float | None:
    try:
        f = float(val)
        return None if (f != f) else round(f, ndigits)
    except (TypeError, ValueError):
        return None


def _to_date(raw: str) -> str:
    """Normalise nba_api GAME_DATE (e.g. '2024-05-14' or '2024-05-14T00:00:00')."""
    s = str(raw)[:10]
    return s


def _to_int(val) -> int | None:
    try:
        if val is None or (isinstance(val, float) and val != val):
            return None
        return int(val)
    except (TypeError, ValueError):
        return None


# ── API fetch ─────────────────────────────────────────────────────────────────

def _fetch_league_game_log(season: int, player_or_team: str):
    """
    Fetch a full season of WNBA game logs.

    player_or_team: 'T' (team-game rows) or 'P' (player-game rows).
    Returns a pandas DataFrame (may be empty).
    """
    if not NBA_API_AVAILABLE:
        raise RuntimeError("nba_api not installed — cannot fetch WNBA stats")

    resp = leaguegamelog.LeagueGameLog(
        league_id=WNBA_LEAGUE_ID,
        season=str(season),
        season_type_all_star="Regular Season",
        player_or_team_abbreviation=player_or_team,
        timeout=NBA_TIMEOUT,
    )
    df = resp.get_data_frames()[0]
    return df


# ── Games (from team game log) ─────────────────────────────────────────────────

def _pair_games(team_df) -> dict:
    """
    Group the team-game DataFrame into one record per game.
    Returns {nba_game_id: {date, home, away, home_pts, away_pts, season}}.
    MATCHUP encodes location: 'LVA vs. NYL' = home, 'NYL @ LVA' = away.
    """
    games: dict[str, dict] = {}
    for row in team_df.itertuples(index=False):
        gid = str(getattr(row, "GAME_ID", ""))
        if not gid:
            continue
        team = _norm_wnba(getattr(row, "TEAM_ABBREVIATION", ""),
                          getattr(row, "TEAM_NAME", ""))
        matchup = str(getattr(row, "MATCHUP", ""))
        pts = _to_int(getattr(row, "PTS", None))
        gdate = _to_date(getattr(row, "GAME_DATE", ""))
        is_home = "vs." in matchup  # '@' means away

        g = games.setdefault(gid, {"date": gdate, "season": int(gdate[:4])})
        if is_home:
            g["home"] = team
            g["home_pts"] = pts
        else:
            g["away"] = team
            g["away_pts"] = pts
    # keep only complete pairings
    return {k: v for k, v in games.items()
            if v.get("home") and v.get("away")}


def _build_game_rows(paired: dict) -> tuple[list[dict], dict]:
    """
    Build games rows and a map nba_game_id → our game_id.
    """
    rows = []
    id_map: dict[str, str] = {}
    for nba_gid, g in paired.items():
        gid = _build_game_id(g["date"], g["away"], g["home"])
        id_map[nba_gid] = gid
        home_pts, away_pts = g.get("home_pts"), g.get("away_pts")
        home_win = None
        if home_pts is not None and away_pts is not None:
            home_win = 1 if home_pts > away_pts else 0
        rows.append({
            "game_id":    gid,
            "sport":      "WNBA",
            "season":     g["season"],
            "game_date":  g["date"],
            "home_team":  g["home"],
            "away_team":  g["away"],
            "home_score": home_pts,
            "away_score": away_pts,
            "home_win":   home_win,
        })
    return rows, id_map


# ── Player game log rows ───────────────────────────────────────────────────────

def _build_player_log_rows(player_df, id_map: dict) -> list[dict]:
    rows = []
    for r in player_df.itertuples(index=False):
        nba_gid = str(getattr(r, "GAME_ID", ""))
        game_id = id_map.get(nba_gid)
        if not game_id:
            continue  # game not in our paired set (e.g. all-star)
        gdate = _to_date(getattr(r, "GAME_DATE", ""))
        team = _norm_wnba(getattr(r, "TEAM_ABBREVIATION", ""),
                          getattr(r, "TEAM_NAME", ""))
        rows.append({
            "player_id":     str(getattr(r, "PLAYER_ID", "")),
            "player_name":   getattr(r, "PLAYER_NAME", ""),
            "team":          team,
            "game_id":       game_id,
            "game_date":     gdate,
            "season":        int(gdate[:4]),
            "minutes":       _safe(getattr(r, "MIN", None), 1),
            "is_starter":    None,  # not in LeagueGameLog; backfill later if needed
            "points":        _to_int(getattr(r, "PTS", None)),
            "rebounds":      _to_int(getattr(r, "REB", None)),
            "offensive_reb": _to_int(getattr(r, "OREB", None)),
            "defensive_reb": _to_int(getattr(r, "DREB", None)),
            "assists":       _to_int(getattr(r, "AST", None)),
            "steals":        _to_int(getattr(r, "STL", None)),
            "blocks":        _to_int(getattr(r, "BLK", None)),
            "turnovers":     _to_int(getattr(r, "TOV", None)),
            "fg_made":       _to_int(getattr(r, "FGM", None)),
            "fg_att":        _to_int(getattr(r, "FGA", None)),
            "fg3_made":      _to_int(getattr(r, "FG3M", None)),
            "fg3_att":       _to_int(getattr(r, "FG3A", None)),
            "ft_made":       _to_int(getattr(r, "FTM", None)),
            "ft_att":        _to_int(getattr(r, "FTA", None)),
        })
    return rows


# ── Team season-aggregate rows ─────────────────────────────────────────────────

def _build_team_stat_rows(team_df, paired: dict, season: int,
                          as_of_date: str, before_date: str | None) -> list[dict]:
    """
    Aggregate the team-game DataFrame into one wnba_team_stats row per team.

    If before_date is None (backfill), aggregates the whole season and stamps
    as_of_date (typically {season}-01-01) — season totals with documented
    look-ahead, same convention as the MLB pitcher backfill. If before_date is
    set (daily refresh), only games strictly before it are aggregated.
    """
    # opponent points per (nba_game_id, team)
    opp_pts: dict[tuple, int] = {}
    for gid, g in paired.items():
        if g.get("home_pts") is not None and g.get("away_pts") is not None:
            opp_pts[(gid, g["home"])] = g["away_pts"]
            opp_pts[(gid, g["away"])] = g["home_pts"]

    acc: dict[str, dict] = {}
    for r in team_df.itertuples(index=False):
        gdate = _to_date(getattr(r, "GAME_DATE", ""))
        if before_date is not None and gdate >= before_date:
            continue
        team = _norm_wnba(getattr(r, "TEAM_ABBREVIATION", ""),
                          getattr(r, "TEAM_NAME", ""))
        if not team:
            continue
        gid = str(getattr(r, "GAME_ID", ""))
        a = acc.setdefault(team, {
            "n": 0, "pts": 0, "opp": 0, "fgm": 0, "fga": 0, "fg3m": 0, "fg3a": 0,
            "ftm": 0, "fta": 0, "oreb": 0, "reb": 0, "ast": 0, "tov": 0,
            "w": 0, "l": 0, "home_pts": [], "away_pts": [],
        })
        pts = _to_int(getattr(r, "PTS", None)) or 0
        opp = opp_pts.get((gid, team))
        if opp is None:
            continue
        a["n"]    += 1
        a["pts"]  += pts
        a["opp"]  += opp
        a["fgm"]  += _to_int(getattr(r, "FGM", None)) or 0
        a["fga"]  += _to_int(getattr(r, "FGA", None)) or 0
        a["fg3m"] += _to_int(getattr(r, "FG3M", None)) or 0
        a["fg3a"] += _to_int(getattr(r, "FG3A", None)) or 0
        a["ftm"]  += _to_int(getattr(r, "FTM", None)) or 0
        a["fta"]  += _to_int(getattr(r, "FTA", None)) or 0
        a["oreb"] += _to_int(getattr(r, "OREB", None)) or 0
        a["reb"]  += _to_int(getattr(r, "REB", None)) or 0
        a["ast"]  += _to_int(getattr(r, "AST", None)) or 0
        a["tov"]  += _to_int(getattr(r, "TOV", None)) or 0
        if str(getattr(r, "WL", "")) == "W":
            a["w"] += 1
        else:
            a["l"] += 1
        if "vs." in str(getattr(r, "MATCHUP", "")):
            a["home_pts"].append(pts)
        else:
            a["away_pts"].append(pts)

    rows = []
    for team, a in acc.items():
        n = a["n"]
        if n == 0:
            continue
        # possessions estimate (team ~ opponent possessions in basketball)
        poss = a["fga"] - a["oreb"] + a["tov"] + 0.44 * a["fta"]
        poss = poss if poss > 0 else None
        rows.append({
            "team":              team,
            "season":            season,
            "as_of_date":        as_of_date,
            "games_played":      n,
            "points_per_game":   _safe(a["pts"] / n, 2),
            "points_allowed_pg": _safe(a["opp"] / n, 2),
            "pace":              _safe(poss / n, 2) if poss else None,
            "off_rating":        _safe(100 * a["pts"] / poss, 2) if poss else None,
            "def_rating":        _safe(100 * a["opp"] / poss, 2) if poss else None,
            "efg_pct":           _safe((a["fgm"] + 0.5 * a["fg3m"]) / a["fga"], 4) if a["fga"] else None,
            "fg_pct":            _safe(a["fgm"] / a["fga"], 4) if a["fga"] else None,
            "fg3_pct":           _safe(a["fg3m"] / a["fg3a"], 4) if a["fg3a"] else None,
            "ft_pct":            _safe(a["ftm"] / a["fta"], 4) if a["fta"] else None,
            "reb_per_game":      _safe(a["reb"] / n, 2),
            "ast_per_game":      _safe(a["ast"] / n, 2),
            "tov_pct":           _safe(100 * a["tov"] / poss, 2) if poss else None,
            "points_last_3":     None,  # rolling computed by feature engine from games
            "points_last_5":     None,
            "points_home":       _safe(np.mean(a["home_pts"]), 2) if a["home_pts"] else None,
            "points_away":       _safe(np.mean(a["away_pts"]), 2) if a["away_pts"] else None,
            "wins":              a["w"],
            "losses":            a["l"],
            "point_differential": _safe((a["pts"] - a["opp"]) / n, 2),
        })
    return rows


# ── DB writers ────────────────────────────────────────────────────────────────

def _upsert_games(conn: DBConnection, rows: list[dict]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO games (
            game_id, sport, season, game_date, home_team, away_team,
            home_score, away_score, home_win, data_source
        ) VALUES (
            %(game_id)s, %(sport)s, %(season)s, %(game_date)s, %(home_team)s, %(away_team)s,
            %(home_score)s, %(away_score)s, %(home_win)s, 'nba_api'
        )
        ON CONFLICT(game_id) DO UPDATE SET
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score,
            home_win   = EXCLUDED.home_win,
            updated_at = NOW()::TEXT
    """
    conn.executemany(sql, rows)
    return len(rows)


def _upsert_player_log(conn: DBConnection, rows: list[dict]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO wnba_player_game_log (
            player_id, player_name, team, game_id, game_date, season,
            minutes, is_starter, points, rebounds, offensive_reb, defensive_reb,
            assists, steals, blocks, turnovers,
            fg_made, fg_att, fg3_made, fg3_att, ft_made, ft_att
        ) VALUES (
            %(player_id)s, %(player_name)s, %(team)s, %(game_id)s, %(game_date)s, %(season)s,
            %(minutes)s, %(is_starter)s, %(points)s, %(rebounds)s, %(offensive_reb)s, %(defensive_reb)s,
            %(assists)s, %(steals)s, %(blocks)s, %(turnovers)s,
            %(fg_made)s, %(fg_att)s, %(fg3_made)s, %(fg3_att)s, %(ft_made)s, %(ft_att)s
        )
        ON CONFLICT(player_id, game_id) DO UPDATE SET
            minutes  = EXCLUDED.minutes,
            points   = EXCLUDED.points,
            rebounds = EXCLUDED.rebounds,
            offensive_reb = EXCLUDED.offensive_reb,
            defensive_reb = EXCLUDED.defensive_reb,
            assists  = EXCLUDED.assists,
            steals   = EXCLUDED.steals,
            blocks   = EXCLUDED.blocks,
            turnovers = EXCLUDED.turnovers,
            fg_made  = EXCLUDED.fg_made,  fg_att  = EXCLUDED.fg_att,
            fg3_made = EXCLUDED.fg3_made, fg3_att = EXCLUDED.fg3_att,
            ft_made  = EXCLUDED.ft_made,  ft_att  = EXCLUDED.ft_att
    """
    conn.executemany(sql, rows)
    return len(rows)


def _upsert_team_stats(conn: DBConnection, rows: list[dict]) -> int:
    if not rows:
        return 0
    cols = [
        "team", "season", "as_of_date", "games_played",
        "points_per_game", "points_allowed_pg", "pace", "off_rating", "def_rating",
        "efg_pct", "fg_pct", "fg3_pct", "ft_pct", "reb_per_game", "ast_per_game",
        "tov_pct", "points_last_3", "points_last_5", "points_home", "points_away",
        "wins", "losses", "point_differential",
    ]
    placeholders = ", ".join(f"%({c})s" for c in cols)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols
                        if c not in ("team", "season", "as_of_date"))
    sql = f"""
        INSERT INTO wnba_team_stats ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(team, season, as_of_date) DO UPDATE SET {updates}
    """
    conn.executemany(sql, rows)
    return len(rows)


def _log_pipeline(conn, run_date, status, records_in, records_out, duration_s, error_msg=None):
    conn.execute("""
        INSERT INTO pipeline_log (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (%s, 'wnba_stats', %s, %s, %s, %s, %s)
    """, (run_date, status, records_in, records_out, duration_s, error_msg))


# ── Core ingest for one season ────────────────────────────────────────────────

def _ingest_season(conn: DBConnection, season: int, as_of_date: str,
                   before_date: str | None,
                   only_date: str | None = None) -> dict:
    """
    Fetch one season's logs and upsert games + player logs + team stats.

    only_date: if set, restrict games/player-log upserts to that game_date
               (used by the daily game-log step). Team stats are skipped then.
    """
    team_df   = _fetch_league_game_log(season, "T")
    time.sleep(REQUEST_SLEEP)
    player_df = _fetch_league_game_log(season, "P")
    time.sleep(REQUEST_SLEEP)

    if team_df is None or len(team_df) == 0:
        logger.info(f"WNBA {season}: no team game log rows")
        return {"games": 0, "player_rows": 0, "team_rows": 0}

    paired = _pair_games(team_df)
    game_rows, id_map = _build_game_rows(paired)
    player_rows = _build_player_log_rows(player_df, id_map)

    if only_date:
        game_rows   = [g for g in game_rows if g["game_date"] == only_date]
        keep_ids    = {g["game_id"] for g in game_rows}
        player_rows = [p for p in player_rows if p["game_id"] in keep_ids]

    n_games  = _upsert_games(conn, game_rows)
    n_player = _upsert_player_log(conn, player_rows)

    n_team = 0
    if not only_date:
        team_rows = _build_team_stat_rows(team_df, paired, season,
                                          as_of_date, before_date)
        n_team = _upsert_team_stats(conn, team_rows)

    return {"games": n_games, "player_rows": n_player, "team_rows": n_team}


# ── Main entry points ──────────────────────────────────────────────────────────

def run_wnba_stats_ingestor(season: int = None, as_of_date: str = None) -> dict:
    """
    Daily refresh: upsert the current season's games + player logs, and rebuild
    the team-stats snapshot as-of as_of_date (season-to-date, no look-ahead).
    """
    today = date.today()
    if as_of_date is None:
        as_of_date = today.isoformat()
    if season is None:
        season = int(as_of_date[:4])

    logger.info(f"WNBA stats ingestor — season={season}, as_of={as_of_date}")
    start = datetime.now()
    conn = get_connection()
    try:
        res = _ingest_season(conn, season, as_of_date, before_date=as_of_date)
        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, as_of_date, "success",
                      res["games"], res["player_rows"] + res["team_rows"], duration)
        conn.commit()
        logger.success(
            f"WNBA stats: {res['games']} games, {res['player_rows']} player-log rows, "
            f"{res['team_rows']} team rows — {duration:.1f}s"
        )
    except Exception as exc:
        conn.rollback()
        _log_pipeline(conn, as_of_date, "error", 0, 0,
                      (datetime.now() - start).total_seconds(), str(exc))
        conn.commit()
        logger.error(f"WNBA stats ingestor failed: {exc}")
        raise
    finally:
        conn.close()

    return {"season": season, "as_of_date": as_of_date, **res,
            "duration_s": (datetime.now() - start).total_seconds()}


def ingest_wnba_game_log_for_date(game_date: str) -> dict:
    """
    Daily pipeline step: upsert games + player box scores for game_date only.
    Idempotent. Returns counts.
    """
    season = int(game_date[:4])
    logger.info(f"WNBA game log ingest for {game_date} (season {season})")
    conn = get_connection()
    try:
        res = _ingest_season(conn, season, game_date, before_date=None,
                             only_date=game_date)
        conn.commit()
        logger.success(f"WNBA {game_date}: {res['games']} games, "
                       f"{res['player_rows']} player-log rows")
    except Exception as exc:
        conn.rollback()
        logger.error(f"WNBA game log ingest failed for {game_date}: {exc}")
        raise
    finally:
        conn.close()
    return res


def backfill_wnba_stats(start_season: int, end_season: int) -> None:
    """
    Backfill WNBA games + player logs + team stats for start..end seasons.
    Team-stats snapshot is stamped {season}-01-01 (full-season totals with
    documented look-ahead — same convention as the MLB pitcher backfill).
    """
    for season in range(start_season, end_season + 1):
        snap = f"{season}-01-01"
        logger.info(f"Backfilling WNBA {season} → snapshot {snap}")
        conn = get_connection()
        try:
            res = _ingest_season(conn, season, snap, before_date=None)
            conn.commit()
            logger.success(f"  WNBA {season}: {res}")
        except Exception as exc:
            conn.rollback()
            logger.error(f"  WNBA {season} failed: {exc}")
        finally:
            conn.close()
        time.sleep(2)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run WNBA stats ingestor")
    parser.add_argument("--season", type=int, help="Season (year of play)")
    parser.add_argument("--date", dest="as_of_date", help="As-of / game date YYYY-MM-DD")
    parser.add_argument("--game-log-date", help="Ingest games + box scores for this date only")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill seasons START through END")
    args = parser.parse_args()

    if args.backfill:
        backfill_wnba_stats(args.backfill[0], args.backfill[1])
    elif args.game_log_date:
        result = ingest_wnba_game_log_for_date(args.game_log_date)
        logger.info(f"Done: {result}")
    else:
        result = run_wnba_stats_ingestor(season=args.season, as_of_date=args.as_of_date)
        logger.info(f"Done: {result}")

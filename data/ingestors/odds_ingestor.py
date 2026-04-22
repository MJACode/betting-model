"""
odds_ingestor.py — Live DraftKings odds fetcher via The Odds API.

Pulls moneyline, spread, and totals markets for MLB and NHL.
Snapshots are stored as 'open' (first pull of the day) or 'close'
(final pull before game time, via the historical endpoint).

Usage:
    python -m data.ingestors.odds_ingestor           # both sports, today
    python -m data.ingestors.odds_ingestor --sport MLB
    python -m data.ingestors.odds_ingestor --sport NHL
    python -m data.ingestors.odds_ingestor --historical 2024-04-15  # backfill

API docs: https://the-odds-api.com/liveapi/guides/v4/
"""

import argparse
import json
import re
import time
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    ODDS_API_BASE,
    ODDS_API_BOOKMAKER,
    ODDS_API_KEY,
    ODDS_API_REGIONS,
    SPORTS,
)
from data.db import get_connection, DBConnection

# ── Constants ─────────────────────────────────────────────────────────────────

# The Odds API sport key → our sport label
SPORT_KEYS = {
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
}

# Markets to pull
MARKETS = ["h2h", "spreads", "totals"]

# NHL 3-way regulation market (separate endpoint call)
NHL_3WAY_MARKET = "h2h_3way"

# Rate limit: free tier = 500 requests/mo; starter = 10k/mo
# Sleep briefly between requests to be safe
REQUEST_SLEEP = 0.3  # seconds

# ── Team Name Normalization ───────────────────────────────────────────────────
# The Odds API returns full city+team names. Map to our 3-letter abbrevs.

MLB_ODDS_API_MAP = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Cleveland Indians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
    # A's relocation alias
    "Athletics": "OAK",
    "Sacramento River Cats": "OAK",
}

NHL_ODDS_API_MAP = {
    "Anaheim Ducks": "ANA",
    "Arizona Coyotes": "ARI",
    "Utah Hockey Club": "ARI",   # relocated franchise
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN",
    "Montreal Canadiens": "MTL",
    "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}


def _normalize_team(name: str, sport: str) -> str:
    mapping = MLB_ODDS_API_MAP if sport == "MLB" else NHL_ODDS_API_MAP
    abbrev = mapping.get(name)
    if not abbrev:
        # Fuzzy fallback: last word of team name
        abbrev = name.split()[-1][:3].upper()
        logger.warning(f"Unknown {sport} team name from Odds API: '{name}' → using '{abbrev}'")
    return abbrev


# ── Game ID Builder ───────────────────────────────────────────────────────────

def _build_game_id(sport: str, game_date: str, away: str, home: str) -> str:
    """Consistent with sbr_loader.py format."""
    return f"{sport}_{game_date}_{away}_{home}"


# ── Odds Parsing ──────────────────────────────────────────────────────────────

def _parse_outcomes(outcomes: list, sport: str, home_team_name: str = "") -> dict:
    """
    Parse The Odds API h2h/h2h_3way outcomes into our column structure.
    The Odds API returns full team names (not "Home"/"Away"), so we match
    against home_team_name to assign home_price vs away_price.
    """
    result = {}
    for o in outcomes:
        name  = o.get("name", "")
        price = o.get("price")
        if name == "Draw":
            result["draw_price"] = price
        elif name == home_team_name:
            result["home_price"] = price
        else:
            result["away_price"] = price
    return result


def _parse_spread_outcomes(outcomes: list, home_team_name: str) -> dict:
    """Parse spread outcomes where keys are full team names."""
    result = {}
    for o in outcomes:
        name  = o.get("name", "")
        price = o.get("price")
        point = o.get("point")
        if name == home_team_name:
            result["spread_home"]  = point
            result["home_price"]   = price
        else:
            result["away_price"]   = price
    return result


def _parse_total_outcomes(outcomes: list) -> dict:
    """Parse over/under totals."""
    result = {}
    for o in outcomes:
        name  = o.get("name", "")
        price = o.get("price")
        point = o.get("point")
        if point is not None:
            result["total_line"] = point
        if name == "Over":
            result["over_price"]  = price
        elif name == "Under":
            result["under_price"] = price
    return result


# ── API Fetcher ───────────────────────────────────────────────────────────────

def _get_odds(sport_key: str, markets: list[str]) -> list[dict]:
    """
    Call The Odds API /sports/{sport_key}/odds endpoint.
    Returns raw JSON list of game events.
    """
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set in .env")

    url = f"{ODDS_API_BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    ODDS_API_REGIONS,
        "markets":    ",".join(markets),
        "bookmakers": ODDS_API_BOOKMAKER,
        "oddsFormat": "american",
    }

    resp = requests.get(url, params=params, timeout=15)

    # Log remaining credits
    remaining = resp.headers.get("x-requests-remaining", "?")
    used      = resp.headers.get("x-requests-used", "?")
    logger.debug(f"Odds API credits — used: {used}, remaining: {remaining}")

    if resp.status_code == 401:
        raise ValueError("Invalid ODDS_API_KEY — check your .env file")
    if resp.status_code == 422:
        logger.warning(f"Odds API 422 for {sport_key}/{markets}: {resp.text[:200]}")
        return []

    resp.raise_for_status()
    return resp.json()


def _get_historical_odds(sport_key: str, markets: list[str],
                          snapshot_date: str) -> list[dict]:
    """
    Call The Odds API historical odds endpoint.
    snapshot_date: ISO date YYYY-MM-DD — returns lines from market open that day.
    NOTE: Historical endpoint uses extra credits (10× regular).
    """
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set in .env")

    # Historical endpoint expects ISO 8601 datetime
    snapshot_ts = f"{snapshot_date}T12:00:00Z"
    url = f"{ODDS_API_BASE}/historical/sports/{sport_key}/odds"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    ODDS_API_REGIONS,
        "markets":    ",".join(markets),
        "bookmakers": ODDS_API_BOOKMAKER,
        "oddsFormat": "american",
        "date":       snapshot_ts,
    }

    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


# ── Event Processor ───────────────────────────────────────────────────────────

def _process_events(events: list[dict], sport: str,
                    snapshot_type: str, snapshot_at: str,
                    include_3way: bool = False) -> tuple[list[dict], list[dict]]:
    """
    Parse a list of Odds API event dicts.
    Returns (game_rows, odds_rows) ready for DB insert.
    """
    game_rows = []
    odds_rows = []

    _ET = ZoneInfo("America/New_York")
    for event in events:
        commence_ts = event.get("commence_time", "")
        try:
            game_dt = datetime.fromisoformat(commence_ts.replace("Z", "+00:00"))
            game_dt_et = game_dt.astimezone(_ET)
            game_date = game_dt_et.strftime("%Y-%m-%d")
            game_time = game_dt_et.strftime("%H:%M")
        except Exception:
            game_date = snapshot_at[:10]
            game_time = None

        home_name = event.get("home_team", "")
        away_name = event.get("away_team", "")
        home_team = _normalize_team(home_name, sport)
        away_team = _normalize_team(away_name, sport)

        # Extract season from game_date
        year = int(game_date[:4])
        month = int(game_date[5:7])
        if sport == "NHL" and month >= 10:
            season = year + 1   # NHL season spans Oct–Jun, labeled by ending year
        else:
            season = year

        game_id = _build_game_id(sport, game_date, away_team, home_team)

        # Game row (upsert-safe — will not overwrite scores)
        game_rows.append({
            "game_id":     game_id,
            "sport":       sport,
            "season":      season,
            "game_date":   game_date,
            "game_time":   game_time,
            "home_team":   home_team,
            "away_team":   away_team,
            "data_source": "live",
        })

        # Bookmaker odds
        bookmakers = event.get("bookmakers", [])
        dk_book = next((b for b in bookmakers
                        if b.get("key") == ODDS_API_BOOKMAKER), None)
        if not dk_book:
            continue

        for mkt in dk_book.get("markets", []):
            market_key = mkt.get("key")
            outcomes   = mkt.get("outcomes", [])
            last_update = mkt.get("last_update", snapshot_at)

            base_row = {
                "game_id":       game_id,
                "sport":         sport,
                "bookmaker":     ODDS_API_BOOKMAKER,
                "snapshot_type": snapshot_type,
                "snapshot_at":   last_update,
                "home_price":    None,
                "away_price":    None,
                "draw_price":    None,
                "spread_home":   None,
                "total_line":    None,
                "over_price":    None,
                "under_price":   None,
            }

            if market_key in ("h2h", "h2h_3way"):
                parsed = _parse_outcomes(outcomes, sport, home_name)
                row = {**base_row, **parsed, "market": market_key}
                odds_rows.append(row)

            elif market_key == "spreads":
                parsed = _parse_spread_outcomes(outcomes, home_name)
                row = {**base_row, **parsed, "market": "spreads"}
                odds_rows.append(row)

            elif market_key == "totals":
                parsed = _parse_total_outcomes(outcomes)
                row = {**base_row, **parsed, "market": "totals"}
                odds_rows.append(row)

    return game_rows, odds_rows


# ── DB Writers ────────────────────────────────────────────────────────────────

def _upsert_games(conn: DBConnection, game_rows: list[dict]) -> int:
    """Insert game stubs (won't overwrite existing scores)."""
    sql = """
        INSERT INTO games (game_id, sport, season, game_date, game_time, home_team, away_team, data_source)
        VALUES (%(game_id)s, %(sport)s, %(season)s, %(game_date)s, %(game_time)s, %(home_team)s, %(away_team)s, %(data_source)s)
        ON CONFLICT(game_id) DO UPDATE SET
            game_time   = EXCLUDED.game_time,
            data_source = EXCLUDED.data_source,
            updated_at  = NOW()::TEXT
    """
    conn.executemany(sql, game_rows)
    return len(game_rows)


def _insert_odds(conn: DBConnection, odds_rows: list[dict]) -> int:
    """Insert odds snapshot rows (always append — no dedup)."""
    sql = """
        INSERT INTO odds (
            game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
            home_price, away_price, draw_price,
            spread_home, total_line, over_price, under_price
        ) VALUES (
            %(game_id)s, %(sport)s, %(market)s, %(bookmaker)s, %(snapshot_type)s, %(snapshot_at)s,
            %(home_price)s, %(away_price)s, %(draw_price)s,
            %(spread_home)s, %(total_line)s, %(over_price)s, %(under_price)s
        )
    """
    conn.executemany(sql, odds_rows)
    return len(odds_rows)


def _log_pipeline(conn: DBConnection, run_date: str,
                  status: str, records_in: int, records_out: int,
                  duration_s: float, error_msg: str = None):
    conn.execute("""
        INSERT INTO pipeline_log (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (%s, 'odds', %s, %s, %s, %s, %s)
    """, (run_date, status, records_in, records_out, duration_s, error_msg))


# ── Main Entry Points ─────────────────────────────────────────────────────────

def run_odds_ingestor(sport: str = None, snapshot_type: str = "open",
                      target_date: str = None) -> dict:
    """
    Pull live DraftKings odds for today's games.

    Args:
        sport:         'MLB', 'NHL', or None (both)
        snapshot_type: 'open' | 'close' | 'live'
        target_date:   ISO date (default: today)

    Returns:
        Summary dict with games and odds counts.
    """
    _ET = ZoneInfo("America/New_York")
    if target_date is None:
        target_date = datetime.now(_ET).strftime("%Y-%m-%d")

    sports = [sport] if sport else ["MLB", "NHL"]
    snapshot_at = datetime.now(_ET).isoformat()
    start = datetime.now()

    total_games = 0
    total_odds  = 0

    conn = get_connection()

    try:
        for sp in sports:
            sp_start   = datetime.now()
            sport_key  = SPORT_KEYS[sp]

            # Standard markets
            markets = MARKETS[:]
            if sp == "NHL":
                markets.append(NHL_3WAY_MARKET)

            try:
                events = _get_odds(sport_key, markets)
                time.sleep(REQUEST_SLEEP)
            except Exception as exc:
                logger.error(f"Odds API {sp} fetch failed: {exc}")
                _log_pipeline(conn, target_date, "error", 0, 0,
                              (datetime.now() - sp_start).total_seconds(), str(exc))
                conn.commit()
                continue

            if not events:
                logger.info(f"{sp}: no events returned from Odds API")
                continue

            game_rows, odds_rows = _process_events(
                events, sp, snapshot_type, snapshot_at
            )

            n_games = _upsert_games(conn, game_rows)
            n_odds  = _insert_odds(conn, odds_rows)
            total_games += n_games
            total_odds  += n_odds

            duration = (datetime.now() - sp_start).total_seconds()
            _log_pipeline(conn, target_date, "success",
                          records_in=len(events),
                          records_out=n_odds,
                          duration_s=duration)

            logger.success(
                f"{sp}: {n_games} games, {n_odds} odds rows "
                f"({snapshot_type}) — {duration:.1f}s"
            )

        conn.commit()

    except Exception as exc:
        conn.rollback()
        total_duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, target_date, "error", 0, 0, total_duration, str(exc))
        conn.commit()
        logger.error(f"Odds ingestor fatal error: {exc}")
        raise
    finally:
        conn.close()

    return {
        "target_date":  target_date,
        "snapshot_type": snapshot_type,
        "sports":       sports,
        "games":        total_games,
        "odds_rows":    total_odds,
        "duration_s":   (datetime.now() - start).total_seconds(),
    }


def run_historical_odds(sport: str, snapshot_date: str) -> dict:
    """
    Pull historical DraftKings lines for a past date using the
    Odds API historical endpoint. Uses 10× credits — use sparingly.

    Primarily used for backfilling open-line snapshots for the
    2024 test season before we had the live pipeline running.
    """
    sport_key = SPORT_KEYS[sport]
    markets   = MARKETS[:]
    if sport == "NHL":
        markets.append(NHL_3WAY_MARKET)

    snapshot_at = f"{snapshot_date}T12:00:00Z"
    start = datetime.now()

    logger.info(f"Fetching HISTORICAL odds for {sport} on {snapshot_date} "
                f"(uses 10× credits!)")

    events = _get_historical_odds(sport_key, markets, snapshot_date)
    time.sleep(REQUEST_SLEEP)

    game_rows, odds_rows = _process_events(
        events, sport, "open", snapshot_at
    )

    conn = get_connection()
    try:
        n_games = _upsert_games(conn, game_rows)
        n_odds  = _insert_odds(conn, odds_rows)
        conn.commit()
        logger.success(f"Historical {sport} {snapshot_date}: "
                       f"{n_games} games, {n_odds} odds rows")
    finally:
        conn.close()

    return {
        "snapshot_date": snapshot_date,
        "sport":         sport,
        "games":         n_games,
        "odds_rows":     n_odds,
        "duration_s":    (datetime.now() - start).total_seconds(),
    }


def get_latest_odds_for_game(conn: DBConnection,
                              game_id: str,
                              market: str) -> dict | None:
    """
    Helper used by the scorer. Returns the most recent odds snapshot
    for a given game_id and market. Prefers DraftKings; falls back to
    sbr_consensus for historical games loaded from SBR data.
    """
    cols = ["home_price", "away_price", "draw_price",
            "spread_home", "total_line", "over_price", "under_price",
            "snapshot_type", "snapshot_at"]

    for bookmaker in (ODDS_API_BOOKMAKER, "sbr_consensus"):
        row = conn.execute("""
            SELECT home_price, away_price, draw_price,
                   spread_home, total_line, over_price, under_price,
                   snapshot_type, snapshot_at
            FROM odds
            WHERE game_id  = ?
              AND market   = ?
              AND bookmaker = ?
            ORDER BY snapshot_at DESC
            LIMIT 1
        """, (game_id, market, bookmaker)).fetchone()

        if row:
            return dict(zip(cols, row))

    return None


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run odds ingestor")
    parser.add_argument("--sport", choices=["MLB", "NHL"],
                        help="Sport to fetch (default: both)")
    parser.add_argument("--snapshot", default="open",
                        choices=["open", "close", "live"],
                        help="Snapshot type label (default: open)")
    parser.add_argument("--historical", metavar="YYYY-MM-DD",
                        help="Pull historical odds for a past date (uses 10× credits)")
    args = parser.parse_args()

    if args.historical:
        sports = [args.sport] if args.sport else ["MLB", "NHL"]
        for sp in sports:
            result = run_historical_odds(sp, args.historical)
            logger.info(f"Done: {result}")
    else:
        result = run_odds_ingestor(sport=args.sport, snapshot_type=args.snapshot)
        logger.info(f"Done: {result}")

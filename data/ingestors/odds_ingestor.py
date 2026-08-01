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
import os
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
    ODDS_API_BOOKMAKERS_PARAM,
    ODDS_API_KEY,
    ODDS_API_REGIONS,
    LINE_SHOP_BOOKMAKERS,
    SPORTS,
    WNBA_ODDS_API_MAP,
    NBA_ODDS_API_MAP,
)
from data.db import get_connection, DBConnection

# ── Constants ─────────────────────────────────────────────────────────────────

# The Odds API sport key → our sport label
SPORT_KEYS = {
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "WNBA": "basketball_wnba",
    "NBA": "basketball_nba",
    "UFC": "mma_mixed_martial_arts",
}

# Markets to pull (full-game)
MARKETS = ["h2h", "spreads", "totals"]

# MLB first-5-innings markets (pulled only for MLB)
MLB_F5_MARKETS = ["h2h_1st_5_innings", "spreads_1st_5_innings", "totals_1st_5_innings"]

# NHL 3-way regulation market (separate endpoint call)
NHL_3WAY_MARKET = "h2h_3way"

# UFC: the bulk endpoint reliably carries only h2h for MMA. Round totals are
# attempted per-event (like MLB F5) — absent lines are non-fatal and the
# ufc_total_rounds model falls back to prob-only scoring.
UFC_BULK_MARKETS = ["h2h"]
UFC_EVENT_MARKETS = ["totals"]

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
    # Relocated franchise — canonical id is UTA across all seasons (Arizona
    # Coyotes → Utah Hockey Club 2024-25 → Utah Mammoth 2025-26).
    "Arizona Coyotes": "UTA",
    "Utah Hockey Club": "UTA",
    "Utah Mammoth": "UTA",
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
    if sport == "UFC":
        # Fighters have no abbreviations. games.home_team/away_team store the
        # display name as the books list it (after alias normalization); the
        # game_id uses the slugified name (see _build_game_id). The ufcstats
        # results scraper matches games by slug pair + date.
        from config import UFC_NAME_ALIASES
        return UFC_NAME_ALIASES.get(name, name)
    if sport == "MLB":
        mapping = MLB_ODDS_API_MAP
    elif sport == "NHL":
        mapping = NHL_ODDS_API_MAP
    elif sport == "NBA":
        mapping = NBA_ODDS_API_MAP
    else:  # WNBA
        mapping = WNBA_ODDS_API_MAP
    abbrev = mapping.get(name)
    if not abbrev:
        # Fuzzy fallback: last word of team name
        abbrev = name.split()[-1][:3].upper()
        logger.warning(f"Unknown {sport} team name from Odds API: '{name}' → using '{abbrev}'")
    return abbrev


# ── Game ID Builder ───────────────────────────────────────────────────────────

def _build_game_id(sport: str, game_date: str, away: str, home: str) -> str:
    """Consistent with sbr_loader.py format. UFC uses fighter-name slugs."""
    if sport == "UFC":
        from data.ingestors.ufc_stats_ingestor import slugify_fighter
        return f"UFC_{game_date}_{slugify_fighter(away)}_{slugify_fighter(home)}"
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
        link  = o.get("link")      # betslip deep link (includeLinks=true)
        sid   = o.get("sid")       # bookmaker selection id (includeSids=true)
        if name == "Draw":
            result["draw_price"] = price
            result["draw_link"]  = link
            result["draw_sid"]   = sid
        elif name == home_team_name:
            result["home_price"] = price
            result["home_link"]  = link
            result["home_sid"]   = sid
        else:
            result["away_price"] = price
            result["away_link"]  = link
            result["away_sid"]   = sid
    return result


def _parse_spread_outcomes(outcomes: list, home_team_name: str) -> dict:
    """Parse spread outcomes where keys are full team names."""
    result = {}
    for o in outcomes:
        name  = o.get("name", "")
        price = o.get("price")
        point = o.get("point")
        link  = o.get("link")
        sid   = o.get("sid")
        if name == home_team_name:
            result["spread_home"]  = point
            result["home_price"]   = price
            result["home_link"]    = link
            result["home_sid"]     = sid
        else:
            result["away_price"]   = price
            result["away_link"]    = link
            result["away_sid"]     = sid
    return result


def _parse_total_outcomes(outcomes: list) -> dict:
    """Parse over/under totals."""
    result = {}
    for o in outcomes:
        name  = o.get("name", "")
        price = o.get("price")
        point = o.get("point")
        link  = o.get("link")
        sid   = o.get("sid")
        if point is not None:
            result["total_line"] = point
        if name == "Over":
            result["over_price"]  = price
            result["over_link"]   = link
            result["over_sid"]    = sid
        elif name == "Under":
            result["under_price"] = price
            result["under_link"]  = link
            result["under_sid"]   = sid
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
        "apiKey":       ODDS_API_KEY,
        "regions":      ODDS_API_REGIONS,
        "markets":      ",".join(markets),
        # Multi-book for line shopping (game markets). Counts as ONE region on
        # The Odds API, so this does not increase credit cost vs DK-only.
        "bookmakers":   ODDS_API_BOOKMAKERS_PARAM,
        "oddsFormat":   "american",
        "includeLinks": "true",   # DK betslip deep links (no extra credit cost)
        "includeSids":  "true",   # bookmaker selection ids
    }

    resp = requests.get(url, params=params, timeout=15)

    # Log remaining credits
    remaining = resp.headers.get("x-requests-remaining", "?")
    used      = resp.headers.get("x-requests-used", "?")
    logger.debug(f"Odds API credits — used: {used}, remaining: {remaining}")

    if resp.status_code == 401:
        raise ValueError("Invalid ODDS_API_KEY — check your .env file")
    if resp.status_code == 422:
        # A 422 here is usually an unsupported MARKET (the h2h_3way incident), but
        # it can also be an unsupported BOOKMAKER key. Losing the whole slate
        # because one display-only book was renamed is never acceptable, so retry
        # once with draftkings alone — the book the models actually score against.
        logger.warning(f"Odds API 422 for {sport_key}/{markets}: {resp.text[:200]}")
        if params["bookmakers"] != ODDS_API_BOOKMAKER:
            logger.warning(
                f"{sport_key}: retrying with draftkings only "
                f"(line-shop books unavailable: {params['bookmakers']})"
            )
            params["bookmakers"] = ODDS_API_BOOKMAKER
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"{sport_key}: DK-only retry also failed ({resp.status_code})")
        return []

    resp.raise_for_status()
    return resp.json()


def _list_events(sport_key: str) -> list[dict]:
    """List upcoming events (no odds, just metadata) — costs 0 credits per docs."""
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set in .env")
    url = f"{ODDS_API_BASE}/sports/{sport_key}/events"
    resp = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=15)
    if resp.status_code in (404, 422):
        logger.warning(f"events endpoint {sport_key}: {resp.status_code} — {resp.text[:200]}")
        return []
    resp.raise_for_status()
    return resp.json()


def _get_event_odds(sport_key: str, event_id: str, markets: list[str]) -> dict | None:
    """Fetch odds for a single event id (per-event endpoint supports additional markets)."""
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set in .env")
    url = f"{ODDS_API_BASE}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey":       ODDS_API_KEY,
        "regions":      ODDS_API_REGIONS,
        "markets":      ",".join(markets),
        "bookmakers":   ODDS_API_BOOKMAKER,
        "oddsFormat":   "american",
        "includeLinks": "true",   # DK betslip deep links
        "includeSids":  "true",
    }
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code in (404, 422):
        logger.debug(f"event {event_id}: {resp.status_code} (markets unsupported for this event)")
        return None
    resp.raise_for_status()
    return resp.json()


def _fetch_f5_per_event(sport_key: str, sport: str, snapshot_type: str,
                         snapshot_at: str) -> list[dict]:
    """
    Fetch F5 markets via the per-event endpoint. F5 (1st_5_innings) markets are
    "additional markets" on The Odds API and are NOT returned by the bulk
    /sports/{sport_key}/odds endpoint — only by /sports/{sport_key}/events/{id}/odds.

    Cost: 1 credit per market per region per per-event call. For 15 MLB games
    × 3 F5 markets × 1 region = ~45 credits per fetch.
    """
    events = _list_events(sport_key)
    if not events:
        logger.info(f"{sport} F5: no upcoming events")
        return []

    event_responses = []
    for ev in events:
        event_id = ev.get("id")
        if not event_id:
            continue
        try:
            ev_odds = _get_event_odds(sport_key, event_id, MLB_F5_MARKETS)
        except Exception as exc:
            logger.warning(f"  F5 per-event fetch failed for {event_id}: {exc}")
            continue
        if ev_odds:
            event_responses.append(ev_odds)
        time.sleep(REQUEST_SLEEP)

    if not event_responses:
        logger.info(f"{sport} F5: per-event endpoint returned no F5 markets")
        return []

    _, odds_rows = _process_events(event_responses, sport, snapshot_type, snapshot_at)
    return [r for r in odds_rows if r.get("market") in MLB_F5_MARKETS]


def _fetch_ufc_totals_per_event(sport_key: str, snapshot_type: str,
                                snapshot_at: str) -> list[dict]:
    """
    Attempt DK round-total lines for upcoming UFC fights via the per-event
    endpoint (totals is not in the bulk MMA feed). UFC volume is low
    (~13 fights/event, ~1 event/week) so this runs on every odds fetch.
    Returns [] without raising when the market isn't offered — the
    ufc_total_rounds model then scores prob-only against a synthetic line.
    """
    events = _list_events(sport_key)
    if not events:
        return []

    event_responses = []
    for ev in events:
        event_id = ev.get("id")
        if not event_id:
            continue
        try:
            ev_odds = _get_event_odds(sport_key, event_id, UFC_EVENT_MARKETS)
        except Exception as exc:
            logger.debug(f"  UFC totals per-event fetch failed for {event_id}: {exc}")
            continue
        if ev_odds:
            event_responses.append(ev_odds)
        time.sleep(REQUEST_SLEEP)

    if not event_responses:
        logger.info("UFC: per-event endpoint returned no round-total markets")
        return []

    _, odds_rows = _process_events(event_responses, "UFC", snapshot_type, snapshot_at)
    return [r for r in odds_rows if r.get("market") == "totals"]


def _fetch_nhl_3way_per_event(sport_key: str, snapshot_type: str,
                              snapshot_at: str) -> list[dict]:
    """
    Fetch DK's 3-way regulation market (h2h_3way) for upcoming NHL games via
    the per-event endpoint. h2h_3way is an additional market — including it in
    the bulk /odds request returns a 422 and kills the whole NHL fetch (the
    bug that originally broke NHL odds ingestion). NHL slates are ~5-13
    games/day, so per-event calls are cheap. Returns [] without raising when
    the market isn't offered — nhl_moneyline_regulation then simply skips
    (it only scores against real 3-way prices).
    """
    events = _list_events(sport_key)
    if not events:
        return []

    event_responses = []
    for ev in events:
        event_id = ev.get("id")
        if not event_id:
            continue
        try:
            ev_odds = _get_event_odds(sport_key, event_id, [NHL_3WAY_MARKET])
        except Exception as exc:
            logger.debug(f"  NHL 3-way per-event fetch failed for {event_id}: {exc}")
            continue
        if ev_odds:
            event_responses.append(ev_odds)
        time.sleep(REQUEST_SLEEP)

    if not event_responses:
        logger.info("NHL: per-event endpoint returned no 3-way regulation markets")
        return []

    _, odds_rows = _process_events(event_responses, "NHL", snapshot_type, snapshot_at)
    return [r for r in odds_rows if r.get("market") == NHL_3WAY_MARKET]


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
        "apiKey":       ODDS_API_KEY,
        "regions":      ODDS_API_REGIONS,
        "markets":      ",".join(markets),
        "bookmakers":   ODDS_API_BOOKMAKER,
        "oddsFormat":   "american",
        "date":         snapshot_ts,
        "includeLinks": "true",
        "includeSids":  "true",
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
        game_dt = None
        try:
            game_dt = datetime.fromisoformat(commence_ts.replace("Z", "+00:00"))
            game_date = game_dt.astimezone(_ET).strftime("%Y-%m-%d")
        except Exception:
            game_date = snapshot_at[:10]

        home_name = event.get("home_team", "")
        away_name = event.get("away_team", "")
        home_team = _normalize_team(home_name, sport)
        away_team = _normalize_team(away_name, sport)

        # Extract season from game_date
        year = int(game_date[:4])
        month = int(game_date[5:7])
        if sport in ("NHL", "NBA") and month >= 10:
            season = year + 1   # NHL/NBA seasons span Oct–Jun, labeled by ending year
        else:
            season = year

        game_id = _build_game_id(sport, game_date, away_team, home_team)

        # Game row (upsert-safe — will not overwrite scores)
        game_rows.append({
            "game_id":       game_id,
            "sport":         sport,
            "season":        season,
            "game_date":     game_date,
            "home_team":     home_team,
            "away_team":     away_team,
            "commence_time": game_dt.isoformat() if game_dt else None,
            "data_source":   "live",
        })

        # Bookmaker odds. Store a row per line-shop book (DraftKings is the book
        # the models score against; the others are kept for line shopping only).
        # Require DK to be present — if DK doesn't list a game we don't score it.
        bookmakers = event.get("bookmakers", [])
        if not any(b.get("key") == ODDS_API_BOOKMAKER for b in bookmakers):
            continue

        for book in bookmakers:
            book_key = book.get("key")
            if book_key not in LINE_SHOP_BOOKMAKERS:
                continue

            for mkt in book.get("markets", []):
                market_key = mkt.get("key")
                outcomes   = mkt.get("outcomes", [])
                last_update = mkt.get("last_update", snapshot_at)

                base_row = {
                    "game_id":       game_id,
                    "sport":         sport,
                    "bookmaker":     book_key,
                    "snapshot_type": snapshot_type,
                    "snapshot_at":   last_update,
                    "home_price":    None,
                    "away_price":    None,
                    "draw_price":    None,
                    "spread_home":   None,
                    "total_line":    None,
                    "over_price":    None,
                    "under_price":   None,
                    # Betslip deep links + selection ids (includeLinks/includeSids)
                    "home_link":     None,
                    "away_link":     None,
                    "draw_link":     None,
                    "over_link":     None,
                    "under_link":    None,
                    "home_sid":      None,
                    "away_sid":      None,
                    "draw_sid":      None,
                    "over_sid":      None,
                    "under_sid":     None,
                }

                if market_key in ("h2h", "h2h_3way", "h2h_1st_5_innings"):
                    parsed = _parse_outcomes(outcomes, sport, home_name)
                    row = {**base_row, **parsed, "market": market_key}
                    odds_rows.append(row)

                elif market_key in ("spreads", "spreads_1st_5_innings"):
                    parsed = _parse_spread_outcomes(outcomes, home_name)
                    row = {**base_row, **parsed, "market": market_key}
                    odds_rows.append(row)

                elif market_key in ("totals", "totals_1st_5_innings"):
                    parsed = _parse_total_outcomes(outcomes)
                    row = {**base_row, **parsed, "market": market_key}
                    odds_rows.append(row)

    return game_rows, odds_rows


# ── DB Writers ────────────────────────────────────────────────────────────────

def _upsert_games(conn: DBConnection, game_rows: list[dict]) -> int:
    """Insert game stubs (won't overwrite existing scores)."""
    sql = """
        INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, commence_time, data_source)
        VALUES (%(game_id)s, %(sport)s, %(season)s, %(game_date)s, %(home_team)s, %(away_team)s, %(commence_time)s, %(data_source)s)
        ON CONFLICT(game_id) DO UPDATE SET
            commence_time = COALESCE(EXCLUDED.commence_time, games.commence_time),
            data_source   = EXCLUDED.data_source,
            updated_at    = NOW()::TEXT
    """
    conn.executemany(sql, game_rows)
    return len(game_rows)


def _insert_odds(conn: DBConnection, odds_rows: list[dict]) -> int:
    """Insert odds snapshot rows (always append — no dedup)."""
    sql = """
        INSERT INTO odds (
            game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
            home_price, away_price, draw_price,
            spread_home, total_line, over_price, under_price,
            home_link, away_link, draw_link, over_link, under_link,
            home_sid, away_sid, draw_sid, over_sid, under_sid
        ) VALUES (
            %(game_id)s, %(sport)s, %(market)s, %(bookmaker)s, %(snapshot_type)s, %(snapshot_at)s,
            %(home_price)s, %(away_price)s, %(draw_price)s,
            %(spread_home)s, %(total_line)s, %(over_price)s, %(under_price)s,
            %(home_link)s, %(away_link)s, %(draw_link)s, %(over_link)s, %(under_link)s,
            %(home_sid)s, %(away_sid)s, %(draw_sid)s, %(over_sid)s, %(under_sid)s
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

    sports = [sport] if sport else ["MLB", "NHL", "WNBA", "NBA", "UFC"]
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
            if sp == "UFC":
                # Bulk MMA feed carries only h2h; spreads/totals 422 the call.
                markets = UFC_BULK_MARKETS[:]
            else:
                markets = MARKETS[:]
            # NOTE: h2h_3way is NOT appended here — The Odds API rejects it in
            # the bulk request with a 422 (which would kill the entire NHL
            # fetch). It's an additional market, fetched per-event below.

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

            # F5 markets — MLB only, fetched via the per-event endpoint (additional
            # markets are not returned by the bulk /odds endpoint). Gated by env var
            # FETCH_F5_LIVE=1 so only the daily 11am pipeline triggers it; mid-day
            # refreshes skip F5 to conserve API credits (see daily_pipeline.yml).
            if sp == "MLB" and os.environ.get("FETCH_F5_LIVE", "0") == "1":
                try:
                    f5_rows = _fetch_f5_per_event(sport_key, sp, snapshot_type, snapshot_at)
                    if f5_rows:
                        n_f5 = _insert_odds(conn, f5_rows)
                        total_odds += n_f5
                        logger.success(f"MLB F5 markets: {n_f5} odds rows stored")
                except Exception as exc:
                    logger.warning(f"MLB F5 odds fetch failed (non-fatal, will use prob-only): {exc}")
            elif sp == "MLB":
                logger.debug("MLB F5 fetch skipped (FETCH_F5_LIVE not set — daily pipeline only)")

            # NHL 3-way regulation — per-event additional market (bulk 422s),
            # attempted on every fetch. Non-fatal when absent.
            if sp == "NHL" and events:
                try:
                    nhl_3way_rows = _fetch_nhl_3way_per_event(
                        sport_key, snapshot_type, snapshot_at)
                    if nhl_3way_rows:
                        n_3way = _insert_odds(conn, nhl_3way_rows)
                        total_odds += n_3way
                        logger.success(f"NHL 3-way regulation: {n_3way} odds rows stored")
                except Exception as exc:
                    logger.warning(f"NHL 3-way fetch failed (non-fatal — regulation "
                                   f"model skips unpriced games): {exc}")

            # UFC round totals — per-event additional market, attempted on every
            # fetch (low volume: ~13 fights once a week). Non-fatal when absent.
            if sp == "UFC":
                try:
                    ufc_total_rows = _fetch_ufc_totals_per_event(
                        sport_key, snapshot_type, snapshot_at)
                    if ufc_total_rows:
                        n_ufc_t = _insert_odds(conn, ufc_total_rows)
                        total_odds += n_ufc_t
                        logger.success(f"UFC round totals: {n_ufc_t} odds rows stored")
                except Exception as exc:
                    logger.warning(f"UFC round-total fetch failed (non-fatal, "
                                   f"prob-only fallback applies): {exc}")

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
    # NOTE: F5 and NHL h2h_3way markets not supported on the bulk endpoint —
    # h2h_3way in a bulk request 422s the whole call.

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
    parser.add_argument("--sport", choices=["MLB", "NHL", "WNBA", "NBA", "UFC"],
                        help="Sport to fetch (default: all)")
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

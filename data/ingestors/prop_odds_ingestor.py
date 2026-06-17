"""
prop_odds_ingestor.py — DraftKings MLB player prop odds via The Odds API.

Fetches all 11 player prop markets for every MLB game today and stores
lines in the player_prop_odds table. This is the collection layer —
no scoring is done here.

How it works:
  1. GET /v4/sports/baseball_mlb/events  → list of today's event IDs
  2. For each event, GET /v4/sports/baseball_mlb/events/{id}/odds
     with all prop markets (one call per game, one DK bookmaker)
  3. Parse player name + line + over/under prices
  4. Upsert into player_prop_odds

Credit cost: ~1 credit per game per call. With 15 games/day = ~15 credits/day.

Usage:
    python -m data.ingestors.prop_odds_ingestor              # today
    python -m data.ingestors.prop_odds_ingestor --date 2026-05-08
    python -m data.ingestors.prop_odds_ingestor --snapshot live
"""

import argparse
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    ODDS_API_BASE,
    ODDS_API_BOOKMAKER,
    ODDS_API_KEY,
    ODDS_API_REGIONS,
    PROP_MARKETS_ALL,
    PROP_MARKETS_WNBA,
    PROP_MARKETS_NBA,
)
from data.db import get_connection, DBConnection
from data.ingestors.odds_ingestor import (
    MLB_ODDS_API_MAP,
    SPORT_KEYS,
    _normalize_team,
    _build_game_id,
)

# ── Constants ─────────────────────────────────────────────────────────────────

SPORT_KEY = "baseball_mlb"   # default (MLB) — overridden per sport at runtime
REQUEST_SLEEP = 0.5   # seconds between event-level calls — be polite

# Allowed prop markets per sport (used to filter the bookmaker response)
PROP_MARKETS_BY_SPORT = {
    "MLB":  PROP_MARKETS_ALL,
    "WNBA": PROP_MARKETS_WNBA,
    "NBA":  PROP_MARKETS_NBA,
}

# Markets that use logistic (binary) — everything else is Poisson count
BINARY_MARKETS = {"batter_home_runs", "batter_stolen_bases"}

# Yes/No markets DK lists without a numeric `point` — default the line to 0.5 so
# the parser keeps the row (over=Yes, under=No). HR and NBA double-double both
# fit this shape.
YESNO_DEFAULT_LINE_MARKETS = {"batter_home_runs", "player_double_double"}

# ── API Helpers ───────────────────────────────────────────────────────────────

def _get_events(target_date: str, sport_key: str = SPORT_KEY) -> list[dict]:
    """
    Fetch a sport's events from The Odds API for target_date.
    Filters to events whose commence_time falls on target_date (ET).
    Returns a list of {id, home_team, away_team, commence_time} dicts.
    """
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set in .env")

    url = f"{ODDS_API_BASE}/sports/{sport_key}/events"
    params = {"apiKey": ODDS_API_KEY, "dateFormat": "iso"}
    resp = requests.get(url, params=params, timeout=15)

    remaining = resp.headers.get("x-requests-remaining", "?")
    logger.debug(f"Prop odds API credits remaining: {remaining}")

    if resp.status_code == 401:
        raise ValueError("Invalid ODDS_API_KEY")
    if resp.status_code != 200:
        logger.warning(f"Events endpoint returned {resp.status_code}: {resp.text[:200]}")
        return []

    _ET = ZoneInfo("America/New_York")
    events = []
    for event in resp.json():
        try:
            commence = event.get("commence_time", "")
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            event_date = dt.astimezone(_ET).strftime("%Y-%m-%d")
        except Exception:
            event_date = target_date

        if event_date == target_date:
            events.append({
                "id":           event["id"],
                "home_team":    event.get("home_team", ""),
                "away_team":    event.get("away_team", ""),
                "commence_time": event.get("commence_time", ""),
                "game_date":    event_date,
            })

    logger.info(f"Found {len(events)} events for {target_date} ({sport_key})")
    return events


def _get_event_props(event_id: str, markets: list[str],
                     sport_key: str = SPORT_KEY) -> list[dict]:
    """
    Fetch player prop odds for a single event.
    Returns the raw bookmaker markets list, or [] on error.
    """
    url = f"{ODDS_API_BASE}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey":       ODDS_API_KEY,
        "regions":      ODDS_API_REGIONS,
        "markets":      ",".join(markets),
        "bookmakers":   ODDS_API_BOOKMAKER,
        "oddsFormat":   "american",
        "includeLinks": "true",   # DK betslip deep links per prop selection
        "includeSids":  "true",
    }

    resp = requests.get(url, params=params, timeout=20)

    if resp.status_code == 422:
        logger.warning(f"Event {event_id}: 422 on prop markets (DK may not carry these)")
        return []
    if resp.status_code != 200:
        logger.warning(f"Event {event_id}: HTTP {resp.status_code}")
        return []

    data = resp.json()
    bookmakers = data.get("bookmakers", [])
    dk = next((b for b in bookmakers if b.get("key") == ODDS_API_BOOKMAKER), None)
    if not dk:
        logger.debug(f"Event {event_id}: DraftKings not in response")
        return []

    return dk.get("markets", [])


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_prop_markets(markets_data: list[dict], game_id: str,
                        game_date: str, snapshot_type: str,
                        snapshot_at: str,
                        allowed_markets=PROP_MARKETS_ALL) -> list[dict]:
    """
    Parse the markets list from a DK bookmaker response into DB rows.

    The Odds API serves two outcome shapes for player props:

    Over/Under markets (hits, TB, Ks, etc.) — has a numeric line:
        {"name": "Over",  "description": "Gerrit Cole", "price": -130, "point": 7.5}
        {"name": "Under", "description": "Gerrit Cole", "price": +110, "point": 7.5}

    Yes/No markets (batter_home_runs) — binary, no `point`:
        {"name": "Yes", "description": "Aaron Judge", "price": +210}
        {"name": "No",  "description": "Aaron Judge", "price": -260}

    The `name` and `description` fields can also appear in the opposite roles
    (some endpoints return name=player, description=direction). Both cases
    are handled defensively. For Yes/No, Yes maps to over_price, No to
    under_price, and the line defaults to 0.5 (DK's standard 0.5+ HR market).

    Returns one row per player per market.
    """
    from collections import defaultdict
    player_rows: dict[tuple, dict] = defaultdict(lambda: {
        "game_id":      game_id,
        "game_date":    game_date,
        "snapshot_type": snapshot_type,
        "snapshot_at":  snapshot_at,
        "bookmaker":    ODDS_API_BOOKMAKER,
        "player_name":  None,
        "team":         None,
        "market":       None,
        "line":         None,
        "over_price":   None,
        "under_price":  None,
        "over_link":    None,
        "under_link":   None,
        "over_sid":     None,
        "under_sid":    None,
    })

    OU_DIRS  = {"over", "under"}
    YN_DIRS  = {"yes", "no"}
    YN_TO_OU = {"yes": "Over", "no": "Under"}

    for mkt in markets_data:
        market_key = mkt.get("key", "")
        if market_key not in allowed_markets:
            continue

        for outcome in mkt.get("outcomes", []):
            name_field = (outcome.get("name") or "").strip()
            desc_field = (outcome.get("description") or "").strip()
            price = outcome.get("price")
            point = outcome.get("point")
            link  = outcome.get("link")
            sid   = outcome.get("sid")

            # Detect which field holds direction vs. player name
            n_lo, d_lo = name_field.lower(), desc_field.lower()
            if n_lo in OU_DIRS:
                direction, player_name = name_field.capitalize(), desc_field
            elif d_lo in OU_DIRS:
                direction, player_name = desc_field.capitalize(), name_field
            elif n_lo in YN_DIRS:
                direction, player_name = YN_TO_OU[n_lo], desc_field
            elif d_lo in YN_DIRS:
                direction, player_name = YN_TO_OU[d_lo], name_field
            else:
                continue   # unknown outcome shape

            if not player_name:
                continue

            # Yes/No markets (HR, NBA double-double) have no `point` — DK lists
            # them as the 0.5+ over side.
            if point is None and market_key in YESNO_DEFAULT_LINE_MARKETS:
                point = 0.5

            key = (market_key, player_name)
            row = player_rows[key]
            row["player_name"] = player_name
            row["market"]      = market_key
            if point is not None:
                row["line"] = point
            if direction == "Over":
                row["over_price"] = price
                row["over_link"]  = link
                row["over_sid"]   = sid
            elif direction == "Under":
                row["under_price"] = price
                row["under_link"]  = link
                row["under_sid"]   = sid

    result = []
    for row in player_rows.values():
        if row["player_name"] and row["market"] and row["line"] is not None:
            result.append(dict(row))
    return result


# ── DB Writer ─────────────────────────────────────────────────────────────────

def _insert_prop_odds(conn: DBConnection, rows: list[dict]) -> int:
    """Insert prop odds rows. No dedup — always append snapshots."""
    if not rows:
        return 0
    sql = """
        INSERT INTO player_prop_odds (
            game_id, game_date, player_name, team, market,
            bookmaker, snapshot_type, snapshot_at,
            line, over_price, under_price,
            over_link, under_link, over_sid, under_sid
        ) VALUES (
            %(game_id)s, %(game_date)s, %(player_name)s, %(team)s, %(market)s,
            %(bookmaker)s, %(snapshot_type)s, %(snapshot_at)s,
            %(line)s, %(over_price)s, %(under_price)s,
            %(over_link)s, %(under_link)s, %(over_sid)s, %(under_sid)s
        )
    """
    conn.executemany(sql, rows)
    return len(rows)


def _log_pipeline(conn: DBConnection, run_date: str, status: str,
                  records_in: int, records_out: int,
                  duration_s: float, error_msg: str = None):
    conn.execute("""
        INSERT INTO pipeline_log (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (%s, 'prop_odds', %s, %s, %s, %s, %s)
    """, (run_date, status, records_in, records_out, duration_s, error_msg))


# ── Main Entry Point ──────────────────────────────────────────────────────────

def run_prop_odds_ingestor(target_date: str = None,
                           snapshot_type: str = "open",
                           sport: str = "MLB") -> dict:
    """
    Pull DK player prop lines for all of a sport's games on target_date.

    Args:
        target_date:   ISO date YYYY-MM-DD (default: today ET)
        snapshot_type: 'open' | 'live'
        sport:         'MLB', 'WNBA', or 'NBA'

    Returns:
        Summary dict.
    """
    _ET = ZoneInfo("America/New_York")
    if target_date is None:
        target_date = datetime.now(_ET).strftime("%Y-%m-%d")

    sport_key = SPORT_KEYS[sport]
    markets   = PROP_MARKETS_BY_SPORT.get(sport, PROP_MARKETS_ALL)
    allowed   = set(markets)

    snapshot_at = datetime.now(_ET).isoformat()
    start = datetime.now()

    logger.info(f"Prop odds ingestor: {sport} {target_date} ({snapshot_type})")

    conn = get_connection()
    total_rows = 0
    total_events = 0

    try:
        events = _get_events(target_date, sport_key)
        if not events:
            logger.info(f"No {sport} events found for {target_date} — nothing to do")
            _log_pipeline(conn, target_date, "success", 0, 0,
                          (datetime.now() - start).total_seconds())
            conn.commit()
            return {"target_date": target_date, "sport": sport, "events": 0, "prop_rows": 0}

        for event in events:
            home_name = event["home_team"]
            away_name = event["away_team"]
            home_team = _normalize_team(home_name, sport)
            away_team = _normalize_team(away_name, sport)
            game_id   = _build_game_id(sport, event["game_date"], away_team, home_team)

            logger.debug(f"Fetching props for {away_team} @ {home_team} ({game_id})")

            try:
                markets_data = _get_event_props(event["id"], markets, sport_key)
                time.sleep(REQUEST_SLEEP)
            except Exception as exc:
                logger.warning(f"Props fetch failed for {game_id}: {exc}")
                continue

            if not markets_data:
                logger.debug(f"No prop markets returned for {game_id}")
                continue

            rows = _parse_prop_markets(
                markets_data, game_id, event["game_date"],
                snapshot_type, snapshot_at, allowed_markets=allowed,
            )

            if rows:
                n = _insert_prop_odds(conn, rows)
                total_rows   += n
                total_events += 1
                logger.info(f"  {away_team} @ {home_team}: {n} prop rows "
                            f"({len(set(r['market'] for r in rows))} markets, "
                            f"{len(set(r['player_name'] for r in rows))} players)")
            else:
                logger.debug(f"  {game_id}: no parseable prop rows")

        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, target_date, "success",
                      records_in=len(events),
                      records_out=total_rows,
                      duration_s=duration)
        conn.commit()

        logger.success(
            f"Prop odds complete: {total_events}/{len(events)} games "
            f"with props, {total_rows} rows — {duration:.1f}s"
        )

    except Exception as exc:
        conn.rollback()
        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, target_date, "error", 0, 0, duration, str(exc))
        conn.commit()
        logger.error(f"Prop odds ingestor fatal error: {exc}")
        raise
    finally:
        conn.close()

    return {
        "target_date":  target_date,
        "sport":        sport,
        "snapshot_type": snapshot_type,
        "events":       total_events,
        "prop_rows":    total_rows,
        "duration_s":   (datetime.now() - start).total_seconds(),
    }


def run_wnba_prop_odds_ingestor(target_date: str = None,
                                snapshot_type: str = "open") -> dict:
    """Convenience wrapper — DK WNBA player prop lines for target_date."""
    return run_prop_odds_ingestor(target_date=target_date,
                                  snapshot_type=snapshot_type, sport="WNBA")


def run_nba_prop_odds_ingestor(target_date: str = None,
                               snapshot_type: str = "open") -> dict:
    """Convenience wrapper — DK NBA player prop lines for target_date."""
    return run_prop_odds_ingestor(target_date=target_date,
                                  snapshot_type=snapshot_type, sport="NBA")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch DK player prop odds")
    parser.add_argument("--date",     metavar="YYYY-MM-DD",
                        help="Date to fetch (default: today ET)")
    parser.add_argument("--sport", default="MLB", choices=["MLB", "WNBA", "NBA"],
                        help="Sport to fetch (default: MLB)")
    parser.add_argument("--snapshot", default="open",
                        choices=["open", "live"],
                        help="Snapshot type label (default: open)")
    args = parser.parse_args()

    result = run_prop_odds_ingestor(
        target_date=args.date,
        snapshot_type=args.snapshot,
        sport=args.sport,
    )
    logger.info(f"Done: {result}")

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
    ODDS_HISTORY_BOOKMAKERS,
    LINE_SHOP_BOOKMAKERS,
    SPORTS,
    WNBA_ODDS_API_MAP,
    NBA_ODDS_API_MAP,
)
from data.db import get_connection, DBConnection
from data.ingestors.odds_quota import record_quota_headers, persist_quota

# ── Constants ─────────────────────────────────────────────────────────────────

# The Odds API sport key → our sport label
SPORT_KEYS = {
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "WNBA": "basketball_wnba",
    "NBA": "basketball_nba",
    "UFC": "mma_mixed_martial_arts",
    "NCAAF": "americanfootball_ncaaf",
}

# Markets to pull (full-game)
MARKETS = ["h2h", "spreads", "totals"]

# MLB first-5-innings markets (pulled only for MLB)
MLB_F5_MARKETS = ["h2h_1st_5_innings", "spreads_1st_5_innings", "totals_1st_5_innings"]

# NHL 3-way regulation market (separate endpoint call)
NHL_3WAY_MARKET = "h2h_3way"

# Out of season DK offers no 3-way regulation market, but the events endpoint
# still lists the whole future slate, so the per-event loop walked all ~32 of
# them and 422'd on every one — ~1,300 wasted round trips a day, and 32 lines
# of error in every pass log, which is how a real error gets missed.
#
# The fix is a proximity window, not a season calendar and not a give-up-after-N
# circuit breaker. A calendar has to be right about the NHL's start date every
# year forever and is wrong silently. A breaker cannot tell "out of season"
# from "in season, but the first few events listed are far-future games" — it
# would abandon a market that IS being offered, which is exactly the failure
# that hid h2h_3way for months, so it is the one mechanism this must not use.
#
# Proximity separates the two cleanly and needs no maintenance: DK prices the
# regulation market for games that are about to happen, so an event more than
# this many days out is not worth a call either way. Out of season the nearest
# game is weeks off and the loop makes ZERO calls. In season it walks today's
# slate and nothing else.
THREE_WAY_LOOKAHEAD_DAYS = 3


def _within_lookahead(ev: dict, now: datetime | None = None,
                      days: int = THREE_WAY_LOOKAHEAD_DAYS) -> bool:
    """
    True when this event starts within the lookahead window.

    FAILS OPEN. A missing or unparseable commence_time returns True, so a real
    game is never silently dropped because its timestamp had a shape we did not
    expect — these fields arrive as text in mixed shapes ('Z' suffix vs offset
    vs naive) and a string comparison is not a time comparison.
    """
    raw = ev.get("commence_time")
    if not raw:
        return True
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return ts <= now + timedelta(days=days)

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
    if sport == "NCAAF":
        # Canonical NCAAF identity is the CFBD SCHOOL NAME, not an abbrev (136
        # FBS programs collide badly in 3 letters). The Odds API appends the
        # mascot ("Ohio State Buckeyes"); the resolver strips it against the
        # ncaaf_teams registry and falls back to the input unchanged.
        from data.ingestors.cfbd_ingestor import resolve_odds_api_school
        return resolve_odds_api_school(name)
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
    if sport == "NCAAF":
        from data.ingestors.cfbd_ingestor import build_ncaaf_game_id
        return build_ncaaf_game_id(game_date, away, home)
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

    # Log + persist remaining credits (headers present even on 401/429, so a
    # quota-dead key still records remaining=0 for the health check)
    record_quota_headers(resp)
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
            record_quota_headers(resp)
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
    record_quota_headers(resp)
    if resp.status_code in (404, 422):
        logger.warning(f"events endpoint {sport_key}: {resp.status_code} — {resp.text[:200]}")
        return []
    resp.raise_for_status()
    return resp.json()


def _get_event_odds(sport_key: str, event_id: str, markets: list[str],
                    bookmakers: str | None = None) -> dict | None:
    """Fetch odds for a single event id (per-event endpoint supports additional markets).

    BOOKMAKERS DEFAULTS TO EVERY BOOK, NOT DRAFTKINGS. This parameter said
    `ODDS_API_BOOKMAKER` from the day it was written, and it is the only route
    by which MLB F5 and UFC round totals are fetched — so those two markets were
    DK-only in the database while every bulk-endpoint market carried seven books.
    Measured 2026-09-02: `h2h_1st_5_innings` had 704 DK rows and zero from any
    other book, UFC `totals` 891 and zero, and 51 of 176 recent MLB pre-game
    BETs (every `mlb_f5_moneyline` pick) could not be line-shopped at all
    because there was nothing to shop against.

    This is the same bug, in the same file, as the one mike named on 2026-09-01
    about `_get_historical_odds` ("Pinnacle data is in odds api. I have brought
    this up several times. why do you ignore it.").

    COST, MEASURED 2026-09-03 against the live endpoint rather than taken from
    the docs -- and it is NOT free, which the first draft of this comment
    claimed. `x-requests-last` on the same event:

        F5, bookmakers=draftkings   -> cost 1, 1 market  (h2h_1st_5_innings)
        F5, all seven books         -> cost 3, 3 markets (+ spreads, totals F5)
        UFC totals, DK-only         -> cost 1
        UFC totals, all seven books -> cost 1

    So this endpoint bills per market RETURNED, not per market requested. DK
    alone offers only F5 moneyline; the other books offer F5 spreads and totals
    as well, so the call comes back with three markets and is billed for three.
    UFC round totals is one market either way and does not move.

    Net: ~+2 credits per MLB event per F5 fetch (~15 events, daily pipeline
    only) = roughly +30/day against 4,900,852 remaining. The extra spend buys
    F5 spreads and F5 totals, which this repo has never held.
    """
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set in .env")
    url = f"{ODDS_API_BASE}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey":       ODDS_API_KEY,
        "regions":      ODDS_API_REGIONS,
        "markets":      ",".join(markets),
        "bookmakers":   bookmakers or ODDS_API_BOOKMAKERS_PARAM,
        "oddsFormat":   "american",
        "includeLinks": "true",   # DK betslip deep links
        "includeSids":  "true",
    }
    resp = requests.get(url, params=params, timeout=15)
    record_quota_headers(resp)
    if resp.status_code in (404, 422):
        logger.debug(f"event {event_id}: {resp.status_code} (markets unsupported for this event)")
        return None
    # A book list the endpoint rejects must not take the whole market down: fall
    # back to the decision book, which is what this fetch returned before.
    # Mirrors the bulk fetch's own 422 fallback at _get_odds.
    if resp.status_code == 400 and (bookmakers or ODDS_API_BOOKMAKERS_PARAM) != ODDS_API_BOOKMAKER:
        logger.warning(f"event {event_id}: 400 on multi-book request — "
                       f"retrying DraftKings-only")
        return _get_event_odds(sport_key, event_id, markets,
                               bookmakers=ODDS_API_BOOKMAKER)
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


def _known_fighter_slugs(conn) -> set:
    """
    Slugs of fighters with at least one fight in `ufc_fight_log` — i.e.
    fighters whose bouts ufcstats actually records. NOT the whole `fighters`
    table: ufcstats hosts profile pages for Contender Series prospects whose
    DWCS bouts it never records (verified 2026-08-14 — zero Tuesday events in
    14.5K fight-log rows), so a profile-based set would keep entire DWCS cards
    that can never score. Empty set on any failure — callers treat that as
    "filter off" (fail open).
    """
    try:
        rows = conn.execute("""
            SELECT DISTINCT f.slug
            FROM fighters f
            JOIN ufc_fight_log l ON l.fighter_id = f.fighter_id
        """).fetchall()
        return {r[0] for r in rows if r[0]}
    except Exception as exc:
        logger.warning(f"fighters slug load failed ({exc}) — "
                       f"UFC phantom-event filter disabled this run")
        return set()


def _is_known_ufc_matchup(game_id: str, known_slugs: set) -> bool:
    """
    True when at least one fighter in a UFC game_id is a known ufcstats
    fighter. The Odds API's `mma_mixed_martial_arts` key lists EVERY promotion
    (Oktagon, Contender Series, PFL, ...), but ufcstats — our only results
    source — covers UFC events only, so a fight where NEITHER fighter is known
    can never score or settle and would sit as a phantom NULL-score games row
    forever (session 96b). Nothing scoreable is lost: the scorer's
    MIN_UFC_FIGHTS gate already skips both-unknown fights, and a real UFC
    debutant vs a veteran keeps its row via the veteran.

    Fails open: an empty slug set or an unexpected game_id shape keeps the
    row. Fighter slugs are hyphenated (never underscored), so the 4-way
    underscore split of `UFC_{date}_{away_slug}_{home_slug}` is unambiguous.
    """
    if not known_slugs:
        return True
    parts = game_id.split("_")
    if len(parts) != 4 or parts[0] != "UFC":
        return True
    return parts[2] in known_slugs or parts[3] in known_slugs


def _filter_ufc_phantom(game_rows: list[dict], odds_rows: list[dict],
                        known_slugs: set) -> tuple[list[dict], list[dict], int]:
    """Drop games (and their odds rows) where no fighter is UFC-known."""
    keep = {r["game_id"] for r in game_rows
            if _is_known_ufc_matchup(r["game_id"], known_slugs)}
    kept_games = [r for r in game_rows if r["game_id"] in keep]
    kept_odds  = [r for r in odds_rows if r["game_id"] in keep]
    return kept_games, kept_odds, len(game_rows) - len(kept_games)


def _fetch_ufc_totals_per_event(sport_key: str, snapshot_type: str,
                                snapshot_at: str,
                                known_slugs: set = None) -> list[dict]:
    """
    Attempt round-total lines for upcoming UFC fights via the per-event
    endpoint (totals is not in the bulk MMA feed). Every book in
    ODDS_API_BOOKMAKERS_PARAM, not DraftKings alone -- measured 2026-09-03, one
    market either way, so this widening costs nothing here. UFC volume is low
    (~13 fights/event, ~1 event/week) so this runs on every odds fetch.
    Returns [] without raising when the market isn't offered — the
    ufc_total_rounds model then scores prob-only against a synthetic line.

    known_slugs (optional): skip non-UFC promotions' events BEFORE spending a
    per-event credit on them (same predicate as the bulk phantom filter).
    """
    from data.ingestors.ufc_stats_ingestor import slugify_fighter

    events = _list_events(sport_key)
    if not events:
        return []

    event_responses = []
    for ev in events:
        event_id = ev.get("id")
        if not event_id:
            continue
        if known_slugs:
            # Alias-normalize before slugifying — same path _process_events
            # uses to build game_ids, so the predicate can't diverge from the
            # bulk filter for fighters carried in UFC_NAME_ALIASES.
            home_slug = slugify_fighter(
                _normalize_team(ev.get("home_team") or "", "UFC"))
            away_slug = slugify_fighter(
                _normalize_team(ev.get("away_team") or "", "UFC"))
            if home_slug not in known_slugs and away_slug not in known_slugs:
                continue  # non-UFC promotion — don't pay the per-event credit
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

    near = [ev for ev in events if _within_lookahead(ev)]
    if not near:
        logger.info(
            f"NHL 3-way: none of {len(events)} listed events start within "
            f"{THREE_WAY_LOOKAHEAD_DAYS} days — out of season, skipping")
        return []
    if len(near) < len(events):
        logger.debug(f"NHL 3-way: {len(near)} of {len(events)} events in window")

    event_responses = []
    for ev in near:
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
                          snapshot_date: str, hour_utc: int = 12,
                          bookmakers: list[str] | None = None) -> list[dict]:
    """
    Call The Odds API historical odds endpoint.

    snapshot_date: ISO date YYYY-MM-DD. hour_utc picks the moment WITHIN that
    day, which is the whole point of the parameter: one snapshot per date gives
    a level, and two or more give MOVEMENT — the quantity
    features/market_movement.py needs and that the stored history does not have
    for any season before 2026.

    bookmakers defaults to config.ODDS_HISTORY_BOOKMAKERS rather than DK alone.
    This function requested `bookmakers=draftkings` from the day it was written,
    which is why Supabase holds seventeen seasons of single-book consensus and
    five days of Pinnacle: not because the data was unavailable, but because we
    never asked for it. The `bookmakers` param counts as ONE region, so naming
    seven books costs exactly what naming one costs.

    NOTE: the historical endpoint bills 10x the regular rate.
    """
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set in .env")

    books = bookmakers or ODDS_HISTORY_BOOKMAKERS
    # Historical endpoint expects ISO 8601 datetime
    snapshot_ts = f"{snapshot_date}T{int(hour_utc):02d}:00:00Z"
    url = f"{ODDS_API_BASE}/historical/sports/{sport_key}/odds"
    params = {
        "apiKey":       ODDS_API_KEY,
        "regions":      ODDS_API_REGIONS,
        "markets":      ",".join(markets),
        "bookmakers":   ",".join(books),
        "oddsFormat":   "american",
        "date":         snapshot_ts,
        "includeLinks": "true",
        "includeSids":  "true",
    }

    resp = requests.get(url, params=params, timeout=20)
    record_quota_headers(resp)
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
        elif sport == "NCAAF" and month <= 2:
            # CFB is labeled by the year of the FALL, so a January bowl or
            # playoff game belongs to the PRIOR season. Mirror image of the
            # NHL/NBA rule above — and the same footgun if it is missed.
            season = year - 1
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


def fetch_pregame_rows(sports: list, snapshot_type: str = "open") -> list[dict]:
    """Fetch and parse the bulk game lines for `sports` WITHOUT writing.

    This is the read half of run_odds_ingestor, split out for the 30-second
    pre-game poller (data/ingestors/pregame_line_poller.py), which has to see
    the parsed rows BEFORE deciding whether any of them are worth storing.

    It deliberately reuses _get_odds and _process_events rather than
    reimplementing them: team normalisation, game_id construction and outcome
    parsing all have sport-specific edge cases, and a second copy would drift
    from this one exactly as the Discord renderer drifted from its fixture
    (§7). The UFC phantom filter is applied here too, for the same reason --
    the MMA feed mixes promotions, and a poller writing phantom games every 30
    seconds would accumulate them 40x faster than the hourly pass did.

    Per-event markets (F5, NHL 3-way, UFC round totals) are NOT fetched. They
    cost one call per event, which is the expensive shape, and none of them is
    what a fast pre-game watch is for.

    Never raises: one sport's failure returns that sport's rows as empty and
    leaves the others intact, because a poller that dies on one bad payload is
    indistinguishable from a quiet market.
    """
    snapshot_at = datetime.now(ZoneInfo("America/New_York")).isoformat()
    rows: list[dict] = []
    conn = None
    for sp in sports:
        sport_key = SPORT_KEYS.get(sp)
        if not sport_key:
            continue
        markets = UFC_BULK_MARKETS[:] if sp == "UFC" else MARKETS[:]
        try:
            events = _get_odds(sport_key, markets)
        except Exception as exc:                              # noqa: BLE001
            logger.error(f"pregame fetch {sp} failed: {exc}")
            continue
        if not events:
            continue
        game_rows, odds_rows = _process_events(events, sp, snapshot_type, snapshot_at)
        if sp == "UFC":
            try:
                conn = conn or get_connection()
                game_rows, odds_rows, _ = _filter_ufc_phantom(
                    game_rows, odds_rows, _known_fighter_slugs(conn))
            except Exception as exc:                          # noqa: BLE001
                logger.warning(f"pregame fetch: UFC phantom filter skipped ({exc})")
        rows.extend(odds_rows)
    return rows


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

    sports = [sport] if sport else ["MLB", "NHL", "WNBA", "NBA", "UFC", "NCAAF"]
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

            # The MMA feed mixes every promotion; drop events where no fighter
            # is UFC-known so phantom never-scoreable games rows stop
            # accumulating (session 96b). Fails open on a slug-load error.
            ufc_known_slugs: set = set()
            if sp == "UFC":
                ufc_known_slugs = _known_fighter_slugs(conn)
                game_rows, odds_rows, n_phantom = _filter_ufc_phantom(
                    game_rows, odds_rows, ufc_known_slugs)
                if n_phantom:
                    logger.info(f"UFC: skipped {n_phantom} non-UFC "
                                f"(unknown-fighter) event(s)")

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
                        sport_key, snapshot_type, snapshot_at,
                        known_slugs=ufc_known_slugs)
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
        # Persist the latest x-requests-remaining observation (own commit,
        # swallows errors) — feeds the odds_api_credits health check.
        persist_quota(conn)
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


PULL_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS odds_history_pulls (
    sport         TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    hour_utc      INTEGER NOT NULL,
    pulled_at     TIMESTAMPTZ NOT NULL,
    rows          INTEGER NOT NULL,
    PRIMARY KEY (sport, snapshot_date, hour_utc)
)
"""


def _mark_in_play(game_rows: list[dict], odds_rows: list[dict]) -> int:
    """Re-label rows whose snapshot is AFTER first pitch. Returns how many.

    A 22:00Z historical snapshot catches afternoon games in the sixth inning,
    and _process_events labels everything "open" because that is what the
    caller asked for. Storing a live price as a pre-game one is the exact leak
    §7 warns about, and it is not theoretical here: the pilot wrote
    ARI@NYM at 21:55Z as home -1213 / away +747, which is a mid-game number
    sitting in a column every pre-game reader trusts.

    The feature loaders bound on `snapshot_at <= commence_time` and so were
    already safe; this stops the TABLE from lying to anything that does not.
    """
    # first_pitch_at where known; the row dicts built here carry only
    # commence_time, so the caller's map is the scheduled time and the DB-side
    # repair (relabel_in_play) applies the better bound.
    commence = {g["game_id"]: g.get("first_pitch_at") or g.get("commence_time")
                for g in game_rows}
    flipped = 0
    for row in odds_rows:
        start = commence.get(row.get("game_id"))
        snap = row.get("snapshot_at")
        if not start or not snap:
            continue                      # fail open: unknown timing stays as-is
        try:
            s_dt = datetime.fromisoformat(str(snap).replace("Z", "+00:00"))
            c_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        except ValueError:
            continue
        if s_dt > c_dt:
            row["snapshot_type"] = "in_play"
            flipped += 1
    return flipped


def relabel_in_play(sport: str, since: str = "2000-01-01") -> dict:
    """Re-stamp stored rows whose snapshot is after first pitch as in_play.

    A repair, not a routine: the historical backfill labelled everything "open"
    before _mark_in_play existed, so the rows its first run wrote include live
    prices wearing a pre-game label. Runs as a job so the fix reaches production
    the same way the bug did.

    Bounded by `since` and by sport so a repair can be scoped to exactly the
    rows a known-bad run produced, rather than rewriting seventeen years of
    history to fix three days of it.
    """
    conn = get_connection()
    try:
        # PARSED, not string-compared. §7 says it in as many words -- "these
        # columns are TEXT in mixed shapes; a string comparison silently keeps
        # leaked rows" -- and the first version of this function did it anyway.
        # Measured on this database: odds.snapshot_at is naive-or-Z,
        # games.commence_time carries a -04:00 offset. Comparing those as text
        # compares a UTC hour against an ET hour and is wrong by the offset.
        #
        # ONE-DIRECTIONAL on purpose. It can promote 'open' -> 'in_play' and
        # never the reverse: the live loop labels rows from GAME STATE, and a
        # scheduled commence_time is not the actual first pitch (rain delays,
        # late starts). 48,712 rows in this database are labelled in_play with
        # a timestamp at or before their scheduled start, and re-labelling
        # those "pre-game" on the strength of a schedule would manufacture the
        # leak this function exists to remove.
        cur = conn.execute("""
            UPDATE odds o
               SET snapshot_type = 'in_play'
              FROM games g
             WHERE g.game_id = o.game_id
               AND o.sport = %s
               AND o.snapshot_at >= %s
               AND COALESCE(o.snapshot_type, '') <> 'in_play'
               AND COALESCE(g.first_pitch_at, g.commence_time) IS NOT NULL
               AND (CASE WHEN o.snapshot_at LIKE '%%Z'
                          OR o.snapshot_at ~ '[+-][0-9]{2}:[0-9]{2}$'
                         THEN o.snapshot_at::timestamptz
                         ELSE (o.snapshot_at || 'Z')::timestamptz END)
                   > COALESCE(g.first_pitch_at, g.commence_time)::timestamptz
            RETURNING o.odds_id
        """, (sport.upper(), since)).fetchall()
        conn.commit()
        n = len(cur or [])
        logger.success(f"relabelled {n} {sport} odds rows as in_play (since {since})")
        return {"sport": sport.upper(), "since": since, "relabelled": n}
    finally:
        conn.close()


def run_historical_odds_range(sport: str, start: str, end: str,
                              hours_utc: list[int] | None = None,
                              bookmakers: list[str] | None = None,
                              credit_cap: int = 25_000) -> dict:
    """Backfill a DATE RANGE of historical odds, several snapshots per day.

    This is what makes market-movement features trainable on more than the 2026
    season. `run_historical_odds` pulls one snapshot for one date from one book;
    movement needs at least two moments, and a model needs more than one season
    of them.

    RESUMABLE BY CONSTRUCTION. Before spending on a (date, hour) it checks
    whether rows already exist for that snapshot -- so a run that dies halfway,
    or a second run over an overlapping range, costs nothing for what is already
    stored. The historical endpoint bills 10x, and a backfill that cannot resume
    is a backfill nobody dares restart.

    CREDIT-CAPPED, and the cap is not advisory: the loop stops the moment the
    next call would cross it, and reports how far it got. An unbounded range
    over seven seasons at 30 credits a call is six figures.

    Cost model: 10 credits x n_markets x n_regions, and `bookmakers` counts as
    one region. Three markets => ~30 credits per (date, hour), whether one book
    is named or seven.
    """
    from datetime import date as _date, timedelta as _td

    sport = sport.upper()
    sport_key = SPORT_KEYS[sport]
    hours = sorted(set(hours_utc or [12, 22]))
    books = bookmakers or ODDS_HISTORY_BOOKMAKERS
    markets = MARKETS[:]
    per_call = 10 * len(markets)          # bookmakers param = one region

    d0 = _date.fromisoformat(start)
    d1 = _date.fromisoformat(end)
    spent = 0
    stats = {"sport": sport, "start": start, "end": end, "hours_utc": hours,
             "bookmakers": books, "credit_cap": credit_cap,
             "calls": 0, "skipped_cached": 0, "credits_spent": 0,
             "marked_in_play": 0,
             "games": 0, "odds_rows": 0, "errors": 0,
             "stopped_early": False, "last_date": None}

    conn = get_connection()
    try:
        conn.execute(PULL_LEDGER_DDL)
        conn.commit()
        day = d0
        while day <= d1:
            for hour in hours:
                snapshot_at = f"{day.isoformat()}T{hour:02d}:00:00Z"
                # Resume against a LEDGER of what we pulled, not against the
                # timestamp we asked for. The API stamps each row with the
                # market's own last_update -- a 12:00Z request comes back as
                # 11:55:34Z -- so the obvious `WHERE snapshot_at = ...` check
                # never matches and every re-run re-spends the whole range at
                # 10x rates. Found by reading the rows the pilot wrote.
                already = conn.execute("""
                    SELECT 1 FROM odds_history_pulls
                     WHERE sport=%s AND snapshot_date=%s AND hour_utc=%s LIMIT 1
                """, (sport, day.isoformat(), hour)).fetchone()
                if already:
                    stats["skipped_cached"] += 1
                    continue
                if spent + per_call > credit_cap:
                    stats["stopped_early"] = True
                    logger.warning(
                        f"historical backfill stopping at {snapshot_at}: next call "
                        f"would spend {spent + per_call} of a {credit_cap} cap")
                    stats["credits_spent"] = spent
                    stats["last_date"] = day.isoformat()
                    return stats
                try:
                    events = _get_historical_odds(sport_key, markets,
                                                  day.isoformat(), hour, books)
                    spent += per_call
                    stats["calls"] += 1
                    time.sleep(REQUEST_SLEEP)
                    game_rows, odds_rows = _process_events(
                        events, sport, "open", snapshot_at)
                    flipped = _mark_in_play(game_rows, odds_rows)
                    stats["marked_in_play"] += flipped
                    if game_rows:
                        stats["games"] += _upsert_games(conn, game_rows)
                    if odds_rows:
                        stats["odds_rows"] += _insert_odds(conn, odds_rows)
                    conn.execute("""
                        INSERT INTO odds_history_pulls
                            (sport, snapshot_date, hour_utc, pulled_at, rows)
                        VALUES (%s, %s, %s, NOW(), %s)
                        ON CONFLICT (sport, snapshot_date, hour_utc) DO UPDATE
                            SET pulled_at = NOW(), rows = EXCLUDED.rows
                    """, (sport, day.isoformat(), hour, len(odds_rows)))
                    conn.commit()
                except Exception as exc:  # noqa: BLE001 — one bad day must not end the run
                    stats["errors"] += 1
                    logger.warning(f"historical {sport} {snapshot_at} failed: {exc}")
                    try:
                        conn.rollback()
                    except Exception:  # noqa: BLE001
                        pass
            stats["last_date"] = day.isoformat()
            day += _td(days=1)
    finally:
        conn.close()

    stats["credits_spent"] = spent
    logger.success(
        f"historical {sport} {start}..{end}: {stats['calls']} calls, "
        f"{spent} credits, {stats['odds_rows']} odds rows, "
        f"{stats['skipped_cached']} already stored, {stats['errors']} errors")
    return stats


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
    parser.add_argument("--sport", choices=["MLB", "NHL", "WNBA", "NBA", "UFC", "NCAAF"],
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

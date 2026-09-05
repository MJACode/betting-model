"""
prop_odds_ingestor.py — multi-book player prop odds via The Odds API.

Fetches all player prop markets for every game today, at every book in
config.LINE_SHOP_BOOKMAKERS, and stores lines in player_prop_odds. This is the
collection layer — no scoring is done here.

DraftKings vs the rest: the models score props ONLY against the draftkings rows
(models/scorer.py `_get_prop_dk_odds` filters `bookmaker = 'draftkings'`). Every
other book is display-only, so the app can show the user the price at the book
they actually bet.

How it works:
  1. GET /v4/sports/{sport}/events  → list of today's event IDs
  2. For each event, GET /v4/sports/{sport}/events/{id}/odds
     with all prop markets, for all line-shop bookmakers (one call per game)
  3. Parse player name + line + over/under prices, once per book
  4. Insert into player_prop_odds (append-only snapshots)

Credit cost: ~1 credit per game per call — UNCHANGED by multi-book. The Odds API
counts the `bookmakers` param as a single region, so N books cost the same as one.
Row volume, however, scales with the number of books.

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
    LINE_SHOP_BOOKMAKERS,
    ODDS_API_BASE,
    ODDS_API_BOOKMAKER,
    ODDS_API_BOOKMAKERS_PARAM,
    ODDS_API_KEY,
    ODDS_API_REGIONS,
    PROP_MARKETS_ALL,
    PROP_MARKETS_WNBA,
    PROP_MARKETS_NBA,
    PROP_ALT_MARKETS,
    PROP_ALT_REFRESH_MIN,
)
from data.db import get_connection, DBConnection
from data.ingestors.odds_quota import record_quota_headers, persist_quota
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
# `player_anytime_td` is the same shape: Yes/No, no numeric `point`. Without
# it here the parser drops every row and the market looks like it does not
# exist — which is exactly how it read on the first backfill.
YESNO_DEFAULT_LINE_MARKETS = {"batter_home_runs", "player_double_double",
                              "player_anytime_td"}

# DraftKings does NOT serve the standard `batter_home_runs` market via The Odds
# API (verified 2026-06-20 — DK returns batter_hits/total_bases but never
# batter_home_runs). It serves "to hit a home run" under `batter_home_runs_alternate`
# (the 0.5-line over at real +250..+500 prices, plus a 1.5 multi-HR line).
# Request the alternate and remap its 0.5 line back to our canonical
# batter_home_runs market so the scorer/settlement are unchanged. Its OTHER
# lines were dropped until 2026-09-05; they are now kept under the alternate
# key like every other alternate line (below).
ALT_MARKET_REMAP = {"batter_home_runs_alternate": "batter_home_runs"}
ALT_KEEP_POINT   = {"batter_home_runs_alternate": 0.5}
# Extra request-only markets per sport, requested on EVERY pass because a
# model prices off them (the HR remap above).
EXTRA_REQUEST_MARKETS = {"MLB": ["batter_home_runs_alternate"]}

# ALTERNATE LINES (Matt, 2026-09-05: "Yes to alternate lines"). The
# `*_alternate` markets in config.PROP_ALT_MARKETS carry every milestone a
# book posts -- 2+/3+ hits, 7+/8+ strikeouts -- and are written UNDER THEIR
# OWN MARKET KEY, one row per (player, line), never folded into the standard
# market. Every model-facing read takes the newest DraftKings row for (game,
# player, market) and must keep finding exactly one standard line there;
# config.py has the reasoning. The app reads the alternate key beside the
# standard one (mobile/src/lib/propLines.ts) and the all-books view returns
# every line the newest pass wrote for an alternate key
# (data/migrations/alternate_prop_lines_view.sql).
#
# They are requested at most every config.PROP_ALT_REFRESH_MIN minutes
# (_alt_markets_due) because each market costs ~2 credits per event call
# (measured, config.py) and the evening pass runs every 10 minutes.
ALT_LINE_MARKETS = frozenset(m for ms in PROP_ALT_MARKETS.values() for m in ms)


def _is_alt_line_market(market: str) -> bool:
    """A market key stored as-is with one row per line (never remapped)."""
    return market.endswith("_alternate")


def alt_markets_due(conn: DBConnection, sport: str, target_date: str,
                    now: datetime | None = None) -> bool:
    """Should this pass request the alternate markets?

    True when the sport has any, and the newest alternate row for the date is
    older than PROP_ALT_REFRESH_MIN minutes (or there is none). A failed check
    answers False and WARNS: a broken gate that spent every pass would double
    the approved credit budget silently, whereas stale alternates are visible
    on the board and in this log line.
    """
    markets = PROP_ALT_MARKETS.get(sport) or []
    if not markets:
        return False
    if PROP_ALT_REFRESH_MIN <= 0:
        return True
    try:
        row = conn.execute("""
            SELECT max(snapshot_at)
            FROM player_prop_odds
            WHERE game_date = %s AND market = ANY(%s)
        """, (target_date, list(markets))).fetchone()
    except Exception as exc:  # noqa: BLE001 -- the gate must never abort the pass
        logger.warning(f"Alternate-line gate failed ({exc}); NOT requesting alternates this pass")
        return False
    newest = row[0] if row else None
    if not newest:
        return True
    try:
        newest_dt = datetime.fromisoformat(str(newest).replace("Z", "+00:00"))
    except ValueError:
        return True
    now = now or datetime.now(newest_dt.tzinfo)
    age_min = (now - newest_dt).total_seconds() / 60.0
    return age_min >= PROP_ALT_REFRESH_MIN

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

    record_quota_headers(resp)
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
                     sport_key: str = SPORT_KEY) -> list[tuple[str, list[dict]]]:
    """
    Fetch player prop odds for a single event, for every line-shop bookmaker.

    Returns [(bookmaker_key, markets_list), ...] — one entry per book that priced
    the event — or [] on error. DraftKings is the book the models score against;
    the rest are display-only line shopping.

    Multi-book costs NOTHING extra: The Odds API counts the `bookmakers` param as
    a single region, so this is the same credit spend as the old DK-only call.
    """
    url = f"{ODDS_API_BASE}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey":       ODDS_API_KEY,
        "regions":      ODDS_API_REGIONS,
        "markets":      ",".join(markets),
        "bookmakers":   ODDS_API_BOOKMAKERS_PARAM,
        "oddsFormat":   "american",
        "includeLinks": "true",   # betslip deep links per prop selection, per book
        "includeSids":  "true",
    }

    resp = requests.get(url, params=params, timeout=20)
    record_quota_headers(resp)

    if resp.status_code == 422:
        # An alternate key the API does not recognise for this sport would
        # 422 the WHOLE call and cost the models their standard lines. Drop the
        # alternate-line markets and retry before anything else; the standard
        # set has been accepted for months.
        alts = [m for m in markets if m in ALT_LINE_MARKETS]
        if alts:
            logger.warning(f"Event {event_id}: 422 with alternate markets "
                           f"({resp.text[:160]!r}) — retrying without them")
            params["markets"] = ",".join(m for m in markets if m not in ALT_LINE_MARKETS)
            resp = requests.get(url, params=params, timeout=20)
            record_quota_headers(resp)

    if resp.status_code == 422:
        # Usually an unsupported market for this event, but can also be an
        # unsupported bookmaker key. Retry DK-only so a renamed display-only book
        # can never cost us the prop lines the models actually score against.
        logger.warning(f"Event {event_id}: 422 on prop markets (book/market unsupported)")
        if params["bookmakers"] != ODDS_API_BOOKMAKER:
            params["bookmakers"] = ODDS_API_BOOKMAKER
            resp = requests.get(url, params=params, timeout=20)
            record_quota_headers(resp)
            if resp.status_code != 200:
                return []
        else:
            return []
    elif resp.status_code != 200:
        logger.warning(f"Event {event_id}: HTTP {resp.status_code}")
        return []

    data = resp.json()
    out: list[tuple[str, list[dict]]] = []
    for book in data.get("bookmakers", []):
        key = book.get("key")
        # Ignore anything we didn't ask for, so an API-side change can't quietly
        # write an unexpected book into player_prop_odds.
        if key not in LINE_SHOP_BOOKMAKERS:
            continue
        out.append((key, book.get("markets", [])))

    if not any(k == ODDS_API_BOOKMAKER for k, _ in out):
        logger.debug(f"Event {event_id}: DraftKings not in response")

    return out


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_prop_markets(markets_data: list[dict], game_id: str,
                        game_date: str, snapshot_type: str,
                        snapshot_at: str,
                        allowed_markets=PROP_MARKETS_ALL,
                        bookmaker: str = ODDS_API_BOOKMAKER) -> list[dict]:
    """
    Parse one bookmaker's markets list into DB rows.

    `bookmaker` is stamped onto every row. Call once per book — rows for the same
    player/market at different books are independent and must not be merged.

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
        "bookmaker":    bookmaker,
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
        # An alternate market carries several lines per player. The configured
        # line (DK's batter_home_runs_alternate at 0.5) is remapped to the
        # canonical market the model prices; every other line stays under the
        # alternate key, one row per (player, line), so no canonical market
        # ever holds two lines for one player (config.PROP_ALT_MARKETS).
        is_alt  = _is_alt_line_market(market_key)
        keep_pt = ALT_KEEP_POINT.get(market_key)

        for outcome in mkt.get("outcomes", []):
            name_field = (outcome.get("name") or "").strip()
            desc_field = (outcome.get("description") or "").strip()
            price = outcome.get("price")
            point = outcome.get("point")
            link  = outcome.get("link")
            sid   = outcome.get("sid")

            if is_alt and keep_pt is not None and point == keep_pt:
                out_market = ALT_MARKET_REMAP[market_key]
            elif is_alt:
                if point is None:
                    continue   # a milestone with no number cannot be a line
                out_market = market_key
            else:
                out_market = market_key

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
            if point is None and out_market in YESNO_DEFAULT_LINE_MARKETS:
                point = 0.5

            # Alternate rows are keyed by line as well: the whole point is
            # that one player has several.
            key = (out_market, player_name, point) if _is_alt_line_market(out_market) \
                else (out_market, player_name)
            row = player_rows[key]
            row["player_name"] = player_name
            row["market"]      = out_market
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
    # An alternate line that duplicates this book's STANDARD line for the same
    # player (1+ hits beside batter_hits 0.5) is the same proposition twice;
    # the standard row is the one the app and the models already read.
    standard = {(r["market"], r["player_name"], r["line"])
                for r in result if not _is_alt_line_market(r["market"])}
    result = [r for r in result
              if not (_is_alt_line_market(r["market"])
                      and (r["market"][:-len("_alternate")], r["player_name"], r["line"]) in standard)]
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
    markets   = list(PROP_MARKETS_BY_SPORT.get(sport, PROP_MARKETS_ALL))
    # Request extra source markets that get remapped to canonical on parse
    # (e.g. DK's batter_home_runs_alternate → batter_home_runs).
    markets  += EXTRA_REQUEST_MARKETS.get(sport, [])

    snapshot_at = datetime.now(_ET).isoformat()
    start = datetime.now()

    logger.info(f"Prop odds ingestor: {sport} {target_date} ({snapshot_type})")

    conn = get_connection()
    # The alternate-line markets ride on the same event call, at most every
    # PROP_ALT_REFRESH_MIN minutes (credits: config.PROP_ALT_MARKETS).
    if alt_markets_due(conn, sport, target_date):
        markets += PROP_ALT_MARKETS.get(sport, [])
        logger.info(f"  alternate lines requested this pass: {PROP_ALT_MARKETS.get(sport)}")
    allowed = set(markets)
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
                books_data = _get_event_props(event["id"], markets, sport_key)
                time.sleep(REQUEST_SLEEP)
            except Exception as exc:
                logger.warning(f"Props fetch failed for {game_id}: {exc}")
                continue

            if not books_data:
                logger.debug(f"No prop markets returned for {game_id}")
                continue

            # Parse each book separately — same player/market at two books are
            # two independent rows (the app line-shops across them; the models
            # only ever read the draftkings rows).
            rows: list[dict] = []
            for book_key, markets_data in books_data:
                rows.extend(_parse_prop_markets(
                    markets_data, game_id, event["game_date"],
                    snapshot_type, snapshot_at, allowed_markets=allowed,
                    bookmaker=book_key,
                ))

            if rows:
                n = _insert_prop_odds(conn, rows)
                total_rows   += n
                total_events += 1
                logger.info(f"  {away_team} @ {home_team}: {n} prop rows "
                            f"({len(set(r['market'] for r in rows))} markets, "
                            f"{len(set(r['player_name'] for r in rows))} players, "
                            f"{len(set(r['bookmaker'] for r in rows))} books)")
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
        # Persist the latest x-requests-remaining observation (own commit,
        # swallows errors) — feeds the odds_api_credits health check.
        persist_quota(conn)
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

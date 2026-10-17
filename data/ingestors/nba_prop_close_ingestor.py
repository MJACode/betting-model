"""The closing prop snapshot for every game holding an NBA prop bet (either NBA prop model).

WHY. Bar 11 of the 2026-27 rebuild (docs/nba_models_2026.md section 1) is
closing-line value, and it could not be measured on the archive the rule was
graded on: one snapshot a game, an hour before tip. So from night one every
bet gets a later price to be graded against. mike, 2026-10-15.

WHAT IT BUYS. For each game with an nba_prop_market BET, ONE event call
between NBA_PROP_CLOSE_OPENS_MIN (25) and NBA_PROP_CLOSE_CLOSES_MIN (12)
minutes before the scheduled tip, for the markets bet on that game only, at
every fetched book. Filed `snapshot_type = 'close'` -- the NHL final's
mechanism (data/ingestors/nhl_prop_odds_ingestor.py): no card reads 'close'
(scripts/nba_prop_market_card reads 'open' only), and the CLV capture
(tracking/paper_tracker._closing_prop_odds) reads the newest pre-start row of
any type at the bet's own book. Twelve minutes is the inside edge because the
tip is the league's scheduled start and a quote taken after the real tip is
an in-play price.

THE GATE IS THE POINT. `due()` answers from what is stored, so a pass with no
bet game in the window spends nothing at all: no event list, no event call.

COST, read off every response's `x-requests-last` and returned, never assumed;
the run stops at NBA_PROP_CLOSE_MAX_CREDITS_PER_RUN. The feed bills markets x
regions, and ten named books are one region (config.LINE_SHOP_BOOKMAKERS), so
a one-market close is expected to bill 1 credit. That expectation was not
spent to check; tests/test_nba_prop_close.py pins that the run reports what
the header says.

    python -m data.ingestors.nba_prop_close_ingestor            # buy what is due
    python -m data.ingestors.nba_prop_close_ingestor --dry-run  # say what is due, spend nothing
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

from config import (
    LINE_SHOP_BOOKMAKERS,
    NBA_PROP_CLOSE_CLOSES_MIN,
    NBA_PROP_CLOSE_MAX_CREDITS_PER_RUN,
    NBA_PROP_CLOSE_OPENS_MIN,
    ODDS_API_BASE,
    ODDS_API_BOOKMAKERS_PARAM,
    ODDS_API_KEY,
    ODDS_API_REGIONS,
)
from data.db import DBConnection, get_connection
from data.ingestors.odds_ingestor import SPORT_KEYS, _build_game_id, _normalize_team
from data.ingestors.odds_quota import persist_quota, record_quota_headers
from data.ingestors.prop_odds_ingestor import (
    REQUEST_SLEEP,
    _insert_prop_odds,
    _parse_prop_markets,
)

ET = ZoneInfo("America/New_York")
SPORT_KEY = SPORT_KEYS["NBA"]
MODEL_ID = "nba_prop_market"
# Every NBA prop model whose bets get a closing snapshot: the rule, and the
# projection model (models/nba_prop_projection.py, 2026-10-16), whose bar 11 is
# unmeasured for the same reason.
MODEL_IDS = ("nba_prop_market", "nba_prop_projection")
SNAPSHOT_TYPE = "close"          # read by the CLV capture, never by a card


def due(tip: datetime, now: datetime, has_bet: bool, close_taken: bool,
        opens_min: int = NBA_PROP_CLOSE_OPENS_MIN,
        closes_min: int = NBA_PROP_CLOSE_CLOSES_MIN) -> bool:
    """Is this game owed its closing snapshot on this pass?

    Only a game holding a bet, only once, only inside [tip - opens, tip - closes).
    """
    if not has_bet or close_taken:
        return False
    return tip - timedelta(minutes=opens_min) <= now < tip - timedelta(minutes=closes_min)


def bet_games(conn: DBConnection, now: datetime) -> dict[str, dict]:
    """{game_id: {"markets": [...], "tip", "home", "away", "game_date"}} for every
    NBA prop BET (MODEL_IDS) whose game tips within the close window's far end."""
    from models.nba_prop_market import tip_of
    today = now.astimezone(ET).date()
    dates = [(today + timedelta(days=d)).isoformat() for d in (-1, 0, 1)]
    rows = conn.execute("""
        SELECT p.game_id, p.prop_market, g.home_team, g.away_team, g.game_date,
               g.commence_time, s.commence_time
        FROM picks p
        JOIN games g ON g.game_id = p.game_id
        LEFT JOIN nba_schedule s ON s.game_id = p.game_id
        WHERE p.model_id = ANY(%s) AND p.signal_type = 'BET' AND p.game_date = ANY(%s)
    """, (list(MODEL_IDS), dates)).fetchall()
    out: dict[str, dict] = {}
    for gid, market, home, away, gd, g_ct, s_ct in rows:
        tip = tip_of(s_ct, g_ct)
        if tip is None or tip <= now or tip - now > timedelta(minutes=NBA_PROP_CLOSE_OPENS_MIN):
            continue
        g = out.setdefault(gid, {"markets": [], "tip": tip, "home": home,
                                 "away": away, "game_date": str(gd)[:10]})
        if market and market not in g["markets"]:
            g["markets"].append(market)
    return out


def closes_taken(conn: DBConnection, game_ids: list[str]) -> set[str]:
    """Games whose 'close' snapshot is already stored. Asked BY GAME ID."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT game_id FROM player_prop_odds "
        "WHERE game_id = ANY(%s) AND snapshot_type = %s",
        (list(game_ids), SNAPSHOT_TYPE)).fetchall()}


def _events() -> tuple[list[dict], int]:
    """NBA events from the feed (the list is free; its cost is read, not assumed)."""
    resp = requests.get(f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events",
                        params={"apiKey": ODDS_API_KEY, "dateFormat": "iso"}, timeout=15)
    record_quota_headers(resp)
    cost = int(float(resp.headers.get("x-requests-last") or 0))
    if resp.status_code != 200:
        logger.warning(f"NBA close: event list HTTP {resp.status_code}: {resp.text[:160]}")
        return [], cost
    out = []
    for ev in resp.json():
        try:
            start = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        out.append({"id": ev["id"], "home": ev.get("home_team", ""),
                    "away": ev.get("away_team", ""),
                    "game_date": start.astimezone(ET).strftime("%Y-%m-%d")})
    return out, cost


def _event_props(event_id: str, markets: list[str]) -> tuple[list[tuple], int]:
    """One paid call: the bet markets at every fetched book. -> ((book, last_update,
    markets) triples, the credits the feed billed)."""
    resp = requests.get(
        f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{event_id}/odds",
        params={"apiKey": ODDS_API_KEY, "regions": ODDS_API_REGIONS,
                "markets": ",".join(markets), "bookmakers": ODDS_API_BOOKMAKERS_PARAM,
                "oddsFormat": "american", "includeLinks": "true", "includeSids": "true"},
        timeout=20)
    record_quota_headers(resp)
    cost = int(float(resp.headers.get("x-requests-last") or 0))
    if resp.status_code != 200:
        logger.warning(f"NBA close: event {event_id} HTTP {resp.status_code}: {resp.text[:160]}")
        return [], cost
    books = [(b.get("key"), b.get("last_update"), b.get("markets", []))
             for b in resp.json().get("bookmakers", [])
             if b.get("key") in LINE_SHOP_BOOKMAKERS]
    return books, cost


def run_nba_prop_close_ingestor(now: datetime | None = None, dry_run: bool = False) -> dict:
    """Buy the closing snapshot for every bet game whose close is due."""
    now = now or datetime.now(timezone.utc)
    out = {"due": 0, "bought": 0, "prop_rows": 0, "credits": 0,
           "credits_by_game": {}, "no_event": 0, "not_priced": 0}
    conn = get_connection()
    try:
        games = bet_games(conn, now)
        if not games:
            return out
        taken = closes_taken(conn, sorted(games))
        owed = {gid: g for gid, g in games.items()
                if due(g["tip"], now, has_bet=True, close_taken=gid in taken)}
        out["due"] = len(owed)
        if not owed:
            return out
        if dry_run:
            for gid, g in owed.items():
                logger.info(f"  {gid}: close due for {g['markets']} (dry run, nothing bought)")
            return out
        if not ODDS_API_KEY:
            raise ValueError("ODDS_API_KEY not set")
        events, cost = _events()
        out["credits"] += cost
        by_id = {}
        for ev in events:
            gid = _build_game_id("NBA", ev["game_date"], _normalize_team(ev["away"], "NBA"),
                                 _normalize_team(ev["home"], "NBA"))
            by_id[gid] = ev["id"]
        snapshot_at = now.isoformat()            # '+00:00', never 'Z' (backfilled_dates)
        for gid, g in sorted(owed.items()):
            if out["credits"] >= NBA_PROP_CLOSE_MAX_CREDITS_PER_RUN:
                logger.warning(f"NBA close: {out['credits']} credits this run, at the "
                               f"{NBA_PROP_CLOSE_MAX_CREDITS_PER_RUN} ceiling; stopping")
                break
            event_id = by_id.get(gid)
            if event_id is None:
                out["no_event"] += 1
                logger.warning(f"NBA close: {gid} is not in the feed's event list; no close bought")
                continue
            books, cost = _event_props(event_id, g["markets"])
            out["credits"] += cost
            out["credits_by_game"][gid] = cost
            time.sleep(REQUEST_SLEEP)
            rows: list[dict] = []
            for book, last_update, markets in books:
                rows += _parse_prop_markets(markets, gid, g["game_date"], SNAPSHOT_TYPE,
                                            snapshot_at, allowed_markets=set(g["markets"]),
                                            bookmaker=book, book_last_update=last_update)
            if not rows:
                out["not_priced"] += 1
                logger.info(f"  {gid}: no prop rows returned ({cost} credits)")
                continue
            n = _insert_prop_odds(conn, rows)
            conn.commit()                        # per game: one failure cannot unwrite the rest
            out["bought"] += 1
            out["prop_rows"] += n
            logger.info(f"  {gid}: close snapshot, {n} rows, {len(g['markets'])} market(s), "
                        f"{len({r['bookmaker'] for r in rows})} books, {cost} credit(s)")
        logger.success(f"NBA prop close: {out}")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="say what is due; buy nothing")
    a = ap.parse_args()
    print(run_nba_prop_close_ingestor(dry_run=a.dry_run))

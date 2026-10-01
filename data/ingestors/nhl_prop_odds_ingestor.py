"""Live NHL player-prop prices: TWO pre-game snapshots a game, and no more.

WHY. The only NHL results that held over three priced seasons are props
(docs/nhl_market_lab.md: blocked-shot unders, saves and shots on goal at the
best book), and `player_prop_odds` held no NHL row for 2026-27, so nothing
could be tracked forward. mike, 2026-10-01: collect them, an opening and a
closing price.

WHAT IT BUYS. For every NHL game dated today (ET), the six markets the
history purchase bought (config.PROP_MARKETS_NHL), at the ten fetched books:

  * the OPEN  -- the first refresh pass that finds the game priced;
  * the CLOSE -- the first pass inside the last NHL_PROP_CLOSE_WINDOW_MIN
                 minutes before puck drop.

THE GATE IS THE POINT OF THIS FILE. The refresh pass runs hourly and then
every ten minutes through the evening; a collector that fetched on every pass
would buy ~20 snapshots a game. `due()` answers from what is already stored,
so a pass with nothing to buy makes one free event-list call and one query.
Both snapshots are filed as `snapshot_type = 'open'`, the pre-game series
every other sport's prop history uses and every reader already bounds on
`snapshot_at <= commence_time`; the open and the close are the first and last
rows of that series, which is how scripts/nhl_prop_lab_priced.py reads them.

COST IS MEASURED, NOT ASSUMED: every response's `x-requests-last` is summed
and returned, and the run stops at NHL_PROP_MAX_CREDITS_PER_RUN.

    python -m data.ingestors.nhl_prop_odds_ingestor            # buy what is due
    python -m data.ingestors.nhl_prop_odds_ingestor --dry-run  # say what is due, spend nothing
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
    NHL_PROP_CLOSE_WINDOW_MIN,
    NHL_PROP_MAX_CREDITS_PER_RUN,
    ODDS_API_BASE,
    ODDS_API_BOOKMAKERS_PARAM,
    ODDS_API_KEY,
    ODDS_API_REGIONS,
    PROP_MARKETS_NHL,
)
from data.db import DBConnection, get_connection
from data.ingestors.odds_ingestor import SPORT_KEYS, _build_game_id, _normalize_team
from data.ingestors.odds_quota import persist_quota, record_quota_headers
from data.ingestors.prop_odds_ingestor import (
    REQUEST_SLEEP,
    _existing_game_ids,
    _insert_prop_odds,
    _parse_prop_markets,
)

ET = ZoneInfo("America/New_York")
SPORT_KEY = SPORT_KEYS["NHL"]
SNAPSHOT_TYPE = "open"
YESNO_MARKET = "player_goal_scorer_anytime"


def _utc(v) -> datetime:
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)


def due(start: datetime, now: datetime, stored: list[datetime],
        window_min: int = NHL_PROP_CLOSE_WINDOW_MIN) -> str | None:
    """Which snapshot, if any, this pass owes one game: 'open', 'close' or None.

    `stored` is every pre-game snapshot time already held for the game. Nothing
    is owed once the puck has dropped, and a game first priced inside the
    closing window gets ONE snapshot, not two back to back.
    """
    if now >= start:
        return None
    pre = [s for s in stored if s <= start]
    if not pre:
        return "open"
    window_opens = start - timedelta(minutes=window_min)
    if now >= window_opens and max(pre) < window_opens:
        return "close"
    return None


def _events(today_et: str) -> tuple[list[dict], int]:
    """Today's NHL events. The event list is free on this feed; the cost is
    read off the response rather than taken on trust."""
    resp = requests.get(f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events",
                        params={"apiKey": ODDS_API_KEY, "dateFormat": "iso"}, timeout=15)
    record_quota_headers(resp)
    cost = int(float(resp.headers.get("x-requests-last") or 0))
    if resp.status_code != 200:
        logger.warning(f"NHL prop odds: event list HTTP {resp.status_code}: {resp.text[:160]}")
        return [], cost
    out = []
    for ev in resp.json():
        try:
            start = _utc(ev["commence_time"])
        except (KeyError, ValueError):
            continue
        if start.astimezone(ET).strftime("%Y-%m-%d") == today_et:
            out.append({"id": ev["id"], "home": ev.get("home_team", ""),
                        "away": ev.get("away_team", ""), "start": start})
    return out, cost


def _stored_snapshots(conn: DBConnection, game_ids: list[str]) -> dict[str, list[datetime]]:
    """Snapshot times already held, per game. Asked BY GAME ID: the table is
    indexed on it and is far too large for anything else."""
    out: dict[str, list[datetime]] = {g: [] for g in game_ids}
    if not game_ids:
        return out
    rows = conn.execute(
        "SELECT DISTINCT game_id, snapshot_at FROM player_prop_odds "
        "WHERE game_id = ANY(%s) AND market = ANY(%s) AND snapshot_type = %s",
        (game_ids, list(PROP_MARKETS_NHL), SNAPSHOT_TYPE)).fetchall()
    for gid, snap in rows:
        try:
            out[gid].append(_utc(snap))
        except ValueError:
            continue
    return out


def _event_props(event_id: str) -> tuple[list[tuple[str, list[dict]]], int]:
    """One paid call: every requested market at every fetched book. Returns the
    (book, markets) pairs and the credits the feed billed for it."""
    resp = requests.get(
        f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{event_id}/odds",
        params={"apiKey": ODDS_API_KEY, "regions": ODDS_API_REGIONS,
                "markets": ",".join(PROP_MARKETS_NHL), "bookmakers": ODDS_API_BOOKMAKERS_PARAM,
                "oddsFormat": "american", "includeLinks": "true", "includeSids": "true"},
        timeout=20)
    record_quota_headers(resp)
    cost = int(float(resp.headers.get("x-requests-last") or 0))
    if resp.status_code != 200:
        logger.warning(f"NHL prop odds: event {event_id} HTTP {resp.status_code}: {resp.text[:160]}")
        return [], cost
    books = [(b.get("key"), b.get("markets", [])) for b in resp.json().get("bookmakers", [])
             if b.get("key") in LINE_SHOP_BOOKMAKERS]
    return books, cost


def run_nhl_prop_odds_ingestor(now: datetime | None = None, dry_run: bool = False) -> dict:
    """Buy whichever of today's opening and closing snapshots are due."""
    now = now or datetime.now(timezone.utc)
    today_et = now.astimezone(ET).strftime("%Y-%m-%d")
    out = {"date": today_et, "events": 0, "open": 0, "close": 0, "prop_rows": 0,
           "credits": 0, "unknown_games": 0, "not_priced": 0}
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY not set")
    conn = get_connection()
    try:
        events, cost = _events(today_et)
        out["credits"] += cost
        out["events"] = len(events)
        if not events:
            return out
        for ev in events:
            ev["game_id"] = _build_game_id("NHL", today_et, _normalize_team(ev["away"], "NHL"),
                                           _normalize_team(ev["home"], "NHL"))
        known = _existing_game_ids(conn, [e["game_id"] for e in events])
        stored = _stored_snapshots(conn, sorted(known))
        snapshot_at = now.isoformat()
        for ev in events:
            gid = ev["game_id"]
            if gid not in known:
                # No `games` row: the prices cannot be stored (FK), so do not buy them.
                logger.warning(f"NHL prop odds: {gid} has no games row ({ev['away']} @ {ev['home']})")
                out["unknown_games"] += 1
                continue
            which = due(ev["start"], now, stored.get(gid, []))
            if which is None:
                continue
            if dry_run:
                logger.info(f"  {gid}: {which} snapshot due (dry run, nothing bought)")
                out[which] += 1
                continue
            if out["credits"] >= NHL_PROP_MAX_CREDITS_PER_RUN:
                logger.warning(f"NHL prop odds: {out['credits']} credits this run, at the "
                               f"{NHL_PROP_MAX_CREDITS_PER_RUN} ceiling; stopping")
                break
            books, cost = _event_props(ev["id"])
            out["credits"] += cost
            time.sleep(REQUEST_SLEEP)
            rows: list[dict] = []
            for book, markets in books:
                for m in markets:
                    if m.get("key") == YESNO_MARKET:     # Yes/No, no number: "to score" IS over 0.5
                        for o in m.get("outcomes", []):
                            o.setdefault("point", 0.5)
                rows += _parse_prop_markets(markets, gid, today_et, SNAPSHOT_TYPE, snapshot_at,
                                            allowed_markets=set(PROP_MARKETS_NHL), bookmaker=book)
            if not rows:
                out["not_priced"] += 1
                logger.info(f"  {gid}: no prop rows returned ({cost} credits) — not priced yet")
                continue
            n = _insert_prop_odds(conn, rows)
            conn.commit()                                # per game: one failure cannot unwrite the rest
            out[which] += 1
            out["prop_rows"] += n
            logger.info(f"  {gid}: {which} snapshot, {n} rows, "
                        f"{len({r['market'] for r in rows})} markets, "
                        f"{len({r['bookmaker'] for r in rows})} books, {cost} credits")
        logger.success(f"NHL prop odds: {out}")
        return out
    finally:
        try:
            persist_quota(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="say what is due; buy nothing")
    a = ap.parse_args()
    print(run_nhl_prop_odds_ingestor(dry_run=a.dry_run))

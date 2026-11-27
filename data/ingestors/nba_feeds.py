"""Public NBA feeds that keep no history, saved change by change in Supabase.

WHY (mike, 2026-11-27: "1) yes 2) yes" to building the collectors; record:
docs/nba_data_sources_and_handle_2026_11.md, section F). Each feed below
overwrites itself: the league's lineup file loses its morning Expected fives
once a game is confirmed, a news feed rolls off after 30 days, a projection is
replaced each hour. No archive of any of them exists, so what is not read today
cannot be had later.

HOW IT STORES. One log for every feed, written only when something changed:

  nba_feed_fetches   one row per read: which feed, from where, the HTTP status,
                     how many items it held and how many of them were new or
                     changed. A feed that stops answering shows here.
  nba_feed_changes   one row per (feed, item, our read time) whenever that
                     item's state differs from the state we last stored for it.
                     A state that goes A -> B -> A is three rows.
  nba_feed_latest    the state hash we last stored per item: what the next read
                     is compared with. A cache of nba_feed_changes, maintained
                     by the writer (a "newest row per key" view over a growing
                     log is the shape .claude/rules/data-integrity.md rules out).

The key is OUR read time. The feeds restamp their own times (the lineup file
rewrites every row's stamp about every 15 minutes with nothing changed), so a
feed's stamp is kept in the state for reference and left out of the comparison:
every key of a state that starts with "_" is stored and not compared.

An item that leaves a feed that lists everything (a starter dropped from an
Expected five, a pulled line) is written once as {"gone": true}.

    python -m data.ingestors.nba_feeds --once                    # every feed, one read
    python -m data.ingestors.nba_feeds --once --feeds nba_lineups
    python -m data.ingestors.nba_feeds --loop --until 2026-12-31T00:00:00
    python -m data.ingestors.nba_feeds --once --measure state.json   # no database
    python -m data.ingestors.nba_feeds --backfill-news               # every page, once
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

ET = ZoneInfo("America/New_York")
UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
GONE = {"gone": True}
LOOP_PORT = 47241          # one loop a machine: a second one cannot bind it

FETCHES = "nba_feed_fetches"
FETCH_COLS = ("fetch_id", "feed", "origin", "fetched_at", "http_status", "bytes", "items",
              "changed", "error")
FETCHES_DDL = """
CREATE TABLE IF NOT EXISTS nba_feed_fetches (
    fetch_id     BIGSERIAL PRIMARY KEY,
    feed         TEXT NOT NULL,
    origin       TEXT NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL,
    http_status  INTEGER,
    bytes        INTEGER,
    items        INTEGER,
    changed      INTEGER,
    error        TEXT
)
"""
FETCHES_INDEX = "idx_nba_feed_fetches_feed_time"
FETCHES_INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {FETCHES_INDEX} ON {FETCHES} (feed, fetched_at)"

CHANGES = "nba_feed_changes"
CHANGE_COLS = ("feed", "item_key", "seen_at", "state_hash", "state", "origin")
CHANGES_DDL = """
CREATE TABLE IF NOT EXISTS nba_feed_changes (
    feed        TEXT NOT NULL,
    item_key    TEXT NOT NULL,
    seen_at     TIMESTAMPTZ NOT NULL,
    state_hash  TEXT NOT NULL,
    state       JSONB NOT NULL,
    origin      TEXT NOT NULL,
    PRIMARY KEY (feed, item_key, seen_at)
)
"""
CHANGES_INDEX = "idx_nba_feed_changes_feed_time"
CHANGES_INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {CHANGES_INDEX} ON {CHANGES} (feed, seen_at)"

LATEST = "nba_feed_latest"
LATEST_COLS = ("feed", "item_key", "state_hash", "seen_at", "expires_at")
LATEST_DDL = """
CREATE TABLE IF NOT EXISTS nba_feed_latest (
    feed        TEXT NOT NULL,
    item_key    TEXT NOT NULL,
    state_hash  TEXT NOT NULL,
    seen_at     TIMESTAMPTZ NOT NULL,
    expires_at  TIMESTAMPTZ,
    PRIMARY KEY (feed, item_key)
)
"""
LATEST_INDEX = "idx_nba_feed_latest_feed_expires"
LATEST_INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {LATEST_INDEX} ON {LATEST} (feed, expires_at)"


def ensure_tables(conn) -> None:
    changed = False
    for table, cols, ddl, index, index_ddl in (
            (FETCHES, FETCH_COLS, FETCHES_DDL, FETCHES_INDEX, FETCHES_INDEX_DDL),
            (CHANGES, CHANGE_COLS, CHANGES_DDL, CHANGES_INDEX, CHANGES_INDEX_DDL),
            (LATEST, LATEST_COLS, LATEST_DDL, LATEST_INDEX, LATEST_INDEX_DDL)):
        if not schema_is_current(conn, table, columns=cols, indexes=(index,), rls=True,
                                 revoked_from=API_ROLES):
            conn.execute(ddl)
            conn.execute(index_ddl)
            lock_down(conn, table)
            changed = True
    if changed:
        conn.commit()


# ---------------------------------------------------------------- comparing

def state_hash(state: dict) -> str:
    """The hash of what is compared: every key not starting with "_"."""
    kept = {k: v for k, v in state.items() if not k.startswith("_")}
    blob = json.dumps(kept, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


GONE_HASH = state_hash(GONE)


def diff(latest: dict[str, str], items: dict[str, dict], lists_everything: bool) -> list[tuple]:
    """(item_key, state, hash) for each item that is new or whose compared state
    differs from `latest` (item_key -> the hash last stored). With
    `lists_everything`, an item in `latest` that the read no longer holds is
    returned once as GONE."""
    out = []
    for key, state in items.items():
        h = state_hash(state)
        if latest.get(key) != h:
            out.append((key, state, h))
    if lists_everything:
        for key, h in latest.items():
            if key not in items and h != GONE_HASH:
                out.append((key, dict(GONE), GONE_HASH))
    return out


# -------------------------------------------------------------------- feeds

@dataclass
class Read:
    status: int | None
    nbytes: int
    items: dict[str, dict]
    expires_at: datetime | None = None
    error: str | None = None


def _get(url: str, timeout: int = 60, **params) -> requests.Response:
    return requests.get(url, headers=UA, params=params or None, timeout=timeout)


def et_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(ET)


def slate_dates(now: datetime | None = None) -> list[date]:
    """Today in ET, and yesterday too before 3am ET: a 10pm ET tip is still
    being played, under yesterday's date, after midnight."""
    n = et_now(now)
    return [n.date() - timedelta(days=1), n.date()] if n.hour < 3 else [n.date()]


# -- the league's daily lineup file

LINEUPS_URL = "https://stats.nba.com/js/data/leaders/00_daily_lineups_{d}.json"


def parse_lineups(payload: dict) -> dict[str, dict]:
    """One item per listed player, and one per team holding its Expected five
    and its Confirmed starters as lists, so a player DROPPED from a five shows
    as a change (the per-player item would only show as gone)."""
    items: dict[str, dict] = {}
    for g in payload.get("games") or []:
        gid = g.get("gameId")
        for side in ("homeTeam", "awayTeam"):
            t = g.get(side) or {}
            abbr = t.get("teamAbbreviation")
            expected, confirmed, inactive = [], [], []
            for p in t.get("players") or []:
                pid = p.get("personId")
                items[f"{gid}:{pid}"] = {
                    "game": gid, "team": abbr, "side": side[:4], "player": p.get("playerName"),
                    "lineup": p.get("lineupStatus"), "roster": p.get("rosterStatus"),
                    "pos": p.get("position") or "", "_feed_stamp": p.get("timestamp"),
                    "_game_status": g.get("gameStatus"),
                }
                if p.get("lineupStatus") == "Expected":
                    expected.append([pid, p.get("position") or ""])
                elif p.get("rosterStatus") == "Inactive":
                    inactive.append(pid)
                elif p.get("position"):
                    confirmed.append([pid, p.get("position")])
            items[f"{gid}:{abbr}:fives"] = {
                "game": gid, "team": abbr, "side": side[:4],
                "expected": sorted(expected), "confirmed_starters": sorted(confirmed),
                "inactive": sorted(inactive), "_tip_text": g.get("gameStatusText"),
                "_game_status": g.get("gameStatus"),
            }
    return items


def read_lineups(now: datetime | None = None) -> Read:
    items: dict[str, dict] = {}
    status, nbytes = None, 0
    for d in slate_dates(now):
        r = _get(LINEUPS_URL.format(d=d.strftime("%Y%m%d")))
        status, nbytes = r.status_code, nbytes + len(r.content)
        if r.status_code != 200 or "json" not in r.headers.get("content-type", "json"):
            return Read(r.status_code, nbytes, {}, error=f"{d}: HTTP {r.status_code}")
        items.update(parse_lineups(r.json()))
    return Read(status, nbytes, items, expires_at=et_now(now) + timedelta(days=2))


# -- referee crews, as the league posts them (about 9:12am ET)

REFEREES_URL = "https://official.nba.com/wp-json/api/v1/get-game-officials"


def parse_referees(payload: dict, leagues=("nba", "gl")) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for lg in leagues:
        block = payload.get(lg) or {}
        for row in (block.get("Table") or {}).get("rows") or []:
            crew = [[row.get(f"official{i}"), row.get(f"official{i}_code")] for i in (1, 2, 3, 4)
                    if row.get(f"official{i}")]
            items[f"{lg}:{row.get('game_id')}"] = {
                "league": lg, "game": row.get("game_id"), "date": row.get("game_date"),
                "code": row.get("game_code"), "home": row.get("home_team_abbr"),
                "away": row.get("away_team_abbr"), "crew": crew,
            }
        replay = sorted(str(r.get("replaycenter_official")) for r in
                        (block.get("Table1") or {}).get("rows") or [])
        if replay:
            day = (block["Table1"]["rows"][0] or {}).get("game_date")
            items[f"{lg}:replay:{day}"] = {"league": lg, "date": day, "replay_center": replay}
    return items


def read_referees(now: datetime | None = None) -> Read:
    r = _get(REFEREES_URL, date=et_now(now).strftime("%Y-%m-%d"))
    if r.status_code != 200:
        return Read(r.status_code, len(r.content), {}, error=f"HTTP {r.status_code}")
    return Read(200, len(r.content), parse_referees(r.json()),
                expires_at=et_now(now) + timedelta(days=2))


# -- Underdog's player news (RotoWire's text, stamped to the second, 30 days kept)

NEWS_URL = "https://api.underdogfantasy.com/v1/news_items"
NEWS_MAX_PAGES = 12        # a normal pass stops at the first page with nothing new


def parse_news(payload: dict) -> dict[str, dict]:
    items = {}
    for n in payload.get("news_items") or []:
        p = n.get("player") or {}
        items[str(n.get("id"))] = {
            "title": n.get("title"), "content": n.get("content"),
            "created_at": n.get("created_at"), "updated_at": n.get("updated_at"),
            "source": n.get("source"), "player_id": p.get("id"),
            "player": " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x),
            "team_id": p.get("team_id"), "position": p.get("position_name"),
        }
    return items


def read_news(now: datetime | None = None, known: set[str] | None = None,
              max_pages: int = NEWS_MAX_PAGES) -> Read:
    """Newest page first; goes on to the next page only while every item on the
    page is one we do not hold (`known`), so a gap after an outage is filled and
    a normal pass costs one request."""
    items: dict[str, dict] = {}
    nbytes, page = 0, 1
    while page and page <= max_pages:
        r = _get(NEWS_URL, sport_id="NBA", page=page)
        nbytes += len(r.content)
        if r.status_code != 200:
            return Read(r.status_code, nbytes, items, error=f"page {page}: HTTP {r.status_code}")
        body = r.json()
        got = parse_news(body)
        items.update(got)
        if known is None or any(k in known for k in got):
            break
        page = (body.get("meta") or {}).get("next")
        time.sleep(0.6)
    return Read(200, nbytes, items)


# -- RotoWire's per-game projection, as Sleeper serves it (rebuilt each hour)

SLEEPER_PROJ_URL = "https://api.sleeper.app/projections/nba/{season}/{week}"
SLEEPER_SEASON = 2026
SLEEPER_WEEK1_MONDAY = date(2026, 10, 19)   # week 1 = 2026-10-20..25, week 6 = 11-23..29 (measured)


def sleeper_week(d: date) -> int:
    return (d - SLEEPER_WEEK1_MONDAY).days // 7 + 1


def parse_sleeper_projections(payload: list, from_date: date) -> dict[str, dict]:
    """Games on or after `from_date` only: a played game's row no longer moves."""
    items = {}
    for x in payload or []:
        d = x.get("date")
        if not d or d < from_date.isoformat():
            continue
        p = x.get("player") or {}
        items[f"{d}:{x.get('player_id')}"] = {
            "date": d, "team": x.get("team"), "opp": x.get("opponent"),
            "player": " ".join(v for v in (p.get("first_name"), p.get("last_name")) if v),
            "stats": x.get("stats") or {}, "injury_status": p.get("injury_status"),
            "injury_body_part": p.get("injury_body_part"), "injury_notes": p.get("injury_notes"),
            "company": x.get("company"), "_updated_at": x.get("updated_at"),
            "_news_updated": p.get("news_updated"),
        }
    return items


def read_sleeper_projections(now: datetime | None = None) -> Read:
    today = et_now(now).date()
    weeks = sorted({sleeper_week(today), sleeper_week(today + timedelta(days=1))})
    items: dict[str, dict] = {}
    nbytes = 0
    for w in weeks:
        r = _get(SLEEPER_PROJ_URL.format(season=SLEEPER_SEASON, week=w), season_type="regular")
        nbytes += len(r.content)
        if r.status_code != 200:
            return Read(r.status_code, nbytes, {}, error=f"week {w}: HTTP {r.status_code}")
        items.update(parse_sleeper_projections(r.json(), today))
    return Read(200, nbytes, items, expires_at=et_now(now) + timedelta(days=9))


@dataclass
class Feed:
    name: str
    read: Callable[..., Read]
    every_sec: Callable[[datetime], int]
    lists_everything: bool = False     # a missing item means it left the feed
    wants_known: bool = False          # read() takes known=<keys already held>


def _lineups_every(now: datetime) -> int:
    return 60 if 8 <= et_now(now).hour or et_now(now).hour < 2 else 900


def _referees_every(now: datetime) -> int:
    n = et_now(now)
    return 60 if (n.hour == 8 and n.minute >= 30) or n.hour == 9 else 1800


FEEDS: dict[str, Feed] = {f.name: f for f in (
    Feed("nba_lineups", read_lineups, _lineups_every, lists_everything=True),
    Feed("nba_referees", read_referees, _referees_every),
    Feed("underdog_news", read_news, lambda now: 120, wants_known=True),
    Feed("sleeper_projections", read_sleeper_projections, lambda now: 600),
)}


# ------------------------------------------------------------------ storing

def _rows(result) -> list[tuple]:
    return [tuple(r.values()) if isinstance(r, dict) else tuple(r) for r in result.fetchall()]


def load_latest(conn, feed: str) -> dict[str, str]:
    rows = _rows(conn.execute(
        f"SELECT item_key, state_hash FROM {LATEST} WHERE feed = %s "
        "AND (expires_at IS NULL OR expires_at > NOW())", (feed,)))
    return {r[0]: r[1] for r in rows}


_CHANGE_INSERT = (f"INSERT INTO {CHANGES} (feed, item_key, seen_at, state_hash, state, origin) "
                  "VALUES (%s, %s, %s, %s, %s::jsonb, %s) ON CONFLICT DO NOTHING")
_LATEST_UPSERT = (f"INSERT INTO {LATEST} (feed, item_key, state_hash, seen_at, expires_at) "
                  "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (feed, item_key) DO UPDATE SET "
                  "state_hash = EXCLUDED.state_hash, seen_at = EXCLUDED.seen_at, "
                  "expires_at = EXCLUDED.expires_at")
_FETCH_INSERT = (f"INSERT INTO {FETCHES} (feed, origin, fetched_at, http_status, bytes, items, "
                 "changed, error) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")


def store(conn, feed: Feed, origin: str, seen_at: datetime, read: Read,
          latest: dict[str, str]) -> int:
    """Write what changed, then the ledger row, in one transaction. A read that
    failed writes its ledger row only: an error is never taken for an empty feed."""
    changes = [] if read.error else diff(latest, read.items, feed.lists_everything)
    stamp = seen_at.isoformat()
    exp = read.expires_at.isoformat() if read.expires_at else None
    if changes:
        conn.executemany(_CHANGE_INSERT, [
            (feed.name, k, stamp, h, json.dumps(s, ensure_ascii=False), origin)
            for k, s, h in changes])
        conn.executemany(_LATEST_UPSERT, [(feed.name, k, h, stamp, exp) for k, s, h in changes])
    conn.execute(_FETCH_INSERT, (feed.name, origin, stamp, read.status, read.nbytes,
                                 len(read.items), len(changes), read.error))
    conn.commit()
    return len(changes)


def one_read(conn, feed: Feed, origin: str, now: datetime | None = None,
             measure: dict | None = None) -> dict:
    """Read one feed and store what changed. With `measure` (a dict kept by the
    caller in place of the database) nothing is written anywhere."""
    seen_at = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    latest = measure.setdefault(feed.name, {}) if measure is not None else load_latest(conn, feed.name)
    try:
        read = feed.read(now, known=set(latest)) if feed.wants_known else feed.read(now)
    except Exception as exc:                                    # noqa: BLE001
        read = Read(None, 0, {}, error=f"{type(exc).__name__}: {str(exc)[:300]}")
    if measure is not None:
        changes = [] if read.error else diff(latest, read.items, feed.lists_everything)
        for k, _s, h in changes:
            latest[k] = h
        n = len(changes)
    else:
        n = store(conn, feed, origin, seen_at, read, latest)
    return {"feed": feed.name, "seen_at": seen_at.isoformat(), "status": read.status,
            "bytes": read.nbytes, "items": len(read.items), "changed": n, "error": read.error}


def backfill_news(conn, origin: str, max_pages: int = 400) -> dict:
    """Every page the news feed still serves (30 days), oldest reachable first
    stored: run once, before the oldest items roll off."""
    feed = FEEDS["underdog_news"]
    seen_at = datetime.now(timezone.utc).replace(microsecond=0)
    read = read_news(known=set(), max_pages=max_pages)
    n = store(conn, feed, origin, seen_at, read, load_latest(conn, feed.name))
    return {"feed": feed.name, "items": len(read.items), "changed": n, "error": read.error}


def default_origin() -> str:
    return "worker" if os.environ.get("RAILWAY_ENVIRONMENT") else "pc"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Public NBA feeds -> Supabase, change by change")
    ap.add_argument("--feeds", help="comma-separated; default every feed")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--until", help="with --loop: stop at this UTC time")
    ap.add_argument("--origin", default=default_origin())
    ap.add_argument("--measure", help="keep state in this JSON file; write no database")
    ap.add_argument("--backfill-news", action="store_true")
    a = ap.parse_args(argv)
    names = a.feeds.split(",") if a.feeds else list(FEEDS)
    unknown = [n for n in names if n not in FEEDS]
    if unknown:
        ap.error(f"unknown feed(s): {unknown}; known: {sorted(FEEDS)}")
    feeds = [FEEDS[n] for n in names]

    measure = None
    if a.measure:
        measure = json.loads(open(a.measure, encoding="utf-8").read()) if os.path.exists(a.measure) else {}
    conn = None
    if measure is None:
        from data.db import get_connection
        conn = get_connection()
        ensure_tables(conn)
    guard = None
    try:
        if a.backfill_news:
            print(json.dumps(backfill_news(conn, a.origin)))
            return 0
        if not a.loop:
            for f in feeds:
                print(json.dumps(one_read(conn, f, a.origin, measure=measure)))
            return 0
        guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            guard.bind(("127.0.0.1", LOOP_PORT))
        except OSError:
            print(json.dumps({"already_running": LOOP_PORT}))
            return 0
        until = datetime.fromisoformat(a.until).replace(tzinfo=timezone.utc) if a.until else None
        due = {f.name: 0.0 for f in feeds}
        while until is None or datetime.now(timezone.utc) < until:
            for f in feeds:
                if time.time() < due[f.name]:
                    continue
                now = datetime.now(timezone.utc)
                try:
                    res = one_read(conn, f, a.origin, now=now, measure=measure)
                    if res["changed"] or res["error"]:
                        logger.info(json.dumps(res))
                except Exception as exc:                        # noqa: BLE001
                    logger.warning(f"{f.name}: {exc}")
                    try:
                        conn.rollback()
                    except Exception:                           # noqa: BLE001
                        pass
                due[f.name] = time.time() + f.every_sec(now)
            time.sleep(5)
        return 0
    finally:
        if measure is not None and a.measure:
            open(a.measure, "w", encoding="utf-8").write(json.dumps(measure))
        if conn is not None:
            conn.close()
        if guard is not None:
            guard.close()


if __name__ == "__main__":
    raise SystemExit(main())

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
    python -m data.ingestors.nba_feeds --tick --skip unabated_props  # the worker, every minute
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


# -- Pinnacle's own NBA board: every pre-game market with its stake limit

PINNACLE_BASE = "https://guest.api.arcadia.pinnacle.com/0.1/leagues/487"


def parse_pinnacle(matchups: list, markets: list, now: datetime) -> dict[str, dict]:
    """Pre-game markets only (an in-play price moves every few seconds and is
    not what this is for). Player props are Pinnacle's "special" matchups: the
    player and stat are in the special's description, the game in its parent."""
    info: dict[int, dict] = {}
    for m in matchups or []:
        parent = m.get("parent") or {}
        start = parent.get("startTime") or m.get("startTime")
        live = bool(m.get("isLive") or parent.get("isLive"))
        teams = {p.get("alignment"): p.get("name")
                 for p in (parent.get("participants") or m.get("participants") or [])}
        sp = m.get("special") or {}
        info[m.get("id")] = {
            "start": start, "live": live, "kind": m.get("type"),
            "home": teams.get("home"), "away": teams.get("away"),
            "what": sp.get("description"), "category": sp.get("category"),
            "names": {p.get("id"): p.get("name") for p in m.get("participants") or []},
        }
    items: dict[str, dict] = {}
    for x in markets or []:
        mi = info.get(x.get("matchupId"))
        if not mi or mi["live"]:
            continue
        try:
            if mi["start"] and datetime.fromisoformat(mi["start"].replace("Z", "+00:00")) <= now:
                continue
        except ValueError:
            pass
        prices = [{"side": pr.get("designation") or mi["names"].get(pr.get("participantId")),
                   "points": pr.get("points"), "price": pr.get("price")}
                  for pr in x.get("prices") or []]
        limit = next((li.get("amount") for li in x.get("limits") or []
                      if li.get("type") == "maxRiskStake"), None)
        items[f"{x.get('matchupId')}:{x.get('key')}"] = {
            "type": x.get("type"), "period": x.get("period"), "prices": prices, "limit": limit,
            "kind": mi["kind"], "what": mi["what"], "category": mi["category"],
            "home": mi["home"], "away": mi["away"], "start": mi["start"],
        }
    return items


def read_pinnacle(now: datetime | None = None) -> Read:
    now = now or datetime.now(timezone.utc)
    mu = _get(f"{PINNACLE_BASE}/matchups")
    if mu.status_code != 200:
        return Read(mu.status_code, len(mu.content), {}, error=f"matchups: HTTP {mu.status_code}")
    mk = _get(f"{PINNACLE_BASE}/markets/straight")
    nbytes = len(mu.content) + len(mk.content)
    if mk.status_code != 200:
        return Read(mk.status_code, nbytes, {}, error=f"markets: HTTP {mk.status_code}")
    return Read(200, nbytes, parse_pinnacle(mu.json(), mk.json(), now),
                expires_at=now + timedelta(days=3))


# -- Unabated's public prop file: each source's line, price and OPENING line and price

UNABATED_URL = "https://content.unabated.com/markets/v2/league/3/propodds.json"


def parse_unabated(payload: dict, now: datetime) -> dict[str, dict]:
    """One item per (event, player, bet type, side, source). Sources and
    players are named from the file's own tables. Games already started are
    left out. Alternate ladders are not stored (14,871 of 45,087 items carried
    one on 2026-11-27; the main line and the opener are what this is for)."""
    sources = {f"ms{m.get('id')}": m.get("name") for m in payload.get("marketSources") or []}
    people = payload.get("people") or {}
    items: dict[str, dict] = {}
    for group, records in (payload.get("odds") or {}).items():
        if "pregame" not in group:
            continue
        for o in records or []:
            start = o.get("eventStart")
            try:
                if start and datetime.fromisoformat(start).replace(tzinfo=timezone.utc) <= now:
                    continue
            except ValueError:
                pass
            who = people.get(str(o.get("personId"))) or {}
            name = " ".join(v for v in (who.get("firstName"), who.get("lastName")) if v)
            for side_key, by_source in (o.get("sides") or {}).items():
                side = side_key.split(":")[0]
                for ms, v in (by_source or {}).items():
                    items[f"{o.get('eventId')}:{o.get('personId')}:{o.get('betTypeId')}:{side}:{ms}"] = {
                        "event": o.get("eventId"), "event_name": o.get("eventName"), "start": start,
                        "player": name, "bet_type": o.get("betTypeId"), "side": side,
                        "source": sources.get(ms, ms), "points": v.get("points"),
                        "price": v.get("price"), "opener_points": v.get("openerPoints"),
                        "opener_price": v.get("openerPrice"), "status": v.get("statusId"),
                        "_modified_on": v.get("modifiedOn"),
                    }
    return items


_unabated_snapshot: dict = {"stamp": None}


def read_unabated(now: datetime | None = None) -> Read:
    now = now or datetime.now(timezone.utc)
    r = _get(UNABATED_URL, timeout=180)
    if r.status_code != 200:
        return Read(r.status_code, len(r.content), {}, error=f"HTTP {r.status_code}")
    body = r.json()
    items = parse_unabated(body, now)
    for it in items.values():
        it["_file_snapshot"] = body.get("snapshotStartedAtUtc")
    return Read(200, len(r.content), items, expires_at=now + timedelta(days=3))


# -- the pick'em boards: each app's line and payout, and how many picked each side

PRIZEPICKS_URL = "https://partner-api.prizepicks.com/projections"
UNDERDOG_LINES_URL = "https://api.underdogfantasy.com/v1/over_under_lines"
SLEEPER_LINES_URL = "https://api.sleeper.app/lines/available"


def parse_prizepicks(payload: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """(lines, popularity). A line's item is its number and type; the pick
    count lives in its own feed so that a count ticking up is not a line row."""
    players = {x.get("id"): x.get("attributes") or {} for x in payload.get("included") or []
               if x.get("type") == "new_player"}
    lines, counts = {}, {}
    for x in payload.get("data") or []:
        a = x.get("attributes") or {}
        if a.get("status") != "pre_game":
            continue
        pid = (((x.get("relationships") or {}).get("new_player") or {}).get("data") or {}).get("id")
        who = players.get(pid) or {}
        lines[str(x.get("id"))] = {
            "player": who.get("display_name") or who.get("name"), "team": who.get("team"),
            "stat": a.get("stat_type"), "line": a.get("line_score"), "odds_type": a.get("odds_type"),
            "start": a.get("start_time"), "promo": bool(a.get("is_promo")),
            "flash_line": a.get("flash_sale_line_score"), "adjusted_odds": a.get("adjusted_odds"),
            "_updated_at": a.get("updated_at"), "_board_time": a.get("board_time"),
        }
        if a.get("trending_count"):
            counts[str(x.get("id"))] = {
                "player": who.get("display_name") or who.get("name"), "stat": a.get("stat_type"),
                "line": a.get("line_score"), "odds_type": a.get("odds_type"),
                "trending_count": a.get("trending_count"),
            }
    return lines, counts


def _prizepicks(now=None) -> tuple[Read, Read]:
    r = _get(PRIZEPICKS_URL, timeout=120, league_id=7, per_page=10000)
    if r.status_code != 200:
        bad = Read(r.status_code, len(r.content), {}, error=f"HTTP {r.status_code}")
        return bad, bad
    lines, counts = parse_prizepicks(r.json())
    exp = (now or datetime.now(timezone.utc)) + timedelta(days=3)
    return Read(200, len(r.content), lines, expires_at=exp), Read(200, len(r.content), counts, expires_at=exp)


def read_prizepicks(now: datetime | None = None) -> Read:
    return _prizepicks(now)[0]


def read_prizepicks_counts(now: datetime | None = None) -> Read:
    return _prizepicks(now)[1]


def parse_underdog_lines(payload: dict) -> dict[str, dict]:
    """NBA lines only (the file holds every sport): a line belongs to an
    appearance, an appearance to a match, and a match names its sport."""
    nba = {g.get("id"): g for g in payload.get("games") or [] if g.get("sport_id") == "NBA"}
    app = {a.get("id"): a for a in payload.get("appearances") or []}
    players = {p.get("id"): p for p in payload.get("players") or []}
    items = {}
    for ln in payload.get("over_under_lines") or []:
        ou = ln.get("over_under") or {}
        st = ou.get("appearance_stat") or {}
        a = app.get(st.get("appearance_id")) or {}
        g = nba.get(a.get("match_id"))
        if not g or ln.get("live_event") or g.get("status") not in (None, "scheduled"):
            continue
        p = players.get(a.get("player_id")) or {}
        items[str(ln.get("id"))] = {
            "player": " ".join(v for v in (p.get("first_name"), p.get("last_name")) if v),
            "game": g.get("abbreviated_title"), "start": g.get("scheduled_at"),
            "stat": st.get("stat"), "line": ln.get("stat_value"), "line_type": ln.get("line_type"),
            "status": ln.get("status"),
            "options": sorted(
                [{"choice": o.get("choice"), "american": o.get("american_price"),
                  "decimal": o.get("decimal_price"), "payout": o.get("payout_multiplier"),
                  "status": o.get("status")} for o in ln.get("options") or []],
                key=lambda o: str(o["choice"])),
            "_updated_at": ln.get("updated_at"),
        }
    return items


def read_underdog_lines(now: datetime | None = None) -> Read:
    r = _get(UNDERDOG_LINES_URL, timeout=180)
    if r.status_code != 200:
        return Read(r.status_code, len(r.content), {}, error=f"HTTP {r.status_code}")
    return Read(200, len(r.content), parse_underdog_lines(r.json()),
                expires_at=(now or datetime.now(timezone.utc)) + timedelta(days=3))


def parse_sleeper_lines(payload: list) -> tuple[dict[str, dict], dict[str, dict]]:
    """(lines, pick counts), pre-game only."""
    lines, counts = {}, {}
    for x in payload or []:
        if x.get("sport") != "nba" or x.get("game_status") != "pre_game":
            continue
        opts = sorted(
            [{"outcome": o.get("outcome"), "value": o.get("outcome_value"),
              "payout": o.get("payout_multiplier"), "status": o.get("status")}
             for o in x.get("options") or []], key=lambda o: str(o["outcome"]))
        value = opts[0]["value"] if opts else None
        key = f"{x.get('game_id')}:{x.get('market_type')}:{x.get('line_type')}"
        if x.get("line_type") != "normal":
            key += f":{value}"
        team = next((o.get("subject_team") for o in x.get("options") or []), None)
        lines[key] = {"subject": x.get("subject_id"), "team": team, "stat": x.get("wager_type"),
                      "line_type": x.get("line_type"), "status": x.get("status"), "options": opts,
                      "_updated_at": x.get("updated_at")}
        c = (x.get("pick_stats") or {}).get("counts")
        if c and c.get("total"):
            counts[key] = {"subject": x.get("subject_id"), "stat": x.get("wager_type"),
                           "value": value, "over": c.get("over"), "under": c.get("under"),
                           "total": c.get("total")}
    return lines, counts


def _sleeper_lines(now=None) -> tuple[Read, Read]:
    r = _get(SLEEPER_LINES_URL + "?sports[]=nba", timeout=120)
    if r.status_code != 200:
        bad = Read(r.status_code, len(r.content), {}, error=f"HTTP {r.status_code}")
        return bad, bad
    lines, counts = parse_sleeper_lines(r.json())
    exp = (now or datetime.now(timezone.utc)) + timedelta(days=3)
    return Read(200, len(r.content), lines, expires_at=exp), Read(200, len(r.content), counts, expires_at=exp)


def read_sleeper_lines(now: datetime | None = None) -> Read:
    return _sleeper_lines(now)[0]


def read_sleeper_counts(now: datetime | None = None) -> Read:
    return _sleeper_lines(now)[1]


# -- BetMGM's bet % and money % per game, as Yahoo Sports serves them

YAHOO_ODDS_URL = "https://graphite.sports.yahoo.com/v1/query/shangrila/gameOdds"
# Yahoo's game id is nba.g.<YYYYMMDD><home team's two digits>; one id a call (two ids in one
# call answer 400, an id with no game answers an empty list: measured 2026-11-27).
YAHOO_TEAM_CODE = {
    "ATL": "01", "BOS": "02", "NOP": "03", "CHI": "04", "CLE": "05", "DAL": "06", "DEN": "07",
    "DET": "08", "GSW": "09", "HOU": "10", "IND": "11", "LAC": "12", "LAL": "13", "MIA": "14",
    "MIL": "15", "MIN": "16", "BKN": "17", "NYK": "18", "ORL": "19", "PHI": "20", "PHX": "21",
    "POR": "22", "SAC": "23", "SAS": "24", "OKC": "25", "UTA": "26", "WAS": "27", "TOR": "28",
    "MEM": "29", "CHA": "30",
}


def parse_yahoo_game(g: dict) -> dict:
    markets = []
    for m in g.get("gameLineSixPack") or []:
        markets.append({
            "type": m.get("type"), "period": m.get("period"), "status": m.get("status"),
            "options": [{"name": o.get("name"), "price": o.get("americanOdds"),
                         "money_pct": o.get("stakePercentage"), "bets_pct": o.get("wagerPercentage"),
                         "won": o.get("isCorrect")} for o in m.get("options") or []],
        })
    return {"game": g.get("gameId"), "status": g.get("status"), "start": g.get("startTime"),
            "home": (g.get("homeTeam") or {}).get("abbreviation"),
            "away": (g.get("awayTeam") or {}).get("abbreviation"),
            "summary": (g.get("gameOddsSummary") or {}).get("pregameOddsDisplay"),
            "markets": sorted(markets, key=lambda m: str(m["type"]))}


def read_yahoo_date(d: date, codes: list[str]) -> tuple[dict[str, dict], int, str | None]:
    items, nbytes = {}, 0
    for code in codes:
        gid = f"nba.g.{d.strftime('%Y%m%d')}{code}"
        r = _get(YAHOO_ODDS_URL, gameIds=gid)
        nbytes += len(r.content)
        if r.status_code != 200:
            return items, nbytes, f"{gid}: HTTP {r.status_code}"
        for g in ((r.json().get("data") or {}).get("games") or []):
            items[g.get("gameId")] = parse_yahoo_game(g)
        time.sleep(1.0)
    return items, nbytes, None


def _home_codes(d: date) -> list[str]:
    """The home teams of a date from the league's lineup file; every team when
    it does not answer or lists nothing (30 calls then, not about 10)."""
    try:
        r = _get(LINEUPS_URL.format(d=d.strftime("%Y%m%d")))
        homes = [(g.get("homeTeam") or {}).get("teamAbbreviation") for g in r.json().get("games") or []]
        codes = [YAHOO_TEAM_CODE[h] for h in homes if h in YAHOO_TEAM_CODE]
        if codes:
            return codes
    except Exception:                                           # noqa: BLE001
        pass
    return sorted(YAHOO_TEAM_CODE.values())


def read_yahoo_splits(now: datetime | None = None) -> Read:
    items: dict[str, dict] = {}
    nbytes = 0
    for d in slate_dates(now):
        got, n, err = read_yahoo_date(d, _home_codes(d))
        nbytes += n
        if err:
            return Read(None, nbytes, {}, error=err)
        items.update(got)
    return Read(200, nbytes, items, expires_at=et_now(now) + timedelta(days=3))


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
    Feed("pinnacle_nba", read_pinnacle, lambda now: 300, lists_everything=True),
    Feed("unabated_props", read_unabated, lambda now: 900),
    Feed("prizepicks_lines", read_prizepicks, lambda now: 600, lists_everything=True),
    Feed("prizepicks_counts", read_prizepicks_counts, lambda now: 3600),
    Feed("underdog_lines", read_underdog_lines, lambda now: 900, lists_everything=True),
    Feed("sleeper_lines", read_sleeper_lines, lambda now: 600, lists_everything=True),
    Feed("sleeper_counts", read_sleeper_counts, lambda now: 3600),
    Feed("yahoo_mgm_splits", read_yahoo_splits, lambda now: 600),
)}


# ------------------------------------------------------------------ storing

def _rows(result) -> list[tuple]:
    return [tuple(r.values()) if isinstance(r, dict) else tuple(r) for r in result.fetchall()]


def load_latest(conn, feed: str) -> dict[str, str]:
    rows = _rows(conn.execute(
        f"SELECT item_key, state_hash FROM {LATEST} WHERE feed = %s "
        "AND (expires_at IS NULL OR expires_at > NOW())", (feed,)))
    return {r[0]: r[1] for r in rows}


_CHANGE_HEAD = f"INSERT INTO {CHANGES} (feed, item_key, seen_at, state_hash, state, origin) VALUES "
_CHANGE_ROW = "(%s, %s, %s, %s, %s::jsonb, %s)"
_CHANGE_TAIL = " ON CONFLICT DO NOTHING"
_LATEST_HEAD = f"INSERT INTO {LATEST} (feed, item_key, state_hash, seen_at, expires_at) VALUES "
_LATEST_ROW = "(%s, %s, %s, %s, %s)"
_LATEST_TAIL = (" ON CONFLICT (feed, item_key) DO UPDATE SET state_hash = EXCLUDED.state_hash, "
                "seen_at = EXCLUDED.seen_at, expires_at = EXCLUDED.expires_at")
_FETCH_INSERT = (f"INSERT INTO {FETCHES} (feed, origin, fetched_at, http_status, bytes, items, "
                 "changed, error) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
BATCH = 500


def _insert_many(conn, head: str, row: str, tail: str, rows: list[tuple]) -> None:
    """Multi-row inserts, BATCH rows a statement: a first read of a big board is
    tens of thousands of rows, and one round trip a row would take half an hour."""
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        conn.execute(head + ", ".join([row] * len(chunk)) + tail,
                     tuple(v for r in chunk for v in r))


def store(conn, feed: Feed, origin: str, seen_at: datetime, read: Read,
          latest: dict[str, str]) -> int:
    """Write what changed, then the ledger row, in one transaction. A read that
    failed writes its ledger row only: an error is never taken for an empty feed."""
    changes = [] if read.error else diff(latest, read.items, feed.lists_everything)
    stamp = seen_at.isoformat()
    exp = read.expires_at.isoformat() if read.expires_at else None
    if changes:
        _insert_many(conn, _CHANGE_HEAD, _CHANGE_ROW, _CHANGE_TAIL, [
            (feed.name, k, stamp, h, json.dumps(s, ensure_ascii=False), origin)
            for k, s, h in changes])
        _insert_many(conn, _LATEST_HEAD, _LATEST_ROW, _LATEST_TAIL,
                     [(feed.name, k, h, stamp, exp) for k, s, h in changes])
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


def backfill_yahoo(conn, origin: str, first: date, last: date, pause: float = 1.0) -> dict:
    """Every game Yahoo still fills between two dates (it empties a season's
    games some months after they are played). Stored date by date, so a refusal
    part-way keeps what was read; the result names the date to resume from.
    Yahoo refused the connection after about 650 requests at four a second
    (2026-11-27), so this asks only for each date's home teams, one a second."""
    feed = FEEDS["yahoo_mgm_splits"]
    games = changed = 0
    d = first
    while d <= last:
        try:
            got, nbytes, err = read_yahoo_date(d, _home_codes(d))
        except Exception as exc:                                # noqa: BLE001
            got, nbytes, err = {}, 0, f"{type(exc).__name__}: {str(exc)[:200]}"
        seen_at = datetime.now(timezone.utc).replace(microsecond=0)
        read = Read(None if err else 200, nbytes, got, error=err)
        changed += store(conn, feed, origin, seen_at, read, load_latest(conn, feed.name))
        if err:
            return {"feed": feed.name, "games": games, "changed": changed,
                    "resume_from": d.isoformat(), "error": err}
        games += len(got)
        d += timedelta(days=1)
        time.sleep(pause)
    return {"feed": feed.name, "games": games, "changed": changed, "error": None}


def last_reads(conn) -> dict[str, datetime]:
    """When each feed was last read, by anyone (this machine or the worker)."""
    rows = _rows(conn.execute(
        f"SELECT feed, max(fetched_at) FROM {FETCHES} "
        "WHERE fetched_at > NOW() - INTERVAL '2 days' GROUP BY feed"))
    return {r[0]: r[1] for r in rows}


def due_feeds(feeds: list[Feed], last: dict[str, datetime], now: datetime) -> list[Feed]:
    """The feeds whose own interval has passed since their last read (5 seconds
    of slack, so a one-minute feed is not skipped by a tick that starts early)."""
    out = []
    for f in feeds:
        at = last.get(f.name)
        if at is None or (now - at).total_seconds() >= f.every_sec(now) - 5:
            out.append(f)
    return out


def tick(conn, origin: str, feeds: list[Feed], now: datetime | None = None) -> list[dict]:
    """One scheduled pass: read each feed that is due by the ledger. The worker
    calls this every minute; it keeps no state of its own between calls, and a
    feed the PC's loop has just read is not read again."""
    now = now or datetime.now(timezone.utc)
    return [one_read(conn, f, origin, now=datetime.now(timezone.utc))
            for f in due_feeds(feeds, last_reads(conn), now)]


def default_origin() -> str:
    return "worker" if os.environ.get("RAILWAY_ENVIRONMENT") else "pc"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Public NBA feeds -> Supabase, change by change")
    ap.add_argument("--feeds", help="comma-separated; default every feed")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--tick", action="store_true",
                    help="one pass of the feeds that are due by the ledger (the worker's job)")
    ap.add_argument("--skip", help="comma-separated feeds to leave out")
    ap.add_argument("--until", help="with --loop: stop at this UTC time")
    ap.add_argument("--origin", default=default_origin())
    ap.add_argument("--measure", help="keep state in this JSON file; write no database")
    ap.add_argument("--backfill-news", action="store_true")
    ap.add_argument("--backfill-yahoo", nargs=2, metavar=("FIRST", "LAST"),
                    help="BetMGM splits for every game of these dates (YYYY-MM-DD)")
    ap.add_argument("--port", type=int, default=LOOP_PORT,
                    help="with --loop: the local port that marks this loop as running")
    a = ap.parse_args(argv)
    names = a.feeds.split(",") if a.feeds else list(FEEDS)
    unknown = [n for n in names if n not in FEEDS]
    if unknown:
        ap.error(f"unknown feed(s): {unknown}; known: {sorted(FEEDS)}")
    skip = set(a.skip.split(",")) if a.skip else set()
    feeds = [FEEDS[n] for n in names if n not in skip]

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
        if a.backfill_yahoo:
            print(json.dumps(backfill_yahoo(conn, a.origin, date.fromisoformat(a.backfill_yahoo[0]),
                                            date.fromisoformat(a.backfill_yahoo[1]))))
            return 0
        if a.tick:
            for res in tick(conn, a.origin, feeds):
                print(json.dumps(res))
            return 0
        if not a.loop:
            for f in feeds:
                print(json.dumps(one_read(conn, f, a.origin, measure=measure)))
            return 0
        guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            guard.bind(("127.0.0.1", a.port))
        except OSError:
            print(json.dumps({"already_running": a.port}))
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

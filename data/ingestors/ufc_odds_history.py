"""UFC fight-winner and round-total history from the odds feed, 2020-06 on.

WHY. The UFC search of 2026-11-13 (docs/ufc_market_audit.md) found a rating
model anchored on the FIRST posted moneyline that predicts the line's move,
but only on a free archive whose "open" is whichever book posts first. The
question it left is whether DraftKings', FanDuel's or Pinnacle's own first
price carries it, and round totals had no price history at all. This buys
both (mike, 2026-11-13: "yes", 150,360 credits quoted).

WHAT THE FEED HOLDS (measured 2026-11-13). The MMA key has nothing before
2020-06-06. A bulk historical snapshot of fight winner and round totals at
the US and EU regions bills 20 credits a market: 40 a snapshot. Round totals
appear in it from Pinnacle in 2021 and DraftKings by 2025. The key carries
every promotion, not only UFC.

TWO STAGES, each a list of instants to ask for:

  * DAILY: 12:00 UTC on every day from FIRST_DAY to LAST_DAY (the day before
    our own store starts keeping every pull). It dates each fight's first
    listing at every book and gives a daily price path.
  * CARDS: on each UFC card day, six pulls timed off the start times the daily
    pulls returned for that card's fights: six hours, one hour and five
    minutes before the first fight, five minutes before the middle of the
    card, and one hour and five minutes before the last fight. The latest one
    before a fight's start is its close.

FETCH, THEN STORE. --fetch asks each instant once and writes the answer to
the spool (DIR/<stage>/<YYYYMMDDTHHMM>.json.gz), so a stopped run resumes
buying nothing twice. --store reads the whole spool in the feed's own time
order and writes:

  * ufc_odds_history: one row per (event, book, market) each time its price
    or line differs from the last stored row (change-only), with the
    snapshot that first showed it. Every promotion is kept; a UFC fight
    carries our ufc_fight_log game id (the unordered fighter-slug pair within
    two days, names through config.UFC_NAME_ALIASES), others NULL.
  * ufc_odds_history_pulls: one row per instant asked, in the same
    transaction as its rows: the ledger.

The change memory is rebuilt from the spool on every store, so a re-run
stores exactly what an unbroken run would. The table is not `odds`: the odds
clean-up never visits it, and the app never reads it.

CREDITS. --ceiling (default: the stage's unspooled asks at 40 each, so the
two stages together cannot pass the quoted 150,360) and --floor (default
1,000,000, so other feeds are never starved) are hard stops, read off the
feed's own billing headers on every answer.

    python -m data.ingestors.ufc_odds_history --spool DIR                 # the plan, no spend
    python -m data.ingestors.ufc_odds_history --spool DIR --stage daily --fetch --store
    python -m data.ingestors.ufc_odds_history --spool DIR --stage cards --fetch --store
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SPORT_KEY = "mma_mixed_martial_arts"
BASE = f"https://api.the-odds-api.com/v4/historical/sports/{SPORT_KEY}/odds"
SOURCE = "odds_api_ufc_history"
MARKETS = ("h2h", "totals")
REGIONS = "us,eu"
CALL_COST = 40                       # 20 a market at two regions, measured 2026-11-13
FIRST_DAY = date(2020, 6, 6)         # the feed's first MMA snapshot
LAST_DAY = date(2026, 6, 13)         # our own store keeps every pull from here
DAILY_HOUR = 12
QUOTED = 150_360
MATCH_DAYS = 2
STAGES = ("daily", "cards")

TABLE = "ufc_odds_history"
COLS = ("event_id", "commence_time", "home_name", "away_name", "game_id", "bookmaker",
        "market", "last_update", "served_at", "home_price", "away_price", "total_line",
        "over_price", "under_price", "source")
DDL = """
CREATE TABLE IF NOT EXISTS ufc_odds_history (
    event_id       TEXT NOT NULL,
    commence_time  TIMESTAMPTZ,
    home_name      TEXT NOT NULL,
    away_name      TEXT NOT NULL,
    game_id        TEXT,
    bookmaker      TEXT NOT NULL,
    market         TEXT NOT NULL,
    last_update    TIMESTAMPTZ,
    served_at      TIMESTAMPTZ NOT NULL,
    home_price     INTEGER,
    away_price     INTEGER,
    total_line     REAL,
    over_price     INTEGER,
    under_price    INTEGER,
    source         TEXT NOT NULL,
    PRIMARY KEY (event_id, bookmaker, market, served_at)
)
"""
INDEX = "ufc_odds_history_game_idx"
INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {INDEX} ON ufc_odds_history (game_id)"
PULLS = "ufc_odds_history_pulls"
PULL_COLS = ("asked_at", "stage", "served_at", "events", "rows_stored", "stored_at")
PULLS_DDL = """
CREATE TABLE IF NOT EXISTS ufc_odds_history_pulls (
    asked_at     TIMESTAMPTZ PRIMARY KEY,
    stage        TEXT NOT NULL,
    served_at    TIMESTAMPTZ,
    events       INTEGER NOT NULL,
    rows_stored  INTEGER NOT NULL,
    stored_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def ensure_tables(conn) -> None:
    changed = False
    if not schema_is_current(conn, TABLE, columns=COLS, indexes=(INDEX,), rls=True,
                             revoked_from=API_ROLES):
        conn.execute(DDL)
        conn.execute(INDEX_DDL)
        lock_down(conn, TABLE)
        changed = True
    if not schema_is_current(conn, PULLS, columns=PULL_COLS, rls=True, revoked_from=API_ROLES):
        conn.execute(PULLS_DDL)
        lock_down(conn, PULLS)
        changed = True
    if changed:
        conn.commit()


# ── time and identity ────────────────────────────────────────────────────────

def _utc(s) -> datetime | None:
    if s is None or s == "":
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _stamp(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name: str) -> str:
    """Accent-folded, lowercase, hyphenated: the UFC tables' fighter key."""
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


def feed_slug(name: str) -> str:
    """A feed name's slug after the Odds API -> ufcstats alias map."""
    return slugify(config.UFC_NAME_ALIASES.get(name, name))


class FightIndex:
    """Places a feed event on a ufc_fight_log game id by the unordered fighter
    pair whose fight date is within MATCH_DAYS of the event's start."""

    def __init__(self, fights: list[tuple[str, str, str, str]]):
        self._by_pair: dict[frozenset, list[tuple[date, str]]] = defaultdict(list)
        self.card_day: dict[str, date] = {}
        for gid, d, a, b in fights:
            day = date.fromisoformat(str(d)[:10])
            self._by_pair[frozenset((slugify(a), slugify(b)))].append((day, gid))
            self.card_day[gid] = day

    def __call__(self, home: str, away: str, commence: datetime | None) -> str | None:
        if commence is None:
            return None
        want = commence.date()
        for day, gid in self._by_pair.get(frozenset((feed_slug(home), feed_slug(away))), []):
            if abs((day - want).days) <= MATCH_DAYS:
                return gid
        return None


def load_fight_index(conn) -> FightIndex:
    rows = conn.execute("""
        SELECT game_id, MIN(game_date), MIN(fighter_name), MAX(fighter_name)
          FROM ufc_fight_log GROUP BY game_id
    """).fetchall()
    return FightIndex([tuple(r) for r in rows])


# ── the plan ─────────────────────────────────────────────────────────────────

def daily_instants(first: date = FIRST_DAY, last: date = LAST_DAY) -> list[datetime]:
    out, d = [], first
    while d <= last:
        out.append(datetime(d.year, d.month, d.day, DAILY_HOUR, tzinfo=timezone.utc))
        d += timedelta(days=1)
    return out


def card_instants(starts_by_card: dict[date, list[datetime]]) -> list[datetime]:
    """Six asks per card from its fights' start times (module docstring)."""
    out = set()
    for starts in starts_by_card.values():
        if not starts:
            continue
        first, last = min(starts), max(starts)
        mid = first + (last - first) / 2
        for t in (first - timedelta(hours=6), first - timedelta(hours=1),
                  first - timedelta(minutes=5), mid - timedelta(minutes=5),
                  last - timedelta(hours=1), last - timedelta(minutes=5)):
            out.add(t.replace(second=0, microsecond=0))
    return sorted(out)


def card_starts(spool: Path, index: FightIndex, first: date = FIRST_DAY,
                last: date = LAST_DAY) -> dict[date, list[datetime]]:
    """{card day: the start times of its UFC fights}, read from the daily spool.
    A fight's start is the latest one the feed gave it."""
    start: dict[str, datetime] = {}
    for body in _spooled(spool, "daily"):
        for ev in body.get("data") or []:
            ct = _utc(ev.get("commence_time"))
            gid = index(ev.get("home_team") or "", ev.get("away_team") or "", ct)
            if gid:
                start[gid] = ct
    out: dict[date, list[datetime]] = defaultdict(list)
    for gid, ct in start.items():
        day = index.card_day[gid]
        if first <= day <= last:
            out[day].append(ct)
    return dict(out)


# ── the spool ────────────────────────────────────────────────────────────────

def spool_path(spool: Path, stage: str, asked: datetime) -> Path:
    return spool / stage / f"{asked.astimezone(timezone.utc):%Y%m%dT%H%M}.json.gz"


def write_spool(spool: Path, stage: str, asked: datetime, body: dict) -> None:
    p = spool_path(spool, stage, asked)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump({"asked_at": _stamp(asked), **body}, fh)
    tmp.replace(p)


def _spooled(spool: Path, stage: str):
    for p in sorted((spool / stage).glob("*.json.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            yield json.load(fh)


# ── fetch ────────────────────────────────────────────────────────────────────

def _params(asked: datetime) -> dict:
    return {"date": _stamp(asked), "regions": REGIONS, "markets": ",".join(MARKETS),
            "oddsFormat": "american"}


def fetch(meter, spool: Path, stage: str, instants: list[datetime]) -> dict:
    """Ask each instant not yet spooled; spool every 200 answer."""
    from data.ingestors.ncaab_odds_history import _paid_calls
    todo = [t for t in instants if not spool_path(spool, stage, t).exists()]
    stats = {"asked": 0, "spooled": 0, "failed": 0, "already": len(instants) - len(todo)}

    def jobs():
        for t in todo:
            yield t, BASE, _params(t)

    def consume(asked, r):
        stats["asked"] += 1
        if r is not None and r.status_code == 200:
            write_spool(spool, stage, asked, r.json())
            stats["spooled"] += 1
        else:
            stats["failed"] += 1
            logger.warning(f"{_stamp(asked)}: HTTP {getattr(r, 'status_code', None)}")

    stats["stopped"] = _paid_calls(meter, jobs(), CALL_COST, consume)
    stats["spent"], stats["remaining"] = meter.spent, meter.remaining
    return stats


# ── store ────────────────────────────────────────────────────────────────────

def _price(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def quote_rows(body: dict, index: FightIndex) -> list[dict]:
    """Every (event, book, market) quote in one snapshot, as table rows."""
    served = _utc(body.get("timestamp"))
    out = []
    for ev in body.get("data") or []:
        home, away = ev.get("home_team") or "", ev.get("away_team") or ""
        ct = _utc(ev.get("commence_time"))
        gid = index(home, away, ct)
        for bk in ev.get("bookmakers") or []:
            for mk in bk.get("markets") or []:
                key = mk.get("key")
                if key not in MARKETS:
                    continue
                row = dict(event_id=ev.get("id"), commence_time=ct, home_name=home,
                           away_name=away, game_id=gid, bookmaker=bk.get("key"), market=key,
                           last_update=_utc(mk.get("last_update") or bk.get("last_update")),
                           served_at=served, home_price=None, away_price=None,
                           total_line=None, over_price=None, under_price=None, source=SOURCE)
                for o in mk.get("outcomes") or []:
                    name = o.get("name")
                    if key == "h2h":
                        if name == home:
                            row["home_price"] = _price(o.get("price"))
                        elif name == away:
                            row["away_price"] = _price(o.get("price"))
                    else:
                        if name == "Over":
                            row["over_price"] = _price(o.get("price"))
                            row["total_line"] = o.get("point")
                        elif name == "Under":
                            row["under_price"] = _price(o.get("price"))
                if key == "h2h" and (row["home_price"] is None or row["away_price"] is None):
                    continue
                if key == "totals" and (row["total_line"] is None or row["over_price"] is None
                                        or row["under_price"] is None):
                    continue
                if row["event_id"] and row["bookmaker"] and served:
                    out.append(row)
    return out


class ChangeKeeper:
    """Keeps a quote only when its price or line differs from the last kept
    one for the same event, book and market."""

    def __init__(self):
        self._last: dict[tuple, tuple] = {}

    def wanted(self, row: dict) -> bool:
        k = (row["event_id"], row["bookmaker"], row["market"])
        q = (row["home_price"], row["away_price"], row["total_line"], row["over_price"],
             row["under_price"])
        if self._last.get(k) == q:
            return False
        self._last[k] = q
        return True


def _held(conn) -> set[str]:
    return {_stamp(_utc(r[0])) for r in conn.execute(f"SELECT asked_at FROM {PULLS}").fetchall()}


def store(conn, spool: Path, index: FightIndex) -> dict:
    """Both stages' spool, in the feed's own time order, change-only."""
    ensure_tables(conn)
    held = _held(conn)
    snaps = []
    for stage in STAGES:
        for body in _spooled(spool, stage):
            snaps.append((stage, body))
    snaps.sort(key=lambda sb: (sb[1].get("timestamp") or "", sb[1]["asked_at"]))
    keeper = ChangeKeeper()
    cols = list(COLS)
    sql = (f"INSERT INTO {TABLE} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
           "ON CONFLICT (event_id, bookmaker, market, served_at) DO NOTHING")
    stats = {"snapshots": len(snaps), "stored_snapshots": 0, "rows": 0, "already": 0}
    for stage, body in snaps:
        rows = [r for r in quote_rows(body, index) if keeper.wanted(r)]
        if body["asked_at"] in held:
            stats["already"] += 1
            continue
        if rows:
            conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        conn.execute(f"""INSERT INTO {PULLS} (asked_at, stage, served_at, events, rows_stored)
                         VALUES (%s, %s, %s, %s, %s) ON CONFLICT (asked_at) DO NOTHING""",
                     (body["asked_at"], stage, body.get("timestamp"),
                      len(body.get("data") or []), len(rows)))
        conn.commit()
        held.add(body["asked_at"])
        stats["stored_snapshots"] += 1
        stats["rows"] += len(rows)
    return stats


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spool", required=True, type=Path)
    ap.add_argument("--stage", choices=STAGES)
    ap.add_argument("--start", type=date.fromisoformat, default=FIRST_DAY)
    ap.add_argument("--end", type=date.fromisoformat, default=LAST_DAY)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--store", action="store_true")
    ap.add_argument("--ceiling", type=int, default=None,
                    help="default: this stage's unspooled asks at CALL_COST each")
    ap.add_argument("--floor", type=int, default=1_000_000)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    from data.db import get_connection
    conn = get_connection()
    try:
        index = load_fight_index(conn)
        plans = {"daily": daily_instants(a.start, a.end)}
        plans["cards"] = card_instants(card_starts(a.spool, index, a.start, a.end))
        for stage, inst in plans.items():
            todo = sum(1 for t in inst if not spool_path(a.spool, stage, t).exists())
            logger.info(f"{stage}: {len(inst):,} instants, {todo:,} not spooled, "
                        f"at most {todo * CALL_COST:,} credits")
        if a.fetch:
            if not a.stage:
                raise SystemExit("--fetch needs --stage")
            from data.ingestors.ncaab_odds_history import PoolMeter
            todo = sum(1 for t in plans[a.stage] if not spool_path(a.spool, a.stage, t).exists())
            ceiling = a.ceiling if a.ceiling is not None else todo * CALL_COST
            meter = PoolMeter(ceiling, a.floor, a.workers)
            logger.info(f"fetch {a.stage}: {fetch(meter, a.spool, a.stage, plans[a.stage])}")
        if a.store:
            logger.success(f"store: {store(conn, a.spool, index)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

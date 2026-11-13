"""Pinnacle's own tennis prices, every professional level, from its public guest
API, stored in Supabase.

WHY. The odds feed sells tennis only for its 53 top-tier tournaments, and on
2026-11-13 it carried no Pinnacle price for either Finals while Pinnacle's own
site priced both. Pinnacle prices every level: on 2026-11-13 its tennis board
held 33 leagues, among them ATP Challengers, ITF men's and women's events, a
WTA 125, a 250 and the Davis Cup. It is the sharp reference for every match
below the top tier, and a second one above it.

THE SOURCE. guest.api.arcadia.pinnacle.com/0.1, the API pinnacle.com's own pages
read, without a key (a plain request answered 200 from mike's PC, 2026-11-13).
Two calls a pass hold the whole sport (id 33):
  /sports/33/matchups              every match: league, players, start, best-of,
                                   live or not. A match is two matchups: the
                                   parent in Sets (match winner, sets spread,
                                   sets total, first-set lines) and a child in
                                   Games (games spread, total games).
  /sports/33/markets/straight      every price, with the market's version (it
                                   moves when a price moves) and its stake limit.

WHAT IS STORED, both worker-only:
  tennis_pinnacle_matchups   one row per matchup, first and last seen.
  tennis_pinnacle_prices     one row per (matchup, market, version): a price
                             is written once, when its version is first seen,
                             so the table is change-only by Pinnacle's own count.
Doubles leagues are skipped. In-play prices are stored and marked (is_live).

    python -m data.ingestors.tennis_pinnacle --once
    python -m data.ingestors.tennis_pinnacle --until 2026-12-31T00:00:00 --every-min 30
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
SPORT_ID = 33
SOURCE = "pinnacle_guest"

MATCHUPS = "tennis_pinnacle_matchups"
MATCHUP_COLS = ("matchup_id", "parent_id", "units", "league_id", "league_name", "best_of",
                "start_time", "home_name", "away_name", "is_live", "status", "source",
                "first_seen", "last_seen")
MATCHUPS_DDL = """
CREATE TABLE IF NOT EXISTS tennis_pinnacle_matchups (
    matchup_id   BIGINT PRIMARY KEY,
    parent_id    BIGINT,
    units        TEXT,
    league_id    BIGINT,
    league_name  TEXT,
    best_of      INTEGER,
    start_time   TIMESTAMPTZ,
    home_name    TEXT,
    away_name    TEXT,
    is_live      BOOLEAN,
    status       TEXT,
    source       TEXT NOT NULL,
    first_seen   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
PRICES = "tennis_pinnacle_prices"
PRICE_COLS = ("matchup_id", "market_key", "type", "period", "is_alternate", "version",
              "seen_at", "is_live", "home_price", "away_price", "home_points", "away_points",
              "over_price", "under_price", "total_points", "limit_amount", "source")
PRICES_DDL = """
CREATE TABLE IF NOT EXISTS tennis_pinnacle_prices (
    matchup_id    BIGINT NOT NULL,
    market_key    TEXT NOT NULL,
    type          TEXT,
    period        INTEGER,
    is_alternate  BOOLEAN,
    version       BIGINT NOT NULL,
    seen_at       TIMESTAMPTZ NOT NULL,
    is_live       BOOLEAN,
    home_price    INTEGER,
    away_price    INTEGER,
    home_points   DOUBLE PRECISION,
    away_points   DOUBLE PRECISION,
    over_price    INTEGER,
    under_price   INTEGER,
    total_points  DOUBLE PRECISION,
    limit_amount  DOUBLE PRECISION,
    source        TEXT NOT NULL,
    PRIMARY KEY (matchup_id, market_key, version)
)
"""
PRICES_INDEX = "idx_tennis_pinnacle_prices_seen"
PRICES_INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {PRICES_INDEX} ON {PRICES} (seen_at)"


def ensure_tables(conn) -> None:
    changed = False
    if not schema_is_current(conn, MATCHUPS, columns=MATCHUP_COLS, rls=True,
                             revoked_from=API_ROLES):
        conn.execute(MATCHUPS_DDL)
        lock_down(conn, MATCHUPS)
        changed = True
    if not schema_is_current(conn, PRICES, columns=PRICE_COLS, indexes=(PRICES_INDEX,),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(PRICES_DDL)
        conn.execute(PRICES_INDEX_DDL)
        lock_down(conn, PRICES)
        changed = True
    if changed:
        conn.commit()


def fetch() -> tuple[list, list]:
    mu = requests.get(f"{BASE}/sports/{SPORT_ID}/matchups", params={"withSpecials": "false"},
                      timeout=90)
    mu.raise_for_status()
    mk = requests.get(f"{BASE}/sports/{SPORT_ID}/markets/straight",
                      params={"primaryOnly": "false"}, timeout=90)
    mk.raise_for_status()
    return mu.json(), mk.json()


def _singles(m: dict) -> bool:
    return "doubles" not in str((m.get("league") or {}).get("name", "")).lower()


def matchup_rows(matchups: list) -> list[tuple]:
    out = []
    for m in matchups:
        if m.get("type") != "matchup" or not _singles(m):
            continue
        parts = {p.get("alignment"): p.get("name") for p in m.get("participants") or []}
        lg = m.get("league") or {}
        out.append((m["id"], m.get("parentId"), m.get("units"), lg.get("id"), lg.get("name"),
                    m.get("bestOfX"), m.get("startTime"), parts.get("home"), parts.get("away"),
                    bool(m.get("isLive")), m.get("status"), SOURCE))
    return out


def price_rows(markets: list, live: dict, seen_at: str) -> list[tuple]:
    """Moneyline, spread and total markets of the matchups in `live` (the
    singles ones), in PRICE_COLS order."""
    out = []
    for x in markets:
        mid = x.get("matchupId")
        if mid not in live or x.get("type") not in ("moneyline", "spread", "total"):
            continue
        hp = ap = hpt = apt = op = up = tp = None
        for pr in x.get("prices") or []:
            d = pr.get("designation")
            if d == "home":
                hp, hpt = pr.get("price"), pr.get("points")
            elif d == "away":
                ap, apt = pr.get("price"), pr.get("points")
            elif d == "over":
                op, tp = pr.get("price"), pr.get("points")
            elif d == "under":
                up = pr.get("price")
        lim = next((li.get("amount") for li in x.get("limits") or []
                    if li.get("type") == "maxRiskStake"), None)
        out.append((mid, x.get("key"), x.get("type"), x.get("period"),
                    bool(x.get("isAlternate")), x.get("version"), seen_at, live[mid],
                    hp, ap, hpt, apt, op, up, tp, lim, SOURCE))
    return out


_MATCHUP_UPSERT = (
    f"INSERT INTO {MATCHUPS} ({', '.join(MATCHUP_COLS[:-2])}) VALUES "
    f"({', '.join(['%s'] * (len(MATCHUP_COLS) - 2))}) ON CONFLICT (matchup_id) DO UPDATE SET "
    "start_time = EXCLUDED.start_time, is_live = EXCLUDED.is_live, status = EXCLUDED.status, "
    "last_seen = NOW()")
_PRICE_INSERT = (f"INSERT INTO {PRICES} ({', '.join(PRICE_COLS)}) VALUES "
                 f"({', '.join(['%s'] * len(PRICE_COLS))}) ON CONFLICT DO NOTHING")


def one_pass(conn) -> dict:
    seen_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    matchups, markets = fetch()
    mrows = matchup_rows(matchups)
    live = {r[0]: r[9] for r in mrows}
    prows = price_rows(markets, live, seen_at)
    ensure_tables(conn)
    if mrows:
        conn.executemany(_MATCHUP_UPSERT, mrows)
    if prows:
        conn.executemany(_PRICE_INSERT, prows)
    conn.commit()
    return {"seen_at": seen_at, "matchups": len(mrows), "prices_seen": len(prows)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pinnacle tennis prices -> Supabase")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--until", help="poll until this UTC time")
    ap.add_argument("--every-min", type=float, default=30)
    a = ap.parse_args(argv)
    from data.db import get_connection
    conn = get_connection()
    try:
        if a.once or not a.until:
            print(json.dumps(one_pass(conn)))
            return 0
        until = datetime.fromisoformat(a.until).replace(tzinfo=timezone.utc)
        while datetime.now(timezone.utc) < until:
            try:
                logger.info(json.dumps(one_pass(conn)))
            except Exception as exc:                            # noqa: BLE001
                logger.warning(f"pass failed: {exc}")
                try:
                    conn.rollback()
                except Exception:                               # noqa: BLE001
                    pass
            time.sleep(a.every_min * 60)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

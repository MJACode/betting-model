"""The NCAAB opener grid's ledgers and its read-back, against a real Postgres.

WHY A REAL DATABASE. Two claims here are the server's, not Python's.

  * The grid leaves the shared pull ledger as it is. odds_history_pulls keeps
    production's key (sport, snapshot_date, hour_utc), so every purchase's
    ON CONFLICT naming those three columns still works after the grid has
    checked its tables and bought. The grid's half hours go to
    odds_history_fetches, keyed on the instant. (A re-key to four columns,
    the first version of this change, made such a writer raise after the paid
    call and roll its rows back: the 2026-10-30 review.)
  * A quote already in `odds` is not stored again: not one the game-line
    purchase stored, and not one an earlier grid run stored before a stop.
    `odds` has no unique index on a quote and _insert_odds always appends, so
    only the read-back stops a second copy.

The ledgers are created in production's shape (pg_constraint and
information_schema on the Supabase connector, 2026-10-30); `odds` carries
production's columns and types (tests/test_ncaab_odds_replay_pg.py). Runs on
LATEST_LINE_TEST_DSN or a throwaway cluster (tests/_pg.py); skips where
neither exists.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.ingestors import nba_odds_history as nba  # noqa: E402
from data.ingestors import ncaab_odds_history as h  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402
from tests.test_ncaab_odds_history import (GAMES, REGISTRY, FakeMeter, Resp,  # noqa: E402
                                           _event, contract_process_events)
from tests.test_ncaab_odds_replay_pg import ODDS_DDL  # noqa: E402

# Production's pull ledger, as it stands on 2026-10-30.
PULLS_DDL = """
CREATE TABLE odds_history_pulls (
    sport         TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    hour_utc      INTEGER NOT NULL,
    pulled_at     TIMESTAMPTZ NOT NULL,
    rows          INTEGER NOT NULL,
    PRIMARY KEY (sport, snapshot_date, hour_utc)
)
"""
# The ledger write every other history purchase makes (odds_ingestor's
# backfill and the NBA purchase on origin/master, and any older copy of them).
OTHER_WRITER = """
INSERT INTO odds_history_pulls (sport, snapshot_date, hour_utc, pulled_at, rows)
VALUES (%s, %s, %s, NOW(), %s)
ON CONFLICT (sport, snapshot_date, hour_utc) DO UPDATE
   SET pulled_at = NOW(), rows = EXCLUDED.rows
"""
EV = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z",
            last_update="2025-11-17T20:12:00Z")
MOVED = _event("e1", "Duke Blue Devils", "Kentucky Wildcats", "2025-11-19T00:30:00Z",
               home_pt=-5.5, last_update="2025-11-17T22:41:00Z")


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-grid-pg-") as d:
        yield d


@pytest.fixture()
def cur(dsn, monkeypatch):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS odds, odds_history_pulls, odds_history_fetches, "
              "ncaab_odds_unmatched")
    c.execute("""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            CREATE ROLE authenticated; END IF; END $$""")
    for ddl in (ODDS_DDL, PULLS_DDL, nba.FETCH_LEDGER_DDL, h.UNMATCHED_DDL):
        c.execute(ddl)
    monkeypatch.setenv("DATABASE_URL", dsn)
    try:
        yield c
    finally:
        conn.close()


def _key(cur, table) -> list[str]:
    cur.execute("""
        SELECT array_agg(a.attname ORDER BY k.ord)
          FROM pg_constraint c
          CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
         WHERE c.conrelid = %s::regclass AND c.contype = 'p'""", (table,))
    return list(cur.fetchone()[0])


def _buy(conn, monkeypatch, when, events, keeper, taken=None):
    monkeypatch.setattr(h, "_process_events", contract_process_events)
    meter = FakeMeter(lambda u, p: Resp(body={"timestamp": p["date"], "data": list(events)}))
    stats = defaultdict(int)
    tips = {g["game_id"]: g["commence_time"] for g in GAMES}
    assert h._buy_snapshot(conn, meter, tips, h.EventResolver(REGISTRY, GAMES),
                           datetime.fromisoformat(when), stats, keeper, taken=taken)
    return meter, stats


def _odds(cur) -> list[tuple]:
    cur.execute("SELECT game_id, market, bookmaker, snapshot_at, home_price, away_price, "
                "spread_home, total_line, source FROM odds ORDER BY odds_id")
    return cur.fetchall()


def test_the_grid_leaves_the_shared_ledger_and_its_other_writers_alone(cur, monkeypatch):
    from data.db import get_connection
    cur.execute(OTHER_WRITER, ("NHL", "2025-01-01", 22, 1))
    conn = get_connection()
    try:
        h._ensure_tables(conn)                # the purchase's own table check, before it buys
        _buy(conn, monkeypatch, "2025-11-17T22:00:00+00:00", [EV], h.ChangeKeeper(), set())
        _buy(conn, monkeypatch, "2025-11-17T22:30:00+00:00", [EV], h.ChangeKeeper(), set())
        assert h._held_instants(conn) == {datetime.fromisoformat("2025-11-17T22:00:00+00:00"),
                                          datetime.fromisoformat("2025-11-17T22:30:00+00:00")}
    finally:
        conn.close()
    assert _key(cur, "odds_history_pulls") == ["sport", "snapshot_date", "hour_utc"]
    # every other purchase's ledger write still lands, and still updates in place
    cur.execute(OTHER_WRITER, ("NHL", "2025-01-02", 22, 1))
    cur.execute(OTHER_WRITER, ("NHL", "2025-01-02", 22, 5))
    cur.execute("SELECT sport, snapshot_date, hour_utc, rows FROM odds_history_pulls "
                "ORDER BY sport, snapshot_date, hour_utc")
    assert cur.fetchall() == [("NCAAB", "2025-11-17", 22, 3), ("NHL", "2025-01-01", 22, 1),
                              ("NHL", "2025-01-02", 22, 5)]
    cur.execute("SELECT sport, requested_at, why, rows FROM odds_history_fetches")
    (sport, at, why, rows), = cur.fetchall()
    assert (sport, at, why, rows) == ("NCAAB", datetime.fromisoformat("2025-11-17T22:30:00+00:00"),
                                      "opener_grid", 0)


def test_a_quote_already_in_odds_is_not_stored_again(cur, monkeypatch):
    from data.db import get_connection
    conn = get_connection()
    try:
        # the game-line purchase bought D-1 22Z and stored the evening-before anchor
        _buy(conn, monkeypatch, "2025-11-17T22:00:00+00:00", [EV], h.QuoteKeeper(GAMES))
        assert len(_odds(cur)) == 3
        # the grid at 22:30, a fresh keeper: the feed still shows the same quotes
        _, st = _buy(conn, monkeypatch, "2025-11-17T22:30:00+00:00", [EV], h.ChangeKeeper(), set())
        assert len(_odds(cur)) == 3 and st["rows_already_stored"] == 3
        # a grid run resumed after a stop, a fresh keeper again
        _buy(conn, monkeypatch, "2025-11-17T23:00:00+00:00", [EV], h.ChangeKeeper(), set())
        assert len(_odds(cur)) == 3
        # the spread moved: that quote is new and is stored
        _, st = _buy(conn, monkeypatch, "2025-11-17T23:30:00+00:00", [MOVED], h.ChangeKeeper(),
                     set())
        assert st["odds_rows"] == 3 and len(_odds(cur)) == 6
    finally:
        conn.close()
    rows = _odds(cur)
    assert len(set(rows)) == len(rows)                       # no quote stored twice

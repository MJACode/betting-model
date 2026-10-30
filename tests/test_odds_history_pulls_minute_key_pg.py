"""The pull ledger gains a minute, against a real Postgres.

WHY A REAL DATABASE. The claims here are the server's: that the migration
turns production's hour key (sport, snapshot_date, hour_utc) into (sport,
snapshot_date, hour_utc, minute_utc) with every existing row reading as
minute 0, under the SAME constraint name; that every writer's
ON CONFLICT ON CONSTRAINT odds_history_pulls_pkey works before the migration
and after it; that a half-hour row then sits beside its hour's row instead of
overwriting it; and that the purchase applies the migration itself when the
worker pass has not yet. Runs on LATEST_LINE_TEST_DSN or a throwaway cluster
(tests/_pg.py); skips where neither exists.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.ingestors import ncaab_odds_history as h  # noqa: E402
from data.ingestors import odds_ingestor as oi  # noqa: E402
from data.view_migrations import MIGRATIONS_DIR  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

# Production's ledger as it stands (pg_constraint and information_schema on
# the Supabase connector, 2026-10-30): PRIMARY KEY (sport, snapshot_date,
# hour_utc), named odds_history_pulls_pkey.
OLD_DDL = """
CREATE TABLE odds_history_pulls (
    sport         TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    hour_utc      INTEGER NOT NULL,
    pulled_at     TIMESTAMPTZ NOT NULL,
    rows          INTEGER NOT NULL,
    PRIMARY KEY (sport, snapshot_date, hour_utc)
)
"""
# The other sports' writers (odds_ingestor's backfill, the NBA purchase): no
# minute named, so the column's default applies once it exists.
HOUR_WRITER = """
INSERT INTO odds_history_pulls (sport, snapshot_date, hour_utc, pulled_at, rows)
VALUES (%s, %s, %s, NOW(), %s)
ON CONFLICT ON CONSTRAINT odds_history_pulls_pkey DO UPDATE
   SET pulled_at = NOW(), rows = EXCLUDED.rows
"""


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("minute-key-pg-") as d:
        yield d


@pytest.fixture()
def cur(dsn, monkeypatch):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS odds_history_pulls")
    c.execute("""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            CREATE ROLE authenticated; END IF; END $$""")
    monkeypatch.setenv("DATABASE_URL", dsn)
    try:
        yield c
    finally:
        conn.close()


def _migration() -> str:
    return (MIGRATIONS_DIR / h.MINUTE_KEY_MIGRATION.name).read_text(encoding="utf-8")


def _key(cur) -> tuple[str, list[str]]:
    cur.execute("""
        SELECT c.conname, array_agg(a.attname ORDER BY k.ord)
          FROM pg_constraint c
          CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
         WHERE c.conrelid = 'odds_history_pulls'::regclass AND c.contype = 'p'
         GROUP BY c.conname""")
    name, cols = cur.fetchone()
    return name, list(cols)


def _rows(cur):
    cur.execute("SELECT sport, snapshot_date, hour_utc, minute_utc, rows FROM odds_history_pulls "
                "ORDER BY sport, snapshot_date, hour_utc, minute_utc")
    return cur.fetchall()


def test_the_migration_keys_on_the_minute_and_existing_rows_read_as_minute_0(cur):
    cur.execute(OLD_DDL)
    # the hour writer on the old key: the second write updates the first
    cur.execute(HOUR_WRITER, ("NCAAB", "2025-11-19", 22, 99))
    cur.execute(HOUR_WRITER, ("NCAAB", "2025-11-19", 22, 100))
    cur.execute(HOUR_WRITER, ("NBA", "2026-01-15", 23, 50))
    cur.execute(_migration())
    assert _key(cur) == ("odds_history_pulls_pkey",
                         ["sport", "snapshot_date", "hour_utc", "minute_utc"])
    assert _rows(cur) == [("NBA", "2026-01-15", 23, 0, 50), ("NCAAB", "2025-11-19", 22, 0, 100)]

    # a half-hour row sits beside its hour's row; it does not overwrite it
    cur.execute("""
        INSERT INTO odds_history_pulls (sport, snapshot_date, hour_utc, minute_utc, pulled_at, rows)
        VALUES ('NCAAB', '2025-11-19', 22, 30, NOW(), 7)
        ON CONFLICT ON CONSTRAINT odds_history_pulls_pkey DO UPDATE
           SET pulled_at = NOW(), rows = EXCLUDED.rows""")
    # and the other sports' writer still lands on minute 0, updating in place
    cur.execute(HOUR_WRITER, ("NBA", "2026-01-15", 23, 51))
    assert _rows(cur) == [("NBA", "2026-01-15", 23, 0, 51), ("NCAAB", "2025-11-19", 22, 0, 100),
                          ("NCAAB", "2025-11-19", 22, 30, 7)]

    cur.execute(_migration())                                   # a second pass changes nothing
    assert _key(cur)[1] == ["sport", "snapshot_date", "hour_utc", "minute_utc"]
    assert len(_rows(cur)) == 3
    with pytest.raises(psycopg2.errors.CheckViolation):
        cur.execute("INSERT INTO odds_history_pulls (sport, snapshot_date, hour_utc, minute_utc, "
                    "pulled_at, rows) VALUES ('NCAAB', '2025-11-19', 22, 60, NOW(), 0)")


def test_a_fresh_ledger_is_created_on_the_minute_key_and_the_migration_leaves_it(cur):
    cur.execute(oi.PULL_LEDGER_DDL)
    assert _key(cur) == ("odds_history_pulls_pkey",
                         ["sport", "snapshot_date", "hour_utc", "minute_utc"])
    cur.execute(_migration())
    assert _key(cur)[1] == ["sport", "snapshot_date", "hour_utc", "minute_utc"]


def test_the_migration_does_nothing_where_the_ledger_does_not_exist(cur):
    cur.execute(_migration())
    cur.execute("SELECT to_regclass('public.odds_history_pulls')")
    assert cur.fetchone() == (None,)


def test_the_purchase_re_keys_an_hour_keyed_ledger_and_then_buys_the_half_hour(cur, monkeypatch):
    from data.db import get_connection
    from tests.test_ncaab_odds_history import REGISTRY, FakeMeter, Resp, contract_process_events
    cur.execute(OLD_DDL)
    cur.execute(HOUR_WRITER, ("NCAAB", "2025-11-19", 22, 100))
    conn = get_connection()
    try:
        # read before the migration: the hour row, as minute 0
        assert h._held_instants(conn) == {datetime.fromisoformat("2025-11-19T22:00:00+00:00")}
        assert h._ledger_keyed_by_minute(conn) is False
        h._ensure_tables(conn)
        assert h._ledger_keyed_by_minute(conn) is True

        monkeypatch.setattr(h, "_process_events", contract_process_events)
        meter = FakeMeter(lambda u, p: Resp(body={"timestamp": "x", "data": []}))
        resolver = h.EventResolver(REGISTRY, [])
        for when in ("2025-11-19T22:30:00+00:00", "2025-11-19T22:30:00+00:00",
                     "2025-11-19T22:00:00+00:00"):
            stats = defaultdict(int)
            assert h._buy_snapshot(conn, meter, {}, resolver, datetime.fromisoformat(when), stats)
        assert len(meter.calls) == 1 and meter.calls[0][1]["date"] == "2025-11-19T22:30:00Z"
        assert h._held_instants(conn) == {datetime.fromisoformat("2025-11-19T22:00:00+00:00"),
                                          datetime.fromisoformat("2025-11-19T22:30:00+00:00")}
    finally:
        conn.close()
    assert [r[:4] for r in _rows(cur)] == [("NCAAB", "2025-11-19", 22, 0),
                                           ("NCAAB", "2025-11-19", 22, 30)]

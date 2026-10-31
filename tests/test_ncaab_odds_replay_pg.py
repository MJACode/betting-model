"""The NCAAB replay of kept raw events, against a real Postgres.

WHY A REAL DATABASE. Two properties are claims about the server, not about
Python: the dry run's connection cannot write (psycopg2 opens every
transaction READ ONLY), and a second --apply stores nothing new (the replay
reads `odds` back before it inserts). The raw rows are read through a
server-side cursor, which only a real server has. So this runs against
LATEST_LINE_TEST_DSN or a throwaway cluster from tests/_pg.py, and SKIPS only
where neither exists (the worker). The in-memory version of the same walk is
in tests/test_ncaab_odds_history.py.

The tables are created from the modules' own DDL (ncaab_odds_unmatched, the
pull ledger, ncaab_teams, ncaab_events); `odds` carries production's columns
and types (information_schema, 2026-10-29).
"""
from __future__ import annotations

import json

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.ingestors import ncaab_odds_history as h  # noqa: E402
from data.ingestors import ncaab_teams as nt  # noqa: E402
from data.ingestors import odds_ingestor as oi  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-replay-pg-") as d:
        yield d


ODDS_DDL = """
CREATE TABLE odds (
    odds_id BIGSERIAL PRIMARY KEY, game_id TEXT, sport TEXT, market TEXT, bookmaker TEXT,
    snapshot_type TEXT, snapshot_at TEXT,
    home_price NUMERIC, away_price NUMERIC, draw_price NUMERIC, spread_home NUMERIC,
    total_line NUMERIC, over_price NUMERIC, under_price NUMERIC, created_at TEXT DEFAULT now()::text,
    home_link TEXT, away_link TEXT, draw_link TEXT, over_link TEXT, under_link TEXT,
    home_sid TEXT, away_sid TEXT, draw_sid TEXT, over_sid TEXT, under_sid TEXT, source TEXT)
"""
TIP = "2025-11-20T17:00:00Z"
GAME_ID = "NCAAB_2025-11-20_duke_kansas-state"


def _event(eid, home, away, last_update, tip=TIP):
    mk = {"last_update": last_update}
    return {"id": eid, "commence_time": tip, "home_team": home, "away_team": away,
            "bookmakers": [{"key": "fanduel", "markets": [
                {"key": "h2h", **mk, "outcomes": [{"name": home, "price": -190},
                                                  {"name": away, "price": 160}]},
                {"key": "spreads", **mk, "outcomes": [
                    {"name": home, "price": -108, "point": -4.5},
                    {"name": away, "price": -112, "point": 4.5}]},
                {"key": "totals", **mk, "outcomes": [
                    {"name": "Over", "price": -110, "point": 149.5},
                    {"name": "Under", "price": -110, "point": 149.5}]}]}]}


# (event id, the feed's stamp, the markets' last_update, home name). "Kansas St
# Wildcats" places only through the 2026-10-29 shortened-school rule.
RAW = [
    ("e2", "2025-11-19T21:55:38Z", "2025-11-19T21:50:00Z", "Kansas St Wildcats"),  # 22Z opener
    ("e2", "2025-11-20T14:55:12Z", "2025-11-20T14:52:00Z", "Kansas St Wildcats"),  # 15Z anchor
    ("e2", "2025-11-20T15:55:20Z", "2025-11-20T15:51:00Z", "Kansas St Wildcats"),  # 16Z, an hour out
    ("e2", "2025-11-20T17:55:00Z", "2025-11-20T17:20:00Z", "Kansas St Wildcats"),  # 18Z, in play
    ("e2", "2025-11-18T09:00:00Z", "2025-11-18T08:58:00Z", "Kansas St Wildcats"),  # no instant
    ("e9", "2025-11-19T21:55:38Z", "2025-11-19T21:50:00Z", "Mystery Moose"),       # no team
]
LEDGER = [("2025-11-19", 22), ("2025-11-20", 15), ("2025-11-20", 16), ("2025-11-20", 18)]


@pytest.fixture()
def db(dsn, monkeypatch):
    """The five tables, filled; DATABASE_URL pointed at them."""
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS odds, ncaab_odds_unmatched, odds_history_pulls, "
                "ncaab_teams, ncaab_events")
    for ddl in (ODDS_DDL, h.UNMATCHED_DDL, oi.PULL_LEDGER_DDL, nt.TEAMS_DDL, nt.EVENTS_DDL):
        cur.execute(ddl)
    cur.executemany(
        "INSERT INTO ncaab_teams (espn_id, school, slug, mascot, display_name, short_name, "
        "abbreviation, is_d1) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)",
        [(150, "Duke", "duke", "Blue Devils", "Duke Blue Devils", "Duke", "DUKE"),
         (96, "Kentucky", "kentucky", "Wildcats", "Kentucky Wildcats", "Kentucky", "UK"),
         (2306, "Kansas State", "kansas-state", "Wildcats", "Kansas State Wildcats",
          "Kansas St", "KSU")])
    cur.execute("INSERT INTO ncaab_events (espn_event_id, game_id, season, game_date, "
                "commence_time, home_espn_id, away_espn_id) VALUES "
                "(401, %s, 2026, '2025-11-20', %s, 2306, 150)", (GAME_ID, TIP))
    cur.executemany("INSERT INTO odds_history_pulls (sport, snapshot_date, hour_utc, pulled_at, rows)"
                    " VALUES ('NCAAB', %s, %s, NOW(), 0)", LEDGER)
    cur.executemany(
        "INSERT INTO ncaab_odds_unmatched (snapshot_at, event_id, home_name, away_name, "
        "commence_time, payload, source) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)",
        [(stamp, eid, home, "Duke Blue Devils", TIP,
          json.dumps(_event(eid, home, "Duke Blue Devils", lu)), oi.HISTORICAL_ODDS_SOURCE)
         for eid, stamp, lu, home in RAW])
    monkeypatch.setenv("DATABASE_URL", dsn)
    nt.reset_registry_cache()
    try:
        yield conn
    finally:
        nt.reset_registry_cache()
        conn.close()


def _count(conn, table):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def _main(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["ncaab_odds_history", "--replay-unmatched",
                                     "--seasons", "2026", "2026", *argv])
    h.main()


def test_the_dry_run_connection_refuses_a_write_and_leaves_the_session_alone(db):
    conn = h._read_only_connection()
    try:
        with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
            conn.execute("INSERT INTO odds (game_id) VALUES ('x')")
        conn.rollback()
        with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
            conn.execute("DELETE FROM ncaab_odds_unmatched")
        conn.rollback()
        # every transaction is READ ONLY, and the SESSION default is untouched:
        # nothing is left on a pooled server connection for its next client
        assert conn.execute("SHOW transaction_read_only").fetchone()[0] == "on"
        assert conn.execute("SHOW default_transaction_read_only").fetchone()[0] == "off"
        conn.rollback()
        # the server-side cursor reads on it, in batches
        assert [len(b) for b in h._stream(conn, "SELECT generate_series(1, 1203)", ())] == [
            500, 500, 203]
    finally:
        conn.close()
    assert _count(db, "odds") == 0 and _count(db, "ncaab_odds_unmatched") == len(RAW)


def test_a_dry_run_then_an_apply_then_a_second_apply(db, monkeypatch, capsys):
    _main(monkeypatch)                                            # the default: a dry run
    out = capsys.readouterr().out
    assert "dry run, read only" in out and "9 would be inserted" in out
    assert "4 mapped to a planned instant, 1 unmapped" in out
    assert "1 resolved, 1 unresolved" in out and "12 parsed, 3 marked in-play, 9 kept" in out
    assert _count(db, "odds") == 0

    _main(monkeypatch, "--apply")
    out = capsys.readouterr().out
    assert "9 inserted" in out and _count(db, "odds") == 9
    cur = db.cursor()
    cur.execute("SELECT DISTINCT game_id, source, snapshot_type FROM odds")
    assert cur.fetchall() == [(GAME_ID, oi.HISTORICAL_ODDS_SOURCE, "open")]
    cur.execute("SELECT spread_home, home_price FROM odds WHERE market = 'spreads' "
                "ORDER BY snapshot_at")
    assert [(float(a), float(b)) for a, b in cur.fetchall()] == [(-4.5, -108.0)] * 3

    _main(monkeypatch, "--apply")                                 # idempotent
    out = capsys.readouterr().out
    assert "9 already stored, 0 inserted" in out and _count(db, "odds") == 9
    # the ledger and the raw store are read, never written
    assert _count(db, "odds_history_pulls") == len(LEDGER)
    assert _count(db, "ncaab_odds_unmatched") == len(RAW)

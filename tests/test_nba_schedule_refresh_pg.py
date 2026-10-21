"""The NBA schedule refresh's writes, run on a real Postgres.

tests/test_nba_schedule_refresh.py pins the plan and records the SQL the run
sends; nothing there runs it. These run the refresh's reads and writes through
the worker's own connection wrapper (data.db.DBConnection) against the two
tables as production declares them (column types read from
information_schema on 2026-10-20), so a write that is dropped, or one whose
guard is lost, shows up as a row that changed or did not. The health check
reads only nba_schedule.updated_at, so the confirm stamp is the run's one
signal that it reached ESPN; a played game's status must never be rewritten.

Needs a scratch Postgres (tests/_pg.py: LATEST_LINE_TEST_DSN, initdb on PATH,
or the embedded-postgres package in requirements-test.txt); skips without one.
"""
from __future__ import annotations

import pytest

psycopg2 = pytest.importorskip("psycopg2")

import data.ingestors.nba_schedule_refresh as nsr  # noqa: E402
from data.db import DBConnection  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402
from tests.test_nba_schedule_refresh import NOW, _board, _core, _espn, _refused  # noqa: E402


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("nba-schedule-pg-") as d:
        yield d


SCHEMA = """
DROP TABLE IF EXISTS games; DROP TABLE IF EXISTS nba_schedule;
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL, game_date TEXT NOT NULL,
    home_team TEXT NOT NULL, away_team TEXT NOT NULL, home_score NUMERIC, away_score NUMERIC,
    data_source TEXT, created_at TEXT DEFAULT (now())::text, updated_at TEXT DEFAULT (now())::text,
    commence_time TEXT, neutral_site INTEGER);
CREATE TABLE nba_schedule (
    nba_game_id TEXT PRIMARY KEY, game_id TEXT, season INTEGER NOT NULL, game_type TEXT NOT NULL,
    game_date TEXT NOT NULL, commence_time TEXT, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_score INTEGER, away_score INTEGER, status_text TEXT, ot_periods INTEGER, arena_name TEXT,
    arena_city TEXT, arena_state TEXT, is_neutral BOOLEAN, game_label TEXT, game_sublabel TEXT,
    national_tv TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
"""
LOADED = "2026-10-15 22:17:47+00"          # the by-hand load every 2026-27 row carries


@pytest.fixture
def conn(dsn):
    raw = psycopg2.connect(dsn)
    with raw.cursor() as cur:
        cur.execute(SCHEMA)
    raw.commit()
    c = DBConnection(raw)
    yield c
    raw.close()


def _sched(conn, nid, gid, kind, tip, status=None, score=None):
    _, d, away, home = gid.split("_")
    conn.execute("""INSERT INTO nba_schedule (nba_game_id, game_id, season, game_type, game_date,
                        commence_time, home_team, away_team, home_score, away_score, status_text, updated_at)
                    VALUES (%s, %s, 2027, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                 (nid, gid, kind, d, tip, home, away, score, score, status, LOADED))


def _game(conn, gid, tip, source="live"):
    _, d, away, home = gid.split("_")
    conn.execute("""INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
                        commence_time, data_source) VALUES (%s, 'NBA', 2027, %s, %s, %s, %s, %s)""",
                 (gid, d, home, away, tip, source))


def _row(conn, table, key, cols):
    col = "nba_game_id" if table == "nba_schedule" else "game_id"
    r = conn.execute(f"SELECT {', '.join(cols)} FROM {table} WHERE {col} = %s", (key,)).fetchall()
    return dict(zip(cols, r[0])) if r else None


def _confirmed(conn, nid) -> bool:
    return conn.execute("SELECT updated_at > %s::timestamptz FROM nba_schedule WHERE nba_game_id = %s",
                        (LOADED, nid)).fetchall()[0][0]


QF, SF, FINAL = "NBA_2025-12-09_MIA_ORL", "NBA_2025-12-13_NYK_ORL", "NBA_2025-12-16_SAS_NYK"


def test_a_run_confirms_listed_rows_adds_the_missing_game_and_drops_a_replaced_espn_row(conn):
    """The fixture's December 2025 games through refresh(): the quarterfinal is
    listed (confirmed, untouched), the semifinal is not (added, with a games
    row), and the final has the league's row and an old 'espn:' row (the
    'espn:' row goes)."""
    _sched(conn, "0062500001", QF, "regular", "2025-12-09T23:00:00+00:00", status="Final")
    _sched(conn, "0062500003", FINAL, "cup_final", "2025-12-17T01:30:00+00:00")
    _sched(conn, "espn:401809839", FINAL, "cup_final", "2025-12-17T01:30:00+00:00")
    _game(conn, QF, "2025-12-09T23:10:00+00:00")
    conn.commit()

    t = nsr.refresh("2025-12-01", get_json=lambda url, p: _board(p["dates"]),
                    connect=lambda: conn, now=NOW)

    assert t["error"] is None and t["failed"] == []
    assert _confirmed(conn, "0062500001") and _confirmed(conn, "0062500003")
    assert _row(conn, "nba_schedule", "0062500001", ("commence_time", "status_text")) == {
        "commence_time": "2025-12-09T23:00:00+00:00", "status_text": "Final"}
    assert _row(conn, "nba_schedule", "espn:401809839", ("game_id",)) is None
    assert _row(conn, "nba_schedule", "espn:401809837", ("game_id", "game_type", "is_neutral", "arena_city")) == {
        "game_id": SF, "game_type": "regular", "is_neutral": True, "arena_city": "Las Vegas"}
    assert _row(conn, "games", SF, ("data_source", "commence_time", "neutral_site")) == {
        "data_source": "espn_schedule", "commence_time": "2025-12-13T22:30:00+00:00", "neutral_site": 1}
    assert _row(conn, "games", QF, ("data_source", "commence_time")) == {
        "data_source": "live", "commence_time": "2025-12-09T23:10:00+00:00"}


PPD, PLAYED = "NBA_2026-12-22_TOR_WAS", "NBA_2026-12-21_BOS_NYK"
FLEX, CUP = "NBA_2027-03-10_LAL_BOS", "NBA_2026-12-08_LAL_BOS"


def test_the_plan_lands_as_written_and_a_played_game_keeps_its_status(conn):
    _sched(conn, "0022600400", PPD, "regular", "2026-12-23T00:00:00+00:00", status="7:00 pm ET")
    _sched(conn, "0022600401", PLAYED, "regular", "2026-12-22T00:30:00+00:00", status="Final", score=110)
    _sched(conn, "0022600900", FLEX, "regular", "2027-03-11T00:00:00+00:00")
    _game(conn, FLEX, "2027-03-11T02:40:00+00:00")                # the feed: flexed to 9:30pm ET
    _game(conn, CUP, "2026-12-09T00:10:00+00:00")                 # the feed has the Cup week game
    conn.commit()
    espn = [_espn(PPD, postponed=True), _espn(PLAYED, tip="2026-12-22T00:30:00+00:00", postponed=True),
            _espn(FLEX, tip="2027-03-11T02:30:00+00:00"), _espn(CUP, eid="9", tip="2026-12-09T00:00:00+00:00")]
    months = ["202612", "202703"]
    p = nsr.plan(espn, nsr.read_stored(conn, months),
                 nsr.read_games(conn, [r["game_id"] for r in espn]), months)
    nsr.apply(conn, p)
    conn.commit()

    assert _row(conn, "nba_schedule", "0022600400", ("status_text",)) == {"status_text": "Postponed"}
    assert _row(conn, "nba_schedule", "0022600401", ("status_text", "home_score")) == {
        "status_text": "Final", "home_score": 110}
    assert _row(conn, "nba_schedule", "0022600900", ("commence_time",)) == {
        "commence_time": "2027-03-11T02:30:00+00:00"}
    assert all(_confirmed(conn, n) for n in ("0022600400", "0022600401", "0022600900"))
    assert _row(conn, "nba_schedule", "espn:9", ("game_id",)) == {"game_id": CUP}
    assert _row(conn, "games", CUP, ("data_source", "commence_time")) == {
        "data_source": "live", "commence_time": "2026-12-09T00:10:00+00:00"}


def test_a_month_read_from_the_fallback_host_keeps_a_stored_status_and_tv(conn):
    """The core host's documents carry no status and no broadcasts inline; a
    month read from it must not blank what the scoreboard stored."""
    _sched(conn, "espn:401809837", SF, "regular", "2025-12-13T22:30:00+00:00", status="Final")
    conn.execute("UPDATE nba_schedule SET national_tv = 'ABC' WHERE nba_game_id = 'espn:401809837'")
    conn.commit()

    t = nsr.refresh("2025-12-01", get_json=_refused, core_json=_core(), connect=lambda: conn, now=NOW)

    assert t["error"] is None and "202512" in t["via_core"]
    assert _row(conn, "nba_schedule", "espn:401809837", ("status_text", "national_tv", "arena_city")) == {
        "status_text": "Final", "national_tv": "ABC", "arena_city": "Las Vegas"}
    assert _confirmed(conn, "espn:401809837")
    assert _row(conn, "nba_schedule", "espn:401809833", ("game_type", "status_text")) == {
        "game_type": "regular", "status_text": None}

"""The NCAAF first-half and team-total purchase end to end against a real
Postgres: which pulls a game holds, the ledger, the purchase and its rerun.

WHY A REAL DATABASE. The purchase decides which games to buy from
`odds.snapshot_at`, a TEXT column in mixed shapes that it casts and buckets in
SQL; it creates a locked-down ledger; it writes the prices and the ledger row
in one transaction; and its dry run reads through a read-only transaction a
database that has no ledger yet. None of that is a claim a stand-in can check.
No Odds API call: the feed is a function in place of the meter's one HTTP line.
Runs against LATEST_LINE_TEST_DSN or a throwaway cluster from tests/_pg.py, and
SKIPS only where neither exists.
"""
from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from data.anon_readable import API_ROLES  # noqa: E402
from data.db import DBConnection  # noqa: E402
from data.ingestors import cfbd_ingestor  # noqa: E402
from data.ingestors import ncaab_odds_history as ncaab  # noqa: E402
from data.ingestors import ncaaf_derivative_history as h  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402
from tests.test_ncaab_odds_history import Resp  # noqa: E402

# production's columns for the three tables this purchase reads and writes
# (data/supabase_schema.sql): odds.snapshot_at and created_at are TEXT, and
# odds.game_id is a foreign key, so a row under an id `games` lacks is refused.
GAMES_DDL = """
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL,
    game_date TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_score NUMERIC, away_score NUMERIC, commence_time TEXT)
"""
ODDS_DDL = """
CREATE TABLE odds (
    odds_id BIGSERIAL PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(game_id),
    sport TEXT NOT NULL, market TEXT NOT NULL, bookmaker TEXT NOT NULL,
    snapshot_type TEXT NOT NULL, snapshot_at TEXT NOT NULL,
    home_price NUMERIC, away_price NUMERIC, draw_price NUMERIC,
    spread_home NUMERIC, total_line NUMERIC, over_price NUMERIC, under_price NUMERIC,
    home_link TEXT, away_link TEXT, draw_link TEXT, over_link TEXT, under_link TEXT,
    home_sid TEXT, away_sid TEXT, draw_sid TEXT, over_sid TEXT, under_sid TEXT,
    source TEXT, created_at TEXT DEFAULT (NOW()::TEXT))
"""
QUOTA_DDL = """CREATE TABLE odds_api_quota (quota_date TEXT PRIMARY KEY, requests_used NUMERIC,
               requests_remaining NUMERIC, observed_at TEXT)"""
# the three columns the name resolution reads (cfbd_ingestor._load_schools)
TEAMS_DDL = "CREATE TABLE ncaaf_teams (school TEXT PRIMARY KEY, mascot TEXT, alt_names TEXT)"

NOON = "NCAAF_2025-08-30_texas_ohio-state"
NIGHT = "NCAAF_2025-08-30_lsu_clemson"            # the odds feed's row: holds the prices
NIGHT_CFBD = "NCAAF_2025-08-31_lsu_clemson"       # CFBD's row: holds the score
EARLY = "NCAAF_2025-08-30_iowa-state_kansas-state"
UNPRICED = "NCAAF_2025-08-30_idaho-state_unlv"
LISTING = [
    {"id": "e-noon", "commence_time": "2025-08-30T16:00:00Z",
     "home_team": "Ohio State Buckeyes", "away_team": "Texas Longhorns"},
    {"id": "e-night", "commence_time": "2025-08-31T01:00:00Z",       # listed the other way round
     "home_team": "LSU Tigers", "away_team": "Clemson Tigers"},
    {"id": "e-early", "commence_time": "2025-08-30T13:30:00Z",
     "home_team": "Kansas State Wildcats", "away_team": "Iowa State Cyclones"},
    {"id": "e-moose", "commence_time": "2025-08-30T19:00:00Z",
     "home_team": "Mystery Moose", "away_team": "Texas Longhorns"},
]


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaaf-derivative-pg-") as d:
        yield d


def _q(dsn, sql, params=None):
    raw = psycopg2.connect(dsn)
    try:
        cur = raw.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        raw.close()


def _markets(home, away):
    return [
        {"key": "h2h_h1", "outcomes": [{"name": home, "price": -160},
                                       {"name": away, "price": 135}]},
        {"key": "spreads_h1", "outcomes": [{"name": home, "price": -112, "point": -2.5},
                                           {"name": away, "price": -108, "point": 2.5}]},
        {"key": "totals_h1", "outcomes": [{"name": "Over", "price": -115, "point": 23.5},
                                          {"name": "Under", "price": -105, "point": 23.5}]},
        {"key": "team_totals", "outcomes": [
            {"name": "Over", "description": home, "price": -120, "point": 27.5},
            {"name": "Under", "description": home, "price": -100, "point": 27.5},
            {"name": "Over", "description": away, "price": -105, "point": 20.5},
            {"name": "Under", "description": away, "price": -115, "point": 20.5}]},
    ]


class Feed:
    """The meter's one HTTP line, answered here: the event list and each
    event's first-half lines and team totals at two books, with a balance."""

    def __init__(self):
        self.sent: list[tuple[str, dict]] = []
        self.balance = 11_900_000
        self.listing = list(LISTING)
        self._lock = threading.Lock()

    def __call__(self, meter, url, params):
        events = {e["id"]: e for e in self.listing}
        served = params["date"].replace(":00:00Z", ":55:38Z").replace("T14:", "T13:").replace(
            "T23:", "T22:")
        if url.endswith("/events"):
            r = Resp(body={"timestamp": served, "data": self.listing}, last="1")
        else:
            e = events[url.rsplit("/", 2)[-2]]
            r = Resp(body={"timestamp": served, "data": {"bookmakers": [
                {"key": b, "markets": _markets(e["home_team"], e["away_team"])}
                for b in ("fanduel", "draftkings")]}}, last="40")
        with self._lock:
            self.sent.append((url, dict(params)))
            self.balance -= int(r.headers["x-requests-last"])
            r.headers["x-requests-remaining"] = str(self.balance)
        return r


@pytest.fixture()
def world(dsn, monkeypatch):
    raw = psycopg2.connect(dsn)
    raw.autocommit = True
    cur = raw.cursor()
    for role in API_ROLES:
        cur.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    f"'{role}') THEN CREATE ROLE {role}; END IF; END $$")
    cur.execute("DROP TABLE IF EXISTS odds, games, odds_api_quota, ncaaf_derivative_fetches, "
                "ncaaf_teams")
    for ddl in (GAMES_DDL, ODDS_DDL, QUOTA_DDL, TEAMS_DDL):
        cur.execute(ddl)
    # the registry the repo's own name resolution reads: nothing is stubbed
    for school, mascot in (("Ohio State", "Buckeyes"), ("Ohio", "Bobcats"), ("Texas", "Longhorns"),
                           ("Clemson", "Tigers"), ("LSU", "Tigers"), ("Kansas State", "Wildcats"),
                           ("Kansas", "Jayhawks"), ("Iowa State", "Cyclones"), ("UNLV", "Rebels")):
        cur.execute("INSERT INTO ncaaf_teams VALUES (%s, %s, NULL)", (school, mascot))
    games = [
        (NOON, "2025-08-30", "Ohio State", "Texas", 14, 10, "2025-08-30T16:00:00Z"),
        (NIGHT, "2025-08-30", "Clemson", "LSU", None, None, "2025-08-31T01:00:00+00:00"),
        (NIGHT_CFBD, "2025-08-31", "Clemson", "LSU", 10, 17, "2025-08-31T01:00:00.000Z"),
        (EARLY, "2025-08-30", "Kansas State", "Iowa State", 21, 24, "2025-08-30T13:30:00Z"),
        (UNPRICED, "2025-08-30", "UNLV", "Idaho State", 38, 31, "2025-08-30T20:00:00Z"),
    ]
    for gid, day, home, away, hs, as_, kick in games:
        cur.execute("INSERT INTO games VALUES (%s,'NCAAF',2025,%s,%s,%s,%s,%s,%s)",
                    (gid, day, home, away, hs, as_, kick))
    # The stored full-game history, in every shape snapshot_at is stored in.
    stamps = [
        (NOON, "2025-08-30T13:55:38Z", "odds_api_historical"),          # the morning pull
        (NOON, "2025-08-30T13:54:10Z", "odds_api_historical"),
        (NOON, "2025-08-29T22:55:41Z", "odds_api_historical"),          # the evening pull
        (NIGHT, "2025-08-30T14:00:00Z", "odds_api_historical"),         # no last_update: the time asked
        (NIGHT, "2025-08-29T18:55:41-04:00", "odds_api_historical"),    # an offset: 22:55:41Z
        (NIGHT, "2025-08-30T13:00:00Z", "odds_api_historical"),         # an hour early: 13:00's pull
        (EARLY, "2025-08-30T13:55:38", "odds_api_historical"),          # naive: read as UTC
        (EARLY, "2025-08-29T22:55:41Z", "odds_api_historical"),
        (UNPRICED, "2025-08-30T13:55:38Z", None),                       # a live row: not a pull
        (UNPRICED, "2025-08-29T22:55:41Z", "odds_api_ncaab_derivative_close"),
    ]
    for gid, snap, source in stamps:
        cur.execute("INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, "
                    "snapshot_at, spread_home, source) VALUES (%s,'NCAAF','spreads','fanduel',"
                    "'open',%s,-3.5,%s)", (gid, snap, source))
    for i, day in enumerate(range(1, 9), start=1):                      # 60,000 a day
        cur.execute("INSERT INTO odds_api_quota VALUES (%s,%s,%s,%s)",
                    (f"2026-11-{day:02d}", 60_000 * i, 12_000_000 - 60_000 * i,
                     f"2026-11-{day:02d}T23:40:00Z"))
    raw.close()

    def connect():
        return DBConnection(psycopg2.connect(dsn), url=dsn)

    feed = Feed()
    monkeypatch.setattr(h, "get_connection", connect)
    monkeypatch.setattr(ncaab, "get_connection", connect)      # the dry run's read-only connection
    monkeypatch.setattr(cfbd_ingestor, "get_connection", connect)
    monkeypatch.setattr(h.PoolMeter, "_send", lambda self, url, params: feed(self, url, params))
    monkeypatch.setattr(h.config, "ODDS_API_KEY", "SECRET-TEST-KEY")
    cfbd_ingestor.reset_school_cache()
    yield {"dsn": dsn, "feed": feed, "connect": connect}
    cfbd_ingestor.reset_school_cache()         # no other test inherits this registry


def _t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


AM, PM = _t("2025-08-30T14:00:00Z"), _t("2025-08-29T23:00:00Z")


def test_the_pull_read_buckets_every_stored_stamp_shape_whatever_the_session_zone(world):
    conn = world["connect"]()
    try:
        # a session that is not on UTC, and not on a whole hour either
        conn.execute("SET TIME ZONE 'Asia/Kolkata'")
        got = h.stored_pulls(conn, [NOON, NIGHT, NIGHT_CFBD, EARLY, UNPRICED])
    finally:
        conn.close()
    assert got == {
        NOON: {AM: 2, PM: 1},
        # 14:00:00 is the 14:00 pull's; 13:00:00 is the pull before's
        NIGHT: {AM: 1, PM: 1, _t("2025-08-30T13:00:00Z"): 1},
        EARLY: {AM: 1, PM: 1},
    }                                              # the live row and the other source: no pull


def test_the_dry_run_reads_a_database_with_no_ledger_and_writes_nothing(world, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["x", "--read", "both"])
    h.main()
    out = capsys.readouterr().out
    am = out[out.index("read am"):out.index("read pm")]
    # the noon game and the night game (once); the 9:30am game is under way at 14:00 UTC
    assert "to buy: 2 games on 1 dates, at most 81 credits" in am
    assert next(line.split() for line in am.splitlines() if line.strip().startswith("2025")) == [
        "2025", "2", "1", "2", "1", "0"]
    assert "1 kick off within 5 minutes of it or before it" in am
    assert "to buy: 3 games on 1 dates, at most 121 credits" in out[out.index("read pm"):]
    # 8 daily readings 60,000 apart: the reserve is 7 days of it
    assert "re-run with --apply --max-credits 202 --floor 420000" in out
    assert "team registry: 9 schools in ncaaf_teams" in out and "WOULD REFUSE" not in out
    assert world["feed"].sent == []
    assert _q(world["dsn"], "SELECT to_regclass('public.ncaaf_derivative_fetches')") == [(None,)]
    assert _q(world["dsn"], "SELECT count(*) FROM odds WHERE source LIKE %s",
              ("odds_api_ncaaf%",)) == [(0,)]


def test_the_purchase_stores_each_game_once_and_a_rerun_buys_nothing(world, monkeypatch, capsys):
    dsn, feed = world["dsn"], world["feed"]
    monkeypatch.setattr("sys.argv", ["x", "--read", "both", "--apply", "--max-credits", "1000",
                                     "--floor", "300000"])
    h.main()
    out = capsys.readouterr().out
    # one list a date and read, then the games: 2 in the morning, 3 the evening before
    lists = sorted(p["date"] for u, p in feed.sent if u.endswith("/events"))
    assert lists == ["2025-08-29T23:00:00Z", "2025-08-30T14:00:00Z"]
    bought = sorted((u.rsplit("/", 2)[-2], p["date"]) for u, p in feed.sent if "/events/" in u)
    assert bought == [("e-early", "2025-08-29T23:00:00Z"), ("e-night", "2025-08-29T23:00:00Z"),
                      ("e-night", "2025-08-30T14:00:00Z"), ("e-noon", "2025-08-29T23:00:00Z"),
                      ("e-noon", "2025-08-30T14:00:00Z")]
    assert feed.balance == 11_900_000 - 2 * 1 - 5 * 40         # two lists, five games
    assert "ceiling 202 (the smaller of --max-credits 1,000 and the plan's most 202)" in out
    assert "floor 420,000 (the larger of --floor 300,000 and the measured reserve 420,000)" in out

    rows = _q(dsn, "SELECT source, game_id, market, bookmaker, snapshot_type, snapshot_at, "
                   "spread_home, total_line, home_price, created_at FROM odds "
                   "WHERE source LIKE 'odds_api_ncaaf_derivative_%' ORDER BY odds_id")
    by_source = {}
    for r in rows:
        by_source.setdefault(r[0], []).append(r)
    assert {s: len(v) for s, v in by_source.items()} == {
        "odds_api_ncaaf_derivative_am": 2 * 2 * 5, "odds_api_ncaaf_derivative_pm": 3 * 2 * 5}
    am = by_source["odds_api_ncaaf_derivative_am"]
    assert {r[1] for r in am} == {NOON, NIGHT}                 # never CFBD's row
    assert {r[2] for r in am} == {"h2h_h1", "spreads_h1", "totals_h1", "team_totals_home",
                                  "team_totals_away"}
    assert {r[4] for r in am} == {"open"} and {r[5] for r in am} == {"2025-08-30T13:55:38Z"}
    assert all(r[9] for r in am)                               # created_at: the table's default
    night = {r[2]: r for r in am if r[1] == NIGHT and r[3] == "fanduel"}
    assert float(night["spreads_h1"][6]) == 2.5                # Clemson, our home, the feed's away
    assert float(night["team_totals_home"][7]) == 20.5 and float(night["h2h_h1"][8]) == 135

    ledger = _q(dsn, "SELECT game_id, read_slot, requested_at, served_at, event_id, credits, "
                     "rows_stored, status FROM ncaaf_derivative_fetches ORDER BY read_slot, game_id")
    assert [(r[0], r[1], r[5], r[6], r[7]) for r in ledger] == [
        (NIGHT, "am", 40, 10, "stored"), (NOON, "am", 40, 10, "stored"),
        (EARLY, "pm", 40, 10, "stored"), (NIGHT, "pm", 40, 10, "stored"),
        (NOON, "pm", 40, 10, "stored")]
    noon_am = next(r for r in ledger if r[0] == NOON and r[1] == "am")
    assert noon_am[2].astimezone(timezone.utc) == AM
    assert noon_am[3].astimezone(timezone.utc) == _t("2025-08-30T13:55:38Z")
    assert noon_am[4] == "e-noon"

    # the ledger is worker-only: RLS on, nothing granted to the app's roles
    assert _q(dsn, "SELECT relrowsecurity FROM pg_class WHERE relname = "
                   "'ncaaf_derivative_fetches'") == [(True,)]
    for role in API_ROLES:
        assert _q(dsn, "SELECT has_table_privilege(%s, 'ncaaf_derivative_fetches', "
                       "'SELECT,INSERT,UPDATE,DELETE')", (role,)) == [(False,)]

    # read back from `odds`: both books, every market, on each bought game
    table = out[out.index("coverage, am"):]
    assert "2 of 2 planned games bought; 2 hold a quote" in table
    assert "3 of 3 planned games bought; 3 hold a quote" in table

    # ── again: the ledger holds everything, so not one call ──
    calls, stored = len(feed.sent), len(rows)
    h.main()
    again = capsys.readouterr().out
    assert len(feed.sent) == calls and "nothing to buy" in again
    assert _q(dsn, "SELECT count(*) FROM odds WHERE source LIKE 'odds_api_ncaaf_derivative_%'") == [
        (stored,)]
    assert _q(dsn, "SELECT count(*) FROM ncaaf_derivative_fetches") == [(5,)]


def test_a_game_stored_under_the_feed_s_own_name_is_bought_once_under_that_id(world, monkeypatch,
                                                                              capsys):
    """The stored history was written before the registry held FCS schools:
    Furman at Clemson sits under 'Furman Paladins', beside CFBD's row for the
    same game under 'Furman', which has the final. With the registry's own
    resolution: one game, with a final, bought under the id with the prices."""
    raw_id, cfbd_id = "NCAAF_2025-09-06_furman-paladins_clemson", "NCAAF_2025-09-06_furman_clemson"
    raw = psycopg2.connect(world["dsn"])
    raw.autocommit = True
    cur = raw.cursor()
    cur.execute("INSERT INTO ncaaf_teams VALUES ('Furman', 'Paladins', NULL)")
    cur.execute("INSERT INTO games VALUES (%s,'NCAAF',2025,'2025-09-06','Clemson',"
                "'Furman Paladins',NULL,NULL,'2025-09-06T16:00:00Z')", (raw_id,))
    cur.execute("INSERT INTO games VALUES (%s,'NCAAF',2025,'2025-09-06','Clemson','Furman',45,10,"
                "'2025-09-06T16:00:00.000Z')", (cfbd_id,))
    cur.execute("INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at, "
                "spread_home, source) VALUES (%s,'NCAAF','spreads','fanduel','open',"
                "'2025-09-06T13:55:38Z',-38.5,'odds_api_historical')", (raw_id,))
    raw.close()
    world["feed"].listing.append({"id": "e-furman", "commence_time": "2025-09-06T16:00:00Z",
                                  "home_team": "Clemson Tigers", "away_team": "Furman Paladins"})
    monkeypatch.setattr("sys.argv", ["x", "--read", "am", "--apply", "--max-credits", "1000",
                                     "--floor", "300000"])
    h.main()
    out = capsys.readouterr().out
    # three games on two dates: the two of 08-30 and this one, all three with a final
    assert next(line.split() for line in out.splitlines() if line.strip().startswith("2025")) == [
        "2025", "3", "2", "3", "2", "0"]
    bought = sorted(u.rsplit("/", 2)[-2] for u, p in world["feed"].sent if "/events/" in u)
    assert bought == ["e-furman", "e-night", "e-noon"]
    rows = _q(world["dsn"], "SELECT DISTINCT game_id FROM odds WHERE source = %s AND game_id LIKE %s",
              ("odds_api_ncaaf_derivative_am", "%furman%"))
    assert rows == [(raw_id,)]                                 # never CFBD's id
    assert _q(world["dsn"], "SELECT game_id, status FROM ncaaf_derivative_fetches WHERE game_id "
                            "LIKE %s", ("%furman%",)) == [(raw_id, "stored")]


def test_a_purchase_with_no_team_registry_makes_no_call(world, monkeypatch, capsys):
    """An empty registry, or none at all: the purchase refuses before its
    first list, and the failed read is not left cached for the next job."""
    raw = psycopg2.connect(world["dsn"])
    raw.autocommit = True
    raw.cursor().execute("DELETE FROM ncaaf_teams")
    argv = ["x", "--read", "both", "--apply", "--max-credits", "1000", "--floor", "300000"]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit, match="refusing to start: ncaaf_teams is empty or unreadable"):
        h.main()
    raw.cursor().execute("DROP TABLE ncaaf_teams")
    raw.close()
    with pytest.raises(SystemExit, match="refusing to start: ncaaf_teams is empty or unreadable"):
        h.main()
    assert world["feed"].sent == [] and cfbd_ingestor._SCHOOL_CACHE is None
    assert _q(world["dsn"], "SELECT count(*) FROM odds WHERE source LIKE %s",
              ("odds_api_ncaaf%",)) == [(0,)]
    monkeypatch.setattr("sys.argv", ["x", "--read", "am"])
    h.main()                                    # the dry run still prints the plan, and says so
    out = capsys.readouterr().out
    assert "WOULD REFUSE: ncaaf_teams is empty or unreadable" in out and "to buy: 2 games" in out
    # the plan was printed from the names as stored: the registry was not asked again, so no
    # empty read is left cached for whatever runs next in this process
    assert cfbd_ingestor._SCHOOL_CACHE is None


def test_a_held_ledger_row_is_never_rewritten_and_an_unheld_one_is(world):
    conn = world["connect"]()
    try:
        h.ensure_ledger(conn)
        game = h.Planned(game_id=NOON, season=2025, eastern_date="2025-08-30", home="Ohio State",
                         away="Texas", kick=_t("2025-08-30T16:00:00Z"), read="am", instant=AM,
                         scored=True, pull_rows=2)
        h._ledger_write(conn, game, served=None, event_id=None, credits=0, rows=0,
                        status=h.UNLISTED)
        conn.commit()
        assert h.ledger_held(conn, [NOON], "am") == set()            # not listed: still owed
        h._ledger_write(conn, game, served=AM, event_id="e-noon", credits=40, rows=10,
                        status=h.STORED)
        conn.commit()
        assert h.ledger_held(conn, [NOON], "am") == {NOON}
        assert h.ledger_held(conn, [NOON], "pm") == set()            # the other read is its own
        h._ledger_write(conn, game, served=None, event_id="e-noon", credits=0, rows=0,
                        status=h.ERROR)                              # a later failure
        conn.commit()
    finally:
        conn.close()
    assert _q(world["dsn"], "SELECT status, credits, rows_stored, event_id FROM "
                            "ncaaf_derivative_fetches") == [("stored", 40, 10, "e-noon")]

"""An NBA bet whose only start is the odds feed's has no close.

The feed's start ran 2.3 to 20.2 minutes behind the league's on all 107 games it wrote 2026-10-20..11-02
(production, games joined to nba_schedule), and refresh passes store in-play rows typed 'open':
NBA_2026-10-27_SAC_SAS had 'open' fetches at 00:00:19 and 00:10:16 with its tip at 00:00:00 and the
feed's start at 00:15:00. So a close bounded on the feed's start can be an in-play price, and closing-line
value is published.

Two writers, and both must hold it. The Python capture runs from settle, and the recompute in
data/migrations/clv_standard_v2_2026_10_14.sql runs on every pass over any bet not yet stamped. A
guard in one is undone by the other, so the Postgres tests run the real capture and the real file.
Needs a scratch Postgres (tests/_pg.py) for those; the rest need nothing.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

psycopg2 = pytest.importorskip("psycopg2")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.nba_prop_market as mk  # noqa: E402
from data.db import DBConnection  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402
from tracking.clv_math import CLV_METHOD_STANDARD  # noqa: E402

MIGRATION = ROOT / "data" / "migrations" / "clv_standard_v2_2026_10_14.sql"
ET = ZoneInfo("America/New_York")
T = datetime(2026, 12, 12, 1, 0, tzinfo=timezone.utc)
_at = lambda minutes: (T + timedelta(minutes=minutes)).isoformat()  # noqa: E731


# ── the two starts ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("sched,feed,tip,source", [
    (0, 0, 0, "schedule"),
    (0, 20, 0, "schedule"),        # the feed's ordinary lag
    (0, 30, 0, "schedule"),        # the edge of it
    (0, 31, 31, "feed"),           # past it: ESPN is the one read as wrong
    (0, 300, 300, "feed"),         # the file's own case, ESPN five hours early
    (None, 0, 0, "feed"),          # no ESPN tip
    (0, None, 0, "schedule"),
    (45, 0, 0, "feed"),            # the feed earlier: the earlier still holds
])
def test_the_postseason_tip_and_where_it_came_from(sched, feed, tip, source):
    s = None if sched is None else _at(sched)
    f = None if feed is None else _at(feed)
    assert mk.postseason_tip(s, f) == (T + timedelta(minutes=tip), source)


def test_no_start_at_all_is_no_tip():
    assert mk.postseason_tip(None, None) == (None, None)


@pytest.mark.parametrize("sched,feed,apart", [(0, 30, False), (0, 31, True), (31, 0, True), (None, 0, False)])
def test_the_two_starts_disagree_past_the_feeds_lag(sched, feed, apart):
    assert mk.starts_disagree(None if sched is None else _at(sched), _at(feed)) is apart


def test_the_gap_is_the_feeds_lag():
    import data.ingestors.nba_schedule_refresh as nsr
    assert timedelta(minutes=mk.START_GAP_MIN) == nsr.FEED_LAG[1]


# ── which start bounds a close ───────────────────────────────────────────────

GID = "NBA_2026-12-11_NYK_OKC"
FLIPPED = "NBA_2026-12-11_OKC_NYK"


@pytest.mark.parametrize("schedule,feed,want", [
    ({}, 15, None),                                     # the schedule does not list it
    ({GID: (None, "cup_final")}, 15, None),             # listed, with no tip
    ({GID: (_at(0), "cup_final")}, 15, 0),              # its own row
    ({FLIPPED: (_at(0), "cup_final")}, 15, 0),          # the row the other way round
    ({GID: (_at(-300), "playoff")}, 15, None),          # ESPN far early: no start to trust
    ({GID: (_at(-300), "regular")}, 15, -300),          # a league row is the league's tip
    ({GID: (_at(30), "playoff")}, 0, 30),               # the feed earlier: the caller takes the earlier
])
def test_the_start_a_close_can_be_bounded_on(schedule, feed, want):
    got = pt._nba_league_tip(GID, _at(feed), schedule)
    assert got == (None if want is None else T + timedelta(minutes=want))


def test_the_other_way_round_is_home_and_away_swapped():
    assert pt._reversed_nba_id(GID) == FLIPPED
    assert pt._reversed_nba_id("not-an-id") == "not-an-id"


# ── on a real Postgres: the real capture and the real recompute ──────────────

@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("nba-clv-feed-start-") as d:
        yield d


SCHEMA = """
DROP VIEW IF EXISTS v_public_track_record;
DROP TABLE IF EXISTS picks; DROP TABLE IF EXISTS games; DROP TABLE IF EXISTS nba_schedule;
DROP TABLE IF EXISTS player_prop_odds; DROP TABLE IF EXISTS odds;
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL, game_date TEXT NOT NULL,
    home_team TEXT NOT NULL, away_team TEXT NOT NULL, home_score NUMERIC, away_score NUMERIC,
    commence_time TEXT);
CREATE TABLE nba_schedule (
    nba_game_id TEXT PRIMARY KEY, game_id TEXT, season INTEGER NOT NULL, game_type TEXT NOT NULL,
    game_date TEXT NOT NULL, commence_time TEXT, home_team TEXT NOT NULL, away_team TEXT NOT NULL);
CREATE TABLE picks (
    pick_id SERIAL PRIMARY KEY, game_id TEXT REFERENCES games(game_id), model_id TEXT NOT NULL,
    game_date TEXT NOT NULL, game_time TEXT, pick_side TEXT, pick_label TEXT, scored_line DOUBLE PRECISION,
    signal_type TEXT NOT NULL, result TEXT, is_live BOOLEAN DEFAULT FALSE, dk_odds NUMERIC,
    decision_odds NUMERIC, decision_book TEXT, prop_market TEXT, created_at TEXT,
    closing_dk_odds NUMERIC, closing_line NUMERIC, clv_pct NUMERIC, line_clv_pts NUMERIC,
    clv_beat_close BOOLEAN, clv_captured_at TEXT, clv_method TEXT, clv_close_book TEXT, clv_bet_book TEXT,
    clv_pp NUMERIC, market_clv_pct NUMERIC, market_clv_pp NUMERIC, market_clv_method TEXT,
    pinnacle_close_odds NUMERIC);
CREATE TABLE player_prop_odds (
    game_id TEXT, player_name TEXT, market TEXT, bookmaker TEXT, line DOUBLE PRECISION,
    over_price DOUBLE PRECISION, under_price DOUBLE PRECISION, snapshot_at TEXT, snapshot_type TEXT);
CREATE TABLE odds (
    game_id TEXT, market TEXT, bookmaker TEXT, snapshot_at TEXT, snapshot_type TEXT,
    home_price DOUBLE PRECISION, away_price DOUBLE PRECISION, draw_price DOUBLE PRECISION,
    spread_home DOUBLE PRECISION, total_line DOUBLE PRECISION, over_price DOUBLE PRECISION,
    under_price DOUBLE PRECISION);
CREATE VIEW v_public_track_record AS SELECT 1 AS clv_game_settled;
"""


@pytest.fixture
def conn(dsn):
    raw = psycopg2.connect(dsn)
    with raw.cursor() as cur:
        cur.execute(SCHEMA)
    raw.commit()
    c = DBConnection(raw)
    yield c
    raw.close()


# The price before the tip, and the in-play price the feed's start would let through.
BEFORE_TIP, IN_PLAY = -110.0, 300.0


class World:
    """One game: the real tip, the feed's start 15 minutes later, a quote before the tip and an
    in-play row typed 'open' between the two."""

    def __init__(self, conn, days_ago=0.1, teams=("NYK", "OKC")):
        self.conn = conn
        self.tip = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=3)
        self.day = self.tip.astimezone(ET).date().isoformat()
        self.away, self.home = teams
        self.gid = f"NBA_{self.day}_{self.away}_{self.home}"
        self.espn_flipped = f"NBA_{self.day}_{self.home}_{self.away}"
        self.feed_start = self.at(15)
        conn.execute("""INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, commence_time)
                        VALUES (%s, 'NBA', 2027, %s, %s, %s, %s)""",
                     (self.gid, self.day, self.home, self.away, self.feed_start))
        for book in ("fanduel", "pinnacle"):
            for at, price in ((-20, BEFORE_TIP), (5, IN_PLAY)):
                conn.execute("""INSERT INTO player_prop_odds (game_id, player_name, market, bookmaker, line,
                                    over_price, under_price, snapshot_at, snapshot_type)
                                VALUES (%s, 'Stephen Curry', 'player_points', %s, 24.5, -110, %s, %s, 'open')""",
                             (self.gid, book, price, self.at(at)))

    def at(self, minutes):
        return (self.tip + timedelta(minutes=minutes)).isoformat()

    def listed(self, gid=None, kind="cup_final", tip=None):
        gid = gid or self.gid
        home, away = (self.home, self.away) if gid == self.gid else (self.away, self.home)
        self.conn.execute("""INSERT INTO nba_schedule (nba_game_id, game_id, season, game_type, game_date,
                                 commence_time, home_team, away_team)
                             VALUES (%s, %s, 2027, %s, %s, %s, %s, %s)""",
                          (f"espn:{gid}", gid, kind, self.day, tip if tip is not None else self.at(0), home, away))

    def bet(self, game_time=None):
        self.conn.execute("""INSERT INTO picks (game_id, model_id, game_date, game_time, pick_side, pick_label,
                                 scored_line, signal_type, decision_odds, decision_book, prop_market, created_at)
                             VALUES (%s, 'nba_prop_market', %s, %s, 'under', 'Stephen Curry Under 24.5 Pts', 24.5,
                                     'BET', 105, 'fanduel', 'player_points', %s)""",
                          (self.gid, self.day, game_time or self.feed_start, self.at(-55)))
        self.conn.commit()

    def capture(self):
        n = pt._capture_clv(self.conn, self.day, datetime.now(timezone.utc).isoformat())
        self.conn.commit()
        return n

    def recompute(self):
        with self.conn._conn.cursor() as cur:
            cur.execute(MIGRATION.read_text(encoding="utf-8"))
        self.conn._conn.commit()

    def row(self):
        return dict(zip(("close", "method", "clv", "book"), self.conn.execute(
            "SELECT closing_dk_odds, clv_method, clv_pct, clv_bet_book FROM picks WHERE game_id = %s",
            (self.gid,)).fetchone()))


def _close(world):
    v = world.row()["close"]
    return None if v is None else float(v)


def test_the_world_would_take_the_in_play_price_on_the_feeds_start(conn):
    """The control: the read itself, bounded on the feed's start, returns the in-play row. Without
    this, every test below could pass because the in-play row was never reachable."""
    w = World(conn)
    got = pt._closing_prop_odds(conn, w.gid, "Stephen Curry", "player_points", w.feed_start, bookmaker="fanduel")
    assert got["under_price"] == IN_PLAY
    got = pt._closing_prop_odds(conn, w.gid, "Stephen Curry", "player_points", w.at(0), bookmaker="fanduel")
    assert got["under_price"] == BEFORE_TIP


@pytest.mark.parametrize("writer", ["capture", "recompute"])
def test_a_game_the_schedule_holds_the_other_way_round_closes_at_espns_tip(conn, writer):
    w = World(conn)
    w.listed(w.espn_flipped)
    w.bet(game_time=w.at(0))
    getattr(w, writer)()
    assert _close(w) == BEFORE_TIP and w.row()["method"] == CLV_METHOD_STANDARD


@pytest.mark.parametrize("writer", ["capture", "recompute"])
def test_a_bet_written_before_the_schedule_listed_its_game_closes_at_the_tip_it_now_has(conn, writer):
    """Its game_time is the feed's, because that was the only start then."""
    w = World(conn)
    w.listed()
    w.bet()
    getattr(w, writer)()
    assert _close(w) == BEFORE_TIP and w.row()["method"] == CLV_METHOD_STANDARD


@pytest.mark.parametrize("writer", ["capture", "recompute"])
def test_a_game_with_no_league_tip_keeps_its_closing_columns_empty(conn, writer):
    w = World(conn)
    w.bet()
    getattr(w, writer)()
    assert w.row() == {"close": None, "method": None, "clv": None, "book": None}


@pytest.mark.parametrize("espn_far_early", [False, True])
def test_the_recompute_leaves_it_empty_when_other_work_makes_it_run(conn, espn_far_early):
    """In production the recompute nearly always has another bet to measure, so it runs, and its own row
    filter is what keeps this bet out. Alone in the table, the bet never reaches that filter: the check that
    decides whether to run at all stops first, so the single-bet tests pass with the row filter removed.
    Both halves of the filter: no league tip, and ESPN's postseason start far before the feed's."""
    w = World(conn)
    if espn_far_early:
        w.listed(tip=w.at(-300))
        for book in ("fanduel", "pinnacle"):
            conn.execute("""INSERT INTO player_prop_odds (game_id, player_name, market, bookmaker, line, over_price,
                                under_price, snapshot_at, snapshot_type)
                            VALUES (%s, 'Stephen Curry', 'player_points', %s, 24.5, -110, -200, %s, 'open')""",
                         (w.gid, book, w.at(-310)))
    w.bet()
    other = World(conn, teams=("BOS", "MIA"))
    other.listed(kind="regular")
    other.bet(game_time=other.at(0))
    w.recompute()
    assert _close(other) == BEFORE_TIP and other.row()["method"] == CLV_METHOD_STANDARD, "the recompute did not run"
    assert w.row() == {"close": None, "method": None, "clv": None, "book": None}


@pytest.mark.parametrize("writer", ["capture", "recompute"])
def test_a_postseason_start_far_before_the_feeds_bounds_nothing(conn, writer):
    """Read as ESPN's error, so the window ran on the feed's start, and that is no bound either. The
    quote before ESPN's false start is what a close read against it would take."""
    w = World(conn)
    w.listed(tip=w.at(-300))
    for book in ("fanduel", "pinnacle"):
        conn.execute("""INSERT INTO player_prop_odds (game_id, player_name, market, bookmaker, line, over_price,
                            under_price, snapshot_at, snapshot_type)
                        VALUES (%s, 'Stephen Curry', 'player_points', %s, 24.5, -110, -200, %s, 'open')""",
                     (w.gid, book, w.at(-310)))
    w.bet()
    getattr(w, writer)()
    assert w.row() == {"close": None, "method": None, "clv": None, "book": None}


@pytest.mark.parametrize("writer", ["capture", "recompute"])
def test_a_regular_season_game_on_its_league_row_closes_as_it_always_has(conn, writer):
    w = World(conn)
    w.listed(kind="regular")
    w.bet(game_time=w.at(0))
    getattr(w, writer)()
    assert _close(w) == BEFORE_TIP and w.row()["method"] == CLV_METHOD_STANDARD


def test_the_empty_bet_is_measured_if_the_schedule_row_arrives_in_time(conn):
    w = World(conn)
    w.bet()
    w.capture()
    w.recompute()
    assert w.row()["method"] is None
    w.listed()
    conn.commit()
    w.capture()
    assert _close(w) == BEFORE_TIP


def test_the_empty_bet_is_stamped_once_no_schedule_row_is_coming_so_it_leaves_the_backfills_queue(conn):
    """The backfill walks the oldest dates holding a bet with no stamp, so a date that can never be
    measured would hold a place at the head of its queue (.claude/rules/data-integrity.md)."""
    w = World(conn, days_ago=pt._NBA_NO_TIP_WAIT_DAYS + 1)
    w.bet()
    assert w.capture() == 1
    assert w.row() == {"close": None, "method": CLV_METHOD_STANDARD, "clv": None, "book": "fanduel"}


def test_the_recompute_leaves_every_other_sport_alone(conn):
    """No schedule table stands behind them, and their rows must not need one."""
    day = (datetime.now(timezone.utc) - timedelta(hours=3)).astimezone(ET).date().isoformat()
    gid = f"NHL_{day}_BOS_MTL"
    start = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    conn.execute("""INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, commence_time)
                    VALUES (%s, 'NHL', 2027, %s, 'MTL', 'BOS', %s)""", (gid, day, start))
    conn.execute("""INSERT INTO player_prop_odds (game_id, player_name, market, bookmaker, line, over_price,
                        under_price, snapshot_at, snapshot_type)
                    VALUES (%s, 'Stephen Curry', 'player_shots_on_goal', 'fanduel', 2.5, -110, -110, %s, 'open')""",
                 (gid, (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()))
    conn.execute("""INSERT INTO picks (game_id, model_id, game_date, game_time, pick_side, pick_label, scored_line,
                        signal_type, decision_odds, decision_book, prop_market, created_at)
                    VALUES (%s, 'nba_prop_market', %s, %s, 'under', 'Stephen Curry Under 2.5 Shots', 2.5, 'BET',
                            105, 'fanduel', 'player_shots_on_goal', %s)""",
                 (gid, day, start, (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()))
    conn.commit()
    with conn._conn.cursor() as cur:
        cur.execute(MIGRATION.read_text(encoding="utf-8"))
    conn._conn.commit()
    assert conn.execute("SELECT clv_method FROM picks WHERE game_id = %s", (gid,)).fetchone()[0] == CLV_METHOD_STANDARD

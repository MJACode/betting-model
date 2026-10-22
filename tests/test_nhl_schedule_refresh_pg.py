"""The NHL schedule refresh's writes, and the readers it must not move, on a real Postgres.

tests/test_nhl_schedule_refresh.py pins the plan and records the SQL a run
sends; nothing there runs it. These run the refresh, the odds feed's own games
upsert (odds_ingestor._upsert_games) and the readers' SQL through the worker's
connection wrapper (data.db.DBConnection) against `games` as production
declares it (TEXT dates and starts, data_source), with three of the 22 tables
that hold a foreign key to it. So a row the feed reaches stays the feed's, a
guard that is lost shows up as a row that changed, and a row only the refresh
wrote is shown to stay off every list that bets or buys.

Needs a scratch Postgres (tests/_pg.py: LATEST_LINE_TEST_DSN, initdb on PATH,
or the embedded-postgres package in requirements-test.txt); skips without one.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

import data.ingestors.nhl_schedule_refresh as nsr  # noqa: E402
from data.db import DBConnection  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402
from tests.test_nhl_schedule_refresh import BEFORE, NOW, TEN, WEEK1, _game, _week_from  # noqa: E402


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("nhl-schedule-pg-") as d:
        yield d


SCHEMA = """
DROP TABLE IF EXISTS nhl_goalie_stats; DROP TABLE IF EXISTS picks; DROP TABLE IF EXISTS odds;
DROP TABLE IF EXISTS games;
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL, game_date TEXT NOT NULL,
    home_team TEXT NOT NULL, away_team TEXT NOT NULL, home_score NUMERIC, away_score NUMERIC,
    data_source TEXT, created_at TEXT DEFAULT (now())::text, updated_at TEXT DEFAULT (now())::text,
    commence_time TEXT, neutral_site INTEGER, first_pitch_at TEXT);
CREATE TABLE odds (id SERIAL PRIMARY KEY, game_id TEXT REFERENCES games(game_id), bookmaker TEXT,
    snapshot_at TEXT);
CREATE TABLE picks (id SERIAL PRIMARY KEY, game_id TEXT REFERENCES games(game_id));
CREATE TABLE nhl_goalie_stats (id SERIAL PRIMARY KEY, game_id TEXT REFERENCES games(game_id),
    team TEXT);
"""
OLD = "2026-10-01 00:00:00+00"


@pytest.fixture
def conn(dsn):
    raw = psycopg2.connect(dsn)
    with raw.cursor() as cur:
        cur.execute(SCHEMA)
    raw.commit()
    c = DBConnection(raw)
    yield c
    raw.close()


def _get(pages):
    return lambda url: pages[url.rsplit("/", 1)[1]]


ONE_WEEK = _get({"2026-10-15": BEFORE, "2026-10-22": dict(WEEK1, nextStartDate=None)})


def _refresh(conn, get=ONE_WEEK, now=NOW):
    return nsr.refresh("2026-10-22", get_json=get, connect=lambda: conn, now=now, sleep=0)


def _row(conn, gid, cols=("data_source", "commence_time", "home_score")):
    got = conn.execute(f"SELECT {', '.join(cols)} FROM games WHERE game_id = %s", (gid,)).fetchone()
    return None if got is None else dict(zip(cols, got))


def _count(conn):
    return conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]


def _put(conn, gid, source, start, score=None, updated=OLD):
    _, day, away, home = gid.split("_")
    conn.execute("""INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
                    home_score, data_source, commence_time, updated_at)
                    VALUES (%s, 'NHL', 2027, %s, %s, %s, %s, %s, %s, %s)""",
                 (gid, day, home, away, score, source, start, updated))
    conn.commit()


def test_the_feeds_later_upsert_lands_on_the_same_row_and_the_row_is_then_the_feeds(conn):
    from data.ingestors.odds_ingestor import _upsert_games
    t = _refresh(conn)
    assert nsr.step_ok(t) and t["insert"] == 27 and _count(conn) == 27
    gid = "NHL_2026-10-24_ANA_PHI"
    assert _row(conn, gid) == {"data_source": "nhl_schedule", "commence_time": "2026-10-24T17:00:00Z",
                               "home_score": None}
    # The odds feed lists the game: its own row shape, its own (books') start.
    _upsert_games(conn, [{"game_id": gid, "sport": "NHL", "season": 2027, "game_date": "2026-10-24",
                          "home_team": "PHI", "away_team": "ANA",
                          "commence_time": "2026-10-24T17:10:00+00:00", "data_source": "live"}])
    conn.commit()
    assert _count(conn) == 27
    assert _row(conn, gid)["data_source"] == "live"
    before = _row(conn, gid, ("commence_time", "updated_at"))
    t = _refresh(conn)
    # Nothing inserted twice, the feed's start survives, the feed's row is not
    # even confirmed.
    assert t["insert"] == 0 and t["confirm"] == 26 and _count(conn) == 27
    assert _row(conn, gid, ("commence_time", "updated_at")) == before
    assert before["commence_time"] == "2026-10-24T17:10:00+00:00"


def test_a_second_run_changes_nothing_but_the_confirmation(conn):
    _refresh(conn)
    rows = conn.execute("SELECT game_id, commence_time, data_source FROM games ORDER BY 1").fetchall()
    t = _refresh(conn)
    assert (t["insert"], t["times"], t["orphans"]) == (0, 0, 0) and t["confirm"] == 27
    assert conn.execute("SELECT game_id, commence_time, data_source FROM games ORDER BY 1").fetchall() == rows


def test_a_moved_start_moves_only_the_refreshs_own_unplayed_row(conn):
    _put(conn, "NHL_2026-10-24_ANA_PHI", "nhl_schedule", "2026-10-24T23:00:00Z")
    _put(conn, "NHL_2026-10-24_LAK_NJD", "live", "2026-10-24T22:10:00+00:00")       # the feed's
    _put(conn, "NHL_2026-10-25_FLA_CHI", "nhl_schedule", "2026-10-25T21:00:00Z", score=4)
    t = _refresh(conn)
    assert t["times"] == 1
    assert _row(conn, "NHL_2026-10-24_ANA_PHI")["commence_time"] == "2026-10-24T17:00:00Z"
    assert _row(conn, "NHL_2026-10-24_LAK_NJD")["commence_time"] == "2026-10-24T22:10:00+00:00"
    assert _row(conn, "NHL_2026-10-25_FLA_CHI") == {
        "data_source": "nhl_schedule", "commence_time": "2026-10-25T21:00:00Z", "home_score": 4}


def test_the_confirmation_is_the_refreshs_one_signal(conn):
    _put(conn, "NHL_2026-10-24_ANA_PHI", "nhl_schedule", "2026-10-24T17:00:00Z")
    _refresh(conn)
    stamp = conn.execute("SELECT updated_at FROM games WHERE game_id = 'NHL_2026-10-24_ANA_PHI'").fetchone()[0]
    assert stamp > OLD


def test_an_orphan_is_removed_unless_something_references_it(conn):
    """A game the API no longer lists on its date: the refresh's own future row
    goes, unless any other table holds its id. The rest of the plan lands."""
    for gid in ("NHL_2026-10-27_ANA_BUF", "NHL_2026-10-27_ANA_DET", "NHL_2026-10-27_ANA_SEA",
                "NHL_2026-10-28_ANA_SEA"):
        _put(conn, gid, "nhl_schedule", f"{gid.split('_')[1]}T23:00:00Z")
    _put(conn, "NHL_2026-10-28_ANA_BUF", "live", "2026-10-28T23:10:00+00:00")       # the feed's
    conn.execute("INSERT INTO odds (game_id, bookmaker) VALUES ('NHL_2026-10-27_ANA_DET', 'draftkings')")
    conn.execute("INSERT INTO nhl_goalie_stats (game_id, team) VALUES ('NHL_2026-10-27_ANA_SEA', 'SEA')")
    conn.commit()
    t = _refresh(conn)
    assert nsr.step_ok(t)
    assert t["orphans"] == 4 and t["orphans_deleted"] == 2 and t["orphans_kept"] == 2
    assert _row(conn, "NHL_2026-10-27_ANA_BUF") is None
    assert _row(conn, "NHL_2026-10-28_ANA_SEA") is None
    assert _row(conn, "NHL_2026-10-27_ANA_DET") is not None           # has odds
    assert _row(conn, "NHL_2026-10-27_ANA_SEA") is not None           # a foreign key holds it
    assert _row(conn, "NHL_2026-10-28_ANA_BUF")["data_source"] == "live"
    assert _count(conn) == 27 + 5 - 2                                  # the week inserted all the same


def test_the_readers_that_bet_or_buy_never_see_a_row_only_the_refresh_wrote(conn):
    """Before the refresh such a game had no row. The scorer's game list, the
    NHL slate the goalie poll, goalie window and prop cards share, the totals
    card's slate and the prop purchase all keep the set they had."""
    from data.ingestors.nhl_prop_odds_ingestor import _schedule_only_ids
    from models.scorer import _game_board
    from scripts.nhl_prop_card import slate as nhl_slate
    from scripts.nhl_totals_card import slate as totals_slate
    _refresh(conn)
    listed = "NHL_2026-10-22_NSH_BOS"
    conn.execute("UPDATE games SET data_source = 'live' WHERE game_id = %s", (listed,))
    conn.execute("""INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
                    data_source, commence_time) VALUES ('NBA_2026-10-22_BOS_NYK', 'NBA', 2027,
                    '2026-10-22', 'NYK', 'BOS', 'espn_schedule', '2026-10-22T23:30:00Z')""")
    conn.commit()
    today = {r["game_id"] for r in nsr.read_stored(conn, "2026-10-22", "2026-10-22")}
    assert len(today) == 12

    assert set(nhl_slate(conn, "2026-10-22", NOW)) == {listed}
    assert set(nhl_slate(conn, "2026-10-23", NOW)) == set()           # tomorrow: no book yet
    assert set(totals_slate(conn, NOW)) == {listed}
    board = {g[0] for g in _game_board(conn, "2026-10-22", "2026-10-29", "2027-03-21", "2026-10-29")}
    assert board == {listed, "NBA_2026-10-22_BOS_NYK"}               # other sports' rows untouched
    assert _schedule_only_ids(conn, sorted(today)) == today - {listed}


def test_a_book_listing_the_game_the_other_way_round_takes_it_over(conn):
    """The refresh writes first, months ahead. If the odds feed then keys the
    game with home and away swapped (a neutral site), the next run removes the
    refresh's row and does not write it again: one game, one row, the book's,
    exactly as before the refresh existed."""
    from data.ingestors.odds_ingestor import _upsert_games
    _refresh(conn)
    assert _count(conn) == 27
    feed_id = "NHL_2026-10-25_WPG_MTL"                  # the API's is NHL_2026-10-25_MTL_WPG
    _upsert_games(conn, [{"game_id": feed_id, "sport": "NHL", "season": 2027,
                          "game_date": "2026-10-25", "home_team": "MTL", "away_team": "WPG",
                          "commence_time": "2026-10-25T23:10:00+00:00", "data_source": "live"}])
    conn.commit()
    assert _count(conn) == 28
    before = _row(conn, feed_id, ("data_source", "commence_time", "home_team", "updated_at"))
    t = _refresh(conn)
    assert _count(conn) == 27 and _row(conn, "NHL_2026-10-25_MTL_WPG") is None
    assert t["twins"] == 1 and nsr.step_ok(t)
    assert _row(conn, feed_id, ("data_source", "commence_time", "home_team", "updated_at")) == before
    t = _refresh(conn)                                     # and it stays that way
    assert t["conflicts"] == 1 and t["insert"] == 0 and _count(conn) == 27


def test_a_game_that_did_not_happen_is_gone_the_morning_after_and_nothing_else_is(conn):
    """Ten of the refresh's rows on 10-21, games the API no longer lists that
    day: removed by the 10-22 run, more than the cap. Left alone: a game the
    API lists as played that the results step has not scored yet, a row
    something references, the odds feed's own unplayed row, and a row older
    than the days the run reads."""
    for a, h in TEN:
        _put(conn, f"NHL_2026-10-21_{a}_{h}", "nhl_schedule", "2026-10-21T23:00:00Z")
    _put(conn, "NHL_2026-10-21_CBJ_PHI", "nhl_schedule", "2026-10-21T23:00:00Z")   # played
    _put(conn, "NHL_2026-10-21_BOS_CAR", "nhl_schedule", "2026-10-21T23:30:00Z")   # referenced
    _put(conn, "NHL_2026-10-21_STL_FLA", "live", "2026-10-21T23:10:00+00:00")      # the feed's
    _put(conn, "NHL_2026-10-13_STL_FLA", "nhl_schedule", "2026-10-13T23:00:00Z")   # before the days read
    conn.execute("INSERT INTO nhl_goalie_stats (game_id, team) VALUES ('NHL_2026-10-21_BOS_CAR', 'CAR')")
    conn.commit()
    played = _game("CBJ", "PHI", "2026-10-21T23:00:00Z", state="OFF")
    t = _refresh(conn, get=_get({
        "2026-10-15": _week_from("2026-10-15", {"2026-10-21": [played]}, nxt="2026-10-22"),
        "2026-10-22": dict(WEEK1, nextStartDate=None)}))
    assert nsr.step_ok(t) and t["orphans_held"] == 0
    left = {r[0] for r in conn.execute(
        "SELECT game_id FROM games WHERE game_date < '2026-10-22' AND home_score IS NULL").fetchall()}
    assert left == {"NHL_2026-10-21_CBJ_PHI", "NHL_2026-10-21_BOS_CAR", "NHL_2026-10-21_STL_FLA",
                    "NHL_2026-10-13_STL_FLA"}

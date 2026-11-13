"""NBA first-quarter team stats: the migration, the writer and the season view.

Runs on a scratch Postgres. What it pins:
  - one row per team per game, home and away mirrored
  - possessions are NULL when the stints' 1Q points miss the quarter score,
    and such a game counts in the record but not in the ratings
  - a re-run rewrites nothing that did not change
  - the season view's record, per-100 ratings and ranks
  - a second pass of the migration returns before any DDL
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "data" / "migrations" / "add_nba_team_q1_2026_10_28.sql").read_text(encoding="utf-8")


def _scratch():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    try:
        dsn = cluster.start()
    except Exception as exc:
        cluster.stop()
        pytest.skip(f"scratch cluster did not start: {exc}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return cluster, conn


SCHEMA = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END $$;
CREATE TABLE games (game_id text primary key, sport text, season int, game_date text,
                    home_team text, away_team text, home_score int, away_score int);
CREATE TABLE nba_period_scores (game_id text, period int, home_points int, away_points int,
                                source text, primary key (game_id, period));
CREATE TABLE nba_stints (game_id text, season int, period smallint, stint_no int,
                         home_pts smallint, away_pts smallint, home_poss smallint, away_poss smallint);
"""

# G1: BOS home 30-25 over NYK, possessions 25/24 over two stints.
# G2: NYK home 28-28 with LAL, the stints say 27 for NYK, so possessions are dropped.
# G3: BOS at LAL 20-31, possessions 24/26.
FIXTURE = """
INSERT INTO games VALUES
 ('NBA_2026-10-21_NYK_BOS','NBA',2027,'2026-10-21','BOS','NYK',110,100),
 ('NBA_2026-10-22_LAL_NYK','NBA',2027,'2026-10-22','NYK','LAL',99,101),
 ('NBA_2026-10-23_BOS_LAL','NBA',2027,'2026-10-23','LAL','BOS',120,105);
INSERT INTO nba_period_scores VALUES
 ('NBA_2026-10-21_NYK_BOS',1,30,25,'t'), ('NBA_2026-10-21_NYK_BOS',2,20,20,'t'),
 ('NBA_2026-10-22_LAL_NYK',1,28,28,'t'),
 ('NBA_2026-10-23_BOS_LAL',1,31,20,'t');
INSERT INTO nba_stints VALUES
 ('NBA_2026-10-21_NYK_BOS',2027,1,1,18,15,15,14),
 ('NBA_2026-10-21_NYK_BOS',2027,1,2,12,10,10,10),
 ('NBA_2026-10-21_NYK_BOS',2027,2,3,20,20,25,25),
 ('NBA_2026-10-22_LAL_NYK',2027,1,1,27,28,25,25),
 ('NBA_2026-10-23_BOS_LAL',2027,1,1,31,20,26,24);
"""


class _Conn:
    """The two calls rebuild() makes, over a psycopg2 connection."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=None):
        cur = self.raw.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        pass


@pytest.fixture(scope="module")
def db():
    cluster, conn = _scratch()
    try:
        cur = conn.cursor()
        cur.execute(SCHEMA)
        cur.execute(FIXTURE)
        cur.execute(MIGRATION)
        yield conn
    finally:
        conn.close()
        cluster.stop()


def _rebuild(conn, seasons):
    from data.ingestors.nba_team_q1 import rebuild
    return rebuild(_Conn(conn), seasons)


def test_one_row_per_team_per_game_with_possessions_only_when_points_agree(db):
    assert _rebuild(db, [2026, 2027])["rows"] == 6
    cur = db.cursor()
    cur.execute("SELECT game_id, team, opponent, is_home, pts_for, pts_against, poss_for, poss_against "
                "FROM nba_team_q1_games ORDER BY game_id, team")
    assert cur.fetchall() == [
        ("NBA_2026-10-21_NYK_BOS", "BOS", "NYK", True, 30, 25, 25, 24),
        ("NBA_2026-10-21_NYK_BOS", "NYK", "BOS", False, 25, 30, 24, 25),
        ("NBA_2026-10-22_LAL_NYK", "LAL", "NYK", False, 28, 28, None, None),
        ("NBA_2026-10-22_LAL_NYK", "NYK", "LAL", True, 28, 28, None, None),
        ("NBA_2026-10-23_BOS_LAL", "BOS", "LAL", False, 20, 31, 24, 26),
        ("NBA_2026-10-23_BOS_LAL", "LAL", "BOS", True, 31, 20, 26, 24),
    ]


def test_a_rerun_rewrites_nothing_unchanged_and_picks_up_a_correction(db):
    _rebuild(db, [2027])
    assert _rebuild(db, [2027])["rows"] == 0
    cur = db.cursor()
    cur.execute("UPDATE nba_stints SET home_pts = 28 WHERE game_id = 'NBA_2026-10-22_LAL_NYK'")
    try:
        assert _rebuild(db, [2027])["rows"] == 2
        cur.execute("SELECT poss_for FROM nba_team_q1_games WHERE game_id = 'NBA_2026-10-22_LAL_NYK' "
                    "AND team = 'NYK'")
        assert cur.fetchone()[0] == 25
    finally:
        cur.execute("UPDATE nba_stints SET home_pts = 27 WHERE game_id = 'NBA_2026-10-22_LAL_NYK'")
        _rebuild(db, [2027])


def test_season_view_record_ratings_and_ranks(db):
    _rebuild(db, [2027])
    cur = db.cursor()
    cur.execute("SELECT team, games, wins, losses, ties, pts_for, pts_against, rated_games, "
                "ortg, drtg, ortg_rank, drtg_rank, teams "
                "FROM v_nba_team_q1_season WHERE season = 2027 AND venue = 'all' ORDER BY team")
    rows = {r[0]: r[1:] for r in cur.fetchall()}
    # BOS: 30-25 W, 20-31 L. Ratings over both: 100*50/49, 100*56/50.
    assert rows["BOS"][:7] == (2, 1, 1, 0, 50, 56, 2)
    assert float(rows["BOS"][7]) == 102.0 and float(rows["BOS"][8]) == 112.0
    # NYK: the tie counts in the record; only G1 is rated (25 on 24, 30 on 25).
    assert rows["NYK"][:7] == (2, 0, 1, 1, 53, 58, 1)
    assert float(rows["NYK"][7]) == 104.2 and float(rows["NYK"][8]) == 120.0
    assert rows["LAL"][9] == 1 and rows["LAL"][11] == 3   # 31 on 26 is the best offence
    cur.execute("SELECT venue, games, wins FROM v_nba_team_q1_season "
                "WHERE season = 2027 AND team = 'BOS' ORDER BY venue")
    assert cur.fetchall() == [("all", 2, 1), ("away", 1, 0), ("home", 1, 1)]


def test_anon_can_read_both_relations_and_cannot_write(db):
    _rebuild(db, [2027])
    cur = db.cursor()
    cur.execute("SELECT has_table_privilege('anon', 'nba_team_q1_games', 'SELECT'), "
                "has_table_privilege('anon', 'nba_team_q1_games', 'INSERT'), "
                "has_table_privilege('anon', 'v_nba_team_q1_season', 'SELECT')")
    assert cur.fetchone() == (True, False, True)
    cur.execute("SET ROLE anon")
    try:
        cur.execute("SELECT count(*) FROM v_nba_team_q1_season")
        assert cur.fetchone()[0] > 0
    finally:
        cur.execute("RESET ROLE")


def test_a_second_pass_returns_before_any_ddl(db):
    cur = db.cursor()
    cur.execute("SELECT xmin::text FROM pg_class WHERE oid = 'public.v_nba_team_q1_season'::regclass")
    before = cur.fetchone()[0]
    cur.execute(MIGRATION)
    cur.execute("SELECT xmin::text FROM pg_class WHERE oid = 'public.v_nba_team_q1_season'::regclass")
    assert cur.fetchone()[0] == before


def test_registered_and_rebuild_skips_without_the_table():
    from data.view_migrations import ACTIVE_MIGRATIONS
    from data.ingestors.nba_team_q1 import rebuild

    assert "add_nba_team_q1_2026_10_28.sql" in ACTIVE_MIGRATIONS

    class NoTable:
        def execute(self, sql, params=None):
            class R:
                def fetchone(self):
                    return (False,)
            return R()

    assert rebuild(NoTable(), [2027])["rows"] == 0

"""NBA first-basket stats: the migration, the writer and the two season views.

Runs on a scratch Postgres. What it pins:
  - the tip winner is the opening Jumpball's team side, and a later held-ball
    jump in the same quarter does not replace it
  - a free throw is the game's first basket (Matt, 2026-11-08) but never a
    team's first SHOT, which is its first field-goal attempt
  - a team that loses the tip can still score first
  - a game with no play-by-play yet, and a playoff game, write no row
  - a game with no Jumpball row has won_tip NULL and no jumper
  - a did-not-play player gets no row; a traded player is listed under his
    latest team with every game he played
  - a re-run rewrites nothing; a second migration pass returns before DDL
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "data" / "migrations" / "add_nba_first_basket_2026_11_08.sql").read_text(encoding="utf-8")


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
CREATE TABLE nba_pbp_games (espn_game_id bigint primary key, game_id text, season int,
                            season_type smallint, game_date text, home_team text, away_team text);
CREATE TABLE nba_pbp_box (espn_game_id bigint, espn_id bigint, game_id text, season int, side text,
                          team text, name text, starter boolean, minutes real, did_not_play boolean);
CREATE TABLE nba_pbp (espn_game_id bigint, play_no int, period smallint, type_text text,
                      team_side text, athlete_id_1 bigint, athlete_id_2 bigint,
                      shooting_play boolean, scoring_play boolean, points smallint);
"""

# G1 BOS (home) v NYK: NYK wins the tip, misses its first shot; BOS scores first.
# G2 NYK (home) v LAL: NYK wins the tip; its first points are a free throw by
#    203, its first FIELD-GOAL attempt is 202's dunk after a held-ball jump.
# G3 LAL v BOS: box loaded, no play-by-play yet.
# G4: a playoff game (season_type 3).
# G5 LAL (home) v BOS: no Jumpball row; 202 now plays for LAL and scores first.
FIXTURE = """
INSERT INTO nba_pbp_games VALUES
 (1,'G1',2027,2,'2026-10-21','BOS','NYK'),
 (2,'G2',2027,2,'2026-10-22','NYK','LAL'),
 (3,'G3',2027,2,'2026-10-23','LAL','BOS'),
 (4,'G4',2026,3,'2026-05-01','BOS','NYK'),
 (5,'G5',2027,2,'2026-10-24','LAL','BOS');
INSERT INTO nba_pbp_box VALUES
 (1,101,'G1',2027,'H','BOS','Bo One',true,30,false),
 (1,102,'G1',2027,'H','BOS','Bo Two',true,30,false),
 (1,103,'G1',2027,'H','BOS','Bo Bench',false,10,false),
 (1,104,'G1',2027,'H','BOS','Bo Out',false,0,true),
 (1,201,'G1',2027,'A','NYK','Ny One',true,30,false),
 (1,202,'G1',2027,'A','NYK','Ny Two',true,30,false),
 (1,203,'G1',2027,'A','NYK','Ny Three',false,12,false),
 (2,201,'G2',2027,'H','NYK','Ny One',true,30,false),
 (2,202,'G2',2027,'H','NYK','Ny Two',true,30,false),
 (2,203,'G2',2027,'H','NYK','Ny Three',true,30,false),
 (2,301,'G2',2027,'A','LAL','La One',true,30,false),
 (2,302,'G2',2027,'A','LAL','La Two',true,30,false),
 (3,301,'G3',2027,'H','LAL','La One',true,30,false),
 (3,101,'G3',2027,'A','BOS','Bo One',true,30,false),
 (4,101,'G4',2026,'H','BOS','Bo One',true,30,false),
 (4,201,'G4',2026,'A','NYK','Ny One',true,30,false),
 (5,301,'G5',2027,'H','LAL','La One',true,30,false),
 (5,202,'G5',2027,'H','LAL','Ny Two',true,30,false),
 (5,101,'G5',2027,'A','BOS','Bo One',true,30,false),
 (5,102,'G5',2027,'A','BOS','Bo Two',true,30,false);
INSERT INTO nba_pbp VALUES
 (1,1,1,'Jumpball','A',101,201,false,false,0),
 (1,2,1,'Jump Shot','A',202,null,true,false,0),
 (1,3,1,'Defensive Rebound','H',101,null,false,false,0),
 (1,4,1,'Layup Shot','H',102,null,true,true,2),
 (1,5,1,'Jump Shot','A',201,null,true,true,3),
 (2,1,1,'Jumpball','H',201,301,false,false,0),
 (2,2,1,'Shooting Foul','A',301,null,false,false,0),
 (2,3,1,'Free Throw - 1 of 2','H',203,null,true,true,1),
 (2,4,1,'Free Throw - 2 of 2','H',203,null,true,false,0),
 (2,5,1,'Jump Shot','A',301,null,true,true,3),
 (2,6,1,'Jumpball','A',202,302,false,false,0),
 (2,7,1,'Dunk Shot','H',202,null,true,true,2),
 (4,1,1,'Jumpball','H',101,201,false,false,0),
 (4,2,1,'Layup Shot','H',101,null,true,true,2),
 (5,1,1,'Layup Shot','H',202,null,true,true,2),
 (5,2,1,'Jump Shot','A',101,null,true,false,0),
 (5,3,1,'Jump Shot','A',102,null,true,true,3);
"""


class _Conn:
    """The calls rebuild() makes, over a psycopg2 connection."""

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
    from data.ingestors.nba_first_basket import rebuild
    return rebuild(_Conn(conn), seasons)


def test_team_game_rows(db):
    out = _rebuild(db, [2026, 2027])
    assert out["games"] == 6
    cur = db.cursor()
    cur.execute("SELECT game_id, team, opponent, is_home, won_tip, jumper_espn_id, jumper_name, "
                "scored_first, first_score_kind, first_fga_espn_id, first_fga_made, first_score_espn_id "
                "FROM nba_first_basket_games ORDER BY game_id, team")
    assert cur.fetchall() == [
        ("G1", "BOS", "NYK", True, False, 101, "Bo One", True, "2PT", 102, True, 102),
        ("G1", "NYK", "BOS", False, True, 201, "Ny One", False, None, 202, False, 201),
        # The free throw is NYK's first basket; its first SHOT is 202's dunk.
        ("G2", "LAL", "NYK", False, False, 301, "La One", False, None, 301, True, 301),
        ("G2", "NYK", "LAL", True, True, 201, "Ny One", True, "FT", 202, True, 203),
        # No Jumpball row: no tip result and no jumper, the scores still count.
        ("G5", "BOS", "LAL", False, None, None, None, False, None, 101, False, 102),
        ("G5", "LAL", "BOS", True, None, None, None, True, "2PT", 202, True, 202),
    ]


def test_player_game_rows_skip_did_not_play(db):
    _rebuild(db, [2026, 2027])
    cur = db.cursor()
    # 20 box rows: minus G3 (no play-by-play), G4 (playoffs) and 104 (DNP).
    cur.execute("SELECT count(*) FROM nba_first_basket_players")
    assert cur.fetchone()[0] == 15
    cur.execute("SELECT count(*) FROM nba_first_basket_players WHERE espn_id = 104")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT game_id, espn_id, team, first_fga, first_fga_made, game_first_score, "
                "team_first_score, jumped, jump_won FROM nba_first_basket_players "
                "WHERE game_id = 'G2' ORDER BY espn_id")
    assert cur.fetchall() == [
        ("G2", 201, "NYK", False, False, False, False, True, True),
        ("G2", 202, "NYK", True, True, False, False, False, False),
        ("G2", 203, "NYK", False, False, True, True, False, False),
        ("G2", 301, "LAL", True, True, False, True, True, False),
        ("G2", 302, "LAL", False, False, False, False, False, False),
    ]


def test_a_rerun_rewrites_nothing(db):
    _rebuild(db, [2027])
    assert _rebuild(db, [2027]) == {"seasons": [2027], "games": 0, "players": 0,
                                    "deleted_games": 0, "deleted_players": 0}


def test_a_row_whose_source_is_gone_is_deleted_and_other_seasons_are_left(db):
    """Review L3: a box row corrected to DNP, or a game's play-by-play removed."""
    _rebuild(db, [2026, 2027])
    cur = db.cursor()
    cur.execute("INSERT INTO nba_first_basket_games (game_id, team, season, game_date, opponent, is_home, "
                "scored_first) VALUES ('OLD', 'BOS', 2025, '2025-01-01', 'NYK', true, true)")
    cur.execute("UPDATE nba_pbp_box SET did_not_play = true WHERE espn_game_id = 1 AND espn_id = 103")
    cur.execute("DELETE FROM nba_pbp WHERE espn_game_id = 5")
    try:
        out = _rebuild(db, [2027])
        assert out["deleted_games"] == 2 and out["deleted_players"] == 1 + 4, out
        cur.execute("SELECT count(*) FROM nba_first_basket_games WHERE game_id = 'G5'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM nba_first_basket_players WHERE game_id = 'G1' AND espn_id = 103")
        assert cur.fetchone()[0] == 0
        # A season not being rebuilt is never touched.
        cur.execute("SELECT count(*) FROM nba_first_basket_games WHERE game_id = 'OLD'")
        assert cur.fetchone()[0] == 1
    finally:
        cur.execute("DELETE FROM nba_first_basket_games WHERE game_id = 'OLD'")
        cur.execute("UPDATE nba_pbp_box SET did_not_play = false WHERE espn_game_id = 1 AND espn_id = 103")
        cur.execute("INSERT INTO nba_pbp VALUES "
                    "(5,1,1,'Layup Shot','H',202,null,true,true,2),"
                    "(5,2,1,'Jump Shot','A',101,null,true,false,0),"
                    "(5,3,1,'Jump Shot','A',102,null,true,true,3)")
        _rebuild(db, [2027])


def test_team_season_view(db):
    _rebuild(db, [2027])
    cur = db.cursor()
    cur.execute("SELECT team, games, tip_games, tips_won, scored_first, scored_first_won_tip, "
                "lost_tip_games, scored_first_lost_tip, allowed_first, jumper_espn_id, "
                "jumper_name, jumper_jumps, jumper_jumps_won "
                "FROM v_nba_first_basket_team_season WHERE season = 2027 ORDER BY team")
    assert cur.fetchall() == [
        ("BOS", 2, 1, 0, 1, 0, 1, 1, 1, 101, "Bo One", 1, 0),
        ("LAL", 2, 1, 0, 1, 0, 1, 0, 1, 301, "La One", 1, 0),
        ("NYK", 2, 2, 2, 1, 1, 0, 0, 1, 201, "Ny One", 2, 2),
    ]


def test_player_season_view_lists_a_traded_player_under_his_latest_team(db):
    _rebuild(db, [2027])
    cur = db.cursor()
    cur.execute("SELECT espn_id, name, team, games, starts, first_fga, first_fga_made, "
                "game_first_scores, team_first_scores, jumps, jumps_won "
                "FROM v_nba_first_basket_player_season WHERE season = 2027 "
                "AND espn_id IN (201, 202, 203) ORDER BY espn_id")
    assert cur.fetchall() == [
        (201, "Ny One", "NYK", 2, 2, 0, 0, 0, 1, 2, 2),
        (202, "Ny Two", "LAL", 3, 3, 3, 2, 1, 1, 0, 0),
        (203, "Ny Three", "NYK", 2, 1, 0, 0, 1, 1, 0, 0),
    ]


def test_player_season_view_counts_first_shots_in_starts_only(db):
    """'Per start' must stay exact: a bench first shot is not counted (review L2)."""
    _rebuild(db, [2027])
    cur = db.cursor()
    cur.execute("INSERT INTO nba_first_basket_players (game_id, espn_id, season, game_date, team, name, "
                "starter, first_fga, first_fga_made, game_first_score, team_first_score, jumped, jump_won) "
                "VALUES ('GX', 999, 2027, '2026-10-30', 'BOS', 'Bench Shooter', false, true, true, true, true, "
                "false, false)")
    try:
        cur.execute("SELECT games, starts, first_fga, first_fga_made, game_first_scores "
                    "FROM v_nba_first_basket_player_season WHERE season = 2027 AND espn_id = 999")
        assert cur.fetchone() == (1, 0, 0, 0, 0)
    finally:
        cur.execute("DELETE FROM nba_first_basket_players WHERE espn_id = 999")


def test_anon_can_read_all_four_relations_and_cannot_write(db):
    _rebuild(db, [2027])
    cur = db.cursor()
    for rel in ("nba_first_basket_games", "nba_first_basket_players",
                "v_nba_first_basket_team_season", "v_nba_first_basket_player_season"):
        cur.execute("SELECT has_table_privilege('anon', %s, 'SELECT'), "
                    "has_table_privilege('anon', %s, 'INSERT')", (rel, rel))
        assert cur.fetchone() == (True, False), rel
    cur.execute("SET ROLE anon")
    try:
        cur.execute("SELECT count(*) FROM v_nba_first_basket_player_season")
        assert cur.fetchone()[0] > 0
    finally:
        cur.execute("RESET ROLE")


def test_a_second_pass_returns_before_any_ddl(db):
    cur = db.cursor()
    q = ("SELECT xmin::text FROM pg_class WHERE oid = "
         "'public.v_nba_first_basket_player_season'::regclass")
    cur.execute(q)
    before = cur.fetchone()[0]
    cur.execute(MIGRATION)
    cur.execute(q)
    assert cur.fetchone()[0] == before


def test_registered_and_rebuild_skips_without_the_tables():
    from data.view_migrations import ACTIVE_MIGRATIONS
    from data.ingestors.nba_first_basket import rebuild

    assert "add_nba_first_basket_2026_11_08.sql" in ACTIVE_MIGRATIONS

    class NoTable:
        def execute(self, sql, params=None):
            class R:
                def fetchone(self):
                    return (False,)
            return R()

    assert rebuild(NoTable(), [2027])["games"] == 0

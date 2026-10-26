"""NBA last-N reads list a player who has not played yet this season under his
ROSTER team (Matt, 2026-10-26), on a real Postgres.

Runs data/migrations/nba_window_reads_roster_team_2026_10_26.sql on a scratch
cluster against a fixture that holds every population the two team sources can
disagree about (CLAUDE.md §7 / frontend rule: a fixture with one team per
player is the guard that passed while the board was wrong):

  brown    traded BOS -> PHI in the summer, has played for PHI   -> PHI (log)
  injured  traded MIA -> GSW, roster says GS, not yet played      -> GSW (roster, mapped)
  retired  last game 2025-26 for BOS, on no roster                -> not listed
  steady   NYK both seasons, roster says NY                       -> NYK
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests._pg import can_scratch, env_dsn, scratch_cluster

psycopg2 = pytest.importorskip("psycopg2")

ROOT = Path(__file__).parent.parent
MIG = ROOT / "data" / "migrations" / "nba_window_reads_roster_team_2026_10_26.sql"

pytestmark = pytest.mark.skipif(not (env_dsn() or can_scratch()), reason="no Postgres available")

SCHEMA = """
CREATE TABLE nba_player_game_log (
    player_id text, player_name text, team text, game_id text, game_date text,
    season integer, minutes numeric, points integer, rebounds integer,
    assists integer, fg3_made integer, steals integer, blocks integer, turnovers integer);
CREATE TABLE player_positions (sport text, player_id text, player_name text, team text);
"""


def _games(pid, name, team, season, dates, pts=20):
    return [(pid, name, team, f"{pid}-{d}", d, season, 30, pts, 5, 5, 2, 1, 1, 2)
            for d in dates]


ROWS = (
    _games("brown", "Jaylen Brown", "BOS", 2026, [f"2026-04-{d:02d}" for d in range(1, 11)])
    + _games("brown", "Jaylen Brown", "PHI", 2027, ["2026-10-20", "2026-10-22"])
    + _games("injured", "Hurt Guy", "MIA", 2026, [f"2026-03-{d:02d}" for d in range(1, 11)])
    + _games("retired", "Old Guy", "BOS", 2026, [f"2026-02-{d:02d}" for d in range(1, 11)])
    + _games("steady", "Same Guy", "NYK", 2026, [f"2026-04-{d:02d}" for d in range(1, 11)])
    + _games("steady", "Same Guy", "NYK", 2027, ["2026-10-21"])
)
ROSTER = [("NBA", "brown", "Jaylen Brown", "PHI"), ("NBA", "injured", "Hurt Guy", "GS"),
          ("NBA", "steady", "Same Guy", "NY")]


@pytest.fixture(scope="module")
def cur():
    def run(dsn):
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        c = conn.cursor()
        c.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        c.execute(SCHEMA)
        c.executemany("INSERT INTO nba_player_game_log VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", ROWS)
        c.executemany("INSERT INTO player_positions VALUES (%s,%s,%s,%s)", ROSTER)
        c.execute(MIG.read_text(encoding="utf-8"))
        return conn, c
    dsn = env_dsn()
    if dsn:
        conn, c = run(dsn)
        yield c
        conn.close()
        return
    with scratch_cluster("nba-roster-") as dsn:
        conn, c = run(dsn)
        yield c
        conn.close()


def _board(cur, teams=None):
    cur.execute("SELECT player_id, team, count(*) FROM player_recent_games_nba(2027, 10, %s) "
                "WHERE rn = 1 OR true GROUP BY player_id, team ORDER BY 1, 2", (teams,))
    rows = cur.fetchall()
    cur.execute("SELECT player_id, team FROM player_recent_games_nba(2027, 10, %s) WHERE rn = 1", (teams,))
    head = dict(cur.fetchall())
    cur.execute("SELECT player_id, count(*) FROM player_recent_games_nba(2027, 10, %s) GROUP BY 1", (teams,))
    games = dict(cur.fetchall())
    return head, games, rows


def test_newest_row_carries_the_current_team(cur):
    head, games, _ = _board(cur)
    assert head == {"brown": "PHI", "injured": "GSW", "steady": "NYK"}
    assert "retired" not in head


def test_window_still_spans_last_season(cur):
    _, games, _ = _board(cur)
    assert games == {"brown": 10, "injured": 10, "steady": 10}


def test_older_rows_keep_the_team_they_were_played_for(cur):
    cur.execute("SELECT team FROM player_recent_games_nba(2027, 10) WHERE player_id='brown' AND rn > 2")
    assert {t for (t,) in cur.fetchall()} == {"BOS"}


def test_slate_narrowing_uses_the_resolved_team(cur):
    head, games, _ = _board(cur, ["GSW"])
    assert head == {"injured": "GSW"} and games == {"injured": 10}
    head, _, _ = _board(cur, ["MIA"])
    assert head == {}, "a player who left MIA must not be admitted to its board"
    head, _, _ = _board(cur, ["BOS"])
    assert head == {}, "Brown left BOS; the retired BOS player is on no roster"


def test_window_totals_match(cur):
    cur.execute("SELECT player_id, team, games_played FROM player_window_totals_nba(2027, 10) ORDER BY 1")
    assert cur.fetchall() == [("brown", "PHI", 10), ("injured", "GSW", 10), ("steady", "NYK", 10)]


def test_season_chip_stays_this_season_only(cur):
    cur.execute("SELECT player_id, games_played FROM player_window_totals_nba(2027, NULL) ORDER BY 1")
    # injured has no game this season but is on a roster: listed with 0? No —
    # the Season read has no last-season rows to sum, so he has no row at all.
    assert cur.fetchall() == [("brown", 2), ("steady", 1)]


def test_second_run_is_a_no_op(cur):
    cur.execute("SELECT md5(pg_get_functiondef('public.player_recent_games_nba(integer,integer,text[])'::regprocedure))")
    before = cur.fetchone()[0]
    cur.execute(MIG.read_text(encoding="utf-8"))
    cur.execute("SELECT md5(pg_get_functiondef('public.player_recent_games_nba(integer,integer,text[])'::regprocedure))")
    assert cur.fetchone()[0] == before
    notices = cur.connection.notices
    assert any("skipping" in n for n in notices), notices

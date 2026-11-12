"""Women's player log for the Stats tab.

The rows come from the sportsdataverse player box (data/ingestors/ncaabw_sdv_import.py),
not an ESPN women's box. The SQL is add_ncaabw_player_game_log_2026_11_12.sql,
which is not on the worker's migration list.

The Postgres half runs against LATEST_LINE_TEST_DSN or a scratch cluster and
SKIPS where neither exists.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data.ingestors import ncaabw_sdv_import as si

ROOT = Path(__file__).parent.parent
MIGRATION_NAME = "add_ncaabw_player_game_log_2026_11_12.sql"
SQL = (ROOT / "data" / "migrations" / MIGRATION_NAME).read_text(encoding="utf-8")

GAME = {
    "game_id": "NCAABW_2026-11-02_lindenwood_colorado-state",
    "game_date": "2026-11-02",
    "season": 2027,
    "home_espn_id": 36,
    "away_espn_id": 2815,
    "home_team": "Colorado State",
    "away_team": "Lindenwood",
}


def _box(**over):
    row = {
        "espn_game_id": "401927946", "team_espn_team_id": "36", "team": "Colorado St.",
        "clean_name": "Allie Roden", "player_id": "11516591", "mins": 6, "pts": 0,
        "orb": 0, "drb": 1, "ast": 2, "stl": 0, "blk": 0, "tov": 1, "pf": 1,
        "fgm": 0, "fga": 1, "tpm": 0, "tpa": 1, "ftm": 0, "fta": 0,
    }
    row.update(over)
    return row


def test_the_migration_is_not_on_the_worker_list():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIGRATION_NAME not in ACTIVE_MIGRATIONS
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in SQL


def test_the_sql_names_the_womens_sport_and_never_the_mens():
    """A men's predicate would score women's games against the wrong schools."""
    assert "g.sport = 'NCAABW'" in SQL
    assert "g.sport = 'NCAAB'" not in SQL
    for name in ("player_window_totals_ncaabw", "player_recent_games_ncaabw",
                 "player_season_stat_values_ncaabw", "player_h2h_stat_values_ncaabw",
                 "v_player_season_totals_ncaabw", "ncaabw_player_game_log"):
        assert name in SQL, name
        bare = name.replace("_ncaabw", "_ncaab").replace("ncaabw_", "ncaab_")
        assert bare + "(" not in SQL and f"'{bare}'" not in SQL, bare


def test_a_box_row_lands_on_the_stored_game_and_school():
    """The file says 'Colorado St.'; the games row says 'Colorado State'.
    The board joins on the stored school, so the file's spelling is not the
    one that is kept. NCAA's player_id is not the log's id."""
    rows = si.game_log_rows(pd.DataFrame([_box()]), {401927946: GAME})
    assert len(rows) == 1
    row = rows[0]
    assert row["game_id"] == GAME["game_id"]
    assert row["team"] == "Colorado State"
    assert row["player_id"] == "36:allie roden"
    assert row["player_id"] != "11516591"
    assert row["player_name"] == "Allie Roden"
    assert row["espn_event_id"] == 401927946
    assert row["season"] == 2027 and row["game_date"] == "2026-11-02"
    assert (row["points"], row["rebounds"], row["assists"], row["fg3_made"],
            row["minutes"], row["source"]) == (0, 1, 2, 0, 6, si.SOURCE)
    assert row["position"] is None and row["is_starter"] is None
    assert list(row) == list(si.LOG_COLS)


def test_minutes_stay_fractional_and_counts_are_whole():
    rows = si.game_log_rows(pd.DataFrame([_box(mins=2.017, pts=3, ftm=3, fta=3,
                                               fgm=0, fga=0, tpm=1, tpa=2)]),
                            {401927946: GAME})
    assert rows[0]["minutes"] == pytest.approx(2.017)
    assert rows[0]["points"] == 3 and rows[0]["fg3_made"] == 1 and rows[0]["fg3_att"] == 2


def test_rows_the_board_cannot_join_are_left_out():
    games = {401927946: GAME}
    assert si.game_log_rows(pd.DataFrame([_box(espn_game_id=None)]), games) == []
    assert si.game_log_rows(pd.DataFrame([_box(espn_game_id="999")]), games) == []
    assert si.game_log_rows(pd.DataFrame([_box(team_espn_team_id="1")]), games) == []
    assert si.game_log_rows(pd.DataFrame([_box(mins=0, pts=0, orb=0, drb=0, ast=0,
                                               stl=0, blk=0, tov=0, fgm=0, tpm=0, ftm=0)]),
                            games) == []


def test_the_same_folded_name_on_two_teams_is_two_players():
    away = _box(team_espn_team_id="2815", team="Lindenwood", clean_name="Allie Roden",
                player_id="999", mins=20, pts=11)
    rows = {r["player_id"]: r for r in si.game_log_rows(pd.DataFrame([_box(pts=4), away]),
                                                        {401927946: GAME})}
    assert set(rows) == {"36:allie roden", "2815:allie roden"}
    assert rows["2815:allie roden"]["team"] == "Lindenwood"
    assert rows["2815:allie roden"]["points"] == 11


def test_two_games_keep_one_id_and_a_duplicate_keeps_the_longer_stint():
    other = dict(GAME, game_id="NCAABW_2026-11-05_x_colorado-state", game_date="2026-11-05")
    short = _box(mins=4, pts=1)
    long = _box(mins=30, pts=18)
    later = _box(espn_game_id="401927999", mins=22, pts=9)
    rows = si.game_log_rows(pd.DataFrame([short, long, later]),
                            {401927946: GAME, 401927999: other})
    by_game = {r["game_id"]: r for r in rows}
    assert set(by_game) == {GAME["game_id"], other["game_id"]}
    assert by_game[GAME["game_id"]]["minutes"] == 30
    assert by_game[GAME["game_id"]]["player_id"] == by_game[other["game_id"]]["player_id"]


class _LogConn:
    """to_regclass answers, then the stored game ids, and what was inserted."""

    def __init__(self, ready=True, games=()):
        self.ready, self.games, self.sql, self.inserted = ready, list(games), [], []

    def execute(self, sql, params=()):
        self.sql.append(" ".join(sql.split()))
        text = self.sql[-1]
        if text.startswith("SELECT to_regclass"):
            answer = [("ncaabw_player_game_log",)] if self.ready else [(None,)]
        elif text.startswith("SELECT game_id"):
            answer = list(self.games)
        elif text.startswith("SELECT e.espn_event_id"):
            answer = [(401927946, GAME["game_id"], GAME["game_date"], 2027,
                       36, 2815, "Colorado State", "Lindenwood")]
        else:
            answer = []

        class R:
            def fetchone(_self):
                return answer[0] if answer else None

            def fetchall(_self):
                return answer
        return R()

    def executemany(self, sql, rows):
        assert "ncaabw_player_game_log" in sql
        assert "ncaab_player_game_log" not in sql.replace("ncaabw_player_game_log", "")
        self.inserted += list(rows)

    def commit(self):
        self.sql.append("COMMIT")


def test_the_daily_read_writes_the_log_only_when_the_table_exists():
    frame = pd.DataFrame([_box()])
    missing = _LogConn(ready=False)
    assert si._write_game_log(missing, 2027, frame) is None
    assert missing.inserted == []
    ready = _LogConn(ready=True)
    assert si._write_game_log(ready, 2027, frame) == 1
    assert ready.inserted[0]["team"] == "Colorado State"
    assert any("g.sport = 'NCAABW'" in q for q in ready.sql)
    again = _LogConn(ready=True, games=[(GAME["game_id"],)])
    assert si._write_game_log(again, 2027, frame) == 0
    assert again.inserted == []


# ── Postgres ─────────────────────────────────────────────────────────────────

psycopg2 = pytest.importorskip("psycopg2")

from data.anon_readable import API_ROLES  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

GAMES_DDL = """
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL,
    game_date TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_score NUMERIC, away_score NUMERIC)
"""


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaabw-player-pg-") as d:
        yield d


@pytest.fixture()
def raw(dsn):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    for role in API_ROLES:
        cur.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    f"'{role}') THEN CREATE ROLE {role}; END IF; END $$")
    cur.execute("DROP VIEW IF EXISTS v_player_season_totals_ncaabw")
    cur.execute("DROP TABLE IF EXISTS games, ncaabw_player_game_log")
    cur.execute(GAMES_DDL)
    cur.execute("INSERT INTO games VALUES (%s, 'NCAABW', 2027, '2026-11-02', "
                "'Colorado State', 'Lindenwood', 71, 68)", (GAME["game_id"],))
    try:
        yield conn
    finally:
        conn.close()


def test_the_migration_applies_twice_and_opens_only_reads(raw):
    cur = raw.cursor()
    cur.execute(SQL)
    cur.execute(SQL)
    cur.execute("SELECT has_table_privilege('anon', 'ncaabw_player_game_log', 'SELECT'), "
                "has_table_privilege('anon', 'ncaabw_player_game_log', 'INSERT'), "
                "has_table_privilege('anon', 'v_player_season_totals_ncaabw', 'SELECT')")
    assert cur.fetchone() == (True, False, True)
    for fn in ("player_window_totals_ncaabw(integer, integer)",
               "player_recent_games_ncaabw(integer, integer, text[])",
               "player_season_stat_values_ncaabw(integer, text)",
               "player_h2h_stat_values_ncaabw(integer[], text, text[], text[])"):
        cur.execute("SELECT has_function_privilege('anon', %s, 'EXECUTE')", (fn,))
        assert cur.fetchone() == (True,), fn


def test_the_stats_reads_answer_for_one_stored_game(raw):
    cur = raw.cursor()
    cur.execute(SQL)
    cur.execute(
        "INSERT INTO ncaabw_player_game_log (game_id, player_id, player_name, team, "
        "team_espn_id, espn_event_id, season, game_date, minutes, points, rebounds, "
        "assists, fg3_made, steals, blocks, source) VALUES "
        "(%s, '36:allie roden', 'Allie Roden', 'Colorado State', 36, 401927946, 2027, "
        "'2026-11-02', 28.4, 16, 7, 4, 2, 1, 0, 'sportsdataverse_ncaa')",
        (GAME["game_id"],))
    cur.execute("SELECT player_name, team, games_played, points, threes, pra "
                "FROM v_player_season_totals_ncaabw WHERE player_id = '36:allie roden'")
    assert cur.fetchone() == ("Allie Roden", "Colorado State", 1, 16, 2, 27)
    cur.execute("SELECT count(*) FROM player_window_totals_ncaabw(2027, 10)")
    assert cur.fetchone() == (1,)
    cur.execute("SELECT player_id, rn, points FROM player_recent_games_ncaabw(2027, 10, "
                "ARRAY['Colorado State'])")
    assert cur.fetchone() == ("36:allie roden", 1, 16)
    cur.execute("SELECT \"values\" FROM player_season_stat_values_ncaabw(2027, 'points') "
                "WHERE player_id = '36:allie roden'")
    assert [float(v) for v in cur.fetchone()[0]] == [16.0]
    cur.execute("SELECT opponent, games, dates FROM player_h2h_stat_values_ncaabw("
                "ARRAY[2027], 'points', ARRAY['Colorado State'], ARRAY['Lindenwood']) "
                "WHERE player_id = '36:allie roden'")
    assert cur.fetchone() == ("Lindenwood", 1, ["2026-11-02"])

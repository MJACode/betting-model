"""
The schema statement splitter.

setup_database() applies data/supabase_schema.sql by splitting it into
statements. It used to split on ";" alone, which silently corrupted the schema
in two ways — see _split_sql_statements' docstring. Both are pinned here
because the failure mode is a production migration dying halfway through.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data.db_setup import SCHEMA_SQL, _load_postgres_schema, _split_sql_statements

SQL_KEYWORDS = ("CREATE", "ALTER", "DROP", "INSERT", "UPDATE", "GRANT", "REVOKE",
                "COMMENT", "DO", "SELECT", "SET", "WITH", "BEGIN", "COMMIT")


class TestSplitter:
    def test_prose_comment_with_semicolon_yields_nothing(self):
        # The exact line that killed the first production migration run.
        line = "-- leaderboard); nba_team_stats stays locked down."
        assert _split_sql_statements(line) == []

    def test_semicolon_inside_string_literal_is_not_a_break(self):
        sql = "INSERT INTO t VALUES ('a;b');"
        assert _split_sql_statements(sql) == ["INSERT INTO t VALUES ('a;b')"]

    def test_dollar_quoted_function_body_stays_one_statement(self):
        sql = ("CREATE FUNCTION f() RETURNS int AS $$ "
               "BEGIN; RETURN 1; END; $$ LANGUAGE plpgsql;")
        assert len(_split_sql_statements(sql)) == 1

    def test_trailing_comment_keeps_the_sql(self):
        sql = "CREATE TABLE x (id INT);  -- note; with a semicolon"
        assert _split_sql_statements(sql) == ["CREATE TABLE x (id INT)"]

    def test_block_comment_is_skipped(self):
        sql = "/* a; b */ CREATE TABLE x (id INT);"
        assert _split_sql_statements(sql) == ["CREATE TABLE x (id INT)"]


class TestRealSchema:
    def test_every_statement_is_sql(self):
        # The regression that matters: no prose fragment may reach Postgres.
        stmts = _split_sql_statements(_load_postgres_schema())
        assert len(stmts) > 100
        bad = [s for s in stmts
               if not s.upper().lstrip("( \n").startswith(SQL_KEYWORDS)]
        assert not bad, f"non-SQL fragments would be executed: {bad[:3]}"


class TestSqliteSchema:
    def _db(self):
        c = sqlite3.connect(":memory:")
        c.executescript(SCHEMA_SQL)
        return c

    def _cols(self, c, table):
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}

    def test_condition_columns_are_on_picks_not_injuries(self):
        # They were briefly added to `injuries` by an anchor that matched the
        # wrong table's created_at. Both halves are asserted.
        c = self._db()
        cond = {"condition_status", "condition_note", "condition_checked_at"}
        assert cond <= self._cols(c, "picks")
        assert not (cond & self._cols(c, "injuries"))

    def test_locked_pick_history_table_exists(self):
        cols = self._cols(self._db(), "nfl_pick_status_history")
        for required in ("pick_id", "game_id", "model_id", "observed_at",
                         "still_qualifies", "status", "reason"):
            assert required in cols

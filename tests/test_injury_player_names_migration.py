"""Worker migration: one row per athlete, so the name seed does not sort injuries."""
from __future__ import annotations

from pathlib import Path

MIG = (
    Path(__file__).parent.parent
    / "data" / "migrations" / "injury_player_names_2026_10_01.sql"
)
CODE = MIG.read_text(encoding="utf-8")


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    from data.db_setup import _split_sql_statements
    stmts = _split_sql_statements(CODE)
    assert len(stmts) == 1
    assert stmts[0].lstrip().upper().startswith("DO ")


def test_it_noops_once_the_table_and_index_exist_and_does_not_lock_up_front():
    """CREATE INDEX still takes ShareLock when executed. The guard returns
    before any DDL, and a contended lock fails fast instead of stalling
    apply-view-migrations."""
    guard = CODE.index("injury_player_names already present")
    create = CODE.index("CREATE INDEX idx_injuries_player_id_created")
    assert CODE.index("IF to_regclass") < guard < create
    assert "RETURN;" in CODE[guard:create]
    assert "lock_timeout" in CODE
    assert "5s" in CODE
    assert "CREATE INDEX CONCURRENTLY" not in CODE


def test_the_backfill_matches_the_index_predicate():
    """A partial index is used only when the query implies its predicate.
    The backfill and the index must name the same filter and the same order."""
    for piece in (
        "player_id IS NOT NULL",
        "player_id <> ''",
        "player_name <> 'Unknown'",
        "ORDER BY player_id, created_at DESC",
        "INCLUDE (player_name)",
    ):
        assert piece in CODE
    assert "PAUSED_MODELS" not in CODE
    assert "model_action_thresholds" not in CODE
    assert "DELETE FROM injuries" not in CODE
    assert "DELETE FROM picks" not in CODE

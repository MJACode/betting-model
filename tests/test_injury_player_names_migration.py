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


def _code(sql: str) -> str:
    """Drop line comments so the prose (which quotes the manual
    CONCURRENTLY statement) is not mistaken for the statement."""
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


STMT = _code(CODE)
INGESTOR = (
    Path(__file__).parent.parent / "data" / "ingestors" / "injury_ingestor.py"
).read_text(encoding="utf-8")


def test_it_noops_once_the_table_and_index_exist_and_does_not_lock_up_front():
    """CREATE INDEX still takes ShareLock when executed. The guard returns
    before any DDL, and a contended lock fails fast instead of stalling
    apply-view-migrations."""
    guard = STMT.index("injury_player_names already present")
    create = STMT.index("CREATE INDEX idx_injuries_player_id_created\n")
    assert STMT.index("IF to_regclass") < guard < create
    assert "RETURN;" in STMT[guard:create]
    assert "set_config('lock_timeout', '5s', true)" in STMT
    assert "CREATE INDEX CONCURRENTLY" not in STMT


def test_a_valid_hand_built_index_is_not_rebuilt():
    """#858 review: Matt builds the index CONCURRENTLY first. The guard is
    pg_index (valid AND ready) plus the full definition, and only a MISSING
    index reaches the in-transaction CREATE INDEX."""
    head = STMT[:STMT.index("CREATE INDEX idx_injuries_player_id_created\n")]
    assert "pg_index" in head
    assert "indisvalid" in head and "indisready" in head
    assert "pg_get_indexdef" in head
    assert "idx_ok" in head
    assert "IF idx_def IS NULL THEN" in head
    # An invalid / different index WARNs and is not touched.
    tail = STMT[STMT.index("ELSIF NOT idx_ok THEN"):]
    assert tail.split("\n", 1)[1].lstrip().startswith("RAISE WARNING")
    # The block never drops anything; the WARNING text only names the fix.
    assert "DROP INDEX" not in STMT.replace("DROP INDEX CONCURRENTLY and rebuild", "")


def test_the_expected_definition_is_what_the_manual_statement_builds():
    """The guard compares pg_get_indexdef against this string (PG 17
    output for the manual CONCURRENTLY statement, checked on a local PG 17).
    The fallback CREATE and the comment must build the same index."""
    for piece in (
        "(player_id, created_at DESC) INCLUDE (player_name)",
        "(player_id IS NOT NULL) AND (player_id <> ''''::text)",
        "(player_name IS NOT NULL) AND (player_name <> ''Unknown''::text)",
    ):
        assert piece in STMT
    assert "ON public.injuries (player_id, created_at DESC)" in CODE
    assert "CREATE INDEX CONCURRENTLY idx_injuries_player_id_created" in CODE


def test_no_backfill_in_the_migration_the_ingestor_fills_an_empty_table():
    """#858 review: the migration ran the 825k-row DISTINCT ON in the same
    transaction as the index build. The ingestor already fills an empty
    names table on its first seed, so the migration does not."""
    assert "INSERT INTO" not in STMT
    assert "DISTINCT ON" not in STMT
    assert "FROM public.injuries" not in STMT
    assert "statement_timeout" not in STMT
    assert "rows = _backfill_player_names(conn)" in INGESTOR


def test_the_ingestor_backfill_matches_the_index_predicate():
    """A partial index is used only when the query implies its predicate.
    The ingestor's backfill and the index must name the same filter and
    the same order."""
    fill = INGESTOR[INGESTOR.index("def _backfill_player_names"):]
    fill = fill[:fill.index("def _name_rows_from_pairs")]
    for piece in (
        "player_id IS NOT NULL",
        "player_id <> ''",
        "player_name IS NOT NULL",
        "player_name <> 'Unknown'",
        "ORDER BY player_id, created_at DESC",
    ):
        assert piece in fill
        assert piece in CODE
    assert "INCLUDE (player_name)" in STMT
    for forbidden in ("PAUSED_MODELS", "model_action_thresholds",
                      "DELETE FROM injuries", "DELETE FROM picks"):
        assert forbidden not in CODE

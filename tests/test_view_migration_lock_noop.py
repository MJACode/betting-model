"""Already-applied view migrations must not take an exclusive lock.

Hourly run b22f8e4fb9e34d27858c341e46ce635c (2026-10-01 17:17Z) failed
apply-view-migrations after 363.733s: 41/44 applied. Postgres
statement_timeout is 2min and lock_timeout is 0. The log in that window is
three ~119s waits:

  * AccessExclusiveLock on push_sent (oid 25944), 17:17:02–17:19:01
  * the statement text of picks_open_nonbet_index, logged 17:19:03
  * AccessExclusiveLock on picks (oid 17680), 17:19:04–17:21:03
  * AccessExclusiveLock on push_sent again, 17:21:05–17:23:04

Those line up with the three files that still issued lock-taking DDL on
every pass after the property already held: ALTER TABLE push_sent ADD
COLUMN IF NOT EXISTS, ALTER TABLE picks ADD COLUMN IF NOT EXISTS, and
discord_publish_state's DROP/CREATE POLICY. CREATE INDEX IF NOT EXISTS
opens the table with ShareLock before the name check; it did not time out
on this run, and it still must not run once the index exists.

pipeline_log stored "see 'View migration FAILED' above" because
_timed_step keeps only the last ERROR line, and that line did not name
the files.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "data" / "migrations"


def _sql(name: str) -> str:
    return (MIG / name).read_text(encoding="utf-8")


def _code(sql: str) -> str:
    """Drop line comments so a marker in the prose is not the statement."""
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def _before(sql: str, marker: str) -> str:
    code = _code(sql)
    assert marker in code, marker
    return code.split(marker, 1)[0]


def test_push_sent_message_id_returns_before_alter():
    sql = _sql("add_message_id_to_push_sent.sql")
    head = _before(sql, "ALTER TABLE")
    assert "information_schema.columns" in head
    assert "message_id" in head
    assert "RETURN" in head


def test_clv_columns_return_before_alter_and_still_stamp_legacy_rows():
    sql = _sql("add_clv_method_2026_09_14.sql")
    head = _before(sql, "ALTER TABLE")
    assert "information_schema.columns" in head
    assert "RETURN" in head or "IF NOT EXISTS" in head
    assert "ADD COLUMN IF NOT EXISTS clv_method" in sql
    assert "ADD COLUMN IF NOT EXISTS clv_close_book" in sql
    assert "clv_method = 'raw_one_sided'" in sql
    # The stamp and the comments are behind their own property checks.
    assert sql.index("IF EXISTS") < sql.index("UPDATE public.picks")
    assert sql.index("IS DISTINCT FROM") < sql.index("COMMENT ON COLUMN")


def test_open_nonbet_index_returns_before_create_index():
    sql = _sql("picks_open_nonbet_index_2026_09_08.sql")
    head = _before(sql, "CREATE INDEX")
    assert "pg_indexes" in head
    assert "idx_picks_open_nonbet" in head
    assert "signal_type" in head and "is_live" in head
    assert "RETURN" in head


def test_discord_publish_state_returns_before_policy_ddl():
    sql = _sql("discord_publish_state_2026_09_23.sql")
    head = _before(sql, "DROP POLICY")
    assert "pg_policy" in head or "polname" in head
    assert "RETURN" in head
    assert "security_invoker" in head
    # The view body itself still does not project the snowflake. The grant
    # check names message_id above the CREATE, which is the point.
    view = sql.split("CREATE OR REPLACE VIEW", 1)[1].split("$v$", 1)[0]
    assert "message_id" not in view


def test_injuries_status_ts_returns_before_alter_and_stays_one_statement():
    sql = _sql("add_injuries_status_ts_2026_09_14.sql")
    assert sql.count("$$") == 2
    assert sql.split("$$")[-1].strip() == ";"
    head = _before(sql, "ALTER TABLE")
    assert "information_schema.columns" in head
    assert "status_ts" in head
    assert "RETURN" in head
    assert "ADD COLUMN IF NOT EXISTS status_ts" in sql


def test_placement_checks_return_before_enable_rls():
    sql = _sql("pick_placement_checks_2026_09_22.sql")
    head = _before(sql, "ENABLE ROW LEVEL SECURITY")
    assert "relrowsecurity" in head
    assert "RETURN" in head
    assert "CREATE TABLE IF NOT EXISTS" in sql


class _LockTimeout(Exception):
    pgcode = "55P03"

    def __init__(self):
        super().__init__("canceling statement due to lock timeout")


class _Syntax(Exception):
    pgcode = "42601"

    def __init__(self):
        super().__init__('syntax error at or near "ALTER"')


class _Conn:
    def __init__(self, errors):
        self.errors = list(errors)
        self.executed: list[str] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql, params=None):
        self.executed.append(sql)
        if sql.lstrip().upper().startswith("SET LOCAL"):
            return None
        if self.errors:
            raise self.errors.pop(0)
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_a_lock_timeout_is_retried_and_then_counts_as_applied(monkeypatch):
    import data.view_migrations as vm
    monkeypatch.setattr(vm.time, "sleep", lambda _s: None)
    conn = _Conn([_LockTimeout(), _LockTimeout()])
    err = vm._apply_one(conn, "add_message_id_to_push_sent.sql", "SELECT 1")
    assert err is None
    assert conn.commits == 1
    assert conn.rollbacks == 2
    # Two failed attempts and the success: three migration statements, each
    # preceded by SET LOCAL.
    sets = [s for s in conn.executed if s.startswith("SET LOCAL")]
    assert len(sets) == 3
    assert "lock_timeout" in sets[0]


def test_a_lock_timeout_that_survives_the_retries_names_the_file(monkeypatch):
    import data.view_migrations as vm
    monkeypatch.setattr(vm.time, "sleep", lambda _s: None)
    conn = _Conn([_LockTimeout(), _LockTimeout(), _LockTimeout()])
    err = vm._apply_one(conn, "discord_publish_state_2026_09_23.sql", "SELECT 1")
    assert err is not None and "lock timeout" in err
    assert conn.commits == 0
    assert conn.rollbacks == vm.LOCK_ATTEMPTS
    line = vm.format_view_migration_failure(
        41, 44, (("discord_publish_state_2026_09_23.sql", err),))
    assert "discord_publish_state_2026_09_23.sql" in line
    assert "41/44" in line


def test_a_real_migration_error_is_not_retried(monkeypatch):
    import data.view_migrations as vm
    slept: list[float] = []
    monkeypatch.setattr(vm.time, "sleep", slept.append)
    conn = _Conn([_Syntax(), _Syntax(), _Syntax()])
    err = vm._apply_one(conn, "add_clv_method_2026_09_14.sql", "SELECT 1")
    assert err is not None and "syntax error" in err
    assert conn.rollbacks == 1
    assert slept == []
    # The leftover errors were not consumed.
    assert len(conn.errors) == 2


def test_the_step_error_is_the_line_pipeline_log_keeps(monkeypatch):
    """_timed_step stores the last ERROR. The filenames have to be in it,
    not only in the per-file line logged earlier."""
    import run_pipeline
    from loguru import logger

    import data.view_migrations as vm
    total = len(vm.ACTIVE_MIGRATIONS)
    failed = (
        ("add_message_id_to_push_sent.sql", "canceling statement due to lock timeout"),
        ("add_clv_method_2026_09_14.sql", "canceling statement due to lock timeout"),
    )
    monkeypatch.setattr(
        vm, "apply_view_migrations",
        lambda: vm.ViewMigrationResult(total - 2, failed))
    captured: list[str] = []
    sink = logger.add(lambda m: captured.append(m.record["message"]), level="ERROR")
    try:
        assert run_pipeline.step_apply_view_migrations("2026-10-01") is False
    finally:
        logger.remove(sink)
    assert captured, "the step logged no error"
    last = captured[-1]
    assert "add_message_id_to_push_sent.sql" in last
    assert "add_clv_method_2026_09_14.sql" in last
    assert "see 'View migration FAILED'" not in last

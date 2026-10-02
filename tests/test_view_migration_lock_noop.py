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
    head = _before(sql, "CREATE INDEX IF NOT EXISTS")
    assert "pg_index" in head and "indisvalid" in head and "indisready" in head
    assert "idx_picks_open_nonbet" in head
    # The whole definition, not keywords.
    assert "pg_get_indexdef" in head
    assert "(signal_type <> ''BET''::text)" in head
    assert "(is_live IS NOT TRUE)" in head
    assert "RETURN" in head


def test_open_nonbet_index_that_is_invalid_or_different_is_left_alone():
    """#857 review: an invalid or differently-defined index of that name
    used to fall through to CREATE INDEX IF NOT EXISTS, which takes
    ShareLock on picks and then no-ops on the name. Now it WARNs and
    returns; only a missing index reaches the CREATE."""
    sql = _code(_sql("picks_open_nonbet_index_2026_09_08.sql"))
    branch = sql.split("IF def IS NOT NULL THEN", 1)[1].split("CREATE INDEX IF NOT EXISTS", 1)[0]
    assert "RAISE WARNING" in branch
    assert branch.rstrip().endswith("END IF;")
    assert "RETURN;" in branch.split("RAISE WARNING", 1)[1]


def test_discord_publish_state_compares_the_whole_view_and_policy():
    """#857 review: keyword checks would skip a future body change."""
    sql = _sql("discord_publish_state_2026_09_23.sql")
    head = _code(_before(sql, "DROP POLICY"))
    assert "want_def" in head and "def IS NOT DISTINCT FROM want_def" in head
    assert "qual IS NOT DISTINCT FROM want_qual" in head
    assert "polcmd" in head and "cmd IS NOT DISTINCT FROM 'r'" in head
    assert "polpermissive" in head and "permissive IS TRUE" in head
    assert "polroles" in head
    assert "roles IS NOT DISTINCT FROM ARRAY['anon', 'authenticated']" in head
    # The expected strings are what PG 17 prints for the DDL in this file.
    assert ("SELECT lock_key, kind FROM push_sent s WHERE kind = ANY "
            in head)
    assert "(ARRAY[''discord_signal''::text, ''discord_live''::text])" in head
    body = sql.split("CREATE OR REPLACE VIEW", 1)[1].split("$v$", 1)[0]
    assert "SELECT s.lock_key, s.kind" in body
    assert "s.kind IN ('discord_signal', 'discord_live')" in body
    policy = sql.split("CREATE POLICY", 1)[1]
    assert "FOR SELECT TO anon, authenticated" in policy
    assert "USING (kind IN ('discord_signal', 'discord_live'))" in policy


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


class _Deadlock(Exception):
    pgcode = "40P01"

    def __init__(self):
        super().__init__("deadlock detected")


class _StatementTimeout(Exception):
    pgcode = "57014"

    def __init__(self):
        super().__init__("canceling statement due to statement timeout")


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
    # Two failed attempts and the success: three executes, each the SET
    # LOCAL and the migration together (see the reconnect test below).
    assert len(conn.executed) == 3
    for sent in conn.executed:
        assert sent.startswith(f"SET LOCAL lock_timeout = '{vm.LOCK_TIMEOUT}';")
        assert sent.endswith("SELECT 1")


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


def test_a_deadlock_is_retried(monkeypatch):
    import data.view_migrations as vm
    slept: list[float] = []
    monkeypatch.setattr(vm.time, "sleep", slept.append)
    conn = _Conn([_Deadlock()])
    err = vm._apply_one(conn, "pick_placement_checks_2026_09_22.sql", "SELECT 1")
    assert err is None
    assert conn.commits == 1 and conn.rollbacks == 1
    assert slept == [vm.LOCK_BACKOFF_S[0]]


def test_a_statement_timeout_is_not_retried(monkeypatch):
    """#857 review: a statement timeout means the migration held its lock and
    worked for the whole 2min statement_timeout. Retrying ran it three times
    and held the lock for ~6 minutes. It fails the file on the first try."""
    import data.view_migrations as vm
    slept: list[float] = []
    monkeypatch.setattr(vm.time, "sleep", slept.append)
    conn = _Conn([_StatementTimeout(), _StatementTimeout(), _StatementTimeout()])
    err = vm._apply_one(conn, "add_clv_method_2026_09_14.sql", "SELECT 1")
    assert err is not None and "statement timeout" in err
    assert len(conn.executed) == 1
    assert conn.rollbacks == 1 and conn.commits == 0
    assert slept == []
    assert len(conn.errors) == 2


def test_only_lock_timeouts_and_deadlocks_are_transient():
    import psycopg2

    import data.view_migrations as vm
    assert vm._is_transient_lock_error(_LockTimeout())
    assert vm._is_transient_lock_error(_Deadlock())
    # Text only (no SQLSTATE): the lock_timeout wording retries ...
    assert vm._is_transient_lock_error(
        RuntimeError("canceling statement due to lock timeout"))
    # ... and a statement timeout does not, with or without its SQLSTATE.
    assert not vm._is_transient_lock_error(_StatementTimeout())
    assert not vm._is_transient_lock_error(
        psycopg2.errors.QueryCanceled("canceling statement due to statement timeout"))
    assert not vm._is_transient_lock_error(
        RuntimeError("canceling statement due to statement timeout"))
    assert not vm._is_transient_lock_error(_Syntax())


def test_a_dropped_connection_replays_the_migration_with_its_lock_timeout(monkeypatch):
    """#857 review: SET LOCAL sent on its own counts as a write in data/db,
    so a pooler drop during the migration raised ConnectionLost and failed
    the file. Sent in the same execute, the transaction is clean when the
    statement starts: the wrapper reconnects and replays both, and the
    replay still carries the 5s lock_timeout."""
    import psycopg2

    import data.db as db
    import data.view_migrations as vm

    class _Cur:
        def __init__(self, c):
            self.c = c

        def execute(self, sql, params=None):
            self.c.executed.append(sql)
            if self.c.drop_next:
                self.c.drop_next = False
                self.c.closed = 2
                raise psycopg2.OperationalError(
                    "server closed the connection unexpectedly")

        def close(self):
            pass

    class _PG:
        def __init__(self, drop_next=False):
            self.closed = 0
            self.drop_next = drop_next
            self.executed: list[str] = []
            self.commits = 0

        def cursor(self):
            if self.closed:
                raise psycopg2.InterfaceError("connection already closed")
            return _Cur(self)

        def commit(self):
            self.commits += 1

        def rollback(self):
            pass

        def close(self):
            self.closed = 1

    opened: list[_PG] = []

    def fake_open(url, options=None):
        opened.append(_PG())
        return opened[-1]

    monkeypatch.setattr(db, "_open", fake_open)
    monkeypatch.setattr(db.time, "sleep", lambda _s: None)
    monkeypatch.setattr(vm.time, "sleep", lambda _s: None)
    first = _PG(drop_next=True)
    conn = db.DBConnection(first, url="postgresql://x")
    body = "DO $mig$ BEGIN RETURN; END $mig$;"
    err = vm._apply_one(conn, "add_message_id_to_push_sent.sql", body)
    assert err is None, err
    assert len(opened) == 1, "one reconnect, no ConnectionLost"
    assert opened[0].commits == 1
    (replayed,) = opened[0].executed
    assert replayed.startswith(f"SET LOCAL lock_timeout = '{vm.LOCK_TIMEOUT}';")
    assert replayed.rstrip().endswith(body)

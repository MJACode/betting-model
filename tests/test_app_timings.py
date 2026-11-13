"""Load-time logging from the mobile app (2026-10-31, Matt: "improve the
performance of the app" -- measure first).

Pinned here:

* the client logic -- mobile/scripts/verify_perf_log.ts, run under node. Each
  property it asserts was watched failing by breaking the code it guards
  (response not passed through, own send timed, query string kept, a poll
  holding a screen open, a request in the quiet gap ignored, rows dropped on a
  failed send, a throwing clock breaking the request, a screen left before it
  loaded dropped, a slow start losing its launch row, no backoff offline,
  a quiet pre-nav read closing the launch as "unknown", a rejected batch
  retried forever);
* the wiring -- the Supabase client fetches through timedFetch, App.tsx starts
  the logger and reports each route;
* the server surface -- add_app_timings.sql is write-only for the anon key, and
  on a real Postgres the RPC inserts, drops a bad kind, caps a call at 100 rows
  and leaves the table unreadable to anon;
* the follow-up -- app_timings_cap_2026_11_01.sql is not in ACTIVE_MIGRATIONS.
  On a real Postgres a signed-in caller shares one hourly budget across device
  ids, one call cannot fill past the room left under 1,000, an oversized
  integer is clamped, and prune_app_timings deletes only rows older than 45 days.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MOBILE = ROOT / "mobile"
MIGRATION = ROOT / "data" / "migrations" / "add_app_timings.sql"


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_the_perf_log_logic_holds():
    from tests._node import NODE, node_strips_types
    if not node_strips_types():
        pytest.skip("node >= 22.6 not available")
    script = (MOBILE / "scripts" / "verify_perf_log.ts").read_text(encoding="utf-8")
    script = script.replace("from '../src/lib/perfLog';", "from './perfLog.ts';")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "verify_perf_log.ts").write_text(script, encoding="utf-8")
        (folder / "perfLog.ts").write_text(
            (MOBILE / "src" / "lib" / "perfLog.ts").read_text(encoding="utf-8"), encoding="utf-8")
        (folder / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        proc = subprocess.run(
            [NODE, "--experimental-strip-types", "verify_perf_log.ts"],
            cwd=folder, capture_output=True, text=True, timeout=120,
        )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "[FAIL]" not in proc.stdout
    for line in (
        "the response is the same object",
        "the error is the same object",
        "a throwing clock still returns the response",
        "no query string is kept",
        "the logger's own send is not timed",
        "the screen is not loaded while a request is still out",
        "a request after JOIN_MS does not hold the screen open",
        "a request in the quiet gap holds the screen open",
        "launch row timed from the launch clock",
        "offline: the rows stay buffered",
        "back online: delivered once",
        "a screen left before it loaded writes its row, status 0",
        "a slow start still gets a launch row, timed from the launch clock",
        "a quiet pre-nav read does not close the launch as unknown",
        "the named first screen still gets the launch row",
        "that launch row runs through the first screen reads, from the launch clock",
        "a rejected batch is dropped instead of retrying forever",
        "after a rejected batch, the next rows still send",
        "offline: no second attempt inside the backoff",
        "offline: the backoff doubles, so one first-backoff later is still too soon",
    ):
        assert f"[PASS] {line}" in proc.stdout, line


def test_perf_log_is_free_of_app_imports():
    """The logic module must run under bare node, so it imports nothing."""
    assert not re.search(r"^import ", _src("mobile/src/lib/perfLog.ts"), flags=re.M)


def test_the_app_is_wired_to_it():
    supa = _src("mobile/src/lib/supabase.ts")
    assert re.search(r"global:\s*\{\s*fetch:\s*timedFetch\(", supa), "the Supabase client must fetch through timedFetch"
    app = _src("mobile/App.tsx")
    assert "startPerfLogging();" in app
    assert "setPerfScreen(name);" in app
    setup = _src("mobile/src/lib/perfLogSetup.ts")
    assert "supabase.rpc('log_app_timings'" in setup


def test_own_rpc_names_agree():
    """The logger skips its own sends by name; a rename on either side would
    make every send log a row about itself."""
    src = _src("mobile/src/lib/perfLog.ts")
    assert "'rpc:log_app_timings'" in src
    assert "CREATE OR REPLACE FUNCTION public.log_app_timings(" in MIGRATION.read_text(encoding="utf-8")


def test_kinds_agree_between_app_and_server():
    src = _src("mobile/src/lib/perfLog.ts")
    app = set(re.findall(r"'([a-z_]+)'", src.split("export type TimingKind =", 1)[1].split(";", 1)[0]))
    sql = MIGRATION.read_text(encoding="utf-8")
    check = re.search(r"kind\s+TEXT NOT NULL CHECK \(kind IN \(([^)]*)\)\)", sql)
    assert check
    assert app == set(re.findall(r"'([a-z_]+)'", check.group(1)))


def test_app_timings_is_write_only_for_the_anon_key():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ALTER TABLE app_timings ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON TABLE app_timings FROM anon, authenticated" in sql
    assert "REVOKE ALL ON SEQUENCE app_timings_id_seq FROM anon, authenticated" in sql
    assert "CREATE POLICY" not in sql
    fn = sql.split("CREATE OR REPLACE FUNCTION public.log_app_timings", 1)[1]
    assert "SECURITY DEFINER" in fn and "SET search_path = public, pg_temp" in fn
    assert "RETURNS VOID" in fn
    assert "ON app_timings (device_id, received_at DESC)" in sql
    from data.anon_readable import RPC_ANON_CALLABLE
    assert "log_app_timings" in RPC_ANON_CALLABLE


# ── the migration on a real Postgres ──────────────────────────────────────────

@pytest.fixture(scope="module")
def dsn():
    from tests._pg import can_scratch, env_dsn, scratch_cluster
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("no scratch Postgres")
    with scratch_cluster("app-timings-pg-") as d:
        yield d


def test_the_rpc_inserts_bounds_and_hides_rows(dsn):
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    for role in ("anon", "authenticated"):
        cur.execute(f"DO $$ BEGIN CREATE ROLE {role}; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    cur.execute("DROP TABLE IF EXISTS app_timings CASCADE")
    cur.execute(MIGRATION.read_text(encoding="utf-8"))
    cur.execute("GRANT USAGE ON SCHEMA public TO anon")

    good = {"kind": "request", "name": "v_public_track_record", "ms": 812, "status": 200,
            "screen": "Tabs", "request_count": None, "since_launch_ms": 4000,
            "occurred_at": "2026-10-31T12:00:00Z"}
    rows = [good] * 120 + [{**good, "kind": "bogus"}]
    cur.execute("SET ROLE anon")
    cur.execute("SELECT log_app_timings(%s, %s::jsonb, %s, %s, %s)",
                ("device-abcdef-1", json.dumps(rows), "1.1.0", "upd-1", "ios 27.2"))
    with pytest.raises(psycopg2.Error):
        cur.execute("SELECT count(*) FROM app_timings")
    cur.execute("RESET ROLE")

    cur.execute("SELECT count(*), min(ms), max(name), min(platform) FROM app_timings")
    n, ms, name, platform = cur.fetchone()
    assert n == 100, "one call is capped at 100 rows"
    assert (ms, name, platform) == (812, "v_public_track_record", "ios 27.2")

    cur.execute("TRUNCATE app_timings")
    cur.execute("SELECT log_app_timings(%s, %s::jsonb)",
                ("device-abcdef-1", json.dumps([{**good, "kind": "bogus"}, {**good, "name": None}])))
    cur.execute("SELECT count(*) FROM app_timings")
    assert cur.fetchone()[0] == 0, "a bad kind or a missing name is dropped, not inserted"

    with pytest.raises(psycopg2.Error):
        cur.execute("SELECT log_app_timings(%s, %s::jsonb)", ("short", "[]"))
    conn.close()


# ── the follow-up: retention, and the hand-applied cap ────────────────────────

CAP = ROOT / "data" / "migrations" / "app_timings_cap_2026_11_01.sql"
_USER = "11111111-1111-1111-1111-111111111111"


def test_retention_is_45_days_and_the_cap_migration_is_hand_applied():
    from data.app_timings_retention import APP_TIMINGS_RETENTION_DAYS, _DELETE
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert APP_TIMINGS_RETENTION_DAYS == 45
    assert "make_interval(days => %s)" in _DELETE
    assert "45 days" in (ROOT / "docs" / "app_timings.md").read_text(encoding="utf-8")
    assert CAP.name not in ACTIVE_MIGRATIONS
    assert "add_app_timings.sql" not in ACTIVE_MIGRATIONS
    sql = CAP.read_text(encoding="utf-8")
    assert "NOT in ACTIVE_MIGRATIONS" in sql
    assert "auth.uid()" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "ADD COLUMN IF NOT EXISTS user_id UUID" in sql
    assert "GRANT EXECUTE" in sql and "TO anon, authenticated" in sql
    # The table stays unreadable. This file must not grant it.
    assert "GRANT SELECT" not in sql and "GRANT INSERT" not in sql
    pipe = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert '"prune-app-timings"' in pipe
    assert 'results["prune_app_timings"] = step_prune_app_timings(run_date)' in pipe
    assert "if not dry_run:" in pipe.split("Step 11c:", 1)[0][-80:]


def test_prune_deletes_only_rows_older_than_the_window():
    from data.app_timings_retention import prune_app_timings

    class _Cur:
        def __init__(self, n):
            self.rowcount = n

    class _Conn:
        def __init__(self):
            self.calls = []
            self.commits = 0
            self.closed = False
        def execute(self, sql, params):
            self.calls.append((sql, params))
            # First batch full, second short: the loop stops.
            return _Cur(2 if len(self.calls) == 1 else 1)
        def commit(self):
            self.commits += 1
        def close(self):
            self.closed = True

    conn = _Conn()
    assert prune_app_timings(conn, days=45, batch=2) == 3
    assert conn.commits == 2 and conn.closed is False
    assert conn.calls[0][1] == (45, 2)
    assert "app_timings" in conn.calls[0][0]


def test_a_missing_table_does_not_fail_the_daily_step(monkeypatch):
    import run_pipeline

    def boom():
        err = Exception('relation "app_timings" does not exist')
        err.pgcode = "42P01"
        raise err

    monkeypatch.setattr("data.app_timings_retention.prune_app_timings", boom)
    assert run_pipeline.step_prune_app_timings("2026-11-01") is True


def test_a_real_prune_failure_marks_the_step_failed(monkeypatch):
    import run_pipeline

    def boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr("data.app_timings_retention.prune_app_timings", boom)
    assert run_pipeline.step_prune_app_timings("2026-11-01") is False


def _auth_uid(cur, user):
    cur.execute("CREATE SCHEMA IF NOT EXISTS auth")
    cur.execute("DROP FUNCTION IF EXISTS auth.uid()")
    cur.execute(
        "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS "
        f"$$ SELECT {user} $$"
    )


def test_the_cap_counts_a_signed_in_caller_and_clamps_integers(dsn):
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    for role in ("anon", "authenticated"):
        cur.execute(
            f"DO $$ BEGIN CREATE ROLE {role}; EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
    cur.execute("DROP TABLE IF EXISTS app_timings CASCADE")
    cur.execute("DROP FUNCTION IF EXISTS public.log_app_timings(TEXT, JSONB, TEXT, TEXT, TEXT)")
    cur.execute(MIGRATION.read_text(encoding="utf-8"))
    cur.execute(CAP.read_text(encoding="utf-8"))
    cur.execute("GRANT USAGE ON SCHEMA public TO anon")
    _auth_uid(cur, "NULL::uuid")

    good = {"kind": "request", "name": "picks", "ms": 10, "status": 200,
            "screen": "Tabs", "request_count": 1, "since_launch_ms": 4,
            "occurred_at": "2026-11-01T12:00:00.000Z"}
    cur.execute(
        "INSERT INTO app_timings (device_id, kind, name, ms) "
        "SELECT 'device-abcdef-1', 'request', 'picks', 1 FROM generate_series(1, 950)"
    )
    cur.execute("SET ROLE anon")
    rows = [{**good, "since_launch_ms": 9999999999999, "status": 99999, "request_count": -4}] * 120
    cur.execute(
        "SELECT log_app_timings(%s, %s::jsonb, %s, %s, %s)",
        ("device-abcdef-1", json.dumps(rows), "1.1.0", None, "ios"),
    )
    cur.execute("RESET ROLE")
    cur.execute(
        "SELECT count(*), max(since_launch_ms), max(status), min(request_count) "
        "FROM app_timings WHERE since_launch_ms IS NOT NULL"
    )
    n, since, status, reqs = cur.fetchone()
    assert n == 50, "950 already stored, so one call may fill only the room left under 1,000"
    assert (since, status, reqs) == (2147483647, 599, 0)

    # A value that does not fit in INTEGER must not abort the call.
    cur.execute("SET ROLE anon")
    cur.execute(
        "SELECT log_app_timings(%s, %s::jsonb)",
        ("device-abcdef-2", json.dumps([{**good, "ms": 10 ** 20}])),
    )
    cur.execute("RESET ROLE")
    cur.execute("SELECT count(*) FROM app_timings WHERE device_id = 'device-abcdef-2'")
    assert cur.fetchone()[0] == 0, "a non-integer ms is dropped, not a failed batch"

    # Signed in: two device ids share one user budget.
    cur.execute("TRUNCATE app_timings")
    _auth_uid(cur, f"'{_USER}'::uuid")
    cur.execute(
        "INSERT INTO app_timings (device_id, user_id, kind, name, ms) "
        "SELECT 'device-abcdef-1', %s::uuid, 'request', 'picks', 1 FROM generate_series(1, 1000)",
        (_USER,),
    )
    cur.execute("SET ROLE anon")
    cur.execute(
        "SELECT log_app_timings(%s, %s::jsonb)",
        ("device-abcdef-9", json.dumps([good])),
    )
    cur.execute("RESET ROLE")
    cur.execute("SELECT count(*) FROM app_timings WHERE device_id = 'device-abcdef-9'")
    assert cur.fetchone()[0] == 0, "rotating device_id does not open a new budget for a signed-in caller"
    cur.execute("SELECT count(*) FROM app_timings WHERE user_id = %s", (_USER,))
    assert cur.fetchone()[0] == 1000

    # And the rows this caller does write carry that user id.
    cur.execute("TRUNCATE app_timings")
    cur.execute("SET ROLE anon")
    cur.execute(
        "SELECT log_app_timings(%s, %s::jsonb)",
        ("device-abcdef-9", json.dumps([good])),
    )
    cur.execute("RESET ROLE")
    cur.execute("SELECT user_id::text, ms FROM app_timings")
    assert cur.fetchone() == (_USER, 10)

    # Anonymous again: the other device is its own budget.
    _auth_uid(cur, "NULL::uuid")
    cur.execute("SET ROLE anon")
    cur.execute(
        "SELECT log_app_timings(%s, %s::jsonb)",
        ("device-abcdef-8", json.dumps([good])),
    )
    cur.execute("RESET ROLE")
    cur.execute(
        "SELECT device_id, user_id IS NULL FROM app_timings WHERE device_id = 'device-abcdef-8'"
    )
    assert cur.fetchone() == ("device-abcdef-8", True)
    conn.close()


def test_prune_on_postgres_keeps_the_recent_rows(dsn):
    psycopg2 = pytest.importorskip("psycopg2")
    from data.app_timings_retention import prune_app_timings

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS app_timings CASCADE")
    cur.execute(MIGRATION.read_text(encoding="utf-8"))
    cur.execute(
        "INSERT INTO app_timings (device_id, kind, name, ms, received_at) VALUES "
        "('device-abcdef-1', 'request', 'old', 1, now() - interval '46 days'),"
        "('device-abcdef-1', 'request', 'keep', 1, now() - interval '44 days'),"
        "('device-abcdef-1', 'launch', 'Tabs', 1, now())"
    )
    conn.autocommit = False

    class _Wrap:
        def __init__(self, raw):
            self.raw = raw
        def execute(self, sql, params=None):
            c = self.raw.cursor()
            c.execute(sql, params)
            return c
        def commit(self):
            self.raw.commit()

    assert prune_app_timings(_Wrap(conn), days=45, batch=1) == 1
    cur = conn.cursor()
    cur.execute("SELECT name FROM app_timings ORDER BY name")
    assert [r[0] for r in cur.fetchall()] == ["Tabs", "keep"]
    conn.close()

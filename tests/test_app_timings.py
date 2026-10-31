"""Load-time logging from the mobile app (2026-10-31, Matt: "improve the
performance of the app" -- measure first).

Three halves are pinned here:

* the client logic -- mobile/scripts/verify_perf_log.ts, run under node. Each
  property it asserts was watched failing by breaking the code it guards
  (response not passed through, own send timed, query string kept, a poll
  holding a screen open, a request in the quiet gap ignored, rows dropped on a
  failed send, a throwing clock breaking the request);
* the wiring -- the Supabase client fetches through timedFetch, App.tsx starts
  the logger and reports each route;
* the server surface -- add_app_timings.sql is write-only for the anon key, and
  on a real Postgres the RPC inserts, drops a bad kind, caps a call at 100 rows
  and leaves the table unreadable to anon.
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

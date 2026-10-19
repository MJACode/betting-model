"""Crash logging from the mobile app (2026-10-19, Matt: "Set up crash logging").

The app had no crash reporting and no error boundary, so a crash on first open
left nothing to trace. Two halves are pinned here:

* the client logic -- mobile/scripts/verify_crash_log.ts, run under node. Each
  property it asserts was watched failing by breaking the code it guards
  (fatal handler not waiting, a failed send dropped, an ota_reload marker
  ignored, nothing stored before the send);
* the server surface -- add_app_errors.sql is write-only for the anon key:
  RLS on, table grants revoked by name, one SECURITY DEFINER insert function.
"""

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MOBILE = ROOT / "mobile"
MIGRATION = ROOT / "data" / "migrations" / "add_app_errors.sql"


def test_the_crash_log_logic_holds():
    from tests._node import NODE, node_strips_types
    if not node_strips_types():
        pytest.skip("node >= 22.6 not available")
    script = (MOBILE / "scripts" / "verify_crash_log.ts").read_text(encoding="utf-8")
    script = re.sub(r"from '\.\./src/lib/crashLog';", "from './crashLog.ts';", script)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "verify_crash_log.ts").write_text(script, encoding="utf-8")
        (folder / "crashLog.ts").write_text(
            (MOBILE / "src" / "lib" / "crashLog.ts").read_text(encoding="utf-8"), encoding="utf-8")
        (folder / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        proc = subprocess.run(
            [NODE, "--experimental-strip-types", "verify_crash_log.ts"],
            cwd=folder, capture_output=True, text=True, timeout=60,
        )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "[FAIL]" not in proc.stdout
    for line in (
        "the report was in storage when the send began",
        "offline: the report stays queued",
        "fatal: the native handler ran after the report was sent",
        "fatal with a hung send: the native handler still runs within FATAL_FLUSH_MS",
        "died at ota_reload: reported as early_exit with that stage",
    ):
        assert f"[PASS] {line}" in proc.stdout, line


def test_crash_log_is_free_of_app_imports():
    """The logic module must run under bare node, so it imports nothing."""
    src = (MOBILE / "src" / "lib" / "crashLog.ts").read_text(encoding="utf-8")
    assert not re.search(r"^import ", src, flags=re.M)


def test_app_errors_is_write_only_for_the_anon_key():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ALTER TABLE app_errors ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON TABLE app_errors FROM anon, authenticated" in sql
    assert "REVOKE ALL ON SEQUENCE app_errors_id_seq FROM anon, authenticated" in sql
    assert "CREATE POLICY" not in sql
    fn = sql.split("CREATE OR REPLACE FUNCTION public.log_app_error", 1)[1]
    assert "SECURITY DEFINER" in fn and "SET search_path = public, pg_temp" in fn
    assert "RETURNS VOID" in fn, "the RPC must not hand rows back to the caller"
    assert re.search(r"GRANT EXECUTE ON FUNCTION public\.log_app_error\([^)]*\)\s*TO anon, authenticated", sql)


def test_kinds_agree_between_app_and_server():
    sql = MIGRATION.read_text(encoding="utf-8")
    src = (MOBILE / "src" / "lib" / "crashLog.ts").read_text(encoding="utf-8")
    app = set(re.findall(r"'([a-z_]+)'", src.split("export type ReportKind =", 1)[1].split(";", 1)[0]))
    check = re.search(r"kind\s+TEXT NOT NULL CHECK \(kind IN\s*\(([^)]*)\)\)", sql)
    assert check, "app_errors.kind CHECK not found"
    server = set(re.findall(r"'([a-z_]+)'", check.group(1)))
    assert app == server, (app, server)


def test_the_app_calls_the_rpc_and_mounts_the_boundary():
    setup = (MOBILE / "src" / "lib" / "crashLogSetup.ts").read_text(encoding="utf-8")
    assert "rpc('log_app_error'" in setup
    app = (MOBILE / "App.tsx").read_text(encoding="utf-8")
    assert "startCrashLogging();" in app
    assert "<AppErrorBoundary onReset={resetNav}>" in app and "</AppErrorBoundary>" in app
    assert "setNavReady(false)" in app, "Retry must reset navReady so a pending deep link replays"
    ota = (MOBILE / "src" / "hooks" / "useOtaUpdates.ts").read_text(encoding="utf-8")
    body = ota.split("reloadAsync: async () => {", 1)[1]
    assert body.index("markOtaReload()") < body.index("Updates.reloadAsync()"), \
        "the ota_reload stage must be written before the reload starts"


def test_the_fallback_never_renders_blank():
    """ErrorState renders nothing for an abort-shaped error. The boundary must
    not hand it the caught error, or an aborted fetch rethrown in render is a
    blank screen with no Retry (UX review, 2026-10-19). It must branch on a
    flag, not the error, so `throw 0` cannot re-render the children."""
    src = (MOBILE / "src" / "components" / "AppErrorBoundary.tsx").read_text(encoding="utf-8")
    tag = src.split("<ErrorState", 1)[1].split("/>", 1)[0]
    assert "error={null}" in tag, tag
    assert "if (this.state.hasError)" in src
    assert "<ScrollView" in src, "Retry must stay reachable at the largest text sizes"

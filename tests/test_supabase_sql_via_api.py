"""Read-only Supabase queries answered by the hook itself, so no connector
permission prompt is shown (mike, 2026-11-26: the claude.ai connector setting
asks before every `execute_sql`, in every chat, and he cannot change it).

The hook sends a query that already passed the write check to Supabase's
read-only query endpoint (it runs as `supabase_read_only_user`) and hands the
rows back as the hook's answer. When that route is not available (no token, an
auth error, the network), it falls back to the old behaviour: allow the MCP
call inside BEGIN READ ONLY, which shows the prompt as before.

These tests run the hook as a subprocess against a local fake of the API, so
they never touch the network.
"""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "picks_read_only_guard.py"
BASH_GUARD = ROOT / ".claude" / "hooks" / "supabase_api_bash_guard.py"


class _Fake:
    status = 201
    body = b"[]"
    seen = []


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        _Fake.seen.append({
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "body": json.loads(self.rfile.read(n) or b"{}"),
        })
        self.send_response(_Fake.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(_Fake.body)

    def log_message(self, *a):
        pass


@pytest.fixture
def api():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _Fake.seen = []
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _run(sql, api_url, tool="mcp__Supabase__execute_sql", **env):
    payload = {"tool_name": tool, "tool_input": {"query": sql}}
    e = {"SUPABASE_API_URL": api_url, "PATH": "", "SYSTEMROOT": ""}
    e.update(env)
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=e, timeout=60)


def test_read_is_answered_by_the_hook_without_the_mcp_call(api):
    _Fake.status, _Fake.body = 201, json.dumps([{"n": 7}]).encode()
    r = _run("SELECT count(*) AS n FROM picks", api)
    assert r.returncode == 2, r.stderr
    assert '"n": 7' in r.stderr
    assert "ANSWERED WITHOUT A PROMPT" in r.stderr
    sent = _Fake.seen[-1]
    assert sent["path"] == "/v1/projects/vvprgnrmzeekokzkrkfu/database/query/read-only"
    assert sent["body"] == {"query": "SELECT count(*) AS n FROM picks"}
    assert sent["auth"].startswith("Bearer ")


def test_a_token_in_the_environment_is_sent(api):
    _Fake.status, _Fake.body = 200, b"[]"
    _run("SELECT 1", api, SUPABASE_ACCESS_TOKEN="sbp_local")
    assert _Fake.seen[-1]["auth"] == "Bearer sbp_local"


@pytest.mark.parametrize("status", [401, 403, 404, 500, 503])
def test_no_api_route_falls_back_to_the_mcp_call(api, status):
    _Fake.status, _Fake.body = status, b'{"message":"nope"}'
    r = _run("SELECT 1 FROM picks;", api)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "allow"
    assert out["updatedInput"]["query"].startswith("BEGIN READ ONLY;")


def test_unreachable_api_falls_back():
    r = _run("SELECT 1", "http://127.0.0.1:9")
    assert r.returncode == 0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_role_permission_error_falls_back(api):
    _Fake.status = 400
    _Fake.body = b'{"message":"ERROR: 42501: permission denied for table secret"}'
    r = _run("SELECT * FROM secret", api)
    assert r.returncode == 0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_sql_error_is_returned_like_the_mcp_would(api):
    _Fake.status = 400
    _Fake.body = b'{"message":"ERROR: 42P01: relation \\"nope\\" does not exist"}'
    r = _run("SELECT * FROM nope", api)
    assert r.returncode == 2
    assert "does not exist" in r.stderr


def test_switch_off_skips_the_api(api):
    r = _run("SELECT 1", api, SUPABASE_SQL_VIA_API="0")
    assert r.returncode == 0 and _Fake.seen == []


def test_write_never_reaches_the_api(api):
    r = _run("UPDATE picks SET result='WIN'", api)
    assert r.returncode == 2 and "READ-ONLY" in r.stderr
    assert _Fake.seen == []


def test_large_results_are_cut(api):
    _Fake.status = 200
    _Fake.body = json.dumps([{"x": "y" * 1000}] * 400).encode()
    r = _run("SELECT x FROM t", api)
    assert r.returncode == 2
    assert len(r.stderr) < 120_000 and "cut at" in r.stderr


# --- the token reaches api.supabase.com, so a Bash call must not use it ---

def _bash(cmd):
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    return subprocess.run([sys.executable, str(BASH_GUARD)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("cmd", [
    "curl -X POST https://api.supabase.com/v1/projects/x/database/query -d '{}'",
    "python -c \"import requests; requests.post('https://api.supabase.com/v1/projects/x')\"",
    "wget -qO- https://API.SUPABASE.COM/v1/projects",
])
def test_bash_calls_to_the_management_api_are_refused(cmd):
    r = _bash(cmd)
    assert r.returncode == 2 and "READ-ONLY" in r.stderr


@pytest.mark.parametrize("cmd", [
    "grep -rn api.supabase.com docs/",
    "python -m pytest -q tests/test_supabase_sql_via_api.py",
    "curl -s https://vvprgnrmzeekokzkrkfu.supabase.co/rest/v1/",
])
def test_other_bash_calls_pass(cmd):
    assert _bash(cmd).returncode == 0


def test_bash_guard_is_wired_in_settings():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for e in settings["hooks"]["PreToolUse"]
            for h in e["hooks"] if "Bash" in e.get("matcher", "")]
    assert any("supabase_api_bash_guard.py" in c for c in cmds)


def test_execute_sql_hook_has_time_for_the_api():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    for e in settings["hooks"]["PreToolUse"]:
        if "execute_sql" in e.get("matcher", ""):
            assert all(h.get("timeout", 0) >= 60 for h in e["hooks"])

"""The Supabase-MCP guard: Claude reads the model picks, never writes them
(Matt, 2026-11-21; CLAUDE.md §1b)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "picks_read_only_guard.py"

_spec = importlib.util.spec_from_file_location("picks_guard", HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

WRITES = [
    "UPDATE picks SET result='WIN' WHERE id=1",
    "update public.picks set dk_odds=-110",
    'DELETE FROM "picks" WHERE id = 5',
    "INSERT INTO picks (model_id) VALUES ('x')",
    "insert into picks_log select * from picks",
    "TRUNCATE picks",
    "truncate table results_snapshots",
    "ALTER TABLE picks ADD COLUMN x int",
    "DROP TABLE IF EXISTS picks_log",
    "WITH x AS (SELECT 1) UPDATE picks SET result = NULL",
    "MERGE INTO picks USING t ON true WHEN MATCHED THEN DELETE",
    "BEGIN; SELECT 1; UPDATE\n  picks\n SET result='LOSS'; COMMIT;",
    "CREATE TRIGGER t BEFORE UPDATE ON picks FOR EACH ROW EXECUTE FUNCTION f()",
]

READS = [
    "SELECT * FROM picks WHERE signal_type='BET'",
    "BEGIN READ ONLY; SELECT count(*) FROM picks; COMMIT;",
    "SELECT model_id, sum(profit_flat) FROM picks GROUP BY 1",
    "-- UPDATE picks SET x=1\nSELECT 1",
    "SELECT * FROM v_discord_published JOIN picks USING (id)",
    "UPDATE worker_jobs SET status='done' WHERE id=1",  # not a picks table
    "SELECT updated_at FROM picks",
]


@pytest.mark.parametrize("sql", WRITES)
def test_writes_to_picks_are_blocked(sql):
    assert guard.blocked_reason(sql) is not None, sql


@pytest.mark.parametrize("sql", READS)
def test_reads_pass(sql):
    assert guard.blocked_reason(sql) is None, sql


def _run(sql):
    payload = {"tool_name": "mcp__Supabase__execute_sql",
               "tool_input": {"project_id": "p", "query": sql}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True)


def test_hook_process_exits_2_on_write_and_0_on_read():
    w = _run("UPDATE picks SET result='WIN'")
    assert w.returncode == 2 and "READ-ONLY" in w.stderr
    assert _run("SELECT 1 FROM picks").returncode == 0


def test_hook_is_wired_in_settings():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for e in settings["hooks"]["PreToolUse"]
            for h in e["hooks"] if "execute_sql" in e.get("matcher", "")]
    assert any("picks_read_only_guard.py" in c for c in cmds)


def test_rule_is_in_claude_md():
    assert "THE MODEL PICKS ARE READ-ONLY FOR CLAUDE" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

"""The Supabase-MCP guard: every table is read-only for Claude
(Matt, 2026-11-21 and 2026-11-22; CLAUDE.md §1b)."""
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
    "TRUNCATE results_snapshots",
    "ALTER TABLE picks ADD COLUMN x int",
    "DROP TABLE IF EXISTS picks_log",
    "WITH x AS (SELECT 1) UPDATE picks SET result = NULL",
    "MERGE INTO picks USING t ON true WHEN MATCHED THEN DELETE",
    # every table, not just the picks
    "INSERT INTO worker_jobs (job_type) VALUES ('x')",
    "UPDATE model_action_thresholds SET min_edge = 0",
    "DELETE FROM games",
    "CREATE TABLE scratch (i int)",
    "CREATE OR REPLACE VIEW open_picks AS SELECT 1",
    "GRANT SELECT ON picks TO anon",
    "SELECT * INTO picks_copy FROM picks",
    "REFRESH MATERIALIZED VIEW mv_scored_pick_outcomes",
    "DO $$ BEGIN DELETE FROM picks; END $$",
    "CALL some_proc()",
    # escaping the read-only wrapper
    "SELECT 1; COMMIT; DELETE FROM picks",
    "SET TRANSACTION READ WRITE",
    "set session characteristics as transaction read write",
    "BEGIN; UPDATE picks SET x=1; COMMIT;",
]

READS = [
    "SELECT * FROM picks WHERE signal_type='BET'",
    "SELECT model_id, sum(profit_flat) FROM picks GROUP BY 1",
    "-- UPDATE picks SET x=1\nSELECT 1",
    "SELECT * FROM v_discord_published JOIN picks USING (id)",
    "SELECT updated_at, created_at FROM picks",
    "WITH b AS (SELECT * FROM picks) SELECT count(*) FROM b",
    "SELECT * FROM picks WHERE pick_label = 'Update: BUF +1'",
    'SELECT "Drop Zone" FROM t',
    "SELECT * FROM open_picks;",
]


@pytest.mark.parametrize("sql", WRITES)
def test_writes_are_blocked(sql):
    assert guard.blocked_reason(sql) is not None, sql


@pytest.mark.parametrize("sql", READS)
def test_reads_pass(sql):
    assert guard.blocked_reason(sql) is None, sql


def _run(tool, sql):
    payload = {"tool_name": tool, "tool_input": {"project_id": "p", "query": sql}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True)


def test_write_exits_2():
    w = _run("mcp__Supabase__execute_sql", "UPDATE worker_jobs SET status='x'")
    assert w.returncode == 2 and "READ-ONLY" in w.stderr


def test_read_is_rewritten_inside_a_read_only_transaction():
    r = _run("mcp__Supabase__execute_sql", "SELECT 1 FROM picks;")
    assert r.returncode == 0
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "allow"
    q = out["updatedInput"]["query"]
    assert q.startswith("BEGIN READ ONLY;") and q.endswith("ROLLBACK;")
    assert "SELECT 1 FROM picks;" in q
    assert out["updatedInput"]["project_id"] == "p"


def test_apply_migration_is_refused():
    r = _run("mcp__Supabase__apply_migration", "CREATE INDEX i ON picks(id)")
    assert r.returncode == 2


def test_hook_is_wired_in_settings():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for e in settings["hooks"]["PreToolUse"]
            for h in e["hooks"] if "execute_sql" in e.get("matcher", "")]
    assert any("picks_read_only_guard.py" in c for c in cmds)


def test_rule_is_in_claude_md():
    assert "THE DATABASE IS READ-ONLY FOR CLAUDE" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

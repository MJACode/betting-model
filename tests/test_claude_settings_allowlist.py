"""Write-capable Supabase MCP tools stay prompted.

PR #1067 allow-listed read-only Supabase tools in `.claude/settings.json` so a
session skips the permission prompt. `execute_sql` was on that list. It runs
read-only only when the Supabase MCP connection is started that way
(`--read-only` or `read_only=true` on the server URL). That flag lives on the
connection, not in this repo: `.mcp.json` is `{"mcpServers": {}}`, and the two
prefixes this file names are the claude.ai account connector
(`mcp__claude_ai_Supabase__*`) and a user-local `mcp__Supabase__*` server.
A committed project server would be a third connection. `read_only=true`
is a query parameter on that server's URL, so it would not change either
prefix already named here. The claude.ai connector is configured on the
account (`docs/rules_evidence.md`). A 2026-10-19 session recorded
`execute_sql` writing (`docs/sessions/2026-10.md`).

So `execute_sql` is write-capable here, same as `apply_migration`. An allow
entry, or a wildcard that covers one, would run UPDATE/DELETE/DROP against
production with no prompt on any connection that is not read-only.
"""
from __future__ import annotations

import fnmatch
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = os.path.join(ROOT, ".claude", "settings.json")

# Tool names that mutate production, spend money, or run arbitrary SQL.
# `execute_sql` is in this set because read-only is a connection flag, not a
# property of the tool. Review on #1067 (5683667946) named the rest.
WRITE_CAPABLE = frozenset({
    "apply_migration",
    "deploy_edge_function",
    "create_branch",
    "merge_branch",
    "delete_branch",
    "reset_branch",
    "rebase_branch",
    "pause_project",
    "restore_project",
    "create_project",
    "execute_sql",
})


def _allow_rules() -> list[str]:
    with open(SETTINGS, encoding="utf-8") as handle:
        payload = json.load(handle)
    allow = payload.get("permissions", {}).get("allow", [])
    assert isinstance(allow, list), "permissions.allow must be a list"
    return allow


def _covers_write(rule: str) -> str | None:
    """Return one write-capable tool this allow rule would approve, if any.

    Claude Code matches `mcp__<server>` and `mcp__<server>__*` to every tool
    on that server, and `*` only in the tool segment (`mcp__server__execute_*`).
    A wildcard is judged only on a Supabase server. An exact tool name is
    judged on any server: `execute_sql` is the same prompt bypass wherever
    the prefix sits. `*` on a non-Supabase server is not this list's subject.
    """
    base = rule.split("(", 1)[0].strip()
    parts = base.split("__")
    if len(parts) < 2 or parts[0] != "mcp":
        return None
    supabase = "supabase" in parts[1].lower()
    if len(parts) == 2:
        return base if supabase else None
    tool = parts[-1]
    wildcard = any(ch in tool for ch in "*?[]")
    if wildcard and not supabase:
        return None
    for name in sorted(WRITE_CAPABLE):
        if fnmatch.fnmatchcase(name, tool):
            return name
    return None


def test_permissions_allow_has_no_write_capable_supabase_tool() -> None:
    offenders = {
        rule: hit
        for rule in _allow_rules()
        if (hit := _covers_write(rule)) is not None
    }
    assert not offenders, (
        "permissions.allow auto-approves a write-capable Supabase tool: "
        + ", ".join(f"{rule} -> {hit}" for rule, hit in sorted(offenders.items()))
        + ". Read-only is a connection flag this repo does not pin "
        "(.mcp.json is empty; the claude.ai connector is account-side). "
        "Drop the entry so the call stays prompted."
    )


def test_supabase_wildcards_cover_execute_sql_and_reads_do_not() -> None:
    """The file check above is exact names. These are the shapes that sneak past it."""
    assert _covers_write("mcp__Supabase__execute_sql") == "execute_sql"
    assert _covers_write("mcp__claude_ai_Supabase__execute_sql") == "execute_sql"
    assert _covers_write("mcp__Supabase__*") == "apply_migration"
    assert _covers_write("mcp__claude_ai_Supabase__execute_*") == "execute_sql"
    assert _covers_write("mcp__claude_ai_Supabase") == "mcp__claude_ai_Supabase"
    assert _covers_write("mcp__Supabase__list_tables") is None
    assert _covers_write("mcp__claude_ai_Supabase__query_logs") is None
    assert _covers_write("mcp__Railway__*") is None

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

2026-11-17: "Matt asked for SQL to run without approval prompts in every
session" (PR #1437, which allow-listed `execute_sql` and `apply_migration` on
the two servers named above). Those four allow entries are approved, and only
as those exact strings. Any other server, spelling or letter case, and any
wildcard, is still refused: no wildcard was approved, and one like
`mcp__Supabase__*` would also cover the branch, deploy and project tools
below. Every other write-capable tool stays prompted. The no-deletion rule
(CLAUDE.md 1b) still governs what that SQL may do; this file only governs
whether it is prompted.
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


# The allow entries Matt approved (2026-11-17, PR #1437), as whole strings: the
# two tools on the two servers #1437 named. A rule is approved only if it is one
# of these exactly, so a look-alike server ("supabase_staging"), another letter
# case, a suffix or a wildcard still goes through `_covers_write` and fails.
APPROVED_RULES = frozenset({
    "mcp__Supabase__execute_sql",
    "mcp__Supabase__apply_migration",
    "mcp__claude_ai_Supabase__execute_sql",
    "mcp__claude_ai_Supabase__apply_migration",
})


def _approved(rule: str) -> bool:
    return rule in APPROVED_RULES


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
        if not _approved(rule) and (hit := _covers_write(rule)) is not None
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


def test_only_exact_approved_names_pass() -> None:
    """Matt's approval covers four exact entries, never a wildcard or another tool."""
    for rule in APPROVED_RULES:
        assert _approved(rule)
    assert not _approved("mcp__Supabase__execute_*")
    assert not _approved("mcp__Supabase__*")
    assert not _approved("mcp__claude_ai_Supabase")
    assert not _approved("mcp__Supabase__delete_branch")
    assert not _approved("mcp__Supabase__pause_project")
    # Look-alike servers, letter case and padding: each would be honoured as an
    # exact allow rule on that server, and none of them was approved.
    assert not _approved("mcp__Railway__execute_sql")
    assert not _approved("mcp__notsupabase__execute_sql")
    assert not _approved("mcp__supabase_staging__execute_sql")
    assert not _approved("mcp__supabase__execute_sql")
    assert not _approved("mcp__SUPABASE__apply_migration")
    assert not _approved("mcp__supabase__x__execute_sql")
    assert not _approved(" mcp__Supabase__execute_sql ")


def test_look_alike_server_fails_the_guard() -> None:
    """End to end: an unapproved spelling of an approved tool is still flagged."""
    for rule in ("mcp__supabase_staging__execute_sql", "mcp__supabase__apply_migration"):
        assert not _approved(rule) and _covers_write(rule) is not None, rule

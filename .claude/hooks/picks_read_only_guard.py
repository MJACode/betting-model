"""PreToolUse guard: Claude may READ the model picks through the Supabase MCP,
never WRITE them (Matt, 2026-11-21: "never touch the actual model picks, but
use that data").

Runs on every Supabase `execute_sql` / `apply_migration` call. If the SQL
would insert, update, delete, truncate, alter or drop a protected table, the
call is blocked (exit 2) and the reason goes back to Claude. Reads pass.

This governs Claude's MCP route only. The pipeline writes picks through
DATABASE_URL and is untouched by this hook.
"""
from __future__ import annotations

import json
import re
import sys

# Tables that hold the model picks and the record built from them.
PROTECTED = r"(?:picks\w*|results_snapshots)"

_TARGET = r'(?:only\s+)?(?:"?public"?\s*\.\s*)?"?' + PROTECTED + r'"?\b'

WRITE_RE = re.compile(
    r"\b(?:"
    r"insert\s+into|update|delete\s+from|merge\s+into|"
    r"truncate(?:\s+table)?|alter\s+table(?:\s+if\s+exists)?|"
    r"drop\s+(?:table|view|materialized\s+view)(?:\s+if\s+exists)?|"
    r"copy|create\s+(?:or\s+replace\s+)?(?:trigger|rule)\b[^;]*?\bon"
    r")\s+" + _TARGET,
    re.IGNORECASE | re.DOTALL,
)


def blocked_reason(sql: str) -> str | None:
    # Strip comments so a commented-out write does not block, and a write
    # cannot hide behind one.
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    m = WRITE_RE.search(sql)
    if not m:
        return None
    return (
        "BLOCKED: the model picks are READ-ONLY for Claude (Matt, 2026-11-21, "
        "CLAUDE.md §1b). This statement writes a protected table: "
        f"'{m.group(0).strip()}'. Query the data with SELECT; any change to "
        "picks needs Matt's explicit approval in chat and goes through the "
        "sanctioned script, not the MCP."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    sql = tool_input.get("query") or tool_input.get("sql") or ""
    reason = blocked_reason(sql)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

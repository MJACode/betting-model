"""PreToolUse guard: the database is READ-ONLY for Claude through the Supabase
MCP. Every table, not only the picks (Matt, 2026-11-21: "never touch the
actual model picks, but use that data"; 2026-11-22: "all should be
protected").

Two layers on every Supabase `execute_sql` call:

1. A statement that writes, changes schema, changes permissions or controls
   the transaction is refused (exit 2) before it is sent.
2. Whatever passes is rewritten to run inside `BEGIN READ ONLY; ... ROLLBACK;`,
   so Postgres itself refuses any write the first layer did not recognise
   (a function with side effects, `nextval()`, ...).

`apply_migration` is refused outright: migrations land through a reviewed PR
and the worker's `data.view_migrations`, never from a chat.

This governs Claude's MCP route only. The pipeline writes through
DATABASE_URL and is untouched by this hook.
"""
from __future__ import annotations

import json
import re
import sys

WRITE_KEYWORDS = (
    r"insert|update|delete|merge|upsert|truncate|alter|drop|create|grant|revoke|"
    r"copy|comment|refresh|vacuum|analy[sz]e|reindex|cluster|call|do|lock|"
    r"security\s+label|import|reassign|discard|load|listen|notify|"
    r"prepare|execute|deallocate|savepoint|release|"
    r"begin|start|commit|end|rollback|abort|set|reset"
)
WRITE_RE = re.compile(r"\b(?:" + WRITE_KEYWORDS + r")\b", re.IGNORECASE)
# SELECT ... INTO new_table creates a table.
SELECT_INTO_RE = re.compile(r"\bselect\b[^;]*?\binto\b", re.IGNORECASE | re.DOTALL)

REASON = (
    "BLOCKED: the database is READ-ONLY for Claude (Matt, 2026-11-21/22, "
    "CLAUDE.md §1b). Every table can be queried with SELECT/WITH; nothing can "
    "be written, altered or granted from a chat. {detail}"
)


def _strip(sql: str) -> str:
    """Remove comments, string literals and quoted identifiers, so a keyword
    inside a value ('update', "Drop Zone") neither blocks nor hides."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"\$([A-Za-z_]*)\$.*?\$\1\$", " '' ", sql, flags=re.DOTALL)
    sql = re.sub(r"'(?:[^']|'')*'", " '' ", sql)
    sql = re.sub(r'"(?:[^"]|"")*"', " x ", sql)
    return sql


def blocked_reason(sql: str) -> str | None:
    body = _strip(sql)
    m = WRITE_RE.search(body)
    if m:
        return REASON.format(detail=f"Refused keyword: '{m.group(0)}'.")
    if SELECT_INTO_RE.search(body):
        return REASON.format(detail="SELECT ... INTO creates a table.")
    return None


def wrap_read_only(sql: str) -> str:
    return "BEGIN READ ONLY;\n" + sql.strip().rstrip(";") + ";\nROLLBACK;"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool.endswith("apply_migration"):
        print(REASON.format(detail="apply_migration is refused: migrations "
                            "land through a reviewed PR."), file=sys.stderr)
        return 2

    sql = tool_input.get("query") or ""
    reason = blocked_reason(sql)
    if reason:
        print(reason, file=sys.stderr)
        return 2

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "read-only query, run inside BEGIN READ ONLY",
            "updatedInput": {**tool_input, "query": wrap_read_only(sql)},
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

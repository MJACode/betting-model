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

3. A query that passes is first sent to Supabase's read-only query endpoint
   (`/v1/projects/{ref}/database/query/read-only`, run as
   `supabase_read_only_user`) and its rows come back as this hook's answer,
   so the MCP call is never made and the claude.ai connector's "always ask"
   prompt never shows (mike, 2026-11-26). The token is a Supabase access
   token: the cloud proxy injects it for api.supabase.com (an environment
   network secret), or SUPABASE_ACCESS_TOKEN on a local machine. With no
   token, an auth error, a role permission error or no network, the hook
   falls back to layer 2 and the MCP call runs as before. Set
   SUPABASE_SQL_VIA_API=0 to skip the route.

This governs Claude's MCP route only. The pipeline writes through
DATABASE_URL and is untouched by this hook.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

PROJECT_REF = "vvprgnrmzeekokzkrkfu"
API_URL = "https://api.supabase.com"
MAX_ANSWER_CHARS = 100_000
ANSWERED = (
    "ANSWERED WITHOUT A PROMPT: the repo hook ran this read-only query through "
    "Supabase's read-only query API (as supabase_read_only_user), so the MCP "
    "call was not sent. This is the query's real result, not an error."
)

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


def _debug(msg: str) -> None:
    """Why the API route fell back, when SUPABASE_SQL_VIA_API_DEBUG=1."""
    if os.environ.get("SUPABASE_SQL_VIA_API_DEBUG") == "1":
        print(f"api route fell back: {msg}", file=sys.stderr)


def run_via_api(sql: str) -> str | None:
    """The hook's own answer for a read query, or None to fall back to the
    MCP call. Never raises."""
    if os.environ.get("SUPABASE_SQL_VIA_API", "1") == "0":
        return None
    base = os.environ.get("SUPABASE_API_URL", API_URL).rstrip("/")
    ref = os.environ.get("SUPABASE_PROJECT_REF", PROJECT_REF)
    # In a cloud session the proxy replaces this placeholder with the saved
    # network secret; on a PC, SUPABASE_ACCESS_TOKEN carries the real one.
    token = os.environ.get("SUPABASE_ACCESS_TOKEN") or "sbp_injected_by_proxy"
    req = urllib.request.Request(
        f"{base}/v1/projects/{ref}/database/query/read-only",
        data=json.dumps({"query": sql}).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if e.code == 400 and "permission denied" not in detail.lower():
            return ("The query failed (Supabase read-only query API, HTTP 400): "
                    + detail[:MAX_ANSWER_CHARS])
        _debug(f"HTTP {e.code}: {detail[:300]}")
        return None
    except Exception as e:  # no network, proxy refusal, timeout
        _debug(f"{type(e).__name__}: {str(e)[:300]}")
        return None
    try:
        body = json.dumps(json.loads(body), indent=1, default=str)
    except ValueError:
        pass
    if len(body) > MAX_ANSWER_CHARS:
        body = (body[:MAX_ANSWER_CHARS]
                + f"\n... cut at {MAX_ANSWER_CHARS:,} characters; "
                  "narrow the query or add a LIMIT.")
    return f"{ANSWERED}\nRows (JSON):\n{body}"


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

    answer = run_via_api(sql)
    if answer is not None:
        print(answer, file=sys.stderr)
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

"""PreToolUse guard on Bash: no direct calls to Supabase's management API.

The cloud proxy injects a Supabase access token into every request to
api.supabase.com, so that `picks_read_only_guard.py` can answer read-only
queries without the connector's permission prompt (mike, 2026-11-26). The
same token can write and change the project, and the database is READ-ONLY
for Claude (Matt, 2026-11-21/22, CLAUDE.md §1b). So a Bash command that
names that host together with a network client is refused; queries go
through the Supabase `execute_sql` tool, which the hook answers.
"""
from __future__ import annotations

import json
import re
import sys

HOST_RE = re.compile(r"api\.supabase\.com|supabase\.com/v1", re.IGNORECASE)
CLIENT_RE = re.compile(
    r"\b(?:curl|wget|http|https|httpie|requests|urllib|httpx|aiohttp|fetch|"
    r"python3?|node|deno|bun|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b",
    re.IGNORECASE,
)

REASON = (
    "BLOCKED: direct calls to api.supabase.com are refused. The database is "
    "READ-ONLY for Claude (Matt, 2026-11-21/22, CLAUDE.md §1b) and the token "
    "the proxy adds there can write. Query with the Supabase execute_sql tool: "
    "the repo hook answers read-only queries without a permission prompt."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if HOST_RE.search(cmd) and CLIENT_RE.search(cmd):
        print(REASON, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Stop hook: a session that used /league-models and changed files writes back.

The league-models skill (.claude/skills/league-models/) learns only when a
session that used it writes what it learned into its learning log
(references/learning-log.md, SKILL.md step 9). This hook makes that a gate,
not a suggestion: when a session is about to stop, it reads the session's
transcript and blocks ONCE if all three hold:

  * the session used the skill: a Skill tool call naming league-models, the
    user typing /league-models, or any tool call that names the skill's
    SKILL.md (a session whose checkout lacks the skill reads it from git:
    the first EuroLeague session, 2026-11-12, did exactly that);
  * the session wrote files (an Edit, Write or NotebookEdit call, or a Bash
    command that commits);
  * nothing in the session touched the learning log (no tool call names
    learning-log.md).

Blocking means Claude Code tells the session why and lets it continue, so the
session writes the entry (or says plainly why there was nothing to learn).
When the session stops again, Claude Code sets stop_hook_active and this hook
lets it go: one reminder, never a loop.

It FAILS OPEN. Any error -- no transcript, a malformed line, an unreadable
file -- exits 0 with no output, so a fault here can never trap a session.
"""
from __future__ import annotations

import json
import re
import sys

SKILL = "league-models"
SKILL_FILE = "league-models/SKILL.md"
LOG_NAME = "learning-log.md"
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
COMMAND_RE = re.compile(r"<command-name>/?league-models</command-name>")
COMMIT_RE = re.compile(r"\bgit\b[^\n]*\bcommit\b")

REASON = (
    "This session used the league-models skill and changed files, but never "
    "wrote the skill's learning log. Before finishing, add an entry to "
    ".claude/skills/league-models/references/learning-log.md in the branch "
    "that holds the work: what was tried, what was new (methods, traps, "
    "sources, price routes, kill tests, each also written into its reference "
    "file), what was corrected, and what in the framework changed. If nothing "
    "was learned, write that entry with one sentence saying what was checked. "
    "End the reply with the line 'What this build taught the skill: ...'. "
    "(SKILL.md, 'How this skill learns, corrects and evolves', and step 9.)"
)


def _blocks(message):
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def _texts(message):
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [content]
    return [b.get("text", "") for b in _blocks(message)
            if isinstance(b.get("text"), str)]


def scan(lines):
    """Return (used_skill, wrote_files, touched_log) for transcript lines."""
    used = wrote = touched = False
    for line in lines:
        try:
            entry = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if entry.get("type") == "user":
            if any(COMMAND_RE.search(t) for t in _texts(message)):
                used = True
        for block in _blocks(message):
            if block.get("type") != "tool_use":
                continue
            name = block.get("name") or ""
            tool_input = block.get("input") or {}
            flat = json.dumps(tool_input, ensure_ascii=False).replace("\\\\", "/")
            if name == "Skill" and SKILL in str(tool_input.get("skill", "")):
                used = True
            if SKILL_FILE in flat:
                used = True
            if name in WRITE_TOOLS:
                wrote = True
            if name in ("Bash", "PowerShell") and COMMIT_RE.search(
                    str(tool_input.get("command", ""))):
                wrote = True
            if LOG_NAME in flat:
                touched = True
    return used, wrote, touched


def decide(payload, read_lines):
    """The hook's output for one Stop event, or None to let the stop go."""
    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return None
    path = payload.get("transcript_path")
    if not path:
        return None
    used, wrote, touched = scan(read_lines(path))
    if used and wrote and not touched:
        return {"decision": "block", "reason": REASON}
    return None


def _read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.readlines()


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        out = decide(payload, _read_lines)
    except Exception:  # fail open: a fault here must never trap a session
        return 0
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

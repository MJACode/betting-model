"""The Stop hook that makes a /league-models session write back what it learned.

`.claude/hooks/league_models_writeback.py` blocks a session's stop once when it
used the skill, wrote files and never touched the skill's learning log. These
tests run it on synthetic transcripts in the shape Claude Code writes them
(one JSON object per line, tool calls as `tool_use` blocks), and through the
real command line, because the hook must fail open on anything unexpected.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, ".claude", "hooks", "league_models_writeback.py")
SETTINGS = os.path.join(ROOT, ".claude", "settings.json")

sys.path.insert(0, os.path.dirname(HOOK))
import league_models_writeback as hook  # noqa: E402


def _tool(name, **tool_input):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_x", "name": name, "input": tool_input}]}})


def _user(text):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


SKILL_CALL = _tool("Skill", skill="league-models", args="euroleague")
READ_SKILL = _tool("Read", file_path="C:\\repo\\.claude\\skills\\league-models\\SKILL.md")
SLASH = _user("<command-name>/league-models</command-name>\n<command-args>wnba</command-args>")
EDIT_CODE = _tool("Edit", file_path="/repo/models/new_card.py", old_string="a", new_string="b")
COMMIT = _tool("Bash", command="git add -A && git commit -m 'new card'")
WRITE_LOG = _tool("Edit", file_path="/repo/.claude/skills/league-models/references/learning-log.md",
                  old_string="x", new_string="y")
LOG_BY_SCRIPT = _tool("Bash", command="python update.py .claude/skills/league-models/references/learning-log.md")


def _decide(lines, **payload):
    payload.setdefault("transcript_path", "t.jsonl")
    return hook.decide(payload, lambda _path: lines)


@pytest.mark.parametrize("used", [SKILL_CALL, READ_SKILL, SLASH], ids=["skill", "read", "slash"])
@pytest.mark.parametrize("wrote", [EDIT_CODE, COMMIT], ids=["edit", "commit"])
def test_it_blocks_once_when_the_skill_was_used_files_changed_and_no_log(used, wrote):
    out = _decide([used, wrote])
    assert out and out["decision"] == "block"
    assert "learning-log.md" in out["reason"]
    assert "What this build taught the skill" in out["reason"]


@pytest.mark.parametrize("log", [WRITE_LOG, LOG_BY_SCRIPT], ids=["edit", "script"])
def test_it_lets_the_stop_go_once_the_log_was_touched(log):
    assert _decide([SKILL_CALL, EDIT_CODE, log]) is None


def test_it_ignores_a_session_that_never_used_the_skill():
    assert _decide([EDIT_CODE, COMMIT]) is None


def test_it_ignores_a_session_that_only_read_or_asked():
    assert _decide([SKILL_CALL, _tool("Read", file_path="/repo/docs/sports/nba.md")]) is None


def test_it_reminds_once_and_never_loops():
    assert _decide([SKILL_CALL, EDIT_CODE], stop_hook_active=True) is None


def test_a_mention_in_prose_is_not_a_use():
    prose = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": "the league-models skill could help here"}]}})
    assert _decide([prose, EDIT_CODE]) is None


def test_malformed_lines_are_skipped():
    assert _decide(["not json", "", "[1,2]", SKILL_CALL, "{", EDIT_CODE])["decision"] == "block"


def _run(stdin):
    return subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True,
                          text=True, timeout=30)


@pytest.mark.parametrize("stdin", ["", "garbage", "[]", '{"transcript_path": "/no/such/file.jsonl"}'],
                         ids=["empty", "garbage", "list", "missing-file"])
def test_the_command_fails_open(stdin):
    res = _run(stdin)
    assert res.returncode == 0
    assert res.stdout == ""


def test_the_command_blocks_through_stdout(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("\n".join([SKILL_CALL, EDIT_CODE]) + "\n", encoding="utf-8")
    res = _run(json.dumps({"transcript_path": str(transcript), "stop_hook_active": False}))
    assert res.returncode == 0
    assert json.loads(res.stdout)["decision"] == "block"


def test_settings_run_the_hook_on_stop():
    with open(SETTINGS, encoding="utf-8") as fh:
        settings = json.load(fh)
    commands = [h.get("command", "") for group in settings.get("hooks", {}).get("Stop", [])
                for h in group.get("hooks", [])]
    assert any("league_models_writeback.py" in c for c in commands), commands

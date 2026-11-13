"""`scripts/outstanding.py`: the list of everything still open, and its session-start line.

The tracker is GitHub (open pull requests, issues labelled `outstanding`) plus
pushed branches with no pull request. These tests pin the parts that decide
what counts as open, with no network: a squash-merged branch is not open, a
branch whose only pull request was closed is listed apart, the session-start
summary reads the cache and fails open, and the settings run it.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import pytest

from scripts import outstanding as o

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = dt.datetime(2026, 11, 13, 14, 0, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize("url", [
    "https://github.com/MJACode/betting-model.git",
    "https://github.com/MJACode/betting-model",
    "git@github.com:MJACode/betting-model.git",
])
def test_repo_slug(url):
    assert o.repo_slug(url) == "MJACode/betting-model"


@pytest.mark.parametrize("rollup, expected", [
    ([], "no checks"),
    ([{"conclusion": "SUCCESS"}, {"state": "SUCCESS"}], "checks pass"),
    ([{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}], "checks failing"),
    ([{"status": "IN_PROGRESS"}, {"conclusion": "SUCCESS"}], "checks running"),
    ([{"name": "daily pipeline not running", "conclusion": "FAILURE"},
      {"name": "pytest-subset", "conclusion": "SUCCESS"}], "checks pass"),
])
def test_checks_state(rollup, expected):
    assert o.checks_state(rollup) == expected


REFS = "\n".join([
    "origin/HEAD\t2026-11-13T10:00:00+00:00\t-",
    "origin/claude/squash-merged\t2026-11-12T10:00:00+00:00\tmerged by squash",
    "origin/claude/open-pr\t2026-11-12T10:00:00+00:00\thas an open PR",
    "origin/claude/closed-pr\t2026-11-10T10:00:00+00:00\tits PR was closed",
    "origin/claude/no-pr\t2026-11-11T10:00:00+00:00\tnever had a PR",
    "origin/claude/old\t2026-09-01T10:00:00+00:00\told work",
])
PAST = [
    {"headRefName": "claude/squash-merged", "state": "MERGED"},
    {"headRefName": "claude/closed-pr", "state": "CLOSED"},
    {"headRefName": "claude/reopened", "state": "CLOSED"},
    {"headRefName": "claude/reopened", "state": "MERGED"},
]


def test_a_merged_pull_request_closes_the_branch_and_a_closed_one_is_listed_apart():
    merged, closed = o.split_by_pr_state(PAST)
    assert merged == {"claude/squash-merged", "claude/reopened"}
    assert closed == {"claude/closed-pr"}
    rows = o.branches_without_pr(REFS, {"claude/open-pr"} | merged, NOW)
    names = [r[0] for r in rows]
    assert "claude/squash-merged" not in names and "claude/open-pr" not in names
    assert "HEAD" not in names
    assert names[:3] == ["claude/no-pr", "claude/closed-pr", "claude/old"]  # newest first
    assert dict((r[0], r[1]) for r in rows)["claude/old"] == 73


def _gathered(prs=(), issues=(), branches=(), closed=()):
    return NOW, "MJACode/betting-model", list(prs), list(issues), list(branches), list(closed)


def test_the_session_line_names_counts_the_oldest_items_and_the_rule():
    prs = [{"number": 818, "createdAt": "2026-09-22T10:00:00Z", "title": "a", "headRefName": "x"},
           {"number": 1270, "createdAt": "2026-11-13T10:00:00Z", "title": "b", "headRefName": "y"}]
    issues = [{"number": 1280, "createdAt": "2026-11-13T09:00:00Z", "title": "check Monday's run"}]
    branches = [("claude/no-pr", 2, "s"), ("claude/old", 73, "s")]
    text = o.session_summary(*_gathered(prs, issues, branches))
    assert "2 pull requests not merged, oldest #818 (52d)" in text
    assert "1 pushed branches with no pull request in the last 30 days" in text
    assert "1 issues labelled outstanding, oldest #1280" in text
    assert "TEST IT NOW" in text and len(text) < 450


def test_the_cache_round_trips_and_expires(tmp_path):
    path = str(tmp_path / "cache.json")
    o.write_cache(_gathered(), path)
    got = o.read_cache(path, now=dt.datetime.fromisoformat(json.load(open(path))["at"]) + dt.timedelta(minutes=30))
    assert got and got[1] == 30 and got[0].startswith("OPEN WORK")
    later = NOW + dt.timedelta(hours=30)
    assert o.read_cache(path, now=later) is None
    assert o.read_cache(str(tmp_path / "missing.json")) is None


def test_session_start_prints_the_cache_without_asking_github(tmp_path, monkeypatch, capsys):
    path = str(tmp_path / "cache.json")
    o.write_cache(_gathered(), path)
    monkeypatch.setattr(o, "cache_path", lambda: path)
    monkeypatch.setattr(o, "gather", lambda **_: (_ for _ in ()).throw(AssertionError("asked GitHub")))
    assert o.main(["--session-start"]) == 0
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert ctx["hookEventName"] == "SessionStart" and "min ago" in ctx["additionalContext"]


def test_session_start_fails_open(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(o, "cache_path", lambda: str(tmp_path / "none.json"))

    def broken(**_):
        raise RuntimeError("gh not installed")
    monkeypatch.setattr(o, "gather", broken)
    assert o.main(["--session-start"]) == 0
    assert o.main(["--refresh-cache"]) == 0
    assert capsys.readouterr().out == ""


def test_settings_run_it_at_session_start_and_refresh_in_the_background():
    with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as fh:
        hooks = [h for g in json.load(fh)["hooks"]["SessionStart"] for h in g["hooks"]]
    start = [h for h in hooks if "outstanding.py\" --session-start" in h["command"]]
    refresh = [h for h in hooks if "outstanding.py\" --refresh-cache" in h["command"]]
    assert start and not start[0].get("async")
    assert refresh and refresh[0].get("async") is True

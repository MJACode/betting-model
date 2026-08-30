"""
The two autonomous agents have a contract, and it has to stay true.

Before 2026-08-30 this repo had no agents at all — no `.claude/` directory, no
Routines, only deterministic cron jobs. The scheduler could DETECT a problem
(health checks, the run ledger, pipeline_log) but nothing ever ACTED on what it
detected, which is why the same four small fixes sat untouched across four
sessions.

These tests pin the parts an agent cannot be trusted to check about itself:
that its data source still runs, that the backlog it reads is well-formed, and
that the guardrails are still written down. An agent whose contract has quietly
drifted is worse than no agent, because it looks supervised.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

AGENTS = ROOT / "docs" / "agents.md"
FOLLOWUPS = ROOT / "docs" / "followups.md"
REPORT = ROOT / "scripts" / "pipeline_report.py"


# ── the data source ───────────────────────────────────────────────────────────

def test_the_report_script_exists_and_parses():
    """pipeline-watch is useless if its one input does not run."""
    assert REPORT.exists()
    ast.parse(REPORT.read_text(encoding="utf-8"))


def test_the_report_covers_every_question_the_watch_acts_on():
    """
    Each trigger in the agent's contract needs a section in the report, or the
    agent is told to act on something it cannot see.
    """
    src = REPORT.read_text(encoding="utf-8")
    for key in ("slowest_steps", "recent_passes", "failing_checks",
                "api_burn_by_source", "picks_written", "delivery"):
        assert f'"{key}"' in src, f"report has no {key} section"


def test_the_report_reads_the_dispatch_timings():
    """
    The whole reason the watch can answer "where does the time go" is the
    per-step dispatch rows added in #332. Reading anything else would silently
    return to the 8-of-28 blindness.
    """
    src = REPORT.read_text(encoding="utf-8")
    assert "dispatch:%%" in src, "must read the dispatch rows, not just producers"


def test_the_report_never_crashes_the_watch_on_one_bad_query():
    """
    A schema drift in one section must not take the whole report down — the
    agent should still see the other five. Same fail-open principle as the
    NCAAF price prefilter.
    """
    src = REPORT.read_text(encoding="utf-8")
    fn = src[src.index("def _rows("):src.index("def collect(")]
    assert "except Exception" in fn
    assert "QUERY FAILED" in fn


# ── the backlog ───────────────────────────────────────────────────────────────

def test_the_backlog_exists_and_has_items():
    assert FOLLOWUPS.exists()
    items = re.findall(r"^## \[[ x]\] ", FOLLOWUPS.read_text(encoding="utf-8"), re.M)
    assert len(items) >= 5, f"only {len(items)} backlog items — did the file get truncated?"


def test_every_backlog_item_is_a_checkbox():
    """
    A heading without a checkbox cannot be ticked, so the agent would redo it
    every single morning.
    """
    text = FOLLOWUPS.read_text(encoding="utf-8")
    headings = [ln for ln in text.splitlines() if ln.startswith("## ")]
    for h in headings:
        assert re.match(r"^## \[[ x]\] ", h), f"backlog heading is not a checkbox: {h!r}"


def test_blocked_items_are_marked_so_the_agent_skips_them():
    """
    `[needs-decision]` is what stops an agent guessing a human's call — most
    importantly a model threshold, which CLAUDE.md §1b says must carry a named
    person.
    """
    text = FOLLOWUPS.read_text(encoding="utf-8")
    assert "[needs-decision]" in text
    # the threshold sweep in particular must never be agent-shippable
    sweep = [ln for ln in text.splitlines()
             if ln.startswith("## ") and "sweep" in ln.lower()]
    assert sweep and all("[needs-decision]" in ln for ln in sweep), (
        "a threshold sweep must be marked needs-decision — §1b requires a "
        "named human on any model update")


# ── the guardrails ────────────────────────────────────────────────────────────

def test_the_contract_documents_both_agents_by_name():
    """
    Named Sentinel and Janitor by mike, 2026-08-30. Pinned because a rename that
    lands in the Routine but not the repo leaves two agents nobody can look up.
    """
    text = AGENTS.read_text(encoding="utf-8")
    assert "Sentinel" in text and "Janitor" in text


def test_the_agents_are_findable_from_the_file_every_session_reads():
    """
    CLAUDE.md §9 is the map. An agent documented only in docs/ is an agent a
    fresh session never learns exists — the same reason the §9 table exists at
    all.
    """
    root = Path(__file__).parent.parent
    claude_md = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Sentinel" in claude_md and "Janitor" in claude_md
    assert "docs/agents.md" in claude_md
    assert "docs/followups.md" in claude_md


def test_there_is_a_one_screen_summary():
    """`docs/AGENTS.md` is the capitalised, obvious landing spot — the name
    someone types when they do not know what they are looking for."""
    root = Path(__file__).parent.parent
    quick = root / "docs" / "AGENTS.md"
    assert quick.exists()
    text = quick.read_text(encoding="utf-8")
    assert "Sentinel" in text and "Janitor" in text
    assert "agents.md" in text and "followups.md" in text


@pytest.mark.parametrize("rule", [
    "Never push to master",
    "Full suite before any PR",
    "Mutation-check",
    "Stop and report rather than guess",
])
def test_the_shared_guardrails_are_still_written_down(rule):
    """
    These are the four that keep an unattended session from doing damage. If
    one is edited away, the agents keep running under a contract nobody
    re-agreed to.
    """
    assert rule in AGENTS.read_text(encoding="utf-8"), f"guardrail lost: {rule}"


def test_neither_agent_may_change_a_model_threshold():
    """
    The one hard prohibition. A threshold change is a model update under §1b
    and needs `Updated-By: <person>` — an agent cannot supply that without
    putting a decision in someone's mouth.
    """
    text = AGENTS.read_text(encoding="utf-8")
    assert text.count("threshold") >= 2, "the prohibition must appear for both agents"
    assert "Updated-By" in text

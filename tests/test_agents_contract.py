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

# The full contract. Renamed from docs/agents.md on 2026-08-31: it collided
# with docs/AGENTS.md on every case-insensitive filesystem (Windows, and
# macOS by default), so only ONE of the two could exist on disk and this
# module silently read whichever won. That is what made
# test_there_is_a_one_screen_summary fail for days.
AGENTS = ROOT / "docs" / "agents_contract.md"
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

# Every scheduled agent this repo ever had is now retired: Sentinel and
# ModelCalibration on 2026-09-01..03 (the watch became a worker cron), Janitor on
# 2026-09-03 (four SUCCEEDED runs, nothing landed, no working exit from its
# sandbox). They stay DOCUMENTED rather than deleted, which is the whole point
# of the tests below — a retired agent that vanishes from the docs is one the
# next session cheerfully rebuilds, and rebuilding Janitor costs ~$6 a day to
# produce nothing.
RETIRED_AGENTS = ("Sentinel", "Janitor")


def _labelled_retired(text: str, name: str, window: int = 700) -> bool:
    """True when every mention of `name` sits near the word 'retire'."""
    low = text.lower()
    needle = name.lower()
    i = low.find(needle)
    if i < 0:
        return False
    while i >= 0:
        near = low[max(0, i - window): i + window]
        if "retire" in near:
            return True
        i = low.find(needle, i + 1)
    return False


def test_the_contract_documents_every_agent_by_name():
    """
    Named Sentinel and Janitor by mike, 2026-08-30. Pinned because a rename that
    lands in the Routine but not the repo leaves an agent nobody can look up.
    Retirement does not release the obligation — it strengthens it.
    """
    text = AGENTS.read_text(encoding="utf-8")
    for name in RETIRED_AGENTS:
        assert name in text, f"{name} is undocumented; a future session will rebuild it"
        assert _labelled_retired(text, name), (
            f"the contract names {name} but never says it is retired, so it reads "
            f"as a live agent")


def test_the_contract_says_not_to_rebuild_janitor_and_why():
    """
    The specific trap. Janitor's prompt was rewritten on 2026-09-03 to remove its
    do-nothing escape hatch and to demand `git ls-remote` proof of the push, and
    the very NEXT run still landed nothing. Without that recorded, the obvious
    move for a reader who sees a broken agent is another prompt rewrite.
    """
    # Whitespace-normalised: the contract is hard-wrapped, so a phrase that
    # straddles a line break is still the phrase. Matching the raw text made
    # this fail for the formatting rather than the content.
    text = " ".join(AGENTS.read_text(encoding="utf-8").lower().split())
    assert "do not rebuild" in text
    assert "prompt was never the binding constraint" in text


def test_the_agents_are_findable_from_the_file_every_session_reads():
    """
    CLAUDE.md §9 is the map. An agent documented only in docs/ is an agent a
    fresh session never learns exists — the same reason the §9 table exists at
    all. It must not advertise a retired agent as a live one either.
    """
    root = Path(__file__).parent.parent
    claude_md = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "docs/agents_contract.md" in claude_md
    assert "docs/followups.md" in claude_md
    for name in RETIRED_AGENTS:
        if name in claude_md:
            assert _labelled_retired(claude_md, name), (
                f"CLAUDE.md names {name} without saying it is retired")


def test_the_backlog_does_not_promise_an_agent_that_no_longer_runs():
    """
    followups.md described itself as "Janitor's worklist" and said an agent took
    an item every morning. Nothing takes an item any more, and a backlog that
    claims an owner it does not have is how items sit untouched while everyone
    assumes something else is on it.
    """
    root = Path(__file__).parent.parent
    text = (root / "docs" / "followups.md").read_text(encoding="utf-8")
    assert "Janitor's worklist" not in text
    assert _labelled_retired(text, "Janitor"), (
        "followups.md must say why no agent is coming for these items")


def test_there_is_a_one_screen_summary():
    """`docs/AGENTS.md` is the capitalised, obvious landing spot — the name
    someone types when they do not know what they are looking for."""
    root = Path(__file__).parent.parent
    quick = root / "docs" / "AGENTS.md"
    assert quick.exists()
    text = quick.read_text(encoding="utf-8")
    for name in RETIRED_AGENTS:
        assert name in text, f"{name} vanished from the one-screen summary"
        assert _labelled_retired(text, name), (
            f"AGENTS.md names {name} without marking it retired")
    # Links onward to both, by their post-rename names. Asserting the bare
    # "agents.md" used to pass for the wrong reason: this file and the contract
    # collided on case, so on Windows both paths read the SAME file and the
    # link check was really checking the contract against itself.
    assert "agents_contract.md" in text and "followups.md" in text


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


def test_the_contract_tells_an_agent_to_wait_for_the_checkout():
    """Measured 2026-09-01: a Sentinel run reported "no git repository is
    checked out" and blamed the environment binding, 3m20s BEFORE the clone
    landed. A whole run was lost to a transient reported as a permanent fault,
    and the report asked a human to go fix something that was not broken.

    Pinned because the guidance lives in a Routine prompt, which this repo
    cannot see: if the contract stops saying it, nothing else does.
    """
    text = AGENTS.read_text(encoding="utf-8")
    assert "checkout" in text.lower()
    assert "01:39:45" in text, (
        "the timeline is the evidence — without it this reads as a worry "
        "rather than a measurement")
    assert "WAIT, not a finding" in text


def test_the_contract_records_where_the_calibration_judgement_actually_runs():
    """ModelCalibration's Routine was created with NO MCP connections, so it
    could never read `model_calibration_sweeps` — the one table its whole job
    is about. Four routes to attach a connector are closed (create_trigger
    refuses the parameter for this org; pass-through has no passable grant; no
    DATABASE_URL reaches a Routine session; a Routine-fired session has no
    Routines tooling to recreate itself). The judgement pass therefore runs
    inside Sentinel, which already holds Supabase.

    Pinned because the arrangement is invisible from the repo: a reader who
    only sees `tracking/model_calibration_agent.py` and a Monday cron would
    reasonably conclude there is a third agent, and go looking for its reports.
    """
    text = AGENTS.read_text(encoding="utf-8")
    block = text[text.index("### Why the judgement pass moved into Sentinel"):]
    assert "no MCP connections" in block
    # The undo has to be written down, or the move is one-way by accident.
    assert "re-enable" in block and "section B" in block
    # The worker half is unaffected and must not be described as moved.
    assert "mechanical sweep on the worker is untouched" in block


def test_the_one_screen_summary_says_modelcalibration_is_not_a_third_agent():
    quick = (Path(__file__).parent.parent / "docs" / "AGENTS.md").read_text(encoding="utf-8")
    assert "not a third agent" in quick, (
        "someone looking for ModelCalibration's Routine must land on why there "
        "isn't one, not on a dead name")


def test_the_contract_forbids_waiting_on_a_human_and_says_which_tool_prompts():
    """Measured 2026-09-01: Sentinel called `mcp__Railway__get-logs`, the harness
    raised a permission prompt, and an unattended 7:15am run sat in
    REQUIRES_ACTION for over 100 minutes producing nothing.

    Pinned with the tool NAMED, because the general advice ("don't block") is
    useless without knowing which call does it — and the permitted-tool list
    lives in the Routine's session_context, which `update_trigger` cannot set,
    so not making the call is the only available fix.
    """
    text = AGENTS.read_text(encoding="utf-8")
    block = text[text.index("## An unattended agent must never make a call"):]
    assert "REQUIRES_ACTION" in block

    # BOTH measurements, because naming only the first is how this was got
    # wrong: the original entry said Railway prompts and Supabase is safe, and
    # the next day's run blocked on Supabase. The rule is about the mcp__
    # prefix, not about one connector.
    assert "mcp__Railway__" in block and "mcp__Supabase__" in block, (
        "one server is an anecdote; the class needs both to be visible")
    assert "It is not one connector. It is MCP." in block

    # Both halves of the rule, or it collapses into the opposite bug: the same
    # day's OTHER lost run gave up on a checkout that had not arrived yet.
    assert "Never wait on a person" in block
    assert "Wait for what arrives on its own" in block


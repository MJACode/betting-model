"""The path-scoped rules directory stays coherent.

mike, 2026-09-03: "this project will only continue to grow. How can we ensure we
don't lose context? Multiple files? Allow a bigger file?"

Neither, quite. Claude Code loads CLAUDE.md in full every session, so its size
is a fixed tax on every session whether or not the rules are relevant — and the
docs target under 200 lines because "longer files consume more context and
reduce adherence". A bigger file buys less compliance, not more.

`.claude/rules/*.md` with `paths:` frontmatter load ONLY when Claude opens a
matching file. Zero cost until relevant, then guaranteed present — which is
also MORE reliable than a line 700 lines deep in a file read at startup.

What must stay in CLAUDE.md is what has to be known BEFORE deciding which file
to open: the reply format, the pick rule, the evaluation rule, how to verify.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

REPO = Path(__file__).resolve().parent.parent
RULES = sorted((REPO / ".claude" / "rules").glob("*.md"))


def test_the_rules_directory_exists_and_is_not_empty():
    assert RULES, ".claude/rules/ is empty — the split was reverted"


@pytest.mark.parametrize("path", RULES, ids=lambda p: p.name)
def test_every_rule_file_is_path_scoped(path):
    """A rule file WITHOUT `paths:` loads unconditionally at launch, which
    re-creates the cost the split exists to remove — silently, because it still
    works."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} has no frontmatter"
    front = text.split("---", 2)[1]
    assert "paths:" in front, f"{path.name} is not path-scoped"
    globs = re.findall(r'^\s*-\s*"(.+?)"', front, re.M)
    assert globs, f"{path.name} declares paths: with no patterns"
    for g in globs:
        top = g.split("/")[0].replace("**", "")
        if top:
            assert (REPO / top).exists(), (
                f"{path.name} scopes to {g!r} but {top!r} does not exist — the "
                f"rule would never load")


@pytest.mark.parametrize("path", RULES, ids=lambda p: p.name)
def test_every_rule_file_actually_carries_rules(path):
    text = path.read_text(encoding="utf-8")
    # A rule leads either a bullet or a paragraph — frontend.md is one long
    # paragraph rule, and an assertion that only accepted bullets called it
    # empty.
    assert re.search(r'^(- )?\*\*', text, re.M), (
        f"{path.name} has frontmatter but no rules")


def test_no_rule_was_lost_when_the_split_happened():
    """Every rule lead that CLAUDE.md carried before the split is still SOMEWHERE
    — either still in CLAUDE.md or in a rules file. Checked mechanically,
    because 'I moved it carefully' is not evidence."""
    def leads(text):
        out = []
        for pat in (r'^- \*\*(.+?)\*\*', r'^\*\*(.+?)\*\*'):
            out += [" ".join(b.split())
                    for b in re.findall(pat, text, re.M | re.S)
                    if len(" ".join(b.split())) > 20]
        return out

    here = leads((REPO / "CLAUDE.md").read_text(encoding="utf-8"))
    for p in RULES:
        here += leads(p.read_text(encoding="utf-8"))

    # The rules that must never stop being universal, spot-checked by name.
    universal = [
        "THE EVALUATION RULE",
        "NEVER ESTIMATE WHAT YOU CAN MEASURE",
        "THE SANDBOX'S LIMITS ARE NOT THE SYSTEM'S LIMITS",
    ]
    claude_md = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    for u in universal:
        assert u in claude_md, (
            f"{u!r} left CLAUDE.md — it governs sessions that open no matching "
            f"file, so scoping it hides it")
    assert len(here) >= 74, f"only {len(here)} rule leads survive the split"


def test_claude_md_still_points_at_the_rules_directory():
    """A reader who never opens a matching file should still know the rules
    exist, or the split looks like deletion."""
    text = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    assert ".claude/rules/" in text

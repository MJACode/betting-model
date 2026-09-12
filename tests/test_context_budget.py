"""The context budget — what every session pays to start, and who polices it.

WHY THIS IS A TEST AND NOT A SENTENCE IN CLAUDE.md. CLAUDE.md used to carry
"keep this file under ~30 KB" in three places, so every session read the warning
and a fair number of them spent a reply repeating it. That is the wrong place for
a budget: a size limit is a mechanical fact, and a mechanical fact belongs in the
only quality gate. This file says it once, at merge time, to whoever grew it.

WHAT IS BUDGETED. Not "CLAUDE.md" — **the always-loaded layer**, which is what a
session actually pays before it does anything:

    CLAUDE.md  +  the SessionStart hook's injected context

`.claude/rules/*.md` are NOT in that budget. They load only when Claude opens a
file matching their `paths:` frontmatter, so a rule about the mobile app costs a
session that never opens `mobile/` nothing. That is the mechanism that lets the
project keep growing without the start-up cost growing with it (CLAUDE.md §10).
They still get a PER-FILE cap here, because without one the 909 KB failure mode
simply relocates into a rules file — and a rules file that grows unbounded is
worse than a big CLAUDE.md, since nothing in the always-loaded layer shows it.

THE HISTORY, because it is the argument for the layering. CLAUDE.md reached
**909 KB (~225k tokens)** on 2026-08-30 under the convention "update CLAUDE.md
after every commit"; 76% of it was a session log duplicating git history. The log
moved to `docs/sessions/`, the evidence to `docs/rules_evidence.md`, and the
area-specific rules to `.claude/rules/`. Between 2026-09-03 and 2026-09-07 this
cap was raised six times — 36,000, 37,000, 38,000, 46,000 — roughly a day's
headroom each, until mike said *"just increase the claude limit, tired of this
warning, just figure it out."* Raising it was never the fix; the cap was being
tuned as though it were the plan, when the plan is the layering. Full story:
`git log --follow tests/test_context_budget.py` (it was renamed from
test_claude_md_size.py, so plain `git log` stops there) and `docs/rules_evidence.md`.

IF A CAP FAILS, THE FIX IS ALMOST NEVER TO RAISE IT. Ask, in order:
  1. Is it a LOG ENTRY? -> `docs/sessions/<YYYY-MM>.md`.
  2. Is it EVIDENCE for a rule? -> `docs/rules_evidence.md`, rule statement here.
  3. Is it REFERENCE for one sport or subsystem? -> its own `docs/` file.
  4. Can it only be broken by editing files under some directory?
     -> `.claude/rules/<topic>.md` with `paths:`, plus a one-line pointer in
        CLAUDE.md under the original section number.
Only what governs every session, with no path to attach to, belongs in the
always-loaded layer.
"""
from __future__ import annotations

import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_MD = os.path.join(ROOT, "CLAUDE.md")
RULES_DIR = os.path.join(ROOT, ".claude", "rules")
HOOK = os.path.join(ROOT, ".claude", "hooks", "connector_reminder.json")

# 36,990 bytes after the 2026-09-12 layering, down from 45,978 on master (-19.5%).
# The pick rule's mechanics, the publishing rule, section 6's invariants and the
# model-update rules moved to .claude/rules/; each left a one-line pointer under
# its original section number.
#
# Headroom is ~2 KB. Before raising this, read the four questions in the
# docstring. The layering is what bounds growth now, and a raise that skips
# question 4 is the 2026-09-07 mistake again -- the cap was lifted six times in
# four days that week and each raise bought about a day.
MAX_CLAUDE_MD_BYTES = 39_000

# CLAUDE.md + the hook's injected context. This is the real per-session cost and
# the number worth watching: moving prose from the file into the hook does not
# make a session cheaper, so the budget covers both and cannot be gamed that way.
MAX_ALWAYS_LOADED_BYTES = 41_000

# Per rules file. The largest today is data-integrity.md at 9,926 bytes. A rules
# file only costs the sessions that open its paths, so the cap is looser than
# CLAUDE.md's -- but it exists, because "move it to a rules file" must not become
# the new way to write 909 KB.
MAX_RULE_FILE_BYTES = 12_000


def _read(path: str) -> str:
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def _size(path: str) -> int:
    """CONTENT bytes, not bytes on disk.

    os.path.getsize() counts the line endings the platform happens to have
    checked out, and this repo is developed on Windows (autocrlf) while the
    worker runs Linux -- ~660 bytes of difference on a 900-line file, purely
    from CR characters that cost a session nothing. Measured on disk, the same
    commit passed on one machine and failed on the other, which is a false alarm
    about the one thing this test exists to make people notice. The limit is a
    context budget, so it is measured the way a reader loads it: normalised.
    """
    return len(_read(path).encode("utf-8"))


def _rule_files() -> list[str]:
    if not os.path.isdir(RULES_DIR):
        return []
    return sorted(f for f in os.listdir(RULES_DIR) if f.endswith(".md"))


def _expand_braces(text: str) -> str:
    """Expand this repo's `{a,b}.md` shorthand so a pointer written that way counts.

    CLAUDE.md §7 and §9 both use it (`.claude/rules/{data-integrity,operations}.md`,
    `docs/sports/{mlb,wnba,...}.md`). A checker that only does literal matching
    calls those pointers missing, which would push the file towards spelling
    every path out — more bytes, in the one file where bytes are budgeted.
    """
    def _one(match: re.Match[str]) -> str:
        prefix, options, suffix = match.group(1), match.group(2), match.group(3)
        return " ".join(f"{prefix}{opt.strip()}{suffix}"
                        for opt in options.split(","))

    return re.sub(r"([\w./-]*)\{([^{}]+)\}([\w./-]*)", _one, text)


def _hook_context() -> str:
    if not os.path.exists(HOOK):
        return ""
    with io.open(HOOK, encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("hookSpecificOutput", {}).get("additionalContext", "")


# --------------------------------------------------------------- the budget


def test_claude_md_stays_small_enough_to_load_every_session() -> None:
    size = _size(CLAUDE_MD)
    assert size <= MAX_CLAUDE_MD_BYTES, (
        f"CLAUDE.md is {size:,} bytes (limit {MAX_CLAUDE_MD_BYTES:,}). It is "
        "re-read at the start of every session, so every byte is a permanent "
        "context tax. Read the four questions at the top of this file before "
        "raising the cap -- most new text belongs in docs/sessions/, "
        "docs/rules_evidence.md, or a path-scoped .claude/rules/ file."
    )


def test_the_always_loaded_layer_stays_within_budget() -> None:
    """CLAUDE.md plus the hook. Moving prose between them saves nothing."""
    claude = _size(CLAUDE_MD)
    hook = len(_hook_context().encode("utf-8"))
    total = claude + hook
    assert total <= MAX_ALWAYS_LOADED_BYTES, (
        f"The always-loaded layer is {total:,} bytes "
        f"(CLAUDE.md {claude:,} + SessionStart hook {hook:,}; limit "
        f"{MAX_ALWAYS_LOADED_BYTES:,}). This is what every session pays before "
        "it does anything. Path-scope a rule instead (CLAUDE.md §10)."
    )


def test_no_single_rules_file_grows_unbounded() -> None:
    """Otherwise 'move it to a rules file' becomes the new 909 KB."""
    oversized = {
        name: _size(os.path.join(RULES_DIR, name))
        for name in _rule_files()
        if _size(os.path.join(RULES_DIR, name)) > MAX_RULE_FILE_BYTES
    }
    assert not oversized, (
        "These .claude/rules/ files are over the per-file cap of "
        f"{MAX_RULE_FILE_BYTES:,} bytes: "
        + ", ".join(f"{n} ({s:,})" for n, s in sorted(oversized.items()))
        + ". Split by path, or move the evidence to docs/rules_evidence.md and "
        "leave the rule statement."
    )


# ------------------------------------------------- the layering's invariants


# NOTE: `paths:` frontmatter is validated by tests/test_claude_rules_split.py,
# which also checks the glob's top-level directory exists -- stricter than a
# frontmatter check, and it caught a `.env*` scope here that would never have
# loaded. Not duplicated: this file had a weaker copy of that guard on
# 2026-09-12 and it was removed, which is the same duplication that had the
# analysis-method rules in two places.


def test_every_rules_file_is_pointed_at_from_claude_md() -> None:
    """CLAUDE.md §10, obligation 1: a moved rule leaves a pointer behind.

    A session doing analysis purely in SQL opens no file under `tracking/**`, so
    the path-scoped rule never loads. The pointer in the always-loaded layer is
    the only way that session learns the rule exists at all.
    """
    text = _expand_braces(_read(CLAUDE_MD))
    unpointed = [n for n in _rule_files() if n not in text]
    assert not unpointed, (
        f"These rules files are not mentioned in CLAUDE.md: {unpointed}. Add a "
        "one-line pointer under the relevant section number saying what the "
        "rule is and what opens it (CLAUDE.md §10)."
    )


def test_section_numbers_cited_elsewhere_still_exist() -> None:
    """Never renumber a section: config.py and the models cite §1b, §1c, §6, §7.

    A moved rule keeps its section number as a signpost, so a citation in code
    or docs never goes dead.
    """
    text = _read(CLAUDE_MD)
    headings = set(re.findall(r"^## (0|00|1|1b|1c|\d+)\.", text, re.M))
    for cited in ("00", "0", "1", "1b", "1c", "2", "3", "4", "5", "6", "7", "8", "9"):
        assert cited in headings, (
            f"CLAUDE.md no longer has a section {cited}, but config.py, the "
            "model code and docs/ cite it. A section whose body moved keeps its "
            "number and becomes a pointer to the new home (CLAUDE.md §10)."
        )


# ------------------------------------------------------- the original guards


def test_the_session_log_lives_in_docs_not_here() -> None:
    text = _read(CLAUDE_MD)
    stray = [line for line in text.split("\n")
             if line.startswith("**Session summary")]
    assert not stray, (
        f"{len(stray)} session summary block(s) are back in CLAUDE.md. They "
        "belong in docs/sessions/<YYYY-MM>.md with a row in "
        "docs/sessions/README.md."
    )


def test_every_doc_referenced_by_the_index_exists() -> None:
    """A dead pointer in §9 is worse than no pointer — it hides the content."""
    text = _read(CLAUDE_MD)
    referenced = {
        ref for ref in re.findall(r"`(docs/[A-Za-z0-9_/.-]+\.md)`", text)
        if "{" not in ref
    }
    assert referenced, "§9 index appears to be empty — did the map get dropped?"
    missing = sorted(r for r in referenced
                     if not os.path.exists(os.path.join(ROOT, r)))
    assert not missing, f"CLAUDE.md points at files that do not exist: {missing}"


def test_rules_files_point_only_at_docs_that_exist() -> None:
    """Same guard, for the layer that CLAUDE.md no longer carries."""
    missing: dict[str, list[str]] = {}
    for name in _rule_files():
        text = _read(os.path.join(RULES_DIR, name))
        refs = {r for r in re.findall(r"`(docs/[A-Za-z0-9_/.-]+\.md)`", text)
                if "{" not in r}
        gone = sorted(r for r in refs
                      if not os.path.exists(os.path.join(ROOT, r)))
        if gone:
            missing[name] = gone
    assert not missing, f".claude/rules/ files point at missing docs: {missing}"


def test_the_session_archive_is_present_and_indexed() -> None:
    sessions = os.path.join(ROOT, "docs", "sessions")
    assert os.path.isdir(sessions), "docs/sessions/ is missing"
    months = [f for f in os.listdir(sessions) if re.fullmatch(r"\d{4}-\d{2}\.md", f)]
    assert months, "docs/sessions/ has no <YYYY-MM>.md archive files"
    index = _read(os.path.join(sessions, "README.md"))
    for month in months:
        assert month[:-3] in index, f"{month} is not listed in docs/sessions/README.md"

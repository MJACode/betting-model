"""CLAUDE.md is read in full at the start of every session — keep it small.

It reached **909 KB (~225k tokens)** on 2026-08-30 because the convention was
"update CLAUDE.md after every commit", and 76% of it had become a session log
duplicating git history. The log moved to `docs/sessions/` and the reference
sections to `docs/`; this test is the tripwire that stops it growing back.

If this fails, the fix is almost never to raise the limit. Ask which part of the
new text is a LOG ENTRY (goes in `docs/sessions/<YYYY-MM>.md`) or REFERENCE
material for one sport/subsystem (goes in its own `docs/` file), and which part
is genuinely a rule that governs every future session (stays here).
"""
from __future__ import annotations

import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_MD = os.path.join(ROOT, "CLAUDE.md")

# 31.7 KB after the 2026-08-30 split. The headroom is for promoting real rules,
# not for parking a session summary.
# Tightened 2026-09-03 from 45,000, to lock in the trim rather than leave room
# to drift straight back. The §1b and §7 EVIDENCE moved to
# docs/rules_evidence.md that day (every rule statement stayed here verbatim),
# taking the file from 45,605 to 39,377 bytes.
#
# The headroom is deliberate and small: ~1.6 KB, which is a couple of new rules.
# The file's own footer asks for ~30 KB and it is not there yet — closing that
# gap means moving more evidence out, never dropping a rule. Raise this only
# with a reason; the point of the number is that growth has to be noticed.
# 2026-09-03: the 21 area-specific rules moved to .claude/rules/, which load
# only when Claude opens a matching file. That is the mechanism that keeps this
# flat as the project grows -- a new rule for one area now costs nothing on a
# session that never touches it -- so this cap matters less than it did and is
# a backstop rather than the plan. Lowered 41,000 -> 36,000 to hold the gain.
MAX_BYTES = 36_000


def _read(path: str) -> str:
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def test_claude_md_stays_small_enough_to_load_every_session() -> None:
    size = os.path.getsize(CLAUDE_MD)
    assert size <= MAX_BYTES, (
        f"CLAUDE.md is {size:,} bytes (limit {MAX_BYTES:,}). It is re-read at the "
        "start of every session, so every byte is a permanent context tax. Move "
        "session narrative to docs/sessions/<YYYY-MM>.md and subsystem reference "
        "to its own docs/ file; promote only rules that govern future work."
    )


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


def test_the_session_archive_is_present_and_indexed() -> None:
    sessions = os.path.join(ROOT, "docs", "sessions")
    assert os.path.isdir(sessions), "docs/sessions/ is missing"
    months = [f for f in os.listdir(sessions) if re.fullmatch(r"\d{4}-\d{2}\.md", f)]
    assert months, "docs/sessions/ has no <YYYY-MM>.md archive files"
    index = _read(os.path.join(sessions, "README.md"))
    for month in months:
        assert month[:-3] in index, f"{month} is not listed in docs/sessions/README.md"

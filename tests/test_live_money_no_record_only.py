"""Every graded pick is live money. There is no second bucket.

The published recap used to count a pick in the W-L and leave it out of the
units. That split is not a mode. This test fails when the split, or a
paper-tracking mode, is written back into the code, the rules, or the
standing docs.

Allowlist, and only this:
  * this file (it has to name the phrases in order to forbid them)
  * a migration that drops the old column (it has to name the column)
  * docs/sessions and docs/history (the changelog quotes what was said)
  * docs/rules_evidence.md (it quotes the instructions that created the rules)
"""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Space or hyphen, not underscore: the published-window constant keeps its
# historical name and is a date, not a mode.
# "the record only two ways" and "the published record only" are the
# settled-record rule, not this mode.
_PHRASES = (
    re.compile(r"record_only", re.IGNORECASE),
    re.compile(r"record-only", re.IGNORECASE),
    re.compile(r"record only(?! two)", re.IGNORECASE),
    re.compile(r"paper[ -]trad(?:e|ing)", re.IGNORECASE),
    re.compile(r"paper[ -]track", re.IGNORECASE),
    re.compile(r"paper[ -]only", re.IGNORECASE),
)
_ENGLISH_NOT_A_MODE = re.compile(
    r"record only two ways|published record only",
    re.IGNORECASE,
)

_SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".sql", ".html", ".md", ".mdc", ".js"}

_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".expo",
}

# Changelog and the evidence file quote older instructions. They are not
# the rules a session follows.
_SKIP_PREFIXES = (
    "docs/sessions/",
    "docs/history/",
    "docs/rules_evidence.md",
)


def _rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def _allowed(rel: str, text: str) -> bool:
    if rel == "tests/test_live_money_no_record_only.py":
        return True
    if rel.startswith(_SKIP_PREFIXES) or rel in _SKIP_PREFIXES:
        return True
    # A migration that drops the column has to name it.
    if rel.startswith("data/migrations/") and "DROP COLUMN record_only" in text:
        return True
    return False


def _hits() -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".git")]
        for name in filenames:
            ext = os.path.splitext(name)[1]
            if ext not in _SCAN_SUFFIXES:
                continue
            path = os.path.join(dirpath, name)
            rel = _rel(path)
            try:
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
            except (OSError, UnicodeError):
                continue
            if _allowed(rel, text):
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if _ENGLISH_NOT_A_MODE.search(line):
                    continue
                for phrase in _PHRASES:
                    if phrase.search(line):
                        found.append(f"{rel}:{i}: {line.strip()[:160]}")
                        break
    return found


def test_the_repo_has_no_record_only_or_paper_tracking_mode():
    hits = _hits()
    assert hits == [], (
        "graded picks are live money; units and the record are the same set.\n"
        + "\n".join(hits[:40])
    )


def test_the_snapshot_migration_drops_the_old_column_and_records_both_totals():
    path = os.path.join(
        ROOT, "data", "migrations", "recompute_snapshot_units_2026_10_14.sql")
    text = open(path, encoding="utf-8").read()
    assert "DROP COLUMN record_only" in text
    assert "before_units" in text and "after_units" in text
    assert "COALESCE(p.decision_odds, p.dk_odds)" in text
    assert text.count("DO $mig$") == 1

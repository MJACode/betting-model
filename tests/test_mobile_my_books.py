"""The member's own sportsbooks (Matt, 2026-10-19).

Onboarding asks which books the member uses (every one checked to start),
Settings keeps the same list, and the pick cards, the pick detail and the
Stats lines show only those books. A pick found at a book they do not use is
shown at their best book, with the edge and return worked out at that price;
a pick none of their books has is marked "Not offered at your books".

DISPLAY ONLY: nothing on the model, scorer, record or publishing side reads
the set. These tests pin both halves.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._node import tsx_cmd

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_my_books.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_new_members_start_with_every_book_and_are_asked():
    hook = _read(SRC / "hooks" / "usePreferredBooks.ts")
    assert "const DEFAULT_BOOKS: BookKey[] = BETTABLE_BOOKS;" in hook
    # Stored in Supabase, not only on the phone (CLAUDE.md §1b).
    assert "member_books_get" in hook and "member_books_set" in hook
    app = _read(MOBILE / "App.tsx")
    assert "needsChoice" in app and "booksOnly" in app
    onboarding = _read(SRC / "components" / "OnboardingModal.tsx")
    assert "BookChecklist" in onboarding
    assert "most value" in onboarding


def test_the_pick_surfaces_read_the_set():
    card = _read(SRC / "components" / "PickCard.tsx")
    assert "usePreferredBooks()" in card and "myBooksView(" in card
    assert "bestHandoffForPick(pick, item.bookRows, heroPrice, priceAge, myBooksReady ? myBooks : undefined)" in card
    detail = _read(SRC / "screens" / "PickDetailScreen.tsx")
    assert "allowedBooks={allowedBooks}" in detail
    assert detail.count("allowedBooks={allowedBooks}") == 2  # chips + table


def test_the_models_never_read_the_set():
    """The set is what a member SEES. A model, the scorer, a publisher or the
    record reading it would make one member's state change everyone's pick."""
    for folder in ("models", "tracking", "nfl", "ncaaf_live", "data/ingestors"):
        for path in (ROOT / folder).rglob("*.py"):
            text = _read(path)
            assert "member_sportsbooks" not in text, path
            assert "member_books_" not in text, path

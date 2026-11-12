"""A pick's line at the member's OWN books (Matt, 2026-11-12).

"Coppin State +10.5" was found at Hard Rock +120 and the card said "Not
offered at your books", while BetMGM (+115) and DraftKings (+111) had +10.5 on
their alternate ladders. The card read main lines only. Now it also reads the
ladder rung at the pick's own number, and lists each of the member's books
that only has another number, with that number, as a hand-off.

DISPLAY AND HAND-OFF ONLY: the pick, its line, edge, stake and record stay at
the model's number (CLAUDE.md §1c, §6). Matt: "Everything goes off the main
model for tracking".
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
        [*tsx_cmd(MOBILE), "scripts/verify_other_lines.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_every_pick_board_read_adds_the_same_line_ladder():
    q = _read(SRC / "lib" / "queries.ts")
    # One call per board that enriches game-market picks: today, NFL, NCAAF,
    # college basketball, NHL.
    assert q.count("await addSameLineLadder(booksByGameMarket") == 5
    # Narrowed to the picks' own numbers: the full ladder is ~26k rows a day.
    assert ".in('point', Array.from(points))" in q
    assert ".from('alt_game_lines')" in q


def test_a_different_line_is_never_best_nor_the_sheets_bet():
    card = _read(SRC / "components" / "PickCard.tsx")
    assert "row.price != null && !row.otherLine" in card
    sheet = _read(SRC / "components" / "PickBooksSheet.tsx")
    assert "PICK_BOOKS_OTHER_LINE_NOTE" in sheet

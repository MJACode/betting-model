"""Betslip / saved parlay "Track bet" (Matt, 2026-11-24: "No way for me to add
this to tracker").

The behavioural checks live in `mobile/scripts/verify_parlay_track.ts`. This
file pins the wiring so the button cannot quietly disappear from either screen
when node modules are not installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"

from tests._node import tsx_cmd  # noqa: E402


def _read(rel: str) -> str:
    return (MOBILE / rel).read_text(encoding="utf-8")


def test_betslip_has_track_bet_wired_to_your_bets():
    src = _read("src/screens/ParlayScreen.tsx")
    assert 'accessibilityLabel="Track bet"' in src
    assert "<ManualBetModal" in src
    assert "manualBets.add(input)" in src
    # Priced off the same quotes the "Place this bet at" row shows.
    assert "priceBooksForParlay(pricedLegs, 1, BETTABLE_BOOKS, sgpFits, enteredPrices)" in src


def test_saved_parlay_has_track_bet_wired_to_your_bets():
    src = _read("src/screens/SavedParlaysScreen.tsx")
    assert 'accessibilityLabel="Track bet"' in src
    assert "<ManualBetModal" in src
    assert "savedParlayTrackPrefill(" in src
    assert "manualBets.add(input)" in src


def test_form_never_prefills_the_stake():
    src = _read("src/components/ManualBetModal.tsx")
    assert "setStake('');" in src
    assert "prefill.stake" not in src


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_parlay_track.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

"""Multi-pick sportsbook deep-link carryover.

Matt, 2026-09-20: several picks ready to convert into a sportsbook, only one
landed on the slip. The hand-off sheet opened `firstLink` — the first
single-outcome URL The Odds API stores per pick — and left the rest for a
manual "Add to slip" tap. Books whose stored URL has a measured multi-selection
form (DraftKings `outcomes=` joined with `+`, FanDuel indexed market/selection,
BetMGM comma `options` + `type=combo`, Caesars comma `selectionIds`, ESPN BET
indexed `market_selection_id`) now combine in `combineBetslipLinks`. A book
without that form still opens the first leg; inventing a URL is the other way
to drop picks.

The behavioural checks live in `mobile/scripts/verify_betslip_combine.ts`.
This file pins the wiring so a revert to `firstLink` fails even when node
modules are not installed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_handoff_opens_the_combined_url_not_the_first_leg():
    src = _read(MOBILE / "src" / "components" / "ParlayDkHandoff.tsx")
    # Comments may name the old first-leg-only bug; the identifier must not
    # return as the URL we open.
    code = "\n".join(
        line for line in src.splitlines() if not line.strip().startswith("*") and not line.strip().startswith("//")
    )
    assert "firstLink" not in code
    assert "combineBetslipLinks(" in src
    assert "openBookBetslip(book, openLink)" in src
    # A book we cannot join must still open something.
    assert "combined ?? linked[0]" in src


def test_combiner_is_pure_and_lives_next_to_fill():
    """The opener cannot run in a verify script (react-native). The join can."""
    src = _read(MOBILE / "src" / "lib" / "betslipLinks.ts")
    assert "export function combineBetslipLinks(" in src
    assert "export function fillBetslipLink(" in src
    # Hard Rock / BetRivers must not grow a guessed combiner — null is the
    # honest answer until a stored multi-leg form is measured.
    assert "hardrock" not in src.lower() or "deep_link_value" not in src
    assert "betrivers" not in src or "coupon" not in src.split("combineBetslipLinks")[1]


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_betslip_combine.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

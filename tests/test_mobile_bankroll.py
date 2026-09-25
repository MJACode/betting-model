"""The optional, display-only bankroll in Settings (Designer Option A,
Matt-approved 2026-09-25; scope cut the same day: "No daily limit. This is
purely informational display.").

A member may enter a bankroll so Settings can say what one unit is worth in
dollars. It sizes nothing: picks stay a flat 1u, no Kelly, no limit reads it.
It lives on the device under `bankroll.v2`; #786's `bankroll` key (which
defaulted to $1,000) is never read. The daily exposure card, its
`responsibleGambling.v2` storage and the Picks > Today banner are untouched.

The behavioural pins live in `mobile/scripts/verify_bankroll.ts`; this file
runs it when the mobile toolchain is installed and pins the source-level
shape either way.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
LIB = MOBILE / "src/lib/bankroll.ts"
HOOK = MOBILE / "src/hooks/useBankroll.ts"
SETTINGS = MOBILE / "src/screens/SettingsScreen.tsx"
PICKS = MOBILE / "src/screens/PicksHomeScreen.tsx"
RG = MOBILE / "src/hooks/useResponsibleGambling.ts"
EXPLAINER = MOBILE / "src/screens/ExplainerScreen.tsx"


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def test_storage_key_and_legacy_key_ignored():
    lib = _read(LIB)
    assert "export const BANKROLL_KEY = 'bankroll.v2';" in lib
    assert "store.getItem(BANKROLL_KEY)" in lib
    assert "getItem(LEGACY_BANKROLL_KEY)" not in lib
    for path in (MOBILE / "src").rglob("*.ts*"):
        text = _read(path)
        assert "getItem('bankroll')" not in text, path
        assert 'getItem("bankroll")' not in text, path


def test_copy_is_word_for_word():
    lib = _read(LIB)
    assert (
        "'Only used to show your units in dollars. Nothing is sized off it, and it stays on this device.'"
        in lib
    )
    assert (
        "'A unit is your standard bet. As a starting point, we suggest 1 unit = 1% of your bankroll. "
        "Change it to fit your budget, and only bet what you can afford to lose.'" in lib
    )
    for msg in (
        "Enter an amount greater than $0.",
        "Enter a positive dollar amount.",
        "Enter at least $10.",
        "That's more than we can convert. Enter $10,000,000 or less.",
    ):
        assert msg in lib


def test_section_placement_and_scope():
    settings = _read(SETTINGS)
    assert (
        '<SectionHeader title="Bankroll" />\n\n        <BankrollCard />\n\n'
        '        <SectionHeader title="Staying in control" />' in settings
    )
    assert "Bankroll & limits" not in settings
    for gone in ("Daily limit:", "Presets", "Show $ next to units", "24 hours"):
        assert gone not in settings


def test_display_only_nothing_sized():
    lib = _read(LIB)
    for word in ("stakeFor", "convictionFor", "unitsFor", "recommended_bet"):
        assert word not in lib
    # Only Settings reads it — not the pick cards, the stake math or the banner.
    users = sorted(
        str(p.relative_to(MOBILE / "src")).replace("\\", "/")
        for p in (MOBILE / "src").rglob("*.ts*")
        if "useBankroll(" in _read(p) and p != HOOK
    )
    assert users == ["screens/SettingsScreen.tsx"]


def test_exposure_card_storage_and_banner_unchanged():
    settings = _read(SETTINGS)
    assert "<Text style={styles.cardLabel}>Daily exposure limit</Text>" in settings
    assert "const toggleRgCap = (on: boolean) => setExposureCapUnits(on ? 10 : null);" in settings
    rg = _read(RG)
    assert "const STORAGE_KEY = 'responsibleGambling.v2';" in rg
    assert "bankroll'" not in rg
    picks = _read(PICKS)
    assert "Today’s picks ask for {formatUnits(exposure.total)} — over your{' '}" in picks
    assert "{formatUnits(exposure.cap)} daily limit. Consider sizing" in picks
    assert "bankroll" not in picks.lower()


def test_explainer_no_longer_denies_a_bankroll():
    explainer = " ".join(_read(EXPLAINER).split())
    assert "we never ask for your bankroll" not in explainer
    assert "stays on this device" in explainer
    assert "never sizes a bet" in explainer


def test_runs_in_pr_ci():
    assert "tests/test_mobile_bankroll.py" in _read(ROOT / ".github/workflows/pr-ci.yml")


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_bankroll.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

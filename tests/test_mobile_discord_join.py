"""Discord perk: Join screen, onboarding slide, paywall line, settings tile.

The behavioural pins live in mobile/scripts/verify_discord_join.ts. This
file runs that script when node can strip types, and pins the source shape
either way: paid-only invite, slide with no Join button, once-only storage.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._node import node_exe, node_strips_types

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
NODE = node_exe() or "node"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_discord_join_stays_behind_the_paid_gate():
    helpers = _read(MOBILE / "src/lib/discordHelpers.ts")
    assert "if (!paid) return null;" in helpers
    assert "https://discord.gg/JWMUzK9Da" in helpers
    modal = _read(MOBILE / "src/components/DiscordJoinModal.tsx")
    assert "discordInviteIfPaid(discordPaid)" in modal
    assert "discord.gg" not in modal
    onboarding = _read(MOBILE / "src/components/OnboardingModal.tsx")
    assert "Join Discord" not in onboarding
    assert "discordOnboardingSlide(discordPaid)" in onboarding
    hook = _read(MOBILE / "src/hooks/useDiscordJoin.ts")
    assert "markDiscordJoinChosen" in hook
    assert "discord.join.v1" in _read(MOBILE / "src/lib/discordJoin.ts")
    app = _read(MOBILE / "App.tsx")
    assert app.index("<OnboardingModal") < app.index("<DiscordJoinModal")
    assert "onboardingFinished" in app


def test_runs_in_pr_ci():
    assert "tests/test_mobile_discord_join.py" in _read(ROOT / ".github/workflows/pr-ci.yml")


@pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")
def test_discord_join_script():
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "scripts/verify_discord_join.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "ALL PASS" in proc.stdout

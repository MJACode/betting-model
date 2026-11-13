"""Settings home is the Option B grid. Drill-ins keep today's controls.

The behavioural pins live in mobile/scripts/verify_settings_home.ts. This
file runs that script when node can strip types, and pins the source shape
either way: tile order, the back pill, and that Bankroll and Notifications
are not interactive on the home.
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


def test_home_order_and_drill_ins():
    home = _read(MOBILE / "src/lib/settingsHome.ts")
    order = [
        "'sportsbooks'",
        "'bankroll'",
        "'notifications'",
        "'explore'",
        "'community'",
        "'account'",
        "'legal'",
    ]
    at = [home.index(piece) for piece in order]
    assert at == sorted(at)
    # "sportsbooks" is the section id. Anything else with "sport" would be a
    # per-sport notification line, which this screen does not have.
    assert "sport" not in home.lower().replace("sportsbooks", "")
    settings = _read(MOBILE / "src/screens/SettingsScreen.tsx")
    home_fn = settings.split("export function SettingsScreen(", 1)[1].split(
        "export function SettingsSectionScreen", 1
    )[0]
    assert "navigate('SettingsSection'" in home_fn
    assert "<BankrollCard" not in home_fn
    assert "<NotificationsCard" not in home_fn
    assert "openLink(TERMS_URL, 'Terms of Use')" in settings
    assert "openLink(PRIVACY_URL, 'Privacy Policy')" in settings
    assert "AUTH_ENABLED || billingReady()" in settings
    app = _read(MOBILE / "App.tsx")
    assert 'name="SettingsSection"' in app
    assert "SettingsSectionBackButton" in app
    assert "headerBackVisible: false" in app


def test_runs_in_pr_ci():
    assert "tests/test_mobile_settings_home.py" in _read(ROOT / ".github/workflows/pr-ci.yml")


@pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")
def test_settings_home_script():
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "scripts/verify_settings_home.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "ALL PASS" in proc.stdout

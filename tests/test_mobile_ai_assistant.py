"""AI assistant screens in the app (Settings tile, setup/connected/trial
screen, the Picks intro card and the trial-to-paid sheet).

The behavioural pins live in mobile/scripts/verify_ai_assistant.ts. This file
runs it when node can strip types, and pins the wiring either way.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._node import node_exe, node_strips_types

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
NODE = node_exe() or "node"


def _read(rel: str) -> str:
    return (MOBILE / rel).read_text(encoding="utf-8")


def test_wiring():
    app = _read("App.tsx")
    assert 'name="AiAssistant"' in app and "AiAssistantScreen" in app
    assert "AiAssistant: undefined" in _read("src/types/index.ts")
    settings = _read("src/screens/SettingsScreen.tsx")
    home = settings.split("export function SettingsScreen(", 1)[1].split(
        "export function SettingsSectionScreen", 1)[0]
    assert "<AiAssistantTile" in home and "navigate('AiAssistant')" in home
    picks = _read("src/screens/PicksHomeScreen.tsx")
    assert "<AiAssistantIntro" in picks
    api = _read("src/lib/aiAssistantApi.ts")
    assert "rpc('mcp_my_status')" in api and "rpc('mcp_disconnect')" in api
    # One Disconnect per assistant (Matt, 2026-11-22), wired to the screen.
    assert "rpc('mcp_disconnect_assistant', { p_assistant: assistant })" in api
    screen = _read("src/screens/AiAssistantScreen.tsx")
    assert "onDisconnect(item.assistant)" in screen and "connectedAssistants(status)" in screen


def test_no_one_app_wording_left():
    """2026-11-22: several assistants may connect; nothing may still say one."""
    for rel in ("src/lib/aiAssistant.ts", "src/screens/AiAssistantScreen.tsx"):
        text = _read(rel).lower()
        assert "one connected app" not in text and "one app at a time" not in text, rel
    terms = (ROOT / "web/content/terms.md").read_text(encoding="utf-8").lower()
    assert "one connected assistant" not in terms and "up to three connected assistants" in terms


def test_address_matches_the_server():
    lib = _read("src/lib/aiAssistant.ts")
    server = (ROOT / "supabase/functions/mcp/index.ts").read_text(encoding="utf-8")
    assert "export const MCP_SERVER_ADDRESS = 'signalbase-ai.com/mcp';" in lib
    assert '"https://signalbase-ai.com/mcp"' in server


def test_no_purchase_prompt_on_the_trial_screen():
    """The trial converts on its own; the screen sells nothing (mockup 4)."""
    screen = _read("src/screens/AiAssistantScreen.tsx")
    trial = screen.split("function TrialCard(", 1)[1].split("\nfunction ", 1)[0]
    for word in ("Paywall", "Subscribe", "Upgrade", "purchase"):
        assert word not in trial, word


def test_hooks_reachable_from_picks_are_not_focus_aware():
    for rel in ("src/hooks/useAiAssistant.ts", "src/components/AiAssistantIntro.tsx",
                "src/components/AiAssistantTile.tsx"):
        assert "useFocusEffect" not in _read(rel), rel


def test_runs_in_pr_ci():
    assert "tests/test_mobile_ai_assistant.py" in (ROOT / ".github/workflows/pr-ci.yml").read_text(encoding="utf-8")


@pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")
def test_ai_assistant_script():
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "scripts/verify_ai_assistant.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "ALL PASS" in proc.stdout

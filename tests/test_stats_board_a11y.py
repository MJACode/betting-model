"""#1091 Lows: Stats board headline wrap, missing-price VoiceOver, picker hand-off.

`mobile/scripts/verify_stats_board_a11y.ts` calls the pure helpers and checks
that StatsScreen wires them. No device and no React Native.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"

from tests._node import NODE, node_strips_types  # noqa: E402


@pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")
def test_stats_board_a11y_script_passes():
    proc = subprocess.run(
        [NODE or "node", "--experimental-strip-types", "scripts/verify_stats_board_a11y.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    assert "ALL PASS" in proc.stdout

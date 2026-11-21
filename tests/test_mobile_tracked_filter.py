"""The Tracked filter on the Picks board (Matt, 2026-11-21: show the signals
not yet placed, read off the Track indicator).

The pins live in mobile/scripts/verify_tracked_filter.ts; this runs it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._node import tsx_cmd

MOBILE = Path(__file__).resolve().parents[1] / "mobile"


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_tracked_filter_script():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_tracked_filter.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "ALL PASS" in proc.stdout

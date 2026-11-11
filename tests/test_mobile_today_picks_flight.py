"""Today's board is fetched once and shared.

useTodayPicks used to start the seven-sport read from every mount: the
betslip bar, the Picks screen, Player Stats, and the model screens. The
flight cache collapses concurrent callers onto one request and a finished
read is reused until refresh.

The behaviour is mobile/scripts/verify_today_picks_flight.ts. It runs under
tsx (the app's path alias and the request-count import). Without
mobile/node_modules the behavioural test is skipped; the source pin above
still runs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"

from tests._node import tsx_cmd  # noqa: E402


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_the_hook_reads_through_the_shared_flight():
    """A mount must not call the seven fetches itself. The flight does."""
    src = (MOBILE / "src" / "hooks" / "useTodayPicks.ts").read_text(encoding="utf-8")
    assert "loadTodayBoard(target, false)" in src
    assert "loadTodayBoard(target, true)" in src
    assert "setTodayBoardReader(readTodayBoard)" in src
    # The paused split stays at the source. All reads pausedData; everyone
    # else reads data. Refresh still goes through the same reader.
    assert "setData(all.filter((d) => !isPausedForDisplay(d.pick)))" in src
    assert "setPausedData(all.filter((d) => isPausedForDisplay(d.pick)))" in src


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_single_flight_and_refresh_invalidation():
    proc = _run([*(tsx_cmd(MOBILE) or []), "scripts/verify_today_picks_flight.ts"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "four concurrent callers start one read" in proc.stdout
    assert "refresh after a finished read starts another" in proc.stdout
    assert "ALL PASS" in proc.stdout

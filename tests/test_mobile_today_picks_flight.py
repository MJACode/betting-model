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
    # refresh() forces a read of today's Eastern date, so a pull or a Picks
    # reload after midnight reads the new day, not the one it mounted on.
    refresh = src[src.index("const refresh = useCallback"):]
    refresh = refresh[: refresh.index("}, [date, target")]
    assert "refresh: true" in refresh and "loadTodayBoard(day, true)" in refresh
    # ...and moves every other undated board onto that day, AFTER its read has
    # started so they join it (design review, 2026-11-13: the betslip bar,
    # which never pulls or remounts, kept yesterday's board after midnight).
    assert "moveDay(day)" in refresh, "a refresh after midnight leaves the other boards on yesterday"
    assert refresh.index("loadTodayBoard(day, true)") < refresh.index("moveDay(day)")
    assert "subscribeTodayBoardDay(" in src, "undated boards no longer follow the shared day"
    assert "moveTodayBoardDay(" in src
    assert "setTodayBoardReader(readTodayBoard)" in src
    # Coming back to the app moves an undated board onto the new Eastern date.
    # AppState, not useFocusEffect: the betslip bar is outside the navigator.
    assert "AppState.addEventListener" in src
    assert "useFocusEffect" not in src
    # ...and it does NOT reload. Reloading on return is PicksHomeScreen's rule
    # (#1260: every 10 minutes while focused, and on return when the last load
    # is over a minute old). A second resume reload in the hook would start a
    # read on top of that one.
    assert "loadTodayBoardOnForeground" not in src
    handler = src[src.index("AppState.addEventListener"):]
    handler = handler[: handler.index("return () => sub.remove();")]
    assert "loadTodayBoard" not in handler, "the hook reloads on resume as well as Picks"
    assert "moveDay(todayET())" in handler, "a return after midnight no longer moves the boards to the new date"
    flight = (MOBILE / "src" / "lib" / "todayPicksFlight.ts").read_text(encoding="utf-8")
    assert "export const TODAY_PICKS_STALE_MS = 5 * 60 * 1000;" in flight
    assert "TODAY_BOARD_MAX_AGE_MS" not in flight
    assert "loadTodayBoardOnForeground" not in flight
    assert "Infinity" in flight
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
    assert "a reload from Picks reads even inside the window" in proc.stdout
    assert "a background reload does not clear the error when it starts" in proc.stdout
    assert "a cancelled reload leaves the shown error and the rows" in proc.stdout
    assert "after midnight the bar follows Picks onto the new date" in proc.stdout
    assert "the first read is shown while the follow-up runs" in proc.stdout
    assert "pull-to-refresh after midnight ET reads the new date" in proc.stdout
    assert "a stale mount after midnight ET rolls forward" in proc.stdout
    assert "the staleness age is five minutes" in proc.stdout
    assert "Infinity: a later mount does not re-read" in proc.stdout
    assert "ALL PASS" in proc.stdout

"""Stats threshold bubble: the screen contracts CI can see without the app.

`mobile/scripts/verify_line_ruler.ts` is the full check (stop math and the
typed-line outcomes). It imports the stat catalog, which imports React
Native, so it runs only when `mobile/node_modules` is installed. The PR job
does not install that. The asserts below are the review pins from #993: they
read the source, and they run in that job.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"

from tests._node import tsx_cmd  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _slice(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i:src.index(end, i)]


def test_talkback_can_activate_the_bubble():
    stats = _read(MOBILE / "src/screens/StatsScreen.tsx")
    bubble = _slice(stats, "accessibilityLabel={thresholdBubbleLabel", "pointerEvents=\"none\"")
    assert "accessibilityActions={[{ name: 'activate' }]}" in bubble
    assert "actionName === 'activate') openDraft()" in bubble
    assert "onAccessibilityTap={openDraft}" in bubble


def test_a_bubble_tap_does_not_clear_the_tick_guard_in_the_same_turn():
    stats = _read(MOBILE / "src/screens/StatsScreen.tsx")
    guard = _slice(stats, "const releaseTickGuard", "const scrollToValue")
    tap = _slice(stats, "const onBubbleTap", "const draftSelection")
    assert "requestAnimationFrame" in guard
    assert guard.index("suppressTick.current = false") > guard.index("requestAnimationFrame")
    assert "releaseTickGuard()" in tap
    assert "suppressTick.current = false" not in tap


def test_cancel_scrolls_the_strip_back_and_does_not_change_the_board():
    stats = _read(MOBILE / "src/screens/StatsScreen.tsx")
    cancel = _slice(stats, "const cancelDraft = () => {", "const commitRef")
    assert "scrollToValue(openedValue.current)" in cancel
    assert "onChange(" not in cancel


def test_blur_commits_and_the_clamp_is_announced_once():
    stats = _read(MOBILE / "src/screens/StatsScreen.tsx")
    assert "onBlur={commitDraft}" in stats
    assert "outcome.notice && Platform.OS !== 'android'" in stats
    assert "accessibilityLiveRegion={Platform.OS === 'android' ? 'polite' : undefined}" in stats
    accessory = _slice(stats, "<InputAccessoryView", "</InputAccessoryView>")
    assert "onDone={commitDraft}" in accessory
    assert "Keyboard.dismiss()" not in accessory


def test_cancel_wins_when_blur_fires_before_the_click():
    # Web blurs the field on mouse-down, before Cancel's click, and
    # react-native-web delays onPressIn by 50ms, so a latch set there is
    # already late. Cancel's host calls preventDefault on that mouse-down,
    # which keeps the field focused. Done does not. A blur elsewhere still
    # commits: onBlur stays wired to commitDraft.
    stats = _read(MOBILE / "src/screens/StatsScreen.tsx")
    bar = _slice(stats, "function ThresholdDoneBar", "function LineRuler")
    cancel, done = bar.split('accessibilityLabel="Done"', 1)
    assert "addEventListener('mousedown', keepFocus)" in cancel
    assert "event.preventDefault()" in cancel
    assert "ref={cancelHost}" in cancel
    assert "preventDefault" not in done
    assert "onPress={onCancel}" in cancel
    assert "onBlur={commitDraft}" in stats
    assert "cancelPending" not in stats


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_verify_line_ruler_script():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_line_ruler.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ALL PASS" in proc.stdout

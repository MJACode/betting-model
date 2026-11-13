"""Freeze and restart tracking in the mobile app (2026-11-06).

Matt: a screen stopped responding ("Cannot move from that screen need to
restart. This keeps happening in other spots"), and app_errors held nothing,
because a freeze throws no error. mobile/src/lib/freezeLog.ts records a trail
of screens, taps and pop-ups and reports `restart`, `js_stall` and
`modal_stuck` (docs/app_errors.md).

* the logic -- mobile/scripts/verify_freeze_log.ts under node. Each guard was
  watched failing by breaking the code it checks (the onShow clear, the
  background window, the watchdog clock reset, the trail hook, the stall cap);
* the wiring -- every pop-up goes through TrackedModal, and the root starts it.
"""

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"


def test_the_freeze_log_logic_holds():
    from tests._node import NODE, node_strips_types
    if not node_strips_types():
        pytest.skip("node >= 22.6 not available")
    script = (MOBILE / "scripts" / "verify_freeze_log.ts").read_text(encoding="utf-8")
    script = script.replace("'../src/lib/freezeLog'", "'./freezeLog.ts'")
    script = script.replace("'../src/lib/crashLog'", "'./crashLog.ts'")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "verify_freeze_log.ts").write_text(script, encoding="utf-8")
        for name in ("freezeLog.ts", "crashLog.ts"):
            (folder / name).write_text((SRC / "lib" / name).read_text(encoding="utf-8"), encoding="utf-8")
        (folder / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        proc = subprocess.run(
            [NODE, "--experimental-strip-types", "verify_freeze_log.ts"],
            cwd=folder, capture_output=True, text=True, timeout=60,
        )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "[FAIL]" not in proc.stdout
    for line in (
        "ended on screen: reported as restart, naming the screen",
        "relaunched 10 min after background: not reported",
        "time spent in background is not a stall",
        "a pop-up iOS showed is not stuck",
        "a pop-up iOS never showed is reported as modal_stuck present",
        "a js_error report carries the trail",
        "stall reports are capped per launch",
    ):
        assert f"[PASS] {line}" in proc.stdout, line


def test_freeze_log_is_free_of_app_imports():
    """It must run under bare node, like crashLog.ts."""
    src = (SRC / "lib" / "freezeLog.ts").read_text(encoding="utf-8")
    assert not re.search(r"^import ", src, flags=re.M)


def _tsx_files():
    return [p for p in SRC.rglob("*.tsx")] + [MOBILE / "App.tsx"]


def test_every_pop_up_goes_through_tracked_modal():
    """A pop-up opened with react-native's Modal directly is invisible to the
    freeze log, and a stuck one is the leading suspect for a frozen screen."""
    offenders = []
    for p in _tsx_files():
        if p.name == "TrackedModal.tsx":
            continue
        src = p.read_text(encoding="utf-8")
        for m in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*'react-native';", src):
            if re.search(r"\bModal\b", m.group(1)):
                offenders.append(str(p.relative_to(MOBILE)))
        for m in re.finditer(r"<Modal\b(?![^>]*\btrackName=)", src):
            offenders.append(f"{p.relative_to(MOBILE)}: <Modal without trackName")
    assert not offenders, offenders


def test_the_root_starts_it_and_feeds_it():
    app = (MOBILE / "App.tsx").read_text(encoding="utf-8")
    assert "startFreezeLogging();" in app
    assert "noteScreen(name);" in app
    assert "onTouchStart={noteTouch}" in app
    setup = (SRC / "lib" / "freezeLogSetup.ts").read_text(encoding="utf-8")
    assert "setTrailProvider(" in setup and "AppState.addEventListener" in setup

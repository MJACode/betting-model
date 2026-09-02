"""
The app must apply published OTA bundles by itself.

WHY THIS IS A TEST. `.github/workflows/mobile-ota.yml` publishes every JS-only
merge to the production channel within minutes, and it does. Publishing is not
delivering: expo-updates' default is check-on-launch and apply on the NEXT cold
launch, so an installed build renders the bundle it launched with until someone
force-quits it twice. On 2026-08-31 that produced a visible wrong number — the
in-app daily recap showed Sunday's MLB day as 7 picks / 2-5 / -$325.93 (the
pre-2026-08-30 rule, in-play picks excluded) while the Discord recap, computed
server-side from the same rows and the same thresholds, had already posted
10-6 / +11.4% with 9 in-play bets.

The fix is `useOtaUpdates()` at the app root. The behaviour it wraps is pinned
off-device by mobile/scripts/verify_ota_update.ts; what THAT harness cannot see
is whether App.tsx still calls the hook, which is the one line a refactor can
silently drop. Hence this test.

Source is read with an explicit encoding: the repo runs on Windows, where
read_text() defaults to cp1252 and raises on the box-drawing characters these
files contain (see CLAUDE.md §7).
"""
from __future__ import annotations

from pathlib import Path

import pytest

MOBILE = Path(__file__).resolve().parents[1] / "mobile"


def _read(rel: str) -> str:
    return (MOBILE / rel).read_text(encoding="utf-8")


def test_app_root_mounts_the_ota_updater() -> None:
    app = _read("App.tsx")
    assert "from '@/hooks/useOtaUpdates'" in app, (
        "App.tsx no longer imports useOtaUpdates — published OTA bundles would "
        "again wait for a manual force-quit"
    )
    assert "useOtaUpdates();" in app, (
        "useOtaUpdates is imported but never called in App.tsx"
    )


def test_the_updater_actually_applies_the_update() -> None:
    """A checker that fetches but never reloads is the pre-fix behaviour."""
    lib = _read("src/lib/otaUpdate.ts")
    for call in ("checkForUpdateAsync", "fetchUpdateAsync", "reloadAsync"):
        assert call in lib, f"otaUpdate.ts no longer calls {call}"
    assert "api.reloadAsync()" in lib, (
        "the fetched bundle is never applied — fetching without reloading leaves "
        "the update for a relaunch that may never happen"
    )


@pytest.mark.parametrize("path", [
    "scripts/verify_ota_update.ts",
    "src/hooks/useOtaUpdates.ts",
    "src/lib/otaUpdate.ts",
])
def test_the_pieces_exist(path: str) -> None:
    assert (MOBILE / path).is_file(), f"missing {path}"

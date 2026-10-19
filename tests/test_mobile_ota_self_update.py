"""
The app must download published OTA bundles by itself, and never apply one
to a running app.

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

import re
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


def test_the_updater_downloads_the_update() -> None:
    """The 2026-08-31 gap: the app must FIND and FETCH a published bundle by
    itself, so the next cold start runs it."""
    lib = _read("src/lib/otaUpdate.ts")
    for call in ("api.checkForUpdateAsync()", "api.fetchUpdateAsync()"):
        assert call in lib, f"otaUpdate.ts no longer calls {call}"
    hook = _read("src/hooks/useOtaUpdates.ts")
    assert "downloadUpdate(api)" in hook


def _code_only(src: str) -> str:
    """Source with // and /* */ comments removed, so a comment that NAMES the
    banned call does not count as calling it."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())


def test_nothing_in_the_app_reloads_a_running_app() -> None:
    """Matt, 2026-10-19 (option A): never apply a bundle to a running app. The
    TestFlight crash of 10:41 ET was expo-updates' ErrorRecovery aborting on a
    fatal JS error inside its 10 s post-render window, in a process launched at
    09:04, i.e. right after an in-process reload on return from the background.
    So no app code may call reloadAsync, and UpdatesApi does not offer it."""
    callers = []
    for path in [MOBILE / "App.tsx", *(MOBILE / "src").rglob("*.ts*")]:
        if re.search(r"reloadAsync\s*\(", _code_only(path.read_text(encoding="utf-8"))):
            callers.append(str(path.relative_to(MOBILE)))
    assert not callers, f"these call reloadAsync: {callers}"
    lib = _code_only(_read("src/lib/otaUpdate.ts"))
    api = lib.split("export interface UpdatesApi", 1)[1].split("}", 1)[0]
    assert "reloadAsync" not in api


@pytest.mark.parametrize("path", [
    "scripts/verify_ota_update.ts",
    "src/hooks/useOtaUpdates.ts",
    "src/lib/otaUpdate.ts",
])
def test_the_pieces_exist(path: str) -> None:
    assert (MOBILE / path).is_file(), f"missing {path}"


def test_every_trigger_only_downloads() -> None:
    """Launch and a real return both download; a downloaded bundle waits for
    the next cold start and no further check runs this session."""
    hook = _read("src/hooks/useOtaUpdates.ts")
    assert "void run('launch', null);" in hook
    assert "nextAction(" in hook, "the hook must route every trigger through nextAction"
    lib = _read("src/lib/otaUpdate.ts")
    assert "export type UpdateAction = 'download' | 'skip';" in lib
    body = lib.split("export function nextAction", 1)[1].split("\n}\n", 1)[0]
    assert "if (s.trigger === 'launch') return 'download';" in body
    assert "if (s.pending) return 'skip';" in body

"""Sentry in the mobile app (2026-11-06, Matt: "Yes continue with all").

Pinned: privacy settings (no PII, no screenshots, replay off), the native
config a build needs, the app version bump that keeps OTA bundles importing
the Sentry native module away from 1.2.0 binaries, and a missing Sentry token
never failing a build or an OTA.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests._node import NODE, tsx_cmd

ROOT = Path(__file__).parent.parent
MOBILE = ROOT / "mobile"


def _src():
    return (MOBILE / "src" / "lib" / "sentry.ts").read_text(encoding="utf-8")


def test_privacy_settings():
    src = _src()
    for line in ("sendDefaultPii: false", "attachScreenshot: false", "attachViewHierarchy: false"):
        assert line in src, line
    # Any NUMBER here, 0 included, installs replay / tracing in 7.2.0.
    init = src.split("Sentry.init({", 1)[1].split("});", 1)[0]
    code = "\n".join(l.split("//", 1)[0] for l in init.splitlines())
    for key in ("tracesSampleRate", "replaysSessionSampleRate", "replaysOnErrorSampleRate", "tracesSampler"):
        assert key not in code, key + " is set: that turns the feature ON"
    assert "enableAppHangTracking: true" in src and "enableNativeCrashHandling: true" in src


PUBLIC_DSN = (
    "https://f8fbe2f714eba74c4159b93cf987a942"
    "@o4512386387017728.ingest.us.sentry.io/4512386389311488"
)


def test_the_public_dsn_is_set():
    src = _src()
    assert f"'{PUBLIC_DSN}'" in src
    assert "export const SENTRY_DSN = ''" not in src


def test_an_empty_dsn_starts_nothing():
    src = _src()
    start = src.split("export function startSentry", 1)[1].split("function initSentry", 1)[0]
    assert "if (started || !SENTRY_DSN)" in start
    assert "return Promise.resolve();" in start
    assert "peekDeviceId()" not in start.split("if (started || !SENTRY_DSN)", 1)[0]
    assert "Sentry.init" not in start
    assert "SENTRY_DSN ? Sentry.wrap(component) : component" in src


def test_the_root_starts_it_and_names_the_screen():
    app = (MOBILE / "App.tsx").read_text(encoding="utf-8")
    # The call, not the helper that mentions startCrashLogging above it.
    assert app.index("const sentryStarting = startSentry();") < app.index("if (sentryReadyNow()) startOtherLoggers();")
    # Empty DSN, and a device id already on disk, start the other loggers in
    # this turn. Only the first launch with a DSN waits.
    assert "if (sentryReadyNow()) startOtherLoggers();" in app
    body = app.split("function startOtherLoggers()", 1)[1].split("const sentryStarting", 1)[0]
    assert body.index("startCrashLogging()") < body.index("startFreezeLogging()") < body.index("startPerfLogging()")
    assert "setSentryScreen(name);" in app
    assert "export default wrapWithSentry(App);" in app


def test_device_id_and_release_are_on_the_first_event():
    src = _src()
    start = src.split("export function startSentry", 1)[1].split("function initSentry", 1)[0]
    init = src.split("function initSentry", 1)[1].split("export function setSentryScreen", 1)[0]
    assert "peekDeviceId()" in start
    assert "getDeviceId()" not in init
    assert "initialScope:" in init
    assert "scopeTags({ deviceId, release: APP_VERSION, updateId })" in init
    assert "beforeSend: scrubSentryEvent" in init
    assert "beforeBreadcrumb: scrubBreadcrumb" in init
    # No release option on init: that would replace the native release and
    # the dSYM uploaded with the binary would no longer match.
    code = "\n".join(line.split("//", 1)[0] for line in init.split("Sentry.init({", 1)[1].split("});", 1)[0].splitlines())
    assert re.search(r"^\s*release\s*:", code, re.M) is None


def test_native_config():
    pkg = json.loads((MOBILE / "package.json").read_text(encoding="utf-8"))
    assert "@sentry/react-native" in pkg["dependencies"]
    app = json.loads((MOBILE / "app.json").read_text(encoding="utf-8"))["expo"]
    assert any(isinstance(p, list) and p[0] == "@sentry/react-native/expo" for p in app["plugins"])
    metro = (MOBILE / "metro.config.js").read_text(encoding="utf-8")
    assert "getSentryExpoConfig(__dirname)" in metro


def test_version_moved_past_the_last_binary_without_sentry():
    """runtimeVersion is appVersion: an OTA importing @sentry/react-native must
    never reach a 1.2.0 binary, which lacks the native module and would crash
    on launch."""
    app = json.loads((MOBILE / "app.json").read_text(encoding="utf-8"))["expo"]
    assert app["runtimeVersion"] == {"policy": "appVersion"}
    assert tuple(int(x) for x in app["version"].split(".")) >= (1, 3, 0)


def test_a_missing_sentry_token_never_fails_a_build_or_an_ota():
    eas = json.loads((MOBILE / "eas.json").read_text(encoding="utf-8"))
    assert eas["build"]["production"]["env"]["SENTRY_ALLOW_FAILURE"] == "true"
    ota = (ROOT / ".github" / "workflows" / "mobile-ota.yml").read_text(encoding="utf-8")
    publish = ota.split("- name: Publish OTA", 1)[1].split("- name:", 1)[0]
    assert "npx expo export" in publish and "--source-maps" in publish and "--output-dir dist" in publish
    assert "--skip-bundler" in publish and "--input-dir dist" in publish
    step = ota.split("- name: Upload source maps to Sentry", 1)[1].split("- name:", 1)[0]
    assert "exit 0" in step and "node scripts/upload-ota-sourcemaps.mjs dist" in step
    assert ota.index("Publish OTA") < ota.index("Upload source maps to Sentry")


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_scrubber_and_init_tags():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_sentry_scrub.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ALL PASS" in proc.stdout


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_ota_upload_uses_the_native_release_and_dist(tmp_path: Path):
    """The published bundle and the map are one export. Release and dist are
    the native SDK's, from app.json, so the upload names the same pair an
    event carries when Sentry.init does not override them."""
    dist = tmp_path / "dist" / "_expo" / "static" / "js" / "ios"
    dist.mkdir(parents=True)
    (dist / "entry.hbc").write_bytes(b"bytecode")
    source_map = dist / "entry.hbc.map"
    source_map.write_text(
        json.dumps({"version": 3, "debugId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "mappings": ""}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [NODE, str(MOBILE / "scripts" / "upload-ota-sourcemaps.mjs"), "--dry-run", str(tmp_path / "dist")],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    app = json.loads((MOBILE / "app.json").read_text(encoding="utf-8"))["expo"]
    assert plan["release"] == f"{app['ios']['bundleIdentifier']}@{app['version']}+{app['ios']['buildNumber']}"
    assert plan["dist"] == str(app["ios"]["buildNumber"])
    assert plan["groups"][0]["hermes"] is True
    assert plan["groups"][0]["debugId"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    rewritten = json.loads(source_map.read_text(encoding="utf-8"))
    assert rewritten["debug_id"] == rewritten["debugId"]

    empty = tmp_path / "empty"
    empty.mkdir()
    missing = subprocess.run(
        [NODE, str(MOBILE / "scripts" / "upload-ota-sourcemaps.mjs"), "--dry-run", str(empty)],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert missing.returncode != 0

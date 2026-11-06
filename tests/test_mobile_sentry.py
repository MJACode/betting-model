"""Sentry in the mobile app (2026-11-06, Matt: "Yes continue with all").

Pinned: privacy settings (no PII, no screenshots, replay off), the native
config a build needs, the app version bump that keeps OTA bundles importing
the Sentry native module away from 1.2.0 binaries, and a missing Sentry token
never failing a build or an OTA.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOBILE = ROOT / "mobile"


def _src():
    return (MOBILE / "src" / "lib" / "sentry.ts").read_text(encoding="utf-8")


def test_privacy_settings():
    src = _src()
    for line in ("sendDefaultPii: false", "attachScreenshot: false", "attachViewHierarchy: false",
                 "replaysSessionSampleRate: 0", "replaysOnErrorSampleRate: 0", "tracesSampleRate: 0"):
        assert line in src, line
    assert "enableAppHangTracking: true" in src and "enableNativeCrashHandling: true" in src


def test_an_empty_dsn_starts_nothing():
    src = _src()
    assert "if (started || !SENTRY_DSN) return;" in src
    assert "SENTRY_DSN ? Sentry.wrap(component) : component" in src


def test_the_root_starts_it_and_names_the_screen():
    app = (MOBILE / "App.tsx").read_text(encoding="utf-8")
    assert app.index("startSentry();") < app.index("startCrashLogging();")
    assert "setSentryScreen(name);" in app
    assert "export default wrapWithSentry(App);" in app


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
    step = ota.split("- name: Upload source maps to Sentry", 1)[1].split("- name:", 1)[0]
    assert "exit 0" in step and "npx sentry-expo-upload-sourcemaps dist" in step
    assert ota.index("Publish OTA") < ota.index("Upload source maps to Sentry")

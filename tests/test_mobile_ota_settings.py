"""The OTA bundle must carry the app's settings, or every phone rolls back.

From #1202 (2026-11-06) the OTA workflow bundled with a local `expo export`,
which does not load the EAS "production" environment. Every OTA from then until
2026-11-15 shipped without EXPO_PUBLIC_SUPABASE_URL, threw "supabaseUrl is
required" at launch, and expo-updates rolled each phone back to the bundle in
its TestFlight build. app_timings shows phones only ever ran build-embedded
bundles in that window (docs/sessions/2026-11.md).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OTA = (ROOT / ".github" / "workflows" / "mobile-ota.yml").read_text(encoding="utf-8")


def _publish_step() -> str:
    start = OTA.index("- name: Publish OTA")
    end = OTA.index("- name:", start + 1)
    return OTA[start:end]


def test_settings_are_pulled_before_the_bundle_is_built():
    step = _publish_step()
    pull = step.find("eas env:pull --environment production")
    export = step.find("npx expo export")
    assert pull != -1, "the publish step must pull the EAS production environment"
    assert export != -1
    assert pull < export, "settings must be pulled before the bundle is built"
    assert "--path .env.local" in step


def test_a_missing_setting_publishes_nothing():
    step = _publish_step()
    assert re.search(r'if \[ -z "\$SUPABASE_URL" \] \|\| \[ -z "\$ANON_KEY" \]; then[\s\S]{0,200}exit 1', step)


def test_a_bundle_without_the_supabase_url_publishes_nothing():
    step = _publish_step()
    guard = step.find('grep -aqF "$SUPABASE_URL" "$BUNDLE"')
    publish = step.find("eas update --skip-bundler")
    assert guard != -1, "the built bundle must be checked for the Supabase URL"
    assert publish != -1
    assert guard < publish, "the check must run before anything is published"
    assert "for plat in ios android; do" in step

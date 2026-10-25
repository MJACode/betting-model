"""The marketing site renders legal copy without placeholders and keeps the
record math aligned with the app."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def load_build():
    spec = importlib.util.spec_from_file_location("signalbase_web_build", WEB / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legal_source_stays_intact_and_the_pages_drop_placeholders(tmp_path):
    build = load_build()
    terms_src = (WEB / "content" / "terms.md").read_text(encoding="utf-8")
    privacy_src = (WEB / "content" / "privacy.md").read_text(encoding="utf-8")
    assert "DRAFT" in terms_src and "[DATE]" in terms_src and "ATTORNEY NOTE" in terms_src
    assert "DRAFT" in privacy_src and "[DATE]" in privacy_src

    when = build.build(tmp_path, "2026-10-24")

    assert (WEB / "content" / "terms.md").read_text(encoding="utf-8") == terms_src
    assert (WEB / "content" / "privacy.md").read_text(encoding="utf-8") == privacy_src
    assert when == "October 24, 2026"

    for name in ("terms/index.html", "privacy/index.html", "index.html"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "[" not in text
        assert "ATTORNEY NOTE" not in text
        assert "FOR ATTORNEY REVIEW" not in text
        assert "[DATE]" not in text
        assert "21+" in text
        assert "not a sportsbook" in text
        assert "mailto:Signalbaseskinny@gmail.com" in text
        assert "tel:+18004262537" in text
        assert "1-800-GAMBLER" in text
        assert "apps.apple.com" not in text
        assert "play.google.com" not in text

    terms = (tmp_path / "terms" / "index.html").read_text(encoding="utf-8")
    assert "<strong>Effective date:</strong> October 24, 2026" in terms
    assert "filled in at publish" not in terms
    assert "the date these terms are published" not in terms
    assert "Norfolk County, Massachusetts." in terms
    assert "please review" not in terms
    assert "https://www.1800gambler.net" in terms
    privacy = (tmp_path / "privacy" / "index.html").read_text(encoding="utf-8")
    assert "<strong>Effective date:</strong> October 24, 2026" in privacy
    assert "filled in at publish" not in privacy
    assert "the date this policy is published" not in privacy
    assert "does not use cookies or analytics" in privacy
    assert (
        "When you delete your account in the app, it is removed right away, "
        "and remaining server data and backups are purged within 30 days."
    ) in privacy
    assert "filled in at publish" in terms_src
    assert "filled in at publish" in privacy_src


def test_a_leftover_bracket_fails_the_build():
    build = load_build()
    with pytest.raises(build.PlaceholderError):
        build.render_legal_markdown("See [STILL HERE] before you continue.\n", "October 24, 2026")


def test_landing_record_row_is_hidden_until_the_live_view_loads(tmp_path):
    build = load_build()
    build.build(tmp_path, "2026-10-24")
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'id="record"' in html
    assert "hidden" in html
    assert 'id="record-picks"' in html
    script = (tmp_path / "record.js").read_text(encoding="utf-8")
    assert "v_public_track_record" in script
    assert "sport,model_id,picks,wins,losses,pushes,units,risked" in script
    assert "credentials: \"omit\"" in script or 'credentials: "omit"' in script
    config = json.loads((WEB / "src" / "public-config.json").read_text(encoding="utf-8"))
    payload = config["supabaseAnonKey"].split(".")[1]
    payload += "=" * (-len(payload) % 4)
    import base64

    claims = json.loads(base64.urlsafe_b64decode(payload))
    assert claims["role"] == "anon"
    assert claims["ref"] == "vvprgnrmzeekokzkrkfu"
    assert "service_role" not in config["supabaseAnonKey"]


def test_record_math_matches_the_node_suite():
    completed = subprocess.run(
        ["node", "--test", "src/record-math.test.mjs"],
        cwd=WEB,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

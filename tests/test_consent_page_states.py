"""The AI-assistant consent page must show one step at a time.

2026-11-23: `.consent-form { display: flex }` beat the `hidden` attribute the
page toggles, so the email step, the code step and the error box all rendered
together; a member kept tapping "Send code", the first send succeeded and the
next nine hit Supabase's per-email rate limit (429), which the page reported as
"Something went wrong". Checked in a browser against the built page; these pin
the two pieces of the fix in source.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hidden_beats_consent_display_rules():
    css = (ROOT / "web/static/site.css").read_text(encoding="utf-8")
    assert re.search(r"\.consent-card \[hidden\]\s*\{\s*display:\s*none\s*!important;", css)


def test_send_code_is_single_flight_and_429_goes_to_code_step():
    js = (ROOT / "web/src/consent-boot.js").read_text(encoding="utf-8")
    assert 'if (button.disabled) return;' in js
    assert "e.status === 429" in js
    html = (ROOT / "web/templates/consent.html").read_text(encoding="utf-8")
    assert 'id="send-code"' in html and 'id="code-note"' in html


def test_error_step_offers_try_again():
    html = (ROOT / "web/templates/consent.html").read_text(encoding="utf-8")
    assert 'id="error-retry"' in html
    js = (ROOT / "web/src/consent-boot.js").read_text(encoding="utf-8")
    assert '$("error-retry").addEventListener("click"' in js


def test_code_step_offers_resend_with_cooldown():
    """2026-11-23 (Matt): a member who never gets the email needs a way to ask
    for a new code from the code step. The button calls /otp again and waits
    out Supabase's per-email window before it can be tapped again."""
    html = (ROOT / "web/templates/consent.html").read_text(encoding="utf-8")
    assert 'id="code-resend"' in html
    js = (ROOT / "web/src/consent-boot.js").read_text(encoding="utf-8")
    assert '$("code-resend").addEventListener("click"' in js
    handler = js.split('$("code-resend").addEventListener("click"', 1)[1]
    assert "requestCode()" in handler and "startResendWait()" in handler

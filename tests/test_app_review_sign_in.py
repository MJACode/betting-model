"""App Review sign-in: one email, a code that is never committed.

The attempt-log migration stays out of ACTIVE_MIGRATIONS so a merge does
not apply it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "mobile" / "APP_STORE_METADATA.md"
MIGRATION = ROOT / "data" / "migrations" / "app_review_sign_in_attempts_2026_11_04.sql"
DEMO_EMAIL = "review@signalbase-ai.com"
SIX_DIGITS = re.compile(r"(?<!\d)\d{6}(?!\d)")


def _fence(heading_prefix: str) -> str:
    text = META.read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)
    for part in parts:
        if not part.startswith(heading_prefix):
            continue
        match = re.search(r"```\n(.*?)```", part, flags=re.S)
        assert match, heading_prefix
        body = match.group(1)
        if body.endswith("\n"):
            body = body[:-1]
        return body
    raise AssertionError(heading_prefix)


def test_keywords_drop_discord_for_signals():
    keywords = _fence("Keywords")
    assert "discord" not in keywords
    assert "signals" in keywords.split(",")
    assert " " not in keywords
    assert len(keywords) <= 100
    assert keywords == (
        "ncaab,nfl,mlb,nhl,nba,ncaaf,wnba,ufc,picks,premium,signals,"
        "props,stats,odds,record,live,edge,lines"
    )
    assert len(keywords) == 98


def test_reviewer_lines_name_the_email_and_leave_the_code_blank():
    text = META.read_text(encoding="utf-8")
    assert f"**User name:** {DEMO_EMAIL}" in text
    assert "TODO — Matt fills a fresh 6-digit code" in text
    password = text.split("**Password:**", 1)[1].split("\n", 1)[0]
    assert SIX_DIGITS.search(password) is None
    notes = _fence("App Review Notes")
    assert DEMO_EMAIL in notes
    assert "This note does not contain that code." in notes
    assert SIX_DIGITS.search(notes) is None
    assert len(notes) <= 4000
    what = _fence("TestFlight — What to Test")
    assert SIX_DIGITS.search(what) is None
    assert len(what) <= 4000
    beta = _fence("TestFlight — Beta App Description")
    assert SIX_DIGITS.search(beta) is None
    assert len(beta) <= 4000
    # The sandbox tester is still Matt's, and the line still says so.
    assert "**Sandbox Apple ID for StoreKit:** TODO" in text


def test_no_sign_in_code_literal_in_the_review_sources():
    """A six-digit token next to the review account is a published code.

    The verify script is allowed fixture digits. It must not name a
    DEMO_OTP constant.
    """
    paths = [
        META,
        ROOT / "mobile" / "docs" / "AUTHENTICATION.md",
        ROOT / "mobile" / "TESTFLIGHT.md",
        ROOT / "mobile" / "src" / "lib" / "appReview.ts",
        ROOT / "mobile" / "src" / "lib" / "auth.ts",
        ROOT / "supabase" / "functions" / "app-review-sign-in" / "index.ts",
        ROOT / "supabase" / "functions" / "_shared" / "appReviewSignIn.ts",
        ROOT / "data" / "migrations" / "app_review_sign_in_attempts_2026_11_04.sql",
    ]
    hits = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if "DEMO_OTP" in text and re.search(r"DEMO_OTP\s*=\s*['\"]?\d{6}", text):
            hits.append(f"{path.relative_to(ROOT)} assigns DEMO_OTP")
        for match in SIX_DIGITS.finditer(text):
            hits.append(f"{path.relative_to(ROOT)}:{match.group(0)}")
    script = (ROOT / "mobile" / "scripts" / "verify_app_review_sign_in.ts").read_text(
        encoding="utf-8"
    )
    assert re.search(r"DEMO_OTP\s*=\s*['\"]?\d{6}", script) is None
    assert hits == []


def test_attempt_log_is_not_applied_by_the_worker():
    listed = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    assert MIGRATION.name not in listed
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON TABLE public.app_review_sign_in_attempts FROM anon, authenticated" in sql
    assert "GRANT SELECT, INSERT, DELETE ON TABLE public.app_review_sign_in_attempts TO service_role" in sql
    assert "bucket" in sql
    assert "SHA-256" in sql
    assert "app_review_sign_in_attempts" in sql


@pytest.mark.skipif(
    not (ROOT / "mobile" / "node_modules" / ".bin" / "tsx").exists()
    or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_verify_script_passes():
    tsx = ROOT / "mobile" / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_app_review_sign_in.ts"],
        cwd=ROOT / "mobile",
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ALL PASS" in proc.stdout

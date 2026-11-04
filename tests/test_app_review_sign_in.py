"""App Review sign-in: one email, one fixed code, keywords without discord.

The code is documented in mobile/APP_STORE_METADATA.md. It must not appear
in the app binary sources or the edge function. The attempt-log migration
stays out of ACTIVE_MIGRATIONS so a merge does not apply it.
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
DEMO_OTP = "847291"


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


def test_reviewer_lines_name_the_demo_email_and_code():
    text = META.read_text(encoding="utf-8")
    assert f"**User name:** {DEMO_EMAIL}" in text
    assert f"**Password:** {DEMO_OTP}." in text
    notes = _fence("App Review Notes")
    assert DEMO_EMAIL in notes
    assert DEMO_OTP in notes
    assert "No email is sent" in notes
    assert len(notes) <= 4000
    what = _fence("TestFlight — What to Test")
    assert DEMO_OTP not in what
    assert len(what) <= 4000
    beta = _fence("TestFlight — Beta App Description")
    assert DEMO_OTP not in beta
    assert len(beta) <= 4000
    # The sandbox tester is still Matt's, and the line still says so.
    assert "**Sandbox Apple ID for StoreKit:** TODO" in text


def test_documented_code_is_not_in_the_client_or_the_function():
    roots = [ROOT / "mobile" / "src", ROOT / "supabase" / "functions"]
    hits = []
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".js"}:
                continue
            if DEMO_OTP in path.read_text(encoding="utf-8"):
                hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_attempt_log_is_not_applied_by_the_worker():
    listed = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    assert MIGRATION.name not in listed
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON TABLE public.app_review_sign_in_attempts FROM anon, authenticated" in sql
    assert "GRANT SELECT, INSERT, DELETE ON TABLE public.app_review_sign_in_attempts TO service_role" in sql
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

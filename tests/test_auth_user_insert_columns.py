"""A hand-written INSERT INTO auth.users must set every token column GoTrue
scans as a non-NULL string. On 2026-11-16 nine comped accounts (inserted by
scripts/grant_*_comped_*.sql without email_change) got HTTP 500 on /otp:
"Scan error on column email_change: converting NULL to string is unsupported".
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REQUIRED = (
    "confirmation_token",
    "recovery_token",
    "email_change",
    "email_change_token_new",
    "email_change_token_current",
    "reauthentication_token",
)


def _auth_user_inserts():
    for path in sorted((REPO / "scripts").rglob("*.sql")) + sorted(
        (REPO / "data" / "migrations").rglob("*.sql")
    ) + [REPO / "scripts" / "premium_access.py"]:
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"INSERT\s+INTO\s+auth\.users\s*\((.*?)\)", text, re.I | re.S):
            cols = {c.strip().lower() for c in m.group(1).split(",")}
            yield path, cols


def test_there_is_something_to_check():
    assert list(_auth_user_inserts()), "no INSERT INTO auth.users found; update this test"


def test_every_auth_user_insert_sets_the_scanned_token_columns():
    missing = {
        str(p.relative_to(REPO)): sorted(set(REQUIRED) - cols)
        for p, cols in _auth_user_inserts()
        if set(REQUIRED) - cols
    }
    assert not missing, missing

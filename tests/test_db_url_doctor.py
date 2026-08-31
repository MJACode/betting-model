"""
Tests for scripts/db_url_doctor.py.

Two properties matter, and the second is the one that makes the tool safe to
run anywhere and paste the output into a chat:

  1. It NAMES each failure mode, rather than reporting the driver's single
     undifferentiated "password authentication failed".
  2. It NEVER emits the password, in any branch, including the branches that
     talk about the password's characters.

Both were mutation-checked. Two of the cases below (the placeholder, and a
password whose special characters make the port unparseable) are here because
the first version of the tool got them wrong -- it crashed on one and gave a
misleading message about IPv6 addresses on the other.
"""

from __future__ import annotations

import pytest

from scripts.db_url_doctor import diagnose


REF = "vvprgnrmzeekokzkrkfu"
HOST = "aws-1-us-west-2.pooler.supabase.com"
GOOD = f"postgresql://postgres.{REF}:Xk92mQr4TzPw18Ld@{HOST}:5432/postgres"


def _levels(rows):
    return {label: level for level, label, _ in rows}


def _fails(rows):
    return {label for level, label, _ in rows if level == "FAIL"}


def _text(rows):
    return " ".join(f"{lvl} {lbl} {det}" for lvl, lbl, det in rows)


# ── the healthy case ─────────────────────────────────────────────────────────

def test_a_correct_url_reports_no_failures():
    rows = diagnose(GOOD)
    assert not _fails(rows), _text(rows)
    assert _levels(rows)["username"] == "OK"


# ── each failure mode is NAMED, not lumped together ──────────────────────────

def test_placeholder_is_named_as_a_placeholder():
    """The Connect modal does not fill the password in. Square brackets make
    urlsplit complain about IPv6, so this must be caught on the raw string."""
    rows = diagnose(f"postgresql://postgres.{REF}:[YOUR-PASSWORD]@{HOST}:5432/postgres")
    assert "password" in _fails(rows)
    assert "placeholder" in _text(rows).lower()
    assert "IPv6" not in _text(rows)


def test_unencoded_at_sign_is_named_as_an_encoding_problem():
    rows = diagnose(f"postgresql://postgres.{REF}:pa@ssw0rd@{HOST}:5432/postgres")
    assert "password encoding" in _fails(rows)
    assert "@" in _text(rows)


def test_specials_that_break_parsing_do_not_crash_the_tool():
    """A diagnostic that dies on the malformed input it exists to explain is
    not a diagnostic. urlsplit defers validation to .port, which raises."""
    rows = diagnose(f"postgresql://postgres.{REF}:p%ss#w0rd?x@{HOST}:5432/postgres")
    assert _fails(rows), "should report problems, not raise"
    assert "port" in _fails(rows)


def test_missing_password_field_is_named():
    rows = diagnose(f"postgresql://postgres.{REF}@{HOST}:5432/postgres")
    assert "password" in _fails(rows)
    assert "no password field" in _text(rows).lower()


def test_trailing_newline_is_named():
    rows = diagnose(GOOD + "\n")
    assert "whitespace" in _fails(rows)


def test_bare_postgres_on_a_pooler_host_is_named():
    rows = diagnose(f"postgresql://postgres:Xk92mQr4TzPw18Ld@{HOST}:5432/postgres")
    assert "username" in _fails(rows)
    assert "tenant" in _text(rows).lower()


def test_bare_postgres_on_a_DIRECT_host_is_fine():
    """The direct-connection string legitimately uses the bare role; only the
    pooler needs the tenant suffix. Flagging both would train the reader to
    ignore the check."""
    rows = diagnose(f"postgresql://postgres:Xk92mQr4TzPw18Ld@db.{REF}.supabase.co:5432/postgres")
    assert "username" not in _fails(rows)


def test_empty_url_is_named():
    assert "DATABASE_URL" in _fails(diagnose(""))


# ── the safety property ──────────────────────────────────────────────────────

@pytest.mark.parametrize("password,url_pw", [
    ("SuPerSecr3tCanary99", "SuPerSecr3tCanary99"),
    ("ab@cd#ef", "ab%40cd%23ef"),          # encoded: tool discusses its chars
    ("pa@ssw0rdCanary", "pa@ssw0rdCanary"),  # un-encoded: tool reports the bug
])
def test_the_password_is_never_printed(password, url_pw):
    rows = diagnose(f"postgresql://postgres.{REF}:{url_pw}@{HOST}:5432/postgres")
    assert password not in _text(rows)


def test_the_password_is_not_printed_even_when_it_is_the_reported_problem():
    """The encoding branch quotes the offending CHARACTERS back. It must quote
    the class, never the string -- this is the branch most likely to leak."""
    secret = "Canary@Secret"
    rows = diagnose(f"postgresql://postgres.{REF}:{secret}@{HOST}:5432/postgres")
    assert "password encoding" in _fails(rows)
    assert secret not in _text(rows)
    assert "Canary" not in _text(rows)

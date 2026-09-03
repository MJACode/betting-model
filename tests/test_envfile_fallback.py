"""A diagnostic that cannot see the config it diagnoses reports a lie.

scripts/db_url_doctor.py said "DATABASE_URL not set / empty" on a machine
where it was set in .env and where the very next command connected fine. It
read os.environ only, while every other entry point goes through config.py or
data/db.py, which load_dotenv() first.

These pin the fallback and, just as importantly, its ORDER.
"""

from __future__ import annotations

import os
import subprocess
import sys

from scripts._envfile import database_url, env_value, parse_env_file


def test_env_file_is_read_when_the_environment_is_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    envf = tmp_path / ".env"
    envf.write_text("DATABASE_URL=postgresql://u:p@h:5432/db\n", encoding="utf-8")
    assert database_url(envf) == "postgresql://u:p@h:5432/db"


def test_the_real_environment_wins_over_the_file(tmp_path, monkeypatch):
    """On the worker the variable IS the environment. A stale .env sitting
    beside it must never override the live value."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://live@host/db")
    envf = tmp_path / ".env"
    envf.write_text("DATABASE_URL=postgresql://stale@host/db\n", encoding="utf-8")
    assert database_url(envf) == "postgresql://live@host/db"


def test_a_missing_env_file_is_empty_not_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url(tmp_path / "nope.env") == ""


def test_parser_handles_what_a_real_env_carries(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text(
        "# a comment\n"
        "\n"
        "export ODDS_API_KEY=abc123\n"
        'QUOTED="dq-value"\n'
        "SINGLE='sq-value'\n"
        "  SPACED = spaced-value  \n",
        encoding="utf-8",
    )
    got = parse_env_file(envf)
    assert got["ODDS_API_KEY"] == "abc123"
    assert got["QUOTED"] == "dq-value"
    assert got["SINGLE"] == "sq-value"
    assert got["SPACED"] == "spaced-value"
    assert "# a comment" not in got


def test_a_value_containing_equals_survives(tmp_path, monkeypatch):
    """Base64 passwords end in '='. Splitting on every '=' would truncate one
    and produce the exact wrong-password error this tool exists to explain."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    envf = tmp_path / ".env"
    envf.write_text("DATABASE_URL=postgresql://u:aGVsbG8=@h:5432/db\n", encoding="utf-8")
    assert database_url(envf) == "postgresql://u:aGVsbG8=@h:5432/db"


def test_env_value_reads_other_keys_too(tmp_path, monkeypatch):
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    envf = tmp_path / ".env"
    envf.write_text("ODDS_API_KEY=k-123\n", encoding="utf-8")
    assert env_value("ODDS_API_KEY", envf) == "k-123"


def test_the_doctor_actually_uses_it(tmp_path):
    """End to end, through the CLI, with the URL ONLY in a file.

    Run as a subprocess with DATABASE_URL scrubbed from the environment, so
    this is the exact situation that produced the false "not set / empty":
    a local machine whose credential lives in .env. DOTENV_PATH points at a
    temp file so the developer's real .env is never read or written.
    """
    envf = tmp_path / ".env"
    envf.write_text(
        "DATABASE_URL=postgresql://postgres.abc:pw@aws-1-us-west-2."
        "pooler.supabase.com:5432/postgres\n",
        encoding="utf-8",
    )
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env["DOTENV_PATH"] = str(envf)
    out = subprocess.run(
        [sys.executable, "-m", "scripts.db_url_doctor"],
        capture_output=True, text=True, env=env,
    )
    assert "not set / empty" not in out.stdout, out.stdout
    assert "pooler.supabase.com" in out.stdout, out.stdout

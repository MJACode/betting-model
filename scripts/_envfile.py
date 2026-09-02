"""Read DATABASE_URL the way the rest of the repo does: env first, then .env.

WHY THIS EXISTS
---------------
2026-08-31: `python -m scripts.db_url_doctor --connect` reported

    FAIL  DATABASE_URL   not set / empty

on a machine where DATABASE_URL was set perfectly well, and where
`scripts.model_roi_report` connected on the very next line. The doctor read
`os.environ` only; every other entry point in the repo goes through config.py
or data/db.py, which call `load_dotenv()` first. So on the ONE machine these
tools were written for -- a local box with a .env, not the worker with real
environment variables -- the diagnostic was blind, and it said "not set" rather
than "I cannot see it", which reads as a finding.

That is CLAUDE.md's "a health check must not gate on the thing that breaks"
wearing a different hat: a diagnostic that cannot see the config it diagnoses
reports a healthy system as broken, which is just as expensive as the reverse.

Deliberately does NOT import python-dotenv. These scripts are meant to run
anywhere -- including a bare container mid-incident -- so the parser is 20
lines rather than a dependency.
"""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env into a dict. Missing file = empty dict, never an error.

    Handles what a real .env carries: `export` prefixes, comments, blank
    lines, and values wrapped in matching quotes. A value containing '=' (a
    base64 password, say) survives, because only the FIRST '=' splits.
    """
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def _default_env_path() -> Path:
    """Repo root .env, unless DOTENV_PATH names another one.

    The override exists so these scripts can be pointed at a candidate file
    during an incident ("does THIS one work?") without editing the real .env,
    and so the end-to-end test can exercise the fallback without touching the
    developer's own credentials.
    """
    override = os.environ.get("DOTENV_PATH", "").strip()
    return Path(override) if override else _ROOT / ".env"


def env_value(name: str, env_path: Path | None = None) -> str:
    """The real environment wins; .env is the fallback.

    That order matters: on the worker the variable IS the environment, and a
    stale .env committed alongside it must never override the live value.
    """
    from_environ = os.environ.get(name, "").strip()
    if from_environ:
        return from_environ
    return parse_env_file(env_path or _default_env_path()).get(name, "").strip()


def database_url(env_path: Path | None = None) -> str:
    return env_value("DATABASE_URL", env_path)

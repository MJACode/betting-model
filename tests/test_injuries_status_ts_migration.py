"""Worker migration: injuries.status_ts for the NFL prop veto clock."""
from __future__ import annotations

from pathlib import Path

MIG = (
    Path(__file__).parent.parent
    / "data/migrations/add_injuries_status_ts_2026_09_14.sql"
)
CODE = MIG.read_text(encoding="utf-8")


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_only_adds_status_ts_and_is_idempotent():
    assert "ADD COLUMN IF NOT EXISTS status_ts" in CODE
    assert "ALTER TABLE public.injuries" in CODE
    assert "DROP TABLE" not in CODE.upper()
    assert "picks" not in CODE.lower()
    assert "discord" not in CODE.lower()
    assert "push_sent" not in CODE.lower()

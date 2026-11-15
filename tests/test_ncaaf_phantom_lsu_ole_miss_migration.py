"""The worker migration that removes the minted LSU @ Ole Miss row.

Measured 2026-11-15: NCAAF_2026-11-21_lsu_ole-miss was created by the
2025-12-01 historical odds snapshot and has no picks and no odds.
NCAAF_2026-11-21_wofford_ole-miss is the CFBD schedule row. ESPN agrees
with Wofford. This file deletes only the phantom, and only while nothing
points at it.
"""
from __future__ import annotations

from pathlib import Path

MIG = (Path(__file__).parent.parent
       / "data/migrations/ncaaf_drop_phantom_lsu_ole_miss_2026_11_21.sql")
CODE = MIG.read_text(encoding="utf-8")

PHANTOM = "NCAAF_2026-11-21_lsu_ole-miss"
WOFFORD = "NCAAF_2026-11-21_wofford_ole-miss"


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_the_phantom_and_requires_the_schedule_row():
    assert PHANTOM in CODE
    assert WOFFORD in CODE
    assert "away_team = 'LSU'" in CODE
    assert "away_team = 'Wofford'" in CODE
    assert "data_source = 'live'" in CODE
    assert "home_score IS NULL" in CODE


def test_it_deletes_only_the_phantom():
    assert "DELETE FROM games" in CODE
    assert "WHERE game_id = phantom" in CODE
    assert WOFFORD not in CODE.split("DELETE FROM games")[1]
    assert "DELETE FROM picks" not in CODE
    assert "DELETE FROM odds" not in CODE


def test_a_child_row_blocks_the_delete():
    """A pick or an odds snapshot that appears before the worker runs must
    keep its games row. Re-pointing LSU prices onto Wofford would price the
    wrong game. The pass then returns without deleting."""
    assert "SELECT count(*) FROM %I WHERE game_id = $1" in CODE
    assert "information_schema.columns" in CODE
    assert "column_name = 'game_id'" in CODE
    assert "'picks'" in CODE
    assert "'odds'" in CODE
    delete_at = CODE.index("DELETE FROM games")
    guard_at = CODE.index("IF n > 0 THEN")
    assert guard_at < delete_at
    assert "RETURN;" in CODE[guard_at:delete_at]

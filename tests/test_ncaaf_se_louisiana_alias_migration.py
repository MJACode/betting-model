"""
The one-off that consolidates the UL Monroe 2026-09-19 SE Louisiana split.

Measured 2026-09-14: two games rows, same commence_time, 0 odds / 0 picks on
both, identical weather. Canonical is the CFBD id. The worker applies this
from view_migrations because the Supabase connector available to sessions
is read-only.
"""
from __future__ import annotations

from pathlib import Path

MIG = (Path(__file__).parent.parent
       / "data/migrations/ncaaf_se_louisiana_ul_monroe_alias_2026_09_14.sql")
CODE = MIG.read_text(encoding="utf-8")

CANON = "NCAAF_2026-09-19_se-louisiana_ul-monroe"
ALIAS = "NCAAF_2026-09-19_southeastern-louisiana-lions_ul-monroe"


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript; a second top-level
    statement would be shredded at its semicolons."""
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_the_measured_pair_and_keeps_the_cfbd_id():
    assert f"'{CANON}'" in CODE
    assert f"'{ALIAS}'" in CODE
    assert "away_team = 'SE Louisiana'" in CODE
    assert "away_team = 'Southeastern Louisiana Lions'" in CODE
    assert "home_team = 'UL Monroe'" in CODE


def test_it_deletes_the_alias_games_row_and_never_the_canonical():
    assert "DELETE FROM games" in CODE
    assert "WHERE game_id = alias" in CODE
    assert "DELETE FROM games\n     WHERE game_id = canon" not in CODE


def test_a_pick_is_never_deleted_and_never_regraded():
    """CLAUDE.md 1c: consolidate by moving game_id, never by dropping the row
    or stamping a result. If a unique collision leaves a pick on the alias,
    the games delete is refused."""
    assert "DELETE FROM picks" not in CODE
    assert "SET result" not in CODE
    assert "leftover odds/picks on alias, games row kept" in CODE
    assert "UPDATE picks SET game_id = canon WHERE game_id = alias" in CODE


def test_it_guards_on_both_names_and_both_still_unscored():
    """A second pass is a no-op: either row renamed, scored, or already
    deleted and the IF NOT EXISTS at the top returns."""
    assert "AND home_score IS NULL" in CODE
    assert CODE.count("AND home_score IS NULL") >= 3  # both exists-guards + the delete


def test_odds_move_only_when_canonical_has_none():
    """Do not pile a second snapshot stream onto an id that already has one."""
    assert "IF NOT EXISTS (SELECT 1 FROM odds WHERE game_id = canon)" in CODE
    assert "UPDATE odds SET game_id = canon WHERE game_id = alias" in CODE

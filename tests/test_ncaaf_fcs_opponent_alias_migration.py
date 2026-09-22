"""
The one-off that deletes three empty NCAAF live-duplicate rows on 2026-09-26.

Measured 2026-09-22: each pair shares a home team and a kickoff. The live
row (created 05:49–05:59Z) has 0 odds and 0 picks. Canonical is the CFBD
id. The worker applies this from view_migrations because the Supabase
connector available to sessions is read-only.
"""
from __future__ import annotations

from pathlib import Path

MIG = (Path(__file__).parent.parent
       / "data/migrations/ncaaf_fcs_opponent_alias_2026_09_22.sql")
CODE = MIG.read_text(encoding="utf-8")

PAIRS = (
    ("NCAAF_2026-09-26_william-mary_duke",
     "NCAAF_2026-09-26_william-and-mary-tribe_duke",
     "Duke", "William & Mary", "William and Mary Tribe"),
    ("NCAAF_2026-09-26_long-island-university_florida-international",
     "NCAAF_2026-09-26_liu-sharks_florida-international",
     "Florida International", "Long Island University", "LIU Sharks"),
    ("NCAAF_2026-09-26_houston-christian_north-texas",
     "NCAAF_2026-09-26_houston-baptist-huskies_north-texas",
     "North Texas", "Houston Christian", "Houston Baptist Huskies"),
)


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript; a second top-level
    statement would be shredded at its semicolons."""
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_the_three_measured_pairs_and_keeps_the_cfbd_ids():
    for canon, alias, home, away_canon, away_alias in PAIRS:
        assert f"'{canon}'" in CODE
        assert f"'{alias}'" in CODE
        assert f"'{home}'" in CODE
        assert f"'{away_canon}'" in CODE
        assert f"'{away_alias}'" in CODE


def test_it_deletes_the_alias_games_row_and_never_the_canonical():
    assert "DELETE FROM games" in CODE
    assert "WHERE game_id = rec.alias" in CODE
    assert "DELETE FROM games\n         WHERE game_id = rec.canon" not in CODE


def test_a_pick_is_never_deleted_and_never_regraded():
    """CLAUDE.md 1c: consolidate by moving game_id, never by dropping the row
    or stamping a result. If a unique collision leaves a pick on the alias,
    the games delete is refused."""
    assert "DELETE FROM picks" not in CODE
    assert "SET result" not in CODE
    assert "leftover odds/picks on %, games row kept" in CODE
    assert "UPDATE picks SET game_id = rec.canon WHERE game_id = rec.alias" in CODE


def test_it_guards_on_both_names_and_both_still_unscored():
    """A second pass is a no-op: either row renamed, scored, or already
    deleted and the EXISTS guard continues to the next pair."""
    assert "AND home_score IS NULL" in CODE
    assert CODE.count("AND home_score IS NULL") >= 3
    assert "CONTINUE;" in CODE


def test_odds_move_only_when_canonical_has_none():
    assert "IF NOT EXISTS (SELECT 1 FROM odds WHERE game_id = rec.canon)" in CODE
    assert "UPDATE odds SET game_id = rec.canon WHERE game_id = rec.alias" in CODE

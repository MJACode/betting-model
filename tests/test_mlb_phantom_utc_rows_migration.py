"""
The one-off that relabels the three April phantom MLB rows.

mike, 2026-09-07: "clean up the three phantom rows". They are the previous
night's game filed again under its UTC date (session 253). Five voided picks
point at two of them, so the rows stay; they are relabelled, not deleted, and
not scored.
"""
from __future__ import annotations

from pathlib import Path

MIG = Path(__file__).parent.parent / "data/migrations/mlb_phantom_utc_rows_2026_09_07.sql"
CODE = MIG.read_text(encoding="utf-8")

PHANTOMS = ("MLB_2026-04-16_NYM_LAD", "MLB_2026-04-17_SEA_SD", "MLB_2026-04-17_COL_HOU")


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_exactly_the_three_rows():
    for gid in PHANTOMS:
        assert f"'{gid}'" in CODE
    assert CODE.count("'MLB_2026-") == 3


def test_it_relabels_and_never_deletes_or_scores():
    assert "SET data_source = 'duplicate_utc'" in CODE
    assert "DELETE FROM" not in CODE
    assert "SET home_score" not in CODE and "home_score =" not in CODE


def test_it_guards_on_its_own_property():
    assert "AND data_source = 'live'" in CODE
    assert "AND home_score IS NULL" in CODE
    assert "AND commence_time IS NULL" in CODE


def test_the_declared_void_covers_the_four_avoids_on_those_rows():
    import json
    import config
    entries = json.loads((config.ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    job = next(e for e in entries if e["key"] == "void-phantom-utc-avoids-2026-04-16-17")
    assert job["job_type"] == "void_picks"
    assert sorted(job["args"]["pick_ids"]) == [660, 662, 704, 705]
    assert "after the game" in job["args"]["reason"]

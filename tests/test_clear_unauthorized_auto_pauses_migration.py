"""
The one-off that deletes the unauthorized 2026-09-11 auto-pause rows.

mike, 2026-09-14: nothing autopauses. Measured against production the same
day: model_auto_pauses held exactly mlb_prop_batter_runs and
mlb_prop_pitcher_k (COUNT(*) = 2). The worker ACTIVE_MIGRATIONS pass
clears the table. The review still reports; it never writes pauses.
"""
from __future__ import annotations

from pathlib import Path

MIG = (
    Path(__file__).parent.parent
    / "data/migrations/clear_unauthorized_auto_pauses_2026_09_14.sql"
)
CODE = MIG.read_text(encoding="utf-8")

UNAUTHORIZED = ("mlb_prop_batter_runs", "mlb_prop_pitcher_k")


def _stmts() -> str:
    return " ".join(
        ln for ln in CODE.splitlines() if not ln.strip().startswith("--")
    )


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript; a second top-level
    statement would be shredded at its semicolons."""
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_the_two_measured_unauthorized_rows():
    for mid in UNAUTHORIZED:
        assert mid in CODE
    assert "COUNT(*) = 2" in CODE or "only rows" in CODE.lower()


def test_it_clears_the_whole_auto_pause_table():
    """Those two were the only rows. A WHERE that named only them would leave
    a third unauthorized pause in place; the policy is nothing autopauses."""
    stmts = _stmts()
    assert "DELETE FROM model_auto_pauses" in stmts
    assert "DELETE FROM picks" not in stmts
    assert "INSERT INTO model_auto_pauses" not in stmts
    assert "UPDATE model_auto_pauses" not in stmts


def test_it_no_ops_when_the_table_is_missing_or_already_empty():
    stmts = _stmts()
    assert "to_regclass('public.model_auto_pauses')" in stmts
    assert "GET DIAGNOSTICS" in stmts


def test_the_two_models_are_not_moved_into_paused_models():
    """Unpausing by listing them in PAUSED_MODELS would be the opposite of
    the policy. They go live when the table is empty, not by joining the
    deliberate-pause set."""
    import config
    for mid in UNAUTHORIZED:
        assert mid not in config.PAUSED_MODELS


def test_it_does_not_touch_picks_thresholds_or_the_review_ledger():
    stmts = _stmts()
    assert "DELETE FROM picks" not in stmts
    assert "UPDATE picks" not in stmts
    assert "threshold_reviews" not in stmts
    assert "PAUSED_MODELS" not in stmts
    assert "ACTION_THRESHOLDS" not in stmts
    assert "model_action_thresholds" not in stmts

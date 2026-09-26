"""The 2026-09-19 Platt map on ncaaf_over_under comes out of the decision path.

Michael Alksninis, 2026-09-26 ET: demote that map so the over arm is decided
again at the validated +8 gate on the raw probability (~0.650). The worker
ACTIVE_MIGRATIONS pass applies the SQL. A later, different promotion is not
cleared. The ±8 gate, the 0.65 floor, and PAUSED_MODELS are not in the file.
"""
from __future__ import annotations

from pathlib import Path

MIG = (
    Path(__file__).parent.parent
    / "data/migrations/demote_ncaaf_over_under_platt_2026_09_26.sql"
)
CODE = MIG.read_text(encoding="utf-8")


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


def test_it_demotes_only_the_measured_promotion():
    sql = _stmts()
    assert "model_id = 'ncaaf_over_under'" in sql
    assert "promoted = FALSE" in sql
    assert "promoted_a = NULL" in sql
    assert "promoted_b = NULL" in sql
    assert "promoted_method = NULL" in sql
    assert "promoted_helps = NULL" in sql
    assert "promoted_transfers = NULL" in sql
    assert "promoted_at = '2026-09-19T17:45:14.751731-04:00'" in sql
    assert "promoted_b = -0.281555" in sql
    assert "promoted_a = 1.0" in sql
    assert sql.count("model_id") == 1


def test_it_does_not_move_the_gate_the_floor_or_a_pause():
    sql = _stmts().lower()
    assert "paused_models" not in sql
    assert "d_threshold" not in sql
    assert "model_prob_thresholds" not in sql
    assert "update picks" not in sql
    assert "delete from" not in sql

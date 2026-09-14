"""
The one-off that deletes leftover nfl_wind_totals opening_signals rows
whose picks were VOIDED/DELETED after MAX_FIRE_LEAD, keeping DEN@KC.

mike, 2026-09-14: the old wind picks should be deleted; keep the posted
DEN@KC Under 43.5 (pick_id 1969489). Capture leftovers stayed because
ON CONFLICT DO NOTHING. The worker ACTIVE_MIGRATIONS pass applies this;
the session MCP is read-only. No Discord re-announce.
"""
from __future__ import annotations

from pathlib import Path

MIG = (
    Path(__file__).parent.parent
    / "data/migrations/drop_voided_nfl_wind_opening_signals_2026_09_14.sql"
)
CODE = MIG.read_text(encoding="utf-8")

LEFTOVERS = (
    "NFL_2026_01_BUF_HOU",
    "NFL_2026_01_CLE_JAX",
    "NFL_2026_01_BAL_IND",
    "NFL_2026_01_NYJ_TEN",
    "NFL_2026_01_DAL_NYG",
    "NFL_2026_01_TB_CIN",
)
KEEP = "NFL_2026_01_DEN_KC:nfl_wind_totals"


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript; a second top-level
    statement would be shredded at its semicolons."""
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_the_six_measured_week1_leftovers():
    for gid in LEFTOVERS:
        assert gid in CODE
    assert "NFL_2026_01_BUF_HOU:nfl_wind_totals" in CODE


def test_it_pins_den_kc_and_the_standing_pick_id():
    assert f"os.lock_key <> '{KEEP}'" in CODE
    assert "1969489" in CODE


def test_it_deletes_only_wind_captures_without_a_standing_bet():
    assert "DELETE FROM opening_signals" in CODE
    assert "os.model_id = 'nfl_wind_totals'" in CODE
    assert "p.signal_type = 'BET'" in CODE
    assert "COALESCE(p.condition_status, '') <> 'VOID'" in CODE
    assert "NOT EXISTS" in CODE


def test_it_does_not_touch_picks_or_discord():
    """Statements only — the header may mention Discord to say we do not."""
    stmts = " ".join(
        ln for ln in CODE.splitlines() if not ln.strip().startswith("--")
    )
    assert "DELETE FROM picks" not in stmts
    assert "UPDATE picks" not in stmts
    assert "push_sent" not in stmts
    assert "discord" not in stmts.lower()

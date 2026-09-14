"""
The one-off that deletes leftover nfl_prop_market opening_signals rows
whose picks were deleted after the 24h lead ceiling.

mike, 2026-09-14: sweep the three leftovers the same way as the wind
cleanup. Capture stayed because ON CONFLICT DO NOTHING. Match on the
synthesised lock_key, not game_id+model_id, so a standing BET on the
same game cannot hide a leftover. The worker ACTIVE_MIGRATIONS pass
applies this; the session MCP is read-only. No Discord re-announce.
"""
from __future__ import annotations

from pathlib import Path

MIG = (
    Path(__file__).parent.parent
    / "data/migrations/drop_voided_nfl_prop_market_opening_signals_2026_09_14.sql"
)
CODE = MIG.read_text(encoding="utf-8")

LEFTOVERS = (
    "NFL_2026_01_TB_CIN:nfl_prop_market:joeburrow:player_pass_completions",
    "NFL_2026_01_NO_DET:nfl_prop_market:tylershough:player_pass_attempts",
    "NFL_2026_01_DEN_KC:nfl_prop_market:bonix:player_pass_tds",
)


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript; a second top-level
    statement would be shredded at its semicolons."""
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_names_the_three_measured_leftovers():
    for key in LEFTOVERS:
        assert key in CODE


def test_the_delete_is_the_class_not_a_hardcoded_key_list():
    """Comments name the three measured rows; the statement guards on the
    property (no standing pick), the same shape as the wind sweep."""
    stmts = " ".join(
        ln for ln in CODE.splitlines() if not ln.strip().startswith("--")
    )
    for key in LEFTOVERS:
        assert key not in stmts
    assert "os.model_id = 'nfl_prop_market'" in stmts
    assert "NOT EXISTS" in stmts
    assert "p.signal_type = 'BET'" in stmts
    assert "COALESCE(p.condition_status, '') <> 'VOID'" in stmts


def test_it_matches_the_publish_lock_key_not_game_plus_model():
    """nfl_prop_market writes player_key + prop_market and leaves player_id
    NULL. game_id+model_id would keep a leftover whenever any other prop on
    that game still has a standing BET (DEN@KC has both Nix leftover and
    other market captures)."""
    from tracking.publish_keys import lock_key_sql
    expr = " ".join(lock_key_sql("p").split())
    body = " ".join(CODE.split())
    assert expr in body
    stmts = " ".join(
        ln for ln in CODE.splitlines() if not ln.strip().startswith("--")
    )
    assert "p.game_id = os.game_id" not in stmts


def test_it_does_not_touch_picks_or_discord():
    """Statements only — the header may mention Discord to say we do not."""
    stmts = " ".join(
        ln for ln in CODE.splitlines() if not ln.strip().startswith("--")
    )
    assert "DELETE FROM picks" not in stmts
    assert "UPDATE picks" not in stmts
    assert "push_sent" not in stmts
    assert "discord" not in stmts.lower()

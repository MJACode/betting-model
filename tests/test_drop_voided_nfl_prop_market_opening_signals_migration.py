"""
The one-off that deletes leftover nfl_prop_market opening_signals rows
whose picks were deleted after the 24h lead ceiling.

mike, 2026-09-14: sweep the three leftovers. A naive
game_id+model_id+player_id join is WRONG — this model leaves player_id
NULL and identifies via player_key + prop_market. Delete by exact
lock_key list, and skip a key only when lock_key_sql finds a standing
non-VOID BET. No Discord re-announce.
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


def test_it_deletes_exactly_the_three_measured_lock_keys():
    stmts = _stmts()
    assert "os.lock_key IN" in stmts
    for key in LEFTOVERS:
        assert f"'{key}'" in stmts
    assert stmts.count("nfl_prop_market:") == 3


def test_standing_pick_uses_lock_key_sql_not_player_id():
    """nfl_prop_market writes player_key + prop_market and leaves player_id
    NULL. game_id+model_id+COALESCE(player_id,'') matched 3/2/2 standing
    props on these leftovers (DEN@KC/NO@DET/TB@CIN) while lock_key_sql
    matched 0 — that join would have refused the delete."""
    from tracking.publish_keys import KEY_PARTS, lock_key_sql
    assert KEY_PARTS == ("player_id", "player_key", "prop_market")
    expr = " ".join(lock_key_sql("p").split())
    body = " ".join(CODE.split())
    assert expr in body
    stmts = _stmts()
    assert "p.player_key" in stmts and "p.prop_market" in stmts
    assert "os.player_id" not in stmts
    assert "p.game_id = os.game_id" not in stmts
    assert "COALESCE(p.player_id, '')" not in stmts
    assert "COALESCE(p.player_id::text, '')" not in stmts


def test_it_still_skips_a_key_that_has_a_standing_bet():
    stmts = _stmts()
    assert "NOT EXISTS" in stmts
    assert "p.signal_type = 'BET'" in stmts
    assert "COALESCE(p.condition_status, '') <> 'VOID'" in stmts


def test_it_does_not_touch_picks_or_discord():
    """Statements only — the header may mention Discord to say we do not."""
    stmts = _stmts()
    assert "DELETE FROM picks" not in stmts
    assert "UPDATE picks" not in stmts
    assert "push_sent" not in stmts
    assert "discord" not in stmts.lower()

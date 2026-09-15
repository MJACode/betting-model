"""Worker migration: game_market_gate log for the MLB game overlay."""
from __future__ import annotations

from pathlib import Path

MIG = (
    Path(__file__).parent.parent
    / "data/migrations/add_game_market_gate_2026_09_15.sql"
)
CODE = MIG.read_text(encoding="utf-8")


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_it_only_creates_the_log_and_does_not_touch_picks():
    assert "CREATE TABLE public.game_market_gate" in CODE
    assert "PRIMARY KEY (game_id, model_id, pick_side)" in CODE
    assert "DROP TABLE" not in CODE.upper()
    assert "ALTER TABLE public.picks" not in CODE
    assert "ALTER TABLE public.picks_log" not in CODE
    assert "discord_signal" not in CODE
    assert "push_sent" not in CODE
    assert "closing_dk_odds" not in CODE
    assert "clv_pct" not in CODE

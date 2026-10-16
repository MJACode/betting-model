"""NHL Stats-tab reads: one worker migration, anon grants, no record rewrite.

The views are ahead of the screen. mobile/src does not query them yet, so
they sit on AHEAD_OF_THE_APP in tests/test_anon_readable.py rather than
being left as an unexplained grant. The migration is not applied from a
development session; ACTIVE_MIGRATIONS is what runs it, after the CLV stamp,
and the file does not mention the published-record views.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "add_nhl_stats_views_2026_10_16.sql"
NAME = MIG.name


def _sql() -> str:
    return MIG.read_text(encoding="utf-8")


def test_the_migration_is_one_statement_and_returns_once_applied():
    text = _sql()
    assert text.count("DO $mig$") == 1
    assert text.strip().endswith(";")
    assert "RAISE NOTICE 'nhl stats views already present" in text
    assert "RETURN;" in text
    assert "v_public_track_record" not in text
    for name in (
        "v_player_season_totals_nhl",
        "v_team_season_totals_nhl",
        "v_nhl_player_prop_odds",
        "player_stat_values_nhl",
        "anon read nhl_skater_game_log",
        "anon read nhl_goalie_game_log",
        "anon read nhl_team_game_log",
    ):
        assert name in text, name
    assert "security_invoker = on" in text
    assert "game_type = 2" in text
    assert "FORCE ROW LEVEL SECURITY" not in text.upper()


def test_the_stat_list_is_the_board_and_the_arrays_are_windows():
    text = _sql()
    for stat in ("points", "goals", "assists", "shots", "hits", "blocks", "pp_points", "toi"):
        assert f"WHEN '{stat}'" in text, stat
    for stat in ("saves", "save_pct", "gaa"):
        assert f"WHEN '{stat}'" in text, stat
    assert 'FILTER (WHERE r.val IS NOT NULL)' in text
    assert "p_window IS NULL OR (p_window > 0 AND r.rn <= p_window)" in text
    assert "3600.0" in text
    assert "/ 60.0" in text


def test_the_prop_quote_is_pre_game_and_refuses_an_ambiguous_player():
    text = _sql()
    assert "sport = 'NHL'" in text
    assert "snapshot_type <> 'in_play'" in text
    assert "snapshot_at::timestamptz <= g.commence_time::timestamptz" in text
    assert "WHEN ids.n = 1 THEN ids.player_id ELSE NULL" in text


def test_it_is_registered_after_the_clv_stamp_and_declared_for_anon():
    from data.anon_readable import (
        ANON_READABLE,
        RPC_ANON_CALLABLE,
        VIEW_BASE_TABLES,
    )
    from data.view_migrations import ACTIVE_MIGRATIONS
    from tests.test_anon_readable import AHEAD_OF_THE_APP

    clv = "clv_standard_v2_2026_10_14.sql"
    assert ACTIVE_MIGRATIONS[-1] == NAME
    assert ACTIVE_MIGRATIONS.index(clv) < ACTIVE_MIGRATIONS.index(NAME)
    for view in (
        "v_player_season_totals_nhl",
        "v_team_season_totals_nhl",
        "v_nhl_player_prop_odds",
    ):
        assert view in ANON_READABLE
        assert view in AHEAD_OF_THE_APP
    for table in ("nhl_skater_game_log", "nhl_goalie_game_log", "nhl_team_game_log"):
        assert table in VIEW_BASE_TABLES
        assert table not in ANON_READABLE
    assert "player_stat_values_nhl" in RPC_ANON_CALLABLE


def test_no_scorer_or_card_reads_the_new_names():
    """A stats view that a scorer started reading would be a BET path."""
    needles = (
        "v_player_season_totals_nhl",
        "v_team_season_totals_nhl",
        "v_nhl_player_prop_odds",
        "player_stat_values_nhl",
    )
    roots = [ROOT / "models", ROOT / "scripts", ROOT / "tracking", ROOT / "nfl"]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in needles:
                assert needle not in text, f"{path} reads {needle}"

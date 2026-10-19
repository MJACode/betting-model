"""NHL skater chips on the Stats tab.

Shots, Points, Goals and Assists, priced from the markets the board already
reads. Season and window totals come from player_window_totals_nhl, which
reads nhl_skater_game_log (column shots, season = the ending year). Hit
rate stays off. The log's anon SELECT is #962 and is not granted here.
The behavioural pins live in `mobile/scripts/verify_nhl_skater_stats.ts`;
this file runs it when the mobile toolchain is installed and pins the
source-level shape either way.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
MIG = ROOT / "data" / "migrations" / "add_nhl_skater_window_totals_2026_10_17.sql"

from tests._node import tsx_cmd  # noqa: E402


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def test_nhl_skater_chips_and_the_read_are_in_source():
    catalog = _read(MOBILE / "src/lib/statCatalog.ts")
    queries = _read(MOBILE / "src/lib/queries.ts")
    screen = _read(MOBILE / "src/screens/StatsScreen.tsx")
    assert "key: 'shots', label: 'Shots', sport: 'NHL'" in catalog
    assert "key: 'points', label: 'Points', sport: 'NHL'" in catalog
    assert "key: 'goals', label: 'Goals', sport: 'NHL'" in catalog
    assert "key: 'assists', label: 'Assists', sport: 'NHL'" in catalog
    assert "'NHL:shots': 'player_shots_on_goal'" in catalog
    assert "'NHL:points': 'player_points'" in catalog
    assert "'NHL:goals': 'player_goal_scorer_anytime'" in catalog
    assert "'NHL:assists': 'player_assists'" in catalog
    assert "NHL: ['NHL']" in catalog
    # Hit rate stays on the five sports that already have a per-game grant.
    assert "new Set<Sport>(['MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF'])" in catalog
    assert "const fn = 'player_window_totals_nhl'" in queries
    assert ".from('nhl_skater_stats')" not in queries
    assert ".from('nhl_skater_game_log')" not in queries
    assert "v_player_season_totals_nhl" not in queries
    assert "createNhlSkaterReader" not in queries
    markets = _read(MOBILE / "src/lib/markets.ts")
    assert "if (market === 'player_goal_scorer_anytime') return 'Anytime Goal';" in markets
    assert "if (sport === 'NHL') setHitMode('atLeast')" in screen
    assert "rankedBoardChrome(" in screen
    bet = screen.index("const betLabel = propDisplayLabel")
    section = screen.index("const lineOnlySection")
    assert 0 < bet < section
    assert "Season totals aren" not in screen
    board = _read(MOBILE / "src/lib/statsBoard.ts")
    assert "sport === 'NHL' && lineOnlyCount > 0" in board
    teams = screen.index("if (boardMode === 'teams' && supportsTeamBoard(sport))")
    # The load callback also has `if (!stat)`. The render guard is the one
    # that used to replace the NHL player board with the Teams-only empty state.
    no_stat = screen.index("NHL is not this")
    assert 0 < teams < no_stat


def test_the_function_is_on_the_anon_manifest_and_the_empty_table_is_not():
    src = _read(ROOT / "data/anon_readable.py")
    assert '"player_window_totals_nhl"' in src
    assert '"nhl_skater_stats"' not in src


def test_the_window_function_reads_the_game_log_and_does_not_grant_it():
    sql = _read(MIG)
    assert "FROM public.nhl_skater_game_log" in sql
    assert "COALESCE(SUM(shots), 0)" in sql
    assert "game_type = 2" in sql
    assert "ENDING year" in sql
    assert "GRANT EXECUTE ON FUNCTION public.player_window_totals_nhl" in sql
    assert "GRANT SELECT" not in sql
    assert "v_public_track_record" not in sql
    assert "42501" in sql and "PGRST202" in sql and "42883" in sql
    assert "returns no rows" not in sql
    board = _read(MOBILE / "src/lib/nhlBoard.ts")
    assert "NHL_SKATER_READ_MISSING = new Set(['42501', 'PGRST202', '42883'])" in board
    queries = _read(MOBILE / "src/lib/queries.ts")
    assert "if (nhlSkaterReadMissing(e)) return [];" in queries
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS
    clv = "clv_standard_v2_2026_10_14.sql"
    assert ACTIVE_MIGRATIONS.index(clv) < ACTIVE_MIGRATIONS.index(MIG.name)


@pytest.mark.skipif(
    tsx_cmd(MOBILE) is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_nhl_skater_stats.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

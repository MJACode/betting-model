"""NHL skater chips on the Stats tab.

Shots, Points, Goals and Assists, priced from the markets the board already
reads, summed from nhl_skater_stats. Hit rate stays off: that needs the
game-log grants, which are not applied. The behavioural pins live in
`mobile/scripts/verify_nhl_skater_stats.ts`; this file runs it when the
mobile toolchain is installed and pins the source-level shape either way.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"

from tests._node import tsx_cmd  # noqa: E402


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def test_nhl_skater_chips_and_the_read_are_in_source():
    catalog = _read(MOBILE / "src/lib/statCatalog.ts")
    queries = _read(MOBILE / "src/lib/queries.ts")
    screen = _read(MOBILE / "src/screens/StatsScreen.tsx")
    assert "key: 'shots_on_goal', label: 'Shots', sport: 'NHL'" in catalog
    assert "key: 'points', label: 'Points', sport: 'NHL'" in catalog
    assert "key: 'goals', label: 'Goals', sport: 'NHL'" in catalog
    assert "key: 'assists', label: 'Assists', sport: 'NHL'" in catalog
    assert "'NHL:shots_on_goal': 'player_shots_on_goal'" in catalog
    assert "'NHL:points': 'player_points'" in catalog
    assert "'NHL:goals': 'player_goal_scorer_anytime'" in catalog
    assert "'NHL:assists': 'player_assists'" in catalog
    assert "NHL: ['NHL']" in catalog
    # Hit rate stays on the five sports that already have a per-game grant.
    assert "new Set<Sport>(['MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF'])" in catalog
    assert ".from('nhl_skater_stats')" in queries
    assert "nhl_skater_game_log" not in queries
    assert "v_player_season_totals_nhl" not in queries
    markets = _read(MOBILE / "src/lib/markets.ts")
    assert "if (market === 'player_goal_scorer_anytime') return 'Anytime Goal';" in markets
    assert "if (sport === 'NHL') setHitMode('atLeast')" in screen
    assert "rankedBoardChrome(" in screen
    assert "createNhlSkaterReader" in queries
    board = _read(MOBILE / "src/lib/statsBoard.ts")
    assert "sport === 'NHL' && lineOnlyCount > 0" in board
    assert "Lines are up. Season totals aren\u2019t in yet." in screen
    teams = screen.index("if (boardMode === 'teams' && supportsTeamBoard(sport))")
    # The load callback also has `if (!stat)`. The render guard is the one
    # that used to replace the NHL player board with the Teams-only empty state.
    no_stat = screen.index("NHL is not this")
    assert 0 < teams < no_stat


def test_the_relation_is_on_the_anon_manifest():
    src = _read(ROOT / "data/anon_readable.py")
    assert '"nhl_skater_stats"' in src


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

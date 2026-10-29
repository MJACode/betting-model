"""Picks Scoreboard segment: DK game markets, stored live scores only.

Matt approved the boards on 2026-10-28. The behavioural pins live in
`mobile/scripts/verify_scoreboard.ts`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
PICKS = MOBILE / "src" / "screens" / "PicksHomeScreen.tsx"
QUERIES = MOBILE / "src" / "lib" / "queries.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_scoreboard_reads_name_the_relation_at_from():
    src = _read(QUERIES)
    games = src[src.index("export async function fetchScoreboardGames") : src.index("export async function fetchScoreboardDkOdds")]
    assert ".from('games')" in games
    assert "SCOREBOARD_SPORTS" in games
    assert "fetchAllPages" in games
    odds = src[src.index("export async function fetchScoreboardDkOdds") : src.index("export async function fetchNcaafScoreboard")]
    assert ".from('v_latest_dk_odds')" in odds
    assert "SCOREBOARD_MARKETS" in odds
    assert "fetchScoreboardDkOddsForGame" in odds
    assert ".eq('game_id', gameId)" in odds
    ncaaf = src[src.index("export async function fetchNcaafScoreboard") : src.index("export async function fetchDkInplayForGames")]
    assert ".from('v_ncaaf_scoreboard_latest')" in ncaaf
    assert ".in('game_id'" in ncaaf
    assert ".in('game_date'" not in ncaaf
    live = src[src.index("export async function fetchDkInplayForGames") : src.index("export async function fetchNextScoreboardGame")]
    assert "v_latest_inplay_odds_all_books" not in live
    assert "draftkings" in live
    assert "in_play" in live
    assert ".limit(1," in live
    assert ".limit(12)" not in live
    assert "fetchDkInplayForGame(" not in src.replace("fetchDkInplayForGames(", "")


def test_scoreboard_poll_is_one_game_and_stops_when_hidden():
    sheet = _read(MOBILE / "src" / "screens" / "ScoreboardGameScreen.tsx")
    hook = _read(MOBILE / "src" / "hooks" / "useScoreboard.ts")
    assert "useFocusEffect" in sheet
    assert "fetchScoreboardDkOdds([" not in sheet
    assert "fetchScoreboardDkOddsForGame" in sheet
    assert "fetchLiveGameStates(" not in sheet
    assert "fetchLiveGameStateById" in sheet
    assert "fetchNcaafScoreboard([gameId])" in sheet
    assert "fetchDkInplayForGames" in sheet
    assert "fetchDkInplayForGames" in hook
    assert "fetchNcaafScoreboard(ncaafIds)" in hook
    assert "fetchDkInplayForGame(" not in hook.replace("fetchDkInplayForGames(", "")


def test_ncaaf_scoreboard_index_is_hand_applied():
    # Read the list as text. Importing data.view_migrations pulls loguru,
    # which the scoreboard pin does not need.
    migrations = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    name = "ncaaf_scoreboard_game_index_2026_10_28.sql"
    assert name not in migrations
    sql = (ROOT / "data" / "migrations" / name).read_text(encoding="utf-8")
    assert "CREATE INDEX IF NOT EXISTS ncaaf_live_states_scoreboard_idx" in sql
    assert "(game_id, seen_at DESC, state_id DESC)" in sql
    assert "CREATE OR REPLACE VIEW" not in sql


def test_the_ncaaf_view_is_declared_and_not_last():
    from data.anon_readable import ANON_READABLE, VIEW_BASE_TABLES

    migrations = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    assert "v_ncaaf_scoreboard_latest" in ANON_READABLE
    assert "ncaaf_live_states" in VIEW_BASE_TABLES
    assert "ncaaf_live_states" not in ANON_READABLE
    added = migrations.index("add_ncaaf_scoreboard_latest_2026_10_28.sql")
    last = migrations.rindex("published_record_units_2026_10_16.sql")
    assert added < last


def test_scoreboard_is_on_the_pr_ci_subset():
    yml = _read(ROOT / ".github" / "workflows" / "pr-ci.yml")
    assert "tests/test_mobile_scoreboard.py" in yml


def test_picks_keeps_live_signals_separate():
    src = _read(PICKS)
    assert 'label="Live Signals"' in src
    assert 'label="Scoreboard"' in src
    assert "ScoreboardGame" in src


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_scoreboard_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_scoreboard.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

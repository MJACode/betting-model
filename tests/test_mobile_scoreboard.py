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
    ncaaf = src[src.index("export async function fetchNcaafScoreboard") : src.index("export async function fetchDkInplayForGame")]
    assert ".from('v_ncaaf_scoreboard_latest')" in ncaaf
    live = src[src.index("export async function fetchDkInplayForGame") : src.index("export async function fetchNextScoreboardGame")]
    assert ".from('odds')" in live
    assert "draftkings" in live
    assert "in_play" in live


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

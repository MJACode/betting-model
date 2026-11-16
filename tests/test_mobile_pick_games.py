"""A pick whose game row moved to another date still gets its game on the board.

2026-11-15: "Utah ML" (pick 4498275) drew as a bare "ML" with no matchup. Its
game was postponed and the ESPN ingest moved the games row to 2026-12-05, so
the Picks board's by-date games read no longer returned it. The boards now ask
for the games their picks name that the date read missed
(mobile/src/lib/pickGames.ts). The behaviour is checked by
mobile/scripts/verify_pick_games.ts; this file runs it.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MOBILE = ROOT / "mobile"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_the_by_id_read_names_games_literally():
    """tests/test_anon_readable.py parses literal relation names; the extra
    read must name `games` at its .from(...), not through a variable."""
    src = _read(MOBILE / "src" / "lib" / "queries.ts")
    assert "supabase.from('games').select(GAME_COLUMNS).in('game_id', ids)" in src


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_pick_games.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

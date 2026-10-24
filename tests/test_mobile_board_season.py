"""The Stats board asks the NBA for the season in progress, not the calendar year.

2026-10-23 (Matt): the NBA board showed Jaylen Brown on BOS three months after
his trade to PHI. The board asked for season = calendar year (2026), and the
NBA labels a season by its ENDING year (CLAUDE.md §4), so 2026 is last season.
`boardSeasonET` is the one place the board and the player page get the label.

Runs mobile/src/lib/format.ts under node's type stripping with a pinned clock.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._node import node_exe, node_strips_types

ROOT = Path(__file__).parent.parent
FORMAT = ROOT / "mobile" / "src" / "lib" / "format.ts"
NODE = node_exe() or "node"
needs_node = pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")


def _season_at(tmp_path: Path, iso_utc: str, sport: str) -> int:
    (tmp_path / "format.ts").write_text(FORMAT.read_text(encoding="utf-8"), encoding="utf-8")
    script = f"""
const Real = Date;
const fixed = new Real('{iso_utc}').getTime();
globalThis.Date = class extends Real {{
  constructor(...a) {{ a.length ? super(...a) : super(fixed); }}
  static now() {{ return fixed; }}
}};
const {{ boardSeasonET }} = await import('./format.ts');
console.log(boardSeasonET('{sport}'));
"""
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return int(proc.stdout.strip())


@needs_node
def test_nba_in_october_is_next_years_label(tmp_path):
    """The day it was reported: 2026-10-23 is the 2026-27 season = 2027."""
    assert _season_at(tmp_path, "2026-10-23T16:00:00Z", "NBA") == 2027


@needs_node
def test_nba_after_new_year_is_the_calendar_year(tmp_path):
    assert _season_at(tmp_path, "2027-02-10T16:00:00Z", "NBA") == 2027


@needs_node
def test_nba_label_turns_on_the_et_clock_not_utc(tmp_path):
    """23:30 ET on 30 Sep is 03:30 UTC on 1 Oct — still September in ET."""
    assert _season_at(tmp_path, "2026-10-01T03:30:00Z", "NBA") == 2026


@needs_node
def test_other_sports_keep_the_calendar_year(tmp_path):
    for sport in ("MLB", "WNBA", "NFL", "NCAAF", "NHL", "UFC"):
        assert _season_at(tmp_path, "2026-10-23T16:00:00Z", sport) == 2026, sport


def test_board_reads_use_the_helper_not_the_calendar_year():
    """Every NBA-reachable board read goes through boardSeasonET."""
    src = (ROOT / "mobile" / "src" / "screens" / "StatsScreen.tsx").read_text(encoding="utf-8")
    for call in ("fetchRecentGames(sport, ", "fetchSeasonStatValues(sport, ",
                 "fetchH2HStatValues(sport, ", "fetchWindowTotals(sport, "):
        start = 0
        while (i := src.find(call, start)) != -1:
            assert src.startswith("boardSeasonET(sport)", i + len(call)), call
            start = i + 1
    detail = (ROOT / "mobile" / "src" / "hooks" / "usePlayerDetail.ts").read_text(encoding="utf-8")
    assert "boardSeasonET(sport)" in detail

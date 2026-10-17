"""Pick Detail: a team's form strip is that sport's games in that sport's scoring unit.

The form strip called fetchTeamRecentGames with no sport. PHI's newest 25
finished games before 2026-10-11 were 17 MLB, 4 NHL and 4 NFL. The L3 of the
three games before the 2026-10-05 Flyers result is an Eagles loss (20) and
two Flyers losses (2, 2): 0% and 8.0, labelled "R". NCAAF school names do
not collide with another sport's team id (zero shared names, same day); the
"48.0 R" report is the same hardcoded runs suffix on a points average.

Line history is master's implementation (lineMovementView / sincePick /
historyFrom). Those checks live in tests/test_mobile_line_movement.py and
tests/test_mobile_pick_cta.py.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"
LIB = SRC / "lib"
HOOK = SRC / "hooks" / "useTeamTrends.ts"
SCREEN = SRC / "screens" / "PickDetailScreen.tsx"
STRIP = SRC / "components" / "TrendStrip.tsx"
FORM = LIB / "teamForm.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node_strips_types() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    match = re.match(r"v(\d+)\.(\d+)", out)
    return bool(match) and (int(match.group(1)), int(match.group(2))) >= (22, 6)


def _run(tmp_path: Path, names: list[str], script: str) -> subprocess.CompletedProcess:
    for name in names:
        (tmp_path / name).write_text(_read(LIB / name), encoding="utf-8")
    return subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


PRELUDE = """
const eq = (got, want, what) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) {
    throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
  }
};
"""


def test_team_form_reads_one_sport_and_does_not_say_runs_for_football():
    hook = _read(HOOK)
    assert "fetchTeamRecentGamesForSport(sport, team, beforeDate" in hook
    assert "fetchTeamRecentGames(" not in hook, "the unscoped read mixes PHI across MLB, NFL and NHL"
    screen = _read(SCREEN)
    assert "game?.sport" in screen
    assert "teamScoringUnit(game.sport)" in screen
    assert "teamScoringUnitSpoken(game.sport)" in screen
    assert "countThisSeason(homeTrends.games, game.season)" in screen
    assert "countThisSeason(awayTrends.games, game.season)" in screen
    assert "useTeamTrends('NFL'" not in screen, "NCAAF uses the same strip; the sport comes from the game"
    strip = _read(STRIP)
    assert "toFixed(1)} R`" not in strip, "the team average was hardcoded as runs"
    assert "${t.avg.toFixed(1)} ${unit}" in strip
    # Team column names come from teamStripLabels. Player mode keeps "Season".
    assert "teamStripLabels(" in strip
    assert "teamFifthColumnLabel(" in _read(FORM)
    assert "columnLabel: label" in strip
    assert "label: 'Season'" in strip
    assert "teamCellAccessibilityLabel(" in strip
    assert "teamGamesRow(" not in strip
    assert "teamShortWindowNote(" in strip
    assert "teamSeasonNote(" in strip
    assert "accessible={mode === 'team'}" in strip
    assert strip.count("textAlign: 'center'") >= 4
    assert "season: g.season" in hook
    assert FORM.exists()
    assert "export function teamScoringUnit" in _read(FORM)


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_scoring_unit_is_points_for_football_and_runs_for_baseball(tmp_path):
    script = PRELUDE + """
import { teamScoringUnit, teamScoringUnitSpoken, teamShortWindowNote, teamSeasonNote, teamFifthColumnLabel, teamStripLabels, teamCellAccessibilityLabel, countThisSeason } from './teamForm.ts';
eq(teamScoringUnit('MLB'), 'R', 'mlb');
eq(teamScoringUnit('NFL'), 'pts', 'nfl');
eq(teamScoringUnit('NCAAF'), 'pts', 'ncaaf');
eq(teamScoringUnit('NBA'), 'pts', 'nba');
eq(teamScoringUnit('WNBA'), 'pts', 'wnba');
eq(teamScoringUnit('NHL'), 'goals', 'nhl');
eq(teamScoringUnit(null), '', 'unknown is not runs');
eq(teamScoringUnitSpoken('MLB'), 'runs', 'spoken mlb');
eq(teamScoringUnitSpoken('NFL'), 'points', 'spoken nfl');
eq(teamScoringUnitSpoken('NCAAF'), 'points', 'spoken ncaaf');
eq(teamScoringUnitSpoken('NBA'), 'points', 'spoken nba');
eq(teamScoringUnitSpoken('WNBA'), 'points', 'spoken wnba');
eq(teamScoringUnitSpoken('NHL'), 'goals', 'spoken nhl');
eq(teamScoringUnitSpoken(null), '', 'spoken unknown');
eq(teamFifthColumnLabel(0, 0), 'Season', 'zero games is not L25');
eq(teamFifthColumnLabel(0, null), 'Season', 'empty unknown season is not L25');
eq(teamFifthColumnLabel(1, 1), 'Season', 'one game this season');
eq(teamFifthColumnLabel(4, 4), 'Season', 'fewer than 25, all this season');
eq(teamFifthColumnLabel(25, 25), 'L25', '25 this season is last 25, not the whole season');
eq(teamFifthColumnLabel(25, 4), 'L25', 'last 25 may span seasons');
eq(teamFifthColumnLabel(20, 4), 'L20', 'a short span is not Season and not L25');
eq(teamFifthColumnLabel(4, null), 'L4', 'unknown season is not called Season');
eq(teamShortWindowNote({ l3: 0, l5: 0, l10: 0, l20: 0, l25: 0 }), null, 'no data is not 0 games');
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }), null, 'a full window hides the count');
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }, 4), null, '25 games stays silent');
eq(teamShortWindowNote({ l3: 3, l5: 4, l10: 4, l20: 4, l25: 4 }, 4), 'Only 4 games so far. L5–Season all use those 4.', 'short window');
eq(teamShortWindowNote({ l3: 1, l5: 1, l10: 1, l20: 1, l25: 1 }, 1), 'Only 1 game so far. L3–Season all use that 1.', 'one game');
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 20, l25: 20 }, 20), 'Only 20 games so far. Season uses those 20.', 'only the season column is short');
eq(
  teamStripLabels({ l3: 3, l5: 5, l10: 10, l20: 20, l25: 20 }, 4),
  { l3: 'L3', l5: 'L5', l10: 'L10', l20: 'L20', fifth: 'All' },
  '20 cross-season games are L20 and All, not two L20 columns',
);
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 20, l25: 20 }, 4), 'Only 20 games available. L20 and All use those 20.', '20 cross-season names both columns');
eq(
  teamStripLabels({ l3: 3, l5: 5, l10: 10, l20: 12, l25: 12 }, 4),
  { l3: 'L3', l5: 'L5', l10: 'L10', l20: 'L12', fifth: 'All' },
  '12 cross-season games are L12 and All, not L20 beside L12',
);
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 12, l25: 12 }, 4), 'Only 12 games available. L12 and All use those 12.', '12 cross-season names both columns');
eq(
  teamStripLabels({ l3: 3, l5: 5, l10: 10, l20: 11, l25: 11 }, 4),
  { l3: 'L3', l5: 'L5', l10: 'L10', l20: 'L11', fifth: 'All' },
  '11 cross-season games',
);
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 11, l25: 11 }, 4), 'Only 11 games available. L11 and All use those 11.', '11 cross-season names both columns');
eq(
  teamStripLabels({ l3: 3, l5: 5, l10: 10, l20: 19, l25: 19 }, 4),
  { l3: 'L3', l5: 'L5', l10: 'L10', l20: 'L19', fifth: 'All' },
  '19 cross-season games',
);
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 19, l25: 19 }, 4), 'Only 19 games available. L19 and All use those 19.', '19 cross-season names both columns');
eq(
  teamStripLabels({ l3: 3, l5: 5, l10: 10, l20: 10, l25: 10 }, 4),
  { l3: 'L3', l5: 'L5', l10: 'L10', l20: 'L20', fifth: 'All' },
  '10 cross-season games do not put a second L10 on column 4',
);
const unknownFour = teamShortWindowNote({ l3: 3, l5: 4, l10: 4, l20: 4, l25: 4 }, null);
eq(unknownFour, 'Only 4 games. Every column after L3 uses those 4.', 'unknown season names no season');
if (unknownFour.includes('so far') || unknownFour.includes('Season') || unknownFour.includes('L5, L10')) {
  throw new Error(`unknown season note claims a season: ${unknownFour}`);
}
eq(
  teamStripLabels({ l3: 3, l5: 4, l10: 4, l20: 4, l25: 4 }, null),
  { l3: 'L3', l5: 'L5', l10: 'L10', l20: 'L4', fifth: 'All' },
  'unknown 4 games are not two L4 columns',
);
eq(
  teamSeasonNote(4, { l3: 3, l5: 5, l10: 10, l20: 20, l25: 20 }),
  'This season: 4 games. L5–All include earlier seasons.',
  '20 cross-season season note uses All',
);
eq(
  teamSeasonNote(4, { l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }),
  'This season: 4 games. L5–L25 include earlier seasons.',
  'smallest window that crosses',
);
eq(
  teamSeasonNote(1, { l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }),
  'This season: 1 game. L3–L25 include earlier seasons.',
  'singular game',
);
eq(
  teamSeasonNote(20, { l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }),
  'This season: 20 games. L25 includes earlier seasons.',
  'only L25 crosses',
);
eq(
  teamSeasonNote(0, { l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }),
  'No games yet this season. Every column is from earlier seasons.',
  'none this season',
);
eq(teamSeasonNote(25, { l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }), null, 'all this season');
eq(teamSeasonNote(null, { l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }), null, 'unknown season');
eq(teamSeasonNote(0, { l3: 0, l5: 0, l10: 0, l20: 0, l25: 0 }), null, 'empty fetch is not a season note');
eq(
  teamCellAccessibilityLabel({
    window: 5, games: 5, winPct: 0.4, avg: 18.8, spokenUnit: 'points', seasonGames: 4,
  }),
  'Last 5 games, including earlier seasons: won 40 percent, 18.8 points a game',
  'voiceover',
);
eq(
  teamCellAccessibilityLabel({
    window: 5, games: 5, winPct: 0.4, avg: 18.8, spokenUnit: 'points', seasonGames: 5,
  }),
  'Last 5 games: won 40 percent, 18.8 points a game',
  'voiceover this season only',
);
eq(
  teamCellAccessibilityLabel({
    window: 5, games: 4, winPct: 0.5, avg: 3.2, spokenUnit: 'goals', seasonGames: 2,
  }),
  'Last 5 games, only 4 played, including earlier seasons: won 50 percent, 3.2 goals a game',
  'short count stays in the spoken label',
);
eq(
  teamCellAccessibilityLabel({
    window: 25, games: 4, winPct: 0.5, avg: 3.2, spokenUnit: 'goals', columnLabel: 'Season',
  }),
  'Season, only 4 played: won 50 percent, 3.2 goals a game',
  'a season column is not spoken as last 25',
);
eq(
  teamCellAccessibilityLabel({
    window: 25, games: 25, winPct: 0.5, avg: 3.2, spokenUnit: 'goals', columnLabel: 'L25', seasonGames: 4,
  }),
  'Last 25 games, including earlier seasons: won 50 percent, 3.2 goals a game',
  'L25 may include earlier seasons',
);
eq(
  teamCellAccessibilityLabel({
    window: 25, games: 20, winPct: 0.5, avg: 3.2, spokenUnit: 'goals', columnLabel: 'All', seasonGames: 4,
  }),
  'All games, including earlier seasons: won 50 percent, 3.2 goals a game',
  'All is every game in hand',
);
eq(
  teamCellAccessibilityLabel({
    window: 20, games: 12, winPct: 0.5, avg: 3.2, spokenUnit: 'goals', columnLabel: 'L12', seasonGames: 4,
  }),
  'Last 12 games, including earlier seasons: won 50 percent, 3.2 goals a game',
  'column 4 speaks the count it shows',
);
eq(
  teamCellAccessibilityLabel({
    window: 3, games: 0, winPct: null, avg: null, spokenUnit: 'runs', seasonGames: 0,
  }),
  'Last 3 games: win rate not available, average not available',
  'empty cell does not say 0 games',
);
eq(countThisSeason([{ season: 2027 }, { season: 2027 }, { season: 2026 }], 2027), 2, 'this season');
eq(countThisSeason([{ season: 2026 }], null), null, 'unknown season count');
"""
    proc = _run(tmp_path, ["teamForm.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout

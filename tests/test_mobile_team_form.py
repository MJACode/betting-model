"""The team form strips on a game pick's detail screen: one sport, its own unit.

Two defects the NBA totals overs model (nba_total_luck) brought to NBA picks,
the only live NBA picks that show these strips:

  * the form read matched the team code alone, and `games` stores the Celtics,
    the Red Sox and the Bruins all as 'BOS', so a Celtics strip averaged in
    baseball and hockey games (mobile/src/hooks/useTeamTrends.ts);
  * the scoring average was labelled "R" (runs) for every sport, so an NBA
    total read "112.4 R" (mobile/src/components/TrendStrip.tsx).

The unit is a pure function, run here under node's type stripping; the wiring
is read from the source, as tests/test_mobile_team_detail.py reads its query.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests._node import NODE, node_strips_types

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile" / "src"


def _read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


@pytest.mark.skipif(not node_strips_types(), reason="needs node >= 22.6")
def test_the_scoring_unit_follows_the_sport(tmp_path):
    (tmp_path / "teamForm.ts").write_text(_read("lib/teamForm.ts"), encoding="utf-8")
    script = ("import { teamScoreUnit } from './teamForm.ts';"
              "console.log(JSON.stringify(['MLB','NHL','NBA','WNBA','NFL','NCAAF','nba',null]"
              ".map(teamScoreUnit)));")
    r = subprocess.run([NODE, "--experimental-strip-types", "--input-type=module", "-e", script],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["R", "GF", "PTS", "PTS", "PTS", "PTS", "PTS", "R"]


def test_the_strip_s_team_unit_is_not_hard_coded():
    src = _read("components/TrendStrip.tsx")
    assert "toFixed(1)} R`" not in src, "team mode still says R for every sport"
    assert "toFixed(1)} ${unit ?? 'R'}`" in src


def test_the_form_read_is_scoped_to_one_sport():
    hook = _read("hooks/useTeamTrends.ts")
    assert re.search(r"export function useTeamTrends\(\s*sport: string \| null,", hook)
    assert "fetchTeamRecentGamesForSport(sport, team, beforeDate" in hook
    assert "[sport, team, beforeDate]" in hook, "a new sport must reload the strip"
    for path in SRC.rglob("*.ts*"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bfetchTeamRecentGames\b(?!ForSport)", text), \
            f"{path}: the team-code-only read is back"


def test_the_pick_detail_screen_passes_the_pick_s_sport_and_unit():
    screen = _read("screens/PickDetailScreen.tsx")
    assert "const teamSport = game?.sport ?? pick.sport ?? null;" in screen
    calls = re.findall(r"useTeamTrends\(\s*([^,]+),", screen)
    assert calls == ["showTeamTrends ? teamSport : null"] * 2, calls
    strips = re.findall(r"<TrendStrip\s+title=\{`\$\{game\.(?:home|away)_team\}[^>]*?/>", screen, re.S)
    assert len(strips) == 2 and all("unit={teamScoreUnit(teamSport)}" in s for s in strips), strips

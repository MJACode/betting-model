"""The Teams board explains every number, labels its season right, and does
not print a percentage on a split too small to mean one (Matt, 2026-11-03).

Five things, each of which shipped wrong before this:

1. EVERY stat on the board carries a one-line hint and a Details explanation
   (what it is, what's good, how to use it). Before: 10 of 35 had a hint and
   none said how to use the number for a bet.
2. NBA and NHL ask for the season by its ENDING year. Before: the board asked
   for the calendar year, so on 2026-11-02 it showed the finished 2025-26
   season labelled "2026", a month into 2026-27.
3. MLB / NHL spread splits say run line / puck line, not ATS.
4. A split under 10 games ranks below every split with enough games. Before:
   a 3-2 start at 60% topped a column of 12-game records.
5. Scored/Allowed/Margin per game and NFL pass/rush yards are Record, not
   Efficiency — they are unadjusted, and the yardage is volume.

Plus the server halves: the NBA team-stats step runs before the board
refresh, and the MLB/NHL main-line migration runs after the function's owners.

Run under node's type stripping, like tests/test_mobile_team_total.py.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "mobile" / "src" / "lib"

from tests._node import NODE, node_strips_types  # noqa: E402

node = pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")

FILES = ["teamStatCatalog.ts", "teamBoard.ts"]

PRELUDE = """
const eq = (got, want, what) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
const ok = (cond, what) => { if (!cond) throw new Error(what); };
"""


def _run(tmp_path: Path, script: str) -> None:
    for name in FILES:
        src = (LIB / name).read_text(encoding="utf-8")
        src = re.sub(r"from '\./([\w.]+)';", r"from './\1.ts';", src)
        src = re.sub(r"from '@/lib/([\w.]+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", PRELUDE + script],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


@node
def test_every_stat_in_every_sport_is_explained(tmp_path):
    _run(tmp_path, """
import { teamStatsForSport, explainSections, TEAM_GROUP_INTRO, TEAM_GROUP_ORDER } from './teamStatCatalog.ts';
let n = 0;
for (const sport of ['MLB', 'NBA', 'WNBA', 'NHL', 'NFL', 'NCAAF']) {
  for (const s of teamStatsForSport(sport)) {
    n++;
    const where = `${sport} ${String(s.key)}`;
    ok(typeof s.hint === 'string' && s.hint.length > 10, `${where} has no hint`);
    ok(s.explain && s.explain.what && s.explain.good && s.explain.use, `${where} explain is incomplete`);
    const heads = explainSections(s.explain).map((x) => x.heading);
    eq(heads.slice(0, 3), ['What it is', 'What’s good', 'How to use it'], `${where} sections`);
  }
}
ok(n > 60, `only ${n} stat/sport pairs`);
for (const g of TEAM_GROUP_ORDER) ok(TEAM_GROUP_INTRO[g].length > 10, `${g} has no intro`);
""")


@node
def test_nba_and_nhl_ask_for_the_season_by_its_ending_year(tmp_path):
    _run(tmp_path, """
import { teamBoardSeason, teamSeasonLabel } from './teamStatCatalog.ts';
const nov = new Date('2026-11-02T16:00:00Z');
eq(teamBoardSeason('NBA', nov), 2027, 'NBA in November is the 2026-27 season');
eq(teamBoardSeason('NHL', nov), 2027, 'NHL in November');
eq(teamBoardSeason('NBA', new Date('2026-04-10T16:00:00Z')), 2026, 'NBA in April');
eq(teamBoardSeason('NHL', new Date('2026-10-01T16:00:00Z')), 2027, 'NHL in October');
// 11:30pm ET on Sep 30 is still September in New York (Oct 1 in UTC).
eq(teamBoardSeason('NBA', new Date('2026-10-01T03:30:00Z')), 2026, 'ET clock, not UTC');
eq(teamBoardSeason('MLB', nov), 2026, 'MLB is the calendar year');
eq(teamBoardSeason('NFL', nov), 2026, 'NFL is the starting year');
eq(teamSeasonLabel('NBA', 2027), '2026-27', 'NBA label');
eq(teamSeasonLabel('NHL', 2027), '2026-27', 'NHL label');
eq(teamSeasonLabel('MLB', 2026), '2026', 'MLB label');
""")


@node
def test_run_line_and_puck_line_are_named_for_their_sport(tmp_path):
    _run(tmp_path, """
import { teamStatsForSport, teamStatFor, spreadWord } from './teamStatCatalog.ts';
eq(teamStatFor('MLB', 'ats_pct').label, 'Run Line%', 'MLB ATS');
eq(teamStatFor('NHL', 'ats_pct').label, 'Puck Line%', 'NHL ATS');
eq(teamStatFor('NBA', 'ats_pct').label, 'ATS%', 'NBA ATS');
for (const sport of ['MLB', 'NHL']) {
  for (const s of teamStatsForSport(sport)) ok(!s.label.includes('ATS'), `${sport} ${String(s.key)} still says ATS`);
}
eq([spreadWord('MLB'), spreadWord('NHL'), spreadWord('NFL')], ['RL', 'PL', 'ATS'], 'spread word');
""")


@node
def test_a_split_under_ten_games_ranks_below_one_with_enough(tmp_path):
    _run(tmp_path, """
import { teamStatFor } from './teamStatCatalog.ts';
import { MIN_SPLIT_SAMPLE, isThinSample, rankTeams, sampleFor } from './teamBoard.ts';
eq(MIN_SPLIT_SAMPLE, 10, 'the floor Matt approved');
const ats = teamStatFor('NFL', 'ats_pct');
const base = { team: 'X', games_played: 12, wins: 6, losses: 6, home_w: 3, home_l: 3, away_w: 3, away_l: 3 };
const hot = { ...base, team: 'HOT', ats_w: 3, ats_l: 1, ats_p: 0, ats_pct: 0.75 };
const steady = { ...base, team: 'STD', ats_w: 7, ats_l: 5, ats_p: 0, ats_pct: 0.583 };
eq(sampleFor(hot, ats), 4, 'ATS sample sums w+l+p');
ok(isThinSample(hot, ats), '4 games is thin');
ok(!isThinSample(steady, ats), '12 games is not');
eq(rankTeams([hot, steady], ats).rows.map((r) => r.team), ['STD', 'HOT'], 'thin sinks below');
const home = teamStatFor('NFL', 'ats_home_pct');
eq(sampleFor(hot, home), 6, 'home split counts home games');
ok(isThinSample(hot, home), '6 home games is thin');
ok(!isThinSample(hot, teamStatFor('NFL', 'yards_per_play')), 'a season metric is never thin');
""")


@node
def test_unadjusted_scoring_and_nfl_volume_are_record_not_efficiency(tmp_path):
    _run(tmp_path, """
import { teamStatFor } from './teamStatCatalog.ts';
for (const key of ['point_diff_pg', 'points_for_pg', 'points_against_pg']) {
  eq(teamStatFor('NBA', key).group, 'Record', key);
}
eq(teamStatFor('NFL', 'pass_yards_pg').group, 'Record', 'pass yards');
eq(teamStatFor('NFL', 'rush_yards_pg').group, 'Record', 'rush yards');
eq(teamStatFor('NFL', 'yards_per_play').group, 'Efficiency', 'yards per play');
""")


def test_the_board_asks_by_sport_not_by_calendar_year():
    board = (ROOT / "mobile" / "src" / "components" / "TeamsBoard.tsx").read_text(encoding="utf-8")
    assert "fetchTeamStats(sport, teamBoardSeason(sport))" in board
    assert "getUTCFullYear" not in board
    detail = (ROOT / "mobile" / "src" / "hooks" / "useTeamDetail.ts").read_text(encoding="utf-8")
    assert "season ?? teamBoardSeason(sport)" in detail


def test_nba_team_stats_are_built_before_the_board_refreshes():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    nba = src.index('results["nba_team_stats_box"] = step_nba_team_stats_box(run_date)')
    board = src.index('results["refresh_team_board"] = step_refresh_team_board(run_date)')
    assert nba < board


def test_main_run_line_patch_runs_after_the_functions_owners():
    from data.view_migrations import ACTIVE_MIGRATIONS
    order = {name: i for i, name in enumerate(ACTIVE_MIGRATIONS)}
    mine = order["team_stats_board_main_run_line_2026_11_03.sql"]
    assert mine > order["team_stats_board_line_probe_2026_09_28.sql"]
    assert mine > order["team_stats_board_commence_bound_2026_09_30.sql"]
    sql = (ROOT / "data" / "migrations" / "team_stats_board_main_run_line_2026_11_03.sql").read_text(encoding="utf-8")
    # Guards on its own marker and leaves the owners' markers in place.
    assert "position('team_board_main_run_line' in def) > 0" in sql
    assert "abs(oo.spread_home) = 1.5" in sql

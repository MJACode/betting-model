"""Pick Detail: line movement must reach the latest snapshot, and a team's
form strip must be that sport's games in that sport's scoring unit.

Measured 2026-10-06 on JAX/PHI (NFL_2026_05_PHI_JAX), DraftKings spreads:
3,939 snapshots. Ordered oldest-first with a 50-row limit, the page ended
2026-10-02 at home −3. The latest row the same minute was home −7. The card
prints the last row it was given as the current number, so an away pick
locked at +6 read "+6 → +3" while every book was at PHI +6.5/+7.

The form strip called fetchTeamRecentGames with no sport. PHI's newest 25
finished games before 2026-10-11 were 17 MLB, 4 NHL and 4 NFL. The L3 of the
three games before the 2026-10-05 Flyers result is an Eagles loss (20) and
two Flyers losses (2, 2): 0% and 8.0, labelled "R". NCAAF school names do
not collide with another sport's team id (zero shared names, same day); the
"48.0 R" report is the same hardcoded runs suffix on a points average.
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
QUERIES = LIB / "queries.ts"
HOOK = SRC / "hooks" / "useTeamTrends.ts"
SCREEN = SRC / "screens" / "PickDetailScreen.tsx"
STRIP = SRC / "components" / "TrendStrip.tsx"
HISTORY = LIB / "lineHistory.ts"
FORM = LIB / "teamForm.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _history_region(src: str) -> str:
    start = src.index("// ── Line movement")
    end = src.index("// ── Prop matchup context")
    return src[start:end]


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


# ── line movement ──────────────────────────────────────────────────────────


def test_odds_history_is_not_an_oldest_first_page():
    """The old read was one ascending query capped at 50. That page is the
    open, and the card treats its last row as now."""
    region = _history_region(_read(QUERIES))
    assert "sampleOpenToNow" in region
    assert region.count("sampleOpenToNow") >= 2, "game lines and props both sample open-to-now"
    assert ".eq('bookmaker', bookmaker)" in region
    assert "'draftkings'" not in region
    # The player-page tripwire matches only up to the function's first
    # unindented close, so the relation literal has to sit inside it.
    for fn, rel in (
        ("fetchOddsHistory", "odds"),
        ("fetchPropOddsHistory", "player_prop_odds"),
    ):
        body = re.search(rf"export async function {fn}\(.*?\n\}}\n", region, re.S)
        assert body, fn
        assert f".from('{rel}')" in body.group(0)
    assert not re.search(
        r"order\('snapshot_at', \{ ascending: true \}\)\s*\.limit\(50\)",
        region,
    ), "an oldest-first limit-50 page drops the current line"


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_sampler_ends_on_the_latest_line_not_the_fiftieth_oldest(tmp_path):
    """The JAX/PHI shape: a long early run at −3, then the current −7.
    slice(0, 50) still ends at −3. The sampler must start at the open and
    end at −7, and keep the latest page rather than replace it."""
    script = PRELUDE + """
import { sampleOpenToNow, LINE_HISTORY_PAGE, historyBucketInstants } from './lineHistory.ts';

function stamp(ms) { return new Date(ms).toISOString(); }
const rows = [];
const t0 = Date.parse('2026-10-01T03:59:29.000Z');
const late = Date.parse('2026-10-06T09:31:00.000Z');
rows.push({ snapshot_at: stamp(t0), spread_home: -2.5 });
// The early line has to span the gap. A burst in the first hour sits between
// the open and the first bucket, and equal-time probes then land in the hole
// after it. On the JAX/PHI book the −3 held for days, not an hour.
for (let i = 0; i < 70; i++) {
  rows.push({ snapshot_at: stamp(t0 + ((late - t0) * (i + 1)) / 72), spread_home: -3 });
}
for (let i = 0; i < 50; i++) {
  rows.push({ snapshot_at: stamp(late + i * 1000), spread_home: -7 });
}
const oldestPage = rows.slice(0, LINE_HISTORY_PAGE);
eq(oldestPage[oldestPage.length - 1].spread_home, -3, 'stale page');
eq(rows[rows.length - 1].spread_home, -7, 'true latest');

const read = async (probe) => {
  let xs = rows.filter((r) => {
    const t = Date.parse(r.snapshot_at);
    if (probe.gte && t < Date.parse(probe.gte)) return false;
    if (probe.lt && t >= Date.parse(probe.lt)) return false;
    return true;
  });
  xs.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));
  if (!probe.ascending) xs.reverse();
  return xs.slice(0, probe.limit);
};
const sampled = await sampleOpenToNow(read);
eq(sampled[0].spread_home, -2.5, 'open');
eq(sampled[sampled.length - 1].spread_home, -7, 'latest line');
eq(sampled[sampled.length - 1].snapshot_at, rows[rows.length - 1].snapshot_at, 'latest stamp');
eq(sampled.filter((r) => r.spread_home === -7).length, 50, 'latest page kept');
if (!sampled.some((r) => r.spread_home === -3)) throw new Error('gap between open and now was dropped');
for (let i = 1; i < sampled.length; i++) {
  if (Date.parse(sampled[i].snapshot_at) < Date.parse(sampled[i - 1].snapshot_at)) {
    throw new Error('series is not oldest-first');
  }
}
const instants = historyBucketInstants(rows[0].snapshot_at, rows[rows.length - 1].snapshot_at, 12);
eq(instants.length, 10, 'interior buckets');
if (!(Date.parse(instants[0]) > Date.parse(rows[0].snapshot_at))) throw new Error('bucket on the open');
if (!(Date.parse(instants[instants.length - 1]) < Date.parse(rows[rows.length - 1].snapshot_at))) {
  throw new Error('bucket on the latest');
}
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_short_history_is_returned_whole(tmp_path):
    """Bucketing a 4-row series would drop the middle. Under a page, every row stays."""
    script = PRELUDE + """
import { sampleOpenToNow } from './lineHistory.ts';
const rows = [
  { snapshot_at: '2026-10-01T00:00:00.000Z', spread_home: -2.5 },
  { snapshot_at: '2026-10-02T00:00:00.000Z', spread_home: -3 },
  { snapshot_at: '2026-10-03T00:00:00.000Z', spread_home: -6 },
  { snapshot_at: '2026-10-04T00:00:00.000Z', spread_home: -7 },
];
const read = async (probe) => {
  let xs = rows.filter((r) => {
    const t = Date.parse(r.snapshot_at);
    if (probe.gte && t < Date.parse(probe.gte)) return false;
    if (probe.lt && t >= Date.parse(probe.lt)) return false;
    return true;
  });
  xs.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));
  if (!probe.ascending) xs.reverse();
  return xs.slice(0, probe.limit);
};
const sampled = await sampleOpenToNow(read);
eq(sampled.map((r) => r.spread_home), [-2.5, -3, -6, -7], 'whole series');
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


# ── form strip ─────────────────────────────────────────────────────────────


def test_team_form_reads_one_sport_and_does_not_say_runs_for_football():
    hook = _read(HOOK)
    assert "fetchTeamRecentGamesForSport(sport, team, beforeDate" in hook
    assert "fetchTeamRecentGames(" not in hook, "the unscoped read mixes PHI across MLB, NFL and NHL"
    screen = _read(SCREEN)
    assert "game?.sport" in screen
    assert "teamScoringUnit(game.sport)" in screen
    assert "useTeamTrends('NFL'" not in screen, "NCAAF uses the same strip; the sport comes from the game"
    strip = _read(STRIP)
    assert "toFixed(1)} R`" not in strip, "the team average was hardcoded as runs"
    assert "${t.avg.toFixed(1)} ${unit}" in strip
    # The fifth column is the last 25 games in that sport, not the season.
    # Player mode keeps "Season": its window is 25 or 50 depending on sport.
    assert "mode === 'team' && k.key === 'season' ? 'L25'" in strip
    assert "label: 'Season'" in strip


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_scoring_unit_is_points_for_football_and_runs_for_baseball(tmp_path):
    script = PRELUDE + """
import { teamScoringUnit } from './teamForm.ts';
eq(teamScoringUnit('MLB'), 'R', 'mlb');
eq(teamScoringUnit('NFL'), 'pts', 'nfl');
eq(teamScoringUnit('NCAAF'), 'pts', 'ncaaf');
eq(teamScoringUnit('NBA'), 'pts', 'nba');
eq(teamScoringUnit('WNBA'), 'pts', 'wnba');
eq(teamScoringUnit('NHL'), 'goals', 'nhl');
eq(teamScoringUnit(null), '', 'unknown is not runs');
"""
    proc = _run(tmp_path, ["teamForm.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_partial_history_footer_does_not_quote_the_sample_as_the_book(tmp_path):
    """62 sampled rows are not 62 snapshots of the book. The complete-history
    footer is unchanged."""
    script = PRELUDE + """
import { changesFooter, LINE_HISTORY_PAGE } from './lineHistory.ts';
const partial = changesFooter({ changes: 11, shownChanges: 8, hidden: 3 }, 62, true);
if (partial.includes('62')) throw new Error('partial footer quotes the sample size: ' + partial);
if (!partial.includes('open')) throw new Error(partial);
if (!partial.includes(String(LINE_HISTORY_PAGE))) throw new Error(partial);
eq(changesFooter({ changes: 19, shownChanges: 8, hidden: 12 }, 20), 'Last 8 of 19 changes · 20 snapshots', 'complete');
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_the_card_marks_a_full_page_as_partial():
    card = _read(SRC / "components" / "LineMovementCard.tsx")
    assert "snaps.length > LINE_HISTORY_PAGE" in card
    assert "changesFooter({ changes, shownChanges, hidden }, snaps.length, partial)" in card


def test_history_and_form_modules_exist():
    assert HISTORY.exists()
    assert FORM.exists()
    assert "export async function sampleOpenToNow" in _read(HISTORY)
    assert "export function teamScoringUnit" in _read(FORM)

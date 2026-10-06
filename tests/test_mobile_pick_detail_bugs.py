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
const sampled = (await sampleOpenToNow(read)).rows;
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
const sampled = (await sampleOpenToNow(read)).rows;
eq(sampled.map((r) => r.spread_home), [-2.5, -3, -6, -7], 'whole series');
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_history_reads_cap_at_commence_and_do_not_filter_snapshot_type():
    """Post-start rows stay tagged 'open'. The cap is snapshot_at <= commence,
    after the equality filters, inside each exported function."""
    region = _history_region(_read(QUERIES))
    for fn in ("fetchOddsHistory", "fetchPropOddsHistory"):
        body = re.search(rf"export async function {fn}\(.*?\n\}}\n", region, re.S)
        assert body, fn
        assert ".lte('snapshot_at', probe.lte)" in body.group(0)
        assert "snapshot_type" not in body.group(0)
    card = _read(SRC / "components" / "LineMovementCard.tsx")
    assert "lineHistoryWindow" in card
    assert "fetchOddsHistory(pick.game_id, market, historyBook, historyWindow, sideQuote)" in card
    assert "fetchPropOddsHistory(pick.game_id, market, playerName!, historyBook, historyWindow, sideQuote)" in card
    screen = _read(SCREEN)
    assert "commenceTime={game?.commence_time || pick.game_time}" in screen
    assert "gameHasStarted(game, liveState, pick.game_time)" in screen
    history = _read(HISTORY)
    assert "No start time on the game or the pick, so this read is not capped." in history


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_pregame_history_stops_at_kickoff_and_a_live_pick_may_pass_it(tmp_path):
    """ATL @ NO shape: the book keeps printing after the start, and the last
    DraftKings spread is NO +21.5 (home +21.5) at -1100. A pregame pick must
    not read that row. A live pick, locked after the start, may."""
    script = PRELUDE + """
import { sampleOpenToNow, lineHistoryWindow, LINE_HISTORY_BISECT_CAP, LINE_HISTORY_BISECT_STEPS } from './lineHistory.ts';

const KICK = '2026-10-05T00:15:00.000Z';
const LOCK = '2026-10-05T01:00:00.000Z';
const rows = [];
const t0 = Date.parse('2026-10-01T03:59:29.000Z');
const kick = Date.parse(KICK);
for (let i = 0; i < 70; i++) {
  const at = t0 + ((kick - 60_000 - t0) * i) / 69;
  rows.push({
    snapshot_at: new Date(at).toISOString(),
    spread_home: i === 0 ? -2.5 : -3,
    home_price: -110,
  });
}
// In-game. The last row is the one the card used to treat as current.
for (let i = 0; i < 60; i++) {
  const at = kick + 5 * 60_000 + i * 3 * 60_000;
  const last = i === 59;
  rows.push({
    snapshot_at: last ? '2026-10-05T03:26:00.000Z' : new Date(at).toISOString(),
    spread_home: last ? 21.5 : 14,
    home_price: last ? -1100 : -180,
  });
}

function readFactory() {
  const probes = [];
  const read = async (probe) => {
    probes.push(probe);
    let xs = rows.filter((r) => {
      const t = Date.parse(r.snapshot_at);
      if (probe.gte && t < Date.parse(probe.gte)) return false;
      if (probe.lt && t >= Date.parse(probe.lt)) return false;
      if (probe.lte && t > Date.parse(probe.lte)) return false;
      return true;
    });
    xs.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));
    if (!probe.ascending) xs.reverse();
    return xs.slice(0, probe.limit);
  };
  return { probes, read };
}

const pregame = lineHistoryWindow({
  commenceTime: KICK,
  createdAt: '2026-10-04T18:00:00.000Z',
  isLive: false,
});
eq(pregame, { until: KICK }, 'pregame window');
const pre = readFactory();
const capped = await sampleOpenToNow(pre.read, pregame);
if (capped.rows.some((r) => Date.parse(r.snapshot_at) > Date.parse(KICK))) {
  throw new Error('pregame read returned a post-start row');
}
if (capped.rows.some((r) => r.spread_home === 21.5)) {
  throw new Error('pregame read ended on the in-game NO +21.5');
}
eq(capped.rows[capped.rows.length - 1].spread_home, -3, 'last pregame number');
if (!pre.probes.length) throw new Error('no probes');
if (!pre.probes.every((p) => p.unbounded || p.lte === KICK)) {
  throw new Error('a probe was not capped at commence_time: ' + JSON.stringify(pre.probes.find((p) => !p.unbounded && p.lte !== KICK)));
}
const openProbe = pre.probes.find((p) => p.ascending && p.limit === 1 && !p.gte);
const latestProbe = pre.probes.find((p) => !p.ascending && p.limit === 50);
if (!openProbe || !latestProbe) throw new Error('open or latest page was not read');

// Unknown start: the same book is read unbounded, which is the old behaviour.
eq(lineHistoryWindow({ commenceTime: null, createdAt: '2026-10-04T18:00:00.000Z', isLive: false }), {}, 'unknown start');
const openEnded = await sampleOpenToNow(readFactory().read);
eq(openEnded.rows[openEnded.rows.length - 1].spread_home, 21.5, 'uncapped still sees the in-game line');

const latePregame = lineHistoryWindow({ commenceTime: KICK, createdAt: LOCK, isLive: false });
eq(latePregame, { until: LOCK }, 'written after the stored start is capped at the lock');
if (latePregame.from) throw new Error('a non-live window must not start at the lock');
if (Date.parse(latePregame.until) < Date.parse(KICK)) throw new Error('cap is before the start');
const liveWindow = lineHistoryWindow({ commenceTime: KICK, createdAt: LOCK, isLive: true });
eq(liveWindow, { from: LOCK }, 'is_live starts at the lock');
eq(lineHistoryWindow({ commenceTime: KICK, createdAt: '2026-10-04T18:00:00.000Z', isLive: true }), { from: '2026-10-04T18:00:00.000Z' }, 'is_live before the start still starts at the lock');
const live = readFactory();
const after = await sampleOpenToNow(live.read, liveWindow);
if (after.rows.some((r) => Date.parse(r.snapshot_at) < Date.parse(LOCK))) {
  throw new Error('live read returned a row from before the lock');
}
eq(after.rows[after.rows.length - 1].spread_home, 21.5, 'live read may pass the start');
eq(after.rows[after.rows.length - 1].home_price, -1100, 'live read keeps the in-game price');
if (!live.probes.every((p) => !p.lte)) throw new Error('live read was capped at kickoff');
if (!live.probes.every((p) => !p.gte || Date.parse(p.gte) >= Date.parse(LOCK))) {
  throw new Error('live read started before the lock');
}

// Bisect budget. Twelve distinct gap quotes, so most changes are not refined.
const noisy = [];
const spanStart = Date.parse('2026-10-01T00:00:00.000Z');
const spanEnd = Date.parse('2026-10-06T00:00:00.000Z');
for (let i = 0; i < 80; i++) {
  noisy.push({
    snapshot_at: new Date(spanStart + ((spanEnd - spanStart) * i) / 79).toISOString(),
    spread_home: i < 30 ? i : -7,
  });
}
let calls = 0;
const noisyRead = async (probe) => {
  calls += 1;
  let xs = noisy.filter((r) => {
    const t = Date.parse(r.snapshot_at);
    if (probe.gte && t < Date.parse(probe.gte)) return false;
    if (probe.lt && t >= Date.parse(probe.lt)) return false;
    if (probe.lte && t > Date.parse(probe.lte)) return false;
    return true;
  });
  xs.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));
  if (!probe.ascending) xs.reverse();
  return xs.slice(0, probe.limit);
};
await sampleOpenToNow(noisyRead);
// The extra read is the unbounded newest row that names the series offset.
if (calls > 1 + 2 + 10 + LINE_HISTORY_BISECT_CAP) {
  throw new Error(`bisect blew the cap: ${calls} reads, cap ${LINE_HISTORY_BISECT_CAP}, steps ${LINE_HISTORY_BISECT_STEPS}`);
}
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_gap_change_is_bisected_back_toward_the_real_move(tmp_path):
    """The probe time is the first row at the bucket, hours after the move.
    Six steps between adjacent samples have to land on the real first row."""
    script = PRELUDE + """
import { sampleOpenToNow } from './lineHistory.ts';
// A row every minute, so a bucket probe lands on the probe time and not on
// the move. The move sits between the 1h and 2h probes.
const t0 = Date.parse('2026-10-01T00:00:00.000Z');
const minute = 60_000;
const trueMove = t0 + 90 * minute;
const pageStart = t0 + 11 * 60 * minute;
const rows = [];
for (let m = 0; m < 11 * 60; m++) {
  const at = t0 + m * minute;
  rows.push({
    snapshot_at: new Date(at).toISOString(),
    spread_home: at < t0 + minute ? -2.5 : at < trueMove ? -3 : -7,
  });
}
for (let i = 0; i < 50; i++) {
  rows.push({ snapshot_at: new Date(pageStart + i * 1000).toISOString(), spread_home: -7 });
}
const read = async (probe) => {
  let xs = rows.filter((r) => {
    const t = Date.parse(r.snapshot_at);
    if (probe.gte && t < Date.parse(probe.gte)) return false;
    if (probe.lt && t >= Date.parse(probe.lt)) return false;
    if (probe.lte && t > Date.parse(probe.lte)) return false;
    return true;
  });
  xs.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));
  if (!probe.ascending) xs.reverse();
  return xs.slice(0, probe.limit);
};
const sampled = await sampleOpenToNow(read);
const firstSeven = sampled.rows.find((r) => r.spread_home === -7);
eq(firstSeven.snapshot_at, new Date(trueMove).toISOString(), 'change time, not the probe');
const pageKept = sampled.rows.filter((r) => Date.parse(r.snapshot_at) >= pageStart);
eq(pageKept.length, 50, 'latest page kept row for row');
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_close_label_and_footer_copy(tmp_path):
    """After the start the headline and the verdict compare the lock to the
    close, and the last row is labelled Close. Unstarted copy stays put."""
    script = PRELUDE + """
import { historyTimeLabel, movementHeadline, movementVerdict, changesFooter } from './lineHistory.ts';
eq(historyTimeLabel('3:10 PM', { atCloseLast: true, bounded: false }), 'Close', 'close row');
eq(historyTimeLabel('8:21 PM', { atCloseLast: false, atFinalLast: true, bounded: false }), 'Final', 'live end');
eq(historyTimeLabel('3:10 PM', { atCloseLast: false, bounded: true }), 'by 3:10 PM', 'upper bound');
eq(historyTimeLabel('3:10 PM', { atCloseLast: false, bounded: false }), '3:10 PM', 'real time');
eq(movementHeadline('+6', '+3', false), '+6 → +3', 'unstarted headline');
eq(movementHeadline('+6', '+3', true), '+6 → +3 at the close', 'close headline');
eq(movementHeadline('-110', '-105', true), '-110 → -105 at the close', 'close price headline');
eq(
  movementVerdict({ kind: 'steady', atClose: false }),
  'Line steady since pick',
  'unstarted steady',
);
eq(
  movementVerdict({ kind: 'steady', atClose: true }),
  'Line steady through the close',
  'close steady',
);
eq(
  movementVerdict({ kind: 'against', atClose: false, lock: '+6', end: '+3' }),
  'Line moved +6 → +3 against your pick',
  'unstarted against',
);
eq(
  movementVerdict({ kind: 'against', atClose: true, lock: '+6', end: '+3' }),
  'Line moved +6 → +3 against your pick by the close',
  'close against',
);
if (movementVerdict({ kind: 'against', atClose: true, lock: '+6', end: '+3' }).includes('away')) {
  throw new Error('the side key is still in the verdict');
}
eq(
  movementVerdict({ kind: 'favor', atClose: true, lock: '+6', end: '+7' }),
  'Line moved +6 → +7 in your favor by the close',
  'close favor',
);
eq(
  movementVerdict({ kind: 'steamed', atClose: false, pp: 2.4 }),
  'Steamed 2.4pp against you since scoring',
  'unstarted steam',
);
eq(
  movementVerdict({ kind: 'steamed', atClose: true, pp: 2.4 }),
  'Steamed 2.4pp against you by the close',
  'close steam',
);
eq(
  movementVerdict({ kind: 'eased', atClose: true, pp: -2.4 }),
  'Moved 2.4pp in your favor by the close',
  'close eased',
);
eq(
  movementVerdict({ kind: 'eased', atClose: false, pp: -2.4 }),
  'Moved 2.4pp in your favor since scoring',
  'unstarted eased',
);
const footer = changesFooter({ changes: 11, shownChanges: 8, hidden: 3 }, 62, true);
eq(footer, "Last 8 changes shown · brief moves between samples may be missing", 'footer');
if (footer.includes('62')) throw new Error(footer);
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_the_card_uses_the_close_copy():
    card = _read(SRC / "components" / "LineMovementCard.tsx")
    assert "movementHeadline(" in card
    assert "movementVerdict(" in card
    assert "historyTimeLabel(" in card
    assert "historyWindow, sideQuote)" in card
    assert "gameStarted && historyWindow.until != null && !inPlay" in card
    assert "inPlayMovementLabel()" in card
    assert "atFinalLast: inPlay && i === recent.length - 1" in card
    assert "Changed at (ET)" in card
    assert "the line at ${book}" in card
    assert "formatHistoryAmerican(" in card
    assert "formatHistoryLine(lineForSide(" in card
    assert "formatSideLine(" not in card
    assert "accessibilityLabel={movementHeadlineLabel(" in card
    assert "historyRowAccessibilityLabel(" in card
    history = _read(HISTORY)
    assert "against your pick" in history
    assert "against your ${" not in history


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_bounds_follow_the_series_offset_and_close_is_pregame(tmp_path):
    """snapshot_at is text. A UTC cap lets every -04:00 / -05:00 in-game row
    through, and the card would label that row Close. ATL @ LAD shape."""
    script = PRELUDE + r"""
import { sampleOpenToNow, lineHistoryWindow, formatBoundLike, normalizeTimestamp, historyTimeLabel } from './lineHistory.ts';

const KICK = '2026-10-05T00:10:00+00:00';
eq(formatBoundLike('2026-10-04T23:20:05-04:00', Date.parse(KICK)), '2026-10-04T20:10:00-04:00', '-04 cap');
eq(formatBoundLike('2026-10-04T22:00:00-05:00', Date.parse(KICK)), '2026-10-04T19:10:00-05:00', '-05 cap');
eq(formatBoundLike('2026-10-05T03:26:00.000Z', Date.parse('2026-10-05T00:15:00.000Z')), '2026-10-05T00:15:00.000Z', 'Z bound');
eq(formatBoundLike(KICK, Date.parse(KICK)), KICK, '+00:00 bound');
eq(formatBoundLike('2026-10-04T23:20:05-04:00', Date.parse('2026-10-04T23:20:05-04:00')), '2026-10-04T23:20:05-04:00', '-04 round trip');
eq(formatBoundLike('2026-10-04T22:00:00-05:00', Date.parse('2026-10-04T22:00:00-05:00')), '2026-10-04T22:00:00-05:00', '-05 round trip');

const lock = normalizeTimestamp('2026-10-05 01:00:00.123+00');
eq(lock, '2026-10-05T01:00:00.123+00:00', 'space form');
if (Date.parse(lock) !== Date.parse('2026-10-05T01:00:00.123Z')) throw new Error('normalized lock drifted');
eq(lineHistoryWindow({ createdAt: '2026-10-05 01:00:00.123+00', commenceTime: KICK, isLive: false }), { until: lock }, 'late pregame space lock is capped at the lock');
eq(lineHistoryWindow({ createdAt: '2026-10-05 01:00:00.123+00', commenceTime: KICK, isLive: true }), { from: lock }, 'live space lock is normalized');
eq(lineHistoryWindow({ createdAt: 'not-a-timestamp', commenceTime: KICK, isLive: false }), { until: KICK }, 'unparseable pregame lock is still capped');
eq(lineHistoryWindow({ createdAt: 'not-a-timestamp', commenceTime: KICK, isLive: true }), {}, 'unparseable live lock is unknown');

function textRead(rows, probes) {
  return async (probe) => {
    probes.push({ ...probe });
    let xs = rows.filter((r) => {
      if (probe.unbounded) return true;
      const at = r.snapshot_at;
      if (probe.gte && at < probe.gte) return false;
      if (probe.lt && at >= probe.lt) return false;
      if (probe.lte && at > probe.lte) return false;
      return true;
    });
    xs.sort((a, b) => (a.snapshot_at < b.snapshot_at ? -1 : a.snapshot_at > b.snapshot_at ? 1 : 0));
    if (!probe.ascending) xs.reverse();
    return xs.slice(0, probe.limit);
  };
}

async function runOffset(sample, cap, lastPregame, late, mixed) {
  if (!(late <= KICK)) throw new Error('late row no longer slips under the UTC cap: ' + late);
  if (!(late > cap)) throw new Error('series cap does not exclude the in-game row');
  const rows = [];
  for (let i = 10; i >= 1; i--) {
    rows.push({
      snapshot_at: formatBoundLike(sample, Date.parse(lastPregame) - i * 60_000),
      spread_home: -3,
    });
  }
  rows.push({ snapshot_at: lastPregame, spread_home: 7.5 });
  for (let i = 2; i <= 70; i++) {
    rows.push({
      snapshot_at: formatBoundLike(sample, Date.parse(lastPregame) + i * 60_000),
      spread_home: 14,
    });
  }
  rows.push({ snapshot_at: late, spread_home: 99 });
  if (mixed) rows.push({ snapshot_at: mixed, spread_home: 98 });
  const probes = [];
  const window = lineHistoryWindow({
    commenceTime: KICK,
    createdAt: '2026-10-04 18:00:00+00',
    isLive: false,
  });
  eq(window, { until: KICK }, 'pregame until');
  const sampled = await sampleOpenToNow(textRead(rows, probes), window);
  const kickMs = Date.parse(KICK);
  for (const row of sampled.rows) {
    if (Date.parse(row.snapshot_at) > kickMs) throw new Error('post-start reached the card: ' + row.snapshot_at);
  }
  eq(sampled.rows[sampled.rows.length - 1].snapshot_at, lastPregame, 'close row');
  eq(sampled.rows[sampled.rows.length - 1].spread_home, 7.5, 'close number');
  if (sampled.rows.some((r) => r.spread_home === 99 || r.spread_home === 98)) {
    throw new Error('in-game number reached the card');
  }
  eq(historyTimeLabel('8:09 PM ET', { atCloseLast: true, bounded: false }), 'Close', 'close label');
  const ranged = probes.filter((p) => !p.unbounded);
  if (!ranged.length) throw new Error('no ranged read');
  if (!ranged.every((p) => p.lte === cap)) {
    throw new Error('bound left the series offset: ' + JSON.stringify(ranged.find((p) => p.lte !== cap)));
  }
}

await runOffset(
  '2026-10-04T23:20:05-04:00',
  '2026-10-04T20:10:00-04:00',
  '2026-10-04T20:09:00-04:00',
  '2026-10-04T23:20:05-04:00',
  '2026-10-04T20:00:00-05:00',
);
await runOffset(
  '2026-10-04T22:00:00-05:00',
  '2026-10-04T19:10:00-05:00',
  '2026-10-04T19:09:00-05:00',
  '2026-10-04T22:00:00-05:00',
  '2026-10-04T19:00:00-06:00',
);

const liveProbes = [];
const liveRows = [
  { snapshot_at: '2026-10-05T00:30:00.000Z', spread_home: -3 },
  { snapshot_at: '2026-10-05T01:30:00.000Z', spread_home: -7 },
];
const liveSampled = await sampleOpenToNow(
  textRead(liveRows, liveProbes),
  lineHistoryWindow({ createdAt: '2026-10-05 01:00:00.123+00', commenceTime: KICK, isLive: true }),
);
if (liveSampled.rows.some((r) => Date.parse(r.snapshot_at) < Date.parse(lock))) {
  throw new Error('space-form lock leaked a row from before the lock');
}
eq(liveSampled.rows.map((r) => r.spread_home), [-7], 'live page starts at the lock');
const gtes = liveProbes.map((p) => p.gte).filter(Boolean);
if (!gtes.length) throw new Error('live read sent no lower bound');
if (gtes.some((g) => g.includes(' '))) throw new Error('space-form bound was sent: ' + gtes.join(','));
if (!gtes.every((g) => g.endsWith('Z'))) throw new Error('lock was not written like the series: ' + gtes.join(','));
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_bisect_on_a_local_offset_does_not_call_the_wrong_row_tight(tmp_path):
    """Bucket and bisect probes used to be toISOString() UTC. Against a
    -04:00 series that text misses the real move and can call a later row tight."""
    script = PRELUDE + r"""
import { sampleOpenToNow, formatBoundLike } from './lineHistory.ts';

const sample = '2026-10-01T00:00:00-04:00';
const t0 = Date.parse('2026-10-01T04:00:00Z');
const minute = 60_000;
const trueMove = t0 + 90 * minute;
const pageStart = t0 + 11 * 60 * minute;
const rows = [];
for (let m = 0; m < 11 * 60; m++) {
  const at = t0 + m * minute;
  rows.push({
    snapshot_at: formatBoundLike(sample, at),
    spread_home: at < t0 + minute ? -2.5 : at < trueMove ? -3 : -7,
  });
}
for (let i = 0; i < 50; i++) {
  rows.push({ snapshot_at: formatBoundLike(sample, pageStart + i * 1000), spread_home: -7 });
}
const probes = [];
const read = async (probe) => {
  probes.push({ ...probe });
  let xs = rows.filter((r) => {
    if (probe.unbounded) return true;
    const at = r.snapshot_at;
    if (probe.gte && at < probe.gte) return false;
    if (probe.lt && at >= probe.lt) return false;
    if (probe.lte && at > probe.lte) return false;
    return true;
  });
  xs.sort((a, b) => (a.snapshot_at < b.snapshot_at ? -1 : a.snapshot_at > b.snapshot_at ? 1 : 0));
  if (!probe.ascending) xs.reverse();
  return xs.slice(0, probe.limit);
};
const sampled = await sampleOpenToNow(read);
const want = formatBoundLike(sample, trueMove);
const firstSeven = sampled.rows.find((r) => r.spread_home === -7);
eq(firstSeven.snapshot_at, want, 'change time');
if (sampled.moveByAt.includes(want)) throw new Error('true move left as an upper bound');
const bisect = probes.filter((p) => p.ascending && p.limit === 1 && p.gte && p.lt);
if (!bisect.length) throw new Error('no bisect probe');
if (bisect.some((p) => p.gte.endsWith('Z') || !p.gte.endsWith('-04:00'))) {
  throw new Error('bisect gte left the series: ' + bisect[0].gte);
}
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_the_other_sides_price_does_not_place_the_move(tmp_path):
    """A home-price tick with the away line and price unchanged is not the move."""
    script = PRELUDE + r"""
import { sampleOpenToNow } from './lineHistory.ts';

const t0 = Date.parse('2026-10-01T00:00:00.000Z');
const minute = 60_000;
const trueMove = t0 + 90 * minute;
const otherTick = t0 + 100 * minute;
const pageStart = t0 + 11 * 60 * minute;
const rows = [];
for (let m = 0; m < 11 * 60; m++) {
  const at = t0 + m * minute;
  rows.push({
    snapshot_at: new Date(at).toISOString(),
    spread_home: at < t0 + minute ? -2.5 : at < trueMove ? -3 : -7,
    home_price: at < otherTick ? -110 : -115,
    away_price: -110,
  });
}
for (let i = 0; i < 50; i++) {
  rows.push({
    snapshot_at: new Date(pageStart + i * 1000).toISOString(),
    spread_home: -7,
    home_price: -115,
    away_price: -110,
  });
}
const read = async (probe) => {
  let xs = rows.filter((r) => {
    const t = Date.parse(r.snapshot_at);
    if (probe.gte && t < Date.parse(probe.gte)) return false;
    if (probe.lt && t >= Date.parse(probe.lt)) return false;
    if (probe.lte && t > Date.parse(probe.lte)) return false;
    return true;
  });
  xs.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));
  if (!probe.ascending) xs.reverse();
  return xs.slice(0, probe.limit);
};
const quote = (row) => `${row.spread_home}|${row.away_price}`;
const sampled = await sampleOpenToNow(read, undefined, quote);
const firstSeven = sampled.rows.find((r) => r.spread_home === -7);
eq(firstSeven.snapshot_at, new Date(trueMove).toISOString(), 'side quote');
if (firstSeven.snapshot_at === new Date(otherTick).toISOString()) {
  throw new Error('move placed on the other side');
}
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_late_pregame_pick_stops_at_the_close_and_a_live_pick_ends_on_final(tmp_path):
    """is_live false and the lock after the stored commence_time. Capping at
    commence alone drops the row the pick was priced from. The cap is the
    lock: open through that row, Close on it, and the later in-play row
    stays out. A true live pick may pass the start and ends on Final."""
    script = PRELUDE + r"""
import {
  sampleOpenToNow, lineHistoryWindow, historyTimeLabel, inPlayMovementLabel,
  collapseLineHistory, historyRowAccessibilityLabel, movementHeadlineLabel,
  formatHistoryAmerican, formatHistoryLine,
} from './lineHistory.ts';

const KICK = '2026-10-06T00:00:00.000Z';
const CREATED = '2026-10-06T00:06:00.000Z';
const late = lineHistoryWindow({ commenceTime: KICK, createdAt: CREATED, isLive: false });
eq(late, { until: CREATED }, 'cap is the lock, not the earlier commence');
if (late.from != null) throw new Error('non-live window is inverted');
if (Date.parse(late.until) < Date.parse(KICK)) throw new Error('negative window');
const rows = [
  { snapshot_at: '2026-10-05T23:40:00.000Z', home_price: 100, away_price: -120 },
  { snapshot_at: '2026-10-05T23:59:00.000Z', home_price: 105, away_price: -125 },
  { snapshot_at: CREATED, home_price: 100, away_price: -120 },
  { snapshot_at: '2026-10-06T00:06:30.000Z', home_price: 400, away_price: -500 },
  { snapshot_at: '2026-10-06T01:20:00.000Z', home_price: 1400, away_price: -2500 },
];
const read = async (probe) => {
  let xs = rows.filter((r) => {
    if (probe.unbounded) return true;
    const t = Date.parse(r.snapshot_at);
    if (probe.gte && t < Date.parse(probe.gte)) return false;
    if (probe.lt && t >= Date.parse(probe.lt)) return false;
    if (probe.lte && t > Date.parse(probe.lte)) return false;
    return true;
  });
  xs.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));
  if (!probe.ascending) xs.reverse();
  return xs.slice(0, probe.limit);
};
const capped = await sampleOpenToNow(read, late);
if (capped.rows.some((r) => Date.parse(r.snapshot_at) > Date.parse(CREATED))) {
  throw new Error('a row after the lock reached the card');
}
if (capped.rows.some((r) => r.home_price === 1400 || r.home_price === 400)) {
  throw new Error('in-play price reached the card');
}
if (!capped.rows.some((r) => r.home_price === 105)) {
  throw new Error('open-through-lock dropped the pregame row');
}
const closeRow = capped.rows[capped.rows.length - 1];
eq(closeRow.snapshot_at, CREATED, 'close is the lock row');
eq(closeRow.home_price, 100, 'the pick price stays');
eq(historyTimeLabel('8:00 PM', { atCloseLast: true, bounded: false }), 'Close', 'close label');

const liveWindow = lineHistoryWindow({ commenceTime: KICK, createdAt: CREATED, isLive: true });
eq(liveWindow, { from: CREATED }, 'true live');
const live = await sampleOpenToNow(read, liveWindow);
eq(live.rows[live.rows.length - 1].home_price, 1400, 'live may pass the start');
if (live.rows.some((r) => Date.parse(r.snapshot_at) < Date.parse(CREATED))) {
  throw new Error('live read started before the lock');
}
eq(historyTimeLabel('9:20 PM', { atCloseLast: false, atFinalLast: true, bounded: false }), 'Final', 'final row');
eq(inPlayMovementLabel(), 'In-play prices since your pick', 'neutral verdict');

const span = collapseLineHistory([
  { at: '2026-10-05T00:21:00.000Z', line: 3.5, price: -112 },
  { at: '2026-10-05T04:00:00.000Z', line: 4, price: -113 },
]);
eq(span.map((r) => r.label), ['10/4 8:21 PM', '10/5 12:00 AM'], 'date when the series crosses midnight');
eq(
  historyRowAccessibilityLabel({
    marker: span[0].label, at: span[0].at, line: 3.5, price: -112, showLine: true, signedLine: true,
  }),
  'Changed by October 4 at 8:21 PM: line plus 3.5, price minus 112',
  'row label',
);
eq(
  historyRowAccessibilityLabel({
    marker: 'by 10/4 8:21 PM', at: span[0].at, line: 3.5, price: -112, showLine: true, signedLine: true,
  }),
  'No later than October 4 at 8:21 PM: line plus 3.5, price minus 112',
  'upper bound spoken',
);
eq(
  historyRowAccessibilityLabel({
    marker: '8:21:12 PM', at: '2026-10-05T00:21:12.000Z', line: 8.5, price: -110, showLine: true, signedLine: false,
  }),
  'Changed by October 4 at 8:21:12 PM: line 8.5, price minus 110',
  'seconds and unsigned line',
);
eq(
  historyRowAccessibilityLabel({
    marker: 'Close', at: span[1].at, line: 4, price: -113, showLine: true, signedLine: true,
  }),
  'Close: line plus 4, price minus 113',
  'close label spoken',
);
eq(
  movementHeadlineLabel({ kind: 'price', lock: 100, end: 1400, atClose: false }),
  'Price plus 100 to plus 1400',
  'headline spoken',
);
eq(
  movementHeadlineLabel({ kind: 'line', lock: 47.5, end: 48, atClose: false, signedLine: false }),
  'Line 47.5 to 48',
  'unsigned total',
);
eq(formatHistoryAmerican(-110), '\u2212' + '110', 'minus price');
eq(formatHistoryAmerican(null), '\u2014', 'missing price');
eq(formatHistoryLine(3.5, true), '+3.5', 'signed line');
eq(formatHistoryLine(-4, true), '\u2212' + '4', 'negative line');
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
    assert "teamScoringUnitSpoken(game.sport)" in screen
    assert "countThisSeason(homeTrends.games, game.season)" in screen
    assert "countThisSeason(awayTrends.games, game.season)" in screen
    assert "useTeamTrends('NFL'" not in screen, "NCAAF uses the same strip; the sport comes from the game"
    strip = _read(STRIP)
    assert "toFixed(1)} R`" not in strip, "the team average was hardcoded as runs"
    assert "${t.avg.toFixed(1)} ${unit}" in strip
    # The fifth column is the last 25 games in that sport, not the season.
    # Player mode keeps "Season": its window is 25 or 50 depending on sport.
    assert "mode === 'team' && k.key === 'season' ? 'L25'" in strip
    assert "label: 'Season'" in strip
    assert "teamCellAccessibilityLabel(" in strip
    assert "teamGamesRow(" not in strip
    assert "teamShortWindowNote(" in strip
    assert "teamSeasonNote(" in strip
    assert "accessible={mode === 'team'}" in strip
    assert strip.count("textAlign: 'center'") >= 4
    assert "season: g.season" in hook


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_scoring_unit_is_points_for_football_and_runs_for_baseball(tmp_path):
    script = PRELUDE + """
import { teamScoringUnit, teamScoringUnitSpoken, teamShortWindowNote, teamSeasonNote, teamCellAccessibilityLabel, countThisSeason } from './teamForm.ts';
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
eq(teamShortWindowNote({ l3: 0, l5: 0, l10: 0, l20: 0, l25: 0 }), null, 'no data is not 0 games');
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 20, l25: 25 }), null, 'a full window hides the count');
eq(teamShortWindowNote({ l3: 3, l5: 4, l10: 4, l20: 4, l25: 4 }), 'Only 4 games so far. L5–L25 all use those 4.', 'short window');
eq(teamShortWindowNote({ l3: 1, l5: 1, l10: 1, l20: 1, l25: 1 }), 'Only 1 game so far. L3–L25 all use that 1.', 'one game');
eq(teamShortWindowNote({ l3: 3, l5: 5, l10: 10, l20: 20, l25: 20 }), 'Only 20 games so far. L25 uses those 20.', 'only L25 is short');
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
  'Last 5 games, including earlier seasons: won 50 percent, 3.2 goals a game',
  'short count is not in the cell label',
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


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_partial_history_footer_does_not_quote_the_sample_as_the_book(tmp_path):
    """62 sampled rows are not 62 snapshots of the book. The complete-history
    footer is unchanged."""
    script = PRELUDE + """
import { changesFooter } from './lineHistory.ts';
const partial = changesFooter({ changes: 11, shownChanges: 8, hidden: 3 }, 62, true);
if (partial.includes('62')) throw new Error('partial footer quotes the sample size: ' + partial);
eq(partial, "Last 8 changes shown · brief moves between samples may be missing", 'partial cut');
const partialAllShown = changesFooter({ changes: 8, shownChanges: 8, hidden: 1 }, 62, true);
if (partialAllShown.includes('62')) throw new Error(partialAllShown);
eq(partialAllShown, "8 changes · brief moves between samples may be missing", 'partial, table not cut');
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

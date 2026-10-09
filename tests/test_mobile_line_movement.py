"""The line-movement card shows the line since the pick, not the oldest 50
snapshots (2026-10-09).

The card read the OLDEST 50 snapshots of a market at the pick's book and
called the last of them "now". On pick 3350315 (CIN @ MIA Under 42.5 at
Fanatics) that was a 42.5 from 2026-10-06, the day before the pick, while
Fanatics had moved to 43.0: the card said "steady". Now:

- game lines (odds): every stamp is UTC, so the server cuts the window: the
  last pre-game snapshot before the pick's second, then the newest 50 from
  that second up to the start, in-play rows excluded;
- props (player_prop_odds): a third of the rows are stamped in Eastern time,
  so text order is not time order. The whole series comes back, never ordered
  or filtered by snapshot_at on the server, and is sorted and cut on the
  phone. The player page reads the same series: its opening line is the true
  earliest row and its fallback "now" the true latest;
- the first row is the book's price when the pick was made ("At pick");
- a pick made after the start (a live pick) has no pre-game line: no card;
- after the start the card says "by game time", not "now".

The pure helpers run under node's type stripping (CI sets up node 22); the
wiring is pinned structurally.
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
CARD = SRC / "components" / "LineMovementCard.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    m = re.search(rf"export async function {name}\(.*?\n\}}\n", src, re.S)
    assert m, f"{name} is missing from queries.ts"
    return m.group(0)


def _node_strips_types() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)


def _run(tmp_path: Path, script: str) -> subprocess.CompletedProcess:
    """lineHistory.ts and its one import, with node-resolvable relative imports."""
    for name in ("lineHistory.ts", "format.ts"):
        src = re.sub(r"from '\./(\w+)';", r"from './\1.ts';", _read(LIB / name))
        (tmp_path / name).write_text(src, encoding="utf-8")
    return subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )


PRELUDE = """
import { byTime, changesFooter, collapseLineHistory, gameStartAt, HISTORY_ROWS, pickedBeforeStart, recentChanges, sincePick, utcSecond } from './lineHistory.ts';
const eq = (got, want, what) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
const row = (at, total_line) => ({ snapshot_at: at, total_line });
// Pick 3350315's shape: picks.created_at is the Postgres text form (a space,
// six digits, a bare +00); the game starts 2026-10-11 17:00 UTC.
const PICK = '2026-10-07 18:00:15.889355+00';
const START = '2026-10-11T17:00:00+00:00';
"""

node = pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")


@node
def test_the_window_runs_from_the_price_at_the_pick_to_the_start(tmp_path):
    script = PRELUDE + """
const rows = [
  row('2026-10-06T17:16:58Z', 42.5),               // the old card's "now" (the 50th-oldest)
  row('2026-10-07T17:16:56Z', 42.5),               // the snapshot the pick was scored from
  row('2026-10-08T13:16:57.123456+00:00', 43),
  row('2026-10-09T13:16:56Z', 43),                 // the latest pre-game snapshot
  row('2026-10-11T17:05:00Z', 44),                 // an "open" row after the start
];
const open = sincePick(rows, PICK, START, HISTORY_ROWS, Date.parse('2026-10-09T14:00:00Z'));
eq(open.rows.map((r) => r.snapshot_at), ['2026-10-07T17:16:56Z', '2026-10-08T13:16:57.123456+00:00', '2026-10-09T13:16:56Z'], 'price at the pick, then everything since, up to the start');
eq([open.fromPick, open.closed], [true, false], 'from the pick; the game has not started');
const shut = sincePick(rows, PICK, START, HISTORY_ROWS, Date.parse('2026-10-11T20:00:00Z'));
eq([shut.rows.at(-1).total_line, shut.closed], [43, true], 'after the start the last row is the last pre-game price');
// A pick made minutes ago: only the snapshot it was scored from. One row, not
// an empty card (a window that began AT the pick would hide most NHL props).
eq(sincePick(rows.slice(0, 2), PICK, START).rows.map((r) => r.total_line), [42.5], 'price at the pick alone');
// Inside the pick's second: a row stamped before the pick is the price at it.
const sameSecond = sincePick([row('2026-10-07T17:00:00Z', 42.5), row('2026-10-07T18:00:15.3+00:00', 42)], PICK, START);
eq([sameSecond.rows.length, sameSecond.rows[0].total_line, sameSecond.fromPick], [1, 42, true], 'same second, before the pick');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_a_pick_made_after_the_start_has_no_window(tmp_path):
    """Live picks (pick 3366092: made 00:27, game started 23:05 the day before)
    have no pre-game line since the pick, so the card hides."""
    script = PRELUDE + """
const live = '2026-10-08 00:27:18.40531+00';
const kick = '2026-10-07T23:05:00+00:00';
eq(pickedBeforeStart(live, kick), false, 'live pick');
eq(sincePick([row('2026-10-07T22:00:00Z', 50), row('2026-10-08T00:20:00Z', 52)], live, kick).rows, [], 'no rows');
eq(pickedBeforeStart(PICK, START), true, 'pre-game pick');
eq(pickedBeforeStart(PICK, null), true, 'an unknown start does not hide the card');
eq(pickedBeforeStart('not a time', START), false, 'an unreadable pick time hides it');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_too_many_snapshots_keeps_the_newest_and_says_so(tmp_path):
    """NFL DraftKings spreads post every minute (5,558 rows in one pick's
    window). The newest are kept; the first row is then not the price at the
    pick, and fromPick says so."""
    script = PRELUDE + """
const minute = (i) => new Date(Date.parse('2026-10-08T00:00:00Z') + i * 60000).toISOString();
const many = [row('2026-10-07T17:00:00Z', 42.5), ...Array.from({ length: 60 }, (_, i) => row(minute(i), 43))];
const cut = sincePick(many, PICK, START, 50);
eq([cut.rows.length, cut.fromPick, cut.rows[0].snapshot_at, cut.rows.at(-1).snapshot_at], [50, false, minute(10), minute(59)], 'newest 50');
const fits = sincePick(many.slice(0, 50), PICK, START, 50);
eq([fits.rows.length, fits.fromPick, fits.rows[0].total_line], [50, true, 42.5], 'price at the pick + 49 since fits');
eq(HISTORY_ROWS, 50, 'cap');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_prop_stamps_in_eastern_time_sort_and_cut_by_the_instant(tmp_path):
    """player_prop_odds mixes "...-04:00" (MLB, WNBA, NBA, NCAAF writers) with
    UTC (NFL, NHL, and the historical backfill). Text order puts 18:30-04:00
    (22:30 UTC) before 21:00Z; a text bound of 22:00 drops it."""
    script = PRELUDE + """
const props = [
  { snapshot_at: '2026-08-25T18:30:00.000000-04:00', line: 5.5 },   // 22:30 UTC
  { snapshot_at: '2026-08-25T19:45:00.000000-04:00', line: 6.5 },   // 23:45 UTC
  { snapshot_at: '2026-08-25T21:00:00Z', line: 5 },                 // backfilled, UTC
  { snapshot_at: '2026-08-25T23:00:00Z', line: 6 },
];
eq(byTime(props).map((r) => r.line), [5, 5.5, 6, 6.5], 'sorted by the instant, not the text');
const w = sincePick(props, '2026-08-25 22:00:00.5+00', '2026-08-26T00:10:00+00:00');
eq(w.rows.map((r) => r.line), [5, 5.5, 6, 6.5], 'the Eastern rows after the pick are in the window');
eq(w.fromPick, true, 'from the pick');
// November: the Eastern writer stamps -05:00. 20:00-05:00 is 01:00 UTC.
eq(byTime([{ snapshot_at: '2026-11-02T20:00:00-05:00' }, { snapshot_at: '2026-11-03T00:30:00Z' }]).map((r) => r.snapshot_at),
   ['2026-11-03T00:30:00Z', '2026-11-02T20:00:00-05:00'], 'standard time');
eq(byTime([{ snapshot_at: 'garbage' }, { snapshot_at: '2026-10-07 18:00:15.889355+00' }]).length, 1, 'an unreadable stamp is dropped');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_the_server_bound_is_utc_to_the_second(tmp_path):
    """The game-line reads compare snapshot_at as text. A 19-character UTC
    bound sorts before every UTC shape stamped in its second ("Z", "+00:00",
    "....ffffff+00:00") and after every shape in the second before it."""
    script = PRELUDE + """
eq(utcSecond(PICK), '2026-10-07T18:00:15', 'floored, 19 characters');
eq(utcSecond('2026-10-07T14:00:15-04:00'), '2026-10-07T18:00:15', 'any offset becomes UTC');
eq(utcSecond(null), null, 'nothing');
const b = utcSecond('2026-10-07T18:00:15.9Z');
for (const s of ['2026-10-07T18:00:15Z', '2026-10-07T18:00:15+00:00', '2026-10-07T18:00:15.000001+00:00']) if (!(s >= b)) throw new Error(`${s} sorts before ${b}`);
for (const s of ['2026-10-07T18:00:14Z', '2026-10-07T18:00:14+00:00', '2026-10-07T18:00:14.999999+00:00']) if (!(s < b)) throw new Error(`${s} sorts after ${b}`);
// Pick 3359501: games.commence_time 02:10, picks.game_time 02:00 -> 02:00.
eq(gameStartAt('2026-10-08T02:10:00+00:00', '2026-10-08T02:00:00+00:00'), '2026-10-08T02:00:00.000Z', 'the earlier start');
eq(gameStartAt(null, '2026-10-07T22:10:00+00:00'), '2026-10-07T22:10:00.000Z', 'no games row');
eq(gameStartAt(null, undefined), null, 'unknown');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_the_first_row_is_the_price_at_the_pick_not_the_opener(tmp_path):
    script = PRELUDE + """
const pts = [{ at: '2026-10-07T17:16:56Z', line: 42.5, price: -105 }, { at: '2026-10-08T13:16:57.123456+00:00', line: 43, price: -110 }];
eq(recentChanges(pts, 8, true).rows.map((r) => r.label), ['At pick', '9:16 AM ET'], 'price at the pick');
eq(recentChanges(pts, 8, false).rows[0].label, '1:16 PM ET', 'only the newest held: a time, not "At pick"');
// A partial first point is skipped; the first row is then after the pick.
const partial = collapseLineHistory([{ ...pts[0], price: null }, pts[1], { at: '2026-10-08T14:00:00Z', line: 43.5, price: -110 }], true);
eq(partial[0].label, '9:16 AM ET', 'partial first point');
eq(changesFooter({ changes: 8, shownChanges: 8, hidden: 1 }, 9, true), '8 changes since your pick · 9 snapshots', 'every change shown');
eq(changesFooter({ changes: 19, shownChanges: 8, hidden: 12 }, 120, true), 'Last 8 of 19 changes since your pick · 120 snapshots', 'cut');
eq(changesFooter({ changes: 19, shownChanges: 8, hidden: 12 }, 50, false), 'Last 8 of 19 changes in the newest 50 snapshots', 'newest only');
for (const f of [true, false]) if (/opening/.test(changesFooter({ changes: 8, shownChanges: 8, hidden: 1 }, 9, f))) throw new Error('the first row is not the opener');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


def test_game_line_history_is_windowed_on_the_server():
    body = _fn(_read(QUERIES), "fetchOddsHistory")
    assert "ascending: true" not in body, "the oldest 50 snapshots are not the line since the pick"
    assert ".from('odds')" in body
    assert ".neq('snapshot_type', 'in_play')" in body
    assert "utcSecond(pickAt)" in body and "utcSecond(startAt)" in body
    assert ".gte('snapshot_at', from)" in body and ".lt('snapshot_at', until)" in body
    assert ".lt('snapshot_at', from).order('snapshot_at', { ascending: false }).limit(1)" in body
    assert ".order('snapshot_at', { ascending: false }).limit(HISTORY_ROWS)" in body
    assert "return byTime(" in body


def test_prop_history_is_never_ordered_or_filtered_by_snapshot_at_on_the_server():
    body = _fn(_read(QUERIES), "fetchPropOddsHistory")
    assert ".from('player_prop_odds')" in body
    assert not re.search(r"\.(order|gte|gt|lte|lt|eq|neq|filter|range|or)\(\s*'snapshot_at'", body), (
        "Eastern-time rows make snapshot_at's text order hours off its time order"
    )
    assert ".limit(50)" not in body and "ascending: true" not in body
    assert ".order('prop_id', { ascending: false })" in body
    assert "return byTime(" in body


def test_stamps_are_parsed_never_new_date():
    """Hermes rejects six-digit fractions and the space form; parseStamp trims both."""
    lib = _read(LIB / "lineHistory.ts")
    assert "import { parseStamp } from './format';" in lib
    assert "new Date(at)" not in lib
    assert re.search(r"function stamp\(at: string, seconds: boolean\): string \{\s*const d = parseStamp\(at\);", lib)


def test_the_card_windows_from_the_pick_to_the_start():
    card = _read(CARD)
    assert "const startAt = gameStartAt(commenceTime, pick.game_time);" in card
    assert "!pickedBeforeStart(pick.created_at, startAt)" in card
    assert "fetchPropOddsHistory(pick.game_id, market, playerName!, historyBook)" in card
    assert "fetchOddsHistory(pick.game_id, market, historyBook, pick.created_at, startAt)" in card
    assert "setHist(sincePick(rows as Snap[], pick.created_at, startAt))" in card
    assert "const latest = snaps[snaps.length - 1];" in card and "const snaps = hist.rows;" in card
    assert re.search(r"recentChanges\(\s*snaps\.map\(.*?\),\s*8,\s*fromPick,\s*\)", card, re.S)
    assert "changesFooter({ changes, shownChanges, hidden }, snaps.length, fromPick)" in card
    screen = _read(SRC / "screens" / "PickDetailScreen.tsx")
    assert "<LineMovementCard pick={pick} playerName={playerName} commenceTime={game?.commence_time ?? null} />" in screen


def test_after_the_start_the_card_says_by_game_time():
    card = _read(CARD)
    assert "const byGameTime = hist.closed;" in card
    assert "byGameTime ? 'Line steady from pick to game time' : 'Line steady since pick'" in card
    assert "const when = byGameTime ? ' by game time' : '';" in card
    assert "const since = byGameTime ? 'by game time' : 'since scoring';" in card
    assert card.count("${when}`") == 2 and card.count("${since}`") == 2
    assert "byGameTime ? 'moved from your pick to game time' : 'has moved since'" in card
    assert "byGameTime ? 'from your pick to game time' : 'since'" in card


def test_this_file_is_on_the_pr_ci_subset():
    assert "tests/test_mobile_line_movement.py" in _read(ROOT / ".github" / "workflows" / "pr-ci.yml")

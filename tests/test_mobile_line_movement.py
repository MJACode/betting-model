"""The line-movement card shows the line since the pick, not the oldest 50
snapshots (2026-10-09).

The card read the OLDEST 50 snapshots of a market at the pick's book and
called the last of them "now". On pick 3350315 (CIN @ MIA Under 42.5 at
Fanatics) that was a 42.5 from 2026-10-06, the day before the pick, while
Fanatics had moved to 43.0: the card said "steady". Now:

- game lines (odds): every stamp is UTC, so the server cuts the window: the
  last pre-game snapshot before the pick's second, then the newest 50 from
  that second up to the start, in-play rows excluded;
- props (player_prop_odds): about half of the rows are stamped in Eastern
  time, so text order is not time order. The whole series comes back, never ordered
  or filtered by snapshot_at on the server, and is sorted and cut on the
  phone. The player page reads the same series: its opening line is the true
  earliest row and its fallback "now" the true latest;
- the first row is the book's price when the pick was made ("At pick").

The review of that change (same day) added:

- when more snapshots follow the pick than the card holds, the price at the
  pick stays first, a divider row marks the dropped stretch, and the footer
  names it instead of counting changes it cannot see;
- "At pick" only when that row is the number the pick locked;
- "No new price from <book>" when nothing came after the pick, and an
  "As of" time on every card;
- after the start the verdict is not graded (the Closing Line Value card
  grades the number against the close);
- only a live pick loses the card; a pre-game pick made after the start the
  card computes (an NHL start moved earlier at settlement) reads the last
  pre-game price;
- day labels when the rows cross midnight, signed spread rows, a "Time (ET)"
  column heading.

The pure helpers and the card's text (lib/lineMovementView) run under node's
type stripping (CI sets up node 22); the wiring is pinned structurally.
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
VIEW = LIB / "lineMovementView.ts"

# lineHistory.ts and its one import.
HISTORY_FILES = ["lineHistory.ts", "format.ts"]
# lib/lineMovementView.ts and everything it imports (markets.ts pulls in the rest).
VIEW_FILES = HISTORY_FILES + [
    "lineMovementView.ts", "markets.ts", "thresholds.ts", "thresholds.generated.ts",
    "decisionPrice.ts", "discordPublish.ts", "clvBet.ts",
]


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


def _run(tmp_path: Path, script: str, files: list[str] = HISTORY_FILES) -> subprocess.CompletedProcess:
    """Copy lib modules with node-resolvable relative imports, then run `script`."""
    for name in files:
        src = re.sub(r"from '\./([\w.]+)';", r"from './\1.ts';", _read(LIB / name))
        (tmp_path / name).write_text(src, encoding="utf-8")
    return subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
    )


PRELUDE = """
import { byTime, changesFooter, collapseLineHistory, gameStartAt, HISTORY_ROWS, historyFrom, recentChanges, sincePick, utcSecond } from './lineHistory.ts';
const eq = (got, want, what) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
const row = (at, total_line) => ({ snapshot_at: at, total_line });
// Pick 3350315's shape: picks.created_at is the Postgres text form (a space,
// six digits, a bare +00); the game starts 2026-10-11 17:00 UTC.
const PICK = '2026-10-07 18:00:15.889355+00';
const START = '2026-10-11T17:00:00+00:00';
"""

# Picks as the app reads them (PostgREST returns numeric columns as numbers).
VIEW_PRELUDE = PRELUDE + """
import { lineMovementView } from './lineMovementView.ts';
import { formatLineValue, snapshotMatchesLock } from './markets.ts';
const at = (iso) => Date.parse(iso);
const tot = (snapshot_at, total_line, over_price = -110, under_price = -110) => ({ snapshot_at, total_line, over_price, under_price });
const sp = (snapshot_at, spread_home, home_price, away_price) => ({ snapshot_at, spread_home, home_price, away_price });
// Pick 3133024: NE @ BUF Under 49 at Fanatics, made 10-02 13:00 UTC, start 10-04 17:00 UTC.
// Fanatics read 49 at the pick and 49.5 at its last pre-game snapshot (read-only SQL, 2026-10-09).
const NE_BUF = {
  pick_id: 3133024, game_id: 'NFL_2026_04_NE_BUF', model_id: 'nfl_wind_totals', sport: 'NFL',
  game_date: '2026-10-04', pick_side: 'under', signal_type: 'BET', is_live: false,
  pick_label: 'NE @ BUF Under 49 (Wind 11 mph, fanatics) · 1.01u',
  dk_odds: -110, scored_line: 49, decision_odds: null, decision_edge: null, decision_book: null, line_book: null,
  created_at: '2026-10-02 13:00:17.293434+00', game_time: '2026-10-04T17:00:00+00:00',
};
const NE_BUF_ROWS = [tot('2026-10-02T12:17:20Z', 49), tot('2026-10-03T12:17:20Z', 49), tot('2026-10-04T16:24:04Z', 49.5)];
// An MLB total priced at DraftKings (pick 3389399's shape: CWS vs CLE Under 7 at +104).
const MLB = {
  pick_id: 3389399, game_id: 'MLB_2026-10-08_CLE_CWS', model_id: 'mlb_over_under', sport: 'MLB',
  game_date: '2026-10-08', pick_side: 'under', signal_type: 'BET', is_live: false, pick_label: 'CWS vs CLE Under 7.0',
  dk_odds: 104, scored_line: 7, decision_odds: 104, decision_edge: 0.05, decision_book: 'draftkings', line_book: null,
  created_at: '2026-10-08 13:17:39.703358+00', game_time: '2026-10-09T00:00:00+00:00',
};
const view = (pick, rows, market, nowIso, isProp = false) =>
  lineMovementView(pick, sincePick(rows, historyFrom(pick, pick.game_time), pick.game_time, HISTORY_ROWS, at(nowIso)), market, isProp);
const GRADED = /favor|against/i;
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
eq([open.fromPick, open.gap, open.since, open.closed], [true, false, 2, false], 'from the pick; nothing dropped; two since; not started');
const shut = sincePick(rows, PICK, START, HISTORY_ROWS, Date.parse('2026-10-11T20:00:00Z'));
eq([shut.rows.at(-1).total_line, shut.closed], [43, true], 'after the start the last row is the last pre-game price');
// A pick made minutes ago: only the snapshot it was scored from. One row, not
// an empty card (a window that began AT the pick would hide most NHL props),
// and `since` says nothing came after it.
const fresh = sincePick(rows.slice(0, 2), PICK, START);
eq([fresh.rows.map((r) => r.total_line), fresh.fromPick, fresh.since], [[42.5], true, 0], 'price at the pick alone');
// Inside the pick's second: a row stamped before the pick is the price at it.
const sameSecond = sincePick([row('2026-10-07T17:00:00Z', 42.5), row('2026-10-07T18:00:15.3+00:00', 42)], PICK, START);
eq([sameSecond.rows.length, sameSecond.rows[0].total_line, sameSecond.fromPick], [1, 42, true], 'same second, before the pick');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_only_a_live_pick_loses_the_card(tmp_path):
    """Live picks (pick 3366092: made 00:27, game started 23:05 the day
    before) have no card. A pre-game pick made after the start the card
    computes reads the last price before the start: an NHL game's start moves
    about ten minutes earlier when it is settled, and the card used to vanish
    from those picks once the result was in."""
    script = PRELUDE + """
const live = { is_live: true, created_at: '2026-10-08 00:27:18.40531+00' };
const kick = '2026-10-07T23:05:00+00:00';
eq(historyFrom(live, kick), null, 'a live pick has no card');
const late = { is_live: false, created_at: '2026-10-08 00:27:18.40531+00' };
eq(historyFrom(late, kick), '2026-10-07T23:05:00.000Z', 'a pre-game pick after the start reads from the start');
const w = sincePick([row('2026-10-07T22:00:00Z', 50), row('2026-10-07T23:00:00Z', 51), row('2026-10-07T23:20:00Z', 52)], historyFrom(late, kick), kick, HISTORY_ROWS, Date.parse('2026-10-08T03:00:00Z'));
eq([w.rows.map((r) => r.total_line), w.fromPick, w.since, w.closed], [[51], true, 0, true], 'the last pre-game price, as the price at the pick');
// The clamp holds inside sincePick too: a pick time after the start reads as the start.
eq(sincePick([row('2026-10-07T23:00:00Z', 51)], late.created_at, kick).rows.length, 1, 'sincePick clamps');
eq(historyFrom({ is_live: false, created_at: PICK }, START), '2026-10-07T18:00:15.889Z', 'a pick before the start reads from the pick');
eq(historyFrom({ is_live: null, created_at: PICK }, null), '2026-10-07T18:00:15.889Z', 'an unknown start does not hide the card');
eq(historyFrom({ is_live: false, created_at: 'not a time' }, START), null, 'an unreadable pick time hides it');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_too_many_snapshots_keep_the_price_at_the_pick_and_mark_the_gap(tmp_path):
    """NFL DraftKings spreads post every minute (5,558 rows in one pick's
    window). The price at the pick stays first; after it, the newest 49; and
    `gap` says snapshots in between were dropped."""
    script = PRELUDE + """
const minute = (i) => new Date(Date.parse('2026-10-08T00:00:00Z') + i * 60000).toISOString();
const many = [row('2026-10-07T17:00:00Z', 42.5), ...Array.from({ length: 60 }, (_, i) => row(minute(i), 43))];
const cut = sincePick(many, PICK, START, 50);
eq([cut.rows.length, cut.fromPick, cut.gap, cut.since], [50, true, true, 60], 'price at the pick + newest 49');
eq([cut.rows[0].snapshot_at, cut.rows[1].snapshot_at, cut.rows.at(-1).snapshot_at], ['2026-10-07T17:00:00Z', minute(11), minute(59)], 'which rows');
const fits = sincePick(many.slice(0, 50), PICK, START, 50);
eq([fits.rows.length, fits.fromPick, fits.gap, fits.rows[0].total_line], [50, true, false, 42.5], 'price at the pick + 49 since fits');
// No snapshot at or before the pick (a capped prop series): the newest 50, and
// the window says it does not start at the pick.
const none = sincePick(many.slice(1), PICK, START, 50);
eq([none.rows.length, none.fromPick, none.gap, none.rows[0].snapshot_at], [50, false, true, minute(10)], 'no price at the pick');
eq(sincePick(many, PICK, START, 1).rows.map((r) => r.total_line), [42.5], 'a cap of 1 keeps only the price at the pick');
eq(HISTORY_ROWS, 50, 'cap');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_no_run_crosses_the_gap_and_the_footer_names_it(tmp_path):
    """The price at the pick equal to the newest price used to read as one
    unbroken run with nothing in between. With a gap, a divider row sits
    between them and the footer names the missing stretch. It never claims
    "since your pick" for a table that does not run from it, and never counts
    snapshots."""
    script = PRELUDE + """
const pts = [
  { at: '2026-10-07T17:16:56Z', line: 7.5, price: -110 },
  { at: '2026-10-09T14:34:00Z', line: 7.5, price: -110 },
  { at: '2026-10-09T14:40:00Z', line: 8, price: -110 },
];
const merged = recentChanges(pts, 8, { atPick: true });
eq(merged.rows.map((r) => r.label), ['At pick', 'Fri 10:40 AM'], 'without a gap the same price is one run');
const cut = recentChanges(pts, 8, { atPick: true, gap: true });
eq(cut.rows.map((r) => [r.label, r.divider, r.baseline]), [['At pick', false, true], ['Earlier changes not shown', true, false], ['Fri 10:34 AM', false, true], ['Fri 10:40 AM', false, false]], 'divider; the run restarts after it');
eq(new Set(cut.rows.map((r) => r.key)).size, 4, 'unique keys');
eq([cut.changes, cut.shownChanges], [1, 1], 'only the move after the divider is a known change');
const footer = changesFooter(cut, { fromPick: true, gap: true });
eq(footer, 'Changes between your pick and Fri, 10/9, 10:34 AM ET not shown', 'gap footer');
// Eight rows on screen: the first row on screen, not the one after the divider, bounds the missing stretch.
const long = [pts[0], ...Array.from({ length: 12 }, (_, i) => ({ at: `2026-10-09T15:${String(10 + i).padStart(2, '0')}:00Z`, line: 7.5 + (i % 2) / 2, price: -110 }))];
const tail = recentChanges(long, 8, { atPick: true, gap: true });
eq(changesFooter(tail, { fromPick: true, gap: true }), `Changes between your pick and Fri, 10/9, 11:14 AM ET not shown`, 'screen-cut gap footer');
const noPick = changesFooter(recentChanges(pts.slice(1), 8), { fromPick: false, gap: true });
eq(noPick, "1 change since Fri, 10/9, 10:34 AM ET. The price at your pick isn't available.", 'no price at the pick');
for (const f of [footer, noPick]) if (/since your pick|snapshot/.test(f)) throw new Error(`claims the table runs from the pick: ${f}`);
eq(changesFooter(merged, { fromPick: true, gap: false }), '1 change since your pick', 'no gap: a total since the pick');
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
const pts = [{ at: '2026-10-07T17:16:56Z', line: 42.5, price: -105 }, { at: '2026-10-07T23:16:57.123456+00:00', line: 43, price: -110 }];
eq(recentChanges(pts, 8, { atPick: true }).rows.map((r) => r.label), ['At pick', '7:16 PM'], 'price at the pick');
eq(recentChanges(pts, 8).rows[0].label, '1:16 PM', 'not the pick: a time, not "At pick"');
// A partial first point is skipped; the first row is then after the pick.
const partial = collapseLineHistory([{ ...pts[0], price: null }, pts[1], { at: '2026-10-07T23:40:00Z', line: 43.5, price: -110 }], { atPick: true });
eq(partial[0].label, '7:16 PM', 'partial first point');
const nine = { rows: [], changes: 8, shownChanges: 8, hidden: 1, firstAt: pts[0].at };
eq(changesFooter(nine, { fromPick: true, gap: false }), '8 changes since your pick', 'every change shown');
eq(changesFooter({ ...nine, changes: 19, hidden: 12 }, { fromPick: true, gap: false }), 'Last 8 of 19 changes since your pick', 'cut');
for (const w of [{ fromPick: true, gap: false }, { fromPick: false, gap: false }, { fromPick: true, gap: true }]) {
  if (/opening/.test(changesFooter(nine, w))) throw new Error('the first row is not the opener');
}
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_labels_carry_the_day_when_rows_cross_midnight(tmp_path):
    """A pick made days before an NFL game: "2:17 AM" after "12:16 PM" read as
    the table running backwards. Rows on one Eastern day keep the bare time;
    across midnight they carry the weekday; across more than six days the
    date too (a weekday repeats after seven). "ET" is in the column heading."""
    script = PRELUDE + """
const p = (at, line) => ({ at, line, price: -110 });
const sameDay = collapseLineHistory([p('2026-10-08T14:00:00Z', 42.5), p('2026-10-09T02:00:00Z', 43)]);
eq(sameDay.map((r) => r.label), ['10:00 AM', '10:00 PM'], 'one Eastern day (02:00 UTC is 10 PM the day before)');
const twoDays = collapseLineHistory([p('2026-10-08T16:16:45Z', 42.5), p('2026-10-09T06:17:00Z', 43)], { atPick: true });
eq(twoDays.map((r) => r.label), ['At pick', 'Fri 2:17 AM'], 'across midnight: the weekday');
const week = collapseLineHistory([p('2026-10-01T16:00:00Z', 42.5), p('2026-10-03T06:17:00Z', 43), p('2026-10-09T15:00:00Z', 43.5)]);
eq(week.map((r) => r.label), ['Thu 10/1, 12:00 PM', 'Sat 10/3, 2:17 AM', 'Fri 10/9, 11:00 AM'], 'over six days: the date too');
const sixDays = collapseLineHistory([p('2026-10-03T16:00:00Z', 42.5), p('2026-10-09T15:00:00Z', 43.5)]);
eq(sixDays.map((r) => r.label), ['Sat 12:00 PM', 'Fri 11:00 AM'], 'six days apart: weekdays are still unique');
// Seconds still break a shared minute, with the day.
const clash = collapseLineHistory([p('2026-10-08T16:16:05Z', 42.5), p('2026-10-09T06:17:05Z', 43), p('2026-10-09T06:17:40Z', 43.5)]);
eq(clash.map((r) => r.label), ['Thu 12:16 PM', 'Fri 2:17:05 AM', 'Fri 2:17:40 AM'], 'seconds with the day');
for (const r of [...sameDay, ...twoDays, ...week]) if (/ET$/.test(r.label)) throw new Error(`"ET" is in the heading: ${r.label}`);
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@node
def test_after_the_start_the_verdict_is_not_graded(tmp_path):
    """Pick 3133024 (Under 49 at Fanatics, 49 to 49.5). Before kickoff the
    move reads "in your favor": a bettor gets a better number now. After it,
    the Closing Line Value card on the same screen grades the same move the
    other way (the number taken was worse than the close), so this card says
    where the line went, in grey, and points to that card."""
    script = VIEW_PRELUDE + """
const before = view(NE_BUF, NE_BUF_ROWS, 'totals', '2026-10-04T00:00:00Z');
eq([before.verdict.label, before.verdict.tone], ['Line moved 49 → 49.5 in your favor', 'for'], 'graded before the start');
const after = view(NE_BUF, NE_BUF_ROWS, 'totals', '2026-10-05T00:00:00Z');
eq([after.header, after.verdict.label, after.verdict.tone], ['49 → 49.5', 'Line moved to 49.5 by game time', 'neutral'], 'not graded after it');
if (GRADED.test(after.verdict.label) || /for or against/.test(after.note)) throw new Error(`graded after the start: ${after.verdict.label} / ${after.note}`);
if (!/Closing Line Value/.test(after.note) || !/from your pick to game time/.test(after.note)) throw new Error(after.note);
// A price move (MLB total at DraftKings, +104 to -112) reads as a price, also in grey.
const mlbRows = [tot('2026-10-08T13:10:00Z', 7, -125, 104), tot('2026-10-08T22:00:00Z', 7, -108, -112)];
const priced = view(MLB, mlbRows, 'totals', '2026-10-09T01:00:00Z');
eq([priced.header, priced.verdict.label, priced.verdict.tone], ['+104 → -112', 'Price moved to -112 by game time', 'neutral'], 'price, after the start');
if (/for or against/.test(priced.note)) throw new Error(priced.note);
const pricedBefore = view(MLB, mlbRows, 'totals', '2026-10-08T23:00:00Z');
eq(pricedBefore.verdict.tone, 'against', 'the same move is graded before the start');
if (!/for or against you/.test(pricedBefore.note)) throw new Error(pricedBefore.note);
const steady = view(NE_BUF, [NE_BUF_ROWS[0], NE_BUF_ROWS[1]], 'totals', '2026-10-05T00:00:00Z');
eq([steady.verdict.label, steady.verdict.tone], ['Line steady from pick to game time', 'neutral'], 'steady after the start');
"""
    proc = _run(tmp_path, script, VIEW_FILES)
    assert proc.returncode == 0, proc.stderr


@node
def test_nothing_since_the_pick_reads_no_new_price_with_its_age(tmp_path):
    """A pick made minutes ago, or a book that stopped posting (DraftKings
    NCAAF rows end 2026-09-05 for some 10-24 games): the only row is the
    snapshot the pick was scored from. That is not "steady"; it is no new
    price, and the card says how old the newest price is."""
    script = VIEW_PRELUDE + """
const fresh = view(NE_BUF, [NE_BUF_ROWS[0]], 'totals', '2026-10-02T13:05:00Z');
eq([fresh.header, fresh.verdict.label, fresh.verdict.tone, fresh.asOf], ['49', 'No new price from Fanatics since your pick', 'neutral', 'As of Fri, 10/2, 8:17 AM ET'], 'open');
const shut = view(NE_BUF, [NE_BUF_ROWS[0]], 'totals', '2026-10-05T00:00:00Z');
eq(shut.verdict.label, 'No new price from Fanatics between your pick and game time', 'after the start');
// One snapshot five weeks before the pick and none after it.
const ncaaf = {
  pick_id: 1, game_id: 'NCAAF_2026-10-24_X_Y', model_id: 'ncaaf_spread', sport: 'NCAAF', game_date: '2026-10-24',
  pick_side: 'home', signal_type: 'BET', is_live: false, pick_label: 'X -3.5', dk_odds: -108, scored_line: -3.5,
  decision_odds: -108, decision_edge: 0.04, decision_book: 'draftkings', line_book: null,
  created_at: '2026-10-08 16:00:00.5+00', game_time: '2026-10-24T19:30:00+00:00',
};
const stale = view(ncaaf, [sp('2026-09-05T13:00:00Z', -3.5, -108, -112)], 'spreads', '2026-10-09T12:00:00Z');
eq([stale.header, stale.verdict.label, stale.asOf], ['-108', 'No new price from DraftKings since your pick', 'As of Sat, 9/5, 9:00 AM ET'], 'five weeks old');
if (/steady/i.test(stale.verdict.label)) throw new Error(stale.verdict.label);
// Snapshots after the pick at the same price: the line really was steady.
const held = view(NE_BUF, [NE_BUF_ROWS[0], NE_BUF_ROWS[1]], 'totals', '2026-10-03T13:00:00Z');
eq([held.verdict.label, held.asOf], ['Line steady since pick', 'As of Sat, 10/3, 8:17 AM ET'], 'steady: the newest snapshot dates it');
"""
    proc = _run(tmp_path, script, VIEW_FILES)
    assert proc.returncode == 0, proc.stderr


@node
def test_at_pick_only_when_the_row_is_the_lock(tmp_path):
    """An NFL opener locked TEN +9.5 at -108 while DraftKings' last stored
    snapshot before the pick read +7.5 at -117. That row keeps its time; it
    is not labelled as the pick. NFL picks compare the line only (home to
    home: PHI +6 is stored as -6 on both sides); other picks compare the price
    at the deciding book."""
    script = VIEW_PRELUDE + """
const TEN = {
  pick_id: 2, game_id: 'NFL_2026_06_X_TEN', model_id: 'nfl_opener_spread', sport: 'NFL', game_date: '2026-10-11',
  pick_side: 'home', signal_type: 'BET', is_live: false, pick_label: 'X @ TEN — TEN +9.5 (Opener vs Pinnacle, DK) · 1.00u',
  dk_odds: -108, scored_line: 9.5, decision_odds: null, decision_edge: null, decision_book: null, line_book: null,
  created_at: '2026-10-08 09:09:04.286567+00', game_time: '2026-10-11T17:00:00+00:00',
};
const after = [sp('2026-10-08T09:12:45Z', 9, -109, -112), sp('2026-10-08T14:17:18Z', 7.5, -115, -107)];
const wrong = view(TEN, [sp('2026-10-08T08:16:39Z', 7.5, -117, -105), ...after], 'spreads', '2026-10-08T15:00:00Z');
eq(wrong.rows.map((r) => r.label), ['4:16 AM', '5:12 AM', '10:17 AM'], 'another number keeps its time');
eq(wrong.footer, null, 'still a window from the pick');
const right = view(TEN, [sp('2026-10-08T08:16:39Z', 9.5, -108, -112), ...after], 'spreads', '2026-10-08T15:00:00Z');
eq(right.rows[0].label, 'At pick', 'the locked number reads "At pick"');
// Away spread: PHI +6 is scored_line -6 and spread_home -6.
const PHI = { ...TEN, pick_side: 'away', scored_line: -6, pick_label: 'PHI @ JAX — PHI +6 (Opener -2 vs Pinnacle, DK) · 1.27u' };
eq(snapshotMatchesLock(PHI, sp('x', -6, -108, -112), 'spreads'), true, 'away spread, home to home');
eq(snapshotMatchesLock(PHI, sp('x', 6, -108, -112), 'spreads'), false, 'the other side is another line');
// Not NFL: the price at the deciding book, and the line when it is that book's.
eq(snapshotMatchesLock(MLB, tot('x', 7, -125, 104), 'totals'), true, 'MLB: price and line');
eq(snapshotMatchesLock(MLB, tot('x', 7, -120, 100), 'totals'), false, 'MLB: another price');
eq(snapshotMatchesLock(MLB, tot('x', 7.5, -125, 104), 'totals'), false, 'MLB: another line');
eq(snapshotMatchesLock({ ...MLB, line_book: 'fanduel' }, tot('x', 7.5, -125, 104), 'totals'), true, "another book's line is not compared");
"""
    proc = _run(tmp_path, script, VIEW_FILES)
    assert proc.returncode == 0, proc.stderr


@node
def test_a_cut_table_keeps_the_pick_and_says_what_it_covers(tmp_path):
    """Pick 3350315's shape: more snapshots after the pick than the card
    holds. The price at the pick stays as the first row, a divider follows,
    and neither the footer nor the note says the table runs from the pick."""
    script = VIEW_PRELUDE + """
const WIND = {
  ...NE_BUF, pick_id: 3350315, game_id: 'NFL_2026_05_CIN_MIA', pick_label: 'CIN @ MIA Under 42.5 (Wind 11 mph, fanatics) · 1.00u',
  dk_odds: -105, scored_line: 42.5, created_at: PICK, game_time: START,
};
const hour = (i) => new Date(Date.parse('2026-10-08T13:16:45Z') + i * 3600000).toISOString();
const rows = [tot('2026-10-07T17:16:47Z', 42.5, -115, -105), ...Array.from({ length: 60 }, (_, i) => tot(hour(i), i < 58 ? 42.5 : 43, i < 58 ? -115 : -110, i < 58 ? -105 : -110))];
const v = view(WIND, rows, 'totals', '2026-10-11T12:00:00Z');
eq(v.rows[0].label, 'At pick', 'the price at the pick is kept');
eq(v.rows.filter((r) => r.divider).map((r) => r.label), ['Earlier changes not shown'], 'one divider');
eq(v.rows.filter((r) => !r.divider).map((r) => r.lineText), ['42.5', '42.5', '43'], 'no run crosses the divider');
if (!v.footer || /since your pick|snapshot/.test(v.footer)) throw new Error(`footer: ${v.footer}`);
if (/since your pick|from your pick to game time/.test(v.note)) throw new Error(`note: ${v.note}`);
eq(/when you picked, then its latest prices/.test(v.note), true, 'the note says what the table holds');
// The same pick with everything on the card says "since your pick".
const whole = view(WIND, rows.slice(0, 20), 'totals', '2026-10-11T12:00:00Z');
if (!/since your pick/.test(whole.note)) throw new Error(whole.note);
"""
    proc = _run(tmp_path, script, VIEW_FILES)
    assert proc.returncode == 0, proc.stderr


@node
def test_spread_rows_carry_a_sign_like_the_header(tmp_path):
    script = VIEW_PRELUDE + """
eq([formatLineValue(7.5, 'spreads'), formatLineValue(-3, 'spreads'), formatLineValue(0, 'spreads'), formatLineValue(7.5, 'totals'), formatLineValue(null, 'spreads')],
   ['+7.5', '-3', '0', '7.5', '—'], 'formatLineValue');
const PHI = {
  pick_id: 3262471, game_id: 'NFL_2026_05_PHI_JAX', model_id: 'nfl_opener_spread', sport: 'NFL', game_date: '2026-10-11',
  pick_side: 'away', signal_type: 'BET', is_live: false, pick_label: 'PHI @ JAX — PHI +6 (Opener -2 vs Pinnacle, DK) · 1.27u',
  dk_odds: -112, scored_line: -6, decision_odds: null, decision_edge: null, decision_book: null, line_book: null,
  created_at: '2026-10-05 21:11:02.961433+00', game_time: '2026-10-11T13:30:00+00:00',
};
const v = view(PHI, [sp('2026-10-05T21:00:00Z', -6, -108, -112), sp('2026-10-06T21:00:00Z', -7.5, -110, -110)], 'spreads', '2026-10-07T00:00:00Z');
eq([v.header, v.rows.map((r) => r.lineText)], ['+6 → +7.5', ['+6', '+7.5']], 'away spread rows read like the header');
const t = view(NE_BUF, NE_BUF_ROWS, 'totals', '2026-10-04T00:00:00Z');
eq(t.rows.map((r) => r.lineText), ['49', '49.5'], 'totals unsigned');
"""
    proc = _run(tmp_path, script, VIEW_FILES)
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
    q = _read(QUERIES)
    body = _fn(q, "fetchPropOddsHistory")
    assert ".from('player_prop_odds')" in body
    assert not re.search(r"\.(order|gte|gt|lte|lt|eq|neq|filter|range|or)\(\s*'snapshot_at'", body), (
        "Eastern-time rows make snapshot_at's text order hours off its time order"
    )
    assert ".limit(50)" not in body and "ascending: true" not in body
    assert ".order('prop_id', { ascending: false })" in body
    assert "return byTime(" in body
    # The card finds the price at the pick in this series, and the player page
    # takes its opening line from it: the read must hold the whole series.
    m = re.search(r"const PROP_HISTORY_CAP = (\d+);", q)
    assert m, "the prop history read must have a named cap"
    assert int(m.group(1)) >= 200, (
        "a prop series for the card's markets runs to 174 rows at one book (WNBA, measured 2026-10-09); "
        "a smaller cap drops the price at the pick and the player page's opening line"
    )
    assert ".limit(PROP_HISTORY_CAP)" in body


def test_stamps_are_parsed_never_new_date():
    """Hermes rejects six-digit fractions and the space form; parseStamp trims both."""
    lib = _read(LIB / "lineHistory.ts")
    assert "import { etDate, formatDayTimeET, parseStamp } from './format';" in lib
    assert "new Date(at)" not in lib
    assert re.search(
        r"function stamp\(at: string, seconds: boolean, day: DayPart = 'none'\): string \{\s*const d = parseStamp\(at\);",
        lib,
    )
    assert ".map((a) => parseStamp(a))" in lib


def test_the_card_windows_from_the_pick_to_the_start():
    card = _read(CARD)
    assert "const startAt = gameStartAt(commenceTime, pick.game_time);" in card
    # Only a live pick loses the card; the start does not hide a pre-game pick.
    assert "const from = historyFrom(pick, startAt);" in card
    assert "from == null" in card and "pickedBeforeStart" not in card
    assert "fetchPropOddsHistory(pick.game_id, market, playerName!, historyBook)" in card
    assert "fetchOddsHistory(pick.game_id, market, historyBook, from, startAt)" in card
    assert "setHist(sincePick(rows as Snap[], from, startAt))" in card
    assert "lineMovementView(pick, hist, market, isProp)" in card
    screen = _read(SRC / "screens" / "PickDetailScreen.tsx")
    assert "<LineMovementCard pick={pick} playerName={playerName} commenceTime={game?.commence_time ?? null} />" in screen
    view = _read(VIEW)
    assert "const latest = snaps[snaps.length - 1];" in view and "const snaps = hist.rows;" in view
    assert "atPick: hist.fromPick && snapshotMatchesLock(pick, snaps[0], market)," in view
    assert "gap: hist.fromPick && hist.gap," in view
    assert "changesFooter(recent, { fromPick: hist.fromPick, gap: hist.gap })" in view
    assert "const nothingSince = hist.fromPick && hist.since === 0;" in view


def test_the_card_prints_what_the_view_says():
    """The card has no copy of its own: every word comes from
    lib/lineMovementView, which the Node tests above run."""
    card = _read(CARD)
    for needle in ("{view.header}", "{view.verdict.label}", "{view.asOf}", "{view.footer}", "{view.note}",
                   "{r.lineText}", "{r.priceText}", "key={r.key}"):
        assert needle in card, needle
    assert "view.verdict.tone === 'for'" in card and "view.verdict.tone === 'against'" in card
    assert "r.divider ?" in card
    # The time column: "At pick", times and the first kept row are not all
    # changes, and the zone is said once.
    assert ">Time (ET)</Text>" in card
    assert "Changed at" not in card
    for word in ("in your favor", "against you", "steady", "for or against"):
        assert word not in card, f"copy belongs in lib/lineMovementView: {word}"


def test_this_file_is_on_the_pr_ci_subset():
    assert "tests/test_mobile_line_movement.py" in _read(ROOT / ".github" / "workflows" / "pr-ci.yml")

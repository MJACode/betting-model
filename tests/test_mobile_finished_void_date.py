"""Three board fixes from closed draft #846, re-done on current master.

A finished VOID hides Track and Slip. Date chips toggle the selection the
screen is showing. Null-date rows sort last, and the verify script says so.

Over is `gameStartState(...) === 'over'`. That helper already falls back to
the pick's `game_time`. There is no second `gameIsOver`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
LIB = MOBILE / "src" / "lib"

from tests._node import NODE, node_strips_types  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run(tmp_path: Path, files: list[str], script: str) -> subprocess.CompletedProcess:
    for name in files:
        src = _read(LIB / name)
        src = re.sub(r"from '\./(\w+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    return subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )


needs_node = pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")


@needs_node
def test_a_finished_published_void_is_not_open_for_track_or_slip(tmp_path):
    """A published VOID stays actionable until the game is over, then Track
    and Slip go. An unsettled pick stays open so it can still grade. Over is
    the existing gameStartState, including a missing games row."""
    script = r"""
import { openForActionNow } from './discordPublish.ts';
import { gameStartState } from './format.ts';
const publishedVoid = { result: 'NO_ACTION', condition_status: 'VOID', discordPublish: 'published' };
const unsettled = { result: null, condition_status: null, discordPublish: 'published' };
const future = new Date(Date.now() + 3 * 3600000).toISOString();
const hourAgo = new Date(Date.now() - 3600000).toISOString();
const longPast = new Date(Date.now() - 9 * 3600000).toISOString();
const fail = (what) => { throw new Error(what); };
if (openForActionNow(publishedVoid, false) !== true) fail('upcoming void');
if (openForActionNow(publishedVoid, true) !== false) fail('finished void');
if (openForActionNow(unsettled, true) !== true) fail('unsettled stays open');
if (openForActionNow({ ...publishedVoid, discordPublish: 'unpublished' }, false) !== false) fail('unpublished void');
if (gameStartState({ sport: 'UFC', commence_time: future, home_score: 1, away_score: 0 }, null, future) !== 'over') fail('scored');
if (gameStartState(null, null, longPast) !== 'over') fail('missing row, game_time past the window');
if (gameStartState(null, null, future) !== 'pre') fail('missing row, game_time ahead');
if (gameStartState({ sport: 'MLB', commence_time: hourAgo }, null) !== 'live') fail('still inside the window');
const postponed = { abstract_game_state: 'Final', home_score: null, away_score: null };
if (gameStartState({ sport: 'MLB', commence_time: future }, postponed) !== 'postponed') fail('called off is not over');
"""
    proc = _run(tmp_path, ["discordPublish.ts", "format.ts"], script)
    assert proc.returncode == 0, proc.stderr
    card = _read(MOBILE / "src/components/PickCard.tsx")
    detail = _read(MOBILE / "src/screens/PickDetailScreen.tsx")
    publish = _read(LIB / "discordPublish.ts")
    fmt = _read(LIB / "format.ts")
    assert "export function gameIsOver" not in fmt
    assert "once both land" not in fmt
    assert "gameStartState(...) === 'over'" in fmt
    body = publish[publish.index("export function openForActionNow"):]
    body = body[:body.index("\n}")]
    assert "openForAction(p) && (p.result == null || !over)" in body
    for src in (card, detail):
        assert "gameStartState(game, liveState, pick.game_time) === 'over'" in src
        assert "openForActionNow(pick, over)" in src
    assert "const canTrack = Boolean(onToggleTrack) && open && cta.track;" in card
    assert "&& open && !preview && !paused &&" in card
    assert "&& cta.slip;" in card
    assert "(open || pillSilent)" in card
    assert "boardStatus.kind === 'ended'" in card
    assert "const canTrack = openHere;" in detail
    assert "hasPricedLine(pick) && openHere" in detail
    assert "(openHere || detailPillSilent)" in detail


@needs_node
def test_date_chips_toggle_the_selection_shown_on_screen(tmp_path):
    """A chip tap starts from the selection the chips show. A day stored on
    another board, and absent here, does not ride along."""
    script = r"""
import { dateOptionsFor, toggleDateSelection } from './dateFilter.ts';
const TODAY = '2026-09-26';
const tomorrowOpts = dateOptionsFor([TODAY, '2026-09-27'], TODAY);
const sat = new Set(['2026-11-28']);
const fellBack = toggleDateSelection(sat, '2026-09-27', tomorrowOpts);
if (!(fellBack.size === 1 && fellBack.has('2026-09-27') && !fellBack.has('2026-11-28'))) {
  throw new Error('fallback ' + [...fellBack].join(','));
}
const partly = toggleDateSelection(new Set([TODAY, '2026-11-28']), '2026-09-27', tomorrowOpts);
if ([...partly].sort().join(',') !== `${TODAY},2026-09-27,2026-11-28`) {
  throw new Error('partly ' + [...partly].sort().join(','));
}
const off = toggleDateSelection(new Set([TODAY]), TODAY, tomorrowOpts);
if (off.size !== 0) throw new Error('clear ' + off.size);
const input = new Set([TODAY]);
toggleDateSelection(input, '2026-09-27', tomorrowOpts);
if (!(input.size === 1 && input.has(TODAY))) throw new Error('mutated');
const fresh = toggleDateSelection(new Set(), '2026-09-27', tomorrowOpts);
if (!(fresh.size === 1 && fresh.has('2026-09-27'))) throw new Error('empty ' + [...fresh].join(','));
"""
    proc = _run(tmp_path, ["dateFilter.ts", "format.ts"], script)
    assert proc.returncode == 0, proc.stderr
    screen = _read(MOBILE / "src/screens/PicksHomeScreen.tsx")
    assert "setPickedDates((prev) => toggleDateSelection(prev, date, dateOptions))" in screen
    assert "const next = new Set(prev);" not in screen


@needs_node
def test_null_date_rows_sort_last(tmp_path):
    """A row with no game_date sorts after every dated day, under Date TBD,
    and the verify script asserts that full shape."""
    script = r"""
import { rowsByDay } from './dateFilter.ts';
const TODAY = '2026-09-26';
const shape = (rs) => rs.map((r) => (r.kind === 'day' ? `[${r.label}]` : r.item.id)).join(' ');
const tbd = rowsByDay(
  [{ id: 'x', date: null }, { id: 'y', date: TODAY }],
  (p) => p.date, (p) => p.id, () => false, TODAY);
if (shape(tbd) !== '[Today] y [Date TBD] x') throw new Error(shape(tbd));
const mixed = rowsByDay(
  [{ id: 'n1', date: null }, { id: 'sat', date: '2026-11-28' }, { id: 'n2', date: null }, { id: 't', date: TODAY }],
  (p) => p.date, (p) => p.id, () => false, TODAY);
if (shape(mixed) !== '[Today] t [Sat 11/28] sat [Date TBD] n1 n2') throw new Error(shape(mixed));
"""
    proc = _run(tmp_path, ["dateFilter.ts", "format.ts"], script)
    assert proc.returncode == 0, proc.stderr
    verify = _read(MOBILE / "scripts/verify_date_filter.ts")
    assert "tbdShape(tbd) === '[Today] y [Date TBD] x'" in verify
    assert "tbdShape(mixed) === '[Today] t [Sat 11/28] sat [Date TBD] n1 n2'" in verify


def test_the_three_pins_are_on_the_pr_ci_subset():
    yml = _read(ROOT / ".github/workflows/pr-ci.yml")
    assert "tests/test_mobile_finished_void_date.py" in yml

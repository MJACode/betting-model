"""Tap targets and VoiceOver — usability audit PR 4.

H9 (sport selector tabs), M8 (full pick-card label, tab roles), M5 (Sharp
score label), M7 (bottom inset for the floating betslip bar), M9, M10, M18,
M19, M22, M25, M26, L13 and the unlabelled Pressables.

`mobile/scripts/verify_a11y.ts` is the gate: it scans every Pressable,
TextInput and Switch in the app and every vertical list the betslip bar can
cover. It imports only node: modules (plus the pure lib/a11y.ts), so it runs
here under node's type stripping with no node_modules. The pins below guard
the pieces most likely to be undone by a later edit.
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node_strips_types() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)


needs_node = pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")


@needs_node
def test_verify_a11y_script_passes():
    """The whole scan: roles, labels, 44pt/hitSlop, inputs, the M7 inset."""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "scripts/verify_a11y.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    assert "ALL PASS" in proc.stdout
    # The scan must actually have looked at the app, not an empty tree.
    m = re.search(r"\((\d+) Pressables;", proc.stdout)
    assert m and int(m.group(1)) >= 200, proc.stdout[-2000:]
    m = re.search(r"ends with BetslipBarSpacer \((\d+) covered\)", proc.stdout)
    assert m and int(m.group(1)) >= 20, proc.stdout[-2000:]


def _run(tmp_path: Path, files: list[str], script: str) -> subprocess.CompletedProcess:
    for name in files:
        src = _read(LIB / name)
        src = re.sub(r"from '\./(\w+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    return subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )


PRELUDE = """
const eq = (got, want, what) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
"""


@needs_node
def test_spoken_labels(tmp_path):
    script = PRELUDE + """
import { gameStatusSpeech, unitsSpeech, sharpScoreSpeech, pageLabel, spokenDate, slopFor, unknownCountSpeech } from './a11y.ts';
import { gameStartedSpeech, gameStartedLine } from './pickCta.ts';
eq(gameStatusSpeech({ kind: 'live', awayScore: 3, homeScore: 2, inning: 9, inningHalf: 'bottom', outs: 2 }), 'Live, bottom 9th, 2 outs, 3 to 2', 'M22 live');
eq(gameStatusSpeech({ kind: 'final', awayScore: 5, homeScore: 3 }), 'Final, 5 to 3', 'final');
eq(gameStatusSpeech({ kind: 'pre', timeLabel: '7:05 PM ET' }), 'Starts 7:05 PM ET', 'pre');
eq(gameStatusSpeech({ kind: 'ended' }), null, 'ended');
eq(unitsSpeech('1.2u → 1.0u'), '1.2 units to win 1.0 units', 'stake');
eq(unitsSpeech('0.5u'), '0.5 units', 'conviction stake');
eq(sharpScoreSpeech(35, 'low'), 'Sharp score 35 of 100, low', 'M5');
eq(pageLabel(0, 4), 'Page 1 of 4', 'M19');
eq(spokenDate('2026-01-05'), 'January 5, 2026', 'calendar');
eq(slopFor(31), { top: 7, bottom: 7, left: 0, right: 0 }, 'slop');
// "—" counts (#845) speak the sub-tabs' "count not available".
eq(unknownCountSpeech('Sep 28 · — bets · — scored'), 'Sep 28, bets count not available, scored count not available', 'unknown counts');
eq(unknownCountSpeech(unitsSpeech('Sep 28 · — pre-game signals · 1.2u staked')), 'Sep 28, pre-game signals count not available, 1.2 units staked', 'unknown + units');
eq(unknownCountSpeech('3 in play'), '3 in play', 'known count');
eq(gameStartedSpeech(-125, 'DraftKings'), 'Game started. Picked at -125 at DraftKings. Betting links are off once a game starts.', 'started speech');
eq(gameStartedSpeech(null, 'DraftKings'), 'Game started. Betting links are off once a game starts.', 'started, no price');
// The visible line is unchanged from #847.
eq(gameStartedLine(-125, 'DK'), 'Game started · picked at -125 DK', 'visible line');
"""
    proc = _run(tmp_path, ["a11y.ts", "format.ts", "pickCta.ts"], script)
    assert proc.returncode == 0, proc.stderr


def test_betslip_bar_inset_wiring():
    """M7: the bar publishes its height; the spacer reserves exactly that."""
    bar = _read(SRC / "components" / "BetslipBar.tsx")
    assert "setBetslipBarInset(barHeight.current + floatGap)" in bar
    assert "useEffect(() => () => setBetslipBarInset(0), [])" in bar
    hook = _read(SRC / "hooks" / "useBetslipBarInset.ts")
    assert "export function setBetslipBarInset" in hook and "export function useBetslipBarInset" in hook
    spacer = _read(SRC / "components" / "BetslipBarSpacer.tsx")
    assert "height: inset" in spacer and "if (inset <= 0) return null;" in spacer
    # A representative screen from each list kind.
    assert "ListFooterComponent={<BetslipBarSpacer />}" in _read(SRC / "screens" / "PicksHomeScreen.tsx")
    assert re.search(r"<BetslipBarSpacer />\s*</ScrollView>", _read(SRC / "screens" / "SettingsScreen.tsx"))


def test_tab_roles():
    """H9 / M8: tablist containers, tab items with selected state."""
    toggle = _read(SRC / "components" / "SportToggle.tsx")
    assert 'accessibilityRole="tablist"' in toggle and 'accessibilityRole="tab"' in toggle
    assert 'accessibilityRole="button"' not in toggle
    home = _read(SRC / "screens" / "PicksHomeScreen.tsx")
    assert '<View style={styles.subTabs} accessibilityRole="tablist">' in home
    record = _read(SRC / "screens" / "TrackRecordScreen.tsx")
    assert 'accessibilityRole="tablist"' in record and 'accessibilityRole="tab"' in record
    assert "accessibilityLabel={s === 'All' ? 'All sports' : s}" in record
    models = _read(SRC / "screens" / "ModelsScreen.tsx")
    assert '<View style={styles.segmentRow} accessibilityRole="tablist">' in models


def test_pick_card_label_is_complete():
    """M8: status + time, stake and when it posted; nested buttons as actions."""
    card = _read(SRC / "components" / "PickCard.tsx")
    assert "gameStatusSpeech(gameStatus(game, liveState)" in card
    assert "`Stake ${unitsSpeech(stakeCaption)}`" in card
    assert "timing ? timing.label : null" in card
    assert "accessibilityActions={a11yActions.length > 0 ? a11yActions : undefined}" in card


def test_started_line_speaks_the_same_on_card_and_detail():
    """#847 moved the started line onto Pick Detail: both say gameStartedSpeech."""
    spoken = "gameStartedSpeech(decisionOdds(pick), bookName(storedQuoteBook(pick)))"
    assert spoken in _read(SRC / "components" / "PickCard.tsx")
    detail = _read(SRC / "screens" / "PickDetailScreen.tsx")
    assert re.search(r"styles\.startedCard\}[\s\S]{0,120}accessibilityLabel=\{" + re.escape(spoken) + r"\}", detail)


def test_audited_targets():
    """M10 stake chip, M18 tooltip icon, M25 disabled Add bet, M26 chips."""
    perf = _read(SRC / "screens" / "PerformanceScreen.tsx")
    assert "hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}" in perf
    assert "accessibilityLabel={`Edit stake, ${formatCurrency(row.stake)}`}" in perf
    assert "hitSlop={6}" not in perf
    assert "hitSlop={12}" in _read(SRC / "components" / "InfoTooltip.tsx")
    manual = _read(SRC / "components" / "ManualBetModal.tsx")
    assert "accessibilityHint={addHint}" in manual
    assert "addBetHint({ bet: desc, stake })" in manual
    assert "accessibilityState={{ disabled: !valid }}" in manual
    for label in ['"Bet"', '"Sportsbook, optional"', '"Stake in dollars"', '"Odds, American"']:
        assert f"accessibilityLabel={label}" in manual, label
    assert "hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }}" in _read(SRC / "components" / "filters" / "FilterChip.tsx")


def test_h9_rows_reach_44pt_inside_their_bounds():
    """H9: slop only lands inside a horizontal ScrollView, so the rows grow
    their bounds (reachFrame) instead; adjacent rows split the shared gap."""
    toggle = _read(SRC / "components" / "SportToggle.tsx")
    assert "top: TOGGLE_ROOM_ABOVE + reachAbove," in toggle and "bottom: 2 + reachBelow," in toggle
    assert "reachFrame(reachAbove, reachBelow, { raise: reachBelow > 0, marginTop })" in toggle
    chip = int(re.search(r"export const TOGGLE_CHIP_H = (\d+);", toggle).group(1))
    home = _read(SRC / "screens" / "PicksHomeScreen.tsx")
    above = int(re.search(r"reachAbove=\{(\d+)\}", home).group(1))
    below = int(re.search(r"reachBelow=\{(\d+)\}", home).group(1))
    assert chip + 10 + above + 2 + below >= 44
    sub_above = int(re.search(r"const SUBTAB_REACH_ABOVE = (\d+);", home).group(1))
    assert 2 + below + sub_above == 12, "the 12pt gap is split so the rows tile"
    models = _read(SRC / "screens" / "ModelsScreen.tsx")
    m = re.search(r"<SportToggle marginTop=\{spacing\.md\} reachAbove=\{(\d+)\} />", models)
    assert m and int(m.group(1)) <= 12 and chip + 10 + int(m.group(1)) + 2 >= 44
    ps = _read(SRC / "screens" / "PlayerStatsScreen.tsx")
    assert "const rangeReachBelow = error ? 0 : 6;" in ps
    assert "hitSlop={{ top: 4, bottom: 4 + rangeReachBelow, left: 2, right: 2 }}" in ps
    assert "hitSlop={{ top: 2, bottom: 2, left: 6, right: 6 }}" in _read(SRC / "components" / "CalendarGrid.tsx")


@needs_node
def test_reach_frame_and_add_bet_hint(tmp_path):
    script = PRELUDE + """
import { reachFrame, addBetHint } from './a11y.ts';
eq(reachFrame(6, 4, { raise: true }), { frame: { marginTop: -6, marginBottom: -4, zIndex: 1 }, content: { paddingTop: 6, paddingBottom: 4 } }, 'raised');
eq(reachFrame(10, 0, { marginTop: 12 }), { frame: { marginTop: 2, marginBottom: -0 }, content: { paddingTop: 10, paddingBottom: 0 } }, 'own margin');
eq(addBetHint({ bet: 'Yankees ML', stake: '' }), 'Enter a stake above zero to add this bet.', 'M25 stake');
eq(addBetHint({ bet: '', stake: '0' }), 'Enter the bet and a stake above zero to add this bet.', 'M25 both');
eq(addBetHint({ bet: 'x', stake: '5' }), undefined, 'M25 valid');
"""
    proc = _run(tmp_path, ["a11y.ts"], script)
    assert proc.returncode == 0, proc.stderr


def test_sheet_backdrops_do_not_wrap_the_sheet():
    """An accessible backdrop that wraps the sheet hides the sheet from VoiceOver."""
    for name in ["AddLineSheet", "HitModeSheet", "StatGroupSheet", "PlayerNewsSheet", "StatePickerSheet",
                 "ParlayDkHandoff", "SportsbookPickerSheet", "InfoTooltip", "filters/FilterSheet"]:
        src = _read(SRC / "components" / f"{name}.tsx")
        assert "<View style={styles.backdrop}>" in src, name
        assert not re.search(r"<Pressable\s+style=\{styles\.backdrop\}", src), name

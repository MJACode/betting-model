"""Paused models' picks on the All board work like any other pick.

Matt, 2026-09-28 (Designer mockups in the paused-on-All PR): a paused model's
pick keeps its BET / NONE / AVOID badge, stake, Sharp Score, timing, best
book, Slip and Track on All, with a neutral "Paused" tag, because the only
thing a pause changes is that the pick is never SENT as a signal (no Discord,
no push). What this file pins:

- the strict ``passesActionFilter`` (Signals, sport badges) still refuses a
  paused model, and Live Signals still drops one;
- the lenient ``passesActionFilterIgnoringPause`` (All's "N bets", the card's
  green edge, the Edge tint) ignores the pause and the Discord check but never
  counts a VOID, and is the strict filter for every other model;
- paused rows sort like any other, Time included; "BET only" keeps them;
- the tag renders and the badge stays; its VoiceOver text is in cardLabel;
- the card and detail gates are gone; the betslip keeps paused keys;
- the copy ("Paused", "Picked …", the detail note, the stake line, tooltip).

The pure lib modules run under node's type stripping (CI has node 22 and no
node_modules); ``mobile/scripts/verify_paused_on_all.ts`` runs when the node
modules exist.
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

PURE = [
    "thresholds.ts",
    "thresholds.generated.ts",
    "decisionPrice.ts",
    "discordPublish.ts",
    "format.ts",
    "markets.ts",
    "lineMovementBoard.ts",
    "dateFilter.ts",
    "pausedPick.ts",
]


def _read(path: Path) -> str:
    # Explicit encoding: cp1252 on Windows dies on the source's punctuation.
    return path.read_text(encoding="utf-8")


def _node_strips_types() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)


def _run(tmp_path: Path, script: str) -> subprocess.CompletedProcess:
    for name in PURE:
        src = _read(LIB / name)
        src = re.sub(r"from '\./([\w.]+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    return subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )


PRELUDE = """
const eq = (got, want, what) => {
  if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
import {
  isModelPaused, isPausedForDisplay, passesActionFilter,
  passesActionFilterIgnoringPause, setServerThresholds,
} from './thresholds.ts';
setServerThresholds(null);
// ncaaf_moneyline is paused in the bundle (0.62 / 0.08 / -250). The mockups'
// Alabama ML: model 76.2% at -142, edge +17.5%, never posted.
const base = {
  model_id: 'ncaaf_moneyline', signal_type: 'BET', model_probability: 0.762,
  dk_odds: -142, edge: 0.175, condition_status: null, result: null,
  discordPublish: 'unpublished', sport: 'NCAAF', game_date: '2026-09-28',
};
const active = {
  ...base, model_id: 'nhl_moneyline', sport: 'NHL', model_probability: 0.6,
  dk_odds: 120, edge: 0.15, discordPublish: 'published',
};
"""


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_strict_and_lenient_filters(tmp_path):
    script = PRELUDE + """
eq(isModelPaused('ncaaf_moneyline'), true, 'fixture paused');
eq(isPausedForDisplay(base), true, 'fixture drawn paused');
eq(passesActionFilter(base), false, 'strict refuses a paused BET');
eq(passesActionFilterIgnoringPause(base), true, 'lenient passes a paused BET over its bar');
eq(passesActionFilterIgnoringPause({ ...base, discordPublish: 'unknown' }), true, 'lenient, no ledger read');
eq(passesActionFilterIgnoringPause({ ...base, condition_status: 'VOID' }), false, 'lenient never counts a VOID');
eq(passesActionFilterIgnoringPause({ ...base, signal_type: 'NONE' }), false, 'NONE');
eq(passesActionFilterIgnoringPause({ ...base, signal_type: 'AVOID' }), false, 'AVOID');
eq(passesActionFilterIgnoringPause({ ...base, edge: 0.05 }), false, 'under the edge bar');
eq(passesActionFilterIgnoringPause({ ...base, model_probability: 0.6 }), false, 'under the prob bar');
eq(passesActionFilterIgnoringPause({ ...base, model_id: 'mlb_prop_batter_rbi' }), false, 'retired');
// An active model: lenient IS strict, on every VOID / Discord combination.
for (const cs of [null, 'VOID', 'OK']) {
  for (const dp of ['published', 'unpublished', undefined]) {
    const p = { ...active, condition_status: cs, discordPublish: dp };
    eq(passesActionFilterIgnoringPause(p), passesActionFilter(p), `active ${cs} ${dp}`);
  }
}
eq(passesActionFilter(active), true, 'active fixture passes');
// The server flag wins once loaded.
setServerThresholds({ ncaaf_moneyline: { min_prob: 0.62, min_edge: 0.08, min_odds: -250, prob_only: false, paused: true } });
eq([passesActionFilter(base), passesActionFilterIgnoringPause(base)], [false, true], 'server paused');
setServerThresholds({ ncaaf_moneyline: { min_prob: 0.62, min_edge: 0.08, min_odds: -250, prob_only: false, paused: false } });
const pub = { ...base, discordPublish: 'published' };
eq(passesActionFilterIgnoringPause(pub), passesActionFilter(pub), 'server unpaused: same filter');
setServerThresholds(null);
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_paused_rows_never_badge_a_sport_and_copy(tmp_path):
    script = PRELUDE + """
import { signalCountsBySport } from './lineMovementBoard.ts';
import { pickTimingInfo } from './markets.ts';
import { rowsByDay } from './dateFilter.ts';
import { PAUSED_TAG_TEXT, PAUSED_SPOKEN, PAUSED_DETAIL_NOTE } from './pausedPick.ts';
const counts = signalCountsBySport([{ pick: base, game: null }, { pick: active, game: null }]);
eq(counts, { NHL: 1 }, 'sport badges: the active BET only');
const t = { ...base, created_at: '2026-09-28T21:19:00Z', player_id: null, is_live: false };
const paused = pickTimingInfo(t, { paused: true });
const posted = pickTimingInfo(t);
eq(paused.verb, 'Picked', 'paused verb');
eq(paused.label.startsWith('Picked '), true, 'paused label');
eq(/wasn’t sent as a signal/.test(paused.note), true, 'paused note');
eq(posted.label.startsWith('Posted '), true, 'any other pick still Posted');
eq(PAUSED_TAG_TEXT, 'Paused', 'tag');
eq(PAUSED_SPOKEN, 'Model paused, not sent as a signal', 'spoken');
eq(PAUSED_DETAIL_NOTE, 'This model is paused, so this pick isn’t sent as a signal (no Discord or push alerts). Everything else works as usual.', 'note');
const rows = rowsByDay([{ id: 'a', d: '2026-09-28' }, { id: 'p', d: '2026-09-28' }, { id: 'b', d: '2026-09-28' }], (r) => r.d, (r) => r.id, undefined, '2026-09-28');
eq(rows.map((r) => r.key), ['a', 'p', 'b'], 'no trailing key keeps kickoff order');
"""
    proc = _run(tmp_path, script)
    assert proc.returncode == 0, proc.stderr


def test_the_tag_renders_and_the_badge_stays():
    card = _read(SRC / "components" / "PickCard.tsx")
    assert ">PAUSED<" not in card
    assert re.search(r"\) : showSignalBadge \? \(\s*<View style=\{styles\.labelChip\}>\s*<SignalBadge", card)
    assert re.search(r"caption && paused \? \([\s\S]*?<PausedTag />", card)
    # Read once, in cardLabel; the tag itself is hidden (#848's rule).
    assert re.search(r"pick\.signal_type,\s*//[^\n]*\n\s*paused \? PAUSED_SPOKEN : null,", card)
    tag = _read(SRC / "components" / "PausedTag.tsx")
    assert "speak = false" in tag
    assert "accessibilityElementsHidden: true, importantForAccessibility: 'no-hide-descendants'" in tag
    assert "borderWidth: StyleSheet.hairlineWidth" in tag
    assert "borderColor: colors.separatorOpaque" in tag
    assert "color: colors.textSecondary" in tag
    assert 'name="pause"' in tag
    assert "backgroundColor" not in tag  # neutral outline, not a flat grey pill
    assert "large ? font.size.caption : font.size.micro" in tag
    detail = _read(SRC / "screens" / "PickDetailScreen.tsx")
    assert re.search(
        r"<Text style=\{styles\.modelName\}>\{modelLong\(pick\.model_id\)\}</Text>[\s\S]{0,200}"
        r"\{paused \? <PausedTag large /> : null\}",
        detail,
    )
    assert "<SignalBadge signal={voided ? 'NONE' : pick.signal_type} />" in detail
    assert "'PAUSED'" not in detail
    assert "{paused ? <Text style={styles.pausedNote}>{PAUSED_DETAIL_NOTE}</Text> : null}" in detail
    assert re.search(r"pausedNote: \{[\s\S]*?color: colors\.textSecondary", detail)
    assert "for reference" not in detail
    leg = _read(SRC / "components" / "ParlayLegCard.tsx")
    assert "leg.pick && isPausedForDisplay(leg.pick) ? <PausedTag speak /> : null" in leg


def test_sort_and_count_on_all_signals_unchanged():
    home = _read(SRC / "screens" / "PicksHomeScreen.tsx")
    # Normal sort, Time included.
    assert not re.search(r"all\.filter\(\(d\) => !?isPausedForDisplay", home)
    assert re.search(
        r"rowsByDay\(\s*sortPicks\(filtered, 'time'\),\s*\(d\) => d\.pick\.game_date,\s*"
        r"\(d\) => String\(d\.pick\.pick_id\),\s*\)",
        home,
    )
    # "BET only" keeps a paused BET.
    assert "displayFilter.signals.size === ALL_SIGNALS.length || !isPausedForDisplay" not in home
    # All counts paused BETs; " · N paused" stays.
    assert re.search(
        r"const bet = todayData\.filter\(\s*\(d\) => passesActionFilterIgnoringPause\(d\.pick\) "
        r"&& !isUnlockedPreview\(d\.pick\),?\s*\)\.length;",
        home,
    )
    assert "const paused = todayData.filter((d) => isPausedForDisplay(d.pick)).length;" in home
    # Signals, sport badges and Live Signals stay strict.
    assert "todayData.filter((d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick))" in home
    assert "signalCountsBySport(allData)" in home
    assert "if (!passesActionFilter(d.pick)) continue;" in _read(LIB / "lineMovementBoard.ts")
    assert re.search(r"!isModelPaused\(d\.pick\.model_id\) &&\s*!isModelRetired", home)
    assert (
        "tagged Paused. They work like any other pick, but aren’t sent as signals "
        "(no Discord or push alerts) and never appear on Signals." in home
    )
    assert "marked PAUSED" not in home


def test_stake_slip_track_and_best_book_are_back():
    card = _read(SRC / "components" / "PickCard.tsx")
    assert "const sharp = preview ? null : sharpScore(pick);" in card
    assert "const contra = contrarianTag(pick);" in card
    assert "pick.signal_type !== 'BET' || preview\n" in card
    assert "const offersBook = !preview && pick.signal_type === 'BET';" in card
    assert re.search(
        r"const canSlip =\s*Boolean\(onToggleSlip\) && hasPricedLine\(pick\) && open && !preview && cta\.slip;",
        card,
    )
    assert re.search(r"const canTrack = [^;]*&& open && cta\.track;", card)
    assert "const timing = openForAction(pick) ? pickTimingInfo(pick, { paused }) : null;" in card
    assert "const qualifies = passesActionFilterIgnoringPause(pick);" in card
    assert "shown for reference" not in card and "pausedLabel" not in card

    detail = _read(SRC / "screens" / "PickDetailScreen.tsx")
    assert "<PickTimingCard pick={pick} paused={paused} />" in detail
    assert re.search(r"\n\s*<SharpScoreCard pick=\{pick\} />", detail)
    assert re.search(
        r"\{pick\.signal_type === 'BET' && !preview && !retired && !voided \? \(\s*cta\.handoff", detail
    )
    assert re.search(r"hasPricedLine\(pick\) && openHere && !preview && !retired\s*&& !voided && cta\.slip", detail)
    # #847's started / AllBooksCard rules are unchanged for a paused row.
    assert "{live || !cta.handoff ? null : <AllBooksCard pick={pick} bookRows={bookRows} />}" in detail

    reasoning = _read(SRC / "components" / "ReasoningCard.tsx")
    assert "pick.signal_type === 'BET' && !isUnlockedPreview(pick) ? (" in reasoning
    assert "the stake the model would publish" in reasoning
    assert "tint={passesActionFilterIgnoringPause(pick)" in reasoning
    assert "reasoningHeading(pick.signal_type, { preview: isUnlockedPreview(pick) })" in reasoning


def test_the_betslip_keeps_paused_keys():
    hook = _read(SRC / "hooks" / "useResolvedSlip.ts")
    assert "const { data, pausedData, loading, error } = picks;" in hook
    assert "[...data, ...pausedData, ...livePicks.data]" in hook


def test_the_mock_switch_never_ships():
    for path in [
        SRC / "components" / "PickCard.tsx",
        SRC / "components" / "PausedTag.tsx",
        SRC / "components" / "ParlayLegCard.tsx",
        SRC / "components" / "ReasoningCard.tsx",
        SRC / "screens" / "PicksHomeScreen.tsx",
        SRC / "screens" / "PickDetailScreen.tsx",
        SRC / "hooks" / "useResolvedSlip.ts",
        LIB / "thresholds.ts",
    ]:
        src = _read(path)
        assert "__fix" not in src and "fix('PAUSED')" not in src, path.name
    assert not (LIB / "__fix.ts").exists()


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_paused_on_all.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

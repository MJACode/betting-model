"""Pick CTA after the start, price check, line history, reasoning heading —
usability audit PR 3 (H5, H4, M13, M14).

H5: once a pre-game pick's game has started, the book hand-off becomes a
non-interactive "Game started · picked at <decision price> <decision book>"
line, the "Now" tag reads "Live price", Slip is hidden and Track stays. Before
the start the hand-off is always the best available book, never DK-only.
H4: a display-only "Price check" band (edge > 25pp or |locked − current| >
500 cents) shows "—" for edge and EV and sorts the row last on the Edge sort;
NONE / AVOID cards demote the edge to a secondary line. M13: line-movement
rows are changes, not raw snapshots. M14: "Why this bet?" only on a bet.

The pure modules run here under node's type stripping; the full behavioural
script (`mobile/scripts/verify_pick_cta.ts`) runs when node modules exist.
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


def _run(tmp_path: Path, files: list[str], script: str) -> subprocess.CompletedProcess:
    """Copy pure lib modules into tmp_path with node-resolvable relative imports."""
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


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_game_started_cta_behaviour(tmp_path):
    script = PRELUDE + """
import { gameHasStarted, gameStartState } from './format.ts';
import { gameStartedLine, pickCta, pickCtaFor, reasoningHeading } from './pickCta.ts';
const future = new Date(Date.now() + 3 * 3600000).toISOString();
const past = new Date(Date.now() - 3600000).toISOString();
eq(gameHasStarted({ sport: 'MLB', commence_time: future }), false, 'pre');
eq(gameHasStarted({ sport: 'MLB', commence_time: future }, { abstract_game_state: 'Live' }), true, 'live feed');
eq(gameHasStarted({ sport: 'MLB', commence_time: past }), true, 'past first pitch');
eq(gameHasStarted({ sport: 'MLB', commence_time: past }, { abstract_game_state: 'Preview' }), false, 'delayed');
eq(pickCta({ isLive: false, started: false }), { handoff: true, startedLine: false, slip: true, track: true, priceTag: 'Now' }, 'before');
eq(pickCta({ isLive: false, started: true, inPlay: true }), { handoff: false, startedLine: true, slip: false, track: true, priceTag: 'Live price' }, 'after');
eq(pickCta({ isLive: true, started: true, inPlay: true }), { handoff: true, startedLine: false, slip: true, track: true, priceTag: 'Live price' }, 'live signal');
// Reviewer #847: "Live price" only in play; a final game reads "Now".
eq(pickCta({ isLive: false, started: true, inPlay: false }).priceTag, 'Now', 'final tag');
// M6: fail closed on a missing games row / commence_time via pick.game_time.
eq(gameHasStarted(null, null, past), true, 'no games row, game_time past');
eq(gameHasStarted({ sport: 'MLB', commence_time: null }, null, past), true, 'no commence_time');
eq(gameHasStarted(null, null, future), false, 'game_time ahead');
eq(gameHasStarted(null, null, null), false, 'nothing known');
// Low: called off before first pitch is not "started".
const fin = { abstract_game_state: 'Final', home_score: null, away_score: null };
eq(gameStartState({ sport: 'MLB', commence_time: future }, fin), 'postponed', 'postponed');
eq(gameStartState({ sport: 'MLB', commence_time: past }, fin), 'over', 'ended');
eq(pickCta({ isLive: false, started: false, postponed: true }), { handoff: false, startedLine: false, slip: false, track: true, priceTag: 'Now' }, 'postponed cta');
eq(pickCtaFor({ is_live: false, game_time: past }, null, null).startedLine, true, 'pickCtaFor fallback');
eq(pickCtaFor({ is_live: false, game_time: future }, { sport: 'MLB', commence_time: future }, fin).startedLine, false, 'pickCtaFor postponed');
eq(gameStartedLine(-125, 'DK'), 'Game started · picked at -125 DK', 'line');
eq(gameStartedLine(215, 'FAN'), 'Game started · picked at +215 FAN', 'line +');
eq(gameStartedLine(null, 'DK'), 'Game started', 'no price');
eq(reasoningHeading('BET'), 'Why this bet?', 'BET');
eq(reasoningHeading('NONE'), 'Why no bet?', 'NONE');
eq(reasoningHeading('AVOID'), 'Why avoid?', 'AVOID');
eq(reasoningHeading('BET', { paused: true }), 'Why this pick?', 'paused BET');
"""
    proc = _run(tmp_path, ["format.ts", "pickCta.ts"], script)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_price_check_boundaries_and_sort(tmp_path):
    script = PRELUDE + """
import { centsApart, flaggedLast, priceCheck, PRICE_CHECK_MAX_CENTS, PRICE_CHECK_MAX_EDGE } from './priceCheck.ts';
eq([PRICE_CHECK_MAX_EDGE, PRICE_CHECK_MAX_CENTS], [0.25, 500], 'constants');
eq(centsApart(-110, 110), 20, 'even-money gap');
eq(centsApart(3300, -110), 3210, 'NYY ML');
const f = (edge, locked, current) => priceCheck({ edge, locked, current }).flagged;
eq(f(0.25, -110, -110), false, 'edge at the bound');
eq(f(0.2501, -110, -110), true, 'edge over the bound');
eq(f(-0.4, -110, -110), false, 'negative edge');
eq(f(0.05, -600, -100), false, '500 cents');
eq(f(0.05, -601, -100), true, '501 cents');
eq(f(0.05, 3300, null), false, 'no current price');
eq(priceCheck({ edge: 0.548, locked: 3300, current: -110 }).reasons, ['edge', 'moved'], 'reasons');
// Reviewer #847 M2: after the start the hero Now is the in-play price.
eq(f(0.05, -150, 700), true, 'pre-game moved');
eq(priceCheck({ edge: 0.05, locked: -150, current: 700, started: true }).flagged, false, 'in-play: moved rule skipped');
eq(priceCheck({ edge: 0.3, locked: -150, current: 700, started: true }).flagged, true, 'in-play: edge rule kept');
eq(flaggedLast([1, 2, 3, 4, 5], (n) => n % 2 === 0), [1, 3, 5, 2, 4], 'stable partition');
"""
    proc = _run(tmp_path, ["priceCheck.ts"], script)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_line_history_collapses_and_disambiguates(tmp_path):
    script = PRELUDE + """
import { changesFooter, collapseLineHistory, recentChanges } from './lineHistory.ts';
const t = (h, m, s = 0) => `2026-09-25T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}Z`;
const runs = collapseLineHistory([
  { at: t(19, 50, 1), line: 8.5, price: -110 }, { at: t(19, 50, 20), line: 8.5, price: -110 },
  { at: t(20, 5), line: 8.5, price: -115 }, { at: t(20, 30), line: 9, price: -105 },
]);
eq(runs.map((r) => r.count), [2, 1, 1], 'collapse');
eq(runs.map((r) => r.label), ['3:50 PM ET', '4:05 PM ET', '4:30 PM ET'], 'minute labels');
const flick = collapseLineHistory([
  { at: t(19, 50, 5), line: null, price: -105 }, { at: t(19, 50, 25), line: null, price: -115 },
]);
if (!flick.every((r) => /^3:50:\\d\\d PM ET$/.test(r.label))) throw new Error(flick.map((r) => r.label).join('|'));
const rc = recentChanges(Array.from({ length: 20 }, (_, i) => ({ at: t(18, i), line: null, price: i % 2 ? -110 : -112 })), 8);
eq([rc.rows.length, rc.changes, rc.shownChanges, rc.hidden], [8, 19, 8, 12], 'recent');
// Reviewer #847 lows: the opening row is not a change; a mid-run null joins
// the run; same-timestamp rows get unique keys.
eq(recentChanges([{ at: t(18, 0), line: 8.5, price: -110 }, { at: t(18, 30), line: 8.5, price: -115 }]).changes, 1, 'opening not a change');
const gap = collapseLineHistory([
  { at: t(18, 0), line: 8.5, price: -110 }, { at: t(18, 5), line: 8.5, price: null },
  { at: t(18, 10), line: null, price: -110 }, { at: t(18, 15), line: 8.5, price: -110 },
]);
eq(gap.map((r) => r.count), [2], 'partial rows are unknown, not counted');
// Reviewer #847 approval: carry only when BOTH are null; a partial row never
// borrows the other field (8.5 @ -110 then 9.0 @ null must not print 9.0 @ -110).
const invent = collapseLineHistory([
  { at: t(18, 0), line: 8.5, price: -110 }, { at: t(18, 5), line: 9, price: null }, { at: t(18, 10), line: 9, price: -115 },
]);
eq(invent.map((r) => [r.line, r.price]), [[8.5, -110], [9, -115]], 'no invented pair');
eq(collapseLineHistory([
  { at: t(18, 0), line: 8.5, price: -110 }, { at: t(18, 5), line: null, price: null }, { at: t(18, 10), line: 8.5, price: -110 },
]).map((r) => r.count), [3], 'both null is a gap');
eq(collapseLineHistory([{ at: t(18, 0), line: null, price: -110 }, { at: t(18, 5), line: null, price: -120 }]).length, 2, 'moneyline: line untracked');
// Footer: the hidden row is the opening → not "Last 8 of 8 changes".
const nine = recentChanges(Array.from({ length: 9 }, (_, i) => ({ at: t(18, i), line: null, price: i % 2 ? -110 : -112 })), 8);
eq(changesFooter(nine, 9), '8 changes · opening not shown · 9 snapshots', 'opening-only hidden');
eq(changesFooter(rc, 20), 'Last 8 of 19 changes · 20 snapshots', 'really cut');
const same = collapseLineHistory([{ at: t(18, 0), line: null, price: -110 }, { at: t(18, 0), line: null, price: -115 }]);
eq(new Set(same.map((r) => r.key)).size, 2, 'unique keys');
"""
    proc = _run(tmp_path, ["lineHistory.ts"], script)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_best_handoff_reranks_by_current_price(tmp_path):
    """Reviewer #847 M4, in CI (node 22 is set up there; no node_modules
    needed): record DK -110, now DK -130, FD -115 → the hand-off is FD -115,
    never "Bet DK -130". markets.ts and its pure imports run under node's type
    stripping (type-only imports are erased)."""
    files = ["markets.ts", "format.ts", "thresholds.ts", "thresholds.generated.ts", "decisionPrice.ts", "discordPublish.ts"]
    for name in files:
        src = _read(LIB / name)
        src = re.sub(r"from '\./([\w.]+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    script = PRELUDE + """
import { bestHandoffForPick, heroAmericanForPick, MODEL_BOOK } from './markets.ts';
const pick = {
  pick_id: 1, game_id: 'MLB_2026-09-13_NYJ_BUF', model_id: 'mlb_over_under', sport: 'MLB', game_date: '2026-09-13',
  pick_side: 'over', pick_label: 'NYJ @ BUF Over 8.5', model_probability: 0.58, dk_implied_prob: 0.535, edge: 0.082,
  dk_odds: -110, scored_line: 8.5, signal_type: 'BET', is_live: false, dk_bet_link: 'dk://lock',
  decision_odds: -110, decision_edge: 0.082, decision_book: 'draftkings', line_book: null,
};
const latest = (over) => ({ game_id: pick.game_id, game_date: '2026-09-13', market: 'totals', home_price: null, away_price: null,
  spread_home: null, total_line: 8.5, over_price: -110, under_price: -110, snapshot_at: '2026-09-13T17:00:00+00:00', ...over });
const rows = [
  { bookmaker: 'draftkings', over_price: -130, total_line: 8.5 },
  { bookmaker: 'fanduel', over_price: -115, total_line: 8.5, over_link: 'fd://now' },
];
const hero = heroAmericanForPick(pick, latest({ over_price: -130 }), rows);
eq([hero?.kind, hero?.price, hero?.book], ['now', -130, MODEL_BOOK], 'hero is Now DK -130');
const h = bestHandoffForPick(pick, rows, hero);
eq([h?.bookmaker, h?.price, h?.verb, h?.link], ['fanduel', -115, 'Best', 'fd://now'], 'M4 re-rank -> FD -115');
// Still DK when DK's CURRENT price is the best.
const rows2 = [{ bookmaker: 'draftkings', over_price: -112, total_line: 8.5 }, { bookmaker: 'fanduel', over_price: -115, total_line: 8.5 }];
const h2 = bestHandoffForPick(pick, rows2, heroAmericanForPick(pick, latest({ over_price: -112 }), rows2));
eq([h2?.bookmaker, h2?.price, h2?.verb], [MODEL_BOOK, -112, 'Bet'], 'DK now -112 beats FD -115');
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_best_handoff_rerank_is_wired():
    """The static half, for runners without node: the re-rank reads the hero's
    current price, not the record chip's stored one."""
    markets = _read(LIB / "markets.ts")
    assert re.search(r"export function bestHandoffForPick\(", markets)
    assert "hero" in markets[markets.index("export function bestHandoffForPick("):][:3000]
    card = _read(SRC / "components" / "PickCard.tsx")
    assert re.search(r"bestHandoffForPick\(pick, item\.bookRows, heroPrice\)", card)


def test_pick_card_wiring():
    card = _read(SRC / "components" / "PickCard.tsx")
    assert "const cta = pickCtaFor(pick, game, liveState);" in card
    assert "priceCheckForItem(item, liveState)" in card
    assert re.search(r"offersBook && cta\.handoff\s*\?\s*bestHandoffForPick", card)
    assert re.search(r"const canSlip =[^;]*&& cta\.slip;", card)
    assert re.search(r"const canTrack = [^;]*&& open && cta\.track;", card)
    # The started line is not gated on paused: no NEW paused gating (#847).
    started_def = re.search(r"const startedText =[^;]*;", card)
    assert started_def and "pick.signal_type === 'BET' && !preview && open && cta.startedLine" in started_def.group(0)
    assert "paused" not in started_def.group(0) and "offersBook" not in started_def.group(0)
    started = re.search(r"<View style=\{styles\.startedLine\}.*?</View>", card, re.S)
    assert started, "no Game started line"
    block = started.group(0)
    assert 'accessibilityRole="text"' in block and 'name="lock-closed"' in block
    assert "onPress" not in block and "Pressable" not in block
    assert re.search(r"startedText: \{[^}]*color: colors\.textSecondary", card)
    assert card.count("cta.priceTag") >= 2 and "kind === 'now' ? 'Now'" not in card
    assert ">Price check<" in card and re.search(r"priceCheckChip: \{[^}]*colors\.medSoft", card)
    assert "flagged ? '—' : formatPctSigned(decisionEdge(pick))" in card and "flagged ? 'EV —'" in card
    assert "const demoteEdge = pick.signal_type !== 'BET';" in card
    assert "kind === 'pre' && !flagged" in card


def test_pick_detail_board_and_copy_wiring():
    detail = _read(SRC / "screens" / "PickDetailScreen.tsx")
    assert re.search(r"cta\.handoff \? \(\s*<View style=\{styles\.linesCard\}>", detail)
    assert "cta.startedLine && openHere" in detail
    assert "gameStartedLine(decisionOdds(pick), bookLabel(storedQuoteBook(pick)))" in detail
    assert "&& !voided && cta.slip ?" in detail and "const canTrack = openHere;" in detail
    assert "const cta = pickCtaFor(pick, game, liveState);" in detail
    # H5: AllBooksCard's rows open betslips, so it goes with the hand-off.
    assert "{live || !cta.handoff ? null : <AllBooksCard" in detail and detail.count("<AllBooksCard") == 1
    assert "{pick.signal_type === 'BET' && !preview && !retired && !voided && cta.startedLine && openHere ? (" in detail
    reasoning = _read(SRC / "components" / "ReasoningCard.tsx")
    assert "reasoningHeading(pick.signal_type" in reasoning and ">Why this bet?<" not in reasoning
    movement = _read(SRC / "components" / "LineMovementCard.tsx")
    assert "recentChanges(" in movement and "snaps.slice(-8)" not in movement
    assert "key={r.key}" in movement and "key={r.at}" not in movement
    home = _read(SRC / "screens" / "PicksHomeScreen.tsx")
    assert "priceCheck: (d) => priceCheckForItem(d, liveStates.get(d.pick.game_id) ?? null).flagged" in home


def test_price_check_is_display_only():
    pc = _read(LIB / "priceCheck.ts")
    assert not re.search(r"^import ", pc, re.M), "priceCheck.ts must stay pure"
    assert "DISPLAY HEURISTICS ONLY" in pc and "MAX_EDGE_CAP" in pc
    for rel in ("components/PickCard.tsx", "screens/PickDetailScreen.tsx", "screens/PicksHomeScreen.tsx"):
        assert not re.search(r"PRICE_CHECK_MAX_(EDGE|CENTS)\s*=", _read(SRC / rel)), rel


def test_pick_cta_pins_are_on_the_pr_ci_subset():
    assert "tests/test_mobile_pick_cta.py" in _read(ROOT / ".github" / "workflows" / "pr-ci.yml")


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_pick_cta.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

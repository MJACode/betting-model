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
// "ET" is in the card's column heading ("Time (ET)"), not on every row.
eq(runs.map((r) => r.label), ['3:50 PM', '4:05 PM', '4:30 PM'], 'minute labels');
const flick = collapseLineHistory([
  { at: t(19, 50, 5), line: null, price: -105 }, { at: t(19, 50, 25), line: null, price: -115 },
]);
if (!flick.every((r) => /^3:50:\\d\\d PM$/.test(r.label))) throw new Error(flick.map((r) => r.label).join('|'));
const rc = recentChanges(Array.from({ length: 20 }, (_, i) => ({ at: t(18, i), line: null, price: i % 2 ? -110 : -112 })), 8);
eq([rc.rows.length, rc.changes, rc.shownChanges, rc.hidden], [8, 19, 8, 12], 'recent');
// Reviewer #847 lows: the first row is not a change; a mid-run null joins
// the run; same-timestamp rows get unique keys.
eq(recentChanges([{ at: t(18, 0), line: 8.5, price: -110 }, { at: t(18, 30), line: 8.5, price: -115 }]).changes, 1, 'first row not a change');
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
// Footer: the hidden row is the first row → not "Last 8 of 8 changes".
const nine = recentChanges(Array.from({ length: 9 }, (_, i) => ({ at: t(18, i), line: null, price: i % 2 ? -110 : -112 })), 8);
eq(changesFooter(nine, { fromPick: true, gap: false }), '8 changes since your pick', 'first-row-only hidden');
eq(changesFooter(rc, { fromPick: true, gap: false }), 'Last 8 of 19 changes since your pick', 'really cut');
const same = collapseLineHistory([{ at: t(18, 0), line: null, price: -110 }, { at: t(18, 0), line: null, price: -115 }]);
eq(new Set(same.map((r) => r.key)).size, 2, 'unique keys');
"""
    proc = _run(tmp_path, ["lineHistory.ts", "format.ts"], script)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_best_handoff_reranks_by_current_price(tmp_path):
    """Reviewer #847 M4, in CI (node 22 is set up there; no node_modules
    needed): record DK -110, now DK -130, FD -115 → the hand-off is FD -115,
    never "Bet DK -130". markets.ts and its pure imports run under node's type
    stripping (type-only imports are erased)."""
    files = ["markets.ts", "format.ts", "thresholds.ts", "thresholds.generated.ts", "decisionPrice.ts", "discordPublish.ts", "clvBet.ts"]
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


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_stale_pre_game_price_is_no_price_on_the_card(tmp_path):
    """The scorer's price-age rule, on the card (2026-10-09). Pick 3204788,
    BYU vs Notre Dame Under 54.5 -112, was posted off DraftKings' 2026-09-05
    row. The app's latest-price views keep the newest row whatever its age, so
    the card showed -112 as current, with a bet link, and the price check
    passed it. Before the start, a deciding price older than
    PREGAME_PRICE_MAX_AGE_MIN is now "Now -", no hand-off at it, and a price
    check. Runs in CI (node 22); the machine it was written on had no node."""
    files = ["markets.ts", "format.ts", "thresholds.ts", "thresholds.generated.ts",
             "decisionPrice.ts", "discordPublish.ts", "clvBet.ts", "priceCheck.ts",
             "pickPriceCheck.ts"]
    for name in files:
        src = _read(LIB / name)
        src = re.sub(r"from '(?:\./|@/lib/)([\w.]+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    script = PRELUDE + """
import { bestHandoffForPick, heroAmericanForPick, PREGAME_PRICE_MAX_AGE_MIN, priceAgeApplies, priceAgeFor } from './markets.ts';
import { priceCheckForItem } from './pickPriceCheck.ts';
const NOW = Date.parse('2026-10-09T16:30:00Z');
const kick = '2099-01-01T00:00:00Z';     // never started, whenever CI runs
const pick = {
  pick_id: 3204788, game_id: 'NCAAF_2026-10-17_notre-dame_byu', model_id: 'ncaaf_over_under', sport: 'NCAAF',
  game_date: '2026-10-17', game_time: kick, pick_side: 'under', pick_label: 'BYU vs Notre Dame Under 54.5',
  model_probability: 0.56, dk_implied_prob: 0.528, edge: 0.03, dk_odds: -112, scored_line: 54.5,
  signal_type: 'BET', is_live: false, dk_bet_link: 'dk://under', decision_odds: -112, decision_edge: 0.03,
  decision_book: 'draftkings', line_book: null,
};
const STALE = '2026-09-05T23:59:48Z';
const FRESH = '2026-10-09T16:20:00Z';
const latest = (snap) => ({ game_id: pick.game_id, game_date: '2026-10-17', market: 'totals', home_price: null,
  away_price: null, spread_home: null, total_line: 54.5, over_price: -108, under_price: -112, snapshot_at: snap });
const staleRows = [
  { bookmaker: 'draftkings', under_price: -112, total_line: 54.5, snapshot_at: STALE },
  { bookmaker: 'fanduel', under_price: -105, total_line: 54.5, under_link: 'fd://old', snapshot_at: STALE },
];
const pre = { started: false, now: NOW };
eq(PREGAME_PRICE_MAX_AGE_MIN, 180, 'the bound');

// The September price is no price.
const hero = heroAmericanForPick(pick, latest(STALE), staleRows, pre);
eq([hero?.kind, hero?.price, hero?.link, hero?.showLockedCaption, hero?.lockedPrice, hero?.stale],
   ['now', null, null, true, -112, true], 'stale: Now -, Locked -112, no link');
eq(heroAmericanForPick(pick, latest(STALE), staleRows)?.kind, 'decision', 'no clock passed: unchanged');
eq(heroAmericanForPick(pick, latest(STALE), staleRows, { started: true, now: NOW })?.kind, 'decision',
   'after the start the last pre-game row is the close');
eq(heroAmericanForPick(pick, null, [], pre)?.kind, 'decision', 'a missing row is not a stale row');
const at = (min) => new Date(NOW - min * 60000).toISOString();
eq(heroAmericanForPick(pick, latest(at(179)), [], pre)?.stale, undefined, '179 minutes old is current');
eq(heroAmericanForPick(pick, latest(at(181)), [], pre)?.stale, true, '181 minutes old is not');

// No hand-off at a stale price.
eq(bestHandoffForPick(pick, staleRows, hero, pre), null, 'every book stale: no hand-off');
const mixed = [staleRows[0], { bookmaker: 'betmgm', under_price: -110, total_line: 54.5, under_link: 'mgm://now', snapshot_at: FRESH }];
const hm = bestHandoffForPick(pick, mixed, heroAmericanForPick(pick, latest(STALE), mixed, pre), pre);
eq([hm?.bookmaker, hm?.price, hm?.link], ['betmgm', -110, 'mgm://now'], 'only a book still pricing it');
const stamped = { ...pick, best_book: 'fanduel', best_odds: -105, best_bet_link: 'fd://stamp' };
eq(bestHandoffForPick(stamped, staleRows, heroAmericanForPick(stamped, latest(STALE), staleRows, pre), pre), null,
   'the best-price stamp at a book whose row went stale is not offered');
const freshRows = staleRows.map((r) => ({ ...r, snapshot_at: FRESH }));
const fh = heroAmericanForPick(pick, latest(FRESH), freshRows, pre);
eq([fh?.kind, fh?.price], ['decision', -112], 'fresh: unchanged');
eq(bestHandoffForPick(pick, freshRows, fh, pre)?.bookmaker, 'fanduel', 'fresh: best price hand-off');

// Only where the scorer applies the rule.
eq(priceAgeApplies({ ...pick, model_id: 'nhl_prop_shots_on_goal' }, pre), false, 'props');
eq(priceAgeApplies({ ...pick, model_id: 'nfl_wind_totals' }, pre), false, 'NFL card models');
eq(priceAgeApplies({ ...pick, is_live: true }, pre), false, 'in-play signals');
eq(priceAgeApplies(pick, {}), false, 'no clock');
// No known start time: not bounded, the scorer's convention too.
eq(priceAgeFor({ game_time: null }, null, null, NOW), { now: NOW }, 'no start known: rule off');
eq(priceAgeFor({ game_time: kick }, null, null, NOW), { started: false, now: NOW }, 'start ahead: rule on');
eq(priceAgeFor({ game_time: null }, { sport: 'NCAAF', commence_time: '2026-01-01T00:00:00Z' }, null, NOW).started, true, 'started: rule off');
eq(priceCheckForItem({ pick: { ...pick, game_time: null }, latestOdds: latest(STALE), bookRows: staleRows, game: null }, null, NOW).flagged,
   false, 'no start known: a stale row is not judged');

// The price check flags it; fresh and missing pass.
const game = { sport: 'NCAAF', commence_time: kick };
const pc = priceCheckForItem({ pick, latestOdds: latest(STALE), bookRows: staleRows, game }, null, NOW);
eq([pc.flagged, pc.reasons], [true, ['stale']], 'a stale price is a price check');
eq(priceCheckForItem({ pick, latestOdds: latest(FRESH), bookRows: freshRows, game }, null, NOW).flagged, false, 'fresh');
eq(priceCheckForItem({ pick, latestOdds: null, bookRows: [], game }, null, NOW).flagged, false, 'missing');
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_stale_card_says_why_and_speaks_the_locked_price(tmp_path):
    """Second review (2026-10-09). A stale card said "Price check" and spoke
    "this price looks off", when DraftKings had simply not updated the price
    since September; "Now —" never said why; and VoiceOver heard "Now
    unavailable DK" with no price at all while the eye saw "Locked -112". The
    wording now comes from the check's reasons, the stale result carries the
    deciding book's last update time, and the label speaks the lock."""
    files = ["markets.ts", "format.ts", "thresholds.ts", "thresholds.generated.ts",
             "decisionPrice.ts", "discordPublish.ts", "clvBet.ts", "priceCheck.ts",
             "pickPriceCheck.ts", "heroPriceText.ts"]
    for name in files:
        src = _read(LIB / name)
        src = re.sub(r"from '(?:\./|@/lib/)([\w.]+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    script = PRELUDE + """
import { heroAmericanForPick } from './markets.ts';
import { heroPriceSpeech, lockedCaptionText, priceCheckChipText, priceCheckSpeech } from './heroPriceText.ts';
const ok = (cond, what) => { if (!cond) throw new Error(what); };
const NOW = Date.parse('2026-10-09T16:30:00Z');
const pre = { started: false, now: NOW };
const pick = {
  pick_id: 2558736, game_id: 'NCAAF_2099-11-07_x_y', model_id: 'ncaaf_over_under', sport: 'NCAAF',
  game_date: '2099-11-07', game_time: '2099-11-07T20:00:00Z', pick_side: 'under', pick_label: 'Under 54.5',
  model_probability: 0.56, dk_implied_prob: 0.528, edge: 0.03, dk_odds: -112, scored_line: 54.5,
  signal_type: 'BET', is_live: false, dk_bet_link: 'dk://under', decision_odds: -112, decision_edge: 0.03,
  decision_book: 'draftkings', line_book: null,
};
const STALE = '2026-09-05T23:59:48Z';
const latest = (snap) => ({ game_id: pick.game_id, game_date: '2099-11-07', market: 'totals', home_price: null,
  away_price: null, spread_home: null, total_line: 54.5, over_price: -108, under_price: -112, snapshot_at: snap });

// The stale result carries the deciding book's newest stamp, from either view.
const hero = heroAmericanForPick(pick, latest(STALE), [], pre);
eq([hero?.stale, hero?.staleSince], [true, STALE], 'stale carries the stamp');
const newerRow = [{ bookmaker: 'draftkings', under_price: -112, total_line: 54.5, snapshot_at: '2026-09-06T02:00:00Z' }];
eq(heroAmericanForPick(pick, latest(STALE), newerRow, pre)?.staleSince, '2026-09-06T02:00:00Z', 'the newer of the two views');
eq(heroAmericanForPick(pick, latest('2026-10-09T16:20:00Z'), [], pre)?.staleSince, undefined, 'a current price has no stamp');

// The chip and the spoken reason follow the reasons.
const staleOnly = { flagged: true, reasons: ['stale'] };
eq(priceCheckChipText(staleOnly), 'Old price', 'old price only');
eq(priceCheckChipText({ flagged: true, reasons: ['edge', 'stale'] }), 'Price check', 'edge and old');
eq(priceCheckChipText({ flagged: true, reasons: ['moved'] }), 'Price check', 'moved');
const why = priceCheckSpeech(staleOnly, hero);
ok(why.startsWith('DraftKings has not updated this price since ') && why.includes('9/5') && why.includes(' ET')
   && why.endsWith(', so edge and EV are hidden') && !why.includes('looks off'), why);
eq(priceCheckSpeech({ flagged: true, reasons: ['edge'] }, hero),
   'Price check: this price looks off, so edge and EV are hidden', 'edge keeps the looks-off sentence');

// The spoken price: no "unavailable DK", and the lock is read out.
eq(heroPriceSpeech(hero, 'Now'), 'No current DraftKings price. Locked -112', 'stale label speaks the lock');
const moved = heroAmericanForPick({ ...pick, decision_odds: -110, dk_odds: -110 }, latest('2026-10-09T16:20:00Z'), [], pre);
eq(heroPriceSpeech(moved, 'Now'), 'Now -112 DraftKings. Locked -110', 'moved: Now and the lock');
const unmoved = heroAmericanForPick(pick, latest('2026-10-09T16:20:00Z'), [], pre);
eq(heroPriceSpeech(unmoved, 'Now'), '-112 DraftKings', 'unmoved: the decision price');
const live = heroAmericanForPick({ ...pick, is_live: true }, null, []);
eq(heroPriceSpeech(live, 'Live price'), 'Live price unavailable DraftKings. Locked -112',
   'a live price not loaded yet is not "no current price"');

// The visible caption says when the book last priced it.
const cap = lockedCaptionText(hero);
ok(cap.startsWith('Locked -112 · DK last priced ') && cap.includes('9/5') && cap.endsWith(' ET'), cap);
eq(lockedCaptionText(moved), 'Locked -110', 'a moved price keeps the plain caption');
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_a_stale_card_offers_no_bet():
    """Second review (2026-10-09): with "Now —" and no hand-off, the card
    still offered "Add to betslip" (and the VoiceOver slip action), which
    priced the leg at the September number with its full edge, and still
    printed a stake. A leg already in the slip can still be taken out."""
    card = _read(SRC / "components" / "PickCard.tsx")
    slip = re.search(r"const canSlip =[^;]*;", card).group(0)
    assert "(!heroPrice?.stale || Boolean(inSlip))" in slip and slip.endswith("&& cta.slip;")
    assert re.search(r"const stakeCaption =\s*pick\.signal_type !== 'BET' \|\| preview"
                     r" \|\| paused \|\| heroPrice\?\.stale\s*\?\s*null", card)
    # The words come from the reasons (lib/heroPriceText.ts).
    assert "{priceCheckChipText(check)}" in card and ">Price check<" not in card
    assert "flagged ? priceCheckSpeech(check, heroPrice) : `Edge ${edgeText}`" in card
    assert "heroPrice ? heroPriceSpeech(heroPrice, cta.priceTag) : null" in card
    assert "{lockedCaptionText(heroPrice)}" in card
    markets = _read(LIB / "markets.ts")
    hero = markets[markets.index("export function heroAmericanForPick("):]
    assert "staleSince: at" in hero[:2000]


def test_the_card_applies_the_price_age_rule():
    """The static half, for runners without node."""
    markets = _read(LIB / "markets.ts")
    hero = markets[markets.index("export function heroAmericanForPick("):]
    hero = hero[:hero.index("\nexport function ")]
    assert "priceAge?: PriceAgeContext" in hero
    assert "priceAgeApplies(pick, priceAge)" in hero and "stale: true" in hero
    handoff = markets[markets.index("export function bestHandoffForPick("):]
    assert "freshBookRows(pick, bookRows, priceAge)" in handoff[:2500]
    assert "hero?.stale" in handoff[:2500]
    card = _read(SRC / "components" / "PickCard.tsx")
    assert "const priceAge = priceAgeFor(pick, game, liveState);" in card
    assert "heroAmericanForPick(pick, item.latestOdds, item.bookRows, priceAge)" in card
    pc = _read(LIB / "priceCheck.ts")
    assert "if (!started && stale) reasons.push('stale');" in pc
    ppc = _read(LIB / "pickPriceCheck.ts")
    assert "priceAgeFor(item.pick, item.game ?? null, liveState ?? null, now)" in ppc
    assert "heroAmericanForPick(item.pick, item.latestOdds, item.bookRows, priceAge)" in ppc
    assert "stale: hero?.stale === true" in ppc
    # No known start time, no bound: the scorer's convention.
    assert "if (!(game?.commence_time || pick.game_time)) return { now };" in markets


def test_best_handoff_rerank_is_wired():
    """The static half, for runners without node: the re-rank reads the hero's
    current price, not the record chip's stored one."""
    markets = _read(LIB / "markets.ts")
    assert re.search(r"export function bestHandoffForPick\(", markets)
    assert "hero" in markets[markets.index("export function bestHandoffForPick("):][:3000]
    card = _read(SRC / "components" / "PickCard.tsx")
    assert re.search(r"bestHandoffForPick\(pick, item\.bookRows, heroPrice, priceAge\)", card)


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
    started = re.search(r"<View\s+style=\{styles\.startedLine\}.*?</View>", card, re.S)
    assert started, "no Game started line"
    block = started.group(0)
    assert 'accessibilityRole="text"' in block and 'name="lock-closed"' in block
    assert "onPress" not in block and "Pressable" not in block
    assert re.search(r"startedText: \{[^}]*color: colors\.textSecondary", card)
    assert card.count("cta.priceTag") >= 2 and "kind === 'now' ? 'Now'" not in card
    assert "{priceCheckChipText(check)}" in card and re.search(r"priceCheckChip: \{[^}]*colors\.medSoft", card)
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
    # The card renders lib/lineMovementView, which builds the rows (review, 2026-10-09).
    movement_view = _read(LIB / "lineMovementView.ts")
    assert "recentChanges(" in movement_view and "snaps.slice(-8)" not in movement_view
    assert "view.rows.map(" in movement
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

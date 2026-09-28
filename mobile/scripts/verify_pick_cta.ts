/**
 * Pick CTA after the start, price check, line history, reasoning heading —
 * usability audit PR 3 (H5, H4, M13, M14).
 *
 *   npx tsx scripts/verify_pick_cta.ts
 *
 * Behavioural (runs the logic):
 *   - H5: after a pre-game pick's game starts, no book hand-off, a "Game
 *     started · picked at <decision price> <decision book>" line, "Live price"
 *     for the Now tag, Slip hidden, Track kept; live in-play signals unchanged;
 *   - standing rule: before the start the hand-off is the BEST available book,
 *     never DraftKings-only;
 *   - H4: the price-check band's boundaries (edge > 25pp, |locked − current| >
 *     500 cents, both strict), flagged rows last on the Edge sort only;
 *   - M13: repeated line/price runs collapse, same-minute rows get seconds;
 *   - M14: "Why this bet?" only on a bet.
 * Plus wiring pins for the card, Pick Detail, the board sort and the card copy.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { gameHasStarted } from '../src/lib/format';
import { collapseLineHistory, recentChanges } from '../src/lib/lineHistory';
import { bestHandoffForPick, MODEL_BOOK } from '../src/lib/markets';
import { gameStartedLine, pickCta, reasoningHeading } from '../src/lib/pickCta';
import { priceCheckForItem } from '../src/lib/pickPriceCheck';
import { sortPicks } from '../src/lib/pickSort';
import {
  americanCents,
  centsApart,
  flaggedLast,
  priceCheck,
  PRICE_CHECK_MAX_CENTS,
  PRICE_CHECK_MAX_EDGE,
} from '../src/lib/priceCheck';
import type { BookPricedRow, LatestDkOddsRow, Pick, PickSide } from '../src/types';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function mkPick(over: Partial<Pick> = {}): Pick {
  return {
    pick_id: 1,
    game_id: 'MLB_2026-09-13_NYJ_BUF',
    model_id: 'mlb_over_under',
    sport: 'MLB',
    game_date: '2026-09-13',
    pick_side: 'over' as PickSide,
    pick_label: 'NYJ @ BUF Over 8.5',
    model_probability: 0.58,
    dk_implied_prob: 0.535,
    edge: 0.082,
    dk_odds: -110,
    scored_line: 8.5,
    signal_type: 'BET',
    is_live: false,
    dk_bet_link: 'dk://lock',
    decision_odds: -110,
    decision_edge: 0.082,
    decision_book: 'draftkings',
    line_book: null,
    ...over,
  } as Pick;
}
function latest(over: Partial<LatestDkOddsRow> = {}): LatestDkOddsRow {
  return {
    game_id: 'MLB_2026-09-13_NYJ_BUF',
    game_date: '2026-09-13',
    market: 'totals',
    home_price: null,
    away_price: null,
    spread_home: null,
    total_line: 8.5,
    over_price: -110,
    under_price: -110,
    snapshot_at: '2026-09-13T17:00:00+00:00',
    ...over,
  };
}

// ── H5: game started ────────────────────────────────────────────────────────
const future = new Date(Date.now() + 3 * 3_600_000).toISOString();
const past = new Date(Date.now() - 3_600_000).toISOString();
check('gameHasStarted: a game that has not started is pre', !gameHasStarted({ sport: 'MLB', commence_time: future }));
check('gameHasStarted: the live feed says Live → started', gameHasStarted({ sport: 'MLB', commence_time: future }, { abstract_game_state: 'Live' }));
check('gameHasStarted: past first pitch, no feed → started', gameHasStarted({ sport: 'MLB', commence_time: past }));
check('gameHasStarted: final → started', gameHasStarted({ sport: 'MLB', commence_time: past, home_score: 3, away_score: 2 }));
check('gameHasStarted: a delayed start (feed says Preview) is still pre', !gameHasStarted({ sport: 'MLB', commence_time: past }, { abstract_game_state: 'Preview' }));

const pre = pickCta({ isLive: false, started: false });
check('before the start: hand-off, Slip, Track, "Now"',
  pre.handoff && pre.slip && pre.track && !pre.startedLine && pre.priceTag === 'Now', JSON.stringify(pre));
const after = pickCta({ isLive: false, started: true });
check('after the start: NO hand-off', !after.handoff);
check('after the start: the "Game started" line', after.startedLine);
check('after the start: Slip hidden', !after.slip);
check('after the start: Track kept', after.track);
check('after the start: the tag reads "Live price"', after.priceTag === 'Live price');
const liveSignal = pickCta({ isLive: true, started: true });
check('a live in-play signal keeps its hand-off and Slip (made in-game by design)',
  liveSignal.handoff && liveSignal.slip && !liveSignal.startedLine && liveSignal.priceTag === 'Live price');
check('"Game started · picked at -125 DK"', gameStartedLine(-125, 'DK') === 'Game started · picked at -125 DK', gameStartedLine(-125, 'DK'));
check('"… picked at +215 FAN"', gameStartedLine(215, 'FAN') === 'Game started · picked at +215 FAN');
check('no decision price → just "Game started"', gameStartedLine(null, 'DK') === 'Game started');

// ── standing rule: before the start, the BEST book, never DK-only ──────────
{
  const rows: BookPricedRow[] = [
    { bookmaker: 'draftkings', over_price: -125, total_line: 8.5 },
    { bookmaker: 'fanduel', over_price: -105, total_line: 8.5, over_link: 'fd://best' },
    { bookmaker: 'betmgm', over_price: -115, total_line: 8.5 },
  ];
  const h = bestHandoffForPick(mkPick({ decision_book: 'draftkings' }), rows);
  check('pre-game CTA goes to the best book (FD −105), not DK', h?.bookmaker === 'fanduel' && h.price === -105, JSON.stringify(h));
}
{
  // DK is the record (decided at −110); FanDuel is worse, so DK is the best book.
  const rows: BookPricedRow[] = [{ bookmaker: 'fanduel', over_price: -115, total_line: 8.5 }];
  const h = bestHandoffForPick(mkPick(), rows);
  check('…and DK only when DK IS the best book', h?.bookmaker === MODEL_BOOK && h.price === -110, JSON.stringify(h));
}

// ── H4: price check ─────────────────────────────────────────────────────────
check('display constants: 25pp and 500 cents', PRICE_CHECK_MAX_EDGE === 0.25 && PRICE_CHECK_MAX_CENTS === 500);
check('cents: −110 ↔ +110 is 20', centsApart(-110, 110) === 20);
check('cents: +3300 ↔ −110 is 3,210 (the NYY ML row)', centsApart(3300, -110) === 3210);
check('cents: ±100 both sit at 0', americanCents(100) === 0 && americanCents(-100) === 0);
const P = (edge: number | null, locked: number | null, current: number | null) => priceCheck({ edge, locked, current }).flagged;
check('edge exactly 25pp is NOT flagged', !P(0.25, -110, -110));
check('edge 25.01pp IS flagged', P(0.2501, -110, -110));
check('a big negative edge is not this flag (edge > 25pp only)', !P(-0.4, -110, -110));
check('|locked − current| exactly 500 cents is NOT flagged (−600 vs −100)', !P(0.05, -600, -100));
check('501 cents IS flagged (−601 vs −100)', P(0.05, -601, -100));
check('across even money: +450 vs −151 = 401, not flagged', !P(0.05, 450, -151));
check('no current price → only the edge rule', !P(0.05, 3300, null) && P(0.3, 3300, null));
check('reasons name the rule(s)', JSON.stringify(priceCheck({ edge: 0.548, locked: 3300, current: -110 }).reasons) === '["edge","moved"]');
{
  const nyy = { pick: mkPick({ decision_odds: 3300, dk_odds: 3300, decision_edge: 0.548 }), latestOdds: latest({ over_price: -110 }), bookRows: [] };
  const fine = { pick: mkPick(), latestOdds: latest({ over_price: -115 }), bookRows: [] };
  check('priceCheckForItem flags the +3300 / now −110 row', priceCheckForItem(nyy).flagged);
  check('priceCheckForItem leaves a normal row alone', !priceCheckForItem(fine).flagged);
  const moved = { pick: mkPick({ decision_edge: 0.05 }), latestOdds: latest({ over_price: 700 }), bookRows: [] };
  check('priceCheckForItem: the lock far from the same book’s current price flags (−110 vs +700 = 610c)', priceCheckForItem(moved).flagged);
  const near = { pick: mkPick({ decision_edge: 0.05 }), latestOdds: latest({ over_price: 420 }), bookRows: [] };
  check('priceCheckForItem: −110 vs +420 (330c) is not flagged', !priceCheckForItem(near).flagged);
}
{
  type Row = { pick: Pick; flag: boolean };
  const rows: Row[] = [
    { pick: mkPick({ pick_id: 1, decision_edge: 0.548 }), flag: true },
    { pick: mkPick({ pick_id: 2, decision_edge: 0.178 }), flag: false },
    { pick: mkPick({ pick_id: 3, decision_edge: 0.3 }), flag: true },
    { pick: mkPick({ pick_id: 4, decision_edge: 0.16 }), flag: false },
  ];
  const ids = (xs: Row[]) => xs.map((r) => r.pick.pick_id).join(',');
  check('Edge sort without the flag: edge order', ids(sortPicks(rows, 'edge')) === '1,3,2,4');
  check('Edge sort with the flag: flagged rows LAST, edge order kept in both halves',
    ids(sortPicks(rows, 'edge', { priceCheck: (r) => r.flag })) === '2,4,1,3', ids(sortPicks(rows, 'edge', { priceCheck: (r) => r.flag })));
  check('other sorts ignore the flag', ids(sortPicks(rows, 'sharp', { priceCheck: (r) => r.flag })) === ids(sortPicks(rows, 'sharp')));
  check('flaggedLast is stable', flaggedLast([1, 2, 3, 4, 5], (n) => n % 2 === 0).join(',') === '1,3,5,2,4');
}

// ── M13: line history ───────────────────────────────────────────────────────
{
  const t = (hh: number, mm: number, ss = 0) => `2026-09-25T${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}Z`;
  const runs = collapseLineHistory([
    { at: t(19, 50, 1), line: 8.5, price: -110 },
    { at: t(19, 50, 20), line: 8.5, price: -110 },
    { at: t(19, 50, 40), line: 8.5, price: -110 },
    { at: t(20, 5), line: 8.5, price: -115 },
    { at: t(20, 30), line: 9, price: -105 },
  ]);
  check('repeated line + price collapse into one row', runs.length === 3 && runs[0].count === 3, JSON.stringify(runs.map((r) => r.count)));
  check('distinct minutes print minute precision in ET', runs[0].label === '3:50 PM ET' && runs[1].label === '4:05 PM ET', runs.map((r) => r.label).join(' | '));
  const flicker = collapseLineHistory([
    { at: t(19, 50, 5), line: null, price: -105 },
    { at: t(19, 50, 25), line: null, price: -115 },
    { at: t(19, 50, 45), line: null, price: -105 },
  ]);
  check('rows sharing a minute get seconds', flicker.every((r) => /^3:50:\d\d PM ET$/.test(r.label)), flicker.map((r) => r.label).join(' | '));
  const many = Array.from({ length: 20 }, (_, i) => ({ at: t(18, i), line: null, price: i % 2 ? -110 : -112 }));
  const rc = recentChanges(many, 8);
  check('the card shows the last 8 changes and counts them all', rc.rows.length === 8 && rc.changes === 20);
}

// ── M14: reasoning heading ──────────────────────────────────────────────────
check('BET → "Why this bet?"', reasoningHeading('BET') === 'Why this bet?');
check('NONE → "Why no bet?"', reasoningHeading('NONE') === 'Why no bet?');
check('AVOID → "Why avoid?"', reasoningHeading('AVOID') === 'Why avoid?');
check('a paused or preview BET is not called a bet', reasoningHeading('BET', { paused: true }) === 'Why this pick?' && reasoningHeading('BET', { preview: true }) === 'Why this pick?');

// ── wiring ──────────────────────────────────────────────────────────────────
const card = read('src/components/PickCard.tsx');
check('PickCard: started = gameHasStarted(game, liveState); cta = pickCta(…)',
  /gameHasStarted\(game, liveState\)/.test(card) && /pickCta\(\{ isLive: pick\.is_live === true, started \}\)/.test(card));
check('PickCard: hand-off only while cta.handoff', /offersBook && cta\.handoff\s*\?\s*bestHandoffForPick/.test(card));
check('PickCard: Slip needs cta.slip, Track keeps cta.track', /&& cta\.slip;/.test(card) && /&& open && cta\.track;/.test(card));
const started = card.match(/<View\s+style=\{styles\.startedLine\}[\s\S]*?<\/View>/)?.[0] ?? '';
check('PickCard: the started line is role text, lock icon, not a Pressable',
  /accessibilityRole="text"/.test(started) && /name="lock-closed"/.test(started) && !/Pressable|onPress/.test(started));
check('PickCard: started line is textSecondary', /startedText: \{[\s\S]*?color: colors\.textSecondary/.test(card));
check('PickCard: the tag reads cta.priceTag (Now / Live price)', (card.match(/cta\.priceTag/g) ?? []).length >= 2 && !/kind === 'now' \? 'Now'/.test(card));
check('PickCard: "Price check" chip on medSoft, medInk icon', />Price check</.test(card) && /priceCheckChip: \{[\s\S]*?colors\.medSoft/.test(card) && /alert-circle-outline"[\s\S]{0,80}colors\.medInk/.test(card));
check('PickCard: flagged → "—" for edge and "EV —"', /flagged \? '—' : formatPctSigned\(decisionEdge\(pick\)\)/.test(card) && /flagged \? 'EV —'/.test(card));
check('PickCard: NONE / AVOID edge demoted to a secondary line', /const demoteEdge = pick\.signal_type !== 'BET';/.test(card) && /edgeSecondary: \{[\s\S]*?font\.size\.footnote[\s\S]*?colors\.textSecondary/.test(card));
check('PickCard: a flagged row’s movement line is suppressed', /kind === 'pre' && !flagged/.test(card));
const detail = read('src/screens/PickDetailScreen.tsx');
check('PickDetail: hand-off (BookLinesRow) only while cta.handoff, started line otherwise',
  /cta\.handoff \? \(\s*<View style=\{styles\.linesCard\}>/.test(detail) && /cta\.startedLine && openHere/.test(detail) && /gameStartedLine\(decisionOdds\(pick\), bookLabel\(storedQuoteBook\(pick\)\)\)/.test(detail));
check('PickDetail: betslip card needs cta.slip; Track unchanged', /&& !voided && cta\.slip \?/.test(detail) && /const canTrack = openHere;/.test(detail));
check('ReasoningCard: heading from reasoningHeading', /reasoningHeading\(pick\.signal_type/.test(read('src/components/ReasoningCard.tsx')) && !/>Why this bet\?</.test(read('src/components/ReasoningCard.tsx')));
check('LineMovementCard: rows from recentChanges', /recentChanges\(/.test(read('src/components/LineMovementCard.tsx')) && !/snaps\.slice\(-8\)/.test(read('src/components/LineMovementCard.tsx')));
const home = read('src/screens/PicksHomeScreen.tsx');
check('PicksHome: Edge sort passes the price check', /sortPicks\(filtered, sortKey, \{ priceCheck: \(d\) => priceCheckForItem\(d\)\.flagged \}\)/.test(home));
const pc = read('src/lib/priceCheck.ts');
check('priceCheck.ts: pure, and says it is a display heuristic only', !/^import /m.test(pc) && /DISPLAY HEURISTICS ONLY/.test(pc) && /MAX_EDGE_CAP/.test(pc));
check('the thresholds live only in priceCheck.ts', !/PRICE_CHECK_MAX_(EDGE|CENTS)\s*=/.test(card + detail + home));

console.log(failures ? `\n${failures} FAILED` : '\nALL PASS');
process.exit(failures ? 1 : 0);

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
 *
 * Reviewer REQUEST CHANGES at 7f3f573d (#847), pinned below:
 *   - H5 on Pick Detail: AllBooksCard (every row opens a betslip) goes with
 *     the hand-off after the start;
 *   - the moved-price rule is skipped in-play (the hero Now is the live price);
 *   - the started line is not gated on paused (no NEW paused gating);
 *   - the best-book CTA re-ranks by the record book's CURRENT price;
 *   - gameHasStarted falls back to pick.game_time (fails closed);
 *   - a game called off before first pitch is not "Game started"; "Live
 *     price" only while in play; line history counts moves only, joins
 *     mid-run nulls, and keys rows uniquely.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { gameHasStarted, gameStartState } from '../src/lib/format';
import { changesFooter, collapseLineHistory, recentChanges } from '../src/lib/lineHistory';
import { bestHandoffForPick, heroAmericanForPick, MODEL_BOOK } from '../src/lib/markets';
import { gameStartedLine, pickCta, pickCtaFor, reasoningHeading } from '../src/lib/pickCta';
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
// Reviewer #847 M6: fail CLOSED when the games row or commence_time is missing.
check('gameHasStarted: no games row, pick.game_time past → started', gameHasStarted(null, null, past));
check('gameHasStarted: games row without commence_time, game_time past → started', gameHasStarted({ sport: 'MLB', commence_time: null }, null, past));
check('gameHasStarted: no games row, game_time ahead → pre', !gameHasStarted(null, null, future));
check('gameHasStarted: nothing known at all → pre', !gameHasStarted(null, null, null));
check('gameHasStarted: the games row’s commence_time wins over game_time', !gameHasStarted({ sport: 'MLB', commence_time: future }, null, past));
// Low: a game called off before first pitch never "started".
const finalNoScore = { abstract_game_state: 'Final', home_score: null, away_score: null };
check('postponed: Final with no score and the start still ahead → postponed', gameStartState({ sport: 'MLB', commence_time: future }, finalNoScore) === 'postponed');
check('postponed: …is not "started"', !gameHasStarted({ sport: 'MLB', commence_time: future }, finalNoScore));
check('postponed: via game_time when the games row is missing', gameStartState(null, finalNoScore, future) === 'postponed');
check('Final with no score AFTER the start → over (ended), still started', gameStartState({ sport: 'MLB', commence_time: past }, finalNoScore) === 'over');
check('Final with a score → over', gameStartState({ sport: 'MLB', commence_time: past }, { abstract_game_state: 'Final', home_score: 3, away_score: 2 }) === 'over');
check('the feed says Live → live', gameStartState({ sport: 'MLB', commence_time: past }, { abstract_game_state: 'Live' }) === 'live');

const pre = pickCta({ isLive: false, started: false });
check('before the start: hand-off, Slip, Track, "Now"',
  pre.handoff && pre.slip && pre.track && !pre.startedLine && pre.priceTag === 'Now', JSON.stringify(pre));
const after = pickCta({ isLive: false, started: true, inPlay: true });
check('after the start: NO hand-off', !after.handoff);
check('after the start: the "Game started" line', after.startedLine);
check('after the start: Slip hidden', !after.slip);
check('after the start: Track kept', after.track);
check('after the start: the tag reads "Live price"', after.priceTag === 'Live price');
const liveSignal = pickCta({ isLive: true, started: true, inPlay: true });
check('a live in-play signal keeps its hand-off and Slip (made in-game by design)',
  liveSignal.handoff && liveSignal.slip && !liveSignal.startedLine && liveSignal.priceTag === 'Live price');
check('"Game started · picked at -125 DK"', gameStartedLine(-125, 'DK') === 'Game started · picked at -125 DK', gameStartedLine(-125, 'DK'));
check('"… picked at +215 FAN"', gameStartedLine(215, 'FAN') === 'Game started · picked at +215 FAN');
check('no decision price → just "Game started"', gameStartedLine(null, 'DK') === 'Game started');
// Low: "Live price" only while IN PLAY, not on a final game.
check('a final game’s price tag is "Now", not "Live price"', pickCta({ isLive: false, started: true, inPlay: false }).priceTag === 'Now');
const ctaPick = mkPick({ game_time: past });
check('pickCtaFor: final (scores in) → no hand-off, started line, tag "Now"', (() => {
  const c = pickCtaFor(ctaPick, { sport: 'MLB', commence_time: past, home_score: 3, away_score: 2 }, null);
  return !c.handoff && c.startedLine && c.priceTag === 'Now';
})());
check('pickCtaFor: in play → "Live price"', pickCtaFor(ctaPick, { sport: 'MLB', commence_time: past }, { abstract_game_state: 'Live' }).priceTag === 'Live price');
check('pickCtaFor: no games row, game_time past → started line, no hand-off (fails closed)', (() => {
  const c = pickCtaFor(ctaPick, null, null);
  return !c.handoff && !c.slip && c.startedLine;
})());
const called = pickCtaFor(mkPick({ game_time: future }), { sport: 'MLB', commence_time: future }, finalNoScore);
check('pickCtaFor: postponed → no "Game started", no hand-off, no Slip, Track kept',
  !called.startedLine && !called.handoff && !called.slip && called.track && called.priceTag === 'Now', JSON.stringify(called));

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
{
  // Reviewer #847 M4: record DK −110, now DK −130, FD −115. The record chip
  // wins the ranking at its STORED price; the same-book swap then said
  // "Bet DK −130". Re-ranked by DK's current price, FD −115 wins.
  const pick = mkPick({ decision_book: 'draftkings', decision_odds: -110 });
  const rows: BookPricedRow[] = [
    { bookmaker: 'draftkings', over_price: -130, total_line: 8.5 },
    { bookmaker: 'fanduel', over_price: -115, total_line: 8.5, over_link: 'fd://now' },
  ];
  const lo = latest({ over_price: -130 });
  const hero = heroAmericanForPick(pick, lo, rows);
  check('M4 setup: hero is Now DK −130', hero?.kind === 'now' && hero.price === -130 && hero.book === MODEL_BOOK, JSON.stringify(hero));
  const h = bestHandoffForPick(pick, rows, hero);
  check('M4: record DK −110 / now DK −130 / FD −115 → hand-off FD −115 ("Best"), never "Bet DK −130"',
    h?.bookmaker === 'fanduel' && h.price === -115 && h.verb === 'Best' && h.link === 'fd://now', JSON.stringify(h));
  // Still DK when DK's CURRENT price is the best one.
  const lo2 = latest({ over_price: -112 });
  const rows2: BookPricedRow[] = [{ bookmaker: 'draftkings', over_price: -112, total_line: 8.5 }, { bookmaker: 'fanduel', over_price: -115, total_line: 8.5 }];
  const h2 = bestHandoffForPick(pick, rows2, heroAmericanForPick(pick, lo2, rows2));
  check('M4: DK now −112 beats FD −115 → "Bet DK −112" (the current number)', h2?.bookmaker === MODEL_BOOK && h2.price === -112 && h2.verb === 'Bet', JSON.stringify(h2));
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
  // Reviewer #847 M2: after the start the hero Now is the IN-PLAY price.
  check('in-play: priceCheck({ edge: .05, locked: −150, current: +700 }) pre-game IS flagged', P(0.05, -150, 700));
  check('in-play: …with started, the moved rule is skipped', !priceCheck({ edge: 0.05, locked: -150, current: 700, started: true }).flagged);
  check('in-play: the edge rule still applies after the start', priceCheck({ edge: 0.3, locked: -150, current: 700, started: true }).flagged);
  const inPlay = { pick: mkPick({ decision_edge: 0.05, decision_odds: -150, dk_odds: -150, is_live: true }), latestOdds: latest({ over_price: 700 }), bookRows: [] };
  check('priceCheckForItem: an in-play signal −150 vs now +700 is not flagged', !priceCheckForItem(inPlay).flagged);
  const startedGame = { pick: mkPick({ decision_edge: 0.05, decision_odds: -150, dk_odds: -150 }), game: { commence_time: past, sport: 'MLB' } as never, latestOdds: latest({ over_price: 700 }), bookRows: [] };
  check('priceCheckForItem: a pre-game pick whose game started (−150 vs now +700) is not flagged', !priceCheckForItem(startedGame).flagged);
  check('priceCheckForItem: …nor when the games row is missing and game_time has passed',
    !priceCheckForItem({ ...startedGame, game: null, pick: { ...startedGame.pick, game_time: past } }).flagged);
  check('priceCheckForItem: the live feed decides too (Live snapshot)',
    !priceCheckForItem({ ...startedGame, game: { commence_time: future, sport: 'MLB' } as never }, { abstract_game_state: 'Live', home_score: 1, away_score: 0 }).flagged);
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
  check('the card shows the last 8 rows and counts every CHANGE (the opening row is not one)',
    rc.rows.length === 8 && rc.changes === 19 && rc.shownChanges === 8 && rc.hidden === 12, JSON.stringify({ c: rc.changes, s: rc.shownChanges, h: rc.hidden }));
  // Reviewer #847 lows.
  const one = recentChanges([{ at: t(18, 0), line: 8.5, price: -110 }, { at: t(18, 30), line: 8.5, price: -115 }]);
  check('M13: opening + one move = 1 change, not 2', one.changes === 1 && one.rows[0].opening && !one.rows[1].opening);
  check('M13: an unmoved line is 0 changes', recentChanges([{ at: t(18, 0), line: 8.5, price: -110 }, { at: t(18, 5), line: 8.5, price: -110 }]).changes === 0);
  const gap = collapseLineHistory([
    { at: t(18, 0), line: 8.5, price: -110 },
    { at: t(18, 5), line: 8.5, price: null },
    { at: t(18, 10), line: null, price: -110 },
    { at: t(18, 15), line: 8.5, price: -110 },
  ]);
  check('M13: partial snapshots are unknown — no "N/A" row, not counted in the run', gap.length === 1 && gap[0].count === 2, JSON.stringify(gap.map((r) => [r.line, r.price, r.count])));
  // Reviewer #847 approval: per-field carry invented 9.0 @ −110.
  const invent = collapseLineHistory([
    { at: t(18, 0), line: 8.5, price: -110 },
    { at: t(18, 5), line: 9, price: null },
    { at: t(18, 10), line: 9, price: -115 },
  ]);
  check('M13: a partial row never borrows the other field (no invented 9 @ −110)',
    invent.length === 2 && !invent.some((r) => r.line === 9 && r.price === -110) && invent[1].line === 9 && invent[1].price === -115, JSON.stringify(invent.map((r) => [r.line, r.price])));
  const blank = collapseLineHistory([
    { at: t(18, 0), line: 8.5, price: -110 },
    { at: t(18, 5), line: null, price: null },
    { at: t(18, 10), line: 8.5, price: -110 },
  ]);
  check('M13: a snapshot with BOTH null is a feed gap and joins the run', blank.length === 1 && blank[0].count === 3);
  const ml = collapseLineHistory([{ at: t(18, 0), line: null, price: -110 }, { at: t(18, 5), line: null, price: -120 }]);
  check('M13: a field no snapshot has (moneyline line) is untracked, not "partial"', ml.length === 2);
  const nine = recentChanges(Array.from({ length: 9 }, (_, i) => ({ at: t(18, i), line: null, price: i % 2 ? -110 : -112 })), 8);
  check('footer: only the opening hidden → "8 changes · opening not shown", not "Last 8 of 8"',
    changesFooter(nine, 9) === '8 changes · opening not shown · 9 snapshots', changesFooter(nine, 9));
  check('footer: changes really cut → "Last 8 of 19 changes"', changesFooter(rc, 20) === 'Last 8 of 19 changes · 20 snapshots', changesFooter(rc, 20));
  check('footer: nothing hidden → "1 change"', changesFooter(one, 2) === '1 change · 2 snapshots');
  const same = collapseLineHistory([
    { at: t(18, 0), line: null, price: -110 },
    { at: t(18, 0), line: null, price: -115 },
    { at: t(18, 0), line: null, price: -110 },
  ]);
  check('M13: same-timestamp rows get unique keys', new Set(same.map((r) => r.key)).size === same.length && same.length === 3);
}

// ── M14: reasoning heading ──────────────────────────────────────────────────
check('BET → "Why this bet?"', reasoningHeading('BET') === 'Why this bet?');
check('NONE → "Why no bet?"', reasoningHeading('NONE') === 'Why no bet?');
check('AVOID → "Why avoid?"', reasoningHeading('AVOID') === 'Why avoid?');
check('a preview BET is not called a bet', reasoningHeading('BET', { preview: true }) === 'Why this pick?');

// ── wiring ──────────────────────────────────────────────────────────────────
const card = read('src/components/PickCard.tsx');
check('PickCard: cta = pickCtaFor(pick, game, liveState) (game_time fallback, postponed, in-play tag)',
  /const cta = pickCtaFor\(pick, game, liveState\);/.test(card) && !/gameHasStarted\(game, liveState\)\s*;/.test(card));
check('PickCard: the price check reads the live snapshot', /priceCheckForItem\(item, liveState\)/.test(card));
check('LineMovementCard: footer is changesFooter (no "Last 8 of 8")', /changesFooter\(\{ changes, shownChanges, hidden \}, snaps\.length\)/.test(read('src/components/LineMovementCard.tsx')));
check('PickCard: hand-off only while cta.handoff', /offersBook && cta\.handoff\s*\?\s*bestHandoffForPick/.test(card));
check('PickCard: canSlip ends with cta.slip, canTrack with cta.track',
  /const canSlip =[^;]*&& cta\.slip;/.test(card) && /const canTrack = [^;]*&& open && cta\.track;/.test(card));
const startedDef = card.match(/const startedText =[^;]*;/)?.[0] ?? '';
check('PickCard: the started line is NOT gated on paused (no new paused gating)',
  /pick\.signal_type === 'BET' && !preview && open && cta\.startedLine/.test(startedDef) && !/paused|offersBook/.test(startedDef), startedDef.replace(/\s+/g, ' ').slice(0, 120));
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
check('PickDetail: cta = pickCtaFor(pick, game, liveState)', /const cta = pickCtaFor\(pick, game, liveState\);/.test(detail));
check('PickDetail: AllBooksCard (rows open betslips) hidden when !cta.handoff (H5)',
  /\{live \|\| !cta\.handoff \? null : <AllBooksCard\b/.test(detail) && (detail.match(/<AllBooksCard\b/g) ?? []).length === 1);
check('PickDetail: the started line is NOT gated on paused',
  /\{pick\.signal_type === 'BET' && !preview && !retired && !voided && cta\.startedLine && openHere \? \(/.test(detail));
check('ReasoningCard: heading from reasoningHeading', /reasoningHeading\(pick\.signal_type/.test(read('src/components/ReasoningCard.tsx')) && !/>Why this bet\?</.test(read('src/components/ReasoningCard.tsx')));
check('LineMovementCard: rows from recentChanges', /recentChanges\(/.test(read('src/components/LineMovementCard.tsx')) && !/snaps\.slice\(-8\)/.test(read('src/components/LineMovementCard.tsx')));
const home = read('src/screens/PicksHomeScreen.tsx');
check('PicksHome: Edge sort passes the price check, with the live snapshot',
  /priceCheck: \(d\) => priceCheckForItem\(d, liveStates\.get\(d\.pick\.game_id\) \?\? null\)\.flagged/.test(home));
check('LineMovementCard: rows keyed by r.key (timestamps can repeat)', /key=\{r\.key\}/.test(read('src/components/LineMovementCard.tsx')) && !/key=\{r\.at\}/.test(read('src/components/LineMovementCard.tsx')));
const pc = read('src/lib/priceCheck.ts');
check('priceCheck.ts: pure, and says it is a display heuristic only', !/^import /m.test(pc) && /DISPLAY HEURISTICS ONLY/.test(pc) && /MAX_EDGE_CAP/.test(pc));
check('the thresholds live only in priceCheck.ts', !/PRICE_CHECK_MAX_(EDGE|CENTS)\s*=/.test(card + detail + home));

console.log(failures ? `\n${failures} FAILED` : '\nALL PASS');
process.exit(failures ? 1 : 0);

/**
 * Denser PickCard helpers: Now vs Locked, the one-book CTA, and the
 * decision-price slip / movement gates.
 *
 * Run: npx tsx scripts/verify_pick_card.ts
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { hasPricedLine } from '../src/lib/decisionPrice';
import {
  bestHandoffForPick,
  canShowLineMovementHistory,
  computeMovement,
  formatSideLine,
  heroAmericanForPick,
  historyBookForPick,
  isNflLineOnly,
  movementFromLatest,
  movementFromSameBookHistory,
  MODEL_BOOK,
} from '../src/lib/markets';
import type { BookPricedRow, LatestDkOddsRow, Pick, PickSide } from '../src/types';

let failed = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failed++;
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
    over_price: -115,
    under_price: -105,
    snapshot_at: '2026-09-13T17:00:00+00:00',
    ...over,
  };
}

// ── hasPricedLine ───────────────────────────────────────────────────────────
check('DK-priced row is priced', hasPricedLine(mkPick()));
check(
  'decision-priced non-DK prop is priced',
  hasPricedLine(mkPick({ dk_odds: null, decision_odds: -105, decision_book: 'fanduel', line_book: 'fanduel' })),
);
check('prob-only is not priced', !hasPricedLine(mkPick({ dk_odds: null, decision_odds: null })));

// ── heroAmericanForPick ─────────────────────────────────────────────────────
{
  const h = heroAmericanForPick(mkPick(), latest({ over_price: -110 }));
  check('pre-game unmoved → decision (no Now tag)', h?.kind === 'decision' && h.price === -110 && !h.showLockedCaption);
}
{
  const h = heroAmericanForPick(mkPick(), latest({ over_price: -115 }));
  check(
    'pre-game moved → Now + Locked caption',
    h?.kind === 'now' && h.price === -115 && h.showLockedCaption && h.lockedPrice === -110,
  );
}
{
  const h = heroAmericanForPick(
    mkPick({ is_live: true }),
    latest({ over_price: -115 }),
    [{ bookmaker: 'draftkings', over_price: -115, total_line: 8.5, over_link: 'dk://now' }],
  );
  check(
    'live with current → Now, lock is caption',
    h?.kind === 'now' && h.price === -115 && h.showLockedCaption && h.lockedPrice === -110,
  );
}
{
  const h = heroAmericanForPick(mkPick({ is_live: true }), null, []);
  check(
    'live with no snapshot → Now empty, lock is caption only',
    h?.kind === 'now' && h.price === null && h.showLockedCaption && h.lockedPrice === -110,
  );
}
{
  const h = heroAmericanForPick(
    mkPick({ is_live: true }),
    latest({ over_price: -110 }),
  );
  check(
    'live Now equals lock → labeled Now, Locked caption still on',
    h?.kind === 'now' && h.price === -110 && h.showLockedCaption,
  );
}

// ── bestHandoffForPick ──────────────────────────────────────────────────────
{
  const rows: BookPricedRow[] = [
    { bookmaker: 'draftkings', over_price: -125, total_line: 8.5 },
    { bookmaker: 'fanduel', over_price: 105, total_line: 8.5, over_link: 'fd://best' },
  ];
  const h = bestHandoffForPick(mkPick(), rows);
  check(
    'pre-game CTA is Best FD when FD beats the record',
    h?.verb === 'Best' && h.bookmaker === 'fanduel' && h.price === 105,
  );
}
{
  const rows: BookPricedRow[] = [
    { bookmaker: 'draftkings', over_price: -125, total_line: 8.5 },
  ];
  const hero = heroAmericanForPick(mkPick(), latest({ over_price: -115 }));
  const h = bestHandoffForPick(mkPick(), rows, hero);
  check(
    'pre-game same-book CTA uses Now, not the lock',
    hero?.kind === 'now' && h?.bookmaker === MODEL_BOOK && h.price === -115,
  );
}
{
  const h = bestHandoffForPick(mkPick({ is_live: true }), [], {
    kind: 'now',
    price: -115,
    book: MODEL_BOOK,
    line: 8.5,
    link: 'dk://now',
    lockedPrice: -110,
    showLockedCaption: true,
  });
  check(
    'live CTA is Bet DK at the Now price',
    h?.verb === 'Bet' && h.bookmaker === MODEL_BOOK && h.price === -115 && h.link === 'dk://now',
  );
}
{
  const liveQuotes = bestHandoffForPick(
    mkPick({ is_live: true }),
    [{ bookmaker: 'fanduel', over_price: 120, total_line: 8.5 }],
  );
  check(
    'live CTA ignores other books even if they are cheaper',
    liveQuotes?.bookmaker === MODEL_BOOK,
  );
}
{
  const hero = heroAmericanForPick(mkPick({ is_live: true }), null, []);
  const h = bestHandoffForPick(mkPick({ is_live: true }), [], hero);
  check(
    'live CTA falls back to the lock when Now has no snapshot',
    hero?.kind === 'now' && hero.price === null && h?.verb === 'Bet' && h.price === -110,
  );
}

// ── movementFromLatest keys off decision price, same book ───────────────────
{
  const m = movementFromLatest(
    mkPick({ dk_odds: null, decision_odds: -110, decision_book: 'draftkings' }),
    latest({ over_price: -140 }),
  );
  check('DK decision without dk_odds still flags steam', m?.severity === 'caution');
}
{
  const m = movementFromLatest(
    mkPick({
      dk_odds: null,
      decision_odds: -110,
      decision_book: 'fanduel',
      line_book: 'fanduel',
    }),
    latest({ over_price: -140 }),
  );
  check('FD lock vs DK snapshot is not movement', m === null);
}
{
  const m = movementFromLatest(
    mkPick({
      dk_odds: null,
      decision_odds: -110,
      decision_book: 'fanduel',
      line_book: 'fanduel',
    }),
    null,
    [{ bookmaker: 'fanduel', over_price: -140, total_line: 8.5 }],
  );
  check('FD lock vs FD snapshot is steam', m?.severity === 'caution' && m.scoredPrice === -110);
}

check(
  'away spread Now line is side-flipped, not the home number',
  formatSideLine(-4.5, 'away', 'spreads') === '+4.5',
);

// ── same-book history: fetch book === lock book ────────────────────────────
{
  const fd = mkPick({
    model_id: 'mlb_prop_batter_hits',
    dk_odds: -110,
    decision_odds: -105,
    decision_book: 'fanduel',
    line_book: 'fanduel',
  });
  const snap = latest({ over_price: -140 });
  check('off-DK PROP is not lineOnly', !isNflLineOnly(fd.model_id));
  check('off-DK PROP history book is FanDuel, not DK', historyBookForPick(fd) === 'fanduel');
  check('off-DK PROP can open history (at FanDuel)', canShowLineMovementHistory(fd));
  const sameBook = movementFromSameBookHistory(fd, snap, 'totals');
  check(
    'same-book path steams an FD lock vs an FD snapshot at scoredPrice −105',
    sameBook?.severity === 'caution' && sameBook.scoredPrice === -105,
  );
  const naive = computeMovement(fd, snap, 'totals');
  check(
    'naive computeMovement also uses decisionOdds (trap if the snap is DK)',
    naive?.severity === 'caution' && naive.scoredPrice === -105,
  );
}
{
  const dk = mkPick({
    dk_odds: -110,
    decision_odds: -110,
    decision_book: 'draftkings',
  });
  check('DK history book is DraftKings', historyBookForPick(dk) === MODEL_BOOK);
  check(
    'same-book path steams a DK pick against DK now',
    movementFromSameBookHistory(dk, latest({ over_price: -140 }), 'totals')?.severity === 'caution',
  );
}
{
  const unpriced = mkPick({
    dk_odds: null,
    decision_odds: null,
    decision_book: null,
  });
  check('unpriced pick has no history book', historyBookForPick(unpriced) === null);
  check('unpriced pick does not open the history card', !canShowLineMovementHistory(unpriced));
}

{
  const cardSrc = readFileSync(join(__dirname, '../src/components/LineMovementCard.tsx'), 'utf-8');
  check(
    'LineMovementCard fetch uses historyBook, not MODEL_BOOK',
    cardSrc.includes('historyBookForPick') &&
      cardSrc.includes('fetchOddsHistory(pick.game_id, market, historyBook)') &&
      !cardSrc.includes('MODEL_BOOK'),
  );
  const qSrc = readFileSync(join(__dirname, '../src/lib/queries.ts'), 'utf-8');
  const hist = qSrc.slice(
    qSrc.indexOf('export async function fetchOddsHistory'),
    qSrc.indexOf('export async function fetchSavantStats'),
  );
  check(
    'history fetches have no draftkings literal',
    hist.includes(".eq('bookmaker', bookmaker)") && !hist.includes("'draftkings'"),
  );
}

console.log(failed === 0 ? '\nALL PASS' : `\n${failed} FAILURE(S)`);
if (failed > 0) process.exit(1);

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
  playerNameFromPickLabel,
  splitPickTitle,
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
  const mlbFd = mkPick({
    model_id: 'mlb_over_under',
    pick_side: 'over',
    scored_line: 8.5,
    decision_odds: -110,
    decision_book: 'fanduel',
    line_book: null,
    dk_odds: -110,
  });
  const fdTotalNine = latest({ total_line: 9.0, over_price: -110 });
  const naiveLine = computeMovement(mlbFd, fdTotalNine, 'totals');
  check(
    'without the line-book gate, FD 9.0 vs scored 8.5 Over is SKIP',
    naiveLine?.severity === 'skip',
  );
  const gated = movementFromSameBookHistory(mlbFd, fdTotalNine, 'totals');
  check(
    'MLB totals FD decision, line_book null, FD 9.0 vs scored 8.5 is not a line SKIP',
    gated === null || gated.severity !== 'skip',
  );
  const board = movementFromLatest(mlbFd, null, [
    { bookmaker: 'fanduel', total_line: 9.0, over_price: -110 },
  ]);
  check(
    'board path: FD 9.0 vs scored 8.5 via bookRows is not a line SKIP',
    board === null || board.severity !== 'skip',
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

// ── splitPickTitle (PickCard two-line prop titles) ─────────────────────────
{
  const prop = splitPickTitle({ pick_label: 'Roquan Smith Under 9.5 Tackles' });
  check(
    'prop primary is the bet only',
    prop.primary === 'Under 9.5 Tackles' && prop.secondary === 'Roquan Smith',
  );
  check(
    'prop parser and split agree on the player',
    playerNameFromPickLabel('Roquan Smith Under 9.5 Tackles') === prop.secondary,
  );
}
{
  const suffix = splitPickTitle({ pick_label: 'Jadarian Price Over 1.5 Rec (FD)' });
  check(
    'prop keeps the stored suffix on the bet line',
    suffix.primary === 'Over 1.5 Rec (FD)' && suffix.secondary === 'Jadarian Price',
  );
}
{
  const jr = splitPickTitle({ pick_label: "Ja'Marr Chase Over 4.5 Rec" });
  check(
    "apostrophe names stay on the caption line",
    jr.primary === 'Over 4.5 Rec' && jr.secondary === "Ja'Marr Chase",
  );
}
{
  const jose = splitPickTitle({ pick_label: 'José Soriano Over 4.5 Ks' });
  check(
    'accented given name splits',
    jose.primary === 'Over 4.5 Ks' && jose.secondary === 'José Soriano',
  );
}
{
  const acuna = splitPickTitle({ pick_label: 'Ronald Acuña Jr. Under 0.5 Runs' });
  check(
    'accented surname + Jr. splits',
    acuna.primary === 'Under 0.5 Runs' && acuna.secondary === 'Ronald Acuña Jr.',
  );
}
{
  const gameMl = splitPickTitle({ pick_label: 'NYY ML' });
  check('moneyline stays a single pick_label', gameMl.primary === 'NYY ML' && gameMl.secondary === null);
}
{
  const spread = splitPickTitle({ pick_label: 'BUF +1' });
  check('spread stays a single pick_label', spread.primary === 'BUF +1' && spread.secondary === null);
}
{
  const totalVs = splitPickTitle({ pick_label: 'NYY vs BOS Over 8.5' });
  check(
    'game total with vs is not split (regex also matches Over/Under)',
    totalVs.primary === 'NYY vs BOS Over 8.5' && totalVs.secondary === null,
  );
}
{
  const totalAt = splitPickTitle({ pick_label: 'NYJ @ BUF Over 8.5' });
  check(
    'game total with @ stays a single pick_label',
    totalAt.primary === 'NYJ @ BUF Over 8.5' && totalAt.secondary === null,
  );
}
{
  const live = splitPickTitle({ pick_label: 'Over 9.5 (live)' });
  check(
    'live total with no player prefix stays a single pick_label',
    live.primary === 'Over 9.5 (live)' && live.secondary === null,
  );
}
{
  const src = readFileSync(join(__dirname, '../src/components/PickCard.tsx'), 'utf-8');
  check('PickCard titles through splitPickTitle', src.includes('splitPickTitle'));
  check(
    'PickCard a11y still announces the stored pick_label',
    /accessibilityLabel=\{\[[\s\S]*?pick\.pick_label/.test(src),
  );
  check(
    'PickCard does not write pick_label',
    !/pick\.pick_label\s*=/.test(src),
  );
  check(
    'prop bet shrink floor stays above the caption (0.75 × 17 > 12)',
    /minimumFontScale:\s*0\.75/.test(src),
  );
}

console.log(failed === 0 ? '\nALL PASS' : `\n${failed} FAILURE(S)`);
if (failed > 0) process.exit(1);

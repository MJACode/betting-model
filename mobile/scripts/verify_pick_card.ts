/**
 * Denser PickCard helpers: Now vs Locked, the one-book CTA, and the
 * decision-price slip / movement gates.
 *
 * Run: npx tsx scripts/verify_pick_card.ts
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { hasPricedLine } from '../src/lib/decisionPrice';
import { historyFrom, sincePick } from '../src/lib/lineHistory';
import { lineMovementView } from '../src/lib/lineMovementView';
import {
  allBooksLineSource,
  bestHandoffForPick,
  bookLabel,
  bookName,
  canShowLineMovementHistory,
  computeMovement,
  formatSideLine,
  heroAmericanForPick,
  historyBookForPick,
  isNflLineOnly,
  movementFromLatest,
  movementFromSameBookHistory,
  lockedLineAtHistoryBook,
  playerNameFromPickLabel,
  snapshotMatchesLock,
  splitPickTitle,
  MODEL_BOOK,
} from '../src/lib/markets';
import { heroPriceSpeech, lockedCaptionText } from '../src/lib/heroPriceText';
import { formatAmerican, gameStatus, MINUS } from '../src/lib/format';
import {
  signalsBetHeadline,
  signalsCardSpeech,
  signalsContextLine,
  signalsContextTime,
  signalsCtaLabel,
  signalsCtaSpeech,
  signalsHeroSpeech,
  signalsModelCaption,
  signalsNowLine,
  signalsPriceText,
  signalsReasonLine,
  signalsStakeLine,
  signalsStakeSpeech,
} from '../src/lib/signalsCard';
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
  check('a price move at the same line does not set movedLine', h?.movedLine == null && h?.line === 8.5);
}
{
  // Line moved, price unchanged. The board pill stays the lock (kind
  // decision, line is the scored line). Signals reads movedLine.
  const pick = mkPick({
    model_id: 'ncaaf_spread',
    sport: 'NCAAF',
    pick_side: 'home',
    pick_label: 'Sam Houston -7.5',
    scored_line: -7.5,
    dk_odds: -110,
    decision_odds: -110,
    decision_book: 'draftkings',
  });
  const row = latest({
    market: 'spreads',
    spread_home: -8.5,
    total_line: null,
    home_price: -110,
    away_price: -110,
    over_price: null,
    under_price: null,
  });
  const hero = heroAmericanForPick(pick, row, [
    { bookmaker: 'draftkings', home_price: -110, away_price: -110, spread_home: -8.5 },
  ]);
  check(
    'line-only move stays a decision hero and records the current line',
    hero?.kind === 'decision' && hero.price === -110 && hero.line === -7.5 && hero.movedLine === -8.5,
    JSON.stringify(hero),
  );
  const sideLine = formatSideLine(hero?.movedLine ?? null, pick.pick_side, 'spreads');
  const screenNow = signalsNowLine({
    line: sideLine,
    price: formatAmerican(hero?.price),
    priceDiffers: false,
    book: bookLabel(hero?.book ?? ''),
  });
  const spokenNow = signalsNowLine({
    line: sideLine,
    price: formatAmerican(hero?.price),
    priceDiffers: false,
    book: bookName(hero?.book ?? ''),
  });
  check('Signals shows the moved line under the hero', screenNow === `DK line now ${MINUS}8.5 (${MINUS}110)`, screenNow ?? '');
  const speech = signalsHeroSpeech({
    decisionPrice: formatAmerican(hero?.lockedPrice),
    book: bookName(hero?.book ?? ''),
    now: spokenNow,
  });
  check(
    'VoiceOver says that same Now line, with the full book name',
    speech === `${MINUS}110 DraftKings. DraftKings line now ${MINUS}8.5 (${MINUS}110)` &&
      speech.includes(spokenNow ?? 'missing'),
    speech,
  );
  const handoff = bestHandoffForPick(pick, [
    { bookmaker: 'draftkings', home_price: -110, away_price: -110, spread_home: -8.5 },
  ], hero);
  check(
    'line-only move is a Now handoff with kind still decision: no current slip link, so Open DK',
    handoff?.bookmaker === 'draftkings' && handoff.price == null && handoff.link == null && handoff.verb === 'Open' &&
      signalsCtaLabel(bookLabel(handoff.bookmaker), null) === 'Open DK',
    JSON.stringify(handoff),
  );
  const linked = bestHandoffForPick(pick, [
    { bookmaker: 'draftkings', home_price: -110, away_price: -110, spread_home: -8.5, home_link: 'dk://now-8.5' },
  ], hero);
  check(
    'line-only move with a current slip link names the line and uses that link',
    linked?.bookmaker === 'draftkings' && linked.price === -110 && linked.link === 'dk://now-8.5' && linked.verb === 'Bet' &&
      signalsCtaLabel(bookLabel(linked.bookmaker), formatAmerican(linked.price), sideLine) ===
        `Bet DK ${MINUS}8.5 ${MINUS}110`,
    JSON.stringify(linked),
  );
  const shop = bestHandoffForPick(pick, [
    { bookmaker: 'draftkings', home_price: -110, away_price: -110, spread_home: -8.5 },
    { bookmaker: 'betmgm', home_price: -112, away_price: -108, spread_home: -7.5, home_link: 'mgm://7.5' },
  ], hero);
  check(
    'line-only move prefers a book still at the scored line',
    shop?.bookmaker === 'betmgm' && shop.price === -112 && shop.link === 'mgm://7.5',
    JSON.stringify(shop),
  );
}
{
  // Price and line both moved, and the button is that current DK quote.
  const pick = mkPick({
    model_id: 'ncaaf_spread',
    sport: 'NCAAF',
    pick_side: 'home',
    pick_label: 'Sam Houston -7.5',
    scored_line: -7.5,
    dk_odds: -110,
    decision_odds: -110,
    decision_book: 'draftkings',
  });
  const row = latest({
    market: 'spreads',
    spread_home: -8.5,
    total_line: null,
    home_price: -105,
    away_price: -115,
    over_price: null,
    under_price: null,
  });
  const rows: BookPricedRow[] = [
    { bookmaker: 'draftkings', home_price: -105, away_price: -115, spread_home: -8.5 },
  ];
  const hero = heroAmericanForPick(pick, row, rows);
  check(
    'price and line moved: Now price, and movedLine is the new line',
    hero?.kind === 'now' && hero.price === -105 && hero.lockedPrice === -110 && hero.movedLine === -8.5,
    JSON.stringify(hero),
  );
  const sideLine = formatSideLine(hero?.movedLine ?? null, pick.pick_side, 'spreads');
  const screenNow = signalsNowLine({
    line: sideLine,
    price: formatAmerican(hero?.price),
    priceDiffers: true,
    book: bookLabel(hero?.book ?? ''),
  });
  check('Signals shows line and price together', screenNow === `DK line now ${MINUS}8.5 (${MINUS}105)`, screenNow ?? '');
  const handoff = bestHandoffForPick(pick, rows, hero);
  check(
    'price and line moved, no current slip link: Open DK, not the lock slip',
    handoff?.bookmaker === 'draftkings' && handoff.price == null && handoff.link == null &&
      handoff.verb === 'Open' && handoff.link !== pick.dk_bet_link &&
      signalsCtaLabel(bookLabel(handoff.bookmaker), null) === 'Open DK',
    JSON.stringify(handoff),
  );
  const linkedRows: BookPricedRow[] = [
    { bookmaker: 'draftkings', home_price: -105, away_price: -115, spread_home: -8.5, home_link: 'dk://now-8.5' },
  ];
  const linked = bestHandoffForPick(pick, linkedRows, heroAmericanForPick(pick, row, linkedRows));
  check(
    'price and line moved: the button names the line and uses the current row link',
    linked?.price === -105 && linked.link === 'dk://now-8.5' && linked.verb === 'Bet' &&
      linked.link !== pick.dk_bet_link &&
      signalsCtaLabel(bookLabel(linked!.bookmaker), formatAmerican(linked!.price), sideLine) ===
        `Bet DK ${MINUS}8.5 ${MINUS}105`,
    JSON.stringify(linked),
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

{
  // A model whose loop stops reading DraftKings after the bet: its newest
  // in-play row is the lock's own quote, never shown as the live price.
  const pick = mkPick({
    model_id: 'nfl_live_leader_ml', sport: 'NFL', game_id: 'NFL_2026-09-13_TB_DAL',
    pick_side: 'away' as PickSide, pick_label: 'TB ML (live)', scored_line: null,
    dk_odds: -330, decision_odds: -330, is_live: true, created_at: '2026-09-13T17:05:00+00:00',
  });
  const row = (at: string, away: number) =>
    latest({ market: 'h2h', home_price: 250, away_price: away, total_line: null,
             over_price: null, under_price: null, snapshot_at: at });
  for (const at of ['2026-09-13T17:00:00+00:00', '2026-09-13T17:05:00+00:00']) {
    const h = heroAmericanForPick(pick, row(at, -330));
    check(
      `untracked model, row not newer than the lock (${at.slice(11, 16)}) → no live price, not stale`,
      h?.kind === 'now' && h.price === null && h.untracked === true && !h.stale && h.lockedPrice === -330,
    );
    const ho = bestHandoffForPick(pick, [], h);
    check('… and an Open DK hand-off with no number on it',
      ho?.verb === 'Open' && ho.bookmaker === MODEL_BOOK && ho.price === null);
    check('… and the caption says why',
      h != null && lockedCaptionText(h) === 'Locked -330 · live price not tracked after the bet',
      h ? lockedCaptionText(h) : '');
    check('… and VoiceOver says to check the book',
      h != null && heroPriceSpeech(h, 'Live price') ===
        'Live price not shown after the bet. Locked -330. Check DraftKings for the live price',
      h ? heroPriceSpeech(h, 'Live price') : '');
  }
  const none = heroAmericanForPick(pick, null, []);
  check('untracked model with no in-play row → the same shape', none?.price === null && none.untracked === true);
  const fresh = heroAmericanForPick(pick, row('2026-09-13T17:06:00+00:00', -500));
  check('untracked model, a row after the lock → Now', fresh?.price === -500 && !fresh.untracked);
  // Every other in-play model keeps logging: until DraftKings republishes,
  // its lock quote IS the current price, and the card keeps it and the hand-off.
  const other = mkPick({ is_live: true, created_at: '2026-09-13T17:05:00+00:00' });
  const oh = heroAmericanForPick(other, latest({ over_price: -110, snapshot_at: '2026-09-13T17:00:00+00:00' }));
  check('other in-play models: a row not newer than the lock is still the live price',
    oh?.kind === 'now' && oh.price === -110 && !oh.untracked && !oh.stale);
  const oho = bestHandoffForPick(other, [], oh);
  check('… with its priced hand-off', oho?.verb === 'Bet' && oho.price === -110);
  // Pick Detail's book row: the same numberless chip, never "Bet at DK -330".
  const rowSrc = readFileSync(join(__dirname, '../src/components/BookLinesRow.tsx'), 'utf8');
  const head = rowSrc.slice(rowSrc.indexOf('export function BookLinesRow'), rowSrc.indexOf('const quotes = currentLineQuotes'));
  check('BookLinesRow: an untracked hero returns the numberless Open chip before any priced chip',
    /if \(hero\?\.untracked\)/.test(head) && /to check the live price/.test(head) && !/formatAmerican/.test(head));
  const detail = readFileSync(join(__dirname, '../src/screens/PickDetailScreen.tsx'), 'utf8');
  check('PickDetail: the book row renders for an untracked hero',
    /cta\.handoff && \(lineQuotes\.length > 0 \|\| hero\?\.untracked\)/.test(detail));
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

// ── multi-market prop rules: the scored line is the BET book's ─────────────
// nba/nfl/wnba_prop_market store the bet book's own line as scored_line, and
// their history is that book's. Read as DraftKings' line, a price at a NEW
// line was compared with the lock at the OLD one: FanDuel moving Under 24.5
// -110 to Under 23.5 +105 read "Moved 3.6pp in your favor" when the line had
// moved a point against the bet (designer review, 2026-10-16).
{
  const nba = mkPick({
    model_id: 'nba_prop_market',
    sport: 'NBA',
    pick_side: 'under',
    pick_label: 'Jalen Brunson Under 24.5 Pts',
    prop_market: 'player_points',
    scored_line: 24.5,
    dk_odds: -115, // DraftKings posts the same line, so line_book is NULL
    decision_odds: -110,
    decision_book: 'fanduel',
    line_book: null,
  });
  const fdNow = { line: 23.5, under_price: 105, over_price: -125 };
  const hist = movementFromSameBookHistory(nba, fdNow, 'player_points');
  check('NBA rule: FanDuel Under 23.5 +105 against a 24.5 lock is not "in your favor"',
    hist?.severity !== 'good', `severity=${hist?.severity}`);
  check('NBA rule: that move is the line moving against the under',
    hist?.lineMovedAgainst === true && hist.currentLine === 23.5, `lineMovedAgainst=${hist?.lineMovedAgainst}`);
  const board = movementFromLatest(nba, null, [{ bookmaker: 'fanduel', ...fdNow }]);
  check('NBA rule, board chip: the same move reads against the bet',
    board?.severity === 'skip', `severity=${board?.severity}`);
  check('NBA rule: a FanDuel 25.5 row does not match a 24.5 lock at the same price',
    !snapshotMatchesLock(nba, { line: 25.5, under_price: -110 }, 'player_points'));
  check('NBA rule: the FanDuel 24.5 row at the locked price does match',
    snapshotMatchesLock(nba, { line: 24.5, under_price: -110 }, 'player_points'));
  check('NBA rule: the locked line belongs to the history book',
    lockedLineAtHistoryBook(nba, 'player_points') === 24.5);

  // WNBA and NFL rows carry no decision_book: the book is only in the label,
  // and dk_odds holds that book's price (wnba/nfl_prop_market_card.py).
  const wnba = mkPick({
    model_id: 'wnba_prop_market',
    sport: 'WNBA',
    pick_side: 'under',
    pick_label: 'Jackie Young Under 15.5 Pts (FD)',
    prop_market: 'player_points',
    scored_line: 15.5,
    dk_odds: -110,
    decision_odds: null,
    decision_book: null,
    line_book: null,
  });
  check('WNBA rule: history is the label book', historyBookForPick(wnba) === 'fanduel');
  const wHist = movementFromSameBookHistory(wnba, { line: 14.5, under_price: 105 }, 'player_points');
  check('WNBA rule: FanDuel Under 14.5 +105 against a 15.5 lock is not "in your favor"',
    wHist?.severity !== 'good' && wHist?.lineMovedAgainst === true, `severity=${wHist?.severity}`);
  check('WNBA rule: a FanDuel 16.5 row does not match a 15.5 lock',
    !snapshotMatchesLock(wnba, { line: 16.5, under_price: -110 }, 'player_points'));
  check('WNBA rule: the FanDuel 15.5 row at the locked price does match',
    snapshotMatchesLock(wnba, { line: 15.5, under_price: -110 }, 'player_points'));

  const nfl = mkPick({
    model_id: 'nfl_prop_market',
    sport: 'NFL',
    pick_side: 'under',
    pick_label: 'Marvin Harrison Jr. Under 3.5 Rec (MGM)',
    prop_market: 'player_receptions',
    scored_line: 3.5,
    dk_odds: -120,
    decision_odds: null,
    decision_book: null,
    line_book: null,
  });
  check('NFL rule: the locked line is the label book\'s (BetMGM)',
    historyBookForPick(nfl) === 'betmgm' && lockedLineAtHistoryBook(nfl, 'player_receptions') === 3.5);
  check('NFL rule: a BetMGM 4.5 row does not match a 3.5 lock',
    !snapshotMatchesLock(nfl, { line: 4.5, under_price: -120 }, 'player_receptions'));

  // The NBA projection model writes the NBA rule's row shape
  // (scripts/nba_prop_projection_card.py pick_rows) and bets OVERS too. Every
  // fixture above is an under, so the over direction is pinned here: a line
  // moving UP is against an over.
  const projOver = mkPick({
    model_id: 'nba_prop_projection',
    sport: 'NBA',
    pick_side: 'over',
    pick_label: 'Stephen Curry Over 1.5 Steals',
    prop_market: 'player_steals',
    scored_line: 1.5,
    dk_odds: 105, // DraftKings hangs the same line, so line_book is NULL
    decision_odds: 120,
    decision_book: 'fanduel',
    line_book: null,
  });
  const fdUp = { line: 2.5, over_price: 150, under_price: -190 };
  check('projection over: the history is the deciding book', historyBookForPick(projOver) === 'fanduel');
  check('projection over: the locked line belongs to the history book',
    lockedLineAtHistoryBook(projOver, 'player_steals') === 1.5);
  const upHist = movementFromSameBookHistory(projOver, fdUp, 'player_steals');
  check('projection over: FanDuel Over 2.5 +150 against a 1.5 lock is not "in your favor"',
    upHist?.severity !== 'good', `severity=${upHist?.severity}`);
  check('projection over: a line moving up is against the over',
    upHist?.lineMovedAgainst === true && upHist.currentLine === 2.5, `lineMovedAgainst=${upHist?.lineMovedAgainst}`);
  const upBoard = movementFromLatest(projOver, null, [{ bookmaker: 'fanduel', ...fdUp }]);
  check('projection over, board chip: the same move reads against the bet',
    upBoard?.severity === 'skip', `severity=${upBoard?.severity}`);
  const fdDown = { line: 0.5, over_price: -250, under_price: 190 };
  check('projection over: a line moving down is not against the over',
    movementFromSameBookHistory(projOver, fdDown, 'player_steals')?.lineMovedAgainst !== true);
  check('projection over: the FanDuel 1.5 row at the locked over price matches the lock',
    snapshotMatchesLock(projOver, { line: 1.5, over_price: 120 }, 'player_steals'));
  check('projection over: a FanDuel 2.5 row at that price does not',
    !snapshotMatchesLock(projOver, { line: 2.5, over_price: 120 }, 'player_steals'));
  const projOverBooks = allBooksLineSource(projOver);
  check('projection over, All books: DraftKings hangs the line, so it is DraftKings’ row',
    projOverBooks.modeledBook === MODEL_BOOK && projOverBooks.note.startsWith('The line is DraftKings’.'),
    projOverBooks.note);

  // An under on a line DraftKings does not hang: line_book names the book.
  const projUnder = mkPick({
    model_id: 'nba_prop_projection',
    sport: 'NBA',
    pick_side: 'under',
    pick_label: 'Nikola Jokic Under 13.5 Reb+Ast',
    prop_market: 'player_rebounds_assists',
    scored_line: 13.5,
    dk_odds: null,
    decision_odds: -105,
    decision_book: 'betmgm',
    line_book: 'betmgm',
  });
  check('projection under off DraftKings: priced at its deciding book', hasPricedLine(projUnder));
  check('projection under off DraftKings: the history is BetMGM’s',
    historyBookForPick(projUnder) === 'betmgm' && lockedLineAtHistoryBook(projUnder, 'player_rebounds_assists') === 13.5);
  const mgmDown = movementFromSameBookHistory(projUnder, { line: 12.5, under_price: 110 }, 'player_rebounds_assists');
  check('projection under: BetMGM Under 12.5 +110 against a 13.5 lock is the line moving against it',
    mgmDown?.lineMovedAgainst === true && mgmDown.severity !== 'good', `severity=${mgmDown?.severity}`);
  const projUnderBooks = allBooksLineSource(projUnder);
  check('projection under, All books: BetMGM row, and the DraftKings clause',
    projUnderBooks.modeledBook === 'betmgm' && projUnderBooks.note.includes('DraftKings doesn’t post this line'),
    projUnderBooks.note);

  // The projection's labels use the NBA rule's words for the shared markets:
  // "Reb" for rebounds and "3PM" for threes (models/nba_prop_projection.py
  // MARKET_LABEL). The card's title, the player name the prop odds are keyed
  // on, and the market (from prop_market, never the label) must all hold.
  const threesOver = mkPick({
    model_id: 'nba_prop_projection',
    sport: 'NBA',
    pick_side: 'over',
    pick_label: 'Karl-Anthony Towns Over 1.5 3PM',
    prop_market: 'player_threes',
    scored_line: 1.5,
    dk_odds: 110,
    decision_odds: 125,
    decision_book: 'fanduel',
    line_book: null,
  });
  check('projection "3PM" label: the player name parses (hyphenated)',
    playerNameFromPickLabel(threesOver.pick_label) === 'Karl-Anthony Towns');
  {
    const t = splitPickTitle(threesOver);
    check('projection "3PM" label: the title splits into the bet and the player',
      t.primary === 'Over 1.5 3PM' && t.secondary === 'Karl-Anthony Towns', `${t.primary} | ${t.secondary}`);
  }
  const threesUp = movementFromSameBookHistory(threesOver, { line: 2.5, over_price: 160, under_price: -200 }, 'player_threes');
  check('projection "3PM" over: FanDuel moving to 2.5 is against it, not in its favor',
    threesUp?.lineMovedAgainst === true && threesUp.severity !== 'good', `severity=${threesUp?.severity}`);
  const rebUnder = mkPick({
    model_id: 'nba_prop_projection',
    sport: 'NBA',
    pick_side: 'under',
    pick_label: 'Josh Hart Under 7.5 Reb',
    prop_market: 'player_rebounds',
    scored_line: 7.5,
    dk_odds: -115,
    decision_odds: -105,
    decision_book: 'betmgm',
    line_book: null,
  });
  {
    const t = splitPickTitle(rebUnder);
    check('projection "Reb" label: the title splits into the bet and the player',
      t.primary === 'Under 7.5 Reb' && t.secondary === 'Josh Hart', `${t.primary} | ${t.secondary}`);
  }
  check('projection "Reb" under: the BetMGM 7.5 row at the locked price matches the lock',
    snapshotMatchesLock(rebUnder, { line: 7.5, under_price: -105 }, 'player_rebounds') &&
    !snapshotMatchesLock(rebUnder, { line: 6.5, under_price: -105 }, 'player_rebounds'));

  // Other models keep the DraftKings line rule (the broad fix is separate):
  // an MLB prop decided at FanDuel with line_book NULL still skips line deltas.
  const mlb = mkPick({
    model_id: 'mlb_prop_batter_runs',
    pick_side: 'over',
    scored_line: 0.5,
    dk_odds: -110,
    decision_odds: -105,
    decision_book: 'fanduel',
    line_book: null,
  });
  check('other models unchanged: an MLB prop at FanDuel with no line book compares no line',
    lockedLineAtHistoryBook(mlb, 'batter_runs_scored') === null);
}

// ── All books: whose line it is, for a rule priced at its label book ───────
// The NFL and WNBA rules name their book only in the label (decision_book
// NULL). Their "modeled" row and footnote said DraftKings, under a FanDuel
// line (designer review, 2026-10-16). Whether DraftKings posts the line is
// only known when line_book is set, so that clause goes on this branch.
{
  const wnbaFd = mkPick({
    model_id: 'wnba_prop_market',
    pick_side: 'under',
    pick_label: 'Jackie Young Under 15.5 Pts (FD)',
    decision_book: null,
    decision_odds: null,
    line_book: null,
  });
  const w = allBooksLineSource(wnbaFd);
  check('All books, WNBA rule: the modeled row is the label book', w.modeledBook === 'fanduel', w.modeledBook);
  check('All books, WNBA rule: the footnote names that book', w.note.startsWith('The line is FanDuel’s.'), w.note);
  check('All books, WNBA rule: no claim about what DraftKings posts', !w.note.includes('DraftKings doesn’t post'));
  const nflMgm = allBooksLineSource(mkPick({
    model_id: 'nfl_prop_market',
    pick_side: 'under',
    pick_label: 'Marvin Harrison Jr. Under 3.5 Rec (MGM)',
    decision_book: null,
    decision_odds: null,
    line_book: null,
  }));
  check('All books, NFL rule: BetMGM row and BetMGM footnote',
    nflMgm.modeledBook === 'betmgm' && nflMgm.note.startsWith('The line is BetMGM’s.'), nflMgm.note);
  const wnbaDk = allBooksLineSource(mkPick({
    model_id: 'wnba_prop_market',
    pick_label: 'Jackie Young Under 15.5 Pts (DK)',
    decision_book: null,
    line_book: null,
  }));
  check('All books, a rule labelled (DK) keeps the DraftKings sentence',
    wnbaDk.modeledBook === MODEL_BOOK && wnbaDk.note.startsWith('The line is DraftKings’.'), wnbaDk.note);
  // NBA rows carry decision_book (and line_book when DraftKings has no line):
  // the existing logic, unchanged.
  const nbaAtDkLine = allBooksLineSource(mkPick({
    model_id: 'nba_prop_market',
    pick_label: 'Jalen Brunson Under 24.5 Pts',
    decision_book: 'fanduel',
    line_book: null,
  }));
  check('All books, NBA rule with no line book: DraftKings row, as before',
    nbaAtDkLine.modeledBook === MODEL_BOOK && nbaAtDkLine.note.startsWith('The line is DraftKings’.'));
  const nbaOffDk = allBooksLineSource(mkPick({
    model_id: 'nba_prop_market',
    pick_label: 'Jalen Brunson Under 24.5 Pts',
    decision_book: 'fanduel',
    line_book: 'fanduel',
  }));
  check('All books, NBA rule with a line book: that book, and the DraftKings clause, as before',
    nbaOffDk.modeledBook === 'fanduel' && nbaOffDk.note.includes('DraftKings doesn’t post this line'));
}

{
  const cardSrc = readFileSync(join(__dirname, '../src/components/LineMovementCard.tsx'), 'utf-8');
  check(
    'LineMovementCard fetch uses historyBook, not MODEL_BOOK',
    cardSrc.includes('historyBookForPick') &&
      cardSrc.includes('fetchOddsHistory(pick.game_id, market, historyBook, from, startAt)') &&
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
  // 2026-10-09: the reads were the OLDEST 50 snapshots, the last called "now".
  check(
    'history fetches are not the oldest 50',
    !hist.includes('ascending: true') && hist.includes('ascending: false') && hist.includes("neq('snapshot_type', 'in_play')"),
  );
  check(
    'the card windows the rows from the pick to the start',
    cardSrc.includes('sincePick(rows as Snap[], pick.created_at, startAt)') &&
      cardSrc.includes('const from = historyFrom(pick, startAt);') &&
      cardSrc.includes('gameStartAt(commenceTime, pick.game_time)'),
  );
}

// Review 2026-10-09: the book has posted nothing since the pick. The only row
// is the snapshot the pick was scored from — "No new price", not "steady".
{
  const pick = mkPick({ created_at: '2026-09-13 16:00:00.5+00', game_time: '2026-09-13T23:05:00+00:00' } as Partial<Pick>);
  const only = [{ snapshot_at: '2026-09-13T15:58:00Z', total_line: 8.5, over_price: -110, under_price: -110 }];
  const from = historyFrom(pick, pick.game_time);
  const open = lineMovementView(pick, sincePick(only, from!, pick.game_time, 50, Date.parse('2026-09-13T16:05:00Z')), 'totals', false);
  check(
    'one row at the pick: "No new price", grey, dated',
    open?.verdict.label === 'No new price from DraftKings since your pick' &&
      open?.verdict.tone === 'neutral' &&
      open?.asOf === 'As of Sun, 9/13, 11:58 AM ET',
    JSON.stringify(open && [open.verdict, open.asOf]),
  );
  const shut = lineMovementView(pick, sincePick(only, from!, pick.game_time, 50, Date.parse('2026-09-14T03:00:00Z')), 'totals', false);
  check(
    'one row at the pick, after the start: "between your pick and game time"',
    shut?.verdict.label === 'No new price from DraftKings between your pick and game time',
    JSON.stringify(shut?.verdict),
  );
  check('a live pick has no window', historyFrom(mkPick({ is_live: true }), pick.game_time) === null);
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
    'board cardLabel still announces the stored pick_label',
    /joinCardSpeech\(\[[\s\S]*?pick\.pick_label/.test(src) && /accessibilityLabel=\{cardLabel\}/.test(src),
  );
  check(
    'Signals cardLabel is the structured speech, not the stored label',
    /const cardLabel = signals\s*\?\s*signalsCardSpeech\(/.test(src) &&
      !/signalsBetHeadline\(pick\.pick_label\)/.test(src),
  );
  check(
    'PickCard does not write pick_label',
    !/pick\.pick_label\s*=/.test(src),
  );
  check(
    'prop bet shrink floor stays above the caption (0.75 × 17 > 12)',
    /minimumFontScale:\s*0\.75/.test(src),
  );
  const labelRow = src.slice(src.indexOf('labelRow:'), src.indexOf('labelChip:'));
  check(
    'labelRow aligns chips to the primary line, not the two-line mid-point',
    /alignItems:\s*'flex-start'/.test(labelRow) && !/alignItems:\s*'center'/.test(labelRow),
  );
}

// ── Signals card (Option A) ────────────────────────────────────────────────
{
  const abbrevs = new Map([['Western Kentucky', 'WKU'], ['Sam Houston', 'SHSU']]);
  check(
    'context line is abbrev @ abbrev · sport · time',
    signalsContextLine({
      sport: 'NCAAF',
      away: 'Western Kentucky',
      home: 'Sam Houston',
      timeLabel: '8:00 PM ET',
      abbrevs,
    }) === 'WKU @ SHSU · NCAAF · 8:00 PM ET',
  );
  check(
    'unknown NCAAF school is not given an invented code',
    signalsContextLine({
      sport: 'NCAAF',
      away: 'Western Kentucky',
      home: 'Sam Houston',
      timeLabel: '8:00 PM ET',
      abbrevs: null,
    }) === 'Western Kentucky @ Sam Houston · NCAAF · 8:00 PM ET',
  );
  const spread = signalsBetHeadline({
    side: 'home', line: -7.5, market: 'spreads', homeTeam: 'Sam Houston', awayTeam: 'WKU',
  });
  check(
    'spread headline is the club and the side line, with a true minus',
    spread === `Sam Houston ${MINUS}7.5` && !spread.includes('-7.5'),
  );
  check(
    'a whole-number spread does not grow a tenth',
    signalsBetHeadline({ side: 'home', line: -7, market: 'spreads', homeTeam: 'BUF', awayTeam: 'KC' }) === `BUF ${MINUS}7` &&
      signalsBetHeadline({ side: 'home', line: 3, market: 'spreads', homeTeam: 'BUF', awayTeam: 'KC' }) === 'BUF +3' &&
      signalsBetHeadline({ side: 'away', line: 3, market: 'spreads', homeTeam: 'BUF', awayTeam: 'KC' }) === `KC ${MINUS}3`,
  );
  check(
    'a hyphen inside a school name stays a hyphen',
    signalsBetHeadline({
      side: 'home', line: -2.5, market: 'spreads', homeTeam: 'Louisiana-Monroe', awayTeam: 'WKU',
    }) === `Louisiana-Monroe ${MINUS}2.5`,
  );
  check(
    'moneyline headline is the team and ML',
    signalsBetHeadline({ side: 'home', line: null, market: 'h2h', homeTeam: 'Sam Houston', awayTeam: 'WKU' }) === 'Sam Houston ML',
  );
  check(
    'total headline is the side and the line',
    signalsBetHeadline({ side: 'over', line: 8.5, market: 'totals', homeTeam: 'BOS', awayTeam: 'NYY' }) === 'Over 8.5',
  );
  check(
    'a whole-number total drops the decimal',
    signalsBetHeadline({ side: 'under', line: 56, market: 'totals', homeTeam: 'BUF', awayTeam: 'KC' }) === 'Under 56',
  );
  check(
    'F5 stays on a total, a spread and a moneyline',
    signalsBetHeadline({ side: 'over', line: 4.5, market: 'totals_1st_5_innings', homeTeam: 'BOS', awayTeam: 'NYY' }) === 'Over 4.5 F5' &&
      signalsBetHeadline({ side: 'home', line: -1.5, market: 'spreads_1st_5_innings', homeTeam: 'NYY', awayTeam: 'BOS' }) === `NYY ${MINUS}1.5 F5` &&
      signalsBetHeadline({ side: 'home', line: null, market: 'h2h_1st_5_innings', homeTeam: 'NYY', awayTeam: 'BOS' }) === 'NYY ML F5',
  );
  check(
    'a whole-number game total does not keep a trailing .0',
    signalsBetHeadline({ side: 'under', line: 6, market: 'totals', homeTeam: 'EDM', awayTeam: 'LAK' }) === 'Under 6',
  );
  check(
    'a team total names the club the market belongs to',
    signalsBetHeadline({ side: 'over', line: 3.5, market: 'team_totals_home', homeTeam: 'Boston Bruins', awayTeam: 'NYY' }) === 'Boston Bruins Over 3.5' &&
      signalsBetHeadline({ side: 'under', line: 2.5, market: 'team_totals_away', homeTeam: 'New York', awayTeam: 'Los Angeles' }) === 'Los Angeles Under 2.5' &&
      signalsBetHeadline({ side: 'over', line: 8.5, market: 'totals', homeTeam: 'New York', awayTeam: 'Los Angeles' }) === 'Over 8.5',
  );
  check(
    'prop headline is the player, the side, the line and the stat',
    signalsBetHeadline({
      side: 'under', line: 9.5, market: 'player_tackles_assists', player: 'Roquan Smith',
    }) === 'Roquan Smith Under 9.5 Tackles + Assists' &&
      signalsBetHeadline({
        side: 'over', line: 2.5, market: 'player_threes', player: 'Karl-Anthony Towns',
      }) === 'Karl-Anthony Towns Over 2.5 Three-pointers' &&
      signalsBetHeadline({
        side: 'over', line: 32.5, market: 'player_points_rebounds_assists', player: 'Jalen Brunson',
      }) === 'Jalen Brunson Over 32.5 Points + Rebounds + Assists',
  );
  check(
    'the headline has no stake suffix and no wind parenthetical',
    signalsBetHeadline({ side: 'under', line: 43.5, market: 'totals', homeTeam: 'MIA', awayTeam: 'NYJ' }) === 'Under 43.5' &&
      signalsBetHeadline({
        side: 'under', line: 56, market: 'totals',
        label: 'KC @ BUF Under 56 (Wind 14 mph, FD) · 0.77u',
      }) === 'Under 56',
  );
  check(
    'golf and UFC method use the stored label, not the event or the home fighter',
    signalsBetHeadline({
      side: 'yes', line: null, market: null, homeTeam: 'The Masters', awayTeam: 'FIELD',
      label: 'Scottie Scheffler to Win',
    }) === 'Scottie Scheffler to Win' &&
      signalsBetHeadline({
        side: '1845', line: null, market: null, homeTeam: 'The Masters',
        label: 'Scottie Scheffler over Rory McIlroy (matchup)',
      }) === 'Scottie Scheffler over Rory McIlroy (matchup)' &&
      signalsBetHeadline({
        side: 'ko_tko', line: null, market: null, homeTeam: 'Islam Makhachev', awayTeam: 'Alex Pereira',
        label: 'Alex Pereira vs Islam Makhachev — KO/TKO',
      }) === 'Alex Pereira vs Islam Makhachev — KO/TKO' &&
      signalsBetHeadline({
        side: 'decision', line: null, market: null, homeTeam: 'Islam Makhachev',
        label: 'Alex Pereira vs Islam Makhachev — Decision',
      }) === 'Alex Pereira vs Islam Makhachev — Decision',
  );
  check(
    'a regulation moneyline is not a full-game ML',
    signalsBetHeadline({
      side: 'home', line: null, market: 'h2h_3way', homeTeam: 'Boston Bruins', awayTeam: 'Toronto Maple Leafs',
    }) === 'Boston Bruins (Regulation)' &&
      signalsBetHeadline({
        side: 'away', line: null, market: 'h2h_3way', homeTeam: 'Boston Bruins', awayTeam: 'Toronto Maple Leafs',
      }) === 'Toronto Maple Leafs (Regulation)' &&
      signalsBetHeadline({
        side: 'draw', line: null, market: 'h2h_3way', homeTeam: 'Boston Bruins', awayTeam: 'Toronto Maple Leafs',
      }) === 'Draw (Regulation)' &&
      !signalsBetHeadline({
        side: 'home', line: null, market: 'h2h_3way', homeTeam: 'Boston Bruins',
      }).includes('ML'),
  );
  check(
    'UFC rounds names the market, and an anytime touchdown drops the 0.5',
    signalsBetHeadline({ side: 'under', line: 2.5, market: 'totals', stat: 'Rounds' }) === 'Under 2.5 Rounds' &&
      signalsBetHeadline({
        side: 'over', line: 0.5, market: 'player_anytime_td', player: "Ja'Marr Chase",
      }) === "Ja'Marr Chase Anytime TD",
  );
  check(
    'a prop with no player or no stat falls back to the cleaned label',
    signalsBetHeadline({
      side: 'under', line: 9.5, market: 'player_tackles_assists', player: null,
      label: 'Roquan Smith Under 9.5 Tackles (FD) · 0.50u',
    }) === 'Roquan Smith Under 9.5 Tackles' &&
      signalsBetHeadline({
        side: 'over', line: 1.5, market: 'player_custom', player: 'Someone',
        label: 'Someone Over 1.5 Custom (DK)',
      }) === 'Someone Over 1.5 Custom',
  );
  check(
    'wind reason is the forecast, and other models stay quiet',
    signalsReasonLine({ modelId: 'nfl_wind_totals', windMph: 14 }) === 'Wind 14 mph at kickoff' &&
      signalsReasonLine({ modelId: 'nfl_wind_totals', windMph: 14.2 }) === 'Wind 14 mph at kickoff' &&
      signalsReasonLine({ modelId: 'nfl_wind_totals', windMph: 14, dome: 1 }) === null &&
      signalsReasonLine({ modelId: 'nfl_opener_spread', windMph: 14 }) === null &&
      signalsReasonLine({ modelId: 'nfl_wind_totals', windMph: null }) === null &&
      signalsReasonLine({
        modelId: 'nfl_wind_totals', windMph: null,
        label: 'KC @ BUF Under 56 (Wind 14 mph, FD) · 0.77u',
      }) === 'Wind 14 mph at kickoff' &&
      signalsReasonLine({
        modelId: 'nfl_wind_totals', windMph: 21,
        label: 'KC @ BUF Under 56 (Wind 14 mph, FD) · 0.77u',
      }) === 'Wind 14 mph at kickoff' &&
      signalsReasonLine({
        modelId: 'nfl_wind_totals', windMph: null, dome: 1,
        label: 'KC @ BUF Under 56 (Wind 14 mph, FD) · 0.77u',
      }) === null &&
      signalsReasonLine({
        modelId: 'nfl_opener_spread', windMph: null,
        label: 'KC @ BUF — KC -3 (Wind 14 mph, FD)',
      }) === null,
  );
  check(
    'model caption is modelLong plus when it posted',
    signalsModelCaption('Wind Totals (Under)', 'Posted 11:07 AM ET') === 'Wind Totals (Under) model · Posted 11:07 AM ET' &&
      signalsModelCaption('Wind Totals (Under)', null) === 'Wind Totals (Under) model',
  );
  check(
    'VoiceOver reads bet, price, game, reason, figures, stake, model, posted',
    signalsCardSpeech({
      bet: 'Under 56',
      price: `${MINUS}110 DraftKings`,
      reason: 'Wind 14 mph at kickoff',
      teams: 'Kansas City at Buffalo',
      time: '8:00 PM ET',
      edge: 'Edge +6.0%',
      modelChance: 'Model chance 58%',
      expectedReturn: 'Expected return +4.0%',
      stake: 'Stake, Bet 1.1 units, win 1 unit',
      modelName: 'Wind Totals (Under) model',
      posted: 'Posted 11:07 AM ET',
      paused: null,
      gameStatus: null,
      sharp: null,
      started: null,
    }) === `Under 56. ${MINUS}110 DraftKings. Kansas City at Buffalo. 8:00 PM ET. Wind 14 mph at kickoff. Edge +6.0%. Model chance 58%. Expected return +4.0%. Stake, Bet 1.1 units, win 1 unit. Wind Totals (Under) model. Posted 11:07 AM ET` &&
      signalsCardSpeech({
        verdict: 'NEUTRAL',
        bet: 'Under 43.5',
        price: null,
        reason: null,
        teams: null,
        time: null,
        edge: null,
        modelChance: null,
        expectedReturn: null,
        stake: null,
        modelName: null,
        posted: null,
        paused: null,
        gameStatus: null,
        sharp: null,
        started: null,
      }) === 'NEUTRAL. Under 43.5',
  );
  check(
    'paused, live, locked and flagged speech keep their place',
    signalsCardSpeech({
      bet: 'Under 56', price: null, reason: null, teams: null, time: null,
      edge: 'Price check. The number looks off.',
      modelChance: 'Model chance 58%',
      expectedReturn: 'Expected return unavailable',
      stake: 'Stake unavailable',
      modelName: 'Wind Totals (Under) model',
      posted: 'Locked Tue 10/20 · 9:31 AM ET',
      paused: 'Paused model, not a bet',
      gameStatus: 'Live',
      sharp: null,
      started: `Game started, picked at ${MINUS}110, DraftKings`,
    }).endsWith(`Paused model, not a bet. Live. Game started, picked at ${MINUS}110, DraftKings`) &&
      signalsCardSpeech({
        bet: 'Under 56', price: null, reason: null, teams: null, time: null,
        edge: 'Price check. The number looks off.',
        modelChance: null, expectedReturn: null, stake: 'Stake unavailable',
        modelName: null, posted: null, paused: null, gameStatus: null, sharp: null, started: null,
      }).includes('Price check') &&
      !signalsCardSpeech({
        bet: 'Under 56', price: null, reason: null, teams: null, time: null,
        edge: null, modelChance: null, expectedReturn: null, stake: null,
        modelName: null, posted: null, paused: null, gameStatus: null, sharp: null, started: null,
      }).includes('models agree'),
  );
  check(
    'price and book use a true minus',
    signalsPriceText('-110', 'MGM') === `${MINUS}110 MGM`,
  );
  check('CTA names the best book, word is Bet', signalsCtaLabel('MGM', '-110') === `Bet MGM ${MINUS}110`);
  check('CTA names the line when that bet is at a moved line', signalsCtaLabel('DK', '-105', '-8.5') === `Bet DK ${MINUS}8.5 ${MINUS}105`);
  check('CTA with no price does not invent one', signalsCtaLabel('DK', null) === 'Open DK');
  check(
    'a different book or price is Best now on the button',
    signalsCtaLabel('FD', '-105', null, { bestNow: true }) === `Best now · FD ${MINUS}105` &&
      signalsCtaLabel('DK', '-105', '-8.5', { bestNow: true }) === `Best now · DK ${MINUS}8.5 ${MINUS}105` &&
      signalsCtaSpeech('FanDuel', '-105', null, { bestNow: true }) === `Best now, FanDuel, ${MINUS}105` &&
      !signalsCtaSpeech('FanDuel', '-105', null, { bestNow: true }).includes('·'),
  );
  check(
    'stake cell names units to bet and units to win',
    signalsStakeLine('1.5u', '0.4u') === 'Bet 1.5u · Win 0.4u' &&
      signalsStakeLine('1.1u', '1u') === 'Bet 1.1u · Win 1u' &&
      !signalsStakeLine('1.1u', '1u').includes('→'),
  );
  check(
    'stake speech says both amounts, singular only at 1u',
    signalsStakeSpeech('1.5u', '0.4u') === 'Bet 1.5 units, win 0.4 units' &&
      signalsStakeSpeech('1u', '1u') === 'Bet 1 unit, win 1 unit' &&
      signalsStakeSpeech('10u', '1.5u') === 'Bet 10 units, win 1.5 units',
  );
  const card = readFileSync(join(__dirname, '../src/components/PickCard.tsx'), 'utf-8');
  check('the picked-at line is not under the hero', !card.includes('signalsPickedAtLine') && !/pickedAt:/.test(card));
  check('Today uses the same Best now wording as Signals', /bestNow: handoff\.verb === 'Best'/.test(card));
  const home = readFileSync(join(__dirname, '../src/screens/PicksHomeScreen.tsx'), 'utf-8');
  check(
    'All, Signals and Live use the new card',
    /layout="signals"/.test(home) && !/layout=\{view === 'signals'/.test(home),
  );
  check(
    'a paused card is paused on every view, including Signals',
    /paused=\{isPausedForDisplay\(item\.pick\)\}/.test(home) &&
      !/paused=\{view === 'today' && isPausedForDisplay/.test(home),
  );
  check(
    'NCAAF abbreviations load for every view',
    /useNcaafAbbrevs\(sport === 'NCAAF'\)/.test(home) && /teamAbbrevs=\{ncaafAbbrevs\}/.test(home),
  );
  {
    const liveGame = gameStatus(
      {
        sport: 'MLB',
        home_score: null,
        away_score: null,
        commence_time: '2020-01-01T00:00:00Z',
      },
      {
        abstract_game_state: 'Live',
        home_score: 3,
        away_score: 2,
        inning: 7,
        inning_half: 'bottom',
        outs: 1,
        bases_state: null,
      },
    );
    const matchupAt = card.indexOf('<Text style={styles.matchupLine}>');
    const betAt = card.indexOf('{betHeadline}');
    const between = matchupAt >= 0 && betAt > matchupAt ? card.slice(matchupAt, betAt) : '';
    check(
      'a live snapshot stays live, and the score badge sits on the matchup row',
      liveGame.kind === 'live' &&
        liveGame.awayScore === 2 &&
        liveGame.homeScore === 3 &&
        liveGame.inning === 7 &&
        between.includes('<GameStatusPill') &&
        between.includes("kind !== 'pre'") &&
        !/numberOfLines/.test(between),
    );
  }
  check('hero is 22pt', /betLeft: \{[\s\S]*?font\.size\.title2/.test(card) && /betRight: \{[\s\S]*?font\.size\.title2/.test(card));
  check(
    'three figures use the plain words, and Stake is not a fourth cell',
    /Model chance/.test(card) && /Expected return/.test(card) && />Edge</.test(card) && !/>Stake</.test(card),
  );
  check(
    'the bet, the reason and the matchup wrap instead of ellipsizing',
    /\{betHeadline\}/.test(card) &&
      !/numberOfLines=\{[^}]*\}\s*>\s*\{betHeadline\}/.test(card) &&
      /styles\.reasonLine/.test(card) &&
      !/numberOfLines=\{[^}]*\}[^<]{0,40}reasonLine/.test(card) &&
      /styles\.matchupLine/.test(card) &&
      !/numberOfLines=\{[^}]*\}[\s\S]{0,80}signalsContextLine\(/.test(card),
  );
  check(
    'the model name is the footer caption',
    /styles\.modelCaption/.test(card) && /\{modelCaption\}/.test(card),
  );
  check(
    'a paused Signals card shows PAUSED and mutes the hero',
    /signalsMuted = signals && \(flagged \|\| Boolean\(heroPrice\?\.stale\) \|\| paused\)/.test(card) &&
      card.split('>PAUSED<').length === 3,
  );
  {
    const signalsJsx = card.slice(card.indexOf('styles.contextRow'));
    check(
      'the new card shows the verdict, and a non-bet headline is not bold',
        /<SignalBadge signal=\{pick\.signal_type\} small \/>/.test(signalsJsx) &&
        signalsJsx.indexOf('<SignalBadge') < signalsJsx.indexOf('styles.matchupLine') &&
        /quietHeadline && styles\.betMuted/.test(signalsJsx) &&
        /verdict: signalsVerdict/.test(card) &&
        /const signalsVerdict = preview/.test(card) &&
        /paused: null/.test(card),
    );
    check(
      'a live lock stays green, and the grey caption does not repeat it',
      /name="lock-closed-outline"/.test(signalsJsx) &&
        /color=\{colors\.betInk\}/.test(signalsJsx) &&
        /timing\?\.kind === 'live' \? null/.test(card),
    );
  }
  {
    const queries = readFileSync(join(__dirname, '../src/lib/queries.ts'), 'utf-8');
    const nflFn = queries.split('export async function fetchUpcomingNflPicks')[1]?.split('export async function ')[0] ?? '';
    check(
      'look-ahead NFL picks do not read game_weather',
      !/\.from\('game_weather'\)/.test(nflFn) && /weather: null/.test(nflFn),
    );
  }
  check(
    'a long bet keeps its line with the name; the price does not steal the row',
    /betLeft: \{[\s\S]*?flexShrink: 0[\s\S]*?maxWidth: '100%'/.test(card) &&
      !/betLeft: \{[\s\S]*?flexBasis: '55%'/.test(card),
  );
  const navy = /handoffNavy: \{[\s\S]*?\}/.exec(card)?.[0] ?? '';
  check('CTA fill is navy tint, not DK green or system blue', /backgroundColor: colors\.tint/.test(navy) && !/DK_GREEN|colors\.info/.test(navy));
  check('CTA label is textInverse', /handoffNavyText: \{[\s\S]*?color: colors\.textInverse/.test(card));
  check(
    'signals stake is stakeFor risk and win, and the value is not line-capped',
    /signalsStakeLine\(signalsRiskUnits, signalsWinUnits\)/.test(card) &&
      /formatUnits\(stake\.risk\)/.test(card) &&
      /formatUnits\(stake\.win\)/.test(card) &&
      /Stake unavailable/.test(card) &&
      /\{signalsStakeShown \?\? '—'\}/.test(card) &&
      !/numberOfLines[\s\S]{0,120}signalsStakeShown \?\?/.test(card) &&
      /metric: \{[\s\S]*?flexBasis: '30%'[\s\S]*?maxWidth: '32%'/.test(card) &&
      !/flexBasis: '46%'/.test(card) &&
      !/flexBasis: '100%'/.test(card),
  );
  check(
    'Signals movement chip uses a true minus; the board chip does not',
    card.includes('trueMinus(movementSummary.label)') &&
      card.split('trueMinus(movementSummary.label)').length === 2,
  );
  check(
    'a later day joins the clock; today stays the clock',
    signalsContextTime(null, '8:00 PM ET') === '8:00 PM ET' &&
      signalsContextTime('Sat 10/17', '8:00 PM ET') === 'Sat 10/17 · 8:00 PM ET',
  );
  const samePrice = signalsPriceText('-110', 'DraftKings');
  const movedNow = signalsNowLine({ line: '-8.5', price: '-110', priceDiffers: false, book: 'DraftKings' });
  const priceNow = signalsNowLine({ line: null, price: '-105', priceDiffers: true, book: 'DraftKings' });
  check(
    'VoiceOver uses the same price text as the headline, then the Now line the screen shows',
    signalsHeroSpeech({ decisionPrice: '-110', book: 'DraftKings' }) === samePrice &&
      signalsHeroSpeech({ decisionPrice: '-110', book: 'DraftKings', now: null }) === samePrice &&
      !signalsHeroSpeech({ decisionPrice: '-110', book: 'DraftKings' }).includes('Now') &&
      signalsHeroSpeech({ decisionPrice: '-110', book: 'DraftKings', now: priceNow }) ===
        `${samePrice}. ${priceNow}`,
  );
  check(
    'a moved line is a Now line, and an unchanged card is not',
    movedNow === `DraftKings line now ${MINUS}8.5 (${MINUS}110)` &&
      priceNow === `DraftKings now (${MINUS}105)` &&
      signalsNowLine({ line: '-4.5', price: '-110', priceDiffers: false, book: 'MGM' }) ===
        `MGM line now ${MINUS}4.5 (${MINUS}110)` &&
      signalsNowLine({ line: '-8.5', price: '-105', priceDiffers: true, book: 'DK' }) ===
        `DK line now ${MINUS}8.5 (${MINUS}105)` &&
      signalsNowLine({ line: null, price: '-110', priceDiffers: false, book: 'DK' }) === null &&
      signalsNowLine({ line: '-8.5', price: null, priceDiffers: false, book: 'DK' }) === null,
  );
  check(
    'a plain moved price does not restate Locked under the decision hero',
    /heroPrice\?\.showLockedCaption && \(heroPrice\.stale \|\| heroPrice\.untracked\)/.test(card),
  );
  check('wrapped price stays on the trailing edge', /betRight: \{[\s\S]*?marginLeft: 'auto'/.test(card));
  const slip = readFileSync(join(__dirname, '../src/components/AddToPlayButton.tsx'), 'utf-8');
  const track = readFileSync(join(__dirname, '../src/components/TrackButton.tsx'), 'utf-8');
  const tallOmitsSlop = (src: string) => {
    const start = src.indexOf('if (tall)');
    const slop = src.indexOf('hitSlop=', start);
    const between = start >= 0 && slop > start ? src.slice(start, slop) : '';
    return between.includes('styles.btnTall') && between.includes('</Pressable>');
  };
  check('tall Slip and Track omit the compact hit slop', tallOmitsSlop(slip) && tallOmitsSlop(track));
  check('Slip and Track can be 44pt with a checkmark and a tint outline',
    /btnTall: \{[\s\S]*?minHeight: 44/.test(slip) && /btnTall: \{[\s\S]*?minHeight: 44/.test(track) &&
    /inPlay \? 'checkmark'/.test(slip) && /tracked \? 'checkmark'/.test(track) &&
    !/colors\.info/.test(slip) && !/colors\.info/.test(track));
}

console.log(failed === 0 ? '\nALL PASS' : `\n${failed} FAILURE(S)`);
if (failed > 0) process.exit(1);

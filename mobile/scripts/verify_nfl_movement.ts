/**
 * Standalone verification for the NFL movement + pick-timing plumbing
 * (session 121). Run with:
 *
 *   npx tsx scripts/verify_nfl_movement.ts
 *
 * Pins: gameMarketForModel maps the two NFL card models into the odds table
 * (movement machinery on) while other nfl_ ids stay null; computeMovement's
 * new spreads branch flags home/away line moves in the right direction and
 * leaves the fixed ±1.5 runline untouched; line-only mode (NFL) never uses
 * the cross-book price delta and reports favorable line moves; nflTimingInfo
 * distinguishes the opener's hard lock from wind's re-pricing.
 */

import {
  computeMovement,
  formatSideLine,
  gameMarketForModel,
  isNflLineOnly,
  lineForSide,
  movementFromLatest,
  nflTimingInfo,
} from '../src/lib/markets';
import type { LatestDkOddsRow, Pick, PickSide } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function mkPick(over: Partial<Pick>): Pick {
  return {
    pick_id: 1,
    game_id: 'NFL_2026_02_NYJ_MIA',
    model_id: 'nfl_opener_spread',
    sport: 'NFL',
    game_date: '2026-09-20',
    game_time: '2026-09-20T17:00:00+00:00',
    pick_side: 'home' as PickSide,
    pick_label: 'NYJ @ MIA — MIA -3.5 (Opener -1.5 vs Pinnacle, MGM)',
    model_probability: 0.5818,
    dk_implied_prob: 0.55,
    edge: 0.03,
    dk_odds: -108,
    scored_line: -3.5,
    kelly_fraction: 0.01,
    recommended_bet: 100,
    bankroll_at_pick: 10000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: null,
    result: null,
    profit_flat: null,
    profit_kelly: null,
    settled_at: null,
    created_at: '2026-09-15T13:31:00+00:00',
    player_id: null,
    pitcher_throw_hand: null,
    is_live: null,
    inning_at_pick: null,
    score_diff_at_pick: null,
    public_bet_pct: null,
    public_money_pct: null,
    closing_dk_odds: null,
    closing_line: null,
    clv_pct: null,
    clv_captured_at: null,
    dk_bet_link: null,
    ...over,
  } as Pick;
}

function snap(over: Partial<LatestDkOddsRow>): LatestDkOddsRow {
  return {
    game_id: 'NFL_2026_02_NYJ_MIA',
    game_date: '2026-09-20',
    market: 'spreads',
    home_price: -110,
    away_price: -110,
    spread_home: -3.5,
    total_line: null,
    over_price: null,
    under_price: null,
    snapshot_at: '2026-09-20T13:30:00+00:00',
  } as LatestDkOddsRow;
}

// ── market mapping ──────────────────────────────────────────────────────────
check('nfl_wind_totals → totals', gameMarketForModel('nfl_wind_totals') === 'totals');
check('nfl_opener_spread → spreads', gameMarketForModel('nfl_opener_spread') === 'spreads');
check('unknown nfl_ model stays null', gameMarketForModel('nfl_future_thing') === null);
check('MLB mapping unchanged', gameMarketForModel('mlb_over_under') === 'totals');
check('isNflLineOnly', isNflLineOnly('nfl_wind_totals') && !isNflLineOnly('mlb_runline'));

// ── spreads line movement (home-relative scored_line) ───────────────────────
{
  // Home side locked MIA -3.5; market now MIA -5.0 → home entry worse? No:
  // spread_home -3.5 → -5.0 is delta -1.5 → AGAINST home (laying more).
  const m = computeMovement(
    mkPick({ pick_side: 'home' }),
    { ...snap({}), spread_home: -5.0 },
    'spreads',
    { lineOnly: true },
  );
  check('home side: home spread shrinking = against', m?.severity === 'skip' && m.lineMovedAgainst === true);
}
{
  // Home side, spread_home -3.5 → -2.5 (delta +1.0) → favorable for home entry.
  const m = computeMovement(
    mkPick({ pick_side: 'home' }),
    { ...snap({}), spread_home: -2.5 },
    'spreads',
    { lineOnly: true },
  );
  check('home side: home spread growing = favorable (lineOnly good)',
    m?.severity === 'good' && m.lineOnly === true && m.priceShiftPp === null);
}
{
  // Away side locked NYJ +3.5 (spread_home -3.5); market now spread_home -2.5
  // (away only gets +2.5) → against away.
  const m = computeMovement(
    mkPick({ pick_side: 'away', scored_line: -3.5 }),
    { ...snap({}), spread_home: -2.5 },
    'spreads',
    { lineOnly: true },
  );
  check('away side: home spread rising = against', m?.severity === 'skip');
}
{
  // Fixed ±1.5 runline: delta 0 → no line movement; price steam still works
  // for non-lineOnly models exactly as before.
  const m = computeMovement(
    mkPick({ model_id: 'mlb_runline', sport: 'MLB', pick_side: 'home', scored_line: -1.5, dk_odds: -110 }),
    { ...snap({}), spread_home: -1.5, home_price: -130 },
    'spreads',
  );
  check('runline: fixed spread, price steam still flags caution',
    m?.severity === 'caution' && m.lineMovedAgainst === false);
}

// ── line-only mode ignores cross-book price deltas ──────────────────────────
{
  // Locked at MGM -124 vs DK -110 today: a 3pp cross-book delta that is NOT
  // movement. Line unchanged → no chip at all.
  const m = computeMovement(
    mkPick({ dk_odds: -124 }),
    { ...snap({}), spread_home: -3.5, home_price: -110 },
    'spreads',
    { lineOnly: true },
  );
  check('lineOnly: cross-book price delta produces no movement', m === null);
}
{
  // Same pick WITHOUT lineOnly would have read the price delta as favorable —
  // the bug lineOnly exists to prevent.
  const m = computeMovement(
    mkPick({ dk_odds: -124 }),
    { ...snap({}), spread_home: -3.5, home_price: -110 },
    'spreads',
  );
  check('control: without lineOnly the cross-book delta reads as movement', m?.severity === 'good');
}
{
  // movementFromLatest applies lineOnly automatically for nfl_ models.
  const m = movementFromLatest(
    mkPick({ dk_odds: -124 }),
    snap({}),
  );
  check('movementFromLatest: NFL model auto line-only', m === null);
}

// ── wind totals (under) ─────────────────────────────────────────────────────
{
  // Under 43.5 priced Sunday morning; market total now 41.5 → the under entry
  // is gone → against.
  const m = computeMovement(
    mkPick({
      model_id: 'nfl_wind_totals', pick_side: 'under', scored_line: 43.5, dk_odds: -105,
    }),
    { ...snap({}), spread_home: null, total_line: 41.5, over_price: -110, under_price: -110 },
    'totals',
    { lineOnly: true },
  );
  check('wind under: total dropping = against', m?.severity === 'skip');
}
{
  // Total rose 43.5 → 44.5 → a better under entry than the card took.
  const m = computeMovement(
    mkPick({
      model_id: 'nfl_wind_totals', pick_side: 'under', scored_line: 43.5, dk_odds: -105,
    }),
    { ...snap({}), spread_home: null, total_line: 44.5, over_price: -110, under_price: -110 },
    'totals',
    { lineOnly: true },
  );
  check('wind under: total rising = favorable', m?.severity === 'good' && m.lineOnly === true);
}

// ── side-relative line display ──────────────────────────────────────────────
// Spreads are stored HOME-relative, so an away pick labeled "NYJ +5" carries
// scored_line -5. Showing "-5" beside that label reads as a different bet.
{
  check('away spread flips sign for display', lineForSide(-5, 'away', 'spreads') === 5);
  check('home spread unchanged', lineForSide(-5, 'home', 'spreads') === -5);
  check('totals never flip (under)', lineForSide(41.5, 'under', 'totals') === 41.5);
  check('totals never flip (over)', lineForSide(41.5, 'over', 'totals') === 41.5);
  check('null passes through', lineForSide(null, 'away', 'spreads') === null);
  check('away spread formats with + sign', formatSideLine(-5, 'away', 'spreads') === '+5');
  check('home spread keeps -', formatSideLine(-5, 'home', 'spreads') === '-5');
  check('totals format unsigned', formatSideLine(41.5, 'under', 'totals') === '41.5');
  check('missing line renders em dash', formatSideLine(null, 'away', 'spreads') === '—');
  // The full chip string a day-of user reads on an away opener pick.
  const m = computeMovement(
    mkPick({ pick_side: 'away', scored_line: -5 }),
    { ...snap({}), spread_home: -3 },
    'spreads',
    { lineOnly: true },
  );
  const chip =
    `Line ${formatSideLine(m!.scoredLine, 'away', 'spreads')} → ` +
    `${formatSideLine(m!.currentLine, 'away', 'spreads')}`;
  check('away opener chip matches its label orientation', chip === 'Line +5 → +3', chip);
}

// ── timing info ─────────────────────────────────────────────────────────────
{
  const opener = nflTimingInfo(mkPick({}));
  const wind = nflTimingInfo(mkPick({ model_id: 'nfl_wind_totals' }));
  const mlb = nflTimingInfo(mkPick({ model_id: 'mlb_moneyline', sport: 'MLB' }));
  check('opener timing verb = Locked', opener?.verb === 'Locked');
  check('opener note says never re-priced', Boolean(opener?.note.includes('never re-priced')));
  check('wind timing verb = Priced', wind?.verb === 'Priced');
  check('wind note says re-priced each run', Boolean(wind?.note.toLowerCase().includes('re-priced')));
  check('non-NFL models have no timing info', mlb === null);
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
if (failures > 0) process.exit(1);

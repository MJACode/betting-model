/**
 * Standalone verification for the sport-toggle signal badge
 * (signalCountsBySport in src/lib/lineMovementBoard.ts). Run with:
 *
 *   npx tsx scripts/verify_signal_counts.ts
 *
 * Pins: counts only picks that clear their model's action threshold; groups
 * across ALL sports (the toggle's whole point); omits zero-signal sports so no
 * empty badge renders; and — the load-bearing invariant — the badge for the
 * selected sport equals what the Signals sub-tab shows for it.
 */

import { signalCountsBySport } from '../src/lib/lineMovementBoard';
import { isUnlockedPreview, passesActionFilter } from '../src/lib/thresholds';
import { todayET } from '../src/lib/format';
import type { EnrichedPick, Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function ep(over: Partial<Pick>): EnrichedPick {
  const pick = {
    pick_id: Math.random(), game_id: 'g', model_id: 'mlb_moneyline', sport: 'MLB',
    game_date: '2026-09-20', game_time: null, pick_side: 'home',
    pick_label: 'x', model_probability: 0.80, dk_implied_prob: 0.60, edge: 0.20,
    dk_odds: -110, scored_line: null, kelly_fraction: 0.02, recommended_bet: 100,
    bankroll_at_pick: 10000, injury_flag: null, injury_detail: null,
    signal_type: 'BET', confidence_tier: null, result: null, profit_flat: null,
    profit_kelly: null, settled_at: null, created_at: '2026-09-20T12:00:00Z',
    player_id: null, pitcher_throw_hand: null, is_live: null, inning_at_pick: null,
    score_diff_at_pick: null, public_bet_pct: null, public_money_pct: null,
    closing_dk_odds: null, closing_line: null, clv_pct: null, clv_captured_at: null,
    dk_bet_link: null, ...over,
  } as Pick;
  return { pick, game: null, weather: null, latestOdds: null } as EnrichedPick;
}

// A realistic Sept slate: MLB winding down, NFL live, NHL not started.
const board: EnrichedPick[] = [
  ep({}),                                                   // MLB signal
  ep({}),                                                   // MLB signal
  ep({ signal_type: 'NONE', edge: 0.001 }),                 // MLB dead zone
  ep({ signal_type: 'AVOID', edge: -0.20 }),                // MLB avoid
  ep({ sport: 'NFL', model_id: 'nfl_opener_spread', model_probability: 0.5818, edge: 0.028 }),
  ep({ sport: 'NFL', model_id: 'nfl_wind_totals', model_probability: 0.567, edge: 0.055 }),
  ep({ sport: 'NFL', model_id: 'nfl_wind_totals', model_probability: 0.51, edge: 0.055 }), // below bar
  ep({ sport: 'WNBA', model_id: 'wnba_moneyline', model_probability: 0.70, edge: 0.10 }),
];

const counts = signalCountsBySport(board);
check('MLB counts only its signals', counts.MLB === 2, JSON.stringify(counts));
check('NFL counted across the toggle', counts.NFL === 2);
check('sub-threshold NFL pick excluded', counts.NFL !== 3);
check('WNBA counted', counts.WNBA === 1);
check('zero-signal sport is absent (no empty badge)', !('NHL' in counts));
check('AVOID never counts', !Object.values(counts).some((n) => n > 2));

// The invariant: the badge must equal the Signals sub-tab count for that sport.
// (Both apply the same filter: action thresholds AND not an unlocked preview.)
for (const sport of ['MLB', 'NFL', 'WNBA']) {
  const subTab = board
    .filter((d) => d.pick.sport === sport)
    .filter((d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick)).length;
  check(`${sport} badge === Signals sub-tab count`, (counts[sport] ?? 0) === subTab,
    `badge ${counts[sport] ?? 0} vs sub-tab ${subTab}`);
}

// ── Unlocked look-ahead previews (Matt, 2026-08-24: "we can show betting lines
// but I don't want a signal to show unless it's locked") ─────────────────────
// UFC/golf picks scored days ahead re-score every refresh until they lock on
// game day, so a future-dated one is a PREVIEW and must never badge or count
// as a signal. NFL look-ahead picks are insert-once locked → still signals.
const today = todayET();
const future = new Date(Date.now() + 3 * 86400_000).toISOString().slice(0, 10);

check('future UFC BET is an unlocked preview',
  isUnlockedPreview({ sport: 'UFC', game_date: future }));
check('same-day UFC BET is locked (not a preview)',
  !isUnlockedPreview({ sport: 'UFC', game_date: today }));
check('future GOLF BET is an unlocked preview',
  isUnlockedPreview({ sport: 'GOLF', game_date: future }));
check('future NFL pick is NOT a preview (insert-once locked)',
  !isUnlockedPreview({ sport: 'NFL', game_date: future }));
check('future MLB date is NOT a preview (same-day sport, never scored ahead)',
  !isUnlockedPreview({ sport: 'MLB', game_date: future }));

const ufcBoard: EnrichedPick[] = [
  ep({ sport: 'UFC', model_id: 'ufc_total_rounds', model_probability: 0.70,
       edge: 0.15, game_date: future }),                      // preview — no badge
  ep({ sport: 'UFC', model_id: 'ufc_total_rounds', model_probability: 0.70,
       edge: 0.15, game_date: today }),                       // fight day — locked signal
];
const ufcCounts = signalCountsBySport(ufcBoard);
check('UFC badge counts only the locked fight-day signal', ufcCounts.UFC === 1,
  JSON.stringify(ufcCounts));

const previewOnly = signalCountsBySport([ufcBoard[0]]);
check('a board of only previews shows no badge at all', !('UFC' in previewOnly));

check('empty board yields no badges', Object.keys(signalCountsBySport([])).length === 0);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
if (failures > 0) process.exit(1);

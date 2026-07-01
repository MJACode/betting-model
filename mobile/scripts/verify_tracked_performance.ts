/**
 * Verify computeTrackedResults / trackedBetStatus (lib/trackedPerformance.ts).
 * Run: npx tsx scripts/verify_tracked_performance.ts
 */
import { computeTrackedResults, trackedBetStatus } from '../src/lib/trackedPerformance';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean) {
  if (cond) {
    console.log(`  PASS  ${name}`);
  } else {
    failures++;
    console.log(`  FAIL  ${name}`);
  }
}

function mkPick(overrides: Partial<Pick>): Pick {
  return {
    pick_id: 1,
    game_id: 'MLB_2026-06-30_NYY_BOS',
    model_id: 'mlb_moneyline',
    sport: 'MLB',
    game_date: '2026-06-30',
    pick_side: 'home',
    pick_label: 'BOS ML',
    model_probability: 0.72,
    dk_implied_prob: 0.6,
    edge: 0.12,
    dk_odds: -150,
    scored_line: null,
    kelly_fraction: 0.03,
    recommended_bet: 30,
    bankroll_at_pick: 1000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: 'HIGH',
    result: null,
    profit_flat: null,
    profit_kelly: null,
    settled_at: null,
    created_at: '2026-06-30T11:00:00Z',
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
    ...overrides,
  } as Pick;
}

const win = mkPick({ pick_id: 1, result: 'WIN', profit_flat: 66.67, game_date: '2026-06-28' });
const loss = mkPick({ pick_id: 2, result: 'LOSS', profit_flat: -100, game_date: '2026-06-29' });
const push = mkPick({ pick_id: 3, result: 'PUSH', profit_flat: 0, game_date: '2026-06-27' });
const open1 = mkPick({ pick_id: 4, result: null, game_date: '2026-07-01' });
const open2 = mkPick({ pick_id: 5, result: null, game_date: '2026-06-30' });
const noAction = mkPick({ pick_id: 6, result: 'NO_ACTION', profit_flat: null, game_date: '2026-06-26' });
const untrackedWin = mkPick({ pick_id: 99, result: 'WIN', profit_flat: 500 });

console.log('trackedBetStatus');
check('WIN → won', trackedBetStatus(win) === 'won');
check('LOSS → lost', trackedBetStatus(loss) === 'lost');
check('PUSH → push', trackedBetStatus(push) === 'push');
check('NO_ACTION → no_action', trackedBetStatus(noAction) === 'no_action');
check('null → open', trackedBetStatus(open1) === 'open');

console.log('computeTrackedResults — record + P&L');
const trackedIds = [1, 2, 3, 4, 5, 6, 7]; // 7 has no matching pick (pre-lock era)
const picks = [win, loss, push, open1, open2, noAction, untrackedWin];
const { rows, summary } = computeTrackedResults(trackedIds, picks);

check('untracked pick excluded', rows.every((r) => r.pick.pick_id !== 99));
check('missing id dropped silently', rows.length === 6);
check('wins counted', summary.wins === 1);
check('losses counted', summary.losses === 1);
check('pushes counted', summary.pushes === 1);
check('open counted', summary.open === 2);
check('settled = W+L+P', summary.settled === 3);
check('net = sum of settled profit', Math.abs(summary.net - (66.67 - 100 + 0)) < 1e-9);
check('NO_ACTION excluded from net + record', rows.find((r) => r.status === 'no_action')!.profit === 0);
check('ROI over settled stake', Math.abs((summary.roi ?? 0) - (66.67 - 100) / 300) < 1e-9);

console.log('computeTrackedResults — ordering');
check('open rows first', rows[0].status === 'open' && rows[1].status === 'open');
check('open sorted soonest-first', rows[0].pick.game_date <= rows[1].pick.game_date);
check(
  'settled sorted newest-first',
  rows[2].pick.game_date >= rows[3].pick.game_date && rows[3].pick.game_date >= rows[4].pick.game_date,
);

console.log('computeTrackedResults — edges');
const empty = computeTrackedResults([], []);
check('empty → no rows', empty.rows.length === 0);
check('empty → roi null', empty.summary.roi === null);
const dup = computeTrackedResults([1], [win, win]);
check('duplicate pick rows deduped', dup.rows.length === 1 && dup.summary.wins === 1);
const openOnly = computeTrackedResults([4], [open1]);
check('open-only → settled 0, roi null', openOnly.summary.settled === 0 && openOnly.summary.roi === null);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

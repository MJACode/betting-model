/**
 * Models and the flat book: a settled pick with NO book price contributes
 * no money. Settlement grades an unpriced pick at a −110 that never existed
 * (tracking/paper_tracker), so its profit_flat is fabricated: +90.91 per 100
 * on a win that could not have been placed. flatPnl drops that money. On
 * 2026-09-03 the Models tab showed UFC Total Rounds at +13.0% because it
 * had not. The Record tab now uses the posted stake (1 unit when the price
 * is missing). Yesterday does too. The block at the bottom pins that day:
 * an unpriced win plus a win at −140 is 2.00u on 2.40u risked, not the old
 * flat-book +71.43 on one priced pick.
 *
 * The fixture below is the REAL UFC settled set behind that screenshot (every
 * BET pick since 2026-04-14, values copied from the picks table), so the
 * Models numbers are the ones that tab printed.
 *
 *   npx tsx scripts/verify_unpriced_pnl.ts
 */
import { computeDailyResults } from '../src/lib/dailyResults';
import { computeBuiltInModelStats, computeCustomModelStats } from '../src/lib/customModelBacktest';
import { flatPnl, isModelPaused, setServerThresholds } from '../src/lib/thresholds';
import type { CustomModel, Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}
function near(a: number, b: number, eps = 0.005): boolean {
  return Math.abs(a - b) <= eps;
}

let nextId = 1;
function mk(over: Partial<Pick>): Pick {
  const id = nextId++;
  return {
    pick_id: id,
    game_id: `UFC_g${id}`,
    model_id: 'ufc_total_rounds',
    sport: 'UFC',
    game_date: '2026-08-22',
    game_time: '2026-08-23T00:00:00+00:00',
    pick_side: 'over',
    pick_label: 'Test pick',
    model_probability: 0.7,
    dk_implied_prob: 0.5,
    edge: 0.15,
    dk_odds: -110,
    scored_line: 2.5,
    kelly_fraction: 0.03,
    recommended_bet: 30,
    bankroll_at_pick: 1000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: 'HIGH',
    condition_status: null,
    result: 'WIN',
    profit_flat: 90.91,
    profit_kelly: 27,
    settled_at: '2026-08-23T21:04:06Z',
    created_at: '2026-08-22T03:51:11Z',
    player_id: null,
    pitcher_throw_hand: null,
    public_bet_pct: null,
    public_money_pct: null,
    closing_dk_odds: null,
    closing_line: null,
    clv_pct: null,
    line_clv_pts: null,
    clv_beat_close: null,
    clv_captured_at: null, clv_method: null, clv_close_book: null, clv_bet_book: null,
    is_live: false,
    inning_at_pick: null,
    score_diff_at_pick: null,
    dk_bet_link: null,
    best_book: null,
    best_odds: null,
    best_implied_prob: null,
    best_edge: null,
    best_bet_link: null,
    line_book: null,
    decision_book: null,
    decision_odds: null,
    decision_implied_prob: null,
    decision_edge: null,
    ...over,
  };
}

// ufc_total_rounds — 13 settled BETs, 7 priced (3-4) and 6 graded at the
// fabricated -110 (5-1). The screenshot's 8-5.
const ROUNDS: Pick[] = [
  mk({ model_probability: 0.7253, edge: 0.1012, dk_odds: -166, result: 'WIN', profit_flat: 60.24 }),
  mk({ model_probability: 0.6603, edge: 0.0951, dk_odds: -130, result: 'WIN', profit_flat: 76.92 }),
  mk({ model_probability: 0.6737, edge: 0.1388, dk_odds: -115, result: 'LOSS', profit_flat: -100 }),
  mk({ model_probability: 0.6261, edge: 0.1261, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ model_probability: 0.6566, edge: 0.101, dk_odds: -125, result: 'LOSS', profit_flat: -100 }),
  mk({ model_probability: 0.6338, edge: 0.1338, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ model_probability: 0.6735, edge: 0.1735, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ model_probability: 0.6206, edge: 0.1206, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ model_probability: 0.6338, edge: 0.1338, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ model_probability: 0.6636, edge: 0.0984, dk_odds: -130, result: 'WIN', profit_flat: 76.92 }),
  mk({ model_probability: 0.6264, edge: 0.1264, dk_odds: 100, result: 'LOSS', profit_flat: -100 }),
  mk({ model_probability: 0.671, edge: 0.0876, dk_odds: -140, result: 'LOSS', profit_flat: -100 }),
  mk({ model_probability: 0.6208, edge: 0.1208, dk_odds: null, result: 'LOSS', profit_flat: -100 }),
];

// ufc_method_of_victory — prob-only, every pick unpriced. 3-2, and no money.
const METHOD: Pick[] = [
  mk({ model_id: 'ufc_method_of_victory', pick_side: 'decision', scored_line: null, model_probability: 0.6601, edge: 0.3268, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ model_id: 'ufc_method_of_victory', pick_side: 'decision', scored_line: null, model_probability: 0.6709, edge: 0.3376, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ model_id: 'ufc_method_of_victory', pick_side: 'decision', scored_line: null, model_probability: 0.6543, edge: 0.3209, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ model_id: 'ufc_method_of_victory', pick_side: 'decision', scored_line: null, model_probability: 0.651, edge: 0.3176, dk_odds: null, result: 'LOSS', profit_flat: -100 }),
  mk({ model_id: 'ufc_method_of_victory', pick_side: 'decision', scored_line: null, model_probability: 0.7163, edge: 0.383, dk_odds: null, result: 'LOSS', profit_flat: -100 }),
];

// ufc_moneyline — every pick priced. The control: nothing here may move.
const ML: Pick[] = [
  mk({ model_id: 'ufc_moneyline', pick_side: 'home', scored_line: null, model_probability: 0.6947, edge: 0.1492, dk_odds: -120, result: 'WIN', profit_flat: 83.33 }),
  mk({ model_id: 'ufc_moneyline', pick_side: 'away', scored_line: null, model_probability: 0.749, edge: 0.1745, dk_odds: -135, result: 'WIN', profit_flat: 74.07 }),
  mk({ model_id: 'ufc_moneyline', pick_side: 'away', scored_line: null, model_probability: 0.6551, edge: 0.1673, dk_odds: 105, result: 'LOSS', profit_flat: -100 }),
];

const SETTLED = [...ROUNDS, ...METHOD, ...ML];

// Guard: the fixture assumes the three UFC models are live. A pause would turn
// every assertion below red on arithmetic that was never wrong -- and on
// 2026-09-11 it did: ufc_total_rounds is PAUSED in config.py and has been in
// production since, while the bundled mirror still called it live. Syncing the
// mirror made that real and took seven assertions with it.
//
// So the fixture now DECLARES its own world instead of borrowing the live one.
// What is under test is flatPnl's arithmetic -- an unpriced settled pick keeps
// its W-L and contributes no money -- which has nothing to do with whether the
// model is currently offered. Reaching for a still-live model instead would
// have moved the subject onto its own priced control and silently collapsed
// the two populations this file exists to keep apart.
setServerThresholds({
  ufc_total_rounds: { min_prob: 0.62, min_edge: 0.08, min_odds: -200, prob_only: false, paused: false },
  ufc_moneyline: { min_prob: 0.65, min_edge: 0.08, min_odds: -200, prob_only: false, paused: false },
  ufc_method_of_victory: { min_prob: 0.65, min_edge: 0, min_odds: -200, prob_only: true, paused: false },
});
for (const m of ['ufc_total_rounds', 'ufc_method_of_victory', 'ufc_moneyline']) {
  check(`fixture precondition: ${m} is not paused`, !isModelPaused(m));
}

// ── The rule itself ────────────────────────────────────────────────────────
check('flatPnl: priced win keeps its profit and $100 stake',
  (() => { const r = flatPnl({ dk_odds: -166, profit_flat: 60.24 }); return near(r.profit, 60.24) && r.staked === 100; })());
check('flatPnl: priced push stakes $100 and returns $0',
  (() => { const r = flatPnl({ dk_odds: -110, profit_flat: 0 }); return r.profit === 0 && r.staked === 100; })());
check('flatPnl: unpriced win is $0 profit on $0 stake — the -110 never existed',
  (() => { const r = flatPnl({ dk_odds: null, profit_flat: 90.91 }); return r.profit === 0 && r.staked === 0; })());
check('flatPnl: unpriced loss is $0 too — no stake, nothing to lose',
  (() => { const r = flatPnl({ dk_odds: null, profit_flat: -100 }); return r.profit === 0 && r.staked === 0; })());

// ── Models tab (computeBuiltInModelStats) ──────────────────────────────────
const rounds = computeBuiltInModelStats('ufc_total_rounds', SETTLED);
check('Models tab rounds: W-L keeps every settled pick (13 picks, 8-5)',
  rounds.picks === 13 && rounds.wins === 8 && rounds.losses === 5 && rounds.pushes === 0,
  `${rounds.picks} picks, ${rounds.wins}-${rounds.losses}-${rounds.pushes}`);
check('Models tab rounds: profit is the 7 priced picks only (-$185.92, not +$168.63)',
  near(rounds.profitFlat, -185.92), `profitFlat=${rounds.profitFlat}`);
check('Models tab rounds: stake is the 7 priced picks only ($700, not $1300)',
  rounds.stakedFlat === 700, `stakedFlat=${rounds.stakedFlat}`);
check('Models tab rounds: ROI is -26.6% — what the Record tab shows',
  near(rounds.roiFlat, -0.2656, 0.0005), `roiFlat=${rounds.roiFlat}`);

const method = computeBuiltInModelStats('ufc_method_of_victory', SETTLED);
check('Models tab method: 5 picks, 3-2',
  method.picks === 5 && method.wins === 3 && method.losses === 2,
  `${method.picks} picks, ${method.wins}-${method.losses}`);
check('Models tab method: nothing priced, so $0 on $0 and 0.0% (not +14.5%)',
  method.profitFlat === 0 && method.stakedFlat === 0 && method.roiFlat === 0,
  `profit=${method.profitFlat} staked=${method.stakedFlat} roi=${method.roiFlat}`);

const ml = computeBuiltInModelStats('ufc_moneyline', SETTLED);
check('Models tab moneyline (control): fully priced, unchanged at 2-1 +$57.40 / $300',
  ml.picks === 3 && ml.wins === 2 && ml.losses === 1 && near(ml.profitFlat, 57.4) && ml.stakedFlat === 300
    && near(ml.roiFlat, 0.1913, 0.0005),
  `${ml.wins}-${ml.losses} profit=${ml.profitFlat} staked=${ml.stakedFlat} roi=${ml.roiFlat}`);

const silentWin = mk({
  model_id: 'ufc_moneyline', pick_side: 'home', scored_line: null,
  model_probability: 0.7, edge: 0.15, dk_odds: -110, result: 'WIN', profit_flat: 90.91,
  discordPublish: 'unpublished',
});
const mlSilent = computeBuiltInModelStats('ufc_moneyline', [...SETTLED, silentWin]);
check('Models tab moneyline: an unpublished graded win stays out',
  mlSilent.picks === 3 && mlSilent.wins === 2 && near(mlSilent.profitFlat, 57.4),
  `${mlSilent.picks} picks, ${mlSilent.wins}-${mlSilent.losses}, profit=${mlSilent.profitFlat}`);
const unknownLoss = mk({
  model_id: 'ufc_moneyline', pick_side: 'away', scored_line: null,
  model_probability: 0.7, edge: 0.15, dk_odds: -110, result: 'LOSS', profit_flat: -100,
  discordPublish: 'unknown',
});
const mlUnknown = computeBuiltInModelStats('ufc_moneyline', [...ML, unknownLoss]);
check('Models tab moneyline: an unread ledger stamp still counts',
  mlUnknown.picks === 4 && mlUnknown.wins === 2 && mlUnknown.losses === 2,
  `${mlUnknown.picks} picks, ${mlUnknown.wins}-${mlUnknown.losses}`);

// ── Custom models on the settled fallback (computeCustomModelStats) ────────
const custom: CustomModel = {
  id: 'c1', name: 'Rounds, any', rules: [{ model_id: 'ufc_total_rounds' }],
  created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
};
const cs = computeCustomModelStats(custom, SETTLED);
check('Custom model on UFC rounds: same 13 picks, 8-5, -$185.92 on $700',
  cs.picks === 13 && cs.wins === 8 && cs.losses === 5 && near(cs.profitFlat, -185.92) && cs.stakedFlat === 700,
  `${cs.picks} picks, ${cs.wins}-${cs.losses}, profit=${cs.profitFlat} staked=${cs.stakedFlat}`);
const customSilent = computeCustomModelStats(
  { ...custom, rules: [{ model_id: 'ufc_moneyline' }] },
  [...ML, silentWin],
);
check('Custom backtest still counts the unpublished win',
  customSilent.picks === 4 && customSilent.wins === 3,
  `${customSilent.picks} picks, ${customSilent.wins}-${customSilent.losses}`);

// ── Yesterday's-results recap (computeDailyResults) ────────────────────────
// Posted stake, not the flat book. An unpriced win is 1 unit to win 1.
// A win at −140 risks 1.40 to win 1. Together: 2.00u on 2.40u risked.
const DAY = '2026-08-22';
const day = computeDailyResults(DAY, [
  mk({ game_date: DAY, model_probability: 0.6208, edge: 0.1208, dk_odds: null, result: 'WIN', profit_flat: 90.91 }),
  mk({ game_date: DAY, model_probability: 0.671, edge: 0.0876, dk_odds: -140, result: 'WIN', profit_flat: 71.43 }),
]);
check('Daily recap: both wins count (2-0) at the posted stake, 2.00u on 2.40u risked',
  day.overall.wins === 2 && day.overall.losses === 0
    && near(day.overall.units, 2) && near(day.overall.risked, 2.4)
    && near(day.overall.roi, 2 / 2.4),
  `${day.overall.wins}-${day.overall.losses} units=${day.overall.units} risked=${day.overall.risked} roi=${day.overall.roi}`);
const ufcDay = day.sports.find((s) => s.sport === 'UFC')?.total;
check('Daily recap: the sport row carries the same posted stake as the overall',
  !!ufcDay && near(ufcDay.units, 2) && near(ufcDay.risked, 2.4) && near(ufcDay.roi, 2 / 2.4),
  ufcDay ? `units=${ufcDay.units} risked=${ufcDay.risked} roi=${ufcDay.roi}` : 'no UFC row');

console.log(failures === 0 ? '\nAll checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);

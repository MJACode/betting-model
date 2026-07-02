/**
 * Standalone verification for the daily-recap aggregator (src/lib/dailyResults.ts).
 * No JS test runner is configured for the app, so — like the other verify_*.ts
 * scripts — we assert the pure function here and run with tsx:
 *
 *   npx tsx scripts/verify_daily_results.ts
 *
 * Pins: overall + per-sport + per-model records and ROI are correct; and that
 * off-date, NO_ACTION, sub-threshold, live, AVOID, and paused-model picks are
 * all excluded (they would otherwise inflate the counts).
 */
import { computeDailyResults } from '../src/lib/dailyResults';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}
function near(a: number, b: number, eps = 0.01): boolean {
  return Math.abs(a - b) <= eps;
}

const DATE = '2026-06-29';
const WIN_PROFIT = 90.91; // ~ -110 decimal payout on a $100 flat stake

let nextId = 1;
function mk(over: Partial<Pick>): Pick {
  return {
    pick_id: nextId++,
    game_id: `g${nextId}`,
    model_id: 'mlb_moneyline',
    sport: 'MLB',
    game_date: DATE,
    pick_side: 'home',
    pick_label: 'Test pick',
    model_probability: 0.75,
    dk_implied_prob: 0.5,
    edge: 0.15,
    dk_odds: -110,
    scored_line: null,
    kelly_fraction: 0.03,
    recommended_bet: 30,
    bankroll_at_pick: 1000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: 'HIGH',
    result: 'WIN',
    profit_flat: WIN_PROFIT,
    profit_kelly: 27,
    settled_at: '2026-06-30T12:00:00Z',
    created_at: '2026-06-29T11:00:00Z',
    player_id: null,
    pitcher_throw_hand: null,
    public_bet_pct: null,
    public_money_pct: null,
    closing_dk_odds: null,
    closing_line: null,
    clv_pct: null,
    clv_captured_at: null,
    is_live: false,
    inning_at_pick: null,
    score_diff_at_pick: null,
    dk_bet_link: null,
    ...over,
  };
}

const picks: Pick[] = [
  // MLB moneyline: 1W / 1L
  mk({ model_id: 'mlb_moneyline', result: 'WIN', profit_flat: WIN_PROFIT }),
  mk({ model_id: 'mlb_moneyline', result: 'LOSS', profit_flat: -100 }),
  // MLB over/under: 2W (prob 0.62 / edge 0.10 both clear 0.57/0.04)
  mk({ model_id: 'mlb_over_under', model_probability: 0.62, edge: 0.1, result: 'WIN', profit_flat: WIN_PROFIT }),
  mk({ model_id: 'mlb_over_under', model_probability: 0.62, edge: 0.1, result: 'WIN', profit_flat: WIN_PROFIT }),
  // WNBA assists: 1L / 1P (prob 0.72 / edge 0.12 clear 0.69/0.08)
  mk({ model_id: 'wnba_prop_player_assists', sport: 'WNBA', model_probability: 0.72, edge: 0.12, result: 'LOSS', profit_flat: -100 }),
  mk({ model_id: 'wnba_prop_player_assists', sport: 'WNBA', model_probability: 0.72, edge: 0.12, result: 'PUSH', profit_flat: 0 }),

  // ── Must all be EXCLUDED ──
  mk({ model_id: 'mlb_moneyline', result: 'NO_ACTION', profit_flat: null }), // not graded
  mk({ model_id: 'mlb_moneyline', game_date: '2026-06-28', result: 'WIN' }), // wrong date
  mk({ model_id: 'mlb_moneyline', model_probability: 0.6, result: 'WIN' }), // below 0.70 prob
  mk({ model_id: 'mlb_moneyline', is_live: true, result: 'WIN' }), // live pick
  mk({ model_id: 'mlb_over_under', signal_type: 'AVOID', model_probability: 0.62, edge: 0.1, result: 'WIN' }), // not a BET
  mk({ model_id: 'mlb_prop_batter_tb', sport: 'MLB', model_probability: 0.9, edge: 0.2, result: 'WIN' }), // paused model

  // ── PENDING: BET, clears the cut, but not yet graded (result NULL) ──
  mk({ model_id: 'mlb_prop_pitcher_walks', sport: 'MLB', model_probability: 0.7, edge: 0.12, result: null, profit_flat: null }),
  mk({ model_id: 'mlb_moneyline', signal_type: 'AVOID', result: null }), // AVOID null → NOT pending
];

const r = computeDailyResults(DATE, picks);

// Overall: 3W-2L-1P, picks 6, profit -9.09 + 181.82 - 100 = 72.73, staked 600
check('overall picks = 6', r.overall.picks === 6, `got ${r.overall.picks}`);
check('overall record 3-2-1', r.overall.wins === 3 && r.overall.losses === 2 && r.overall.pushes === 1,
  `${r.overall.wins}-${r.overall.losses}-${r.overall.pushes}`);
check('overall profitFlat ≈ 72.73', near(r.overall.profitFlat, 72.73), `got ${r.overall.profitFlat}`);
check('overall roiFlat ≈ 0.1212', near(r.overall.roiFlat, 72.73 / 600), `got ${r.overall.roiFlat}`);
check('overall winRate = 0.6', near(r.overall.winRate, 0.6), `got ${r.overall.winRate}`);

// Pending: the one BET/null pick counts; the AVOID/null and NO_ACTION do not.
check('pending = 1', r.pending === 1, `got ${r.pending}`);
check('pending excluded from graded picks', r.overall.picks === 6, `got ${r.overall.picks}`);

// Two sports, MLB first
check('two sports', r.sports.length === 2, `got ${r.sports.length}`);
check('MLB ordered before WNBA', r.sports[0]?.sport === 'MLB' && r.sports[1]?.sport === 'WNBA',
  r.sports.map((s) => s.sport).join(','));

const mlb = r.sports.find((s) => s.sport === 'MLB')!;
const wnba = r.sports.find((s) => s.sport === 'WNBA')!;

// MLB total: 3W-1L, picks 4, profit 172.73, staked 400
check('MLB total 3-1-0', mlb.total.wins === 3 && mlb.total.losses === 1 && mlb.total.pushes === 0,
  `${mlb.total.wins}-${mlb.total.losses}-${mlb.total.pushes}`);
check('MLB profitFlat ≈ 172.73', near(mlb.total.profitFlat, 172.73), `got ${mlb.total.profitFlat}`);
check('MLB roiFlat ≈ 0.4318', near(mlb.total.roiFlat, 172.73 / 400), `got ${mlb.total.roiFlat}`);

// MLB models: over_under (profit +181.82) sorted before moneyline (-9.09)
check('MLB has 2 models', mlb.models.length === 2, `got ${mlb.models.length}`);
check('MLB models sorted by profit desc',
  mlb.models[0]?.modelId === 'mlb_over_under' && mlb.models[1]?.modelId === 'mlb_moneyline',
  mlb.models.map((m) => m.modelId).join(','));
check('mlb_over_under 2-0-0', mlb.models[0]?.wins === 2 && mlb.models[0]?.losses === 0, '');
check('mlb_moneyline profit ≈ -9.09', near(mlb.models[1]?.profitFlat ?? 0, -9.09), `got ${mlb.models[1]?.profitFlat}`);
check('paused model excluded from MLB', !mlb.models.some((m) => m.modelId === 'mlb_prop_batter_tb'), '');

// WNBA total: 0W-1L-1P, picks 2, profit -100, staked 200
check('WNBA total 0-1-1', wnba.total.wins === 0 && wnba.total.losses === 1 && wnba.total.pushes === 1,
  `${wnba.total.wins}-${wnba.total.losses}-${wnba.total.pushes}`);
check('WNBA roiFlat = -0.5', near(wnba.total.roiFlat, -0.5), `got ${wnba.total.roiFlat}`);

// Graded picks list: the 6 counted picks, sorted sport-order then profit desc,
// with every excluded pick (off-date, live, AVOID, paused, sub-threshold,
// NO_ACTION, pending) absent.
check('gradedPicks has the 6 counted picks', r.gradedPicks.length === 6, `got ${r.gradedPicks.length}`);
check('gradedPicks all on-date settled BETs',
  r.gradedPicks.every((p) => p.game_date === DATE && p.signal_type === 'BET' && !p.is_live
    && (p.result === 'WIN' || p.result === 'LOSS' || p.result === 'PUSH')), '');
check('gradedPicks MLB before WNBA',
  r.gradedPicks.findIndex((p) => p.sport === 'WNBA') === 4,
  r.gradedPicks.map((p) => p.sport).join(','));
check('gradedPicks profit desc within sport',
  Number(r.gradedPicks[0]?.profit_flat) === WIN_PROFIT && Number(r.gradedPicks[3]?.profit_flat) === -100,
  r.gradedPicks.map((p) => p.profit_flat).join(','));
check('paused model absent from gradedPicks',
  !r.gradedPicks.some((p) => p.model_id === 'mlb_prop_batter_tb'), '');

// Empty day → empty result
const empty = computeDailyResults(DATE, []);
check('empty day → 0 picks, no sports, 0 pending, no graded list',
  empty.overall.picks === 0 && empty.sports.length === 0 && empty.pending === 0
    && empty.gradedPicks.length === 0, '');

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

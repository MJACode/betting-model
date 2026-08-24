/**
 * Standalone verification for the NCAAF sport wiring. Run with:
 *
 *   npx tsx scripts/verify_ncaaf_ui.ts
 *
 * NCAAF is the first sport whose live model is a MARGIN REGRESSION rather than
 * a classifier, and two of its three registry rows still carry dead classifier
 * artifacts. So the load-bearing assertions here are: ncaaf_spread reaches the
 * board at its real gate, and ncaaf_moneyline / ncaaf_over_under can NEVER
 * surface a bet no matter how good their numbers look.
 */

import { SPORTS, type Sport } from '../src/hooks/useSportFilter';
import { MODEL_META, sportOfModel, modelShort } from '../src/lib/modelMeta';
import {
  ACTION_THRESHOLDS, PAUSED_MODELS, isModelPaused, passesActionFilter,
} from '../src/lib/thresholds';
import { gameMarketForModel } from '../src/lib/markets';
import { GROUP_ORDER, statsForSport } from '../src/lib/statCatalog';
import { ALL_SPORTS } from '../src/lib/dailyResults';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function pick(over: Partial<Pick>): Pick {
  return {
    pick_id: 1, game_id: 'NCAAF_2026-09-05_toledo_ohio-state',
    model_id: 'ncaaf_spread', sport: 'NCAAF', game_date: '2026-09-05',
    game_time: null, pick_side: 'home', pick_label: 'Ohio State -3.5',
    model_probability: 0.66, dk_implied_prob: 0.524, edge: 0.136,
    dk_odds: -110, scored_line: -3.5, kelly_fraction: 0.02,
    recommended_bet: 100, bankroll_at_pick: 10000, injury_flag: null,
    injury_detail: null, signal_type: 'BET', confidence_tier: null,
    result: null, profit_flat: null, profit_kelly: null, settled_at: null,
    created_at: '2026-09-05T10:00:00Z', player_id: null,
    pitcher_throw_hand: null, is_live: null, inning_at_pick: null,
    score_diff_at_pick: null, public_bet_pct: null, public_money_pct: null,
    closing_dk_odds: null, closing_line: null, clv_pct: null,
    clv_captured_at: null, dk_bet_link: null, ...over,
  } as Pick;
}

// ── Sport registration ───────────────────────────────────────────────────────
check('NCAAF is in the sport toggle', SPORTS.includes('NCAAF' as Sport));
check('NCAAF appears in the daily recap sport order', ALL_SPORTS.includes('NCAAF'));
check('NCAAF sits next to NFL in the toggle (football grouped)',
  Math.abs(SPORTS.indexOf('NCAAF' as Sport) - SPORTS.indexOf('NFL' as Sport)) === 1);

// ── Model metadata ───────────────────────────────────────────────────────────
for (const id of ['ncaaf_spread', 'ncaaf_moneyline', 'ncaaf_over_under']) {
  check(`${id} has display metadata`, !!MODEL_META[id]);
  check(`${id} maps to the NCAAF sport`, sportOfModel(id) === 'NCAAF');
}
check('spread label does not leak a model id', !modelShort('ncaaf_spread').includes('_'));
check('no NCAAF prop models exist (game-level sport only)',
  Object.keys(MODEL_META).filter((m) => m.startsWith('ncaaf')).length === 3);

// ── Odds market mapping ──────────────────────────────────────────────────────
check('ncaaf_spread prices against the spreads market',
  gameMarketForModel('ncaaf_spread') === 'spreads');
check('ncaaf_over_under prices against totals',
  gameMarketForModel('ncaaf_over_under') === 'totals');
check('ncaaf_moneyline prices against h2h',
  gameMarketForModel('ncaaf_moneyline') === 'h2h');

// ── Thresholds mirror config.py ──────────────────────────────────────────────
// min_prob IS the +/-5.5 disagreement gate expressed as a cover probability;
// min_edge is 0 on purpose (the validated rule is the disagreement, not price).
check('ncaaf_spread prob floor mirrors the validated gate',
  ACTION_THRESHOLDS['ncaaf_spread']?.min_prob === 0.63,
  String(ACTION_THRESHOLDS['ncaaf_spread']?.min_prob));
check('ncaaf_spread edge floor is 0 (disagreement gate, not a price filter)',
  ACTION_THRESHOLDS['ncaaf_spread']?.min_edge === 0.0);

// ── The pause is the safety property ─────────────────────────────────────────
check('ncaaf_moneyline is paused', isModelPaused('ncaaf_moneyline'));
check('ncaaf_over_under is paused', isModelPaused('ncaaf_over_under'));
check('ncaaf_spread is NOT paused', !isModelPaused('ncaaf_spread'));
check('both dead classifiers are in the bundled offline fallback set',
  PAUSED_MODELS.has('ncaaf_moneyline') && PAUSED_MODELS.has('ncaaf_over_under'));

// A paused model must never surface a bet even with spectacular numbers —
// their registry rows still point at classifiers that held out at AUC ~0.49.
check('a paused NCAAF model cannot surface even at 99% / +40% edge',
  !passesActionFilter(pick({
    model_id: 'ncaaf_over_under', model_probability: 0.99, edge: 0.40,
  })));

// ── The live model reaches the board ─────────────────────────────────────────
check('a spread pick above the gate surfaces',
  passesActionFilter(pick({ model_probability: 0.66, edge: 0.136 })));
check('a spread pick below the gate does not surface',
  !passesActionFilter(pick({ model_probability: 0.58, edge: 0.136 })));
check('a spread pick at zero edge still surfaces when prob clears the gate',
  passesActionFilter(pick({ model_probability: 0.66, edge: 0.0 })),
  'edge floor is 0 by design');
check('an AVOID spread pick never surfaces',
  !passesActionFilter(pick({ signal_type: 'AVOID', edge: -0.20 })));

// ── Stats tab ────────────────────────────────────────────────────────────────
// CFBD player data is not ingested — team stats only. The Stats tab must show
// its empty state rather than an empty leaderboard with a live stat selector.
check('NCAAF has no stat groups (empty state, not a broken leaderboard)',
  GROUP_ORDER.NCAAF.length === 0);
check('NCAAF has no stats in the catalog',
  statsForSport('NCAAF' as Sport).length === 0);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

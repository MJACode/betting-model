/**
 * Standalone verification for the NCAAF sport wiring. Run with:
 *
 *   npx tsx scripts/verify_ncaaf_ui.ts
 *
 * NCAAF is the sport where none of the live models is a calibrated classifier
 * (the 42-config search found none — §31): ncaaf_over_under is a TOTAL
 * REGRESSION and both spread tiers are a CROSS-BOOK OPENER rule. ncaaf_moneyline
 * still carries a dead AUC~0.50 classifier and is paused.
 *
 * The load-bearing assertions are: the live rules reach the board at their real
 * gates, the two spread tiers are DISJOINT (they must never double-stake one
 * game), and a paused model can NEVER surface a bet however good it looks.
 *
 * Thresholds are read from ACTION_THRESHOLDS rather than pinned to literals.
 * The pinned version of this file went red on 2026-08-26 when over_under was
 * unpaused and the spread gate moved 0.63 -> 0.55, and stayed red — a stale
 * assertion is worse than no assertion, because it trains you to ignore the
 * script that would have caught a real regression.
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
// The real invariant is the SHAPE, not the count: NCAAF is a game-level sport
// with no player-prop market, so no NCAAF model may be typed as a prop. Pinning
// the count instead broke the moment ncaaf_spread_premium and the two live
// lanes were added, without any of them being wrong.
check('no NCAAF prop models exist (game-level sport only)',
  Object.keys(MODEL_META)
    .filter((m) => m.startsWith('ncaaf'))
    .every((m) => MODEL_META[m].type === 'game'));
for (const id of ['ncaaf_spread_premium', 'ncaaf_live_win_prob', 'ncaaf_live_total']) {
  check(`${id} has display metadata`, !!MODEL_META[id]);
  check(`${id} maps to the NCAAF sport`, sportOfModel(id) === 'NCAAF');
}

// ── Odds market mapping ──────────────────────────────────────────────────────
check('ncaaf_spread prices against the spreads market',
  gameMarketForModel('ncaaf_spread') === 'spreads');
check('ncaaf_over_under prices against totals',
  gameMarketForModel('ncaaf_over_under') === 'totals');
check('ncaaf_moneyline prices against h2h',
  gameMarketForModel('ncaaf_moneyline') === 'h2h');

// ── Thresholds mirror config.py ──────────────────────────────────────────────
// For all three live rules the GATE is the filter (a disagreement threshold or
// an opener deviation), so min_edge is 0 on purpose — a price floor would cut
// picks the walk-forward never excluded. min_prob only has to sit at or under
// the rule's own validated probability so it can never suppress a qualifying
// pick; it is deliberately NOT pinned to a literal here (see the header).
const NCAAF_LIVE_RULES = ['ncaaf_spread', 'ncaaf_spread_premium', 'ncaaf_over_under'];
for (const id of NCAAF_LIVE_RULES) {
  const t = ACTION_THRESHOLDS[id];
  check(`${id} has a threshold entry`, !!t);
  check(`${id} edge floor is 0 (the gate is the filter, not the price)`,
    t?.min_edge === 0.0, String(t?.min_edge));
  check(`${id} prob floor is a plausible cover probability`,
    !!t && t.min_prob > 0.5 && t.min_prob < 0.8, String(t?.min_prob));
}
// The two spread tiers are DISJOINT bands of the SAME opener rule (§31), so the
// premium tier must sit strictly above the standard one. If they ever inverted,
// one game could clear both and be staked twice.
check('spread_premium demands more conviction than spread',
  ACTION_THRESHOLDS['ncaaf_spread_premium'].min_prob >
  ACTION_THRESHOLDS['ncaaf_spread'].min_prob,
  `${ACTION_THRESHOLDS['ncaaf_spread'].min_prob} -> ${ACTION_THRESHOLDS['ncaaf_spread_premium'].min_prob}`);

// ── The pause is the safety property ─────────────────────────────────────────
// ncaaf_moneyline is the one still-dead classifier (AUC ~0.50, every edge cell
// negative at real Bovada prices — §31). over_under and both spread tiers were
// unpaused when they were REPLACED by rules, not when the classifiers improved.
check('ncaaf_moneyline is paused', isModelPaused('ncaaf_moneyline'));
check('the dead classifier is in the bundled offline fallback set',
  PAUSED_MODELS.has('ncaaf_moneyline'));
for (const id of NCAAF_LIVE_RULES) {
  check(`${id} is NOT paused (it is a live rule, not a classifier)`,
    !isModelPaused(id));
}

// A paused model must never surface a bet even with spectacular numbers —
// its registry row still points at a classifier that held out at AUC ~0.50.
check('a paused NCAAF model cannot surface even at 99% / +40% edge',
  !passesActionFilter(pick({
    model_id: 'ncaaf_moneyline', model_probability: 0.99, edge: 0.40,
  })));

// ── The live model reaches the board ─────────────────────────────────────────
check('a spread pick above the gate surfaces',
  passesActionFilter(pick({
    model_probability: ACTION_THRESHOLDS['ncaaf_spread'].min_prob + 0.01,
    edge: 0.136,
  })));
// Below the rule's own floor, whatever that floor currently is.
check('a spread pick below the gate does not surface',
  !passesActionFilter(pick({
    model_probability: ACTION_THRESHOLDS['ncaaf_spread'].min_prob - 0.01,
    edge: 0.136,
  })));
check('a spread pick at zero edge still surfaces when prob clears the gate',
  passesActionFilter(pick({
    model_probability: ACTION_THRESHOLDS['ncaaf_spread'].min_prob + 0.01,
    edge: 0.0,
  })),
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

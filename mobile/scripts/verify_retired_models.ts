/**
 * Standalone verification for RETIRED models. Run with:
 *
 *   npx tsx scripts/verify_retired_models.ts
 *
 * A retired model is one removed from the backend registries outright
 * (config.LIVE_MODELS / MODELS), so nothing will ever score another pick for
 * it. That is a different state from PAUSED, and the difference matters in the
 * app in exactly two places:
 *
 *   1. its old picks must never read as actionable again, and
 *   2. it must not be listed as a model you could follow,
 *
 * while everything that RENDERS HISTORY keeps working — the label, the market
 * mapping behind the Line Movement card — because those picks really happened
 * and stay in the DB (§1c: a pick that existed is the bet of record).
 *
 * The adversarial case, and the reason RETIRED_MODELS exists at all rather than
 * reusing PAUSED_MODELS: the server's model_action_thresholds row survives
 * until the next threshold_sync prune, and while it survives it reports
 * paused=false. passesActionFilter prefers the server store, so a retired model
 * dropped from the bundled PAUSED_MODELS list would have gone actionable again.
 */

import { MODEL_META } from '../src/lib/modelMeta';
import {
  ACTION_THRESHOLDS, PAUSED_MODELS, RETIRED_MODELS,
  isModelPaused, isModelRetired, passesActionFilter, setServerThresholds,
  thresholdFor, isLiveModel, isContaminatedPregamePick } from '../src/lib/thresholds';
import { gameMarketForModel } from '../src/lib/markets';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function pick(over: Partial<Pick>): Pick {
  return {
    pick_id: 1, game_id: 'MLB_2026-08-27_BOS_NYY',
    model_id: 'mlb_live_win_prob', sport: 'MLB', game_date: '2026-08-27',
    game_time: null, pick_side: 'home', pick_label: 'NYY ML (live)',
    model_probability: 0.80, dk_implied_prob: 0.60, edge: 0.20,
    dk_odds: -150, scored_line: null, kelly_fraction: 0.02,
    recommended_bet: 100, bankroll_at_pick: 10000, injury_flag: null,
    injury_detail: null, signal_type: 'BET', confidence_tier: null,
    result: null, profit_flat: null, profit_kelly: null, settled_at: null,
    created_at: '2026-08-27T22:00:00Z', player_id: null,
    pitcher_throw_hand: null, is_live: true, inning_at_pick: 5,
    score_diff_at_pick: 1, public_bet_pct: null, public_money_pct: null,
    closing_dk_odds: null, closing_line: null, clv_pct: null,
    clv_captured_at: null, dk_bet_link: null, ...over,
  } as Pick;
}

const RETIRED = ['mlb_live_win_prob', 'mlb_live_runline'];

// ── The set itself ───────────────────────────────────────────────────────────
check('the two binary MLB live models are retired',
  RETIRED.every((m) => RETIRED_MODELS.has(m) && isModelRetired(m)));
check('mlb_live_total_runs is NOT retired — it is the profitable live model',
  !isModelRetired('mlb_live_total_runs'));
check('retired is not paused (a retired model has nothing left to pause)',
  RETIRED.every((m) => !PAUSED_MODELS.has(m)));
check('a retired model carries no bundled threshold',
  RETIRED.every((m) => ACTION_THRESHOLDS[m] === undefined));
// 2026-08-30 (mike): the prob floor went 0.68 -> 0.70 with the live volume cut
// (config.MODEL_PROB_THRESHOLDS). This assertion still pinned 0.68 and had been
// failing since, which is how a red harness stops being read.
check('mlb_live_total_runs carries its current cut',
  ACTION_THRESHOLDS['mlb_live_total_runs']?.min_prob === 0.70 &&
  ACTION_THRESHOLDS['mlb_live_total_runs']?.min_edge === 0.14);

// ── Never actionable ─────────────────────────────────────────────────────────
setServerThresholds(null);
check('offline: a retired model BET is not actionable however good it looks',
  RETIRED.every((m) => !passesActionFilter(pick({ model_id: m }))));
check('offline: the live model that remains is still actionable at its cut',
  passesActionFilter(pick({
    model_id: 'mlb_live_total_runs', model_probability: 0.70, edge: 0.15,
  })));
check('offline: a retired model has no resolvable threshold',
  RETIRED.every((m) => thresholdFor(m) === null));

// The stale-server-row case this set exists for.
setServerThresholds({
  mlb_live_win_prob: { min_prob: 0.65, min_edge: 0.10, min_odds: null, prob_only: false, paused: false },
  mlb_live_runline: { min_prob: 0.65, min_edge: 0.10, min_odds: null, prob_only: false, paused: false },
  mlb_live_total_runs: { min_prob: 0.68, min_edge: 0.14, min_odds: null, prob_only: false, paused: false },
});
check('a stale un-paused server row cannot revive a retired model',
  RETIRED.every((m) => !passesActionFilter(pick({ model_id: m }))));
check('the server store still drives the live model that remains',
  passesActionFilter(pick({
    model_id: 'mlb_live_total_runs', model_probability: 0.70, edge: 0.15,
  })) &&
  !passesActionFilter(pick({
    model_id: 'mlb_live_total_runs', model_probability: 0.70, edge: 0.10,
  })));
setServerThresholds(null);

// ── History still renders ────────────────────────────────────────────────────
check('retired models keep their labels for picks already made',
  RETIRED.every((m) => !!MODEL_META[m]?.shortLabel));
check('retired live picks still map to their own market (Line Movement card)',
  gameMarketForModel('mlb_live_win_prob') === 'h2h' &&
  gameMarketForModel('mlb_live_runline') === 'spreads');

// ── The live-model partition (2026-08-30) ───────────────────────────────────
// `picks.is_live` carries two populations and only model_id separates them:
//   1. real in-play bets from the live scorers — these COUNT in every record;
//   2. the session-114 repair rows — ~14k PRE-GAME prop picks flagged is_live
//      because they were scored against an in-play price — which never do.
// Mirrors the `model_id LIKE '%\\_live\\_%'` predicate in v_public_track_record
// (migration track_record_include_live_models) and the Discord recap's
// _SETTLED_SQL, so all three publish the same population. The lists below are
// every model_id that has actually written an is_live row in production.
const LIVE_MODELS = [
  'mlb_live_total_runs', 'mlb_live_win_prob', 'mlb_live_runline',
  'ncaaf_live_total', 'ncaaf_live_win_prob',
];
const REPAIRED_PROP_MODELS = [
  'mlb_prop_batter_hits', 'mlb_prop_batter_hr', 'mlb_prop_batter_rbi',
  'mlb_prop_batter_runs', 'mlb_prop_batter_sb', 'mlb_prop_batter_tb',
  'mlb_prop_batter_walks', 'mlb_prop_pitcher_er', 'mlb_prop_pitcher_hits',
  'mlb_prop_pitcher_k', 'mlb_prop_pitcher_outs', 'mlb_prop_pitcher_walks',
  'wnba_prop_player_assists', 'wnba_prop_player_points', 'wnba_prop_player_pra',
  'wnba_prop_player_rebounds', 'wnba_prop_player_threes',
];
const PREGAME_MODELS = [
  'mlb_moneyline', 'mlb_over_under', 'mlb_runline', 'mlb_f5_moneyline',
  'wnba_moneyline', 'ncaaf_spread', 'ncaaf_over_under', 'nfl_wind_totals',
  'nfl_opener_spread', 'ufc_moneyline', 'golf_top10', 'nba_moneyline',
];

check('every live model is recognised as one',
  LIVE_MODELS.every(isLiveModel), LIVE_MODELS.filter((m) => !isLiveModel(m)).join(','));
check('no repaired prop model is mistaken for a live model',
  REPAIRED_PROP_MODELS.every((m) => !isLiveModel(m)),
  REPAIRED_PROP_MODELS.filter(isLiveModel).join(','));
check('no pre-game model is mistaken for a live model',
  PREGAME_MODELS.every((m) => !isLiveModel(m)),
  PREGAME_MODELS.filter(isLiveModel).join(','));

// The whole point: same flag, opposite verdicts, decided by model_id.
check('a real live bet is not treated as contaminated',
  LIVE_MODELS.every((m) => !isContaminatedPregamePick({ is_live: true, model_id: m })));
check('a repair row IS treated as contaminated',
  REPAIRED_PROP_MODELS.every((m) => isContaminatedPregamePick({ is_live: true, model_id: m })));
check('a pre-game row is never contaminated regardless of model',
  [...PREGAME_MODELS, ...REPAIRED_PROP_MODELS, ...LIVE_MODELS].every(
    (m) => !isContaminatedPregamePick({ is_live: false, model_id: m })
      && !isContaminatedPregamePick({ model_id: m })));

// Retired live models are still live models — they must keep grading out of
// history rather than being re-classified as contamination.
check('retired live models are still live models',
  isLiveModel('mlb_live_win_prob') && isLiveModel('mlb_live_runline'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

/**
 * Standalone verification that paused models are hidden from mobile catalog
 * surfaces. Run with:
 *
 *   npx tsx scripts/verify_paused_catalog.ts
 *
 * A pause is not a retirement: the model still exists, it still has a settled
 * record, and MODEL_META still names the picks it already made. What a pause
 * means on the phone (Matt, 2026-09-19) is that the catalog — the Models list,
 * the custom-model bet-type picker, the Stats "add this prop" button, today's
 * board — must not offer it as something to follow or bet.
 *
 * The pause source is `isModelPaused` (server `model_action_thresholds.paused`,
 * bundled `PAUSED_MODELS` fallback). A hand-copied set here would drift the
 * moment config.py moved.
 */

import { MODEL_META, BET_TYPE_GROUPS, betTypeGroups } from '../src/lib/modelMeta';
import {
  PAUSED_MODELS,
  isModelPaused,
  isModelRetired,
  setServerThresholds,
} from '../src/lib/thresholds';
import { propModelForStat, statForPropModel, STAT_CATALOG } from '../src/lib/statCatalog';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

setServerThresholds(null);

const PAUSED = [...PAUSED_MODELS];
check('the bundled pause set is non-empty (otherwise this file tests nothing)',
  PAUSED.length > 0, String(PAUSED.length));
check('every bundled pause is isModelPaused when the server store is empty',
  PAUSED.every((m) => isModelPaused(m)));

// ── Labels stay, so history still has a name ────────────────────────────────
check('paused models keep their MODEL_META labels for picks already made',
  PAUSED.every((m) => !!MODEL_META[m]?.shortLabel),
  PAUSED.filter((m) => !MODEL_META[m]?.shortLabel).join(','));

// ── Bet-type picker ─────────────────────────────────────────────────────────
const pickerIds = betTypeGroups().flatMap((g) => g.options.map((o) => o.id));
check('betTypeGroups offers no paused model',
  pickerIds.every((id) => !isModelPaused(id)),
  pickerIds.filter(isModelPaused).join(','));
check('the module-load snapshot agrees (bundled fallback)',
  BET_TYPE_GROUPS.flatMap((g) => g.options.map((o) => o.id))
    .every((id) => !PAUSED_MODELS.has(id)));
check('an active game model is still a bet type you can build on',
  pickerIds.includes('mlb_moneyline'));
check('an active batter prop is still a bet type you can build on',
  pickerIds.includes('mlb_prop_batter_runs'));

// ── Stats add-pick ──────────────────────────────────────────────────────────
const hitsStat = STAT_CATALOG.find((d) => d.sport === 'MLB' && d.key === 'hits') ?? null;
const tbStat = STAT_CATALOG.find((d) => d.sport === 'MLB' && d.key === 'total_bases') ?? null;
const runsStat = STAT_CATALOG.find((d) => d.sport === 'MLB' && d.key === 'runs') ?? null;
const walksStat = STAT_CATALOG.find((d) => d.sport === 'MLB' && d.key === 'walks') ?? null;
check('fixture: batter hits is still paused', isModelPaused('mlb_prop_batter_hits'));
check('fixture: batter TB is still paused', isModelPaused('mlb_prop_batter_tb'));
check('fixture: batter runs is still live', !isModelPaused('mlb_prop_batter_runs') && !isModelRetired('mlb_prop_batter_runs'));
check('the Hits column stays on the leaderboard', hitsStat != null);
check('propModelForStat offers no model for a paused hits market',
  propModelForStat(hitsStat) === null);
check('propModelForStat offers no model for a paused TB market',
  propModelForStat(tbStat) === null);
check('propModelForStat still resolves a live batter prop (runs)',
  propModelForStat(runsStat) === 'mlb_prop_batter_runs');
check('propModelForStat still resolves a live batter prop (walks)',
  propModelForStat(walksStat) === 'mlb_prop_batter_walks');
check('a pick a paused model already made still opens its player\'s stat page',
  statForPropModel('mlb_prop_batter_hits')?.key === 'hits');

// ── Server flag wins, same helper every surface uses ────────────────────────
setServerThresholds({
  mlb_moneyline: { min_prob: 0.58, min_edge: 0.05, min_odds: -200, prob_only: false, paused: true },
  mlb_prop_batter_runs: { min_prob: 0.62, min_edge: 0.10, min_odds: -140, prob_only: false, paused: false },
});
check('isModelPaused prefers the server flag (live-in-bundle, paused-on-server)',
  isModelPaused('mlb_moneyline'));
check('betTypeGroups re-reads isModelPaused (moneyline drops when the server pauses it)',
  !betTypeGroups().flatMap((g) => g.options.map((o) => o.id)).includes('mlb_moneyline'));
check('a model the server leaves live still appears',
  betTypeGroups().flatMap((g) => g.options.map((o) => o.id)).includes('mlb_prop_batter_runs'));
setServerThresholds(null);
check('clearing the server store restores the bundled pause set',
  !isModelPaused('mlb_moneyline') && isModelPaused('mlb_prop_batter_hits'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

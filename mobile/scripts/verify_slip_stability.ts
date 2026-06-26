/**
 * Regression check for the parlay-tab-display bug: a slip selection must survive
 * the hourly delete+rescore. The picks table re-inserts rows with brand-new
 * pick_ids each run; keying the slip on the stable game|model|player key (not
 * pick_id) is what makes the selection re-resolve to the new row.
 *
 * Run: npx tsx scripts/verify_slip_stability.ts
 */
import { resolveSlipLegs, slipKeyForPick } from '../src/lib/parlay';
import type { EnrichedPick, Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  console.log(`${cond ? '[PASS]' : '[FAIL]'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!cond) failures++;
}

function pick(pickId: number, over: Partial<Pick> = {}): Pick {
  return {
    pick_id: pickId,
    game_id: 'MLB_2026-06-26_NYY_BOS',
    model_id: 'mlb_prop_batter_hits',
    sport: 'MLB',
    pick_side: 'over',
    pick_label: 'Aaron Judge Over 1.5 Hits',
    model_probability: 0.62,
    dk_implied_prob: 0.5,
    edge: 0.12,
    dk_odds: -110,
    signal_type: 'BET',
    player_id: '592450',
    ...over,
  } as unknown as Pick;
}
const ep = (p: Pick): EnrichedPick => ({ pick: p, game: null, bestOdds: null } as unknown as EnrichedPick);

// User adds the morning pick (id 1001) → slip stores its stable key.
const morning = pick(1001);
const key = slipKeyForPick(morning);
check('slipKey is game|model|player (no pick_id)', key === 'MLB_2026-06-26_NYY_BOS|mlb_prop_batter_hits|592450', key);

// Afternoon rescore: same market, BRAND-NEW pick_id (1057). Slip key unchanged.
const afternoon = pick(1057);
const r1 = resolveSlipLegs([ep(afternoon)], [key]);
check('selection survives pick_id churn', r1.legs.length === 1 && r1.missingKeys.length === 0,
  `legs=${r1.legs.length} resolvedPickId=${r1.legs[0]?.pickId}`);
check('resolved leg points at the NEW pick_id', r1.legs[0]?.pickId === 1057);

// Genuinely gone (market settled / de-listed) → reported as missing, not silently kept.
const r2 = resolveSlipLegs([], [key]);
check('truly-absent market reported missing', r2.legs.length === 0 && r2.missingKeys[0] === key);

console.log(failures === 0 ? '\nALL SLIP-STABILITY CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);

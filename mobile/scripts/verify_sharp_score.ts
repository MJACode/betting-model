/**
 * Standalone verification for the Sharp Score + contrarian tag
 * (src/lib/sharpScore.ts). No JS test runner is configured for the app, so —
 * like the parlay math (CLAUDE.md sessions 43/48) — we assert the pure functions
 * here and run with tsx:
 *
 *   npx tsx scripts/verify_sharp_score.ts
 *
 * Pins: non-BET → no score/tag; edge component scales with distance past the
 * model's bar; CLV pedigree lifts/sinks the score (and neutral when unproven);
 * contrarian thresholds; prob-only models score off probability; the 'sharp'
 * sort orders by score; determinism.
 */

import {
  contrarianTag,
  modelClvFor,
  setModelClv,
  sharpScore,
  type ModelClv,
} from '../src/lib/sharpScore';
import { sortPicks } from '../src/lib/pickSort';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}

/** Full Pick with sane defaults; override what a case needs. */
function mkPick(over: Partial<Pick> = {}): Pick {
  return {
    pick_id: 1,
    game_id: 'g1',
    model_id: 'mlb_moneyline',
    sport: 'MLB',
    game_date: '2026-06-25',
    game_time: '2026-06-25T23:10:00+00:00',
    pick_side: 'home',
    pick_label: 'Test',
    model_probability: 0.75,
    dk_implied_prob: 0.6,
    edge: 0.15,
    dk_odds: -110,
    scored_line: null,
    kelly_fraction: 0.02,
    recommended_bet: 20,
    bankroll_at_pick: 1000,
    injury_flag: null,
    injury_detail: null,
    signal_type: 'BET',
    confidence_tier: 'HIGH',
    result: null,
    profit_flat: null,
    profit_kelly: null,
    settled_at: null,
    created_at: '2026-06-25T00:00:00Z',
    player_id: null,
    pitcher_throw_hand: null,
    public_bet_pct: null,
    public_money_pct: null,
    closing_dk_odds: null,
    closing_line: null,
    clv_pct: null,
    clv_captured_at: null,
    is_live: null,
    inning_at_pick: null,
    score_diff_at_pick: null,
    dk_bet_link: null,
    best_book: null,
    best_odds: null,
    best_implied_prob: null,
    best_edge: null,
    best_bet_link: null,
    ...over,
  };
}

// Start with no CLV pedigree loaded (the cold-start / offline state).
setModelClv(null);

// 1. Non-BET picks produce neither a score nor a tag.
check('AVOID → no sharp score', sharpScore(mkPick({ signal_type: 'AVOID' })) === null);
check('NONE → no contrarian tag', contrarianTag(mkPick({ signal_type: 'NONE', public_bet_pct: 30 })) === null);

// 2. Edge component scales with distance past the model bar (mlb_moneyline min_edge 0.11).
//    edge 0.33 = 3× the bar → full 40; no public/CLV → pedigree 20 + contrarian 10 = 70.
const strongEdge = sharpScore(mkPick({ edge: 0.33 }))!;
check('edge 3× bar → edge part 40', Math.round(strongEdge.parts.edge) === 40, `edge=${strongEdge.parts.edge}`);
check('no CLV/public → score 70, band high', strongEdge.score === 70 && strongEdge.band === 'high', `score=${strongEdge.score}/${strongEdge.band}`);

//    A pick right at the bar earns ~0 edge points.
const atBar = sharpScore(mkPick({ edge: 0.11 }))!;
check('edge at bar → edge part ~0', atBar.parts.edge < 1, `edge=${atBar.parts.edge}`);

// 3. Contrarian tag thresholds (public_bet_pct = share on OUR side).
check('public 30% → sharp side', contrarianTag(mkPick({ public_bet_pct: 30 }))?.tone === 'sharp');
check('public 70% → crowded', contrarianTag(mkPick({ public_bet_pct: 70 }))?.tone === 'crowded');
check('public 50% → no tag', contrarianTag(mkPick({ public_bet_pct: 50 })) === null);

// 4. CLV pedigree lifts/sinks the score; neutral when unproven (small sample).
const proven: Record<string, ModelClv> = { mlb_moneyline: { beatRate: 0.8, avgClvPct: 2.1, settled: 50 } };
setModelClv(proven);
check('modelClvFor reads store', modelClvFor('mlb_moneyline')?.beatRate === 0.8);
const sharpProven = sharpScore(mkPick({ edge: 0.33, public_bet_pct: 30 }))!;
check('proven model → pedigree 40', Math.round(sharpProven.parts.pedigree) === 40, `ped=${sharpProven.parts.pedigree}`);
check('all three strong → score 100', sharpProven.score === 100, `score=${sharpProven.score}`);

setModelClv({ mlb_moneyline: { beatRate: 0.4, avgClvPct: -1, settled: 50 } });
check('weak CLV model → pedigree 0', Math.round(sharpScore(mkPick({ edge: 0.33 }))!.parts.pedigree) === 0);

setModelClv({ mlb_moneyline: { beatRate: 0.9, avgClvPct: 3, settled: 5 } });
const unproven = sharpScore(mkPick({ edge: 0.33 }))!;
check('tiny sample → pedigree neutral 20, not trusted', Math.round(unproven.parts.pedigree) === 20 && !unproven.parts.pedigreeKnown);

// 5. Prob-only model scores off probability. The bar is read from
// ACTION_THRESHOLDS, not hardcoded: mlb_prop_batter_hr's min_prob moved 0.20 ->
// 0.225 (session 60) and this assertion, which pinned the resulting 20, went
// red and stayed red. Assert the SHAPE (prob above the bar earns a positive,
// bounded edge part) so a future threshold change cannot make it a false alarm.
setModelClv(null);
const probOnly = sharpScore(mkPick({ model_id: 'mlb_prop_batter_hr', edge: 0, model_probability: 0.6 }))!;
check('prob-only → edge part derived from prob, not from edge',
  probOnly.parts.edge > 0 && probOnly.parts.edge <= 40, `edge=${probOnly.parts.edge}`);
const probOnlyAtBar = sharpScore(mkPick({ model_id: 'mlb_prop_batter_hr', edge: 0, model_probability: 0.2251 }))!;
check('prob-only at the bar → ~0 edge part',
  Math.round(probOnlyAtBar.parts.edge) === 0, `edge=${probOnlyAtBar.parts.edge}`);

// 6. The 'sharp' sort orders by score desc; non-BET sinks below scored BETs.
const lo = { pick: mkPick({ pick_id: 2, edge: 0.115 }) };          // just over bar → low
const hi = { pick: mkPick({ pick_id: 3, edge: 0.33, public_bet_pct: 30 }) }; // strong
const avoid = { pick: mkPick({ pick_id: 4, signal_type: 'AVOID', edge: 0.5 }) };
const sorted = sortPicks([lo, avoid, hi], 'sharp');
check('sharp sort: strongest first', sorted[0].pick.pick_id === 3, `order=${sorted.map((s) => s.pick.pick_id).join(',')}`);
check('sharp sort: non-BET last', sorted[2].pick.pick_id === 4);

// 7. Determinism.
const a = sharpScore(mkPick({ edge: 0.2, public_bet_pct: 35 }))!.score;
const b = sharpScore(mkPick({ edge: 0.2, public_bet_pct: 35 }))!.score;
check('deterministic', a === b, `${a} vs ${b}`);

console.log(failures === 0 ? '\nAll sharp-score checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);

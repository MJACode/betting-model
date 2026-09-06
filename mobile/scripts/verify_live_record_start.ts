/**
 * Standalone verification for the OFFICIAL LIVE DATE and the Retool mirror.
 * Run with:
 *
 *   npx tsx scripts/verify_live_record_start.ts
 *
 * Matt, 2026-09-04: "Just mirror retool for now. But only start tracking bets as
 * of 9/1 and on, that will be our official live date."
 *
 * Two things this pins, because both have already drifted once:
 *
 * 1. THE DATE IS STATED ONCE. It used to be spelled out in five files and four
 *    screens' copy as 2026-04-14, which is why moving it was a nine-file change.
 *    `lib/recordStart.ts` is now the only place it is written, and every screen
 *    and constant reads from it. A re-introduced literal is what this catches.
 *
 * 2. THE APP READS WHAT RETOOL READS. The Models tab used to read
 *    `v_model_full_outcome_record` — every scored pick re-graded at today's cut,
 *    which answers a different question from Retool's settled-BET-as-fired and
 *    gave a different number for the same model on the same day (mlb_moneyline
 *    -3.3% vs +23.8%, measured 2026-09-04). It now reads `v_public_track_record`,
 *    which is the view Retool is pointed at.
 *
 * The server is what actually filters, so this cannot prove the published number
 * — it proves the app asks the right view for the right window and says the
 * right date on screen.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import {
  BACKTEST_START,
  LIVE_RECORD_START,
  LIVE_RECORD_START_LABEL,
  LIVE_RECORD_START_SHORT,
  MIN_PICKS_FOR_COLOURED_ROI,
  SHADOW_TRACK_START,
} from '../src/lib/recordStart';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const SRC = join(import.meta.dirname, '..', 'src');

function walk(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}
const FILES = walk(SRC);

// ── 1. The date itself ───────────────────────────────────────────────────────
check('the live date is 2026-09-01', LIVE_RECORD_START === '2026-09-01', LIVE_RECORD_START);
check('the label and the short form describe the same day',
  LIVE_RECORD_START_LABEL === 'September 1, 2026' && LIVE_RECORD_START_SHORT === 'Sep 1, 2026',
  `${LIVE_RECORD_START_LABEL} / ${LIVE_RECORD_START_SHORT}`);
// A bare "09-01" in the month the window moved invites "since last September?".
check('the compact form carries its year', /20\d\d/.test(LIVE_RECORD_START_SHORT),
  LIVE_RECORD_START_SHORT);

// ── The two deliberately LONGER windows ──────────────────────────────────────
// A custom-model backtest reads the sweep matview, which keeps 2026-04-14 on
// purpose. Labelling that number with the live date overstates the sample by
// five months, so the longer window is a named constant rather than a literal.
check('the backtest window is named and is longer than the live window',
  BACKTEST_START === '2026-04-14' && BACKTEST_START < LIVE_RECORD_START);
check('the shadow track keeps its own window too',
  SHADOW_TRACK_START === '2026-04-14');

// ── 2. Nothing re-states the old date ────────────────────────────────────────
// The sweep windows are allowed to differ from the published window (a cut
// cannot be swept on a few days), so the two analysis surfaces are exempt by
// name rather than by pattern — an exemption has to be deliberate.
// The test is on VALUES, not prose: a comment explaining why the sweep window
// is longer is exactly what this change added, and forbidding it would push the
// reasoning out of the code. What must not recur is a date LITERAL standing in
// for one of the constants.
const DATE_LITERAL = /['"`]2026-(?:04-14|09-01)['"`]/;
const stale: string[] = [];
for (const f of FILES) {
  const rel = relative(SRC, f).replace(/\\/g, '/');
  if (rel === 'lib/recordStart.ts') continue; // the one place the dates are values
  if (DATE_LITERAL.test(readFileSync(f, 'utf-8'))) stale.push(rel);
}
check('no screen or constant hardcodes either window as a literal',
  stale.length === 0, stale.join(', '));

// ── The four things the UX review caught, each pinned ────────────────────────
const cache = readFileSync(join(SRC, 'lib/settledPickCache.ts'), 'utf-8');
check('the settled-pick cache key was bumped for the new window',
  /settledPicks\.v3/.test(cache),
  'a device upgrading from v2 kept ~3,200 pre-9/1 rows under "since Sep 1" headers');
check('the cache drops anything before the live date on merge',
  /game_date >= LIVE_RECORD_START/.test(cache),
  'so the next move of the date is self-healing rather than another key bump');

const q = readFileSync(join(SRC, 'lib/queries.ts'), 'utf-8');
check('the pick list behind a record is bounded to the published window',
  /v_model_full_outcome_picks[\s\S]{0,400}gte\('game_date', LIVE_RECORD_START\)/.test(q),
  'ungated it listed April-onward picks under a "since 09-01" record');

const models = readFileSync(join(SRC, 'screens/ModelsScreen.tsx'), 'utf-8');
check('custom-model copy names the BACKTEST window, not the live one',
  models.includes('BACKTEST_START_LABEL'),
  'the backtest RPC reads the sweep matview, which is five months longer');

// CLAUDE.md §2: the platform is LIVE. "paper" must not appear in user copy, and
// after the reset every model is under the 50-pick gate, so a sentence about
// staying "paper-only" until 50 reads as "all of this is paper".
const PAPER = /\bpaper[- ]?(only|trading)?\b/i;
const paperCopy = FILES.filter((f) => {
  const rel = relative(SRC, f).replace(/\\/g, '/');
  return /screens\/|components\//.test(rel) && PAPER.test(readFileSync(f, 'utf-8'));
});
check('no user-facing screen describes the platform as paper',
  paperCopy.length === 0, paperCopy.map((f) => relative(SRC, f)).join(', '));

check('a small-sample floor exists and is below the go-live gate',
  MIN_PICKS_FOR_COLOURED_ROI > 0 && MIN_PICKS_FOR_COLOURED_ROI < 50,
  String(MIN_PICKS_FOR_COLOURED_ROI));

// The PAPER check above greps for a WORD, and passed for days while four
// surfaces made the same claim as a NUMBER: "not backed for real money until
// 50+ settled picks" is §2's go-live gate quoted at members, which is the
// banned concept with the banned word removed (CLAUDE.md §7, "Banned copy").
// So ban the thing that computes it, in two halves.
//
// Half one — the rendered surfaces carry no gate copy. Scoped to screens/ and
// components/ for the same reason PAPER is: those are the files whose strings
// reach a member. A source comment that explains the rule is not a claim made
// to anyone, which is why lib/ is not swept for prose.
const GATE = /GO_LIVE_SETTLED_PICKS|\bnot backed\b|\bisn't backed\b|\d+\s*\+?\s*settled picks\b/i;
const gateCopy = FILES.filter((f) => {
  const rel = relative(SRC, f).replace(/\\/g, '/');
  return /screens\/|components\//.test(rel) && GATE.test(readFileSync(f, 'utf-8'));
});
check('no user-facing screen quotes the go-live gate at members',
  gateCopy.length === 0, gateCopy.map((f) => relative(SRC, f)).join(', '));

// Half two — and the constant is gone, so there is nothing to quote. This is
// the half that actually holds: a screen cannot interpolate a number the app
// does not define, whatever wording the next author reaches for.
const rs = readFileSync(join(SRC, 'lib/recordStart.ts'), 'utf-8');
check('the app defines no go-live-gate constant to render',
  !/export const GO_LIVE_SETTLED_PICKS/.test(rs),
  'the gate governs backing server-side (models/backtester.GO_LIVE_MIN_PICKS), not app copy');

// ── 3. The mirror: the Models tab reads Retool's view ────────────────────────
const queries = readFileSync(join(SRC, 'lib/queries.ts'), 'utf-8');
check('fetchPublishedModelRecord reads v_public_track_record',
  /fetchPublishedModelRecord[\s\S]{0,600}v_public_track_record/.test(queries));

const hook = readFileSync(join(SRC, 'hooks/useCustomModelStats.ts'), 'utf-8');
check('the record hook fetches the published record, not the re-graded view',
  hook.includes('fetchPublishedModelRecord') && !hook.includes('fetchModelFullOutcomeRecord'),
  'the two answer different questions and disagreed by 27pp on mlb_moneyline');
check('the hook takes its window from the single constant',
  hook.includes('LIVE_RECORD_START') && !/PAPER_START\s*=\s*['"]/.test(hook));

// The re-graded view must still EXIST as a fetch — it is the threshold-sweep
// tool (CLAUDE.md §7, THE EVALUATION RULE), and deleting it would leave no way
// to see dead-zone picks.
check('the full-outcome fetch is kept for threshold analysis',
  queries.includes('fetchModelFullOutcomeRecord') &&
  queries.includes('v_model_full_outcome_record'));

// ── 4. Unpriced picks still contribute no money ──────────────────────────────
// profit_flat fabricates -110 when dk_odds is NULL (CLAUDE.md §6), so the
// mapper has to derive stake from staked_flat and never from the pick count.
check('priced_bets comes from staked_flat, not from the pick count',
  /priced_bets:\s*staked\s*\/\s*100/.test(queries));
check('roi is null rather than 0 when nothing was priced',
  /roi_pct:\s*staked > 0 \?/.test(queries));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);

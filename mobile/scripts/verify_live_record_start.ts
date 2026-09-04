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
  LIVE_RECORD_START,
  LIVE_RECORD_START_LABEL,
  LIVE_RECORD_START_SHORT,
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
check('the label and the short form agree with it',
  LIVE_RECORD_START_LABEL === 'September 1, 2026' && LIVE_RECORD_START_SHORT === '09-01',
  `${LIVE_RECORD_START_LABEL} / ${LIVE_RECORD_START_SHORT}`);
check('the short form is the date\'s own month-day',
  LIVE_RECORD_START_SHORT === LIVE_RECORD_START.slice(5));

// ── 2. Nothing re-states the old date ────────────────────────────────────────
// The sweep windows are allowed to differ from the published window (a cut
// cannot be swept on a few days), so the two analysis surfaces are exempt by
// name rather than by pattern — an exemption has to be deliberate.
const SWEEP_SURFACES = ['screens/OpeningComparisonScreen.tsx', 'lib/thresholds.ts'];
const stale: string[] = [];
for (const f of FILES) {
  const rel = relative(SRC, f).replace(/\\/g, '/');
  if (SWEEP_SURFACES.includes(rel)) continue;
  if (rel === 'lib/recordStart.ts') continue; // documents the old date in prose
  const body = readFileSync(f, 'utf-8');
  if (body.includes('2026-04-14')) stale.push(rel);
}
check('no screen or constant still carries the old 2026-04-14 start',
  stale.length === 0, stale.join(', '));

// A literal of the NEW date is just as much a drift risk as the old one: it is
// the second copy that goes stale next time.
const hardcoded = FILES.filter((f) => {
  const rel = relative(SRC, f).replace(/\\/g, '/');
  if (rel === 'lib/recordStart.ts') return false;
  const body = readFileSync(f, 'utf-8');
  // A doc comment naming the date is fine; a string literal is not.
  return /['"`]2026-09-01['"`]/.test(body);
});
check('the new date is not re-hardcoded anywhere either',
  hardcoded.length === 0,
  hardcoded.map((f) => relative(SRC, f)).join(', '));

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

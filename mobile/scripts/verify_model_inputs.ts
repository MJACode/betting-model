/**
 * Standalone verification for the "What these models look at" copy on the
 * Models tab. Run with:
 *
 *   npx tsx scripts/verify_model_inputs.ts
 *
 * The card explains, per sport, which data elements the built-in models
 * consider. The copy is hand-written (a description, not a mirror of the
 * feature lists), so what can drift is coverage and register:
 *
 *   1. every sport in the toggle has an entry, and every built-in model the
 *      Models list can show belongs to a sport that has one;
 *   2. the copy never leaks a raw feature name or a model id — users see plain
 *      words and markets (UX_REVIEW §7);
 *   3. nothing describes the platform as paper trading (CLAUDE.md §2);
 *   4. every entry has groups, items and sources, and no chip is long enough
 *      to wrap into a paragraph on a phone;
 *   5. the closing line names DraftKings as the deciding line (CLAUDE.md §6).
 */

import { SPORTS } from '../src/hooks/useSportFilter';
import { MODEL_INPUTS_BY_SPORT, MODEL_INPUTS_DECIDES, modelInputsForSport } from '../src/lib/modelInputs';
import { MODEL_META, sportOfModel } from '../src/lib/modelMeta';
import { isModelPaused, isModelRetired } from '../src/lib/thresholds';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// ── 1. Coverage ──────────────────────────────────────────────────────────────
for (const sport of SPORTS) {
  const entry = MODEL_INPUTS_BY_SPORT[sport];
  check(`${sport} has a model-inputs entry`, entry != null);
  check(`${sport} lookup returns the same entry`, modelInputsForSport(sport) === entry);
}
check('no entry for a sport that is not in the toggle',
  Object.keys(MODEL_INPUTS_BY_SPORT).every((k) => (SPORTS as string[]).includes(k)),
  Object.keys(MODEL_INPUTS_BY_SPORT).filter((k) => !(SPORTS as string[]).includes(k)).join(','));

const listable = Object.keys(MODEL_META).filter((id) => !isModelPaused(id) && !isModelRetired(id));
check('every listable built-in model belongs to a sport with an entry',
  listable.every((id) => MODEL_INPUTS_BY_SPORT[sportOfModel(id)] != null),
  listable.filter((id) => MODEL_INPUTS_BY_SPORT[sportOfModel(id)] == null).join(','));

// ── 2–4. Register and shape ──────────────────────────────────────────────────
const RAW_FEATURE = /\b(?:d_|home_|away_|opp_|savant_|season_|mkt_|is_)[a-z0-9_]+\b/;
const MODEL_ID = new RegExp(`\\b(?:${Object.keys(MODEL_META).join('|')})\\b`);
const PAPER = /\b(paper|simulated|test mode)\b/i;
const CHIP_MAX = 64; // longer than this wraps into a paragraph inside a pill
const HEADLINE_MAX = 160;

function allText(sport: string): string[] {
  const e = MODEL_INPUTS_BY_SPORT[sport as keyof typeof MODEL_INPUTS_BY_SPORT];
  return [e.headline, ...e.groups.flatMap((g) => [g.label, ...g.items]), ...e.sources];
}

for (const sport of SPORTS) {
  const e = MODEL_INPUTS_BY_SPORT[sport];
  const text = allText(sport);
  check(`${sport}: at least two input groups`, e.groups.length >= 2, String(e.groups.length));
  check(`${sport}: every group has a label and at least one item`,
    e.groups.every((g) => g.label.trim().length > 0 && g.items.length > 0));
  check(`${sport}: names at least one source`, e.sources.length > 0);
  check(`${sport}: headline is one sentence, not a paragraph`,
    e.headline.length > 0 && e.headline.length <= HEADLINE_MAX, String(e.headline.length));
  check(`${sport}: no chip longer than ${CHIP_MAX} chars`,
    e.groups.every((g) => g.items.every((i) => i.length <= CHIP_MAX)),
    e.groups.flatMap((g) => g.items).filter((i) => i.length > CHIP_MAX).join(' | '));
  check(`${sport}: no raw feature name in the copy`,
    !text.some((t) => RAW_FEATURE.test(t)), text.filter((t) => RAW_FEATURE.test(t)).join(' | '));
  check(`${sport}: no model id in the copy`,
    !text.some((t) => MODEL_ID.test(t)), text.filter((t) => MODEL_ID.test(t)).join(' | '));
  check(`${sport}: nothing says paper trading`,
    !text.some((t) => PAPER.test(t)), text.filter((t) => PAPER.test(t)).join(' | '));
  check(`${sport}: no duplicate group labels`,
    new Set(e.groups.map((g) => g.label)).size === e.groups.length);
  check(`${sport}: no duplicate chips within a group`,
    e.groups.every((g) => new Set(g.items).size === g.items.length));
}

// Sports whose models price against a DraftKings market number say so in the
// Market group; sports whose rules are cross-book say which books.
check('NFL copy names Pinnacle (the opener and prop rules are Pinnacle-relative)',
  allText('NFL').some((t) => /Pinnacle/.test(t)));
check('NCAAF copy names Bovada (the opener rule is Bovada vs DraftKings)',
  allText('NCAAF').some((t) => /Bovada/.test(t)));
check('WNBA copy names Pinnacle (the market-relative prop rule)',
  allText('WNBA').some((t) => /Pinnacle/.test(t)));
check('MLB copy mentions the umpire (the strikeout prop input)',
  allText('MLB').some((t) => /umpire/i.test(t)));
check('GOLF copy mentions strokes gained',
  allText('GOLF').some((t) => /strokes gained/i.test(t)));

// ── 5. The closing line ──────────────────────────────────────────────────────
check('the closing line names DraftKings as the deciding line',
  /DraftKings/.test(MODEL_INPUTS_DECIDES) && /decided/.test(MODEL_INPUTS_DECIDES));
check('the closing line does not say paper trading', !PAPER.test(MODEL_INPUTS_DECIDES));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);

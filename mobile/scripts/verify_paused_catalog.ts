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

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  MODEL_META,
  BET_TYPE_GROUPS,
  betTypeGroups,
  sportHasLivePropModel,
  betSlotForModel,
  betTypeLabel,
  betTypePickerGroups,
  betTypeStatusSuffix,
  choiceAddedLabel,
  modelLong,
  modelProbabilityNote,
  withdrawnRulesEmpty,
} from '../src/lib/modelMeta';
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

// ── One explained name for the rules priced against Pinnacle ────────────────
// '(market-relative)' was explained nowhere in the app; Pinnacle is (designer
// review, 2026-10-16). Every rule that de-vigs Pinnacle and bets a soft book
// says so the same way.
for (const id of ['mlb_spread_market', 'mlb_total_market', 'nba_prop_market', 'nfl_prop_market', 'wnba_prop_market']) {
  check(`${id} is named "(vs Pinnacle)"`, modelLong(id).endsWith('(vs Pinnacle)'), modelLong(id));
}
check('no model is called "market-relative" any more',
  !Object.values(MODEL_META).some((m) => m.longLabel.includes('market-relative')));
// The NBA projection model prices its own projection, not Pinnacle's number,
// so its name must not borrow the rule's "(vs Pinnacle)".
check('the NBA projection model is "NBA Props (Projection)", not "(vs Pinnacle)"',
  modelLong('nba_prop_projection') === 'NBA Props (Projection)', modelLong('nba_prop_projection'));
check('the NBA projection model is a player prop with no single stat',
  MODEL_META.nba_prop_projection?.type === 'player_prop' && MODEL_META.nba_prop_projection.statLabel === '');
check('the NBA projection model\'s short name is a word, not its id',
  MODEL_META.nba_prop_projection?.shortLabel === 'Projection');
// The chip sits beside "BOS vs NYK Over 225.5": a bare "Over" repeats the side
// and names neither the market nor the model. Market plus method, as
// 'O/U Mkt' and 'O/U Fade' do.
check('the NBA totals overs model\'s chip names its market and method, not the side',
  MODEL_META.nba_total_luck?.shortLabel === 'O/U Luck', String(MODEL_META.nba_total_luck?.shortLabel));
// "Why this bet?": the projection model's probability is an upper bound. The
// figures are its graded seasons, not a posted record (it has none yet), and
// the 48% the prices implied is what shows the 50% beat them (UX review,
// 2026-10-16).
check('the projection model\'s probability note says upper bound, graded seasons, and the price',
  modelProbabilityNote('nba_prop_projection') ===
    'What our model says is the chance this side hits. Read it as an upper bound: graded on the last ' +
    'three NBA seasons, the bets it would have made averaged 53% here, won 50%, and were priced at 48%.',
  modelProbabilityNote('nba_prop_projection'));
check('every other model keeps the plain probability sentence',
  modelProbabilityNote('nba_prop_market') === 'What our model says is the chance this side hits.' &&
  modelProbabilityNote('mlb_moneyline') === 'What our model says is the chance this side hits.');
check('the "Why this bet?" card reads that note for the pick\'s own model',
  readFileSync(join(__dirname, '..', 'src/components/ReasoningCard.tsx'), 'utf-8')
    .includes('sub={modelProbabilityNote(pick.model_id)}'));

// ── The built-in model screen's title is the long name ──────────────────────
// Titled with the short label, the three prop-rule screens all read
// "Prop Mkt". The long names differ; the chip on the screen keeps the short one.
{
  const screen = readFileSync(join(__dirname, '..', 'src/screens/BuiltInModelDetailScreen.tsx'), 'utf-8');
  check('the built-in model screen is titled with the long label',
    /navigation\.setOptions\(\{ title: modelLong\(modelId\) \}\)/.test(screen));
  check('its chip keeps the short label', /<Text style=\{styles\.modelChipText\}>\{modelShort\(modelId\)\}<\/Text>/.test(screen));
  const titles = new Set(
    ['nba_prop_market', 'nba_prop_projection', 'nfl_prop_market', 'wnba_prop_market'].map(modelLong),
  );
  check('the four multi-market prop screens have four different titles', titles.size === 4, [...titles].join(' / '));
}

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

{
  const choiceLabels = betTypePickerGroups().flatMap((g) => g.choices.map((c) => c.label));
  const allowed = new Set(['ML', 'Run line', 'Spread', 'Puck line', 'Player props']);
  check('picker rows are the short bet types, never a model strategy name',
    choiceLabels.length > 0 && choiceLabels.every((label) => allowed.has(label) && !label.includes('(')));
  const ids = betTypePickerGroups().flatMap((g) => g.choices.flatMap((c) => c.modelIds));
  check('a picker choice never carries a paused or retired model',
    ids.every((id) => !isModelPaused(id) && !isModelRetired(id)));
  check('totals, First-5 and live markets are not a picker row',
    ids.every((id) => !id.includes('_f5_') && !id.includes('_live_') && !id.includes('over_under') && !id.includes('_total')));
  const row = (sport: string) =>
    betTypePickerGroups().find((g) => g.sport === sport)?.choices.map((c) => `${c.label}|${c.subtitle}`) ?? [];
  check('MLB is ML, Run line, Player props',
    row('MLB').join(',') === 'ML|Moneyline,Run line|±1.5,Player props|All player markets');
  const mlbLine = betTypePickerGroups().find((g) => g.sport === 'MLB')?.choices.find((c) => c.slot === 'line');
  check('MLB Run line maps to the active spread model, not the paused runline',
    mlbLine?.modelIds.includes('mlb_spread_market') === true && !mlbLine?.modelIds.includes('mlb_runline'));
  const mlbProps = betTypePickerGroups().find((g) => g.sport === 'MLB')?.choices.find((c) => c.slot === 'props');
  check('MLB Player props maps to live prop models and not a retired one',
    mlbProps?.modelIds.includes('mlb_prop_batter_runs') === true &&
      mlbProps?.modelIds.includes('mlb_prop_batter_walks') === true &&
      !mlbProps?.modelIds.includes('mlb_prop_batter_hr'));
  check('NFL has no moneyline model, so it does not invent an ML row',
    row('NFL').join(',') === 'Spread|Spread line,Player props|All player markets');
  // The NBA rebuild retired nba_moneyline and nba_spread (config
  // RETIRED_MODELS); the live NBA models are the nba_prop_market rule and the
  // nba_prop_projection model, both props, so the picker offers Player props
  // and nothing else for NBA.
  check('NBA is Player props only — its moneyline and spread are retired',
    row('NBA').join(',') === 'Player props|All player markets');
  const nbaProps = betTypePickerGroups().find((g) => g.sport === 'NBA')?.choices.find((c) => c.slot === 'props');
  check('NBA Player props writes the two live NBA prop models, not a retired per-stat model',
    nbaProps?.modelIds.join(',') === 'nba_prop_market,nba_prop_projection', nbaProps?.modelIds.join(','));
  check('the NBA totals overs are a game line the picker does not offer as a slot',
    MODEL_META.nba_total_luck?.type === 'game' && betSlotForModel('nba_total_luck', 'game') === null);
  check('the NBA projection model is titled in picker language',
    betTypeLabel('nba_prop_projection') === 'NBA · Player props', betTypeLabel('nba_prop_projection'));
  check('NCAAF is Spread only — its moneyline is paused and it has no prop model',
    row('NCAAF').join(',') === 'Spread|Spread line');
  const ncaafLine = betTypePickerGroups().find((g) => g.sport === 'NCAAF')?.choices.find((c) => c.slot === 'line');
  check('NCAAF Spread maps to ncaaf_spread only, not the premium band',
    ncaafLine?.modelIds.join(',') === 'ncaaf_spread');
  check('WNBA omits Spread while that model is paused',
    !row('WNBA').some((label) => label.startsWith('Spread')));
  check('NHL line is Puck line, not Spread',
    row('NHL').join(',') === 'ML|Moneyline,Puck line|±1.5,Player props|All player markets');
  check('UFC is moneyline only',
    row('UFC').join(',') === 'ML|Moneyline');
  check('golf is not a picker section',
    !betTypePickerGroups().some((g) => g.sport === 'GOLF'));
  check('a slot rule is titled in picker language, with no strategy parenthetical',
    betTypeLabel('mlb_spread_market') === 'MLB · Run line' &&
      betTypeLabel('nfl_opener_spread') === 'NFL · Spread' &&
      betTypeLabel('ncaaf_spread') === 'NCAAF · Spread' &&
      betTypeLabel('nhl_puckline') === 'NHL · Puck line' &&
      betTypeLabel('mlb_moneyline') === 'MLB · ML' &&
      betTypeLabel('nba_spread') === 'NBA · Spread' &&
      betTypeLabel('wnba_moneyline') === 'WNBA · ML' &&
      betTypeLabel('mlb_prop_batter_runs') === 'MLB · Player props' &&
      betTypeLabel('nfl_prop_market') === 'NFL · Player props' &&
      !betTypeLabel('mlb_spread_market').includes('(') &&
      !betTypeLabel('nfl_opener_spread').includes('('));
  check('a market the picker does not offer keeps its long name',
    betTypeLabel('mlb_f5_moneyline') === 'MLB · First 5 Moneyline' &&
      betTypeLabel('mlb_total_market') === 'MLB · Total Runs (vs Pinnacle)' &&
      betTypeLabel('ncaaf_spread_premium') === 'NCAAF · Spread (Opener, High Conviction)');
  check('a slot is Added only when every model is already a rule',
    choiceAddedLabel(0, 9) === null &&
      choiceAddedLabel(6, 9) === '6 of 9 added' &&
      choiceAddedLabel(9, 9) === 'Added');
}

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

// ── "Our picks on <player>": does any live prop model price this sport? ─────
// Read from the model catalog. The NBA and NFL live prop models are
// multi-market rules with no single stat, so the old stat-catalog test told an
// NBA or NFL player page that no prop model priced it.
check('a live prop model prices NBA players (nba_prop_market)', sportHasLivePropModel('NBA'));
check('a live prop model prices NFL players (nfl_prop_market)', sportHasLivePropModel('NFL'));
check('no prop model prices NCAAF players', !sportHasLivePropModel('NCAAF'));

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
{
  const mlb = betTypePickerGroups().find((g) => g.sport === 'MLB');
  check('a server pause drops the ML row and keeps the live prop row',
    !mlb?.choices.some((c) => c.slot === 'ml') &&
      mlb?.choices.some((c) => c.slot === 'props' && c.modelIds.includes('mlb_prop_batter_runs')) === true);
}
setServerThresholds(null);
check('clearing the server store restores the bundled pause set',
  !isModelPaused('mlb_moneyline') && isModelPaused('mlb_prop_batter_hits'));

// The NBA player page's "our picks" note asks whether ANY live prop model
// prices NBA players. With the rule paused on the server the projection model
// still does; with both paused, none does.
setServerThresholds({
  nba_prop_market: { min_prob: 0, min_edge: 0, min_odds: -200, prob_only: false, paused: true },
});
check('the projection model alone keeps NBA priced when the rule is paused',
  sportHasLivePropModel('NBA'));
setServerThresholds({
  nba_prop_market: { min_prob: 0, min_edge: 0, min_odds: -200, prob_only: false, paused: true },
  nba_prop_projection: { min_prob: 0, min_edge: 0, min_odds: -200, prob_only: false, paused: true },
});
check('with both NBA prop models paused, no live prop model prices NBA players',
  !sportHasLivePropModel('NBA'));
setServerThresholds(null);

check('a paused rule chip is labelled (paused), not (retired)',
  betTypeStatusSuffix('mlb_prop_batter_hits') === ' (paused)');
check('a live rule chip has no status suffix',
  betTypeStatusSuffix('mlb_moneyline') === '');
check('an all-paused custom model gets the paused empty, not the quiet-slate one',
  withdrawnRulesEmpty([{ model_id: 'mlb_over_under' }, { model_id: 'mlb_runline' }])
    === 'Every bet type in this model has been paused — it is not producing new picks.');
check('a mixed live+paused custom model is a quiet slate, not withdrawn',
  withdrawnRulesEmpty([{ model_id: 'mlb_moneyline' }, { model_id: 'mlb_over_under' }]) === null);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

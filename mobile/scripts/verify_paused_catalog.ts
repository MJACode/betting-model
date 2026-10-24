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
  modelHistoryMark,
  modelLongWithMark,
  modelDetailTitle,
  modelLong,
  modelProbabilityNote,
  sportOfModel,
  withdrawnRulesEmpty,
} from '../src/lib/modelMeta';
import {
  stackModelBadge,
  modelRecordBelow,
  navShowsSportOnly,
  STACKED_BLOCK,
  MODEL_BADGE_MIN,
  MODEL_BADGE_MAX,
  MODEL_RECORD_BELOW_SCALE,
  modelsListNameWidth,
} from '../src/lib/modelBadgeLayout';
import {
  PAUSED_MODELS,
  hasFetchedThresholds,
  isModelPaused,
  isModelRetired,
  markThresholdsFetched,
  passesActionFilter,
  setServerThresholds,
  subscribeThresholds,
  thresholdsRevisionNow,
  type ServerThreshold,
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

// ── Names are the sport plus the bet type, with no parenthetical ───────────
// Method words (Pinnacle, opener, wind, luck, the side) are not in the label.
const RENAMED: Record<string, [string, string]> = {
  mlb_spread_market: ['MLB Spreads', 'Spread'],
  mlb_total_market: ['MLB Totals', 'O/U'],
  nba_prop_market: ['NBA Props', 'Props'],
  nfl_prop_market: ['NFL Props', 'Props'],
  wnba_prop_market: ['WNBA Props', 'Props'],
};
for (const [id, [name, badge]] of Object.entries(RENAMED)) {
  check(`${id} is named ${name}`, modelLong(id) === name, modelLong(id));
  check(`${id} badge is ${badge}`, MODEL_META[id]?.shortLabel === badge, String(MODEL_META[id]?.shortLabel));
}
check('no model name carries a parenthetical',
  !Object.values(MODEL_META).some((m) => m.longLabel.includes('(') || m.longLabel.includes(')')));
check('no model is called "market-relative" any more',
  !Object.values(MODEL_META).some((m) => m.longLabel.includes('market-relative')));
// The projection model is its own title, not "NBA Props".
check('the NBA projection model is "NBA Projected Props"',
  modelLong('nba_prop_projection') === 'NBA Projected Props', modelLong('nba_prop_projection'));
check('the NBA projection model is a player prop with no single stat',
  MODEL_META.nba_prop_projection?.type === 'player_prop' && MODEL_META.nba_prop_projection.statLabel === '');
check('the NBA projection model\'s short name is a word, not its id',
  MODEL_META.nba_prop_projection?.shortLabel === 'Projected');
// The chip sits beside "BOS vs NYK Over 225.5": a bare "Over" repeats the side.
check('the NBA totals model\'s chip is the market, not the side',
  MODEL_META.nba_total_luck?.shortLabel === 'O/U' && modelLong('nba_total_luck') === 'NBA Totals',
  `${MODEL_META.nba_total_luck?.shortLabel} / ${modelLong('nba_total_luck')}`);
// Team total, not the game total. TT is the chip.
check('the NBA team-total model\'s chip is TT',
  MODEL_META.nba_team_total_luck?.shortLabel === 'TT', String(MODEL_META.nba_team_total_luck?.shortLabel));
check('the NBA team-total model is named NBA Team Totals',
  modelLong('nba_team_total_luck') === 'NBA Team Totals', modelLong('nba_team_total_luck'));
{
  const nflTotals = Object.entries(MODEL_META).filter(([, m]) => m.longLabel === 'NFL Totals');
  check('nfl_wind_totals is the only NFL Totals, and its badge is O/U',
    nflTotals.length === 1 && nflTotals[0][0] === 'nfl_wind_totals' && nflTotals[0][1].shortLabel === 'O/U',
    nflTotals.map(([id, m]) => `${id}=${m.shortLabel}`).join(', '));
}
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
// Titled with the short label, the prop-market screens all read "Props".
// The long names differ; the chip on the screen keeps the short one.
// At 1.5× the nav bar shows the sport. The on-screen title may break
// "Double-Double" after the hyphen and never ellipsizes.
{
  const screen = readFileSync(join(__dirname, '..', 'src/screens/BuiltInModelDetailScreen.tsx'), 'utf-8');
  check('below 1.5× the nav title is the long name, and at 1.5× it is the sport',
    screen.includes('navShowsSportOnly(fontScale) ? sportOfModel(modelId) : modelLong(modelId)') &&
      !navShowsSportOnly(1.3) &&
      navShowsSportOnly(1.5) &&
      navShowsSportOnly(2) &&
      sportOfModel('nba_team_total_luck') === 'NBA' &&
      sportOfModel('ncaaf_spread_premium') === 'NCAAF');
  check('the on-screen title breaks Double-Double after the hyphen and does not ellipsize',
    modelDetailTitle('nba_prop_player_dd') === 'NBA Double-\u200BDouble' &&
      modelDetailTitle('nba_moneyline') === 'NBA Moneyline' &&
      screen.includes('modelDetailTitle(modelId)') &&
      screen.includes('adjustsFontSizeToFit') &&
      screen.includes('minimumFontScale={0.85}') &&
      !/modelTitle[\s\S]{0,240}numberOfLines/.test(screen) &&
      !screen.includes('ellipsizeMode'));
  const badge = readFileSync(join(__dirname, '..', 'src/components/ModelBadgeRow.tsx'), 'utf-8');
  check('its chip keeps the short label', screen.includes('badge={modelShort(modelId)}'));
  check('the badge is one line and shrinks to fit',
    badge.includes('numberOfLines={1}') && badge.includes('adjustsFontSizeToFit'));
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
  const allowed = new Set(['ML', 'Spread', 'Player props']);
  check('picker rows are the short bet types, never a model strategy name',
    choiceLabels.length > 0 && choiceLabels.every((label) => allowed.has(label) && !label.includes('(')));
  const ids = betTypePickerGroups().flatMap((g) => g.choices.flatMap((c) => c.modelIds));
  check('a picker choice never carries a paused or retired model',
    ids.every((id) => !isModelPaused(id) && !isModelRetired(id)));
  check('totals, First-5 and live markets are not a picker row',
    ids.every((id) => !id.includes('_f5_') && !id.includes('_live_') && !id.includes('over_under') && !id.includes('_total')));
  const row = (sport: string) =>
    betTypePickerGroups().find((g) => g.sport === sport)?.choices.map((c) => `${c.label}|${c.subtitle}`) ?? [];
  check('MLB is ML, Spread, Player props',
    row('MLB').join(',') === 'ML|Moneyline,Spread|±1.5,Player props|All player markets');
  const mlbLine = betTypePickerGroups().find((g) => g.sport === 'MLB')?.choices.find((c) => c.slot === 'line');
  check('MLB Spread maps to the active spread model, not the paused runline',
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
  check('the NBA home team-total unders are a game line the picker does not offer as a slot',
    MODEL_META.nba_team_total_luck?.type === 'game' && betSlotForModel('nba_team_total_luck', 'game') === null);
  check('the NBA projection model is titled with its long name',
    betTypeLabel('nba_prop_projection') === 'NBA Projected Props', betTypeLabel('nba_prop_projection'));
  check('NCAAF is Spread only — its moneyline is paused and it has no prop model',
    row('NCAAF').join(',') === 'Spread|Spread line');
  const ncaafLine = betTypePickerGroups().find((g) => g.sport === 'NCAAF')?.choices.find((c) => c.slot === 'line');
  check('NCAAF Spread maps to ncaaf_spread only, not the premium band',
    ncaafLine?.modelIds.join(',') === 'ncaaf_spread');
  check('WNBA omits Spread while that model is paused',
    !row('WNBA').some((label) => label.startsWith('Spread')));
  check('NHL line is Spread, with the ±1.5 subtitle',
    row('NHL').join(',') === 'ML|Moneyline,Spread|±1.5,Player props|All player markets');
  check('UFC is moneyline only',
    row('UFC').join(',') === 'ML|Moneyline');
  check('golf is not a picker section',
    !betTypePickerGroups().some((g) => g.sport === 'GOLF'));
  check('every rule title is the long name, one shape, with no middle dot to split on',
    betTypeLabel('mlb_spread_market') === 'MLB Spreads' &&
      betTypeLabel('nfl_opener_spread') === 'NFL Spreads' &&
      betTypeLabel('ncaaf_spread') === 'NCAAF Spreads' &&
      betTypeLabel('nhl_puckline') === 'NHL Spreads' &&
      betTypeLabel('mlb_moneyline') === 'MLB Moneyline' &&
      betTypeLabel('nba_spread') === 'NBA Spreads' &&
      betTypeLabel('wnba_moneyline') === 'WNBA Moneyline' &&
      betTypeLabel('mlb_prop_batter_runs') === 'MLB Runs Scored' &&
      betTypeLabel('nfl_prop_market') === 'NFL Props' &&
      betTypeLabel('nba_prop_projection') === 'NBA Projected Props' &&
      betTypeLabel('mlb_f5_moneyline') === 'MLB First 5 Moneyline' &&
      betTypeLabel('mlb_total_market') === 'MLB Totals' &&
      betTypeLabel('ncaaf_spread_premium') === 'NCAAF Premium Spreads' &&
      betTypeLabel('nfl_wind_totals') === 'NFL Totals' &&
      !betTypeLabel('nfl_wind_totals').includes(' · ') &&
      !betTypeLabel('mlb_spread_market').includes('('));
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

// A cache from a build that did not store `paused` has the row and no flag.
// Until the live table lands, that must not unpause a bundle-paused model
// on Signals. After the fetch, a row with no flag is not paused. An explicit
// flag wins either way. A model with no row still uses the bundle.
const cachedWithoutFlag = {
  mlb_over_under: { min_prob: 0, min_edge: 0, min_odds: -200, prob_only: false } as ServerThreshold,
};
const signalPick = {
  model_id: 'mlb_over_under',
  model_probability: 0.6,
  edge: 0.2,
  dk_odds: -110,
  signal_type: 'BET' as const,
  condition_status: 'OK',
  discordPublish: 'published' as const,
};
setServerThresholds(cachedWithoutFlag);
check('a cached row with no paused flag stays bundle-paused before the live table',
  !hasFetchedThresholds() &&
    isModelPaused('mlb_over_under') === true &&
    PAUSED_MODELS.has('mlb_over_under') &&
    passesActionFilter(signalPick) === false);
check('a model with no server row still uses the bundled pause list',
  isModelPaused('mlb_runline') === true && PAUSED_MODELS.has('mlb_runline'));
check('the history mark still waits for the live table when the row omits paused',
  !hasFetchedThresholds() && modelHistoryMark('mlb_over_under') === 'Paused');
setServerThresholds({
  mlb_over_under: { min_prob: 0, min_edge: 0, min_odds: -200, prob_only: false, paused: false },
  mlb_moneyline: { min_prob: 0, min_edge: 0, min_odds: -200, prob_only: false, paused: true },
});
check('an explicit paused flag wins before the live table lands',
  !hasFetchedThresholds() &&
    isModelPaused('mlb_over_under') === false &&
    isModelPaused('mlb_moneyline') === true);
setServerThresholds(cachedWithoutFlag);
markThresholdsFetched();
check('once the live table has landed, a row with no paused flag is not paused',
  hasFetchedThresholds() &&
    isModelPaused('mlb_over_under') === false &&
    passesActionFilter(signalPick) === true);
setServerThresholds(null);

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

check('a paused model that shares MLB Totals is marked Paused, and the live one is not',
  modelHistoryMark('mlb_over_under') === 'Paused' && modelHistoryMark('mlb_total_market') === null);
check('a paused model that shares MLB Spreads is marked Paused, and the live one is not',
  modelHistoryMark('mlb_runline') === 'Paused' && modelHistoryMark('mlb_spread_market') === null);
check('a retired model that shares NBA Totals is marked Retired, and the live one is not',
  modelHistoryMark('nba_over_under') === 'Retired' && modelHistoryMark('nba_total_luck') === null);
check('a settled pick names the paused model, not the live one that shares the title',
  modelLongWithMark('mlb_over_under') === 'MLB Totals · Paused' &&
  modelLongWithMark('mlb_total_market') === 'MLB Totals' &&
  modelLongWithMark('mlb_runline') === 'MLB Spreads · Paused' &&
  modelLongWithMark('mlb_spread_market') === 'MLB Spreads' &&
  modelLongWithMark('nba_over_under') === 'NBA Totals · Retired' &&
  modelLongWithMark('nba_total_luck') === 'NBA Totals');
// A cached map can say the paused twin is live before the fetch corrects it.
// The footer must keep the bundled mark until that fetch is the store.
setServerThresholds({
  mlb_over_under: { min_prob: 0, min_edge: 0, min_odds: -200, prob_only: false, paused: false },
});
check('a cached unpause does not take the Paused mark off before the live table lands',
  !hasFetchedThresholds() &&
  isModelPaused('mlb_over_under') === false &&
  modelHistoryMark('mlb_over_under') === 'Paused' &&
  modelLongWithMark('mlb_over_under') === 'MLB Totals · Paused');
markThresholdsFetched();
check('once the live table has landed, the mark follows the server',
  hasFetchedThresholds() && modelHistoryMark('mlb_over_under') === null);
setServerThresholds(null);
check('clearing the store returns the mark to the bundled pause',
  !hasFetchedThresholds() && modelHistoryMark('mlb_over_under') === 'Paused');
{
  const models = readFileSync(join(__dirname, '..', 'src/screens/ModelsScreen.tsx'), 'utf-8');
  const detail = readFileSync(join(__dirname, '..', 'src/screens/ModelDetailScreen.tsx'), 'utf-8');
  const daily = readFileSync(join(__dirname, '..', 'src/components/DailyResultsModal.tsx'), 'utf-8');
  const badge = readFileSync(join(__dirname, '..', 'src/components/ModelBadgeRow.tsx'), 'utf-8');
  check('model rows use the shared badge, sized between 56 and 112',
    models.includes('<ModelBadgeRow ') &&
      detail.includes('<ModelBadgeRow ') &&
      daily.includes('<ModelBadgeRow ') &&
      badge.includes('minWidth: MODEL_BADGE_MIN') &&
      badge.includes('maxWidth: MODEL_BADGE_MAX') &&
      MODEL_BADGE_MIN === 56 &&
      MODEL_BADGE_MAX === 112 &&
      !models.includes('modelNameFloor') &&
      !detail.includes('modelNameFloor'));
  // 320 stacks at every text size. 393 stays side by side at 1× and stacks from 1.3×.
  const cases: Array<[number, number, boolean]> = [
    [1, 320, true],
    [1.3, 320, true],
    [2, 320, true],
    [1, 393, false],
    [1.3, 393, true],
    [2, 393, true],
  ];
  check('the badge stacks at 1.3× text or on a window under 360pt',
    cases.every(([scale, width, stacked]) => stackModelBadge(scale, width) === stacked));
  check('the record stays beside the name at 1× and moves under it at 2×',
    !modelRecordBelow(1, 320) &&
      !modelRecordBelow(1, 393) &&
      !modelRecordBelow(1.3, 393) &&
      modelRecordBelow(1.3, 320) &&
      modelRecordBelow(2, 320) &&
      modelRecordBelow(2, 393));
  // "TT" is a short badge (box 56). At 1× on 393 the name gets 171pt
  // (235 left − 8 gap − 56), which is the room "NBA Team Totals" needs.
  check('at 1× on 393 a short badge leaves the name 171pt',
    modelsListNameWidth(393, 1, 20) === 171);
  check('at 1× on 320 the stacked badge leaves the name the 162pt left column',
    modelsListNameWidth(320, 1, 20) === 162);
  check('at 2× on 320 the name gets the full 264pt card width',
    modelsListNameWidth(320, 2, 80) === 264);
  check('at 2× on 393 the name gets the full 337pt card width',
    modelsListNameWidth(393, 2, 80) === 337);
  check('a stacked block is grow 0, shrink 0, basis auto — not flex 0 or flex 1',
    STACKED_BLOCK.flexGrow === 0 &&
      STACKED_BLOCK.flexShrink === 0 &&
      STACKED_BLOCK.flexBasis === 'auto' &&
      !('flex' in STACKED_BLOCK));
  check('stacked containers do not also carry flex: 1',
    models.includes('builtInLeftStacked') &&
      models.includes('...STACKED_BLOCK') &&
      badge.includes('stacked ? styles.stacked : styles.row') &&
      badge.includes('stacked ? styles.bodyStacked : styles.body') &&
      badge.includes('...STACKED_BLOCK') &&
      daily.includes('modelLeftStacked') &&
      daily.includes('...STACKED_BLOCK') &&
      !/builtInLeftStacked:\s*\{[^}]*flex:\s*1/.test(models) &&
      !/stacked:\s*\{[^}]*flex:\s*1/.test(badge) &&
      !/bodyStacked:\s*\{[^}]*flex:\s*1/.test(badge) &&
      !/modelLeftStacked:\s*\{[^}]*flex:\s*1/.test(daily));
  const record = readFileSync(join(__dirname, '..', 'src/screens/TrackRecordScreen.tsx'), 'utf-8');
  check('Track Record moves the percent under the name from 1.5×, and the name block does not use flex: 1',
    record.includes('fontScale >= MODEL_RECORD_BELOW_SCALE') &&
      record.includes('modelLeftStacked') &&
      record.includes('...STACKED_BLOCK') &&
      record.includes('modelRoiStacked') &&
      !/modelLeftStacked:\s*\{[^}]*flex:\s*1/.test(record) &&
      MODEL_RECORD_BELOW_SCALE === 1.5);
}
check('pitcher outs keeps the role in the name',
  MODEL_META.mlb_prop_pitcher_outs.longLabel === 'MLB Pitcher Outs' &&
  MODEL_META.mlb_prop_pitcher_outs.shortLabel === 'P Outs' &&
  MODEL_META.mlb_prop_pitcher_outs.statLabel === 'Outs');
check('a paused rule chip is labelled (paused), not (retired)',
  betTypeStatusSuffix('mlb_prop_batter_hits') === ' (paused)');
check('a live rule chip has no status suffix',
  betTypeStatusSuffix('mlb_moneyline') === '');
check('an all-paused custom model gets the paused empty, not the quiet-slate one',
  withdrawnRulesEmpty([{ model_id: 'mlb_over_under' }, { model_id: 'mlb_runline' }])
    === 'Every bet type in this model has been paused — it is not producing new picks.');
check('a mixed live+paused custom model is a quiet slate, not withdrawn',
  withdrawnRulesEmpty([{ model_id: 'mlb_moneyline' }, { model_id: 'mlb_over_under' }]) === null);

{
  let notes = 0;
  const stop = subscribeThresholds(() => {
    notes += 1;
  });
  const before = thresholdsRevisionNow();
  setServerThresholds({
    mlb_moneyline: { min_prob: 0, min_edge: 0, min_odds: -200, prob_only: false, paused: true },
  });
  markThresholdsFetched();
  const afterFetch = thresholdsRevisionNow();
  markThresholdsFetched();
  check('replacing the store and the fetch flag each notify once',
    notes === 2 && afterFetch === before + 2 && thresholdsRevisionNow() === afterFetch);
  setServerThresholds(null);
  stop();
  const picks = readFileSync(join(__dirname, '..', 'src/screens/PicksHomeScreen.tsx'), 'utf-8');
  check('Signals re-runs the action filter when that notification lands',
    picks.includes('useThresholdsRevision()') &&
      picks.includes('[todayData, thresholdsRevision]'));
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

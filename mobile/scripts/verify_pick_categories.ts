/**
 * Standalone verification for the Picks filter's MARKET cut. Run with:
 *
 *   npx tsx scripts/verify_pick_categories.ts
 *
 * Two defects, both visible in one screenshot of the NFL board (Matt,
 * 2026-09-09: *"This filter that is on shows baseball and it's under nfl"*):
 *
 *  1. The filter offered all four market categories on every sport, so the NFL
 *     board carried MLB-only "Pitcher" and "Batter" chips and an active pill
 *     reading "Pitcher, Batter, Player" over a board of football props.
 *  2. Twelve NFL prop models had no MODEL_META entry while being live
 *     server-side, so their card chip rendered the RAW model id, and
 *     `applyFilter`'s `if (meta && ...)` let them survive every category cut —
 *     including "Game", which they are not.
 *
 * These run against the real modules rather than a grep, because the guard that
 * would have caught #2 is the one that reads MODEL_META and asks what happens
 * when the entry is MISSING (CLAUDE.md §7).
 */

import {
  activeFilterCount,
  applyFilter,
  categoriesAreNarrowed,
  categoryCountsFor,
  freshFilter,
  presentCategoriesFor,
  selectedCategories,
  type ModelCategory,
  type PicksFilterState,
} from '../src/lib/pickFilterState';
import { MODEL_META, modelCategory, modelShort, sportOfModel } from '../src/lib/modelMeta';
import { ACTION_THRESHOLDS, RETIRED_MODELS } from '../src/lib/thresholds';

let failures = 0;
function check(name: string, ok: boolean, detail = '') {
  if (ok) {
    console.log(`[PASS] ${name}`);
  } else {
    failures++;
    console.log(`[FAIL] ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

// ── the boards, as production actually holds them (picks since 2026-09-01) ──
const NFL_BOARD = [
  'nfl_wind_totals',
  'nfl_opener_spread',
  'nfl_prop_market',
  'nfl_prop_receptions',
  'nfl_prop_rec_yards',
  'nfl_prop_rush_yards',
  'nfl_prop_pass_yards',
  'nfl_prop_rush_rec_yards',
  'nfl_prop_pass_completions',
  'nfl_prop_anytime_td',
];
const MLB_BOARD = [
  'mlb_moneyline',
  'mlb_over_under',
  'mlb_prop_pitcher_k',
  'mlb_prop_batter_hits',
];
const NCAAF_BOARD = ['ncaaf_spread', 'ncaaf_spread_premium', 'ncaaf_over_under', 'ncaaf_moneyline'];
const UFC_BOARD = ['ufc_moneyline', 'ufc_total_rounds', 'ufc_method_of_victory'];

const labels = (cats: ModelCategory[]) => cats.join(',');

// ── 1. the reported bug: no baseball market is offered on a football board ──
check(
  'the NFL board offers Game and Player only',
  labels(presentCategoriesFor(NFL_BOARD)) === 'game,player_prop',
  labels(presentCategoriesFor(NFL_BOARD)),
);
check(
  'no NFL board category is an MLB-only market',
  !presentCategoriesFor(NFL_BOARD).some((c) => c === 'pitcher_prop' || c === 'batter_prop'),
);
check(
  'MLB still offers its pitcher and batter cuts',
  labels(presentCategoriesFor(MLB_BOARD)) === 'game,pitcher_prop,batter_prop',
  labels(presentCategoriesFor(MLB_BOARD)),
);
check(
  'an all-game board (NCAAF) offers only Game',
  labels(presentCategoriesFor(NCAAF_BOARD)) === 'game',
);
check('an all-game board (UFC) offers only Game', labels(presentCategoriesFor(UFC_BOARD)) === 'game');
// The first fix fell back to ALL_CATEGORIES here "so the bar doesn't read as
// broken" — which is the reported bug again (Pitcher and Batter on an NFL
// board), unreachable only because PicksHomeScreen gates the filter bar on a
// non-empty board. An empty board offers nothing.
check('an empty board offers no markets rather than four wrong ones', presentCategoriesFor([]).length === 0);
check(
  'and an empty board therefore never reads as filtered',
  !categoriesAreNarrowed(freshFilter(), presentCategoriesFor([])) &&
    activeFilterCount(freshFilter(), presentCategoriesFor([])) === 0,
);

// ── the facet counts that make an empty result attributable ──
const nflCounts = categoryCountsFor(NFL_BOARD);
check(
  'the NFL facet counts are picks, not models',
  nflCounts.game === 2 && nflCounts.player_prop === 8,
  JSON.stringify(nflCounts),
);
check(
  'a duplicated model id counts once per PICK',
  categoryCountsFor(['nfl_prop_rec_yards', 'nfl_prop_rec_yards', 'nfl_wind_totals'])
    .player_prop === 2,
);
check(
  'no MLB-only category is counted on an NFL board',
  nflCounts.pitcher_prop === 0 && nflCounts.batter_prop === 0,
);

// ── 2. the pill the screenshot showed: "Props" on NFL names Player, alone ──
const propsOnly: PicksFilterState = {
  ...freshFilter(),
  categories: new Set<ModelCategory>(['pitcher_prop', 'batter_prop', 'player_prop']),
};
check(
  'the Props pill on an NFL board reads "Player", not "Pitcher, Batter, Player"',
  labels(selectedCategories(propsOnly, presentCategoriesFor(NFL_BOARD))) === 'player_prop',
  labels(selectedCategories(propsOnly, presentCategoriesFor(NFL_BOARD))),
);
check(
  'the same state on an MLB board still names all three',
  labels(selectedCategories(propsOnly, presentCategoriesFor(MLB_BOARD))) ===
    'pitcher_prop,batter_prop',
  labels(selectedCategories(propsOnly, presentCategoriesFor(MLB_BOARD))),
);

// ── 3. a cut that cuts nothing is not an active filter ──
const playerOnly: PicksFilterState = {
  ...freshFilter(),
  categories: new Set<ModelCategory>(['player_prop']),
};
check(
  'selecting Player on an NFL board IS a narrowing cut',
  categoriesAreNarrowed(playerOnly, presentCategoriesFor(NFL_BOARD)) &&
    activeFilterCount(playerOnly, presentCategoriesFor(NFL_BOARD)) === 1,
);
check(
  'a board with one market present never reads as filtered',
  !categoriesAreNarrowed(freshFilter(), presentCategoriesFor(NCAAF_BOARD)) &&
    activeFilterCount(freshFilter(), presentCategoriesFor(NCAAF_BOARD)) === 0,
);

// ── 4. the escape hatch: a model with no metadata is cut like any other ──
const pick = (model_id: string) => ({
  pick: {
    model_id,
    signal_type: 'BET' as const,
    model_probability: 0.72,
    edge: 0.19,
    dk_odds: -115,
  },
});
const board = NFL_BOARD.map(pick);
const gameOnly: PicksFilterState = { ...freshFilter(), categories: new Set<ModelCategory>(['game']) };

check(
  'a Game-only cut on the NFL board keeps only the two game models',
  applyFilter(board, gameOnly).map((b) => b.pick.model_id).join(',') ===
    'nfl_wind_totals,nfl_opener_spread',
  applyFilter(board, gameOnly).map((b) => b.pick.model_id).join(','),
);
check(
  'a Player-only cut on the NFL board keeps every prop and no game line',
  applyFilter(board, playerOnly).length === NFL_BOARD.length - 2,
  String(applyFilter(board, playerOnly).length),
);
// The adversarial case that produced the bug: a model that is NOT in
// MODEL_META. `MODEL_META[id]?.type` is undefined for it, and the old
// `if (meta && ...)` guard therefore skipped the cut entirely.
check(
  'an unregistered prop model is categorised from its id, not waved through',
  !MODEL_META['nfl_prop_not_yet_registered'] &&
    modelCategory('nfl_prop_not_yet_registered') === 'player_prop' &&
    applyFilter([pick('nfl_prop_not_yet_registered')], gameOnly).length === 0,
);
check(
  'an unregistered MLB pitcher prop lands in the pitcher cut',
  modelCategory('mlb_prop_pitcher_not_registered') === 'pitcher_prop',
);
check(
  'an unregistered MLB batter prop lands in the batter cut',
  modelCategory('mlb_prop_batter_not_registered') === 'batter_prop',
);
check('an unregistered game model lands in the game cut', modelCategory('nhl_futures') === 'game');

// ── 5. every scorable model has display metadata, and the id agrees with it ──
const scorable = Object.keys(ACTION_THRESHOLDS).filter((id) => !RETIRED_MODELS.has(id));
const unlabelled = scorable.filter((id) => !MODEL_META[id]);
check(
  'every model the app can score carries a label (no raw model_id on a card)',
  unlabelled.length === 0,
  unlabelled.join(', '),
);
const rawIdOnCard = scorable.filter((id) => modelShort(id) === id);
check('no model renders its own id as its market chip', rawIdOnCard.length === 0, rawIdOnCard.join(', '));

// The id fallback is only safe while the naming convention holds. Walk every
// registered model and assert the derived category matches the declared one —
// so a future model that breaks the convention fails HERE rather than being
// silently misfiled by modelCategory the day someone forgets its entry.
const misderived = Object.entries(MODEL_META).filter(
  ([id, meta]) => deriveFromId(id) !== meta.type,
);
/** modelCategory's fallback branch, reachable here without a MODEL_META hit. */
function deriveFromId(modelId: string): ModelCategory {
  if (modelId.includes('_prop_pitcher_')) return 'pitcher_prop';
  if (modelId.includes('_prop_batter_')) return 'batter_prop';
  if (modelId.includes('_prop_') || modelId.endsWith('_prop')) return 'player_prop';
  return 'game';
}
check(
  'every registered model id derives its own declared category',
  misderived.length === 0,
  misderived.map(([id, m]) => `${id}: declared ${m.type}, id says ${deriveFromId(id)}`).join('; '),
);

// ── 6. the NFL props specifically — live server-side, so they must render ──
const NFL_PROPS = scorable.filter((id) => sportOfModel(id) === 'NFL' && id.includes('_prop_'));
check('all thirteen NFL prop models are registered', NFL_PROPS.length === 13, String(NFL_PROPS.length));
check(
  'every NFL prop model is a player prop',
  NFL_PROPS.every((id) => modelCategory(id) === 'player_prop'),
);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

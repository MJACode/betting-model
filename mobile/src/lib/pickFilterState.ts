/**
 * The pure state behind the Picks / Signals / Live filter bar — the shape, the
 * category maths and the predicate. `PickFilters` renders it; this file holds
 * everything about it that does not need React Native, so it can be executed
 * directly (`npx tsx scripts/verify_pick_categories.ts`) rather than only
 * grepped.
 *
 * THE RULE THIS FILE EXISTS FOR: **the Market cut is scoped to the sport on
 * screen.** `pitcher_prop` and `batter_prop` are MLB-only markets, but the
 * filter offered all four categories on every board — so the NFL tab shipped
 * "Pitcher" and "Batter" chips (Matt, 2026-09-09: *"This filter that is on
 * shows baseball and it's under nfl"*), the Props quick chip wrote all three
 * into the state, and the active pill read "Pitcher, Batter, Player" over a
 * board of football props. Two of those three words named markets that cannot
 * exist in NFL, and the same held in reverse for every sport: NCAAF and UFC
 * boards are 100% game models today, so Game/Props were dead controls there.
 *
 * So `presentCategoriesFor` derives the offered set from the picks actually on
 * screen, and every comparison below — the count, the pills, the quick-chip
 * states — is relative to THAT, not to the four-category universe.
 */

import { decisionEdge, decisionOdds } from '@/lib/decisionPrice';
import { expectedValue } from '@/lib/format';
import { modelCategory, type ModelCategory } from '@/lib/modelMeta';
import type { SignalType } from '@/types';

export type { ModelCategory };

export const ALL_CATEGORIES: ModelCategory[] = [
  'game',
  'pitcher_prop',
  'batter_prop',
  'player_prop',
];
export const PROP_CATEGORIES: ModelCategory[] = ['pitcher_prop', 'batter_prop', 'player_prop'];
export const ALL_SIGNALS: SignalType[] = ['BET', 'AVOID', 'NONE'];

export const CATEGORY_LABEL: Record<ModelCategory, string> = {
  game: 'Game',
  pitcher_prop: 'Pitcher',
  batter_prop: 'Batter',
  player_prop: 'Player',
};

export interface PicksFilterState {
  signals: Set<SignalType>;
  categories: Set<ModelCategory>;
  minProb: number | null;
  minEdge: number | null;
  minEV: number | null;
}

export const DEFAULT_FILTER: PicksFilterState = {
  signals: new Set<SignalType>(ALL_SIGNALS),
  categories: new Set<ModelCategory>(ALL_CATEGORIES),
  minProb: null,
  minEdge: null,
  minEV: null,
};

export function cloneFilter(state: PicksFilterState): PicksFilterState {
  return {
    signals: new Set(state.signals),
    categories: new Set(state.categories),
    minProb: state.minProb,
    minEdge: state.minEdge,
    minEV: state.minEV,
  };
}

export function freshFilter(): PicksFilterState {
  return cloneFilter(DEFAULT_FILTER);
}

/**
 * The market categories the picks on screen actually contain, in canonical
 * order — the only ones a filter may offer.
 *
 * An empty board offers NOTHING, deliberately. The first version fell back to
 * all four "so the bar doesn't read as broken", which re-created the reported
 * bug exactly (Pitcher and Batter on an NFL board) and was unreachable only by
 * accident — PicksHomeScreen happens to gate the whole filter bar on
 * `activeItems.length > 0`. A rule that depends on another component's accident
 * is not a rule (UX review, 2026-09-09).
 */
export function presentCategoriesFor(modelIds: Iterable<string>): ModelCategory[] {
  const present = new Set<ModelCategory>();
  for (const id of modelIds) present.add(modelCategory(id));
  return ALL_CATEGORIES.filter((c) => present.has(c));
}

/**
 * How many picks each market category holds — the count that goes on the facet
 * chip. Pass the model id of EVERY pick on the board, duplicates included.
 *
 * A facet that says how much is behind it explains an empty board before the
 * user commits to it, which is the one thing the Today→Signals switch could
 * not do: the two segments hold different markets, so a cut made on one can
 * empty the other with nothing on screen tying the result to the tap.
 */
export function categoryCountsFor(modelIds: Iterable<string>): Record<ModelCategory, number> {
  const counts: Record<ModelCategory, number> = {
    game: 0,
    pitcher_prop: 0,
    batter_prop: 0,
    player_prop: 0,
  };
  for (const id of modelIds) counts[modelCategory(id)] += 1;
  return counts;
}

/** The selected categories, restricted to the ones this board can show. */
export function selectedCategories(
  state: PicksFilterState,
  present: ModelCategory[],
): ModelCategory[] {
  return present.filter((c) => state.categories.has(c));
}

/**
 * Is the Market cut NARROWING this board? Selecting "Player" on an NFL board is
 * a real filter; selecting it on a board that only holds player props is not,
 * and must not light up the Filters badge or grow a pill (the state is shared
 * across the Today / Signals / Live segments, which hold different markets).
 */
export function categoriesAreNarrowed(
  state: PicksFilterState,
  present: ModelCategory[],
): boolean {
  return selectedCategories(state, present).length < present.length;
}

export function activeFilterCount(
  state: PicksFilterState,
  present: ModelCategory[] = ALL_CATEGORIES,
): number {
  let n = 0;
  if (state.signals.size < ALL_SIGNALS.length) n++;
  if (categoriesAreNarrowed(state, present)) n++;
  if (state.minProb != null) n++;
  if (state.minEdge != null) n++;
  if (state.minEV != null) n++;
  return n;
}

interface FilterablePick {
  signal_type: SignalType;
  model_id: string;
  model_probability: number;
  edge: number;
  dk_odds: number | null;
  // The price the pick was DECIDED at (2026-09-09); absent = DraftKings.
  decision_odds?: number | null;
  decision_edge?: number | null;
}

export function applyFilter<T extends { pick: FilterablePick }>(
  items: T[],
  state: PicksFilterState,
): T[] {
  return items.filter((it) => {
    const p = it.pick;
    if (!state.signals.has(p.signal_type)) return false;
    // modelCategory, NOT `MODEL_META[id]?.type` — a model with no metadata gets
    // its category from its id and is cut like any other. See modelCategory.
    if (!state.categories.has(modelCategory(p.model_id))) return false;
    if (state.minProb != null && p.model_probability < state.minProb) return false;
    // Edge and EV at the price the pick was decided at.
    if (state.minEdge != null && decisionEdge(p) < state.minEdge) return false;
    if (state.minEV != null) {
      const ev = expectedValue(p.model_probability, decisionOdds(p));
      // null EV (prob-only markets with no payout) is excluded when minEV is set.
      if (ev == null || ev < state.minEV) return false;
    }
    return true;
  });
}

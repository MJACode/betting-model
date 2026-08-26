/**
 * Picks / Signals / Movement filtering — one bar, one sheet.
 *
 * Previously this shipped as two components stacked on top of each other
 * (QuickFilters for search + category + sort, PicksFilterBar for the modal,
 * count and threshold pills). They edited the same state but looked and behaved
 * differently, and category was settable from both places. Now there is a single
 * `PickFilters` that owns the whole surface:
 *
 *   search + Filters(n)  →  quick chips (category + sort)  →  active pills
 *
 * The sheet applies live (see FilterSheet) rather than behind an Apply button.
 *
 * `PicksFilterState`, `DEFAULT_FILTER` and `applyFilter` are exported from here
 * — they're pure and the screens depend on them.
 *
 * There is deliberately NO per-model filter. It listed every model across every
 * sport in one flat list (four unlabeled "Moneyline" chips, and so on), and the
 * cut people actually want — regular betting lines vs player props — is what the
 * Market section and the Game/Props quick chips express.
 */

import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { expectedValue } from '@/lib/format';
import { MODEL_META } from '@/lib/modelMeta';
import { SORT_OPTIONS, type SortKey } from '@/lib/pickSort';
import { colors, font, spacing } from '@/lib/theme';
import { FilterBar, type ActivePill } from './FilterBar';
import { FilterChip, chipRowStyle } from './FilterChip';
import { FilterField } from './FilterField';
import { FilterSection, FilterSheet } from './FilterSheet';
import type { SignalType } from '@/types';

export type ModelCategory = 'game' | 'pitcher_prop' | 'batter_prop' | 'player_prop';

const ALL_CATEGORIES: ModelCategory[] = ['game', 'pitcher_prop', 'batter_prop', 'player_prop'];
const PROP_CATEGORIES: ModelCategory[] = ['pitcher_prop', 'batter_prop', 'player_prop'];

export interface PicksFilterState {
  signals: Set<SignalType>;
  categories: Set<ModelCategory>;
  minProb: number | null;
  minEdge: number | null;
  minEV: number | null;
}

export const DEFAULT_FILTER: PicksFilterState = {
  signals: new Set<SignalType>(['BET', 'AVOID', 'NONE']),
  categories: new Set<ModelCategory>(ALL_CATEGORIES),
  minProb: null,
  minEdge: null,
  minEV: null,
};

const ALL_SIGNALS: SignalType[] = ['BET', 'AVOID', 'NONE'];
const CATEGORY_LABEL: Record<ModelCategory, string> = {
  game: 'Game',
  pitcher_prop: 'Pitcher',
  batter_prop: 'Batter',
  player_prop: 'Player',
};

export function activeFilterCount(state: PicksFilterState): number {
  let n = 0;
  if (state.signals.size < ALL_SIGNALS.length) n++;
  if (state.categories.size < ALL_CATEGORIES.length) n++;
  if (state.minProb != null) n++;
  if (state.minEdge != null) n++;
  if (state.minEV != null) n++;
  return n;
}

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

interface Props {
  state: PicksFilterState;
  onChange: (next: PicksFilterState) => void;
  sortKey: SortKey;
  onSortChange: (key: SortKey) => void;
  search: string;
  onSearchChange: (v: string) => void;
  totalShown: number;
  totalAll: number;
  /**
   * Restricts the Market options to the model types actually on screen.
   * Used by the Signals/Movement views; undefined offers everything (Today).
   */
  availableModelIds?: string[];
  /** Hide the Signal section (Signals/Movement are all BET — the chips are noise). */
  showSignals?: boolean;
  /** Noun for counts and the sheet footer, e.g. "pick" / "signal". */
  itemNoun?: string;
}

export function PickFilters({
  state,
  onChange,
  sortKey,
  onSortChange,
  search,
  onSearchChange,
  totalShown,
  totalAll,
  availableModelIds,
  showSignals = true,
  itemNoun = 'pick',
}: Props) {
  const [open, setOpen] = useState(false);

  const presentCategories = useMemo(() => {
    if (!availableModelIds) return ALL_CATEGORIES;
    const present = new Set<ModelCategory>();
    for (const id of availableModelIds) {
      const meta = MODEL_META[id];
      if (meta) present.add(meta.type);
    }
    return ALL_CATEGORIES.filter((c) => present.has(c));
  }, [availableModelIds]);

  const patch = (fn: (draft: PicksFilterState) => void) => {
    const next = cloneFilter(state);
    fn(next);
    onChange(next);
  };

  const toggleSignal = (s: SignalType) =>
    patch((d) => {
      if (d.signals.has(s)) d.signals.delete(s);
      else d.signals.add(s);
    });

  const toggleCategory = (c: ModelCategory) =>
    patch((d) => {
      if (d.categories.has(c)) d.categories.delete(c);
      else d.categories.add(c);
    });

  const setThreshold = (key: 'minProb' | 'minEdge' | 'minEV', text: string) => {
    const n = parseFloat(text);
    patch((d) => {
      d[key] = Number.isFinite(n) ? n / 100 : null;
    });
  };

  // Quick chips: whole-category shortcuts for the two cuts people actually use.
  const gameOnly = state.categories.size === 1 && state.categories.has('game');
  const propsOnly =
    !state.categories.has('game') && PROP_CATEGORIES.every((c) => state.categories.has(c));

  const setCategories = (cats: ModelCategory[]) =>
    patch((d) => {
      d.categories = new Set(cats);
    });

  const pills = useMemo(
    () => buildPills(state, onChange, presentCategories),
    [state, onChange, presentCategories],
  );

  const count = activeFilterCount(state);

  return (
    <>
      <FilterBar
        search={search}
        onSearchChange={onSearchChange}
        searchPlaceholder="Search player or team"
        onOpenFilters={() => setOpen(true)}
        activeCount={count}
        pills={pills}
        onClearAll={count > 0 ? () => onChange(freshFilter()) : undefined}
        countLabel={totalShown === totalAll ? undefined : `${totalShown}/${totalAll}`}
      >
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={chipRowStyle}
          keyboardShouldPersistTaps="handled"
        >
          <FilterChip
            label="Game"
            active={gameOnly}
            onPress={() => setCategories(gameOnly ? ALL_CATEGORIES : ['game'])}
          />
          <FilterChip
            label="Props"
            active={propsOnly}
            onPress={() => setCategories(propsOnly ? ALL_CATEGORIES : PROP_CATEGORIES)}
          />
          <View style={styles.divider} />
          <Text style={styles.sortLabel}>SORT</Text>
          {SORT_OPTIONS.map((o) => (
            <FilterChip
              key={o.key}
              label={o.label}
              active={sortKey === o.key}
              onPress={() => onSortChange(o.key)}
            />
          ))}
        </ScrollView>
      </FilterBar>

      <FilterSheet
        visible={open}
        onClose={() => setOpen(false)}
        title={`Filter ${itemNoun}s`}
        resultCount={totalShown}
        itemNoun={itemNoun}
        onReset={() => onChange(freshFilter())}
        canReset={count > 0}
      >
        {showSignals ? (
          <FilterSection title="Signal" subtitle="BET, AVOID or no-signal picks.">
            <View style={styles.chipWrap}>
              {ALL_SIGNALS.map((s) => (
                <FilterChip
                  key={s}
                  label={s}
                  active={state.signals.has(s)}
                  onPress={() => toggleSignal(s)}
                />
              ))}
            </View>
          </FilterSection>
        ) : null}

        <FilterSection
          title="Market"
          subtitle="Game = the regular betting lines (moneyline, spread, total). The rest are player props."
        >
          <View style={styles.chipWrap}>
            {presentCategories.map((c) => (
              <FilterChip
                key={c}
                label={CATEGORY_LABEL[c]}
                active={state.categories.has(c)}
                onPress={() => toggleCategory(c)}
              />
            ))}
          </View>
        </FilterSection>

        <FilterSection title="Minimums" subtitle="Only show picks at or above these.">
          <View style={styles.fieldRow}>
            <FilterField
              label="Model probability"
              value={pctText(state.minProb)}
              onChange={(t) => setThreshold('minProb', t)}
              placeholder="65"
              suffix="%"
              decimal
            />
            <FilterField
              label="Edge"
              value={pctText(state.minEdge)}
              onChange={(t) => setThreshold('minEdge', t)}
              placeholder="10"
              suffix="%"
              decimal
            />
          </View>
          <View style={styles.fieldRow}>
            <FilterField
              label="Expected value"
              value={pctText(state.minEV)}
              onChange={(t) => setThreshold('minEV', t)}
              placeholder="2"
              suffix="%"
              decimal
            />
            <View style={styles.fieldSpacer} />
          </View>
        </FilterSection>
      </FilterSheet>
    </>
  );
}

function pctText(v: number | null): string {
  return v == null ? '' : String(Math.round(v * 100));
}

/** One removable pill per active filter — including the set-in-sheet ones the
 *  old bar left invisible (signal, category). */
function buildPills(
  state: PicksFilterState,
  onChange: (next: PicksFilterState) => void,
  presentCategories: ModelCategory[],
): ActivePill[] {
  const out: ActivePill[] = [];
  const patch = (fn: (d: PicksFilterState) => void) => {
    const next = cloneFilter(state);
    fn(next);
    onChange(next);
  };

  if (state.signals.size < ALL_SIGNALS.length) {
    out.push({
      key: 'signals',
      label: Array.from(state.signals).join(', ') || 'No signals',
      onRemove: () => patch((d) => (d.signals = new Set(ALL_SIGNALS))),
    });
  }
  if (state.categories.size < ALL_CATEGORIES.length) {
    const shown = presentCategories.filter((c) => state.categories.has(c));
    const list = (shown.length > 0 ? shown : Array.from(state.categories)) as ModelCategory[];
    out.push({
      key: 'categories',
      label: list.map((c) => CATEGORY_LABEL[c]).join(', ') || 'No markets',
      onRemove: () => patch((d) => (d.categories = new Set(ALL_CATEGORIES))),
    });
  }
  if (state.minProb != null) {
    out.push({
      key: 'minProb',
      label: `prob ≥ ${Math.round(state.minProb * 100)}%`,
      onRemove: () => patch((d) => (d.minProb = null)),
    });
  }
  if (state.minEdge != null) {
    out.push({
      key: 'minEdge',
      label: `edge ≥ ${Math.round(state.minEdge * 100)}%`,
      onRemove: () => patch((d) => (d.minEdge = null)),
    });
  }
  if (state.minEV != null) {
    out.push({
      key: 'minEV',
      label: `EV ≥ ${Math.round(state.minEV * 100)}%`,
      onRemove: () => patch((d) => (d.minEV = null)),
    });
  }
  return out;
}

interface FilterablePick {
  signal_type: SignalType;
  model_id: string;
  model_probability: number;
  edge: number;
  dk_odds: number | null;
}

export function applyFilter<T extends { pick: FilterablePick }>(
  items: T[],
  state: PicksFilterState,
): T[] {
  return items.filter((it) => {
    const p = it.pick;
    if (!state.signals.has(p.signal_type)) return false;
    const meta = MODEL_META[p.model_id];
    if (meta && !state.categories.has(meta.type)) return false;
    if (state.minProb != null && p.model_probability < state.minProb) return false;
    if (state.minEdge != null && p.edge < state.minEdge) return false;
    if (state.minEV != null) {
      const ev = expectedValue(p.model_probability, p.dk_odds);
      // null EV (prob-only markets with no payout) is excluded when minEV is set.
      if (ev == null || ev < state.minEV) return false;
    }
    return true;
  });
}

const styles = StyleSheet.create({
  chipWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  fieldRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  fieldSpacer: { flex: 1 },
  divider: {
    width: StyleSheet.hairlineWidth,
    alignSelf: 'stretch',
    marginVertical: 2,
    marginHorizontal: spacing.xs,
    backgroundColor: colors.separator,
  },
  sortLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.3,
  },
});

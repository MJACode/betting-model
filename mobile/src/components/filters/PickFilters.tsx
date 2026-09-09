/**
 * Picks / Signals filtering — one bar, one sheet.
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
 *
 * THE MARKET CUT IS SCOPED TO THE BOARD ON SCREEN (2026-09-09). `pitcher_prop`
 * and `batter_prop` are MLB-only markets and this offered all four categories
 * everywhere, so the NFL board shipped Pitcher and Batter chips and an active
 * pill reading "Pitcher, Batter, Player" over football props. The offered set
 * now comes from `presentCategoriesFor(availableModelIds)` — which is why that
 * prop is REQUIRED rather than "undefined offers everything", the exact
 * default that produced the bug. The pure half lives in lib/pickFilterState.
 */

import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SORT_OPTIONS, type SortKey } from '@/lib/pickSort';
import {
  ALL_CATEGORIES,
  ALL_SIGNALS,
  CATEGORY_LABEL,
  activeFilterCount,
  categoriesAreNarrowed,
  categoryCountsFor,
  cloneFilter,
  freshFilter,
  presentCategoriesFor,
  selectedCategories,
  type ModelCategory,
  type PicksFilterState,
} from '@/lib/pickFilterState';
import { colors, font, spacing } from '@/lib/theme';
import { FilterBar, type ActivePill } from './FilterBar';
import { FilterChip, chipRowStyle } from './FilterChip';
import { FilterField } from './FilterField';
import { FilterSection, FilterSheet } from './FilterSheet';
import { GameFilterSection } from './GameFilterSection';
import { gameFilterSummary, type SelectableGame } from '@/lib/gameFilter';
import type { SignalType } from '@/types';

// Re-exported so the screens keep one import site for the whole filter surface.
export {
  DEFAULT_FILTER,
  activeFilterCount,
  applyFilter,
  cloneFilter,
  freshFilter,
} from '@/lib/pickFilterState';
export type { ModelCategory, PicksFilterState } from '@/lib/pickFilterState';

const EMPTY_SELECTION: Set<string> = new Set();

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
   * The model id of EVERY pick on screen, duplicates included. REQUIRED: the
   * Market options and their counts are derived from it, so a board can never
   * offer a market it cannot contain. This was optional until 2026-09-09, and
   * the "undefined offers everything" default is what put MLB's Pitcher and
   * Batter chips on the NFL board.
   */
  availableModelIds: string[];
  /**
   * Tonight's games, and which of them the user has picked. The SELECTION is
   * shared with the Stats tab (useGameSelection) rather than living in
   * PicksFilterState: that object is a set of thresholds, cloned and reset as
   * one, and a game id is a fixture on a date — it belongs to the slate.
   */
  games?: SelectableGame[];
  selectedGames?: Set<string>;
  onToggleGame?: (gameId: string) => void;
  onClearGames?: () => void;
  /** Hide the Signal section (Signals are all BET — the chips are noise). */
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
  games = [],
  selectedGames = EMPTY_SELECTION,
  onToggleGame,
  onClearGames,
  showSignals = true,
  itemNoun = 'pick',
}: Props) {
  const [open, setOpen] = useState(false);

  const presentCategories = useMemo(
    () => presentCategoriesFor(availableModelIds),
    [availableModelIds],
  );
  const categoryCounts = useMemo(
    () => categoryCountsFor(availableModelIds),
    [availableModelIds],
  );
  const presentProps = useMemo(
    () => presentCategories.filter((c) => c !== 'game'),
    [presentCategories],
  );

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
  // Both are judged on what is PRESENT — "Props only" on an NFL board means the
  // one prop category it has, not all three (two of which are baseball).
  const shownCategories = selectedCategories(state, presentCategories);
  const gameOnly = shownCategories.length === 1 && shownCategories[0] === 'game';
  const propsOnly =
    presentProps.length > 0 &&
    !shownCategories.includes('game') &&
    shownCategories.length === presentProps.length;

  const setCategories = (cats: ModelCategory[]) =>
    patch((d) => {
      d.categories = new Set(cats);
    });

  // A cut with nothing to cut is a dead control: NCAAF and UFC boards are 100%
  // game models, so Game/Props and the Market section did nothing there. The
  // two surfaces answer that differently, on purpose (UX review, 2026-09-09):
  //
  //  - IN THE SHEET, the section is HIDDEN. A faceted filter that drops a facet
  //    with nothing behind it is the standard shape, and the sheet is a
  //    vertical list, so removing a section moves nothing the user is aiming at.
  //  - IN THE BAR, the chips stay and go DISABLED. That row is positional and
  //    shared with SORT: removing ~150pt of leading content slides every sort
  //    chip left under a thumb already on the row, so a tap meaning "Game"
  //    silently re-sorts the board. SportToggle one row above already mutes
  //    rather than removes, and FilterChip has carried a `disabled` prop for
  //    exactly this since it was written.
  //
  // Both stay live while the state IS narrowed, so the control that produced a
  // filter is always reachable to undo it (the state survives a Today→Signals
  // switch, and those two segments can hold different markets).
  const marketIsNarrowed = categoriesAreNarrowed(state, presentCategories);
  const marketCutBites = presentCategories.length > 1 || marketIsNarrowed;

  const pills = useMemo(
    () => buildPills(state, onChange, presentCategories),
    [state, onChange, presentCategories],
  );

  const count = activeFilterCount(state, presentCategories);

  // Collapsed-row summaries. "All" rather than an exhaustive list when nothing
  // is excluded — the row exists to say what is NARROWING the board.
  const marketSummary = useMemo(() => {
    const shown = selectedCategories(state, presentCategories);
    if (shown.length === presentCategories.length) return 'All';
    if (shown.length === 0) return 'None';
    return shown.map((c) => CATEGORY_LABEL[c]).join(', ');
  }, [state, presentCategories]);

  const minimumsSummary = useMemo(() => {
    const parts: string[] = [];
    if (state.minProb != null) parts.push(`Prob ${pctText(state.minProb)}%`);
    if (state.minEdge != null) parts.push(`Edge ${pctText(state.minEdge)}%`);
    if (state.minEV != null) parts.push(`EV ${pctText(state.minEV)}%`);
    return parts.length ? parts.join(' · ') : 'None';
  }, [state.minProb, state.minEdge, state.minEV]);

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
          {/* Always rendered, so the row's geometry never changes under a
              thumb — see marketCutBites. */}
          <FilterChip
            label="Game"
            active={gameOnly}
            disabled={!marketCutBites}
            onPress={() => setCategories(gameOnly ? ALL_CATEGORIES : ['game'])}
          />
          <FilterChip
            label="Props"
            active={propsOnly}
            disabled={!marketCutBites || presentProps.length === 0}
            // The PRESENT props, not all three: one tap used to write
            // pitcher_prop and batter_prop into the state on an NFL board —
            // invisible today because every read intersects with
            // presentCategories, but that is the bug masked rather than absent,
            // and the next surface to read the state raw re-ships it.
            onPress={() => setCategories(propsOnly ? ALL_CATEGORIES : presentProps)}
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
        onReset={() => {
          onChange(freshFilter());
          onClearGames?.();
        }}
        canReset={count > 0 || selectedGames.size > 0}
      >
        {/* GAMES first — the widest cut on the sheet, and the same control the
            Stats tab renders from the same selection (Matt, 2026-09-09). Only
            where there are fixtures to pick: a UFC card is fighters, and the
            section would be an empty box. */}
        {onToggleGame && games.length > 0 ? (
          <FilterSection
            title="Games"
            summary={gameFilterSummary(games, selectedGames)}
            defaultOpen={selectedGames.size > 0}
          >
            <GameFilterSection
              games={games}
              selected={selectedGames}
              onToggle={onToggleGame}
              onClear={() => onClearGames?.()}
              emptyNote="No games on this board."
            />
          </FilterSection>
        ) : null}

        {showSignals ? (
          <FilterSection
            title="Signal"
            subtitle="BET, AVOID or no-signal picks."
            summary={
              state.signals.size === ALL_SIGNALS.length
                ? 'All'
                : ALL_SIGNALS.filter((s) => state.signals.has(s)).join(', ') || 'None'
            }
          >
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

        {marketCutBites ? (
          <FilterSection
            title="Market"
            subtitle="Game = the regular betting lines (moneyline, spread, total). The rest are player props."
            summary={marketSummary}
          >
            <View style={styles.chipWrap}>
              {presentCategories.map((c) => (
                <FilterChip
                  key={c}
                  label={CATEGORY_LABEL[c]}
                  // The count is what makes an empty result attributable to the
                  // tap that caused it, rather than to a board that looks broken.
                  count={categoryCounts[c]}
                  active={state.categories.has(c)}
                  onPress={() => toggleCategory(c)}
                />
              ))}
            </View>
          </FilterSection>
        ) : null}

        <FilterSection
          title="Minimums"
          subtitle="Only show picks at or above these."
          summary={minimumsSummary}
        >
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
  // Only the categories THIS board can show are named. The pill read
  // "Pitcher, Batter, Player" on an NFL board of football props until
  // 2026-09-09, because it listed the state rather than the intersection.
  if (categoriesAreNarrowed(state, presentCategories)) {
    const shown = selectedCategories(state, presentCategories);
    out.push({
      key: 'categories',
      // "No markets on this board", not "No markets": this fires when the user
      // narrows on one segment and switches to another that holds different
      // markets, so the empty result is a state they never chose. The pill has
      // to say which half is wrong — the filter, not the board.
      label: shown.map((c) => CATEGORY_LABEL[c]).join(', ') || 'No markets on this board',
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

/**
 * Picks / Signals filtering — one bar, one sheet.
 *
 * Idle chrome is search + Filters only. Sort and the Game/Props (Market) cut
 * live in the sheet: the old quick-chip row (~150pt plus SORT) sat on every
 * board and undid the denser PickCard. Game/Props-always-visible in the bar
 * was for a positional SORT row that no longer exists; on UFC/NCAAF those
 * chips were disabled-but-visible dead controls. The sheet already hides
 * Market when it cannot cut (`marketCutBites`).
 *
 *   search + Filters(n)  →  active pills (when anything is narrowing)
 *
 * The sheet applies live (see FilterSheet) rather than behind an Apply button.
 *
 * `PicksFilterState`, `DEFAULT_FILTER` and `applyFilter` are exported from here
 * — they're pure and the screens depend on them.
 *
 * There is deliberately NO per-model filter. It listed every model across every
 * sport in one flat list (four unlabeled "Moneyline" chips, and so on), and the
 * cut people actually want — regular betting lines vs player props — is what
 * the Market section expresses.
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
import { StyleSheet, View } from 'react-native';
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
import { spacing } from '@/lib/theme';
import { FilterBar, type ActivePill } from './FilterBar';
import { FilterChip } from './FilterChip';
import { FilterField } from './FilterField';
import { FilterSection, FilterSheet } from './FilterSheet';
import { GameFilterSection } from './GameFilterSection';
import { gameFilterSummary, type SelectableGame } from '@/lib/gameFilter';
import { dateFilterSummary, datesAreNarrowed, type DateOption } from '@/lib/dateFilter';
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
const EMPTY_DATES: DateOption[] = [];

interface Props {
  state: PicksFilterState;
  onChange: (next: PicksFilterState) => void;
  sortKey: SortKey;
  onSortChange: (key: SortKey) => void;
  /**
   * False when fewer than 20% of on-screen rows have a public-ticket split
   * (`PUBLIC_SORT_MIN_SHARE`). Public is then hidden — ranking those boards
   * would fall through to Edge for most rows. Sharp stays offered on every
   * view (the score is computed for every pick; a 0 is a real 0).
   */
  publicSortAvailable: boolean;
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
  /**
   * The days the board's picks fall on, and which the user has picked (Matt,
   * 2026-09-26: "games could be on different days"). Empty selection = every
   * date. The section only renders when there is more than one day to choose.
   */
  dateOptions?: DateOption[];
  selectedDates?: Set<string>;
  onToggleDate?: (date: string) => void;
  onClearDates?: () => void;
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
  publicSortAvailable,
  search,
  onSearchChange,
  totalShown,
  totalAll,
  availableModelIds,
  games = [],
  selectedGames = EMPTY_SELECTION,
  onToggleGame,
  onClearGames,
  dateOptions = EMPTY_DATES,
  selectedDates = EMPTY_SELECTION,
  onToggleDate,
  onClearDates,
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

  // A cut with nothing to cut is a dead control: NCAAF and UFC boards are 100%
  // game models, so the Market section did nothing there. The sheet HIDES it —
  // a faceted filter that drops a facet with nothing behind it is the standard
  // shape, and the sheet is a vertical list, so removing a section moves
  // nothing the user is aiming at.
  //
  // It stays live while the state IS narrowed, so the control that produced a
  // filter is reachable to undo it when the destination board still holds that
  // market. An impossible Market (selected ∩ present is empty) is cleared by
  // the screen when leaving Today — the Signal section is hidden on
  // Signals/Live, and a hidden cut with no undo empties the board.
  const marketIsNarrowed = categoriesAreNarrowed(state, presentCategories);
  const marketCutBites = presentCategories.length > 1 || marketIsNarrowed;

  // THE GAME CUT IS IN THE BAR, NOT JUST THE SHEET. It lives outside
  // PicksFilterState (it is shared with the Stats tab), and leaving it out of
  // the pills and the count meant a user could filter to one game, close the
  // sheet, and see a shorter board with no badge, no removable pill and no
  // Clear all — the exact blindness the pill row was added to end. It also made
  // Reset look like it cleared something that had never been shown as set.
  const gamesNarrowed = selectedGames.size > 0;
  // The Date cut, in the bar for the same reason as Games: a narrowed board
  // with no badge and no pill reads as a board that lost its picks.
  const datesNarrowed = datesAreNarrowed(selectedDates, dateOptions);
  const dateSummary = dateFilterSummary(selectedDates, dateOptions);
  // One day on the board is nothing to cut — hide the section, as Market does.
  const dateCutBites = !!onToggleDate && (dateOptions.length > 1 || datesNarrowed);
  const searchActive = search.trim().length > 0;
  const pills = useMemo(() => {
    const out = buildPills(state, onChange, presentCategories);
    if (searchActive) {
      out.unshift({
        key: 'search',
        label: `"${search.trim()}"`,
        onRemove: () => onSearchChange(''),
      });
    }
    if (datesNarrowed && onClearDates) {
      out.push({ key: 'dates', label: dateSummary, onRemove: onClearDates });
    }
    if (gamesNarrowed && onClearGames) {
      out.push({
        key: 'games',
        label: gameFilterSummary(games, selectedGames),
        onRemove: onClearGames,
      });
    }
    return out;
  }, [
    state,
    onChange,
    presentCategories,
    searchActive,
    search,
    onSearchChange,
    datesNarrowed,
    dateSummary,
    onClearDates,
    gamesNarrowed,
    games,
    selectedGames,
    onClearGames,
  ]);

  const count =
    activeFilterCount(state, presentCategories) +
    (datesNarrowed ? 1 : 0) +
    (gamesNarrowed ? 1 : 0) +
    (searchActive ? 1 : 0);

  const clearAll = () => {
    onChange(freshFilter());
    onClearDates?.();
    onClearGames?.();
    onSearchChange('');
  };

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

  const sortSummary =
    SORT_OPTIONS.find((o) => o.key === sortKey)?.label ?? 'Edge';

  return (
    <>
      <FilterBar
        search={search}
        onSearchChange={onSearchChange}
        searchPlaceholder="Search player or team"
        onOpenFilters={() => setOpen(true)}
        activeCount={count}
        pills={pills}
        onClearAll={count > 0 ? clearAll : undefined}
        countLabel={totalShown === totalAll ? undefined : `${totalShown}/${totalAll}`}
      />

      <FilterSheet
        visible={open}
        onClose={() => setOpen(false)}
        title={`Filter ${itemNoun}s`}
        resultCount={totalShown}
        itemNoun={itemNoun}
        onReset={clearAll}
        canReset={count > 0}
      >
        <FilterSection
          title="Sort"
          subtitle="Order the board. Does not hide any picks."
          summary={sortSummary}
          defaultOpen
        >
          <View style={styles.chipWrap}>
            {SORT_OPTIONS.filter((o) => o.key !== 'public' || publicSortAvailable).map((o) => (
              <FilterChip
                key={o.key}
                label={o.label}
                active={sortKey === o.key}
                onPress={() => onSortChange(o.key)}
              />
            ))}
          </View>
        </FilterSection>

        {/* DATE before Games: it is the wider cut, and picking a day narrows
            the Games list below it to that day's fixtures (the screen passes
            the date-filtered slate). Multi-select, so "Today + Tomorrow" is
            one tap each; the count says how many picks are behind a day
            before the user commits to it. */}
        {dateCutBites ? (
          <FilterSection
            title="Date"
            subtitle="Games on this board fall on different days."
            summary={dateSummary}
            defaultOpen={datesNarrowed}
            onClear={datesNarrowed ? onClearDates : undefined}
          >
            <View style={styles.chipWrap}>
              {dateOptions.map((o) => (
                <FilterChip
                  key={o.date}
                  label={o.label}
                  count={o.count}
                  active={selectedDates.has(o.date)}
                  onPress={() => onToggleDate!(o.date)}
                  accessibilityLabel={`${o.label}, ${o.count} ${itemNoun}${o.count === 1 ? '' : 's'}`}
                />
              ))}
            </View>
          </FilterSection>
        ) : null}

        {/* GAMES after Date — the per-fixture cut, and the same
            control the Stats tab renders from the same selection (Matt,
            2026-09-09). Only where there are fixtures to pick: a UFC card is
            fighters, and the section would be an empty box. */}
        {onToggleGame && games.length > 0 ? (
          <FilterSection
            title="Games"
            summary={gameFilterSummary(games, selectedGames)}
            defaultOpen={selectedGames.size > 0}
            onClear={gamesNarrowed ? onClearGames : undefined}
          >
            <GameFilterSection
              games={games}
              selected={selectedGames}
              onToggle={onToggleGame}
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
          subtitle={
            showSignals
              ? 'Only show picks at or above these.'
              : 'Optional extra floor — this board already only shows picks that cleared the action line.'
          }
          summary={minimumsSummary}
        >
          <View style={styles.fieldRow}>
            <FilterField
              label="Model probability"
              value={pctText(state.minProb)}
              onChange={(t) => setThreshold('minProb', t)}
              placeholder="e.g. 65"
              suffix="%"
              decimal
            />
            <FilterField
              label="Edge"
              value={pctText(state.minEdge)}
              onChange={(t) => setThreshold('minEdge', t)}
              placeholder="e.g. 10"
              suffix="%"
              decimal
            />
          </View>
          <View style={styles.fieldRow}>
            <FilterField
              label="Expected value"
              value={pctText(state.minEV)}
              onChange={(t) => setThreshold('minEV', t)}
              placeholder="e.g. 2"
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
});

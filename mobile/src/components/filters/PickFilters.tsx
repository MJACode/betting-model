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
 * THE MODEL SECTION CAME BACK ON 2026-11-18 (Matt), on the terms its removal
 * named. The old one listed every model across every sport in one flat list
 * (four unlabeled "Moneyline" chips, and so on). This one lists only the
 * models with picks on the board on screen, never a paused model, each with
 * its published record and a hot / cold tag (ModelFilterSection,
 * lib/modelHeat).
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
  presentModelsFor,
  modelsAreNarrowed,
  selectedCategories,
  selectedModels,
  type ModelCategory,
  type PicksFilterState,
  type PresentModel,
} from '@/lib/pickFilterState';
import { spacing } from '@/lib/theme';
import { FilterBar, type ActivePill } from './FilterBar';
import { FilterChip } from './FilterChip';
import { FilterField } from './FilterField';
import { FilterSection, FilterSheet } from './FilterSheet';
import { GameFilterSection } from './GameFilterSection';
import { ModelFilterSection } from './ModelFilterSection';
import { modelShort } from '@/lib/modelMeta';
import type { ModelRecordSummary } from '@/lib/modelHeat';
import type { ModelRecordsStatus } from '@/hooks/useModelFilterRecords';
import { gameFilterSummary, type SelectableGame } from '@/lib/gameFilter';
import { dateFilterSummary, datesAreNarrowed, type DateOption } from '@/lib/dateFilter';
import {
  gameStateSummary,
  gameStatesAreNarrowed,
  isGameStateSelected,
  type GameState,
  type GameStateOption,
} from '@/lib/gameStateFilter';
import {
  TRACKED_CUT_LABEL,
  type TrackedCut,
  type TrackedCutOption,
} from '@/lib/trackedFilter';
import { signalDisplayName } from '@/lib/tone';
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
const EMPTY_STATES: GameStateOption[] = [];
const EMPTY_STATE_SELECTION: Set<GameState> = new Set();
const EMPTY_RECORDS: Record<string, ModelRecordSummary> = {};
const EMPTY_TRACKED: TrackedCutOption[] = [];

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
   * The model id of every pick the Model section may LIST, duplicates
   * included. The screen leaves out picks that draw as PAUSED (Matt,
   * 2026-11-18: paused models are not listed), and keeps a paused model's
   * posted or settled BET, which still draws as a bet (§1c) and must keep a
   * row, or ticking any model would hide it with nothing to bring it back.
   * Defaults to availableModelIds.
   */
  selectableModelIds?: string[];
  /** Each model's published record and hot / cold tag (useModelFilterRecords). */
  modelRecords?: Record<string, ModelRecordSummary>;
  modelRecordsStatus?: ModelRecordsStatus;
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
  /**
   * Not started / Live / Final, and which the user has picked (Matt,
   * 2026-11-14). Empty selection = every state but Final, which is opt-in
   * (2026-11-15). Renders when the board holds more than one state, or any
   * finished game.
   */
  gameStateOptions?: GameStateOption[];
  selectedGameStates?: Set<GameState>;
  onToggleGameState?: (state: GameState) => void;
  onClearGameStates?: () => void;
  /**
   * All / Not tracked / Tracked, read from the card's Track button (Matt,
   * 2026-11-21: show the bets not yet placed). 'all' = no cut. The section
   * only renders when something on the board is tracked, or the cut is set.
   */
  trackedOptions?: TrackedCutOption[];
  trackedCut?: TrackedCut;
  onTrackedCutChange?: (cut: TrackedCut) => void;
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
  selectableModelIds,
  modelRecords = EMPTY_RECORDS,
  modelRecordsStatus = 'loading',
  games = [],
  selectedGames = EMPTY_SELECTION,
  onToggleGame,
  onClearGames,
  dateOptions = EMPTY_DATES,
  selectedDates = EMPTY_SELECTION,
  onToggleDate,
  onClearDates,
  gameStateOptions = EMPTY_STATES,
  selectedGameStates = EMPTY_STATE_SELECTION,
  onToggleGameState,
  onClearGameStates,
  trackedOptions = EMPTY_TRACKED,
  trackedCut = 'all',
  onTrackedCutChange,
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

  const presentModels = useMemo(
    () => presentModelsFor(selectableModelIds ?? availableModelIds),
    [selectableModelIds, availableModelIds],
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

  const toggleModel = (id: string) =>
    patch((d) => {
      if (d.models.has(id)) d.models.delete(id);
      else d.models.add(id);
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
  // Model: the same rule. One model on the board is nothing to choose between.
  const modelIsNarrowed = modelsAreNarrowed(state, presentModels);
  const modelCutBites = presentModels.length > 1 || modelIsNarrowed;

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
  const dateChips = dateOptions.map((o) => (
    <FilterChip
      key={o.date}
      label={o.label}
      count={o.count}
      active={selectedDates.has(o.date)}
      onPress={() => onToggleDate!(o.date)}
      accessibilityLabel={`${o.spoken}, ${o.count} ${itemNoun}${o.count === 1 ? '' : 's'}`}
    />
  ));
  // The Status cut, same shape as Date: in the bar while it narrows, and
  // hidden when the board holds games in only one state.
  const statesNarrowed = gameStatesAreNarrowed(selectedGameStates, gameStateOptions);
  const stateSummary = gameStateSummary(selectedGameStates, gameStateOptions);
  // Final always earns the section: it is the only way today's finished games
  // reach the board, even when they are all the board holds.
  const stateCutBites =
    !!onToggleGameState &&
    (gameStateOptions.length > 1 || statesNarrowed || gameStateOptions.some((o) => o.state === 'final'));
  // The Tracked cut: in the bar while it narrows. Offered whenever the board
  // holds picks and the screen can apply it — "Not tracked" on a board with
  // nothing tracked yet is still a real answer (every pick), and hiding the
  // section until the first tap of Track made it undiscoverable.
  const trackedNarrowed = trackedCut !== 'all';
  const trackedCutBites = !!onTrackedCutChange && (trackedOptions.length > 0 || trackedNarrowed);
  const trackedSummary = TRACKED_CUT_LABEL[trackedCut];
  const searchActive = search.trim().length > 0;
  const pills = useMemo(() => {
    const out = buildPills(state, onChange, presentCategories, presentModels);
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
    if (statesNarrowed && onClearGameStates) {
      out.push({ key: 'gameStates', label: stateSummary, onRemove: onClearGameStates });
    }
    if (trackedNarrowed && onTrackedCutChange) {
      out.push({
        key: 'tracked',
        label: trackedSummary,
        onRemove: () => onTrackedCutChange('all'),
      });
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
    presentModels,
    searchActive,
    search,
    onSearchChange,
    datesNarrowed,
    dateSummary,
    onClearDates,
    statesNarrowed,
    stateSummary,
    onClearGameStates,
    trackedNarrowed,
    trackedSummary,
    onTrackedCutChange,
    gamesNarrowed,
    games,
    selectedGames,
    onClearGames,
  ]);

  const count =
    activeFilterCount(state, presentCategories, presentModels) +
    (datesNarrowed ? 1 : 0) +
    (statesNarrowed ? 1 : 0) +
    (trackedNarrowed ? 1 : 0) +
    (gamesNarrowed ? 1 : 0) +
    (searchActive ? 1 : 0);

  const clearAll = () => {
    onChange(freshFilter());
    onClearDates?.();
    onClearGameStates?.();
    onTrackedCutChange?.('all');
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

  const modelSummary = useMemo(() => {
    const shown = selectedModels(state, presentModels);
    if (shown.length === 0 || shown.length === presentModels.length) return 'All models';
    return modelPillLabel(shown);
  }, [state, presentModels]);

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
            subtitle="Kickoff date, ET. Pick one or more."
            summary={dateSummary}
            defaultOpen={datesNarrowed}
            onClear={datesNarrowed ? onClearDates : undefined}
          >
            <View style={styles.chipWrap}>{dateChips}</View>
          </FilterSection>
        ) : null}

        {/* STATUS between Date and Games: "Not started + Live" is the
            bettable board and the default; Final brings today's finished
            games back (Matt, 2026-11-15). The Games list below follows it. */}
        {stateCutBites ? (
          <FilterSection
            title="Status"
            subtitle="Finished games stay hidden until you pick Final."
            summary={stateSummary}
            defaultOpen={statesNarrowed}
            onClear={statesNarrowed ? onClearGameStates : undefined}
          >
            <View style={styles.chipWrap}>
              {gameStateOptions.map((o) => (
                <FilterChip
                  key={o.state}
                  label={o.label}
                  count={o.count}
                  active={isGameStateSelected(o.state, selectedGameStates)}
                  onPress={() => onToggleGameState!(o.state)}
                  accessibilityLabel={`${o.label}, ${o.count} ${itemNoun}${o.count === 1 ? '' : 's'}`}
                />
              ))}
            </View>
          </FilterSection>
        ) : null}

        {/* TRACKED after Status: both ask "can I still act on this?", and
            "Not tracked" is the list of signals not yet placed (Matt,
            2026-11-21). Reads the same isTracked the card's Track button
            draws, so a chip can never disagree with the card. */}
        {trackedCutBites ? (
          <FilterSection
            title="Tracked"
            subtitle={`Not tracked shows the ${itemNoun}s you haven’t placed yet.`}
            summary={trackedSummary}
            defaultOpen={trackedNarrowed}
            onClear={trackedNarrowed ? () => onTrackedCutChange!('all') : undefined}
          >
            <View style={styles.chipWrap}>
              {trackedOptions.map((o) => (
                <FilterChip
                  key={o.cut}
                  label={o.label}
                  count={o.count}
                  active={trackedCut === o.cut}
                  onPress={() => onTrackedCutChange!(o.cut)}
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
            subtitle="BET, AVOID or NEUTRAL picks."
            summary={
              state.signals.size === ALL_SIGNALS.length
                ? 'All'
                : ALL_SIGNALS.filter((s) => state.signals.has(s)).map(signalDisplayName).join(', ') || 'None'
            }
          >
            <View style={styles.chipWrap}>
              {ALL_SIGNALS.map((s) => (
                <FilterChip
                  key={s}
                  label={signalDisplayName(s)}
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

        {modelCutBites ? (
          <FilterSection
            title="Model"
            subtitle="Show only the models you choose. Leave empty for every model."
            summary={modelSummary}
            defaultOpen={modelIsNarrowed}
            onClear={
              state.models.size > 0 ? () => patch((d) => (d.models = new Set())) : undefined
            }
          >
            <ModelFilterSection
              models={presentModels}
              selected={state.models}
              records={modelRecords}
              status={modelRecordsStatus}
              onToggle={toggleModel}
              itemNoun={itemNoun}
            />
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

/** "ML", "ML, SOG", or "3 models" — the sheet's collapsed-row summary. */
function modelPillLabel(ids: string[]): string {
  if (ids.length <= 2) return ids.map(modelShort).join(', ');
  return `${ids.length} models`;
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
  presentModels: PresentModel[],
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
      label: Array.from(state.signals).map(signalDisplayName).join(', ') || 'No signals',
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
  // Named from the models on THIS board, like the Market pill.
  if (modelsAreNarrowed(state, presentModels)) {
    out.push({
      key: 'models',
      // "Model: ML", so a short label cannot be read as a Market pill.
      label: `Model: ${modelPillLabel(selectedModels(state, presentModels))}`,
      onRemove: () => patch((d) => (d.models = new Set())),
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

/**
 * Merged Picks tab — a single home for the daily board with a
 * `All | Signals | Live` segmented control. Replaces the old separate
 * Picks and Signals tabs (which both showed BET picks and read as redundant):
 *   - All      = every scored pick today (the old Picks tab; labelled
 *                "Today" until 2026-09-26, Matt).
 *   - Signals  = picks that crossed the bet line and are still live.
 *   - Live Signals = in-play picks. Always on screen; empty when nothing is
 *     live, which is itself the answer (see below).
 *
 * LIVE WAS A BOTTOM TAB UNTIL 2026-09-06 (Matt's call, after measurement). It
 * was the same PickCard, over the same sport filter, in a header that was a
 * lossy copy of this one — the third state of one object, given a sixth of the
 * tab bar. Measured over the 30 days to 2026-09-06: 175 live BETs on 25 of 31
 * days, ~5.3h of board occupancy per active day — the board was empty ~81% of
 * the clock, and for NBA, NHL, NFL, UFC and GOLF it was empty 100% of it. A tab
 * that is empty on your first three visits teaches you not to go there.
 *
 * THE SEGMENT WAS CONDITIONAL FROM 2026-09-06 UNTIL 2026-09-12, when matt asked
 * for the opposite and for the name: "I want it to always show for each sport
 * but only populates with live signal bets", called Live Signals. So it is now
 * unconditional on every sport, and the measurement above stands as the known
 * cost — most of the time it reads (0).
 *
 * What carries the information instead is the COUNT and the dot: `(0)` with no
 * dot is the "nothing in play" answer, given in the same place every time
 * somebody looks for it. That is the one thing the conditional version could not
 * do — a board that exists only when it has something cannot be found when it
 * has nothing, so "is anything live?" had nowhere to be asked and its absence
 * read as a missing feature rather than an empty one (matt, 2026-09-12).
 *
 * Which sport is live is still carried by the red dot on the sport chips
 * (SportToggle `liveSports`). A sport with no in-play model AT ALL says so in
 * its own empty state (lib/liveSports.ts): "no edge right now" is a false
 * promise on NBA, which has no live lane that could find one.
 *
 * Picks lock the first time a model scores them each day (game markets at the
 * first run, props at their first signal) and never change again for the rest
 * of the day, so there's no "dropped to AVOID" state to track. How the DK line
 * has moved since a pick locked lives on the pick's detail screen.
 *
 * Reuses the shared filter/sort/search pipeline (PickFilters +
 * applyFilter/sortPicks/searchPicks) and the same PickCard list — so the only
 * per-view difference is the data source.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  FlatList,
  type LayoutChangeEvent,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { PickCard } from '@/components/PickCard';
import { EmptyState } from '@/components/EmptyState';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import {
  knownCount,
  loadPresentation,
  showLivePricesBanner,
  sportChipsAvailable,
  todayHeaderCounts,
} from '@/lib/loadState';
import { Skeleton, SkeletonBlock } from '@/components/Skeleton';
import { InfoTooltip } from '@/components/InfoTooltip';
import { SectionTitle } from '@/components/SectionTitle';
import {
  applyFilter,
  cloneFilter,
  freshFilter,
  PickFilters,
  type PicksFilterState,
} from '@/components/filters/PickFilters';
import { SportToggle } from '@/components/SportToggle';
import { SettingsButton } from '@/components/SettingsButton';
import { BetslipButton } from '@/components/BetslipButton';
import { LiveDot } from '@/components/LiveDot';
import { SignalLockCard } from '@/components/SignalLockCard';
import { showToast } from '@/components/Toast';
import { useEntitlement } from '@/hooks/useEntitlement';
import { useGameSelection } from '@/hooks/useGameSelection';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useLivePicks, LIVE_POLL_MS, LIVE_IDLE_POLL_MS } from '@/hooks/useLivePicks';
import { useLiveGameStates } from '@/hooks/useLiveGameStates';
import { useTrackedBets } from '@/hooks/useTrackedBets';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { signalCountsBySport } from '@/lib/lineMovementBoard';
import { gameFilterSummary, isGameSelected, selectableGames } from '@/lib/gameFilter';
import {
  dateOptionsFor,
  effectiveDateSelection,
  isDateSelected,
  rowsByDay,
  type DayRow,
} from '@/lib/dateFilter';
import { slipKeyForPick } from '@/lib/parlay';
import {
  ALL_SIGNALS,
  presentCategoriesFor,
  resetImpossibleMarket,
} from '@/lib/pickFilterState';
import { publicSortAvailable, searchPicks, sortPicks, type SortKey } from '@/lib/pickSort';
import { priceCheckForItem } from '@/lib/pickPriceCheck';
import { colors, font, radii, spacing } from '@/lib/theme';
import {
  isModelPaused,
  isPausedForDisplay,
  isModelRetired,
  isUnlockedPreview,
  passesActionFilter,
  unitsFor,
  formatUnits,
} from '@/lib/thresholds';
import { formatCurrency, formatPct, gameStatus, todayET } from '@/lib/format';
import { reachFrame, unitsSpeech, unknownCountSpeech } from '@/lib/a11y';

/**
 * H9 geometry of the sub-tab row. Above: the 12pt between the sport chips and
 * these is split 6/6 (SportToggle reachBelow={4} takes 2 + 4; this row keeps
 * its wrap's 2pt padding + the 4pt of margin the toggle doesn't cover). Below:
 * 6pt of the header's 12pt bottom padding plus the wrap's 2pt. ~32pt segments
 * reach 6 + 32 + 8 = 46pt.
 */
const SUBTAB_REACH_ABOVE = 6;
const SUBTAB_REACH_BELOW = 6;
const subTabsReach = reachFrame(0, SUBTAB_REACH_BELOW);
import type { EnrichedPick, PicksView, RootStackParamList, TabParamList } from '@/types';
import { decisionOdds } from '@/lib/decisionPrice';
import { hasLiveModel, liveModelSportsSentence } from '@/lib/liveSports';
import { friendlyCause } from '@/lib/errors';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';

type Nav = NativeStackNavigationProp<RootStackParamList>;
export type { PicksView };

// Designer (#845): on the one screen where a failed load could read as lost
// picks, say plainly that they are not. Other screens pass no reassurance.
const PICKS_REASSURANCE = 'Nothing is wrong with your picks.';

export function PicksHomeScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<RouteProp<TabParamList, 'Picks'>>();
  const { data: allData, pausedData, loading, loaded, error, partial, refresh, date } = useTodayPicks();
  const { sport } = useSportFilter();
  const tracked = useTrackedBets();
  const slip = useParlaySlip();

  const [view, setView] = useState<PicksView>('today');
  const [filter, setFilter] = useState<PicksFilterState>(freshFilter);
  const [sortKey, setSortKey] = useState<SortKey>('edge');
  const [search, setSearch] = useState('');

  // In-play picks, across every sport (the sport cut happens below, so the
  // toggle can mark the sports that are live). Polled fast only while the user
  // is on the live segment — see useLivePicks.
  const {
    data: allLiveData,
    loading: liveLoading,
    loaded: liveLoaded,
    error: liveError,
    pricesUnavailable: livePricesUnavailable,
    refresh: refreshLive,
    dates: liveDates,
  } = useLivePicks({ pollMs: view === 'live' ? LIVE_POLL_MS : LIVE_IDLE_POLL_MS });

  // In-play score + inning for games that have started (polls every 30s).
  // Over the SAME window the live picks were read across, not just today, so a
  // game that kicked off late keeps its score and clock after midnight ET
  // instead of freezing at the rollover (liveSlateDatesET).
  const { byGame: liveStates } = useLiveGameStates(liveDates);

  // The All board is every scored pick, INCLUDING a paused model's (Matt,
  // 2026-09-26), each card labelled PAUSED. Signals is derived from this list
  // through passesActionFilter, which refuses a paused model, so a paused row
  // never becomes a signal, a stake, or a count in a sport badge.
  const todayData = useMemo(
    () => [...allData, ...pausedData].filter((d) => d.pick.sport === sport),
    [allData, pausedData, sport],
  );
  // fetchLivePicks decides "in progress" as `commence_time <= now AND
  // home_score IS NULL`, and games.home_score stays NULL until next-morning
  // settlement — so on that test alone a finished game stays "live" until ~6am.
  // That was a stale tab nobody looked at; now the segment's very presence is
  // the live indicator, so it has to clear. gameStatus() reads the live-state
  // snapshot and returns 'ended'/'final' correctly, so filter on it.
  //
  // The state poller is MLB-only, so other sports fall through to gameStatus's
  // blind-window branch rather than a real clock. Better than "until tomorrow
  // morning", and not the durable fix — that is server-side (see the PR).
  //
  // A PAUSED or RETIRED model's live BET is not stakeable. The Live board is
  // the one board that never ran rows through the action filter, so a live
  // BET locked before its lane was paused (the row is never rewritten, §1c)
  // kept drawing a green BET badge and a stake here while Discord and push
  // had already stopped on `model_action_thresholds.paused`. The surfaces
  // show the same picks (CLAUDE.md §1b); this is the Live board's half.
  // Deliberately NOT the full passesActionFilter: nfl_live_prop's cut is EV
  // server-side, and its bundled row would hide BETs the lane legitimately
  // wrote.
  const liveInProgress = useMemo(
    () =>
      allLiveData.filter(
        (d) =>
          !isModelPaused(d.pick.model_id) &&
          !isModelRetired(d.pick.model_id) &&
          gameStatus(d.game, liveStates.get(d.pick.game_id) ?? null).kind === 'live',
      ),
    [allLiveData, liveStates],
  );
  const liveData = useMemo(
    () => liveInProgress.filter((d) => d.pick.sport === sport),
    [liveInProgress, sport],
  );
  // Sports with an in-play pick standing right now — the red dot on the chips.
  const liveSports = useMemo(
    () => new Set(liveInProgress.map((d) => d.pick.sport)),
    [liveInProgress],
  );
  // Sports with anything on today's board — the rest are muted in the toggle so
  // the eye lands on the ones that actually have picks.
  const sportsWithPicks = useMemo(
    () => new Set([...allData, ...pausedData].map((d) => d.pick.sport)),
    [allData, pausedData],
  );
  // A sport whose ONLY rows today are in-play picks must not read as "nothing
  // here": fetchPicksForDate excludes is_live rows, so without this union the
  // chip renders muted AND live-dotted, two marks saying opposite things.
  const availableSports = useMemo(
    () => new Set([...sportsWithPicks, ...liveSports]),
    [sportsWithPicks, liveSports],
  );

  // Live picks standing on the board at the previous settled fetch, for the
  // transition toast below. Declared here because the sport-change reset clears
  // it, and that effect runs first.
  const prevLiveCount = useRef<number | null>(null);

  // MLB and WNBA share no model_ids — a stale filter would show "0 of N" after a
  // sport switch. Reset filter/search on sport change.
  //
  // THE VIEW IS NOT RESET, and that is the whole of what a sport switch does to
  // it. It had to be while the live segment was conditional — a sport with
  // nothing in play had no segment to stand on, so someone glancing at another
  // sport was put back on Today. Live Signals is on screen for every sport now
  // (matt, 2026-09-12), so the board a reader chose survives the switch:
  // changing sport is how you check another game, not a request to change board.
  useEffect(() => {
    setFilter(freshFilter());
    setSearch('');
    // And the live board's previous count is FORGOTTEN, because `liveData` is
    // sport-scoped: without this, a reader on 3 MLB live picks who taps NBA goes
    // 3 -> 0 and gets told "Last in-play game finished". Nothing finished; they
    // changed sport. With the board empty ~81% of the clock and 100% of it on the
    // sports with no live lane, that false report was the USUAL outcome of a sport
    // tap from the live board (UX review, 2026-09-12).
    prevLiveCount.current = null;
  }, [sport]);

  // Where each segment sits in the scroller, measured rather than assumed: the
  // labels scale with Dynamic Type, so no constant survives a text-size change.
  const segmentsRef = useRef<ScrollView | null>(null);
  const segmentX = useRef<Partial<Record<PicksView, number>>>({});
  const onSegmentLayout = (v: PicksView) => (e: LayoutChangeEvent) => {
    segmentX.current[v] = e.nativeEvent.layout.x;
  };
  useEffect(() => {
    const x = segmentX.current[view];
    if (x == null) return;
    segmentsRef.current?.scrollTo({ x: Math.max(0, x - spacing.md), animated: true });
  }, [view]);

  const requestedView = route.params?.view;

  // The live board emptying out under a reader (the last game ended) still gets
  // a word — the list swaps for an empty state while they are looking at it, and
  // a screen that rearranges itself in silence reads as a glitch. What changed
  // on 2026-09-12 is that NOBODY IS MOVED: the segment no longer vanishes, so
  // the honest thing is to say the games finished and leave them where they are.
  //
  // Fires on the something-to-zero TRANSITION only, never on a board that was
  // already empty when they arrived — the empty state says that perfectly well,
  // and a toast for it would fire on arrival from the Settings row. Hence the
  // ref: `liveLoading` flips on every 30s poll, so a check on the count alone
  // re-ran this effect and toasted every half minute.
  useEffect(() => {
    if (liveLoading) return;
    const prev = prevLiveCount.current;
    prevLiveCount.current = liveData.length;
    if (view === 'live' && liveData.length === 0 && prev !== null && prev > 0) {
      showToast('Last in-play game finished — no live signals right now');
    }
  }, [view, liveLoading, liveData.length]);

  // Deep link into a segment (Settings' "Live betting" row, and the live push
  // handler when it is built). This CANNOT be a useState initializer: Picks is
  // the initial tab, mounts at launch and is never unmounted, so by the time
  // anyone taps that row the initial state is long fixed and the tap would
  // switch tabs and land on whatever segment was already showing. The param is
  // cleared after use so a second tap works and a back-navigation does not
  // re-trigger it.
  useEffect(() => {
    if (!requestedView) return;
    setView(requestedView);
    navigation.setParams({ view: undefined } as never);
  }, [requestedView, navigation]);
  // Signals per sport, across ALL sports (not just the selected one) — the
  // toggle badge. The boards show one sport at a time, so without this a user
  // parked on their usual sport never learns another has bets waiting.
  const sportSignalCounts = useMemo(() => signalCountsBySport(allData), [allData]);
  // A pick is only a SIGNAL once it's locked. Future-dated UFC/golf picks
  // re-score until game day — they show on Today as lines/previews but are
  // excluded here (and from every signal count) until they lock.
  const live = useMemo(
    () => todayData.filter((d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick)),
    [todayData],
  );

  const activeItems: EnrichedPick[] =
    view === 'today' ? todayData : view === 'live' ? liveData : live;

  // Signals is the paid surface; Today (every scored pick, with
  // model % and edge) stays free. `entitled` is true whenever billing is off,
  // so this is inert until the flag flips.
  const { entitled } = useEntitlement();
  const signalsLocked = !entitled && view !== 'today';

  // Restrict the filter's Market options to what is on screen — on EVERY view,
  // not just the signal ones. Today passed `undefined` here until 2026-09-09,
  // which PickFilters read as "offer all four categories", so the NFL board
  // offered MLB's Pitcher and Batter markets and the active pill named them.
  //
  // NOT deduplicated: the filter counts picks per market to put a number on
  // each facet chip, and a Set of model ids counts models instead.
  const availableModelIds = useMemo(
    () => activeItems.map((d) => d.pick.model_id),
    [activeItems],
  );

  // ── The GAMES cut, shared with the Stats tab ───────────────────────────────
  // Matt, 2026-09-09: one selection across both tabs, so picking tonight's
  // game on the Stats board narrows this list to that game's bets and back.
  // Kept OUT of PicksFilterState deliberately: that object is cloned, reset and
  // persisted as a set of thresholds, and a game id is none of those things —
  // it is one fixture on one date and belongs to the slate, not to the filter.
  const gamePicker = useGameSelection(sport);

  // ── The DATE cut (Matt, 2026-09-26: "games could be on different days") ────
  // One board can hold a game in play, tonight's kickoffs and a look-ahead pick
  // for a Saturday weeks out, all interleaved by edge. A set of `game_date`s;
  // empty = every date. Local and unpersisted (lib/dateFilter), and dropped on
  // a sport switch because another sport's days are a different slate.
  const [pickedDates, setPickedDates] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    setPickedDates(new Set());
  }, [sport]);
  const dateOptions = useMemo(
    () => dateOptionsFor(activeItems.map((d) => d.pick.game_date)),
    [activeItems],
  );
  // Resolved against THIS board, for display only: a day picked on Today that
  // Signals does not hold reads as all dates there rather than emptying Signals
  // behind chips that show nothing selected. NOT written back — `pickedDates`
  // stays what the user chose, so Today → Live → Today returns to their day.
  const selectedDates = useMemo(
    () => effectiveDateSelection(pickedDates, dateOptions),
    [pickedDates, dateOptions],
  );
  const toggleDate = useCallback((date: string) => {
    setPickedDates((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  }, []);
  const clearDates = useCallback(() => setPickedDates(new Set()), []);
  const datedItems = useMemo(
    () => activeItems.filter((d) => isDateSelected(d.pick.game_date, selectedDates)),
    [activeItems, selectedDates],
  );

  // The Games list follows the Date cut, so picking Saturday lists Saturday's
  // fixtures instead of every game in the window — EXCEPT a game already
  // checked. The Games selection is shared with Stats, so it can hold a game on
  // another day; dropping it from the list left a "1 game" pill, an empty board
  // and no checkbox to undo it (UX review, 2026-09-26). A checked game always
  // stays listed, under its own day header.
  const pickableGames = useMemo(() => {
    const byId = new Map<string, NonNullable<EnrichedPick['game']>>();
    for (const d of activeItems) {
      if (!d.game) continue;
      const keep =
        isDateSelected(d.pick.game_date, selectedDates) || gamePicker.selected.has(d.game.game_id);
      if (keep) byId.set(d.game.game_id, d.game);
    }
    return selectableGames(Array.from(byId.values()), sport, todayET());
  }, [activeItems, selectedDates, gamePicker.selected, sport]);
  // THIS SCREEN DOES NOT PRUNE, AND MUST NOT. Pruning belongs to the one read
  // that sees the whole forward window — the Stats tab's slate read. The list
  // here is only the games with picks IN THIS VIEW (`activeItems` swaps with
  // Today / Signals / Live), so pruning against it would intersect the shared
  // selection down to nothing: Picks mounts at launch and never unmounts, so a
  // game picked on the Stats board for Sunday would be dropped immediately by
  // a screen that has never heard of it, and the Stats board would silently
  // widen back to the whole league. Tapping Today -> Signals did the same thing
  // inside this screen alone (UX review, 2026-09-09).
  //
  // A picked game with no picks in this view is a legitimate empty list. The
  // empty state names the game and the board (Today / Signals / Live) and
  // offers Clear games — the generic "widen signals / thresholds" copy never
  // mentioned this cut.

  // Apply Signal/Market locks on the first paint of the destination board.
  // A useEffect write-back alone flashes the empty list (and a Signal pill
  // on a board with no Signal section) — the case locks 3/4 exist to stop.
  const displayFilter = useMemo(() => {
    const present = presentCategoriesFor(availableModelIds);
    const afterMarket = resetImpossibleMarket(filter, present);
    if (view !== 'today' && afterMarket.signals.size < ALL_SIGNALS.length) {
      const next = afterMarket === filter ? cloneFilter(filter) : afterMarket;
      next.signals = new Set(ALL_SIGNALS);
      return next;
    }
    return afterMarket;
  }, [filter, view, availableModelIds]);
  useEffect(() => {
    if (displayFilter !== filter) setFilter(displayFilter);
  }, [displayFilter, filter]);

  // Every cut except the search box. Split out so the empty state can tell
  // "search emptied it" from "the filters emptied it" (usability audit M12).
  const unsearched = useMemo(
    () =>
      applyFilter(datedItems, displayFilter).filter(
        (d) =>
          isGameSelected(d.pick.game_id, gamePicker.selected) &&
          // A Signal filter asks what the MODEL called, and a paused model
          // is making no calls: a paused row's stored BET is not a bet
          // (passesActionFilter refuses it, and the header's "N bets" does
          // not count it). So once Signal narrows, paused rows drop out —
          // otherwise "BET only" listed PAUSED cards under a header that
          // counted three bets (UX review, 2026-09-26).
          (displayFilter.signals.size === ALL_SIGNALS.length || !isPausedForDisplay(d.pick)),
      ),
    [datedItems, displayFilter, gamePicker.selected],
  );
  const filtered = useMemo(() => searchPicks(unsearched, search), [unsearched, search]);
  const publicSortLive = useMemo(() => publicSortAvailable(filtered), [filtered]);
  useEffect(() => {
    if (!publicSortLive && sortKey === 'public') setSortKey('edge');
  }, [publicSortLive, sortKey]);
  // Paused rows sort AFTER active ones on every key, the chosen sort holding
  // inside each group: a paused model's noisy edges would otherwise take the
  // top of an edge-sorted All board and push the real bets below the fold
  // (UX review, 2026-09-26). A stable partition of the sorted list.
  //
  // H4: on the Edge sort a row the price-check band flags goes after the rest
  // of its group, so an implausible price never takes the top slot (display
  // only, lib/priceCheck.ts).
  // The live snapshot goes in so the in-play skip matches the card's.
  const sorted = useMemo(() => {
    const all = sortPicks(filtered, sortKey, {
      priceCheck: (d) => priceCheckForItem(d, liveStates.get(d.pick.game_id) ?? null).flagged,
    });
    return [
      ...all.filter((d) => !isPausedForDisplay(d.pick)),
      ...all.filter((d) => isPausedForDisplay(d.pick)),
    ];
  }, [filtered, sortKey, liveStates]);
  // Time sort reads as a schedule, so it is split by day with a header per
  // day (Matt, 2026-09-28). Every other sort is a ranking and stays one list.
  const rows: DayRow<EnrichedPick>[] = useMemo(
    () =>
      sortKey === 'time'
        ? rowsByDay(
            sortPicks(filtered, 'time'),
            (d) => d.pick.game_date,
            (d) => String(d.pick.pick_id),
            (d) => isPausedForDisplay(d.pick),
          )
        : sorted.map((d) => ({ kind: 'item' as const, key: String(d.pick.pick_id), item: d })),
    [filtered, sorted, sortKey],
  );

  // Games is shared with Stats. A game picked there (or here) can empty THIS
  // board while Today still has picks — the generic "widen signals / thresholds"
  // empty state never named the shared cut, so the board read as broken.
  const emptiedByGames = useMemo(() => {
    if (activeItems.length === 0 || filtered.length > 0 || gamePicker.selected.size === 0) {
      return false;
    }
    return searchPicks(applyFilter(datedItems, displayFilter), search).length > 0;
  }, [activeItems, datedItems, filtered.length, displayFilter, search, gamePicker.selected]);

  // Search alone emptied the board: the filters and Games still leave picks,
  // the query matched none of them. The generic "widen signals / thresholds"
  // copy blamed settings the user never touched (usability audit M12).
  const emptiedBySearch = useMemo(
    () => filtered.length === 0 && search.trim().length > 0 && unsearched.length > 0,
    [filtered.length, search, unsearched.length],
  );

  // All: BET/AVOID/NONE counts.
  const todayStats = useMemo(() => {
    const bet = todayData.filter((d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick)).length;
    const paused = todayData.filter((d) => isPausedForDisplay(d.pick)).length;
    return { total: todayData.length, bet, paused };
  }, [todayData]);

  // Signals / Live views: exposure of the recommended stakes on screen.
  const signalExposure = useMemo(() => {
    if (view === 'today') return 0;
    return filtered.reduce((sum, d) => sum + unitsFor(d.pick.kelly_fraction, decisionOdds(d.pick)), 0);
  }, [filtered, view]);

  // FIRST LOAD ONLY on the live board. `refresh()` sets loading on every poll,
  // and the poll is 30s while this segment is open — so while the board was
  // conditional this was invisible (it always had rows), and the moment it became
  // permanent it meant a reader parked on an empty board watched the empty state
  // blink out to a spinner twice a minute (UX review, 2026-09-12). prevLiveCount
  // is null until the first settled fetch, which is exactly "never loaded".
  const liveFirstLoad = liveLoading && prevLiveCount.current === null;
  const busy = view === 'live' ? liveFirstLoad : loading;
  // A FAILED load with nothing to show for this view. It replaces the empty
  // state rather than sitting above it: "No MLB picks today" under a timeout
  // told the user the opposite of what happened (usability audit H3). With
  // rows still on screen from an earlier load, the banner carries the failure.
  const viewError = view === 'live' ? liveError : error;
  // lib/loadState decides (and is RUN by the verify script and the pytest);
  // busy is checked first below, so a failure mid-first-load stays a skeleton.
  const failed =
    loadPresentation({
      loading: false,
      error: viewError,
      hasData: view === 'live' ? liveData.length > 0 : activeItems.length > 0,
    }).body === 'error';
  // Counts that were never loaded are unknown, not zero ("—", PATTERNS §F5):
  // a failed first load, and also everything BEFORE the first successful one
  // (loading or slow). "0 bets · 0 scored" and "(0)" on a cold start claimed
  // an empty board nobody had read yet (Designer #845).
  const todayUnknown =
    knownCount(0, { loaded, error, hasData: allData.length > 0 || pausedData.length > 0 }) === null;
  const liveUnknown = knownCount(0, { loaded: liveLoaded, error: liveError, hasData: allLiveData.length > 0 }) === null;
  // Pull-to-refresh still has to spin, and it cannot read `busy` any more for the
  // same reason. Local, because the hook cannot tell a poll from a pull.
  const [pulling, setPulling] = useState(false);
  const stakedSuffix = signalExposure > 0 ? ` · ${formatUnits(signalExposure)} staked` : '';
  const subtitle = failed
    ? view === 'live'
      ? 'Live signals unavailable'
      : todayHeaderCounts({ date, known: false, ...todayStats })
    : view === 'today'
      ? todayHeaderCounts({ date, known: !todayUnknown, ...todayStats })
      // NO DATE on the live board, and that is not a tidy-up. The board can now
      // hold a game that kicked off before midnight ET, which the whole system
      // files under YESTERDAY -- Discord posted it under that date, the track
      // record will file it under that date, and the pick's own timing card
      // says so one tap away. Nothing on a live card carries a date, so the
      // header was the only one a reader got, and it was the wrong one.
      // Everything here is by definition happening now, so the date carries no
      // information and carried wrong information (UX review, 2026-09-06;
      // Apple Sports and FotMob both replace the date with the clock in play).
      : view === 'live'
        ? // An always-on board is read when it is empty too, so the header says
          // so in words rather than handing back "0 in play". Not before the
          // first fetch has answered, though: that is unknown, not empty.
          liveUnknown
          ? '— in play'
          : liveData.length === 0
          ? 'No live signals right now'
          : `${liveData.length} in play${stakedSuffix}`
        // "PRE-GAME signals". Signals and Live Signals are disjoint sets —
        // fetchPicksForDate excludes is_live rows — so `Signals (3)` beside
        // `Live Signals (2)` is five standing bets, not two of three. Naming the
        // third board "Live Signals" is what invites the subset reading, and the
        // person it misleads is the one adding up exposure (UX review,
        // 2026-09-12). "signals", not "live", for the older reason: with a
        // segment labelled Live on the same control, "3 live" meant two different
        // things one line apart.
        : `${date} · ${todayUnknown ? '—' : live.length} pre-game signals${stakedSuffix}`;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Picks</Text>
          <InfoTooltip
            title="The three boards"
            body={
              // The live sports are INTERPOLATED, not typed out: this sentence
              // and the empty state are the two places a reader is told which
              // sports have an in-play model, and a hand-written list here would
              // be the one that goes stale when a lane ships (lib/liveSports.ts).
              `All = every pick the model scored today. Picks from a paused model show here too, marked PAUSED — they are the model’s number, not a bet, and never appear on Signals.\n\nSignals = pre-game picks that crossed the bet line and are still standing right now. In-play picks are counted separately, on Live Signals — the two boards never hold the same pick.\n\nLive Signals = in-play picks, priced at DraftKings while a game is running. This board is always here, and it fills only while a game is in play and the in-play model finds an edge — so (0) is a real answer, not a board that failed. In-play models run on ${liveModelSportsSentence()} today. A game that started before midnight stays here until it ends, so a late game keeps yesterday’s date everywhere else in the app.\n\nA red dot on a sport, or on Live Signals, means a game is in play now.\n\nPicks lock the first time they’re scored each day (props at their first signal) and never change again after that — so a signal shown here won’t flip to AVOID later. Open a pick to see how the DK line has moved since it locked.\n\nLines refresh hourly 6am–6pm ET, then every 10 minutes until 11pm. Live picks refresh every 30 seconds.`
            }
            accessibilityLabel="About the three boards"
          />
          <View style={styles.headerRight}>
            <BetslipButton />
            <SettingsButton />
          </View>
        </View>
        <Text style={styles.subtitle} accessibilityLabel={unknownCountSpeech(unitsSpeech(subtitle))}>{subtitle}</Text>
        {/* Neutral chips until today's board (and the live one) is known: built
            from empty data, every chip read muted and "no picks today" after a
            failure or before the first load (Designer #845). */}
        <SportToggle
          available={sportChipsAvailable(availableSports, !todayUnknown && !liveUnknown)}
          signalCounts={sportSignalCounts}
          liveSports={liveSports}
          // H9, 45pt with no visual change: 6pt over the subtitle line above
          // (text, not a control) and half of the 12pt gap to the sub-tab chips
          // below — they take the other half (SUBTAB_REACH_ABOVE).
          reachAbove={6}
          reachBelow={4}
        />
        {/* Horizontal scroller, the same one SportToggle uses. Three segments
            with counts and a dot fit comfortably at default text size, but only
            the labels scale: the row ran off the right edge at roughly the first
            accessibility text size on a 375pt screen, and at plain xxLarge on a
            320pt one (or any phone with Display Zoom on). "Live Signals (0)" is
            8 characters longer than "Live (3)", which moves both breakpoints
            down by about a quarter (UX review, 2026-09-12), so the row gets the
            two things SportToggle already has: trailing padding, so the last
            pill never butts the bezel with no hint that there is more, and
            SCROLL-INTO-VIEW on the selected segment — a deep link from Settings
            or a push can select one that is off-screen, and a control showing
            three unselected segments reads as a rendering bug. */}
        <ScrollView
          ref={segmentsRef}
          horizontal
          showsHorizontalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          // Down into the header's own bottom padding (no sibling there), so
          // the sub-tabs' slop below is in bounds (H9).
          style={subTabsReach.frame}
          contentContainerStyle={[styles.subTabsScroll, subTabsReach.content]}
        >
          <View style={styles.subTabs} accessibilityRole="tablist">
            <SubTabBtn label="All" count={todayUnknown ? null : todayStats.total} active={view === 'today'} onPress={() => setView('today')} onLayout={onSegmentLayout('today')} />
            <SubTabBtn label="Signals" count={todayUnknown ? null : live.length} active={view === 'signals'} onPress={() => setView('signals')} onLayout={onSegmentLayout('signals')} />
            {/* UNCONDITIONAL, on every sport (matt, 2026-09-12) — see the file
                header. The count and the dot carry what the conditional render
                used to: `(0)` with no dot is the "nothing in play" answer, in a
                fixed place. The DOT is what must stay conditional — a red mark
                that is always lit says nothing at all, and it is the same 6pt
                dot the sport chips and the LIVE pill on a card use. */}
            <SubTabBtn
              label="Live Signals"
              count={liveUnknown ? null : liveData.length}
              active={view === 'live'}
              onPress={() => setView('live')}
              live
              dot={liveData.length > 0}
              onLayout={onSegmentLayout('live')}
            />
          </View>
        </ScrollView>
      </View>

      {/* Live pricing caveats, and ONLY on the live segment. Both are
          load-bearing (CLAUDE.md §6): the feed serves one cached in-play
          snapshot for ~45s so a number here can be behind DK's own app, and the
          in-play model reads DK's line and the bet is placed there. Kept as one
          paragraph: "bet your sportsbook's number" beside "your sportsbook
          doesn't apply" contradicted itself (UX review). */}
      {view === 'live' && liveData.length > 0 ? (
        <View style={styles.liveNoteWrap}>
          <Ionicons name="alert-circle-outline" size={16} color={colors.medInk} />
          <Text style={styles.liveNote}>DraftKings only · prices up to ~45s old</Text>
          <InfoTooltip
            title="Live pricing"
            body={
              'Live picks are priced and placed at DraftKings only — the in-play model reads DK’s line and the bet is placed there, so your own sportsbook setting does not apply here.\n\nOur feed serves one cached in-play snapshot for about 45 seconds, and its bulk and per-event endpoints return the same cache — so a number here can be up to ~45s behind DraftKings’ own app. Polling faster would not change that.\n\nBet the number DraftKings shows, and skip it if it has moved past the edge.'
            }
            accessibilityLabel="About live pricing"
          />
        </View>
      ) : null}

      {/* Rows from an earlier load are still up: keep them, say the refresh
          failed, offer Retry (PATTERNS §E3). A whole-view failure is the
          ErrorState in the list instead, so the two never stack. */}
      {viewError && !failed ? (
        <ErrorBanner
          what={view === 'live' ? `the latest ${sport} live signals` : `the latest ${sport} picks`}
          error={viewError}
          onRetry={() => void (view === 'live' ? refreshLive() : refresh())}
          retrying={view === 'live' ? liveLoading : loading}
          reassurance={PICKS_REASSURANCE}
        />
      ) : null}

      {/* The picks loaded but something behind them did not — the odds views
          the line pills read, or one sport's look-ahead card. Say so and
          offer the retry; an empty pill and silence is how the 2026-09-04
          timeouts went unseen here. Hidden while reloading, so a tap on Retry
          answers at once and the banner only returns if the reload fails
          again (UX review). */}
      {!error && !loading && partial ? (
        <Pressable
          onPress={() => void refresh()}
          accessibilityRole="button"
          accessibilityLabel={partialSentence(partial)}
          accessibilityHint="Reloads today’s picks"
          style={({ pressed }) => [styles.partialBanner, pressed && styles.partialPressed]}
        >
          <Ionicons name="alert-circle-outline" size={16} color={colors.medInk} />
          <Text style={styles.partialText} numberOfLines={3}>
            {partialSentence(partial)} <Text style={styles.partialLink}>Retry</Text>
          </Text>
        </Pressable>
      ) : null}

      {/* Picks came back, DraftKings' in-play prices did not: every card would
          quietly lose its Now price. Say so, with the same retry as the Today
          partial banner (usability audit M2). */}
      {showLivePricesBanner({
        view,
        liveError,
        pricesUnavailable: livePricesUnavailable,
        liveCount: liveData.length,
      }) ? (
        <Pressable
          onPress={() => void refreshLive()}
          accessibilityRole="button"
          accessibilityLabel="Live prices unavailable. Cards show the locked price only."
          accessibilityHint="Reloads live prices"
          accessibilityLiveRegion="polite"
          style={({ pressed }) => [styles.partialBanner, pressed && styles.partialPressed]}
        >
          <Ionicons name="alert-circle-outline" size={16} color={colors.medInk} />
          <Text style={styles.partialText} numberOfLines={3}>
            Live prices unavailable. Cards show the locked price only.{' '}
            <Text style={styles.partialLink}>Retry</Text>
          </Text>
        </Pressable>
      ) : null}

      {activeItems.length > 0 && !signalsLocked ? (
        <PickFilters
          state={displayFilter}
          onChange={setFilter}
          sortKey={sortKey}
          onSortChange={setSortKey}
          publicSortAvailable={publicSortLive}
          search={search}
          onSearchChange={setSearch}
          totalShown={filtered.length}
          totalAll={activeItems.length}
          availableModelIds={availableModelIds}
          games={pickableGames}
          selectedGames={gamePicker.selected}
          onToggleGame={gamePicker.toggle}
          onClearGames={gamePicker.clear}
          dateOptions={dateOptions}
          selectedDates={selectedDates}
          onToggleDate={toggleDate}
          onClearDates={clearDates}
          showSignals={view === 'today'}
          itemNoun={view === 'today' ? 'pick' : view === 'live' ? 'live pick' : 'signal'}
        />
      ) : null}

      {/* The paywall card is for picks that EXIST and are hidden behind it. On an
          empty live board it said "the models haven't found a bet that clears the
          line yet today", which on a sport with no in-play model is a promise the
          app cannot keep — the exact sentence lib/liveSports.ts exists to prevent
          — and it pitched a trial on a board that is structurally empty there
          (UX review, 2026-09-12). */}
      {signalsLocked && !(view === 'live' && liveData.length === 0) ? (
        <SignalLockCard
          count={view === 'live' ? liveData.length : live.length}
          onPress={() => navigation.navigate('Paywall')}
        />
      ) : (
      <FlatList
        ListFooterComponent={<BetslipBarSpacer />}
        data={rows}
        keyExtractor={(row) => row.key}
        renderItem={({ item: row, index }) => {
          if (row.kind === 'day') {
            // The first header sits where the first card would (the list's
            // own paddingTop), so switching to Time does not drop the board.
            return (
              <SectionTitle
                title={row.label}
                accessibilityLabel={row.spoken}
                style={index === 0 ? styles.firstDayHeader : undefined}
              />
            );
          }
          const item = row.item;
          return (
            <PickCard
              item={item}
              onPress={() => navigation.navigate('PickDetail', { pickId: item.pick.pick_id })}
              tracked={tracked.isTracked(item.pick)}
              onToggleTrack={() => tracked.toggle(item.pick)}
              inSlip={slip.has(slipKeyForPick(item.pick))}
              onToggleSlip={() => slip.toggle(slipKeyForPick(item.pick))}
              liveState={liveStates.get(item.pick.game_id) ?? null}
              showSignalBadge={view === 'today'}
              paused={view === 'today' && isPausedForDisplay(item.pick)}
            />
          );
        }}
        ListEmptyComponent={
          busy ? (
            <PicksSkeleton sport={sport} />
          ) : failed ? (
            <ErrorState
              what={view === 'live' ? `${sport} live signals` : `today’s ${sport} picks`}
              error={viewError}
              onRetry={() => void (view === 'live' ? refreshLive() : refresh())}
              retrying={view === 'live' ? liveLoading : loading}
              reassurance={PICKS_REASSURANCE}
            />
          ) : (
            <EmptyForView
              view={view}
              sport={sport}
              date={date}
              hasAny={activeItems.length > 0}
              search={emptiedBySearch ? search.trim() : ''}
              onClearSearch={() => setSearch('')}
              emptiedByGames={emptiedByGames}
              gameSummary={gameFilterSummary(pickableGames, gamePicker.selected)}
              onClearGames={gamePicker.clear}
            />
          )
        }
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={view === 'live' ? pulling : busy}
            onRefresh={() => {
              // Pull-to-refresh on the live segment must hit the live fetch —
              // refreshing today's board there would spin and change nothing.
              if (view !== 'live') {
                void refresh();
                return;
              }
              setPulling(true);
              void refreshLive().finally(() => setPulling(false));
            }}
          />
        }
      />
      )}
    </SafeAreaView>
  );
}

function boardLabel(view: PicksView): string {
  if (view === 'today') return 'All';
  if (view === 'signals') return 'Signals';
  return 'Live';
}

/**
 * First load of the board: card-shaped placeholders under the real header,
 * segments and filters, never a flash of "No picks today" (PATTERNS §E2).
 */
function PicksSkeleton({ sport }: { sport: string }) {
  return (
    <Skeleton label={`${sport} picks`} style={styles.skeletonWrap}>
      {[0, 1, 2].map((i) => (
        <View key={i} style={styles.skeletonCard}>
          <SkeletonBlock width="30%" height={8} />
          <SkeletonBlock width="70%" height={14} />
          <SkeletonBlock width="40%" height={8} />
          <View style={styles.skeletonFoot}>
            <SkeletonBlock width={64} height={20} />
            <SkeletonBlock width={56} height={16} />
          </View>
        </View>
      ))}
    </Skeleton>
  );
}

function EmptyForView({
  view,
  sport,
  date,
  hasAny,
  search,
  onClearSearch,
  emptiedByGames,
  gameSummary,
  onClearGames,
}: {
  view: PicksView;
  sport: string;
  date: string;
  hasAny: boolean;
  /** Non-empty only when the search query alone emptied the board (M12). */
  search: string;
  onClearSearch: () => void;
  emptiedByGames: boolean;
  gameSummary: string;
  onClearGames: () => void;
}) {
  if (hasAny && search) {
    return (
      <EmptyState
        title={`No picks match “${search}”`}
        subtitle={`Search looks at player and team names on ${boardLabel(view)}. Check the spelling, or clear the search to see every pick here.`}
        actionLabel="Clear search"
        onAction={onClearSearch}
      />
    );
  }
  if (hasAny && emptiedByGames) {
    return (
      <EmptyState
        title={`No picks for ${gameSummary} on the ${boardLabel(view)} board`}
        actionLabel="Clear games"
        onAction={onClearGames}
      />
    );
  }
  if (hasAny) {
    return (
      <EmptyState
        title="No picks match your filter"
        subtitle="Try widening signals, categories, or lowering the thresholds. Search, Date and Games also narrow this list — they show as pills above."
      />
    );
  }
  if (view === 'today') {
    return (
      <EmptyState
        title={`No ${sport} picks today`}
        subtitle={`No ${sport} picks have been scored for ${date} yet. Lines refresh hourly 6am–6pm ET, then every 10 minutes until 11pm.`}
      />
    );
  }
  if (view === 'signals') {
    return (
      <EmptyState
        title="No signal bets right now"
        subtitle="Zero picks is a valid signal — no high-conviction plays right now. Open the All board to see everything the model scored, or check back after the next refresh."
      />
    );
  }
  if (view === 'live') {
    // THE ORDINARY STATE OF THIS BOARD, not a transient one: it is on screen for
    // every sport now, and empty most of the clock (file header). So it has to
    // answer the question a reader opened it with, and that answer is different
    // per sport — which is the whole reason lib/liveSports.ts exists. For a
    // sport with an in-play model, empty means no edge right now. For a sport
    // without one, "an in-play model finds an edge" is a promise about something
    // that cannot happen, and a reader waiting on it waits forever.
    if (!hasLiveModel(sport)) {
      return (
        <EmptyState
          title={`No live model for ${sport} yet`}
          subtitle={`In-play models run on ${liveModelSportsSentence()} today, so this board stays empty for ${sport}. The All and Signals boards carry ${sport}’s pre-game picks.`}
        />
      );
    }
    return (
      <EmptyState
        title={`No ${sport} live signals right now`}
        subtitle="Live signals appear while a game is in play and the in-play model finds an edge at DraftKings’ live number. Zero of them is a valid answer, not a board that failed to load."
      />
    );
  }
  // Exhaustive over View2 — a third view added later has to say what it shows
  // here rather than silently inheriting the Signals copy (UX review). The
  // null is unreachable; the annotation is what fails the build.
  const exhaustive: never = view;
  void exhaustive;
  return null;
}

function SubTabBtn({
  label,
  count,
  active,
  onPress,
  live = false,
  dot = false,
  onLayout,
}: {
  label: string;
  /** null = never loaded (a failed first load): shown as "—", not 0. */
  count: number | null;
  active: boolean;
  onPress: () => void;
  /** Reports where this segment sits, so the selected one can be scrolled to. */
  onLayout?: (e: LayoutChangeEvent) => void;
  /** This is the in-play board — drives what its count is counting. */
  live?: boolean;
  /**
   * Draws the app's live dot ahead of the label. SEPARATE from `live` since
   * 2026-09-12: the live board is always on screen, so "is this the live board"
   * and "is anything live right now" stopped being the same question, and a
   * permanently lit dot is a dot that has stopped meaning anything.
   */
  dot?: boolean;
}) {
  const noun = label === 'All' ? 'picks' : live ? 'picks in play' : 'signals';
  return (
    <Pressable
      onPress={onPress}
      onLayout={onLayout}
      // Only the in-bounds part of slop lands (a horizontal ScrollView takes
      // no touches outside itself), so this is exactly the room inside the
      // row: 6 above (its half of the gap to the sport chips) and 2 + 6 below
      // (subTabsReach) → ~46pt (audit H9/M8).
      hitSlop={{ top: SUBTAB_REACH_ABOVE, bottom: 2 + SUBTAB_REACH_BELOW }}
      accessibilityRole="tab"
      accessibilityState={{ selected: active }}
      accessibilityLabel={count == null ? `${label}, count not available` : `${label}, ${count} ${noun}`}
      style={({ pressed }) => [styles.subTab, active && styles.subTabActive, pressed && styles.pressed]}
    >
      <View style={styles.subTabInner}>
        {dot ? <LiveDot /> : null}
        <Text style={[styles.subTabText, active && styles.subTabTextActive]}>
          {label} ({count ?? '—'})
        </Text>
      </View>
    </Pressable>
  );
}

/** "Couldn’t load today’s lines and the line shop. Signalbase is slow to
 *  respond right now. Try again in a moment. Today’s picks are unaffected."
 *  One sentence per part, for the partial-load banner. The raw reason is
 *  sorted into a plain cause and never shown (usability audit M1). */
export function partialSentence(p: { whats: string[]; reason: string }): string {
  const w = p.whats;
  const list = w.length <= 1 ? w.join('') : `${w.slice(0, -1).join(', ')} and ${w[w.length - 1]}`;
  return `Couldn’t load ${list}. ${friendlyCause(p.reason)} Today’s picks are unaffected.`;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  headerRight: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 4,
  },
  // Trailing gutter on the SCROLLER, not on the row: the last segment must not
  // butt the bezel, which is the only hint a reader gets that the row scrolls
  // (SportToggle does the same).
  subTabsScroll: {
    paddingRight: spacing.lg,
  },
  subTabs: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    padding: 2,
    marginTop: spacing.sm,
  },
  subTab: {
    paddingHorizontal: spacing.md,
    // ~32pt tall, the iOS segmented-control height. spacing.xs left it at ~25pt
    // and misses landed on the header behind it (UX review, 2026-09-05).
    paddingVertical: spacing.sm,
    borderRadius: radii.sm - 2,
  },
  subTabActive: {
    backgroundColor: colors.bgCard,
  },
  subTabInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  pressed: {
    opacity: 0.6,
  },
  subTabText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  subTabTextActive: {
    color: colors.tint,
  },
  firstDayHeader: { marginTop: 0 },
  list: {
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
  },
  skeletonWrap: { gap: spacing.xs },
  // Same box as PickCard's card, so the list does not jump when rows land.
  skeletonCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    marginHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  skeletonFoot: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.xs },
  partialBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: radii.sm,
    minHeight: 44,
  },
  partialPressed: {
    opacity: 0.7,
  },
  partialText: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: font.size.footnote,
  },
  partialLink: {
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  liveNoteWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  // The caution reads as amber through the ICON, never the text. colors.med is
  // #FF9500 — 1.97:1 on colors.bg, well under the 4.5:1 floor, and theme.ts
  // already struck it from the grade ramp for exactly that. This paragraph
  // carries a CLAUDE.md §6 rule and the staleness disclosure, so it is the last
  // text in the app that should be hard to read; the full version hangs off the
  // tooltip beside it rather than costing ~110pt above the board.
  liveNote: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: font.size.footnote,
  },
});

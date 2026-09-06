/**
 * Merged Picks tab — a single home for the daily board with a
 * `Today | Signals | Live` segmented control. Replaces the old separate
 * Picks and Signals tabs (which both showed BET picks and read as redundant):
 *   - Today    = every scored pick today (the old Picks tab).
 *   - Signals  = picks that crossed the bet line and are still live.
 *   - Live     = in-play picks, and ONLY when there are some (see below).
 *
 * LIVE WAS A BOTTOM TAB UNTIL 2026-09-06 (Matt's call, after measurement). It
 * was the same PickCard, over the same sport filter, in a header that was a
 * lossy copy of this one — the third state of one object, given a sixth of the
 * tab bar. Measured over the 30 days to 2026-09-06: 175 live BETs on 25 of 31
 * days, ~5.3h of board occupancy per active day — the board was empty ~81% of
 * the clock, and for NBA, NHL, NFL, UFC and GOLF it was empty 100% of it. A tab
 * that is empty on your first three visits teaches you not to go there.
 *
 * So the Live SEGMENT is conditional: it renders only when the selected sport
 * has an in-play pick standing. When nothing is live the control reads
 * `Today | Signals` exactly as before and nobody learns to ignore an empty
 * slot — the segment appearing IS the live indicator. Which sport is live is
 * carried by the red dot on the sport chips (SportToggle `liveSports`), which
 * is strictly more than the tab ever said: the tab was always visible but never
 * named the sport.
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

import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { PickCard } from '@/components/PickCard';
import { EmptyState } from '@/components/EmptyState';
import { InfoTooltip } from '@/components/InfoTooltip';
import {
  applyFilter,
  freshFilter,
  PickFilters,
  type PicksFilterState,
} from '@/components/filters/PickFilters';
import { SportToggle } from '@/components/SportToggle';
import { SettingsButton } from '@/components/SettingsButton';
import { BetslipButton } from '@/components/BetslipButton';
import { SignalLockCard } from '@/components/SignalLockCard';
import { useEntitlement } from '@/hooks/useEntitlement';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useLivePicks, LIVE_POLL_MS, LIVE_IDLE_POLL_MS } from '@/hooks/useLivePicks';
import { useLiveGameStates } from '@/hooks/useLiveGameStates';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useTrackedBets } from '@/hooks/useTrackedBets';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useResponsibleGambling } from '@/hooks/useResponsibleGambling';
import { signalCountsBySport } from '@/lib/lineMovementBoard';
import { slipKeyForPick } from '@/lib/parlay';
import { sortPicks, searchPicks, type SortKey } from '@/lib/pickSort';
import { colors, font, radii, spacing } from '@/lib/theme';
import { isUnlockedPreview, passesActionFilter, unitsFor, formatUnits } from '@/lib/thresholds';
import { formatCurrency, formatPct } from '@/lib/format';
import type { EnrichedPick, RootStackParamList, TabParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
export type PicksView = 'today' | 'signals' | 'live';

export function PicksHomeScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<RouteProp<TabParamList, 'Picks'>>();
  const { data: allData, loading, error, partial, refresh, date } = useTodayPicks();
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const tracked = useTrackedBets();
  const slip = useParlaySlip();
  // In-play score + inning for games that have started (polls every 30s).
  const { byGame: liveStates } = useLiveGameStates(date);
  const { settings: rg } = useResponsibleGambling();

  const [view, setView] = useState<PicksView>(route.params?.view ?? 'today');
  const [filter, setFilter] = useState<PicksFilterState>(freshFilter);
  const [sortKey, setSortKey] = useState<SortKey>('edge');
  const [search, setSearch] = useState('');

  // In-play picks, across every sport (the sport cut happens below, so the
  // toggle can mark the sports that are live). Polled fast only while the user
  // is on the live segment — see useLivePicks.
  const {
    data: allLiveData,
    loading: liveLoading,
    error: liveError,
    refresh: refreshLive,
  } = useLivePicks({ pollMs: view === 'live' ? LIVE_POLL_MS : LIVE_IDLE_POLL_MS });

  const todayData = useMemo(
    () => allData.filter((d) => d.pick.sport === sport),
    [allData, sport],
  );
  const liveData = useMemo(
    () => allLiveData.filter((d) => d.pick.sport === sport),
    [allLiveData, sport],
  );
  // Sports with an in-play pick standing right now — the red dot on the chips.
  const liveSports = useMemo(
    () => new Set(allLiveData.map((d) => d.pick.sport)),
    [allLiveData],
  );

  // MLB and WNBA share no model_ids — a stale filter would show "0 of N" after a
  // sport switch. Reset filter/search on sport change.
  //
  // The view is only reset when the NEW sport cannot show it: bouncing someone
  // back to Today every time they switch sports was fine while both views always
  // existed, but the live segment is conditional, so a blanket reset would eject
  // a user watching a live game the moment they glanced at another sport. Live
  // survives a switch to another live sport; it falls back to Today otherwise,
  // because there is no segment left to stand on.
  useEffect(() => {
    setFilter(freshFilter());
    setSearch('');
    setView((v) => (v === 'live' && !liveSports.has(sport) ? 'today' : v));
    // liveSports is deliberately not a dependency: this runs on a SPORT change,
    // and re-running it as live picks arrive would fight the user's own taps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sport]);

  // The live board emptying out (last game ended) has to move the user too —
  // the segment is about to disappear from under them.
  useEffect(() => {
    if (view === 'live' && !liveLoading && liveData.length === 0) setView('today');
  }, [view, liveLoading, liveData.length]);
  // Sports with anything on today's board — the rest are muted in the toggle so
  // the eye lands on the ones that actually have picks.
  const sportsWithPicks = useMemo(
    () => new Set(allData.map((d) => d.pick.sport)),
    [allData],
  );
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

  // For the signal views, restrict the filter options to what's on screen.
  const availableModelIds = useMemo(
    () =>
      view === 'today'
        ? undefined
        : Array.from(new Set(activeItems.map((d) => d.pick.model_id))),
    [view, activeItems],
  );

  const filtered = useMemo(
    () => searchPicks(applyFilter(activeItems, filter), search),
    [activeItems, filter, search],
  );
  const sorted = useMemo(() => sortPicks(filtered, sortKey), [filtered, sortKey]);

  // Today: BET/AVOID/NONE counts. Daily exposure guardrail (over the opt-in cap).
  const todayStats = useMemo(() => {
    const bet = todayData.filter((d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick)).length;
    return { total: todayData.length, bet };
  }, [todayData]);

  const exposure = useMemo(() => {
    if (rg.exposureCapUnits == null) return null;
    const total = allData
      .filter((d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick))
      .reduce((s, d) => s + unitsFor(d.pick.kelly_fraction, kelly, d.pick.dk_odds), 0);
    return total > rg.exposureCapUnits ? { total, cap: rg.exposureCapUnits } : null;
  }, [allData, rg.exposureCapUnits, kelly]);

  // Signals / Live views: exposure of the recommended stakes on screen.
  const signalExposure = useMemo(() => {
    if (view === 'today') return 0;
    return filtered.reduce((sum, d) => sum + unitsFor(d.pick.kelly_fraction, kelly, d.pick.dk_odds), 0);
  }, [filtered, view, kelly]);

  const busy = view === 'live' ? liveLoading : loading;
  const stakedSuffix = signalExposure > 0 ? ` · ${formatUnits(signalExposure)} staked` : '';
  const subtitle =
    view === 'today'
      ? `${date} · ${todayStats.bet} bets · ${todayStats.total} scored`
      : view === 'live'
        ? `${date} · ${liveData.length} in play${stakedSuffix}`
        : `${date} · ${live.length} live${stakedSuffix}`;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Picks</Text>
          <InfoTooltip
            title="Today, Signals & Live"
            body={
              'Today = every pick the model scored today.\n\nSignals = picks that crossed the bet line and are still live right now.\n\nLive = in-play picks, priced at DraftKings while a game is running. This one only appears when a game is actually in play, so no tab sits empty waiting for one.\n\nPicks lock the first time they\'re scored each day (props at their first signal) and never change again after that — so a signal shown here won\'t flip to AVOID later. Open a pick to see how the DK line has moved since it locked.\n\nLines refresh hourly 6am–6pm ET, then every 10 minutes until 11pm. Live picks refresh every 30 seconds.'
            }
            accessibilityLabel="About Today, Signals and Live"
          />
          <View style={styles.headerRight}>
            <BetslipButton />
            <SettingsButton />
          </View>
        </View>
        <Text style={styles.subtitle}>{subtitle}</Text>
        <SportToggle
          available={sportsWithPicks}
          signalCounts={sportSignalCounts}
          liveSports={liveSports}
        />
        <View style={styles.subTabs}>
          <SubTabBtn label="Today" count={todayStats.total} active={view === 'today'} onPress={() => setView('today')} />
          <SubTabBtn label="Signals" count={live.length} active={view === 'signals'} onPress={() => setView('signals')} />
          {/* Conditional by design — see the file header. No live picks in this
              sport, no segment, so there is no empty slot to learn to ignore. */}
          {liveData.length > 0 ? (
            <SubTabBtn
              label="Live"
              count={liveData.length}
              active={view === 'live'}
              onPress={() => setView('live')}
              live
            />
          ) : null}
        </View>
      </View>

      {/* Live pricing caveats, and ONLY on the live segment. Both are
          load-bearing (CLAUDE.md §6): the feed serves one cached in-play
          snapshot for ~45s so a number here can be behind DK's own app, and the
          in-play model reads DK's line and the bet is placed there. Kept as one
          paragraph: "bet your sportsbook's number" beside "your sportsbook
          doesn't apply" contradicted itself (UX review). */}
      {view === 'live' ? (
        <View style={styles.liveNoteWrap}>
          <Text style={styles.liveNote}>
            Live picks are priced and placed at DraftKings only. Lines move fast and our
            feed refreshes about every 45s — bet the number DraftKings shows, and skip it
            if it has moved past the edge.
          </Text>
          <Text style={styles.liveNoteSub}>Updating every 30 seconds.</Text>
        </View>
      ) : null}

      {error || (view === 'live' && liveError) ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error ?? liveError}</Text>
        </View>
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
          <Ionicons name="alert-circle-outline" size={16} color={colors.med} />
          <Text style={styles.partialText} numberOfLines={3}>
            {partialSentence(partial)} <Text style={styles.partialLink}>Retry</Text>
          </Text>
        </Pressable>
      ) : null}

      {view === 'today' && exposure ? (
        <View style={styles.rgBanner}>
          <Ionicons name="hand-left-outline" size={16} color={colors.med} />
          <Text style={styles.rgBannerText}>
            Today’s picks ask for {formatUnits(exposure.total)} — over your{' '}
            {formatUnits(exposure.cap)} daily limit. Consider sizing
            down or sitting some out.
          </Text>
        </View>
      ) : null}

      {activeItems.length > 0 && !signalsLocked ? (
        <PickFilters
          state={filter}
          onChange={setFilter}
          sortKey={sortKey}
          onSortChange={setSortKey}
          search={search}
          onSearchChange={setSearch}
          totalShown={filtered.length}
          totalAll={activeItems.length}
          availableModelIds={availableModelIds}
          showSignals={view === 'today'}
          itemNoun={view === 'today' ? 'pick' : view === 'live' ? 'live pick' : 'signal'}
        />
      ) : null}

      {signalsLocked ? (
        <SignalLockCard
          count={live.length}
          onPress={() => navigation.navigate('Paywall')}
        />
      ) : (
      <FlatList
        data={sorted}
        keyExtractor={(item) => String(item.pick.pick_id)}
        renderItem={({ item }) => (
          <PickCard
            item={item}
            bankroll={bankroll}
            kelly={kelly}
            onPress={() => navigation.navigate('PickDetail', { pickId: item.pick.pick_id })}
            tracked={tracked.isTracked(item.pick)}
            onToggleTrack={() => tracked.toggle(item.pick)}
            inSlip={slip.has(slipKeyForPick(item.pick))}
            onToggleSlip={() => slip.toggle(slipKeyForPick(item.pick))}
            liveState={liveStates.get(item.pick.game_id) ?? null}
          />
        )}
        ListEmptyComponent={
          busy ? (
            <View style={styles.loadingWrap}>
              <ActivityIndicator />
            </View>
          ) : (
            <EmptyForView view={view} sport={sport} date={date} hasAny={activeItems.length > 0} />
          )
        }
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={busy}
            onRefresh={() => {
              // Pull-to-refresh on the live segment must hit the live fetch —
              // refreshing today's board there would spin and change nothing.
              void (view === 'live' ? refreshLive() : refresh());
            }}
          />
        }
      />
      )}
    </SafeAreaView>
  );
}

function EmptyForView({
  view,
  sport,
  date,
  hasAny,
}: {
  view: PicksView;
  sport: string;
  date: string;
  hasAny: boolean;
}) {
  if (hasAny) {
    return (
      <EmptyState
        title="No picks match your filter"
        subtitle="Try widening signals, categories, or lowering the thresholds."
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
        title="No live signal bets"
        subtitle="Zero picks is a valid signal — no high-conviction plays right now. Check Today to see everything the model scored, or check back after the next refresh."
      />
    );
  }
  if (view === 'live') {
    // Reachable only in the instant between the last live game ending and the
    // effect that moves the user back to Today — the segment does not render
    // without picks behind it. Written out rather than inherited, because the
    // Signals copy ("check back after the next refresh") is wrong here: nothing
    // is coming back until a game is in play.
    return (
      <EmptyState
        title={`No ${sport} picks in play`}
        subtitle="The last in-play game finished. Live picks appear here while a game is running and an in-play model finds an edge — zero live picks is a valid signal."
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
}: {
  label: string;
  count: number;
  active: boolean;
  onPress: () => void;
  /** Draws the app's live dot ahead of the label. */
  live?: boolean;
}) {
  const noun = label === 'Today' ? 'picks' : live ? 'picks in play' : 'signals';
  return (
    <Pressable
      onPress={onPress}
      hitSlop={{ top: 8, bottom: 8 }}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      accessibilityLabel={`${label}, ${count} ${noun}`}
      style={({ pressed }) => [styles.subTab, active && styles.subTabActive, pressed && styles.pressed]}
    >
      <View style={styles.subTabInner}>
        {live ? <View style={styles.subTabLiveDot} /> : null}
        <Text style={[styles.subTabText, active && styles.subTabTextActive]}>
          {label} ({count})
        </Text>
      </View>
    </Pressable>
  );
}

/** "Couldn’t load today’s lines, the line shop and the prop line shop —
 *  statement timeout (57014). Today’s picks are unaffected." One sentence,
 *  one reason, for the partial-load banner. */
export function partialSentence(p: { whats: string[]; reason: string }): string {
  const w = p.whats;
  const list = w.length <= 1 ? w.join('') : `${w.slice(0, -1).join(', ')} and ${w[w.length - 1]}`;
  return `Couldn’t load ${list} — ${p.reason}. Today’s picks are unaffected.`;
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
    gap: 5,
  },
  // The app's one live mark — same 6pt red dot as GameStatusPill's LIVE pill
  // and the sport chips.
  subTabLiveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.avoid,
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
  list: {
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
  },
  loadingWrap: {
    paddingVertical: spacing.xxl,
    alignItems: 'center',
  },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: 8,
  },
  errorText: {
    color: colors.avoid,
    fontSize: font.size.footnote,
  },
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
  rgBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: '#FFF4E5',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: 8,
  },
  liveNoteWrap: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  // colors.med is the amber the confidence tiers already use — a caution, not
  // an error, so it must not read like the red error banner below it.
  liveNote: {
    color: colors.med,
    fontSize: font.size.footnote,
  },
  liveNoteSub: {
    color: colors.textTertiary,
    fontSize: font.size.footnote,
    marginTop: 2,
  },
  rgBannerText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.med,
    fontWeight: font.weight.medium,
  },
});

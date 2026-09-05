/**
 * Merged Picks tab — a single home for the daily board with a
 * `Today | Signals` segmented control. Replaces the old separate
 * Picks and Signals tabs (which both showed BET picks and read as redundant):
 *   - Today    = every scored pick today (the old Picks tab).
 *   - Signals  = picks that crossed the bet line and are still live.
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
import { useNavigation } from '@react-navigation/native';
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
import type { EnrichedPick, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type View2 = 'today' | 'signals';

export function PicksHomeScreen() {
  const navigation = useNavigation<Nav>();
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

  const [view, setView] = useState<View2>('today');
  const [filter, setFilter] = useState<PicksFilterState>(freshFilter);
  const [sortKey, setSortKey] = useState<SortKey>('edge');
  const [search, setSearch] = useState('');

  // MLB and WNBA share no model_ids — a stale filter would show "0 of N" after a
  // sport switch. Reset filter/search/view on sport change.
  useEffect(() => {
    setFilter(freshFilter());
    setSearch('');
    setView('today');
  }, [sport]);

  const todayData = useMemo(
    () => allData.filter((d) => d.pick.sport === sport),
    [allData, sport],
  );
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

  const activeItems: EnrichedPick[] = view === 'today' ? todayData : live;

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

  // Signals view: exposure of the live recommended stakes.
  const signalExposure = useMemo(() => {
    if (view !== 'signals') return 0;
    return filtered.reduce((sum, d) => sum + unitsFor(d.pick.kelly_fraction, kelly, d.pick.dk_odds), 0);
  }, [filtered, view, kelly]);

  const busy = loading;
  const subtitle =
    view === 'today'
      ? `${date} · ${todayStats.bet} bets · ${todayStats.total} scored`
      : `${date} · ${live.length} live${
          signalExposure > 0 ? ` · ${formatUnits(signalExposure)} staked` : ''
        }`;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Picks</Text>
          <InfoTooltip
            title="Today & Signals"
            body={
              'Today = every pick the model scored today.\n\nSignals = picks that crossed the bet line and are still live right now.\n\nPicks lock the first time they\'re scored each day (props at their first signal) and never change again after that — so a signal shown here won\'t flip to AVOID later. Open a pick to see how the DK line has moved since it locked.\n\nLines refresh hourly 6am–6pm ET, then every 10 minutes until 11pm.'
            }
            accessibilityLabel="About Today and Signals"
          />
          <View style={styles.headerRight}>
            <BetslipButton />
            <SettingsButton />
          </View>
        </View>
        <Text style={styles.subtitle}>{subtitle}</Text>
        <SportToggle available={sportsWithPicks} signalCounts={sportSignalCounts} />
        <View style={styles.subTabs}>
          <SubTabBtn label="Today" count={todayStats.total} active={view === 'today'} onPress={() => setView('today')} />
          <SubTabBtn label="Signals" count={live.length} active={view === 'signals'} onPress={() => setView('signals')} />
        </View>
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
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
          itemNoun={view === 'today' ? 'pick' : 'signal'}
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
              void refresh();
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
  view: View2;
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
}: {
  label: string;
  count: number;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={{ top: 8, bottom: 8 }}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      accessibilityLabel={`${label}, ${count} ${label === 'Today' ? 'picks' : 'signals'}`}
      style={({ pressed }) => [styles.subTab, active && styles.subTabActive, pressed && styles.pressed]}
    >
      <Text style={[styles.subTabText, active && styles.subTabTextActive]}>
        {label} ({count})
      </Text>
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
  rgBannerText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.med,
    fontWeight: font.weight.medium,
  },
});

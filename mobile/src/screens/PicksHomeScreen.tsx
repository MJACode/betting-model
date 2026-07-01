/**
 * Merged Picks tab — a single home for the daily board with a
 * `Today | Signals | Dropped` segmented control. Replaces the old separate
 * Picks and Signals tabs (which both showed BET picks and read as redundant):
 *   - Today    = every scored pick today (the old Picks tab).
 *   - Signals  = picks that crossed the bet line and are still live.
 *   - Movement = live signals annotated with how the DK line has moved since we
 *                locked them (picks lock now, so they no longer drop).
 *
 * Reuses the shared filter/sort/search pipeline (QuickFilters + PicksFilterBar +
 * applyFilter/sortPicks/searchPicks), the signal bucketing (bucketSignals), and
 * the same PickCard list — so the only per-view difference is the data source.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { PickCard } from '@/components/PickCard';
import { DroppedSignalStrip } from '@/components/DroppedSignalStrip';
import { EmptyState } from '@/components/EmptyState';
import { InfoTooltip } from '@/components/InfoTooltip';
import { QuickFilters } from '@/components/QuickFilters';
import {
  applyFilter,
  DEFAULT_FILTER,
  PicksFilterBar,
  type PicksFilterState,
} from '@/components/PicksFilterBar';
import { SportToggle } from '@/components/SportToggle';
import { SettingsButton } from '@/components/SettingsButton';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useOpeningSignals } from '@/hooks/useOpeningSignals';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useTrackedBets } from '@/hooks/useTrackedBets';
import { useResponsibleGambling } from '@/hooks/useResponsibleGambling';
import { bucketSignals, type DroppedSignal } from '@/lib/signalBoard';
import { movedSignals, movementTally } from '@/lib/lineMovementBoard';
import { sortPicks, searchPicks, type SortKey } from '@/lib/pickSort';
import { colors, font, radii, spacing } from '@/lib/theme';
import { passesActionFilter, recommendedBet } from '@/lib/thresholds';
import { formatCurrency, formatPct } from '@/lib/format';
import type { EnrichedPick, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type View3 = 'today' | 'signals' | 'movement';

function freshDefaultFilter(): PicksFilterState {
  return {
    signals: new Set(DEFAULT_FILTER.signals),
    categories: new Set(DEFAULT_FILTER.categories),
    modelIds: new Set<string>(),
    minProb: null,
    minEdge: null,
    minEV: null,
  };
}

function isDropped(item: EnrichedPick | DroppedSignal): item is DroppedSignal {
  return 'droppedReason' in item;
}

export function PicksHomeScreen() {
  const navigation = useNavigation<Nav>();
  const { data: allData, loading, error, refresh, date } = useTodayPicks();
  const opening = useOpeningSignals(date);
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const tracked = useTrackedBets();
  const { settings: rg } = useResponsibleGambling();

  const [view, setView] = useState<View3>('today');
  const [filter, setFilter] = useState<PicksFilterState>(freshDefaultFilter);
  const [sortKey, setSortKey] = useState<SortKey>('edge');
  const [search, setSearch] = useState('');

  // MLB and WNBA share no model_ids — a stale filter would show "0 of N" after a
  // sport switch. Reset filter/search/view on sport change.
  useEffect(() => {
    setFilter(freshDefaultFilter());
    setSearch('');
    setView('today');
  }, [sport]);

  const todayData = useMemo(
    () => allData.filter((d) => d.pick.sport === sport),
    [allData, sport],
  );
  const { live } = useMemo(
    () => bucketSignals(allData, opening.rows, opening.gameById, sport),
    [allData, opening.rows, opening.gameById, sport],
  );
  // Now that picks lock, the third view tracks LINE MOVEMENT since lock (not drops).
  const moved = useMemo(() => movedSignals(live), [live]);
  const tally = useMemo(() => movementTally(moved), [moved]);

  const activeItems: (EnrichedPick | DroppedSignal)[] =
    view === 'today' ? todayData : view === 'signals' ? live : moved;

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
    const bet = todayData.filter((d) => passesActionFilter(d.pick)).length;
    return { total: todayData.length, bet };
  }, [todayData]);

  const exposure = useMemo(() => {
    if (rg.exposureCapPct == null || bankroll <= 0) return null;
    const total = allData
      .filter((d) => passesActionFilter(d.pick))
      .reduce((s, d) => s + recommendedBet(d.pick.kelly_fraction, bankroll, kelly), 0);
    const capDollars = rg.exposureCapPct * bankroll;
    return total > capDollars ? { total, cap: capDollars } : null;
  }, [allData, rg.exposureCapPct, bankroll, kelly]);

  // Signals view: exposure of the live recommended stakes.
  const signalExposure = useMemo(() => {
    if (view !== 'signals') return 0;
    return filtered.reduce(
      (sum, d) => sum + recommendedBet(d.pick.kelly_fraction, bankroll, kelly),
      0,
    );
  }, [filtered, view, bankroll, kelly]);

  const busy = loading || opening.loading;
  const subtitle =
    view === 'today'
      ? `${date} · ${todayStats.bet} bets · ${todayStats.total} scored`
      : view === 'signals'
        ? `${date} · ${live.length} live${
            signalExposure > 0
              ? ` · ${formatCurrency(signalExposure)} (${formatPct(bankroll > 0 ? signalExposure / bankroll : 0)})`
              : ''
          }`
        : `${date} · ${tally.toward} toward · ${tally.against} against`;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Picks</Text>
          <InfoTooltip
            title="Today, Signals & Movement"
            body={
              'Today = every pick the model scored today.\n\nSignals = picks that crossed the bet line and are still live right now.\n\nMovement = your live signals, showing how the DK line has moved since we locked your number. "Toward" means the market came to your side (you beat the close); "against" means it moved away. Picks lock at 6am (props at their first signal), so they no longer drop — we just keep watching the line for you.\n\nLines refresh hourly 6am–6pm ET, then every 10 minutes until 11pm.'
            }
            accessibilityLabel="About Today, Signals and Movement"
          />
          <View style={styles.headerRight}>
            <SettingsButton />
          </View>
        </View>
        <Text style={styles.subtitle}>{subtitle}</Text>
        <SportToggle />
        <View style={styles.subTabs}>
          <SubTabBtn label="Today" count={todayStats.total} active={view === 'today'} onPress={() => setView('today')} />
          <SubTabBtn label="Signals" count={live.length} active={view === 'signals'} onPress={() => setView('signals')} />
          <SubTabBtn label="Movement" count={moved.length} active={view === 'movement'} onPress={() => setView('movement')} />
        </View>
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}

      {view === 'today' && exposure ? (
        <View style={styles.rgBanner}>
          <Ionicons name="hand-left-outline" size={16} color={colors.med} />
          <Text style={styles.rgBannerText}>
            Today’s picks ask for {formatCurrency(exposure.total)} — over your{' '}
            {formatPct(rg.exposureCapPct)} limit ({formatCurrency(exposure.cap)}). Consider sizing
            down or sitting some out.
          </Text>
        </View>
      ) : null}

      {activeItems.length > 0 ? (
        <>
          <QuickFilters
            filter={filter}
            onFilterChange={setFilter}
            sortKey={sortKey}
            onSortChange={setSortKey}
            search={search}
            onSearchChange={setSearch}
            showSignalChip={view === 'today'}
          />
          <PicksFilterBar
            state={filter}
            onChange={setFilter}
            totalShown={filtered.length}
            totalAll={activeItems.length}
            availableModelIds={availableModelIds}
            showSignals={view === 'today'}
            itemNoun={view === 'today' ? 'pick' : 'signal'}
          />
        </>
      ) : null}

      <FlatList
        data={sorted}
        keyExtractor={(item) => String(item.pick.pick_id)}
        renderItem={({ item }) => {
          if (isDropped(item)) {
            const canOpen = item.pick.pick_id > 0;
            return (
              <View>
                <DroppedSignalStrip reason={item.droppedReason} opening={item.opening} />
                <PickCard
                  item={item}
                  bankroll={bankroll}
                  kelly={kelly}
                  onPress={() => {
                    if (canOpen) navigation.navigate('PickDetail', { pickId: item.pick.pick_id });
                  }}
                />
              </View>
            );
          }
          return (
            <PickCard
              item={item}
              bankroll={bankroll}
              kelly={kelly}
              onPress={() => navigation.navigate('PickDetail', { pickId: item.pick.pick_id })}
              tracked={tracked.isTracked(item.pick.pick_id)}
              onToggleTrack={() => tracked.toggle(item.pick)}
            />
          );
        }}
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
              void opening.refresh();
            }}
          />
        }
      />
    </SafeAreaView>
  );
}

function EmptyForView({
  view,
  sport,
  date,
  hasAny,
}: {
  view: View3;
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
        subtitle="Zero picks is a valid signal — no high-conviction plays right now. Check Movement to see how lines are moving, or check back after the next refresh."
      />
    );
  }
  return (
    <EmptyState
      title="No line movement yet"
      subtitle="Your locked signals haven't moved much since we locked them. As the DK line moves toward or against your number, those signals collect here."
    />
  );
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
      style={({ pressed }) => [styles.subTab, active && styles.subTabActive, pressed && styles.pressed]}
    >
      <Text style={[styles.subTabText, active && styles.subTabTextActive]}>
        {label} ({count})
      </Text>
    </Pressable>
  );
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
  headerRight: { marginLeft: 'auto' },
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
    paddingVertical: spacing.xs,
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

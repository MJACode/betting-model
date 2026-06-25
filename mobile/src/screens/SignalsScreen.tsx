import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { PickCard } from '@/components/PickCard';
import { DroppedSignalStrip } from '@/components/DroppedSignalStrip';
import { EmptyState } from '@/components/EmptyState';
import { InfoTooltip } from '@/components/InfoTooltip';
import {
  applyFilter,
  DEFAULT_FILTER,
  PicksFilterBar,
  type PicksFilterState,
} from '@/components/PicksFilterBar';
import { QuickFilters } from '@/components/QuickFilters';
import { SportToggle } from '@/components/SportToggle';
import { sortPicks, searchPicks, type SortKey } from '@/lib/pickSort';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useOpeningSignals } from '@/hooks/useOpeningSignals';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { bucketSignals, type DroppedSignal } from '@/lib/signalBoard';
import { colors, font, radii, spacing } from '@/lib/theme';
import { passesActionFilter, recommendedBet } from '@/lib/thresholds';
import { formatCurrency, formatPct } from '@/lib/format';
import type { EnrichedPick, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type SubTab = 'live' | 'dropped';

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

export function SignalsScreen() {
  const navigation = useNavigation<Nav>();
  const { data, loading, error, refresh, date } = useTodayPicks();
  const opening = useOpeningSignals(date);
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const slip = useParlaySlip();
  const [tab, setTab] = useState<SubTab>('live');
  const [filter, setFilter] = useState<PicksFilterState>(freshDefaultFilter);
  const [sortKey, setSortKey] = useState<SortKey>('edge');
  const [search, setSearch] = useState('');

  // MLB and WNBA share no model_ids — a stale filter would silently show
  // "0 of N" after a sport switch. Reset filter + tab when sport changes.
  useEffect(() => {
    setFilter(freshDefaultFilter());
    setSearch('');
    setTab('live');
  }, [sport]);

  // Live = currently a displayed signal. Dropped = locked as a signal earlier
  // today but no longer live (flipped to Avoid / weakened / no-signal / pulled).
  const { live, dropped } = useMemo(
    () => bucketSignals(data, opening.rows, opening.gameById, sport),
    [data, opening.rows, opening.gameById, sport],
  );

  const activeBucket: (EnrichedPick | DroppedSignal)[] = tab === 'live' ? live : dropped;

  // Filter options track what's actually on screen for the active sub-tab.
  const availableModelIds = useMemo(
    () => Array.from(new Set(activeBucket.map((d) => d.pick.model_id))),
    [activeBucket],
  );

  const filtered = useMemo(
    () => searchPicks(applyFilter(activeBucket, filter), search),
    [activeBucket, filter, search],
  );

  const sorted = useMemo(() => sortPicks(filtered, sortKey), [filtered, sortKey]);

  // Exposure only applies to the Live tab (dropped picks aren't actionable bets).
  const exposure = useMemo(() => {
    if (tab !== 'live') return 0;
    return filtered.reduce(
      (sum, d) => sum + recommendedBet(d.pick.kelly_fraction, bankroll, kelly),
      0,
    );
  }, [filtered, tab, bankroll, kelly]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Signal Bets</Text>
          <InfoTooltip
            title="Signals are locked, then tracked"
            body={
              "A signal is locked the first time a model crosses its bet threshold today, and never disappears.\n\nLive = still a recommended bet right now. Dropped = it fired earlier but the line has since moved against it (flipped to Avoid, weakened below the threshold, or pulled off the board).\n\nLines refresh at 7am, then hourly from 11am to 11pm ET. Waiting until closer to game time means fewer signals flip."
            }
            accessibilityLabel="About signal bets"
          />
        </View>
        <Text style={styles.subtitle}>
          {date} · {live.length} live · {dropped.length} dropped
          {tab === 'live' && exposure > 0
            ? ` · Exposure ${formatCurrency(exposure)} (${formatPct(bankroll > 0 ? exposure / bankroll : 0)})`
            : ''}
        </Text>
        <SportToggle />
        <View style={styles.subTabs}>
          <SubTabBtn label="Live" count={live.length} active={tab === 'live'} onPress={() => setTab('live')} />
          <SubTabBtn label="Dropped" count={dropped.length} active={tab === 'dropped'} onPress={() => setTab('dropped')} />
        </View>
      </View>
      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}
      {activeBucket.length > 0 ? (
        <>
          <QuickFilters
            filter={filter}
            onFilterChange={setFilter}
            sortKey={sortKey}
            onSortChange={setSortKey}
            search={search}
            onSearchChange={setSearch}
            showSignalChip={false}
          />
          <PicksFilterBar
            state={filter}
            onChange={setFilter}
            totalShown={filtered.length}
            totalAll={activeBucket.length}
            availableModelIds={availableModelIds}
            showSignals={false}
            itemNoun="signal"
          />
        </>
      ) : null}
      <FlatList
        data={sorted}
        keyExtractor={(item) => String(item.pick.pick_id)}
        renderItem={({ item }) => {
          if (isDropped(item)) {
            // off-the-board cards (no live pick) carry a synthetic negative id —
            // there's no detail screen to open.
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
              inPlay={slip.has(item.pick.pick_id)}
              onTogglePlay={() => slip.toggle(item.pick.pick_id)}
            />
          );
        }}
        ListEmptyComponent={
          loading || opening.loading ? (
            <View style={styles.loadingWrap}>
              <ActivityIndicator />
            </View>
          ) : tab === 'live' ? (
            <EmptyState
              title="No live signal bets"
              subtitle="Zero picks is a valid signal — no high-conviction plays right now. Check the Dropped tab to see what's moved, or check back after the next refresh."
            />
          ) : (
            <EmptyState
              title="Nothing has dropped yet today"
              subtitle="Every signal that fired today is still live. As lines move, signals that fall off will collect here."
            />
          )
        }
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={loading || opening.loading}
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
      style={({ pressed }) => [
        styles.subTab,
        active && styles.subTabActive,
        pressed && styles.pressed,
      ]}
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
    paddingHorizontal: spacing.lg,
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
});

import React, { useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { PickCard } from '@/components/PickCard';
import { EmptyState } from '@/components/EmptyState';
import {
  applyFilter,
  DEFAULT_FILTER,
  PicksFilterBar,
  type PicksFilterState,
} from '@/components/PicksFilterBar';
import { SportToggle } from '@/components/SportToggle';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { colors, font, spacing } from '@/lib/theme';
import { passesActionFilter } from '@/lib/thresholds';
import type { EnrichedPick, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

function freshDefaultFilter(): PicksFilterState {
  return {
    signals: new Set(DEFAULT_FILTER.signals),
    categories: new Set(DEFAULT_FILTER.categories),
    modelIds: new Set<string>(),
    minProb: null,
    minEdge: null,
  };
}

export function PicksScreen() {
  const navigation = useNavigation<Nav>();
  const { data: allData, loading, error, refresh, date } = useTodayPicks();
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const [filter, setFilter] = useState<PicksFilterState>(freshDefaultFilter);

  // Show only the selected sport — WNBA picks stay separate from MLB.
  const data = useMemo(() => allData.filter((d) => d.pick.sport === sport), [allData, sport]);
  const filtered = useMemo(() => applyFilter(data, filter), [data, filter]);

  const stats = useMemo(() => {
    const bet = filtered.filter((d) => passesActionFilter(d.pick)).length;
    const avoid = filtered.filter((d) => d.pick.signal_type === 'AVOID').length;
    const none = filtered.filter((d) => d.pick.signal_type === 'NONE').length;
    return { total: filtered.length, bet, avoid, none };
  }, [filtered]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const ta = a.game?.commence_time ?? '';
      const tb = b.game?.commence_time ?? '';
      if (ta !== tb) return ta.localeCompare(tb);
      return b.pick.edge - a.pick.edge;
    });
  }, [filtered]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Today's Picks</Text>
        <Text style={styles.subtitle}>
          {date} · {stats.bet} BET · {stats.avoid} AVOID · {stats.none} NONE
        </Text>
        <Text style={styles.scheduleNote}>
          Betting lines refresh every hour from 8am to 11pm ET.
        </Text>
        <SportToggle />
      </View>
      {error ? <ErrorBanner message={error} /> : null}
      <PicksFilterBar
        state={filter}
        onChange={setFilter}
        totalShown={filtered.length}
        totalAll={data.length}
      />
      <FlatList
        data={sorted}
        keyExtractor={(item) => String(item.pick.pick_id)}
        renderItem={({ item }) => (
          <PickCard
            item={item}
            bankroll={bankroll}
            kelly={kelly}
            onPress={() => navigation.navigate('PickDetail', { pickId: item.pick.pick_id })}
          />
        )}
        ListEmptyComponent={
          loading ? (
            <View style={styles.loadingWrap}>
              <ActivityIndicator />
            </View>
          ) : data.length === 0 ? (
            <EmptyState
              title={`No ${sport} picks today`}
              subtitle={`No ${sport} picks have been scored for ${date} yet. Lines refresh hourly 8am–11pm ET.`}
            />
          ) : (
            <EmptyState
              title="No picks match your filter"
              subtitle="Try widening signals, categories, or lowering the thresholds."
            />
          )
        }
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
      />
    </SafeAreaView>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <View style={styles.errorBanner}>
      <Text style={styles.errorText}>Connection error: {message}</Text>
    </View>
  );
}

export function todayPicksList(items: EnrichedPick[], filter?: (i: EnrichedPick) => boolean): EnrichedPick[] {
  return filter ? items.filter(filter) : items;
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
  scheduleNote: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
    fontStyle: 'italic',
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

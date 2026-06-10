import React, { useEffect, useMemo, useState } from 'react';
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
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { colors, font, spacing } from '@/lib/theme';
import { passesActionFilter, recommendedBet } from '@/lib/thresholds';
import { formatCurrency, formatPct } from '@/lib/format';
import type { RootStackParamList } from '@/types';

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

export function SignalsScreen() {
  const navigation = useNavigation<Nav>();
  const { data, loading, error, refresh, date } = useTodayPicks();
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const slip = useParlaySlip();
  const [filter, setFilter] = useState<PicksFilterState>(freshDefaultFilter);

  // MLB and WNBA share no model_ids — a stale selection would silently show
  // "0 of N" after a sport switch, so reset the filter when sport changes.
  useEffect(() => {
    setFilter(freshDefaultFilter());
  }, [sport]);

  // All qualifying signals for this sport — the universe the filter narrows.
  const base = useMemo(
    () => data.filter((d) => d.pick.sport === sport && passesActionFilter(d.pick)),
    [data, sport],
  );

  // Filter options track what's actually on screen (dynamic).
  const availableModelIds = useMemo(
    () => Array.from(new Set(base.map((d) => d.pick.model_id))),
    [base],
  );

  const filtered = useMemo(() => applyFilter(base, filter), [base, filter]);

  const sorted = useMemo(
    () => [...filtered].sort((a, b) => b.pick.edge - a.pick.edge),
    [filtered],
  );

  const totals = useMemo(() => {
    const totalBet = filtered.reduce(
      (sum, d) => sum + recommendedBet(d.pick.kelly_fraction, bankroll, kelly),
      0,
    );
    return {
      count: filtered.length,
      totalBet,
      pctOfRoll: bankroll > 0 ? totalBet / bankroll : 0,
    };
  }, [filtered, bankroll, kelly]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Signal Bets</Text>
        <Text style={styles.subtitle}>
          {date} · {totals.count} signal{totals.count === 1 ? '' : 's'} · Exposure {formatCurrency(totals.totalBet)} ({formatPct(totals.pctOfRoll)})
        </Text>
        <SportToggle />
      </View>
      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}
      {base.length > 0 ? (
        <PicksFilterBar
          state={filter}
          onChange={setFilter}
          totalShown={filtered.length}
          totalAll={base.length}
          availableModelIds={availableModelIds}
          showSignals={false}
          itemNoun="signal"
        />
      ) : null}
      <FlatList
        data={sorted}
        keyExtractor={(item) => String(item.pick.pick_id)}
        renderItem={({ item }) => (
          <PickCard
            item={item}
            bankroll={bankroll}
            kelly={kelly}
            onPress={() => navigation.navigate('PickDetail', { pickId: item.pick.pick_id })}
            inPlay={slip.has(item.pick.pick_id)}
            onTogglePlay={() => slip.toggle(item.pick.pick_id)}
          />
        )}
        ListEmptyComponent={
          loading ? (
            <View style={styles.loadingWrap}>
              <ActivityIndicator />
            </View>
          ) : base.length === 0 ? (
            <EmptyState
              title="No signal bets today"
              subtitle="Zero picks is a valid signal — no high-conviction plays right now. Check back after the next refresh."
            />
          ) : (
            <EmptyState
              title="No signals match your filter"
              subtitle="Try lowering the edge or model % thresholds, or widening the model selection."
            />
          )
        }
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
      />
    </SafeAreaView>
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

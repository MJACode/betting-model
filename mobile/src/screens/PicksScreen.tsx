import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
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
import { useResponsibleGambling } from '@/hooks/useResponsibleGambling';
import { colors, font, spacing } from '@/lib/theme';
import { passesActionFilter, recommendedBet } from '@/lib/thresholds';
import { formatCurrency, formatPct } from '@/lib/format';
import type { EnrichedPick, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

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

export function PicksScreen() {
  const navigation = useNavigation<Nav>();
  const { data: allData, loading, error, refresh, date } = useTodayPicks();
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const slip = useParlaySlip();
  const { settings: rg } = useResponsibleGambling();
  const [filter, setFilter] = useState<PicksFilterState>(freshDefaultFilter);

  // Daily exposure guardrail: total recommended stake across ALL of today's BET
  // picks (every sport), compared to the user's opt-in cap.
  const exposure = useMemo(() => {
    if (rg.exposureCapPct == null || bankroll <= 0) return null;
    const total = allData
      .filter((d) => passesActionFilter(d.pick))
      .reduce((s, d) => s + recommendedBet(d.pick.kelly_fraction, bankroll, kelly), 0);
    const cap = rg.exposureCapPct * bankroll;
    return total > cap ? { total, cap } : null;
  }, [allData, rg.exposureCapPct, bankroll, kelly]);

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
          Lines refresh at 7am, then hourly from 11am to 11pm ET.
        </Text>
        <Pressable
          onPress={() => navigation.navigate('TrackRecord')}
          style={({ pressed }) => [styles.trackLink, pressed && styles.trackLinkPressed]}
        >
          <Ionicons name="shield-checkmark-outline" size={15} color={colors.tint} />
          <Text style={styles.trackLinkText}>See our verified track record — every pick, win or lose</Text>
          <Ionicons name="chevron-forward" size={14} color={colors.tint} />
        </Pressable>
        <SportToggle />
      </View>
      {error ? <ErrorBanner message={error} /> : null}
      {exposure ? (
        <View style={styles.rgBanner}>
          <Ionicons name="hand-left-outline" size={16} color={colors.med} />
          <Text style={styles.rgBannerText}>
            Today’s picks ask for {formatCurrency(exposure.total)} — over your{' '}
            {formatPct(rg.exposureCapPct)} limit ({formatCurrency(exposure.cap)}). Consider sizing
            down or sitting some out.
          </Text>
        </View>
      ) : null}
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
            inPlay={slip.has(item.pick.pick_id)}
            onTogglePlay={() => slip.toggle(item.pick.pick_id)}
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
  trackLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  trackLinkText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  trackLinkPressed: {
    opacity: 0.6,
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
  errorText: {
    color: colors.avoid,
    fontSize: font.size.footnote,
  },
});

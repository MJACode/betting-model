import React, { useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { ModelBreakdown } from '@/components/ModelBreakdown';
import { PerformanceCalendar } from '@/components/PerformanceCalendar';
import { StatTile } from '@/components/StatTile';
import { EmptyState } from '@/components/EmptyState';
import { useBankroll } from '@/hooks/useBankroll';
import { type Range, type SizingMode, usePerformance } from '@/hooks/usePerformance';
import { formatCurrencySigned, formatPctSigned, todayET } from '@/lib/format';
import { modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

const RANGES: Array<{ key: Range; label: string }> = [
  { key: '7d', label: '7d' },
  { key: '30d', label: '30d' },
  { key: '90d', label: '90d' },
  { key: 'season', label: 'Season' },
  { key: 'all', label: 'All' },
];

export function PerformanceScreen() {
  const navigation = useNavigation<Nav>();
  const [range, setRange] = useState<Range>('30d');
  const [mode, setMode] = useState<SizingMode>('kelly');
  const { summary, loading, error, refresh } = usePerformance(range);
  const { bankroll } = useBankroll();

  const today = todayET();
  const [calYear, setCalYear] = useState<number>(parseInt(today.slice(0, 4), 10));
  const [calMonth, setCalMonth] = useState<number>(parseInt(today.slice(5, 7), 10));

  const onNavigateMonth = (delta: number) => {
    let m = calMonth + delta;
    let y = calYear;
    if (m < 1) {
      m = 12;
      y -= 1;
    } else if (m > 12) {
      m = 1;
      y += 1;
    }
    setCalMonth(m);
    setCalYear(y);
  };

  const totalProfit = mode === 'kelly' ? summary.totalKelly : summary.totalFlat;
  const roi = mode === 'kelly' ? summary.roiKelly : summary.roiFlat;
  const totalTint = totalProfit > 0 ? colors.bet : totalProfit < 0 ? colors.avoid : colors.textPrimary;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
      >
        <View style={styles.header}>
          <Text style={styles.title}>Performance</Text>
          <Text style={styles.subtitle}>
            Picks you marked Placed · Bankroll ${bankroll.toFixed(0)}
          </Text>
        </View>

        {error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Connection error: {error}</Text>
          </View>
        ) : null}

        <View style={styles.headlineCard}>
          <Text style={styles.headlineLabel}>Total ROI ({mode === 'kelly' ? 'Kelly' : 'Flat'})</Text>
          <Text style={[styles.headlineRoi, { color: totalTint }]}>
            {formatPctSigned(roi)}
          </Text>
          <Text style={[styles.headlineDollars, { color: totalTint }]}>
            {formatCurrencySigned(totalProfit)}
          </Text>
          <View style={styles.modeToggle}>
            <Pressable
              onPress={() => setMode('kelly')}
              style={[styles.modePill, mode === 'kelly' && styles.modePillActive]}
            >
              <Text style={[styles.modePillText, mode === 'kelly' && styles.modePillTextActive]}>
                Kelly
              </Text>
            </Pressable>
            <Pressable
              onPress={() => setMode('flat')}
              style={[styles.modePill, mode === 'flat' && styles.modePillActive]}
            >
              <Text style={[styles.modePillText, mode === 'flat' && styles.modePillTextActive]}>
                Flat
              </Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.rangeRow}>
          {RANGES.map((r) => (
            <Pressable
              key={r.key}
              onPress={() => setRange(r.key)}
              style={[styles.rangeChip, range === r.key && styles.rangeChipActive]}
            >
              <Text style={[styles.rangeChipText, range === r.key && styles.rangeChipTextActive]}>
                {r.label}
              </Text>
            </Pressable>
          ))}
        </View>

        {loading && summary.totalPicks === 0 ? (
          <ActivityIndicator style={styles.loading} />
        ) : summary.totalPicks === 0 ? (
          <EmptyState
            title="No placed bets in this range"
            subtitle="Mark BET picks as Placed from their detail screen and they'll show up here once settled."
          />
        ) : (
          <>
            <PerformanceCalendar
              year={calYear}
              month={calMonth}
              byDay={summary.byDay}
              mode={mode}
              onSelectDay={(date) => navigation.navigate('DayDetail', { date })}
              onNavigate={onNavigateMonth}
            />

            <View style={styles.statRow}>
              <StatTile
                label="Win %"
                value={
                  summary.wins + summary.losses > 0
                    ? `${((summary.wins / (summary.wins + summary.losses)) * 100).toFixed(1)}%`
                    : '—'
                }
                caption="excludes pushes"
              />
              <StatTile
                label="Record"
                value={`${summary.wins}-${summary.losses}-${summary.pushes}`}
                caption="W–L–P"
              />
            </View>
            <View style={styles.statRow}>
              <StatTile
                label="Units"
                value={summary.units >= 0 ? `+${summary.units.toFixed(2)}u` : `${summary.units.toFixed(2)}u`}
                caption="flat (1u = $100)"
                tint={summary.units > 0 ? colors.bet : summary.units < 0 ? colors.avoid : undefined}
              />
              <StatTile
                label="Streak"
                value={
                  summary.streak.kind === 'none'
                    ? '—'
                    : `${summary.streak.count}${summary.streak.kind}`
                }
                caption={summary.streak.kind === 'W' ? 'on a heater' : summary.streak.kind === 'L' ? 'cold' : ''}
                tint={summary.streak.kind === 'W' ? colors.bet : summary.streak.kind === 'L' ? colors.avoid : undefined}
              />
            </View>
            <View style={styles.statRow}>
              <StatTile
                label="Avg Edge"
                value={formatPctSigned(summary.avgEdge)}
                caption="on placed bets"
              />
              <StatTile
                label="Best Model"
                value={summary.bestModel ? modelShort(summary.bestModel.model_id) : '—'}
                caption={
                  summary.bestModel
                    ? `${formatPctSigned(summary.bestModel.roi)} · ${summary.bestModel.picks} picks`
                    : '≥10 picks needed'
                }
              />
            </View>

            <ModelBreakdown byModel={summary.byModel} mode={mode} />
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  list: {
    paddingBottom: spacing.xl,
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
  headlineCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    alignItems: 'center',
  },
  headlineLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  headlineRoi: {
    fontSize: 48,
    fontWeight: font.weight.bold,
    marginTop: 4,
  },
  headlineDollars: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    marginTop: 2,
    marginBottom: spacing.md,
  },
  modeToggle: {
    flexDirection: 'row',
    backgroundColor: colors.bg,
    borderRadius: radii.pill,
    padding: 3,
  },
  modePill: {
    paddingHorizontal: spacing.lg,
    paddingVertical: 6,
    borderRadius: radii.pill,
  },
  modePillActive: {
    backgroundColor: colors.bgCard,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 2,
    shadowOffset: { width: 0, height: 1 },
  },
  modePillText: {
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
    fontSize: font.size.footnote,
  },
  modePillTextActive: {
    color: colors.textPrimary,
    fontWeight: font.weight.semibold,
  },
  rangeRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  rangeChip: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    alignItems: 'center',
  },
  rangeChipActive: {
    backgroundColor: colors.tint,
  },
  rangeChipText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  rangeChipTextActive: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
  },
  statRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    gap: spacing.md,
  },
  loading: {
    marginVertical: spacing.xxl,
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

import React from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { colors, font, radii, spacing } from '@/lib/theme';
import { formatCurrencySigned, formatPctSigned } from '@/lib/format';
import { modelLong, modelShort } from '@/lib/modelMeta';
import type { CustomModelStats } from '@/hooks/useCustomModelStats';
import type { DailyResults, ModelDayStats } from '@/lib/dailyResults';

/**
 * Daily recap: how every model did yesterday — a consolidated "All" record + ROI
 * plus a per-sport / per-model breakdown. Presentational; the host owns the data
 * (useYesterdayResults) and visibility (useDailyRecapControl).
 */
export function YesterdayResultsModal({
  visible,
  onClose,
  date,
  results,
  loading,
  error,
}: {
  visible: boolean;
  onClose: () => void;
  date: string;
  results: DailyResults;
  loading: boolean;
  error: string | null;
}) {
  const hasResults = results.overall.picks > 0;

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="fullScreen">
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={styles.title}>Yesterday's results</Text>
            <Text style={styles.subtitle}>{prettyDate(date)}</Text>
          </View>
          <Pressable onPress={onClose} hitSlop={12} style={styles.closeBtn}>
            <Ionicons name="close" size={22} color={colors.textSecondary} />
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator />
          </View>
        ) : error ? (
          <View style={styles.center}>
            <Text style={styles.error}>Couldn’t load yesterday’s results.</Text>
            <Text style={styles.errorDetail}>{error}</Text>
          </View>
        ) : !hasResults ? (
          <View style={styles.center}>
            <Ionicons name="moon-outline" size={40} color={colors.textTertiary} />
            <Text style={styles.emptyTitle}>No settled picks yesterday</Text>
            <Text style={styles.emptyBody}>
              An off day — nothing cleared the bar or no games settled. That’s a valid signal,
              not a miss.
            </Text>
          </View>
        ) : (
          <ScrollView contentContainerStyle={styles.list}>
            {/* Consolidated "All" hero */}
            <View style={styles.hero}>
              <Text style={styles.heroLabel}>All models — flat-bet ROI</Text>
              <Text style={[styles.heroRoi, { color: roiColor(results.overall.roiFlat) }]}>
                {formatPctSigned(results.overall.roiFlat)}
              </Text>
              <Text style={styles.heroRecord}>{recordLine(results.overall)}</Text>
              <View style={styles.heroStats}>
                <HeroStat label="Picks" value={String(results.overall.picks)} />
                <HeroStat
                  label="P&L (flat)"
                  value={formatCurrencySigned(results.overall.profitFlat)}
                  color={roiColor(results.overall.roiFlat)}
                />
                <HeroStat label="Win rate" value={formatPctSigned(results.overall.winRate).replace('+', '')} />
              </View>
            </View>

            {/* Per-sport breakdown */}
            {results.sports.map((s) => (
              <View key={s.sport} style={styles.sportCard}>
                <View style={styles.sportHeader}>
                  <Text style={styles.sportName}>{s.sport}</Text>
                  <Text style={[styles.sportRoi, { color: roiColor(s.total.roiFlat) }]}>
                    {formatPctSigned(s.total.roiFlat)}
                  </Text>
                </View>
                <Text style={styles.sportSub}>
                  {recordLine(s.total)} · {formatCurrencySigned(s.total.profitFlat)}
                </Text>
                {s.models.map((m) => (
                  <ModelRow key={m.modelId} model={m} />
                ))}
              </View>
            ))}

            <Text style={styles.footer}>
              Settled BET picks only, graded at the current thresholds. Flat ROI assumes a $100
              stake per pick.
            </Text>
          </ScrollView>
        )}
      </SafeAreaView>
    </Modal>
  );
}

function HeroStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.heroStat}>
      <Text style={[styles.heroStatValue, color ? { color } : null]}>{value}</Text>
      <Text style={styles.heroStatLabel}>{label}</Text>
    </View>
  );
}

function ModelRow({ model }: { model: ModelDayStats }) {
  return (
    <View style={styles.modelRow}>
      <View style={styles.modelLeft}>
        <View style={styles.chip}>
          <Text style={styles.chipText}>{modelShort(model.modelId)}</Text>
        </View>
        <View style={styles.modelNameWrap}>
          <Text style={styles.modelName} numberOfLines={1}>
            {modelLong(model.modelId)}
          </Text>
          <Text style={styles.modelSub}>
            {recordLine(model)} · {formatCurrencySigned(model.profitFlat)}
          </Text>
        </View>
      </View>
      <Text style={[styles.modelRoi, { color: roiColor(model.roiFlat) }]}>
        {formatPctSigned(model.roiFlat)}
      </Text>
    </View>
  );
}

function recordLine(s: CustomModelStats): string {
  const base = `${s.wins}–${s.losses}`;
  return s.pushes > 0 ? `${base}–${s.pushes}` : base;
}

function roiColor(roi: number): string {
  if (roi > 0.001) return colors.positive;
  if (roi < -0.001) return colors.negative;
  return colors.textSecondary;
}

function prettyDate(date: string): string {
  try {
    const d = new Date(`${date}T12:00:00Z`);
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'UTC',
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    }).format(d);
  } catch {
    return date;
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  headerText: { flex: 1 },
  title: {
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.noneSoft,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  error: { fontSize: font.size.callout, fontWeight: font.weight.semibold, color: colors.textPrimary },
  errorDetail: { fontSize: font.size.footnote, color: colors.textSecondary, textAlign: 'center' },
  emptyTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  emptyBody: {
    fontSize: font.size.callout,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  list: { padding: spacing.lg, paddingTop: spacing.xs, gap: spacing.md },

  hero: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    alignItems: 'center',
  },
  heroLabel: { fontSize: font.size.footnote, color: colors.textSecondary },
  heroRoi: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    marginTop: 2,
  },
  heroRecord: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: 2,
  },
  heroStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignSelf: 'stretch',
    marginTop: spacing.md,
  },
  heroStat: { alignItems: 'center' },
  heroStatValue: { fontSize: font.size.callout, fontWeight: font.weight.semibold, color: colors.textPrimary },
  heroStatLabel: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: 2 },

  sportCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.md,
  },
  sportHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sportName: { fontSize: font.size.headline, fontWeight: font.weight.bold, color: colors.textPrimary },
  sportRoi: { fontSize: font.size.headline, fontWeight: font.weight.bold },
  sportSub: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 2, marginBottom: spacing.sm },

  modelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  modelLeft: { flexDirection: 'row', alignItems: 'center', flex: 1, gap: spacing.sm },
  chip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
  },
  chipText: { fontSize: font.size.caption, fontWeight: font.weight.semibold, color: colors.textSecondary },
  modelNameWrap: { flex: 1 },
  modelName: { fontSize: font.size.body, fontWeight: font.weight.medium, color: colors.textPrimary },
  modelSub: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 1 },
  modelRoi: { fontSize: font.size.callout, fontWeight: font.weight.semibold, marginLeft: spacing.sm },

  footer: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 18,
  },
});

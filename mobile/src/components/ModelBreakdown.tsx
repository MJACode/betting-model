import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { ModelStats, SizingMode } from '@/hooks/usePerformance';
import { formatCurrencySigned, formatPctSigned } from '@/lib/format';
import { modelLong, modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  byModel: ModelStats[];
  mode: SizingMode;
}

export function ModelBreakdown({ byModel, mode }: Props) {
  const rows = byModel.filter((m) => m.picks > 0);
  if (rows.length === 0) return null;

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.heading}>By Model</Text>
        <Text style={styles.headerHint}>
          ROI · Record · P/L ({mode === 'kelly' ? 'Kelly' : 'Flat'})
        </Text>
      </View>
      {rows.map((m, idx) => (
        <ModelRow key={m.model_id} stats={m} mode={mode} isLast={idx === rows.length - 1} />
      ))}
    </View>
  );
}

function ModelRow({
  stats,
  mode,
  isLast,
}: {
  stats: ModelStats;
  mode: SizingMode;
  isLast: boolean;
}) {
  const roi = mode === 'kelly' ? stats.roiKelly : stats.roiFlat;
  const profit = mode === 'kelly' ? stats.profitKelly : stats.profitFlat;
  const decided = stats.wins + stats.losses;
  const winPct = decided > 0 ? stats.wins / decided : null;
  const roiColor = roi > 0 ? colors.bet : roi < 0 ? colors.avoid : colors.textSecondary;

  return (
    <View style={[styles.row, !isLast && styles.rowBorder]}>
      <View style={styles.modelCol}>
        <View style={styles.modelChip}>
          <Text style={styles.modelChipText}>{modelShort(stats.model_id)}</Text>
        </View>
        <View style={styles.modelMeta}>
          <Text style={styles.modelName} numberOfLines={1}>
            {modelLong(stats.model_id)}
          </Text>
          <Text style={styles.subtle}>
            {stats.picks} pick{stats.picks === 1 ? '' : 's'}
            {winPct != null ? ` · ${(winPct * 100).toFixed(0)}% win` : ''}
          </Text>
        </View>
      </View>

      <View style={styles.statsCol}>
        <Text style={[styles.roi, { color: roiColor }]}>{formatPctSigned(roi)}</Text>
        <View style={styles.recordRow}>
          <Text style={styles.record}>
            {stats.wins}-{stats.losses}
            {stats.pushes > 0 ? `-${stats.pushes}` : ''}
          </Text>
          <Text style={[styles.profit, { color: roiColor }]}>
            {formatCurrencySigned(profit)}
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    paddingVertical: spacing.sm,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  heading: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  headerHint: {
    fontSize: 10,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  row: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    gap: spacing.md,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  modelCol: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  modelChip: {
    backgroundColor: colors.noneSoft,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    minWidth: 44,
    alignItems: 'center',
  },
  modelChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  modelMeta: {
    flex: 1,
    flexShrink: 1,
  },
  modelName: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  subtle: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 1,
  },
  statsCol: {
    alignItems: 'flex-end',
    minWidth: 110,
  },
  roi: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
  },
  recordRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: 2,
  },
  record: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  profit: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
  },
});

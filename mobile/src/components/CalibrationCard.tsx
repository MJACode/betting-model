import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import {
  CAL_ERROR_GATE,
  type CalibrationBin,
  type ModelCalibration,
} from '@/hooks/usePerformance';
import { formatPct, formatPctSigned } from '@/lib/format';
import { modelLong, modelShort } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  calibration: ModelCalibration[];
}

export function CalibrationCard({ calibration }: Props) {
  const rows = calibration.filter((c) => c.decided > 0);
  if (rows.length === 0) return null;

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.heading}>Calibration</Text>
        <Text style={styles.headerHint}>Gate ≤ {Math.round(CAL_ERROR_GATE * 100)}%</Text>
      </View>
      <Text style={styles.caption}>
        How well predicted probability tracks actual win rate. Positive gap = model overconfident.
      </Text>
      {rows.map((c, idx) => (
        <CalibrationRow key={c.model_id} cal={c} isLast={idx === rows.length - 1} />
      ))}
    </View>
  );
}

function CalibrationRow({ cal, isLast }: { cal: ModelCalibration; isLast: boolean }) {
  const passes = cal.absGap <= CAL_ERROR_GATE;
  const gapColor =
    cal.absGap <= CAL_ERROR_GATE
      ? colors.bet
      : cal.absGap <= CAL_ERROR_GATE * 2
        ? colors.med
        : colors.avoid;
  const sampleWarning = cal.decided < 20;

  return (
    <View style={[styles.row, !isLast && styles.rowBorder]}>
      <View style={styles.topRow}>
        <View style={styles.modelMeta}>
          <View style={styles.modelChip}>
            <Text style={styles.modelChipText}>{modelShort(cal.model_id)}</Text>
          </View>
          <Text style={styles.modelName} numberOfLines={1}>
            {modelLong(cal.model_id)}
          </Text>
        </View>
        <Text style={styles.gateBadge}>{passes ? '✓' : '!'}</Text>
      </View>

      <View style={styles.metricRow}>
        <Metric label="Predicted" value={formatPct(cal.avgPredicted)} />
        <Metric label="Actual" value={formatPct(cal.actualWinRate)} />
        <Metric label="Gap" value={formatPctSigned(cal.gap)} color={gapColor} />
        <Metric
          label="Picks"
          value={`${cal.decided}`}
          caption={sampleWarning ? 'low sample' : undefined}
        />
      </View>

      {cal.bins.length > 1 ? <BinStrip bins={cal.bins} /> : null}
    </View>
  );
}

function Metric({
  label,
  value,
  color,
  caption,
}: {
  label: string;
  value: string;
  color?: string;
  caption?: string;
}) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, color ? { color } : null]}>{value}</Text>
      {caption ? <Text style={styles.metricCaption}>{caption}</Text> : null}
    </View>
  );
}

function BinStrip({ bins }: { bins: CalibrationBin[] }) {
  return (
    <View style={styles.binStrip}>
      {bins.map((b) => {
        const gap = b.meanPredicted - b.actualWinRate;
        const absGap = Math.abs(gap);
        const tone =
          absGap <= CAL_ERROR_GATE
            ? colors.bet
            : absGap <= CAL_ERROR_GATE * 2
              ? colors.med
              : colors.avoid;
        return (
          <View key={`${b.lower}`} style={styles.bin}>
            <Text style={styles.binLabel}>
              {Math.round(b.lower * 100)}–{Math.round(b.upper * 100)}
            </Text>
            <View style={[styles.binBar, { backgroundColor: tone, opacity: 0.18 }]} />
            <Text style={styles.binActual}>
              {Math.round(b.actualWinRate * 100)}% · {b.n}
            </Text>
          </View>
        );
      })}
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
  },
  heading: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  headerHint: {
    fontSize: 10,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  caption: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  row: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  modelMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flex: 1,
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
  modelName: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
    flex: 1,
  },
  gateBadge: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
    paddingHorizontal: 6,
  },
  metricRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  metric: {
    flex: 1,
  },
  metricLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  metricValue: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: 1,
  },
  metricCaption: {
    fontSize: 10,
    color: colors.med,
    marginTop: 1,
  },
  binStrip: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
    gap: spacing.xs,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  bin: {
    flex: 1,
    alignItems: 'center',
    minWidth: 40,
  },
  binLabel: {
    fontSize: 10,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  binBar: {
    height: 4,
    width: '100%',
    borderRadius: 2,
    marginBottom: 2,
  },
  binActual: {
    fontSize: 10,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
});

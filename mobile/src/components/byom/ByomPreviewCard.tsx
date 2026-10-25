import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ErrorBanner } from '@/components/ErrorState';
import { Skeleton } from '@/components/Skeleton';
import { formatPct, formatPctSigned, formatSignedUnits } from '@/lib/format';
import {
  byomRoi,
  byomWinRate,
  formatByomRecord,
  type ByomRecord,
} from '@/lib/byomRecord';
import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';

export function ByomPreviewCard({
  record,
  loading,
  error,
  onRetry,
  showsUnits,
  emptyLabel = 'No games match',
}: {
  record: ByomRecord | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  showsUnits: boolean;
  /** Replaces “No games match” when the row was not graded. */
  emptyLabel?: string;
}) {
  if (loading) {
    return (
      <Skeleton label="your preview">
        <View style={styles.skel} />
      </Skeleton>
    );
  }
  if (error) {
    return (
      <ErrorBanner
        what="this preview"
        error={error}
        onRetry={onRetry}
      />
    );
  }
  if (record == null || record.bets === 0) {
    return (
      <View style={styles.card} accessibilityRole="summary" accessibilityLabel={emptyLabel}>
        <Text style={styles.empty}>{emptyLabel}</Text>
      </View>
    );
  }

  const rate = byomWinRate(record);
  const roi = showsUnits ? byomRoi(record) : null;
  const unitsText = showsUnits && record.units != null ? formatSignedUnits(record.units) : null;
  const unitsMissing = showsUnits && record.units == null;
  const unitsColor = unitsText != null ? pnlColor(record.units, 1) : colors.textSecondary;
  const recordText = formatByomRecord(record);
  const rateText = rate == null ? '—' : `${formatPct(rate)} wins`;
  const roiText = roi == null ? 'ROI —' : `ROI ${formatPctSigned(roi)}`;
  const label = [
    showsUnits && record.units != null ? unitsText : null,
    recordText,
    rate == null ? null : rateText,
    roi == null ? null : roiText,
    `${record.bets} bet${record.bets === 1 ? '' : 's'}`,
  ].filter(Boolean).join(', ');

  return (
    <View style={styles.card} accessibilityRole="summary" accessibilityLabel={label}>
      {unitsText != null ? (
        <Text style={[styles.units, { color: unitsColor }]}>{unitsText}</Text>
      ) : null}
      {unitsMissing ? (
        <Text style={[styles.units, { color: colors.textSecondary }]}>—</Text>
      ) : null}
      <Text style={unitsText == null && !unitsMissing ? styles.units : styles.record}>{recordText}</Text>
      <Text style={styles.meta}>
        {rateText} · {roiText}
      </Text>
      <Text style={styles.meta}>{record.bets} bet{record.bets === 1 ? '' : 's'}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  empty: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  units: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  record: {
    marginTop: spacing.xs,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  meta: {
    marginTop: 2,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  skel: {
    height: 96,
    borderRadius: radii.lg,
    backgroundColor: colors.noneSoft,
    marginBottom: spacing.md,
  },
});

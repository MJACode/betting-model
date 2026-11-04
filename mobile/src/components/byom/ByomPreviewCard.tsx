import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

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
  closeRecord = null,
  onShowBets,
  closingHeadline = false,
}: {
  record: ByomRecord | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  showsUnits: boolean;
  /** Replaces “No games match” when the row was not graded. */
  emptyLabel?: string;
  /**
   * The same bets at the closing line. Set when `record` is the official
   * pick. Null when `record` already is the close.
   */
  closeRecord?: ByomRecord | null;
  /** Opens the list of the bets this record counts. */
  onShowBets?: () => void;
  /**
   * The official rows are empty, so `record` is the close.
   * Names that basis. The secondary close row stays off.
   */
  closingHeadline?: boolean;
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
  const official = closeRecord != null;
  const closingLead = !official && closingHeadline;
  const closeUnits = closeRecord != null && showsUnits && closeRecord.units != null
    ? formatSignedUnits(closeRecord.units)
    : null;
  const closeText = closeRecord == null
    ? null
    : closeRecord.bets === 0
      ? 'No bets at the closing line'
      : [closeUnits, formatByomRecord(closeRecord)].filter(Boolean).join(' · ');

  return (
    <View style={styles.card}>
      <View accessible accessibilityRole="summary"
        accessibilityLabel={
          official ? `At the official line: ${label}`
            : closingLead ? `At the closing line: ${label}`
              : label
        }>
      {official ? <Text style={styles.kicker}>At the official line</Text> : null}
      {closingLead ? <Text style={styles.kicker}>At the closing line</Text> : null}
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
      {closeText != null ? (
        <View style={styles.closeRow} accessible
          accessibilityLabel={`At the closing line: ${closeText}`}>
          <Text style={styles.closeLabel}>At the closing line</Text>
          <Text style={styles.closeValue}>{closeText}</Text>
        </View>
      ) : null}
      {onShowBets ? (
        <Pressable
          onPress={onShowBets}
          accessibilityRole="button"
          accessibilityLabel={`See the ${record.bets} bet${record.bets === 1 ? '' : 's'}`}
          style={({ pressed }) => [styles.showBets, pressed && styles.pressed]}
        >
          <Text style={styles.showBetsText}>
            See the {record.bets} bet{record.bets === 1 ? '' : 's'}
          </Text>
          <Text style={styles.chevron} accessibilityElementsHidden importantForAccessibility="no">›</Text>
        </Pressable>
      ) : null}
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
  kicker: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  closeRow: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    gap: spacing.sm,
  },
  closeLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  closeValue: {
    flexShrink: 1,
    textAlign: 'right',
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  showBets: {
    minHeight: 44,
    marginTop: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  pressed: { opacity: 0.6 },
  showBetsText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  chevron: {
    fontSize: font.size.title3,
    color: colors.textTertiary,
  },
  skel: {
    height: 96,
    borderRadius: radii.lg,
    backgroundColor: colors.noneSoft,
    marginBottom: spacing.md,
  },
});

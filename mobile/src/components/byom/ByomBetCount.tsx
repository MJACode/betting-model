import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ErrorBanner } from '@/components/ErrorState';
import { Skeleton } from '@/components/Skeleton';
import { formatSignedUnits } from '@/lib/format';
import { formatByomRecord, type ByomRecord } from '@/lib/byomRecord';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Navy bet-count bar. A zero count is the existing empty line, not a
 * zero hero and not a sample warning.
 */
export function ByomBetCount({
  record,
  loading,
  error,
  onRetry,
  showsUnits,
  emptyLabel = 'No games match',
  blocked = null,
}: {
  record: ByomRecord | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  showsUnits: boolean;
  emptyLabel?: string;
  /** A required choice is still missing. This is not an empty result. */
  blocked?: string | null;
}) {
  if (blocked) {
    return (
      <View style={styles.empty} accessibilityRole="summary" accessibilityLabel={blocked}>
        <Text style={styles.emptyText}>{blocked}</Text>
      </View>
    );
  }
  if (loading) {
    return (
      <Skeleton label="your preview">
        <View style={styles.skel} />
      </Skeleton>
    );
  }
  if (error) {
    return <ErrorBanner what="this preview" error={error} onRetry={onRetry} />;
  }
  if (record == null || record.bets === 0) {
    return (
      <View style={styles.empty} accessibilityRole="summary" accessibilityLabel={emptyLabel}>
        <Text style={styles.emptyText}>{emptyLabel}</Text>
      </View>
    );
  }
  const unitsText = showsUnits && record.units != null ? formatSignedUnits(record.units) : null;
  const unitsColor = record.units == null
    ? colors.textInverse
    : record.units > 0
      ? colors.positive
      : record.units < 0
        ? colors.negative
        : colors.textInverse;
  const recordText = formatByomRecord(record);
  const noun = record.bets === 1 ? 'bet' : 'bets';
  const label = [
    `${record.bets} ${noun}`,
    unitsText,
    recordText,
  ].filter(Boolean).join(', ');
  return (
    <View style={styles.bar} accessibilityRole="summary" accessibilityLabel={label}>
      <View>
        <Text style={styles.kicker}>Bets that match</Text>
        <Text style={styles.count}>{record.bets}</Text>
      </View>
      <View style={styles.right}>
        <Text style={styles.kickerRight}>units · record</Text>
        <Text style={styles.recordLine}>
          {unitsText != null ? (
            <Text style={[styles.units, { color: unitsColor }]}>{unitsText} </Text>
          ) : null}
          <Text style={styles.record}>{recordText}</Text>
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  kicker: {
    fontSize: font.size.caption,
    color: colors.brandMuted,
  },
  kickerRight: {
    fontSize: font.size.caption,
    color: colors.brandMuted,
    textAlign: 'right',
  },
  count: {
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  right: {
    alignItems: 'flex-end',
  },
  recordLine: {
    marginTop: 2,
    textAlign: 'right',
  },
  units: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
  },
  record: {
    fontSize: font.size.footnote,
    color: colors.textInverse,
  },
  empty: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  emptyText: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  skel: {
    height: 72,
    borderRadius: radii.md,
    backgroundColor: colors.noneSoft,
    marginBottom: spacing.md,
  },
});

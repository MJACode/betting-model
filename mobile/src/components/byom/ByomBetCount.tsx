import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

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
  closeRecord = null,
  onShowBets,
  closingHeadline = false,
}: {
  record: ByomRecord | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  showsUnits: boolean;
  emptyLabel?: string;
  /** A required choice is still missing. This is not an empty result. */
  blocked?: string | null;
  /** The same bets at the closing line, when the bar shows the official pick. */
  closeRecord?: ByomRecord | null;
  /** Opens the list of the bets this count is made of. */
  onShowBets?: () => void;
  /** Fallback: this count is the close because official rows are empty. */
  closingHeadline?: boolean;
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
  const closeUnits = closeRecord != null && showsUnits && closeRecord.units != null
    ? formatSignedUnits(closeRecord.units)
    : null;
  const closingLead = closeRecord == null && closingHeadline;
  const closeText = closeRecord == null
    ? null
    : closeRecord.bets === 0
      ? 'No bets at the closing line'
      : [closeUnits, formatByomRecord(closeRecord)].filter(Boolean).join(' · ');
  return (
    <View style={styles.wrap}>
    <View style={styles.bar} accessible accessibilityRole="summary"
      accessibilityLabel={
        closeRecord != null ? `At the official line: ${label}`
          : closingLead ? `At the closing line: ${label}`
            : label
      }>
      <View>
        <Text style={styles.kicker}>Bets that match</Text>
        <Text style={styles.count}>{record.bets}</Text>
      </View>
      <View style={styles.right}>
        <Text style={styles.kickerRight}>{
          closeRecord != null ? 'official line · units · record'
            : closingLead ? 'closing line · units · record'
              : 'units · record'
        }</Text>
        <Text style={styles.recordLine}>
          {unitsText != null ? (
            <Text style={[styles.units, { color: unitsColor }]}>{unitsText} </Text>
          ) : null}
          <Text style={styles.record}>{recordText}</Text>
        </Text>
      </View>
    </View>
    {closeText != null ? (
      <Text style={styles.close} accessibilityLabel={`At the closing line: ${closeText}`}>
        At the closing line: {closeText}
      </Text>
    ) : null}
    {onShowBets ? (
      <Pressable
        onPress={onShowBets}
        accessibilityRole="button"
        accessibilityLabel={`See the ${record.bets} ${noun}`}
        style={({ pressed }) => [styles.showBets, pressed && styles.pressed]}
      >
        <Text style={styles.showBetsText}>See the {record.bets} {noun}</Text>
        <Text style={styles.chevron} accessibilityElementsHidden importantForAccessibility="no">›</Text>
      </Pressable>
    ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: spacing.md,
  },
  close: {
    marginTop: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  showBets: {
    minHeight: 44,
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
  bar: {
    backgroundColor: colors.tint,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
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

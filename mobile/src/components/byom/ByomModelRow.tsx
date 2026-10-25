import React from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { formatPct, formatPctSigned, formatSignedUnits } from '@/lib/format';
import { modelRecordBelow } from '@/lib/modelBadgeLayout';
import {
  byomRoi,
  byomWinRate,
  formatByomRecord,
  marketLabel,
  type ByomRecord,
} from '@/lib/byomRecord';
import type { ByomFilters } from '@/lib/byomFilters';
import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';

export function ByomModelRow({
  rank,
  name,
  filters,
  record,
  showsUnits: unitsVisible,
  ungraded = false,
  onPress,
}: {
  rank: number | null;
  name: string;
  filters: ByomFilters;
  record: ByomRecord | null;
  showsUnits: boolean;
  ungraded?: boolean;
  onPress: () => void;
}) {
  const { width, fontScale } = useWindowDimensions();
  const stacked = modelRecordBelow(fontScale, width);
  const market = marketLabel(filters);
  const noGames = !ungraded && (record == null || record.bets === 0);
  const rate = record == null ? null : byomWinRate(record);
  const roi = record != null && unitsVisible ? byomRoi(record) : null;
  const unitsKnown = !noGames && !ungraded && unitsVisible && record?.units != null;
  const unitsMissing = !noGames && !ungraded && unitsVisible && record?.units == null;
  const unitsText = unitsKnown && record?.units != null ? formatSignedUnits(record.units) : null;
  const unitsColor = unitsKnown && record?.units != null ? pnlColor(record.units, 1) : colors.textSecondary;
  const recordText = record == null ? '' : formatByomRecord(record);
  const rateText = rate == null ? '—' : `${formatPct(rate)} wins`;
  const roiText = roi == null ? 'ROI —' : `ROI ${formatPctSigned(roi)}`;
  const bets = record?.bets ?? 0;
  const label = ungraded
    ? `${name}. ${market}.`
    : noGames
    ? `${name}. ${market}. No games match.`
    : [
      rank != null ? `Rank ${rank}` : null,
      name,
      market,
      !unitsVisible || record?.units == null ? null : unitsText,
      recordText,
      rate == null ? null : rateText,
      roi == null ? null : roiText,
      `${bets} bet${bets === 1 ? '' : 's'}`,
    ].filter(Boolean).join(', ');

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <View style={[styles.body, stacked && styles.bodyStacked]}>
        <View style={styles.main}>
          <View style={styles.titleLine}>
            {rank != null ? <Text style={styles.rank}>{rank}</Text> : null}
            <Text style={styles.name} numberOfLines={2}>{name}</Text>
          </View>
          <Text style={styles.sub} numberOfLines={1}>{market}</Text>
          {noGames || ungraded ? null : (
            <Text style={styles.sub}>{bets} bet{bets === 1 ? '' : 's'}</Text>
          )}
        </View>
        <View style={[styles.figures, stacked && styles.figuresStacked]}>
          {ungraded ? (
            <Text style={styles.noGames}>—</Text>
          ) : noGames ? (
            <Text style={styles.noGames}>No games match</Text>
          ) : (
            <>
              {unitsText != null ? (
                <Text style={[styles.units, { color: unitsColor }]}>{unitsText}</Text>
              ) : null}
              {unitsMissing ? (
                <Text style={[styles.units, { color: colors.textSecondary }]}>—</Text>
              ) : null}
              <Text style={unitsText == null && !unitsMissing ? [styles.units, styles.recordLead] : styles.record}>
                {recordText}
              </Text>
              <Text style={styles.meta}>{rateText} · {roiText}</Text>
            </>
          )}
        </View>
      </View>
      <Ionicons
        name="chevron-forward"
        size={18}
        color={colors.textSecondary}
        importantForAccessibility="no"
        accessibilityElementsHidden
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  pressed: { opacity: 0.7 },
  body: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
  },
  bodyStacked: {
    flexDirection: 'column',
  },
  main: {
    flex: 1,
  },
  titleLine: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  rank: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    minWidth: 24,
  },
  name: {
    flex: 1,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  sub: {
    marginTop: 2,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  figures: {
    alignItems: 'flex-end',
    maxWidth: '46%',
  },
  figuresStacked: {
    alignItems: 'flex-start',
    maxWidth: '100%',
    marginTop: spacing.sm,
  },
  units: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
  },
  record: {
    marginTop: 2,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  recordLead: {
    marginTop: 0,
    color: colors.textPrimary,
  },
  meta: {
    marginTop: 2,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    textAlign: 'right',
  },
  noGames: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
});

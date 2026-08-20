import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { formatDayTimeET } from '@/lib/format';
import { nflTimingInfo } from '@/lib/markets';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';

/**
 * When an NFL pick was locked/priced, and what that means. NFL picks publish
 * days before kickoff (§28 card runs), so a day-of user needs to know they're
 * looking at a number taken earlier in the week — for the opener that number
 * is the whole edge and is never re-priced; for wind the pick re-prices each
 * card run. The Line Movement card below shows where the market has gone since.
 */
export function NflTimingCard({ pick }: { pick: Pick }) {
  const timing = nflTimingInfo(pick);
  if (!timing) return null;

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Pick timing</Text>
      <Text style={styles.headline}>
        {timing.verb} {formatDayTimeET(pick.created_at)}
      </Text>
      <Text style={styles.note}>{timing.note}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  heading: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 4,
  },
  headline: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  note: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
  },
});

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { formatDayTimeET } from '@/lib/format';
import { pickTimingInfo } from '@/lib/markets';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';

/**
 * When this bet posted, and what that time means for the number beside it.
 *
 * Every signal here is a locked bet of record, so the timestamp is part of the
 * pick rather than metadata: an NFL opener was locked days before kickoff and
 * the market has usually corrected since, a live bet was locked mid-game at a
 * price that moves in seconds, and a morning game pick is the number that was
 * on offer at lock. Renders nothing for anything that is not a locked BET —
 * see pickTimingInfo.
 */
export function PickTimingCard({ pick }: { pick: Pick }) {
  const timing = pickTimingInfo(pick);
  if (!timing) return null;

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Pick timing</Text>
      {/* The full stamp here (the card chip abbreviates a same-day post to
          the time alone — on the detail screen the date is worth the room). */}
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

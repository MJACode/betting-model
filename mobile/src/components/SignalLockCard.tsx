import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { colors, font, radii, spacing, opacity, card } from '@/lib/theme';
import { PrimaryButton } from '@/components/PrimaryButton';

/**
 * Soft lock for a free member. Same card on Picks, Signals, Live,
 * and the other non-Record tabs. Record is not locked. Scoreboard uses
 * its own sheet ("Scoreboard is Premium") over a blurred board.
 *
 * The copy is shared. It does not promise a trial on Weekly, which has none.
 * Unlock opens the paywall.
 */
export function SignalLockCard({
  onPress,
  title = "Today's picks are for Premium",
  body = 'See every BET signal, stake and live in-play pick. Monthly and Annual include 7 days free.',
  onRecord,
}: {
  onPress: () => void;
  title?: string;
  body?: string;
  /** Picks only — the board's "Record stays free" row. */
  onRecord?: () => void;
}) {
  return (
    <View style={styles.wrap}>
      <View style={styles.card}>
        <View style={styles.iconWrap}>
          <Ionicons name="lock-closed" size={22} color={colors.brand} />
        </View>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.body}>{body}</Text>
        <PrimaryButton label="Unlock with Premium" onPress={onPress} variant="brand" />
      </View>

      {onRecord ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Record stays free. See how every model did."
          onPress={onRecord}
          style={({ pressed }) => [styles.record, pressed && styles.pressed]}
        >
          <View style={styles.recordText}>
            <Text style={styles.recordTitle}>Record stays free</Text>
            <Text style={styles.recordBody}>
              See how every model did — all sports, all time.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: spacing.lg, gap: spacing.md },
  card: {
    backgroundColor: colors.brandNavy,
    borderRadius: radii.md,
    padding: spacing.xl,
    alignItems: 'center',
    gap: spacing.md,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.brandNavyRaised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontFamily: font.family,
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
    textAlign: 'center',
  },
  body: {
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.brandMuted,
    textAlign: 'center',
    lineHeight: 21,
  },
  record: {
    ...card,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    minHeight: 64,
  },
  recordText: { flex: 1, gap: 2 },
  recordTitle: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  recordBody: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  pressed: { opacity: opacity.pressed },
});

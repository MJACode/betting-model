import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { TRIAL_DAYS } from '@/lib/billingConfig';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Shown in place of the signal list when the user isn't subscribed.
 *
 * It reports HOW MANY signals are waiting rather than hiding that anything
 * exists. That's the honest framing and the one that converts: a "0 signals
 * today" day is a real outcome in this product, so a lock screen claiming
 * value on a day with nothing behind it would be a lie the user discovers
 * immediately after paying.
 */
export function SignalLockCard({
  count,
  onPress,
}: {
  count: number;
  onPress: () => void;
}) {
  const none = count === 0;

  return (
    <View style={styles.wrap}>
      <View style={styles.card}>
        <View style={styles.iconWrap}>
          <Ionicons
            name={none ? 'moon-outline' : 'lock-closed'}
            size={26}
            color={colors.tint}
          />
        </View>

        <Text style={styles.title}>
          {none
            ? 'No signals right now'
            : `${count} signal${count === 1 ? '' : 's'} waiting`}
        </Text>

        <Text style={styles.body}>
          {none
            ? "The models haven't found a bet that clears the line yet today. Zero-signal days are normal — subscribe and you'll see them the moment they fire."
            : 'Subscribe to see which side the model likes, the price it wants, and the stake sized to your bankroll.'}
        </Text>

        <Pressable
          onPress={onPress}
          style={({ pressed }) => [styles.cta, pressed && styles.pressed]}
        >
          <Text style={styles.ctaText}>Start {TRIAL_DAYS}-day free trial</Text>
        </Pressable>

        <Text style={styles.footnote}>
          The full track record, model pages and stats stay free — check the
          record before you pay for anything.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: spacing.lg },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.xl,
    alignItems: 'center',
    gap: spacing.md,
  },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontFamily: font.family,
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  body: {
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 21,
  },
  cta: {
    height: 48,
    alignSelf: 'stretch',
    borderRadius: radii.md,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  pressed: { opacity: 0.6 },
  footnote: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
  },
});

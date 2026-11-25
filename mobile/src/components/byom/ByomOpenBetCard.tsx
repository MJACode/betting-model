import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { formatAmerican, formatDayTimeET } from '@/lib/format';
import { matchupLabel, type ByomOpenBet } from '@/lib/byomAlerts';
import { colors, font, opacity, radii, spacing } from '@/lib/theme';

/**
 * One open bet from the member's own model (Matt, 2026-11-25).
 *
 * The label is the stored bet word for word, beside the price it first fit
 * at. "Fit" is when that line first matched the rules; a later move does
 * not change the card (the bet is the first fit, CLAUDE.md §1c). Not a
 * pick: no track, betslip or Record entry.
 */
export function ByomOpenBetCard({
  bet,
  showModel = true,
  onPress,
}: {
  bet: ByomOpenBet;
  /** False on the model's own page, where the name is the screen title. */
  showModel?: boolean;
  onPress?: () => void;
}) {
  const matchup = matchupLabel(bet);
  const kick = formatDayTimeET(bet.commence_time);
  const fit = bet.locked_at ? formatDayTimeET(bet.locked_at) : '';
  const price = formatAmerican(bet.price);
  const meta = [matchup, bet.started ? 'Started' : kick].filter(Boolean).join(' · ');
  const spoken = [
    showModel ? `${bet.model_name}.` : '',
    `${bet.label}, ${price}.`,
    meta ? `${meta}.` : '',
    fit ? `Fit your rules ${fit}.` : '',
  ].filter(Boolean).join(' ');

  const body = (
    <>
      {showModel ? (
        <View style={styles.modelRow}>
          <Ionicons name="construct-outline" size={14} color={colors.textSecondary} />
          <Text style={styles.model} numberOfLines={1}>{bet.model_name}</Text>
        </View>
      ) : null}
      <View style={styles.betRow}>
        <Text style={styles.label}>{bet.label}</Text>
        <Text style={styles.price}>{price}</Text>
      </View>
      {meta ? <Text style={styles.meta}>{meta}</Text> : null}
      {fit ? <Text style={styles.fit}>{`Fit your rules ${fit}`}</Text> : null}
    </>
  );

  if (!onPress) {
    return (
      <View style={styles.card} accessible accessibilityLabel={spoken}>
        {body}
      </View>
    );
  }
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={spoken}
      accessibilityHint="Opens this model"
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: 44,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  pressed: { opacity: opacity.pressed },
  modelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  model: {
    flexShrink: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  betRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  label: {
    flexShrink: 1,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  price: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  meta: {
    marginTop: spacing.xs,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  fit: {
    marginTop: 2,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
});

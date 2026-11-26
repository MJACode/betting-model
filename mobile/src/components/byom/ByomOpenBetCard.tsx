import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { formatAmerican, formatDayTimeET, formatGameTimeET } from '@/lib/format';
import { foundAtText } from '@/lib/myBooks';
import { matchupLabel, movedLine, type ByomOpenBet } from '@/lib/byomAlerts';
import { cardDense, colors, font, opacity, spacing } from '@/lib/theme';

/**
 * One open bet from the member's own model (Matt, 2026-11-25).
 *
 * The label is the stored bet word for word, with the DraftKings price it
 * first fit at, on a game-week line. A later move does not change the
 * card (CLAUDE.md §1c). Matt, 2026-11-26: no "Fit your rules" date.
 * Not a pick: no track, betslip or Record entry.
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
  // The builder grades at DraftKings only (docs/byom_nfl.md).
  const price = foundAtText('DK', formatAmerican(bet.price));
  // Matt, 2026-11-26: the line now on the card. The bet stays the line it
  // fit at (CLAUDE.md §1c); this only says where DraftKings is today.
  const moved = movedLine(bet);
  // DraftKings is the subject, so it reads as the book's line, not the bet
  // (UX review 2026-11-26). The time says how old the quote is.
  const nowAt = moved && bet.now_at ? formatGameTimeET(bet.now_at) : '';
  const nowText = moved
    ? [`DK now ${moved.label}`, formatAmerican(moved.price), nowAt].filter(Boolean).join(' · ')
    : null;
  // Time first, so a long school name cuts the matchup, not the time.
  const meta = [bet.started ? 'Started' : kick, matchup].filter(Boolean).join(' · ');
  const spoken = [
    showModel ? `${bet.model_name}.` : '',
    `${bet.label}. ${foundAtText('DraftKings', formatAmerican(bet.price))}.`,
    moved ? `DraftKings now ${moved.label} at ${formatAmerican(moved.price)}${nowAt ? `, as of ${nowAt}` : ''}.` : '',
    meta ? `${meta}.` : '',
  ].filter(Boolean).join(' ');

  const body = (
    <>
      {showModel ? (
        <View style={styles.modelRow}>
          <Ionicons name="construct-outline" size={14} color={colors.textSecondary} />
          <Text style={styles.model} numberOfLines={1}>{bet.model_name}</Text>
        </View>
      ) : null}
      <Text style={styles.label}>{bet.label}</Text>
      <Text style={styles.price}>{price}</Text>
      {nowText ? <Text style={styles.now}>{nowText}</Text> : null}
      {meta ? <Text style={styles.meta} numberOfLines={2}>{meta}</Text> : null}
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
  card: { ...cardDense, minHeight: 44, marginBottom: spacing.sm },
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
  label: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  price: {
    marginTop: spacing.xs,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  now: {
    marginTop: spacing.xs,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  meta: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
});

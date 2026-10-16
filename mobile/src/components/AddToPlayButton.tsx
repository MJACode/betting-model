import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  inPlay: boolean;
  onPress: () => void;
  /** Tighter padding + smaller text for dense rows (e.g. Stats leaderboard). */
  compact?: boolean;
  /** Signals card: 44pt tall, navy outline (tint, not system blue). */
  tall?: boolean;
}

/**
 * "+ Add to betslip" / "✓ In betslip" pill. Its own Pressable, so a tap is
 * captured here and does NOT bubble to an enclosing card/row Pressable (RN
 * responder model — the innermost responder wins).
 */
export function AddToPlayButton({ inPlay, onPress, compact, tall }: Props) {
  const short = Boolean(compact || tall);
  const label = inPlay
    ? 'In your betslip. Tap to remove.'
    : 'Add this bet to your betslip.';
  const word = inPlay ? (short ? 'In slip' : 'In betslip') : short ? 'Slip' : 'Add to betslip';
  // The Signals row is already 44pt. Extra slop would cover the posted-time
  // line and the gap before the navy button (UX review, 2026-10-16).
  if (tall) {
    return (
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityState={{ selected: inPlay }}
        accessibilityLabel={label}
        style={({ pressed }) => [
          styles.btn,
          styles.btnTall,
          inPlay ? styles.inPlayTall : styles.add,
          pressed && styles.pressed,
        ]}
      >
        <View style={styles.row}>
          <Ionicons name={inPlay ? 'checkmark' : 'add'} size={16} color={colors.tint} />
          <Text style={[styles.text, styles.textTall, { color: colors.tint }]}>{word}</Text>
        </View>
      </Pressable>
    );
  }
  return (
    <Pressable
      onPress={onPress}
      // Vertical slop only: the compact pills sit ~8pt apart in PickCard's
      // actions row, so wider side slop would let the later sibling swallow
      // taps meant for its neighbour (UX review, 2026-09-05).
      hitSlop={{ top: 11, bottom: 11, left: 6, right: 6 }}
      accessibilityRole="button"
      // VoiceOver says "selected" on the ON state, not only a changed label.
      accessibilityState={{ selected: inPlay }}
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.btn,
        compact && styles.btnCompact,
        inPlay ? styles.inPlay : styles.add,
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.row}>
        <Ionicons name={inPlay ? 'checkmark' : 'add'} size={compact ? 14 : 16} color={colors.tint} />
        <Text style={[styles.text, compact && styles.textCompact, { color: colors.tint }]}>{word}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    borderRadius: radii.pill,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  btnCompact: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  // Signals card. minHeight 44 (HIG). Outline is tint — brand navy, 18:1 on
  // bgCard — not the system blue.
  btnTall: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
  },
  add: {
    borderColor: colors.tint,
    backgroundColor: colors.bgCard,
  },
  // ON is outlined in tint with a checkmark, not green: green means only
  // "good for the user" (UX_REVIEW §2; Designer ruling, 2026-09-25).
  inPlay: {
    borderColor: colors.tint,
    backgroundColor: colors.bgCard,
  },
  // Tall (Signals) selected state. Compact pills stay on the card ground.
  inPlayTall: {
    borderColor: colors.tint,
    backgroundColor: colors.tintSoft,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  text: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  textCompact: {
    fontSize: font.size.caption,
  },
  textTall: {
    fontSize: font.size.footnote,
  },
  pressed: {
    opacity: 0.6,
  },
});

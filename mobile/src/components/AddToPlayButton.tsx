import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  inPlay: boolean;
  onPress: () => void;
  /** Tighter padding + smaller text for dense rows (e.g. Stats leaderboard). */
  compact?: boolean;
}

/**
 * "+ Add to betslip" / "✓ In betslip" pill. Its own Pressable, so a tap is
 * captured here and does NOT bubble to an enclosing card/row Pressable (RN
 * responder model — the innermost responder wins).
 */
export function AddToPlayButton({ inPlay, onPress, compact }: Props) {
  return (
    <Pressable
      onPress={onPress}
      // Vertical slop only: the compact pills sit ~8pt apart in PickCard's
      // actions row, so wider side slop would let the later sibling swallow
      // taps meant for its neighbour (UX review, 2026-09-05).
      hitSlop={{ top: 11, bottom: 11, left: 6, right: 6 }}
      accessibilityRole="button"
      accessibilityLabel={
        inPlay
          ? 'In your betslip. Tap to remove.'
          : 'Add this bet to your betslip.'
      }
      style={({ pressed }) => [
        styles.btn,
        compact && styles.btnCompact,
        inPlay ? styles.inPlay : styles.add,
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.row}>
        <Ionicons
          name={inPlay ? 'checkmark' : 'add'}
          size={compact ? 14 : 16}
          color={inPlay ? colors.bet : colors.tint}
        />
        <Text
          style={[
            styles.text,
            compact && styles.textCompact,
            { color: inPlay ? colors.bet : colors.tint },
          ]}
        >
          {inPlay ? 'In betslip' : 'Add to betslip'}
        </Text>
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
  add: {
    borderColor: colors.tint,
    backgroundColor: colors.bgCard,
  },
  inPlay: {
    borderColor: colors.bet,
    backgroundColor: colors.betSoft,
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
  pressed: {
    opacity: 0.6,
  },
});

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  tracked: boolean;
  onPress: () => void;
  /** Tighter padding + smaller text for dense pick cards. */
  compact?: boolean;
}

/**
 * "Track" / "Tracking" pill with a bell icon. When tracked, the line-change
 * notifier pings the user if the DK line moves big before game time. Its own
 * Pressable so a tap doesn't bubble to the enclosing card (RN responder model).
 */
export function TrackButton({ tracked, onPress, compact }: Props) {
  return (
    <Pressable
      onPress={onPress}
      // Vertical slop only: the compact pills sit ~8pt apart in PickCard's
      // actions row, so wider side slop would let the later sibling swallow
      // taps meant for its neighbour (UX review, 2026-09-05).
      hitSlop={{ top: 11, bottom: 11, left: 6, right: 6 }}
      accessibilityRole="button"
      accessibilityLabel={
        tracked
          ? 'Tracking this bet — we’ll alert you if the line moves a lot before game time. Tap to stop.'
          : 'Track this bet — we’ll alert you if the line moves a lot before game time.'
      }
      style={({ pressed }) => [
        styles.btn,
        compact && styles.btnCompact,
        tracked ? styles.on : styles.off,
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.row}>
        <Ionicons
          name={tracked ? 'notifications' : 'notifications-outline'}
          size={compact ? 14 : 16}
          color={tracked ? colors.bet : colors.tint}
        />
        <Text
          style={[
            styles.text,
            compact && styles.textCompact,
            { color: tracked ? colors.bet : colors.tint },
          ]}
        >
          {tracked ? 'Tracking' : 'Track'}
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
  on: {
    borderColor: colors.bet,
    backgroundColor: 'transparent',
  },
  off: {
    borderColor: colors.tint,
    backgroundColor: 'transparent',
  },
  pressed: {
    opacity: 0.6,
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
});

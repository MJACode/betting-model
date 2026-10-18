import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  tracked: boolean;
  onPress: () => void;
  /** Tighter padding + smaller text for dense pick cards. */
  compact?: boolean;
  /** Signals card: 44pt tall, navy outline (tint, not system blue). */
  tall?: boolean;
}

/**
 * "Track" (bell) / "Tracking" (checkmark) pill. Both states are outlined in
 * tint: the ON state changes the icon and the label, not the colour, because
 * green means only "good for the user" (UX_REVIEW §2; Designer ruling on the
 * usability audit, 2026-09-25). When tracked, the line-change
 * notifier pings the user if the DK line moves big before game time. Its own
 * Pressable so a tap doesn't bubble to the enclosing card (RN responder model).
 */
export function TrackButton({ tracked, onPress, compact, tall }: Props) {
  const label = tracked
    ? 'Tracking this bet — we’ll alert you if the line moves a lot before game time. Tap to stop.'
    : 'Track this bet — we’ll alert you if the line moves a lot before game time.';
  const word = tracked ? 'Tracking' : 'Track';
  // The Signals row is already 44pt. Extra slop would cover the posted-time
  // line and the gap before the navy button (UX review, 2026-10-16).
  if (tall) {
    return (
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityState={{ selected: tracked }}
        accessibilityLabel={label}
        style={({ pressed }) => [
          styles.btn,
          styles.btnTall,
          tracked ? styles.onTall : styles.off,
          pressed && styles.pressed,
        ]}
      >
        <View style={styles.row}>
          <Ionicons name={tracked ? 'checkmark' : 'notifications-outline'} size={16} color={colors.tint} />
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
      accessibilityState={{ selected: tracked }}
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.btn,
        compact && styles.btnCompact,
        tracked ? styles.on : styles.off,
        pressed && styles.pressed,
      ]}
    >
      <View style={styles.row}>
        <Ionicons
          name={tracked ? 'checkmark' : 'notifications-outline'}
          size={compact ? 14 : 16}
          color={colors.tint}
        />
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
  on: {
    borderColor: colors.tint,
    backgroundColor: 'transparent',
  },
  // Tall (Signals) selected state. Compact pills stay transparent.
  onTall: {
    borderColor: colors.tint,
    backgroundColor: colors.tintSoft,
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
  textTall: {
    fontSize: font.size.footnote,
  },
});

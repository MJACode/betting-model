/**
 * The one chip. Every filter surface in the app (picks, stats, sports, sort,
 * time windows) renders this — before it existed there were four near-identical
 * copies with slightly different padding, so chips looked subtly wrong depending
 * on which screen you were on.
 *
 * Sizes: 'md' is the default tap target; 'sm' is for dense lists (e.g. the model
 * list inside a sheet, where a screen's worth of chips has to fit).
 */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii, spacing } from '@/lib/theme';

export interface FilterChipProps {
  label: string;
  active?: boolean;
  onPress: () => void;
  size?: 'sm' | 'md';
  /** Leading icon (Ionicons name). Tinted with the chip's text color. */
  icon?: React.ComponentProps<typeof Ionicons>['name'];
  /** Trailing count, e.g. the "(12)" on a view tab. */
  count?: number;
  /** Dim + block taps — used for sports with nothing on the board today. */
  disabled?: boolean;
  /**
   * A load this chip started is in flight. Announced, NOT dimmed and NOT
   * blocked: `disabled` renders textTertiary, and on an ACTIVE chip that puts
   * tertiary text on the tint fill at 0.45 opacity, which erases the on/off
   * affordance of the one control that changes the population of the board
   * (UX_REVIEW §5, and the review that caught it 2026-09-09). Taps stay live
   * because the caller stamps its requests and a second tap is harmless.
   */
  busy?: boolean;
  accessibilityLabel?: string;
}

export function FilterChip({
  label,
  active = false,
  onPress,
  size = 'md',
  icon,
  count,
  disabled = false,
  busy = false,
  accessibilityLabel,
}: FilterChipProps) {
  const fg = disabled ? colors.textTertiary : active ? colors.textInverse : colors.textSecondary;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      // 34pt tall at 'md', 28 at 'sm' — both under the 44pt HIG floor, and on
      // the Stats board height is the one thing that cannot be spent (UX
      // review, 2026-09-12). The target is made up out of the gap instead.
      hitSlop={{ top: 6, bottom: 6, left: 4, right: 4 }}
      accessibilityRole="button"
      accessibilityState={{ selected: active, disabled, busy }}
      accessibilityLabel={accessibilityLabel ?? label}
      style={({ pressed }) => [
        styles.chip,
        size === 'sm' && styles.chipSm,
        active && styles.chipActive,
        disabled && styles.chipDisabled,
        pressed && styles.pressed,
      ]}
    >
      {icon ? <Ionicons name={icon} size={size === 'sm' ? 11 : 13} color={fg} /> : null}
      <Text style={[styles.text, size === 'sm' && styles.textSm, { color: fg }]}>{label}</Text>
      {count != null ? (
        <View style={[styles.countWrap, active && styles.countWrapActive]}>
          <Text style={[styles.countText, active && styles.countTextActive]}>{count}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  chipSm: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    gap: 4,
  },
  chipActive: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  chipDisabled: {
    opacity: 0.45,
  },
  text: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  textSm: {
    fontSize: font.size.caption,
  },
  countWrap: {
    minWidth: 17,
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: radii.pill,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
  },
  countWrapActive: {
    backgroundColor: 'rgba(255,255,255,0.25)',
  },
  countText: {
    fontSize: font.size.nano,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  countTextActive: {
    color: colors.textInverse,
  },
  pressed: { opacity: 0.6 },
});

/** Horizontal scroller spacing for a row of chips. Exported so every caller
 *  lays chips out identically instead of re-deriving gap/padding. */
export const chipRowStyle = {
  flexDirection: 'row' as const,
  alignItems: 'center' as const,
  gap: spacing.sm,
  paddingHorizontal: spacing.lg,
};

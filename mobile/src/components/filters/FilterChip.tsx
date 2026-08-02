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
  accessibilityLabel,
}: FilterChipProps) {
  const fg = disabled ? colors.textTertiary : active ? colors.textInverse : colors.textSecondary;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ selected: active, disabled }}
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
    fontSize: 10,
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

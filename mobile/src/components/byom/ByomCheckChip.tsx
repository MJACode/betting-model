import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';

import { colors, font, radii, spacing } from '@/lib/theme';

export function ByomCheckChip({
  label,
  selected,
  disabled = false,
  onPress,
  accessibilityLabel,
  exclusive = false,
  showCheck = true,
}: {
  label: string;
  selected: boolean;
  disabled?: boolean;
  onPress: () => void;
  accessibilityLabel?: string;
  /** One choice in the group. VoiceOver uses a radio. */
  exclusive?: boolean;
  /** Removal chips carry their own ✕ and do not add a check. */
  showCheck?: boolean;
}) {
  const mark = selected && showCheck;
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      disabled={disabled}
      accessibilityRole={exclusive ? 'radio' : 'button'}
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ selected, disabled }}
      style={[styles.chip, selected && styles.chipOn, disabled && styles.chipOff]}
    >
      <Text style={[styles.text, selected && styles.textOn, disabled && styles.textOff]}>
        {mark ? `\u2713  ${label}` : label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
  },
  chipOn: {
    backgroundColor: colors.tintSoft,
    borderColor: colors.tint,
    borderWidth: 2,
  },
  chipOff: {
    borderStyle: 'dashed',
    backgroundColor: colors.bg,
  },
  text: {
    fontSize: font.size.body,
    fontWeight: font.weight.medium,
    color: colors.tint,
  },
  textOn: {
    fontWeight: font.weight.bold,
  },
  textOff: {
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
  },
});

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * The BYOM pill segmented control. One control, so the season toggle and
 * the official/closing toggle cannot drift apart (UX review, 2026-11-04).
 */
export function ByomPillToggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <View style={styles.row} accessibilityRole="tablist">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            onPress={() => onChange(option.value)}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            accessibilityLabel={option.label}
            style={[styles.pill, selected && styles.pillOn]}
          >
            <Text style={[styles.label, selected && styles.labelOn]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    backgroundColor: colors.bgCard,
    borderRadius: radii.pill,
    padding: 3,
    marginBottom: spacing.md,
  },
  pill: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.pill,
  },
  pillOn: {
    backgroundColor: colors.tintSoft,
  },
  label: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.medium,
    color: colors.textSecondary,
  },
  labelOn: {
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
});

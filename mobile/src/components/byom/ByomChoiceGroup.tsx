import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, font, radii, spacing } from '@/lib/theme';

export function ByomChoiceGroup<T extends string>({
  label,
  value,
  options,
  onChange,
  clearOnReselect = false,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  /** A second tap on the selected chip clears it. The parent treats '' as none. */
  clearOnReselect?: boolean;
}) {
  return (
    <View style={styles.group} accessibilityRole="radiogroup" accessibilityLabel={label}>
      <Text style={styles.groupLabel}>{label}</Text>
      <View style={styles.wrap}>
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <Pressable
              key={option.value}
              onPress={() => onChange(selected && clearOnReselect ? ('' as T) : option.value)}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={`${label}, ${option.label}`}
              style={[styles.choice, selected && styles.choiceOn]}
            >
              <Text style={[styles.choiceText, selected && styles.choiceTextOn]}>{option.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  group: {
    marginBottom: spacing.lg,
  },
  groupLabel: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  choice: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
  },
  choiceOn: {
    backgroundColor: colors.tintSoft,
    borderColor: colors.tint,
  },
  choiceText: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  choiceTextOn: {
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
});

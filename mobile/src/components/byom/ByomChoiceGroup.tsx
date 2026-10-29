import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, font, radii, spacing } from '@/lib/theme';

export function ByomChoiceGroup<T extends string>({
  label,
  value,
  options,
  onChange,
  clearOnReselect = false,
  marked = false,
  hideLabel = false,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  /** A second tap on the selected chip clears it. The parent treats '' as none. */
  clearOnReselect?: boolean;
  /** Selected chip draws a check, matching the prop filter boards. */
  marked?: boolean;
  /** The parent draws the section title. The group label stays for VoiceOver. */
  hideLabel?: boolean;
}) {
  return (
    <View style={[styles.group, hideLabel && styles.groupTight]} accessibilityRole="radiogroup" accessibilityLabel={label}>
      {hideLabel ? null : <Text style={styles.groupLabel}>{label}</Text>}
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
              style={[styles.choice, selected && styles.choiceOn, selected && marked && styles.choiceMarked]}
            >
              <Text style={[styles.choiceText, selected && styles.choiceTextOn]}>
                {marked && selected ? `\u2713  ${option.label}` : option.label}
              </Text>
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
  groupTight: {
    marginBottom: 0,
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
  choiceMarked: {
    borderWidth: 2,
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

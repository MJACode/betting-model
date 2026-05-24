import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { StatChip } from '@/lib/playerStatChips';
import type { PlayerStatKey } from '@/hooks/usePlayerTrends';

interface Props {
  chips: StatChip[];
  value: PlayerStatKey;
  onChange: (key: PlayerStatKey) => void;
}

export function StatChipRow({ chips, value, onChange }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      {chips.map((c) => {
        const active = c.key === value;
        return (
          <Pressable
            key={c.key}
            onPress={() => onChange(c.key)}
            style={({ pressed }) => [
              styles.chip,
              active && styles.chipActive,
              pressed && styles.pressed,
            ]}
          >
            <Text style={[styles.chipText, active && styles.chipTextActive]}>{c.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: colors.noneSoft,
  },
  chipActive: {
    backgroundColor: colors.tint,
  },
  chipText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.textInverse,
  },
  pressed: { opacity: 0.7 },
});

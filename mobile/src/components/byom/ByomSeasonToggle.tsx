import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useByomSeason } from '@/hooks/useByomSeason';
import type { ByomSeasonScope } from '@/lib/byomRecord';
import { colors, font, radii, spacing } from '@/lib/theme';

const OPTIONS: { scope: ByomSeasonScope; label: string }[] = [
  { scope: 'all', label: 'All seasons' },
  { scope: 'current', label: 'This season' },
];

export function ByomSeasonToggle() {
  const { scope, setScope } = useByomSeason();
  return (
    <View style={styles.row} accessibilityRole="tablist">
      {OPTIONS.map((option) => {
        const selected = option.scope === scope;
        return (
          <Pressable
            key={option.scope}
            onPress={() => setScope(option.scope)}
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

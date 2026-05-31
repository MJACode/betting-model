import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
import { SPORTS, useSportFilter, type Sport } from '@/hooks/useSportFilter';

/**
 * Segmented MLB | WNBA control. Drives the global sport filter so the picks
 * screens show one sport at a time — WNBA picks stay visually separate from MLB.
 */
export function SportToggle() {
  const { sport, setSport } = useSportFilter();
  return (
    <View style={styles.wrap}>
      {SPORTS.map((s: Sport) => {
        const active = s === sport;
        return (
          <Pressable
            key={s}
            onPress={() => setSport(s)}
            style={({ pressed }) => [
              styles.segment,
              active && styles.segmentActive,
              pressed && styles.pressed,
            ]}
          >
            <Text style={[styles.label, active && styles.labelActive]}>{s}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    padding: 2,
    marginTop: spacing.sm,
  },
  segment: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm - 2,
  },
  segmentActive: {
    backgroundColor: colors.bgCard,
  },
  pressed: {
    opacity: 0.6,
  },
  label: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  labelActive: {
    color: colors.tint,
  },
});

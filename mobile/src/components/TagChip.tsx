import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, radii } from '@/lib/theme';

/**
 * A static label pill — the "model input" chip on the model detail screen and
 * on the Models tab's inputs card. Not a control: nothing to press, so it is
 * a View, unlike FilterChip. Lives here so the two surfaces cannot drift into
 * two chip styles (UX review, 2026-09-03).
 */
export function TagChip({ label }: { label: string }) {
  return (
    <View style={styles.chip}>
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  text: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
});

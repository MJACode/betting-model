import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
import { unitsSpeech } from '@/lib/a11y';

interface Props {
  label: string;
  value: string;
  caption?: string;
  tint?: string;
}

export function StatTile({ label, value, caption, tint }: Props) {
  return (
    // One VoiceOver stop per tile, with a units figure spoken as units
    // ("+3.21 units", not "+3.21 u"); a percent passes through unchanged.
    <View
      style={styles.tile}
      accessible
      accessibilityLabel={[label, unitsSpeech(value), caption ? unitsSpeech(caption) : null].filter(Boolean).join(', ')}
    >
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, tint ? { color: tint } : null]}>{value}</Text>
      {caption ? <Text style={styles.caption}>{caption}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  tile: {
    flex: 1,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    minHeight: 80,
    justifyContent: 'center',
  },
  label: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 4,
  },
  value: {
    fontSize: font.size.title3,
    color: colors.textPrimary,
    fontWeight: font.weight.semibold,
  },
  caption: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
});

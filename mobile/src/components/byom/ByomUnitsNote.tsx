import React from 'react';
import { StyleSheet, Text } from 'react-native';

import { BYOM_UNITS_COPY } from '@/lib/byomRecord';
import { colors, font, spacing } from '@/lib/theme';

export function ByomUnitsNote() {
  return <Text style={styles.note}>{BYOM_UNITS_COPY}</Text>;
}

const styles = StyleSheet.create({
  note: {
    fontSize: font.size.footnote,
    lineHeight: 18,
    color: colors.textSecondary,
    marginTop: spacing.md,
  },
});

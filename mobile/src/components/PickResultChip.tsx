import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, font, radii, spacing } from '@/lib/theme';
import type { PickResultView } from '@/lib/pickResult';

/**
 * The W/L/P badge's ink and wash — one table for the results recap and the
 * pick card, so the two can never drift (contrast, audit H2: 4.61 / 5.01 /
 * above 9:1 on their washes).
 */
export const RESULT_TONE: Record<'WIN' | 'LOSS' | 'PUSH', { label: string; color: string; bg: string }> = {
  WIN: { label: 'W', color: colors.betInk, bg: colors.betSoft },
  LOSS: { label: 'L', color: colors.avoidInk, bg: colors.avoidSoft },
  PUSH: { label: 'P', color: colors.textSecondary, bg: colors.noneSoft },
};

/**
 * "W +0.91u" beside the FINAL pill on a graded BET. The wash and ink are the
 * results recap's (RESULT_TONE, shared), and the size matches the status pill
 * beside it: on a finished card the result is the point. Spoken through the
 * card's own label, so this is hidden from VoiceOver.
 */
export function PickResultChip({ view }: { view: PickResultView }) {
  const tone = RESULT_TONE[view.result];
  return (
    <View
      style={[styles.chip, { backgroundColor: tone.bg }]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Text style={[styles.text, { color: tone.color }]}>
        {view.letter} {view.unitsText}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
    alignSelf: 'center',
  },
  text: {
    fontSize: font.size.micro,
    fontWeight: font.weight.semibold,
    fontVariant: ['tabular-nums'],
  },
});

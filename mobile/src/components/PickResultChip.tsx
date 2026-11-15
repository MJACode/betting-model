import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, font, radii } from '@/lib/theme';
import type { PickResultView } from '@/lib/pickResult';

/**
 * "W +0.91u" beside the FINAL pill on a graded BET. The wash and ink are the
 * results recap's (DailyResultsModal RESULT_STYLE, audit H2 contrast), so a W
 * here reads exactly like a W there. Spoken through the card's own label, so
 * this is hidden from VoiceOver.
 */
const TONE = {
  WIN: { color: colors.betInk, bg: colors.betSoft },
  LOSS: { color: colors.avoidInk, bg: colors.avoidSoft },
  PUSH: { color: colors.textSecondary, bg: colors.noneSoft },
} as const;

export function PickResultChip({ view }: { view: PickResultView }) {
  const tone = TONE[view.result];
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
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    alignSelf: 'center',
  },
  text: {
    fontSize: font.size.nano,
    fontWeight: font.weight.semibold,
    fontVariant: ['tabular-nums'],
  },
});

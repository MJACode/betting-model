/**
 * Matchup strength, Option A (Matt, 2026-10-28).
 *
 * Five equal segments, filled from the left. 5–4 green, 3 gray, 2–1 maroon,
 * empty #D1D1D6. The filled count is the meaning. Nothing in this component
 * is a word: the parent speaks "Matchup strength N of 5".
 */
import React from 'react';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { colors, font, strengthColor } from '@/lib/theme';

export const MATCHUP_BAR_COUNT = 5;

const SIZES = {
  board: { width: 8, height: 6, gap: 2, radius: 1 },
  chip: { width: 6, height: 7, gap: 2, radius: 1 },
} as const;

export function MatchupStrengthBar({
  filled,
  size = 'board',
  grow = false,
}: {
  filled: number;
  size?: keyof typeof SIZES;
  /**
   * Player detail and the stacked Anytime row have the width. The compact
   * column caps at 1.3 so five segments still fit in 64pt.
   */
  grow?: boolean;
}) {
  const { fontScale } = useWindowDimensions();
  const dim = SIZES[size];
  const scale = Math.min(grow ? 2 : 1.3, Math.max(1, Number.isFinite(fontScale) ? fontScale : 1));
  const n = Math.max(0, Math.min(MATCHUP_BAR_COUNT, Math.round(filled)));
  const fill = strengthColor(n);
  const gap = Math.round(dim.gap * scale);
  const width = Math.round(dim.width * scale);
  const height = Math.round(dim.height * scale);
  return (
    <View
      style={[styles.meter, { gap }]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {Array.from({ length: MATCHUP_BAR_COUNT }, (_, i) => (
        <View
          key={i}
          style={{
            width,
            height,
            borderRadius: dim.radius,
            backgroundColor: i < n ? fill : colors.matchupEmpty,
          }}
        />
      ))}
    </View>
  );
}

/** Bars and a plus, for a floor chip's summary and the active pill. */
export function MatchupFloorMark({
  filled,
  tone = 'secondary',
}: {
  filled: number;
  tone?: 'secondary' | 'tint';
}) {
  const plus = tone === 'tint' ? colors.tint : colors.textSecondary;
  return (
    <View
      style={styles.floor}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <MatchupStrengthBar filled={filled} size="chip" />
      <Text style={[styles.plus, { color: plus }]}>+</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  meter: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  floor: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  plus: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
});

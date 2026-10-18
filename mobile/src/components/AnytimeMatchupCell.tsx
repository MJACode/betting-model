/**
 * The Anytime TD matchup cell: five bars, a tier word, and "3rd easiest".
 * A dash names the reason. Colour is the grade ramp, and the word is always
 * there, so the bars are not the only signal.
 */
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import {
  ATD_COPY,
  ATD_MATCHUP_W,
  type AnytimeMatchupView,
  type MatchupTier,
} from '@/lib/anytimeMatchup';
import { colors, font } from '@/lib/theme';

const BAR_COUNT = 5;

function tierColor(tier: MatchupTier): string {
  if (tier === 'Easiest' || tier === 'Easy') return colors.gradeGood;
  if (tier === 'Average') return colors.gradeMid;
  return colors.gradeBad;
}

function Meter({ filled, color }: { filled: number; color: string }) {
  return (
    <View
      style={styles.meter}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {Array.from({ length: BAR_COUNT }, (_, i) => (
        <View
          key={i}
          style={[styles.bar, { backgroundColor: i < filled ? color : colors.separatorOpaque }]}
        />
      ))}
    </View>
  );
}

export function AnytimeMatchupCell({
  view,
  grow = false,
}: {
  view: AnytimeMatchupView;
  /** Large text: the column may grow so the tier word is not clipped. */
  grow?: boolean;
}) {
  if (view.kind === 'loading') {
    return (
      <View style={[styles.wrap, grow && styles.wrapGrow]} accessible accessibilityLabel={ATD_COPY.loadingSpoken}>
        <Text style={styles.dash}>—</Text>
        <Text style={styles.reason} numberOfLines={1}>
          {ATD_COPY.loadingLabel}
        </Text>
      </View>
    );
  }
  if (view.kind === 'unavailable') {
    return (
      <View style={[styles.wrap, grow && styles.wrapGrow]} accessible accessibilityLabel={ATD_COPY.unavailableSpoken}>
        <Text style={styles.dash}>—</Text>
        <Text style={styles.reason} numberOfLines={1}>
          {ATD_COPY.unavailableLabel}
        </Text>
      </View>
    );
  }
  if (view.kind === 'gap') {
    return (
      <View style={[styles.wrap, grow && styles.wrapGrow]} accessible accessibilityLabel={view.spoken}>
        <Text style={styles.dash}>—</Text>
        <Text style={styles.reason} numberOfLines={1}>
          {view.label}
        </Text>
      </View>
    );
  }
  const color = tierColor(view.tier);
  return (
    <View style={[styles.wrap, grow && styles.wrapGrow]} accessible accessibilityLabel={view.spoken}>
      <Meter filled={view.bars} color={color} />
      <Text style={[styles.tier, { color }]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
        {view.tier}
      </Text>
      <Text style={styles.rank} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}>
        {view.line}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: ATD_MATCHUP_W,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  wrapGrow: {
    width: undefined,
    minWidth: ATD_MATCHUP_W,
    maxWidth: 140,
    flexShrink: 1,
  },
  meter: {
    flexDirection: 'row',
    gap: 2,
    marginBottom: 2,
  },
  bar: {
    width: 8,
    height: 6,
    borderRadius: 1,
  },
  tier: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    textAlign: 'right',
  },
  rank: {
    fontSize: font.size.nano,
    color: colors.textSecondary,
    textAlign: 'right',
  },
  dash: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
    textAlign: 'right',
  },
  reason: {
    fontSize: font.size.nano,
    color: colors.textSecondary,
    textAlign: 'right',
  },
});

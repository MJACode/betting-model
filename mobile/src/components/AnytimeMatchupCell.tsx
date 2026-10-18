/**
 * The Anytime TD matchup cell: five bars, a tier word, and "3rd easiest"
 * (or "3rd toughest" from the other end). A dash names the reason. Colour
 * is the grade ramp, and the word is always there, so the bars are not the
 * only signal. The cell itself opens the explainer. The header has no icon.
 */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  ATD_COPY,
  ATD_MATCHUP_W,
  stackedMatchupLine,
  type AnytimeMatchupView,
  type MatchupTier,
} from '@/lib/anytimeMatchup';
import { colors, font } from '@/lib/theme';

const BAR_COUNT = 5;

function tierColor(tier: MatchupTier): string {
  if (tier === 'Great' || tier === 'Good') return colors.gradeGood;
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
          style={[styles.bar, { backgroundColor: i < filled ? color : colors.none }]}
        />
      ))}
    </View>
  );
}

export function AnytimeMatchupCell({
  view,
  fullWidth = false,
  onExplain,
}: {
  view: AnytimeMatchupView;
  /** Large text: the matchup sits on its own line, as wide as the row. */
  fullWidth?: boolean;
  onExplain: () => void;
}) {
  const spoken =
    view.kind === 'loading' ? ATD_COPY.loadingSpoken
    : view.kind === 'unavailable' ? ATD_COPY.unavailableSpoken
    : view.kind === 'gap' ? view.spoken
    : view.spoken;
  const gapLabel =
    view.kind === 'loading' ? ATD_COPY.loadingLabel
    : view.kind === 'unavailable' ? ATD_COPY.unavailableLabel
    : view.kind === 'gap' ? view.label
    : '';
  return (
    <Pressable
      onPress={onExplain}
      accessibilityRole="button"
      accessibilityLabel={spoken}
      accessibilityHint={ATD_COPY.explainHint}
      style={({ pressed }) => [styles.wrap, fullWidth && styles.wrapFull, pressed && styles.pressed]}
    >
      {view.kind === 'rank' ? (
        fullWidth ? (
          // One line, the width of the row. A right-aligned tier over the
          // rank clipped both at 2× ("Tough…", "5th easie…").
          <Text style={[styles.lineFull, { color: tierColor(view.tier) }]} numberOfLines={2}>
            {stackedMatchupLine(view.tier, view.line)}
          </Text>
        ) : (
          <>
            <Meter filled={view.bars} color={tierColor(view.tier)} />
            <Text
              style={[styles.tier, { color: tierColor(view.tier) }]}
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.75}
            >
              {view.tier}
            </Text>
            <Text
              style={styles.rank}
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.8}
            >
              {view.line}
            </Text>
          </>
        )
      ) : fullWidth ? (
        <Text style={styles.lineFull} numberOfLines={2}>
          {`— ${gapLabel}`}
        </Text>
      ) : (
        <>
          <Text style={styles.dash}>—</Text>
          <Text style={styles.reason} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
            {gapLabel}
          </Text>
        </>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: ATD_MATCHUP_W,
    minHeight: 44,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  wrapFull: {
    width: '100%',
    maxWidth: undefined,
    alignSelf: 'stretch',
    alignItems: 'flex-start',
  },
  lineFull: {
    width: '100%',
    textAlign: 'left',
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  pressed: { opacity: 0.65 },
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

/**
 * The Anytime TD matchup cell. Five bars, filled from the left. No tier word
 * and no rank line — the filled count is the strength (Matt, 2026-10-28,
 * Option A). A status word (Bye, No game, Not playing) is text, never a bar.
 * No rank is a dash. The cell opens the explainer.
 */
import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';

import { MatchupStrengthBar } from '@/components/MatchupStrengthBar';
import {
  ATD_COPY,
  ATD_MATCHUP_W,
  type AnytimeMatchupView,
} from '@/lib/anytimeMatchup';
import { colors, font } from '@/lib/theme';

function statusText(view: Exclude<AnytimeMatchupView, { kind: 'rank' }>): string {
  if (view.kind === 'loading') return ATD_COPY.loadingLabel;
  if (view.kind === 'unavailable') return ATD_COPY.unavailableLabel;
  // Unknown defense is a dash, never a hollow bar and never a weak grade.
  if (view.reason === 'too_early') return '—';
  return view.label;
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
    : view.spoken;
  return (
    <Pressable
      onPress={onExplain}
      accessibilityRole="button"
      accessibilityLabel={spoken}
      accessibilityHint={ATD_COPY.explainHint}
      style={({ pressed }) => [styles.wrap, fullWidth && styles.wrapFull, pressed && styles.pressed]}
    >
      {view.kind === 'rank' ? (
        <MatchupStrengthBar filled={view.bars} grow={fullWidth} />
      ) : (
        <Text
          style={[styles.status, fullWidth && styles.statusFull]}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.7}
        >
          {statusText(view)}
        </Text>
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
    justifyContent: 'flex-end',
    paddingBottom: 0,
  },
  pressed: { opacity: 0.65 },
  status: {
    maxWidth: '100%',
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    textAlign: 'right',
  },
  statusFull: {
    width: '100%',
    textAlign: 'left',
  },
});

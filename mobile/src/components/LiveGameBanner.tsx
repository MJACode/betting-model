// LiveGameBanner — Phase 5 scaffolding.
// Compact in-progress game banner: matchup, score, and inning.
// Will read real inning data from a future useLiveGameStates hook that
// subscribes to live_game_state once the backend poller is running in prod.

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, spacing } from '@/lib/theme';
import type { GameRow } from '@/types';

interface Props {
  game: GameRow;
  inning?: number | null;
  inningHalf?: 'top' | 'bottom' | null;
}

export function LiveGameBanner({ game, inning, inningHalf }: Props) {
  const awayScore = game.away_score ?? '-';
  const homeScore = game.home_score ?? '-';
  const inningLabel =
    inning != null
      ? `${inningHalf === 'top' ? 'Top' : inningHalf === 'bottom' ? 'Bot' : ''} ${inning}`.trim()
      : 'LIVE';

  return (
    <View style={styles.row}>
      <View style={styles.matchup}>
        <Text style={styles.team}>
          {game.away_team} {awayScore}
        </Text>
        <Text style={styles.at}>@</Text>
        <Text style={styles.team}>
          {game.home_team} {homeScore}
        </Text>
      </View>
      <View style={styles.inningPill}>
        <Text style={styles.inningText}>{inningLabel}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: 12,
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  matchup: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  team: { color: colors.textPrimary, fontSize: font.size.body, fontWeight: font.weight.semibold },
  at: { color: colors.textTertiary, fontSize: font.size.body, marginHorizontal: spacing.xs },
  inningPill: {
    backgroundColor: colors.tint,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: 8,
  },
  inningText: { color: colors.textInverse, fontSize: font.size.footnote, fontWeight: font.weight.bold },
});

// LiveGameBanner — compact in-progress game banner for the Live tab:
// matchup, live score, inning/outs, and who's on base.
//
// Score and inning come from v_live_game_state_latest (the live poller's
// freshest snapshot, ~15s cadence). `games.home_score/away_score` stay NULL
// until next-morning settlement, so the live row is the only in-game source.

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { basesLabel, inningLong } from '@/lib/format';
import { colors, font, spacing } from '@/lib/theme';
import type { GameRow, LiveGameStateRow } from '@/types';

interface Props {
  game: GameRow;
  /** Freshest live snapshot. Null when the poller has no row for this game. */
  live?: LiveGameStateRow | null;
}

export function LiveGameBanner({ game, live }: Props) {
  // Prefer the live feed; fall back to settled scores, then to a dash.
  const awayScore = live?.away_score ?? game.away_score ?? '-';
  const homeScore = live?.home_score ?? game.home_score ?? '-';
  const half = live?.inning_half === 'top' || live?.inning_half === 'bottom' ? live.inning_half : null;
  const inningLabel = inningLong(live?.inning ?? null, half, live?.outs ?? null) ?? 'LIVE';
  const bases = basesLabel(live?.bases_state ?? null);

  return (
    <View style={styles.row}>
      <View style={styles.left}>
        <View style={styles.matchup}>
          <Text style={styles.team}>
            {game.away_team} {awayScore}
          </Text>
          <Text style={styles.at}>@</Text>
          <Text style={styles.team}>
            {game.home_team} {homeScore}
          </Text>
        </View>
        {bases ? <Text style={styles.bases}>{bases}</Text> : null}
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
  left: { flexShrink: 1, marginRight: spacing.sm },
  matchup: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  team: { color: colors.textPrimary, fontSize: font.size.body, fontWeight: font.weight.semibold },
  at: { color: colors.textTertiary, fontSize: font.size.body, marginHorizontal: spacing.xs },
  bases: { color: colors.textTertiary, fontSize: font.size.caption, marginTop: 2 },
  inningPill: {
    backgroundColor: colors.info, // status, not a control
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: 8,
  },
  inningText: { color: colors.textInverse, fontSize: font.size.footnote, fontWeight: font.weight.bold },
});

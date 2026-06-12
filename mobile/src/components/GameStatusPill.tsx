import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { gameDayLabelET, gameStatus, type GameStatus } from '@/lib/format';
import { colors, font, radii } from '@/lib/theme';
import type { GameRow } from '@/types';

interface Props {
  game: GameRow | null | undefined;
  /** When true, render compact pill suitable for card headers. */
  compact?: boolean;
}

export function GameStatusPill({ game, compact = true }: Props) {
  const status = gameStatus(game);

  if (status.kind === 'pre') {
    if (!status.timeLabel) return null;
    // Future-day events (the upcoming UFC card) get a day prefix: "Sat 6/14 · 10:00 PM ET"
    const dayLabel = gameDayLabelET(game?.commence_time);
    const label = dayLabel ? `${dayLabel} · ${status.timeLabel}` : status.timeLabel;
    return <Text style={compact ? styles.timeCompact : styles.time}>{label}</Text>;
  }

  if (status.kind === 'live') {
    const scoreStr = scoreLabel(status.awayScore, status.homeScore);
    return (
      <View style={styles.row}>
        {scoreStr ? <Text style={styles.scoreText}>{scoreStr}</Text> : null}
        <View style={[styles.pill, styles.livePill]}>
          <View style={styles.liveDot} />
          <Text style={styles.liveText}>LIVE</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.row}>
      <Text style={styles.scoreText}>{scoreLabel(status.awayScore, status.homeScore)}</Text>
      <View style={[styles.pill, styles.finalPill]}>
        <Text style={styles.finalText}>FINAL</Text>
      </View>
    </View>
  );
}

function scoreLabel(away: number | null, home: number | null): string {
  if (away == null || home == null) return '';
  return `${away}–${home}`;
}

const styles = StyleSheet.create({
  time: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
  },
  timeCompact: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  scoreText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.pill,
    gap: 4,
  },
  livePill: {
    backgroundColor: colors.avoidSoft,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.avoid,
  },
  liveText: {
    fontSize: 10,
    fontWeight: font.weight.bold,
    color: colors.avoid,
    letterSpacing: 0.5,
  },
  finalPill: {
    backgroundColor: colors.noneSoft,
  },
  finalText: {
    fontSize: 10,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
    letterSpacing: 0.5,
  },
});

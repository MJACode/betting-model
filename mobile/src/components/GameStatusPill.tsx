import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { gameDayLabelET, gameStatus, inningLong, inningShort } from '@/lib/format';
import { LiveDot } from '@/components/LiveDot';
import { colors, font, radii } from '@/lib/theme';
import type { GameRow, LiveGameStateRow } from '@/types';

interface Props {
  game: GameRow | null | undefined;
  /** When true, render compact pill suitable for card headers. */
  compact?: boolean;
  /**
   * Freshest live snapshot for this game (v_live_game_state_latest). When
   * present, an in-progress game shows the real score + inning next to LIVE
   * instead of a bare badge — `games` scores don't land until settlement.
   */
  live?: LiveGameStateRow | null;
}

export function GameStatusPill({ game, compact = true, live }: Props) {
  const status = gameStatus(game, live);

  if (status.kind === 'pre') {
    if (!status.timeLabel) return null;
    // Future-day events (the upcoming UFC card) get a day prefix: "Sat 6/14 · 10:00 PM ET"
    const dayLabel = gameDayLabelET(game?.commence_time);
    const label = dayLabel ? `${dayLabel} · ${status.timeLabel}` : status.timeLabel;
    return <Text style={compact ? styles.timeCompact : styles.time}>{label}</Text>;
  }

  if (status.kind === 'live') {
    const scoreStr = scoreLabel(status.awayScore, status.homeScore);
    // Compact (card header): "T5". Roomy (detail): "Top 5th · 2 out".
    const inningStr = compact
      ? inningShort(status.inning, status.inningHalf)
      : inningLong(status.inning, status.inningHalf, status.outs);
    return (
      <View style={styles.row}>
        {scoreStr ? <Text style={styles.scoreText}>{scoreStr}</Text> : null}
        {inningStr ? <Text style={styles.inningText}>{inningStr}</Text> : null}
        <View style={[styles.pill, styles.livePill]}>
          <LiveDot />
          <Text style={styles.liveText}>LIVE</Text>
        </View>
      </View>
    );
  }

  // Over, but we have no score to show — render nothing rather than a stale
  // LIVE badge or a FINAL pill with a blank score.
  if (status.kind === 'ended') return null;

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
  inningText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.medium,
    color: colors.textSecondary,
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

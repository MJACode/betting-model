import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  gameDayLabelET,
  gameStatus,
  inningLong,
  inningShort,
  postponedLabel,
  postponedSpeech,
  postponedStart,
} from '@/lib/format';
import { LiveDot } from '@/components/LiveDot';
import { gameStatusSpeech } from '@/lib/a11y';
import { colors, font, opacity, radii } from '@/lib/theme';
import { feedView, type ScoreboardFeed } from '@/lib/scoreboard';
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
  /**
   * The start the pick was made for (its game_time). A game since moved more
   * than two days past it reads "Postponed · now Sat, 12/5", not the new date
   * as if it were simply scheduled then.
   */
  scheduledStart?: string | null;
  /**
   * The Scoreboard tab's own feed for this game (live_scoreboard / the NCAAF
   * scoreboard): every sport but MLB, whose `live` row carries the inning.
   * When fresh it supplies the score and clock — "35–39 · Half" — that a bare
   * LIVE badge used to stand in for (Matt, 2026-11-24).
   */
  feed?: ScoreboardFeed | null;
  /**
   * Opens this game on the scoreboard (Matt, 2026-11-24). Only a started game
   * takes the tap: before the start the pill is a time, and there is no score
   * to go and look at.
   */
  onPress?: () => void;
}

export function GameStatusPill({ game, compact = true, live, scheduledStart, feed, onPress }: Props) {
  const fromFeed = feedView(game ?? null, feed);
  if (fromFeed) {
    const body = fromFeed.kind === 'live' ? (
      <View style={styles.row}>
        {fromFeed.score ? <Text style={styles.scoreText}>{fromFeed.score}</Text> : null}
        {fromFeed.clock ? <Text style={styles.inningText}>{fromFeed.clock}</Text> : null}
        <View style={[styles.pill, styles.livePill]}>
          <LiveDot />
          <Text style={styles.liveText}>LIVE</Text>
        </View>
      </View>
    ) : (
      <View style={styles.row}>
        <Text style={styles.scoreText}>{fromFeed.score}</Text>
        <View style={[styles.pill, styles.finalPill]}>
          <Text style={styles.finalText}>FINAL</Text>
        </View>
      </View>
    );
    return wrap(body, fromFeed.speech, onPress);
  }
  const inner = statusBody(game, compact, live, scheduledStart);
  if (!inner) return null;
  return inner.started ? wrap(inner.node, inner.speech, onPress) : inner.node;
}

/** A started game's pill is a button when the caller can open the game. */
function wrap(node: React.ReactElement, speech: string, onPress?: () => void): React.ReactElement {
  if (!onPress) {
    return (
      <View accessible accessibilityRole="text" accessibilityLabel={speech}>
        {node}
      </View>
    );
  }
  return (
    <Pressable
      onPress={onPress}
      // The pill is ~17pt tall; 14pt above and below brings the target to
      // ~45pt. Sideways only 4pt: the signals row spaces chips 4pt apart, and
      // a wider slop would steal taps from the Sharp Score pill (UX review).
      hitSlop={{ top: 14, bottom: 14, left: 4, right: 4 }}
      accessibilityRole="button"
      accessibilityLabel={speech}
      accessibilityHint="Opens this game on the scoreboard"
      style={({ pressed }) => [styles.row, pressed ? styles.pressed : null]}
    >
      {node}
      {/* At rest, the chevron is what says this pill goes somewhere the rest
          of the card does not (UX review: NBA app's "FINAL ▸"). */}
      <Ionicons
        name="chevron-forward"
        size={12}
        color={colors.textSecondary}
        accessibilityElementsHidden
        importantForAccessibility="no"
      />
    </Pressable>
  );
}

function statusBody(
  game: GameRow | null | undefined,
  compact: boolean,
  live: LiveGameStateRow | null | undefined,
  scheduledStart: string | null | undefined,
): { node: React.ReactElement; speech: string; started: boolean } | null {
  const movedTo = postponedStart(game, scheduledStart);
  if (movedTo) {
    return {
      started: false,
      speech: postponedSpeech(movedTo),
      node: (
        <Text style={compact ? styles.timeCompact : styles.time} accessibilityLabel={postponedSpeech(movedTo)}>
          {postponedLabel(movedTo)}
        </Text>
      ),
    };
  }
  const status = gameStatus(game, live);
  // Spoken form (audit M22): "Live, bottom 9th, 3 to 2", not "3 dash 2 B9 live".
  const spoken = gameStatusSpeech(status, gameDayLabelET(game?.commence_time));

  if (status.kind === 'pre') {
    if (!status.timeLabel) return null;
    // Future-day events (the upcoming UFC card) get a day prefix: "Sat 6/14 · 10:00 PM ET"
    const dayLabel = gameDayLabelET(game?.commence_time);
    const label = dayLabel ? `${dayLabel} · ${status.timeLabel}` : status.timeLabel;
    return {
      started: false,
      speech: spoken ?? label,
      node: (
        <Text style={compact ? styles.timeCompact : styles.time} accessibilityLabel={spoken ?? undefined}>
          {label}
        </Text>
      ),
    };
  }

  if (status.kind === 'live') {
    const scoreStr = scoreLabel(status.awayScore, status.homeScore);
    // Compact (card header): "T5". Roomy (detail): "Top 5th · 2 out".
    const inningStr = compact
      ? inningShort(status.inning, status.inningHalf)
      : inningLong(status.inning, status.inningHalf, status.outs);
    return {
      started: true,
      speech: spoken ?? 'Live',
      node: (
        <View style={styles.row}>
          {scoreStr ? <Text style={styles.scoreText}>{scoreStr}</Text> : null}
          {inningStr ? <Text style={styles.inningText}>{inningStr}</Text> : null}
          <View style={[styles.pill, styles.livePill]}>
            <LiveDot />
            <Text style={styles.liveText}>LIVE</Text>
          </View>
        </View>
      ),
    };
  }

  // Over, but we have no score to show — render nothing rather than a stale
  // LIVE badge or a FINAL pill with a blank score.
  if (status.kind === 'ended') return null;

  return {
    started: true,
    speech: spoken ?? 'Final',
    node: (
      <View style={styles.row}>
        <Text style={styles.scoreText}>{scoreLabel(status.awayScore, status.homeScore)}</Text>
        <View style={[styles.pill, styles.finalPill]}>
          <Text style={styles.finalText}>FINAL</Text>
        </View>
      </View>
    ),
  };
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
  // micro (11pt, the iOS caption2 floor) and avoidInk: the literal 10 in
  // `avoid` was 3.10:1 on avoidSoft. The LiveDot keeps the bright red (M22).
  liveText: {
    fontSize: font.size.micro,
    fontWeight: font.weight.bold,
    color: colors.avoidInk,
    letterSpacing: 0.5,
  },
  pressed: {
    opacity: opacity.pressed,
  },
  finalPill: {
    backgroundColor: colors.noneSoft,
  },
  finalText: {
    fontSize: font.size.micro,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
    letterSpacing: 0.5,
  },
});

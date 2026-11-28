import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { GameStatusPill } from '@/components/GameStatusPill';
import { decisionOdds } from '@/lib/decisionPrice';
import { formatAmerican, gameStatus, isVersusSport } from '@/lib/format';
import { gameStatusSpeech } from '@/lib/a11y';
import { bookLabel, pickTitleText, storedQuoteBook } from '@/lib/markets';
import { feedView, type ScoreboardFeed } from '@/lib/scoreboard';
import { trueMinus } from '@/lib/signalsCard';
import { colors, font, radii, spacing, opacity, cardDense } from '@/lib/theme';
import type { EnrichedPick, LiveGameStateRow } from '@/types';

interface Props {
  item: EnrichedPick;
  kind: 'live' | 'final';
  liveState: LiveGameStateRow | null;
  scoreFeed: ScoreboardFeed | null;
  tracked: boolean;
  onPress: () => void;
  onToggleTrack: () => void;
  onRecord: () => void;
  teamAbbrevs?: ReadonlyMap<string, string> | null;
}

function shortTeam(name: string, abbrevs?: ReadonlyMap<string, string> | null): string {
  const hit = abbrevs?.get(name);
  return hit && hit.length > 0 ? hit : name;
}

/**
 * One compact row inside the Started group (Matt, 2026-11-27). The pick at
 * its price, then the matchup with the score pill. Track on the right; a
 * final game links to Record instead. The row itself opens Pick Detail.
 */
export function StartedPickRow({
  item,
  kind,
  liveState,
  scoreFeed,
  tracked,
  onPress,
  onToggleTrack,
  onRecord,
  teamAbbrevs,
}: Props) {
  const { pick, game } = item;
  const price = decisionOdds(pick);
  const priceText = price == null ? '' : trueMinus(`${formatAmerican(price)} ${bookLabel(storedQuoteBook(pick))}`);
  const title = trueMinus(pickTitleText(pick).trim());
  const sport = game?.sport ?? pick.sport;
  const away = shortTeam(game?.away_team ?? '', teamAbbrevs);
  const home = shortTeam(game?.home_team ?? '', teamAbbrevs);
  const matchup = !away || away === 'FIELD'
    ? home
    : !home
      ? away
      : `${away} ${isVersusSport(sport) ? 'vs' : '@'} ${home}`;
  const statusWord = kind === 'final' ? 'Final' : 'Live';
  const statusSpeech = feedView(game, scoreFeed)?.speech
    ?? gameStatusSpeech(gameStatus(game, liveState));

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${title}${priceText ? `, ${priceText}` : ''}. ${matchup}. ${statusSpeech || statusWord}`}
      accessibilityHint="Opens the pick"
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <View style={styles.body}>
        <View style={styles.titleRow}>
          <Text style={styles.title} numberOfLines={1}>{title}</Text>
          {priceText ? <Text style={styles.price}>{priceText}</Text> : null}
        </View>
        <View style={styles.meta}>
          {matchup ? (
            <Text style={styles.matchup} numberOfLines={1}>{matchup}</Text>
          ) : null}
          <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            <GameStatusPill
              game={game}
              live={liveState}
              feed={scoreFeed}
              scheduledStart={pick.game_time}
            />
          </View>
        </View>
      </View>
      {kind === 'final' ? (
        <Pressable
          onPress={onRecord}
          accessibilityRole="button"
          accessibilityLabel="Record"
          accessibilityHint="Opens Record"
          hitSlop={{ top: 8, bottom: 8, left: 6, right: 6 }}
          style={({ pressed }) => [styles.action, pressed && styles.pressed]}
        >
          <Text style={styles.actionText}>Record</Text>
          <Ionicons name="chevron-forward" size={14} color={colors.tint} />
        </Pressable>
      ) : (
        <Pressable
          onPress={onToggleTrack}
          accessibilityRole="button"
          accessibilityState={{ selected: tracked }}
          accessibilityLabel={tracked ? 'Tracked. Stop tracking this bet.' : 'Track this bet'}
          hitSlop={{ top: 8, bottom: 8, left: 6, right: 6 }}
          style={({ pressed }) => [styles.action, tracked && styles.actionOn, pressed && styles.pressed]}
        >
          <Ionicons
            name={tracked ? 'checkmark' : 'notifications-outline'}
            size={14}
            color={colors.tint}
          />
          <Text style={styles.actionText}>{tracked ? 'Tracked' : 'Track'}</Text>
        </Pressable>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    ...cardDense,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    minHeight: 56,
  },
  body: { flex: 1, minWidth: 0, gap: 2 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  title: {
    flexShrink: 1,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  price: {
    flexShrink: 0,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  meta: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, minWidth: 0 },
  matchup: {
    flexShrink: 1,
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  action: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    minHeight: 36,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.tint,
  },
  actionOn: { backgroundColor: colors.tintSoft },
  actionText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  pressed: { opacity: opacity.pressed },
});

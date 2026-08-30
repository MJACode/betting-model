import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { PlayerNewsSheet } from '@/components/PlayerNewsSheet';
import type { PlayerNewsState } from '@/hooks/usePlayerNews';
import { colors, radii, spacing } from '@/lib/theme';

/**
 * The top-right newspaper icon on a prop player's screens, and the sheet it
 * opens. One component so the player detail screen and the pick detail screen
 * cannot drift apart on where news lives or what it looks like.
 *
 * It renders NOTHING when the feed has no note about this player. An icon that
 * opens an empty sheet teaches people not to tap it, and coverage is uneven by
 * construction: the free provider writes about whoever is newsworthy, so a
 * fifth starter may genuinely have nothing. The green dot marks a note inside
 * the last NEWS_FRESH_HOURS — that is the one that might change a bet.
 */
export function PlayerNewsButton({
  playerName,
  subtitle,
  news,
}: {
  playerName: string;
  subtitle?: string | null;
  news: PlayerNewsState;
}) {
  const [open, setOpen] = useState(false);

  if (news.news.length === 0) return null;

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        hitSlop={8}
        style={styles.button}
        accessibilityRole="button"
        accessibilityLabel={`Recent news for ${playerName}`}
      >
        <Ionicons name="newspaper-outline" size={20} color={colors.tint} />
        {news.fresh ? <View style={styles.dot} /> : null}
      </Pressable>

      <PlayerNewsSheet
        visible={open}
        onClose={() => setOpen(false)}
        playerName={playerName}
        subtitle={subtitle}
        news={news.news}
        loading={news.loading}
        error={news.error}
      />
    </>
  );
}

const styles = StyleSheet.create({
  button: {
    width: 36,
    height: 36,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dot: {
    position: 'absolute',
    top: spacing.xs,
    right: spacing.xs,
    width: 8,
    height: 8,
    borderRadius: radii.pill,
    backgroundColor: colors.bet,
    borderWidth: 1,
    borderColor: colors.bgElevated,
  },
});

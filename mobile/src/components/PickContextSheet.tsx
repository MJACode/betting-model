/**
 * A bottom-sheet "quick peek" at the rich context behind a pick — Statcast /
 * umpire / lineup (props), team or player form, and the UFC tale of the tape —
 * one tap from the list instead of a full navigation to PickDetail.
 *
 * It reuses the SAME context cards and hooks as PickDetailScreen
 * (PropContextCard / TrendStrip / TaleOfTheTapeCard, usePropContext /
 * useTeamTrends / usePlayerTrends). The hooks fetch per pick, so the sheet is
 * only mounted while open (`visible && <PickContextSheet/>` at the call site) —
 * that's why this lives in a sheet and not inline on every card in the list.
 */

import React, { useMemo } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { PropContextCard } from '@/components/PropContextCard';
import { TaleOfTheTapeCard } from '@/components/TaleOfTheTapeCard';
import { TrendStrip } from '@/components/TrendStrip';
import { usePlayerTrends, type PlayerStatKey } from '@/hooks/usePlayerTrends';
import { usePropContext } from '@/hooks/usePropContext';
import { useTeamTrends } from '@/hooks/useTeamTrends';
import { MODEL_META } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick } from '@/types';

/** Picks that have something to show in the sheet. Golf/other have no run-based
 *  trends or prop context, so the affordance is hidden for them. */
export function pickHasContext(pick: EnrichedPick['pick'], sport?: string | null): boolean {
  const meta = MODEL_META[pick.model_id];
  const sp = sport ?? pick.sport;
  if (sp === 'UFC') return true;
  if (meta?.type === 'pitcher_prop' || meta?.type === 'batter_prop') return true;
  if (meta?.type === 'game' && sp !== 'GOLF') return true;
  return false;
}

export function PickContextSheet({
  enriched,
  visible,
  onClose,
}: {
  enriched: EnrichedPick;
  visible: boolean;
  onClose: () => void;
}) {
  const { pick, game } = enriched;
  const meta = MODEL_META[pick.model_id];

  const isPitcherProp = meta?.type === 'pitcher_prop';
  const isBatterProp = meta?.type === 'batter_prop';
  const isGameModel = meta?.type === 'game';
  const isUfc = game?.sport === 'UFC' || pick.sport === 'UFC';
  const isGolf = game?.sport === 'GOLF' || pick.sport === 'GOLF';
  const showTeamTrends = isGameModel && !isUfc && !isGolf;

  // Mirror PickDetailScreen's player-name parse: "Blake Snell Over 5.5 Ks".
  const playerName = useMemo(() => {
    if (!isPitcherProp && !isBatterProp) return null;
    const m = pick.pick_label.match(/^([A-Za-z .'\-]+?)\s+(?:Over|Under)\s/);
    return m ? m[1] : null;
  }, [isPitcherProp, isBatterProp, pick.pick_label]);

  const statKey = (meta?.statKey ?? null) as PlayerStatKey | null;

  const homeTrends = useTeamTrends(
    showTeamTrends ? game?.home_team ?? null : null,
    pick.game_date,
  );
  const awayTrends = useTeamTrends(
    showTeamTrends ? game?.away_team ?? null : null,
    pick.game_date,
  );
  const propContext = usePropContext(pick);
  const playerTrends = usePlayerTrends({
    playerId: pick.player_id,
    playerName: pick.player_id ? null : playerName,
    beforeDate: pick.game_date,
    statKey: isPitcherProp || isBatterProp ? statKey : null,
  });

  const loading =
    playerTrends.loading || homeTrends.loading || awayTrends.loading || propContext.loading;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.sheet}>
        <View style={styles.handleRow}>
          <Text style={styles.title}>{pick.pick_label}</Text>
          <Pressable onPress={onClose} hitSlop={8}>
            <Ionicons name="close" size={22} color={colors.textSecondary} />
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={styles.body}>
          <PropContextCard pick={pick} context={propContext} />

          {isUfc && game ? (
            <TaleOfTheTapeCard
              awayName={game.away_team}
              homeName={game.home_team}
              gameDate={pick.game_date}
            />
          ) : null}

          {showTeamTrends && game ? (
            <>
              <TrendStrip title={`${game.home_team} (home) form`} trends={homeTrends.trends} mode="team" />
              <TrendStrip title={`${game.away_team} (away) form`} trends={awayTrends.trends} mode="team" />
            </>
          ) : null}

          {(isPitcherProp || isBatterProp) && (pick.player_id || playerName) ? (
            <TrendStrip
              title={`${playerName ?? 'Player'} — recent form`}
              trends={playerTrends.trends}
              mode="player"
              unit={meta?.statLabel ?? ''}
            />
          ) : null}

          {!loading ? (
            <Text style={styles.footnote}>Tap the card for the full breakdown.</Text>
          ) : null}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: '#00000055',
  },
  sheet: {
    maxHeight: '72%',
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
  },
  handleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  title: {
    flex: 1,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  body: {
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
  },
  footnote: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.md,
  },
});

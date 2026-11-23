/**
 * "Our pick" on the matchup page (screens/ScoreboardGameScreen).
 *
 * Its own component so the day's picks board is read ONLY where the page is a
 * matchup (lib/gameMatchup hasMatchupView). Mounted from the screen, the hook
 * ran on every game page and read a whole day's board for an NFL or MLB game
 * just to throw it away (PR #1595 review, M1).
 *
 * The cards are the Signals board's own: the same hook Picks reads, cut by
 * the same filters, never a lean below the bar (Matt, 2026-11-23: "No pick,
 * just stats in their matchup").
 */
import React, { useEffect, useMemo, useRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';

import { ErrorBanner } from '@/components/ErrorState';
import { Section, SectionHeading } from '@/components/MatchupSections';
import { PickCard } from '@/components/PickCard';
import { useThresholdsRevision } from '@/hooks/useActionThresholds';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useTrackedBets } from '@/hooks/useTrackedBets';
import { betslipPlayerFromPick } from '@/lib/betslipGuard';
import { REFRESH_TIMES } from '@/lib/format';
import { gamePicks } from '@/lib/gameMatchup';
import { slipKeyForPick } from '@/lib/parlay';
import { isPausedForDisplay, isUnlockedPreview, passesActionFilter, passesRecordFilter } from '@/lib/thresholds';
import { colors, font, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function MatchupPicks({
  gameId,
  gameDate,
  refreshNonce,
  onLoadingChange,
}: {
  gameId: string;
  gameDate: string;
  /** Bumped by the page's pull to refresh. */
  refreshNonce: number;
  /** The page's pull spinner waits on this read too. Must be stable (a
   *  state setter): the unmount cleanup is keyed on it. */
  onLoadingChange: (loading: boolean) => void;
}) {
  const navigation = useNavigation<Nav>();
  const today = useTodayPicks(gameDate);
  const thresholdsRevision = useThresholdsRevision();
  const tracked = useTrackedBets();
  const slip = useParlaySlip();

  // A pull refreshes the board; the first render is not a pull.
  const lastNonce = useRef(refreshNonce);
  useEffect(() => {
    if (refreshNonce === lastNonce.current) return;
    lastNonce.current = refreshNonce;
    today.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshNonce]);
  useEffect(() => {
    onLoadingChange(today.loading);
  }, [today.loading, onLoadingChange]);
  // Unmounted mid-read: the page must not wait on it forever.
  useEffect(() => () => onLoadingChange(false), [onLoadingChange]);

  const picks = useMemo(
    () =>
      gamePicks(gameId, today.data, today.finishedData, {
        action: (d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick),
        record: (d) => passesRecordFilter(d.pick) && !isUnlockedPreview(d.pick),
      }),
    // thresholdsRevision: the action filter reads a module store.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [gameId, today.data, today.finishedData, thresholdsRevision],
  );
  // Any row for this game on its day, BET or not: with none, the models have
  // not scored it yet, which is not the same answer as "no pick" (UX review).
  const scored = useMemo(
    () => [...today.data, ...today.pausedData, ...today.finishedData].some((d) => d.pick.game_id === gameId),
    [today.data, today.pausedData, today.finishedData, gameId],
  );

  // A refresh that failed AFTER a good load keeps the last answer on screen
  // and says so (PR #1595 review, L4) — the app's own stale-board banner, so
  // VoiceOver announces it and Retry shows it is running (UX review).
  const staleNote =
    today.loaded && today.error ? (
      <ErrorBanner
        what="the latest picks"
        error={today.error}
        onRetry={today.refresh}
        retrying={today.loading}
        reassurance="Showing the last picks loaded."
      />
    ) : null;

  if (picks.length > 0) {
    // The board's own cards on the page, not inside a second card: the
    // wrapper cancels the page gutter so PickCard's own margin gives the
    // Signals board's gutter (UX review, 2026-11-23).
    return (
      <>
        <SectionHeading title="Our pick" />
        {staleNote}
        <View style={styles.pickCards}>
          {picks.map((item) => (
            <PickCard
              key={item.pick.pick_id}
              item={item}
              onPress={() => navigation.navigate('PickDetail', { pickId: item.pick.pick_id })}
              tracked={tracked.isTracked(item.pick)}
              onToggleTrack={() => tracked.toggle(item.pick)}
              inSlip={slip.has(slipKeyForPick(item.pick))}
              onToggleSlip={() => {
                void slip.toggle(slipKeyForPick(item.pick), betslipPlayerFromPick(item.pick));
              }}
              showSignalBadge={false}
              paused={isPausedForDisplay(item.pick)}
              layout="signals"
            />
          ))}
        </View>
      </>
    );
  }
  // A failed FIRST read is never "No pick": the member would be told the
  // models passed on a game they may have bet (UX review Blocker).
  return (
    <Section
      title="Our pick"
      loading={!today.loaded && !today.error}
      error={today.loaded ? null : today.error}
      onRetry={today.refresh}
    >
      {scored ? (
        <Text style={styles.noPick}>No pick from our models on this game.</Text>
      ) : (
        <Text style={styles.noPick}>
          Our models haven’t scored this game yet. <Text style={styles.noPickNote}>{REFRESH_TIMES}</Text>
        </Text>
      )}
      {staleNote}
    </Section>
  );
}

const styles = StyleSheet.create({
  pickCards: { marginHorizontal: -spacing.lg },
  noPickNote: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.regular,
    color: colors.textSecondary,
  },
  noPick: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
});

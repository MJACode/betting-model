import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { AllBooksCard } from '@/components/AllBooksCard';
import { GameStatusPill } from '@/components/GameStatusPill';
import { LineMovementCard } from '@/components/LineMovementCard';
import { NflTimingCard } from '@/components/NflTimingCard';
import { PropContextCard } from '@/components/PropContextCard';
import { PublicBettingCard } from '@/components/PublicBettingCard';
import { ReasoningCard } from '@/components/ReasoningCard';
import { SharpScoreCard } from '@/components/SharpScoreCard';
import { SignalBadge } from '@/components/SignalBadge';
import { TaleOfTheTapeCard } from '@/components/TaleOfTheTapeCard';
import { TrackButton } from '@/components/TrackButton';
import { TrendStrip } from '@/components/TrendStrip';
import { TrendSparkline } from '@/components/TrendSparkline';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useTrackedBets } from '@/hooks/useTrackedBets';
import { useLiveGameState } from '@/hooks/useLiveGameStates';
import { usePlayerTrends } from '@/hooks/usePlayerTrends';
import {
  detailStatForPropModel,
  supportsPlayerDetail,
  type PlayerLogSport,
} from '@/lib/playerLog';
import type { Sport } from '@/hooks/useSportFilter';
import { usePreferredBook } from '@/hooks/usePreferredBook';
import { usePropContext } from '@/hooks/usePropContext';
import { useTeamTrends } from '@/hooks/useTeamTrends';
import { fetchPickById } from '@/lib/queries';
import { betOnBookLabel, bookButtonColors, openBookBetslip } from '@/lib/sportsbookLinks';
import { basesLabel, formatAmerican, gameStatus } from '@/lib/format';
import { MODEL_META, modelLong, sportOfModel } from '@/lib/modelMeta';
import { displayQuoteForPick, playerNameFromPickLabel, MODEL_BOOK } from '@/lib/markets';
import { PROB_ONLY_MODELS, type KellySizingOpts } from '@/lib/thresholds';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick, Pick, RootStackParamList } from '@/types';

type DetailRoute = RouteProp<RootStackParamList, 'PickDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function PickDetailScreen() {
  const route = useRoute<DetailRoute>();
  const { pickId } = route.params;
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);

  const [data, setData] = useState<EnrichedPick | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    fetchPickById(pickId)
      .then((row) => {
        if (mounted) setData(row);
      })
      .catch((e: unknown) => {
        if (mounted) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [pickId]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <ActivityIndicator style={styles.loading} />
      </SafeAreaView>
    );
  }

  if (error || !data) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <Text style={styles.error}>{error ?? 'Pick not found'}</Text>
      </SafeAreaView>
    );
  }

  return <PickDetailContent enriched={data} bankroll={bankroll} kelly={kelly} />;
}

function PickDetailContent({
  enriched,
  bankroll,
  kelly,
}: {
  enriched: EnrichedPick;
  bankroll: number;
  kelly: KellySizingOpts;
}) {
  const navigation = useNavigation<Nav>();
  const tracked = useTrackedBets();
  const { pick, game, weather, bookRows } = enriched;
  const meta = MODEL_META[pick.model_id];
  // Hand off to the user's own sportsbook, using that book's betslip link. Falls
  // back to DraftKings (the modeled book) when their book doesn't price this side.
  const { book: preferredBook } = usePreferredBook();
  const quote = displayQuoteForPick(pick, bookRows ?? [], preferredBook);
  const betBook = quote?.bookmaker ?? MODEL_BOOK;
  const betLink = quote?.link ?? pick.dk_bet_link;
  const betColors = bookButtonColors(betBook);

  const isGameModel = meta?.type === 'game';
  // Freshest in-play snapshot for this game (score/inning/outs/bases).
  const liveState = useLiveGameState(pick.game_date ?? null, pick.game_id ?? null);
  // Track — any pick (props, started games, and live in-play picks) until it
  // settles. Live picks track by a stable proposition key so the delete+rescore
  // churn can't drop them (useTrackedBets).
  const canTrack = pick.result == null;
  // Line-move alerts only apply to game-level pre-game picks with a DK price
  // (the backend notifier filters to exactly this set) — adjust the copy so we
  // don't promise alerts on props or already-started games.
  const trackAlertsEligible =
    isGameModel && pick.dk_odds != null && pick.player_id == null &&
    gameStatus(game, liveState).kind === 'pre';
  // Who's on base, shown under the matchup while the game is actually in play.
  const liveBases =
    liveState?.abstract_game_state === 'Live' ? basesLabel(liveState.bases_state) : null;
  const isPitcherProp = meta?.type === 'pitcher_prop';
  const isBatterProp = meta?.type === 'batter_prop';
  const isPlayerProp = isPitcherProp || isBatterProp || meta?.type === 'player_prop';

  // Player name for prop picks — shared with the prop line-shopping join in
  // queries.ts so both use one parser.
  const playerName = isPlayerProp ? playerNameFromPickLabel(pick.pick_label) : null;

  // The stat this pick is about, and the log it lives in. Null for a prop model
  // with no leaderboard stat behind it — today that is the NFL market-relative
  // rule, which is ONE model id spanning eight markets (the market is on
  // pick.prop_market, not the model), so there is no single stat to chart.
  const propStat = isPlayerProp ? detailStatForPropModel(pick.model_id) : null;
  const modelSport = sportOfModel(pick.model_id) as Sport;
  const propSport =
    propStat && supportsPlayerDetail(modelSport) ? (modelSport as PlayerLogSport) : null;
  const isUfc = game?.sport === 'UFC' || pick.sport === 'UFC';
  // Golf picks are per-player on a one-row tournament (no two teams) — there is
  // no run-based team form to show, so skip the trend strips like UFC.
  const isGolf = game?.sport === 'GOLF' || pick.sport === 'GOLF';
  const showTeamTrends = isGameModel && !isUfc && !isGolf;

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
    sport: propSport ?? 'MLB',
    stat: propSport ? propStat : null,
    playerType: isPitcherProp ? 'pitcher' : isBatterProp ? 'batter' : null,
  });

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list}>
        <View style={styles.header}>
          <Text style={styles.label}>{pick.pick_label}</Text>
          <View style={styles.metaRow}>
            <SignalBadge signal={pick.signal_type} />
            <Text style={styles.modelName}>{modelLong(pick.model_id)}</Text>
          </View>
          {game ? (
            <View style={styles.matchupRow}>
              <Text style={styles.matchup}>
                {game.sport === 'GOLF'
                  ? game.home_team
                  : `${game.away_team} ${game.sport === 'UFC' ? 'vs' : '@'} ${game.home_team}`}
              </Text>
              <GameStatusPill game={game} compact={false} live={liveState} />
            </View>
          ) : null}
          {liveBases ? <Text style={styles.liveBases}>{liveBases}</Text> : null}
        </View>

        <ReasoningCard pick={pick} bankroll={bankroll} kelly={kelly} />

        {pick.sport === 'NFL' ? <NflTimingCard pick={pick} /> : null}

        <SharpScoreCard pick={pick} />

        {PROB_ONLY_MODELS.has(pick.model_id) ? (
          <View style={styles.infoCard}>
            <Text style={styles.infoHeading}>Why no edge number?</Text>
            <Text style={styles.infoBody}>
              This market is priced on model probability alone. DraftKings doesn’t post a
              reliable line for it (or juices it heavily), so we flag the pick when the model is
              confident rather than comparing it to a book price.
            </Text>
          </View>
        ) : null}

        <LineMovementCard pick={pick} playerName={playerName} />

        <AllBooksCard pick={pick} bookRows={bookRows} />

        {canTrack ? (
          <View style={styles.trackCard}>
            <View style={styles.trackText}>
              <Text style={styles.trackTitle}>
                {tracked.isTracked(pick) ? 'Tracking this bet' : 'Track this bet'}
              </Text>
              <Text style={styles.trackSub}>
                {pick.is_live
                  ? 'Tracked live bets are scored on the Performance tab from the model’s final pick on this side once the game ends.'
                  : trackAlertsEligible
                    ? 'We’ll send you a notification if the DK line moves a lot before game time. Tracked bets are scored on the Performance tab.'
                    : 'Tracked bets are scored on the Performance tab once results come in.'}
              </Text>
            </View>
            <TrackButton
              tracked={tracked.isTracked(pick)}
              onPress={() => tracked.toggle(pick)}
            />
          </View>
        ) : null}

        {pick.signal_type === 'BET' && betLink ? (
          <Pressable
            onPress={() => {
              void openBookBetslip(betBook, betLink);
            }}
            style={({ pressed }) => [
              styles.dkButton,
              { backgroundColor: betColors.bg },
              pressed && styles.dkButtonPressed,
            ]}
          >
            <Ionicons name="open-outline" size={18} color={betColors.fg} />
            <Text style={[styles.dkButtonText, { color: betColors.fg }]}>
              {betOnBookLabel(betBook)}
            </Text>
          </Pressable>
        ) : null}

        <PublicBettingCard pick={pick} />

        <ClvCard pick={pick} />

        {pick.injury_flag ? (
          <View style={styles.infoCard}>
            <Text style={styles.infoHeading}>Injury</Text>
            <Text style={styles.infoBody}>
              {pick.injury_flag}
              {pick.injury_detail ? ` — ${pick.injury_detail}` : ''}
            </Text>
          </View>
        ) : null}

        {weather ? (
          <View style={styles.infoCard}>
            <Text style={styles.infoHeading}>Weather</Text>
            <Text style={styles.infoBody}>
              {weather.is_dome_game === 1
                ? `Dome${weather.venue ? ` · ${weather.venue}` : ''}`
                : `${weather.temp_f ?? '—'}°F · Wind ${weather.wind_mph ?? '—'} mph (out ${weather.wind_out_component != null ? weather.wind_out_component.toFixed(1) : '—'})${weather.venue ? ` · ${weather.venue}` : ''}`}
            </Text>
          </View>
        ) : null}

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

        {propSport && (pick.player_id || playerName) ? (
          <>
            <TrendStrip
              title={`${playerName ?? 'Player'} — recent form`}
              trends={playerTrends.trends}
              mode="player"
              unit={propStat?.label ?? meta?.statLabel ?? ''}
            />
            <TrendSparkline
              values={playerTrends.values}
              line={pick.scored_line ?? null}
              label={`${propStat?.label ?? 'Stat'} — last 20 games (newest at right)`}
            />
            <Pressable
              onPress={() =>
                navigation.navigate('PlayerStats', {
                  playerId: pick.player_id ?? '',
                  playerName: playerName ?? '',
                  sport: propSport,
                  // MLB only — decides batter vs pitcher chips on the detail screen.
                  playerType: isPitcherProp ? 'pitcher' : isBatterProp ? 'batter' : undefined,
                })
              }
              style={({ pressed }) => [styles.viewStatsBtn, pressed && styles.viewStatsBtnPressed]}
            >
              <Ionicons name="bar-chart-outline" size={16} color={colors.tint} />
              <Text style={styles.viewStatsText}>View all stats for {playerName ?? 'player'}</Text>
              <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
            </Pressable>
          </>
        ) : null}

        {playerTrends.loading || homeTrends.loading || awayTrends.loading ? (
          <ActivityIndicator style={styles.loadingTrend} />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

// Closing line value, captured at settlement from the last pre-game DK snapshot.
// clv_pct is in percentage points: positive = the price moved toward our side
// after we made the pick (we beat the close).
function ClvCard({ pick }: { pick: Pick }) {
  if (pick.clv_pct == null) return null;

  const beat = pick.clv_pct > 0;
  const flat = pick.clv_pct === 0;
  const valueColor = flat ? colors.textSecondary : beat ? colors.bet : colors.avoid;
  const sign = pick.clv_pct > 0 ? '+' : '';
  const verdict = flat ? 'Matched the close' : beat ? 'Beat the close' : 'Closed worse';
  const lineMoved =
    pick.scored_line != null &&
    pick.closing_line != null &&
    pick.scored_line !== pick.closing_line;

  return (
    <View style={styles.infoCard}>
      <Text style={styles.infoHeading}>Closing Line Value</Text>
      <View style={styles.clvHeadRow}>
        <Text style={[styles.clvValue, { color: valueColor }]}>
          {`${sign}${pick.clv_pct.toFixed(1)}pp`}
        </Text>
        <Text style={[styles.clvVerdict, { color: valueColor }]}>{verdict}</Text>
      </View>
      <Text style={styles.infoBody}>
        Bet {formatAmerican(pick.dk_odds)} → Close {formatAmerican(pick.closing_dk_odds)}
      </Text>
      {lineMoved ? (
        <Text style={styles.infoBody}>
          Line {pick.scored_line} → {pick.closing_line}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  trackCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  trackText: {
    flex: 1,
  },
  trackTitle: {
    color: colors.textPrimary,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    marginBottom: 2,
  },
  trackSub: {
    color: colors.textSecondary,
    fontSize: font.size.footnote,
  },
  clvHeadRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: spacing.sm,
    marginBottom: 4,
  },
  clvValue: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
  },
  clvVerdict: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
  },
  list: {
    paddingBottom: spacing.xl,
    paddingTop: spacing.md,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  label: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: 4,
  },
  modelName: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  matchupRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  matchup: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  liveBases: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  infoCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  infoHeading: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 4,
  },
  infoBody: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    lineHeight: 20,
  },
  loading: {
    marginTop: spacing.xxl,
  },
  loadingTrend: {
    marginTop: spacing.md,
  },
  error: {
    color: colors.avoid,
    padding: spacing.lg,
    fontSize: font.size.body,
  },
  viewStatsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  viewStatsBtnPressed: {
    opacity: 0.7,
  },
  // Colors come from the book being handed off to (bookButtonColors) and are
  // applied inline.
  dkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  dkButtonPressed: {
    opacity: 0.85,
  },
  dkButtonText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
  },
  viewStatsText: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
});

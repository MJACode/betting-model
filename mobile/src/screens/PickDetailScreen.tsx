import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { AddToPlayButton } from '@/components/AddToPlayButton';
import { GameStatusPill } from '@/components/GameStatusPill';
import { LineMovementCard } from '@/components/LineMovementCard';
import { PropContextCard } from '@/components/PropContextCard';
import { PublicBettingCard } from '@/components/PublicBettingCard';
import { ReasoningCard } from '@/components/ReasoningCard';
import { SignalBadge } from '@/components/SignalBadge';
import { TaleOfTheTapeCard } from '@/components/TaleOfTheTapeCard';
import { TrendStrip } from '@/components/TrendStrip';
import { TrendSparkline } from '@/components/TrendSparkline';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { usePlayerTrends, type PlayerStatKey } from '@/hooks/usePlayerTrends';
import { usePropContext } from '@/hooks/usePropContext';
import { useTeamTrends } from '@/hooks/useTeamTrends';
import { fetchPickById } from '@/lib/queries';
import { DK_GREEN, openBetslip } from '@/lib/draftkings';
import { formatAmerican } from '@/lib/format';
import { MODEL_META, modelLong } from '@/lib/modelMeta';
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
  const slip = useParlaySlip();
  const { pick, game, weather } = enriched;
  const meta = MODEL_META[pick.model_id];

  const isGameModel = meta?.type === 'game';
  const isPitcherProp = meta?.type === 'pitcher_prop';
  const isBatterProp = meta?.type === 'batter_prop';

  // Player name: parse from pick_label for prop picks. Format examples:
  //   "Blake Snell Over 5.5 Ks"
  //   "Aaron Judge Over 0.5 HR"
  const playerName = (() => {
    if (!isPitcherProp && !isBatterProp) return null;
    const m = pick.pick_label.match(/^([A-Za-z .'\-]+?)\s+(?:Over|Under)\s/);
    return m ? m[1] : null;
  })();

  const statKey = (meta?.statKey ?? null) as PlayerStatKey | null;
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
    statKey: isPitcherProp || isBatterProp ? statKey : null,
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
              <GameStatusPill game={game} compact={false} />
            </View>
          ) : null}
          {pick.dk_odds != null ? (
            <View style={styles.playRow}>
              <AddToPlayButton
                inPlay={slip.has(pick.pick_id)}
                onPress={() => slip.toggle(pick.pick_id)}
              />
            </View>
          ) : null}
        </View>

        <ReasoningCard pick={pick} bankroll={bankroll} kelly={kelly} />

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

        {pick.signal_type === 'BET' && pick.dk_bet_link ? (
          <Pressable
            onPress={() => {
              void openBetslip(pick.dk_bet_link);
            }}
            style={({ pressed }) => [styles.dkButton, pressed && styles.dkButtonPressed]}
          >
            <Ionicons name="open-outline" size={18} color="#000" />
            <Text style={styles.dkButtonText}>Bet on DraftKings</Text>
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

        {(isPitcherProp || isBatterProp) && (pick.player_id || playerName) ? (
          <>
            <TrendStrip
              title={`${playerName ?? 'Player'} — recent form`}
              trends={playerTrends.trends}
              mode="player"
              unit={meta?.statLabel ?? ''}
            />
            <TrendSparkline
              values={playerTrends.values}
              line={pick.scored_line ?? null}
              label={`${meta?.statLabel ?? 'Stat'} — last 20 games (newest at right)`}
            />
            <Pressable
              onPress={() =>
                navigation.navigate('PlayerStats', {
                  playerId: pick.player_id ?? '',
                  playerName: playerName ?? '',
                  playerType: isPitcherProp ? 'pitcher' : 'batter',
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
  playRow: {
    flexDirection: 'row',
    marginTop: spacing.md,
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
  dkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: DK_GREEN,
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
    color: '#000',
  },
  viewStatsText: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
});

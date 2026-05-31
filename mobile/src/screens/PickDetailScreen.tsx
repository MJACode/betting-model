import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { BetAmountEditor } from '@/components/BetAmountEditor';
import { GameStatusPill } from '@/components/GameStatusPill';
import { PlacedToggle } from '@/components/PlacedToggle';
import { PublicBettingCard } from '@/components/PublicBettingCard';
import { ReasoningCard } from '@/components/ReasoningCard';
import { SignalBadge } from '@/components/SignalBadge';
import { TrendStrip } from '@/components/TrendStrip';
import { TrendSparkline } from '@/components/TrendSparkline';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import {
  isPlaced,
  usePlacedPicks,
  type PlacedBet,
  type PlacedMap,
} from '@/hooks/usePlacedPicks';
import { usePlayerTrends, type PlayerStatKey } from '@/hooks/usePlayerTrends';
import { useTeamTrends } from '@/hooks/useTeamTrends';
import { fetchPickById } from '@/lib/queries';
import { MODEL_META, modelLong } from '@/lib/modelMeta';
import { recommendedBet, type KellySizingOpts } from '@/lib/thresholds';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick, RootStackParamList } from '@/types';

type DetailRoute = RouteProp<RootStackParamList, 'PickDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function PickDetailScreen() {
  const route = useRoute<DetailRoute>();
  const { pickId } = route.params;
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const { overrides, togglePlaced, setBetAmount, getPlacedBet } = usePlacedPicks();

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

  return (
    <PickDetailContent
      enriched={data}
      bankroll={bankroll}
      kelly={kelly}
      overrides={overrides}
      togglePlaced={togglePlaced}
      setBetAmount={setBetAmount}
      getPlacedBet={getPlacedBet}
    />
  );
}

function PickDetailContent({
  enriched,
  bankroll,
  kelly,
  overrides,
  togglePlaced,
  setBetAmount,
  getPlacedBet,
}: {
  enriched: EnrichedPick;
  bankroll: number;
  kelly: KellySizingOpts;
  overrides: PlacedMap;
  togglePlaced: (id: number, pick: EnrichedPick['pick'], defaultAmount: number) => void;
  setBetAmount: (id: number, amount: number) => void;
  getPlacedBet: (id: number) => PlacedBet | undefined;
}) {
  const navigation = useNavigation<Nav>();
  const { pick, game, weather } = enriched;
  const meta = MODEL_META[pick.model_id];
  const placed = isPlaced(pick.pick_id, pick.signal_type, overrides);
  const placedBet = getPlacedBet(pick.pick_id);
  const recommendation = recommendedBet(pick.kelly_fraction, bankroll, kelly);

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

  const homeTrends = useTeamTrends(isGameModel ? game?.home_team ?? null : null, pick.game_date);
  const awayTrends = useTeamTrends(isGameModel ? game?.away_team ?? null : null, pick.game_date);
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
                {game.away_team} @ {game.home_team}
              </Text>
              <GameStatusPill game={game} compact={false} />
            </View>
          ) : null}
        </View>

        <PlacedToggle
          value={placed}
          onChange={() => togglePlaced(pick.pick_id, pick, recommendation)}
        />

        {placed ? (
          <BetAmountEditor
            amount={placedBet?.amount ?? recommendation}
            recommendation={recommendation}
            bankroll={bankroll}
            onChange={(v) => setBetAmount(pick.pick_id, v)}
          />
        ) : null}

        <ReasoningCard pick={pick} bankroll={bankroll} kelly={kelly} />

        <PublicBettingCard pick={pick} />

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

        {isGameModel && game ? (
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

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
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
  viewStatsText: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
});

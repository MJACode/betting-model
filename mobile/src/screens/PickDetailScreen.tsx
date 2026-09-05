import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation, useRoute } from '@react-navigation/native';
import { AddToPlayButton } from '@/components/AddToPlayButton';
import { AllBooksCard } from '@/components/AllBooksCard';
import { BookLinesRow } from '@/components/BookLinesRow';
import { GameStatusPill } from '@/components/GameStatusPill';
import { LineMovementCard } from '@/components/LineMovementCard';
import { PickTimingCard } from '@/components/PickTimingCard';
import { PlayerNewsButton } from '@/components/PlayerNewsButton';
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
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useLiveGameState } from '@/hooks/useLiveGameStates';
import { usePlayerTrends } from '@/hooks/usePlayerTrends';
import {
  detailStatForPropModel,
  supportsPlayerDetail,
  type PlayerLogSport,
} from '@/lib/playerLog';
import type { Sport } from '@/hooks/useSportFilter';
import { usePlayerNews } from '@/hooks/usePlayerNews';
import { usePropContext } from '@/hooks/usePropContext';
import { useTeamTrends } from '@/hooks/useTeamTrends';
import { fetchPickById } from '@/lib/queries';
import { slipKeyForPick } from '@/lib/parlay';
import { basesLabel, formatAmerican, formatPctSigned, gameStatus } from '@/lib/format';
import { MODEL_META, modelLong, sportOfModel } from '@/lib/modelMeta';
import {
  bookName,
  displayQuoteForPick,
  formatSideLine,
  gameMarketForModel,
  playerNameFromPickLabel,
  propMarketForModel,
  MODEL_BOOK,
} from '@/lib/markets';
import { isModelRetired, isProbOnlyModel, type KellySizingOpts, isUnlockedPreview } from '@/lib/thresholds';
import { colors, font, radii, spacing } from '@/lib/theme';
import { errorText } from '@/lib/errors';
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
        if (mounted) setError(errorText(e));
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
  const slip = useParlaySlip();
  const { pick, game, weather, bookRows } = enriched;
  const meta = MODEL_META[pick.model_id];
  // The headline price is the modeled DraftKings number the edge, EV and stake
  // were computed from. Picks do not follow the member's book preference
  // (Matt, 2026-09-04) — where to place the bet is the Betting lines row below,
  // every bettable book, best price first.
  const live = pick.is_live === true;
  const quote = displayQuoteForPick(pick, [], MODEL_BOOK);
  // Unlocked look-ahead (future UFC/golf): show the line, never the signal —
  // the pick re-scores every refresh until it locks on game day.
  const preview = isUnlockedPreview(pick);
  const retired = isModelRetired(pick.model_id);
  // One plain-English line saying whose price this screen is showing — always
  // the book the pick was modeled at. Renders in the header so the provenance
  // is never implicit.
  const quoteProvenance =
    quote == null
      ? null
      : live
        ? `${bookName(quote.bookmaker)} ${formatAmerican(quote.price)} · live picks are DraftKings only`
        : `${bookName(quote.bookmaker)} ${formatAmerican(quote.price)}${
            quote.line != null && pick.scored_line != null && quote.line !== pick.scored_line
              ? ` (line ${quote.line})`
              : ''
          } · the price this pick was modeled at`;

  // The best price we found across every book the odds feed carries, recorded
  // on the pick when it was scored. Shown only when it genuinely beats the
  // price the pick was measured at — otherwise it just restates the header.
  // This is where the bettor should place it; the BET/AVOID call, the edge and
  // the stake are still measured against DraftKings (see config.BEST_LINE_BOOKMAKERS).
  const bestLine =
    pick.best_book != null &&
    pick.best_odds != null &&
    (pick.dk_odds == null || Number(pick.best_odds) !== Number(pick.dk_odds))
      ? `Best price ${formatAmerican(Number(pick.best_odds))} at ${bookName(pick.best_book)}` +
        (pick.best_edge != null ? ` · ${formatPctSigned(Number(pick.best_edge))} edge there` : '')
      : null;

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
  // Recent news about the player this prop is on. Keyed on the model's sport
  // rather than the chartable stat: a prop with no leaderboard stat behind it
  // (the NFL market-relative rule) still has a player, and still has news.
  const playerNews = usePlayerNews({
    sport: isPlayerProp ? pick.sport ?? modelSport : null,
    playerId: pick.player_id,
    playerName,
    enabled: isPlayerProp,
  });
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
          <View style={styles.titleRow}>
            <Text style={[styles.label, styles.labelFlex]}>{pick.pick_label}</Text>
            {/* Recent news for the player this prop is on — same icon, same
                sheet as the player detail screen. */}
            <PlayerNewsButton
              playerName={playerName ?? 'Player'}
              subtitle={pick.pick_label}
              news={playerNews}
            />
          </View>
          <View style={styles.metaRow}>
            {preview ? (
              <View style={styles.previewBadge}>
                <Text style={styles.previewBadgeText}>PREVIEW</Text>
              </View>
            ) : (
              <SignalBadge signal={pick.signal_type} />
            )}
            <Text style={styles.modelName}>{modelLong(pick.model_id)}</Text>
          </View>
          {preview ? (
            <Text style={styles.previewNote}>
              {pick.sport === 'GOLF'
                ? 'This pick re-prices until the tournament starts, then locks. It becomes a signal only if it still clears the bar then.'
                : 'This pick re-prices until fight-day morning, then locks. It becomes a signal only if it still clears the bar then.'}
            </Text>
          ) : null}
          {bestLine ? <Text style={styles.bestLine}>{bestLine}</Text> : null}
          {quoteProvenance ? (
            <Text style={styles.quoteProvenance}>{quoteProvenance}</Text>
          ) : null}
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

        <PickTimingCard pick={pick} />

        <SharpScoreCard pick={pick} />

        {isProbOnlyModel(pick.model_id) ? (
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

        {/* Where to place it, then every book and line — one section, action
            first (UX review): the chips are the bettable same-line subset, the
            table below carries books at a different number and the reference
            books that cannot be bet. Not for live picks: they are DraftKings
            only, and the in-play rows are no longer fetched. */}
        {pick.signal_type === 'BET' && !preview && !retired ? (
          <View style={styles.linesCard}>
            <BookLinesRow pick={pick} bookRows={bookRows} />
          </View>
        ) : null}
        {live ? null : <AllBooksCard pick={pick} bookRows={bookRows} />}

        {/* A retired model's pick (reachable from a tracked bet on Performance)
            is history, not something to slip or hand off — the board it would
            resolve against no longer carries the model. Tracking stays so the
            user can still untrack it. */}
        {pick.dk_odds != null && pick.result == null && !preview && !retired ? (
          <View style={styles.trackCard}>
            <View style={styles.trackText}>
              <Text style={styles.trackTitle}>
                {slip.has(slipKeyForPick(pick)) ? 'In your betslip' : 'Add to your betslip'}
              </Text>
              <Text style={styles.trackSub}>
                Package this bet with others in your betslip — combined odds, EV, and each
                sportsbook’s price for the whole slip.
              </Text>
            </View>
            <AddToPlayButton
              inPlay={slip.has(slipKeyForPick(pick))}
              onPress={() => slip.toggle(slipKeyForPick(pick))}
            />
          </View>
        ) : null}

        {canTrack ? (
          <View style={styles.trackCard}>
            <View style={styles.trackText}>
              <Text style={styles.trackTitle}>
                {tracked.isTracked(pick) ? 'Tracking this bet' : 'Track this bet'}
              </Text>
              <Text style={styles.trackSub}>
                {pick.is_live
                  ? 'Live signals lock at the first BET — this line and price are the bet of record. Tracked live bets score on the Performance tab once the game ends.'
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

// Closing line value, captured at settlement from the last pre-game DK snapshot
// on the pick side.
//
// TWO MEASURES, and which one applies depends on whether the number moved:
//   - the number HELD  → clv_pct, the price delta in pp
//   - the number MOVED → line_clv_pts, how far it moved toward our side
// A price on a line we no longer hold is not a comparison (Over 44.5 at -110
// and Over 46.5 at -110 are different bets), which is why clv_pct is NULL for
// a moved line rather than misleading. `clv_beat_close` carries the single
// verdict so this card can never pick the wrong one of the two.
//
// The headline the card exists for is the SIGNAL LINE vs THE CLOSING LINE:
// the number we handed the user against the number the market settled on.
function ClvCard({ pick }: { pick: Pick }) {
  // clv_captured_at is the "we have a close" flag. Gating on clv_pct instead
  // would hide the card for exactly the picks whose line moved — the ones with
  // the most to show.
  if (pick.clv_captured_at == null) return null;

  const market = pick.model_id.includes('prop')
    ? propMarketForModel(pick.model_id)
    : gameMarketForModel(pick.model_id);
  const lineCLV = pick.line_clv_pts;
  const lineMoved = lineCLV != null && lineCLV !== 0;
  const hasLines = pick.scored_line != null && pick.closing_line != null;

  const beat = pick.clv_beat_close;
  const flat = !lineMoved && pick.clv_pct === 0;
  const valueColor = flat
    ? colors.textSecondary
    : beat == null
      ? colors.textSecondary
      : beat
        ? colors.bet
        : colors.avoid;
  const verdict = flat
    ? 'Matched the close'
    : beat == null
      ? 'Close recorded'
      : beat
        ? 'Beat the close'
        : 'Closed worse';

  // The number moved → quote the move in points, the unit the bet is actually
  // in. It held → quote the price move in pp, as before.
  const headline = lineMoved
    ? `${lineCLV > 0 ? '+' : ''}${lineCLV.toFixed(1)} pts`
    : pick.clv_pct != null
      ? `${pick.clv_pct > 0 ? '+' : ''}${pick.clv_pct.toFixed(1)}pp`
      : '—';

  return (
    <View style={styles.infoCard}>
      <Text style={styles.infoHeading}>Closing Line Value</Text>
      <View style={styles.clvHeadRow}>
        <Text style={[styles.clvValue, { color: valueColor }]}>{headline}</Text>
        <Text style={[styles.clvVerdict, { color: valueColor }]}>{verdict}</Text>
      </View>

      {hasLines ? (
        <View style={styles.clvRow}>
          <Text style={styles.clvRowLabel}>Signal line</Text>
          <Text style={styles.clvRowValue}>
            {formatSideLine(pick.scored_line, pick.pick_side, market)} at{' '}
            {formatAmerican(pick.dk_odds)}
          </Text>
        </View>
      ) : null}
      {hasLines ? (
        <View style={styles.clvRow}>
          <Text style={styles.clvRowLabel}>Closing line</Text>
          <Text style={styles.clvRowValue}>
            {formatSideLine(pick.closing_line, pick.pick_side, market)} at{' '}
            {formatAmerican(pick.closing_dk_odds)}
          </Text>
        </View>
      ) : (
        <Text style={styles.infoBody}>
          Bet {formatAmerican(pick.dk_odds)} → Close {formatAmerican(pick.closing_dk_odds)}
        </Text>
      )}

      <Text style={styles.clvNote}>
        {lineMoved
          ? `The number moved ${Math.abs(lineCLV).toFixed(1)} ${
              Math.abs(lineCLV) === 1 ? 'point' : 'points'
            } ${lineCLV > 0 ? 'in your favor' : 'against you'} after we posted this — ` +
            `betting it later would have been ${lineCLV > 0 ? 'worse' : 'better'}. ` +
            `The prices aren't compared here because they're quoted on different numbers.`
          : `The number held from signal to close, so the prices are directly comparable. ` +
            `Closing line value is the market's own verdict on the bet, independent of ` +
            `whether it won.`}
      </Text>
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
  clvRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: spacing.sm,
    paddingVertical: 3,
  },
  clvRowLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  clvRowValue: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  clvNote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  list: {
    paddingBottom: spacing.xl,
    paddingTop: spacing.md,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  labelFlex: { flex: 1 },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.md,
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
  previewBadge: {
    borderRadius: radii.pill,
    paddingVertical: 3,
    paddingHorizontal: 10,
    backgroundColor: colors.noneSoft,
    alignSelf: 'flex-start',
  },
  previewBadgeText: {
    fontSize: 12,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
    color: colors.none,
  },
  previewNote: {
    marginTop: spacing.xs,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  modelName: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  bestLine: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.bet,
    marginTop: 2,
  },
  quoteProvenance: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: 4,
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
  // The Betting lines row (BookLinesRow) on its own card — the row carries
  // its own top margin, so the card only pads the sides and bottom.
  linesCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  viewStatsText: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
});

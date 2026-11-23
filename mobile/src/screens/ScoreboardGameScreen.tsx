import React, { useCallback, useMemo, useRef, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import {
  BestPriceSection,
  CompareSection,
  FormSection,
  HeadToHeadSection,
  InjurySection,
  Section,
} from '@/components/MatchupSections';
import { PickCard } from '@/components/PickCard';
import { useThresholdsRevision } from '@/hooks/useActionThresholds';
import { useMatchup } from '@/hooks/useMatchup';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useTrackedBets } from '@/hooks/useTrackedBets';
import { betslipPlayerFromPick } from '@/lib/betslipGuard';
import { gamePicks, hasMatchupView } from '@/lib/gameMatchup';
import { slipKeyForPick } from '@/lib/parlay';
import { isPausedForDisplay, isUnlockedPreview, passesActionFilter, passesRecordFilter } from '@/lib/thresholds';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { useNcaafAbbrevs } from '@/hooks/useNcaafAbbrevs';
import { errorText, isAbortError } from '@/lib/errors';
import {
  fetchDkInplayForGames,
  fetchDkMarketEnds,
  fetchLiveGameStateById,
  fetchLiveScoreboard,
  fetchNcaafScoreboard,
  fetchScoreboardDkOddsForGame,
  fetchScoreboardGame,
} from '@/lib/queries';
import {
  ESPN_LIVE_SPORTS,
  feedFromEspn,
  feedFromMlb,
  feedFromNcaaf,
  mergeDkInplay,
  movementText,
  presentScoreboard,
  scoreboardMarketLabel,
  scoreboardMarketsFor,
  type ScoreboardQuote,
} from '@/lib/scoreboard';
import { colors, font, spacing, sectionHeaderText, card } from '@/lib/theme';
import type { GameRow, RootStackParamList } from '@/types';
import { SkeletonList } from '@/components/Skeleton';

type Route = RouteProp<RootStackParamList, 'ScoreboardGame'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

const MARKETS = [
  { id: 'h2h' as const, title: 'Moneyline' },
  { id: 'spreads' as const, title: 'Spread' },
  { id: 'totals' as const, title: 'Total' },
];

/** The blocks this sport gets: the board's own tabs (a fight has no spread). */
function marketsFor(sport: string) {
  const ids = scoreboardMarketsFor(sport);
  return MARKETS.filter((m) => ids.includes(m.id));
}

/**
 * One game. Every sport: DraftKings moneyline, spread and total, and how the
 * line moved, with scores from the same stored feeds as the board.
 *
 * NBA (lib/matchup MATCHUP_SPORTS) is the MATCHUP page (Matt, 2026-11-23: "we
 * don't have a nice match up view with games to figure out who to bet"): our
 * picks on this game first — the Signals board's own cards and its own
 * filters, or a plain "No pick" — then the best price at the member's books,
 * the two teams side by side, last 10, rest, head-to-head and injuries.
 */
export function ScoreboardGameScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation<Nav>();
  const gameId = route.params.gameId;
  const [game, setGame] = useState<GameRow | null>(null);
  const matchupOn = hasMatchupView(game?.sport);
  const m = useMatchup(game, matchupOn);
  // The board's picks for this game's day. The same hook Picks reads, so the
  // cards below are the Signals board's cards, never a second copy of them.
  const today = useTodayPicks(game?.game_date);
  const thresholdsRevision = useThresholdsRevision();
  const tracked = useTrackedBets();
  const slip = useParlaySlip();
  const picks = useMemo(
    () =>
      matchupOn
        ? gamePicks(gameId, today.data, today.finishedData, {
            action: (d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick),
            record: (d) => passesRecordFilter(d.pick) && !isUnlockedPreview(d.pick),
          })
        : [],
    // thresholdsRevision: the action filter reads a module store.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [matchupOn, gameId, today.data, today.finishedData, thresholdsRevision],
  );
  const abbrevs = useNcaafAbbrevs(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [card, setCard] = useState<ReturnType<typeof presentScoreboard> | null>(null);
  const [movement, setMovement] = useState<Record<string, string | null>>({});
  const [retrying, setRetrying] = useState(false);
  const [linesError, setLinesError] = useState<string | null>(null);
  const inplayHold = useRef<ScoreboardQuote[]>([]);
  const loadGen = useRef(0);

  const load = useCallback(async () => {
    const gen = ++loadGen.current;
    setLoading(true);
    setError(null);
    try {
      const game = await fetchScoreboardGame(gameId);
      if (gen !== loadGen.current) return;
      setGame(game);
      if (!game) {
        setCard(null);
        setError('This game isn’t on the board.');
        return;
      }
      const [dk, ends, inplayRows, mlb, ncaaf, espn] = await Promise.all([
        fetchScoreboardDkOddsForGame(gameId).catch(() => []),
        Promise.all(marketsFor(game.sport).map(async (m) => [m.id, await fetchDkMarketEnds(gameId, m.id)] as const)).catch(
          () => [] as const,
        ),
        fetchDkInplayForGames([gameId]),
        game.sport === 'MLB' ? fetchLiveGameStateById(gameId).catch(() => null) : Promise.resolve(null),
        game.sport === 'NCAAF' ? fetchNcaafScoreboard([gameId]).catch(() => []) : Promise.resolve([]),
        ESPN_LIVE_SPORTS.includes(game.sport)
          ? fetchLiveScoreboard([gameId]).catch(() => [])
          : Promise.resolve([]),
      ]);
      const merged = mergeDkInplay(
        new Map([[gameId, inplayHold.current]]),
        [gameId],
        inplayRows,
      );
      const inplay = merged.lines.get(gameId) ?? [];
      const now = Date.now();
      const feed = game.sport === 'MLB'
        ? feedFromMlb(mlb, now)
        : game.sport === 'NCAAF'
          ? feedFromNcaaf(ncaaf[0], now)
          : ESPN_LIVE_SPORTS.includes(game.sport)
            ? feedFromEspn(espn[0], now)
            : null;
      if (gen !== loadGen.current) return;
      inplayHold.current = inplay;
      setCard(presentScoreboard({ game, pregame: dk, inplay, feed, abbrevs }));
      const moved: Record<string, string | null> = {};
      for (const [market, pair] of ends) {
        const live = market === 'spreads' || market === 'totals' || market === 'h2h'
          ? inplay.find((q) => q.market === market) ?? null
          : null;
        const current = feed?.inProgress && live ? live : pair.current;
        moved[market] = movementText(pair.open, current, market);
      }
      setMovement(moved);
      setLinesError(merged.error);
    } catch (e: unknown) {
      if (gen !== loadGen.current) return;
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (gen === loadGen.current) {
        setLoading(false);
        setRetrying(false);
      }
    }
  }, [gameId, abbrevs]);

  useFocusEffect(
    useCallback(() => {
      void load();
      const id = setInterval(() => void load(), 30_000);
      return () => clearInterval(id);
    }, [load]),
  );

  if (loading && !card) {
    return (
      <View style={styles.skeletonScreen}>
        <SkeletonList label="this game" rows={5} />
      </View>
    );
  }
  if (error && !card) {
    return (
      <ErrorState
        what="this game"
        error={error}
        onRetry={() => {
          setRetrying(true);
          void load();
        }}
        retrying={retrying}
      />
    );
  }
  if (!card) return null;

  const statusWord = card.footerBadge === 'LIVE'
    ? `Live${card.footerText ? ` · ${card.footerText}` : ''}`
    : card.footerText;

  const started = card.footerBadge === 'LIVE' || game?.home_score != null;
  const refreshAll = () => {
    void load();
    if (matchupOn) {
      m.refresh();
      today.refresh();
    }
  };

  return (
    <ScrollView
      contentContainerStyle={styles.page}
      refreshControl={matchupOn ? <RefreshControl refreshing={false} onRefresh={refreshAll} /> : undefined}
    >
      {linesError ? (
        <ErrorBanner
          what="DraftKings lines"
          error={linesError}
          onRetry={() => {
            setRetrying(true);
            void load();
          }}
          retrying={retrying}
        />
      ) : null}
      {error ? (
        <ErrorBanner
          what="this game"
          error={error}
          onRetry={() => {
            setRetrying(true);
            void load();
          }}
          retrying={retrying}
        />
      ) : null}
      <Text style={styles.matchup} accessibilityRole="header">
        {card.awayFull}
        {matchupOn && m.awayRow ? <Text style={styles.record}>{`  ${m.awayRow.wins}-${m.awayRow.losses}`}</Text> : null}
      </Text>
      <Text style={styles.matchup}>
        {card.homeFull}
        {matchupOn && m.homeRow ? <Text style={styles.record}>{`  ${m.homeRow.wins}-${m.homeRow.losses}`}</Text> : null}
      </Text>
      <Text style={styles.scoreBig}>{card.away.score}–{card.home.score}</Text>
      <Text style={styles.status}>
        {statusWord}
        {card.updatedLabel ? ` · ${card.updatedLabel}` : ''}
      </Text>
      {card.situation ? <Text style={styles.situation}>{card.situation}</Text> : null}
      {matchupOn && game ? (
        <>
          {/* Our verdict first: the Signals board's own cards for this game,
              or a plain "No pick" — never a lean below the bar (Matt,
              2026-11-23: "No pick, just stats in their matchup"). */}
          <Section title="Our pick" loading={today.loading && !today.loaded}>
            {picks.length === 0 ? (
              <Text style={styles.noPick}>No pick from our models on this game.</Text>
            ) : (
              picks.map((item) => (
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
              ))
            )}
          </Section>
          <BestPriceSection m={m} away={game.away_team} home={game.home_team} started={started} />
          <CompareSection m={m} away={game.away_team} home={game.home_team} group="efficiency" />
          <FormSection m={m} away={game.away_team} home={game.home_team} />
          <CompareSection m={m} away={game.away_team} home={game.home_team} group="betting" />
          <HeadToHeadSection m={m} away={game.away_team} home={game.home_team} />
          <InjurySection m={m} away={game.away_team} home={game.home_team} />
        </>
      ) : null}
      <Text style={styles.book}>{matchupOn ? 'DraftKings line movement' : 'DraftKings'}</Text>
      {/* The board's tabs: a fight has no spread at DraftKings (review L4). */}
      {marketsFor(card.sport).map((m) => (
        <View key={m.id} style={styles.block}>
          <Text style={styles.blockTitle}>{m.id === 'h2h' ? m.title : scoreboardMarketLabel(m.id, card.sport)}</Text>
          <MarketLines card={card} market={m.id} />
          {movement[m.id] ? <Text style={styles.move}>{movement[m.id]}</Text> : (
            <Text style={styles.move}>No DraftKings line stored for this market.</Text>
          )}
        </View>
      ))}
      {matchupOn ? null : <Text style={styles.note}>Game markets only. No bet from here.</Text>}
      <BetslipBarSpacer />
    </ScrollView>
  );
}

function newest(rows: ScoreboardQuote[]): ScoreboardQuote[] {
  const by = new Map<string, ScoreboardQuote>();
  for (const row of rows) {
    const prev = by.get(row.market);
    const at = row.snapshot_at ?? '';
    if (!prev || at > (prev.snapshot_at ?? '')) by.set(row.market, row);
  }
  return [...by.values()];
}

function MarketLines({
  card,
  market,
}: {
  card: ReturnType<typeof presentScoreboard>;
  market: 'h2h' | 'spreads' | 'totals';
}) {
  const away = market === 'h2h' ? card.away.ml : market === 'spreads' ? `${card.away.spread}  ${card.away.spreadPrice}` : `${card.away.total}  ${card.away.totalPrice}`;
  const home = market === 'h2h' ? card.home.ml : market === 'spreads' ? `${card.home.spread}  ${card.home.spreadPrice}` : `${card.home.total}  ${card.home.totalPrice}`;
  return (
    <View style={styles.lines}>
      <Text style={styles.line}>{card.awayFull}  {away}</Text>
      <Text style={styles.line}>{card.homeFull}  {home}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: spacing.lg, gap: spacing.md },
  skeletonScreen: { flex: 1, padding: spacing.lg, backgroundColor: colors.bg },
  matchup: {
    fontFamily: font.family,
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  record: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.regular,
    color: colors.textSecondary,
  },
  noPick: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  scoreBig: {
    fontFamily: font.family,
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  status: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  book: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  situation: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  block: {
    ...card,
    gap: spacing.sm,
  },
  blockTitle: {
    ...sectionHeaderText,
  },
  lines: { gap: spacing.xs },
  line: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  move: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  note: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
});

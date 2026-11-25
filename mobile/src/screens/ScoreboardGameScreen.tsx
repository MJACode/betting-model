import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import { useMatchup } from '@/hooks/useMatchup';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { bookLabel } from '@/lib/markets';
import { hasMatchupView } from '@/lib/gameMatchup';
import { MatchupPicks } from '@/components/MatchupPicks';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { useNcaafAbbrevs } from '@/hooks/useNcaafAbbrevs';
import { errorText, isAbortError } from '@/lib/errors';
import {
  fetchDkInplayForGames,
  fetchDkMarketEnds,
  fetchInplayAtBooksForGame,
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
  liveBookLines,
  mergeDkInplay,
  movementText,
  presentScoreboard,
  scoreboardMarketLabel,
  scoreboardMarketsFor,
  type ScoreboardQuote,
} from '@/lib/scoreboard';
import { colors, font, spacing, sectionHeaderText, card } from '@/lib/theme';
import type { GameRow, OddsByBookRow, RootStackParamList } from '@/types';
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
  // The 30s poll re-reads the best-price lines too, so they keep pace with
  // the DraftKings block; a ref, because the poll's closure outlives renders.
  const refreshLinesRef = useRef<(() => void) | null>(null);
  const polledOnce = useRef(false);
  refreshLinesRef.current = matchupOn ? m.refreshLines : null;
  // Pull to refresh shows its spinner until every section has settled.
  const [pulling, setPulling] = useState(false);
  // The picks block reports its own read (components/MatchupPicks).
  const [picksLoading, setPicksLoading] = useState(false);
  const [pullNonce, setPullNonce] = useState(0);
  const settling = m.anyLoading || picksLoading;
  // Cleared only once a load was SEEN in flight and then settled: the pull's
  // own render can come before any section has flipped to loading.
  const sawSettling = useRef(false);
  useEffect(() => {
    if (!pulling) return undefined;
    // A pull where nothing reloads (no sections to read) still ends.
    const stop = setTimeout(() => {
      sawSettling.current = false;
      setPulling(false);
    }, 10_000);
    if (settling) sawSettling.current = true;
    else if (sawSettling.current) {
      sawSettling.current = false;
      setPulling(false);
    }
    return () => clearTimeout(stop);
  }, [pulling, settling]);
  // The way in says "Matchup", so the page does too.
  useEffect(() => {
    if (matchupOn) navigation.setOptions({ title: 'Matchup' });
  }, [matchupOn, navigation]);
  const abbrevs = useNcaafAbbrevs(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [card, setCard] = useState<ReturnType<typeof presentScoreboard> | null>(null);
  const [movement, setMovement] = useState<Record<string, string | null>>({});
  const [retrying, setRetrying] = useState(false);
  const [linesError, setLinesError] = useState<string | null>(null);
  // Every book the member uses, live (mike, 2026-11-25: "why not FanDuel,
  // MGM etc"). Read only once the game has started and has no final score.
  const { books } = usePreferredBooks();
  const [bookRows, setBookRows] = useState<OddsByBookRow[]>([]);
  const [bookError, setBookError] = useState<string | null>(null);
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
      const started = game.commence_time != null && Date.parse(game.commence_time) <= Date.now();
      const maybeLive = started && (game.home_score == null || game.away_score == null);
      const [dk, ends, inplayRows, mlb, ncaaf, espn, atBooks] = await Promise.all([
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
        maybeLive
          ? fetchInplayAtBooksForGame(gameId, books)
          : Promise.resolve({ rows: [] as OddsByBookRow[], error: null as string | null }),
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
      setBookRows(atBooks.rows);
      setBookError(atBooks.error);
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
      // Not on the first load: the lines section is already reading then.
      if (polledOnce.current) refreshLinesRef.current?.();
      polledOnce.current = true;
    } catch (e: unknown) {
      if (gen !== loadGen.current) return;
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (gen === loadGen.current) {
        setLoading(false);
        setRetrying(false);
      }
    }
  }, [gameId, abbrevs, books]);

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
    setPulling(true);
    void load();
    if (matchupOn) {
      m.refresh();
      setPullNonce((n) => n + 1);
    }
  };
  const retrySections = () => {
    m.refresh();
  };

  return (
    <ScrollView
      contentContainerStyle={styles.page}
      refreshControl={matchupOn ? <RefreshControl refreshing={pulling} onRefresh={refreshAll} /> : undefined}
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
      {card.phase === 'live' ? (
        <LiveAtBooks
          card={card}
          rows={bookRows}
          books={books}
          error={bookError}
          onRetry={() => {
            setRetrying(true);
            void load();
          }}
          retrying={retrying}
        />
      ) : null}
      {matchupOn && game ? (
        <>
          {/* Our verdict first: the Signals board's own cards for this game,
              or a plain "No pick" — never a lean below the bar (Matt,
              2026-11-23: "No pick, just stats in their matchup"). */}
          <MatchupPicks
            gameId={gameId}
            gameDate={game.game_date}
            refreshNonce={pullNonce}
            onLoadingChange={setPicksLoading}
          />
          <BestPriceSection m={m} away={game.away_team} home={game.home_team} started={started} onRetry={retrySections} />
          <CompareSection m={m} away={game.away_team} home={game.home_team} group="efficiency" onRetry={retrySections} />
          <FormSection m={m} away={game.away_team} home={game.home_team} onRetry={retrySections} />
          <CompareSection m={m} away={game.away_team} home={game.home_team} group="betting" onRetry={retrySections} />
          <HeadToHeadSection m={m} away={game.away_team} home={game.home_team} onRetry={retrySections} />
          <InjurySection m={m} away={game.away_team} home={game.home_team} started={started} onRetry={retrySections} />
        </>
      ) : null}
      <Text style={styles.book}>{matchupOn ? 'DraftKings lines and movement' : 'DraftKings'}</Text>
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

/**
 * Each book the member uses, its own live number per market, newest first in
 * the member's book order. Rows older than LIVE_BOOK_MAX_AGE_MS are a book
 * that stopped posting, and are left out (lib/scoreboard liveBookLines).
 */
function LiveAtBooks({
  card,
  rows,
  books,
  error,
  onRetry,
  retrying,
}: {
  card: ReturnType<typeof presentScoreboard>;
  rows: OddsByBookRow[];
  books: readonly string[];
  error: string | null;
  onRetry: () => void;
  retrying: boolean;
}) {
  const teams = { away: card.away.name, home: card.home.name };
  return (
    <View style={styles.block}>
      <Text style={styles.blockTitle} accessibilityRole="header">Live at your books</Text>
      {error ? <ErrorBanner what="live lines at your books" error={error} onRetry={onRetry} retrying={retrying} /> : null}
      {marketsFor(card.sport).map((m) => {
        const lines = liveBookLines(rows, m.id, books, teams, bookLabel);
        return (
          <View key={m.id} style={styles.bookMarket}>
            <Text style={styles.bookMarketTitle}>
              {m.id === 'h2h' ? m.title : scoreboardMarketLabel(m.id, card.sport)}
            </Text>
            {lines.length === 0 ? (
              <Text style={styles.move}>No book you use has a live line stored for this market.</Text>
            ) : (
              lines.map((l) => (
                <View key={l.book} style={styles.bookRow} accessible accessibilityLabel={l.spoken}>
                  <Text style={styles.bookName} numberOfLines={1}>{l.label}</Text>
                  <Text style={styles.bookCell}>
                    {m.id === 'totals' ? l.away : `${teams.away} ${l.away}`}
                  </Text>
                  <Text style={styles.bookCell}>
                    {m.id === 'totals' ? l.home : `${teams.home} ${l.home}`}
                  </Text>
                  <Text style={styles.bookAge}>{l.age}</Text>
                </View>
              ))
            )}
          </View>
        );
      })}
      <Text style={styles.note}>Each book's own number, read every 30 seconds.</Text>
    </View>
  );
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
  bookMarket: { gap: spacing.xs },
  bookMarketTitle: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  bookRow: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm, minHeight: 28 },
  bookName: {
    flex: 1.2,
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  bookCell: {
    flex: 1.4,
    fontFamily: font.family,
    fontSize: font.size.callout,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  bookAge: {
    flex: 0.8,
    textAlign: 'right',
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
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

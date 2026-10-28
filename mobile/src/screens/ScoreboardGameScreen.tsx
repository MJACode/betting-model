import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { RouteProp } from '@react-navigation/native';
import { useRoute } from '@react-navigation/native';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { useNcaafAbbrevs } from '@/hooks/useNcaafAbbrevs';
import { errorText, isAbortError } from '@/lib/errors';
import {
  fetchDkInplayForGame,
  fetchDkMarketEnds,
  fetchLiveGameStates,
  fetchNcaafScoreboard,
  fetchScoreboardDkOdds,
  fetchScoreboardGame,
} from '@/lib/queries';
import {
  feedFromMlb,
  feedFromNcaaf,
  movementText,
  presentScoreboard,
  type ScoreboardQuote,
} from '@/lib/scoreboard';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'ScoreboardGame'>;

const MARKETS = [
  { id: 'h2h' as const, title: 'Moneyline' },
  { id: 'spreads' as const, title: 'Spread' },
  { id: 'totals' as const, title: 'Total' },
];

/**
 * One game: DraftKings moneyline, spread and total, and how the line moved.
 * No box score, no signal, no bet button. Scores come from the same stored
 * feeds as the board.
 */
export function ScoreboardGameScreen() {
  const route = useRoute<Route>();
  const gameId = route.params.gameId;
  const abbrevs = useNcaafAbbrevs(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [card, setCard] = useState<ReturnType<typeof presentScoreboard> | null>(null);
  const [movement, setMovement] = useState<Record<string, string | null>>({});
  const [retrying, setRetrying] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const game = await fetchScoreboardGame(gameId);
      if (!game) {
        setCard(null);
        setError('This game isn’t on the board.');
        return;
      }
      const [dk, ends, inplayRows, mlb, ncaaf] = await Promise.all([
        fetchScoreboardDkOdds([game.game_date]).catch(() => []),
        Promise.all(MARKETS.map(async (m) => [m.id, await fetchDkMarketEnds(gameId, m.id)] as const)).catch(
          () => [] as const,
        ),
        fetchDkInplayForGame(gameId).catch(() => []),
        game.sport === 'MLB' ? fetchLiveGameStates(game.game_date).catch(() => []) : Promise.resolve([]),
        game.sport === 'NCAAF' ? fetchNcaafScoreboard([game.game_date]).catch(() => []) : Promise.resolve([]),
      ]);
      const pregame = dk.filter((row) => row.game_id === gameId);
      const inplay = newest(inplayRows);
      const now = Date.now();
      const feed = game.sport === 'MLB'
        ? feedFromMlb(mlb.find((row) => row.game_id === gameId), now)
        : game.sport === 'NCAAF'
          ? feedFromNcaaf(ncaaf.find((row) => row.game_id === gameId), now)
          : null;
      setCard(presentScoreboard({ game, pregame, inplay, feed, abbrevs }));
      const moved: Record<string, string | null> = {};
      for (const [market, pair] of ends) {
        const live = market === 'spreads' || market === 'totals' || market === 'h2h'
          ? inplay.find((q) => q.market === market) ?? null
          : null;
        const current = feed?.inProgress && live ? live : pair.current;
        moved[market] = movementText(pair.open, current, market);
      }
      setMovement(moved);
    } catch (e: unknown) {
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      setLoading(false);
      setRetrying(false);
    }
  }, [gameId, abbrevs]);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 30_000);
    return () => clearInterval(id);
  }, [load]);

  if (loading && !card) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.tint} />
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

  return (
    <ScrollView contentContainerStyle={styles.page}>
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
      <Text style={styles.matchup} accessibilityRole="header">{card.awayFull}</Text>
      <Text style={styles.matchup}>{card.homeFull}</Text>
      <Text style={styles.scoreBig}>{card.away.score}–{card.home.score}</Text>
      <Text style={styles.status}>
        {statusWord}
        {card.updatedLabel ? ` · ${card.updatedLabel}` : ''}
      </Text>
      <Text style={styles.book}>DraftKings</Text>
      {card.situation ? <Text style={styles.situation}>{card.situation}</Text> : null}
      {MARKETS.map((m) => (
        <View key={m.id} style={styles.block}>
          <Text style={styles.blockTitle}>{m.id === 'spreads' && card.sport === 'NHL' ? 'Puck line' : m.title}</Text>
          <MarketLines card={card} market={m.id} />
          {movement[m.id] ? <Text style={styles.move}>{movement[m.id]}</Text> : (
            <Text style={styles.move}>No DraftKings line stored for this market.</Text>
          )}
        </View>
      ))}
      <Text style={styles.note}>Game markets only. No bet from here.</Text>
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
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  matchup: {
    fontFamily: font.family,
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
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
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  blockTitle: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
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

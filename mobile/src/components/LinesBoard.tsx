import React, { useMemo, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AllBooksSheet } from '@/components/AllBooksSheet';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { EmptyState } from '@/components/EmptyState';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { Skeleton, SkeletonBlock } from '@/components/Skeleton';
import { formatGameTimeET } from '@/lib/format';
import { bookLabelShort, bookName } from '@/lib/markets';
import {
  LINES_CELL_HINT,
  LINES_EMPTY_LINES,
  LINES_EMPTY_LINES_BODY,
  LINES_ERROR_RETRY,
  LINES_GAME_UNPRICED,
  LINES_NO_PRICE,
  filterLinesGames,
  linesCardMarkets,
  linesEmptyGamesBody,
  linesEmptyGamesTitle,
  linesHaveOdds,
  linesLineCaption,
  linesMarketLabel,
  linesMarketsStack,
  linesMarks,
  linesPausedChipLabel,
  linesPickChipLabel,
  linesPriceText,
  linesRowsFor,
  linesSheetRows,
  linesSideQuotes,
  modalLine,
  sortLinesGames,
  type LinesMarket,
  type LinesMarkPick,
  type LinesMarks,
  type LinesMlMode,
  type LinesOddsRow,
  type LinesPickRef,
  type LinesSportFilter,
} from '@/lib/linesBoard';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { GameRow } from '@/types';

/**
 * One card per game. Spread / puck line, moneyline and total, each at least
 * 44pt, showing the best bettable price on that side. A game with a pick
 * gets a quiet chip; the picked cell gets a navy dot, never the bet green.
 * At 2× text the three markets stack.
 */
export function LinesBoard({
  games,
  odds,
  picks,
  pausedPicks,
  sport,
  loading,
  loaded,
  error,
  retrying,
  onRefresh,
  showMarks,
  onOpenPick,
}: {
  games: GameRow[];
  odds: LinesOddsRow[];
  picks: readonly LinesPickRef[];
  pausedPicks: readonly LinesPickRef[];
  sport: LinesSportFilter;
  loading: boolean;
  loaded: boolean;
  error: string | null;
  retrying: boolean;
  onRefresh: () => Promise<void>;
  showMarks: boolean;
  onOpenPick: (picks: readonly LinesMarkPick[], kind: 'pick' | 'paused') => void;
}) {
  const { fontScale } = useWindowDimensions();
  const stack = linesMarketsStack(fontScale);
  const [pulling, setPulling] = useState(false);
  const [open, setOpen] = useState<{ gameId: string; market: LinesMarket } | null>(null);
  const [mode, setMode] = useState<LinesMlMode>('full');

  const shown = useMemo(
    () => sortLinesGames(filterLinesGames(games, sport)),
    [games, sport],
  );
  const marks = useMemo(
    () => (showMarks ? linesMarks(picks, pausedPicks) : new Map()),
    [picks, pausedPicks, showMarks],
  );
  const hasOdds = linesHaveOdds(shown.map((g) => g.game_id), odds);

  const openGame = shown.find((g) => g.game_id === open?.gameId) ?? null;
  const sheetMode = open?.market === 'h2h' ? mode : 'full';
  const sheetRows =
    openGame && open
      ? linesSheetRows(
          odds,
          openGame.game_id,
          open.market,
          { away: openGame.away_team, home: openGame.home_team },
          openGame.commence_time,
          sheetMode,
        )
      : [];
  const lineCaption =
    openGame && open
      ? linesLineCaption(
          modalLine(
            linesRowsFor(odds, openGame.game_id, open.market, sheetMode, openGame.commence_time),
            open.market,
          ),
          open.market,
          openGame.sport,
        )
      : null;

  const refresh = () => {
    setPulling(true);
    void onRefresh().finally(() => setPulling(false));
  };

  // `loading` flips inside an effect, so the first frame is not loading yet.
  // An unloaded board with no error is the skeleton, not "No games today".
  if (!loaded && !error) {
    return (
      <View style={styles.fill}>
        <Skeleton label="today’s lines" style={styles.skeletonWrap}>
          {[0, 1, 2].map((i) => (
            <View key={i} style={styles.skeletonCard}>
              <SkeletonBlock width="55%" height={14} />
              <SkeletonBlock width="100%" height={44} />
            </View>
          ))}
        </Skeleton>
        <BetslipBarSpacer />
      </View>
    );
  }

  if (!loaded && error) {
    return (
      <View style={styles.fill}>
        <ErrorState
          what="today’s lines"
          error={error}
          onRetry={() => void onRefresh()}
          retrying={retrying}
          retryLabel={LINES_ERROR_RETRY}
        />
        <BetslipBarSpacer />
      </View>
    );
  }

  if (shown.length === 0 || (!hasOdds && !error)) {
    const noGames = shown.length === 0;
    return (
      <FlatList
        data={[]}
        keyExtractor={() => 'empty'}
        ListFooterComponent={<BetslipBarSpacer />}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={pulling} onRefresh={refresh} />}
        renderItem={() => null}
        ListEmptyComponent={
          <EmptyState
            title={noGames ? linesEmptyGamesTitle(sport) : LINES_EMPTY_LINES}
            subtitle={
              noGames
                ? linesEmptyGamesBody(sport, games.some((g) => g.sport !== sport))
                : LINES_EMPTY_LINES_BODY
            }
          />
        }
      />
    );
  }

  return (
    <View style={styles.fill}>
      {error ? (
        <ErrorBanner
          what="today’s lines"
          error={error}
          onRetry={() => void onRefresh()}
          retrying={retrying}
          retryLabel={LINES_ERROR_RETRY}
        />
      ) : null}
      <FlatList
        data={shown}
        keyExtractor={(g) => g.game_id}
        ListFooterComponent={<BetslipBarSpacer />}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={pulling} onRefresh={refresh} />}
        renderItem={({ item }) => (
          <GameCard
            game={item}
            odds={odds}
            stack={stack}
            picked={marks.get(item.game_id)}
            onOpen={(market) => {
              setMode('full');
              setOpen({ gameId: item.game_id, market });
            }}
            onOpenPick={onOpenPick}
          />
        )}
      />
      <AllBooksSheet
        visible={openGame != null && open != null}
        title={open ? linesMarketLabel(openGame?.sport ?? '', open.market) : ''}
        matchup={openGame ? `${openGame.away_team} @ ${openGame.home_team}` : ''}
        when={openGame ? formatGameTimeET(openGame.commence_time) : ''}
        lineCaption={lineCaption}
        rows={sheetRows}
        showRegulationSwitch={openGame?.sport === 'NHL' && open?.market === 'h2h'}
        mode={mode}
        onMode={setMode}
        onClose={() => setOpen(null)}
      />
    </View>
  );
}

function GameCard({
  game,
  odds,
  stack,
  picked,
  onOpen,
  onOpenPick,
}: {
  game: GameRow;
  odds: LinesOddsRow[];
  stack: boolean;
  picked: LinesMarks | undefined;
  onOpen: (market: LinesMarket) => void;
  onOpenPick: (picks: readonly LinesMarkPick[], kind: 'pick' | 'paused') => void;
}) {
  const time = formatGameTimeET(game.commence_time);
  const teams = { away: game.away_team, home: game.home_team };
  return (
    <View style={styles.card}>
      <View style={styles.top}>
        <Text style={styles.matchup} numberOfLines={1}>
          {game.away_team} @ {game.home_team}
        </Text>
        {time ? (
          <Text style={styles.time} numberOfLines={1}>
            {time}
          </Text>
        ) : null}
      </View>
      {picked && (picked.picks.length > 0 || picked.paused.length > 0) ? (
        <View style={styles.chipRow}>
          {picked.picks.length > 0 ? (
            <Pressable
              onPress={() => onOpenPick(picked.picks, 'pick')}
              accessibilityRole="button"
              accessibilityLabel={`${linesPickChipLabel(picked.picks.length)} on this game`}
              accessibilityHint={picked.picks.length > 1 ? 'Choose a pick' : 'Opens pick detail'}
              style={({ pressed }) => [styles.pickChip, pressed && styles.pressed]}
            >
              <Text style={styles.pickChipText}>{linesPickChipLabel(picked.picks.length)}</Text>
            </Pressable>
          ) : null}
          {picked.paused.length > 0 ? (
            <Pressable
              onPress={() => onOpenPick(picked.paused, 'paused')}
              accessibilityRole="button"
              accessibilityLabel={`${linesPausedChipLabel(picked.paused.length)} on this game`}
              accessibilityHint={picked.paused.length > 1 ? 'Choose a paused pick' : 'Opens pick detail'}
              style={({ pressed }) => [styles.pausedChip, pressed && styles.pressed]}
            >
              <Text style={styles.pausedChipText}>{linesPausedChipLabel(picked.paused.length)}</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
      {linesCardMarkets().every((market) =>
        linesSideQuotes(odds, game.game_id, market, teams, game.commence_time).every((q) => q.price == null),
      ) ? (
        <Text style={styles.unpriced}>{LINES_GAME_UNPRICED}</Text>
      ) : (
      <View style={[styles.markets, stack && styles.marketsStack]}>
        {linesCardMarkets().map((market) => {
          const quotes = linesSideQuotes(odds, game.game_id, market, teams, game.commence_time);
          const label = linesMarketLabel(game.sport, market);
          const marked = picked?.cells.has(market) ?? false;
          const spoken = quotes
            .map((q) => {
              const price = q.price == null ? 'no price' : linesPriceText(q.price);
              const book = q.book ? ` at ${bookName(q.book)}` : '';
              return `${q.label}, current best price ${price}${book}`;
            })
            .join('. ');
          return (
            <Pressable
              key={market}
              onPress={() => onOpen(market)}
              accessibilityRole="button"
              accessibilityLabel={`${label}. ${spoken || 'No price'}.${marked ? ' Pick on this market.' : ''}`}
              accessibilityHint={LINES_CELL_HINT}
              style={({ pressed }) => [
                styles.cell,
                !stack && styles.cellShare,
                stack && styles.cellStack,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.cellLabelRow}>
                <Text style={styles.cellLabel} numberOfLines={1}>
                  {label}
                </Text>
                {marked ? <View style={styles.pickDot} accessibilityElementsHidden importantForAccessibility="no" /> : null}
              </View>
              {quotes.map((q) => (
                <View key={q.key}>
                  <Text style={styles.cellSide} numberOfLines={1}>
                    {q.name}
                  </Text>
                  {q.lineText ? <Text style={styles.cellLine}>{q.lineText}</Text> : null}
                  <Text style={styles.cellPrice}>
                    {q.price == null ? LINES_NO_PRICE : linesPriceText(q.price)}
                    {q.book ? <Text style={styles.cellBook}>{` ${bookLabelShort(q.book)}`}</Text> : null}
                  </Text>
                </View>
              ))}
            </Pressable>
          );
        })}
      </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  list: {
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
  },
  skeletonWrap: { gap: spacing.xs, paddingTop: spacing.sm },
  skeletonCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    marginHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.xs,
    gap: spacing.sm,
  },
  top: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  matchup: {
    flex: 1,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  time: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  pickChip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    minHeight: 44,
    justifyContent: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  pickChipText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  pausedChip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.pill,
    minHeight: 44,
    justifyContent: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  pausedChipText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
  },
  unpriced: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    minHeight: 44,
  },
  markets: {
    flexDirection: 'row',
    gap: spacing.xs,
  },
  marketsStack: {
    flexDirection: 'column',
  },
  cell: {
    minHeight: 44,
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    gap: 2,
  },
  cellShare: {
    flex: 1,
  },
  cellStack: {
    alignSelf: 'stretch',
  },
  cellLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  cellLabel: {
    flexShrink: 1,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  // Navy, on purpose. The bet green is the best price in the sheet, and a
  // pick is not a price.
  pickDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.brandNavy,
  },
  cellSide: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  cellLine: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  cellPrice: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  cellBook: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.regular,
    color: colors.textSecondary,
  },
  pressed: {
    opacity: 0.6,
  },
});

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { AddLineSheet } from '@/components/AddLineSheet';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { BookMark } from '@/components/BookMark';
import { EmptyState } from '@/components/EmptyState';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { FilterChip } from '@/components/filters/FilterChip';
import { LiveDot } from '@/components/LiveDot';
import { discColor } from '@/components/ScoreboardBoard';
import { Skeleton, SkeletonBlock } from '@/components/Skeleton';
import { useNcaafAbbrevs } from '@/hooks/useNcaafAbbrevs';
import { useNow } from '@/hooks/useNow';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { useScoreboard } from '@/hooks/useScoreboard';
import type { Sport } from '@/hooks/useSportFilter';
import { errorText, isAbortError } from '@/lib/errors';
import { formatAmerican, liveSlateDatesET, MINUS, todayET } from '@/lib/format';
import {
  gameBetCells,
  gamesDayHasLines,
  gamesDayStrip,
  type GameBetCell,
  type GameBetCells,
} from '@/lib/gamesBoard';
import { lineLegLabel } from '@/lib/lineLegs';
import { bookName } from '@/lib/markets';
import { sportDisplayName } from '@/lib/liveSports';
import { fetchGameLinesForDate } from '@/lib/queries';
import { orderScoreboard, presentScoreboard, type ScoreboardCard } from '@/lib/scoreboard';
import { buildTeamLineIndex, unstartedGameIds } from '@/lib/statsOdds';
import { colors, font, radii, spacing, opacity, card as cardStyle } from '@/lib/theme';
import type { OddsByBookRow } from '@/types';

/**
 * Stats → Games (Matt, 2026-11-27): one card per game, CBS-scoreboard style,
 * for the sport the Stats screen is on. A day strip runs three days back to
 * three ahead. Past and live games show the score; only TODAY's games that
 * have not started carry bet buttons — each team's spread and moneyline, the
 * Over and the Under — and a tap opens the "Add to betslip?" sheet
 * (lib/gamesBoard.ts).
 *
 * Games, live scores and days come from the Scoreboard's own read
 * (useScoreboard); prices come from every book's latest line for today
 * (fetchGameLinesForDate), shopped across the member's books like the Teams
 * board.
 */
export function GamesBoard({
  sport,
  onAdded,
  onOpenGame,
}: {
  sport: Sport;
  /** After a bet is added — Stats bounces back to the betslip when it came from there. */
  onAdded?: () => void;
  /** Opens the game page (the Scoreboard's). */
  onOpenGame?: (gameId: string) => void;
}) {
  const now = useNow();
  const today = todayET();
  const [date, setDate] = useState(today);
  // A board left open across midnight ET follows the calendar.
  const lastToday = useRef(today);
  if (lastToday.current !== today) {
    if (date === lastToday.current) setDate(today);
    lastToday.current = today;
  }
  const days = useMemo(() => gamesDayStrip(today), [today]);
  const dates = useMemo(() => (date === today ? liveSlateDatesET() : [date]), [date, today]);
  const board = useScoreboard(true, dates, sport, date);
  const abbrevs = useNcaafAbbrevs(sport === 'NCAAF');
  const { books, ready: booksReady } = usePreferredBooks();

  // Today's lines, every book. Read only on today's board.
  const withLines = gamesDayHasLines(date, today);
  const [lines, setLines] = useState<OddsByBookRow[]>([]);
  const [linesError, setLinesError] = useState<string | null>(null);
  const linesGen = useRef(0);
  const loadLines = useCallback(async () => {
    const gen = ++linesGen.current;
    if (!withLines) {
      setLines([]);
      setLinesError(null);
      return;
    }
    try {
      const rows = await fetchGameLinesForDate(today);
      if (gen !== linesGen.current) return;
      setLines(rows);
      setLinesError(null);
    } catch (e: unknown) {
      if (gen !== linesGen.current || isAbortError(e)) return;
      setLinesError(errorText(e));
    }
  }, [withLines, today]);
  useEffect(() => {
    void loadLines();
  }, [loadLines]);

  const [pulling, setPulling] = useState(false);
  const refresh = () => {
    setPulling(true);
    void Promise.all([board.refresh(), loadLines()]).finally(() => setPulling(false));
  };

  const cards = useMemo(() => {
    const out: ScoreboardCard[] = [];
    for (const game of board.games) {
      if (game.sport !== sport) continue;
      const c = presentScoreboard({
        game,
        pregame: board.quotes.get(game.game_id),
        inplay: board.inplay.get(game.game_id),
        feed: board.feeds.get(game.game_id) ?? null,
        abbrevs,
      });
      // Today also carries last night's late games while they are live.
      const onDay = game.game_date === date;
      if (!onDay && !(date === today && c.phase === 'live')) continue;
      out.push(c);
    }
    return orderScoreboard(out);
  }, [board.games, board.quotes, board.inplay, board.feeds, sport, abbrevs, date, today]);

  // Bet buttons: today's games that have not started, priced across the
  // member's books.
  const unstarted = useMemo(
    () => unstartedGameIds(board.games, new Date(now).toISOString()),
    [board.games, now],
  );
  const betCells = useMemo(() => {
    const out = new Map<string, GameBetCells>();
    if (!withLines || !booksReady) return out;
    const games = board.games.filter((g) => g.sport === sport && g.game_date === today);
    const build = (market: 'h2h' | 'spreads' | 'totals') =>
      buildTeamLineIndex(lines, games, { market, books, gameIds: unstarted });
    const idx = { h2h: build('h2h'), spreads: build('spreads'), totals: build('totals') };
    for (const g of games) {
      if (!unstarted.has(g.game_id)) continue;
      const cells = gameBetCells(g, idx, books, sport);
      if (cells) out.set(g.game_id, cells);
    }
    return out;
  }, [withLines, booksReady, board.games, sport, today, lines, books, unstarted]);

  const [sheet, setSheet] = useState<GameBetCell | null>(null);
  const sheetGame = sheet ? board.games.find((g) => g.game_id === sheet.input.spec.game_id) ?? null : null;

  const dayLabel = days.find((d) => d.date === date)?.label ?? date;
  const sportName = sportDisplayName(sport);

  return (
    <View style={styles.fill}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.dayScroll}
        contentContainerStyle={styles.days}
      >
        {days.map((d) => (
          <FilterChip key={d.date} label={d.label} active={d.date === date} onPress={() => setDate(d.date)} />
        ))}
      </ScrollView>

      {linesError && withLines ? (
        <ErrorBanner what="today’s lines" error={linesError} onRetry={() => void loadLines()} retrying={false} />
      ) : null}
      {board.liveError && board.loaded ? (
        <ErrorBanner
          what={`${sportName} live scores`}
          error={board.liveError}
          onRetry={() => void board.refresh()}
          retrying={board.loading}
        />
      ) : null}

      {!board.loaded && !board.error ? (
        <Skeleton label="the games" style={styles.skeletonWrap}>
          {[0, 1, 2].map((i) => (
            <View key={i} style={styles.skeletonCard}>
              <SkeletonBlock width="40%" height={14} />
              <SkeletonBlock width="100%" height={60} />
            </View>
          ))}
        </Skeleton>
      ) : !board.loaded && board.error ? (
        <ErrorState what="the games" error={board.error} onRetry={() => void board.refresh()} retrying={board.loading} />
      ) : (
        <FlatList
          data={cards}
          keyExtractor={(c) => c.gameId}
          contentContainerStyle={styles.list}
          ListFooterComponent={<BetslipBarSpacer />}
          refreshControl={<RefreshControl refreshing={pulling} onRefresh={refresh} />}
          ListEmptyComponent={
            <EmptyState
              title={`No ${sportName} games ${dayLabel === 'Today' || dayLabel === 'Tomorrow' || dayLabel === 'Yesterday' ? dayLabel.toLowerCase() : `on ${dayLabel}`}`}
              subtitle="Pick another day above."
            />
          }
          renderItem={({ item }) => (
            <GameCard
              card={item}
              cells={betCells.get(item.gameId) ?? null}
              showLines={withLines && unstarted.has(item.gameId)}
              onBet={setSheet}
              onOpen={onOpenGame ? () => onOpenGame(item.gameId) : undefined}
            />
          )}
        />
      )}

      <AddLineSheet
        input={sheet?.input ?? null}
        choices={sheet?.choices}
        game={sheetGame}
        onClose={() => setSheet(null)}
        onAdded={onAdded}
      />
    </View>
  );
}

function priceText(p: number): string {
  return formatAmerican(p).replace(/-/g, MINUS);
}

function GameCard({
  card,
  cells,
  showLines,
  onBet,
  onOpen,
}: {
  card: ScoreboardCard;
  cells: GameBetCells | null;
  /** Today and not started: the three bet columns replace the score. */
  showLines: boolean;
  onBet: (cell: GameBetCell) => void;
  onOpen?: () => void;
}) {
  const header =
    card.phase === 'live' ? (
      <View style={styles.liveBadge}>
        <LiveDot />
        <Text style={styles.liveBadgeText}>LIVE</Text>
      </View>
    ) : null;
  return (
    <View style={styles.card}>
      <Pressable
        onPress={onOpen}
        disabled={!onOpen}
        // 28pt row plus 8pt either side: a 44pt target without a taller card.
        hitSlop={{ top: 8, bottom: 8 }}
        accessibilityRole={onOpen ? 'button' : undefined}
        accessibilityLabel={card.accessibilityLabel}
        accessibilityHint={onOpen ? 'Opens the game' : undefined}
        style={({ pressed }) => [styles.head, pressed && onOpen ? styles.pressed : null]}
      >
        {header}
        {card.footerText ? (
          <Text style={styles.headText} numberOfLines={1}>
            {card.footerText}
          </Text>
        ) : null}
        <View style={styles.headSpacer} />
        {showLines ? (
          <View style={styles.colHeads} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            <Text style={styles.colHead}>SPREAD</Text>
            <Text style={styles.colHead}>TOTAL</Text>
            <Text style={styles.colHead}>ML</Text>
          </View>
        ) : null}
      </Pressable>
      {(['away', 'home'] as const).map((side) => {
        const row = card[side];
        const bets = cells?.[side] ?? null;
        return (
          <View key={side} style={styles.side}>
            <View style={styles.team}>
              <View style={[styles.disc, { backgroundColor: discColor(row.disc) }]}>
                <Text style={styles.discText} numberOfLines={1}>
                  {row.disc}
                </Text>
              </View>
              <Text style={styles.teamName} numberOfLines={1} maxFontSizeMultiplier={1.6}>
                {row.name}
              </Text>
            </View>
            {showLines ? (
              <>
                <BetButton cell={bets?.spread ?? null} what="spread" onBet={onBet} />
                <BetButton cell={bets?.total ?? null} what="total" onBet={onBet} />
                <BetButton cell={bets?.ml ?? null} what="moneyline" onBet={onBet} />
              </>
            ) : (
              <Text
                style={[styles.score, row.scoreMuted && styles.scoreMuted]}
                numberOfLines={1}
                maxFontSizeMultiplier={1.6}
              >
                {row.score}
              </Text>
            )}
          </View>
        );
      })}
      {card.situation ? <Text style={styles.situation}>{card.situation}</Text> : null}
    </View>
  );
}

function BetButton({
  cell,
  what,
  onBet,
}: {
  cell: GameBetCell | null;
  what: string;
  onBet: (cell: GameBetCell) => void;
}) {
  if (!cell) {
    return (
      <View style={[styles.bet, styles.betEmpty]} accessible accessibilityLabel={`No ${what} posted yet`}>
        <Text style={styles.betDash}>—</Text>
      </View>
    );
  }
  const price = priceText(cell.price);
  return (
    <Pressable
      onPress={() => onBet(cell)}
      accessibilityRole="button"
      accessibilityLabel={`${lineLegLabel(cell.input.spec)}, ${price} at ${bookName(cell.book)}`}
      accessibilityHint="Asks to add this bet to your betslip"
      style={({ pressed }) => [styles.bet, pressed && styles.pressed]}
    >
      {cell.line ? (
        <Text style={styles.betLine} numberOfLines={1} maxFontSizeMultiplier={1.4}>
          {cell.line.replace(/-/g, MINUS)}
        </Text>
      ) : null}
      <View style={styles.betPriceRow}>
        <Text style={styles.betPrice} numberOfLines={1} maxFontSizeMultiplier={1.4}>
          {price}
        </Text>
        <BookMark book={cell.book} size={10} color={colors.textSecondary} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  dayScroll: { flexGrow: 0 },
  days: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
  },
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.sm,
  },
  skeletonWrap: { paddingHorizontal: spacing.lg, gap: spacing.sm },
  skeletonCard: { ...cardStyle, gap: spacing.sm, padding: spacing.md },
  card: {
    ...cardStyle,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
  },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    minHeight: 28,
  },
  headText: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  headSpacer: { flex: 1 },
  colHeads: { flexDirection: 'row', gap: spacing.xs },
  colHead: {
    width: 64,
    textAlign: 'center',
    fontFamily: font.family,
    fontSize: font.size.nano,
    fontWeight: font.weight.bold,
    color: colors.textTertiary,
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.avoidSoft,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    minHeight: 20,
  },
  liveBadgeText: {
    fontFamily: font.family,
    fontSize: font.size.micro,
    fontWeight: font.weight.bold,
    color: colors.avoidInk,
  },
  side: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    minHeight: 48,
  },
  team: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    minWidth: 0,
  },
  disc: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  discText: {
    fontFamily: font.family,
    fontSize: font.size.nano,
    fontWeight: font.weight.bold,
    color: colors.onChrome,
  },
  teamName: {
    flexShrink: 1,
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  score: {
    fontFamily: font.family,
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
    minWidth: 40,
    textAlign: 'right',
  },
  scoreMuted: { color: colors.textTertiary },
  bet: {
    width: 64,
    minHeight: 44,
    borderRadius: radii.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separatorOpaque,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 2,
  },
  betEmpty: { borderStyle: 'dashed' },
  betDash: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textTertiary,
  },
  betLine: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  betPriceRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  betPrice: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  situation: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  pressed: { opacity: opacity.pressed },
});

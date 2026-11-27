import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';

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
import { dayLabelET, formatAmerican, formatGameTimeET, liveSlateDatesET, MINUS, todayET } from '@/lib/format';
import {
  gameBetCells,
  gamesCardLabel,
  gamesDayHasLines,
  gamesDayStrip,
  newestSnapshot,
  type GameBetCell,
  type GameBetCells,
} from '@/lib/gamesBoard';
import { lineLegLabel } from '@/lib/lineLegs';
import { bookName } from '@/lib/markets';
import { sportDisplayName } from '@/lib/liveSports';
import { fetchGameLinesForDate } from '@/lib/queries';
import { orderScoreboard, presentScoreboard, type ScoreboardCard, type ScoreboardPhase } from '@/lib/scoreboard';
import { buildTeamLineIndex, unstartedGameIds } from '@/lib/statsOdds';
import { colors, font, radii, spacing, opacity, cardDense, sectionHeaderText } from '@/lib/theme';
import type { OddsByBookRow } from '@/types';

/** How often today's prices are re-read while the board is open. */
const LINES_POLL_MS = 60_000;

const PHASE_LABEL: Record<ScoreboardPhase, string> = {
  live: 'Live',
  upcoming: 'Upcoming',
  final: 'Final',
};

/** What a price cell shows when it has no button. */
type CellState = 'loading' | 'failed' | 'none';

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
 * board, and re-read every minute while the board is open.
 *
 * Premium like the Scoreboard it is built on: a locked member sees the
 * unlock card, not the board.
 */
export function GamesBoard({
  sport,
  locked,
  onUnlock,
  onAdded,
  onOpenGame,
}: {
  sport: Sport;
  /** The member has no Premium: the Scoreboard's lock applies here too. */
  locked: boolean;
  onUnlock: () => void;
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
  const board = useScoreboard(!locked, dates, sport, date);
  const abbrevs = useNcaafAbbrevs(sport === 'NCAAF');
  const { books, ready: booksReady } = usePreferredBooks();
  const { width, fontScale } = useWindowDimensions();
  // At 320pt three 64pt buttons leave the team name ~24pt; at large text the
  // disc goes and the name keeps the room (UX review, 2026-11-27).
  const compact = width < 360 || fontScale > 1.3;

  // Today's lines, every book. Read only on today's board.
  const withLines = gamesDayHasLines(date, today) && !locked;
  const [lines, setLines] = useState<OddsByBookRow[]>([]);
  const [linesLoaded, setLinesLoaded] = useState(false);
  const [linesError, setLinesError] = useState<string | null>(null);
  const [linesRetrying, setLinesRetrying] = useState(false);
  const linesGen = useRef(0);
  const loadLines = useCallback(async () => {
    const gen = ++linesGen.current;
    if (!withLines) {
      setLines([]);
      setLinesError(null);
      setLinesLoaded(false);
      return;
    }
    try {
      const rows = await fetchGameLinesForDate(today);
      if (gen !== linesGen.current) return;
      setLines(rows);
      setLinesError(null);
      setLinesLoaded(true);
    } catch (e: unknown) {
      if (gen !== linesGen.current || isAbortError(e)) return;
      setLinesError(errorText(e));
      setLinesLoaded(true);
    }
  }, [withLines, today]);
  useEffect(() => {
    void loadLines();
    if (!withLines) return;
    // Prices move all day; the buttons must not sit on a morning number.
    const id = setInterval(() => void loadLines(), LINES_POLL_MS);
    return () => clearInterval(id);
  }, [loadLines, withLines]);
  const retryLines = () => {
    setLinesRetrying(true);
    void loadLines().finally(() => setLinesRetrying(false));
  };

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
  // member's books. Indexed PER GAME — the indexes key on the team, so one
  // index over a doubleheader would hand game 1 game 2's prices (UX review).
  const unstarted = useMemo(
    () => unstartedGameIds(board.games, new Date(now).toISOString()),
    [board.games, now],
  );
  const betCells = useMemo(() => {
    const out = new Map<string, GameBetCells>();
    if (!withLines || !booksReady) return out;
    for (const g of board.games) {
      if (g.sport !== sport || g.game_date !== today || !unstarted.has(g.game_id)) continue;
      const only = new Set([g.game_id]);
      const build = (market: 'h2h' | 'spreads' | 'totals') =>
        buildTeamLineIndex(lines, [g], { market, books, gameIds: only });
      const cells = gameBetCells(g, { h2h: build('h2h'), spreads: build('spreads'), totals: build('totals') }, books, sport);
      if (cells) out.set(g.game_id, cells);
    }
    return out;
  }, [withLines, booksReady, board.games, sport, today, lines, books, unstarted]);
  const cellState: CellState = !linesLoaded || !booksReady ? 'loading' : linesError ? 'failed' : 'none';
  const asOf = withLines && linesLoaded && !linesError ? newestSnapshot(lines) : null;

  const [sheet, setSheet] = useState<GameBetCell | null>(null);
  const sheetGame = sheet ? board.games.find((g) => g.game_id === sheet.input.spec.game_id) ?? null : null;

  const dayLabel = days.find((d) => d.date === date)?.label ?? date;
  const sportName = sportDisplayName(sport);
  const dayPhrase = dayLabel === 'Today' || dayLabel === 'Tomorrow' || dayLabel === 'Yesterday'
    ? dayLabel.toLowerCase()
    : `on ${dayLabel}`;
  const next = board.nextGame && board.nextGame.game_date !== date ? board.nextGame : null;

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

      {locked ? (
        <EmptyState
          title="Games is Premium"
          subtitle="Scores for every day and today’s lines at your books, one tap from your betslip."
          actionLabel="Unlock with Premium"
          onAction={onUnlock}
        />
      ) : (
        <>
          {linesError && withLines ? (
            <ErrorBanner what="today’s lines" error={linesError} onRetry={retryLines} retrying={linesRetrying} />
          ) : null}
          {board.liveError && board.loaded ? (
            <ErrorBanner
              what={`${sportName} live scores`}
              error={board.liveError}
              onRetry={() => void board.refresh()}
              retrying={board.loading}
            />
          ) : null}
          {asOf ? (
            <Text style={styles.asOf}>{`Best price at your books · as of ${formatGameTimeET(asOf)}`}</Text>
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
                  title={`No ${sportName} games ${dayPhrase}`}
                  subtitle={next ? `Next slate: ${dayLabelET(next.game_date, today)}` : 'Pick another day above.'}
                  actionLabel={next ? `See ${dayLabelET(next.game_date, today)}` : undefined}
                  onAction={next ? () => setDate(next.game_date) : undefined}
                />
              }
              renderItem={({ item, index }) => (
                <View>
                  {index === 0 || cards[index - 1]?.phase !== item.phase ? (
                    <Text style={[styles.group, index > 0 && styles.groupGap]} accessibilityRole="header">
                      {`${PHASE_LABEL[item.phase]} · ${cards.filter((c) => c.phase === item.phase).length}`}
                    </Text>
                  ) : null}
                  <GameCard
                    card={item}
                    cells={betCells.get(item.gameId) ?? null}
                    cellState={cellState}
                    showLines={withLines && unstarted.has(item.gameId)}
                    compact={compact}
                    onBet={setSheet}
                    onOpen={onOpenGame ? () => onOpenGame(item.gameId) : undefined}
                  />
                </View>
              )}
            />
          )}
        </>
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
  cellState,
  showLines,
  compact,
  onBet,
  onOpen,
}: {
  card: ScoreboardCard;
  cells: GameBetCells | null;
  cellState: CellState;
  /** Today and not started: the three bet columns replace the score. */
  showLines: boolean;
  /** Narrow screen or large text: no disc, so the name keeps its room. */
  compact: boolean;
  onBet: (cell: GameBetCell) => void;
  onOpen?: () => void;
}) {
  return (
    <View style={styles.card}>
      <Pressable
        onPress={onOpen}
        disabled={!onOpen}
        // 28pt row plus 8pt either side: a 44pt target without a taller card.
        hitSlop={{ top: 8, bottom: 8 }}
        accessibilityRole={onOpen ? 'button' : undefined}
        accessibilityLabel={gamesCardLabel(card)}
        accessibilityHint={onOpen ? 'Opens the game' : undefined}
        style={({ pressed }) => [styles.head, pressed && onOpen ? styles.pressed : null]}
      >
        {card.phase === 'live' ? (
          <View style={styles.liveBadge}>
            <LiveDot />
            <Text style={styles.liveBadgeText}>LIVE</Text>
          </View>
        ) : null}
        {card.footerText ? (
          <Text style={styles.headText} numberOfLines={1}>
            {card.footerText}
          </Text>
        ) : null}
        <View style={styles.headSpacer} />
        {showLines ? (
          <View style={styles.colHeads} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            {['SPREAD', 'TOTAL', 'ML'].map((h) => (
              <Text key={h} style={styles.colHead} numberOfLines={1} maxFontSizeMultiplier={1.4}>
                {h}
              </Text>
            ))}
          </View>
        ) : null}
      </Pressable>
      {(['away', 'home'] as const).map((side) => {
        const row = card[side];
        const bets = cells?.[side] ?? null;
        return (
          <View key={side} style={styles.side}>
            <View style={styles.team}>
              {compact ? null : (
                <View style={[styles.disc, { backgroundColor: discColor(row.disc) }]}>
                  <Text style={styles.discText} numberOfLines={1}>
                    {row.disc}
                  </Text>
                </View>
              )}
              <Text style={styles.teamName} numberOfLines={1}>
                {row.name}
              </Text>
            </View>
            {showLines ? (
              <>
                <BetButton cell={bets?.spread ?? null} state={cellState} what="spread" onBet={onBet} />
                <BetButton cell={bets?.total ?? null} state={cellState} what="total" onBet={onBet} />
                <BetButton cell={bets?.ml ?? null} state={cellState} what="moneyline" onBet={onBet} />
              </>
            ) : (
              <Text style={[styles.score, row.scoreMuted && styles.scoreMuted]} numberOfLines={1} maxFontSizeMultiplier={1.6}>
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
  state,
  what,
  onBet,
}: {
  cell: GameBetCell | null;
  state: CellState;
  what: string;
  onBet: (cell: GameBetCell) => void;
}) {
  if (!cell) {
    if (state === 'loading') return <SkeletonBlock width={64} height={44} />;
    // A failed read is explained once, by the banner; a cell does not claim
    // nothing is posted when we could not look.
    const spoken = state === 'failed' ? `${what} unavailable` : `No ${what} at your books yet`;
    return (
      <View style={[styles.bet, styles.betEmpty]} accessible accessibilityLabel={spoken}>
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
  asOf: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xs,
  },
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.sm,
  },
  group: {
    ...sectionHeaderText,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.xs,
  },
  groupGap: { marginTop: spacing.sm },
  skeletonWrap: { paddingHorizontal: spacing.lg, gap: spacing.sm },
  skeletonCard: { ...cardDense, gap: spacing.sm },
  card: {
    ...cardDense,
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
    fontSize: font.size.micro,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
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
    borderRadius: radii.pill,
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

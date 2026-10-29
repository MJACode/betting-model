import React, { useMemo, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { LiveDot } from '@/components/LiveDot';
import { FilterChip } from '@/components/filters/FilterChip';
import { Skeleton, SkeletonBlock } from '@/components/Skeleton';
import { useNcaafAbbrevs } from '@/hooks/useNcaafAbbrevs';
import { addDays, dayLabelET } from '@/lib/format';
import {
  SCOREBOARD_BOOK_NOTE,
  SCOREBOARD_SPORTS,
  nextSlateText,
  orderScoreboard,
  presentScoreboard,
  scoreboardSwitchLine,
  type ScoreboardCard,
  type ScoreboardFeed,
  type ScoreboardPhase,
  type ScoreboardQuote,
  type ScoreboardSport,
} from '@/lib/scoreboard';
import { colors, font, radii, spacing, teamDisc } from '@/lib/theme';
import type { GameRow } from '@/types';

const PHASE_LABEL: Record<ScoreboardPhase, string> = {
  live: 'Live',
  upcoming: 'Upcoming',
  final: 'Final',
};

function discColor(label: string): string {
  let h = 0;
  for (let i = 0; i < label.length; i++) h = (h + label.charCodeAt(i) * (i + 1)) % 997;
  return teamDisc[h % teamDisc.length] ?? teamDisc[0];
}

function sportIcon(sport: string): React.ComponentProps<typeof Ionicons>['name'] | null {
  if (sport === 'NFL' || sport === 'NCAAF') return 'american-football';
  if (sport === 'MLB') return 'baseball';
  if (sport === 'NBA') return 'basketball';
  return null;
}

export function ScoreboardBoard({
  games,
  quotes,
  feeds,
  inplay,
  nextGame,
  sport,
  onSport,
  date,
  today,
  onDate,
  loading,
  loaded,
  error,
  linesError,
  liveError,
  ncaafUnavailable,
  liveScoresUnavailable,
  retrying,
  onRefresh,
  locked,
  onUnlock,
  onTrial,
  onRestore,
  onRecord,
  onOpenGame,
}: {
  games: GameRow[];
  quotes: ReadonlyMap<string, ScoreboardQuote[]>;
  feeds: ReadonlyMap<string, ScoreboardFeed>;
  inplay: ReadonlyMap<string, ScoreboardQuote[]>;
  nextGame: GameRow | null;
  sport: ScoreboardSport;
  onSport: (sport: ScoreboardSport) => void;
  date: string;
  today: string;
  onDate: (date: string) => void;
  loading: boolean;
  loaded: boolean;
  error: string | null;
  linesError: string | null;
  /** The selected sport's live feed failed. Null when that sport has no feed. */
  liveError: string | null;
  ncaafUnavailable: boolean;
  /** live_scoreboard is not readable yet (migration not applied). */
  liveScoresUnavailable: boolean;
  retrying: boolean;
  onRefresh: () => Promise<void>;
  locked: boolean;
  onUnlock: () => void;
  onTrial: () => void;
  onRestore: () => void;
  onRecord: () => void;
  onOpenGame: (gameId: string) => void;
}) {
  const abbrevs = useNcaafAbbrevs(true);
  const [pulling, setPulling] = useState(false);
  const [datesOpen, setDatesOpen] = useState(false);
  const dayWord = dayLabelET(date, today);

  const dayGames = useMemo(
    () => games.filter((g) => g.game_date === date),
    [games, date],
  );
  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const g of dayGames) out[g.sport] = (out[g.sport] ?? 0) + 1;
    return out;
  }, [dayGames]);

  const sportCards = useMemo(() => {
    if (locked) return [] as ScoreboardCard[];
    const rows: ScoreboardCard[] = [];
    for (const game of games) {
      if (game.sport !== sport) continue;
      const card = presentScoreboard({
        game,
        pregame: quotes.get(game.game_id),
        inplay: inplay.get(game.game_id),
        feed: feeds.get(game.game_id) ?? null,
        abbrevs,
      });
      const onDay = game.game_date === date;
      const carried = !onDay && date === today && card.phase === 'live';
      if (!onDay && !carried) continue;
      rows.push(card);
    }
    return rows;
  }, [locked, games, sport, quotes, inplay, feeds, abbrevs, date, today]);
  // Every game for the sport in one list (Matt, 2026-10-29): live, then
  // upcoming, then final. A label marks where each group starts.
  const cards = useMemo(() => orderScoreboard(sportCards), [sportCards]);

  const refresh = () => {
    setPulling(true);
    void onRefresh().finally(() => setPulling(false));
  };

  const dayPhrase = dayWord === 'Today' || dayWord === 'Tomorrow' || dayWord === 'Yesterday'
    ? dayWord.toLowerCase()
    : `on ${dayWord}`;
  const emptyTitle = `No ${sport} games ${dayPhrase}`;
  const next = nextSlateText(nextGame, abbrevs);
  const emptyBody = next ? `Next slate: ${next}` : 'Games show up here once they’re on the board.';
  const emptyAction = nextGame && nextGame.game_date !== date
    ? `See ${dayLabelET(nextGame.game_date, today)}`
    : null;
  const nudge = (counts[sport] ?? 0) === 0 ? scoreboardSwitchLine(counts, sport) : null;
  const ncaafNote = sport === 'NCAAF' && ncaafUnavailable
    ? 'Live NCAAF scores aren’t available in this build yet.'
    : (sport === 'NFL' || sport === 'NBA' || sport === 'NHL') && liveScoresUnavailable
      ? `Live ${sport} scores aren’t available yet. Finals show once stored.`
      : null;

  return (
    <View style={styles.fill}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.sportScroll}
        contentContainerStyle={styles.sports}
      >
        {SCOREBOARD_SPORTS.map((id) => (
          <FilterChip
            key={id}
            label={id}
            active={sport === id}
            onPress={() => onSport(id)}
            accessibilityLabel={id}
          />
        ))}
      </ScrollView>

      <View style={styles.filters}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`${dayWord}, DraftKings. Choose a day.`}
          onPress={() => setDatesOpen((v) => !v)}
          style={({ pressed }) => [styles.today, pressed && styles.pressed]}
        >
          <Text style={styles.todayText}>{dayWord}</Text>
          <Ionicons name="chevron-down" size={14} color={colors.textSecondary} />
          <Text style={styles.todayBook}>· DK</Text>
        </Pressable>
      </View>
      {datesOpen ? (
        <View style={styles.dateRow}>
          {[-1, 0, 1].map((step) => {
            const id = addDays(today, step);
            return (
              <FilterChip
                key={id}
                label={dayLabelET(id, today)}
                active={date === id}
                onPress={() => {
                  onDate(id);
                  setDatesOpen(false);
                }}
              />
            );
          })}
        </View>
      ) : null}
      {ncaafNote ? <Text style={styles.caption}>{ncaafNote}</Text> : null}
      {linesError && loaded ? (
        <ErrorBanner
          what="DraftKings lines"
          error={linesError}
          onRetry={() => void onRefresh()}
          retrying={retrying}
        />
      ) : null}
      {liveError && loaded ? (
        <ErrorBanner
          what={`${sport} live scores`}
          error={liveError}
          onRetry={() => void onRefresh()}
          retrying={retrying}
        />
      ) : null}

      {locked ? (
        <LockedBoard onUnlock={onUnlock} onTrial={onTrial} onRestore={onRestore} onRecord={onRecord} />
      ) : !loaded && !error ? (
        <Skeleton label="the scoreboard" style={styles.skeletonWrap}>
          {[0, 1, 2].map((i) => (
            <View key={i} style={styles.skeletonCard}>
              <SkeletonBlock width="40%" height={14} />
              <SkeletonBlock width="100%" height={44} />
            </View>
          ))}
        </Skeleton>
      ) : !loaded && error ? (
        <ErrorState
          what="the scoreboard"
          error={error}
          onRetry={() => void onRefresh()}
          retrying={retrying}
        />
      ) : (
        <FlatList
          data={cards}
          keyExtractor={(c) => c.gameId}
          contentContainerStyle={styles.list}
          ListFooterComponent={<BetslipBarSpacer />}
          refreshControl={<RefreshControl refreshing={pulling} onRefresh={refresh} />}
          ListHeaderComponent={
            <View>
              {error ? (
                <ErrorBanner
                  what="the scoreboard"
                  error={error}
                  onRetry={() => void onRefresh()}
                  retrying={retrying}
                />
              ) : null}
              {cards.length > 0 ? (
                <View style={styles.cols}>
                  <Text style={[styles.colHead, styles.colMatch]}>Matchup</Text>
                  <Text
                    style={[styles.colHead, styles.colScore]}
                    numberOfLines={1}
                    adjustsFontSizeToFit
                    minimumFontScale={0.7}
                  >
                    Score
                  </Text>
                  <Text style={[styles.colHead, styles.colLine]}>{sport === 'NHL' ? 'Puck line' : 'Spread'}</Text>
                  <Text style={[styles.colHead, styles.colLine]}>Total</Text>
                </View>
              ) : null}
            </View>
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              {sportIcon(sport) ? (
                <Ionicons name={sportIcon(sport)!} size={36} color={colors.textTertiary} />
              ) : (
                <View style={styles.puck} accessibilityElementsHidden />
              )}
              <Text style={styles.emptyTitle}>{emptyTitle}</Text>
              <Text style={styles.emptyBody}>{emptyBody}</Text>
              {emptyAction ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={emptyAction}
                onPress={() => {
                  if (nextGame) onDate(nextGame.game_date);
                }}
                style={({ pressed }) => [styles.emptyBtn, pressed && styles.pressed]}
              >
                <Text style={styles.emptyBtnText}>{emptyAction}</Text>
              </Pressable>
              ) : null}
              {nudge ? <Text style={styles.nudge}>{nudge}</Text> : null}
            </View>
          }
          renderItem={({ item, index }) => (
            <View>
              {index === 0 || cards[index - 1]?.phase !== item.phase ? (
                <Text style={[styles.group, index > 0 && styles.groupGap]} accessibilityRole="header">
                  {`${PHASE_LABEL[item.phase]} · ${cards.filter((c) => c.phase === item.phase).length}`}
                </Text>
              ) : null}
              <GameCard card={item} onPress={() => onOpenGame(item.gameId)} />
            </View>
          )}
        />
      )}
    </View>
  );
}

function LockedBoard({
  onUnlock,
  onTrial,
  onRestore,
  onRecord,
}: {
  onUnlock: () => void;
  onTrial: () => void;
  onRestore: () => void;
  onRecord: () => void;
}) {
  return (
    <View style={styles.lockWrap}>
      <View
        style={styles.lockFade}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        {[0, 1].map((i) => (
          <View key={i} style={styles.ghost}>
            <View style={styles.ghostBar} />
            <View style={styles.ghostBarShort} />
          </View>
        ))}
      </View>
      <View style={styles.lockCard}>
        <View style={styles.lockIcon}>
          <Ionicons name="lock-closed" size={22} color={colors.tint} />
        </View>
        <Text style={styles.lockTitle}>Scoreboard is Premium</Text>
        <Text style={styles.lockBody}>
          Live scores and DK lines for every game. Free keeps the Record tab.
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Unlock with Premium"
          onPress={onUnlock}
          style={({ pressed }) => [styles.lockBtn, pressed && styles.pressed]}
        >
          <Text style={styles.lockBtnText}>Unlock with Premium</Text>
        </Pressable>
        <View style={styles.lockLinks}>
          <Pressable accessibilityRole="button" accessibilityLabel="Start free trial" onPress={onTrial} style={styles.lockLinkBtn}>
            <Text style={styles.lockLink}>Start free trial</Text>
          </Pressable>
          <Text style={styles.lockDot}>·</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Restore purchase" onPress={onRestore} style={styles.lockLinkBtn}>
            <Text style={styles.lockLink}>Restore purchase</Text>
          </Pressable>
        </View>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Record stays free. See how every model did."
        onPress={onRecord}
        style={({ pressed }) => [styles.recordRow, pressed && styles.pressed]}
      >
        <View style={styles.recordText}>
          <Text style={styles.recordTitle}>Record stays free</Text>
          <Text style={styles.recordBody}>See how every model did — all sports, all time.</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
      </Pressable>
    </View>
  );
}

function GameCard({ card, onPress }: { card: ScoreboardCard; onPress: () => void }) {
  const ink = card.linesMuted ? colors.textTertiary : colors.textPrimary;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={card.accessibilityLabel}
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <SideRow card={card} side="away" ink={ink} />
      <SideRow card={card} side="home" ink={ink} />
      {card.showMl ? (
        <Text style={styles.mlLine}>
          ML  {card.away.name} {card.away.ml} · {card.home.name} {card.home.ml}
        </Text>
      ) : null}
      {card.situation ? <Text style={styles.situation}>{card.situation}</Text> : null}
      <View style={styles.footer}>
        <View style={styles.footerLeft}>
          {card.footerBadge === 'LIVE' ? (
            <View style={styles.liveBadge}>
              <LiveDot />
              <Text style={styles.liveBadgeText}>LIVE</Text>
            </View>
          ) : null}
          {card.footerBadge === 'F' ? (
            <View style={styles.finalBadge}>
              <Text style={styles.finalBadgeText}>F</Text>
            </View>
          ) : null}
          {card.footerText ? <Text style={styles.footerText}>{card.footerText}</Text> : null}
        </View>
        <Text style={styles.bookNote}>{SCOREBOARD_BOOK_NOTE}</Text>
      </View>
      {card.updatedLabel ? <Text style={styles.updated}>{card.updatedLabel}</Text> : null}
    </Pressable>
  );
}

function SideRow({
  card,
  side,
  ink,
}: {
  card: ScoreboardCard;
  side: 'away' | 'home';
  ink: string;
}) {
  const row = card[side];
  const scoreColor = row.scoreMuted ? colors.textTertiary : colors.textPrimary;
  return (
    <View style={styles.side}>
      <View style={[styles.colMatch, styles.match]}>
        <View style={[styles.disc, { backgroundColor: discColor(row.disc) }]}>
          <Text style={styles.discText} numberOfLines={1}>{row.disc}</Text>
        </View>
        <Text style={styles.abbr} numberOfLines={1}>{row.name}</Text>
        {row.possession ? <Text style={styles.poss}>◀</Text> : null}
      </View>
      <Text
        style={[styles.score, styles.colScore, { color: scoreColor }]}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.7}
        maxFontSizeMultiplier={1.6}
      >
        {row.score}
      </Text>
      <LineCell value={row.spread} price={row.spreadPrice} ink={ink} />
      <LineCell value={row.total} price={row.totalPrice} ink={ink} />
    </View>
  );
}

function LineCell({
  value,
  price,
  ink,
  single = false,
}: {
  value: string;
  price: string;
  ink: string;
  single?: boolean;
}) {
  const shown = single || !price || price === '—' ? value : `${value}  ${price}`;
  return (
    <View style={[styles.cell, styles.colLine]}>
      <Text
        style={[styles.cellValue, { color: ink }]}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.7}
      >
        {shown === '—  —' ? '—' : shown}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  // A horizontal ScrollView in a column grows to fill the height it is
  // given, which stretched every sport pill (Matt's screenshot, 2026-10-29).
  sportScroll: { flexGrow: 0 },
  sports: {
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    paddingBottom: spacing.sm,
  },
  filters: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  group: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.xs,
  },
  groupGap: { marginTop: spacing.sm },
  today: {
    marginLeft: 'auto',
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  todayText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  todayBook: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  dateRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  caption: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.medInk,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  list: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xl },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: spacing.sm,
    minHeight: 44,
  },
  cols: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.xs,
  },
  colHead: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  colMatch: { flex: 1, minWidth: 80 },
  // 40 fits a three-digit NBA score and the 'Score' heading on one line.
  colScore: { width: 40, textAlign: 'center' },
  colLine: { width: 68, alignItems: 'center', textAlign: 'center' },
  side: { flexDirection: 'row', alignItems: 'center', minHeight: 44, gap: spacing.xs },
  match: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
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
    color: colors.textInverse,
  },
  abbr: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    flexShrink: 1,
  },
  poss: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textPrimary,
  },
  score: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
  },
  cell: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.xs,
    minHeight: 32,
    justifyContent: 'center',
  },
  cellValue: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    textAlign: 'center',
  },
  mlLine: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  situation: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  footerLeft: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, flexShrink: 1 },
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
  finalBadge: {
    backgroundColor: colors.noneSoft,
    borderRadius: radii.xs,
    paddingHorizontal: spacing.xs,
    minHeight: 20,
    justifyContent: 'center',
  },
  finalBadgeText: {
    fontFamily: font.family,
    fontSize: font.size.nano,
    fontWeight: font.weight.bold,
    color: colors.textSecondary,
  },
  footerText: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    flexShrink: 1,
  },
  bookNote: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  updated: {
    fontFamily: font.family,
    fontSize: font.size.nano,
    color: colors.textTertiary,
  },
  empty: {
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xxl,
    gap: spacing.sm,
  },
  puck: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.textTertiary,
  },
  emptyTitle: {
    fontFamily: font.family,
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  emptyBody: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 18,
  },
  emptyBtn: {
    marginTop: spacing.sm,
    minHeight: 48,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    backgroundColor: colors.brandNavy,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyBtnText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  nudge: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
  lockWrap: { flex: 1, justifyContent: 'flex-end' },
  lockFade: { paddingHorizontal: spacing.lg, gap: spacing.md, opacity: 0.35 },
  ghost: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  ghostBar: { height: 14, borderRadius: radii.xs, backgroundColor: colors.noneSoft },
  ghostBarShort: { height: 14, width: '60%', borderRadius: radii.xs, backgroundColor: colors.noneSoft },
  lockCard: {
    margin: spacing.lg,
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.xl,
    alignItems: 'center',
    gap: spacing.sm,
  },
  lockIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  lockTitle: {
    fontFamily: font.family,
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  lockBody: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 18,
  },
  lockBtn: {
    marginTop: spacing.sm,
    alignSelf: 'stretch',
    minHeight: 48,
    borderRadius: radii.md,
    backgroundColor: colors.brandNavy,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  lockBtnText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  lockLinks: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  lockLinkBtn: { minHeight: 44, justifyContent: 'center', paddingHorizontal: spacing.sm },
  recordRow: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.lg,
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    minHeight: 64,
  },
  recordText: { flex: 1, gap: 2 },
  recordTitle: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  recordBody: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  lockLink: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  lockDot: { color: colors.textTertiary, fontSize: font.size.footnote },
  skeletonWrap: { padding: spacing.lg, gap: spacing.md },
  skeletonCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  pressed: { opacity: 0.6 },
});

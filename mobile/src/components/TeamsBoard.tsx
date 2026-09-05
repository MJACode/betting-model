/**
 * The Teams half of the Stats tab.
 *
 * Same shape as the player leaderboard — group tabs, stat chips, one ranked
 * list — so switching between Players and Teams does not mean learning a
 * second interface. What differs is the ordering of what it offers: efficiency
 * metrics first, plain record second, betting splits last and captioned, since
 * ATS and over/under records describe what happened rather than predicting
 * what will.
 *
 * Values are tinted by league tertile (top third / middle / bottom third)
 * oriented by each stat's direction, which is the glanceable pattern the
 * category's better tools use in place of a rank number.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AddLineSheet } from '@/components/AddLineSheet';
import { EmptyState } from '@/components/EmptyState';
import { GroupTabs } from '@/components/GroupTabs';
import { FilterChip } from '@/components/filters/FilterChip';
import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { BookMark } from '@/components/BookMark';
import { showToast } from '@/components/Toast';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import type { Sport } from '@/hooks/useSportFilter';
import { addDays, formatAmerican, todayET, weekdayET, gameStatus } from '@/lib/format';
import { bookLabel, bookName, booksLabel, booksNoneName, MODEL_BOOK } from '@/lib/markets';
import { teamLineSheetInput } from '@/lib/lineLegs';
import { bookButtonColors } from '@/lib/sportsbookLinks';
import { fetchGameLinesForDate, fetchSlateGames, fetchTeamStats } from '@/lib/queries';
import { buildTonightSlate } from '@/lib/statsBoard';
import {
  buildTeamLineIndex,
  teamLineCaption,
  teamLineMarketFor,
  unstartedGameIds,
  type TeamLineQuote,
} from '@/lib/statsOdds';
import {
  isThinSample,
  rankTeams,
  sampleFor,
  tierFor,
  type Tier,
} from '@/lib/teamBoard';
import {
  defaultTeamStatFor,
  formatRecord,
  formatTeamStat,
  teamGroupsForSport,
  teamStatValue,
  teamStatsForSport,
  type TeamStatDef,
  type TeamStatGroup,
} from '@/lib/teamStatCatalog';
import { colors, font, radii, spacing } from '@/lib/theme';
import { errorText } from '@/lib/errors';
import type { GameRow, OddsByBookRow, TeamStatsRow } from '@/types';

const AMBER = '#FF9500'; // mid tertile (no theme token)

/**
 * Seasons to try, newest first. Every league except MLB/WNBA is out of season
 * for part of the calendar year, and NFL/NCAAF label a season by its starting
 * year — so the current year is frequently empty and the board should fall
 * back to the most recent season with data rather than render blank.
 */
function seasonCandidates(): number[] {
  const y = new Date().getUTCFullYear();
  return [y, y - 1];
}

function tierColor(tier: Tier): string | undefined {
  if (tier === 'good') return colors.bet;
  if (tier === 'bad') return colors.avoid;
  if (tier === 'mid') return AMBER;
  return undefined;
}

export function TeamsBoard({
  sport,
  onAdded,
}: {
  sport: Sport;
  /** After a line is added — the Stats screen bounces back to the betslip
   *  when the member came from there, on this board as on Players. */
  onAdded?: () => void;
}) {
  const groups = useMemo(() => teamGroupsForSport(sport), [sport]);
  const [stat, setStat] = useState<TeamStatDef | null>(() => defaultTeamStatFor(sport));
  const [rows, setRows] = useState<TeamStatsRow[]>([]);
  const [season, setSeason] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState<string>('');

  // ── The LINE column: the user's sportsbook's number for each team's next
  // game, from that team's side. Matt, 2026-09-03: "see a current line for a
  // player or team … if they select FanDuel we only show FanDuel". The market
  // follows the stat (Over% beside the total, ATS% beside the spread, Win%
  // beside the moneyline — lib/statsOdds.teamLineMarketFor). No model, no
  // fallback outside the member's own books.
  // `ready` gates the column: the pill's book is the member's own, so a tap
  // before storage answers would show the wrong one (UX review).
  const { books, ready: booksReady } = usePreferredBooks();
  // THE PILL ASKS, here too (Matt, 2026-09-05: "Team line legs, yes build
  // it"). A tap opens AddLineSheet with the team's line — its moneyline, its
  // spread at the board's number, the game total — and every book's price
  // for it; the one action puts a GAME line leg in our betslip
  // (lib/lineLegs.ts). Until today this pill was the one control on the
  // Stats tab that still left the app.
  const [lineSheet, setLineSheet] = useState<TeamLineQuote | null>(null);
  const [slate, setSlate] = useState<{ date: string; isToday: boolean; games: GameRow[] }>({
    date: '',
    isToday: false,
    games: [],
  });
  const [gameLines, setGameLines] = useState<OddsByBookRow[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const from = todayET();
    // Today's games, or the next scheduled day for a sport that does not play
    // daily — the same rule the Players board's "Playing today" toggle uses.
    fetchSlateGames(sport, from, addDays(from, 7))
      .then(async (games) => {
        const t = buildTonightSlate(games, sport, from);
        const onDate = games.filter((g) => g.sport === sport && g.game_date === t.date);
        if (cancelled) return;
        setSlate({ date: t.date, isToday: t.isToday, games: onDate });
        if (!t.date) {
          setGameLines([]);
          return;
        }
        const lines = await fetchGameLinesForDate(t.date);
        if (!cancelled) setGameLines(lines);
      })
      // Enrichment only — the board must never break because the odds view is
      // unreachable. But say so: an unreachable view and "no games" both look
      // like an empty column.
      .catch((e: unknown) => {
        if (cancelled) return;
        setSlate({ date: '', isToday: false, games: [] });
        setGameLines([]);
        showToast(`Couldn’t load today’s lines — ${errorText(e)}`);
      });
    return () => {
      cancelled = true;
    };
  }, [sport]);

  // Reset to the sport's default stat whenever the sport changes — the stat
  // sets do not overlap across sports, so keeping the old one would be invalid.
  useEffect(() => {
    setStat(defaultTeamStatFor(sport));
    setQuery('');
  }, [sport]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      for (const s of seasonCandidates()) {
        const data = await fetchTeamStats(sport, s);
        if (data.length) {
          setRows(data);
          setSeason(s);
          return;
        }
      }
      setRows([]);
      setSeason(null);
    } catch (e: unknown) {
      setError(errorText(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [sport]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeGroup = stat?.group ?? groups[0];
  const pickGroup = (g: TeamStatGroup) => {
    if (g === activeGroup) return;
    const first = teamStatsForSport(sport).find((s) => s.group === g);
    if (first) setStat(first);
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.team.toLowerCase().includes(q) ||
        (r.conference ?? '').toLowerCase().includes(q),
    );
  }, [rows, query]);

  const { rows: ranked, cuts } = useMemo(
    () => (stat ? rankTeams(filtered, stat) : { rows: [], cuts: null }),
    [filtered, stat],
  );

  const lineMarket = stat ? teamLineMarketFor(String(stat.key)) : 'h2h';
  // Only games that have NOT started: a game in progress has no line a user
  // can still take, and its "latest" pre-game row is a live number.
  const unstarted = useMemo(
    () => unstartedGameIds(slate.games, new Date().toISOString()),
    [slate.games],
  );
  // Teams whose game is live or over: the cell says which ("Live" / "Final",
  // GameStatusPill's words) rather than printing a dash that reads as "no
  // line" (same as the Players board). A team with a game still to come gets
  // no label.
  const startedTeams = useMemo(() => {
    const out = new Map<string, 'Live' | 'Final'>();
    const pending = new Set<string>();
    for (const g of slate.games) {
      const teams = [g.home_team, g.away_team].filter(Boolean) as string[];
      if (unstarted.has(g.game_id)) {
        teams.forEach((t) => pending.add(t));
        continue;
      }
      const kind = gameStatus(g).kind;
      const label = kind === 'live' ? 'Live' : kind === 'final' || kind === 'ended' ? 'Final' : null;
      if (label) teams.forEach((t) => out.set(t, label));
    }
    pending.forEach((t) => out.delete(t));
    return out;
  }, [slate.games, unstarted]);
  const lineByTeam = useMemo(
    () =>
      buildTeamLineIndex(gameLines, slate.games, {
        market: lineMarket,
        books,
        gameIds: unstarted,
      }),
    [gameLines, slate.games, lineMarket, books, unstarted],
  );
  // Gated on the DAY and the BOOKS, never on which stat is selected — the
  // column must not come and go as the user taps through chips.
  const mine = useMemo(() => new Set<string>(books), [books]);
  const showLines =
    booksReady &&
    unstarted.size > 0 &&
    gameLines.some((r) => mine.has(r.bookmaker) && unstarted.has(r.game_id));
  // The header names the book when there is one, else the RULE ("BEST") — with
  // several books the cells no longer share one, so each pill carries its own
  // badge instead. Plus the day when it is not today; the market is on every
  // cell's caption ("ML", "−1.5", "o8.5").
  const lineHeader = `${booksLabel(books)}${slate.date && !slate.isToday ? ` ${weekdayET(slate.date)}` : ''}`;
  // None of their books posts anything for today's games — say so, with the switch.
  const noLinesNote =
    unstarted.size > 0 && gameLines.length > 0 && !gameLines.some((r) => mine.has(r.bookmaker))
      ? `${booksNoneName(books)} ${books.length === 1 ? 'hasn’t' : 'has'} posted lines for today’s games.`
      : null;

  if (!stat) {
    return (
      <EmptyState
        title="No team stats"
        subtitle={`Team stats aren't available for ${sport}.`}
      />
    );
  }

  return (
    <>
      {/* Group tabs — Efficiency first by design, and the same two-level tab
          bar the Players board uses (Matt, 2026-09-04). */}
      <GroupTabs groups={groups} active={activeGroup} onChange={pickGroup} />

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.fixedRow}
        contentContainerStyle={styles.chipRow}
        keyboardShouldPersistTaps="handled"
      >
        {teamStatsForSport(sport)
          .filter((s) => s.group === activeGroup)
          .map((s) => (
            <FilterChip
              key={String(s.key)}
              label={s.label}
              active={s.key === stat.key}
              onPress={() => setStat(s)}
            />
          ))}
      </ScrollView>

      {/* What this number is, and — for the betting group — what it isn't. */}
      {stat.hint ? (
        <View style={styles.hintRow}>
          <Text style={styles.hintText}>{stat.hint}</Text>
        </View>
      ) : null}
      {activeGroup === 'Betting' && !stat.hint ? (
        <View style={styles.hintRow}>
          <Text style={styles.hintText}>
            Betting records describe what already happened. They regress toward .500 once
            the market prices a trend in — read them as context, not as an edge.
          </Text>
        </View>
      ) : null}

      <View style={styles.searchWrap}>
        <Ionicons name="search" size={16} color={colors.textTertiary} />
        <TextInput
          style={styles.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder={sport === 'NCAAF' ? 'Search team or conference…' : 'Search teams…'}
          placeholderTextColor={colors.textTertiary}
          autoCorrect={false}
          returnKeyType="search"
        />
        {query.length > 0 ? (
          <Pressable onPress={() => setQuery('')} hitSlop={8} accessibilityRole="button" accessibilityLabel="Clear search">
            <Ionicons name="close-circle" size={18} color={colors.textTertiary} />
          </Pressable>
        ) : null}
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}

      {noLinesNote ? (
        <Pressable
          onPress={() => setPickerOpen(true)}
          accessibilityRole="button"
          accessibilityLabel={`${noLinesNote} Switch sportsbook`}
          style={({ pressed }) => [styles.noLinesRow, pressed && styles.pressed]}
        >
          <Ionicons name="information-circle-outline" size={13} color={colors.textTertiary} />
          <Text style={styles.noLinesText}>
            {noLinesNote} <Text style={styles.noLinesLink}>Change your sportsbooks ›</Text>
          </Text>
        </Pressable>
      ) : null}

      {ranked.length > 0 ? (
        <View style={styles.colHeader}>
          <Text style={styles.colHeaderRank}>RK</Text>
          <Text style={styles.colHeaderName}>
            TEAM{season ? `  ·  ${season}` : ''}
          </Text>
          <Text style={styles.colHeaderRight} numberOfLines={1}>
            {stat.label.toUpperCase()}
          </Text>
          {showLines ? (
            <Text style={[styles.colHeaderRight, styles.colHeaderLine]} numberOfLines={1}>
              {lineHeader}
            </Text>
          ) : null}
        </View>
      ) : null}

      <FlatList
        data={ranked}
        keyExtractor={(item) => item.team}
        renderItem={({ item, index }) => {
          const quote = lineByTeam.get(item.team) ?? null;
          return (
            <TeamRow
              rank={index + 1}
              row={item}
              def={stat}
              cuts={cuts}
              quote={quote}
              started={startedTeams.get(item.team) ?? null}
              showLine={showLines}
              // The pill asks: a tap opens the add-to-betslip sheet.
              onLinePress={quote ? () => setLineSheet(quote) : undefined}
            />
          );
        }}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator style={styles.loading} />
          ) : (
            <EmptyState
              title="No teams"
              subtitle={
                query.trim()
                  ? `Nothing matched "${query.trim()}".`
                  : `No ${sport} team stats yet. Records fill in as games are played and lines are stored.`
              }
            />
          )
        }
        style={styles.listFlex}
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
        initialNumToRender={20}
      />

      <SportsbookPickerSheet visible={pickerOpen} onClose={() => setPickerOpen(false)} />
      <AddLineSheet
        input={lineSheet ? teamLineSheetInput(lineSheet, sport) : null}
        game={lineSheet ? slate.games.find((g) => g.game_id === lineSheet.gameId) ?? null : null}
        onClose={() => setLineSheet(null)}
        onAdded={onAdded}
      />
    </>
  );
}

function TeamRow({
  rank,
  row,
  def,
  cuts,
  quote,
  started,
  showLine,
  onLinePress,
}: {
  rank: number;
  row: TeamStatsRow;
  def: TeamStatDef;
  cuts: { lo: number; hi: number } | null;
  quote: TeamLineQuote | null;
  started: 'Live' | 'Final' | null;
  showLine: boolean;
  onLinePress?: () => void;
}) {
  const value = teamStatValue(row, def);
  const thin = isThinSample(row, def);
  // A thin split still shows its number, but is never tinted as if it ranked.
  const tier: Tier = thin ? 'none' : tierFor(value, cuts, def.better);
  const color = tierColor(tier);
  const record = formatRecord(row, def);
  const sample = def.sample ? sampleFor(row, def) : null;

  return (
    <View style={styles.row}>
      <Text style={styles.rank}>{rank}</Text>
      <View style={styles.rowMain}>
        <Text style={styles.rowName} numberOfLines={1}>
          {row.team}
          {row.conference ? <Text style={styles.rowSub}>  {row.conference}</Text> : null}
        </Text>
        <Text style={styles.rowMeta} numberOfLines={1}>
          {row.wins}-{row.losses}
          {row.point_diff_pg != null
            ? `  ·  ${row.point_diff_pg > 0 ? '+' : ''}${Number(row.point_diff_pg).toFixed(1)}/g`
            : ''}
          {thin ? `  ·  ${sample} game${sample === 1 ? '' : 's'}` : ''}
        </Text>
      </View>
      <View style={styles.valueWrap}>
        <Text style={[styles.value, color ? { color } : null]}>
          {formatTeamStat(value, def.format)}
        </Text>
        {record ? (
          <Text style={styles.valueLabel}>{record}</Text>
        ) : thin ? (
          <Text style={styles.thinLabel}>thin</Text>
        ) : null}
      </View>
      {showLine ? <TeamLineCell quote={quote} team={row.team} started={started} onPress={onLinePress} /> : null}
    </View>
  );
}

/** The user's sportsbook's number for this team's game, from its side, or a
 *  dash. Same filled, book-branded pill as the Players board, and the same
 *  ask-to-add-to-betslip tap (Matt, 2026-09-05). The caption stays here —
 *  unlike the Players board, the market genuinely varies row to row only by
 *  which stat is selected, and "ML" / "−1.5" / "o8.5" is what names it. */
function TeamLineCell({
  quote,
  team,
  started,
  onPress,
}: {
  quote: TeamLineQuote | null;
  team: string;
  /** The team's game is live or over: no line, and the cell says which. */
  started?: 'Live' | 'Final' | null;
  onPress?: () => void;
}) {
  if (quote == null) {
    if (started) {
      return (
        <View style={styles.lineWrap} accessible accessibilityLabel={`${team}, game ${started.toLowerCase()}`}>
          <Text style={styles.lineStarted}>{started}</Text>
        </View>
      );
    }
    return (
      <View style={styles.lineWrap} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Text style={styles.lineEmpty}>—</Text>
      </View>
    );
  }
  const c = bookButtonColors(quote.book);
  const filled = quote.book === MODEL_BOOK;
  const caption = teamLineCaption(quote);
  const what =
    quote.market === 'h2h'
      ? 'moneyline'
      : quote.market === 'spreads'
        ? `spread ${caption}`
        : `total over ${quote.line}`; // spoken: the side, not the sighted "o8.5"
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}
      accessibilityRole="button"
      accessibilityLabel={`${team} ${what}, ${formatAmerican(quote.price)} at ${bookName(quote.book)}`}
      accessibilityHint="Asks to add this line to your betslip"
      style={({ pressed }) => [styles.lineWrap, pressed && styles.pressed]}
    >
      <View
        style={[
          styles.linePill,
          filled ? { backgroundColor: c.bg } : styles.linePillOutlined,
        ]}
      >
        <Text
          style={[styles.lineText, { color: filled ? c.fg : colors.textPrimary }]}
          numberOfLines={1}
        >
          {formatAmerican(quote.price)}
        </Text>
        <BookMark book={quote.book} size={12} color={filled ? c.fg : colors.textPrimary} />
        {/* No arrow-out glyph: the pill no longer leaves the app. It asks,
            like the Players pill, and carries what that one carries. */}
      </View>
      {caption ? <Text style={styles.lineCaption}>{caption}</Text> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fixedRow: { flexGrow: 0, flexShrink: 0 },
  listFlex: { flex: 1 },
  list: { paddingBottom: spacing.xl },
  chipRow: { paddingHorizontal: spacing.lg, gap: spacing.sm, paddingVertical: 2 },
  hintRow: { paddingHorizontal: spacing.lg, paddingTop: spacing.xs, paddingBottom: 2 },
  hintText: { fontSize: 11, color: colors.textTertiary, lineHeight: 15 },
  searchWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
    gap: spacing.sm,
  },
  searchInput: { flex: 1, fontSize: font.size.body, color: colors.textPrimary, paddingVertical: 2 },
  colHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: 6,
    gap: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  colHeaderRank: {
    width: 20,
    fontSize: 11,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  colHeaderName: {
    flex: 1,
    fontSize: 11,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  colHeaderRight: {
    width: 72,
    textAlign: 'right',
    fontSize: 11,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    paddingVertical: 5,
    gap: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  rowMain: { flex: 1, minWidth: 0 },
  rank: {
    width: 20,
    textAlign: 'center',
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textTertiary,
  },
  rowName: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  rowSub: { fontSize: 11, fontWeight: font.weight.semibold, color: colors.textTertiary },
  rowMeta: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  valueWrap: { alignItems: 'flex-end', width: 72 },
  colHeaderLine: { minWidth: 66, textAlign: 'right' },
  lineWrap: { minWidth: 66, alignItems: 'flex-end' },
  // Filled in the book's own colour — the pill IS the bet button.
  linePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 5,
    minHeight: 26,
    borderRadius: radii.sm,
  },
  linePillOutlined: {
    backgroundColor: colors.noneSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
  },
  lineText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    fontVariant: ['tabular-nums'],
  },
  lineCaption: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: 1 },
  lineEmpty: { fontSize: font.size.footnote, color: colors.textTertiary },
  lineStarted: { fontSize: font.size.caption, fontWeight: font.weight.semibold, color: colors.textTertiary, textAlign: 'center' },
  noLinesRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 5,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  noLinesText: {
    flex: 1,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: font.size.caption * 1.35,
  },
  noLinesLink: { color: colors.tint, fontWeight: font.weight.semibold },
  value: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  valueLabel: { fontSize: 10, color: colors.textTertiary },
  thinLabel: { fontSize: 10, color: colors.textTertiary, fontStyle: 'italic' },
  pressed: { opacity: 0.65 },
  loading: { marginVertical: spacing.xxl },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    borderRadius: 8,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },
});

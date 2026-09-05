import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { CompositeNavigationProp, RouteProp } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { SportsbookIndicator } from '@/components/SportsbookIndicator';
import { AddLineSheet } from '@/components/AddLineSheet';
import { HitModeSheet } from '@/components/HitModeSheet';
import { propLineSheetInput } from '@/lib/lineLegs';
import type { StatsOddsSide } from '@/lib/statsOdds';
import { SportsbookPickerSheet } from '@/components/SportsbookPickerSheet';
import { BookMark } from '@/components/BookMark';
import { GroupTabs, SegmentTabs } from '@/components/GroupTabs';
import { InfoTooltip } from '@/components/InfoTooltip';
import { showToast } from '@/components/Toast';
import { SportToggle } from '@/components/SportToggle';
import { TeamsBoard } from '@/components/TeamsBoard';
import { SettingsButton } from '@/components/SettingsButton';
import { FilterChip } from '@/components/filters/FilterChip';
import { FilterField } from '@/components/filters/FilterField';
import { FilterSection, FilterSheet } from '@/components/filters/FilterSheet';
import type { ActivePill } from '@/components/filters/FilterBar';
import { useNow } from '@/hooks/useNow';
import { useSportFilter, type Sport } from '@/hooks/useSportFilter';
import { usePreferredBooks, BOOKS } from '@/hooks/usePreferredBooks';
import {
  fetchPropLinesForDate,
  fetchRecentGames,
  fetchSeasonStatValues,
  fetchSlateGames,
  fetchTonightMatchups,
  fetchWindowTotals,
} from '@/lib/queries';
import { bookLabel, bookName, booksLabel, booksName, booksNoneName, MODEL_BOOK, oneWayMarket, propDisplayLabel } from '@/lib/markets';
import { bookButtonColors } from '@/lib/sportsbookLinks';
import {
  ambiguousKeys,
  anyBookPostsSide,
  bookCoverageForMarket,
  bookPostsMarket,
  buildQuoteIndex,
  quoteForRow,
  unstartedGameIds,
  type BookSideCoverage,
  type StatsOddsQuote,
} from '@/lib/statsOdds';
import { computeHitRate, hitRateBandOf, hitRateColorDiscriminates } from '@/lib/hitRate';
import { hitModeHeadline, hitModeLabel, hitModeLineLabel, selectionFor, thresholdLabel, type HitMode } from '@/lib/hitMode';
import { supportsPlayerDetail } from '@/lib/playerLog';
import { buildMatchupMap, gradeMatchup, gradeSpoken, type MatchupInfo } from '@/lib/matchup';
import { addDays, formatAmerican, todayET, weekdayET, gameStatus } from '@/lib/format';
import {
  EMPTY_SLATE,
  HIT_RATE_PRESETS,
  buildSlateGameIndex,
  buildTonightSlate,
  compareRows,
  hitRateBand,
  inHitRateBand,
  isOnSlate,
  isStatParticipant,
  slateGameFor,
  slateSubline,
  sublineSpoken,
  sortLabel,
  sortOptionsFor,
  type SortKey,
  type TonightSlate,
} from '@/lib/statsBoard';
import {
  GROUP_ORDER,
  defaultStatFor,
  defaultThresholdFor,
  propMarketForStat,
  sportHasAnyPropMarket,
  statValue,
  statsForSport,
  supportsHitRate,
  type StatDef,
} from '@/lib/statCatalog';
import { supportsTeamBoard } from '@/lib/teamStatCatalog';
import { colors, font, gradeColor, radii, spacing } from '@/lib/theme';
import { errorText } from '@/lib/errors';
import type {
  EnrichedPick,
  GameRow,
  PropOddsByBookRow,
  HitRatePlayer,
  RecentGameRow,
  SeasonStatValuesRow,
  SeasonTotalsRow,
  TonightMatchupRow,
  RootStackParamList,
  TabParamList,
} from '@/types';

type Nav = CompositeNavigationProp<
  BottomTabNavigationProp<TabParamList, 'Stats'>,
  NativeStackNavigationProp<RootStackParamList>
>;
type StatsRoute = RouteProp<TabParamList, 'Stats'>;
type Basis = 'total' | 'perGame';
/** Which half of the Stats tab is showing. */
type BoardMode = 'players' | 'teams';
const BOARD_MODES: BoardMode[] = ['players', 'teams'];
type Mode = 'totals' | 'hitRate';
const MODES: Mode[] = ['hitRate', 'totals'];
// Last-N-games window. 'season' = whole season (null window on the totals RPC;
// the player_season_stat_values_* RPCs in Hit Rate mode).
type TimeWindow = 3 | 5 | 10 | 15 | 20 | 'season';

// The LINE pill on a row is the user's own sportsbook's current number for the
// line the board is showing — lib/statsOdds. Separate from the models by
// design (Matt, 2026-09-03). Tapping it opens the sheet with that book's price
// and its "Bet on …" button.

const SEASON = new Date().getUTCFullYear();
/**
 * The two right-hand column widths, shared by the header cell and the row cell
 * so the header rail cannot drift off its column — content-sized rows under a
 * fixed header meant one long pitcher name shifted that row's price out from
 * under its own "DK".
 *
 * Each cell is min/max/shrink rather than a single fixed width, which is the
 * only shape that survives both failure modes:
 *
 *   - `flexShrink: 1` because the row's only other flexible child is the
 *     player's NAME. With the default flexShrink of 0 these two grew at Dynamic
 *     Type sizes and the name paid for all of it, reaching zero around
 *     fontScale 2. The detail ellipsizing is the right thing to lose first.
 *   - `maxWidth` because content-sized cells under a fixed header shifted one
 *     row's price out from under its own "DK" whenever a pitcher's name ran
 *     long. Bounded growth bounds the drift.
 *   - and NOT a hard width, which was the first attempt: it pins the header
 *     perfectly and then clips the PRICE at about fontScale 1.3, which is the
 *     one number on the row a user came for.
 */
// The GRADE column holds two characters now, not a stacked opponent + fact
// (2026-09-05), so it gives ~24pt back to the player name — which is exactly
// where the new subline needs it.
//
// The header word is GRADE, not MATCHUP: "MATCHUP" at 11pt semibold needs
// ~56-58pt and truncated to "MATCHU…" inside a 52pt box (UX review). It is
// also the more honest label — the cell IS a grade, and the subline above
// already says who the opponent is, so "MATCHUP" promises a fixture the column
// no longer prints.
//
// 64, not 52, because the header carries the LEGEND: "B+" explains nothing on
// its own — not which end is good, not what it is graded against, not why some
// rows are a dash — where the two-line cell it replaces explained itself by
// printing "S. Gray 5.90 ERA". Still 12pt narrower than the old SPOT column.
const MATCHUP_W = 64;
const ODDS_W = 62;

const TIME_WINDOWS: { value: TimeWindow; label: string }[] = [
  { value: 3, label: 'L3' },
  { value: 5, label: 'L5' },
  { value: 10, label: 'L10' },
  { value: 15, label: 'L15' },
  { value: 20, label: 'L20' },
  { value: 'season', label: 'Season' },
];

/** '2026-08-30' → 'Sun 8/30' (for the next-slate chip). */
function shortDate(date: string): string {
  if (!date) return '';
  const d = new Date(`${date}T12:00:00Z`);
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC',
    weekday: 'short',
    month: 'numeric',
    day: 'numeric',
  }).format(d);
}

/**
 * The board's PRIMARY number, on the same ramp as the matchup grade.
 *
 * It was `colors.bet` / `#FF9500` / `colors.avoid` — 2.22:1, 2.20:1 and
 * 3.55:1 on the card, all three below the AA floor for 13pt bold text. That
 * predates this change, but adding an accessible ramp two columns to the right
 * left the board running two contrast standards side by side with the
 * accessible one on the SECONDARY column (UX review, 2026-09-05), so they are
 * now one ramp.
 *
 * `colorful === false` means every row on screen sits in the same band, so the
 * ramp would be a verdict on the bet rather than a comparison between players
 * — see `hitRateColorDiscriminates`. Accessible or not, a colour that says the
 * same thing about every row says nothing about any of them.
 */
function hitRateColor(pct: number, colorful: boolean): string {
  if (!colorful) return colors.textPrimary;
  const b = hitRateBandOf(pct);
  return b === 'high' ? colors.gradeGood : b === 'mid' ? colors.gradeMid : colors.gradeBad;
}

/**
 * The integer threshold shown on the ruler for a stat, e.g. "1+ Hits",
 * "6+ Strikeouts". Stat defaults are half-lines (0.5 / 5.5) so the ceiling is
 * the first whole number that clears them.
 */
/**
 * Does this sport's board start filtered to the slate?
 *
 * Football does. Its leaderboard is national — 136 college programs — while
 * props are pulled only for games a book already prices (~70 of a 120-game
 * Saturday), so an unfiltered board is mostly dashes: every one of them
 * honest, none of them explained. Baseball's slate is nearly the whole league
 * every day, so the filter would only hide players.
 *
 * Stated once because the initial value and the sport-change reset have to
 * agree, and they did not when this was written inline (UX review,
 * 2026-09-05).
 */
function defaultTonightOnly(sport: Sport): boolean {
  return sport === 'NCAAF' || sport === 'NFL';
}

function defaultLineN(def: StatDef | null): number {
  return Math.max(1, Math.ceil(defaultThresholdFor(def)));
}

/** Upper bound of the ruler — generous enough to cover league leaders. */
function maxLineN(def: StatDef | null): number {
  return Math.max(10, defaultLineN(def) * 3);
}

export function StatsScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<StatsRoute>();
  const { sport } = useSportFilter();
  // Today's board — hangs a live price off each leaderboard row, and backs the
  // player odds sheet (all-books prices + add-to-betslip) behind the odds pill.
  // The user's sportsbooks: the column prints the best of THOSE books and
  // nothing else. `ready` gates the odds column, not just a label: a tap adds
  // the pill's line to the betslip (AddLineSheet below), so a tap in the
  // seeded-default frame would add DraftKings' number for a FanDuel member.
  const { books, ready: booksReady } = usePreferredBooks();
  // Every clock-derived cell on this board reads THIS value, so the start
  // time, the Live/Final label and the "is it still bettable" filter all age
  // together on one tick (useNow).
  const now = useNow();
  // The user came from the betslip to find a leg — banner + auto-return.
  const fromParlay = route.params?.fromParlay === true;
  // The "hasn't posted lines" note is the switch — an instruction sits with
  // the control that performs it.
  const [pickerOpen, setPickerOpen] = useState(false);

  const [stat, setStat] = useState<StatDef | null>(() => defaultStatFor(sport));
  const [mode, setMode] = useState<Mode>('hitRate');
  const [basis, setBasis] = useState<Basis>('perGame');
  const [timeWindow, setTimeWindow] = useState<TimeWindow>(10);
  const [query, setQuery] = useState<string>('');
  const [teamFilter, setTeamFilter] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('default');
  // Hit Rate controls (front page): a whole-number ruler, plus which side of
  // it the bet is on. The ruler starts at 1 for every mode: "at least 0" is
  // every game, and "under 0" is fewer than none, which no game can be and no
  // book prices (lib/hitMode.ts).
  const [lineN, setLineN] = useState<number>(() => defaultLineN(defaultStatFor(sport)));
  const [hitMode, setHitMode] = useState<HitMode>('atLeast');
  const [modeOpen, setModeOpen] = useState<boolean>(false);
  const [minHitRate, setMinHitRate] = useState<string>('');
  const [maxHitRate, setMaxHitRate] = useState<string>('');

  const [rows, setRows] = useState<SeasonTotalsRow[]>([]); // totals mode
  const [recentRows, setRecentRows] = useState<RecentGameRow[]>([]); // hit-rate mode, last-N
  // Hit-rate mode, Season window. The rows are ONE stat's value arrays, so they
  // carry the stat key they were fetched for — the memo below ignores them
  // when the user has already switched stats (prevents the old stat's numbers
  // rendering under the new stat's label while the refetch is in flight).
  const [seasonValues, setSeasonValues] = useState<{ statKey: string; rows: SeasonStatValuesRow[] }>(
    { statKey: '', rows: [] },
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState<boolean>(false);
  // The SPOT column: team → matchup (opponent + strength). MLB/WNBA only —
  // the other sports have no matchup view, and get no SPOT column.
  const [matchups, setMatchups] = useState<TonightMatchupRow[]>([]);
  // "Playing tonight": who is actually in action. Read from `games`, so unlike
  // the matchup views above this works for every sport.
  const [tonightOnly, setTonightOnly] = useState<boolean>(() => defaultTonightOnly(sport));
  const [slate, setSlate] = useState<TonightSlate>(EMPTY_SLATE);
  // The slate's raw games. The prop-odds view has no sport column and
  // `player_points` is both an NBA and a WNBA market, so the odds read is
  // bounded to these game ids rather than to a date alone.
  const [slateGames, setSlateGames] = useState<GameRow[]>([]);
  // Every book's latest line for the selected stat's market on the slate date.
  const [propLines, setPropLines] = useState<{
    market: string;
    rows: PropOddsByBookRow[];
    /** A failed read renders exactly the em-dash this column exists to remove,
     *  so the two must not look the same (UX_REVIEW §3). 'loading' keeps the
     *  column mounted; 'failed' says so once, out loud. */
    status: 'loading' | 'ok' | 'failed';
  }>({ market: '', rows: [], status: 'ok' });
  // Players | Teams. Teams is a separate board with its own stats and data.
  const [boardMode, setBoardMode] = useState<BoardMode>('players');

  // Hit Rate only exists for sports with per-game player logs (MLB/WNBA/NBA).
  const canHitRate = supportsHitRate(sport);
  const effectiveMode: Mode = canHitRate ? mode : 'totals';

  // Reset to the sport's default stat + clear filters whenever the sport changes.
  useEffect(() => {
    const next = defaultStatFor(sport);
    setStat(next);
    setQuery('');
    setTeamFilter(null);
    setTonightOnly(defaultTonightOnly(sport)); // a different sport is a different slate
    setLineN(defaultLineN(next));
    // UFC and golf have no teams — never strand the user on an empty board.
    if (!supportsTeamBoard(sport)) setBoardMode('players');
  }, [sport]);

  // Load tonight's matchups (MLB/WNBA; others resolve to []). Failure-tolerant —
  // the leaderboard must never break because the matchup view is unreachable.
  useEffect(() => {
    let cancelled = false;
    fetchTonightMatchups(sport)
      .then((m) => {
        if (!cancelled) setMatchups(m);
      })
      .catch(() => {
        if (!cancelled) setMatchups([]);
      });
    return () => {
      cancelled = true;
    };
  }, [sport]);

  // Tonight's slate (all sports). Looks a week ahead so sports that don't play
  // daily still get a usable toggle — buildTonightSlate prefers today and falls
  // back to the next scheduled day. Failure-tolerant: a slate we can't reach
  // just leaves the toggle hidden.
  useEffect(() => {
    let cancelled = false;
    const from = todayET();
    fetchSlateGames(sport, from, addDays(from, 7))
      .then((games: GameRow[]) => {
        if (cancelled) return;
        setSlate(buildTonightSlate(games, sport, from));
        setSlateGames(games.filter((g) => g.sport === sport));
      })
      .catch(() => {
        if (cancelled) return;
        setSlate(EMPTY_SLATE);
        setSlateGames([]);
      });
    return () => {
      cancelled = true;
    };
  }, [sport]);

  const matchupByTeam = useMemo(() => buildMatchupMap(matchups), [matchups]);
  // Only filter when there is actually a slate — a stale toggle on an off day
  // (or after switching sports) must not empty the list.
  const hasSlate = slate.keys.size > 0;
  const tonightActive = tonightOnly && hasSlate;
  const slateLabel = slate.isToday ? 'Playing today' : `Next slate ${shortDate(slate.date)}`;

  const playerType = stat?.playerType;

  // Season hit rates are fetched per stat (the RPC returns one stat's value
  // arrays), so the load must refetch when the stat changes — but ONLY in that
  // mode. Keying the dependency on this derived value keeps stat switching in
  // every other mode client-side (no refetch), as before.
  const seasonStatKey =
    effectiveMode === 'hitRate' && timeWindow === 'season' ? String(stat?.key) : null;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (!stat) {
        setRows([]);
        setRecentRows([]);
        setSeasonValues({ statKey: '', rows: [] });
        return;
      }
      if (effectiveMode === 'hitRate') {
        if (timeWindow === 'season') {
          const key = String(stat.key);
          const data = await fetchSeasonStatValues(sport, SEASON, key, playerType);
          setSeasonValues({ statKey: key, rows: data });
        } else {
          const data = await fetchRecentGames(sport, SEASON, timeWindow, playerType);
          setRecentRows(data);
        }
      } else {
        const win = timeWindow === 'season' ? null : timeWindow;
        const data = await fetchWindowTotals(sport, SEASON, win, playerType);
        setRows(data);
      }
    } catch (e: unknown) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [sport, playerType, timeWindow, effectiveMode, seasonStatKey]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleBasis = (next: Basis) => setBasis(next);

  // Each stat carries its own sensible line — snap the ruler back on switch.
  const pickStat = (s: StatDef) => {
    setStat(s);
    setLineN(defaultLineN(s));
  };

  // The bet the board is about: a half-point line and a side. Everything
  // downstream — the hit rate, the odds cell, the betslip leg — reads these
  // two and never the mode (lib/hitMode.ts).
  const { line, side } = useMemo(() => selectionFor(lineN, hitMode), [lineN, hitMode]);

  // ── The LINE column ────────────────────────────────────────────────────────
  // The user's sportsbook's current line for the number the RULER is on, for
  // every player it prices. Matt, 2026-09-03: "display all lines regardless of
  // bet status … if they select FanDuel we only show FanDuel". So there is no
  // pick precedence and no DraftKings fallback — the pill is the chosen book's
  // number or a dash, and when the book posts nothing for the stat the board
  // says so instead of showing a column of dashes. See lib/statsOdds.ts.
  //
  // TAPPING A PILL OPENS THE BOOK (Matt, 2026-09-04: "mirror exactly how they
  // show the draft kings line and its betable link directly to that
  // sportsbook"). There is no in-app sheet in between — the pill is the bet
  // link. Adding a leg to our own betslip lives one tap deeper, on the
  // player's detail screen, which is where a researcher lands anyway.
  //
  // The MARKET, not the model: a retired model's stat keeps its LINE column
  // (Matt, 2026-09-03: "works separately from the models"), and football
  // resolves here without a model at all, having none. This screen no longer
  // reads a model for anything — the betslip button lives one tap deeper, on
  // the player's detail screen, which is where a researcher lands anyway.
  const propMarket = propMarketForStat(stat);

  // Prop lines for the slate date. Bounded to one market, and re-read when the
  // user switches stat — a full MLB market is ~190 players x 13 books.
  const oddsDate = slate.date || todayET();
  useEffect(() => {
    let cancelled = false;
    if (!propMarket) {
      setPropLines({ market: '', rows: [], status: 'ok' });
      return;
    }
    setPropLines((prev) => ({ ...prev, status: 'loading' }));
    fetchPropLinesForDate(oddsDate, propMarket)
      .then((rows) => {
        if (!cancelled) setPropLines({ market: propMarket, rows, status: 'ok' });
      })
      // Enrichment only — the leaderboard must never break because the odds
      // view is unreachable. But it must not fail SILENTLY: an unreachable view
      // and "this book posts nothing" both look like an empty column.
      .catch((e: unknown) => {
        if (cancelled) return;
        setPropLines({ market: propMarket, rows: [], status: 'failed' });
        showToast(`Couldn’t load today’s lines — ${errorText(e)}`);
      });
    return () => {
      cancelled = true;
    };
  }, [propMarket, oddsDate]);

  // The slate's games that have NOT started. A game in progress has no line a
  // user can still take, and its "latest" pre-game row is a live number.
  const slateGameIds = useMemo(
    () =>
      unstartedGameIds(
        slateGames.filter((g) => g.game_date === oddsDate),
        new Date(now).toISOString(),
      ),
    [slateGames, oddsDate, now],
  );

  // Teams whose game is in progress or over. Their lines are hidden by design
  // (no line a user can still take), and the cell says WHICH — "Live" or
  // "Final", the words GameStatusPill uses — instead of printing a dash that
  // reads as "no line": at 6:45pm on 2026-09-04 the 6:11 game's players had
  // all gone blank while every other row was priced. A team with a game still
  // to come (a doubleheader) gets no label: that game's line can still show.
  const startedTeams = useMemo(() => {
    const out = new Map<string, 'Live' | 'Final'>();
    const pending = new Set<string>();
    for (const g of slateGames) {
      if (g.game_date !== oddsDate) continue;
      const teams = [g.home_team, g.away_team].filter(Boolean) as string[];
      if (slateGameIds.has(g.game_id)) {
        teams.forEach((t) => pending.add(t));
        continue;
      }
      // `now` is not read here, but gameStatus reads the clock internally —
      // the dependency below is what makes this re-derive on the tick.
      const kind = gameStatus(g).kind;
      const label = kind === 'live' ? 'Live' : kind === 'final' || kind === 'ended' ? 'Final' : null;
      if (label) teams.forEach((t) => out.set(t, label));
    }
    pending.forEach((t) => out.delete(t));
    return out;
  }, [slateGames, oddsDate, slateGameIds, now]);

  const quoteByPlayerKey = useMemo(() => {
    if (!propMarket || propLines.market !== propMarket) return new Map<string, StatsOddsQuote>();
    return buildQuoteIndex(propLines.rows, {
      market: propMarket,
      line,
      side,
      books,
      gameIds: slateGameIds,
    });
  }, [propLines, propMarket, line, side, books, slateGameIds]);

  // Leaderboard names that two players share once folded. Neither gets a quote:
  // a wrong price on the wrong player is worse than a dash (data/name_match.py).
  const ambiguousLeaderboardKeys = useMemo(() => {
    const names = effectiveMode === 'hitRate'
      ? (timeWindow === 'season' ? seasonValues.rows : recentRows).map((r) => r.player_name)
      : rows.map((r) => r.player_name);
    return ambiguousKeys(names);
  }, [rows, recentRows, seasonValues, effectiveMode, timeWindow]);

  const quoteFor = useCallback(
    (row: { player_name?: string | null }): StatsOddsQuote | null =>
      quoteForRow(row, quoteByPlayerKey, ambiguousLeaderboardKeys),
    [quoteByPlayerKey, ambiguousLeaderboardKeys],
  );

  // Do any of the member's books post this market at all today? Gated on the
  // DAY and the BOOKS — never on the ruler position, which would collapse the
  // column and re-flow the board under the thumb.
  const bookPosts =
    propMarket != null &&
    propLines.market === propMarket &&
    slateGameIds.size > 0 &&
    bookPostsMarket(propLines.rows, propMarket, books, slateGameIds, side);
  const showOdds = bookPosts && booksReady;

  // The slate is not always today: buildTonightSlate falls back to the next
  // scheduled day, so for a weekly sport this reads SATURDAY from Sunday
  // onward. Declared here because both the picker's coverage note and the
  // empty-column note below date themselves by it.
  const slateDayLabel = slate.isToday || !slate.date ? 'today’s' : `${weekdayET(slate.date)}’s`;

  // ── What each of the member's books actually prices for THIS stat ─────────
  // Computed from the rows already on screen, so it costs nothing: a
  // slate-wide coverage read against the odds view measured 8-17s on
  // 2026-09-05 and is not something a screen can afford.
  // TWO MAPS, over two different book sets, and the difference is load-bearing.
  // `coverage` is the member's OWN books and drives the direction control.
  // `coverageAll` is every book the picker lists, because the picker shows the
  // ones they have NOT selected too — computing the note off the selected set
  // would print "No Hits lines today" under every unselected book, which is
  // the exact false impression this whole change exists to remove.
  const coverage = useMemo(
    () =>
      propMarket != null && propLines.market === propMarket
        ? bookCoverageForMarket(propLines.rows, propMarket, books, slateGameIds)
        : new Map<string, BookSideCoverage>(),
    [propLines, propMarket, books, slateGameIds],
  );
  const coverageAll = useMemo(
    () =>
      propMarket != null && propLines.market === propMarket
        ? bookCoverageForMarket(propLines.rows, propMarket, BOOKS, slateGameIds)
        : new Map<string, BookSideCoverage>(),
    [propLines, propMarket, slateGameIds],
  );

  // The picker's per-book sub-line. It EXPLAINS, it never restricts (Matt,
  // 2026-09-05: "if we are getting betting lines for a Sportsbook we should
  // show it as an option and display those lines"). He read FanDuel's and
  // Caesars' blank columns as us not carrying those books; we do — they post
  // Hits through the milestone market, which is over-only, so the honest
  // answer is a sentence on the row rather than a book removed from the list.
  const coverageReady =
    propMarket != null && propLines.market === propMarket && propLines.status === 'ok';
  const coverageNote = useCallback(
    (book: string): string | null => {
      if (!coverageReady || slateGameIds.size === 0) return null;
      const statLabel = stat?.label ?? '';
      // EVERY row gets one, including the fully-covered case. A slot used
      // only for the bad news makes a covered book look like a book nobody
      // checked (UX review); when every row carries a sub-line, the thin ones
      // read as a variation rather than as the only rows with information.
      const when = slateDayLabel === 'today’s' ? 'today' : `on ${weekdayET(slate.date)}`;
      const c = coverageAll.get(book);
      if (!c) return `No ${statLabel} lines ${when}`;
      if (c.over && !c.under) return `At Least only for ${statLabel} ${when}`;
      if (c.under && !c.over) return `At Most only for ${statLabel} ${when}`;
      return `Both sides for ${statLabel} ${when}`;
    },
    [coverageAll, coverageReady, slateGameIds, stat, slateDayLabel, slate.date],
  );

  // ── The Over/Under control ────────────────────────────────────────────────
  // Matt, 2026-09-05, on FanDuel's near-empty At-Most column: hide the side
  // none of their books sells rather than answer it with a column of dashes.
  // FanDuel carried an Under price on 2 of the 12 MLB stats that day and
  // Caesars on 3, because the milestone market the feed gives us for them is
  // over-only.
  //
  // FAIL OPEN. While the lines are loading, when the read failed, when the
  // slate has no unstarted game left, and on a stat no book prices at all
  // (football's solo tackles, and every sport with no prop market), BOTH sides
  // stay live: the board's hit rate is real research on its own and must never
  // lose a control to a slow query.
  const sideKnown = coverageReady && slateGameIds.size > 0 && coverage.size > 0;
  const underAvailable = !sideKnown || anyBookPostsSide(coverage, 'under');
  const overAvailable = !sideKnown || anyBookPostsSide(coverage, 'over');
  // Only one side left: snap to it rather than leaving the member parked on a
  // view their books cannot price with the control to leave it greyed out.
  //
  // THE MEMBER'S CHOICE OUTLIVES THE SNAP. `requestedMode` is what they
  // last asked for, and it is restored the moment their books price it again
  // — otherwise switching to a stat FanDuel prices one-sided would silently
  // eat an At-Most they set deliberately, and switching back would not give
  // it back (UX review). The snap is announced too: the prop read is async, so
  // without a toast the hit-rate column, the headline and the row order all
  // change under the thumb with nothing saying why.
  const requestedMode = useRef<HitMode>('atLeast');
  const snapAnnounced = useRef<string | null>(null);
  const chooseMode = useCallback((m: HitMode) => {
    requestedMode.current = m;
    setHitMode(m);
  }, []);
  // Which side each mode bets. It does not depend on the ruler: At Least and
  // Over both take the over, Under takes the under — which is why a book that
  // posts only one side no longer LOCKS this control the way it did when
  // there were two modes. Two of the three survive an over-only book, and the
  // sheet marks the one that does not.
  const sideOfMode = useCallback((m: HitMode) => selectionFor(1, m).side, []);
  const modeAvailable = useCallback(
    (m: HitMode) => (sideOfMode(m) === 'under' ? underAvailable : overAvailable),
    [sideOfMode, underAvailable, overAvailable],
  );
  useEffect(() => {
    // Only where the control exists. In Totals mode there is no pill and no
    // caption, so a snap there would be the silent rewrite this avoids; the
    // empty-column note already explains that case.
    if (effectiveMode !== 'hitRate') return;
    const wanted = requestedMode.current;
    if (modeAvailable(wanted)) {
      if (hitMode !== wanted) setHitMode(wanted);
      snapAnnounced.current = null;
      return;
    }
    // The nearest mode on the side the books DO price: At Least is the plain
    // reading of any over-side ask, and Under is the only under-side mode.
    const fallback: HitMode = sideOfMode(wanted) === 'under' ? 'atLeast' : 'under';
    if (!modeAvailable(fallback)) return;
    if (hitMode !== fallback) setHitMode(fallback);
    // Announced once per (stat, book set) — the effect re-runs on every rows
    // refresh, and a toast on each would be worse than the silence it fixes.
    const key = `${stat?.key ?? ''}|${books.join(',')}|${wanted}`;
    if (snapAnnounced.current === key) return;
    snapAnnounced.current = key;
    showToast(
      `No ${hitModeLabel(wanted)} ${stat?.label ?? ''} lines at ${booksName(books)} — showing ${hitModeLabel(fallback)}.`,
    );
  }, [effectiveMode, hitMode, modeAvailable, sideOfMode, stat, books]);
  // Naming the book is the whole point: a greyed control with no reason is the
  // "why is FanDuel blank" question in a smaller box.
  // POSITIVE sentence, so it takes booksName. booksNoneName is the subject of
  // a NEGATIVE one ("Neither DraftKings nor FanDuel has posted…") and would
  // invert the meaning here the moment a second book was selected.
  const dirLockNote =
    underAvailable && overAvailable
      ? null
      : `${booksName(books)} ${books.length === 1 ? 'posts' : 'post'} only ${
          underAvailable ? 'Under' : 'At Least and Over'
        } lines for ${stat?.label ?? 'this stat'} ${
          slateDayLabel === 'today’s' ? 'today' : `on ${weekdayET(slate.date)}`
        }.`;

  // ── The subline: "9:40 PM ET · @ SEA" under every row's name ───────────────
  // Matt, 2026-09-05, from a competitor screenshot. Keyed off `games` rather
  // than the MLB/WNBA matchup views so it lands in EVERY sport at once — the
  // football boards have no matchup feed at all and would otherwise be the two
  // that got nothing.
  const slateGameIndex = useMemo(
    () => buildSlateGameIndex(slateGames, slate, new Date(now).toISOString()),
    [slateGames, slate, now],
  );
  const sublineFor = useCallback(
    (row: { team?: string | null; player_name?: string | null }): string | null => {
      const match = slateGameFor(row, slateGameIndex);
      if (!match) return null;
      // Two rules, both learned the hard way (UX review, 2026-09-05):
      //   - the status is looked up by the key the row actually MATCHED on, not
      //     by `row.team` — a UFC row has no team, so keying on it left every
      //     fight advertising a start time hours after it ended;
      //   - and it is only handed to the subline when the price column is
      //     hidden, because that column prints the very same word.
      const started = showOdds ? null : startedTeams.get(match.key) ?? null;
      return slateSubline(match.game, started);
    },
    [slateGameIndex, startedTeams, showOdds],
  );

  // The column has nothing honest to show — say why, once, in words. Three
  // reasons look identical as an empty column and are not: NO BOOK PRICES THIS
  // STAT at all (nothing to wait for — six of the eighteen football columns,
  // solo tackles and passes defended among them), the chosen book has not
  // posted it (switch books), or no book has yet (wait).
  //
  // The slate is not always today: buildTonightSlate falls back to the next
  // scheduled day, so for a weekly sport this note is about SATURDAY from
  // Sunday onward. The column header already dates itself; the note used to
  // contradict it (UX review, 2026-09-05).
  //
  // ONE PLACE ON THIS SCREEN FOR BOOK-COVERAGE COPY (UX review). The lock's
  // reason is not a second caption under the ruler: it joins the note that
  // already owns this — same info icon, same row, same "Change your
  // sportsbooks ›" tail, which is the one action that lifts the lock. It sits
  // LAST because it is the mildest of these states: the column is priced, just
  // on one side only.
  const noLinesNote: { text: string; canSwitch: boolean } | null =
    propMarket == null
      ? stat != null && sportHasAnyPropMarket(sport)
        ? { text: `No sportsbook posts ${stat.label} lines.`, canSwitch: false }
        : null
      : propLines.status !== 'ok' || slateGameIds.size === 0
        ? null
        : propLines.rows.length === 0
          ? { text: `${stat?.label ?? ''} lines post once books price ${slateDayLabel} games.`, canSwitch: false }
          : !bookPosts
            ? {
                text: oneWayMarket(propMarket, side)
                  ? `${booksNoneName(books)} only posts the Yes side of ${propDisplayLabel(propMarket, stat?.label ?? '')}.`
                  : `${booksNoneName(books)} ${books.length === 1 ? 'hasn’t' : 'has'} posted ${stat?.label ?? ''} lines ${slateDayLabel === 'today’s' ? 'today' : `on ${weekdayET(slate.date)}`}.`,
                canSwitch: !oneWayMarket(propMarket, side),
              }
            : dirLockNote
              ? { text: dirLockNote, canSwitch: true }
              : null;

  // THE PILL ASKS. Matt, 2026-09-04, reversing the same morning's "the pill is
  // the bet link": "it shouldn't take you directly to the book, it should ask
  // you if you want to add to bet slip then bet slip should allow you to add
  // to any book." A tap opens AddLineSheet — the player, the line, every
  // book's price — and its one action puts the line in OUR betslip
  // (lib/lineLegs.ts); the betslip's Open-with row is where a book is chosen.
  const [lineSheet, setLineSheet] = useState<StatsOddsQuote | null>(null);
  const openBook = useCallback((quote: StatsOddsQuote) => {
    setLineSheet(quote);
  }, []);
  const lineSheetGame = useMemo(
    () => (lineSheet ? slateGames.find((g) => g.game_id === lineSheet.gameId) ?? null : null),
    [lineSheet, slateGames],
  );

  const band = useMemo(() => hitRateBand(minHitRate, maxHitRate), [minHitRate, maxHitRate]);

  // ── Averages / Totals mode ranking ──
  const ranked = useMemo(() => {
    if (!stat || effectiveMode !== 'totals') return [];
    const q = query.trim().toLowerCase();
    return rows
      .filter((r) => isStatParticipant(sport, [statValue(r, stat)]))
      .filter((r) => !teamFilter || r.team === teamFilter)
      .filter((r) => !tonightActive || isOnSlate(r, slate))
      .filter((r) => !q || (r.player_name ?? '').toLowerCase().includes(q))
      .map((r) => {
        const total = statValue(r, stat);
        const gp = r.games_played || 0;
        const value = basis === 'perGame' && gp > 0 ? total / gp : total;
        return { row: r, value, total, gp };
      })
      .sort((a, b) =>
        compareRows(
          { primary: a.value, games: a.gp, avg: a.gp > 0 ? a.total / a.gp : 0 },
          { primary: b.value, games: b.gp, avg: b.gp > 0 ? b.total / b.gp : 0 },
          sortKey,
        ),
      );
  }, [rows, stat, sport, basis, query, teamFilter, effectiveMode, tonightActive, slate, sortKey]);

  // ── Hit Rate mode: count games over/under the line per player. Last-N mode
  // groups the raw rows client-side; Season mode reads the per-player value
  // arrays from player_season_stat_values_* (values newest-first, nulls already
  // excluded server-side), so the line ruler stays instant either way. ──
  const hitRatePlayers = useMemo<HitRatePlayer[]>(() => {
    if (!stat || effectiveMode !== 'hitRate') return [];
    const out: HitRatePlayer[] = [];
    if (timeWindow === 'season') {
      if (seasonValues.statKey !== String(stat.key)) return []; // fetch in flight
      for (const r of seasonValues.rows) {
        const values = (r.values ?? []).map(Number);
        const { hits, total, pct } = computeHitRate(values, line, side);
        if (total === 0) continue;
        const avg = values.reduce((s, v) => s + v, 0) / total;
        out.push({
          player_id: r.player_id,
          player_name: r.player_name,
          team: r.team,
          player_type: r.player_type,
          games: [], // raw rows aren't fetched in Season mode
          values,
          hits,
          total,
          pct,
          avg,
        });
      }
    } else {
      const byPlayer = new Map<string, RecentGameRow[]>();
      for (const r of recentRows) {
        const arr = byPlayer.get(r.player_id);
        if (arr) arr.push(r);
        else byPlayer.set(r.player_id, [r]);
      }
      for (const [player_id, games] of byPlayer) {
        const values = games.map((g) => statValue(g, stat));
        const { hits, total, pct } = computeHitRate(values, line, side);
        if (total === 0) continue;
        const avg = values.reduce((s, v) => s + v, 0) / total;
        const head = games[0];
        out.push({
          player_id,
          player_name: head.player_name,
          team: head.team,
          player_type: head.player_type,
          games,
          values,
          hits,
          total,
          pct,
          avg,
        });
      }
    }
    const q = query.trim().toLowerCase();
    return out
      .filter((p) => isStatParticipant(sport, p.values))
      .filter((p) => inHitRateBand(p.pct, band))
      .filter((p) => !teamFilter || p.team === teamFilter)
      .filter((p) => !tonightActive || isOnSlate(p, slate))
      .filter((p) => !q || p.player_name.toLowerCase().includes(q))
      .sort((a, b) =>
        compareRows(
          { primary: a.pct, games: a.total, avg: a.avg },
          { primary: b.pct, games: b.total, avg: b.avg },
          sortKey,
        ),
      );
  }, [recentRows, seasonValues, timeWindow, stat, sport, line, side, band, query, teamFilter, effectiveMode, tonightActive, slate, sortKey]);

  // Does the hit-rate column span more than one colour band? A rare-event
  // column (Doubles, Triples, Home Runs) does not — every player lands in the
  // same band — and a whole column of one colour beside a live price reads as
  // a verdict on the bet rather than a ranking of players. Computed over what
  // is actually on screen, so the board never colours what it cannot
  // distinguish.
  const colorful = useMemo(
    () => hitRateColorDiscriminates(hitRatePlayers.map((p) => p.pct)),
    [hitRatePlayers],
  );

  // Teams present in the active dataset, for the team filter chips.
  const teams = useMemo(() => {
    const src: Array<{ team: string | null }> =
      effectiveMode === 'hitRate'
        ? timeWindow === 'season'
          ? seasonValues.rows
          : recentRows
        : rows;
    const set = new Set<string>();
    for (const r of src) if (r.team) set.add(r.team);
    return Array.from(set).sort();
  }, [rows, recentRows, seasonValues, effectiveMode, timeWindow]);

  // Every sport with a per-game player log gets the detail view; UFC/NHL/Golf
  // have no per-game player stats to chart.
  const playerDetail = supportsPlayerDetail(sport);

  /** The board's matchup for a team, as the two params the detail screen takes. */
  const matchupParams = (team?: string | null) => {
    const m = team ? matchupByTeam.get(team) : undefined;
    if (!m) return {};
    const graded = gradeMatchup(sport, playerType, m);
    return { matchupText: graded.text, matchupGrade: graded.grade ?? undefined };
  };

  const openPlayer = (p: {
    player_id: string;
    player_name: string;
    team?: string | null;
    player_type?: SeasonTotalsRow['player_type'];
  }) => {
    // Called directly rather than via `playerDetail` above: it is a type guard,
    // so this line is what narrows `sport` to a sport the route accepts.
    if (!supportsPlayerDetail(sport)) return;
    navigation.navigate('PlayerStats', {
      playerId: p.player_id,
      playerName: p.player_name,
      sport,
      // MLB only — it decides batter vs pitcher chips. Fall back to the selected
      // stat's player type so a row missing the column still opens the right side.
      playerType: sport === 'MLB' ? (p.player_type ?? playerType) : undefined,
      // The pill goes to the sportsbook now, so the leg is added one screen
      // deeper — carry the round-trip with us.
      fromParlay: fromParlay || undefined,
      // The matchup FACT rides along, because the board's column is now just
      // the grade (MatchupCell). Computed here rather than refetched there.
      ...matchupParams(p.team),
    });
  };

  const groups = GROUP_ORDER[sport];
  const windowN = typeof timeWindow === 'number' ? timeWindow : 10;
  // The headline under the ruler, e.g. "25+ Points" / "At most 2 Walks".
  const lineHeadline =
    hitModeHeadline(lineN, hitMode, stat?.label ?? '');
  // What a BET made from this column is called. Almost always the column's own
  // name; "Anytime TD" where the board asks Rush+Rec TDs, because no book
  // sells the column's version (markets.ts propDisplayLabel).
  const betLabel = propDisplayLabel(propMarket, stat?.label ?? '');

  // What the tapped pill hands the add-to-betslip sheet: the proposition,
  // every book's price for it, and the off-line explainer when the book's own
  // number differs from the board's (lib/lineLegs.ts).
  const lineSheetInput = useMemo(
    () => (lineSheet ? propLineSheetInput(lineSheet, sport, betLabel, lineHeadline) : null),
    [lineSheet, sport, betLabel, lineHeadline],
  );

  /**
   * One definition of "what the hit-rate band is set to", so the collapsed
   * sheet row and the removable pill can never describe it differently.
   */
  const bandSummary = useMemo(() => {
    const lo = Math.round(band.lo * 100);
    const hi = Math.round(band.hi * 100);
    if (band.lo > 0 && band.hi < 1) return `${lo}–${hi}%`;
    if (band.hi < 1) return `≤ ${hi}%`;
    if (band.lo > 0) return `${lo}%+`;
    return 'Any';
  }, [band]);

  // Count filters the user has changed away from defaults, for the trigger badge.
  // Only counts what still lives in the modal — the front-page controls are visible.
  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (teamFilter) n += 1;
    if (query.trim()) n += 1;
    if (sortKey !== 'default') n += 1;
    if (effectiveMode === 'hitRate') {
      if (band.lo > 0 || band.hi < 1) n += 1;
    } else if (basis !== 'perGame') {
      n += 1;
    }
    return n;
  }, [teamFilter, query, sortKey, effectiveMode, band, basis]);

  /**
   * Clears the filters that live in the sheet only. The front-page controls
   * (stat, line, window, Hit Rates/Averages) are deliberately left alone —
   * resetting the stat you're looking at from a "Filters" sheet reads as the
   * app losing your place, not as clearing a filter.
   */
  const resetFilters = useCallback(() => {
    setBasis('perGame');
    setQuery('');
    setTeamFilter(null);
    setMinHitRate('');
    setMaxHitRate('');
    setSortKey('default');
    setTonightOnly(false);
  }, []);

  // Removable chips for whatever is narrowing the board right now. Before this,
  // the only hint that a filter was on was a number badge on the Filters button.
  const activePills = useMemo<ActivePill[]>(() => {
    const out: ActivePill[] = [];
    if (teamFilter) {
      out.push({ key: 'team', label: teamFilter, onRemove: () => setTeamFilter(null) });
    }
    if (query.trim()) {
      out.push({ key: 'query', label: `"${query.trim()}"`, onRemove: () => setQuery('') });
    }
    if (tonightActive) {
      out.push({ key: 'tonight', label: slateLabel, onRemove: () => setTonightOnly(false) });
    }
    if (sortKey !== 'default') {
      out.push({
        key: 'sort',
        label: `by ${sortLabel(sortKey, effectiveMode).toLowerCase()}`,
        onRemove: () => setSortKey('default'),
      });
    }
    if (effectiveMode === 'hitRate') {
      if (band.lo > 0 || band.hi < 1) {
        out.push({
          key: 'hitBand',
          label: `hit ${bandSummary}`,
          onRemove: () => {
            setMinHitRate('');
            setMaxHitRate('');
          },
        });
      }
    } else if (basis !== 'perGame') {
      out.push({ key: 'basis', label: 'Totals', onRemove: () => setBasis('perGame') });
    }
    return out;
  }, [teamFilter, query, tonightActive, slateLabel, sortKey, effectiveMode, band, bandSummary, basis]);

  // What the empty board should SAY. An empty list and a failed fetch look
  // identical to a FlatList, and until 2026-09-01 both rendered "No MLB Hits
  // data for the last 5 games yet." — so a full outage (PostgREST was
  // answering 503) read to users as "this sport has no data", which is a
  // different problem with a different fix. The error case wins.
  const emptySubtitle = useMemo(() => {
    if (error) return 'The board could not be loaded. Tap Retry above.';
    if (query.trim()) return `Nothing matched "${query.trim()}".`;
    if (activeFilterCount > 0 || tonightActive) {
      return 'No players match your filters. Tap a pill above to widen the board.';
    }
    const window = timeWindow === 'season' ? 'this season' : `the last ${windowN} games`;
    return `No ${sport} ${stat?.label ?? ''} data for ${window} yet.`;
  }, [error, query, activeFilterCount, tonightActive, timeWindow, windowN, sport, stat]);

  // Teams board. Deliberately ahead of the !stat guard below: NHL and NCAAF
  // have no player leaderboard at all, and they are two of the sports where
  // team stats matter most — gating this behind `stat` would hide it there.
  if (boardMode === 'teams' && supportsTeamBoard(sport)) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <View style={styles.titleRow}>
            <Text style={styles.title}>Stats</Text>
            <SettingsButton />
          </View>
          <SportsbookIndicator coverageNote={coverageNote} />
          <SportToggle />
        </View>
        <BoardModeToggle mode={boardMode} onChange={setBoardMode} />
        <TeamsBoard sport={sport} onAdded={fromParlay ? () => navigation.navigate('Betslip') : undefined} />
      </SafeAreaView>
    );
  }

  // Sports with no per-player leaderboard (NHL: team+goalie only; Golf: v1).
  if (!stat) {
    const isGolf = sport === 'GOLF';
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <View style={styles.titleRow}>
            <Text style={styles.title}>Stats</Text>
            <SettingsButton />
          </View>
          <SportToggle />
        </View>
        {supportsTeamBoard(sport) ? (
          <BoardModeToggle mode={boardMode} onChange={setBoardMode} />
        ) : null}
        <EmptyState
          title={isGolf ? 'No golf stats yet' : 'No player leaderboard'}
          subtitle={
            isGolf
              ? 'Player strokes-gained leaderboards are on the way. Golf picks live on the Picks and Signals tabs.'
              : `Player stat leaderboards aren't available for ${sport} yet.`
          }
        />
      </SafeAreaView>
    );
  }

  const rightLabel =
    effectiveMode === 'hitRate' ? 'Hit Rate' : basis === 'perGame' ? 'Avg' : stat.label;

  // The stat group being browsed is simply the selected stat's group — derived,
  // never separate state, so the group tabs can't desync from the leaderboard.
  const activeGroup = stat.group;
  // Switching group selects that group's first stat (which also snaps the line
  // ruler to its default). Re-tapping the active group is a no-op.
  const pickGroup = (g: (typeof groups)[number]) => {
    if (g === activeGroup) return;
    const first = statsForSport(sport).find((s) => s.group === g);
    if (first) pickStat(first);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Stats</Text>
          <View style={styles.rightActions}>
            <Pressable
              onPress={() => setFiltersOpen(true)}
              style={({ pressed }) => [styles.filterBtn, pressed && styles.pressed]}
            >
              <Ionicons name="options-outline" size={16} color={colors.tint} />
              <Text style={styles.filterBtnText}>Filters</Text>
              {activeFilterCount > 0 ? (
                <View style={styles.filterBadge}>
                  <Text style={styles.filterBadgeText}>{activeFilterCount}</Text>
                </View>
              ) : null}
            </Pressable>
            <SettingsButton />
          </View>
        </View>
        <SportsbookIndicator coverageNote={coverageNote} />
        <SportToggle />
      </View>

      {supportsTeamBoard(sport) ? (
        <BoardModeToggle mode={boardMode} onChange={setBoardMode} />
      ) : null}

      {/* Stat selector — the primary control, straight under the sport row.
          One tappable group row (Passing | Rushing | …) plus a single stat chip
          row scoped to the active group, instead of the old one-chip-row-per-
          group stack (4 rows for NFL) that pushed the leaderboard below the
          fold. Sports with a single group (WNBA/NBA/UFC) skip the group row. */}
      <View style={styles.statPicker}>
        {groups.length > 1 ? (
          <GroupTabs
            groups={groups}
            active={activeGroup}
            onChange={pickGroup}
          />
        ) : null}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.fixedRow}
          contentContainerStyle={styles.chipRow}
          keyboardShouldPersistTaps="handled"
        >
          {statsForSport(sport)
            .filter((s) => s.group === activeGroup)
            .map((s) => (
              <FilterChip
                key={`${s.group}:${String(s.key)}`}
                label={s.label}
                active={s.key === stat.key && s.group === stat.group}
                onPress={() => pickStat(s)}
              />
            ))}
        </ScrollView>
      </View>

      {/* Line picker: the mode, a tick ruler, then the headline. */}
      {effectiveMode === 'hitRate' ? (
        <>
          <View style={styles.lineRow}>
            {/* Locked to the one side the member's books actually sell. It
                loses the chevron AND the chip's fill and border, because a
                DIMMED BORDERED CHIP is iOS for "a button you cannot use right
                now" and gets tapped again; a label has no container (UX
                review). The text stays at full textSecondary strength rather
                than being faded onto a chip, which would land at ~3.5:1.
                The reason lives in the coverage note below, so this carries no
                accessibilityState and no sentence — VoiceOver was reading the
                whole thing twice, once here and once from the caption, and
                announcing "dimmed" on an element declared as static text. */}
            <Pressable
              onPress={() => setModeOpen(true)}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              accessibilityRole="button"
              accessibilityLabel="Show bets that are"
              accessibilityValue={{ text: hitModeLabel(hitMode) }}
              accessibilityHint="Opens the At Least, Over, Under options"
              style={({ pressed }) => [styles.dirPill, pressed && styles.pressed]}
            >
              <Text style={styles.dirPillText} numberOfLines={1}>
                {hitModeLabel(hitMode)}
              </Text>
              {/* chevron-expand, not chevron-down: this opens a menu in place,
                  it does not navigate. */}
              <Ionicons name="chevron-expand" size={14} color={colors.textSecondary} />
            </Pressable>
            <LineRuler
              value={lineN}
              min={1}
              max={maxLineN(stat) + (hitMode === 'under' ? 1 : 0)}
              onChange={setLineN}
              a11yLabel={`${stat?.label ?? ''} line`}
            />
          </View>
          <View style={styles.headlineRow}>
            <View style={styles.headlineRule} />
            <Text style={styles.headlineText}>{lineHeadline}</Text>
            {/* The book's own name for the same bet. Without it the ruler says
                1, the headline says "2+" and the number joining them is
                nowhere on screen (UX review). */}
            <Text style={styles.headlineLine}>{hitModeLineLabel(lineN, hitMode)}</Text>
            <View style={styles.headlineRule} />
          </View>
        </>
      ) : null}

      {/* Time window strip (L3…L20) + the tonight-slate toggle at the end.
          The toggle sits here rather than in the Filters sheet because "who is
          playing today" is the cut users reach for constantly; it only renders
          when a slate actually exists, so it can never empty the board.
          RN ScrollViews default to flexGrow/flexShrink 1, so as a direct child
          of the screen column this row gets crushed to a sliver whenever the
          controls + list overflow the screen (labels clip out entirely).
          Pin it to its natural height — the FlatList below is the flexible
          region. */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.fixedRow}
        contentContainerStyle={styles.windowRow}
        keyboardShouldPersistTaps="handled"
      >
        {TIME_WINDOWS.map((w) => (
          <FilterChip
            key={String(w.value)}
            label={w.label}
            active={w.value === timeWindow}
            onPress={() => setTimeWindow(w.value)}
          />
        ))}
        {hasSlate ? (
          <>
            <View style={styles.rowDivider} />
            <FilterChip
              label={slateLabel}
              icon="flame-outline"
              active={tonightActive}
              onPress={() => setTonightOnly((v) => !v)}
            />
          </>
        ) : null}
      </ScrollView>

      {/* Hit Rates | Averages */}
      {canHitRate ? (
        <SegmentTabs
          items={MODES}
          active={mode}
          onChange={setMode}
          labelFor={(m) => (m === 'hitRate' ? 'Hit Rates' : 'Averages')}
        />
      ) : null}

      {/* A failed load is recoverable far more often than not — PostgREST
          answers 503 for as long as it takes to rebuild its schema cache — so
          the banner carries the retry rather than making the user leave the
          tab and come back. */}
      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText} numberOfLines={3}>
            Couldn’t load the board: {error}
          </Text>
          <Pressable
            onPress={() => void load()}
            disabled={loading}
            hitSlop={8}
            accessibilityLabel="Retry loading the board"
            style={({ pressed }) => [styles.retryBtn, pressed && styles.pressed]}
          >
            <Text style={styles.retryText}>{loading ? 'Retrying…' : 'Retry'}</Text>
          </Pressable>
        </View>
      ) : null}

      {fromParlay ? (
        <View style={styles.fromParlayBanner}>
          <Ionicons name="receipt-outline" size={15} color={colors.tint} />
          <Text style={styles.fromParlayText}>
            Building your betslip — tap a line to add it, and you’ll head right back.
          </Text>
          <Pressable
            onPress={() => navigation.setParams({ fromParlay: undefined })}
            hitSlop={8}
            accessibilityLabel="Dismiss"
          >
            <Ionicons name="close" size={16} color={colors.textSecondary} />
          </Pressable>
        </View>
      ) : null}

      {activePills.length > 0 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.fixedRow}
          contentContainerStyle={styles.pillsScroll}
          keyboardShouldPersistTaps="handled"
        >
          {activePills.map((p) => (
            <Pressable
              key={p.key}
              onPress={p.onRemove}
              accessibilityLabel={`Remove filter ${p.label}`}
              style={({ pressed }) => [styles.pill, pressed && styles.pressed]}
              hitSlop={6}
            >
              <Text style={styles.pillText}>{p.label}</Text>
              <Ionicons name="close" size={12} color={colors.tint} />
            </Pressable>
          ))}
          {/* Only offered once the user has actually changed something. */}
          {activeFilterCount > 0 || tonightActive ? (
            <Pressable
              onPress={resetFilters}
              style={({ pressed }) => [styles.clearBtn, pressed && styles.pressed]}
              hitSlop={6}
            >
              <Text style={styles.clearText}>Clear all</Text>
            </Pressable>
          ) : null}
        </ScrollView>
      ) : null}

      {noLinesNote ? (
        <Pressable
          onPress={noLinesNote.canSwitch ? () => setPickerOpen(true) : undefined}
          disabled={!noLinesNote.canSwitch}
          accessibilityRole={noLinesNote.canSwitch ? 'button' : undefined}
          accessibilityLabel={
            noLinesNote.canSwitch ? `${noLinesNote.text} Switch sportsbook` : noLinesNote.text
          }
          style={({ pressed }) => [styles.noLinesRow, pressed && styles.pressed]}
        >
          <Ionicons name="information-circle-outline" size={13} color={colors.textTertiary} />
          <Text style={styles.noLinesText}>
            {noLinesNote.text}
            {noLinesNote.canSwitch ? (
              <Text style={styles.noLinesLink}> Change your sportsbooks ›</Text>
            ) : null}
          </Text>
        </Pressable>
      ) : null}

      {(effectiveMode === 'hitRate' ? hitRatePlayers.length : ranked.length) > 0 ? (
        <ColumnHeader
          rightLabel={rightLabel}
          showOdds={showOdds}
          // Named for the book it prints — "FD", "DK", "MGM" — so a FanDuel
          // user never reads an unlabelled number as someone else's. With
          // several books selected the cells no longer share one, so the
          // header names the rule ("BEST") and each pill carries its badge.
          oddsLabel={booksLabel(books)}
          // On an off day the slate — and so the lines — belong to a FUTURE
          // date. An undated header would read as "now" (UX_REVIEW §3).
          oddsDateLabel={slate.date && !slate.isToday ? weekdayET(slate.date) : null}
          showMatchup={matchupByTeam.size > 0}
        />
      ) : null}

      {effectiveMode === 'hitRate' ? (
        <FlatList
          data={hitRatePlayers}
          keyExtractor={(item) => item.player_id}
          renderItem={({ item, index }) => {
            const mu = item.team ? matchupByTeam.get(item.team) : undefined;
            const quote = quoteFor(item);
            return (
              <HitRateRow
                rank={index + 1}
                player={item}
                matchup={mu ? gradeMatchup(sport, playerType, mu) : null}
                showMatchup={matchupByTeam.size > 0}
                subline={sublineFor(item)}
                quote={quote}
                started={item.team ? startedTeams.get(item.team) ?? null : null}
                showOdds={showOdds}
                statLabel={betLabel}
                colorful={colorful}
                onOddsPress={quote ? () => openBook(quote) : undefined}
                tappable={playerDetail}
                onPress={() => openPlayer(item)}
              />
            );
          }}
          ListEmptyComponent={
            loading ? (
              <ActivityIndicator style={styles.loading} />
            ) : (
              <EmptyState
                title={error ? 'Couldn’t load players' : 'No players'}
                subtitle={emptySubtitle}
              />
            )
          }
          style={styles.listFlex}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          initialNumToRender={20}
          // Every row prints a clock now, so the board can visibly go stale
          // between fetches — and it was the one list screen in the app whose
          // pull gesture did nothing (UX review, 2026-09-05). The 60s tick
          // ages the LABELS; this is how a user re-reads the DATA.
          refreshControl={<RefreshControl refreshing={loading} onRefresh={() => void load()} />}
        />
      ) : (
        <FlatList
          data={ranked}
          keyExtractor={(item) => item.row.player_id}
          renderItem={({ item, index }) => {
            const mu = item.row.team ? matchupByTeam.get(item.row.team) : undefined;
            const quote = quoteFor(item.row);
            return (
              <LeaderRow
                rank={index + 1}
                row={item.row}
                value={item.value}
                gp={item.gp}
                basis={basis}
                matchup={mu ? gradeMatchup(sport, playerType, mu) : null}
                showMatchup={matchupByTeam.size > 0}
                subline={sublineFor(item.row)}
                quote={quote}
                started={item.row.team ? startedTeams.get(item.row.team) ?? null : null}
                showOdds={showOdds}
                statLabel={betLabel}
                onOddsPress={quote ? () => openBook(quote) : undefined}
                tappable={playerDetail}
                onPress={() => openPlayer(item.row)}
              />
            );
          }}
          ListEmptyComponent={
            loading ? (
              <ActivityIndicator style={styles.loading} />
            ) : (
              <EmptyState
                title={error ? 'Couldn’t load players' : 'No players'}
                subtitle={emptySubtitle}
              />
            )
          }
          style={styles.listFlex}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          initialNumToRender={20}
          // Every row prints a clock now, so the board can visibly go stale
          // between fetches — and it was the one list screen in the app whose
          // pull gesture did nothing (UX review, 2026-09-05). The 60s tick
          // ages the LABELS; this is how a user re-reads the DATA.
          refreshControl={<RefreshControl refreshing={loading} onRefresh={() => void load()} />}
        />
      )}

      <SportsbookPickerSheet
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        coverageNote={coverageNote}
      />
      <HitModeSheet
        visible={modeOpen}
        mode={hitMode}
        lineN={lineN}
        statLabel={stat?.label ?? ''}
        onPick={chooseMode}
        overAvailable={overAvailable}
        underAvailable={underAvailable}
        unavailableNote={dirLockNote}
        onClose={() => setModeOpen(false)}
      />
      <AddLineSheet
        input={lineSheetInput}
        game={lineSheetGame}
        onClose={() => setLineSheet(null)}
        onAdded={fromParlay ? () => navigation.navigate('Betslip') : undefined}
      />

      <FilterSheet
        visible={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Filter players"
        resultCount={effectiveMode === 'hitRate' ? hitRatePlayers.length : ranked.length}
        itemNoun="player"
        onReset={resetFilters}
        canReset={activeFilterCount > 0}
      >
        <FilterSection
          title="Search"
          summary={query.trim() ? `“${query.trim()}”` : 'Any player'}
          defaultOpen={query.trim().length > 0}
        >
          <View style={styles.searchWrap}>
            <Ionicons name="search" size={16} color={colors.textTertiary} />
            <TextInput
              style={styles.searchInput}
              value={query}
              onChangeText={setQuery}
              placeholder="Search players in this list…"
              placeholderTextColor={colors.textTertiary}
              autoCorrect={false}
              autoCapitalize="words"
              returnKeyType="search"
            />
            {query.length > 0 ? (
              <Pressable onPress={() => setQuery('')} hitSlop={8} accessibilityRole="button" accessibilityLabel="Clear search">
                <Ionicons name="close-circle" size={18} color={colors.textTertiary} />
              </Pressable>
            ) : null}
          </View>
        </FilterSection>

        {effectiveMode === 'totals' ? (
          <FilterSection
            title="Rank by"
            subtitle="Per-game average or the raw total."
            summary={basis === 'perGame' ? 'Per game' : 'Total'}
          >
            <View style={styles.chipWrap}>
              <FilterChip
                label="Per game"
                active={basis === 'perGame'}
                onPress={() => toggleBasis('perGame')}
              />
              <FilterChip
                label="Total"
                active={basis === 'total'}
                onPress={() => toggleBasis('total')}
              />
            </View>
          </FilterSection>
        ) : null}

        <FilterSection
          title="Sort by"
          subtitle="Ties break on sample size, so regulars come first."
          summary={sortLabel(sortKey, effectiveMode)}
        >
          <View style={styles.chipWrap}>
            {sortOptionsFor(effectiveMode).map((o) => (
              <FilterChip
                key={o.key}
                label={o.label}
                active={sortKey === o.key}
                onPress={() => setSortKey(o.key)}
              />
            ))}
          </View>
        </FilterSection>

        {/* Hit-rate band — the reason someone opens this sheet is usually
            "show me the 70%+ guys", so the presets come before the fields. */}
        {effectiveMode === 'hitRate' ? (
          <FilterSection
            title="Hit rate"
            subtitle="Only show players inside this band."
            summary={bandSummary}
          >
            <View style={styles.chipWrap}>
              {HIT_RATE_PRESETS.map((p) => {
                const on = (parseFloat(minHitRate) || 0) === p && maxHitRate.trim() === '';
                return (
                  <FilterChip
                    key={p}
                    label={`${p}%+`}
                    active={on}
                    onPress={() => {
                      setMinHitRate(on ? '' : String(p));
                      setMaxHitRate('');
                    }}
                  />
                );
              })}
            </View>
            <View style={styles.fieldRow}>
              <FilterField
                label="Min hit rate"
                value={minHitRate}
                onChange={setMinHitRate}
                placeholder="0"
                suffix="%"
                maxLength={3}
              />
              <FilterField
                label="Max hit rate"
                value={maxHitRate}
                onChange={setMaxHitRate}
                placeholder="100"
                suffix="%"
                maxLength={3}
              />
            </View>
          </FilterSection>
        ) : null}

        {teams.length > 1 ? (
          <FilterSection title="Team" summary={teamFilter ?? 'All teams'}>
            <View style={styles.chipWrap}>
              <FilterChip
                label="All teams"
                active={teamFilter === null}
                onPress={() => setTeamFilter(null)}
              />
              {teams.map((t) => (
                <FilterChip
                  key={t}
                  label={t}
                  size="sm"
                  active={teamFilter === t}
                  onPress={() => setTeamFilter(teamFilter === t ? null : t)}
                />
              ))}
            </View>
          </FilterSection>
        ) : null}
      </FilterSheet>
    </SafeAreaView>
  );
}

/** Width of one ruler tick on long rulers — the snap interval. */
const TICK_W = 12;
/** Fixed width of a tick's value label (fits 3 digits). */
const LABEL_W = 44;

/**
 * Scrollable tick ruler for the line, global across every sport's stat board.
 *
 * The old windowed row only offered ±1/±2 taps — unusable on stats whose lines
 * run into the hundreds (NFL Pass Yards: getting from 225 to 250 took 25 taps).
 * This is a real drag/flick ruler: the strip scrolls under a fixed centre
 * marker, snaps to whole values (snapToInterval), and reports the value under
 * the marker when the scroll settles. Tapping a tick still selects it.
 *
 * Sync rules: `reportedRef` is the last value THIS component emitted, so the
 * value-prop effect only repositions the strip for OUTSIDE changes (a stat
 * switch snapping to its default) and never fights an in-flight scroll.
 * Label cadence adapts to the range (every value for short rulers, every
 * 5th/25th for yard-scale ones) so the strip stays legible at any size.
 */
function LineRuler({
  value,
  min,
  max,
  onChange,
  a11yLabel,
}: {
  a11yLabel: string;
  value: number;
  min: number;
  max: number;
  onChange: (n: number) => void;
}) {
  const [width, setWidth] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const reportedRef = useRef(value);
  const count = Math.max(1, max - min + 1);
  // Short rulers (hits, Ks) get wide ticks with every value labeled — the old
  // look, now scrollable. Long rulers (points, yards) get dense ticks with
  // labels every 5th/10th value so the strip stays legible and flickable.
  const tickW = count <= 30 ? 26 : TICK_W;
  const labelEvery = count > 120 ? 10 : count > 30 ? 5 : 1;
  // Pad each end by half the viewport so the first/last values can reach the
  // centre marker.
  const sidePad = Math.max(0, width / 2 - tickW / 2);

  const offsetFor = (v: number) => (Math.min(max, Math.max(min, v)) - min) * tickW;

  // Position the strip once the viewport is measured (contentOffset alone is
  // unreliable on Android), and again whenever the value changes from outside.
  useEffect(() => {
    if (width === 0) return;
    reportedRef.current = value;
    scrollRef.current?.scrollTo({ x: offsetFor(value), animated: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width]);
  useEffect(() => {
    if (reportedRef.current === value) return;
    reportedRef.current = value;
    scrollRef.current?.scrollTo({ x: offsetFor(value), animated: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Emit the value under the centre marker once a scroll settles. Fires from
  // both end events (a drag with no fling never gets a momentum-end); emitting
  // is idempotent via reportedRef.
  const settle = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const idx = Math.round(e.nativeEvent.contentOffset.x / tickW);
    const v = Math.min(max, Math.max(min, min + idx));
    if (v !== reportedRef.current) {
      reportedRef.current = v;
      onChange(v);
    }
  };

  const pickTick = (v: number) => {
    reportedRef.current = v;
    scrollRef.current?.scrollTo({ x: offsetFor(v), animated: true });
    onChange(v);
  };

  return (
    // ONE adjustable element, not N tick buttons. VoiceOver gets the number
    // as a value it can increment and decrement; the ticks themselves are
    // decoration and are hidden from it. This matters more since the mode
    // landed: in Under mode the ruler's number and the headline's deliberately
    // differ by one, so a screen-reader user who cannot reach the ruler cannot
    // tell which bet the board is on (UX review, 2026-09-05).
    <View
      style={styles.rulerWrap}
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      accessible
      accessibilityRole="adjustable"
      accessibilityLabel={a11yLabel}
      accessibilityValue={{ min, max, now: value, text: String(value) }}
      accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
      onAccessibilityAction={(e) => {
        const next = e.nativeEvent.actionName === 'increment' ? value + 1 : value - 1;
        if (next >= min && next <= max) pickTick(next);
      }}
    >
      {width > 0 ? (
        <ScrollView
          ref={scrollRef}
          horizontal
          showsHorizontalScrollIndicator={false}
          snapToInterval={tickW}
          decelerationRate="fast"
          contentOffset={{ x: offsetFor(value), y: 0 }}
          contentContainerStyle={{ paddingHorizontal: sidePad }}
          onMomentumScrollEnd={settle}
          onScrollEndDrag={settle}
        >
          {Array.from({ length: count }, (_, i) => {
            const v = min + i;
            const labeled = v % labelEvery === 0 || v === min || v === max;
            return (
              <Pressable
                key={v}
                onPress={() => pickTick(v)}
                accessibilityElementsHidden
                importantForAccessibility="no-hide-descendants"
                style={[styles.tickCol, { width: tickW }]}
              >
                <View style={[styles.tick, labeled && styles.tickMajor]} />
                {/* The label is wider than its tick column — centre it with a
                    negative margin so it can't clip, and only label ticks far
                    enough apart (labelEvery) that neighbours can't collide. */}
                <Text
                  style={[styles.tickLabel, { marginHorizontal: -(LABEL_W - tickW) / 2 }]}
                  numberOfLines={1}
                >
                  {labeled ? v : ''}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
      {/* Fixed centre marker + the selected value, over the scrolling strip. */}
      <View pointerEvents="none" style={styles.centerMarker}>
        <View style={styles.centerLine} />
        <View style={styles.tickValueBox}>
          <Text style={styles.tickValueActive}>{value}</Text>
        </View>
      </View>
    </View>
  );
}

/**
 * Players | Teams. Uses the same underline-tab look as Hit Rates | Averages so
 * the two levels of switching read as the same kind of control.
 */
function BoardModeToggle({
  mode,
  onChange,
}: {
  mode: BoardMode;
  onChange: (m: BoardMode) => void;
}) {
  return (
    <SegmentTabs
      items={BOARD_MODES}
      active={mode}
      onChange={onChange}
      labelFor={(m) => (m === 'players' ? 'Players' : 'Teams')}
    />
  );
}

function fmtValue(value: number, basis: Basis): string {
  return basis === 'perGame' ? value.toFixed(1) : String(Math.round(value));
}

/** Right-hand LINE cell: the user's sportsbook's price for the number the
 * board is on, or a dash.
 *
 * Filled in the book's own colour with the book's mark beside the price, and
 * tapping it opens that book — the shape Matt asked for on 2026-09-04, and the
 * shape every odds-comparison app in the category uses. The price is the whole
 * cell: no caption under it, because the board's headline above already says
 * which line it is ("1+ Hits") and repeating it 25 times down a column is noise
 * the competitor does not carry either.
 *
 * Its own Pressable, so the tap doesn't bubble to the row (which opens the
 * player). */
/** "2+" for over 1.5, "At most 1" for under 1.5 — lineHeadline's idiom. */
export function offLineCaption(line: number, side: StatsOddsSide): string {
  return thresholdLabel(line, side);
}

function OddsCell({
  quote,
  started,
  playerName,
  statLabel,
  onPress,
}: {
  quote: StatsOddsQuote | null;
  started?: 'Live' | 'Final' | null;
  playerName: string;
  statLabel: string;
  onPress?: () => void;
}) {
  if (quote == null) {
    // A game in progress has no line a user can still take (unstartedGameIds),
    // and the cell says so — a dash there read as "the book never priced him".
    if (started) {
      return (
        <View style={styles.oddsWrap} accessible accessibilityLabel={`${playerName}, game ${started.toLowerCase()}`}>
          <Text style={styles.oddsStarted}>{started}</Text>
        </View>
      );
    }
    // The dash is not read out: the row's own label already says the player and
    // the stat, and "em dash" is not information.
    return (
      <View style={styles.oddsWrap} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Text style={styles.oddsEmpty}>—</Text>
      </View>
    );
  }
  // Filled only for the book whose brand colour we actually have. The app tint
  // is near-black; twenty-five solid blocks of it down the right edge outweigh
  // the hit rate, which is the number this board exists to show — and a tint
  // pill also reads as one of our own buttons rather than as FanDuel's price.
  const c = bookButtonColors(quote.book);
  const filled = quote.book === MODEL_BOOK;
  const sideWord = quote.side === 'under' ? 'under' : 'over';
  // The pill is a nested Pressable, so VoiceOver reads it as its own element and
  // inherits nothing from the row — without the player and the stat it is 25
  // near-identical prices with no way to tell whose is whose. The line goes in
  // here precisely because it is no longer printed on the row.
  const label = `${playerName}, ${sideWord} ${quote.line} ${statLabel}, ${formatAmerican(quote.price)} at ${bookName(quote.book)}${quote.offLine ? ', the book’s own line, not the board’s' : ''}`;
  // The book's OWN line, when it does not post the board's: printed under the
  // price in the BOARD'S idiom ("2+", "At most 1" — the header's vocabulary,
  // not sportsbook notation) so it reads against the header without
  // translation (UX review). statsOdds offLine.
  const caption = quote.offLine ? offLineCaption(quote.line, quote.side) : null;
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      // Dropping the caption shrank the target below 44pt, so hitSlop makes up
      // the difference; a mis-tap opens a dismissible sheet, never a book.
      hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint="Asks to add this line to your betslip"
      style={({ pressed }) => [styles.oddsWrap, pressed && styles.pressed]}
    >
      <View
        style={[
          styles.oddsPill,
          filled ? { backgroundColor: c.bg } : styles.oddsPillOutlined,
        ]}
      >
        <Text
          style={[styles.oddsText, { color: filled ? c.fg : colors.textPrimary }]}
          numberOfLines={1}
        >
          {formatAmerican(quote.price)}
        </Text>
        <BookMark book={quote.book} color={filled ? c.fg : colors.textPrimary} />
      </View>
      {caption ? <Text style={styles.oddsCaption}>{caption}</Text> : null}
    </Pressable>
  );
}

/** MATCHUP: how hard this spot is, as one letter.
 *
 * Matt, 2026-09-05: "update spot column to just be difficulty of that match up
 * and have a bigger scale besides low med and high". So the cell is the grade
 * and nothing else — the opponent moved under the name the same day, and the
 * FACT behind the grade (the opposing starter and his ERA, the defence's
 * rating) moved to the player's detail screen, which was Matt's own alternative
 * home for it on 2026-09-04 ("or have it be in the player data when you click
 * on a record"). It is also still spoken in full here, in the cell's label.
 *
 * The grade is a percentile against MEASURED league distributions, not the
 * three hand-set cliffs it replaces — `lib/matchup.ts` carries the numbers and
 * why the old bands called 77% of WNBA matchups favourable.
 *
 * Colour is the `colors.grade*` ramp, NOT bet/avoid: those are this app's
 * BET/AVOID semantics and the hit-rate column 60pt away is already a traffic
 * light. It is also never the only carrier — the letter is the fact, the
 * colour only speeds up the scan, and the label spells the letter out
 * ("B plus", because VoiceOver reads a bare "+" as nothing).
 *
 * An ungraded matchup is a DASH, never a C: grading a starter we do not know
 * as average invents the one fact this column exists to report.
 */
function MatchupCell({ matchup }: { matchup: MatchupInfo | null }) {
  if (!matchup?.grade) {
    return (
      <View
        style={styles.matchupWrap}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <Text style={styles.oddsEmpty}>—</Text>
      </View>
    );
  }
  return (
    <View
      style={styles.matchupWrap}
      accessible
      accessibilityLabel={`Matchup grade ${gradeSpoken(matchup.grade)}${matchup.fact ? `, ${matchup.fact}` : ''}`}
    >
      <Text style={[styles.matchupGrade, { color: gradeColor(matchup.grade) }]} numberOfLines={1}>
        {matchup.grade}
      </Text>
    </View>
  );
}

/** Compact column header sitting flush above the leaderboard (HOF-style). */
function ColumnHeader({
  rightLabel,
  showOdds,
  oddsLabel,
  oddsDateLabel,
  showMatchup,
}: {
  rightLabel: string;
  showOdds: boolean;
  /** Short name of the book the column prints ("FD", "DK"). */
  oddsLabel: string;
  /** Weekday of the slate the prices are for, when it is not today. */
  oddsDateLabel?: string | null;
  showMatchup: boolean;
}) {
  return (
    <View style={styles.colHeader}>
      <Text style={styles.colHeaderRank}>RK</Text>
      <Text style={styles.colHeaderName}>PLAYER</Text>
      <Text style={styles.colHeaderRight} numberOfLines={1}>
        {rightLabel.toUpperCase()}
      </Text>
      {showOdds ? (
        <Text style={[styles.colHeaderRight, styles.colHeaderOdds]} numberOfLines={1}>
          {oddsDateLabel ? `${oddsLabel} ${oddsDateLabel}` : oddsLabel}
        </Text>
      ) : null}
      {showMatchup ? (
        <View style={styles.colHeaderMatchup}>
          <Text style={styles.colHeaderRight} numberOfLines={1}>
            GRADE
          </Text>
          <InfoTooltip
            title="Matchup grade"
            body={
              'How hard tonight\u2019s spot is for this player, graded against the ' +
              'rest of the league this season. A+ is the easiest matchup on the ' +
              'board and F the hardest.\n\n' +
              'Batters are graded on the opposing starter\u2019s ERA, pitchers on the ' +
              'opposing lineup\u2019s wOBA and strikeout rate, and WNBA players on the ' +
              'opposing defence\u2019s rating.\n\n' +
              'A dash means the starter isn\u2019t confirmed yet — an unknown matchup ' +
              'is never graded as average.'
            }
            accessibilityLabel="What the matchup grade means"
          />
        </View>
      ) : null}
    </View>
  );
}

function LeaderRow({
  rank,
  row,
  value,
  gp,
  basis,
  matchup,
  showMatchup,
  subline,
  quote,
  started,
  showOdds,
  statLabel,
  onOddsPress,
  tappable,
  onPress,
}: {
  rank: number;
  row: SeasonTotalsRow;
  value: number;
  gp: number;
  basis: Basis;
  matchup: MatchupInfo | null;
  showMatchup: boolean;
  /** "9:40 PM ET · @ SEA" under the name; null when the row has no game. */
  subline: string | null;
  quote: StatsOddsQuote | null;
  /** The player's game is live or over: no line, and the cell says which. */
  started: 'Live' | 'Final' | null;
  showOdds: boolean;
  statLabel: string;
  onOddsPress?: () => void;
  tappable: boolean;
  onPress: () => void;
}) {
  const body = (
    <>
      <Text style={styles.rank}>{rank}</Text>
      <View
        style={styles.rowMain}
        accessible={tappable}
        accessibilityRole={tappable ? 'button' : undefined}
        accessibilityLabel={
          tappable
            ? `${row.player_name ?? ''}${row.team ? `, ${row.team}` : ''}, ${fmtValue(value, basis)} ${statLabel}${subline ? `, ${sublineSpoken(subline)}` : ''}`
            : undefined
        }
        accessibilityHint={tappable ? 'Opens this player' : undefined}
      >
        <Text style={styles.rowName} numberOfLines={1}>
          {row.player_name}
          {row.team ? <Text style={styles.rowTeam}>  {row.team}</Text> : null}
        </Text>
        {subline ? (
          // The spoken form goes on the Text itself, not only in the row's
          // label: a row that is NOT tappable (NHL, UFC, Golf) sets
          // `accessible={false}` above, so VoiceOver reads this line on its own
          // and would say "at sign SEA" (UX review, 2026-09-05).
          <Text
            style={styles.rowSubline}
            numberOfLines={1}
            accessibilityLabel={sublineSpoken(subline)}
          >
            {subline}
          </Text>
        ) : null}
      </View>
      <View style={styles.valueWrap}>
        <Text style={styles.value}>{fmtValue(value, basis)}</Text>
      </View>
      {showOdds ? (
        <OddsCell
          quote={quote}
          started={started}
          playerName={row.player_name ?? ''}
          statLabel={statLabel}
          onPress={onOddsPress}
        />
      ) : null}
      {showMatchup ? <MatchupCell matchup={matchup} /> : null}
    </>
  );
  if (!tappable) return <View style={styles.row}>{body}</View>;
  return (
    // accessible={false}: a Pressable is accessible by default, which collapses
    // the row into ONE VoiceOver element — the nested price pill stops being a
    // button and activating anywhere fires the ROW's onPress. That made the
    // sportsbook hand-off, which is now the only bet link, unreachable with
    // VoiceOver. The row's own tap is carried by the name block instead.
    <Pressable
      onPress={onPress}
      accessible={false}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      {body}
    </Pressable>
  );
}

function HitRateRow({
  rank,
  player,
  matchup,
  showMatchup,
  subline,
  quote,
  started,
  showOdds,
  statLabel,
  colorful,
  onOddsPress,
  tappable,
  onPress,
}: {
  rank: number;
  player: HitRatePlayer;
  matchup: MatchupInfo | null;
  showMatchup: boolean;
  /** "9:40 PM ET · @ SEA" under the name; null when the row has no game. */
  subline: string | null;
  quote: StatsOddsQuote | null;
  /** Does the hit-rate column span more than one band? Colour only if so. */
  colorful: boolean;
  /** The player's game is live or over: no line, and the cell says which. */
  started: 'Live' | 'Final' | null;
  showOdds: boolean;
  statLabel: string;
  onOddsPress?: () => void;
  tappable: boolean;
  onPress: () => void;
}) {
  const pctColor = hitRateColor(player.pct, colorful);
  const body = (
    <>
      <Text style={styles.rank}>{rank}</Text>
      <View
        style={styles.rowMain}
        accessible={tappable}
        accessibilityRole={tappable ? 'button' : undefined}
        accessibilityLabel={
          tappable
            ? `${player.player_name}${player.team ? `, ${player.team}` : ''}, ${Math.round(player.pct * 100)} percent, ${player.hits} of ${player.total}${subline ? `, ${sublineSpoken(subline)}` : ''}`
            : undefined
        }
        accessibilityHint={tappable ? 'Opens this player' : undefined}
      >
        <Text style={styles.rowName} numberOfLines={1}>
          {player.player_name}
          {player.team ? <Text style={styles.rowTeam}>  {player.team}</Text> : null}
        </Text>
        {subline ? (
          // The spoken form goes on the Text itself, not only in the row's
          // label: a row that is NOT tappable (NHL, UFC, Golf) sets
          // `accessible={false}` above, so VoiceOver reads this line on its own
          // and would say "at sign SEA" (UX review, 2026-09-05).
          <Text
            style={styles.rowSubline}
            numberOfLines={1}
            accessibilityLabel={sublineSpoken(subline)}
          >
            {subline}
          </Text>
        ) : null}
      </View>
      <View style={styles.valueWrap}>
        <Text style={[styles.value, { color: pctColor }]}>
          {Math.round(player.pct * 100)}%
        </Text>
        <Text style={styles.valueLabel}>
          {player.hits}/{player.total}
        </Text>
      </View>
      {showOdds ? (
        <OddsCell
          quote={quote}
          started={started}
          playerName={player.player_name}
          statLabel={statLabel}
          onPress={onOddsPress}
        />
      ) : null}
      {showMatchup ? <MatchupCell matchup={matchup} /> : null}
    </>
  );
  if (!tappable) return <View style={styles.row}>{body}</View>;
  return (
    // accessible={false}: a Pressable is accessible by default, which collapses
    // the row into ONE VoiceOver element — the nested price pill stops being a
    // button and activating anywhere fires the ROW's onPress. That made the
    // sportsbook hand-off, which is now the only bet link, unreachable with
    // VoiceOver. The row's own tap is carried by the name block instead.
    <Pressable
      onPress={onPress}
      accessible={false}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },

  // Applied to the horizontal chip/pill scrollers that sit directly in the
  // screen column: overrides the ScrollView default flexGrow/flexShrink of 1
  // so they can never be stretched or crushed — the leaderboard FlatList
  // (listFlex) is the one flexible child.
  fixedRow: {
    flexGrow: 0,
    flexShrink: 0,
  },
  listFlex: {
    flex: 1,
  },

  // Active-filter pills, shown between the controls and the table so it's
  // always obvious what's narrowing the board (and one tap to undo).
  pillsScroll: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingLeft: 10,
    paddingRight: 7,
    paddingVertical: 4,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.tint,
  },
  pillText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  clearBtn: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  clearText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.avoid,
  },

  // Sheet layout helpers
  chipWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  fieldRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  // Separates the time-window chips from the tonight toggle in the same row.
  rowDivider: {
    width: 1,
    alignSelf: 'stretch',
    marginVertical: 4,
    backgroundColor: colors.separatorOpaque,
  },

  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rightActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  filterBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  filterBtnText: {
    fontSize: font.size.footnote,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  filterBadge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 5,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterBadgeText: {
    fontSize: font.size.micro,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },

  // ── Line picker ──
  lineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.xs,
  },
  dirPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: 9,
    borderRadius: radii.sm,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  dirPillLocked: {
    // The container is what says "button", so the container goes. Padding is
    // kept so the ruler beside it does not shift when the lock engages, and
    // Nothing here fades the pill — dimming text onto a chip is the ~3.5:1
    // case UX_REVIEW §5 names by hand, and the check in
    // scripts/verify_stats_odds.ts greps this block for exactly that. The
    // text keeps full textSecondary contrast instead.
    backgroundColor: 'transparent',
    borderColor: 'transparent',
  },
  dirPillTextLocked: {
    color: colors.textSecondary,
  },
  dirPillText: {
    flexShrink: 1,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  rulerWrap: {
    flex: 1,
    height: 58,
    justifyContent: 'center',
  },
  tickCol: {
    alignItems: 'center',
    paddingTop: 6,
  },
  tick: {
    width: 1,
    height: 12,
    borderRadius: 1,
    backgroundColor: colors.separator,
  },
  tickMajor: {
    width: 2,
    height: 20,
    backgroundColor: colors.separatorOpaque,
  },
  tickLabel: {
    width: LABEL_W,
    marginTop: 4,
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    textAlign: 'center',
  },
  // The fixed marker the strip scrolls under: a tint line at the exact snap
  // point, with the selected value boxed beneath it.
  centerMarker: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'flex-start',
    paddingTop: 2,
  },
  centerLine: {
    width: 3,
    height: 24,
    borderRadius: 1.5,
    backgroundColor: colors.tint,
  },
  tickValueBox: {
    marginTop: 2,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radii.sm,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  tickValueActive: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  headlineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.sm,
  },
  headlineRule: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.separator,
  },
  headlineLine: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  headlineText: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },

  // ── Window chips ──
  windowRow: {
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },

  // ── Hit Rates / Averages tabs ──

  statPicker: {
    paddingTop: spacing.xs,
  },
  // Group tabs (Passing | Rushing | …) — same uppercase-caption look the old
  // section labels had, but tappable and on one row.
  chipRow: {
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    paddingVertical: 2,
  },
  searchWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
    gap: spacing.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    paddingVertical: 2,
  },
  list: {
    paddingBottom: spacing.xl,
  },
  // Column header sits flush above the first row so header + rows read as one
  // continuous white table (HOF-style), not inset cards.
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
    fontSize: font.size.micro,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  colHeaderName: {
    flex: 1,
    fontSize: font.size.micro,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  colHeaderRight: {
    width: 48,
    textAlign: 'right',
    fontSize: font.size.micro,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  colHeaderOdds: { minWidth: ODDS_W, textAlign: 'right' },
  // "FanDuel doesn't post Hits lines today" — the book's coverage, in words,
  // where a column of dashes would otherwise read as a broken screen.
  noLinesRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 5,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
  },
  noLinesText: {
    flex: 1,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: font.size.caption * 1.35,
  },
  noLinesLink: { color: colors.tint, fontWeight: font.weight.semibold },
  // A row, not a Text: the legend lives in the header (see MATCHUP_W).
  colHeaderMatchup: {
    minWidth: MATCHUP_W,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 2,
  },
  // Rows are deliberately compact — more players visible per screen.
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    paddingVertical: 5,
    // The row is a tap target that opens the player, and a full-width row
    // cannot use hitSlop without overlapping its neighbours — so the height
    // has to be the target (HIG 44pt). It also stops the list re-flowing when
    // the slate query lands: a one-line row (~26pt) and a two-line row with a
    // subline (~40pt) both fit inside 44, so nothing moves under the thumb
    // (UX review, 2026-09-05).
    minHeight: 44,
    gap: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  rowMain: {
    flex: 1,
    minWidth: 0,
  },
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
  rowTeam: {
    fontSize: font.size.micro,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
  },
  // "9:40 PM ET · @ SEA". Quieter than the name, but NOT quieter than the AA
  // floor: textTertiary (#3C3C4399) composites to ~3.4:1 on the card, and 11pt
  // is not large text, so the hierarchy is carried by SIZE and position rather
  // than by contrast (UX review, 2026-09-05).
  rowSubline: {
    fontSize: font.size.micro,
    color: colors.textSecondary,
    marginTop: 1,
  },
  valueWrap: {
    alignItems: 'flex-end',
    width: 48,
  },
  value: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  valueLabel: {
    fontSize: font.size.nano,
    color: colors.textTertiary,
  },
  // minWidth, not width: the price and its column grow together at large text
  // sizes instead of the number being the thing that gets an ellipsis.
  oddsWrap: {
    minWidth: ODDS_W,
    maxWidth: ODDS_W * 1.5,
    flexShrink: 1,
    alignItems: 'flex-end',
  },
  // Filled in the book's own colour — the pill IS the bet button, and the mark
  // beside the price says whose price it is.
  oddsPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 5,
    minHeight: 26,
    borderRadius: radii.sm,
  },
  oddsPillOutlined: {
    backgroundColor: colors.noneSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
  },
  oddsText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    fontVariant: ['tabular-nums'],
  },
  fromParlayBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  fromParlayText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  oddsEmpty: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
  },
  oddsStarted: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textAlign: 'center',
  },
  oddsCaption: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 1,
  },
  matchupWrap: {
    minWidth: MATCHUP_W,
    maxWidth: MATCHUP_W * 1.4,
    flexShrink: 1,
    alignItems: 'flex-end',
  },
  // One letter (two with a modifier), so it can carry the row's weight — it is
  // the only thing in the column and it has to be legible at a glance down 25
  // rows. Bumped from caption because a bold "B+" at 12pt reads as a footnote
  // rather than a grade.
  matchupGrade: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    letterSpacing: 0.2,
  },
  pressed: { opacity: 0.65 },
  loading: { marginVertical: spacing.xxl },
  retryBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.avoid,
  },
  retryText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.avoid,
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    borderRadius: 8,
  },
  errorText: { flex: 1, color: colors.avoid, fontSize: font.size.footnote },
});

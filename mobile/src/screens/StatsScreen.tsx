import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
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
import { FilterSection, FilterSheet } from '@/components/filters/FilterSheet';
import { RangeSlider } from '@/components/filters/RangeSlider';
import { GameFilterSection } from '@/components/filters/GameFilterSection';
import type { ActivePill } from '@/components/filters/FilterBar';
import { useNow } from '@/hooks/useNow';
import { useGameSelection } from '@/hooks/useGameSelection';
import { useSportFilter, type Sport } from '@/hooks/useSportFilter';
import { usePreferredBooks, BOOKS } from '@/hooks/usePreferredBooks';
import {
  fetchPropLinesForDate,
  fetchRecentGames,
  fetchSeasonStatValues,
  fetchSlateGames,
  fetchTeamStats,
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
import {
  gameFilterSummary,
  isGameSelected,
  pruneSelection,
  selectableGames,
  selectedTeams,
} from '@/lib/gameFilter';
import { computeHitRate, hitRateBandOf, hitRateColorDiscriminates } from '@/lib/hitRate';
import {
  hitModeHeadline,
  hitModeLabel,
  hitModeLineLabel,
  modeLineLabel,
  rulerValueLabel,
  selectionFor,
  type HitMode,
} from '@/lib/hitMode';
import { supportsPlayerDetail } from '@/lib/playerLog';
import {
  buildMatchupMap,
  defenceMetricSpoken,
  gradeColorDiscriminates,
  gradeMatchup,
  gradeOpponentDefence,
  gradeSpoken,
  gradesOnDefence,
  meetsGradeFloor,
  GRADE_FLOORS,
  type MatchupGrade,
  type MatchupInfo,
} from '@/lib/matchup';
import { addDays, formatAmerican, todayET, weekdayET, gameStatus } from '@/lib/format';
import {
  EMPTY_SLATE,
  HIT_RATE_MAX,
  HIT_RATE_MIN,
  HIT_RATE_PRESETS,
  HIT_RATE_STEP,
  buildSlateGameIndex,
  buildTonightSlate,
  compareRows,
  hitRateBand,
  inHitRateBand,
  isOnSlate,
  isStatParticipant,
  slateGameFor,
  slateSubline,
  slateTeams,
  sublineSpoken,
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
  TeamSeasonStats,
  TeamStatsRow,
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

/**
 * How long the board waits for the slate before reading the whole league.
 *
 * One `games` read over a 7-day window — 118 rows on the widest sport measured
 * 2026-09-09 — so the normal case is far inside this and the user sees one
 * continuous spinner rather than a second one. The bound is for the case that
 * never returns at all (see the slate effect).
 */
const SLATE_GATE_MS = 4000;

/** Stable identity, so swapping to "no rows" cannot itself re-render the list. */
const EMPTY_ROWS: never[] = [];

/**
 * Row-shaped placeholders, in place of a bare spinner.
 *
 * The board's loads are no longer instant — turning the slate chip off re-reads
 * the whole league — and the rows that were on screen belong to the question
 * the user just changed, so they must not be left up as if they were the
 * answer. Rows rather than a centred spinner because that is what is arriving,
 * and because a spinner at the top of a scrolled list is invisible to anyone
 * who has scrolled into the board.
 */
function BoardSkeleton() {
  return (
    <View accessible accessibilityLabel="Loading players" style={styles.skeletonWrap}>
      {Array.from({ length: 8 }, (_, i) => (
        <View key={i} style={styles.skeletonRow}>
          <View style={[styles.skeletonBlock, { width: 22 }]} />
          <View style={{ flex: 1, gap: 6 }}>
            <View style={[styles.skeletonBlock, { width: '55%' }]} />
            <View style={[styles.skeletonBlock, { width: '35%', height: 8 }]} />
          </View>
          <View style={[styles.skeletonBlock, { width: ODDS_W - 10 }]} />
        </View>
      ))}
    </View>
  );
}

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
  // Hit Rate controls (front page): a ruler, plus which side of it the bet is
  // on. `lineN` is the ruler's STOP INDEX, not the number on its face — the
  // face is the stop drawn in the active mode's idiom (whole in At Least,
  // the book's half-point line in Over / Under: lib/hitMode.ts). It starts at
  // 1 for every mode, because stop 0 would be "at least none" — every game —
  // and "under -0.5", which no game can be and no book prices.
  const [lineN, setLineN] = useState<number>(() => defaultLineN(defaultStatFor(sport)));
  const [hitMode, setHitMode] = useState<HitMode>('atLeast');
  const [modeOpen, setModeOpen] = useState<boolean>(false);
  // TOUGHNESS as a filter, which is the half of Matt's ask the grade alone did
  // not answer: the column is truthful on every sport now, but until this the
  // board could not be cut or ordered by it. A FLOOR, not a band — "B or
  // better" is the question ("show me the soft spots"); nobody asks for the
  // hardest matchups on the board.
  const [minGrade, setMinGrade] = useState<MatchupGrade | null>(null);
  // Default ON: a dash means we hold no rating for that defence, not that the
  // spot is bad, and on an NCAAF Saturday the ungraded rows are the FCS
  // visitors — the softest spots on the board. Excluding them by default made
  // the filter delete the answer to its own question (UX review).
  const [includeUngraded, setIncludeUngraded] = useState<boolean>(true);
  // The hit-rate band, as whole percents, straight off the sheet's slider.
  // 0-100 is "Any" — the band only narrows the board once an end has moved.
  const [hitLow, setHitLow] = useState<number>(HIT_RATE_MIN);
  const [hitHigh, setHitHigh] = useState<number>(HIT_RATE_MAX);

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
  // The leaderboard read is NARROWED to the slate's teams when the board is
  // filtered to it (statsBoard.slateTeams), so it has to wait for the slate to
  // land — otherwise the first load reads the whole league (54,687 rows on a
  // college Saturday) and is thrown away a moment later. Settled, not
  // successful: a slate we could not reach still releases the board.
  // WHICH SPORT the slate belongs to, not whether one arrived. As a boolean it
  // was read stale on a sport switch: `setSlateReady(false)` and the load effect
  // land in the same commit, so the effect's closure still saw `true` and fired
  // a read narrowed by the OUTGOING sport's teams — NCAAF school names sent at
  // an NFL read, or the whole-league 12,850-row one this gate exists to avoid
  // (UX review, 2026-09-09). The stamping below means no wrong rows were ever
  // painted; the cost was a wasted multi-page request and a slower first paint.
  const [slateFor, setSlateFor] = useState<string | null>(null);
  // The opponent's DEFENCE, for the sports with no matchup view. MLB and WNBA
  // grade a spot off the probable starter or the lineup; every other sport had
  // a column of dashes, so a toughness filter over it would have filtered
  // nothing (Matt, 2026-09-09). Failure-tolerant: no team stats is an ungraded
  // column, never a wrong one.
  const [teamStats, setTeamStats] = useState<TeamSeasonStats>({ season: null, rows: [] });
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
    // BOUNDED, because .finally() is not a guarantee that anything happens.
    // The supabase client is created with no fetch timeout, so a request that
    // hangs never settles: no `.finally`, no `error` to render the Retry banner
    // with, and the tab sits on a spinner it cannot leave (pull-to-refresh
    // bypasses the gate, but is undiscoverable under a spinner). Before this
    // gate existed that user got a board. Releasing early fails OPEN —
    // slateTeams() returns null for an empty slate, so the read is the
    // whole-league one, which is exactly master's behaviour.
    const release = setTimeout(() => {
      if (!cancelled) setSlateFor(sport);
    }, SLATE_GATE_MS);
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
      })
      .finally(() => {
        if (!cancelled) setSlateFor(sport);
      });
    return () => {
      cancelled = true;
      clearTimeout(release);
    };
  }, [sport]);

  // Team stats for the defence grade. Only fetched where it is actually used,
  // so the sports that already grade off a matchup view pay nothing for it.
  useEffect(() => {
    if (!gradesOnDefence(sport)) {
      setTeamStats({ season: null, rows: [] });
      return;
    }
    let cancelled = false;
    fetchTeamStats(sport, SEASON)
      .then((res) => {
        if (!cancelled) setTeamStats(res);
      })
      .catch(() => {
        if (!cancelled) setTeamStats({ season: null, rows: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [sport]);

  const matchupByTeam = useMemo(() => buildMatchupMap(matchups), [matchups]);
  const defenceByTeam = useMemo(() => {
    const m = new Map<string, TeamStatsRow>();
    for (const r of teamStats.rows) if (r.team) m.set(r.team, r);
    return m;
  }, [teamStats]);
  /** The season the defence grade is computed from — named on screen, never assumed. */
  const defenceSeason = teamStats.season;

  // ── The GAMES cut, shared with the Picks tab ───────────────────────────────
  // One selection across both tabs (Matt, 2026-09-09), so picking tonight's
  // SEA-NE here narrows the picks list to the same two teams and their bets.
  const gamePicker = useGameSelection(sport);
  const pickableGames = useMemo(
    () => selectableGames(slateGames, sport, todayET()),
    [slateGames, sport],
  );
  // THE ONLY PLACE THE SELECTION IS PRUNED, because this is the only read that
  // sees the whole forward window (`slateGames`, seven days). The Picks tab
  // deliberately does not: its list is just the games with picks in the current
  // view, and pruning against that would intersect the shared selection to
  // nothing — see the note there.
  //
  // A selection outlives the games it was made from — the day rolls over, a
  // game leaves the window — and a stale id filters the board to nothing while
  // every control still says a game is picked. Prune to "All games", which is
  // wrong in the harmless direction.
  //
  // Depends on the VALUES, not on `gamePicker`: the hook returns a fresh object
  // literal every render, so naming it here re-ran this effect on every render.
  const replaceGames = gamePicker.replace;
  const selectedGameIds = gamePicker.selected;
  useEffect(() => {
    if (pickableGames.length === 0) return;
    const pruned = pruneSelection(selectedGameIds, pickableGames);
    if (pruned !== selectedGameIds) replaceGames(pruned);
  }, [pickableGames, selectedGameIds, replaceGames]);
  /** The picked games as TEAMS — leaderboard rows carry a team, never a game. */
  /** A specific game is picked, so the slate chip no longer applies. */
  const gamesPicked = gamePicker.selected.size > 0;
  const gameTeams = useMemo(
    () => selectedTeams(pickableGames, gamePicker.selected),
    [pickableGames, gamePicker.selected],
  );
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

  // The teams the server should narrow the read to — null when the board is
  // showing the whole league, or when the sport's slate keys are not teams
  // (UFC). Client-side `isOnSlate` still runs over what comes back, so the two
  // can never disagree about what is on screen; this only bounds what travels.
  const readTeams = useMemo(
    // A picked game is a NARROWER slate, so it wins: reading two teams when
    // the user asked for one game is the same waste the slate narrowing
    // exists to remove, one level down.
    () => gameTeams ?? slateTeams(sport, slate, tonightActive),
    [gameTeams, sport, slate, tonightActive],
  );
  // Array identity changes on every slate render; the loader keys on the
  // CONTENT so an unchanged slate does not refetch the board. JSON and not a
  // join: an NCAAF team id is a school NAME, and a separator that can occur
  // inside one collapses two different slates onto the same key.
  const readTeamsKey = readTeams ? JSON.stringify(readTeams.slice().sort()) : '';

  // WHAT THE ROWS ON SCREEN ARE AN ANSWER TO. A read is now up to several
  // sequential requests instead of one, so the window in which a stale response
  // can land on a board the user has already left is 10-50x wider than it was.
  // Two things key on this: `load` drops every setState whose stamp is no longer
  // current (so NCAAF rows cannot be painted under NFL stat labels, and an error
  // banner cannot appear for a sport the user left), and the list shows a
  // placeholder rather than rows it knows belong to a different question.
  const readKey = `${sport}|${playerType ?? ''}|${timeWindow}|${effectiveMode}|${seasonStatKey ?? ''}|${readTeamsKey}`;
  const inFlight = useRef<string | null>(null);
  const [shownKey, setShownKey] = useState<string | null>(null);
  /** The rows on screen answer a question the user has since changed. */
  const rowsAreStale = shownKey !== null && shownKey !== readKey;

  const load = useCallback(async () => {
    const stamp = readKey;
    inFlight.current = stamp;
    setLoading(true);
    setError(null);
    try {
      if (!stat) {
        setRows([]);
        setRecentRows([]);
        setSeasonValues({ statKey: '', rows: [] });
        return;
      }
      const teams = readTeams;
      if (effectiveMode === 'hitRate') {
        if (timeWindow === 'season') {
          const key = String(stat.key);
          const data = await fetchSeasonStatValues(sport, SEASON, key, playerType, teams);
          if (inFlight.current !== stamp) return;
          setSeasonValues({ statKey: key, rows: data });
        } else {
          const data = await fetchRecentGames(sport, SEASON, timeWindow, playerType, teams);
          if (inFlight.current !== stamp) return;
          setRecentRows(data);
        }
      } else {
        const win = timeWindow === 'season' ? null : timeWindow;
        const data = await fetchWindowTotals(sport, SEASON, win, playerType, teams);
        if (inFlight.current !== stamp) return;
        setRows(data);
      }
      setShownKey(stamp);
    } catch (e: unknown) {
      if (inFlight.current !== stamp) return;
      setError(errorText(e));
    } finally {
      if (inFlight.current === stamp) setLoading(false);
    }
    // `readTeamsKey` and not `readTeams`: see above. `readKey` carries the rest.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sport, playerType, timeWindow, effectiveMode, seasonStatKey, readTeamsKey]);

  useEffect(() => {
    if (slateFor !== sport) return; // the read is narrowed by THIS sport's slate
    void load();
  }, [load, slateFor, sport]);

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

  /**
   * How tough this row's spot is, whichever way the sport can answer it.
   *
   * MLB and WNBA have a matchup view (the probable starter, the opposing
   * lineup) and it stays the better answer where it exists. Everything else
   * grades the OPPONENT'S DEFENCE off the Teams-board read — before this the
   * column was a dash for every sport but those two, which is what made a
   * toughness filter meaningless on the board Matt was looking at.
   *
   * Null means "this sport cannot answer", and the column hides entirely.
   * A null GRADE inside a returned MatchupInfo means "this row cannot be
   * answered" — an unknown defence is a dash, never a C.
   */
  const matchupFor = useCallback(
    (row: { team?: string | null; player_name?: string | null }): MatchupInfo | null => {
      const m = row.team ? matchupByTeam.get(row.team) : undefined;
      if (m) return gradeMatchup(sport, playerType, m);
      if (!gradesOnDefence(sport)) return null;
      const match = slateGameFor(row, slateGameIndex);
      const opponent = match?.game.opponent ?? null;
      const opp = opponent ? defenceByTeam.get(opponent) ?? null : null;
      return gradeOpponentDefence(
        sport,
        opp as unknown as Record<string, unknown> | null,
        opponent,
        defenceSeason,
      );
    },
    [matchupByTeam, sport, playerType, slateGameIndex, defenceByTeam, defenceSeason],
  );

  /** Does the column have anything to say for this sport at all? */
  const showMatchupCol = matchupByTeam.size > 0 || (gradesOnDefence(sport) && defenceByTeam.size > 0);

  /**
   * The GRADE column's legend, per sport and naming the season it graded on.
   *
   * It has to be per sport because the column now answers the same question
   * three different ways, and it has to name the season because the football
   * grade reads from LAST season until the new one has games in it — a
   * tooltip asserting "this season" over 2025 numbers is the column lying in
   * the one place it explains itself.
   */
  const matchupTooltip = useMemo(() => {
    const seasonWords = defenceSeason != null ? `the ${defenceSeason} season` : 'the season so far';
    const head =
      'How hard tonight\u2019s spot is for this player, graded against the rest of ' +
      'the league. A+ is the easiest matchup on the board and F the hardest.';
    const how = gradesOnDefence(sport)
      ? `Graded on ${defenceMetricSpoken(sport)} for the team this player faces, over ${seasonWords}.`
      : 'Batters are graded on the opposing starter\u2019s ERA, pitchers on the ' +
        'opposing lineup\u2019s wOBA and strikeout rate, and WNBA players on the ' +
        'opposing defence\u2019s rating.';
    const dash = gradesOnDefence(sport)
      ? 'A dash means we have no matchup data for this row yet \u2014 no game ' +
        'tonight, or nothing on file for the opponent. An unknown matchup is ' +
        'never graded as average.'
      : 'A dash means the starter isn\u2019t confirmed yet \u2014 an unknown matchup ' +
        'is never graded as average.';
    return `${head}\n\n${how}\n\n${dash}`;
  }, [sport, defenceSeason]);

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
  //
  // THE NOTE NAMES THE LEAGUE, and that is not decoration. Until 2026-09-05 a
  // column unpriced here was unpriced everywhere, so a flat "no sportsbook
  // posts this" was true. Then college books turned out not to price carries
  // or sacks while the NFL prices both, and the same sentence about the same
  // word became something the user can disprove two taps away on the other
  // football board — which makes the APP look wrong rather than the market
  // look thin (UX review, 2026-09-05). Every sport gets the league word; it
  // costs the others nothing and it is true for all of them.
  //
  // And when the whole active GROUP is unpriced it is said once, about the
  // group. College defence is 0 of 6 after that same prune, so walking the
  // Defense chips otherwise produces six identical sentences, which is how a
  // reader learns to stop reading them.
  const groupUnpriced =
    stat != null &&
    statsForSport(sport)
      .filter((s) => s.group === stat.group)
      .every((s) => propMarketForStat(s) == null);
  const noLinesNote: { text: string; canSwitch: boolean } | null =
    propMarket == null
      ? stat != null && sportHasAnyPropMarket(sport)
        ? {
            text: groupUnpriced
              ? `No sportsbook posts ${sport} ${stat.group.toLowerCase()} lines.`
              : `No sportsbook posts ${sport} ${stat.label} lines.`,
            canSwitch: false,
          }
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

  const band = useMemo(() => hitRateBand(hitLow, hitHigh), [hitLow, hitHigh]);

  // ── Averages / Totals mode ranking ──
  const ranked = useMemo(() => {
    if (!stat || effectiveMode !== 'totals') return [];
    const q = query.trim().toLowerCase();
    return rows
      .filter((r) => isStatParticipant(sport, [statValue(r, stat)]))
      .filter((r) => !teamFilter || r.team === teamFilter)
      .filter((r) => !tonightActive || gamesPicked || isOnSlate(r, slate))
      .filter((r) => !gameTeams || (!!r.team && gameTeams.includes(r.team)))
      .filter((r) => !minGrade || meetsGradeFloor(matchupFor(r)?.grade, minGrade, includeUngraded))
      .filter((r) => !q || (r.player_name ?? '').toLowerCase().includes(q))
      .map((r) => {
        const total = statValue(r, stat);
        const gp = r.games_played || 0;
        const value = basis === 'perGame' && gp > 0 ? total / gp : total;
        return { row: r, value, total, gp };
      })
      .sort((a, b) =>
        compareRows({ primary: a.value, games: a.gp }, { primary: b.value, games: b.gp }),
      );
  }, [rows, stat, sport, basis, query, teamFilter, effectiveMode, tonightActive, gamesPicked, slate, gameTeams, minGrade, includeUngraded, matchupFor]);

  // ── Hit Rate mode: count games over/under the line per player. Last-N mode
  // groups the raw rows client-side; Season mode reads the per-player value
  // arrays from player_season_stat_values_* (values newest-first, nulls already
  // excluded server-side), so the line ruler stays instant either way. ──
  // Split in two ON PURPOSE (UX review, 2026-09-12). Everything expensive —
  // grouping every fetched game row by player, computing hit rates, and the
  // sort — is keyed on everything EXCEPT the band, because the band is now
  // dragged: a single gesture steps it up to twenty times, and these boards
  // run to tens of thousands of rows. The band is a filter over the finished,
  // already-sorted list (a filter preserves order), so a drag costs one pass.
  const hitRateBase = useMemo<HitRatePlayer[]>(() => {
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
      .filter((p) => !teamFilter || p.team === teamFilter)
      .filter((p) => !tonightActive || gamesPicked || isOnSlate(p, slate))
      .filter((p) => !gameTeams || (!!p.team && gameTeams.includes(p.team)))
      .filter((p) => !minGrade || meetsGradeFloor(matchupFor(p)?.grade, minGrade, includeUngraded))
      .filter((p) => !q || p.player_name.toLowerCase().includes(q))
      .sort((a, b) =>
        compareRows({ primary: a.pct, games: a.total }, { primary: b.pct, games: b.total }),
      );
  }, [recentRows, seasonValues, timeWindow, stat, sport, line, side, query, teamFilter, effectiveMode, tonightActive, gamesPicked, slate, gameTeams, minGrade, includeUngraded, matchupFor]);

  const hitRatePlayers = useMemo<HitRatePlayer[]>(
    () => hitRateBase.filter((p) => inHitRateBand(p.pct, band)),
    [hitRateBase, band],
  );

  // Does the hit-rate column span more than one colour band? A rare-event
  // column (Doubles, Triples, Home Runs) does not — every player lands in the
  // same band — and a whole column of one colour beside a live price reads as
  // a verdict on the bet rather than a ranking of players. Computed over what
  // is actually on screen, so the board never colours what it cannot
  // distinguish.
  /**
   * Does the GRADE column span more than one colour on what is rendered?
   *
   * Computed here, over the visible rows, for the same reason `colorful` is:
   * on a two-team NFL slate whose defences were both elite, every row grades
   * D- and the column paints one red block beside a live price. The letter
   * stays — it is true — and only the ramp goes quiet.
   */
  const gradesColorful = useMemo(() => {
    const rowsOnScreen: { team?: string | null; player_name?: string | null }[] =
      effectiveMode === 'hitRate' ? hitRatePlayers : ranked.map((r) => r.row);
    return gradeColorDiscriminates(
      rowsOnScreen.slice(0, 60).map((r) => matchupFor(r)?.grade ?? null),
    );
  }, [effectiveMode, hitRatePlayers, ranked, matchupFor]);

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
  const matchupParams = (row: { team?: string | null; player_name?: string | null }) => {
    const graded = matchupFor(row);
    if (!graded || !graded.text) return {};
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
      ...matchupParams(p),
    });
  };

  const groups = GROUP_ORDER[sport];
  const windowN = typeof timeWindow === 'number' ? timeWindow : 10;
  // The headline under the ruler, in the mode's own idiom: "25+ Points" in
  // At Least, "Over 0.5 Hits" in Over (lib/hitMode.ts).
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
    () =>
      lineSheet
        ? propLineSheetInput(lineSheet, sport, betLabel, lineHeadline, (l, sd) =>
            modeLineLabel(l, sd, hitMode),
          )
        : null,
    [lineSheet, sport, betLabel, lineHeadline, hitMode],
  );

  /**
   * One definition of "what the hit-rate band is set to", so the collapsed
   * sheet row and the removable pill can never describe it differently.
   */
  const bandSummary = useMemo(() => {
    const lo = Math.round(band.lo * 100);
    const hi = Math.round(band.hi * 100);
    // The thumbs are allowed to MEET, and the slider makes that a one-drag
    // routine where typing 60 into both fields never was. "60–60%" reads as a
    // rendering bug on all three surfaces this feeds. Phrased as "60% only"
    // rather than "Exactly 60%" because the pill composes `hit ${summary}`,
    // and a capital mid-phrase is the one thing this string cannot carry
    // (UX review, 2026-09-12).
    if (lo === hi) return `${lo}% only`;
    if (band.lo > 0 && band.hi < 1) return `${lo}–${hi}%`;
    if (band.hi < 1) return `≤ ${hi}%`;
    if (band.lo > 0) return `${lo}%+`;
    return 'Any';
  }, [band]);

  /** Is the hit-rate band narrowing the board right now? */
  const bandActive = band.lo > 0 || band.hi < 1;

  /** Back to "Any". The pill, the section's own Clear and the reset all use it. */
  const clearBand = useCallback(() => {
    setHitLow(HIT_RATE_MIN);
    setHitHigh(HIT_RATE_MAX);
  }, []);

  // Count filters the user has changed away from defaults, for the trigger badge.
  // Only counts what still lives in the modal — the front-page controls are visible.
  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (teamFilter) n += 1;
    if (gamePicker.selected.size > 0) n += 1;
    if (minGrade) n += 1;
    if (minGrade && !includeUngraded) n += 1;
    if (query.trim()) n += 1;
    if (effectiveMode === 'hitRate') {
      if (bandActive) n += 1;
    } else if (basis !== 'perGame') {
      n += 1;
    }
    return n;
  }, [teamFilter, gamePicker.selected, minGrade, includeUngraded, query, effectiveMode, bandActive, basis]);

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
    clearBand();
    setTonightOnly(false);
    setMinGrade(null);
    setIncludeUngraded(true);
    gamePicker.clear();
  }, [gamePicker, clearBand]);

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
    if (gamePicker.selected.size > 0) {
      out.push({
        key: 'games',
        label: gameFilterSummary(pickableGames, gamePicker.selected),
        onRemove: () => gamePicker.clear(),
      });
    }
    if (minGrade) {
      out.push({
        key: 'grade',
        label: `${minGrade} or better${includeUngraded ? '' : ', graded only'}`,
        onRemove: () => {
          setMinGrade(null);
          setIncludeUngraded(true);
        },
      });
    }
    if (tonightActive && !gamesPicked) {
      out.push({ key: 'tonight', label: slateLabel, onRemove: () => setTonightOnly(false) });
    }
    if (effectiveMode === 'hitRate') {
      if (bandActive) {
        out.push({ key: 'hitBand', label: `hit ${bandSummary}`, onRemove: clearBand });
      }
    } else if (basis !== 'perGame') {
      out.push({ key: 'basis', label: 'Totals', onRemove: () => setBasis('perGame') });
    }
    return out;
  }, [teamFilter, query, tonightActive, gamesPicked, slateLabel, effectiveMode, bandActive, bandSummary,
      basis, clearBand, gamePicker, pickableGames, minGrade, includeUngraded]);

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

  // Sports with no per-player leaderboard (NHL: team+goalie only).
  // The golf branch went with the sport on 2026-09-08: its copy promised
  // leaderboards that are not coming and pointed at Picks/Signals for golf picks
  // that no longer render, and GOLF is no longer a chip, so it was unreachable
  // copy that could only ever mislead.
  if (!stat) {
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
          title="No player leaderboard"
          subtitle={`Player stat leaderboards aren't available for ${sport} yet.`}
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
              // Not "Show bets that are": this control survives on a column
              // with no line at all (NCAAF carries, sacks), where it is the
              // only place left that would still say "bets" (UX review,
              // 2026-09-05). The threshold is what it actually sets, priced
              // or not.
              accessibilityLabel="Threshold direction"
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
            {/* Every mode resolves a stop to the SAME half-point line — only
                the face differs — so a mode change renames the bet without
                moving it (lib/hitMode.ts). The stops are not quite the same
                SET, though: Under n names "n-1 or fewer", so it needs one
                extra to reach the ceiling At Least and Over both express at
                maxLineN. Without it "10 or fewer Hits" is unsayable while
                "10+ Hits" is (UX review, 2026-09-06). */}
            <LineRuler
              value={lineN}
              min={1}
              max={maxLineN(stat) + (hitMode === 'under' ? 1 : 0)}
              onChange={setLineN}
              format={(n) => rulerValueLabel(n, hitMode)}
              describe={(n) => hitModeHeadline(n, hitMode, stat?.label ?? '')}
              a11yLabel={`${stat?.label ?? ''} line`}
            />
          </View>
          <View style={styles.headlineRow}>
            <View style={styles.headlineRule} />
            <Text style={styles.headlineText}>{lineHeadline}</Text>
            {/* At Least only. Its headline is the fan's idiom — "2+ Hits" —
                so the book's number for the same bet would otherwise be
                nowhere on screen (UX review, 2026-09-05). Over and Under ARE
                that number now, and repeating it beside itself is noise
                (Matt, 2026-09-06). */}
            {hitMode === 'atLeast' ? (
              <Text style={styles.headlineLine}>{hitModeLineLabel(lineN, hitMode)}</Text>
            ) : null}
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
            {/* This chip re-READS the board now (the server is narrowed to the
                slate's teams), so it is the one chip on the row whose tap is
                not instant. Two consequences, both handled here rather than
                left to the list: a second impatient tap must not queue a
                second whole-league read, and VoiceOver has to be told that
                something is happening — focus stays on the chip while the
                rows underneath it change silently. */}
            <FilterChip
              label={slateLabel}
              icon="flame-outline"
              active={tonightActive && !gamesPicked}
              busy={loading}
              // MUTED, NOT REMOVED, while a specific game is picked. The two
              // are not the same cut — the chip is one slate date, the Games
              // list is a seven-day window — so with both on you get their
              // INTERSECTION, which on a Sunday game with "Next slate" showing
              // is an empty board and two pills each claiming to be on (UX
              // review, 2026-09-09). The narrower one wins and says so.
              disabled={gamesPicked}
              accessibilityLabel={
                gamesPicked
                  ? `${slateLabel}, off while a game is picked`
                  : loading
                    ? `${slateLabel}, loading`
                    : tonightActive
                      ? `${slateLabel}, on. Turn off to show every player`
                      : `${slateLabel}, off`
              }
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
          showMatchup={showMatchupCol}
          matchupTooltip={matchupTooltip}
        />
      ) : null}

      {effectiveMode === 'hitRate' ? (
        <FlatList
          data={rowsAreStale ? EMPTY_ROWS : hitRatePlayers}
          keyExtractor={(item) => item.player_id}
          renderItem={({ item, index }) => {
            const quote = quoteFor(item);
            return (
              <HitRateRow
                rank={index + 1}
                player={item}
                matchup={matchupFor(item)}
                showMatchup={showMatchupCol}
                gradeColorful={gradesColorful}
                subline={sublineFor(item)}
                quote={quote}
                started={item.team ? startedTeams.get(item.team) ?? null : null}
                showOdds={showOdds}
                statLabel={betLabel}
                hitMode={hitMode}
                colorful={colorful}
                onOddsPress={quote ? () => openBook(quote) : undefined}
                tappable={playerDetail}
                onPress={() => openPlayer(item)}
              />
            );
          }}
          ListEmptyComponent={
            loading ? (
              <BoardSkeleton />
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
          data={rowsAreStale ? EMPTY_ROWS : ranked}
          keyExtractor={(item) => item.row.player_id}
          renderItem={({ item, index }) => {
            const quote = quoteFor(item.row);
            return (
              <LeaderRow
                rank={index + 1}
                row={item.row}
                value={item.value}
                gp={item.gp}
                basis={basis}
                matchup={matchupFor(item.row)}
                showMatchup={showMatchupCol}
                gradeColorful={gradesColorful}
                subline={sublineFor(item.row)}
                quote={quote}
                started={item.row.team ? startedTeams.get(item.row.team) ?? null : null}
                showOdds={showOdds}
                statLabel={betLabel}
                hitMode={hitMode}
                onOddsPress={quote ? () => openBook(quote) : undefined}
                tappable={playerDetail}
                onPress={() => openPlayer(item.row)}
              />
            );
          }}
          ListEmptyComponent={
            loading ? (
              <BoardSkeleton />
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
        {/* GAMES first, because it is the widest cut on the sheet and the one
            Matt asked for by name. Shared with the Picks tab, so a game picked
            here is the same game picked there. */}
        <FilterSection
          title="Games"
          summary={gameFilterSummary(pickableGames, gamePicker.selected)}
          defaultOpen={gamePicker.selected.size > 0}
          onClear={gamePicker.selected.size > 0 ? gamePicker.clear : undefined}
        >
          <GameFilterSection
            games={pickableGames}
            selected={gamePicker.selected}
            onToggle={gamePicker.toggle}
            emptyNote={
              sport === 'UFC'
                ? 'A UFC card is fighters, not fixtures — filter by fighter with the search above.'
                : `No ${sport} games scheduled in the next week.`
            }
          />
        </FilterSection>

        {/* TOUGHNESS. Only where the sport can answer it — a control over a
            column of dashes is a filter that silently does nothing. */}
        {showMatchupCol ? (
          <FilterSection
            title="Matchup grade"
            // The comparison is stated once, here, so the chip, this summary
            // and the pill all say the same thing. The chips were labelled
            // "A+" and set floor 'A' — ambiguous on a scale where A+ is a real
            // grade, and a second name for one setting (UX review).
            subtitle="How soft the defence is, at or above the grade you pick. A is the easiest spot on the board."
            summary={minGrade ? `${minGrade} or better` : 'Any matchup'}
            defaultOpen={minGrade != null}
            onClear={minGrade ? () => { setMinGrade(null); setIncludeUngraded(true); } : undefined}
          >
            <View style={styles.chipWrap}>
              <FilterChip
                label="Any"
                active={minGrade == null}
                onPress={() => setMinGrade(null)}
              />
              {GRADE_FLOORS.map((g) => (
                <FilterChip
                  key={g}
                  label={g}
                  active={minGrade === g}
                  accessibilityLabel={`${gradeSpoken(g)} or better`}
                  onPress={() => setMinGrade(minGrade === g ? null : g)}
                />
              ))}
            </View>
            {/* A dash is "no rating for that defence", not "a bad spot" — and
                on a college Saturday those rows are the FCS visitors, the
                softest spots there are. Included by default; the switch is for
                anyone who wants only rows we can vouch for. */}
            {minGrade ? (
              <View style={styles.ungradedRow}>
                <Text style={styles.ungradedLabel}>Include ungraded matchups</Text>
                <Switch
                  value={includeUngraded}
                  onValueChange={setIncludeUngraded}
                  accessibilityLabel="Include players whose matchup has no grade"
                />
              </View>
            ) : null}
          </FilterSection>
        ) : null}

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

        {/* Hit-rate band — the reason someone opens this sheet is usually
            "show me the 70%+ guys", so the presets come before the slider. */}
        {effectiveMode === 'hitRate' ? (
          <FilterSection
            title="Hit rate"
            subtitle="Only show players inside this band."
            summary={bandSummary}
            // Every other narrowing section on this sheet carries its own
            // Clear. The band needs it MORE than they do now the fields are
            // gone: emptying two text boxes used to be the way back to "Any",
            // and "Clear all" also wipes Games, Matchup, Search and Team.
            onClear={bandActive ? clearBand : undefined}
            // A sheet that opens collapsed hides the control that produced the
            // band the row is reporting (UX review, 2026-09-12).
            defaultOpen={bandActive}
          >
            <View style={styles.chipWrap}>
              {HIT_RATE_PRESETS.map((p) => {
                const on = hitLow === p && hitHigh === HIT_RATE_MAX;
                return (
                  <FilterChip
                    key={p}
                    label={`${p}%+`}
                    active={on}
                    onPress={() => {
                      setHitLow(on ? HIT_RATE_MIN : p);
                      setHitHigh(HIT_RATE_MAX);
                    }}
                  />
                );
              })}
            </View>
            {/* The band is DRAGGED, not typed (Matt, 2026-09-12). The two
                number fields this replaced raised the keyboard over the
                sheet's own result count — the feedback the whole live-editing
                sheet is built on — to answer a question that is one gesture. */}
            <View style={styles.sliderWrap}>
              <RangeSlider
                min={HIT_RATE_MIN}
                max={HIT_RATE_MAX}
                step={HIT_RATE_STEP}
                low={hitLow}
                high={hitHigh}
                onChange={(lo, hi) => {
                  setHitLow(lo);
                  setHitHigh(hi);
                }}
                format={(v) => `${v}%`}
                lowLabel="Minimum hit rate"
                highLabel="Maximum hit rate"
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
  format,
  describe,
  a11yLabel,
}: {
  a11yLabel: string;
  /** The ruler's STOP INDEX. What the user sees is `format(value)`. */
  value: number;
  min: number;
  max: number;
  onChange: (n: number) => void;
  /** The stop drawn in the caller's units — the mode's idiom on the stat
   *  board, where Over reads 0.5 where At Least reads 1 (lib/hitMode.ts).
   *  Snapping stays on the integer stop either way, so a scroll offset still
   *  divides cleanly. */
  format?: (n: number) => string;
  /** The whole bet at that stop, for VoiceOver — "Over 0.5 Hits". Defaults to
   *  the face. */
  describe?: (n: number) => string;
}) {
  const [width, setWidth] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const reportedRef = useRef(value);
  const count = Math.max(1, max - min + 1);
  // Short rulers (hits, Ks) get wide ticks with every value labeled — the old
  // look, now scrollable. Long rulers (points, yards) get dense ticks with
  // labels every 5th/10th value so the strip stays legible and flickable.
  const faceOf = format ?? String;
  // The pitch follows the FACE, not the count: an Over/Under face carries a
  // decimal ("23.5" against "23"), and at the old fixed 26 the labels on a
  // short ruler abutted with about a point of air — one run of digits at
  // default Dynamic Type, overlapping above it — while the opaque centre pill
  // grew wide enough to cover its neighbours (UX review, 2026-09-06).
  const describeOf = describe ?? faceOf;
  const faceChars = Math.max(faceOf(min).length, faceOf(max).length);
  const tickW = count <= 30 ? Math.max(26, faceChars * 8 + 6) : TICK_W;
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
      // `text` overrides `now` for VoiceOver, which is the point: the stop
      // index is meaningless to a user, and in Over mode the face is 0.5
      // where the index is 1. It announces the whole BET rather than the bare
      // face, because the side and the stat live on other elements and this is
      // the one element a screen-reader user actually drives (UX review).
      accessibilityValue={{ min, max, now: value, text: describeOf(value) }}
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
                  {labeled ? faceOf(v) : ''}
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
          <Text style={styles.tickValueActive}>{faceOf(value)}</Text>
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
/** The book's own number for the line IT posts, in the idiom the board is
 *  speaking — "3+" in At Least, "O 2.5" in Over/Under. Abbreviated because
 *  this sits in a 62pt column: "Under 224.5" wrapped to two lines and made one
 *  row of a 25-row board taller than its neighbours (UX review, 2026-09-06).
 *  The pill's accessibilityLabel keeps the full words. */
export function offLineCaption(line: number, side: StatsOddsSide, mode: HitMode): string {
  return modeLineLabel(line, side, mode, true);
}

function OddsCell({
  quote,
  started,
  playerName,
  statLabel,
  hitMode,
  onPress,
}: {
  quote: StatsOddsQuote | null;
  started?: 'Live' | 'Final' | null;
  playerName: string;
  statLabel: string;
  /** Which idiom the board is speaking, for the off-line caption. */
  hitMode: HitMode;
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
  // price in whichever idiom the header is speaking — "3+" in At Least, the
  // book's own "O 2.5" in Over/Under — so it reads against the header without
  // translation (UX review). statsOdds offLine.
  const caption = quote.offLine ? offLineCaption(quote.line, quote.side, hitMode) : null;
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
      {caption ? (
        <Text style={styles.oddsCaption} numberOfLines={1}>
          {caption}
        </Text>
      ) : null}
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
function MatchupCell({
  matchup,
  colorful = true,
}: {
  matchup: MatchupInfo | null;
  /**
   * False when every visible row lands in the same colour band — the letter is
   * still right, but a whole column of one colour beside a live price reads as
   * a verdict on the bet rather than a ranking of players (the same rule
   * `colorful` applies to the hit-rate column).
   */
  colorful?: boolean;
}) {
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
      <Text
        style={[
          styles.matchupGrade,
          { color: colorful ? gradeColor(matchup.grade) : colors.textPrimary },
        ]}
        numberOfLines={1}
      >
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
  matchupTooltip,
}: {
  rightLabel: string;
  showOdds: boolean;
  /** Short name of the book the column prints ("FD", "DK"). */
  oddsLabel: string;
  /** Weekday of the slate the prices are for, when it is not today. */
  oddsDateLabel?: string | null;
  showMatchup: boolean;
  matchupTooltip: string;
}) {
  return (
    <View style={styles.colHeader}>
      <Text style={styles.colHeaderRank}>RK</Text>
      <Text style={styles.colHeaderName}>PLAYER</Text>
      {/* The arrow is the board's only statement of its own order now the
          sort picker is gone — the removable "by games played" pill used to be
          the one place it was written down (UX review, 2026-09-12). It is an
          indicator, not a control: the order is fixed.

          It is a SIBLING of the label, not part of its string: the cell is a
          fixed 48pt box with `numberOfLines={1}`, so an arrow appended inside
          it is the first glyph the ellipsis eats — and `rightLabel` in
          Averages mode is the stat's own name ("PASSING YARDS"), which
          overflows that box on its own. The label shrinks; the arrow does
          not. */}
      <View
        style={styles.colHeaderSorted}
        accessibilityLabel={`${rightLabel}, sorted highest first`}
      >
        <Text style={[styles.colHeaderRight, styles.colHeaderSortLabel]} numberOfLines={1}>
          {rightLabel.toUpperCase()}
        </Text>
        <Ionicons name="arrow-down" size={9} color={colors.textTertiary} />
      </View>
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
          {/* The column's only legend, so it has to describe the grade the
              reader is ACTUALLY looking at. It named the two baseball answers
              alone and asserted "this season" -- both wrong for the three
              sports now graded on defence, whose numbers come from the season
              this text names, which on opening night is LAST season (UX
              review, 2026-09-09). */}
          <InfoTooltip
            title="Matchup grade"
            body={matchupTooltip}
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
  gradeColorful,
  subline,
  quote,
  started,
  showOdds,
  statLabel,
  hitMode,
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
  /** False when every visible grade lands in one colour band. */
  gradeColorful?: boolean;
  /** "9:40 PM ET · @ SEA" under the name; null when the row has no game. */
  subline: string | null;
  quote: StatsOddsQuote | null;
  /** The player's game is live or over: no line, and the cell says which. */
  started: 'Live' | 'Final' | null;
  showOdds: boolean;
  statLabel: string;
  /** Passed through to the odds cell's off-line caption. */
  hitMode: HitMode;
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
          hitMode={hitMode}
          onPress={onOddsPress}
        />
      ) : null}
      {showMatchup ? <MatchupCell matchup={matchup} colorful={gradeColorful} /> : null}
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
  gradeColorful,
  subline,
  quote,
  started,
  showOdds,
  statLabel,
  hitMode,
  colorful,
  onOddsPress,
  tappable,
  onPress,
}: {
  rank: number;
  player: HitRatePlayer;
  matchup: MatchupInfo | null;
  showMatchup: boolean;
  /** False when every visible grade lands in one colour band. */
  gradeColorful?: boolean;
  /** "9:40 PM ET · @ SEA" under the name; null when the row has no game. */
  subline: string | null;
  quote: StatsOddsQuote | null;
  /** Does the hit-rate column span more than one band? Colour only if so. */
  colorful: boolean;
  /** The player's game is live or over: no line, and the cell says which. */
  started: 'Live' | 'Final' | null;
  showOdds: boolean;
  statLabel: string;
  /** Passed through to the odds cell's off-line caption. */
  hitMode: HitMode;
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
          hitMode={hitMode}
          onPress={onOddsPress}
        />
      ) : null}
      {showMatchup ? <MatchupCell matchup={matchup} colorful={gradeColorful} /> : null}
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
  // Breathing room under the preset chips; the slider brings its own
  // read-out and end labels.
  sliderWrap: {
    marginTop: spacing.md,
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
  ungradedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  ungradedLabel: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textPrimary,
  },
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
  // The sorted column: label + a fixed arrow, in one 48pt cell.
  colHeaderSorted: {
    width: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 2,
  },
  // Inside the row the label gives up its own fixed width and shrinks instead,
  // so the arrow beside it can never be truncated away.
  colHeaderSortLabel: { width: undefined, flexShrink: 1 },
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
  skeletonWrap: { paddingTop: spacing.xs },
  skeletonRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  skeletonBlock: {
    height: 10,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
  },
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

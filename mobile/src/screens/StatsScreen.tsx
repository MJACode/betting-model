import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { NativeScrollEvent, NativeSyntheticEvent } from 'react-native';
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
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { CompositeNavigationProp, RouteProp } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { PlayerOddsSheet } from '@/components/PlayerOddsSheet';
import { showToast } from '@/components/Toast';
import { SportToggle } from '@/components/SportToggle';
import { TeamsBoard } from '@/components/TeamsBoard';
import { SettingsButton } from '@/components/SettingsButton';
import { FilterChip } from '@/components/filters/FilterChip';
import { FilterField } from '@/components/filters/FilterField';
import { FilterSection, FilterSheet } from '@/components/filters/FilterSheet';
import type { ActivePill } from '@/components/filters/FilterBar';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import {
  fetchRecentGames,
  fetchSeasonStatValues,
  fetchSlateGames,
  fetchTonightMatchups,
  fetchWindowTotals,
} from '@/lib/queries';
import { computeHitRate, type HitDirection } from '@/lib/hitRate';
import { supportsPlayerDetail } from '@/lib/playerLog';
import { buildMatchupMap, gradeMatchup, type MatchupInfo } from '@/lib/matchup';
import { addDays, formatAmerican, todayET } from '@/lib/format';
import {
  EMPTY_SLATE,
  HIT_RATE_PRESETS,
  autoMinGames,
  buildTonightSlate,
  compareRows,
  hitRateBand,
  inHitRateBand,
  isOnSlate,
  isStatParticipant,
  maxGamesIn,
  sortLabel,
  sortOptionsFor,
  type SortKey,
  type TonightSlate,
} from '@/lib/statsBoard';
import {
  GROUP_ORDER,
  defaultStatFor,
  defaultThresholdFor,
  propModelForStat,
  statValue,
  statsForSport,
  supportsHitRate,
  type StatDef,
} from '@/lib/statCatalog';
import { supportsTeamBoard } from '@/lib/teamStatCatalog';
import { colors, font, radii, spacing } from '@/lib/theme';
import type {
  EnrichedPick,
  GameRow,
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
type Mode = 'totals' | 'hitRate';
// Last-N-games window. 'season' = whole season (null window on the totals RPC;
// the player_season_stat_values_* RPCs in Hit Rate mode).
type TimeWindow = 3 | 5 | 10 | 15 | 20 | 'season';

// The odds pill on a row is backed by that player's full EnrichedPick (today's
// prop pick for the selected stat) — tapping it opens the odds sheet.

const SEASON = new Date().getUTCFullYear();
const PER_GAME_MIN = 5; // qualifier when ranking by per-game rate
const AMBER = '#FF9500'; // mid-tier hit rate (no theme token)

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

function hitRateColor(pct: number): string {
  if (pct >= 0.6) return colors.bet;
  if (pct >= 0.4) return AMBER;
  return colors.avoid;
}

/**
 * The integer threshold shown on the ruler for a stat, e.g. "1+ Hits",
 * "6+ Strikeouts". Stat defaults are half-lines (0.5 / 5.5) so the ceiling is
 * the first whole number that clears them.
 */
function defaultLineN(def: StatDef | null): number {
  return Math.max(1, Math.ceil(defaultThresholdFor(def)));
}

/** Upper bound of the ruler — generous enough to cover league leaders. */
function maxLineN(def: StatDef | null): number {
  return Math.max(10, defaultLineN(def) * 3);
}

/**
 * Ruler value → the continuous line the hit-rate math uses.
 *   at least N  →  value > N-0.5  ⇔  value >= N
 *   at most  N  →  value < N+0.5  ⇔  value <= N
 */
function lineFor(n: number, direction: HitDirection): number {
  return direction === 'over' ? n - 0.5 : n + 0.5;
}

export function StatsScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<StatsRoute>();
  const { sport } = useSportFilter();
  // Today's board — hangs a live price off each leaderboard row, and backs the
  // player odds sheet (all-books prices + add-to-betslip) behind the odds pill.
  const { data: todayPicks } = useTodayPicks();
  // The user came from the betslip to find a leg — banner + auto-return.
  const fromParlay = route.params?.fromParlay === true;
  const [oddsSheet, setOddsSheet] = useState<{ ep: EnrichedPick; name: string } | null>(null);

  const [stat, setStat] = useState<StatDef | null>(() => defaultStatFor(sport));
  const [mode, setMode] = useState<Mode>('hitRate');
  const [basis, setBasis] = useState<Basis>('perGame');
  const [timeWindow, setTimeWindow] = useState<TimeWindow>(10);
  // Blank = the auto qualifier (a share of the pool leader's games — see
  // statsBoard.autoMinGames). Typing a number pins it.
  const [minGames, setMinGames] = useState<string>('');
  const [query, setQuery] = useState<string>('');
  const [teamFilter, setTeamFilter] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('default');
  // Hit Rate controls (front page): integer line + at least / at most.
  const [lineN, setLineN] = useState<number>(() => defaultLineN(defaultStatFor(sport)));
  const [direction, setDirection] = useState<HitDirection>('over');
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
  const [tonightOnly, setTonightOnly] = useState<boolean>(false);
  const [slate, setSlate] = useState<TonightSlate>(EMPTY_SLATE);
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
    setTonightOnly(false); // a different sport is a different slate
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
        if (!cancelled) setSlate(buildTonightSlate(games, sport, from));
      })
      .catch(() => {
        if (!cancelled) setSlate(EMPTY_SLATE);
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
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [sport, playerType, timeWindow, effectiveMode, seasonStatKey]);

  useEffect(() => {
    void load();
  }, [load]);

  // Per-game ranking needs its own floor; that now lives in effectiveMinGames
  // so it composes with the auto qualifier instead of overwriting the field.
  const toggleBasis = (next: Basis) => setBasis(next);

  // Each stat carries its own sensible line — snap the ruler back on switch.
  const pickStat = (s: StatDef) => {
    setStat(s);
    setLineN(defaultLineN(s));
  };

  const line = useMemo(() => lineFor(lineN, direction), [lineN, direction]);

  // Live prop pick per player for the selected stat's market, so the board
  // shows what the number is actually priced at today — and tapping the pill
  // opens the odds sheet (every book's price + add-to-betslip). Empty when the
  // stat has no prop model or the market isn't listed. BET rows win over
  // dead-zone rows.
  const propModel = propModelForStat(stat);
  const oddsByPlayer = useMemo(() => {
    const map = new Map<string, EnrichedPick>();
    if (!propModel) return map;
    for (const ep of todayPicks) {
      const p = ep.pick;
      if (p.model_id !== propModel || !p.player_id || p.dk_odds == null) continue;
      const existing = map.get(p.player_id);
      if (existing && p.signal_type !== 'BET') continue;
      map.set(p.player_id, ep);
    }
    return map;
  }, [todayPicks, propModel]);
  const showOdds = oddsByPlayer.size > 0;

  // Odds-sheet plumbing. Adding a leg while on the betslip round-trip bounces
  // the user straight back to their slip (the session-53 flow, restored).
  const openOddsSheet = useCallback((ep: EnrichedPick, name: string) => {
    setOddsSheet({ ep, name });
  }, []);
  const handleSheetAdded = useCallback(() => {
    setOddsSheet(null);
    if (fromParlay) {
      navigation.setParams({ fromParlay: undefined });
      navigation.navigate('Betslip');
    } else {
      showToast('Added · tap the betslip bar at the bottom to open it');
    }
  }, [fromParlay, navigation]);

  /**
   * Games played by the busiest player in the loaded pool — the scale the auto
   * qualifier is a share of. Computed from the RAW rows (pre-filter), so the
   * qualifier can't chase its own tail as filters narrow the board.
   */
  const poolMaxGames = useMemo(() => {
    if (effectiveMode === 'hitRate') {
      if (timeWindow === 'season') return maxGamesIn(seasonValues.rows.map((r) => (r.values ?? []).length));
      const counts = new Map<string, number>();
      for (const r of recentRows) counts.set(r.player_id, (counts.get(r.player_id) ?? 0) + 1);
      return maxGamesIn(Array.from(counts.values()));
    }
    return maxGamesIn(rows.map((r) => r.games_played));
  }, [rows, recentRows, seasonValues, effectiveMode, timeWindow]);

  const autoMin = useMemo(() => autoMinGames(poolMaxGames), [poolMaxGames]);
  const minGamesManual = minGames.trim() !== '';
  /**
   * Ranking by a per-game rate needs a floor of its own or one huge game tops
   * the board, so PER_GAME_MIN raises the AUTO qualifier in that mode. A number
   * the user pinned always wins — otherwise clearing the qualifier pill in
   * Averages mode would leave it stuck at 5.
   */
  const effectiveMinGames = useMemo(() => {
    if (minGamesManual) return Math.max(0, parseInt(minGames, 10) || 0);
    return effectiveMode === 'totals' && basis === 'perGame'
      ? Math.max(autoMin, PER_GAME_MIN)
      : autoMin;
  }, [minGames, minGamesManual, autoMin, effectiveMode, basis]);

  const band = useMemo(() => hitRateBand(minHitRate, maxHitRate), [minHitRate, maxHitRate]);

  // ── Averages / Totals mode ranking ──
  const ranked = useMemo(() => {
    if (!stat || effectiveMode !== 'totals') return [];
    const q = query.trim().toLowerCase();
    return rows
      .filter((r) => isStatParticipant(sport, [statValue(r, stat)]))
      .filter((r) => (r.games_played ?? 0) >= effectiveMinGames)
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
  }, [rows, stat, sport, basis, effectiveMinGames, query, teamFilter, effectiveMode, tonightActive, slate, sortKey]);

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
        const { hits, total, pct } = computeHitRate(values, line, direction);
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
        const { hits, total, pct } = computeHitRate(values, line, direction);
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
      .filter((p) => p.total >= effectiveMinGames)
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
  }, [recentRows, seasonValues, timeWindow, stat, sport, line, direction, effectiveMinGames, band, query, teamFilter, effectiveMode, tonightActive, slate, sortKey]);

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

  const openPlayer = (p: {
    player_id: string;
    player_name: string;
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
    });
  };

  const groups = GROUP_ORDER[sport];
  const windowN = typeof timeWindow === 'number' ? timeWindow : 10;
  // The headline under the ruler, e.g. "25+ Points" / "At most 2 Walks".
  const lineHeadline =
    direction === 'over' ? `${lineN}+ ${stat?.label ?? ''}` : `At most ${lineN} ${stat?.label ?? ''}`;

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
    if (minGamesManual) n += 1;
    if (sortKey !== 'default') n += 1;
    if (effectiveMode === 'hitRate') {
      if (band.lo > 0 || band.hi < 1) n += 1;
    } else if (basis !== 'perGame') {
      n += 1;
    }
    return n;
  }, [teamFilter, query, minGamesManual, sortKey, effectiveMode, band, basis]);

  /**
   * Clears the filters that live in the sheet only. The front-page controls
   * (stat, line, window, Hit Rates/Averages) are deliberately left alone —
   * resetting the stat you're looking at from a "Filters" sheet reads as the
   * app losing your place, not as clearing a filter.
   */
  const resetFilters = useCallback(() => {
    setBasis('perGame');
    setMinGames(''); // back to the auto qualifier
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
    // The auto qualifier is shown too — it IS narrowing the board, and a user
    // who wonders where the 2-game call-ups went should be able to see (and
    // clear) the reason in one tap.
    if (effectiveMinGames > 0) {
      out.push({
        key: 'minGames',
        label: `${effectiveMinGames}+ GP${minGamesManual ? '' : ' · auto'}`,
        onRemove: () => setMinGames('0'),
      });
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
  }, [teamFilter, query, tonightActive, slateLabel, effectiveMinGames, minGamesManual, sortKey, effectiveMode, band, bandSummary, basis]);

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
          <SportToggle />
        </View>
        <BoardModeToggle mode={boardMode} onChange={setBoardMode} />
        <TeamsBoard sport={sport} />
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
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.fixedRow}
            contentContainerStyle={styles.groupTabRow}
            keyboardShouldPersistTaps="handled"
          >
            {groups.map((g) => (
              <Pressable
                key={g}
                onPress={() => pickGroup(g)}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityState={{ selected: g === activeGroup }}
                style={({ pressed }) => pressed && styles.pressed}
              >
                <Text style={[styles.groupTab, g === activeGroup && styles.groupTabActive]}>
                  {g.toUpperCase()}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
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

      {/* Line picker: at least / at most + a tick ruler, then the headline. */}
      {effectiveMode === 'hitRate' ? (
        <>
          <View style={styles.lineRow}>
            <Pressable
              onPress={() => setDirection((d) => (d === 'over' ? 'under' : 'over'))}
              style={({ pressed }) => [styles.dirPill, pressed && styles.pressed]}
            >
              <Text style={styles.dirPillText}>
                {direction === 'over' ? 'At Least' : 'At Most'}
              </Text>
              <Ionicons name="chevron-down" size={14} color={colors.textSecondary} />
            </Pressable>
            <LineRuler
              value={lineN}
              min={1}
              max={maxLineN(stat)}
              onChange={setLineN}
            />
          </View>
          <View style={styles.headlineRow}>
            <View style={styles.headlineRule} />
            <Text style={styles.headlineText}>{lineHeadline}</Text>
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
        <View style={styles.tabRow}>
          <TabButton
            label="Hit Rates"
            active={mode === 'hitRate'}
            onPress={() => setMode('hitRate')}
          />
          <TabButton
            label="Averages"
            active={mode === 'totals'}
            onPress={() => setMode('totals')}
          />
        </View>
      ) : null}

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}

      {fromParlay ? (
        <View style={styles.fromParlayBanner}>
          <Ionicons name="receipt-outline" size={15} color={colors.tint} />
          <Text style={styles.fromParlayText}>
            Building your betslip — tap a player’s odds to add them, and you’ll head right back.
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
          {/* Only offered once the user has actually changed something — the
              auto qualifier alone is a default, not a filter to clear. */}
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

      {(effectiveMode === 'hitRate' ? hitRatePlayers.length : ranked.length) > 0 ? (
        <ColumnHeader
          rightLabel={rightLabel}
          showOdds={showOdds}
          showMatchup={matchupByTeam.size > 0}
        />
      ) : null}

      {effectiveMode === 'hitRate' ? (
        <FlatList
          data={hitRatePlayers}
          keyExtractor={(item) => item.player_id}
          renderItem={({ item, index }) => {
            const mu = item.team ? matchupByTeam.get(item.team) : undefined;
            const ep = oddsByPlayer.get(item.player_id) ?? null;
            return (
              <HitRateRow
                rank={index + 1}
                player={item}
                matchup={mu ? gradeMatchup(sport, playerType, mu) : null}
                showMatchup={matchupByTeam.size > 0}
                oddsPick={ep}
                showOdds={showOdds}
                onOddsPress={ep ? () => openOddsSheet(ep, item.player_name) : undefined}
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
                title="No players"
                subtitle={
                  query.trim()
                    ? `Nothing matched "${query.trim()}".`
                    : activeFilterCount > 0 || tonightActive
                      ? 'No players match your filters. Tap a pill above to widen the board.'
                      : `No ${sport} ${stat.label} data for ${
                          timeWindow === 'season' ? 'this season' : `the last ${windowN} games`
                        } yet.`
                }
              />
            )
          }
          style={styles.listFlex}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          initialNumToRender={20}
        />
      ) : (
        <FlatList
          data={ranked}
          keyExtractor={(item) => item.row.player_id}
          renderItem={({ item, index }) => {
            const mu = item.row.team ? matchupByTeam.get(item.row.team) : undefined;
            const ep = oddsByPlayer.get(item.row.player_id) ?? null;
            return (
              <LeaderRow
                rank={index + 1}
                row={item.row}
                value={item.value}
                gp={item.gp}
                basis={basis}
                matchup={mu ? gradeMatchup(sport, playerType, mu) : null}
                showMatchup={matchupByTeam.size > 0}
                oddsPick={ep}
                showOdds={showOdds}
                onOddsPress={ep ? () => openOddsSheet(ep, item.row.player_name ?? '') : undefined}
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
                title="No players"
                subtitle={
                  query.trim()
                    ? `Nothing matched "${query.trim()}".`
                    : activeFilterCount > 0 || tonightActive
                      ? 'No players match your filters. Tap a pill above to widen the board.'
                      : `No ${sport} ${stat.label} data for ${
                          timeWindow === 'season' ? 'this season' : `the last ${windowN} games`
                        } yet.`
                }
              />
            )
          }
          style={styles.listFlex}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          initialNumToRender={20}
        />
      )}

      {oddsSheet ? (
        <PlayerOddsSheet
          enriched={oddsSheet.ep}
          playerName={oddsSheet.name}
          visible
          onClose={() => setOddsSheet(null)}
          onOpenDetail={() => {
            const id = oddsSheet.ep.pick.pick_id;
            setOddsSheet(null);
            navigation.navigate('PickDetail', { pickId: id });
          }}
          onAdded={handleSheetAdded}
        />
      ) : null}

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
              <Pressable onPress={() => setQuery('')} hitSlop={8}>
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

        <FilterSection
          title="Qualifiers"
          subtitle={
            minGamesManual || autoMin === 0
              ? 'Drop players below these cutoffs.'
              : `Auto: ${autoMin}+ games — a quarter of the ${poolMaxGames} the leader has played. Type a number to pin it.`
          }
          summary={
            effectiveMinGames > 0
              ? `${effectiveMinGames}+ games${minGamesManual ? '' : ' · auto'}`
              : 'No minimum'
          }
        >
          <View style={styles.fieldRow}>
            <FilterField
              label="Min games played"
              value={minGames}
              onChange={setMinGames}
              placeholder={`${autoMin} (auto)`}
              maxLength={3}
            />
            <View style={styles.fieldSpacer} />
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
}: {
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
    <View style={styles.rulerWrap} onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
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
              <Pressable key={v} onPress={() => pickTick(v)} style={[styles.tickCol, { width: tickW }]}>
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
    <View style={styles.tabRow}>
      <TabButton label="Players" active={mode === 'players'} onPress={() => onChange('players')} />
      <TabButton label="Teams" active={mode === 'teams'} onPress={() => onChange('teams')} />
    </View>
  );
}

function TabButton({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={[styles.tab, active && styles.tabActive]}>
      <Text style={[styles.tabText, active && styles.tabTextActive]}>{label}</Text>
    </Pressable>
  );
}

function fmtValue(value: number, basis: Basis): string {
  return basis === 'perGame' ? value.toFixed(1) : String(Math.round(value));
}

function matchupColor(tier: MatchupInfo['tier']): string {
  if (tier === 'favorable') return colors.bet;
  if (tier === 'tough') return colors.avoid;
  return colors.textSecondary;
}

function matchupTierLabel(tier: MatchupInfo['tier']): string {
  if (tier === 'favorable') return 'FAV';
  if (tier === 'tough') return 'TGH';
  return 'NEU';
}

/** Right-hand odds cell: today's price for this player's prop, or a dash.
 * Tappable (its own Pressable, so the tap doesn't bubble to the row) — opens
 * the player odds sheet with every book's price + add-to-betslip. */
function OddsCell({ ep, onPress }: { ep: EnrichedPick | null; onPress?: () => void }) {
  if (!ep || ep.pick.dk_odds == null) {
    return (
      <View style={styles.oddsWrap}>
        <Text style={styles.oddsEmpty}>—</Text>
      </View>
    );
  }
  const p = ep.pick;
  const side = p.pick_side === 'under' ? 'u' : 'o';
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      hitSlop={6}
      style={({ pressed }) => [styles.oddsWrap, pressed && styles.pressed]}
    >
      <View style={styles.oddsPill}>
        <Text style={styles.oddsText}>{formatAmerican(p.dk_odds)}</Text>
      </View>
      {p.scored_line != null ? (
        <Text style={styles.oddsLine}>
          {side}
          {p.scored_line}
        </Text>
      ) : null}
    </Pressable>
  );
}

/** Matchup cell: tonight's opponent + how good a spot it is. */
function MatchupCell({ matchup }: { matchup: MatchupInfo | null }) {
  if (!matchup) {
    return (
      <View style={styles.matchupWrap}>
        <Text style={styles.oddsEmpty}>—</Text>
      </View>
    );
  }
  const c = matchupColor(matchup.tier);
  return (
    <View style={styles.matchupWrap}>
      <Text style={[styles.matchupTier, { color: c }]}>{matchupTierLabel(matchup.tier)}</Text>
      <Text style={styles.matchupOpp} numberOfLines={1}>
        {matchup.row.opponent}
      </Text>
    </View>
  );
}

/** Compact column header sitting flush above the leaderboard (HOF-style). */
function ColumnHeader({
  rightLabel,
  showOdds,
  showMatchup,
}: {
  rightLabel: string;
  showOdds: boolean;
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
          ODDS
        </Text>
      ) : null}
      {showMatchup ? (
        <Text style={[styles.colHeaderRight, styles.colHeaderMatchup]} numberOfLines={1}>
          SPOT
        </Text>
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
  oddsPick,
  showOdds,
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
  oddsPick: EnrichedPick | null;
  showOdds: boolean;
  onOddsPress?: () => void;
  tappable: boolean;
  onPress: () => void;
}) {
  const body = (
    <>
      <Text style={styles.rank}>{rank}</Text>
      <View style={styles.rowMain}>
        <Text style={styles.rowName} numberOfLines={1}>
          {row.player_name}
          {row.team ? <Text style={styles.rowTeam}>  {row.team}</Text> : null}
        </Text>
        <Text style={styles.rowMeta} numberOfLines={1}>
          {gp} GP
          {matchup ? `  ·  ${matchup.text}` : ''}
        </Text>
      </View>
      <View style={styles.valueWrap}>
        <Text style={styles.value}>{fmtValue(value, basis)}</Text>
      </View>
      {showOdds ? <OddsCell ep={oddsPick} onPress={onOddsPress} /> : null}
      {showMatchup ? <MatchupCell matchup={matchup} /> : null}
    </>
  );
  if (!tappable) return <View style={styles.row}>{body}</View>;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      {body}
    </Pressable>
  );
}

function HitRateRow({
  rank,
  player,
  matchup,
  showMatchup,
  oddsPick,
  showOdds,
  onOddsPress,
  tappable,
  onPress,
}: {
  rank: number;
  player: HitRatePlayer;
  matchup: MatchupInfo | null;
  showMatchup: boolean;
  oddsPick: EnrichedPick | null;
  showOdds: boolean;
  onOddsPress?: () => void;
  tappable: boolean;
  onPress: () => void;
}) {
  const pctColor = hitRateColor(player.pct);
  const body = (
    <>
      <Text style={styles.rank}>{rank}</Text>
      <View style={styles.rowMain}>
        <Text style={styles.rowName} numberOfLines={1}>
          {player.player_name}
          {player.team ? <Text style={styles.rowTeam}>  {player.team}</Text> : null}
        </Text>
        <Text style={styles.rowMeta} numberOfLines={1}>
          avg {player.avg.toFixed(1)}
          {matchup ? `  ·  ${matchup.text}` : ''}
        </Text>
      </View>
      <View style={styles.valueWrap}>
        <Text style={[styles.value, { color: pctColor }]}>
          {Math.round(player.pct * 100)}%
        </Text>
        <Text style={styles.valueLabel}>
          {player.hits}/{player.total}
        </Text>
      </View>
      {showOdds ? <OddsCell ep={oddsPick} onPress={onOddsPress} /> : null}
      {showMatchup ? <MatchupCell matchup={matchup} /> : null}
    </>
  );
  if (!tappable) return <View style={styles.row}>{body}</View>;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
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
  fieldSpacer: { flex: 1 },
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
    fontSize: 11,
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
  dirPillText: {
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
  tabRow: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: colors.tint,
  },
  tabText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  tabTextActive: {
    color: colors.tint,
  },

  statPicker: {
    paddingTop: spacing.xs,
  },
  // Group tabs (Passing | Rushing | …) — same uppercase-caption look the old
  // section labels had, but tappable and on one row.
  groupTabRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xs,
  },
  groupTab: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
    paddingVertical: 4,
  },
  groupTabActive: {
    color: colors.tint,
    fontWeight: font.weight.bold,
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
    width: 48,
    textAlign: 'right',
    fontSize: 11,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    letterSpacing: 0.3,
  },
  colHeaderOdds: { width: 54 },
  colHeaderMatchup: { width: 40 },
  // Rows are deliberately compact — more players visible per screen.
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
    fontSize: 11,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
  },
  rowMeta: {
    fontSize: 11,
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
    fontSize: 10,
    color: colors.textTertiary,
  },
  oddsWrap: {
    width: 54,
    alignItems: 'flex-end',
  },
  // Tinted border — the pill is a tappable button (opens the odds sheet).
  oddsPill: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
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
  oddsText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  oddsLine: {
    fontSize: 10,
    color: colors.textTertiary,
    marginTop: 1,
  },
  oddsEmpty: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
  },
  matchupWrap: {
    width: 40,
    alignItems: 'flex-end',
  },
  matchupTier: {
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    letterSpacing: 0.2,
  },
  matchupOpp: {
    fontSize: 10,
    color: colors.textTertiary,
    marginTop: 1,
  },
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

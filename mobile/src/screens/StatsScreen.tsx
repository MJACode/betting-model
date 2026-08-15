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
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { useNavigation } from '@react-navigation/native';
import type { CompositeNavigationProp } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { SportToggle } from '@/components/SportToggle';
import { SettingsButton } from '@/components/SettingsButton';
import { FilterChip } from '@/components/filters/FilterChip';
import { FilterField } from '@/components/filters/FilterField';
import { FilterSection, FilterSheet } from '@/components/filters/FilterSheet';
import type { ActivePill } from '@/components/filters/FilterBar';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { fetchRecentGames, fetchTonightMatchups, fetchWindowTotals } from '@/lib/queries';
import { computeHitRate, hitFlags, type HitDirection } from '@/lib/hitRate';
import { buildMatchupMap, gradeMatchup, type MatchupInfo } from '@/lib/matchup';
import { formatAmerican } from '@/lib/format';
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
import { colors, font, radii, spacing } from '@/lib/theme';
import type {
  HitRatePlayer,
  RecentGameRow,
  SeasonTotalsRow,
  TonightMatchupRow,
  RootStackParamList,
  TabParamList,
} from '@/types';

type Nav = CompositeNavigationProp<
  BottomTabNavigationProp<TabParamList, 'Stats'>,
  NativeStackNavigationProp<RootStackParamList>
>;
type Basis = 'total' | 'perGame';
type Mode = 'totals' | 'hitRate';
// Last-N-games window. 'season' = whole season (null window on the RPC).
type TimeWindow = 3 | 5 | 10 | 15 | 20 | 'season';

/** Today's DK prop price for a player under the selected stat's prop model. */
interface PropOdds {
  odds: number;
  line: number | null;
  side: string;
}

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
  const { sport } = useSportFilter();
  // Today's board — used only to hang a live DK price off each leaderboard row.
  const { data: todayPicks } = useTodayPicks();

  const [stat, setStat] = useState<StatDef | null>(() => defaultStatFor(sport));
  const [mode, setMode] = useState<Mode>('hitRate');
  const [basis, setBasis] = useState<Basis>('perGame');
  const [timeWindow, setTimeWindow] = useState<TimeWindow>(10);
  const [minGames, setMinGames] = useState<string>('3');
  const [query, setQuery] = useState<string>('');
  const [teamFilter, setTeamFilter] = useState<string | null>(null);
  // Hit Rate controls (front page): integer line + at least / at most.
  const [lineN, setLineN] = useState<number>(() => defaultLineN(defaultStatFor(sport)));
  const [direction, setDirection] = useState<HitDirection>('over');
  const [minHitRate, setMinHitRate] = useState<string>('');

  const [rows, setRows] = useState<SeasonTotalsRow[]>([]); // totals mode
  const [recentRows, setRecentRows] = useState<RecentGameRow[]>([]); // hit-rate mode
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState<boolean>(false);
  // Tonight's slate: team → matchup (opponent + strength). Empty on off days
  // and for sports without a matchup view.
  const [tonightOnly, setTonightOnly] = useState<boolean>(false);
  const [matchups, setMatchups] = useState<TonightMatchupRow[]>([]);

  // Hit Rate only exists for sports with per-game player logs (MLB/WNBA/NBA).
  const canHitRate = supportsHitRate(sport);
  const effectiveMode: Mode = canHitRate ? mode : 'totals';

  // Reset to the sport's default stat + clear filters whenever the sport changes.
  useEffect(() => {
    const next = defaultStatFor(sport);
    setStat(next);
    setQuery('');
    setTeamFilter(null);
    setLineN(defaultLineN(next));
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

  const matchupByTeam = useMemo(() => buildMatchupMap(matchups), [matchups]);
  // Only filter when there is actually a slate — a stale toggle on an off day
  // (or after switching to a sport with no matchup view) must not empty the list.
  const tonightActive = tonightOnly && matchupByTeam.size > 0;

  // Hit Rate needs a fixed N — coerce away from 'season' when entering it.
  useEffect(() => {
    if (effectiveMode === 'hitRate' && timeWindow === 'season') setTimeWindow(10);
  }, [effectiveMode, timeWindow]);

  const playerType = stat?.playerType;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (!stat) {
        setRows([]);
        setRecentRows([]);
        return;
      }
      if (effectiveMode === 'hitRate') {
        const n = typeof timeWindow === 'number' ? timeWindow : 10;
        const data = await fetchRecentGames(sport, SEASON, n, playerType);
        setRecentRows(data);
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
  }, [sport, playerType, timeWindow, effectiveMode]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleBasis = (next: Basis) => {
    setBasis(next);
    if (next === 'perGame' && (parseInt(minGames, 10) || 0) < PER_GAME_MIN) {
      setMinGames(String(PER_GAME_MIN));
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    if (next === 'hitRate' && timeWindow === 'season') setTimeWindow(10);
  };

  // Each stat carries its own sensible line — snap the ruler back on switch.
  const pickStat = (s: StatDef) => {
    setStat(s);
    setLineN(defaultLineN(s));
  };

  const line = useMemo(() => lineFor(lineN, direction), [lineN, direction]);

  // Live DK prop price per player for the selected stat's market, so the board
  // shows what the number is actually priced at today. Empty when the stat has
  // no prop model or the market isn't listed. BET rows win over dead-zone rows.
  const propModel = propModelForStat(stat);
  const oddsByPlayer = useMemo(() => {
    const map = new Map<string, PropOdds>();
    if (!propModel) return map;
    for (const ep of todayPicks) {
      const p = ep.pick;
      if (p.model_id !== propModel || !p.player_id || p.dk_odds == null) continue;
      const existing = map.get(p.player_id);
      if (existing && p.signal_type !== 'BET') continue;
      map.set(p.player_id, { odds: p.dk_odds, line: p.scored_line, side: p.pick_side });
    }
    return map;
  }, [todayPicks, propModel]);
  const showOdds = oddsByPlayer.size > 0;

  // ── Averages / Totals mode ranking ──
  const ranked = useMemo(() => {
    if (!stat || effectiveMode !== 'totals') return [];
    const mg = Math.max(0, parseInt(minGames, 10) || 0);
    const q = query.trim().toLowerCase();
    return rows
      .filter((r) => (r.games_played ?? 0) >= mg)
      .filter((r) => !teamFilter || r.team === teamFilter)
      .filter((r) => !tonightActive || (r.team != null && matchupByTeam.has(r.team)))
      .filter((r) => !q || (r.player_name ?? '').toLowerCase().includes(q))
      .map((r) => {
        const total = statValue(r, stat);
        const gp = r.games_played || 0;
        return { row: r, value: basis === 'perGame' && gp > 0 ? total / gp : total, total, gp };
      })
      .sort((a, b) => b.value - a.value);
  }, [rows, stat, basis, minGames, query, teamFilter, effectiveMode, tonightActive, matchupByTeam]);

  // ── Hit Rate mode: group last-N rows per player, count over/under the line ──
  const hitRatePlayers = useMemo<HitRatePlayer[]>(() => {
    if (!stat || effectiveMode !== 'hitRate') return [];
    const byPlayer = new Map<string, RecentGameRow[]>();
    for (const r of recentRows) {
      const arr = byPlayer.get(r.player_id);
      if (arr) arr.push(r);
      else byPlayer.set(r.player_id, [r]);
    }
    const out: HitRatePlayer[] = [];
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
    const mg = Math.max(0, parseInt(minGames, 10) || 0);
    const mhr = Math.max(0, parseFloat(minHitRate) || 0);
    const q = query.trim().toLowerCase();
    return out
      .filter((p) => p.total >= mg)
      .filter((p) => p.pct * 100 >= mhr)
      .filter((p) => !teamFilter || p.team === teamFilter)
      .filter((p) => !tonightActive || (p.team != null && matchupByTeam.has(p.team)))
      .filter((p) => !q || p.player_name.toLowerCase().includes(q))
      .sort((a, b) => b.pct - a.pct || b.total - a.total);
  }, [recentRows, stat, line, direction, minGames, minHitRate, query, teamFilter, effectiveMode, tonightActive, matchupByTeam]);

  // Teams present in the active dataset, for the team filter chips.
  const teams = useMemo(() => {
    const src: Array<{ team: string | null }> =
      effectiveMode === 'hitRate' ? recentRows : rows;
    const set = new Set<string>();
    for (const r of src) if (r.team) set.add(r.team);
    return Array.from(set).sort();
  }, [rows, recentRows, effectiveMode]);

  const openPlayer = (p: {
    player_id: string;
    player_name: string;
    player_type?: SeasonTotalsRow['player_type'];
  }) => {
    // WNBA/NBA player detail isn't supported yet (trends read MLB game log only).
    if (sport !== 'MLB' || !p.player_type) return;
    navigation.navigate('PlayerStats', {
      playerId: p.player_id,
      playerName: p.player_name,
      playerType: p.player_type,
    });
  };

  const groups = GROUP_ORDER[sport];
  const windowOptions =
    effectiveMode === 'hitRate' ? TIME_WINDOWS.filter((w) => w.value !== 'season') : TIME_WINDOWS;
  const windowN = typeof timeWindow === 'number' ? timeWindow : 10;
  // The headline under the ruler, e.g. "25+ Points" / "At most 2 Walks".
  const lineHeadline =
    direction === 'over' ? `${lineN}+ ${stat?.label ?? ''}` : `At most ${lineN} ${stat?.label ?? ''}`;

  // Count filters the user has changed away from defaults, for the trigger badge.
  // Only counts what still lives in the modal — the front-page controls are visible.
  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (teamFilter) n += 1;
    if (query.trim()) n += 1;
    if ((parseInt(minGames, 10) || 0) !== 3) n += 1;
    if (effectiveMode === 'hitRate') {
      if ((parseFloat(minHitRate) || 0) > 0) n += 1;
    } else if (basis !== 'perGame') {
      n += 1;
    }
    return n;
  }, [teamFilter, query, minGames, effectiveMode, minHitRate, basis]);

  /**
   * Clears the filters that live in the sheet only. The front-page controls
   * (stat, line, window, Hit Rates/Averages) are deliberately left alone —
   * resetting the stat you're looking at from a "Filters" sheet reads as the
   * app losing your place, not as clearing a filter.
   */
  const resetFilters = useCallback(() => {
    setBasis('perGame');
    setMinGames('3');
    setQuery('');
    setTeamFilter(null);
    setMinHitRate('');
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
    if ((parseInt(minGames, 10) || 0) !== 3) {
      out.push({
        key: 'minGames',
        label: `${parseInt(minGames, 10) || 0}+ GP`,
        onRemove: () => setMinGames('3'),
      });
    }
    if (effectiveMode === 'hitRate') {
      const mhr = parseFloat(minHitRate) || 0;
      if (mhr > 0) {
        out.push({ key: 'minHit', label: `hit ≥ ${mhr}%`, onRemove: () => setMinHitRate('') });
      }
    } else if (basis !== 'perGame') {
      out.push({ key: 'basis', label: 'Totals', onRemove: () => setBasis('perGame') });
    }
    return out;
  }, [teamFilter, query, minGames, effectiveMode, minHitRate, basis]);

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

      {/* Stat selector — the primary control, straight under the sport row. */}
      <View style={styles.statPicker}>
        {groups.map((g) => (
          <View key={g} style={styles.statGroup}>
            {groups.length > 1 ? <Text style={styles.groupLabel}>{g.toUpperCase()}</Text> : null}
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chipRow}
              keyboardShouldPersistTaps="handled"
            >
              {statsForSport(sport)
                .filter((s) => s.group === g)
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
        ))}
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

      {/* Time window + tonight filter.
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
        {windowOptions.map((w) => (
          <FilterChip
            key={String(w.value)}
            label={w.label}
            active={w.value === timeWindow}
            onPress={() => setTimeWindow(w.value)}
          />
        ))}
        {matchupByTeam.size > 0 ? (
          <FilterChip
            label="Tonight"
            icon="moon-outline"
            active={tonightActive}
            onPress={() => setTonightOnly((v) => !v)}
          />
        ) : null}
      </ScrollView>

      {/* Hit Rates | Averages */}
      {canHitRate ? (
        <View style={styles.tabRow}>
          <TabButton
            label="Hit Rates"
            active={mode === 'hitRate'}
            onPress={() => switchMode('hitRate')}
          />
          <TabButton
            label="Averages"
            active={mode === 'totals'}
            onPress={() => switchMode('totals')}
          />
        </View>
      ) : null}

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
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
          <Pressable
            onPress={resetFilters}
            style={({ pressed }) => [styles.clearBtn, pressed && styles.pressed]}
            hitSlop={6}
          >
            <Text style={styles.clearText}>Clear all</Text>
          </Pressable>
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
            return (
              <HitRateRow
                rank={index + 1}
                player={item}
                line={line}
                direction={direction}
                matchup={mu ? gradeMatchup(sport, playerType, mu) : null}
                showMatchup={matchupByTeam.size > 0}
                odds={oddsByPlayer.get(item.player_id) ?? null}
                showOdds={showOdds}
                tappable={sport === 'MLB'}
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
                    : `No ${sport} ${stat.label} data for the last ${windowN} games yet.`
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
            return (
              <LeaderRow
                rank={index + 1}
                row={item.row}
                value={item.value}
                gp={item.gp}
                basis={basis}
                matchup={mu ? gradeMatchup(sport, playerType, mu) : null}
                showMatchup={matchupByTeam.size > 0}
                odds={oddsByPlayer.get(item.row.player_id) ?? null}
                showOdds={showOdds}
                tappable={sport === 'MLB'}
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

      <FilterSheet
        visible={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Filter players"
        resultCount={effectiveMode === 'hitRate' ? hitRatePlayers.length : ranked.length}
        itemNoun="player"
        onReset={resetFilters}
        canReset={activeFilterCount > 0}
      >
        <FilterSection title="Search">
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
          <FilterSection title="Rank by" subtitle="Per-game average or the raw total.">
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

        <FilterSection title="Qualifiers" subtitle="Drop players below these cutoffs.">
          <View style={styles.fieldRow}>
            <FilterField
              label="Min games played"
              value={minGames}
              onChange={setMinGames}
              placeholder="3"
              maxLength={3}
            />
            {effectiveMode === 'hitRate' ? (
              <FilterField
                label="Min hit rate"
                value={minHitRate}
                onChange={setMinHitRate}
                placeholder="0"
                suffix="%"
                maxLength={3}
              />
            ) : (
              <View style={styles.fieldSpacer} />
            )}
          </View>
        </FilterSection>

        {teams.length > 1 ? (
          <FilterSection title="Team">
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

/**
 * Tick ruler for the line. Shows a fixed window of values centred on the
 * current one — tapping a neighbour re-centres. A windowed row (rather than a
 * scroll view) keeps the selected value pinned in the middle with no measuring.
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
  const offsets = [-2, -1, 0, 1, 2];
  return (
    <View style={styles.ruler}>
      {offsets.map((o, i) => {
        const v = value + o;
        const inRange = v >= min && v <= max;
        const active = o === 0;
        return (
          <React.Fragment key={o}>
            {i > 0 ? (
              <View style={styles.rulerGap}>
                <View style={styles.tickSmall} />
                <View style={styles.tickSmall} />
                <View style={styles.tickSmall} />
              </View>
            ) : null}
            <Pressable
              disabled={!inRange || active}
              onPress={() => onChange(v)}
              hitSlop={8}
              style={styles.tickWrap}
            >
              <View
                style={[
                  styles.tickTall,
                  active && styles.tickTallActive,
                  !inRange && styles.tickHidden,
                ]}
              />
              {inRange ? (
                active ? (
                  <View style={styles.tickValueBox}>
                    <Text style={styles.tickValueActive}>{v}</Text>
                  </View>
                ) : (
                  <Text style={styles.tickValue}>{v}</Text>
                )
              ) : (
                <Text style={styles.tickValue}> </Text>
              )}
            </Pressable>
          </React.Fragment>
        );
      })}
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

/** Right-hand odds cell: today's DK price for this player's prop, or a dash. */
function OddsCell({ odds }: { odds: PropOdds | null }) {
  if (!odds) {
    return (
      <View style={styles.oddsWrap}>
        <Text style={styles.oddsEmpty}>—</Text>
      </View>
    );
  }
  const side = odds.side === 'under' ? 'u' : 'o';
  return (
    <View style={styles.oddsWrap}>
      <View style={styles.oddsPill}>
        <Text style={styles.oddsText}>{formatAmerican(odds.odds)}</Text>
      </View>
      {odds.line != null ? (
        <Text style={styles.oddsLine}>
          {side}
          {odds.line}
        </Text>
      ) : null}
    </View>
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
  odds,
  showOdds,
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
  odds: PropOdds | null;
  showOdds: boolean;
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
      {showOdds ? <OddsCell odds={odds} /> : null}
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
  line,
  direction,
  matchup,
  showMatchup,
  odds,
  showOdds,
  tappable,
  onPress,
}: {
  rank: number;
  player: HitRatePlayer;
  line: number;
  direction: HitDirection;
  matchup: MatchupInfo | null;
  showMatchup: boolean;
  odds: PropOdds | null;
  showOdds: boolean;
  tappable: boolean;
  onPress: () => void;
}) {
  const pctColor = hitRateColor(player.pct);
  // Oldest → newest left-to-right (RPC returns newest-first, so reverse).
  const flags = hitFlags(player.values, line, direction).slice().reverse();
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
        <View style={styles.dotStrip}>
          {flags.map((hit, i) => (
            <View
              key={i}
              style={[styles.dot, { backgroundColor: hit ? colors.bet : colors.avoid }]}
            />
          ))}
        </View>
      </View>
      <View style={styles.valueWrap}>
        <Text style={[styles.value, { color: pctColor }]}>
          {Math.round(player.pct * 100)}%
        </Text>
        <Text style={styles.valueLabel}>
          {player.hits}/{player.total}
        </Text>
      </View>
      {showOdds ? <OddsCell odds={odds} /> : null}
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
  ruler: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  rulerGap: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    paddingTop: 6,
  },
  tickWrap: {
    alignItems: 'center',
    minWidth: 26,
  },
  tickTall: {
    width: 2,
    height: 20,
    borderRadius: 1,
    backgroundColor: colors.separatorOpaque,
  },
  tickTallActive: {
    backgroundColor: colors.tint,
    height: 24,
    width: 3,
  },
  tickHidden: {
    opacity: 0,
  },
  tickSmall: {
    width: 1,
    height: 9,
    borderRadius: 1,
    backgroundColor: colors.separator,
  },
  tickValue: {
    marginTop: 6,
    fontSize: font.size.footnote,
    color: colors.textTertiary,
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
  statGroup: {
    marginBottom: spacing.xs,
  },
  groupLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
    paddingHorizontal: spacing.lg,
    marginBottom: 2,
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
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    paddingVertical: 9,
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
    fontSize: font.size.footnote,
    fontWeight: font.weight.bold,
    color: colors.textTertiary,
  },
  rowName: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  rowTeam: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
  },
  rowMeta: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 1,
  },
  dotStrip: {
    flexDirection: 'row',
    gap: 2.5,
    marginTop: 5,
    flexWrap: 'wrap',
  },
  dot: {
    width: 9,
    height: 9,
    borderRadius: 2,
  },
  valueWrap: {
    alignItems: 'flex-end',
    width: 48,
  },
  value: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  valueLabel: {
    fontSize: 10,
    color: colors.textTertiary,
    marginTop: 1,
  },
  oddsWrap: {
    width: 54,
    alignItems: 'flex-end',
  },
  oddsPill: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
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

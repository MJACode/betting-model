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
import { useNavigation, useRoute } from '@react-navigation/native';
import type { CompositeNavigationProp, RouteProp } from '@react-navigation/native';
import { AddToPlayButton } from '@/components/AddToPlayButton';
import { EmptyState } from '@/components/EmptyState';
import { SportToggle } from '@/components/SportToggle';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { slipKeyForPick } from '@/lib/parlay';
import { fetchWindowTotals } from '@/lib/queries';
import { formatAmerican } from '@/lib/format';
import {
  GROUP_ORDER,
  defaultStatFor,
  propModelForStat,
  statValue,
  statsForSport,
  type StatDef,
} from '@/lib/statCatalog';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick, SeasonTotalsRow, RootStackParamList, TabParamList } from '@/types';

type Nav = CompositeNavigationProp<
  BottomTabNavigationProp<TabParamList, 'Stats'>,
  NativeStackNavigationProp<RootStackParamList>
>;
type Basis = 'total' | 'perGame';
// Last-N-games window. 'season' = whole season (null window on the RPC).
type TimeWindow = 3 | 5 | 10 | 20 | 'season';

const SEASON = new Date().getUTCFullYear();
const PER_GAME_MIN = 5; // qualifier when ranking by per-game rate

const TIME_WINDOWS: { value: TimeWindow; label: string }[] = [
  { value: 3, label: 'Last 3' },
  { value: 5, label: 'Last 5' },
  { value: 10, label: 'Last 10' },
  { value: 20, label: 'Last 20' },
  { value: 'season', label: 'Season' },
];

export function StatsScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<RouteProp<TabParamList, 'Stats'>>();
  const { sport } = useSportFilter();
  const { data: todayPicks } = useTodayPicks();
  const slip = useParlaySlip();

  // User came here from the Parlay tab to find a leg — adding a player sends
  // them straight back to their parlay.
  const fromParlay = route.params?.fromParlay === true;
  const clearFromParlay = useCallback(() => {
    navigation.setParams({ fromParlay: undefined });
  }, [navigation]);

  const [stat, setStat] = useState<StatDef | null>(() => defaultStatFor(sport));
  const [basis, setBasis] = useState<Basis>('total');
  const [timeWindow, setTimeWindow] = useState<TimeWindow>(10);
  const [minGames, setMinGames] = useState<string>('1');
  const [query, setQuery] = useState<string>('');

  const [rows, setRows] = useState<SeasonTotalsRow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Reset to the sport's default stat whenever the sport changes.
  useEffect(() => {
    setStat(defaultStatFor(sport));
    setQuery('');
  }, [sport]);

  // Load windowed totals for the current sport + player_type + window.
  // Refetches when sport, player_type, or the time window changes (not on
  // every stat switch within the same player type).
  const playerType = stat?.playerType;
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (!stat) {
        setRows([]);
        return;
      }
      const win = timeWindow === 'season' ? null : timeWindow;
      const data = await fetchWindowTotals(sport, SEASON, win, playerType);
      setRows(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [sport, playerType, timeWindow]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleBasis = (next: Basis) => {
    setBasis(next);
    if (next === 'perGame' && (parseInt(minGames, 10) || 0) < PER_GAME_MIN) {
      setMinGames(String(PER_GAME_MIN));
    }
  };

  const ranked = useMemo(() => {
    if (!stat) return [];
    const mg = Math.max(0, parseInt(minGames, 10) || 0);
    const q = query.trim().toLowerCase();
    return rows
      .filter((r) => (r.games_played ?? 0) >= mg)
      .filter((r) => !q || (r.player_name ?? '').toLowerCase().includes(q))
      .map((r) => {
        const total = statValue(r, stat);
        const gp = r.games_played || 0;
        return { row: r, value: basis === 'perGame' && gp > 0 ? total / gp : total, total, gp };
      })
      .sort((a, b) => b.value - a.value);
  }, [rows, stat, basis, minGames, query]);

  // Bridge to today's picks: a player can be added to the parlay slip when a
  // priced prop pick exists for them under the prop model matching the selected
  // stat (e.g. "Hits" → mlb_prop_batter_hits). Keyed by player_id|model_id.
  const modelForStat = useMemo(() => propModelForStat(stat), [stat]);
  const pickByPlayerModel = useMemo(() => {
    const m = new Map<string, EnrichedPick>();
    for (const ep of todayPicks) {
      const p = ep.pick;
      if (p.player_id == null || p.dk_odds == null) continue;
      const key = `${p.player_id}|${p.model_id}`;
      if (!m.has(key)) m.set(key, ep);
    }
    return m;
  }, [todayPicks]);

  const pickForRow = useCallback(
    (row: SeasonTotalsRow): EnrichedPick | undefined =>
      modelForStat ? pickByPlayerModel.get(`${row.player_id}|${modelForStat}`) : undefined,
    [modelForStat, pickByPlayerModel],
  );

  const handleTogglePlay = useCallback(
    (ep: EnrichedPick) => {
      const key = slipKeyForPick(ep.pick);
      const adding = !slip.has(key);
      slip.toggle(key);
      if (adding && fromParlay) {
        clearFromParlay();
        navigation.navigate('Parlay');
      }
    },
    [slip, fromParlay, clearFromParlay, navigation],
  );

  const openPlayer = (r: SeasonTotalsRow) => {
    // WNBA player detail isn't supported yet (trends read MLB game log only).
    if (sport !== 'MLB' || !r.player_type) return;
    navigation.navigate('PlayerStats', {
      playerId: r.player_id,
      playerName: r.player_name,
      playerType: r.player_type,
    });
  };

  const groups = GROUP_ORDER[sport];
  const windowLabel =
    timeWindow === 'season' ? `${SEASON} season` : `Last ${timeWindow} games`;

  // Sports with no per-player leaderboard (NHL: team+goalie only; Golf: v1).
  if (!stat) {
    const isGolf = sport === 'GOLF';
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <Text style={styles.title}>Stats</Text>
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

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Stats</Text>
        <Text style={styles.subtitle}>
          {windowLabel} — most {stat.label.toLowerCase()} ranked first.
        </Text>
        <SportToggle />
      </View>

      {fromParlay ? (
        <View style={styles.parlayBanner}>
          <Ionicons name="layers-outline" size={16} color={colors.tint} />
          <Text style={styles.parlayBannerText}>
            Building your parlay — tap "Add to parlay" on a player and you'll go back to the Parlay
            tab.
          </Text>
          <Pressable onPress={clearFromParlay} hitSlop={8}>
            <Ionicons name="close-circle" size={18} color={colors.textTertiary} />
          </Pressable>
        </View>
      ) : null}

      {/* Time-window selector (last N games) */}
      <View>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.windowRow}
          keyboardShouldPersistTaps="handled"
        >
          {TIME_WINDOWS.map((w) => {
            const active = w.value === timeWindow;
            return (
              <Pressable
                key={String(w.value)}
                onPress={() => setTimeWindow(w.value)}
                style={[styles.windowChip, active && styles.windowChipActive]}
              >
                <Text style={[styles.windowChipText, active && styles.windowChipTextActive]}>
                  {w.label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {/* Stat category selector */}
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
                .map((s) => {
                  const active = s.key === stat.key && s.group === stat.group;
                  return (
                    <Pressable
                      key={`${s.group}:${String(s.key)}`}
                      onPress={() => setStat(s)}
                      style={[styles.chip, active && styles.chipActive]}
                    >
                      <Text style={[styles.chipText, active && styles.chipTextActive]}>
                        {s.label}
                      </Text>
                    </Pressable>
                  );
                })}
            </ScrollView>
          </View>
        ))}
      </View>

      {/* Basis + min games + search */}
      <View style={styles.controls}>
        <View style={styles.basisToggle}>
          <BasisPill label="Total" active={basis === 'total'} onPress={() => toggleBasis('total')} />
          <BasisPill label="Per game" active={basis === 'perGame'} onPress={() => toggleBasis('perGame')} />
        </View>
        <View style={styles.minGamesWrap}>
          <Text style={styles.minGamesLabel}>Min GP</Text>
          <TextInput
            style={styles.minGamesInput}
            value={minGames}
            onChangeText={(t) => setMinGames(t.replace(/[^0-9]/g, ''))}
            keyboardType="number-pad"
            maxLength={3}
            placeholder="1"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
      </View>

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

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}

      <FlatList
        data={ranked}
        keyExtractor={(item) => item.row.player_id}
        renderItem={({ item, index }) => {
          const addPick = pickForRow(item.row);
          return (
            <LeaderRow
              rank={index + 1}
              row={item.row}
              value={item.value}
              gp={item.gp}
              basis={basis}
              statLabel={stat.label}
              tappable={sport === 'MLB'}
              onPress={() => openPlayer(item.row)}
              addPick={addPick}
              inPlay={addPick ? slip.has(slipKeyForPick(addPick.pick)) : false}
              onTogglePlay={addPick ? () => handleTogglePlay(addPick) : undefined}
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
                  : `No ${sport} ${stat.label} data for ${windowLabel.toLowerCase()} yet.`
              }
            />
          )
        }
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
        initialNumToRender={20}
      />
    </SafeAreaView>
  );
}

function BasisPill({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.basisPill, active && styles.basisPillActive]}>
      <Text style={[styles.basisPillText, active && styles.basisPillTextActive]}>{label}</Text>
    </Pressable>
  );
}

function fmtValue(value: number, basis: Basis): string {
  return basis === 'perGame' ? value.toFixed(1) : String(Math.round(value));
}

function LeaderRow({
  rank,
  row,
  value,
  gp,
  basis,
  statLabel,
  tappable,
  onPress,
  addPick,
  inPlay,
  onTogglePlay,
}: {
  rank: number;
  row: SeasonTotalsRow;
  value: number;
  gp: number;
  basis: Basis;
  statLabel: string;
  tappable: boolean;
  onPress: () => void;
  addPick?: EnrichedPick;
  inPlay: boolean;
  onTogglePlay?: () => void;
}) {
  const odds = addPick?.pick.dk_odds;
  const body = (
    <>
      <Text style={styles.rank}>{rank}</Text>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowName} numberOfLines={1}>
          {row.player_name}
        </Text>
        <Text style={styles.rowMeta}>
          {row.team ?? '—'} · {gp} GP
        </Text>
      </View>
      <View style={styles.valueWrap}>
        <Text style={styles.value}>{fmtValue(value, basis)}</Text>
        <Text style={styles.valueLabel}>
          {statLabel}
          {basis === 'perGame' ? '/g' : ''}
        </Text>
      </View>
      {onTogglePlay ? (
        <View style={styles.addWrap}>
          <AddToPlayButton inPlay={inPlay} onPress={onTogglePlay} compact />
          {odds != null ? <Text style={styles.addOdds}>{formatAmerican(odds)}</Text> : null}
        </View>
      ) : tappable ? (
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
      ) : null}
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
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 4,
    marginBottom: spacing.sm,
  },
  parlayBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.tint,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  parlayBannerText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  windowRow: {
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  windowChip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  windowChipActive: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  windowChipText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  windowChipTextActive: {
    color: colors.textInverse,
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
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  chipActive: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  chipText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  chipTextActive: {
    color: colors.textInverse,
  },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    marginTop: spacing.sm,
    gap: spacing.md,
  },
  basisToggle: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderRadius: radii.pill,
    padding: 3,
  },
  basisPill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.pill,
  },
  basisPillActive: {
    backgroundColor: colors.tint,
  },
  basisPillText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  basisPillTextActive: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
  },
  minGamesWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  minGamesLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  minGamesInput: {
    width: 52,
    textAlign: 'center',
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    backgroundColor: colors.bgCard,
    borderRadius: radii.sm,
    paddingVertical: spacing.xs,
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
    paddingTop: spacing.md,
    paddingBottom: spacing.xl,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    gap: spacing.md,
  },
  rank: {
    width: 26,
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
  rowMeta: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  valueWrap: {
    alignItems: 'flex-end',
    minWidth: 56,
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
  addWrap: {
    alignItems: 'center',
    gap: 2,
  },
  addOdds: {
    fontSize: 10,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
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

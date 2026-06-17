import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { HitRateChart } from '@/components/HitRateChart';
import { StatChipRow } from '@/components/StatChipRow';
import { TrendStrip } from '@/components/TrendStrip';
import { type PlayerStatKey, usePlayerTrends } from '@/hooks/usePlayerTrends';
import { chipsForPlayerType, defaultChip } from '@/lib/playerStatChips';
import { todayET } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { PlayerGameLogRow, RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'PlayerStats'>;
// Game-range window. 'season' = every game we loaded (up to 50).
type GameWindow = 5 | 10 | 20 | 'season';

const WINDOWS: { value: GameWindow; label: string }[] = [
  { value: 5, label: 'L5' },
  { value: 10, label: 'L10' },
  { value: 20, label: 'L20' },
  { value: 'season', label: 'Season' },
];

export function PlayerStatsScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation();
  const { playerId, playerName, playerType } = route.params;
  const chips = useMemo(() => chipsForPlayerType(playerType), [playerType]);
  const [statKey, setStatKey] = useState<PlayerStatKey>(() => defaultChip(playerType));
  const [gameWindow, setGameWindow] = useState<GameWindow>(10);
  // The "at least" threshold. null = auto-default to the rounded median once data loads.
  const [line, setLine] = useState<number | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: playerName });
  }, [navigation, playerName]);

  const beforeDate = todayET();
  const { games, values, trends, loading, error } = usePlayerTrends({
    playerId: playerId || null,
    playerName: playerId ? null : playerName,
    beforeDate,
    statKey,
  });

  const currentChip = chips.find((c) => c.key === statKey) ?? chips[0]!;
  const teamLabel = games[0]?.team ?? '—';

  // Reset the line to auto whenever the stat changes — a points line makes no
  // sense for rebounds.
  useEffect(() => {
    setLine(null);
  }, [statKey, playerId]);

  // Values come most-recent-first. Window slices the most recent N.
  const windowed = useMemo(
    () => (gameWindow === 'season' ? values : values.slice(0, gameWindow)),
    [values, gameWindow],
  );

  const { avg, median } = useMemo(() => computeAvgMedian(windowed), [windowed]);
  const maxValue = useMemo(() => (values.length ? Math.max(...values) : 0), [values]);

  // Auto-pick a sensible starting line (rounded median) once, then keep it
  // sticky across window changes until the stat/player changes.
  useEffect(() => {
    if (line == null && median != null) {
      setLine(Math.max(1, Math.round(median)));
    }
  }, [line, median]);

  const effLine = line ?? 0;
  const hits = useMemo(
    () => (line == null ? 0 : windowed.filter((v) => v >= line).length),
    [windowed, line],
  );
  const hitPct = windowed.length > 0 ? hits / windowed.length : 0;
  const hitColor = hitPct >= 0.6 ? colors.bet : hitPct >= 0.45 ? colors.med : colors.avoid;

  const stepLine = (delta: number) => {
    setLine((prev) => {
      const base = prev ?? Math.max(1, Math.round(median ?? 1));
      return Math.min(Math.max(0, base + delta), Math.ceil(maxValue) + 5);
    });
  };

  const windowLabel = gameWindow === 'season' ? `${windowed.length} games` : `last ${gameWindow}`;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list}>
        <View style={styles.header}>
          <Text style={styles.playerName}>{playerName}</Text>
          <Text style={styles.meta}>
            {teamLabel} · {playerType === 'pitcher' ? 'Pitcher' : 'Batter'}
          </Text>
        </View>

        <StatChipRow chips={chips} value={statKey} onChange={setStatKey} />

        {/* Game-range selector */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.windowRow}
        >
          {WINDOWS.map((w) => {
            const active = w.value === gameWindow;
            return (
              <Pressable
                key={String(w.value)}
                onPress={() => setGameWindow(w.value)}
                style={[styles.windowChip, active && styles.windowChipActive]}
              >
                <Text style={[styles.windowChipText, active && styles.windowChipTextActive]}>
                  {w.label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        {error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Connection error: {error}</Text>
          </View>
        ) : null}

        {loading && games.length === 0 ? (
          <ActivityIndicator style={styles.loading} />
        ) : windowed.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>No recent games on file.</Text>
          </View>
        ) : (
          <>
            {/* Hit-rate summary + line stepper */}
            <View style={styles.hitCard}>
              <View style={styles.hitTop}>
                <View>
                  <Text style={styles.hitLabel}>
                    {currentChip.label} {effLine}+ · {windowLabel}
                  </Text>
                  <Text style={styles.hitCount}>
                    Hit {hits} of {windowed.length} games
                  </Text>
                </View>
                <View style={[styles.hitBadge, { backgroundColor: hitColor }]}>
                  <Text style={styles.hitBadgeText}>{Math.round(hitPct * 100)}%</Text>
                </View>
              </View>

              <View style={styles.statsRow}>
                <View style={styles.statCell}>
                  <Text style={styles.statCellValue}>{avg != null ? avg.toFixed(1) : '—'}</Text>
                  <Text style={styles.statCellLabel}>Avg</Text>
                </View>
                <View style={styles.statCell}>
                  <Text style={styles.statCellValue}>{median != null ? median.toFixed(1) : '—'}</Text>
                  <Text style={styles.statCellLabel}>Median</Text>
                </View>
                <View style={styles.stepper}>
                  <Text style={styles.stepperLabel}>At least</Text>
                  <Pressable
                    onPress={() => stepLine(-1)}
                    hitSlop={8}
                    style={styles.stepBtn}
                  >
                    <Ionicons name="remove" size={18} color={colors.tint} />
                  </Pressable>
                  <Text style={styles.stepValue}>{effLine}</Text>
                  <Pressable
                    onPress={() => stepLine(1)}
                    hitSlop={8}
                    style={styles.stepBtn}
                  >
                    <Ionicons name="add" size={18} color={colors.tint} />
                  </Pressable>
                </View>
              </View>

              <HitRateChart values={windowed} line={effLine} avg={avg} median={median} />

              <View style={styles.legendRow}>
                <View style={styles.legendItem}>
                  <View style={[styles.legendDot, { backgroundColor: colors.bet }]} />
                  <Text style={styles.legendText}>Hit ({effLine}+)</Text>
                </View>
                <View style={styles.legendItem}>
                  <View style={[styles.legendDot, { backgroundColor: colors.avoid }]} />
                  <Text style={styles.legendText}>Under</Text>
                </View>
              </View>
            </View>

            <TrendStrip
              title={`${currentChip.label} — rolling averages`}
              trends={trends}
              mode="player"
              unit={currentChip.label}
            />

            <Text style={styles.sectionHeader}>Recent games</Text>
            {games.map((g) => (
              <GameRow
                key={g.game_id}
                row={g}
                statKey={statKey}
                statLabel={currentChip.label}
                line={effLine}
              />
            ))}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function computeAvgMedian(values: number[]): { avg: number | null; median: number | null } {
  if (values.length === 0) return { avg: null, median: null };
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median =
    sorted.length % 2 === 1 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
  return { avg, median };
}

function GameRow({
  row,
  statKey,
  statLabel,
  line,
}: {
  row: PlayerGameLogRow;
  statKey: PlayerStatKey;
  statLabel: string;
  line: number;
}) {
  const num = extractNumeric(row, statKey);
  const value = num == null ? '—' : String(num);
  const hit = num != null && num >= line;
  return (
    <View style={styles.gameRow}>
      <View style={styles.gameDot}>
        {num != null ? (
          <View
            style={[styles.dot, { backgroundColor: hit ? colors.bet : colors.avoid }]}
          />
        ) : null}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.gameDate}>{row.game_date}</Text>
        <Text style={styles.gameMeta}>
          {row.team} · {statKey === 'outs' ? `${row.innings_pitched ?? '—'} IP` : `${row.at_bats ?? '—'} AB`}
        </Text>
      </View>
      <View style={styles.gameStat}>
        <Text style={styles.gameStatValue}>{value}</Text>
        <Text style={styles.gameStatLabel}>{statLabel}</Text>
      </View>
    </View>
  );
}

function extractNumeric(row: PlayerGameLogRow, key: PlayerStatKey): number | null {
  if (key === 'outs') {
    const ip = row.innings_pitched;
    if (ip == null) return null;
    const whole = Math.floor(ip);
    const frac = Math.round((ip - whole) * 10);
    return whole * 3 + frac;
  }
  const v = (row as unknown as Record<string, number | null>)[key];
  return v == null ? null : v;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { paddingBottom: spacing.xl },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  playerName: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  meta: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
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
  hitCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  hitTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  hitLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  hitCount: {
    fontSize: font.size.headline,
    color: colors.textPrimary,
    fontWeight: font.weight.bold,
    marginTop: 2,
  },
  hitBadge: {
    minWidth: 56,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    alignItems: 'center',
  },
  hitBadgeText: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.lg,
  },
  statCell: {
    alignItems: 'center',
  },
  statCellValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  statCellLabel: {
    fontSize: 10,
    color: colors.textTertiary,
    marginTop: 1,
  },
  stepper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: spacing.sm,
  },
  stepperLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginRight: spacing.xs,
  },
  stepBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepValue: {
    minWidth: 26,
    textAlign: 'center',
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  legendRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: spacing.lg,
    marginTop: spacing.sm,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  sectionHeader: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  gameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  gameDot: {
    width: 16,
    alignItems: 'center',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  gameDate: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  gameMeta: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  gameStat: {
    alignItems: 'flex-end',
  },
  gameStatValue: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  gameStatLabel: {
    fontSize: 10,
    color: colors.textTertiary,
    marginTop: 1,
  },
  emptyCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  loading: { marginVertical: spacing.xxl },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: 8,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },
});

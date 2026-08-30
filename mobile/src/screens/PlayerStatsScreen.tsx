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
import { PlayerNewsButton } from '@/components/PlayerNewsButton';
import { TrendStrip } from '@/components/TrendStrip';
import { usePlayerNews } from '@/hooks/usePlayerNews';
import { usePlayerTrends } from '@/hooks/usePlayerTrends';
import {
  chipGroupsFor,
  chipsForPlayer,
  defaultChipForPlayer,
  gameContextLine,
  lineStepFor,
  logStatValue,
  playerSubtitle,
  roundLineToStep,
  windowOptionsFor,
  type GameWindow,
  type PlayerLogEntry,
  type PlayerLogSport,
} from '@/lib/playerLog';
import type { StatDef } from '@/lib/statCatalog';
import { todayET } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'PlayerStats'>;

export function PlayerStatsScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation();
  const { playerId, playerName, playerType } = route.params;
  // Older navigation state (a screen restored from a build before player detail
  // went multi-sport) carries no sport — MLB was the only one that could open it.
  const sport: PlayerLogSport = route.params.sport ?? 'MLB';

  const chips = useMemo(() => chipsForPlayer(sport, playerType), [sport, playerType]);
  const groups = useMemo(() => chipGroupsFor(sport, playerType), [sport, playerType]);
  const [stat, setStat] = useState<StatDef | null>(() => defaultChipForPlayer(sport, playerType));
  const windows = useMemo(() => windowOptionsFor(sport), [sport]);
  const [gameWindow, setGameWindow] = useState<GameWindow>(10);
  // The "at least" threshold. null = auto-default to the rounded median once data loads.
  const [line, setLine] = useState<number | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: playerName });
  }, [navigation, playerName]);

  // Sport/player changed (the screen is reused across pushes) — reset to that
  // sport's default stat and window rather than charting a stat it has no data for.
  useEffect(() => {
    setStat(defaultChipForPlayer(sport, playerType));
    setGameWindow(windows.some((w) => w.value === 10) ? 10 : windows[0]!.value);
  }, [sport, playerType, playerId, windows]);

  const beforeDate = todayET();
  const { games, values, trends, loading, error } = usePlayerTrends({
    playerId: playerId || null,
    playerName: playerId ? null : playerName,
    beforeDate,
    sport,
    stat,
    playerType,
  });

  // Recent news for this player. Independent of the trend load: news failing
  // must never cost the chart, and vice versa.
  const news = usePlayerNews({ sport, playerId: playerId || null, playerName });

  const step = useMemo(() => lineStepFor(stat), [stat]);
  const statLabel = stat?.label ?? '';

  // Reset the line to auto whenever the stat changes — a points line makes no
  // sense for rebounds.
  useEffect(() => {
    setLine(null);
  }, [stat?.key, sport, playerId]);

  // Values come most-recent-first. Window slices the most recent N.
  const windowed = useMemo(
    () => (gameWindow === 'all' ? values : values.slice(0, gameWindow)),
    [values, gameWindow],
  );

  const { avg, median } = useMemo(() => computeAvgMedian(windowed), [windowed]);
  const maxValue = useMemo(() => (values.length ? Math.max(...values) : 0), [values]);

  // Auto-pick a sensible starting line (the median, snapped onto the stepper's
  // grid) once, then keep it sticky across window changes until stat/player changes.
  useEffect(() => {
    if (line == null && median != null) {
      setLine(roundLineToStep(median, step));
    }
  }, [line, median, step]);

  const effLine = line ?? 0;
  const hits = useMemo(
    () => (line == null ? 0 : windowed.filter((v) => v >= line).length),
    [windowed, line],
  );
  const hitPct = windowed.length > 0 ? hits / windowed.length : 0;
  const hitColor = hitPct >= 0.6 ? colors.bet : hitPct >= 0.45 ? colors.med : colors.avoid;

  const stepLine = (deltaSteps: number) => {
    setLine((prev) => {
      const base = prev ?? roundLineToStep(median ?? step, step);
      return Math.min(Math.max(0, base + deltaSteps * step), Math.ceil(maxValue) + step * 5);
    });
  };

  const windowLabel = gameWindow === 'all' ? `${windowed.length} games` : `last ${gameWindow}`;
  const activeGroup = stat?.group ?? groups[0];
  const groupChips = groups.length > 1 ? chips.filter((c) => c.group === activeGroup) : chips;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={styles.playerName}>{playerName}</Text>
            <Text style={styles.meta}>{playerSubtitle(sport, games[0]?.team ?? null, games[0], playerType)}</Text>
          </View>
          {/* Recent news, top right — the sentence behind the number. Hidden
              when the feed has nothing on this player, so the header never
              offers a sheet with nothing in it. */}
          <PlayerNewsButton
            playerName={playerName}
            subtitle={playerSubtitle(sport, games[0]?.team ?? null, games[0], playerType)}
            news={news}
          />
        </View>

        {/* Group tabs — only sports whose stats span several groups (NFL) get a
            row here; one group means the chip row already says everything. */}
        {groups.length > 1 ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.groupTabRow}
          >
            {groups.map((g) => {
              const active = g === activeGroup;
              return (
                <Pressable
                  key={g}
                  onPress={() => {
                    if (active) return;
                    const first = chips.find((c) => c.group === g);
                    if (first) setStat(first);
                  }}
                  style={styles.groupTab}
                >
                  <Text style={[styles.groupTabText, active && styles.groupTabTextActive]}>{g}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
        ) : null}

        {/* Stat selector */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.windowRow}
        >
          {groupChips.map((c) => {
            const active = c.key === stat?.key && c.group === stat?.group;
            return (
              <Pressable
                key={`${c.group}:${String(c.key)}`}
                onPress={() => setStat(c)}
                style={[styles.windowChip, active && styles.windowChipActive]}
              >
                <Text style={[styles.windowChipText, active && styles.windowChipTextActive]}>
                  {c.label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        {/* Game-range selector */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.windowRow}
        >
          {windows.map((w) => {
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
                    {statLabel} {effLine}+ · {windowLabel}
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
              title={`${statLabel} — rolling averages`}
              trends={trends}
              mode="player"
              unit={statLabel}
            />

            <Text style={styles.sectionHeader}>Recent games</Text>
            {games.map((g) => (
              <GameRow
                key={g.game_id}
                row={g}
                sport={sport}
                stat={stat}
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
  sport,
  stat,
  line,
}: {
  row: PlayerLogEntry;
  sport: PlayerLogSport;
  stat: StatDef | null;
  line: number;
}) {
  const num = logStatValue(row, stat);
  // Yardage arrives as a NUMERIC string and can be fractional in nflverse — one
  // decimal at most, so a 78-yard game never renders as 78.0000001.
  const value = num == null ? '—' : String(Math.round(num * 10) / 10);
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
        <Text style={styles.gameMeta}>{gameContextLine(sport, row)}</Text>
      </View>
      <View style={styles.gameStat}>
        <Text style={styles.gameStatValue}>{value}</Text>
        <Text style={styles.gameStatLabel}>{stat?.label ?? ''}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { paddingBottom: spacing.xl },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  headerText: { flex: 1, paddingRight: spacing.md },
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
  groupTabRow: {
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
    paddingTop: spacing.xs,
  },
  groupTab: {
    paddingVertical: 4,
  },
  groupTabText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  groupTabTextActive: {
    color: colors.tint,
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

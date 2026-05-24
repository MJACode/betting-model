import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { RouteProp } from '@react-navigation/native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { StatChipRow } from '@/components/StatChipRow';
import { TrendSparkline } from '@/components/TrendSparkline';
import { TrendStrip } from '@/components/TrendStrip';
import { type PlayerStatKey, usePlayerTrends } from '@/hooks/usePlayerTrends';
import { chipsForPlayerType, defaultChip } from '@/lib/playerStatChips';
import { todayET } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { PlayerGameLogRow, RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'PlayerStats'>;

export function PlayerStatsScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation();
  const { playerId, playerName, playerType } = route.params;
  const chips = useMemo(() => chipsForPlayerType(playerType), [playerType]);
  const [statKey, setStatKey] = useState<PlayerStatKey>(() => defaultChip(playerType));

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

        {error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Connection error: {error}</Text>
          </View>
        ) : null}

        {loading && games.length === 0 ? (
          <ActivityIndicator style={styles.loading} />
        ) : (
          <>
            <TrendStrip
              title={`${currentChip.label} — rolling averages`}
              trends={trends}
              mode="player"
              unit={currentChip.label}
            />
            <View style={styles.sparkWrap}>
              <TrendSparkline
                values={values}
                label={`${currentChip.label} — last ${Math.min(values.length, 20)} games (newest at right)`}
              />
            </View>

            <Text style={styles.sectionHeader}>Recent games</Text>
            {games.length === 0 ? (
              <View style={styles.emptyCard}>
                <Text style={styles.emptyText}>No recent games on file.</Text>
              </View>
            ) : (
              games.map((g) => (
                <GameRow key={g.game_id} row={g} statKey={statKey} statLabel={currentChip.label} />
              ))
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function GameRow({
  row,
  statKey,
  statLabel,
}: {
  row: PlayerGameLogRow;
  statKey: PlayerStatKey;
  statLabel: string;
}) {
  const value = extractDisplayValue(row, statKey);
  return (
    <View style={styles.gameRow}>
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

function extractDisplayValue(row: PlayerGameLogRow, key: PlayerStatKey): string {
  if (key === 'outs') {
    const ip = row.innings_pitched;
    if (ip == null) return '—';
    const whole = Math.floor(ip);
    const frac = Math.round((ip - whole) * 10);
    return String(whole * 3 + frac);
  }
  const v = (row as unknown as Record<string, number | null>)[key];
  return v == null ? '—' : String(v);
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
  sparkWrap: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    alignItems: 'center',
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

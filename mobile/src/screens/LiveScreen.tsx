// LiveScreen — Phase 5 scaffolding for the Live tab.
//
// Renders active games and live (in-play) picks. Empty until the backend live
// pipeline starts writing picks with is_live=true (Phase 4). Until then the
// EmptyState below tells the user the feature is being built.
//
// Layout mirrors the BettingPros-style mock the user shared:
//   - Active games banner row at top (LiveGameBanner per game)
//   - Live picks list underneath (existing PickCard)

import React, { useMemo } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';

import { PickCard } from '@/components/PickCard';
import { EmptyState } from '@/components/EmptyState';
import { LiveGameBanner } from '@/components/LiveGameBanner';
import { SportToggle } from '@/components/SportToggle';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useLivePicks } from '@/hooks/useLivePicks';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { isPlaced, usePlacedPicks } from '@/hooks/usePlacedPicks';
import { colors, font, spacing } from '@/lib/theme';
import { recommendedBet } from '@/lib/thresholds';
import type { EnrichedPick, GameRow, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function LiveScreen() {
  const navigation = useNavigation<Nav>();
  const { data: allData, loading, error, refresh, date } = useLivePicks();
  const { sport } = useSportFilter();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);
  const { overrides, togglePlaced } = usePlacedPicks();

  // Show only the selected sport — WNBA live picks stay separate from MLB.
  const data = useMemo(() => allData.filter((d) => d.pick.sport === sport), [allData, sport]);

  const activeGames = useMemo<GameRow[]>(() => {
    const byId = new Map<string, GameRow>();
    for (const d of data) {
      if (d.game && !byId.has(d.game.game_id)) byId.set(d.game.game_id, d.game);
    }
    return Array.from(byId.values()).sort((a, b) =>
      a.commence_time.localeCompare(b.commence_time)
    );
  }, [data]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Live</Text>
        <Text style={styles.subtitle}>
          {date} · {activeGames.length} active · {data.length} live picks
        </Text>
        <Text style={styles.scheduleNote}>
          Live picks update every 30 seconds while this tab is open.
        </Text>
        <SportToggle />
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {activeGames.length > 0 ? (
        <View style={styles.banners}>
          {activeGames.map((g) => (
            <LiveGameBanner key={g.game_id} game={g} />
          ))}
        </View>
      ) : null}

      <FlatList
        data={data}
        keyExtractor={(item) => String(item.pick.pick_id)}
        renderItem={({ item }) => (
          <PickCard
            item={item}
            bankroll={bankroll}
            kelly={kelly}
            placed={isPlaced(item.pick.pick_id, undefined, overrides)}
            onTogglePlaced={() =>
              togglePlaced(
                item.pick.pick_id,
                item.pick,
                recommendedBet(item.pick.kelly_fraction, bankroll, kelly)
              )
            }
            onPress={() => navigation.navigate('PickDetail', { pickId: item.pick.pick_id })}
          />
        )}
        refreshControl={
          <RefreshControl
            refreshing={loading && data.length > 0}
            onRefresh={refresh}
            tintColor={colors.tint}
          />
        }
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator color={colors.tint} style={{ marginTop: spacing.lg }} />
          ) : (
            <EmptyState
              title="No live picks right now"
              subtitle="In-play scoring is still being built (Phase 4). Live picks will appear here as games progress."
            />
          )
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  title: { color: colors.textPrimary, fontSize: font.size.largeTitle, fontWeight: font.weight.bold },
  subtitle: { color: colors.textSecondary, fontSize: font.size.footnote, marginTop: 2 },
  scheduleNote: { color: colors.textTertiary, fontSize: font.size.footnote, marginTop: 2 },
  banners: { paddingTop: spacing.xs },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    padding: spacing.sm,
    marginHorizontal: spacing.md,
    borderRadius: 8,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },
});

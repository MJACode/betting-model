// LiveScreen — Phase 5 scaffolding for the Live tab.
//
// Renders active games and live (in-play) picks. Empty until the backend live
// pipeline starts writing picks with is_live=true (live loop running). Otherwise the
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
import { SettingsButton } from '@/components/SettingsButton';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useLivePicks } from '@/hooks/useLivePicks';
import { useLiveGameStates } from '@/hooks/useLiveGameStates';
import { useTrackedBets } from '@/hooks/useTrackedBets';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { colors, font, spacing } from '@/lib/theme';
import type { EnrichedPick, GameRow, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function LiveScreen() {
  const navigation = useNavigation<Nav>();
  const { data: allData, loading, error, refresh, date } = useLivePicks();
  const { sport } = useSportFilter();
  const tracked = useTrackedBets();
  // Real score/inning/outs per game, refreshed every 30s alongside the picks.
  const { byGame: liveStates } = useLiveGameStates(date);
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const kelly = useMemo(() => ({ multiplier, cap }), [multiplier, cap]);

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
        <View style={styles.titleRow}>
          <Text style={styles.title}>Live</Text>
          <SettingsButton />
        </View>
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
            <LiveGameBanner key={g.game_id} game={g} live={liveStates.get(g.game_id) ?? null} />
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
            onPress={() => navigation.navigate('PickDetail', { pickId: item.pick.pick_id })}
            tracked={tracked.isTracked(item.pick)}
            onToggleTrack={() => tracked.toggle(item.pick)}
            liveState={liveStates.get(item.pick.game_id) ?? null}
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
              subtitle="Live picks appear when an in-play model finds an edge while the live pipeline is running. Zero live picks is a valid signal."
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
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
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

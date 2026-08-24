// LiveScreen — the Live (in-play) picks board.
//
// Renders live picks only. Empty until the backend live pipeline starts writing
// picks with is_live=true (live loop running).
//
// The board is deliberately picks-only: the active-games banner row that used to
// sit above the list was removed (2026-08-02) because it duplicated the matchup
// already on every card and pushed the actual picks below the fold. Per-game
// score/inning still shows — on the card header itself, via `liveState`.

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
import { SportToggle } from '@/components/SportToggle';
import { SettingsButton } from '@/components/SettingsButton';
import { SportsbookIndicator } from '@/components/SportsbookIndicator';
import { SignalLockCard } from '@/components/SignalLockCard';
import { useSubscription } from '@/hooks/useSubscription';
import { useSportFilter } from '@/hooks/useSportFilter';
import { useLivePicks } from '@/hooks/useLivePicks';
import { useLiveGameStates } from '@/hooks/useLiveGameStates';
import { useTrackedBets } from '@/hooks/useTrackedBets';
import { useBankroll } from '@/hooks/useBankroll';
import { useKellySettings } from '@/hooks/useKellySettings';
import { colors, font, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

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

  // Live picks are BET signals by definition, so the whole tab is paid.
  // `entitled` is true while billing is off, leaving this inert until launch.
  const { entitled } = useSubscription();

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Live</Text>
          <SettingsButton />
        </View>
        <Text style={styles.subtitle}>
          {date} · {data.length} live {data.length === 1 ? 'pick' : 'picks'}
        </Text>
        <Text style={styles.scheduleNote}>
          Live picks update every 30 seconds while this tab is open.
        </Text>
        <SportsbookIndicator />
        <SportToggle />
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {!entitled ? (
        <SignalLockCard
          count={data.length}
          onPress={() => navigation.navigate('Paywall')}
        />
      ) : (
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
      )}
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
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    padding: spacing.sm,
    marginHorizontal: spacing.md,
    borderRadius: 8,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },
});

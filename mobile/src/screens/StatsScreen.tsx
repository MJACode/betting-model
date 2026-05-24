import React, { useMemo, useState } from 'react';
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
import { useNavigation } from '@react-navigation/native';
import { EmptyState } from '@/components/EmptyState';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import { usePlayerSearch } from '@/hooks/usePlayerSearch';
import { MODEL_META } from '@/lib/modelMeta';
import type { PlayerSearchResult } from '@/lib/playerSearch';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick, PlayerType, RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

const PLAYER_NAME_RE = /^([A-Za-z .'\-]+?)\s+(?:Over|Under)\s/;

interface TodayPlayer {
  playerId: string | null;
  playerName: string;
  playerType: PlayerType;
}

function extractTodayPlayers(picks: EnrichedPick[]): TodayPlayer[] {
  const seenIds = new Set<string>();
  const seenNames = new Set<string>();
  const out: TodayPlayer[] = [];
  for (const { pick } of picks) {
    const meta = MODEL_META[pick.model_id];
    if (!meta || (meta.type !== 'batter_prop' && meta.type !== 'pitcher_prop')) continue;
    const playerType: PlayerType = meta.type === 'pitcher_prop' ? 'pitcher' : 'batter';
    if (pick.player_id) {
      if (seenIds.has(pick.player_id)) continue;
      seenIds.add(pick.player_id);
      const m = pick.pick_label.match(PLAYER_NAME_RE);
      out.push({ playerId: pick.player_id, playerName: m ? m[1]! : pick.pick_label, playerType });
    } else {
      const m = pick.pick_label.match(PLAYER_NAME_RE);
      if (!m) continue;
      const name = m[1]!;
      if (seenNames.has(name)) continue;
      seenNames.add(name);
      out.push({ playerId: null, playerName: name, playerType });
    }
  }
  return out;
}

export function StatsScreen() {
  const navigation = useNavigation<Nav>();
  const [query, setQuery] = useState<string>('');
  const { results, loading, error } = usePlayerSearch(query);
  const { data: todayPicks } = useTodayPicks();

  const todayPlayers = useMemo(() => extractTodayPlayers(todayPicks), [todayPicks]);
  const searching = query.trim().length >= 2;

  const openPlayer = (p: { playerId: string | null; playerName: string; playerType: PlayerType }) => {
    navigation.navigate('PlayerStats', {
      playerId: p.playerId ?? '',
      playerName: p.playerName,
      playerType: p.playerType,
    });
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Stats</Text>
        <Text style={styles.subtitle}>
          Look up any MLB player's hits, HR, Ks, walks — over last 3 / 5 / 10 / 20 games and season.
        </Text>
      </View>

      <View style={styles.searchWrap}>
        <Ionicons name="search" size={16} color={colors.textTertiary} style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder="Search by player name…"
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

      {!searching && todayPlayers.length > 0 ? (
        <View style={styles.todaySection}>
          <Text style={styles.todayLabel}>TODAY</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.todayRow}
          >
            {todayPlayers.map((p, i) => (
              <Pressable
                key={(p.playerId ?? '') + p.playerName + i}
                onPress={() => openPlayer(p)}
                style={({ pressed }) => [styles.todayChip, pressed && styles.pressed]}
              >
                <Ionicons
                  name={p.playerType === 'pitcher' ? 'baseball-outline' : 'person-outline'}
                  size={13}
                  color={colors.textSecondary}
                />
                <Text style={styles.todayChipText}>{p.playerName}</Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      ) : null}

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>Connection error: {error}</Text>
        </View>
      ) : null}

      <FlatList
        data={searching ? results : []}
        keyExtractor={(item) => item.playerId}
        renderItem={({ item }) => <PlayerRow result={item} onPress={() => openPlayer(item)} />}
        ListEmptyComponent={
          searching ? (
            loading ? (
              <ActivityIndicator style={styles.loading} />
            ) : (
              <EmptyState
                title="No players found"
                subtitle={`Nothing matched "${query.trim()}". Try a different spelling.`}
              />
            )
          ) : (
            <View style={styles.helpBlock}>
              <Text style={styles.helpHeading}>How this works</Text>
              <Text style={styles.helpBody}>
                Type a player's name (first or last). After two characters we search the full game log and show every
                player who matches. Tap a player to see their hits, HRs, Ks, walks and more over the last 3 / 5 / 10 /
                20 games and the season.
              </Text>
            </View>
          )
        }
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
      />
    </SafeAreaView>
  );
}

function PlayerRow({ result, onPress }: { result: PlayerSearchResult; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      <View style={styles.rowIconWrap}>
        <Ionicons
          name={result.playerType === 'pitcher' ? 'baseball-outline' : 'person-outline'}
          size={20}
          color={colors.tint}
        />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowName}>{result.playerName}</Text>
        <Text style={styles.rowMeta}>
          {result.team ?? '—'} · {result.playerType === 'pitcher' ? 'Pitcher' : 'Batter'}
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
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
  searchIcon: {},
  searchInput: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    paddingVertical: 2,
  },
  todaySection: {
    marginTop: spacing.md,
  },
  todayLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.xs,
  },
  todayRow: {
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  todayChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  todayChipText: {
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
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
  rowIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
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
  pressed: { opacity: 0.65 },
  helpBlock: {
    marginHorizontal: spacing.lg,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
  },
  helpHeading: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  helpBody: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    lineHeight: 22,
  },
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

import React, { useCallback } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ByomModelRow } from '@/components/byom/ByomModelRow';
import { ByomSeasonToggle } from '@/components/byom/ByomSeasonToggle';
import { ByomUnitsNote } from '@/components/byom/ByomUnitsNote';
import { EmptyState } from '@/components/EmptyState';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { Skeleton, SkeletonRow } from '@/components/Skeleton';
import { useByomLeaderboard } from '@/hooks/useByomLeaderboard';
import { useByomSeason } from '@/hooks/useByomSeason';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Sport } from '@/hooks/useSportFilter';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function ByomModelList({ sport }: { sport: Sport }) {
  const navigation = useNavigation<Nav>();
  const { scope } = useByomSeason();
  const nfl = sport === 'NFL';
  const { rows, loading, error, reload, signedIn, authReady } = useByomLeaderboard(sport, scope);
  const busy = nfl && (!authReady || (signedIn && loading && rows.length === 0));
  const failedRefresh = error != null && rows.length > 0;

  useFocusEffect(useCallback(() => {
    void reload();
  }, [reload]));

  const openBuilder = () => navigation.navigate('ByomBuilder');

  return (
    <FlatList
      style={styles.list}
      data={busy ? [] : rows}
      keyExtractor={(item) => item.model.model_id}
      contentContainerStyle={styles.content}
      refreshControl={nfl ? (
        <RefreshControl
          refreshing={loading && rows.length > 0}
          onRefresh={() => void reload()}
        />
      ) : undefined}
      ListHeaderComponent={nfl ? (
        <View>
          {failedRefresh ? (
            <ErrorBanner
              what="your NFL models"
              error={error}
              onRetry={() => void reload()}
              retrying={loading}
            />
          ) : null}
          <View style={styles.toggleWrap}>
            <ByomSeasonToggle />
          </View>
          {!busy && rows.length > 0 ? (
            <View style={styles.countRow}>
              <Text style={styles.count}>
                {rows.length} NFL model{rows.length === 1 ? '' : 's'} · yours only
              </Text>
              <Text style={styles.sort}>Most units</Text>
            </View>
          ) : null}
        </View>
      ) : null}
      renderItem={({ item }) => (
        <ByomModelRow
          rank={item.rank}
          name={item.model.name}
          filters={item.model.filters}
          record={item.record}
          showsUnits={item.showsUnits}
          ungraded={item.ungraded}
          failed={item.failed}
          onPress={() => navigation.navigate('ByomDetail', { modelId: item.model.model_id })}
        />
      )}
      ListEmptyComponent={
        busy ? (
          <Skeleton label={`${sport} models`}>
            {[0, 1, 2].map((i) => (
              <View key={i} style={styles.skeletonCard}>
                <SkeletonRow />
              </View>
            ))}
          </Skeleton>
        ) : error && rows.length === 0 ? (
          <ErrorState
            what={nfl ? 'your NFL models' : `your ${sport} models`}
            error={error}
            onRetry={() => void reload()}
            retrying={loading}
          />
        ) : nfl && !signedIn ? (
          <EmptyState
            title="Sign in to see your models"
            subtitle="Saving needs a signed-in account."
            actionLabel={AUTH_ENABLED ? 'Sign in' : undefined}
            onAction={AUTH_ENABLED ? () => navigation.navigate('SignIn') : undefined}
          />
        ) : nfl ? (
          <EmptyState
            title="No NFL models yet"
            subtitle="Pick a bet type and a side, then see how it would have done before you save it."
          />
        ) : (
          <EmptyState
            title={`No ${sport} models yet`}
            subtitle="Switch to NFL to build a model."
          />
        )
      }
      ListFooterComponent={
        <>
          {nfl ? (
            <View style={styles.noteWrap}>
              <ByomUnitsNote />
            </View>
          ) : null}
          {nfl ? (
            <Pressable
              onPress={openBuilder}
              accessibilityRole="button"
              accessibilityLabel="Build an NFL model"
              style={({ pressed }) => [styles.build, pressed && styles.pressed]}
            >
              <Text style={styles.buildText}>+ Build an NFL model</Text>
            </Pressable>
          ) : null}
          <BetslipBarSpacer />
        </>
      }
    />
  );
}

const styles = StyleSheet.create({
  list: { flex: 1 },
  content: {
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
  },
  toggleWrap: {
    marginHorizontal: spacing.lg,
  },
  noteWrap: {
    marginHorizontal: spacing.lg,
  },
  countRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  count: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  sort: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  skeletonCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  build: {
    minHeight: 44,
    marginHorizontal: spacing.lg,
    marginTop: spacing.lg,
    borderRadius: radii.md,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  buildText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  pressed: { opacity: 0.7 },
});

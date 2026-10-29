import React, { useCallback, useLayoutEffect } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ByomPreviewCard } from '@/components/byom/ByomPreviewCard';
import { ByomSeasonToggle } from '@/components/byom/ByomSeasonToggle';
import { ByomUnitsNote } from '@/components/byom/ByomUnitsNote';
import { EmptyState } from '@/components/EmptyState';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { Skeleton } from '@/components/Skeleton';
import { useByomRecord } from '@/hooks/useByomRecord';
import { useByomSavedModel } from '@/hooks/useByomSavedModel';
import { useByomSeason } from '@/hooks/useByomSeason';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { deleteByomModel } from '@/lib/byom';
import { friendlyCause, isAbortError } from '@/lib/errors';
import { isPropMarket, isWholeSeason, marketLabel, showsUnits, type ByomSport } from '@/lib/byomRecord';
import { propFilterSummary } from '@/lib/byomPropFilters';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'ByomDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function ByomDetailScreen() {
  const navigation = useNavigation<Nav>();
  const { modelId } = useRoute<Route>().params;
  const { scope } = useByomSeason();
  const { model, loading, error, missing, reload, signedIn } = useByomSavedModel(modelId);
  const graded = model != null && !isWholeSeason(model.filters);
  const sport: ByomSport = model?.sport === 'NBA' ? 'NBA' : 'NFL';
  const filterMarket = model?.filters.markets?.[0] ?? null;
  const filterLine = model == null || !isPropMarket(filterMarket)
    ? null
    : propFilterSummary(model.filters, sport, filterMarket);
  const preview = useByomRecord(scope, graded && model ? model.filters : null, sport);

  useFocusEffect(useCallback(() => {
    void reload();
  }, [reload]));

  useLayoutEffect(() => {
    navigation.setOptions({
      title: model?.name ?? 'Model',
      headerBackTitle: 'My models',
      headerRight: model == null ? undefined : () => (
        <Pressable
          onPress={() => navigation.navigate('ByomEdit', { modelId })}
          accessibilityRole="button"
          accessibilityLabel={`Edit ${model.name}`}
          style={styles.headerBtn}
        >
          <Text style={styles.headerBtnText}>Edit</Text>
        </Pressable>
      ),
    });
  }, [navigation, model, modelId]);

  const remove = () => {
    if (model == null) return;
    Alert.alert('Delete this model?', model.name, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          void (async () => {
            try {
              await deleteByomModel(model.model_id);
              navigation.goBack();
            } catch (e: unknown) {
              if (isAbortError(e)) return;
              Alert.alert('Couldn’t delete this model', friendlyCause(e));
            }
          })();
        },
      },
    ]);
  };

  const showSkeleton = loading && model == null && error == null;

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
    <ScrollView style={styles.flex} contentContainerStyle={styles.content}>
      {showSkeleton ? (
          <Skeleton label="this model">
          <View style={styles.skel} />
        </Skeleton>
      ) : error && model == null ? (
        <ErrorState
          what="this model"
          error={error}
          onRetry={() => void reload()}
        />
      ) : !signedIn ? (
        <EmptyState
          title="Sign in to open this model"
          subtitle={AUTH_ENABLED ? undefined : 'Saving needs a signed-in account.'}
          actionLabel={AUTH_ENABLED ? 'Sign in' : undefined}
          onAction={AUTH_ENABLED ? () => navigation.navigate('SignIn') : undefined}
        />
      ) : missing || model == null ? (
        <EmptyState title="This model is no longer saved" />
      ) : (
        <>
          {error ? (
            <ErrorBanner
              what="this model"
              error={error}
              onRetry={() => void reload()}
              retrying={loading}
              style={styles.banner}
            />
          ) : null}
          <Text style={styles.market}>{marketLabel(model.filters)}</Text>
          {filterLine ? <Text style={styles.filters}>{filterLine}</Text> : null}
          <ByomSeasonToggle />
          <ByomPreviewCard
            record={preview.record}
            loading={graded && preview.loading}
            error={graded ? preview.error : null}
            onRetry={() => void preview.reload()}
            showsUnits={showsUnits(model.filters)}
            emptyLabel={graded ? 'No games match' : '—'}
          />
          <ByomUnitsNote />
          <Pressable
            onPress={remove}
            accessibilityRole="button"
            accessibilityLabel={`Delete ${model.name}`}
            style={styles.delete}
          >
            <Text style={styles.deleteText}>Delete model</Text>
          </Pressable>
        </>
      )}
      <BetslipBarSpacer />
    </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  content: { padding: spacing.lg },
  banner: { marginHorizontal: 0 },
  market: {
    marginTop: spacing.xs,
    marginBottom: spacing.sm,
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  filters: {
    marginBottom: spacing.lg,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  delete: {
    minHeight: 44,
    marginTop: spacing.xl,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.avoidInk,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bgCard,
  },
  deleteText: {
    color: colors.avoidInk,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  headerBtn: {
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: spacing.sm,
  },
  headerBtnText: {
    color: colors.tint,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
  },
  skel: {
    height: 120,
    backgroundColor: colors.noneSoft,
    borderRadius: radii.lg,
  },
});

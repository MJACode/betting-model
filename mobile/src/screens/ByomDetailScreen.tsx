import React, { useCallback, useLayoutEffect } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ByomPreviewCard } from '@/components/byom/ByomPreviewCard';
import { ByomAlertToggle } from '@/components/byom/ByomAlertToggle';
import { ByomOpenBetsSection } from '@/components/byom/ByomOpenBetsSection';
import { useByomOpenBets } from '@/hooks/useByomOpenBets';
import { useMembership } from '@/hooks/useMembership';
import { ByomSeasonToggle } from '@/components/byom/ByomSeasonToggle';
import { ByomSeasonBreakdown } from '@/components/byom/ByomSeasonBreakdown';
import { currentByomSeason } from '@/lib/byomRecord';
import { ByomUnitsNote } from '@/components/byom/ByomUnitsNote';
import { EmptyState } from '@/components/EmptyState';
import { PremiumLock } from '@/components/PremiumLock';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { Skeleton } from '@/components/Skeleton';
import { useByomRecord } from '@/hooks/useByomRecord';
import { useByomSavedModel } from '@/hooks/useByomSavedModel';
import { useByomSeason } from '@/hooks/useByomSeason';
import { useNbaGameFacts } from '@/hooks/useNbaGameFacts';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { byomBetsAvailable, deleteByomModel } from '@/lib/byom';
import { friendlyCause, isAbortError } from '@/lib/errors';
import { isPropMarket, isWholeSeason, marketLabel, showsUnits, byomEmptyLabel, type ByomSport, asByomSport } from '@/lib/byomRecord';
import { propFilterSummary } from '@/lib/byomPropFilters';
import { HEADER_ITEM_HEIGHT, HEADER_TEXT_MAX_FONT_MULTIPLIER } from '@/lib/stackBack';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'ByomDetail'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function ByomDetailScreen() {
  const navigation = useNavigation<Nav>();
  const { modelId } = useRoute<Route>().params;
  const { scope } = useByomSeason();
  const { model, loading, error, noAccess, missing, reload, signedIn } = useByomSavedModel(modelId);
  const graded = model != null && !isWholeSeason(model.filters);
  const sport: ByomSport = asByomSport(model?.sport);
  const filterMarket = model?.filters.markets?.[0] ?? null;
  // Game models show their sheet and trend filters too (UX review, 2026-11-05).
  const filterLine = model == null || filterMarket == null
    ? null
    : propFilterSummary(model.filters, sport, filterMarket);
  const facts = useNbaGameFacts(model == null ? null : sport);
  const preview = useByomRecord(scope, graded && model ? model.filters : null, sport);
  // Open bets and alerts: NFL (Matt, 2026-11-25) and NCAAB (2026-11-26).
  // Members only (Matt, 2026-11-26), the same gate as Picks: a locked member
  // sees no open bets and no alert switch. The server refuses them too.
  const { contentLocked, hold: membershipHold } = useMembership();
  const alertSportModel = model?.sport === 'NFL' || model?.sport === 'NCAAB';
  const alertsSport = alertSportModel && !contentLocked && !membershipHold;
  const openBets = useByomOpenBets(alertsSport, false);
  // A lapsed member sees why alerts stopped, the way the record says so
  // below (UX review 2026-11-26), not an empty slot.
  const alertsLocked = alertSportModel && !membershipHold
    && (contentLocked || openBets.noAccess);
  const thisModelBets = openBets.bets.filter((b) => b.model_id === modelId);

  const reloadOpenBets = openBets.reload;
  useFocusEffect(useCallback(() => {
    void reload();
    void reloadOpenBets();
  }, [reload, reloadOpenBets]));

  useLayoutEffect(() => {
    navigation.setOptions({
      title: model?.name ?? 'Model',
      headerRight: model == null ? undefined : () => (
        <Pressable
          onPress={() => navigation.navigate('ByomEdit', { modelId })}
          accessibilityRole="button"
          accessibilityLabel={`Edit ${model.name}`}
          accessibilityShowsLargeContentViewer
          accessibilityLargeContentTitle="Edit"
          hitSlop={{ top: 4, bottom: 4 }}
          style={styles.headerBtn}
        >
          <Text style={styles.headerBtnText} maxFontSizeMultiplier={HEADER_TEXT_MAX_FONT_MULTIPLIER}>
            Edit
          </Text>
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
      ) : noAccess && model == null ? (
        <PremiumLock locked>
          <EmptyState title="This model is no longer saved" />
        </PremiumLock>
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
          <Text style={styles.market}>{marketLabel(model.filters, sport)}</Text>
          {filterLine ? <Text style={styles.filters}>{filterLine}</Text> : null}
          {alertsLocked ? (
            <View style={styles.alertsLock}>
              <PremiumLock locked />
            </View>
          ) : null}
          {alertsSport && !openBets.noAccess ? (
            <>
              <ByomOpenBetsSection
                title="Open bets"
                bets={thisModelBets}
                showModel={false}
                inset={false}
                error={openBets.error}
                retrying={openBets.loading}
                onRetry={() => void openBets.reload()}
                emptyText={openBets.available
                  ? 'No open bets. You’ll get an alert when this model finds one.'
                  : undefined}
              />
              <ByomAlertToggle modelId={model.model_id} modelName={model.name} />
            </>
          ) : null}
          <ByomSeasonToggle />
          <PremiumLock locked={graded && preview.noAccess}>
          <ByomPreviewCard
            record={preview.noAccess ? null : preview.record}
            loading={graded && preview.loading}
            error={graded && !preview.noAccess ? preview.error : null}
            onRetry={() => void preview.reload()}
            showsUnits={showsUnits(model.filters)}
            emptyLabel={graded && model ? byomEmptyLabel(sport, facts.status, model.filters) : '—'}
            closeRecord={graded ? preview.closeRecord : null}
            closingHeadline={preview.timing === 'close'}
            onShowBets={graded && !preview.noAccess && byomBetsAvailable() && preview.record != null && preview.record.bets > 0
              ? () => navigation.navigate('ByomBets', {
                filters: model.filters, sport, title: model.name, timing: preview.timing,
              })
              : undefined}
          />
          </PremiumLock>
          <ByomSeasonBreakdown
            record={preview.record}
            seasons={preview.seasons}
            currentSeason={currentByomSeason(sport)}
            showsUnits={showsUnits(model.filters)}
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
  alertsLock: { marginBottom: spacing.lg },
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
  // 36 tall, not 44: the header-slot height (HEADER_ITEM_HEIGHT explains).
  // The 4pt hitSlop is declared, but on RNS 4.16 it may not reach (only the
  // first header view gets taps forwarded), so the target may be 36pt tall.
  headerBtn: {
    height: HEADER_ITEM_HEIGHT,
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
    borderRadius: radii.md,
  },
});

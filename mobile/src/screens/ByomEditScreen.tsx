import React, { useLayoutEffect, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ByomBetCount } from '@/components/byom/ByomBetCount';
import { ByomMarketField, ByomSideFields } from '@/components/byom/ByomFields';
import { ByomFilterSheet } from '@/components/byom/ByomFilterSheet';
import { ByomPreviewCard } from '@/components/byom/ByomPreviewCard';
import {
  ByomMoreFiltersCard,
  ByomPropSideFields,
  type ByomSheetTab,
} from '@/components/byom/ByomPropSideFields';
import { ByomSeasonToggle } from '@/components/byom/ByomSeasonToggle';
import { ByomUnitsNote } from '@/components/byom/ByomUnitsNote';
import { EmptyState } from '@/components/EmptyState';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { Skeleton } from '@/components/Skeleton';
import { useByomRecord } from '@/hooks/useByomRecord';
import { useByomSavedModel } from '@/hooks/useByomSavedModel';
import { useByomSeason } from '@/hooks/useByomSeason';
import { deleteByomModel, fetchByomModels, saveByomModel, type ByomFilters } from '@/lib/byom';
import { errorText, friendlyCause, isAbortError } from '@/lib/errors';
import {
  draftFromFilters,
  filtersForDraft,
  BYOM_MODEL_CAP,
  isPropMarket,
  isWholeSeason,
  type ByomSport,
  marketLabel,
  otherModelWithName,
  propSideAfterMarketChange,
  saveBlockReason,
  sideBlockFromError,
  showsUnits,
  sideForMarket,
  type ByomMarket,
  type ByomPropSide,
} from '@/lib/byomRecord';
import { EMPTY_PROP_FILTERS, type ByomPropFilterState } from '@/lib/byomPropFilters';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'ByomEdit'>;
type Nav = NativeStackNavigationProp<RootStackParamList>;

export function ByomEditScreen() {
  const navigation = useNavigation<Nav>();
  const { modelId } = useRoute<Route>().params;
  const { scope } = useByomSeason();
  const { model, loading, error, missing, reload, signedIn } = useByomSavedModel(modelId);
  const [name, setName] = useState('');
  const [seeded, setSeeded] = useState(false);
  const [market, setMarket] = useState<ByomMarket | null>(null);
  const [side, setSide] = useState<'home' | 'away' | 'over' | 'under' | null>(null);
  const [role, setRole] = useState<'favorite' | 'underdog' | 'pickem' | null>(null);
  const [primetime, setPrimetime] = useState<boolean | null>(null);
  const [propSide, setPropSide] = useState<ByomPropSide | null>(null);
  const [rest, setRest] = useState<'b2b' | 'rest2' | null>(null);
  const [propFilters, setPropFilters] = useState<ByomPropFilterState>(EMPTY_PROP_FILTERS);
  const [sheet, setSheet] = useState<ByomSheetTab | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useLayoutEffect(() => {
    if (model == null || seeded) return;
    const draft = draftFromFilters(model.filters);
    setName(model.name);
    setMarket(draft?.market ?? null);
    setSide(draft?.side ?? null);
    setRole(draft?.role ?? null);
    setPrimetime(draft?.primetime ?? null);
    setPropSide(draft?.propSide ?? null);
    setRest(draft?.rest ?? null);
    setPropFilters(draft?.propFilters ?? EMPTY_PROP_FILTERS);
    setSeeded(true);
  }, [model, seeded]);

  const sport: ByomSport = model?.sport === 'NBA' ? 'NBA' : 'NFL';
  const edited = market == null
    ? null
    : filtersForDraft(
      {
        market,
        side,
        role,
        primetime,
        propSide,
        rest: sport === 'NBA' ? rest : null,
        propFilters,
      },
      model?.filters ?? {},
      sport,
    );
  const loadedDraft = model == null ? null : draftFromFilters(model.filters);
  const formDraft = market == null
    ? null
    : {
      market,
      side,
      role,
      primetime,
      propSide,
      rest: sport === 'NBA' ? rest : null,
      propFilters,
    };
  const activeDraft = seeded ? formDraft : loadedDraft;
  const sideReason = activeDraft == null ? null : saveBlockReason(activeDraft);
  const previewFilters: ByomFilters | null = sideReason != null
    ? null
    : edited ?? (model != null && !isWholeSeason(model.filters) ? model.filters : null);
  const preview = useByomRecord(scope, previewFilters, sport);
  const unitsVisible = previewFilters != null && showsUnits(previewFilters);
  const previewWaiting = sideReason == null
    && previewFilters != null
    && preview.record == null
    && preview.error == null;
  const trimmed = name.trim();
  const saveDisabled = saving
    || model == null
    || sideReason != null
    || trimmed.length < 1
    || trimmed.length > 80;

  // A new name is a new row. Save it first. Delete the old id only when
  // that save wrote a different row. A cap failure leaves the original.
  const chooseMarket = (next: ByomMarket) => {
    setMarket(next);
    setSide((current) => sideForMarket(next, current));
    setPropSide((current) => propSideAfterMarketChange(market, next, current));
    setPropFilters((current) => ({ ...current, lineBand: null }));
    if (next === 'totals') setRole(null);
    else if (isPropMarket(next)) {
      setRole((current) => (current === 'favorite' || current === 'underdog' ? current : null));
    }
  };

  const save = async (replaceExisting = false) => {
    if (model == null || saveDisabled || sideReason != null) return;
    setSaving(true);
    setSaveMessage(null);
    const filters = edited ?? model.filters;
    const renaming = trimmed !== model.name;
    try {
      if (!replaceExisting) {
        const models = await fetchByomModels();
        const taken = otherModelWithName(models, trimmed, model.model_id);
        if (taken) {
          Alert.alert(
            'Replace this model?',
            renaming
              ? `“${trimmed}” is already saved. Replace overwrites that model, then removes “${model.name}”. Choose another name to keep both.`
              : `“${trimmed}” is already saved. Replace overwrites that model. Choose another name to keep it.`,
            [
              { text: 'Choose another name', style: 'cancel' },
              { text: 'Replace', style: 'destructive', onPress: () => { void save(true); } },
            ],
          );
          return;
        }
        if (renaming && models.length >= BYOM_MODEL_CAP) {
          setSaveMessage('You have 25 models. Delete one before renaming.');
          return;
        }
      }
      const saved = await saveByomModel(trimmed, filters, null, sport);
      const savedId = saved.model_id;
      if (renaming && savedId !== '' && savedId !== model.model_id) {
        try {
          await deleteByomModel(model.model_id);
        } catch (e: unknown) {
          if (isAbortError(e)) return;
          Alert.alert(
            'Saved the new name',
            `“${trimmed}” is saved. The old model is still in your list.`,
            [{ text: 'OK', onPress: () => navigation.goBack() }],
          );
          return;
        }
      }
      navigation.goBack();
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      const raw = errorText(e);
      const blocked = sideBlockFromError(raw);
      setSaveMessage(blocked
        ?? (renaming && /cap is 25/.test(raw)
          ? 'You have 25 models. Delete one before renaming.'
          : /cap is 25/.test(raw)
            ? 'You can save 25 models.'
            : `Couldn’t save this model. ${friendlyCause(e)}`));
    } finally {
      setSaving(false);
    }
  };

  const formReady = model != null && signedIn && !missing;
  const showSkeleton = loading && model == null && error == null;

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 96 : 0}
    >
    <ScrollView
      style={styles.flex}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      {showSkeleton ? (
        <Skeleton label="this model">
          <View style={styles.skel} />
        </Skeleton>
      ) : error && model == null ? (
        <ErrorState what="this model" error={error} onRetry={() => void reload()} />
      ) : !signedIn ? (
        <EmptyState title="Sign in to edit this model" />
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
          <Text style={styles.title}>Edit model</Text>
          <TextInput
            value={name}
            onChangeText={setName}
            maxLength={80}
            accessibilityLabel="Model name"
            autoCorrect={false}
            style={styles.input}
          />
          <Text style={styles.current}>
            {market != null && edited ? marketLabel(edited) : marketLabel(model.filters)}
          </Text>
          {market != null && isPropMarket(market) ? (
            <>
              <ByomPropSideFields
                market={market}
                propSide={propSide}
                role={role}
                primetime={primetime}
                sport={sport}
                rest={rest}
                propFilters={propFilters}
                onPropSide={setPropSide}
                onRole={setRole}
                onPrimetime={setPrimetime}
                onRest={setRest}
                onPropFilters={setPropFilters}
              />
              <ByomMoreFiltersCard
                sport={sport}
                side={side}
                primetime={primetime}
                propFilters={propFilters}
                onOpen={setSheet}
              />
            </>
          ) : null}
          {market != null && !isPropMarket(market) ? (
            <ByomSideFields
              market={market}
              side={side}
              role={role}
              primetime={primetime}
              propSide={propSide}
              sport={sport}
              rest={rest}
              onSide={setSide}
              onRole={setRole}
              onPrimetime={setPrimetime}
              onPropSide={setPropSide}
              onRest={setRest}
            />
          ) : null}
          <ByomMarketField market={market} onChange={chooseMarket} sport={sport} />
          {sideReason == null ? (
            <>
              <ByomSeasonToggle />
              {market != null && isPropMarket(market) ? (
                <ByomBetCount
                  record={preview.record}
                  loading={preview.loading || previewWaiting}
                  error={previewFilters != null ? preview.error : null}
                  onRetry={() => void preview.reload()}
                  showsUnits={unitsVisible}
                />
              ) : (
              <ByomPreviewCard
                record={preview.record}
                loading={preview.loading || previewWaiting}
                error={previewFilters != null ? preview.error : null}
                onRetry={() => void preview.reload()}
                showsUnits={unitsVisible}
                emptyLabel={previewFilters == null ? '—' : 'No games match'}
              />
              )}
              <ByomUnitsNote />
            </>
          ) : null}
        </>
      )}
      <BetslipBarSpacer />
    </ScrollView>
    {formReady ? (
      <>
        {sideReason ? (
          <Text style={styles.saveMessage} accessibilityLiveRegion="polite">{sideReason}</Text>
        ) : null}
        {saveMessage ? <Text style={styles.saveMessage}>{saveMessage}</Text> : null}
        <View style={styles.footer}>
          <Pressable
            onPress={() => void save()}
            disabled={saveDisabled}
            accessibilityRole="button"
            accessibilityLabel="Save model"
            accessibilityHint={sideReason ?? undefined}
            accessibilityState={{ disabled: saveDisabled }}
            style={[styles.primary, saveDisabled && styles.primaryDisabled]}
          >
            <Text style={[styles.primaryText, saveDisabled && styles.primaryTextDisabled]}>
              {saving ? 'Saving…' : 'Save model'}
            </Text>
          </Pressable>
        </View>
      </>
    ) : null}
    <BetslipBarSpacer />
    </KeyboardAvoidingView>
    {market != null && isPropMarket(market) ? (
      <ByomFilterSheet
        tab={sheet}
        sport={sport}
        market={market}
        propSide={propSide}
        side={side}
        primetime={primetime}
        propFilters={propFilters}
        record={preview.record}
        loading={preview.loading || previewWaiting}
        error={sideReason == null ? preview.error : null}
        showsUnits={unitsVisible}
        blocked={sideReason}
        onRetry={() => void preview.reload()}
        onClose={() => setSheet(null)}
        onTab={setSheet}
        onSide={setSide}
        onPrimetime={setPrimetime}
        onPropFilters={setPropFilters}
      />
    ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  content: { padding: spacing.lg },
  banner: { marginHorizontal: 0 },
  title: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.lg,
  },
  current: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  input: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.lg,
    fontSize: font.size.body,
    color: colors.textPrimary,
    marginBottom: spacing.lg,
  },
  saveMessage: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.textPrimary,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separatorOpaque,
    backgroundColor: colors.bg,
  },
  primary: {
    minHeight: 44,
    borderRadius: radii.md,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  primaryDisabled: { backgroundColor: colors.noneSoft },
  primaryText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  primaryTextDisabled: { color: colors.textSecondary },
  skel: {
    height: 120,
    backgroundColor: colors.noneSoft,
    borderRadius: radii.lg,
  },
});

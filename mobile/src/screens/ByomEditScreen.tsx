import React, { useEffect, useState } from 'react';
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
import { ByomMarketField, ByomSideFields } from '@/components/byom/ByomFields';
import { ByomPreviewCard } from '@/components/byom/ByomPreviewCard';
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
  isWholeSeason,
  marketLabel,
  otherModelWithName,
  saveBlockReason,
  sideBlockFromError,
  showsUnits,
  sideForMarket,
  type ByomGameMarket,
} from '@/lib/byomRecord';
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
  const [market, setMarket] = useState<ByomGameMarket | null>(null);
  const [side, setSide] = useState<'home' | 'away' | 'over' | 'under' | null>(null);
  const [role, setRole] = useState<'favorite' | 'underdog' | 'pickem' | null>(null);
  const [primetime, setPrimetime] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    if (model == null || seeded) return;
    const draft = draftFromFilters(model.filters);
    setName(model.name);
    setMarket(draft?.market ?? null);
    setSide(draft?.side ?? null);
    setRole(draft?.role ?? null);
    setPrimetime(draft?.primetime ?? null);
    setSeeded(true);
  }, [model, seeded]);

  const edited = market == null
    ? null
    : filtersForDraft({ market, side, role, primetime }, model?.filters ?? {});
  const loadedDraft = model == null ? null : draftFromFilters(model.filters);
  const formDraft = market == null ? null : { market, side, role, primetime };
  const activeDraft = seeded ? formDraft : loadedDraft;
  const sideReason = activeDraft == null ? null : saveBlockReason(activeDraft);
  const previewFilters: ByomFilters | null = sideReason != null
    ? null
    : edited ?? (model != null && !isWholeSeason(model.filters) ? model.filters : null);
  const preview = useByomRecord(scope, previewFilters);
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
  const chooseMarket = (next: ByomGameMarket) => {
    setMarket(next);
    setSide((current) => sideForMarket(next, current));
    if (next === 'totals') setRole(null);
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
      const saved = await saveByomModel(trimmed, filters, null);
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
          {market == null ? (
            <Text style={styles.current}>{marketLabel(model.filters)}</Text>
          ) : null}
          <ByomMarketField market={market} onChange={chooseMarket} />
          {market != null ? (
            <ByomSideFields
              market={market}
              side={side}
              role={role}
              primetime={primetime}
              onSide={setSide}
              onRole={setRole}
              onPrimetime={setPrimetime}
            />
          ) : null}
          {sideReason == null ? (
            <>
              <ByomSeasonToggle />
              <ByomPreviewCard
                record={preview.record}
                loading={preview.loading || previewWaiting}
                error={previewFilters != null ? preview.error : null}
                onRetry={() => void preview.reload()}
                showsUnits={unitsVisible}
                emptyLabel={previewFilters == null ? '—' : 'No games match'}
              />
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

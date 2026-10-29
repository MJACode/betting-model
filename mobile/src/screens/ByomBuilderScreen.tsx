import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
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
import { useAuth } from '@/hooks/useAuth';
import { useByomRecord } from '@/hooks/useByomRecord';
import { useByomSeason } from '@/hooks/useByomSeason';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { fetchByomModels, saveByomModel } from '@/lib/byom';
import { friendlyCause, errorText, isAbortError } from '@/lib/errors';
import {
  betTypeLabel,
  filtersForDraft,
  isPropMarket,
  otherModelWithName,
  propSideAfterMarketChange,
  saveBlockReason,
  sideBlockFromError,
  showsUnits,
  sideForMarket,
  suggestedName,
  type ByomDraft,
  type ByomMarket,
  type ByomPropSide,
  type ByomSport,
} from '@/lib/byomRecord';
import { EMPTY_PROP_FILTERS, type ByomPropFilterState } from '@/lib/byomPropFilters';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type Route = RouteProp<RootStackParamList, 'ByomBuilder'>;

export function ByomBuilderScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const sport: ByomSport = route.params?.sport === 'NBA' ? 'NBA' : 'NFL';
  const { signedIn } = useAuth();
  const { scope } = useByomSeason();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [market, setMarket] = useState<ByomMarket | null>(null);
  const [side, setSide] = useState<'home' | 'away' | 'over' | 'under' | null>(null);
  const [role, setRole] = useState<'favorite' | 'underdog' | 'pickem' | null>(null);
  const [primetime, setPrimetime] = useState<boolean | null>(null);
  const [propSide, setPropSide] = useState<ByomPropSide | null>(null);
  const [rest, setRest] = useState<'b2b' | 'rest2' | null>(null);
  const [propFilters, setPropFilters] = useState<ByomPropFilterState>(EMPTY_PROP_FILTERS);
  const [sheet, setSheet] = useState<ByomSheetTab | null>(null);
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const suggestion = useRef('');
  const scrollRef = useRef<ScrollView>(null);

  const draft: ByomDraft | null = market == null
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
  const sideReason = draft == null ? null : saveBlockReason(draft);
  const filters = draft == null ? null : filtersForDraft(draft, {}, sport);
  const previewFilters = step === 1 || sideReason != null ? null : filters;
  const preview = useByomRecord(step === 1 ? 'current' : scope, previewFilters, sport);

  useLayoutEffect(() => {
    navigation.setOptions({
      title: sport === 'NBA' ? 'New NBA model' : 'New NFL model',
      headerLeft: () => (
        <Pressable
          onPress={() => navigation.goBack()}
          accessibilityRole="button"
          accessibilityLabel="Cancel"
          style={styles.headerBtn}
        >
          <Text style={styles.headerBtnText}>Cancel</Text>
        </Pressable>
      ),
    });
  }, [navigation, sport]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  }, [step]);

  useEffect(() => {
    if (step !== 3 || market == null || sideReason != null) return;
    const next = suggestedName({
      market, side, role, primetime, propSide, rest: sport === 'NBA' ? rest : null, propFilters,
    });
    setName((current) => (current.trim() === '' || current === suggestion.current ? next : current));
    suggestion.current = next;
  }, [step, market, side, role, primetime, propSide, rest, propFilters, sideReason, sport]);

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

  const goNext = () => {
    if (step === 1) {
      if (market == null) return;
      setStep(2);
      return;
    }
    if (step === 2) {
      if (sideReason != null) return;
      setStep(3);
    }
  };

  const save = async (replaceExisting = false) => {
    if (draft == null || saving || sideReason != null) return;
    const trimmed = name.trim();
    if (trimmed.length < 1 || trimmed.length > 80) return;
    if (!signedIn) {
      if (AUTH_ENABLED) {
        navigation.navigate('SignIn');
        return;
      }
      setSaveMessage('Saving needs a signed-in account.');
      return;
    }
    setSaving(true);
    setSaveMessage(null);
    try {
      if (!replaceExisting) {
        const taken = otherModelWithName(await fetchByomModels(), trimmed);
        if (taken) {
          Alert.alert(
            'Replace this model?',
            `“${trimmed}” is already saved. Replace overwrites that model. Choose another name to keep it.`,
            [
              { text: 'Choose another name', style: 'cancel' },
              { text: 'Replace', style: 'destructive', onPress: () => { void save(true); } },
            ],
          );
          return;
        }
      }
      await saveByomModel(trimmed, filtersForDraft(draft, {}, sport), null, sport);
      navigation.goBack();
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      const raw = errorText(e);
      const blocked = sideBlockFromError(raw);
      setSaveMessage(blocked
        ?? (/cap is 25/.test(raw)
          ? 'You can save 25 models.'
          : `Couldn’t save this model. ${friendlyCause(e)}`));
    } finally {
      setSaving(false);
    }
  };

  const nextDisabled = (step === 1 && market == null) || (step === 2 && sideReason != null);
  const previewWaiting = sideReason == null
    && previewFilters != null
    && preview.record == null
    && preview.error == null;
  const matchedBets = preview.record?.bets ?? 0;
  const nextLabel = step === 2
    && market != null
    && isPropMarket(market)
    && sideReason == null
    && !preview.loading
    && !previewWaiting
    && preview.error == null
    && matchedBets > 0
    ? `Next · ${matchedBets} bet${matchedBets === 1 ? '' : 's'}`
    : 'Next';
  const saveDisabled = saving
    || sideReason != null
    || name.trim().length < 1
    || name.trim().length > 80;

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 96 : 0}
    >
    <ScrollView
      ref={scrollRef}
      style={styles.flex}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.progressRow}>
        <View style={styles.progress}>
          {[1, 2, 3].map((n) => (
            <View key={n} style={[styles.progressSeg, n <= step && styles.progressOn]} />
          ))}
        </View>
        <Text style={styles.step}>Step {step} of 3</Text>
      </View>
      {step === 1 ? (
        <>
          <Text style={styles.title}>What do you want to bet?</Text>
          <ByomMarketField market={market} onChange={chooseMarket} sport={sport} />
        </>
      ) : null}
      {step === 2 && market != null && isPropMarket(market) ? (
        <>
          <Text style={styles.title}>Which side?</Text>
          <Text style={styles.lead}>
            {betTypeLabel(market)} · every DK-priced {sport} player line that fits.
          </Text>
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
      {step === 2 && market != null && !isPropMarket(market) ? (
        <>
          <Text style={[styles.title, styles.titleTight]}>{betTypeLabel(market)}</Text>
          <Text style={styles.lead}>Which side?</Text>
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
        </>
      ) : null}
      {step === 3 ? (
        <>
          <Text style={styles.title}>Name and save</Text>
          <TextInput
            value={name}
            onChangeText={setName}
            maxLength={80}
            placeholder="Name this model"
            placeholderTextColor={colors.textSecondary}
            accessibilityLabel="Model name"
            autoCorrect={false}
            style={styles.input}
          />
        </>
      ) : null}
      {step > 1 && filters != null && sideReason == null ? (
        <>
          <ByomSeasonToggle />
          {step === 2 && market != null && isPropMarket(market) ? (
            <ByomBetCount
              record={preview.record}
              loading={preview.loading || previewWaiting}
              error={preview.error}
              onRetry={() => void preview.reload()}
              showsUnits={showsUnits(filters)}
            />
          ) : (
            <ByomPreviewCard
              record={preview.record}
              loading={preview.loading || previewWaiting}
              error={preview.error}
              onRetry={() => void preview.reload()}
              showsUnits={showsUnits(filters)}
            />
          )}
          <ByomUnitsNote />
        </>
      ) : null}
      <BetslipBarSpacer />
      </ScrollView>
      {step > 1 && sideReason ? (
        <Text style={styles.saveMessage} accessibilityLiveRegion="polite">{sideReason}</Text>
      ) : null}
      {saveMessage ? <Text style={styles.saveMessage}>{saveMessage}</Text> : null}
      <View style={styles.actions}>
        {step > 1 ? (
          <Pressable
            onPress={() => setStep((step - 1) as 1 | 2)}
            accessibilityRole="button"
            accessibilityLabel="Back"
            style={styles.back}
          >
            <Text style={styles.backText}>Back</Text>
          </Pressable>
        ) : null}
        {step < 3 ? (
          <Pressable
            onPress={goNext}
            disabled={nextDisabled}
            accessibilityRole="button"
            accessibilityLabel={nextLabel}
            accessibilityHint={sideReason ?? undefined}
            accessibilityState={{ disabled: nextDisabled }}
            style={[styles.primary, nextDisabled && styles.primaryDisabled]}
          >
            <Text style={[styles.primaryText, nextDisabled && styles.primaryTextDisabled]}>{nextLabel}</Text>
          </Pressable>
        ) : (
          <Pressable
            onPress={() => void save()}
            disabled={saveDisabled}
            accessibilityRole="button"
            accessibilityLabel={signedIn || !AUTH_ENABLED ? 'Save model' : 'Sign in to save'}
            accessibilityHint={sideReason ?? undefined}
            accessibilityState={{ disabled: saveDisabled }}
            style={[styles.primary, saveDisabled && styles.primaryDisabled]}
          >
            <Text style={[styles.primaryText, saveDisabled && styles.primaryTextDisabled]}>
              {saving ? 'Saving…' : signedIn || !AUTH_ENABLED ? 'Save model' : 'Sign in to save'}
            </Text>
          </Pressable>
        )}
      </View>
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
        showsUnits={filters != null && showsUnits(filters)}
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
  screen: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  flex: {
    flex: 1,
  },
  content: {
    padding: spacing.lg,
  },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  progress: {
    flex: 1,
    flexDirection: 'row',
    gap: spacing.xs,
  },
  progressSeg: {
    flex: 1,
    height: 4,
    borderRadius: radii.xs,
    backgroundColor: colors.separatorOpaque,
  },
  progressOn: {
    backgroundColor: colors.tint,
  },
  step: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  title: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.lg,
  },
  titleTight: {
    marginBottom: spacing.sm,
  },
  lead: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
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
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
  },
  actions: {
    gap: spacing.sm,
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
  primaryDisabled: {
    backgroundColor: colors.noneSoft,
  },
  primaryText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  primaryTextDisabled: {
    color: colors.textSecondary,
  },
  back: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backText: {
    color: colors.tint,
    fontSize: font.size.body,
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
  },
});

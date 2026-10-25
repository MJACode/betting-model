import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
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
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ByomMarketField, ByomSideFields } from '@/components/byom/ByomFields';
import { ByomPreviewCard } from '@/components/byom/ByomPreviewCard';
import { ByomSeasonToggle } from '@/components/byom/ByomSeasonToggle';
import { ByomUnitsNote } from '@/components/byom/ByomUnitsNote';
import { useAuth } from '@/hooks/useAuth';
import { useByomRecord } from '@/hooks/useByomRecord';
import { useByomSeason } from '@/hooks/useByomSeason';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { saveByomModel } from '@/lib/byom';
import { friendlyCause, errorText, isAbortError } from '@/lib/errors';
import {
  filtersForDraft,
  showsUnits,
  suggestedName,
  type ByomDraft,
  type ByomGameMarket,
} from '@/lib/byomRecord';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function ByomBuilderScreen() {
  const navigation = useNavigation<Nav>();
  const { signedIn } = useAuth();
  const { scope } = useByomSeason();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [market, setMarket] = useState<ByomGameMarket | null>(null);
  const [side, setSide] = useState<'home' | 'away' | null>(null);
  const [role, setRole] = useState<'favorite' | 'underdog' | 'pickem' | null>(null);
  const [primetime, setPrimetime] = useState<boolean | null>(null);
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const suggestion = useRef('');
  const scrollRef = useRef<ScrollView>(null);

  const draft: ByomDraft | null = market == null ? null : { market, side, role, primetime };
  const filters = draft == null ? null : filtersForDraft(draft);
  const preview = useByomRecord(step === 1 ? 'current' : scope, step === 1 ? null : filters);

  useLayoutEffect(() => {
    navigation.setOptions({
      title: 'New NFL model',
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
  }, [navigation]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  }, [step]);

  useEffect(() => {
    if (step !== 3 || market == null) return;
    const next = suggestedName({ market, side, role, primetime });
    setName((current) => (current.trim() === '' || current === suggestion.current ? next : current));
    suggestion.current = next;
  }, [step, market, side, role, primetime]);

  const goNext = () => {
    if (step === 1) {
      if (market == null) return;
      setStep(2);
      return;
    }
    if (step === 2) setStep(3);
  };

  const save = async () => {
    if (draft == null || saving) return;
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
      await saveByomModel(trimmed, filtersForDraft(draft), null);
      navigation.goBack();
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      const raw = errorText(e);
      setSaveMessage(/cap is 25/.test(raw)
        ? 'You can save 25 models.'
        : `Couldn’t save this model. ${friendlyCause(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const nextDisabled = step === 1 && market == null;
  const saveDisabled = saving || name.trim().length < 1 || name.trim().length > 80;

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
      <Text style={styles.step}>Step {step} of 3</Text>
      {step === 1 ? (
        <>
          <Text style={styles.title}>What do you want to bet?</Text>
          <ByomMarketField market={market} onChange={setMarket} />
        </>
      ) : null}
      {step === 2 && market != null ? (
        <>
          <Text style={styles.title}>{market === 'totals' ? 'When is kickoff?' : 'Which side?'}</Text>
          <ByomSideFields
            market={market}
            side={side}
            role={role}
            primetime={primetime}
            onSide={setSide}
            onRole={setRole}
            onPrimetime={setPrimetime}
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
      {step > 1 && filters != null ? (
        <>
          <ByomSeasonToggle />
          <ByomPreviewCard
            record={preview.record}
            loading={preview.loading}
            error={preview.error}
            onRetry={() => void preview.reload()}
            showsUnits={showsUnits(filters)}
          />
          <ByomUnitsNote />
        </>
      ) : null}
      <BetslipBarSpacer />
      </ScrollView>
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
            accessibilityLabel="Next"
            accessibilityState={{ disabled: nextDisabled }}
            style={[styles.primary, nextDisabled && styles.primaryDisabled]}
          >
            <Text style={[styles.primaryText, nextDisabled && styles.primaryTextDisabled]}>Next</Text>
          </Pressable>
        ) : (
          <Pressable
            onPress={() => void save()}
            disabled={saveDisabled}
            accessibilityRole="button"
            accessibilityLabel={signedIn || !AUTH_ENABLED ? 'Save model' : 'Sign in to save'}
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
  step: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
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

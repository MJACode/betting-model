import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BILLING_RAIL, PLANS, TRIAL_DAYS, type PlanKey } from '@/lib/billingConfig';
import {
  formatPerMonth,
  monthlyPlan,
  savingsPct,
  trialCopy,
} from '@/lib/billingHelpers';
import { displayPrice } from '@/lib/iapHelpers';
import { fetchLocalizedPrices } from '@/lib/iap';
import { billingErrorMessage, restorePurchases, startCheckout } from '@/lib/billing';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** What a subscription actually buys. Kept honest — no ROI promises. */
const INCLUDED = [
  'Every BET signal, all 8 sports',
  'Recommended stake sized to your bankroll',
  'Live in-play signals as games move',
  'Player props, parlays and same-game builder',
];

export function PaywallScreen() {
  const navigation = useNavigation<Nav>();
  const { signedIn, user } = useAuth();
  const { refresh } = useSubscription();

  const [selected, setSelected] = useState<PlanKey>('semiannual');
  const [busy, setBusy] = useState(false);
  const monthly = useMemo(() => monthlyPlan(), []);

  // On the IAP rail, prefer the store's localized prices — they're what the
  // user is actually charged. Config prices are the fallback (and must match
  // App Store Connect, or the fallback lies). Best-effort: a fetch failure
  // just leaves the config numbers.
  const [storePrices, setStorePrices] = useState<Partial<Record<PlanKey, string>>>({});
  useEffect(() => {
    if (BILLING_RAIL !== 'iap' || !user?.id) return;
    let mounted = true;
    fetchLocalizedPrices(user.id)
      .then((prices) => {
        if (mounted) setStorePrices(prices);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [user?.id]);

  const onSubscribe = useCallback(async () => {
    if (!signedIn || !user?.id) {
      // A subscription belongs to an account — without one there's nothing to
      // attach it to, and the user could never restore it on another device.
      navigation.navigate('SignIn');
      return;
    }
    setBusy(true);
    try {
      const result = await startCheckout(selected, user.id);
      // The durable truth lands via webhook — refresh now and once more a few
      // seconds later so a just-paid user isn't staring at a lock while the
      // webhook is in flight. On IAP, entitledNow is receipt-validated, so we
      // can also close the paywall immediately.
      await refresh();
      setTimeout(() => {
        void refresh();
      }, 4000);
      if (result.entitledNow && navigation.canGoBack()) navigation.goBack();
    } catch (e) {
      Alert.alert('Could not start checkout', billingErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [signedIn, user?.id, selected, navigation, refresh]);

  const onRestore = useCallback(async () => {
    if (!signedIn || !user?.id) {
      navigation.navigate('SignIn');
      return;
    }
    setBusy(true);
    try {
      const restored = await restorePurchases(user.id);
      await refresh();
      Alert.alert(
        restored ? 'Purchases restored' : 'Nothing to restore',
        restored
          ? 'Your subscription is active on this device.'
          : 'No active subscription was found for this App Store account.',
      );
      if (restored && navigation.canGoBack()) navigation.goBack();
    } catch (e) {
      Alert.alert('Could not restore', billingErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [signedIn, user?.id, navigation, refresh]);

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Unlock every signal</Text>
        <Text style={styles.subtitle}>{trialCopy()}</Text>

        <View style={styles.card}>
          {INCLUDED.map((line) => (
            <View key={line} style={styles.includedRow}>
              <Ionicons name="checkmark-circle" size={18} color={colors.bet} />
              <Text style={styles.includedText}>{line}</Text>
            </View>
          ))}
        </View>

        <Text style={styles.sectionLabel}>Choose a plan</Text>

        {PLANS.map((plan) => {
          const active = plan.key === selected;
          const save = savingsPct(plan, monthly);
          return (
            <Pressable
              key={plan.key}
              onPress={() => setSelected(plan.key)}
              style={({ pressed }) => [
                styles.planCard,
                active && styles.planCardActive,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.planRadio}>
                <Ionicons
                  name={active ? 'radio-button-on' : 'radio-button-off'}
                  size={20}
                  color={active ? colors.tint : colors.textTertiary}
                />
              </View>
              <View style={{ flex: 1 }}>
                <View style={styles.planHeader}>
                  <Text style={styles.planName}>{plan.name}</Text>
                  {plan.badge ? (
                    <View style={styles.badge}>
                      <Text style={styles.badgeText}>{plan.badge}</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={styles.planBlurb}>{plan.blurb}</Text>
              </View>
              <View style={styles.planPricing}>
                <Text style={styles.planPrice}>
                  {displayPrice(plan, storePrices[plan.key])}
                </Text>
                {plan.months > 1 ? (
                  <>
                    <Text style={styles.planPerMonth}>{formatPerMonth(plan)}</Text>
                    {save > 0 ? (
                      <Text style={styles.planSave}>Save {save}%</Text>
                    ) : null}
                  </>
                ) : (
                  <Text style={styles.planPerMonth}>per month</Text>
                )}
              </View>
            </Pressable>
          );
        })}

        <Pressable
          onPress={onSubscribe}
          disabled={busy}
          style={({ pressed }) => [
            styles.cta,
            pressed && styles.pressed,
            busy && styles.disabled,
          ]}
        >
          {busy ? (
            <ActivityIndicator color={colors.textInverse} />
          ) : (
            <Text style={styles.ctaText}>
              {signedIn ? `Start ${TRIAL_DAYS}-day free trial` : 'Sign in to start'}
            </Text>
          )}
        </Pressable>

        {BILLING_RAIL === 'iap' ? (
          <Pressable onPress={onRestore} disabled={busy}>
            <Text style={styles.restore}>Restore purchases</Text>
          </Pressable>
        ) : null}

        <Pressable onPress={() => navigation.goBack()} disabled={busy}>
          <Text style={styles.skip}>Not now</Text>
        </Pressable>

        {/* Required disclosure — renewal terms and how to cancel. */}
        <Text style={styles.legal}>
          {BILLING_RAIL === 'iap'
            ? `Your ${TRIAL_DAYS}-day trial is free. After that your plan renews automatically at the price shown until you cancel. Billed through your App Store account; manage or cancel any time in your device's subscription settings or from Settings → Subscription.`
            : `Your ${TRIAL_DAYS}-day trial is free. After that your plan renews automatically at the price shown until you cancel. Cancel any time from Settings → Subscription. Payment is handled by Stripe; we never see your card details.`}
        </Text>
        <Text style={styles.legal}>
          Signalbase publishes model signals for information only. It is not
          betting advice, and past performance does not predict future results.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bgGrouped },
  content: { padding: spacing.lg, gap: spacing.md },
  title: {
    fontFamily: font.family,
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginTop: spacing.md,
  },
  subtitle: {
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  includedRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  includedText: {
    flex: 1,
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  sectionLabel: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    marginTop: spacing.sm,
  },
  planCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  planCardActive: { borderColor: colors.tint },
  planRadio: { width: 22 },
  planHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  planName: {
    fontFamily: font.family,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  badge: {
    backgroundColor: colors.betSoft,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  badgeText: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.bet,
  },
  planBlurb: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  planPricing: { alignItems: 'flex-end' },
  planPrice: {
    fontFamily: font.family,
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  planPerMonth: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  planSave: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.bet,
    marginTop: 2,
  },
  cta: {
    height: 52,
    borderRadius: radii.md,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.sm,
  },
  ctaText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  pressed: { opacity: 0.6 },
  disabled: { opacity: 0.4 },
  restore: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.tint,
    textAlign: 'center',
    paddingVertical: spacing.sm,
  },
  skip: {
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
    paddingVertical: spacing.md,
  },
  legal: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
  },
});

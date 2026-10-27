import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BILLING_RAIL, DEFAULT_PLAN_KEY, PLANS, type PlanKey } from '@/lib/billingConfig';
import {
  paywallCta,
  paywallSubtitle,
  planPriceCaption,
  planTrialLine,
  renewalDisclosure,
} from '@/lib/billingHelpers';
import { displayPrice } from '@/lib/iapHelpers';
import { fetchLocalizedPrices } from '@/lib/iap';
import {
  billingErrorMessage,
  redeemCode,
  restorePurchases,
  startCheckout,
} from '@/lib/billing';
import { accessSourceCopy } from '@/lib/discord';
import { EULA_URL, PRIVACY_URL, TERMS_URL, openLink } from '@/lib/socialLinks';
import { useAuth } from '@/hooks/useAuth';
import { useEntitlement } from '@/hooks/useEntitlement';
import { useMembership } from '@/hooks/useMembership';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;
type PaywallRoute = RouteProp<RootStackParamList, 'Paywall'>;

/** What a subscription buys. The Discord line is paid-only, after the trial. */
const INCLUDED = [
  'Every BET signal, all 7 sports',
  'A recommended stake, in units, on every pick',
  'Live in-play signals as games move',
  'Player props, parlays and same-game builder',
  'The subscriber Discord (paid plans, after the trial)',
];

const PLAN_ORDER: Record<PlanKey, number> = { annual: 0, monthly: 1, weekly: 2 };

/**
 * The paywall. Annual is selected by default and is the only plan with a
 * badge. Weekly's header and button do not offer a trial.
 *
 * No Whop checkout on this screen — the board is the App Store ladder only.
 * The Whop rail stays in the backend.
 */
export function PaywallScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<PaywallRoute>();
  const { signedIn, user } = useAuth();
  const { access, entitled, loading, refresh } = useEntitlement();
  const { subscription } = useMembership();

  const [selected, setSelected] = useState<PlanKey>(DEFAULT_PLAN_KEY);
  const [busy, setBusy] = useState(false);
  const plans = useMemo(
    () => [...PLANS].sort((a, b) => PLAN_ORDER[a.key] - PLAN_ORDER[b.key]),
    [],
  );
  const plan = useMemo(
    () => plans.find((p) => p.key === selected) ?? plans[0],
    [plans, selected],
  );

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

  const dismiss = useCallback(() => {
    if (navigation.canGoBack()) navigation.goBack();
    else navigation.reset({ index: 0, routes: [{ name: 'Tabs' }] });
  }, [navigation]);

  // Only the screen shown right after sign-in closes itself for someone who
  // is already subscribed. Opening the paywall from a lock must stay open.
  useEffect(() => {
    if (!route.params?.autoCloseIfEntitled || loading || !entitled) return;
    dismiss();
  }, [route.params?.autoCloseIfEntitled, loading, entitled, dismiss]);

  const requireSignIn = useCallback((): boolean => {
    if (signedIn && user?.id) return false;
    navigation.navigate('SignIn');
    return true;
  }, [signedIn, user?.id, navigation]);

  const onSubscribe = useCallback(async () => {
    if (requireSignIn() || !user?.id) return;
    setBusy(true);
    try {
      const result = await startCheckout(selected, user.id);
      await refresh();
      setTimeout(() => {
        void refresh();
      }, 4000);
      if (result.entitledNow) dismiss();
    } catch (e) {
      Alert.alert('Could not start checkout', billingErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [requireSignIn, user?.id, selected, dismiss, refresh]);

  const onRestore = useCallback(async () => {
    if (requireSignIn() || !user?.id) return;
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
      if (restored) dismiss();
    } catch (e) {
      Alert.alert('Could not restore', billingErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [requireSignIn, user?.id, dismiss, refresh]);

  const onRedeem = useCallback(async () => {
    if (requireSignIn() || !user?.id) return;
    setBusy(true);
    try {
      const shown = await redeemCode(user.id);
      if (!shown) {
        Alert.alert(
          'Not available here',
          'Offer codes can only be redeemed on iOS. On Android, redeem the code in the Play Store app.',
        );
        return;
      }
      await refresh();
      setTimeout(() => {
        void refresh();
      }, 4000);
    } catch (e) {
      Alert.alert('Could not redeem', billingErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [requireSignIn, user?.id, refresh]);

  // A trial is entitled, so source "app" would say Discord is already included.
  // The checklist above says it comes after the trial. Hide the sentence then.
  const sourceCopy = subscription?.status === 'trialing' ? '' : accessSourceCopy(access);
  const cta = paywallCta(plan);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <View style={styles.frame}>
        <View style={styles.card}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Close paywall"
            onPress={dismiss}
            disabled={busy}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            style={styles.close}
          >
            <Ionicons name="close" size={22} color={colors.textInverse} />
          </Pressable>
          <ScrollView
            style={styles.scroller}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
          <Text style={styles.title}>Unlock every signal</Text>
          <Text style={styles.subtitle}>{paywallSubtitle(plan)}</Text>

          {INCLUDED.map((line) => (
            <View key={line} style={styles.includedRow}>
              <Ionicons name="checkmark" size={16} color={colors.bet} />
              <Text style={styles.includedText}>{line}</Text>
            </View>
          ))}

          {sourceCopy ? <Text style={styles.sourceNote}>{sourceCopy}</Text> : null}

          {plans.map((p) => {
            const active = p.key === selected;
            return (
              <Pressable
                key={p.key}
                onPress={() => setSelected(p.key)}
                accessibilityRole="radio"
                accessibilityState={{ selected: active }}
                accessibilityLabel={`${p.name}, ${planTrialLine(p)}, ${displayPrice(p, storePrices[p.key])}, ${planPriceCaption(p)}`}
                style={[styles.plan, active && styles.planActive]}
              >
                <View style={styles.planTop}>
                  <Ionicons
                    name={active ? 'radio-button-on' : 'radio-button-off'}
                    size={22}
                    color={active ? colors.brand : colors.brandMuted}
                  />
                  <View style={styles.planNameCol}>
                    {p.badge ? (
                      <View style={styles.badge}>
                        <Text style={styles.badgeText}>{p.badge}</Text>
                      </View>
                    ) : null}
                    <Text style={styles.planName}>{p.name}</Text>
                    <Text style={styles.planTrial}>{planTrialLine(p)}</Text>
                  </View>
                  <View style={styles.planPriceCol}>
                    <Text style={styles.planPrice}>{displayPrice(p, storePrices[p.key])}</Text>
                    <Text style={styles.planCaption}>{planPriceCaption(p)}</Text>
                  </View>
                </View>
              </Pressable>
            );
          })}

          <Pressable
            accessibilityLabel={cta}
            accessibilityState={{ busy, disabled: busy }}
            onPress={onSubscribe}
            disabled={busy}
            accessibilityRole="button"
            style={({ pressed }) => [styles.cta, pressed && styles.pressed, busy && styles.disabled]}
          >
            {busy ? (
              <ActivityIndicator color={colors.brandInk} />
            ) : (
              <Text style={styles.ctaText}>{cta}</Text>
            )}
          </Pressable>

          <Text style={styles.legal}>
            {BILLING_RAIL === 'iap'
              ? renewalDisclosure(plan)
              : `${renewalDisclosure(plan)} Payment is handled by Stripe; we never see your card details.`}
          </Text>

          <View style={styles.linkRow}>
            {BILLING_RAIL === 'iap' ? (
              <>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Restore purchases"
                  onPress={onRestore}
                  disabled={busy}
                  hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}
                >
                  <Text style={styles.linkText}>Restore purchases</Text>
                </Pressable>
                {Platform.OS === 'ios' ? (
                  <>
                    <Text style={styles.linkSep}>·</Text>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel="Redeem code"
                      onPress={onRedeem}
                      disabled={busy}
                      hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}
                    >
                      <Text style={styles.linkText}>Redeem code</Text>
                    </Pressable>
                  </>
                ) : null}
                <Text style={styles.linkSep}>·</Text>
              </>
            ) : null}
            <Pressable
              accessibilityRole="link"
              accessibilityLabel="Terms"
              onPress={() => openLink(TERMS_URL, 'Terms')}
              hitSlop={{ top: 12, bottom: 12, left: 4, right: 4 }}
            >
              <Text style={styles.linkText}>Terms</Text>
            </Pressable>
            <Text style={styles.linkSep}>·</Text>
            <Pressable
              accessibilityRole="link"
              accessibilityLabel="Privacy policy"
              onPress={() => openLink(PRIVACY_URL, 'Privacy Policy')}
              hitSlop={{ top: 12, bottom: 12, left: 4, right: 4 }}
            >
              <Text style={styles.linkText}>Privacy</Text>
            </Pressable>
            <Text style={styles.linkSep}>·</Text>
            <Pressable
              accessibilityRole="link"
              accessibilityLabel="EULA"
              onPress={() => openLink(EULA_URL, 'EULA')}
              hitSlop={{ top: 12, bottom: 12, left: 4, right: 4 }}
            >
              <Text style={styles.linkText}>EULA</Text>
            </Pressable>
          </View>
          </ScrollView>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bgGrouped },
  frame: { flex: 1, padding: spacing.lg },
  card: {
    flex: 1,
    backgroundColor: colors.brandNavy,
    borderRadius: radii.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  scroller: { flex: 1 },
  scrollContent: { gap: spacing.sm, paddingBottom: spacing.md },
  close: {
    alignSelf: 'flex-end',
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontFamily: font.family,
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  subtitle: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.brandMuted,
    marginBottom: spacing.sm,
  },
  includedRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  includedText: {
    flex: 1,
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textInverse,
    lineHeight: 18,
  },
  sourceNote: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.brand,
    marginTop: spacing.xs,
  },
  plan: {
    borderRadius: radii.md,
    borderWidth: 2,
    borderColor: colors.brandNavyRaised,
    backgroundColor: colors.brandNavyRaised,
    padding: spacing.md,
    marginTop: spacing.xs,
  },
  planActive: { borderColor: colors.brand },
  planTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  planNameCol: { flex: 1 },
  planPriceCol: { alignItems: 'flex-end' },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.brand,
    borderRadius: radii.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginBottom: 2,
  },
  badgeText: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.brandInk,
    textTransform: 'uppercase',
  },
  planName: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  planTrial: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.brandMuted,
  },
  planPrice: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  planCaption: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.brandMuted,
    textAlign: 'right',
  },
  cta: {
    minHeight: 52,
    borderRadius: radii.md,
    backgroundColor: colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.sm,
  },
  ctaText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.brandInk,
  },
  pressed: { opacity: 0.6 },
  disabled: { opacity: 0.4 },
  legal: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.brandMuted,
    lineHeight: 16,
    marginTop: spacing.xs,
  },
  linkRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  linkText: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.brand,
    textDecorationLine: 'underline',
  },
  linkSep: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.brandMuted,
  },
});

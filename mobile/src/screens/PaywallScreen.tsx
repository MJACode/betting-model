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
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BILLING_RAIL, PLANS, type PlanKey } from '@/lib/billingConfig';
import {
  formatPerMonth,
  monthlyPlan,
  renewalDisclosure,
  savingsPct,
  trialCopy,
} from '@/lib/billingHelpers';
import { displayPrice } from '@/lib/iapHelpers';
import { fetchLocalizedPrices } from '@/lib/iap';
import {
  billingErrorMessage,
  redeemCode,
  restorePurchases,
  startCheckout,
} from '@/lib/billing';
import { WHOP_CHECKOUT_URL, discordLinkReady } from '@/lib/discordConfig';
import { accessSourceCopy } from '@/lib/discord';
import { EULA_URL, PRIVACY_URL, TERMS_URL, openLink } from '@/lib/socialLinks';
import { useAuth } from '@/hooks/useAuth';
import { useEntitlement } from '@/hooks/useEntitlement';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** What a subscription actually buys. Kept honest — no ROI promises. */
const INCLUDED = [
  'Every BET signal, all 8 sports',
  'Recommended stake sized to your bankroll',
  'Live in-play signals as games move',
  'Player props, parlays and same-game builder',
  'The subscriber Discord, included',
];

/**
 * The paywall.
 *
 * Layout mirrors the reference Matt supplied: three plans side by side with the
 * saving called out above the best-value card, one primary CTA, and a footer
 * row of Restore / Redeem / legal links.
 *
 * The second CTA is the DISCORD rail, not a duplicate of the first. One
 * membership covers both surfaces, so someone who would rather buy where the
 * community is can do that and the app comes with it — and someone who already
 * did never sees this screen, because `useEntitlement()` reads the Whop
 * membership as access. The row hides itself when no Whop checkout URL is
 * configured, rather than linking somewhere broken.
 */
export function PaywallScreen() {
  const navigation = useNavigation<Nav>();
  const { signedIn, user } = useAuth();
  const { access, refresh } = useEntitlement();

  const [selected, setSelected] = useState<PlanKey>('monthly');
  const [busy, setBusy] = useState(false);
  const monthly = useMemo(() => monthlyPlan(), []);
  const plan = useMemo(
    () => PLANS.find((p) => p.key === selected) ?? monthly,
    [selected, monthly],
  );

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

  const requireSignIn = useCallback((): boolean => {
    if (signedIn && user?.id) return false;
    // A subscription belongs to an account — without one there's nothing to
    // attach it to, and the user could never restore it on another device.
    navigation.navigate('SignIn');
    return true;
  }, [signedIn, user?.id, navigation]);

  const onSubscribe = useCallback(async () => {
    if (requireSignIn() || !user?.id) return;
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
  }, [requireSignIn, user?.id, selected, navigation, refresh]);

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
      if (restored && navigation.canGoBack()) navigation.goBack();
    } catch (e) {
      Alert.alert('Could not restore', billingErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [requireSignIn, user?.id, navigation, refresh]);

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
      // StoreKit reports nothing back — the entitlement arrives by webhook, so
      // re-read rather than believing anything about what the sheet did.
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

  const sourceCopy = accessSourceCopy(access);
  const showDiscordRail = discordLinkReady() && WHOP_CHECKOUT_URL !== '';

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

        {sourceCopy ? <Text style={styles.sourceNote}>{sourceCopy}</Text> : null}

        {/* Three plans in a row, the way the reference lays them out. Each card
            carries its own price, per-month equivalent and selection dot. */}
        <View style={styles.planRow}>
          {PLANS.map((p) => {
            const active = p.key === selected;
            const save = savingsPct(p, monthly);
            return (
              <Pressable
                key={p.key}
                onPress={() => setSelected(p.key)}
                accessibilityRole="radio"
                accessibilityState={{ selected: active }}
                accessibilityLabel={`${p.name}, ${displayPrice(p, storePrices[p.key])}`}
                style={({ pressed }) => [
                  styles.planCard,
                  active && styles.planCardActive,
                  pressed && styles.pressed,
                ]}
              >
                {/* Badge only when the saving is real. savingsPct is negative
                    for the weekly plan (it costs more per month), and a
                    fabricated badge there would be a lie on a paid screen. */}
                {save > 0 ? (
                  <View style={styles.saveBadge}>
                    <Text style={styles.saveBadgeText}>Save {save}%</Text>
                  </View>
                ) : (
                  <View style={styles.saveBadgeSpacer} />
                )}

                <Text style={styles.planName}>{p.name}</Text>
                <Text style={styles.planPrice}>
                  {displayPrice(p, storePrices[p.key])}
                </Text>
                <Text style={styles.planPerMonth}>
                  {p.key === 'monthly' ? 'per month' : formatPerMonth(p)}
                </Text>

                <View style={styles.planFooter}>
                  <Ionicons
                    name={active ? 'checkmark-circle' : 'ellipse-outline'}
                    size={20}
                    color={active ? colors.tint : colors.textTertiary}
                  />
                </View>
              </Pressable>
            );
          })}
        </View>

        <Pressable
          onPress={onSubscribe}
          disabled={busy}
          accessibilityRole="button"
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
              {!signedIn
                ? 'Sign in to continue'
                : plan.trialDays > 0
                  ? `Start ${plan.trialDays}-day free trial`
                  : 'Continue'}
            </Text>
          )}
        </Pressable>

        {/* The other rail. One membership covers both surfaces, so buying on
            Discord unlocks the app too — see docs/DISCORD_LINKING.md. */}
        {showDiscordRail ? (
          <Pressable
            onPress={() => openLink(WHOP_CHECKOUT_URL, 'Discord membership')}
            disabled={busy}
            accessibilityRole="button"
            style={({ pressed }) => [styles.secondaryCta, pressed && styles.pressed]}
          >
            <Ionicons name="logo-discord" size={18} color={colors.textPrimary} />
            <Text style={styles.secondaryCtaText}>Get access on Discord</Text>
          </Pressable>
        ) : null}

        <View style={styles.linkRow}>
          {BILLING_RAIL === 'iap' ? (
            <>
              <Pressable onPress={onRestore} disabled={busy} hitSlop={8}>
                <Text style={styles.linkText}>Restore Purchases</Text>
              </Pressable>
              {Platform.OS === 'ios' ? (
                <Pressable onPress={onRedeem} disabled={busy} hitSlop={8}>
                  <Text style={styles.linkText}>Redeem Code</Text>
                </Pressable>
              ) : null}
            </>
          ) : null}
        </View>

        <View style={styles.legalRow}>
          <Pressable onPress={() => openLink(TERMS_URL, 'Terms')} hitSlop={8}>
            <Text style={styles.legalLink}>Terms</Text>
          </Pressable>
          <Text style={styles.legalSep}>·</Text>
          <Pressable onPress={() => openLink(PRIVACY_URL, 'Privacy Policy')} hitSlop={8}>
            <Text style={styles.legalLink}>Privacy</Text>
          </Pressable>
          <Text style={styles.legalSep}>·</Text>
          <Pressable onPress={() => openLink(EULA_URL, 'EULA')} hitSlop={8}>
            <Text style={styles.legalLink}>EULA</Text>
          </Pressable>
        </View>

        <Pressable onPress={() => navigation.goBack()} disabled={busy}>
          <Text style={styles.skip}>Not now</Text>
        </Pressable>

        {/* Required disclosure — renewal terms and how to cancel, worded for
            the SELECTED plan. The weekly plan has no trial, and claiming one
            it doesn't have is both untrue and a 3.1.2 rejection. */}
        <Text style={styles.legal}>
          {BILLING_RAIL === 'iap'
            ? `${renewalDisclosure(plan)} Billed through your App Store account; manage or cancel any time in your device's subscription settings or from Settings → Subscription.`
            : `${renewalDisclosure(plan)} Payment is handled by Stripe; we never see your card details.`}
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
  sourceNote: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.bet,
  },
  planRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  planCard: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderWidth: 2,
    borderColor: 'transparent',
    gap: 2,
  },
  planCardActive: { borderColor: colors.tint },
  saveBadge: {
    backgroundColor: colors.betSoft,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  saveBadgeText: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.bet,
  },
  // Keeps the three cards the same height when only one carries a badge.
  saveBadgeSpacer: { height: 18 },
  planName: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
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
    textAlign: 'center',
  },
  planFooter: { marginTop: spacing.xs },
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
  secondaryCta: {
    height: 48,
    flexDirection: 'row',
    gap: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryCtaText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  pressed: { opacity: 0.6 },
  disabled: { opacity: 0.4 },
  linkRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: spacing.sm,
  },
  linkText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
    textDecorationLine: 'underline',
  },
  legalRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing.sm,
  },
  legalLink: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    textDecorationLine: 'underline',
  },
  legalSep: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
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

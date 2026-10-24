import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { BrandMark } from '@/components/BrandMark';
import { useAccess } from '@/hooks/useAccess';
import { useAuth } from '@/hooks/useAuth';
import { useDeviceId } from '@/hooks/useDeviceId';
import { useSubscription } from '@/hooks/useSubscription';
import {
  authErrorMessage,
  isCompleteOtp,
  normalizeOtp,
  sendEmailCode,
  signInWithProvider,
  verifyEmailCode,
} from '@/lib/auth';
import { EMAIL_OTP_LENGTH } from '@/lib/authConfig';
import { openManageSubscription } from '@/lib/billing';
import { isEntitled } from '@/lib/billingHelpers';
import { billingReady } from '@/lib/billingConfig';
import { finishLocalAccountDeletion, runAccountDeletion } from '@/lib/deleteAccount';
import {
  CONFIRM_BODY,
  CONFIRM_TITLE,
  DELETE_ERROR,
  DELETE_PERMANENT,
  DELETE_TITLE,
  DELETED_TOAST,
  LOCAL_INCOMPLETE,
  REAUTH_APPLE_BODY,
  REAUTH_TITLE,
  STAYS_LINE,
  deletedLines,
  providersForUser,
  purchasePlace,
  reauthEmailBody,
  reauthMethod,
  subscriptionNotice,
  type ReauthMethod,
} from '@/lib/deleteAccountHelpers';
import { fallbackManagementUrl } from '@/lib/iapHelpers';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList, 'DeleteAccount'>;
type Phase = 'ready' | 'deleting' | 'error' | 'local' | 'done';

/**
 * Delete account. Option A confirm (the system alert). Re-auth is shown
 * only after delete_my_account() rejects a stale session. The type-DELETE
 * sheet is not used.
 */
export function DeleteAccountScreen() {
  const navigation = useNavigation<Nav>();
  const insets = useSafeAreaInsets();
  const { email, user, signedIn } = useAuth();
  const { access } = useAccess();
  const { subscription } = useSubscription();
  const { deviceId } = useDeviceId();

  const [phase, setPhase] = useState<Phase>('ready');
  const [reauth, setReauth] = useState(false);
  const [code, setCode] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [localRetry, setLocalRetry] = useState(false);
  const [reauthError, setReauthError] = useState<string | null>(null);
  const [reauthBusy, setReauthBusy] = useState(false);
  const sentFor = useRef<string | null>(null);

  const method: ReauthMethod = reauthMethod(providersForUser(user));
  const deleting = phase === 'deleting';
  const locked = deleting || phase === 'local';
  const place = purchasePlace({
    appAccess: access.app_access || isEntitled(subscription),
    whopAccess: access.discord_access,
  });
  const notice = subscriptionNotice(place, Platform.OS);
  const manageLabel =
    place === 'both'
      ? Platform.OS === 'android'
        ? 'Manage Google Play subscription'
        : 'Manage App Store subscription'
      : 'Manage subscription';

  useLayoutEffect(() => {
    navigation.setOptions({
      title: phase === 'local' ? 'Clear this phone' : 'Delete account',
      headerShown: phase !== 'done',
      headerBackVisible: !locked,
      gestureEnabled: !locked,
    });
  }, [navigation, phase, locked]);

  useEffect(() => {
    const sub = navigation.addListener('beforeRemove', (e) => {
      if (locked) e.preventDefault();
    });
    return sub;
  }, [navigation, locked]);

  const run = useCallback(
    async (lastSignInAt: string | null) => {
      setPhase('deleting');
      setReauth(false);
      try {
        const outcome = await runAccountDeletion({
          lastSignInAt,
          deviceId,
        });
        if (outcome.ok) {
          setPhase('done');
          return;
        }
        if (outcome.stale) {
          setPhase('ready');
          setCode('');
          setCodeSent(false);
          setReauthError(null);
          setReauth(true);
          return;
        }
        setPhase(outcome.serverDeleted ? 'local' : 'error');
      } catch {
        setPhase('error');
      }
    },
    [deviceId],
  );

  const retryLocal = useCallback(async () => {
    setLocalRetry(true);
    setPhase('deleting');
    const cleared = await finishLocalAccountDeletion(deviceId);
    setLocalRetry(false);
    setPhase(cleared ? 'done' : 'local');
  }, [deviceId]);

  const ask = useCallback(() => {
    Alert.alert(CONFIRM_TITLE, CONFIRM_BODY, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          void run(user?.last_sign_in_at ?? null);
        },
      },
    ]);
  }, [run, user?.last_sign_in_at]);

  const sendCode = useCallback(async () => {
    if (!email) return;
    setReauthError(null);
    setCodeSent(false);
    setReauthBusy(true);
    try {
      await sendEmailCode(email);
      sentFor.current = email;
      setCodeSent(true);
    } catch (e) {
      setReauthError(authErrorMessage(e));
    } finally {
      setReauthBusy(false);
    }
  }, [email]);

  useEffect(() => {
    if (!reauth || method !== 'email' || !email) return;
    if (sentFor.current === email) {
      setCodeSent(true);
      return;
    }
    void sendCode();
  }, [reauth, method, email, sendCode]);

  const onProvider = useCallback(async () => {
    if (method === 'email') return;
    setReauthError(null);
    setReauthBusy(true);
    try {
      const session = await signInWithProvider(method);
      if (!session) return;
      await run(session.user.last_sign_in_at ?? new Date().toISOString());
    } catch (e) {
      setReauthError(authErrorMessage(e));
    } finally {
      setReauthBusy(false);
    }
  }, [method, run]);

  const onConfirmCode = useCallback(async () => {
    if (!email || !isCompleteOtp(code)) return;
    setReauthError(null);
    setReauthBusy(true);
    try {
      const session = await verifyEmailCode(email, code);
      await run(session.user.last_sign_in_at ?? new Date().toISOString());
    } catch (e) {
      setReauthError(authErrorMessage(e));
    } finally {
      setReauthBusy(false);
    }
  }, [email, code, run]);

  const onManage = useCallback(() => {
    const open = async () => {
      if (billingReady()) {
        await openManageSubscription(user?.id ?? null);
        return;
      }
      await Linking.openURL(fallbackManagementUrl(Platform.OS));
    };
    open().catch(() => {
      const store = Platform.OS === 'android' ? 'the Play Store' : 'the App Store';
      const where = place === 'whop' ? 'Whop' : place === 'both' ? `${store} or Whop` : store;
      Alert.alert('Couldn’t open subscriptions', `Cancel it where you bought it — ${where}.`);
    });
  }, [user?.id, place]);

  const leave = useCallback(() => {
    if (navigation.canGoBack()) navigation.goBack();
  }, [navigation]);

  const continueWithout = useCallback(() => {
    navigation.reset({ index: 0, routes: [{ name: 'Tabs' }] });
  }, [navigation]);

  const signInAgain = useCallback(() => {
    navigation.reset({ index: 1, routes: [{ name: 'Tabs' }, { name: 'SignIn' }] });
  }, [navigation]);

  if (phase === 'done') {
    return (
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <ScrollView contentContainerStyle={styles.success} keyboardShouldPersistTaps="handled">
          <BrandMark size={72} />
          <Text style={styles.wordmark}>Signalbase</Text>
          <Text style={styles.tagline}>Model picks with a public record.</Text>
          <View style={styles.toast} accessibilityRole="alert" accessibilityLiveRegion="polite">
            <Ionicons
              name="checkmark"
              size={18}
              color={colors.textInverse}
              accessible={false}
            />
            <Text style={styles.toastText}>{DELETED_TOAST}</Text>
          </View>
        </ScrollView>
        <View style={styles.footer}>
          <Pressable
            onPress={continueWithout}
            accessibilityRole="button"
            accessibilityLabel="Continue without an account"
            style={({ pressed }) => [styles.quietBtn, pressed && styles.pressed]}
          >
            <Text style={styles.quietText}>Continue without an account</Text>
          </Pressable>
          <Pressable
            onPress={signInAgain}
            accessibilityRole="button"
            accessibilityLabel="Sign in or create an account"
            style={({ pressed }) => [styles.textBtn, pressed && styles.pressed]}
          >
            <Text style={styles.textBtnLabel}>Sign in or create an account</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const primaryLabel = deleting
    ? localRetry
      ? 'Clearing this phone...'
      : 'Deleting your account...'
    : phase === 'error' || phase === 'local'
      ? 'Try again'
      : 'Continue';
  const emailBody =
    reauthBusy && !codeSent
      ? 'Sending a 6-digit code…'
      : codeSent
        ? reauthEmailBody(email ?? 'your email')
        : reauthError
          ? 'The code was not sent.'
          : 'Sending a 6-digit code…';
  const providerApple = method === 'apple';

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {phase === 'error' || phase === 'local' ? (
          <View
            style={phase === 'local' ? styles.localBanner : styles.banner}
            accessibilityRole="alert"
            accessibilityLiveRegion="polite"
          >
            <Text style={phase === 'local' ? styles.localBannerText : styles.bannerText}>
              {phase === 'local' ? LOCAL_INCOMPLETE : DELETE_ERROR}
            </Text>
          </View>
        ) : null}

        {phase === 'local' ? (
          <Text style={styles.title} accessibilityRole="header">
            Finish clearing this phone
          </Text>
        ) : (
          <>
            <Text style={styles.title} accessibilityRole="header">
              {DELETE_TITLE}
            </Text>
            <Text style={styles.permanent}>{DELETE_PERMANENT}</Text>

            <Text style={styles.section}>What gets deleted</Text>
            <View style={styles.card}>
              {deletedLines(email).map((line, i) => (
                <View key={line} style={[styles.row, i > 0 && styles.rowRule]}>
                  <Text style={styles.rowText}>{`- ${line}`}</Text>
                </View>
              ))}
            </View>

            <Text style={styles.section}>What stays</Text>
            <View style={styles.card}>
              <View style={styles.row}>
                <Text style={styles.rowText}>{`- ${STAYS_LINE}`}</Text>
              </View>
            </View>
          </>
        )}

        {notice.show ? (
          <View style={styles.notice}>
            <Text style={styles.noticeKicker}>{notice.kicker}</Text>
            <Text style={styles.noticeBody}>{notice.body}</Text>
            {notice.showManage ? (
              <Pressable
                onPress={onManage}
                disabled={deleting}
                accessibilityRole="button"
                accessibilityLabel={manageLabel}
                accessibilityState={{ disabled: deleting }}
                style={({ pressed }) => [styles.manageBtn, pressed && styles.pressed]}
              >
                <Text style={styles.manageText}>{manageLabel}</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}
      </ScrollView>

      <View style={styles.footer}>
        <Pressable
          onPress={
            phase === 'local'
              ? () => void retryLocal()
              : phase === 'error'
                ? () => void run(user?.last_sign_in_at ?? null)
                : ask
          }
          disabled={deleting}
          accessibilityRole="button"
          accessibilityLabel={primaryLabel}
          accessibilityState={{ disabled: deleting, busy: deleting }}
          accessibilityLiveRegion={deleting ? 'assertive' : 'none'}
          style={({ pressed }) => [
            styles.dangerBtn,
            deleting && styles.dangerBtnBusy,
            pressed && !deleting && styles.pressed,
          ]}
        >
          {deleting ? (
            <ActivityIndicator color={colors.textInverse} style={styles.spinner} />
          ) : null}
          <Text style={styles.dangerText}>{primaryLabel}</Text>
        </Pressable>
        {phase === 'local' ? null : (
          <Pressable
            onPress={leave}
            disabled={deleting}
            accessibilityRole="button"
            accessibilityLabel="Cancel"
            accessibilityState={{ disabled: deleting }}
            style={({ pressed }) => [styles.textBtn, pressed && styles.pressed]}
          >
            <Text style={[styles.textBtnLabel, deleting && styles.textBtnOff]}>Cancel</Text>
          </Pressable>
        )}
      </View>

      <Modal
        visible={reauth && signedIn}
        animationType="slide"
        transparent
        onRequestClose={() => {
          if (!reauthBusy) setReauth(false);
        }}
      >
        <KeyboardAvoidingView
          style={styles.avoider}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.sheetBackdrop}>
            <Pressable
              style={StyleSheet.absoluteFill}
              onPress={() => {
                if (!reauthBusy) setReauth(false);
              }}
              disabled={reauthBusy}
              accessibilityRole="button"
              accessibilityLabel="Cancel"
            />
            {/* Tap target only. VoiceOver reads the rows inside, not this wrapper. */}
            <Pressable
              style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, spacing.lg) }]}
              onPress={() => {}}
              accessible={false}
              accessibilityViewIsModal
            >
              <View
                style={styles.grabber}
                accessibilityElementsHidden
                importantForAccessibility="no-hide-descendants"
              />
              <ScrollView keyboardShouldPersistTaps="handled" bounces={false}>
                <Text style={styles.sheetTitle} accessibilityRole="header">
                  {REAUTH_TITLE}
                </Text>
                <Text style={styles.sheetBody}>
                  {method === 'email' ? emailBody : REAUTH_APPLE_BODY}
                </Text>
                {method === 'email' ? (
                  <TextInput
                    value={code}
                    onChangeText={(raw) => setCode(normalizeOtp(raw))}
                    keyboardType="number-pad"
                    textContentType="oneTimeCode"
                    autoComplete="one-time-code"
                    maxLength={EMAIL_OTP_LENGTH}
                    placeholder="6-digit code"
                    placeholderTextColor={colors.textTertiary}
                    accessibilityLabel="6-digit code"
                    autoFocus
                    onSubmitEditing={() => void onConfirmCode()}
                    style={styles.codeInput}
                  />
                ) : null}
                {reauthError ? (
                  <Text style={styles.reauthError} accessibilityRole="alert">
                    {reauthError}
                  </Text>
                ) : null}
              </ScrollView>
              <View style={styles.sheetActions}>
                {method === 'email' ? (
                  <View style={styles.sheetRow}>
                    <Pressable
                      onPress={() => {
                        sentFor.current = null;
                        void sendCode();
                      }}
                      disabled={reauthBusy}
                      accessibilityRole="button"
                      accessibilityLabel="Send a new code"
                      accessibilityState={{ disabled: reauthBusy }}
                      style={({ pressed }) => [styles.sheetSide, pressed && styles.pressed]}
                    >
                      <Text style={[styles.sheetSideText, reauthBusy && styles.textBtnOff]}>
                        Send a new code
                      </Text>
                    </Pressable>
                    <Pressable
                      onPress={() => void onConfirmCode()}
                      disabled={reauthBusy || !isCompleteOtp(code)}
                      accessibilityRole="button"
                      accessibilityLabel="Confirm"
                      accessibilityState={{
                        disabled: reauthBusy || !isCompleteOtp(code),
                        busy: reauthBusy,
                      }}
                      style={({ pressed }) => [styles.sheetSide, pressed && styles.pressed]}
                    >
                      {reauthBusy ? (
                        <ActivityIndicator color={colors.tint} />
                      ) : (
                        <Text
                          style={[
                            styles.sheetConfirm,
                            !isCompleteOtp(code) && styles.textBtnOff,
                          ]}
                        >
                          Confirm
                        </Text>
                      )}
                    </Pressable>
                  </View>
                ) : (
                  <Pressable
                    onPress={() => void onProvider()}
                    disabled={reauthBusy}
                    accessibilityRole="button"
                    accessibilityLabel={
                      providerApple ? 'Continue with Apple' : 'Continue with Google'
                    }
                    accessibilityState={{ disabled: reauthBusy, busy: reauthBusy }}
                    style={({ pressed }) => [
                      styles.providerBtn,
                      providerApple ? styles.appleBtn : styles.googleBtn,
                      pressed && styles.pressed,
                    ]}
                  >
                    {reauthBusy ? (
                      <ActivityIndicator
                        color={providerApple ? colors.textInverse : colors.textPrimary}
                      />
                    ) : (
                      <>
                        <Ionicons
                          name={providerApple ? 'logo-apple' : 'logo-google'}
                          size={18}
                          color={providerApple ? colors.textInverse : colors.textPrimary}
                        />
                        <Text style={providerApple ? styles.appleText : styles.googleText}>
                          {providerApple ? 'Continue with Apple' : 'Continue with Google'}
                        </Text>
                      </>
                    )}
                  </Pressable>
                )}
                <Pressable
                  onPress={() => setReauth(false)}
                  disabled={reauthBusy}
                  accessibilityRole="button"
                  accessibilityLabel="Cancel"
                  accessibilityState={{ disabled: reauthBusy }}
                  style={({ pressed }) => [styles.textBtn, pressed && styles.pressed]}
                >
                  <Text style={[styles.textBtnLabel, reauthBusy && styles.textBtnOff]}>Cancel</Text>
                </Pressable>
              </View>
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.lg,
  },
  banner: {
    backgroundColor: colors.avoidSoft,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  bannerText: {
    fontSize: font.size.footnote,
    color: colors.avoidInk,
    lineHeight: 18,
  },
  localBanner: {
    backgroundColor: colors.tintSoft,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  localBannerText: {
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    lineHeight: 18,
  },
  title: {
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  permanent: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  section: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: spacing.sm,
    marginLeft: 2,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginBottom: spacing.lg,
    overflow: 'hidden',
  },
  row: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  rowRule: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  rowText: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    lineHeight: 22,
  },
  notice: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.medInk,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  noticeKicker: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.medInk,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: spacing.sm,
  },
  noticeBody: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  manageBtn: {
    marginTop: spacing.md,
    minHeight: 44,
    borderRadius: radii.md,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  manageText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  footer: {
    flexShrink: 0,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  dangerBtn: {
    minHeight: 52,
    borderRadius: radii.md,
    backgroundColor: colors.avoidInk,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  dangerBtnBusy: {
    opacity: 0.7,
  },
  spinner: {
    marginRight: spacing.sm,
  },
  dangerText: {
    flexShrink: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
    textAlign: 'center',
  },
  textBtn: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  textBtnLabel: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
    textAlign: 'center',
  },
  textBtnOff: {
    color: colors.textTertiary,
  },
  pressed: {
    opacity: 0.6,
  },
  success: {
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.xl,
    paddingBottom: spacing.lg,
  },
  wordmark: {
    marginTop: spacing.lg,
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  tagline: {
    marginTop: spacing.xs,
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  toast: {
    alignSelf: 'stretch',
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginTop: spacing.xl,
    backgroundColor: colors.brandNavy,
    borderRadius: radii.md,
    padding: spacing.lg,
  },
  toastText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textInverse,
    lineHeight: 18,
  },
  quietBtn: {
    alignSelf: 'stretch',
    minHeight: 52,
    borderRadius: radii.md,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  quietText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  avoider: {
    flex: 1,
  },
  sheetBackdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: '#00000066',
  },
  sheet: {
    backgroundColor: colors.bgCard,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
    maxHeight: '90%',
  },
  grabber: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.separatorOpaque,
    marginBottom: spacing.md,
  },
  sheetTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  sheetBody: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: spacing.md,
  },
  codeInput: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.separatorOpaque,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    fontSize: font.size.title3,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  reauthError: {
    fontSize: font.size.footnote,
    color: colors.avoidInk,
    marginBottom: spacing.sm,
  },
  sheetActions: {
    marginTop: spacing.sm,
  },
  sheetRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'stretch',
    gap: spacing.sm,
  },
  sheetSide: {
    flexGrow: 1,
    flexBasis: 140,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
  },
  sheetSideText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
    textAlign: 'center',
  },
  sheetConfirm: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
    textAlign: 'center',
  },
  providerBtn: {
    minHeight: 52,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  appleBtn: {
    backgroundColor: colors.textPrimary,
  },
  googleBtn: {
    backgroundColor: colors.bgElevated,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separatorOpaque,
  },
  appleText: {
    flexShrink: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
    textAlign: 'center',
  },
  googleText: {
    flexShrink: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
});

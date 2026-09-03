import React, { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Image,
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
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import {
  authErrorMessage,
  isCompleteOtp,
  isValidEmail,
  normalizeOtp,
  providerLabel,
  sendEmailCode,
  signInWithProvider,
  verifyEmailCode,
  visibleProviders,
  type AuthProvider,
} from '@/lib/auth';
import { AUTH_PROVIDERS, EMAIL_OTP_LENGTH } from '@/lib/authConfig';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Sign-in screen. Unreachable while `AUTH_ENABLED` is false — nothing navigates
 * here — but kept fully wired so turning auth on is a one-line change.
 *
 * Email uses a 6-digit code rather than a magic link, so the flow never leaves
 * the app and can't be broken by an email client that rewrites links.
 */
export function SignInScreen() {
  const navigation = useNavigation<Nav>();
  const providers = useMemo(() => visibleProviders(Platform.OS), []);

  const [step, setStep] = useState<'email' | 'code'>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState<AuthProvider | 'email' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const dismiss = useCallback(() => {
    if (navigation.canGoBack()) navigation.goBack();
  }, [navigation]);

  const onProvider = useCallback(
    async (provider: AuthProvider) => {
      setError(null);
      setNotice(null);
      setBusy(provider);
      try {
        const session = await signInWithProvider(provider);
        // null = the user dismissed the browser. Not an error; stay put.
        if (session) dismiss();
      } catch (e) {
        setError(authErrorMessage(e));
      } finally {
        setBusy(null);
      }
    },
    [dismiss],
  );

  const onSendCode = useCallback(async () => {
    setError(null);
    setNotice(null);
    if (!isValidEmail(email)) {
      setError('Enter a valid email address.');
      return;
    }
    setBusy('email');
    try {
      await sendEmailCode(email);
      setCode('');
      setStep('code');
      setNotice(`We sent a ${EMAIL_OTP_LENGTH}-digit code to ${email.trim()}.`);
    } catch (e) {
      setError(authErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }, [email]);

  const onVerify = useCallback(async () => {
    setError(null);
    setBusy('email');
    try {
      await verifyEmailCode(email, code);
      dismiss();
    } catch (e) {
      setError(authErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }, [email, code, dismiss]);

  const onBackToEmail = useCallback(() => {
    setStep('email');
    setCode('');
    setError(null);
    setNotice(null);
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <Image
            source={require('../../assets/brand/mark.png')}
            style={styles.mark}
            accessibilityIgnoresInvertColors
            accessible={false}
          />
          <Text style={styles.title}>
            {step === 'email' ? 'Sign in to Signalbase' : 'Check your email'}
          </Text>
          <Text style={styles.subtitle}>
            {/* No cross-device-sync promise here: auth is session-only today. */}
            {step === 'email'
              ? 'Signing in is optional. Your bankroll, models and tracked bets stay on this device.'
              : `Enter the ${EMAIL_OTP_LENGTH}-digit code we sent you.`}
          </Text>

          {error ? (
            <View style={styles.errorBanner}>
              <Ionicons name="alert-circle" size={16} color={colors.avoid} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          {notice && !error ? (
            <View style={styles.noticeBanner}>
              <Ionicons name="mail-outline" size={16} color={colors.tint} />
              <Text style={styles.noticeText}>{notice}</Text>
            </View>
          ) : null}

          {step === 'email' ? (
            <>
              {providers.map((provider) => {
                const isApple = provider === 'apple';
                const pending = busy === provider;
                return (
                  <Pressable
                    key={provider}
                    onPress={() => onProvider(provider)}
                    disabled={busy != null}
                    style={({ pressed }) => [
                      styles.providerBtn,
                      isApple ? styles.appleBtn : styles.googleBtn,
                      pressed && styles.btnPressed,
                      busy != null && busy !== provider && styles.btnDisabled,
                    ]}
                  >
                    {pending ? (
                      <ActivityIndicator
                        color={isApple ? colors.textInverse : colors.textPrimary}
                      />
                    ) : (
                      <>
                        <Ionicons
                          name={isApple ? 'logo-apple' : 'logo-google'}
                          size={18}
                          color={isApple ? colors.textInverse : colors.textPrimary}
                        />
                        <Text
                          style={[
                            styles.providerBtnText,
                            isApple
                              ? styles.appleBtnText
                              : styles.googleBtnText,
                          ]}
                        >
                          {providerLabel(provider)}
                        </Text>
                      </>
                    )}
                  </Pressable>
                );
              })}

              {providers.length > 0 && AUTH_PROVIDERS.email ? (
                <View style={styles.dividerRow}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerText}>or</Text>
                  <View style={styles.dividerLine} />
                </View>
              ) : null}

              {AUTH_PROVIDERS.email ? (
                <>
                  <TextInput
                    style={styles.input}
                    value={email}
                    onChangeText={setEmail}
                    placeholder="you@example.com"
                    placeholderTextColor={colors.textTertiary}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoCorrect={false}
                    autoComplete="email"
                    textContentType="emailAddress"
                    editable={busy == null}
                    onSubmitEditing={onSendCode}
                    returnKeyType="go"
                  />
                  <Pressable
                    onPress={onSendCode}
                    disabled={busy != null}
                    style={({ pressed }) => [
                      styles.primaryBtn,
                      pressed && styles.btnPressed,
                      busy != null && styles.btnDisabled,
                    ]}
                  >
                    {busy === 'email' ? (
                      <ActivityIndicator color={colors.textInverse} />
                    ) : (
                      <Text style={styles.primaryBtnText}>Email me a code</Text>
                    )}
                  </Pressable>
                </>
              ) : null}
            </>
          ) : (
            <>
              <TextInput
                style={[styles.input, styles.codeInput]}
                value={code}
                onChangeText={(t) => setCode(normalizeOtp(t))}
                placeholder={'0'.repeat(EMAIL_OTP_LENGTH)}
                placeholderTextColor={colors.textTertiary}
                keyboardType="number-pad"
                autoComplete="one-time-code"
                textContentType="oneTimeCode"
                maxLength={EMAIL_OTP_LENGTH}
                editable={busy == null}
                autoFocus
                onSubmitEditing={onVerify}
                returnKeyType="go"
              />
              <Pressable
                onPress={onVerify}
                disabled={busy != null || !isCompleteOtp(code)}
                style={({ pressed }) => [
                  styles.primaryBtn,
                  pressed && styles.btnPressed,
                  (busy != null || !isCompleteOtp(code)) && styles.btnDisabled,
                ]}
              >
                {busy === 'email' ? (
                  <ActivityIndicator color={colors.textInverse} />
                ) : (
                  <Text style={styles.primaryBtnText}>Verify and sign in</Text>
                )}
              </Pressable>

              <Pressable onPress={onSendCode} disabled={busy != null}>
                <Text style={styles.linkText}>Send a new code</Text>
              </Pressable>
              <Pressable onPress={onBackToEmail} disabled={busy != null}>
                <Text style={styles.linkText}>Use a different email</Text>
              </Pressable>
            </>
          )}

          <Pressable onPress={dismiss} disabled={busy != null}>
            <Text style={styles.skipText}>Not now</Text>
          </Pressable>

          <Text style={styles.footnote}>
            Picks, models and the track record work without an account.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bgGrouped },
  content: { padding: spacing.lg, gap: spacing.md },
  // The brand mark, decorative: the title beneath it already names the app,
  // so it carries no label of its own.
  mark: {
    width: 64,
    height: 64,
    borderRadius: radii.lg,
    marginBottom: spacing.xs,
  },
  title: {
    fontFamily: font.family,
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginTop: spacing.lg,
  },
  subtitle: {
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.avoidSoft,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  errorText: {
    flex: 1,
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.avoid,
  },
  noticeBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.noneSoft,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  noticeText: {
    flex: 1,
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  providerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    height: 50,
    borderRadius: radii.md,
  },
  appleBtn: { backgroundColor: '#000000' },
  googleBtn: {
    backgroundColor: colors.bgElevated,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separatorOpaque,
  },
  providerBtnText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  appleBtnText: { color: colors.textInverse },
  googleBtnText: { color: colors.textPrimary },
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginVertical: spacing.xs,
  },
  dividerLine: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.separatorOpaque,
  },
  dividerText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textTertiary,
  },
  input: {
    backgroundColor: colors.bgElevated,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    height: 50,
    fontFamily: font.family,
    fontSize: font.size.callout,
    color: colors.textPrimary,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separatorOpaque,
  },
  codeInput: {
    textAlign: 'center',
    fontSize: font.size.title2,
    letterSpacing: 8,
    fontWeight: font.weight.semibold,
  },
  primaryBtn: {
    height: 50,
    borderRadius: radii.md,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  btnPressed: { opacity: 0.6 },
  btnDisabled: { opacity: 0.4 },
  linkText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.tint,
    textAlign: 'center',
    paddingVertical: spacing.sm,
  },
  skipText: {
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
    paddingVertical: spacing.md,
  },
  footnote: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
  },
});

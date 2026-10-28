import React, { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
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

import {
  authErrorMessage,
  isCompleteOtp,
  isValidEmail,
  normalizeOtp,
  sendEmailCode,
  signInWithProvider,
  verifyEmailCode,
  visibleProviders,
  type AuthProvider,
} from '@/lib/auth';
import { BrandMark } from '@/components/BrandMark';
import { AUTH_PROVIDERS, EMAIL_OTP_LENGTH } from '@/lib/authConfig';
import { billingReady } from '@/lib/billingConfig';
import { PRIVACY_URL, TERMS_URL, openLink } from '@/lib/socialLinks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Sign-in. Required when auth is on — cold open lands here, and there is no
 * skip. Unreachable while `AUTH_ENABLED` is false.
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

  const finish = useCallback(() => {
    const routes: { name: 'Tabs' | 'Paywall'; params?: { autoCloseIfEntitled: boolean } }[] = [
      { name: 'Tabs' },
    ];
    if (billingReady()) {
      routes.push({ name: 'Paywall', params: { autoCloseIfEntitled: true } });
    }
    navigation.reset({ index: routes.length - 1, routes });
  }, [navigation]);

  const onProvider = useCallback(
    async (provider: AuthProvider) => {
      setError(null);
      setBusy(provider);
      try {
        const session = await signInWithProvider(provider);
        // null = the user dismissed the browser. Not an error; stay put.
        if (session) finish();
      } catch (e) {
        setError(authErrorMessage(e));
      } finally {
        setBusy(null);
      }
    },
    [finish],
  );

  const onSendCode = useCallback(async () => {
    setError(null);
    if (!isValidEmail(email)) {
      setError('Enter a valid email address.');
      return;
    }
    setBusy('email');
    try {
      await sendEmailCode(email);
      setCode('');
      setStep('code');
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
      finish();
    } catch (e) {
      setError(authErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }, [email, code, finish]);

  const onBackToEmail = useCallback(() => {
    setStep('email');
    setCode('');
    setError(null);
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.card}>
            <BrandMark size={64} style={styles.mark} />
            <Text style={styles.title}>Sign in to Signalbase</Text>
            <Text style={styles.subtitle}>Model picks with a public record.</Text>
            <Text style={styles.body}>
              An account is needed to start a trial, subscribe and restore purchases.
            </Text>

            {error ? (
              <View style={styles.errorBanner}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            {step === 'email' ? (
              <>
                {providers.map((provider) => {
                  const isApple = provider === 'apple';
                  const pending = busy === provider;
                  return (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={isApple ? 'Continue with Apple' : 'Continue with Google'}
                      accessibilityState={{ busy: pending, disabled: busy != null }}
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
                        <ActivityIndicator color={isApple ? colors.brandInk : colors.textInverse} />
                      ) : (
                        <Text
                          style={[
                            styles.providerBtnText,
                            isApple ? styles.appleBtnText : styles.googleBtnText,
                          ]}
                        >
                          {isApple ? 'Continue with Apple' : 'Continue with Google'}
                        </Text>
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
                      accessibilityLabel="Email address"
                      style={styles.input}
                      value={email}
                      onChangeText={setEmail}
                      placeholder="Email address"
                      placeholderTextColor={colors.brandMuted}
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
                      accessibilityRole="button"
                      accessibilityLabel="Email me a code"
                      accessibilityState={{ busy: busy === 'email', disabled: busy != null }}
                      onPress={onSendCode}
                      disabled={busy != null}
                      style={({ pressed }) => [
                        styles.primaryBtn,
                        pressed && styles.btnPressed,
                        busy != null && styles.btnDisabled,
                      ]}
                    >
                      {busy === 'email' ? (
                        <ActivityIndicator color={colors.brandInk} />
                      ) : (
                        <Text style={styles.primaryBtnText}>Email me a code</Text>
                      )}
                    </Pressable>
                  </>
                ) : null}
              </>
            ) : (
              <>
                <Text style={styles.kicker}>Check your email</Text>
                <Text style={styles.body}>
                  We sent a {EMAIL_OTP_LENGTH}-digit code to {email.trim()}.
                </Text>
                <TextInput
                  accessibilityLabel={`${EMAIL_OTP_LENGTH}-digit sign-in code`}
                  style={[styles.input, styles.codeInput]}
                  value={code}
                  onChangeText={(t) => setCode(normalizeOtp(t))}
                  placeholder={'·'.repeat(EMAIL_OTP_LENGTH)}
                  placeholderTextColor={colors.brandMuted}
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
                  accessibilityRole="button"
                  accessibilityLabel="Verify and sign in"
                  accessibilityState={{
                    busy: busy === 'email',
                    disabled: busy != null || !isCompleteOtp(code),
                  }}
                  onPress={onVerify}
                  disabled={busy != null || !isCompleteOtp(code)}
                  style={({ pressed }) => [
                    styles.primaryBtn,
                    pressed && styles.btnPressed,
                    (busy != null || !isCompleteOtp(code)) && styles.btnDisabled,
                  ]}
                >
                  {busy === 'email' ? (
                    <ActivityIndicator color={colors.brandInk} />
                  ) : (
                    <Text style={styles.primaryBtnText}>Verify and sign in</Text>
                  )}
                </Pressable>

                <Pressable
                  hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                  accessibilityRole="button"
                  accessibilityLabel="Send a new code"
                  onPress={onSendCode}
                  disabled={busy != null}
                >
                  <Text style={styles.linkText}>Send a new code</Text>
                </Pressable>
                <Pressable
                  hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                  accessibilityRole="button"
                  accessibilityLabel="Use a different email"
                  onPress={onBackToEmail}
                  disabled={busy != null}
                >
                  <Text style={styles.linkText}>Use a different email</Text>
                </Pressable>
              </>
            )}

            <Text style={styles.legal}>By continuing you agree to the</Text>
            <View style={styles.legalRow}>
              <Pressable
                accessibilityRole="link"
                accessibilityLabel="Terms"
                onPress={() => openLink(TERMS_URL, 'Terms')}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                style={styles.legalHit}
              >
                <Text style={styles.legalLink}>Terms</Text>
              </Pressable>
              <Text style={styles.legal}>and</Text>
              <Pressable
                accessibilityRole="link"
                accessibilityLabel="Privacy Policy"
                onPress={() => openLink(PRIVACY_URL, 'Privacy Policy')}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                style={styles.legalHit}
              >
                <Text style={styles.legalLink}>Privacy Policy</Text>
              </Pressable>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bgGrouped },
  content: { padding: spacing.lg, flexGrow: 1 },
  card: {
    backgroundColor: colors.brandNavy,
    borderRadius: radii.lg,
    padding: spacing.xl,
    gap: spacing.md,
    alignItems: 'center',
  },
  mark: { marginBottom: spacing.xs },
  title: {
    fontFamily: font.family,
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
    textAlign: 'center',
  },
  subtitle: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
    textAlign: 'center',
  },
  body: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.brandMuted,
    textAlign: 'center',
    lineHeight: 18,
  },
  kicker: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.brandMuted,
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    alignSelf: 'stretch',
  },
  errorBanner: {
    alignSelf: 'stretch',
    backgroundColor: colors.avoidSoft,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  errorText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.avoidInk,
  },
  providerBtn: {
    alignSelf: 'stretch',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
    borderRadius: radii.md,
  },
  appleBtn: { backgroundColor: colors.textInverse },
  googleBtn: { backgroundColor: colors.textPrimary },
  providerBtnText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  appleBtnText: { color: colors.brandInk },
  googleBtnText: { color: colors.textInverse },
  dividerRow: {
    alignSelf: 'stretch',
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginVertical: spacing.xs,
  },
  dividerLine: {
    flex: 1,
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.brandSeparator,
  },
  dividerText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.brandMuted,
  },
  input: {
    alignSelf: 'stretch',
    backgroundColor: colors.brandNavyRaised,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    minHeight: 50,
    fontFamily: font.family,
    fontSize: font.size.callout,
    color: colors.textInverse,
  },
  codeInput: {
    textAlign: 'center',
    fontSize: font.size.title2,
    letterSpacing: 8,
    fontWeight: font.weight.semibold,
  },
  primaryBtn: {
    alignSelf: 'stretch',
    minHeight: 50,
    borderRadius: radii.md,
    backgroundColor: colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnText: {
    fontFamily: font.family,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.brandInk,
  },
  btnPressed: { opacity: 0.6 },
  btnDisabled: { opacity: 0.4 },
  linkText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.brand,
    textAlign: 'center',
    paddingVertical: spacing.sm,
  },
  legal: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.brandMuted,
    textAlign: 'center',
    lineHeight: 18,
  },
  legalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  legalHit: {
    minHeight: 44,
    justifyContent: 'center',
  },
  legalLink: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.brand,
    textDecorationLine: 'underline',
    fontWeight: font.weight.semibold,
  },
});

/**
 * Verifies the pure auth helpers — the parts that decide whether a real
 * sign-in succeeds or dead-ends — plus a source-level check that every network
 * entry point is actually behind the feature flag.
 *
 *   npx tsx scripts/verify_auth.ts
 *
 * Imports only lib/authHelpers + lib/authConfig on purpose: lib/auth.ts reaches
 * react-native transitively (Supabase → AsyncStorage), which tsx/esbuild cannot
 * transform. Same split as lib/customModelBacktest.ts.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  assertAuthEnabled,
  authErrorMessage,
  AuthDisabledError,
  isCompleteOtp,
  isValidEmail,
  normalizeOtp,
  parseAuthCallback,
  providerLabel,
  visibleProviders,
} from '../src/lib/authHelpers';
import { AUTH_ENABLED, AUTH_REDIRECT_URL } from '../src/lib/authConfig';
import { BILLING_ENABLED } from '../src/lib/billingConfig';
import { freeSegmentOpensPaywall, postSignInRoutes, signedOutRouteIsShell } from '../src/lib/authShell';

let passed = 0;
const failures: string[] = [];

function check(label: string, cond: boolean) {
  if (cond) passed++;
  else failures.push(label);
}

function eq<T>(label: string, actual: T, expected: T) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) passed++;
  else
    failures.push(
      `${label} — got ${JSON.stringify(actual)}, want ${JSON.stringify(expected)}`,
    );
}

// --- the flag itself --------------------------------------------------------
// The whole point of this change: auth ships dark. If this ever flips to true
// without a deliberate decision, this is the tripwire.
check('AUTH_ENABLED defaults to false', AUTH_ENABLED === false);
check('BILLING_ENABLED defaults to false', BILLING_ENABLED === false);
check('signed-out SignIn is not the shell', !signedOutRouteIsShell('SignIn'));
check('signed-out Tabs is the shell', signedOutRouteIsShell('Tabs'));
check('signed-out PickDetail is the shell', signedOutRouteIsShell('PickDetail'));
check('an unknown route is not the shell', !signedOutRouteIsShell(undefined));
check('Signals opens the paywall for a free member', freeSegmentOpensPaywall('signals'));
check('Live Signals opens the paywall for a free member', freeSegmentOpensPaywall('live'));
check('All stays the teaser', !freeSegmentOpensPaywall('today'));
check('Scoreboard stays its own lock', !freeSegmentOpensPaywall('scoreboard'));

const appSrc = readFileSync(join(__dirname, '..', 'App.tsx'), 'utf8');
check(
  'a signed-out navigation returns to SignIn from the module status',
  appSrc.includes('readAuthStatus()') && appSrc.includes('signedOutRouteIsShell'),
);
check(
  'the Picks tab is the teaser, not a paywall listener',
  /<Tab\.Screen name="Picks" component=\{PicksHomeScreen\} \/>/.test(appSrc) &&
    !/<Tab\.Screen name="Picks"[^>]*listeners=\{lockedTab\}/.test(appSrc),
);
const picksSrc = readFileSync(join(__dirname, '..', 'src', 'screens', 'PicksHomeScreen.tsx'), 'utf8');
check(
  'Signals and Live Signals call the paywall when locked',
  picksSrc.includes('freeSegmentOpensPaywall') && picksSrc.includes('openPaywall()'),
);
const pushSrc = readFileSync(join(__dirname, '..', 'src', 'hooks', 'usePushDeepLink.ts'), 'utf8');
check(
  'a signed-out push does not open the shell',
  pushSrc.includes("readAuthStatus() === 'signedOut'"),
);
check('redirect URL uses the app scheme', AUTH_REDIRECT_URL.startsWith('signalbase://'));

// --- disabled guard ---------------------------------------------------------
let threw = false;
try {
  assertAuthEnabled(false);
} catch (e) {
  threw = e instanceof AuthDisabledError;
}
check('assertAuthEnabled(false) throws AuthDisabledError', threw);
let passedThrough = true;
try {
  assertAuthEnabled(true);
} catch {
  passedThrough = false;
}
check('assertAuthEnabled(true) is a no-op', passedThrough);

// Source-level tripwire: every function in lib/auth.ts that talks to Supabase
// must call the guard first. A refactor that drops one would let a build with
// the flag off still create accounts — this is the check that catches it.
// (Same spirit as the DraftKings-filter source guards in test_multi_book_odds.py.)
const authSrc = readFileSync(join(__dirname, '..', 'src', 'lib', 'auth.ts'), 'utf8');
for (const fn of [
  'sendEmailCode',
  'verifyEmailCode',
  'signInWithProvider',
  'signOut',
]) {
  const body = authSrc.split(`export async function ${fn}`)[1] ?? '';
  const guarded = body.split('\n').slice(0, 12).join('\n');
  check(
    `${fn}() guards on AUTH_ENABLED`,
    guarded.includes('assertAuthEnabled(AUTH_ENABLED)'),
  );
}
check(
  'getCurrentSession() short-circuits when disabled',
  (authSrc.split('export async function getCurrentSession')[1] ?? '').includes(
    'if (!AUTH_ENABLED) return null',
  ),
);

// iOS Apple is the system sheet. A static import of the native module would
// load it for email, Google, and Android the moment this file is evaluated.
check(
  'auth.ts has no static value import of expo-apple-authentication',
  !/^import\s+(?!type\b)[^;]*from\s+'expo-apple-authentication'/m.test(authSrc),
);
const appleLoader = authSrc.split('function loadAppleAuthentication')[1]?.split(
  'async function signInWithAppleNative',
)[0] ?? '';
check(
  'the Apple native module is a dynamic require inside its loader',
  appleLoader.includes("require('expo-apple-authentication')") &&
    appleLoader.indexOf("Platform.OS !== 'ios'") <
      appleLoader.indexOf("require('expo-apple-authentication')"),
);
const appleNative = authSrc.split('async function signInWithAppleNative')[1]?.split(
  'async function signInWithOAuthBrowser',
)[0] ?? '';
check(
  'iOS Apple exchanges the identity token',
  appleNative.includes("signInWithIdToken") &&
    appleNative.includes("provider: 'apple'") &&
    appleNative.includes('identityToken'),
);
check(
  'a failed Apple sign-in is one sentence',
  appleNative.includes("Couldn't sign in with Apple. Try again."),
);
check(
  'iOS Apple does not open the in-app browser',
  !appleNative.includes('signInWithOAuth') && !appleNative.includes('openAuthSessionAsync'),
);
check(
  'a dismissed Apple sheet is a cancel',
  appleNative.includes('isAppleCancel') &&
    appleNative.includes('return null') &&
    authSrc.includes("=== 'ERR_REQUEST_CANCELED'"),
);
const providerFn = authSrc.split('export async function signInWithProvider')[1]?.split(
  'export async function signOut',
)[0] ?? '';
check(
  'iOS Apple returns before the browser flow',
  providerFn.includes("provider === 'apple'") &&
    providerFn.includes("Platform.OS === 'ios'") &&
    providerFn.indexOf('signInWithAppleNative') < providerFn.indexOf('signInWithOAuthBrowser'),
);
check(
  'Google still uses the in-app browser',
  authSrc.includes('signInWithOAuth') && authSrc.includes('openAuthSessionAsync'),
);

const appJson = JSON.parse(
  readFileSync(join(__dirname, '..', 'app.json'), 'utf8'),
) as {
  expo: {
    version: string;
    plugins?: string[];
    ios?: { bundleIdentifier?: string; usesAppleSignIn?: boolean };
  };
};
const pkg = JSON.parse(readFileSync(join(__dirname, '..', 'package.json'), 'utf8')) as {
  dependencies?: Record<string, string>;
};
check(
  'bundle id is unchanged',
  appJson.expo.ios?.bundleIdentifier === 'com.mja.bettingpicks',
);
check(
  'Sign in with Apple capability is on',
  appJson.expo.ios?.usesAppleSignIn === true,
);
check(
  'expo-apple-authentication plugin is configured',
  Array.isArray(appJson.expo.plugins) &&
    appJson.expo.plugins.includes('expo-apple-authentication'),
);
check(
  'expo-apple-authentication is a dependency',
  typeof pkg.dependencies?.['expo-apple-authentication'] === 'string',
);
// 1.1.0 is the last runtime without this native module. runtimeVersion follows
// appVersion, so an OTA of this bundle must not target that binary.
check(
  'app version moved off the pre-native-Apple runtime',
  appJson.expo.version !== '1.1.0' && appJson.expo.version === '1.2.0',
);

const signInSrc = readFileSync(
  join(__dirname, '..', 'src', 'screens', 'SignInScreen.tsx'),
  'utf8',
);
check(
  'SignInScreen has no static value import of expo-apple-authentication',
  !/^import\s+(?!type\b)[^;]*from\s+'expo-apple-authentication'/m.test(signInSrc),
);
const signInLoader = signInSrc.split('function loadAppleSignInButton')[1]?.split(
  'export function SignInScreen',
)[0] ?? '';
check(
  'the Apple button require runs only after the iOS check',
  signInLoader.indexOf("Platform.OS !== 'ios'") !== -1 &&
    signInLoader.indexOf("Platform.OS !== 'ios'") <
      signInLoader.indexOf("require('expo-apple-authentication')"),
);
check(
  'iOS uses the system Continue with Apple button',
  signInSrc.includes('AppleAuthenticationButtonType.CONTINUE') &&
    signInSrc.includes('AppleAuthenticationButtonStyle.WHITE'),
);
check(
  'sign-in asks whether the account is premium before it routes',
  signInSrc.includes('postSignInRoutes(') && signInSrc.includes('isAppPremium('),
);
eq('billing off skips the paywall', postSignInRoutes(false, false), [{ name: 'Tabs' }]);
eq('a premium sign-in skips the paywall', postSignInRoutes(true, true), [{ name: 'Tabs' }]);
eq('a free sign-in opens the paywall over the tabs', postSignInRoutes(true, false), [
  { name: 'Tabs' },
  { name: 'Paywall', params: { autoCloseIfEntitled: true } },
]);

// --- email validation -------------------------------------------------------
check('accepts a normal address', isValidEmail('matt@example.com'));
check('accepts subdomains', isValidEmail('a@mail.example.co.uk'));
check('accepts + tags', isValidEmail('matt+picks@example.com'));
check('trims surrounding space', isValidEmail('  matt@example.com  '));
check('rejects empty', !isValidEmail(''));
check('rejects missing @', !isValidEmail('matt.example.com'));
check('rejects missing domain dot', !isValidEmail('matt@example'));
check('rejects internal whitespace', !isValidEmail('matt @example.com'));
check('rejects double @', !isValidEmail('a@b@example.com'));

// --- OTP normalization ------------------------------------------------------
eq('strips non-digits', normalizeOtp('12-34 56'), '123456');
eq('clamps to length', normalizeOtp('12345678'), '123456');
eq('non-numeric yields empty', normalizeOtp('abc'), '');
check('complete at 6 digits', isCompleteOtp('123456'));
check('incomplete at 5', !isCompleteOtp('12345'));
check('complete despite formatting', isCompleteOtp('123 456'));

// --- OAuth callback parsing -------------------------------------------------
eq(
  'reads PKCE code from the query',
  parseAuthCallback('signalbase://auth-callback?code=abc123'),
  { code: 'abc123', error: null },
);
eq(
  'reads a provider error',
  parseAuthCallback(
    'signalbase://auth-callback?error=access_denied&error_description=User%20cancelled',
  ),
  { code: null, error: 'User cancelled' },
);
eq(
  'error wins over a code',
  parseAuthCallback('signalbase://auth-callback?code=abc&error=bad_state'),
  { code: null, error: 'bad_state' },
);
eq(
  'reads a code from the fragment too',
  parseAuthCallback('signalbase://auth-callback#code=frag123'),
  { code: 'frag123', error: null },
);
check(
  'implicit-flow tokens surface as an explicit error, not silence',
  parseAuthCallback('signalbase://auth-callback#access_token=xyz&token_type=bearer')
    .error != null,
);
eq('a bare callback yields neither', parseAuthCallback('signalbase://auth-callback'), {
  code: null,
  error: null,
});

// --- provider surface -------------------------------------------------------
// Apple must come first on iOS (App Store guideline 4.8 expects it to be at
// least as prominent as other options) and Google must never appear alone there.
eq('iOS offers Apple then Google', visibleProviders('ios'), ['apple', 'google']);
eq('Android offers Google only', visibleProviders('android'), ['google']);
check(
  'iOS never shows Google without Apple',
  !(visibleProviders('ios').includes('google') && !visibleProviders('ios').includes('apple')),
);
eq('Apple label', providerLabel('apple'), 'Sign in with Apple');
eq('Google label', providerLabel('google'), 'Continue with Google');

// --- error messages ---------------------------------------------------------
check(
  'expired code is explained',
  authErrorMessage(new Error('Token has expired or is invalid')).includes('expired'),
);
check(
  'rate limit is explained',
  authErrorMessage(new Error('For security purposes, email rate limit exceeded')).includes(
    'Wait',
  ),
);
check(
  'network failure is explained',
  authErrorMessage(new Error('Network request failed')).includes('connection'),
);
check(
  'unconfigured provider is explained',
  authErrorMessage(new Error('Provider is not enabled')).includes('not set up'),
);
check('non-Error input still yields a string', typeof authErrorMessage(null) === 'string');
check(
  'unknown message passes through',
  authErrorMessage(new Error('Weird thing')) === 'Weird thing',
);

if (failures.length === 0) {
  console.log(`ALL PASS (${passed} assertions)`);
} else {
  console.error(`${failures.length} FAILED, ${passed} passed:`);
  failures.forEach((f) => console.error('  ✗ ' + f));
  process.exit(1);
}

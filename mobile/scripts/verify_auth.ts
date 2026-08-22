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

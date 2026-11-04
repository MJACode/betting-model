/**
 * App Review fixed-code gate. The code itself is not an argument here.
 *
 *   npx tsx scripts/verify_app_review_sign_in.ts
 *
 * Run from mobile/. Extensionless imports, same as verify_auth.ts: tsc rejects
 * a .ts suffix (TS5097), and tsx resolves these. The OTP value lives in
 * APP_STORE_METADATA.md and is asserted from tests/test_app_review_sign_in.py.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  APP_REVIEW_DEMO_EMAIL,
  REVIEW_SIGN_IN_ERRORS,
  isAppReviewDemoEmail,
  reviewFunctionErrorMessage,
} from '../src/lib/appReview';
import {
  REVIEW_CODE_MISMATCH,
  REVIEW_FAILURE_LIMIT,
  REVIEW_MINT_FAILED,
  REVIEW_NOT_CONFIGURED,
  REVIEW_TOO_MANY,
  reviewBypassConfigured,
  reviewCredentialsMatch,
  reviewFailureLimitReached,
} from '../../supabase/functions/_shared/appReviewSignIn';

let passed = 0;
const failures: string[] = [];

function check(label: string, cond: boolean) {
  if (cond) passed++;
  else failures.push(label);
}

const EMAIL = 'review@signalbase-ai.com';
const OTP = '847291';

check('demo address is the documented one', APP_REVIEW_DEMO_EMAIL === EMAIL);
check('trims and lowercases the demo address', isAppReviewDemoEmail(`  ${EMAIL.toUpperCase()} `));
check('a normal address is not the demo', !isAppReviewDemoEmail('matt@example.com'));
check('empty is not the demo', !isAppReviewDemoEmail(''));

check('both secrets configure the bypass', reviewBypassConfigured(EMAIL, OTP));
check('missing email leaves it off', !reviewBypassConfigured('', OTP));
check('missing code leaves it off', !reviewBypassConfigured(EMAIL, ''));
check('a five-digit code leaves it off', !reviewBypassConfigured(EMAIL, '84729'));
check('a word leaves it off', !reviewBypassConfigured(EMAIL, 'password'));
check('seven digits leave it off', !reviewBypassConfigured(EMAIL, '8472910'));

check(
  'the documented pair matches',
  reviewCredentialsMatch(EMAIL, OTP, EMAIL, OTP),
);
check(
  'email case and surrounding space still match',
  reviewCredentialsMatch(` ${EMAIL.toUpperCase()} `, ` ${OTP} `, EMAIL, OTP),
);
check(
  'a formatted code still matches',
  reviewCredentialsMatch(EMAIL, '847-291', EMAIL, OTP),
);
check(
  'the right code on another email does not match',
  !reviewCredentialsMatch('other@signalbase-ai.com', OTP, EMAIL, OTP),
);
check(
  'the right email with the wrong code does not match',
  !reviewCredentialsMatch(EMAIL, '111111', EMAIL, OTP),
);
check(
  'a short code does not match',
  !reviewCredentialsMatch(EMAIL, '84729', EMAIL, OTP),
);
check(
  'both compares run: wrong email and wrong code',
  !reviewCredentialsMatch('nope@example.com', '000000', EMAIL, OTP),
);

check(
  'the app shows the same four sentences the function returns',
  REVIEW_SIGN_IN_ERRORS.length === 4 &&
    REVIEW_SIGN_IN_ERRORS.includes(REVIEW_NOT_CONFIGURED) &&
    REVIEW_SIGN_IN_ERRORS.includes(REVIEW_CODE_MISMATCH) &&
    REVIEW_SIGN_IN_ERRORS.includes(REVIEW_TOO_MANY) &&
    REVIEW_SIGN_IN_ERRORS.includes(REVIEW_MINT_FAILED),
);
check(
  'a known function sentence is shown',
  reviewFunctionErrorMessage({ error: REVIEW_CODE_MISMATCH }) === REVIEW_CODE_MISMATCH,
);
check(
  'a stray function sentence is not shown',
  reviewFunctionErrorMessage({ error: 'internal stack' }) === null,
);
check('a non-object body is not shown', reviewFunctionErrorMessage(null) === null);

check('eight failures are still allowed', !reviewFailureLimitReached(REVIEW_FAILURE_LIMIT));
check('the next failure is refused', reviewFailureLimitReached(REVIEW_FAILURE_LIMIT + 1));

const root = join(__dirname, '..', '..');
const authSrc = readFileSync(join(root, 'mobile/src/lib/auth.ts'), 'utf8');
const sendBody = authSrc.split('export async function sendEmailCode')[1]?.split(
  'export async function verifyEmailCode',
)[0] ?? '';
const verifyBody = authSrc.split('export async function verifyEmailCode')[1]?.split(
  'async function exchangeReviewCode',
)[0] ?? '';
check(
  'sendEmailCode returns before signInWithOtp for the demo address',
  sendBody.indexOf('isAppReviewDemoEmail(address)') !== -1 &&
    sendBody.indexOf('isAppReviewDemoEmail(address)') < sendBody.indexOf('signInWithOtp'),
);
check(
  'verifyEmailCode uses the review function before verifyOtp',
  verifyBody.indexOf('isAppReviewDemoEmail(address)') !== -1 &&
    verifyBody.indexOf('exchangeReviewCode') < verifyBody.indexOf('verifyOtp'),
);
check(
  'the review exchange calls the edge function',
  authSrc.includes("functions.invoke(APP_REVIEW_SIGN_IN_FUNCTION"),
);
check(
  'a non-2xx body is read before the generic sentence',
  authSrc.includes('reviewFunctionErrorMessage') &&
    authSrc.includes("name === 'FunctionsHttpError'"),
);
check(
  'a dropped connection stays a network error',
  authSrc.includes("name === 'FunctionsFetchError'") &&
    authSrc.includes('Network request failed'),
);

const screen = readFileSync(join(root, 'mobile/src/screens/SignInScreen.tsx'), 'utf8');
const provider = screen.split('const onProvider = useCallback')[1]?.split(
  'const onSendCode',
)[0] ?? '';
check(
  'Apple and Google open the code step when the demo email is filled',
  provider.indexOf('isAppReviewDemoEmail(email)') !== -1 &&
    provider.indexOf('isAppReviewDemoEmail(email)') < provider.indexOf('signInWithProvider'),
);

const fn = readFileSync(
  join(root, 'supabase/functions/app-review-sign-in/index.ts'),
  'utf8',
);
check('the function reads both secrets', fn.includes('APP_REVIEW_DEMO_EMAIL') && fn.includes('APP_REVIEW_DEMO_OTP'));
check('a missing attempt table refuses the call', fn.includes('attemptsTableReady'));
check('the right code is checked before a failure is recorded', (() => {
  const handler = fn.split('Deno.serve')[1] ?? '';
  return handler.indexOf('reviewCredentialsMatch') < handler.indexOf('recordFailure');
})());
const deleteSrc = readFileSync(
  join(root, 'mobile/src/screens/DeleteAccountScreen.tsx'),
  'utf8',
);
check(
  'delete reauth does not send a code for the demo address',
  deleteSrc.includes('isAppReviewDemoEmail(email)') &&
    deleteSrc.includes('reviewAccount ? null'),
);

check(
  'the documented code is not hardcoded in the function',
  !fn.includes(OTP),
);
const shared = readFileSync(
  join(root, 'supabase/functions/_shared/appReviewSignIn.ts'),
  'utf8',
);
check('the shared gate does not contain the documented code', !shared.includes(OTP));

if (failures.length === 0) {
  console.log(`ALL PASS (${passed} assertions)`);
} else {
  console.error(`${failures.length} FAILED, ${passed} passed:`);
  failures.forEach((f) => console.error('  ✗ ' + f));
  process.exit(1);
}

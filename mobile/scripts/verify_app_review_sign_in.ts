/**
 * App Review fixed-code gate.
 *
 *   npx tsx scripts/verify_app_review_sign_in.ts
 *
 * Run from mobile/. Extensionless imports, same as verify_auth.ts: tsc rejects
 * a .ts suffix (TS5097), and tsx resolves these.
 *
 * Most checks below are source greps (the order of calls in auth.ts and the
 * edge function). They are not a call to the deployed function. The matcher,
 * the failure cap, and the address hash are the behavioral checks. Fixture
 * codes in this file are not a published sign-in code.
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
  REVIEW_GLOBAL_FAILURE_LIMIT,
  REVIEW_MINT_FAILED,
  REVIEW_NOT_CONFIGURED,
  REVIEW_TOO_MANY,
  REVIEW_UNAVAILABLE,
  clientIpFromHeaders,
  hashAttemptBucket,
  reviewBypassConfigured,
  reviewCredentialsMatch,
  reviewFailureLimitReached,
  reviewGlobalFailureLimitReached,
} from '../../supabase/functions/_shared/appReviewSignIn';

let passed = 0;
const failures: string[] = [];

function check(label: string, cond: boolean) {
  if (cond) passed++;
  else failures.push(label);
}

const EMAIL = 'review@signalbase-ai.com';
const FIXTURE = '111111';

check('demo address is the documented one', APP_REVIEW_DEMO_EMAIL === EMAIL);
check('trims and lowercases the demo address', isAppReviewDemoEmail(`  ${EMAIL.toUpperCase()} `));
check('a normal address is not the demo', !isAppReviewDemoEmail('matt@example.com'));
check('empty is not the demo', !isAppReviewDemoEmail(''));

check('both secrets configure the bypass', reviewBypassConfigured(EMAIL, FIXTURE));
check('missing email leaves it off', !reviewBypassConfigured('', FIXTURE));
check('missing code leaves it off', !reviewBypassConfigured(EMAIL, ''));
check('a five-digit code leaves it off', !reviewBypassConfigured(EMAIL, '11111'));
check('a word leaves it off', !reviewBypassConfigured(EMAIL, 'password'));
check('seven digits leave it off', !reviewBypassConfigured(EMAIL, '1111111'));

check(
  'a fixture pair matches',
  reviewCredentialsMatch(EMAIL, FIXTURE, EMAIL, FIXTURE),
);
check(
  'email case and surrounding space still match',
  reviewCredentialsMatch(` ${EMAIL.toUpperCase()} `, ` ${FIXTURE} `, EMAIL, FIXTURE),
);
check(
  'a formatted code still matches',
  reviewCredentialsMatch(EMAIL, '111-111', EMAIL, FIXTURE),
);
check(
  'the right code on another email does not match',
  !reviewCredentialsMatch('other@signalbase-ai.com', FIXTURE, EMAIL, FIXTURE),
);
check(
  'the right email with the wrong code does not match',
  !reviewCredentialsMatch(EMAIL, '222222', EMAIL, FIXTURE),
);
check(
  'a short code does not match',
  !reviewCredentialsMatch(EMAIL, '11111', EMAIL, FIXTURE),
);
check(
  'both compares run: wrong email and wrong code',
  !reviewCredentialsMatch('nope@example.com', '000000', EMAIL, FIXTURE),
);

check(
  'the app shows the same sentences the function returns',
  REVIEW_SIGN_IN_ERRORS.length === 5 &&
    REVIEW_SIGN_IN_ERRORS.includes(REVIEW_NOT_CONFIGURED) &&
    REVIEW_SIGN_IN_ERRORS.includes(REVIEW_UNAVAILABLE) &&
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
check(
  'two hundred failures in an hour are still allowed',
  !reviewGlobalFailureLimitReached(REVIEW_GLOBAL_FAILURE_LIMIT),
);
check(
  'the next failure in that hour is refused for every caller',
  reviewGlobalFailureLimitReached(REVIEW_GLOBAL_FAILURE_LIMIT + 1),
);

const edgeAddress = '198.51.100.9';
check(
  'cf-connecting-ip is the caller',
  clientIpFromHeaders('192.0.2.10', '203.0.113.5, ' + edgeAddress) === '192.0.2.10',
);
check(
  'without cf-connecting-ip the last forwarded hop is the caller',
  clientIpFromHeaders(null, '203.0.113.5, ' + edgeAddress) === edgeAddress,
);
check(
  'a single forwarded hop is the caller',
  clientIpFromHeaders(null, edgeAddress) === edgeAddress,
);
check(
  'no address is its own bucket label',
  clientIpFromHeaders('  ', ' , ') === 'unknown',
);
async function checkBuckets(): Promise<void> {
  const spoofed = await hashAttemptBucket(
    clientIpFromHeaders(null, '203.0.113.5, ' + edgeAddress),
  );
  const real = await hashAttemptBucket(clientIpFromHeaders(null, edgeAddress));
  check(
    'a faked first XFF hop does not change the rate-limit bucket',
    spoofed === real,
  );
  const viaEdge = await hashAttemptBucket(
    clientIpFromHeaders(edgeAddress, '203.0.113.5, 192.0.2.10'),
  );
  check(
    'cf-connecting-ip keeps the bucket when the first hop is faked',
    viaEdge === real,
  );
  const other = await hashAttemptBucket('203.0.113.5');
  check('two addresses hash differently', spoofed !== other);
  check('the hash is not the address', spoofed !== edgeAddress && spoofed.length === 64);
}

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
check('a full bucket is refused before the code is compared', (() => {
  const handler = fn.split('Deno.serve')[1] ?? '';
  const limitAt = handler.indexOf('overFailureLimit');
  const matchAt = handler.indexOf('reviewCredentialsMatch');
  return limitAt !== -1 &&
    limitAt < matchAt &&
    matchAt < handler.indexOf('recordFailure') &&
    fn.includes('reviewGlobalFailureLimitReached');
})());
check('the caller is cf-connecting-ip, not the first forwarded hop', fn.includes('cf-connecting-ip'));
check('failures are stored on the caller bucket', fn.includes('.eq("bucket", bucket)'));
check('a database error on the count is 503', fn.includes('unavailable()') && fn.includes('503'));
check(
  'an existing user is only email_exists',
  fn.includes('=== "email_exists"') && !fn.includes('status === 422'),
);
const deleteSrc = readFileSync(
  join(root, 'mobile/src/screens/DeleteAccountScreen.tsx'),
  'utf8',
);
check(
  'delete reauth does not send a code for the demo address',
  deleteSrc.includes('isAppReviewDemoEmail(email)') &&
    deleteSrc.includes('reviewAccount ? null'),
);

check('the function source has no six-digit code', !/(?<!\d)\d{6}(?!\d)/.test(fn));
const shared = readFileSync(
  join(root, 'supabase/functions/_shared/appReviewSignIn.ts'),
  'utf8',
);
check('the shared gate has no six-digit code', !/(?<!\d)\d{6}(?!\d)/.test(shared));

checkBuckets()
  .then(() => {
    if (failures.length === 0) {
      console.log(`ALL PASS (${passed} assertions)`);
    } else {
      console.error(`${failures.length} FAILED, ${passed} passed:`);
      failures.forEach((f) => console.error('  ✗ ' + f));
      process.exit(1);
    }
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });

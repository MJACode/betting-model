/**
 * Verifies the pure half of push registration — the part that decides WHAT THE
 * READER IS TOLD when registration or delivery fails.
 *
 *   npx tsx scripts/verify_push.ts
 *
 * The bug this guards against is not a crash. It is the 2026-09-12 state:
 * every failure collapsing into one silent `console.warn`, so a build with no
 * APNs entitlement, a declined prompt and a refused write were indistinguishable
 * on screen. So the checks below are mostly about DISCRIMINATION — that four
 * different causes produce four different diagnoses — plus the one property
 * that has to hold whatever Expo's wording does: an unrecognised error is still
 * reported in full rather than squeezed into the nearest bucket.
 *
 * Imports only lib/pushDiagnosis + lib/pushTest. Both are free of react-native,
 * which is why PUSH_ROUTE_VERSION was split into lib/pushRouteVersion.ts —
 * lib/pushRoute.ts reaches useSportFilter → AsyncStorage, which tsx cannot
 * transform. Same split as lib/authHelpers.ts.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  diagnosePushError,
  errorText,
  type PushFailureReason,
} from '../src/lib/pushDiagnosis';
import { buildTestMessage, interpretExpoResponse } from '../src/lib/pushTest';
import { PUSH_ROUTE_VERSION } from '../src/lib/pushRouteVersion';

let passed = 0;
const failures: string[] = [];

function check(label: string, cond: boolean) {
  if (cond) passed++;
  else failures.push(label);
}

function eq<T>(label: string, actual: T, expected: T) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) passed++;
  else
    failures.push(`${label} — got ${JSON.stringify(actual)}, want ${JSON.stringify(expected)}`);
}

function reasonOf(err: unknown): PushFailureReason {
  return diagnosePushError(err).reason;
}

// ── 1. The four causes are four diagnoses ────────────────────────────────────
// Each string below is the shape of a real failure. They are matched leniently
// on purpose (see pushDiagnosis.ts), so these assert the CLASSIFICATION, never
// that Expo emits this exact prose.
eq(
  'a binary with no push module reads as unsupported',
  reasonOf(new Error("Cannot find native module 'ExpoPushTokenManager'")),
  'unsupported',
);
eq(
  'a simulator reads as unsupported',
  reasonOf(new Error('Must use physical device for push notifications')),
  'unsupported',
);
eq(
  'a missing entitlement reads as credentials',
  reasonOf(
    new Error(
      'Error encountered while fetching Expo token: no valid "aps-environment" entitlement string found for application',
    ),
  ),
  'credentials',
);
eq(
  'an APNs key EAS does not hold reads as credentials',
  reasonOf(new Error('InvalidCredentials: Could not find APNs credentials')),
  'credentials',
);
eq('a declined prompt reads as permission', reasonOf('Permission not granted'), 'permission');
eq(
  'a dead network reads as network',
  reasonOf(new Error('Network request failed')),
  'network',
);
eq(
  'a retired token reads as stale',
  reasonOf(new Error('DeviceNotRegistered: "ExponentPushToken[x]" is not a registered push notification recipient')),
  'stale',
);

// The discrimination itself: seven distinct causes must not share a bucket.
const reasons = new Set<PushFailureReason>([
  reasonOf(new Error("Cannot find native module 'ExpoPushTokenManager'")),
  reasonOf(new Error('no valid "aps-environment" entitlement string found')),
  reasonOf('Permission not granted'),
  reasonOf(new Error('Network request failed')),
  reasonOf(new Error('DeviceNotRegistered')),
  reasonOf(new Error('something nobody has ever seen')),
]);
eq('six distinct causes produce six distinct reasons', reasons.size, 6);

// ── 2. An unrecognised error is still reported IN FULL ───────────────────────
// The property that must survive any wording change at Expo: we would rather
// say "Registration failed" plus the exact text than confidently say the wrong
// thing. This is the check that makes the lenient matching above safe.
const odd = diagnosePushError(new Error('Kernel panic in the push subsystem #4821'));
eq('an unmatched error is reason=unknown', odd.reason, 'unknown');
check(
  'an unmatched error keeps its message verbatim',
  odd.detail.includes('Kernel panic in the push subsystem #4821'),
);
check('every diagnosis carries a non-empty title', odd.title.length > 0);

// ── 3. Forced reasons win over matching ──────────────────────────────────────
// The caller sometimes knows better than the text: a Supabase write failure is
// a storage failure even when its message mentions permission (RLS refusals
// say exactly that, and would otherwise be reported as an iOS setting).
eq(
  'a forced reason overrides the rules',
  diagnosePushError({ message: 'permission denied for table device_push_tokens' }, 'storage')
    .reason,
  'storage',
);
eq(
  'without forcing, that same RLS message would have misread as permission',
  reasonOf({ message: 'permission denied for table device_push_tokens' }),
  'permission',
);

// ── 4. Actionability: what the UI keys off ───────────────────────────────────
check(
  'a permission failure offers iOS Settings',
  diagnosePushError('Permission not granted').opensSettings,
);
check(
  'a credentials failure does NOT offer a retry — nothing on the phone can fix it',
  !diagnosePushError(new Error('no valid "aps-environment" entitlement')).retryable,
);
check(
  'a credentials failure does not send the reader to iOS Settings either',
  !diagnosePushError(new Error('no valid "aps-environment" entitlement')).opensSettings,
);
check('a network failure is retryable', diagnosePushError(new Error('timed out')).retryable);

// ── 5. errorText survives whatever was thrown ────────────────────────────────
eq('a string error passes through', errorText('plain'), 'plain');
check('an Error uses its message', errorText(new Error('boom')).includes('boom'));
check(
  'a Supabase-style object uses its message',
  errorText({ message: 'row violates policy', code: '42501' }).includes('row violates policy'),
);
check('null never returns empty', errorText(null).length > 0);
check('an unserialisable value never returns empty', errorText(Symbol('x')).length > 0);
check(
  'an object with no message still yields something printable',
  errorText({ weird: true }).length > 0,
);

// ── 6. Expo's reply is read, not assumed ─────────────────────────────────────
// A 200 is not a delivery: the ticket inside it is what says so.
eq(
  'an ok ticket is a success with its receipt',
  interpretExpoResponse({ data: [{ status: 'ok', id: 'rcpt-1' }] }),
  { ok: true, receiptId: 'rcpt-1' },
);
const dead = interpretExpoResponse({
  data: [
    {
      status: 'error',
      message: '"ExponentPushToken[x]" is not a registered push notification recipient',
      details: { error: 'DeviceNotRegistered' },
    },
  ],
});
check('an error ticket is NOT a success', !dead.ok);
eq('an error ticket keeps Expo\'s own code', dead.diagnosis?.reason, 'stale');
const badCreds = interpretExpoResponse({
  data: [{ status: 'error', message: 'nope', details: { error: 'InvalidCredentials' } }],
});
eq('InvalidCredentials surfaces as a credentials problem', badCreds.diagnosis?.reason, 'credentials');
check(
  'a top-level errors array is a failure',
  !interpretExpoResponse({ errors: [{ code: 'PUSH_TOO_MANY_EXPERIENCE_IDS', message: 'no' }] }).ok,
);
check('an empty body is a failure, not a silent pass', !interpretExpoResponse(null).ok);
check('a body with no ticket is a failure', !interpretExpoResponse({ data: [] }).ok);
check(
  'a bare object ticket is accepted (Expo does this for a single message)',
  interpretExpoResponse({ data: { status: 'ok', id: 'rcpt-2' } }).ok,
);

// ── 7. The test push rides the REAL payload contract ─────────────────────────
// A test that invented its own payload would pass while the deep link was
// broken, which is the failure mode pushRoute.ts was written to prevent.
const msg = buildTestMessage('ExponentPushToken[abc]') as {
  to: string;
  data: { v: number; type: string };
  title: string;
  body: string;
};
eq('the test message addresses this device', msg.to, 'ExponentPushToken[abc]');
eq('the test payload carries the current route version', msg.data.v, PUSH_ROUTE_VERSION);
check('the test payload names a routed type', msg.data.type === 'new_bets');
check('the test message says what it is', msg.title.toLowerCase().includes('test'));

// ── 8. The version is pinned on BOTH sides ───────────────────────────────────
// pushRouteVersion.ts and push_notifier.py are one contract shipped by two
// deploys (OTA and the worker). A silent divergence routes every tap nowhere.
const notifier = readFileSync(
  join(import.meta.dirname, '..', '..', 'tracking', 'push_notifier.py'),
  'utf-8',
);
const declared = /PUSH_ROUTE_VERSION\s*=\s*(\d+)/.exec(notifier);
check('push_notifier.py declares a route version', declared != null);
eq(
  'the app and the worker agree on the route version',
  declared ? Number(declared[1]) : null,
  PUSH_ROUTE_VERSION,
);

// ── Report ───────────────────────────────────────────────────────────────────
if (failures.length > 0) {
  console.error(`verify_push: ${failures.length} FAILED, ${passed} passed`);
  for (const f of failures) console.error(`  ✗ ${f}`);
  process.exit(1);
}
console.log(`verify_push: ${passed} checks passed`);

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

// ── 1. Distinct causes get distinct diagnoses ────────────────────────────────────
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

// ── 4b. The two forced-only reasons ──────────────────────────────────────────
// Neither is inferable from an error's text; only the caller knows. A dismissed
// prompt and a denial in iOS Settings need OPPOSITE recoveries, and the hook
// computes canAskAgain precisely to tell them apart — it forced one reason for
// both until the 2026-09-12 UX review, sending a user who simply swiped the
// prompt away into a Settings screen where the app is not yet listed.
const dismissed = diagnosePushError('prompt dismissed', 'prompt');
const denied = diagnosePushError('denied in settings', 'permission');
check('a dismissed prompt can be retried in-app', dismissed.retryable);
check('a dismissed prompt does NOT send the reader to iOS Settings', !dismissed.opensSettings);
check('a denial DOES send the reader to iOS Settings', denied.opensSettings);
check(
  'the two permission states give different advice',
  dismissed.advice !== denied.advice && dismissed.title !== denied.title,
);

// A failed opt-OUT is the opposite sentence to a failed opt-IN: the reader is
// STILL registered, and saying "could not be saved" would read as the reverse.
const stop = diagnosePushError({ message: 'write refused' }, 'stop');
const store = diagnosePushError({ message: 'write refused' }, 'storage');
check('a failed opt-out says notifications are still ON', stop.title.toLowerCase().includes('still on'));
check('a failed opt-out is retryable', stop.retryable);
check('opt-in and opt-out failures do not share copy', stop.title !== store.title);

// ── 4c. Every reason is actionable or honestly dead-ended ────────────────────
// A reason with no button must at least say why nothing can be done here; a
// reason with a button must not also tell the reader to do something else.
for (const d of [dismissed, denied, stop, store, odd,
                 diagnosePushError(new Error('DeviceNotRegistered')),
                 diagnosePushError(new Error('timed out')),
                 diagnosePushError(new Error('aps-environment')),
                 diagnosePushError(new Error('cannot find native module'))]) {
  check(`${d.reason}: advice is non-empty`, d.advice.trim().length > 0);
  check(
    `${d.reason}: a retryable reason does not ALSO tell the reader to toggle`,
    !d.retryable || !/toggle off and back on/i.test(d.advice),
  );
}

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
// 'dropped' routes to Picks -> Today, which is true whatever is on the board.
// A test push must not land on Signals claiming signals that do not exist.
check('the test payload names a routed type', msg.data.type === 'dropped');
check(
  'the test push does not land on a board that would be announcing signals',
  msg.data.type !== 'new_bets' && msg.data.type !== 'live_signals',
);
check('the body says where the tap goes', msg.body.toLowerCase().includes("today's board"));
check('the test message says what it is', msg.title.toLowerCase().includes('test'));

// ── 7b. The hook actually USES the distinction ───────────────────────────────
// The copy checks above prove the two permission states READ differently; this
// proves the caller still routes them apart. The bug being guarded is precise:
// the hook computed `perm.canAskAgain` to tell them apart and then passed one
// hard-coded reason for both, so the distinction existed in the code and not
// in the product. A source check, because the branch needs a native module to
// reach at runtime.
const hook = readFileSync(
  join(import.meta.dirname, '..', 'src', 'hooks', 'usePushNotifications.ts'),
  'utf-8',
);
const hookCode = hook
  .split('\n')
  .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
  .join('\n');
check(
  'the hook forwards canAskAgain into the reason it reports',
  /canAskAgain\s*\?\s*'prompt'\s*:\s*'permission'/.test(hookCode),
);
check(
  "the opt-out failure reports 'stop', not 'storage'",
  /diagnosePushError\(error,\s*'stop'\)/.test(hookCode),
);
// SCOPED TO registerForPush's BODY. The first version of this check matched
// `const { error } = await supabase` anywhere in the file and was therefore
// satisfied by unregisterForPush's own destructure — it passed while the
// upsert's error was thrown away, which is the exact bug it was written for.
// Watched failing before this comment was written.
const registerBody = hookCode.slice(
  hookCode.indexOf('export function registerForPush'),
  hookCode.indexOf('export async function unregisterForPush'),
);
check('registerForPush was located in the source', registerBody.length > 200);
check(
  'the registration upsert still reads its error',
  /const \{ error \} = await supabase[\s\S]{0,80}\.upsert\(/.test(registerBody),
);
check(
  'the registration failure path acts on that error',
  /if \(error\) \{[\s\S]{0,200}status: 'failed'/.test(registerBody),
);

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

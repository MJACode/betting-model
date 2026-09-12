/**
 * What went wrong when this device tried to register for push, in words the
 * reader can act on.
 *
 * WHY THIS FILE EXISTS. Until 2026-09-12 `usePushNotifications` wrapped the
 * whole registration in one `try { ... } catch { console.warn }`. Every
 * failure — a build with no push entitlement, a denied OS prompt, a dead
 * network, a rejected write — produced the same outcome on screen: a toggle
 * that slid to ON, registered nothing, and said nothing. `device_push_tokens`
 * held ZERO rows on 2026-09-12 while `push_sent` held 1,736 ledgered events,
 * and nothing in the app could have told you which of those four it was.
 *
 * So the classification below is a CONVENIENCE and the raw message is the
 * TRUTH. Every diagnosis carries `detail` verbatim, an unmatched error is
 * reported as 'unknown' with its own text rather than squeezed into the
 * nearest bucket, and no caller re-parses `detail` to decide anything. If
 * Expo changes its wording, this degrades to "Registration failed" plus the
 * exact message — never to a confident wrong answer.
 *
 * Pure on purpose: no react-native import, so scripts/verify_push.ts can run
 * it under tsx (the same split as lib/authHelpers.ts).
 */

export type PushFailureReason =
  | 'unsupported' // this binary has no push module, or it is a simulator
  | 'prompt' // the OS prompt was dismissed and CAN be shown again
  | 'permission' // notifications are off for this app in iOS Settings
  | 'credentials' // the build carries no APNs entitlement / EAS has no push key
  | 'network' // could not reach Expo's token service
  | 'storage' // Apple issued a token but we could not save it
  | 'stop' // the opt-OUT write failed, so delivery has NOT stopped
  | 'stale' // the stored token is no longer a valid recipient
  | 'unknown'; // unmatched — `detail` is all we know, and it is shown as-is

/**
 * Reasons that are never inferred from an error's text — the caller is the
 * only thing that knows them. `prompt` vs `permission` is decided by
 * `canAskAgain`, and `stop` by which direction the write was going: the same
 * refusal means "you are not registered" on the way in and "you are still
 * registered" on the way out, which are opposite sentences.
 */
export type ForcedOnlyReason = 'prompt' | 'stop';

export interface PushDiagnosis {
  reason: PushFailureReason;
  /** One line, shown under the Settings toggle. */
  title: string;
  /** What the reader can do about it. Empty when there is nothing they can do. */
  advice: string;
  /** The underlying error text, verbatim. Displayed, never re-parsed. */
  detail: string;
  /** True when pressing "Try again" could plausibly succeed unaided. */
  retryable: boolean;
  /** True when the fix lives in iOS Settings, so the UI offers to open it. */
  opensSettings: boolean;
}

/**
 * Substrings matched case-insensitively against the error text, first rule
 * wins. Deliberately lenient and deliberately ORDERED: a credentials failure
 * and a permission failure can both mention "notification", so the more
 * specific signal is tested first. These are matched, not asserted — see the
 * file header on why an unmatched error is still fully reported.
 */
const RULES: ReadonlyArray<{ reason: PushFailureReason; match: readonly string[] }> = [
  {
    // A binary built before expo-notifications landed (2026-09-08) throws on
    // the very first property access, and so does any simulator.
    reason: 'unsupported',
    match: [
      'cannot find native module',
      'native module',
      'nativemodule',
      'must use physical device',
      'simulator',
      'not supported on',
      'not available on',
    ],
  },
  {
    // Expo's own verdict on a token it will not deliver to. Tested before
    // 'credentials' because its message names "push notification recipient",
    // which the looser credentials matches would otherwise swallow.
    reason: 'stale',
    match: ['devicenotregistered', 'not a registered push notification recipient'],
  },
  {
    // The build has no `aps-environment` entitlement, or EAS holds no APNs
    // key for the project. Neither is fixable from the phone.
    reason: 'credentials',
    match: [
      'aps-environment',
      'entitlement',
      'invalidcredentials',
      'push notification credentials',
      'no valid push',
      'mismatchsenderid',
      'firebase',
      'fcm',
    ],
  },
  {
    reason: 'permission',
    match: [
      'permission',
      'denied',
      'not authorized',
      'notauthorized',
      'user rejected',
    ],
  },
  {
    reason: 'network',
    match: [
      'network request failed',
      'failed to fetch',
      'timeout',
      'timed out',
      'econnrefused',
      'enotfound',
      'offline',
      'socket',
    ],
  },
];

const COPY: Record<PushFailureReason, { title: string; advice: string; retryable: boolean; opensSettings: boolean }> = {
  unsupported: {
    title: 'This build cannot receive notifications',
    // Deliberately covers both cases this bucket matches. It also catches a
    // SIMULATOR, which can never receive a push however new the build is, and
    // which is where a developer will see this message most often — so the
    // TestFlight instruction is conditioned rather than stated flat.
    advice:
      'On a physical device, install the latest build from TestFlight — this one was built before notifications were added. A simulator cannot receive them at all.',
    retryable: false,
    opensSettings: false,
  },
  prompt: {
    title: 'Notifications need your permission',
    // NOT "open iOS Settings": the prompt was dismissed rather than denied, so
    // the app is not listed under Settings → Notifications yet and sending the
    // reader there dead-ends them.
    advice: 'Tap Try again and choose Allow.',
    retryable: true,
    opensSettings: false,
  },
  permission: {
    title: 'Notifications are turned off for Signalbase',
    advice: 'Turn them on in iOS Settings → Notifications → Signalbase, then come back.',
    retryable: true,
    opensSettings: true,
  },
  credentials: {
    title: 'This build is not registered for Apple push',
    advice:
      'The app is missing its push entitlement, so Apple will not issue it a token. A new TestFlight build with push credentials is needed — nothing on the phone can fix it.',
    retryable: false,
    opensSettings: false,
  },
  network: {
    title: 'Could not reach the notification service',
    advice: 'Check your connection and try again.',
    retryable: true,
    opensSettings: false,
  },
  stale: {
    // Not "no longer a valid recipient" — that is Expo's phrase for its own
    // records, and it reads as an accusation about the person.
    title: 'This device needs to register again',
    // ONE recovery. It used to name a second ("turn the toggle off and back
    // on") beside a Try again button, leaving the reader to guess which was
    // real and unable to tell whether their tap had done anything.
    advice:
      'Apple has retired the token we hold — normal after a reinstall or a long gap. Tap Try again to register a fresh one.',
    retryable: true,
    opensSettings: false,
  },
  stop: {
    title: 'Notifications are still on for this device',
    advice:
      'You turned them off, but the server did not hear it, so alerts will keep arriving. Tap Try again.',
    retryable: true,
    opensSettings: false,
  },
  storage: {
    title: 'Registered with Apple, but this device could not be saved',
    advice:
      'Apple issued a push token and the server was not able to store it, so it does not yet know where to send. Try again.',
    retryable: true,
    opensSettings: false,
  },
  unknown: {
    title: 'Registration failed',
    // This bucket's detail is the whole answer, so NotificationsCard opens it
    // expanded rather than behind "Show details" — the advice used to point at
    // text that was collapsed out of sight.
    advice: 'The exact error is below. Try again, and include it if you send feedback.',
    retryable: true,
    opensSettings: false,
  },
};

/** The error's text, however it was thrown. Never throws, never returns ''. */
export function errorText(err: unknown): string {
  if (err == null) return 'No error reported.';
  if (typeof err === 'string') return err.trim() || 'Empty error.';
  if (err instanceof Error) {
    const text = [err.message, (err as { code?: string }).code].filter(Boolean).join(' ');
    return text.trim() || err.name || 'Error with no message.';
  }
  if (typeof err === 'object') {
    const o = err as { message?: unknown; error?: unknown; code?: unknown };
    const text = [o.message, o.error, o.code]
      .filter((v) => typeof v === 'string' && v)
      .join(' ');
    if (text.trim()) return text.trim();
    try {
      return JSON.stringify(err);
    } catch {
      return 'Unserialisable error.';
    }
  }
  return String(err);
}

/** Classify a registration failure. `reason` is a hint; `detail` is the record. */
export function diagnosePushError(err: unknown, forced?: PushFailureReason): PushDiagnosis {
  const detail = errorText(err);
  const haystack = detail.toLowerCase();
  const reason =
    forced ?? RULES.find((r) => r.match.some((m) => haystack.includes(m)))?.reason ?? 'unknown';
  return { reason, detail, ...COPY[reason] };
}

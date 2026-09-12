import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';
import { useCallback, useEffect, useState } from 'react';
import { Platform } from 'react-native';

import { getDeviceId } from '@/hooks/useDeviceId';
import { usePushOptIn } from '@/hooks/usePushOptIn';
import { diagnosePushError, type PushDiagnosis } from '@/lib/pushDiagnosis';
import { supabase } from '@/lib/supabase';

/**
 * Register this device for push, and SAY WHAT HAPPENED.
 *
 * The previous version was five lines of happy path inside one `try/catch`
 * that ended in `console.warn`. Measured on 2026-09-12: `device_push_tokens`
 * held zero rows against 1,736 ledgered `push_sent` events, and the app could
 * not tell you whether that was a build with no entitlement, a declined
 * prompt, or a write the server refused — all three looked like a toggle that
 * turned on. Worse, `.upsert()`'s `{ error }` was never read, so a rejected
 * write was indistinguishable from a successful one.
 *
 * So every outcome now lands in a state other code can render:
 *   idle        — opted out, nothing attempted
 *   registering — in flight
 *   registered  — Apple issued a token AND the row was written
 *   failed      — `diagnosis` says which of the five reasons it was
 *
 * The state lives at module level (the useOnboarding / usePushOptIn pattern)
 * because App.tsx mounts the registrar and SettingsScreen renders the result;
 * two copies would drift, and two mounts must not race two registrations —
 * hence the in-flight promise below.
 */

export type PushStatus = 'idle' | 'registering' | 'registered' | 'failed';

export interface PushState {
  status: PushStatus;
  /** The Expo token, once Apple and Expo have issued one. */
  token: string | null;
  /** Set whenever `status` is 'failed'; null otherwise. */
  diagnosis: PushDiagnosis | null;
  /** ISO timestamp of the last successful registration, for the diagnostics row. */
  registeredAt: string | null;
}

/** The last token we successfully registered, so opt-OUT can find its row
 *  after a restart — `getExpoPushTokenAsync` is not callable once permission
 *  has been revoked, which is exactly when someone opts out. */
const TOKEN_KEY = 'push.token.v1';

const listeners = new Set<(s: PushState) => void>();
let state: PushState = { status: 'idle', token: null, diagnosis: null, registeredAt: null };
let inFlight: Promise<PushState> | null = null;

function setState(next: Partial<PushState>): PushState {
  state = { ...state, ...next };
  listeners.forEach((fn) => fn(state));
  return state;
}

async function rememberToken(token: string | null): Promise<void> {
  try {
    if (token) await AsyncStorage.setItem(TOKEN_KEY, token);
    else await AsyncStorage.removeItem(TOKEN_KEY);
  } catch {
    // A device that cannot persist the token still registers fine; it just
    // needs a live token to opt out. Not worth failing registration over.
  }
}

async function rememberedToken(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/**
 * Do the registration. Never throws; every failure becomes a diagnosis.
 * Concurrent callers share one attempt.
 */
export function registerForPush(): Promise<PushState> {
  if (inFlight) return inFlight;
  inFlight = (async () => {
    setState({ status: 'registering', diagnosis: null });
    try {
      // Ask what we already have before prompting. On iOS a second request
      // after a denial resolves 'denied' WITHOUT showing anything, so without
      // this split the two cases are indistinguishable — and they need
      // different advice ("accept the prompt" vs "open iOS Settings").
      const existing = await Notifications.getPermissionsAsync();
      const perm = existing.granted
        ? existing
        : existing.canAskAgain
          ? await Notifications.requestPermissionsAsync()
          : existing;

      if (!perm.granted) {
        return setState({
          status: 'failed',
          diagnosis: diagnosePushError(
            perm.canAskAgain
              ? 'The notification permission prompt was dismissed without allowing.'
              : 'Notifications are denied for this app in iOS Settings.',
            'permission',
          ),
        });
      }

      const projectId = '0e16eb4b-190b-4356-be61-5b7a6b1da5ee';
      const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
      if (!token) {
        return setState({
          status: 'failed',
          diagnosis: diagnosePushError('Expo returned no push token.', 'credentials'),
        });
      }

      const deviceId = await getDeviceId();
      const registeredAt = new Date().toISOString();
      // READ THE ERROR. supabase-js resolves rather than throwing, so the old
      // bare `await supabase.from(...).upsert(...)` swallowed an RLS refusal,
      // a schema mismatch and a network failure alike.
      const { error } = await supabase.from('device_push_tokens').upsert(
        {
          token,
          device_id: deviceId,
          platform: Platform.OS,
          enabled: true,
          last_seen: registeredAt,
        },
        { onConflict: 'token' },
      );
      if (error) {
        return setState({
          status: 'failed',
          token,
          diagnosis: diagnosePushError(error, 'storage'),
        });
      }

      await rememberToken(token);
      return setState({ status: 'registered', token, diagnosis: null, registeredAt });
    } catch (err) {
      // Anything the native module threw: no module in this binary, a
      // simulator, a missing aps-environment entitlement, a dead network.
      // diagnosePushError classifies what it recognises and reports the rest
      // verbatim rather than guessing.
      return setState({ status: 'failed', diagnosis: diagnosePushError(err) });
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}

/**
 * Stop delivery to this device. Flips the row rather than deleting it, so the
 * backend's `WHERE enabled = TRUE` stops selecting it and re-opting in is an
 * update rather than a new row.
 *
 * NOTHING DID THIS BEFORE 2026-09-12. The toggle wrote an AsyncStorage boolean
 * and no more, so turning notifications OFF left `enabled = true` and the
 * worker would have kept sending indefinitely. No user has hit it only because
 * no token row has ever existed.
 */
export async function unregisterForPush(): Promise<void> {
  const token = state.token ?? (await rememberedToken());
  setState({ status: 'idle', token: null, diagnosis: null });
  // Nothing was ever registered from this install, so there is no row to flip
  // — and no write on every cold start of a device that has never opted in.
  if (!token) return;
  const { error } = await supabase
    .from('device_push_tokens')
    .update({ enabled: false, last_seen: new Date().toISOString() })
    .eq('token', token);
  if (error) {
    // Surfaced, not swallowed: the reader has turned notifications off and is
    // entitled to know the server did not hear it. NotificationsCard renders a
    // failure whatever the toggle now says, precisely so this one is visible.
    setState({ status: 'failed', diagnosis: diagnosePushError(error, 'storage') });
    return;
  }
  // Forget it only once the server has agreed, so a failed opt-out can be
  // retried against the right row rather than losing it.
  await rememberToken(null);
}

/** Subscribe to the shared registration state. Render-only; starts nothing. */
export function usePushState(): PushState {
  const [snapshot, setSnapshot] = useState<PushState>(state);
  useEffect(() => {
    setSnapshot(state);
    const listener = (s: PushState) => setSnapshot(s);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return snapshot;
}

/**
 * Mount ONCE (App.tsx). Drives registration off the opt-in flag and exposes
 * the result, plus a retry for the Settings screen's error row.
 */
export function usePushNotifications(): PushState & { retry: () => void } {
  const { enabled, ready } = usePushOptIn();
  const snapshot = usePushState();

  useEffect(() => {
    // `ready` guards the first frame: usePushOptIn reports `false` before
    // AsyncStorage answers, and acting on that would unregister on every cold
    // start of an opted-in device.
    if (!ready) return;
    if (enabled) void registerForPush();
    else void unregisterForPush();
  }, [enabled, ready]);

  const retry = useCallback(() => {
    void registerForPush();
  }, []);

  return { ...snapshot, retry };
}

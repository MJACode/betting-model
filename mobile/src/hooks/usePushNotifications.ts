import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';
import { useCallback, useEffect, useState } from 'react';
import { Platform } from 'react-native';

import { readAuthStatus, readAuthUserId, subscribeAuthUser } from '@/hooks/useAuth';
import { getDeviceId } from '@/hooks/useDeviceId';
import { clearPushOptInForAccountDeletion, usePushOptIn } from '@/hooks/usePushOptIn';
import { diagnosePushError, type PushDiagnosis } from '@/lib/pushDiagnosis';
import { enqueuePushWrite } from '@/lib/pushQueue';
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
/** Account deletion sets this so a registration still waiting on the
 *  permission prompt cannot finish last and leave the token enabled. */
let pushWritesClosed = false;
let state: PushState = { status: 'idle', token: null, diagnosis: null, registeredAt: null };
function setState(next: Partial<PushState>): PushState {
  state = { ...state, ...next };
  listeners.forEach((fn) => fn(state));
  return state;
}

/**
 * Save the token. Pass p_user_id when we know who is signed in. If the
 * deployed function does not take that argument yet, retry without it so
 * registration does not start failing before the inbox migration is applied.
 */
function pushTokenArgMissing(error: { message?: string; code?: string }): boolean {
  const text = `${error.code ?? ''} ${error.message ?? ''}`;
  return /PGRST202|p_user_id|Could not find the function|schema cache/i.test(text);
}

async function savePushToken(args: {
  p_token: string;
  p_device_id: string;
  p_platform: string;
  p_enabled: boolean;
  p_last_seen: string;
  p_user_id: string | null;
}): Promise<{ error: { message?: string; code?: string } | null }> {
  const { p_user_id, ...rest } = args;
  const withUser = p_user_id ? { ...rest, p_user_id } : rest;
  const first = await supabase.rpc('save_device_push_token', withUser);
  if (!first.error || !p_user_id) return { error: first.error };
  const text = `${first.error.code ?? ''} ${first.error.message ?? ''}`;
  if (!/PGRST202|p_user_id|Could not find the function|schema cache/i.test(text)) {
    return { error: first.error };
  }
  const second = await supabase.rpc('save_device_push_token', rest);
  return { error: second.error };
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
  return enqueuePushWrite(() => registerForPushNow());
}

async function registerForPushNow(): Promise<PushState> {
  return (async () => {
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
        // The two cases need OPPOSITE advice, which is the whole reason the
        // check above is split. A dismissed prompt can simply be asked again;
        // a denial has to be undone in iOS Settings — where an app that has
        // never been granted anything is not yet listed, so sending a
        // dismissed-prompt user there dead-ends them.
        return setState({
          status: 'failed',
          diagnosis: diagnosePushError(
            perm.canAskAgain
              ? 'The notification permission prompt was dismissed without allowing.'
              : 'Notifications are denied for this app in iOS Settings.',
            perm.canAskAgain ? 'prompt' : 'permission',
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
      // READ THE ERROR. supabase-js resolves rather than throwing.
      // The write is an RPC, not a table upsert. INSERT ... ON CONFLICT DO
      // UPDATE is rejected (42501) for anon and authenticated while the table
      // has no SELECT policy, including when the row does not exist yet. A
      // SELECT policy would let the anon key list every Expo token. The
      // function runs as the table owner and returns nothing.
      // p_user_id is optional and only exists after the inbox migration.
      // A server that has not been migrated rejects the extra argument, and
      // the same call without it still registers the device.
      const userId = readAuthUserId();
      if (pushWritesClosed) {
        return setState({ status: 'idle', token: null, diagnosis: null });
      }
      const base = {
        p_token: token,
        p_device_id: deviceId,
        p_platform: Platform.OS,
        p_enabled: true,
        p_last_seen: registeredAt,
      };
      const payload = userId ? { ...base, p_user_id: userId } : base;
      const { error } = await supabase.rpc('save_device_push_token', payload);
      if (error) {
        const failed = userId && pushTokenArgMissing(error)
          ? (await supabase.rpc('save_device_push_token', base)).error
          : error;
        if (failed) return setState({ status: 'failed', token, diagnosis: diagnosePushError(failed, 'storage') });
      }
      if (pushWritesClosed) {
        await savePushToken({ ...base, p_enabled: false, p_user_id: userId });
        await rememberToken(null);
        return setState({ status: 'idle', token: null, diagnosis: null });
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
      /* The queue, not an in-flight flag, serialises the next call. */
    }
  })();
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
export async function unregisterForPush(): Promise<boolean> {
  // Behind any registration already in flight. Otherwise that write lands
  // last and the server stays enabled after the reader turned notifications off.
  return enqueuePushWrite(() => unregisterForPushNow());
}

async function unregisterForPushNow(): Promise<boolean> {
  const token = state.token ?? (await rememberedToken());
  setState({ status: 'idle', token: null, diagnosis: null });
  // Nothing was ever registered from this install, so there is no row to flip
  // — and no write on every cold start of a device that has never opted in.
  if (!token) return true;
  // Same function as registration. A direct UPDATE matches 0 rows and reports
  // success, because the row is not visible without a SELECT policy, so the
  // toggle would say notifications are off while the worker still sends.
  const deviceId = await getDeviceId();
  const { error } = await savePushToken({
    p_token: token,
    p_device_id: deviceId,
    p_platform: Platform.OS,
    p_enabled: false,
    p_last_seen: new Date().toISOString(),
    p_user_id: readAuthUserId(),
  });
  if (error) {
    // Surfaced, not swallowed: the reader has turned notifications off and is
    // entitled to know the server did not hear it. NotificationsCard renders a
    // failure whatever the toggle now says, precisely so this one is visible.
    // 'stop', not 'storage': the same refusal means "you are not registered"
    // on the way in and "you are STILL registered" on the way out, and only
    // the second one is true here.
    setState({ status: 'failed', diagnosis: diagnosePushError(error, 'stop') });
    return false;
  }
  // Forget it only once the server has agreed, so a failed opt-out can be
  // retried against the right row rather than losing it.
  await rememberToken(null);
  return true;
}

/** Opt out and unregister. False when the server still has the token enabled.
 *  Not queued: a registration stuck on the permission prompt must not hold
 *  the delete spinner. The flag stops that registration from enabling the row. */
export async function clearPushForAccountDeletion(): Promise<boolean> {
  pushWritesClosed = true;
  await clearPushOptInForAccountDeletion();
  return unregisterForPushNow();
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
    // start of an opted-in device. Auth can still be `loading` after that.
    // Re-save when the user id changes, including sign-in after a cold start
    // that registered with no user, and sign-out (auth.uid() is then null,
    // which unlinks the token). Opt-out does not wait for a session:
    // save_device_push_token stays callable without one.
    if (!ready) return;
    let seen = '';
    let have = false;
    return subscribeAuthUser((userId, status) => {
      if (status === 'loading' || readAuthStatus() === 'loading') return;
      const key = userId ?? '';
      if (have && seen === key) return;
      have = true;
      seen = key;
      if (enabled) void registerForPush();
      else void unregisterForPush();
    });
  }, [enabled, ready]);

  const retry = useCallback(() => {
    void registerForPush();
  }, []);

  return { ...snapshot, retry };
}

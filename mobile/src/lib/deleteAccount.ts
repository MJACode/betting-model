/**
 * Account deletion. The SQL functions do the server deletes. This module
 * orders the steps the screen cannot see:
 *
 *   1. Call delete_my_account(). A stale session or a rejected JWT comes
 *      back as `stale` and deletes nothing. Any other error is `error`.
 *      Nothing is unlinked before this call succeeds.
 *   2. Unlink Discord and SharpSports. A failure here is not success: the
 *      login stays, so a retry can still revoke the links.
 *   3. Call delete_my_login(). That removes auth.users.
 *   4. Wipe this install and sign out locally.
 *
 * The phone clock does not gate any step. The 10-minute rule is the
 * server's, inside both functions.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import { clearBankrollForAccountDeletion } from '@/hooks/useBankroll';
import { clearCustomModelsForAccountDeletion } from '@/hooks/useCustomModels';
import { clearFeedbackForAccountDeletion } from '@/hooks/useFeedback';
import { clearLineLegsForAccountDeletion } from '@/hooks/useLineLegs';
import { clearManualBetsForAccountDeletion } from '@/hooks/useManualBets';
import { clearParlaySlipForAccountDeletion } from '@/hooks/useParlaySlip';
import {
  clearPreferredBooksForAccountDeletion,
  resetPreferredBooksDeviceRow,
} from '@/hooks/usePreferredBooks';
import { clearPushForAccountDeletion } from '@/hooks/usePushNotifications';
import { clearSavedParlaysForAccountDeletion } from '@/hooks/useSavedParlays';
import { clearSportsbookConnectionsForAccountDeletion } from '@/hooks/useSportsbookConnection';
import { clearStakeSettingsForAccountDeletion } from '@/hooks/useStakeSettings';
import { clearTrackedBetsForAccountDeletion } from '@/hooks/useTrackedBets';
import { AUTH_ENABLED } from './authConfig';
import { assertAuthEnabled } from './authHelpers';
import { ACCOUNT_WIPE_KEYS, QUERY_CACHE_KEYS, isStaleSessionError } from './deleteAccountHelpers';
import { discordLinkReady } from './discordConfig';
import { unlinkDiscord } from './discord';
import { setModelClv } from './sharpScore';
import { unlinkSportsbooks } from './sharpsports';
import { clearSettledCache } from './settledPickCache';
import { supabase } from './supabase';
import { setServerThresholds } from './thresholds';

export type LocalFailure = 'unlink' | 'login' | 'tracked' | 'wipe';

export type DeleteOutcome =
  | { ok: true }
  | { ok: false; stale: true; serverDeleted: false }
  | { ok: false; stale: false; serverDeleted: false }
  | {
      ok: false;
      stale: boolean;
      serverDeleted: true;
      localFailure: LocalFailure;
      loginDeleted: boolean;
    };

/** Settled picks, action thresholds, and model CLV. Memory and AsyncStorage. */
export async function clearQueryCache(): Promise<void> {
  setServerThresholds(null);
  setModelClv(null);
  clearFeedbackForAccountDeletion();
  await clearSettledCache();
  await AsyncStorage.multiRemove([...QUERY_CACHE_KEYS]);
}

/**
 * Wipe this install's copies. Returns 'tracked' when the tracked_bets delete
 * failed (that one is surfaced on its own). Returns 'wipe' for any other
 * failure. Does not sign out and does not rewrite the device books row.
 */
export async function wipeLocalAccountData(deviceId: string | null): Promise<LocalFailure | null> {
  let failure: LocalFailure | null = null;
  try {
    await Promise.all([
      clearCustomModelsForAccountDeletion(),
      clearTrackedBetsForAccountDeletion(),
      clearBankrollForAccountDeletion(),
      clearStakeSettingsForAccountDeletion(),
      clearManualBetsForAccountDeletion(),
      clearSavedParlaysForAccountDeletion(),
      clearParlaySlipForAccountDeletion(),
      clearLineLegsForAccountDeletion(),
      clearSportsbookConnectionsForAccountDeletion(),
      clearPreferredBooksForAccountDeletion(),
      clearQueryCache(),
    ]);
    const pushCleared = await clearPushForAccountDeletion();
    await AsyncStorage.multiRemove([...ACCOUNT_WIPE_KEYS]);
    if (!pushCleared) failure = 'wipe';
  } catch (e) {
    console.warn('[deleteAccount] local wipe', e);
    failure = 'wipe';
  }
  if (!deviceId) return failure;
  // This install's push-notify rows. The policy already allows the delete.
  // The public picks table is not this table.
  const { error } = await supabase.from('tracked_bets').delete().eq('device_id', deviceId);
  if (error) {
    console.warn('[deleteAccount] tracked_bets', error.message);
    failure = 'tracked';
  }
  return failure;
}

/**
 * Discord and SharpSports, only after delete_my_account() has committed.
 * False when either call fails. The login is still there in that case.
 */
async function unlinkAfterDelete(deviceId: string | null): Promise<boolean> {
  let ok = true;
  if (deviceId) {
    try {
      await unlinkSportsbooks(deviceId);
    } catch (e) {
      console.warn('[deleteAccount] sharpsports unlink', e);
      ok = false;
    }
  }
  // Always when linking is on, not only when the access row says linked.
  // That row can still be loading. Unlink with no row is a no-op. A
  // role-removal failure throws, and delete_my_login() does not run.
  if (discordLinkReady()) {
    try {
      await unlinkDiscord();
    } catch (e) {
      console.warn('[deleteAccount] discord unlink', e);
      ok = false;
    }
  }
  return ok;
}

/**
 * Wipe this install and sign out locally. The login row is already gone
 * when this is called from the success path, so a failure here must not be
 * reported as "nothing was deleted". 'tracked' wins over 'wipe' so the
 * tracked-bet failure stays visible.
 */
export async function finishLocalAccountDeletion(
  deviceId: string | null,
): Promise<LocalFailure | null> {
  let failure = await wipeLocalAccountData(deviceId);
  const signedOut = await supabase.auth.signOut({ scope: 'local' });
  if (signedOut.error) {
    console.warn('[deleteAccount] local sign-out', signedOut.error.message);
    if (failure !== 'tracked') failure = 'wipe';
    return failure;
  }
  // After the local sign-out, auth.uid() is null, so this rewrites the
  // device row only and does not recreate the user: row.
  if (deviceId) {
    try {
      await resetPreferredBooksDeviceRow(deviceId);
    } catch (e) {
      console.warn('[deleteAccount] preferred books', e);
      if (failure !== 'tracked') failure = 'wipe';
    }
  }
  return failure;
}

/**
 * Unlink, delete the login, then clear the phone. Call only after
 * delete_my_account() has committed. A stale login delete opens re-auth.
 * An unlink failure leaves the login in place.
 */
export async function continueAccountDeletion(
  deviceId: string | null,
): Promise<DeleteOutcome> {
  const unlinked = await unlinkAfterDelete(deviceId);
  if (!unlinked) {
    return { ok: false, stale: false, serverDeleted: true, localFailure: 'unlink', loginDeleted: false };
  }
  const { error } = await supabase.rpc('delete_my_login');
  if (error) {
    // The data delete already committed. Stay on the local screen either way.
    // Stale opens re-auth on top of that screen; the login row is still there.
    if (isStaleSessionError(error)) {
      return { ok: false, stale: true, serverDeleted: true, localFailure: 'login', loginDeleted: false };
    }
    console.warn('[deleteAccount] delete_my_login', error.message);
    return { ok: false, stale: false, serverDeleted: true, localFailure: 'login', loginDeleted: false };
  }
  const failure = await finishLocalAccountDeletion(deviceId);
  if (failure) {
    return { ok: false, stale: false, serverDeleted: true, localFailure: failure, loginDeleted: true };
  }
  return { ok: true };
}

/**
 * One confirmed delete. Unlink runs only after delete_my_account() commits.
 * A stale result does not throw. `serverDeleted` means that first RPC
 * committed. `loginDeleted` means delete_my_login() committed too.
 */
export async function runAccountDeletion(input: {
  deviceId: string | null;
}): Promise<DeleteOutcome> {
  assertAuthEnabled(AUTH_ENABLED);
  const { error } = await supabase.rpc('delete_my_account');
  if (error) {
    return isStaleSessionError(error)
      ? { ok: false, stale: true, serverDeleted: false }
      : { ok: false, stale: false, serverDeleted: false };
  }
  return continueAccountDeletion(input.deviceId);
}

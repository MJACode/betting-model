/**
 * Account deletion. The SQL function does the server delete. This module
 * orders the steps the screen cannot see:
 *
 *   1. When the session already looks fresh, unlink Discord (must throw —
 *      a failure stops the delete) and SharpSports (best-effort).
 *   2. Call delete_my_account(). A stale session or a rejected JWT comes
 *      back as `stale` and deletes nothing. Any other error is `error`.
 *   3. On success, wipe this install's user data and sign out locally.
 *      The auth user row is already gone, so the sign-out is local only.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import { clearBankrollForAccountDeletion } from '@/hooks/useBankroll';
import { clearCustomModelsForAccountDeletion } from '@/hooks/useCustomModels';
import { clearLineLegsForAccountDeletion } from '@/hooks/useLineLegs';
import { clearManualBetsForAccountDeletion } from '@/hooks/useManualBets';
import { clearParlaySlipForAccountDeletion } from '@/hooks/useParlaySlip';
import { clearSavedParlaysForAccountDeletion } from '@/hooks/useSavedParlays';
import { clearSportsbookConnectionsForAccountDeletion } from '@/hooks/useSportsbookConnection';
import { clearStakeSettingsForAccountDeletion } from '@/hooks/useStakeSettings';
import { clearTrackedBetsForAccountDeletion } from '@/hooks/useTrackedBets';
import { AUTH_ENABLED } from './authConfig';
import { assertAuthEnabled } from './authHelpers';
import {
  ACCOUNT_WIPE_KEYS,
  isStaleSessionError,
  sessionLooksFresh,
} from './deleteAccountHelpers';
import { discordLinkReady } from './discordConfig';
import { unlinkDiscord } from './discord';
import { unlinkSportsbooks } from './sharpsports';
import { supabase } from './supabase';

export type DeleteOutcome =
  | { ok: true }
  | { ok: false; stale: true; serverDeleted: false }
  | { ok: false; stale: false; serverDeleted: boolean };

export async function wipeLocalAccountData(deviceId: string | null): Promise<void> {
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
  ]);
  await AsyncStorage.multiRemove([...ACCOUNT_WIPE_KEYS]);
  if (!deviceId) return;
  // This install's push-notify rows. The policy already allows the delete.
  // The public picks table is not this table.
  const { error } = await supabase.from('tracked_bets').delete().eq('device_id', deviceId);
  if (error) console.warn('[deleteAccount] tracked_bets', error.message);
}

async function unlinkIfFresh(input: {
  lastSignInAt: string | null;
  deviceId: string | null;
  nowMs: number;
}): Promise<void> {
  if (!sessionLooksFresh(input.lastSignInAt, input.nowMs)) return;
  if (input.deviceId) {
    try {
      await unlinkSportsbooks(input.deviceId);
    } catch (e) {
      console.warn('[deleteAccount] sharpsports unlink', e);
    }
  }
  // Always, not only when the access row says linked. That row can still be
  // loading, and a miss here deletes discord_links in the RPC with the role
  // still granted. Unlink with no row is a no-op. A role-removal failure
  // throws, and the RPC does not run.
  if (discordLinkReady()) {
    await unlinkDiscord();
  }
}

/**
 * Wipe this install and sign out locally. The account row is already gone,
 * so a failure here must not be reported as "nothing was deleted".
 * Returns false when either step fails.
 */
export async function finishLocalAccountDeletion(deviceId: string | null): Promise<boolean> {
  try {
    await wipeLocalAccountData(deviceId);
  } catch (e) {
    console.warn('[deleteAccount] local wipe', e);
    return false;
  }
  const signedOut = await supabase.auth.signOut({ scope: 'local' });
  if (signedOut.error) {
    console.warn('[deleteAccount] local sign-out', signedOut.error.message);
    return false;
  }
  return true;
}

/**
 * One confirmed delete. A Discord unlink failure throws, and the caller
 * shows the error banner — the RPC has not run. A stale RPC result does
 * not throw. `serverDeleted` means the RPC committed and only the phone
 * still has to be cleared.
 */
export async function runAccountDeletion(input: {
  lastSignInAt: string | null;
  deviceId: string | null;
  nowMs?: number;
}): Promise<DeleteOutcome> {
  assertAuthEnabled(AUTH_ENABLED);
  const nowMs = input.nowMs ?? Date.now();
  await unlinkIfFresh({ ...input, nowMs });

  const { error } = await supabase.rpc('delete_my_account');
  if (error) {
    return isStaleSessionError(error)
      ? { ok: false, stale: true, serverDeleted: false }
      : { ok: false, stale: false, serverDeleted: false };
  }

  const cleared = await finishLocalAccountDeletion(input.deviceId);
  return cleared
    ? { ok: true }
    : { ok: false, stale: false, serverDeleted: true };
}

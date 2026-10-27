/**
 * Pure delete-account rules. No React, no react-native, no Supabase, so
 * scripts/verify_delete_account.ts can import this file.
 *
 * The server rule lives in data/migrations/delete_my_account_2026_10_24.sql:
 * delete_my_account() and delete_my_login() each raise SQLSTATE 28000 /
 * STALE_SESSION unless the caller's last_sign_in_at is within
 * FRESH_SIGN_IN_MINUTES. A rejected JWT never reaches those functions
 * (PostgREST PGRST301). Both map to the re-auth sheet. The phone clock does
 * not decide anything. Anything else before the data delete is the error
 * banner, and nothing was deleted.
 */

import { errorText } from './errors';

/** Must match interval '10 minutes' in delete_my_account() and delete_my_login(). */
export const FRESH_SIGN_IN_MINUTES = 10;

export const STALE_SESSION_CODE = '28000';
export const STALE_SESSION_TOKEN = 'STALE_SESSION';

/** PostgREST's code when the JWT is expired or rejected. */
export const JWT_REJECTED_CODE = 'PGRST301';

export const DELETE_TITLE = 'Delete your Signalbase account?';

/**
 * Immediate in the app. Server copies and backups follow the 30-day line.
 * The current privacy.html does not say this yet; the sentence is the
 * approved account-deletion copy.
 */
export const DELETE_PERMANENT =
  "This is permanent. You can't undo it. We delete it from this app now. Copies on our servers and in backups are purged within 30 days.";

export const CONFIRM_TITLE = 'Delete your account?';
export const CONFIRM_BODY =
  "Your account, models, tracked picks and bankroll setting will be deleted. You can't undo this.";

export const DELETE_ERROR =
  "Couldn't delete your account. Check your connection and try again. Nothing was deleted.";

/**
 * delete_my_account() committed and the login is still there, because Discord
 * or the sportsbook link did not come off. Not the success toast.
 */
export const UNLINK_INCOMPLETE =
  'Your saved data was deleted, but Discord or your sportsbook connection is still linked. Try again.';

/** delete_my_account() committed. delete_my_login() did not, so the sign-in remains. */
export const LOGIN_INCOMPLETE =
  'Your saved data was deleted, but your sign-in is still active. Try again.';

/** The login is gone. This install's tracked_bets delete did not. */
export const TRACKED_INCOMPLETE =
  "Your account was deleted, but this phone's tracked bets could not be cleared. Try again.";

/** The server delete committed. This phone still holds the user's data. */
export const LOCAL_INCOMPLETE =
  'Your account was deleted, but this phone could not finish clearing it. Try again.';

export const DELETED_TOAST =
  "Your account was deleted. You're signed out. You can keep using Signalbase without an account.";

export const STAYS_LINE =
  'The public model record. It shows how our models did, not anything about you.';

export const REAUTH_TITLE = "Confirm it's you";
export const REAUTH_APPLE_BODY =
  'For your security, sign in again before we delete your account. You signed in a while ago.';

export function reauthEmailBody(email: string): string {
  return `We sent a 6-digit code to ${email}. Enter it to delete your account.`;
}

const JWT_REJECTED =
  /jwt expired|invalid jwt|malformed jwt|invalid claim|PGRST301|session (?:is )?expired/i;

/**
 * True when the server refused because the session is stale or the JWT was
 * rejected. Network failures and every other error are false — those keep
 * the account and show the banner.
 */
export function isStaleSessionError(err: unknown): boolean {
  if (err == null) return false;
  const code =
    typeof err === 'object' && err !== null && 'code' in err
      ? String((err as { code?: unknown }).code ?? '')
      : '';
  if (code === STALE_SESSION_CODE || code === JWT_REJECTED_CODE) return true;
  const msg = errorText(err, '');
  if (msg.includes(STALE_SESSION_TOKEN)) return true;
  return JWT_REJECTED.test(msg) || JWT_REJECTED.test(code);
}

export type ReauthMethod = 'apple' | 'google' | 'email';

/** Apple wins when the account has more than one identity. Email is the rest. */
export function reauthMethod(providers: readonly string[]): ReauthMethod {
  if (providers.includes('apple')) return 'apple';
  if (providers.includes('google')) return 'google';
  return 'email';
}

export function providersForUser(user: {
  app_metadata?: { provider?: string } | null;
  identities?: { provider?: string }[] | null;
} | null): string[] {
  const out: string[] = [];
  const meta = user?.app_metadata?.provider;
  if (typeof meta === 'string' && meta) out.push(meta);
  for (const id of user?.identities ?? []) {
    if (id?.provider && !out.includes(id.provider)) out.push(id.provider);
  }
  return out;
}

export function deletedLines(email: string | null): string[] {
  const signIn = email
    ? `Your account and sign-in (${email})`
    : 'Your account and sign-in';
  return [
    signIn,
    'Your saved and custom models, including Build Your Own Model',
    'Your tracked picks and bets',
    'Your bankroll setting',
  ];
}

export type PurchasePlace = 'app_store' | 'whop' | 'both' | 'none';

/** App Store (or Play) access and a Whop membership are separate purchases. */
export function purchasePlace(input: {
  appAccess: boolean;
  whopAccess: boolean;
}): PurchasePlace {
  if (input.appAccess && input.whopAccess) return 'both';
  if (input.appAccess) return 'app_store';
  if (input.whopAccess) return 'whop';
  return 'none';
}

export interface SubscriptionNotice {
  show: boolean;
  kicker: string;
  body: string;
  /** Opens the store's subscription sheet. Whop is copy only. */
  showManage: boolean;
}

/**
 * Tells the member to cancel where they bought it. Never cancels for them.
 * The dashed box is omitted when they have no subscription.
 */
export function subscriptionNotice(
  place: PurchasePlace,
  platform: string,
): SubscriptionNotice {
  if (place === 'none') {
    return { show: false, kicker: '', body: '', showManage: false };
  }
  const apple = platform !== 'android';
  const storeHow = apple
    ? 'Cancel it first in Manage subscription (iPhone Settings → your name → Subscriptions), or Apple will keep billing you.'
    : 'Cancel it in the Play Store, where you bought it.';
  const whopHow = 'Cancel it on Whop, where you bought it.';
  const lead = apple
    ? "Deleting your account doesn't cancel your Apple subscription."
    : "Deleting your account doesn't cancel your subscription.";
  if (place === 'whop') {
    return {
      show: true,
      kicker: 'WHOP SUBSCRIPTION',
      body: `${lead} ${whopHow}`,
      showManage: false,
    };
  }
  if (place === 'app_store') {
    return {
      show: true,
      kicker: platform === 'android' ? 'GOOGLE PLAY SUBSCRIPTION' : 'APP STORE SUBSCRIPTION',
      body: `${lead} ${storeHow}`,
      showManage: true,
    };
  }
  return {
    show: true,
    kicker: 'YOUR SUBSCRIPTION',
    body: `${lead} ${storeHow} ${whopHow}`,
    showManage: true,
  };
}

/**
 * On-device user data removed after the server delete succeeds.
 * `device.id` is not here: the install keeps its id so the phone can
 * keep being used without an account. This app does not use SecureStore.
 */
export const ACCOUNT_WIPE_KEYS = [
  'customModels.v1',
  'trackedBets.pickIds.v1',
  'trackedBets.live.v1',
  'bankroll.v2',
  'stake.mode.v1',
  'stake.custom.v1',
  'manualBets.v1',
  'savedParlays.v1',
  'parlaySlip.keys.v2',
  'parlaySlip.pickIds.v1',
  'betslip.lineLegs.v1',
  'sportsbook.connections.v2',
  'sportsbook.connection.v1',
  'preferredBooks.selected',
  'preferredBooks.promptDue',
  'preferredBook.selected',
  'push.optIn.v1',
] as const;

/**
 * On-device copies of server query results. Not the user's account. Cleared
 * with the wipe so the next read refetches. `device.id` is not here.
 */
export const QUERY_CACHE_KEYS = [
  'settledPicks.v9',
  'actionThresholds.v1',
  'modelClvPedigree.v2',
] as const;

export const DEVICE_ID_KEY = 'device.id';

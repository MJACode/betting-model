/**
 * Delete-account flow: stale-session mapping, the local wipe, and the
 * copy the screens are required to show.
 *
 *   npx tsx scripts/verify_delete_account.ts
 *
 * Imports only lib/deleteAccountHelpers (and bankroll's key constant).
 * lib/deleteAccount.ts reaches react-native, so it is checked as source.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { BANKROLL_KEY } from '../src/lib/bankroll';
import {
  ACCOUNT_WIPE_KEYS,
  CONFIRM_BODY,
  CONFIRM_TITLE,
  DELETE_ERROR,
  DELETE_PERMANENT,
  LOCAL_INCOMPLETE,
  DELETE_TITLE,
  DELETED_TOAST,
  DEVICE_ID_KEY,
  FRESH_SIGN_IN_MINUTES,
  QUERY_CACHE_KEYS,
  STALE_SESSION_CODE,
  STALE_SESSION_TOKEN,
  STAYS_LINE,
  LOGIN_INCOMPLETE,
  TRACKED_INCOMPLETE,
  UNLINK_INCOMPLETE,
  deletedLines,
  deletionBanner,
  isStaleSessionError,
  providersForUser,
  purchasePlace,
  reauthMethod,
  subscriptionNotice,
} from '../src/lib/deleteAccountHelpers';

const root = join(import.meta.dirname, '..');
const read = (rel: string) => readFileSync(join(root, rel), 'utf8');

let passed = 0;
const failures: string[] = [];

function check(label: string, cond: boolean) {
  if (cond) passed++;
  else failures.push(label);
}

function eq<T>(label: string, actual: T, expected: T) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) passed++;
  else failures.push(`${label} — got ${JSON.stringify(actual)}, want ${JSON.stringify(expected)}`);
}

// --- stale session ----------------------------------------------------------
check('fresh window is 10 minutes', FRESH_SIGN_IN_MINUTES === 10);
const helpers = read('src/lib/deleteAccountHelpers.ts');
check('the phone clock is not a gate', !helpers.includes('sessionLooksFresh'));

check('SQLSTATE 28000 is stale', isStaleSessionError({ code: STALE_SESSION_CODE, message: 'STALE_SESSION' }));
check('the STALE_SESSION token is stale', isStaleSessionError(new Error(STALE_SESSION_TOKEN)));
check('PGRST301 is a rejected JWT', isStaleSessionError({ code: 'PGRST301', message: 'JWT expired' }));
check('JWT expired text is stale', isStaleSessionError({ message: 'JWT expired' }));
check('a network failure is not stale', !isStaleSessionError({ message: 'Failed to fetch', code: '500' }));
check('null is not stale', !isStaleSessionError(null));
check('an unrelated postgres code is not stale', !isStaleSessionError({ code: '23505', message: 'duplicate key' }));

// --- who re-auths, and with what -------------------------------------------
eq('apple wins over email', reauthMethod(['email', 'apple']), 'apple');
eq('google when that is the identity', reauthMethod(['google']), 'google');
eq('anything else is the email code', reauthMethod(['email']), 'email');
eq('no identity is the email code', reauthMethod([]), 'email');
eq(
  'providers come from the user',
  providersForUser({
    app_metadata: { provider: 'email' },
    identities: [{ provider: 'email' }, { provider: 'apple' }],
  }),
  ['email', 'apple'],
);

// --- copy -------------------------------------------------------------------
check('title matches the board', DELETE_TITLE === 'Delete your Signalbase account?');
check('permanent copy names 30 days', DELETE_PERMANENT.includes('purged within 30 days'));
check('permanent copy says it happens now', DELETE_PERMANENT.includes("can't undo it"));
eq('confirm title', CONFIRM_TITLE, 'Delete your account?');
check('confirm names what goes', CONFIRM_BODY.includes('tracked picks') && CONFIRM_BODY.includes("can't undo this"));
check('error says nothing was deleted', DELETE_ERROR.includes('Nothing was deleted'));
check('unlink failure is not plain success', !UNLINK_INCOMPLETE.includes('Nothing was deleted') && UNLINK_INCOMPLETE.includes('still linked'));
check('login failure names the sign-in', LOGIN_INCOMPLETE.includes('sign-in is still active') && !LOGIN_INCOMPLETE.includes('Nothing was deleted'));
check('tracked failure names tracked bets', TRACKED_INCOMPLETE.includes('tracked bets') && !TRACKED_INCOMPLETE.includes('Nothing was deleted'));
check('success toast is signed-out, not a celebration', DELETED_TOAST.includes('signed out') && !/green|congrat/i.test(DELETED_TOAST));
check('what stays is the public record', STAYS_LINE.includes('public model record'));
eq(
  'deleted lines name the account, models, picks, bankroll',
  deletedLines('alex.example@icloud.com'),
  [
    'Your account and sign-in (alex.example@icloud.com)',
    'Your saved and custom models, including Build Your Own Model',
    'Your tracked picks and bets',
    'Your bankroll setting',
  ],
);

eq('success copy is the deleted toast', deletionBanner({ ok: true, serverDeleted: true, loginDeleted: true }), DELETED_TOAST);
eq(
  'success copy is refused when the login delete did not happen',
  deletionBanner({ ok: true, serverDeleted: true, loginDeleted: false }),
  LOGIN_INCOMPLETE,
);
eq(
  'a failed login delete says the sign-in is still active',
  deletionBanner({ ok: false, serverDeleted: true, localFailure: 'login', loginDeleted: false }),
  LOGIN_INCOMPLETE,
);
eq(
  'a failed push opt-out before the login delete is not the wiped-phone copy',
  deletionBanner({ ok: false, serverDeleted: true, localFailure: 'wipe', loginDeleted: false }),
  LOGIN_INCOMPLETE,
);
eq(
  'a failed push opt-out after the login delete is the wiped-phone copy',
  deletionBanner({ ok: false, serverDeleted: true, localFailure: 'wipe', loginDeleted: true }),
  LOCAL_INCOMPLETE,
);
eq('no subscription, no box', purchasePlace({ appAccess: false, whopAccess: false }), 'none');
eq('app store', purchasePlace({ appAccess: true, whopAccess: false }), 'app_store');
eq('whop', purchasePlace({ appAccess: false, whopAccess: true }), 'whop');
eq('both', purchasePlace({ appAccess: true, whopAccess: true }), 'both');

const appStore = subscriptionNotice('app_store', 'ios');
check('app store box tells them to cancel in Settings', appStore.show && appStore.showManage && appStore.body.includes('iPhone Settings'));
check('app store box does not cancel for them', !/we('ll| will) cancel/i.test(appStore.body));
const whop = subscriptionNotice('whop', 'ios');
check('whop box names Whop and has no manage button', whop.show && !whop.showManage && whop.body.includes('Whop'));
const both = subscriptionNotice('both', 'ios');
check('both names the App Store path and Whop', both.showManage && both.body.includes('Whop') && both.body.includes('iPhone Settings'));
check('no subscription hides the box', !subscriptionNotice('none', 'ios').show);
const play = subscriptionNotice('app_store', 'android');
check('play store names Play', play.body.includes('Play Store') && play.showManage);

// --- local wipe -------------------------------------------------------------
check('bankroll key is wiped', (ACCOUNT_WIPE_KEYS as readonly string[]).includes(BANKROLL_KEY));
check('device id is kept', !(ACCOUNT_WIPE_KEYS as readonly string[]).includes(DEVICE_ID_KEY));
for (const key of [
  'customModels.v1',
  'trackedBets.pickIds.v1',
  'trackedBets.live.v1',
  'stake.mode.v1',
  'stake.custom.v1',
  'manualBets.v1',
  'savedParlays.v1',
  'parlaySlip.keys.v2',
  'betslip.lineLegs.v1',
  'sportsbook.connections.v2',
  'preferredBooks.selected',
  'preferredBooks.promptDue',
  'preferredBook.selected',
  'push.optIn.v1',
]) {
  check(`wipe includes ${key}`, (ACCOUNT_WIPE_KEYS as readonly string[]).includes(key));
}
check('push token is not removed before the server agrees', !(ACCOUNT_WIPE_KEYS as readonly string[]).includes('push.token.v1'));
for (const key of ['settledPicks.v9', 'actionThresholds.v1', 'modelClvPedigree.v2']) {
  check(`query cache includes ${key}`, (QUERY_CACHE_KEYS as readonly string[]).includes(key));
}

/** Calls in source order. Comments and string literals are not calls. */
function functionCalls(src: string): string[] {
  const calls: string[] = [];
  const keywords = new Set(['if', 'for', 'while', 'switch', 'catch', 'function', 'typeof', 'await']);
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (c === '/' && src[i + 1] === '/') {
      const nl = src.indexOf('\n', i);
      i = nl < 0 ? src.length : nl + 1;
      continue;
    }
    if (c === '/' && src[i + 1] === '*') {
      const end = src.indexOf('*/', i + 2);
      i = end < 0 ? src.length : end + 2;
      continue;
    }
    if (c === "'" || c === '"' || c === '`') {
      const quote = c;
      i += 1;
      while (i < src.length && src[i] !== quote) {
        i += src[i] === '\\' ? 2 : 1;
      }
      i += 1;
      continue;
    }
    if (/[A-Za-z_]/.test(c)) {
      const start = i;
      i += 1;
      while (i < src.length && /[A-Za-z0-9_]/.test(src[i])) i += 1;
      const name = src.slice(start, i);
      let j = i;
      while (src[j] === ' ' || src[j] === '\n' || src[j] === '\t' || src[j] === '\r') j += 1;
      if (name === 'return') {
        calls.push('return');
        continue;
      }
      if (src[j] !== '(') continue;
      if (keywords.has(name)) continue;
      if (name === 'rpc') {
        const lit = /^\(\s*'([^']+)'/.exec(src.slice(j));
        calls.push(lit ? `rpc:${lit[1]}` : 'rpc');
      } else {
        calls.push(name);
      }
      continue;
    }
    i += 1;
  }
  return calls;
}

function callPositions(calls: string[], names: string[]): number[] {
  const at: number[] = [];
  let from = 0;
  for (const name of names) {
    const found = calls.indexOf(name, from);
    at.push(found);
    if (found >= 0) from = found + 1;
  }
  return at;
}

const flow = read('src/lib/deleteAccount.ts');
const runAt = flow.indexOf('export async function runAccountDeletion');
const continueAt = flow.indexOf('export async function continueAccountDeletion');
const unlinkAt = flow.indexOf('async function unlinkAfterDelete');
const optOutAt = flow.indexOf('function pushOptOutBeforeLoginDelete');
const runBody = flow.slice(runAt);
const continueBody = flow.slice(continueAt, runAt);
const unlinkBody = flow.slice(unlinkAt, flow.indexOf('export async function finishLocalAccountDeletion'));
const continueCalls = functionCalls(continueBody);
const optOutCalls = functionCalls(flow.slice(optOutAt, continueAt));
const decoy = [
  '// clearPushForAccountDeletion()',
  "// supabase.rpc('delete_my_login')",
  'await unlinkAfterDelete(deviceId);',
  "await supabase.rpc('forget_my_notifications');",
  'await clearPushForAccountDeletion();',
  "await supabase.rpc('delete_my_login');",
  'await finishLocalAccountDeletion(deviceId);',
].join('\n');
eq('a comment is not a call', functionCalls(decoy), [
  'unlinkAfterDelete',
  'rpc:forget_my_notifications',
  'clearPushForAccountDeletion',
  'rpc:delete_my_login',
  'finishLocalAccountDeletion',
]);
check('the flow calls delete_my_account', flow.includes("supabase.rpc('delete_my_account')"));
check('the flow calls delete_my_login', flow.includes("supabase.rpc('delete_my_login')"));
check('the flow guards on AUTH_ENABLED', flow.includes('assertAuthEnabled(AUTH_ENABLED)'));
check('the flow maps stale with isStaleSessionError', flow.includes('isStaleSessionError'));
check('the phone clock is not consulted', !flow.includes('sessionLooksFresh') && !flow.includes('lastSignInAt'));
check('the data delete does not unlink', !runBody.includes('unlinkDiscord') && !runBody.includes('unlinkSportsbooks'));
check(
  'unlink runs only after the data delete commits',
  callPositions(functionCalls(runBody), ['rpc:delete_my_account', 'continueAccountDeletion']).every((n, i, all) => n >= 0 && (i === 0 || n > all[i - 1])),
);
check('discord unlink is in the post-delete helper', unlinkBody.includes('unlinkDiscord()'));
check('sharpsports unlink is in the post-delete helper', unlinkBody.includes('unlinkSportsbooks('));
const continueOrder = callPositions(continueCalls, [
  'unlinkAfterDelete',
  'rpc:forget_my_notifications',
  'pushOptOutBeforeLoginDelete',
  'rpc:delete_my_login',
  'finishLocalAccountDeletion',
]);
check(
  'continue calls unlink, forget, opt-out, login delete, then the local wipe',
  continueOrder.every((n, i, all) => n >= 0 && (i === 0 || n > all[i - 1])),
);
check(
  'the opt-out helper is the push clear, and it does not delete the login',
  optOutCalls.includes('clearPushForAccountDeletion') && !optOutCalls.includes('rpc:delete_my_login'),
);
const optOutCall = continueCalls.indexOf('pushOptOutBeforeLoginDelete');
const loginCall = continueCalls.indexOf('rpc:delete_my_login', optOutCall + 1);
check(
  'a failed push opt-out does not return before the login delete',
  optOutCall >= 0
    && loginCall > optOutCall
    && !continueCalls.slice(optOutCall + 1, loginCall).includes('return'),
);
check(
  'the opt-out gives up on a hung write',
  optOutCalls.includes('setTimeout') && flow.includes('PUSH_OPT_OUT_MS = 5000'),
);
check('an unlink failure is not success', continueBody.includes("localFailure: 'unlink'"));
check('a login-delete failure names the login', continueBody.includes("localFailure: 'login'"));
check(
  'a stale login delete stays a server delete',
  /isStaleSessionError\(error\)[\s\S]{0,220}serverDeleted: true/.test(continueBody),
);
check('a local failure is not a clean success', runBody.includes('serverDeleted: false') && flow.includes('serverDeleted: true'));
check('local failure copy does not say nothing was deleted', !LOCAL_INCOMPLETE.includes('Nothing was deleted'));
check('the flow signs out locally', flow.includes("signOut({ scope: 'local' })"));
check('the flow clears custom models', flow.includes('clearCustomModelsForAccountDeletion'));
check('the flow clears tracked bets', flow.includes('clearTrackedBetsForAccountDeletion'));
check('the flow clears the bankroll', flow.includes('clearBankrollForAccountDeletion'));
check('the flow clears stake settings', flow.includes('clearStakeSettingsForAccountDeletion'));
check('the flow clears preferred books', flow.includes('clearPreferredBooksForAccountDeletion'));
check('the flow resets the device book row after sign-out', flow.includes('resetPreferredBooksDeviceRow'));
check('the flow clears the push token', flow.includes('clearPushForAccountDeletion'));
check('the flow clears the query cache', flow.includes('clearQueryCache'));
check('the query cache drops settled picks', flow.includes('clearSettledCache'));
check('the query cache drops thresholds', flow.includes('setServerThresholds(null)'));
check('the query cache drops model CLV', flow.includes('setModelClv(null)'));
check('a tracked-bet failure is returned', flow.includes("failure = 'tracked'"));
check('tracked_bets delete is this device only', /from\('tracked_bets'\)[\s\S]{0,120}\.eq\('device_id'/.test(flow));
check('the flow does not delete the picks table', !flow.includes("from('picks')"));

const screen = read('src/screens/DeleteAccountScreen.tsx');
check('confirm is Alert.alert', screen.includes('Alert.alert(CONFIRM_TITLE, CONFIRM_BODY'));
check('confirm Delete is destructive', /text: 'Delete',\s*style: 'destructive'/.test(screen));
check('no type-DELETE field', !screen.includes('Type DELETE'));
check('success check is textInverse', screen.includes('color={colors.textInverse}'));
check('success check is not bet green', !/name="checkmark"[\s\S]{0,80}colors\.bet\b/.test(screen));
check('large text is not switched off', !screen.includes('allowFontScaling={false}'));
check('the title is not truncated', !/style=\{styles\.title\}[^>]*numberOfLines/.test(screen));
check('try again retries the delete', screen.includes("phase === 'error'"));
check('the screen does not read the phone clock', !screen.includes('last_sign_in_at'));
check('the local screen asks the banner for the copy', screen.includes('deletionBanner({ ok: false, serverDeleted: true, localFailure, loginDeleted })'));
check('the success screen asks the banner with the login deleted', screen.includes('deletionBanner({ ok: true, serverDeleted: true, loginDeleted: true })'));
const apply = screen.slice(screen.indexOf('const applyOutcome'), screen.indexOf('const run ='));
check(
  'a stale login delete does not return to the start screen',
  apply.indexOf('outcome.serverDeleted') !== -1
    && apply.indexOf('outcome.serverDeleted') < apply.indexOf("setPhase('ready')"),
);
check('re-auth on the local screen retries the rest', screen.includes("phase === 'local') await retryLocal()"));

const settings = read('src/screens/SettingsScreen.tsx');
check('settings has a Delete account row', settings.includes('accessibilityLabel="Delete account"'));
check('delete row navigates to the screen', settings.includes("navigation.navigate('DeleteAccount')"));
check('sign out uses the navy tint', /signOutText: \{[^}]*color: colors\.tint/.test(settings));
check('sign out is not the red fill', !/signOutBtn: \{[^}]*backgroundColor: colors\.avoid/.test(settings));
check('email row reads Signed in as', settings.includes('Signed in as'));
check('delete row is at least 52pt', /deleteRow: \{[^}]*minHeight: 52/.test(settings));

const app = read('App.tsx');
check('DeleteAccount is registered', app.includes('name="DeleteAccount"'));
check('the betslip bar hides on DeleteAccount', app.includes("'DeleteAccount'"));

if (failures.length) {
  console.error(`verify_delete_account: ${failures.length} failed\n` + failures.map((f) => `  - ${f}`).join('\n'));
  process.exit(1);
}
console.log(`verify_delete_account: ${passed} passed`);

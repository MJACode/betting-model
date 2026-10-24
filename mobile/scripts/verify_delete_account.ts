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
  STALE_SESSION_CODE,
  STALE_SESSION_TOKEN,
  STAYS_LINE,
  deletedLines,
  isStaleSessionError,
  providersForUser,
  purchasePlace,
  reauthMethod,
  sessionLooksFresh,
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

const MIN = FRESH_SIGN_IN_MINUTES * 60 * 1000;
const now = Date.parse('2026-10-24T15:00:00Z');

// --- stale session ----------------------------------------------------------
check('fresh window is 10 minutes', FRESH_SIGN_IN_MINUTES === 10);
check('a sign-in just now looks fresh', sessionLooksFresh(new Date(now - 60_000).toISOString(), now));
check('a sign-in 11 minutes ago does not', !sessionLooksFresh(new Date(now - 11 * MIN / 10).toISOString(), now));
check('a missing timestamp does not look fresh', !sessionLooksFresh(null, now));
check('a future timestamp does not look fresh', !sessionLooksFresh(new Date(now + MIN).toISOString(), now));

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
]) {
  check(`wipe includes ${key}`, (ACCOUNT_WIPE_KEYS as readonly string[]).includes(key));
}

const flow = read('src/lib/deleteAccount.ts');
const runBody = flow.slice(flow.indexOf('export async function runAccountDeletion'));
check('the flow calls delete_my_account', flow.includes("supabase.rpc('delete_my_account')"));
check('the flow guards on AUTH_ENABLED', flow.includes('assertAuthEnabled(AUTH_ENABLED)'));
check('the flow maps stale with isStaleSessionError', flow.includes('isStaleSessionError'));
check(
  'the flow wipes local data only after success',
  runBody.indexOf('finishLocalAccountDeletion') > runBody.indexOf("rpc('delete_my_account')"),
);
check('a local failure is not a clean success', runBody.includes('serverDeleted: true'));
check('local failure copy does not say nothing was deleted', !LOCAL_INCOMPLETE.includes('Nothing was deleted'));
check('the flow signs out locally', flow.includes("signOut({ scope: 'local' })"));
check('the flow clears custom models', flow.includes('clearCustomModelsForAccountDeletion'));
check('the flow clears tracked bets', flow.includes('clearTrackedBetsForAccountDeletion'));
check('the flow clears the bankroll', flow.includes('clearBankrollForAccountDeletion'));
check('the flow clears stake settings', flow.includes('clearStakeSettingsForAccountDeletion'));
check('the flow unlinks discord before a fresh delete', flow.includes('unlinkDiscord()'));
check('the flow unlinks sharpsports', flow.includes('unlinkSportsbooks'));
check('tracked_bets delete is this device only', /from\('tracked_bets'\)[\s\S]{0,80}\.eq\('device_id'/.test(flow));
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

/**
 * Verifies the pure Discord-linking helpers, plus source-level checks that
 * Apple-only app access is what the unapplied migration and the webhooks do.
 *
 *   npx tsx scripts/verify_discord_link.ts
 *
 * Imports only discordHelpers + discordConfig: lib/discord.ts reaches
 * react-native transitively (Supabase → AsyncStorage), which esbuild can't
 * transform. Same split as authHelpers / billingHelpers.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  DiscordLinkDisabledError,
  NO_ACCESS,
  accessSourceCopy,
  assertDiscordLinkEnabled,
  describeDiscordLink,
  discordErrorMessage,
  discordInviteIfPaid,
  parseAccess,
  parseDiscordCallback,
  type AccessRow,
} from '../src/lib/discordHelpers';
import {
  DISCORD_LINK_ENABLED,
  DISCORD_REDIRECT_URL,
  discordLinkReady,
} from '../src/lib/discordConfig';
import { subscriptionGrantsDiscordRole } from '../../supabase/functions/_shared/discordRole';

let passed = 0;
const failures: string[] = [];

const check = (label: string, cond: boolean) => {
  if (cond) passed++;
  else failures.push(label);
};
const eq = <T>(label: string, actual: T, expected: T) => {
  if (JSON.stringify(actual) === JSON.stringify(expected)) passed++;
  else
    failures.push(
      `${label} — got ${JSON.stringify(actual)}, want ${JSON.stringify(expected)}`,
    );
};

const access = (over: Partial<AccessRow> = {}): AccessRow => ({
  ...NO_ACCESS,
  ...over,
});

// --- flags ------------------------------------------------------------------
// Linking ships dark, like auth and billing before it. Tripwire if that ever
// changes without a decision.
check('DISCORD_LINK_ENABLED defaults to false', DISCORD_LINK_ENABLED === false);
check('discordLinkReady() is false while the flag is off', discordLinkReady() === false);
// Must match app.json's scheme, the Discord application's registered redirect,
// and DISCORD_REDIRECT_URI in the edge function secrets. All four.
eq('redirect URL', DISCORD_REDIRECT_URL, 'signalbase://discord-callback');

check(
  'assertDiscordLinkEnabled throws while off',
  (() => {
    try {
      assertDiscordLinkEnabled(false);
      return false;
    } catch (e) {
      return e instanceof DiscordLinkDisabledError;
    }
  })(),
);
check('assertDiscordLinkEnabled passes when on', (() => {
  assertDiscordLinkEnabled(true);
  return true;
})());

// --- parseAccess ------------------------------------------------------------
// PostgREST returns a set-returning function as an array; a zero-row result is
// an empty array, not null. Both shapes, and the garbage cases, must resolve.
eq('array payload is unwrapped', parseAccess([{ entitled: true, source: 'app' }]).entitled, true);
eq('object payload is accepted', parseAccess({ entitled: true, source: 'app' }).entitled, true);
eq('empty array → no access', parseAccess([]), NO_ACCESS);
eq('null → no access', parseAccess(null), NO_ACCESS);
eq('garbage → no access', parseAccess('nope'), NO_ACCESS);
// Falsy-but-present must not read as true, and a non-boolean must not either.
eq('non-boolean entitled is not truthy', parseAccess([{ entitled: 'yes' }]).entitled, false);
eq('unknown source degrades to none', parseAccess([{ source: 'whop' }]).source, 'none');
eq(
  'blank username becomes null',
  parseAccess([{ discord_username: '   ' }]).discord_username,
  null,
);
eq(
  'a full row round-trips',
  parseAccess([
    {
      entitled: true,
      source: 'discord',
      app_access: false,
      discord_access: true,
      discord_linked: true,
      discord_username: 'matt',
      guild_member: true,
      app_role_granted: false,
    },
  ]),
  {
    entitled: true,
    source: 'discord',
    app_access: false,
    discord_access: true,
    discord_linked: true,
    discord_username: 'matt',
    guild_member: true,
    app_role_granted: false,
  },
);

// --- OAuth callback parsing -------------------------------------------------
eq(
  'code and state are read from the query',
  parseDiscordCallback('signalbase://discord-callback?code=abc&state=xyz'),
  { code: 'abc', state: 'xyz', error: null },
);
// A user tapping Cancel on Discord's consent screen is a normal outcome, and
// must surface as a cancel rather than an error dialog.
eq(
  'access_denied reads as a cancel',
  parseDiscordCallback('signalbase://discord-callback?error=access_denied').error,
  'cancelled',
);
eq(
  'a real error is surfaced',
  parseDiscordCallback(
    'signalbase://discord-callback?error=invalid_scope&error_description=Bad%20scope',
  ).error,
  'Bad scope',
);
eq(
  'no params → nothing, but no error either',
  parseDiscordCallback('signalbase://discord-callback'),
  { code: null, state: null, error: null },
);

// --- copy -------------------------------------------------------------------
// Whop ties the person. It must not be described as paying for the app.
check(
  'a Whop-only link does not say the app is included',
  !describeDiscordLink(
    access({
      discord_linked: true,
      discord_access: true,
      app_access: false,
      entitled: false,
      discord_username: 'matt',
    }),
  )
    .toLowerCase()
    .includes('includes the app'),
);
check(
  'an unmatched Discord membership does not say it covers the app',
  !describeDiscordLink(access({ discord_access: true }))
    .toLowerCase()
    .includes('covers the app'),
);
check(
  'an app subscriber is told the Discord is included',
  describeDiscordLink(
    access({ discord_linked: true, app_role_granted: true, discord_username: 'matt' }),
  ).includes('includes the Discord'),
);
check(
  'an unlinked user is invited to connect',
  describeDiscordLink(NO_ACCESS).includes('Connect your Discord'),
);
check(
  'a linked-but-unpaid user is told what unlocks the channels',
  describeDiscordLink(
    access({ discord_linked: true, guild_member: true, discord_username: 'matt' }),
  ).includes('Subscribe'),
);
eq(
  'no source, no copy',
  accessSourceCopy(NO_ACCESS),
  '',
);
eq(
  'a Whop-only source does not tell the paywall the app is included',
  accessSourceCopy(access({ source: 'discord', discord_access: true, entitled: false })),
  '',
);
check(
  'an Apple subscription still says Discord is included',
  accessSourceCopy(access({ source: 'app', entitled: true, app_access: true })).includes(
    'includes access to the subscriber Discord',
  ),
);

// --- error copy -------------------------------------------------------------
check(
  'a taken Discord account gets a sentence, not a constraint violation',
  discordErrorMessage(
    new Error('That Discord account is already connected to a different Signalbase account.'),
  ).includes('already connected to another'),
);
check(
  'an expired state asks them to try again',
  discordErrorMessage(new Error('That link request expired. Try again.')).includes(
    'Tap Connect Discord again',
  ),
);
check(
  'a network failure reads as a network failure',
  discordErrorMessage(new Error('fetch failed')).includes('No connection'),
);
check(
  'an unknown error passes through rather than being swallowed',
  discordErrorMessage(new Error('kaboom')) === 'kaboom',
);

// --- invite is paid-only ----------------------------------------------------
eq('unpaid invite is withheld', discordInviteIfPaid(false, 'https://discord.gg/example'), null);
eq('blank invite is withheld', discordInviteIfPaid(true, '  '), null);
eq('paid invite is returned', discordInviteIfPaid(true, ' https://discord.gg/example '), 'https://discord.gg/example');
eq('unpaid default invite is withheld', discordInviteIfPaid(false), null);
eq('paid default invite is the apple link', discordInviteIfPaid(true), 'https://discord.gg/JWMUzK9Da');
function walkSrc(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (name === 'node_modules') continue;
    try {
      if (readdirSync(p)) walkSrc(p, out);
    } catch {
      if (name.endsWith('.ts') || name.endsWith('.tsx')) out.push(p);
    }
  }
  return out;
}
const inviteLeaks = walkSrc(join(__dirname, '..', 'src')).filter((p) => {
  if (p.endsWith('discordHelpers.ts')) return false;
  const text = readFileSync(p, 'utf8');
  return text.includes('discord.gg') || text.includes('DISCORD_URL');
});
check('invite url is only in discordHelpers', inviteLeaks.length === 0);
const publicJoin = walkSrc(join(__dirname, '..', 'src')).filter((p) =>
  readFileSync(p, 'utf8').includes('Join our Discord'),
);
check('no public Join our Discord row', publicJoin.length === 0);

const NOW = Date.parse('2026-09-01T00:00:00Z');
check(
  'a trial does not get the paid discord role',
  subscriptionGrantsDiscordRole(
    { status: 'trialing', current_period_end: '2026-09-08T00:00:00Z' },
    NOW,
  ) === false,
);
check(
  'an active paid row gets the discord role',
  subscriptionGrantsDiscordRole(
    { status: 'active', current_period_end: '2026-10-01T00:00:00Z' },
    NOW,
  ) === true,
);
check(
  'an ended active row does not keep the discord role',
  subscriptionGrantsDiscordRole(
    { status: 'active', current_period_end: '2026-08-01T00:00:00Z' },
    NOW,
  ) === false,
);
check('no subscription row does not get the discord role', subscriptionGrantsDiscordRole(null, NOW) === false);
check(
  'a just-paid active row with no period end still gets the role',
  subscriptionGrantsDiscordRole({ status: 'active', current_period_end: null }, NOW) === true,
);

const modalSrc = readFileSync(join(__dirname, '..', 'src', 'components', 'DiscordLinkModal.tsx'), 'utf8');
check(
  'connect discord during a trial does not open the invite',
  modalSrc.includes("subscription.status === 'active'") &&
    modalSrc.includes('discordInviteIfPaid(applePaid)') &&
    modalSrc.includes('onPress={onConnect}') &&
    modalSrc.includes('const linked = await link()'),
);

// --- source-level guards ----------------------------------------------------
const libSrc = readFileSync(join(__dirname, '..', 'src', 'lib', 'discord.ts'), 'utf8');
for (const fn of ['linkDiscord', 'unlinkDiscord']) {
  const body = libSrc.split(`export async function ${fn}`)[1] ?? '';
  check(
    `${fn}() guards on discordLinkReady()`,
    body.split('\n').slice(0, 6).join('\n').includes('assertDiscordLinkEnabled(discordLinkReady())'),
  );
}
// The app must never be able to claim a membership it did not buy: everything
// that grants access happens server-side.
check(
  'the app never writes discord_links or whop_memberships',
  !/from\(['"](discord_links|whop_memberships)['"]\)/.test(libSrc),
);
check(
  'access is read through the RPC, not by selecting the tables',
  libSrc.includes("supabase.rpc('my_access')"),
);

const fnRoot = join(__dirname, '..', '..', 'supabase', 'functions');
const linkFn = readFileSync(join(fnRoot, 'discord-link', 'index.ts'), 'utf8');
const whopFn = readFileSync(join(fnRoot, 'whop-webhook', 'index.ts'), 'utf8');
const shared = readFileSync(join(fnRoot, '_shared', 'entitlement.ts'), 'utf8');
const discordShared = readFileSync(join(fnRoot, '_shared', 'discord.ts'), 'utf8');

check(
  'discord-link binds the OAuth round trip to the caller with a signed state',
  linkFn.includes('verifyState(state, userId)') && linkFn.includes('timingSafeEqual'),
);
check(
  'discord-link asks for guilds.join so the join is one tap',
  linkFn.includes('identify email guilds.join'),
);
check(
  'discord-link refuses to relink a Discord account already on another user',
  linkFn.includes('existing.user_id !== userId'),
);
// An unverified Discord email is attacker-chosen. Trusting it would let anyone
// claim a paid Whop membership by setting their address to the buyer's.
check(
  'only a Discord-verified email is stored as verified',
  linkFn.includes('Boolean(profile.verified && profile.email)'),
);
check(
  'unlinking takes back our role before dropping the row',
  linkFn.indexOf('removeAppRole') < linkFn.indexOf('.delete()'),
);

check(
  'whop-webhook verifies an HMAC signature over the RAW body',
  whopFn.includes('signatureValid(raw, header)') && whopFn.includes('await req.text()'),
);
check(
  "whop-webhook trusts Whop's own valid flag rather than re-deriving it",
  whopFn.includes('if (typeof m.valid === "boolean") return m.valid;'),
);
// Whop owns its Discord role and does not unlock the app. Our role is the
// Apple subscription only.
check(
  'whop-webhook never touches Discord roles or the subscription row',
  !whopFn.includes('addAppRole') &&
    !whopFn.includes('removeAppRole') &&
    !whopFn.includes('syncAppRoleForUser') &&
    !/from\(['"]subscriptions['"]\)/.test(whopFn),
);

// It grants OUR role, which represents an app-side purchase. Reading the Whop
// table here would make a lapsed app subscription able to strip a member who
// is still paying through Discord — the exact destructive behaviour the
// two-role split exists to prevent.
check(
  'the role sync reads only the app subscription',
  shared.includes('.from("subscriptions")') &&
    !shared.includes('.from("whop_memberships")'),
);
check(
  'the role sync grants only an active subscription',
  shared.includes('subscriptionGrantsDiscordRole(sub)') &&
    !shared.includes('shouldHold = subscriptionEntitles'),
);
check(
  'the role sync never throws into a webhook response',
  shared.includes('catch (e)') && shared.includes('last_sync_error'),
);
check(
  'the role sync skips when it is already in the desired state',
  shared.includes('if (shouldHold === holds)'),
);
check(
  'only OUR role id is ever written',
  discordShared.includes('APP_ROLE_ID') &&
    !/ROLE_ID_(WHOP|OTHER)/.test(discordShared),
);

const mig = readFileSync(
  join(__dirname, '..', '..', 'data', 'migrations', 'add_discord_link_and_whop_memberships.sql'),
  'utf8',
);
const hasApp = mig.slice(
  mig.indexOf('FUNCTION public.has_app_access()'),
  mig.indexOf('$$;', mig.indexOf('FUNCTION public.has_app_access()')),
);
const myFor = mig.slice(
  mig.indexOf('FUNCTION public.my_access_for'),
  mig.indexOf('$$;', mig.indexOf('FUNCTION public.my_access_for')),
);
check(
  'has_app_access is the Apple subscription and does not OR Whop',
  hasApp.includes('app_subscription_access_for') && !hasApp.includes('discord_access_for'),
);
check(
  'my_access_for entitled column is the Apple flag, not an OR',
  myFor.includes('SELECT a,') && !myFor.includes('(a OR d)') && !myFor.includes('a OR d'),
);

const entHook = readFileSync(
  join(__dirname, '..', 'src', 'hooks', 'useEntitlement.ts'),
  'utf8',
);
const entFn = entHook.split('export function useEntitlement')[1] ?? '';
check(
  'useEntitlement does not OR discord_access into entitled',
  !entFn.includes('discord_access') && !entHook.includes('ORs both'),
);
check(
  'useEntitlement still folds in a just-completed Apple purchase',
  entHook.includes('accessEntitled || (billingReady() && subEntitled)'),
);

if (failures.length === 0) {
  console.log(`ALL PASS (${passed} assertions)`);
} else {
  console.error(`${failures.length} FAILED, ${passed} passed:`);
  failures.forEach((f) => console.error('  ✗ ' + f));
  process.exit(1);
}

/**
 * Verifies the pure Discord-linking helpers, plus source-level checks that the
 * two-way membership rule is actually wired the way it is documented.
 *
 *   npx tsx scripts/verify_discord_link.ts
 *
 * Imports only discordHelpers + discordConfig: lib/discord.ts reaches
 * react-native transitively (Supabase → AsyncStorage), which esbuild can't
 * transform. Same split as authHelpers / billingHelpers.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  DiscordLinkDisabledError,
  NO_ACCESS,
  accessSourceCopy,
  assertDiscordLinkEnabled,
  describeDiscordLink,
  discordErrorMessage,
  parseAccess,
  parseDiscordCallback,
  type AccessRow,
} from '../src/lib/discordHelpers';
import {
  DISCORD_LINK_ENABLED,
  DISCORD_REDIRECT_URL,
  discordLinkReady,
} from '../src/lib/discordConfig';

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
// The case that matters most: a Discord-paid member must be TOLD that is why
// they were not charged, or they will assume something is broken and buy again.
check(
  'a Discord-paid member is told the app is included',
  describeDiscordLink(
    access({ discord_linked: true, discord_access: true, discord_username: 'matt' }),
  ).includes('includes the app'),
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
check(
  'the discord source explains why nothing is being charged',
  accessSourceCopy(access({ source: 'discord' })).includes('no second subscription'),
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
// Whop owns its own role. If we revoked it, a member who cancelled in the app
// but still pays through Discord would lose access they are paying for.
check(
  'whop-webhook never touches Discord roles',
  !whopFn.includes('addAppRole') && !whopFn.includes('removeAppRole'),
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

if (failures.length === 0) {
  console.log(`ALL PASS (${passed} assertions)`);
} else {
  console.error(`${failures.length} FAILED, ${passed} passed:`);
  failures.forEach((f) => console.error('  ✗ ' + f));
  process.exit(1);
}

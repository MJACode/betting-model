/**
 * Discord perk: Join-screen eligibility, the four triggers, once-only,
 * and which onboarding slide is shown.
 *
 *   node --experimental-strip-types scripts/verify_discord_join.ts
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
const read = (rel: string) => readFileSync(join(ROOT, rel), 'utf8');

let failures = 0;
function check(name: string, ok: boolean, detail = ''): void {
  if (ok) console.log(`[PASS] ${name}`);
  else {
    failures += 1;
    console.log(`[FAIL] ${name} ${detail}`);
  }
}
function eq(name: string, actual: unknown, expected: unknown): void {
  check(name, actual === expected, `got ${JSON.stringify(actual)}`);
}

const perk = await import(pathToFileURL(join(ROOT, 'src/lib/discordJoin.ts')).href);
const home = await import(pathToFileURL(join(ROOT, 'src/lib/settingsHome.ts')).href);

const {
  EMPTY_DISCORD_JOIN_RECORD,
  discordJoinBlocksRecap,
  discordJoinCopy,
  discordJoinOffer,
  discordOnboardingSlide,
  markDiscordJoinChosen,
  mergeDiscordJoinStores,
  noteSubscription,
  observeDiscordTier,
  parseDiscordJoinStore,
  paywallDiscordBullet,
  serializeDiscordJoinStore,
  userDiscordJoinRecord,
  withUserDiscordJoinRecord,
} = perk;

type Gate = {
  discordPaid: boolean;
  seen: boolean;
  sawTrial: boolean;
  comped: boolean;
  onboardingFinished: boolean;
  surfaceClear: boolean;
  hasAccount: boolean;
  subscriptionReady: boolean;
};

function gate(over: Partial<Gate> = {}): Gate {
  return {
    discordPaid: true,
    seen: false,
    sawTrial: false,
    comped: false,
    onboardingFinished: true,
    surfaceClear: true,
    hasAccount: true,
    subscriptionReady: true,
    ...over,
  };
}

// --- copy -------------------------------------------------------------------

eq(
  'annual and monthly paywall line',
  paywallDiscordBullet(7),
  'The subscriber Discord: the community, plus extra bets shared beyond the models (after the trial)',
);
eq(
  'weekly paywall line',
  paywallDiscordBullet(0),
  'The subscriber Discord: the community, plus extra bets shared beyond the models, included with this plan',
);
eq('any trial length uses the after-trial line', paywallDiscordBullet(1), paywallDiscordBullet(7));

const freeSlide = discordOnboardingSlide(false);
const paidSlide = discordOnboardingSlide(true);
eq('slide title', freeSlide.title, 'The subscriber Discord');
eq('paid slide keeps the title', paidSlide.title, freeSlide.title);
eq(
  'free or trial slide',
  freeSlide.body,
  'Paid plans include a private community, plus extra bets shared beyond the models. It unlocks when a paid plan is active, after any free trial.',
);
eq(
  'paid or comped slide',
  paidSlide.body,
  'Your plan includes a private community, plus extra bets shared beyond the models. You’ll be able to join after this intro — or anytime in Settings.',
);
eq(
  'replay after join drops the after-intro clause',
  perk.discordOnboardingSlide(true, true).body,
  'Your plan includes a private community, plus extra bets shared beyond the models. You’ll be able to join anytime in Settings.',
);
check(
  'replay does not promise the join screen is next',
  !perk.discordOnboardingSlide(true, true).body.includes('after this intro'),
);
eq(
  'a free replay does not use the paid sentence',
  perk.discordOnboardingSlide(false, true).body,
  freeSlide.body,
);
check('neither slide offers a join button', !/join discord/i.test(freeSlide.body) && !/join discord/i.test(paidSlide.body));
check('neither slide prints an invite', !freeSlide.body.includes('discord.gg') && !paidSlide.body.includes('discord.gg'));

const first = discordJoinCopy('firstPaid');
const converted = discordJoinCopy('converted');
eq('first paid headline', first.headline, 'Join the subscriber Discord');
eq(
  'first paid body',
  first.body,
  'Your plan includes a private community, plus extra bets shared beyond the models.',
);
eq('converted headline', converted.headline, 'Your paid plan includes Discord');
eq(
  'converted body',
  converted.body,
  'The trial has ended, and the subscriber Discord is now included — the community, plus extra bets shared beyond the models.',
);
eq(
  'shared bullets',
  first.bullets.join(' | '),
  'Talk with other subscribers | Extra bets shared beyond the model board | Room to talk through the models and the day',
);
check('converted uses the same bullets and actions', converted.bullets.join('|') === first.bullets.join('|') && converted.primary === 'Join Discord' && converted.secondary === 'Maybe later' && converted.note === first.note);
eq(
  'settings note',
  first.note,
  'You can always join later from Settings → Community.',
);
check('join copy does not print an invite', !JSON.stringify(first).includes('discord.gg') && !JSON.stringify(converted).includes('discord.gg'));

// --- eligibility and triggers ----------------------------------------------

function shown(over: Partial<Gate>) {
  return discordJoinOffer(gate(over));
}

{
  const weekly = shown({});
  eq('weekly checkout shows the first-paid screen', weekly.show && weekly.variant === 'firstPaid', true);
}
{
  const trial = observeDiscordTier(EMPTY_DISCORD_JOIN_RECORD, 'trial');
  eq('a running trial is remembered', trial.sawTrial, true);
  eq('a running trial does not see the screen', shown({ discordPaid: false, sawTrial: true }).show, false);
  const after = observeDiscordTier(trial, 'paid');
  eq('conversion keeps the trial memory', after.sawTrial, true);
  const offer = shown({ sawTrial: after.sawTrial });
  eq('a converted trial sees 02b', offer.show && offer.variant === 'converted', true);
}
{
  // Unlock Discord early is the same transition: the account was trial, then paid.
  const trial = observeDiscordTier(EMPTY_DISCORD_JOIN_RECORD, 'trial');
  const offer = shown({ sawTrial: observeDiscordTier(trial, 'paid').sawTrial });
  eq('unlock discord early sees 02b', offer.show && offer.variant === 'converted', true);
}
{
  const offer = shown({ comped: true, sawTrial: false });
  eq('a comped first session sees 02', offer.show && offer.variant === 'firstPaid', true);
}
{
  const offer = shown({ comped: true, sawTrial: true });
  eq('comped after a trial still sees 02', offer.show && offer.variant === 'firstPaid', true);
}
eq('free does not see it', shown({ discordPaid: false }).show, false);
eq('billing off does not see it', shown({ discordPaid: false }).show, false);
eq('whop-only is not paid and does not see it', shown({ discordPaid: false }).show, false);
eq('onboarding still up hides it', shown({ onboardingFinished: false }).show, false);
eq('paywall still up hides it', shown({ surfaceClear: false }).show, false);
eq('no account hides it', shown({ hasAccount: false }).show, false);
eq('already seen hides it', shown({ seen: true, sawTrial: true }).show, false);

// A long-time paid member was never observed on a trial, so the copy is 02.
eq(
  'already-paid first session is 02',
  shown({ sawTrial: false }).variant,
  'firstPaid',
);

// --- once only, per account -------------------------------------------------

{
  let record = EMPTY_DISCORD_JOIN_RECORD;
  record = observeDiscordTier(record, 'paid');
  for (const choice of ['join', 'later'] as const) {
    const seen = markDiscordJoinChosen(record, choice);
    eq(`${choice} marks the screen seen`, seen.seen, true);
    eq(`${choice} does not show again`, shown({ seen: seen.seen, sawTrial: seen.sawTrial }).show, false);
    eq(`${choice} twice stays seen`, markDiscordJoinChosen(seen, choice).seen, true);
  }
}

{
  let store = { users: {} as Record<string, { seen: boolean; sawTrial: boolean }> };
  const trial = observeDiscordTier(EMPTY_DISCORD_JOIN_RECORD, 'trial');
  store = withUserDiscordJoinRecord(store, 'annual', markDiscordJoinChosen(trial, 'later'));
  store = withUserDiscordJoinRecord(store, 'weekly', EMPTY_DISCORD_JOIN_RECORD);
  const annual = userDiscordJoinRecord(store, 'annual');
  const weekly = userDiscordJoinRecord(store, 'weekly');
  eq('account A stays seen', shown({ seen: annual.seen, sawTrial: annual.sawTrial }).show, false);
  const b = shown({ seen: weekly.seen, sawTrial: weekly.sawTrial });
  eq('account B still sees 02', b.show && b.variant === 'firstPaid', true);
  eq('account B did not inherit the trial', weekly.sawTrial, false);
}

{
  const stored = withUserDiscordJoinRecord({ users: {} }, 'a', { seen: true, sawTrial: false });
  const memory = withUserDiscordJoinRecord({ users: {} }, 'a', { seen: false, sawTrial: true });
  const merged = mergeDiscordJoinStores(stored, memory);
  const row = userDiscordJoinRecord(merged, 'a');
  eq('a read does not drop an in-memory trial', row.sawTrial, true);
  eq('a read does not clear a stored seen flag', row.seen, true);
  const again = parseDiscordJoinStore(serializeDiscordJoinStore(merged));
  eq('the store round-trips', userDiscordJoinRecord(again, 'a').seen && userDiscordJoinRecord(again, 'a').sawTrial, true);
}

eq('garbage is unseen', userDiscordJoinRecord(parseDiscordJoinStore('not json'), 'a').seen, false);
eq('a truthy string is not seen', userDiscordJoinRecord(parseDiscordJoinStore('{"users":{"a":{"seen":"1","sawTrial":1}}}'), 'a').seen, false);
eq('a truthy string is not a trial', userDiscordJoinRecord(parseDiscordJoinStore('{"users":{"a":{"seen":"1","sawTrial":1}}}'), 'a').sawTrial, false);
eq('null storage is empty', Object.keys(parseDiscordJoinStore(null).users).length, 0);

eq('storage not ready holds the recap', discordJoinBlocksRecap({ storageReady: false, membershipHold: false, show: false }), true);
eq('membership still loading holds the recap', discordJoinBlocksRecap({ storageReady: true, membershipHold: true, show: false }), true);
eq('the join screen holds the recap', discordJoinBlocksRecap({ storageReady: true, membershipHold: false, show: true }), true);
eq('a decided non-show releases the recap', discordJoinBlocksRecap({ storageReady: true, membershipHold: false, show: false }), false);

eq('a loaded trialing row is a trial', perk.confirmedTrial({ subLoading: false, status: 'trialing', periodEntitled: true }), true);
eq('a row still loading is not a trial', perk.confirmedTrial({ subLoading: true, status: 'trialing', periodEntitled: true }), false);
eq('entitled with no row is not a trial', perk.confirmedTrial({ subLoading: false, status: null, periodEntitled: true }), false);
eq('an active row is not a trial', perk.confirmedTrial({ subLoading: false, status: 'active', periodEntitled: true }), false);
eq('an expired trial row is not a trial', perk.confirmedTrial({ subLoading: false, status: 'trialing', periodEntitled: false }), false);
{
  // Cold start. my_access is entitled and the subscription row has not
  // loaded. membershipTier reports 'trial' for that shape. This path does not.
  let record = noteSubscription(EMPTY_DISCORD_JOIN_RECORD, {
    subLoading: true,
    status: null,
    periodEntitled: false,
  });
  eq('a loading row does not remember a trial', record.sawTrial, false);
  eq(
    'the screen waits while the row is loading',
    shown({ discordPaid: true, sawTrial: false, subscriptionReady: false }).show,
    false,
  );
  record = noteSubscription(record, { subLoading: false, status: null, periodEntitled: true });
  eq('entitled with no row still is not a trial', record.sawTrial, false);
  record = noteSubscription(record, { subLoading: false, status: 'active', periodEntitled: true });
  eq('the landed active row does not invent a trial', record.sawTrial, false);
  const offer = shown({ discordPaid: true, sawTrial: record.sawTrial, subscriptionReady: true });
  eq('a long-time payer sees 02', offer.show && offer.variant === 'firstPaid', true);
}
{
  let record = noteSubscription(EMPTY_DISCORD_JOIN_RECORD, {
    subLoading: false,
    status: 'trialing',
    periodEntitled: true,
  });
  eq('a loaded trialing row is remembered', record.sawTrial, true);
  eq(
    'a later read in flight does not pick 02b yet',
    shown({ discordPaid: true, sawTrial: true, subscriptionReady: false }).show,
    false,
  );
  record = noteSubscription(record, { subLoading: false, status: 'active', periodEntitled: true });
  const offer = shown({ sawTrial: record.sawTrial, subscriptionReady: true });
  eq('the same account sees 02b after the row is active', offer.show && offer.variant === 'converted', true);
}
eq('a failed read stays hidden', perk.discordJoinVisible({ ready: true, loadFailed: true, offerShow: true }), false);
eq('a good read can show', perk.discordJoinVisible({ ready: true, loadFailed: false, offerShow: true }), true);
{
  const store = withUserDiscordJoinRecord(
    withUserDiscordJoinRecord({ users: {} }, 'keep', { seen: true, sawTrial: false }),
    'gone',
    { seen: true, sawTrial: true },
  );
  const left = perk.withoutUserDiscordJoinRecord(store, 'gone');
  eq('deletion drops only that account', userDiscordJoinRecord(left, 'gone').seen, false);
  eq('deletion keeps the other account', userDiscordJoinRecord(left, 'keep').seen, true);
}

const helpers = read('src/lib/discordHelpers.ts');
check('unpaid invite is still withheld', helpers.includes('if (!paid) return null;'));
check('paid invite is still the apple link', helpers.includes('https://discord.gg/JWMUzK9Da'));
check('the join module does not carry the url', !read('src/lib/discordJoin.ts').includes('discord.gg'));

// --- settings tile ----------------------------------------------------------

eq('discord leads the community tile', home.communityTileSummary(true, 0), 'Discord · X · Feedback');
eq('flags-off tile stays X and feedback', home.communityTileSummary(false, 0), 'X · Feedback');
eq('paid tile chip', home.communityIncludedChip(true, true), true);
eq('trial tile has no chip', home.communityIncludedChip(true, false), false);
eq('flags-off has no chip even if paid was passed', home.communityIncludedChip(false, true), false);
eq('an unread reply hides the Included chip', home.communityIncludedChip(true, true, 1), false);

// --- wiring -----------------------------------------------------------------

const paywall = read('src/screens/PaywallScreen.tsx');
check('paywall uses the shared bullet', paywall.includes('paywallDiscordBullet(plan.trialDays)'));
check('paywall still says 8 sports', paywall.includes('Every BET signal, all 8 sports') && !paywall.includes('all 7 sports'));
check(
  'old paywall discord lines are gone',
  !paywall.includes('The subscriber Discord (paid plans, after the trial)') &&
    !paywall.includes('The subscriber Discord, included with this plan'),
);

const onboarding = read('src/components/OnboardingModal.tsx');
const story = onboarding.split('const STORY_SLIDES')[1]?.split('];')[0] ?? '';
const titles = [...story.matchAll(/title: '([^']+)'/g)].map((m) => m[1]);
eq('four story slides before discord', titles.length, 4);
eq('discord follows bet to stay in the game', titles[3], 'Bet to stay in the game');
check('slide body comes from the paid flag and the join flag', onboarding.includes('discordOnboardingSlide(discordPaid, joinSeen)'));
check('books step is still after the slides', onboarding.includes("const BOOKS_TITLE = 'Where do you bet?'"));
check('pagination is slides plus the books step', /const total = SLIDES\.length \+ 1;/.test(onboarding));
check('onboarding has no join button', !onboarding.includes('Join Discord') && !onboarding.includes('discord.gg'));

const modal = read('src/components/DiscordJoinModal.tsx');
check('join opens the paid invite only', modal.includes('discordInviteIfPaid(discordPaid)'));
check('join does not hard-code the url', !modal.includes('discord.gg') && !modal.includes('https://'));
check(
  'a failed join does not print the invite',
  modal.includes("openLink(invite, 'Discord', { revealUrl: false })"),
);
check('large text can scroll the join screen', modal.includes('<ScrollView') && modal.includes('flexGrow: 1'));
check('both buttons choose', modal.includes("onChoose('join')") && modal.includes("onChoose('later')"));
check('back is maybe later', modal.includes("onRequestClose={() => onChoose('later')}"));

const hook = read('src/hooks/useDiscordJoin.ts');
check(
  'the flag is stored',
  read('src/lib/discordJoinStore.ts').includes('DISCORD_JOIN_STORAGE_KEY') &&
    read('src/lib/discordJoinStore.ts').includes('AsyncStorage'),
);
check('both choices go through the same mark', hook.includes('markDiscordJoinChosen'));

const app = read('App.tsx');
check(
  'join is mounted after onboarding',
  app.indexOf('<OnboardingModal') !== -1 && app.indexOf('<OnboardingModal') < app.indexOf('<DiscordJoinModal'),
);
check('join waits for the intro to finish', app.includes('onboardingFinished'));
check('the recap waits for the join screen', app.includes('!join.blocking'));

const settings = read('src/screens/SettingsScreen.tsx');
const community = settings.split('function CommunitySection(')[1]?.split('function AccountSection(')[0] ?? '';
const discordAt = community.indexOf('DISCORD_CARD_TITLE');
const xAt = community.indexOf('Follow us on X');
const feedbackAt = community.indexOf('Send feedback');
check('discord leads the community drill-in', discordAt !== -1 && discordAt < xAt && xAt < feedbackAt);
check('paid card uses the approved line', settings.includes('DISCORD_CARD_BODY'));
check('old paid card line is gone', !settings.includes('Talk picks with other subscribers.'));
check(
  'trial card still withholds the invite',
  settings.includes('Unlocks when your paid plan starts, after the free trial. No invite is shown until then.'),
);
check('unlock discord early is unchanged', settings.includes('Unlock Discord early') && settings.includes('endTrialEarly'));
check('the home tile chip follows the paid flag', settings.includes('communityIncludedChip('));
check(
  'a failed settings join does not print the invite',
  settings.includes("openLink(invite, 'Discord', { revealUrl: false })"),
);
check(
  'hiding the address is opt-in',
  read('src/lib/socialLinks.ts').includes('opts?.revealUrl === false'),
);

const storeSrc = read('src/lib/discordJoinStore.ts');
{
  const wipeFn =
    read('src/lib/deleteAccount.ts').split('export async function wipeLocalAccountData')[1]?.split(
      'export async function',
    )[0] ?? '';
  const logged = wipeFn.indexOf("console.warn('[deleteAccount] discord join flag'");
  const rest = wipeFn.indexOf('clearBankrollForAccountDeletion');
  check(
    'a discord-flag failure does not skip the other wipes',
    wipeFn.includes('forgetDiscordJoinForCurrentUser') && logged !== -1 && rest > logged,
  );
}
check(
  'account deletion drops one user, not the whole map',
  !read('src/lib/deleteAccountHelpers.ts').includes('DISCORD_JOIN_STORAGE_KEY') &&
    read('src/lib/deleteAccount.ts').includes('forgetDiscordJoinUser') &&
    storeSrc.includes('withoutUserDiscordJoinRecord') &&
    storeSrc.includes('notifyDiscordJoinUserForgotten') &&
    perk.DISCORD_JOIN_STORAGE_KEY === 'discord.join.v1',
);
check(
  'reads and writes share one queue',
  storeSrc.includes('let tail: Promise<void>') &&
    hook.includes('readDiscordJoinRaw') &&
    hook.includes('writeDiscordJoinStore'),
);
check('line height follows the text size', read('src/components/DiscordJoinModal.tsx').includes('Math.round(24 * scale)'));
const membership = read('src/hooks/useMembership.ts');
check('a trial is confirmed from the loaded row', membership.includes('confirmedTrial({'));
check('the join hook does not watch the fallback tier', hook.includes('trialConfirmed') && !hook.includes('input.tier'));
check('the screen waits for the subscription read', hook.includes('subscriptionReady'));
check('a failed read does not show or save', hook.includes('setLoadFailed(true)') && hook.includes('if (!ready || loadFailed) return'));

if (failures === 0) console.log('ALL PASS');
else {
  console.log(`${failures} FAILED`);
  process.exit(1);
}

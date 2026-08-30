/**
 * Verifies the pure billing helpers — entitlement, price math, and status copy
 * — plus a source-level check that the network calls stay behind the flag.
 *
 *   npx tsx scripts/verify_billing.ts
 *
 * Imports only billingHelpers + billingConfig: lib/billing.ts reaches
 * react-native transitively (Supabase → AsyncStorage), which esbuild can't
 * transform. Same split as authHelpers.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  describeSubscription,
  formatPerMonth,
  formatPrice,
  isEntitled,
  isPlanKey,
  monthlyPlan,
  perMonth,
  renewalDisclosure,
  savingsPct,
  trialDaysLeft,
  type SubscriptionRow,
} from '../src/lib/billingHelpers';
import {
  BILLING_ENABLED,
  BILLING_RAIL,
  PLANS,
  TRIAL_DAYS,
  billingReady,
  planFor,
} from '../src/lib/billingConfig';
import {
  REVENUECAT_ENTITLEMENT_ID,
  customerInfoEntitled,
  displayPrice,
  fallbackManagementUrl,
  packageForPlan,
  planForPackageType,
  planForProductId,
  type MinimalPackage,
} from '../src/lib/iapHelpers';

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

const sub = (over: Partial<SubscriptionRow> = {}): SubscriptionRow => ({
  status: 'active',
  plan: 'annual',
  current_period_end: '2027-01-01T00:00:00Z',
  trial_end: null,
  cancel_at_period_end: false,
  ...over,
});
const NOW = new Date('2026-09-01T12:00:00Z');

// --- flags ------------------------------------------------------------------
// Billing ships dark. Tripwire if that ever changes without a decision.
check('BILLING_ENABLED defaults to false', BILLING_ENABLED === false);
check('billingReady() is false while the flag is off', billingReady() === false);
eq('trial length is 7 days', TRIAL_DAYS, 7);
// The rail decision of 2026-08-22: IAP by default (Stripe restricts the
// category; the app stores don't). Flipping this back to 'stripe' should be a
// deliberate act, not a drive-by.
eq("default rail is 'iap'", BILLING_RAIL, 'iap');

// --- the price ladder -------------------------------------------------------
// Weekly / Monthly / Annual (2026-08-30). These must match App Store Connect
// exactly or the paywall's fallback quotes a number the user isn't charged.
eq('weekly price', planFor('weekly').price, 9.99);
eq('monthly price', planFor('monthly').price, 29.99);
eq('annual price', planFor('annual').price, 199.99);
eq('three plans offered', PLANS.length, 3);
check('every plan key is recognised', PLANS.every((p) => isPlanKey(p.key)));
check('unknown plan key rejected', !isPlanKey('semiannual'));

// A 7-day trial on a 7-day term is a free week that renews into another free
// week for anyone willing to cancel and resubscribe.
eq('weekly carries no free trial', planFor('weekly').trialDays, 0);
eq('monthly carries the 7-day trial', planFor('monthly').trialDays, 7);
eq('annual carries the 7-day trial', planFor('annual').trialDays, 7);

// --- per-month + savings math ----------------------------------------------
const monthly = monthlyPlan();
check('monthly per-month is the price itself', perMonth(monthly) === 29.99);
// 52 weeks / 12 months, not 4 weeks: a four-week "month" understates the
// weekly plan's real cost by 8%, in the direction that flatters us.
check(
  'weekly works out near $43.29/mo',
  Math.abs(perMonth(planFor('weekly')) - 43.29) < 0.01,
);
check(
  'annual works out near $16.67/mo',
  Math.abs(perMonth(planFor('annual')) - 16.666) < 0.01,
);
eq('annual saves 44%', savingsPct(planFor('annual'), monthly), 44);
eq('monthly saves nothing vs itself', savingsPct(monthly, monthly), 0);
// Negative on purpose — weekly costs MORE per month than monthly, and the
// paywall hides the badge rather than inventing a saving.
check('weekly shows no saving', savingsPct(planFor('weekly'), monthly) < 0);
eq('price formatting', formatPrice(199.99), '$199.99');
eq('per-month formatting', formatPerMonth(planFor('annual')), '$16.67/mo');

// --- renewal disclosure -----------------------------------------------------
// A plan with no trial must never claim one: untrue, and a 3.1.2 rejection.
check(
  'monthly disclosure states the trial',
  renewalDisclosure(planFor('monthly')).startsWith('7-day free trial'),
);
check(
  'weekly disclosure claims no trial',
  !renewalDisclosure(planFor('weekly')).toLowerCase().includes('trial'),
);
check(
  'weekly disclosure names the weekly term',
  renewalDisclosure(planFor('weekly')).includes('$9.99 per week'),
);
check(
  'every disclosure says how to cancel',
  PLANS.every((p) => renewalDisclosure(p).includes('Cancel anytime')),
);

// --- entitlement ------------------------------------------------------------
check('active entitles', isEntitled(sub(), NOW));
check('trialing entitles', isEntitled(sub({ status: 'trialing' }), NOW));
check('past_due does not entitle', !isEntitled(sub({ status: 'past_due' }), NOW));
check('canceled does not entitle', !isEntitled(sub({ status: 'canceled' }), NOW));
check('unpaid does not entitle', !isEntitled(sub({ status: 'unpaid' }), NOW));
check('incomplete does not entitle', !isEntitled(sub({ status: 'incomplete' }), NOW));
check('null subscription does not entitle', !isEntitled(null, NOW));
// The case a status-only check would get wrong: still 'active' in our table,
// but the period lapsed because a webhook was missed.
check(
  'active but expired period does NOT entitle',
  !isEntitled(sub({ current_period_end: '2026-08-01T00:00:00Z' }), NOW),
);
// And the opposite failure: locking out a user we just wrote a row for.
check(
  'active with no period end still entitles',
  isEntitled(sub({ current_period_end: null }), NOW),
);
check(
  'cancel_at_period_end still entitles until the period ends',
  isEntitled(sub({ cancel_at_period_end: true }), NOW),
);

// --- trial countdown --------------------------------------------------------
eq(
  'seven-day trial reads as 7 days left',
  trialDaysLeft(
    sub({ status: 'trialing', trial_end: '2026-09-08T12:00:00Z' }),
    NOW,
  ),
  7,
);
eq(
  'part of a day rounds up',
  trialDaysLeft(
    sub({ status: 'trialing', trial_end: '2026-09-01T18:00:00Z' }),
    NOW,
  ),
  1,
);
eq(
  'elapsed trial reads as 0',
  trialDaysLeft(
    sub({ status: 'trialing', trial_end: '2026-08-20T12:00:00Z' }),
    NOW,
  ),
  0,
);
eq('an active (non-trial) sub has no trial days', trialDaysLeft(sub(), NOW), 0);

// --- status copy ------------------------------------------------------------
check(
  'no subscription says so plainly',
  describeSubscription(null, NOW) === 'No active subscription.',
);
check(
  'past_due tells the user to fix their card',
  describeSubscription(sub({ status: 'past_due' }), NOW).includes('update your card'),
);
check(
  'trial copy shows days remaining',
  describeSubscription(
    sub({ status: 'trialing', trial_end: '2026-09-04T12:00:00Z' }),
    NOW,
  ).includes('3 days left'),
);
check(
  'a pending cancellation says "ends", never "renews"',
  (() => {
    const s = describeSubscription(sub({ cancel_at_period_end: true }), NOW);
    return s.includes('ends') && !s.includes('renews');
  })(),
);
check(
  'an active sub says when it renews',
  describeSubscription(sub(), NOW).includes('renews'),
);
check(
  'plan name is used in the copy',
  describeSubscription(sub({ plan: 'annual' }), NOW).includes('Annual'),
);
// A row carrying a plan key we no longer sell (a replayed six-month product
// from the pre-2026-08-30 ladder) degrades to the generic word rather than
// rendering an empty name.
check(
  'a retired plan key falls back to "Subscription"',
  describeSubscription(sub({ plan: 'semiannual' }), NOW).includes('Subscription'),
);

// --- IAP helpers ------------------------------------------------------------
eq('RC entitlement id', REVENUECAT_ENTITLEMENT_ID, 'signals');
eq('WEEKLY package → weekly', planForPackageType('WEEKLY'), 'weekly');
eq('MONTHLY package → monthly', planForPackageType('MONTHLY'), 'monthly');
eq('ANNUAL package → annual', planForPackageType('ANNUAL'), 'annual');
eq('unknown package type → null', planForPackageType('SIX_MONTH'), null);
// The ordering trap: a longer marker that contains a shorter one has to win.
eq(
  'a 52-week yearly id is annual, not weekly',
  planForProductId('com.mja.bettingpicks.sub.52_week_year'),
  'annual',
);
eq('weekly product id', planForProductId('sb_weekly_999'), 'weekly');
eq('annual product id', planForProductId('sb_annual_19999'), 'annual');
eq('monthly product id', planForProductId('sb_monthly_2999'), 'monthly');
eq('unrecognisable product id → null', planForProductId('sb_lifetime'), null);

const pkgs: MinimalPackage[] = [
  { packageType: 'ANNUAL', product: { identifier: 'sb_annual', priceString: '$199.99' } },
  { packageType: 'CUSTOM', product: { identifier: 'sb_weekly', priceString: '$9.99' } },
  { packageType: 'MONTHLY', product: { identifier: 'sb_monthly', priceString: '$29.99' } },
];
eq(
  'packageForPlan matches by package type',
  packageForPlan(pkgs, 'annual')?.product.identifier,
  'sb_annual',
);
eq(
  'packageForPlan falls back to product-id heuristic for CUSTOM packages',
  packageForPlan(pkgs, 'weekly')?.product.identifier,
  'sb_weekly',
);
eq('packageForPlan misses honestly', packageForPlan([], 'annual'), null);

eq(
  'localized store price wins',
  displayPrice(planFor('annual'), '$199.99'),
  '$199.99',
);
eq(
  'config price is the fallback',
  displayPrice(planFor('annual'), null),
  '$199.99',
);
eq('blank localized price falls back', displayPrice(planFor('monthly'), ' '), '$29.99');

check(
  'active entitlement recognised',
  customerInfoEntitled({ entitlements: { active: { signals: {} } } }),
);
check(
  'other entitlements do not count',
  !customerInfoEntitled({ entitlements: { active: { something_else: {} } } }),
);
check('null customer info → not entitled', !customerInfoEntitled(null));
check(
  'management fallback URLs are per-platform',
  fallbackManagementUrl('ios').includes('apple.com') &&
    fallbackManagementUrl('android').includes('play.google.com'),
);

// --- source-level flag guard ------------------------------------------------
// Both network entry points must refuse to run while billing is off, so an
// accidental call can't create a real Stripe customer before launch.
const src = readFileSync(join(__dirname, '..', 'src', 'lib', 'billing.ts'), 'utf8');
for (const fn of [
  'startCheckout',
  'openManageSubscription',
  'restorePurchases',
  'redeemCode',
]) {
  const body = src.split(`export async function ${fn}`)[1] ?? '';
  check(
    `${fn}() guards on billingReady()`,
    body.split('\n').slice(0, 8).join('\n').includes('assertBillingReady()'),
  );
}
check(
  'startCheckout dispatches on the rail',
  (src.split('export async function startCheckout')[1] ?? '').includes(
    "BILLING_RAIL === 'iap'",
  ),
);
check(
  'fetchSubscription() short-circuits when billing is off',
  (src.split('export async function fetchSubscription')[1] ?? '').includes(
    'if (!billingReady()) return null',
  ),
);
// Checkout must never let the client pick the price — that's the difference
// between a paywall and a suggestion box.
const fn = readFileSync(
  join(__dirname, '..', '..', 'supabase', 'functions', 'stripe-checkout', 'index.ts'),
  'utf8',
);
check('checkout maps plan → price server-side', fn.includes('const priceId = PRICES[plan]'));
check(
  'checkout takes the user from the JWT, not the body',
  fn.includes('admin.auth.getUser(token)'),
);
const hook = readFileSync(
  join(__dirname, '..', '..', 'supabase', 'functions', 'stripe-webhook', 'index.ts'),
  'utf8',
);
check('webhook verifies the Stripe signature', hook.includes('verifySignature(rawBody'));
check('webhook signs over the raw body', hook.includes('await req.text()'));
check('webhook enforces a timestamp tolerance', hook.includes('TOLERANCE_SEC'));

// The IAP file must never import the native module statically — an OTA bundle
// doing so crashes on launch on binaries that predate the rebuild. Only a
// dynamic require inside loadPurchases() (and type-only imports) are allowed.
const iapSrc = readFileSync(join(__dirname, '..', 'src', 'lib', 'iap.ts'), 'utf8');
check(
  'iap.ts has no static value import of react-native-purchases',
  !/^import\s+(?!type\b)[^;]*from\s+'react-native-purchases'/m.test(iapSrc),
);
check(
  'iap.ts loads the SDK via dynamic require',
  iapSrc.includes("require('react-native-purchases')"),
);
const rcHook = readFileSync(
  join(__dirname, '..', '..', 'supabase', 'functions', 'revenuecat-webhook', 'index.ts'),
  'utf8',
);
check(
  'revenuecat webhook checks the Authorization header constant-time',
  rcHook.includes('timingSafeEqual(header, AUTH_VALUE)'),
);
check(
  'revenuecat webhook validates the user id as a UUID',
  rcHook.includes('UUID_RE.test'),
);
check(
  'revenuecat webhook keeps the longer-marker-first heuristic order',
  rcHook.indexOf('week|wk') < rcHook.indexOf('if (/month/') &&
    rcHook.indexOf('annual|year') < rcHook.indexOf('week|wk'),
);
// The Discord half of the membership rule: paying in the app has to grant the
// role, and letting the subscription lapse has to take it back.
check(
  'revenuecat webhook syncs the Discord role after the upsert',
  rcHook.includes('syncAppRoleForUser(admin, userId)') &&
    rcHook.indexOf('upsert failed') < rcHook.indexOf('syncAppRoleForUser(admin, userId)'),
);

if (failures.length === 0) {
  console.log(`ALL PASS (${passed} assertions)`);
} else {
  console.error(`${failures.length} FAILED, ${passed} passed:`);
  failures.forEach((f) => console.error('  ✗ ' + f));
  process.exit(1);
}

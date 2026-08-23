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
// These must match the Stripe Prices exactly or the paywall quotes a number the
// user isn't charged.
eq('monthly price', planFor('monthly').price, 29.99);
eq('semiannual price', planFor('semiannual').price, 129.99);
eq('annual price', planFor('annual').price, 199.99);
eq('three plans offered', PLANS.length, 3);
check('every plan key is recognised', PLANS.every((p) => isPlanKey(p.key)));
check('unknown plan key rejected', !isPlanKey('weekly'));

// --- per-month + savings math ----------------------------------------------
const monthly = monthlyPlan();
check('monthly per-month is the price itself', perMonth(monthly) === 29.99);
check(
  'semiannual works out near $21.67/mo',
  Math.abs(perMonth(planFor('semiannual')) - 21.665) < 0.01,
);
check(
  'annual works out near $16.67/mo',
  Math.abs(perMonth(planFor('annual')) - 16.666) < 0.01,
);
eq('semiannual saves 28%', savingsPct(planFor('semiannual'), monthly), 28);
eq('annual saves 44%', savingsPct(planFor('annual'), monthly), 44);
eq('monthly saves nothing vs itself', savingsPct(monthly, monthly), 0);
eq('price formatting', formatPrice(199.99), '$199.99');
eq('per-month formatting', formatPerMonth(planFor('annual')), '$16.67/mo');

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
  describeSubscription(sub({ plan: 'semiannual' }), NOW).includes('Season Pass'),
);

// --- IAP helpers ------------------------------------------------------------
eq('RC entitlement id', REVENUECAT_ENTITLEMENT_ID, 'signals');
eq('MONTHLY package → monthly', planForPackageType('MONTHLY'), 'monthly');
eq('SIX_MONTH package → semiannual', planForPackageType('SIX_MONTH'), 'semiannual');
eq('ANNUAL package → annual', planForPackageType('ANNUAL'), 'annual');
eq('unknown package type → null', planForPackageType('WEEKLY'), null);
// The ordering trap: 'six_month' contains 'month' and must NOT read as monthly.
eq(
  'six_month product id is semiannual, not monthly',
  planForProductId('com.mja.bettingpicks.sub.six_month'),
  'semiannual',
);
eq('annual product id', planForProductId('sb_annual_19999'), 'annual');
eq('monthly product id', planForProductId('sb_monthly_2999'), 'monthly');
eq('unrecognisable product id → null', planForProductId('sb_weekly'), null);

const pkgs: MinimalPackage[] = [
  { packageType: 'ANNUAL', product: { identifier: 'sb_annual', priceString: '$199.99' } },
  { packageType: 'CUSTOM', product: { identifier: 'sb_six_month', priceString: '$129.99' } },
  { packageType: 'MONTHLY', product: { identifier: 'sb_monthly', priceString: '$29.99' } },
];
eq(
  'packageForPlan matches by package type',
  packageForPlan(pkgs, 'annual')?.product.identifier,
  'sb_annual',
);
eq(
  'packageForPlan falls back to product-id heuristic for CUSTOM packages',
  packageForPlan(pkgs, 'semiannual')?.product.identifier,
  'sb_six_month',
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
for (const fn of ['startCheckout', 'openManageSubscription', 'restorePurchases']) {
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
  'revenuecat webhook keeps the six-month-before-month heuristic order',
  rcHook.indexOf('six|semi') < rcHook.indexOf('if (/month/'),
);

if (failures.length === 0) {
  console.log(`ALL PASS (${passed} assertions)`);
} else {
  console.error(`${failures.length} FAILED, ${passed} passed:`);
  failures.forEach((f) => console.error('  ✗ ' + f));
  process.exit(1);
}

# Billing — built and switched off. Rail: IAP (RevenueCat), Stripe as fallback

Signalbase has a complete subscription layer that is **inactive**.
`BILLING_ENABLED` in `src/lib/billingConfig.ts` is the kill switch (`false`),
and billing also requires `AUTH_ENABLED` — `billingReady()` enforces the pair,
because a subscription belongs to an account, not a device UUID that dies on
reinstall.

## The ladder

| Plan | Price | Effective/mo | Saving |
|---|---|---|---|
| Monthly | $29.99 | $29.99 | — |
| Season Pass (6 mo) | $129.99 | $21.67 | 28% |
| Annual | $199.99 | $16.67 | 44% |

7-day free trial on all three. `billingConfig.ts` holds the **display** prices;
the store (App Store Connect / Stripe) holds what's actually charged. Change
one, change both — `verify_billing.ts` pins the display numbers.

## The rail decision (2026-08-22)

`BILLING_RAIL` defaults to **`'iap'`** — Apple/Google in-app purchases via
RevenueCat. Why, decided after checking the policies rather than assuming:

- **Every mainstream card processor restricts this category.** Stripe's
  restricted list names "sports forecasting or odds making" (default: decline
  or account closure); Lemon Squeezy prohibits gambling outright; Paddle's AUP
  is equivalent. Handicapping subscriptions are also treated as high-chargeback,
  which is the underwriting objection behind the policy.
- **The app stores have no such objection** — the picks-app category is full of
  precedents. 15% fee under the Small Business Program (both stores, under
  $1M/yr), no underwriting, no rolling reserve, no PCI scope, no sales tax to
  register, and nobody can freeze the account mid-season.
- The Stripe path (0% Apple commission in the US today under the Epic
  injunction; Apple filed 2026-08-13 to charge 5–15%) stays **built and dark**.
  It becomes interesting only if Stripe grants written approval for the
  category AND the fee gap is worth carrying platform risk. Flip with
  `EXPO_PUBLIC_BILLING_RAIL=stripe`.

RevenueCat sits in front of StoreKit/Play Billing because it validates
receipts, normalizes the two stores, survives the renewal edge cases, and
delivers one webhook that writes our `subscriptions` table. Free below
$2.5k/mo tracked revenue.

## ⚠️ IAP is a NATIVE module — the one hard constraint

`react-native-purchases` is native code. Unlike everything else in the auth +
billing stack, **activating the IAP rail requires an EAS rebuild** — it cannot
ship over OTA. Two rules protect existing installs:

1. `src/lib/iap.ts` loads the SDK **only via a guarded dynamic `require`**
   inside functions gated on `billingReady()`. Never add a static
   `import Purchases from 'react-native-purchases'` anywhere — an OTA bundle
   containing one crashes on launch on every binary built before the module was
   added. (`verify_billing.ts` has a source-level tripwire for this.)
2. **Bump `version` in `app.json`** (e.g. 1.0.0 → 1.1.0) with the rebuild.
   `runtimeVersion` follows `appVersion`, so the bump keeps new OTA bundles
   away from old binaries.

## How entitlement flows (IAP rail)

```
app → Purchases.configure(apiKey, appUserID = supabase user id)
    → native purchase sheet, store charges the user
    → RevenueCat validates the receipt
    → revenuecat-webhook (Authorization header, constant-time) → subscriptions upsert
    → app re-reads subscriptions (RLS: own row only) → entitled
```

The RevenueCat app user id **is** the Supabase user id — set at configure time,
which is why purchasing requires sign-in and why the webhook needs no alias
bookkeeping. The app never writes `subscriptions` on either rail. Right after a
purchase the paywall also trusts the receipt-validated `CustomerInfo`
(`entitledNow`) so the user isn't staring at a lock while the webhook is in
flight; the table remains the durable truth.

`isEntitled()` checks status **and** period end — an `active` row whose period
lapsed (missed webhook) does not entitle.

---

## Activation — IAP rail

### 1. App Store Connect (and later, Play Console)

Create three auto-renewable subscriptions in one subscription group:

| Reference | Product ID (suggested) | Price | Duration |
|---|---|---|---|
| Monthly | `com.mja.bettingpicks.sub.monthly` | $29.99 | 1 month |
| Season Pass | `com.mja.bettingpicks.sub.six_month` | $129.99 | 6 months |
| Annual | `com.mja.bettingpicks.sub.annual` | $199.99 | 1 year |

Add a **7-day free trial** as an introductory offer on each. Prices must match
`billingConfig.ts` (the paywall's fallback display) exactly.

### 2. RevenueCat dashboard

1. Create a project; add the iOS app (bundle id `com.mja.bettingpicks`) with
   the App Store Connect API key.
2. Create an **entitlement** named exactly **`signals`**
   (`REVENUECAT_ENTITLEMENT_ID` in `iapHelpers.ts`).
3. Attach all three products to it.
4. Create an **offering** (default) with packages **Monthly / Six Month /
   Annual** — the standard package types are what `planForPackageType` maps.
5. Copy the **public** SDK key(s) into the build env:
   `EXPO_PUBLIC_REVENUECAT_IOS_KEY` (and `_ANDROID_KEY` when Play ships).

### 3. Webhook

RevenueCat → Integrations → Webhooks:

```
URL:            https://vvprgnrmzeekokzkrkfu.supabase.co/functions/v1/revenuecat-webhook
Authorization:  <a long random string>
```

```bash
supabase secrets set REVENUECAT_WEBHOOK_AUTH=<same string>
# optional exact product→plan pins (the substring heuristic is the fallback):
supabase secrets set RC_PRODUCT_MONTHLY=com.mja.bettingpicks.sub.monthly \
  RC_PRODUCT_SEMIANNUAL=com.mja.bettingpicks.sub.six_month \
  RC_PRODUCT_ANNUAL=com.mja.bettingpicks.sub.annual

supabase functions deploy revenuecat-webhook --no-verify-jwt
```

`--no-verify-jwt` is required — RevenueCat sends no Supabase JWT; authenticity
is the Authorization header check.

### 4. Rebuild

```bash
# bump "version" in app.json first (OTA runtime separation — see above)
cd mobile && eas build --profile production --platform ios
```

The dep is already in `package.json`; Expo autolinks it, no config plugin.

### 5. Sandbox test (before any flag flips)

With a preview/TestFlight build, `EXPO_PUBLIC_AUTH_ENABLED=true` +
`EXPO_PUBLIC_BILLING_ENABLED=true`, and an App Store **sandbox tester**
account: sign in → paywall shows store-localized prices → purchase (sandbox
sheet, no real charge) → paywall closes (receipt-validated `entitledNow`) →
within seconds the webhook writes the row:

```sql
SELECT user_id, status, plan, store, trial_end, current_period_end FROM subscriptions;
```

Then: **Restore purchases** after delete/reinstall recovers access; Settings →
Subscription opens the OS management screen; cancelling there flips
`cancel_at_period_end` on the next webhook and access survives to period end.
Sandbox renewals are accelerated (a "month" is minutes) — watch a RENEWAL and
an EXPIRATION arrive.

### 6. Ship

Flip `AUTH_ENABLED` + `BILLING_ENABLED` (rail already defaults to `iap`) and
release the **native build** through TestFlight/App Store — not OTA.

App Review notes: the restore button exists (required), the paywall discloses
auto-renewal and where to cancel, and sign-in-before-purchase is justified
under 5.1.1 because the subscription is account-bound (works across devices).
Expect Review to test exactly that flow.

---

## Stripe rail (fallback, dark)

Everything from the original Stripe build remains: `stripe-checkout`,
`stripe-webhook`, `stripe-portal` Edge Functions, and the runbook steps below.
Use only if Stripe grants **written approval** for the business category —
apply describing it accurately first; an account freeze with live subscriptions
is the worst available outcome. High-risk processors (PaymentCloud, PayKings,
Host Merchant Services) are the web-checkout alternative if Stripe declines.

<details>
<summary>Stripe activation steps (kept for the fallback)</summary>

1. Stripe: one Product, three recurring Prices matching the ladder; enable the
   Billing Portal with cancellation allowed.
2. Secrets: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_MONTHLY`,
   `STRIPE_PRICE_SEMIANNUAL`, `STRIPE_PRICE_ANNUAL`, `STRIPE_TRIAL_DAYS=7`,
   `BILLING_RETURN_URL=signalbase://billing-return`.
3. Deploy: `stripe-checkout`, `stripe-portal`, and `stripe-webhook`
   **`--no-verify-jwt`**.
4. Webhook endpoint on `checkout.session.completed` +
   `customer.subscription.*`; set `STRIPE_WEBHOOK_SECRET`.
5. Test with `stripe listen` / card `4242 4242 4242 4242`.
6. `EXPO_PUBLIC_BILLING_RAIL=stripe` in the build env.

US storefront only (EU external-purchase rules differ), and note Apple's
pending 5–15% linkout fee. Stripe-rail guarantees, pinned by
`verify_billing.ts`: price chosen server-side from a plan key; user from the
JWT; webhook signature verified over the raw body.

</details>

---

## Two limitations stated plainly

**1. The paywall is client-side.** `picks` is anon-readable and deliberately so
— the website and the Claude-mobile workflow (CLAUDE.md §16) both query it with
the anon key. The gate stops ordinary users, not someone reading the table
directly. `has_active_subscription()` exists for real enforcement; wiring it up
means first moving the website + Claude-mobile onto a service-role key, then
revoking anon SELECT on `picks`, then serving signals through a gated RPC. Do
it in that order or the daily workflow breaks.

**2. Selling picks raises the bar on claims.** CLAUDE.md §2 still frames this
as paper trading until the go-live gate. Once money changes hands, ROI and
win-rate claims become advertising, and income claims in gambling-adjacent
products attract FTC attention. The paywall copy promises access to signals,
not returns — keep it that way.

## Files

| Piece | File |
|---|---|
| Flags, rail, plans, RC keys | `src/lib/billingConfig.ts` |
| Pure billing helpers | `src/lib/billingHelpers.ts` |
| Pure IAP helpers (entitlement id, plan mapping) | `src/lib/iapHelpers.ts` |
| Native SDK wrapper (guarded dynamic require) | `src/lib/iap.ts` |
| Rail dispatcher (checkout / manage / restore) | `src/lib/billing.ts` |
| Entitlement state | `src/hooks/useSubscription.ts` |
| Paywall (localized prices, restore) | `src/screens/PaywallScreen.tsx` |
| Locked-signal state | `src/components/SignalLockCard.tsx` |
| IAP webhook | `supabase/functions/revenuecat-webhook/` |
| Stripe functions (fallback) | `supabase/functions/stripe-*/` |
| Verification (72 assertions) | `scripts/verify_billing.ts` |

Schema: `subscriptions` keyed to `auth.users` — migrations
`add_stripe_subscriptions`, `tighten_subscriptions_grants`,
`add_iap_columns_to_subscriptions` (applied). RLS on; users read their own row;
`anon` revoked; only the webhooks write (service role).

# Billing — Stripe subscriptions, built and switched off

Signalbase has a complete subscription layer (Stripe Checkout, webhook-driven
entitlement, billing portal, paywall UI) that is **inactive**. `BILLING_ENABLED`
in `src/lib/billingConfig.ts` is the kill switch, and it is `false`.

## The ladder

| Plan | Price | Effective/mo | Saving |
|---|---|---|---|
| Monthly | $29.99 | $29.99 | — |
| Season Pass (6 mo) | $129.99 | $21.67 | 28% |
| Annual | $199.99 | $16.67 | 44% |

7-day free trial on all three. Prices live in **two** places — `billingConfig.ts`
(display) and Stripe (what's actually charged). `verify_billing.ts` pins the
display numbers; if you change a price in Stripe, change it here too or the
paywall will quote a number the customer isn't billed.

## Read this before you launch

### 1. Stripe may not accept this business

Stripe's restricted-business list names *"sports forecasting or odds making with
a monetary or material prize."* **Restricted** means conditional: the default
outcome is decline or **account closure**, and approval must be in writing.

You are plausibly outside the literal wording — you sell model output and award
no prizes — but "sports betting picks subscription" is exactly the description
that triggers a review. **Describe the business accurately when you apply and
get written confirmation before you take a single payment.** A frozen account
with live subscriptions and customer funds in flight is the worst outcome
available here, and it is entirely avoidable by asking first.

If Stripe declines, the realistic alternatives are Paddle or Lemon Squeezy
(merchant-of-record, generally more tolerant of this category, and they handle
sales tax) or Apple IAP.

### 2. Apple: US-only, and the commission is about to change

In the US you may link out to external checkout with **no entitlement and no
Apple commission** — that's the court-ordered position from the Epic contempt
ruling. But Apple filed on **2026-08-13** to charge 15% (5% under the Small
Business Program) on external-link purchases, and the court is setting a rate
now. Budget for 5–15% appearing with little notice; annual plans absorb it far
better than monthly.

Outside the US the rules are different (EU needs the External Purchase Link
entitlement plus Core Technology fees). **Ship this to the US storefront only**
until someone works the EU rules deliberately.

Practical review notes:
- The paywall must state renewal terms and how to cancel — it does.
- There must be a working cancel path — that's the `stripe-portal` function,
  surfaced from Settings → Subscription.
- Don't describe the purchase as an in-app purchase, and don't use Apple's IAP
  vocabulary in the UI.

### 3. The paywall is client-side. Know exactly what that means.

`picks` is **anon-readable** today, and deliberately so: the Lovable website and
your own Claude-mobile workflow (CLAUDE.md §16) both query it with the anon key.
So the gate in the app hides signals from ordinary users but **does not stop
anyone who reads the table directly**.

That's an acceptable launch position — it stops essentially every real user, and
the honest track record is the pitch anyway — but it is not enforcement, and it
should not be described to customers as though it were.

Real enforcement means revoking anon SELECT on `picks` and serving signals
through a `security definer` RPC that checks `has_active_subscription()`. That
function is already created and granted. The reason it isn't wired up is that
doing so **breaks your Claude-mobile daily workflow and the website**, both of
which read `picks` anonymously. Sequence it deliberately:

1. Move the website + Claude-mobile queries onto a service-role or dedicated key.
2. Add the gated RPC for the app.
3. Revoke anon SELECT on `picks`.

### 4. Selling picks raises the bar on claims

CLAUDE.md §2 still says the project is paper-trading until the go-live gate
passes, and several models are paused. The published record (+5–6% ROI over
~1,500 picks) is real and defensible — but once money changes hands, ROI and
win-rate claims become advertising, and income claims in gambling-adjacent
products attract FTC attention. Decide what you will and won't claim before the
marketing copy is written. The paywall copy currently promises access to
signals, not returns; keep it that way.

---

## Activation

### 1. Stripe dashboard

Create one **Product** ("Signalbase") with three recurring **Prices**:

| Price | Amount | Interval |
|---|---|---|
| Monthly | $29.99 | every 1 month |
| Season Pass | $129.99 | every 6 months |
| Annual | $199.99 | every 12 months |

Copy each `price_…` id. Enable the **Billing Portal** (Settings → Billing →
Customer portal) with cancellation allowed, or the manage/cancel path 404s.

### 2. Edge Function secrets

```bash
supabase secrets set \
  STRIPE_SECRET_KEY=sk_test_xxx \
  STRIPE_PRICE_MONTHLY=price_xxx \
  STRIPE_PRICE_SEMIANNUAL=price_xxx \
  STRIPE_PRICE_ANNUAL=price_xxx \
  STRIPE_TRIAL_DAYS=7 \
  BILLING_RETURN_URL=signalbase://billing-return
```

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are injected automatically.

### 3. Deploy

```bash
supabase functions deploy stripe-checkout
supabase functions deploy stripe-portal
supabase functions deploy stripe-webhook --no-verify-jwt
```

`stripe-webhook` **must** be `--no-verify-jwt` — Stripe doesn't send a Supabase
JWT. Its authenticity comes from the signature check instead.

### 4. Register the webhook

Stripe → Developers → Webhooks → Add endpoint:

```
https://vvprgnrmzeekokzkrkfu.supabase.co/functions/v1/stripe-webhook
```

Events: `checkout.session.completed`, `customer.subscription.created`,
`customer.subscription.updated`, `customer.subscription.deleted`,
`customer.subscription.paused`, `customer.subscription.resumed`.

Copy the signing secret and set it:

```bash
supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_xxx
```

### 5. Test before flipping anything

```bash
stripe listen --forward-to \
  https://vvprgnrmzeekokzkrkfu.supabase.co/functions/v1/stripe-webhook
stripe trigger checkout.session.completed
```

Then confirm a row landed:

```sql
SELECT user_id, status, plan, trial_end, current_period_end FROM subscriptions;
```

Use test card `4242 4242 4242 4242`. Verify the full loop: subscribe → row
appears as `trialing` → app unlocks → cancel in the portal →
`cancel_at_period_end` flips true → access persists to period end.

### 6. Flip the flags

Billing requires auth — a subscription belongs to an account, not a device, or
it's lost on reinstall and can't follow the user to a second phone.
`billingReady()` enforces the pairing.

```ts
// src/lib/authConfig.ts
export const AUTH_ENABLED = true;
// src/lib/billingConfig.ts
export const BILLING_ENABLED = true;
```

Or per-build: `EXPO_PUBLIC_AUTH_ENABLED=true EXPO_PUBLIC_BILLING_ENABLED=true`.

Complete `docs/AUTHENTICATION.md` first — billing on top of dark auth does
nothing.

### 7. Ship

JS-only → **Actions → Mobile OTA update (production)**.

---

## How entitlement actually flows

```
app → stripe-checkout (JWT)     plan key → price id, server-side
    → Stripe Checkout (browser) user pays
    → Stripe → stripe-webhook   signature verified, subscriptions upserted
    → app re-reads subscriptions (RLS: own row only) → entitled
```

The app never writes `subscriptions`, so a client cannot grant itself access —
not by replaying the success URL, not by posting a price id of its own. Three
properties hold that up, each pinned by `verify_billing.ts`:

- the **price is chosen server-side** from a plan key;
- the **user comes from the JWT**, never the request body;
- the **webhook verifies Stripe's signature** over the raw body, in constant
  time, within a 5-minute tolerance.

`isEntitled()` checks status **and** period end. An `active` row whose period
already lapsed does not entitle — that happens when a webhook is missed, and
trusting status alone would hand out free access indefinitely.

## Files

| Piece | File |
|---|---|
| Flag, plans, prices | `src/lib/billingConfig.ts` |
| Pure helpers | `src/lib/billingHelpers.ts` |
| Checkout / portal / read | `src/lib/billing.ts` |
| Entitlement state | `src/hooks/useSubscription.ts` |
| Paywall | `src/screens/PaywallScreen.tsx` |
| Locked-signal state | `src/components/SignalLockCard.tsx` |
| Checkout session | `supabase/functions/stripe-checkout/` |
| Entitlement webhook | `supabase/functions/stripe-webhook/` |
| Manage / cancel | `supabase/functions/stripe-portal/` |
| Verification | `scripts/verify_billing.ts` |

Schema: migrations `add_stripe_subscriptions` + `tighten_subscriptions_grants`
(applied). RLS on, users read their own row, `anon` explicitly revoked, the
webhook writes as service role.

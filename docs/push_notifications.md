# Signal-flip push notifications

The **backend is built and live**: a `push-notifications` pipeline step detects
new/dropped signals and pushes a summary to every opted-in device via the keyless
Expo Push API. What remains is the **mobile half**, which needs a native rebuild +
push credentials — only doable on Matt's machine with the Apple/Google accounts.
This file is the precise enablement guide.

> **Now three producers** (all share the same tokens + `push_sent` ledger; this
> doc's enablement covers all of them):
> - `notify_signal_changes` — new/dropped pre-game BET signals (hourly pipeline).
> - `notify_line_changes` — Track-a-bet: a tracked bet's DK line moved ≥
>   `config.LINE_CHANGE_NOTIFY_PP` (hourly pipeline). Needs `device_id` on the
>   token row (see the hook below).
> - `notify_live_signals` — a new in-play BET signal (fires from the live loop).
>
> CLI: `python -m tracking.push_notifier [--line-changes | --live] [--dry-run]`.

## What the backend already does

- **Tables** (`add_push_notifications` migration, applied):
  - `device_push_tokens(token, platform, enabled, …)` — opted-in Expo tokens. Anon
    can INSERT/UPDATE (the app writes its own token) but **not SELECT** (tokens
    can't be enumerated). The pipeline reads via service-role.
  - `push_sent(lock_key, kind, sent_at)` — ledger so a signal is never pushed twice.
- **`tracking/push_notifier.py`** — `notify_signal_changes(date, dry_run)`:
  - `new_bet`: a locked `opening_signals` row that clears the current
    `model_action_thresholds` cut (same filter the app's `passesActionFilter` uses)
    and hasn't been pushed.
  - `dropped`: a previously-pushed signal whose live pick is now `AVOID`
    (flipped against us), pre-settlement.
  - Sends **one summary push per event type per device** (not one per signal),
    then ledgers every `lock_key`. Idempotent across the hourly runs.
- **Pipeline**: runs last as Step 11; `python run_pipeline.py --step push-notifications`
  (supports `--dry-run`). No-op when there are no devices or no new/dropped signals.

## Status, measured — NO PUSH HAS EVER REACHED A PHONE (2026-09-06)

`push_sent` looks like a working notifier and is not one. Counts on 2026-09-06:
**1,158 `new_bet`, 578 `live_signal`**, running right up to that morning — and
**`device_push_tokens` held ZERO rows**.

The producers ledger *regardless of token count* (the comment in
`notify_signal_changes` says so explicitly: "so a signal with zero devices
online isn't re-detected forever"). So with no tokens, `messages` is `[]`,
`_expo_send` is never called, and every lock_key is still written. **A row in
`push_sent` means "this signal was considered", not "a phone was notified."**
This is the `.claude/rules/operations.md` rule — *check `push_sent` before
believing a notifier ever worked* — landing one step further along than it
reads: the kinds are not empty, and the notifier still never delivered.

What is missing is only the REGISTRATION half below: a native build carrying
`expo-notifications`, APNs/FCM credentials, and a user who opts in
(`usePushOptIn`). Until one token exists, every producer is a no-op and the
routing added on 2026-09-06 (`mobile/src/lib/pushRoute.ts`,
`usePushDeepLink`) cannot be exercised end to end.

**Re-check with one query before believing otherwise:**

```sql
select (select count(*) from device_push_tokens where enabled) as devices,
       kind, count(*) from push_sent group by kind order by count desc;
```

Zero devices means the ledger is bookkeeping, whatever its counts say.

## Where a tap LANDS (added 2026-09-06)

Every message now carries a versioned `data` payload and the app routes on it —
before this a tap opened whatever screen the user last had open, which for a
live pick (~45s stale by construction) discarded the point of the notification.

| push | lands on |
|---|---|
| one pick in the batch | that pick's detail screen |
| `live_signals` (several) | Picks → Live segment |
| `new_bets` (several) | Picks → Signals |
| `dropped` | Picks → Today (a flipped pick is no longer a signal) |
| `line_change` | the tracked bet's detail (always exactly one) |
| `feedback_reply` | that support thread |

`sport` is only sent when the whole batch shares one; a push spanning sports
must not switch the board, which shows one sport at a time. `PUSH_ROUTE_VERSION`
is pinned in both halves — the worker deploys on merge, the app arrives by OTA,
and an unreadable payload deliberately routes nowhere (the tap just opens the
app) rather than guessing.

Test it now without any mobile work:

```bash
python -m tracking.push_notifier --dry-run            # prints intended pushes
python run_pipeline.py --step push-notifications --dry-run
```

## Mobile enablement (Matt's machine)

### 1. Install the native module + rebuild

```bash
cd mobile
npx expo install expo-notifications
# expo-notifications is a NATIVE module — an OTA update can't add it. Cut a new
# dev/prod build so the binary contains it:
eas build --profile preview --platform ios      # (and/or android)
```

### 2. Configure push credentials

- **iOS**: an APNs key in your Apple Developer account, registered with EAS:
  `eas credentials` → iOS → Push Notifications → set up a Push Key. (Expo can
  manage this for you.)
- **Android**: an FCM V1 service-account key uploaded to EAS
  (`eas credentials` → Android → FCM V1).
- Expo routes through these automatically once set; the backend sends to
  `exp.host/--/api/v2/push/send` with no key.

### 3. Add the registration hook (ready to paste)

`mobile/src/hooks/usePushNotifications.ts`:

```ts
import { useEffect } from 'react';
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { supabase } from '@/lib/supabase';
import { getDeviceId } from '@/hooks/useDeviceId';   // stable per-install id (track-a-bet)
import { usePushOptIn } from '@/hooks/usePushOptIn'; // tiny AsyncStorage boolean store

/** Registers for push + upserts the Expo token when the user has opted in.
 *  All native calls are guarded so a binary without the module just no-ops. */
export function usePushNotifications(): void {
  const { enabled } = usePushOptIn();
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    (async () => {
      try {
        const perm = await Notifications.requestPermissionsAsync();
        if (perm.status !== 'granted') return;
        const projectId = '0e16eb4b-190b-4356-be61-5b7a6b1da5ee';
        const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
        if (cancelled || !token) return;
        const deviceId = await getDeviceId();   // ← needed so Track-a-bet line-change
                                                //   alerts can resolve THIS device's token
        await supabase
          .from('device_push_tokens')
          .upsert(
            { token, device_id: deviceId, platform: Platform.OS, enabled: true,
              last_seen: new Date().toISOString() },
            { onConflict: 'token' },
          );
      } catch (err) {
        // No native module (pre-rebuild) or permission denied → silently skip.
        console.warn('[push] registration skipped', err);
      }
    })();
    return () => { cancelled = true; };
  }, [enabled]);
}
```

Mount it once in `App.tsx` next to `useActionThresholds()`. Add a
`usePushOptIn` store (mirror `useOnboarding`) and a **Settings** toggle row
("Signal alerts") that flips it; on disable, set `enabled = false` on the token
row so the backend stops sending:

```ts
await supabase.from('device_push_tokens')
  .update({ enabled: false }).eq('token', token);
```

> Because `expo-notifications` is only imported in this hook, don't add it to the
> JS bundle until the dep is installed (step 1) — otherwise Metro can't resolve it
> and the EAS preview build fails. Add the dep + hook together in the rebuild PR.

### 4. Verify end-to-end

1. Install the new build on a device, toggle Settings → Signal alerts on, accept
   the permission prompt. Confirm a row lands in `device_push_tokens`.
2. Trigger a send: `python -m tracking.push_notifier` (or wait for the next
   pipeline run). You should get a summary notification for the day's new signals.
3. Re-run it — no duplicate (the `push_sent` ledger blocks it).

## Tuning knobs (later)

- Quiet hours / per-sport opt-in: filter tokens or events in `push_notifier.py`.
- Per-signal (not summary) pushes: build one message per signal in `_build_messages`.
- Settled-result pushes ("your signal won"): add a `kind='settled'` pass after
  `settle_opening_signals`.


---

## One-time enablement checklist (moved from CLAUDE.md §26, 2026-08-30)

All four notification producers are **built, wired, and ledgered** (sessions 73, 79–81):
`tracking/push_notifier.py` has `notify_signal_changes` (new/dropped BET signals),
`notify_line_changes` (Track-a-bet big DK line moves), and `notify_live_signals`
(in-play BET signals). They send via the keyless Expo Push API to every row in
`device_push_tokens`. **The ONLY thing left is the one-time native push setup on
your machine** — until a device token exists, every alert is computed and ledgered
but has nowhere to deliver. Full guide: `docs/push_notifications.md`. Quick path:

### 1. Native module + registration hook (mobile/)
```bash
cd mobile
npx expo install expo-notifications
```
- Create `src/hooks/usePushOptIn.ts` — AsyncStorage boolean store (mirror `useOnboarding`).
- Create `src/hooks/usePushNotifications.ts` — paste from `docs/push_notifications.md`,
  **but add `device_id` to the upsert** (import `getDeviceId` from `useDeviceId`) so
  Track-a-bet line-change alerts can resolve THIS device's token:
  ```ts
  const deviceId = await getDeviceId();
  await supabase.from('device_push_tokens').upsert(
    { token, device_id: deviceId, platform: Platform.OS, enabled: true,
      last_seen: new Date().toISOString() },
    { onConflict: 'token' });
  ```
- Mount `usePushNotifications()` in `App.tsx` next to `useActionThresholds()`.
- Add a **Settings → "Notifications"** toggle wired to `usePushOptIn` (on disable,
  set `enabled = false` on the token row so the backend stops sending).
- Add the dep + hook **together** in this rebuild (don't import `expo-notifications`
  in the JS bundle before installing it, or the EAS preview build fails).

### 2. EAS push credentials
```bash
cd mobile
eas credentials      # iOS → Push Notifications → set up an APNs key (let Expo manage)
eas credentials      # Android → FCM V1 → upload the service-account key
```

### 3. Native build (push is a NATIVE module — OTA/Expo Update can't add it)
```bash
cd mobile
eas build --profile preview --platform ios      # and/or android
# install the resulting build on your phone
```

### 4. Turn it on + test each producer
- Open the app → **Settings → Notifications ON** → accept the OS permission prompt.
  Confirm a row appears in `device_push_tokens` (with your `device_id`).
- Fire each producer from a terminal (each supports `--dry-run` to preview):
  ```bash
  python -m tracking.push_notifier                 # new/dropped signal alerts
  python -m tracking.push_notifier --line-changes  # track-a-bet (needs a tracked bet whose line moved)
  python -m tracking.push_notifier --live          # live in-play signals
  ```
  Signal-flip + line-change also fire automatically every hourly refresh
  (`--step push-notifications`); live alerts fire from the live loop.
- Re-run → no duplicate (the `push_sent` ledger blocks it).

Once a token exists, **everything built in P1–P4 starts delivering with zero further
code changes** — just edit `config.LINE_CHANGE_NOTIFY_PP` to tune the track threshold.

---

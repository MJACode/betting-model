# Signal-flip push notifications

The **backend is built and live** (this PR): a `push-notifications` pipeline step
detects new/dropped signals and pushes a summary to every opted-in device via the
keyless Expo Push API. What remains is the **mobile half**, which needs a native
rebuild + push credentials — only doable on Matt's machine with the Apple/Google
accounts. This file is the precise enablement guide.

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
        await supabase
          .from('device_push_tokens')
          .upsert(
            { token, platform: Platform.OS, enabled: true, last_seen: new Date().toISOString() },
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

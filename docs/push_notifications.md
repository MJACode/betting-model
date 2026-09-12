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

## Status, measured — NO PUSH HAS EVER REACHED A PHONE (re-measured 2026-09-12)

`push_sent` looks like a working notifier and is not one. On 2026-09-12:

```
device_push_tokens:  0 rows (enabled or not), last_seen NULL
push_sent:           1,736 rows  (1,158 new_bet, 578 live_signal)
```

The producers ledger *regardless of token count* (the comment in
`notify_signal_changes` says so explicitly: "so a signal with zero devices
online isn't re-detected forever"). So with no tokens, `messages` is `[]`,
`_expo_send` is never called, and every lock_key is still written. **A row in
`push_sent` means "this signal was considered", not "a phone was notified."**

**Re-check with one query before believing otherwise:**

```sql
select (select count(*) from device_push_tokens where enabled) as devices,
       kind, count(*) from push_sent group by kind order by count desc;
```

Zero devices means the ledger is bookkeeping, whatever its counts say.

### Why zero, when the app has shipped push code since 2026-09-08

`expo-notifications` and the registration hook landed in `27cfe34`
(2026-09-08). TestFlight build **12201** (run #69, 2026-09-11, commit
`3e05350`) is a descendant of it, so the binary on the phone carries the
module. The registration still cannot succeed, and **the EAS build log for
that run says why**:

```
Project Credentials Configuration
Distribution Certificate   Updated  3 months ago
Provisioning Profile       Updated  2 months ago
All credentials are ready to build @mjacode/betting-picks
```

The profile was last touched ~2026-07-11 — **two months before push existed in
this project**. A push-capable iOS binary needs the `aps-environment`
entitlement, which comes from the provisioning profile, and
`eas build --non-interactive` REUSES the profile it already holds rather than
regenerating one for a newly added capability. Nothing in the build, the
submit, or the app said a word about it.

> **Not yet measured directly:** the entitlement has not been read out of the
> IPA — the sandbox cannot reach `expo.dev` artifacts and the xcode log URL
> expires in 15 minutes. The build workflow now performs that read on every
> run (below), so the next build answers it definitively rather than by
> inference.

## The enablement, in the order it has to happen (2026-09-12)

1. **Add an APNs push key to EAS** — only Matt can, it needs the Apple account:

   ```bash
   cd mobile
   eas credentials       # iOS → production → Push Notifications → set up a Push Key
   ```

   Let Expo manage the key. This also enables the Push Notifications capability
   on the App ID, which is what makes the regenerated profile carry
   `aps-environment`.

2. **Cut a new TestFlight build** — Actions → *Mobile TestFlight build* → Run
   workflow. It now **downloads the finished IPA, reads `aps-environment` out
   of the embedded provisioning profile, and refuses to submit a build that
   lacks it** (override with the `allow_missing_push_entitlement` input). A
   push-less build can no longer reach TestFlight unnoticed.

3. **On the phone:** install the build, Settings → **Notifications** ON, accept
   the OS prompt. The card now says which of these happened:

   | what you see | what it means |
   |---|---|
   | "This device is registered" | a row exists in `device_push_tokens` |
   | "This build is not registered for Apple push" | step 1 or 2 was skipped |
   | "Notifications are turned off for Signalbase" | the OS prompt was declined — the card offers to open iOS Settings |
   | "…could not be saved" | Apple issued a token, the database write failed |

4. **Prove it end to end:** tap **Send a test notification** in the same card.
   The app posts to the keyless Expo push API with its own token and reads the
   ticket back, so it covers the entitlement, the token, Expo, the OS
   presenting it, and the deep link. No slate and no worker run needed.

5. **Then the producers:** `python -m tracking.push_notifier [--line-changes | --live]`.

## What 2026-09-12 changed in the code

The registration half existed and could not report. Four silent failures, all
closed:

- **`usePushNotifications` swallowed everything** into one `console.warn`, and
  never read `.upsert()`'s `{ error }`. It now resolves to a state —
  `idle / registering / registered / failed` — with a typed diagnosis
  (`lib/pushDiagnosis.ts`), rendered by `components/NotificationsCard.tsx`.
- **Opt-OUT was never implemented.** The toggle wrote an AsyncStorage boolean
  and nothing else, so turning notifications off left `enabled = true` and the
  worker would have kept sending forever. `unregisterForPush` now flips the row
  (and the last token is persisted, so it works after a restart).
- **No `setNotificationHandler`, so a push arriving while the app was OPEN was
  never displayed.** The first thing anyone would do to check that push works
  was guaranteed to show nothing. `lib/pushPresentation.ts`, installed at
  App.tsx module scope.
- **`_expo_send` counted a 200 as a delivery.** Expo returns one ticket per
  message and a ticket can say `DeviceNotRegistered` or `InvalidCredentials`;
  the worker read none of it, so a message Apple refused was logged as sent.
  `_read_tickets` now pairs tickets to messages positionally, counts only
  accepted ones, disables retired tokens, and logs a credentials refusal as its
  own line. A reply it cannot pair counts nothing and disables nothing —
  guessing which token an error belongs to is worse than not acting.

Guards: `tests/test_push_tickets.py` (12, watched failing under three
mutations) and `mobile/scripts/verify_push.ts` (37, watched failing under
four).

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

## Mobile enablement — SUPERSEDED (kept as history)

This section used to be the guide: install `expo-notifications`, paste a
registration hook, add a Settings toggle. **All three shipped on 2026-09-08 and
2026-09-12.** The hook it told you to paste is not the hook in the repo — the
pasted one swallowed every error, which is the bug that cost this feature a
week. Following it now would be a regression.

The live guide is **"The enablement, in the order it has to happen"** above.
What survives from here is the one step that was always the real blocker and is
still outstanding: the **APNs push key** (`eas credentials`), which is step 1
there.

## Tuning knobs (later)

- Quiet hours / per-sport opt-in: filter tokens or events in `push_notifier.py`.
- Per-signal (not summary) pushes: build one message per signal in `_build_messages`.
- Settled-result pushes ("your signal won"): add a `kind='settled'` pass after
  `settle_opening_signals`.


---

## One-time enablement checklist — SUPERSEDED (kept as history)

Moved here from CLAUDE.md §26 on 2026-08-30 and correct for its moment: at the
time nothing mobile existed. Its steps 1 and 3 are done. Its step 2 — the EAS
push credentials — is the one still open, and is step 1 of the live guide
above. Do not work this list; work that one.

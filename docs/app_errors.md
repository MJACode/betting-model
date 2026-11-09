# App crash and error logging (`app_errors`)

Added 2026-10-19 (Matt: "Set up crash logging"), after "the app crashes now and
then the first time I open it, then works" could not be traced: the app had no
crash reporting and no error boundary.

## What is captured

| kind | when | what it can and cannot tell you |
|---|---|---|
| `js_fatal` | uncaught JS error that closes the app | message + stack. The native handler waits up to 1.5 s for the send, then the report is kept on the phone and sent next launch |
| `js_error` | uncaught JS error the app survived | message + stack |
| `render` | a screen threw while rendering | message, stack and React's component stack. The member sees "Something went wrong / Retry" instead of the app closing (`AppErrorBoundary`) |
| `early_exit` | the PREVIOUS launch never lived 15 s | JS cannot see a native crash, but it can see the last launch died young and at which `stage`. **Not every row is a crash**: a member closing the app inside 15 s also lands here. `extra.gap_ms` is the marker → next launch gap |
| `emergency_launch` | expo-updates rolled back to the built-in bundle because the downloaded one crashed | `message` is expo-updates' own reason |

`stage` is `launching` (first 15 s) or `running`. Rows from 2026-10-19 may
carry `ota_reload`, written just before `Updates.reloadAsync()` while the app
still applied bundles in-process. **It no longer does** (Matt, option A): a
check only downloads, and expo-updates runs the bundle at the next cold start.
The TestFlight report that settled it (10:41 ET, process launched 09:04) died
in expo-updates' `ErrorRecovery.crash()`, i.e. a fatal JS error inside the
10 s window after an in-process reload. If a crash like that comes back, look
for a `js_fatal` row: the global handler sees the error before expo-updates
re-throws it.
`update_id` /
`update_created_at` name the OTA bundle running when the report was made; NULL
is the bundle built into the binary.

## Freeze tracking (added 2026-11-06)

Matt: "Back button was not working on this screen … Cannot move from that
screen need to restart. This keeps happening in other spots." Nothing was in
`app_errors`: a frozen screen throws no error. `mobile/src/lib/freezeLog.ts`
adds three kinds and a trail.

| kind | when | what it tells you |
|---|---|---|
| `restart` | at launch, about the PREVIOUS session (15 s or longer): it ended while `active` or `inactive` (on screen or in the app switcher) without going to background, OR the app was relaunched within 2 min of going to background | the member likely killed the app. `screen` is where they were. `extra.touches_since_nav` (taps with no screen change), `extra.open_modals`, `extra.since_last_touch_ms` and `extra.trail` say what they were trying. iOS reclaiming a backgrounded app can also land here: `ended_state = background` with a long trail of normal use is that |
| `js_stall` | the JS thread stopped for 5 s or more while on screen (a 2 s watchdog saw a long gap) | `extra.stall_ms`. Up to 3 per launch. A stall that never ends sends nothing itself; the next launch's `restart` shows it as a session with no saves near the end (`since_last_save_ms`) |
| `modal_stuck` | a pop-up was told to open (or close) and iOS did not confirm with `onShow` (`onDismiss`) within 4 s | `extra.modal` names the pop-up (`trackName`), `extra.phase` is `present` or `dismiss`. A pop-up left half-presented is an invisible layer that swallows every tap. Once per pop-up and phase per launch. iOS only for `dismiss` |

**The trail.** Every report from 2026-11-06 carries `extra.trail`: the last 40
events as `[seconds before the report, kind, detail]` — `launch`, `screen`,
`touch` (a run of taps is one entry, detail = count), `app_state`,
`modal_open` / `modal_shown` / `modal_close` / `modal_dismissed`, `stall`.
`extra.session` has `app_state`, `open_modals`, `touches_since_nav`,
`since_last_touch_ms`. On a `restart` the trail's seconds count back from the
last saved event of that session, not from the report.

**Every pop-up goes through `mobile/src/components/TrackedModal.tsx`**, never
react-native's `Modal` (`tests/test_mobile_freeze_log.py`). Taps are counted at
the root (`onTouchStart` on `GestureHandlerRootView`). Taps on the native
header (the iOS Back button) are UIKit, so they may not reach it: unverified.

**First catch, 2026-11-07 23:54Z** (iOS 27.2, PlayerStats). A `restart` with
`open_modals` [] and 19 taps since the last screen change. AddLineSheet's open
and close were both confirmed. This is the "Back does nothing" signature: JS
alive, no layer over the screen, and the native pop refused. Response
2026-11-08: arrow-only Back with no custom title (`tests/test_mobile_back_button.py`,
`docs/sessions/2026-11.md`). Another such row after that ships means it was
not the custom title.

**Not verified on a phone before merge**: that iOS fires `onDismiss` on every
close in this React Native version. If every close shows up as a
`modal_stuck` `dismiss`, that is the callback, not a freeze.

```sql
-- Freezes and restarts, newest first, with what was going on
SELECT received_at, kind, screen, platform, app_version, left(message, 120) AS message,
       extra->'open_modals' AS open_modals, extra->'touches_since_nav' AS taps_no_nav,
       extra->'modal' AS modal, extra->'phase' AS phase, extra->'trail' AS trail
FROM app_errors
WHERE kind IN ('restart', 'js_stall', 'modal_stuck')
ORDER BY received_at DESC
LIMIT 30;
```

```sql
-- Which screens and pop-ups the restarts happen on
SELECT kind, coalesce(screen, extra->>'modal') AS where_, count(*)
FROM app_errors
WHERE kind IN ('restart', 'js_stall', 'modal_stuck')
GROUP BY 1, 2 ORDER BY 3 DESC;
```

Migration: `data/migrations/app_errors_freeze_kinds_2026_11_06.sql` (hand-applied,
widens the kind CHECK and the RPC, raises the `extra` cap to 16,000 chars).

**Native crashes and iOS app hangs** are in Sentry, copied to `sentry_events`: `docs/sentry.md`.

## Where it lives

| Piece | What |
|---|---|
| `data/migrations/add_app_errors.sql` | table + `log_app_error` RPC. Applied 2026-10-19 via MCP `apply_migration` |
| `mobile/src/lib/crashLog.ts` | the logic: queue in AsyncStorage, send, global handler, launch marker. No imports, so it runs under bare node |
| `mobile/src/lib/crashLogSetup.ts` | wires it to AsyncStorage, Supabase and expo-updates; `startCrashLogging()` runs at module scope in `App.tsx` |
| `mobile/src/components/AppErrorBoundary.tsx` | root error boundary |
| `mobile/src/lib/freezeLog.ts` + `freezeLogSetup.ts`, `components/TrackedModal.tsx` | freeze tracking (above); checks in `scripts/verify_freeze_log.ts` + `tests/test_mobile_freeze_log.py` |
| `mobile/scripts/verify_crash_log.ts` + `tests/test_app_crash_log.py` | the checks (in the PR CI subset) |

Access: RLS on, no policies, table grants revoked from anon/authenticated by
name. The anon key can only call `log_app_error`, which inserts and returns
nothing. Capped at 60 rows per device per hour; past that, reports are dropped
silently.

## Reading it

Run as the service role (Supabase SQL editor or the MCP). Row 1
(`device-verify-1234`) is the 2026-10-19 end-to-end check, not a crash.

```sql
-- Latest reports
SELECT received_at, kind, stage, screen, platform, app_version,
       update_created_at, left(message, 160) AS message, extra
FROM app_errors
WHERE device_id <> 'device-verify-1234'
ORDER BY received_at DESC
LIMIT 50;
```

```sql
-- Launches that died young, by stage, with the gap to the next launch.
-- (ota_reload rows exist only from before the 2026-10-19 never-reload change.)
SELECT stage,
       count(*)                                         AS n,
       count(*) FILTER (WHERE (extra->>'gap_ms')::bigint <  5000) AS back_under_5s,
       count(*) FILTER (WHERE (extra->>'gap_ms')::bigint >= 5000) AS back_after_5s,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY (extra->>'gap_ms')::bigint) AS median_gap_ms
FROM app_errors
WHERE kind = 'early_exit'
GROUP BY stage;
```

```sql
-- One device's history (the device id is in Settings → feedback rows too)
SELECT received_at, kind, stage, screen, left(message, 200), stack
FROM app_errors WHERE device_id = '<id>' ORDER BY received_at DESC;
```

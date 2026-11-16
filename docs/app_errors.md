# App crash and error logging (`app_errors`)

Added 2026-10-19 (Matt: "Set up crash logging"), after "the app crashes now and
then the first time I open it, then works" could not be traced: the app had no
crash reporting and no error boundary.

## What is captured

| kind | when | what it can and cannot tell you |
|---|---|---|
| `js_fatal` | uncaught JS error that closes the app | message + stack. The native handler waits up to 1.5 s for the send, then the report is kept on the phone and sent next launch |
| `js_error` | uncaught JS error the app survived | message + stack. A message starting `handoff:` is not an error: see "Hand-offs that missed the app" |
| `render` | a screen threw while rendering | message, stack and React's component stack. The member sees "Something went wrong / Retry" instead of the app closing (`AppErrorBoundary`) |
| `early_exit` | the PREVIOUS launch never lived 15 s | JS cannot see a native crash, but it can see the last launch died young and at which `stage`. **Not every row is a crash**: a member closing the app inside 15 s also lands here. `extra.gap_ms` is the marker → next launch gap |
| `emergency_launch` | expo-updates rolled back to the built-in bundle because the downloaded one crashed, OR (from 2026-11-14) expo-updates' own log records a failed launch not yet reported (`extra.source = 'updates_log'`) | `message` is expo-updates' own reason, or the newest launch-failure log entry as `code: message`. `extra.updates_log` lists up to 15 entries (`at`, `level`, `code`, `message`, `update_id`, `asset_id`, `stacktrace`). See "Native aborts before JS" below |

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

## Native aborts before JS (added 2026-11-14)

TestFlight 1.3.0 (14101), 2026-11-14 07:08 ET: the app died 0.24 s after
launch in expo-updates' `ErrorRecovery.crash()`. The bundle it picked failed,
the relaunch from cache failed, and it aborted, while `UpdatesReaper` was
deleting old update files on another thread. No JS ran, so nothing reached
`app_errors`, and Apple's report does not print the exception's text.

expo-updates writes that text to its own log file on the phone before it
aborts (`ErrorRecovery.writeErrorOrExceptionToLog`, code `JSRuntimeError`,
then `UpdateFailedToLoad` "crashing"). `beginLaunch` now reads that log
(`Updates.readLogEntriesAsync`, last 24 h, the read cut off at 3 s). When the
`error`/`fatal` entries not yet sent include a failed LAUNCH (code
`UpdateFailedToLoad`, `JSRuntimeError`, `InitializationError`, or level
`fatal`), one `emergency_launch` row goes, with `extra.source = 'updates_log'`,
named and dated by the newest launch-failure entry. Download errors, which
expo-updates also logs at error level when the phone is offline (code `Unknown`,
`AssetsFailedToLoad`, `UpdateServerUnreachable`), are never a row on their own,
and ride along as context. The newest timestamp sent is kept in AsyncStorage
(`crashlog.updates_log_seen`), written only once the row is stored. No new
server kind: an unknown kind fails its send and stops the queue behind it.

**Limit, unverified on a device:** the exception's log write is dispatched to
a background queue (`DispatchQueue.global().async`), so the abort can beat it.
Whether any entry survives a real abort is not yet measured. The first row
from a real crash settles it.

```sql
SELECT occurred_at, device_id, app_version, update_id, message,
       jsonb_pretty(extra->'updates_log') AS log
  FROM app_errors
 WHERE kind = 'emergency_launch'
 ORDER BY occurred_at DESC LIMIT 20;
```

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
`modal_open` / `modal_shown` / `modal_close` / `modal_dismissed`, `back` (a tap
on the React Back pill reached JS; detail `pop` / `replace` / `reset`, and a run on a dead
Back is one crumb, `pop x12`; taps with no `back` never reached it; a `back` with no
`screen` after it usually means the pop failed, but popping onto a screen of the same
name logs no `screen`, so `pop xN` can include such pops that worked), `push` (`held`: a notification tap
waited for the app to become active; `replay`: it then opened), `stall`.
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

## Hand-offs that missed the app (added 2026-11-15)

Not a crash. A tap on a book button that did not end with iOS opening the
book's app through the link that app claims writes one row, kind `js_error`,
message `handoff: <book> -> <route> (inst= via= mod= claimed= build=)`.
`mobile/src/lib/handoffLog.ts`; every book with an app entry (BOOK_APPS),
iOS only, one row per book and route per app session.

An `alt_host` row is NOT a miss: the BetMGM app opened through the same link
on another state host (`www.<st>` or `<st>.betmgm.com`) after iOS refused
`sports.<st>`. Exclude it when counting misses
(`AND message NOT LIKE 'handoff: % -> alt_host%'`).

A `link` row is not proof of Safari: iOS decides where the stored link opens,
and the app cannot see which. `scheme`, `store`, `web` and `failed` are exact.

| field (`extra.handoff`) | meaning |
|---|---|
| `route` | what opened: `scheme` (the app, by URL scheme, no bet on the slip), `store`, `link` (the stored link: the app or Safari, iOS decides), `web`, `failed` |
| `installed` | a declared scheme said the app is installed (`true`), the verified one said no (`false`), or cannot tell (`null`) |
| `viaApp` | iOS's answer to "open the claimed link in the app only": `false` = refused, `null` = not asked or the call failed |
| `moduleInBinary` | the `OpenInApp` native module is in this binary. `false` on a build before 14201 |
| `claimed` | host and path iOS was asked about, state masked; `null` = no claimed link was built |
| `scheme` | the scheme opened on the `scheme` route. A candidate that appears here is a real scheme of that book's app |
| `nativeBuild` | CFBundleVersion, e.g. `14301`; `null` if the binary cannot say |

```sql
SELECT received_at, device_id, message, extra->'handoff' AS handoff
FROM app_errors
WHERE kind = 'js_error' AND message LIKE 'handoff:%'
ORDER BY received_at DESC LIMIT 50;
```

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

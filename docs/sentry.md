# Sentry — native crashes and iOS app hangs (added 2026-11-06)

Matt: "Can we add Sentry tracking in the app" → "Yes continue with all"
(Sentry on; copy every event into Supabase; session replay off at first).

## Why, next to app_errors

`app_errors` (docs/app_errors.md) is written by the app's own JavaScript. It
cannot see a **native crash** (it only infers one: `early_exit`) or an **iOS
app hang**, where the main thread stops and the screen freezes while the JS
thread may be fine — the leading suspect for "the Back button did nothing,
had to restart" (2026-11-06). Sentry's native SDK reports both; hangs over
2 s by default.

**Supabase is still the system of record** (CLAUDE.md §1b). The worker copies
every Sentry event into `sentry_events` every 15 minutes
(`data/ingestors/sentry_events.py`, job `sentry_events_sync`), keyed on
Sentry's event id. Join to `app_errors` on `device_id`.

## What is sent

| Setting | Value | Why |
|---|---|---|
| `sendDefaultPii` | false | no email, no IP |
| `attachScreenshot`, `attachViewHierarchy` | false | screens show emails and bets |
| session replay | off: the replay rates are left UNSET | Matt: off at first. In 7.2.0 any number, 0 included, installs replay |
| performance tracing | off: `tracesSampleRate` left UNSET | same reason |
| `shutdownTimeout` | 1000 ms | a crashed app closes sooner; the native layer already saved the event |
| tags | `device_id` (the app's anonymous id), `release` (the app version), `screen`, `update_id` | join to app_errors. `device_id` and `release` are set in `initialScope`, before the first event. The id is read synchronously when a previous launch already stored it |
| `beforeSend` / `beforeBreadcrumb` | strip emails, bearer and basic tokens, JWTs, API keys, passwords, query-string tokens, and `user.email` / `user.ip_address` | a breadcrumb can carry a secret even with `sendDefaultPii` off |

Code: `mobile/src/lib/sentry.ts`. The public DSN for org `signal-base`,
project `signal-base-mobile` is set there. An empty `SENTRY_DSN` still
starts nothing.

## Setup — Matt's steps (once)

1. Create a free Sentry account (Developer plan), organisation, and a
   **React Native** project.
2. The public **DSN** is in `mobile/src/lib/sentry.ts` (org `signal-base`,
   project `signal-base-mobile`). It can only send events. `SENTRY_ORG` is
   `signal-base` and `SENTRY_PROJECT` is `signal-base-mobile`.
3. Create an **auth token** with scope `project:read` and `project:releases`
   (Settings → Auth Tokens). Then set the same three values in three places:

| Where | `SENTRY_AUTH_TOKEN` | `SENTRY_ORG` | `SENTRY_PROJECT` | What it does |
|---|---|---|---|---|
| EAS → project → Environment variables (production, secret) | ✓ | ✓ | ✓ | uploads source maps and native debug files during the TestFlight build |
| GitHub → repo → Settings → Secrets → Actions | ✓ | ✓ | ✓ | uploads OTA source maps (`mobile-ota.yml`). The workflow exports with `expo export --source-maps` and publishes that directory (`eas update --skip-bundler`), then uploads those maps with release `bundleId@version+build` and dist `buildNumber` from app.json — the native SDK's release, which `Sentry.init` does not override |
| Railway → `worker` → Variables (then redeploy) | ✓ | ✓ | ✓ | the copy into `sentry_events` |

Any of them missing: nothing fails. The build warns (`SENTRY_ALLOW_FAILURE=true`
in eas.json), the OTA step skips, the worker job reports `not_configured`.

4. Run **Mobile TestFlight build**. Sentry is a native module: it cannot ship
   over the air. The app version moved to **1.3.0**, so OTA updates published
   from now on reach only 1.3.0 builds (runtimeVersion = app version), and a
   1.2.0 install never gets a bundle that imports Sentry (it would crash on
   launch). 1.2.0 installs get no further OTA updates until they install
   1.3.0 — submit 1.3.0 to the App Store too.
5. App Store Connect → App Privacy. Every event carries the app's
   `device_id`, and `feedback_threads` stores that id beside `user_id`, so
   under Apple's definition the data is **linked to the user**. Declare
   **Diagnostics → Crash Data**, **Diagnostics → Performance Data** (hangs)
   and **Identifiers → Device ID**, each *linked to the user*, purpose **App
   Functionality**, **not used for tracking**. (The other way is to stop
   sending `device_id` to Sentry, which loses the join to `app_errors`.)
   Update the privacy policy to name Sentry as a processor of crash reports.

## Reading it

```sql
-- Latest Sentry events, newest first
SELECT occurred_at, event_type, level, title, screen, device_id, release
FROM sentry_events ORDER BY occurred_at DESC LIMIT 50;

-- App hangs by screen
SELECT screen, count(*) FROM sentry_events
WHERE title ILIKE 'App Hanging%' GROUP BY 1 ORDER BY 2 DESC;

-- One device: Sentry and app_errors side by side
SELECT 'sentry' src, occurred_at, title AS what, screen FROM sentry_events WHERE device_id = '<id>'
UNION ALL
SELECT 'app_errors', received_at, kind || ': ' || left(message, 80), screen FROM app_errors WHERE device_id = '<id>'
ORDER BY 2 DESC;
```

The `App Hanging` title is Sentry's wording for hang events on Cocoa as of the
schema read on 2026-11-06; confirm against the first real row.

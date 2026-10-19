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
| `early_exit` | the PREVIOUS launch never lived 15 s | JS cannot see a native crash, but it can see the last launch died young and at which `stage`. **Not every row is a crash**: a member closing the app inside 15 s and a successful OTA reload also land here. `extra.gap_ms` (marker → next launch) separates them: a reload that worked comes back in about a second |
| `emergency_launch` | expo-updates rolled back to the built-in bundle because the downloaded one crashed | `message` is expo-updates' own reason |

`stage` is `launching` (first 15 s), `ota_reload` (written just before
`Updates.reloadAsync()` in `useOtaUpdates`) or `running`. If `reloadAsync()`
throws, `clearOtaReload()` writes `running` again and replaces the marker, so
later errors in that same session are not labelled `ota_reload`.

**Since the same PR, launch no longer reloads** (`nextAction` returns
`download` at launch; the bundle is applied on the next return from the
background). So an `ota_reload` row now comes from a foreground reload, and
the measure of the fix is `early_exit` rows at stage `launching` with a gap of
tens of seconds after a new bundle ships: those are what a first-open crash
looks like, and there should be few. `update_id` /
`update_created_at` name the OTA bundle running when the report was made; NULL
is the bundle built into the binary.

## Where it lives

| Piece | What |
|---|---|
| `data/migrations/add_app_errors.sql` | table + `log_app_error` RPC. Applied 2026-10-19 via MCP `apply_migration` |
| `mobile/src/lib/crashLog.ts` | the logic: queue in AsyncStorage, send, global handler, launch marker. No imports, so it runs under bare node |
| `mobile/src/lib/crashLogSetup.ts` | wires it to AsyncStorage, Supabase and expo-updates; `startCrashLogging()` runs at module scope in `App.tsx` |
| `mobile/src/components/AppErrorBoundary.tsx` | root error boundary |
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
-- The first-open crash question: launches that died, by stage, with the gap.
-- A cluster of ota_reload rows with gap_ms in the tens of seconds = the app
-- died during the OTA reload and the member reopened it by hand.
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

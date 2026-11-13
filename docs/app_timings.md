# App load times (`app_timings`)

Added 2026-10-31 (Matt: "how can we improve the performance of the app" →
"measure first"). Before it, the only timing we had was `pg_stat_statements`,
which is server time only and a lifetime average since 2026-04-04. It cannot
see the network or how long a member waited for a screen.

## What is captured

| kind | what | measured from → to |
|---|---|---|
| `request` | one Supabase call. `name` = view/table, or `rpc:<fn>`, or `auth:<path>`. Never the query string | fetch start → response (or failure, `status = 0`) |
| `screen` | one navigation | route named → every request it started in its first 1.5 s has finished and the network has been idle 300 ms. `request_count` = how many. A screen with no request writes nothing |
| `launch` | the first screen of a cold start | JS start (perfLog module evaluated) → that screen loaded. Time iOS spends before JS runs is not visible |

On `screen` and `launch` rows, `status` is NULL when the screen loaded and **0
when the member left it first** (`ms` is then how long they waited before
leaving). Filter on it: a p90 over loaded screens alone hides the slowest ones.

`screen` on every row is the route that was focused when the request finished.
Polls (every 30 s / 2 min) appear as `request` rows and do not extend a screen.

## Where it lives

| Piece | What |
|---|---|
| `data/migrations/add_app_timings.sql` | table + `log_app_timings` RPC. Hand-applied 2026-10-31. Not in `ACTIVE_MIGRATIONS` (a fresh database needs it applied by hand; the worker must not re-run it) |
| `data/migrations/app_timings_cap_2026_11_01.sql` | replaces the RPC. Hand-applied, not in `ACTIVE_MIGRATIONS`, not applied by this change. Signed-in callers are capped on `auth.uid()`; integer columns are clamped |
| `mobile/src/lib/perfLog.ts` | the logic, no imports. Wraps the fetch Supabase uses; buffers up to 300 rows in memory |
| `mobile/src/lib/perfLogSetup.ts` | sends every 60 s and when the app goes to the background. After a network failure it waits 1, 2, 4 … 15 min; a batch the server rejects is dropped. Returning to the foreground resets the backoff |
| `data/app_timings_retention.py` | daily delete of rows older than 45 days. `python run_pipeline.py --step prune-app-timings` |
| `mobile/src/lib/supabase.ts` | `global: { fetch: timedFetch(...) }` |
| `mobile/scripts/verify_perf_log.ts` + `tests/test_app_timings.py` | the checks |

Rows are held in memory only: a crash or a kill loses the unsent minute. That
is acceptable for timings, unlike crash reports.

## Reading it

Service role (SQL editor or the MCP).

```sql
-- Cold start, and each screen: median and p90, last 7 days
SELECT kind, name, count(*) n, count(*) FILTER (WHERE status = 0) left_before_loaded,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ms)::int p50,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY ms)::int p90,
       round(avg(request_count), 1) avg_requests
FROM app_timings
WHERE kind IN ('launch', 'screen') AND received_at > now() - interval '7 days'
GROUP BY 1, 2 ORDER BY 1, p90 DESC;
```

```sql
-- Which reads cost the most waiting, last 7 days (calls x median)
SELECT name, count(*) calls,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ms)::int p50,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY ms)::int p90,
       count(*) FILTER (WHERE status = 0 OR status >= 400) failed
FROM app_timings
WHERE kind = 'request' AND received_at > now() - interval '7 days'
GROUP BY 1 ORDER BY calls * percentile_cont(0.5) WITHIN GROUP (ORDER BY ms) DESC
LIMIT 20;
```

Phone time minus server time (`pg_stat_statements.mean_exec_time` for the same
view) is network plus PostgREST. Compare only over the same window: reset
`pg_stat_statements` or read deltas, never the lifetime mean.

## Retention and the cap

Rows older than **45 days** are deleted by the daily pipeline
(`prune-app-timings`, `data/app_timings_retention.py`). The constant is 45,
inside the 30–60 day range: the queries above read 7 days, and a month behind
that stays. A dry run does not delete. The step is a skip, not a failure,
when the table is not there yet.

The RPC still drops rows silently past 1,000 in an hour. After
`app_timings_cap_2026_11_01.sql` is applied by hand, a signed-in caller is
counted on `auth.uid()` (`user_id`), so rotating the client device id does
not open a new budget, one call cannot insert past the room left under
1,000, and `ms` / `status` / `request_count` / `since_launch_ms` are clamped
instead of failing the batch. Until that file is applied, production still
caps on the client device id only.

An anonymous caller (no user JWT) is still capped only on `p_device_id`,
which the client chooses. There is no server-side identity on the anon key,
so that rotation hole stays. Retention is what bounds the table. The Live
tab polls three reads every 30 s, so a member who keeps it open through a
game could approach 1,000. The cap was not lowered: that member is the
population this table exists to measure. Check nothing sits at the cap:

```sql
SELECT device_id, date_trunc('hour', received_at) h, count(*)
FROM app_timings GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20;
```

After `app_timings_cap_2026_11_01.sql` is applied, group by `user_id` as
well. That column does not exist before then. It stays null on rows written
by an anonymous caller.

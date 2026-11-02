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
| `data/migrations/add_app_timings.sql` | table + `log_app_timings` RPC (insert-only, returns nothing, ≤100 rows a call, ≤1,000 rows per device per hour) |
| `mobile/src/lib/perfLog.ts` | the logic, no imports. Wraps the fetch Supabase uses; buffers up to 300 rows in memory |
| `mobile/src/lib/perfLogSetup.ts` | sends every 60 s and when the app goes to the background. After a failed send it waits 1, 2, 4 … 15 min; returning to the foreground resets that |
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

None yet. Size it from the first week's row count before adding a prune.

The RPC drops rows silently past 1,000 per device per hour. The Live tab polls
three reads every 30 s, so a member who keeps it open through a game could
approach that. After the first day, check nothing sits at the cap:

```sql
SELECT device_id, date_trunc('hour', received_at) h, count(*)
FROM app_timings GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20;
```

# Reliable pipeline scheduling — Supabase pg_cron → GitHub Actions

## The problem this fixes

The hourly **Refresh Picks** run was driven by GitHub Actions `schedule:` (cron).
GitHub's scheduled-event queue has **no timing guarantee** — under load it delays
runs 15–60 minutes or skips them. That's why picks/odds were going stale.

## The fix (Phase 1)

Supabase **pg_cron** now fires on the minute and calls GitHub's
**`workflow_dispatch`** API. A dispatched run starts within *seconds*, bypassing
GitHub's congested schedule queue. **No pipeline code changed.** The GitHub
workflows are untouched and their native `schedule:` crons are **kept as a backup**.

```
Supabase pg_cron (on time, every hour)
  └─ trigger_github_workflow('refresh_picks.yml')
       └─ POST .../actions/workflows/refresh_picks.yml/dispatches  (starts in seconds)
            └─ existing GitHub Actions job runs run_pipeline.py steps (unchanged)
```

## One-time setup (do these in order)

### Step 1 — Create a GitHub token
1. GitHub → Settings → Developer settings → **Fine-grained personal access tokens** → Generate new token.
2. **Resource owner:** MJACode · **Repository access:** Only select repos → `MJACode/betting-model`.
3. **Repository permissions:** `Actions` = **Read and write**, `Contents` = **Read**.
4. **Expiration:** pick a date (max 1 year) and set a calendar reminder to rotate it.
5. Copy the token (starts with `github_pat_...`). You only see it once.

### Step 2 — Apply the database migration
Run the SQL in `data/migrations/20260620_pg_cron_github_dispatch.sql`:
- Easiest: Supabase dashboard → **SQL Editor** → paste the file contents → Run.
- Or via the Supabase MCP `apply_migration` once approvals are available.

This enables pg_cron/pg_net, creates the trigger function + log table, and
schedules the two jobs. It's safe to re-run.

### Step 3 — Store the token (the only secret step)
In the Supabase **SQL Editor**, run once (paste your real token):

```sql
select vault.create_secret(
  'github_pat_PASTE_YOUR_TOKEN_HERE',
  'github_pat',
  'GitHub PAT for pg_cron workflow_dispatch (rotate before expiry)'
);
```

The moment this exists, the cron jobs start triggering GitHub successfully.
(Before it exists, they run but just log `SKIPPED` rows — harmless.)

## Verify it works

```sql
-- jobs are registered + active
select jobname, schedule, active from cron.job;

-- fire one manually right now
select public.trigger_github_workflow('refresh_picks.yml');
-- → a "Refresh Picks" run should appear in GitHub Actions within seconds

-- check it logged + GitHub accepted it (expect status_code 204)
select * from public.cron_trigger_log order by requested_at desc limit 5;
select status_code, content from net._http_response order by created desc limit 5;

-- cron execution history
select * from cron.job_run_details order by start_time desc limit 5;
```

## Schedule (UTC; EDT convention = UTC−4, same as the old GitHub crons)

| Job | Cron (UTC) | ET | Triggers |
|-----|-----------|----|----------|
| `refresh-picks-hourly` | `0 15-23,0-3 * * *` | 11am–11pm hourly (13×) | `refresh_picks.yml` |
| `daily-pipeline-7am` | `0 11 * * *` | 7am | `daily_pipeline.yml` |

Note: like the existing setup, this uses the EDT offset; in winter (EST) every
label drifts +1 hour. Acceptable — it matches current behavior.

## Backup / tradeoff

The GitHub native `schedule:` crons are intentionally **left in place** as a
fallback. If GitHub's late run fires *after* pg_cron already ran, you get a
duplicate run. That's **safe** — the scorer deletes and re-inserts unsettled
picks each pass — but it spends a few extra Odds API credits and GitHub minutes.
Once pg_cron is proven (a week or so), you can thin the native hourly cron in
`refresh_picks.yml` down to 1–2 times/day so it's a true backup, not a routine
double-fire.

## Rollback

```sql
select cron.unschedule('refresh-picks-hourly');
select cron.unschedule('daily-pipeline-7am');
```
The GitHub native crons keep running, so you're back to the old behavior.

## Phase 2 (later — growth path, not built yet)

When live in-play betting arrives (a 15s always-on loop GitHub Actions can't
host), move `run_pipeline.py` to a **Render Cron Job** + a **Render Background
Worker** for the live loop. Same platform for both, removes GitHub's monthly
Actions-minutes ceiling, and retires GitHub scheduling entirely (GitHub Actions
stays only for CI: mobile builds + manual training workflows). See the plan file
for details.

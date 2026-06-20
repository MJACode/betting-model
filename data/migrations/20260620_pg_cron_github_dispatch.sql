-- ============================================================================
-- Migration: pg_cron -> GitHub workflow_dispatch (reliable pipeline scheduling)
-- Date: 2026-06-20
-- Branch: claude/github-refresh-consistency-yjy6b7
--
-- WHY: GitHub Actions `schedule:` (cron) triggers have no timing SLA and were
-- routinely firing the hourly "Refresh Picks" run 15-60 min late (or dropping
-- it). This replaces the *timing* source with Supabase pg_cron, which calls
-- GitHub's workflow_dispatch API. A dispatched run starts within seconds,
-- bypassing GitHub's congested schedule queue. No pipeline code changes; the
-- GitHub workflows are unchanged and their native `schedule:` crons are kept as
-- a backup safety net.
--
-- WHAT THIS FILE DOES (safe to re-run — idempotent):
--   1. Enables pg_cron + pg_net.
--   2. Creates public.cron_trigger_log (observability) with RLS on, no anon policy.
--   3. Creates public.trigger_github_workflow(text) — reads the GitHub PAT from
--      Vault and POSTs a workflow_dispatch. No-ops gracefully (logs SKIPPED) if
--      the 'github_pat' secret is not present yet.
--   4. Schedules the two cron jobs (UTC; EDT convention = UTC-4, matches the
--      existing GitHub crons).
--
-- ONE MANUAL STEP REQUIRED (NOT in this file — it contains a secret):
--   After creating a fine-grained GitHub PAT (repo MJACode/betting-model,
--   permissions: Actions = Read and write, Contents = Read), run ONCE in the
--   Supabase SQL editor:
--
--     select vault.create_secret(
--       'github_pat_value_here',         -- paste the real token
--       'github_pat',
--       'GitHub PAT for pg_cron workflow_dispatch (rotate before expiry)'
--     );
--
--   Until that secret exists the cron jobs run but log SKIPPED rows (harmless).
-- ============================================================================

-- 1. Extensions -------------------------------------------------------------
create extension if not exists pg_cron;
create extension if not exists pg_net;

-- 2. Observability log ------------------------------------------------------
create table if not exists public.cron_trigger_log (
  id           bigint generated always as identity primary key,
  workflow     text not null,
  requested_at timestamptz not null default now(),
  request_id   bigint,      -- pg_net request id; join to net._http_response
  note         text         -- e.g. 'SKIPPED: github_pat secret not found'
);

alter table public.cron_trigger_log enable row level security;
-- Internal table: no anon/authenticated policy. The pipeline + cron run as the
-- postgres/service role, which bypasses RLS.

-- 3. Trigger function -------------------------------------------------------
create or replace function public.trigger_github_workflow(workflow_file text)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_token      text;
  v_request_id bigint;
begin
  select decrypted_secret
    into v_token
    from vault.decrypted_secrets
   where name = 'github_pat'
   limit 1;

  if v_token is null then
    insert into public.cron_trigger_log(workflow, note)
    values (workflow_file, 'SKIPPED: github_pat secret not found in vault');
    raise warning 'trigger_github_workflow: github_pat not set; skipped %', workflow_file;
    return null;
  end if;

  select net.http_post(
    url := 'https://api.github.com/repos/MJACode/betting-model/actions/workflows/'
           || workflow_file || '/dispatches',
    body := jsonb_build_object('ref', 'master'),
    headers := jsonb_build_object(
      'Authorization',        'Bearer ' || v_token,
      'Accept',               'application/vnd.github+json',
      'X-GitHub-Api-Version', '2022-11-28',
      'Content-Type',         'application/json',
      'User-Agent',           'supabase-pg-cron'   -- GitHub rejects no-UA requests
    ),
    timeout_milliseconds := 8000
  ) into v_request_id;

  insert into public.cron_trigger_log(workflow, request_id)
  values (workflow_file, v_request_id);

  return v_request_id;
end;
$$;

-- Lock the function down: only the table owner / postgres (and cron, which runs
-- as the job owner) may execute it. Never anon/authenticated.
revoke all on function public.trigger_github_workflow(text) from public;
revoke all on function public.trigger_github_workflow(text) from anon, authenticated;

-- 4. Schedules (UTC; EDT = UTC-4) ------------------------------------------
-- cron.schedule upserts by job name, so re-running this file just updates them.
--
-- Hourly refresh, 11am-11pm ET (= 15:00-23:00 + 00:00-03:00 UTC) = 13 runs/day:
select cron.schedule(
  'refresh-picks-hourly',
  '0 15-23,0-3 * * *',
  $job$ select public.trigger_github_workflow('refresh_picks.yml'); $job$
);

-- Full daily pipeline, 7am ET (= 11:00 UTC):
select cron.schedule(
  'daily-pipeline-7am',
  '0 11 * * *',
  $job$ select public.trigger_github_workflow('daily_pipeline.yml'); $job$
);

-- ============================================================================
-- VERIFY (run these in the SQL editor after applying + adding the secret):
--   select jobname, schedule, active from cron.job;
--   select public.trigger_github_workflow('refresh_picks.yml');  -- manual test
--   select * from public.cron_trigger_log order by requested_at desc limit 5;
--   select status_code, content from net._http_response order by created desc limit 5;  -- expect 204
--   select * from cron.job_run_details order by start_time desc limit 5;
--
-- ROLLBACK (revert to GitHub-only scheduling):
--   select cron.unschedule('refresh-picks-hourly');
--   select cron.unschedule('daily-pipeline-7am');
-- ============================================================================

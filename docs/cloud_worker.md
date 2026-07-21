# Cloud worker — running the pipeline off GitHub Actions

## Why

The betting pipeline used to be triggered by three scheduled GitHub Actions workflows
(`daily_pipeline.yml`, `refresh_picks.yml`, `evening_lines.yml`). On a **private** repo
that burned **~10,000 Actions minutes/month against a 2,000 free cap** — the evening loop
alone held a paid runner idle ~55 min/night (~8,000 min/month). GitHub started billing
overage (~$0.008/min).

The fix: run the same schedule on a **cheap always-on worker** (~$5/mo flat, no per-idle-
minute billing) via [`scheduler.py`](../scheduler.py). The pipeline code is unchanged —
`scheduler.py` just shells out to the existing entrypoints (`python run_pipeline.py` and
`bash scripts/refresh_pass.sh`) on the same cadence, with a real DST-aware
`America/New_York` timezone (which also fixes the "shifts 1 hr in winter" drift the old
crons had).

## Schedule (identical to the old Actions cadence)

| Job | When (ET) | Command |
|---|---|---|
| Daily full pipeline | 6:00am | `python run_pipeline.py` |
| Hourly refresh | :17, 7am–5pm | `bash scripts/refresh_pass.sh` |
| Evening fast lines | every :00..:50, 6–11pm | `bash scripts/refresh_pass.sh` |
| In-play live loop (supervisor) | every 10 min, 11am–midnight | `python -m data.ingestors.live_trigger_orchestrator --loop` |

Pre-game Odds-API credit burn is unchanged (same refresh cadence). Each job is
single-instance (`max_instances=1, coalesce=True`), so a long pass queues the next tick
instead of double-fetching.

### The in-play live loop

The live loop is not a cron in the usual sense — one invocation polls every live game's
state every 15 seconds, fetches in-play DK odds on inning/score changes, re-scores the
live models, and **runs for hours until the slate ends** (it exits after ~1 minute with
no active games). The `*/10` cron is a **supervisor**: whenever the loop isn't running
(morning, gap between afternoon and evening games, post-slate), the next tick relaunches
it; while it IS running, ticks are skipped by `max_instances=1` (APScheduler logs a
"maximum number of running instances reached" warning for each skipped tick — that's
expected, and doubles as a heartbeat that the loop is alive). A loop started late evening
keeps running past midnight until the last west-coast game finishes.

Credit safety: in-play fetches are debounced (60s) and capped by `LIVE_DAILY_CREDIT_CAP`
(default **1000/day**; set `LIVE_DAILY_CREDIT_CAP=0` in Variables to uncap once trusted).
Realistic burn is ~300–600 credits/evening on top of the pre-game refresh cadence.
Kill switch: set `RUN_LIVE_LOOP=0` in the Railway Variables tab and redeploy — the job is
never scheduled.

---

## Step 0 — stop the Actions billing now (GitHub UI, ~2 min)

Before/independent of deploying the worker:

1. GitHub → your avatar → **Settings → Billing and licensing → Budgets and alerts**.
2. Add/edit the **Actions** budget and set it to **$0** → blocks all Actions runs until
   the monthly reset → no overage charges.

Notes:
- A $0 budget also blocks the *manual* Actions jobs (mobile builds, retrains) until the
  reset. Run retrains from this worker or locally, and mobile builds via `eas build` /
  `eas update` from your machine (those already offload to Expo's servers) in the meantime.
- The $0 budget is only a **stopgap until the monthly reset**. The durable fix is that the
  three scheduled workflows no longer have a `schedule:` trigger (they're manual-only now),
  so they can't re-blow the cap after the reset.

---

## Deploy — Railway (recommended, ~$5/mo Hobby)

1. [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo** →
   `MJACode/betting-model`. Deploy from the **`master`** branch (that's where the worker
   files live).
2. The repo ships [`railway.json`](../railway.json), which sets the **Start Command** to
   `python scheduler.py` explicitly. Confirm it in **Settings → Deploy → Start Command**.
   (Do *not* rely on the `Procfile` alone — Railway/Nixpacks only auto-runs a `web:`
   process, so a lone `worker:` entry gets silently ignored and nothing ever starts.)
3. **Variables** tab → add (copy the secret values from your local `.env`):
   - `DATABASE_URL` — the Supabase **session pooler** connection string
   - `ODDS_API_KEY`
   - `DATAGOLF_API_KEY`
   - `FETCH_F5_LIVE` = `1`
   - `TZ` = `America/New_York`
4. Deploy. Open the **Logs** — on boot you should see
   `Betting scheduler starting … Registered jobs:` with the three jobs and their next run
   times in ET.

### ⚠️ The two reasons Railway "never kicks off the daily runs"

This is a **long-running always-on worker**, not a one-shot job. Two Railway settings
break it silently:

1. **Serverless / App Sleeping must be OFF.** Service → **Settings → Serverless** →
   disable it. The scheduler has **no HTTP server**, so it receives zero inbound traffic —
   with Serverless on, Railway sleeps the container and APScheduler never wakes to fire the
   6am / refresh jobs. This is the #1 cause of "it's deployed but nothing runs."
2. **Do NOT configure a Railway "Cron Schedule" on this service.** Railway's native cron
   expects the process to run and then **exit**; `scheduler.py` blocks forever, so pairing
   it with a cron schedule makes Railway think it's a hung job. Leave **Cron Schedule
   empty** — `scheduler.py` is the scheduler. (If you *want* Railway-native cron instead of
   the always-on worker, the schedule would run `python run_pipeline.py`, but that only
   covers the one daily run — you'd lose the hourly/evening refresh passes. Stick with the
   worker.)

Also confirm **`DATABASE_URL` is set** — without it the boot banner still prints, but every
job exits non-zero (`FAIL daily-pipeline (exit …)` in the logs) and no odds/picks are
written. The logs tell you which case you're in: no `START`/`DONE` lines at all → the
worker isn't running (start command / sleeping); `START` → `FAIL` → a missing/ bad env var.

## Deploy — Render (alternative, ~$7/mo Background Worker)

Option A (blueprint): the repo ships [`render.yaml`](../render.yaml). Render dashboard →
**New → Blueprint** → pick this repo → it creates a `worker` service. Then set the three
secret env vars (marked `sync:false`) in the dashboard.

Option B (manual): **New → Background Worker** → connect the repo → Build
`pip install -r requirements.txt`, Start `python scheduler.py`, plan **Starter**, and add
the same env vars as the Railway list above.

---

## What stays on your PC (do NOT move to the cloud)

The **Basketball Daily Ingest** Task Scheduler job (`scripts/wnba_daily_ingest.bat`, uses
`nba_api`/stats.nba.com) must stay on your machine — stats.nba.com blocks datacenter IPs,
so a cloud worker can't reach it any more than Actions could. Unchanged.

---

## Verify after deploy

1. **Boot:** worker logs show the four registered jobs + next-run times in ET.
2. **First tick:** at the next :17 (daytime) or :10 boundary (evening), logs show
   `START refresh-pass …` → `DONE refresh-pass (exit 0)`, and `picks` / `odds` in Supabase
   get a fresh `snapshot_at`.
3. **Live loop:** any tick between 11am and midnight ET shows `START live-loop` →
   `Live loop starting (interval 15s, …)`. Before first pitch it exits within ~1 min
   (`idle for 4 passes, exiting` → `DONE live-loop (exit 0)`) — normal. During games it
   stays running (skipped-tick warnings are the heartbeat), and Supabase accumulates rows
   in `live_game_state`, `live_credit_telemetry`, and `picks` with `is_live = true` (they
   surface on the mobile Live tab).
3. **Morning after cutover:** ask Claude mobile "how's the system?" — the daily run's
   `system_health.py` (Step 12) writes `system_health_checks`; confirm feeds are fresh
   (coming from the worker, not stale).
4. **Actions:** the Actions tab no longer shows auto-scheduled runs (only manual
   dispatches), and the billing page stops accruing minutes.

## Rollback / break-glass

The three workflows keep their `workflow_dispatch` trigger, so any step can still be run
on demand from **Actions → (workflow) → Run workflow** (needs the Actions budget > $0). To
fully revert to Actions scheduling, re-add the `schedule:` cron blocks (see git history)
and pause/delete the worker.

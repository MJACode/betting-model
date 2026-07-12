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

Odds-API credit burn is unchanged (same refresh cadence). Each job is single-instance
(`max_instances=1, coalesce=True`), so a long pass queues the next tick instead of
double-fetching.

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
   `MJACode/betting-model`.
2. Railway detects Python + the `Procfile`. Confirm the service **Start Command** is
   `python scheduler.py` (it reads the `Procfile`'s `worker:` line).
3. **Variables** tab → add (copy the secret values from your local `.env`):
   - `DATABASE_URL` — the Supabase **session pooler** connection string
   - `ODDS_API_KEY`
   - `DATAGOLF_API_KEY`
   - `FETCH_F5_LIVE` = `1`
   - `TZ` = `America/New_York`
4. Deploy. Open the **Logs** — on boot you should see
   `Betting scheduler starting … Registered jobs:` with the three jobs and their next run
   times in ET.

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

1. **Boot:** worker logs show the three registered jobs + next-run times in ET.
2. **First tick:** at the next :17 (daytime) or :10 boundary (evening), logs show
   `START refresh-pass …` → `DONE refresh-pass (exit 0)`, and `picks` / `odds` in Supabase
   get a fresh `snapshot_at`.
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

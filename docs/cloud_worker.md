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
| NFL poll — hourly | every :00 | `run_nfl_poll(fast=False)` — both NFL models, 10-day horizon |
| NFL poll — fast | every :10 | `run_nfl_poll(fast=True)` — only inside 3h of a kickoff |

Pre-game Odds-API credit burn is unchanged (same refresh cadence). Each job is
single-instance (`max_instances=1, coalesce=True`), so a long pass queues the next tick
instead of double-fetching.

### NFL polling (changed 2026-08-22)

The four fixed wind-card slots and the daily opener card were replaced by one poll
driver covering both NFL models. It watches from **10 days out, hourly**, and switches
to **every 10 minutes once a kickoff is inside 3 hours**.

The two jobs are mutually exclusive — the hourly one stands down inside the fast window,
so a tick is never paid for twice — and the driver returns immediately, spending
nothing, when no game is inside the horizon. That is most of the year, which is why it
stays scheduled year-round. Roughly **4 credits a tick** (2 markets x 2 regions), about
100/day in season.

Why poll rather than run on fixed days: **the lock**. The first moment a bet qualifies
it is written, timestamped and made immutable, and every later tick records whether the
conditions still hold (`nfl_pick_status_history`) without ever re-pricing the bet. Fixed
slots can only catch a qualifying number if it happens to still be there at 9am.

Watching early is not betting early — firing stays inside each model's validated window
(opener T-7..T-2, wind inside its 7-day calibration). Polling from T-10 buys the first
*fireable* moment, not an earlier bet.

**This is deliberately NOT on GitHub Actions.** At 144 runs/day the fast poll alone
would be ~13,000 Actions minutes/month against the 2,000 cap — the exact overage this
whole document exists to escape. An always-on worker runs it for a flat fee.

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

### The NFL wind-totals card

The standalone `nfl/` package's weekly bet card (CLAUDE.md §28), automated on the
runbook cadence — Thursday scan, Saturday firm-up, Sunday-morning place — plus a
**Monday 9am run** the runbook lacks (Sunday's `--days 1` window closes before
Monday-night kickoff, so without it MNF would never be priced). Each run re-prices
whatever is left in its window; per the runbook, later is better — the edge is
measured against the close and forecast skill improves as kickoff nears.

Operational notes:

- Runs with **cwd = `nfl/`** (the package reads `data/games.csv` and writes
  `data/cards/` relative to its own root). Its Python deps for this path (pandas,
  numpy, requests) are already in the root `requirements.txt` — the heavier
  `nfl/requirements.txt` extras (scipy, lightgbm, pyarrow) are only needed by the
  backtest/validation scripts, which are not scheduled.
- **No new key needed.** The nfl package (developed externally) reads
  `THE_ODDS_API_KEY` — a different env var *name* for the same Odds API service — so
  the scheduler maps the platform's existing `ODDS_API_KEY` into it automatically.
  Cost ≈ **5 credits/week in season** (1/run, +1 for the Sunday `us,eu` shop) —
  negligible against the platform's daily burn. Set `THE_ODDS_API_KEY` in Railway
  Variables only if you ever want the NFL card on its own key/quota (it takes
  precedence). With neither key set, the jobs run `--dry-run` (weather printout,
  0 credits) with a log warning.
- **Off-season is free:** the script exits `No games in window.` before any odds
  call, so the jobs can stay scheduled year-round.
- **After each LIVE card run, `scripts/nfl_wind_publisher.py` mirrors the
  qualifying bets into the `games` + `picks` tables** so they surface in the
  mobile app (NFL sport toggle, model `nfl_wind_totals`). Dry-run cards are
  never published. Results land via pipeline Step 0f (`--step nfl-results`,
  hosted nflverse games.csv) and picks settle through the generic totals path.
- The printed card in the worker log remains the primary read. The CSV
  (`nfl/data/cards/`) and the package's credit ledger
  (`nfl/data/credit_ledger.json`) land on ephemeral disk and reset on redeploy.
- **The opener-spread card** (`nfl_opener_spread`) runs daily at 9:30am ET on the
  same key: T-7..T-2 window, soft-book spread ≥ 1.0 pts off Pinnacle (regions
  `us,eu` — 2 credits/run), bet locked at its FIRST qualifying card and never
  re-priced (`--opener` publishing is insert-once; the edge is staleness).
- Kill switch: `RUN_NFL_WIND_CARD=0` in Railway Variables (disables both NFL
  card jobs).

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
   - `THE_ODDS_API_KEY` — OPTIONAL, normally omit. The NFL wind-card jobs reuse
     `ODDS_API_KEY` automatically (~5 credits/week in season); set this only to put
     the NFL card on a dedicated key/quota.
   - `DISCORD_WEBHOOK_*` — OPTIONAL, see [Discord](#discord-picks-to-your-server)
     below. Omit them all and nothing Discord-related runs.
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


## Discord — picks to your server

Picks post to Discord over **incoming webhooks**: no bot, no gateway connection,
nothing extra to host. Each channel gives you a URL; the worker POSTs to it. The
whole feature is off until at least one URL is set, so there is no "enable" flag.

### Creating the webhooks

In Discord, for each channel you want picks in:
**Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL.**
(You need Manage Webhooks on the server.) Name it whatever you like — the name
and avatar shown on the post come from the webhook itself.

### Railway variables

One channel per sport. Set only the sports you actually want; a sport with no
webhook is skipped, and — importantly — its signals are **not** marked as sent,
so adding that channel later still delivers the rest of the day's picks.

| Variable | Channel it feeds |
|---|---|
| `DISCORD_WEBHOOK_MLB` | e.g. `#mlb-picks` |
| `DISCORD_WEBHOOK_NFL` | `#nfl-picks` |
| `DISCORD_WEBHOOK_NBA` | `#nba-picks` |
| `DISCORD_WEBHOOK_NHL` | `#nhl-picks` |
| `DISCORD_WEBHOOK_WNBA` | `#wnba-picks` |
| `DISCORD_WEBHOOK_UFC` | `#ufc-picks` |
| `DISCORD_WEBHOOK_GOLF` | `#golf-picks` |
| `DISCORD_WEBHOOK_NCAAF` | `#ncaaf-picks` |
| `DISCORD_WEBHOOK_DEFAULT` | Catch-all for any sport without its own channel. Leave unset to post nothing for unmapped sports rather than dumping everything into one room. |
| `DISCORD_WEBHOOK_LIVE` | In-play signals. Worth its own channel — the live board re-scores every ~10 min during a slate. Falls back to the sport's channel if unset. |
| `DISCORD_WEBHOOK_RESULTS` | The morning results recap (cross-sport, so it needs its own home). Falls back to `DISCORD_WEBHOOK_DEFAULT`. |
| `DISCORD_MAX_EMBEDS_PER_RUN` | Optional, default `20`. Max picks posted to one channel per run. |

### What posts, and when

| Event | Trigger | Channel |
|---|---|---|
| **New BET signal** | The pick's first cross of the action thresholds — the same cut the app's Signals tab uses. Fires on the 6am run and each refresh pass as signals lock. | The sport's channel |
| **Live (in-play) signal** | End of each live-scorer pass | `DISCORD_WEBHOOK_LIVE`, else the sport's |
| **Results recap** | After settlement, once per settled day | `DISCORD_WEBHOOK_RESULTS` |

Each slate posts as one embed with a field per pick, showing **game, start time,
odds and unit stake only** — no model %, no edge, no book name. 1 unit = 1% of
roll (Kelly-scaled, rounded to 0.5u); prob-only picks default to 1u.

### Guarantees

- **Never posts twice.** Deduped through the existing `push_sent` ledger under
  `discord_*` kinds, independent of the mobile push for the same signal.
- **Only records what actually sent.** A post that fails (bad URL, Discord
  outage, rate limit) is left un-ledgered and retries on the next pass, rather
  than being silently swallowed.
- **Never breaks the pipeline.** Discord runs in its own try block in both the
  pipeline step and the live loop; a broken webhook logs and moves on.
- **The recap only covers a finished day.** `--step settle` runs every refresh
  pass against *today*; the recap refuses any date that is not already over, so
  it can't post a partial mid-slate record and then be ledgered.

### Testing it

From the worker shell or your machine, with the variables set:

```bash
python -m tracking.discord_notifier --dry-run              # log intended posts, send nothing
python -m tracking.discord_notifier                        # post today's new signals
python -m tracking.discord_notifier --results --date 2026-08-21   # post a past day's recap
```

`--dry-run` never posts and never ledgers, so it is safe to run repeatedly.

### Turning it off

Delete the `DISCORD_WEBHOOK_*` variables and redeploy. Deleting the webhook in
Discord also works — posts then fail, log, and (correctly) never ledger.

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

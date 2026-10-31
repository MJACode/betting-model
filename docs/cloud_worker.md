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
| Weekly and monthly results | Monday 7:30am (the month only on the first Monday) | `run_period_recaps()` — prior Mon–Sun, and the previous calendar month; Discord `#results` and X; ledgered. The same call also posts Eggz's windows to `#eggz-picks` when `DISCORD_WEBHOOK_EGGZ` is set, and ParlayMatt's windows when `DISCORD_WEBHOOK_PARLAYMATT` is set |
| Eggz channel read | every 15 min | `run_eggz_ingest()` — `#eggz-picks`, author `DISCORD_EGGZ_AUTHOR_ID` only, then ParlayMatt's channel when `DISCORD_PARLAYMATT_CHANNEL_ID` and `DISCORD_PARLAYMATT_AUTHOR_ID` are set. No request for a capper whose token, channel id, or author id is unset |
| Model quality monitor | 11:00am | `tracking.model_quality.run_model_quality()` — also Step 13 of the daily; report only, `model_quality_checks`. Kill switch: `RUN_MODEL_QUALITY=0` |
| Hourly refresh | :17, 7am–5pm | `bash scripts/refresh_pass.sh` |
| Evening fast lines | every :00..:50, 6–11pm | `bash scripts/refresh_pass.sh` |
| In-play live loop (supervisor) | every 10 min, 11am–midnight | `python -m data.ingestors.live_trigger_orchestrator --loop` |
| NFL poll — hourly | every :00 | `run_nfl_poll(fast=False)` — both NFL models, 10-day horizon |
| NFL poll — fast | every :10 | `run_nfl_poll(fast=True)` — only inside 3h of a kickoff |
| NFL schedule refresh | :05, :20, :35, :50, 24x7, and once when the scheduler starts | `python -m data.ingestors.nfl_props_data_ingestor --schedule-only` — the next 14 days of the nflverse schedule into `games` and `nfl_team_game_stats` (kickoffs, venues, newly listed playoff games); free, no odds call. Kill switch: `RUN_NFL_SCHEDULE_REFRESH=0`; cadence: `NFL_SCHEDULE_REFRESH_MINUTES` (default 15) |
| Heartbeat watchdog | every 15 min, 24x7 | `tracking.heartbeat_watchdog.run_watchdog()` — see below |
| Kalshi NFL prop ladders (quotes stored, not a bet) | every :40 | `run_kalshi_ladder_record()` → `kalshi_prop_ladders`; free, keyless, never on the betting path |
| Kalshi NCAAF game markets (quotes stored, not a bet) | every :45 | `run_kalshi_game_record()` → `kalshi_game_markets` (winner / total / spread ladders, ~5,000 contracts a pass); added 2026-09-10, session 280 |

Manual posts to @SignalBasePicks (`social_post_queue`, every 5 minutes) are
a separate job. They do not move the pick slate or the recap jobs above.
See `docs/social_posts.md`.

**Alternate spreads and totals (2026-10-29, Matt approved the cost; every
pass since the same day, option B).** Every refresh pass's odds step buys
alternates for games starting in the next 24 hours
(`ALT_GAME_LINES_WINDOW_HOURS`, default 24; `FETCH_ALT_GAME_LINES=0` turns
it off) and refreshes `alt_game_lines` for them, one ledger row per sport per
pass (`endpoint = 'pass'`). The daily full pipeline's Step 2-alt (`--step alt-game-lines`,
`data/ingestors/alt_game_lines.py`) makes one per-event call per game starting
in the next 3 days, for NFL, NCAAF, NBA, NHL, MLB, WNBA and NCAAB, and stores
every rung in `odds` (source `odds_api_alt_game_lines_live`, protected from the
pruner) and the current ladder in `alt_game_lines`, which the betslip's
game-line edit reads. Its cost was put to Matt as an ESTIMATE (~2-4 credits a
game, ~160 games); the measurement is `alt_game_line_fetches.credits_last`,
one row per call:

    SELECT fetch_at::date, sport, count(*) FILTER (WHERE endpoint = 'event_odds') AS games,
           sum(credits_last) AS credits, count(*) FILTER (WHERE NOT ok) AS failed
      FROM alt_game_line_fetches GROUP BY 1, 2 ORDER BY 1 DESC, 2;

Pre-game Odds-API credit burn is otherwise unchanged (same refresh cadence). Each job is
single-instance (`max_instances=1, coalesce=True`), so a long pass queues the next tick
instead of double-fetching.

### Same-day daily retry (2026-09-18)

The 6:00am ET daily is the only writer of `mlb_bullpen_workload` / `mlb_team_stats`
(Steps 0d/3/3b/5c). Hourlies never touch them. A CronTrigger whose 6:00am fire has
already passed does **not** misfire when the scheduler starts — so a worker restart
mid-daily (a Railway redeploy after a merge) left the run `failed_steps=aborted` and
aimed the next daily at *tomorrow* 6:00am. `pipeline_watch` reported the abort and
did not re-queue.

`scheduler.py::catch_up_daily_pipeline` runs on boot and again after the 7:15am ET
pipeline watch. If today's daily is missing, unfinished, aborted, or failed before
the MLB freshness steps, it invokes `python run_pipeline.py` once the same
America/New_York calendar day, posts an ops Discord note, and caps at one automatic
retry (two ledgered `run_kind='daily'` starts). In-process lock plus a successful
daily already today both no-op. Kill switch: `RUN_DAILY_RETRY=0`. See
`tracking/daily_retry.py`.

**The :17 refresh pass has the same catch-up (2026-09-21).** A merge to master
stops the container whatever it is doing; 11 refresh passes ended `aborted`
between 09-18 and 09-20, and on 09-20 no pass completed between 16:32 and 19:31
UTC. `scheduler.py::catch_up_refresh_pass` runs as a one-off job 60 seconds
after boot: if this hour's `hourly` pass is unfinished or `aborted`, the next
:17 is at least ten minutes away, and no more than two passes were interrupted
this hour, it runs `refresh_pass.sh` once. The evening pass is never replaced
(its next tick is at most ten minutes away). **It buys odds — about 1,000
credits a re-run** (1,018 measured on the 09-20 19:17 UTC pass). Kill switch:
`RUN_REFRESH_RETRY=0`. See `tracking/refresh_retry.py`.

**A deploy-killed refresh row is closed at boot (2026-10-16).**
`_abort_orphans` only stamps the kind that is starting. Evening
`06b9db72a43c4323ad5ed84abf00b591` (started 03:50Z) was still the only
unfinished `pipeline_runs` row later that morning: later hourlies finished,
and the next evening `start_run` is the next evening, so
`refresh_pass_completion` stayed on its stuck branch.
`scheduler.abort_orphaned_refresh_runs` runs once before the scheduler
starts, on the service that owns `hourly_refresh`, and stamps unfinished
`hourly` and `evening` rows that started before this process
(`finished_at`, `ok=false`, `failed_steps='aborted'`). It does not touch
`daily`. The cutoff freezes on the first call, so a second call cannot
abort a pass this process has opened. The one-off
`abort_deploy_killed_evening_2026_10_16.sql` closes that row on the next
view-migration pass if boot has not already. This sweep does not re-run
the pass.

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

### Scoreboard live scores (NFL, NBA, NHL — added 2026-10-29)

`live_scoreboard` job, `pollers` service, every minute 24x7
(`data/ingestors/live_scoreboard.py`). While a sport has a game that has
started, has no final on `games` and no final row yet, it reads ESPN's site
scoreboard once per sport for each ET date on the slate (today, and
yesterday until 6 am ET; ESPN refuses a date range with HTTP 400) and
upserts one row per game into
`public.live_scoreboard` (`state` `in` / `post`, score, clock label, NFL down
and possession). The app's Scoreboard reads it. No Odds API credits. An idle
tick is one database read and no HTTP call. `RUN_LIVE_SCOREBOARD=0` stops it.
`site.api.espn.com` answered the worker 200 on 3,164 scheduler calls in the
week before 2026-10-29 (`api_call_log`); older notes calling it 403 from the
worker are out of date. MLB and NCAAF keep their own live tables.

The Scoreboard's % bets / % money come from the `scoreboard-splits`
refresh-pass step (`data/ingestors/scoreboard_splits.py`) into
`public.scoreboard_splits`: Action Network's free v2 scoreboard, every sport
with an unstarted game today or tomorrow, display only (never
`public_betting`, which the scorer reads).

### NHL player props

`data/ingestors/nhl_prop_odds_ingestor.py`, 2026-10-01 (mike). Step
`nhl-prop-odds` on **every refresh pass**, and safe there: it buys an opening
and a closing snapshot per game and nothing else, decided from what
`player_prop_odds` already holds. Measured on the live endpoint: 5 credits a
game per snapshot, so about 13,400 a season. One run stops at
`NHL_PROP_MAX_CREDITS_PER_RUN` (400). Kill switch: `RUN_NHL_PROP_ODDS=0`.

`nhl-prop-scoring` runs right after it: the blocked-shots card
(`scripts/nhl_prop_card.py`, DraftKings) and the saves / shots-on-goal /
assists card (`scripts/nhl_props_card.py`, the best price among the bettable
books in the game's newest fetch). Neither spends credits; each writes a pick
at most once per player per game per market and is a no-op until a book has
posted the market. One card failing does not stop the other.

### College football player props

`data/ingestors/ncaaf_prop_odds_ingestor.py`, 2026-09-05. **9am / 1pm / 6pm ET
daily**, gated on `RUN_NCAAF_PROP_ODDS=1` (code default is still `0`, so it is
one Railway variable away from off).

A college Saturday is 120 games against MLB's ~15, and a prop pull is one paid
call per event, so this is the one ingestor whose cost is set by slate size
rather than cadence. It is scoped to games DraftKings has already lined
(`NCAAF_PROP_REQUIRE_DK_LINE=1`, 70 of 120 on the measured Saturday) under a
hard per-pass ceiling (`NCAAF_PROP_MAX_EVENTS=80`), and the measured cost
comes from the probe rather than an estimate:

```
python -m data.ingestors.ncaaf_prop_odds_ingestor --probe    # writes nothing
```

or as a worker job, which is how it runs here — `ncaaf_prop_odds` with
`{"probe": true}` (`jobs/declared_jobs.json`). The probe reports credits per
event, WHICH of the 24 requested markets The Odds API actually serves for
college (it uses one key namespace for both football leagues and documents
neither), which books answer, and what one full scoped pass would cost.

**What the probe measured, 2026-09-05** (job `ncaaf_prop_odds`, `{"probe":
true}`, verified against `api_call_log` rather than its own header delta):

| | |
|---|---|
| credits per event | **8.7** |
| events the feed lists | **68** (not the 120 in `games` — the Odds API never carries the Division III fixtures) |
| one full pass | **~590 credits** |
| markets served | 13 of 20 requested, from 7 books |
| rejected (422) | 0 |

Three passes on a Saturday is therefore **~1,800 credits**, and hourly would
be ~8,300 — both affordable, which is why the cadence is set by how often a
college prop line is worth re-reading rather than by cost. 9am / 1pm / 6pm ET
puts one fresh number before each kick wave; minute 35 keeps it clear of the
:17 refresh pass and the :25 NFL prop card.

Scheduled **daily**, not Saturday-only: college also plays Thursday and Friday
nights. A day with no games costs nothing — the ingestor lists events first
(that call is free, measured) and returns before any paid call.

**A prior estimate here was wrong by ~12x and is worth remembering.** Before
the probe, this section projected ~6,800 credits for one pass, derived from
MLB's cost per market. Two assumptions did it: that our 120-game slate was
the population (the feed lists 68), and that credits scale with markets
REQUESTED (they scale with what comes back — college serves few markets at
few books, so a call is 1.7 credits, not 12). An estimate extrapolated from a
real measurement is still an estimate.

### The NFL wind-totals card

The standalone `nfl/` package's weekly bet card (`docs/sports/nfl.md`), automated on the
runbook cadence — Thursday scan, Saturday firm-up, Sunday-morning place — plus a
**Monday 9am run** the runbook lacks (Sunday's `--days 1` window closes before
Monday-night kickoff, so without it MNF would never be priced). Each run re-prices
whatever is left in its window; per the runbook, later is better — the edge is
measured against the close and forecast skill improves as kickoff nears.

Operational notes:

- Runs with **cwd = `nfl/`** (the package writes `data/cards/` relative to its
  own root). Its schedule is the `games` table (`nfl/data_ingest/schedule.py`),
  not the frozen `data/games.csv`, since 2026-10-20 (`docs/sports/nfl.md`),
  kept current by the NFL schedule refresh above. Its Python deps for this path (pandas,
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
   - `MLB_SPREAD_MARKET_PUBLISH` / `MLB_TOTAL_MARKET_PUBLISH` /
     `MLB_TOTAL_PUBLIC_FADE_PUBLISH` — OPTIONAL, default `0`. MLB game-line
     cards log every pass; they INSERT picks only when the matching flag is
     `1` (redeploy after setting). Totals Pin-vs-soft INSERT is Pin fair −
     soft implied, BEST_LINE, pin-lean. Public-OVER fade INSERT is
     `mlb_total_public_fade` (ticket cut `MLB_TOTAL_PUBLIC_FADE_TICKET_PCT`,
     default 70; optional `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` default 0
     = all-pass, set 2 + `RANK=ticket` for top-K; optional under-juice
     band `MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MIN`/`_MAX`, unset = no
     band, I24 is −110/−100). See
     `docs/mlb_runline_ou_edge_search.md` and
     `docs/mlb_total_public_fade.md`.
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


## Live monitor — API traffic and picks as they happen

The worker also serves a real-time dashboard (`monitoring/`, full runbook in
`docs/monitoring.md`): every outbound API call, every pick as it is written,
credit burn, the last passes and the health checks. It runs as a daemon thread
inside `scheduler.py` — no second service, no extra cost.

Two steps to reach it from your phone:

1. Railway → Variables → `MONITOR_TOKEN` = a long random string.
   **Without it the server binds loopback only and stays unreachable** — that is
   deliberate, since the dashboard exposes pipeline internals and a Railway
   domain is public.
2. Railway → the `worker` service → Settings → Networking → **Generate Domain**.

Then open `https://<domain>/?token=<MONITOR_TOKEN>`.

`RUN_MONITOR=0` starts the worker without it; `PIPELINE_TELEMETRY=0` stops the
recording as well. Neither can break a pass — every part of the monitor
swallows its own failures.

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
| `DISCORD_WEBHOOK_LIVE_NFL` / `_LIVE_MLB` / `_LIVE_NCAAF` | **The sport's live channel** (`#nfl-live`, `#mlb-live`, `#ncaaf-live`; mike, 2026-09-09). Set on BOTH `worker` (runs the NFL in-play worker) and `pollers` (runs the MLB and NCAAF loops). Any `DISCORD_WEBHOOK_LIVE_{SPORT}` over the sport list works. |
| `DISCORD_WEBHOOK_LIVE` | Shared in-play channel, the fallback for a sport with no live channel of its own. Falls back to the sport's channel if unset too. |
| `DISCORD_WEBHOOK_RESULTS` | The morning results recap (cross-sport, so it needs its own home). Falls back to `DISCORD_WEBHOOK_DEFAULT`. |
| `DISCORD_WEBHOOK_FREE` | Free pick of the day. **No fallback on purpose** — this is a more
  public audience than the full feed, so leaving it unset posts nothing rather than leaking the
  free pick into the catch-all channel. |
| `DISCORD_WEBHOOK_OPS` | **Infrastructure alerts from the heartbeat watchdog.** **No fallback on purpose** — an outage alert in `#results` or a sport channel is noise to subscribers and leaks internal state. Unset means the watchdog can still SEE a problem and cannot report it, so it logs at CRITICAL instead. Point this at a private ops channel. A capper post that cannot be parsed is logged here once per message id when this is set (`eggz_review`, `parlaymatt_review`). |
| `DISCORD_WEBHOOK_EGGZ` | Eggz recaps in `#eggz-picks` only. **No fallback** to `#results`, `DISCORD_WEBHOOK_DEFAULT`, or X. Unset posts nothing. |
| `DISCORD_EGGZ_CHANNEL_ID` | The `#eggz-picks` channel id the bot reads. Unset, the poll does not call Discord. |
| `DISCORD_EGGZ_AUTHOR_ID` | Discord user id of the only author stored. That id is the user whose username is `jack_mehoff123` and whose display name is Dr. Eggz. The username is not the filter. |
| `DISCORD_WEBHOOK_PARLAYMATT` | ParlayMatt recaps in his channel only. **No fallback** to `#results`, `DISCORD_WEBHOOK_DEFAULT`, or X. Unset posts nothing. |
| `DISCORD_PARLAYMATT_CHANNEL_ID` | The `#parlaymatt-picks` channel id the bot reads. Unset, his poll does not call Discord. |
| `DISCORD_PARLAYMATT_AUTHOR_ID` | Discord user id of the only ParlayMatt author stored. The username is not the filter. |
| `DISCORD_BOT_TOKEN` | Existing bot token, the same one `monitoring/discord_stats.py` uses. The Eggz read reuses it. The bot needs View Channel and Read Message History in `#eggz-picks`, and the Message Content privileged intent. Without that intent Discord returns an empty body. |
| `WATCHDOG_STALE_MINUTES` | Optional, default `90`. How old the newest `pipeline_runs` row may get before the watchdog calls it a stall. |
| `WATCHDOG_RENOTIFY_MINUTES` | Optional, default `360`. How long before a still-live alert is repeated. |
| `DISCORD_MAX_EMBEDS_PER_RUN` | Optional, default `20`. Max picks posted to one channel per run. |

### What posts, and when

| Event | Trigger | Channel |
|---|---|---|
| **New BET signal** | The pick's first cross of the action thresholds — the same cut the app's Signals tab uses. Fires on the 6am run and each refresh pass as signals lock. | The sport's channel |
| **Live (in-play) signal** | End of each MLB / NCAAF live pass; after every NFL live BET the in-play worker writes | `DISCORD_WEBHOOK_LIVE_{SPORT}`, else `DISCORD_WEBHOOK_LIVE`, else the sport's |
| **Results recap** | After settlement, once per settled day. The 6:00am ET daily settles yesterday. A miss retries from 7:00am ET on later settle passes. | `DISCORD_WEBHOOK_RESULTS` (`#results`) |
| **Weekly results** | Monday 7:30am ET, the prior Monday–Sunday. Later settle passes retry until the next Monday 7:30am. | `DISCORD_WEBHOOK_RESULTS` (`#results`) |
| **Monthly results** | The first Monday of the month, 7:30am ET, the previous calendar month. Later settle passes retry until the next month's first Monday 7:30am. | `DISCORD_WEBHOOK_RESULTS` (`#results`) |
| **Eggz results** | Previous day from the 6:00am ET settle, and again on later settle passes. The week and the month use the Monday 7:30am clock. A window that still has a pending leg is not ledgered. | `DISCORD_WEBHOOK_EGGZ` (`#eggz-picks`) |
| **ParlayMatt results** | The same windows as Eggz. Unset webhook posts nothing. | `DISCORD_WEBHOOK_PARLAYMATT` |
| **Watchdog alert / recovery** | Database unreachable, or no completed pass in `WATCHDOG_STALE_MINUTES`. Checked every 15 minutes, around the clock. | `DISCORD_WEBHOOK_OPS` |
| **Free pick of the day** | ONE random qualifying pick, posted by the first pass of the day that finds one. NFL is preferred once the season produces signals; until then it falls through to MLB/WNBA/whatever qualified. | `DISCORD_WEBHOOK_FREE` |

Each slate posts as one embed with a field per pick, showing **game, start time,
odds and unit stake only** — no model %, no edge, no book name. 1 unit = 1% of
roll (Kelly-scaled, rounded to 0.5u); prob-only picks default to 1u.

### The units convention in the recap

The recap reports **units, not dollars**. The wager is the units you RISK; what
you win depends on the price — *risk 1.1u at −110 to win 1u*. So:

| outcome | units |
|---|---|
| WIN | `+ stake × (decimal odds − 1)` |
| LOSS | `− stake` (the full amount risked) |
| PUSH | `0`, and nothing counts as risked |

ROI is units won over units risked. The price is the one the bet was taken
at. A pick with no taken price is staked at the bare conviction, not dropped
and not given a made-up −110. Every graded pick in the record is in the units.

The recap fires from the **6am daily run**, which settles *yesterday*. It refuses
any date that is not already over, so the `--step settle` that runs on every
refresh pass (grading games as they finish) can never post a partial mid-slate
record and then ledger it.

The week and the month use that same settled query and the same `#results`
webhook. `period_recaps` fires Monday at 7:30am ET, after the daily post and
after the 7:00am retry. The week is the Monday–Sunday that just ended. The
month is the previous calendar month, and only when that Monday is the first
Monday of the month. A window that did not post stays due until the next one
opens; the ledger (`discord_results_week`, `discord_results_month`, and the
`x_results_*` pair, keyed on the window's start date) posts it once. X uses
the daily recap's renderer with the window's heading.

Eggz's recap uses that same clock and the same tally, on `DISCORD_WEBHOOK_EGGZ`
only. Ledger keys are `discord_eggz_results_day`, `discord_eggz_results_week`,
and `discord_eggz_results_month`, each with the window's start date. His bets
are `capper_picks`, graded with the existing settler and the DraftKings
pre-start close. They are not rows in `picks`, and they are not in `#results`
or on X. A line that cannot be parsed or matched is `needs_review` and is
logged; if `DISCORD_WEBHOOK_OPS` is set, one alert is posted for that message
id. The read is `eggz_ingest`, every 15 minutes, with `DISCORD_BOT_TOKEN`.

ParlayMatt uses that same clock and the same tally, on `DISCORD_WEBHOOK_PARLAYMATT`
only. Ledger keys are `discord_parlaymatt_results_day`,
`discord_parlaymatt_results_week`, and `discord_parlaymatt_results_month`.
His rows are `capper_picks` with `capper_key = 'parlaymatt'`. A parlay header
(`PARLAY +450 1u`, `3 leg parlay`) is one bet at that price and stake. The
legs are stored and graded, and they are not a second unit. A line that
cannot be parsed, a round robin, and a push that would change the stated
price are `needs_review`. They are not dropped. His all-time line starts at
his own first graded `game_date`. Unset channel, author, or webhook: that
half returns without a request and without a post. The same 15-minute job
reads his channel after Eggz.

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
   surface on the mobile Picks tab's Live segment).
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

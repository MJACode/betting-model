# Ops without GitHub Actions

**GitHub Actions is not used by this project.** The pipeline runs on the Railway
worker (`scheduler.py` — see [`cloud_worker.md`](cloud_worker.md)), and the
workflows that used to wrap one-off jobs were removed on 2026-08-24: a private
repo bills Actions minutes, and every one of those workflows was a thin wrapper
around a command that runs just as well on your machine.

This file is the replacement — what each deleted workflow ran, and what to run
instead. Nothing here needs a runner.

Everything below assumes you are in the repo root with your local `.env`
populated (`DATABASE_URL` = the Supabase **session pooler** string, `ODDS_API_KEY`,
`DATAGOLF_API_KEY`).

---

## Pipeline — already automatic on Railway

| Was | Now |
|---|---|
| `daily_pipeline.yml` | Railway `daily` job, 6:00am ET |
| `refresh_picks.yml` | Railway hourly refresh, :17 past 7am–5pm ET |
| `evening_lines.yml` | Railway evening loop, every 10 min 6–11pm ET |

You should never need to run these by hand. If Railway is down and you want a
manual run:

```bash
python run_pipeline.py            # full daily pipeline
bash scripts/refresh_pass.sh      # one odds-and-scoring refresh pass
python run_pipeline.py --step scoring     # or any single step
```

`python run_pipeline.py --help` lists every step name.

Model-quality monitor (one-sided slates / fade risk / CLV / ROI / volume) —
report only, writes `model_quality_checks`. See [`model_quality.md`](model_quality.md):

```bash
python -m tracking.model_quality
python run_pipeline.py --step model-quality
```

---

## NFL 2026 live track (opener + wind)

Not a retrain and not a unit bump. Re-score the two fragile §28 rules:

```bash
python -m scripts.nfl_rule_2026_track              # 2026 settled record
python -m scripts.nfl_rule_2026_track --settle     # existing grader, then record
```

Policy and current counts: [`docs/nfl_rule_2026_track.md`](nfl_rule_2026_track.md).
Opener retires if 2026 ≤ flat. Wind `MAX_FIRE_LEAD` stays 4.

---

## Model retrains

```bash
# Any model. The trainer registers the new version and deactivates the old one.
python -m models.trainer --model mlb_over_under \
  --seasons 2019 2020 2021 2022 2023 2024 2026 --holdout 2025 --trials 100

# WNBA / MLB-prop batches (these were wnba_train.yml / mlb_prop_retrain.yml —
# both just looped the same command over a list of model ids)
for m in wnba_moneyline wnba_over_under wnba_spread; do
  python -m models.trainer --model "$m" --trials 100
done
```

**The step the workflow did for you and you must not forget:** commit the new
artifact so the Railway worker can load it, and remove the superseded one.

```bash
git add -f models/saved/<model_id>_<new_timestamp>.pkl
# Keep-list is model_registry.is_active=1, not newest-filename. Update both:
#   .gitignore  !models/saved/<new>.pkl  (and drop the old ! line)
#   models/saved/MANIFEST.md
git rm --cached --ignore-unmatch models/saved/<old_version>.pkl
git commit -m "Retrain <model_id>" && git push
```

Without that push, `model_registry` points at a `.pkl` that isn't in the repo and
scoring silently skips the model — the session-51 UFC failure.

---

## Backfills and one-off data jobs

```bash
python -m data.ingestors.wnba_stats_ingestor --backfill 2019 2025   # was wnba_backfill.yml
python -m scripts.nfl_odds_backfill <args>                          # was nfl_odds_backfill.yml
python -m data.view_migrations                                      # after a merge: the view/function migrations (the worker also runs them each pass)
python -m data.db_setup                                             # FIRST-TIME schema setup only (was db_migrate.yml)
```

`data.db_setup` is not the post-merge step. It replays the whole base schema and
builds any index it declares that production lacks: on 2026-10-20 it tried to build
`idx_prop_odds_game` on `player_prop_odds`, held that table's writes for the full
two-minute statement timeout, and rolled back. A merged view or function change
goes through `data.view_migrations`.

```bash
```

**Local purchase runs are logged too** (since 2026-11-03). Every Odds API call
is written to `api_call_log`, however the run was started: `python -m
data.ingestors.nba_odds_history ...`, a launcher that calls `runpy`, a script,
or the worker. A local run's rows are named for the module it ran
(`data.ingestors.nba_odds_history`), so they read apart from the worker's
(`scheduler`). What a run spent, from the log:

```sql
SELECT source, count(*) AS calls, sum(credits) AS credits
FROM api_call_log
WHERE api = 'The Odds API' AND ts >= now() - interval '6 hours'
GROUP BY 1 ORDER BY 3 DESC NULLS LAST;
```

If the database stops answering mid-run, the calls are held and written once
it answers again; a call is never slowed or failed by its log. If it is still
down when the run exits, the run's own log says how many calls and credits were
not written. `PIPELINE_TELEMETRY=0` turns the log off, so never set it on a
purchase. Detail: `docs/monitoring.md`.

`nfl_props_setup.yml` existed only because the dev sandbox cannot reach Supabase
or the Odds API. From your machine, run its steps directly (see
`docs/nfl_props_model.md`); the `.github/nfl_props_trigger.txt` mechanism is gone.

---

## Mobile — the one thing that was never Railway's job

EAS builds cannot run on Railway (they need Expo's build service and your Apple
credentials). They also never needed Actions — the workflows just called the EAS
CLI. Run the same commands locally:

```bash
cd mobile

# Ship a JS-only change (almost every mobile session) — was mobile-ota.yml
eas update --channel production --message "what changed"

# Native change or a new binary — also available as a GitHub button, see below
eas build --profile production --platform ios
eas submit --platform ios --id <build-id>

# Preview build for a branch — was mobile-preview.yml
eas update --branch <branch-name>
```

Requires `npm i -g eas-cli` and `eas login` once. **Rule of thumb unchanged:** OTA
for pure JS/TS; a full build whenever a native module or `app.json` native config
changes, since an OTA bundle importing a missing native module crashes on launch.

**The app fetches OTA updates by itself (2026-08-31; never applies them in-session since 2026-10-19).** Publishing is not
delivering: expo-updates' default is check-on-launch, apply on the NEXT cold
launch, so an installed build kept rendering the bundle it launched with until
someone force-quit it twice. That produced a visibly wrong number — the in-app
daily recap showed 2026-08-30 MLB as 7 picks / 2-5 while the Discord recap,
computed from the same rows, had 10-6 / +11.4% with 9 in-play bets. `App.tsx`
now mounts `useOtaUpdates()` (`src/lib/otaUpdate.ts`), which checks at launch
and on every real return from the background and **downloads** what it finds;
expo-updates runs it at the next cold start. It never reloads a running app
(Matt, option A, 2026-10-19: the TestFlight crash was expo-updates aborting on
a fatal JS error right after an in-process reload). The Settings line shows the running bundle's publish date beside the
app version, so "am I current?" is answerable on the device — `APP_VERSION` is
app.json's `version` and never moves on an OTA. Behaviour is pinned by
`mobile/scripts/verify_ota_update.ts` and the wiring by
`tests/test_mobile_ota_self_update.py`.

### TestFlight builds also have a button

`.github/workflows/mobile-build.yml` is restored — the one workflow that survives
the "no more Actions" rule, so you can ship a build from your phone. It is
**`workflow_dispatch`-only (no cron)**, so it bills runner minutes only when you
press the button, and the build runs on EAS's servers rather than the runner.

**Actions tab → Mobile TestFlight build → Run workflow →** pick the branch.

It builds the production profile, submits to TestFlight, and writes the build
link and next steps into a pinned "Latest TestFlight build" issue. On a submit
failure it retries once, then pulls the real error out of the EAS GraphQL API
into that issue — `eas submit` alone only prints a generic "Something went
wrong". Requires the `EXPO_TOKEN` repo secret and the App Store Connect API key
already registered with EAS.

**`BUILD_NUMBER_BASE` in that file only ever goes up.** Apple rejects any upload
whose build number is not strictly higher than the last, and the base is what
guarantees that across the workflow's deletion and restore.

**A run can also fail without building anything.** EAS meters iOS builds per
month per account, and refuses the build once the allowance is gone — after the
project archive has uploaded, so the job reads as healthy until it stops. The
build step classifies that case and the tracking issue says so with the reset
date (2026-08-30 is the run that prompted it: the only verdict on the run was
"Process completed with exit code 1", and the real line was 30 lines up the
log). Nothing in code fixes it — ship JS-only work over the air instead
(`Mobile OTA update (production)`), wait for the reset, or upgrade the plan,
which is Matt's spend decision and not CI's. `mobile/TESTFLIGHT.md` §5 has the
long version.

**The project archive is ~253 MB and does not have to be.** eas-cli archives the
whole repository, not just `mobile/` (2.4 MB of it), because the project sits
inside a git repo. It costs upload time on every build — not builds — so it is
not urgent. Before adding an `.easignore`: the file REPLACES `.gitignore` for
archiving rather than adding to it, so it must re-list `node_modules/`, `.expo/`
and everything else `mobile/.gitignore` covers, or the archive gets bigger and
the build breaks. Not worth attempting while the monthly allowance is spent —
a failed experiment costs a build.

---

## Live monitor

```bash
python -m monitoring            # http://127.0.0.1:8787/ — opens a browser
python -m monitoring --port 9000 --no-open
```

Reads the same Supabase the worker writes to, so it shows the worker's live
traffic as well as anything you run yourself — including when the worker is
down, which is when you want it. Needs `DATABASE_URL` in `.env`; loopback-only
unless you set `MONITOR_TOKEN`. Runbook: `docs/monitoring.md`.

## Tests

```bash
python -m pytest -q tests/            # was tests.yml, on every PR
python -m pytest tests/test_discord_notifier.py -v   # one file
python -m pip install -r requirements-test.txt       # once: pytest, node and Postgres as pip wheels
(cd mobile && python ../scripts/npm.py ci --no-audit --no-fund)   # once: the app's node_modules
```

Losing the PR check is the one real tradeoff in removing Actions: nothing now
runs pytest automatically, so **run it locally before merging.** The suite needs
no `DATABASE_URL` and no API keys — it runs against fakes and fixtures.

---

## Database inspection

`db_report.yml` ran read-only SQL. Use the Supabase MCP from Claude, the Supabase
SQL editor, or `psql "$DATABASE_URL"`.

---

## Local carbon copy of Supabase and GitHub (mike, 2026-11-03)

*"supabase is the SOR, but everything should be a carbon copy on my local as a
backup - everything"*, and *"can you also mirror github on my machine? the full
setup"*. Supabase stays the system of record. This is a second copy on mike's PC
that catches up with Supabase every time it runs.

### What is copied, and where

Everything lives under `C:\Users\micha\Documents\betting_local_copies\`, outside
the repo on purpose: `data/local/` is committed, and
`tests/test_everything_in_supabase.py` fails on a store inside the repo.

| What | Where |
|---|---|
| Every table in every schema that holds app data (`public`, `auth`, `storage`, `realtime`, `vault`, `supabase_migrations`): 227 tables on 2026-11-03 | `supabase_mirror\tables\<schema>.<table>\` — Parquet files plus `manifest.json` |
| The schema, every run: tables, constraints, indexes, views, functions, triggers, RLS policies, grants, sequences, types, extensions, publications | `supabase_mirror\schema\<run time>\*.sql`, with `all.sql` in order; `LATEST.txt` names the newest |
| Every storage object (the `social-post-media` bucket: 18 objects, 3.4 MB on 2026-11-03), each checked against its stored size and md5 | `supabase_mirror\storage\<bucket>\` |
| The exact-count check of the last run, local against Supabase, per table | `supabase_mirror\verify\<run time>.txt` |
| Each GitHub repo the gh login reaches under `MJACode` and `malkatrazz`, as a full mirror: every branch, tag and pull-request head | `github\<owner>\<repo>.git` |
| Each repo's issues, pull requests, every comment, review and review comment, labels, milestones, releases and their files, workflows and recent runs, deployments, settings, branches, and the names of Actions secrets and variables | `github\<owner>\<repo>.meta\*.json` |
| What GitHub refused to show, item by item, with the HTTP status | `github\<owner>\<repo>.meta\_export_report.json` |
| Run logs | `logs\` |

A table's `manifest.json` holds its row count, key columns, watermark (the
last key copied), when every range was last confirmed against the server, and
its bytes on disk. `python local_mirror.py status` prints them all without
touching the database.

Not covered, and why:
- **A private storage bucket.** Today's one bucket is public, so its files
  download over plain HTTPS. A private bucket needs `SUPABASE_SERVICE_ROLE_KEY`,
  which is not in the local `.env`. The script uses it if it is ever added, and
  otherwise lists each such object as not covered.
- **Secret VALUES.** GitHub never returns them, and `vault.secrets` is copied as
  stored, which is encrypted with a key Supabase keeps outside the database.
- **The `auth` tables hold password hashes and session tokens.** They are copied,
  because that is what a full backup is. They are on this disk.

### How a table catches up

A table is split into chunks. Each chunk is one file holding every row whose
primary key falls between the previous chunk's last key and its own. Each chunk
remembers its row count and a fingerprint of its rows (a hash Postgres computes
in the same read that returns them).

- **Tables under 2 million rows**, the 14 tables with no primary key, and
  `latest_odds` and `latest_prop_odds` (whose rows are almost all replaced
  between runs) are copied whole every run, then swapped in.
- **The bigger tables** (`player_prop_odds`, `odds`, `nfl_odds_history`,
  `picks_log`, `kalshi_game_markets`, `nba_pbp`, `kalshi_prop_ladders` on
  2026-11-03) are caught up. New rows past the last key are added. Every chunk's
  row count is compared with Supabase's, which finds rows the odds prune deleted.
  The fingerprints of the newest 40 chunks (where odds get marked in play) and of
  the oldest-checked seventh of the rest are compared too, which finds edited
  rows. A chunk that differs is copied again. Run daily, every chunk's
  fingerprint is re-checked about once a week.
- None of those big tables has an `updated_at` column, so the fingerprint is how
  an edit is found.

### Load on production

There is one database, and it serves live scoring. The copy reads through one
connection, and every read is its own read-only transaction with a 60-second
limit. A read is at most 50,000 rows and about 32 MB, taken in primary-key
order, with a short pause between reads. The copy waits while more than 6
other queries are running. It does not read at 10:00-10:50 UTC (the 6am ET
pipeline) or at minutes :15-:27 of each hour from 11:00 to 22:00 UTC (the
hourly refresh). It never writes to the database. An interrupted run picks up
where it stopped.

### Running it by hand

```powershell
# One pass of both (what a schedule would run):
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\micha\Documents\betting_local_copies\bin\local_mirror_run.ps1

# The database alone, or a few tables:
python C:\Users\micha\Documents\betting_local_copies\bin\local_mirror.py run
python C:\Users\micha\Documents\betting_local_copies\bin\local_mirror.py run --only public.picks --skip-schema --skip-storage

python ...\local_mirror.py status    # what is on disk, no database
python ...\local_mirror.py verify    # exact counts, local against Supabase
python ...\local_mirror_github.py    # GitHub alone
```

`DATABASE_URL` is read from this checkout's `.env` when the run starts. It is
never printed, and errors in the log have database addresses removed. GitHub
access comes from the `gh` login; the token is never written to a file or a
remote URL.

The scripts run from `betting_local_copies\bin\`, a copy outside the repo, so
a worktree being removed cannot break a run. Each wrapper run first replaces
that copy with `scripts/local_mirror*.py` from `origin/master` of this checkout
when they exist there, so a merged fix reaches the next run.

### Restoring one table

Restore into a NEW table first and compare, never straight over production.

```powershell
# 1. The table's rows as a CSV that Postgres reads back exactly:
python ...\local_mirror.py export-csv --table public.picks --out C:\Temp\picks.csv
```
```sql
-- 2. An empty copy of the table, then load it:
CREATE TABLE public.picks_restored (LIKE public.picks INCLUDING ALL);
\copy public.picks_restored FROM 'C:/Temp/picks.csv' WITH (FORMAT csv, HEADER true)
```

If the table itself is gone, its `CREATE TABLE` is in the newest
`schema\<run time>\04_tables.sql`, and its constraints and indexes in `05_` and
`06_`. To read a table in Python without restoring it: `pyarrow.parquet` over
the files its `manifest.json` lists (`TableDir.read_rows` in the script does
this). Numbers stored as Postgres `numeric` are kept as exact text, and every
other type that has no exact Parquet equivalent (json, uuid, arrays) is kept
as its Postgres text.

### The schedule: daily at 00:30, registered 2026-11-03

The task `BettingModel\LocalMirror` exists on mike's PC (read from Task
Scheduler on 2026-11-11: registered 2026-11-03 18:37, one daily trigger at
00:30 local time, which is 05:30 UTC in winter and 04:30 in summer). That is
after the evening games, with about five hours before the 6am ET pipeline
window, which the run waits through if it is still going. It ran every night
from 2026-11-04 to 2026-11-10, about 75 minutes a night
(`logs\supabase_*.log`).

**It runs only while mike is signed in to Windows.** On 2026-11-10 Windows
Update restarted the PC at 10:29pm and again at 10:35pm ET; nobody was
signed in from 10:29pm until 8:17am (System log, Winlogon events 7002 and
7001), so the 00:30 run of 2026-11-11 never started, and signing in did not
start it either. It was started by hand at 8:39am (`schtasks /Run`) and
finished at 11:41am ET with no table failed.

**Since 2026-11-11 it also starts two minutes after mike signs in** (mike:
"yes on backup"). The task holds two triggers, the daily one and a sign-in
one for `MAHOME\micha`; a start while a run is going is ignored
(`MultipleInstances = IgnoreNew`), and a second run would exit on the lock
file anyway. The sign-in trigger had not fired yet when this was written:
the first sign-in after a restart is where to look for a new
`logs\supabase_*.log`. It still does not wake a sleeping PC, and a restart
with nobody signing in for days still skips those nights.

```bat
:: Register (runs as you, only while you are logged on):
schtasks /Create /TN "BettingModel\LocalMirror" /SC DAILY /ST 00:30 /RL LIMITED /F /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Users\micha\Documents\betting_local_copies\bin\local_mirror_run.ps1"

:: The sign-in trigger was added in PowerShell, not by the line above:
:: New-ScheduledTaskTrigger -AtLogOn -User MAHOME\micha, Delay PT2M, then
:: Set-ScheduledTask -Trigger with both triggers. Running the /Create line
:: again with /F replaces the task, so add the sign-in trigger again after it.

:: View it, and when it last ran:
schtasks /Query /TN "BettingModel\LocalMirror" /V /FO LIST

:: Run it now:
schtasks /Run /TN "BettingModel\LocalMirror"

:: Remove it:
schtasks /Delete /TN "BettingModel\LocalMirror" /F
```

A run started while another is still going exits at once: one run holds a
lock file in `supabase_mirror\`, and Windows releases it if the run dies.

---

## First-time setup (moved from CLAUDE.md §7, 2026-08-30)

The original bootstrap sequence, kept verbatim. Nothing here runs on a
schedule; it is what you run against an empty database.

```bash
# First-time setup (do once)
python -m data.db_setup
python -m data.ingestors.sbr_loader --sport MLB
python -m data.ingestors.sbr_loader --sport NHL
python -m data.ingestors.mlb_stats_ingestor --backfill 2019 2024
python -m data.ingestors.nhl_stats_ingestor --backfill 2019 2024
python -m data.ingestors.mlb_stats_ingestor --backfill-pitchers 2019 2025
python -m data.ingestors.mlb_stats_ingestor --backfill-bullpen 2019 2025
python -m data.ingestors.weather_ingestor --backfill 2019 2025
python -m models.trainer --all
python -m models.backtester --all --season 2024

# Daily run (scheduled at 6:00 AM)
python run_pipeline.py

# Individual steps
python run_pipeline.py --step injuries
python run_pipeline.py --step odds
python run_pipeline.py --step mlb_stats
python run_pipeline.py --step weather
python run_pipeline.py --step scoring
python run_pipeline.py --step settle

# Preview picks without writing to DB
python run_pipeline.py --dry-run

# Launch dashboard
# streamlit and plotly are NOT in requirements.txt -- they are the only
# packages nothing outside dashboard/ imports, and they were costing the
# Railway worker ~176 MB of image for nothing. Install them alongside:
pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py
```

---

## The DraftKings direct live feed — runs HERE, not on Railway

mike, 2026-08-31: *"1) My machine."*

**Why it cannot run on the worker.** Probed 2026-08-31 from Railway (egress
`152.55.177.9`) with `impersonate=chrome124 + cookie-bootstrap` — the exact
configuration that collected 6,214 quotes over 16 hours from this machine —
DraftKings returned **403 in 10-40ms** on both hosts. That timing is an edge
refusal: the request never reached an application that could have asked for a
cookie. Same code, same fingerprint, same session handling, different address.
`#293` concluded the block was a TLS fingerprint rather than an IP; that was
true from a residential connection and does not hold from a datacentre.

`RUN_DK_DIRECT_FEED` stays **0** on Railway. That flag gates the SCHEDULER job
only — running the module directly here ignores it entirely.

### The command

```bash
# From the repo root, with .env present (it needs DATABASE_URL).
python -m data.ingestors.dk_direct_feed --sports MLB --minutes 480
```

**Use a `--minutes` that covers the whole slate.** The default is 60 because on
the worker a supervisor cron relaunches the job every 10 minutes; on this
machine nothing does. A feed that quietly exits after an hour while games are
still live is the same failure shape as the midnight blind spot — invisible,
because an empty board and a stopped feed look identical. 480 covers an evening
slate from first pitch to the last west-coast final.

Add `--dry-run` to watch it parse without writing.

### What you should see

```
dk_direct: 96 passes, 1240 quotes, 310 written, 12 unmatched, 0 errors
```

- **written** is FIRST-SEEN quotes, not polls. An unchanged number is a no-op,
  so this counts line and price MOVES.
- **unmatched** is DK events with no unique game in our schedule — futures,
  props and anything whose teams did not resolve. A few is normal; all of them
  means the team map or the slate dates are wrong.
- **A run that writes nothing logs at WARNING**, deliberately, because a feed
  that stopped and a slate that is quiet produce the same silence otherwise.

### Where the rows go, and how to undo them

`odds`, as `bookmaker='draftkings'`, `snapshot_type='in_play'`,
`source='dk_direct'` — the same book and vocabulary the aggregator uses, so the
live scorer and `_best_live_price` pick them up with no code change.

```sql
-- complete rollback
DELETE FROM odds WHERE source = 'dk_direct';

-- did it land?
SELECT count(*), min(created_at), max(created_at)
  FROM odds WHERE source = 'dk_direct';
```

**One semantic difference worth knowing.** For aggregator rows `snapshot_at` is
the book's own publish clock. DK's league feed carries no per-market publish
stamp, so for these rows it is OUR clock at read time. At a 5s cadence that
clears the 30s freshness gate by observation rather than by the book's
assertion. The bovada feed does not have this caveat — it publishes
`lastModified` and uses it.

### NCAAB in-play: DraftKings' own board (`dk_live_board`)

mike, 2026-11-12: *"This is live betting ... This needs to be as close to Real
time as possible."* The three NCAAB in-play models decide on DraftKings' own
board, read from here every second: the line, and DraftKings' score and clock
from the same read. The worker's NCAAB loop reads what this writes and decides
and posts within seconds; without it the loop falls back to the odds provider
and ESPN (minutes).

```bash
# From the repo root, with .env present (it needs DATABASE_URL).
python -m data.ingestors.dk_live_board            # runs while games are live, exits 45 min after the last
python -m data.ingestors.dk_live_board --dry-run  # read and print, write nothing
```

It writes `dk_live_reads` (a row per game each time its score or a line
changes) and `dk_live_feed` (every read). The worker trusts the rows only while
`dk_live_feed.last_read_at` is under 8 s old, so this machine off, asleep or
refused means the slow path, never a bet on an old line.

```sql
-- is it reading?
SELECT sport, last_read_at, ok, live_events, matched, detail FROM dk_live_feed;
```

`matched` below `live_events` means a DraftKings game did not resolve onto our
schedule; the log names it. It reads every second while a game is live (mike:
*"can it run even faster"*); a refusal doubles the gap, up to 5 s, and a quiet
minute halves it back. Five refusals in a row back the feed off two minutes
(this address is the one DraftKings would block).

**The schedule: every minute 11am-3am ET, registered 2026-11-12** (mike:
*"yes"*). The task `BettingModel\DkLiveBoard` runs
`betting_local_copies\bin\dk_live_board_run.ps1` (in the repo as
`scripts/dk_live_board_run.ps1`) every minute from 11:00 for 16 hours, and two
minutes after sign-in. A start while a run is going is ignored
(`MultipleInstances = IgnoreNew`), and a feed already running holds
127.0.0.1:47231, so a second one exits at once. The launcher puts its own
worktree, `C:\Users\micha\Documents\bm-live-feed`, on origin/master before
each start, so what runs is always master and never another session's branch.
Until the feed is merged and its tables exist it logs one line and exits. Like
the backup task, it runs only while mike is signed in to Windows. Log:
`betting_local_copies\logs\dk_live_board_<date>.log`.

```bat
schtasks /Query /TN "BettingModel\DkLiveBoard" /V /FO LIST
schtasks /Run /TN "BettingModel\DkLiveBoard"
schtasks /Delete /TN "BettingModel\DkLiveBoard" /F
```

## Diagnosing a DATABASE_URL that will not authenticate

`python -m scripts.db_url_doctor` — reports the SHAPE of the string and never
the password, so its output is safe to paste anywhere.

```bash
python -m scripts.db_url_doctor                    # reads $DATABASE_URL
python -m scripts.db_url_doctor --connect          # also tries a real connection
echo -n 'postgresql://...' | python -m scripts.db_url_doctor --stdin
```

**Check a candidate string with `--stdin` BEFORE pasting it into Railway.**

Written 2026-08-31, after the Supabase password was reset twice and the pooler
rejected both with the identical `password authentication failed for user
"postgres"`. That message is the same for a wrong password, a password mangled
by URI parsing, an empty password field, and the Connect modal's
`[YOUR-PASSWORD]` placeholder pasted verbatim — so three deploy-and-see rounds
produced no new information. The error text is not a diagnosis; the shape is.

The two traps it exists for:

- **Un-encoded reserved characters in the password.** libpq splits userinfo
  from host at the LAST `@`, so an un-encoded `@` silently moves part of the
  password into the hostname. `#`, `%`, `?`, `/` and `:` corrupt it differently
  and can make the port unparseable. Percent-encode them, or — simpler and
  permanent — **reset to an alphanumeric-only password**, which is the
  recommendation when this bites.
- **`postgres` vs `postgres.<project-ref>`.** The session pooler needs the
  tenant suffix; the direct-connection host takes the bare role. The doctor
  checks the two halves agree, and does not flag the bare role on a direct
  host.

Reading the raw driver error is not enough to tell these apart. Supavisor
strips the tenant suffix before logging, so a *correct* pooler username is
reported as plain `"postgres"` — which reads exactly like a missing suffix and
sent one session down the wrong path. The half that does distinguish them is in
Supabase's own structured log attributes: `tenant` resolved plus
`state: auth_scram_final_wait` means the username was fine and the handshake
failed on the password.

### The sub-10-second path: `--score`

mike, 2026-08-31: *"How do we get instant live odds and a model pick in under 10
seconds end to end?"*

**Measured answer: the pipeline was already sub-10s. The problem was never
speed, it was the moves it never saw.** On the four live picks that fired that
day:

| stage | measured |
|---|---|
| DK publishes → we hold the price | 2.4 – 5.8 s |
| price → pick row written | 0.8 – 1.0 s |
| pick → push and Discord sent | 1.1 – 2.2 s |
| **DK publish → in your hand** | **4.6 – 8.7 s** |

Those four fired because the 30s gate only lets a pick through on a fresh price
— so the picks that happen are, by construction, the fast ones. The gap is the
other seven moves in ten: **the aggregator shows us 29.7% of DK's line changes,
and a pick that is never made cannot be fast.**

`--score` closes that. The feed already knows the exact moment a quote is new,
so it prices those games in the same tick instead of waiting for the next pass:

```bash
python -m data.ingestors.dk_direct_feed --sports MLB --minutes 480 --score
```

**Verified live on 2026-08-31 against 8 in-play games**, four-minute dry run:
32 passes, 640 quotes, **167 distinct new quotes**, 30 scoring runs, 0 unmatched,
scoring in **2.0–2.8s**. Cadence holds a true 5s.

| stage | budget |
|---|---|
| poll interval | 5.0 s worst, 2.5 s average |
| score | 2.0 – 2.8 s |
| notify | ~2 s |
| **total** | **~9.3 s worst, ~6.8 s typical** |

…on ~100% of DK's moves instead of 30%.

**Notifications need two more variables locally.** `DISCORD_WEBHOOK_MLB` and
`DISCORD_WEBHOOK_FREE` are not in the local `.env` (copy them from Railway). If
they are absent the pick is still written and **Railway's loop notifies within
about 5 seconds** — slower, but nothing is lost. That is the degradation, not a
failure.

### What happens when this machine is off

Nothing breaks and nothing needs switching. The Railway loop keeps running; the
`dk_direct` rows simply age past `LIVE_ODDS_MAX_AGE_SEC` and the scorer falls
back to aggregator rows on its own. **Two writers are safe by construction**: a
live delete can no longer remove a `BET` row (`signal_type <> 'BET'` in the
statement), so the laptop and the worker cannot destroy each other's bet of
record even if they interleave.

### Expected consequence, so a jump is not misread as drift

Coverage going from 30% to 100% of DK's moves means more first-crossings, caught
earlier. **Live volume will rise**, and `tracking/live_calibration.py` re-derives
every live cut from the RECENT regime, so its bets/week projections move with
it. That is the machinery working — the same lesson as 2026-08-29, when the
meaning of a cut moved without anyone changing the cut.

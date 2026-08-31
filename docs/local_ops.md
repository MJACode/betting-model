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
git add -f models/saved/<model_id>_2*.pkl
git rm -f --ignore-unmatch models/saved/<old_version>.pkl
git commit -m "Retrain <model_id>" && git push
```

Without that push, `model_registry` points at a `.pkl` that isn't in the repo and
scoring silently skips the model — the session-51 UFC failure.

---

## Backfills and one-off data jobs

```bash
python -m data.ingestors.wnba_stats_ingestor --backfill 2019 2025   # was wnba_backfill.yml
python -m scripts.nfl_odds_backfill <args>                          # was nfl_odds_backfill.yml
python -m data.db_setup                                             # was db_migrate.yml
```

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
```

Losing the PR check is the one real tradeoff in removing Actions: nothing now
runs pytest automatically, so **run it locally before merging.** The suite needs
no `DATABASE_URL` and no API keys — it runs against fakes and fixtures.

---

## Database inspection

`db_report.yml` ran read-only SQL. Use the Supabase MCP from Claude, the Supabase
SQL editor, or `psql "$DATABASE_URL"`.

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

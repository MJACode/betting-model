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

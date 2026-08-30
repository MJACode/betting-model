# Daily system health check + retrain workflow

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 27. Daily System Health Check + Retrain Workflow
### System health check (added 2026-07-04 — after the 80-day bullpen freeze went unnoticed)

`tracking/system_health.py` verifies every API feed / data table is fresh. Runs as the
**final step (Step 12) of the daily pipeline** (after all ingestion + scoring) and on
demand via `python run_pipeline.py --step health-check`. Results are upserted into
**`system_health_checks`** (anon-readable; UNIQUE(run_date, check_name) — re-runs overwrite).

- **CRIT** stale/empty feed → the step returns False → **the daily run fails** — since
  2026-07-19 the daily pipeline runs on the Railway worker, so a red run is visible in the
  Railway deploy logs (not GitHub mobile; a manually-dispatched break-glass Actions run
  still shows RED there). The "how's the system?" Supabase query below works the same
  either way. CRIT checks: DK odds snapshot, MLB team stats, bullpen
  workload, weather, player game log, final scores landing (≥2 missing older than
  yesterday = dead ingest job), picks scored today.
- **WARN** = degraded but not pick-blocking: prop odds, pitcher stats, injuries, lineups,
  umpires, public betting, WNBA/NBA box-score logs (the local Task Scheduler job),
  golf odds, missing model artifacts, settlement lag.
- **Cadence-aware:** every sport's checks gate on that sport having games in the window —
  NBA in July, UFC midweek, golf off-weeks are SKIPPED, never false alarms.
- `KNOWN_UNTRAINED` in the module lists config models intentionally without artifacts
  (F5 O/U+RL, NHL/WNBA/NBA totals+spreads, the 5 golf models) — update it when one trains.

### Pipeline-observability checks (added 2026-08-27 — after the refresh pass died silently for 3 days)

The checks above all measure **data freshness**, and the daily 6am pipeline continues past
step failures — so when a `NameError` aborted every *hourly* pass at step 9 of 24 (8/24-8/27),
the daily run kept the data fresh and **every check stayed green through a three-day outage**
in which no signal was captured, no Discord post or mobile push was sent, and nothing settled
intraday. Three additions close that gap, and the health check now runs on **every refresh
pass**, not just the daily one:

| check | severity | catches |
|---|---|---|
| `refresh_pass_completion` | CRIT | no pass finished in 90 min inside the 7am–midnight ET window; or a run that started >2h ago and never finished (hang / OOM / killed worker) |
| `refresh_pass_steps` | CRIT / WARN | a step failing in **all** of the last 3 passes = a real break (CRIT, names the step); failing in only some = flaky upstream (WARN) |
| `signal_delivery` | CRIT | a signal was locked but never delivered — uses the notifier's own predicate (same thresholds join, same `:early` exclusion) so the two cannot disagree about what counts as postable |

Backed by **`pipeline_runs`** (one row per pipeline invocation, written by
`tracking/run_ledger.py`). Before this, *nothing* recorded that a pass had run — the only
evidence was an absence of side-effects, which is exactly why the outage was invisible. A
pass that starts and never finishes leaves `finished_at` NULL, which is how a hang becomes
visible rather than silent.

Load-bearing details:
- **The ledger creates its own table** (`CREATE TABLE IF NOT EXISTS` on each `start`). The
  Supabase MCP is read-only and `setup_database()` only runs at first-time setup, so
  without this the feature would need a manual migration before it did anything.
- **Every ledger call swallows its own exceptions and the CLI always exits 0.**
  Observability must never be able to break the thing it observes — verified by test.
- **The health check runs as a step, i.e. before the pass calls `finish_run`.** So the first
  pass after this ships has a started row and no finished one; that reports SKIPPED, not a
  failure.
- `refresh_pass_steps` ignores `run_kind='daily'` — the daily pipeline's failure semantics
  are different (it continues past failures by design).

**Claude mobile query (add to the Betting project — "how's the system?"):**
```sql
SELECT check_name, status, severity, detail, latest_seen
FROM system_health_checks
WHERE run_date = '{today_et}'
ORDER BY CASE severity WHEN 'CRIT' THEN 0 ELSE 1 END,
         CASE WHEN status IN ('STALE','EMPTY','ERROR') THEN 0 WHEN status='OK' THEN 1 ELSE 2 END,
         check_name;
```
Zero rows = the daily pipeline hasn't run yet for that date.

### Retrain Model workflow (`.github/workflows/retrain_model.yml`)

Manual model retrains from GitHub UI/mobile — no local machine needed. Actions →
**Retrain Model** → Run workflow with `model_id` (+ optional `seasons` /
`holdout` / `trials` overrides). Trains against Supabase (trainer registers the
new version + deactivates the old), then **commits the new .pkl to master and
removes the superseded ones** so Actions scoring can load it (the session-51 UFC
lesson). One retrain at a time (concurrency group). If it fails after the Train
step, model_registry already points at an uncommitted pkl — re-run the workflow.

**Planned first use:** after the bullpen catch-up lands (first post-merge daily run),
retrain `mlb_over_under` **including 2026** to fix the summer-drift anchoring:
model_id `mlb_over_under`, seasons `2019 2020 2021 2022 2023 2024 2026`, holdout `2025`.
(2026 training rows need 2026 bullpen data — don't dispatch before the catch-up runs.)
Then re-evaluate the pause (`docs/thresholds.md`). `mlb_moneyline` / `mlb_runline` also consumed the
frozen bullpen features all season — consider the same 2026-inclusive retrain for them
once O/U validates.

---

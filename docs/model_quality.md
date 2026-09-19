# Daily model-quality monitor

Ops health (`tracking/system_health.py` / `system_health_checks`) catches
stale feeds and pipeline failures. It does **not** catch betting-quality
failures: a model going one-sided on a slate, public-fade concentration,
CLV/ROI collapse versus a recent baseline, or a sudden spike in BET volume
or unit exposure.

This monitor is that half. It is **report only** — it never pauses a model,
never changes a unit size, and never fails the betting pipeline. A pause
stays a human / Model Performance call (`config.PAUSED_MODELS` +
`Updated-By:`).

Code: `tracking/model_quality.py`. Table: `model_quality_checks`.

## How to run

Any operator, any tool — the same three entry points as `health_check`:

```bash
python -m tracking.model_quality                 # today ET; exit 1 on CRIT
python -m tracking.model_quality --date 2026-09-19
python run_pipeline.py --step model-quality      # observe-only, always exit 0
```

On the Railway worker:

| Path | When |
|---|---|
| Daily pipeline Step 13 | 6:00am ET, after scoring + health. Observe-only. |
| Scheduler job `model_quality` | 11:00am ET, after morning refresh passes have booked more of the slate. |
| Worker job `model_quality` | On demand. Enqueue via `jobs/declared_jobs.json` or `python -m tracking.job_queue --enqueue model_quality`. |

Kill switch for the 11:00am cron only: `RUN_MODEL_QUALITY=0` (redeploy).
The daily step and the job type still run.

A CRIT finding is **visible** (ERROR log + a `FLAGGED`/`CRIT` row). It does
not fail the daily or a refresh pass. The dedicated CLI exits 1 so a
hand-run is readable. The job runner records `ok=false` in `worker_jobs`
and does not raise.

## Checks

Every registered sport/model that has today's open BETs or recent settled
BETs is scanned. Nothing is MLB-only. VOID rows (`condition_status='VOID'`)
are excluded. `RECORD_EXCLUSIONS` is applied to settled windows.

| `check_name` | What | WARN | CRIT |
|---|---|---|---|
| `slate_concentration` | Today's open BETs on one `model_id` pile the same side (over / under / home / away / yes / no) | ≥5 BETs, ≥85% one side, enough distinct games | 100% one side, ≥6 BETs, slate large enough (the all-unders fade case) |
| `public_fade_risk` | Those BETs are fading a public pile, and they pile one side | ≥85% look like fades and share a side | 100% fades, one side, ≥6 BETs. Fade-style = `fade` in `model_id` (any sport). Other models: `public_bet_pct` ≤40 (minority side) or ≥70 (publisher stamped the opposite pile) |
| `clv_degradation` | Settled BETs with `clv_method` in (`no_vig`,`zero_vig`) — last 14 days vs the prior 28 | recent mean CLV ≤ −1.0pp **and** ≥1.5pp worse than baseline (n≥15) | recent mean ≤ −2.0pp **and** beat-rate < 40% (n≥20) |
| `roi_collapse` | Same windows; units = `profit_flat / 100` gated on a non-NULL price (§6) | recent ROI ≤ −15% **and** ≥10pp worse than baseline (n≥20 priced) | recent ROI ≤ −25% **and** hit-rate < 40% |
| `volume_spike` | Today's BET count / `recommended_bet/100` vs that model's median of the last 14 days that had BETs | ≥3× median, ≥6 BETs today | ≥5× median, ≥6 BETs today |

A model with too few rows is `SKIPPED`, not a pass. Re-runs **upsert**
(`UNIQUE(run_date, check_name, model_key)`).

## How to read the table

Today's findings (any operator, Claude mobile, Discord, Grok Bot):

```sql
SELECT run_date, check_name, model_key, sport, status, severity, detail, metrics
FROM model_quality_checks
WHERE run_date = '{today_et}'
  AND status NOT IN ('OK', 'SKIPPED')
ORDER BY CASE severity WHEN 'CRIT' THEN 0 ELSE 1 END,
         model_key, check_name;
```

Zero rows with `status` not in (`OK`,`SKIPPED`) means the monitor ran and
found nothing to flag — or it has not run yet. Distinguish those:

```sql
SELECT COUNT(*) AS rows, MAX(created_at) AS last_write
FROM model_quality_checks
WHERE run_date = '{today_et}';
```

`status` is `OK` | `FLAGGED` | `SKIPPED` | `ERROR`. `severity` is `WARN` |
`CRIT` (the finding's severity; OK/SKIPPED rows still carry the check's
design severity). `metrics` is a JSON object (JSONB in Postgres).

Anon/authenticated hold SELECT. The pipeline writes as the table owner.

## What this is not

- A pause or unpause. Nothing autopauses (CLAUDE.md §1b).
- A unit bump or a threshold move.
- A replacement for `system_health_checks`. Freshness stays there.
- A replacement for the Monday calibration sweep
  (`docs/probability_calibration.md`) or the 250-bet threshold review.

Related: [`health_checks.md`](health_checks.md), [`clv.md`](clv.md),
[`mlb_total_public_fade.md`](mlb_total_public_fade.md),
[`cloud_worker.md`](cloud_worker.md).

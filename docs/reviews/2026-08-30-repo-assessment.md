# Repo assessment — intent, model quality, operations, infrastructure

> Deep read of the whole repo on 2026-08-30, requested by Matt.
> **Analysis only — nothing in this review was changed.** Every recommendation
> is a proposal, not a shipped edit.
>
> **Verification boundary.** The Supabase and Railway MCP connectors are not
> authenticated in this session (non-interactive, so the OAuth flow cannot run),
> so no production number below was independently checked. Every pick count, ROI
> and calibration figure is *as documented in the repo*. Section 7 names what
> would close that gap. The simulations in §1 and §4.8 were run here and are
> reproducible.

---

## 0. The verdict in one paragraph

This is a serious, unusually self-aware system, and the engineering discipline
around **data integrity** is better than most funded quant shops: the leakage
guards, the pick-lock rule (§1c), the `picks_log` audit backstop, the pause
discipline, and the NCAAF search harness are all real and all hard-won. The
weakness is not care — it is **statistical power**. Nearly every live threshold
was chosen by taking the best-performing cell of a ~187-cell grid, on samples of
15–50 bets, from the same data the cut is then justified with. Section 1
quantifies what that procedure returns when the model has *no edge at all*, and
the answer is roughly the same as the numbers currently being shipped on. That
one issue outweighs everything else in this document.

---

## 1. THE HEADLINE — the 10% ROI bar sits at the noise floor

`config.PAUSED_MODELS` records the governing rule (2026-06-21):
*"Per Matt, surface only models that can clear 10% ROI."*

`docs/thresholds.md` then justifies live models with: `mlb_moneyline` +29.5% on
27 bets, `mlb_prop_batter_runs` +24.6% on 40, `mlb_prop_batter_rbi` +14.8% on
30, `mlb_f5_moneyline` +9.86% on 105, `mlb_prop_batter_tb` +6.9% on 24,
`mlb_prop_batter_walks` +37.0% on 18, `mlb_live_total_runs` +27.9% on 17.

### What the sweep returns on a model with ZERO edge

Simulated using the **actual grid** from `scripts/mlb_runline_sweep.py:248-249`
(17 prob floors × 11 edge floors = 187 nested cells), on a universe of scored
picks whose true win rate is exactly **52.38%** — break-even at −110, i.e. no
edge whatsoever — taking the best cell that clears the minimum-bet floor:

| universe of scored picks | min bets/cell | median "best cut" ROI | 90th pct |
|---|---|---|---|
| 300 | 25 | **+18.8%** | +37.5% |
| 300 | 50 | **+14.2%** | +28.1% |
| 800 | 25 | **+13.2%** | +27.3% |
| 800 | 50 | **+12.3%** | +25.0% |
| 2,000 | 25 | **+8.8%** | +18.7% |
| 2,000 | 50 | **+8.4%** | +17.5% |

**A model with no edge produces a "+8% to +19% best cut" as the typical outcome
of this exact procedure.** The 10% bar is not a filter — at these sample sizes
it is approximately the *median of the null*. Most cited per-model records sit
at or below what a coin flip returns after the same sweep.

This does not prove the models are worthless. It means **the sweep cannot tell
the difference**, and the repo is currently reading selection noise as evidence.
The docs half-know this — `docs/thresholds.md:71` says outright *"In-sample
tuning on small samples — forward ROI will regress"* — but cuts derived that way
are still the live cuts.

### The plateau guard is real, and it is not enough

Full credit: `plateau_score()` (`scripts/mlb_runline_sweep.py:276-296`) requires
the eight neighbouring cells to also be positive, and CLAUDE.md §7 promotes it
to a standing rule. In the same simulation, a **pure-noise** best cell passes
"all 8 neighbours positive" only **19–24% of the time** — a genuine 4–5×
reduction in false positives, and the single best methodological decision in the
repo.

But 20% is still 20%. Across ~44 unpaused models, **roughly nine would clear the
plateau test on noise alone.** The guard turns a coin flip into a 1-in-5 shot,
not into evidence.

### Recommendation — the highest-value change available

1. **Print the null next to every cut.** Bake the simulation above into the
   sweep scripts: for each candidate cell, report the median best-cut ROI a
   zero-edge model of that universe size would have produced. A cut is
   interesting when it beats *its own null*, not when it beats zero.

   *One caveat on the table above, and the fix for it.* The numbers assume a
   neutral universe — (prob, edge) drawn uniformly — so they approximate rather
   than reproduce any specific model's pick distribution. The in-script version
   should not simulate the universe at all: **keep each model's actual scored
   (prob, edge) rows and replace only the outcomes with Bernoulli(breakeven)
   draws.** That is a parametric bootstrap of the model's own universe, it
   inherits the real correlation structure between cells for free, and it makes
   the null exact for the model being swept rather than indicative.
2. **Promote CLV to a required gate for every sport.** CLV is the one measure
   immune to this bias — it does not depend on outcomes, so it cannot be
   inflated by picking the lucky cell. The machinery already exists
   (`tracking/paper_tracker._closing_dk_odds`, `tracking/opening_signals.py`).
   It is used as a gate in exactly one place — the NCAAF search — and
   `docs/thresholds.md` mentions CLV **zero times** across every other model.
3. **Adopt the NCAAF harness as the house standard.** `scripts/ncaaf_search/`
   already encodes the right protocol (`validate.py:1-20`): expanding-window
   walk-forward, *"NEVER random k-fold"*, a `market_only_sanity` check that must
   score ~50% or the harness is declared leaky, a `LEAK_SUSPICION_WR = 0.55`
   tripwire that treats a *good* result as a bug report, per-season consistency,
   and CI vs breakeven. **The right tool is already built. It has been pointed
   at one sport.** That asymmetry is the biggest available upgrade in the repo.

---

## 2. Model quality — everything else

**Sound, and worth keeping.** The season-based holdout
(`config.py:1078-1163`, every sport `test_season: 2025`) is the correct design
and is *not* the season being bet. The Kelly implementation is mathematically
exact — `f = k·(p−IP)/(1−IP)` at `models/scorer.py:118-146` is precisely full
Kelly at the offered price, scaled by the multiplier. Post-deployment
calibration (`models/probability_calibration.py:162-215`) is genuinely strong:
Platt on logits with a time split, refusal below 150 graded picks, refusal when
the map hurts held-out data, scoped to the active model version.

**Findings, ranked:**

1. **The go-live gate is advisory only.** ≥50 settled picks / positive flat ROI
   / CalErr ≤5% is computed inside a printed CLI summary
   (`models/backtester.py:67-69`, `:876-892`) and consumed by *nothing* in the
   scoring or pause path. Live models documented below it: `mlb_moneyline`
   (27 bets), `mlb_runline` (19, cut "carried over UNVALIDATED"),
   `mlb_prop_batter_walks` (18), `mlb_prop_pitcher_outs` (15),
   `mlb_live_total_runs` (17), both NCAAF live models (10, thresholds
   "explicitly unvalidated" — `docs/live_betting.md:188`). On the calibration
   leg, `docs/probability_calibration.md:127-136` measures `mlb_moneyline` at
   **+10.5pp overconfident** on live picks — more than double the 5% gate — and
   it is live.

2. **Tenth-Kelly is accidentally absorbing the calibration error.** At the
   `mlb_moneyline` cut (p ≥ 0.72) with the documented +10.5pp bias, true p is
   ~0.615. Tenth-Kelly on the *stated* probability stakes 4.12% of bankroll;
   true full Kelly at the real probability is 19.2%. So the bet is 0.22× true
   full Kelly — safe — but **2.2× true tenth-Kelly**. For `mlb_live_total_runs`
   at p ≥ 0.65 it is **6.0× true tenth-Kelly**. The conservatism is real but
   unintentional. If calibration is ever fixed without revisiting
   `KELLY_MULTIPLIER`, sizing stops being correct-by-accident.

3. **Optuna tunes on shuffled `StratifiedKFold` over pooled seasons**
   (`models/trainer.py:83, 123, 563, 590, 696`). Season-to-date aggregates leak
   across folds — `home_win_pct`, `d_run_differential`, `runs_last_5/10`,
   bullpen/starter ERA (`features/feature_engine.py:60-145`), the `season_*_avg`
   family (`features/prop_feature_engine.py:109-232`). A late-season training
   row's win% encodes the outcome of an earlier same-season validation game. The
   final 2025 holdout is **clean**; what is contaminated is the hyperparameter
   *selection signal* and the CV Platt fit (`trainer.py:280-285`). Fix:
   `GroupKFold(groups=season)`. Note the repo's own best doc already forbids
   this (`ncaaf_search/validate.py:4`) — the main trainer does not follow it.

4. **`holdout_roi` is a hardcoded `0.0` for every classifier.**
   `models/trainer.py:474-490` returns zero unconditionally behind a
   "placeholder" comment, and the training log prints `ROI=0.000` as though
   measured. Any registry-driven "positive flat ROI" check reads a fabricated
   number. One query sizes the blast radius (§7).

5. **Two models were retrained with the live season in-sample.**
   `mlb_over_under` and `mlb_runline` trained on "2019-2024+2026, holdout 2025"
   — the holdout is chronologically *before* part of the training data.
   `docs/thresholds.md:33` states "2026 now in-sample", which is honest, but the
   holdout metric from that run is not interpretable.

6. **Backtest ROI is synthetic-odds where DK history is absent**
   (`models/backtester.py:252-305, 338`), and `docs/live_betting.md:95` states
   there is *no* ROI backtest for live models at all. "Positive holdout ROI" can
   mean "positive at prices nobody offered" — which is exactly the covariate
   shift the WNBA O/U pause note diagnoses.

7. **`mlb_prop_batter_hr` is live while its own note says every real-odds cut is
   −EV** (`docs/thresholds.md:44`: "maximizes record, not profit (real-odds cuts
   all -EV). Never paused"). A per-model verdict overridden without a stated
   profit basis.

8. **Model artifacts have no recorded library version.** `model_registry`
   (`data/supabase_schema.sql:1033-1045`) stores train seasons and holdout
   metrics but not the sklearn/xgboost version the `.pkl` was written with. See
   §5.2 — this is the other half of the unpinned-dependency risk.

**The pause discipline deserves to be stated plainly as a strength.** 26 of ~69
registered models are paused, with written reasons that name the failure rather
than defend the model: the WNBA props killed after the *retrained* models swept
negative across the entire prob×edge surface; the NCAAF classifiers killed at
AUC 0.49; two live MLB models retired at −34.1% and −39.9% within a day of the
evidence arriving. Killing your own work is the hardest habit in this field and
this repo has it.

---

## 3. The stated strategic premise is ahead of its evidence

CLAUDE.md §1b: *"Live player props are a priority and are treated as a
**proven-profitable** market."*

The repo's own record, as documented:

- **MLB live:** three models. Two **retired** 2026-08-30 at −34.1% (15 bets) and
  −39.9% (14 bets), for overconfidence a threshold could not fix. One survivor,
  `mlb_live_total_runs`, at **17 bets** on a re-cut the doc itself calls "thin
  and in-sample".
- **NFL props:** all **12** models paused (`config.py`, never priced).
- **WNBA props:** 6 of 8 paused.

There is also a gap between the thesis and the implementation. §1b describes
pricing live props *relative to the starting line* to capture in-game flow; what
actually shipped is `mlb_live_total_runs`, a Poisson on remaining runs
(`docs/live_betting.md:30`). The stated thesis has not really been tested yet.

**This is the one item that needs a decision rather than a fix.** "Proven
profitable" is load-bearing — it is why credits, volume and priority flow there.
Either the wording becomes "the priority hypothesis", or the evidence that
justifies "proven" gets named. Flagged, not argued: it is a premise Matt set.

---

## 4. Operational process

**Strong.** `scripts/refresh_pass.sh` is the best-engineered file in the repo:
no `set -e`, every step runs to completion, subshell failures collected via
marker files (`:55-81`), the ledger row closes whatever happened (`:191-194`),
and the pass still exits non-zero — the 3-day NameError post-mortem is encoded
in the mechanism, not just the comments. `tracking/run_ledger.py:113-142`
aborts-and-labels orphaned runs so a killed worker is visible, and every
function swallows its own exceptions ("observability must never break the thing
it observes"). The supervisor pattern for live loops (`scheduler.py:245-278` —
loops exit when idle, a `*/10` cron relaunches, the "max instances" warning
doubles as a heartbeat) gets crash recovery for free. And
`ncaaf_live/feeds/odds_live.py:41-54` declines to price a stale line rather than
guessing — failing safe by refusing to bet is the right default for live money.

**Findings, ranked:**

1. **Worker death has no external alarm.** Every detection surface runs *on the
   thing being monitored*: the health check is a pipeline step
   (`run_pipeline.py:1425`), the monitor is a daemon thread inside the scheduler
   process (`scheduler.py:632-639`), and no ops/alert Discord webhook exists
   (`config.py:85-113`). The one external probe,
   `.github/workflows/monitor-probe.yml:13-17`, has **no `schedule:` trigger** —
   only `workflow_dispatch` and pushes to `claude/**`. Worse,
   `scheduler.py:447-451` uses the default **in-memory jobstore** with
   `misfire_grace_time: 300`, so a restart spanning 5:58–6:06am ET means the 6am
   daily pipeline simply does not run that day. Detection latency for total
   worker death is ~24h, resting on Sentinel — a Claude routine created *today*.
   **Adding a `schedule:` cron to that workflow is the cheapest high-value fix
   in this document.**

2. **The step meta-check excludes the daily run.**
   `tracking/system_health.py:594-596`: `AND run_kind <> 'daily'`. A step dying
   in the 6am pipeline (settle, threshold_sync, results ingest) has no
   meta-check — precisely the shape of the July outage where settle and
   threshold-sync ran dead for a week. CLAUDE.md §7's "empty board vs broken
   pipeline" trap is therefore structurally fixed *for refresh passes* and
   instance-patched everywhere else.

3. **Two of four live credit caps reset on process restart.** MLB is DB-backed
   and correct (`data/ingestors/live_odds_ingestor.py:67-73`). NFL's
   `CreditMeter` is an in-memory dataclass starting at `spent=0`
   (`nfl/live_model/feeds/odds_live.py:47-66`); NCAAF's is per-process
   (`ncaaf_live/feeds/odds_live.py:36-38`). Both are relaunched by a `*/10`
   supervisor, so **a crash-looping worker gets a fresh cap every ten minutes**.
   Separately, the pregame poller's cap counts burn from `api_call_log`, written
   by the monitoring probe (`monitoring/store.py:30,61`) — set
   `PIPELINE_TELEMETRY=0` and the cap reads 0 forever. A spend limit that fails
   open when observability is disabled is the inverse of §7's own rule. Also
   note `cap <= 0` means *uncapped* everywhere, so
   `LIVE_DAILY_CREDIT_CAP=0` is an uncap, not a stop.

4. **`owns()` fails open** (`scheduler.py:211-223`) — an unrecognised
   `SERVICE_ROLE` runs *everything*. APScheduler's `max_instances=1` is
   per-process only, so two containers would run concurrent refresh passes with
   overlapping look-ahead delete windows — the board-emptying hazard
   `refresh_pass.sh:115-119` keeps scorers sequential to avoid. The fail-open is
   well-argued ("a typo must leave the scheduler running everything, never
   nothing") but wants a DB advisory lock behind it.

5. **The only quality gate is currently red.** Measured this session:
   **1,522 passed, 5 failed, 93.2s.** Full triage in §7.

6. **Velocity versus gate.** 262 commits in August alone (~8.5/day), 116 touches
   to `config.py` since April, no CI, no git hooks, no `.pre-commit-config.yaml`
   — and `.github/workflows/mobile-ota.yml:39-43` ships JS to production phones
   on any push to master touching `mobile/**` with **no test gate in the
   workflow**. A 93-second suite not wired to anything means the real gate is
   memory. The FEATURE_MAP KeyError of 2026-08-29 — which killed game scoring
   league-wide for a day — is exactly what a pre-push hook catches.

7. **Two stale comments sit in the money path.** `scheduler.py:172` says the
   live credit cap defaults to "1000/day"; `config.py:944` says **50000** — 50×
   off, and CLAUDE.md §1b exists *because* a stale credit comment already
   mis-scoped an analysis once. The original offender is also still there:
   `nfl/data_ingest/odds_api.py:7` still carries the 20k-quota comment CLAUDE.md
   names by file and line. And `data/ingestors/pregame_line_poller.py:47` claims
   a kill switch is readable "without a deploy", contradicting CLAUDE.md §6 — an
   operator will believe the docstring mid-incident.

8. **The review cadence institutionalises variance-chasing.**
   `docs/thresholds.md` triggers a review every 10 settled picks and demands
   "investigate immediately" on any 5-pick losing streak. Simulated here: a
   **genuinely +EV 58%-win-rate model** — an enormous real edge — throws a
   5-pick losing streak within its first 100 picks **53% of the time**; at 55%
   it is 65%; at break-even, 74%. Across ~44 live models that alarm fires
   constantly on nothing, and each investigation is an invitation to re-sweep
   in-sample — which §1 shows is how noise becomes a threshold. Replace it with
   a CUSUM or a CI-based drift test, or drop it.

---

## 5. Infrastructure, data and repo hygiene

**Strong.** `data/db.py:264-268` tunes TCP keepalives for the session pooler.
The 2.2M-row `player_prop_odds` lookups are indexed `LIMIT 1` point reads
(`models/scorer.py:2381-2391`), and the one real unbounded-scan incident
(`MAX(snapshot_at)` full-scanning 1.5 GB at 7s/call) was found and fixed with a
documented migration (`data/migrations/add_disk_io_indexes.sql:28`). Nearly
every trap in the DB layer and scheduler carries an inline post-mortem with the
date it bit — that documentation culture is a genuine asset.

**Findings, ranked:**

1. **Secrets are clean.** `.env` is not tracked and never was
   (`git log --all --diff-filter=A -- .env "*.env"` → empty), correctly ignored
   (`.gitignore:2-3`), and `.env.example` holds placeholders only. A pattern
   scan over tracked py/ts/js/json/sh/md/sql found nothing real. Caveat: no
   `gitleaks`/`trufflehog` history scan was run — a one-time run is worth doing.
   Nit: `.env.example` still says "Paper Trading Bankroll" and documents
   `BET_EDGE_THRESHOLD=0.03`, both framings CLAUDE.md marks stale.

2. **`requirements.txt` is effectively unpinned against 61 raw pickles.** 28
   requirement lines, exactly **one** `==`. The stated reason (Python 3.14 wheel
   availability) is legitimate, but the consequence is that every Railway
   rebuild can silently bump sklearn/xgboost, and the 61 committed
   `models/saved/*.pkl` are raw `pickle.dump` (`models/trainer.py:378, 945,
   1029, 1149, 1388`) with **no library version recorded anywhere**. sklearn
   does not guarantee cross-version pickle compatibility; failure modes run from
   a load error (CLAUDE.md §7 already documents a month-long silent scoring
   outage from an unloadable artifact) to *silently changed predictions*, which
   is worse. `nfl/requirements.txt` even pins a different floor
   (`scikit-learn>=1.3` vs `>=1.6`). **Fix: keep the `>=` floors for resolution,
   add a `requirements.lock` that the Railway build installs, and write the
   library version into `model_registry` at train time.**

3. **The data still outside Supabase keeps accruing, and its backup is
   manual-only.** `grep backup scheduler.py` returns nothing:
   `nfl/scripts/live_prop_job.sh backup` is a hand-run job, so the 2026-08-28
   rescue was a one-off. Every decision-log line (`nfl/live_model/recorder.py:33`,
   `DECISION_LOG_DIR`, which its own docstring calls the audit of record) and
   every prop snapshot written since sits on **one Railway volume with no second
   copy**. Also confirmed outside: `nfl/data/cards/` and
   `nfl/data/credit_ledger.json` on *ephemeral* disk. And there is no
   `pg_dump`/PITR/export job anywhere in the repo — Supabase's own backup tier
   is the entire durability story for 2.2M+ irreplaceable rows.
   **Scheduling the existing backup job is a small change with a large payoff.**

4. **Three parallel migration mechanisms and no applied-migrations ledger.**
   (i) additive column migrations at setup time (`data/db_setup.py:1308, 1404`);
   (ii) `data/view_migrations.py:38-44`, a hand-curated `ACTIVE_MIGRATIONS` list
   of 5 of the 41 files in `data/migrations/`, run every pass, where "failures
   are logged and **swallowed**" per its own docstring, and files are *removed
   from the list* once applied — so the list is not history; (iii) the other ~36
   applied by hand in the Supabase SQL editor. No `supabase/migrations/`
   directory, no table recording what has been applied. Drift will only be
   discovered when a query fails, and the view mechanism is built to swallow
   exactly that failure.

5. **`DBConnection.executescript` docstring contradicts its code.**
   `data/db.py:196-200` claims "each statement runs in its own savepoint so one
   failure doesn't abort the whole transaction," but the code calls
   `self._conn.rollback()` — a full transaction rollback discarding all prior
   uncommitted statements, then continues. Mostly hidden by idempotent
   `IF NOT EXISTS` DDL; any script mixing DDL and data can partially apply.
   Same layer: no pooling, no retry, no statement timeout, and a regex-based
   SQLite→Postgres translator whose own comments document two production
   outages it caused (`data/db.py:56-66`).

6. **`docs/AGENTS.md` and `docs/agents.md` are both tracked and cannot coexist
   on Windows** — the primary development machine. `core.ignorecase=true`, only
   one materialises on disk, and `git checkout` of either dirties the other in
   an endless flip-flop (**verified this session — the working tree can never be
   clean**). Two consequences: `tests/test_agents_contract.py` fails
   permanently, and **a `git commit -a` would silently overwrite one file with
   the other's contents**, destroying the one-screen version. Fix:
   `git mv docs/AGENTS.md docs/agents_summary.md`. Two minutes, removes a
   permanent booby trap.

7. **~900 MB working tree, 177 MB pack, no LFS.** `nfl/data` is 705 MB of it
   (odds_cache 655 MB across 6,769 tracked JSONs); largest blobs are
   `nfl/data/processed/dev_long.parquet` (35 MB) and two `mlb_prop_batter_sb`
   pickles (34 + 30 MB — the *superseded* 2026-05-13 version is still tracked
   alongside the 2026-06-11 one, contradicting `.gitignore:11`). This is a
   deliberate trade-off — CLAUDE.md calls committing odds_cache its protection
   scheme — but it is unbounded growth in a repo every clone pulls, and
   git-as-backup has none of the integrity verification that
   `nfl_live_prop_snapshots` has (checksummed rows, `--verify`).

8. **The `nfl/` carve-out costs ~17,271 lines of duplicated platform concerns.**
   Its own Odds API client and credit ledger, its own decision recorder (JSONL)
   versus the shared `data/ingestors/live_price_log.py` that CLAUDE.md holds up
   as "the shape", its own `requirements.txt` with divergent pins, its own
   storage plane, its own `RESTORE.md`, and `cwd=nfl/`-dependent execution
   (`scheduler.py:264, :301`). Measured costs so far: the 100k-credit near-loss,
   the `THE_ODDS_API_KEY`/`ODDS_API_KEY` naming seam bridged in
   `scheduler.py:266-268`, the still-present stale quota comment, and publisher
   glue to mirror picks back into the real tables. **CLAUDE.md §1b's "assess a
   change against all models" rule structurally cannot reach code that shares
   nothing** — that is the real cost, and it will keep compounding.

---

## 6. Product surface

**Strong.** The entitlement invariant genuinely holds in code: every gated
surface uses `useEntitlement()` (`LiveScreen.tsx:58-61`,
`PicksHomeScreen.tsx:116`, `PaywallScreen.tsx:69`, `SettingsScreen.tsx:118`),
the one remaining `useSubscription()` caller is display-only with a comment
explaining exactly why, and `mobile/scripts/verify_discord_link.ts:218` asserts
the lib really calls `supabase.rpc('my_access')`. Webhook security is textbook —
HMAC-SHA256 over the raw body, constant-time compare, timestamp tolerance
(`supabase/functions/whop-webhook/index.ts:18-64`). The OTA workflow gates on a
typecheck that diffs against a documented error *set* rather than a count, which
is the repo's own verification standard applied correctly.

**Findings, ranked:**

1. **Responsible gambling and jurisdiction — this is the live exposure.** What
   exists, in the app only: a 1-800-GAMBLER link (`SettingsScreen.tsx:187-188`),
   an opt-in daily exposure cap (`useResponsibleGambling.ts:5-14`), bankroll
   onboarding, a past-performance disclaimer (`PaywallScreen.tsx:321`), a 17+
   rating. What exists nowhere: an in-app **age gate**, any **jurisdiction
   check**, any **self-exclusion/timeout** — and the **Discord channels, free
   picks, email and X publisher carry no RG resources or disclaimer at all**
   (`tracking/discord_notifier.py`; `email/render_picks_email.py:305-306`).
   Meanwhile `mobile/APP_STORE_METADATA.md:48` claims "research and educational
   use only" while the app publishes Kelly stakes and hands off to a DraftKings
   betslip (`ParlayDkHandoff.tsx`, `BetslipBar.tsx`). That claims tension is a
   review risk under App Store guideline 5.3 and an FTC-substantiation risk that
   `BILLING.md:236-240` already half-acknowledges. **Matt's call, but it is the
   broadest gap in the product.**

2. **Two anon-write RLS policies allow destructive writes** (repo SQL; live
   state unverified). `tracked_bets` has anon INSERT *and* anon DELETE
   `USING (true)` (`data/supabase_schema.sql:2201-2204`) — any holder of the
   publishable key can delete every row in the table. `device_push_tokens` has
   anon UPDATE `USING (true)` (`:2173-2176`) — token overwrite for a guessed
   device id. Both should be scoped to the owning device/user.
   Note `data/supabase_schema.sql` is a *partial* mirror (the `picks` anon
   SELECT policy is referenced at `:2443` but its `CREATE POLICY` is absent), so
   live state needs checking (§7).

3. **The paywall has no server-side enforcement** — documented-deliberate
   (`mobile/docs/BILLING.md:225-231`) and latent while billing ships dark, but
   it becomes the top risk the day `BILLING_ENABLED` flips. Related: client
   entitlement fails *open* twice (`mobile/src/hooks/useAccess.ts:29-36, 151`)
   on the stated grounds that "the server-side check is the real boundary
   anyway" — which is currently not true. These must be revisited together.

4. **Never-succeeded notification monitoring covers one `kind` out of five.**
   `tracking/system_health.py:637-690` checks only `kind='discord_signal'`. The
   daily recap, free pick, restatements and mobile push have **no**
   never-succeeded check — the exact CLAUDE.md trap, guarded in one place.

5. **Residual "paper trading" wording in two artifacts** — `email/preview.html:386`
   (a stale rendered file; the generator no longer emits it) and
   `dashboard/app.py:374` ("Paper Bankroll"). Both internal. **Do not confuse
   these with the correct per-model wording** in `TrackRecordScreen.tsx:265` and
   `mobile/src/lib/thresholds.ts:104`, which describes the go-live gate and
   should stay.

6. **The OTA native-config guard has a lockfile blind spot.**
   `.github/workflows/mobile-ota.yml` refuses to publish when
   `mobile/package.json` or `app.json` changed — but the job runs `npm ci` from
   `package-lock.json`, which is not in the guard's diff paths. A lockfile-only
   native-dep bump ships a bundle built against different native modules than
   the installed binary.

---

## 7. The five failing tests

Measured here: `python -m pytest -q tests/` → **1,522 passed, 5 failed, 93.22s**.

| Test | Cause | Verdict |
|---|---|---|
| `test_system_health_checks::TestSignalDelivery::test_undelivered_signal_is_crit` | **an undelivered signal grades `OK` instead of `STALE`/`CRIT`** | **triage first** — this guards the check that exists to catch undelivered signals |
| `...::test_default_channel_covers_every_sport` | same check | as above |
| `test_agents_contract::test_there_is_a_one_screen_summary` | the `AGENTS.md`/`agents.md` case collision (§5.6) | **real** — a repo defect, not a test bug |
| `test_x_publisher::test_both_renderers_are_link_free_and_fit_one_tweet` | `tracking/x_publisher.py:164` uses `strftime("%b %-d")`; `%-d` is a glibc extension that raises `ValueError` on Windows | **platform-real** — works on the Linux worker, crashes on the machine that runs the gate |
| `test_refresh_pass_parallel::test_a_parallel_step_that_fails_is_still_recorded` | bash-array harness reports `TOTAL=0` under Git-Bash on Windows | probably environmental; unproven |

Two things are worth naming beyond the individual fixes.

**The failures cluster in the failure-detection machinery.** Two of five are the
signal-delivery health check; one is the guard that failed parallel steps get
recorded. This is the same class CLAUDE.md §7 has already promoted twice ("a
health check must not gate on the thing that breaks"), and it is currently red.

**The repo's only quality gate is not green on the only machine that runs it** —
structurally identical to the `encoding="utf-8"` incident of 2026-08-30. A gate
that is expected to fail is a gate nobody reads. Either fix the
platform-specific failures or mark them `skipif(sys.platform == "win32")` with a
reason, but do not leave five red.

---

## 8. What would close the verification gap

Nothing above was checked against production. Per CLAUDE.md §1b, the routes and
why each is unavailable here:

- **Supabase MCP** — not authenticated in this non-interactive session, so the
  OAuth flow cannot run. Authorize via claude.ai connector settings (or `/mcp`
  in an interactive session). Then: one query per live model against
  `mv_scored_pick_outcomes` / `v_model_full_outcome_record`, restricted to the
  clean NONE-row windows (2026-05-12→06-25, 2026-08-09→present), replaces every
  documented number in §1–§2 with a measured one;
  `SELECT model_id, holdout_roi, cal_error FROM model_registry WHERE active`
  sizes §2.4 in one line; `get_advisors(security)` settles §6.2.
- **Railway MCP** — same auth gap. Would confirm whether the `SERVICE_ROLE`
  split is actually deployed as two services (§4.4), the Supabase backup tier
  (§5.3), and the live values of `RUN_LIVE_LOOP`, `LIVE_DAILY_CREDIT_CAP` and
  `PIPELINE_TELEMETRY` (§4.3).
- **Matt's machine** — any of the above SQL, run directly.

---

## 9. Recommended order of work

Ranked by value ÷ effort, not by severity.

**Do this week (minutes to an hour each):**

1. **Add a `schedule:` cron to `.github/workflows/monitor-probe.yml`** — removes
   the ~24h blind spot on total worker death. (§4.1)
2. **Rename one of `AGENTS.md`/`agents.md`** — unbreaks the working tree and one
   test, and removes a `git commit -a` data-loss trap. (§5.6)
3. **Fix the three stale comments** — `scheduler.py:172` (50× credit cap),
   `pregame_line_poller.py:47` ("without a deploy"),
   `nfl/data_ingest/odds_api.py:7` (the 20k quota CLAUDE.md already names).
   (§4.7)
4. **Triage the signal-delivery test on the Linux worker** — it guards the
   detection of undelivered signals. (§7)
5. **Drop `AND run_kind <> 'daily'`** from `tracking/system_health.py:596`. One
   line, closes a known-shape hole. (§4.2)
6. **Schedule the existing `live_prop_job.sh backup`** instead of running it by
   hand. (§5.3)

**Do this month (an afternoon each):**

7. **Add `requirements.lock`, install from it on Railway, and record the library
   version in `model_registry` at train time.** Protects 61 artifacts and every
   future deploy. (§5.2, §2.8)
8. **Persist the NFL and NCAAF credit meters** to the DB the way MLB's already
   is, and make `cap <= 0` mean *stop*, not *uncapped*. (§4.3)
9. **Scope the two anon-write RLS policies** to the owning device/user. (§6.2)
10. **Switch Optuna to `GroupKFold(groups=season)`** and retrain one model to
    measure what the shuffled CV was buying. (§2.3)
11. **Add a pre-push hook running the 93-second suite**, and a test gate to the
    mobile OTA workflow. (§4.6)

**The two that actually change outcomes:**

12. **Print the null alongside every swept cut, and make CLV a required gate for
    every sport** — i.e. point the NCAAF harness at MLB. This is the largest
    item in the document and the one that changes what gets shipped. (§1)
13. **Decide the §3 question** — "proven profitable" or "the priority
    hypothesis". Matt's call, not a code change.

**And one thing to consciously not do:** the per-model threshold re-sweeps.
Until §1.1 and §1.2 are in place, every re-sweep on a 20-50 bet sample is more
likely to move a cut toward noise than toward edge. The 116 `config.py` commits
since April are, in aggregate, probably value-neutral at best.

---

*Written 2026-08-30. Analysis only — no code, config, model or threshold was
changed. Files touched: this document, plus the session-log entry in
`docs/sessions/2026-08.md` and its index row in `docs/sessions/README.md`, per
the CLAUDE.md §1b convention. Nothing was committed.*

*One more thing the working tree will show: `docs/AGENTS.md` reports as
modified. That is not an edit — it is the §5.6 defect demonstrating itself.
`AGENTS.md` and `agents.md` cannot both exist on a case-insensitive filesystem,
so whichever one git last wrote, the other reads as dirty; `git checkout` of
either just moves the flag to the other. `agents.md`'s content is what is
currently on disk.*

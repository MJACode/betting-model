---
paths:
  - "data/**"
  - "tracking/**"
  - "monitoring/**"
  - "scheduler.py"
  - "run_pipeline.py"
  - "scripts/**"
---

# Operations

> Loaded only when Claude opens a file matching the paths above, so this costs
> nothing on a session that never touches this area. Rules that govern EVERY
> session stay in CLAUDE.md; the measured story behind each one is in
> `docs/rules_evidence.md`. Split out 2026-09-03 (mike: "this project will only
> continue to grow. How can we ensure we don't lose context?").

How this system fails in production, and what each failure looked like
before anyone noticed it.

- **A LIVE cutoff decays, so re-derive it rather than setting it once.** A
  pre-game model is scored daily against a line that barely moves; a live model
  locks at the first crossing of a market that moves every few seconds. The
  first-signal lock plus 5s polling took MLB live from ~35% of games producing a
  bet to **100%** at an UNCHANGED threshold — nobody moved a cut, the meaning of
  the cut moved. `tracking/live_calibration.py` re-derives every live cut each
  pass, and its verdict is allowed to be "no cut works, retrain or pause".
- **Project volume from the CURRENT regime, not the lifetime average.** A
  threshold chosen off a lifetime average is chosen for a world that no longer
  exists.
- **A retrained model must have its `.pkl` COMMITTED.** The registry row points
  at a path; if the artifact is not in the repo the worker cannot load it and
  the model silently stops scoring. This has cost a month of UFC picks and a
  four-week outage across three MLB prop models.
- **A model in `config.MODELS` with no `FEATURE_MAP` entry raises before the
  artifact is even looked at — and kills scoring for EVERY sport.** A derived
  test asserts the two stay in sync; keep it.
- **A table created at write time must not re-run its DDL on every write, and
  `IF NOT EXISTS` does not make it free.** `CREATE INDEX IF NOT EXISTS` takes a
  SHARE lock and `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` takes ACCESS
  EXCLUSIVE whether or not the object is already there — and **every one fires
  Supabase's `pgrst_ddl_watch`, so PostgREST answers 503 to the whole app while
  it rebuilds its schema cache.** Seven modules did this on every call, costing
  **11.6 hours of database time and ~3,600 forced cache reloads**. Gate every
  write-time ensure block on `data/ddl_guard.schema_is_current`, which fails
  open; `tests/test_ddl_guard.py` is the tripwire. **Judge these statements per
  INVOCATION, not per millisecond.** And **a test scoped to the symptom already
  found is not a tripwire** — the first one missed a whole module.
- **An empty board and a broken pipeline look identical.** Prefer writing a
  "declined, and here is why" row over `return []`. Check
  `pipeline_runs.failed_steps` before blaming thresholds, and `push_sent` before
  believing a notifier ever worked — a `kind` with zero rows has NEVER
  succeeded. **But a `kind` with MANY rows has not necessarily succeeded
  either, and this line used to claim it had** ("nothing is ledgered unless a
  POST confirmed"). That is not true of the push producers: all three ledger
  *regardless of token count*, deliberately, so a signal with no device online
  is not re-detected forever. Measured 2026-09-06 — **1,158 `new_bet` and 578
  `live_signal` rows against ZERO rows in `device_push_tokens`**, i.e. every
  one of those was `messages = []`, `_expo_send` never called, lock_key written
  anyway. No push has ever reached a phone. **So the ledger is evidence a
  signal was CONSIDERED, and the recipient table is the evidence it was SENT —
  check both.** (`docs/push_notifications.md` carries the query.)
- **A health check must not gate on the thing that breaks.** Two checks reported
  SKIPPED for the entire outage they existed to catch, because they keyed off
  data the failing feed produces.
- **A swallowed exception plus a legitimately empty channel is invisible.**
  Where a caller must swallow, test the producer's REAL output through the real
  renderer — a hand-written fixture drifts from the producer exactly as the
  renderer did.
- **A job that times out does nothing, and does it silently.** Judge a query's
  SHAPE, not just its result: a second anti-join added to the odds pruner took
  it from ~80s to a statement timeout, and a pruner that never completes prunes
  nothing while the growth it bounds continues.
- **Supabase: after creating anything in `public`, REVOKE from `anon` and
  `authenticated` BY NAME.** Default privileges grant them EXECUTE/ALL, and
  `REVOKE ... FROM PUBLIC` does nothing. Matviews have no RLS at all. Run
  `get_advisors(security)` after every migration and read the result, not the
  intent.
- **The Odds API returns `x-requests-remaining` on every response, including a
  401.** A silent quota exhaustion took out every feed for 2.5 days. Check the
  live figure (`odds_api_quota`), never a code comment.

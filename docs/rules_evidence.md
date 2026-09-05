# The evidence behind the standing rules

CLAUDE.md is re-read in full at the start of every session, so it holds the
RULES. This file holds the measured stories they were derived from — the
numbers, the outages, the queries — which a session only needs when it is
questioning a rule, changing one, or deciding whether a new trap qualifies.

Split out 2026-09-03 at mike's request. §1b and §7 were 12,731 and 13,008 bytes
— **57% of CLAUDE.md** — and their rule STATEMENTS were only 6% and 8% of those
bytes. The other ~92% is what you are reading now. **Every rule statement stayed
in CLAUDE.md verbatim; nothing here is a rule that is not also stated there.**

If you are adding to this file: put the rule in CLAUDE.md and the evidence here,
and never the other way round. The test CLAUDE.md already states — *would a
session that never opens `docs/` still do the right thing?* — is what decides
which half a sentence belongs in.

---

## 1b (evidence). Standing Rules From Matt (do not relitigate, do not forget)
**The reply format in Section 0 is the first of these rules — it was asked
for three times before it was written down. Do not drop it.**

These are instructions Matt has given that MUST survive across sessions. A new
session starts with no memory of previous ones, so anything Matt says to
"remember" belongs HERE, in the repo, immediately. Anything not written here is
gone the moment the session ends.

**API credits and spend.** Do NOT assume what the credit ceiling is, and do NOT
scope work around a guessed budget. Matt sets the ceiling, not Claude. If a
piece of work looks like it will use a meaningful number of credits, ASK HIM
FIRST and state the number. Check the live figure before saying anything about
quota (`odds_api_quota` in Supabase, or the `x-requests-remaining` header),
never a code comment: the comment in `nfl/data_ingest/odds_api.py` referencing a
20k quota is STALE and caused exactly this mistake on 2026-08-28, where a real
5,000,000 credit plan was mistaken for 20k and a whole analysis was wrongly
scoped down around it.

**NEVER ESTIMATE WHAT YOU CAN MEASURE.** (Added 2026-08-30 at mike's request,
after five wrong answers in one session that shared one cause.) Before stating
*when*, *whether*, *how much*, or *how long*, ask one question: **do I have what
I need to check this right now?** If yes, check. An estimate is not a faster
version of the answer — it is a wrong answer you have not noticed yet.

The failure is always the same shape: reaching for the FAMILIAR SHAPE OF THE
TASK instead of the facts already in hand. "Read tomorrow's timings" was said
four minutes after the deploy landed, on a job that runs hourly — three known
facts (deploy time, cron schedule, current clock), never multiplied, because
"instrument now, analyse tomorrow" is how this kind of work usually goes. The
tell is confidence: a guess that knows it is a guess gets hedged, and these
never are.

Three forms, each of which produced a real wrong answer here on 2026-08-30:

- **A time estimate** — state the clock arithmetic, don't round to "tomorrow".
- **A number** — name the query that produced it AND what it excludes. "MLB
  12-8" and "beats the close 0.7%" were both real queries answering the wrong
  question: the first counted repair rows the published view excludes, the
  second counted CLV of exactly zero as a loss.
- **A test** — it is not finished until you have WATCHED IT FAIL. Two tests
  shipped that day passed with the fix removed; both were caught only by
  deliberately mutating the code. A test that passes without the fix is not a
  test, and a guard that dead code can satisfy is not a guard.

This is the general form of the sandbox rule below, and of §7's verification
standards. Those say "go and look" for one specific case each; this says it for
every case.

**THE SANDBOX'S LIMITS ARE NOT THE SYSTEM'S LIMITS. Never report "I can't
reach X" as a conclusion.** (Added 2026-08-28 after saying third-party vendor
pricing "can't be checked from this sandbox" while holding a WebSearch tool,
in the same session that had already pivoted to Railway for exactly this
reason.) The dev sandbox has a narrow egress allowlist. The SYSTEM does not.
Four routes reach anything:

1. **WebSearch / WebFetch** — available in-session. Use them for docs, vendor
   pricing, API coverage, anything on the public web. There is no excuse for
   "I couldn't check" on a question the open web answers.
2. **The Railway worker** — open egress, already holds `ODDS_API_KEY`,
   `DATABASE_URL`, `DATAGOLF_API_KEY`. Any script in the repo can be run there:
   push it, then point a one-off service's start command at it (the
   `prop-probe` service exists for exactly this) or add a scheduler job. This
   is how the 100k-credit prop pull ran. See `docs/cloud_worker.md`.
3. **Matt's machine** — he can run any command and download any dataset
   directly. Ask for it as a specific command, not as a vague blocker.
4. **The Supabase MCP** — reads and writes production data directly.

So the shape of an honest report is "the sandbox can't reach it, so I'm going
via Railway / WebSearch / you" — never "this can't be done." If a blocker is
real, name which of the four routes was tried and why each failed. Reaching
for the sandbox's limit as an answer is the failure mode; be resourceful about
the route instead of scoping the work down to fit the box.

**THE CURRENT STATE OF A SYSTEM IS NOT ITS CAPABILITY, AND WORK YOU CAN DO IS
NOT AN ACTION ITEM FOR MATT.** (Added 2026-09-01 after the same failure three
times in one session.) The sandbox rule above says the sandbox's limits are not
the system's. This is the same mistake one level in, and it is the more common
one:

- **Asked "are you using the Odds API data?", I queried what was STORED.** The
  answer came back "73 Pinnacle games, five days" and I reported that Pinnacle
  history did not exist. `data/ingestors/odds_ingestor._get_historical_odds` has
  fetched `/v4/historical` into Supabase for years; it passed
  `bookmakers=draftkings`, and the param counts as ONE region, so seven books
  cost what one book costs. A three-day pilot returned 205 Pinnacle rows over 48
  games for June 2024. The data was never missing. **Before reporting that data
  does not exist, check what the SOURCE offers, not what the table holds.**
- **Four times I ended a turn with "run this on your machine."** Savant, five
  retrains, `threshold_sync`, the calibration promote. Two were already
  automated. The retrain never happened at all: I hit one obstacle (prop-probe
  has no build snapshot, so `redeploy` refuses), asked Railway's agent, was told
  it needed a commit, and stopped — instead of building the thing that makes the
  obstacle irrelevant. That thing is now `tracking/job_queue.py`: a row in
  `worker_jobs`, or an entry in `jobs/declared_jobs.json`, runs on the worker
  where the credentials and the egress already are. **A handover is a last
  resort with a reason attached, not a way to end a turn.**

The tell is the same in both: a turn that ends with a tidy summary and a to-do
list FOR SOMEONE ELSE feels finished. It is the work redistributed. Ask instead:
what did I actually change, and what did I merely describe?

**EXTRACTED DATA BELONGS IN SUPABASE.** (Added 2026-08-28.) Supabase is the
system of record and already holds essentially everything: 149k picks, 2.26M
prop-odds rows, 1.35M odds rows, 85k games, play-by-play, live game state, the
graded-outcomes matview, even the `nfl/` package's own `nfl_odds_history`. Any
dataset that cost money or time to acquire goes there, so it is queryable
beside everything else and is covered by one backup story rather than N.

The exception that proves it: the `nfl/` package (`docs/sports/nfl.md`) was imported as a standalone package
explicitly "NOT wired into ... Supabase", and that carve-out is exactly how
**100,116 credits of live prop snapshots came to exist only on a single
Railway volume** — no repo copy, no local copy, no second region. Backed up
2026-08-28 via `live_prop_job.sh backup` into `nfl_live_prop_snapshots`
(one gzipped, checksummed row per file; `--verify` decompresses and compares,
`--restore` rebuilds the tree). Ephemeral container disk is never a home for
paid data; a Railway volume is one copy, not a backup.

STILL OUTSIDE and worth fixing when touched: the live decision log
(`DECISION_LOG_DIR`, a JSONL on the worker's volume) and `nfl/data/odds_cache`
(committed to git, ~45k credits — protected, but by a different scheme).

**Live player props are a priority and are treated as a proven-profitable
market.** The thesis is NOT beating line movement or reacting faster than a
book. It is a statistical model for live prop over/unders priced RELATIVE TO
THE STARTING LINE, capturing in-game flow. The book re-anchors its live prop
line mechanically off the pregame number and the clock; the edge is predicting
where true remaining production deviates from that. Do not rebuild a player
projection from scratch and throw the pregame line away.

**A CHANGE TO HOW ONE MODEL OPERATES IS ASSESSED AGAINST ALL OF THEM.**
(Repo-level rule, 2026-08-29.) Before shipping an operational change — how a
loop prices, what it records, how it locks, what it publishes — ask whether the
other models want it too, and say so either way. Fixing one sport and leaving
the identical gap in five others is how this repo accumulates work: the live
price log existed for MLB and not NCAAF, the first-signal lock existed for NFL
and not anywhere else, and each was only found when it produced a visible
failure in the sport that lacked it.

The test is mechanical: *if this had been a problem in sport X, would we have
noticed?* If the answer is "only after someone questioned a number", the change
belongs in shared code, not in one loop. Prefer a sport-agnostic helper the
loops call over a per-sport implementation — `data/ingestors/live_price_log.py`
is the shape.

This applies to model MECHANICS, not to model CUTS: a threshold is measured per
model on its own record and must never be copied across.

**EVERY MODEL UPDATE IS STAMPED WITH WHO ASKED FOR IT — `mike` or `matt`.**
(Repo-level rule, 2026-08-29.) Two people direct this work, and six months
later "why is this model paused?" is unanswerable if the commit does not say
whose call it was. Threshold sweeps get re-litigated constantly (`docs/thresholds.md` is full of
corrections to corrections), so the person is part of the evidence, not
bookkeeping.

The stamp is a **git trailer on the commit** that lands the change:

```
Updated-By: mike
```

It goes on the branch commit, so it survives the squash-merge into master and
is greppable forever (`git log --grep="Updated-By: matt"`).

**What counts as a model update** — anything that changes what a model does or
whether it fires:
- a retrain, or a `model_registry` version swap / rollback
- a threshold change in `MODEL_PROB_THRESHOLDS` / `MODEL_EDGE_THRESHOLDS` /
  `ACTION_THRESHOLDS` / `MODEL_MIN_ODDS`
- a pause or unpause (`PAUSED_MODELS`)
- a feature-list change, a new model, or a retired one

**Not** a model update: cadence, plumbing, notifications, mobile UI, docs. Those
do not need the trailer.

**If you do not know whose call it is, ASK before committing.** Guessing an
attribution is worse than none — it puts a decision in someone's mouth. Where a
session's own user is the one directing, that is the name; where they are
relaying ("Matt wants…"), the name is the originator, not the relayer.

**EVERY FRONT-END CHANGE IS REVIEWED BY THE UX DESIGNER AGENT BEFORE ITS PR
OPENS. ALWAYS. NOT "WHEN IT SEEMS WORTH IT".** (Matt, 2026-09-02.) Any change
that adds or edits a file under `mobile/src` — a component, a screen, a
user-facing helper in `lib/` — gets the `frontend-ux-designer` subagent run on
it (`/ux-review`, or the Agent tool with that type) and its findings addressed
or explicitly declined in the PR body, before the PR is opened. The agent
reads `mobile/docs/UX_REVIEW.md`, runs `node mobile/scripts/ux_scan.mts
--changed`, and pulls real references from the Mobbin MCP server; it reports
and never edits. Mobbin being unavailable is a status line in the report, not
a reason to skip the review. A front-end PR opened without the review in its
body is incomplete — the same way a threshold change without `Updated-By:` is.

**WRITE THE SESSION SUMMARY TO `docs/sessions/`, NOT TO THIS FILE.**
(Repo-level rule, 2026-08-30.) The changelog convention that built this file was
"update CLAUDE.md after every commit". Over 192 sessions that grew it to
**909 KB — roughly 225k tokens re-read at the start of every session**, 76% of it
a log that duplicates git history. The split:

- Every session appends its summary to **`docs/sessions/<YYYY-MM>.md`**, newest
  first, and adds a row to `docs/sessions/README.md`. Same detail as before —
  what changed, why, what was verified, what was deliberately not done.
- Reference material for one sport or subsystem goes in its own `docs/` file
  (the map is §9). Update the doc, not this file.
- **Only PROMOTE into CLAUDE.md** when something becomes a rule that governs
  FUTURE work: a standing instruction, a convention, an invariant, or a trap
  that has now bitten twice (§7). Then state it here in its own right, plainly,
  rather than as a link to a session.

The test is the same one §1b already applies: *would a session that never opens
`docs/` still do the right thing?* If yes, it belongs in `docs/`. If no, promote
it. **Keep this file under ~30 KB.** If it is drifting past that, something in it
is a log entry wearing a rule's clothes.

---

## 7 (evidence). Hard-won lessons — the traps that have cost us twice

Promoted out of the session log because each one produced a real, shipped bug.
The detail behind every entry is in `docs/sessions/` (grep the session number).

### Analysis and thresholds

- **THE EVALUATION RULE. Any analysis of model performance, thresholds or signal
  timing MUST evaluate every scored pick — `BET`, `AVOID` and dead-zone `NONE`
  alike.** A BET-only sample contains only picks that already cleared the live
  bar, so it is systematically optimistic and cannot see the population a looser
  cut would draw from. The BET-only sweep put `mlb_moneyline` at +29% on 23 bets;
  the full-outcome sample said +4.1% on 50. `mv_scored_pick_outcomes` grades the
  whole universe. Three coverage traps to check FIRST: `NONE` rows only exist
  from 2026-05-12; they were **deleted ~2026-06-26 → 2026-08-09** (July 2026 has
  literally zero for every MLB model); and a game where `abs(edge) >
  MAX_EDGE_CAP` gets **no row at all** (35.3% of `mlb_runline` games). Clean
  windows: 2026-05-12→06-25 and 2026-08-09→present. Re-verify by month; never
  assume. Full version: `docs/signal_timing.md`.
- **Validate the grading before moving a cut.** Recompute outcomes from raw
  scores and reconcile against stored settlements first. A sign bug in away-side
  spread grading (`+scored_line` instead of `−`) survived a threshold change and
  turned a −20.6% cut into a phantom +15%.
- **Require a plateau, not a peak.** A cell whose eight neighbours flip negative
  one grid step away is noise. Report the neighbourhood, the per-season split,
  the bet count and a CI — and when the grid is negative everywhere, say so and
  retrain instead of shipping the least-bad cut.
- **A time split kills most false positives.** Every situational edge in the
  NCAAF search that looked strong pooled (61% wind+rain) collapsed when split
  early/late. Make the split part of the method, not a follow-up.
- **In-sample is in-sample.** Cuts swept on live picks regress forward. State
  which samples are trustworthy by volume and which are not.

### Data integrity

- **Leakage hides in "latest snapshot".** Every bulk feature loader that takes
  the newest odds row must bound on `snapshot_at <= commence_time` AND exclude
  `in_play`. Without it, 67% of completed 2026 WNBA games were featurized with a
  total that had already drifted toward the final score (avg 8.2 pts), which
  invalidated a whole threshold sweep and two models. Guards must FAIL OPEN when
  a timestamp is missing, so synthetic and SBR historical rows survive.
- **A pick stamped after its own first pitch is not a pre-game pick, and any
  measurement against market state must exclude it.** CLV, line movement,
  opening-signal comparisons — all of them difference the pick's number against
  a market snapshot, and that is only meaningful if the pick existed before the
  market closed. Bound on `created_at <= commence_time`, not just on the
  snapshot side. Measured 2026-08-30: **1,046 of 1,249** unmeasured MLB/WNBA
  prop bets carried a `created_at` after `commence_time` (restore/backfill
  restamping — §1c says timing is data, and this is what it looks like when
  that was not honoured), and only 10% of the MLB ones had their `scored_line`
  anywhere in DK's pre-game history. Without the guard they would each have been
  handed a fabricated beat-the-close verdict, **nearly all positive**, because a
  stale number always reads as a favourable move.
- **A self-healing backfill that walks "the oldest N un-done items" jams on the
  items it can never do.** Filter the queue by the SAME predicate the worker
  applies, or the head of the queue is permanently occupied and the backfill
  silently never converges. `_backfill_clv` re-walked the same 40 dates for days
  — eleven of its twelve oldest had zero capturable picks — and the only visible
  symptom was a coverage number that stopped climbing.
- **Parse timestamps before comparing them.** These columns are TEXT in mixed
  shapes (`Z` suffix vs `-04:00` offset vs naive); a string comparison silently
  keeps leaked rows.
- **"Today" is the wrong question for a LIVE loop, and it has now cost two
  outages.** A game carries the `game_date` of its FIRST PITCH, so a 10pm ET
  start is still in the fourth inning at 00:30 the next day — under YESTERDAY's
  date. #296 fixed the UTC half (the worker's `date.today()` rolled at 8pm ET
  and asked for tomorrow); on the very next night the same loop went dark at
  **midnight ET** for the last 77 minutes of three West Coast games, because it
  asked for today's schedule and they were no longer in it. Anything resolving
  which games to poll, price or score uses `config.live_slate_dates()` (today +
  yesterday in the early window), never `today_et()` alone. **Both failures were
  silent for the same reason: "no active games" is also exactly what an empty
  slate looks like** — so the guard is a test, not a log line.
- **Use ET, never UTC, for "today".** `new Date().toISOString().slice(0,10)` is
  tomorrow after 8pm ET. Python has the same trap.
- **A model's PROBABILITY is a separate claim from its point estimate, and
  needs its own gate.** Measured 2026-08-30, twelve models publish probabilities
  6-16pp above what they deliver at the levels actually bet, and it tracks
  sample size rather than sport or market — a model fits its training seasons
  more tightly than any season it has not seen, and every live pick is made out
  of sample. `mlb_live_total_runs` shows it cleanly: in-sample -2pp, on 2025
  +9pp, on 2026 +7 to +13pp, while its point estimate is nearly unbiased. **So a
  retrain is not the fix** — it moves the boundary, not the behaviour. The fix is
  a claimed-to-realised map (`models/probability_calibration.py`,
  `docs/probability_calibration.md`), published but deliberately NOT yet used to
  decide, because every threshold was swept on raw probabilities.
- **Gate the number that gets BET, not the one that is convenient to compute.**
  `_mean_calibration_error` averages bins unweighted and across the whole
  probability range, so a 10pp error in the small band that gets bet is diluted
  by the large well-calibrated band near 0.5. And for a Poisson model it was not
  measuring a probability at all — the count fit passed while the serve-time
  Poisson tail, which is what the scorer bets, was 9-10pp off on its own
  holdout and had never been evaluated. Use `cal_error_actionable`.
- **A stat that is always NULL deletes the training matrix.** One sparse column
  plus `dropna` silently drops most rows (`d_xgf_pct`, the goalie last-5 diffs).
  Check population before adding a feature.
- **Season-to-date rates are noise early.** Blend toward the prior season by
  games played; a raw average over the first month of a 12-game season is the
  single biggest modelling error available.

### Operations

- **A LIVE cutoff decays, so re-derive it rather than setting it once.** A
  pre-game model is scored daily against a line that barely moves; a live model
  locks at the first crossing of a market that moves every few seconds. On
  2026-08-29 the first-signal lock plus 5s polling took MLB live from ~35% of
  games producing a bet to **100%** — ~63 bets/week — at an UNCHANGED threshold.
  Nobody moved a cut; the meaning of the cut moved. `tracking/live_calibration.py`
  re-derives every live cut each pass and publishes it (monitor → Live tuning),
  and its verdict is allowed to be "no cut works, retrain or pause".
- **Project volume from the CURRENT regime, not the lifetime average.** The
  lifetime average said 10 live bets/week while the live rate was ~60, because it
  averaged five quiet weeks with the two days after the machinery changed. A
  threshold chosen off that number is chosen for a world that no longer exists.
- **A retrained model must have its `.pkl` COMMITTED.** The registry row points
  at a path; if the artifact is not in the repo the worker cannot load it and the
  model silently stops scoring. This has cost a month of UFC picks and a
  four-week outage across three MLB prop models.
- **A model in `config.MODELS` with no `FEATURE_MAP` entry raises before the
  artifact is even looked at — and kills scoring for EVERY sport.** One missing
  key produced zero game-level picks league-wide for a day, visible only as an
  empty board for one sport. A derived test asserts the two stay in sync; keep
  it.
- **A table created at write time must not re-run its DDL on every write, and
  `IF NOT EXISTS` does not make it free.** `CREATE INDEX IF NOT EXISTS` takes a
  SHARE lock and `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` takes ACCESS
  EXCLUSIVE whether or not the object is already there — and **every one of them
  fires Supabase's `pgrst_ddl_watch`, so PostgREST answers 503 to the whole app
  while it rebuilds its schema cache.** Seven modules did this on every call.
  Measured 2026-09-01 from `pg_stat_statements`: `ALTER TABLE api_call_log
  ENABLE ROW LEVEL SECURITY` 1,676 calls at a 7.8s mean, `CREATE INDEX IF NOT
  EXISTS idx_api_call_ts` 1,925 calls at a 15.1s mean — **11.6 hours of database
  time and ~3,600 forced cache reloads**, 232 of which then hit the 8s
  `authenticator` timeout. The visible symptom was one screen: the Stats tab
  showing "Connection error" over an empty board. It is self-reinforcing —
  `monitoring/probe.py` re-ran its ensure block on every reconnect, so the more
  the database struggled the more DDL it got. Gate every write-time ensure block
  on `data/ddl_guard.schema_is_current`, which fails open;
  `tests/test_ddl_guard.py` is the tripwire for the next one. **Judge these
  statements per INVOCATION, not per millisecond** — `CREATE TABLE IF NOT
  EXISTS` costs 5-7ms and looks free, but it ran 3,479 times from one module
  and every one was a cache reload. The first tripwire missed
  `tracking/threshold_review.py` entirely by grepping only for the RLS
  statement: **a test scoped to the symptom already found is not a tripwire**,
  and only deliberately reverting the fix showed it.
- **An empty board and a broken pipeline look identical.** Prefer writing a
  "declined, and here is why" row over `return []`. Check
  `pipeline_runs.failed_steps` before blaming thresholds, and `push_sent` before
  believing a notifier ever worked — nothing is ledgered unless a POST confirmed,
  so a `kind` with zero rows means it has NEVER succeeded.
- **A health check must not gate on the thing that breaks.** Two checks reported
  SKIPPED for the entire outage they existed to catch, because they keyed off
  data the failing feed produces.
- **A swallowed exception plus a legitimately empty channel is invisible.** Live
  Discord posts raised on every call for five days behind a correct try/except.
  Where a caller must swallow, test the producer REAL output through the real
  renderer — a hand-written fixture drifts from the producer exactly as the
  renderer did.
- **Supabase: after creating anything in `public`, REVOKE from `anon` and
  `authenticated` BY NAME.** Default privileges grant them EXECUTE/ALL, and
  `REVOKE ... FROM PUBLIC` does nothing. Matviews have no RLS at all — anon held
  MAINTAIN (i.e. `REFRESH`) on one, and SELECT+INSERT+UPDATE+DELETE on a
  2.2M-row irreplaceable archive. Run `get_advisors(security)` after every
  migration and read the result, not the intent.
- **The Odds API returns `x-requests-remaining` on every response, including a
  401.** A silent quota exhaustion took out every feed for 2.5 days. Check the
  live figure (`odds_api_quota`), never a code comment.

### Verification standards — what "verified" means here

- **`git stash` is NOT a master baseline once the work is committed.** Use
  `git worktree add --detach origin/master` and diff against that. Local
  `master` in these sandboxes is routinely dozens of commits behind — always
  compare to `origin/master`.
- **Report a tsc or pytest baseline as an error-SET diff, not a count.** The
  mobile tree carries a documented set of pre-existing `queries.ts` cast errors;
  the claim to make is "byte-identical to master, 0 in touched files".
- **Read source with an explicit encoding.** A dozen tests assert things about
  the repo's own source by reading it back, and `read_text()` with no encoding
  uses the PLATFORM default — cp1252 on Windows, where this repo actually runs.
  The source is full of box-drawing characters, so those tests did not fail, they
  raised `UnicodeDecodeError`, and one raised it at COLLECTION time, which
  aborted the entire suite. The repo's only quality gate was unrunnable on the
  only machine that runs it. Fixed 2026-08-30; keep `encoding="utf-8"` on every
  source read.
- **Check whether deps actually install before hand-waving.** PyPI is often
  reachable from these sandboxes — a real suite run beats "run it on your
  machine". Equally, the sandbox egress limits are not the system limits (§1b).

## The app, Discord and push show the same picks (2026-09-05)

The rule is in CLAUDE.md §1b. This is what was measured.

**The report.** Matt: *"There was an NFL signal last night at 8pm. Why didn't
that post to discord."* `picks` row 1634280 — `nfl_wind_totals`, CLE @ JAX
Under 40.5 (-105), written 2026-09-05 00:00:19 UTC = **2026-09-04 20:00:19 ET**.
It cleared every threshold: edge 5.97pp against a 3.00pp cut, probability 0.5489
against 0.52, -105 against a -200 floor, model not paused. The app showed it.
Discord never did, and neither did push.

**Why.** The publishers read `opening_signals`; the app reads `picks`.
`capture_opening_signals` reached `NFL_LOCK_AHEAD_DAYS` (7) forward, the game
was 2026-09-13 — 9 days out — so no lock row was ever written and there was
nothing for the publishers to find. `config.py` carried the comment *"the wind
card never reaches further than ~4 days out"*; `scheduler.NFL_POLL_HORIZON_DAYS`
is 10, and Week 1 Sunday is 9 days from Friday.

**The gap was not NFL-only.** Every BET clearing its current thresholds since
the first Discord signal (2026-08-23 22:42 ET) through 2026-09-05:

| Sport | Eligible | Published | Never captured | Captured, not published |
|---|---|---|---|---|
| MLB | 117 | 113 | 4 | 0 |
| NFL | 2 | 0 | 2 | 0 |
| WNBA | 4 | 4 | 0 | 0 |
| UFC | 1 | 1 | 0 | 0 |
| NCAAF | 1 | 1 | 0 | 0 |
| **Total** | **125** | **119** | **6** | **0** |

**The shape of the answer is the whole point: every miss is a capture miss, and
nothing that was captured failed to deliver.** Delivery was already 100%.
Bounding on the launch date mattered — an unbounded query showed 39 misses out
of 161, but 33 of those were picks written before Discord signals existed and
were never eligible. Reporting that 24% would have been wrong.

The 4 MLB misses (3 × `mlb_f5_moneyline` on 08-26, 1 × `mlb_prop_batter_walks`
on 08-24) pass every guard in the capture predicate — right `game_date`,
pre-first-pitch, `signal_type='BET'`, not live, no lock row under any side — and
remain unexplained: `pipeline_runs` only reaches back to 2026-08-27. Since that
date, where the run history exists, the only capture misses are the two NFL
picks.

**Push was worse than Discord.** `push_notifier._new_bet_signals` read
`opening_signals` AND bounded on `os.game_date = target_date`, without even the
look-ahead widening Discord carried, and applied no `min_odds` gate. So no
look-ahead pick in any sport could be pushed on the day it was written.

**Deploy check before shipping.** Re-pointing the producers at `picks` risks a
backlog flood on the first run. Counted first: exactly 2 rows — the two NFL
picks. No burst.

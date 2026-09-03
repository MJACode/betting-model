## ModelCalibration — the weekly re-measure (added 2026-08-31, mike)

**Two halves, and only one of them is an agent.**

- **The mechanical sweep runs on the Railway worker**, Mondays 8:30am ET
  (`scheduler.py::run_model_calibration`). **Code:**
  `tracking/model_calibration_agent.py`. **Kill switch:**
  `RUN_MODEL_CALIBRATION=0`. Unchanged.
- **The judgement pass runs inside SENTINEL**, section B of its Routine prompt,
  on Mondays or any day the sweep is more than 8 days stale. It had its own
  Routine until 2026-09-01; see "Why the judgement pass moved into Sentinel"
  below.

Refits the calibration candidates, sweeps **every** registered model on
calibrated probabilities with the price floor applied and the time split
enforced, writes one row per model per run to `model_calibration_sweeps`, and
posts a summary to `DISCORD_WEBHOOK_OPS`.

**"Every" is the load-bearing word.** Two exclusions were removed to get there:

- **Prob-only models** (`mlb_prop_batter_hr`, `nba_prop_player_dd`,
  `ufc_method_of_victory`) were skipped entirely, because their `edge` is
  measured against an invented baseline rather than a market price. They are now
  swept on the probability dimension alone (`edge_grid=[0.0]`). That exclusion is
  how the worst model on the board — HR, −63% over 252 settled bets — sat outside
  every review this repo has ever run.
- **The HR never-pause directive** (session 60) is lifted. It rested on a true
  observation, that a longshot market always looks bad on W-L, used to excuse a
  model that is separately overstating: claimed 22.5% against a realised 16.7%
  at an average +513.

Live models stay out: `tracking/live_calibration.py` re-derives their cuts every
pass, and judging one mechanism on the other's cadence misreports both.

**It changes nothing.** No threshold, no pause, no promotion — each is a model
update needing a person and an `Updated-By` trailer. The agent's job is to make
the decision unavoidable, not to make it. The single automatic action in the
system is the one-way 250-bet pause rule in `tracking/threshold_review.py`.

**Why weekly and unconditional.** Every threshold here decays, and each time one
did, a person found it by noticing a bad number: `mlb_f5_moneyline` ran at −9.3%
for a month before a −195 pick raised the question; `mlb_runline` stopped
producing picks on 2026-07-19 and went six weeks unnoticed, because a dormant
model and a broken feed look identical. A sweep that runs only when someone is
suspicious finds problems at the speed of suspicion.

### Why the judgement pass moved into Sentinel (2026-09-01)

The ModelCalibration Routine was created on 2026-08-31 **with no MCP connections
at all** — unlike Sentinel and Janitor, which both carry Supabase and Railway.
Its entire job is reading `model_calibration_sweeps`, the sandbox has no
`DATABASE_URL`, and its own prompt correctly told it to stop rather than write a
report blind. So it was going to stop, every Monday, forever.

Four routes to attach a connector were tried and all are closed:

1. `create_trigger` with `connectors` → *"not available for this organization."*
2. Implicit pass-through from a dev session that holds Supabase → the API
   answers *"this call had none to pass through … no passable connector
   grants."* (Verified with a throwaway Routine, then deleted.)
3. Dropping the dependency — no `DATABASE_URL`, no `.env`, no Postgres
   credentials reach a Routine session.
4. Having Sentinel recreate it, since the API's own warning says *"create it
   from a session that holds them"* → a Routine-fired session gets only the
   connectors on its own Routine, and no Routines tooling, so it has no
   `create_trigger` to call. It made nothing.

That leaves one honest option: **put the work where the connector already is.**
Sentinel holds Supabase, already runs daily, and is already a read-and-report
watch — the calibration pass is a bigger instance of what it does. The old
Routine is DISABLED rather than deleted, and renamed so its state is legible in
the Routines list.

**To undo this if a person ever attaches Supabase to that Routine in the
claude.ai UI:** re-enable it and delete section B of Sentinel's prompt. Nothing
else moves. The mechanical sweep on the worker is untouched either way.

**The general rule this is an instance of:** an agent whose one data source is a
connector it does not hold is not a degraded agent, it is a decorative one. When
a scheduled agent is created, the thing to verify is not that its prompt is
right but that it can *reach* what the prompt tells it to read.

### Catch-up on boot

`scheduler.py::catch_up_weekly_jobs()` runs a weekly job immediately at startup
if its data is already stale. A weekly cron has a one-week worst-case first run,
and that bit us twice in the same week:

- **The Savant refresh** was added with a Monday 5:30am trigger *hours after*
  that Monday's 5:30 had passed, so a four-month-old pitcher snapshot and an
  entirely absent 2026 batter snapshot would have kept feeding every prop score
  for another week. Freshness signal: `MAX(as_of_date)` and the count of
  `player_type`s in `player_savant_stats` for the current season.
- **ModelCalibration** was added the SAME DAY, at 18:06 ET, with a Monday 8:30am
  trigger — and the catch-up written for the first case covered only Savant. So
  `model_calibration_sweeps` did not exist in production at all, and the first
  sweep of every registered model would have waited until 2026-09-07. Freshness
  signal: `MAX(run_date)` in that table, where a MISSING table is the loudest
  possible stale.

Fixed 2026-09-01 by making it a LOOP over weekly jobs rather than one check with
a second bolted on: the next weekly job inherits the catch-up by appearing in the
list, not by someone remembering. Ownership is checked per job inside the
function — gating the whole catch-up on `owns("savant_refresh")` meant a role
that did not own Savant skipped every other weekly catch-up too.

Boot is the right moment because a deploy is the one event that reliably follows
a change to what these jobs do. Guarded by a freshness check (so a crash-looping
container does not re-pull), scoped to the pipeline service (so two services do
not double the spend), and best-effort per job (a catch-up that raised would stop
the scheduler starting at all, and one weekly job failing must not cancel the
rest).

---

# Agents — Sentinel and Janitor

> **Sentinel** watches the pipeline. **Janitor** clears the backlog.
> Named by mike, 2026-08-30. If you are looking for "the agents", this is the
> file (or `docs/AGENTS.md` for the one-screen version); `docs/followups.md`
> is Janitor's worklist.

> Two scheduled Claude sessions that do work between hands-on sessions.
> Created 2026-08-30 (mike). Before this, the repo had **no agents at all** —
> no `.claude/` directory, no Routines, only deterministic cron jobs. The
> scheduler could *detect* a problem (health checks, the run ledger,
> `pipeline_log`) but nothing ever *acted* on what it detected, which is why
> the same four small fixes sat untouched for four sessions in a row.

## Why these are sessions, not cron jobs

The eleven scheduler jobs run fixed Python entry points. That is right for
work whose steps are known in advance — fetch odds, score, settle. It is
useless for "the pass got slower, find out why", because the answer is
different every time and the next action depends on it.

These two agents exist for exactly the work that needs judgement, and they are
scoped so the judgement is bounded.

---

## THE PIPELINE WATCH — a cron job, not an agent (moved 2026-09-03)

**Runs:** 7:15am ET daily on the Railway worker, `scheduler.py::run_pipeline_watch`.
**Code:** `tracking/pipeline_watch.py`. **Kill switch:** `RUN_PIPELINE_WATCH=0`.
**Output:** one Discord post to `DISCORD_WEBHOOK_OPS` every run, clean or not.

**Why it stopped being Sentinel.** mike, 2026-09-03: *"sentinel and janitor keep
asking for permission to run queries, I have to keep clicking allow"* → *"move
the watch to the worker"*.

Sentinel read the database through the Supabase MCP. Routine sessions carry no
`mcp__*` entry in their permitted-tool list, so **every read raised a permission
prompt**. Unattended, nobody answers it and the run dies in `REQUIRES_ACTION` —
that happened on two consecutive days (`mcp__Railway__get-logs` 09-01,
`mcp__Supabase__list_tables` 09-02), each time reporting nothing. Attended, it
is worse: the prompts queue on a person's screen, and a watch that pages you
every morning is a chore, not a watch.

Three fixes were tried before this one and all failed the same way — each
removed the *instance* rather than the *class*. Ban the Railway MCP: it blocked
on Supabase the next day. Ban all `mcp__*`: the watch goes blind, because
reading the database was its whole job. Grant the permission in
`.claude/settings.json`: correct, and the right long-term answer, but an agent
is deliberately barred from authoring a file that widens its own permissions,
so it needs a person.

So the watch stopped needing the permission. The worker already holds
`DATABASE_URL` and the webhook and already runs eleven cron jobs.

**What is lost, plainly: judgement.** An agent could notice something nobody
wrote a rule for. This applies the six rules below and nothing else. The honest
trade is that a narrower watch which runs every day beats a broader one that has
not completed a run since 2026-08-31. If the MCP permissions are ever granted,
the judgement layer can come back on top of this — the deterministic report is
the input either way, which is why `scripts/pipeline_report.py` was always
separate from the agent.

**The six rules** (`tracking/pipeline_watch.py`, each a pure function so it is
testable without a database):

1. A step whose average duration regressed against its own 7-day baseline —
   both ≥5s absolute and ≥1.5× relative, since either test alone is noise.
2. A pass that failed, or never recorded a finish. "No finish" means the pass
   died OR its finish-ledger call failed; the wording does not pick one.
3. Any health check not OK, CRIT first.
4. Odds API burn at or above 55k credits against the 60k daily cap, plus any
   source with failed calls. Judged against the cap, not against yesterday — a
   day-on-day test fires on every quiet day.
5. A `push_sent` kind that fired in the last fortnight but not in the window.
   Only ever compares successes against successes.
6. A weekly job stale past 8 days: `model_calibration_sweeps` and
   `player_savant_stats`. A missing table reads as never-completed.

It changes nothing — no threshold, no pause, no registry swap. Those are model
updates needing a person and an `Updated-By` trailer (CLAUDE.md §1b).

## JANITOR — the backlog runner (daily, 8:00am ET)

*Routine name: `Janitor — backlog runner` (renamed from `followup-runner`).*

**Janitor clears one thing off the list a day, properly.**

**Reads:** `docs/followups.md`, the durable backlog.

**Does:** picks the highest-value item it can finish end to end, does it
properly (tests, mutation check, PR), ticks it off the list, and messages the
user with what landed.

**Why a file and not a prompt:** "knock out follow-up tasks" is undefined
without a list. A fresh session has no memory of what was agreed three
sessions ago, and a task list living only in chat history is gone the moment
the session ends — the same failure mode CLAUDE.md §1b was written to stop.
The file is the memory.

**Must not:**
- take an item marked `[needs-decision]`. Those are blocked on a human by
  definition; taking one means guessing what was wanted.
- take more than one item per run. A session that half-finishes three things
  is worse than one that finishes one, and the PR is the unit of review.
- touch model thresholds, for the same reason as above.
- delete an item it did not complete. An item it could not do gets a note
  saying why, so the next run does not rediscover the same wall.

**Reports:** a message to the user naming the PR and what changed. Silence
after an unattended run is indistinguishable from failure.

---

## The checkout is not there the instant the session is

Measured 2026-09-01, and it cost a whole Sentinel run.

    01:32:36Z  Sentinel session starts
    01:36:25Z  Sentinel finishes: "no git repository is checked out"
    01:39:45Z  the clone lands in /home/user/betting-model

The repo arrived **three minutes and twenty seconds after the agent gave up.**
Its report named the wrong cause with real confidence — "the trigger's
environment config lost its repo source", a durable-sounding fault requiring a
human — for what was a transient it could have waited out. Nothing was wrong
with the Routine, the environment, or the binding.

This is CLAUDE.md §1b's "the sandbox's limits are not the system's limits"
arriving from a new angle, and §1b's estimate rule underneath it: an empty
directory four minutes into a session is not evidence that a repo does not
exist, it is evidence that nobody has looked twice.

**So: an absent checkout is a WAIT, not a finding.** Poll for the working tree
before concluding anything about it, and only report a missing repo after the
wait has actually expired — then say how long you waited. An agent that reports
a transient as a permanent fault trains its reader to ignore it, which is the
one failure a watch cannot recover from.

The same applies to every other thing an agent finds missing on the first look:
`docs/`, the test suite, an MCP connector still handshaking. Look twice before
calling something gone.

## An unattended agent must never make a call that can block on a human

Measured 2026-09-01, and it cost a whole Sentinel run — the second one lost that
day, to the opposite failure from the first.

Sentinel's prompt told it to check the worker's logs via the Railway MCP when
`model_calibration_sweeps` was missing. It did. The harness raised a permission
prompt for `mcp__Railway__get-logs`, and with nobody watching a 7:15am scheduled
run, the session sat in `REQUIRES_ACTION` for **over 100 minutes** and never
produced a report at all.

Note the shape. The first lost run gave up too early on something that would
have arrived (the checkout). This one waited forever on something that never
would (a human). Both produced silence, and **silence is the one output a watch
must never produce** — a blocked watch and a stopped watch are indistinguishable
to the person relying on it, and both are worse than "I could not see X".

So the rule has two halves, and they are not in tension:

- **Wait for what arrives on its own.** A checkout, a container, an MCP server
  still handshaking. Bounded, local, poll for it.
- **Never wait on a person.** If a tool needs approval, it will never be
  approved on a scheduled run. Treat it as unavailable, say what you could not
  see and why it mattered, and finish.

**It is not one connector. It is MCP.** The first diagnosis here said "the
Railway MCP prompts; Supabase and Bash do not", and named Supabase as the safe
route. That was an assumption, not a measurement, and the very next day
disproved it:

    2026-09-01 11:19Z  mcp__Railway__get-logs      blocked 100+ min, no report
    2026-09-02 11:18Z  mcp__Supabase__list_tables  blocked again, no report

Two different servers, two consecutive daily runs, both lost. The Routines'
`allowed_tools` lists contain no `mcp__*` entries at all — only Bash, Read,
Grep, Glob, Write, Edit, WebFetch, WebSearch and friends — so **every** MCP call
raises a prompt an unattended run cannot answer. Both prompts now forbid the
whole `mcp__` prefix.

Note what the first fix did: it removed the one call that had actually failed
and declared the rest safe. Fixing the instance rather than the class bought
exactly one day, and cost the run that proved it. When a call fails because of
what KIND of thing it is, enumerate the class before writing the rule.

The permitted-tool list lives in the Routine's `session_context` and is NOT
settable through `update_trigger`, so this cannot be fixed by granting the
permission from here — only by not making the call, or by a person editing the
Routine's tool permissions in the claude.ai UI.

**What this costs.** Sentinel's entire daily watch reads the database, the
sandbox has no `DATABASE_URL`, and Supabase is now off the table — so Sentinel
cannot see the pipeline at all unattended. It is reduced to what the repo alone
supports: what landed on master, the state of `docs/followups.md`, and a real
`pytest` run (worth something, since there is no CI on PRs). Its prompt now says
to report that blindness in one line every run rather than hang. **A degraded
agent that reports is worth more than a complete one that is silent**, but this
is a real capability loss and the fix needs a person.

The general form, and the reason this belongs next to the guardrails rather than
in a session log: **an agent's tool list is not its capability list.** A tool it
holds but cannot use without a human is worse than one it does not hold, because
the missing tool fails fast and the gated one hangs.

## Guardrails both agents share

1. **Full suite before any PR** (`python -m pytest -q tests/`), and the result
   stated in the PR body. There is no CI on pull requests in this repo — the
   suite is the only gate.
2. **Never push to master.** Branch, PR, and let a human merge. An agent that
   can self-merge can ship a regression at 7am with nobody watching.
3. **Mutation-check anything load-bearing.** A test that passes when the fix is
   removed is not a test. This session found two such tests in one day.
4. **Stop and report rather than guess.** A blocked item reported honestly is
   worth more than a plausible-looking change nobody asked for.
5. **Read CLAUDE.md first.** Section 0's reply format, §1b's standing rules and
   §1c's pick rule apply to an agent exactly as they apply to a session.

## Changing an agent

Its prompt lives in the Routine, not in this file — edit it with
`update_trigger`, which keeps the Routine's run history. This file is the
contract; the Routine is the implementation.

---

## UX DESIGNER — the front-end review (proactive on any front-end change, and `/ux-review`)

*Added 2026-09-02 (Matt). Not a Routine: a project subagent at
`.claude/agents/frontend-ux-designer.md`, invoked by `/ux-review` or delegated
to automatically after a change under `mobile/src`. The first agent whose
definition lives in the repo rather than in a Routine — so changing it is a
commit, and its history is git's.*

**The designer looks at every component a change touches and says what a
user will feel.**

**Reads:** the changed `.tsx` files and the screens that mount them;
`mobile/docs/UX_REVIEW.md` (the checklist — the contract for *what* it looks
at); and the output of `node mobile/scripts/ux_scan.mts --changed`, the
deterministic half. Same split as Sentinel and `pipeline_report`: the script's
findings are comparable run to run, the agent supplies judgement on top and
never replaces them.

**References:** real shipped screens pulled through the Mobbin MCP server
(`mobbin`, declared in `.mcp.json`; official remote server, OAuth, paid plan —
`mobile/docs/UX_REVIEW.md` has the setup). Each finding names the app and
screen it is compared against, or the Apple HIG section, so Matt has a picture
to look at rather than an adjective. When Mobbin is not connected, the review
says so in one line and continues on HIG and the app's own conventions — a
missing reference is never a reason to skip a review.

**Reports:** a verdict (Ship / Ship with fixes / Do not ship), findings as
`[severity] file:line — what / why / reference / change`, the scan output
verbatim, then the CLAUDE.md §0 headings. Blockers are the product rules
(§1c pick-is-a-pick, §6 DK-decides, §2 LIVE-not-paper, the entitlement gate,
ET dates) and accessibility failures; everything else is Should-fix or
Consider, and Consider is capped at five because past that it is a redesign,
which is Matt's call.

**Must not:**
- edit a file. It has no edit tools; the review is the deliverable, and the
  fixes are a normal session afterwards.
- touch a threshold, a pause, or a `config.py` / `thresholds.ts` value, for the
  same reason as the other two.
- propose dark mode. The app is light-only by decision; hard-coded colours are
  flagged because they break the day that changes, not because it has not.
- redesign a screen the change did not touch, or report "could not reach
  Mobbin" as an outcome rather than a status line.

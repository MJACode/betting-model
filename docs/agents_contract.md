## ModelCalibration — the weekly re-measure (added 2026-08-31, mike)

**Runs:** Mondays 8:30am ET on the Railway worker (`scheduler.py::run_model_calibration`).
**Code:** `tracking/model_calibration_agent.py`. **Kill switch:** `RUN_MODEL_CALIBRATION=0`.

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

### Catch-up on boot

`scheduler.py::catch_up_weekly_jobs()` runs a weekly job immediately at startup
if its data is already stale. A weekly cron has a one-week worst-case first run,
and that bit us the same day: the Savant refresh was added with a Monday 5:30am
trigger *hours after* that Monday's 5:30 had passed, so a four-month-old pitcher
snapshot and an entirely absent 2026 batter snapshot would have kept feeding
every prop score for another week. Boot is the right moment because a deploy is
the one event that reliably follows a change to what these jobs do. Guarded by a
freshness check (so a crash-looping container does not re-pull), scoped to the
pipeline service (so two services do not double the spend), and best-effort (a
catch-up that raised would stop the scheduler starting at all).

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

## SENTINEL — the pipeline watch (daily, 7:15am ET)

*Routine name: `Sentinel — pipeline watch` (renamed from `pipeline-watch`).*

**Sentinel stands watch over the pipeline and says what it sees.**

**Reads:** `python -m scripts.pipeline_report --hours 24`

That script is deliberately NOT part of the agent. If the agent had to
discover the schema and write its own SQL every morning, it would produce a
different analysis each day and its findings would not be comparable — which
is the one thing a watch needs. The data is deterministic; the agent supplies
judgement about what it means.

**Acts when:**
- a step's average duration regressed materially against the days before it
- a pass failed, aborted, or ran long enough to overrun its own cadence
- a health check is CRIT, or a check flipped from OK to not-OK
- Odds API burn jumped without a matching increase in picks
- a `push_sent` kind that normally fires has gone silent

**Must not:**
- change a model threshold, pause or unpause a model, or swap a registry
  version. Those are model updates under CLAUDE.md §1b and need a named human
  (`Updated-By:`). Guessing an attribution puts a decision in someone's mouth.
- push to master. It opens a PR.
- "fix" a failing test by weakening it.

**Reports:** always, even when everything is clean — a watch that only speaks
up when it has something to say is indistinguishable from a watch that has
stopped.

---

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

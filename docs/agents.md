# Autonomous agents

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

## 1. `pipeline-watch` — daily, 7:15am ET

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

## 2. `followup-runner` — daily, 8:00am ET

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

# AGENTS

**One subagent works. One scheduled agent does not, and the table below says so
rather than describing what it was meant to do.**

**UX Designer** is a project subagent that reviews front-end changes on demand
and proactively. It works.

**The pipeline watch is no longer an agent** — it is a cron job on the Railway
worker (`tracking/pipeline_watch.py`, 7:15am ET), because every database read
from a Routine session raised a permission prompt nobody could answer
unattended. It posted on schedule the first morning it ran, and its first run
found two defects in `scripts/pipeline_report.py` that had been silent for as
long as the report existed (#417). The Sentinel Routine is disabled and renamed
to say why.

**Janitor** is the scheduled session that is supposed to clear one backlog item
a day. **As of 2026-09-03 it cannot land work at all.** Four runs finished
SUCCEEDED having put nothing in the repo, two of them directed runs with the
item chosen for them; `git push` does not work from its sandbox and the GitHub
MCP is not attached to its Routine, so it has no exit. `agents_contract.md`
carries the table, the routes tested, and the decision pending. Read that
before touching it — in particular, do not rewrite its prompt again, which has
already been tried and changed nothing.

| | Janitor | UX Designer |
|---|---|---|
| **Does** | Supposed to clear one backlog item a day. Currently lands nothing | Reviews every component a change touches, against the checklist and real Mobbin references |
| **Runs** | 08:00 ET daily | `/ux-review`, or automatically after a change under `mobile/src` |
| **Reads** | `docs/followups.md` | `mobile/docs/UX_REVIEW.md` + `node mobile/scripts/ux_scan.mts --changed` |
| **Output** | **Nothing reaches the repo.** A report only its own session can see | A verdict and findings with file:line, why, reference, change. No edits |
| **Cannot** | Push, open a PR, or read the database. Change a model threshold. Take a `[needs-decision]` item | Edit a file. Change a threshold. Propose dark mode or a redesign of an untouched screen |

**ModelCalibration** is not a third agent. Its mechanical sweep is a cron job on
the Railway worker — it first ran 2026-09-02 via the boot catch-up, 22 models,
and the table came out locked down. Its judgement pass has no home now that
Sentinel is retired; that is part of the pending decision.

**Backlog items are currently cleared in ordinary sessions**, which is how the
two NHL items went out on 2026-09-03 (#420). That is not a workaround pending a
fix — on today's evidence it is the only thing that works.

**Full contract and guardrails: [`agents_contract.md`](agents_contract.md).**
**Janitor's worklist: [`followups.md`](followups.md).**

Janitor is a Routine (a scheduled session), not a cron job. The cron jobs in
`scheduler.py` run fixed Python entry points and decide nothing; a Routine
exists for work needing judgement. Rename or reschedule one with
`update_trigger`, which keeps its run history — the name lives in the Routine,
not in this file. Note the asymmetry the watch demonstrated: a cron job on the
worker can write to the database and post to Discord, while a Routine session
can do neither, and cannot push either. Judgement is the only thing a Routine
has that a cron job does not. UX Designer is defined in `.claude/agents/frontend-ux-designer.md`;
change it with a commit.

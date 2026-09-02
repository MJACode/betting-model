# AGENTS

**Sentinel** and **Janitor** are the two scheduled Claude sessions that work on
this repo between hands-on sessions. **UX Designer** is a project subagent
that reviews front-end changes on demand and proactively.

| | Sentinel | Janitor | UX Designer |
|---|---|---|---|
| **Does** | Watches the pipeline and reports what it sees | Clears one backlog item a day | Reviews every component a change touches, against the checklist and real Mobbin references |
| **Runs** | 07:15 ET daily | 08:00 ET daily | `/ux-review`, or automatically after a change under `mobile/src` |
| **Reads** | `python -m scripts.pipeline_report --hours 24` | `docs/followups.md` | `mobile/docs/UX_REVIEW.md` + `node mobile/scripts/ux_scan.mts --changed` |
| **Output** | A report every run, clean or not. A PR when it can fix something | A PR, the item ticked off, and a message to the user | A verdict and findings with file:line, why, reference, change. No edits |
| **Cannot** | Change a model threshold. Push to master | Change a model threshold. Push to master. Take a `[needs-decision]` item | Edit a file. Change a threshold. Propose dark mode or a redesign of an untouched screen |

**Full contract and guardrails: [`agents_contract.md`](agents_contract.md).**
**Janitor's worklist: [`followups.md`](followups.md).**

Sentinel and Janitor are Routines (scheduled sessions), not cron jobs. The eleven cron jobs in
`scheduler.py` run fixed Python entry points and decide nothing; these two exist
for the work that needs judgement. Rename or reschedule them with
`update_trigger`, which keeps their run history — the name lives in the Routine,
not in this file. UX Designer is defined in `.claude/agents/frontend-ux-designer.md`;
change it with a commit.

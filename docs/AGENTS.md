# AGENTS

**Sentinel** and **Janitor** are the two scheduled Claude sessions that work on
this repo between hands-on sessions.

| | Sentinel | Janitor |
|---|---|---|
| **Does** | Watches the pipeline and reports what it sees | Clears one backlog item a day |
| **Runs** | 07:15 ET daily | 08:00 ET daily |
| **Reads** | `python -m scripts.pipeline_report --hours 24` | `docs/followups.md` |
| **Output** | A report every run, clean or not. A PR when it can fix something | A PR, the item ticked off, and a message to the user |
| **Cannot** | Change a model threshold. Push to master | Change a model threshold. Push to master. Take a `[needs-decision]` item |

**Full contract and guardrails: [`agents_contract.md`](agents_contract.md).**
**Janitor's worklist: [`followups.md`](followups.md).**

They are Routines (scheduled sessions), not cron jobs. The eleven cron jobs in
`scheduler.py` run fixed Python entry points and decide nothing; these two exist
for the work that needs judgement. Rename or reschedule them with
`update_trigger`, which keeps their run history — the name lives in the Routine,
not in this file.

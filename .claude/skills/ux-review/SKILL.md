---
name: ux-review
description: Run the front-end UX designer review on a change under mobile/src — the current branch's diff by default, or a PR number, branch, or explicit files. Use before opening a PR that touches a component or screen, or when asked to review front-end UX.
---

# /ux-review [pr-number | branch | file …] [--comment]

Runs the `frontend-ux-designer` agent on a front-end change and returns its
report. The agent is read-only; this command never edits code.

## Steps

1. **Resolve the target.**
   - No argument: the current branch against `origin/master`, plus uncommitted
     changes. Run `git fetch origin master` first so the base is current.
   - A number: that pull request in `mjacode/betting-model`. Read its head
     branch and changed files through the GitHub MCP tools.
   - A branch name: `git fetch origin <branch>` and diff it against
     `origin/master`.
   - File paths: exactly those files.
   If the resolved set contains nothing under `mobile/src`, say so in one line
   and stop. Do not review Python, docs or the dashboard here.

2. **Run the deterministic scan yourself first** so its output is in hand
   whether or not the agent finishes:
   ```
   node mobile/scripts/ux_scan.mts --changed
   ```
   (or with the explicit files). Quote it in the final reply.

3. **Launch the agent** with the Agent tool, `subagent_type: frontend-ux-designer`,
   in the foreground. Give it: the target as resolved, the list of changed
   front-end files, and the scan output. Tell it whether the Mobbin MCP server
   is connected in this session (check for any `mcp__Mobbin__*` or
   `mcp__mobbin__*` tool); if it is not, or it answers "requires a paid plan",
   tell the agent to say so and proceed on HIG and the app's conventions.

4. **Relay the report** to the user unchanged in substance: verdict, findings
   (severity, file:line, why, reference, change), scan output, then the four
   CLAUDE.md §0 headings. Do not summarise findings away; the agent's final
   message is not shown to the user, so what you relay is the deliverable.

5. **`--comment`** (only when passed): post the report as a single pull request
   review comment on the target PR through the GitHub MCP tools, ending with
   the Claude Code attribution footer. Never approve or request changes; the
   review is advisory and Matt decides.

## Not this command's job

Fixing findings. If the user wants them applied, that is a normal edit session
after the review, and the agent is re-run on the result.

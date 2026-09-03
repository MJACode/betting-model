---
paths:
  - "mobile/src/**"
  - "mobile/docs/**"
---

# Front-end changes

> Loaded only when Claude opens a file under `mobile/`, so it costs nothing on
> a session that never touches the app. Split out of CLAUDE.md §1b on
> 2026-09-03; the rule is unchanged.

**EVERY FRONT-END CHANGE IS REVIEWED BY THE UX DESIGNER AGENT BEFORE ITS PR
OPENS. ALWAYS. NOT "WHEN IT SEEMS WORTH IT".** (Matt, 2026-09-02.) Any change
that adds or edits a file under `mobile/src` — a component, a screen, a
user-facing helper in `lib/` — gets the `frontend-ux-designer` subagent run on
it (`/ux-review`, or the Agent tool with that type) and its findings addressed
or explicitly declined in the PR body, before the PR is opened. The agent reads
`mobile/docs/UX_REVIEW.md`, runs `node mobile/scripts/ux_scan.mts --changed`,
and pulls real references from the Mobbin MCP server; it reports and never
edits. Mobbin being unavailable is a status line in the report, not a reason to
skip the review. A front-end PR opened without the review in its body is
incomplete — the same way a threshold change without `Updated-By:` is.

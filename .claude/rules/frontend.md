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

**A HOOK REACHABLE FROM AN APP-ROOT COMPONENT MUST NOT USE `useFocusEffect`.**
(2026-09-06, found by the UX review, second occurrence of the shape.)
`useFocusEffect` calls `useNavigation()`, which THROWS — "Couldn't find a
navigation object" — when neither `NavigationContext` nor
`NavigationContainerRefContext` is in scope. `BetslipBar` and `ToastHost` are
mounted in `App.tsx` as SIBLINGS of `<NavigationContainer>`, deliberately, so
they cover the tabs and pushed screens alike. Every hook on their path is
therefore outside both contexts, and a focus-aware hook there crashes on render
— for `BetslipBar`, that is any user with something in their betslip, on every
screen.

Wiring live picks into `useResolvedSlip` did exactly this. The fix is a plain
`useEffect` variant for that path: `useLivePicksUnfocused` is the shape, and
`useTodayPicks` has always followed the rule for the same reason.

**`ux_scan` cannot catch this** — it has no cross-file reachability.
`tests/test_mobile_live_segment.py::test_no_app_root_component_reaches_a_focus_aware_hook`
walks the import graph symbol by symbol from `BetslipBar` and is the tripwire.
Add a new app-root component to that test's roots when you mount one.

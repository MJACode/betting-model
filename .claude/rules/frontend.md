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

**A GUARD THAT GREPS FOR A BANNED WORD DOES NOT CATCH THE SAME CLAIM MADE AS A
NUMBER.** (2026-09-06, Matt: *"Remove all paper trading. we are not doing paper
trading."*) `mobile/scripts/verify_live_record_start.ts` has banned "paper" in
`screens/` and `components/` since 2026-08-30 and passed on every run — while
four surfaces told members a model was **"not backed for real money until 50+
settled picks"**. That is CLAUDE.md §2's go-live gate quoted at them row by row:
the banned concept with the banned word removed.

So when you ban a concept from user copy, **ban the CONSTANT that computes it
too**, and sweep for the constant (`grep` its name) rather than for the wording
before calling a surface clean. `GO_LIVE_SETTLED_PICKS` no longer exists in the
app for exactly this reason; the gate still governs backing server-side
(`models/backtester.GO_LIVE_MIN_PICKS`), where it is not copy.
`verify_live_record_start.ts` now checks both halves, and the structural one —
the app defines no gate constant to render — is the half that holds.

**A rule's scope is not a complaint's scope.** The first fix at this was scoped
to in-play models, because §2 genuinely does exempt them from the gate. It was
still wrong: the objection was that the claim was being made at all, not about
which models were entitled to make it, and `ncaaf_spread` kept the line two rows
above the card in the same screenshot. When a fix is scoped by a RULE rather
than by the reported SYMPTOM, check the other rows on the same screen first.
Measured story: `docs/rules_evidence.md`.

**THE 1,000-ROW CAP IS A PROPERTY OF EVERY READ, NOT OF THE READS THAT HAVE
ALREADY BITTEN.** (2026-09-09, second occurrence.) Supabase caps every
PostgREST response at max-rows — 1,000 on this project — whatever `.limit()`
asks for, and says nothing: no error, no header the client reads. The
2026-09-04 fix paged the four all-books LINE reads and stopped there, so the
per-player leaderboard reads behind the Stats board kept returning an arbitrary
first 1,000 for another five days, at 12,850 rows for the NFL's last-10 and
54,687 for the NCAAF's. It surfaced only on the board that opens filtered to a
slate, as an EMPTY board — six of tonight's players survived the cut and not
one played the default stat.

Two halves, and the second is the one that was missed:

- **Drain the cap** — `fetchAllPages` with a deterministic order on the
  REQUEST, never the function body's own `ORDER BY`. `.range()`, `.order()`
  and `.in()` all chain onto `supabase.rpc()`, which returns a filter builder;
  PostgREST filters and pages a set-returning function exactly like a view.
- **Then don't ask for what the screen will throw away.** A board already
  filtered to a slate asks the SERVER for that slate (`statsBoard.slateTeams`).
  Paging a 54,687-row read onto a phone to render one game is a second bug
  wearing the first one's fix.

**A SERVER NARROWING ONLY REPLACES A CLIENT FILTER WHEN THE ROW MEANS THE SAME
THING.** `.in('team', …)` is exact on a read that returns ONE ROW PER PLAYER
(`player_window_totals_*`, `player_season_stat_values_*` — `team` there is
already `(array_agg(team ORDER BY game_date DESC))[1]`, the row the board groups
to). On a read that returns one row per GAME it filters GAMES while the board
filters PLAYERS, and the two then disagree for everyone who changed team inside
the window — in BOTH directions: a traded player's last-10 is silently cut to
his games for tonight's team, and a player who LEFT that team is admitted to its
board. Neither is visible; the row prints "3 of 5" under a chip that says L10.
Narrow a per-game read through the FUNCTION instead (`p_teams`, filtering the
ranked CTE on `rn = 1`), and if the parameter is new, DROP the old signature in
the same DO block — an added argument makes an OVERLOAD, and a call carrying
only the old arguments then matches both, which PostgREST answers with 300
Multiple Choices for every app build already in the field.

The guard for this had already been written and it PASSED: every row in its
fixture carried one team. **When you assert that two filters agree, the fixture
must contain the population they can disagree about** — §7's blind-spot rule in
its narrowing-shaped form.

**BEFORE ADDING A READ, GET ITS ROW COUNT FROM PRODUCTION.** Not its shape, not
"a few hundred rows" in the docstring above it — the count, on the biggest day
it will ever have. Four of these carried a comment saying the set was small.

**AND NAME THE RELATION AT THE `.from(...)`, NEVER THROUGH A VARIABLE.**
`tests/test_anon_readable.py` parses literal relation names out of `mobile/src`
to check the read surface against `data/anon_readable.py`. A view picked by a
ternary is one it cannot see: `v_player_season_totals_nfl` and `_ncaaf` sat
outside the manifest from the day they shipped and would have lost anon SELECT
the moment the default grant is revoked — silently, as an empty screen, which
is the failure mode that manifest exists to end.

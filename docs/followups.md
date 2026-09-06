# Follow-ups

> **The durable backlog.** Anyone can add to it any time, and items are cleared
> in ordinary working sessions — pick one up when a session has room.
>
> **There is no longer an agent that does this.** Janitor was retired
> 2026-09-03 after four runs finished SUCCEEDED having landed nothing at all;
> it had no way to get work out of its sandbox. `docs/agents_contract.md` has
> the measurements and the routes that were tried, so nobody rebuilds it.
>
> **Why a file:** a task list that lives only in a chat is gone the moment the
> session ends. Four small fixes below were flagged in three separate sessions
> and never done, because each time they lost to a larger ask and nothing
> carried them forward. Same reasoning as CLAUDE.md §1b. That reasoning is
> UNCHANGED by the retirement — the file was always the memory; the agent was
> only ever one possible reader of it.
>
> **Format:** one `## Item` per task. `[needs-decision]` means blocked on a
> human. Tick with `- [x]` and leave it in place for one week so a reader can
> see what recently changed, then delete.

---

## [ ] [needs-decision] Two merged mobile changes are undelivered until the 1.1.0 native build ships

Found 2026-09-05 (session 239), checking whether the calibration removal had
actually reached users rather than trusting a green workflow.

**#504 bumped `mobile/app.json` to version 1.1.0** to ship
`LSApplicationQueriesSchemes` (an Info.plist key only a new binary can carry).
`runtimeVersion` policy is `appVersion`, so **every OTA now targets runtime
1.1.0, and every installed binary is 1.0.0.** Nothing picks them up.

The evidence, from the run history:

- **OTA run #71** (#504) **failed** — correctly. The workflow hard-fails any push
  that moves `mobile/package.json` or `mobile/app.json`, because an OTA cannot
  add native config to an installed binary.
- **OTA run #72** (#503, the calibration removal) **succeeded** — but only because
  that squash commit did not itself touch `app.json`; the bump was already on
  master. The guard only inspects the current push. It published a bundle to a
  runtime version nobody is running.

So the guard did its job for #504 and was structurally unable to catch #503.
Nothing is broken and nothing is lost — both changes wait on master — but
**a green OTA run is not proof of delivery while `version` is ahead of the
shipped binary**, and that is not obvious from the workflow's output.

**Unblocks both:** run `mobile-build.yml` for the 1.1.0 native build, ship it,
and the already-published bundle applies on install. Matt's call — it is a
TestFlight / App Store path.

**Worth fixing while there:** the OTA job could compare `app.json`'s `version`
against the last native build tag and warn (not fail) when it publishes to a
runtime no released binary matches. That is the check that would have said
"published, but to nobody" on run #72.

---

## [ ] [needs-decision] The Explainer's "Why we're different" no longer differentiates

Found 2026-09-05 (session 239), in the UX review of the calibration removal.
**Matt: "I will add new content later."** Left as-is deliberately, waiting on him.

The section used to claim a different OBJECTIVE FUNCTION — most services sell
accuracy, we optimise for calibration — with an external citation behind it.
Calibration came out of the UI, so the rewrite argues from the published record
instead. That is true, but it is the third place the app says it: the Track
Record subtitle ("Nothing hidden, nothing cherry-picked") and its "Read this
first" card already do. A differentiator that restates a promise made twice
elsewhere is not one.

**Two replacements that are true and genuinely unusual**, if he wants a starting
point rather than a blank page:

- **CLV as the skill metric.** "Beat the close" is already computed, already on
  the Record screen, and is the one number that separates edge from variance.
  Almost no consumer picks product publishes it.
- **The pick rule (CLAUDE.md §1c).** "A pick is a pick" — once written, the
  number never changes, even when the line moves against us. That is a real,
  checkable commitment competitors do not make, and the app already enforces it.

Touch `mobile/src/screens/ExplainerScreen.tsx`, the section headed "Why we're
different — the whole record, not one number".

---

## [ ] Dead code: OpeningComparisonScreen has no entry point

Found 2026-09-05 (session 239a). The Record tab's "Experiment: lock our first
signal vs chase the live line" link was that screen's ONLY route in, and it was
removed at Matt's request.

Still shipping in the bundle with no way to reach it: `OpeningComparisonScreen.tsx`
(~200 lines), the `OpeningComparison` route in `App.tsx` (annotated in the
`SignIn` style so it does not read as live), the `OpeningComparison` key in
`RootStackParamList`, and `fetchOpeningVsLive` / `fetchOpeningSlices` plus
`OpeningVsLiveRow` / `OpeningSliceRow` in `queries.ts` / `types/index.ts`.

**The shadow track itself is unaffected** — it keeps running server-side and
keeps its own window (`docs/opening_signals.md`). This is only about whether the
screen stays compiled. Matt's call: delete the lot, or restore one entry point.

---

## [ ] Two icon-only buttons in Settings are silent to VoiceOver

Found 2026-09-05 (session 239), by `ux_scan.mts` — the only two BLOCKER-level
findings in the app.

`mobile/src/screens/SettingsScreen.tsx:423` and `:434` are icon-only
`<Pressable>`s with no `accessibilityLabel`, so a screen-reader user hears
nothing at all. Pre-existing and byte-identical on master, which is why they were
declined on the calibration PR rather than fixed there — but they are real, and
the fix is one prop each.

While in that file, `ExplainerScreen.tsx:414` carries a `fontSize: 13` literal
that should be `font.size.*`.

---

## [ ] Nothing tells us when a market we pruned starts being priced

Found 2026-09-05 (session 237), in the UX review of the college prop prune.

`FOOTBALL_MARKET_NOT_PRICED` (mobile) and the pruned entries in
`config.PROP_MARKETS_NCAAF` / `PROP_ALT_MARKETS['NCAAF']` are a hand-maintained
mirror of one coverage probe. **They are measurements with no drift
detection.** If college books start posting carries or sacks mid-season —
plausible; the pro market prices both — nothing notices. We stop asking, so no
rows appear; no rows appear, so nobody looks. The column stays dark until a
person happens to re-run `scripts/probe_market_coverage.py`.

Same shape as the gap the probe was built to close (CLAUDE.md §1b: the current
state of a system is not its capability), one level up: we have now written our
belief about the market into config, where it will age silently.

**Cheap version:** a scheduled job that re-probes each sport's pruned keys
weekly — one market per call, a handful of credits — and posts to Discord when
one comes back served. The probe already reports exactly this and writes
nothing; it needs a caller and a comparison against the pruned list.

**Related, same session, same file to touch:** neither prop ingestor writes to
`api_call_log` (both use bare `requests.get` with only `record_quota_headers`),
so **prop credit spend is invisible in that table for every sport**. Today's
590-credit college pass had to be read out of the Railway worker log. Worth
doing at the same time — both are about a measurement that exists nowhere
queryable. Detail in `docs/market_coverage.md`.

---

## [ ] [needs-decision] The pre-game line poller deletes a game's non-BET PROP picks

Found 2026-09-03 (session 185) while tracing why the Stats board's ODDS column
was empty for players DraftKings was pricing.

`data/ingestors/pregame_line_poller.py` calls `run_scorer(only_games=…)` every
time DK's number on a game moves. The game scorer's non-BET housekeeping delete
(`models/scorer.py`, "Housekeeping for the pairs the lock deliberately leaves
open") is scoped by `game_id` and not by model, so it removes that game's PROP
`NONE` and `AVOID` rows as well — and `run_scorer` never re-creates them,
because prop scoring is a separate function that only runs on the hourly pass.
`picks_log` for 2026-09-03 shows it plainly: INSERT 36 batter-hits rows at :20,
DELETE 36 at :24, nothing until the next hour.

**Measured.** Prop non-BET deletes per day: 0 on 2026-08-28 and 08-29, then
8,467 / 23,047 / 15,841 / 15,718 on 08-30 → 09-02 — the step is the day the
poller shipped. **No prop BET row was deleted** in that window, so §1c holds for
the bet of record; what churns is the dead-zone and AVOID population.

**Why it is not just "delete the delete".** `_locked_prop_keys` locks on ANY
unsettled row including `NONE`, so nothing else un-locks a dead-zone player. Stop
the delete and a player who was in the dead zone at 10am can never later cross
into a BET — a worse bug than the one being fixed.

**The likely fix, and why it needs a human.** Lock props on `BET` only, matching
the game lock's own rule ("no pick because bad number, then it drifts into pick
territory, is a pick we should take"), and let the prop scorers delete-and-rescore
their own non-BET rows each pass. That changes which picks fire, so under §1b it
is a model update and needs `Updated-By:` — **whose call it is has not been
asked.** Do not ship it from the backlog.

The app-side symptom is already gone: the Stats ODDS column reads
`v_latest_prop_odds_all_books` as of session 185, so a missing prop row no
longer blanks the price.

---

## [ ] 145 pressables are silent or roleless for VoiceOver

Found 2026-09-02 by the first run of `node mobile/scripts/ux_scan.mts --all`
(the deterministic half of the front-end UX review, `mobile/docs/UX_REVIEW.md`
§5): **145 `Pressable`/`Touchable*` tags across 47 files carry neither
`accessibilityRole` nor `accessibilityLabel`. 20 of them are icon-only**, so
VoiceOver has nothing to read at all — the Ionicons glyph is not text — and
the control does not exist for a screen-reader user. The other 125 have a
`<Text>` child, so the label is read but the role is not: "Track" instead of
"Track, button". Both are Apple HIG failures; the icon-only ones are the
Blockers.

Where they are (icon-only first):

| file | icon-only | all |
|---|---|---|
| `screens/StatsScreen.tsx` | 3 | 9 |
| `screens/ModelEditScreen.tsx` | 2 | 13 |
| `screens/SettingsScreen.tsx` | 2 | 7 |
| `screens/ModelsScreen.tsx` | 2 | 5 |
| `screens/PlayerStatsScreen.tsx` | 2 | 5 |
| `components/ParlayLegCard.tsx` | 2 | 2 |
| `screens/ParlayScreen.tsx` | 1 | 11 |
| `components/ParlayDkHandoff.tsx` | 1 | 3 |

Fix, per tag: `accessibilityRole="button"` on every one; `accessibilityLabel`
on the icon-only ones saying what the tap does ("Open settings", "Add to
betslip", "Remove leg"), not what the icon is. `TrackButton.tsx` is the
existing pattern. Where an `Ionicons` sits beside text inside a pressable,
mark it decorative with `accessibilityElementsHidden` so it is not read
before the label. Do not add `accessible={false}` to make the scan quiet.

Mechanical, but not one sitting: it touches ~47 files and the OTA ships it to
every installed build, so do it a few screens per PR, highest-traffic first
(Picks board, Live, Pick detail, Betslip), run `/ux-review` on each PR, and
finish with `node mobile/scripts/ux_scan.mts --all | grep -c a11y-pressable`
reading 0. JS-only, so each merge goes out over the air; no native rebuild.

Same source flagged a second pattern, smaller and separate: a fixed
`height: 48` on the primary button in `PaywallScreen`, `SignInScreen`,
`DiscordLinkModal`, `ConnectSportsbookScreen` and `SignalLockCard` clips the
label under Dynamic Type. `minHeight` plus vertical padding fixes each; five
edits, one PR.

## [x] `mlb_prop_batter_hits` — dormant, and losing when it fires

Surfaced by the first ModelCalibration sweep (2026-09-02): unpaused, 5,661
settled, `cur_n = 0`. Investigated 2026-09-03. It is DORMANT, not a broken feed
— it scored 460 rows on 1–2 Sept and `player_game_log` is continuous — so §7's
"a dormant model and a broken feed look identical" resolves to the dormant side.

**Its predictions compressed, on an unchanged artifact.** `model_registry` shows
one active version since 2026-06-21, never swapped. Two UNCENSORED windows
either side (both with NONE rows present, so like-for-like):

| window | n | sd | p95 | p99.9 | max | ≥0.78 |
|---|---|---|---|---|---|---|
| 06-21→06-25 | 1,457 | 0.1394 | 0.757 | 0.944 | 0.950 | 53 (3.64%) |
| 08-10→09-02 | 8,026 | 0.1020 | 0.657 | 0.774 | 0.795 | 8 (0.10%) |

Same model file, 36x fewer rows clearing the 0.78 prob cut. The break is sharp
at **2026-07-23**: daily max prob ran 0.87–0.99 with BETs every day up to
07-22, and never exceeded 0.795 afterwards. The cut did not move (0.78/0.17
since 2026-06-28), so this is the inputs losing discriminative power, not a
threshold change. Which feature is the open question — the repo's git history
starts 2026-08-27, so there is no code history for July, and identifying it
needs the feature engine run for one date either side of 07-23 (a worker job:
no DATABASE_URL in a dev sandbox).

**Do NOT chase the volume back.** Realised record, 521 settled BETs, flat $100
(`profit_flat` is exactly -100 on every loss, so flat ROI = sum/(n*100) —
dividing by `recommended_bet` mixes flat profit with a Kelly stake and gives a
nonsense -127%):

| bucket | bets | win% | breakeven% | avg odds | flat ROI |
|---|---|---|---|---|---|
| blocked by the -140 floor | 401 | 65.1 | 67.9 | -225 | **-3.89%** |
| passes the -140 floor | 120 | 40.0 | 50.1 | +3 | **-21.16%** |
| all | 521 | 59.3 | 63.8 | -172 | **-7.87%** |

**The -140 floor keeps the WORSE half for this model.** The slice it admits lost
-21.2%; the slice it blocks lost -3.9%. That inverts the floor's purpose here
(on `mlb_prop_batter_rbi` the same floor capped 36 bets at +7.3% vs +2.2%
uncapped), so it is a per-model fact, not a general one.

So the dormancy is currently PROTECTIVE, and that is the risk: the model is
unpaused, and if its distribution ever un-compresses it resumes betting the
-21% slice with nobody deciding to.

The sweep's "best" cell (29 bets, +19%) is not a way out — its verdict was
"FAILS THE TIME SPLIT (19.5% then None%)": the second half has no bets at all,
so it is fitting the pre-07-23 period that no longer exists.

**Decision needed (a model update — needs `Updated-By: <person>` per §1b):**
1. PAUSE or RETIRE it. config's own comment has called it a retrain candidate
   since 2026-06-21; it has now lost $4,098 at flat $100 over 521 bets.
2. Or retrain first, then decide — the features (rolling form, prior-season
   Savant, batting order, opp team ERA) are the same ones that stopped
   discriminating on 07-23, so a retrain without finding that cause may
   reproduce it.
Leaving it live and dormant is the one option with a hidden downside.

**DECIDED 2026-09-03 (mike): PAUSED.** Option 1. `PAUSED_MODELS` in
`config.py`, with the evidence above kept alongside the entry; thresholds
left in the dicts for the unpause. Unpause path is a retrain, but find the
2026-07-23 cause FIRST — the features that stopped discriminating are the
ones a retrain would re-fit, so retraining blind may reproduce it. That
still needs the feature engine run for one date either side of 07-23, which
is a worker job (no `DATABASE_URL` in a dev sandbox).

## [ ] `my_access()` is called by the app and does not exist in production

Found 2026-09-04 in session 208 while enumerating the function grant surface.
`mobile/src/lib/discord.ts:157` calls `supabase.rpc('my_access')` and
`fetchAccess()` does `if (error) throw error` — it does not fail soft. But
`my_access()` is **absent from `pg_proc`**: it and `has_app_access()` are defined
only in `data/migrations/add_discord_link_and_whop_memberships.sql`, which has
**never been applied**. `has_active_subscription()` — the function that migration
supersedes — is the one that actually exists.

CLAUDE.md §6 states the gate is `public.my_access()` / `has_app_access()`. That
is the intended design, not the deployed one, and the difference has never been
written down.

**What needs deciding:** whether to apply that migration (it also creates the
Discord-link and Whop-membership tables), or to change the app. Not touched here
— it is the entitlement path, and applying a never-run migration that creates
billing-adjacent tables is not a side effect of a grant change.

Note it does NOT block the grant work: the migration already carries its own
`REVOKE ALL ... FROM PUBLIC, anon, authenticated` plus
`GRANT EXECUTE ... TO authenticated`, so it stays correct now the default
privilege is revoked.

## [x] Default privileges still hand anon EXECUTE on every new function

Found 2026-09-03 in session 206, alongside the table fix. `pg_default_acl`
carries three entries for `public` from grantor `postgres`:

    objtype r (tables/views)  anon=arwdDxtm   <- REVOKED 2026-09-03
    objtype S (sequences)     anon=rwU        <- still there
    objtype f (functions)     anon=X          <- still there

So every new function in `public` is still callable by `anon` the moment it
exists. That is how five `SECURITY DEFINER` `feedback_*` RPCs ended up
anon-callable — intended in that case, but nobody granted it.

**DONE 2026-09-04 in session 208** (mike: *"do the function grants too"*), with
exactly that treatment: `RPC_ANON_CALLABLE` in `data/anon_readable.py`, a test
against `mobile/src`, and grants generated from it.

**And "the 17 the app calls" was wrong — it is 24.** Four call sites in
`queries.ts` build the name at runtime (`const fn = sport === 'NFL' ? ... : ...`),
so a literal grep for `.rpc('...')` misses eight functions the app reaches
through a ternary. Sweeping on the literal list would have revoked EXECUTE on
the NBA, WNBA, NCAAF and NFL stats functions — silently. The test resolves both
forms and has its own guard-the-guard case, because a resolver that stops
resolving fails OPEN: the surface looks smaller and the sweep gets bolder.

Also caught: `_jsonb_text_array` must stay granted even though the app never
names it. `custom_model_picks` and `custom_model_backtest` are SECURITY INVOKER
and both call it, so the CALLER needs EXECUTE.

**Completed 2026-09-04 in session 210** (mike: *"sweep the PUBLIC grant off the
19 stats rpcs"*). Session 208 named PUBLIC in the two REVOKEs but not on the 25
it was GRANTing, so the explicit `anon, authenticated` grant sat on top of a
PUBLIC grant that was still there on **20** of them — decoration. The apply now
does `REVOKE ALL ON FUNCTION ... FROM PUBLIC` before each GRANT (order pinned by
a test), and a third in-transaction read-back rolls the whole apply back if
PUBLIC still holds anything on a declared callable. Verified in `pg_proc` after
the run: callable-by-PUBLIC **21 -> 1**, the one being `log_picks_changes()`,
left alone on purpose.

Sequences remain deliberately untouched: `tracked_bets.id` defaults to
`nextval('tracked_bets_id_seq')` and anon holds USAGE/UPDATE on it, so closing
the sequence default would break the next app-writable table's INSERT on its own
primary key.

Sequences are the low-stakes third: `w` on a sequence is `nextval`/`setval`, and
nothing reads a sequence through PostgREST here.

**Also still open, and NOT fixable from this project:** the `supabase_admin`
default-ACL entry for `public` tables grants `anon=arwdDxtm` too. Altering it
needs membership in `supabase_admin`, which `postgres` does not have on a
managed project. Nothing in this repo creates tables as that role, so it is
latent rather than live.

## [x] RLS is off on `worker_jobs` and `odds_history_pulls`

Found 2026-09-01 by `get_advisors(security)`, which reports both at **ERROR**
level: "is public, but RLS has not been enabled."

**IT IS AN OPEN DOOR. This item said it was not, and that was wrong** (corrected
2026-09-03, session 205, while fixing the `odds` grant next door).

`pg_class.relacl` on both tables reads
`{postgres=arwdDxtm/postgres,anon=arwdDxtm/postgres,authenticated=arwdDxtm/postgres,service_role=arwdDxtm/postgres}`
and `has_table_privilege('anon', ..., 'INSERT')` returns **true**. With RLS off
there is nothing behind that, so anon -- the key shipped inside the app -- could
INSERT into `worker_jobs`, the queue the Railway worker claims and executes every
five minutes.

**Why the check below said otherwise:** `information_schema.role_table_grants`
only shows grants the CURRENT role can see. It returns 0 rows for `odds` too --
a table whose relacl demonstrably reads `anon=arwdDxtm`. So 0 rows meant "you
cannot see them", not "they do not exist". `relacl` and `has_table_privilege()`
are the authoritative reads. This is §7's "read the result, not the intent" in
its other form: a null result was read as evidence of absence.

**REVOKEd 2026-09-03** (`data/migrations/tighten_anon_write_grants.sql`), so the
grant is gone and the door is shut. **Still open: enabling RLS on both**, as the
second lock. It was deliberately NOT done in the same migration -- RLS with no
policy locks out every connection that is not the table owner, and the worker's
role has not been verified to be that owner; the revoke closes the hole without
gambling the job queue.

**DONE 2026-09-04 in session 211** (mike: *"enable rls on those three tables"*),
on all three -- `model_artifacts` joined the two named here, because it has the
same shape and the same on-demand creation.

**The open question this item flagged is answered: the worker IS the owner.**
"the worker's role has not been verified to be that owner" was the stated reason
for not doing it in the same migration. Measured: all three are owned by
`postgres`, `postgres` has `rolbypassrls` **and** owns them (exempt twice over),
`service_role` also has `rolbypassrls`, and `pg_stat_activity` shows the worker's
connections as `usename=postgres` via Supavisor. No view or matview selects from
any of the three (`pg_depend` -> `pg_rewrite`), and `mobile/src` never names
them. `FORCE ROW LEVEL SECURITY` -- the variant that WOULD subject the owner to
the policies -- is deliberately not used, and a test pins that.

**NOT run once as a migration, and the reason is this file's own next paragraph
plus a third data point.** All three tables are created on demand by the code
that writes them, so a migration is undone by the next run against a database
where the table does not yet exist -- which is exactly how `model_artifacts` came
back with the full anon grant between two sweeps hours apart. So the pair lives
beside each CREATE, through `data/anon_readable.py::lock_down(conn, table)`,
which carries the `schema_is_current` gate INTERNALLY as the paragraph below
requires. The gate is inside the helper rather than at each call site so a new
caller cannot forget it; `lock_down_sql()` is the ungated builder, for the admin
script and the tests only.

**Verified after the apply, three ways.** `pg_class`: RLS on, `FORCE` off, 0
policies, anon/authenticated hold nothing on all three. `get_advisors(security)`:
the two ERROR-level `rls_disabled_in_public` lints are **gone** and all three now
report `rls_enabled_no_policy` at INFO -- the locked shape this file's last
paragraph says is expected. And `scripts/verify_worker_rls.py` on the worker
itself (it cannot run anywhere else -- the Supabase MCP is
`supabase_read_only_user` and `SET LOCAL ROLE postgres` is denied):

    connected as 'postgres', rolbypassrls=True
    model_artifacts:     rls=True owner=postgres rows_visible=4
    odds_history_pulls:  rls=True owner=postgres rows_visible=1042
    worker_jobs:         rls=True owner=postgres rows_visible=15
    worker_jobs write probe: insert/read-back/update/delete all succeeded

Row counts matter more than the absence of an exception: a non-exempt role gets
**zero rows**, not an error, so a SELECT returning the count already known to be
there is what proves exemption. All rolled back.

Two follow-on fixes the change forced, both worth knowing:

- `job_queue.ensure_schema`'s `schema_is_current(...)` early-return fires BEFORE
  the lock-down, so without `rls=True, revoked_from=API_ROLES` it answers True on
  a still-open table and the lock-down never runs. A guard that dead code can
  satisfy.
- `tests/test_ddl_guard.py` now treats `lock_down(` as a guarded path rather than
  exempting each caller, with its own guard-the-guard case: if `lock_down` stops
  calling `schema_is_current`, every caller silently becomes an unguarded DDL
  site while the offender test keeps passing.

**AND THEN THE REST, 2026-09-04 in session 212** (mike: *"do the remaining seven
too"*). It was **eight** -- my seven was an hour stale and `nfl_odds_cache_backup`
had arrived in between. The invariant now holds schema-wide:

    0 of 84 public base tables have RLS off
    0 have FORCE RLS on

`brand_assets` turned out to be a fourth CREATE SITE (`fetch_brand_avatar.py`)
rather than an archive; the other seven have no create site and are swept by the
admin script only. They are locked rather than dropped because a repair is
reversible only while its backup exists -- retention is a separate decision.

**A NEW OPEN DOOR OF THE SAME SHAPE, FOUND WHILE VERIFYING THIS ONE:**
`game_weather` grants anon INSERT/UPDATE/DELETE while its only anon policies are
SELECT (`allow anon read`, `anon read game_weather`, plus `service_role_all`). So
the writes are **inert today** -- RLS denies them -- but the ACL does not match
intent, and that is precisely the "one lock, and it is an ACL" state this section
exists to complain about. The session-205 sweep missed it.

Safe to close: `mobile/src` only ever SELECTs `game_weather` (three call sites in
`queries.ts`), and every writer is server-side over `postgres`
(`data/ingestors/weather_ingestor.py` and the feature engines). Fix is
`REVOKE INSERT, UPDATE, DELETE ON game_weather FROM anon, authenticated`, or
adding it to a declared write surface if anon really should write weather.

Worth re-running the same query against the other three anon-writable tables
whenever this is touched -- `device_push_tokens`, `feedback` and `tracked_bets`
all hold write grants wider than their policies (DELETE on the first two, UPDATE
on all three), inert for the same reason:

```sql
select c.relname,
       has_table_privilege('anon', c.oid, 'INSERT') as ins,
       has_table_privilege('anon', c.oid, 'UPDATE') as upd,
       has_table_privilege('anon', c.oid, 'DELETE') as del,
       (select string_agg(p.polname||':'||p.polcmd::text, ', ')
          from pg_policy p where p.polrelid = c.oid) as policies
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r'
  and has_table_privilege('anon', c.oid, 'INSERT,UPDATE,DELETE');
```

The superseded check, kept so nobody re-runs it and re-reaches the wrong answer:

```sql
select table_name, grantee, privilege_type
from information_schema.role_table_grants
where table_schema='public'
  and table_name in ('worker_jobs','odds_history_pulls')
  and grantee in ('anon','authenticated');
-- 0 rows
```

Neither role holds a single table privilege, so PostgREST cannot read or write
either table however the advisor grades it. What is missing is the second lock,
not the first — and §7's rule is that the grant is the thing to check, not the
lint's intent ("run `get_advisors(security)` after every migration and read the
result, not the intent").

Why it still matters enough to do: `worker_jobs` is the queue the Railway worker
CLAIMS AND EXECUTES every five minutes (`tracking/job_queue.py`). A future
migration that grants `anon` INSERT — or a `GRANT ... ON ALL TABLES` that sweeps
it up — turns a missing RLS policy into arbitrary job execution on the container
holding `ODDS_API_KEY`, `DATABASE_URL` and open egress. That is the one table in
this repo where defence in depth is worth the two lines.

Fix: `ALTER TABLE public.worker_jobs ENABLE ROW LEVEL SECURITY;` and the same for
`odds_history_pulls`, with NO policy (so the tables stay service-role only, which
is what they already are in practice), then re-run `get_advisors(security)` and
confirm both ERRORs clear. Add the statements to `supabase/` alongside the other
migrations so a rebuilt project carries them.

**Run it ONCE, as a migration — never in application code.** #389 measured what
that statement costs on this database: `ALTER TABLE ... ENABLE ROW LEVEL
SECURITY` takes ACCESS EXCLUSIVE *whether or not RLS is already on*, and fires
Supabase's `pgrst_ddl_watch`, which 503s the whole app while PostgREST rebuilds
its schema cache. It ran 1,676 times at a 7.8s mean from code that assumed it
was a free no-op. So: a one-time migration is correct and cheap; the same line
inside a function that runs per call is the outage. If you do put it behind
code, guard it with `data.ddl_guard.schema_is_current(...)` as the seven modules
in #389 now do.

Note while you are there: 30 further tables report `rls_enabled_no_policy` at
INFO. That lint is the *opposite* shape — RLS on, no policy, i.e. locked — and is
expected for service-role tables. Do not "fix" those by adding policies.

## [x] `commence_time` is ~16-20 minutes LATER than the actual first pitch

**Done 2026-09-01 in session 166** — `data/first_pitch.py`, `games.first_pitch_at`,
the COALESCE at all three guard sites, and two queued jobs to derive and repair.
The open question (feed artefact vs genuine drift) is unchanged and still needs a
timestamped play source.

**Finished 2026-09-03 in session 204**, because it was closed a call site short
and a clamp short:

- `_is_pregame_snapshot` GAINED the `first_pitch_at` parameter in session 166
  and **not one of its five callers ever passed it** — the guard was wired but
  never armed. All four feature engines now do (measured: zero game-level keys
  change today).
- Three readers had hand-copied `pregame_cutoff_sql()`'s output instead of
  calling it, so they could not inherit a fix to it. All three call it now.
- The prop PRICE read — the one that decides a bet — was not on the list at all.
  It is now, via `_pregame_cutoff_map`, and 49% of player+market keys were
  pricing inside the window.
- **The derivation needed a sanity clamp.** 7 of 415 games derive a first pitch
  hours early (a doubleheader matched to the wrong game); `relabel_in_play` had
  already marked 6,565 genuinely pre-game rows as in_play on the strength of it.
  See `SUSPICIOUS_EARLY_MINUTES`.

**The 6,565 mislabelled rows are repaired** (mike, 2026-09-03: "run the repair
and merge to master"). `scripts/repair_bogus_first_pitch_labels.py` ran on the
worker; verified by query, not by log: the backup table
`odds_pre_first_pitch_relabel_20260903` holds all 6,565 rows with their
original `in_play` value, those rows now read `open`, none remain mislabelled,
and the 33,091 `in_play`-before-scheduled-start rows on other games (the live
loop's own, correct population) were not touched.

mike, 2026-09-01: "should be commence time." He is right, and the direction is
the opposite of what I assumed when I raised it.

Measured over the 413 games with live state coverage (2026-07 onward): the first
`live_game_state` row with `abstract_game_state='Live'` lands on average **19.5
minutes BEFORE** `games.commence_time`, median 15.9 minutes before. Only 4 of
413 games began after their commence_time.

So the boundary every pre-game read uses -- `snapshot_at <= commence_time`, the
§7 rule -- is systematically too late, and odds rows inside that window are
treated as pre-game while the game is already under way. This is a leak in the
PERMISSIVE direction, and it is the explanation for the 48,712 rows labelled
`in_play` by the live loop (correctly, from game state) whose timestamp is at or
before their commence_time.

What to build:
- `games.first_pitch_at`, derived from `MIN(snapshot_at)` over
  `live_game_state` where `abstract_game_state='Live'`, per game.
- Make the pre-game guard prefer it: `COALESCE(first_pitch_at, commence_time)`.
  `features/feature_engine._is_pregame_snapshot` and
  `features/market_movement.load_market_movement` are the two call sites, plus
  `data/ingestors/odds_ingestor._mark_in_play`.
- Do NOT overwrite `commence_time`. It is the scheduled time, the app shows it,
  and the schedule is the right thing to show.
- Coverage is 2026-07 onward only, so `first_pitch_at` will be NULL for
  everything older. The COALESCE handles that, and the guard already fails open.

Whether the ~19-minute gap is a feed artefact (the API marking a game Live
during warmups) or a genuine commence_time drift is worth one query before
building: compare `first_pitch_at` against the first PLAY, if a timestamped
play source can be found. `plays` carries no timestamp today.

## [ ] Market-aware MLB model, now trainable on three seasons instead of one

Blocked until the 2024/2025/2026 historical backfill finishes (declared jobs
`mlb-history-2024`, `-2025`, `-2026-preaug`; watch `odds_history_pulls`).

`features/market_movement.py` computes nine columns and NO model consumes them.
Before 2026-09-01 that was forced: movement existed for 1,906 MLB games, all in
2026, disjoint from where the game models train. The backfill removes that
constraint -- 2024, 2025 and 2026 at two snapshots a day across seven books.

The plan is in `docs/market_movement_features.md` and one thing in it is now
out of date: it says "a new model trained on 2026 alone". It should be
2024-2026, with a chronological split, compared against the incumbent on the
same games.

Check coverage per season before training. A season where the backfill hit its
credit cap is a season with a hole in it, and `stopped_early` in the job result
says so.

## [x] Opposing-starter retrain, as a cloud job rather than a handover

**Done 2026-09-01 in session 166.** All five baselines trained ON THE WORKER via
`jobs/declared_jobs.json`, register=false, seasons 2020-2024, holdout 2025:

| model | holdout_ou_acc | MAE | repo artifact for comparison |
|---|---|---|---|
| hits  | 0.6046 | 0.6861 | 0.6043 / 0.6858 (2019-2024, holdout 2025) |
| tb    | 0.5963 | 1.3269 | 0.5963 / 1.3268 (2019-2024, holdout 2025) |
| runs  | 0.6370 | 0.5662 | 0.6370 / 0.5662 (2019-2024, holdout 2025) |
| rbi   | 0.7082 | 0.6148 | 0.7121 / 0.6199 (2019-2023, holdout 2024) |
| walks | 0.7277 | 0.4501 | 0.7281 / 0.4496 (2019-2023, holdout 2024) |

**Dropping 2019 costs nothing.** hits, tb and runs come back identical to their
2019-2024 artifacts to four decimal places, which settles the one open worry
about pinning 2020-2024 for the activation: the seasons are interchangeable and
only the opposing-starter columns will differ.

Step 2 of the runbook is now unblocked: apply
`docs/patches/activate_opp_starter_features.patch`, queue the same five jobs
with register=true, and compare against the table above.

## [ ] (superseded) Opposing-starter retrain — original handover wording

`docs/activate_opp_starter_features.md` has the patch and the runbook, and it
has been "run these five commands on your machine" for a day. It should be a
`retrain_model` declaration in `jobs/declared_jobs.json` -- the queue exists
now, and `model_artifacts` means the resulting `.pkl` survives the container.

Order matters and the runbook has it: baselines FIRST (register=false, seasons
2020-2024, holdout 2025, current features), then apply the patch, then the real
runs. Comparing a patched model against the artifact in the repo measures two
changes at once.

## [ ] [needs-decision] `DATAGOLF_API_KEY` is not set on either Railway service

Golf has been silently skipping on every pass — `Golf: DATAGOLF_API_KEY not set
— skipping golf step`, three times per refresh (ingest, ingest, scorer). The
variable is absent from both the `worker` and `pollers` variable lists, though
CLAUDE.md §6 lists it as a worker secret, so it was dropped rather than never
added.

This is a SEPARATE outage from the 2026-08-31 database break and predates it.
Found while diagnosing that one; not fixed here because only Matt can supply
the key, and whether the golf models should be running at all right now is his
call, not an agent's. Evidence: worker deploy logs, any refresh pass.

## [x] `nhl-api-py` is not installed on the worker

**The premise was wrong, and the warning was the thing lying.** `nhl-api-py`
3.3.0 WAS installed and had been pinned in `requirements.txt` from the start.
Its module is `nhlpy`; `nhl_stats_ingestor.py` imported `nhl_api` and
`nhl_api_py`, so both spellings raised `ImportError` and the "not installed"
warning fired on every pass forever.

Nothing was broken behind it: neither imported handle was ever read, and the
`NHL_API_AVAILABLE` flag it set was referenced nowhere in the repo. The
ingestor calls `api-web.nhle.com` and `api.nhle.com` directly for everything.
The whole block was dead code whose only output was a daily error naming a
cause that did not exist — and it cost a follow-up item chasing a missing
dependency that was never missing.

Same shape as the NFL wind card failing behind a comment saying it could not:
an error message is a claim, and a claim nothing verifies goes stale pointing
at the wrong thing.

Fixed 2026-09-03: dead block and false warning removed, docstring corrected,
and the unused requirement dropped (nothing imports `nhlpy`; a test now fails
if anything starts to, so the pin goes back before the import does).
Found 2026-08-31.

## [ ] An off-platform pinger, so both containers dying is not silent

`tracking/heartbeat_watchdog.py` (2026-08-31) runs on every service role
precisely so one container can report the other's death, but it is still hosted
inside the system it watches: losing both at once is silent. Closing that needs
something outside Railway — a cron on Matt's machine, or an uptime service
hitting the monitor's `/healthz` — that alerts on the ABSENCE of a heartbeat
rather than on an error. Documented in `docs/monitoring.md` under "What it still
does not cover".

## [x] Stop pulling the NHL 3-way market out of season

`h2h_3way` is fetched per NHL event on every pass and returns **422 on every
one** — 32 wasted round trips per pass, ~1,300 a day. Credits are not charged
on a 422 (verified), so this is latency and noise rather than money, but it is
also 32 lines of error in every pass log, which is how a real error gets
missed.

Flagged 2026-08-30, three times. Fixed 2026-09-03 — but NOT by the season
gate suggested here, and not by a circuit breaker either. A season calendar
has to be right about the NHL's start date every year forever and is wrong
silently. A give-up-after-N-misses breaker was written first and a test
killed it: it cannot tell "out of season" from "in season, but the first
few events listed are far-future games", so it would abandon a market that
IS offered — the exact failure that hid `h2h_3way` for months.

What shipped is a proximity window (`THREE_WAY_LOOKAHEAD_DAYS = 3`): DK
prices the regulation market for games about to happen, so an event further
out is not worth a call either way. Out of season the nearest game is weeks
off and the loop makes ZERO calls; in season it walks today's slate and
nothing else. Fails OPEN on a missing or unparseable `commence_time`, so a
real game is never dropped over a timestamp shape.

## [ ] `run_ledger finish` swallows its own errors

`python -m tracking.run_ledger finish ... 2>/dev/null || true` in
`scripts/refresh_pass.sh`. So a pass that COMPLETED but failed to write its
finish row is later marked `aborted` by the next run, and "aborted" therefore
means either "the pass died" or "the bookkeeping call failed" — two very
different things that cannot be told apart.

This actively cost diagnosis time on 2026-08-30: four passes were investigated
as hangs when at least two were deploy restarts. Keep the `|| true` (a ledger
must never break the pass it observes) but log the failure somewhere visible
instead of `/dev/null`.

## [ ] Settle is step 24 of 28, so it is the first thing lost

Grading and the daily recap sit near the end of the chain. On 2026-08-30 four
passes died mid-chain and the corrected recap went unposted for five hours,
while odds — step 2 — kept updating fine.

Settle genuinely must follow the results ingests, so this is not a reorder.
The fix is to make the record not depend on a pass surviving to the end: a
small settle-and-recap entry point that can run on its own, or a late-day
guarantee pass that does only that.

## [ ] One leaked database connection

`pg_stat_activity` showed a connection idle for 1 day 20 hours. Harmless at
this scale — `data.db.get_connection()` does not pool, so one leak is one
connection — but it is a leak and it will not be the last. Find the caller
that does not close.

## [ ] Batter props never get a best price stamped

Zero August `mlb_prop_batter_*` BETs carry `best_odds`, while
`mlb_prop_pitcher_k` carries 6 of 18. So it is a live code-path bug, not
missing plumbing: the books are configured, all three append sites in
`run_batter_prop_scorer` tag `_best_ctx`, and **1,726 of 1,783 DK batter-prop
quotes (97%) have a same-line match at another book**.

Leading hypothesis, unverified: the prop lock freezes a pick at first signal,
so one written before best-price stamping shipped is never re-stamped. Needs a
reproduction against real rows — the dev sandbox has no `DATABASE_URL`, so run
it locally or on the worker.

Worth real money: on props, **1 in 3 has 1–30 cents available elsewhere and 1
in 16 has 30+**.

## [ ] Surface the best book in Discord and the betslip

Depends on the item above. mike, 2026-08-30: *"the bet should pick the best
line for the bettor, across the main books, not just DK."*

Display and betslip only. The models keep DECIDING on DraftKings — every
threshold was swept on DK-implied edge, and best-of-N prices ~2pp cheaper in
implied probability, so adopting it as the qualifying price would loosen every
cut by that much with nobody deciding to (CLAUDE.md §6).

## [ ] [needs-decision] Re-sweep `mlb_live_total_runs` — the gate is CLEARED

**Measured 2026-09-04 (session 216): 95 settled BETs, every one carrying a DK
price, +12.99u — about +13.7% on flat stakes — most recent pick that same day.**
The item was written at 17 settled with the re-sweep due at ~50, so it is now
overdue rather than pending. (Query: `picks` where `model_id =
'mlb_live_total_runs' and signal_type = 'BET'`, result in ('WIN','LOSS','PUSH');
units gated on `dk_odds IS NOT NULL` per §6, though here nothing is unpriced.)

This is the nearest thing the live lane has to a real result, and CLAUDE.md §1b
cites it as promising-but-unproven — that citation is now stale by 8 bets and
should be refreshed from this number when someone touches it.

A threshold move needs a named human under §1b, so an agent may prepare the
sweep and report it but must not ship the cut.

## [ ] [needs-decision] Live odds feed

Measured 2026-08-30 against a direct DK capture: the Odds API lags DK's in-play
number by a median **54s**, worst **210s**, and missed two lines entirely
inside one 80-minute window. Polling faster cannot fix it — the staleness is on
their side.

Options are a vendor with a real publish clock (OddsPapi free tier, TheRundown
~$49/mo) or accepting the lag. Blocked on mike; needs a spend decision.

## [ ] Backtest a best-line decision basis

The honest version of "does a model rebuild improve things": re-score history
with best-of-N as the qualifying price and compare against the DK-only record,
per model, with the thresholds re-swept in the same pass.

Preliminary evidence says it will NOT help game lines — on 319 settled BETs, DK
was best or tied on **316**, and units at DK equal units at the best price
exactly. Props are the open question.

Substantial: a session's work, not a corner of one.

## [x] Backfill `player_game_log` for the games it never covered — CAUSE FOUND AND FIXED 2026-09-03

The pitcher-stats rebuild (`data/pitcher_stats_rebuild.py`) can only build a
row where `player_game_log` holds the start. It does not hold every game:

| season | completed games | both starters found | pct |
|---|---|---|---|
| 2019-2023 | ~2,500 each | ~2,200 | **86-89%** |
| 2024 | 2,520 | 2,058 | **81.7%** |
| 2025 | 2,518 | 1,889 | **75.0%** |
| 2026 | 2,007 | 1,873 | **93.3%** |

The largest single hole is systematic: **there is not one pgl pitcher row for
any game involving the White Sox or the Nationals before 2026** — not even the
opponent's starter. Those clubs' entire schedules are missing, which is ~638
games in 2024 alone.

The uncovered games now get no pitcher row and drop out of training, which is
the honest outcome but a real cost — the missingness is by CLUB, not at random,
and 2024's White Sox were 41-121, so the drop removes a set of very lopsided
games.

**The cause was not a missing feed. It was the backfill's own skip predicate.**
`backfill_player_game_log` skipped a whole DATE if `player_game_log` held any
row for it — and every MLB date carries ~15 games, so one ingested game marked
the entire date done and every other game on it was never fetched. Measured
before the fix: of 200 White Sox games in 2024, **200 sat on a date that already
had rows from other games, and 0 had rows of their own.**

That is `.claude/rules/data-integrity.md`'s jamming backfill in another shape —
a backfill must filter by the SAME predicate the worker applies, and the unit of
work here is a GAME.

Fixed 2026-09-03: the skip is now per `game_id`, pinned by
`tests/test_game_log_backfill_skip.py` (4 tests, 4 mutations, all caught).
`game_log_backfill` is registered in `tracking/job_queue.py` so the re-fetch
runs on the worker, which has the StatsAPI egress. Deterministic and free — no
paid API involved.

**Still to do: RUN it** (`enqueue(conn, "game_log_backfill",
{"start_season": 2019, "end_season": 2025})`), and only AFTER the fix is on
master and the worker has redeployed — a run against the old code would skip
everything and mark itself done. Then re-run
`python -m data.pitcher_stats_rebuild --force` to lift pitcher coverage from
75-89%, and re-measure.

## [ ] The daily pitcher last-3 lookup keys on `player_name`, not `player_id`

`_build_pitcher_rows` (`data/ingestors/mlb_stats_ingestor.py:562`) computes
`era_last3` with `WHERE player_name = ?`. Names collide: a query for `%Nola%`
in this repo returns two different pitchers, and the rebuild found the same
shape elsewhere. When two pitchers share a name the window silently mixes
them.

`player_id` is present on every row of both tables and is what
`data/pitcher_stats_rebuild.py` groups by. One-line change, but it alters a
served feature value, so it wants a measurement rather than a blind fix.

## [ ] [needs-decision] Make `era_last3` a true rolling last-three ERA

**This is a model update, not a repair, and it is mike's or matt's call.**

`era_last3` is not an ERA over the pitcher's last three starts. Both the daily
ingest and (deliberately) the rebuild compute it as `AVG(era)` over the last
three stored rows — the MEAN OF THREE SEASON-TO-DATE RATES, which is a smoothed
near-duplicate of `era` itself.

The rebuild replicates that on purpose. Serving will keep computing it that way
tomorrow morning, and `d_starter_era_last3` is ~21% of `mlb_f5_moneyline`'s
importance, so training on a truer statistic would measure a system nobody
deployed and silently redefine a fifth of the model.

The true rolling version is computable exactly from `player_game_log` and is
very likely a better feature — it carries information `era` does not, where
today it mostly restates it. Doing it properly means: fix the ingestor, rebuild
all seasons, recompute 2026, re-sweep the thresholds, and stamp it
`Updated-By:`. One decision, one owner, one session.

## [ ] Doubleheaders collide under one game_id, and their props land on top of each other

Found 2026-09-05 while designing the alternate-lines view. 1,546 (game,
market, player, book) keys since 2026-08-29 carry TWO rows at the same
`snapshot_at`, DraftKings included (163): `_build_game_id` is
`MLB_<date>_<away>_<home>`, so both games of DET@CLE on 2026-09-04 write
their props under `MLB_2026-09-04_DET_CLE`, and "the newest row" for Jose
Ramirez is whichever game's batch inserted last. The Odds API gives each game
its own event id; the game_id throws that away. Touches the odds ingestor,
the prop ingestor, `games`, the scorer's `_latest_dk_prop_row` and
settlement, so it is its own session: decide how a second game is keyed
(the app's `startedTeams` map already treats a team with a game still to
come as unstarted), then make both ingestors and the pick lock agree.

**Second symptom, found 2026-09-05 and CONTAINED, not fixed:** the collision
also duplicated PICKS. Game 1's final score settled a prop pick while game 2's
`commence_time` kept the pre-game cutoff open, and both locks released a pick
the moment it was graded — so every 10-minute pass wrote another copy. Eleven
rows for one Logan Allen Over 4.5 Hits, and 20 of the 132 settled BETs in the
published 09-01 window were copies (+7.38u published against +5.68u real). The
locks now key on a pick's EXISTENCE, the prop scorers skip a game that already
has a final score, and `uq_picks_one_row_per_pick` enforces one row per pick —
so the collision can no longer inflate the record. It can still put game 1's
score against game 2's pick, which is what this item is for.

## [ ] `picks.player_id` and `picks.is_live` exist in production and in neither schema file

Found 2026-09-05 writing tests against the real table. Both columns are read
and written all over the scorer, the views and the app, and neither
`data/db_setup.py`'s `SCHEMA_SQL` nor `data/supabase_schema.sql` declares
them — they were added by hand and never written back. So a first-time setup
builds a `picks` table the scorer cannot insert into, and every sqlite-backed
test has to ALTER them in (`tests/test_pick_lock_survives_settlement.py` does).
Small and mechanical: add both to each schema file, and check the same way for
every other column production has grown.

## [x] NCAAF player props have no ingest — DONE 2026-09-05

Raised when NCAAF alternates were approved with nothing to ride. Matt asked
what it meant and then "Yes do it", so
`data/ingestors/ncaaf_prop_odds_ingestor.py` exists: CFBD ids via
`resolve_odds_api_school`, `americanfootball_ncaaf`, the shared parser, and
`config.PROP_MARKETS_NCAAF` + the NCAAF alternates. Scoped to games
DraftKings already prices (measured: 120 games on a Saturday, 70 lined) under
a per-pass ceiling, and OFF (`RUN_NCAAF_PROP_ODDS=0`) until the probe's
measured cost is in front of Matt.

Still open underneath it: **no NCAAF prop MODEL.** These rows are research —
the Stats board's line column and betslip line legs. A college prop model is
its own piece of work, and would need the CFBD player log as its substrate.

## [ ] No slate-wide book-coverage answer the app can afford

Found 2026-09-05 building the Stats picker's coverage note. The board can say
"FanDuel posts no At-Most Hits lines today" for free, because it already holds
that stat's rows. It cannot say "FanDuel has nothing at all today" without
reading every market — and that read is not affordable: `explain analyze` on
`v_latest_prop_odds_all_books` grouped by book for one date measured **17.5s**,
and straight off `player_prop_odds` **8.5s** over 172,462 rows for 2026-09-05.
Both are far past what a screen (or the statement timeout) will take.

The fix is a small coverage table the prop ingestors maintain as they write —
`(game_date, sport, bookmaker, market, has_over, has_under, games)`, one row
per combination, refreshed each pass — which the app reads in milliseconds.

**2026-09-05 update:** most of that table now exists. `latest_prop_odds`
(migration `latest_line_state_tables`) holds one row per current line, so
"which books post which markets today" is `SELECT bookmaker, market, count(*)
FROM latest_prop_odds JOIN games USING (game_id) WHERE game_date = $1 GROUP BY
1, 2` — a few thousand rows, milliseconds. What is left is an RPC (or a tiny
view) for the app to call and the picker copy that reads it.
It would also give the Discord and monitoring surfaces a cheap answer to "which
books did we actually get tonight", which today is a table scan nobody runs.

Not needed for anything shipped yet: Matt's rule is that a book we pull lines
for stays in the picker whatever its depth (2026-09-05), so nothing currently
depends on the slate-wide answer.

---

## [ ] Two publishers can now post the same pick twice

Opened 2026-09-05 by #505, which made every pick-WRITER publish rather than
leaving it to the refresh pass. There are now two processes that can call
`notify_discord_signals` / `notify_signal_changes` for the same date: the
refresh pass (`worker`, at :17 and every 10 minutes in the evening) and the
pre-game line poller (`pollers`, every 30 seconds, whenever a tick writes a
BET). The NFL card jobs are a third.

`push_sent` is `UNIQUE(lock_key, kind)` and is written AFTER a successful post,
so it cannot stop a second POST that was already in flight — only the second
ledger row. Both producers read "unposted BETs", so if their reads straddle the
same ~1-2 second window the same pick goes to the channel twice.

Small: it needs both producers inside the same couple of seconds AND the same
pick. Not zero: the poller ticks 2,880 times a day.

The fix is a Postgres advisory lock around the publish sequence --
`pg_try_advisory_lock` on a fixed key at the top of
`tracking.signal_publisher.publish_new_signals`, skipping the run when it is
not acquired (the other producer is already doing it). For that to bind, the
refresh pass has to go through the same helper rather than calling the two
notifiers directly in `run_pipeline.step_push_notifications` -- which is the
§1b shape anyway (one helper, every caller), but it changes that step's
failure reporting, so it wants its own PR rather than being tacked on.

---

## [ ] The locked-pick monitor has never written a row: the eval CSV and `picks` use different game_id shapes

Found 2026-09-06 (mike, asking why the wind model was firing on nearly half the
Week 1 slate). `nfl_pick_status_history` holds **0 rows for every model**, and
`condition_status` is NULL on all five live `nfl_wind_totals` picks.

It is not a missing dump and it is not a schema problem. The monitor runs
cleanly on every hourly tick and says so:

```
04:00  START nfl-pick-monitor
       NFL pick monitor 2026-09-06: 0 locked pick(s) observed
       DONE  nfl-pick-monitor (exit 0)
```

— repeated at 05:01, 06:02, 07:03, 08:04, 09:04, 10:05, 11:06. It printed the
post-loop message rather than `no evaluation dump — nothing to do`, so the CSV
was read and had rows. The loop found none of them.

**The join key does not match.** `nfl/data_ingest/pick_eval.py` writes
`game_id` as the bare nflverse id and its own field comment calls it "the join
key to picks" — but `scripts/nfl_wind_publisher.py` writes
`game_id = f"NFL_{nflverse_id}"` (its module docstring says so at line 12). So
`current.get((game_id, model_id))` in `scripts/nfl_pick_monitor.py:latest_per_pick`
looks up `NFL_2026_01_CLE_JAX` in a dict keyed `2026_01_CLE_JAX` and misses
every time. `written` stays 0 and the run exits 0, which looks exactly like
"nothing changed".

**Why it is load-bearing.** Wind became insert-once on 2026-08-22 and the
scheduler comment justifies the lock with "every later tick records whether the
conditions still hold (`nfl_pick_status_history`) without touching the bet".
That sentence is currently false. A pick locked at a 12 mph forecast whose wind
collapses to 8 mph before kickoff is flagged nowhere — not in the table, not on
the pick, not in the app.

**It has already cost something concrete.** `CLE @ JAX Under 40.5` locked on
2026-09-05 at a **14.0 mph** forecast. The card's dry run the next day, still
seven days from kickoff, reads **4.3 mph** at the same stadium — the lowest on
the board. The pick stands (§1c, and correctly), but the premise for it is
gone, and there is nowhere that says so: not `nfl_pick_status_history`, not
`picks.condition_status`, not the app. That is the exact scenario
`nfl_pick_monitor`'s docstring describes as "the case this whole mechanism
exists for".

Fix is one line at the write side or the read side; prefer normalising in
`pick_eval.eval_row` so the CSV's own comment becomes true. **The test has to
watch it fail** (§1b): assert a published pick's `game_id` resolves against a
dump produced by `evaluate_board` — the current suite passes with the bug in.

## [ ] 43 of the 2026 NFL schedule rows have a BLANK roof and are scored as open-air

Found alongside the item above. `nfl/data/games.csv` for season 2026:

```
outdoors 177   dome 52   (blank) 43
```

The 43 blanks are exactly five stadiums — `ATL97`, `DAL00`, `HOU00`, `IND00`,
`PHO00` — every one of them a **retractable** roof. Prior seasons carry `open`
or `closed` per game (128 and 621 rows), which is the roof state on the day;
2026 has not been played, so the state is empty.

`INDOOR_ROOFS = {"dome", "closed"}` and `select_bets` filters with
`~games.roof.isin(INDOOR_ROOFS)`, so a blank is **outdoor**. Two of the five
live Week 1 wind picks are on that basis:

| pick | stadium | roof in csv | forecast wind |
|---|---|---|---|
| BUF @ HOU Under 44.5 | HOU00 (NRG) | *(blank)* | 12 mph |
| BAL @ IND Under 48.5 | IND00 (Lucas Oil) | *(blank)* | 11 mph |

Both venues close the roof for most games. A wind under bet on a game played
under a closed roof has no premise at all — the forecast is for air the players
never stand in.

This inflates the fire rate on its own: it adds 2 games to an 11-game outdoor
denominator that should be 9, and both of them qualified.

Options, in order of honesty: treat a blank roof at a known retractable venue
as **not eligible** until the state is known (the model loses nothing — a
genuinely open roof re-qualifies once the state lands); or source the roof
state pre-game rather than from the schedule file. Do NOT default blank to
`outdoors`, which is what happens today by omission.

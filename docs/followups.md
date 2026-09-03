# Follow-ups

> **Janitor's worklist.** The durable backlog: Janitor (see `docs/agents_contract.md`)
> takes one item from here every morning, and a human can add to it any time.
>
> **Why a file:** a task list that lives only in a chat is gone the moment the
> session ends. Four small fixes below were flagged in three separate sessions
> and never done, because each time they lost to a larger ask and nothing
> carried them forward. Same reasoning as CLAUDE.md §1b.
>
> **Format:** one `## Item` per task. `[needs-decision]` means blocked on a
> human and the agent must skip it. Tick with `- [x]` and leave it in place for
> one week so a reader can see what recently changed, then delete.

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

## [ ] RLS is off on `worker_jobs` and `odds_history_pulls`

Found 2026-09-01 by `get_advisors(security)`, which reports both at **ERROR**
level: "is public, but RLS has not been enabled."

**It is not currently an open door, and the first report of it said it was.**
Checked before writing this item:

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

## [ ] [needs-decision] Re-sweep `mlb_live_total_runs` at ~50 settled picks

17 settled as of 2026-08-30. A threshold move needs a named human under §1b,
so an agent may prepare the sweep and report it but must not ship the cut.

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

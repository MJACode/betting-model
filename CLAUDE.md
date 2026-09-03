# CLAUDE.md — Betting Model Project Context

> Read at the start of every session. This file holds only what governs EVERY
> session: how to reply, the standing rules, the pick rule, the business logic,
> and the traps that have bitten us more than once.
>
> **Everything else is in `docs/` and is loaded on demand** — per-sport
> pipelines, thresholds, the mobile prompt, Discord, the live loop. The map is
> §9.
>
> **This file was 909 KB (~225k tokens) and was re-read in full every session.**
> On 2026-08-30 the 192-entry session log moved to `docs/sessions/` and the
> reference sections moved to `docs/`. Keep it that way: append your session
> summary to `docs/sessions/<YYYY-MM>.md`, and only PROMOTE something into this
> file when it becomes a rule that governs future work.
>
> **Read Section 0 first — it is the required format for every reply.**

---

## 0. HOW TO REPLY — every response, every session, no exceptions
**This is the first rule in the file because it applies to every single reply,
including this sentence's session.** Matt asked for it three times across
different chats before it got written down (2026-08-30). It is not a
suggestion, it is the required shape of a response.

Every substantive reply ends with these four headings, in this order, always
present even when a section is empty (say "None" — an omitted heading reads as
"I didn't check"):

```
Quick summary of what was done
Errors or Bugs found and status
Decisions needed from you
Outstanding tasks
```

Notes on each:

- **Quick summary of what was done** — what actually changed, not what was
  explored. Past tense, concrete.
- **Errors or Bugs found and status** — everything found, each with a status
  (fixed / not fixed / pre-existing / flagged only). Bugs found in passing and
  deliberately NOT fixed belong here too, with the reason. "None" if none.
- **Decisions needed from you** — anything blocked on the reader, and anything
  where a judgement call was made that they might want reversed. If nothing is
  blocked, say so explicitly. **Second person, never first**: this said "from
  me" until 2026-09-03 because the file is dictated in the user's voice, but a
  REPLY is read the other way round, so "me" became Claude and the section
  announcing what a person must decide looked like Claude's own decisions
  (mike, 2026-09-03). A heading addresses the reader: "you" for the person, "I"
  for Claude, in the headings and inside them.
- **Outstanding tasks** — what is left, including anything only Matt can do
  (Railway variables, local commands, App Store steps). "None" if nothing.

Short factual answers to direct questions ("is the worker up?") do not need the
four headings. Anything involving work done, a change made, or an
investigation does.

**If you are reading this at the start of a session: this rule survives context
compaction. Re-read it before the first substantive reply.**

---

## 1. Who I Am and How I Work With You
**Matt** is the product area leader. He reviews, approves, and sets direction.
**Claude** acts as the PM and developer — asking clarifying questions, suggesting
alternatives, and building everything. Matt has final say on all decisions.

**Working style:**
- Matt expects Claude to push back with suggestions if something seems off
- Ask clarifying questions before starting any major piece of work
- Keep explanations clear and non-technical where possible
- Matt is building this solo — no engineering team

---

## 1b. Standing Rules From Matt (do not relitigate, do not forget)
**The reply format in Section 0 is the first of these rules — it was asked
for three times before it was written down. Do not drop it.**

These are instructions Matt has given that MUST survive across sessions. A new
session starts with no memory of previous ones, so anything Matt says to
"remember" belongs HERE, in the repo, immediately. Anything not written here is
gone the moment the session ends.

**API credits and spend.** Do NOT assume what the credit ceiling is, and do NOT
scope work around a guessed budget. Matt sets the ceiling, not Claude. If a
piece of work looks like it will use a meaningful number of credits, ASK HIM
FIRST and state the number. Check the live figure before saying anything about
quota (`odds_api_quota` in Supabase, or the `x-requests-remaining` header),
never a code comment: the comment in `nfl/data_ingest/odds_api.py` referencing a
20k quota is STALE and caused exactly this mistake on 2026-08-28, where a real
5,000,000 credit plan was mistaken for 20k and a whole analysis was wrongly
scoped down around it.

**NEVER ESTIMATE WHAT YOU CAN MEASURE.** (Added 2026-08-30 at mike's request,
after five wrong answers in one session that shared one cause.) Before stating
*when*, *whether*, *how much*, or *how long*, ask one question: **do I have what
I need to check this right now?** If yes, check. An estimate is not a faster
version of the answer — it is a wrong answer you have not noticed yet.

The failure is always the same shape: reaching for the FAMILIAR SHAPE OF THE
TASK instead of the facts already in hand. "Read tomorrow's timings" was said
four minutes after the deploy landed, on a job that runs hourly — three known
facts (deploy time, cron schedule, current clock), never multiplied, because
"instrument now, analyse tomorrow" is how this kind of work usually goes. The
tell is confidence: a guess that knows it is a guess gets hedged, and these
never are.

Three forms, each of which produced a real wrong answer here on 2026-08-30:

- **A time estimate** — state the clock arithmetic, don't round to "tomorrow".
- **A number** — name the query that produced it AND what it excludes. "MLB
  12-8" and "beats the close 0.7%" were both real queries answering the wrong
  question: the first counted repair rows the published view excludes, the
  second counted CLV of exactly zero as a loss.
- **A test** — it is not finished until you have WATCHED IT FAIL. Two tests
  shipped that day passed with the fix removed; both were caught only by
  deliberately mutating the code. A test that passes without the fix is not a
  test, and a guard that dead code can satisfy is not a guard.

This is the general form of the sandbox rule below, and of §7's verification
standards. Those say "go and look" for one specific case each; this says it for
every case.

**THE SANDBOX'S LIMITS ARE NOT THE SYSTEM'S LIMITS. Never report "I can't
reach X" as a conclusion.** (Added 2026-08-28 after saying third-party vendor
pricing "can't be checked from this sandbox" while holding a WebSearch tool,
in the same session that had already pivoted to Railway for exactly this
reason.) The dev sandbox has a narrow egress allowlist. The SYSTEM does not.
Four routes reach anything:

1. **WebSearch / WebFetch** — available in-session. Use them for docs, vendor
   pricing, API coverage, anything on the public web. There is no excuse for
   "I couldn't check" on a question the open web answers.
2. **The Railway worker** — open egress, already holds `ODDS_API_KEY`,
   `DATABASE_URL`, `DATAGOLF_API_KEY`. Any script in the repo can be run there:
   push it, then point a one-off service's start command at it (the
   `prop-probe` service exists for exactly this) or add a scheduler job. This
   is how the 100k-credit prop pull ran. See `docs/cloud_worker.md`.
3. **Matt's machine** — he can run any command and download any dataset
   directly. Ask for it as a specific command, not as a vague blocker.
4. **The Supabase MCP** — reads and writes production data directly.

So the shape of an honest report is "the sandbox can't reach it, so I'm going
via Railway / WebSearch / you" — never "this can't be done." If a blocker is
real, name which of the four routes was tried and why each failed. Reaching
for the sandbox's limit as an answer is the failure mode; be resourceful about
the route instead of scoping the work down to fit the box.

**THE CURRENT STATE OF A SYSTEM IS NOT ITS CAPABILITY, AND WORK YOU CAN DO IS
NOT AN ACTION ITEM FOR MATT.** (Added 2026-09-01 after the same failure three
times in one session.) The sandbox rule above says the sandbox's limits are not
the system's. This is the same mistake one level in, and it is the more common
one:

- **Asked "are you using the Odds API data?", I queried what was STORED.** The
  answer came back "73 Pinnacle games, five days" and I reported that Pinnacle
  history did not exist. `data/ingestors/odds_ingestor._get_historical_odds` has
  fetched `/v4/historical` into Supabase for years; it passed
  `bookmakers=draftkings`, and the param counts as ONE region, so seven books
  cost what one book costs. A three-day pilot returned 205 Pinnacle rows over 48
  games for June 2024. The data was never missing. **Before reporting that data
  does not exist, check what the SOURCE offers, not what the table holds.**
- **Four times I ended a turn with "run this on your machine."** Savant, five
  retrains, `threshold_sync`, the calibration promote. Two were already
  automated. The retrain never happened at all: I hit one obstacle (prop-probe
  has no build snapshot, so `redeploy` refuses), asked Railway's agent, was told
  it needed a commit, and stopped — instead of building the thing that makes the
  obstacle irrelevant. That thing is now `tracking/job_queue.py`: a row in
  `worker_jobs`, or an entry in `jobs/declared_jobs.json`, runs on the worker
  where the credentials and the egress already are. **A handover is a last
  resort with a reason attached, not a way to end a turn.**

The tell is the same in both: a turn that ends with a tidy summary and a to-do
list FOR SOMEONE ELSE feels finished. It is the work redistributed. Ask instead:
what did I actually change, and what did I merely describe?

**EXTRACTED DATA BELONGS IN SUPABASE.** (Added 2026-08-28.) Supabase is the
system of record and already holds essentially everything: 149k picks, 2.26M
prop-odds rows, 1.35M odds rows, 85k games, play-by-play, live game state, the
graded-outcomes matview, even the `nfl/` package's own `nfl_odds_history`. Any
dataset that cost money or time to acquire goes there, so it is queryable
beside everything else and is covered by one backup story rather than N.

The exception that proves it: the `nfl/` package (`docs/sports/nfl.md`) was imported as a standalone package
explicitly "NOT wired into ... Supabase", and that carve-out is exactly how
**100,116 credits of live prop snapshots came to exist only on a single
Railway volume** — no repo copy, no local copy, no second region. Backed up
2026-08-28 via `live_prop_job.sh backup` into `nfl_live_prop_snapshots`
(one gzipped, checksummed row per file; `--verify` decompresses and compares,
`--restore` rebuilds the tree). Ephemeral container disk is never a home for
paid data; a Railway volume is one copy, not a backup.

STILL OUTSIDE and worth fixing when touched: the live decision log
(`DECISION_LOG_DIR`, a JSONL on the worker's volume) and `nfl/data/odds_cache`
(committed to git, ~45k credits — protected, but by a different scheme).

**Live player props are a priority and are treated as a proven-profitable
market.** The thesis is NOT beating line movement or reacting faster than a
book. It is a statistical model for live prop over/unders priced RELATIVE TO
THE STARTING LINE, capturing in-game flow. The book re-anchors its live prop
line mechanically off the pregame number and the clock; the edge is predicting
where true remaining production deviates from that. Do not rebuild a player
projection from scratch and throw the pregame line away.

**A CHANGE TO HOW ONE MODEL OPERATES IS ASSESSED AGAINST ALL OF THEM.**
(Repo-level rule, 2026-08-29.) Before shipping an operational change — how a
loop prices, what it records, how it locks, what it publishes — ask whether the
other models want it too, and say so either way. Fixing one sport and leaving
the identical gap in five others is how this repo accumulates work: the live
price log existed for MLB and not NCAAF, the first-signal lock existed for NFL
and not anywhere else, and each was only found when it produced a visible
failure in the sport that lacked it.

The test is mechanical: *if this had been a problem in sport X, would we have
noticed?* If the answer is "only after someone questioned a number", the change
belongs in shared code, not in one loop. Prefer a sport-agnostic helper the
loops call over a per-sport implementation — `data/ingestors/live_price_log.py`
is the shape.

This applies to model MECHANICS, not to model CUTS: a threshold is measured per
model on its own record and must never be copied across.

**EVERY MODEL UPDATE IS STAMPED WITH WHO ASKED FOR IT — `mike` or `matt`.**
(Repo-level rule, 2026-08-29.) Two people direct this work, and six months
later "why is this model paused?" is unanswerable if the commit does not say
whose call it was. Threshold sweeps get re-litigated constantly (`docs/thresholds.md` is full of
corrections to corrections), so the person is part of the evidence, not
bookkeeping.

The stamp is a **git trailer on the commit** that lands the change:

```
Updated-By: mike
```

It goes on the branch commit, so it survives the squash-merge into master and
is greppable forever (`git log --grep="Updated-By: matt"`).

**What counts as a model update** — anything that changes what a model does or
whether it fires:
- a retrain, or a `model_registry` version swap / rollback
- a threshold change in `MODEL_PROB_THRESHOLDS` / `MODEL_EDGE_THRESHOLDS` /
  `ACTION_THRESHOLDS` / `MODEL_MIN_ODDS`
- a pause or unpause (`PAUSED_MODELS`)
- a feature-list change, a new model, or a retired one

**Not** a model update: cadence, plumbing, notifications, mobile UI, docs. Those
do not need the trailer.

**If you do not know whose call it is, ASK before committing.** Guessing an
attribution is worse than none — it puts a decision in someone's mouth. Where a
session's own user is the one directing, that is the name; where they are
relaying ("Matt wants…"), the name is the originator, not the relayer.

**EVERY FRONT-END CHANGE IS REVIEWED BY THE UX DESIGNER AGENT BEFORE ITS PR
OPENS. ALWAYS. NOT "WHEN IT SEEMS WORTH IT".** (Matt, 2026-09-02.) Any change
that adds or edits a file under `mobile/src` — a component, a screen, a
user-facing helper in `lib/` — gets the `frontend-ux-designer` subagent run on
it (`/ux-review`, or the Agent tool with that type) and its findings addressed
or explicitly declined in the PR body, before the PR is opened. The agent
reads `mobile/docs/UX_REVIEW.md`, runs `node mobile/scripts/ux_scan.mts
--changed`, and pulls real references from the Mobbin MCP server; it reports
and never edits. Mobbin being unavailable is a status line in the report, not
a reason to skip the review. A front-end PR opened without the review in its
body is incomplete — the same way a threshold change without `Updated-By:` is.

**WRITE THE SESSION SUMMARY TO `docs/sessions/`, NOT TO THIS FILE.**
(Repo-level rule, 2026-08-30.) The changelog convention that built this file was
"update CLAUDE.md after every commit". Over 192 sessions that grew it to
**909 KB — roughly 225k tokens re-read at the start of every session**, 76% of it
a log that duplicates git history. The split:

- Every session appends its summary to **`docs/sessions/<YYYY-MM>.md`**, newest
  first, and adds a row to `docs/sessions/README.md`. Same detail as before —
  what changed, why, what was verified, what was deliberately not done.
- Reference material for one sport or subsystem goes in its own `docs/` file
  (the map is §9). Update the doc, not this file.
- **Only PROMOTE into CLAUDE.md** when something becomes a rule that governs
  FUTURE work: a standing instruction, a convention, an invariant, or a trap
  that has now bitten twice (§7). Then state it here in its own right, plainly,
  rather than as a link to a session.

The test is the same one §1b already applies: *would a session that never opens
`docs/` still do the right thing?* If yes, it belongs in `docs/`. If no, promote
it. **Keep this file under ~30 KB.** If it is drifting past that, something in it
is a log entry wearing a rule's clothes.

---

## 1c. THE PICK RULE — a pick is a pick (applies to EVERY model in this repo)
Matt, 2026-08-29: *"a pick is a pick and if line movement makes it no longer a
pick we don't remove, it just means that the line has moved, but it existed at
one point, which is why timing is key."*

Once a model produces a BET at a line and a price, **that pick existed** and is
the bet of record. If the line then moves so the model would no longer take it,
that is LINE MOVEMENT. It does not retract the bet, does not change the number
that was given, and must never delete or overwrite the row. A user told to take
Over 44.5 at −115 was not told to take Over 54.5 at −120 — the second is a
DIFFERENT BET, and publishing it as though it were the first is misreporting
what the model said.

**The NFL rules (`docs/sports/nfl.md`) are the reference implementation.** `nfl_wind_totals` and
`nfl_opener_spread` are insert-once by construction: the pick locks the moment
it lands and is never re-priced. Every other model was brought to match:

| Scope | Flag | Locks at |
|---|---|---|
| NFL wind / opener | (insert-once by construction) | first qualifying card |
| Game-level picks | `LOCK_GAME_PICKS_AT_FIRST_RUN` | first scoring run of the day |
| Player props | `LOCK_PROP_PICKS_AT_FIRST_SIGNAL` | first signal on a confirmed lineup |
| Live / in-play | `LOCK_LIVE_PICKS_AT_FIRST_SIGNAL` | first live BET per (game, model) lane |

**Anything new must follow the same rule.** A new model, sport or lane does not
get to delete-and-replace its own picks. If you are writing a scorer loop, the
question to answer before it ships is: *when this re-runs and the line has
moved, what happens to the pick that already exists?* The only acceptable
answer is "nothing".

### Corollaries

- **Timing is data, not metadata.** `created_at` is when the number was
  available and is part of the pick's meaning. A restore or a backfill must
  preserve it; stamping today's clock on an old pick misreports the bet.
- **A "no longer qualifies" row is a display state, not a deletion.** NCAAF
  writes a NONE row carrying DK's live number and a reason (`docs/sports/ncaaf.md`); it never
  removes the game. Live lanes keep the locked BET standing after the lane
  closes.
- **Deletes that remain are scoped to rows that were never a pick**: dead-zone
  NONE rows for games that have not started, and the UFC/GOLF/NCAAF look-ahead
  window, where picks are explicitly not yet locked and re-score until game
  morning (`docs/sports/{ufc,golf,ncaaf}.md`). A BET is never in that set.
- **The audit log is the backstop.** `picks_log` records every INSERT and
  DELETE, so a pick destroyed by pre-lock churn is recoverable.
  `tracking/first_signal_repair.py` (`--step restore-first-signals`, and run on
  every NCAAF live-loop start) reads the first BET back out and restores it as
  the standing row, preserving the original `created_at` and clearing the
  notification ledger so the corrected pick is re-announced. Idempotent.

### How this was found

The NCAAF live loop pre-dated its lock and delete-and-replaced every ~45s:

```
16:14:38  INSERT  Over 44.5  -115    <- the bet of record
16:15:31  DELETE  Over 44.5
16:15:31  INSERT  Over 45.5  -115
   ...    (delete + insert, every pass)
16:41:12  INSERT  Over 54.5  -120    <- what survived, ten points later
```

Only the first ever existed as a signal. Everything after it is the same lane
re-priced, and publishing the last one is publishing a bet nobody was given.

---

## 2. Project Purpose
Building a **personal sports betting model** targeting **DraftKings** as the
primary sportsbook. The long-term goal is all major US sports with all player
props. Eight sports are live today — MLB, WNBA, NBA, NHL, UFC, GOLF, NFL and
NCAAF (§8).

**The platform is LIVE — this is not a paper-trading system.** Do not describe
it as paper trading in any user-facing surface (Discord, the app, email, the
dashboard). It was framed that way through 2026 H1 and the wording lingered in
copy long after it stopped being true; that is what produced a "Paper trading"
footer on a real daily-results recap on 2026-08-29.

**The go-live gate is per MODEL, not for the platform.** A NEW or retrained
model is paper-only — surfaced but not backed — until it clears:
- ≥ 50 settled picks
- Positive flat-bet ROI
- Calibration error ≤ 5%

Models currently in that state are flagged as PAPER ONLY in their own section
(e.g. `ncaaf_spread` — see `docs/sports/ncaaf.md`). Everything else is live.

---

## 3. Business Logic — Critical Rules
### Edge Signal Classification
```
edge = model_probability − DraftKings_implied_probability

edge ≥ +cut  →  BET signal  (Tenth-Kelly sizing)
edge ≤ −cut  →  AVOID signal (informational only — don't bet the other side blindly)
−cut < edge < +cut  →  No signal (dead zone)
```
**The cut is PER MODEL — see `docs/thresholds.md`, which is canonical.** Every registered model
has an entry in `config.MODEL_EDGE_THRESHOLDS` / `MODEL_PROB_THRESHOLDS` (a
model without one is a bug, pinned by
`tests/test_config.py::test_every_model_carries_its_own_thresholds`), so the
module-level `BET_EDGE_THRESHOLD` / `AVOID_EDGE_THRESHOLD` fallback is never
reached in practice. It is **0.10**, not the ±3% this section documented until
2026-08-29 — the original spec value, which was raised with the general
tightening and never corrected here.

### Tenth-Kelly Bet Sizing
```
f_q = 0.10 × (model_prob − implied_prob) / (1 − implied_prob)
max bet = min(f_q × bankroll, 5% of bankroll)
```
Switched from quarter-Kelly (0.25) to tenth-Kelly (0.10) on 2026-05-04.
Quarter-Kelly always exceeded the 5% cap for picks meeting min-edge thresholds (10-14%),
producing identical flat bets on every pick. Tenth-Kelly keeps bets at 2-4% of bankroll
and lets edge size drive differentiation. KELLY_MULTIPLIER in config.py is env-overridable.

### Injury Scenarios
- **Scenario A** — Active injury: penalizes team's expected performance
- **Scenario B** — Return from IL: applies ramp factor (0.70 → 0.85 → 1.00 over 5 games)
- **Scenario C** — Opponent injury: positive edge signal for the other team

### Early Season Rule
No picks are generated until a team has played ≥ 10 games.
Prior-season stats are used as the feature baseline during this window.

### NHL Overtime
Full-game moneyline counts OT/SO results.
Regulation-only model uses a separate 3-way market (Home / Draw / Away).
Regulation market often has better value since casual bettors underweight it.

---

## 4. Conventions
- Dates: always ISO format `YYYY-MM-DD`
- Profit: positive = win, negative = loss
- Edge: always expressed as decimal (0.05 = 5%), not percentage
- `home_win = 1` means home team won the full game
- `home_win_reg = 1` means home team won in regulation (NHL only)
- **Season labels differ by sport.** MLB and WNBA = year of play. NHL, NBA and
  NCAAF = ENDING year (NBA 2025 = the 2024-25 season). NBA/NHL seasons straddle
  two calendar years, so the season is threaded explicitly, never derived from a
  game's date.
- **Team ids are 3-letter abbrevs except NCAAF**, which uses the CFBD school name
  (136 FBS programs collide badly in 3 letters). UFC uses fighter slugs; golf
  uses one `games` row per tournament with `away_team = 'FIELD'`.
- **`scored_line` is always the HOME number** for spreads. An away cover is
  `(away − home) − scored_line > 0`. Getting this sign wrong has produced a wrong
  threshold twice (sessions 74 and 87) — it flips every one-run game.

---

## 5. Commands

> **There is no CI on pull requests.** The pipeline runs on the Railway worker
> (`docs/cloud_worker.md`); every one-off job runs locally per
> **`docs/local_ops.md`**. Run `python -m pytest -q tests/` yourself before
> merging. Mobile JS-only merges ship over the air automatically
> (`.github/workflows/mobile-ota.yml` fires on push to master touching
> `mobile/**`); anything touching a native module needs a TestFlight build.
>
> **Every change under `mobile/src` is reviewed by the `frontend-ux-designer`
> agent before its PR opens** — a standing rule, §1b. `/ux-review` runs it.

```bash
python run_pipeline.py                      # full daily pipeline
python run_pipeline.py --step <name>        # one step (see --help for the list)
python run_pipeline.py --dry-run            # preview picks, write nothing
bash scripts/refresh_pass.sh                # one intraday refresh pass
python -m data.threshold_sync               # config.py -> model_action_thresholds
python -m scripts.emit_threshold_sql        # the action-filter SQL, generated
python -m models.trainer --model <id>       # retrain (then COMMIT the .pkl)
python -m pytest -q tests/                  # the only quality gate
streamlit run dashboard/app.py
```

First-time setup, backfills and per-sport training runbooks live in the sport's
own doc (§9) and in `docs/local_ops.md`.

---

## 6. Config topology — where each kind of setting actually lives

Three homes, three different roles. Getting this wrong is how a threshold change
silently fails to reach production.

**Secrets → Railway Variables** (the live copy the worker reads): `DATABASE_URL`
(Supabase **session pooler** string), `ODDS_API_KEY`, `DATAGOLF_API_KEY`,
`CFBD_API_KEY`, `FETCH_F5_LIVE=1`, `TZ=America/New_York`, plus the loop kill
switches (`RUN_LIVE_LOOP`, `RUN_NFL_WIND_CARD`, `LIVE_DAILY_CREDIT_CAP`). The
same keys also sit in the local `.env` for manual CLI runs.
**Railway env edits only take effect on redeploy.** `docs/cloud_worker.md` is the
source of truth for the variable list.

**Thresholds → canonical in `config.py`, mirrored to Supabase.** The scorer reads
`config.py` directly, so the BET decision is config-canonical wherever the code
runs. `data.threshold_sync` (Step 0c of the daily pipeline) mirrors it into the
`model_action_thresholds` table, which the app action filter and the track-record
views read. **A hand edit to that table is temporary** — the next daily run
overwrites it from `config.py` on master. To change a cut permanently, edit
`config.py` and merge; to make it live immediately, edit the table AND merge
before the next 6am run.

**Sportsbooks → `config.py`, env-overridable.** `LINE_SHOP_BOOKMAKERS` drives the
Odds API `bookmakers` param; the param counts as ONE region, so extra books cost
zero extra credits.

### Two invariants that must not be broken

- **The models only ever DECIDE on DraftKings.** `edge`, the BET/AVOID call, the
  Kelly stake, settled P&L and CLV all measure against DK, because every
  threshold was swept on DK-implied edge and best-of-N pricing runs ~2pp cheaper
  in implied probability — adopting it as the qualifying price would loosen every
  cut by that much with nobody deciding to. `scorer._get_dk_odds` /
  `_get_prop_dk_odds`, `paper_tracker._closing_dk_odds` and every feature engine
  hard-filter to DK; `tests/test_multi_book_odds.py` is the tripwire.
  `picks.best_*` records the best price across all books for DISPLAY and for the
  betslip hand-off only (`tests/test_best_line.py` asserts the decision path
  never sees it).
- **ACCESS IS DECIDED IN ONE PLACE, AND IT IS NOT THE SUBSCRIPTIONS TABLE.**
  (2026-08-30, Matt.) A membership bought on Discord (Whop) entitles the app,
  and an app subscription entitles the Discord — so `subscriptions` only ever
  holds half the answer. The gate is `public.my_access()` / `has_app_access()`
  server-side and `useEntitlement()` in the app; gating on
  `useSubscription().entitled` charges a Discord member twice for what they
  already bought. Revocation follows the same rule in reverse, with one
  refinement that must not be lost: **each side revokes only the Discord role
  it granted**, so a lapsed App Store subscription cannot strip a member who is
  still paying Whop. Detail: `mobile/docs/DISCORD_LINKING.md`.
- **Pre-game and in-play prices never mix.** In-play rows are written with
  `snapshot_type='in_play'` and are excluded from pre-game scoring, training
  features and closing-line math. Separately, the evening refresh keeps writing
  `open` rows AFTER first pitch, so any read of a "pre-game" line must also bound
  on `snapshot_at <= commence_time` — see the leak trap in §7.

Full detail (retention and pruning, best-line mechanics, machine paths):
`docs/config_topology.md`.

---

## 7. Hard-won lessons — the traps that have cost us twice

Promoted out of the session log because each one produced a real, shipped bug.
The detail behind every entry is in `docs/sessions/` (grep the session number).

### Analysis and thresholds

- **THE EVALUATION RULE. Any analysis of model performance, thresholds or signal
  timing MUST evaluate every scored pick — `BET`, `AVOID` and dead-zone `NONE`
  alike.** A BET-only sample contains only picks that already cleared the live
  bar, so it is systematically optimistic and cannot see the population a looser
  cut would draw from. The BET-only sweep put `mlb_moneyline` at +29% on 23 bets;
  the full-outcome sample said +4.1% on 50. `mv_scored_pick_outcomes` grades the
  whole universe. Three coverage traps to check FIRST: `NONE` rows only exist
  from 2026-05-12; they were **deleted ~2026-06-26 → 2026-08-09** (July 2026 has
  literally zero for every MLB model); and a game where `abs(edge) >
  MAX_EDGE_CAP` gets **no row at all** (35.3% of `mlb_runline` games). Clean
  windows: 2026-05-12→06-25 and 2026-08-09→present. Re-verify by month; never
  assume. Full version: `docs/signal_timing.md`.
- **Validate the grading before moving a cut.** Recompute outcomes from raw
  scores and reconcile against stored settlements first. A sign bug in away-side
  spread grading (`+scored_line` instead of `−`) survived a threshold change and
  turned a −20.6% cut into a phantom +15%.
- **Require a plateau, not a peak.** A cell whose eight neighbours flip negative
  one grid step away is noise. Report the neighbourhood, the per-season split,
  the bet count and a CI — and when the grid is negative everywhere, say so and
  retrain instead of shipping the least-bad cut.
- **A time split kills most false positives.** Every situational edge in the
  NCAAF search that looked strong pooled (61% wind+rain) collapsed when split
  early/late. Make the split part of the method, not a follow-up.
- **In-sample is in-sample.** Cuts swept on live picks regress forward. State
  which samples are trustworthy by volume and which are not.

### Data integrity

- **Leakage hides in "latest snapshot".** Every bulk feature loader that takes
  the newest odds row must bound on `snapshot_at <= commence_time` AND exclude
  `in_play`. Without it, 67% of completed 2026 WNBA games were featurized with a
  total that had already drifted toward the final score (avg 8.2 pts), which
  invalidated a whole threshold sweep and two models. Guards must FAIL OPEN when
  a timestamp is missing, so synthetic and SBR historical rows survive.
- **A pick stamped after its own first pitch is not a pre-game pick, and any
  measurement against market state must exclude it.** CLV, line movement,
  opening-signal comparisons — all of them difference the pick's number against
  a market snapshot, and that is only meaningful if the pick existed before the
  market closed. Bound on `created_at <= commence_time`, not just on the
  snapshot side. Measured 2026-08-30: **1,046 of 1,249** unmeasured MLB/WNBA
  prop bets carried a `created_at` after `commence_time` (restore/backfill
  restamping — §1c says timing is data, and this is what it looks like when
  that was not honoured), and only 10% of the MLB ones had their `scored_line`
  anywhere in DK's pre-game history. Without the guard they would each have been
  handed a fabricated beat-the-close verdict, **nearly all positive**, because a
  stale number always reads as a favourable move.
- **A self-healing backfill that walks "the oldest N un-done items" jams on the
  items it can never do.** Filter the queue by the SAME predicate the worker
  applies, or the head of the queue is permanently occupied and the backfill
  silently never converges. `_backfill_clv` re-walked the same 40 dates for days
  — eleven of its twelve oldest had zero capturable picks — and the only visible
  symptom was a coverage number that stopped climbing.
- **Parse timestamps before comparing them.** These columns are TEXT in mixed
  shapes (`Z` suffix vs `-04:00` offset vs naive); a string comparison silently
  keeps leaked rows.
- **"Today" is the wrong question for a LIVE loop, and it has now cost two
  outages.** A game carries the `game_date` of its FIRST PITCH, so a 10pm ET
  start is still in the fourth inning at 00:30 the next day — under YESTERDAY's
  date. #296 fixed the UTC half (the worker's `date.today()` rolled at 8pm ET
  and asked for tomorrow); on the very next night the same loop went dark at
  **midnight ET** for the last 77 minutes of three West Coast games, because it
  asked for today's schedule and they were no longer in it. Anything resolving
  which games to poll, price or score uses `config.live_slate_dates()` (today +
  yesterday in the early window), never `today_et()` alone. **Both failures were
  silent for the same reason: "no active games" is also exactly what an empty
  slate looks like** — so the guard is a test, not a log line.
- **Use ET, never UTC, for "today".** `new Date().toISOString().slice(0,10)` is
  tomorrow after 8pm ET. Python has the same trap.
- **A model's PROBABILITY is a separate claim from its point estimate, and
  needs its own gate.** Measured 2026-08-30, twelve models publish probabilities
  6-16pp above what they deliver at the levels actually bet, and it tracks
  sample size rather than sport or market — a model fits its training seasons
  more tightly than any season it has not seen, and every live pick is made out
  of sample. `mlb_live_total_runs` shows it cleanly: in-sample -2pp, on 2025
  +9pp, on 2026 +7 to +13pp, while its point estimate is nearly unbiased. **So a
  retrain is not the fix** — it moves the boundary, not the behaviour. The fix is
  a claimed-to-realised map (`models/probability_calibration.py`,
  `docs/probability_calibration.md`), published but deliberately NOT yet used to
  decide, because every threshold was swept on raw probabilities.
- **Gate the number that gets BET, not the one that is convenient to compute.**
  `_mean_calibration_error` averages bins unweighted and across the whole
  probability range, so a 10pp error in the small band that gets bet is diluted
  by the large well-calibrated band near 0.5. And for a Poisson model it was not
  measuring a probability at all — the count fit passed while the serve-time
  Poisson tail, which is what the scorer bets, was 9-10pp off on its own
  holdout and had never been evaluated. Use `cal_error_actionable`.
- **A stat that is always NULL deletes the training matrix.** One sparse column
  plus `dropna` silently drops most rows (`d_xgf_pct`, the goalie last-5 diffs).
  Check population before adding a feature.
- **Season-to-date rates are noise early.** Blend toward the prior season by
  games played; a raw average over the first month of a 12-game season is the
  single biggest modelling error available.

### Operations

- **A LIVE cutoff decays, so re-derive it rather than setting it once.** A
  pre-game model is scored daily against a line that barely moves; a live model
  locks at the first crossing of a market that moves every few seconds. On
  2026-08-29 the first-signal lock plus 5s polling took MLB live from ~35% of
  games producing a bet to **100%** — ~63 bets/week — at an UNCHANGED threshold.
  Nobody moved a cut; the meaning of the cut moved. `tracking/live_calibration.py`
  re-derives every live cut each pass and publishes it (monitor → Live tuning),
  and its verdict is allowed to be "no cut works, retrain or pause".
- **Project volume from the CURRENT regime, not the lifetime average.** The
  lifetime average said 10 live bets/week while the live rate was ~60, because it
  averaged five quiet weeks with the two days after the machinery changed. A
  threshold chosen off that number is chosen for a world that no longer exists.
- **A retrained model must have its `.pkl` COMMITTED.** The registry row points
  at a path; if the artifact is not in the repo the worker cannot load it and the
  model silently stops scoring. This has cost a month of UFC picks and a
  four-week outage across three MLB prop models.
- **A model in `config.MODELS` with no `FEATURE_MAP` entry raises before the
  artifact is even looked at — and kills scoring for EVERY sport.** One missing
  key produced zero game-level picks league-wide for a day, visible only as an
  empty board for one sport. A derived test asserts the two stay in sync; keep
  it.
- **A table created at write time must not re-run its DDL on every write, and
  `IF NOT EXISTS` does not make it free.** `CREATE INDEX IF NOT EXISTS` takes a
  SHARE lock and `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` takes ACCESS
  EXCLUSIVE whether or not the object is already there — and **every one of them
  fires Supabase's `pgrst_ddl_watch`, so PostgREST answers 503 to the whole app
  while it rebuilds its schema cache.** Seven modules did this on every call.
  Measured 2026-09-01 from `pg_stat_statements`: `ALTER TABLE api_call_log
  ENABLE ROW LEVEL SECURITY` 1,676 calls at a 7.8s mean, `CREATE INDEX IF NOT
  EXISTS idx_api_call_ts` 1,925 calls at a 15.1s mean — **11.6 hours of database
  time and ~3,600 forced cache reloads**, 232 of which then hit the 8s
  `authenticator` timeout. The visible symptom was one screen: the Stats tab
  showing "Connection error" over an empty board. It is self-reinforcing —
  `monitoring/probe.py` re-ran its ensure block on every reconnect, so the more
  the database struggled the more DDL it got. Gate every write-time ensure block
  on `data/ddl_guard.schema_is_current`, which fails open;
  `tests/test_ddl_guard.py` is the tripwire for the next one. **Judge these
  statements per INVOCATION, not per millisecond** — `CREATE TABLE IF NOT
  EXISTS` costs 5-7ms and looks free, but it ran 3,479 times from one module
  and every one was a cache reload. The first tripwire missed
  `tracking/threshold_review.py` entirely by grepping only for the RLS
  statement: **a test scoped to the symptom already found is not a tripwire**,
  and only deliberately reverting the fix showed it.
- **An empty board and a broken pipeline look identical.** Prefer writing a
  "declined, and here is why" row over `return []`. Check
  `pipeline_runs.failed_steps` before blaming thresholds, and `push_sent` before
  believing a notifier ever worked — nothing is ledgered unless a POST confirmed,
  so a `kind` with zero rows means it has NEVER succeeded.
- **A health check must not gate on the thing that breaks.** Two checks reported
  SKIPPED for the entire outage they existed to catch, because they keyed off
  data the failing feed produces.
- **A swallowed exception plus a legitimately empty channel is invisible.** Live
  Discord posts raised on every call for five days behind a correct try/except.
  Where a caller must swallow, test the producer REAL output through the real
  renderer — a hand-written fixture drifts from the producer exactly as the
  renderer did.
- **Supabase: after creating anything in `public`, REVOKE from `anon` and
  `authenticated` BY NAME.** Default privileges grant them EXECUTE/ALL, and
  `REVOKE ... FROM PUBLIC` does nothing. Matviews have no RLS at all — anon held
  MAINTAIN (i.e. `REFRESH`) on one, and SELECT+INSERT+UPDATE+DELETE on a
  2.2M-row irreplaceable archive. Run `get_advisors(security)` after every
  migration and read the result, not the intent.
- **The Odds API returns `x-requests-remaining` on every response, including a
  401.** A silent quota exhaustion took out every feed for 2.5 days. Check the
  live figure (`odds_api_quota`), never a code comment.

### Verification standards — what "verified" means here

- **`git stash` is NOT a master baseline once the work is committed.** Use
  `git worktree add --detach origin/master` and diff against that. Local
  `master` in these sandboxes is routinely dozens of commits behind — always
  compare to `origin/master`.
- **Report a tsc or pytest baseline as an error-SET diff, not a count.** The
  mobile tree carries a documented set of pre-existing `queries.ts` cast errors;
  the claim to make is "byte-identical to master, 0 in touched files".
- **Read source with an explicit encoding.** A dozen tests assert things about
  the repo's own source by reading it back, and `read_text()` with no encoding
  uses the PLATFORM default — cp1252 on Windows, where this repo actually runs.
  The source is full of box-drawing characters, so those tests did not fail, they
  raised `UnicodeDecodeError`, and one raised it at COLLECTION time, which
  aborted the entire suite. The repo's only quality gate was unrunnable on the
  only machine that runs it. Fixed 2026-08-30; keep `encoding="utf-8"` on every
  source read.
- **Check whether deps actually install before hand-waving.** PyPI is often
  reachable from these sandboxes — a real suite run beats "run it on your
  machine". Equally, the sandbox egress limits are not the system limits (§1b).

---

## 8. Current state — the 30-second version

- **Live sports:** MLB, WNBA, NBA, NHL, UFC, GOLF, NFL, NCAAF. ~70 models carry
  their own prob/edge cut in `config.ACTION_THRESHOLDS`; 26 are paused.
- **The platform is LIVE, not paper trading.** The go-live gate (≥50 settled
  picks, positive flat ROI, calibration ≤5%) is per MODEL — a new or retrained
  model is paper-only until it clears, and that is stated in its own doc.
- **Where it runs:** the Railway worker (`scheduler.py`) — 6am daily pipeline,
  intraday refresh passes, the MLB and NCAAF live loops, the NFL card poll.
  See `docs/cloud_worker.md`.
- **Where picks go:** Supabase `picks` → the mobile app, the Discord channels,
  and Claude mobile.
- Per-model records, thresholds and their evidence: `docs/thresholds.md`.

---

## 9. Where everything else lives

| Topic | File |
|---|---|
| **Agents — Sentinel (pipeline watch) and Janitor (backlog runner)** | `docs/agents_contract.md` |
| **Janitor's worklist — the durable follow-up backlog** | `docs/followups.md` |
| Session-by-session history (192 entries — grep it) | `docs/sessions/README.md` |
| Thresholds, review cadence, per-model evidence | `docs/thresholds.md` |
| Claude-mobile picks prompt + the generated SQL | `docs/mobile_picks_prompt.md` |
| Discord routing, producers, delivery post-mortems | `docs/discord.md` |
| Auth, billing, Discord membership (one membership, two surfaces) | `mobile/docs/{AUTHENTICATION,BILLING,DISCORD_LINKING}.md` |
| Live (in-play) betting — models, loop, credit safety | `docs/live_betting.md` |
| Live monitor dashboard | `docs/monitoring.md` |
| Probability calibration (claimed vs realised) | `docs/probability_calibration.md` |
| Health checks + retrain workflow | `docs/health_checks.md` |
| Opening-signal shadow track | `docs/opening_signals.md` |
| Signal-timing analysis + the full evaluation rule | `docs/signal_timing.md` |
| Config topology in full (retention, best line) | `docs/config_topology.md` |
| Railway worker, schedule, variables | `docs/cloud_worker.md` |
| Local commands (retrains, backfills, EAS, pytest) | `docs/local_ops.md` |
| Test suite coverage | `docs/testing.md` |
| Push-notification enablement | `docs/push_notifications.md` |
| Support runbook for in-app feedback | `docs/feedback.md` |
| Front-end UX review checklist (the `frontend-ux-designer` agent's contract) | `mobile/docs/UX_REVIEW.md` |
| Player news feed + the "Recent News" sheet | `docs/player_news.md` |
| Live-odds freshness investigation | `docs/live_odds_freshness.md` |
| Prediction markets evaluation | `docs/prediction_markets_eval.md` |

**Per sport:** `docs/sports/{mlb,wnba,nba,nhl,ufc,golf,nfl,ncaaf}.md` — each
carries that sport's models, data sources, load-bearing conventions, pipeline
steps and first-time setup.

**History (provenance, not instructions):** `docs/history/build_state.md` (build
state, data sources, model registry, spec decisions),
`docs/history/learnings.md`, `docs/history/stale_next_steps.md`.

---

*CLAUDE.md was 909 KB on 2026-08-30. Keep it under ~30 KB: new work goes in
`docs/sessions/`, and only rules that govern future sessions get promoted here.*

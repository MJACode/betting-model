# CLAUDE.md — Betting Model Project Context

> **This file is the always-loaded layer. It holds only what a session must know
> BEFORE it decides which file to open**: how to reply, the rules that no folder
> can trigger, the business logic, and the map.
>
> **Everything else loads by itself, at the moment it applies.** Three layers,
> and §10 says how to choose between them:
>
> | Layer | Lives in | Arrives |
> |---|---|---|
> | Always | this file | every session |
> | When you touch the code it governs | `.claude/rules/*.md` | on opening a matching file |
> | When you go looking | `docs/**` | you read it |
>
> Nothing was deleted to make this file smaller — every rule is in one of the
> three layers and §10 says which. **Section numbers never change**, because
> `config.py`, the models and ~300 lines of `docs/` cite them; a section whose
> body moved keeps its number and points at the new home.
>
> **Read Section 00 first — no guessing, factual answers only. Then Section 0,
> the required format for every reply.**

---

## 00. CLAUDE IS NOT ALLOWED TO GUESS. FACTUAL ANSWERS ONLY.

**This is above Section 0 because it outranks the format of a reply: it governs
whether the reply is allowed to exist.** mike, 2026-09-06, after a session that
did it twice: *"Claude is not allowed to guess, factual answers only. Claude
will delete its own source code if it tries guess."*

Say only what you have established. Not what is likely, not what the shape of
the system suggests, not what was true last time someone looked.

**Before any factual claim — a number, a time, a state, a cause — answer one
question: how do I know this?** If the answer is not "I ran X and it returned
Y", it is not sayable. Go and get it; every route is open (§1b).

**"I don't know, and here is the query that would tell us" is a complete
answer.** A confident number in its place is not — it is a wrong answer nobody
has noticed yet.

Three things that are guessing while not feeling like it: **reasoning from the
code to the behaviour** (the source says what should happen, only the data says
what did); **reusing a fact past its timestamp** (an hour-old value is a memory,
not a measurement); and **narrating the check instead of doing it** — never
write "checking rather than guessing", verification is the floor, not an
achievement.

This is the general rule. §1b's NEVER ESTIMATE WHAT YOU CAN MEASURE is its
measurement-shaped case and §7's standards its testing-shaped case; when they
seem to conflict, this one wins. Evidence: `docs/rules_evidence.md`.

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

> **The measured story behind every rule below is in `docs/rules_evidence.md`** —
> the outages, the queries, the numbers. Read it when you are questioning a rule
> or changing one. The rules themselves are complete as stated here.

**API credits and spend.** Do NOT assume what the credit ceiling is, and do NOT
scope work around a guessed budget. Matt sets the ceiling, not Claude. If a
piece of work looks like it will use a meaningful number of credits, ASK HIM
FIRST and state the number. Check the live figure before saying anything about
quota (`odds_api_quota` in Supabase, or the `x-requests-remaining` header),
never a code comment — a stale 20k comment once turned a real 5,000,000-credit
plan into a wrongly scoped-down analysis.

**NEVER ESTIMATE WHAT YOU CAN MEASURE.** (Added 2026-08-30 at mike's request;
the absolute form is **§00**, which outranks this and everything else.)
Before stating *when*, *whether*, *how much*, or *how long*, ask one question:
**do I have what I need to check this right now?** If yes, check. An estimate is
not a faster version of the answer — it is a wrong answer you have not noticed
yet. The failure is always the same shape: reaching for the FAMILIAR SHAPE OF
THE TASK instead of the facts already in hand, and the tell is confidence — a
guess that knows it is a guess gets hedged, and these never are.

Three forms, each of which produced a real wrong answer here:

- **A time estimate** — state the clock arithmetic, don't round to "tomorrow".
- **A number** — name the query that produced it AND what it excludes.
- **A test** — it is not finished until you have WATCHED IT FAIL. **A test that
  passes without the fix is not a test, and a guard that dead code can satisfy
  is not a guard.**

This is the general form of the sandbox rule below, and of §7's verification
standards. Those say "go and look" for one specific case each; this says it for
every case.

**THE SANDBOX'S LIMITS ARE NOT THE SYSTEM'S LIMITS. Never report "I can't reach
X" as a conclusion.** The dev sandbox has a narrow egress allowlist. The SYSTEM
does not. Four routes reach anything, and a blocker report must name which were
tried and what each returned:

1. **WebSearch / WebFetch** — docs, vendor pricing, API coverage, the public web.
2. **The Railway worker** — open egress, already holds `ODDS_API_KEY`,
   `DATABASE_URL`, `DATAGOLF_API_KEY`. Any script in the repo can run there: push
   it, then point a one-off service's start command at it (`prop-probe` exists for
   this) or add a scheduler job. See `docs/cloud_worker.md`.
3. **Matt's machine** — ask for a specific command, not a vague blocker.
4. **The Supabase MCP** — READS production. It does not write.

**The general form of this rule — a banner is not a test, reachability and
capability are two separate measurements, a missing credential is not a missing
capability, one absent route is not zero routes — is in the global
`~/.claude/CLAUDE.md` §0 and loads on every project.** It is not repeated here.
What is project-specific is the four routes above and the MEASURED limit of each
tool, which the session-start hook injects verbatim
(`.claude/hooks/connector_reminder.json`): Supabase `execute_sql` is read-only,
Railway `list-variables` hides the values, and there is no node and no Railway
CLI on this machine. The cases that cost a day each: `docs/rules_evidence.md`.
**THE CURRENT STATE OF A SYSTEM IS NOT ITS CAPABILITY, AND WORK YOU CAN DO IS
NOT AN ACTION ITEM FOR MATT.** (Added 2026-09-01.) Two halves, both common:

- **Before reporting that data does not exist, check what the SOURCE offers,
  not what the table holds.** "Pinnacle history doesn't exist" was a query
  against what had been stored; the endpoint had offered it for years and we
  had never asked.
- **A handover is a last resort with a reason attached, not a way to end a
  turn.** Work that can run on the worker runs there: a row in `worker_jobs`,
  or an entry in `jobs/declared_jobs.json` (`tracking/job_queue.py`).

The tell is the same in both: a turn that ends with a tidy summary and a to-do
list FOR SOMEONE ELSE feels finished. It is the work redistributed. Ask instead:
what did I actually change, and what did I merely describe?

**EVERYTHING GOES IN SUPABASE. THERE ARE NO EXCEPTIONS, AND A TOLERATED ONE IS
NOT A RULE.** (mike, 2026-08-30 and again 2026-09-12: *"EVERYTHING SHOULD BE IN
SUPABASE FOR THE MILLIONTH FUCKING TIME. Need a global rule."*) Supabase is the
system of record: **any dataset that cost money or time is stored there FIRST**,
before it is analysed, modelled on or committed. **A local file is a CACHE OF
Supabase or it is a bug** (`data/local_store.py` is the sanctioned shape:
opt-in, gitignored, regenerable, every row already in the database); a Railway
volume is ONE COPY, not a backup; and an ingestor that buys data writes it in
the same run, keyed on a `source` marker so a re-run imports nothing already
stored. The old version of this rule carried exceptions "worth fixing when
touched" and nobody touched them: 655 MB of PAID NFL odds history sat on one
laptop for a fortnight. `tests/test_everything_in_supabase.py` fails on any
undeclared store on disk, and the fix is an importer, not an allowlist entry.

**A LOSING MODEL IS AN ASSESSMENT TO RUN, NOT A MODEL TO PAUSE — AND "SHOULD WE
UNPAUSE IT?" IS NEVER A QUESTION TO ASK.** (mike, 2026-09-12.) A pause banks the
loss and ends the search. A losing model — paused or live — gets the FULL SWEEP
first: every scored pick (§7's evaluation rule), a grid reported as a
NEIGHBOURHOOD not a peak, an early/late split, a bet count, a confidence
interval, and every candidate re-graded on the artifact `model_registry` says is
LIVE (a pooled record blends retired models). **"No cut clears, here is the grid
and here is what would have to change" is a complete answer; "shall I unpause
it?" is not.** `scripts/paused_model_assessment.py`,
`docs/paused_model_assessment.md`.

**EVERY MODEL UPDATE IS STAMPED WITH WHO ASKED FOR IT** — the git trailer
`Updated-By: mike` (or `matt`) on the commit that lands it, and **if you do not
know whose call it is, ASK before committing.** A retrain, a registry swap, a
threshold move, a pause or unpause, a feature-list change, a new or retired
model. Not plumbing, cadence, docs or mobile UI. The full definition, plus **one
model's operational change is assessed against all of them** and the live-prop
hypothesis → **`.claude/rules/model-updates.md`** (loads on `config.py`,
`models/**`, `nfl/live_model/**`, `docs/thresholds.md`).

**THE APP, DISCORD AND PUSH SHOW THE SAME PICKS. THEY ARE IDENTICAL.** (Matt,
2026-09-05.) Every publishing surface reads **`picks`** and applies the same
`model_action_thresholds` cut the app's `passesActionFilter` applies. A surface
that reads anything else will disagree, and the disagreement is always silent.
**No publishing surface gets a date horizon; one publisher at a time; one pick,
one key; a VOID pick is neither publishable nor displayable; live picks post to
their sport's live channel.** → **`.claude/rules/picks-and-publishing.md`**,
which loads on `tracking/**`, `models/**`, `nfl/**`, `ncaaf_live/**`,
`mobile/src/**` and the migrations. Read it before touching any surface.

**Front-end changes are reviewed by the UX designer agent before their PR
opens — always.** The full rule loads automatically from
`.claude/rules/frontend.md` when a file under `mobile/` is opened.

**WRITE THE SESSION SUMMARY TO `docs/sessions/`, NOT TO THIS FILE.**
(Repo-level rule, 2026-08-30.) "Update CLAUDE.md after every commit" grew this
file to 909 KB — ~225k tokens re-read at the start of every session. The split:

- Every session appends its summary to **`docs/sessions/<YYYY-MM>.md`**, newest
  first, and adds a row to `docs/sessions/README.md`. Same detail as before —
  what changed, why, what was verified, what was deliberately not done.
- Reference material for one sport or subsystem goes in its own `docs/` file
  (the map is §9). Update the doc, not this file.
- **Only PROMOTE into CLAUDE.md** when something becomes a rule that governs
  FUTURE work: a standing instruction, a convention, an invariant, or a trap
  that has now bitten twice (§7). State the RULE here and put its evidence in
  `docs/rules_evidence.md`.

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
that is LINE MOVEMENT: it does not retract the bet, does not change the number
that was given, and **must never delete or overwrite the row**. Every model locks
its pick — game-level at the first scoring run, props at the first signal on a
confirmed lineup, live at the first BET per lane, NFL wind/opener by
construction. **Timing is data, not metadata:** `created_at` is when the number
was available and is part of the pick's meaning.

- **A SETTLED PICK LEAVES THE RECORD ONLY TWO WAYS, AND A PAUSE IS NEITHER.**
  (mike, 2026-09-12: *"Pausing a model should not erase settled record unless I
  explicitly say so."*) A pick is in the record because it was WRITTEN as a
  BET; no pause, threshold change or retrain reaches back and removes one.
  One query answering both "may bet next" and "did bet" moves the number with
  nothing deleted — 55 settled NCAAF bets, overnight. A record query filters on
  what the pick WAS (`signal_type='BET'`, a real result, in the window), never
  joining `model_action_thresholds`. The exits: **VOID** — a row the model should never
  have PRODUCED, not one overtaken by LINE MOVEMENT. `scripts/void_picks.py`
  sets `result='NO_ACTION'` + `condition_status='VOID'`, keeps `created_at`,
  the line, the price and the lock, and REFUSES a graded pick (deleting
  destroys the evidence) — and **`config.RECORD_EXCLUSIONS`**, naming who
  asked. Sweep views DO re-cut (§7). Test:
  `tests/test_settled_record_is_immutable.py`.
  **A paused model is LISTED, not hidden** (mike, same day: *"Don't hide detail
  of paused models unless I say so"*) — labelled "Paused", record shown. Hiding
  it left the Record tab counting a model the Models tab did not list. RETIRED
  differs: nothing will score for it again.

**The mechanics — the four lock flags, the remaining corollaries and the
`picks_log` backstop — are in `.claude/rules/picks-and-publishing.md`**, which
loads whenever you open code that could break them. The question to answer before
any scorer loop ships: *when this re-runs and the line has moved, what happens to
the pick that already exists?* The only acceptable answer is "nothing".

## 2. Project Purpose
Building a **personal sports betting model** targeting **DraftKings** as the
primary sportsbook. The long-term goal is all major US sports with all player
props. Seven sports are live today — MLB, WNBA, NBA, NHL, UFC, NFL and NCAAF
(§8). **GOLF was retired 2026-09-08** (mike) — `config.RETIRED_MODELS`.

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

**`nfl_live_prop` is LIVE with the gate deliberately NOT met** (Matt,
2026-09-05). Settled record at go-live: zero — it wrote to a JSONL file, so it
could never have cleared the gate by waiting. Raised, restated, his call. **Do
not pause it or restore the gate without asking him.** Re-sweep its cut at ~50
settled bets; it runs 0.0/0.0 because the cut is EV, in
`nfl/live_model/config.EV_THRESHOLDS`. Detail: `docs/rules_evidence.md`.

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
`f = 0.10 x (model_prob - implied) / (1 - implied)`, capped at 5% of bankroll.
Quarter-Kelly always hit that cap at our edge sizes, so every pick got the same
flat bet; tenth-Kelly keeps bets at 2-4% and lets edge drive the difference
(2026-05-04). `config.KELLY_MULTIPLIER` is env-overridable.

### Injury Scenarios
- **Scenario A** — Active injury: penalizes team's expected performance
- **Scenario B** — Return from IL: applies ramp factor (0.70 → 0.85 → 1.00 over 5 games)
- **Scenario C** — Opponent injury: positive edge signal for the other team

### Early Season Rule
No picks until a team has played >= 10 games; prior-season stats are the
baseline in that window. Season-to-date rates are noise early — blend toward
the prior season by games played.

### NHL Overtime
Full-game moneyline counts OT/SO; the regulation model prices a separate 3-way
market (`docs/sports/nhl.md`).

---

## 4. Conventions
- Dates: always ISO format `YYYY-MM-DD`
- Profit: positive = win, negative = loss
- **RESULTS ARE ALWAYS IN UNITS. NEVER DOLLARS.** (mike, 2026-09-08: *"why are
  you expressing results in dollars, I have hard coded units everywhere, I want
  that a global rule."*) One unit = one flat bet. A record is "-206.7 units over
  3,201 bets", never "-$20,670 at $100 flat" — the dollar figure invents a stake
  size nobody chose, changes meaning the moment the bankroll does, and cannot be
  compared against any other number in this repo. This governs EVERY surface:
  replies, docs, commit messages, the dashboard, Discord, the app. `profit_flat`
  is stored as dollars-per-$100 stake, so divide by 100 to report it.
- Edge: always expressed as decimal (0.05 = 5%), not percentage
- `home_win = 1` means home team won the full game
- `home_win_reg = 1` means home team won in regulation (NHL only)
- **Season labels differ by sport.** MLB and WNBA = year of play. NHL, NBA and
  NCAAF = ENDING year (NBA 2025 = the 2024-25 season). NBA/NHL seasons straddle
  two calendar years, so the season is threaded explicitly, never derived from a
  game's date.
- **Team ids are 3-letter abbrevs except NCAAF**, which uses the CFBD school name
  (136 FBS programs collide badly in 3 letters). UFC uses fighter slugs.
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
pip install -r requirements-dashboard.txt   # dashboard deps, not on the worker
streamlit run dashboard/app.py
```

First-time setup, backfills and per-sport training runbooks live in the sport's
own doc (§9) and in `docs/local_ops.md`.

---

## 6. Config topology — where each kind of setting actually lives
Three homes, three different roles. Getting this wrong is how a threshold change
silently fails to reach production.

- **Secrets → Railway Variables**, mirrored in the local `.env` for CLI runs.
  **Railway env edits only take effect on redeploy.** `docs/cloud_worker.md` is
  the source of truth for the variable list.
- **Thresholds → canonical in `config.py`, mirrored to Supabase** by
  `data.threshold_sync` (Step 0c of the daily pipeline). The scorer reads
  `config.py`, so the BET decision is config-canonical wherever it runs. **A hand
  edit to `model_action_thresholds` is temporary** — the next 6am run overwrites
  it from `config.py` on master.
- **Sportsbooks → `config.py`, env-overridable.** `LINE_SHOP_BOOKMAKERS` is what
  gets fetched; `BEST_LINE_BOOKMAKERS` is the set a pick may be DECIDED at.

**The invariants that must not be broken are in
`.claude/rules/config-topology.md`** (loads on `config.py`, the scorers,
`data/threshold_sync.py`, `scheduler.py`) — breaking one means editing a file it
is scoped to. In one line each, so you know they exist:

- **A pick is decided, sized and settled at the best bettable price**, and the
  row records which price and whose line (`decision_*`, read as
  `COALESCE(decision_x, dk_x)`). DraftKings stays the REFERENCE for features and
  CLV.
- **A player prop DraftKings does not list is scored off the first bettable book
  that does** — in `BEST_LINE_BOOKMAKERS` order, never by price. `line_book`
  names it. These picks are a NEW population; report them separately.
- **`picks.profit_flat` fabricates -110 for any pick with no price**, so every
  read of it must be gated on a non-NULL price.
- **Access is decided by `public.my_access()`, not the `subscriptions` table** —
  one membership entitles both the app and Discord.
- **Pre-game and in-play prices never mix**, and the evening refresh keeps
  writing `open` rows after first pitch, so bound on
  `snapshot_at <= commence_time`.

Full detail (retention and pruning, best-line mechanics, machine paths):
`docs/config_topology.md`.

---

## 7. Hard-won lessons — the traps that have cost us twice

Each one produced a real, shipped bug. **The measured story behind every entry —
the numbers, the outages, the queries that found them — is in
`docs/rules_evidence.md`.** Read it before you decide a rule does not apply to
your case; the rules below are complete as stated, the evidence is why.

### Analysis and thresholds

- **THE EVALUATION RULE. Any analysis of model performance, thresholds or signal
  timing MUST evaluate every scored pick — `BET`, `AVOID` and dead-zone `NONE`
  alike.** A BET-only sample contains only picks that already cleared the live
  bar, so it is systematically optimistic and cannot see the population a looser
  cut would draw from. `mv_scored_pick_outcomes` grades the whole universe.
  Three coverage traps to check FIRST: `NONE` rows only exist from 2026-05-12;
  they were **deleted ~2026-06-26 → 2026-08-09**; and a game where `abs(edge) >
  MAX_EDGE_CAP` gets **no row at all**. Clean windows: 2026-05-12→06-25 and
  2026-08-09→present. Re-verify by month; never assume.
  Full version: `docs/signal_timing.md`.
- **The method rules — validate the grading before moving a cut, require a
  plateau and not a peak, split early/late, in-sample is in-sample** — are in
  `.claude/rules/analysis-and-thresholds.md`, which loads on `models/**` and
  `scripts/**`. They were duplicated here word-for-word until 2026-09-12.
### Data integrity, and Operations

**These moved to `.claude/rules/` on 2026-09-03** and load automatically when
Claude opens a file they apply to — `data-integrity.md` for `data/`, `models/`,
`tracking/`, `monitoring/`; `operations.md` for the pipeline, the scheduler and
the scripts. Twenty-one rules, none rewritten, costing nothing on a session that
never touches those directories.

They are NOT optional reading that got demoted. A path-scoped rule is *more*
reliably present than a line in a long file: it arrives in context at the moment
the file is opened, rather than 700 lines earlier. What stays here is what has
to be known BEFORE deciding which file to open.

- **A TEST WRITTEN FROM THE SAME UNDERSTANDING THAT PRODUCED THE CODE INHERITS
  ITS BLIND SPOT.** Five guards in one day (2026-09-04) passed while the thing
  they guarded was broken — each checked the case its author had in mind, which
  is the case the code already handled.
  **So a guard is not evidence. Go and look at the running system** — the
  catalog after an apply, the worker's own scheduled cycle rather than your
  hand-run of it, the row counts a query returns rather than the exit code.
  The test is what stops a fixed bug returning; it is not what finds one.
  All five, and what each missed: `docs/rules_evidence.md`.

### Verification standards — what "verified" means here

- **`git stash` is NOT a master baseline once the work is committed.** Use
  `git worktree add --detach origin/master` and diff against that. Local
  `master` in these sandboxes is routinely dozens of commits behind — always
  compare to `origin/master`.
- **Report a tsc or pytest baseline as an error-SET diff, not a count.** The
  claim to make is "byte-identical to master, 0 in touched files".
- **Read source with an explicit encoding.** `read_text()` with no encoding uses
  the PLATFORM default — cp1252 on Windows, where this repo actually runs — and
  this repo's source is full of box-drawing characters. One such read raised
  `UnicodeDecodeError` at COLLECTION time and aborted the entire suite, leaving
  the only quality gate unrunnable on the only machine that runs it. Keep
  `encoding="utf-8"` on every source read.
- **Check whether deps actually install before hand-waving.** PyPI is often
  reachable from these sandboxes — a real suite run beats "run it on your
  machine". Equally, the sandbox egress limits are not the system limits (§1b).

---

## 8. Current state — the 30-second version

- **Live sports:** MLB, WNBA, NBA, NHL, UFC, NFL, NCAAF. 65 models carry their
  own prob/edge cut in `config.ACTION_THRESHOLDS`; 14 are paused.
- **GOLF was RETIRED 2026-09-08** (mike). `DATAGOLF_API_KEY` was never set on
  the worker, so every golf pipeline step no-opped and the sport produced no
  games, no odds and no picks, ever. The ingestors, feature engine and pipeline
  steps are left in place; reviving it starts with the key, not with config.
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
| **Agents — why the scheduled ones were all retired** | `docs/agents_contract.md` |
| **The durable follow-up backlog** | `docs/followups.md` |
| Session-by-session history (192 entries — grep it) | `docs/sessions/README.md` |
| Thresholds, review cadence, per-model evidence | `docs/thresholds.md` |
| Claude-mobile picks prompt + the generated SQL | `docs/mobile_picks_prompt.md` |
| Discord routing, producers, delivery post-mortems | `docs/discord.md` |
| Auth, billing, Discord membership (one membership, two surfaces) | `mobile/docs/{AUTHENTICATION,BILLING,DISCORD_LINKING}.md` |
| Live (in-play) betting — models, loop, credit safety | `docs/live_betting.md` |
| Live monitor dashboard | `docs/monitoring.md` |
| Calibration — claimed vs realised, the sweep, the weekly pass | `docs/probability_calibration.md` |
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
| Sportsbook logos in the line pills (and why a label ships first) | `docs/book_logos.md` |
| **Can a paused model be profitable? The standing assessment** | `docs/paused_model_assessment.md` |
| **Evidence behind the §1b and §7 rules** | `docs/rules_evidence.md` |
| Live-odds freshness investigation | `docs/live_odds_freshness.md` |
| **Model artifacts: present, tracked, and loadable** | `docs/artifact_integrity.md` |
| **NFL wind: how far out it may fire, and the lead evidence** | `docs/nfl_wind_lead_evidence.md` |
| **NFL props: near kickoff is the only well-evidenced regime** | `docs/nfl_prop_offset_evidence.md` |
| Best line on pre-game picks | `docs/best_line.md` |
| Which prop markets the feed actually serves | `docs/market_coverage.md` |
| **The historical team-stats leak** | `docs/team_stats_leak.md` |
| Rebuilding the team-stats tables (scope) | `docs/team_stats_rebuild_scope.md` |
| Prediction markets evaluation | `docs/prediction_markets_eval.md` |
| **Who has beaten player props, how, and with what data** | `docs/prop_market_research.md` |
| **Odds providers: what exists, what it costs, what it adds** | `docs/odds_sources.md` |
| **The eleven NFL prop models hold no information the line lacks** | `docs/nfl_prop_information_test.md` |
| **The search for a profitable NFL prop model: tackles was the wrong stat, DK is flat** | `docs/nfl_prop_profitability_search.md` |
| **The stat models: what is exhausted, what the outside world does, the one method left (market-anchored shape simulation)** | `docs/nfl_prop_method_search.md` |
| **NFL prop lines lean over — the measured bias, and the per-side cut it bought** | `docs/nfl_prop_over_lean.md` |

**Per sport:** `docs/sports/{mlb,wnba,nba,nhl,ufc,nfl,ncaaf}.md` — each
(`golf.md` is kept as the revival runbook for the retired sport) —
carries that sport's models, data sources, load-bearing conventions, pipeline
steps and first-time setup.

**History (provenance, not instructions):** `docs/history/build_state.md` (build
state, data sources, model registry, spec decisions),
`docs/history/learnings.md`, `docs/history/stale_next_steps.md`.

---

## 10. Where a NEW rule goes — the only question to ask

**Can this rule ONLY be broken by editing files in a known folder?** That is the
whole decision.

| If the rule… | it goes in | and it arrives |
|---|---|---|
| governs every reply, or is needed BEFORE deciding which file to open | **this file** | always |
| can only be broken by editing files in one area | **`.claude/rules/<topic>.md`**, with `paths:` frontmatter | when Claude opens one of them |
| is a measured fact about a tool or this machine | **`.claude/hooks/connector_reminder.json`** | injected at session start |
| is what happened, or the evidence behind a rule | **`docs/sessions/<YYYY-MM>.md`** / **`docs/rules_evidence.md`** | when someone reads it |

**The test that matters is the one that has already failed.** On 2026-09-12 a
pause erased 55 settled bets, and that session edited one line of `config.py` —
it opened nothing under `tracking/`, `mobile/src/` or `data/migrations/`. A
folder-scoped copy of "a pause must not erase a settled record" would not have
loaded for the session that broke it. So: **anything reachable WITHOUT opening a
file — pausing a model, running SQL, answering a question — stays here.**

Four rules are pinned here by tests that assert the rule is in THIS file, not
merely somewhere in the repo: `test_everything_in_supabase.py`,
`test_settled_record_is_immutable.py` (two) and
`test_paused_model_assessment.py`. Do not move them out.

**Putting a rule in `.claude/rules/` is NOT demoting it.** It arrives at the
moment it applies, beside the code it governs, instead of 700 lines earlier in a
file that was skimmed.

**Two obligations when a rule moves out:**

1. **Leave a one-line pointer here**, under its original section number — the
   rule, the file, and what opens it. A session doing analysis in SQL touches no
   file in `tracking/`, so the pointer is how it learns the rule exists.
2. **Never renumber a section.** `config.py`, the model code and ~300 `docs/`
   lines cite §1b, §1c, §6, §7. A section whose body moved keeps its number and
   becomes the signpost.

**Nobody has to police the size of this file.** `tests/test_context_budget.py`
does: a cap on this file, a cap on this file PLUS the session-start hook (so
moving prose between them cannot game it), a per-file cap on each rules file, and
a check that every rules file is pointed at from here. It fails once, at merge
time, for whoever grew it — which is why no session needs to spend a reply on it.

*Layered 2026-09-12: three layers and a routing rule (§10) replaced "keep this
file under ~30 KB", which was repeated in three places and re-read every
session. `tests/test_context_budget.py` holds the budget now. Nothing was
deleted — §10 says where each rule went.*

---
name: league-models
description: Build, audit or extend the betting models for EVERY market in one league — a league we have never bet, new markets in a league we already bet, or a full audit of one league's markets. Use when asked to "build models for <league>", "add <league>", "audit all <league> markets", "why is nothing firing in <league>", "what else can we bet in <league>", or to port what was learned in one sport to another. It is the framework for that work: the market grid, prices before models, the market as the baseline, a method search per market, the kill tests, ship what passes live, keep improving on live data — and invent new methods when the known ones run out.
---

# /league-models <league> [market … | audit]

One league, every market the books offer, worked to a verdict. With no market
named, the scope is the whole league. `audit` means the league already has
models: start from what they did, not from zero.

This file is the method. The detail lives beside it and is read when the step
that needs it starts:

| File | Read it at |
|---|---|
| `references/market-grid.md` | step 1: the grid template, the market families, every route to a price |
| `references/methods.md` | step 5: every method tried in this repo, where it worked, where it failed and why, and the untried ones |
| `references/kill-tests.md` | step 6: the tests that killed false edges here, and how to run each |
| `references/porting-traps.md` | steps 2–3: what a copy of existing code got wrong on a new league's data |
| `references/shipping.md` | step 7: every file, table, test and production step a new model or sport touches |

**The catalog is a starting set, not a boundary.** Step 5 ends with inventing
methods, and step 9 writes every new method, trap and null back into these
files, so the next league starts from more than this one did.

---

## What success is

In order of priority:

1. **Units won at prices we could actually have bet.** The published stake
   (1 unit to win, risk capped at 3) at the price the pick would have been
   decided at, against the no-vig market on the same games. Closing-line value
   is the second witness. AUC, log loss and calibration are diagnostics only.
2. **Every market the books offer gets a verdict.** Live, null (with the
   table), or parked (with the reason, in the grid). Nothing is out of scope by
   silence. A short list of markets we can beat is worth more than coverage we
   cannot, but no market is skipped unexamined, and none is narrowed or left
   out to save credits (`~/.claude/CLAUDE.md` §5).
3. **What passes the backtest goes live now.** The backtest is the gate. No
   paper version, no "once it reaches N bets", no "next season". Live data is
   for improving a model, never for deciding whether it may start.
4. **The record stays honest.** A pick is a pick (CLAUDE.md §1c): locked at
   first signal, never deleted or overwritten, graded at its own price.
5. **Volume a person can bet.** mike, 2026-11-10: *"maximize units but also
   not too much crazy volume."* A cut that doubles the bets for a sliver more
   units is a worse model; report units and bets together, always.

**A league is done when** every grid row has a verdict backed by a results
table; every model that cleared is live with its own cut, EV floor and price
floor; its first decision has been watched on the worker and its first bet on
every surface (app, Discord, push); the nulls are written down so they are
never re-run; and the live record is being graded on the whole scored
universe. Then it moves to step 8, which never ends.

---

## Rules that bind every step

These are standing instructions. Each one was broken at least once before it
was written down. Do not relitigate them; the evidence is in
`docs/rules_evidence.md` and the memory files named in `references/`.

- **No guessing (CLAUDE.md §00).** Every number in the grid and in a reply
  names the script or query that produced it. "Not measured, here is the
  query" is a complete cell.
- **Results in units, never dollars.** Bets, units, return with an interval,
  CLV.
- **Everything bought or built goes into Supabase first**, keyed on a
  `source` marker so a re-run imports nothing twice, and is mirrored to mike's
  PC. A local file is a cache of Supabase or it is a bug.
- **Credits:** check the live balance (`odds_api_quota`, or the
  `x-requests-remaining` header) before quoting it. Ask before a meaningful
  purchase, with the measured number, unless mike has pre-approved buys for
  this build. Never propose buying less to save credits. Measure the cost of
  one call (`x-requests-last`) before quoting a collection cost: history bills
  about 10× live.
- **Every model carries its own cut, its own EV floor and its own price
  floor**, swept on its own record. A cut is never copied from another model.
- **State the price range before a model ships**: median, shortest, the share
  shorter than -300 and -500, and what the stake becomes there. A floor set
  wide open on purpose is a decision for mike, in plain words.
- **Every model update carries `Updated-By:`** (a new model, a retrain, a cut,
  a pause, a feature change). If it is not clear whose call it is, ask.
- **A losing model is an assessment, never a pause question.** Nothing
  autopauses. "No cut clears, here is the grid and what would have to change"
  is a complete answer.
- **No hold, gate or early-season rule without grading that window first** on
  every stored season. Most proposed holds here were wrong when measured.
- **One league asked, one league in the reply.** Describe a method by what it
  does ("a line-shopping rule", "a halftime state model"), never by the sport
  it was first built for. Provenance stays in the repo docs.
- **Heavy research reads come off the local mirror**, never production
  (`docs/local_ops.md`). Production has one database for analysis and live
  scoring.
- **Subagents get the same rules.** Tell every subagent in writing: no paid
  API call, no production write, run `graphify query` before grepping code.

---

## The steps

### 0. Orient — timeboxed, and it produces facts, not prose

- Read the rules from `git show origin/master:CLAUDE.md` if the checkout is
  behind; a stale branch has hidden newer standing rules three times.
- Read the league's own doc if it exists (`docs/sports/<league>.md`) and any
  build-state memory. In an audit, read what every live and paused model in the
  league actually did: settled bets, units, the cut in force, and why the
  quiet ones are quiet (the reasons column on non-bet rows).
- Inventory what is stored, by query: games and scores (and how far ahead the
  schedule is stored), period scores, box scores, play-by-play, player logs,
  odds rows by season, book and market, pulls a day. Do not report "we have no
  X" until the source has been asked what it offers (CLAUDE.md §1b).

### 1. The market grid — before any model

One row per market the books offer in this league. Template and market
families: `references/market-grid.md`. Every row fills these columns:

| Market | Settles on | Inputs held | Prices: source, books, seasons, pulls a day | Baseline | Method tried | Result | Status |

A row with an empty cell is a to-do. A row that cannot be worked yet is
**parked with its reason in the table** ("one book, a handful of games", "no
price source", "one-way market, cannot be de-vigged"). The grid lives in the
league doc (`docs/sports/<league>.md`, "The market grid") and is updated in
place as rows resolve.

### 2. Prices before models

No price, no profit claim. For every grid row, find prices in this order and
write what each route returned (routes in `references/market-grid.md`):
stored rows; what the odds feed sells for this sport key (the event list is
free; one historical call shows the depth and the cost); free archives (ESPN's
odds, closing lines in a stats API, exchange or prediction-market history);
the prior season's close. **A price source found here is an input to use
today, not a finding to report.** Buy history once approved, store it the same
run, mirror it, and verify both copies by row count.

Start the forward collection at the same time. A market with no history still
gets its prices stored from today, at the pull times the model would decide
at, so next season's research has data. Every model that will run in play
needs its own price log from its first day.

### 3. Settlement and inputs

For each target: the column that settles it, and a check that it reproduces
the books' grading (overtime in or out, regulation 3-way, periods, voids). For
inputs: what really drives this sport (scoring process, pace, lineups,
starters, rest and travel from the stored schedule, weather, injuries) and
which of those we hold. Run the leakage checks in `references/porting-traps.md`
before any feature reaches a model: as-of dates per season, constant values
per entity-season, snapshots bounded at `commence_time`, in-play rows
excluded, a missing feature never filled as 0.

### 4. Baselines

Run these first, on every market in the grid, before any model. They are the
floor any model must beat, and they often answer a row on their own:

- **The blind bets**: always home, away, favourite, underdog, over, under, each
  side of a spread, at the first and the last stored number, by price band.
- **Betting every quote both ways.** That loses the margin. A rule that only
  matches it has found nothing.
- **The market's own accuracy**: log loss of the open and the close on the
  target. A model whose log loss is worse than the open's has "edges" that are
  its own error.
- **State what the sample can resolve** (about 2,700 games resolves a return
  to roughly ±4 points).

Then every candidate is scored against the no-vig probability of the price it
would bet into, on the same games.

### 5. The method search, one market at a time

Start from `references/methods.md`. For each grid row, pick the methods whose
mechanism could apply, and run each as an experiment against prices: one
hypothesis, a decision time fixed before looking at results, a walk-forward fit
on every earlier season, graded at the quoted price of the book the live path
would use. Record every run in the league's results table, nulls included.

Each experiment reports the same columns, so tables can be compared: bets,
units, return, interval, CLV, beat-the-close share, early, late, by season.
Inputs are tested by **removing one group at a time** against a control row
that is the market's own number alone.

**The finding that has held in every league here:** models that predict the
game from statistics and compare with the line mostly add nothing over the
closing line. The edges that held came from market structure. Re-mining
features on the same data rarely helps; a new edge needs new information or a
new mechanism. So **ask why the book would be wrong here before writing a
model.** The methods that worked each had a mechanism:

- the book re-hangs a line mechanically (off its opener and the clock, off
  the full-game number for a derivative market) and misses something the
  state shows;
- the books disagree with each other, or with their own other markets, at a
  fixed time of day;
- a regressing quantity (shooting luck, finishing luck) is priced as if it
  persists;
- an input the market under-weights at the moment of decision (weather,
  confirmed starters, a schedule spot known weeks ahead).

A stat model with no such mechanism usually measures what the line already
knows (`references/kill-tests.md`, the information test).

**Player props** start with a decision, not code: one model across markets,
one per market, or a shared usage core feeding per-market heads, decided from
each market's response shape. Then: measure which side the margin sits on per
market, check the target counts what the book grades, run the information test
and a retail-book placebo (`references/methods.md` §6–8).

**In-play models** need their own price log and score feed from day one; only
fresh quotes (re-hung since the last score) count; the first qualifying quote
locks the pick, so replay the live loop's real fetch cadence; a between-period
break is often the best decision point; and the live cut is re-derived as the
markets and polling change (`references/methods.md` §3).

**Run the market-structure round on a market that stays null**: blind results
by line and price band at the first and last number, sharp against soft within
one snapshot, "other number" rules, and the hindsight ceiling. It says whether
the market has a cheap side at all, and after four rounds of fitted models
found nothing on hockey totals it produced the rule now live there (shipped on
mike's call; its interval still reaches below zero).

#### When the catalog runs out — invent

The methods file holds what has been tried. It is not the list of what is
possible. When no catalogued method fits a market, or all of them fail, design
a new one:

1. **Name the mechanism**: who sets this line, what it anchors to, what it
   updates mechanically, what it cannot see, who bets it and how.
2. **Write the falsifiable prediction**: "the book's live total falls too
   slowly after a scoreless first period", not "pace matters".
3. **Find the cheapest experiment** that could kill it on stored prices.
4. **Run the kill tests** on whatever survives.
5. **Write it into `references/methods.md`** with its result, whatever it is.
   A null that is written down is never paid for twice.

Sources of new ideas worth searching (WebSearch, papers, practitioners'
write-ups — orientation, timeboxed): how professionals price this sport, how
its markets are known to be set, which derivative markets are priced off
which. A league that fits no sport shape in the catalog is the case for
defining a new shape, and for adding it to `references/market-grid.md`.

**Run independent markets in parallel.** Each grid row is its own experiment.
When there are many, give each to a subagent with its grid row, the kill
tests, the decision time and the rules above in writing, and merge the tables.

### 6. The kill tests

Every result that looks positive goes through `references/kill-tests.md`
before it is called an edge: the walk-forward by season, the early/late split,
a plateau not a peak, the side split, the placebo reference, seed stability,
a fit on every season available, the price range, fresh quotes only, and a
backtest that runs exactly what the live path would run. The bar a model must
clear to ship, in one place:

- positive in units at real prices, walk-forward, with an interval reported;
- a plateau: neighbouring cuts positive on both sides;
- positive in both halves of the time split, and across seasons (or the
  failing season explained by something measured, not by luck);
- not one side, one price band or a handful of dates carrying the total;
- the same result from the code the live path will run, at the decision time
  and books it will use.

"No version clears, here is the grid, here is what would have to change" is a
finished result. It goes in the grid and in the doc.

### 7. Ship — the passing model goes live now

Mechanics in `references/shipping.md`. In outline: config entries with the
model's own cut, EV floor and price floor; the scorer or in-play loop; the
pick writer through the shared lock and integrity checks; the artifact
committed and registered; thresholds synced; the app name and the Discord
route; tests that fail without the change; the league doc and the session log.
The commit carries `Updated-By:`. The branch waits for mike's "merge"; after
it, finish the production steps yourself (migrations through
`data.view_migrations`, `data.threshold_sync`, the artifact `--store`, a
health check), and watch the model's first decision on the worker and its
first bet reach every surface. Avoid merging over the 6am ET pipeline or a
model's only deciding run.

### 8. Live: improve, never re-gate

- Grade the live record on every scored pick (BET, AVOID and the dead zone),
  on the artifact that is actually live, in units, early/late.
- A live cut decays as polling and markets change; re-derive it.
- When the record or new data suggests a better version, it is a new
  experiment through steps 5–7, and it ships the same way.
- A losing model gets the full assessment (`docs/paused_model_assessment.md`,
  `scripts/paused_model_assessment.py`).
- Proactively check adjacent markets, lead times and execution details
  around a live model, and say what the next measured step would be.

### 9. Write it down, and teach this skill

- The league doc: the source inventory, the grid, each model's evidence, what
  a copy of existing code got wrong, open items.
- A study doc per large search (`docs/<league>_market_audit.md` is the shape),
  with each table naming the script that printed it.
- The session log (`docs/sessions/<YYYY-MM>.md` and its README row).
- **This skill's references**: a new method, a new kill test, a new trap or a
  new price route goes into the matching file under `references/`, with the
  league, the date and the doc that holds the evidence. If the framework
  itself was wrong somewhere, fix this file.

---

## The reply

CLAUDE.md §0 governs: the four headings, nothing above them, each fact once.
For this work, **"Quick summary of what was done" leads with the grid and the
results table** (bets, units, return with interval, CLV, early/late), then the
approach. Every model that is about to ship states its price range there.
Decisions are written so mike can answer without opening a file: what he gets
or loses, one idea per sentence, a recommendation.

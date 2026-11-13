---
name: league-models
description: "Build, audit or extend the betting models for EVERY market in one league — a league we have never bet, new markets in a league we already bet, or a full audit of one league's markets. Use when asked to build models for a league, add a league or sport, audit all of a league's markets, explain why nothing is firing in a league, find what else can be bet in a league, or port what was learned in one sport to another. It is the framework for that work — the market grid, prices before models, the market as the baseline, a method search per market, the kill tests, ship what passes live, keep improving on live data — for hunting outside the repo (papers, forums, open-source code, data and price sources), and for inventing new methods when nothing found clears."
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
| `references/scouting.md` | step 2b and the stuck ladder: hunting outside the repo for methods, data and prices, and judging what is found |
| `references/learning-log.md` | step 0 (read) and step 9 (append): what every use of this skill taught it |

**The catalog is a starting set, not a boundary.** Step 2b goes outside the
repo for what others have found, step 5 ends with inventing methods nobody
has tried, and step 9 writes every new method, trap, source and null back into
these files, so the next league starts from more than this one did.

---

## How this skill learns, corrects and evolves

It does not change by itself. It changes only when a session using it writes
back, and only once that write-back is merged. So the write-back is part of
the work, not a courtesy after it:

- **Learn, on every use, from inside and outside.** Step 0 reads
  `references/learning-log.md`. Step 2b brings in what others have published
  or built. Step 9 appends an entry (what was tried, what was new, what was
  searched and where, what was corrected, what in the framework changed) and
  writes each new method, trap, source, price route or kill test into its
  reference file. **A build is not done until those changes are
  in the same branch as the work**, and the reply carries one line: *"What this
  build taught the skill: …"*.
- **Correct, the moment a measurement contradicts it.** Fix the claim in place
  the same day — the new number, the date, the doc — and log "was X, now Y,
  because Z". A method listed as working that fails on re-measure moves to
  failed. A null is never deleted: it is what stops a rerun. Every claim that
  can change (a file path, a config name, a model's status, a number) is a
  memory, not a measurement: re-check it before relying on it.
  `tests/test_league_models_skill.py` corrects the skill when nobody is using
  it: it fails the suite when a file, module or setting the skill cites no
  longer exists, so whoever moved it updates the skill in the same change.
- **Evolve the framework itself.** A step that was wrong, missing or in the
  wrong order is changed here, with the reason in the log. A trap or failure
  that appears in two log entries is promoted to a rule in the step it belongs
  to. A league that fits no sport shape adds one to `references/market-grid.md`.
  Every fifth entry, read the whole log for patterns and revise this file.

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
   units is a worse model; report units and bets together, always. The cut is
   set for edge; volume after shipping is a per-night cap set from the record,
   or the volume dial (`set_model_volume`), never a moved cut.

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
`docs/rules_evidence.md` and the docs each reference file cites.

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
- **Bulk history reads come off the local mirror** (`docs/local_ops.md`):
  production is one database for analysis and live scoring. The mirror lags
  by up to a day, so today's rows are a small read on production by indexed
  key.
- **Subagents get the same rules.** Tell every subagent in writing: no paid
  API call, no production write, run `graphify query` before grepping code.

---

## The steps

### 0. Orient — timeboxed, and it produces facts, not prose

- Read `references/learning-log.md`: what earlier uses learned, what they
  corrected, and the open items they left.
- Run the skill's self-check, `python -m pytest -q
  tests/test_league_models_skill.py`. A failure means a file or setting this
  skill cites has moved: fixing the skill is the first correction of the build.
- Read the rules from `git show origin/master:CLAUDE.md` if the checkout is
  behind; a stale branch has hidden newer standing rules three times.
- Read the league's own doc if it exists (`docs/sports/<league>.md`) and any
  build-state memory. In an audit, read what every live and paused model in the
  league actually did: settled bets, units, the cut in force, and why the
  quiet ones are quiet (the reasons column on non-bet rows). Check that the
  graded-universe view holds the league's rows at all (it held none for one
  league, so its non-bets had to be graded from the local copy).
- Inventory what is stored, by query: games and scores (and how far ahead the
  schedule is stored), period scores, box scores, play-by-play, player logs,
  odds rows by season, book and market, pulls a day. Do not report "we have no
  X" until the source has been asked what it offers (CLAUDE.md §1b).

**A new league, in the order that has worked.** The last one went from the
brief to its first live model in a day (2026-11-09 to 11-10,
`docs/sports/ncaabw.md`):

1. Measure every source on the day: the feed's history start, books and
   markets for the sport key; the free score, box and play-by-play sources.
2. Write down what differs from the closest league we already bet (periods,
   overtime, ids, team names, books, markets).
3. Identity: a per-league team table and a feed-name census.
4. Buy and store the price history; start the forward collection the same day
   (the whole season's schedule, odds pulls at the decision times, the price
   path kept, box scores). **First merge the groundwork that protects the new
   sources from the odds clean-up** (`data/prune_odds.PROTECTED_SOURCES`
   lives in code, so until it merges, production thins what was bought), and
   put the measured cost of a large purchase to mike in chat (EuroLeague,
   2026-11-12, `references/learning-log.md`).
5. Scout outside the repo for this league (step 2b).
6. Run the closest league's working methods **unchanged** as the first
   candidates, then the scouted leads and the rest of the grid. Unchanged
   first, so a pass or a fail means something.
7. Ship what passes, through a card that replays the research bet for bet.
8. Then in play, then the app's stats pages.

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

### 2b. Scout outside the repo — every build, not only when stuck

Before the method search, go and find what others know about this league's
markets: papers, professional bettors' write-ups, forums, open-source models
and scrapers on GitHub, data and price sources we do not hold. Routes, search
terms, how to judge a lead and how to bring it back are in
`references/scouting.md`. The output is a leads table: each lead with its
source, its claim, its mechanism, what it needs, and the experiment that would
test it. Leads join the grid as experiments; data and prices found join step
2's routes. A claim found online is a hypothesis until it passes the kill
tests on our prices.

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

- the market's own number is the anchor, and the model may only move it;
- the books disagree with each other, with a sharp book, or with their own
  other markets, at a fixed moment (the first post is often the best one);
- the book re-hangs a line mechanically (off its opener and the clock, off
  the full-game number for a derivative market) and misses something the
  state shows;
- a regressing quantity (shooting luck, finishing luck) is priced as if it
  persists;
- an input the market under-weights at the moment of decision (a weather
  forecast, a confirmed starter, a schedule spot known weeks ahead);
- the margin sits on one side (count-prop overs), so a model that picks which
  unders has something to work with;
- the book settles a different number than our data counts.

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

**Before any market is called null, invent at least three mechanisms of your
own** — not from the catalog and not from the scout — each with its
falsifiable prediction and its cheapest experiment. Run the cheapest. The rest
go into the frontier list in `references/methods.md` with the experiment
written out, so the next session can run them without re-deriving them.

Sources of new ideas worth searching (WebSearch, papers, practitioners'
write-ups — orientation, timeboxed): how professionals price this sport, how
its markets are known to be set, which derivative markets are priced off
which. A league that fits no sport shape in the catalog is the case for
defining a new shape, and for adding it to `references/market-grid.md`.

**Run independent markets in parallel.** Each grid row is its own experiment.
When there are many, give each to a subagent with its grid row, the kill
tests, the decision time and the rules above in writing, and merge the tables.

#### When stuck — go outside the box before calling anything null

**You are stuck when any one of these is true:**

- two rounds on one market and nothing has survived the kill tests;
- every variant of a method fails the same way;
- a result does not fit what the mechanism predicts;
- a blocker: no data, no price, no access;
- you notice you are sweeping cuts or adding features on the same data.

**Then climb this ladder. Every rung is done before a market is called null.**

1. **Stop tuning.** Another cut, seed or feature on the same data is not a
   new idea. The searches here that kept re-mining the same data found
   nothing that held (`docs/sports/ncaaf.md`, "The model search is CLOSED").
2. **Back to the mechanism.** Write out who sets this line, from what, when it
   moves and what it cannot know. Ask what a professional bettor and a
   bookmaker in this sport each do.
3. **Change the information.** What does the book lack, or get late? A
   forecast, a lineup, tracking data, officials, travel, the timing of news.
   Look for sources outside the odds feed.
4. **Change the market or the moment.** An adjacent market, a derivative, an
   alternate line, the first post rather than the close, a break between
   periods, another book, a prediction market.
5. **Invert the question.** Which side does the book make its money on? Why
   do the losing bets lose? Why are the biggest claimed edges wrong? What would
   a perfect predictor of the line's move have earned?
6. **Look outside, deeper.** A second scout aimed at this one market
   (`references/scouting.md`): papers, practitioners' write-ups, forum
   threads, open-source code, and methods from other fields — stale quotes and
   lead-lag from market microstructure; ensembles, shrinkage and calibration
   from forecasting; the sport's own science. Timeboxed, and every idea comes
   back as an experiment, not a paragraph.
7. **Get a read that is not anchored on yours.** Give a fresh subagent the
   grid, the data and the question — not your hypothesis or your conclusions
   — and ask what is missing. Or call the advisor.
8. **Re-check the plumbing.** Is the target what the book grades? Is the
   grading right? Is the price one we could bet? Is the data what we think it
   is? Several findings here were reversed by data quality or sampling, not by
   modelling (`references/kill-tests.md`, "Is the data right?").

Only then: "no version clears; here is what was tried at each rung; here is
what would have to change". Every untried idea from the ladder goes into the
frontier list in `references/methods.md`, and the ladder's outcome goes in the
log. **Never hand being stuck back to mike as a question.** Ask him only for
what only he can do: a purchase with its measured cost, an account, a call
that is his to make.

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

A model mike asks for that misses the bar still ships live ("build it
anyway"). The reply and the doc then say plainly which part of the bar it
missed and by how much; it is never presented as a pass, and the gap is never
a reason to hold it back.

### 7. Ship — the passing model goes live now

Mechanics in `references/shipping.md`. In outline: decide whether it is a rule
card (a committed JSON artifact, the recent pattern), a trained model (a
committed and registered `.pkl`) or an in-play loop; config entries with the
model's own cut, EV floor and price floor; the writer through the shared gates
(the EV gate, the schedule gate, the lock, pick integrity, side conflicts,
quote bounds); the app name, CLV market and settlement entries; the Discord
route; tests that fail without the change; the league doc and the session log.

**The card replays the research bet for bet before it ships.** That replay is
what found every copy error in the last new league.

The commit carries `Updated-By:`. The reply that ships it states the price
range, the bar it cleared (or plainly that it did not), the expected volume,
and the go-live gate standing as a fact. The branch waits for mike's "merge";
after it, finish the production steps yourself (migrations through
`data.view_migrations`, `data.threshold_sync`, a trained artifact's `--store`
and a health check), and watch the model's first decision on the worker and
its first bet reach every surface. Avoid merging over the 6am ET pipeline, a
live slate, or a card's only deciding run.

### 8. Live: improve, never re-gate

- Grade the live record on every scored pick (BET, AVOID and the dead zone),
  on the artifact that is actually live, in units, early/late. Report the
  go-live gate standing (≥ 50 settled, positive flat-bet return, calibration
  error ≤ 5%) as a fact; it is a report, never a hold.
- A live cut decays as polling and markets change; re-derive it.
- When the record or new data suggests a better version, it is a new
  experiment through steps 5–7, and it ships the same way.
- A losing model gets the full assessment (`docs/paused_model_assessment.md`,
  `scripts/paused_model_assessment.py`).
- Proactively check adjacent markets, lead times and execution details
  around a live model, and say what the next measured step would be.
- Re-scout (step 2b) at the start of each season, and whenever a live model's
  record decays: new data sources, new books, new published methods.

### 9. Write it down, and teach this skill — the build is not done without it

- The league doc: the source inventory, the grid, each model's evidence, what
  a copy of existing code got wrong, open items.
- A study doc per large search (`docs/<league>_market_audit.md` is the shape),
  with each table naming the script that printed it.
- The session log (`docs/sessions/<YYYY-MM>.md` and its README row).
- **This skill**, in the same branch: an entry in
  `references/learning-log.md`; each new method, kill test, trap or price
  route in its reference file, with the league, the date and the doc that
  holds the evidence; each contradicted claim corrected in place; and any
  change to the steps here. "How this skill learns" above says how.

---

## The reply

CLAUDE.md §0 governs: the four headings, nothing above them, each fact once.
For this work, **"Quick summary of what was done" leads with the grid and the
results table** (bets, units, return with interval, CLV, early/late), then the
approach. Every model that is about to ship states its price range there. It
ends with the line *"What this build taught the skill: …"*, naming what was
added or corrected. Decisions are written so mike can answer without opening a
file: what he gets or loses, one idea per sentence, a recommendation.

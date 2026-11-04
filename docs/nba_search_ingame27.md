# NBA search: the in-play game-state model on 2026-27's live prices, and a late-game leader cell (pre-registered 2026-11-03, before any cell was graded)

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find
it"*.

**Why this search.** No pre-game full-game spread or moneyline cell has passed in any search
(`docs/nba_models_2026.md`, section 13). The one spread or moneyline family that ever passed is
in-play: the third search's game-state model, IG-2 (record 7.3), passed the house standard in 6 of
its 18 cells (spread in quarters 1-2 and in quarter 3, moneyline in quarter 3). Every warning sign
of stale quotes was written down before that grade, and every one was present:

- about half of each passing cell's units came from outlier prices (a book more than 20 cents
  better than the next, or a number no other book hung);
- DraftKings alone lost in 2025-26 in all six cells;
- whether a price could actually be bet could not be measured, because the history was bought one
  hour at a time.

It was never built, because no NBA in-play loop exists.

**What has changed since.** The worker has stored live in-play prices since 2026-27 began: about
10-17 spread quotes per book per game, about 10 minutes apart. Those are prices a loop running
today would have seen, at a spacing where "was it still there at the next look" can be measured.
Nobody has graded IG-2 on them.

**This search has two steps.**

1. **No new choices.** IG-2's 18 registered cells, unchanged, on 2026-27's live in-play prices.
2. **One new cell, written here before any number about it:** the leader's live moneyline in the
   last six minutes of the fourth quarter, a phase IG-2 never had. Graded first on the held
   2020-21 to 2025-26 in-play quotes (the third search's data), then on 2026-27.

**Written before any cell was graded. Nothing below changes after a result is seen; a later change
gets its own dated line and reason.** Lab: `scripts/nba_s_ingame27.py`. Pass/fail: `python -m
scripts.nba_game2_verdict --results <folder> --house5` (record 9.1's bars). Nothing is bought. No
Odds API call is made. This document does not edit `docs/nba_models_2026.md`.

---

## 1. Data

### 1.1 2026-27: the live in-play prices

- **Where they are.** Table `odds`, full-game markets `h2h` and `spreads`, written by the worker's
  live fetches. On these rows `source` is empty and `snapshot_type` is `open`, the same label a
  pre-game row carries. So the label says nothing; a row is in play only by the clocks in
  section 2.
- **One fetch is one `created_at`.** The worker writes every book of every game in one fetch with
  one `created_at` (checked on a 2026-11-02 game: one value across ten books). The ingestor appends
  a row for every book and market it is served, every fetch, with no de-duplication
  (`data/ingestors/odds_ingestor._insert_odds`). So a book that has not changed its price shows the
  same stamp again in the next fetch.
- **What is read.** For every 2026-27 regular-season game with a final score in `games` when the
  pull runs, and a play-by-play in `nba_pbp`:
  - every `h2h` and `spreads` row stamped later than 90 minutes before the listed tip (the held
    table's own pre-filter), every book;
  - Pinnacle's `h2h` and `spreads` rows stamped in the 36 hours before the listed tip, for its
    pre-game close (the model's prior);
  - the game's `nba_pbp` plays and `nba_pbp_box` rows;
  - the whole 2026-27 schedule from `games` (dates and ids only), for section 7.3's projection.
- **How it is read.** Once, read-only, by game id in chunks of at most 60 with a pause between
  them, after checking `pg_stat_activity`, never between 10:00 and 10:45 UTC. Written to the
  scratch folder only (`%TEMP%/nba_s/ingame27/`). Every row read is already in Supabase, so the
  local copy is a cache of it (CLAUDE.md section 1b).

### 1.2 2020-21 to 2025-26: the held in-play quotes

- `%TEMP%/nba_game_edge/ingame/quotes_state.parquet`, built by `scripts/nba_ingame_data.py`
  (record 7.1): 374,827 in-play quotes on 2020-21 to 2025-26 joined to the game state at each
  quote's stamp. IG-2's graded run read exactly this file. Read-only; nothing is rebuilt into that
  folder.
- IG-2's own training states and pre-game prior beside it (`ig2_train_states.parquet` for 2020-21
  to 2024-25, `ig2_train_states_2026.parquet` for 2025-26, `ig2_prior.parquet`) are read, never
  rewritten. The lab never calls IG-2's `training_states` or `pregame_prior` with a refresh, both
  of which write to that folder.

### 1.3 Play-by-play and starters

- **Held seasons:** the ESPN release files the `nba_pbp` ingestor downloaded
  (`%TEMP%/nba_free_data/sportsdataverse_espn/`), through `scripts/nba_ingame_data.season_plays`,
  as IG-2 used them.
- **2026-27:** the `nba_pbp` rows themselves. They were written by the same code
  (`data/ingestors/nba_pbp.slim_plays`), so their team sides are already our home and away and
  `scripts/nba_ingame_data.plays_frame` reads them directly. Starters and minutes come from
  `nba_pbp_box` (`espn_id`, `side` H or A, `starter`, `minutes`).
- **Top players** (IG-2's foul inputs) are each side's three starters with the most minutes per
  game in their earlier games this season, from `nba_pbp_box` for 2026-27; else last season's
  average from the 2025-26 box file (matched on the ESPN athlete id); else 0. That is
  `nba_ingame_data.prior_minutes` with 2026-27's box rows in place of the release file.

### 1.4 Results

The final score in `games`, overtime counted, as every earlier full-game market. A live spread and
a live moneyline settle on the full-game score.

---

## 2. Definitions for the 2026-27 rows

Everything not named here is record 7.1's definition in `scripts/nba_ingame_data.py`, unchanged.

| | Held quotes (record 7.1) | 2026-27 live rows (this search) | Why the difference |
|---|---|---|---|
| Stamp | `snapshot_at`, the book's last update | the same | |
| Fetch | the purchase ledger's requested instant | `created_at` | live rows have no ledger; one `created_at` per fetch |
| Served | the fetch minus the feed's 5-minute grid offset, never before the fetch's newest stamp | `created_at`, never before the fetch's newest stamp | the live endpoint serves at request time, so there is no grid offset. Stamps run up to a few seconds past `created_at` (clock skew, seen on 2026-11-02), so "never before the newest stamp" keeps the points-since-stamp count from reading time backwards |
| In play | stamp at or after the first play (ESPN wallclock) and before the end of the final period | the same, **and** stamp after the listed tip | the second clause is the task's bound on these `open`-labelled rows; the lab counts any row it changes |
| Same stamp in a later fetch | dropped, the first kept | the same, for the decision and the Pinnacle pairing | IG-2 unchanged |
| Still offered at the next fetch | not measured (the next purchase is an hour later) | measured, on the rows **before** that drop | see below |

**Still offered at the next fetch** (2026-27 only, reported, never a bar). The bet's book, in the
next fetch that holds any row for that game, quotes the same market at the same number (spreads)
with a price on the bet's side at least as good. A book that has not moved shows the same stamp
again, and that counts as still offered. Read on the undeduplicated rows, because dropping repeats
first would read every unchanged price as gone. A second column gives the share at the identical
price.

**The freshness rule (record 7.1), unchanged.** A deciding quote is used only when no point was
scored between its stamp and the moment its fetch was served, the same holds for its Pinnacle
quote, and Pinnacle quoted the same game and market in the same fetch within 60 seconds, with a
coherent two-way price.

---

## 3. Impossible numbers (written before the first count of this search was taken)

Applied to every quote either step reads, held and live alike. Each is a number no book could hang,
not a judgement on a price.

1. **A price between -100 and +100**, or a price that is not a number, is not an American price.
   The quote is dropped.
2. **A two-way quote whose implied chances sum outside 1.00-1.15** is out (the harness's
   `coherent` rule, unchanged).
3. **A deciding spread more than 6 points from its paired Pinnacle number is dropped.** The
   freshness rule already puts the two quotes at the same score: no point was scored after either
   stamp, and the stamps are within 60 seconds. At one score, an honest disagreement of 6 points is
   not a live market; it is a swapped sign or a bad row. A swapped -4 against +4 is 8 points.
4. **A deciding moneyline whose no-vig home chance is more than 0.25 from its paired Pinnacle
   no-vig is dropped**, for the same reason. The cap is set wide on purpose: late in a game a
   minute of clock moves a leader's chance a long way, and the two stamps can be up to 60 seconds
   apart.
5. **Very short prices are not impossible.** A late-game -50,000 (FanDuel, 2026-11-02) is a real
   price. Nothing caps a moneyline's size; the -200 floor (section 6) is what keeps such prices out
   of a bet.

`--smoke` prints the extremes of every line and price read, by season, the highest-EV offers, every
row rules 1, 3 and 4 drop, and the gap to Pinnacle's paired number for every deciding quote.

---

## 4. Step 1: IG-2's 18 cells on 2026-27, unchanged

**Unchanged from IG-2** (record 7.3, `scripts/nba_ingame_ig2.py`, whose functions the lab calls):

- the eligible quote (section 2's freshness rule), the 8 deciding books
  (`config.BEST_LINE_BOOKMAKERS`; Pinnacle and Bovada never decide);
- the three phases: quarters 1-2 (live, or the break after the first quarter), quarter 3 (live, or
  the break after it), quarter 4 with 6:00 or more on the clock. Halftime is not a phase;
- the decision: per game, market and phase, the **first** fetch in the phase holding an eligible
  deciding quote; every eligible deciding quote in that fetch is an offer; a later fetch in the
  phase is never used;
- the model: IG-2's game-state model (margin, time left, Pinnacle's pre-game close spread as the
  prior with Stern's variance, team fouls, the top players' fouls), its form and inputs unchanged;
- the side: the side the model favours, the one whose best deciding offer has the higher EV;
- the cuts: EV >= 0.02 / 0.05 / 0.08;
- the market's fair price for the blind bets: Pinnacle's live no-vig at the paired quote.

**The cells: 2 markets (moneyline, spread) x 3 phases x 3 EV cuts = 18.**

**What differs, each forced by the data or by the bars, none chosen for a result:**

1. **The model for 2026-27 is fit on 2020-21 to 2025-26.** IG-2 is walk-forward: season S is
   predicted by a model fit on the seasons before it. Its graded run stopped at 2025-26, so 2025-26
   now joins the training rows (the stored 2025-26 states, built by IG-2's own code).
2. **The pre-game prior for 2026-27** is Pinnacle's last pre-tip coherent spread from the live
   rows, solved through the harness's empirical distribution fit on 2020-21 to 2025-26 closes
   (`H.close_dist`). A game without one is left out, as in IG-2.
3. **Fetch and served time** come from `created_at` (section 2).
4. **Section 3's impossible numbers** apply. IG-2 had no such rule; the lab counts every decision it
   changes.
5. **200 placebo runs, seeds 1 to 200**, and bands in place of nested neighbours: record 9.1's bars,
   which this search is judged by. IG-2 ran 20 placebo runs and the earlier house standard.
6. **Still offered at the next fetch** is measured (section 2). IG-2 could not measure it.

**Not re-run: IG-2's information test.** Its gate passed in both markets on 2021-22 to 2025-26
(record 7.3). Re-running it on 2026-27 would read the 2026-27 results of the very games the cells
bet, which this pre-registration does not allow before the grade.

---

## 5. Step 2: the leader's live moneyline in the last six minutes

**Why this cell.** IG-2's fourth-quarter phase stopped at 6:00 left, so the last six minutes were
never graded. The hypothesis, untested here before: late in a game, a team ahead by a few
possessions may be priced as if the trailing team's fouling and threes make a comeback likelier
than it is. IG-2's model carries the inputs that matter there: time left, margin, and who is in
the penalty. The cell asks one narrow question: is the leader's live moneyline underpriced against
the game-state model, at a price the -200 floor allows?

**The cell, every choice with its reason:**

- **Window.** Period 4, live (not a break), with 0 < clock <= 6:00. Overtime is out: it is a
  different game state, and IG-2's phases never included it. A state at exactly 6:00 sits in IG-2's
  quarter-4 phase and in this window; they are different families, and neither is pooled with the
  other.
- **Lead.** The leader is ahead by 4 to 16 points, both ends included, read from the score at the
  quote's own stamp. Under 4 is one possession, where "the leader" is close to a coin flip, not a
  leader. Over 16 with six minutes left, the leader is expected to be priced far shorter than
  -200, where the floor removes it anyway. Under the freshness rule, every eligible quote in one fetch sees the same score
  (no point was scored after any of their stamps), so the leader is one team per decision.
- **Side.** The leader, always (a per-game side, `side_pick`). The trailing team is never bet. The
  home and away split is reported beside.
- **Decision.** Per game, the **first** fetch holding an eligible deciding moneyline quote whose
  state is inside the window and the lead range. Every such quote in that fetch is an offer. A later
  fetch is never used, as in IG-2. The window and the lead together are the population, so the
  decision is the first moment the game is in it.
- **Freshness.** Section 2's rule, unchanged.
- **The model.** IG-2's model form and inputs, **refit on states from the last six minutes**: each
  game's state every 30 seconds of game time with 6:00 or less left in regulation, built by IG-2's
  own grid function from the play-by-play, walk-forward (season S fit on the seasons before it;
  2020-21 fit on itself, reported only). Why refit: IG-2's model was fit on states with 6:00 to
  47:30 left. Its variance is a straight line in time left fitted on that range, and stretching it
  below 6:00 is a guess, not a fit. The refit's states are written to the scratch folder only.
- **Fair chance.** The refit model's home win chance at each quote's own state (the leader's chance
  is that or one minus it). A moneyline has no push.
- **Cuts.** EV >= 0.02 / 0.05 / 0.08, IG-2's cut axis, so the bands match.
- **Price.** The best deciding price, -200 floor, as every cell.
- **No 10-game wait.** IG-2 had none: its prior is Pinnacle's pre-game spread, which carries no
  early-season gap.

**The cells: 3 EV cuts, each graded twice:** on the held 2020-21 to 2025-26 quotes (choosing seasons
2021-22 to 2024-25, confirming 2025-26, 2020-21 reported only), and on 2026-27 alone. Six rows; the
held three are judged first.

**Expected to be thin, said now, not yet measured.** A leader by 4 or more with six minutes or less
to play is expected to be priced shorter than -200 in most games, so the floor may remove most
decisions. The held quotes were bought one hour at a time, about two in-play purchases per game
(record 7), so few games may have a fresh quote inside the last six minutes. `--smoke` counts the
decisions, the leader's price at each, and how many the floor removes, before anything is graded.

---

## 6. Grading rules, every cell

Record 6.2 and 7.1, in the shared harness (`scripts/nba_game_harness.py`, `H.run_cells`):

- **Price.** Best deciding price among the 8 books, coherent two-way quote, -200 floor
  (`config.DEFAULT_MIN_ODDS`). DraftKings alone is graded beside every cell.
- **Units.** One unit to win, risk capped at 3 (`H.risk_win`). A push returns the stake: 0 units,
  and its risk leaves the denominator. Results are in units, never dollars.
- **Spreads.** The stored number is the home number: home covers when (home - away) + number > 0.
- **Seasons.** Held quotes (step 2's first grade): pooled 2021-22 to 2025-26, choosing seasons
  2021-22 to 2024-25, 2020-21 reported only (its model is fit on itself). 2026-27 (step 1, and
  step 2's second grade): 2026-27 alone. In the harness's columns, 2026-27's numbers fill the
  "choose" and "pool" columns (`choose_seasons=(2027,)`); no other season's bet is in those cells.

---

## 7. The bars, and how a thin or one-season cell reads

### 7.1 The bars

Record 9.1, through `scripts/nba_game2_verdict.py --house5`, unchanged:

1. pooled, at least 200 bets;
2. the pooled whole-day bootstrap 95% interval of the return above zero (4,000 resamples, seed 7);
3. at least two graded seasons with 30 or more bets, all but at most one of them positive;
4. beats the blind bet on its dominant real side, pooled;
5. bands, not nested cuts: the band just below the cell's cut and every band from its cut to the top
   positive, pooled (a band under 30 bets is reported, not judged), and the cell's own return
   positive. The bands lie between the EV cuts; the lowest cut's lower band starts at EV 0; the top
   band is open;
6. placebo: the return on the choosing seasons above the 95th percentile of 200 shuffles.

Closing-line value is not computed (an in-play bet has no close). Expected passes by chance: 24
cells x 0.025 = 0.6 clear bar 2 alone, before correlation.

### 7.2 One season cannot pass bar 3

Bar 3 needs two seasons with 30 or more bets. 2026-27 is one season, so **no 2026-27 cell can pass
record 9.1 this season, whatever it shows.** Said now, so the verdict is not read as a finding.
What 2026-27 can show this season is bars 1, 2, 4, 5 and 6 on prices a live loop would have seen,
and the beside-numbers of section 9. A 2026-27 cell is never pooled with the held seasons: those
were bought an hour apart and graded already, and pooling would let the known seasons carry the
fresh one.

### 7.3 "Too few games to tell"

A cell under 200 bets is reported in full and labelled **too few games to tell**. With about two and
a half weeks of 2026-27 played, that is expected for every 2026-27 cell. For each one the lab prints:

- the bets it would place so far (counted from prices, before any grade);
- the games it has seen, and its bets per game;
- the date the 2026-27 schedule reaches 200 bets at that rate (counting the scheduled games per date
  from `games`), or "not this season" when the rate does not get there by the last scheduled date.

---

## 8. The placebo, and the check that it is a null

- **What moves.** The model's disagreement with Pinnacle at the decision, read at Pinnacle's own
  state (logit points for the moneyline, margin points for the spread), is moved to another game on
  the same date and market, and added back to that game's own Pinnacle fair price (IG-2's placebo,
  `H.shuffle_within_date`). Prices, sides and results stay with their games. Step 2's side stays the
  leader.
- **Runs.** 200, seeds 1 to 200, built one frame at a time (`nba_game5.LazyFrames`).
- **The null check, on real prices, before any grade.** For each cell, the share of placebo bets
  that land on a game the cell itself does not bet, over 20 seeds. A share near zero means the
  shuffle repeats the real bets and is no null. A date with a single decision cannot be shuffled
  (it keeps its own number); late-game decisions on the held quotes may be few per date, which is
  why the share is measured. If a cell with 30 or more real bets shows a share under 50%, that is
  written in section 11 before any grade; the shuffle is not changed after a count without a dated
  line here first.
- The correlation between each run's moved disagreement and the real one is printed beside it.

---

## 9. Reported beside every cell, never a bar

- **DraftKings alone**: the same cell with DraftKings the only book.
- **Still offered at the next fetch** (2026-27 only): the share of bets, and their units, with the
  price still there at the next fetch at least as good; and the share at the identical price.
  Not measured on the held quotes, and written as such.
- **Bets whose side had just outscored its opponent**: units, bets and return on bets whose side
  scored more than its opponent in the 120 seconds before the quote, and on the rest. This is the
  deciding books' own moneyline lag that the freshness rule does not remove (record 7.1).
- Units without outlier prices (a price more than 20 cents better than the next book's, or a number
  no other book hangs), the share of bets that are outliers.
- Prices: lowest, median, highest; bets and units by book; underdog bets and their units.

---

## 10. What the lab writes, and how it runs

- `--pull`: section 1.1's read, once, into the scratch folder. Run through
  `%TEMP%/q1trend/run_with_db.py`, which supplies only `DATABASE_URL`.
- `--smoke`: synthetic checks (each rule watched failing), then counts on the real data: no result
  of any bet. Every grade inside it reads scores replaced by random numbers, and a guard stops the
  run if a grade is handed real scores. It prints the data found, the extremes, the dropped rows,
  the counts by cell and season, the placebo's differing share, and the time of one placebo run with
  the projected `--full` time.
- `--full`: refuses unless `NBA_GAME2_GO=1`, `NBA_GAME2_RESULTS` and `NBA_GAME2_BETS` are set.
  Writes `cells_S1.parquet` (18 rows), `cells_S2held.parquet` (3) and `cells_S2live.parquet` (3) to
  the results folder, each cell's bets to the bets folder, and the beside-numbers to
  `beside.json`.
- Families in the cell tables: `S1_IG2_live27` (points `Q1-Q2`, `Q3`, `Q4`), `S2_lead_held` and
  `S2_lead_live27` (point `Q4-last6`).

```
PYTHONPATH=. python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_ingame27 --pull
NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_ingame27 --smoke
NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets NBA_RESEARCH_CACHE=<cache> \
    PYTHONPATH=. python -m scripts.nba_s_ingame27 --full
PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5
```

---

## 11. Counts before grading

Added after `--smoke` ran on the real data, before any cell was graded.

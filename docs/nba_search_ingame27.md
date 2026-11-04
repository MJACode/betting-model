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

### 3.1 Changes after the data was first read, before any cell was graded (2026-11-03)

The first `--smoke` attempt stopped before any count was printed. Reading the 2026-27 rows and the
machine's files found three things. No cell had been graded and no bet counted when these were
written.

1. **Rule 5: a game whose ESPN clock starts before its listed tip is left out whole.**
   - Two 2026-11-01 games, `NBA_2026-11-01_BOS_ORL` and `NBA_2026-11-01_BKN_IND`, have their
     first ESPN play 60 minutes before the listed tip. That was the night the US clocks went back.
   - The prices say the listed tip is right and ESPN's clock is an hour early. In BOS_ORL, ESPN
     has Orlando 10 points up at 21:01 UTC, yet Pinnacle's moneyline sat at its pre-game level
     (+244 / -282 at 20:17, +243 / -289 at 21:17) and first moved at 22:17 (+809).
   - Joined as they are, those plays would give a quote the score from up to an hour after it.
     So a game whose first play is more than 15 minutes before its listed tip is dropped.
   - In 2026-27 the listed tip sits close to the first play: the other 105 games start between
     4.4 minutes before and 1.2 minutes after it. In the held quotes no game is affected: every first play is at least 0.2 minutes
     after the listed tip. The lab stops if one ever is.
2. **Step 2's training states come from `nba_pbp`, not the ESPN release files.** The release
   folders on this machine are empty (`%TEMP%/nba_free_data/sportsdataverse_espn/pbp_2025` and
   the rest, emptied 2026-10-26). `nba_pbp` and `nba_pbp_box` hold the same rows: the ingestor
   wrote them from those files. So:
   - the held seasons' plays (2020-21 to 2025-26, regular season) and box rows (2019-20 to
     2025-26) are read once, read-only, into the scratch folder (`--pull-held`), by indexed key
     in chunks of 60 games with a pause;
   - top players' prior minutes come from `nba_pbp_box` for every season, so 2026-27's
     "last season" fallback reads the 2025-26 box rows from that pull (section 1.3 named the
     release file);
   - as a check, IG-2's own window (6:00 to 47:30 left) is rebuilt the same way for 2024-25 and
     compared with IG-2's stored states. Section 11 reports how many states match.
3. **`nba_pbp` is read by `espn_game_id`.** Its only index is (`espn_game_id`, `play_no`). The
   first 2026-27 pull filtered it by `game_id`, which read the whole table twice. The rows it
   returned are the same; every later read goes through the index.

### 3.2 Changes after an independent review, before any cell was graded (2026-11-04)

An independent review of this search and its lab came back on 2026-11-04. **No cell had been
graded and no result of any bet had been read when these changes were made.** The owner's
decisions:
- run the grade after these fixes;
- leave step 2 as registered, read as too few games to tell.

Every number below comes from prices, clocks and counts. The log is
`%TEMP%/nba_s/ingame27/smoke4.txt`; each fix's own effect is in `probe_fixes.txt` beside it.

1. **The game state at a quote is now the last play in play order (this one changes results).**
   - Record 7.1 defines the state at a stamp as everything logged at or before it, ties broken
     by play order. The shared join, `scripts/nba_ingame_data.state_at`, drops the play number
     and re-sorts by wallclock alone with an unstable sort. So among plays logged in the same
     second it can take one that is not the last.
   - Example: `NBA_2026-10-20_BOS_DET`, DraftKings at 21:15:37 UTC. Plays 429 to 432 all carry
     21:14:48. The old join read the score as 103-99; the last of those plays gives 104-99.
   - The fix is this lab's own join (`state_at_stable`): it keeps the play number and sorts by
     (wallclock, play number), stable. The shared script is not edited, so the record's IG-2
     run stays reproducible.
   - **2026-27:** 416 of 26,076 in-play quotes now read a different score. The old join was low
     every time: by 1 point on 366, 2 on 29, 3 on 21. Points scored between stamp and serving
     changed on 295 quotes. Step 1 gains 1 decision (513 to 514), and the bets change in 15 of
     the 18 step-1 cells, by 1 or 2 bets each. Step 2 on 2026-27 does not change.
   - **Held quotes:** the lab now re-joins them too, from the `nba_pbp` pull of section 3.1.
     1,121 of 374,827 (0.30%) read a different score than the stored table. IG-2's graded run
     used that stored table; the reviewer's upper bound was about 0.29%. **So record 7.3 is no
     longer an exact comparator for step 1.** Step 2's held decisions (175) and bets (4 in the
     graded seasons) do not change.
   - IG-2's training states are not affected. They are built on game time, through no state
     join.
2. **Rules 3 and 4 are now counted in decisions, not only rows** (game × market × phase, with
   every fix in place):

   | | Decisions with the rules | Without | Decided only without | Decided at a different fetch |
   |---|---|---|---|---|
   | Step 1, 2026-27 | 507 | 510 | 3 | 5 |
   | Step 2, 2026-27 | 24 | 29 | 5 | 0 |
   | Step 2, held | 175 | 221 | 46 | 0 |

   Before the other fixes the reviewer measured 513 against 517 for step 1, 9 of them at a
   different fetch.
3. **Rule 6: a game with a clock jump of 45 minutes or more is left out whole.**
   - The jump is measured between consecutive plays in play order, in either direction. Rule 5
     looks only at the first play, in one direction.
   - The rule applies to the 2026-27 quotes, the held quotes and step 2's training states.
   - **2026-27**, each game the reviewer named, checked against the rule:
     - `NBA_2026-10-20_PHI_NYK`: dropped. +45.3 minutes, from the last play of the first half to
       the first play of the third quarter. That may be a real 45-minute halftime; the rule
       drops it either way.
     - `NBA_2026-10-23_MEM_GSW`: dropped. +138.3 then -134.4 minutes around the end of the first
       quarter, a stall and back-fill.
     - `NBA_2026-11-01_BKN_IND`: +62.0; already out under rule 5.
   - **Held moneyline table:** 12 games dropped. Most moved by about an hour; every number is
     minutes:
     - 2021-22: `CLE_DET` 2022-01-30 (+61.2), `UTA_BKN` 2022-03-21 (+61.1), `IND_TOR` 2022-03-26
       (+70.3);
     - 2022-23: `BOS_CLE` 2022-11-02 (+60.5), `NYK_PHI` 2022-11-04 (+240.2), `BOS_DAL` 2023-01-05
       (+61.0);
     - 2024-25: `WAS_MIL` 2024-12-21 (+65.0), `MIA_BKN` 2025-01-25 (+45.0, at halftime);
     - 2025-26: `NYK_SAC` 2026-01-14 (+300.4), and on 2026-03-08 `DAL_TOR` (-59.7), `DET_MIA` (-59.0)
       and `WAS_NOP` (-59.8).
     - The pull holds 46 jump games in all; the other 34 have no quote in the held moneyline table.
   - **Step 2's training states:** 12 games left out (0, 3, 3, 0, 2 and 4 from 2020-21 to
     2025-26).
   - **What it moved:**
     - Step 1 loses 7 decisions (514 to 507), and the bets change in 7 of the 18 step-1 cells
       (each moneyline cell in quarters 3 and 4, and the quarter-4 spread at 0.02), by 1 bet each.
     - Step 2 on 2026-27 loses 1 decision (25 to 24), and with it its only bet, PHI_NYK. It now
       has **0 bets**.
     - Step 2's held decisions do not change.
   - The next clock change, 2027-03-14, falls inside this season. Rules 5 and 6 are what catch a
     shifted clock.
4. **Reported beside every cell, never judged: the seconds from the last play ESPN logged to the
   decision quote's stamp** (median, 90th percentile, and how many are over 180 seconds).
   - Why: a quote priced during an ESPN logging stall passes the freshness rule against a frozen
     state.
   - The clear case is `NBA_2026-10-23_LAC_LAL`. ESPN logged nothing after 02:20:03 UTC, then wrote
     74 plays and 41 points of the first quarter (7:03 to 0:00) at 02:35:53-54. A quote stamped
     inside that gap sees the score from 02:20.
   - No exclusion rule now. On 2026-27, step 1's cells have medians of 11 to 61 seconds, 90th
     percentiles of 55 to 164, and 0 to 4 bets over 180 seconds per cell. Step 2 held: median 17,
     90th percentile 33, none over 180.
5. **Step 2's "units without outliers" now leaves out 2020-21, which is reported only.** The
   harness counted every season the cell bet. Every cell now reads the outlier share and the
   units without outliers on its own pooled seasons.
6. **Noted, nothing changed:**
   - The served time uses the newest stamp among the rows this search pulled from that fetch,
     not every row the fetch wrote. That moves a served time by seconds at most.
   - Step 2's training states never go below 30 seconds left (the 30-second grid's last point),
     so a decision with under 30 seconds left is priced outside the range the model was fit on.

**Counts after these fixes** (section 11 holds the counts before them; everything there not
listed here is unchanged). Step 1 bets on 2026-27, EV ≥ 0.02 / 0.05 / 0.08:

| Phase, market | Bets | Games decided | Reaches 200 bets |
|---|---|---|---|
| Quarters 1-2, moneyline | 46 / 18 / 10 | 99 | 2026-12-30 / 2027-04-11 / not this season |
| Quarters 1-2, spread | 57 / 36 / 14 | 100 | 2026-12-18 / 2027-01-16 / not this season |
| Quarter 3, moneyline | 32 / 29 / 28 | 86 | 2027-01-26 / 2027-02-04 / 2027-02-07 |
| Quarter 3, spread | 70 / 51 / 36 | 98 | 2026-12-01 / 2026-12-23 / 2027-01-16 |
| Quarter 4, moneyline | 23 / 18 / 17 | 52 | 2027-03-07 / 2027-04-11 / not this season |
| Quarter 4, spread | 55 / 42 / 31 | 72 | 2026-12-20 / 2027-01-05 / 2027-01-28 |

- **Step 2:** held, 175 decisions and 4 bets in the graded seasons (3 in 2020-21, reported only).
  2026-27: 24 decisions, every one with the leader priced shorter than -200, so 0 bets.
- **The placebo's differing share:** the same seven cells are under 50% as in section 11.4, now at
  19% to 48%.
- **Projected `--full`:** 14.4 minutes.

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

- `--pull`: section 1.1's read, once, into the scratch folder. `--pull-held`: section 3.1's read
  of the held seasons' play-by-play. Both run through `%TEMP%/q1trend/run_with_db.py`, which
  supplies only `DATABASE_URL`; `--full` refuses until both have run.
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
PYTHONPATH=. python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_ingame27 --pull-held
NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_ingame27 --smoke
NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets NBA_RESEARCH_CACHE=<cache> \
    PYTHONPATH=. python -m scripts.nba_s_ingame27 --full
PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5
```

---

## 11. Counts before grading

Added after `--smoke` ran on the real data, before any cell was graded (2026-11-04, 03:12 to 03:15
UTC, on the committed lab; log `%TEMP%/nba_s/ingame27/smoke3.txt`). **These counts predate the
review fixes of section 3.2, which lists every count they moved.** Every number below comes from prices, clocks and
counts. No result of any bet this search would place was computed or read: every grade inside
`--smoke` read random scores.

### 11.1 The 2026-27 in-play prices found

- **Games.** 107 regular-season games were final between 2026-10-20 and 2026-11-02, each with a
  play-by-play. Rule 5 left out 2, so 105 are used. All 43,001 rows read have an empty `source`
  and the label `open`.
- **In-play quotes** by the play-by-play clock: 26,076 after every rule. 62 rows were in play by
  the clock but stamped at or before the listed tip, and the tip bound dropped them. 496 rows
  repeat a stamp from an earlier fetch: dropped for the decision, kept for "still offered".
- **Quotes per book per game** (median, range): moneyline 11-13 (2-20), spread 14 (2-20);
  Pinnacle 11 moneyline and 12 spread.
- **Spacing.** Median 10.0 minutes between in-play fetches (10th percentile 6.2, 90th 10.1);
  16 in-play fetches per game at the median (3 to 21).
- **Quote age when served:** median 23 seconds, 90th percentile 70.
- **Freshness under record 7.1's rule.** Of 21,123 deciding-book quotes in play, 71.3% have a
  Pinnacle quote in the same fetch within 60 seconds, and 53.3% pass the whole rule.
- **Decisions** (game x market x phase): quarters 1-2, 101 moneyline and 102 spread; quarter 3,
  87 and 98; quarter 4 with 6:00 or more left, 53 and 72.
- **The model's prior** (Pinnacle's pre-game spread close) exists for all 107 games.

### 11.2 Bad rows

- **Rule 1** (a price between -100 and +100): 0 rows, in 2026-27 and in the held moneylines.
- **Rule 5** (an early ESPN clock): 2 games, section 3.1. None in the held quotes.
- **Rules 3 and 4** (a deciding quote far from its Pinnacle pair): 644 rows in 2026-27, 2,034 held
  moneyline rows. In the biggest gaps the deciding books agree with each other and Pinnacle is the
  odd one out, often with its two sides swapped. Example: `NBA_2026-10-20_BOS_DET`, quarter 4 with
  5:10 left, home up 8. Seven books hang the home side at -4.5 to -7.5 and Pinnacle at +8.0; on the
  moneyline Pinnacle gives home 0.16 against 0.73-0.86 at the others.
- **How often Pinnacle disagrees with the deciding books at the same score** (fresh, coherent
  in-play quotes, fetches with 4 or more fresh deciding books; before rules 3 and 4):

  | | Pinnacle more than 0.15 from the books' median (moneyline) | Pinnacle more than 3 points from it (spread) | Any other single book, the same tests |
  |---|---|---|---|
  | 2026-27 | 63 of 763 (8.3%) | 208 of 875 (23.8%) | at most 3 rows per book |
  | Held, 2020-21 to 2025-26 | 734 of 6,892 (10.7%) | 1,574 of 6,071 (25.9%) | at most 59, except Bovada (261, 470) and William Hill (194, 87) |

  So the price IG-2 is measured against, and that its blind bets and placebo are built on, is the
  least consistent quote in the fetch, in both data sets. IG-2 was graded on the same property.
- **Extremes kept** (2026-27 in play): moneyline prices -100,000 to +9,000; spreads -45.5 to +48.5
  (home number), spread prices -15,000 to +2,500. Held moneylines go as short as -10,000,000
  (2022-23 and 2023-24). None is impossible by the rules; the -200 floor keeps every one of them
  out of a bet.
- **The highest-EV offers include prices that look stale and pass every rule.**
  - FanDuel +1200 on the away side of `NBA_2026-10-31_MIN_SAS`, down 4 with 6:49 left; the model
    gives it 0.21, EV +1.68 (step 1, quarter 4).
  - DraftKings -164 on a 6-point leader with 9.6 seconds left (`NBA_2021-11-15_BOS_CLE`, step 2,
    held).
  - These are the prices section 9's "still offered" and "just outscored" numbers exist for.

### 11.3 Counts by cell and season

Bets each cell would place, from prices alone. "Reaches 200" counts the 2026-27 schedule after
2026-11-02 (1,096 games, last on 2027-04-11) at the cell's bets per final game so far (107 games,
the 2 left out by rule 5 included).

**Step 1, 2026-27 (all 18 cells are under 200 bets: too few games to tell):**

| Phase | Market | EV >= 0.02 | EV >= 0.05 | EV >= 0.08 | Games decided | Reaches 200 bets (0.02 / 0.05 / 0.08) |
|---|---|---|---|---|---|---|
| Quarters 1-2 | moneyline | 47 | 19 | 9 | 101 | 2026-12-29 / 2027-04-02 / not this season |
| Quarters 1-2 | spread | 56 | 35 | 14 | 102 | 2026-12-18 / 2027-01-18 / not this season |
| Quarter 3 | moneyline | 32 | 29 | 28 | 87 | 2027-01-26 / 2027-02-04 / 2027-02-07 |
| Quarter 3 | spread | 69 | 50 | 36 | 98 | 2026-12-01 / 2026-12-25 / 2027-01-16 |
| Quarter 4, 6:00+ | moneyline | 24 | 18 | 17 | 53 | 2027-03-02 / 2027-04-11 / not this season |
| Quarter 4, 6:00+ | spread | 56 | 41 | 30 | 72 | 2026-12-18 / 2027-01-06 / 2027-01-31 |

The six cells that passed in IG-2 are quarters 1-2 spread at 0.05 and 0.08, quarter 3 moneyline at
0.05 and 0.08, quarter 3 spread at 0.05 and 0.08. At the measured rates they reach 200 bets on
2027-01-18, never this season, 2027-02-04, 2027-02-07, 2026-12-25 and 2027-01-16. Bar 3 needs a
second season in any case (section 7.2), so 2027-28 is the earliest any of them can pass.

**Step 2, the leader's moneyline in the last six minutes:**

| | Decisions | Leader's best price shorter than -200 | Bets at every cut | Leader's best price, median |
|---|---|---|---|---|
| Held, by season 2020-21 .. 2025-26 | 22, 41, 21, 22, 28, 41 (175) | 19, 39, 21, 22, 26, 41 (168) | 3, 2, 0, 0, 2, 0 (2020-21 is reported only) | -1,430 |
| 2026-27 | 25 | 24 | 1 | -1,300 |

- The three cuts bet the same games: every decision priced -200 or better clears EV 0.08.
- On the graded held seasons the cell places **4 bets in five seasons**; 2026-27 has 1 in 107
  games. **Too few games to tell, and at the -200 floor it never will be:** at its rate the
  2026-27 cell does not reach 200 bets this season, and the held seasons hold 4.
- The floor is what removes them, as section 5 expected: 168 of 175 held decisions and 24 of 25
  in 2026-27 have the leader priced shorter than -200. Leads at the held decisions run 4 to 15
  points; the clock from 0:03 to 5:56 (median 2:11).

### 11.4 The placebo on real prices

Share of placebo bets (20 seeds) on a game the cell itself does not bet:

| Phase | Market | EV >= 0.02 | EV >= 0.05 | EV >= 0.08 |
|---|---|---|---|---|
| Quarters 1-2 | moneyline | 45% | 76% | 87% |
| Quarters 1-2 | spread | 38% | 58% | 81% |
| Quarter 3 | moneyline | 52% | 56% | 58% |
| Quarter 3 | spread | 25% | 40% | 54% |
| Quarter 4, 6:00+ | moneyline | 47% | 60% | 62% |
| Quarter 4, 6:00+ | spread | 18% | 34% | 47% |

- **Seven cells with 30 or more real bets are under 50%:** quarters 1-2 moneyline and spread at
  0.02; quarter 3 spread at 0.02 and 0.05; quarter 4 spread at all three cuts. Section 8 says this
  is written here; the shuffle is not changed.
- **Why, measured:** the shuffle does move the model's disagreement (its correlation with the
  real one is 0.06 to 0.28 across phases and markets). What stays is the placebo's base price,
  Pinnacle's live no-vig. Priced at Pinnacle alone, with no disagreement added, the best deciding
  offer clears EV 0.02 on 41 to 81 games per phase and market, and 60% to 77% of those bets fall on
  the spread cells' own games at 0.02 (74% in quarter 3, 77% in quarter 4). So in those cells the
  placebo mostly bets Pinnacle against the deciding books, the same stale-quote gap section 11.2
  measured, on the same games. Bar 6 then asks the cell to beat Pinnacle's own disagreement with
  the books. IG-2's placebo was built the same way.
- **Step 2's placebo is no null:** 145 of the 175 held decisions are alone on their date, so the
  shuffle cannot move them; every placebo bet in 20 runs falls on one of the cell's own 4 games.
  With 4 bets the cell is too few games to tell in any case.
- In 2026-27 no step-1 phase has more than 4 decisions alone on their date.

### 11.5 Still offered at the next fetch (step 1, 2026-27, prices only)

The share of each cell's bets whose book, at the next fetch about 10 minutes later, still hangs the
same number at a price at least as good:

- **Moneyline:** 47% / 63% / 78% (quarters 1-2, by cut), 44% / 48% / 46% (quarter 3), 38% / 33% /
  35% (quarter 4). At the identical price: 0% to 22%.
- **Spread:** 4% to 11% in quarters 1-2 and 3, 0% to 4% in quarter 4. A live spread moves its number
  with the score, so ten minutes later the same number is rarely there; this measures the number
  more than the staleness.

### 11.6 The late-window training states, and the check against IG-2

- 79,700 states with 6:00 or less left, 11,972 to 13,644 per season, 2020-21 to 2025-26; games
  whose play-by-play final differs from the official one are left out. Built in 187 seconds.
- **IG-2's own window rebuilt from `nba_pbp` for 2024-25 reproduces IG-2's stored states:**
  102,036 of 102,036 states match on game, time left and score. Every input matches on 100% of
  them except two foul inputs: who-is-in-foul-trouble on 99.99% and the top players' summed fouls
  on 99.79% (the top-three ranking reads minutes from `nba_pbp_box`, not the release file).

### 11.7 Time and memory for `--full`

- One placebo run: 0.742 seconds for one step-1 phase (6 cells), 0.491 seconds for step 2's held
  cells (3 cells).
- **Projected `--full`: 16.5 minutes** (step 1 7.7, step 2 held 1.7, step 2 2026-27 at most 6.1,
  loads 1.0), peak working set 3.2 GB. The late-window states are read from the scratch folder;
  rebuilding them adds about 3 minutes.
- **Measured on a dry `--full` with random scores** (every game's score replaced, the no-result
  guard on): 669 seconds end to end. It wrote all 24 cells with 200 placebo runs and band
  columns each, the 2026-27 cells carrying their bets in the pooled columns, and
  `nba_game2_verdict --house5` read the folder (24 cells, no error). Its picks differ slightly
  from 11.3 because its pre-game prior was built from random scores too (100 of 107 priors
  moved, by at most 0.39 points). The folder was deleted.

```
NBA_GAME2_GO=1 NBA_GAME2_RESULTS=C:/Users/micha/AppData/Local/Temp/nba_s/ingame27/results \
NBA_GAME2_BETS=C:/Users/micha/AppData/Local/Temp/nba_s/ingame27/results/bets \
NBA_RESEARCH_CACHE=C:/Users/micha/documents/bm-nba-q1trend/data/local/nba \
PYTHONPATH=. PYTHONIOENCODING=utf-8 python -W ignore -m scripts.nba_s_ingame27 --full
PYTHONPATH=. python -m scripts.nba_game2_verdict --results C:/Users/micha/AppData/Local/Temp/nba_s/ingame27/results --house5
```


## 12. Results (graded 2026-11-04)

Run `2026-11-04-ingame27`, stored in Supabase. 24 cells, graded after the review fixes of section 3.2. The grade took
558 seconds.

**0 of the 24 cells pass, and every cell is under 200 bets: too few games to tell.** No 2026-27 cell can pass this
season, whatever it shows (section 7.2).

| Step 1, 2026-27 | EV 0.02 | EV 0.05 | EV 0.08 |
|---|---|---|---|
| Quarters 1-2, moneyline | 46 bets, -16.4% | 18, -22.0% | 10, -43.6% |
| Quarters 1-2, spread | 57, -7.1% | 36, -5.7% | 14, -5.5% |
| Quarter 3, moneyline | 32, -24.3% | 29, -22.7% | 28, -16.3% |
| Quarter 3, spread | 70, +5.6% | 51, +12.0% | 36, +11.7% |
| Quarter 4, moneyline | 23, -28.1% | 18, -28.7% | 17, -28.4% |
| Quarter 4, spread | 55, +5.9% | 42, +21.1% | 31, +35.0% |

- **The spread cells in quarters 3 and 4 are positive and the moneyline cells lose.** Intervals on this few bets run
  from about -25% to +50%, so this is a reading, not a result. At this season's rate the quarter 3 and quarter 4 spread
  cells reach 200 bets between 2026-12-01 and 2027-01-31 (section 11), and the earliest any can pass bar 3 is 2027-28.
- **The late-game leader (step 2) is closed by the -200 floor:** 4 bets in five held seasons and 0 in 2026-27. Leaders
  are priced around -1,400 in the last six minutes.

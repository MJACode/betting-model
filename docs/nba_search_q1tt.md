# NBA search: first-quarter and first-half team totals (pre-registered 2026-11-03, before any cell was graded)

mike asked for a first-quarter model: *"whatever is missing, find it"*, then *"Buy 1Q data"*. The
first-quarter and first-half **team totals** were bought on 2026-11-03. No search has graded them,
because no search had their prices.

**What has already failed on these periods.** No first-quarter spread or total has passed in three
searches: the fifth (team period shares, `docs/nba_models_2026.md` §9), the eighth (mike's
cover-record method, §12) and the starters search (`docs/nba_search_starters.md`). Sections below
marked § are `docs/nba_models_2026.md`'s.

**The idea, in two families.**

- **A, the book's own numbers.** A book that hangs a first-quarter spread and a first-quarter total
  has already said how many points it expects each team to score in the quarter. Its team total for
  that quarter should say the same thing. Where the team total and the book's own spread and total
  disagree, one of them is mispriced. Family A prices every team-total offer at the number the
  spread and total imply, and bets the offers that clear an expected-value cut.
- **B, a live rule carried over.** The live home team-total model (`nba_team_total_luck`, the fourth
  search's cell C2, §8.4) bets the home team's full-game total under when the away defence has been
  lucky. Family B applies that exact rule, with no new choice, to the home team's first-half and
  first-quarter totals.

**Written before any cell was graded. Nothing below changes after a result is seen; a later change
gets its own dated line and reason.** Lab: `scripts/nba_s_q1tt.py`. Pass/fail:
`python -m scripts.nba_game2_verdict --results DIR --house5` (§9.1's bars), then
`python -m scripts.nba_s_q1tt --judge --results DIR` (this search's one stricter line, section 9).
No data is bought by the lab and nothing is written to the database.

**What was read before this was written.** The bought rows' lines, prices and timestamps; the
period spread and total purchases; the period scores of 2020-21 to 2023-24 (seasons this search
never grades), to measure the result shape in section 4.4. No win, loss or unit of any bet this
search would place was computed. No result of a 2024-25 or 2025-26 game was read.

## 1. What earlier searches did and did not cover

| Search | First-quarter and first-half markets it graded | Team totals it graded |
|---|---|---|
| First, §4.2 | spreads, totals, moneylines (its own bars) | full game only |
| Fourth, §8 | spreads, totals, moneylines (P1, P2, P3) | full game only: C2 passed and is live |
| Fifth, §9 | spreads, totals, moneylines from team period shares | none |
| Eighth, §12 | spreads and totals from cover and over/under records | none |
| Starters | spreads and totals from who starts | none |

**No first-quarter or first-half team total has ever been graded.** The full-game team total was:
the fourth search's same-number and off-number rules (§8.2) found nothing, and its shooting-luck
cell C2 passed.

## 2. Data

### 2.1 The bought team totals (measured)

- **Rows:** `odds`, `source = 'odds_api_nba_period_team_total_history'`, markets
  `team_totals_q1_home`, `team_totals_q1_away`, `team_totals_h1_home`, `team_totals_h1_away`, one
  over and under price per line.
- **Counts:** 2024-25 29,709 rows on all 1,230 games; 2025-26 41,763 rows on 1,230 games (1,229 for
  the first quarter). Read 2026-11-03 by the lab's `--pull` (below).
- **2023-24 holds none.** The pull asked for all 1,230 of its games and got 0 rows.
- **Books:** betPARX (2025-26 only), BetRivers, DraftKings, FanDuel, Hard Rock. All five are in
  `config.BEST_LINE_BOOKMAKERS`. Pinnacle prices none.
- **One purchase per game.** Every game has exactly one snapshot time, and in all 2,460 games it is
  the **same instant** as the period spread and total purchase already in the cache. So a book's team
  total and its period spread and total were quoted at the same moment.
- **When:** a median 54.4 minutes before tip. 1,224 of 2024-25's games and 1,218 of 2025-26's fall
  45-75 minutes before tip (decision point D). The other 18 have a stored tip far from the purchase:
  from 66 minutes before the purchase to 174 minutes after it.
- **Every row has both prices.**

**The pull is a cache of Supabase.** These rows are not in the research cache. The lab reads them
once, read-only, into its scratch folder (`python run_with_db.py scripts.nba_s_q1tt --pull`): indexed
reads by `game_id = ANY(...)`, 60 games at a time with a pause, in read-only transactions with a
30-second statement limit. Running it again regenerates the file.

### 2.2 Everything else (the research cache, itself a cache of Supabase)

- **Period spreads and totals:** each game's one purchase, 2023-24 to 2025-26 (`odds`, `source =
  'odds_api_nba_derivative_history'`).
- **Period scores:** `nba_period_scores`, through the first search's check (section 6).
- **Pinnacle's full-game close** (`H.pinnacle_close`): the period markets' pricing (§8.3) and the
  shape's stand-in (section 4.4).
- **Box scores:** `nba_player_game_log`, for family B's ratings (`models/nba_total_luck.team_box`).

## 3. Which number a book hangs

### 3.1 The main number (fixed before anything is priced)

**Hard Rock lists a ladder.** Counted on the bought rows (lines per book, team, period and purchase):

| Season | Book | Quotes | More than one line | Most lines |
|---|---|---|---|---|
| 2024-25 | BetRivers | 3,480 | 0.0% | 1 |
| | DraftKings | 4,648 | 0.0% | 1 |
| | FanDuel | 4,822 | 0.0% | 1 |
| | Hard Rock | 3,354 | 99.9% | 6 |
| 2025-26 | betPARX | 4,918 | 0.0% | 1 |
| | BetRivers | 4,918 | 0.0% | 1 |
| | DraftKings | 4,684 | 0.0% | 1 |
| | FanDuel | 4,906 | 0.0% | 1 |
| | Hard Rock | 4,738 | 90.0% | 11 |

On `NBA_2026-01-15_MEM_ORL` Hard Rock hangs five first-quarter home lines, 28.5 to 32.5, priced -185
to +175 on the over; the other four books all hang 30.5.

**The rule, per (game, market, book, purchase):**

1. Only a line with **both prices** can be the main one.
2. Coherent lines first (implied chances summing to 1.00-1.15).
3. The line whose two prices are **closest to even** (smallest gap between their implied chances).
4. Ties go to the **lower line**.

This is `models/nba_book_numbers.main_rungs`, the rule `split_main_rungs` applies when the live feed
stores the first-half total. **Every other line is a rung: filed, never bet, never a blind bet, never
part of any fair line.** On the example above Hard Rock's main number is 30.5 (+100 / -125).

**Then the house's ladder rule** (§8.2): a deciding book's main number more than 1 point from the
median of the deciding books' main numbers is an alternate line and is dropped the same way
(`NB.visible_numbers`). **Then** a visible main number priced past ±250 on either side is not a main
number and is dropped (`docs/nba_search_starters.md` 4.7). How many each rule removes is counted in
section 11.

### 3.2 Impossible numbers (stated before anything is read)

A row outside these ranges is filed wrong. It is dropped before anything is computed, and counted.

| Market | Allowed |
|---|---|
| First-quarter team total | 10 to 41 |
| First-half team total | 42 to 90 |
| First-quarter spread / total | ±15 / 35 to 80 |
| First-half spread / total | ±25 / 85 to 170 |

- **The two team-total ranges do not overlap,** so a first-half number filed under the first quarter
  cannot pass. (Why it is here: §10.8's 191 rows filed as full-game totals at 9.5 to 107.5 looked like
  an edge.) The spread and total ranges are the starters search's.
- **What it found, read before this was written:** every stored team-total line is in range:
  first-quarter 20.5 to 38.5, first-half 44.5 to 75.5. Prices run -300 to +230 at Hard Rock, whose
  rungs reach far from even, and -186 to +135 at the other four books. The starters search found no
  period spread or total out of range.

## 4. Family A: the book's own numbers

### 4.1 Decision time

Each game's one purchase, used only when it falls 45-75 minutes before tip (decision point D,
`H.per_event_times`). The team total and the period spread and total come from that purchase.

### 4.2 The implied period points

- **A quote's centre.** Each coherent period spread and total quote is solved to the centre at which
  its no-vig chance holds at its own number (`H.solve_any`), through that period market's own pricing:
  the spread of the period's result around a + b × Pinnacle's full-game close, from seasons before the
  graded one (`P3.period_market_pricing`, §8.3). **A centre is compared with a centre** (§9.3). At
  -110 / -110 the centre is the number itself. A lopsided quote (§8.4 found the period purchase kept
  one listed line per book, often an alternate at BetRivers, betPARX and Hard Rock) states its centre
  through its price instead of passing its off-centre number on.
- **The sign.** A spread's stored number is the **HOME number** (-3.5 = home favoured by 3.5). Its
  centre is the home team's expected margin, the quantity whose threshold is minus the home number
  (`H.threshold`). So a home -2 at even prices has a centre of +2.
- **Each team's points:** home = (total centre + home margin centre) / 2; away = (total centre - home
  margin centre) / 2. A first-quarter home -2 with a total of 58 at even prices implies home 30, away 28.
- **The quotes read** are each book's main number at T after the ladder rule (section 3.1), as every
  earlier period search read them. So a book whose stored period number sits more than 1 point from
  the deciding books' median has no number of its own that game.

**Corrected 2026-11-03, before any cell was graded (section 14.2):** "at -110 / -110 the centre is the
number itself" is not exact, and neither are the two worked examples above. The centre sits a few
hundredths of a point off the number, because the shape is centred on its average and not its middle.
The lab always solved the centre, so no bet moves.

### 4.3 Two references

- **(i) The same book.** A team-total offer at a book is priced at the points implied by **that book's
  own** period spread and total. A book with no visible main spread or no total that game has no
  same-book price, so none of its offers are bet in the same-book cells that game.
- **(ii) The consensus.** Every offer is priced at the points implied by the **median of the deciding
  books' centres**, spread and total apart. Pinnacle is not in it: it is the deciding books' median by
  definition, and Pinnacle sells no team total to compare against.

### 4.4 The result shape

A team's period points scatter around its implied number. That scatter prices an offer:
P(over wins) at the offer's line, given the centre.

- **The residual:** the team's period points minus its implied number, home and away pooled,
  re-centred on zero (`H.ResidDist`: the spread, not the average miss), with whole-point lines given
  their push mass.
- **From every season before the graded one, from 2020-21.**
  - Seasons **with period prices** (2023-24, and 2024-25 for 2025-26's shape): around the
    consensus implied number at that game's purchase.
  - Seasons **without** (2020-21 to 2022-23): around a stand-in, the team's points implied by
    Pinnacle's full-game close (home = (total - home number) / 2) times the period's minutes (12/48,
    24/48). This is how §8.2 priced the first period season.
  - 2024-25 is graded with 2020-21 to 2023-24; 2025-26 with 2020-21 to 2024-25. **A graded season's
    own results never price it**, and 2025-26's results are never read for the shape at all.
- **Fewer than 600 earlier residuals stops the run** (two teams a game, 300 games: the live
  team-total model's bar). There is no fallback to the season itself.
- **Why the stand-in seasons are kept.** Measured on 2023-24 (history, never graded), the same games'
  residuals around the implied number and around the stand-in have nearly the same spread:

  | Period | Around the implied number | Around the stand-in | Stand-in, 2020-21 to 2022-23 |
  |---|---|---|---|
  | First quarter | 5.77 points (2,450 residuals) | 5.82 (2,460) | 5.82 (7,080) |
  | First half | 8.07 (2,450) | 8.19 (2,460) | 8.12 (7,080) |

  So the stand-in seasons widen the shape by about 1%, and triple the sample in its tails.

### 4.5 The bet

- **Each team-total offer** at a deciding book is priced at its reference's implied number through
  the shape: P(win), P(push), and expected value per unit risked.
- **The bet** is the best deciding offer on the cell's side with expected value at or above the cut,
  at -200 or better (`H.choose`, the model-family rule: the cut is an expected-value floor on the
  family's own probabilities). Ties go to the earlier book in `config.BEST_LINE_BOOKMAKERS`.
- **Both teams' markets form one cell per side and cut** (as §8.1 and §8.2 did for team totals). A
  game can carry a bet on each team's total; every bet keeps its own market and settles on its own
  team's points. The whole-day bootstrap keeps a game's two bets together.

### 4.6 The team-total market's own fair line

The blind bets, and the centre the placebo moves a disagreement onto, need the team-total market's own
fair line. It is `H.market_fair` on the team-total quotes: the median of the deciding books' centres
(no Pinnacle quote exists), each solved through the same shape as 4.4.

## 5. Family B: the live home team-total rule on the period totals

**The rule is read from `models/nba_team_total_luck.py` and imported, not typed:**

- **The signal:** `home_part`, the home team's part of the shooting-luck gap: the away defence's
  luck-adjusted minus raw points allowed per 100 possessions, times the two teams' mean pace. Ratings
  from the same season's box scores dated before the game (`models/nba_total_luck.f4_projections`).
- **The side and cut:** the home team total **under** when -`home_part` is **2.0 or more**
  (`GAP_CUT`, `SIDE`).
- **Games:** both teams with at least **one** game this season (`LIVE_MIN_GAMES`, mike 2026-11-02:
  no 10-game wait). The live model's graded evidence was on 10+ games, so the bets inside either
  team's first 10 games are counted beside each cell.
- **The offer:** the best under at a deciding book, under the team-total market's own fair line
  (section 4.6), at -200 or better. The gap decides the game; the fair line only chooses the offer.
- **Not carried over:** the live card's expected-value floor. It is applied to the fair chance plus
  the full-game bucket's uplift, which has no period counterpart, and on the 349 graded bets it removed
  one.

**The period's share.** The gap and the cut are both in full-game points. The period's share of
full-game points (both teams' period points over their final points, overtime included, seasons
2020-21 to the one before the graded one) scales the gap and the cut alike. **So it moves no bet:**
the cell bets exactly the games the live rule would, on the period's home team total. The lab runs the
gap and cut unscaled and writes each season's share and the cut in period points beside the cell. A
cut kept at 2 period points would be a new cut (about 4 full-game points for the first half, 8 for the
first quarter), which is a new choice, so it is not registered.

**Bands (bar 5):** the fifth search's F8 bands on the same live signal: gap 1-2 (the band below the
cut), 2-3, 3-4 and 4+, in full-game points.

## 6. Settlement

- **A team total settles on that team's own points in the period:** the first quarter's, or the first
  two quarters' summed. Overtime never counts in a period. A push is a push: stake back, out of the
  denominator (§6.2).
- **The check** (the first search's, `H.with_periods`): a game's periods, overtime included, sum to the
  stored final score for both teams; they are numbered 1 to n with n at least 4; periods 1 and 2 are
  both there. **A game that fails has no settlement: it is left out of every cell and counted**
  (section 11).
- **How the harness is used.** The harness settles a team total on that team's own score. The lab hands
  it each team's period points as that score (`period_games`), so the harness's own settlement code
  grades every bet. A test pins it.

## 7. The cells (26)

| Family | Period | Sides | Reference or rule | Cut | Cells |
|---|---|---|---|---|---|
| `A_same` | first quarter, first half | over, under | the same book's spread and total | EV ≥ 0.02 / 0.04 / 0.06 | 12 |
| `A_consensus` | first quarter, first half | over, under | the deciding books' median | EV ≥ 0.02 / 0.04 / 0.06 | 12 |
| `B` | first quarter, first half (home team only) | under | the live home team-total rule | home part ≤ -2.0 | 2 |
| **Total** | | | | | **26** |

- **Every cell:** the best deciding price among the five books, -200 floor, one unit to win with risk
  capped at 3 (`H.risk_win`).
- **Beside each cell, never judged:**
  - DraftKings alone (2024-25 and 2025-26 apart, as the harness writes it);
  - the blind over and the blind under on the same population and offers, pooled, at the best deciding
    offer under the team-total market's fair line;
  - how many of its bets fall on games the live home team-total model and the live first-half total
    model would bet (each model's own rule on the period purchase, counts only);
  - for B, how many bets fall inside either team's first 10 games.
- **Bands (bar 5):** for A, expected value 0-0.02 (the band below the lowest cut), 0.02-0.04,
  0.04-0.06, 0.06 and up. For B, section 5.
- **A thin cell is still reported.** A cell under 200 pooled bets fails bar 1, and its bets, units,
  return, interval and season split are printed anyway. Its answer is "too few games to tell", not "it
  loses".

**One line added 2026-11-03, with the lab and before any cell was graded. It changes no cell and no
bar:** DraftKings alone is also written pooled over both seasons beside each cell (`dk_pool_n`,
`dk_pool_units`, `dk_pool_roi`), since the harness writes it only season by season.

## 8. Seasons

- **Graded and pooled: 2024-25 and 2025-26**, the only seasons with team totals.
- **2023-24 is history only:** its period prices and scores build the shape (4.4).
- **The choosing season, which the placebo bar reads, is 2024-25 alone** (`P3.choosing`: every graded
  season but 2025-26).
- `--full` refuses team totals in any other season, and a graded season whose purchases reach fewer
  than 90% of its games at D.

## 9. The bars

§9.1's house standard, by `python -m scripts.nba_game2_verdict --results DIR --house5`:

1. Pooled over the graded seasons, 200 or more bets.
2. The pooled whole-day bootstrap 95% interval of the return is above zero (4,000 resamples, seed 7).
3. Seasons mostly positive.
4. Beats the blind bet on its dominant real side, pooled (§6.4's bar 9).
5. The band just below the cut and every band from the cut up each have a positive pooled return where
   they hold 30 or more bets, and the cell's own pooled return is above zero.
6. The return on the choosing season beats the 95th percentile of 200 placebo runs, a run with no bet
   counting as 0.

**With two seasons, "seasons mostly positive" means both.** The verdict's bar 3 lets one of the counted
seasons be negative, which with two seasons is half of them. So this search adds one line: **both
2024-25 and 2025-26 have 30 or more bets and a positive return.** `python -m scripts.nba_s_q1tt --judge
--results DIR` calls the verdict's own function and applies it, so the verdict script is unchanged. A
cell passes only on both.

Closing-line value cannot be measured: one purchase per game, so the decision quote is the last one.
"Still offered at the next purchase" reads 0 for the same reason.

## 10. The placebo

**200 runs, seeds 1-200. Each run moves every game's information to another game on the same date and
keeps every game's own lines and prices.**

- **Family A.** A game's **disagreement** is its implied number minus the team-total quote's own
  centre:
  - same book: the book's own team-total quote, solved through the shape;
  - consensus: the team-total market's fair centre (4.6).

  In a run, each game draws another game on the same date (one permutation per date), in the same
  period, for the same team role (home to home, away to away) and, for the same-book cells, the same
  book. The drawn disagreement is added to the game's own team-total centre, every offer is priced
  again, and the cell's rule is applied.
  - **Why against the quote's centre and not its bare line:** the game's own lean between over and
    under stays with the game, so the run moves only the information the reference adds.
  - **Why not move the whole probability:** that hands each game another game's market price, which any
    model beats (§8.1).
  - **An offer whose drawn game has no disagreement at that book** (that book had no same-book number
    there) is not priced in that run. So a same-book run can place fewer bets than the real cell for a
    mechanical reason; the counts (section 11) report real and placebo bets side by side.
- **Family B.** Each game's home part is moved to another game on the same date (the fifth search's F8
  placebo, `S.ShuffledGaps`).

**The placebo must be a null on the real prices.** `--smoke` measures, on real offers with no result
read, the share of placebo bets that are not the real bets, and the most any shuffle could reach (1
minus the share of the population the cell bets). Section 11 reports both.

## 11. Counts before grading

Counted 2026-11-03 by `python -m scripts.nba_s_q1tt --smoke` on the real data, before any cell was
graded. Prices, lines, timestamps and settlement checks only: no win,
loss or unit of any bet this search would place was computed, and no 2024-25 or 2025-26 result was
read except to know that its period scores pass the check.

### 11.1 The answer before grading: family A has almost nothing to bet

**The books set their period team totals from their own period spread and total.** The implied number
minus the team-total quote's own centre, in points, over every team and game at T:

| Period | Reference | Team-games | Average | Spread (sd) | 1st to 99th percentile |
|---|---|---|---|---|---|
| First quarter | same book | 10,516 | -0.00 | 0.10 | -0.23 to +0.25 |
| | consensus | 4,882 | +0.04 | 0.14 | -0.27 to +0.41 |
| First half | same book | 12,352 | -0.06 | 0.14 | -0.40 to +0.30 |
| | consensus | 4,864 | -0.06 | 0.18 | -0.48 to +0.37 |

- **A bet needs half a point in the first quarter and most of a point in the first half.** Through the
  shapes used, an over at -110 whose centre sits exactly on its line is worth -0.051 (first quarter) and
  -0.057 (first half): the books' margin. With the centre a point above the line it is worth +0.080 and
  +0.036. Reaching 0.02 takes 0.53 to 0.55 points in the first quarter and 0.83 in the first half. The
  typical disagreement is 0.10 to 0.18.
- **The expected value of every deciding offer** averages -0.053 (first quarter, same book), -0.058
  (first quarter, consensus), -0.047 and -0.054 (first half). The best single offers reach 0.10, 0.11,
  0.07 and 0.14.
- **So every family A cell is under 200 bets** (section 11.4) and fails bar 1 by construction. By
  section 7 its answer is **too few games to tell**, and its bets are graded and printed anyway. The
  measured reason is stronger than thinness: a book's team total says what its own spread and total
  say, to within a tenth or two of a point (the spreads in the table, 0.10 to 0.18).

### 11.2 Games per season

| Season | Games | A team-total row before tip | A purchase 45-75 min before tip | Trusted period score | First quarter: offers / consensus number / same-book number / home part | First half: the same |
|---|---|---|---|---|---|---|
| 2024-25 | 1,230 | 1,229 | 1,224 | 1,230 | 1,224 / 1,224 / 1,213 / 1,208 | 1,224 / 1,224 / 1,224 / 1,208 |
| 2025-26 | 1,230 | 1,228 | 1,218 | 1,230 | 1,218 / 1,217 / 1,212 / 1,202 | 1,218 / 1,208 / 1,206 / 1,202 |

- **The choosing season keeps its gate.** 2024-25's purchases reach 99.5% of its games at D, above the
  harness's 95% (`H.gated_seasons`), so the placebo bar reads it.
- **Settlement: no graded game is left out.** All 2,460 games of 2024-25 and 2025-26 pass the check
  (their periods, overtime included, sum to the final), and so does every game of 2020-21 to 2023-24.
  The cache's only failures are 4 games of 2019-20 with no period rows, a season this search never
  reads.

### 11.3 What the number rules removed

- **The impossible-number rule removed no row,** of the team totals or the period spreads and totals.
- **The main-number rule:** 35,317 first-quarter lines read became 19,958 main numbers; 36,103
  first-half lines became 20,194. The ladder rule then removed 0 and 1, and no visible main number was
  priced past ±250. The ladder table of section 3.1, recounted after dropping rows stamped after tip,
  moves by at most 6 quotes a book.
- **The main numbers visible at T:** first-quarter team totals 22.5 to 35.5, first-half 45.5 to 70.5,
  priced -150 to +118. Period spreads and totals visible at T: first-quarter spreads -9.5 to 7.5 and
  totals 48.5 to 66.5; first-half spreads -14.5 to 13 and totals 97 to 130.5; priced -200 to +145.
- **Implied points:** first quarter 22.9 to 35.7, first half 45.9 to 70.7. The team-total market's
  own fair centres: 22.9 to 35.5 and 46.1 to 70.6.
- **The highest-EV offers are disagreements, not bad rows.** First quarter, consensus, 0.106: FanDuel's
  Boston under 29.5 at +100 against Portland (2025-03-05), where the consensus implies 28.8 and the other
  books hang 28.5 to 29.5. First half, consensus, 0.141: Hard Rock's Cleveland over 64.5 at +100 against
  New Orleans (2025-12-23), where the consensus implies 66.1 and the other books hang 65.5.
- **Same-book numbers are mostly DraftKings and FanDuel.** Games where a book has a team total and its
  own visible period spread and total:

  | Book | First quarter, 2024-25 / 2025-26 | First half, 2024-25 / 2025-26 |
  |---|---|---|
  | DraftKings | 1,102 of 1,105 / 1,149 of 1,155 | 1,202 of 1,207 / 1,161 of 1,164 |
  | FanDuel | 1,184 of 1,197 / 1,205 of 1,215 | 1,183 of 1,202 / 1,200 of 1,215 |
  | BetRivers | 175 of 864 / 0 of 1,218 | 41 of 864 / 0 of 1,218 |
  | Hard Rock | 8 of 834 / 124 of 1,173 | 428 of 833 / 869 of 1,176 |
  | betPARX | none / 311 of 1,218 | none / 92 of 1,218 |

  BetRivers prices no period spread or total at all in 2025-26. Otherwise BetRivers, Hard Rock and
  betPARX lose theirs to the ladder rule: their stored period number is the last line listed (§8.4),
  often an alternate more than 1 point from the other books. Counted at T: the rule removes Hard Rock's
  first-quarter spread on 1,163 of 1,195 games in 2024-25 and 1,036 of 1,183 in 2025-26, BetRivers'
  first-half total on 1,011 of 1,221 in 2024-25, and betPARX's first-half total on 950 of 1,218 in
  2025-26; DraftKings and FanDuel lose at most 16 of about 1,200 in any market.

### 11.4 The bets each cell would place

An offer at a deciding book at -200 or better that clears the cell's cut; counted, never graded.

| Family | Period | Side | Cut | 2024-25 | 2025-26 | Pooled | On the live home team-total model's games | On the live first-half total model's games |
|---|---|---|---|---|---|---|---|---|
| A_same | first quarter | over | 0.02 / 0.04 / 0.06 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | | |
| | | under | | 2 / 1 / 1 | 0 / 0 / 0 | 2 / 1 / 1 | 0 | 0 |
| | first half | over | | 3 / 1 / 0 | 1 / 0 / 0 | 4 / 1 / 0 | 1 / 0 / 0 | 0 |
| | | under | | 2 / 2 / 1 | 2 / 0 / 0 | 4 / 2 / 1 | 1 / 0 / 0 | 0 |
| A_consensus | first quarter | over | | 28 / 3 / 1 | 53 / 5 / 2 | 81 / 8 / 3 | 12 / 1 / 0 | 14 / 2 / 1 |
| | | under | | 27 / 3 / 1 | 14 / 3 / 2 | 41 / 6 / 3 | 9 / 0 / 0 | 7 / 2 / 0 |
| | first half | over | | 16 / 5 / 1 | 15 / 4 / 2 | 31 / 9 / 3 | 4 / 2 / 0 | 6 / 1 / 0 |
| | | under | | 45 / 11 / 2 | 35 / 6 / 2 | 80 / 17 / 4 | 6 / 2 / 0 | 23 / 6 / 2 |
| B | first quarter | under | home part ≤ -2 | 156 | 131 | 287 | 287 | 10 |
| B | first half | under | home part ≤ -2 | 156 | 131 | 287 | 287 | 10 |

- **24 of the 26 cells are under 200 bets: every family A cell.** The largest holds 81. They fail bar 1
  and read "too few games to tell" (11.1 says why).
- **Both family B cells clear 200: 287 bets each.** Every one of them falls on a game the live home
  team-total model would bet: it is the same rule on the same games, so family B tests whether the
  rule's edge reaches the period's home total, not new games. 10 of them (3.5%) are also on the live
  first-half total model's games, and 77 fall inside either team's first 10 games (the live model now
  bets from the first game; its graded evidence was on 10+).
- **The two B cells bet the same 287 games,** one on the first-quarter home total, one on the first-half
  home total, and they are exactly the live home team-total model's 287 (`b_games` in `--smoke`): every
  game the rule picks has both periods' home team-total offers.
- **The live models' games on the graded seasons:** the home team-total model 287, the first-half total
  model 444, each by its own rule on the cache's period purchase.
- **Bands (bar 5), pooled bets:** family B, home part 1-2: 373, 2-3: 172, 3-4: 58, 4 and up: 57, in both
  periods, so all four bands are judged. Family A's bands from the cut up hold 0 to 73 bets; the band
  below the lowest cut holds 5 to 343.

### 11.5 The shape and the period's share

| Period | Season | Kind | Residuals | Spread (sd) |
|---|---|---|---|---|
| First quarter | 2020-21 / 2021-22 / 2022-23 | stand-in | 2,160 / 2,460 / 2,460 | 5.83 / 5.81 / 5.82 |
| | 2023-24 / 2024-25 | implied | 2,450 / 2,448 | 5.77 / 5.74 |
| First half | 2020-21 / 2021-22 / 2022-23 | stand-in | 2,160 / 2,460 / 2,460 | 8.13 / 8.20 / 8.04 |
| | 2023-24 / 2024-25 | implied | 2,450 / 2,448 | 8.07 / 7.84 |

The shapes used: 2024-25 is priced on 9,530 residuals (first quarter 5.81 wide, first half 8.12);
2025-26 on 11,978 (5.79 and 8.06). 2024-25's residuals enter only 2025-26's shape. Their average is not
printed: it would read like a blind over or under on a graded season.

**Family B's share** (both teams' period points over their final points, earlier seasons from 2020-21):
first quarter 0.2524 for 2024-25 and 0.2520 for 2025-26; first half 0.5035 and 0.5025. The live cut of
2.0 full-game points is so about 0.50 first-quarter points and 1.01 first-half points; the gap scales
the same way, and no bet moves.

### 11.6 The placebo on the real prices

The share of placebo bets that are not the real bets, 10 runs per cell, no result read; the ceiling is 1
minus the share of the population the cell bets.

| Family | Cells | Share of placebo bets that differ | Ceiling |
|---|---|---|---|
| A_consensus | 12 | 0.55 to 0.91, mean 0.78 | 0.98 to 1.00 |
| A_same | 12 (8 with any bet) | 0.85 to 1.00, mean 0.93 | 1.00 |
| B | 2 | 0.73 in both | 0.88 |

- **It is a null on the real data:** most placebo bets are other games' bets in every cell.
- **The consensus runs place more bets than the real cells:** 149 against 81 at the first-quarter over,
  cut 0.02; 159.6 against 80 at the first-half under. The same-book runs place a little fewer (the
  mechanical reason in section 10).

### 11.7 The clock

Two smoke runs, the counts above identical in both; the times are the second's, the first's beside.

- **A family A placebo run takes 0.025 to 0.029 seconds** (0.33 to 0.45 frame by frame; first run
  0.019 to 0.031). On the real offers with made-up scores, the two paths agreed on all six
  first-quarter cells of each reference, two runs each.
- One group of six family A cells without its placebo: 8.1 seconds (6.7). One family B cell with its 200
  runs: 3.3 seconds (4.1).
- **`--full` is projected at 5.9 minutes (4.9):** 4.9 for the setup with Pinnacle's closes saved (3.8),
  1.1 for the cells. Building the closes afresh took the first smoke's cache read from 3 seconds to 27.
  **Peak memory in `--smoke` was 1.8 GB** in both.

## 12. Expected passes by chance

26 × 0.025 ≈ 0.65 cells clear bar 2 alone, before correlation. The cuts are nested and a game's two
team totals are bet together, so the cells are far from independent. Bars 3 to 6 and the both-seasons
line make a chance pass rarer still.

**A pass is built live** (`CLAUDE.md` §2) with its own EV floor and the prices it lays stated before
it ships. It needs a live capture of these markets first; whether one exists has not been checked here.

## 13. What the lab does

- `--pull`: the read-only pull of section 2.1.
- `--smoke`: the synthetic checks, then real counts and inputs only, never a graded real bet.
- `--full` refuses unless `NBA_GAME2_GO=1`, `NBA_GAME2_RESULTS` and `NBA_GAME2_BETS` are set, the
  pulled file and the cache's ledger and period scores exist, and section 8's season checks hold. It
  writes `cells_A_same.parquet`, `cells_A_consensus.parquet` and `cells_B.parquet` only after all three
  families are built, with the implied numbers and the shape's summary.
- **Bets are saved** through the harness's own column list, with the period named on each (`period`,
  `tt_market`): no column parquet cannot store.
- **A placebo run is a lookup.** Every offer is graded once. For family A each run re-prices the offers
  as arrays and takes run_cells' own choice as a group arg-max; for family B the starters search's
  `ShuffledGaps` reads each game's bet from a table. A test, and `--smoke` on real offers with made-up
  scores, hold both equal to the harness's frame-by-frame path.
- **What is saved** under `NBA_S_Q1TT_SCRATCH`: the pulled rows and Pinnacle's full-game closes, each
  regenerable (the first by `--pull`, the second from the cache, with a fingerprint of the cache files).

## 14. Changes after an independent review, before any cell was graded (2026-11-03)

An independent review of this section's rules and its lab ran before any cell was graded. It found no
fault that changes what a cell bets or how it is judged, and four smaller points. Each is recorded here
before `--full` runs. The reviewer's scripts and logs are in
`C:/Users/micha/AppData/Local/Temp/nba_s/q1tt_review/`; the lab's own re-measurement is
`C:/Users/micha/AppData/Local/Temp/nba_s/q1tt/review_points.py`. Prices, shapes and drawn results only:
no real result of a bet this search would place was read.

### 14.1 Bar 6 is looser for family A than intended

**What happens.** Family A's placebo runs place more bets than the real cell: about twice as many
pooled (149 against 81 at the first-quarter over, cut 0.02, section 11.6), and 1.2 to 1.6 times as many
on 2024-25, the season bar 6 reads (the four consensus cells at cut 0.02).

**Why.** An offer's price in a placebo run is the game's own team-total centre plus another game's
disagreement. The own centre carries how far the market's fair centre sits from that offer's own
centre. In the real price that gap partly cancels against the game's own disagreement: across every
consensus offer the two correlate at -0.16 (first quarter) and -0.13 (first half). A placebo run breaks
the pairing, so its prices spread wider than the real ones: a spread of 0.216 against 0.202 points in
the first quarter, 0.282 against 0.266 in the first half. More offers then clear each cut.

**And the runs repeat each other.** Across 20 runs of each consensus cell, a run's bets also appear in
another run 34% to 44% of the time at cut 0.02 (pooled; 29% to 42% on 2024-25), and 17% to 49% across
all twelve consensus cells.

**How much looser.** The reviewer drew results from the fair distribution, so no real cell carried an
edge, and asked how often bar 6 would pass:

| Cells | Drawn worlds each | Bar 6 passed |
|---|---|---|
| Consensus, cut 0.02 (16 to 45 bets on 2024-25) | 300 | 4.7% to 13.7% |
| Every consensus cell | 300 | 0% to 19.3% |
| Family B, both periods | 500 | 5.8% and 5.0% |

The intended rate is 5%. So bar 6 passes a no-edge family A cell up to 2.7 times too often at cut 0.02,
and up to 3.9 times in its thinnest cells.
Family B's placebo holds the intended rate.

**What this changes: nothing now.** Every family A cell is under 200 bets (section 11.4), so each fails
bar 1 whatever bar 6 reads. The lab is not changed. Bar 6 is still reported for family A. **It is
read as looser than 5% for that family: a family A cell that passed bar 6 and nothing else would not be
evidence of anything.**

### 14.2 The centre at even prices (section 4.2, corrected)

At -110 / -110 a quote's centre is its number less the shape's middle offset: the shape is re-centred
on its average, and the average and the middle of a skewed scatter differ.

- **Measured** through every shape used, over every half and whole number in the range quoted:
  - period spreads and totals: within 0.06 points on half-point numbers, 0.07 on whole numbers;
  - first-quarter team totals: within 0.06;
  - first-half team totals: within 0.14.
- On the quotes themselves, the reviewer measured at most 0.053 points for the implied team points from
  DraftKings' even-priced period quotes, and 0.045 (first quarter) and 0.14 (first half) for the
  team-total quotes at even prices.
- **No bet moves.** The lab solves every centre through the shape and never assumes the number. Only
  the sentence and its two worked examples (home -2 has a centre of +2; home 30, away 28) were too
  round.

### 14.3 The same-book cells' blind bet

The blind over and blind under beside a same-book cell are bet on the cell's own population of games.
They take the best offer at **any** deciding book that game, not only at the books the cell can bet
there (a book with its own visible spread and total). That is how `H.run_cells` builds every blind bet.

Measured on the real prices: 13% to 37% of those blind bets fall at a book the same-book cell cannot
bet in that game:

| Period | Blind over | Blind under |
|---|---|---|
| First quarter | 1,805 of 4,850 (37.2%) | 627 of 4,850 (12.9%) |
| First half | 816 of 4,860 (16.8%) | 831 of 4,860 (17.1%) |

Most of them are at Hard Rock, betPARX and BetRivers, the books section 11.3 found without a same-book
number. So bar 4 compares a same-book cell with a blind bet that can shop more books than the cell
can. Bar 4 is unchanged; read it with that in mind.

### 14.4 Family B is now checked against the live decision function

The test that family B bets exactly the live rule's games compared the lab with its own copy of the
rule. With family B's sign flipped, it still passed.

**It is replaced.** `test_family_b_bets_exactly_the_games_the_live_decision_function_bets` hands each
period's home team-total quotes to the live model's own decision function,
`models.nba_team_total_luck.decide`, through the lab's `live_rule_games`, on a synthetic world. It
requires decide's bet games to equal family B's in every graded season and both periods.

- **Watched failing:** with family B's sign flipped, the new test fails, and the old one passes.
- **On the real data** (the same call, `q1tt/live_real.py`): family B's games equal decide's in both
  periods and both seasons, 156 in 2024-25 and 131 in 2025-26. The reviewer found the same with decide
  on the full-game home team-total quotes: 287 of 287, and all 2,410 home parts it compared identical.


## 15. Results (graded 2026-11-04)

Run `2026-11-04-q1tt`, stored in Supabase. 26 cells. The grade took 417 seconds.

**0 of the 26 cells pass. The first-quarter and first-half team totals stay closed.**

- **Family A, 24 cells: too few games to tell.** The books set these totals from their own period spread and total,
  so a disagreement big enough to bet is rare (section 11). The largest cell holds 81 bets.
- **Family B, the live home team-total rule carried to the period totals:**

| Cell | Bets | Units | Return | 95% interval | 2024-25 / 2025-26 | Fails |
|---|---|---|---|---|---|---|
| Home first-quarter team total, under | 287 | +10.67 | +3.3% | -8.7% to +14.7% | +3.9% / +2.7% | interval, bands, placebo |
| Home first-half team total, under | 287 | +9.91 | +3.1% | -8.8% to +14.7% | +3.8% / +2.3% | interval, placebo |

  Both cells bet exactly the 287 games the live home team-total model bets. Both seasons are positive in both, but
  287 bets cannot separate +3% from nothing. They say the live model's lean does not get stronger in the shorter
  period.

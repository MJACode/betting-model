# NBA search: spreads and moneylines re-graded with result shapes that depend on the size of the line

**Written 2026-10-31, before any cell of this search was graded. Nothing below changes after a
result is seen; a later change gets its own dated line and its reason.** Lab:
`scripts/nba_s_shapes.py`. Tests: `tests/test_nba_s_shapes.py`. Pass/fail:
`python -m scripts.nba_game2_verdict --results <folder> --house5` (the bars of
`docs/nba_models_2026.md` section 9.1). No data is bought and nothing is written to the database.

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find it."*
Section numbers below are those of `docs/nba_models_2026.md`, "the record".

## 1. What is tested, and why

Several failed families turn a spread into a win chance, or price an offer at a number other than
the market's. To do that they need the spread of results around the number: the **result shape**.
They all used **one shape per season and market** (`H.close_dist`, or a projection's own error
pooled the same way).

Section 10.7 measured, after those searches had closed, that the shape depends on the size of the
line. Results around Pinnacle's close, signed toward the favourite, before 2023-24:

| Closing line | Games | Favourite by 12+ more than the line | Underdog by 12+ more |
|---|---|---|---|
| 5 or less | 1,749 | 15.6% | 18.4% |
| 5 to 10 | 1,355 | 15.1% | 19.1% |
| more than 10 | 436 | 19.0% | 15.4% |

One shape therefore overstates a big underdog's chance of winning outright and understates a close
game's. That is a possible pricing error in the grading itself: it could have made bad bets look
good and hidden good ones. **This search re-grades the same cells with the shape for the size of the
line and changes nothing else that a result could have influenced.**

The honest prior, from the sweep that proposed this: it mostly removes bets rather than adds them.
That is a prediction, not a bar.

## 2. What earlier searches covered, and what they did not

- **Covered, one shape:** F2 and F6d (spread against moneyline; §6.3, closed §6.6, house standard
  §6.7), F1 (§6.3, same), P1 and P2 (§8.1, §8.2, closed §8.4).
- **Line-size shapes were used only** for the alternate lines (§10.7) and the injury-report search
  (§11.2 item 3). No family above was ever priced with them.
- **Those families' placebo was weak where a whole number moved.** F2's placebo moved the favourite's
  whole win chance between games, and F1's a whole projection, which hands a game another game's
  market price. Section 10 below replaces that.
- **Those families were judged before section 9.1's bars existed** (bands, 200 placebo runs). This
  search is judged under them.

## 3. What the shape can reach

Read from the labs, before any cell. A shape can only change a bet where the bet's number is read
through it.

| Cells of the original | Does a shape set the bet? | Here |
|---|---|---|
| F2, moneyline, 96 | **Yes.** The spread becomes a win chance through the shape; the moneyline is priced on it | S_F2, 96 |
| F6d, moneyline, 8 | **Yes.** The same, each book's moneyline against its own spread | S_F6d, 8 |
| F1, spread and moneyline, 96 | **Yes, its own shape.** The projection is priced through its own pooled error | S_F1, 96 |
| P1, full-game spread, 24 | **Yes.** The market's centre is solved through the shape, the model moves it, and every offer is priced through the shape | S_P1, 24 |
| P2 off-number, full-game spread, 32 | **Partly.** The gap and the side read no shape. The shape decides which qualifying offer is taken and prices the blind bets | S_P2, 32 |
| P2 same-number, moneyline and spread, 64 | **No.** The rule's chance is Pinnacle's no-vig share (§8.2). Only its blind bets move | graded once, control, never judged |
| P1, full-game moneyline, 24 | **No.** The offset is the no-vig log-odds | graded once, control, never judged |
| Every total: F1 48, P1 24, P2 full game 64, F6d 8 | **No line-size shape exists.** §10.7 measured totals and kept one shape | not re-graded |
| F1b 48, F5 36 | **Hardly.** They cut on a gap in points, and the shape only ranks offers on one side. On S_P2, the family that reads spreads this way, it moves 81 of 25,610 bets (§15.2). 61% to 63% of spread quotes sit at Pinnacle's number (corrected 2026-11-01: this line first said 90%, a figure measured nowhere) | not re-graded |
| First half, first quarter, team totals in P1 and P2 | No shape was measured for period lines. Team totals have one (§10.7) but are not a spread or moneyline | not re-graded |

**The 256 cells re-graded are the ones a shape reaches.** F1's is one definition beyond a plain swap:
the market's shape never priced F1, so its own error is split the same way (section 5.2).

## 4. Data

The research cache (`NBA_RESEARCH_CACHE`, built 2026-10-29), a cache of Supabase, read-only:

- **Prices:** `nba_odds`, source `odds_api_historical`, moneylines and full-game spreads, 2020-21 to
  2025-26, every game priced (`H.load`; the seventh search's news-window purchases are left out, as
  `H.load` does by default, so the decision and closing fetches are the originals').
- **Results:** `nba_games`, final scores, overtime counted.
- **The projection (S_F1, S_P1):** `nba_player_game_log`, `nba_player_game_adv`, `nba_stints`,
  `nba_injury_report`, `nba_game_inactives`, through `scripts/nba_game2_projection.py`, its own
  walk-forward. **The inputs of S_P1:** `nba_schedule`, and the shooting-luck gap (§8.1).
- **Reads of results** are of seasons before the one graded (shapes, the projection's fits, P1's
  fits), never of a game's own result.

Frames this lab creates (`NBA_S_PROJ_DIR`, the projection at each decision point) are regenerable
from the cache: the engine is deterministic and takes no input from outside it.

## 5. Definitions

### 5.1 The shape

- **The size of the line:** 5 or less, 5 to 10, more than 10 points (`A.spread_bucket`: 5.0 reads the
  first, 10.0 the second).
- **The market's shapes:** `scripts/nba_game6_alt.spread_shapes`, unchanged. Results around Pinnacle's
  closing spread, from earlier seasons, for games whose close was the same size, signed toward the
  favourite and mirrored when the away team is favoured. Called with seasons 2020-21 to 2025-26 and
  its own floor of **300 earlier games** per size. `H.ResidDist` re-centres each on zero: the spread
  of results, not the average miss.
- **Which shape a game reads:** by its number at the decision time T, the HOME number: Pinnacle's
  coherent spread where it quotes, else the median of the deciding books' (`M.posted_spread`), among
  the quotes that family reads. F2's Pinnacle cells read Pinnacle's number, its consensus cells the
  deciding books' median, F6d each book's own number. Every offer on that game is priced through
  that one shape, whichever number the offer hangs (`A.game_sigma`).
- **The fallback is the one shape** (`H.close_dist`), for: a level line (no favourite), a game with no
  number at T, and a size with fewer than 300 earlier games.
- **What the fallback costs, stated now.** Earlier games per size, Pinnacle's close, counted
  2026-10-30 before the quote rule below (`H.pinnacle_close`, `A.spread_bucket`):

  | Season graded | 5 or less | 5 to 10 | more than 10 | Games over 10 that season |
  |---|---|---|---|---|
  | 2021-22 | 537 | 429 | **114** | 185 |
  | 2022-23 | 1,123 | 888 | **299** | 137 |
  | 2023-24 | 1,749 | 1,355 | 436 | 244 |
  | 2024-25 | 2,311 | 1,779 | 680 | 278 |
  | 2025-26 | 2,803 | 2,239 | 958 | 298 |

  **So the games with lines over 10 in 2021-22 and 2022-23 keep the one shape: the seasons where the
  mechanism lives most have it only in the last three of five.** The floor stays at 300, the plain
  reading of "reuse `spread_shapes`". A tail read from 114 games has a standard error near 3 points
  of probability on a 15% tail, larger than most of the EV cuts, so a lower floor would swap a known
  bias for noise of a size that could itself create false bets. The floor is not moved to reach the
  299; it was fixed before this count was used for anything.
- **2020-21** has no earlier priced season: both arms read its own season's one shape, in-sample,
  reported apart and never chosen on, as in the originals.

### 5.2 F1's shape

F1 prices the projection through its own error: result minus the same projection at the same
decision point, on earlier seasons, never the market's smaller error (§6.5, second amendment). That
stays. **The error is split the same way:** by the size and sign of the game's number at T
(`P.consensus`: Pinnacle's, else the deciding books' median), signed toward the favourite that number
names, mirrored when the away team is favoured, floor 300, the same fallback (F1's own pooled error,
`P.projection_dist`). The market's number only says how big the game is; the centre stays the
projection's. `own_error_shapes` is written to match `spread_shapes`, and a test holds them equal.

### 5.3 Each family, in one line each

- **S_F2:** the reference's spread at T is solved to a centre through the game's shape; the home win
  chance is P(margin above 0) with the tie mass removed; moneyline offers are priced on it. Sides:
  the reference's favourite, its underdog. A level reference has no favourite (§6.5).
- **S_F6d:** the same, each deciding book's moneyline against that book's own spread, both from one
  fetch (§6.5). Moneyline cells only.
- **S_F1:** the moneyline is P(margin above 0) from the projection and its shape, the tie mass
  removed; spread offers are priced through the shape. The rest of the projection is §6.3.
- **S_P1:** the market's centre is solved through the game's shape, the walk-forward model is fit on
  results around that centre and moves it, and offers are priced through the same shape (§8.1).
- **S_P2:** Pinnacle and a deciding book in one fetch at different numbers; the side and the gap are
  §8.2's; the best-EV qualifying offer is taken, priced around Pinnacle through the game's shape.

### 5.4 Numbers that cannot be read: the rule, stated up front

Measured 2026-10-30 on the quotes this search reads, at decision points A, C and D, reading no
result. The highest-EV offers in the one-shape arm were broken quotes, not prices:

- `NBA_2023-04-08_DEN_UTA`: Pinnacle's spread +5.5 with the deciding books' median at +10.5, its
  moneyline left behind with it. Under F2 every book's home moneyline read +0.56 to +0.61 EV.
- `NBA_2021-12-10_BOS_PHX`: FanDuel's home number +3.5 with Pinnacle's -3.5, the sign flipped.
- `NBA_2026-03-21_MIA_HOU`: Fanatics at +9.5 priced -450/+350, with Pinnacle at -2.

**The rule, applied to both arms before any pricing, to every family:**

- A **spread** quote, Pinnacle's included, more than **2.5 points** from the median of the deciding
  books' numbers at T is dropped.
- A **moneyline** quote, Pinnacle's included, whose no-vig home chance is more than **0.08** from the
  median of the deciding books' at T is dropped.
- It needs **3 or more** deciding books quoting that game and market at T; with fewer there is no
  median to read against and the quote stays.
- **Why those numbers.** The distance from the deciding books' median has a 99.9th percentile of 2.0
  to 2.5 points at A, C and D. The moneyline's distance from Pinnacle has one of 0.037 to 0.083. So
  the rule drops roughly the outermost one quote in a thousand. It was set from the spread of the
  numbers, with no result read.
- **Pinnacle falls too**, because a Pinnacle number left over from before a late scratch is exactly
  this fault. A game whose Pinnacle quote is dropped falls to the deciding books' median as its
  market number and has no bet in F2's Pinnacle cells or in S_P2.
- **The same rule on the close:** a Pinnacle close that fails against the deciding books at the
  game's last pre-tip fetch is dropped, from the shapes and from closing-line value, in both arms.
- **No price ceiling is added.** The originals had none, a -200 floor (`config.DEFAULT_MIN_ODDS`), and
  a +1000 underdog is a real price. The prices a passing cell lays are stated before it ships.
- Spread numbers stored run from -24.5 to +22.0, all possible. Nothing else is filtered.
- `--smoke` prints the extremes after the rule, the quotes dropped per season, market and book, and
  the highest-EV offers, so a rule that misses a fault shows before anything is graded.

**This changes the comparison with the record.** See section 11.

## 6. The cells (256)

Cuts, decision points and sides are the originals'. Nothing was re-cut.

| Family | Market, side | Decision points | Extra axis | Cut | Cells |
|---|---|---|---|---|---|
| S_F2 | moneyline, the reference's favourite and underdog | A, B, C, D | reference: Pinnacle's spread, the deciding books' | EV ≥ 0, .01, .02, .03, .05, .08 | 4 × 2 × 2 × 6 = 96 |
| S_F6d | moneyline, home and away | C, D | | EV ≥ .01, .03 | 2 × 2 × 2 = 8 |
| S_F1 | moneyline and spread, home and away | A, B, C, D | | EV ≥ 0, .01, .02, .03, .05, .08 | 4 × 2 × 2 × 6 = 96 |
| S_P1 | spread, home and away | A, C, D | | EV ≥ .02, .04, .06, .08 | 3 × 2 × 4 = 24 |
| S_P2 | spread, home and away | A, B, C, D | off number | gap ≥ 0.5, 1, 1.5, 2 points | 4 × 2 × 4 = 32 |
| **Total** | | | | | **256** |

Decision points are §6.2's: A the 15Z fetch, B the newest fetch 3-6 hours before tip, C 60-180
minutes, D 45-75 minutes. Each game is decided once per cell. Best price among
`config.BEST_LINE_BOOKMAKERS` (Pinnacle and Bovada never a deciding price), -200 floor, DraftKings
alone reported beside. One bet per game and cell, ties to the earlier book (`H.choose`).

## 7. Bands

Bar 5 of §9.1 reads bands along the cut axis, within one family, point, market, side and reference.
The band just below a cell's cut and every band from its cut up must have a positive pooled return
where they hold 30 or more bets (`G5.band_bounds`, `G5.band_columns`).

- **The band below the lowest cut:** from **-0.01** where the lowest cut is EV ≥ 0 (S_F2, S_F1); from
  **0** otherwise (S_F6d, S_P1 for EV; S_P2's gap, where that band is the offers at Pinnacle's number).
- A band's bets are the cell's own choice at its lower edge, less the games still chosen at its upper
  edge (§9.1).

## 8. Seasons and settlement

- **Graded and pooled:** 2021-22 to 2025-26. **Choosing seasons, which the placebo bar reads:** 2021-22
  to 2024-25 (`H.CHOOSE`). **2020-21:** reported apart, never chosen on. In S_P1 it only fits (§8.1), so
  S_P1 has no 2020-21 bet.
- **Walk-forward:** a shape, a projection's fit and P1's fit read only the seasons before the graded
  one. The floor of 300 training rows in P1 is §8.1's.
- **Settlement:** the final score, overtime counted. `spread_home` is the HOME number: home covers
  when (home - away) + spread_home > 0. A push returns the stake and leaves the denominator. One unit
  to win, risk capped at 3 (§6.2). Results are stated in units.
- **Closing-line value** is reported, never a bar, and is read through the one shape in both arms, so
  the two arms' figures share one yardstick.
- **The early-season rule:** the originals registered no 10-game filter, and none is added here.

## 9. The bars

§9.1's house standard, unchanged, applied once to every one of the 256 cells:

1. 200 or more pooled bets.
2. The pooled whole-day bootstrap 95% interval of the return is above zero (4,000 resamples, seed 7).
3. At least two graded seasons have 30 or more bets, and of those all but at most one are positive.
4. Beats the blind bet on its dominant real side, pooled.
5. The bands of section 7, and the cell's own pooled return above zero.
6. Its return on the choosing seasons beats the 95th percentile of its 200 placebo runs.

**A thin cell is still reported in full.** Under 200 pooled bets it fails bar 1, and its answer is "too
few games to tell", not "it loses" (§12.4).

## 10. The placebo: 200 runs, seeds 1 to 200

Under the null the family's opinion carries no information about this game, so **each game keeps its
own market number and its own prices, and takes another game's opinion**. The rule then runs as
usual: the same rate of bets, the same spread of EV, no game-specific information.

- **S_F2, S_F6d, S_F1, S_P1:** the family's **disagreement with the market's own number at T** moves
  between games on the same date: on a moneyline, the difference in log-odds from the market's no-vig
  chance; on a spread, the difference in points from the market's centre. It is added to the game's
  own market number and the offers re-priced through the game's own shape. S_F2 reads it toward the
  favourite, so each game keeps its own favourite and underdog. S_F6d moves it between games on the
  same date at the same book, against that book's own moneyline. S_F1 and S_P1 read it toward the home
  side.
- **S_P2:** the gap moves among the offers on the same date and side (§8.2), prices staying at the
  market's fair line.
- **This is not the original placebo for S_F2, S_F6d or S_F1.** Those moved a whole win chance or a
  whole projection, which hands a game another game's market price: a +400 underdog reading a 60%
  chance. Anything beats that, so it was no test. S_P1's and S_P2's are the originals', with more runs.
- **It must be a null on the real data, not only on made-up data.** `--smoke` prints the share of
  placebo bets that are not the real bets, per family and cut. A date holds 7.5 games on average and
  0.08% to 0.33% of a season's games are alone on theirs, so the shuffle has room (counted 2026-10-30).

### 10.1 Rule changes from the independent review, dated 2026-11-01, before any cell is graded

The review ran after §15 was written. Nothing in it read a bet's result, apart from the three final scores
§15.4 discloses. Each change below is stated before grading.

- **S_F6d's placebo now uses one shuffle of games per date, read by every book.** As first built, each book
  shuffled on its own, so one game took up to eight other games' opinions. Some book cleared the cut far more
  often than in the real rule, and the best of those was a random offer at the vig: 1,509 placebo bets against
  752 real at home .01, 2,602 against 1,357 at away .01. More bets and worse prices lower the bar, so the old
  version was easier to clear. If the other game has no number at this book, this book has no opinion in that
  run and cannot be bet. Keeping its own opinion would hand the placebo real information. The real rule also
  picks generous moneylines, about 3 points of market-fair EV better than the placebo, and this fix does not
  close that gap.
- **S_P2's placebo is not a null for information at gap 1 and above.** The first sentence of this section,
  "the same rate of bets, the same spread of EV", is false for it. Real off-number offers cluster in a game and
  lie on the favoured side; shuffled gaps scatter over more games, mostly onto offers at Pinnacle's number. A
  real gap-1 bet starts about 5 points of market-fair EV ahead of its placebo. So bar 6 carries little weight
  for S_P2 at gap 1 and above, and bars 2 and 4 do that work. The shuffle itself is unchanged: it is the
  original P2 placebo. The same sentence fails on thin S_F2 favourite cells at D, EV .05 and above: 56 real
  against 134 placebo at Pinnacle's reference.
- **S_P1 reads the home team's road-trip count as 0, in both arms and in the moneyline control.** On a
  neutral-site game the schedule's designated home team gets a road count. That count is above zero on 5 games
  of 2024-25 and 5 of 2025-26 and on no other game. Fit on those 5 rows of about 6,000, it moves every priced
  neutral-site game of 2025-26 by 9 to 20 points toward the away team, and all five are bet in all 12 S_P1 away
  cells. This corrects §15.4, which called it one game. **One of the five scores was seen** before this rule
  was written (`NBA_2026-01-18_ORL_MEM`, §15.4). The rule is about an input and is not a filter on games: all
  five stay eligible, priced without the count.
- **A pass in S_F2, S_F6d or S_F1 moneyline has one more test before it is credited to the shape.** A game
  reads the results of its whole size group, so a chance read far from the number can step at a group's edge:
  the review measured the underdog's chance falling 5 to 7 points across half a point at the 5 and 10 edges,
  while the market's moves 1 to 2. On a long underdog that is enough to choose a bet by where its line sits in
  the group. Its second checker could not finish, so this is not treated as settled, and the test below does
  not depend on it, because it can only remove a pass. For each passing cell in these families, the report
  gives the share of its bets within 0.5 of a size edge and the cell's pooled return with the same bets
  re-priced through a shape from earlier games within 1 point of that game's number (floor 300, widened until
  met), keeping only bets that still clear the cut. **If that return is not above zero with a 95% interval
  above zero, the pass is not credited to the shape.** It is computed only if such a cell passes.

## 11. Controls, and how the two runs compare

**Every registered cell is emitted twice in one run.** `control_<family>_oneshape` is the same cell
under the one shape: same quotes, same cut, same model code. Controls are graded and stored, never
judged, and carry no placebo runs.

- **This twin is the comparison, not the record's figure.** The record's cells predate the quote rule
  of section 5.4, so a gap between a twin and §6.7 or §8.4 has two possible causes: that rule, and any
  change in the cache. Comparing inside one run leaves the shape as the only difference.
- `compare_S.parquet` holds, per cell: bets under each arm, the bets in common, games only under one
  arm, games at a different offer, the units on the bets only one arm makes, and the games whose real
  side flips between the arms at that cut.
- **The two families no shape reaches** (`control_S_P2_same_number`, 64 cells;
  `control_S_P1_moneyline`, 24 cells) are graded once. A test holds that the shape cannot move their
  bets. They are controls because a pass there could not be credited to this search's idea.

## 12. Expected passes by chance, and what a pass means

- **By chance:** 256 × 0.025 ≈ **6.4** cells clear bar 2 alone, before correlation. Cells at
  neighbouring cuts share bets, so they cluster.
- **A cell that passes all six bars is built live** (CLAUDE.md §2), with its own EV floor and the
  prices it lays stated first. Reported beside it: its one-shape twin's pooled return, the units on
  the bets the shape changed, DraftKings alone, and its bets at lines over 10. **If the twin returns
  as much, the pass is credited to the family and not to the shape.**
- **A family with no passing cell stays closed.** The search then answers its own question: the
  earlier verdicts did not rest on this pricing choice.

## 13. How it runs

```
PYTHONPATH=. python -m scripts.nba_s_shapes --smoke
NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
    PYTHONPATH=. python -m scripts.nba_s_shapes --full
PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5
```

- **`--smoke`** runs the synthetic checks, then on the real cache prints counts only. It never grades
  a real bet: its timing passes run on scrambled scores. It prints the extremes, the highest-EV offers,
  the placebo-differ shares, the shape coverage, and the projected time and memory of `--full`.
- **`--full`** refuses unless `NBA_GAME2_GO=1`, `NBA_GAME2_RESULTS` and `NBA_GAME2_BETS` are set, and
  refuses a results folder holding another search's cells. It prints a progress line per group and
  writes `cells_*.parquet`, `compare_S.parquet`, the dropped quotes, and the bets.
- **Speed:** the 200 placebo runs reprice arrays built once (one grade of every offer, one sort per
  run), and a test holds that they choose the harness's bets. A real cell goes through `H.run_cells`.

**Dated 2026-10-31, after the lab's first `--smoke` and before any cell was graded.** None of this is a
rule a result could have touched; the rules above stand as written.

- **A p-value stays at 4,000 resamples here.** `H.p_one_sided` recomputes any p under 0.01 with 400,000
  resamples, for the first search's multiple-testing bar. Section 9's bars read the pooled interval and
  never a p (a test changes every p and watches the verdict not move), and the timing passes run on
  scrambled scores where no p comes under 0.01. So a real run with many strong cells would run for
  hours past its projection for a number nothing reads. `p_choose` and `p_confirm` are still stored.
- **The run reads saved projection frames.** `NBA_S_PROJ_DIR` belongs in the `--full` command above. The
  engine's rebuild was measured once at 6,468 s (hyperparameter setup 6,114 s, then the four decision
  points), with other jobs on the machine. Without the folder `--full` pays that first. A frame is used
  only if every game in it was projected at the time this run decides that game; otherwise it is
  rebuilt. So F1 stays in: the rebuild is once, and the run after it is what the 2-hour limit reads.
- **The projection's "deterministic" in section 4 was read from its code, not measured:** it holds no
  random draw outside its placebo and its made-up data. It was not rebuilt twice to compare.
- **`--smoke` prints a benchmark beside the placebo share.** A cell that bets half its games lands on one
  of them half the time by chance, so no shuffle can show a share above one minus the cell's own bet
  rate. That figure and the share of opinions left on their own game are printed with it.
- **`--smoke` checks the 256 cells from the groups it builds,** instead of at the end of a `--full`.

## 14. Not covered, so nobody reads this as closing them

Totals, because §10.7 measured no line-size shape for them. First-half and first-quarter spreads,
because no shape was measured for period lines. Team totals, which have a measured shape (§10.7) and
are not a spread or moneyline. F1b and F5, where the shape only ranks offers on one side. F3, F4 and
F6c, which read spreads the way F5 does. Each could be a later search; none is decided here.

## 15. Counts before grading

Added after the lab's first `--smoke`, dated, before any cell is graded.

**2026-10-31, `--smoke` on the research cache, started with no other python job on the machine. No cell
was graded: every timing pass read scrambled scores.**

**Re-counted 2026-11-01 after the rule changes in §10.1, again before any cell was graded.** Only S_P1's bets and
S_F6d's placebo moved. Those figures below are the new ones. The other four families' 232 per-cell bet counts match in the two
logs (`smoke2.log`, `smoke3.log`).

### 15.1 Bets per family and season

Line-size arm, at or above the -200 floor. A game counts once per cell, so these add up across cells
and the same game recurs.

| Family | Cells | Cells with 200+ pooled bets | Smallest cell | Largest cell | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 |
|---|---|---|---|---|---|---|---|---|---|---|
| S_F2 | 96 | 72 | 0 | 2,218 | 17,586 | 25,638 | 21,257 | 18,333 | 13,456 | 10,281 |
| S_F6d | 8 | 8 | 491 | 1,540 | 1,368 | 2,192 | 1,792 | 1,716 | 1,312 | 946 |
| S_F1 | 96 | 96 | 1,073 | 3,024 | 36,458 | 42,620 | 38,709 | 41,082 | 40,456 | 39,703 |
| S_P1 | 24 | 21 | 172 | 1,966 | 0 | 3,950 | 4,936 | 3,582 | 3,092 | 3,339 |
| S_P2 | 32 | 16 | 37 | 3,013 | 3,398 | 4,169 | 5,223 | 5,358 | 5,519 | 5,815 |
| Total | 256 | 213 | | | 58,810 | 78,569 | 71,917 | 70,071 | 63,835 | 60,044 |

- **43 cells are thin: "too few games to tell", whatever they show.** S_F2's favourite at EV ≥ .03 (8 cells,
  62 to 193 bets), .05 (8, 0 to 46) and .08 (8, 0 to 9); S_P1's home side at .08 (3, 172 to 174); S_P2 at a
  gap of 1.5 or 2 points (16, 37 to 93).
- **Every cell with 200+ pooled bets has at least two seasons with 30 or more,** so bar 3 can be read.
- **S_F2 leans on its earliest season.** At EV ≥ .08, 3,014 of 8,311 bets across every point are 2021-22 and
  321 are 2025-26. That is where the shape has one earlier season behind it, and the games over 10 still
  read the one shape.
- **Every decision point reaches at least 99.4% of every season's games** (D in 2021-22), so no choosing
  season is dropped at D.

### 15.2 What the shape moves, bet for bet, no result read

Summed over points, sides and references. "Same bet" is the same game, side, book, number and price.

| Family, cut | Bets, line-size | Bets, one shape | Same bet | Games only line-size | Games only one shape | Other offer |
|---|---|---|---|---|---|---|
| S_F2, EV ≥ 0 | 30,138 | 33,152 | 20,492 | 9,646 | 12,660 | 0 |
| S_F2, EV ≥ .08 | 8,311 | 5,573 | 4,398 | 3,913 | 1,175 | 0 |
| S_F6d, EV ≥ .01 | 5,735 | 6,723 | 3,247 | 2,296 | 3,284 | 192 |
| S_F1, EV ≥ 0 | 47,262 | 47,232 | 43,915 | 2,481 | 2,451 | 866 |
| S_P1, EV ≥ .02 | 8,424 | 8,713 | 7,655 | 534 | 823 | 235 |
| S_P2, gap ≥ 0.5 | 25,610 | 25,610 | 25,529 | 0 | 0 | 81 |

- **The prior in section 1 was wrong on count.** It said the shape mostly removes bets. At S_F2's top cut it
  adds them: 8,311 against 5,573.
- **S_P2 will read almost the same as its twin:** the shape moves 81 of 25,610 bets, as section 3 predicted.
- **Games whose real side flips between the arms,** summed over cuts: S_F2 2,566, S_F6d 110, S_F1 92, S_P1 1,
  S_P2 0.

### 15.3 Extremes and the numbers the rule dropped

- **After the rule, at every decision point:** spreads from -24.5 to +22.0 (the home number), spread prices
  -135 to +110, moneylines -25,000 to +3,006. A -25,000 is never laid: the floor is -200.
- **Quotes dropped at T, across the four points: 163,** against 412,894 kept at Pinnacle and the deciding books.
  By season: 2020-21 40, 2021-22 31, 2022-23 34, 2023-24 12, 2024-25 20, 2025-26 26. By book: Bovada 84,
  Pinnacle 44, BetMGM 14, FanDuel 12, BetRivers 4, DraftKings 2, Caesars 2, Fanatics 1. Bovada is never a
  deciding price.
- **Closes dropped from the shapes: 30,** 17 of them spreads.
- **Over-10 lines in 2021-22 and 2022-23 read the one shape,** as section 5.1 said: 114 and 299 earlier games.

### 15.4 The highest-EV offers, read one at a time

The rule catches a broken quote, not a strong opinion. Every offer below stays in, in both arms.

- **S_F1:** the home team at +810 (`NBA_2026-04-10_PHI_IND`, 47.9%) and +560 (`NBA_2026-04-12_ORL_BOS`, 58.5%),
  EV 3.4 and 2.9. Six books hang the first game's price, +700 to +810. Both are the last week of the season, and
  the projection is more than 30 points of win chance from the price.
- **S_F2 and S_F6d:** underdogs at +430 to +1,300 with EV .44 to .60, all in 2020-21 and 2021-22. The same 26.7%
  appears on seven of these games: one number in one season reads one chance.
- **S_P2:** EV up to .16, ordinary spread prices of -105 to -112.
- **S_P1 after §10.1's rule:** the top offers are ordinary, EV .24 to .28 on `NBA_2022-04-06_OKC_UTA`,
  `NBA_2025-12-26_CHA_ORL` and `NBA_2022-03-10_GSW_DEN`, at prices of -114 to +100. No neutral-site game is on the list.
- **S_P1, corrected 2026-11-01: this was not one game, and it is now fixed by rule (§10.1).** As first written:
  one game is an input fault, flagged and not fixed here. `NBA_2026-01-18_ORL_MEM`, the London game,
  reads 92.6% for the away team at the home number +4.5, EV .83. The input that stands out on it is the home
  team's road-trip count, 29 standard deviations from the average game. It is above zero on 5 games in 2024-25
  and 5 in 2025-26, the same counts as the schedule's neutral-site games, so P1's 2025-26 fit has at most five
  rows of it. How much of the 92.6% it causes was not broken down. The game stays: nothing but the rule of
  section 5.4 is filtered, it is the same in both arms, and the next line closes the question.
- **Disclosure, 2026-10-31.** Looking at why these games top the list, a schedule row was printed whole, final
  score included, for those three games (`NBA_2026-01-18_ORL_MEM`, `NBA_2026-04-10_PHI_IND`,
  `NBA_2026-04-12_ORL_BOS`). No cell was graded and no rule, cut or filter changed after it. That is why the
  London game is not filtered now: a filter written after seeing its result would not be a rule made first.

### 15.5 The placebo on the real data

Seeds 1 to 5, every cell, weighted by placebo bets.

| Family | Bets on another game than the real bet's | That share if the shuffle had no tie to the real bets | Bets at another offer | Opinions left on their own game |
|---|---|---|---|---|
| S_F1 | 0.475 | 0.585 | 0.485 | 0.131 |
| S_F2 | 0.532 | 0.732 | 0.532 | 0.134 |
| S_F6d | 0.619 | 0.768 | 0.824 | 0.131 |
| S_P1 | 0.636 | 0.812 | 0.642 | 0.131 |
| S_P2 | 0.538 | 0.603 | 0.871 | 0.022 |

- **The shuffle moves.** About 13% of opinions stay on their own game, one in the 7.5 a date holds. S_P2's gaps
  move among more offers, so 2% stay. The fault of the earlier searches, candidates alone on their date, is
  not here.
- **The share cannot be high where a cell bets most games.** At EV ≥ 0, S_F1 bets about 80% of games on one side
  or the other, so a placebo bet lands on a real bet's game near half the time by chance.
- **Placebo bets land on real bets' games 7 to 20 points more than chance.** Each game keeps its own prices, by
  design, and why it runs this high was not broken down. A shared bet settles the same in both, so this
  narrows what the bar can see. It makes bar 6 harder to clear, not easier.
- **By cut:** the lowest share is S_F1 at EV ≥ 0, 0.429; the highest is S_P2 at gap ≥ 2, 0.864.
- **S_F6d's placebo now bets close to the real rule's rate.** All points, seeds 1 to 5: 5,735 real against 6,598 per
  run at EV ≥ .01, and 3,591 against 4,337 at .03. As first built it was 12,124 and 8,703 (§10.1).

### 15.6 How long `--full` takes

The table is the 2026-10-31 run, one placebo run on every group 1.17 s, peak memory 2.93 GB. The 2026-11-01 re-count
projects 2,526 s, 0.70 hours, peak memory 2.95 GB.

| Stage | Seconds |
|---|---|
| Synthetic checks, load, shapes, inputs, saved projections | 35.6 + 22.4 + 112.0 + 9.9 + 0.4 |
| Groups at the four points | 767.3 |
| 200 placebo runs, all groups | 243.9 |
| 256 registered cells, with bands | 606.6 |
| 256 one-shape twins | 421.7 |
| Compare tables | 69.1 |
| 88 controls | 112.5 |
| **Total, with the saved projections** | **2,401 s, 0.67 hours** |

- **Not counted:** writing the parquet files. A 200-run pass on made-up games wrote them after every group and
  finished in 677 s, with coarser tables.
- **With no saved projections,** add the 6,468 s rebuild measured once with other jobs running: about 2.46 hours.
  F1 and P1 need it. The frames at decision points A to D are on disk and were checked against this run's
  decision times: every game matches.
- **The first `--smoke` projected 3.2 hours, and that figure was wrong.** It charged each group's once-only work to
  every cell, and three of this search's own test jobs overlapped its last minutes.

### 15.7 The tests

- **62 tests pass, 2026-11-01.** The three added for §10.1 each failed with its rule broken: one shuffle per date,
  no opinion when the other game has no number at this book, and the road-trip count read as 0.
- **59 tests passed, 2026-10-31.** 58 rule-breaks were each applied once to a scratch copy of the final lab and its
  named test run: all 58 failed it. A `.env`-free copy, no real data.
- **Four tests did not fail the first time, and were rewritten until they did:**
  - The ban on Pinnacle as a deciding price: Pinnacle's offer only tied a deciding book's, and a tie never reaches it.
  - The quotes for "still offered at the next fetch": at C the next fetch is the made-up world's last, so first and
    last could not be told apart.
  - "No bar reads a p": every made-up cell was under the first bar, so a bar reading a p could not show.
  - "Every family has bands": it asked for a band anywhere, so a family with none passed.

- **`--full` was run end to end on made-up games,** every line a real run takes: 256 registered cells, 256 twins, 88
  controls, 200 placebo runs per cell, every table written, then the verdict over them. 4 cells passed there, all
  S_F2 underdogs at C and D, where that world misprices underdogs on purpose.


## 16. Results (graded 2026-11-02)

Run `2026-11-02-shapes`, stored in Supabase: 256 cells, 256 one-shape twins and 88 controls. The grade took 2,425
seconds.

**0 of the 256 cells pass. The families stay closed, and the question this search asked has its answer: the earlier
moneyline and spread verdicts did not rest on the pricing choice.** Two cells clear the 95% interval, each on 3 bets.
213 cells hold 200+ bets, with a median return of -1.0% and 79 positive.

| Family | Market | Cells with 200+ bets | Median return, line-size shape | Median return, one shape | Better under the line-size shape | Best return |
|---|---|---|---|---|---|---|
| S_F2 | Moneyline | 72 | +2.86% | -2.14% | 56 | +9.75% |
| S_F6d | Moneyline | 8 | +2.39% | -0.05% | 7 | +5.41% |
| S_F1 | Moneyline | 48 | -1.30% | -1.44% | 27 | +3.58% |
| S_F1 | Spread | 48 | -3.11% | -3.39% | 22 | +0.58% |
| S_P1 | Spread | 21 | -0.14% | 0.00% | 10 | +5.24% |
| S_P2 | Spread | 16 | -1.50% | -1.51% | 10 | +3.46% |

- **The nearest miss by units is S_F2's underdog at Pinnacle's reference, EV .02, decision point D:** 1,711 bets,
  +38.44 units, +6.8%, interval -1.9% to +15.4%, 3 of 5 seasons positive. It fails the interval, the seasons and the
  bands. Its twin at the same cut made 1,148 bets, +0.75 units, +0.3%.
- **The shape does change who a long underdog looks like, and that is the only family it moves.** Summed over S_F2's
  cells, the bets only the line-size shape makes earn +607.0 units, and the bets only the one shape makes lose
  2,214.3. Those totals repeat games across cells, so they are not a record. On spreads the shape moves almost
  nothing: S_P2's two arms are within 0.01 points, as section 3 predicted.
- **This does not rescue the underdog.** Section 10.1 registered a further test for any moneyline pass, because a game
  reads the results of its whole size group and the chance steps at a group's edge. No moneyline cell passed, so the
  test was not run. The gap between the arms on S_F2 may be that step and is not evidence of a better model.
- **S_P1 after the road-trip rule:** the best is the home side at decision point A, EV .02: 914 bets, +46.75 units,
  +4.7%, interval -1.5% to +10.9%, failing the interval, the seasons, the bands and the placebo.
- **The two families no shape reaches, controls and never judged:** the same-number rule has a median return of +0.1%
  (the one high figure is a thin cell), and P1's moneyline -3.2%.

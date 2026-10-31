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
| F1b 48, F5 36 | **Hardly.** They cut on a gap in points; the shape only ranks offers on one side, and 90% of spread quotes sit at Pinnacle's number (measured, section 5) | not re-graded |
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

## 14. Not covered, so nobody reads this as closing them

Totals, because §10.7 measured no line-size shape for them. First-half and first-quarter spreads,
because no shape was measured for period lines. Team totals, which have a measured shape (§10.7) and
are not a spread or moneyline. F1b and F5, where the shape only ranks offers on one side. Each could
be a later search; none is decided here.

## 15. Counts before grading

Added after the lab's first `--smoke`, dated, before any cell is graded.

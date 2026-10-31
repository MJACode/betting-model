# NBA search: moneyline favourites shorter than -200 (pre-registered 2026-10-31, before any cell was graded)

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find
it"*.

**The gap.** Every NBA moneyline cell in every search used the -200 price floor (the record,
`docs/nba_models_2026.md`, 6.2 rule 1, and its sections 8 to 12). So a favourite shorter than -200
has never been graded on its own, by price. Those favourites are not rare: at the best deciding
price, 60-180 minutes before tip, they are 48% to 59% of a season's games (section 9).

**Why it could work.** Moskowitz and Vasudevan studied 36,609 US basketball and football games.
They find the favourite-longshot pattern in moneylines and not in spreads: for the stronger
teams, the moneyline loses less than the spread. So for a heavy favourite the moneyline may be
the cheaper contract, and the floor shut it out. This reaches the record through the sweep's
critic (`%TEMP%/nba_missing_result.json`, citing Karl Whelan's slides,
https://www.karlwhelan.com/Teaching/BettingMarkets/13.PointSpreadsandAsianHandicap.pdf). The
paper itself was not read for this search. The control in section 7 tests the claim on these
games.

**What earlier searches did and did not cover.**

- The first search's market rules (record 4.1) bet at -200 or better and reported how many bets
  the floor removed. Its blind bets had no floor (`blind_bets` in
  `scripts/nba_game_market_lab.py`) but put every price into one number, never split by price.
- The spread against the moneyline (F2, record 6.3), the market-anchored model (P1, record 8.1)
  and the same-number rule (P2, record 8.2) all bet moneylines at -200 or better. The only
  favourites those cells could bet were priced -200 or better.
- Nothing has graded favourites by price band, or either rule on favourites shorter than -200.

**Written before any cell was graded. Nothing below changes after a result is seen; a later
change gets its own dated line and reason.** Lab: `scripts/nba_s_fav200.py`. Pass/fail:
`python -m scripts.nba_game2_verdict --results <folder> --house5` (record 9.1's bars). Nothing is
bought. This document does not edit `docs/nba_models_2026.md`.

---

## 1. Data

- **Full-game moneylines:** `odds`, `source = 'odds_api_historical'`, 2020-21 to 2025-26, read
  from the research cache (`scripts/nba_research_cache.py`; every row is in Supabase). The
  injury-report purchase of the seventh search is left out, as `H.load` leaves it out by default,
  so a grade does not depend on when the cache was refreshed.
- **Full-game spreads:** the same table. Read only by the spread control in section 7.
- **The market-anchored model's inputs:** exactly record 8.1's: box scores, adjusted plus-minus
  from lineup segments, the injury report, schedule, shooting luck.
- **Results:** final scores in `games`, overtime counted, as every earlier full-game market.

---

## 2. Definitions

Everything not named here is record 6.2's rule, in the shared harness
(`scripts/nba_game_harness.py`).

- **Decision points.** A: the 15Z fetch on the game date. B: the newest fetch 180-360 minutes
  before tip. C: the newest 60-180. D: the newest 45-75. The market-anchored model uses A, C, D,
  and the other two families use A, B, C, D, as those families always did. **C and D are mostly
  the same fetch:** 3,474 and 3,471 games are in range at C and D, counted from the same prices.
  So the C and D cells are close to one cell written twice, and they must not be read as two
  confirmations of each other.
- **Deciding books.** `config.BEST_LINE_BOOKMAKERS`: eight books. Pinnacle and Bovada never
  decide.
- **The favourite.** The side above 50% in the market's own fair line at the decision time
  (`H.fav_sides`): Pinnacle's no-vig home price where Pinnacle quotes, else the deciding books'
  median. It is never read from a result and never from the model. **Every judged bet is on the
  favourite.** That side is a per-game side (`side_pick`), so a favourite can be home or away.
  The home/away split is reported beside each cell.
- **A game's price.** The best price the cell itself would take at the decision time: for the
  blind bet, the best deciding offer; for the same-number rule, the best deciding offer in
  Pinnacle's own fetch; for the market-anchored model, the best deciding offer.
- **The price range decides on that one offer.** A game enters a cell only when that best offer
  falls in the cell's range. A game with one book at -190 and another at -205 is **not** bet at
  -205. Nobody would take -205 there, and at -190 the game already sat inside every earlier
  search.

**The bands** (`lo <= price < hi`, American odds):

| Band | Range | Note |
|---|---|---|
| band below (bar 5 only) | -200 <= price < -150 | -200 itself sits here: the earlier floor allowed it |
| -200 to -300 | -300 <= price < -200 | -300 belongs to this band |
| -300 to -500 | -500 <= price < -300 | -500 belongs to this band |
| shorter than -500 | price < -500 | no floor on this band; see below |

**The floors.** The blind cells have no price floor: "shorter than -500" has no end. The
same-number rule and the market-anchored model are floored at -1000. Their range is
-1000 <= price < -200. Every blind cell's bets are split at -1000 in the report (section 8), so
the part a -1000 floor would keep can be read without another run.

**Impossible numbers (written before the first count of this search was taken).**

1. A price between -100 and +100 is not an American price. The quote is dropped.
2. A quote whose two implied chances sum outside 1.00-1.15 is out (the harness's `coherent` rule).
3. **A quote whose no-vig chance is more than 0.15 from the median of its own fetch is dropped,
   whichever book it is, Pinnacle included**, when four or more books quote the game in that
   fetch. Fewer than four: it cannot be judged and is kept.
   - This catches a swapped row: at any price in range, the favourite's no-vig chance is above
     0.60, so a swapped quote sits more than 0.20 from the median.
   - It covers Pinnacle because Pinnacle sets the same-number rule's fair chance. One bad Pinnacle
     quote would make every soft book look wrong.
   - A real stale price is not touched unless it is more than 15 points of chance away.
4. A spread (control only) more than 3 points from the median number of its own fetch, on four or
   more books, is dropped.

Very short prices are not impossible: -25,000 is a stored Caesars quote on a 2025-26 game the
other books also price as a mismatch. They stay. `--smoke` prints the extremes of every price and
line, and the highest-EV offers, and every row these rules drop.

**What the one-unit-to-win rule with risk capped at 3 does** (`H.risk_win`):

| Price | Risk | A win pays | Break-even win rate | Without the cap, risk would be |
|---|---|---|---|---|
| -200 | 2.00 | 1.00 | 66.7% | 2.00 |
| -250 | 2.50 | 1.00 | 71.4% | 2.50 |
| -300 | 3.00 | 1.00 | 75.0% | 3.00 |
| -400 | 3.00 | 0.75 | 80.0% | 4.00 |
| -500 | 3.00 | 0.60 | 83.3% | 5.00 |
| -700 | 3.00 | 0.43 | 87.5% | 7.00 |
| -1000 | 3.00 | 0.30 | 90.9% | 10.00 |
| -2000 | 3.00 | 0.15 | 95.2% | 20.00 |

- At -300 or shorter the cap sets the stake: every such bet risks 3 units and wins less than 1. One
  loss at -1000 costs ten wins.
- The return on one bet does not change. Win and loss scale together, and the break-even rate is
  the same.
- The pooled return does change, because it is a weighted average of the bets. The cap gives every
  bet at -300 or shorter the same weight, where one unit to win would give a -1000 bet 3.3 times
  the weight of a -300 bet. So the shortest favourites count for less than a true to-win-one card.
  The return with no cap is reported beside every cell, so this can be read on the graded numbers.
- A short price wins small amounts on a large risk. +5% on 1,000 bets at -500 is +150 units on
  3,000 risked.

**How much an interval can tell.** With win rate at break-even, the standard deviation per unit
risked at decimal price d is d x sqrt((1/d)(1 - 1/d)). The 95% half-width of the return, before
any day-to-day correlation:

| Price | 200 bets | 500 bets | 1,000 bets | 2,000 bets |
|---|---|---|---|---|
| -250 | 8.8% | 5.5% | 3.9% | 2.8% |
| -400 | 6.9% | 4.4% | 3.1% | 2.2% |
| -700 | 5.2% | 3.3% | 2.3% | 1.7% |
| -1000 | 4.4% | 2.8% | 2.0% | 1.4% |

---

## 3. The cells (40)

| Family | What it bets | Decision | Cut | Cells |
|---|---|---|---|---|
| FAVB | the favourite at its best deciding price, no model and no rule | A, B, C, D | three price bands | 12 |
| FAVP2 | the same-number rule, record 8.2: a deciding book in Pinnacle's fetch, Pinnacle's proportional no-vig chance x the book's decimal price - 1 | A, B, C, D | EV >= 0.00 / 0.01 / 0.02 / 0.03 | 16 |
| FAVP1 | the market-anchored model, record 8.1: the market's no-vig log-odds as an unpenalised offset, moved by the same inputs, unchanged | A, C, D | EV >= 0.02 / 0.04 / 0.06 / 0.08 | 12 |
| **Total** | | | | **40** |

- **The two rules are not rewritten.** The same-number rule is `sharp_pairs` and P2's quote rules
  (`scripts/nba_game4_p2.py`), imported. The model is P1's own code (`scripts/nba_game4_p1.py`):
  its inputs, walk-forward, penalty and fair line, imported.
- **The model is trained on every game at its decision point, at every price**, from seasons
  before the graded one, as in record 8.1. The floor and the range govern which bets are placed,
  not what the model learns. Its moves are built as in the fourth search, apart from the quotes
  section 2 drops.
- **A cut chooses the same offer as ever.** On a moneyline, EV rises with the price at one fair
  chance, so the best-EV offer is the best price, and the band rule above is read on the offer the
  rule actually takes.
- **The underdog is not a candidate.** Every underdog in these games was inside the earlier
  floor. It is a control.

### The same-number rule will be thin, and that is stated now

Counted from prices alone before this was written (no result read; `--smoke` repeats it). Pinnacle's
proportional no-vig gives a favourite a low chance, so the rule rarely fires:

| Decision | Games in range | EV >= 0.00 | 0.01 | 0.02 | 0.03 |
|---|---|---|---|---|---|
| A | 3,083 | 26 | 5 | 2 | 1 |
| B | 3,545 | 19 | 7 | 2 | 1 |
| C | 3,474 | 50 | 13 | 9 | 8 |
| D | 3,471 | 50 | 13 | 9 | 8 |

Those counts are over six seasons, with 2020-21 included. **Every FAVP2 cell is below the 200-bet
bar before a single bet is graded.** Its answer will be "too few games to tell", not "it loses".
It is graded and printed in full anyway.

---

## 4. Bands (bar 5)

Record 9.1's text is applied as written: the band just below the cell's cut and every band from
its cut to the top each have a positive pooled return, where they hold 30 or more bets, and the
cell's own pooled return is above zero.

- **FAVB:** the bands of section 2, in order of price. The -200 to -300 cell reads -200 to -150,
  its own band, -300 to -500, and shorter than -500. The -300 to -500 cell reads -200 to -300, its
  own, and shorter than -500. The shorter-than-500 cell reads -300 to -500 and its own.
- **FAVP2:** along EV, as nested cuts make bands (record 9.1). The lowest cut's lower band starts
  at -0.01. The top band is open.
- **FAVP1:** along EV. The lowest cut's lower band starts at 0, record 9.1's rule. The top band is
  open.

---

## 5. Seasons and settlement

- **FAVB and FAVP2:** 2021-22 to 2025-26 graded and pooled. 2021-22 to 2024-25 are the choosing
  seasons the placebo reads. 2020-21 is reported apart and never chosen or pooled (record 6.1: its
  own regime).
- **FAVP1:** 2021-22 to 2025-26 graded and pooled, the same choosing seasons. 2020-21 only fits, as
  no earlier priced season exists.
- **D's gate:** a choosing season reached on fewer than 95% of its games at D is reported and not
  chosen on (the harness's rule).
- **Settlement:** the full game's winner on the final score, overtime counted. An NBA game has no
  draw. A row's line is blank; the moneyline has no number.
- **Units:** one unit to win, risk capped at 3 (`H.risk_win`). Reported in units, never dollars.

---

## 6. The bars, and how a thin cell reads

Record 9.1's house standard, unchanged:

1. 200 or more pooled bets.
2. The pooled whole-day bootstrap 95% interval of the return is above zero (4,000 resamples, seed
   7).
3. At least two graded seasons with 30 or more bets, and of those all but at most one positive.
4. Beats the blind bet on its dominant real side, pooled.
   - **FAVB:** the blind favourite on **every game at that point, at any price**. The band's own
     bets cannot be their own comparison, so a band has to beat favourites at large.
   - **FAVP2, FAVP1:** the favourite on every game in the cell's own range and population, no cut.
     FAVP2 reads the same offers as the rule; FAVP1 reads every deciding offer.
   - Bar 4's home and away reading applies where one real side is over 70% of the cell.
5. Bands, as section 4.
6. Beats the 95th percentile of 200 placebo runs on its choosing seasons (section 7).

Closing-line value is reported, never a bar. DraftKings alone is reported beside every cell.

**A thin cell is still reported.** Under 200 pooled bets it fails bar 1, and its bets, units,
return, interval and season split are printed anyway. Its answer is "too few games to tell", not
"it loses" (the 9.9 F8 reading).

**Expected passes by chance:** 40 x 0.025 = 1.0 cell clears bar 2 alone, before correlation, and
the C and D cells are close to duplicates. Bars 3 to 6 make a chance pass rarer still.

**A pass is built live (CLAUDE.md section 2) with its own EV floor.** The -200 floor is a house
rule (`config.DEFAULT_MIN_ODDS`), so the prices a passing cell lays are stated to mike before it
ships.

---

## 7. The placebo and the controls

**Placebo: 200 runs, seeds 1-200.** One rule for all three families: **each game's signal moves
to another game in the same pool in the same calendar week (ISO week), by one permutation per
run. Its price, its favourite and its result stay with the game.** So a run bets the same number
of games in each week, chosen at random.

| Family | The signal | The pool | A run bets |
|---|---|---|---|
| FAVB | "in this band" | every favourite with a deciding offer at that point, any price | the same count of other favourites, at their own prices |
| FAVP2 | the game's best offer's EV; every offer keeps its gap to that best offer | the games in the cell's range | the same count of in-range favourites |
| FAVP1 | the model's move off the market, in log-odds toward the favourite, added to the game's own market number and re-priced at its own offers | the games in range with a model number | about the same count of in-range favourites |

**Why not "same date" as the records have it.** A placebo that repeats the real bets cannot be
beaten, so it is not a null. Counted from prices alone before this was written: of the games in
each band, the share alone in that band on their date is 21-22% for -200 to -300, 25-27% for -300
to -500, 39-40% for -500 to -1000, and 57-62% shorter than -1000. Inside a band, a same-date
shuffle hands those games their own signal back. A wider pool on the date (every game) fixes
that but changes the bet rate: an edge or a move from a near-even game lands on a short favourite,
and near-even games have a different spread of EV. So: the cell's own pool, over a whole week.

**The check on real data.** `--smoke` prints, per cell on the real prices, the share of placebo
bets that are not real bets of that cell, and the same share under a same-date shuffle beside it.
A cell under 50% with 30 or more real bets is named in section 9.

**Controls, graded and reported, never judged, and not counted in the 40:**

- **`control_FAVB_dog`** (12 cells): the underdog in the same games, each band and point, at its
  best deciding price. Betting both sides of the same games measures the price of the bet.
- **`control_FAVB_spread`** (12 cells): the favourite's full-game spread in the same games, each
  band and point. The stored number is the HOME number, so an away favourite at -5.5 is stored as
  +5.5. Priced by the market's fair line (`H.market_fair`) through results around Pinnacle's close
  on earlier seasons. This is the sweep's mechanism on these games: does the moneyline lose less
  than the spread?
- **`control_FAVP2_power`** (16 cells): the same-number rule with Pinnacle's chance taken by the
  power method (`fair_pow` in `sharp_pairs`), not the proportional one. Record 8.2 registered the
  proportional method and this search keeps that as the judged cell. The power method moves a short
  favourite's chance up (-400/+310: 76.6% to 78.5%; -1000/+650: 87.2% to 89.8%), and it fires eight
  to sixteen times as often at EV >= 0 (424 against 50 games at C, six seasons). So it is printed,
  because the judged cells cannot reach the 200-bet bar, and it cannot pass.

---

## 8. Reported beside every cell, not bars

- the bets' lowest, median and highest price;
- bets and return per price band (-200 to -300, -300 to -500, -500 to -1000, shorter than -1000);
- bets and return when the favourite is home, and when it is away;
- the return with no cap (one unit to win at every price);
- bets in either team's first 10 games (CLAUDE.md section 3 is not applied as a filter, as in
  record 8.1);
- closing-line value, DraftKings alone, and the share still offered at the next fetch;
- **without a lone best price:** units without bets whose best price beats the next deciding book
  by more than 2 points of implied chance. The harness's 20-cent outlier test is also written, but
  it misreads a short price: -400 against -420 is 20 cents and 0.8 of a point of chance.

---

## 9. Counts before grading

Added after the first `--smoke`, dated, before any cell is graded.

---

## 10. What the lab writes

`--smoke`: synthetic checks, then counts on the real cache. It computes no result of any bet: every
grade inside it reads scores replaced by random numbers. It prints the extremes and highest-EV
offers, every dropped row, each cell's bets by season, the placebo's differing share, and the time
of one placebo run on the real data with the projected total.

`--full` refuses unless `NBA_GAME2_GO=1`, `NBA_GAME2_RESULTS` and `NBA_GAME2_BETS` are set. It prints
progress lines and writes `cells_FAVB.parquet`, `cells_FAVP2.parquet`, `cells_FAVP1.parquet`, one
`cells_control_*.parquet` per control, `population_FAV.parquet`, `fits_FAVP1.json` and each family's
bets. `python -m scripts.nba_game2_verdict --results <folder> --house5` then judges the 40.

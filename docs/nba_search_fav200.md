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

Added 2026-10-31, before any cell is graded. **No rule above changed.** Every number here is read from
prices, or from the model's chance on seasons after its fit. `--smoke` read no result of any bet: each
grade inside it reads scores replaced by random numbers, and a guard stops the run if a grade is handed
real ones. Source: `--smoke` on the research cache, commit 8178c5e3.

### 9.1 What can reach the 200-bet bar

- **FAVB: all 12 cells can.** Their pooled counts run 951 to 1,334.
- **FAVP2: none can.** The largest pooled count is 40.
- **FAVP1: none can.** The largest pooled count is 141, at EV >= 0.02.

So 28 of the 40 cells will read "too few games to tell", whatever their return. Only the blind bands can
pass. Section 6's chance figure was for all 40. For the 12 that can reach the bar it is
12 x 0.025 = 0.3 cells clearing bar 2 by chance, before correlation.

### 9.2 Bets by cell and season

Pooled is 2021-22 to 2025-26. 2020-21 is apart and never pooled. These are the bets each cell would place,
from prices alone.

**FAVB, the favourite by price band**

| Decision | Cell | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 | **Pooled** |
|---|---|---|---|---|---|---|---|---|
| A | -200 to -300 | 213 | 256 | 300 | 242 | 270 | 266 | **1,334** |
| A | -300 to -500 | 190 | 197 | 188 | 204 | 229 | 206 | **1,024** |
| A | shorter than -500 | 116 | 176 | 97 | 209 | 221 | 248 | **951** |
| B | -200 to -300 | 225 | 244 | 284 | 232 | 280 | 244 | **1,284** |
| B | -300 to -500 | 187 | 197 | 208 | 228 | 220 | 223 | **1,076** |
| B | shorter than -500 | 117 | 178 | 104 | 206 | 228 | 245 | **961** |
| C | -200 to -300 | 212 | 246 | 278 | 238 | 275 | 244 | **1,281** |
| C | -300 to -500 | 186 | 204 | 193 | 216 | 216 | 227 | **1,056** |
| C | shorter than -500 | 123 | 177 | 113 | 208 | 229 | 244 | **971** |
| D | -200 to -300 | 212 | 246 | 278 | 238 | 275 | 244 | **1,281** |
| D | -300 to -500 | 185 | 204 | 193 | 216 | 217 | 227 | **1,057** |
| D | shorter than -500 | 122 | 176 | 113 | 208 | 228 | 244 | **969** |

**FAVP2, the same-number rule**

| Decision | Cell | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 | **Pooled** |
|---|---|---|---|---|---|---|---|---|
| A | EV >= 0.00 | 3 | 2 | 3 | 2 | 10 | 6 | **23** |
| A | EV >= 0.01 | 0 | 1 | 1 | 0 | 2 | 1 | **5** |
| A | EV >= 0.02 | 0 | 1 | 0 | 0 | 0 | 1 | **2** |
| A | EV >= 0.03 | 0 | 0 | 0 | 0 | 0 | 1 | **1** |
| B | EV >= 0.00 | 9 | 4 | 0 | 2 | 3 | 1 | **10** |
| B | EV >= 0.01 | 5 | 0 | 0 | 1 | 1 | 0 | **2** |
| B | EV >= 0.02 | 0 | 0 | 0 | 1 | 1 | 0 | **2** |
| B | EV >= 0.03 | 0 | 0 | 0 | 0 | 1 | 0 | **1** |
| C | EV >= 0.00 | 10 | 17 | 4 | 6 | 9 | 4 | **40** |
| C | EV >= 0.01 | 2 | 5 | 1 | 2 | 2 | 1 | **11** |
| C | EV >= 0.02 | 2 | 3 | 1 | 1 | 2 | 0 | **7** |
| C | EV >= 0.03 | 2 | 2 | 1 | 1 | 2 | 0 | **6** |
| D | EV >= 0.00 | 10 | 17 | 4 | 6 | 9 | 4 | **40** |
| D | EV >= 0.01 | 2 | 5 | 1 | 2 | 2 | 1 | **11** |
| D | EV >= 0.02 | 2 | 3 | 1 | 1 | 2 | 0 | **7** |
| D | EV >= 0.03 | 2 | 2 | 1 | 1 | 2 | 0 | **6** |

**FAVP1, the market-anchored model** (2020-21 only fits, so it holds no bets)

| Decision | Cell | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 | **Pooled** |
|---|---|---|---|---|---|---|---|---|
| A | EV >= 0.02 | 0 | 46 | 20 | 24 | 32 | 17 | **139** |
| A | EV >= 0.04 | 0 | 19 | 6 | 6 | 8 | 6 | **45** |
| A | EV >= 0.06 | 0 | 3 | 4 | 2 | 0 | 0 | **9** |
| A | EV >= 0.08 | 0 | 3 | 1 | 0 | 0 | 0 | **4** |
| C | EV >= 0.02 | 0 | 60 | 20 | 19 | 28 | 14 | **141** |
| C | EV >= 0.04 | 0 | 23 | 10 | 3 | 6 | 4 | **46** |
| C | EV >= 0.06 | 0 | 8 | 3 | 1 | 0 | 0 | **12** |
| C | EV >= 0.08 | 0 | 4 | 2 | 1 | 0 | 0 | **7** |
| D | EV >= 0.02 | 0 | 59 | 19 | 18 | 27 | 14 | **137** |
| D | EV >= 0.04 | 0 | 25 | 9 | 2 | 6 | 4 | **46** |
| D | EV >= 0.06 | 0 | 8 | 3 | 1 | 0 | 0 | **12** |
| D | EV >= 0.08 | 0 | 4 | 2 | 1 | 0 | 0 | **7** |

**`control_FAVB_dog` and `control_FAVB_spread`:** the same games as FAVB in every cell and season, so the same
counts. The script that wrote this table checks that row by row.

**`control_FAVP2_power`, the same-number rule at the power method's chance**

| Decision | Cell | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 | **Pooled** |
|---|---|---|---|---|---|---|---|---|
| A | EV >= 0.00 | 57 | 25 | 40 | 37 | 99 | 54 | **255** |
| A | EV >= 0.01 | 14 | 4 | 5 | 12 | 25 | 11 | **57** |
| A | EV >= 0.02 | 2 | 1 | 2 | 0 | 4 | 1 | **8** |
| A | EV >= 0.03 | 0 | 1 | 1 | 0 | 2 | 1 | **5** |
| B | EV >= 0.00 | 63 | 52 | 33 | 50 | 76 | 40 | **251** |
| B | EV >= 0.01 | 22 | 11 | 5 | 9 | 15 | 4 | **44** |
| B | EV >= 0.02 | 10 | 3 | 0 | 2 | 3 | 0 | **8** |
| B | EV >= 0.03 | 3 | 0 | 0 | 2 | 1 | 0 | **3** |
| C | EV >= 0.00 | 71 | 94 | 41 | 61 | 110 | 47 | **353** |
| C | EV >= 0.01 | 21 | 27 | 9 | 13 | 26 | 11 | **86** |
| C | EV >= 0.02 | 4 | 10 | 2 | 4 | 5 | 2 | **23** |
| C | EV >= 0.03 | 2 | 4 | 1 | 1 | 2 | 0 | **8** |
| D | EV >= 0.00 | 71 | 94 | 41 | 61 | 111 | 47 | **354** |
| D | EV >= 0.01 | 21 | 27 | 9 | 13 | 26 | 11 | **86** |
| D | EV >= 0.02 | 4 | 10 | 2 | 4 | 5 | 2 | **23** |
| D | EV >= 0.03 | 2 | 4 | 1 | 1 | 2 | 0 | **8** |

**How common these favourites are.** The share of a season's games whose favourite's best price at C is shorter
than -200 (the three FAVB bands over the season's stored games):

| 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 |
|---|---|---|---|---|---|
| 48.2% | 51.0% | 47.5% | 53.8% | 58.5% | 58.1% |

The opening paragraph's "48% to 59%" is 47.5% to 58.5% on these counts. It was rounded by hand; this is the measured figure.

### 9.3 Extremes, and what the rules on impossible numbers dropped

Every book, every fetch, after the drops. Prices are American odds. The spread is the HOME number.

| Season | Moneyline shortest | Moneyline longest | Spread lowest | Spread highest | Spread price shortest | Spread price longest |
|---|---|---|---|---|---|---|
| 2020-21 | -5,000 | +1,641 | -19.0 | +16.0 | -130 | +105 |
| 2021-22 | -10,000 | +1,730 | -20.5 | +19.0 | -169 | +150 |
| 2022-23 | -5,000 | +1,400 | -19.5 | +18.5 | -125 | +108 |
| 2023-24 | -10,000 | +1,607 | -20.0 | +18.5 | -135 | +114 |
| 2024-25 | -10,000 | +2,800 | -23.5 | +18.5 | -130 | +105 |
| 2025-26 | -25,000 | +3,283 | -24.5 | +22.0 | -138 | +114 |

- **Stored rows the harness loaded:** 2,733,316 on 7,230 games, every season fully priced. Moneylines and spreads
  only, after the drops and one number per fetch: 880,079 moneyline and 881,409 spread quotes.
- **Moneyline rows dropped by the fetch-median rule:** 22, in 15 games. By book: bovada 11, pinnacle 5, betmgm 3, fanduel 2, hardrockbet 1.
  None of them is a price between -100 and +100; each is a real price far from its fetch.
- **Spread rows dropped by the 3-point rule:** 149, in 88 games. The spread control is the only reader.
- **The two-chances rule:** 1 moneyline quote fails it.
- **What the fetch-median rule cannot judge:** 56,831 moneyline quotes (6.5%) sit in a fetch of fewer than four
  books. No FAVB game is decided at such a fetch, at any point: each game in the three bands has four or more books
  at its decision.
- **The prices a band actually takes.** The stored -25,000 is one book's quote, not a best price. The best prices
  taken, at every point: -300 to -204 in the first band, -500 to -303 in the second. In the third: -5,000 to -510, median
  -769, with 234 to 254 of its games shorter than -1000. Section 8's split at -1000 reads those.
- **One odd spread.** Of 881,409 spread quotes, one is priced outside -140 to +120: DraftKings at -3.5, +150/-169,
  on NBA_2022-02-16_WAS_IND, with the other books between 0.0 and -1.5. It is inside the 3-point rule, so it is kept.
  Only the spread control reads it.

**The highest-EV offers, at C**, on games shorter than -200. Three per list. EV here is the offer's price against the
list's own fair chance.

| List | Game | Book | The bet | Price | Fair chance | EV |
|---|---|---|---|---|---|---|
| same number | NBA_2021-04-19_GSW_PHI | draftkings | PHI | -233 | 0.772 | +0.103 |
| same number | NBA_2022-04-08_MIL_DET | betrivers | MIL | -263 | 0.769 | +0.061 |
| same number | NBA_2025-01-18_ATL_BOS | betmgm | BOS | -275 | 0.775 | +0.057 |
| every favourite | NBA_2021-04-19_GSW_PHI | betrivers | PHI | -233 | 0.772 | +0.103 |
| every favourite | NBA_2022-04-08_MIL_DET | betrivers | MIL | -263 | 0.769 | +0.061 |
| every favourite | NBA_2025-01-18_ATL_BOS | betmgm | BOS | -275 | 0.775 | +0.057 |
| favourite's spread | NBA_2021-04-19_GSW_PHI | fanduel | PHI -6.0 | -110 | 0.573 | +0.125 |
| favourite's spread | NBA_2025-03-10_PHI_ATL | betrivers | ATL -9.0 | -112 | 0.578 | +0.124 |
| favourite's spread | NBA_2025-01-18_ATL_BOS | betmgm | BOS -7.5 | -105 | 0.569 | +0.111 |
| model | NBA_2023-01-19_CHI_DET | betrivers | CHI | -286 | 0.849 | +0.146 |
| model | NBA_2024-03-13_CLE_NOP | draftkings | NOP | -205 | 0.734 | +0.092 |
| model | NBA_2021-11-18_WAS_MIA | fanduel | MIA | -244 | 0.774 | +0.092 |

A spread reads as the team bet and its own number. The stored number is the HOME number, so MIA +1.0 at CLE is stored as -1.0.

None of these is dropped by the rules in section 2. The blind bet reads no EV: its list shows where a game's market
chance and best price are far apart. Such a game's band is read on that best price, as section 2 registers. The full
lists, for all four decision points, print on every `--smoke`.

### 9.4 The market-anchored model's numbers

| Decision | Games in range | Lowest move, log-odds | Highest move | Lowest chance | Highest chance | Penalty |
|---|---|---|---|---|---|---|
| A | 3,090 | -1.17 | +0.51 | 0.363 | 0.920 | 0.003 |
| C | 3,077 | -1.26 | +0.49 | 0.347 | 0.918 | 0.003 |
| D | 3,076 | -1.24 | +0.48 | 0.351 | 0.918 | 0.003 |

A move is in log-odds, signed toward the home team. The lowest chance column is the model's own number for a favourite in
range. A game below the cut gets no bet, and every cut is above zero EV.

### 9.5 Coverage and the gate at D

The share of a season's games with a decision.

| Decision | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 |
|---|---|---|---|---|---|---|
| A | 99.6% | 100.0% | 100.0% | 100.0% | 100.0% | 99.9% |
| B | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| C | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| D | 99.6% | 99.4% | 100.0% | 100.0% | 100.0% | 100.0% |

The lowest choosing season at D is 99.4%, above the 95% gate. **No season is gated out at any point.**

### 9.6 The placebo on real prices

Share of placebo bets on a game the cell itself does not bet, over 20 seeds, on the graded seasons. Near 0 would
mean the shuffle repeats the real bets and the bar could never pass. Beside it, the same share under a same-date
shuffle in the same pool (the rule section 7 turned down). "Mean bets" is a placebo run's bets over those seeds,
set against the real cell's.

| Family | Decision | Cell | Real bets | Mean bets in a run | Other games, same week | Other games, same date |
|---|---|---|---|---|---|---|
| FAVB | A | -200 to -300 | 1,334 | 1,334.0 | 76% | 67% |
| FAVB | A | -300 to -500 | 1,024 | 1,024.0 | 81% | 71% |
| FAVB | A | shorter than -500 | 951 | 951.0 | 78% | 70% |
| FAVP2 | A | EV >= 0.00 | 23 | 23.0 | 94% | 77% |
| FAVP2 | A | EV >= 0.01 | 5 | 5.0 | 96% | 86% |
| FAVP2 | A | EV >= 0.02 | 2 | 2.0 | 98% | 90% |
| FAVP2 | A | EV >= 0.03 | 1 | 1.0 | 100% | 95% |
| FAVB | B | -200 to -300 | 1,284 | 1,284.0 | 77% | 68% |
| FAVB | B | -300 to -500 | 1,076 | 1,076.0 | 81% | 71% |
| FAVB | B | shorter than -500 | 961 | 961.0 | 79% | 70% |
| FAVP2 | B | EV >= 0.00 | 10 | 10.0 | 94% | 78% |
| FAVP2 | B | EV >= 0.01 | 2 | 2.0 | 95% | 78% |
| FAVP2 | B | EV >= 0.02 | 2 | 2.0 | 95% | 78% |
| FAVP2 | B | EV >= 0.03 | 1 | 1.0 | 100% | 80% |
| FAVB | C | -200 to -300 | 1,281 | 1,281.0 | 77% | 68% |
| FAVB | C | -300 to -500 | 1,056 | 1,056.0 | 81% | 71% |
| FAVB | C | shorter than -500 | 971 | 971.0 | 78% | 70% |
| FAVP2 | C | EV >= 0.00 | 40 | 40.0 | 96% | 73% |
| FAVP2 | C | EV >= 0.01 | 11 | 11.0 | 97% | 75% |
| FAVP2 | C | EV >= 0.02 | 7 | 7.0 | 96% | 75% |
| FAVP2 | C | EV >= 0.03 | 6 | 6.0 | 96% | 75% |
| FAVB | D | -200 to -300 | 1,281 | 1,281.0 | 77% | 68% |
| FAVB | D | -300 to -500 | 1,057 | 1,057.0 | 81% | 71% |
| FAVB | D | shorter than -500 | 969 | 969.0 | 78% | 69% |
| FAVP2 | D | EV >= 0.00 | 40 | 40.0 | 93% | 75% |
| FAVP2 | D | EV >= 0.01 | 11 | 11.0 | 92% | 74% |
| FAVP2 | D | EV >= 0.02 | 7 | 7.0 | 94% | 75% |
| FAVP2 | D | EV >= 0.03 | 6 | 6.0 | 93% | 76% |
| FAVP1 | A | EV >= 0.02 | 139 | 150.2 | 84% | 67% |
| FAVP1 | A | EV >= 0.04 | 45 | 40.1 | 88% | 62% |
| FAVP1 | A | EV >= 0.06 | 9 | 10.4 | 95% | 64% |
| FAVP1 | A | EV >= 0.08 | 4 | 2.7 | 93% | 58% |
| FAVP1 | C | EV >= 0.02 | 141 | 141.5 | 81% | 62% |
| FAVP1 | C | EV >= 0.04 | 46 | 46.1 | 86% | 64% |
| FAVP1 | C | EV >= 0.06 | 12 | 14.0 | 92% | 72% |
| FAVP1 | C | EV >= 0.08 | 7 | 4.2 | 93% | 68% |
| FAVP1 | D | EV >= 0.02 | 137 | 133.2 | 80% | 62% |
| FAVP1 | D | EV >= 0.04 | 46 | 44.9 | 86% | 62% |
| FAVP1 | D | EV >= 0.06 | 12 | 13.2 | 92% | 76% |
| FAVP1 | D | EV >= 0.08 | 7 | 3.6 | 90% | 61% |

**No cell with 30 or more real bets is under 50%.** The lowest such cell is at 76% under the week shuffle
and 62% under the date shuffle.

**Alone in their band on their date**, the counts behind section 7:

| Band | A | B | C | D |
|---|---|---|---|---|
| -200 to -300 | 20.7% | 21.2% | 21.9% | 21.9% |
| -300 to -500 | 26.9% | 24.5% | 25.1% | 25.2% |
| -500 to -1000 | 39.7% | 40.0% | 38.9% | 39.3% |
| shorter than -1000 | 62.0% | 56.8% | 57.9% | 57.9% |

### 9.7 Time and memory for `--full`

One placebo run of one cell on the real data, on the path `--full` takes (the same cells at 31 seeds against one): 0.078 s for a blind cell, 0.084 s for a same-number cell, 0.073 s for a model cell.
Projected from that run's own times: **48 minutes** for every cell with 200 placebo runs, the
loading of the prices excluded. Of that, the model's fit and inputs take 33 minutes. The peak working set was
3.1 GB. The whole test suite ran beside this smoke.

A one-off measure with four other jobs running read 0.107 s for a blind cell and 0.274 s for a same-number cell. At
those rates, and 0.274 s for the model cells too, the total is about 67 minutes. Both are inside the two-hour limit.

**`--full` has not been run.** No cell has been graded.

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


## 11. Results (graded 2026-10-31)

Run `2026-10-31-fav200`, stored in Supabase (`nba_game2_cells`, `nba_game2_population`). 40 cells and 40 controls.

**0 of the 40 cells pass. The family stays closed.**

- **The blind favourite, 12 cells, 951 to 1,334 bets each.** The best is the blind favourite at decision points C
  and D: 1,281 bets, +25.35 units, +0.8%, interval -2.8% to +4.3%. It misses the interval, the seasons, the bands and
  the placebo. Median return over the 12 cells with 200+ bets: -1.75%, with 2 positive.
- **Too few games to tell: the two model families.** FAVP1 reaches at most 141 bets and FAVP2 at most 40, against a
  bar of 200.
- **Five cells clear the 95% interval and none of them means anything.** They hold 1, 2, 2, 4 and 9 bets, and every
  bet won, so the interval has nothing to spread over. Each fails the 200-bet bar.

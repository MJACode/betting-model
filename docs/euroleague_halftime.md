# EuroLeague halftime betting — round 4 (2026-11-13)

Run on the local parquet cache only (`C:\Users\micha\euroleague_research\cache`).
No paid call, no database read, no repo file edited. Scripts:
`C:\Users\micha\documents\bm-euroleague-fix\scripts\euroleague_research\r4_*.py`.
Units only: each bet is sized to win 1 unit, with risk capped at 3, graded at the quoted price; a push returns the stake.
Intervals are 90%, from resampling dates (`r1_lib.summary`).

## 0. Pre-registration (written 2026-11-13 BEFORE any result was computed)

What had been read before this section was written: the schemas and row
counts of the cache; per-season and per-book counts of in-play rows; the
snapshot cadence; the shot feed's clock and order; first shot against the
listed tip; the number of five-minute reads inside each break
(`r4_inspect*.py`). No price, outcome or rule result had been computed.

### 0.1 The games
A game qualifies when it was played, it has a halftime row with
`break_minutes` between 10 and 25, and it has a pre-game prior (both a total and a spread, as defined below). Seasons
are labelled by their ending year: 2022 means 2021-22, and 2027 means 2026-27 to 2026-11-12.

### 0.2 The decision time
**The halftime break.** A read is one distinct `snapshot_ts` of the
in-play feed for that game. It counts when it falls strictly after
`last_q2_shot` + 1 minute and strictly before `first_q3_shot` − 1 minute.

### 0.3 Which quotes count: the ported rule
This is the women's college rule, unchanged except where EuroLeague's feed forces a different definition of the clock.
- **Fresh:** `last_update` > `last_q2_shot`, so the quote was re-hung after the half's last score.
- **In play:** `last_update` ≥ the game's first shot. This is the women's rule that a quote's stamp must have a game state.
  Books that pass this test count toward the read's median and toward the
  count of other books, whether or not their own quote is fresh. That is the women's code.
- **Bettable book:** draftkings, fanduel, betmgm, betrivers or fanatics. The reference books (pinnacle, bovada,
  marathonbet, unibet, paddypower) count toward the median and the count of other books, but are never bet.
- **Price of the side taken:** between −250 and +250.
- **Line outlier:** for totals and spreads, the line is within 6 points of the median line over the in-play books in that read. A moneyline has no line, so this check does not apply.
- **Other books:** at least 2 other in-play books quote the same market for the game in that read.
- **Line range:** a total between 60 and 260; a spread of at most 70 points either way.

### 0.4 The decision
The first read in the break that holds at least one eligible quote decides
the game for that market. Its eligible quote with the highest expected value is the bet, if that value is at or above the cut. Ties go by book
order: draftkings, fanduel, betmgm, betrivers, fanatics. The game is spent
for that market whether or not the quote clears the cut. There is one decision per game per market.

**Cut grid: expected value of 0.02, 0.03, 0.05, 0.08 and 0.12.** The headline cut is **0.05**, the cut the women's model ships at.

### 0.5 The model (from `models/ncaabw_live_ht.py` and `scripts/ncaabw_research/inplay.py`, unchanged)
- **Total points still to come** are normal. The mean is X·b; the variance is s0 + s1·f + s2·f², where f is the share of regulation left (out of 2,400 seconds).
  X has four terms: f·prior_t; f·sur; f²·sur; and late. Here sur = cur_t − prior_t·(1−f), and late = 1 when f < 300/2400 and the margin is within 8 points.
  It is fitted by weighted least squares in three passes, on the score every 30 seconds of regulation (30 to 2,370 seconds) of every qualifying game in the training seasons.
  The target is the final total, overtime included, minus the current total.
- **Margin still to come** (the research script's margin model) has three terms: f·prior_m, f·sur_m and f²·sur_m. Here sur_m = cur_m − prior_m·(1−f), and
  prior_m = −(the median pre-game home spread). The target is the final margin, overtime included, minus the current margin.
- **The game state from the shot feed.** Shots are sorted by `shot_utc`, then by `num_anot`. Game seconds come from the minute and the console clock, as a running maximum.
  The score is the running maximum of `points_home` and `points_away`. The state at a grid time is the last shot at or before it.
- **At the break:** f = 0.5. The score is `ht_home`/`ht_away`, which equals the shot feed's running maximum in 1,798 of 1,798 games.
- **Pricing.** Totals: P(over) = pw/(pw+pl), on a whole-number normal with pushes removed (`p_over`). Spreads: k = −spread_home − cur_m, and
  P(home covers) = pw/(pw+pl). Moneyline: P(home wins) = pw + 0.5·pp at k = −cur_m, with the regulation-tie mass split evenly.
  The moneyline pricing is an EXTENSION: the women's work had no moneyline model. EV = p·decimal − 1 for each side, and the side with the higher EV is the one considered.
- **Prior.** For each book, take its last full-game quote with `snapshot_at` ≤ min(listed tip, first shot). Then take the median over every book in the cache:
  spread_home where |v| ≤ 70, and total_line between 90 and 200. A game needs both.

### 0.6 Walk-forward
Season S is graded with constants fitted only on 2022 through S−1, for S = 2023, 2024, 2025, 2026 and 2027.
2022 has no earlier season. It is graded only as a "second look", fitted on 2023, reported apart, and never pooled with the walk-forward seasons.

### 0.7 Variants, fixed now, each at the full cut grid
- V1: no minimum count of other books (others ≥ 0).
- V2: the prior is Pinnacle's last pre-game total and spread alone; games without both are dropped.
- V3: the LAST read of the break that holds an eligible quote decides, not the first.
- V4: first crossing. The first read in which an eligible quote has EV ≥ the cut is bet, with one bet per game.
- V5 (a kill test, never a candidate): the fresh rule is removed, so a quote stamped before the last second-quarter shot also counts.

### 0.8 Baselines
At each book's first read in the break that holds a FRESH quote from it, bet blind. Totals: over and under. Spreads: home, away, favourite and underdog, where the favourite is the side giving points at the half.
Moneyline: home, away, favourite and underdog, by price. This is done for all ten books. Reference books are marked as not bettable.
Then the same at the best price among the decidable books, at the first read that holds any fresh decidable quote. The best price is the best number first, then the best price:
over at the lowest total, under at the highest total, home at the highest home spread, away at the lowest home spread, and a moneyline side at its highest price.
No price band is applied to the baselines. The moneyline is also broken down by price band.

### 0.9 The structural check
share2 = Σ(final − halftime total) / Σ final, over the earlier seasons only, overtime included. The mechanical line is the halftime total + prior_t × share2.
This is compared with each book's first fresh halftime total, by season, by book and by the first-half surprise in bins:
≤ −10, −10 to −4, −4 to +4, +4 to +10, ≥ +10, where the surprise = halftime total − prior_t × (1 − share2).
Beside it sits what actually happened: the second-half points minus the book's implied second half.
Two regressions: (book − halftime total), and (final − halftime total), each on prior_t and the surprise.
Spreads: share_m is the slope through the origin of the second-half margin on prior_m, over the earlier seasons. The mechanical home spread is
−(halftime margin + prior_m × share_m). Book against mechanical, split by whether the pre-game favourite trails at the half, and by the size of the halftime lead.

### 0.10 Kill tests, for anything positive at the headline cut or chosen as a lead
Walk-forward by season; early and late half of each season; the side split; the price band; the result without its 10 best dates;
the neighbouring cuts; and a placebo. The placebo shuffles (ht_home, ht_away) across games within each season, 200 times, then re-prices and re-decides with the quotes and outcomes kept. The real result must sit above the shuffles' 95th percentile.
Also: fresh against all quotes (V5); the other read (V3); the market's own number as a control, which is the blind bet at the same reads.
Benjamini-Hochberg at a 10% false-discovery rate runs across every graded cell, with the cells with 25+ bets also reported apart.
The sample's resolving power is stated from the blind bet's interval. The live loop is checked for whether it could meet the rule's condition: the games with a fresh quote per book and season, the window's length, the delay before a book re-hangs, and how many reads a break holds.

### 0.11 Addendum, registered AFTER reading experiments 2 to 4 and BEFORE running it: the after-the-fact rule P1
**This rule was chosen with the results in view.** Experiment 4 found that DraftKings' halftime total strays from the mechanical line, and that most of the stray is noise (slope −0.68, SE 0.23). This is the cheapest test of whether that pays.
- **Decision:** the first read in the break that holds an eligible total quote, under the ported eligibility rules (0.3).
- mech = halftime total + prior_t × share2, where share2 is the walk-forward share from 0.9. dev = line − mech. The side is under when dev > 0 and over when dev < 0. The price of the side taken must be between −250 and +250.
- Among that read's eligible quotes, take the one with the largest |dev|, with ties going by book order. Bet it if |dev| ≥ D.
- **The D grid: 1.0, 1.5, 2.0, 3.0 points. The headline is D = 2.0.** It is graded on the walk-forward seasons 2022-23 to 2026-27, and each cell is counted in Benjamini-Hochberg.

---

## 1. Coverage, data notes and what a live loop gets

Script: `scripts/euroleague_research/r4_coverage.py`.

### Data notes

- Played games with a halftime row: 1,798; break 10-25 minutes: 1,702; with a pre-game total and spread as well (qualifying): 1,695.
- Qualifying games by season: {2022: 278, 2023: 308, 2024: 319, 2025: 308, 2026: 377, 2027: 105}.
- Final scores include overtime: in 81 overtime games the final equals the sum of all periods in 81.
- In-play rows: 562,936; dropped because last_update was after snapshot_ts: 9.
- In-play rows whose read falls inside a qualifying break: 65,857 on 1,673 games.
- The shot feed's clock: free throws at the end of the second quarter are sometimes logged with a placeholder clock of 01:00 after a 00:10 shot (EUROLEAGUE_E2025_100). The running maximum of game seconds keeps the state in order, and the decision uses the half-time score at f = 0.5 directly. Training states near 1,150-1,200 game seconds can carry a slightly wrong f; this was left as ported.
- Decidable books in play: only DraftKings in 2021-22 to 2024-25; FanDuel, BetMGM, BetRivers and Fanatics from 2025-26 (r4_inspect2.py). In those four seasons the rule that a quote needs two other books is met only through the reference books.
- 2021-22 was snapshotted every 10 minutes (87.8% of gaps); 5 minutes from 2022-23 (96%).

### Games with at least one fresh halftime quote, by book

Fresh = re-hung after the last second-quarter shot; the read inside the break window.

| market | season | draftkings | fanduel | betmgm | betrivers | fanatics | pinnacle | bovada | marathonbet | unibet | paddypower | games with a read in the break | any decidable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| totals | 2022 | 256 | 0 | 0 | 0 | 0 | 213 | 249 | 0 | 265 | 0 | 276 | 256 |
| totals | 2023 | 285 | 0 | 0 | 0 | 0 | 252 | 276 | 0 | 308 | 0 | 308 | 285 |
| totals | 2024 | 313 | 0 | 0 | 0 | 0 | 249 | 310 | 0 | 314 | 0 | 315 | 313 |
| totals | 2025 | 294 | 0 | 0 | 0 | 0 | 269 | 292 | 0 | 166 | 0 | 294 | 294 |
| totals | 2026 | 375 | 335 | 338 | 273 | 347 | 352 | 293 | 0 | 0 | 0 | 376 | 376 |
| totals | 2027 | 104 | 104 | 100 | 104 | 104 | 98 | 104 | 67 | 0 | 0 | 104 | 104 |
| spreads | 2022 | 257 | 0 | 0 | 0 | 0 | 213 | 250 | 0 | 263 | 0 | 276 | 257 |
| spreads | 2023 | 285 | 0 | 0 | 0 | 0 | 252 | 275 | 0 | 308 | 0 | 308 | 285 |
| spreads | 2024 | 313 | 0 | 0 | 0 | 0 | 249 | 311 | 0 | 314 | 0 | 315 | 313 |
| spreads | 2025 | 294 | 0 | 0 | 0 | 0 | 269 | 292 | 0 | 294 | 0 | 294 | 294 |
| spreads | 2026 | 375 | 341 | 286 | 348 | 347 | 352 | 293 | 0 | 376 | 0 | 376 | 376 |
| spreads | 2027 | 104 | 104 | 84 | 104 | 104 | 98 | 104 | 67 | 101 | 0 | 104 | 104 |
| h2h | 2022 | 262 | 0 | 0 | 0 | 0 | 201 | 245 | 0 | 238 | 226 | 276 | 262 |
| h2h | 2023 | 276 | 0 | 0 | 0 | 0 | 249 | 302 | 0 | 285 | 290 | 308 | 276 |
| h2h | 2024 | 297 | 0 | 0 | 0 | 0 | 247 | 308 | 0 | 280 | 307 | 315 | 297 |
| h2h | 2025 | 270 | 0 | 0 | 0 | 0 | 266 | 286 | 0 | 257 | 281 | 294 | 270 |
| h2h | 2026 | 364 | 338 | 338 | 321 | 341 | 349 | 286 | 0 | 351 | 371 | 376 | 375 |
| h2h | 2027 | 98 | 100 | 102 | 89 | 100 | 94 | 100 | 45 | 95 | 104 | 104 | 104 |

### Games with an in-play quote in the break, any book: all quotes against fresh only

| market | kind | 2022 | 2023 | 2024 | 2025 | 2026 | 2027 |
|---|---|---|---|---|---|---|---|
| totals | all in-play | 276 | 308 | 315 | 294 | 376 | 104 |
| totals | fresh | 266 | 308 | 315 | 294 | 376 | 104 |
| spreads | all in-play | 276 | 308 | 315 | 294 | 376 | 104 |
| spreads | fresh | 266 | 308 | 315 | 294 | 376 | 104 |
| h2h | all in-play | 276 | 308 | 315 | 294 | 376 | 104 |
| h2h | fresh | 266 | 308 | 315 | 294 | 376 | 104 |

### The window a live loop gets

Break (last second-quarter shot to first third-quarter shot), qualifying games: median 15.97 minutes, 10th-90th percentile 15.38-17.16. The window used here (one-minute buffers each side): median 13.97 minutes.

Reads inside the window per game (the feed's own cadence):

| season | count | mean | 50% | min | max |
|---|---|---|---|---|---|
| 2022 | 276.00 | 1.43 | 1.00 | 1.00 | 2.00 |
| 2023 | 308.00 | 2.82 | 3.00 | 2.00 | 5.00 |
| 2024 | 315.00 | 2.83 | 3.00 | 2.00 | 5.00 |
| 2025 | 294.00 | 2.80 | 3.00 | 2.00 | 4.00 |
| 2026 | 376.00 | 2.82 | 3.00 | 1.00 | 4.00 |
| 2027 | 104.00 | 2.86 | 3.00 | 2.00 | 4.00 |

### How long after the half's last shot each book re-hangs (its first fresh stamp)

`delay` = first fresh last_update minus the last second-quarter shot, minutes. `minutes_left` = from that stamp to one minute before the first third-quarter shot.

| market | bookmaker | games | delay_median | delay_p90 | minutes_left_median |
|---|---|---|---|---|---|
| h2h | betmgm | 440 | 2.93 | 5.00 | 12.22 |
| h2h | betrivers | 410 | 3.03 | 5.03 | 12.15 |
| h2h | bovada | 1,527 | 3.07 | 6.03 | 11.97 |
| h2h | draftkings | 1,567 | 3.23 | 5.99 | 11.75 |
| h2h | fanatics | 441 | 2.93 | 5.03 | 12.15 |
| h2h | fanduel | 438 | 3.08 | 5.22 | 12.02 |
| h2h | marathonbet | 45 | 3.25 | 5.08 | 12.45 |
| h2h | paddypower | 1,579 | 3.18 | 5.73 | 11.85 |
| h2h | pinnacle | 1,406 | 3.55 | 8.74 | 11.49 |
| h2h | unibet | 1,506 | 3.10 | 5.54 | 11.98 |
| spreads | betmgm | 370 | 3.04 | 5.00 | 12.10 |
| spreads | betrivers | 452 | 2.98 | 5.00 | 12.20 |
| spreads | bovada | 1,525 | 3.08 | 6.10 | 11.93 |
| spreads | draftkings | 1,628 | 3.21 | 5.89 | 11.78 |
| spreads | fanatics | 451 | 2.97 | 5.03 | 12.15 |
| spreads | fanduel | 445 | 3.08 | 5.21 | 12.03 |
| spreads | marathonbet | 67 | 3.28 | 4.79 | 12.37 |
| spreads | pinnacle | 1,433 | 3.55 | 8.70 | 11.50 |
| spreads | unibet | 1,656 | 3.10 | 5.53 | 11.98 |
| totals | betmgm | 438 | 2.93 | 5.01 | 12.22 |
| totals | betrivers | 377 | 3.00 | 4.95 | 12.10 |
| totals | bovada | 1,524 | 3.09 | 6.16 | 11.94 |
| totals | draftkings | 1,627 | 3.22 | 5.89 | 11.78 |
| totals | fanatics | 451 | 2.97 | 5.03 | 12.15 |
| totals | fanduel | 439 | 3.10 | 5.22 | 12.02 |
| totals | marathonbet | 67 | 3.28 | 4.79 | 12.37 |
| totals | pinnacle | 1,433 | 3.55 | 8.70 | 11.50 |
| totals | unibet | 1,053 | 3.17 | 6.18 | 11.78 |

### The score feed's timing

First shot minus the listed tip, minutes: median 1.17, 5th 0.52, 95th 2.72 (1,798 games). The shot chart's wall clock tracks real time: a 15-minute break reads a median 15.97 minutes from the last second-quarter shot to the first third-quarter shot. The decidable books' first fresh total is stamped a median 3.10 minutes after the last shot (share within 1 minute: 8.7%, within 2: 27.4%; 3,332 game-books). That is an upper bound on the re-hang delay: the feed holds only a book's latest stamp at each read, so an earlier re-hang overwritten before the first read is not seen. A quote stamped after the last shot cannot predate the half's final score unless the shot feed runs early, and the one-minute buffer at the start of the window covers a feed that runs up to a minute early. No live EuroLeague in-play feed exists yet, so the lag between a live score source and the books cannot be measured here.

## 2. Baselines at halftime

Script: `scripts/euroleague_research/r4_baselines.py`.

### (a) Blind bets at each book's first fresh halftime quote, all seasons

Reference books are not bettable; their rows say only what their prices would have paid.

| book | market | side | bets | W | L | P | units | ret% | lo% | hi% |
|---|---|---|---|---|---|---|---|---|---|---|
| draftkings | totals | over | 1,627 | 778 | 849 | 0 | -196.63 | -10.52 | -14.52 | -6.62 |
| draftkings | totals | under | 1,627 | 849 | 778 | 0 | -47.05 | -2.51 | -6.42 | 1.46 |
| draftkings | spreads | home | 1,628 | 848 | 780 | 0 | -50.90 | -2.71 | -6.44 | 0.96 |
| draftkings | spreads | away | 1,628 | 780 | 848 | 0 | -194.15 | -10.37 | -14.14 | -6.66 |
| draftkings | spreads | favourite | 1,628 | 803 | 825 | 0 | -145.30 | -7.76 | -11.63 | -3.87 |
| draftkings | spreads | underdog | 1,628 | 825 | 803 | 0 | -99.75 | -5.32 | -9.21 | -1.42 |
| draftkings | h2h | home | 1,567 | 983 | 584 | 0 | 12.50 | 0.40 | -2.74 | 3.32 |
| draftkings | h2h | away | 1,567 | 584 | 983 | 0 | -375.09 | -16.79 | -21.44 | -12.17 |
| draftkings | h2h | favourite | 1,506 | 1,138 | 368 | 0 | -35.78 | -0.96 | -3.09 | 1.07 |
| draftkings | h2h | underdog | 1,506 | 368 | 1,138 | 0 | -317.66 | -21.05 | -27.90 | -13.98 |
| fanduel | totals | over | 439 | 215 | 224 | 0 | -37.65 | -7.61 | -15.20 | 0.46 |
| fanduel | totals | under | 439 | 224 | 215 | 0 | -19.25 | -3.88 | -11.95 | 3.77 |
| fanduel | spreads | home | 445 | 224 | 221 | 0 | -25.45 | -5.08 | -12.59 | 2.14 |
| fanduel | spreads | away | 445 | 221 | 224 | 0 | -32.70 | -6.50 | -13.74 | 1.03 |
| fanduel | spreads | favourite | 445 | 222 | 223 | 0 | -29.85 | -5.95 | -13.28 | 1.02 |
| fanduel | spreads | underdog | 445 | 223 | 222 | 0 | -28.30 | -5.63 | -12.60 | 1.83 |
| fanduel | h2h | home | 438 | 272 | 166 | 0 | -1.70 | -0.19 | -6.83 | 7.30 |
| fanduel | h2h | away | 438 | 166 | 272 | 0 | -83.69 | -13.38 | -22.93 | -3.23 |
| fanduel | h2h | favourite | 433 | 320 | 113 | 0 | -42.19 | -3.95 | -7.81 | -0.12 |
| fanduel | h2h | underdog | 433 | 113 | 320 | 0 | -42.45 | -9.77 | -25.33 | 7.51 |
| betmgm | totals | over | 438 | 208 | 230 | 0 | -51.41 | -10.36 | -17.99 | -2.14 |
| betmgm | totals | under | 438 | 230 | 208 | 0 | -11.20 | -2.19 | -10.23 | 5.56 |
| betmgm | spreads | home | 370 | 189 | 181 | 0 | -20.22 | -4.70 | -12.46 | 2.94 |
| betmgm | spreads | away | 370 | 181 | 189 | 0 | -32.15 | -7.66 | -15.55 | 0.19 |
| betmgm | spreads | favourite | 370 | 180 | 190 | 0 | -36.25 | -8.55 | -16.31 | -0.78 |
| betmgm | spreads | underdog | 370 | 190 | 180 | 0 | -16.12 | -3.78 | -11.50 | 3.98 |
| betmgm | h2h | home | 440 | 273 | 167 | 0 | -17.78 | -1.97 | -7.53 | 4.20 |
| betmgm | h2h | away | 440 | 167 | 273 | 0 | -106.07 | -16.95 | -24.70 | -8.75 |
| betmgm | h2h | favourite | 434 | 320 | 114 | 0 | -39.15 | -3.63 | -7.39 | 0.07 |
| betmgm | h2h | underdog | 434 | 114 | 320 | 0 | -83.80 | -19.23 | -31.16 | -6.07 |
| betrivers | totals | over | 377 | 184 | 191 | 2 | -46.13 | -10.24 | -18.13 | -2.87 |
| betrivers | totals | under | 377 | 191 | 184 | 2 | -31.50 | -6.98 | -14.46 | 0.94 |
| betrivers | spreads | home | 452 | 220 | 225 | 7 | -48.66 | -9.12 | -17.37 | -1.79 |
| betrivers | spreads | away | 452 | 225 | 220 | 7 | -35.78 | -6.74 | -14.09 | 1.47 |
| betrivers | spreads | favourite | 452 | 213 | 232 | 7 | -62.77 | -11.80 | -19.10 | -4.61 |
| betrivers | spreads | underdog | 452 | 232 | 213 | 7 | -21.67 | -4.07 | -11.24 | 3.13 |
| betrivers | h2h | home | 410 | 244 | 166 | 0 | -46.62 | -5.70 | -11.56 | -0.20 |
| betrivers | h2h | away | 410 | 166 | 244 | 0 | -74.96 | -12.48 | -20.74 | -3.75 |
| betrivers | h2h | favourite | 408 | 292 | 116 | 0 | -59.48 | -5.93 | -10.39 | -1.37 |
| betrivers | h2h | underdog | 408 | 116 | 292 | 0 | -61.76 | -15.01 | -27.21 | -2.36 |
| fanatics | totals | over | 451 | 226 | 225 | 0 | -34.95 | -6.68 | -14.42 | 1.29 |
| fanatics | totals | under | 451 | 225 | 226 | 0 | -40.20 | -7.59 | -15.46 | 0.24 |
| fanatics | spreads | home | 451 | 224 | 227 | 0 | -38.70 | -7.38 | -14.64 | -0.48 |
| fanatics | spreads | away | 451 | 227 | 224 | 0 | -34.80 | -6.58 | -13.50 | 0.60 |
| fanatics | spreads | favourite | 451 | 223 | 228 | 0 | -38.35 | -7.39 | -13.98 | -0.51 |
| fanatics | spreads | underdog | 451 | 228 | 223 | 0 | -35.15 | -6.58 | -13.25 | -0.33 |
| fanatics | h2h | home | 441 | 272 | 169 | 0 | -39.28 | -4.34 | -9.39 | 0.52 |
| fanatics | h2h | away | 441 | 169 | 272 | 0 | -102.63 | -16.22 | -24.07 | -8.19 |
| fanatics | h2h | favourite | 431 | 319 | 112 | 0 | -46.16 | -4.27 | -8.22 | -0.46 |
| fanatics | h2h | underdog | 431 | 112 | 319 | 0 | -94.05 | -21.70 | -32.13 | -9.73 |
| pinnacle (reference) | totals | over | 1,433 | 692 | 717 | 24 | -109.42 | -6.95 | -11.09 | -2.61 |
| pinnacle (reference) | totals | under | 1,433 | 717 | 692 | 24 | -57.38 | -3.64 | -8.00 | 0.49 |
| pinnacle (reference) | spreads | home | 1,433 | 721 | 676 | 36 | -35.34 | -2.26 | -6.35 | 1.92 |
| pinnacle (reference) | spreads | away | 1,433 | 676 | 721 | 36 | -128.24 | -8.22 | -12.51 | -4.17 |
| pinnacle (reference) | spreads | favourite | 1,433 | 708 | 689 | 36 | -60.89 | -3.90 | -8.06 | 0.62 |
| pinnacle (reference) | spreads | underdog | 1,433 | 689 | 708 | 36 | -102.69 | -6.57 | -11.14 | -2.37 |
| pinnacle (reference) | h2h | home | 1,406 | 884 | 522 | 0 | 35.77 | 1.27 | -2.02 | 4.73 |
| pinnacle (reference) | h2h | away | 1,406 | 522 | 884 | 0 | -337.61 | -16.83 | -21.62 | -12.34 |
| pinnacle (reference) | h2h | favourite | 1,403 | 1,051 | 352 | 0 | -11.18 | -0.33 | -2.61 | 1.96 |
| pinnacle (reference) | h2h | underdog | 1,403 | 352 | 1,051 | 0 | -290.25 | -20.62 | -28.25 | -13.07 |
| bovada (reference) | totals | over | 1,524 | 730 | 784 | 10 | -165.84 | -9.55 | -13.31 | -5.72 |
| bovada (reference) | totals | under | 1,524 | 784 | 730 | 10 | -58.15 | -3.31 | -7.12 | 0.55 |
| bovada (reference) | spreads | home | 1,525 | 800 | 709 | 16 | -12.01 | -0.69 | -4.36 | 3.30 |
| bovada (reference) | spreads | away | 1,525 | 709 | 800 | 16 | -208.01 | -11.97 | -15.94 | -8.30 |
| bovada (reference) | spreads | favourite | 1,525 | 764 | 745 | 16 | -85.31 | -4.93 | -9.14 | -0.95 |
| bovada (reference) | spreads | underdog | 1,525 | 745 | 764 | 16 | -134.71 | -7.71 | -11.64 | -3.55 |
| bovada (reference) | h2h | home | 1,527 | 970 | 557 | 0 | -15.93 | -0.51 | -3.26 | 2.46 |
| bovada (reference) | h2h | away | 1,527 | 557 | 970 | 0 | -384.04 | -17.55 | -22.10 | -12.87 |
| bovada (reference) | h2h | favourite | 1,495 | 1,123 | 372 | 0 | -115.66 | -3.08 | -5.29 | -0.98 |
| bovada (reference) | h2h | underdog | 1,495 | 372 | 1,123 | 0 | -279.50 | -18.63 | -25.85 | -10.99 |
| marathonbet (reference) | totals | over | 67 | 35 | 32 | 0 | -2.37 | -3.05 | -18.27 | 12.17 |
| marathonbet (reference) | totals | under | 67 | 32 | 35 | 0 | -8.98 | -11.51 | -26.82 | 3.90 |
| marathonbet (reference) | spreads | home | 67 | 31 | 36 | 0 | -11.09 | -14.13 | -37.57 | 12.73 |
| marathonbet (reference) | spreads | away | 67 | 36 | 31 | 0 | 0.17 | 0.22 | -26.75 | 23.82 |
| marathonbet (reference) | spreads | favourite | 67 | 37 | 30 | 0 | 2.26 | 2.91 | -20.04 | 24.66 |
| marathonbet (reference) | spreads | underdog | 67 | 30 | 37 | 0 | -13.18 | -16.83 | -38.73 | 6.07 |
| marathonbet (reference) | h2h | home | 45 | 22 | 23 | 0 | -18.80 | -21.21 | -42.34 | -5.08 |
| marathonbet (reference) | h2h | away | 45 | 23 | 22 | 0 | 2.08 | 3.16 | -17.62 | 26.01 |
| marathonbet (reference) | h2h | favourite | 45 | 35 | 10 | 0 | 1.41 | 1.30 | -10.43 | 12.34 |
| marathonbet (reference) | h2h | underdog | 45 | 10 | 35 | 0 | -18.13 | -40.00 | -66.09 | -13.38 |
| unibet (reference) | totals | over | 1,053 | 495 | 538 | 20 | -121.78 | -10.28 | -15.30 | -5.58 |
| unibet (reference) | totals | under | 1,053 | 538 | 495 | 20 | -29.36 | -2.48 | -7.15 | 2.46 |
| unibet (reference) | spreads | home | 1,656 | 859 | 762 | 35 | -10.42 | -0.56 | -4.24 | 2.83 |
| unibet (reference) | spreads | away | 1,656 | 762 | 859 | 35 | -220.10 | -11.88 | -15.31 | -8.17 |
| unibet (reference) | spreads | favourite | 1,656 | 812 | 809 | 35 | -111.29 | -6.01 | -9.99 | -2.24 |
| unibet (reference) | spreads | underdog | 1,656 | 809 | 812 | 35 | -119.23 | -6.44 | -10.18 | -2.45 |
| unibet (reference) | h2h | home | 1,506 | 928 | 578 | 0 | -13.63 | -0.46 | -3.63 | 2.65 |
| unibet (reference) | h2h | away | 1,506 | 578 | 928 | 0 | -317.32 | -14.50 | -19.05 | -9.79 |
| unibet (reference) | h2h | favourite | 1,502 | 1,109 | 393 | 0 | -106.76 | -2.91 | -5.17 | -0.80 |
| unibet (reference) | h2h | underdog | 1,502 | 393 | 1,109 | 0 | -223.61 | -14.81 | -21.82 | -7.36 |
| paddypower (reference) | totals | over | 0 | 0 | 0 | 0 | 0.00 |  |  |  |
| paddypower (reference) | totals | under | 0 | 0 | 0 | 0 | 0.00 |  |  |  |
| paddypower (reference) | spreads | home | 0 | 0 | 0 | 0 | 0.00 |  |  |  |
| paddypower (reference) | spreads | away | 0 | 0 | 0 | 0 | 0.00 |  |  |  |
| paddypower (reference) | spreads | favourite | 0 | 0 | 0 | 0 | 0.00 |  |  |  |
| paddypower (reference) | spreads | underdog | 0 | 0 | 0 | 0 | 0.00 |  |  |  |
| paddypower (reference) | h2h | home | 1,579 | 1,007 | 572 | 0 | -39.20 | -1.19 | -3.99 | 1.65 |
| paddypower (reference) | h2h | away | 1,579 | 572 | 1,007 | 0 | -454.45 | -19.85 | -24.14 | -15.33 |
| paddypower (reference) | h2h | favourite | 1,555 | 1,185 | 370 | 0 | -126.62 | -3.19 | -5.09 | -1.16 |
| paddypower (reference) | h2h | underdog | 1,555 | 370 | 1,185 | 0 | -362.23 | -23.25 | -30.28 | -15.95 |

### (b) Blind bets at the best decidable price, first read holding a fresh decidable quote

| market | side | season | bets | W | L | P | units | ret% | lo% | hi% |
|---|---|---|---|---|---|---|---|---|---|---|
| totals | over | all | 1,628 | 784 | 844 | 0 | -188.17 | -10.04 | -13.88 | -6.40 |
| totals | over | 2021-22 | 256 | 107 | 149 | 0 | -63.65 | -21.72 | -29.96 | -13.70 |
| totals | over | 2022-23 | 285 | 133 | 152 | 0 | -41.80 | -12.75 | -22.39 | -3.32 |
| totals | over | 2023-24 | 313 | 145 | 168 | 0 | -48.20 | -13.39 | -21.41 | -5.60 |
| totals | over | 2024-25 | 294 | 151 | 143 | 0 | -13.45 | -3.98 | -12.59 | 4.82 |
| totals | over | 2025-26 | 376 | 194 | 182 | 0 | -15.34 | -3.56 | -11.98 | 5.32 |
| totals | over | 2026-27 to 11-12 | 104 | 54 | 50 | 0 | -5.73 | -4.65 | -20.34 | 12.13 |
| totals | under | all | 1,628 | 865 | 762 | 1 | -15.51 | -0.82 | -4.47 | 3.15 |
| totals | under | 2021-22 | 256 | 149 | 107 | 0 | 25.25 | 8.53 | 0.70 | 16.69 |
| totals | under | 2022-23 | 285 | 152 | 133 | 0 | -0.95 | -0.29 | -9.72 | 9.34 |
| totals | under | 2023-24 | 313 | 168 | 145 | 0 | 1.25 | 0.35 | -7.45 | 8.37 |
| totals | under | 2024-25 | 294 | 143 | 151 | 0 | -30.65 | -9.07 | -17.86 | -0.46 |
| totals | under | 2025-26 | 376 | 200 | 175 | 1 | -3.52 | -0.81 | -9.80 | 7.91 |
| totals | under | 2026-27 to 11-12 | 104 | 53 | 51 | 0 | -6.89 | -5.64 | -21.36 | 9.27 |
| spreads | home | all | 1,629 | 856 | 771 | 2 | -35.60 | -1.89 | -5.59 | 1.69 |
| spreads | home | 2021-22 | 257 | 139 | 118 | 0 | 3.90 | 1.32 | -8.37 | 10.78 |
| spreads | home | 2022-23 | 285 | 155 | 130 | 0 | 4.20 | 1.27 | -8.04 | 10.63 |
| spreads | home | 2023-24 | 313 | 165 | 148 | 0 | -6.45 | -1.78 | -10.22 | 6.75 |
| spreads | home | 2024-25 | 294 | 147 | 147 | 0 | -22.70 | -6.67 | -14.86 | 1.39 |
| spreads | home | 2025-26 | 376 | 199 | 175 | 2 | -3.85 | -0.89 | -8.52 | 6.35 |
| spreads | home | 2026-27 to 11-12 | 104 | 51 | 53 | 0 | -10.70 | -8.80 | -26.27 | 8.28 |
| spreads | away | all | 1,629 | 789 | 838 | 2 | -174.21 | -9.31 | -12.82 | -5.70 |
| spreads | away | 2021-22 | 257 | 118 | 139 | 0 | -42.15 | -14.21 | -23.67 | -4.66 |
| spreads | away | 2022-23 | 285 | 130 | 155 | 0 | -47.70 | -14.61 | -23.95 | -5.22 |
| spreads | away | 2023-24 | 313 | 148 | 165 | 0 | -41.55 | -11.55 | -20.13 | -3.04 |
| spreads | away | 2024-25 | 294 | 147 | 147 | 0 | -21.10 | -6.26 | -14.21 | 1.86 |
| spreads | away | 2025-26 | 376 | 187 | 187 | 2 | -28.19 | -6.55 | -14.06 | 1.18 |
| spreads | away | 2026-27 to 11-12 | 104 | 59 | 45 | 0 | 6.48 | 5.34 | -10.64 | 21.88 |
| spreads | favourite | all | 1,603 | 794 | 807 | 2 | -133.03 | -7.23 | -11.02 | -3.52 |
| spreads | favourite | 2021-22 | 257 | 146 | 111 | 0 | 18.85 | 6.39 | -3.99 | 16.54 |
| spreads | favourite | 2022-23 | 285 | 138 | 147 | 0 | -31.05 | -9.48 | -18.93 | 0.25 |
| spreads | favourite | 2023-24 | 313 | 153 | 160 | 0 | -31.30 | -8.70 | -18.26 | 0.49 |
| spreads | favourite | 2024-25 | 294 | 128 | 166 | 0 | -62.20 | -18.40 | -26.81 | -9.34 |
| spreads | favourite | 2025-26 | 355 | 174 | 179 | 2 | -31.23 | -7.72 | -15.20 | 0.07 |
| spreads | favourite | 2026-27 to 11-12 | 99 | 55 | 44 | 0 | 3.90 | 3.39 | -11.77 | 19.68 |
| spreads | underdog | all | 1,655 | 851 | 802 | 2 | -76.78 | -4.01 | -7.80 | -0.49 |
| spreads | underdog | 2021-22 | 257 | 111 | 146 | 0 | -57.10 | -19.26 | -29.47 | -9.13 |
| spreads | underdog | 2022-23 | 285 | 147 | 138 | 0 | -12.45 | -3.79 | -13.50 | 5.72 |
| spreads | underdog | 2023-24 | 313 | 160 | 153 | 0 | -16.70 | -4.62 | -13.76 | 4.96 |
| spreads | underdog | 2024-25 | 294 | 166 | 128 | 0 | 18.40 | 5.42 | -3.56 | 13.74 |
| spreads | underdog | 2025-26 | 397 | 212 | 183 | 2 | -0.81 | -0.18 | -6.67 | 6.45 |
| spreads | underdog | 2026-27 to 11-12 | 109 | 55 | 54 | 0 | -8.12 | -6.34 | -19.93 | 6.36 |
| h2h | home | all | 1,584 | 996 | 588 | 0 | 51.52 | 1.62 | -1.66 | 4.98 |
| h2h | home | 2021-22 | 262 | 177 | 85 | 0 | 50.50 | 9.84 | 2.45 | 17.71 |
| h2h | home | 2022-23 | 276 | 172 | 104 | 0 | 4.43 | 0.79 | -6.19 | 8.37 |
| h2h | home | 2023-24 | 297 | 189 | 108 | 0 | -2.35 | -0.39 | -6.42 | 6.02 |
| h2h | home | 2024-25 | 270 | 161 | 109 | 0 | -13.44 | -2.49 | -10.36 | 4.86 |
| h2h | home | 2025-26 | 375 | 241 | 134 | 0 | 43.85 | 5.90 | -1.17 | 13.13 |
| h2h | home | 2026-27 to 11-12 | 104 | 56 | 48 | 0 | -31.49 | -14.67 | -24.16 | -5.47 |
| h2h | away | all | 1,584 | 588 | 996 | 0 | -357.03 | -15.89 | -20.55 | -10.70 |
| h2h | away | 2021-22 | 262 | 85 | 177 | 0 | -112.87 | -29.23 | -39.80 | -18.51 |
| h2h | away | 2022-23 | 276 | 104 | 172 | 0 | -44.10 | -11.50 | -23.38 | 0.72 |
| h2h | away | 2023-24 | 297 | 108 | 189 | 0 | -83.03 | -19.81 | -28.45 | -11.27 |
| h2h | away | 2024-25 | 270 | 109 | 161 | 0 | -44.81 | -11.49 | -22.04 | -0.06 |
| h2h | away | 2025-26 | 375 | 134 | 241 | 0 | -90.09 | -17.14 | -25.14 | -8.53 |
| h2h | away | 2026-27 to 11-12 | 104 | 48 | 56 | 0 | 17.87 | 12.55 | -15.04 | 49.00 |
| h2h | favourite | all | 1,504 | 1,144 | 360 | 0 | -19.89 | -0.53 | -2.51 | 1.47 |
| h2h | favourite | 2021-22 | 257 | 208 | 49 | 0 | 34.53 | 5.48 | 0.30 | 10.67 |
| h2h | favourite | 2022-23 | 261 | 197 | 64 | 0 | -4.11 | -0.64 | -6.36 | 5.50 |
| h2h | favourite | 2023-24 | 281 | 213 | 68 | 0 | -9.68 | -1.37 | -5.87 | 2.64 |
| h2h | favourite | 2024-25 | 253 | 185 | 68 | 0 | -29.18 | -4.57 | -9.82 | 0.44 |
| h2h | favourite | 2025-26 | 354 | 263 | 91 | 0 | -17.56 | -2.02 | -6.53 | 2.65 |
| h2h | favourite | 2026-27 to 11-12 | 98 | 78 | 20 | 0 | 6.11 | 2.48 | -5.86 | 9.55 |
| h2h | underdog | all | 1,543 | 380 | 1,163 | 0 | -275.43 | -17.81 | -25.28 | -10.24 |
| h2h | underdog | 2021-22 | 257 | 49 | 208 | 0 | -96.15 | -37.28 | -54.43 | -19.10 |
| h2h | underdog | 2022-23 | 261 | 64 | 197 | 0 | -33.30 | -12.76 | -34.22 | 7.12 |
| h2h | underdog | 2023-24 | 281 | 68 | 213 | 0 | -73.30 | -26.08 | -37.52 | -13.34 |
| h2h | underdog | 2024-25 | 253 | 68 | 185 | 0 | -26.52 | -10.48 | -27.69 | 6.62 |
| h2h | underdog | 2025-26 | 384 | 105 | 279 | 0 | -29.88 | -7.74 | -23.24 | 7.53 |
| h2h | underdog | 2026-27 to 11-12 | 107 | 26 | 81 | 0 | -16.28 | -15.16 | -47.69 | 28.90 |

### (b2) Moneyline at the best decidable price, by price band (not registered: sub-rows)

| side | price band | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|
| favourite | -200..+100 | 407 | 237 | 170 | 0 | -18.38 | -2.95 | -9.16 | 4.21 | 0.7717 |
| favourite | -500..-200 | 537 | 400 | 137 | 0 | 2.31 | 0.16 | -3.66 | 3.93 | 0.4726 |
| favourite | <=-500 | 560 | 507 | 53 | 0 | -3.82 | -0.23 | -2.59 | 1.83 | 0.5665 |
| underdog | +100..+300 | 824 | 278 | 546 | 0 | -89.59 | -10.87 | -17.45 | -3.83 | 0.9958 |
| underdog | -200..+100 | 70 | 32 | 38 | 0 | -7.89 | -10.77 | -27.38 | 5.69 | 0.8618 |
| underdog | >+300 | 649 | 70 | 579 | 0 | -177.95 | -27.42 | -43.03 | -10.96 | 0.9976 |

### (b3) The same blind bets: early/late half of each season, without the 10 best dates, and by price band (not registered: sub-rows)

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | share% |
|---|---|---|---|---|---|---|---|---|---|---|
| totals over | early half of each season | 801 | 385 | 416 | 0 | -94.17 | -10.21 | -16.05 | -4.43 |  |
| totals over | late half of each season | 827 | 399 | 428 | 0 | -94.00 | -9.88 | -15.16 | -4.62 |  |
| totals over | without its 10 best dates | 1,577 | 735 | 842 | 0 | -234.92 | -12.94 | -16.79 | -9.16 |  |
| totals over | price band +100..+150 | 3 | 1 | 2 | 0 | -1.00 | -33.33 | -100.00 | 0.00 | 0.20 |
| totals over | price band -150..-100 | 1,625 | 783 | 842 | 0 | -187.17 | -10.01 | -13.83 | -6.33 | 99.80 |
| totals under | early half of each season | 801 | 427 | 374 | 0 | -4.45 | -0.48 | -6.12 | 5.50 |  |
| totals under | late half of each season | 827 | 438 | 388 | 1 | -11.06 | -1.16 | -6.39 | 4.11 |  |
| totals under | without its 10 best dates | 1,577 | 814 | 762 | 1 | -66.51 | -3.65 | -7.17 | 0.00 |  |
| totals under | price band +100..+150 | 2 | 1 | 1 | 0 | 0.00 | 0.00 | -100.00 | 100.00 | 0.10 |
| totals under | price band -150..-100 | 1,626 | 864 | 761 | 1 | -15.51 | -0.83 | -4.48 | 3.11 | 99.90 |
| spreads home | early half of each season | 801 | 428 | 372 | 1 | -0.89 | -0.10 | -5.27 | 4.42 |  |
| spreads home | late half of each season | 828 | 428 | 399 | 1 | -34.71 | -3.62 | -9.66 | 2.11 |  |
| spreads home | without its 10 best dates | 1,578 | 808 | 769 | 1 | -81.45 | -4.46 | -7.93 | -0.85 |  |
| spreads home | price band +100..+150 | 28 | 17 | 11 | 0 | 6.65 | 23.75 | -5.54 | 51.12 | 1.70 |
| spreads home | price band -150..-100 | 1,601 | 839 | 760 | 2 | -42.25 | -2.28 | -5.92 | 1.35 | 98.30 |
| spreads away | early half of each season | 801 | 383 | 416 | 2 | -95.96 | -10.43 | -15.04 | -5.03 |  |
| spreads away | late half of each season | 828 | 406 | 422 | 0 | -78.25 | -8.22 | -14.02 | -2.07 |  |
| spreads away | without its 10 best dates | 1,581 | 743 | 836 | 2 | -217.94 | -12.00 | -15.36 | -8.36 |  |
| spreads away | price band +100..+150 | 50 | 30 | 20 | 0 | 11.30 | 22.60 | -1.91 | 47.77 | 3.10 |
| spreads away | price band -150..-100 | 1,579 | 759 | 818 | 2 | -185.51 | -10.19 | -14.11 | -6.13 | 96.90 |
| spreads favourite | early half of each season | 785 | 373 | 411 | 1 | -98.69 | -10.97 | -16.40 | -5.87 |  |
| spreads favourite | late half of each season | 818 | 421 | 396 | 1 | -34.34 | -3.65 | -9.38 | 2.29 |  |
| spreads favourite | without its 10 best dates | 1,560 | 751 | 807 | 2 | -176.03 | -9.83 | -13.61 | -6.21 |  |
| spreads favourite | price band +100..+150 | 51 | 29 | 22 | 0 | 8.15 | 15.98 | -4.28 | 36.08 | 3.20 |
| spreads favourite | price band -150..-100 | 1,552 | 765 | 785 | 2 | -141.18 | -7.89 | -11.94 | -3.89 | 96.80 |
| spreads underdog | early half of each season | 813 | 436 | 375 | 2 | 2.09 | 0.22 | -4.64 | 5.43 |  |
| spreads underdog | late half of each season | 842 | 415 | 427 | 0 | -78.87 | -8.09 | -14.03 | -3.00 |  |
| spreads underdog | without its 10 best dates | 1,601 | 801 | 798 | 2 | -122.07 | -6.59 | -10.24 | -2.87 |  |
| spreads underdog | price band +100..+150 | 27 | 18 | 9 | 0 | 9.80 | 36.30 | 6.11 | 66.48 | 1.60 |
| spreads underdog | price band -150..-100 | 1,628 | 833 | 793 | 2 | -86.58 | -4.59 | -8.49 | -0.76 | 98.40 |
| h2h home | early half of each season | 785 | 492 | 293 | 0 | 40.73 | 2.62 | -2.29 | 7.13 |  |
| h2h home | late half of each season | 799 | 504 | 295 | 0 | 10.79 | 0.67 | -3.70 | 4.89 |  |
| h2h home | without its 10 best dates | 1,530 | 952 | 578 | 0 | -57.15 | -1.86 | -4.47 | 0.84 |  |
| h2h home | price band +100..+150 | 163 | 74 | 89 | 0 | -0.28 | -0.17 | -14.94 | 14.01 | 10.30 |
| h2h home | price band -150..-100 | 194 | 100 | 94 | 0 | -17.66 | -7.20 | -17.22 | 2.31 | 12.20 |
| h2h home | price band -300..-151 | 318 | 234 | 84 | 0 | 59.25 | 8.49 | 3.09 | 13.96 | 20.10 |
| h2h home | price band < -300 | 580 | 509 | 71 | 0 | -6.91 | -0.40 | -3.01 | 2.18 | 36.60 |
| h2h home | price band > +150 | 329 | 79 | 250 | 0 | 17.12 | 5.20 | -16.79 | 25.94 | 20.80 |
| h2h away | early half of each season | 785 | 293 | 492 | 0 | -170.75 | -15.29 | -22.02 | -7.45 |  |
| h2h away | late half of each season | 799 | 295 | 504 | 0 | -186.28 | -16.48 | -21.97 | -10.27 |  |
| h2h away | without its 10 best dates | 1,541 | 559 | 982 | 0 | -456.12 | -20.89 | -24.95 | -16.76 |  |
| h2h away | price band +100..+150 | 195 | 79 | 116 | 0 | -20.80 | -10.67 | -23.18 | 2.59 | 12.30 |
| h2h away | price band -150..-100 | 182 | 94 | 88 | 0 | -15.46 | -6.81 | -17.40 | 3.21 | 11.50 |
| h2h away | price band -300..-151 | 196 | 126 | 70 | 0 | -14.17 | -3.47 | -11.63 | 4.70 | 12.40 |
| h2h away | price band < -300 | 203 | 164 | 39 | 0 | -39.02 | -6.41 | -12.52 | -0.85 | 12.80 |
| h2h away | price band > +150 | 808 | 125 | 683 | 0 | -267.58 | -33.12 | -42.94 | -22.18 | 51.00 |
| h2h favourite | early half of each season | 744 | 556 | 188 | 0 | -19.68 | -1.07 | -4.16 | 2.07 |  |
| h2h favourite | late half of each season | 760 | 588 | 172 | 0 | -0.21 | -0.01 | -2.79 | 2.89 |  |
| h2h favourite | without its 10 best dates | 1,449 | 1,090 | 359 | 0 | -63.05 | -1.75 | -3.95 | 0.34 |  |
| h2h favourite | price band -150..-100 | 207 | 111 | 96 | 0 | -19.03 | -6.76 | -16.37 | 3.09 | 13.80 |
| h2h favourite | price band -300..-151 | 514 | 360 | 154 | 0 | 45.08 | 4.08 | -0.97 | 8.89 | 34.20 |
| h2h favourite | price band < -300 | 783 | 673 | 110 | 0 | -45.94 | -1.96 | -4.49 | 0.48 | 52.10 |
| h2h underdog | early half of each season | 761 | 197 | 564 | 0 | -103.92 | -13.63 | -24.19 | -2.16 |  |
| h2h underdog | late half of each season | 782 | 183 | 599 | 0 | -171.51 | -21.88 | -31.87 | -11.56 |  |
| h2h underdog | without its 10 best dates | 1,496 | 358 | 1,138 | 0 | -399.33 | -26.64 | -32.12 | -20.83 |  |
| h2h underdog | price band +100..+150 | 358 | 153 | 205 | 0 | -21.08 | -5.89 | -15.86 | 3.57 | 23.20 |
| h2h underdog | price band -150..-100 | 48 | 23 | 25 | 0 | -3.89 | -7.59 | -25.42 | 9.76 | 3.10 |
| h2h underdog | price band > +150 | 1,137 | 204 | 933 | 0 | -250.46 | -22.03 | -31.17 | -12.01 | 73.70 |

### What the sample resolves (blind bet at the best decidable price, all seasons)

| market | side | bets | half-width of the 90% interval |
|---|---|---|---|
| totals | over | 1,628 | 3.74 |
| spreads | home | 1,629 | 3.64 |
| h2h | favourite | 1,504 | 1.99 |

## 3. The women's college halftime method, ported unchanged, then the variants

Script: `scripts/euroleague_research/r4_ported.py`.

### The fitted constants per walk-forward fold (read at the half, f = 0.5)

| graded season | fitted on | states | total: share of prior still to come at the half | total: share of the surprise carried | total: sd at the half | margin: share of prior still to come | margin: share of the surprise carried | margin: sd at the half |
|---|---|---|---|---|---|---|---|---|
| 2021-22 | 2022-23 | 24,298 | 0.51 | 0.05 | 12.31 | 0.55 | -0.28 | 9.19 |
| 2022-23 | 2021-22 | 21,932 | 0.51 | 0.11 | 12.37 | 0.38 | -0.19 | 9.27 |
| 2023-24 | 2021-22,2022-23 | 46,230 | 0.51 | 0.08 | 12.34 | 0.47 | -0.23 | 9.26 |
| 2024-25 | 2021-22,2022-23,2023-24 | 71,401 | 0.51 | 0.04 | 12.60 | 0.48 | -0.25 | 9.23 |
| 2025-26 | 2021-22,2022-23,2023-24,2024-25 | 95,707 | 0.51 | 0.05 | 12.28 | 0.46 | -0.25 | 9.25 |
| 2026-27 to 11-12 | 2021-22,2022-23,2023-24,2024-25,2025-26 | 125,453 | 0.51 | 0.07 | 12.31 | 0.46 | -0.27 | 9.23 |

### Out of sample at the break: the model against what happened in the second half

`mean error` = actual second-half points (or margin) minus the model's mean; `sd ratio` = the standard deviation of (error / the model's sd), 1.0 when the stated spread is right.

| season | games | total: mean error | total: sd ratio | margin: mean error | margin: sd ratio |
|---|---|---|---|---|---|
| 2021-22 | 278 | -1.77 | 1.01 | 0.67 | 1.01 |
| 2022-23 | 308 | -0.72 | 0.99 | 1.17 | 0.99 |
| 2023-24 | 319 | -1.61 | 1.05 | 0.38 | 0.99 |
| 2024-25 | 308 | -0.02 | 0.88 | -0.13 | 1.02 |
| 2025-26 | 377 | -1.36 | 1.02 | 0.54 | 0.99 |
| 2026-27 to 11-12 | 105 | -0.37 | 0.97 | -0.96 | 0.86 |

### How many games the ported rule can decide

| market | season | games with a read in the break | decided (an eligible quote) | games with a fresh decidable quote but none in the price band | games where fewer than 2 other books quote |
|---|---|---|---|---|---|
| totals | 2021-22 | 276 | 255 | 0 | 1 |
| totals | 2022-23 | 308 | 283 | 0 | 2 |
| totals | 2023-24 | 315 | 312 | 0 | 1 |
| totals | 2024-25 | 294 | 285 | 0 | 9 |
| totals | 2025-26 | 376 | 374 | 0 | 2 |
| totals | 2026-27 to 11-12 | 104 | 104 | 0 | 0 |
| spreads | 2021-22 | 276 | 256 | 0 | 1 |
| spreads | 2022-23 | 308 | 281 | 0 | 4 |
| spreads | 2023-24 | 315 | 312 | 0 | 1 |
| spreads | 2024-25 | 294 | 294 | 0 | 0 |
| spreads | 2025-26 | 376 | 376 | 0 | 0 |
| spreads | 2026-27 to 11-12 | 104 | 104 | 0 | 0 |
| h2h | 2021-22 | 276 | 117 | 142 | 3 |
| h2h | 2022-23 | 308 | 133 | 143 | 0 |
| h2h | 2023-24 | 315 | 132 | 165 | 0 |
| h2h | 2024-25 | 294 | 121 | 149 | 0 |
| h2h | 2025-26 | 376 | 189 | 184 | 2 |
| h2h | 2026-27 to 11-12 | 104 | 46 | 56 | 2 |

### The ported rule, unchanged: first read in the break with an eligible quote, best EV there

Walk-forward rows pool 2022-23 to 2026-27; 2021-22 is a second look (fitted on 2022-23) and is not pooled.

| rule | market | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ported unchanged | total | 0.020 | walk-forward 2022-23 to 2026-27 | 811 | 407 | 404 | 0 | -54.23 | -5.86 | -11.56 | -0.56 |
| ported unchanged | total | 0.020 | 2021-22 (second look, not walk-forward) | 88 | 46 | 42 | 0 | -1.20 | -1.21 | -19.00 | 14.89 |
| ported unchanged | total | 0.020 | 2022-23 | 123 | 58 | 65 | 0 | -16.75 | -11.84 | -26.84 | 0.16 |
| ported unchanged | total | 0.020 | 2023-24 | 156 | 76 | 80 | 0 | -16.00 | -8.92 | -19.68 | 1.98 |
| ported unchanged | total | 0.020 | 2024-25 | 135 | 68 | 67 | 0 | -9.05 | -5.83 | -19.88 | 8.17 |
| ported unchanged | total | 0.020 | 2025-26 | 309 | 159 | 150 | 0 | -10.81 | -3.09 | -12.91 | 7.19 |
| ported unchanged | total | 0.020 | 2026-27 to 11-12 | 88 | 46 | 42 | 0 | -1.62 | -1.61 | -18.08 | 15.13 |
| ported unchanged | total | 0.030 | walk-forward 2022-23 to 2026-27 | 724 | 367 | 357 | 0 | -40.38 | -4.89 | -11.03 | 0.74 |
| ported unchanged | total | 0.030 | 2021-22 (second look, not walk-forward) | 73 | 39 | 34 | 0 | 0.80 | 0.97 | -18.13 | 20.59 |
| ported unchanged | total | 0.030 | 2022-23 | 102 | 49 | 53 | 0 | -11.95 | -10.19 | -23.25 | 2.72 |
| ported unchanged | total | 0.030 | 2023-24 | 134 | 66 | 68 | 0 | -12.20 | -7.92 | -18.55 | 2.57 |
| ported unchanged | total | 0.030 | 2024-25 | 118 | 59 | 59 | 0 | -8.85 | -6.52 | -20.55 | 9.06 |
| ported unchanged | total | 0.030 | 2025-26 | 286 | 149 | 137 | 0 | -6.06 | -1.87 | -12.53 | 8.62 |
| ported unchanged | total | 0.030 | 2026-27 to 11-12 | 84 | 44 | 40 | 0 | -1.32 | -1.38 | -20.09 | 16.50 |
| ported unchanged | total | 0.050 | walk-forward 2022-23 to 2026-27 | 574 | 300 | 274 | 0 | -12.61 | -1.93 | -8.44 | 4.23 |
| ported unchanged | total | 0.050 | 2021-22 (second look, not walk-forward) | 43 | 24 | 19 | 0 | 2.70 | 5.56 | -17.56 | 28.44 |
| ported unchanged | total | 0.050 | 2022-23 | 75 | 38 | 37 | 0 | -4.55 | -5.28 | -19.55 | 8.35 |
| ported unchanged | total | 0.050 | 2023-24 | 102 | 52 | 50 | 0 | -5.50 | -4.69 | -18.10 | 8.44 |
| ported unchanged | total | 0.050 | 2024-25 | 92 | 47 | 45 | 0 | -4.75 | -4.49 | -21.20 | 13.91 |
| ported unchanged | total | 0.050 | 2025-26 | 232 | 125 | 107 | 0 | 3.69 | 1.41 | -9.37 | 12.93 |
| ported unchanged | total | 0.050 | 2026-27 to 11-12 | 73 | 38 | 35 | 0 | -1.50 | -1.80 | -21.65 | 16.20 |
| ported unchanged | total | 0.080 | walk-forward 2022-23 to 2026-27 | 341 | 183 | 158 | 0 | 2.93 | 0.75 | -8.08 | 9.25 |
| ported unchanged | total | 0.080 | 2021-22 (second look, not walk-forward) | 10 | 6 | 4 | 0 | 1.50 | 13.10 | -42.36 | 51.12 |
| ported unchanged | total | 0.080 | 2022-23 | 36 | 17 | 19 | 0 | -4.85 | -11.71 | -35.73 | 13.16 |
| ported unchanged | total | 0.080 | 2023-24 | 54 | 27 | 27 | 0 | -4.05 | -6.52 | -25.95 | 12.88 |
| ported unchanged | total | 0.080 | 2024-25 | 51 | 24 | 27 | 0 | -7.05 | -12.02 | -31.32 | 9.97 |
| ported unchanged | total | 0.080 | 2025-26 | 148 | 87 | 61 | 0 | 17.94 | 10.74 | -3.35 | 24.46 |
| ported unchanged | total | 0.080 | 2026-27 to 11-12 | 52 | 28 | 24 | 0 | 0.94 | 1.58 | -18.70 | 20.55 |
| ported unchanged | total | 0.120 | walk-forward 2022-23 to 2026-27 | 120 | 68 | 52 | 0 | 9.25 | 6.80 | -7.91 | 20.44 |
| ported unchanged | total | 0.120 | 2021-22 (second look, not walk-forward) | 2 | 1 | 1 | 0 | -0.15 | -6.67 | -100.00 | 90.91 |
| ported unchanged | total | 0.120 | 2022-23 | 7 | 4 | 3 | 0 | 0.55 | 6.83 | -46.58 | 60.25 |
| ported unchanged | total | 0.120 | 2023-24 | 17 | 9 | 8 | 0 | -0.20 | -1.02 | -34.02 | 31.97 |
| ported unchanged | total | 0.120 | 2024-25 | 16 | 6 | 10 | 0 | -5.50 | -29.89 | -60.64 | 9.06 |
| ported unchanged | total | 0.120 | 2025-26 | 63 | 41 | 22 | 0 | 16.23 | 22.91 | 4.03 | 42.26 |
| ported unchanged | total | 0.120 | 2026-27 to 11-12 | 17 | 8 | 9 | 0 | -1.83 | -9.51 | -49.68 | 34.47 |
| ported unchanged | spread | 0.020 | walk-forward 2022-23 to 2026-27 | 518 | 296 | 222 | 0 | 42.74 | 7.23 | 0.61 | 14.06 |
| ported unchanged | spread | 0.020 | 2021-22 (second look, not walk-forward) | 65 | 33 | 32 | 0 | -3.70 | -4.94 | -24.38 | 14.57 |
| ported unchanged | spread | 0.020 | 2022-23 | 115 | 67 | 48 | 0 | 11.90 | 9.04 | -6.55 | 24.46 |
| ported unchanged | spread | 0.020 | 2023-24 | 99 | 50 | 49 | 0 | -5.95 | -5.25 | -19.44 | 10.32 |
| ported unchanged | spread | 0.020 | 2024-25 | 94 | 58 | 36 | 0 | 17.60 | 16.48 | 1.08 | 30.16 |
| ported unchanged | spread | 0.020 | 2025-26 | 165 | 90 | 75 | 0 | 4.00 | 2.12 | -9.68 | 13.56 |
| ported unchanged | spread | 0.020 | 2026-27 to 11-12 | 45 | 31 | 14 | 0 | 15.19 | 30.02 | 10.69 | 47.49 |
| ported unchanged | spread | 0.030 | walk-forward 2022-23 to 2026-27 | 449 | 261 | 188 | 0 | 46.61 | 9.10 | 1.87 | 16.14 |
| ported unchanged | spread | 0.030 | 2021-22 (second look, not walk-forward) | 48 | 25 | 23 | 0 | -1.40 | -2.52 | -26.21 | 18.79 |
| ported unchanged | spread | 0.030 | 2022-23 | 102 | 59 | 43 | 0 | 9.65 | 8.27 | -6.88 | 23.43 |
| ported unchanged | spread | 0.030 | 2023-24 | 81 | 43 | 38 | 0 | -0.45 | -0.48 | -18.29 | 18.12 |
| ported unchanged | spread | 0.030 | 2024-25 | 79 | 50 | 29 | 0 | 17.45 | 19.42 | 2.33 | 35.46 |
| ported unchanged | spread | 0.030 | 2025-26 | 147 | 80 | 67 | 0 | 3.26 | 1.94 | -11.66 | 14.82 |
| ported unchanged | spread | 0.030 | 2026-27 to 11-12 | 40 | 29 | 11 | 0 | 16.70 | 37.29 | 17.14 | 52.77 |
| ported unchanged | spread | 0.050 | walk-forward 2022-23 to 2026-27 | 312 | 180 | 132 | 0 | 29.80 | 8.37 | -0.06 | 16.33 |
| ported unchanged | spread | 0.050 | 2021-22 (second look, not walk-forward) | 36 | 16 | 20 | 0 | -7.10 | -17.01 | -40.98 | 6.96 |
| ported unchanged | spread | 0.050 | 2022-23 | 84 | 47 | 37 | 0 | 4.55 | 4.73 | -12.19 | 21.78 |
| ported unchanged | spread | 0.050 | 2023-24 | 50 | 26 | 24 | 0 | -1.45 | -2.53 | -23.72 | 19.95 |
| ported unchanged | spread | 0.050 | 2024-25 | 52 | 32 | 20 | 0 | 9.70 | 16.47 | -3.36 | 37.62 |
| ported unchanged | spread | 0.050 | 2025-26 | 100 | 55 | 45 | 0 | 3.70 | 3.23 | -13.04 | 19.15 |
| ported unchanged | spread | 0.050 | 2026-27 to 11-12 | 26 | 20 | 6 | 0 | 13.30 | 45.74 | 19.81 | 65.97 |
| ported unchanged | spread | 0.080 | walk-forward 2022-23 to 2026-27 | 177 | 108 | 69 | 0 | 30.16 | 15.03 | 3.36 | 26.10 |
| ported unchanged | spread | 0.080 | 2021-22 (second look, not walk-forward) | 11 | 7 | 4 | 0 | 2.20 | 17.25 | -33.73 | 53.69 |
| ported unchanged | spread | 0.080 | 2022-23 | 48 | 28 | 20 | 0 | 5.05 | 9.21 | -12.26 | 28.13 |
| ported unchanged | spread | 0.080 | 2023-24 | 26 | 12 | 14 | 0 | -3.95 | -13.41 | -44.77 | 18.83 |
| ported unchanged | spread | 0.080 | 2024-25 | 30 | 22 | 8 | 0 | 13.20 | 38.94 | 15.32 | 61.90 |
| ported unchanged | spread | 0.080 | 2025-26 | 53 | 30 | 23 | 0 | 4.28 | 7.12 | -14.23 | 26.71 |
| ported unchanged | spread | 0.080 | 2026-27 to 11-12 | 20 | 16 | 4 | 0 | 11.58 | 51.74 | 23.62 | 72.98 |
| ported unchanged | spread | 0.120 | walk-forward 2022-23 to 2026-27 | 86 | 47 | 39 | 0 | 3.19 | 3.28 | -13.11 | 21.81 |
| ported unchanged | spread | 0.120 | 2021-22 (second look, not walk-forward) | 4 | 2 | 2 | 0 | -0.40 | -8.70 | -100.00 | 44.04 |
| ported unchanged | spread | 0.120 | 2022-23 | 26 | 13 | 13 | 0 | -1.70 | -5.79 | -36.69 | 25.65 |
| ported unchanged | spread | 0.120 | 2023-24 | 15 | 6 | 9 | 0 | -4.35 | -25.22 | -68.84 | 20.19 |
| ported unchanged | spread | 0.120 | 2024-25 | 16 | 11 | 5 | 0 | 5.40 | 29.59 | -5.76 | 63.45 |
| ported unchanged | spread | 0.120 | 2025-26 | 25 | 14 | 11 | 0 | 1.89 | 6.67 | -23.68 | 37.21 |
| ported unchanged | spread | 0.120 | 2026-27 to 11-12 | 4 | 3 | 1 | 0 | 1.95 | 46.99 | -2.44 | 97.56 |
| ported unchanged | moneyline | 0.020 | walk-forward 2022-23 to 2026-27 | 252 | 135 | 117 | 0 | 7.28 | 2.12 | -8.43 | 12.27 |
| ported unchanged | moneyline | 0.020 | 2021-22 (second look, not walk-forward) | 30 | 21 | 9 | 0 | 11.57 | 26.43 | 3.89 | 50.08 |
| ported unchanged | moneyline | 0.020 | 2022-23 | 67 | 35 | 32 | 0 | -2.45 | -2.57 | -21.23 | 15.03 |
| ported unchanged | moneyline | 0.020 | 2023-24 | 43 | 19 | 24 | 0 | -11.95 | -19.59 | -38.73 | 0.98 |
| ported unchanged | moneyline | 0.020 | 2024-25 | 44 | 27 | 17 | 0 | 7.25 | 11.86 | -10.38 | 35.92 |
| ported unchanged | moneyline | 0.020 | 2025-26 | 80 | 43 | 37 | 0 | 9.11 | 8.70 | -9.53 | 27.93 |
| ported unchanged | moneyline | 0.020 | 2026-27 to 11-12 | 18 | 11 | 7 | 0 | 5.32 | 25.19 | -9.55 | 57.23 |
| ported unchanged | moneyline | 0.030 | walk-forward 2022-23 to 2026-27 | 221 | 119 | 102 | 0 | 9.81 | 3.30 | -7.05 | 14.58 |
| ported unchanged | moneyline | 0.030 | 2021-22 (second look, not walk-forward) | 19 | 13 | 6 | 0 | 7.15 | 27.37 | 2.46 | 51.35 |
| ported unchanged | moneyline | 0.030 | 2022-23 | 59 | 31 | 28 | 0 | -1.90 | -2.28 | -22.35 | 16.98 |
| ported unchanged | moneyline | 0.030 | 2023-24 | 39 | 17 | 22 | 0 | -11.25 | -20.66 | -41.24 | -0.33 |
| ported unchanged | moneyline | 0.030 | 2024-25 | 38 | 23 | 15 | 0 | 6.05 | 11.59 | -14.57 | 37.48 |
| ported unchanged | moneyline | 0.030 | 2025-26 | 68 | 38 | 30 | 0 | 12.59 | 14.19 | -7.18 | 36.08 |
| ported unchanged | moneyline | 0.030 | 2026-27 to 11-12 | 17 | 10 | 7 | 0 | 4.32 | 23.02 | -11.32 | 60.65 |
| ported unchanged | moneyline | 0.050 | walk-forward 2022-23 to 2026-27 | 164 | 84 | 80 | 0 | -0.51 | -0.24 | -13.25 | 12.85 |
| ported unchanged | moneyline | 0.050 | 2021-22 (second look, not walk-forward) | 10 | 7 | 3 | 0 | 4.50 | 34.97 | -1.28 | 68.14 |
| ported unchanged | moneyline | 0.050 | 2022-23 | 48 | 23 | 25 | 0 | -6.20 | -9.45 | -31.58 | 13.96 |
| ported unchanged | moneyline | 0.050 | 2023-24 | 31 | 14 | 17 | 0 | -6.47 | -15.47 | -39.08 | 5.77 |
| ported unchanged | moneyline | 0.050 | 2024-25 | 26 | 15 | 11 | 0 | 2.57 | 7.57 | -22.46 | 39.61 |
| ported unchanged | moneyline | 0.050 | 2025-26 | 47 | 24 | 23 | 0 | 4.09 | 6.79 | -18.87 | 33.39 |
| ported unchanged | moneyline | 0.050 | 2026-27 to 11-12 | 12 | 8 | 4 | 0 | 5.50 | 41.76 | 3.90 | 82.79 |
| ported unchanged | moneyline | 0.080 | walk-forward 2022-23 to 2026-27 | 96 | 50 | 46 | 0 | 4.12 | 3.37 | -12.38 | 19.36 |
| ported unchanged | moneyline | 0.080 | 2021-22 (second look, not walk-forward) | 3 | 2 | 1 | 0 | 1.00 | 24.21 | -28.65 | 64.94 |
| ported unchanged | moneyline | 0.080 | 2022-23 | 32 | 13 | 19 | 0 | -8.00 | -18.43 | -45.65 | 10.40 |
| ported unchanged | moneyline | 0.080 | 2023-24 | 15 | 5 | 10 | 0 | -6.66 | -35.94 | -73.52 | -4.44 |
| ported unchanged | moneyline | 0.080 | 2024-25 | 12 | 8 | 4 | 0 | 3.84 | 26.25 | -21.48 | 77.31 |
| ported unchanged | moneyline | 0.080 | 2025-26 | 29 | 18 | 11 | 0 | 9.29 | 25.04 | -9.79 | 61.90 |
| ported unchanged | moneyline | 0.080 | 2026-27 to 11-12 | 8 | 6 | 2 | 0 | 5.65 | 66.71 | 18.34 | 120.16 |
| ported unchanged | moneyline | 0.120 | walk-forward 2022-23 to 2026-27 | 48 | 21 | 27 | 0 | -1.17 | -2.13 | -28.86 | 28.17 |
| ported unchanged | moneyline | 0.120 | 2021-22 (second look, not walk-forward) | 2 | 1 | 1 | 0 | 0.00 | 0.00 | -100.00 | 67.11 |
| ported unchanged | moneyline | 0.120 | 2022-23 | 18 | 5 | 13 | 0 | -9.40 | -41.59 | -77.12 | -3.47 |
| ported unchanged | moneyline | 0.120 | 2023-24 | 6 | 2 | 4 | 0 | -1.86 | -30.24 | -100.00 | 43.00 |
| ported unchanged | moneyline | 0.120 | 2024-25 | 8 | 5 | 3 | 0 | 2.94 | 32.31 | -22.89 | 82.66 |
| ported unchanged | moneyline | 0.120 | 2025-26 | 13 | 7 | 6 | 0 | 4.80 | 33.92 | -31.02 | 109.37 |
| ported unchanged | moneyline | 0.120 | 2026-27 to 11-12 | 3 | 2 | 1 | 0 | 2.35 | 78.33 | -21.67 | 178.33 |

### Return by claimed EV band, every decided game, walk-forward seasons (bands, not nested cuts)

| market | claimed EV band | bets | W | L | P | units | ret% | lo% | hi% |
|---|---|---|---|---|---|---|---|---|---|
| total | < 0 | 365 | 176 | 189 | 0 | -41.19 | -9.82 | -18.44 | -2.17 |
| total | 0-0.02 | 182 | 96 | 86 | 0 | -2.68 | -1.28 | -13.05 | 9.49 |
| total | 0.02-0.05 | 237 | 107 | 130 | 0 | -41.62 | -15.34 | -26.05 | -4.89 |
| total | 0.05-0.08 | 233 | 117 | 116 | 0 | -15.54 | -5.84 | -15.70 | 3.57 |
| total | 0.08-0.12 | 221 | 115 | 106 | 0 | -6.32 | -2.50 | -12.45 | 8.04 |
| total | 0.12-0.20 | 108 | 58 | 50 | 0 | 1.55 | 1.27 | -13.58 | 15.71 |
| total | >= 0.20 | 12 | 10 | 2 | 0 | 7.70 | 56.66 | 24.73 | 88.96 |
| spread | < 0 | 645 | 331 | 313 | 1 | -28.88 | -3.90 | -10.55 | 2.15 |
| spread | 0-0.02 | 204 | 103 | 101 | 0 | -12.25 | -5.22 | -15.54 | 4.47 |
| spread | 0.02-0.05 | 206 | 116 | 90 | 0 | 12.94 | 5.51 | -5.53 | 16.62 |
| spread | 0.05-0.08 | 135 | 72 | 63 | 0 | -0.36 | -0.23 | -13.22 | 14.06 |
| spread | 0.08-0.12 | 91 | 61 | 30 | 0 | 26.97 | 26.09 | 11.09 | 40.49 |
| spread | 0.12-0.20 | 73 | 40 | 33 | 0 | 2.94 | 3.56 | -15.07 | 21.56 |
| spread | >= 0.20 | 13 | 7 | 6 | 0 | 0.25 | 1.68 | -41.75 | 45.24 |
| moneyline | < 0 | 288 | 152 | 136 | 0 | -9.51 | -2.27 | -10.36 | 5.85 |
| moneyline | 0-0.02 | 81 | 47 | 34 | 0 | 8.96 | 7.69 | -6.33 | 21.19 |
| moneyline | 0.02-0.05 | 88 | 51 | 37 | 0 | 7.79 | 6.06 | -10.86 | 21.89 |
| moneyline | 0.05-0.08 | 68 | 34 | 34 | 0 | -4.63 | -5.00 | -22.13 | 11.73 |
| moneyline | 0.08-0.12 | 48 | 29 | 19 | 0 | 5.29 | 7.88 | -13.71 | 28.73 |
| moneyline | 0.12-0.20 | 40 | 18 | 22 | 0 | -2.02 | -4.30 | -32.67 | 25.92 |
| moneyline | >= 0.20 | 8 | 3 | 5 | 0 | 0.85 | 10.62 | -58.75 | 98.12 |

### Claimed chance against won, every decided game (pushes out), walk-forward seasons

| market | claimed band | games | claimed | won |
|---|---|---|---|---|
| total | [0.0, 0.52) | 192 | 0.51 | 0.46 |
| total | [0.52, 0.55) | 462 | 0.54 | 0.49 |
| total | [0.55, 0.58) | 418 | 0.56 | 0.51 |
| total | [0.58, 0.62) | 250 | 0.59 | 0.51 |
| total | [0.62, 0.7) | 35 | 0.64 | 0.63 |
| total | [0.7, 1.01) | 1 | 0.72 | 1.00 |
| spread | [0.0, 0.52) | 387 | 0.51 | 0.53 |
| spread | [0.52, 0.55) | 529 | 0.54 | 0.51 |
| spread | [0.55, 0.58) | 290 | 0.56 | 0.55 |
| spread | [0.58, 0.62) | 127 | 0.60 | 0.63 |
| spread | [0.62, 0.7) | 33 | 0.64 | 0.55 |
| moneyline | [0.0, 0.52) | 237 | 0.41 | 0.40 |
| moneyline | [0.52, 0.55) | 53 | 0.54 | 0.45 |
| moneyline | [0.55, 0.58) | 46 | 0.56 | 0.56 |
| moneyline | [0.58, 0.62) | 85 | 0.60 | 0.64 |
| moneyline | [0.62, 0.7) | 153 | 0.66 | 0.66 |
| moneyline | [0.7, 1.01) | 47 | 0.73 | 0.72 |

### Variants V1-V4, pooled walk-forward 2022-23 to 2026-27

| rule | market | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V1 no minimum of other books | total | 0.020 | walk-forward 2022-23 to 2026-27 | 819 | 409 | 410 | 0 | -59.18 | -6.33 | -11.81 | -0.71 |
| V1 no minimum of other books | total | 0.030 | walk-forward 2022-23 to 2026-27 | 732 | 369 | 363 | 0 | -45.33 | -5.43 | -11.30 | 0.80 |
| V1 no minimum of other books | total | 0.050 | walk-forward 2022-23 to 2026-27 | 582 | 302 | 280 | 0 | -17.56 | -2.65 | -9.25 | 3.72 |
| V1 no minimum of other books | total | 0.080 | walk-forward 2022-23 to 2026-27 | 345 | 185 | 160 | 0 | 2.58 | 0.66 | -8.21 | 8.57 |
| V1 no minimum of other books | total | 0.120 | walk-forward 2022-23 to 2026-27 | 121 | 69 | 52 | 0 | 10.25 | 7.47 | -6.47 | 22.35 |
| V1 no minimum of other books | spread | 0.020 | walk-forward 2022-23 to 2026-27 | 520 | 297 | 223 | 0 | 42.59 | 7.18 | 0.51 | 13.99 |
| V1 no minimum of other books | spread | 0.030 | walk-forward 2022-23 to 2026-27 | 451 | 262 | 189 | 0 | 46.46 | 9.03 | 1.75 | 16.07 |
| V1 no minimum of other books | spread | 0.050 | walk-forward 2022-23 to 2026-27 | 313 | 180 | 133 | 0 | 28.65 | 8.02 | -0.26 | 16.12 |
| V1 no minimum of other books | spread | 0.080 | walk-forward 2022-23 to 2026-27 | 178 | 108 | 70 | 0 | 29.01 | 14.37 | 2.52 | 25.34 |
| V1 no minimum of other books | spread | 0.120 | walk-forward 2022-23 to 2026-27 | 87 | 47 | 40 | 0 | 2.04 | 2.07 | -14.22 | 20.04 |
| V1 no minimum of other books | moneyline | 0.020 | walk-forward 2022-23 to 2026-27 | 252 | 135 | 117 | 0 | 7.28 | 2.12 | -8.43 | 12.27 |
| V1 no minimum of other books | moneyline | 0.030 | walk-forward 2022-23 to 2026-27 | 221 | 119 | 102 | 0 | 9.81 | 3.30 | -7.05 | 14.58 |
| V1 no minimum of other books | moneyline | 0.050 | walk-forward 2022-23 to 2026-27 | 164 | 84 | 80 | 0 | -0.51 | -0.24 | -13.25 | 12.85 |
| V1 no minimum of other books | moneyline | 0.080 | walk-forward 2022-23 to 2026-27 | 96 | 50 | 46 | 0 | 4.12 | 3.37 | -12.38 | 19.36 |
| V1 no minimum of other books | moneyline | 0.120 | walk-forward 2022-23 to 2026-27 | 48 | 21 | 27 | 0 | -1.17 | -2.13 | -28.86 | 28.17 |
| V2 Pinnacle's close as the prior | total | 0.020 | walk-forward 2022-23 to 2026-27 | 726 | 362 | 364 | 0 | -53.30 | -6.44 | -12.71 | -0.63 |
| V2 Pinnacle's close as the prior | total | 0.030 | walk-forward 2022-23 to 2026-27 | 662 | 335 | 327 | 0 | -38.13 | -5.05 | -11.45 | 1.45 |
| V2 Pinnacle's close as the prior | total | 0.050 | walk-forward 2022-23 to 2026-27 | 509 | 261 | 248 | 0 | -21.79 | -3.76 | -10.78 | 3.27 |
| V2 Pinnacle's close as the prior | total | 0.080 | walk-forward 2022-23 to 2026-27 | 295 | 160 | 135 | 0 | 6.39 | 1.90 | -7.70 | 10.93 |
| V2 Pinnacle's close as the prior | total | 0.120 | walk-forward 2022-23 to 2026-27 | 119 | 67 | 52 | 0 | 8.20 | 6.07 | -7.94 | 20.80 |
| V2 Pinnacle's close as the prior | spread | 0.020 | walk-forward 2022-23 to 2026-27 | 552 | 307 | 245 | 0 | 28.03 | 4.45 | -2.25 | 10.93 |
| V2 Pinnacle's close as the prior | spread | 0.030 | walk-forward 2022-23 to 2026-27 | 476 | 272 | 204 | 0 | 39.68 | 7.31 | 0.37 | 14.17 |
| V2 Pinnacle's close as the prior | spread | 0.050 | walk-forward 2022-23 to 2026-27 | 364 | 215 | 149 | 0 | 45.34 | 10.93 | 3.40 | 18.48 |
| V2 Pinnacle's close as the prior | spread | 0.080 | walk-forward 2022-23 to 2026-27 | 227 | 135 | 92 | 0 | 30.93 | 11.98 | 1.89 | 21.71 |
| V2 Pinnacle's close as the prior | spread | 0.120 | walk-forward 2022-23 to 2026-27 | 117 | 73 | 44 | 0 | 23.36 | 17.59 | 3.19 | 30.45 |
| V2 Pinnacle's close as the prior | moneyline | 0.020 | walk-forward 2022-23 to 2026-27 | 275 | 145 | 130 | 0 | 7.14 | 1.94 | -7.84 | 11.48 |
| V2 Pinnacle's close as the prior | moneyline | 0.030 | walk-forward 2022-23 to 2026-27 | 246 | 127 | 119 | 0 | 1.53 | 0.47 | -9.34 | 10.87 |
| V2 Pinnacle's close as the prior | moneyline | 0.050 | walk-forward 2022-23 to 2026-27 | 185 | 96 | 89 | 0 | 6.77 | 2.84 | -8.21 | 15.59 |
| V2 Pinnacle's close as the prior | moneyline | 0.080 | walk-forward 2022-23 to 2026-27 | 123 | 64 | 59 | 0 | 7.45 | 4.83 | -10.28 | 19.83 |
| V2 Pinnacle's close as the prior | moneyline | 0.120 | walk-forward 2022-23 to 2026-27 | 63 | 31 | 32 | 0 | 3.12 | 4.05 | -17.77 | 25.62 |
| V3 last read of the break decides | total | 0.020 | walk-forward 2022-23 to 2026-27 | 813 | 407 | 406 | 0 | -54.68 | -5.91 | -11.01 | -0.20 |
| V3 last read of the break decides | total | 0.030 | walk-forward 2022-23 to 2026-27 | 731 | 372 | 359 | 0 | -35.93 | -4.32 | -10.20 | 1.41 |
| V3 last read of the break decides | total | 0.050 | walk-forward 2022-23 to 2026-27 | 587 | 295 | 292 | 0 | -36.21 | -5.44 | -11.32 | 0.70 |
| V3 last read of the break decides | total | 0.080 | walk-forward 2022-23 to 2026-27 | 349 | 171 | 178 | 0 | -29.97 | -7.59 | -16.33 | 1.49 |
| V3 last read of the break decides | total | 0.120 | walk-forward 2022-23 to 2026-27 | 112 | 62 | 50 | 0 | 5.45 | 4.31 | -10.02 | 19.41 |
| V3 last read of the break decides | spread | 0.020 | walk-forward 2022-23 to 2026-27 | 502 | 282 | 219 | 1 | 32.45 | 5.66 | -1.02 | 12.03 |
| V3 last read of the break decides | spread | 0.030 | walk-forward 2022-23 to 2026-27 | 430 | 245 | 184 | 1 | 35.05 | 7.13 | -0.27 | 14.39 |
| V3 last read of the break decides | spread | 0.050 | walk-forward 2022-23 to 2026-27 | 300 | 173 | 126 | 1 | 29.68 | 8.67 | -0.03 | 17.35 |
| V3 last read of the break decides | spread | 0.080 | walk-forward 2022-23 to 2026-27 | 162 | 93 | 68 | 1 | 15.98 | 8.71 | -2.31 | 18.94 |
| V3 last read of the break decides | spread | 0.120 | walk-forward 2022-23 to 2026-27 | 72 | 38 | 33 | 1 | 0.56 | 0.69 | -17.52 | 17.70 |
| V3 last read of the break decides | moneyline | 0.020 | walk-forward 2022-23 to 2026-27 | 235 | 127 | 108 | 0 | 6.15 | 1.92 | -7.91 | 12.45 |
| V3 last read of the break decides | moneyline | 0.030 | walk-forward 2022-23 to 2026-27 | 209 | 116 | 93 | 0 | 12.53 | 4.39 | -6.37 | 15.10 |
| V3 last read of the break decides | moneyline | 0.050 | walk-forward 2022-23 to 2026-27 | 154 | 81 | 73 | 0 | 1.01 | 0.49 | -12.33 | 13.08 |
| V3 last read of the break decides | moneyline | 0.080 | walk-forward 2022-23 to 2026-27 | 85 | 43 | 42 | 0 | -1.08 | -0.99 | -18.54 | 16.51 |
| V3 last read of the break decides | moneyline | 0.120 | walk-forward 2022-23 to 2026-27 | 44 | 19 | 25 | 0 | -4.18 | -8.04 | -34.98 | 20.37 |
| V4 first crossing | total | 0.020 | walk-forward 2022-23 to 2026-27 | 863 | 435 | 428 | 0 | -53.72 | -5.45 | -10.36 | -0.02 |
| V4 first crossing | total | 0.030 | walk-forward 2022-23 to 2026-27 | 780 | 399 | 381 | 0 | -35.90 | -4.03 | -9.36 | 1.74 |
| V4 first crossing | total | 0.050 | walk-forward 2022-23 to 2026-27 | 634 | 324 | 310 | 0 | -29.75 | -4.12 | -9.95 | 1.72 |
| V4 first crossing | total | 0.080 | walk-forward 2022-23 to 2026-27 | 395 | 203 | 192 | 0 | -15.19 | -3.38 | -11.55 | 4.31 |
| V4 first crossing | total | 0.120 | walk-forward 2022-23 to 2026-27 | 149 | 82 | 67 | 0 | 6.22 | 3.69 | -9.72 | 17.61 |
| V4 first crossing | spread | 0.020 | walk-forward 2022-23 to 2026-27 | 575 | 321 | 254 | 0 | 31.78 | 4.85 | -1.99 | 10.90 |
| V4 first crossing | spread | 0.030 | walk-forward 2022-23 to 2026-27 | 500 | 285 | 215 | 0 | 39.95 | 7.00 | -0.32 | 13.51 |
| V4 first crossing | spread | 0.050 | walk-forward 2022-23 to 2026-27 | 363 | 211 | 152 | 0 | 38.19 | 9.20 | 1.14 | 17.01 |
| V4 first crossing | spread | 0.080 | walk-forward 2022-23 to 2026-27 | 208 | 124 | 84 | 0 | 29.05 | 12.29 | 2.44 | 23.04 |
| V4 first crossing | spread | 0.120 | walk-forward 2022-23 to 2026-27 | 96 | 51 | 44 | 1 | 1.49 | 1.38 | -15.75 | 17.05 |
| V4 first crossing | moneyline | 0.020 | walk-forward 2022-23 to 2026-27 | 274 | 148 | 126 | 0 | 9.65 | 2.59 | -6.98 | 11.94 |
| V4 first crossing | moneyline | 0.030 | walk-forward 2022-23 to 2026-27 | 241 | 132 | 109 | 0 | 15.26 | 4.70 | -5.26 | 14.00 |
| V4 first crossing | moneyline | 0.050 | walk-forward 2022-23 to 2026-27 | 181 | 95 | 86 | 0 | 3.64 | 1.53 | -9.69 | 13.48 |
| V4 first crossing | moneyline | 0.080 | walk-forward 2022-23 to 2026-27 | 103 | 53 | 50 | 0 | 3.37 | 2.58 | -15.48 | 20.31 |
| V4 first crossing | moneyline | 0.120 | walk-forward 2022-23 to 2026-27 | 57 | 25 | 32 | 0 | -2.89 | -4.39 | -29.88 | 22.74 |

### V5, a kill test: the fresh rule removed, pooled walk-forward (not registered)

| rule | market | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V5 fresh rule removed (kill test) | total | 0.020 | walk-forward 2022-23 to 2026-27 | 815 | 413 | 402 | 0 | -45.91 | -4.93 | -10.57 | 0.97 |
| V5 fresh rule removed (kill test) | total | 0.030 | walk-forward 2022-23 to 2026-27 | 728 | 374 | 354 | 0 | -29.91 | -3.60 | -9.67 | 2.29 |
| V5 fresh rule removed (kill test) | total | 0.050 | walk-forward 2022-23 to 2026-27 | 584 | 307 | 277 | 0 | -9.11 | -1.37 | -8.34 | 4.34 |
| V5 fresh rule removed (kill test) | total | 0.080 | walk-forward 2022-23 to 2026-27 | 355 | 191 | 164 | 0 | 3.98 | 0.98 | -7.57 | 9.18 |
| V5 fresh rule removed (kill test) | total | 0.120 | walk-forward 2022-23 to 2026-27 | 134 | 76 | 58 | 0 | 10.30 | 6.77 | -6.85 | 20.65 |
| V5 fresh rule removed (kill test) | spread | 0.020 | walk-forward 2022-23 to 2026-27 | 543 | 311 | 232 | 0 | 46.74 | 7.55 | 0.66 | 14.30 |
| V5 fresh rule removed (kill test) | spread | 0.030 | walk-forward 2022-23 to 2026-27 | 474 | 276 | 198 | 0 | 50.56 | 9.36 | 1.73 | 15.62 |
| V5 fresh rule removed (kill test) | spread | 0.050 | walk-forward 2022-23 to 2026-27 | 332 | 194 | 138 | 0 | 37.20 | 9.83 | 1.53 | 17.62 |
| V5 fresh rule removed (kill test) | spread | 0.080 | walk-forward 2022-23 to 2026-27 | 192 | 118 | 74 | 0 | 34.71 | 15.95 | 4.15 | 27.23 |
| V5 fresh rule removed (kill test) | spread | 0.120 | walk-forward 2022-23 to 2026-27 | 98 | 55 | 43 | 0 | 6.84 | 6.16 | -9.04 | 22.00 |
| V5 fresh rule removed (kill test) | moneyline | 0.020 | walk-forward 2022-23 to 2026-27 | 255 | 135 | 120 | 0 | 4.97 | 1.43 | -7.58 | 11.57 |
| V5 fresh rule removed (kill test) | moneyline | 0.030 | walk-forward 2022-23 to 2026-27 | 223 | 119 | 104 | 0 | 8.35 | 2.78 | -7.42 | 13.16 |
| V5 fresh rule removed (kill test) | moneyline | 0.050 | walk-forward 2022-23 to 2026-27 | 169 | 86 | 83 | 0 | -2.96 | -1.33 | -13.38 | 10.04 |
| V5 fresh rule removed (kill test) | moneyline | 0.080 | walk-forward 2022-23 to 2026-27 | 102 | 52 | 50 | 0 | 0.92 | 0.71 | -15.66 | 18.99 |
| V5 fresh rule removed (kill test) | moneyline | 0.120 | walk-forward 2022-23 to 2026-27 | 52 | 23 | 29 | 0 | -1.57 | -2.61 | -30.21 | 25.93 |

## 3b. Kill tests on what read positive

Script: `scripts/euroleague_research/r4_kill.py`.

### The kill tests at a glance

| rule | bets | units | ret% | placebo p95% | share of shuffles >= real | without 10 best dates ret% | share on one side (max of home/away) |
|---|---|---|---|---|---|---|---|
| A spread, ported unchanged, cut 0.05 | 312 | 29.80 | 8.37 | -0.45 | 0.00 | 2.63 | 0.62 |
| B spread, V2 Pinnacle prior, cut 0.05 | 364 | 45.34 | 10.93 | -1.09 | 0.00 | 6.18 | 0.67 |
| C total, ported unchanged, cut 0.12 | 120 | 9.25 | 6.80 | -0.49 | 0.00 | -6.68 | 0.98 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | 574 | -12.61 | -1.93 | -0.35 | 0.18 | -7.25 | 0.99 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | 164 | -0.51 | -0.24 | -0.23 | 0.06 | -11.07 | 0.63 |

### A spread, ported unchanged, cut 0.05

Price range of the bets: median -115, shortest -135, longest +105, shorter than -300: 0.0%, shorter than -500: 0.0%.

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | share% |
|---|---|---|---|---|---|---|---|---|---|---|
| A spread, ported unchanged, cut 0.05 | all | 312 | 180 | 132 | 0 | 29.80 | 8.37 | -0.06 | 16.33 |  |
| A spread, ported unchanged, cut 0.05 | season 2023 | 84 | 47 | 37 | 0 | 4.55 | 4.73 | -12.19 | 21.78 |  |
| A spread, ported unchanged, cut 0.05 | season 2024 | 50 | 26 | 24 | 0 | -1.45 | -2.53 | -23.72 | 19.95 |  |
| A spread, ported unchanged, cut 0.05 | season 2025 | 52 | 32 | 20 | 0 | 9.70 | 16.47 | -3.36 | 37.62 |  |
| A spread, ported unchanged, cut 0.05 | season 2026 | 100 | 55 | 45 | 0 | 3.70 | 3.23 | -13.04 | 19.15 |  |
| A spread, ported unchanged, cut 0.05 | season 2027 | 26 | 20 | 6 | 0 | 13.30 | 45.74 | 19.81 | 65.97 |  |
| A spread, ported unchanged, cut 0.05 | early half of each season | 155 | 96 | 59 | 0 | 28.46 | 16.06 | 3.89 | 27.91 |  |
| A spread, ported unchanged, cut 0.05 | late half of each season | 157 | 84 | 73 | 0 | 1.34 | 0.75 | -11.28 | 12.72 |  |
| A spread, ported unchanged, cut 0.05 | without its 10 best dates | 291 | 159 | 132 | 0 | 8.75 | 2.63 | -5.71 | 11.08 |  |
| A spread, ported unchanged, cut 0.05 | side = away | 194 | 113 | 81 | 0 | 21.63 | 9.83 | -1.29 | 21.42 | 62.20 |
| A spread, ported unchanged, cut 0.05 | side = home | 118 | 67 | 51 | 0 | 8.17 | 6.01 | -9.25 | 19.44 | 37.80 |
| A spread, ported unchanged, cut 0.05 | leader_at_half = leader | 207 | 118 | 89 | 0 | 16.04 | 6.76 | -3.93 | 17.74 | 66.30 |
| A spread, ported unchanged, cut 0.05 | leader_at_half = level | 15 | 9 | 6 | 0 | 2.50 | 15.02 | -21.97 | 51.38 | 4.80 |
| A spread, ported unchanged, cut 0.05 | leader_at_half = trailer | 90 | 53 | 37 | 0 | 11.26 | 11.05 | -3.68 | 25.81 | 28.80 |
| A spread, ported unchanged, cut 0.05 | behind_expectation = False | 259 | 150 | 109 | 0 | 25.79 | 8.71 | -1.27 | 17.43 | 83.00 |
| A spread, ported unchanged, cut 0.05 | behind_expectation = True | 53 | 30 | 23 | 0 | 4.01 | 6.70 | -13.08 | 28.10 | 17.00 |
| A spread, ported unchanged, cut 0.05 | bookmaker = betmgm | 52 | 32 | 20 | 0 | 9.66 | 16.46 | -3.01 | 36.71 | 16.70 |
| A spread, ported unchanged, cut 0.05 | bookmaker = betrivers | 24 | 13 | 11 | 0 | 0.04 | 0.14 | -27.13 | 28.83 | 7.70 |
| A spread, ported unchanged, cut 0.05 | bookmaker = draftkings | 205 | 114 | 91 | 0 | 10.25 | 4.38 | -6.76 | 14.91 | 65.70 |
| A spread, ported unchanged, cut 0.05 | bookmaker = fanatics | 4 | 2 | 2 | 0 | -0.20 | -4.40 | -100.00 | 45.33 | 1.30 |
| A spread, ported unchanged, cut 0.05 | bookmaker = fanduel | 27 | 19 | 8 | 0 | 10.05 | 33.22 | 1.28 | 64.90 | 8.70 |
| A spread, ported unchanged, cut 0.05 | underdog | 226 | 130 | 96 | 0 | 20.38 | 7.90 | -3.42 | 18.00 | 72.40 |
| A spread, ported unchanged, cut 0.05 | favourite | 86 | 50 | 36 | 0 | 9.42 | 9.63 | -6.54 | 26.75 | 27.60 |
| A spread, ported unchanged, cut 0.05 | price band +100..+150 | 17 | 11 | 6 | 0 | 5.45 | 32.06 | -4.12 | 68.24 | 5.40 |
| A spread, ported unchanged, cut 0.05 | price band -150..-100 | 295 | 169 | 126 | 0 | 24.35 | 7.18 | -1.37 | 15.81 | 94.60 |
| A spread, ported unchanged, cut 0.05 | neighbour cut 0.02 | 518 | 296 | 222 | 0 | 42.74 | 7.23 | 0.61 | 14.06 |  |
| A spread, ported unchanged, cut 0.05 | neighbour cut 0.03 | 449 | 261 | 188 | 0 | 46.61 | 9.10 | 1.87 | 16.14 |  |
| A spread, ported unchanged, cut 0.05 | neighbour cut 0.05 | 312 | 180 | 132 | 0 | 29.80 | 8.37 | -0.06 | 16.33 |  |
| A spread, ported unchanged, cut 0.05 | neighbour cut 0.08 | 177 | 108 | 69 | 0 | 30.16 | 15.03 | 3.36 | 26.10 |  |
| A spread, ported unchanged, cut 0.05 | neighbour cut 0.12 | 86 | 47 | 39 | 0 | 3.19 | 3.28 | -13.11 | 21.81 |  |
| A spread, ported unchanged, cut 0.05 | the rule's bets turned round (other side, same quote) | 312 | 132 | 180 | 0 | -77.20 | -21.26 | -29.14 | -12.87 |  |
| A spread, ported unchanged, cut 0.05 | fresh rule removed (V5) | 332 | 194 | 138 | 0 | 37.20 | 9.83 | 1.53 | 17.62 |  |
| A spread, ported unchanged, cut 0.05 | last read decides (V3) | 300 | 173 | 126 | 1 | 29.68 | 8.67 | -0.03 | 17.35 |  |
| A spread, ported unchanged, cut 0.05 | 2021-22 second look (fitted on 2022-23) | 36 | 16 | 20 | 0 | -7.10 | -17.01 | -40.98 | 6.96 |  |
| A spread, ported unchanged, cut 0.05 | control: every decided game, blind on the side behind its expected first half | 1,358 | 674 | 683 | 1 | -113.96 | -7.28 | -11.37 | -3.01 |  |
| A spread, ported unchanged, cut 0.05 | control: every decided game, blind on the side ahead of its expected first half | 1,358 | 683 | 674 | 1 | -91.34 | -5.86 | -10.20 | -1.75 |  |
| A spread, ported unchanged, cut 0.05 | control: every decided game, blind on the side getting points at the half (the underdog) | 1,367 | 717 | 649 | 1 | -31.61 | -2.01 | -6.51 | 2.06 |  |

Placebo for A spread, ported unchanged, cut 0.05 (200 shuffles of the half-time score across games within each season, re-priced and re-decided): mean -3.75%, 5th-95th percentile -7.24% to -0.45%; real +8.37%; share of shuffles at or above the real result 0.0%.

### B spread, V2 Pinnacle prior, cut 0.05

Price range of the bets: median -115, shortest -135, longest +105, shorter than -300: 0.0%, shorter than -500: 0.0%.

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | share% |
|---|---|---|---|---|---|---|---|---|---|---|
| B spread, V2 Pinnacle prior, cut 0.05 | all | 364 | 215 | 149 | 0 | 45.34 | 10.93 | 3.40 | 18.48 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | season 2023 | 107 | 60 | 47 | 0 | 6.05 | 4.94 | -9.01 | 18.44 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | season 2024 | 61 | 32 | 29 | 0 | -1.15 | -1.65 | -21.50 | 17.47 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | season 2025 | 58 | 39 | 19 | 0 | 17.90 | 27.18 | 10.01 | 43.27 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | season 2026 | 107 | 62 | 45 | 0 | 10.69 | 8.73 | -5.05 | 22.83 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | season 2027 | 31 | 22 | 9 | 0 | 11.85 | 34.09 | 14.42 | 51.80 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | early half of each season | 178 | 110 | 68 | 0 | 32.22 | 15.84 | 5.34 | 26.33 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | late half of each season | 186 | 105 | 81 | 0 | 13.12 | 6.20 | -3.79 | 16.76 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | without its 10 best dates | 343 | 194 | 149 | 0 | 24.19 | 6.18 | -1.75 | 14.00 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | side = away | 245 | 145 | 100 | 0 | 31.76 | 11.41 | 1.93 | 20.94 | 67.30 |
| B spread, V2 Pinnacle prior, cut 0.05 | side = home | 119 | 70 | 49 | 0 | 13.58 | 9.93 | -3.59 | 23.36 | 32.70 |
| B spread, V2 Pinnacle prior, cut 0.05 | leader_at_half = leader | 213 | 122 | 91 | 0 | 17.86 | 7.32 | -2.25 | 18.14 | 58.50 |
| B spread, V2 Pinnacle prior, cut 0.05 | leader_at_half = level | 15 | 8 | 7 | 0 | 0.35 | 2.11 | -35.90 | 39.52 | 4.10 |
| B spread, V2 Pinnacle prior, cut 0.05 | leader_at_half = trailer | 136 | 85 | 51 | 0 | 27.13 | 17.57 | 4.60 | 29.47 | 37.40 |
| B spread, V2 Pinnacle prior, cut 0.05 | behind_expectation = False | 282 | 166 | 116 | 0 | 33.86 | 10.51 | 1.73 | 19.19 | 77.50 |
| B spread, V2 Pinnacle prior, cut 0.05 | behind_expectation = True | 82 | 49 | 33 | 0 | 11.48 | 12.36 | -3.85 | 29.08 | 22.50 |
| B spread, V2 Pinnacle prior, cut 0.05 | bookmaker = betmgm | 53 | 37 | 16 | 0 | 19.16 | 32.02 | 12.57 | 51.16 | 14.60 |
| B spread, V2 Pinnacle prior, cut 0.05 | bookmaker = betrivers | 24 | 13 | 11 | 0 | 0.03 | 0.11 | -29.08 | 33.62 | 6.60 |
| B spread, V2 Pinnacle prior, cut 0.05 | bookmaker = draftkings | 252 | 144 | 108 | 0 | 20.85 | 7.25 | -2.56 | 16.89 | 69.20 |
| B spread, V2 Pinnacle prior, cut 0.05 | bookmaker = fanatics | 4 | 2 | 2 | 0 | -0.30 | -6.45 | -100.00 | 42.37 | 1.10 |
| B spread, V2 Pinnacle prior, cut 0.05 | bookmaker = fanduel | 31 | 19 | 12 | 0 | 5.60 | 16.18 | -14.95 | 43.82 | 8.50 |
| B spread, V2 Pinnacle prior, cut 0.05 | underdog | 284 | 169 | 115 | 0 | 37.57 | 11.59 | 2.96 | 20.11 | 78.00 |
| B spread, V2 Pinnacle prior, cut 0.05 | favourite | 80 | 46 | 34 | 0 | 7.77 | 8.56 | -9.91 | 26.44 | 22.00 |
| B spread, V2 Pinnacle prior, cut 0.05 | price band +100..+150 | 20 | 14 | 6 | 0 | 8.55 | 42.75 | 11.49 | 73.75 | 5.50 |
| B spread, V2 Pinnacle prior, cut 0.05 | price band -150..-100 | 344 | 201 | 143 | 0 | 36.79 | 9.31 | 1.99 | 17.32 | 94.50 |
| B spread, V2 Pinnacle prior, cut 0.05 | neighbour cut 0.02 | 552 | 307 | 245 | 0 | 28.03 | 4.45 | -2.25 | 10.93 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | neighbour cut 0.03 | 476 | 272 | 204 | 0 | 39.68 | 7.31 | 0.37 | 14.17 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | neighbour cut 0.05 | 364 | 215 | 149 | 0 | 45.34 | 10.93 | 3.40 | 18.48 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | neighbour cut 0.08 | 227 | 135 | 92 | 0 | 30.93 | 11.98 | 1.89 | 21.71 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | neighbour cut 0.12 | 117 | 73 | 44 | 0 | 23.36 | 17.59 | 3.19 | 30.45 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | the rule's bets turned round (other side, same quote) | 364 | 149 | 215 | 0 | -101.28 | -23.91 | -31.44 | -16.54 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | fresh rule removed (V5) | 381 | 227 | 154 | 0 | 51.89 | 11.95 | 3.90 | 19.08 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | last read decides (V3) | 345 | 196 | 148 | 1 | 27.35 | 6.96 | -0.81 | 15.24 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | 2021-22 second look (fitted on 2022-23) | 33 | 17 | 16 | 0 | -1.35 | -3.55 | -32.55 | 23.03 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | control: every decided game, blind on the side behind its expected first half | 1,281 | 626 | 652 | 3 | -126.74 | -8.59 | -12.78 | -4.20 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | control: every decided game, blind on the side ahead of its expected first half | 1,281 | 652 | 626 | 3 | -67.28 | -4.58 | -9.02 | -0.39 |  |
| B spread, V2 Pinnacle prior, cut 0.05 | control: every decided game, blind on the side getting points at the half (the underdog) | 1,297 | 678 | 616 | 3 | -32.76 | -2.20 | -6.29 | 2.07 |  |

Placebo for B spread, V2 Pinnacle prior, cut 0.05 (200 shuffles of the half-time score across games within each season, re-priced and re-decided): mean -4.48%, 5th-95th percentile -7.98% to -1.09%; real +10.93%; share of shuffles at or above the real result 0.0%.

### C total, ported unchanged, cut 0.12

Price range of the bets: median -115, shortest -134, longest +105, shorter than -300: 0.0%, shorter than -500: 0.0%.

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | share% |
|---|---|---|---|---|---|---|---|---|---|---|
| C total, ported unchanged, cut 0.12 | all | 120 | 68 | 52 | 0 | 9.25 | 6.80 | -7.91 | 20.44 |  |
| C total, ported unchanged, cut 0.12 | season 2023 | 7 | 4 | 3 | 0 | 0.55 | 6.83 | -46.58 | 60.25 |  |
| C total, ported unchanged, cut 0.12 | season 2024 | 17 | 9 | 8 | 0 | -0.20 | -1.02 | -34.02 | 31.97 |  |
| C total, ported unchanged, cut 0.12 | season 2025 | 16 | 6 | 10 | 0 | -5.50 | -29.89 | -60.64 | 9.06 |  |
| C total, ported unchanged, cut 0.12 | season 2026 | 63 | 41 | 22 | 0 | 16.23 | 22.91 | 4.03 | 42.26 |  |
| C total, ported unchanged, cut 0.12 | season 2027 | 17 | 8 | 9 | 0 | -1.83 | -9.51 | -49.68 | 34.47 |  |
| C total, ported unchanged, cut 0.12 | early half of each season | 58 | 33 | 25 | 0 | 4.59 | 6.94 | -12.22 | 27.65 |  |
| C total, ported unchanged, cut 0.12 | late half of each season | 62 | 35 | 27 | 0 | 4.66 | 6.66 | -14.65 | 28.82 |  |
| C total, ported unchanged, cut 0.12 | without its 10 best dates | 103 | 51 | 52 | 0 | -7.80 | -6.68 | -21.23 | 7.66 |  |
| C total, ported unchanged, cut 0.12 | side = over | 118 | 67 | 51 | 0 | 9.40 | 7.02 | -7.60 | 20.72 | 98.30 |
| C total, ported unchanged, cut 0.12 | side = under | 2 | 1 | 1 | 0 | -0.15 | -6.67 | -100.00 | 90.91 | 1.70 |
| C total, ported unchanged, cut 0.12 | leader_at_half = leader | 37 | 19 | 18 | 0 | -1.36 | -3.23 | -28.04 | 21.27 | 30.80 |
| C total, ported unchanged, cut 0.12 | leader_at_half = level | 2 | 0 | 2 | 0 | -2.20 | -100.00 | -100.00 | -100.00 | 1.70 |
| C total, ported unchanged, cut 0.12 | leader_at_half = trailer | 81 | 49 | 32 | 0 | 12.81 | 13.95 | -3.57 | 30.39 | 67.50 |
| C total, ported unchanged, cut 0.12 | behind_expectation = False | 45 | 22 | 23 | 0 | -4.02 | -7.87 | -29.15 | 16.02 | 37.50 |
| C total, ported unchanged, cut 0.12 | behind_expectation = True | 75 | 46 | 29 | 0 | 13.27 | 15.61 | -3.35 | 32.57 | 62.50 |
| C total, ported unchanged, cut 0.12 | bookmaker = betmgm | 33 | 21 | 12 | 0 | 7.70 | 20.69 | 0.85 | 41.61 | 27.50 |
| C total, ported unchanged, cut 0.12 | bookmaker = betrivers | 10 | 6 | 4 | 0 | 1.23 | 10.23 | -43.90 | 48.12 | 8.30 |
| C total, ported unchanged, cut 0.12 | bookmaker = draftkings | 57 | 29 | 28 | 0 | -2.93 | -4.52 | -24.07 | 17.94 | 47.50 |
| C total, ported unchanged, cut 0.12 | bookmaker = fanatics | 2 | 2 | 0 | 0 | 2.00 | 88.89 | 86.96 | 90.91 | 1.70 |
| C total, ported unchanged, cut 0.12 | bookmaker = fanduel | 18 | 10 | 8 | 0 | 1.25 | 6.33 | -25.88 | 41.65 | 15.00 |
| C total, ported unchanged, cut 0.12 | underdog | 120 | 68 | 52 | 0 | 9.25 | 6.80 | -7.91 | 20.44 | 100.00 |
| C total, ported unchanged, cut 0.12 | price band +100..+150 | 3 | 1 | 2 | 0 | -0.95 | -31.67 | -100.00 | 36.67 | 2.50 |
| C total, ported unchanged, cut 0.12 | price band -150..-100 | 117 | 67 | 50 | 0 | 10.20 | 7.66 | -6.00 | 21.64 | 97.50 |
| C total, ported unchanged, cut 0.12 | neighbour cut 0.02 | 811 | 407 | 404 | 0 | -54.23 | -5.86 | -11.56 | -0.56 |  |
| C total, ported unchanged, cut 0.12 | neighbour cut 0.03 | 724 | 367 | 357 | 0 | -40.38 | -4.89 | -11.03 | 0.74 |  |
| C total, ported unchanged, cut 0.12 | neighbour cut 0.05 | 574 | 300 | 274 | 0 | -12.61 | -1.93 | -8.44 | 4.23 |  |
| C total, ported unchanged, cut 0.12 | neighbour cut 0.08 | 341 | 183 | 158 | 0 | 2.93 | 0.75 | -8.08 | 9.25 |  |
| C total, ported unchanged, cut 0.12 | neighbour cut 0.12 | 120 | 68 | 52 | 0 | 9.25 | 6.80 | -7.91 | 20.44 |  |
| C total, ported unchanged, cut 0.12 | the rule's bets turned round (other side, same quote) | 120 | 52 | 68 | 0 | -27.28 | -19.47 | -32.83 | -4.82 |  |
| C total, ported unchanged, cut 0.12 | fresh rule removed (V5) | 134 | 76 | 58 | 0 | 10.30 | 6.77 | -6.85 | 20.65 |  |
| C total, ported unchanged, cut 0.12 | last read decides (V3) | 112 | 62 | 50 | 0 | 5.45 | 4.31 | -10.02 | 19.41 |  |
| C total, ported unchanged, cut 0.12 | 2021-22 second look (fitted on 2022-23) | 2 | 1 | 1 | 0 | -0.15 | -6.67 | -100.00 | 90.91 |  |

Placebo for C total, ported unchanged, cut 0.12 (200 shuffles of the half-time score across games within each season, re-priced and re-decided): mean -3.85%, 5th-95th percentile -7.11% to -0.49%; real +6.80%; share of shuffles at or above the real result 0.0%.

### D total, ported unchanged, cut 0.05 (null; splits for the record)

Price range of the bets: median -115, shortest -134, longest +105, shorter than -300: 0.0%, shorter than -500: 0.0%.

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | share% |
|---|---|---|---|---|---|---|---|---|---|---|
| D total, ported unchanged, cut 0.05 (null; splits for the record) | all | 574 | 300 | 274 | 0 | -12.61 | -1.93 | -8.44 | 4.23 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | season 2023 | 75 | 38 | 37 | 0 | -4.55 | -5.28 | -19.55 | 8.35 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | season 2024 | 102 | 52 | 50 | 0 | -5.50 | -4.69 | -18.10 | 8.44 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | season 2025 | 92 | 47 | 45 | 0 | -4.75 | -4.49 | -21.20 | 13.91 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | season 2026 | 232 | 125 | 107 | 0 | 3.69 | 1.41 | -9.37 | 12.93 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | season 2027 | 73 | 38 | 35 | 0 | -1.50 | -1.80 | -21.65 | 16.20 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | early half of each season | 283 | 149 | 134 | 0 | -4.39 | -1.36 | -10.84 | 7.71 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | late half of each season | 291 | 151 | 140 | 0 | -8.22 | -2.48 | -12.06 | 7.01 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | without its 10 best dates | 532 | 263 | 269 | 0 | -44.03 | -7.25 | -13.72 | -0.94 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | side = over | 568 | 298 | 270 | 0 | -10.11 | -1.56 | -8.07 | 4.72 | 99.00 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | side = under | 6 | 2 | 4 | 0 | -2.50 | -36.87 | -100.00 | 26.32 | 1.00 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | leader_at_half = leader | 190 | 98 | 92 | 0 | -6.88 | -3.18 | -14.21 | 7.80 | 33.10 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | leader_at_half = level | 17 | 11 | 6 | 0 | 4.30 | 22.40 | -11.23 | 55.99 | 3.00 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | leader_at_half = trailer | 367 | 191 | 176 | 0 | -10.03 | -2.39 | -10.81 | 6.04 | 63.90 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | behind_expectation = False | 233 | 115 | 118 | 0 | -19.16 | -7.23 | -16.39 | 3.52 | 40.60 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | behind_expectation = True | 341 | 185 | 156 | 0 | 6.55 | 1.68 | -7.22 | 9.97 | 59.40 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | bookmaker = betmgm | 76 | 41 | 35 | 0 | 2.01 | 2.35 | -14.28 | 17.24 | 13.20 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | bookmaker = betrivers | 40 | 19 | 21 | 0 | -6.44 | -13.38 | -37.45 | 9.77 | 7.00 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | bookmaker = draftkings | 361 | 185 | 176 | 0 | -16.28 | -3.94 | -11.90 | 3.96 | 62.90 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | bookmaker = fanatics | 7 | 4 | 3 | 0 | 0.55 | 7.01 | -47.83 | 63.40 | 1.20 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | bookmaker = fanduel | 90 | 51 | 39 | 0 | 7.55 | 7.53 | -8.24 | 23.50 | 15.70 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | underdog | 574 | 300 | 274 | 0 | -12.61 | -1.93 | -8.44 | 4.23 | 100.00 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | price band +100..+150 | 9 | 3 | 6 | 0 | -2.95 | -32.78 | -77.78 | 15.00 | 1.60 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | price band -150..-100 | 565 | 297 | 268 | 0 | -9.66 | -1.50 | -8.00 | 5.08 | 98.40 |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | neighbour cut 0.02 | 811 | 407 | 404 | 0 | -54.23 | -5.86 | -11.56 | -0.56 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | neighbour cut 0.03 | 724 | 367 | 357 | 0 | -40.38 | -4.89 | -11.03 | 0.74 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | neighbour cut 0.05 | 574 | 300 | 274 | 0 | -12.61 | -1.93 | -8.44 | 4.23 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | neighbour cut 0.08 | 341 | 183 | 158 | 0 | 2.93 | 0.75 | -8.08 | 9.25 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | neighbour cut 0.12 | 120 | 68 | 52 | 0 | 9.25 | 6.80 | -7.91 | 20.44 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | the rule's bets turned round (other side, same quote) | 574 | 274 | 300 | 0 | -73.50 | -11.04 | -17.12 | -4.63 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | fresh rule removed (V5) | 584 | 307 | 277 | 0 | -9.11 | -1.37 | -8.34 | 4.34 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | last read decides (V3) | 587 | 295 | 292 | 0 | -36.21 | -5.44 | -11.32 | 0.70 |  |
| D total, ported unchanged, cut 0.05 (null; splits for the record) | 2021-22 second look (fitted on 2022-23) | 43 | 24 | 19 | 0 | 2.70 | 5.56 | -17.56 | 28.44 |  |

Placebo for D total, ported unchanged, cut 0.05 (null; splits for the record) (200 shuffles of the half-time score across games within each season, re-priced and re-decided): mean -3.89%, 5th-95th percentile -6.94% to -0.35%; real -1.93%; share of shuffles at or above the real result 18.5%.

### E moneyline, ported margin model, cut 0.05 (null; splits for the record)

Price range of the bets: median -104, shortest -250, longest +250, shorter than -300: 0.0%, shorter than -500: 0.0%.

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | share% |
|---|---|---|---|---|---|---|---|---|---|---|
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | all | 164 | 84 | 80 | 0 | -0.51 | -0.24 | -13.25 | 12.85 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | season 2023 | 48 | 23 | 25 | 0 | -6.20 | -9.45 | -31.58 | 13.96 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | season 2024 | 31 | 14 | 17 | 0 | -6.47 | -15.47 | -39.08 | 5.77 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | season 2025 | 26 | 15 | 11 | 0 | 2.57 | 7.57 | -22.46 | 39.61 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | season 2026 | 47 | 24 | 23 | 0 | 4.09 | 6.79 | -18.87 | 33.39 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | season 2027 | 12 | 8 | 4 | 0 | 5.50 | 41.76 | 3.90 | 82.79 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | early half of each season | 80 | 41 | 39 | 0 | 1.41 | 1.39 | -17.59 | 18.97 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | late half of each season | 84 | 43 | 41 | 0 | -1.92 | -1.69 | -18.34 | 14.48 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | without its 10 best dates | 152 | 72 | 80 | 0 | -22.29 | -11.07 | -21.95 | 0.81 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | side = away | 104 | 56 | 48 | 0 | 8.26 | 6.22 | -9.91 | 23.18 | 63.40 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | side = home | 60 | 28 | 32 | 0 | -8.77 | -10.70 | -29.64 | 8.43 | 36.60 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | leader_at_half = leader | 145 | 77 | 68 | 0 | -0.81 | -0.41 | -12.96 | 12.03 | 88.40 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | leader_at_half = level | 4 | 3 | 1 | 0 | 3.90 | 93.98 | -5.49 | 200.00 | 2.40 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | leader_at_half = trailer | 15 | 4 | 11 | 0 | -3.60 | -23.68 | -76.43 | 33.60 | 9.10 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | behind_expectation = False | 149 | 79 | 70 | 0 | 2.49 | 1.25 | -11.13 | 15.02 | 90.90 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | behind_expectation = True | 15 | 5 | 10 | 0 | -3.00 | -19.11 | -63.86 | 27.66 | 9.10 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | bookmaker = betmgm | 25 | 16 | 9 | 0 | 7.85 | 24.03 | -4.21 | 52.41 | 15.20 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | bookmaker = betrivers | 11 | 5 | 6 | 0 | -0.70 | -5.17 | -59.17 | 53.32 | 6.70 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | bookmaker = draftkings | 117 | 59 | 58 | 0 | -6.71 | -4.30 | -18.47 | 10.32 | 71.30 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | bookmaker = fanatics | 1 | 0 | 1 | 0 | -1.15 | -100.00 | -100.00 | -100.00 | 0.60 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | bookmaker = fanduel | 10 | 4 | 6 | 0 | 0.20 | 1.78 | -58.12 | 74.90 | 6.10 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | underdog | 101 | 49 | 52 | 0 | 12.27 | 11.84 | -5.34 | 29.57 | 61.60 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | favourite | 63 | 35 | 28 | 0 | -12.78 | -11.51 | -28.24 | 5.13 | 38.40 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | price band +100..+150 | 43 | 26 | 17 | 0 | 14.53 | 33.79 | 5.76 | 61.13 | 26.20 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | price band -150..-100 | 44 | 24 | 20 | 0 | -1.45 | -2.61 | -23.43 | 17.75 | 26.80 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | price band -300..-151 | 39 | 23 | 16 | 0 | -8.38 | -10.71 | -28.96 | 8.52 | 23.80 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | price band > +150 | 38 | 11 | 27 | 0 | -5.21 | -13.71 | -48.98 | 23.78 | 23.20 |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | neighbour cut 0.02 | 252 | 135 | 117 | 0 | 7.28 | 2.12 | -8.43 | 12.27 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | neighbour cut 0.03 | 221 | 119 | 102 | 0 | 9.81 | 3.30 | -7.05 | 14.58 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | neighbour cut 0.05 | 164 | 84 | 80 | 0 | -0.51 | -0.24 | -13.25 | 12.85 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | neighbour cut 0.08 | 96 | 50 | 46 | 0 | 4.12 | 3.37 | -12.38 | 19.36 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | neighbour cut 0.12 | 48 | 21 | 27 | 0 | -1.17 | -2.13 | -28.86 | 28.17 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | the rule's bets turned round (other side, same quote) | 164 | 80 | 84 | 0 | -29.45 | -11.80 | -23.03 | -0.49 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | fresh rule removed (V5) | 169 | 86 | 83 | 0 | -2.96 | -1.33 | -13.38 | 10.04 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | last read decides (V3) | 154 | 81 | 73 | 0 | 1.01 | 0.49 | -12.33 | 13.08 |  |
| E moneyline, ported margin model, cut 0.05 (null; splits for the record) | 2021-22 second look (fitted on 2022-23) | 10 | 7 | 3 | 0 | 4.50 | 34.97 | -1.28 | 68.14 |  |

Placebo for E moneyline, ported margin model, cut 0.05 (null; splits for the record) (200 shuffles of the half-time score across games within each season, re-priced and re-decided): mean -6.29%, 5th-95th percentile -12.41% to -0.23%; real -0.24%; share of shuffles at or above the real result 5.5%.

### Does return rise with the claimed edge? Every decided game under V2 (Pinnacle prior), by claimed EV band, walk-forward seasons

| market | claimed EV band | bets | W | L | P | units | ret% | lo% | hi% |
|---|---|---|---|---|---|---|---|---|---|
| total | < 0 | 391 | 200 | 191 | 0 | -19.59 | -4.36 | -12.90 | 3.44 |
| total | 0-0.02 | 169 | 88 | 81 | 0 | -5.13 | -2.64 | -14.28 | 8.19 |
| total | 0.02-0.05 | 217 | 101 | 116 | 0 | -31.51 | -12.71 | -22.20 | -2.42 |
| total | 0.05-0.08 | 214 | 101 | 113 | 0 | -28.18 | -11.56 | -22.20 | -0.65 |
| total | 0.08-0.12 | 176 | 93 | 83 | 0 | -1.81 | -0.90 | -13.84 | 10.05 |
| total | 0.12-0.20 | 108 | 58 | 50 | 0 | 1.50 | 1.22 | -13.61 | 15.08 |
| total | >= 0.20 | 11 | 9 | 2 | 0 | 6.70 | 54.08 | 19.14 | 89.50 |
| spread | < 0 | 562 | 287 | 273 | 2 | -26.94 | -4.19 | -11.37 | 2.80 |
| spread | 0-0.02 | 183 | 93 | 89 | 1 | -8.43 | -4.05 | -14.59 | 7.18 |
| spread | 0.02-0.05 | 188 | 92 | 96 | 0 | -17.31 | -8.07 | -18.44 | 2.19 |
| spread | 0.05-0.08 | 137 | 80 | 57 | 0 | 14.41 | 9.19 | -3.86 | 22.43 |
| spread | 0.08-0.12 | 110 | 62 | 48 | 0 | 7.57 | 6.04 | -8.81 | 20.70 |
| spread | 0.12-0.20 | 90 | 57 | 33 | 0 | 19.76 | 19.34 | 3.81 | 35.43 |
| spread | >= 0.20 | 27 | 16 | 11 | 0 | 3.60 | 11.75 | -13.33 | 39.29 |
| moneyline | < 0 | 242 | 132 | 110 | 0 | 4.89 | 1.39 | -8.46 | 10.71 |
| moneyline | 0-0.02 | 73 | 40 | 33 | 0 | 2.05 | 1.92 | -15.10 | 17.64 |
| moneyline | 0.02-0.05 | 90 | 49 | 41 | 0 | 0.37 | 0.29 | -13.53 | 14.76 |
| moneyline | 0.05-0.08 | 62 | 32 | 30 | 0 | -0.68 | -0.81 | -18.09 | 15.37 |
| moneyline | 0.08-0.12 | 60 | 33 | 27 | 0 | 4.33 | 5.60 | -17.07 | 28.45 |
| moneyline | 0.12-0.20 | 49 | 26 | 23 | 0 | 3.27 | 5.20 | -17.33 | 28.21 |
| moneyline | >= 0.20 | 14 | 5 | 9 | 0 | -0.15 | -1.06 | -59.79 | 61.89 |

## 4. Structural check: are halftime lines re-hung mechanically, and where do they miss?

Script: `scripts/euroleague_research/r4_structure.py`.

### The shares used (fitted on earlier seasons)

| season | share2 | share_m |
|---|---|---|
| 2021-22 | 0.50 | 0.55 |
| 2022-23 | 0.50 | 0.35 |
| 2023-24 | 0.50 | 0.45 |
| 2024-25 | 0.50 | 0.49 |
| 2025-26 | 0.50 | 0.46 |
| 2026-27 to 11-12 | 0.50 | 0.45 |

### Totals: each book's first fresh halftime total against the mechanical line

`book - mechanical` > 0: the book hangs a higher total than half-time points + the pre-game total x the usual second-half share. `final - book` > 0: the game went over the book's total.

| season | book | games | book - mechanical: mean | sd | mean |dev| | share within 1 point | final - book: mean |
|---|---|---|---|---|---|---|---|
| 2021-22 | bovada | 249 | 1.02 | 1.52 | 1.34 | 0.48 | -0.81 |
| 2021-22 | draftkings | 256 | 1.02 | 1.26 | 1.30 | 0.43 | -1.40 |
| 2021-22 | pinnacle | 213 | 0.99 | 2.71 | 2.11 | 0.32 | -0.94 |
| 2021-22 | unibet | 265 | 0.80 | 1.25 | 1.15 | 0.49 | -0.72 |
| 2022-23 | bovada | 276 | -0.23 | 1.62 | 1.24 | 0.47 | 0.45 |
| 2022-23 | draftkings | 285 | 0.02 | 1.16 | 0.90 | 0.62 | 0.41 |
| 2022-23 | pinnacle | 252 | -0.93 | 5.87 | 2.43 | 0.34 | 1.14 |
| 2022-23 | unibet | 308 | -0.32 | 1.33 | 1.08 | 0.54 | 0.86 |
| 2023-24 | bovada | 310 | -0.19 | 1.53 | 1.14 | 0.55 | 0.23 |
| 2023-24 | draftkings | 313 | 0.21 | 1.29 | 1.04 | 0.55 | -0.14 |
| 2023-24 | pinnacle | 249 | -0.40 | 3.34 | 2.30 | 0.37 | 0.75 |
| 2023-24 | unibet | 314 | -0.12 | 1.28 | 0.96 | 0.63 | 0.23 |
| 2024-25 | bovada | 292 | 0.36 | 3.89 | 2.26 | 0.43 | 1.07 |
| 2024-25 | draftkings | 294 | 0.21 | 1.26 | 1.04 | 0.54 | 1.21 |
| 2024-25 | pinnacle | 269 | 0.47 | 3.16 | 2.30 | 0.35 | 0.99 |
| 2024-25 | unibet | 166 | -0.17 | 1.22 | 0.96 | 0.63 | 2.20 |
| 2025-26 | betmgm | 338 | 0.26 | 1.62 | 1.23 | 0.52 | -0.10 |
| 2025-26 | betrivers | 273 | -0.10 | 1.45 | 1.10 | 0.57 | -0.01 |
| 2025-26 | bovada | 293 | -0.02 | 5.03 | 3.08 | 0.39 | 0.46 |
| 2025-26 | draftkings | 375 | -0.18 | 1.22 | 0.91 | 0.66 | 0.51 |
| 2025-26 | fanatics | 347 | -0.19 | 1.20 | 0.91 | 0.67 | 0.30 |
| 2025-26 | fanduel | 335 | -0.17 | 1.24 | 0.92 | 0.66 | 0.34 |
| 2025-26 | pinnacle | 352 | -0.38 | 3.32 | 2.33 | 0.34 | 1.06 |
| 2026-27 to 11-12 | betmgm | 100 | -0.03 | 1.67 | 1.34 | 0.45 | 0.95 |
| 2026-27 to 11-12 | betrivers | 104 | -0.38 | 1.49 | 1.22 | 0.50 | 1.64 |
| 2026-27 to 11-12 | bovada | 104 | 0.10 | 1.46 | 1.15 | 0.55 | 1.16 |
| 2026-27 to 11-12 | draftkings | 104 | -0.16 | 1.50 | 1.19 | 0.48 | 1.42 |
| 2026-27 to 11-12 | fanatics | 104 | -0.13 | 1.48 | 1.16 | 0.49 | 1.39 |
| 2026-27 to 11-12 | fanduel | 104 | 0.01 | 1.53 | 1.19 | 0.51 | 1.25 |
| 2026-27 to 11-12 | marathonbet | 67 | -0.67 | 1.57 | 1.40 | 0.39 | 2.75 |
| 2026-27 to 11-12 | pinnacle | 98 | -0.55 | 3.29 | 2.36 | 0.40 | 2.12 |

### Totals by the first half's surprise (half-time points minus the share of the pre-game total due by the half)

| book | first-half surprise | quotes | book - mechanical | final - book (+ = over) | over won | second half: actual - book implied |
|---|---|---|---|---|---|---|
| DraftKings | <= -10 (low-scoring half) | 249 | -0.96 | 0.57 | 0.51 | 0.57 |
| DraftKings | -10 to -4 | 308 | -0.36 | -0.06 | 0.45 | -0.06 |
| DraftKings | -4 to +4 | 496 | 0.16 | 0.64 | 0.51 | 0.64 |
| DraftKings | +4 to +10 | 283 | 0.65 | -0.57 | 0.42 | -0.57 |
| DraftKings | >= +10 (high-scoring half) | 291 | 1.38 | 0.47 | 0.48 | 0.47 |
| all decidable books | <= -10 (low-scoring half) | 485 | -1.27 | 0.44 | 0.54 | 0.44 |
| all decidable books | -10 to -4 | 680 | -0.52 | -0.29 | 0.42 | -0.29 |
| all decidable books | -4 to +4 | 948 | 0.05 | 0.50 | 0.50 | 0.50 |
| all decidable books | +4 to +10 | 609 | 0.53 | -0.41 | 0.43 | -0.41 |
| all decidable books | >= +10 (high-scoring half) | 610 | 1.30 | 1.45 | 0.54 | 1.45 |
| Pinnacle (reference) | <= -10 (low-scoring half) | 212 | 0.25 | -0.14 | 0.49 | -0.14 |
| Pinnacle (reference) | -10 to -4 | 274 | 0.20 | -0.38 | 0.43 | -0.38 |
| Pinnacle (reference) | -4 to +4 | 440 | -0.19 | 0.96 | 0.51 | 0.96 |
| Pinnacle (reference) | +4 to +10 | 246 | -0.39 | 0.84 | 0.45 | 0.84 |
| Pinnacle (reference) | >= +10 (high-scoring half) | 261 | -0.43 | 2.39 | 0.51 | 2.39 |

### Totals: the book's second half against what happened (DraftKings, 1,627 games, OLS, SE in brackets)

| fit | const | prior_t | surprise |
|---|---|---|---|
| DraftKings line: (book total - half-time points) | +4.379 (0.499) | +0.473 (0.003) | +0.079 (0.002) |
| what happened: (final - half-time points), same games | -4.050 (6.175) | +0.526 (0.038) | +0.062 (0.029) |

### Spreads: each book's first fresh halftime home spread against the mechanical number

`book - mechanical` > 0: the book gives the home side more points than the half-time margin + the pre-game margin x the usual share. `home cover margin` = final margin + the book's home spread.

| season | book | games | book - mechanical: mean | sd | mean |dev| | share within 1 point | home cover margin: mean |
|---|---|---|---|---|---|---|---|
| 2021-22 | bovada | 250 | 0.38 | 3.07 | 2.50 | 0.26 | 1.14 |
| 2021-22 | draftkings | 257 | 0.33 | 2.81 | 2.31 | 0.28 | 1.09 |
| 2021-22 | pinnacle | 213 | 0.44 | 3.72 | 2.91 | 0.23 | 1.01 |
| 2021-22 | unibet | 263 | 0.39 | 2.70 | 2.25 | 0.28 | 1.30 |
| 2022-23 | bovada | 275 | -0.42 | 2.97 | 2.48 | 0.23 | 0.90 |
| 2022-23 | draftkings | 285 | -0.42 | 2.66 | 2.21 | 0.28 | 0.64 |
| 2022-23 | pinnacle | 252 | -0.26 | 3.69 | 2.85 | 0.23 | 1.04 |
| 2022-23 | unibet | 308 | -0.23 | 2.70 | 2.23 | 0.27 | 1.01 |
| 2023-24 | bovada | 311 | 0.05 | 2.82 | 2.28 | 0.25 | 0.51 |
| 2023-24 | draftkings | 313 | -0.05 | 2.63 | 2.16 | 0.26 | 0.41 |
| 2023-24 | pinnacle | 249 | 0.18 | 3.90 | 2.93 | 0.23 | 0.72 |
| 2023-24 | unibet | 314 | 0.09 | 2.68 | 2.17 | 0.26 | 0.46 |
| 2024-25 | bovada | 292 | 0.47 | 4.81 | 3.49 | 0.22 | 0.35 |
| 2024-25 | draftkings | 294 | 0.12 | 2.78 | 2.33 | 0.23 | -0.03 |
| 2024-25 | pinnacle | 269 | 0.18 | 4.74 | 3.71 | 0.20 | 0.11 |
| 2024-25 | unibet | 294 | 0.06 | 2.96 | 2.47 | 0.23 | -0.10 |
| 2025-26 | betmgm | 286 | 0.06 | 2.67 | 2.18 | 0.29 | 0.29 |
| 2025-26 | betrivers | 348 | 0.03 | 2.71 | 2.22 | 0.27 | 0.52 |
| 2025-26 | bovada | 293 | -0.20 | 4.68 | 3.53 | 0.20 | 0.34 |
| 2025-26 | draftkings | 375 | -0.05 | 2.79 | 2.31 | 0.25 | 0.52 |
| 2025-26 | fanatics | 347 | -0.03 | 2.80 | 2.31 | 0.25 | 0.49 |
| 2025-26 | fanduel | 341 | -0.05 | 2.81 | 2.32 | 0.26 | 0.53 |
| 2025-26 | pinnacle | 352 | -0.10 | 4.48 | 3.34 | 0.23 | 0.66 |
| 2025-26 | unibet | 376 | 0.02 | 2.69 | 2.21 | 0.27 | 0.56 |
| 2026-27 to 11-12 | betmgm | 84 | 0.28 | 2.76 | 2.33 | 0.24 | -0.85 |
| 2026-27 to 11-12 | betrivers | 104 | 0.22 | 2.80 | 2.34 | 0.25 | -1.15 |
| 2026-27 to 11-12 | bovada | 104 | 0.14 | 2.75 | 2.34 | 0.24 | -1.23 |
| 2026-27 to 11-12 | draftkings | 104 | 0.14 | 2.80 | 2.35 | 0.25 | -1.23 |
| 2026-27 to 11-12 | fanatics | 104 | 0.18 | 2.75 | 2.35 | 0.24 | -1.19 |
| 2026-27 to 11-12 | fanduel | 104 | 0.13 | 2.77 | 2.31 | 0.26 | -1.24 |
| 2026-27 to 11-12 | marathonbet | 67 | 0.10 | 2.75 | 2.30 | 0.27 | -1.25 |
| 2026-27 to 11-12 | pinnacle | 98 | 0.20 | 4.11 | 3.05 | 0.28 | -1.02 |
| 2026-27 to 11-12 | unibet | 101 | 0.23 | 2.81 | 2.35 | 0.24 | -1.28 |

### Spreads by the pre-game favourite's half-time lead

Lines on the favourite's side (negative = the favourite gives points). `favourite's cover margin` > 0: the favourite covered the book's halftime number.

| book | pre-game favourite at the half | quotes | book line (favourite's side) | mechanical (favourite's side) | book - mechanical | favourite's cover margin | favourite covered |
|---|---|---|---|---|---|---|---|
| DraftKings | favourite trails by 10+ | 156 | 8.09 | 12.19 | -4.10 | -0.39 | 0.46 |
| DraftKings | trails by 4-10 | 277 | 1.39 | 4.03 | -2.64 | -0.63 | 0.49 |
| DraftKings | trails by 1-4 | 178 | -2.07 | -0.30 | -1.77 | -0.61 | 0.49 |
| DraftKings | level | 57 | -3.73 | -2.50 | -1.22 | -0.24 | 0.47 |
| DraftKings | leads by 1-4 | 306 | -5.42 | -4.85 | -0.57 | -0.33 | 0.48 |
| DraftKings | leads by 4-10 | 325 | -8.86 | -10.08 | 1.23 | -0.84 | 0.48 |
| DraftKings | leads by 10+ | 329 | -15.23 | -18.65 | 3.42 | 0.22 | 0.52 |
| all decidable books | favourite trails by 10+ | 330 | 7.98 | 12.13 | -4.15 | 0.27 | 0.46 |
| all decidable books | trails by 4-10 | 588 | 1.49 | 4.06 | -2.57 | -1.30 | 0.45 |
| all decidable books | trails by 1-4 | 378 | -2.01 | -0.29 | -1.72 | -0.72 | 0.47 |
| all decidable books | level | 113 | -3.61 | -2.36 | -1.25 | -1.59 | 0.42 |
| all decidable books | leads by 1-4 | 609 | -5.34 | -4.87 | -0.47 | -0.18 | 0.48 |
| all decidable books | leads by 4-10 | 677 | -8.88 | -10.24 | 1.35 | -0.55 | 0.47 |
| all decidable books | leads by 10+ | 651 | -15.54 | -19.01 | 3.47 | -0.02 | 0.51 |
| Pinnacle (reference) | favourite trails by 10+ | 139 | 6.14 | 12.35 | -6.21 | -2.55 | 0.33 |
| Pinnacle (reference) | trails by 4-10 | 252 | 0.70 | 4.04 | -3.33 | -1.27 | 0.44 |
| Pinnacle (reference) | trails by 1-4 | 153 | -2.42 | -0.27 | -2.14 | -1.22 | 0.46 |
| Pinnacle (reference) | level | 51 | -3.56 | -2.61 | -0.95 | -0.40 | 0.43 |
| Pinnacle (reference) | leads by 1-4 | 262 | -5.25 | -4.90 | -0.34 | 0.14 | 0.49 |
| Pinnacle (reference) | leads by 4-10 | 292 | -8.56 | -10.10 | 1.54 | -0.48 | 0.46 |
| Pinnacle (reference) | leads by 10+ | 284 | -13.77 | -18.47 | 4.70 | 1.44 | 0.56 |

### Spreads: the book's second-half margin against what happened (DraftKings, 1,628 games, OLS, SE in brackets)

surprise_m = half-time margin - half the pre-game margin (home view).

| fit | const | prior_m | surprise_m |
|---|---|---|---|
| DraftKings line: (-book home spread - half-time margin) | -0.048 (0.028) | +0.502 (0.004) | -0.275 (0.003) |
| what happened: (final margin - half-time margin), same games | +0.665 (0.262) | +0.404 (0.041) | -0.257 (0.024) |

### Is the book's stray from the mechanical number information or noise?

Spread: home cover margin (final margin + book home spread) on (book - mechanical). Total: (final - book) on (book - mechanical). A slope of 0 means the book's stray is information (the book is right where it departs from the formula); +1 for the spread or -1 for the total means the stray is pure noise. In sample, one row per game per book.

| market | book | games | const | slope on (book - mechanical) |
|---|---|---|---|---|
| spread | DraftKings | 1,628 | +0.399 (0.225) | +0.151 (0.082) |
| total | DraftKings | 1,627 | +0.385 (0.305) | -0.681 (0.230) |
| spread | FanDuel | 445 | +0.119 (0.427) | +0.164 (0.152) |
| total | FanDuel | 439 | +0.500 (0.598) | -0.418 (0.455) |
| spread | BetMGM | 370 | +0.024 (0.467) | +0.108 (0.174) |
| total | BetMGM | 438 | +0.239 (0.597) | -0.501 (0.363) |
| spread | Pinnacle (reference) | 1,433 | +0.539 (0.241) | +0.423 (0.058) |
| total | Pinnacle (reference) | 1,433 | +0.635 (0.327) | -1.130 (0.085) |

## 4b. P1, after the fact: fade the book's stray from the mechanical total

Script: `scripts/euroleague_research/r4_posthoc.py`.

### P1 (after the fact): fade the book's stray from the mechanical halftime total, walk-forward

| D | bets | W | L | P | units | ret% | lo% | hi% |
|---|---|---|---|---|---|---|---|---|
| 1.00 | 699 | 379 | 320 | 0 | 5.20 | 0.64 | -5.71 | 6.59 |
| 1.0 2022-23 | 105 | 63 | 42 | 0 | 14.70 | 12.17 | -3.57 | 26.33 |
| 1.0 2023-24 | 141 | 80 | 61 | 0 | 9.85 | 6.07 | -7.18 | 19.88 |
| 1.0 2024-25 | 129 | 63 | 66 | 0 | -12.90 | -8.70 | -21.65 | 4.70 |
| 1.0 2025-26 | 242 | 131 | 111 | 0 | -0.25 | -0.09 | -10.22 | 10.00 |
| 1.0 2026-27 to 11-12 | 82 | 42 | 40 | 0 | -6.20 | -6.31 | -26.16 | 9.67 |
| 1.50 | 398 | 222 | 176 | 0 | 15.79 | 3.39 | -5.16 | 12.01 |
| 1.5 2022-23 | 53 | 32 | 21 | 0 | 7.85 | 12.88 | -8.43 | 33.03 |
| 1.5 2023-24 | 83 | 47 | 36 | 0 | 5.60 | 5.87 | -12.76 | 23.06 |
| 1.5 2024-25 | 61 | 32 | 29 | 0 | -1.35 | -1.92 | -22.84 | 21.37 |
| 1.5 2025-26 | 147 | 86 | 61 | 0 | 13.93 | 8.03 | -4.28 | 21.85 |
| 1.5 2026-27 to 11-12 | 54 | 25 | 29 | 0 | -10.24 | -15.71 | -42.41 | 8.92 |
| 2.00 | 212 | 130 | 82 | 0 | 33.91 | 13.67 | 3.00 | 24.57 |
| 2.0 2022-23 | 28 | 18 | 10 | 0 | 6.50 | 20.19 | -6.52 | 46.89 |
| 2.0 2023-24 | 39 | 22 | 17 | 0 | 2.45 | 5.46 | -19.27 | 31.37 |
| 2.0 2024-25 | 25 | 11 | 14 | 0 | -5.10 | -17.74 | -47.65 | 18.97 |
| 2.0 2025-26 | 88 | 61 | 27 | 0 | 28.97 | 27.94 | 11.40 | 43.07 |
| 2.0 2026-27 to 11-12 | 32 | 18 | 14 | 0 | 1.09 | 2.83 | -26.68 | 29.60 |
| 3.00 | 55 | 35 | 20 | 0 | 11.63 | 18.06 | -1.42 | 37.65 |
| 3.0 2022-23 | 2 | 2 | 0 | 0 | 2.00 | 86.96 | 86.96 | 86.96 |
| 3.0 2023-24 | 8 | 5 | 3 | 0 | 1.55 | 16.85 | -29.89 | 63.59 |
| 3.0 2024-25 | 6 | 2 | 4 | 0 | -2.60 | -37.68 | -100.00 | 24.64 |
| 3.0 2025-26 | 25 | 18 | 7 | 0 | 9.70 | 32.86 | 2.13 | 61.73 |
| 3.0 2026-27 to 11-12 | 14 | 8 | 6 | 0 | 0.98 | 5.94 | -33.51 | 36.61 |

### P1 at D = 2.0: the kill-test splits

Price range: median -115, shortest -140, longest +100, shorter than -300: 0.0%, shorter than -500: 0.0%.

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | share% |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 D 2.0 | all | 212 | 130 | 82 | 0 | 33.91 | 13.67 | 3.00 | 24.57 |  |
| P1 D 2.0 | season 2023 | 28 | 18 | 10 | 0 | 6.50 | 20.19 | -6.52 | 46.89 |  |
| P1 D 2.0 | season 2024 | 39 | 22 | 17 | 0 | 2.45 | 5.46 | -19.27 | 31.37 |  |
| P1 D 2.0 | season 2025 | 25 | 11 | 14 | 0 | -5.10 | -17.74 | -47.65 | 18.97 |  |
| P1 D 2.0 | season 2026 | 88 | 61 | 27 | 0 | 28.97 | 27.94 | 11.40 | 43.07 |  |
| P1 D 2.0 | season 2027 | 32 | 18 | 14 | 0 | 1.09 | 2.83 | -26.68 | 29.60 |  |
| P1 D 2.0 | early half of each season | 104 | 66 | 38 | 0 | 21.17 | 17.37 | 1.77 | 32.44 |  |
| P1 D 2.0 | late half of each season | 108 | 64 | 44 | 0 | 12.74 | 10.10 | -6.14 | 26.15 |  |
| P1 D 2.0 | without its 10 best dates | 186 | 104 | 82 | 0 | 7.91 | 3.65 | -6.65 | 14.77 |  |
| P1 D 2.0 | side = over | 89 | 58 | 31 | 0 | 21.54 | 20.65 | 4.03 | 36.58 | 42.00 |
| P1 D 2.0 | side = under | 123 | 72 | 51 | 0 | 12.37 | 8.61 | -5.87 | 22.87 | 58.00 |
| P1 D 2.0 | bookmaker = betmgm | 57 | 37 | 20 | 0 | 13.42 | 19.93 | -2.90 | 40.42 | 26.90 |
| P1 D 2.0 | bookmaker = betrivers | 25 | 14 | 11 | 0 | 0.37 | 1.20 | -27.78 | 30.22 | 11.80 |
| P1 D 2.0 | bookmaker = draftkings | 119 | 69 | 50 | 0 | 11.27 | 8.21 | -5.94 | 23.44 | 56.10 |
| P1 D 2.0 | bookmaker = fanatics | 1 | 1 | 0 | 0 | 1.00 | 86.96 | 86.96 | 86.96 | 0.50 |
| P1 D 2.0 | bookmaker = fanduel | 10 | 9 | 1 | 0 | 7.85 | 68.26 | 31.00 | 87.72 | 4.70 |
| P1 D 2.0 | price band +100..+150 | 1 | 1 | 0 | 0 | 1.00 | 100.00 | 100.00 | 100.00 | 0.50 |
| P1 D 2.0 | price band -150..-100 | 211 | 129 | 82 | 0 | 32.91 | 13.32 | 2.31 | 24.29 | 99.50 |

Placebo for P1 at D = 2.0 (200 draws: each game gets another game's side and stray size from the same season, bet at its own quote): mean -5.66%, 5th-95th percentile -15.45% to +3.67% (median 212 bets); real +13.67% on 212; share of draws at or above the real result 0.0%.

## 5. Multiplicity: Benjamini-Hochberg across every registered cell

Script: `scripts/euroleague_research/r4_report.py`.

**every graded cell: 183 cells; 0 survive at a 10% false-discovery rate.**

**cells with 25+ bets: 183 cells; 0 survive at a 10% false-discovery rate.**

**secondary, not pre-registered: the method cells only (experiment 3 and P1): 79 cells; 0 survive at 10%.**

**secondary, not pre-registered: the 25 spread cells of experiment 3 only (a family chosen after seeing it; the cells share most of their bets): 25 cells; 17 survive at 10%.**

| experiment | cell | bets | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|
| 3 V2 Pinnacle's close as the prior | spread cut 0.05 | 364 | 45.34 | 10.93 | 3.40 | 18.48 | 0.0096 |
| 3 ported unchanged | spread cut 0.08 | 177 | 30.16 | 15.03 | 3.36 | 26.10 | 0.0151 |
| 3 V2 Pinnacle's close as the prior | spread cut 0.12 | 117 | 23.36 | 17.59 | 3.19 | 30.45 | 0.0171 |
| 3 V1 no minimum of other books | spread cut 0.08 | 178 | 29.01 | 14.37 | 2.52 | 25.34 | 0.0187 |
| 3 ported unchanged | spread cut 0.03 | 449 | 46.61 | 9.10 | 1.87 | 16.14 | 0.0203 |
| 3 V1 no minimum of other books | spread cut 0.03 | 451 | 46.46 | 9.03 | 1.75 | 16.07 | 0.0204 |
| 3 V2 Pinnacle's close as the prior | spread cut 0.08 | 227 | 30.93 | 11.98 | 1.89 | 21.71 | 0.0238 |
| 3 V4 first crossing | spread cut 0.08 | 208 | 29.05 | 12.29 | 2.44 | 23.04 | 0.0277 |
| 3 V4 first crossing | spread cut 0.05 | 363 | 38.19 | 9.20 | 1.14 | 17.01 | 0.0300 |
| 3 ported unchanged | spread cut 0.02 | 518 | 42.74 | 7.23 | 0.61 | 14.06 | 0.0397 |
| 3 V1 no minimum of other books | spread cut 0.02 | 520 | 42.59 | 7.18 | 0.51 | 13.99 | 0.0399 |
| 3 V2 Pinnacle's close as the prior | spread cut 0.03 | 476 | 39.68 | 7.31 | 0.37 | 14.17 | 0.0407 |
| 3 V3 last read of the break decides | spread cut 0.05 | 300 | 29.68 | 8.67 | -0.03 | 17.35 | 0.0469 |
| 3 V4 first crossing | spread cut 0.03 | 500 | 39.95 | 7.00 | -0.32 | 13.51 | 0.0472 |
| 3 ported unchanged | spread cut 0.05 | 312 | 29.80 | 8.37 | -0.06 | 16.33 | 0.0506 |
| 3 V3 last read of the break decides | spread cut 0.03 | 430 | 35.05 | 7.13 | -0.27 | 14.39 | 0.0543 |
| 3 V1 no minimum of other books | spread cut 0.05 | 313 | 28.65 | 8.02 | -0.26 | 16.12 | 0.0575 |

The 15 smallest one-sided p-values (date bootstrap, `r2_lib.p_one_sided`):

| experiment | cell | bets | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|
| 3 V2 Pinnacle's close as the prior | spread cut 0.05 | 364 | 45.34 | 10.93 | 3.40 | 18.48 | 0.0096 |
| 3 ported unchanged | spread cut 0.08 | 177 | 30.16 | 15.03 | 3.36 | 26.10 | 0.0151 |
| 3 V2 Pinnacle's close as the prior | spread cut 0.12 | 117 | 23.36 | 17.59 | 3.19 | 30.45 | 0.0171 |
| P1 after-the-fact: fade the stray from the mechanical total | D 2.0 | 212 | 33.91 | 13.67 | 3.00 | 24.57 | 0.0179 |
| 3 V1 no minimum of other books | spread cut 0.08 | 178 | 29.01 | 14.37 | 2.52 | 25.34 | 0.0187 |
| 3 ported unchanged | spread cut 0.03 | 449 | 46.61 | 9.10 | 1.87 | 16.14 | 0.0203 |
| 3 V1 no minimum of other books | spread cut 0.03 | 451 | 46.46 | 9.03 | 1.75 | 16.07 | 0.0204 |
| 3 V2 Pinnacle's close as the prior | spread cut 0.08 | 227 | 30.93 | 11.98 | 1.89 | 21.71 | 0.0238 |
| 3 V4 first crossing | spread cut 0.08 | 208 | 29.05 | 12.29 | 2.44 | 23.04 | 0.0277 |
| 3 V4 first crossing | spread cut 0.05 | 363 | 38.19 | 9.20 | 1.14 | 17.01 | 0.0300 |
| 3 ported unchanged | spread cut 0.02 | 518 | 42.74 | 7.23 | 0.61 | 14.06 | 0.0397 |
| 3 V1 no minimum of other books | spread cut 0.02 | 520 | 42.59 | 7.18 | 0.51 | 13.99 | 0.0399 |
| 3 V2 Pinnacle's close as the prior | spread cut 0.03 | 476 | 39.68 | 7.31 | 0.37 | 14.17 | 0.0407 |
| 3 V3 last read of the break decides | spread cut 0.05 | 300 | 29.68 | 8.67 | -0.03 | 17.35 | 0.0469 |
| 3 V4 first crossing | spread cut 0.03 | 500 | 39.95 | 7.00 | -0.32 | 13.51 | 0.0472 |

Cells per experiment:

| experiment | cells |
|---|---|
| 2a blind, first fresh quote per book | 94 |
| 2b blind, best decidable price | 10 |
| 3 V1 no minimum of other books | 15 |
| 3 V2 Pinnacle's close as the prior | 15 |
| 3 V3 last read of the break decides | 15 |
| 3 V4 first crossing | 15 |
| 3 ported unchanged | 15 |
| P1 after-the-fact: fade the stray from the mechanical total | 4 |

## 6. Verdict (written after every table above; each number is quoted from them)

Script: `scripts/euroleague_research/r4_verdict.py` (text only; the numbers are the tables').

### 6.1 What the sample resolves
A blind bet at the best decidable price covers about 1,600 games a market (section 2b, "What the sample resolves").
That resolves its return to about ±3.7 points: a 90% half-width of 3.74 for totals, 3.64 for spreads and 1.99 for moneyline favourites.
A rule with about 300 bets resolves to about ±8 points; rule A's interval has a half-width of 8.2.
So a true +8% edge sits right at the edge of what this sample can show.

### 6.2 Per market, at the pre-registered headline cut of 0.05 (pooled walk-forward, 2022-23 to 2026-27)

| Market | Rule | Bets | Units | Return [90%] | Verdict |
|---|---|---|---|---|---|
| Total | ported unchanged | 574 | -12.61 | -1.93% [-8.44, +4.23] | **null** |
| Moneyline | the margin model priced as a moneyline (an extension) | 164 | -0.51 | -0.24% [-13.25, +12.85] | **null** |
| Spread | **A**: ported unchanged | 312 | +29.80 | +8.37% [-0.06, +16.33] | lead; misses the bar (below) |
| Spread | **B**: variant 2, Pinnacle's close as the prior | 364 | +45.34 | +10.93% [+3.40, +18.48] | lead; misses the bar (below) |
| Total | **P1** (after the fact): fade the book's stray from the mechanical total, D = 2 | 212 | +33.91 | +13.67% [+3.00, +24.57] | after-the-fact lead; fails |

**Why the total fails.** Out of sample, the ported model expects 0.02 to 1.77 more second-half points than EuroLeague games score, in every season (section 3).
It is also too sure: it claims 0.54-0.59 and wins 0.49-0.51. So it leans to the over: 99% of its 574 bets at 0.05 are overs, and the blind over loses 10.04% at the best decidable price.
In the split tables for the total (C and D in section 3b), the row labelled "underdog" is the whole rule, because a total has no favourite.
At the 0.12 cut it reads 120 bets, +6.80%. That passed the placebo. It failed the side split (98% overs), the 10-best-dates test (-6.68%) and the neighbourhood (0.05 reads -1.93%, 0.08 reads +0.75%).

**Why the moneyline fails.** Most games are lost to the price band. In a full season, 142 to 184 games had a fresh decidable quote but none inside -250 to +250, so the rule decides only 117 to 189 games a season.
On the games it does decide, it pays nothing at any cut.

**The spread leads, test by test.** A is the ported rule; B is variant 2.

| Test | A (ported) | B (Pinnacle prior) |
|---|---|---|
| 200+ bets with the 90% interval above zero | **fail**: 312 bets, lower bound -0.06 | pass: 364 bets, lower bound +3.40 |
| Every season with 30+ bets positive | **fail**: 2023-24 -2.53% on 50 (4 of 5 seasons positive) | **fail**: 2023-24 -1.65% on 61 (4 of 5 positive) |
| One part-season carrying the total | **leans on it**: 2026-27 to date, 26 bets, carries 13.30 of 29.80 units | **leans on it**: 2026-27 to date, 31 bets, carries 11.85 of 45.34 units |
| 2021-22 second look (fitted on 2022-23, not walk-forward) | **fail**: -17.01% on 36 | **fail**: -3.55% on 33 |
| Early and late halves of each season both positive | pass, barely: +16.06% / +0.75% | pass: +15.84% / +6.20% |
| Neighbouring cuts (0.02 to 0.12) all positive | pass: +7.23, +9.10, +8.37, +15.03, +3.28 | pass: +4.45, +7.31, +10.93, +11.98, +17.59 |
| Without its 10 best dates | weak: +2.63% (those dates carry 21.05 of 29.80 units) | pass: +6.18% |
| Side split, home/away (70% line) | pass: 62% away | pass: 67% away |
| Side split, favourite/underdog (70% line) | **fail**: 72.4% halftime underdogs | **fail**: 78.0% halftime underdogs |
| Blind control: every decided game on the same kind of side, at the same quotes | pass: underdog -2.01%, ahead of its expected first half -5.86%, behind it -7.28% | pass: -2.20%, -4.58%, -8.59% |
| Placebo (half-time score shuffled across games within each season, 200 times) | pass: real +8.37% against a 95th percentile of -0.45%; 0% of shuffles at or above it | pass: +10.93% against -1.09%; 0% |
| The rule's bets turned round | -21.26% | -23.91% |
| Return rises with the claimed edge | **fail**: 0.05-0.08 band -0.23% on 135; 0.08-0.12 +26.09% on 91; 0.12-0.20 +3.56% | pass, roughly: under 0.05 loses (-4.19, -4.05, -8.07); 0.05 and up pays (+9.19, +6.04, +19.34, +11.75) |
| Fresh quotes only (the fresh rule removed instead) | +9.83%: no difference, because the books re-hang during the break anyway | +11.95%: the same |
| The other read (the last read of the break decides) | pass: +8.67% | pass: +6.96% |
| Price range | median -115, -135 to +105, none shorter than -300 | the same |
| Benjamini-Hochberg at 10% | **fail**: p 0.0506; 0 of 183 cells survive | **fail**: p 0.0096; the first-rank threshold is 0.00055; 0 of 183 survive, and 0 of the 79 method cells |
| Chosen before seeing results | yes (the pre-registered headline) | no: the best of five pre-registered spread rules |

The 25 spread cells of experiment 3 taken alone pass the correction: 17 of 25 survive. That family was chosen after seeing it, and its cells share most of their bets.
That is a secondary read, not a pass.

**P1** (after the fact) passed the donor placebo: 0% of draws reached +13.67%, and the draws' 95th percentile is +3.67%.
It passed the side split (58% unders) and both halves of each season (+17.37% / +10.10%).
It **failed** on four counts. 2025-26 carries 28.97 of its 33.91 units, and 2024-25 reads -17.74% on 25. Without its 10 best dates it reads +3.65%. A stray of 1.0 or 1.5 points reads only +0.64% and +3.39%. And it was chosen with the deviation table in view.

### 6.3 The structural check (experiment 4): are halftime lines re-hung mechanically?
- **Totals: yes, closely, and with no systematic miss.** DraftKings' first fresh halftime total sits within 1 point of the mechanical line in 43-66% of games, depending on the season.
  Its mean distance from that line is 0.90-1.30 points. The mechanical line is half-time points + the pre-game total × 0.50.
  DraftKings carries 0.079 (SE 0.002) of the first half's surprise into the second half. The games carried 0.062 (SE 0.029).
  After a high- or a low-scoring half the book does not miss in one direction: the final minus the book's total runs from -0.57 to +0.64 across the surprise bins at DraftKings, with no pattern.
  Where the book departs from the mechanical line, most of the departure is noise: slope -0.68 (SE 0.23) at DraftKings, and -1.13 at Pinnacle. That is what P1 tried to bet.
- **Spreads: the first-half surprise is handed back at the right rate, and the pre-game margin is over-weighted.**
  DraftKings hands back 27.5% of the first-half surprise (SE 0.3). The games handed back 25.7% (SE 2.4).
  But it carries 50.2% of the pre-game margin into the second half, where the games carried 40.4% (SE 4.1). Home teams also beat the book's second half by 0.67 points (SE 0.26).
  These are in-sample fits over all seasons. The result: the pre-game favourite failed to cover the decidable books' halftime number in every lead bin except "leads by 10+".
  It covered 42-48% in those bins and 51% at 10+. That holds whether the favourite trails or leads.
  This is the mechanism the spread leads trade. The walk-forward margin model carries 0.38-0.48 of the pre-game margin, against the books' 0.50, which is why 72-78% of its bets are halftime underdogs.
  Where the book's spread departs from the mechanical number, most of the departure is information: slope +0.15 (SE 0.08) at DraftKings.

### 6.4 What a live loop would need (no live EuroLeague in-play feed exists yet)
- **Books that post halftime full-game lines.** DraftKings in every season since 2021-22: totals and spreads in 92-100% of games with a read in the break, and the moneyline in 90-97%.
  FanDuel, BetMGM, BetRivers and Fanatics from 2025-26, in 73-100% of games. Before 2025-26, DraftKings was the only book a pick may name.
- **The window.** The break runs a median 15.97 minutes from the last second-quarter shot to the first third-quarter shot (10th-90th percentile 15.38-17.16).
  Inside the one-minute buffers that leaves 13.97 minutes.
  The decidable books' first fresh total is stamped at most a median 3.10 minutes after the last shot. That leaves about 12 minutes to read and bet.
  At the five-minute cadence a break holds a median of 3 reads (2 to 5). In 2021-22, at the ten-minute cadence, it held 1 or 2.
- **Inputs.** A live score source that marks the end of the second quarter and gives the half-time score. EuroLeague's live play-by-play, which the shot chart comes from, is the obvious one.
  The lag between that source and the books cannot be measured until it runs live, so it must be logged from its first day.
  The pre-game prior: the median of the books' last pre-game spread and total, or Pinnacle's last pre-game spread for variant 2. Both are already collected before tip.
  An in-play odds poll of the five decidable books every few minutes during the break, with every read stored as its own price log.
  The decision itself: one per game, at the first read after the half ends that holds a fresh eligible quote.
- **Volume** at 0.05: A made 84, 50, 52, 100 and 26 bets in the five walk-forward seasons, the last over 104 games to date. In 2025-26 that was 100 bets on 376 games with five books, about one game in four.

### 6.5 What would change the verdict
The spread is the one market with a mechanism, a passed placebo, a plateau and blind controls that lose. It still misses the multiplicity bar, one season is negative in each version, and the earliest season reads negative on a second look.
What would move it is games it has never seen. Freeze variant 2 at cut 0.05 as it stands (Pinnacle's close as the prior, the walk-forward fit on every earlier season), and read it unchanged on games after 2026-11-12. That needs halftime prices stored from now on.
The total and the moneyline are null as ported. P1 is a frozen after-the-fact lead, to be read the same way.

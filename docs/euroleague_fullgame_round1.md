# EuroLeague full-game markets (moneyline, spread, total): research round 1, 2026-11-13

Run by a read-only research agent on the local parquet cache only (no paid
call, no database, no API key read). Every table below names the script that
printed it; `scripts/euroleague_research/r2_report.py` reruns them all and
rewrites this file. Seasons are named by their years (2025-26); in the tables
they carry the repo's ENDING-year label (2026 = 2025-26). Results are in units
on the posted stake (1 unit to win, risk capped at 3), graded at each book's
quoted price; intervals are 90%, resampling game dates. The settings were
frozen before any return was read (the docstring of `r2_lib.py`).

## Verdicts (written from the tables below)

**Nothing clears the bar.** No rule passes all three of: positive
walk-forward in every finished season, positive without its 10 best dates,
and surviving the multiplicity correction (the table says which each failed). Two patterns are real enough to carry forward,
neither shippable as it stands.

| Market | Best result | Status | What killed it, or what is missing |
|---|---|---|---|
| Spread, line shopping against the books' median | 538 bets, +45.32 units, +7.78% [+0.41, +14.37] (15:00 UTC read, cut 0.03, 2023-24 on) | **Dead as line shopping** | 99.6% of bets are the home team; 345 of 538 sit exactly on the consensus number; the same sides re-bet at the consensus line at -110 keep +6.89%; closing-line value -0.02 (13% beat Pinnacle's close); without its 10 best dates +2.61% [-4.54, +9.48]; 2026-27 -25.26% on 41; every book but DraftKings negative. It is a home lean through the margin table, not an off-market number (the c = 0 placebo at cut 0.03: 87 bets -5.62%). |
| Total, line shopping | 160 bets +1.91% at the close; -4.63% at 15:00 UTC | Null | negative at most reads and cuts |
| Moneyline against the same book's spread | 86 bets -11.00% (catalogued cut 0.01, -200 floor) | Null | negative at every read |
| First post against Pinnacle | 6 moneyline bets in all | **Cannot run** | Pinnacle posts after the soft books: it was standing at 45 of 310, 52 of 331 and 6 of 330 DraftKings first posts (2022-23 to 2024-25) |
| First post priced off its own spread (the catalogued card) | 51 bets +1.17% (cut 0.015, any 3 books up) | Null | small and flat |
| Sharp against soft at one moment | 121 moneyline bets +0.14% at the close (cut 0); spreads and totals 13-23 bets | Null, no volume | the soft books almost never beat Pinnacle's fair at the same number |
| Relocated "home" games (lead i) | residual +0.74 points [-1.35, +2.80] on 80 games vs +0.48 [+0.01, +0.98] at ordinary home games; away on them -14.26% | Null | the relocated home teams did not under-perform the line |
| Home edge by club (lead ii) | out-of-sample slope 0.30 (SE 0.31); the rule 692 bets -0.45% | Null | no persistence by club |
| **Home underdog against the spread** (scout lead 3) | 454 bets +48.34 units, +9.72% [+2.44, +16.89] at the DraftKings close; +11.00% at the best decidable close; rises with the dog (+19.41% at +5 or more, 156 bets) | **Lead, not a pass** | 2025-26 carries 31.09 of 48.34 units; 2023-24 -6.12% and 2026-27 -24.06% (30); without its 10 best dates +5.37% [-2.04, +12.60]; the walk-forward version (buckets chosen from earlier seasons) +3.16% [-2.55, +8.88]; fails the multiplicity correction (best p 0.0025 against a bar of 0.00035); chosen with the residual table in view |
| Home by previous-season attendance (scout lead 2) | top tercile 456 bets +6.53% [-0.86, +13.44] | Not a pass | 2022-23 carries 25.00 of 32.42 units; early half -0.64%; without its 10 best dates +2.21% |
| **Moneyline favourites at -500 or shorter** (lead iii) | 188 bets +34.59 units, +6.13% [+2.27, +9.60] at the DraftKings close; +7.74% at its first post; +6.32% at Pinnacle's close | **Lead; the price range is mike's call** | 5 of 6 seasons positive (2022-23 -1.39%); both halves positive; +4.69% [+0.71, +8.41] without its 10 best dates; survives the multiplicity correction at the DraftKings first post and the best decidable close, not at the DraftKings close (p 0.0023). Every bet lays a median -675 (shortest -4000): 564 units risked to win 73.6; 13 losses at 3 units each. 96% are home favourites. |

**On the multiplicity count** (283 cells, 4 survive): two of the four
survivors are the 90%-or-more moneyline buckets, where every bet won (35 at
DraftKings, 31 at Pinnacle). A band with no losses has no spread in the
date bootstrap, so its p-value is degenerate; read those two as the same
heavy-favourite pattern, not as separate findings.

**The open is as accurate as the close.** On the same 1,642 games,
Pinnacle's moneyline log loss is 0.6105 at its first post and 0.6116 at the
close; DraftKings' 0.6121 and 0.6105 (r2_accuracy.py). Little arrives between
the first post and the tip that the price did not already hold, which is why
the first-post and sharp-against-soft methods find nothing to work with here.
No EuroLeague moneyline floor exists yet (the -200 cap is the college
basketball model's), so whether the heavy-favourite band's prices (median
-675, shortest -4000, 3 units risked a bet) are bettable is a decision, not a
rule that already blocks it.

**The one fact under most of this.** The market underprices the home team.
At Pinnacle's close the home side won 63% against a no-vig 60% (1,642 games,
r2_accuracy.py), and ordinary home games beat the closing spread by +0.48
points. The gap sits on home underdogs (+2.06 points at +1.5 to +5, +2.80 at
+5 or more) and the heaviest home favourites, while away favourites priced at
65-80% won 58.7% (-18.15% at DraftKings). It is not stable: 2026-27 to date
reverses it (home won 54% against 60% priced, 107 games).

**What the sample resolves.** About 1,770 DraftKings games, 2021-22 to
2026-27 to date: one side of a market is resolved to about +/-3.5 to 3.8
points at 90% (r2_baselines.py, last table); a 450-bet rule to about +/-7.

**Data check.** 24 of 397,197 stored quotes were incoherent (a price inside
-100..+100 or an implied sum outside 1.00-1.15) and were dropped. The home
number's sign agrees with the moneyline favourite on 98-100% of last pre-tip
pairs at every book (DraftKings 1,753 of 1,772; the misses are mostly
even-money moneylines beside a -1.5 spread). Pinnacle's closing spread: home
teams laying points won 69.3%, home teams getting points 45.9%.

**Corrections to the brief.**
- DraftKings DID price 2021-22: 292 games, 13,566 rows (r2_coverage.py).
- DraftKings does not post late in the stored history: its first post is a
  median 45-73 hours before the tip, against Pinnacle's 28-43 hours
  (r2_coverage.py B).
- `snapshot_at` is not the 5-minute clock. It is the book's own update stamp:
  0.04% equal a purchase snapshot time, and the snapshot that captured each
  row came a median 46 seconds later (100% within 900 seconds). Every decision
  here is read at a purchase snapshot time.

**Next to test.** (1) The home underdog spread, frozen as it stands, read
unchanged on 2026-27 as it is played; and graded on 2020-21 if that season is
ever bought (it is the only unseen priced season the feed has). (2) The same
home lean on the moneyline (home underdogs) and on the first half. (3) A
market-anchored model of the home edge (the market's own number plus a
penalised home-underdog and attendance term, fitted on earlier seasons
only), against the market alone. (4) Totals: the referee crews are stored
per game (lead 5); and at DraftKings' first post overs lost only -1.38%
against -7.69% for unders, so the opening total may sit low.

## Multiplicity (r2_report.py)

Hypothesis cells with 25+ bets: **283** (scripts r2_baselines, r2_firstpost, r2_leads, r2_leads2, r2_methods; season splits, kill-test subsets and neighbourhood reads excluded). One-sided p < 0.05: 29; < 0.01: 14; positive return: 111. **Surviving Benjamini-Hochberg at a 10% false-discovery rate: 4.**

The BH bar for the single best cell is p <= 0.00035.

The 15 smallest p-values:

| script | table | row | bets | ret% | p_one | survives |
|---|---|---|---|---|---|---|
| r2_leads | (iii) Favourite-longshot: moneyline sides at the close by th | draftkings / >=90% / 35 / 35 / 0 / 0 / 7.92 / 7.55 / 7.07 / 8.00 / 0.0000 / 92.02 / 100.00 / 100.00 | 35 | 7.55 | 0.0000 | yes |
| r2_baselines | Moneyline sides by price band (every side, unfloored), poole | first / draftkings / <=-500 / 178 / 168 / 10 / 0 / 41.33 / 7.74 / 4.36 / 10.84 / 0.0000 / 84.08 / 94.38 | 178 | 7.74 | 0.0000 | yes |
| r2_leads | (iii) Favourite-longshot: moneyline sides at the close by th | pinnacle / >=90% / 31 / 31 / 0 / 0 / 7.65 / 8.23 / 7.67 / 8.78 / 0.0000 / 91.72 / 100.00 / 100.00 | 31 | 8.23 | 0.0000 | yes |
| r2_baselines | Moneyline sides by price band (every side, unfloored), poole | close / best decidable / <=-500 / 182 / 171 / 11 / 0 / 38.74 / 7.10 / 3.53 / 10.11 / 0.0002 / 84.13 / 93.96 | 182 | 7.1 | 0.0002 | yes |
| r2_baselines | Moneyline sides by price band (every side, unfloored), poole | close / draftkings / <=-500 / 188 / 175 / 13 / 0 / 34.59 / 6.13 / 2.27 / 9.60 / 0.0023 / 84.12 / 93.09 | 188 | 6.13 | 0.0023 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line >= +1.5 / best decidable close / all 2021-22 on / 414 / 242 / 168 / 4 / 57.73 | 414 | 12.82 | 0.0025 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line > 0 / DraftKings 15utc / all 2021-22 on / 447 / 261 / 182 / 4 / 61.45 / 12.57 | 447 | 12.57 | 0.0026 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line >= +5 / best decidable close / all 2021-22 on / 158 / 98 / 57 / 3 / 34.98 / 20 | 158 | 20.51 | 0.0032 | no |
| r2_baselines | Moneyline sides by price band (every side, unfloored), poole | close / pinnacle (reference, not bettable) / <=-500 / 161 / 150 / 11 / 0 / 30.51 / 6.32 / 2.14 / 9.93 / 0.0037 | 161 | 6.32 | 0.0037 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line >= +5 / DraftKings close / all 2021-22 on / 156 / 96 / 57 / 3 / 32.80 / 19.41 | 156 | 19.41 | 0.0047 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line > 0 / best decidable close / all 2021-22 on / 455 / 262 / 189 / 4 / 54.54 / 11 | 455 | 11.0 | 0.0053 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line >= +5 / DraftKings 15utc / all 2021-22 on / 156 / 96 / 58 / 2 / 32.20 / 18.87 | 156 | 18.87 | 0.0055 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line >= +1.5 / DraftKings 15utc / all 2021-22 on / 405 / 235 / 166 / 4 / 53.04 / 12 | 405 | 12.01 | 0.0070 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line >= +1.5 / DraftKings close / all 2021-22 on / 412 / 238 / 170 / 4 / 50.53 / 11 | 412 | 11.22 | 0.0073 | no |
| r2_leads2 | H3, the home underdog against the spread (blind) | H3 home underdog ATS, home line > 0 / DraftKings close / all 2021-22 on / 454 / 259 / 191 / 4 / 48.34 / 9.72 /  | 454 | 9.72 | 0.0126 | no |

## r2_coverage.py

### A. Games with any pre-game quote, by season, market and book (all rows, coherent or not)

| season | market | draftkings | fanduel | betmgm | betrivers | fanatics | pinnacle | bovada | marathonbet | unibet | paddypower | played |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | h2h | 292 | 0 | 0 | 0 | 0 | 240 | 292 | 284 | 292 | 270 | 299 |
| 2022 | spreads | 292 | 0 | 0 | 0 | 0 | 240 | 292 | 0 | 292 | 0 | 299 |
| 2022 | totals | 292 | 0 | 0 | 0 | 0 | 240 | 292 | 0 | 292 | 0 | 299 |
| 2023 | h2h | 310 | 0 | 0 | 0 | 0 | 272 | 326 | 326 | 328 | 322 | 328 |
| 2023 | spreads | 310 | 0 | 0 | 0 | 0 | 272 | 326 | 0 | 328 | 0 | 328 |
| 2023 | totals | 310 | 0 | 0 | 0 | 0 | 272 | 326 | 0 | 328 | 0 | 328 |
| 2024 | h2h | 331 | 0 | 0 | 0 | 0 | 291 | 331 | 322 | 331 | 330 | 331 |
| 2024 | spreads | 331 | 0 | 0 | 0 | 0 | 291 | 331 | 0 | 331 | 0 | 331 |
| 2024 | totals | 331 | 0 | 0 | 0 | 0 | 291 | 331 | 0 | 331 | 0 | 331 |
| 2025 | h2h | 330 | 0 | 0 | 0 | 0 | 330 | 330 | 319 | 326 | 330 | 330 |
| 2025 | spreads | 330 | 0 | 0 | 0 | 0 | 330 | 330 | 0 | 326 | 0 | 330 |
| 2025 | totals | 330 | 0 | 0 | 0 | 0 | 330 | 330 | 0 | 188 | 0 | 330 |
| 2026 | h2h | 402 | 369 | 358 | 372 | 372 | 402 | 383 | 402 | 402 | 402 | 402 |
| 2026 | spreads | 402 | 369 | 309 | 372 | 372 | 402 | 383 | 0 | 402 | 0 | 402 |
| 2026 | totals | 402 | 362 | 358 | 297 | 372 | 402 | 383 | 0 | 0 | 0 | 402 |
| 2027 | h2h | 107 | 107 | 105 | 107 | 107 | 107 | 107 | 93 | 107 | 107 | 107 |
| 2027 | spreads | 107 | 107 | 92 | 107 | 107 | 107 | 107 | 67 | 107 | 0 | 107 |
| 2027 | totals | 107 | 107 | 105 | 107 | 107 | 107 | 107 | 67 | 0 | 0 | 107 |

### A2. Games with a decidable quote, a Pinnacle quote, and both

| season | market | any_decidable | pinnacle | decidable_and_pinnacle |
|---|---|---|---|---|
| 2022 | h2h | 292 | 240 | 240 |
| 2022 | spreads | 292 | 240 | 240 |
| 2022 | totals | 292 | 240 | 240 |
| 2023 | h2h | 310 | 272 | 272 |
| 2023 | spreads | 310 | 272 | 272 |
| 2023 | totals | 310 | 272 | 272 |
| 2024 | h2h | 331 | 291 | 291 |
| 2024 | spreads | 331 | 291 | 291 |
| 2024 | totals | 331 | 291 | 291 |
| 2025 | h2h | 330 | 330 | 330 |
| 2025 | spreads | 330 | 330 | 330 |
| 2025 | totals | 330 | 330 | 330 |
| 2026 | h2h | 402 | 402 | 402 |
| 2026 | spreads | 402 | 402 | 402 |
| 2026 | totals | 402 | 402 | 402 |
| 2027 | h2h | 107 | 107 | 107 |
| 2027 | spreads | 107 | 107 | 107 |
| 2027 | totals | 107 | 107 | 107 |

### B. Each book's first post (any market): median hours before tip

| season | draftkings | fanduel | betmgm | betrivers | fanatics | pinnacle | bovada | marathonbet | unibet | paddypower |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 45.80 |  |  |  |  | 35.30 | 61.10 | 69.20 | 57.00 | 74.70 |
| 2023 | 45.00 |  |  |  |  | 28.30 | 61.10 | 77.50 | 76.00 | 75.90 |
| 2024 | 69.30 |  |  |  |  | 43.40 | 37.40 | 79.10 | 72.10 | 78.00 |
| 2025 | 72.80 |  |  |  |  | 27.90 | 26.80 | 79.20 | 75.70 | 78.20 |
| 2026 | 68.20 | 83.10 | 57.60 | 47.90 | 81.80 | 29.90 | 28.30 | 79.80 | 67.00 | 91.80 |
| 2027 | 69.20 | 119.70 | 78.80 | 56.50 | 119.70 | 29.00 | 28.50 | 95.30 | 56.50 | 186.00 |

### B2. First post by market (hours before tip, median)

| season | market | betmgm | betrivers | draftkings | fanatics | fanduel | pinnacle |
|---|---|---|---|---|---|---|---|
| 2022 | h2h |  |  | 45.80 |  |  | 35.30 |
| 2022 | spreads |  |  | 45.80 |  |  | 35.30 |
| 2022 | totals |  |  | 45.80 |  |  | 35.40 |
| 2023 | h2h |  |  | 45.00 |  |  | 28.30 |
| 2023 | spreads |  |  | 45.00 |  |  | 28.30 |
| 2023 | totals |  |  | 45.00 |  |  | 28.30 |
| 2024 | h2h |  |  | 69.30 |  |  | 43.40 |
| 2024 | spreads |  |  | 69.30 |  |  | 43.40 |
| 2024 | totals |  |  | 69.30 |  |  | 43.40 |
| 2025 | h2h |  |  | 72.80 |  |  | 27.90 |
| 2025 | spreads |  |  | 72.80 |  |  | 27.90 |
| 2025 | totals |  |  | 72.80 |  |  | 27.90 |
| 2026 | h2h | 68.90 | 47.80 | 68.20 | 90.30 | 90.20 | 29.90 |
| 2026 | spreads | 55.20 | 47.80 | 68.20 | 90.30 | 90.20 | 29.90 |
| 2026 | totals | 55.80 | 47.90 | 68.20 | 74.90 | 77.50 | 29.90 |
| 2027 | h2h | 81.60 | 56.50 | 69.20 | 185.00 | 186.00 | 29.00 |
| 2027 | spreads | 78.50 | 56.50 | 69.20 | 185.00 | 186.00 | 29.00 |
| 2027 | totals | 78.80 | 56.50 | 69.20 | 82.80 | 82.80 | 29.00 |

### B3. DraftKings and Pinnacle first post, quantiles of hours before tip (any market)

| season | bookmaker | 0.1 | 0.25 | 0.5 | 0.75 | 0.9 |
|---|---|---|---|---|---|---|
| 2022 | draftkings | 23.50 | 32.40 | 45.80 | 78.90 | 100.00 |
| 2022 | pinnacle | 20.40 | 23.90 | 35.30 | 66.80 | 92.70 |
| 2023 | draftkings | 28.80 | 32.10 | 45.00 | 70.40 | 94.00 |
| 2023 | pinnacle | 23.60 | 25.60 | 28.30 | 43.60 | 55.90 |
| 2024 | draftkings | 30.90 | 34.90 | 69.30 | 81.30 | 101.90 |
| 2024 | pinnacle | 26.50 | 29.40 | 43.40 | 60.90 | 77.30 |
| 2025 | draftkings | 32.50 | 35.50 | 72.80 | 95.50 | 105.40 |
| 2025 | pinnacle | 24.80 | 26.20 | 27.90 | 29.70 | 44.90 |
| 2026 | draftkings | 31.70 | 44.00 | 68.20 | 86.10 | 116.80 |
| 2026 | pinnacle | 24.20 | 27.70 | 29.90 | 33.00 | 52.40 |
| 2027 | draftkings | 45.10 | 57.20 | 69.20 | 93.00 | 167.10 |
| 2027 | pinnacle | 26.60 | 27.70 | 29.00 | 30.20 | 51.50 |

### C. Each book's last stored change before tip: median minutes before tip

| season | draftkings | fanduel | betmgm | betrivers | fanatics | pinnacle | bovada | marathonbet | unibet | paddypower |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 30.00 |  |  |  |  | 10.00 | 100.00 | 30.00 | 90.00 | 401.00 |
| 2023 | 50.00 |  |  |  |  | 15.00 | 29.00 | 38.00 | 188.00 | 6.00 |
| 2024 | 10.00 |  |  |  |  | 15.00 | 40.00 | 45.00 | 135.00 | 5.00 |
| 2025 | 59.00 |  |  |  |  | 10.00 | 16.00 | 10.00 | 130.00 | 180.00 |
| 2026 | 66.00 | 74.00 | 65.00 | 25.00 | 60.00 | 10.00 | 6.00 | 21.00 | 25.00 | 135.00 |
| 2027 | 35.00 | 60.00 | 88.00 | 20.00 | 10.00 | 10.00 | 60.00 | 29.00 | 25.00 | 100.00 |

### D. Coherence: rows dropped (price inside -100..+100, or implied sum outside 1.00-1.15)

| bookmaker | market | rows | dropped | price_inside_100 | dropped_% |
|---|---|---|---|---|---|
| betmgm | h2h | 2,699 | 0 | 0 | 0.00 |
| betmgm | spreads | 2,020 | 0 | 0 | 0.00 |
| betmgm | totals | 1,912 | 0 | 0 | 0.00 |
| betrivers | h2h | 5,912 | 0 | 0 | 0.00 |
| betrivers | spreads | 6,556 | 0 | 0 | 0.00 |
| betrivers | totals | 5,343 | 0 | 0 | 0.00 |
| bovada | h2h | 34,939 | 0 | 0 | 0.00 |
| bovada | spreads | 34,593 | 3 | 0 | 0.01 |
| bovada | totals | 30,869 | 4 | 0 | 0.01 |
| draftkings | h2h | 21,059 | 0 | 0 | 0.00 |
| draftkings | spreads | 21,953 | 0 | 0 | 0.00 |
| draftkings | totals | 23,423 | 0 | 0 | 0.00 |
| fanatics | h2h | 5,512 | 0 | 0 | 0.00 |
| fanatics | spreads | 5,802 | 0 | 0 | 0.00 |
| fanatics | totals | 3,283 | 0 | 0 | 0.00 |
| fanduel | h2h | 7,518 | 0 | 0 | 0.00 |
| fanduel | spreads | 7,479 | 0 | 0 | 0.00 |
| fanduel | totals | 3,450 | 0 | 0 | 0.00 |
| marathonbet | h2h | 35,313 | 17 | 0 | 0.05 |
| marathonbet | spreads | 1,190 | 0 | 0 | 0.00 |
| marathonbet | totals | 1,086 | 0 | 0 | 0.00 |
| paddypower | h2h | 10,439 | 0 | 0 | 0.00 |
| pinnacle | h2h | 32,796 | 0 | 0 | 0.00 |
| pinnacle | spreads | 29,816 | 0 | 0 | 0.00 |
| pinnacle | totals | 24,773 | 0 | 0 | 0.00 |
| unibet | h2h | 15,200 | 0 | 0 | 0.00 |
| unibet | spreads | 15,740 | 0 | 0 | 0.00 |
| unibet | totals | 6,522 | 0 | 0 | 0.00 |

Total rows 397197 dropped 24

Implied-sum quantiles of the kept rows, by book (the margin each book carries):

| bookmaker | h2h | spreads | totals |
|---|---|---|---|
| betmgm | 1.05 | 1.05 | 1.05 |
| betrivers | 1.05 | 1.05 | 1.05 |
| bovada | 1.04 | 1.05 | 1.05 |
| draftkings | 1.04 | 1.05 | 1.05 |
| fanatics | 1.07 | 1.07 | 1.07 |
| fanduel | 1.05 | 1.05 | 1.05 |
| marathonbet | 1.04 | 1.05 | 1.05 |
| paddypower | 1.08 |  |  |
| pinnacle | 1.04 | 1.04 | 1.04 |
| unibet | 1.05 | 1.05 | 1.05 |

### E. Home-number sign: last pre-tip moneyline favourite vs sign of spread_home (line != 0)

| bookmaker | pairs | agree | disagree_line_ge_1_5 |
|---|---|---|---|
| betmgm | 401 | 396 | 5 |
| betrivers | 479 | 476 | 0 |
| bovada | 1,769 | 1,739 | 3 |
| draftkings | 1,772 | 1,753 | 9 |
| fanatics | 479 | 474 | 2 |
| fanduel | 476 | 474 | 2 |
| marathonbet | 53 | 53 | 0 |
| pinnacle | 1,642 | 1,615 | 3 |
| unibet | 1,786 | 1,763 | 0 |

home favourite by moneyline AND negative spread_home: 6298 | home underdog AND positive spread_home: 2445

Largest disagreements:

| game_id | bookmaker | pa | pb | line |
|---|---|---|---|---|
| EUROLEAGUE_E2021_190 | bovada | -110.00 | -108.00 | 9.00 |
| EUROLEAGUE_E2022_250 | bovada | -105.00 | -115.00 | -3.50 |
| EUROLEAGUE_E2021_16 | draftkings | -110.00 | -110.00 | -1.50 |
| EUROLEAGUE_E2023_82 | draftkings | -110.00 | -110.00 | -1.50 |
| EUROLEAGUE_E2023_52 | draftkings | -110.00 | -110.00 | -1.50 |
| EUROLEAGUE_E2023_70 | draftkings | -110.00 | -110.00 | -1.50 |
| EUROLEAGUE_E2023_46 | draftkings | -110.00 | -110.00 | -1.50 |
| EUROLEAGUE_E2022_96 | pinnacle | 100.00 | -113.00 | -1.50 |

Pinnacle close: home win rate when spread_home < 0: 0.693 n 1189 | when spread_home > 0: 0.4592 n 453
Pinnacle close: corr(spread_home, home margin): -0.3626

### F. snapshot_at against the ledger's snapshot times

ledger snapshots: 125333 range 2021-09-27 20:05:00+00:00 to 2026-11-13 05:45:36+00:00
seconds from a quote's snapshot_at to the next ledger snapshot (>= it): quantiles {0.01: 3.0, 0.05: 6.0, 0.25: 22.0, 0.5: 46.0, 0.75: 104.0, 0.95: 400.0, 0.99: 536.0}
share with snapshot_at exactly equal to a ledger snapshot time: 0.0004
share with the next ledger snapshot within 300 s: 0.8871 | within 900 s: 1.0
ledger gap seconds quantiles: {0.05: 300.0, 0.25: 600.0, 0.5: 899.0, 0.75: 900.0, 0.95: 900.0}

DraftKings rows in 2021-22: 13566 games 292 first 2021-09-27 19:57:08+00:00 last 2022-05-21 16:59:41+00:00


tip hour UTC counts: {14: 3, 15: 8, 16: 60, 17: 414, 18: 578, 19: 942, 20: 120}
tips before 15:05 UTC: 9 of 2125
home_code                             venue_name  neutral_site   n                            seasons  att_mean  att0
      ASV                             ASTROBALLE         False  72 2021,2022,2023,2024,2025,2026,2027    4888.0    16
      ASV                             LDLC ARENA         False  38                2024,2025,2026,2027    8740.0     0
      BAR                        PALAU BLAUGRANA         False 123 2021,2022,2023,2024,2025,2026,2027    5894.0    22
      BAR                          LANXESS ARENA          True   2                               2021       NaN     2
      BAR                            STARK ARENA          True   2                               2022   12650.0     0
      BAR                         ZALGIRIO ARENA          True   1                               2023   11411.0     0
      BAS                            BUESA ARENA         False 110 2021,2022,2023,2024,2025,2026,2027    8578.0    17
      BER                    MERCEDES-BENZ ARENA         False  66                2021,2022,2023,2024    7064.0    16
      BER                             UBER ARENA         False  18                          2024,2025    9310.0     0
      BER                    MAX SCHMELING HALLE         False   1                               2022    4500.0     0
      BES TURKCELL BASKETBALL DEVELOPMENT CENTER         False   5                               2027    6318.0     0
      CSK                        MEGASPORT ARENA         False  30                          2021,2022    3215.0     0
      CSK                          LANXESS ARENA          True   1                               2021       NaN     1
      CSK                               USH CSKA         False   1                               2021    2479.0     0
      DUB                        COCA-COLA ARENA         False  18                          2026,2027    5871.0     1
      DUB                            ZETRA ARENA         False   5                               2026    5559.0     1
      DUB         ARENA HUSEJIN SMAJLOVIC ZENICA         False   1                               2026    5996.0     0
      DYR                            SIBUR ARENA         False  24                          2021,2022    2456.0     2
      DYR                YUBILEYNY SPORTS PALACE         False   6                          2021,2022    2546.0     0
      HTA                       ARENA 8888 SOFIA         False  16                          2026,2027    4048.0     2
      HTA                        ARENA BOTEVGRAD         False   5                          2026,2027    1868.0     0
      HTA                 MENORA MIVTACHIM ARENA         False   5                               2026    7350.0     0
      HTA                   PAIS ARENA JERUSALEM         False   1                               2026    6230.0     0
      IST               SINAN ERDEM SPORTS HALL.         False  39                          2021,2022   10988.0    20
      IST                SINAN ERDEM SPORTS HALL         False  34                          2023,2024   12929.0     0
      IST          BASKETBALL DEVELOPMENT CENTER         False  20                          2025,2026    9314.0     0
      IST TURKCELL BASKETBALL DEVELOPMENT CENTER         False  19                          2026,2027    6501.0     0
      IST                                 MORACA         False   2                               2026    2449.0     0
      IST                    ANTALYA SPORTS HALL         False   1                               2026   10000.0     0
      IST                             ARENA RIGA         False   1                               2024    7813.0     0
      IST                           XIAOMI ARENA         False   1                               2025    4412.0     0
      KHI                        ARENA MYTISHCHI         False  17                               2021     785.0     7
      MAD                          WIZINK CENTER         False  86           2021,2022,2023,2024,2025    7733.0    19
      MAD                         MOVISTAR ARENA         False  38                     2025,2026,2027    9250.0     2
      MAD                             UBER ARENA          True   2                               2024   13578.0     0
      MAD                            STARK ARENA          True   1                               2022   15482.0     0
      MCO                   SALLE GASTON MEDECIN         False 100           2022,2023,2024,2025,2026    4119.0     1
      MCO                           ETIHAD ARENA          True   1                               2025       NaN     1
      MCO                         ZALGIRIO ARENA          True   1                               2023    9333.0     0
      MIL                       MEDIOLANUM FORUM         False  54                     2021,2022,2023    6654.0    18
      MIL                           UNIPOL FORUM         False  32                     2025,2026,2027    8267.0     0
      MIL                          ALLIANZ CLOUD         False  10                               2026    4366.0     0
      MIL                      MEDIOLANUM FORUM          False   9                               2024    9333.0     0
      MIL                                  FORUM         False   8                               2024   10859.0     0
      MIL                          LANXESS ARENA          True   1                               2021       NaN     1
      MUN                              AUDI DOME         False  52                     2021,2022,2023    4709.0    23
      MUN                             SAP GARDEN         False  41                     2025,2026,2027   10846.0     0
      MUN                               BMW PARK         False  17                               2024    6218.0     0
      OLY           PEACE AND FRIENDSHIP STADIUM         False 113      2021,2022,2023,2024,2025,2026   10699.0    18
      OLY                            SUNEL ARENA         False   5                               2027    6132.0     0
      OLY                           ETIHAD ARENA          True   2                               2025   10218.0     1
      OLY                  TELEKOM CENTER ATHENS          True   2                               2026       NaN     2
      OLY                         ZALGIRIO ARENA          True   2                               2023   11370.0     0
      OLY                            STARK ARENA          True   1                               2022   15472.0     0
      OLY                             UBER ARENA          True   1                               2024   13578.0     0
      PAM            PABELLON FUENTE DE SAN LUIS         False  30                          2023,2024    6308.0     0
      PAM                             ROIG ARENA         False  28                          2026,2027   12533.0     1
      PAM                             LA FONTETA         False  21                          2021,2023    3333.0    14
      PAM                  TELEKOM CENTER ATHENS          True   1                               2026       NaN     1
      PAN                            OAKA Altion         False  79           2021,2022,2023,2024,2025   11147.0     5
      PAN                  TELEKOM CENTER ATHENS         False  29                          2026,2027   18130.0     0
      PAN                                   OAKA         False  12                               2021       NaN    12
      PAN                             UBER ARENA          True   1                               2024   13578.0     0
      PAR                         BELGRADE ARENA         False  39                2024,2025,2026,2027   17749.0     0
      PAR                            STARK ARENA         False  35                          2023,2024   18864.0     0
      PAR                ALEKSANDAR NIKOLIC HALL         False   2                          2025,2026    5998.0     0
      PAR                               BMW PARK         False   1                               2026    1093.0     0
      PRS                           ADIDAS ARENA         False  38                     2025,2026,2027    6409.0     0
      PRS                            ACCOR ARENA         False   5                     2025,2026,2027   12243.0     0
      RED                ALEKSANDAR NIKOLIC HALL         False  52           2021,2022,2023,2025,2026    6407.0    16
      RED                         BELGRADE ARENA         False  39                     2025,2026,2027   18384.0     0
      RED                            STARK ARENA         False  18                          2022,2024   17289.0     0
      TEL                 MENORA MIVTACHIM ARENA         False  59           2021,2022,2023,2024,2026    9016.0    14
      TEL                ALEKSANDAR NIKOLIC HALL         False  51                2024,2025,2026,2027     289.0    16
      TEL                         BELGRADE ARENA         False   2                               2024     400.0     1
      TEL                   PAIS ARENA JERUSALEM         False   1                               2026    9054.0     0
      TEL       SPYROS KYPRIANOU ATHLETIC CENTER         False   1                               2027    1212.0     0
      ULK            ULKER SPORTS AND EVENT HALL         False 112 2021,2022,2023,2024,2025,2026,2027    8653.0     6
      ULK                             SAP GARDEN         False   2                               2026    2790.0     0
      ULK                           ETIHAD ARENA          True   1                               2025   10218.0     0
      ULK                       KALNAPILIO ARENA         False   1                               2024    2938.0     0
      ULK               SINAN ERDEM SPORTS HALL.         False   1                               2022    2577.0     0
      ULK                         ZALGIRIO ARENA         False   1                               2025    1416.0     0
      UNK                      BASKET HALL KAZAN         False  13                               2022    2624.0     0
      VIR                 VIRTUS SEGAFREDO ARENA         False  37                     2023,2024,2025    7872.0     0
      VIR                              PALADOZZA         False  19                2023,2024,2026,2027    4964.0     0
      VIR                           VIRTUS ARENA         False  13                               2026    7515.0     0
      VIR                           UNIPOL ARENA         False   6                               2025    7583.0     0
      ZAL                         ZALGIRIO ARENA         False 111 2021,2022,2023,2024,2025,2026,2027   13283.0    14


## r2_baselines.py

### Blind baselines, pooled 2021-22 to 2026-27 (return = units / units risked; 90% interval resampling dates)

| market | read | book | side | season | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2h | first | draftkings | home | all | 1,772 | 1,115 | 657 | 0 | 27.94 | 0.82 | -2.07 | 3.36 | 0.3072 |
| h2h | first | draftkings | away | all | 1,772 | 657 | 1,115 | 0 | -308.58 | -14.11 | -18.10 | -9.71 | 1.0000 |
| h2h | first | draftkings | fav | all | 1,772 | 1,174 | 598 | 0 | -128.34 | -3.37 | -5.75 | -0.88 | 0.9889 |
| h2h | first | draftkings | dog | all | 1,772 | 598 | 1,174 | 0 | -152.30 | -8.57 | -13.69 | -3.45 | 0.9977 |
| h2h | first | draftkings | fav, -200 floor | all | 866 | 503 | 363 | 0 | -39.43 | -3.02 | -7.35 | 1.63 | 0.8620 |
| h2h | first | draftkings | every quote both ways | all | 3,544 | 1,772 | 1,772 | 0 | -280.64 | -5.03 | -5.34 | -4.69 | 1.0000 |
| h2h | first | best decidable | home | all | 1,772 | 1,115 | 657 | 0 | 47.37 | 1.40 | -1.50 | 3.99 | 0.1970 |
| h2h | first | best decidable | away | all | 1,772 | 657 | 1,115 | 0 | -291.19 | -13.35 | -17.37 | -8.82 | 1.0000 |
| h2h | first | best decidable | fav | all | 1,759 | 1,158 | 601 | 0 | -132.86 | -3.53 | -6.02 | -0.80 | 0.9878 |
| h2h | first | best decidable | dog | all | 1,759 | 601 | 1,158 | 0 | -109.71 | -6.23 | -11.74 | -1.06 | 0.9729 |
| h2h | first | best decidable | fav, -200 floor | all | 868 | 497 | 371 | 0 | -53.51 | -4.08 | -8.54 | 0.59 | 0.9276 |
| h2h | first | best decidable | every quote both ways | all | 3,544 | 1,772 | 1,772 | 0 | -243.82 | -4.39 | -4.70 | -4.06 | 1.0000 |
| h2h | close | draftkings | home | all | 1,772 | 1,115 | 657 | 0 | 30.34 | 0.89 | -1.92 | 3.42 | 0.2921 |
| h2h | close | draftkings | away | all | 1,772 | 657 | 1,115 | 0 | -318.51 | -14.39 | -18.25 | -10.05 | 1.0000 |
| h2h | close | draftkings | fav | all | 1,772 | 1,168 | 604 | 0 | -163.80 | -4.24 | -6.60 | -1.79 | 0.9979 |
| h2h | close | draftkings | dog | all | 1,772 | 604 | 1,168 | 0 | -124.38 | -6.99 | -12.26 | -1.83 | 0.9873 |
| h2h | close | draftkings | fav, -200 floor | all | 805 | 457 | 348 | 0 | -54.01 | -4.52 | -8.96 | 0.09 | 0.9534 |
| h2h | close | draftkings | every quote both ways | all | 3,544 | 1,772 | 1,772 | 0 | -288.18 | -5.11 | -5.39 | -4.81 | 1.0000 |
| h2h | close | best decidable | home | all | 1,772 | 1,115 | 657 | 0 | 45.49 | 1.34 | -1.48 | 3.89 | 0.2065 |
| h2h | close | best decidable | away | all | 1,772 | 657 | 1,115 | 0 | -304.00 | -13.78 | -17.68 | -9.36 | 1.0000 |
| h2h | close | best decidable | fav | all | 1,759 | 1,159 | 600 | 0 | -154.59 | -4.05 | -6.47 | -1.51 | 0.9961 |
| h2h | close | best decidable | dog | all | 1,759 | 600 | 1,159 | 0 | -102.61 | -5.82 | -11.12 | -1.00 | 0.9646 |
| h2h | close | best decidable | fav, -200 floor | all | 805 | 456 | 349 | 0 | -54.96 | -4.60 | -9.32 | 0.11 | 0.9487 |
| h2h | close | best decidable | every quote both ways | all | 3,544 | 1,772 | 1,772 | 0 | -258.50 | -4.61 | -4.91 | -4.28 | 1.0000 |
| spreads | first | draftkings | home | all | 1,772 | 923 | 832 | 17 | 8.30 | 0.43 | -3.03 | 3.91 | 0.4200 |
| spreads | first | draftkings | away | all | 1,772 | 832 | 923 | 17 | -184.88 | -9.57 | -13.05 | -6.11 | 1.0000 |
| spreads | first | draftkings | fav | all | 1,771 | 851 | 903 | 17 | -140.39 | -7.29 | -10.59 | -3.91 | 0.9998 |
| spreads | first | draftkings | dog | all | 1,771 | 903 | 851 | 17 | -36.14 | -1.87 | -5.22 | 1.46 | 0.8145 |
| spreads | first | draftkings | every quote both ways | all | 3,544 | 1,755 | 1,755 | 34 | -176.58 | -4.57 | -4.63 | -4.52 | 1.0000 |
| spreads | first | best decidable | home | all | 1,772 | 923 | 832 | 17 | 10.96 | 0.57 | -2.84 | 4.11 | 0.3950 |
| spreads | first | best decidable | away | all | 1,772 | 832 | 923 | 17 | -179.53 | -9.33 | -12.85 | -5.92 | 1.0000 |
| spreads | first | best decidable | fav | all | 1,771 | 851 | 903 | 17 | -135.99 | -7.09 | -10.39 | -3.52 | 0.9996 |
| spreads | first | best decidable | dog | all | 1,771 | 903 | 851 | 17 | -32.53 | -1.69 | -5.22 | 1.59 | 0.7886 |
| spreads | first | best decidable | every quote both ways | all | 3,544 | 1,755 | 1,755 | 34 | -168.57 | -4.38 | -4.44 | -4.32 | 1.0000 |
| spreads | close | draftkings | home | all | 1,772 | 919 | 833 | 20 | 3.80 | 0.20 | -3.24 | 3.81 | 0.4636 |
| spreads | close | draftkings | away | all | 1,772 | 833 | 919 | 20 | -177.43 | -9.20 | -12.76 | -5.77 | 1.0000 |
| spreads | close | draftkings | fav | all | 1,772 | 850 | 902 | 20 | -139.17 | -7.24 | -10.69 | -3.63 | 0.9996 |
| spreads | close | draftkings | dog | all | 1,772 | 902 | 850 | 20 | -34.46 | -1.78 | -5.36 | 1.69 | 0.7948 |
| spreads | close | draftkings | every quote both ways | all | 3,544 | 1,752 | 1,752 | 40 | -173.63 | -4.50 | -4.57 | -4.44 | 1.0000 |
| spreads | close | best decidable | home | all | 1,772 | 918 | 834 | 20 | 7.00 | 0.37 | -3.28 | 3.96 | 0.4326 |
| spreads | close | best decidable | away | all | 1,772 | 834 | 918 | 20 | -168.86 | -8.81 | -12.38 | -5.23 | 1.0000 |
| spreads | close | best decidable | fav | all | 1,772 | 844 | 908 | 20 | -144.93 | -7.59 | -11.27 | -3.95 | 0.9997 |
| spreads | close | best decidable | dog | all | 1,772 | 908 | 844 | 20 | -16.93 | -0.88 | -4.50 | 2.75 | 0.6549 |
| spreads | close | best decidable | every quote both ways | all | 3,544 | 1,752 | 1,752 | 40 | -161.86 | -4.22 | -4.31 | -4.15 | 1.0000 |
| totals | first | draftkings | over | all | 1,772 | 912 | 854 | 6 | -26.76 | -1.38 | -5.48 | 2.53 | 0.7153 |
| totals | first | draftkings | under | all | 1,772 | 854 | 912 | 6 | -149.44 | -7.69 | -11.68 | -3.64 | 0.9992 |
| totals | first | draftkings | every quote both ways | all | 3,544 | 1,766 | 1,766 | 12 | -176.20 | -4.54 | -4.59 | -4.48 | 1.0000 |
| totals | first | best decidable | over | all | 1,772 | 908 | 858 | 6 | -32.80 | -1.69 | -5.77 | 2.36 | 0.7572 |
| totals | first | best decidable | under | all | 1,772 | 858 | 908 | 6 | -138.47 | -7.14 | -11.24 | -3.03 | 0.9983 |
| totals | first | best decidable | every quote both ways | all | 3,544 | 1,766 | 1,766 | 12 | -171.27 | -4.42 | -4.48 | -4.36 | 1.0000 |
| totals | close | draftkings | over | all | 1,772 | 883 | 873 | 16 | -76.57 | -3.97 | -8.03 | -0.22 | 0.9540 |
| totals | close | draftkings | under | all | 1,772 | 873 | 883 | 16 | -98.70 | -5.11 | -8.88 | -1.04 | 0.9852 |
| totals | close | draftkings | every quote both ways | all | 3,544 | 1,756 | 1,756 | 32 | -175.27 | -4.54 | -4.58 | -4.48 | 1.0000 |
| totals | close | best decidable | over | all | 1,772 | 883 | 873 | 16 | -72.25 | -3.76 | -7.72 | -0.04 | 0.9446 |
| totals | close | best decidable | under | all | 1,772 | 873 | 883 | 16 | -93.95 | -4.88 | -8.61 | -0.90 | 0.9809 |
| totals | close | best decidable | every quote both ways | all | 3,544 | 1,756 | 1,756 | 32 | -166.20 | -4.32 | -4.38 | -4.26 | 1.0000 |

### Blind baselines by season

| market | read | book | side | season | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2h | first | draftkings | home | 2022 | 292 | 190 | 102 | 0 | 33.72 | 6.01 | -1.38 | 13.29 | 0.0849 |
| h2h | first | draftkings | home | 2023 | 310 | 193 | 117 | 0 | -6.46 | -1.09 | -7.39 | 4.89 | 0.6136 |
| h2h | first | draftkings | home | 2024 | 331 | 214 | 117 | 0 | 19.95 | 3.14 | -2.65 | 8.37 | 0.1761 |
| h2h | first | draftkings | home | 2025 | 330 | 204 | 126 | 0 | -5.28 | -0.83 | -6.74 | 5.24 | 0.5887 |
| h2h | first | draftkings | home | 2026 | 402 | 256 | 146 | 0 | 8.83 | 1.14 | -4.63 | 7.22 | 0.3778 |
| h2h | first | draftkings | home | 2027 | 107 | 58 | 49 | 0 | -22.82 | -11.28 | -22.72 | 0.83 | 0.9405 |
| h2h | first | draftkings | away | 2022 | 292 | 102 | 190 | 0 | -86.68 | -22.65 | -32.69 | -11.59 | 0.9998 |
| h2h | first | draftkings | away | 2023 | 310 | 117 | 193 | 0 | -26.41 | -6.97 | -17.40 | 4.04 | 0.8580 |
| h2h | first | draftkings | away | 2024 | 331 | 117 | 214 | 0 | -69.57 | -17.35 | -26.18 | -8.32 | 0.9993 |
| h2h | first | draftkings | away | 2025 | 330 | 126 | 204 | 0 | -55.82 | -13.59 | -23.39 | -4.43 | 0.9917 |
| h2h | first | draftkings | away | 2026 | 402 | 146 | 256 | 0 | -74.18 | -15.35 | -24.81 | -6.27 | 0.9963 |
| h2h | first | draftkings | away | 2027 | 107 | 49 | 58 | 0 | 4.08 | 3.13 | -13.85 | 20.30 | 0.3831 |
| h2h | first | draftkings | fav | 2022 | 292 | 196 | 96 | 0 | -26.41 | -4.06 | -11.08 | 2.59 | 0.8321 |
| h2h | first | draftkings | fav | 2023 | 310 | 207 | 103 | 0 | -18.67 | -2.84 | -8.65 | 2.82 | 0.7938 |
| h2h | first | draftkings | fav | 2024 | 331 | 236 | 95 | 0 | 29.19 | 4.14 | -1.04 | 9.21 | 0.0903 |
| h2h | first | draftkings | fav | 2025 | 330 | 209 | 121 | 0 | -51.07 | -7.15 | -13.37 | -1.58 | 0.9800 |
| h2h | first | draftkings | fav | 2026 | 402 | 256 | 146 | 0 | -49.40 | -5.79 | -11.13 | -0.41 | 0.9605 |
| h2h | first | draftkings | fav | 2027 | 107 | 70 | 37 | 0 | -11.99 | -5.32 | -15.27 | 5.20 | 0.8080 |
| h2h | first | draftkings | dog | 2022 | 292 | 96 | 196 | 0 | -26.55 | -9.06 | -23.22 | 6.14 | 0.8424 |
| h2h | first | draftkings | dog | 2023 | 310 | 103 | 207 | 0 | -14.20 | -4.57 | -17.59 | 7.61 | 0.7243 |
| h2h | first | draftkings | dog | 2024 | 331 | 95 | 236 | 0 | -78.81 | -23.75 | -34.40 | -13.51 | 0.9999 |
| h2h | first | draftkings | dog | 2025 | 330 | 121 | 209 | 0 | -10.03 | -3.04 | -14.32 | 9.25 | 0.6648 |
| h2h | first | draftkings | dog | 2026 | 402 | 146 | 256 | 0 | -15.96 | -3.96 | -14.66 | 6.38 | 0.7283 |
| h2h | first | draftkings | dog | 2027 | 107 | 37 | 70 | 0 | -6.75 | -6.29 | -26.21 | 11.96 | 0.7095 |
| h2h | first | best decidable | home | 2022 | 292 | 190 | 102 | 0 | 33.72 | 6.01 | -1.38 | 13.29 | 0.0849 |
| h2h | first | best decidable | home | 2023 | 310 | 193 | 117 | 0 | -6.46 | -1.09 | -7.39 | 4.89 | 0.6136 |
| h2h | first | best decidable | home | 2024 | 331 | 214 | 117 | 0 | 19.95 | 3.14 | -2.65 | 8.37 | 0.1761 |
| h2h | first | best decidable | home | 2025 | 330 | 204 | 126 | 0 | -5.28 | -0.83 | -6.74 | 5.24 | 0.5887 |
| h2h | first | best decidable | home | 2026 | 402 | 256 | 146 | 0 | 24.56 | 3.24 | -2.75 | 9.47 | 0.1942 |
| h2h | first | best decidable | home | 2027 | 107 | 58 | 49 | 0 | -19.12 | -9.63 | -21.15 | 2.53 | 0.9062 |
| h2h | first | best decidable | away | 2022 | 292 | 102 | 190 | 0 | -86.68 | -22.65 | -32.69 | -11.59 | 0.9998 |
| h2h | first | best decidable | away | 2023 | 310 | 117 | 193 | 0 | -26.41 | -6.97 | -17.40 | 4.04 | 0.8580 |
| h2h | first | best decidable | away | 2024 | 331 | 117 | 214 | 0 | -69.57 | -17.35 | -26.18 | -8.32 | 0.9993 |
| h2h | first | best decidable | away | 2025 | 330 | 126 | 204 | 0 | -55.82 | -13.59 | -23.39 | -4.43 | 0.9917 |
| h2h | first | best decidable | away | 2026 | 402 | 146 | 256 | 0 | -59.92 | -12.52 | -22.53 | -3.12 | 0.9806 |
| h2h | first | best decidable | away | 2027 | 107 | 49 | 58 | 0 | 7.21 | 5.58 | -11.98 | 23.13 | 0.3041 |
| h2h | first | best decidable | fav | 2022 | 286 | 191 | 95 | 0 | -30.31 | -4.70 | -12.04 | 1.93 | 0.8731 |
| h2h | first | best decidable | fav | 2023 | 306 | 204 | 102 | 0 | -20.57 | -3.15 | -9.15 | 2.82 | 0.8125 |
| h2h | first | best decidable | fav | 2024 | 330 | 235 | 95 | 0 | 28.19 | 4.01 | -1.17 | 9.07 | 0.0999 |
| h2h | first | best decidable | fav | 2025 | 329 | 208 | 121 | 0 | -52.07 | -7.30 | -13.41 | -1.80 | 0.9819 |
| h2h | first | best decidable | fav | 2026 | 401 | 250 | 151 | 0 | -49.49 | -5.94 | -11.39 | -0.44 | 0.9610 |
| h2h | first | best decidable | fav | 2027 | 107 | 70 | 37 | 0 | -8.61 | -3.90 | -13.88 | 6.49 | 0.7404 |
| h2h | first | best decidable | dog | 2022 | 286 | 95 | 191 | 0 | -22.05 | -7.70 | -22.24 | 8.29 | 0.8014 |
| h2h | first | best decidable | dog | 2023 | 306 | 102 | 204 | 0 | -11.90 | -3.89 | -16.91 | 9.22 | 0.6897 |
| h2h | first | best decidable | dog | 2024 | 330 | 95 | 235 | 0 | -77.71 | -23.49 | -34.30 | -13.13 | 0.9999 |
| h2h | first | best decidable | dog | 2025 | 329 | 121 | 208 | 0 | -8.93 | -2.71 | -14.07 | 9.48 | 0.6476 |
| h2h | first | best decidable | dog | 2026 | 401 | 151 | 250 | 0 | 14.18 | 3.53 | -8.08 | 14.69 | 0.3064 |
| h2h | first | best decidable | dog | 2027 | 107 | 37 | 70 | 0 | -3.30 | -3.08 | -23.29 | 16.15 | 0.6030 |
| h2h | close | draftkings | home | 2022 | 292 | 190 | 102 | 0 | 37.51 | 6.69 | -0.60 | 13.95 | 0.0644 |
| h2h | close | draftkings | home | 2023 | 310 | 193 | 117 | 0 | -7.69 | -1.28 | -7.47 | 4.52 | 0.6350 |
| h2h | close | draftkings | home | 2024 | 331 | 214 | 117 | 0 | 16.40 | 2.53 | -3.29 | 7.59 | 0.2229 |
| h2h | close | draftkings | home | 2025 | 330 | 204 | 126 | 0 | -6.59 | -1.04 | -7.06 | 5.19 | 0.6121 |
| h2h | close | draftkings | home | 2026 | 402 | 256 | 146 | 0 | 9.16 | 1.18 | -4.81 | 7.28 | 0.3753 |
| h2h | close | draftkings | home | 2027 | 107 | 58 | 49 | 0 | -18.45 | -9.08 | -20.54 | 2.57 | 0.8972 |
| h2h | close | draftkings | away | 2022 | 292 | 102 | 190 | 0 | -90.57 | -23.15 | -33.05 | -12.57 | 0.9999 |
| h2h | close | draftkings | away | 2023 | 310 | 117 | 193 | 0 | -32.26 | -8.49 | -18.40 | 2.07 | 0.9134 |
| h2h | close | draftkings | away | 2024 | 331 | 117 | 214 | 0 | -67.67 | -16.66 | -25.36 | -7.55 | 0.9988 |
| h2h | close | draftkings | away | 2025 | 330 | 126 | 204 | 0 | -55.28 | -13.31 | -22.65 | -4.51 | 0.9916 |
| h2h | close | draftkings | away | 2026 | 402 | 146 | 256 | 0 | -73.03 | -14.87 | -24.51 | -5.53 | 0.9950 |
| h2h | close | draftkings | away | 2027 | 107 | 49 | 58 | 0 | 0.31 | 0.24 | -17.53 | 18.56 | 0.4914 |
| h2h | close | draftkings | fav | 2022 | 292 | 188 | 104 | 0 | -52.76 | -8.01 | -15.71 | -0.99 | 0.9609 |
| h2h | close | draftkings | fav | 2023 | 310 | 210 | 100 | 0 | -13.01 | -1.95 | -7.95 | 4.08 | 0.7059 |
| h2h | close | draftkings | fav | 2024 | 331 | 240 | 91 | 0 | 31.90 | 4.43 | -0.40 | 9.05 | 0.0658 |
| h2h | close | draftkings | fav | 2025 | 330 | 212 | 118 | 0 | -50.06 | -6.94 | -12.84 | -1.57 | 0.9787 |
| h2h | close | draftkings | fav | 2026 | 402 | 253 | 149 | 0 | -58.79 | -6.78 | -11.61 | -1.95 | 0.9894 |
| h2h | close | draftkings | fav | 2027 | 107 | 65 | 42 | 0 | -21.08 | -9.34 | -18.69 | 0.98 | 0.9412 |
| h2h | close | draftkings | dog | 2022 | 292 | 104 | 188 | 0 | -0.30 | -0.10 | -15.31 | 17.15 | 0.5040 |
| h2h | close | draftkings | dog | 2023 | 310 | 100 | 210 | 0 | -26.95 | -8.66 | -22.05 | 4.40 | 0.8624 |
| h2h | close | draftkings | dog | 2024 | 331 | 91 | 240 | 0 | -83.18 | -25.02 | -35.09 | -14.26 | 1.0000 |
| h2h | close | draftkings | dog | 2025 | 330 | 118 | 212 | 0 | -11.81 | -3.57 | -14.59 | 8.64 | 0.6923 |
| h2h | close | draftkings | dog | 2026 | 402 | 149 | 253 | 0 | -5.08 | -1.26 | -11.18 | 8.41 | 0.5834 |
| h2h | close | draftkings | dog | 2027 | 107 | 42 | 65 | 0 | 2.94 | 2.74 | -15.94 | 21.40 | 0.4038 |
| h2h | close | best decidable | home | 2022 | 292 | 190 | 102 | 0 | 37.51 | 6.69 | -0.60 | 13.95 | 0.0644 |
| h2h | close | best decidable | home | 2023 | 310 | 193 | 117 | 0 | -7.69 | -1.28 | -7.47 | 4.52 | 0.6350 |
| h2h | close | best decidable | home | 2024 | 331 | 214 | 117 | 0 | 16.40 | 2.53 | -3.29 | 7.59 | 0.2229 |
| h2h | close | best decidable | home | 2025 | 330 | 204 | 126 | 0 | -6.59 | -1.04 | -7.06 | 5.19 | 0.6121 |
| h2h | close | best decidable | home | 2026 | 402 | 256 | 146 | 0 | 20.69 | 2.71 | -3.44 | 8.91 | 0.2352 |
| h2h | close | best decidable | home | 2027 | 107 | 58 | 49 | 0 | -14.82 | -7.47 | -19.35 | 5.44 | 0.8374 |
| h2h | close | best decidable | away | 2022 | 292 | 102 | 190 | 0 | -90.57 | -23.15 | -33.05 | -12.57 | 0.9999 |
| h2h | close | best decidable | away | 2023 | 310 | 117 | 193 | 0 | -32.26 | -8.49 | -18.40 | 2.07 | 0.9134 |
| h2h | close | best decidable | away | 2024 | 331 | 117 | 214 | 0 | -67.67 | -16.66 | -25.36 | -7.55 | 0.9988 |
| h2h | close | best decidable | away | 2025 | 330 | 126 | 204 | 0 | -55.28 | -13.31 | -22.65 | -4.51 | 0.9916 |
| h2h | close | best decidable | away | 2026 | 402 | 146 | 256 | 0 | -61.09 | -12.59 | -22.59 | -2.90 | 0.9821 |
| h2h | close | best decidable | away | 2027 | 107 | 49 | 58 | 0 | 2.89 | 2.25 | -15.73 | 20.98 | 0.4198 |
| h2h | close | best decidable | fav | 2022 | 289 | 188 | 101 | 0 | -49.46 | -7.55 | -15.14 | -0.47 | 0.9527 |
| h2h | close | best decidable | fav | 2023 | 304 | 205 | 99 | 0 | -16.91 | -2.56 | -8.84 | 3.17 | 0.7563 |
| h2h | close | best decidable | fav | 2024 | 328 | 240 | 88 | 0 | 35.20 | 4.91 | 0.07 | 9.66 | 0.0481 |
| h2h | close | best decidable | fav | 2025 | 329 | 211 | 118 | 0 | -51.06 | -7.09 | -13.16 | -1.66 | 0.9796 |
| h2h | close | best decidable | fav | 2026 | 402 | 250 | 152 | 0 | -54.11 | -6.39 | -11.26 | -1.39 | 0.9806 |
| h2h | close | best decidable | fav | 2027 | 107 | 65 | 42 | 0 | -18.26 | -8.31 | -17.62 | 1.94 | 0.9181 |
| h2h | close | best decidable | dog | 2022 | 289 | 101 | 188 | 0 | -3.30 | -1.14 | -16.65 | 16.34 | 0.5446 |
| h2h | close | best decidable | dog | 2023 | 304 | 99 | 205 | 0 | -22.45 | -7.37 | -20.82 | 6.02 | 0.8153 |
| h2h | close | best decidable | dog | 2024 | 328 | 88 | 240 | 0 | -86.18 | -26.18 | -36.63 | -15.50 | 1.0000 |
| h2h | close | best decidable | dog | 2025 | 329 | 118 | 211 | 0 | -10.71 | -3.24 | -14.36 | 9.06 | 0.6738 |
| h2h | close | best decidable | dog | 2026 | 402 | 152 | 250 | 0 | 13.70 | 3.40 | -7.26 | 13.55 | 0.3007 |
| h2h | close | best decidable | dog | 2027 | 107 | 42 | 65 | 0 | 6.33 | 5.91 | -13.68 | 26.13 | 0.3111 |
| spreads | first | draftkings | home | 2022 | 292 | 148 | 138 | 6 | -3.40 | -1.08 | -11.16 | 8.52 | 0.5720 |
| spreads | first | draftkings | home | 2023 | 310 | 168 | 139 | 3 | 15.40 | 4.57 | -3.66 | 13.03 | 0.1810 |
| spreads | first | draftkings | home | 2024 | 331 | 174 | 150 | 7 | 8.68 | 2.44 | -6.01 | 10.30 | 0.3104 |
| spreads | first | draftkings | home | 2025 | 330 | 173 | 156 | 1 | 1.04 | 0.29 | -7.58 | 8.17 | 0.4764 |
| spreads | first | draftkings | home | 2026 | 402 | 210 | 192 | 0 | -0.68 | -0.15 | -6.83 | 6.44 | 0.5156 |
| spreads | first | draftkings | home | 2027 | 107 | 50 | 57 | 0 | -12.74 | -10.81 | -24.74 | 2.78 | 0.8941 |
| spreads | first | draftkings | away | 2022 | 292 | 138 | 148 | 6 | -25.10 | -7.96 | -17.63 | 2.08 | 0.9103 |
| spreads | first | draftkings | away | 2023 | 310 | 139 | 168 | 3 | -46.15 | -13.64 | -22.03 | -5.41 | 0.9967 |
| spreads | first | draftkings | away | 2024 | 331 | 150 | 174 | 7 | -41.82 | -11.73 | -19.62 | -3.18 | 0.9916 |
| spreads | first | draftkings | away | 2025 | 330 | 156 | 173 | 1 | -34.12 | -9.44 | -17.37 | -1.57 | 0.9741 |
| spreads | first | draftkings | away | 2026 | 402 | 192 | 210 | 0 | -39.72 | -8.96 | -15.51 | -2.33 | 0.9888 |
| spreads | first | draftkings | away | 2027 | 107 | 57 | 50 | 0 | 2.03 | 1.73 | -11.85 | 15.91 | 0.4218 |
| spreads | first | draftkings | fav | 2022 | 292 | 134 | 152 | 6 | -32.25 | -10.30 | -19.23 | -0.86 | 0.9646 |
| spreads | first | draftkings | fav | 2023 | 309 | 155 | 151 | 3 | -10.80 | -3.22 | -12.00 | 4.40 | 0.7397 |
| spreads | first | draftkings | fav | 2024 | 331 | 173 | 151 | 7 | 6.71 | 1.88 | -6.78 | 10.37 | 0.3577 |
| spreads | first | draftkings | fav | 2025 | 330 | 145 | 184 | 1 | -57.56 | -15.90 | -23.61 | -8.73 | 0.9998 |
| spreads | first | draftkings | fav | 2026 | 402 | 185 | 217 | 0 | -52.63 | -11.96 | -18.97 | -4.66 | 0.9968 |
| spreads | first | draftkings | fav | 2027 | 107 | 59 | 48 | 0 | 6.14 | 5.21 | -6.53 | 17.91 | 0.2425 |
| spreads | first | draftkings | dog | 2022 | 292 | 152 | 134 | 6 | 3.75 | 1.19 | -8.12 | 10.07 | 0.4172 |
| spreads | first | draftkings | dog | 2023 | 309 | 151 | 155 | 3 | -19.90 | -5.90 | -13.56 | 2.79 | 0.8807 |
| spreads | first | draftkings | dog | 2024 | 331 | 151 | 173 | 7 | -39.85 | -11.17 | -19.54 | -2.45 | 0.9847 |
| spreads | first | draftkings | dog | 2025 | 330 | 184 | 145 | 1 | 24.48 | 6.77 | -0.35 | 14.45 | 0.0633 |
| spreads | first | draftkings | dog | 2026 | 402 | 217 | 185 | 0 | 12.23 | 2.75 | -4.65 | 9.68 | 0.2648 |
| spreads | first | draftkings | dog | 2027 | 107 | 48 | 59 | 0 | -16.85 | -14.32 | -27.25 | -2.37 | 0.9700 |
| spreads | first | best decidable | home | 2022 | 292 | 148 | 138 | 6 | -3.40 | -1.08 | -11.16 | 8.52 | 0.5720 |
| spreads | first | best decidable | home | 2023 | 310 | 168 | 139 | 3 | 15.40 | 4.57 | -3.66 | 13.03 | 0.1810 |
| spreads | first | best decidable | home | 2024 | 331 | 174 | 150 | 7 | 8.68 | 2.44 | -6.01 | 10.30 | 0.3104 |
| spreads | first | best decidable | home | 2025 | 330 | 173 | 156 | 1 | 1.04 | 0.29 | -7.58 | 8.17 | 0.4764 |
| spreads | first | best decidable | home | 2026 | 402 | 210 | 192 | 0 | 1.38 | 0.32 | -6.29 | 6.69 | 0.4683 |
| spreads | first | best decidable | home | 2027 | 107 | 50 | 57 | 0 | -12.14 | -10.48 | -24.48 | 3.17 | 0.8841 |
| spreads | first | best decidable | away | 2022 | 292 | 138 | 148 | 6 | -25.10 | -7.96 | -17.63 | 2.08 | 0.9103 |
| spreads | first | best decidable | away | 2023 | 310 | 139 | 168 | 3 | -46.15 | -13.64 | -22.03 | -5.41 | 0.9967 |
| spreads | first | best decidable | away | 2024 | 331 | 150 | 174 | 7 | -41.82 | -11.73 | -19.62 | -3.18 | 0.9916 |
| spreads | first | best decidable | away | 2025 | 330 | 156 | 173 | 1 | -34.12 | -9.44 | -17.37 | -1.57 | 0.9741 |
| spreads | first | best decidable | away | 2026 | 402 | 192 | 210 | 0 | -35.34 | -8.09 | -14.53 | -1.52 | 0.9798 |
| spreads | first | best decidable | away | 2027 | 107 | 57 | 50 | 0 | 3.00 | 2.59 | -10.91 | 16.70 | 0.3835 |
| spreads | first | best decidable | fav | 2022 | 292 | 134 | 152 | 6 | -32.25 | -10.30 | -19.23 | -0.86 | 0.9646 |
| spreads | first | best decidable | fav | 2023 | 309 | 155 | 151 | 3 | -10.80 | -3.22 | -12.00 | 4.40 | 0.7397 |
| spreads | first | best decidable | fav | 2024 | 331 | 173 | 151 | 7 | 6.71 | 1.88 | -6.78 | 10.37 | 0.3577 |
| spreads | first | best decidable | fav | 2025 | 330 | 145 | 184 | 1 | -57.56 | -15.90 | -23.61 | -8.73 | 0.9998 |
| spreads | first | best decidable | fav | 2026 | 402 | 185 | 217 | 0 | -48.93 | -11.27 | -18.34 | -3.65 | 0.9920 |
| spreads | first | best decidable | fav | 2027 | 107 | 59 | 48 | 0 | 6.84 | 5.92 | -5.96 | 19.24 | 0.2225 |
| spreads | first | best decidable | dog | 2022 | 292 | 152 | 134 | 6 | 3.75 | 1.19 | -8.12 | 10.07 | 0.4172 |
| spreads | first | best decidable | dog | 2023 | 309 | 151 | 155 | 3 | -19.90 | -5.90 | -13.56 | 2.79 | 0.8807 |
| spreads | first | best decidable | dog | 2024 | 331 | 151 | 173 | 7 | -39.85 | -11.17 | -19.54 | -2.45 | 0.9847 |
| spreads | first | best decidable | dog | 2025 | 330 | 184 | 145 | 1 | 24.48 | 6.77 | -0.35 | 14.45 | 0.0633 |
| spreads | first | best decidable | dog | 2026 | 402 | 217 | 185 | 0 | 14.97 | 3.41 | -4.20 | 10.40 | 0.2314 |
| spreads | first | best decidable | dog | 2027 | 107 | 48 | 59 | 0 | -15.98 | -13.79 | -27.19 | -1.84 | 0.9626 |
| spreads | close | draftkings | home | 2022 | 292 | 149 | 140 | 3 | -4.85 | -1.53 | -11.03 | 8.37 | 0.6032 |
| spreads | close | draftkings | home | 2023 | 310 | 169 | 138 | 3 | 16.75 | 4.96 | -3.00 | 13.51 | 0.1632 |
| spreads | close | draftkings | home | 2024 | 331 | 172 | 154 | 5 | 2.22 | 0.62 | -7.95 | 8.70 | 0.4518 |
| spreads | close | draftkings | home | 2025 | 330 | 164 | 160 | 6 | -11.59 | -3.25 | -11.17 | 5.28 | 0.7488 |
| spreads | close | draftkings | home | 2026 | 402 | 215 | 184 | 3 | 14.08 | 3.22 | -3.73 | 9.78 | 0.2150 |
| spreads | close | draftkings | home | 2027 | 107 | 50 | 57 | 0 | -12.81 | -10.86 | -24.43 | 2.48 | 0.9066 |
| spreads | close | draftkings | away | 2022 | 292 | 140 | 149 | 3 | -24.05 | -7.55 | -17.29 | 1.91 | 0.9036 |
| spreads | close | draftkings | away | 2023 | 310 | 138 | 169 | 3 | -48.10 | -14.25 | -22.75 | -6.29 | 0.9976 |
| spreads | close | draftkings | away | 2024 | 331 | 154 | 172 | 5 | -35.13 | -9.81 | -17.80 | -1.46 | 0.9731 |
| spreads | close | draftkings | away | 2025 | 330 | 160 | 164 | 6 | -20.18 | -5.66 | -14.11 | 2.20 | 0.8780 |
| spreads | close | draftkings | away | 2026 | 402 | 184 | 215 | 3 | -52.06 | -11.83 | -18.34 | -4.76 | 0.9981 |
| spreads | close | draftkings | away | 2027 | 107 | 57 | 50 | 0 | 2.09 | 1.78 | -11.75 | 15.56 | 0.4159 |
| spreads | close | draftkings | fav | 2022 | 292 | 132 | 157 | 3 | -40.90 | -12.85 | -23.25 | -1.99 | 0.9788 |
| spreads | close | draftkings | fav | 2023 | 310 | 157 | 150 | 3 | -8.20 | -2.43 | -11.05 | 5.71 | 0.6822 |
| spreads | close | draftkings | fav | 2024 | 331 | 173 | 153 | 5 | 4.74 | 1.32 | -7.35 | 9.92 | 0.3988 |
| spreads | close | draftkings | fav | 2025 | 330 | 149 | 175 | 6 | -42.93 | -12.06 | -19.98 | -4.06 | 0.9935 |
| spreads | close | draftkings | fav | 2026 | 402 | 184 | 215 | 3 | -50.22 | -11.51 | -18.19 | -4.85 | 0.9977 |
| spreads | close | draftkings | fav | 2027 | 107 | 55 | 52 | 0 | -1.66 | -1.42 | -13.53 | 10.73 | 0.5776 |
| spreads | close | draftkings | dog | 2022 | 292 | 157 | 132 | 3 | 12.00 | 3.78 | -7.09 | 14.09 | 0.2748 |
| spreads | close | draftkings | dog | 2023 | 310 | 150 | 157 | 3 | -23.15 | -6.85 | -15.06 | 1.76 | 0.9089 |
| spreads | close | draftkings | dog | 2024 | 331 | 153 | 173 | 5 | -37.65 | -10.49 | -19.07 | -1.82 | 0.9788 |
| spreads | close | draftkings | dog | 2025 | 330 | 175 | 149 | 6 | 11.16 | 3.13 | -4.80 | 10.89 | 0.2596 |
| spreads | close | draftkings | dog | 2026 | 402 | 215 | 184 | 3 | 12.24 | 2.77 | -3.80 | 9.45 | 0.2467 |
| spreads | close | draftkings | dog | 2027 | 107 | 52 | 55 | 0 | -9.06 | -7.62 | -19.61 | 4.17 | 0.8527 |
| spreads | close | best decidable | home | 2022 | 292 | 149 | 140 | 3 | -4.85 | -1.53 | -11.03 | 8.37 | 0.6032 |
| spreads | close | best decidable | home | 2023 | 310 | 169 | 138 | 3 | 16.75 | 4.96 | -3.00 | 13.51 | 0.1632 |
| spreads | close | best decidable | home | 2024 | 331 | 172 | 154 | 5 | 2.22 | 0.62 | -7.95 | 8.70 | 0.4518 |
| spreads | close | best decidable | home | 2025 | 330 | 164 | 160 | 6 | -11.59 | -3.25 | -11.17 | 5.28 | 0.7488 |
| spreads | close | best decidable | home | 2026 | 402 | 213 | 186 | 3 | 13.66 | 3.18 | -3.75 | 9.99 | 0.2206 |
| spreads | close | best decidable | home | 2027 | 107 | 51 | 56 | 0 | -9.19 | -7.96 | -21.19 | 4.80 | 0.8353 |
| spreads | close | best decidable | away | 2022 | 292 | 140 | 149 | 3 | -24.05 | -7.55 | -17.29 | 1.91 | 0.9036 |
| spreads | close | best decidable | away | 2023 | 310 | 138 | 169 | 3 | -48.10 | -14.25 | -22.75 | -6.29 | 0.9976 |
| spreads | close | best decidable | away | 2024 | 331 | 154 | 172 | 5 | -35.13 | -9.81 | -17.80 | -1.46 | 0.9731 |
| spreads | close | best decidable | away | 2025 | 330 | 160 | 164 | 6 | -20.18 | -5.66 | -14.11 | 2.20 | 0.8780 |
| spreads | close | best decidable | away | 2026 | 402 | 186 | 213 | 3 | -42.75 | -9.93 | -16.80 | -2.98 | 0.9919 |
| spreads | close | best decidable | away | 2027 | 107 | 56 | 51 | 0 | 1.35 | 1.17 | -11.63 | 14.50 | 0.4433 |
| spreads | close | best decidable | fav | 2022 | 292 | 132 | 157 | 3 | -40.90 | -12.85 | -23.25 | -1.99 | 0.9788 |
| spreads | close | best decidable | fav | 2023 | 310 | 157 | 150 | 3 | -8.20 | -2.43 | -11.05 | 5.71 | 0.6822 |
| spreads | close | best decidable | fav | 2024 | 331 | 173 | 153 | 5 | 4.74 | 1.32 | -7.35 | 9.92 | 0.3988 |
| spreads | close | best decidable | fav | 2025 | 330 | 149 | 175 | 6 | -42.93 | -12.06 | -19.98 | -4.06 | 0.9935 |
| spreads | close | best decidable | fav | 2026 | 402 | 179 | 220 | 3 | -55.40 | -13.00 | -19.57 | -5.82 | 0.9990 |
| spreads | close | best decidable | fav | 2027 | 107 | 54 | 53 | 0 | -2.24 | -1.96 | -15.33 | 10.97 | 0.5968 |
| spreads | close | best decidable | dog | 2022 | 292 | 157 | 132 | 3 | 12.00 | 3.78 | -7.09 | 14.09 | 0.2748 |
| spreads | close | best decidable | dog | 2023 | 310 | 150 | 157 | 3 | -23.15 | -6.85 | -15.06 | 1.76 | 0.9089 |
| spreads | close | best decidable | dog | 2024 | 331 | 153 | 173 | 5 | -37.65 | -10.49 | -19.07 | -1.82 | 0.9788 |
| spreads | close | best decidable | dog | 2025 | 330 | 175 | 149 | 6 | 11.16 | 3.13 | -4.80 | 10.89 | 0.2596 |
| spreads | close | best decidable | dog | 2026 | 402 | 220 | 179 | 3 | 26.31 | 6.07 | -1.13 | 12.60 | 0.0730 |
| spreads | close | best decidable | dog | 2027 | 107 | 53 | 54 | 0 | -5.60 | -4.80 | -17.56 | 8.40 | 0.7267 |
| totals | first | draftkings | over | 2022 | 292 | 143 | 148 | 1 | -19.45 | -6.08 | -14.54 | 3.21 | 0.8697 |
| totals | first | draftkings | over | 2023 | 310 | 159 | 148 | 3 | -4.20 | -1.24 | -10.66 | 8.55 | 0.5833 |
| totals | first | draftkings | over | 2024 | 331 | 172 | 157 | 2 | -0.53 | -0.15 | -9.13 | 8.54 | 0.5112 |
| totals | first | draftkings | over | 2025 | 330 | 174 | 156 | 0 | 2.90 | 0.80 | -9.38 | 11.12 | 0.4483 |
| totals | first | draftkings | over | 2026 | 402 | 206 | 196 | 0 | -9.63 | -2.18 | -10.95 | 6.12 | 0.6627 |
| totals | first | draftkings | over | 2027 | 107 | 58 | 49 | 0 | 4.15 | 3.54 | -9.18 | 15.74 | 0.3198 |
| totals | first | draftkings | under | 2022 | 292 | 148 | 143 | 1 | -9.40 | -2.93 | -12.35 | 5.73 | 0.7034 |
| totals | first | draftkings | under | 2023 | 310 | 148 | 159 | 3 | -26.95 | -7.99 | -17.69 | 1.35 | 0.9119 |
| totals | first | draftkings | under | 2024 | 331 | 157 | 172 | 2 | -31.80 | -8.79 | -17.46 | 0.07 | 0.9547 |
| totals | first | draftkings | under | 2025 | 330 | 156 | 174 | 0 | -35.92 | -9.87 | -20.16 | 0.19 | 0.9461 |
| totals | first | draftkings | under | 2026 | 402 | 196 | 206 | 0 | -30.31 | -6.86 | -15.20 | 1.96 | 0.9070 |
| totals | first | draftkings | under | 2027 | 107 | 49 | 58 | 0 | -15.06 | -12.76 | -24.82 | -0.13 | 0.9548 |
| totals | first | best decidable | over | 2022 | 292 | 143 | 148 | 1 | -19.45 | -6.08 | -14.54 | 3.21 | 0.8697 |
| totals | first | best decidable | over | 2023 | 310 | 159 | 148 | 3 | -4.20 | -1.24 | -10.66 | 8.55 | 0.5833 |
| totals | first | best decidable | over | 2024 | 331 | 172 | 157 | 2 | -0.53 | -0.15 | -9.13 | 8.54 | 0.5112 |
| totals | first | best decidable | over | 2025 | 330 | 174 | 156 | 0 | 2.90 | 0.80 | -9.38 | 11.12 | 0.4483 |
| totals | first | best decidable | over | 2026 | 402 | 205 | 197 | 0 | -9.80 | -2.23 | -11.08 | 5.96 | 0.6674 |
| totals | first | best decidable | over | 2027 | 107 | 55 | 52 | 0 | -1.72 | -1.48 | -15.16 | 11.94 | 0.5717 |
| totals | first | best decidable | under | 2022 | 292 | 148 | 143 | 1 | -9.40 | -2.93 | -12.35 | 5.73 | 0.7034 |
| totals | first | best decidable | under | 2023 | 310 | 148 | 159 | 3 | -26.95 | -7.99 | -17.69 | 1.35 | 0.9119 |
| totals | first | best decidable | under | 2024 | 331 | 157 | 172 | 2 | -31.80 | -8.79 | -17.46 | 0.07 | 0.9547 |
| totals | first | best decidable | under | 2025 | 330 | 156 | 174 | 0 | -35.92 | -9.87 | -20.16 | 0.19 | 0.9461 |
| totals | first | best decidable | under | 2026 | 402 | 197 | 205 | 0 | -26.13 | -5.96 | -14.25 | 2.87 | 0.8756 |
| totals | first | best decidable | under | 2027 | 107 | 52 | 55 | 0 | -8.27 | -7.08 | -20.59 | 6.72 | 0.8068 |
| totals | close | draftkings | over | 2022 | 292 | 144 | 148 | 0 | -18.80 | -5.84 | -14.13 | 3.58 | 0.8626 |
| totals | close | draftkings | over | 2023 | 310 | 159 | 148 | 3 | -3.60 | -1.07 | -10.71 | 8.66 | 0.5710 |
| totals | close | draftkings | over | 2024 | 331 | 168 | 159 | 4 | -6.78 | -1.89 | -10.62 | 7.14 | 0.6397 |
| totals | close | draftkings | over | 2025 | 330 | 155 | 166 | 9 | -27.40 | -7.77 | -17.63 | 2.23 | 0.8983 |
| totals | close | draftkings | over | 2026 | 402 | 202 | 200 | 0 | -18.00 | -4.08 | -12.64 | 3.83 | 0.7905 |
| totals | close | draftkings | over | 2027 | 107 | 55 | 52 | 0 | -1.99 | -1.70 | -14.70 | 11.07 | 0.5855 |
| totals | close | draftkings | under | 2022 | 292 | 148 | 144 | 0 | -9.95 | -3.10 | -12.39 | 5.19 | 0.7191 |
| totals | close | draftkings | under | 2023 | 310 | 148 | 159 | 3 | -26.80 | -7.93 | -17.64 | 1.64 | 0.9085 |
| totals | close | draftkings | under | 2024 | 331 | 159 | 168 | 4 | -25.92 | -7.20 | -16.17 | 1.43 | 0.9140 |
| totals | close | draftkings | under | 2025 | 330 | 166 | 155 | 9 | -4.58 | -1.30 | -11.26 | 8.48 | 0.5841 |
| totals | close | draftkings | under | 2026 | 402 | 200 | 202 | 0 | -22.73 | -5.13 | -13.00 | 3.51 | 0.8457 |
| totals | close | draftkings | under | 2027 | 107 | 52 | 55 | 0 | -8.72 | -7.38 | -19.88 | 5.55 | 0.8291 |
| totals | close | best decidable | over | 2022 | 292 | 144 | 148 | 0 | -18.80 | -5.84 | -14.13 | 3.58 | 0.8626 |
| totals | close | best decidable | over | 2023 | 310 | 159 | 148 | 3 | -3.60 | -1.07 | -10.71 | 8.66 | 0.5710 |
| totals | close | best decidable | over | 2024 | 331 | 168 | 159 | 4 | -6.78 | -1.89 | -10.62 | 7.14 | 0.6397 |
| totals | close | best decidable | over | 2025 | 330 | 155 | 166 | 9 | -27.40 | -7.77 | -17.63 | 2.23 | 0.8983 |
| totals | close | best decidable | over | 2026 | 402 | 203 | 199 | 0 | -12.67 | -2.91 | -11.56 | 5.12 | 0.7156 |
| totals | close | best decidable | over | 2027 | 107 | 54 | 53 | 0 | -3.00 | -2.61 | -15.31 | 9.41 | 0.6342 |
| totals | close | best decidable | under | 2022 | 292 | 148 | 144 | 0 | -9.95 | -3.10 | -12.39 | 5.19 | 0.7191 |
| totals | close | best decidable | under | 2023 | 310 | 148 | 159 | 3 | -26.80 | -7.93 | -17.64 | 1.64 | 0.9085 |
| totals | close | best decidable | under | 2024 | 331 | 159 | 168 | 4 | -25.92 | -7.20 | -16.17 | 1.43 | 0.9140 |
| totals | close | best decidable | under | 2025 | 330 | 166 | 155 | 9 | -4.58 | -1.30 | -11.26 | 8.48 | 0.5841 |
| totals | close | best decidable | under | 2026 | 402 | 199 | 203 | 0 | -21.16 | -4.86 | -12.83 | 3.79 | 0.8289 |
| totals | close | best decidable | under | 2027 | 107 | 53 | 54 | 0 | -5.54 | -4.78 | -16.82 | 7.85 | 0.7354 |

### Moneyline sides by price band (every side, unfloored), pooled seasons

| read | book | band | bets | W | L | P | units | ret% | lo% | hi% | p_one | mean_fair% | win% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| close | draftkings | <=-500 | 188 | 175 | 13 | 0 | 34.59 | 6.13 | 2.27 | 9.60 | 0.0023 | 84.12 | 93.09 |
| close | draftkings | -500..-200 | 793 | 543 | 250 | 0 | -151.38 | -7.11 | -10.88 | -3.60 | 0.9995 | 71.02 | 68.47 |
| close | draftkings | -200..+100 | 952 | 530 | 422 | 0 | -51.39 | -3.85 | -7.64 | -0.22 | 0.9559 | 55.44 | 55.67 |
| close | draftkings | +100..+300 | 1,311 | 487 | 824 | 0 | 7.15 | 0.55 | -5.72 | 6.73 | 0.4419 | 35.72 | 37.15 |
| close | draftkings | >+300 | 300 | 37 | 263 | 0 | -127.15 | -42.38 | -56.30 | -28.17 | 1.0000 | 18.20 | 12.33 |
| close | best decidable | <=-500 | 182 | 171 | 11 | 0 | 38.74 | 7.10 | 3.53 | 10.11 | 0.0002 | 84.13 | 93.96 |
| close | best decidable | -500..-200 | 791 | 542 | 249 | 0 | -146.37 | -6.92 | -10.44 | -3.42 | 0.9995 | 70.88 | 68.52 |
| close | best decidable | -200..+100 | 943 | 525 | 418 | 0 | -49.33 | -3.73 | -7.28 | -0.08 | 0.9529 | 55.36 | 55.67 |
| close | best decidable | +100..+300 | 1,312 | 493 | 819 | 0 | 20.91 | 1.59 | -4.74 | 7.54 | 0.3351 | 35.70 | 37.58 |
| close | best decidable | >+300 | 316 | 41 | 275 | 0 | -122.45 | -38.75 | -52.42 | -22.72 | 1.0000 | 17.97 | 12.97 |
| first | draftkings | <=-500 | 178 | 168 | 10 | 0 | 41.33 | 7.74 | 4.36 | 10.84 | 0.0000 | 84.08 | 94.38 |
| first | draftkings | -500..-200 | 752 | 518 | 234 | 0 | -133.24 | -6.62 | -10.27 | -3.02 | 0.9986 | 70.98 | 68.88 |
| first | draftkings | -200..+100 | 978 | 544 | 434 | 0 | -63.67 | -4.55 | -8.59 | -0.49 | 0.9693 | 55.91 | 55.62 |
| first | draftkings | +100..+300 | 1,358 | 508 | 850 | 0 | -6.16 | -0.45 | -6.16 | 4.84 | 0.5531 | 36.19 | 37.41 |
| first | draftkings | >+300 | 278 | 34 | 244 | 0 | -118.90 | -42.77 | -57.32 | -26.73 | 1.0000 | 18.11 | 12.23 |
| close | pinnacle (reference, not bettable) | <=-500 | 161 | 150 | 11 | 0 | 30.51 | 6.32 | 2.14 | 9.93 | 0.0037 | 84.86 | 93.17 |
| close | pinnacle (reference, not bettable) | -500..-200 | 744 | 511 | 233 | 0 | -137.18 | -6.87 | -10.40 | -3.16 | 0.9989 | 71.55 | 68.68 |
| close | pinnacle (reference, not bettable) | -200..+100 | 852 | 469 | 383 | 0 | -61.25 | -5.13 | -9.09 | -1.25 | 0.9847 | 55.87 | 55.05 |
| close | pinnacle (reference, not bettable) | +100..+300 | 1,223 | 471 | 752 | 0 | 46.95 | 3.84 | -2.03 | 9.80 | 0.1424 | 36.07 | 38.51 |
| close | pinnacle (reference, not bettable) | >+300 | 304 | 41 | 263 | 0 | -112.13 | -36.88 | -52.17 | -21.53 | 1.0000 | 18.37 | 13.49 |

### DraftKings close moneyline sides, band by season

| band | season | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|
| +100..+300 | 2022 | 209 | 82 | 127 | 0 | 18.75 | 8.97 | -9.03 | 26.84 | 0.1991 |
| +100..+300 | 2023 | 230 | 83 | 147 | 0 | -5.45 | -2.37 | -15.92 | 11.33 | 0.6116 |
| +100..+300 | 2024 | 242 | 71 | 171 | 0 | -48.80 | -20.17 | -31.76 | -8.25 | 0.9976 |
| +100..+300 | 2025 | 236 | 95 | 141 | 0 | 23.67 | 10.03 | -3.45 | 22.58 | 0.1095 |
| +100..+300 | 2026 | 311 | 126 | 185 | 0 | 22.74 | 7.31 | -5.03 | 19.96 | 0.1670 |
| +100..+300 | 2027 | 83 | 30 | 53 | 0 | -3.76 | -4.53 | -28.96 | 19.76 | 0.6193 |
| -200..+100 | 2022 | 138 | 76 | 62 | 0 | -7.03 | -3.70 | -13.12 | 5.95 | 0.7327 |
| -200..+100 | 2023 | 168 | 98 | 70 | 0 | 1.15 | 0.48 | -7.91 | 9.22 | 0.4640 |
| -200..+100 | 2024 | 176 | 110 | 66 | 0 | 18.47 | 7.35 | -0.51 | 15.01 | 0.0612 |
| -200..+100 | 2025 | 183 | 97 | 86 | 0 | -18.16 | -7.33 | -15.40 | 1.69 | 0.9208 |
| -200..+100 | 2026 | 224 | 112 | 112 | 0 | -45.98 | -14.49 | -21.98 | -6.76 | 0.9989 |
| -200..+100 | 2027 | 63 | 37 | 26 | 0 | 0.16 | 0.18 | -16.00 | 15.72 | 0.4926 |
| -500..-200 | 2022 | 139 | 88 | 51 | 0 | -50.82 | -13.63 | -22.58 | -4.24 | 0.9931 |
| -500..-200 | 2023 | 132 | 90 | 42 | 0 | -21.45 | -6.16 | -15.38 | 2.13 | 0.8766 |
| -500..-200 | 2024 | 147 | 109 | 38 | 0 | 1.77 | 0.45 | -7.06 | 7.58 | 0.4581 |
| -500..-200 | 2025 | 145 | 96 | 49 | 0 | -42.94 | -10.89 | -18.81 | -3.51 | 0.9901 |
| -500..-200 | 2026 | 186 | 132 | 54 | 0 | -21.61 | -4.28 | -10.99 | 2.33 | 0.8477 |
| -500..-200 | 2027 | 44 | 28 | 16 | 0 | -16.32 | -13.77 | -27.73 | -0.41 | 0.9463 |
| <=-500 | 2022 | 41 | 38 | 3 | 0 | 6.69 | 5.44 | -2.60 | 11.87 | 0.1151 |
| <=-500 | 2023 | 36 | 31 | 5 | 0 | -1.51 | -1.39 | -13.73 | 8.48 | 0.5811 |
| <=-500 | 2024 | 36 | 35 | 1 | 0 | 10.98 | 10.17 | 3.89 | 14.25 | 0.0009 |
| <=-500 | 2025 | 39 | 37 | 2 | 0 | 9.35 | 7.99 | 0.64 | 13.99 | 0.0265 |
| <=-500 | 2026 | 27 | 25 | 2 | 0 | 4.98 | 6.15 | -2.96 | 14.41 | 0.1243 |
| <=-500 | 2027 | 9 | 9 | 0 | 0 | 4.08 | 15.13 | 12.76 | 16.98 | 0.0000 |
| >+300 | 2022 | 57 | 8 | 49 | 0 | -20.65 | -36.23 | -67.46 | 1.11 | 0.9620 |
| >+300 | 2023 | 54 | 8 | 46 | 0 | -12.70 | -23.52 | -61.11 | 19.30 | 0.8321 |
| >+300 | 2024 | 61 | 6 | 55 | 0 | -33.70 | -55.25 | -85.52 | -19.11 | 0.9966 |
| >+300 | 2025 | 57 | 5 | 52 | 0 | -33.80 | -59.30 | -85.09 | -30.33 | 0.9997 |
| >+300 | 2026 | 56 | 7 | 49 | 0 | -24.00 | -42.86 | -73.85 | -10.87 | 0.9882 |
| >+300 | 2027 | 15 | 3 | 12 | 0 | -2.30 | -15.33 | -73.75 | 59.38 | 0.6398 |

### What the sample resolves

- h2h: one side at the DraftKings close, 1772 graded bets; per-bet return sd 0.903; 90% half-width of a return = +/-3.5 points (2,700 bets of the same sd: +/-2.9)
- spreads: one side at the DraftKings close, 1752 graded bets; per-bet return sd 0.954; 90% half-width of a return = +/-3.7 points (2,700 bets of the same sd: +/-3.0)
- totals: one side at the DraftKings close, 1756 graded bets; per-bet return sd 0.955; 90% half-width of a return = +/-3.8 points (2,700 bets of the same sd: +/-3.0)


## r2_accuracy.py

### The open and the close, Pinnacle and DraftKings, on the same games (pooled)

| market | read | book | n | logloss | brier | const_logloss | calib_slope | slope_se | calib_icpt | mean_p | mean_y |
|---|---|---|---|---|---|---|---|---|---|---|---|
| h2h | open | pinnacle | 1,642 | 0.6105 | 0.2127 | 0.6597 | 0.8910 | 0.0737 | 0.1597 | 0.60 | 0.63 |
| h2h | open | draftkings | 1,642 | 0.6121 | 0.2134 | 0.6597 | 0.8852 | 0.0741 | 0.1685 | 0.60 | 0.63 |
| h2h | close | pinnacle | 1,642 | 0.6116 | 0.2131 | 0.6597 | 0.8686 | 0.0720 | 0.1727 | 0.60 | 0.63 |
| h2h | close | draftkings | 1,642 | 0.6105 | 0.2127 | 0.6597 | 0.8767 | 0.0722 | 0.1699 | 0.60 | 0.63 |
| spreads | open | pinnacle | 1,608 | 0.6919 | 0.2494 | 0.6916 | 3.0429 | 1.1673 | 0.1045 | 0.50 | 0.53 |
| spreads | open | draftkings | 1,626 | 0.6935 | 0.2502 | 0.6917 | -1.5436 | 1.8948 | 0.1051 | 0.50 | 0.53 |
| spreads | close | pinnacle | 1,615 | 0.6926 | 0.2497 | 0.6920 | 1.3395 | 1.0908 | 0.0944 | 0.50 | 0.52 |
| spreads | close | draftkings | 1,623 | 0.6928 | 0.2498 | 0.6918 | 2.0691 | 1.5548 | 0.1034 | 0.50 | 0.53 |
| totals | open | pinnacle | 1,627 | 0.6926 | 0.2497 | 0.6931 | 1.7626 | 1.2390 | 0.0158 | 0.50 | 0.50 |
| totals | open | draftkings | 1,637 | 0.6931 | 0.2500 | 0.6923 | 1.0988 | 1.9699 | 0.0822 | 0.50 | 0.52 |
| totals | close | pinnacle | 1,622 | 0.6929 | 0.2499 | 0.6930 | 1.0280 | 1.1586 | 0.0233 | 0.50 | 0.51 |
| totals | close | draftkings | 1,626 | 0.6932 | 0.2500 | 0.6931 | 0.3268 | 1.9104 | 0.0224 | 0.50 | 0.51 |

### By season

| market | season | read | book | n | logloss | brier | const_logloss | calib_slope | slope_se | calib_icpt | mean_p | mean_y |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| h2h | 2022 | close | draftkings | 240 | 0.6289 | 0.2220 | 0.6525 | 0.6525 | 0.1569 | 0.3475 | 0.59 | 0.64 |
| h2h | 2022 | close | pinnacle | 240 | 0.6304 | 0.2227 | 0.6525 | 0.6460 | 0.1569 | 0.3514 | 0.59 | 0.64 |
| h2h | 2022 | open | draftkings | 240 | 0.6191 | 0.2179 | 0.6525 | 0.7265 | 0.1656 | 0.3182 | 0.59 | 0.64 |
| h2h | 2022 | open | pinnacle | 240 | 0.6227 | 0.2193 | 0.6525 | 0.6994 | 0.1618 | 0.3349 | 0.59 | 0.64 |
| h2h | 2023 | close | draftkings | 272 | 0.6076 | 0.2105 | 0.6616 | 0.9518 | 0.1877 | 0.1015 | 0.61 | 0.62 |
| h2h | 2023 | close | pinnacle | 272 | 0.6090 | 0.2109 | 0.6616 | 0.9396 | 0.1871 | 0.1049 | 0.61 | 0.62 |
| h2h | 2023 | open | draftkings | 272 | 0.6217 | 0.2161 | 0.6616 | 0.8286 | 0.1830 | 0.1597 | 0.60 | 0.62 |
| h2h | 2023 | open | pinnacle | 272 | 0.6173 | 0.2143 | 0.6616 | 0.8765 | 0.1867 | 0.1354 | 0.61 | 0.62 |
| h2h | 2024 | close | draftkings | 291 | 0.5674 | 0.1931 | 0.6456 | 1.1893 | 0.1927 | 0.1487 | 0.61 | 0.65 |
| h2h | 2024 | close | pinnacle | 291 | 0.5684 | 0.1934 | 0.6456 | 1.1859 | 0.1925 | 0.1504 | 0.61 | 0.65 |
| h2h | 2024 | open | draftkings | 291 | 0.5770 | 0.1969 | 0.6456 | 1.1866 | 0.1997 | 0.1775 | 0.60 | 0.65 |
| h2h | 2024 | open | pinnacle | 291 | 0.5739 | 0.1959 | 0.6456 | 1.2022 | 0.2012 | 0.1420 | 0.61 | 0.65 |
| h2h | 2025 | close | draftkings | 330 | 0.6139 | 0.2149 | 0.6649 | 0.8601 | 0.1569 | 0.1313 | 0.60 | 0.62 |
| h2h | 2025 | close | pinnacle | 330 | 0.6150 | 0.2154 | 0.6649 | 0.8532 | 0.1568 | 0.1351 | 0.60 | 0.62 |
| h2h | 2025 | open | draftkings | 330 | 0.6149 | 0.2155 | 0.6649 | 0.8848 | 0.1643 | 0.1275 | 0.60 | 0.62 |
| h2h | 2025 | open | pinnacle | 330 | 0.6126 | 0.2145 | 0.6649 | 0.8872 | 0.1618 | 0.1088 | 0.60 | 0.62 |
| h2h | 2026 | close | draftkings | 402 | 0.6251 | 0.2190 | 0.6552 | 0.7810 | 0.1528 | 0.2420 | 0.60 | 0.64 |
| h2h | 2026 | close | pinnacle | 402 | 0.6253 | 0.2190 | 0.6552 | 0.7745 | 0.1516 | 0.2416 | 0.60 | 0.64 |
| h2h | 2026 | open | draftkings | 402 | 0.6218 | 0.2177 | 0.6552 | 0.8135 | 0.1556 | 0.2203 | 0.60 | 0.64 |
| h2h | 2026 | open | pinnacle | 402 | 0.6208 | 0.2172 | 0.6552 | 0.8189 | 0.1547 | 0.2206 | 0.60 | 0.64 |
| h2h | 2027 | close | draftkings | 107 | 0.6285 | 0.2208 | 0.6896 | 1.0868 | 0.3116 | -0.2864 | 0.60 | 0.54 |
| h2h | 2027 | close | pinnacle | 107 | 0.6311 | 0.2218 | 0.6896 | 1.0653 | 0.3101 | -0.2760 | 0.60 | 0.54 |
| h2h | 2027 | open | draftkings | 107 | 0.6226 | 0.2186 | 0.6896 | 1.0982 | 0.3044 | -0.3192 | 0.60 | 0.54 |
| h2h | 2027 | open | pinnacle | 107 | 0.6204 | 0.2176 | 0.6896 | 1.1317 | 0.3071 | -0.3395 | 0.60 | 0.54 |
| spreads | 2022 | close | draftkings | 237 | 0.6933 | 0.2501 | 0.6931 | 0.0282 | 3.8745 | 0.0254 | 0.50 | 0.51 |
| spreads | 2022 | close | pinnacle | 236 | 0.6923 | 0.2496 | 0.6931 | 2.4712 | 3.2221 | 0.0204 | 0.50 | 0.50 |
| spreads | 2022 | open | draftkings | 234 | 0.6936 | 0.2502 | 0.6930 | -0.3758 | 2.9764 | 0.0341 | 0.50 | 0.51 |
| spreads | 2022 | open | pinnacle | 232 | 0.6906 | 0.2487 | 0.6926 | 6.1439 | 3.1551 | 0.0428 | 0.50 | 0.52 |
| spreads | 2023 | close | draftkings | 269 | 0.6943 | 0.2506 | 0.6881 | -4.1923 | 3.7683 | 0.2071 | 0.50 | 0.55 |
| spreads | 2023 | close | pinnacle | 272 | 0.6904 | 0.2486 | 0.6886 | 5.7176 | 2.6993 | 0.1937 | 0.50 | 0.55 |
| spreads | 2023 | open | draftkings | 269 | 0.6935 | 0.2502 | 0.6895 | -3.1593 | 6.3325 | 0.1695 | 0.50 | 0.54 |
| spreads | 2023 | open | pinnacle | 268 | 0.6929 | 0.2499 | 0.6898 | 1.0819 | 2.4451 | 0.1673 | 0.50 | 0.54 |
| spreads | 2024 | close | draftkings | 287 | 0.6932 | 0.2500 | 0.6893 | -0.0027 | 4.4979 | 0.1747 | 0.50 | 0.54 |
| spreads | 2024 | close | pinnacle | 289 | 0.6929 | 0.2499 | 0.6894 | 0.3938 | 2.8536 | 0.1706 | 0.50 | 0.54 |
| spreads | 2024 | open | draftkings | 285 | 0.6939 | 0.2504 | 0.6872 | -8.6428 | 6.6137 | 0.2161 | 0.50 | 0.55 |
| spreads | 2024 | open | pinnacle | 288 | 0.6913 | 0.2491 | 0.6902 | 4.4320 | 2.5716 | 0.1826 | 0.50 | 0.54 |
| spreads | 2025 | close | draftkings | 324 | 0.6924 | 0.2496 | 0.6931 | 5.7209 | 4.5873 | 0.0277 | 0.50 | 0.51 |
| spreads | 2025 | close | pinnacle | 321 | 0.6927 | 0.2498 | 0.6930 | 1.2942 | 2.3457 | 0.0295 | 0.50 | 0.51 |
| spreads | 2025 | open | draftkings | 329 | 0.6934 | 0.2501 | 0.6918 | -11.6423 | 11.4796 | 0.1203 | 0.50 | 0.53 |
| spreads | 2025 | open | pinnacle | 321 | 0.6933 | 0.2501 | 0.6917 | -0.2975 | 3.1020 | 0.1076 | 0.50 | 0.53 |
| spreads | 2026 | close | draftkings | 399 | 0.6912 | 0.2490 | 0.6901 | 6.2330 | 2.6990 | 0.1717 | 0.50 | 0.54 |
| spreads | 2026 | close | pinnacle | 392 | 0.6948 | 0.2508 | 0.6906 | -2.5538 | 2.0918 | 0.1574 | 0.50 | 0.54 |
| spreads | 2026 | open | draftkings | 402 | 0.6934 | 0.2501 | 0.6921 | -0.6772 | 3.6162 | 0.0879 | 0.50 | 0.52 |
| spreads | 2026 | open | pinnacle | 394 | 0.6916 | 0.2492 | 0.6910 | 3.8269 | 2.5557 | 0.1090 | 0.50 | 0.53 |
| spreads | 2027 | close | draftkings | 107 | 0.6933 | 0.2501 | 0.6910 | 0.1786 | 5.2836 | -0.1313 | 0.50 | 0.47 |
| spreads | 2027 | close | pinnacle | 105 | 0.6904 | 0.2486 | 0.6909 | 5.3044 | 4.1392 | -0.1336 | 0.50 | 0.47 |
| spreads | 2027 | open | draftkings | 107 | 0.6929 | 0.2499 | 0.6910 | 1.3334 | 5.5415 | -0.1329 | 0.50 | 0.47 |
| spreads | 2027 | open | pinnacle | 105 | 0.6912 | 0.2490 | 0.6909 | 5.0052 | 4.7387 | -0.1422 | 0.50 | 0.47 |
| totals | 2022 | close | draftkings | 240 | 0.6932 | 0.2500 | 0.6930 | 0.4835 | 2.7721 | -0.0331 | 0.50 | 0.49 |
| totals | 2022 | close | pinnacle | 239 | 0.6940 | 0.2504 | 0.6931 | -1.9346 | 3.4539 | -0.0306 | 0.50 | 0.49 |
| totals | 2022 | open | draftkings | 239 | 0.6931 | 0.2500 | 0.6927 | 0.5451 | 2.2546 | -0.0583 | 0.50 | 0.49 |
| totals | 2022 | open | pinnacle | 236 | 0.6931 | 0.2500 | 0.6922 | 0.1705 | 3.4680 | -0.0836 | 0.50 | 0.48 |
| totals | 2023 | close | draftkings | 269 | 0.6924 | 0.2496 | 0.6916 | 9.4923 | 6.6732 | 0.1155 | 0.50 | 0.53 |
| totals | 2023 | close | pinnacle | 266 | 0.6924 | 0.2496 | 0.6913 | 1.6369 | 2.9679 | 0.1085 | 0.50 | 0.53 |
| totals | 2023 | open | draftkings | 270 | 0.6934 | 0.2501 | 0.6914 | -6.1568 | 9.3323 | 0.1238 | 0.50 | 0.53 |
| totals | 2023 | open | pinnacle | 268 | 0.6926 | 0.2497 | 0.6918 | 1.8685 | 2.8886 | 0.1075 | 0.50 | 0.53 |
| totals | 2024 | close | draftkings | 287 | 0.6932 | 0.2500 | 0.6921 | -0.7343 | 7.6305 | 0.0901 | 0.50 | 0.52 |
| totals | 2024 | close | pinnacle | 284 | 0.6928 | 0.2498 | 0.6919 | 0.7443 | 3.1627 | 0.0912 | 0.50 | 0.52 |
| totals | 2024 | open | draftkings | 289 | 0.6924 | 0.2496 | 0.6905 | 18.3321 | 9.6678 | 0.1283 | 0.50 | 0.54 |
| totals | 2024 | open | pinnacle | 290 | 0.6926 | 0.2497 | 0.6920 | 1.8904 | 2.8372 | 0.0998 | 0.50 | 0.52 |
| totals | 2025 | close | draftkings | 321 | 0.6930 | 0.2499 | 0.6926 | 2.7826 | 7.6307 | -0.0665 | 0.50 | 0.48 |
| totals | 2025 | close | pinnacle | 325 | 0.6934 | 0.2501 | 0.6929 | 0.3181 | 2.5233 | -0.0469 | 0.50 | 0.49 |
| totals | 2025 | open | draftkings | 330 | 0.6932 | 0.2500 | 0.6917 | 1.9634 | 11.2813 | 0.1145 | 0.50 | 0.53 |
| totals | 2025 | open | pinnacle | 326 | 0.6915 | 0.2492 | 0.6931 | 4.2675 | 2.6951 | -0.0133 | 0.50 | 0.50 |
| totals | 2026 | close | draftkings | 402 | 0.6938 | 0.2503 | 0.6931 | -3.8554 | 4.1156 | 0.0056 | 0.50 | 0.50 |
| totals | 2026 | close | pinnacle | 401 | 0.6917 | 0.2493 | 0.6931 | 2.9493 | 2.1065 | 0.0033 | 0.50 | 0.50 |
| totals | 2026 | open | draftkings | 402 | 0.6929 | 0.2499 | 0.6928 | 5.0863 | 6.8455 | 0.0463 | 0.50 | 0.51 |
| totals | 2026 | open | pinnacle | 400 | 0.6931 | 0.2500 | 0.6929 | 0.9676 | 2.7440 | -0.0475 | 0.50 | 0.49 |
| totals | 2027 | close | draftkings | 107 | 0.6933 | 0.2501 | 0.6928 | 0.0272 | 6.1638 | 0.0562 | 0.50 | 0.51 |
| totals | 2027 | close | pinnacle | 107 | 0.6941 | 0.2505 | 0.6931 | -1.4916 | 4.3731 | 0.0227 | 0.50 | 0.50 |
| totals | 2027 | open | draftkings | 107 | 0.6940 | 0.2504 | 0.6896 | -10.1447 | 11.4101 | 0.1445 | 0.50 | 0.54 |
| totals | 2027 | open | pinnacle | 107 | 0.6936 | 0.2502 | 0.6928 | -0.7085 | 5.0766 | 0.0554 | 0.50 | 0.51 |

### The close's age: minutes from the book's last change to the tip, at the close read

| market | bookmaker | 0.25 | 0.5 | 0.75 |
|---|---|---|---|---|
| h2h | draftkings | 30.00 | 80.00 | 200.00 |
| h2h | pinnacle | 20.00 | 26.00 | 45.00 |
| spreads | draftkings | 30.00 | 75.00 | 185.00 |
| spreads | pinnacle | 20.00 | 30.00 | 55.00 |
| totals | draftkings | 30.00 | 70.00 | 190.00 |
| totals | pinnacle | 20.00 | 35.00 | 70.00 |


## r2_methods.py

### The walk-forward tables

| priced season | train games (spread) | train games (total) | c_sp (pts) | c_to (pts) | spread h at mean -10/-5/0/+5/+10 | total h at 150/155/160/165/170 | spread neff at 0 |
|---|---|---|---|---|---|---|---|
| 2023 | 290 | 292 | 1.04 | -0.30 | 21.32/21.32/21.32/21.32/21.32 | 21.32/21.32/21.32/21.32/21.32 | 289.00 |
| 2024 | 616 | 620 | 0.94 | 0.71 | 21.32/17.05/10.91/8.73/13.64 | 13.64/8.73/10.91/17.05/21.32 | 601.00 |
| 2025 | 945 | 951 | 0.78 | 0.77 | 13.64/8.73/5.59/3.58/6.98 | 8.73/5.59/4.47/6.98/10.91 | 789.00 |
| 2026 | 1,272 | 1,281 | 0.61 | 0.90 | 10.91/5.59/3.58/2.29/4.47 | 8.73/4.47/3.58/3.58/6.98 | 793.00 |
| 2027 | 1,673 | 1,683 | 0.50 | 0.93 | 8.73/4.47/2.86/1.83/3.58 | 6.98/4.47/3.58/2.86/3.58 | 848.00 |

### (a) line shopping, spreads, consensus over all ten books: read x cut

| method | market | consensus | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) line shopping | spreads | all ten books | 15utc | 0.000 | 2023-24 on | 1,003 | 521 | 470 | 12 | 5.23 | 0.48 | -4.21 | 5.09 | 0.4323 | -0.02 | 12.30 |
| (a) line shopping | spreads | all ten books | 15utc | 0.000 | 2022-23 (1-season table) | 262 | 141 | 118 | 3 | 11.05 | 3.87 | -5.76 | 13.60 | 0.2577 | -0.02 | 9.90 |
| (a) line shopping | spreads | all ten books | 15utc | 0.010 | 2023-24 on | 880 | 463 | 407 | 10 | 16.51 | 1.73 | -3.23 | 6.63 | 0.2835 | -0.02 | 12.50 |
| (a) line shopping | spreads | all ten books | 15utc | 0.010 | 2022-23 (1-season table) | 258 | 138 | 117 | 3 | 9.15 | 3.26 | -6.41 | 13.22 | 0.2955 | -0.02 | 10.10 |
| (a) line shopping | spreads | all ten books | 15utc | 0.020 | 2023-24 on | 715 | 392 | 315 | 8 | 46.69 | 6.01 | 0.37 | 11.35 | 0.0347 | -0.02 | 12.60 |
| (a) line shopping | spreads | all ten books | 15utc | 0.020 | 2022-23 (1-season table) | 236 | 127 | 107 | 2 | 9.35 | 3.63 | -6.10 | 13.36 | 0.2716 | -0.02 | 10.20 |
| (a) line shopping | spreads | all ten books | 15utc | 0.030 | 2023-24 on | 538 | 299 | 232 | 7 | 45.32 | 7.78 | 0.41 | 14.37 | 0.0340 | -0.02 | 13.00 |
| (a) line shopping | spreads | all ten books | 15utc | 0.030 | 2022-23 (1-season table) | 192 | 105 | 86 | 1 | 10.90 | 5.22 | -6.18 | 15.85 | 0.2217 | -0.02 | 10.40 |
| (a) line shopping | spreads | all ten books | 15utc | 0.040 | 2023-24 on | 275 | 144 | 127 | 4 | 5.78 | 1.95 | -7.88 | 11.71 | 0.3703 | -0.02 | 16.00 |
| (a) line shopping | spreads | all ten books | 15utc | 0.040 | 2022-23 (1-season table) | 110 | 58 | 51 | 1 | 2.80 | 2.38 | -10.17 | 15.11 | 0.3819 | -0.02 | 13.60 |
| (a) line shopping | spreads | all ten books | 15utc | 0.050 | 2023-24 on | 125 | 66 | 57 | 2 | 3.53 | 2.62 | -11.34 | 18.48 | 0.3840 | -0.02 | 21.60 |
| (a) line shopping | spreads | all ten books | 15utc | 0.050 | 2022-23 (1-season table) | 32 | 17 | 15 | 0 | 1.15 | 3.39 | -25.00 | 29.65 | 0.4188 | -0.02 | 15.60 |
| (a) line shopping | spreads | all ten books | 6h | 0.000 | 2023-24 on | 1,011 | 526 | 475 | 10 | 4.03 | 0.37 | -4.23 | 4.95 | 0.4478 | -0.02 | 17.50 |
| (a) line shopping | spreads | all ten books | 6h | 0.000 | 2022-23 (1-season table) | 267 | 144 | 118 | 5 | 13.65 | 4.73 | -5.01 | 14.10 | 0.2108 | -0.02 | 16.10 |
| (a) line shopping | spreads | all ten books | 6h | 0.010 | 2023-24 on | 904 | 475 | 420 | 9 | 13.50 | 1.37 | -3.59 | 6.28 | 0.3256 | -0.02 | 17.70 |
| (a) line shopping | spreads | all ten books | 6h | 0.010 | 2022-23 (1-season table) | 263 | 141 | 117 | 5 | 11.80 | 4.16 | -5.92 | 13.79 | 0.2440 | -0.02 | 16.30 |
| (a) line shopping | spreads | all ten books | 6h | 0.020 | 2023-24 on | 728 | 404 | 316 | 8 | 57.58 | 7.27 | 1.50 | 12.63 | 0.0163 | -0.02 | 18.10 |
| (a) line shopping | spreads | all ten books | 6h | 0.020 | 2022-23 (1-season table) | 249 | 134 | 111 | 4 | 11.65 | 4.33 | -5.56 | 13.72 | 0.2330 | -0.02 | 16.10 |
| (a) line shopping | spreads | all ten books | 6h | 0.030 | 2023-24 on | 528 | 298 | 223 | 7 | 53.69 | 9.38 | 2.22 | 16.18 | 0.0143 | -0.02 | 16.70 |
| (a) line shopping | spreads | all ten books | 6h | 0.030 | 2022-23 (1-season table) | 198 | 110 | 86 | 2 | 15.80 | 7.38 | -3.35 | 17.57 | 0.1309 | -0.02 | 16.70 |
| (a) line shopping | spreads | all ten books | 6h | 0.040 | 2023-24 on | 285 | 154 | 130 | 1 | 12.28 | 3.95 | -5.08 | 13.20 | 0.2384 | -0.02 | 18.90 |
| (a) line shopping | spreads | all ten books | 6h | 0.040 | 2022-23 (1-season table) | 117 | 67 | 49 | 1 | 13.75 | 10.96 | -2.49 | 25.20 | 0.0949 | -0.02 | 17.90 |
| (a) line shopping | spreads | all ten books | 6h | 0.050 | 2023-24 on | 123 | 67 | 56 | 0 | 5.65 | 4.19 | -9.33 | 18.90 | 0.3156 | -0.02 | 23.60 |
| (a) line shopping | spreads | all ten books | 6h | 0.050 | 2022-23 (1-season table) | 36 | 23 | 12 | 1 | 10.05 | 26.87 | 2.32 | 51.13 | 0.0334 | -0.02 | 22.20 |
| (a) line shopping | spreads | all ten books | 60m | 0.000 | 2023-24 on | 1,009 | 528 | 468 | 13 | 14.11 | 1.29 | -2.71 | 5.92 | 0.3145 | -0.02 | 8.80 |
| (a) line shopping | spreads | all ten books | 60m | 0.000 | 2022-23 (1-season table) | 264 | 141 | 120 | 3 | 8.75 | 3.05 | -6.88 | 12.71 | 0.3027 | -0.02 | 4.90 |
| (a) line shopping | spreads | all ten books | 60m | 0.010 | 2023-24 on | 895 | 473 | 412 | 10 | 20.94 | 2.15 | -2.71 | 6.91 | 0.2348 | -0.02 | 8.70 |
| (a) line shopping | spreads | all ten books | 60m | 0.010 | 2022-23 (1-season table) | 260 | 139 | 118 | 3 | 8.95 | 3.16 | -6.90 | 12.84 | 0.2993 | -0.02 | 5.00 |
| (a) line shopping | spreads | all ten books | 60m | 0.020 | 2023-24 on | 730 | 398 | 323 | 9 | 44.15 | 5.57 | -0.38 | 11.40 | 0.0563 | -0.02 | 8.60 |
| (a) line shopping | spreads | all ten books | 60m | 0.020 | 2022-23 (1-season table) | 249 | 133 | 114 | 2 | 7.50 | 2.76 | -7.40 | 12.48 | 0.3228 | -0.02 | 5.20 |
| (a) line shopping | spreads | all ten books | 60m | 0.030 | 2023-24 on | 531 | 286 | 238 | 7 | 25.41 | 4.42 | -2.53 | 11.76 | 0.1472 | -0.02 | 8.70 |
| (a) line shopping | spreads | all ten books | 60m | 0.030 | 2022-23 (1-season table) | 214 | 119 | 93 | 2 | 17.30 | 7.46 | -2.68 | 18.04 | 0.1221 | -0.02 | 6.10 |
| (a) line shopping | spreads | all ten books | 60m | 0.040 | 2023-24 on | 302 | 170 | 128 | 4 | 30.08 | 9.20 | -0.55 | 18.71 | 0.0565 | -0.02 | 10.30 |
| (a) line shopping | spreads | all ten books | 60m | 0.040 | 2022-23 (1-season table) | 130 | 74 | 55 | 1 | 14.60 | 10.46 | -2.17 | 22.69 | 0.0822 | -0.02 | 8.50 |
| (a) line shopping | spreads | all ten books | 60m | 0.050 | 2023-24 on | 129 | 73 | 56 | 0 | 11.17 | 7.83 | -7.46 | 23.00 | 0.1946 | -0.02 | 14.70 |
| (a) line shopping | spreads | all ten books | 60m | 0.050 | 2022-23 (1-season table) | 33 | 18 | 15 | 0 | 1.90 | 5.39 | -21.20 | 31.31 | 0.3686 | -0.01 | 12.10 |
| (a) line shopping | spreads | all ten books | close | 0.000 | 2023-24 on | 1,022 | 535 | 476 | 11 | 12.78 | 1.15 | -3.20 | 5.66 | 0.3365 | -0.02 | 6.10 |
| (a) line shopping | spreads | all ten books | close | 0.000 | 2022-23 (1-season table) | 261 | 141 | 118 | 2 | 10.70 | 3.75 | -6.32 | 13.48 | 0.2630 | -0.02 | 1.50 |
| (a) line shopping | spreads | all ten books | close | 0.010 | 2023-24 on | 915 | 485 | 419 | 11 | 25.38 | 2.55 | -2.31 | 7.79 | 0.1946 | -0.02 | 6.10 |
| (a) line shopping | spreads | all ten books | close | 0.010 | 2022-23 (1-season table) | 257 | 138 | 117 | 2 | 8.75 | 3.12 | -6.78 | 12.85 | 0.3000 | -0.02 | 1.60 |
| (a) line shopping | spreads | all ten books | close | 0.020 | 2023-24 on | 734 | 400 | 325 | 9 | 43.69 | 5.48 | -0.58 | 11.04 | 0.0582 | -0.02 | 5.30 |
| (a) line shopping | spreads | all ten books | close | 0.020 | 2022-23 (1-season table) | 246 | 132 | 112 | 2 | 8.50 | 3.17 | -6.61 | 13.24 | 0.2967 | -0.02 | 1.60 |
| (a) line shopping | spreads | all ten books | close | 0.030 | 2023-24 on | 545 | 298 | 240 | 7 | 35.54 | 6.02 | -1.02 | 12.50 | 0.0733 | -0.02 | 5.10 |
| (a) line shopping | spreads | all ten books | close | 0.030 | 2022-23 (1-season table) | 204 | 111 | 91 | 2 | 11.15 | 5.05 | -6.18 | 16.63 | 0.2361 | -0.02 | 2.00 |
| (a) line shopping | spreads | all ten books | close | 0.040 | 2023-24 on | 308 | 171 | 134 | 3 | 24.57 | 7.36 | -0.77 | 16.56 | 0.0829 | -0.02 | 7.10 |
| (a) line shopping | spreads | all ten books | close | 0.040 | 2022-23 (1-season table) | 123 | 70 | 53 | 0 | 12.60 | 9.47 | -4.36 | 22.88 | 0.1241 | -0.02 | 3.30 |
| (a) line shopping | spreads | all ten books | close | 0.050 | 2023-24 on | 128 | 74 | 54 | 0 | 14.48 | 10.26 | -4.62 | 25.06 | 0.1259 | -0.01 | 13.30 |
| (a) line shopping | spreads | all ten books | close | 0.050 | 2022-23 (1-season table) | 37 | 20 | 17 | 0 | 1.75 | 4.40 | -20.27 | 28.56 | 0.3851 | -0.02 | 8.10 |

### (a) line shopping, spreads, consensus over all ten books: cut 0.03 by season

| method | market | consensus | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) line shopping | spreads | all ten books | 15utc | 0.030 | 2023 | 192 | 105 | 86 | 1 | 10.90 | 5.22 | -6.18 | 15.85 | 0.2217 | -0.02 | 10.40 |
| (a) line shopping | spreads | all ten books | 15utc | 0.030 | 2024 | 226 | 125 | 97 | 4 | 19.21 | 7.90 | -2.55 | 17.76 | 0.0945 | -0.02 | 8.40 |
| (a) line shopping | spreads | all ten books | 15utc | 0.030 | 2025 | 130 | 73 | 55 | 2 | 12.94 | 9.22 | -4.85 | 23.41 | 0.1415 | -0.03 | 3.10 |
| (a) line shopping | spreads | all ten books | 15utc | 0.030 | 2026 | 141 | 85 | 55 | 1 | 24.45 | 15.84 | 4.02 | 27.03 | 0.0139 | -0.02 | 23.40 |
| (a) line shopping | spreads | all ten books | 15utc | 0.030 | 2027 | 41 | 16 | 25 | 0 | -11.28 | -25.26 | -52.13 | 4.68 | 0.9289 | -0.01 | 34.10 |
| (a) line shopping | spreads | all ten books | 6h | 0.030 | 2023 | 198 | 110 | 86 | 2 | 15.80 | 7.38 | -3.35 | 17.57 | 0.1309 | -0.02 | 16.70 |
| (a) line shopping | spreads | all ten books | 6h | 0.030 | 2024 | 224 | 123 | 98 | 3 | 15.62 | 6.44 | -4.36 | 16.60 | 0.1545 | -0.02 | 11.20 |
| (a) line shopping | spreads | all ten books | 6h | 0.030 | 2025 | 127 | 71 | 53 | 3 | 12.99 | 9.54 | -6.43 | 25.40 | 0.1565 | -0.03 | 10.20 |
| (a) line shopping | spreads | all ten books | 6h | 0.030 | 2026 | 141 | 89 | 51 | 1 | 33.16 | 21.49 | 10.35 | 32.07 | 0.0005 | -0.01 | 26.20 |
| (a) line shopping | spreads | all ten books | 6h | 0.030 | 2027 | 36 | 15 | 21 | 0 | -8.08 | -20.53 | -47.02 | 7.77 | 0.8896 | -0.01 | 36.10 |
| (a) line shopping | spreads | all ten books | 60m | 0.030 | 2023 | 214 | 119 | 93 | 2 | 17.30 | 7.46 | -2.68 | 18.04 | 0.1221 | -0.02 | 6.10 |
| (a) line shopping | spreads | all ten books | 60m | 0.030 | 2024 | 222 | 117 | 101 | 4 | 6.62 | 2.78 | -8.09 | 13.46 | 0.3369 | -0.02 | 5.00 |
| (a) line shopping | spreads | all ten books | 60m | 0.030 | 2025 | 132 | 68 | 62 | 2 | 0.23 | 0.16 | -13.39 | 13.50 | 0.4921 | -0.02 | 3.00 |
| (a) line shopping | spreads | all ten books | 60m | 0.030 | 2026 | 136 | 83 | 52 | 1 | 25.89 | 17.36 | 4.47 | 29.59 | 0.0118 | -0.01 | 16.20 |
| (a) line shopping | spreads | all ten books | 60m | 0.030 | 2027 | 41 | 18 | 23 | 0 | -7.33 | -16.08 | -41.52 | 11.03 | 0.8420 | -0.01 | 22.00 |
| (a) line shopping | spreads | all ten books | close | 0.030 | 2023 | 204 | 111 | 91 | 2 | 11.15 | 5.05 | -6.18 | 16.63 | 0.2361 | -0.02 | 2.00 |
| (a) line shopping | spreads | all ten books | close | 0.030 | 2024 | 227 | 122 | 101 | 4 | 11.52 | 4.72 | -6.20 | 14.67 | 0.2246 | -0.02 | 1.30 |
| (a) line shopping | spreads | all ten books | close | 0.030 | 2025 | 134 | 72 | 59 | 3 | 7.63 | 5.32 | -7.02 | 17.80 | 0.2475 | -0.02 | 0.00 |
| (a) line shopping | spreads | all ten books | close | 0.030 | 2026 | 143 | 86 | 57 | 0 | 23.48 | 14.93 | 2.98 | 27.72 | 0.0245 | -0.01 | 12.60 |
| (a) line shopping | spreads | all ten books | close | 0.030 | 2027 | 41 | 18 | 23 | 0 | -7.09 | -15.73 | -45.64 | 14.52 | 0.8129 | -0.01 | 17.10 |

### (a) line shopping, spreads, consensus over decidable only (catalogued): read x cut

| method | market | consensus | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.000 | 2023-24 on | 390 | 199 | 189 | 2 | -8.55 | -2.00 | -9.43 | 5.36 | 0.6732 | -0.01 | 21.80 |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.010 | 2023-24 on | 312 | 161 | 150 | 1 | -3.93 | -1.15 | -9.86 | 7.37 | 0.5858 | -0.01 | 24.00 |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.020 | 2023-24 on | 236 | 125 | 110 | 1 | 3.94 | 1.52 | -8.32 | 11.93 | 0.4018 | -0.01 | 25.00 |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.030 | 2023-24 on | 172 | 93 | 78 | 1 | 7.42 | 3.95 | -8.55 | 15.74 | 0.2913 | -0.01 | 26.20 |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.040 | 2023-24 on | 127 | 69 | 57 | 1 | 6.54 | 4.73 | -9.58 | 18.13 | 0.2891 | -0.02 | 26.00 |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.050 | 2023-24 on | 75 | 41 | 33 | 1 | 4.52 | 5.51 | -13.23 | 24.00 | 0.3185 | -0.02 | 28.00 |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.000 | 2023-24 on | 392 | 197 | 194 | 1 | -16.17 | -3.75 | -11.62 | 4.22 | 0.7793 | -0.01 | 25.50 |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.010 | 2023-24 on | 306 | 155 | 151 | 0 | -11.01 | -3.27 | -12.28 | 6.17 | 0.7221 | -0.01 | 27.80 |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.020 | 2023-24 on | 240 | 125 | 115 | 0 | -1.50 | -0.57 | -11.08 | 9.34 | 0.5362 | -0.01 | 28.30 |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.030 | 2023-24 on | 160 | 88 | 72 | 0 | 9.13 | 5.19 | -6.13 | 16.82 | 0.2328 | -0.01 | 28.10 |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.040 | 2023-24 on | 122 | 65 | 57 | 0 | 2.65 | 1.98 | -14.23 | 15.46 | 0.4120 | -0.01 | 29.50 |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.050 | 2023-24 on | 75 | 38 | 37 | 0 | -2.80 | -3.37 | -21.89 | 15.53 | 0.6139 | -0.01 | 29.30 |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.000 | 2023-24 on | 390 | 209 | 180 | 1 | 11.01 | 2.56 | -4.41 | 9.13 | 0.2712 | -0.01 | 16.90 |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.010 | 2023-24 on | 317 | 175 | 142 | 0 | 18.73 | 5.34 | -2.07 | 12.95 | 0.1246 | -0.01 | 18.60 |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.020 | 2023-24 on | 231 | 132 | 99 | 0 | 22.96 | 8.97 | -0.72 | 18.71 | 0.0636 | -0.01 | 19.00 |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.030 | 2023-24 on | 168 | 92 | 76 | 0 | 8.33 | 4.48 | -7.76 | 16.43 | 0.2732 | -0.01 | 17.90 |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.040 | 2023-24 on | 125 | 70 | 55 | 0 | 9.19 | 6.63 | -8.01 | 20.27 | 0.2193 | -0.01 | 18.40 |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.050 | 2023-24 on | 70 | 37 | 33 | 0 | 0.15 | 0.19 | -19.85 | 19.92 | 0.4937 | -0.01 | 21.40 |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.000 | 2023-24 on | 405 | 215 | 189 | 1 | 7.68 | 1.73 | -5.71 | 8.83 | 0.3494 | -0.01 | 13.60 |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.010 | 2023-24 on | 335 | 187 | 147 | 1 | 25.61 | 6.96 | -1.68 | 15.16 | 0.0862 | -0.01 | 15.20 |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.020 | 2023-24 on | 243 | 142 | 101 | 0 | 31.16 | 11.62 | 1.49 | 20.88 | 0.0247 | -0.01 | 14.00 |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.030 | 2023-24 on | 175 | 99 | 76 | 0 | 15.59 | 8.08 | -4.95 | 19.00 | 0.1364 | -0.01 | 14.90 |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.040 | 2023-24 on | 120 | 67 | 53 | 0 | 8.67 | 6.56 | -8.41 | 20.65 | 0.2257 | -0.01 | 13.30 |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.050 | 2023-24 on | 67 | 33 | 34 | 0 | -4.61 | -6.22 | -26.79 | 16.02 | 0.6862 | -0.01 | 17.90 |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |

### (a) line shopping, spreads, consensus over decidable only (catalogued): cut 0.03 by season

| method | market | consensus | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.030 | 2026 | 131 | 77 | 53 | 1 | 18.70 | 13.06 | 1.23 | 24.59 | 0.0332 | -0.01 | 23.70 |
| (a) line shopping | spreads | decidable only (catalogued) | 15utc | 0.030 | 2027 | 41 | 16 | 25 | 0 | -11.28 | -25.26 | -52.13 | 4.68 | 0.9289 | -0.01 | 34.10 |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.030 | 2026 | 124 | 74 | 50 | 0 | 19.31 | 14.14 | 1.86 | 25.61 | 0.0242 | -0.01 | 25.80 |
| (a) line shopping | spreads | decidable only (catalogued) | 6h | 0.030 | 2027 | 36 | 14 | 22 | 0 | -10.18 | -25.82 | -51.25 | 1.35 | 0.9422 | -0.01 | 36.10 |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.030 | 2026 | 126 | 74 | 52 | 0 | 16.74 | 12.03 | -1.18 | 25.34 | 0.0711 | -0.01 | 16.70 |
| (a) line shopping | spreads | decidable only (catalogued) | 60m | 0.030 | 2027 | 42 | 18 | 24 | 0 | -8.41 | -18.02 | -42.86 | 9.75 | 0.8704 | -0.01 | 21.40 |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.030 | 2026 | 134 | 81 | 53 | 0 | 22.68 | 15.35 | 2.70 | 27.27 | 0.0188 | -0.01 | 14.20 |
| (a) line shopping | spreads | decidable only (catalogued) | close | 0.030 | 2027 | 41 | 18 | 23 | 0 | -7.09 | -15.73 | -45.64 | 14.52 | 0.8129 | -0.01 | 17.10 |

### (a) line shopping, totals, consensus over all ten books: read x cut

| method | market | consensus | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) line shopping | totals | all ten books | 15utc | 0.000 | 2023-24 on | 710 | 361 | 344 | 5 | -16.80 | -2.17 | -8.04 | 4.25 | 0.7197 | -0.01 | 28.70 |
| (a) line shopping | totals | all ten books | 15utc | 0.000 | 2022-23 (1-season table) | 7 | 4 | 3 | 0 | 0.75 | 9.80 | -36.99 | 62.84 | 0.3797 | 0.01 | 42.90 |
| (a) line shopping | totals | all ten books | 15utc | 0.010 | 2023-24 on | 438 | 221 | 217 | 0 | -17.49 | -3.63 | -10.81 | 3.68 | 0.7955 | -0.01 | 39.00 |
| (a) line shopping | totals | all ten books | 15utc | 0.010 | 2022-23 (1-season table) | 2 | 2 | 0 | 0 | 2.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.05 | 100.00 |
| (a) line shopping | totals | all ten books | 15utc | 0.020 | 2023-24 on | 267 | 138 | 129 | 0 | -4.17 | -1.41 | -10.44 | 7.72 | 0.5985 | -0.00 | 45.70 |
| (a) line shopping | totals | all ten books | 15utc | 0.020 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.09 | 100.00 |
| (a) line shopping | totals | all ten books | 15utc | 0.030 | 2023-24 on | 139 | 70 | 69 | 0 | -7.19 | -4.63 | -19.06 | 9.54 | 0.7059 | 0.00 | 59.70 |
| (a) line shopping | totals | all ten books | 15utc | 0.030 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.09 | 100.00 |
| (a) line shopping | totals | all ten books | 15utc | 0.040 | 2023-24 on | 53 | 27 | 26 | 0 | -1.74 | -2.98 | -24.93 | 20.63 | 0.5848 | 0.01 | 69.80 |
| (a) line shopping | totals | all ten books | 15utc | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | 15utc | 0.050 | 2023-24 on | 8 | 3 | 5 | 0 | -2.41 | -27.57 | -75.95 | 20.67 | 0.8050 | 0.02 | 87.50 |
| (a) line shopping | totals | all ten books | 15utc | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | 6h | 0.000 | 2023-24 on | 735 | 377 | 358 | 0 | -16.26 | -2.01 | -8.06 | 4.15 | 0.7093 | -0.01 | 31.70 |
| (a) line shopping | totals | all ten books | 6h | 0.000 | 2022-23 (1-season table) | 8 | 3 | 5 | 0 | -2.30 | -26.44 | -71.14 | 20.22 | 0.8275 | -0.00 | 25.00 |
| (a) line shopping | totals | all ten books | 6h | 0.010 | 2023-24 on | 442 | 220 | 222 | 0 | -24.04 | -4.95 | -12.22 | 1.97 | 0.8733 | -0.01 | 42.10 |
| (a) line shopping | totals | all ten books | 6h | 0.010 | 2022-23 (1-season table) | 2 | 2 | 0 | 0 | 2.00 | 88.89 | 86.96 | 90.91 | 0.0000 | 0.05 | 100.00 |
| (a) line shopping | totals | all ten books | 6h | 0.020 | 2023-24 on | 268 | 138 | 130 | 0 | -5.56 | -1.88 | -11.43 | 8.10 | 0.6263 | -0.00 | 50.40 |
| (a) line shopping | totals | all ten books | 6h | 0.020 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.09 | 100.00 |
| (a) line shopping | totals | all ten books | 6h | 0.030 | 2023-24 on | 134 | 64 | 70 | 0 | -14.57 | -9.71 | -24.52 | 5.49 | 0.8592 | 0.00 | 64.20 |
| (a) line shopping | totals | all ten books | 6h | 0.030 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.09 | 100.00 |
| (a) line shopping | totals | all ten books | 6h | 0.040 | 2023-24 on | 59 | 31 | 28 | 0 | -0.01 | -0.02 | -24.39 | 20.69 | 0.5005 | 0.01 | 72.90 |
| (a) line shopping | totals | all ten books | 6h | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | 6h | 0.050 | 2023-24 on | 12 | 3 | 9 | 0 | -7.02 | -52.39 | -84.36 | -6.59 | 0.9868 | 0.03 | 75.00 |
| (a) line shopping | totals | all ten books | 6h | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | 60m | 0.000 | 2023-24 on | 714 | 362 | 349 | 3 | -21.45 | -2.75 | -8.84 | 2.96 | 0.7682 | -0.01 | 23.20 |
| (a) line shopping | totals | all ten books | 60m | 0.000 | 2022-23 (1-season table) | 9 | 4 | 4 | 1 | -0.30 | -3.47 | -57.14 | 49.49 | 0.5400 | -0.01 | 22.20 |
| (a) line shopping | totals | all ten books | 60m | 0.010 | 2023-24 on | 443 | 223 | 220 | 0 | -18.91 | -3.88 | -10.75 | 3.43 | 0.8114 | -0.01 | 34.30 |
| (a) line shopping | totals | all ten books | 60m | 0.010 | 2022-23 (1-season table) | 2 | 1 | 1 | 0 | -0.10 | -4.55 | -100.00 | 90.91 | 0.5269 | -0.00 | 50.00 |
| (a) line shopping | totals | all ten books | 60m | 0.020 | 2023-24 on | 262 | 132 | 130 | 0 | -11.38 | -3.94 | -12.80 | 5.34 | 0.7585 | -0.00 | 49.60 |
| (a) line shopping | totals | all ten books | 60m | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | 60m | 0.030 | 2023-24 on | 146 | 73 | 73 | 0 | -8.48 | -5.22 | -17.15 | 8.01 | 0.7522 | 0.01 | 71.20 |
| (a) line shopping | totals | all ten books | 60m | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | 60m | 0.040 | 2023-24 on | 77 | 40 | 37 | 0 | -0.93 | -1.10 | -20.68 | 16.92 | 0.5378 | 0.01 | 80.50 |
| (a) line shopping | totals | all ten books | 60m | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | 60m | 0.050 | 2023-24 on | 19 | 11 | 8 | 0 | 2.22 | 10.59 | -20.23 | 49.77 | 0.3100 | 0.02 | 94.70 |
| (a) line shopping | totals | all ten books | 60m | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | close | 0.000 | 2023-24 on | 714 | 353 | 359 | 2 | -41.35 | -5.29 | -11.26 | 1.04 | 0.9170 | -0.01 | 20.30 |
| (a) line shopping | totals | all ten books | close | 0.000 | 2022-23 (1-season table) | 9 | 3 | 6 | 0 | -3.45 | -35.38 | -78.24 | 7.14 | 0.9080 | -0.01 | 22.20 |
| (a) line shopping | totals | all ten books | close | 0.010 | 2023-24 on | 446 | 221 | 225 | 0 | -26.31 | -5.37 | -12.64 | 1.42 | 0.8876 | -0.01 | 31.20 |
| (a) line shopping | totals | all ten books | close | 0.010 | 2022-23 (1-season table) | 1 | 0 | 1 | 0 | -1.10 | -100.00 | -100.00 | -100.00 |  | -0.02 | 0.00 |
| (a) line shopping | totals | all ten books | close | 0.020 | 2023-24 on | 260 | 136 | 124 | 0 | -0.96 | -0.34 | -9.90 | 9.79 | 0.5228 | -0.00 | 48.10 |
| (a) line shopping | totals | all ten books | close | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | close | 0.030 | 2023-24 on | 160 | 86 | 74 | 0 | 3.39 | 1.91 | -9.80 | 13.74 | 0.3964 | 0.00 | 66.20 |
| (a) line shopping | totals | all ten books | close | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | close | 0.040 | 2023-24 on | 81 | 45 | 36 | 0 | 5.34 | 5.99 | -10.56 | 22.57 | 0.2737 | 0.01 | 76.50 |
| (a) line shopping | totals | all ten books | close | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | all ten books | close | 0.050 | 2023-24 on | 18 | 7 | 11 | 0 | -5.07 | -25.64 | -66.70 | 13.63 | 0.8565 | 0.03 | 88.90 |
| (a) line shopping | totals | all ten books | close | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |

### (a) line shopping, totals, consensus over all ten books: cut 0.03 by season

| method | market | consensus | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) line shopping | totals | all ten books | 15utc | 0.030 | 2023 | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.09 | 100.00 |
| (a) line shopping | totals | all ten books | 15utc | 0.030 | 2026 | 125 | 64 | 61 | 0 | -4.38 | -3.13 | -17.01 | 11.93 | 0.6355 | 0.00 | 59.20 |
| (a) line shopping | totals | all ten books | 15utc | 0.030 | 2027 | 14 | 6 | 8 | 0 | -2.81 | -18.29 | -66.57 | 36.40 | 0.7285 | 0.00 | 64.30 |
| (a) line shopping | totals | all ten books | 6h | 0.030 | 2023 | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.09 | 100.00 |
| (a) line shopping | totals | all ten books | 6h | 0.030 | 2026 | 120 | 59 | 61 | 0 | -9.49 | -7.05 | -22.92 | 8.22 | 0.7657 | 0.00 | 62.50 |
| (a) line shopping | totals | all ten books | 6h | 0.030 | 2027 | 14 | 5 | 9 | 0 | -5.08 | -32.94 | -72.23 | 16.19 | 0.8930 | 0.01 | 78.60 |
| (a) line shopping | totals | all ten books | 60m | 0.030 | 2024 | 1 | 0 | 1 | 0 | -1.10 | -100.00 | -100.00 | -100.00 |  | 0.02 | 100.00 |
| (a) line shopping | totals | all ten books | 60m | 0.030 | 2025 | 2 | 2 | 0 | 0 | 2.00 | 90.91 | 90.91 | 90.91 | 0.0000 | -0.02 | 0.00 |
| (a) line shopping | totals | all ten books | 60m | 0.030 | 2026 | 125 | 65 | 60 | 0 | -2.02 | -1.45 | -15.71 | 12.45 | 0.5665 | 0.01 | 72.00 |
| (a) line shopping | totals | all ten books | 60m | 0.030 | 2027 | 18 | 6 | 12 | 0 | -7.36 | -37.21 | -70.41 | 4.62 | 0.9490 | 0.01 | 72.20 |
| (a) line shopping | totals | all ten books | close | 0.030 | 2026 | 144 | 75 | 69 | 0 | -2.03 | -1.27 | -14.31 | 12.07 | 0.5623 | 0.00 | 67.40 |
| (a) line shopping | totals | all ten books | close | 0.030 | 2027 | 16 | 11 | 5 | 0 | 5.42 | 31.22 | 1.35 | 62.22 | 0.0442 | 0.01 | 56.20 |

### (a) line shopping, totals, consensus over decidable only (catalogued): read x cut

| method | market | consensus | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.000 | 2023-24 on | 454 | 228 | 226 | 0 | -20.78 | -4.15 | -11.33 | 3.37 | 0.8215 | -0.01 | 38.50 |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.010 | 2023-24 on | 379 | 187 | 192 | 0 | -24.22 | -5.80 | -13.73 | 1.89 | 0.8916 | -0.01 | 40.10 |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.020 | 2023-24 on | 264 | 134 | 130 | 0 | -9.49 | -3.25 | -12.82 | 6.39 | 0.7152 | -0.00 | 43.90 |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.030 | 2023-24 on | 166 | 83 | 83 | 0 | -9.62 | -5.19 | -16.70 | 6.77 | 0.7687 | 0.00 | 54.80 |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.040 | 2023-24 on | 75 | 36 | 39 | 0 | -6.95 | -8.41 | -27.12 | 9.74 | 0.7656 | 0.00 | 62.70 |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.050 | 2023-24 on | 15 | 6 | 9 | 0 | -3.88 | -23.50 | -61.78 | 14.84 | 0.8431 | 0.01 | 73.30 |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.000 | 2023-24 on | 462 | 232 | 230 | 0 | -21.20 | -4.17 | -11.40 | 3.23 | 0.8307 | -0.01 | 40.90 |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.010 | 2023-24 on | 384 | 186 | 198 | 0 | -31.87 | -7.54 | -15.32 | -0.06 | 0.9496 | -0.00 | 44.00 |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.020 | 2023-24 on | 257 | 129 | 128 | 0 | -12.49 | -4.40 | -15.18 | 5.73 | 0.7571 | -0.00 | 49.40 |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.030 | 2023-24 on | 160 | 75 | 85 | 0 | -20.04 | -11.22 | -23.79 | 2.20 | 0.9189 | 0.00 | 58.80 |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.040 | 2023-24 on | 80 | 41 | 39 | 0 | -2.02 | -2.29 | -20.69 | 14.44 | 0.5836 | 0.01 | 66.20 |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.050 | 2023-24 on | 13 | 3 | 10 | 0 | -8.06 | -55.82 | -86.56 | -12.66 | 0.9923 | 0.02 | 69.20 |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.000 | 2023-24 on | 459 | 230 | 229 | 0 | -22.06 | -4.36 | -11.79 | 2.95 | 0.8375 | -0.01 | 34.20 |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.010 | 2023-24 on | 393 | 195 | 198 | 0 | -22.96 | -5.30 | -13.11 | 2.56 | 0.8730 | -0.01 | 36.90 |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.020 | 2023-24 on | 258 | 127 | 131 | 0 | -17.63 | -6.19 | -15.46 | 3.84 | 0.8546 | -0.00 | 47.70 |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.030 | 2023-24 on | 176 | 83 | 93 | 0 | -20.43 | -10.44 | -23.58 | 2.18 | 0.9118 | 0.00 | 58.50 |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.040 | 2023-24 on | 88 | 41 | 47 | 0 | -10.74 | -11.06 | -28.35 | 6.91 | 0.8479 | 0.01 | 67.00 |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.050 | 2023-24 on | 21 | 10 | 11 | 0 | -1.99 | -8.57 | -38.33 | 21.73 | 0.6771 | 0.01 | 81.00 |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.000 | 2023-24 on | 459 | 229 | 230 | 0 | -24.04 | -4.76 | -11.73 | 2.94 | 0.8547 | -0.01 | 31.20 |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.010 | 2023-24 on | 397 | 196 | 201 | 0 | -25.11 | -5.76 | -13.44 | 2.23 | 0.8831 | -0.01 | 33.50 |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.020 | 2023-24 on | 266 | 139 | 127 | 0 | -1.41 | -0.48 | -9.93 | 9.60 | 0.5313 | -0.00 | 44.00 |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.030 | 2023-24 on | 184 | 95 | 89 | 0 | -3.98 | -1.95 | -13.52 | 10.37 | 0.6066 | 0.00 | 54.30 |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.040 | 2023-24 on | 97 | 50 | 47 | 0 | -1.64 | -1.54 | -16.43 | 13.50 | 0.5660 | 0.01 | 61.90 |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.050 | 2023-24 on | 20 | 8 | 12 | 0 | -5.20 | -23.60 | -54.73 | 8.63 | 0.8874 | 0.02 | 70.00 |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.050 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |

### (a) line shopping, totals, consensus over decidable only (catalogued): cut 0.03 by season

| method | market | consensus | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.030 | 2026 | 145 | 74 | 71 | 0 | -5.44 | -3.35 | -16.52 | 8.98 | 0.6651 | 0.00 | 55.90 |
| (a) line shopping | totals | decidable only (catalogued) | 15utc | 0.030 | 2027 | 21 | 9 | 12 | 0 | -4.18 | -18.24 | -48.41 | 14.80 | 0.8255 | -0.00 | 47.60 |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.030 | 2026 | 141 | 69 | 72 | 0 | -11.59 | -7.34 | -20.87 | 7.02 | 0.8007 | 0.00 | 57.40 |
| (a) line shopping | totals | decidable only (catalogued) | 6h | 0.030 | 2027 | 19 | 6 | 13 | 0 | -8.45 | -40.64 | -70.82 | -4.79 | 0.9717 | 0.01 | 68.40 |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.030 | 2026 | 147 | 71 | 76 | 0 | -13.72 | -8.36 | -22.10 | 6.51 | 0.8347 | 0.00 | 59.90 |
| (a) line shopping | totals | decidable only (catalogued) | 60m | 0.030 | 2027 | 29 | 12 | 17 | 0 | -6.71 | -21.23 | -50.93 | 8.08 | 0.8783 | 0.01 | 51.70 |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.030 | 2026 | 162 | 83 | 79 | 0 | -4.94 | -2.74 | -14.62 | 9.89 | 0.6433 | 0.00 | 57.40 |
| (a) line shopping | totals | decidable only (catalogued) | close | 0.030 | 2027 | 22 | 12 | 10 | 0 | 0.96 | 4.00 | -25.95 | 33.47 | 0.4110 | -0.00 | 31.80 |

### (b) moneyline against the same book's spread, -200 floor: read x cut

| method | floor | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) moneyline vs own spread | -200 floor | 15utc | 0.000 | 2023-24 on | 315 | 169 | 146 | 0 | -26.69 | -6.10 | -13.58 | 1.53 | 0.9073 | -0.02 | 17.50 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.000 | 2022-23 (1-season table) | 123 | 65 | 58 | 0 | -0.05 | -0.03 | -13.74 | 13.53 | 0.5014 | -0.01 | 11.40 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.005 | 2023-24 on | 185 | 94 | 91 | 0 | -29.21 | -11.41 | -22.25 | -1.67 | 0.9614 | -0.01 | 23.20 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.005 | 2022-23 (1-season table) | 114 | 61 | 53 | 0 | 1.60 | 1.03 | -12.25 | 14.91 | 0.4514 | -0.01 | 11.40 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.010 | 2023-24 on | 86 | 44 | 42 | 0 | -13.15 | -11.00 | -25.03 | 3.49 | 0.8889 | -0.01 | 27.90 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.010 | 2022-23 (1-season table) | 108 | 60 | 48 | 0 | 7.20 | 4.87 | -8.34 | 19.84 | 0.2857 | -0.01 | 12.00 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.015 | 2023-24 on | 31 | 19 | 12 | 0 | 2.38 | 5.65 | -19.45 | 32.13 | 0.3591 | -0.01 | 38.70 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.015 | 2022-23 (1-season table) | 90 | 54 | 36 | 0 | 16.35 | 13.20 | -1.16 | 28.28 | 0.0732 | -0.01 | 14.40 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.020 | 2023-24 on | 14 | 9 | 5 | 0 | 2.12 | 10.86 | -30.94 | 55.33 | 0.3388 | -0.01 | 35.70 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.020 | 2022-23 (1-season table) | 72 | 45 | 27 | 0 | 20.10 | 21.18 | 2.64 | 38.09 | 0.0235 | -0.01 | 15.30 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.025 | 2023-24 on | 7 | 6 | 1 | 0 | 5.27 | 55.36 | 3.13 | 98.84 | 0.0267 | -0.02 | 28.60 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.025 | 2022-23 (1-season table) | 46 | 30 | 16 | 0 | 16.60 | 27.57 | 1.33 | 55.58 | 0.0472 | -0.01 | 10.90 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.030 | 2023-24 on | 5 | 5 | 0 | 0 | 5.00 | 71.02 | 60.61 | 79.74 | 0.0000 | -0.02 | 20.00 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.030 | 2022-23 (1-season table) | 24 | 16 | 8 | 0 | 6.00 | 17.83 | -8.29 | 43.39 | 0.1306 | -0.01 | 20.80 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.000 | 2023-24 on | 313 | 166 | 147 | 0 | -31.25 | -7.21 | -14.94 | 0.61 | 0.9341 | -0.02 | 22.00 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.000 | 2022-23 (1-season table) | 126 | 66 | 60 | 0 | -3.25 | -1.90 | -14.19 | 11.09 | 0.5960 | -0.02 | 19.80 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.005 | 2023-24 on | 182 | 96 | 86 | 0 | -20.21 | -8.02 | -17.58 | 1.69 | 0.9149 | -0.01 | 25.80 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.005 | 2022-23 (1-season table) | 109 | 62 | 47 | 0 | 9.00 | 6.06 | -6.72 | 18.43 | 0.2166 | -0.01 | 21.10 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.010 | 2023-24 on | 80 | 46 | 34 | 0 | -1.98 | -1.79 | -18.26 | 13.96 | 0.5734 | -0.01 | 32.50 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.010 | 2022-23 (1-season table) | 107 | 61 | 46 | 0 | 9.20 | 6.29 | -6.46 | 19.91 | 0.2167 | -0.01 | 21.50 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.015 | 2023-24 on | 26 | 18 | 8 | 0 | 6.80 | 19.19 | -7.84 | 46.67 | 0.1249 | -0.01 | 42.30 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.015 | 2022-23 (1-season table) | 95 | 54 | 41 | 0 | 9.35 | 7.23 | -7.00 | 20.95 | 0.2026 | -0.01 | 24.20 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.020 | 2023-24 on | 18 | 12 | 6 | 0 | 3.77 | 15.36 | -20.08 | 54.13 | 0.2460 | -0.01 | 44.40 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.020 | 2022-23 (1-season table) | 70 | 41 | 29 | 0 | 13.20 | 14.62 | -6.14 | 32.65 | 0.1127 | -0.01 | 24.30 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.025 | 2023-24 on | 11 | 10 | 1 | 0 | 9.27 | 63.41 | 30.41 | 91.58 | 0.0003 | -0.01 | 36.40 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.025 | 2022-23 (1-season table) | 44 | 27 | 17 | 0 | 11.45 | 20.18 | -4.55 | 42.61 | 0.0823 | -0.01 | 20.50 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.030 | 2023-24 on | 6 | 6 | 0 | 0 | 6.00 | 72.29 | 64.52 | 80.00 | 0.0000 | -0.02 | 33.30 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.030 | 2022-23 (1-season table) | 25 | 14 | 11 | 0 | 3.50 | 10.56 | -26.74 | 48.55 | 0.3214 | -0.01 | 24.00 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.000 | 2023-24 on | 308 | 160 | 148 | 0 | -34.60 | -8.17 | -15.74 | -0.49 | 0.9576 | -0.02 | 12.30 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.000 | 2022-23 (1-season table) | 126 | 67 | 59 | 0 | 0.30 | 0.17 | -12.42 | 12.92 | 0.4913 | -0.02 | 4.00 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.005 | 2023-24 on | 185 | 88 | 97 | 0 | -39.45 | -15.76 | -26.84 | -5.87 | 0.9925 | -0.01 | 14.10 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.005 | 2022-23 (1-season table) | 109 | 59 | 50 | 0 | 3.95 | 2.65 | -9.94 | 17.28 | 0.3758 | -0.02 | 4.60 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.010 | 2023-24 on | 93 | 42 | 51 | 0 | -25.36 | -20.05 | -35.14 | -3.26 | 0.9814 | -0.01 | 14.00 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.010 | 2022-23 (1-season table) | 97 | 56 | 41 | 0 | 10.75 | 8.00 | -6.75 | 22.99 | 0.1889 | -0.02 | 5.20 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.015 | 2023-24 on | 33 | 16 | 17 | 0 | -6.13 | -13.30 | -37.29 | 11.66 | 0.8114 | -0.01 | 24.20 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.015 | 2022-23 (1-season table) | 80 | 46 | 34 | 0 | 7.90 | 7.08 | -8.31 | 24.51 | 0.2368 | -0.02 | 5.00 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.020 | 2023-24 on | 18 | 9 | 9 | 0 | -2.21 | -8.96 | -46.14 | 26.50 | 0.6587 | -0.01 | 33.30 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.020 | 2022-23 (1-season table) | 58 | 35 | 23 | 0 | 10.65 | 13.30 | -6.56 | 32.95 | 0.1360 | -0.02 | 6.90 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.025 | 2023-24 on | 10 | 7 | 3 | 0 | 4.07 | 29.51 | -16.80 | 67.54 | 0.1241 | -0.00 | 50.00 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.025 | 2022-23 (1-season table) | 44 | 26 | 18 | 0 | 9.30 | 15.91 | -8.53 | 40.70 | 0.1471 | -0.02 | 9.10 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.030 | 2023-24 on | 3 | 3 | 0 | 0 | 3.00 | 65.65 | 56.07 | 79.16 | 0.0000 | -0.00 | 33.30 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.030 | 2022-23 (1-season table) | 24 | 13 | 11 | 0 | 3.50 | 11.15 | -28.37 | 50.68 | 0.3260 | -0.02 | 8.30 |
| (b) moneyline vs own spread | -200 floor | close | 0.000 | 2023-24 on | 314 | 168 | 146 | 0 | -24.69 | -5.68 | -12.96 | 1.79 | 0.8956 | -0.02 | 6.10 |
| (b) moneyline vs own spread | -200 floor | close | 0.000 | 2022-23 (1-season table) | 124 | 68 | 56 | 0 | 6.70 | 3.99 | -8.85 | 17.06 | 0.3104 | -0.02 | 1.60 |
| (b) moneyline vs own spread | -200 floor | close | 0.005 | 2023-24 on | 192 | 100 | 92 | 0 | -18.79 | -7.20 | -15.96 | 2.14 | 0.9051 | -0.02 | 6.80 |
| (b) moneyline vs own spread | -200 floor | close | 0.005 | 2022-23 (1-season table) | 113 | 63 | 50 | 0 | 9.05 | 5.92 | -8.10 | 19.78 | 0.2449 | -0.02 | 1.80 |
| (b) moneyline vs own spread | -200 floor | close | 0.010 | 2023-24 on | 100 | 51 | 49 | 0 | -9.95 | -7.40 | -22.65 | 6.45 | 0.7986 | -0.02 | 9.00 |
| (b) moneyline vs own spread | -200 floor | close | 0.010 | 2022-23 (1-season table) | 105 | 60 | 45 | 0 | 11.75 | 8.26 | -5.55 | 24.76 | 0.1831 | -0.02 | 1.90 |
| (b) moneyline vs own spread | -200 floor | close | 0.015 | 2023-24 on | 44 | 23 | 21 | 0 | -3.53 | -5.96 | -27.91 | 15.77 | 0.6693 | -0.01 | 18.20 |
| (b) moneyline vs own spread | -200 floor | close | 0.015 | 2022-23 (1-season table) | 86 | 49 | 37 | 0 | 8.00 | 6.72 | -9.47 | 23.02 | 0.2506 | -0.02 | 2.30 |
| (b) moneyline vs own spread | -200 floor | close | 0.020 | 2023-24 on | 20 | 11 | 9 | 0 | 0.14 | 0.52 | -31.23 | 35.85 | 0.4901 | -0.01 | 35.00 |
| (b) moneyline vs own spread | -200 floor | close | 0.020 | 2022-23 (1-season table) | 63 | 36 | 27 | 0 | 6.40 | 7.43 | -11.18 | 26.64 | 0.2544 | -0.02 | 3.20 |
| (b) moneyline vs own spread | -200 floor | close | 0.025 | 2023-24 on | 15 | 9 | 6 | 0 | 1.90 | 9.25 | -27.50 | 43.66 | 0.3359 | -0.01 | 40.00 |
| (b) moneyline vs own spread | -200 floor | close | 0.025 | 2022-23 (1-season table) | 42 | 24 | 18 | 0 | 6.60 | 11.92 | -14.33 | 36.20 | 0.2206 | -0.02 | 2.40 |
| (b) moneyline vs own spread | -200 floor | close | 0.030 | 2023-24 on | 6 | 5 | 1 | 0 | 3.75 | 44.59 | -8.32 | 75.95 | 0.0296 | -0.03 | 16.70 |
| (b) moneyline vs own spread | -200 floor | close | 0.030 | 2022-23 (1-season table) | 26 | 14 | 12 | 0 | 3.90 | 11.35 | -32.13 | 50.68 | 0.3245 | -0.02 | 3.80 |

### (b) -200 floor: cut 0.01 by season

| method | floor | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) moneyline vs own spread | -200 floor | 15utc | 0.010 | 2023 | 108 | 60 | 48 | 0 | 7.20 | 4.87 | -8.34 | 19.84 | 0.2857 | -0.01 | 12.00 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.010 | 2024 | 31 | 17 | 14 | 0 | -3.58 | -8.01 | -30.43 | 13.80 | 0.7206 | -0.01 | 16.10 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.010 | 2025 | 21 | 11 | 10 | 0 | -2.95 | -9.68 | -37.56 | 18.69 | 0.7091 | -0.01 | 47.60 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.010 | 2026 | 26 | 11 | 15 | 0 | -7.62 | -22.82 | -51.76 | 9.52 | 0.8861 | -0.01 | 26.90 |
| (b) moneyline vs own spread | -200 floor | 15utc | 0.010 | 2027 | 8 | 5 | 3 | 0 | 1.00 | 9.06 | -50.53 | 53.30 | 0.3864 | -0.02 | 25.00 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.010 | 2023 | 107 | 61 | 46 | 0 | 9.20 | 6.29 | -6.46 | 19.91 | 0.2167 | -0.01 | 21.50 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.010 | 2024 | 29 | 16 | 13 | 0 | -3.63 | -8.78 | -29.77 | 16.53 | 0.7358 | -0.02 | 20.70 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.010 | 2025 | 19 | 11 | 8 | 0 | -0.28 | -1.02 | -34.00 | 34.10 | 0.5200 | -0.01 | 42.10 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.010 | 2026 | 27 | 15 | 12 | 0 | -0.45 | -1.28 | -27.93 | 26.72 | 0.5313 | -0.01 | 40.70 |
| (b) moneyline vs own spread | -200 floor | 6h | 0.010 | 2027 | 5 | 4 | 1 | 0 | 2.38 | 35.21 | -38.39 | 79.38 | 0.1631 | -0.02 | 20.00 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.010 | 2023 | 97 | 56 | 41 | 0 | 10.75 | 8.00 | -6.75 | 22.99 | 0.1889 | -0.02 | 5.20 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.010 | 2024 | 26 | 11 | 15 | 0 | -10.60 | -28.47 | -58.55 | 1.23 | 0.9419 | -0.02 | 3.80 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.010 | 2025 | 21 | 9 | 12 | 0 | -6.12 | -21.61 | -54.39 | 10.63 | 0.8716 | -0.02 | 14.30 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.010 | 2026 | 36 | 16 | 20 | 0 | -10.11 | -20.70 | -45.84 | 4.14 | 0.9089 | -0.01 | 16.70 |
| (b) moneyline vs own spread | -200 floor | 60m | 0.010 | 2027 | 10 | 6 | 4 | 0 | 1.47 | 12.18 | -35.86 | 52.55 | 0.3322 | -0.01 | 30.00 |
| (b) moneyline vs own spread | -200 floor | close | 0.010 | 2023 | 105 | 60 | 45 | 0 | 11.75 | 8.26 | -5.55 | 24.76 | 0.1831 | -0.02 | 1.90 |
| (b) moneyline vs own spread | -200 floor | close | 0.010 | 2024 | 33 | 20 | 13 | 0 | 2.31 | 4.93 | -20.05 | 29.58 | 0.3710 | -0.02 | 3.00 |
| (b) moneyline vs own spread | -200 floor | close | 0.010 | 2025 | 21 | 10 | 11 | 0 | -2.62 | -9.37 | -41.74 | 21.77 | 0.6899 | -0.02 | 9.50 |
| (b) moneyline vs own spread | -200 floor | close | 0.010 | 2026 | 39 | 17 | 22 | 0 | -10.26 | -20.05 | -39.66 | -0.13 | 0.9489 | -0.02 | 12.80 |
| (b) moneyline vs own spread | -200 floor | close | 0.010 | 2027 | 7 | 4 | 3 | 0 | 0.62 | 7.32 | -45.71 | 57.47 | 0.4154 | -0.01 | 14.30 |

### (b) moneyline against the same book's spread, no floor: read x cut

| method | floor | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) moneyline vs own spread | no floor | 15utc | 0.000 | 2023-24 on | 464 | 280 | 184 | 0 | -39.73 | -4.62 | -10.04 | 0.27 | 0.9305 | -0.01 | 20.30 |
| (b) moneyline vs own spread | no floor | 15utc | 0.000 | 2022-23 (1-season table) | 193 | 113 | 80 | 0 | -10.10 | -2.88 | -11.61 | 5.91 | 0.7057 | -0.01 | 10.90 |
| (b) moneyline vs own spread | no floor | 15utc | 0.005 | 2023-24 on | 288 | 171 | 117 | 0 | -40.67 | -7.35 | -13.63 | -0.43 | 0.9651 | -0.01 | 25.00 |
| (b) moneyline vs own spread | no floor | 15utc | 0.005 | 2022-23 (1-season table) | 162 | 94 | 68 | 0 | -5.24 | -1.86 | -12.07 | 7.85 | 0.6204 | -0.01 | 11.10 |
| (b) moneyline vs own spread | no floor | 15utc | 0.010 | 2023-24 on | 149 | 92 | 57 | 0 | -18.04 | -5.95 | -15.30 | 2.57 | 0.8640 | -0.01 | 28.20 |
| (b) moneyline vs own spread | no floor | 15utc | 0.010 | 2022-23 (1-season table) | 137 | 79 | 58 | 0 | 0.54 | 0.24 | -11.16 | 10.99 | 0.4857 | -0.01 | 12.40 |
| (b) moneyline vs own spread | no floor | 15utc | 0.015 | 2023-24 on | 68 | 47 | 21 | 0 | -2.46 | -1.63 | -14.17 | 11.57 | 0.5838 | -0.01 | 33.80 |
| (b) moneyline vs own spread | no floor | 15utc | 0.015 | 2022-23 (1-season table) | 101 | 60 | 41 | 0 | 9.34 | 6.14 | -7.97 | 20.61 | 0.2387 | -0.01 | 13.90 |
| (b) moneyline vs own spread | no floor | 15utc | 0.020 | 2023-24 on | 38 | 27 | 11 | 0 | -1.31 | -1.43 | -17.77 | 14.68 | 0.5578 | -0.01 | 36.80 |
| (b) moneyline vs own spread | no floor | 15utc | 0.020 | 2022-23 (1-season table) | 79 | 48 | 31 | 0 | 12.75 | 11.34 | -5.85 | 27.85 | 0.1398 | -0.01 | 15.20 |
| (b) moneyline vs own spread | no floor | 15utc | 0.025 | 2023-24 on | 20 | 15 | 5 | 0 | 0.95 | 1.96 | -20.73 | 25.83 | 0.4456 | -0.01 | 40.00 |
| (b) moneyline vs own spread | no floor | 15utc | 0.025 | 2022-23 (1-season table) | 48 | 31 | 17 | 0 | 15.10 | 23.23 | -1.62 | 48.51 | 0.0660 | -0.01 | 12.50 |
| (b) moneyline vs own spread | no floor | 15utc | 0.030 | 2023-24 on | 10 | 7 | 3 | 0 | -2.00 | -9.15 | -43.26 | 31.50 | 0.6526 | -0.01 | 40.00 |
| (b) moneyline vs own spread | no floor | 15utc | 0.030 | 2022-23 (1-season table) | 25 | 17 | 8 | 0 | 7.00 | 19.47 | -5.57 | 43.39 | 0.0989 | -0.01 | 24.00 |
| (b) moneyline vs own spread | no floor | 6h | 0.000 | 2023-24 on | 478 | 291 | 187 | 0 | -40.68 | -4.54 | -9.99 | 0.21 | 0.9248 | -0.01 | 24.10 |
| (b) moneyline vs own spread | no floor | 6h | 0.000 | 2022-23 (1-season table) | 196 | 114 | 82 | 0 | -14.92 | -4.19 | -12.74 | 4.27 | 0.7915 | -0.01 | 21.40 |
| (b) moneyline vs own spread | no floor | 6h | 0.005 | 2023-24 on | 299 | 182 | 117 | 0 | -38.49 | -6.57 | -12.84 | -0.79 | 0.9578 | -0.01 | 28.80 |
| (b) moneyline vs own spread | no floor | 6h | 0.005 | 2022-23 (1-season table) | 158 | 98 | 60 | 0 | 9.84 | 3.54 | -5.60 | 12.46 | 0.2566 | -0.01 | 22.20 |
| (b) moneyline vs own spread | no floor | 6h | 0.010 | 2023-24 on | 146 | 97 | 49 | 0 | -3.38 | -1.13 | -10.69 | 7.94 | 0.5793 | -0.01 | 36.30 |
| (b) moneyline vs own spread | no floor | 6h | 0.010 | 2022-23 (1-season table) | 138 | 82 | 56 | 0 | 3.81 | 1.68 | -9.43 | 12.93 | 0.4000 | -0.01 | 22.50 |
| (b) moneyline vs own spread | no floor | 6h | 0.015 | 2023-24 on | 69 | 51 | 18 | 0 | 3.48 | 2.18 | -11.57 | 13.79 | 0.3912 | -0.01 | 39.10 |
| (b) moneyline vs own spread | no floor | 6h | 0.015 | 2022-23 (1-season table) | 106 | 61 | 45 | 0 | 6.84 | 4.35 | -8.22 | 16.84 | 0.2856 | -0.01 | 23.60 |
| (b) moneyline vs own spread | no floor | 6h | 0.020 | 2023-24 on | 45 | 32 | 13 | 0 | -1.14 | -1.09 | -17.09 | 14.04 | 0.5465 | -0.01 | 44.40 |
| (b) moneyline vs own spread | no floor | 6h | 0.020 | 2022-23 (1-season table) | 74 | 44 | 30 | 0 | 13.65 | 13.60 | -5.16 | 31.47 | 0.1121 | -0.01 | 25.70 |
| (b) moneyline vs own spread | no floor | 6h | 0.025 | 2023-24 on | 27 | 22 | 5 | 0 | 7.04 | 11.27 | -7.60 | 30.60 | 0.1652 | -0.00 | 48.10 |
| (b) moneyline vs own spread | no floor | 6h | 0.025 | 2022-23 (1-season table) | 45 | 28 | 17 | 0 | 12.45 | 21.08 | -2.13 | 41.55 | 0.0610 | -0.01 | 22.20 |
| (b) moneyline vs own spread | no floor | 6h | 0.030 | 2023-24 on | 13 | 10 | 3 | 0 | 0.72 | 2.47 | -26.16 | 35.91 | 0.4495 | -0.00 | 53.80 |
| (b) moneyline vs own spread | no floor | 6h | 0.030 | 2022-23 (1-season table) | 26 | 15 | 11 | 0 | 4.50 | 12.69 | -23.07 | 47.55 | 0.2808 | -0.01 | 26.90 |
| (b) moneyline vs own spread | no floor | 60m | 0.000 | 2023-24 on | 484 | 293 | 191 | 0 | -44.82 | -4.88 | -10.01 | 0.24 | 0.9369 | -0.01 | 15.90 |
| (b) moneyline vs own spread | no floor | 60m | 0.000 | 2022-23 (1-season table) | 189 | 110 | 79 | 0 | -7.80 | -2.30 | -10.66 | 6.44 | 0.6698 | -0.02 | 5.30 |
| (b) moneyline vs own spread | no floor | 60m | 0.005 | 2023-24 on | 304 | 179 | 125 | 0 | -43.41 | -7.37 | -14.19 | -1.04 | 0.9688 | -0.01 | 18.80 |
| (b) moneyline vs own spread | no floor | 60m | 0.005 | 2022-23 (1-season table) | 155 | 90 | 65 | 0 | -3.63 | -1.34 | -11.14 | 9.08 | 0.5867 | -0.02 | 6.50 |
| (b) moneyline vs own spread | no floor | 60m | 0.010 | 2023-24 on | 168 | 101 | 67 | 0 | -23.89 | -6.94 | -16.37 | 1.63 | 0.8985 | -0.01 | 19.60 |
| (b) moneyline vs own spread | no floor | 60m | 0.010 | 2022-23 (1-season table) | 125 | 74 | 51 | 0 | 3.39 | 1.64 | -10.55 | 13.20 | 0.4078 | -0.02 | 7.20 |
| (b) moneyline vs own spread | no floor | 60m | 0.015 | 2023-24 on | 77 | 53 | 24 | 0 | 3.07 | 1.75 | -10.19 | 12.85 | 0.4029 | -0.01 | 28.60 |
| (b) moneyline vs own spread | no floor | 60m | 0.015 | 2022-23 (1-season table) | 88 | 51 | 37 | 0 | 5.43 | 4.12 | -10.66 | 19.77 | 0.3239 | -0.02 | 4.50 |
| (b) moneyline vs own spread | no floor | 60m | 0.020 | 2023-24 on | 44 | 32 | 12 | 0 | 8.36 | 8.19 | -7.27 | 21.29 | 0.1748 | -0.01 | 34.10 |
| (b) moneyline vs own spread | no floor | 60m | 0.020 | 2022-23 (1-season table) | 61 | 37 | 24 | 0 | 10.10 | 11.54 | -9.05 | 31.49 | 0.1679 | -0.02 | 6.60 |
| (b) moneyline vs own spread | no floor | 60m | 0.025 | 2023-24 on | 23 | 17 | 6 | 0 | 3.73 | 7.13 | -14.74 | 28.86 | 0.2946 | -0.00 | 43.50 |
| (b) moneyline vs own spread | no floor | 60m | 0.025 | 2022-23 (1-season table) | 44 | 26 | 18 | 0 | 9.30 | 15.91 | -8.53 | 40.70 | 0.1471 | -0.02 | 9.10 |
| (b) moneyline vs own spread | no floor | 60m | 0.030 | 2023-24 on | 12 | 10 | 2 | 0 | 3.20 | 10.29 | -14.74 | 36.45 | 0.2591 | -0.00 | 41.70 |
| (b) moneyline vs own spread | no floor | 60m | 0.030 | 2022-23 (1-season table) | 24 | 13 | 11 | 0 | 3.50 | 11.15 | -28.37 | 50.68 | 0.3260 | -0.02 | 8.30 |
| (b) moneyline vs own spread | no floor | close | 0.000 | 2023-24 on | 484 | 295 | 189 | 0 | -36.16 | -3.98 | -8.96 | 0.63 | 0.9110 | -0.02 | 11.40 |
| (b) moneyline vs own spread | no floor | close | 0.000 | 2022-23 (1-season table) | 192 | 113 | 79 | 0 | -6.41 | -1.86 | -10.55 | 6.55 | 0.6424 | -0.02 | 3.10 |
| (b) moneyline vs own spread | no floor | close | 0.005 | 2023-24 on | 314 | 189 | 125 | 0 | -34.12 | -5.66 | -11.82 | 0.67 | 0.9337 | -0.01 | 13.70 |
| (b) moneyline vs own spread | no floor | close | 0.005 | 2022-23 (1-season table) | 166 | 97 | 69 | 0 | -4.50 | -1.54 | -10.69 | 7.52 | 0.6091 | -0.02 | 3.60 |
| (b) moneyline vs own spread | no floor | close | 0.010 | 2023-24 on | 182 | 111 | 71 | 0 | -21.80 | -5.88 | -13.55 | 1.94 | 0.8905 | -0.01 | 15.90 |
| (b) moneyline vs own spread | no floor | close | 0.010 | 2022-23 (1-season table) | 131 | 76 | 55 | 0 | 1.97 | 0.94 | -10.37 | 13.05 | 0.4483 | -0.02 | 3.80 |
| (b) moneyline vs own spread | no floor | close | 0.015 | 2023-24 on | 94 | 61 | 33 | 0 | -7.55 | -3.66 | -15.05 | 9.06 | 0.6968 | -0.01 | 23.40 |
| (b) moneyline vs own spread | no floor | close | 0.015 | 2022-23 (1-season table) | 94 | 55 | 39 | 0 | 8.85 | 6.35 | -9.13 | 20.97 | 0.2404 | -0.02 | 2.10 |
| (b) moneyline vs own spread | no floor | close | 0.020 | 2023-24 on | 52 | 38 | 14 | 0 | 7.39 | 6.05 | -7.09 | 18.45 | 0.2113 | -0.01 | 34.60 |
| (b) moneyline vs own spread | no floor | close | 0.020 | 2022-23 (1-season table) | 66 | 38 | 28 | 0 | 6.10 | 6.53 | -10.46 | 25.27 | 0.2730 | -0.02 | 3.00 |
| (b) moneyline vs own spread | no floor | close | 0.025 | 2023-24 on | 27 | 17 | 10 | 0 | -3.15 | -5.64 | -28.53 | 16.70 | 0.6596 | -0.00 | 44.40 |
| (b) moneyline vs own spread | no floor | close | 0.025 | 2022-23 (1-season table) | 42 | 24 | 18 | 0 | 6.60 | 11.92 | -14.33 | 36.20 | 0.2206 | -0.02 | 2.40 |
| (b) moneyline vs own spread | no floor | close | 0.030 | 2023-24 on | 14 | 10 | 4 | 0 | -0.98 | -3.03 | -34.73 | 27.34 | 0.5660 | -0.01 | 35.70 |
| (b) moneyline vs own spread | no floor | close | 0.030 | 2022-23 (1-season table) | 26 | 14 | 12 | 0 | 3.90 | 11.35 | -32.13 | 50.68 | 0.3245 | -0.02 | 3.80 |

### (b) no floor: cut 0.01 by season

| method | floor | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) moneyline vs own spread | no floor | 15utc | 0.010 | 2023 | 137 | 79 | 58 | 0 | 0.54 | 0.24 | -11.16 | 10.99 | 0.4857 | -0.01 | 12.40 |
| (b) moneyline vs own spread | no floor | 15utc | 0.010 | 2024 | 35 | 18 | 17 | 0 | -9.58 | -17.68 | -40.38 | 3.39 | 0.9066 | -0.01 | 20.00 |
| (b) moneyline vs own spread | no floor | 15utc | 0.010 | 2025 | 27 | 15 | 12 | 0 | -5.53 | -11.56 | -36.68 | 12.63 | 0.7736 | -0.01 | 40.70 |
| (b) moneyline vs own spread | no floor | 15utc | 0.010 | 2026 | 64 | 42 | 22 | 0 | -4.62 | -3.15 | -16.33 | 8.95 | 0.6598 | -0.01 | 31.20 |
| (b) moneyline vs own spread | no floor | 15utc | 0.010 | 2027 | 23 | 17 | 6 | 0 | 1.69 | 3.13 | -19.41 | 24.72 | 0.4079 | -0.02 | 17.40 |
| (b) moneyline vs own spread | no floor | 6h | 0.010 | 2023 | 138 | 82 | 56 | 0 | 3.81 | 1.68 | -9.43 | 12.93 | 0.4000 | -0.01 | 22.50 |
| (b) moneyline vs own spread | no floor | 6h | 0.010 | 2024 | 33 | 18 | 15 | 0 | -6.58 | -13.06 | -34.23 | 10.69 | 0.8352 | -0.01 | 27.30 |
| (b) moneyline vs own spread | no floor | 6h | 0.010 | 2025 | 24 | 14 | 10 | 0 | -2.69 | -6.54 | -33.72 | 17.59 | 0.6609 | -0.00 | 45.80 |
| (b) moneyline vs own spread | no floor | 6h | 0.010 | 2026 | 71 | 51 | 20 | 0 | 3.56 | 2.15 | -9.90 | 14.78 | 0.3873 | -0.01 | 40.80 |
| (b) moneyline vs own spread | no floor | 6h | 0.010 | 2027 | 18 | 14 | 4 | 0 | 2.32 | 5.47 | -21.12 | 28.80 | 0.3592 | -0.02 | 22.20 |
| (b) moneyline vs own spread | no floor | 60m | 0.010 | 2023 | 125 | 74 | 51 | 0 | 3.39 | 1.64 | -10.55 | 13.20 | 0.4078 | -0.02 | 7.20 |
| (b) moneyline vs own spread | no floor | 60m | 0.010 | 2024 | 30 | 14 | 16 | 0 | -10.92 | -22.85 | -51.21 | 2.95 | 0.9159 | -0.02 | 10.00 |
| (b) moneyline vs own spread | no floor | 60m | 0.010 | 2025 | 29 | 13 | 16 | 0 | -14.28 | -27.88 | -51.37 | -4.17 | 0.9718 | -0.01 | 10.30 |
| (b) moneyline vs own spread | no floor | 60m | 0.010 | 2026 | 78 | 52 | 26 | 0 | 1.35 | 0.78 | -11.36 | 11.62 | 0.4545 | -0.01 | 25.60 |
| (b) moneyline vs own spread | no floor | 60m | 0.010 | 2027 | 31 | 22 | 9 | 0 | -0.02 | -0.03 | -18.56 | 19.65 | 0.5011 | -0.01 | 22.60 |
| (b) moneyline vs own spread | no floor | close | 0.010 | 2023 | 131 | 76 | 55 | 0 | 1.97 | 0.94 | -10.37 | 13.05 | 0.4483 | -0.02 | 3.80 |
| (b) moneyline vs own spread | no floor | close | 0.010 | 2024 | 41 | 25 | 16 | 0 | -1.91 | -2.76 | -24.33 | 17.84 | 0.5859 | -0.02 | 7.30 |
| (b) moneyline vs own spread | no floor | close | 0.010 | 2025 | 31 | 15 | 16 | 0 | -12.34 | -21.85 | -45.26 | -0.83 | 0.9487 | -0.01 | 6.50 |
| (b) moneyline vs own spread | no floor | close | 0.010 | 2026 | 82 | 52 | 30 | 0 | -4.96 | -2.79 | -13.17 | 7.35 | 0.6671 | -0.01 | 23.20 |
| (b) moneyline vs own spread | no floor | close | 0.010 | 2027 | 28 | 19 | 9 | 0 | -2.59 | -3.85 | -23.96 | 16.74 | 0.6186 | -0.01 | 17.90 |

### (b) no floor, 15utc, cut 0.01, 2023-24 on: by price band

| band | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| <=-500 | 5 | 5 | 0 | 0 | 2.21 | 14.71 | 12.40 | 17.13 | 0.0000 | -0.00 | 20.00 |
| -500..-200 | 58 | 43 | 15 | 0 | -7.09 | -4.21 | -16.62 | 8.02 | 0.7117 | -0.01 | 29.30 |
| -200..+100 | 84 | 43 | 41 | 0 | -13.90 | -11.82 | -27.58 | 1.94 | 0.9062 | -0.01 | 27.40 |
| +100..+300 | 1 | 1 | 0 | 0 | 1.75 | 175.00 | 175.00 | 175.00 |  | -0.02 | 0.00 |
| >+300 | 1 | 0 | 1 | 0 | -1.00 | -100.00 | -100.00 | -100.00 |  | 0.04 | 100.00 |

### (d) sharp vs soft, h2h: read x cut

| method | market | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (d) sharp vs soft | h2h | 15utc | 0.000 | 2023-24 on | 95 | 43 | 52 | 0 | -2.29 | -2.00 | -18.96 | 15.93 | 0.5755 | 0.00 | 56.80 |
| (d) sharp vs soft | h2h | 15utc | 0.000 | 2022-23 (1-season table) | 3 | 2 | 1 | 0 | 1.00 | 22.73 | -27.40 | 59.41 | 0.2758 | -0.00 | 66.70 |
| (d) sharp vs soft | h2h | 15utc | 0.010 | 2023-24 on | 18 | 11 | 7 | 0 | 3.50 | 14.41 | -18.11 | 42.11 | 0.2077 | 0.01 | 72.20 |
| (d) sharp vs soft | h2h | 15utc | 0.010 | 2022-23 (1-season table) | 2 | 1 | 1 | 0 | 0.00 | 0.00 | -100.00 | 60.61 | 0.5000 | 0.01 | 100.00 |
| (d) sharp vs soft | h2h | 15utc | 0.020 | 2023-24 on | 5 | 3 | 2 | 0 | 1.00 | 15.15 | -55.56 | 63.29 | 0.3232 | 0.01 | 80.00 |
| (d) sharp vs soft | h2h | 15utc | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 15utc | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 15utc | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 15utc | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 15utc | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 6h | 0.000 | 2023-24 on | 78 | 44 | 34 | 0 | 18.52 | 19.06 | -1.91 | 43.16 | 0.0836 | 0.01 | 61.50 |
| (d) sharp vs soft | h2h | 6h | 0.000 | 2022-23 (1-season table) | 2 | 2 | 0 | 0 | 5.00 | 188.68 | 60.61 | 400.00 | 0.0598 | 0.01 | 100.00 |
| (d) sharp vs soft | h2h | 6h | 0.010 | 2023-24 on | 25 | 14 | 11 | 0 | 5.43 | 16.94 | -18.83 | 57.06 | 0.2269 | 0.02 | 80.00 |
| (d) sharp vs soft | h2h | 6h | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 6h | 0.020 | 2023-24 on | 7 | 2 | 5 | 0 | -2.53 | -27.71 | -100.00 | 60.98 | 0.7171 | 0.03 | 100.00 |
| (d) sharp vs soft | h2h | 6h | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 6h | 0.030 | 2023-24 on | 1 | 0 | 1 | 0 | -1.00 | -100.00 | -100.00 | -100.00 |  | 0.03 | 100.00 |
| (d) sharp vs soft | h2h | 6h | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 6h | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 6h | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 60m | 0.000 | 2023-24 on | 98 | 37 | 61 | 0 | -20.23 | -17.35 | -33.77 | 1.92 | 0.9431 | 0.00 | 68.40 |
| (d) sharp vs soft | h2h | 60m | 0.000 | 2022-23 (1-season table) | 3 | 2 | 1 | 0 | 1.50 | 41.10 | -27.40 | 109.59 | 0.2188 | 0.00 | 66.70 |
| (d) sharp vs soft | h2h | 60m | 0.010 | 2023-24 on | 27 | 13 | 14 | 0 | 1.99 | 6.27 | -31.70 | 40.59 | 0.3887 | 0.01 | 70.40 |
| (d) sharp vs soft | h2h | 60m | 0.010 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 60.61 | 60.61 | 60.61 |  | 0.02 | 100.00 |
| (d) sharp vs soft | h2h | 60m | 0.020 | 2023-24 on | 5 | 2 | 3 | 0 | -1.22 | -18.71 | -100.00 | 36.14 | 0.6933 | 0.03 | 100.00 |
| (d) sharp vs soft | h2h | 60m | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 60m | 0.030 | 2023-24 on | 2 | 1 | 1 | 0 | 0.00 | 0.00 | -100.00 | 50.00 | 0.5000 | 0.04 | 100.00 |
| (d) sharp vs soft | h2h | 60m | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 60m | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | 60m | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | close | 0.000 | 2023-24 on | 121 | 54 | 67 | 0 | 0.20 | 0.14 | -16.68 | 17.25 | 0.4945 | 0.01 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.000 | 2022-23 (1-season table) | 3 | 1 | 2 | 0 | -1.55 | -36.90 | -100.00 | 23.26 | 0.7886 | 0.01 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.010 | 2023-24 on | 32 | 15 | 17 | 0 | 6.58 | 17.57 | -23.49 | 58.60 | 0.2419 | 0.02 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.010 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 60.61 | 60.61 | 60.61 |  | 0.02 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.020 | 2023-24 on | 5 | 2 | 3 | 0 | 0.56 | 10.09 | -100.00 | 136.60 | 0.4388 | 0.03 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | close | 0.030 | 2023-24 on | 2 | 0 | 2 | 0 | -2.55 | -100.00 | -100.00 | -100.00 |  | 0.04 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | h2h | close | 0.040 | 2023-24 on | 2 | 0 | 2 | 0 | -2.55 | -100.00 | -100.00 | -100.00 |  | 0.04 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |

### (d) h2h: cut 0.01 by season

| method | market | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (d) sharp vs soft | h2h | 15utc | 0.010 | 2023 | 2 | 1 | 1 | 0 | 0.00 | 0.00 | -100.00 | 60.61 | 0.5000 | 0.01 | 100.00 |
| (d) sharp vs soft | h2h | 15utc | 0.010 | 2026 | 10 | 6 | 4 | 0 | 1.50 | 11.24 | -32.27 | 54.18 | 0.3342 | 0.02 | 80.00 |
| (d) sharp vs soft | h2h | 15utc | 0.010 | 2027 | 8 | 5 | 3 | 0 | 2.00 | 18.28 | -31.08 | 49.88 | 0.2297 | 0.00 | 62.50 |
| (d) sharp vs soft | h2h | 6h | 0.010 | 2025 | 3 | 1 | 2 | 0 | -2.46 | -52.79 | -100.00 | 13.40 | 0.8745 | 0.03 | 100.00 |
| (d) sharp vs soft | h2h | 6h | 0.010 | 2026 | 19 | 12 | 7 | 0 | 8.89 | 37.13 | -7.07 | 86.37 | 0.0958 | 0.01 | 73.70 |
| (d) sharp vs soft | h2h | 6h | 0.010 | 2027 | 3 | 1 | 2 | 0 | -1.00 | -28.99 | -100.00 | 25.64 | 0.7244 | 0.03 | 100.00 |
| (d) sharp vs soft | h2h | 60m | 0.010 | 2023 | 1 | 1 | 0 | 0 | 1.00 | 60.61 | 60.61 | 60.61 |  | 0.02 | 100.00 |
| (d) sharp vs soft | h2h | 60m | 0.010 | 2026 | 17 | 9 | 8 | 0 | 3.24 | 16.55 | -34.45 | 65.57 | 0.2956 | 0.01 | 64.70 |
| (d) sharp vs soft | h2h | 60m | 0.010 | 2027 | 10 | 4 | 6 | 0 | -1.25 | -10.29 | -72.50 | 39.27 | 0.6195 | 0.01 | 80.00 |
| (d) sharp vs soft | h2h | close | 0.010 | 2023 | 1 | 1 | 0 | 0 | 1.00 | 60.61 | 60.61 | 60.61 |  | 0.02 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.010 | 2024 | 1 | 1 | 0 | 0 | 1.00 | 67.57 | 67.57 | 67.57 |  | 0.01 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.010 | 2026 | 20 | 9 | 11 | 0 | 1.98 | 8.52 | -36.77 | 60.44 | 0.3867 | 0.02 | 100.00 |
| (d) sharp vs soft | h2h | close | 0.010 | 2027 | 11 | 5 | 6 | 0 | 3.60 | 28.32 | -59.44 | 117.05 | 0.2981 | 0.02 | 100.00 |

### (d) sharp vs soft, spreads: read x cut

| method | market | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (d) sharp vs soft | spreads | 15utc | 0.000 | 2023-24 on | 13 | 6 | 7 | 0 | -1.43 | -10.38 | -47.75 | 34.98 | 0.6584 | -0.00 | 30.80 |
| (d) sharp vs soft | spreads | 15utc | 0.000 | 2022-23 (1-season table) | 1 | 0 | 1 | 0 | -1.05 | -100.00 | -100.00 | -100.00 |  | -0.01 | 0.00 |
| (d) sharp vs soft | spreads | 15utc | 0.010 | 2023-24 on | 1 | 0 | 1 | 0 | -1.02 | -100.00 | -100.00 | -100.00 |  | 0.02 | 100.00 |
| (d) sharp vs soft | spreads | 15utc | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 15utc | 0.020 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 15utc | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 15utc | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 15utc | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 15utc | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 15utc | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 6h | 0.000 | 2023-24 on | 6 | 1 | 5 | 0 | -4.38 | -68.12 | -100.00 | -4.35 | 0.9914 | 0.00 | 50.00 |
| (d) sharp vs soft | spreads | 6h | 0.000 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 95.24 | 95.24 | 95.24 | 0.0000 | 0.01 | 100.00 |
| (d) sharp vs soft | spreads | 6h | 0.010 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 6h | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 6h | 0.020 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 6h | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 6h | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 6h | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 6h | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 6h | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 60m | 0.000 | 2023-24 on | 15 | 7 | 8 | 0 | -1.35 | -8.50 | -47.54 | 30.06 | 0.6379 | -0.00 | 46.70 |
| (d) sharp vs soft | spreads | 60m | 0.000 | 2022-23 (1-season table) | 3 | 2 | 1 | 0 | 0.95 | 30.16 | -34.92 | 95.24 | 0.2840 | 0.00 | 66.70 |
| (d) sharp vs soft | spreads | 60m | 0.010 | 2023-24 on | 1 | 0 | 1 | 0 | -1.00 | -100.00 | -100.00 | -100.00 |  | 0.01 | 100.00 |
| (d) sharp vs soft | spreads | 60m | 0.010 | 2022-23 (1-season table) | 1 | 0 | 1 | 0 | -1.05 | -100.00 | -100.00 | -100.00 |  | 0.01 | 100.00 |
| (d) sharp vs soft | spreads | 60m | 0.020 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 60m | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 60m | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 60m | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 60m | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | 60m | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | close | 0.000 | 2023-24 on | 16 | 5 | 11 | 0 | -6.30 | -37.86 | -74.71 | -1.60 | 0.9599 | 0.00 | 100.00 |
| (d) sharp vs soft | spreads | close | 0.000 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 95.24 | 95.24 | 95.24 | 0.0000 | 0.00 | 100.00 |
| (d) sharp vs soft | spreads | close | 0.010 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | close | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | close | 0.020 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | close | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | close | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | close | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | close | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | spreads | close | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |

### (d) spreads: cut 0.01 by season

| method | market | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (d) sharp vs soft | spreads | 15utc | 0.010 | 2027 | 1 | 0 | 1 | 0 | -1.02 | -100.00 | -100.00 | -100.00 |  | 0.02 | 100.00 |
| (d) sharp vs soft | spreads | 60m | 0.010 | 2023 | 1 | 0 | 1 | 0 | -1.05 | -100.00 | -100.00 | -100.00 |  | 0.01 | 100.00 |
| (d) sharp vs soft | spreads | 60m | 0.010 | 2027 | 1 | 0 | 1 | 0 | -1.00 | -100.00 | -100.00 | -100.00 |  | 0.01 | 100.00 |

### (d) sharp vs soft, totals: read x cut

| method | market | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (d) sharp vs soft | totals | 15utc | 0.000 | 2023-24 on | 16 | 14 | 2 | 0 | 11.85 | 69.22 | 44.00 | 93.62 | 0.0000 | 0.00 | 50.00 |
| (d) sharp vs soft | totals | 15utc | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 15utc | 0.010 | 2023-24 on | 2 | 1 | 1 | 0 | -0.05 | -2.44 | -100.00 | 100.00 | 0.5138 | 0.01 | 100.00 |
| (d) sharp vs soft | totals | 15utc | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 15utc | 0.020 | 2023-24 on | 1 | 1 | 0 | 0 | 1.00 | 100.00 | 100.00 | 100.00 |  | 0.02 | 100.00 |
| (d) sharp vs soft | totals | 15utc | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 15utc | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 15utc | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 15utc | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 15utc | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 6h | 0.000 | 2023-24 on | 17 | 11 | 6 | 0 | 4.60 | 25.40 | -9.93 | 60.18 | 0.1236 | 0.01 | 58.80 |
| (d) sharp vs soft | totals | 6h | 0.000 | 2022-23 (1-season table) | 1 | 1 | 0 | 0 | 1.00 | 95.24 | 95.24 | 95.24 | 0.0000 | -0.01 | 0.00 |
| (d) sharp vs soft | totals | 6h | 0.010 | 2023-24 on | 1 | 0 | 1 | 0 | -1.05 | -100.00 | -100.00 | -100.00 |  | 0.00 | 100.00 |
| (d) sharp vs soft | totals | 6h | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 6h | 0.020 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 6h | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 6h | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 6h | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 6h | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 6h | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 60m | 0.000 | 2023-24 on | 23 | 15 | 8 | 0 | 6.46 | 26.49 | -7.46 | 59.51 | 0.0969 | 0.00 | 60.90 |
| (d) sharp vs soft | totals | 60m | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 60m | 0.010 | 2023-24 on | 3 | 3 | 0 | 0 | 3.00 | 96.77 | 95.24 | 98.36 | 0.0000 | -0.00 | 33.30 |
| (d) sharp vs soft | totals | 60m | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 60m | 0.020 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 60m | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 60m | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 60m | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 60m | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | 60m | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.000 | 2023-24 on | 16 | 8 | 8 | 0 | -0.45 | -2.64 | -38.76 | 33.89 | 0.5461 | 0.00 | 100.00 |
| (d) sharp vs soft | totals | close | 0.000 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.010 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.010 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.020 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.020 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.030 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.030 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.040 | 2023-24 on | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (d) sharp vs soft | totals | close | 0.040 | 2022-23 (1-season table) | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |

### (d) totals: cut 0.01 by season

| method | market | read | cut | seasons | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (d) sharp vs soft | totals | 15utc | 0.010 | 2026 | 2 | 1 | 1 | 0 | -0.05 | -2.44 | -100.00 | 100.00 | 0.5138 | 0.01 | 100.00 |
| (d) sharp vs soft | totals | 6h | 0.010 | 2026 | 1 | 0 | 1 | 0 | -1.05 | -100.00 | -100.00 | -100.00 |  | 0.00 | 100.00 |
| (d) sharp vs soft | totals | 60m | 0.010 | 2026 | 1 | 1 | 0 | 0 | 1.00 | 100.00 | 100.00 | 100.00 |  | 0.02 | 100.00 |
| (d) sharp vs soft | totals | 60m | 0.010 | 2027 | 2 | 2 | 0 | 0 | 2.00 | 95.24 | 95.24 | 95.24 | 0.0000 | -0.01 | 0.00 |


## r2_firstpost.py

### The condition: decidable first posts, 2022-23 on, with Pinnacle standing at that moment

| season | market | bookmaker | first_posts | pinnacle_up | same_line | with_3_others | median_others |
|---|---|---|---|---|---|---|---|
| 2023 | h2h | draftkings | 310 | 45 | 45 | 45 | 4.00 |
| 2023 | spreads | draftkings | 310 | 45 | 26 | 16 | 2.00 |
| 2023 | totals | draftkings | 310 | 45 | 23 | 17 | 2.00 |
| 2024 | h2h | draftkings | 331 | 52 | 52 | 52 | 3.00 |
| 2024 | spreads | draftkings | 331 | 52 | 30 | 18 | 1.00 |
| 2024 | totals | draftkings | 331 | 52 | 18 | 7 | 1.00 |
| 2025 | h2h | draftkings | 330 | 6 | 6 | 6 | 3.00 |
| 2025 | spreads | draftkings | 330 | 6 | 5 | 0 | 1.00 |
| 2025 | totals | draftkings | 330 | 6 | 2 | 0 | 0.00 |
| 2026 | h2h | betmgm | 358 | 16 | 16 | 16 | 5.00 |
| 2026 | h2h | betrivers | 372 | 10 | 10 | 10 | 6.00 |
| 2026 | h2h | draftkings | 402 | 12 | 12 | 12 | 5.00 |
| 2026 | h2h | fanatics | 372 | 10 | 10 | 10 | 3.00 |
| 2026 | h2h | fanduel | 369 | 10 | 10 | 10 | 3.00 |
| 2026 | spreads | betmgm | 309 | 20 | 7 | 7 | 4.00 |
| 2026 | spreads | betrivers | 372 | 10 | 3 | 3 | 4.00 |
| 2026 | spreads | draftkings | 402 | 12 | 4 | 4 | 3.00 |
| 2026 | spreads | fanatics | 372 | 10 | 6 | 6 | 1.00 |
| 2026 | spreads | fanduel | 369 | 10 | 6 | 6 | 2.00 |
| 2026 | totals | betmgm | 358 | 16 | 4 | 4 | 3.00 |
| 2026 | totals | betrivers | 297 | 14 | 1 | 1 | 3.00 |
| 2026 | totals | draftkings | 402 | 12 | 5 | 4 | 3.00 |
| 2026 | totals | fanatics | 372 | 10 | 3 | 3 | 2.00 |
| 2026 | totals | fanduel | 362 | 4 | 3 | 3 | 2.00 |
| 2027 | h2h | betmgm | 105 | 1 | 1 | 1 | 4.00 |
| 2027 | h2h | betrivers | 107 | 6 | 6 | 6 | 6.00 |
| 2027 | h2h | draftkings | 107 | 0 | 0 | 0 | 5.00 |
| 2027 | h2h | fanatics | 107 | 0 | 0 | 0 | 2.00 |
| 2027 | h2h | fanduel | 107 | 0 | 0 | 0 | 2.00 |
| 2027 | spreads | betmgm | 92 | 2 | 1 | 1 | 3.00 |
| 2027 | spreads | betrivers | 107 | 6 | 4 | 4 | 5.00 |
| 2027 | spreads | draftkings | 107 | 0 | 0 | 0 | 3.00 |
| 2027 | spreads | fanatics | 107 | 0 | 0 | 0 | 1.00 |
| 2027 | spreads | fanduel | 107 | 0 | 0 | 0 | 1.00 |
| 2027 | totals | betmgm | 105 | 1 | 0 | 0 | 3.00 |
| 2027 | totals | betrivers | 107 | 6 | 2 | 2 | 4.00 |
| 2027 | totals | draftkings | 107 | 0 | 0 | 0 | 3.00 |
| 2027 | totals | fanatics | 107 | 0 | 0 | 0 | 2.00 |
| 2027 | totals | fanduel | 107 | 0 | 0 | 0 | 2.00 |

### (c) first post against Pinnacle: cut grid, 2022-23 on

| method | market | cut | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (c) first post, Pinnacle reference | h2h | 0.000 | 6 | 4 | 2 | 0 | 2.16 | 31.53 | -29.85 | 79.38 | 0.1818 | 0.00 | 66.70 |
| (c) first post, Pinnacle reference | h2h | 0.005 | 4 | 3 | 1 | 0 | 2.16 | 49.66 | -29.85 | 99.44 | 0.1541 | -0.00 | 75.00 |
| (c) first post, Pinnacle reference | h2h | 0.010 | 1 | 1 | 0 | 0 | 1.02 | 102.00 | 102.00 | 102.00 | 0.0000 | 0.01 | 100.00 |
| (c) first post, Pinnacle reference | h2h | 0.015 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | h2h | 0.020 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | h2h | 0.025 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | h2h | 0.030 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | spreads | 0.000 | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | -0.09 | 0.00 |
| (c) first post, Pinnacle reference | spreads | 0.005 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | spreads | 0.010 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | spreads | 0.015 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | spreads | 0.020 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | spreads | 0.025 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | spreads | 0.030 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | totals | 0.000 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | totals | 0.005 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | totals | 0.010 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | totals | 0.015 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | totals | 0.020 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | totals | 0.025 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |
| (c) first post, Pinnacle reference | totals | 0.030 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |

### (c) cut 0.015 by season

|  |
||

### (c2) the catalogued first-post card (moneyline off its own spread): condition counts

| season | posts | three_other_decidable | three_other_any |
|---|---|---|---|
| 2023 | 310 | 0 | 272 |
| 2024 | 331 | 0 | 212 |
| 2025 | 329 | 0 | 198 |
| 2026 | 1,662 | 754 | 1,361 |
| 2027 | 475 | 223 | 301 |

### (c2) results

| method | others | cut | bets | W | L | P | units | ret% | lo% | hi% | p_one | clv_mean | beat% | season |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (c2) first post, own spread | 3 other decidable books | 0.000 | 82 | 43 | 39 | 0 | -10.38 | -9.16 | -25.13 | 5.71 | 0.8428 | -0.02 | 36.60 |  |
| (c2) first post, own spread | 3 other decidable books | 0.005 | 23 | 15 | 8 | 0 | 3.36 | 10.79 | -16.80 | 41.52 | 0.2763 | -0.02 | 39.10 |  |
| (c2) first post, own spread | 3 other decidable books | 0.010 | 10 | 8 | 2 | 0 | 5.70 | 45.82 | 3.62 | 79.91 | 0.0211 | -0.03 | 40.00 |  |
| (c2) first post, own spread | 3 other decidable books | 0.015 | 2 | 2 | 0 | 0 | 2.00 | 82.64 | 82.64 | 82.64 |  | -0.09 | 50.00 |  |
| (c2) by season | 3 other decidable books | 0.015 | 2 | 2 | 0 | 0 | 2.00 | 82.64 | 82.64 | 82.64 |  | -0.09 | 50.00 | 2026 |
| (c2) first post, own spread | 3 other decidable books | 0.020 | 2 | 2 | 0 | 0 | 2.00 | 82.64 | 82.64 | 82.64 |  | -0.09 | 50.00 |  |
| (c2) first post, own spread | 3 other decidable books | 0.025 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |  |
| (c2) first post, own spread | 3 other decidable books | 0.030 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |  |  |
| (c2) first post, own spread | 3 other books of any kind | 0.000 | 294 | 161 | 133 | 0 | -6.91 | -1.69 | -10.61 | 6.58 | 0.6296 | -0.01 | 35.40 |  |
| (c2) first post, own spread | 3 other books of any kind | 0.005 | 143 | 76 | 67 | 0 | -8.29 | -4.15 | -17.05 | 7.73 | 0.7084 | -0.01 | 35.00 |  |
| (c2) first post, own spread | 3 other books of any kind | 0.010 | 95 | 51 | 44 | 0 | -3.49 | -2.67 | -15.89 | 11.34 | 0.6275 | -0.01 | 36.80 |  |
| (c2) first post, own spread | 3 other books of any kind | 0.015 | 51 | 27 | 24 | 0 | 0.82 | 1.17 | -16.81 | 20.25 | 0.4585 | -0.01 | 41.20 |  |
| (c2) by season | 3 other books of any kind | 0.015 | 44 | 25 | 19 | 0 | 5.20 | 8.47 | -9.18 | 28.43 | 0.2280 | -0.01 | 38.60 | 2023 |
| (c2) by season | 3 other books of any kind | 0.015 | 3 | 0 | 3 | 0 | -3.88 | -100.00 | -100.00 | -100.00 |  | 0.01 | 66.70 | 2024 |
| (c2) by season | 3 other books of any kind | 0.015 | 1 | 0 | 1 | 0 | -1.15 | -100.00 | -100.00 | -100.00 |  | -0.03 | 0.00 | 2025 |
| (c2) by season | 3 other books of any kind | 0.015 | 3 | 2 | 1 | 0 | 0.65 | 17.24 | -100.00 | 82.64 | 0.3968 | -0.06 | 66.70 | 2026 |
| (c2) first post, own spread | 3 other books of any kind | 0.020 | 33 | 17 | 16 | 0 | -0.35 | -0.79 | -23.47 | 21.09 | 0.5230 | -0.01 | 36.40 |  |
| (c2) first post, own spread | 3 other books of any kind | 0.025 | 17 | 7 | 10 | 0 | -6.25 | -27.47 | -60.40 | 1.52 | 0.9252 | -0.00 | 35.30 |  |
| (c2) first post, own spread | 3 other books of any kind | 0.030 | 5 | 2 | 3 | 0 | -1.45 | -24.17 | -100.00 | 13.75 | 0.7786 | 0.01 | 60.00 |  |


## r2_kill.py

### 1a. (a) spreads, cut 0.03, 2023-24 on: the side split at every read

| read | side | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 15utc | home | 536 | 298 | 231 | 7 | 45.42 | 7.83 | 0.43 | 14.51 | 0.0336 | 99.60 |
| 15utc | away | 2 | 1 | 1 | 0 | -0.10 | -4.55 | -4.55 | -4.55 | 1.0000 | 0.40 |
| 15utc | favourite (by line) | 255 | 137 | 116 | 2 | 10.98 | 3.98 | -5.53 | 12.80 | 0.2355 | 47.40 |
| 15utc | underdog (by line) | 283 | 162 | 116 | 5 | 34.34 | 11.18 | 1.74 | 20.39 | 0.0272 | 52.60 |
| 6h | home | 526 | 297 | 222 | 7 | 53.79 | 9.44 | 2.24 | 16.27 | 0.0141 | 99.60 |
| 6h | away | 2 | 1 | 1 | 0 | -0.10 | -4.55 | -4.55 | -4.55 | 1.0000 | 0.40 |
| 6h | favourite (by line) | 252 | 140 | 107 | 5 | 23.24 | 8.63 | -0.85 | 18.15 | 0.0729 | 47.70 |
| 6h | underdog (by line) | 276 | 158 | 116 | 2 | 30.45 | 10.05 | 0.22 | 18.75 | 0.0422 | 52.30 |
| 60m | home | 530 | 285 | 238 | 7 | 24.41 | 4.25 | -2.72 | 11.59 | 0.1568 | 99.80 |
| 60m | away | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.20 |
| 60m | favourite (by line) | 240 | 121 | 117 | 2 | -5.82 | -2.25 | -12.27 | 7.80 | 0.6429 | 45.20 |
| 60m | underdog (by line) | 291 | 165 | 121 | 5 | 31.23 | 9.85 | -0.16 | 18.94 | 0.0433 | 54.80 |
| close | home | 544 | 297 | 240 | 7 | 34.54 | 5.87 | -1.09 | 12.31 | 0.0787 | 99.80 |
| close | away | 1 | 1 | 0 | 0 | 1.00 | 90.91 | 90.91 | 90.91 | 0.0000 | 0.20 |
| close | favourite (by line) | 254 | 131 | 120 | 3 | 1.02 | 0.37 | -9.30 | 10.11 | 0.4748 | 46.60 |
| close | underdog (by line) | 291 | 167 | 120 | 4 | 34.52 | 10.88 | 0.96 | 20.67 | 0.0329 | 53.40 |

### 1b. Placebo: the home offset c set to 0, everything else unchanged

| read | cut | version | bets | W | L | P | units | ret% | lo% | hi% | p_one | home% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15utc | 0.000 | c = 0 (placebo) | 652 | 345 | 300 | 7 | 16.28 | 2.30 | -3.81 | 8.06 | 0.2606 | 90.80 |
| 15utc | 0.000 | c fitted (the rule) | 1,003 | 521 | 470 | 12 | 5.23 | 0.48 | -4.21 | 5.09 | 0.4323 | 99.10 |
| 15utc | 0.010 | c = 0 (placebo) | 391 | 216 | 170 | 5 | 30.11 | 7.13 | -1.21 | 14.96 | 0.0714 | 92.10 |
| 15utc | 0.010 | c fitted (the rule) | 880 | 463 | 407 | 10 | 16.51 | 1.73 | -3.23 | 6.63 | 0.2835 | 99.50 |
| 15utc | 0.020 | c = 0 (placebo) | 187 | 100 | 85 | 2 | 7.05 | 3.48 | -8.44 | 16.09 | 0.3231 | 93.00 |
| 15utc | 0.020 | c fitted (the rule) | 715 | 392 | 315 | 8 | 46.69 | 6.01 | 0.37 | 11.35 | 0.0347 | 99.60 |
| 15utc | 0.030 | c = 0 (placebo) | 87 | 43 | 44 | 0 | -5.39 | -5.62 | -21.84 | 12.08 | 0.7100 | 94.30 |
| 15utc | 0.030 | c fitted (the rule) | 538 | 299 | 232 | 7 | 45.32 | 7.78 | 0.41 | 14.37 | 0.0340 | 99.60 |
| 15utc | 0.040 | c = 0 (placebo) | 47 | 24 | 23 | 0 | -1.35 | -2.60 | -27.65 | 23.06 | 0.5679 | 93.60 |
| 15utc | 0.040 | c fitted (the rule) | 275 | 144 | 127 | 4 | 5.78 | 1.95 | -7.88 | 11.71 | 0.3703 | 99.60 |
| 15utc | 0.050 | c = 0 (placebo) | 23 | 9 | 14 | 0 | -6.41 | -25.51 | -54.38 | 13.30 | 0.8923 | 91.30 |
| 15utc | 0.050 | c fitted (the rule) | 125 | 66 | 57 | 2 | 3.53 | 2.62 | -11.34 | 18.48 | 0.3840 | 99.20 |
| 6h | 0.000 | c = 0 (placebo) | 659 | 364 | 287 | 8 | 49.41 | 6.91 | 0.58 | 13.06 | 0.0335 | 90.30 |
| 6h | 0.000 | c fitted (the rule) | 1,011 | 526 | 475 | 10 | 4.03 | 0.37 | -4.23 | 4.95 | 0.4478 | 98.60 |
| 6h | 0.010 | c = 0 (placebo) | 380 | 213 | 162 | 5 | 36.03 | 8.77 | -0.03 | 16.58 | 0.0463 | 90.30 |
| 6h | 0.010 | c fitted (the rule) | 904 | 475 | 420 | 9 | 13.50 | 1.37 | -3.59 | 6.28 | 0.3256 | 99.30 |
| 6h | 0.020 | c = 0 (placebo) | 180 | 99 | 81 | 0 | 10.58 | 5.38 | -6.71 | 18.03 | 0.2392 | 93.90 |
| 6h | 0.020 | c fitted (the rule) | 728 | 404 | 316 | 8 | 57.58 | 7.27 | 1.50 | 12.63 | 0.0163 | 99.50 |
| 6h | 0.030 | c = 0 (placebo) | 92 | 46 | 46 | 0 | -4.52 | -4.46 | -21.30 | 11.79 | 0.6689 | 92.40 |
| 6h | 0.030 | c fitted (the rule) | 528 | 298 | 223 | 7 | 53.69 | 9.38 | 2.22 | 16.18 | 0.0143 | 99.60 |
| 6h | 0.040 | c = 0 (placebo) | 44 | 20 | 24 | 0 | -6.70 | -13.69 | -39.36 | 12.02 | 0.8205 | 93.20 |
| 6h | 0.040 | c fitted (the rule) | 285 | 154 | 130 | 1 | 12.28 | 3.95 | -5.08 | 13.20 | 0.2384 | 99.60 |
| 6h | 0.050 | c = 0 (placebo) | 19 | 8 | 11 | 0 | -4.19 | -20.09 | -50.34 | 16.30 | 0.8385 | 89.50 |
| 6h | 0.050 | c fitted (the rule) | 123 | 67 | 56 | 0 | 5.65 | 4.19 | -9.33 | 18.90 | 0.3156 | 99.20 |
| 60m | 0.000 | c = 0 (placebo) | 635 | 346 | 281 | 8 | 38.82 | 5.65 | -0.28 | 12.02 | 0.0635 | 92.40 |
| 60m | 0.000 | c fitted (the rule) | 1,009 | 528 | 468 | 13 | 14.11 | 1.29 | -2.71 | 5.92 | 0.3145 | 99.50 |
| 60m | 0.010 | c = 0 (placebo) | 402 | 219 | 178 | 5 | 24.61 | 5.65 | -3.16 | 13.64 | 0.1303 | 94.30 |
| 60m | 0.010 | c fitted (the rule) | 895 | 473 | 412 | 10 | 20.94 | 2.15 | -2.71 | 6.91 | 0.2348 | 99.80 |
| 60m | 0.020 | c = 0 (placebo) | 190 | 110 | 80 | 0 | 22.38 | 10.67 | -1.37 | 22.22 | 0.0624 | 94.20 |
| 60m | 0.020 | c fitted (the rule) | 730 | 398 | 323 | 9 | 44.15 | 5.57 | -0.38 | 11.40 | 0.0563 | 99.70 |
| 60m | 0.030 | c = 0 (placebo) | 87 | 47 | 40 | 0 | 2.90 | 2.99 | -13.69 | 21.70 | 0.3921 | 96.60 |
| 60m | 0.030 | c fitted (the rule) | 531 | 286 | 238 | 7 | 25.41 | 4.42 | -2.53 | 11.76 | 0.1472 | 99.80 |
| 60m | 0.040 | c = 0 (placebo) | 41 | 20 | 21 | 0 | -3.28 | -7.13 | -35.97 | 18.96 | 0.6608 | 95.10 |
| 60m | 0.040 | c fitted (the rule) | 302 | 170 | 128 | 4 | 30.08 | 9.20 | -0.55 | 18.71 | 0.0565 | 99.70 |
| 60m | 0.050 | c = 0 (placebo) | 17 | 7 | 10 | 0 | -3.99 | -21.16 | -57.47 | 21.05 | 0.8109 | 94.10 |
| 60m | 0.050 | c fitted (the rule) | 129 | 73 | 56 | 0 | 11.17 | 7.83 | -7.46 | 23.00 | 0.1946 | 99.20 |
| close | 0.000 | c = 0 (placebo) | 659 | 358 | 293 | 8 | 37.81 | 5.30 | -0.02 | 11.37 | 0.0673 | 92.40 |
| close | 0.000 | c fitted (the rule) | 1,022 | 535 | 476 | 11 | 12.78 | 1.15 | -3.20 | 5.66 | 0.3365 | 99.20 |
| close | 0.010 | c = 0 (placebo) | 389 | 210 | 176 | 3 | 17.75 | 4.20 | -4.47 | 12.71 | 0.2128 | 94.90 |
| close | 0.010 | c fitted (the rule) | 915 | 485 | 419 | 11 | 25.38 | 2.55 | -2.31 | 7.79 | 0.1946 | 99.60 |
| close | 0.020 | c = 0 (placebo) | 195 | 112 | 82 | 1 | 21.95 | 10.30 | -1.36 | 21.46 | 0.0761 | 93.80 |
| close | 0.020 | c fitted (the rule) | 734 | 400 | 325 | 9 | 43.69 | 5.48 | -0.58 | 11.04 | 0.0582 | 99.70 |
| close | 0.030 | c = 0 (placebo) | 90 | 51 | 39 | 0 | 8.11 | 8.15 | -8.60 | 25.54 | 0.2186 | 94.40 |
| close | 0.030 | c fitted (the rule) | 545 | 298 | 240 | 7 | 35.54 | 6.02 | -1.02 | 12.50 | 0.0733 | 99.80 |
| close | 0.040 | c = 0 (placebo) | 42 | 21 | 21 | 0 | -2.30 | -4.93 | -32.49 | 25.35 | 0.6090 | 92.90 |
| close | 0.040 | c fitted (the rule) | 308 | 171 | 134 | 3 | 24.57 | 7.36 | -0.77 | 16.56 | 0.0829 | 99.70 |
| close | 0.050 | c = 0 (placebo) | 19 | 10 | 9 | 0 | 0.03 | 0.14 | -42.77 | 47.29 | 0.4979 | 94.70 |
| close | 0.050 | c fitted (the rule) | 128 | 74 | 54 | 0 | 14.48 | 10.26 | -4.62 | 25.06 | 0.1259 | 99.20 |

### 1c. The bet line against the consensus at the read and at the close (15utc, cut 0.03)

| bets | mean pts better than 15utc consensus | mean pts better than close consensus | share better than close consensus % | share equal to close consensus % | consensus moved toward the bet line % | consensus moved away % | mean clv (prob, Pinnacle close) |
|---|---|---|---|---|---|---|---|
| 538 | 0.14 | 0.06 | 33.50 | 42.00 | 47.60 | 43.10 | -0.02 |

By how far the bet line sat from the 15utc consensus (points, toward the bet side):

| off_pts (points) | bets | units | risk | ret% |
|---|---|---|---|---|
| -0.50 | 4 | -0.10 | 4.18 | -2.39 |
| -0.20 | 37 | 4.93 | 38.36 | 12.85 |
| 0.00 | 345 | 32.49 | 371.32 | 8.75 |
| 0.20 | 61 | 9.21 | 67.28 | 13.69 |
| 0.50 | 49 | -0.49 | 53.71 | -0.91 |
| 0.80 | 8 | 3.72 | 9.17 | 40.57 |
| 1.00 | 30 | -2.06 | 34.14 | -6.03 |
| 1.50 | 1 | -1.18 | 1.18 | -100.00 |
| 2.00 | 2 | -0.10 | 2.20 | -4.55 |
| 3.00 | 1 | -1.10 | 1.10 | -100.00 |

### 1d. The bet quote's age at the read (hours since that book's last change)

- bets: median 1.5 h, quartiles 0.5 / 3.9
- every game's best decidable quote (bet or not): median 1.8 h
| subset | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| all bets | 538 | 299 | 232 | 7 | 45.32 | 7.78 | 0.41 | 14.37 | 0.0340 |
| quote changed <= 2 h before the read | 315 | 171 | 138 | 6 | 20.31 | 6.00 | -2.33 | 14.92 | 0.1254 |
| quote changed <= 6 h before the read | 444 | 247 | 190 | 7 | 39.44 | 8.23 | 0.70 | 15.66 | 0.0368 |
| quote older than 6 h | 94 | 52 | 42 | 0 | 5.88 | 5.70 | -8.59 | 21.86 | 0.2620 |

The bet book's next LINE change after the read, before the tip:
- no line change before tip: 174 of 538; changed: 364, of which toward the 15utc consensus: 36, away or across: 328; median hours from the read to that change: 1.6

### 1e. Decomposition (15utc, cut 0.03, 2023-24 on)

| version | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| the rule (bet book's line and price) | 538 | 299 | 232 | 7 | 45.32 | 7.78 | 0.41 | 14.37 | 0.0340 |
| the rule's sides at the 15utc consensus line, -110 | 538 | 299 | 235 | 4 | 40.50 | 6.89 | -0.32 | 13.79 | 0.0533 |
| home on the same games, at the bet quote's line and home price | 538 | 299 | 232 | 7 | 45.32 | 7.78 | 0.41 | 14.37 | 0.0340 |
| home on every game, DraftKings at 15utc | 1,165 | 598 | 555 | 12 | -10.44 | -0.82 | -5.03 | 3.21 | 0.6305 |
| away on every game, DraftKings at 15utc | 1,165 | 555 | 598 | 12 | -102.17 | -8.05 | -12.01 | -3.85 | 0.9994 |

### 1f. Best dates, early / late, by book (15utc, cut 0.03, 2023-24 on)

| subset | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| all | 538 | 299 | 232 | 7 | 45.32 | 7.78 | 0.41 | 14.37 | 0.0340 |
| without its 10 best dates | 507 | 268 | 232 | 7 | 14.32 | 2.61 | -4.54 | 9.48 | 0.2677 |
| early half of each season | 265 | 153 | 109 | 3 | 33.69 | 11.71 | 2.29 | 20.39 | 0.0174 |
| late half of each season | 273 | 146 | 123 | 4 | 11.63 | 3.94 | -6.22 | 13.67 | 0.2518 |
| book: betmgm | 56 | 28 | 28 | 0 | -2.91 | -4.67 | -26.63 | 17.03 | 0.6348 |
| book: betrivers | 49 | 23 | 25 | 1 | -4.77 | -8.92 | -30.81 | 11.45 | 0.7537 |
| book: draftkings | 403 | 231 | 166 | 6 | 49.98 | 11.50 | 3.69 | 18.66 | 0.0068 |
| book: fanatics | 25 | 14 | 11 | 0 | 2.10 | 7.73 | -27.86 | 44.09 | 0.3610 |
| book: fanduel | 5 | 3 | 2 | 0 | 0.92 | 17.69 | -60.77 | 95.79 | 0.3432 |
| season 2024 early | 113 | 61 | 49 | 3 | 7.55 | 6.24 | -6.86 | 18.44 | 0.2183 |
| season 2024 late | 113 | 64 | 48 | 1 | 11.66 | 9.53 | -5.98 | 24.17 | 0.1480 |
| season 2025 early | 62 | 38 | 24 | 0 | 11.76 | 17.33 | -2.66 | 35.96 | 0.0755 |
| season 2025 late | 68 | 35 | 31 | 2 | 1.18 | 1.63 | -18.75 | 21.33 | 0.4478 |
| season 2026 early | 70 | 44 | 26 | 0 | 15.36 | 19.98 | 4.50 | 35.37 | 0.0199 |
| season 2026 late | 71 | 41 | 29 | 1 | 9.09 | 11.73 | -8.20 | 29.47 | 0.1486 |
| season 2027 early | 20 | 10 | 10 | 0 | -0.98 | -4.46 | -43.16 | 48.31 | 0.5630 |
| season 2027 late | 21 | 6 | 15 | 0 | -10.30 | -45.37 | -82.48 | -8.33 | 0.9783 |

Volume: 538 bets on 1098 priced games (49.0% of them) over 4 seasons, 134 a season.
Price range of the bets: median -110, shortest -120, longest 100.

### 2. Moneyline favourites at -500 or shorter, DraftKings close

| subset | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| all seasons | 188 | 175 | 13 | 0 | 34.59 | 6.13 | 2.27 | 9.60 | 0.0023 |
| season 2022 | 41 | 38 | 3 | 0 | 6.69 | 5.44 | -2.60 | 11.87 | 0.1151 |
| season 2023 | 36 | 31 | 5 | 0 | -1.51 | -1.39 | -13.73 | 8.48 | 0.5811 |
| season 2024 | 36 | 35 | 1 | 0 | 10.98 | 10.17 | 3.89 | 14.25 | 0.0009 |
| season 2025 | 39 | 37 | 2 | 0 | 9.35 | 7.99 | 0.64 | 13.99 | 0.0265 |
| season 2026 | 27 | 25 | 2 | 0 | 4.98 | 6.15 | -2.96 | 14.41 | 0.1243 |
| season 2027 | 9 | 9 | 0 | 0 | 4.08 | 15.13 | 12.76 | 16.98 | 0.0000 |
| early half of each season | 91 | 85 | 6 | 0 | 17.95 | 6.58 | 1.23 | 11.23 | 0.0175 |
| late half of each season | 97 | 90 | 7 | 0 | 16.63 | 5.72 | 0.98 | 10.59 | 0.0275 |
| without its 10 best dates | 165 | 152 | 13 | 0 | 23.22 | 4.69 | 0.71 | 8.41 | 0.0237 |
| home side | 181 | 169 | 12 | 0 | 34.70 | 6.39 | 2.75 | 9.74 | 0.0013 |
| away side | 7 | 6 | 1 | 0 | -0.11 | -0.53 | -33.19 | 17.19 | 0.5140 |

Stake profile: 188 bets risked 564.0 units to win 73.6; mean win per winning bet 0.421 units; each loss costs up to 3 units (mean loss 3.00). Median price -675, shortest -4000.
Fair: multiplicative de-vig mean 0.8412, power de-vig mean 0.8639, won 0.9309.

Neighbouring thresholds (fixed before reading):

| threshold (price at or shorter) | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| -400 | 279 | 244 | 35 | 0 | 15.69 | 1.87 | -2.04 | 5.62 | 0.2121 |
| -450 | 222 | 200 | 22 | 0 | 23.54 | 3.53 | -0.20 | 7.18 | 0.0602 |
| -500 | 188 | 175 | 13 | 0 | 34.59 | 6.13 | 2.27 | 9.60 | 0.0023 |
| -550 | 151 | 146 | 5 | 0 | 41.59 | 9.18 | 5.97 | 11.57 | 0.0000 |
| -600 | 122 | 121 | 1 | 0 | 40.29 | 11.01 | 9.11 | 12.24 | 0.0000 |
| -700 | 88 | 87 | 1 | 0 | 24.43 | 9.25 | 6.98 | 10.83 | 0.0000 |
| -800 | 66 | 65 | 1 | 0 | 15.38 | 7.77 | 4.50 | 9.75 | 0.0000 |

The same band at other books and reads:

| where | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| DraftKings first post | 178 | 168 | 10 | 0 | 41.33 | 7.74 | 4.36 | 10.84 | 0.0000 |
| Pinnacle close (reference, not bettable) | 161 | 150 | 11 | 0 | 30.51 | 6.32 | 2.14 | 9.93 | 0.0037 |
| Bovada close (reference) | 208 | 188 | 20 | 0 | 18.01 | 2.89 | -1.19 | 6.65 | 0.1151 |
| Unibet close (reference) | 235 | 214 | 21 | 0 | 29.34 | 4.16 | 0.64 | 7.48 | 0.0234 |
| fanduel close (2025-26 on) | 58 | 51 | 7 | 0 | 0.38 | 0.22 | -7.25 | 7.63 | 0.4809 |
| betmgm close (2025-26 on) | 47 | 44 | 3 | 0 | 10.64 | 7.54 | -0.32 | 13.17 | 0.0382 |
| betrivers close (2025-26 on) | 49 | 45 | 4 | 0 | 7.94 | 5.40 | -2.50 | 12.45 | 0.1148 |
| fanatics close (2025-26 on) | 53 | 48 | 5 | 0 | 5.02 | 3.16 | -5.09 | 10.29 | 0.2460 |


## r2_leads.py

### (i) The close's spread residual (home margin + closing home spread), 2021-22 on, by venue group

| group | line | n | mean_resid_pts | lo | hi | home_cover% | home_win% | pin_fair_home% |
|---|---|---|---|---|---|---|---|---|
| R1 relocated (scout's list) | pin | 80 | 0.74 | -1.35 | 2.80 | 57.00 | 58.80 | 55.0000 |
| R1 relocated (scout's list) | dk | 81 | 0.59 | -1.59 | 2.64 | 55.00 |  |  |
| R2 other one-off venue abroad | pin | 8 | 5.75 | -0.70 | 12.25 | 62.50 | 87.50 | 59.6000 |
| R2 other one-off venue abroad | dk | 8 | 5.56 | -1.01 | 12.06 | 71.40 |  |  |
| excluded (location unknown) | pin | 1 | -8.50 | -8.50 | -8.50 | 0.00 | 100.00 | 84.2000 |
| excluded (location unknown) | dk | 1 | -8.50 | -8.50 | -8.50 | 0.00 |  |  |
| neutral | pin | 15 | -2.10 | -4.96 | 1.43 | 42.90 | 46.70 | 58.7000 |
| neutral | dk | 19 | -1.05 | -3.60 | 2.05 | 52.60 |  |  |
| own country | pin | 1,517 | 0.48 | 0.01 | 0.98 | 52.20 | 63.20 | 60.5000 |
| own country | dk | 1,641 | 0.51 | 0.06 | 0.99 | 52.20 |  |  |
| own country, attendance 1-999 | pin | 5 | -4.40 | -12.50 | 3.20 | 40.00 | 40.00 | 47.5000 |
| own country, attendance 1-999 | dk | 5 | -4.80 | -13.00 | 2.90 | 40.00 |  |  |
| own country, attendance missing (0) | pin | 16 | 0.91 | -2.85 | 4.50 | 62.50 | 62.50 | 60.2000 |
| own country, attendance missing (0) | dk | 17 | 0.85 | -2.65 | 4.44 | 58.80 |  |  |

### (i) The three relocated clubs, home games by venue group (Pinnacle close)

| club | group | seasons | n | mean_resid_pts | lo | hi | home_cover% | mean_att |
|---|---|---|---|---|---|---|---|---|
| DUB | R1 relocated (scout's list) | 2026 | 6 | -5.67 | -13.17 | 0.50 | 20.00 | 5,647.00 |
| DUB | own country | 2026,2027 | 17 | 1.38 | -3.24 | 5.68 | 58.80 | 5,871.00 |
| DUB | own country, attendance missing (0) | 2026 | 1 | -6.00 | -6.00 | -6.00 | 0.00 |  |
| HTA | R1 relocated (scout's list) | 2026,2027 | 21 | 3.07 | -0.60 | 6.55 | 61.90 | 3,474.00 |
| HTA | own country | 2026 | 6 | -6.50 | -15.50 | 3.50 | 16.70 | 7,163.00 |
| TEL | R1 relocated (scout's list) | 2024,2025,2026,2027 | 53 | 0.55 | -2.06 | 3.16 | 58.50 | 317.00 |
| TEL | own country | 2022,2023,2024,2026 | 38 | 2.87 | 0.05 | 5.72 | 64.90 | 10,104.00 |
| TEL | own country, attendance missing (0) | 2022,2023 | 3 | 8.50 | 6.17 | 10.83 | 100.00 |  |

### (i) R1 by season (Pinnacle close)

| season | n | mean_resid_pts | lo | hi | home_cover% |
|---|---|---|---|---|---|
| 2024 | 18 | 2.97 | -1.14 | 6.72 | 72.20 |
| 2025 | 17 | 1.59 | -4.06 | 6.94 | 58.80 |
| 2026 | 34 | -0.96 | -4.05 | 1.89 | 48.50 |
| 2027 | 11 | 1.05 | -5.09 | 7.45 | 54.50 |

### (i) Blind bets on the R1 games at the close

| market | side | book | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|---|
| spreads | away | draftkings | 81 | 36 | 44 | 1 | -12.57 | -14.26 | -33.11 | 4.88 | 0.9008 |
| spreads | away | best decidable | 81 | 36 | 44 | 1 | -12.13 | -13.89 | -32.87 | 5.29 | 0.8944 |
| h2h | away | draftkings | 81 | 34 | 47 | 0 | -14.87 | -13.59 | -32.74 | 6.34 | 0.8724 |
| h2h | away | best decidable | 81 | 34 | 47 | 0 | -13.71 | -12.62 | -32.04 | 8.13 | 0.8505 |
| spreads | home | draftkings | 81 | 44 | 36 | 1 | 4.36 | 4.96 | -14.10 | 23.80 | 0.3273 |
| spreads | home | best decidable | 81 | 44 | 36 | 1 | 4.97 | 5.74 | -13.39 | 24.60 | 0.3038 |
| h2h | home | draftkings | 81 | 47 | 34 | 0 | 3.32 | 2.40 | -13.80 | 18.03 | 0.4024 |
| h2h | home | best decidable | 81 | 47 | 34 | 0 | 4.91 | 3.60 | -12.65 | 19.39 | 0.3562 |

### (ii) Home edge by club, out of sample: each game's residual on its club's shrunk earlier deviation

| season | games | league prior mean (pts) | actual mean (pts) | slope on club deviation | slope se | sd of club deviation |
|---|---|---|---|---|---|---|
| 2023 | 306 | 1.10 | 0.92 | 1.0150 | 0.7300 | 0.88 |
| 2024 | 306 | 1.00 | 0.25 | -0.1290 | 0.5720 | 1.12 |
| 2025 | 307 | 0.75 | 0.21 | 0.7010 | 0.7370 | 0.91 |
| 2026 | 360 | 0.61 | 0.35 | 0.3490 | 0.6190 | 1.00 |
| 2027 | 96 | 0.55 | -0.04 | -1.1500 | 1.1060 | 1.00 |
| pooled | 1,375 | 0.83 | 0.40 | 0.3030 | 0.3130 | 0.98 |

### (ii) The club home-edge rule at the DraftKings close

| rule | season | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|
| home when predicted > +1.0 | all | 633 | 332 | 295 | 6 | 7.56 | 1.10 | -5.16 | 7.13 | 0.3849 |
| home when predicted > +1.0 | 2023 | 202 | 114 | 87 | 1 | 18.30 | 8.29 | -2.67 | 19.35 | 0.1060 |
| home when predicted > +1.0 | 2024 | 165 | 83 | 79 | 3 | -4.48 | -2.51 | -14.78 | 9.43 | 0.6305 |
| home when predicted > +1.0 | 2025 | 128 | 63 | 63 | 2 | -5.92 | -4.28 | -17.81 | 9.08 | 0.6987 |
| home when predicted > +1.0 | 2026 | 106 | 60 | 46 | 0 | 9.66 | 8.30 | -7.33 | 24.30 | 0.1869 |
| home when predicted > +1.0 | 2027 | 32 | 12 | 20 | 0 | -10.00 | -28.40 | -47.50 | -4.28 | 0.9820 |
| away when predicted < -1.0 | all | 59 | 25 | 33 | 1 | -10.97 | -17.27 | -39.44 | 2.24 | 0.9152 |
| away when predicted < -1.0 | 2024 | 17 | 10 | 7 | 0 | 2.34 | 12.58 | -21.58 | 47.17 | 0.2949 |
| away when predicted < -1.0 | 2025 | 17 | 5 | 11 | 1 | -7.10 | -40.16 | -75.99 | -4.19 | 0.9655 |
| away when predicted < -1.0 | 2026 | 19 | 8 | 11 | 0 | -3.91 | -18.81 | -49.62 | 20.87 | 0.8081 |
| away when predicted < -1.0 | 2027 | 6 | 2 | 4 | 0 | -2.30 | -35.66 | -100.00 | 29.46 | 0.8221 |
| both | all | 692 | 357 | 328 | 7 | -3.41 | -0.45 | -6.22 | 5.89 | 0.5486 |
| both | 2023 | 202 | 114 | 87 | 1 | 18.30 | 8.29 | -2.67 | 19.35 | 0.1060 |
| both | 2024 | 182 | 93 | 86 | 3 | -2.14 | -1.08 | -13.04 | 10.37 | 0.5615 |
| both | 2025 | 145 | 68 | 74 | 3 | -13.02 | -8.35 | -22.45 | 4.84 | 0.8445 |
| both | 2026 | 125 | 68 | 57 | 0 | 5.75 | 4.19 | -9.81 | 19.21 | 0.3143 |
| both | 2027 | 38 | 14 | 24 | 0 | -12.30 | -29.52 | -50.28 | -4.60 | 0.9815 |

Share of priced home games whose prediction is > +1.0: 46.0%; < -1.0: 4.3%

### (ii) Residual by the club's previous-season attendance (known before the game)

| season | club's previous-season attendance tercile | mean att | n | mean_resid_pts | lo | hi | home_cover% |
|---|---|---|---|---|---|---|---|
| 2023 | low | 3,932.00 | 102 | -0.51 | -2.35 | 1.49 | 49.00 |
| 2023 | mid | 5,819.00 | 88 | 1.59 | -0.57 | 3.77 | 54.50 |
| 2023 | high | 8,897.00 | 73 | 2.36 | 0.32 | 4.41 | 65.80 |
| 2024 | low | 5,558.00 | 108 | -0.50 | -2.19 | 1.20 | 52.80 |
| 2024 | mid | 8,048.00 | 109 | 0.05 | -1.89 | 1.86 | 49.50 |
| 2024 | high | 13,215.00 | 89 | 1.40 | -0.49 | 3.39 | 51.10 |
| 2025 | low | 6,855.00 | 112 | 0.17 | -1.53 | 1.79 | 50.90 |
| 2025 | mid | 10,234.00 | 88 | 0.02 | -2.25 | 2.22 | 51.20 |
| 2025 | high | 15,994.00 | 89 | 0.90 | -1.22 | 3.18 | 52.30 |
| 2026 | low | 6,534.00 | 121 | -0.84 | -2.40 | 0.81 | 50.80 |
| 2026 | mid | 9,813.00 | 97 | 1.08 | -0.87 | 2.84 | 56.40 |
| 2026 | high | 16,052.00 | 101 | 0.53 | -1.61 | 2.88 | 54.50 |
| 2027 | low | 6,318.00 | 32 | -3.09 | -6.83 | -0.12 | 31.20 |
| 2027 | mid | 9,653.00 | 31 | 1.35 | -1.21 | 4.28 | 46.70 |
| 2027 | high | 16,046.00 | 28 | 3.12 | -0.50 | 7.28 | 66.70 |
| pooled | low | 5,815.00 | 475 | -0.61 | -1.40 | 0.22 | 49.60 |
| pooled | mid | 8,574.00 | 413 | 0.71 | -0.24 | 1.73 | 52.30 |
| pooled | high | 13,999.00 | 380 | 1.37 | 0.32 | 2.38 | 56.30 |

### (ii) Residual by the game's own attendance (measured at the game; descriptive only)

| game's own attendance tercile (descriptive) | mean att | n | mean_resid_pts | lo | hi | home_cover% |
|---|---|---|---|---|---|---|
| low | 5,128.00 | 552 | -0.37 | -1.19 | 0.41 | 48.80 |
| mid | 8,504.00 | 547 | 0.78 | -0.02 | 1.56 | 52.10 |
| high | 14,085.00 | 547 | 1.14 | 0.25 | 1.91 | 55.40 |

### (ii) Residual by the size of the closing home spread (the 'weaker teams lean on home court' lead), by season

| closing home spread | season | n | mean_resid_pts | lo | hi | home_cover% |
|---|---|---|---|---|---|---|
| home -10 or more | all | 139 | 1.25 | 0.13 | 2.30 | 51.80 |
| home -10 or more | 2022 | 28 | 0.50 | -2.74 | 3.58 | 42.90 |
| home -10 or more | 2023 | 28 | 0.30 | -2.38 | 2.68 | 53.60 |
| home -10 or more | 2024 | 28 | 0.80 | -0.83 | 2.31 | 55.60 |
| home -10 or more | 2025 | 28 | 1.73 | -1.02 | 4.18 | 50.00 |
| home -10 or more | 2026 | 21 | 3.57 | 0.75 | 6.57 | 60.00 |
| home -10 or more | 2027 | 6 | 0.92 | -4.00 | 6.25 | 50.00 |
| -10..-5 | all | 535 | -0.31 | -1.14 | 0.50 | 48.60 |
| -10..-5 | 2022 | 87 | -0.55 | -2.55 | 1.50 | 50.60 |
| -10..-5 | 2023 | 92 | 0.82 | -1.16 | 3.15 | 52.20 |
| -10..-5 | 2024 | 99 | -0.38 | -2.29 | 1.43 | 45.90 |
| -10..-5 | 2025 | 104 | -0.65 | -2.48 | 1.19 | 46.50 |
| -10..-5 | 2026 | 124 | -1.16 | -2.89 | 0.55 | 45.90 |
| -10..-5 | 2027 | 29 | 1.95 | -2.48 | 6.64 | 58.60 |
| -5..-1.5 | all | 430 | -0.47 | -1.34 | 0.41 | 50.40 |
| -5..-1.5 | 2022 | 63 | -2.05 | -4.60 | 0.51 | 41.90 |
| -5..-1.5 | 2023 | 89 | 0.84 | -0.90 | 2.72 | 53.90 |
| -5..-1.5 | 2024 | 84 | 0.10 | -1.81 | 1.88 | 56.00 |
| -5..-1.5 | 2025 | 70 | -0.41 | -3.08 | 2.15 | 52.90 |
| -5..-1.5 | 2026 | 98 | -1.36 | -3.19 | 0.45 | 46.90 |
| -5..-1.5 | 2027 | 26 | 0.19 | -3.18 | 3.46 | 46.20 |
| -1.5..+1.5 | all | 165 | 0.77 | -0.81 | 2.28 | 56.40 |
| -1.5..+1.5 | 2022 | 23 | 2.52 | -0.81 | 5.71 | 65.20 |
| -1.5..+1.5 | 2023 | 28 | 0.89 | -2.93 | 4.37 | 60.70 |
| -1.5..+1.5 | 2024 | 28 | 2.18 | -1.40 | 5.67 | 57.10 |
| -1.5..+1.5 | 2025 | 41 | -1.93 | -4.76 | 1.07 | 40.00 |
| -1.5..+1.5 | 2026 | 36 | 2.58 | -1.38 | 6.20 | 71.40 |
| -1.5..+1.5 | 2027 | 9 | -3.50 | -6.39 | 0.19 | 33.30 |
| +1.5..+5 | all | 235 | 2.06 | 1.00 | 3.18 | 53.70 |
| +1.5..+5 | 2022 | 46 | 4.36 | 1.64 | 7.15 | 56.50 |
| +1.5..+5 | 2023 | 44 | 1.47 | -1.24 | 4.00 | 52.30 |
| +1.5..+5 | 2024 | 39 | -0.03 | -2.51 | 2.46 | 44.70 |
| +1.5..+5 | 2025 | 36 | 2.88 | 0.06 | 5.77 | 58.30 |
| +1.5..+5 | 2026 | 50 | 3.35 | 1.16 | 5.37 | 65.30 |
| +1.5..+5 | 2027 | 20 | -2.52 | -5.91 | 1.13 | 27.80 |
| home +5 or more | all | 159 | 2.80 | 1.27 | 4.37 | 62.80 |
| home +5 or more | 2022 | 41 | 5.37 | 1.79 | 8.79 | 62.50 |
| home +5 or more | 2023 | 25 | 1.30 | -2.35 | 4.79 | 68.00 |
| home +5 or more | 2024 | 28 | 0.86 | -2.55 | 4.52 | 53.60 |
| home +5 or more | 2025 | 28 | 3.14 | 0.42 | 5.87 | 66.70 |
| home +5 or more | 2026 | 31 | 2.23 | -1.16 | 5.25 | 66.70 |
| home +5 or more | 2027 | 6 | 1.92 | -6.08 | 10.76 | 50.00 |

### (iii) Favourite-longshot: moneyline sides at the close by their power-de-vigged probability

| book | no-vig P(side) | bets | W | L | P | units | ret% | lo% | hi% | p_one | mean fair% | won% | home share% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| draftkings | <10% | 35 | 0 | 35 | 0 | -35.00 | -100.00 | -100.00 | -100.00 |  | 7.98 | 0.00 | 0.00 |
| draftkings | 10-20% | 199 | 24 | 175 | 0 | -80.85 | -40.63 | -58.73 | -21.15 | 0.9997 | 15.90 | 12.06 | 6.00 |
| draftkings | 20-35% | 747 | 239 | 508 | 0 | 23.80 | 3.19 | -4.94 | 12.69 | 0.2749 | 28.14 | 31.99 | 23.00 |
| draftkings | 35-50% | 791 | 341 | 450 | 0 | -32.33 | -4.05 | -10.12 | 1.70 | 0.8715 | 42.78 | 43.11 | 38.30 |
| draftkings | 50-65% | 791 | 450 | 341 | 0 | -47.01 | -4.03 | -8.42 | 0.45 | 0.9333 | 57.22 | 56.89 | 61.70 |
| draftkings | 65-80% | 747 | 508 | 239 | 0 | -141.15 | -7.09 | -10.93 | -3.76 | 0.9994 | 71.86 | 68.01 | 77.00 |
| draftkings | 80-90% | 199 | 175 | 24 | 0 | 16.44 | 2.75 | -1.98 | 7.06 | 0.1610 | 84.10 | 87.94 | 94.00 |
| draftkings | >=90% | 35 | 35 | 0 | 0 | 7.92 | 7.55 | 7.07 | 8.00 | 0.0000 | 92.02 | 100.00 | 100.00 |
| pinnacle | <10% | 31 | 0 | 31 | 0 | -31.00 | -100.00 | -100.00 | -100.00 |  | 8.28 | 0.00 | 0.00 |
| pinnacle | 10-20% | 181 | 23 | 158 | 0 | -63.92 | -35.31 | -56.09 | -14.28 | 0.9976 | 15.84 | 12.71 | 6.60 |
| pinnacle | 20-35% | 700 | 224 | 476 | 0 | 31.80 | 4.54 | -5.07 | 13.53 | 0.2184 | 28.01 | 32.00 | 22.90 |
| pinnacle | 35-50% | 726 | 323 | 403 | 0 | 1.23 | 0.17 | -5.49 | 6.78 | 0.4822 | 42.75 | 44.49 | 38.70 |
| pinnacle | 50-65% | 734 | 407 | 327 | 0 | -62.60 | -5.88 | -10.82 | -1.71 | 0.9819 | 57.17 | 55.45 | 61.20 |
| pinnacle | 65-80% | 700 | 476 | 224 | 0 | -128.44 | -6.92 | -10.49 | -3.02 | 0.9983 | 71.99 | 68.00 | 77.10 |
| pinnacle | 80-90% | 181 | 158 | 23 | 0 | 12.18 | 2.24 | -2.77 | 6.95 | 0.2166 | 84.16 | 87.29 | 93.40 |
| pinnacle | >=90% | 31 | 31 | 0 | 0 | 7.65 | 8.23 | 7.67 | 8.78 | 0.0000 | 91.72 | 100.00 | 100.00 |

### (iii) The tails split by home and away

| book | side | bucket | bets | W | L | P | units | ret% | lo% | hi% | p_one | mean fair% | won% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| draftkings | home | favourite 80%+ | 222 | 201 | 21 | 0 | 28.55 | 4.29 | 0.48 | 7.91 | 0.0304 | 85.40 | 90.54 |
| draftkings | home | favourite 65-80% | 575 | 407 | 168 | 0 | -59.87 | -3.88 | -8.17 | 0.41 | 0.9395 | 72.10 | 70.78 |
| draftkings | home | underdog <20% | 12 | 3 | 9 | 0 | 2.20 | 18.33 | -62.50 | 131.67 | 0.3739 | 16.84 | 25.00 |
| draftkings | away | favourite 80%+ | 12 | 9 | 3 | 0 | -4.19 | -11.65 | -40.54 | 8.82 | 0.7939 | 83.16 | 75.00 |
| draftkings | away | favourite 65-80% | 172 | 101 | 71 | 0 | -81.28 | -18.15 | -26.34 | -8.78 | 0.9997 | 71.05 | 58.72 |
| draftkings | away | underdog <20% | 222 | 21 | 201 | 0 | -118.05 | -53.18 | -68.65 | -36.85 | 1.0000 | 14.60 | 9.46 |
| pinnacle | home | favourite 80%+ | 200 | 181 | 19 | 0 | 27.42 | 4.57 | 0.66 | 8.17 | 0.0255 | 85.43 | 90.50 |
| pinnacle | home | favourite 65-80% | 540 | 383 | 157 | 0 | -51.14 | -3.54 | -7.84 | 0.59 | 0.9176 | 72.25 | 70.93 |
| pinnacle | home | underdog <20% | 12 | 4 | 8 | 0 | 6.46 | 53.83 | -60.50 | 168.17 | 0.1930 | 17.55 | 33.33 |
| pinnacle | away | favourite 80%+ | 12 | 8 | 4 | 0 | -7.58 | -21.07 | -50.38 | 7.20 | 0.9070 | 82.45 | 66.67 |
| pinnacle | away | favourite 65-80% | 160 | 93 | 67 | 0 | -77.30 | -18.70 | -27.43 | -10.16 | 0.9998 | 71.10 | 58.13 |
| pinnacle | away | underdog <20% | 200 | 19 | 181 | 0 | -101.38 | -50.69 | -66.89 | -32.78 | 1.0000 | 14.57 | 9.50 |



## r2_leads2.py

### H3, the home underdog against the spread (blind)

| rule | prices | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H3 home underdog ATS, home line > 0 | DraftKings close | all 2021-22 on | 454 | 259 | 191 | 4 | 48.34 | 9.72 | 2.44 | 16.89 | 0.0126 |
| H3 home underdog ATS, home line > 0 | DraftKings close | season 2022 | 93 | 55 | 37 | 1 | 14.45 | 14.33 | -1.83 | 30.41 | 0.0746 |
| H3 home underdog ATS, home line > 0 | DraftKings close | season 2023 | 77 | 44 | 33 | 0 | 7.60 | 8.95 | -7.03 | 24.68 | 0.1740 |
| H3 home underdog ATS, home line > 0 | DraftKings close | season 2024 | 81 | 39 | 40 | 2 | -5.34 | -6.12 | -26.14 | 12.32 | 0.7020 |
| H3 home underdog ATS, home line > 0 | DraftKings close | season 2025 | 79 | 45 | 33 | 1 | 8.64 | 10.06 | -8.76 | 29.20 | 0.1938 |
| H3 home underdog ATS, home line > 0 | DraftKings close | season 2026 | 94 | 64 | 30 | 0 | 31.09 | 29.75 | 16.37 | 43.64 | 0.0002 |
| H3 home underdog ATS, home line > 0 | DraftKings close | season 2027 | 30 | 12 | 18 | 0 | -8.10 | -24.06 | -49.70 | 1.39 | 0.9467 |
| H3 home underdog ATS, home line > 0 | DraftKings close | early half of each season | 220 | 128 | 89 | 3 | 29.76 | 12.40 | 1.70 | 22.72 | 0.0282 |
| H3 home underdog ATS, home line > 0 | DraftKings close | late half of each season | 234 | 131 | 102 | 1 | 18.58 | 7.23 | -3.09 | 17.25 | 0.1250 |
| H3 home underdog ATS, home line > 0 | DraftKings close | without its 10 best dates | 431 | 236 | 191 | 4 | 25.34 | 5.37 | -2.04 | 12.60 | 0.1133 |
| H3 home underdog ATS, home line > 0 | DraftKings close | price median -110, range -122 to -102 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |
| H3 home underdog ATS, home line > 0 | best decidable close | all 2021-22 on | 455 | 262 | 189 | 4 | 54.54 | 11.00 | 3.63 | 17.95 | 0.0053 |
| H3 home underdog ATS, home line > 0 | DraftKings 15utc | all 2021-22 on | 447 | 261 | 182 | 4 | 61.45 | 12.57 | 5.36 | 20.15 | 0.0026 |
| H3 home underdog ATS, home line >= +1.5 | DraftKings close | all 2021-22 on | 412 | 238 | 170 | 4 | 50.53 | 11.22 | 3.61 | 19.11 | 0.0073 |
| H3 home underdog ATS, home line >= +1.5 | best decidable close | all 2021-22 on | 414 | 242 | 168 | 4 | 57.73 | 12.82 | 5.12 | 20.35 | 0.0025 |
| H3 home underdog ATS, home line >= +1.5 | DraftKings 15utc | all 2021-22 on | 405 | 235 | 166 | 4 | 53.04 | 12.01 | 4.09 | 20.17 | 0.0070 |
| H3 home underdog ATS, home line >= +3 | DraftKings close | all 2021-22 on | 285 | 165 | 117 | 3 | 35.66 | 11.47 | 2.22 | 20.40 | 0.0186 |
| H3 home underdog ATS, home line >= +3 | best decidable close | all 2021-22 on | 286 | 166 | 117 | 3 | 37.22 | 11.98 | 2.86 | 21.84 | 0.0167 |
| H3 home underdog ATS, home line >= +3 | DraftKings 15utc | all 2021-22 on | 281 | 159 | 119 | 3 | 28.29 | 9.22 | 0.01 | 18.41 | 0.0478 |
| H3 home underdog ATS, home line >= +5 | DraftKings close | all 2021-22 on | 156 | 96 | 57 | 3 | 32.80 | 19.41 | 6.72 | 31.56 | 0.0047 |
| H3 home underdog ATS, home line >= +5 | best decidable close | all 2021-22 on | 158 | 98 | 57 | 3 | 34.98 | 20.51 | 7.83 | 32.28 | 0.0032 |
| H3 home underdog ATS, home line >= +5 | DraftKings 15utc | all 2021-22 on | 156 | 96 | 58 | 2 | 32.20 | 18.87 | 6.91 | 31.01 | 0.0055 |
| H3 mirror: the away favourite ATS (away line < 0) | DraftKings close | all 2021-22 on | 1,209 | 594 | 601 | 14 | -68.02 | -5.16 | -9.36 | -0.96 | 0.9774 |
| H3 mirror: the away favourite ATS (away line < 0) | best decidable close | all 2021-22 on | 1,208 | 596 | 598 | 14 | -59.34 | -4.53 | -8.76 | -0.18 | 0.9591 |
| H3 mirror: the away favourite ATS (away line < 0) | DraftKings 15utc | all 2021-22 on | 1,216 | 597 | 601 | 18 | -65.28 | -4.94 | -9.33 | -0.83 | 0.9744 |
| control: home ATS, every game | DraftKings close | all 2021-22 on | 1,663 | 860 | 785 | 18 | -2.53 | -0.14 | -3.90 | 3.59 | 0.5248 |
| control: home ATS, every game | best decidable close | all 2021-22 on | 1,663 | 860 | 785 | 18 | 2.01 | 0.11 | -3.71 | 3.79 | 0.4802 |
| control: home ATS, every game | DraftKings 15utc | all 2021-22 on | 1,663 | 862 | 779 | 22 | 7.67 | 0.43 | -3.31 | 4.08 | 0.4246 |

### H3 walk-forward (buckets chosen from earlier seasons only)

| rule | prices | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H3 walk-forward: home in buckets positive over every earlier season | DraftKings close | 2022-23 on | 674 | 360 | 306 | 8 | 23.18 | 3.16 | -2.55 | 8.88 | 0.1857 |
| H3 walk-forward | DraftKings close | season 2023 | 121 | 69 | 51 | 1 | 12.85 | 9.71 | -3.24 | 23.39 | 0.1144 |
| H3 walk-forward | DraftKings close | season 2024 | 226 | 109 | 113 | 4 | -15.39 | -6.30 | -15.92 | 3.66 | 0.8534 |
| H3 walk-forward | DraftKings close | season 2025 | 130 | 69 | 59 | 2 | 4.13 | 2.93 | -10.93 | 16.49 | 0.3647 |
| H3 walk-forward | DraftKings close | season 2026 | 151 | 96 | 54 | 1 | 36.70 | 22.15 | 11.54 | 33.37 | 0.0003 |
| H3 walk-forward | DraftKings close | season 2027 | 46 | 17 | 29 | 0 | -15.11 | -29.60 | -50.61 | -8.90 | 0.9894 |
| H3 walk-forward: home in buckets positive over every earlier season | best decidable close | 2022-23 on | 678 | 362 | 308 | 8 | 24.90 | 3.39 | -2.40 | 9.22 | 0.1708 |
| H3 walk-forward: home in buckets positive over every earlier season | DraftKings 15utc | 2022-23 on | 668 | 361 | 300 | 7 | 32.62 | 4.49 | -1.34 | 10.18 | 0.1041 |

### H2, home against the spread by the club's previous-season attendance (blind)

| rule | prices | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H2 home ATS, previous-season attendance top tercile | DraftKings close | all 2021-22 on | 456 | 252 | 200 | 4 | 32.42 | 6.53 | -0.86 | 13.44 | 0.0682 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | season 2023 | 89 | 58 | 30 | 1 | 25.00 | 25.87 | 11.32 | 40.12 | 0.0016 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | season 2024 | 106 | 55 | 50 | 1 | -0.42 | -0.36 | -14.58 | 14.45 | 0.5162 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | season 2025 | 108 | 53 | 53 | 2 | -4.97 | -4.27 | -18.26 | 11.18 | 0.6812 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | season 2026 | 120 | 66 | 54 | 0 | 6.99 | 5.31 | -9.34 | 20.20 | 0.2741 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | season 2027 | 33 | 20 | 13 | 0 | 5.82 | 16.12 | -4.46 | 42.35 | 0.1267 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | early half of each season | 222 | 114 | 105 | 3 | -1.55 | -0.64 | -10.83 | 10.24 | 0.5401 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | late half of each season | 234 | 138 | 95 | 1 | 33.97 | 13.28 | 3.48 | 22.66 | 0.0114 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | without its 10 best dates | 434 | 230 | 200 | 4 | 10.42 | 2.21 | -4.64 | 9.57 | 0.3060 |
| H2 home ATS, previous-season attendance top tercile | DraftKings close | price median -110, range -120 to 100 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |
| H2 home ATS, previous-season attendance top tercile | best decidable close | all 2021-22 on | 456 | 253 | 199 | 4 | 36.06 | 7.31 | -0.22 | 14.09 | 0.0476 |
| H2 home ATS, previous-season attendance top tercile | DraftKings 15utc | all 2021-22 on | 456 | 254 | 199 | 3 | 35.51 | 7.13 | -0.28 | 14.12 | 0.0507 |
| H2 home ATS, previous-season attendance top half | DraftKings close | all 2021-22 on | 691 | 377 | 304 | 10 | 43.03 | 5.75 | 0.23 | 11.09 | 0.0425 |
| H2 home ATS, previous-season attendance top half | best decidable close | all 2021-22 on | 691 | 378 | 303 | 10 | 47.23 | 6.35 | 0.95 | 11.81 | 0.0289 |
| H2 home ATS, previous-season attendance top half | DraftKings 15utc | all 2021-22 on | 691 | 379 | 306 | 6 | 43.53 | 5.78 | 0.37 | 11.06 | 0.0411 |
| H2 home ATS, previous-season attendance top quartile | DraftKings close | all 2021-22 on | 359 | 198 | 157 | 4 | 25.76 | 6.60 | -0.99 | 15.23 | 0.0888 |
| H2 home ATS, previous-season attendance top quartile | best decidable close | all 2021-22 on | 359 | 199 | 156 | 4 | 28.67 | 7.38 | -0.13 | 15.91 | 0.0655 |
| H2 home ATS, previous-season attendance top quartile | DraftKings 15utc | all 2021-22 on | 359 | 200 | 156 | 3 | 28.80 | 7.34 | -0.23 | 16.05 | 0.0658 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | all 2021-22 on | 475 | 235 | 235 | 5 | -23.46 | -4.53 | -11.31 | 2.15 | 0.8627 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | season 2023 | 102 | 52 | 50 | 0 | -3.45 | -3.07 | -19.17 | 10.67 | 0.6311 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | season 2024 | 108 | 50 | 57 | 1 | -12.85 | -10.89 | -24.79 | 2.24 | 0.9085 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | season 2025 | 112 | 53 | 56 | 3 | -8.55 | -7.13 | -21.69 | 7.73 | 0.7836 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | season 2026 | 121 | 58 | 62 | 1 | -9.63 | -7.30 | -21.27 | 5.92 | 0.8068 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | season 2027 | 32 | 22 | 10 | 0 | 11.02 | 31.28 | 5.05 | 61.39 | 0.0338 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | early half of each season | 237 | 116 | 118 | 3 | -14.37 | -5.57 | -14.85 | 4.12 | 0.8382 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | late half of each season | 238 | 119 | 117 | 2 | -9.09 | -3.51 | -14.36 | 7.18 | 0.7048 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | without its 10 best dates | 451 | 211 | 235 | 5 | -47.46 | -9.67 | -16.39 | -2.87 | 0.9906 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings close | price median -110, range -118 to 102 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |
| H2 mirror: away ATS, previous-season attendance bottom tercile | best decidable close | all 2021-22 on | 475 | 236 | 234 | 5 | -19.74 | -3.84 | -10.70 | 2.92 | 0.8225 |
| H2 mirror: away ATS, previous-season attendance bottom tercile | DraftKings 15utc | all 2021-22 on | 475 | 232 | 236 | 7 | -27.19 | -5.27 | -12.28 | 1.51 | 0.8991 |

Overlap at the DraftKings close: home-underdog games 454, top-tercile attendance games 456, both 75.

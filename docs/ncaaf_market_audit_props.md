# College football player props: the market-relative rule, 2025 and 2026, at stored prices

> Part of the 2026-11-10 NCAAF market audit (`docs/ncaaf_market_audit.md`). Written by a background
> study in that session. Its scripts are in `scripts/ncaaf_search/audit_2026_11/props/`; the output
> files it names are in the audit's work folder (`paths.py`), outside the repo.

Built by `gen_report.py` from the files `main.py`, `verdict.py` and `alt.py` wrote. Results are in units (1 unit to win, risk capped at 3). No database was read or written; no paid call was made.

## Verdict

**No. Nothing clears.** Of the pre-declared cells (season x named reference x cut, four variants), 0 clear all four tests. The largest pre-declared cell is consensus 2025 at the 0.02 cut with 107 graded bets, so the 150-bet bar is never reached in a single season.

Pre-declared test, 2 percentage point cut (the loosest):

- pinnacle 2026: 42 bets, 14-28-0, -13.61 units, ROI -32.4%, 95% interval (-60.7%, +1.4%).
- bovada 2026: 23 bets, 9-14-0, -3.27 units, ROI -15.6%, 95% interval (-67.0%, +23.0%).
- consensus 2026: 64 bets, 30-34-0, +1.23 units, ROI +2.3%, 95% interval (-21.6%, +29.2%).
- betonlineag 2025: 42 bets, 20-22-0, +2.31 units, ROI +6.3%, 95% interval (-20.5%, +33.2%).
- consensus 2025: 107 bets, 54-53-0, +6.82 units, ROI +6.9%, 95% interval (-14.1%, +31.2%).

The placebo fails again. Used as the "reference", FanDuel returns +13.5% over 111 bets in 2025; in 2026 William Hill returns +25.4% over 34 and Fliff +13.1% over 68. At that cut Pinnacle has the lowest ROI of the 8 references with a bet on the 2026 board.

One variant was added after the first grid was seen, and is labelled POST-HOC everywhere: the edge definition the repo's NFL rule actually uses (reference fair probability minus the soft book's own de-vigged probability, which admits many more bets). On 2026 it gives Pinnacle 558 bets at the 0.02 cut for +1.3% (-5.1%, +8.7%), close value -0.0033 on 264 bets, and it gets worse as the cut tightens (-12.4% over 49 bets at 0.05). Bovada: 147 bets, -6.0%. No season cell clears under it either (0 of the post-hoc season cells).

One pooled two-season row meets all four tests as written: S4_POSTHOC_repo_edge_def, consensus, cut 0.03: 466 bets, +7.11 units, ROI +1.45%, interval (-6.1%, +10.4%), 2025 +2.33% over 279, 2026 +0.04% over 187, close value +0.0071 on 104 bets. It is not counted as a pass, for four reasons: the variant was added after results were seen; the tests were declared for single-season cells and this is a pooled row whose 2026 season is flat; its interval spans zero; and the cuts either side of it lose (-4.3% at 0.02 and -0.6% at 0.04).

Why the board cannot carry this rule (all measured below):

- DraftKings and BetRivers post no two-way college props in either season, so neither can be de-vigged.
- In 2026 only FanDuel (10,457 two-way quotes) and Hard Rock (11,004) are two-way in volume; William Hill has 2,589 and stops in September, BetMGM has 551.
- Where a reference quotes the same player, market and pull, the soft book is on the same line only 52% of the time against Pinnacle and 66% against Bovada (2026), 52% against BetOnline (2025).
- From 2026-09-29 on, FanDuel and Hard Rock all but stopped disagreeing at equal lines. Soft sides reaching the 0.02 cut from that date to the end of the capture: bovada 0 of 10,558; consensus 0 of 7,190; pinnacle 29 of 7,538.

The alternate ladders, the only place DraftKings can be tested, do not clear either: the largest named cell has 87 bets (section 8).

## 1. What was run

Definitions were written at the top of `main.py` before any result was produced (the first-run copy is `main_v1_as_first_run.py`, its grid `grid_v1_first_run.csv`; the re-run reproduces all 324 first-run cells exactly).

- **Pre-game**: `snapshot_at` parsed to UTC, before `commence_time`, type not in-play.
- **Markets**: pass yards, pass TDs, completions, attempts, interceptions, rush yards, reception yards, receptions.
- **Two-way quotes only**; multiplicative de-vig of the reference.
- **Bettable books**: draftkings, fanduel, betmgm, williamhill_us, fanatics, betrivers, hardrockbet.
- **References**: pinnacle, bovada, betonlineag, consensus (median de-vigged probability of at least 2 other books at the same line, same pull).
- **Edge**: reference no-vig probability minus the soft book's implied probability of its price (vig included). Equal line required.
- **Cuts**: 0.02, 0.03, 0.04, 0.05, 0.06, 0.08.
- **Lock**: one bet per player, market and game, at the first pull where any bettable side crosses the cut; largest edge if several.
- **Grading**: the player's stat in `ncaaf_player_game_log`; no row in a logged game for a known player is no action; pushes are 0.
- **Stake**: 1 unit to win, risk capped at 3. ROI = units / units risked.
- **Interval**: 95%, resampling game dates, 2,000 draws. **Halves**: split at the season's median game date (2025: on or before 2025-10-31; 2026: on or before 2026-10-10). Pooled rows use the two seasons as the two halves.
- **Clears** only if: at least 150 bets; positive in both halves; interval lower bound above 0 or close value positive; ROI above every retail placebo reference with at least 50 bets at the same season and cut.

**Variants run: 5, 648 cells in total** (season x reference x cut, pooled rows included).

| variant | what changes | declared | references | cells | cells with a bet |
|---|---|---|---|---|---|
| PRIMARY | nothing (the fixed method) | before results | 4 named + 10 placebo | 252 | 144 |
| S1_power_devig | power de-vig instead of multiplicative | before results | 4 named | 48 | 28 |
| S2_null_stat_no_action | a logged player with an empty stat column is no action instead of 0 | before results | 4 named | 48 | 27 |
| S3_one_way_soft_allowed | a one-way soft price may be bet (lets BetRivers' over-only quotes in) | before results | 4 named | 48 | 27 |
| S4_POSTHOC_repo_edge_def | edge = reference fair minus the soft book's DE-VIGGED probability (the repo's `find_bets`) | AFTER the first grid was seen | 4 named + 10 placebo | 252 | 162 |

## 2. Data inventory (measured)

### 2.1 Two-way coverage, eight over/under markets, pre-game

A quote is one book, one pull, one line. `fanatics` and `draftkings` have no row here at all.

| season | book | bettable | quotes | two-way quotes | two-way share | games | games two-way | propositions two-way |
|---|---|---|---|---|---|---|---|---|
| 2025 | betmgm | True | 3038 | 3038 | 100.0% | 292 | 292 | 3038 |
| 2025 | betonlineag | False | 4567 | 4563 | 99.9% | 378 | 378 | 4563 |
| 2025 | betrivers | True | 455 | 0 | 0.0% | 73 | 0 | 0 |
| 2025 | espnbet | False | 2337 | 2337 | 100.0% | 229 | 229 | 2337 |
| 2025 | fanduel | True | 4915 | 4915 | 100.0% | 421 | 421 | 4915 |
| 2025 | fliff | False | 6461 | 6423 | 99.4% | 464 | 464 | 6423 |
| 2025 | hardrockbet | True | 5892 | 5892 | 100.0% | 318 | 318 | 5892 |
| 2025 | pinnacle | False | 568 | 568 | 100.0% | 59 | 59 | 568 |
| 2025 | williamhill_us | True | 2125 | 2125 | 100.0% | 252 | 252 | 2125 |
| 2026 | betmgm | True | 553 | 551 | 99.6% | 41 | 41 | 416 |
| 2026 | betrivers | True | 2896 | 0 | 0.0% | 133 | 0 | 0 |
| 2026 | bovada | False | 6584 | 6581 | 100.0% | 342 | 342 | 3516 |
| 2026 | espnbet | False | 1677 | 1677 | 100.0% | 94 | 94 | 876 |
| 2026 | fanduel | True | 10457 | 10457 | 100.0% | 363 | 363 | 5506 |
| 2026 | fliff | False | 3541 | 3541 | 100.0% | 72 | 72 | 1688 |
| 2026 | hardrockbet | True | 11004 | 11004 | 100.0% | 331 | 331 | 5589 |
| 2026 | pinnacle | False | 6570 | 6570 | 100.0% | 254 | 254 | 3117 |
| 2026 | williamhill_us | True | 2589 | 2589 | 100.0% | 106 | 106 | 1330 |

DraftKings and BetRivers, every pre-game row by kind (two-way = both prices present):

| season | book | kind | rows | two-way rows |
|---|---|---|---|---|
| 2025 | betrivers | anytime TD | 310 | 0 |
| 2025 | betrivers | eight over/under markets | 455 | 0 |
| 2025 | draftkings | anytime TD | 8218 | 0 |
| 2026 | betrivers | alternate ladders | 11765 | 0 |
| 2026 | betrivers | anytime TD | 4226 | 0 |
| 2026 | betrivers | eight over/under markets | 2896 | 0 |
| 2026 | draftkings | alternate ladders | 130548 | 0 |
| 2026 | draftkings | anytime TD | 25668 | 0 |

**Anytime TD**: 2025: 43,083 pre-game rows, 0 with a No price; 2026: 84,595 pre-game rows, 0 with a No price. No book posts both sides, so it is skipped.

**Alternate ladders**: 2026: 306,971 pre-game rows, 0 two-way. All one-way. Section 8 tests them.

### 2.2 Snapshot cadence

Every pull carries one timestamp. 2026 has 118 distinct pre-game pull stamps; the smallest gap between two is 134.9 minutes, so the 10-minute window is exactly one pull.

Pulls per game before kickoff (number of games):

| season | 1 | 2 | 3 |
|---|---|---|---|
| 2025 | 522 | 0 | 0 |
| 2026 | 97 | 136 | 162 |

Hours from pull to kickoff, per (game, pull):

| season | count | mean | std | min | 25% | 50% | 75% | max |
|---|---|---|---|---|---|---|---|---|
| 2025 | 522.0 | 23.83 | 1.01 | 19.56 | 24.07 | 24.07 | 24.07 | 30.66 |
| 2026 | 855.0 | 5.34 | 3.55 | 0.1 | 2.17 | 5.51 | 8.42 | 14.4 |

2026 (game, pull) pairs by pull time, Eastern: 09:35 = 348, 11:20 = 27, 13:35 = 296, 18:35 = 184.

2025 is one pull per game about 24 hours out, so in 2025 the first-signal lock is that one pull and there is no later quote to measure close value against. 2026 is game-day only (first pull 9:35am ET).

### 2.3 The 2026 capture changed at the end of September

Two-way quotes by week and book:

| week (Tue-Mon) | betmgm | bovada | espnbet | fanduel | fliff | hardrockbet | pinnacle | williamhill_us |
|---|---|---|---|---|---|---|---|---|
| 2026-09-01/2026-09-07 | 0 | 193 | 265 | 324 | 0 | 721 | 160 | 201 |
| 2026-09-08/2026-09-14 | 14 | 327 | 394 | 777 | 1658 | 1662 | 415 | 335 |
| 2026-09-15/2026-09-21 | 77 | 412 | 1018 | 1217 | 1883 | 1809 | 406 | 974 |
| 2026-09-22/2026-09-28 | 25 | 640 | 0 | 1355 | 0 | 2141 | 661 | 1079 |
| 2026-09-29/2026-10-05 | 11 | 581 | 0 | 299 | 0 | 735 | 656 | 0 |
| 2026-10-06/2026-10-12 | 137 | 898 | 0 | 1338 | 0 | 906 | 752 | 0 |
| 2026-10-13/2026-10-19 | 42 | 942 | 0 | 1441 | 0 | 910 | 890 | 0 |
| 2026-10-20/2026-10-26 | 0 | 794 | 0 | 1149 | 0 | 704 | 871 | 0 |
| 2026-10-27/2026-11-02 | 113 | 828 | 0 | 1196 | 0 | 705 | 853 | 0 |
| 2026-11-03/2026-11-09 | 132 | 966 | 0 | 1361 | 0 | 711 | 906 | 0 |

| week (Tue-Mon) | FanDuel/Hard Rock pairs at one line, one pull | mean gap in de-vigged over probability | share of pairs 3pp+ apart |
|---|---|---|---|
| 2026-09-01/2026-09-07 | 76 | 0.0280 | 43.4% |
| 2026-09-08/2026-09-14 | 205 | 0.0245 | 36.6% |
| 2026-09-15/2026-09-21 | 306 | 0.0216 | 28.8% |
| 2026-09-22/2026-09-28 | 400 | 0.0184 | 23.8% |
| 2026-09-29/2026-10-05 | 43 | 0.0075 | 9.3% |
| 2026-10-06/2026-10-12 | 138 | 0.0051 | 2.9% |
| 2026-10-13/2026-10-19 | 212 | 0.0036 | 1.4% |
| 2026-10-20/2026-10-26 | 101 | 0.0032 | 0.0% |
| 2026-10-27/2026-11-02 | 115 | 0.0076 | 7.0% |
| 2026-11-03/2026-11-09 | 103 | 0.0039 | 0.0% |

Books whose last pre-game row of any kind is before the end of the capture (2026-11-07): espnbet last seen 2026-09-19; fliff last seen 2026-09-19; rebet last seen 2026-09-19; williamhill_us last seen 2026-09-26.

Hard Rock two-way markets that end early: player_pass_interceptions last quoted 2026-09-26; player_pass_tds last quoted 2026-09-26. Over the same days the gap between FanDuel and Hard Rock at an equal line falls to a fraction of what it was. The cause is not established here; the effect is that from October the soft books almost never price an equal line 2 points better than a reference.

Soft sides compared at an equal line, and how many reach the 0.02 cut, by week (2026):

| week (Tue-Mon) | pinnacle: sides compared | pinnacle: sides at 0.02+ | bovada: sides compared | bovada: sides at 0.02+ | consensus: sides compared | consensus: sides at 0.02+ |
|---|---|---|---|---|---|---|
| 2026-09-01/2026-09-07 | 298 | 4 | 664 | 6 | 698 | 9 |
| 2026-09-08/2026-09-14 | 1016 | 3 | 990 | 4 | 1772 | 28 |
| 2026-09-15/2026-09-21 | 1282 | 9 | 1594 | 6 | 3370 | 45 |
| 2026-09-22/2026-09-28 | 2098 | 8 | 2336 | 15 | 3468 | 19 |
| 2026-09-29/2026-10-05 | 528 | 2 | 536 | 0 | 446 | 0 |
| 2026-10-06/2026-10-12 | 1448 | 7 | 2036 | 0 | 1400 | 0 |
| 2026-10-13/2026-10-19 | 1724 | 6 | 2262 | 0 | 1640 | 0 |
| 2026-10-20/2026-10-26 | 1246 | 5 | 1780 | 0 | 1200 | 0 |
| 2026-10-27/2026-11-02 | 1304 | 6 | 1788 | 0 | 1270 | 0 |
| 2026-11-03/2026-11-09 | 1288 | 3 | 2156 | 0 | 1234 | 0 |

### 2.4 Matching odds to results

Games with a pre-game quote in the eight markets, matched to a log game (every one found a log game):

| season | direct | teams_within_1_day |
|---|---|---|
| 2025 | 390 | 132 |
| 2026 | 332 | 63 |

Propositions (player, market, game), all books, eight markets. Name-match rate counts a known player with no row that day as matched (he is identified; he did not play):

| season | propositions | matched exactly | matched by fallback | known player, no row (no action) | name never in log (dropped) | two players one name (dropped) | name-match rate | graded share |
|---|---|---|---|---|---|---|---|---|
| 2025 | 9400 | 8612 | 109 | 426 | 249 | 4 | 97.3% | 92.8% |
| 2026 | 8006 | 7312 | 135 | 399 | 158 | 2 | 98.0% | 93.0% |

The fallback matched 20 distinct spellings, for example: Steve Angeli = Steven Angeli; Gio Lopez = Giovanni Lopez; Cam Ross = Cameron Ross; Joshua Meredith = Josh Meredith; Kam Perry = Kamryn Perry; Jam Miller = Jamarion Miller; Cam Edwards = Camryn Edwards; Joe Labas = Joey Labas. All are in `inv_fallback_names.csv`.

A logged player whose stat column is empty (a back with no catch) is graded as 0: 2025: 142 of 8,721 matched propositions; 2026: 136 of 7,447 matched propositions. Variant S2 treats them as no action instead.

### 2.5 How much of the soft board each reference can be compared with

| season | reference | soft two-way quotes | reference quotes the same player/market/pull | at the same line | equal-line share | propositions compared | games compared |
|---|---|---|---|---|---|---|---|
| 2025 | pinnacle | 15970 | 1636 | 896 | 54.8% | 436 | 59 |
| 2026 | pinnacle | 24601 | 11697 | 6116 | 52.3% | 2667 | 250 |
| 2026 | bovada | 24601 | 12172 | 8071 | 66.3% | 3377 | 336 |
| 2025 | betonlineag | 15970 | 11565 | 6018 | 52.0% | 3127 | 375 |
| 2025 | consensus | 15970 |  | 7161 |  | 3129 | 404 |
| 2026 | consensus | 24601 |  | 8249 |  | 3039 | 323 |

### 2.6 Is the grading right? De-vigged probability against what happened

| book | season | de-vigged over probability band | propositions | mean de-vigged over | share that went over |
|---|---|---|---|---|---|
| pinnacle | 2025 | (0.0, 0.4] | 10 | 0.370 | 0.600 |
| pinnacle | 2025 | (0.4, 0.47] | 21 | 0.449 | 0.429 |
| pinnacle | 2025 | (0.47, 0.53] | 479 | 0.500 | 0.445 |
| pinnacle | 2025 | (0.53, 0.6] | 9 | 0.553 | 0.667 |
| pinnacle | 2025 | (0.6, 1.0] | 8 | 0.630 | 0.250 |
| pinnacle | 2026 | (0.0, 0.4] | 119 | 0.359 | 0.361 |
| pinnacle | 2026 | (0.4, 0.47] | 257 | 0.448 | 0.401 |
| pinnacle | 2026 | (0.47, 0.53] | 2329 | 0.498 | 0.490 |
| pinnacle | 2026 | (0.53, 0.6] | 173 | 0.555 | 0.566 |
| pinnacle | 2026 | (0.6, 1.0] | 70 | 0.639 | 0.643 |
| bovada | 2026 | (0.0, 0.4] | 131 | 0.367 | 0.389 |
| bovada | 2026 | (0.4, 0.47] | 113 | 0.439 | 0.389 |
| bovada | 2026 | (0.47, 0.53] | 2896 | 0.500 | 0.491 |
| bovada | 2026 | (0.53, 0.6] | 115 | 0.560 | 0.600 |
| bovada | 2026 | (0.6, 1.0] | 94 | 0.634 | 0.681 |
| betonlineag | 2025 | (0.0, 0.4] | 152 | 0.362 | 0.375 |
| betonlineag | 2025 | (0.4, 0.47] | 335 | 0.442 | 0.418 |
| betonlineag | 2025 | (0.47, 0.53] | 3507 | 0.499 | 0.486 |
| betonlineag | 2025 | (0.53, 0.6] | 186 | 0.562 | 0.527 |
| betonlineag | 2025 | (0.6, 1.0] | 83 | 0.628 | 0.530 |

Looking only at bands of 100 or more propositions: for the three references the share that went over falls from one band to the next 0 times in 9 steps; for FanDuel and Hard Rock 2 times in 16 (`sanity_calibration.csv`). Outcomes follow the quoted probabilities, which is what correct grading looks like. Separately, `crosscheck.py` recomputed five cells with different code (plain loops over the raw rows) and got the same bets, record, units and risk in all five, and matched six graded results to the raw log rows (`crosscheck_out.txt`).

### 2.7 The baseline: bet every proposition blind

| season | side | bets | W-L-P | units | ROI | 95% interval |
|---|---|---|---|---|---|---|
| 2025 | over | 7411 | 3536-3875-0 | -919.17 | -10.6% | (-13.3%, -7.9%) |
| 2026 | over | 7357 | 3618-3739-0 | -573.10 | -6.8% | (-9.8%, -3.7%) |
| 2025 | under | 7411 | 3875-3536-0 | -219.07 | -2.5% | (-5.3%, +0.2%) |
| 2026 | under | 7357 | 3739-3618-0 | -459.46 | -5.3% | (-8.0%, -2.5%) |

First bettable two-way quote per proposition, first book in the bettable order. Any rule has to beat these.

## 3. Results: the pre-declared test

### 3.1 Full grid, named references (every cut, losing and empty cells included)

Close value = the reference's last pre-kick de-vigged probability at the bet's line minus the implied probability of the price taken, on bets where that last pull is later than the bet's own. "No action" = player did not play; "dropped" = name not matched.

| season | reference | cut | bets | W-L-P | units | risked | ROI | 95% interval | 1st half | 2nd half | close value (n / mean) | price min / med / max | shorter than -200 | no action | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025 | pinnacle | 0.02 | 2 | 0-2-0 | -1.53 | 1.5 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 0 | +116 / +133 / +150 | 0.0% | 0 | 0 |
| 2025 | pinnacle | 0.03 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | pinnacle | 0.04 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | pinnacle | 0.05 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | pinnacle | 0.06 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | pinnacle | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2026 | pinnacle | 0.02 | 42 | 14-28-0 | -13.61 | 42.1 | -32.4% | (-60.7%, +1.4%) | 27 / -52.8% | 15 / -0.2% | 14 / +0.0216 | -164 / -112 / +194 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.03 | 18 | 7-11-0 | -3.10 | 16.8 | -18.5% | (-61.3%, +33.5%) | 12 / -47.5% | 6 / +36.5% | 8 / +0.0243 | -116 / -108 / +194 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.04 | 5 | 2-3-0 | -0.82 | 4.5 | -18.1% | (-100.0%, +80.2%) | 5 / -18.1% | 0 | 3 / +0.0472 | -115 / +105 / +185 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.05 | 4 | 1-3-0 | -1.75 | 3.3 | -53.1% | (-100.0%, +79.6%) | 4 / -53.1% | 0 | 2 / +0.0566 | -115 / +130 / +185 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.06 | 1 | 0-1-0 | -0.95 | 1.0 | -100.0% |  | 1 / -100.0% | 0 | 1 / +0.0613 | +105 / +105 / +105 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025+2026 | pinnacle | 0.02 | 44 | 14-30-0 | -15.14 | 43.6 | -34.7% | (-62.8%, -1.6%) | 2 / -100.0% | 42 / -32.4% | 14 / +0.0216 | -164 / -111 / +194 | 0.0% | 0 | 0 |
| 2025+2026 | pinnacle | 0.03 | 18 | 7-11-0 | -3.10 | 16.8 | -18.5% | (-61.3%, +33.5%) | 0 | 18 / -18.5% | 8 / +0.0243 | -116 / -108 / +194 | 0.0% | 0 | 0 |
| 2025+2026 | pinnacle | 0.04 | 5 | 2-3-0 | -0.82 | 4.5 | -18.1% | (-100.0%, +80.2%) | 0 | 5 / -18.1% | 3 / +0.0472 | -115 / +105 / +185 | 0.0% | 0 | 0 |
| 2025+2026 | pinnacle | 0.05 | 4 | 1-3-0 | -1.75 | 3.3 | -53.1% | (-100.0%, +79.6%) | 0 | 4 / -53.1% | 2 / +0.0566 | -115 / +130 / +185 | 0.0% | 0 | 0 |
| 2025+2026 | pinnacle | 0.06 | 1 | 0-1-0 | -0.95 | 1.0 | -100.0% |  | 0 | 1 / -100.0% | 1 / +0.0613 | +105 / +105 / +105 | 0.0% | 0 | 0 |
| 2025+2026 | pinnacle | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | bovada | 0.02 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | bovada | 0.03 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | bovada | 0.04 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | bovada | 0.05 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | bovada | 0.06 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | bovada | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2026 | bovada | 0.02 | 23 | 9-14-0 | -3.27 | 20.9 | -15.6% | (-67.0%, +23.0%) | 23 / -15.6% | 0 | 10 / +0.0328 | -170 / +125 / +175 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.03 | 11 | 4-7-0 | -2.67 | 10.7 | -25.0% | (-100.0%, +10.7%) | 11 / -25.0% | 0 | 5 / +0.0402 | -170 / +120 / +175 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.04 | 4 | 1-3-0 | -1.72 | 3.3 | -52.7% | (-100.0%, -3.1%) | 4 / -52.7% | 0 | 3 / +0.0476 | -105 / +122 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.05 | 3 | 1-2-0 | -0.60 | 2.1 | -27.9% | (-100.0%, +185.0%) | 3 / -27.9% | 0 | 2 / +0.0502 | +105 / +155 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.06 | 2 | 0-2-0 | -1.60 | 1.6 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0428 | +105 / +130 / +155 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025+2026 | bovada | 0.02 | 23 | 9-14-0 | -3.27 | 20.9 | -15.6% | (-67.0%, +23.0%) | 0 | 23 / -15.6% | 10 / +0.0328 | -170 / +125 / +175 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.03 | 11 | 4-7-0 | -2.67 | 10.7 | -25.0% | (-100.0%, +10.7%) | 0 | 11 / -25.0% | 5 / +0.0402 | -170 / +120 / +175 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.04 | 4 | 1-3-0 | -1.72 | 3.3 | -52.7% | (-100.0%, -3.1%) | 0 | 4 / -52.7% | 3 / +0.0476 | -105 / +122 / +185 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.05 | 3 | 1-2-0 | -0.60 | 2.1 | -27.9% | (-100.0%, +185.0%) | 0 | 3 / -27.9% | 2 / +0.0502 | +105 / +155 / +185 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.06 | 2 | 0-2-0 | -1.60 | 1.6 | -100.0% | (-100.0%, -100.0%) | 0 | 2 / -100.0% | 1 / +0.0428 | +105 / +130 / +155 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | betonlineag | 0.02 | 42 | 20-22-0 | +2.31 | 36.9 | +6.3% | (-20.5%, +33.2%) | 23 / -2.7% | 19 / +18.2% | 0 | -165 / +135 / +188 | 0.0% | 3 | 1 |
| 2025 | betonlineag | 0.03 | 25 | 12-13-0 | +0.97 | 21.3 | +4.6% | (-39.3%, +43.1%) | 13 / -34.6% | 12 / +46.9% | 0 | -165 / +135 / +175 | 0.0% | 1 | 0 |
| 2025 | betonlineag | 0.04 | 16 | 6-10-0 | -2.81 | 13.6 | -20.7% | (-62.9%, +19.1%) | 9 / -55.2% | 7 / +24.8% | 0 | -165 / +135 / +175 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.05 | 7 | 4-3-0 | +1.29 | 5.8 | +22.2% | (-51.6%, +113.3%) | 2 / +18.1% | 5 / +23.6% | 0 | -140 / +145 / +175 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.06 | 1 | 0-1-0 | -1.40 | 1.4 | -100.0% |  | 0 | 1 / -100.0% | 0 | -140 / -140 / -140 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2026 | betonlineag | 0.02 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2026 | betonlineag | 0.03 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2026 | betonlineag | 0.04 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2026 | betonlineag | 0.05 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2026 | betonlineag | 0.06 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2026 | betonlineag | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025+2026 | betonlineag | 0.02 | 42 | 20-22-0 | +2.31 | 36.9 | +6.3% | (-20.5%, +33.2%) | 42 / +6.3% | 0 | 0 | -165 / +135 / +188 | 0.0% | 3 | 1 |
| 2025+2026 | betonlineag | 0.03 | 25 | 12-13-0 | +0.97 | 21.3 | +4.6% | (-39.3%, +43.1%) | 25 / +4.6% | 0 | 0 | -165 / +135 / +175 | 0.0% | 1 | 0 |
| 2025+2026 | betonlineag | 0.04 | 16 | 6-10-0 | -2.81 | 13.6 | -20.7% | (-62.9%, +19.1%) | 16 / -20.7% | 0 | 0 | -165 / +135 / +175 | 0.0% | 0 | 0 |
| 2025+2026 | betonlineag | 0.05 | 7 | 4-3-0 | +1.29 | 5.8 | +22.2% | (-51.6%, +113.3%) | 7 / +22.2% | 0 | 0 | -140 / +145 / +175 | 0.0% | 0 | 0 |
| 2025+2026 | betonlineag | 0.06 | 1 | 0-1-0 | -1.40 | 1.4 | -100.0% |  | 1 / -100.0% | 0 | 0 | -140 / -140 / -140 | 0.0% | 0 | 0 |
| 2025+2026 | betonlineag | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025 | consensus | 0.02 | 107 | 54-53-0 | +6.82 | 99.2 | +6.9% | (-14.1%, +31.2%) | 43 / +18.3% | 64 / -0.8% | 0 | -195 / +110 / +190 | 0.0% | 8 | 3 |
| 2025 | consensus | 0.03 | 67 | 35-32-0 | +6.64 | 60.3 | +11.0% | (-12.1%, +40.1%) | 27 / +28.5% | 40 / -0.3% | 0 | -165 / +115 / +188 | 0.0% | 4 | 2 |
| 2025 | consensus | 0.04 | 44 | 21-23-0 | +0.46 | 38.5 | +1.2% | (-23.9%, +30.9%) | 17 / +2.0% | 27 / +0.7% | 0 | -165 / +120 / +188 | 0.0% | 2 | 1 |
| 2025 | consensus | 0.05 | 26 | 15-11-0 | +6.20 | 21.7 | +28.6% | (-11.9%, +64.9%) | 8 / +44.7% | 18 / +21.7% | 0 | -140 / +128 / +175 | 0.0% | 1 | 1 |
| 2025 | consensus | 0.06 | 15 | 8-7-0 | +2.17 | 12.7 | +17.1% | (-27.9%, +55.9%) | 5 / +39.7% | 10 / +6.7% | 0 | -140 / +130 / +175 | 0.0% | 0 | 1 |
| 2025 | consensus | 0.08 | 5 | 4-1-0 | +3.23 | 4.2 | +76.5% | (-7.8%, +130.4%) | 2 / +109.1% | 3 / +51.5% | 0 | +100 / +120 / +150 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.02 | 64 | 30-34-0 | +1.23 | 54.5 | +2.3% | (-21.6%, +29.2%) | 64 / +2.3% | 0 | 35 / +0.0226 | -144 / +119 / +180 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.03 | 32 | 16-16-0 | +2.78 | 26.2 | +10.6% | (-15.7%, +42.4%) | 32 / +10.6% | 0 | 15 / +0.0293 | -124 / +120 / +180 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.04 | 14 | 6-8-0 | -0.77 | 11.3 | -6.8% | (-41.0%, +44.8%) | 14 / -6.8% | 0 | 8 / +0.0494 | -124 / +125 / +185 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.05 | 7 | 3-4-0 | -0.22 | 5.5 | -4.0% | (-79.7%, +106.0%) | 7 / -4.0% | 0 | 4 / +0.0568 | +104 / +125 / +185 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.06 | 2 | 1-1-0 | +0.05 | 1.9 | +2.6% | (-100.0%, +110.0%) | 2 / +2.6% | 0 | 2 / +0.0684 | +105 / +108 / +110 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.08 | 0 | 0-0-0 |  |  |  |  | 0 | 0 |  |  |  | 0 | 0 |
| 2025+2026 | consensus | 0.02 | 171 | 84-87-0 | +8.05 | 153.7 | +5.2% | (-10.4%, +22.7%) | 107 / +6.9% | 64 / +2.3% | 35 / +0.0226 | -195 / +115 / +190 | 0.0% | 8 | 3 |
| 2025+2026 | consensus | 0.03 | 99 | 51-48-0 | +9.42 | 86.5 | +10.9% | (-7.1%, +32.3%) | 67 / +11.0% | 32 / +10.6% | 15 / +0.0293 | -165 / +115 / +188 | 0.0% | 4 | 2 |
| 2025+2026 | consensus | 0.04 | 58 | 27-31-0 | -0.31 | 49.8 | -0.6% | (-20.9%, +24.8%) | 44 / +1.2% | 14 / -6.8% | 8 / +0.0494 | -165 / +120 / +188 | 0.0% | 2 | 1 |
| 2025+2026 | consensus | 0.05 | 33 | 18-15-0 | +5.99 | 27.2 | +22.0% | (-14.4%, +58.5%) | 26 / +28.6% | 7 / -4.0% | 4 / +0.0568 | -140 / +125 / +185 | 0.0% | 1 | 1 |
| 2025+2026 | consensus | 0.06 | 17 | 9-8-0 | +2.22 | 14.5 | +15.3% | (-27.6%, +54.0%) | 15 / +17.1% | 2 / +2.6% | 2 / +0.0684 | -140 / +120 / +175 | 0.0% | 0 | 1 |
| 2025+2026 | consensus | 0.08 | 5 | 4-1-0 | +3.23 | 4.2 | +76.5% | (-7.8%, +130.4%) | 5 / +76.5% | 0 | 0 | +100 / +120 / +150 | 0.0% | 0 | 0 |

### 3.2 The placebo: every book as the reference (bets / ROI)

draftkings, betrivers, rebet and fanatics have no two-way quotes and so produce no bets as a reference.

| season | reference | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|
| 2025 | betonlineag | 42 / +6.3% | 25 / +4.6% | 16 / -20.7% | 7 / +22.2% | 1 / -100.0% | 0 |
| 2025 | bovada | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | consensus | 107 / +6.9% | 67 / +11.0% | 44 / +1.2% | 26 / +28.6% | 15 / +17.1% | 5 / +76.5% |
| 2025 | pinnacle | 2 / -100.0% | 0 | 0 | 0 | 0 | 0 |
| 2025 | betmgm | 44 / +7.7% | 30 / +14.0% | 16 / +5.2% | 8 / +24.9% | 5 / +39.6% | 0 |
| 2025 | betrivers | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | draftkings | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | espnbet | 38 / -10.2% | 25 / -8.3% | 15 / -18.6% | 11 / -25.8% | 7 / -12.5% | 4 / +8.9% |
| 2025 | fanatics | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | fanduel | 111 / +13.5% | 71 / +17.7% | 49 / +21.1% | 30 / +27.6% | 16 / +39.2% | 9 / +20.8% |
| 2025 | fliff | 151 / -2.9% | 103 / -4.0% | 62 / -10.3% | 40 / -8.6% | 20 / -2.5% | 6 / -29.5% |
| 2025 | hardrockbet | 130 / -6.8% | 90 / -10.3% | 55 / -24.5% | 32 / -12.7% | 17 / -27.0% | 7 / +31.2% |
| 2025 | rebet | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | williamhill_us | 29 / +30.3% | 14 / +29.1% | 9 / +11.7% | 3 / +108.3% | 1 / +150.0% | 1 / +150.0% |
| 2026 | betonlineag | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | bovada | 23 / -15.6% | 11 / -25.0% | 4 / -52.7% | 3 / -27.9% | 2 / -100.0% | 0 |
| 2026 | consensus | 64 / +2.3% | 32 / +10.6% | 14 / -6.8% | 7 / -4.0% | 2 / +2.6% | 0 |
| 2026 | pinnacle | 42 / -32.4% | 18 / -18.5% | 5 / -18.1% | 4 / -53.1% | 1 / -100.0% | 0 |
| 2026 | betmgm | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | betrivers | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | draftkings | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | espnbet | 28 / +12.7% | 18 / -8.6% | 9 / -0.4% | 3 / -24.9% | 1 / +125.0% | 0 |
| 2026 | fanatics | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | fanduel | 75 / -4.8% | 38 / +5.7% | 21 / +28.3% | 11 / +45.4% | 6 / +10.9% | 1 / -100.0% |
| 2026 | fliff | 68 / +13.1% | 39 / +13.0% | 17 / +4.9% | 6 / +11.7% | 0 | 0 |
| 2026 | hardrockbet | 88 / -4.5% | 49 / -10.3% | 21 / -16.2% | 8 / -30.4% | 4 / +2.3% | 1 / +108.0% |
| 2026 | rebet | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | williamhill_us | 34 / +25.4% | 17 / +29.6% | 10 / +36.7% | 3 / +40.7% | 1 / +110.0% | 0 |
| 2025+2026 | betonlineag | 42 / +6.3% | 25 / +4.6% | 16 / -20.7% | 7 / +22.2% | 1 / -100.0% | 0 |
| 2025+2026 | bovada | 23 / -15.6% | 11 / -25.0% | 4 / -52.7% | 3 / -27.9% | 2 / -100.0% | 0 |
| 2025+2026 | consensus | 171 / +5.2% | 99 / +10.9% | 58 / -0.6% | 33 / +22.0% | 17 / +15.3% | 5 / +76.5% |
| 2025+2026 | pinnacle | 44 / -34.7% | 18 / -18.5% | 5 / -18.1% | 4 / -53.1% | 1 / -100.0% | 0 |
| 2025+2026 | betmgm | 44 / +7.7% | 30 / +14.0% | 16 / +5.2% | 8 / +24.9% | 5 / +39.6% | 0 |
| 2025+2026 | betrivers | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025+2026 | draftkings | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025+2026 | espnbet | 66 / -1.0% | 43 / -8.4% | 24 / -12.5% | 14 / -25.7% | 8 / +2.5% | 4 / +8.9% |
| 2025+2026 | fanatics | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025+2026 | fanduel | 186 / +6.4% | 109 / +13.7% | 70 / +23.0% | 41 / +31.9% | 22 / +31.6% | 10 / +8.6% |
| 2025+2026 | fliff | 219 / +2.1% | 142 / +0.8% | 79 / -7.3% | 46 / -6.3% | 20 / -2.5% | 6 / -29.5% |
| 2025+2026 | hardrockbet | 218 / -5.8% | 139 / -10.3% | 76 / -22.0% | 40 / -16.9% | 21 / -21.1% | 8 / +42.1% |
| 2025+2026 | rebet | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025+2026 | williamhill_us | 63 / +27.8% | 31 / +29.3% | 19 / +23.5% | 6 / +75.7% | 2 / +126.9% | 1 / +150.0% |

Placebo rows with their intervals at the two loosest cuts:

| season | reference | cut | bets | W-L-P | units | risked | ROI | 95% interval | 1st half | 2nd half | close value (n / mean) | price min / med / max | shorter than -200 | no action | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025 | betmgm | 0.02 | 44 | 23-21-0 | +3.35 | 43.4 | +7.7% | (-12.4%, +33.5%) | 25 / -6.9% | 19 / +25.4% | 0 | -195 / +115 / +198 | 0.0% | 1 | 2 |
| 2025 | betmgm | 0.03 | 30 | 16-14-0 | +4.03 | 28.7 | +14.0% | (-20.4%, +50.3%) | 18 / -13.7% | 12 / +48.3% | 0 | -165 / +120 / +198 | 0.0% | 1 | 2 |
| 2025 | espnbet | 0.02 | 38 | 17-21-0 | -3.87 | 38.0 | -10.2% | (-44.4%, +31.7%) | 15 / +24.4% | 23 / -31.8% | 0 | -195 / +110 / +180 | 0.0% | 5 | 2 |
| 2025 | espnbet | 0.03 | 25 | 11-14-0 | -1.92 | 23.3 | -8.3% | (-41.6%, +38.6%) | 9 / +26.0% | 16 / -25.9% | 0 | -155 / +110 / +180 | 0.0% | 3 | 2 |
| 2025 | fanduel | 0.02 | 111 | 61-50-0 | +14.69 | 108.4 | +13.5% | (-9.0%, +40.2%) | 38 / +12.7% | 73 / +14.0% | 0 | -195 / +105 / +190 | 0.0% | 5 | 3 |
| 2025 | fanduel | 0.03 | 71 | 40-31-0 | +12.04 | 67.9 | +17.7% | (-6.3%, +46.1%) | 23 / +18.5% | 48 / +17.3% | 0 | -165 / +105 / +175 | 0.0% | 3 | 2 |
| 2025 | fliff | 0.02 | 151 | 69-82-0 | -4.02 | 139.1 | -2.9% | (-18.8%, +14.7%) | 90 / -0.5% | 61 / -6.2% | 0 | -165 / +110 / +230 | 0.0% | 7 | 3 |
| 2025 | fliff | 0.03 | 103 | 46-57-0 | -3.65 | 91.3 | -4.0% | (-19.5%, +14.9%) | 60 / +0.2% | 43 / -9.4% | 0 | -165 / +115 / +230 | 0.0% | 5 | 2 |
| 2025 | hardrockbet | 0.02 | 130 | 56-74-0 | -7.90 | 116.4 | -6.8% | (-30.8%, +14.7%) | 45 / +7.5% | 85 / -14.0% | 0 | -166 / +112 / +290 | 0.0% | 4 | 4 |
| 2025 | hardrockbet | 0.03 | 90 | 37-53-0 | -8.42 | 81.7 | -10.3% | (-35.2%, +13.7%) | 28 / +1.9% | 62 / -15.7% | 0 | -166 / +110 / +290 | 0.0% | 3 | 2 |
| 2025 | williamhill_us | 0.02 | 29 | 19-10-0 | +9.36 | 30.9 | +30.3% | (-7.8%, +61.2%) | 14 / +1.2% | 15 / +54.6% | 0 | -170 / -110 / +190 | 0.0% | 3 | 2 |
| 2025 | williamhill_us | 0.03 | 14 | 9-5-0 | +4.37 | 15.0 | +29.1% | (-33.4%, +71.8%) | 6 / -24.6% | 8 / +61.0% | 0 | -165 / -112 / +155 | 0.0% | 2 | 1 |
| 2026 | espnbet | 0.02 | 28 | 15-13-0 | +3.25 | 25.5 | +12.7% | (-20.8%, +58.3%) | 28 / +12.7% | 0 | 15 / +0.0311 | -170 / +112 / +175 | 0.0% | 0 | 0 |
| 2026 | espnbet | 0.03 | 18 | 8-10-0 | -1.41 | 16.4 | -8.6% | (-32.3%, +49.6%) | 18 / -8.6% | 0 | 11 / +0.0330 | -170 / +115 / +175 | 0.0% | 0 | 0 |
| 2026 | fanduel | 0.02 | 75 | 34-41-0 | -3.38 | 69.7 | -4.8% | (-22.1%, +30.2%) | 74 / -6.4% | 1 / +95.2% | 39 / +0.0288 | -170 / +115 / +180 | 0.0% | 0 | 0 |
| 2026 | fanduel | 0.03 | 38 | 19-19-0 | +1.92 | 33.9 | +5.7% | (-13.4%, +41.0%) | 37 / +2.8% | 1 / +95.2% | 19 / +0.0396 | -145 / +115 / +175 | 0.0% | 0 | 0 |
| 2026 | fliff | 0.02 | 68 | 37-31-0 | +8.28 | 63.4 | +13.1% | (-54.3%, +35.8%) | 68 / +13.1% | 0 | 33 / +0.0205 | -158 / +110 / +180 | 0.0% | 1 | 0 |
| 2026 | fliff | 0.03 | 39 | 21-18-0 | +4.61 | 35.5 | +13.0% | (-41.7%, +46.0%) | 39 / +13.0% | 0 | 20 / +0.0218 | -132 / +115 / +180 | 0.0% | 1 | 0 |
| 2026 | hardrockbet | 0.02 | 88 | 42-46-0 | -4.03 | 88.8 | -4.5% | (-31.4%, +17.9%) | 87 / -3.5% | 1 / -100.0% | 40 / +0.0155 | -174 / +103 / +180 | 0.0% | 0 | 0 |
| 2026 | hardrockbet | 0.03 | 49 | 22-27-0 | -5.08 | 49.4 | -10.3% | (-36.1%, +12.5%) | 48 / -8.5% | 1 / -100.0% | 21 / +0.0227 | -174 / +104 / +180 | 0.0% | 0 | 0 |
| 2026 | williamhill_us | 0.02 | 34 | 20-14-0 | +7.74 | 30.5 | +25.4% | (-11.7%, +54.4%) | 34 / +25.4% | 0 | 11 / +0.0319 | -145 / +118 / +175 | 0.0% | 0 | 0 |
| 2026 | williamhill_us | 0.03 | 17 | 10-7-0 | +4.21 | 14.2 | +29.6% | (-18.6%, +66.1%) | 17 / +29.6% | 0 | 5 / +0.0417 | -115 / +120 / +185 | 0.0% | 0 | 0 |
| 2025+2026 | betmgm | 0.02 | 44 | 23-21-0 | +3.35 | 43.4 | +7.7% | (-12.4%, +33.5%) | 44 / +7.7% | 0 | 0 | -195 / +115 / +198 | 0.0% | 1 | 2 |
| 2025+2026 | betmgm | 0.03 | 30 | 16-14-0 | +4.03 | 28.7 | +14.0% | (-20.4%, +50.3%) | 30 / +14.0% | 0 | 0 | -165 / +120 / +198 | 0.0% | 1 | 2 |
| 2025+2026 | espnbet | 0.02 | 66 | 32-34-0 | -0.63 | 63.6 | -1.0% | (-26.6%, +26.1%) | 38 / -10.2% | 28 / +12.7% | 15 / +0.0311 | -195 / +110 / +180 | 0.0% | 5 | 2 |
| 2025+2026 | espnbet | 0.03 | 43 | 19-24-0 | -3.34 | 39.7 | -8.4% | (-31.8%, +23.6%) | 25 / -8.3% | 18 / -8.6% | 11 / +0.0330 | -170 / +110 / +180 | 0.0% | 3 | 2 |
| 2025+2026 | fanduel | 0.02 | 186 | 95-91-0 | +11.31 | 178.1 | +6.4% | (-10.2%, +28.9%) | 111 / +13.5% | 75 / -4.8% | 39 / +0.0288 | -195 / +110 / +190 | 0.0% | 5 | 3 |
| 2025+2026 | fanduel | 0.03 | 109 | 59-50-0 | +13.96 | 101.8 | +13.7% | (-3.8%, +35.9%) | 71 / +17.7% | 38 / +5.7% | 19 / +0.0396 | -165 / +110 / +175 | 0.0% | 3 | 2 |
| 2025+2026 | fliff | 0.02 | 219 | 106-113-0 | +4.26 | 202.5 | +2.1% | (-15.2%, +17.0%) | 151 / -2.9% | 68 / +13.1% | 33 / +0.0205 | -165 / +110 / +230 | 0.0% | 8 | 3 |
| 2025+2026 | fliff | 0.03 | 142 | 67-75-0 | +0.96 | 126.8 | +0.8% | (-14.8%, +17.5%) | 103 / -4.0% | 39 / +13.0% | 20 / +0.0218 | -165 / +115 / +230 | 0.0% | 6 | 2 |
| 2025+2026 | hardrockbet | 0.02 | 218 | 98-120-0 | -11.93 | 205.2 | -5.8% | (-22.8%, +9.7%) | 130 / -6.8% | 88 / -4.5% | 40 / +0.0155 | -174 / +108 / +290 | 0.0% | 4 | 4 |
| 2025+2026 | hardrockbet | 0.03 | 139 | 59-80-0 | -13.51 | 131.1 | -10.3% | (-28.3%, +7.4%) | 90 / -10.3% | 49 / -10.3% | 21 / +0.0227 | -174 / +106 / +290 | 0.0% | 3 | 2 |
| 2025+2026 | williamhill_us | 0.02 | 63 | 39-24-0 | +17.10 | 61.4 | +27.8% | (+3.1%, +48.2%) | 29 / +30.3% | 34 / +25.4% | 11 / +0.0319 | -170 / +110 / +190 | 0.0% | 3 | 2 |
| 2025+2026 | williamhill_us | 0.03 | 31 | 19-12-0 | +8.58 | 29.3 | +29.3% | (-7.4%, +58.2%) | 14 / +29.1% | 17 / +29.6% | 5 / +0.0417 | -165 / +110 / +185 | 0.0% | 2 | 1 |

### 3.3 Rank of each named reference among all references with a bet

| season | reference | cut | bets | ROI | rank vs retail references | best retail reference with 50+ bets |
|---|---|---|---|---|---|---|
| 2025 | pinnacle | 0.02 | 2 | -100.0% | 7 of 7 | best placebo fanduel +0.1355 |
| 2025 | betonlineag | 0.02 | 42 | +6.3% | 4 of 7 | best placebo fanduel +0.1355 |
| 2025 | consensus | 0.02 | 107 | +6.9% | 4 of 7 | best placebo fanduel +0.1355 |
| 2025 | betonlineag | 0.03 | 25 | +4.6% | 4 of 7 | best placebo fanduel +0.1772 |
| 2025 | consensus | 0.03 | 67 | +11.0% | 4 of 7 | best placebo fanduel +0.1772 |
| 2025 | betonlineag | 0.04 | 16 | -20.7% | 6 of 7 | best placebo fliff -0.1032 |
| 2025 | consensus | 0.04 | 44 | +1.2% | 4 of 7 | best placebo fliff -0.1032 |
| 2025 | betonlineag | 0.05 | 7 | +22.2% | 4 of 7 | no placebo with >=50 bets |
| 2025 | consensus | 0.05 | 26 | +28.6% | 2 of 7 | no placebo with >=50 bets |
| 2025 | betonlineag | 0.06 | 1 | -100.0% | 7 of 7 | no placebo with >=50 bets |
| 2025 | consensus | 0.06 | 15 | +17.1% | 4 of 7 | no placebo with >=50 bets |
| 2025 | consensus | 0.08 | 5 | +76.5% | 2 of 6 | no placebo with >=50 bets |
| 2025+2026 | pinnacle | 0.02 | 44 | -34.7% | 7 of 7 | best placebo williamhill_us +0.2783 |
| 2025+2026 | bovada | 0.02 | 23 | -15.6% | 7 of 7 | best placebo williamhill_us +0.2783 |
| 2025+2026 | betonlineag | 0.02 | 42 | +6.3% | 4 of 7 | best placebo williamhill_us +0.2783 |
| 2025+2026 | consensus | 0.02 | 171 | +5.2% | 4 of 7 | best placebo williamhill_us +0.2783 |
| 2025+2026 | pinnacle | 0.03 | 18 | -18.5% | 7 of 7 | best placebo fanduel +0.1371 |
| 2025+2026 | bovada | 0.03 | 11 | -25.0% | 7 of 7 | best placebo fanduel +0.1371 |
| 2025+2026 | betonlineag | 0.03 | 25 | +4.6% | 4 of 7 | best placebo fanduel +0.1371 |
| 2025+2026 | consensus | 0.03 | 99 | +10.9% | 4 of 7 | best placebo fanduel +0.1371 |
| 2025+2026 | pinnacle | 0.04 | 5 | -18.1% | 6 of 7 | best placebo fanduel +0.2302 |
| 2025+2026 | bovada | 0.04 | 4 | -52.7% | 7 of 7 | best placebo fanduel +0.2302 |
| 2025+2026 | betonlineag | 0.04 | 16 | -20.7% | 6 of 7 | best placebo fanduel +0.2302 |
| 2025+2026 | consensus | 0.04 | 58 | -0.6% | 4 of 7 | best placebo fanduel +0.2302 |
| 2025+2026 | pinnacle | 0.05 | 4 | -53.1% | 7 of 7 | no placebo with >=50 bets |
| 2025+2026 | bovada | 0.05 | 3 | -27.9% | 7 of 7 | no placebo with >=50 bets |
| 2025+2026 | betonlineag | 0.05 | 7 | +22.2% | 4 of 7 | no placebo with >=50 bets |
| 2025+2026 | consensus | 0.05 | 33 | +22.0% | 4 of 7 | no placebo with >=50 bets |
| 2025+2026 | pinnacle | 0.06 | 1 | -100.0% | 7 of 7 | no placebo with >=50 bets |
| 2025+2026 | bovada | 0.06 | 2 | -100.0% | 7 of 7 | no placebo with >=50 bets |
| 2025+2026 | betonlineag | 0.06 | 1 | -100.0% | 7 of 7 | no placebo with >=50 bets |
| 2025+2026 | consensus | 0.06 | 17 | +15.3% | 4 of 7 | no placebo with >=50 bets |
| 2025+2026 | consensus | 0.08 | 5 | +76.5% | 2 of 6 | no placebo with >=50 bets |
| 2026 | pinnacle | 0.02 | 42 | -32.4% | 6 of 6 | best placebo fliff +0.1306 |
| 2026 | bovada | 0.02 | 23 | -15.6% | 6 of 6 | best placebo fliff +0.1306 |
| 2026 | consensus | 0.02 | 64 | +2.3% | 4 of 6 | best placebo fliff +0.1306 |
| 2026 | pinnacle | 0.03 | 18 | -18.5% | 6 of 6 | no placebo with >=50 bets |
| 2026 | bovada | 0.03 | 11 | -25.0% | 6 of 6 | no placebo with >=50 bets |
| 2026 | consensus | 0.03 | 32 | +10.6% | 3 of 6 | no placebo with >=50 bets |
| 2026 | pinnacle | 0.04 | 5 | -18.1% | 6 of 6 | no placebo with >=50 bets |
| 2026 | bovada | 0.04 | 4 | -52.7% | 6 of 6 | no placebo with >=50 bets |
| 2026 | consensus | 0.04 | 14 | -6.8% | 5 of 6 | no placebo with >=50 bets |
| 2026 | pinnacle | 0.05 | 4 | -53.1% | 6 of 6 | no placebo with >=50 bets |
| 2026 | bovada | 0.05 | 3 | -27.9% | 5 of 6 | no placebo with >=50 bets |
| 2026 | consensus | 0.05 | 7 | -4.0% | 4 of 6 | no placebo with >=50 bets |
| 2026 | pinnacle | 0.06 | 1 | -100.0% | 5 of 5 | no placebo with >=50 bets |
| 2026 | bovada | 0.06 | 2 | -100.0% | 5 of 5 | no placebo with >=50 bets |
| 2026 | consensus | 0.06 | 2 | +2.6% | 4 of 5 | no placebo with >=50 bets |

### 3.4 By market, by soft book, by side (named references)

**By market** (bets / units / ROI):

| season | reference | market | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|---|
| 2025 | betonlineag | player_pass_tds | 39 / +2.95u / +8.6% | 23 / +2.62u / +13.3% | 14 / -1.16u / -9.7% | 7 / +1.29u / +22.2% | 1 / -1.40u / -100.0% |  |
| 2025 | betonlineag | player_reception_yds | 1 / +1.00u / +110.0% |  |  |  |  |  |
| 2025 | betonlineag | player_receptions | 2 / -1.65u / -100.0% | 2 / -1.65u / -100.0% | 2 / -1.65u / -100.0% |  |  |  |
| 2025 | consensus | player_pass_tds | 63 / +13.69u / +23.2% | 37 / +10.67u / +32.3% | 24 / +2.94u / +14.3% | 14 / +5.03u / +44.6% | 6 / +0.29u / +5.8% | 2 / +2.00u / +133.3% |
| 2025 | consensus | player_reception_yds | 1 / +1.00u / +110.0% |  |  |  |  |  |
| 2025 | consensus | player_receptions | 42 / -8.87u / -23.1% | 29 / -5.03u / -19.0% | 19 / -3.48u / -20.4% | 12 / +1.18u / +11.3% | 9 / +1.89u / +24.5% | 3 / +1.23u / +45.2% |
| 2025 | consensus | player_rush_yds | 1 / +1.00u / +120.0% | 1 / +1.00u / +120.0% | 1 / +1.00u / +120.0% |  |  |  |
| 2025 | pinnacle | player_pass_tds | 2 / -1.53u / -100.0% |  |  |  |  |  |
| 2026 | bovada | player_pass_tds | 22 / -2.43u / -12.1% | 10 / -1.84u / -18.7% | 4 / -1.72u / -52.7% | 3 / -0.60u / -27.9% | 2 / -1.60u / -100.0% |  |
| 2026 | bovada | player_reception_yds | 1 / -0.83u / -100.0% | 1 / -0.83u / -100.0% |  |  |  |  |
| 2026 | consensus | player_pass_tds | 22 / -2.75u / -16.7% | 9 / +0.41u / +6.4% | 3 / -0.62u / -28.8% | 3 / -0.60u / -27.9% | 1 / -0.95u / -100.0% |  |
| 2026 | consensus | player_reception_yds | 1 / -0.83u / -100.0% | 1 / -0.83u / -100.0% |  |  |  |  |
| 2026 | consensus | player_receptions | 39 / +4.72u / +13.4% | 22 / +3.21u / +16.9% | 11 / -0.15u / -1.6% | 4 / +0.38u / +11.4% | 1 / +1.00u / +110.0% |  |
| 2026 | consensus | player_rush_yds | 2 / +0.09u / +5.0% |  |  |  |  |  |
| 2026 | pinnacle | player_pass_tds | 15 / -6.83u / -57.1% | 9 / -1.34u / -20.7% | 3 / -0.67u / -30.2% | 3 / -0.60u / -27.9% | 1 / -0.95u / -100.0% |  |
| 2026 | pinnacle | player_pass_yds | 6 / +1.73u / +26.0% | 2 / -0.15u / -6.5% | 1 / +1.00u / +87.0% |  |  |  |
| 2026 | pinnacle | player_reception_yds | 9 / -1.59u / -15.6% | 3 / +0.85u / +24.9% | 1 / -1.15u / -100.0% | 1 / -1.15u / -100.0% |  |  |
| 2026 | pinnacle | player_rush_yds | 12 / -6.92u / -52.1% | 4 / -2.46u / -53.7% |  |  |  |  |

**By soft book** (bets / units / ROI):

| season | reference | book | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|---|
| 2025 | betonlineag | betmgm | 4 / +0.80u / +19.5% |  |  |  |  |  |
| 2025 | betonlineag | fanduel | 4 / +0.35u / +9.6% | 2 / -1.65u / -100.0% | 2 / -1.65u / -100.0% |  |  |  |
| 2025 | betonlineag | hardrockbet | 32 / +0.73u / +2.6% | 21 / +2.19u / +11.9% | 12 / -1.59u / -14.9% | 5 / +0.86u / +19.0% | 1 / -1.40u / -100.0% |  |
| 2025 | betonlineag | williamhill_us | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% |  |  |
| 2025 | consensus | betmgm | 5 / +3.44u / +76.4% | 1 / +1.00u / +170.0% |  |  |  |  |
| 2025 | consensus | fanduel | 15 / -2.00u / -15.3% | 9 / -2.29u / -30.4% | 6 / -3.35u / -68.6% | 2 / -1.44u / -100.0% | 2 / -1.44u / -100.0% |  |
| 2025 | consensus | hardrockbet | 85 / +4.94u / +6.2% | 55 / +7.50u / +14.7% | 36 / +3.38u / +10.5% | 22 / +7.21u / +38.0% | 13 / +3.61u / +32.1% | 5 / +3.23u / +76.5% |
| 2025 | consensus | williamhill_us | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% |  |  |
| 2025 | pinnacle | betmgm | 1 / -0.67u / -100.0% |  |  |  |  |  |
| 2025 | pinnacle | fanduel | 1 / -0.86u / -100.0% |  |  |  |  |  |
| 2026 | bovada | hardrockbet | 23 / -3.27u / -15.6% | 11 / -2.67u / -25.0% | 4 / -1.72u / -52.7% | 3 / -0.60u / -27.9% | 2 / -1.60u / -100.0% |  |
| 2026 | consensus | fanduel | 21 / +0.09u / +0.4% | 14 / -2.60u / -21.9% | 4 / -1.86u / -49.6% | 2 / -1.62u / -100.0% |  |  |
| 2026 | consensus | hardrockbet | 39 / +0.56u / +1.7% | 16 / +3.39u / +26.8% | 10 / +1.09u / +14.4% | 5 / +1.40u / +36.5% | 2 / +0.05u / +2.6% |  |
| 2026 | consensus | williamhill_us | 4 / +0.59u / +19.0% | 2 / +2.00u / +117.0% |  |  |  |  |
| 2026 | pinnacle | fanduel | 18 / -4.47u / -23.9% | 6 / +0.52u / +10.0% |  |  |  |  |
| 2026 | pinnacle | hardrockbet | 22 / -7.03u / -33.1% | 12 / -3.62u / -31.4% | 5 / -0.82u / -18.1% | 4 / -1.75u / -53.1% | 1 / -0.95u / -100.0% |  |
| 2026 | pinnacle | williamhill_us | 2 / -2.12u / -100.0% |  |  |  |  |  |

**By side** (bets / units / ROI):

| season | reference | side | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|---|
| 2025 | betonlineag | over | 16 / -3.28u / -26.0% | 9 / -3.09u / -46.8% | 6 / -2.78u / -63.9% | 2 / +0.26u / +19.8% |  |  |
| 2025 | betonlineag | under | 26 / +5.59u / +23.0% | 16 / +4.06u / +27.7% | 10 / -0.03u / -0.3% | 5 / +1.03u / +23.0% | 1 / -1.40u / -100.0% |  |
| 2025 | consensus | over | 50 / -0.12u / -0.3% | 32 / -3.15u / -11.5% | 19 / -4.89u / -31.6% | 10 / +1.46u / +19.2% | 6 / -0.85u / -17.7% | 2 / +0.23u / +13.4% |
| 2025 | consensus | under | 57 / +6.93u / +12.6% | 35 / +9.78u / +29.7% | 25 / +5.35u / +23.3% | 16 / +4.74u / +33.6% | 9 / +3.02u / +38.4% | 3 / +3.00u / +120.0% |
| 2025 | pinnacle | over | 2 / -1.53u / -100.0% |  |  |  |  |  |
| 2026 | bovada | over | 11 / +0.16u / +1.8% | 6 / +0.59u / +12.3% | 2 / +0.05u / +3.2% | 2 / +0.05u / +3.2% | 1 / -0.95u / -100.0% |  |
| 2026 | bovada | under | 12 / -3.42u / -28.0% | 5 / -3.26u / -55.2% | 2 / -1.76u / -100.0% | 1 / -0.65u / -100.0% | 1 / -0.65u / -100.0% |  |
| 2026 | consensus | over | 35 / +5.18u / +18.4% | 21 / +3.25u / +19.7% | 7 / -0.20u / -3.8% | 3 / +1.05u / +43.6% | 2 / +0.05u / +2.6% |  |
| 2026 | consensus | under | 29 / -3.95u / -15.0% | 11 / -0.47u / -4.8% | 7 / -0.57u / -9.5% | 4 / -1.26u / -41.3% |  |  |
| 2026 | pinnacle | over | 15 / -5.74u / -41.9% | 7 / -1.97u / -34.7% | 2 / +0.05u / +3.2% | 2 / +0.05u / +3.2% | 1 / -0.95u / -100.0% |  |
| 2026 | pinnacle | under | 27 / -7.87u / -27.8% | 11 / -1.12u / -10.1% | 3 / -0.86u / -28.7% | 2 / -1.80u / -100.0% |  |  |

## 4. Pre-declared sensitivities (named references)

### S1: power de-vig

| season | reference | cut | bets | W-L-P | units | risked | ROI | 95% interval | 1st half | 2nd half | close value (n / mean) | price min / med / max | shorter than -200 | no action | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025 | pinnacle | 0.02 | 2 | 1-1-0 | +0.14 | 2.2 | +6.2% | (-100.0%, +73.5%) | 2 / +6.2% | 0 | 0 | -136 / -106 / +116 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.02 | 59 | 27-32-0 | -7.39 | 67.2 | -11.0% | (-32.7%, +14.0%) | 33 / -25.0% | 26 / +5.5% | 21 / +0.0194 | -200 / -113 / +180 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.03 | 21 | 8-13-0 | -5.97 | 23.2 | -25.7% | (-71.3%, +26.7%) | 11 / -26.0% | 10 / -25.4% | 9 / +0.0222 | -200 / -112 / +185 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.04 | 8 | 5-3-0 | +2.18 | 7.9 | +27.6% | (-46.0%, +91.4%) | 5 / -18.1% | 3 / +88.5% | 4 / +0.0280 | -115 / -112 / +185 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.05 | 2 | 0-2-0 | -2.10 | 2.1 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0655 | -115 / -104 / +105 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.06 | 2 | 0-2-0 | -2.10 | 2.1 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0655 | -115 / -104 / +105 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.02 | 31 | 12-19-0 | -8.38 | 34.2 | -24.5% | (-67.4%, +7.8%) | 31 / -24.5% | 0 | 18 / +0.0251 | -180 / -105 / +175 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.03 | 11 | 5-6-0 | -1.15 | 11.7 | -9.8% | (-70.8%, +22.2%) | 11 / -9.8% | 0 | 7 / +0.0391 | -180 / +105 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.04 | 6 | 2-4-0 | -2.35 | 6.5 | -35.9% | (-100.0%, +17.8%) | 6 / -35.9% | 0 | 2 / +0.0472 | -170 / +100 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.05 | 2 | 0-2-0 | -1.60 | 1.6 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0459 | +105 / +130 / +155 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.06 | 2 | 0-2-0 | -1.60 | 1.6 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0459 | +105 / +130 / +155 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.02 | 47 | 29-18-0 | +11.16 | 53.7 | +20.8% | (-4.1%, +47.2%) | 23 / +16.9% | 24 / +24.2% | 0 | -260 / -105 / +175 | 2.1% | 1 | 2 |
| 2025 | betonlineag | 0.03 | 33 | 19-14-0 | +5.36 | 35.3 | +15.2% | (-10.5%, +43.4%) | 16 / +5.1% | 17 / +23.7% | 0 | -260 / +105 / +175 | 3.0% | 1 | 0 |
| 2025 | betonlineag | 0.04 | 17 | 10-7-0 | +3.19 | 17.4 | +18.4% | (-21.7%, +53.0%) | 8 / -24.8% | 9 / +50.5% | 0 | -260 / +105 / +175 | 5.9% | 0 | 0 |
| 2025 | betonlineag | 0.05 | 8 | 4-4-0 | -0.36 | 7.8 | -4.6% | (-58.3%, +65.2%) | 3 / -45.1% | 5 / +21.7% | 0 | -165 / +120 / +175 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.06 | 2 | 1-1-0 | -0.40 | 2.5 | -15.7% | (-100.0%, +87.0%) | 0 | 2 / -15.7% | 0 | -140 / -126 / -115 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.08 | 1 | 0-1-0 | -1.40 | 1.4 | -100.0% |  | 0 | 1 / -100.0% | 0 | -140 / -140 / -140 | 0.0% | 0 | 0 |
| 2025 | consensus | 0.02 | 117 | 61-56-0 | +3.37 | 129.4 | +2.6% | (-15.1%, +19.9%) | 44 / +14.4% | 73 / -4.5% | 0 | -300 / +100 / +188 | 2.6% | 6 | 4 |
| 2025 | consensus | 0.03 | 81 | 48-33-0 | +17.08 | 85.0 | +20.1% | (+1.6%, +41.5%) | 31 / +30.6% | 50 / +13.9% | 0 | -300 / +105 / +188 | 2.5% | 4 | 2 |
| 2025 | consensus | 0.04 | 52 | 29-23-0 | +6.88 | 53.5 | +12.9% | (-9.2%, +38.4%) | 19 / +14.5% | 33 / +11.9% | 0 | -260 / +105 / +175 | 1.9% | 2 | 1 |
| 2025 | consensus | 0.05 | 31 | 15-16-0 | -0.27 | 29.8 | -0.9% | (-33.3%, +38.9%) | 10 / +22.8% | 21 / -12.6% | 0 | -165 / +105 / +175 | 0.0% | 2 | 1 |
| 2025 | consensus | 0.06 | 18 | 11-7-0 | +4.10 | 17.0 | +24.1% | (-19.0%, +65.0%) | 7 / +13.9% | 11 / +30.7% | 0 | -165 / +112 / +150 | 0.0% | 1 | 1 |
| 2025 | consensus | 0.08 | 5 | 3-2-0 | +0.83 | 5.0 | +16.8% | (-67.0%, +108.2%) | 2 / +109.1% | 3 / -37.5% | 0 | -140 / +105 / +130 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.02 | 69 | 36-33-0 | +1.92 | 72.2 | +2.7% | (-26.0%, +21.1%) | 69 / +2.7% | 0 | 39 / +0.0211 | -180 / +102 / +180 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.03 | 36 | 20-16-0 | +3.70 | 35.3 | +10.5% | (-7.6%, +58.5%) | 36 / +10.5% | 0 | 17 / +0.0342 | -180 / +104 / +185 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.04 | 17 | 8-9-0 | -0.32 | 15.3 | -2.1% | (-27.1%, +77.6%) | 17 / -2.1% | 0 | 7 / +0.0485 | -126 / +110 / +185 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.05 | 6 | 2-4-0 | -1.80 | 5.5 | -32.7% | (-100.0%, +82.6%) | 6 / -32.7% | 0 | 2 / +0.0731 | -124 / +108 / +155 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.06 | 3 | 1-2-0 | -0.91 | 2.8 | -32.4% | (-100.0%, +110.0%) | 3 / -32.4% | 0 | 2 / +0.0731 | +104 / +105 / +110 | 0.0% | 0 | 0 |

Cells with no bet in this variant: 20 of 48.

### S2: empty stat column = no action

| season | reference | cut | bets | W-L-P | units | risked | ROI | 95% interval | 1st half | 2nd half | close value (n / mean) | price min / med / max | shorter than -200 | no action | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025 | pinnacle | 0.02 | 2 | 0-2-0 | -1.53 | 1.5 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 0 | +116 / +133 / +150 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.02 | 41 | 14-27-0 | -12.51 | 41.0 | -30.5% | (-59.5%, +6.3%) | 26 / -50.7% | 15 / -0.2% | 14 / +0.0216 | -164 / -112 / +194 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.03 | 18 | 7-11-0 | -3.10 | 16.8 | -18.5% | (-61.3%, +33.5%) | 12 / -47.5% | 6 / +36.5% | 8 / +0.0243 | -116 / -108 / +194 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.04 | 5 | 2-3-0 | -0.82 | 4.5 | -18.1% | (-100.0%, +80.2%) | 5 / -18.1% | 0 | 3 / +0.0472 | -115 / +105 / +185 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.05 | 4 | 1-3-0 | -1.75 | 3.3 | -53.1% | (-100.0%, +79.6%) | 4 / -53.1% | 0 | 2 / +0.0566 | -115 / +130 / +185 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.06 | 1 | 0-1-0 | -0.95 | 1.0 | -100.0% |  | 1 / -100.0% | 0 | 1 / +0.0613 | +105 / +105 / +105 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.02 | 23 | 9-14-0 | -3.27 | 20.9 | -15.6% | (-67.0%, +23.0%) | 23 / -15.6% | 0 | 10 / +0.0328 | -170 / +125 / +175 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.03 | 11 | 4-7-0 | -2.67 | 10.7 | -25.0% | (-100.0%, +10.7%) | 11 / -25.0% | 0 | 5 / +0.0402 | -170 / +120 / +175 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.04 | 4 | 1-3-0 | -1.72 | 3.3 | -52.7% | (-100.0%, -3.1%) | 4 / -52.7% | 0 | 3 / +0.0476 | -105 / +122 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.05 | 3 | 1-2-0 | -0.60 | 2.1 | -27.9% | (-100.0%, +185.0%) | 3 / -27.9% | 0 | 2 / +0.0502 | +105 / +155 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.06 | 2 | 0-2-0 | -1.60 | 1.6 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0428 | +105 / +130 / +155 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.02 | 42 | 20-22-0 | +2.31 | 36.9 | +6.3% | (-20.5%, +33.2%) | 23 / -2.7% | 19 / +18.2% | 0 | -165 / +135 / +188 | 0.0% | 3 | 1 |
| 2025 | betonlineag | 0.03 | 25 | 12-13-0 | +0.97 | 21.3 | +4.6% | (-39.3%, +43.1%) | 13 / -34.6% | 12 / +46.9% | 0 | -165 / +135 / +175 | 0.0% | 1 | 0 |
| 2025 | betonlineag | 0.04 | 16 | 6-10-0 | -2.81 | 13.6 | -20.7% | (-62.9%, +19.1%) | 9 / -55.2% | 7 / +24.8% | 0 | -165 / +135 / +175 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.05 | 7 | 4-3-0 | +1.29 | 5.8 | +22.2% | (-51.6%, +113.3%) | 2 / +18.1% | 5 / +23.6% | 0 | -140 / +145 / +175 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.06 | 1 | 0-1-0 | -1.40 | 1.4 | -100.0% |  | 0 | 1 / -100.0% | 0 | -140 / -140 / -140 | 0.0% | 0 | 0 |
| 2025 | consensus | 0.02 | 107 | 54-53-0 | +6.82 | 99.2 | +6.9% | (-14.1%, +31.2%) | 43 / +18.3% | 64 / -0.8% | 0 | -195 / +110 / +190 | 0.0% | 8 | 3 |
| 2025 | consensus | 0.03 | 67 | 35-32-0 | +6.64 | 60.3 | +11.0% | (-12.1%, +40.1%) | 27 / +28.5% | 40 / -0.3% | 0 | -165 / +115 / +188 | 0.0% | 4 | 2 |
| 2025 | consensus | 0.04 | 44 | 21-23-0 | +0.46 | 38.5 | +1.2% | (-23.9%, +30.9%) | 17 / +2.0% | 27 / +0.7% | 0 | -165 / +120 / +188 | 0.0% | 2 | 1 |
| 2025 | consensus | 0.05 | 26 | 15-11-0 | +6.20 | 21.7 | +28.6% | (-11.9%, +64.9%) | 8 / +44.7% | 18 / +21.7% | 0 | -140 / +128 / +175 | 0.0% | 1 | 1 |
| 2025 | consensus | 0.06 | 15 | 8-7-0 | +2.17 | 12.7 | +17.1% | (-27.9%, +55.9%) | 5 / +39.7% | 10 / +6.7% | 0 | -140 / +130 / +175 | 0.0% | 0 | 1 |
| 2025 | consensus | 0.08 | 5 | 4-1-0 | +3.23 | 4.2 | +76.5% | (-7.8%, +130.4%) | 2 / +109.1% | 3 / +51.5% | 0 | +100 / +120 / +150 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.02 | 64 | 30-34-0 | +1.23 | 54.5 | +2.3% | (-21.6%, +29.2%) | 64 / +2.3% | 0 | 35 / +0.0226 | -144 / +119 / +180 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.03 | 32 | 16-16-0 | +2.78 | 26.2 | +10.6% | (-15.7%, +42.4%) | 32 / +10.6% | 0 | 15 / +0.0293 | -124 / +120 / +180 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.04 | 14 | 6-8-0 | -0.77 | 11.3 | -6.8% | (-41.0%, +44.8%) | 14 / -6.8% | 0 | 8 / +0.0494 | -124 / +125 / +185 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.05 | 7 | 3-4-0 | -0.22 | 5.5 | -4.0% | (-79.7%, +106.0%) | 7 / -4.0% | 0 | 4 / +0.0568 | +104 / +125 / +185 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.06 | 2 | 1-1-0 | +0.05 | 1.9 | +2.6% | (-100.0%, +110.0%) | 2 / +2.6% | 0 | 2 / +0.0684 | +105 / +108 / +110 | 0.0% | 0 | 0 |

Cells with no bet in this variant: 21 of 48.

### S3: one-way soft prices allowed (BetRivers overs)

| season | reference | cut | bets | W-L-P | units | risked | ROI | 95% interval | 1st half | 2nd half | close value (n / mean) | price min / med / max | shorter than -200 | no action | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025 | pinnacle | 0.02 | 2 | 0-2-0 | -1.53 | 1.5 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 0 | +116 / +133 / +150 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.02 | 42 | 14-28-0 | -13.61 | 42.1 | -32.4% | (-60.7%, +1.4%) | 27 / -52.8% | 15 / -0.2% | 14 / +0.0216 | -164 / -112 / +194 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.03 | 18 | 7-11-0 | -3.10 | 16.8 | -18.5% | (-61.3%, +33.5%) | 12 / -47.5% | 6 / +36.5% | 8 / +0.0243 | -116 / -108 / +194 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.04 | 5 | 2-3-0 | -0.82 | 4.5 | -18.1% | (-100.0%, +80.2%) | 5 / -18.1% | 0 | 3 / +0.0472 | -115 / +105 / +185 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.05 | 4 | 1-3-0 | -1.75 | 3.3 | -53.1% | (-100.0%, +79.6%) | 4 / -53.1% | 0 | 2 / +0.0566 | -115 / +130 / +185 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.06 | 1 | 0-1-0 | -0.95 | 1.0 | -100.0% |  | 1 / -100.0% | 0 | 1 / +0.0613 | +105 / +105 / +105 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.02 | 24 | 9-15-0 | -4.39 | 22.0 | -19.9% | (-70.9%, +20.1%) | 24 / -19.9% | 0 | 11 / +0.0310 | -170 / +122 / +175 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.03 | 11 | 4-7-0 | -2.67 | 10.7 | -25.0% | (-100.0%, +10.7%) | 11 / -25.0% | 0 | 5 / +0.0402 | -170 / +120 / +175 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.04 | 4 | 1-3-0 | -1.72 | 3.3 | -52.7% | (-100.0%, -3.1%) | 4 / -52.7% | 0 | 3 / +0.0476 | -105 / +122 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.05 | 3 | 1-2-0 | -0.60 | 2.1 | -27.9% | (-100.0%, +185.0%) | 3 / -27.9% | 0 | 2 / +0.0502 | +105 / +155 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.06 | 2 | 0-2-0 | -1.60 | 1.6 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0428 | +105 / +130 / +155 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.02 | 43 | 21-22-0 | +3.31 | 37.8 | +8.8% | (-19.1%, +36.1%) | 24 / +1.9% | 19 / +18.2% | 0 | -165 / +135 / +188 | 0.0% | 3 | 1 |
| 2025 | betonlineag | 0.03 | 25 | 12-13-0 | +0.97 | 21.3 | +4.6% | (-39.3%, +43.1%) | 13 / -34.6% | 12 / +46.9% | 0 | -165 / +135 / +175 | 0.0% | 1 | 0 |
| 2025 | betonlineag | 0.04 | 16 | 6-10-0 | -2.81 | 13.6 | -20.7% | (-62.9%, +19.1%) | 9 / -55.2% | 7 / +24.8% | 0 | -165 / +135 / +175 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.05 | 7 | 4-3-0 | +1.29 | 5.8 | +22.2% | (-51.6%, +113.3%) | 2 / +18.1% | 5 / +23.6% | 0 | -140 / +145 / +175 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.06 | 1 | 0-1-0 | -1.40 | 1.4 | -100.0% |  | 0 | 1 / -100.0% | 0 | -140 / -140 / -140 | 0.0% | 0 | 0 |
| 2025 | consensus | 0.02 | 109 | 55-54-0 | +6.73 | 101.1 | +6.7% | (-14.1%, +30.4%) | 45 / +17.2% | 64 / -0.8% | 0 | -195 / +110 / +190 | 0.0% | 8 | 3 |
| 2025 | consensus | 0.03 | 67 | 35-32-0 | +6.64 | 60.3 | +11.0% | (-12.1%, +40.1%) | 27 / +28.5% | 40 / -0.3% | 0 | -165 / +115 / +188 | 0.0% | 4 | 2 |
| 2025 | consensus | 0.04 | 44 | 21-23-0 | +0.46 | 38.5 | +1.2% | (-23.9%, +30.9%) | 17 / +2.0% | 27 / +0.7% | 0 | -165 / +120 / +188 | 0.0% | 2 | 1 |
| 2025 | consensus | 0.05 | 26 | 15-11-0 | +6.20 | 21.7 | +28.6% | (-11.9%, +64.9%) | 8 / +44.7% | 18 / +21.7% | 0 | -140 / +128 / +175 | 0.0% | 1 | 1 |
| 2025 | consensus | 0.06 | 15 | 8-7-0 | +2.17 | 12.7 | +17.1% | (-27.9%, +55.9%) | 5 / +39.7% | 10 / +6.7% | 0 | -140 / +130 / +175 | 0.0% | 0 | 1 |
| 2025 | consensus | 0.08 | 5 | 4-1-0 | +3.23 | 4.2 | +76.5% | (-7.8%, +130.4%) | 2 / +109.1% | 3 / +51.5% | 0 | +100 / +120 / +150 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.02 | 65 | 30-35-0 | +0.11 | 55.6 | +0.2% | (-28.4%, +23.2%) | 65 / +0.2% | 0 | 36 / +0.0222 | -144 / +118 / +180 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.03 | 32 | 16-16-0 | +2.78 | 26.2 | +10.6% | (-15.7%, +42.4%) | 32 / +10.6% | 0 | 15 / +0.0293 | -124 / +120 / +180 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.04 | 14 | 6-8-0 | -0.77 | 11.3 | -6.8% | (-41.0%, +44.8%) | 14 / -6.8% | 0 | 8 / +0.0494 | -124 / +125 / +185 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.05 | 7 | 3-4-0 | -0.22 | 5.5 | -4.0% | (-79.7%, +106.0%) | 7 / -4.0% | 0 | 4 / +0.0568 | +104 / +125 / +185 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.06 | 2 | 1-1-0 | +0.05 | 1.9 | +2.6% | (-100.0%, +110.0%) | 2 / +2.6% | 0 | 2 / +0.0684 | +105 / +108 / +110 | 0.0% | 0 | 0 |

Cells with no bet in this variant: 21 of 48.

## 5. POST-HOC: the repo's own edge definition

Added after the pre-declared grid was seen, because that grid is too thin to test anything. The only change: edge = reference fair probability minus the soft book's de-vigged probability (`models/market_relative.find_bets`, the rule behind `nfl_prop_market` and the 2025 college sweep). This scale sits above the pre-declared one by the soft book's vig. Measured on the 2026 Pinnacle cells, the bets taken average an after-vig edge (reference fair minus the implied probability of the price) of -0.0000 at the 0.02 cut, +0.0082 at the 0.03 cut, +0.0273 at the 0.05 cut. So the loosest cuts here take prices that are about level with the reference's fair value. Column `mean_edge_vs_price` in `grid.csv` has this for every cell.

### 5.1 Full grid, named references

| season | reference | cut | bets | W-L-P | units | risked | ROI | 95% interval | 1st half | 2nd half | close value (n / mean) | price min / med / max | shorter than -200 | no action | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025 | pinnacle | 0.02 | 43 | 23-20-0 | +0.67 | 48.0 | +1.4% | (-27.8%, +37.5%) | 33 / -14.5% | 10 / +54.7% | 0 | -204 / -114 / +172 | 2.3% | 1 | 0 |
| 2025 | pinnacle | 0.03 | 18 | 7-11-0 | -3.65 | 18.4 | -19.8% | (-73.2%, +39.3%) | 13 / -51.9% | 5 / +59.8% | 0 | -168 / -103 / +172 | 0.0% | 0 | 0 |
| 2025 | pinnacle | 0.04 | 11 | 4-7-0 | -3.15 | 11.4 | -27.7% | (-84.0%, +58.8%) | 9 / -55.3% | 2 / +97.1% | 0 | -168 / +110 / +150 | 0.0% | 0 | 0 |
| 2025 | pinnacle | 0.05 | 3 | 1-2-0 | -0.53 | 2.9 | -18.3% | (-100.0%, +73.5%) | 3 / -18.3% | 0 | 0 | -136 / +116 / +150 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.02 | 558 | 299-259-0 | +8.55 | 645.6 | +1.3% | (-5.1%, +8.7%) | 217 / -3.0% | 341 / +4.0% | 264 / -0.0033 | -240 / -114 / +194 | 2.0% | 17 | 5 |
| 2026 | pinnacle | 0.03 | 279 | 142-137-0 | -7.69 | 319.5 | -2.4% | (-13.1%, +7.1%) | 132 / -7.7% | 147 / +2.3% | 116 / +0.0050 | -225 / -114 / +194 | 1.4% | 9 | 2 |
| 2026 | pinnacle | 0.04 | 126 | 57-69-0 | -15.83 | 140.0 | -11.3% | (-28.7%, +8.5%) | 73 / -21.4% | 53 / +1.8% | 56 / +0.0119 | -200 / -112 / +194 | 0.0% | 3 | 0 |
| 2026 | pinnacle | 0.05 | 49 | 22-27-0 | -6.60 | 53.3 | -12.4% | (-39.6%, +20.0%) | 29 / -30.2% | 20 / +12.6% | 21 / +0.0180 | -200 / -114 / +194 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.06 | 18 | 7-11-0 | -4.13 | 18.4 | -22.4% | (-66.3%, +21.8%) | 11 / -47.1% | 7 / +13.5% | 9 / +0.0214 | -116 / -112 / +175 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.08 | 2 | 0-2-0 | -2.10 | 2.1 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0613 | -115 / -104 / +105 | 0.0% | 0 | 0 |
| 2025+2026 | pinnacle | 0.02 | 601 | 322-279-0 | +9.23 | 693.6 | +1.3% | (-5.0%, +8.1%) | 43 / +1.4% | 558 / +1.3% | 264 / -0.0033 | -240 / -114 / +194 | 2.0% | 18 | 5 |
| 2025+2026 | pinnacle | 0.03 | 297 | 149-148-0 | -11.33 | 337.9 | -3.4% | (-14.3%, +7.2%) | 18 / -19.8% | 279 / -2.4% | 116 / +0.0050 | -225 / -114 / +194 | 1.3% | 9 | 2 |
| 2025+2026 | pinnacle | 0.04 | 137 | 61-76-0 | -18.98 | 151.4 | -12.5% | (-30.3%, +7.3%) | 11 / -27.7% | 126 / -11.3% | 56 / +0.0119 | -200 / -112 / +194 | 0.0% | 3 | 0 |
| 2025+2026 | pinnacle | 0.05 | 52 | 23-29-0 | -7.13 | 56.1 | -12.7% | (-40.3%, +19.3%) | 3 / -18.3% | 49 / -12.4% | 21 / +0.0180 | -200 / -113 / +194 | 0.0% | 0 | 0 |
| 2025+2026 | pinnacle | 0.06 | 18 | 7-11-0 | -4.13 | 18.4 | -22.4% | (-66.3%, +21.8%) | 0 | 18 / -22.4% | 9 / +0.0214 | -116 / -112 / +175 | 0.0% | 0 | 0 |
| 2025+2026 | pinnacle | 0.08 | 2 | 0-2-0 | -2.10 | 2.1 | -100.0% | (-100.0%, -100.0%) | 0 | 2 / -100.0% | 1 / +0.0613 | -115 / -104 / +105 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.02 | 147 | 71-76-0 | -9.92 | 164.7 | -6.0% | (-17.4%, +9.8%) | 136 / -7.0% | 11 / +6.5% | 84 / -0.0006 | -220 / -105 / +190 | 0.7% | 1 | 3 |
| 2026 | bovada | 0.03 | 90 | 44-46-0 | -2.66 | 98.3 | -2.7% | (-30.5%, +14.9%) | 87 / -3.8% | 3 / +32.1% | 46 / +0.0110 | -220 / -105 / +190 | 1.1% | 0 | 0 |
| 2026 | bovada | 0.04 | 48 | 22-26-0 | -4.32 | 52.2 | -8.3% | (-53.0%, +26.5%) | 48 / -8.3% | 0 | 26 / +0.0180 | -200 / -105 / +180 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.05 | 27 | 11-16-0 | -4.73 | 28.0 | -16.9% | (-65.7%, +21.7%) | 27 / -16.9% | 0 | 15 / +0.0244 | -180 / -105 / +175 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.06 | 11 | 5-6-0 | -1.05 | 11.6 | -9.0% | (-70.4%, +22.3%) | 11 / -9.0% | 0 | 6 / +0.0396 | -170 / +105 / +185 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.08 | 2 | 0-2-0 | -1.60 | 1.6 | -100.0% | (-100.0%, -100.0%) | 2 / -100.0% | 0 | 1 / +0.0428 | +105 / +130 / +155 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.02 | 147 | 71-76-0 | -9.92 | 164.7 | -6.0% | (-17.4%, +9.8%) | 0 | 147 / -6.0% | 84 / -0.0006 | -220 / -105 / +190 | 0.7% | 1 | 3 |
| 2025+2026 | bovada | 0.03 | 90 | 44-46-0 | -2.66 | 98.3 | -2.7% | (-30.5%, +14.9%) | 0 | 90 / -2.7% | 46 / +0.0110 | -220 / -105 / +190 | 1.1% | 0 | 0 |
| 2025+2026 | bovada | 0.04 | 48 | 22-26-0 | -4.32 | 52.2 | -8.3% | (-53.0%, +26.5%) | 0 | 48 / -8.3% | 26 / +0.0180 | -200 / -105 / +180 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.05 | 27 | 11-16-0 | -4.73 | 28.0 | -16.9% | (-65.7%, +21.7%) | 0 | 27 / -16.9% | 15 / +0.0244 | -180 / -105 / +175 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.06 | 11 | 5-6-0 | -1.05 | 11.6 | -9.0% | (-70.4%, +22.3%) | 0 | 11 / -9.0% | 6 / +0.0396 | -170 / +105 / +185 | 0.0% | 0 | 0 |
| 2025+2026 | bovada | 0.08 | 2 | 0-2-0 | -1.60 | 1.6 | -100.0% | (-100.0%, -100.0%) | 0 | 2 / -100.0% | 1 / +0.0428 | +105 / +130 / +155 | 0.0% | 0 | 0 |
| 2025 | betonlineag | 0.02 | 288 | 145-143-0 | -11.29 | 324.6 | -3.5% | (-12.1%, +5.9%) | 145 / +1.3% | 143 / -8.2% | 0 | -300 / -110 / +220 | 2.8% | 5 | 10 |
| 2025 | betonlineag | 0.03 | 165 | 92-73-0 | +14.16 | 184.0 | +7.7% | (-1.5%, +19.4%) | 75 / +5.2% | 90 / +9.6% | 0 | -300 / -110 / +198 | 2.4% | 5 | 3 |
| 2025 | betonlineag | 0.04 | 83 | 49-34-0 | +17.01 | 90.5 | +18.8% | (+2.2%, +38.7%) | 38 / +15.1% | 45 / +21.6% | 0 | -260 / +102 / +188 | 2.4% | 3 | 3 |
| 2025 | betonlineag | 0.05 | 43 | 25-18-0 | +7.59 | 46.6 | +16.3% | (-7.0%, +39.9%) | 21 / +10.5% | 22 / +21.3% | 0 | -260 / +105 / +175 | 2.3% | 2 | 1 |
| 2025 | betonlineag | 0.06 | 25 | 13-12-0 | +2.88 | 23.0 | +12.5% | (-25.9%, +45.3%) | 12 / -28.7% | 13 / +45.2% | 0 | -260 / +135 / +175 | 4.0% | 1 | 0 |
| 2025 | betonlineag | 0.08 | 8 | 4-4-0 | -0.36 | 7.8 | -4.6% | (-58.3%, +65.2%) | 3 / -45.1% | 5 / +21.7% | 0 | -165 / +120 / +175 | 0.0% | 0 | 0 |
| 2025+2026 | betonlineag | 0.02 | 288 | 145-143-0 | -11.29 | 324.6 | -3.5% | (-12.1%, +5.9%) | 288 / -3.5% | 0 | 0 | -300 / -110 / +220 | 2.8% | 5 | 10 |
| 2025+2026 | betonlineag | 0.03 | 165 | 92-73-0 | +14.16 | 184.0 | +7.7% | (-1.5%, +19.4%) | 165 / +7.7% | 0 | 0 | -300 / -110 / +198 | 2.4% | 5 | 3 |
| 2025+2026 | betonlineag | 0.04 | 83 | 49-34-0 | +17.01 | 90.5 | +18.8% | (+2.2%, +38.7%) | 83 / +18.8% | 0 | 0 | -260 / +102 / +188 | 2.4% | 3 | 3 |
| 2025+2026 | betonlineag | 0.05 | 43 | 25-18-0 | +7.59 | 46.6 | +16.3% | (-7.0%, +39.9%) | 43 / +16.3% | 0 | 0 | -260 / +105 / +175 | 2.3% | 2 | 1 |
| 2025+2026 | betonlineag | 0.06 | 25 | 13-12-0 | +2.88 | 23.0 | +12.5% | (-25.9%, +45.3%) | 25 / +12.5% | 0 | 0 | -260 / +135 / +175 | 4.0% | 1 | 0 |
| 2025+2026 | betonlineag | 0.08 | 8 | 4-4-0 | -0.36 | 7.8 | -4.6% | (-58.3%, +65.2%) | 8 / -4.6% | 0 | 0 | -165 / +120 / +175 | 0.0% | 0 | 0 |
| 2025 | consensus | 0.02 | 410 | 202-208-0 | -17.39 | 443.7 | -3.9% | (-11.5%, +5.2%) | 188 / -3.0% | 222 / -4.7% | 0 | -300 / +100 / +220 | 2.0% | 12 | 13 |
| 2025 | consensus | 0.03 | 279 | 145-134-0 | +7.02 | 301.4 | +2.3% | (-7.2%, +13.2%) | 121 / +6.9% | 158 / -1.1% | 0 | -300 / +102 / +198 | 2.2% | 10 | 9 |
| 2025 | consensus | 0.04 | 181 | 92-89-0 | +4.38 | 191.5 | +2.3% | (-11.0%, +16.7%) | 74 / +4.4% | 107 / +0.8% | 0 | -300 / +105 / +190 | 2.2% | 9 | 5 |
| 2025 | consensus | 0.05 | 110 | 58-52-0 | +6.57 | 115.6 | +5.7% | (-13.7%, +26.7%) | 41 / +23.8% | 69 / -4.2% | 0 | -300 / +103 / +188 | 1.8% | 6 | 4 |
| 2025 | consensus | 0.06 | 70 | 38-32-0 | +8.58 | 67.9 | +12.6% | (-7.2%, +36.7%) | 27 / +21.8% | 43 / +6.9% | 0 | -260 / +108 / +188 | 1.4% | 4 | 2 |
| 2025 | consensus | 0.08 | 25 | 15-10-0 | +5.92 | 22.9 | +25.9% | (-3.8%, +59.6%) | 10 / +24.7% | 15 / +26.7% | 0 | -165 / +110 / +175 | 0.0% | 1 | 1 |
| 2026 | consensus | 0.02 | 333 | 159-174-0 | -16.72 | 352.5 | -4.7% | (-12.5%, +3.4%) | 297 / -4.7% | 36 / -4.9% | 179 / -0.0017 | -220 / -105 / +190 | 0.3% | 7 | 3 |
| 2026 | consensus | 0.03 | 187 | 92-95-0 | +0.08 | 190.3 | +0.0% | (-12.7%, +12.3%) | 181 / -0.0% | 6 / +2.7% | 104 / +0.0071 | -220 / +100 / +180 | 0.5% | 2 | 0 |
| 2026 | consensus | 0.04 | 120 | 55-65-0 | -6.39 | 118.8 | -5.4% | (-24.4%, +14.3%) | 120 / -5.4% | 0 | 62 / +0.0126 | -200 / +105 / +180 | 0.0% | 1 | 0 |
| 2026 | consensus | 0.05 | 63 | 27-36-0 | -5.85 | 57.2 | -10.2% | (-28.4%, +13.7%) | 63 / -10.2% | 0 | 38 / +0.0194 | -180 / +114 / +180 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.06 | 32 | 15-17-0 | -1.24 | 29.6 | -4.2% | (-38.0%, +44.5%) | 32 / -4.2% | 0 | 16 / +0.0288 | -170 / +113 / +175 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.08 | 5 | 2-3-0 | -0.56 | 4.3 | -13.1% | (-100.0%, +117.0%) | 5 / -13.1% | 0 | 2 / +0.0684 | +104 / +110 / +155 | 0.0% | 0 | 0 |
| 2025+2026 | consensus | 0.02 | 743 | 361-382-0 | -34.11 | 796.2 | -4.3% | (-9.7%, +1.4%) | 410 / -3.9% | 333 / -4.7% | 179 / -0.0017 | -300 / -102 / +220 | 1.2% | 19 | 16 |
| 2025+2026 | consensus | 0.03 | 466 | 237-229-0 | +7.11 | 491.7 | +1.4% | (-6.1%, +10.4%) | 279 / +2.3% | 187 / +0.0% | 104 / +0.0071 | -300 / +101 / +198 | 1.5% | 12 | 9 |
| 2025+2026 | consensus | 0.04 | 301 | 147-154-0 | -2.01 | 310.4 | -0.6% | (-11.7%, +11.2%) | 181 / +2.3% | 120 / -5.4% | 62 / +0.0126 | -300 / +105 / +190 | 1.3% | 10 | 5 |
| 2025+2026 | consensus | 0.05 | 173 | 85-88-0 | +0.73 | 172.7 | +0.4% | (-13.3%, +15.3%) | 110 / +5.7% | 63 / -10.2% | 38 / +0.0194 | -300 / +108 / +188 | 1.2% | 6 | 4 |
| 2025+2026 | consensus | 0.06 | 102 | 53-49-0 | +7.34 | 97.6 | +7.5% | (-10.9%, +27.8%) | 70 / +12.6% | 32 / -4.2% | 16 / +0.0288 | -260 / +110 / +188 | 1.0% | 4 | 2 |
| 2025+2026 | consensus | 0.08 | 30 | 17-13-0 | +5.37 | 27.1 | +19.8% | (-11.5%, +54.3%) | 25 / +25.9% | 5 / -13.1% | 2 / +0.0684 | -165 / +110 / +175 | 0.0% | 1 | 1 |

Named cells with no bet (reference not captured that season, or nothing reached the cut): 14.

### 5.2 The placebo under this definition (bets / ROI)

| season | reference | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|
| 2025 | betonlineag | 288 / -3.5% | 165 / +7.7% | 83 / +18.8% | 43 / +16.3% | 25 / +12.5% | 8 / -4.6% |
| 2025 | bovada | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | consensus | 410 / -3.9% | 279 / +2.3% | 181 / +2.3% | 110 / +5.7% | 70 / +12.6% | 25 / +25.9% |
| 2025 | pinnacle | 43 / +1.4% | 18 / -19.8% | 11 / -27.7% | 3 / -18.3% | 0 | 0 |
| 2025 | betmgm | 234 / -10.6% | 148 / -8.8% | 89 / -0.8% | 56 / -2.6% | 32 / +6.0% | 9 / +31.7% |
| 2025 | betrivers | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | draftkings | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | espnbet | 228 / -14.8% | 142 / -11.1% | 82 / -9.4% | 51 / -12.2% | 27 / -19.3% | 11 / -25.8% |
| 2025 | fanatics | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | fanduel | 385 / -5.5% | 275 / -1.8% | 194 / +2.0% | 128 / +8.5% | 74 / +15.8% | 33 / +19.3% |
| 2025 | fliff | 615 / -5.3% | 410 / -2.8% | 270 / -5.5% | 168 / -5.1% | 106 / -0.1% | 40 / -7.8% |
| 2025 | hardrockbet | 362 / -0.4% | 274 / +0.3% | 200 / +0.5% | 132 / -4.7% | 85 / -11.6% | 34 / -9.7% |
| 2025 | rebet | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | williamhill_us | 167 / -6.7% | 102 / -5.9% | 58 / +4.3% | 28 / +17.7% | 16 / +26.2% | 5 / +47.2% |
| 2026 | betonlineag | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | bovada | 147 / -6.0% | 90 / -2.7% | 48 / -8.3% | 27 / -16.9% | 11 / -9.0% | 2 / -100.0% |
| 2026 | consensus | 333 / -4.7% | 187 / +0.0% | 120 / -5.4% | 63 / -10.2% | 32 / -4.2% | 5 / -13.1% |
| 2026 | pinnacle | 558 / +1.3% | 279 / -2.4% | 126 / -11.3% | 49 / -12.4% | 18 / -22.4% | 2 / -100.0% |
| 2026 | betmgm | 4 / +35.7% | 1 / +93.5% | 0 | 0 | 0 | 0 |
| 2026 | betrivers | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | draftkings | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | espnbet | 168 / -16.8% | 92 / -11.9% | 64 / -9.6% | 36 / -9.2% | 19 / +6.8% | 4 / -56.1% |
| 2026 | fanatics | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | fanduel | 324 / -6.4% | 218 / -0.7% | 137 / -5.8% | 83 / -3.7% | 43 / +5.1% | 8 / +39.4% |
| 2026 | fliff | 176 / +12.4% | 129 / +13.9% | 98 / +14.8% | 68 / +19.3% | 38 / +15.0% | 3 / -100.0% |
| 2026 | hardrockbet | 329 / -3.2% | 227 / -1.8% | 152 / -7.5% | 97 / -4.8% | 49 / -4.9% | 9 / -39.3% |
| 2026 | rebet | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | williamhill_us | 226 / +1.8% | 144 / -0.5% | 80 / +13.4% | 41 / +17.7% | 20 / +28.8% | 3 / +40.7% |
| 2025+2026 | betonlineag | 288 / -3.5% | 165 / +7.7% | 83 / +18.8% | 43 / +16.3% | 25 / +12.5% | 8 / -4.6% |
| 2025+2026 | bovada | 147 / -6.0% | 90 / -2.7% | 48 / -8.3% | 27 / -16.9% | 11 / -9.0% | 2 / -100.0% |
| 2025+2026 | consensus | 743 / -4.3% | 466 / +1.4% | 301 / -0.6% | 173 / +0.4% | 102 / +7.5% | 30 / +19.8% |
| 2025+2026 | pinnacle | 601 / +1.3% | 297 / -3.4% | 137 / -12.5% | 52 / -12.7% | 18 / -22.4% | 2 / -100.0% |
| 2025+2026 | betmgm | 238 / -9.8% | 149 / -8.2% | 89 / -0.8% | 56 / -2.6% | 32 / +6.0% | 9 / +31.7% |
| 2025+2026 | betrivers | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025+2026 | draftkings | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025+2026 | espnbet | 396 / -15.6% | 234 / -11.4% | 146 / -9.5% | 87 / -11.0% | 46 / -9.2% | 15 / -34.4% |
| 2025+2026 | fanatics | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025+2026 | fanduel | 709 / -5.9% | 493 / -1.3% | 331 / -1.1% | 211 / +4.0% | 117 / +12.0% | 41 / +22.8% |
| 2025+2026 | fliff | 791 / -1.4% | 539 / +1.1% | 368 / -0.3% | 236 / +1.9% | 144 / +3.9% | 43 / -14.9% |
| 2025+2026 | hardrockbet | 691 / -1.8% | 501 / -0.7% | 352 / -3.1% | 229 / -4.7% | 134 / -9.0% | 43 / -16.8% |
| 2025+2026 | rebet | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025+2026 | williamhill_us | 393 / -1.9% | 246 / -2.8% | 138 / +9.3% | 69 / +17.7% | 36 / +27.4% | 8 / +45.1% |

### 5.3 By market and by soft book, 2026 Pinnacle and 2025 BetOnline (bets / units / ROI)

| season | reference | market | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|---|
| 2025 | betonlineag | player_pass_tds | 240 / -15.59u / -5.7% | 143 / +12.98u / +8.1% | 77 / +16.81u / +19.8% | 40 / +8.24u / +18.7% | 23 / +4.52u / +21.2% | 8 / -0.36u / -4.6% |
| 2025 | betonlineag | player_pass_yds | 8 / +1.65u / +18.7% | 1 / -1.14u / -100.0% |  |  |  |  |
| 2025 | betonlineag | player_reception_yds | 14 / -0.90u / -5.8% | 7 / +0.55u / +7.2% | 3 / +0.85u / +26.5% | 1 / +1.00u / +110.0% |  |  |
| 2025 | betonlineag | player_receptions | 13 / +1.19u / +9.1% | 8 / +0.07u / +0.9% | 3 / -0.65u / -24.6% | 2 / -1.65u / -100.0% | 2 / -1.65u / -100.0% |  |
| 2025 | betonlineag | player_rush_yds | 13 / +2.36u / +16.6% | 6 / +1.70u / +26.3% |  |  |  |  |
| 2025 | consensus | player_pass_completions | 1 / -1.05u / -100.0% | 1 / -1.05u / -100.0% |  |  |  |  |
| 2025 | consensus | player_pass_interceptions | 1 / -1.05u / -100.0% |  |  |  |  |  |
| 2025 | consensus | player_pass_tds | 259 / -21.48u / -7.4% | 175 / +5.42u / +2.8% | 116 / +10.94u / +8.5% | 64 / +10.82u / +15.1% | 40 / +12.62u / +31.0% | 13 / +2.95u / +24.0% |
| 2025 | consensus | player_pass_yds | 6 / +4.00u / +65.5% | 3 / +1.00u / +33.8% | 1 / +1.00u / +107.0% |  |  |  |
| 2025 | consensus | player_reception_yds | 15 / -1.47u / -9.4% | 5 / +1.02u / +20.9% | 1 / +1.00u / +110.0% | 1 / +1.00u / +110.0% |  |  |
| 2025 | consensus | player_receptions | 116 / -0.12u / -0.1% | 92 / -0.37u / -0.4% | 62 / -9.56u / -15.8% | 44 / -6.24u / -14.8% | 29 / -5.03u / -19.0% | 12 / +2.98u / +28.0% |
| 2025 | consensus | player_rush_yds | 12 / +3.78u / +30.6% | 3 / +1.00u / +35.0% | 1 / +1.00u / +120.0% | 1 / +1.00u / +120.0% | 1 / +1.00u / +120.0% |  |
| 2026 | bovada | player_pass_tds | 105 / -14.84u / -12.4% | 74 / -8.46u / -10.4% | 43 / -5.44u / -11.6% | 25 / -2.85u / -10.9% | 10 / -0.22u / -2.0% | 2 / -1.60u / -100.0% |
| 2026 | bovada | player_pass_yds | 11 / +0.63u / +5.2% | 8 / +1.78u / +20.0% | 2 / -0.05u / -2.3% | 1 / -1.05u / -100.0% |  |  |
| 2026 | bovada | player_reception_yds | 25 / +0.35u / +1.3% | 5 / +1.03u / +20.1% | 1 / -0.83u / -100.0% | 1 / -0.83u / -100.0% | 1 / -0.83u / -100.0% |  |
| 2026 | bovada | player_rush_yds | 6 / +3.95u / +62.8% | 3 / +3.00u / +97.0% | 2 / +2.00u / +95.6% |  |  |  |
| 2026 | consensus | player_pass_tds | 128 / -7.37u / -5.3% | 82 / -7.06u / -8.4% | 51 / -3.36u / -6.5% | 20 / -8.93u / -50.2% | 7 / -1.16u / -18.2% | 2 / -1.60u / -100.0% |
| 2026 | consensus | player_pass_yds | 16 / -2.85u / -16.1% | 2 / -2.15u / -100.0% |  |  |  |  |
| 2026 | consensus | player_reception_yds | 26 / -0.77u / -2.8% | 3 / +1.17u / +41.2% | 1 / -0.83u / -100.0% | 1 / -0.83u / -100.0% | 1 / -0.83u / -100.0% |  |
| 2026 | consensus | player_receptions | 131 / +2.22u / +1.7% | 91 / +7.35u / +8.0% | 65 / -1.23u / -1.9% | 40 / +3.82u / +10.4% | 24 / +0.75u / +3.3% | 3 / +1.04u / +38.9% |
| 2026 | consensus | player_rush_yds | 32 / -7.95u / -22.8% | 9 / +0.78u / +8.4% | 3 / -0.96u / -33.4% | 2 / +0.09u / +5.0% |  |  |
| 2026 | pinnacle | player_pass_tds | 146 / -4.14u / -2.3% | 76 / -7.07u / -7.8% | 39 / -7.31u / -17.4% | 16 / -5.74u / -35.5% | 6 / -1.20u / -24.9% | 1 / -0.95u / -100.0% |
| 2026 | pinnacle | player_pass_yds | 57 / +12.42u / +19.4% | 32 / +6.49u / +18.1% | 13 / +0.21u / +1.4% | 6 / +1.73u / +26.0% | 2 / -0.15u / -6.5% |  |
| 2026 | pinnacle | player_reception_yds | 198 / -6.20u / -2.8% | 89 / -6.57u / -6.6% | 35 / -5.36u / -13.5% | 14 / +1.21u / +7.6% | 4 / -0.22u / -4.9% | 1 / -1.15u / -100.0% |
| 2026 | pinnacle | player_receptions | 6 / -2.18u / -31.8% | 3 / -0.95u / -26.8% |  |  |  |  |
| 2026 | pinnacle | player_rush_yds | 151 / +8.65u / +5.1% | 79 / +0.41u / +0.5% | 39 / -3.38u / -7.7% | 13 / -3.80u / -26.3% | 6 / -2.56u / -37.6% |  |

| season | reference | book | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|---|
| 2025 | betonlineag | betmgm | 41 / -11.71u / -24.6% | 22 / +0.81u / +3.2% | 7 / +3.80u / +52.6% | 2 / +2.00u / +80.0% |  |  |
| 2025 | betonlineag | fanduel | 48 / +3.92u / +8.2% | 19 / +1.27u / +6.9% | 6 / +2.35u / +39.6% | 3 / -0.65u / -20.7% | 2 / -1.65u / -100.0% |  |
| 2025 | betonlineag | hardrockbet | 186 / -8.79u / -4.1% | 120 / +9.65u / +7.0% | 68 / +10.43u / +13.7% | 36 / +5.81u / +14.6% | 21 / +4.10u / +20.4% | 6 / -0.79u / -12.1% |
| 2025 | betonlineag | williamhill_us | 13 / +5.29u / +37.6% | 4 / +2.43u / +71.8% | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% |
| 2025 | consensus | betmgm | 35 / -7.82u / -20.0% | 12 / +6.81u / +54.8% | 5 / +1.68u / +35.7% | 2 / +2.00u / +74.1% |  |  |
| 2025 | consensus | fanduel | 61 / +6.14u / +10.0% | 39 / +4.40u / +11.6% | 21 / -0.12u / -0.6% | 15 / -0.29u / -2.2% | 9 / -2.29u / -30.4% | 2 / -1.44u / -100.0% |
| 2025 | consensus | hardrockbet | 291 / -17.08u / -5.4% | 217 / -4.70u / -2.0% | 152 / +1.39u / +0.8% | 91 / +4.44u / +4.5% | 59 / +10.45u / +17.7% | 22 / +6.36u / +30.7% |
| 2025 | consensus | williamhill_us | 23 / +1.37u / +5.6% | 11 / +0.52u / +4.7% | 3 / +1.43u / +65.1% | 2 / +0.43u / +34.0% | 2 / +0.43u / +34.0% | 1 / +1.00u / +145.0% |
| 2026 | bovada | fanduel | 17 / +6.32u / +32.4% | 8 / +3.72u / +41.0% | 1 / +1.00u / +87.7% |  |  |  |
| 2026 | bovada | hardrockbet | 115 / -12.13u / -9.4% | 76 / -5.50u / -6.7% | 46 / -4.27u / -8.6% | 26 / -3.68u / -13.7% | 11 / -1.05u / -9.0% | 2 / -1.60u / -100.0% |
| 2026 | bovada | williamhill_us | 15 / -4.11u / -24.5% | 6 / -0.88u / -12.1% | 1 / -1.05u / -100.0% | 1 / -1.05u / -100.0% |  |  |
| 2026 | consensus | betmgm | 1 / -1.05u / -100.0% |  |  |  |  |  |
| 2026 | consensus | fanduel | 102 / -7.70u / -7.0% | 45 / +0.56u / +1.2% | 31 / -3.67u / -12.3% | 19 / +1.73u / +9.3% | 14 / -1.72u / -12.5% | 1 / -0.96u / -100.0% |
| 2026 | consensus | hardrockbet | 191 / +0.88u / +0.4% | 125 / +4.25u / +3.3% | 80 / -0.29u / -0.4% | 39 / -7.30u / -21.1% | 17 / -0.51u / -3.5% | 4 / +0.40u / +12.2% |
| 2026 | consensus | williamhill_us | 39 / -8.85u / -22.7% | 17 / -4.73u / -29.6% | 9 / -2.42u / -30.8% | 5 / -0.27u / -6.8% | 1 / +1.00u / +100.0% |  |
| 2026 | pinnacle | betmgm | 5 / +2.85u / +49.9% | 3 / +0.85u / +25.8% |  |  |  |  |
| 2026 | pinnacle | fanduel | 386 / +16.13u / +3.6% | 167 / +1.38u / +0.7% | 62 / -3.21u / -4.6% | 17 / +0.36u / +2.0% | 5 / +1.10u / +21.0% |  |
| 2026 | pinnacle | hardrockbet | 138 / -3.68u / -2.3% | 96 / -6.66u / -6.1% | 57 / -11.30u / -18.3% | 29 / -5.85u / -18.4% | 12 / -4.17u / -34.5% | 2 / -2.10u / -100.0% |
| 2026 | pinnacle | williamhill_us | 29 / -6.74u / -21.1% | 13 / -3.26u / -23.8% | 7 / -1.32u / -17.2% | 3 / -1.12u / -34.5% | 1 / -1.07u / -100.0% |  |

| season | reference | side | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|---|
| 2025 | betonlineag | over | 119 / -9.86u / -7.7% | 61 / -0.58u / -0.9% | 29 / +3.65u / +12.9% | 13 / -1.34u / -10.6% | 10 / -2.09u / -22.7% | 1 / -0.74u / -100.0% |
| 2025 | betonlineag | under | 169 / -1.43u / -0.7% | 104 / +14.74u / +12.2% | 54 / +13.36u / +21.5% | 30 / +8.94u / +26.3% | 15 / +4.97u / +36.2% | 7 / +0.38u / +5.3% |
| 2025 | consensus | over | 197 / -35.57u / -17.5% | 120 / -12.79u / -10.5% | 79 / -12.28u / -16.1% | 48 / -3.33u / -7.1% | 32 / -1.50u / -5.0% | 8 / -0.54u / -8.4% |
| 2025 | consensus | under | 213 / +18.18u / +7.6% | 159 / +19.81u / +11.0% | 102 / +16.66u / +14.4% | 62 / +9.90u / +14.4% | 38 / +10.08u / +26.5% | 17 / +6.47u / +39.3% |
| 2026 | bovada | over | 66 / -1.43u / -2.0% | 35 / +2.48u / +7.0% | 15 / -0.59u / -4.4% | 10 / -1.13u / -13.4% | 5 / +1.21u / +29.5% | 1 / -0.95u / -100.0% |
| 2026 | bovada | under | 81 / -8.48u / -9.1% | 55 / -5.13u / -8.2% | 33 / -3.73u / -9.6% | 17 / -3.60u / -18.4% | 6 / -2.26u / -30.1% | 1 / -0.65u / -100.0% |
| 2026 | consensus | over | 159 / -3.32u / -2.1% | 86 / +9.77u / +12.1% | 54 / +1.92u / +4.0% | 33 / +2.90u / +10.7% | 19 / +2.13u / +12.7% | 2 / +0.05u / +2.6% |
| 2026 | consensus | under | 174 / -13.40u / -7.0% | 101 / -9.69u / -8.9% | 66 / -8.30u / -11.7% | 30 / -8.75u / -29.2% | 13 / -3.37u / -26.3% | 3 / -0.61u / -25.2% |
| 2026 | pinnacle | over | 203 / +17.93u / +7.8% | 100 / +1.85u / +1.7% | 42 / -1.10u / -2.5% | 15 / +0.04u / +0.3% | 5 / -0.84u / -18.4% | 1 / -0.95u / -100.0% |
| 2026 | pinnacle | under | 355 / -9.38u / -2.3% | 179 / -9.54u / -4.6% | 84 / -14.73u / -15.3% | 34 / -6.64u / -17.1% | 13 / -3.29u / -23.8% | 1 / -1.15u / -100.0% |

The one reference that looks like something is BetOnline in 2025: +7.7% over 165 bets at 0.03, +18.8% over 83 at 0.04 (interval +2.2% to +38.7%), +16.3% over 43 at 0.05, positive in both halves at 0.03 to 0.05. Two things stop it being a finding. FanDuel as the reference does the same at the tighter cuts (+8.5% over 128 at 0.05, +15.8% over 74 at 0.06). And it cannot be checked on 2026: the 2026 capture holds 0 BetOnline rows.

## 6. The clearing test, cell by cell

| variant | named cells (pooled rows included) | with a bet | 150+ bets | both halves positive | interval above 0 or close value positive | above every 50+ bet placebo | all four |
|---|---|---|---|---|---|---|---|
| PRIMARY | 72 | 48 | 1 | 8 | 30 | 1 | 0 |
| S1_power_devig | 48 | 28 | 0 | 5 | 16 | 0 | 0 |
| S2_null_stat_no_action | 48 | 27 | 0 | 5 | 15 | 0 | 0 |
| S3_one_way_soft_allowed | 48 | 27 | 0 | 6 | 15 | 0 | 0 |
| S4_POSTHOC_repo_edge_def | 72 | 58 | 17 | 8 | 32 | 10 | 1 |

Every named cell with 150 or more bets:

| variant | season | reference | cut | bets | ROI | 95% interval | halves | halves ok | close value | interval/close ok | best retail reference (50+ bets) | beats placebos | CLEARS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRIMARY | 2025+2026 | consensus | 0.02 | 171 | +5.2% | (-10.4%, +22.7%) | +6.9% / +2.3% | yes | 35 / +0.0226 | yes | best placebo williamhill_us +0.2783 | no | no |
| S4_POSTHOC_repo_edge_def | 2025 | betonlineag | 0.02 | 288 | -3.5% | (-12.1%, +5.9%) | +1.3% / -8.2% | no | none | no | best placebo hardrockbet -0.0041 | no | no |
| S4_POSTHOC_repo_edge_def | 2025 | consensus | 0.02 | 410 | -3.9% | (-11.5%, +5.2%) | -3.0% / -4.7% | no | none | no | best placebo hardrockbet -0.0041 | no | no |
| S4_POSTHOC_repo_edge_def | 2025 | betonlineag | 0.03 | 165 | +7.7% | (-1.5%, +19.4%) | +5.2% / +9.6% | yes | none | no | best placebo hardrockbet +0.0026 | yes | no |
| S4_POSTHOC_repo_edge_def | 2025 | consensus | 0.03 | 279 | +2.3% | (-7.2%, +13.2%) | +6.9% / -1.1% | no | none | no | best placebo hardrockbet +0.0026 | yes | no |
| S4_POSTHOC_repo_edge_def | 2025 | consensus | 0.04 | 181 | +2.3% | (-11.0%, +16.7%) | +4.4% / +0.8% | yes | none | no | best placebo williamhill_us +0.0429 | no | no |
| S4_POSTHOC_repo_edge_def | 2025+2026 | pinnacle | 0.02 | 601 | +1.3% | (-5.0%, +8.1%) | +1.4% / +1.3% | yes | 264 / -0.0033 | no | best placebo fliff -0.0142 | yes | no |
| S4_POSTHOC_repo_edge_def | 2025+2026 | betonlineag | 0.02 | 288 | -3.5% | (-12.1%, +5.9%) | -3.5% / n/a | no | none | no | best placebo fliff -0.0142 | no | no |
| S4_POSTHOC_repo_edge_def | 2025+2026 | consensus | 0.02 | 743 | -4.3% | (-9.7%, +1.4%) | -3.9% / -4.7% | no | 179 / -0.0017 | no | best placebo fliff -0.0142 | no | no |
| S4_POSTHOC_repo_edge_def | 2025+2026 | pinnacle | 0.03 | 297 | -3.4% | (-14.3%, +7.2%) | -19.8% / -2.4% | no | 116 / +0.0050 | yes | best placebo fliff +0.0110 | no | no |
| S4_POSTHOC_repo_edge_def | 2025+2026 | betonlineag | 0.03 | 165 | +7.7% | (-1.5%, +19.4%) | +7.7% / n/a | no | none | no | best placebo fliff +0.0110 | yes | no |
| S4_POSTHOC_repo_edge_def | 2025+2026 | consensus | 0.03 | 466 | +1.4% | (-6.1%, +10.4%) | +2.3% / +0.0% | yes | 104 / +0.0071 | yes | best placebo fliff +0.0110 | yes | yes |
| S4_POSTHOC_repo_edge_def | 2025+2026 | consensus | 0.04 | 301 | -0.6% | (-11.7%, +11.2%) | +2.3% / -5.4% | no | 62 / +0.0126 | yes | best placebo williamhill_us +0.0929 | no | no |
| S4_POSTHOC_repo_edge_def | 2025+2026 | consensus | 0.05 | 173 | +0.4% | (-13.3%, +15.3%) | +5.7% / -10.2% | no | 38 / +0.0194 | yes | best placebo williamhill_us +0.1772 | no | no |
| S4_POSTHOC_repo_edge_def | 2026 | pinnacle | 0.02 | 558 | +1.3% | (-5.1%, +8.7%) | -3.0% / +4.0% | no | 264 / -0.0033 | no | best placebo fliff +0.1236 | no | no |
| S4_POSTHOC_repo_edge_def | 2026 | consensus | 0.02 | 333 | -4.7% | (-12.5%, +3.4%) | -4.7% / -4.9% | no | 179 / -0.0017 | no | best placebo fliff +0.1236 | no | no |
| S4_POSTHOC_repo_edge_def | 2026 | pinnacle | 0.03 | 279 | -2.4% | (-13.1%, +7.1%) | -7.7% / +2.3% | no | 116 / +0.0050 | yes | best placebo fliff +0.1392 | no | no |
| S4_POSTHOC_repo_edge_def | 2026 | consensus | 0.03 | 187 | +0.0% | (-12.7%, +12.3%) | -0.0% / +2.7% | no | 104 / +0.0071 | yes | best placebo fliff +0.1392 | no | no |

Every cell's four answers are in `verdict.csv`.

## 7. What could not be done, and what is uncertain

- **DraftKings cannot be tested on its main lines.** It has no row in the eight over/under markets in either season; its college props arrive only as one-way alternate ladders and anytime TD. Section 8 is the only DraftKings test possible.
- **Close value does not exist for 2025** (one pull per game), and in 2026 the "close" is the last of at most three game-day pulls, which can be hours before kickoff.
- **BetOnline was not captured in 2026**, so the only reference with a positive 2025 record has no second season.
- **A player who played and recorded no stat at all is missing from the log** (`docs/sports/ncaaf.md` says the table drops all-zero players; not re-measured here), so he is graded no action here where a book would settle the under as a win. This drops some winning unders and some losing overs. Its size is not measurable from these files.
- **Why soft prices converged after 2026-09-28 is not established.** It could be the books or the capture. It was not investigated beyond the tables in 2.3.
- **Neither reference is a low-margin market maker on this board.** Median two-way overround in 2026: pinnacle 6.5%, bovada 7.0%, fanduel 6.5%, hardrockbet 7.0%.
- None of the three pre-declared sensitivities produces a cell that clears; the largest cell under any of them has 117 bets (section 4).

## 8. Separate section: alternate ladders against a reference's main line (2026 only)

Run after sections 1 to 7 were written. Definitions are at the top of `alt.py`, fixed before its first run; one variant, 54 cells, 50 with a bet. This is the only test DraftKings can take part in, because its college props reach the feed only as ladders.

- **Soft side**: a bettable book's ladder rung. Every rung is over-only and every line ends in .5, so every bet is an over.
- **Reference**: the reference's main two-way quote for the same player and market, in the same pull, at exactly the rung's number.
- **Edge**: reference de-vigged over probability minus the implied probability of the rung's price. Same cuts, lock, grading, stake and tests as the main run.

### 8.1 How many rungs sit on a reference's main line, and how they are priced

| reference | bettable rungs | rungs where the reference quotes that player/market/pull | rungs at the reference's line | propositions | games |
|---|---|---|---|---|---|
| pinnacle | 281139 | 158815 | 2797 | 1182 | 245 |
| bovada | 281139 | 150566 | 2668 | 1239 | 306 |
| consensus | 281139 |  | 6514 | 2830 | 341 |

Edge of every such rung (before any cut):

| reference | soft book | rungs at the reference's line | mean edge | median | 90th pct | 99th pct | max | rungs at or better than fair | rungs at 0.02+ |
|---|---|---|---|---|---|---|---|---|---|
| pinnacle | betmgm | 462 | -0.1029 | -0.1063 | -0.0360 | +0.0212 | +0.0589 | 10 | 5 |
| pinnacle | betrivers | 98 | -0.0454 | -0.0455 | +0.0064 | +0.0344 | +0.0363 | 13 | 6 |
| pinnacle | draftkings | 1928 | -0.0496 | -0.0467 | -0.0118 | +0.0309 | +0.3227 | 113 | 35 |
| pinnacle | fanduel | 85 | -0.0328 | -0.0315 | +0.0082 | +0.0281 | +0.0294 | 13 | 4 |
| pinnacle | hardrockbet | 156 | -0.0370 | -0.0306 | +0.0049 | +0.0460 | +0.0589 | 21 | 7 |
| pinnacle | williamhill_us | 68 | -0.0569 | -0.0536 | -0.0349 | -0.0326 | -0.0322 | 0 | 0 |
| bovada | betmgm | 436 | -0.1066 | -0.1052 | -0.0333 | +0.0204 | +0.0715 | 9 | 5 |
| bovada | betrivers | 121 | -0.0503 | -0.0495 | -0.0074 | +0.0265 | +0.0556 | 12 | 2 |
| bovada | draftkings | 1882 | -0.0484 | -0.0434 | -0.0103 | +0.0328 | +0.3110 | 114 | 45 |
| bovada | fanduel | 6 | -0.0579 | -0.0662 | +0.0078 | +0.0096 | +0.0098 | 2 | 0 |
| bovada | hardrockbet | 158 | -0.0359 | -0.0349 | +0.0107 | +0.0454 | +0.0652 | 28 | 10 |
| bovada | williamhill_us | 65 | -0.0553 | -0.0536 | -0.0360 | -0.0184 | -0.0169 | 0 | 0 |
| consensus | betmgm | 502 | -0.1052 | -0.1041 | -0.0350 | +0.0247 | +0.0715 | 11 | 6 |
| consensus | betrivers | 166 | -0.0449 | -0.0463 | +0.0003 | +0.0265 | +0.0556 | 20 | 4 |
| consensus | draftkings | 5203 | -0.0439 | -0.0404 | -0.0215 | +0.0234 | +0.3110 | 167 | 62 |
| consensus | fanduel | 222 | -0.0328 | -0.0288 | +0.0104 | +0.0599 | +0.0652 | 38 | 13 |
| consensus | hardrockbet | 203 | -0.0339 | -0.0349 | +0.0154 | +0.0454 | +0.0652 | 40 | 18 |
| consensus | williamhill_us | 218 | -0.0545 | -0.0538 | -0.0225 | +0.0246 | +0.0362 | 10 | 6 |

A DraftKings rung at Pinnacle's number is priced a median 4.7 points worse than Pinnacle's fair value: of 1,928 such rungs, 113 are at or better than fair and 35 reach the 0.02 cut.

### 8.2 Full grid, named references

| season | reference | cut | bets | W-L-P | units | risked | ROI | 95% interval | 1st half | 2nd half | close value (n / mean) | price min / med / max | shorter than -200 | no action | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026 | pinnacle | 0.02 | 37 | 18-19-0 | +2.65 | 30.2 | +8.8% | (-21.8%, +46.2%) | 19 / -3.7% | 18 / +19.8% | 14 / +0.0387 | -134 / +117 / +429 | 0.0% | 3 | 0 |
| 2026 | pinnacle | 0.03 | 22 | 11-11-0 | +1.99 | 17.5 | +11.3% | (-22.9%, +53.4%) | 13 / +2.3% | 9 / +22.7% | 5 / +0.0843 | -134 / +122 / +429 | 0.0% | 3 | 0 |
| 2026 | pinnacle | 0.04 | 9 | 5-4-0 | +1.91 | 6.2 | +30.9% | (-52.9%, +134.2%) | 7 / +72.2% | 2 / -100.0% | 3 / +0.1288 | +120 / +130 / +429 | 0.0% | 2 | 0 |
| 2026 | pinnacle | 0.05 | 5 | 2-3-0 | -0.25 | 3.2 | -8.0% | (-100.0%, +217.9%) | 3 / +72.9% | 2 / -100.0% | 1 / +0.3110 | +126 / +145 / +429 | 0.0% | 1 | 0 |
| 2026 | pinnacle | 0.06 | 2 | 2-0-0 | +2.00 | 0.9 | +217.9% | (+146.0%, +429.0%) | 2 / +217.9% | 0 | 1 / +0.3110 | +146 / +288 / +429 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.08 | 2 | 2-0-0 | +2.00 | 0.9 | +217.9% | (+146.0%, +429.0%) | 2 / +217.9% | 0 | 1 / +0.3110 | +146 / +288 / +429 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.02 | 49 | 20-29-0 | -2.10 | 37.7 | -5.6% | (-36.2%, +26.0%) | 29 / +4.1% | 20 / -18.4% | 14 / +0.0309 | -144 / +125 / +429 | 0.0% | 0 | 1 |
| 2026 | bovada | 0.03 | 28 | 11-17-0 | -1.98 | 20.3 | -9.7% | (-42.2%, +26.3%) | 16 / +18.2% | 12 / -44.0% | 5 / +0.0406 | -143 / +130 / +429 | 0.0% | 0 | 1 |
| 2026 | bovada | 0.04 | 13 | 4-9-0 | -2.75 | 9.1 | -30.3% | (-73.6%, +28.7%) | 9 / -0.3% | 4 / -100.0% | 2 / +0.0446 | -143 / +145 / +429 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.05 | 9 | 3-6-0 | -1.86 | 6.3 | -29.4% | (-78.9%, +41.0%) | 6 / +10.4% | 3 / -100.0% | 2 / +0.0446 | -143 / +145 / +429 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.06 | 4 | 2-2-0 | +0.54 | 2.4 | +22.8% | (-100.0%, +217.9%) | 3 / +72.9% | 1 / -100.0% | 0 | +130 / +146 / +429 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.08 | 2 | 2-0-0 | +2.00 | 0.9 | +217.9% | (+146.0%, +429.0%) | 2 / +217.9% | 0 | 0 | +146 / +288 / +429 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.02 | 87 | 37-50-0 | -2.30 | 68.4 | -3.4% | (-24.3%, +30.8%) | 66 / +0.3% | 21 / -13.9% | 28 / +0.0278 | -144 / +120 / +429 | 0.0% | 1 | 1 |
| 2026 | consensus | 0.03 | 48 | 19-29-0 | -3.12 | 36.5 | -8.5% | (-39.9%, +26.9%) | 35 / +6.9% | 13 / -47.1% | 10 / +0.0403 | -120 / +121 / +429 | 0.0% | 0 | 1 |
| 2026 | consensus | 0.04 | 22 | 8-14-0 | -1.75 | 15.0 | -11.6% | (-58.5%, +47.0%) | 18 / +8.0% | 4 / -100.0% | 3 / +0.0442 | -102 / +139 / +429 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.05 | 11 | 5-6-0 | +0.79 | 7.0 | +11.2% | (-83.3%, +115.3%) | 8 / +64.4% | 3 / -100.0% | 0 | +125 / +140 / +429 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.06 | 7 | 4-3-0 | +1.76 | 4.6 | +37.9% | (-69.4%, +143.8%) | 6 / +62.0% | 1 / -100.0% | 0 | +128 / +140 / +429 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.08 | 2 | 2-0-0 | +2.00 | 0.9 | +217.9% | (+146.0%, +429.0%) | 2 / +217.9% | 0 | 0 | +146 / +288 / +429 | 0.0% | 0 | 0 |

### 8.3 The placebo (bets / ROI)

| season | reference | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|
| 2026 | bovada | 49 / -5.6% | 28 / -9.7% | 13 / -30.3% | 9 / -29.4% | 4 / +22.8% | 2 / +217.9% |
| 2026 | consensus | 87 / -3.4% | 48 / -8.5% | 22 / -11.6% | 11 / +11.2% | 7 / +37.9% | 2 / +217.9% |
| 2026 | pinnacle | 37 / +8.8% | 22 / +11.3% | 9 / +30.9% | 5 / -8.0% | 2 / +217.9% | 2 / +217.9% |
| 2026 | betmgm | 7 / -38.8% | 5 / -57.0% | 4 / -46.0% | 2 / +11.5% | 0 | 0 |
| 2026 | espnbet | 57 / +16.1% | 36 / -1.4% | 17 / -33.0% | 3 / -100.0% | 1 / -100.0% | 1 / -100.0% |
| 2026 | fanduel | 125 / -2.8% | 86 / +1.8% | 31 / -6.7% | 13 / +15.1% | 8 / +36.4% | 2 / +245.9% |
| 2026 | fliff | 19 / +23.9% | 11 / +30.8% | 6 / +18.6% | 5 / +47.8% | 4 / +82.2% | 1 / +140.0% |
| 2026 | hardrockbet | 61 / -6.4% | 34 / -9.0% | 15 / +11.4% | 13 / +31.4% | 7 / +1.1% | 0 |
| 2026 | williamhill_us | 28 / +20.7% | 15 / +37.9% | 7 / +30.0% | 2 / +134.7% | 2 / +134.7% | 0 |

### 8.4 By soft book and by market, named references (bets / units / ROI)

| reference | book | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|
| bovada | betmgm | 4 / +0.48u / +14.1% | 3 / -0.52u / -19.2% | 2 / -1.52u / -100.0% | 1 / -0.69u / -100.0% | 1 / -0.69u / -100.0% |  |
| bovada | betrivers | 2 / -1.69u / -100.0% | 1 / -0.80u / -100.0% | 1 / -0.80u / -100.0% | 1 / -0.80u / -100.0% |  |  |
| bovada | draftkings | 35 / -3.30u / -12.9% | 20 / -2.89u / -21.4% | 8 / -0.65u / -12.8% | 6 / +0.40u / +9.8% | 2 / +2.00u / +217.9% | 2 / +2.00u / +217.9% |
| bovada | hardrockbet | 8 / +2.41u / +34.4% | 4 / +2.23u / +66.8% | 2 / +0.23u / +14.4% | 1 / -0.77u / -100.0% | 1 / -0.77u / -100.0% |  |
| consensus | betmgm | 5 / -0.57u / -12.9% | 3 / -0.52u / -19.2% | 2 / -1.52u / -100.0% | 1 / -0.69u / -100.0% | 1 / -0.69u / -100.0% |  |
| consensus | betrivers | 4 / +0.31u / +8.7% | 2 / -1.69u / -100.0% | 1 / -0.80u / -100.0% | 1 / -0.80u / -100.0% |  |  |
| consensus | draftkings | 48 / -4.57u / -12.5% | 28 / -1.30u / -6.5% | 11 / -0.22u / -3.3% | 4 / +0.83u / +39.6% | 2 / +2.00u / +217.9% | 2 / +2.00u / +217.9% |
| consensus | fanduel | 13 / +4.06u / +42.8% | 6 / +2.40u / +54.6% | 5 / +1.40u / +39.8% | 4 / +2.22u / +82.2% | 3 / +1.22u / +53.8% |  |
| consensus | hardrockbet | 13 / -2.12u / -18.4% | 8 / -1.21u / -17.9% | 3 / -0.60u / -24.7% | 1 / -0.77u / -100.0% | 1 / -0.77u / -100.0% |  |
| consensus | williamhill_us | 4 / +0.58u / +19.9% | 1 / -0.79u / -100.0% |  |  |  |  |
| pinnacle | betmgm | 3 / -2.57u / -100.0% | 2 / -1.52u / -100.0% | 2 / -1.52u / -100.0% | 1 / -0.69u / -100.0% |  |  |
| pinnacle | betrivers | 4 / +1.92u / +44.6% | 3 / +0.92u / +27.1% |  |  |  |  |
| pinnacle | draftkings | 26 / +2.63u / +12.9% | 15 / +2.36u / +21.4% | 5 / +3.21u / +104.6% | 3 / +1.21u / +70.5% | 2 / +2.00u / +217.9% | 2 / +2.00u / +217.9% |
| pinnacle | fanduel | 2 / +0.58u / +51.6% |  |  |  |  |  |
| pinnacle | hardrockbet | 2 / +0.09u / +5.2% | 2 / +0.23u / +14.4% | 2 / +0.23u / +14.4% | 1 / -0.77u / -100.0% |  |  |

| reference | market | 0.02 | 0.03 | 0.04 | 0.05 | 0.06 | 0.08 |
|---|---|---|---|---|---|---|---|
| bovada | player_pass_tds | 26 / +1.03u / +5.6% | 14 / +0.62u / +6.7% | 6 / -2.55u / -62.2% | 4 / -1.50u / -49.1% | 1 / -0.69u / -100.0% |  |
| bovada | player_pass_yds | 3 / -0.83u / -31.1% | 1 / +1.00u / +120.0% | 1 / +1.00u / +120.0% |  |  |  |
| bovada | player_reception_yds | 13 / -1.98u / -17.6% | 9 / -2.17u / -28.5% | 2 / +0.17u / +11.0% | 1 / +1.00u / +146.0% | 1 / +1.00u / +146.0% | 1 / +1.00u / +146.0% |
| bovada | player_rush_yds | 7 / -0.32u / -6.0% | 4 / -1.43u / -53.7% | 4 / -1.36u / -52.5% | 4 / -1.36u / -52.5% | 2 / +0.23u / +23.0% | 1 / +1.00u / +429.0% |
| consensus | player_pass_tds | 29 / +3.54u / +17.5% | 12 / +2.67u / +37.4% | 6 / -0.12u / -3.9% | 3 / -0.07u / -4.6% | 1 / -0.69u / -100.0% |  |
| consensus | player_pass_yds | 6 / +0.35u / +6.9% | 3 / +1.18u / +48.7% | 3 / +1.18u / +48.7% | 1 / +1.00u / +130.0% | 1 / +1.00u / +130.0% |  |
| consensus | player_reception_yds | 18 / -2.64u / -16.8% | 13 / -1.89u / -17.1% | 2 / +0.17u / +11.0% | 1 / +1.00u / +146.0% | 1 / +1.00u / +146.0% | 1 / +1.00u / +146.0% |
| consensus | player_receptions | 20 / -0.79u / -5.0% | 9 / -1.40u / -19.0% | 4 / -0.99u / -33.0% |  |  |  |
| consensus | player_rush_yds | 14 / -2.77u / -24.2% | 11 / -3.68u / -43.3% | 7 / -1.98u / -40.2% | 6 / -1.14u / -28.0% | 4 / +0.45u / +18.0% | 1 / +1.00u / +429.0% |
| pinnacle | player_pass_tds | 13 / -0.36u / -4.0% | 5 / -0.01u / -0.5% | 2 / +0.31u / +25.0% | 1 / -0.69u / -100.0% |  |  |
| pinnacle | player_pass_yds | 4 / +2.08u / +49.2% | 2 / +2.00u / +92.0% | 1 / +1.00u / +120.0% |  |  |  |
| pinnacle | player_reception_yds | 11 / -0.49u / -5.2% | 8 / +0.45u / +6.6% | 3 / +1.17u / +50.3% | 1 / +1.00u / +146.0% | 1 / +1.00u / +146.0% | 1 / +1.00u / +146.0% |
| pinnacle | player_receptions | 1 / +1.00u / +99.0% |  |  |  |  |  |
| pinnacle | player_rush_yds | 8 / +0.42u / +6.3% | 7 / -0.44u / -8.0% | 3 / -0.56u / -31.3% | 3 / -0.56u / -31.3% | 1 / +1.00u / +429.0% | 1 / +1.00u / +429.0% |

### 8.5 Verdict for the ladders

**Nothing clears** (0 of 18 named cells; 0 reach 150 bets). The largest named cell has 87 bets (consensus, cut 0.02). At the 0.02 cut: Pinnacle 37 bets, +2.65 units, +8.8% (-21.8%, +46.2%); Bovada 49 bets, -2.10 units, -5.6% (-36.2%, +26.0%); consensus 87 bets, -2.30 units, -3.4% (-24.3%, +30.8%).

DraftKings alone at the 0.02 cut: pinnacle: 26 bets, +2.63 units, +12.9%; bovada: 35 bets, -3.30 units, -12.9%; consensus: 48 bets, -4.57 units, -12.5%.

### 8.6 A data fault in the stored ladders (found after the ladder grid, POST-HOC)

One winning bet above was a DraftKings rung at +429 on a number Pinnacle priced as a coin flip (Bo Jackson rushing yards 69.5, 2026-10-03). In that pull DraftKings' stored ladder for him runs 39.5 at -101, 49.5 at +169, 69.5 at +429, then 70.5 at -119 and 99.5 at +235: the price gets shorter at a higher line, which a single over ladder cannot do. So that stored ladder is not one product; what the second one is was not established. Counted across every ladder (a ladder = one book, player, market and pull; broken = implied probability rises by more than 0.01 at a higher line):

| book | ladders | broken ladders | broken share | rungs | rungs in broken ladders |
|---|---|---|---|---|---|
| betmgm | 4505 | 1 | 0.02% | 15485 | 5 |
| betrivers | 2546 | 0 | 0.00% | 11765 | 0 |
| draftkings | 14053 | 52 | 0.37% | 129462 | 744 |
| fanduel | 9741 | 0 | 0.00% | 78025 | 0 |
| hardrockbet | 6811 | 0 | 0.00% | 25220 | 0 |
| williamhill_us | 2594 | 31 | 1.20% | 21182 | 298 |

The same grid on ordered ladders only (named references; everything else unchanged):

| season | reference | cut | bets | W-L-P | units | risked | ROI | 95% interval | 1st half | 2nd half | close value (n / mean) | price min / med / max | shorter than -200 | no action | dropped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026 | pinnacle | 0.02 | 36 | 17-19-0 | +1.65 | 29.9 | +5.5% | (-24.8%, +40.9%) | 18 / -10.9% | 18 / +19.8% | 13 / +0.0177 | -134 / +116 / +240 | 0.0% | 3 | 0 |
| 2026 | pinnacle | 0.03 | 21 | 10-11-0 | +0.99 | 17.3 | +5.7% | (-28.5%, +42.6%) | 12 / -8.1% | 9 / +22.7% | 4 / +0.0277 | -134 / +120 / +235 | 0.0% | 3 | 0 |
| 2026 | pinnacle | 0.04 | 8 | 4-4-0 | +0.91 | 6.0 | +15.3% | (-71.8%, +96.1%) | 6 / +53.6% | 2 / -100.0% | 2 / +0.0377 | +120 / +128 / +181 | 0.0% | 2 | 0 |
| 2026 | pinnacle | 0.05 | 4 | 1-3-0 | -1.25 | 2.9 | -42.6% | (-100.0%, +146.0%) | 2 / +15.9% | 2 / -100.0% | 0 | +126 / +138 / +146 | 0.0% | 1 | 0 |
| 2026 | pinnacle | 0.06 | 1 | 1-0-0 | +1.00 | 0.7 | +146.0% |  | 1 / +146.0% | 0 | 0 | +146 / +146 / +146 | 0.0% | 0 | 0 |
| 2026 | pinnacle | 0.08 | 1 | 1-0-0 | +1.00 | 0.7 | +146.0% |  | 1 / +146.0% | 0 | 0 | +146 / +146 / +146 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.02 | 48 | 19-29-0 | -3.10 | 37.4 | -8.3% | (-39.3%, +23.0%) | 28 / -0.6% | 20 / -18.4% | 14 / +0.0309 | -144 / +122 / +264 | 0.0% | 0 | 1 |
| 2026 | bovada | 0.03 | 27 | 10-17-0 | -2.98 | 20.1 | -14.8% | (-47.1%, +17.4%) | 15 / +9.5% | 12 / -44.0% | 5 / +0.0406 | -143 / +129 / +264 | 0.0% | 0 | 1 |
| 2026 | bovada | 0.04 | 12 | 3-9-0 | -3.75 | 8.8 | -42.5% | (-82.0%, -5.2%) | 8 / -16.8% | 4 / -100.0% | 2 / +0.0446 | -143 / +138 / +264 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.05 | 8 | 2-6-0 | -2.86 | 6.1 | -46.9% | (-100.0%, -7.8%) | 5 / -15.1% | 3 / -100.0% | 2 / +0.0446 | -143 / +138 / +264 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.06 | 3 | 1-2-0 | -0.46 | 2.1 | -21.4% | (-100.0%, +146.0%) | 2 / +15.9% | 1 / -100.0% | 0 | +130 / +145 / +146 | 0.0% | 0 | 0 |
| 2026 | bovada | 0.08 | 1 | 1-0-0 | +1.00 | 0.7 | +146.0% |  | 1 / +146.0% | 0 | 0 | +146 / +146 / +146 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.02 | 86 | 36-50-0 | -3.30 | 68.1 | -4.8% | (-25.2%, +28.7%) | 65 / -1.6% | 21 / -13.9% | 28 / +0.0278 | -144 / +120 / +264 | 0.0% | 1 | 1 |
| 2026 | consensus | 0.03 | 47 | 18-29-0 | -4.12 | 36.3 | -11.3% | (-42.6%, +21.7%) | 34 / +3.1% | 13 / -47.1% | 10 / +0.0403 | -120 / +120 / +264 | 0.0% | 0 | 1 |
| 2026 | consensus | 0.04 | 21 | 7-14-0 | -2.75 | 14.8 | -18.6% | (-63.0%, +33.5%) | 17 / -0.2% | 4 / -100.0% | 3 / +0.0442 | -102 / +139 / +264 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.05 | 10 | 4-6-0 | -0.21 | 6.8 | -3.1% | (-100.0%, +93.1%) | 7 / +45.7% | 3 / -100.0% | 0 | +125 / +135 / +264 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.06 | 6 | 3-3-0 | +0.76 | 4.4 | +17.2% | (-100.0%, +108.2%) | 5 / +39.0% | 1 / -100.0% | 0 | +128 / +135 / +146 | 0.0% | 0 | 0 |
| 2026 | consensus | 0.08 | 1 | 1-0-0 | +1.00 | 0.7 | +146.0% |  | 1 / +146.0% | 0 | 0 | +146 / +146 / +146 | 0.0% | 0 | 0 |

Still nothing clears (0 of 18 named cells; largest 86 bets). A rung taken from one of these ladders cannot be assumed to be the full-game stat at that number.

## Files

- `scripts/ncaaf_search/audit_2026_11/props/main.py`: definitions, grid, sensitivities, post-hoc variant
- `scripts/ncaaf_search/audit_2026_11/props/main_v1_as_first_run.py`: the script exactly as first run, before the post-hoc variant
- `scripts/ncaaf_search/audit_2026_11/props/verdict.py`: applies the clearing rule
- `scripts/ncaaf_search/audit_2026_11/props/gen_report.py`: builds this file
- `scripts/ncaaf_search/audit_2026_11/props/alt.py / alt_report.py`: the alternate-ladder section
- `scripts/ncaaf_search/audit_2026_11/props/inspect1.py .. inspect6.py`: inventory only, no results
- `scripts/ncaaf_search/audit_2026_11/props/grid.csv`: every cell
- `scripts/ncaaf_search/audit_2026_11/props/breakdowns.csv`: by market / book / side
- `scripts/ncaaf_search/audit_2026_11/props/diagnostics.csv`: comparison counts
- `scripts/ncaaf_search/audit_2026_11/props/bets.parquet`: every locked bet in every cell
- `scripts/ncaaf_search/audit_2026_11/props/verdict.csv`: the four tests per named cell
- `scripts/ncaaf_search/audit_2026_11/props/crosscheck.py / crosscheck_out.txt`: five cells recomputed with different code; six results matched to the raw log
- `scripts/ncaaf_search/audit_2026_11/props/alt_monotone.py`: the broken-ladder count and the ordered-ladders-only grid
- `scripts/ncaaf_search/audit_2026_11/props/alt_grid.csv / alt_m_grid.csv / alt_bets.parquet`: the alternate-ladder cells and bets
- `scripts/ncaaf_search/audit_2026_11/props/grid_v1_first_run.csv`: the grid exactly as first produced, before the post-hoc variant

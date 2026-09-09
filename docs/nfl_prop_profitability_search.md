# The search for a profitable NFL prop model: what was tried, what won

*2026-09-09, at mike's instruction: "don't come back until you find the
features / data / approach to making the eleven distributional models winning
in backtest, a projected profitable model."* This is the complete record of
that search. Every number is a measurement from this session on the current
cache; the scripts that produced them are named so each table can be re-run.

**What won.** One of the eleven, `nfl_prop_tackles_assists`, was never
losing: it was grading the wrong stat. With the stat corrected it measures
**+50.24 units over 363 bets (+13.84%, 90% CI +5.2 to +23.2), positive in all
three seasons**, its projection carries information the line does not (§4),
and it beats its own naive-projection placebo in every season. It is paused,
and unpausing is a model update.

**What did not.** At DraftKings, on the other ten markets, nothing beats the
line: not the player features, not the sharp books' lines, not the retail
consensus, not DK's own movement, not the injury report, not Next Gen Stats.
DraftKings prices its standard prop lines flat at −115 both sides on most
yardage rows, so at DK the market's information is entirely in the line, and
the line is hung as well as Pinnacle's at seven hours out (§2, §3).

**The lead.** A market-anchored model on pass attempts, betting the SOFT books
against a learned weighting of the sharp references, reads +16.5% in both
2024 and 2025 with intervals excluding zero and five times the shipped rule's
volume, but +3.1% and not significant on 2023 and the retail placebo is not
cleanly zero. It is two seasons of three, not the bar (§5).

---

## 1. The starting point

`docs/nfl_prop_information_test.md` (same day, earlier) had established that
the eleven's player and context features hold less information than the
DraftKings line: the book beats the raw model on Brier on every market, a
calibration reaches the book's number and no further, and the residual
coefficient never clears zero out of sample. So the search moved to what the
line might NOT hold: the rest of the market, and outside data.

## 2. The board at DraftKings is priced flat

Share of DK standard-line rows priced with the SAME price on both sides
(−115/−115, −110/−110 and the like), 2023 / 2024 / 2025:

| market | 2023 | 2024 | 2025 |
|---|---|---|---|
| pass_yards | 77% | 72% | 30% |
| rush_rec_yards | 78% | 74% | 13% |
| rec_yards | 56% | 51% | 13% |
| rush_yards | 50% | 48% | 13% |
| receptions | 5% | 6% | 1% |
| pass_tds | 3% | 5% | 1% |

Most common price pair across all DK rows: −115/−115 on 5,218 rows. A book
that prices flat carries no information in its price; whatever it knows is in
the LINE. A DK-decided model therefore wins only by knowing the true median
sits away from DK's number.

## 3. Everything that could tell a DK-decided model where the median sits

`scripts/nfl_prop_market_stack` builds, for every DK row the backtest dumped,
the board as it stood at or before that row's own snapshot: each sharp book's
main line and fair, its fair at DK's line where it quotes it, the retail
consensus line and fair, DK's own line at t72 and t48, and the book's
adjustment against the player's rolling-8. `scripts/nfl_prop_dk_signal_sweep`
grades each as a one-feature bet at the DK price, per season, both directions,
on a fixed grid. Thresholds are not tuned; every cell is printed.

**Result: across ten markets, six signals, a four-point grid and three
seasons, not one cell is positive with an interval excluding zero in all three
seasons.** The single-season flags are what chance produces at that number of
cells (pass_attempts fade-movement 2025 +32% on 32 bets; rec_yards adjustment
2025 +13% on 179 bets, −2% in both prior seasons; receptions movement 2023
+31% on 98 bets, −11% and −14% after).

Receiving yards, the largest market, in detail: Pinnacle's line above DK's
predicts overs at 42.6% (2023), 49.5% (2024), 44.5% (2025). DK's own line
having risen 3+ points from t72: 59.0%, 50.5%, 42.4%. The line sitting 15+
yards below the rolling-8: 45.1%, 47.7%, 43.4%. Noise, every one.

**The learned version says the same.** A ridge logistic with the book's own
logit(fair) as an OFFSET (coefficient fixed at one, so the stack can only move
off the price where a feature earns it), fitted 2023 → 2024 and 2023-24 →
2025, on the sharp features alone and on everything:

| market | 2024 book / sharp / full | 2025 book / sharp / full |
|---|---|---|
| pass_yards | .2500 / .2594 / .2593 | .2501 / .2534 / .2523 |
| rec_yards | .2496 / .2629 / .2676 | .2500 / .2514 / .2514 |
| receptions | .2468 / .2479 / .2514 | .2451 / .2452 / .2461 |
| rush_yards | .2501 / .2790 / .2798 | .2499 / .2513 / .2520 |
| pass_attempts | .2510 / .2681 / .2691 | .2511 / .2533 / .2589 |
| anytime_td | .1928 / .1914 / .1918 | .1876 / .1867 / .1870 |

Lower is better; the book wins or ties everywhere but anytime_td, where the
0.001 gain produces no bets at any cut.

### 3a. The injury report

`scripts/nfl_prop_injury_signal`: nflverse's weekly report, bounded at the
row's snapshot by its modification timestamp (66% carry one), for the player's
own designation and for teammates in his position group. Coverage is real
(rec_yards: 35% of rows have a position-mate Out or Doubtful, 31% have the QB
flagged). **No offensive market shows a cell positive in more than one
season, in either direction.** DK has priced the Friday report by Sunday
morning.

### 3b. Next Gen Stats, and the leak that made it look like a model

Weekly NGS receiving (separation, cushion, intended air yards, YAC over
expectation, catch rate), 2023-25. The first pass merged on the current week
and produced +12% to +45% ROI in every season for EVERY feature — top quartile
and bottom quartile alike. That is the signature of a subset, not a signal:
the NGS weekly file only has a row for a player who saw enough targets THAT
week, so its presence reveals the outcome. Rebuilt with an as-of join to the
latest prior week: the presence itself grades −5% to −15%, and no feature is
positive in two seasons. Recorded here because it is exactly the kind of
result that ships if nobody asks why both quartiles won.

## 4. Tackles: the wrong stat, fixed, and what is left

### The defect

The book grades "tackles + assists" as the box-score TOTAL. Against ESPN's
`TOT` column on 193 player-games (2024 week 10):

| definition | matches ESPN TOT | mean gap |
|---|---|---|
| nflverse solo + assists (what the game log held) | 77.7% | −0.26 |
| nflverse solo + with_assist | 29.0% | −1.69 |
| **nflverse solo + with_assist + assists** | **94.8%** | **−0.07** |

The game log had never ingested `def_tackles_with_assist`, though the feed the
ingestor already reads carries it. Re-checked after the fix on full game days:
2024-11-10 the corrected stat matches ESPN on 100.0% of 222 rows, 2025-11-09
on 99.2% of 241. Ingested for 2015-2025 (167k rows, `def_tackles_with_assist`
non-null on 99.9%), the feature engine rolls it and builds the target from it,
and refuses to build tackles features if the column is empty.

### The model on the corrected stat

`models.nfl_prop_backtest --model nfl_prop_tackles_assists --seasons 2023 2024
2025`, the deployed hyperparameters, walk-forward, the live cut (0.70 / 0.15):

| | bets | win % | ROI | 90% CI | units |
|---|---|---|---|---|---|
| **all** | **363** | **62.8%** | **+13.84%** | **(+5.2, +23.2)** | **+50.24** |
| 2023 | 113 | 55.8% | +1.86% | | |
| 2024 | 144 | 68.1% | +24.10% | | |
| 2025 | 106 | 63.2% | +12.68% | | |

Sides: 319 unders (+16.6%), 44 overs (−6.1%). Universe: our actual now lands
over 47.8% against the book's 50.2% (was 41.1% vs 50.2%), the same −2.4pp the
book runs on rush_yards and receptions, so the stat is no longer a different
stat. The model's own mean P(over) is 45.5%, 2.3pp under reality: the same
mean bias as the other ten, and the model wins anyway.

**The placebo** (`--placebo`: the player's own rolling-8 of all three tackle
components as the projection, same distribution, same cut): 392 bets, +1.15%,
CI (−7.7, +10.2); 2023 −13.0%, 2024 +12.2%, 2025 +3.9%. The model beats it in
every season, by 15pp, 12pp and 9pp. (The placebo had been built from two
components and projected low; fixed this session, and it is the fair one that
is reported.) The corrected stat is not a blind-unders artefact either: blind
unders at DK grade −9.8%, +1.2%, +5.1% across the three seasons.

**The information test** (`scripts/nfl_prop_information_test` on the corrected
rows): the residual coefficient is +0.15 ± 0.06 fitted on 2023 and +0.24 ± 0.06
on 2024, the blend beats the book on Brier in both test seasons (0.2470 vs
0.2492 on 2024; 0.2461 vs 0.2477 on 2025), and the blend as a bet at the DK
price is positive with an interval excluding zero at the 3% and 4% cuts in
BOTH test seasons (2024: +19.0% on 95, +29.3% on 56; 2025: +8.4% on 369,
+9.3% on 297). It is the only one of the eleven for which any of that is true.

**What has not been done:** the live artifact was trained on the old stat and
must be retrained; the model is paused (`config.PAUSED_MODELS`, with the
unpause condition "reconciled against a gamebook source and the gap closes",
which this session met); unpausing is a model update.

## 5. The soft-book stack: the lead that is two seasons of three

The shipped rule (`models/nfl_prop_market`) bets a soft book against a sharp
fair at the same line and is the only NFL prop construction with validated
edge. `scripts/nfl_prop_market_stack --soft` asks whether LEARNING that
comparison beats thresholding it: the same offset logistic, fitted on the
soft-book rows (every soft book's newest two-sided open quote per proposition,
one bet per proposition-side at the best edge), graded at the price paid.

Cells positive in all three seasons at the same cut, with how many carry an
interval excluding zero:

| market | construction | cut | 2023 | 2024 | 2025 | seasons excl. zero |
|---|---|---|---|---|---|---|
| **pass_attempts** | sharp-stack | 5% | +3.1% (152) | **+16.5% (109)** | **+16.4% (150)** | 2 |
| pass_attempts | sharp-stack | 6% | +2.5% (121) | +20.2% (77) | +21.1% (106) | 2 |
| tackles_assists | full-stack | 4% | +10.3% (397) | +22.9% (247) | +1.4% (264) | 2 |
| pass_tds | sharp-stack | 2% | +1.3% (338) | +12.7% (150) | +17.8% (262) | 1 |
| rec_yards | full-stack | 6% | +14.3% (317) | +12.5% (83) | +16.0% (59) | 1 |

pass_attempts is also the only market where the sharp-stack beats the book's
own fair on Brier in all three seasons (.2485/.2500, .2486/.2499, .2483/.2506).
The 2023 read is fitted on 2024-25 and read backwards, because no market
history exists before 2023.

**The placebo is not clean.** With fanduel standing in as the reference the
same cell reads +9.7% (78 bets) in 2024 and +15.8% (37) in 2025, intervals
spanning zero; with betmgm it is thin or negative. A retail reference produces
a third of the volume and no significance, which is what "sharp-specific"
should look like, but the point estimates are not zero and the third season is
not significant. Two of three, not the bar. It would also bet the soft books,
not DraftKings, so it is a second `nfl_prop_market`-style construction rather
than one of the eleven.

## 6. What this settles

- **A DraftKings-decided distributional model has no information to work
  with on ten of eleven markets.** Player features, sharp lines, consensus,
  movement, adjustment, injuries and NGS were each graded across three seasons
  and none survives two. The book prices flat and hangs its line as well as
  Pinnacle does at seven hours.
- **Tackles is the profitable distributional model.** It always was; the
  ruler was wrong. +50.24u over 363 bets, three positive seasons, information
  beyond the line, ahead of its placebo.
- **The only edge in the wider data is other books' prices**, which the
  shipped rule already takes, and which a learned stack may take better on
  pass attempts.

Reproduce:

```
python -m models.nfl_prop_backtest --all --seasons 2023 2024 2025 --dump <rows>
python -m scripts.nfl_prop_market_stack --rows <rows> --cache <feats>            # DK rows
python -m scripts.nfl_prop_market_stack --rows <rows> --cache <feats> --soft     # soft-book rows
python -m scripts.nfl_prop_market_stack --rows <rows> --cache <feats> --soft --placebo fanduel --models nfl_prop_pass_attempts
python -m scripts.nfl_prop_dk_signal_sweep --feats <feats>/dk --only-flagged
python -m scripts.nfl_prop_injury_signal --feats <feats>/dk
python -m models.nfl_prop_backtest --model nfl_prop_tackles_assists --seasons 2023 2024 2025 [--placebo]
```

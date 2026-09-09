# The search for a profitable NFL prop model: what was tried, what won

*2026-09-09, at mike's instruction: "don't come back until you find the
features / data / approach to making the eleven distributional models winning
in backtest, a projected profitable model."* This is the complete record of
that search. Every number is a measurement from this session on the current
cache; the scripts that produced them are named so each table can be re-run.

**What won.** One of the eleven, `nfl_prop_tackles_assists`, was never
losing: it was grading the wrong stat. With the stat corrected it measures
**+53.03 units over 340 bets (+15.6%, 90% CI +6.4 to +24.8), positive in all
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
2025`, the hyperparameters of the artifact retrained on the corrected stat
(v20260909_160911, the registered one), walk-forward, the live cut (0.70 /
0.15). That cut was swept on the OLD stat's record, so it is out of sample
with respect to this target:

| | bets | win % | ROI | 90% CI | units |
|---|---|---|---|---|---|
| **all** | **340** | **63.8%** | **+15.60%** | **(+6.4, +24.8)** | **+53.03** |
| 2023 | 100 | 58.0% | +5.37% | | |
| 2024 | 141 | 70.9% | +28.98% | | |
| 2025 | 99 | 59.6% | +6.86% | | |

Three positive seasons; the pooled interval excludes zero, and only 2024 does
so on its own (the backtest's own verdict string says "one season"). Sides:
301 unders (+17.8%), 39 overs (−1.7%). On the previous artifact's
hyperparameters the same run reads +50.24u over 363 bets (+13.84%, CI +5.2
to +23.2; +1.9% / +24.1% / +12.7%), so the result is not a property of one
parameter draw. The correction bit hardest in 2024: the 2025 feed already
folds most with-assist tackles into the other columns (the old stat matched
ESPN 93% there against 83% in 2024), so 2025 is graded nearly the same before
and after. Universe: our actual now lands
over 47.8% against the book's 50.2% (was 41.1% vs 50.2%), the same −2.4pp the
book runs on rush_yards and receptions, so the stat is no longer a different
stat. The model's own mean P(over) is 45.5%, 2.3pp under reality: the same
mean bias as the other ten, and the model wins anyway.

**The placebo** (`--placebo`: the player's own rolling-8 of all three tackle
components as the projection, same distribution, same cut): 376 bets, +0.59%,
CI (−8.7, +9.5); 2023 −13.6%, 2024 +12.3%, 2025 +3.4%. The model beats it in
every season, by 19pp, 17pp and 3pp. (The placebo had been built from two
components and projected low; fixed this session, and it is the fair one that
is reported.) The corrected stat is not a blind-unders artefact either: blind
unders at DK grade −9.8%, +1.2%, +5.1% across the three seasons.

**The information test** (`scripts/nfl_prop_information_test` on the corrected
rows): the residual coefficient is +0.14 ± 0.06 fitted on 2023 and +0.23 ± 0.06
on 2024, the blend beats the book on Brier in both test seasons (0.2471 vs
0.2492 on 2024; 0.2459 vs 0.2477 on 2025), and the blend as a bet at the DK
price is positive with an interval excluding zero at the 3% cut in BOTH test
seasons (2024: +21.3% on 82; 2025: +9.3% on 360, and +12.7% on 286 at 4%). It is the only one of the eleven for which any of that is true.

**What has not been done:** the artifact HAS been retrained on the corrected
stat and registered (v20260909_160911, holdout 2025 O/U accuracy 0.666); the model is paused (`config.PAUSED_MODELS`, with the
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

### 4a. Found while checking: the backtest was not grading the deployed hyperparameters

`models/nfl_prop_backtest` reads hyperparameters from
`models/saved/nfl_prop_params.json`, and that file still carried the
2026-08-23 versions for all twelve models while the registry had pointed at the
2026-09-07 retrains since then. Every prop backtest between those dates
(including the −40.53u table and the information test) graded the 08-23
parameters. Refreshed from the active artifacts this session and pinned by
`tests/test_nfl_prop_params_match_artifacts.py`; the eleven re-graded on the
deployed parameters are in the session log.

## 7. The second pass: every remaining DraftKings data set, graded

*mike, after the first pass: "the ten other prop models actually do have
plenty of DraftKings data -- did you look hard enough, what is missing?"*
What had not been used: DK's earlier snapshots, DK's own alternate ladders,
DK's line movement as a target, and a nonlinear learner over the market
features. Each is now graded.

### 7a. The other snapshots: t72, t48, t24, t1

`nfl_prop_backtest --all --seasons 2023 2024 2025 --snapshot <type>`, the
models unchanged, live cuts, DK price at that snapshot:

| snapshot | rows with bets | best market | worst market | any interval excluding zero on the positive side |
|---|---|---|---|---|
| t72 (3 days out) | 8 markets | receptions +3.2% (322) | rec_yards −9.2% (189) | none |
| t48 | 9 markets | receptions +3.6% (471) | pass_yards −12.0% (128) | none |
| t24 (2024-25 only) | 8 markets | receptions +1.2% (199) | pass_yards −23.5% (32) | none |
| t1 (2024-25 only; 2,928 DK rows, 115 bets across the ten) | 7 markets | pass_yards +41.7% (8) | pass_tds −1.6% (3) | none; the largest cell is receptions +14.6% (52), CI (−9.6, +40.0) |

Earlier lines are not softer for these models, and the one-hour snapshot is
too thin to say anything on its own (rush_attempts, rush_rec_yards, tackles
and sacks have no t1 rows at all).

### 7b. The model does predict where DraftKings will move its line

Correlation between (projection − t72 line) and (game-day line − t72 line),
lines that moved, per season:

| market | n | corr | 2023 | 2024 | 2025 | when the model sits above the t72 line, DK raises it |
|---|---|---|---|---|---|---|
| receptions | 364 | +0.66 | +0.73 | +0.64 | +0.62 | 93% |
| pass_completions | 293 | +0.31 | +0.45 | +0.13 | +0.34 | 83% |
| pass_attempts | 354 | +0.25 | +0.24 | +0.25 | +0.25 | 70% |
| pass_yards | 1,031 | +0.21 | +0.23 | +0.17 | +0.28 | 64% |
| rec_yards | 2,577 | +0.12 | +0.14 | +0.12 | +0.10 | 63% |

That is real, stable information about the market's own next move. It does
not pay: betting the model's direction at the t72 price wins 51.8% on rec
yards (needs 53.5% at −115), fading it wins 48.2%, and the mean move captured
is +0.4 yards on rec yards, +1.1 on pass yards, +0.12 on receptions --
smaller than the vig on every market. The model and the book read the same
public statistics; the book reads them a day later and moves a little.

### 7c. DraftKings' own alternate ladders

DK's standard line is flat but its alternate ladder (over 40.5 at −250 …
over 80.5 at +400) is where its prices vary, and a distributional model
claims exactly that tail. `scripts/nfl_prop_dk_alt_ladder` prices every DK
alternate strike quoted at or before the row's snapshot with the model's
fitted tail (574,525 DK alternate rows, 21,153 propositions, 2023-25; the
ladder is over-only from 2024).

**Calibration across the ladder, all markets: the models' far tail is too
fat and their near tail too thin.** Pass yards at 1.5× the line and beyond:
model 5.8%, realised 3.5%, DK 4.5%. Rec yards: 11.5% / 9.9% / 12.5%.
Receptions: 8.3% / 6.2% / 9.0%. At 0.6-0.85× the line the models sit 4-14pp
UNDER realised on every market.

**Graded as bets**, one per (proposition, strike) at first: rec_yards,
receptions, rush_yards, rush_rec_yards, pass_completions all negative with
intervals excluding zero in 2025. Pass yards looked like the exception
(+20% / +9% at 5%, +26% / +17% at 8%, both seasons' intervals excluding zero
at 8%). It is not: **one bet per proposition** (the best-edge strike, which
is what a bettor can actually place without stacking correlated strikes on
one quarterback) gives

| cut | 2024 | 2025 |
|---|---|---|
| 5% | +16.7% (414, CI −4.4 to +38.6) | −1.4% (163) |
| 8% | +22.7% (354, CI −0.6 to +46.7) | −1.8% (102) |
| 12% | +42.3% (201, CI +9.4 to +76.6) | −0.8% (45) |

at average odds of +580. At the selected bets the model says 28.6% and
realised is 18.4% (2024), 38.3% vs 26.5% (2025): the model's tail is wrong by
ten points in its own favour. The 2024 result exists because DK's 2024
ladder implied 15.7% where 18.4% landed -- a book error the naive rolling-8
projection also collected (+13.8% at 8%) -- and in 2025 DK's implied (25.6%)
matches realised (26.5%). A one-season mispricing by the book, since fixed,
not a model edge.

### 7d. A nonlinear market-anchored classifier

`scripts/nfl_prop_dk_boost`: a small gradient-boosted classifier on the
market features and the projection, early-stopped on the training season's
own tail, graded at the DK price. On eight of ten markets early stopping
chooses 0-1 trees (nothing to learn); where it grows trees it memorises
(pass_yards 2025: train Brier 0.2209, test 0.2548 against the book's 0.2501).
On the corrected tackles rows it does not beat the eleven's own model
(Brier 0.2512 / 0.2479 vs the book's 0.2492 / 0.2477).

### 7e. What is left that this repo holds

Nothing. `player_prop_odds` holds **zero** NFL rows with
`snapshot_type='in_play'`, in production and in the cache, so the live-prop
programme CLAUDE.md names as the priority has no recorded history to build
on either; that is a recording gap, not a feature for these ten. Every
DraftKings prop data set this repo holds -- the main line at five pre-game
snapshots, the alternate ladder, the line's own movement, the other books'
prices around it -- has now been graded against these models across three
seasons.

## 8. What this settles

- **A DraftKings-decided distributional model has no information to work
  with on ten of eleven markets.** Player features, sharp lines, consensus,
  movement, adjustment, injuries and NGS were each graded across three seasons
  and none survives two. The book prices flat and hangs its line as well as
  Pinnacle does at seven hours.
- **Tackles is the profitable distributional model.** It always was; the
  ruler was wrong. +53.03u over 340 bets, three positive seasons, information
  beyond the line, ahead of its placebo in each.
- **The only edge in the wider data is other books' prices**, which the
  shipped rule already takes, and which a learned stack may take better on
  pass attempts.
- **Second pass (§7): DraftKings is efficient against these models at every
  snapshot we hold and on its alternate ladder.** The models predict DK's
  own next move, and the move is worth less than the vig.

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

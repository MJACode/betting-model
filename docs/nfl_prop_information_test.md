# The eleven NFL prop models: do they know anything the line does not?

*Measured 2026-09-09, at mike's question: "how do we get the models profitable
... it seems like you've done absolutely nothing with new data."* The new data
(the Kalshi ladders, the alternate backfill, the sharp-book restore) timed the
one working rule and graded two constructions that failed. None of it had
touched the eleven distributional models. This is the measurement that says
whether anything can.

**Short answer: no. The projections carry no information the DraftKings line
does not already hold, out of sample, on any of the eleven markets.** A
calibration fix removes their 87%-unders bias and, with it, every bet.

---

## 1. Why they bet under 87% of the time

`models/nfl_prop_backtest --all` now records the model's own mean P(over) on
every row it could have bet, beside the actual over-rate and the book's
de-vigged one (`model_over_pct`, `model_gap_pp`, `mean_pred`, `mean_actual`).
Seasons 2024-25, DraftKings `open` quotes, one flat unit per bet:

| model | quoted rows | actual over % | book over % | **model over %** | gap pp | mean pred | mean actual |
|---|---|---|---|---|---|---|---|
| pass_yards | 942 | 50.3 | 50.0 | 48.1 | −2.2 | 228.45 | 227.48 |
| pass_attempts | 826 | 46.4 | 49.9 | 45.9 | −0.5 | 31.57 | 31.40 |
| pass_completions | 828 | 48.2 | 49.8 | 44.8 | −3.4 | 20.44 | 20.50 |
| pass_tds | 916 | 50.1 | 48.1 | 44.8 | −5.3 | 1.44 | 1.52 |
| rush_yards | 1,244 | 48.0 | 50.1 | 45.0 | −3.0 | 57.55 | 59.52 |
| rush_attempts | 984 | 47.6 | 50.2 | 43.1 | −4.5 | 13.43 | 13.90 |
| rec_yards | 3,177 | 47.6 | 50.1 | 47.9 | +0.3 | 46.95 | 46.73 |
| receptions | 3,114 | 47.2 | 49.8 | 46.7 | −0.5 | 4.00 | 4.01 |
| rush_rec_yards | 1,916 | 49.2 | 50.0 | 44.8 | −4.4 | 65.26 | 68.51 |
| anytime_td | 5,915 | 28.7 | 31.8 | 27.6 | −1.1 | 0.28 | 0.29 |
| sacks | 1,747 | 37.4 | 37.9 | 32.8 | −4.6 | 0.41 | 0.44 |
| tackles_assists (paused, definitional) | 2,347 | 41.1 | 50.2 | 38.6 | −2.5 | 5.88 | 6.03 |

Ten of eleven put P(over) below the rate at which overs actually land. On most
markets the projected MEAN is itself below the actual mean of the quoted
players (rush_rec_yards 65.3 vs 68.5, rush_yards 57.6 vs 59.5): the model is
trained on every player-game and the book only quotes the productive ones, so
the projection regresses the quoted tail toward the population. That is a
mean bias, correctable without a retrain. Whether correcting it helps is §2.

## 2. The information test

`scripts/nfl_prop_information_test`, on every quoted row the backtest dumped
(`--dump`), fitted on 2024 and read on 2025:

```
logit P(over) = a + c · logit(book_fair) + b · z,   z = (projection − line) / sd
```

If the projection adds anything to the line, `b` is positive with an interval
excluding zero in a season the fit never saw. Brier on 2025 (lower is better;
the book is the bar):

| model | n 2025 | book | raw model | calibrated model | blend | b (fit 2024) | b (refit 2025) |
|---|---|---|---|---|---|---|---|
| pass_yards | 468 | 0.2501 | 0.2621 | 0.2502 | 0.2500 | +0.02 ± 0.09 | +0.01 ± 0.09 |
| pass_attempts | 467 | 0.2511 | 0.2599 | 0.2506 | 0.2500 | −0.14 ± 0.11 | +0.04 ± 0.09 |
| pass_completions | 468 | 0.2507 | 0.2537 | 0.2575 | 0.2670 | −0.28 ± 0.11 | +0.16 ± 0.09 |
| pass_tds | 468 | 0.2423 | 0.2443 | 0.2428 | 0.2427 | +0.08 ± 0.16 | +0.19 ± 0.14 |
| rush_yards | 622 | 0.2499 | 0.2554 | 0.2501 | 0.2510 | −0.05 ± 0.08 | +0.17 ± 0.09 |
| rush_attempts | 540 | 0.2483 | 0.2689 | 0.2500 | 0.2483 | +0.14 ± 0.10 | +0.06 ± 0.09 |
| rec_yards | 1,594 | 0.2500 | 0.2579 | 0.2497 | 0.2494 | −0.05 ± 0.05 | +0.01 ± 0.05 |
| receptions | 1,586 | 0.2451 | 0.2545 | 0.2481 | 0.2445 | +0.01 ± 0.06 | +0.02 ± 0.05 |
| rush_rec_yards | 566 | 0.2501 | 0.2524 | 0.2525 | 0.2520 | −0.03 ± 0.06 | +0.14 ± 0.08 |
| anytime_td | 2,924 | 0.1876 | 0.1893 | 0.1896 | 0.1863 | +0.08 ± 0.08 | +0.07 ± 0.07 |
| sacks | 831 | 0.2259 | 0.2273 | 0.2274 | 0.2262 | −0.00 ± 0.09 | +0.10 ± 0.08 |

Read across:

- **The book beats the raw model on all eleven.** Every one.
- **Calibrating the model brings it to the book's Brier and no further.** A
  calibrated copy of the line is not a model.
- **`b` is never positive with an interval excluding zero in both seasons.**
  Five of eleven flip sign between 2024 and 2025. The projection does not add
  to the line.
- **The blend does not beat the book by more than 0.001 Brier anywhere.**

## 3. The blend as a bet

The fitted equation's probability against the DraftKings price on 2025, one
bet per side per row, at four cuts. Because the blend collapses onto the line,
the yardage markets produce **zero bets at a 2% cut**: pass_yards 0,
receptions 0, rush_rec_yards 0, rush_yards 3, rec_yards 28. The cells with
volume:

| model | cut | bets | win % | units | ROI | 90% CI |
|---|---|---|---|---|---|---|
| pass_attempts | 3% | 137 | 56.9 | +14.58 | +10.64% | (−2.6, +24.1) |
| pass_attempts | 4% | 104 | 57.7 | +12.95 | +12.45% | (−2.8, +27.7) |
| pass_completions | 2–5% | 160–267 | 47 | −24 to −40 | −13 to −15% | **excludes zero, negative** |
| rush_attempts | 2% | 153 | 52.3 | +0.47 | +0.31% | (−12.5, +13.2) |
| pass_tds | 3% | 80 | 43.8 | +4.30 | +5.38% | (−16.8, +27.5) |
| sacks | 2% | 21 | 9.5 | −11.73 | −55.9% | (−100, −10.7) |

pass_attempts is one cell whose interval spans zero and whose `b` is negative
in the season it was fitted on. The only intervals excluding zero are negative.

`tackles_assists` shows +9.66% to +12.83% with intervals excluding zero at
every cut, and it is not usable: our computed actual lands over the line
41.1% of the time against the book's 50.2%, which is a different stat, not an
edge (the reason it is paused). The blend inherits that fiction.

## 4. What this settles

- **No calibration and no threshold makes the eleven profitable.** The
  feature set holds less information than the DraftKings line at ~7h to
  kickoff, and correcting the bias produces a model that agrees with the book.
- **The under-skew was a symptom, not a strategy,** and the diagnostic that
  would have shown it on day one (`model_over_pct`) is now part of every
  backtest run.
- **The eleven are live and losing.** Their backtest at the live cuts is
  −12.26 units over 1,521 bets for 2024-25 (−40.53u over 2,133 including 2023,
  `docs/nfl_prop_offset_evidence.md`). Pausing them is a model update and
  mike's call.
- **What would be a model:** a residual against a market-implied distribution
  (the ladder, `models/prop_ladder`) with information the market lacks. The
  current feature set is not that information. The one construction with
  validated edge remains `models/nfl_prop_market`.

Reproduce:

```
python -m models.nfl_prop_backtest --all --dump <dir>
python -m scripts.nfl_prop_information_test --rows <dir>
```

# NHL full-game totals, with the referee crew

Backtest only. `USE_NHL_REF_FEATURES` in `models/nhl_totals_market.py` is False, and this run did not register an artifact or change a threshold, a stake, or a pause. The live card still prices Pinnacle's no-vig against the bettable books in the newest pre-game fetch.

**Recommendation: leave the flag off.** It fails the bar: the referee card is ahead by +2.2 units and the 95% interval on that gap includes zero; a test season is behind the rule; the EV floors next to 0.01 do not keep the gain.

On the same slate the rule bets 356 times for +19.1 units (+5.38%, close EV +1.32%). The referee card bets 1153 times for +21.4 units (+1.85%, close EV -1.67%).

## Head to head

Same quotes, same games (a stored referee and a historical total), the totals lab's rule: the first pre-game snapshot where a bettable book's price at Pinnacle's number has EV at least 0.010, price -200 or better, one bet a game. Profit is one unit risked at the price taken (the lab's grade). The interval resamples game days, 2,000 times, seed 11.

| card | bets | units | ROI | 95% by day |
|---|---:|---:|---:|---|
| Pinnacle no-vig (the live rule's backtest) | 356 | +19.1 | +5.38% | -5.0% .. +15.6% |
| Pinnacle no-vig plus referee deviations | 1153 | +21.4 | +1.85% | -3.9% .. +7.3% |

Unit difference (referee card minus the rule): **+2.2** units, day-clustered 95% **-66.9 .. +72.2**.

Games both cards bet: 269. Same side: 218 (identical ticket 139). Opposite side: 51. Rule only: 87. Referee card only: 884.

Taken as a filter on the rule's own tickets (same game, fetch, book and side; the referee probability still has to clear the EV floor):

| rule tickets | bets | units | ROI |
|---|---:|---:|---:|
| still clears | 213 | +15.3 | +7.17% |
| dropped | 143 | +3.9 | +2.71% |

## By season, side, and half

Seasons are ending years. 2023-24 is the first season with officials, so it trains the first fold and is not a test season. Each later season is fit on every earlier priced season only.

| season | rule bets | rule units | rule ROI | ref bets | ref units | ref ROI |
|---|---:|---:|---:|---:|---:|---:|
| 2024-25 | 164 | +14.3 | +8.70% | 762 | -14.0 | -1.83% |
| 2025-26 | 192 | +4.9 | +2.55% | 391 | +35.4 | +9.04% |

| side | rule bets | rule units | rule ROI | ref bets | ref units | ref ROI |
|---|---:|---:|---:|---:|---:|---:|
| over | 143 | +0.8 | +0.53% | 546 | +13.8 | +2.54% |
| under | 213 | +18.4 | +8.64% | 607 | +7.5 | +1.24% |

Half-season split at the middle game date of that season's scored slate (the games, not the bets):

| season | half | split date | rule bets | rule units | ref bets | ref units |
|---|---|---|---:|---:|---:|---:|
| 2024-25 | early | 2025-01-30 | 98 | +8.4 | 447 | -8.2 |
| 2024-25 | late | 2025-01-30 | 66 | +5.9 | 315 | -5.8 |
| 2025-26 | early | 2026-01-24 | 123 | +4.2 | 274 | +15.8 |
| 2025-26 | late | 2026-01-24 | 69 | +0.6 | 117 | +19.6 |

## Prices, calibration, closing line

Every scored test game at Pinnacle's first pre-game total (pushes out): 2628 games. Log loss, market 0.69265, referee model 0.69257 (gap 0.00008). Calibration error (binned absolute gap, weighted): market 0.42 points, model 1.00 points.

| bin | n | market predicted | market actual | model predicted | model actual |
|---|---:|---:|---:|---:|---:|
| 0.00–0.45 | 15 | 0.441 | 0.533 | 0.437 | 0.549 |
| 0.45–0.50 | 1211 | 0.484 | 0.483 | 0.482 | 0.474 |
| 0.50–0.55 | 1395 | 0.515 | 0.510 | 0.519 | 0.515 |
| 0.55–1.00 | 7 | 0.557 | 0.857 | 0.560 | 0.607 |

On the bets themselves, the probability the card used against whether that side won (pushes out):

| card | bets | mean probability | win rate | calibration error |
|---|---:|---:|---:|---:|
| rule | 354 | 0.503 | 0.520 | 2.98 pts |
| referee | 1151 | 0.522 | 0.518 | 1.67 pts |

EV at Pinnacle's last pre-game price, only where that close is the same number as the bet (a moved number is a different proposition):

| card | bets | same number | line moved | mean EV at the close |
|---|---:|---:|---:|---:|
| rule | 356 | 324 | 32 | +1.32% |
| referee | 1153 | 956 | 197 | -1.67% |

## EV neighborhood

The model is not refit at each floor. The live floor is 0.01. A result that exists only in one cell is a peak.

| EV floor | rule bets | rule units | rule ROI | ref bets | ref units | ref ROI | unit diff | 95% |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0.000 | 794 | +12.1 | +1.52% | 1566 | +10.2 | +0.65% | -1.86 | -79.6 .. +80.7 |
| 0.005 | 530 | +24.0 | +4.52% | 1357 | +16.4 | +1.21% | -7.58 | -79.9 .. +67.4 |
| 0.010 | 356 | +19.1 | +5.38% | 1153 | +21.4 | +1.85% | 2.23 | -66.9 .. +72.2 |
| 0.015 | 220 | +17.6 | +8.02% | 985 | +7.0 | +0.71% | -10.61 | -73.4 .. +49.1 |
| 0.020 | 141 | -4.4 | -3.14% | 813 | +2.2 | +0.27% | 6.65 | -49.0 .. +58.9 |
| 0.030 | 39 | -2.9 | -7.35% | 566 | +0.4 | +0.07% | 3.25 | -42.0 .. +48.4 |

## What the fit used

Three crew means, each a referee's own earlier games shrunk toward the league mean of every earlier game (`K = 50`): goals per game, power-play opportunities per game (both teams' `pp_opportunities`, summed), and penalties per game (both teams' `times_shorthanded`, summed — penalties that left a team shorthanded; the team log has no raw penalty count). The feature is the shrunk rate minus the league mean, so a crew at the mean, and a referee with no earlier game, adds zero. The logistic model has no intercept: it cannot move Pinnacle's price without a deviation. Penalty `C` is chosen on the last quarter of the training rows from [0.1, 1.0, 10.0], then the model is refit on the whole training fold.

Officials cover the games in `nhl_game_officials`. Referee-dates with two games: 0 (a prior is still every game with an earlier commence time, so a shared face-off would not leak either way). Team-log goals disagreed with the scoreboard on 310 of 4591 joined games, and 310 of those are the log short by one (the shootout goal the total counts and the log does not). The goals feature uses the scoreboard. Power plays and penalties use the team log.

Quote rows after the same-fetch, same-number join: 97,042 on 4,189 games, seasons [2024, 2025, 2026]. Books: draftkings, fanduel, betmgm, williamhill_us, betrivers, hardrockbet, fanatics. Source `odds_api_historical`. 2026-27 is absent from that source, so it is not a fold.

Coefficients are the logit change per training standard deviation. Positive means a higher crew rate raises the over probability.

| test season | train seasons | C | n train | goals | power plays | penalties |
|---|---|---:|---:|---:|---:|---:|
| 2025 | 2024 | 0.1 | 1336 | -0.084 | +0.022 | +0.022 |
| 2026 | 2024, 2025 | 0.1 | 2657 | -0.051 | +0.012 | +0.012 |

On the 4591 joined games, `pp_opportunities` and `times_shorthanded` are equal on 4591 games (correlation 1.000). The two special-teams coefficients are one input entered twice. Penalty minutes, from the skater log, are the distinct count, and that ablation is its own row. Crew-feature correlations: goals/PP 0.135, goals/penalties 0.135, PP/penalties 1.000.

## Ablation

Each row is its own walk-forward, same quotes, same floor. "Intercept only" is a recalibration of Pinnacle with no crew input, so a referee result that matches it is the intercept.

| specification | ref bets | ref units | ref ROI | unit diff vs rule | 95% | log loss | market log loss |
|---|---:|---:|---:|---:|---|---:|---:|
| referees (headline) | 1153 | +21.4 | +1.85% | 2.23 | -66.9 .. +72.2 | 0.69257 | 0.69265 |
| drop goals | 755 | +5.1 | +0.67% | -14.09 | -60.4 .. +34.8 | 0.69265 | 0.69265 |
| drop power plays | 1152 | +24.4 | +2.12% | 5.23 | -64.8 .. +75.0 | 0.69257 | 0.69265 |
| drop penalties | 1152 | +24.4 | +2.12% | 5.23 | -64.8 .. +75.0 | 0.69257 | 0.69265 |
| linesmen instead | 513 | -6.3 | -1.23% | -25.46 | -62.8 .. +11.8 | 0.69307 | 0.69265 |
| referees plus linesmen | 1241 | -1.6 | -0.13% | -20.72 | -96.7 .. +58.6 | 0.69303 | 0.69265 |
| penalty minutes instead of times shorthanded | 1144 | +6.7 | +0.59% | -12.44 | -77.5 .. +54.7 | 0.69275 | 0.69265 |
| intercept only | 1611 | -16.0 | -0.99% | -35.15 | -114.1 .. +46.4 | 0.69304 | 0.69265 |

## Shrinkage neighborhood

The headline uses K = 50. The other values are the same walk with the prior weight changed. They are not a search that picked a winner.

| K | ref bets | ref units | ref ROI | unit diff | 95% |
|---:|---:|---:|---:|---:|---|
| 20 | 959 | +5.8 | +0.61% | -13.34 | -70.6 .. +44.4 |
| 50 | 1153 | +21.4 | +1.85% | 2.23 | -66.9 .. +72.2 |
| 100 | 1249 | +20.6 | +1.65% | 1.4 | -70.2 .. +75.4 |

## Checks behind the recommendation

All four had to hold, at K = 50 and the live 0.01 floor, before the features would be worth a separate decision to turn the flag on:

- fail: the referee card's units beat the rule, and the day-clustered 95% interval on that difference sits above zero
- pass: out-of-sample log loss on every scored test game beats Pinnacle's no-vig
- fail: every test season's unit difference is zero or positive
- fail: the unit difference is zero or positive at EV 0.005, 0.01 and 0.015

## What this did not change

The live total still decides on Pinnacle's no-vig in the newest fetch (`scripts/nhl_totals_card.py`). This backtest uses the lab's first qualifying snapshot, which is the selection the 0.01 floor was graded on. No row was written to `picks`. No artifact was saved.

Run: `python -m scripts.nhl_totals_referee_backtest`. The figures above are that script on `odds_api_historical`, read 2026-11-27.


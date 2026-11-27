# NHL points and assists with MoneyPuck, shift and referee inputs — walk-forward, 2026-11-27

Mike asked for a backtest, not a new live artifact. The live assists spec is
unchanged (`models/nhl_props.py`, `USE_MONEYPUCK_POINTS = False`). The card
does not call `assists_spec(True)`, `points_spec` or `add_points_features`.
Nothing was registered. Thresholds, stakes and pauses were not touched.

Points is not a live market. `config.py` still lists `player_points` as
collected and not modelled. There is no `nhl_prop_points` artifact, threshold
or card. The "current" points column below is the assists-shaped feature list
with the target swapped to points (`points_l`, `points_s`, `assists_l`,
`opp_ga`, `opp_pk_opps`, plus the same usage block). It is the spec the engine
would score. It is not a registered model.

```
python -m scripts.nhl_prop_backtest --moneypuck
```

Same walk-forward as the live artifacts: each season is scored by a model fit
only on earlier seasons (`FIRST_TRAIN_SEASON` 2019-20 through the season
before). The seasons scored are 2023-24, 2024-25, 2025-26 and 2026-27 to date
(MoneyPuck through 2026-11-24, skater log through 2026-11-25, open prices for
the games stored on 2026-11-27). Unders only, no per-game cap (assists has
none; points has no live cap), best expected value among the books the card
shops, price floor −200, the model's own probability. The assists cut is
`MODEL_OWN_EV_FLOOR["nhl_prop_assists"]` = 0.18. Points has no floor of its
own, so the same 0.18 is used and said so. Both specs are Poisson, the assists
choice. The distribution is not re-measured here. Overs are reported beside
the rule. Lines are x.5, so the bet lists have no pushes.

Credit MoneyPuck.com. The extra inputs, all from earlier games only (a row's
own xG, tonight's linemates, tonight's power-play count and the starter's
goals tonight are not inputs; tests in `tests/test_nhl_props.py`):

- skater `on_ice_f_x_goals`, `i_f_x_goals`, `i_f_primary_assists`, all
  situations, half-lives 30 and 6 (`moneypuck_skater_games`)
- power-play share: the player's share of his team's power-play time from the
  skater log, half-lives 20 and 4. This exists before the shift chart and is
  required
- power-play unit: the same linemate quality restricted to teammates with at
  least 30 seconds of power-play time that night, on their prior points rate
  and prior individual xG. The shift chart has no strength, so this is not a
  PP1/PP2 flag
- linemate quality: shared-seconds-weighted prior points and prior individual
  xG, from `nhl_shift_linemates`, then a shifted mean (half-lives 30 and 6)
- team pace and xG for: `shots_on_goal_for` and `x_goals_for`, all situations,
  half-life 25 (`moneypuck_team_games`)
- opponent `x_goals_against`, half-life 25
- opposing starter's goals saved above expected (`x_goals − goals` on
  `moneypuck_goalie_games`, joined to starts in `nhl_goalie_game_log`),
  half-life 25, five prior starts. The starter's identity is the input. His
  goals tonight are not
- referee power-play count: the mean of the referees' prior games, where a
  game's count is the sum of both teams' `times_shorthanded`
  (`nhl_game_officials`, role `referee`, regular season, half-life 25, five
  prior games)

Daily Faceoff and EDGE are not read. The shift chart and the officials feed
start on 2023-10-10, so the linemate, power-play unit and referee features are
missing before then and the row is kept (XGBoost treats the gap as missing).
Requiring them would have deleted the training set that scores 2023-24. The
other new features are required. A goalie without five prior starts is the
piece that shrinks the scored set: taking goalie quality out restores the
current row count.

350,717 of 365,278 regular-season skater-games had every required new feature.
149,922 had the shift-chart and referee features together. 1,057,180
regular-season linemate pairs. 8,669 regular-season referee rows.

Points, current features, rows the fit used and rows scored:
159,628 / 46,287 (2023-24), 205,922 / 46,157 (2024-25), 252,165 / 45,997
(2025-26), 298,306 / 12,786 (2026-27). Mean predicted against actual points:
0.48 vs 0.46, 0.46 vs 0.45, 0.46 vs 0.46, 0.47 vs 0.48.

Points, candidate features: 154,673 / 45,601, 200,281 / 45,324, 245,689 /
45,123, 290,956 / 12,526. Means: 0.48 vs 0.46, 0.45 vs 0.45, 0.46 vs 0.47,
0.47 vs 0.48.

Assists uses the same row counts. Current mean predicted against actual
assists: 0.30 vs 0.29, 0.29 vs 0.28, 0.29 vs 0.29, 0.30 vs 0.30. Candidate:
0.30 vs 0.29, 0.28 vs 0.28, 0.29 vs 0.29, 0.30 vs 0.30.

Priced player-games matched to a current-feature prediction, points:
19,679 / 18,919 / 20,837 / 7,218. Candidate: 19,383 / 18,568 / 20,446 / 7,056.
Assists current: 18,743 / 18,851 / 20,853 / 7,147. Candidate: 18,459 / 18,501 /
20,460 / 6,989. Points quotes: 379,495, of which 322 were after puck drop and
2,028 were incoherent. Assists quotes: 346,779, of which 304 were after puck
drop and 41 were incoherent.

Two stake readings. **1u risked** is what this script has always reported
(a loss is −1). **1u to win, risk capped at 3** is the published record's
stake.

## Points — not a live market

At EV ≥ 0.18, each model's own bets:

| | Bets | Hit | 1u risked | ROI | 95% by day | Log loss | Cal. error | Claimed vs hit | 1u to win |
|---|---:|---:|---:|---:|---|---:|---:|---|---:|
| Current features | 508 | 41.1% | +9.33u | +1.84% | −9.3% to +13.2% | 0.6703 | 0.0954 | 0.507 vs 0.411 | +2.97u, +0.59% (−7.1% to +8.1%) |
| Candidate features | 537 | 40.2% | −1.34u | −0.25% | −11.2% to +11.1% | 0.6728 | 0.1135 | 0.507 vs 0.402 | −5.68u, −1.06% (−8.4% to +6.7%) |

377 bets are in both sets (+1.07u, +0.29% either way). On those, log loss is
0.6630 (current probability) and 0.6643 (candidate probability). On 498 of
the 508 current bets, the candidate's probability has log loss 0.6687 and
calibration error 0.0986, against 0.6703 and 0.0954 for the current
probability.

### By season, own bets at EV ≥ 0.18 (1u risked)

| Season | Current | Candidate |
|---|---|---|
| 2023-24 | 314 bets, +3.44% (−12.3 to +18.8); early −5.4% / late +12.2% | 328 bets, −0.25% (−14.9 to +15.9); early −2.3% / late +1.8% |
| 2024-25 | 54 bets, +23.79% (−6.8 to +53.9); early +6.0% / late +41.6% | 66 bets, +21.36% (−8.3 to +50.7); early −10.0% / late +52.7% |
| 2025-26 | 70 bets, −6.79% (−30.0 to +17.8); early −17.4% / late +3.8% | 95 bets, −4.63% (−27.9 to +20.6); early +0.7% / late −9.9% |
| 2026-27 to date | 70 bets, −13.66% (−36.4 to +9.5); early −20.5% / late −6.8% | 48 bets, −21.31% (−43.1 to +1.0); early −10.3% / late −32.4% |

Every season's interval crosses zero or is negative. 2024-25 is the only
season with a large positive point estimate, on 54 and 66 bets.

### Overs

The rule scored here bets unders only. At the same cut, no per-game cap:

| | Bets | Hit | 1u risked | ROI | 95% by day |
|---|---:|---:|---:|---:|---|
| Current overs | 386 | 25.1% | −58.95u | −15.27% | −32.7% to +2.5% |
| Candidate overs | 437 | 27.5% | −42.91u | −9.82% | −24.6% to +5.2% |

Every best-EV over, no cut: 66,656 rows, −4,839.61u, −7.26% (current) and
65,456 rows, −4,810.25u, −7.35% (candidate). The over is where the book's
margin sits.

### Every scored under, not just the bets

One best-EV under per player-game, no EV cut and no price floor.

| | Rows | Log loss | Cal. error | Claimed | Hit | 1u risked | 95% by day |
|---|---:|---:|---:|---:|---:|---|---|
| Current | 66,653 | 0.6568 | 0.0054 | 0.550 | 0.548 | −3,061.80u, −4.59% | −5.5% to −3.6% |
| Candidate | 65,453 | 0.6565 | 0.0047 | 0.550 | 0.548 | −2,937.84u, −4.49% | −5.4% to −3.5% |

### The cut as a neighbourhood (own bets, 1u risked, no cap)

| EV ≥ | Current bets | Current units | Current ROI | Candidate bets | Candidate units | Candidate ROI |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 16,331 | −504.63 | −3.09% | 15,787 | −361.99 | −2.29% |
| 0.03 | 9,698 | −193.06 | −1.99% | 9,381 | −139.27 | −1.48% |
| 0.05 | 6,667 | −125.25 | −1.88% | 6,425 | −69.20 | −1.08% |
| 0.06 | 5,485 | −58.71 | −1.07% | 5,292 | −85.87 | −1.62% |
| 0.08 | 3,636 | −26.41 | −0.73% | 3,602 | −1.03 | −0.03% |
| 0.10 | 2,379 | −40.62 | −1.71% | 2,425 | +40.30 | +1.66% |
| 0.12 | 1,571 | −9.82 | −0.63% | 1,582 | +48.66 | +3.08% |
| 0.15 | 888 | +32.56 | +3.67% | 904 | +36.38 | +4.02% |
| 0.18 | 508 | +9.33 | +1.84% | 537 | −1.34 | −0.25% |
| 0.20 | 362 | +0.60 | +0.17% | 380 | −1.86 | −0.49% |

The candidate's day interval includes zero at every cut from 0.10 up, including
0.10 (−3.3% to +6.7%), 0.12 (−3.2% to +9.5%) and 0.15 (−4.2% to +12.4%). The
current features' intervals include zero at those cuts as well. There is no
plateau that clears.

### What happens when a group is removed

Same prices, same rule, EV ≥ 0.18. Linemate xG is built from the mate's prior
individual xG, so dropping the individual columns does not take that xG out of
the linemate feature.

| Removed | Bets | 1u risked | ROI | 95% by day | Log loss |
|---|---:|---:|---:|---|---:|
| Nothing (full candidate) | 537 | −1.34u | −0.25% | −11.2% to +11.1% | 0.6728 |
| Individual xG and primary assists | 535 | −8.57u | −1.60% | −12.9% to +10.1% | 0.6718 |
| Power-play share and unit | 553 | +23.04u | +4.17% | −7.0% to +15.8% | 0.6679 |
| Linemate quality | 544 | +25.46u | +4.68% | −6.6% to +16.5% | 0.6712 |
| Team pace and xG for | 509 | −7.60u | −1.49% | −12.3% to +10.3% | 0.6539 |
| Opponent xG against | 544 | +24.83u | +4.56% | −6.7% to +16.1% | 0.6598 |
| Goalie quality | 529 | +13.86u | +2.62% | −8.5% to +13.8% | 0.6723 |
| Referee power-play rate | 512 | −8.59u | −1.68% | −13.4% to +10.5% | 0.6634 |

Every removal's day interval includes zero. None is a list to register.

## Assists — the live market

At EV ≥ 0.18, each model's own bets:

| | Bets | Hit | 1u risked | ROI | 95% by day | Log loss | Cal. error | Claimed vs hit | 1u to win |
|---|---:|---:|---:|---:|---|---:|---:|---|---:|
| Current features | 227 | 51.1% | +32.25u | +14.21% | +0.5% to +28.0% | 0.6796 | 0.0512 | 0.546 vs 0.511 | +29.10u, +12.82% (+1.7% to +23.5%) |
| Candidate features | 266 | 49.6% | +32.63u | +12.27% | −1.5% to +25.6% | 0.6833 | 0.0452 | 0.539 vs 0.496 | +27.91u, +10.49% (−0.4% to +20.8%) |

176 bets are in both sets (+23.41u, +13.30% either way). On those, log loss is
0.6816 (current probability) and 0.6806 (candidate probability); calibration
error is 0.0586 and 0.0484. On 226 of the 227 current bets, the candidate's
probability has log loss 0.6793 and calibration error 0.0302, against 0.6796
and 0.0512 for the current probability.

### By season, own bets at EV ≥ 0.18 (1u risked)

| Season | Current | Candidate |
|---|---|---|
| 2023-24 | 159 bets, +17.07% (−0.2 to +33.3); early +16.3% / late +17.9% | 174 bets, +7.60% (−9.1 to +23.4); early +11.2% / late +4.0% |
| 2024-25 | 20 bets, +5.43%; early −16.7% / late +27.6% | 34 bets, +2.17% (−38.8 to +44.5); early −19.3% / late +23.6% |
| 2025-26 | 34 bets, +22.32% (−12.7 to +58.4); early +58.9% / late −14.3% | 47 bets, +38.80% (+5.7 to +74.3); early +38.2% / late +39.4% |
| 2026-27 to date | 14 bets, −25.47%; early −29.9% / late −21.1% | 11 bets, +3.94%; early +18.2% / late −7.9% |

2024-25 and 2026-27 are under 30 bets on the current list, so they have no day
interval. 2023-24 is the only current season with a large bet count, and its
interval touches zero. The candidate is flat there. 2025-26 is the candidate's
best cell and the only one whose interval clears zero, on 47 bets.

### Overs

| | Bets | Hit | 1u risked | ROI | 95% by day |
|---|---:|---:|---:|---:|---|
| Current overs | 357 | 29.7% | +18.55u | +5.20% | −11.8% to +23.1% |
| Candidate overs | 350 | 27.7% | −22.59u | −6.46% | −24.8% to +11.8% |

Every best-EV over, no cut: 65,602 rows, −6,435.70u, −9.81% (current) and
64,417 rows, −6,336.18u, −9.84% (candidate). The current model's overs at the
cut are a positive point estimate whose interval includes zero, on top of a
side that loses about 10% with no cut. It is not a side to add.

### Every scored under, not just the bets

| | Rows | Log loss | Cal. error | Claimed | Hit | 1u risked | 95% by day |
|---|---:|---:|---:|---:|---:|---|---|
| Current | 65,594 | 0.6239 | 0.0030 | 0.657 | 0.657 | −2,238.29u, −3.41% | −4.1% to −2.8% |
| Candidate | 64,409 | 0.6236 | 0.0039 | 0.658 | 0.657 | −2,174.18u, −3.38% | −4.0% to −2.7% |

### The cut as a neighbourhood (own bets, 1u risked, no cap)

| EV ≥ | Current bets | Current units | Current ROI | Candidate bets | Candidate units | Candidate ROI |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 8,995 | −167.21 | −1.86% | 9,039 | −17.20 | −0.19% |
| 0.03 | 5,081 | −63.46 | −1.25% | 5,216 | −7.57 | −0.15% |
| 0.05 | 3,313 | −12.00 | −0.36% | 3,567 | +17.38 | +0.49% |
| 0.06 | 2,695 | +42.39 | +1.57% | 2,959 | +15.31 | +0.52% |
| 0.08 | 1,763 | +54.57 | +3.10% | 1,931 | +68.85 | +3.57% |
| 0.10 | 1,121 | +102.52 | +9.15% | 1,312 | +91.00 | +6.94% |
| 0.12 | 722 | +75.04 | +10.39% | 883 | +80.31 | +9.09% |
| 0.15 | 406 | +60.80 | +14.98% | 454 | +59.51 | +13.11% |
| 0.18 | 227 | +32.25 | +14.21% | 266 | +32.63 | +12.27% |
| 0.20 | 167 | +28.47 | +17.05% | 182 | +27.57 | +15.15% |

From 0.10 up the current features win more units at 0.10, 0.15 and 0.20, and
a higher return per bet at every cut except 0.08. At 0.10 the current interval
is +3.2% to +15.5% and the candidate's is +1.2% to +12.6%. At the live cut the
current interval clears zero and the candidate's does not.

### What happens when a group is removed

| Removed | Bets | 1u risked | ROI | 95% by day | Log loss |
|---|---:|---:|---:|---|---:|
| Nothing (full candidate) | 266 | +32.63u | +12.27% | −1.5% to +25.6% | 0.6833 |
| Individual xG and primary assists | 260 | +31.76u | +12.22% | −1.8% to +25.8% | 0.6801 |
| Power-play share and unit | 285 | +40.87u | +14.34% | +1.9% to +27.7% | 0.6740 |
| Linemate quality | 273 | +40.85u | +14.96% | +1.6% to +28.2% | 0.6795 |
| Team pace and xG for | 267 | +53.59u | +20.07% | +7.0% to +33.7% | 0.6749 |
| Opponent xG against | 255 | +51.39u | +20.15% | +6.6% to +33.1% | 0.6857 |
| Goalie quality | 269 | +44.90u | +16.69% | +2.7% to +30.7% | 0.6722 |
| Referee power-play rate | 266 | +40.75u | +15.32% | +1.6% to +28.4% | 0.6794 |

Taking out team pace, or opponent xG against, raises units above both the full
candidate and the current model's +32.25. Those two cells were not themselves
walked as a model: one removal is not a new spec, and opponent xG against
makes log loss worse (0.6857 against the current 0.6796). On all 64,409
candidate unders, log loss stays 0.6236 when either group is removed.

## Recommendation

Do not replace the live assists artifact, and do not register a points model.

Assists at the live cut: the candidate's units are +32.63 against +32.25 at
1u risked (+27.91 against +29.10 at 1u to win), on more bets, so the return
per bet is lower. Its day interval crosses zero. Its log loss is worse. The
current interval clears zero. Overs lose when every over is taken. Keep the
flag off.

Points has no live model. At the same cut the candidate is −1.34u against
+9.33u for the assists-shaped features, and both intervals include a loss.
The positive cells from 0.10 to 0.15 do not clear zero. The market stays
research.

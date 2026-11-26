# nhl_prop_shots_on_goal with MoneyPuck and shift inputs — walk-forward, 2026-11-26

Mike asked for a backtest, not a new live artifact. The live spec is unchanged
(`models/nhl_props.py`, `USE_MONEYPUCK_SHOTS = False`). The card does not call
`shots_spec(True)` or `add_moneypuck_skater_features`. Nothing was registered.
Thresholds, stakes and pauses were not touched.

```
python -m scripts.nhl_prop_backtest --moneypuck --model nhl_prop_shots_on_goal
```

Same walk-forward as the live artifact: each season is scored by a model fit
only on earlier seasons (`FIRST_TRAIN_SEASON` 2019-20 through the season
before). The seasons scored are 2023-24, 2024-25, 2025-26 and 2026-27 to date
(MoneyPuck through 2026-11-25, skater log and open prices through the games
stored on 2026-11-26). Unders only, at most 3 a game, best expected value among
the books the card shops, price floor −200, the model's own probability. The
live cut is `MODEL_OWN_EV_FLOOR["nhl_prop_shots_on_goal"]` = 0.18. The live
model does not bet overs. Overs are reported beside the rule.

Credit MoneyPuck.com. The extra inputs, all from earlier games only (a row's
own xG, tonight's linemates and the opponent's shots tonight are not inputs;
tests in `tests/test_nhl_props.py`):

- skater `i_f_x_goals`, `i_f_shot_attempts`, `i_f_high_danger_shots`, all
  situations, half-lives 30 and 6 (`moneypuck_skater_games`)
- TOI and power-play TOI trend, short mean minus long mean (the levels are
  already on the live spec)
- linemate quality: shared-seconds-weighted prior xG of teammates, from
  `nhl_shift_linemates`, then a shifted mean (half-lives 30 and 6)
- power-play deployment: the player's share of his team's power-play time
  (half-lives 20 and 4), and the same linemate quality restricted to teammates
  with at least 30 seconds of power-play time that night. The shift chart has
  no strength, so this is not a PP1/PP2 flag. Daily Faceoff and EDGE are not
  read. The chart starts in 2023-24, so those two features are missing before
  then and the row is kept (XGBoost treats the gap as missing). Requiring them
  would have deleted the training set that scores 2023-24.
- opponent `shots_on_goal_against` and `x_goals_against`, all situations,
  half-life 25 (`moneypuck_team_games`)

359,871 of 365,261 regular-season skater-games had every required new feature.
151,186 had the shift-chart features. 1,057,180 regular-season linemate pairs.
Both fits trained on the same rows (43,961 / 90,188 / 136,413 / 182,538) and
scored the same player-games (46,220 / 46,139 / 45,981 / 12,767). Priced
player-games: 18,096 / 17,355 / 18,376 / 5,944.

Two stake readings. **1u risked** is what this script has always reported
(a loss is −1). **1u to win, risk capped at 3** is the published record's
stake. ROI on an identical bet list cannot differ between models. Lines are
x.5, so there are no pushes.

## Live cut, each model's own bets

| | Bets | Hit | 1u risked | ROI | 95% by day | Log loss | Cal. error | Claimed vs hit | 1u to win |
|---|---:|---:|---:|---:|---|---:|---:|---|---:|
| Current features | 1,216 | 52.4% | +104.45u | +8.59% | +2.7% to +14.4% | 0.6989 | 0.0749 | 0.598 vs 0.524 | +89.61u, +7.37% (+2.1% to +12.6%) |
| Candidate features | 919 | 52.8% | +84.03u | +9.14% | +2.5% to +15.8% | 0.6968 | 0.0727 | 0.600 vs 0.528 | +72.01u, +7.84% (+1.7% to +14.1%) |

729 bets are in both sets (+81.64u, +11.20% either way). On those, log loss is
0.6955 (current probability) and 0.6916 (candidate probability); calibration
error is 0.0727 and 0.0663. On the 1,216 current bets, the candidate's
probability has log loss 0.6928 and calibration error 0.0594, against 0.6989
and 0.0749 for the current probability.

## By season, own bets at EV ≥ 0.18 (1u risked)

| Season | Current | Candidate |
|---|---|---|
| 2023-24 | 215 bets, +5.97% (−8.6 to +20.8); early −4.2% / late +16.0% | 169 bets, +0.49% (−16.4 to +17.4); early +6.3% / late −5.3% |
| 2024-25 | 321 bets, +8.85% (−3.0 to +20.8); early +11.9% / late +5.8% | 243 bets, +10.08% (−2.2 to +22.4); early +4.9% / late +15.2% |
| 2025-26 | 328 bets, +5.99% (−4.0 to +15.9); early +2.7% / late +9.3% | 217 bets, +5.40% (−7.9 to +18.6); early −5.3% / late +16.0% |
| 2026-27 to date | 352 bets, +12.37% (+0.9 to +22.5); early +20.3% / late +4.5% | 290 bets, +16.20% (+4.3 to +27.5); early +11.3% / late +21.1% |

2023-24 is scored by a model fit on seasons that have no shift chart, so the
shift features are missing in that fit. That season is the candidate's worst,
and its interval crosses zero. 2026-27 is the season in progress. Its interval
overlaps the current model's.

## Overs

The live rule bets unders only. At the same cut, with no per-game cap:

| | Bets | Hit | 1u risked | ROI | 95% by day |
|---|---:|---:|---:|---:|---|
| Current overs | 247 | 46.2% | −7.83u | −3.17% | −16.5% to +10.8% |
| Candidate overs | 132 | 48.5% | −0.53u | −0.40% | −16.3% to +15.9% |

Every best-EV over, no cut: 59,769 rows, about −7.7% for both models. The
over is where the book's margin sits. It is not a side to add.

## Every scored under, not just the bets

One best-EV under per player-game, no EV cut and no price floor: 59,770 rows,
the same games for both models.

| | Log loss | Cal. error | Claimed | Hit | 1u risked | 95% by day |
|---|---:|---:|---:|---:|---|---|
| Current | 0.6828 | 0.0141 | 0.519 | 0.518 | −887.52u, −1.48% | −2.3% to −0.6% |
| Candidate | 0.6822 | 0.0114 | 0.516 | 0.518 | −901.77u, −1.51% | −2.4% to −0.7% |

## The cut as a neighbourhood (own bets, 1u risked, cap of 3)

| EV ≥ | Current bets | Current units | Current ROI | Candidate bets | Candidate units | Candidate ROI |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 11,895 | +204.21 | +1.72% | 11,407 | +211.99 | +1.86% |
| 0.03 | 10,312 | +190.12 | +1.84% | 9,493 | +358.20 | +3.77% |
| 0.05 | 8,897 | +254.85 | +2.86% | 7,884 | +283.22 | +3.59% |
| 0.06 | 8,084 | +244.41 | +3.02% | 7,006 | +275.39 | +3.93% |
| 0.08 | 6,378 | +240.51 | +3.77% | 5,386 | +264.53 | +4.91% |
| 0.10 | 4,851 | +220.35 | +4.54% | 3,947 | +136.30 | +3.45% |
| 0.12 | 3,501 | +158.41 | +4.52% | 2,785 | +152.28 | +5.47% |
| 0.15 | 2,078 | +137.18 | +6.60% | 1,593 | +115.07 | +7.22% |
| 0.18 | 1,216 | +104.45 | +8.59% | 919 | +84.03 | +9.14% |
| 0.20 | 825 | +107.88 | +13.08% | 609 | +81.44 | +13.37% |

The candidate's return per bet is higher at 0.03 through 0.08 and again from
0.12 up. At 0.10 the current features are ahead on both units and return per
bet. From 0.12 up the candidate bets fewer and wins fewer units, including at
the live cut. That is not a plateau that replaces the live list.

## What happens when a group is removed

Same prices, live rule, EV ≥ 0.18. Linemate quality is built from the mate's
prior MoneyPuck xG, so dropping the individual columns does not take that xG
out of the linemate feature.

| Removed | Bets | 1u risked | ROI | 95% by day | Log loss |
|---|---:|---:|---:|---|---:|
| Nothing (full candidate) | 919 | +84.03u | +9.14% | +2.5% to +15.8% | 0.6968 |
| Individual xG, attempts, high-danger | 1,002 | +65.98u | +6.58% | −0.2% to +13.1% | 0.7010 |
| TOI and PP TOI trends | 1,065 | +93.64u | +8.79% | +2.3% to +15.0% | 0.6960 |
| Linemates and PP deployment | 936 | +55.68u | +5.95% | −0.9% to +13.0% | 0.7033 |
| Opponent shots and xG against | 1,000 | +105.06u | +10.51% | +4.1% to +16.8% | 0.7007 |

Taking out the individual shot rates or the linemates costs units. Taking out
the opponent rates raises units above the full candidate, to +105.06 against
the current model's +104.45, on fewer bets. The day intervals overlap. On all
59,770 unders, log loss stays 0.6822 either way. One cell of a removal is not
a new model.

## Recommendation

Do not replace the live artifact. At the live cut the candidate's return per
bet is a little higher and its probability a little closer to what happened,
and it bets fewer games, so the units are lower (+84.03 against +104.45 at 1u
risked; +72.01 against +89.61 at 1u to win). The day intervals overlap. It is
flat in 2023-24, the season its shift features could not have been learned.
Overs lose. Keep the flag off.

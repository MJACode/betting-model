# nhl_prop_saves with MoneyPuck goalie inputs — walk-forward, 2026-11-26

Mike asked for a backtest, not a new live artifact. The live spec is unchanged
(`models/nhl_props.py`, `USE_MONEYPACK_SAVES = False`). The card does not call
`saves_spec(True)` or `add_moneypuck_goalie_features`. Nothing was registered.
Thresholds, stakes and pauses were not touched.

```
python -m scripts.nhl_prop_backtest --moneypuck --model nhl_prop_saves
```

Same walk-forward as the live artifact: each of 2023-24, 2024-25 and 2025-26
is scored by a model fit only on earlier seasons (`FIRST_TRAIN_SEASON` 2019-20
through the season before). Unders only, best price among the books the card
shops, price floor −200, the model's own probability. The live cut is
`MODEL_OWN_EV_FLOOR["nhl_prop_saves"]` = 0.18.

The extra inputs, all from earlier games only (a row's own xG is not an input;
tests in `tests/test_nhl_props.py`):

- goalie `x_goals`, half-lives 25 and 5 (`mp_xg_l`, `mp_xg_s`)
- goalie `high_dangerx_goals`, half-lives 25 and 5
- goals saved above expected, `x_goals − goals`, half-lives 25 and 5
- opponent `x_goals_for` from `moneypuck_team_games`, half-life 25

All-situation rows. 22,321 of 22,902 regular-season starts had every new
feature. The priced seasons did not lose rows: both fits trained on 8,632 /
11,187 / 13,725 rows and scored 2,555 / 2,538 / 2,537 goalie-starts.

Two stake readings. **1u risked** is what this script has always reported
(a loss is −1). **1u to win, risk capped at 3** is the published record's
stake. ROI on an identical bet list cannot differ between models: the price
and the result are the bet's. What can differ on that list is the probability.

## Live cut, each model's own bets

| | Bets | Hit | 1u risked | ROI | 95% by day | Log loss | Cal. error | Claimed vs hit | 1u to win |
|---|---:|---:|---:|---:|---|---:|---:|---|---:|
| Current features | 783 | 60.5% | +109.62u | +14.00% | +7.1% to +20.6% | 0.6818 | 0.0631 | 0.668 vs 0.605 | +126.33u, +16.13% |
| MoneyPuck features | 953 | 60.1% | +125.26u | +13.14% | +7.0% to +19.0% | 0.6857 | 0.0701 | 0.671 vs 0.601 | +143.48u, +15.06% |

636 bets are in both sets (+99.59u, +15.66% either way). On those, log loss is
0.6794 (current probability) and 0.6786 (MoneyPuck probability). On the 783
current bets, MoneyPuck's probability has log loss 0.6800 and calibration
error 0.0597, against 0.6818 and 0.0631 for the current probability. That is
the whole probability gain, and it is on bets the current model already takes.

## By season, own bets at EV ≥ 0.18 (1u risked)

| Season | Current | MoneyPuck |
|---|---|---|
| 2023-24 | 166 bets, +17.75% (+2.9 to +32.4); early +27.5% / late +8.0% | 198 bets, +11.56% (−2.6 to +25.1); early +19.3% / late +3.9% |
| 2024-25 | 453 bets, +13.03% (+3.2 to +22.5); early +18.0% / late +8.1% | 561 bets, +12.26% (+4.5 to +20.0); early +17.1% / late +7.5% |
| 2025-26 | 164 bets, +12.88% (−1.5 to +26.2); early +15.4% / late +10.3% | 194 bets, +17.31% (+2.1 to +31.4); early +21.8% / late +12.9% |

2025-26 is the only season the new features lead. Its interval overlaps the
current model's.

## Every scored under, not just the bets

One best-price under per goalie-game, no EV cut: 4,795 rows, the same games
for both models. Lines are x.5, so there are no pushes.

| | Log loss | Cal. error | Claimed | Hit | 1u risked | 95% by day |
|---|---:|---:|---:|---:|---|---|
| Current | 0.6942 | 0.0513 | 0.565 | 0.532 | +10.68u, +0.22% | −2.5% to +3.0% |
| MoneyPuck | 0.6947 | 0.0539 | 0.570 | 0.533 | +12.43u, +0.26% | −2.5% to +3.1% |

## The cut as a neighbourhood (own bets, 1u risked)

| EV ≥ | Current bets | Current ROI | MoneyPuck bets | MoneyPuck ROI |
|---:|---:|---:|---:|---:|
| 0.00 | 3,376 | +3.04% | 3,452 | +2.42% |
| 0.03 | 2,908 | +4.61% | 3,007 | +3.88% |
| 0.05 | 2,576 | +4.14% | 2,700 | +5.09% |
| 0.06 | 2,418 | +4.48% | 2,562 | +5.40% |
| 0.08 | 2,106 | +5.88% | 2,252 | +6.26% |
| 0.10 | 1,770 | +7.42% | 1,928 | +6.96% |
| 0.12 | 1,482 | +8.31% | 1,639 | +7.08% |
| 0.15 | 1,072 | +12.41% | 1,254 | +9.67% |
| 0.18 | 783 | +14.00% | 953 | +13.14% |
| 0.20 | 623 | +16.71% | 794 | +12.03% |

At 0.10 the current features are 1,770 bets, +131.30 units, +7.42%, day
interval +2.6% to +12.0%. The registry note on the live artifact (2026-10-01)
says 1,755 bets and +7.8% at the model's own probability. This run is the
script as it is now, including the shared-name filter.

MoneyPuck's ROI is higher at 0.05, 0.06 and 0.08 and lower at every other cut
in the grid, including the live cut. That is not a plateau.

## Recommendation

Do not replace the live artifact. The new features do not beat the current
ones on log loss or calibration over the scored unders, and they do not beat
them on ROI at the live cut. They bet more, so the unit total is higher and
the return per bet is lower. Keep the flag off.

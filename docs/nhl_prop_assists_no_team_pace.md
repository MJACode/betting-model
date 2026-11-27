# NHL assists without team pace — walk-forward, 2026-11-27

The live assists spec is unchanged (`models/nhl_props.py`,
`USE_ASSISTS_NO_TEAM_PACE = False`, and `USE_MONEYPUCK_POINTS` stays false).
`assists_no_team_pace_spec()` is the MoneyPuck assists candidate without team
shot pace and team expected goals for (`own_mp_pace_l`, `own_mp_xgf_l`). It
keeps every other candidate feature, including opponent expected goals
against. It is not in `SPECS` or `LIVE`. The card scores `ASSISTS` and does
not call it. Nothing was registered. Thresholds, stakes and pauses were not
touched.

```
python -m scripts.nhl_prop_backtest --assists-no-team-pace
```

Same walk-forward as the live artifacts and as
`docs/nhl_prop_points_moneypuck.md`: each season is scored by a model fit
only on earlier seasons (`FIRST_TRAIN_SEASON` 2019-20 through the season
before). The seasons scored are 2023-24, 2024-25, 2025-26 and 2026-27 to
date. Unders only, no per-game cap, best expected value among the books the
card shops, price floor −200, the model's own probability. The cut is
`MODEL_OWN_EV_FLOOR["nhl_prop_assists"]` = 0.18. Both specs are Poisson.
Lines are x.5, so these bet lists have no pushes.

The ablation in that earlier doc removed team pace from the full candidate
and printed one row. That removal already refit each fold (`report` calls
`fit`). This run is that spec on its own, with the same-slate comparison,
the four cuts, the season split and the calibration the ablation row did
not carry. The own-bet total matches that row.

Credit MoneyPuck.com. The inputs are the ones named in
`docs/nhl_prop_points_moneypuck.md`, minus team pace and team expected goals
for. A row's own game is still not an input.

Live fit, rows used and rows scored: 159,628 / 46,287 (2023-24), 205,922 /
46,157 (2024-25), 252,165 / 45,997 (2025-26), 298,306 / 12,786 (2026-27).
Mean predicted against actual assists: 0.30 vs 0.29, 0.29 vs 0.28, 0.29 vs
0.29, 0.30 vs 0.30.

No-pace fit: 154,762 / 45,601, 200,370 / 45,324, 245,778 / 45,123, 291,045 /
12,526. Means: 0.30 vs 0.29, 0.28 vs 0.28, 0.29 vs 0.29, 0.30 vs 0.30.
Dropping the two pace columns lets a few more training rows through, because
those columns are no longer required. The scored counts match the full
candidate's scored counts in the earlier doc.

Assists quotes: 346,779, of which 304 were after puck drop and 41 were
incoherent. Books shopped: draftkings, betmgm, williamhill_us, fanatics,
betrivers, hardrockbet.

Priced player-games the live model can score: 65,605. The no-pace model:
64,420. The overlap is 64,420. The no-pace set is the smaller one, so "the
same slate" below is every player-game the candidate can score. The live
model's own list has one bet outside that slate.

Two stake readings. **1u risked** is what this script has always reported
(a loss is −1). **1u to win, risk capped at 3** is the published record's
stake. The day interval resamples whole game days, 5,000 draws, seed 7.
A season under 30 bets has no day interval.

## Head to head at the live cut

EV ≥ 0.18. The same slate is the headline. Own lists are each model on every
player-game it can score.

| | Bets | Hit | 1u risked | ROI | 95% by day | 1u to win | Log loss | Brier | Cal. error | Claimed vs hit |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| Live, own list | 227 | 51.1% | +32.25u | +14.21% | +0.5% to +28.0% | +29.10u, +12.82% (+1.7% to +23.5%) | 0.6796 | 0.2429 | 0.0512 | 0.546 vs 0.511 |
| Live, same slate | 226 | 51.3% | +33.25u | +14.71% | +0.8% to +28.6% | +29.64u, +13.11% (+1.9% to +23.9%) | 0.6799 | 0.2431 | 0.0494 | 0.547 vs 0.513 |
| No-pace, own list and same slate | 267 | 53.2% | +53.59u | +20.07% | +7.0% to +33.7% | +46.68u, +17.48% (+6.9% to +28.1%) | 0.6749 | 0.2409 | 0.0487 | 0.540 vs 0.532 |

181 bets are on both lists (+39.00u, +21.55%, +5.4% to +36.9% either way;
1u to win +32.83u, +18.14%, +5.0% to +30.1%). On those, the live probability
has log loss 0.6783 and calibration error 0.0317. The no-pace probability
has log loss 0.6806 and calibration error 0.0603. The units are the same
because the price is the same.

The 45 live bets the no-pace list does not take are −5.75u. The 86 no-pace
bets the live list does not take are +14.59u. The gap is which unders each
list adds, not a better probability on the shared bets.

No-pace bet prices: median +130, shortest −200, none −300 or shorter. Live
same-slate bets: median +126, shortest −200, none −300 or shorter. The floor
is what keeps −300 and −500 out. Every best-EV under, no cut and no floor,
has median −225, and 27.3% are −300 or shorter (1.7% are −500 or shorter).
Those are not the bets.

### By season, same slate, EV ≥ 0.18 (1u risked)

| Season | Live | No-pace |
|---|---|---|
| 2023-24 | 159 bets, +17.07% (−0.2 to +33.3); early +16.3% / late +17.9% | 178 bets, +17.38% (+0.9 to +32.7); early +17.7% / late +17.1% |
| 2024-25 | 20 bets, +5.43%; early −16.7% / late +27.6% | 29 bets, +12.71%; early +1.3% / late +23.4% |
| 2025-26 | 33 bets, +26.03% (−10.7 to +63.4); early +54.8% / late −1.0% | 48 bets, +37.58% (+5.3 to +70.3); early +40.3% / late +34.8% |
| 2026-27 to date | 14 bets, −25.47%; early −29.9% / late −21.1% | 12 bets, +7.78%; early +23.5% / late −7.9% |

2023-24 is the only large season. Its no-pace interval clears zero. Its two
halves are +17.7% and +17.1%, and each half's own interval includes a loss
(−7.9% to +41.3%, −4.0% to +38.0%). 2025-26 clears zero at 1u risked on 48
bets. At 1u to win that season is +9.44u, +19.67%, and the interval is −5.0%
to +45.0%. 2024-25 and 2026-27 are under 30 bets.

### Early and late, the whole bet list ordered by date

| | Bets | 1u risked | ROI | 95% by day | 1u to win |
|---|---:|---:|---:|---|---:|
| Live, same slate, early | 113 | +22.90u | +20.27% | −0.1% to +39.8% | +22.60u, +20.00% |
| Live, same slate, late | 113 | +10.34u | +9.15% | −10.7% to +28.6% | +7.04u, +6.23% |
| No-pace, early | 133 | +28.91u | +21.74% | +2.0% to +40.4% | +28.13u, +21.15% |
| No-pace, late | 134 | +24.68u | +18.42% | −0.4% to +37.4% | +18.55u, +13.85% |

Both no-pace halves are positive. The early interval clears zero. The late
interval touches it.

## The cut is not one cell

Same slate, 1u risked. 0.18 is the live cut.

| EV ≥ | Live bets | Live units | Live ROI | 95% by day | No-pace bets | No-pace units | No-pace ROI | 95% by day |
|---:|---:|---:|---:|---|---:|---:|---:|---|
| 0.12 | 711 | +72.78u | +10.24% | +2.6% to +17.8% | 846 | +62.41u | +7.38% | +0.2% to +14.4% |
| 0.15 | 401 | +58.96u | +14.70% | +4.6% to +24.5% | 456 | +66.10u | +14.50% | +4.3% to +24.9% |
| 0.18 | 226 | +33.25u | +14.71% | +0.8% to +28.6% | 267 | +53.59u | +20.07% | +7.0% to +33.7% |
| 0.22 | 115 | +18.18u | +15.81% | −6.4% to +38.5% | 119 | +13.29u | +11.17% | −10.6% to +31.6% |

At 1u to win the order is the same. 0.12: live +64.70u (+9.10%) against
no-pace +59.44u (+7.03%). 0.15: live +49.72u (+12.40%) against +62.03u
(+13.60%). 0.18: live +29.64u (+13.11%) against +46.68u (+17.48%). 0.22:
live +16.49u (+14.34%) against +10.30u (+8.66%). At 0.22 both intervals
include a loss, at either stake.

No-pace makes more units at 0.15 and 0.18. Live makes more units at 0.12
and 0.22. The return per bet favours no-pace at 0.18 only. At 0.15 the
returns are close and no-pace is slightly lower at 1u risked, slightly
higher at 1u to win.

## Calibration

On the bets at EV ≥ 0.18, same slate. Brier and log loss are on decisive
rows, which here is every bet.

| | Log loss | Brier | Cal. error | Claimed | Hit |
|---|---:|---:|---:|---:|---:|
| Live | 0.6799 | 0.2431 | 0.0494 | 0.547 | 0.513 |
| No-pace | 0.6749 | 0.2409 | 0.0487 | 0.540 | 0.532 |

Reliability of those bets. Several buckets are small.

| Bucket | Live n | Live claimed | Live hit | No-pace n | No-pace claimed | No-pace hit |
|---|---:|---:|---:|---:|---:|---:|
| 0.30–0.40 | 2 | 0.372 | 0.000 | 4 | 0.381 | 0.500 |
| 0.40–0.50 | 61 | 0.460 | 0.377 | 82 | 0.457 | 0.463 |
| 0.50–0.55 | 58 | 0.527 | 0.483 | 66 | 0.526 | 0.424 |
| 0.55–0.60 | 60 | 0.574 | 0.600 | 63 | 0.572 | 0.587 |
| 0.60–0.65 | 25 | 0.620 | 0.640 | 28 | 0.622 | 0.750 |
| 0.65–0.70 | 10 | 0.672 | 0.800 | 15 | 0.674 | 0.733 |
| 0.70–0.80 | 8 | 0.743 | 0.500 | 7 | 0.743 | 0.571 |
| 0.80–1.00 | 2 | 0.817 | 0.500 | 2 | 0.806 | 0.500 |

The no-pace 0.50–0.55 bucket is the weak one: claimed 0.526, hit 0.424, on
66 bets.

Every best-EV under, no cut and no floor, same 64,409 player-games. This is
the scored universe, not the bet list.

| | Rows | Log loss | Brier | Cal. error | Claimed | Hit | 1u risked |
|---|---:|---:|---:|---:|---:|---:|---|
| Live | 64,409 | 0.6239 | 0.2167 | 0.0033 | 0.657 | 0.657 | −2,172.78u, −3.37% |
| No-pace | 64,409 | 0.6236 | 0.2165 | 0.0034 | 0.657 | 0.657 | −2,175.71u, −3.38% |

From 0.30 up, both models' buckets on that full under list sit within about
two points of the hit rate, and most sit within one. The lists above are
where the two models differ. The probability on a random under is not.

## Overs

The rule scored here bets unders only. At EV ≥ 0.18, no cap, same slate:
live overs 345 bets, +10.00u, +2.90% (−14.2% to +21.2%); no-pace overs 369
bets, −27.51u, −7.45% (−25.0% to +9.5%). The over is not a side to add.

## Recommendation

At the live cut, on the same slate, the no-pace list beats the live list.
+53.59u against +33.25u at 1u risked, +46.68u against +29.64u at 1u to win,
on 267 bets against 226, and its day interval clears zero at both stakes.
The live interval clears zero too. Log loss and Brier on the no-pace bets
are slightly better. The number matches the ablation cell, so this is that
cell walked under its own name, not a new sample.

It does not beat the live list at every neighbouring cut. At 0.12 the live
list makes more units. At 0.22 the live list makes more units and both
intervals include a loss. 2024-25 and 2026-27 are too small for an interval.
The late half of the no-pace list touches zero.

Do not replace the live artifact. Leave `USE_ASSISTS_NO_TEAM_PACE` false.
The result is the candidate to look at if the live assists feature list is
reopened. It is not a switch to make from this run.

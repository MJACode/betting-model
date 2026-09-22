# NHL market lab — every market, in units, at real opening prices

> First run 2026-09-20. Script: `python -m scripts.nhl_market_lab`. Prices:
> the free Sportsbook Reviews Online archive, loaded by
> `data/ingestors/nhl_sbr_archive.py` into `odds` (`source = 'sbr_archive_nhl'`,
> 25,659 rows, 5,135 games 2018-19 -> 2022-11-27; scores agree with `games` on
> 5,132 of 5,135 and overtime on all 5,135). The book behind the consensus is
> not named by the site.

## The market grid

| Market | Target | Inputs held | Price source | Status |
|---|---|---|---|---|
| Moneyline | `home_win` | as-of team + goalie (`data/nhl_asof.py`) | archive open + close | **backtested below** |
| Total | goals vs the opening number | same | archive open + close, with prices | **backtested below** (first time this model has ever had a line) |
| Puck line +/-1.5 | margin vs the HOME line | same | archive, ONE price, not labelled open or close | **backtested below**, no closing-line value possible |
| Regulation 3-way | `home_win_reg` / `went_to_ot`; archive period scores agree 5,135 / 5,135 | same | none stored; the feed sells it from 2023-05-03 | parked: no price. Target ready |
| 1st-period moneyline / total | `nhl_period_scores` (stored 2026-09-21: 5,134 games, 2018-19 -> 2022-11-27, from the archive) | same | none; feed from 2023-05-03 | parked: no price. Target ready |
| Team totals, alternates, periods 2-3 | derivable from scores | same | none until the 2026-10-01 purchase (game lines only) | parked: no price, and the purchase does not cover them |
| Shots on goal, points, goals, assists, blocks, hits | `nhl_skater_game_log`, 378,446 rows | per-game logs, ice time by strength | none before 2023-05-03; not in the 10-01 purchase | parked: no price. NEXT: model the distributions, score vs naive baselines |
| Goalie saves | `nhl_goalie_game_log`, 25,326 rows | same | same | parked: no price |

## Sample

2,694 priced games in the three test seasons (2020-21, 2021-22, Oct-Nov 2022).
At that size a 95% interval on ROI is about +/-4 points, so nothing under ~4%
can be told from zero here. The 2026-10-01 purchase extends prices to 2025-26.

## Results (every bet decided and graded at the OPEN; walk-forward by season)

```
priced games: 5,135; in the test seasons [2021, 2022, 2023]: 2,695

moneyline, 2,694 games — accuracy scores (diagnostics): market OPEN log loss 0.6558 AUC 0.6583; market CLOSE log loss 0.6508 AUC 0.6647; home-win rate 0.537 -> log loss 0.6904

### Blind betting on the test seasons (the floor any model must beat)

                      strategy  bets  units   roi          ci  clv_pts  beat_close
      always home (open price)  2694 -101.5 -3.77  -7.4..-0.2     0.15        52.7
      always away (open price)  2694 -142.6 -5.29  -9.4..-1.2    -0.15        46.8
 always favourite (open price)  2694   -0.9 -0.03  -3.0..+3.0     0.34        57.5
  always underdog (open price)  2694 -243.2 -9.03 -13.6..-4.4    -0.34        41.9
 always over (open line+price)  2683  -32.5 -1.21  -4.8..+2.3    -0.16        29.4
always under (open line+price)  2683 -191.4 -7.14 -10.7..-3.6     0.16        31.1
     puck line: favourite -1.5  2693  -32.5 -1.21  -6.0..+3.5      NaN         NaN
      puck line: underdog +1.5  2693  -96.7 -3.59  -6.6..-0.6      NaN         NaN
moneyline: repo features (22): n=2,558 model log loss 0.7024 AUC 0.5775 | market open on the same games 0.6562 / 0.6588
  minus goalie group: n=2,558 model log loss 0.7044 AUC 0.5792 | market open on the same games 0.6562 / 0.6588
  minus shot-share / PP / PK group: n=2,558 model log loss 0.7089 AUC 0.5615 | market open on the same games 0.6562 / 0.6588
moneyline: repo features + the market's own open probability: n=2,558 log loss 0.6949 vs market open 0.6562

### Moneyline — bet at the OPEN when model minus no-vig open >= edge

                                 model  edge>=  bets  units   roi          ci  clv_pts  beat_close  early_roi  late_roi
         moneyline: repo features (22)    0.02  2269 -115.8 -5.10  -9.6..-0.7     0.36        52.7       -9.6      -0.6
         moneyline: repo features (22)    0.04  1998 -119.7 -5.99 -10.7..-1.2     0.35        52.8       -9.5      -2.5
         moneyline: repo features (22)    0.06  1738  -65.6 -3.77  -8.9..+1.4     0.37        52.8       -8.2       0.6
         moneyline: repo features (22)    0.08  1472  -50.5 -3.43  -9.1..+2.2     0.46        54.4       -7.7       0.8
         moneyline: repo features (22)    0.10  1238  -58.9 -4.75 -11.0..+1.5     0.48        54.4       -9.1      -0.4
                    minus goalie group    0.02  2290 -112.9 -4.93  -9.4..-0.5     0.28        51.7       -6.0      -3.9
                    minus goalie group    0.04  1992  -97.0 -4.87  -9.7..-0.1     0.30        51.8       -7.3      -2.5
                    minus goalie group    0.06  1730  -73.3 -4.24  -9.4..+0.9     0.33        52.4       -6.9      -1.5
                    minus goalie group    0.08  1486  -41.7 -2.80  -8.5..+2.9     0.31        51.1       -5.9       0.3
                    minus goalie group    0.10  1239  -60.2 -4.86 -11.1..+1.4     0.30        51.2       -8.2      -1.5
      minus shot-share / PP / PK group    0.02  2258 -129.1 -5.72 -10.3..-1.2     0.30        52.3       -8.5      -2.9
      minus shot-share / PP / PK group    0.04  1976 -135.6 -6.86 -11.8..-2.0     0.30        52.1       -7.8      -5.9
      minus shot-share / PP / PK group    0.06  1692 -108.3 -6.40 -11.8..-1.0     0.37        52.7       -7.5      -5.3
      minus shot-share / PP / PK group    0.08  1436  -74.7 -5.20 -11.1..+0.7     0.47        53.6       -6.1      -4.3
      minus shot-share / PP / PK group    0.10  1191  -87.9 -7.38 -14.0..-0.8     0.54        53.7       -8.6      -6.2
moneyline: features + market open prob    0.02  2260 -108.6 -4.81  -9.2..-0.4     0.24        51.9       -8.7      -0.9
moneyline: features + market open prob    0.04  1927 -105.3 -5.47 -10.2..-0.7     0.29        52.4       -9.5      -1.5
moneyline: features + market open prob    0.06  1655  -73.7 -4.45  -9.6..+0.7     0.33        53.2       -9.8       0.9
moneyline: features + market open prob    0.08  1370  -61.9 -4.52 -10.2..+1.2     0.41        54.3       -9.3       0.3
moneyline: features + market open prob    0.10  1143  -55.6 -4.87 -11.2..+1.5     0.50        55.9       -9.2      -0.6
totals: n=2,527 model log loss 0.7239 AUC 0.5078 | market open 0.6928 / 0.5260

### Totals — bet the OPENING number and price when model minus no-vig open >= edge

                     model  edge>=  bets  units   roi         ci  clv_pts  beat_close  line_moved_our_way  early_roi  late_roi
totals: repo features (16)    0.02  2197  -56.1 -2.55 -6.6..+1.5     0.22        32.7                10.5        3.5      -8.6
totals: repo features (16)    0.04  1871  -41.9 -2.24 -6.6..+2.2     0.25        33.1                10.6        2.3      -6.8
totals: repo features (16)    0.06  1583  -33.2 -2.10 -6.9..+2.7     0.24        33.1                10.5        2.3      -6.5
totals: repo features (16)    0.08  1314  -51.3 -3.91 -9.2..+1.4     0.28        33.9                 9.7        0.3      -8.1
totals: repo features (16)    0.10  1081  -43.1 -3.99 -9.8..+1.9     0.23        32.9                 9.7       -0.0      -7.9
puck line: n=2,556 model log loss 0.7000 AUC 0.6074 | market 0.6631 / 0.6396

### Puck line +/-1.5 — one archived price, so no closing-line value

                              model  edge>=  bets  units   roi         ci  early_roi  late_roi
puck line: repo features + the line    0.02  2228   31.4  1.41 -2.9..+5.7        0.6       2.2
puck line: repo features + the line    0.04  1964   23.6  1.20 -3.4..+5.8        0.8       1.6
puck line: repo features + the line    0.06  1690   24.0  1.42 -3.6..+6.4        3.3      -0.4
puck line: repo features + the line    0.08  1405   -0.9 -0.06 -5.5..+5.4        2.2      -2.3
puck line: repo features + the line    0.10  1176   -2.0 -0.17 -6.2..+5.8        0.9      -1.3
```

`clv_pts` = mean move, in probability points, of the no-vig price toward the
side taken between open and close. `beat_close` = share of bets where it moved
our way. Accuracy scores (log loss, AUC) are diagnostics only.

## Read

- **No cut clears on moneyline or totals.** Every moneyline row loses 3-7%
  and every totals row 2-4%; the model's log loss (0.702) is worse than the
  market's open (0.656) AND worse than quoting the home-win rate (0.690), so
  its "edges" are its own error. Adding the market's probability as an input
  does not rescue it (0.695).
- **The one thing the inputs do carry**: removing shot share / power play /
  penalty kill makes every row worse (AUC 0.578 -> 0.562, ROI down 1-3 points
  at every cut); removing the goalie group changes nothing. Shot-based team
  strength is signal; the goalie numbers, as built, are not.
- **Puck line is the only non-negative grid** (+1.2 to +1.4% on ~2,000 bets at
  the loose cuts) — but the interval spans zero, it FADES to zero as the edge
  cut tightens (a real edge grows), and it has no closing-line check. Not an
  edge; the first thing to re-test when priced seasons arrive.
- **The openers lean the wrong way on favourites**: blind favourites at the
  open break even (-0.03% on 2,694) and beat the close 57.5% of the time;
  blind underdogs lose 9.0%. The favourite-longshot bias the literature
  reports is visible in this archive. It is not a bet on its own (it does not
  clear the vig), but any NHL moneyline rule should be tilted toward it.
- **Blind unders lost 7.1%** over these seasons against -1.2% for overs —
  the opposite of the "NHL unders" folklore.

---

# Round two (2026-09-20): inputs rebuilt from the per-game logs, regularised models

Scripts: `scripts/nhl_market_lab2.py`, `scripts/nhl_market_lab2_checks.py`,
`scripts/nhl_prop_lab.py`. Round one's ablation said the signal was in shot
share and special teams and that the untuned trees were badly over-confident,
so this round builds every input from `nhl_team_game_log` /
`nhl_goalie_game_log` as exponentially weighted as-of rates (the carry-over
across the summer is the prior-season blend), groups them (form, shots, special
teams, goalie, schedule, a running goal-margin rating), and fits a regularised
logistic model and heavily regularised trees. Walk-forward, test seasons 2020,
2021, 2022, 2023 (3,771 priced games); bets decided and graded at the OPEN.

```
games 2019-2023 with inputs: 6,193; with an opening moneyline: 5,134
ALL inputs, logistic: n=3,771 model log loss 0.6628 AUC 0.6361 | market open 0.6634 / 0.6392
ALL inputs, regularised trees: n=3,771 model log loss 0.6722 AUC 0.6155 | market open 0.6634 / 0.6392
  minus form: n=3,771 model log loss 0.6625 AUC 0.6367 | market open 0.6634 / 0.6392
  minus shots: n=3,771 model log loss 0.6653 AUC 0.6297 | market open 0.6634 / 0.6392
  minus special: n=3,771 model log loss 0.6628 AUC 0.6359 | market open 0.6634 / 0.6392
  minus goalie: n=3,771 model log loss 0.6633 AUC 0.6336 | market open 0.6634 / 0.6392
  minus schedule: n=3,771 model log loss 0.6632 AUC 0.6347 | market open 0.6634 / 0.6392
  minus rating: n=3,771 model log loss 0.6630 AUC 0.6346 | market open 0.6634 / 0.6392
market open + ALL inputs, logistic: n=3,771 model log loss 0.6629 AUC 0.6358 | market open 0.6634 / 0.6392
market open ALONE, logistic (the bar): n=3,776 model log loss 0.6641 AUC 0.6395 | market open 0.6633 / 0.6393

### Moneyline, round two — bet at the OPEN when |model - no-vig open| >= edge

                                model  edge>=  bets  units   roi           ci  clv_pts  beat_close  early  late
                 ALL inputs, logistic    0.02  2961  105.6  3.57   -0.3..+7.5     0.71        57.9    6.5   0.6
                 ALL inputs, logistic    0.04  2185  108.1  4.95   +0.3..+9.6     0.89        59.9    6.0   3.9
                 ALL inputs, logistic    0.06  1561  124.4  7.97  +2.3..+13.6     1.08        61.9    9.4   6.6
                 ALL inputs, logistic    0.08  1021  115.6 11.32  +4.0..+18.6     1.38        64.3   13.5   9.2
                 ALL inputs, logistic    0.10   635   83.7 13.18  +3.3..+23.1     1.74        66.6   15.7  10.7
        ALL inputs, regularised trees    0.02  3073   -4.9 -0.16   -3.9..+3.6     0.59        56.3    0.2  -0.5
        ALL inputs, regularised trees    0.04  2427   31.2  1.29   -3.0..+5.6     0.68        57.2    1.1   1.5
        ALL inputs, regularised trees    0.06  1812   13.6  0.75   -4.3..+5.8     0.78        58.1    1.7  -0.2
        ALL inputs, regularised trees    0.08  1333   35.8  2.68   -3.4..+8.8     0.90        58.9    3.2   2.2
        ALL inputs, regularised trees    0.10   943   31.3  3.32  -4.3..+10.9     0.98        58.9    1.7   5.0
                           minus form    0.02  2925  132.2  4.52   +0.6..+8.5     0.80        58.9    6.3   2.7
                           minus form    0.04  2161  112.6  5.21   +0.5..+9.9     0.98        60.8    7.0   3.4
                           minus form    0.06  1501   99.7  6.64  +0.8..+12.5     1.16        63.0    8.3   5.0
                           minus form    0.08   958  103.2 10.77  +3.2..+18.4     1.42        64.2   11.6   9.9
                           minus form    0.10   606   80.4 13.27  +3.0..+23.6     1.92        68.8   12.7  13.8
                          minus shots    0.02  2869   26.6  0.93   -3.2..+5.0     0.55        54.2    3.4  -1.5
                          minus shots    0.04  2048   79.0  3.86   -1.1..+8.8     0.70        55.3    6.8   0.9
                          minus shots    0.06  1402   71.2  5.08  -1.1..+11.3     0.85        56.1    9.8   0.4
                          minus shots    0.08   901  108.7 12.07  +3.9..+20.2     1.01        56.8   13.3  10.9
                          minus shots    0.10   548   97.3 17.75  +6.4..+29.1     1.42        59.3   23.9  11.6
                        minus special    0.02  2796   57.8  2.07   -2.0..+6.1     0.91        60.6    4.3  -0.2
                        minus special    0.04  1990   82.4  4.14   -0.8..+9.1     1.19        63.1    6.7   1.6
                        minus special    0.06  1296  129.4  9.98  +3.5..+16.5     1.42        65.0   11.8   8.2
                        minus special    0.08   779   89.7 11.51  +2.5..+20.5     1.80        68.7   12.6  10.4
                        minus special    0.10   411   87.4 21.26  +7.5..+35.0     2.39        70.6   26.8  15.7
                         minus goalie    0.02  2936   64.4  2.19   -1.7..+6.1     0.61        56.5    4.0   0.4
                         minus goalie    0.04  2097  105.2  5.02   +0.3..+9.7     0.76        58.1    6.2   3.9
                         minus goalie    0.06  1396  120.7  8.65  +2.6..+14.7     0.97        59.5    9.0   8.3
                         minus goalie    0.08   877  100.8 11.50  +3.5..+19.5     1.33        63.1    9.2  13.8
                         minus goalie    0.10   499   79.6 15.95  +4.4..+27.5     1.76        64.9   18.2  13.7
                       minus schedule    0.02  2912   98.4  3.38   -0.6..+7.3     0.62        56.2    5.6   1.2
                       minus schedule    0.04  2105  101.8  4.83   +0.1..+9.6     0.76        58.1    6.0   3.7
                       minus schedule    0.06  1449   85.7  5.92  -0.0..+11.9     0.93        60.2    7.5   4.4
                       minus schedule    0.08   902   85.9  9.52  +1.6..+17.4     1.31        63.9   11.2   7.9
                       minus schedule    0.10   532   64.3 12.08  +0.9..+23.3     1.61        65.4   16.2   8.0
                         minus rating    0.02  2930   92.0  3.14   -0.9..+7.1     0.71        57.5    5.8   0.5
                         minus rating    0.04  2192  113.6  5.18   +0.4..+9.9     0.91        59.5    5.5   4.9
                         minus rating    0.06  1541  101.6  6.59  +0.7..+12.5     1.09        61.8    6.3   6.9
                         minus rating    0.08  1014  117.9 11.63  +4.0..+19.2     1.32        63.5   10.4  12.8
                         minus rating    0.10   628   73.6 11.73  +1.5..+22.0     1.67        65.9   13.2  10.2
   market open + ALL inputs, logistic    0.02  2930   89.4  3.05   -0.9..+7.0     0.63        57.2    5.2   0.9
   market open + ALL inputs, logistic    0.04  2120  119.9  5.65  +0.9..+10.4     0.83        59.1    6.6   4.7
   market open + ALL inputs, logistic    0.06  1467  117.1  7.98  +2.1..+13.8     1.02        61.0    8.4   7.6
   market open + ALL inputs, logistic    0.08   943   88.5  9.39  +1.8..+17.0     1.34        63.8    8.4  10.4
   market open + ALL inputs, logistic    0.10   558   79.1 14.18  +3.3..+25.0     1.69        65.4   16.4  11.9
market open ALONE, logistic (the bar)    0.02   742  -15.0 -2.03  -12.2..+8.2    -0.06        47.7    1.0  -5.1
market open ALONE, logistic (the bar)    0.04    36    4.0 11.14 -65.4..+87.7     1.25        33.3   16.1   6.2
market open ALONE, logistic (the bar)    0.06     0    NaN   NaN          NaN      NaN         NaN    NaN   NaN
market open ALONE, logistic (the bar)    0.08     0    NaN   NaN          NaN      NaN         NaN    NaN   NaN
market open ALONE, logistic (the bar)    0.10     0    NaN   NaN          NaN      NaN         NaN    NaN   NaN

### Blind favourite at the OPEN, by price band, all priced seasons

favourite's no-vig open  bets  units   roi          ci  clv_pts  beat_close  roi_2019  roi_2020  roi_2021  roi_2022  roi_2023
              0.50-0.55  1644 -104.7 -6.37 -10.8..-1.9     0.22        54.1      -6.8      -7.6      -2.3      -3.9     -21.7
              0.55-0.60  1483    8.8  0.59  -3.6..+4.8     0.24        55.5      -0.8      -8.3       5.8       7.8      -6.2
              0.60-0.65  1062  -18.1 -1.71  -6.2..+2.8     0.20        53.5      -7.4      -4.1      -6.1       6.2      12.1
              0.65-0.70   582  -21.4 -3.67  -9.2..+1.8     0.43        59.5     -12.6      -7.9       8.4       1.2      -9.9
              0.70-1.00   363  -15.6 -4.30 -10.4..+1.8    -0.52        61.4       2.5      -4.4      -5.8      -3.3     -19.3
totals: log inputs + line + market, logistic: n=3,568 model log loss 0.6957 AUC 0.5221 | market open 0.6928 / 0.5227
totals: same, regularised trees: n=3,568 model log loss 0.7036 AUC 0.5087 | market open 0.6928 / 0.5227
totals: inputs WITHOUT the market's price: n=3,568 model log loss 0.6948 AUC 0.5244 | market open 0.6928 / 0.5227

### Totals, round two

                                       model  edge>=  bets  units   roi          ci  clv_pts  beat_close  early  late
totals: log inputs + line + market, logistic    0.02  2525  -32.1 -1.27  -5.1..+2.5     0.76        41.0   -0.3  -2.2
totals: log inputs + line + market, logistic    0.04  1559  -22.6 -1.45  -6.3..+3.4     1.03        44.3    2.3  -5.2
totals: log inputs + line + market, logistic    0.06   843  -25.3 -3.00  -9.7..+3.7     1.44        49.6   -1.4  -4.6
totals: log inputs + line + market, logistic    0.08   418   -4.2 -1.00 -10.8..+8.8     1.71        51.9    4.8  -6.8
totals: log inputs + line + market, logistic    0.10   198   16.9  8.55 -6.3..+23.4     1.99        50.0    4.8  12.3
             totals: same, regularised trees    0.02  2850 -104.3 -3.66  -7.2..-0.1     0.32        36.0   -1.2  -6.1
             totals: same, regularised trees    0.04  2208  -97.6 -4.42  -8.5..-0.4     0.40        37.5   -1.4  -7.5
             totals: same, regularised trees    0.06  1599  -69.0 -4.32  -9.1..+0.4     0.43        38.2   -1.8  -6.8
             totals: same, regularised trees    0.08  1057  -17.5 -1.65  -7.6..+4.2     0.46        38.8   -2.3  -1.0
             totals: same, regularised trees    0.10   684  -19.4 -2.83 -10.3..+4.6     0.59        39.3   -5.0  -0.7
   totals: inputs WITHOUT the market's price    0.02  2512  -43.6 -1.74  -5.5..+2.1     0.80        41.8   -0.8  -2.7
   totals: inputs WITHOUT the market's price    0.04  1531  -31.9 -2.08  -7.0..+2.8     1.12        45.9    1.0  -5.2
   totals: inputs WITHOUT the market's price    0.06   793  -17.1 -2.15  -9.0..+4.7     1.53        52.3   -1.6  -2.7
   totals: inputs WITHOUT the market's price    0.08   360    4.2  1.17 -9.3..+11.6     1.92        57.5    3.9  -1.6
   totals: inputs WITHOUT the market's price    0.10   139   23.2 16.66 -1.1..+34.4     2.52        57.6   10.8  22.4
puck line: ALL inputs + the line, logistic: n=3,770 model log loss 0.6610 AUC 0.6441 | market open 0.6566 / 0.6502
puck line: market price + ALL inputs: n=3,770 model log loss 0.6606 AUC 0.6452 | market open 0.6566 / 0.6502
puck line: same, regularised trees: n=3,770 model log loss 0.6674 AUC 0.6368 | market open 0.6566 / 0.6502

### Puck line, round two (one archived price: no closing-line value)

                                     model  edge>=  bets  units   roi          ci  early  late
puck line: ALL inputs + the line, logistic    0.02  2917   11.9  0.41  -3.4..+4.2    3.9  -3.1
puck line: ALL inputs + the line, logistic    0.04  2115   47.6  2.25  -2.2..+6.7    6.2  -1.7
puck line: ALL inputs + the line, logistic    0.06  1410   74.5  5.29 -0.3..+10.9    7.7   2.9
puck line: ALL inputs + the line, logistic    0.08   906   60.4  6.67 -0.3..+13.6    6.4   6.9
puck line: ALL inputs + the line, logistic    0.10   516   26.8  5.19 -4.2..+14.6    6.5   3.9
      puck line: market price + ALL inputs    0.02  2818   37.7  1.34  -2.4..+5.1    4.1  -1.5
      puck line: market price + ALL inputs    0.04  1931    2.9  0.15  -4.3..+4.6    1.8  -1.5
      puck line: market price + ALL inputs    0.06  1209   40.6  3.36  -2.4..+9.1    3.9   2.8
      puck line: market price + ALL inputs    0.08   708   15.5  2.18  -5.4..+9.7    2.7   1.6
      puck line: market price + ALL inputs    0.10   375    2.1  0.57 -9.6..+10.8   -6.3   7.4
        puck line: same, regularised trees    0.02  2999  -60.4 -2.02  -5.7..+1.7   -0.1  -4.0
        puck line: same, regularised trees    0.04  2330  -20.1 -0.86  -5.1..+3.4    0.5  -2.2
        puck line: same, regularised trees    0.06  1758  -20.0 -1.14  -6.0..+3.7    0.6  -2.8
        puck line: same, regularised trees    0.08  1260    2.7  0.21  -5.5..+5.9   -0.9   1.3
        puck line: same, regularised trees    0.10   809    0.7  0.08  -7.1..+7.3    0.0   0.1
```

## Is the moneyline result real? The checks

```
                                          check  edge>=  bets  units   roi           ci  clv_pts  beat_close
  0. as reported: decide at open, grade at OPEN    0.04  2185  108.1  4.95   +0.3..+9.6     0.89        59.9
        1. same bets, graded at the CLOSE price    0.04  2185   75.3  3.45   -0.9..+7.8     0.89        59.9
     2. decide vs the CLOSE, grade at the CLOSE    0.04  2174   94.4  4.34   -0.2..+8.9    -0.61        42.4
  0. as reported: decide at open, grade at OPEN    0.06  1561  124.4  7.97  +2.3..+13.6     1.08        61.9
        1. same bets, graded at the CLOSE price    0.06  1561   86.1  5.51  +0.3..+10.7     1.08        61.9
     2. decide vs the CLOSE, grade at the CLOSE    0.06  1559   83.8  5.38  -0.1..+10.8    -0.76        40.5
  0. as reported: decide at open, grade at OPEN    0.08  1021  115.6 11.32  +4.0..+18.6     1.38        64.3
        1. same bets, graded at the CLOSE price    0.08  1021   72.6  7.11  +0.7..+13.5     1.38        64.3
     2. decide vs the CLOSE, grade at the CLOSE    0.08   996   58.8  5.91  -1.0..+12.8    -0.97        38.4
3a. no goalie inputs, no team on a back-to-back    0.04  1536   32.3  2.10   -3.3..+7.5     0.45        54.6
                 3b. ...and graded at the CLOSE    0.04  1536   31.9  2.08   -3.2..+7.3     0.45        54.6
3a. no goalie inputs, no team on a back-to-back    0.06   992   57.7  5.82  -1.1..+12.8     0.60        55.6
                 3b. ...and graded at the CLOSE    0.06   992   48.8  4.92  -1.6..+11.5     0.60        55.6
3a. no goalie inputs, no team on a back-to-back    0.08   623   41.7  6.69  -2.5..+15.9     0.89        59.2
                 3b. ...and graded at the CLOSE    0.08   623   25.4  4.07  -4.2..+12.4     0.89        59.2
                       4. bets on the FAVOURITE    0.04   998   39.0  3.90   -1.1..+8.9     1.16        65.6
                        4. bets on the UNDERDOG    0.04  1187   69.1  5.83  -1.6..+13.3     0.67        55.1
                       4. bets on the FAVOURITE    0.06   686   39.7  5.79  -0.2..+11.8     1.33        67.9
                        4. bets on the UNDERDOG    0.06   875   84.7  9.68  +0.7..+18.7     0.89        57.1
                       4. bets on the FAVOURITE    0.08   449   30.9  6.87  -0.5..+14.3     1.54        69.7
                        4. bets on the UNDERDOG    0.08   572   84.7 14.81  +3.1..+26.5     1.26        60.0
                                 5. season 2020    0.06   521   68.3 13.12  +2.9..+23.3     0.57        58.7
                                 5. season 2021    0.06   384   -2.1 -0.55 -11.9..+10.8     0.73        57.0
                                 5. season 2022    0.06   514   71.2 13.86  +3.8..+23.9     1.69        66.7
                                 5. season 2023    0.06   142  -13.1 -9.20  -23.8..+5.4     1.71        69.0

6. shuffled model probabilities, edge >= 0.06, 50 draws: mean ROI -5.07%, 95% of draws within -8.6..-2.0% (the real model: see row 0)
games with a team on a back-to-back: 24.8% of 3,771
```

## Read, round two

- **Moneyline: the first positive grid in this repo's NHL work, and not yet
  proven.** The regularised logistic model on log-built inputs is +5.0% /
  +8.0% / +11.3% at edge cuts 0.04 / 0.06 / 0.08 (1,021-2,185 bets, intervals
  clear of zero), ROI RISES with the cut, both halves are positive, and it
  beats the close 60-64% of the time. It survives grading at the CLOSING price
  (+5.5% at 0.06) and a shuffled-probability test (shuffles average -5.1%,
  95% within -8.6..-2.0). **Against it:** two of four seasons carry it
  (2020 +13.1%, 2022 +13.9%; 2021 -0.6%, 2023 -9.2% on 142 bets); restricted
  to what the opener could know (no goalie inputs, no team on a back-to-back —
  24.8% of games) it is +5.8% on 992 bets with an interval of -1.1..+12.8; and
  the model's own accuracy only MATCHES the market's open (log loss 0.6628 vs
  0.6634), it does not beat the close (0.651 in round one's sample). The
  heavily regularised trees on the same inputs make +1%.
  **Verdict: a candidate, frozen as specified here, to be tested on seasons it
  has never seen (2023-24 -> 2025-26) when those prices arrive on 2026-10-01.
  Not a model to bet on this evidence.**
- **Every input group is small on its own.** Removing shots costs the most
  accuracy (AUC 0.636 -> 0.630); no single group's removal kills the ROI, which
  says the edge — if it is one — is in the regularised combination and in
  being less over-confident than round one, not in any one feature.
- **Favourite lean, market only, five seasons:** not a rule. Only the 0.55-0.60
  band is non-negative (+0.6% on 1,483, interval -3.6..+4.8) and no band is
  positive in every season.
- **Totals: nothing.** Model and market are both near coin-flip on the over
  (AUC 0.52); every row with a usable sample loses 1-4%.
- **Puck line:** logistic +5.3% at 0.06 (1,410 bets, interval -0.3..+10.9),
  +6.7% at 0.08; trees lose. Same caveats as moneyline, plus one archived price
  and no closing-line check. Second candidate for the 10-01 re-test.

# Player props: do log-built models beat the projections a book gets for free?

No NHL prop price is stored (the feed sells them from 2023-05-03), so this is
NOT a profit test. It answers the prior question: on seasons never seen
(2024-25, 2025-26; 92,384 skater-games, 4,081 full goalie starts), does a
Poisson model on usage + matchup beat (a) the player's season-to-date average
and (b) his last ten games? Columns `model` / `season avg` / `last 10` are log
loss on P(over the line), lower is better; the `p>=.60` columns are calibration
in the band that would actually be bet.

```
skater-games with 10+ prior games: 335,920 (92,384 in the holdout seasons)
       market  line  test     n  over_rate  model  season avg  last 10  n p>=.60  hit p>=.60  avg p>=.60  n p<=.40  under hit p<=.40  beats both  gain vs best naive
        shots   1.5  2025 42561      0.439 0.6128      0.6272   0.6444     10072       0.704       0.714     20468             0.723        True              0.0144
        shots   2.5  2025 42561      0.226 0.4660      0.4762   0.4925      1148       0.627       0.678     35810             0.828        True              0.0102
        shots   3.5  2025 42561      0.106 0.2899      0.2964   0.3073        91       0.495       0.637     41667             0.901        True              0.0065
        shots   1.5  2026 42433      0.431 0.6079      0.6215   0.6394      9074       0.709       0.703     21279             0.725        True              0.0136
        shots   2.5  2026 42433      0.222 0.4588      0.4690   0.4847       793       0.663       0.654     36820             0.825        True              0.0102
        shots   3.5  2026 42433      0.104 0.2832      0.2892   0.3009        21       0.619       0.619     41897             0.901        True              0.0060
       points   0.5  2025 42561      0.347 0.5915      0.6195   0.6710      2777       0.680       0.661     27978             0.748        True              0.0280
       points   0.5  2026 42433      0.353 0.5943      0.6217   0.6692      2936       0.669       0.658     27942             0.744        True              0.0274
      assists   0.5  2025 42561      0.239 0.5157      0.5522   0.6226       238       0.643       0.640     38015             0.788        True              0.0365
      assists   0.5  2026 42433      0.245 0.5211      0.5571   0.6242       196       0.607       0.636     37917             0.783        True              0.0360
        goals   0.5  2025 42561      0.152 0.3909      0.4286   0.4996         0         NaN         NaN     42263             0.850        True              0.0377
        goals   0.5  2026 42433      0.155 0.3965      0.4336   0.5009         0         NaN         NaN     42235             0.847        True              0.0371
blocked_shots   1.5  2025 42561      0.213 0.4425      0.4541   0.4710      1141       0.648       0.649     35298             0.848        True              0.0116
blocked_shots   1.5  2026 42433      0.193 0.4156      0.4290   0.4469       561       0.611       0.637     36202             0.859        True              0.0134
         hits   1.5  2025 42561      0.309 0.5059      0.5140   0.5314      6706       0.683       0.718     27348             0.829        True              0.0081
         hits   2.5  2025 42561      0.155 0.3400      0.3459   0.3594      1151       0.672       0.682     38236             0.886        True              0.0059
         hits   1.5  2026 42433      0.290 0.4790      0.4901   0.5048      5647       0.708       0.732     29591             0.832        True              0.0111
         hits   2.5  2026 42433      0.142 0.3107      0.3180   0.3264      1178       0.711       0.691     38386             0.900        True              0.0073
        saves  24.5  2025  2041      0.521 0.6906      0.7165   0.7260       598       0.642       0.697       584             0.582        True              0.0259
        saves  27.5  2025  2041      0.344 0.6555      0.6728   0.6874        66       0.409       0.656      1560             0.692        True              0.0173
        saves  29.5  2025  2041      0.239 0.5633      0.5704   0.5854         6       0.333       0.621      1910             0.771        True              0.0071
        saves  24.5  2026  2040      0.492 0.6653      0.7068   0.7284       282       0.702       0.674       842             0.620        True              0.0415
        saves  27.5  2026  2040      0.319 0.6067      0.6326   0.6551        18       0.778       0.668      1848             0.707        True              0.0259
        saves  29.5  2026  2040      0.226 0.5284      0.5466   0.5653         2       1.000       0.637      2006             0.779        True              0.0182
```

## Read, props

- **The model beats both free projections on all 24 market / line / season
  rows.** Largest gains: goals 0.5 (anytime scorer), assists 0.5, points 0.5,
  goalie saves — the markets where ice time, power-play time and the opponent
  matter most relative to a raw average.
- **Calibration where it would bet is good on shots and points** (shots 1.5:
  claims 0.714 / 0.703, delivers 0.704 / 0.709), **over-confident by ~3-4
  points on hits 1.5 and on 2024-25 saves** (claims 0.697, delivers 0.642).
- **What this does not show:** that it beats the BOOK's line, which already
  uses ice time and matchup. That needs prices: the feed's NHL props from
  2023-05-03 (~672,000 credits for three seasons at open and close, measured
  formula) — or collecting DraftKings / Pinnacle NHL props live from opening
  night, which costs credits per game per market and is not switched on.

---

# Props and the regulation line, in units (2026-09-20, season 2025-26)

Prices: `data/ingestors/nhl_prop_odds_history.py` — bought from the feed the
same day (mike: "buy the prop history now"). One pre-game snapshot per game, an
hour before the day's first puck drop; ten books; **measured 70 credits a game**
(seven markets returned), 94,961 for the 1,394 games of 2025-26. One snapshot
means no closing-line value here. Scripts: `scripts/nhl_prop_lab_priced.py`,
`scripts/nhl_threeway_lab.py`. Models are trained only on seasons before the
test season; a bet is one unit when the model's expected value at that book's
line and price clears the cut; one bet per player-game-market.

## Props (1,312 regular-season games, 722,328 price rows, 632,860 matched to a prediction)

```
priced rows 722,328; matched to a model prediction 632,860 (111,797 player-game-markets, 1,312 games)

### player_shots_on_goal  (18,706 player-games priced; DraftKings 17,906 rows; Pinnacle same-line 125,146)

                                           rule  EV>=  bets   units   roi           ci  over share  early  late
                             MODEL @ DraftKings  0.03  4846    -6.8 -0.14   -2.9..+2.6        0.14   -1.8   1.6
                             MODEL @ DraftKings  0.06  2883    31.5  1.09   -2.5..+4.7        0.09    0.6   1.6
                             MODEL @ DraftKings  0.10  1308    45.5  3.48   -2.1..+9.0        0.06    2.2   4.8
                             MODEL @ DraftKings  0.15   497    91.1 18.33  +9.2..+27.5        0.03   20.5  16.2
                     MODEL @ best bettable book  0.03  6683    83.0  1.24   -1.1..+3.6        0.17    0.6   1.9
                     MODEL @ best bettable book  0.06  4081   119.4  2.92   -0.2..+6.0        0.12    2.7   3.2
                     MODEL @ best bettable book  0.10  1962    89.6  4.57   +0.0..+9.1        0.07    8.0   1.1
                     MODEL @ best bettable book  0.15   758   102.1 13.47  +6.0..+21.0        0.05   21.5   5.5
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.03   258   -10.4 -4.01  -16.9..+8.8        0.65    0.5  -8.5
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.06    52    -5.1 -9.78 -38.9..+19.4        0.71   -3.4 -16.2
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.10     8     NaN   NaN          NaN         NaN    NaN   NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.15     3     NaN   NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.03    73     8.7 11.88 -12.6..+36.3        0.22   23.9   0.2
       MODEL AND Pinnacle agree @ best bettable  0.06    11     NaN   NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.10     0     NaN   NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.15     0     NaN   NaN          NaN         NaN    NaN   NaN
                 BLIND always over @ DraftKings   NaN 17906 -1214.8 -6.78   -8.2..-5.4         NaN    NaN   NaN
                BLIND always under @ DraftKings   NaN 17906  -942.7 -5.26   -6.7..-3.8         NaN    NaN   NaN

### player_points  (20,924 player-games priced; DraftKings 20,572 rows; Pinnacle same-line 84,461)

                                           rule  EV>=  bets   units   roi           ci  over share  early  late
                             MODEL @ DraftKings  0.03  4327  -123.9 -2.86   -6.0..+0.3        0.31   -2.6  -3.2
                             MODEL @ DraftKings  0.06  2241   -17.4 -0.78   -5.2..+3.7        0.28   -0.2  -1.3
                             MODEL @ DraftKings  0.10   886    20.8  2.35   -4.9..+9.6        0.23    1.0   3.7
                             MODEL @ DraftKings  0.15   292     3.2  1.11 -11.4..+13.6        0.25   -3.8   6.1
                     MODEL @ best bettable book  0.03  4902  -155.6 -3.17   -6.1..-0.2        0.31   -2.8  -3.5
                     MODEL @ best bettable book  0.06  2594   -35.1 -1.35   -5.5..+2.8        0.29   -0.6  -2.1
                     MODEL @ best bettable book  0.10  1071    12.0  1.12   -5.5..+7.8        0.26    3.2  -0.9
                     MODEL @ best bettable book  0.15   357    -2.3 -0.66 -12.0..+10.7        0.26   -3.3   2.0
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.03   375     7.8  2.09  -9.6..+13.8        0.80    0.4   3.8
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.06   102    14.5 14.22 -10.5..+39.0        0.81   23.7   4.7
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.10     1     NaN   NaN          NaN         NaN    NaN   NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.15     0     NaN   NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.03    93    -3.1 -3.38 -27.2..+20.4        0.65  -20.0  12.9
       MODEL AND Pinnacle agree @ best bettable  0.06    20     NaN   NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.10     0     NaN   NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.15     0     NaN   NaN          NaN         NaN    NaN   NaN
                 BLIND always over @ DraftKings   NaN 20572 -1277.4 -6.21   -7.6..-4.8         NaN    NaN   NaN
                BLIND always under @ DraftKings   NaN 20572 -1234.6 -6.00   -7.3..-4.7         NaN    NaN   NaN

### player_assists  (20,930 player-games priced; DraftKings 20,591 rows; Pinnacle same-line 81,510)

                                           rule  EV>=  bets   units    roi           ci  over share  early  late
                             MODEL @ DraftKings  0.03  3280   -71.9  -2.19   -6.1..+1.8        0.35   -3.0  -1.4
                             MODEL @ DraftKings  0.06  1535   -32.0  -2.08   -8.2..+4.1        0.40   -4.1  -0.0
                             MODEL @ DraftKings  0.10   597    12.2   2.05  -8.3..+12.4        0.46   -5.2   9.3
                             MODEL @ DraftKings  0.15   208    14.7   7.07  -9.8..+23.9        0.44    5.3   8.8
                     MODEL @ best bettable book  0.03  3636   -76.9  -2.12   -5.8..+1.6        0.35   -2.9  -1.3
                     MODEL @ best bettable book  0.06  1696   -25.6  -1.51   -7.3..+4.3        0.40   -2.4  -0.7
                     MODEL @ best bettable book  0.10   660    21.5   3.26  -6.6..+13.1        0.45   -0.8   7.3
                     MODEL @ best bettable book  0.15   232    20.4   8.78  -7.4..+24.9        0.43    8.5   9.0
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.03   361    12.1   3.34 -10.8..+17.5        0.85    4.6   2.1
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.06   169     9.0   5.33 -16.4..+27.1        0.94    9.2   1.5
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.10    37    -7.3 -19.86 -66.2..+26.5        0.97    7.5 -45.8
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.15     3     NaN    NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.03    54     4.3   7.98 -27.4..+43.3        0.43   23.5  -7.6
       MODEL AND Pinnacle agree @ best bettable  0.06     9     NaN    NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.10     0     NaN    NaN          NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.15     0     NaN    NaN          NaN         NaN    NaN   NaN
                 BLIND always over @ DraftKings   NaN 20591 -1963.4  -9.54  -11.3..-7.7         NaN    NaN   NaN
                BLIND always under @ DraftKings   NaN 20591  -828.0  -4.02   -5.0..-3.0         NaN    NaN   NaN

### player_goal_scorer_anytime  (44,307 player-games priced; DraftKings 43,371 rows; Pinnacle same-line 131,604)

                                           rule  EV>=  bets   units    roi            ci  over share  early  late
                             MODEL @ DraftKings  0.03  3626    95.8   2.64   -7.6..+12.9         1.0    8.7  -3.4
                             MODEL @ DraftKings  0.06  2538    76.5   3.01   -9.4..+15.4         1.0   11.7  -5.7
                             MODEL @ DraftKings  0.10  1620   109.6   6.77   -9.9..+23.4         1.0   23.5 -10.0
                             MODEL @ DraftKings  0.15   957   206.2  21.55   -2.4..+45.5         1.0   51.2  -8.0
                     MODEL @ best bettable book  0.03  6313   368.0   5.83   -2.3..+14.0         1.0   13.0  -1.3
                     MODEL @ best bettable book  0.06  4684   369.8   7.89   -1.9..+17.7         1.0   16.0  -0.2
                     MODEL @ best bettable book  0.10  3197   332.9  10.41   -2.3..+23.1         1.0   21.1  -0.3
                     MODEL @ best bettable book  0.15  2022   447.3  22.12   +4.9..+39.3         1.0   30.1  14.2
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.03  2765   168.1   6.08   -2.4..+14.6         1.0   18.2  -6.1
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.06  1447   139.4   9.63   -4.2..+23.5         1.0   27.7  -8.4
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.10   587    35.7   6.09  -17.6..+29.7         1.0   18.7  -6.5
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.15   232   159.3  68.66 +10.9..+126.5         1.0   90.7  46.6
       MODEL AND Pinnacle agree @ best bettable  0.03   730   220.8  30.24   +5.5..+55.0         1.0   52.2   8.3
       MODEL AND Pinnacle agree @ best bettable  0.06   365   213.3  58.45 +13.4..+103.5         1.0   85.7  31.3
       MODEL AND Pinnacle agree @ best bettable  0.10   164   226.9 138.35 +45.1..+231.6         1.0  187.6  89.1
       MODEL AND Pinnacle agree @ best bettable  0.15    97   233.3 240.52 +89.8..+391.3         1.0  355.2 128.2
                 BLIND always over @ DraftKings   NaN 43371 -5674.9 -13.08  -15.4..-10.8         NaN    NaN   NaN
                BLIND always under @ DraftKings   NaN     0     NaN    NaN           NaN         NaN    NaN   NaN

### player_blocked_shots  (5,239 player-games priced; DraftKings 4,699 rows; Pinnacle same-line 0)

                                           rule  EV>=  bets  units    roi          ci  over share  early  late
                             MODEL @ DraftKings  0.03  1729   58.3   3.37  -1.3..+8.1        0.05    3.5   3.2
                             MODEL @ DraftKings  0.06  1065   74.0   6.95 +0.9..+13.0        0.02    7.7   6.2
                             MODEL @ DraftKings  0.10   541   49.1   9.08 +0.4..+17.7        0.00    8.9   9.3
                             MODEL @ DraftKings  0.15   192   31.1  16.17 +1.6..+30.8        0.01    8.6  23.7
                     MODEL @ best bettable book  0.03  1953   44.0   2.25  -2.2..+6.7        0.05    2.8   1.7
                     MODEL @ best bettable book  0.06  1199   67.5   5.63 -0.1..+11.4        0.02    6.7   4.5
                     MODEL @ best bettable book  0.10   605   43.2   7.14 -1.0..+15.3        0.00    7.2   7.1
                     MODEL @ best bettable book  0.15   218   30.0  13.77 +0.0..+27.5        0.00    7.6  19.9
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.03     0    NaN    NaN         NaN         NaN    NaN   NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.06     0    NaN    NaN         NaN         NaN    NaN   NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.10     0    NaN    NaN         NaN         NaN    NaN   NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.15     0    NaN    NaN         NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.03     0    NaN    NaN         NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.06     0    NaN    NaN         NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.10     0    NaN    NaN         NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.15     0    NaN    NaN         NaN         NaN    NaN   NaN
                 BLIND always over @ DraftKings   NaN  4699 -503.9 -10.72 -13.4..-8.1         NaN    NaN   NaN
                BLIND always under @ DraftKings   NaN  4699  -45.0  -0.96  -3.8..+1.9         NaN    NaN   NaN

### player_total_saves  (1,691 player-games priced; DraftKings 1,588 rows; Pinnacle same-line 8,194)

                                           rule  EV>=  bets  units   roi          ci  over share  early  late
                             MODEL @ DraftKings  0.03   984    2.7  0.27  -5.6..+6.2        0.11   -5.2   5.7
                             MODEL @ DraftKings  0.06   801    8.4  1.04  -5.5..+7.6        0.09   -4.1   6.2
                             MODEL @ DraftKings  0.10   601   15.1  2.51 -5.0..+10.1        0.07   -4.0   9.0
                             MODEL @ DraftKings  0.15   382   11.1  2.89 -6.6..+12.4        0.05   -2.8   8.6
                     MODEL @ best bettable book  0.03  1095    6.2  0.57  -5.0..+6.2        0.13   -4.7   5.8
                     MODEL @ best bettable book  0.06   890    5.5  0.62  -5.6..+6.8        0.10   -3.6   4.9
                     MODEL @ best bettable book  0.10   680   16.7  2.46  -4.7..+9.6        0.08   -1.5   6.4
                     MODEL @ best bettable book  0.15   429   23.1  5.38 -3.6..+14.3        0.06    2.6   8.2
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.03    21    NaN   NaN         NaN         NaN    NaN   NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.06     1    NaN   NaN         NaN         NaN    NaN   NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.10     0    NaN   NaN         NaN         NaN    NaN   NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.15     0    NaN   NaN         NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.03     9    NaN   NaN         NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.06     0    NaN   NaN         NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.10     0    NaN   NaN         NaN         NaN    NaN   NaN
       MODEL AND Pinnacle agree @ best bettable  0.15     0    NaN   NaN         NaN         NaN    NaN   NaN
                 BLIND always over @ DraftKings   NaN  1588 -134.3 -8.45 -13.0..-3.9         NaN    NaN   NaN
                BLIND always under @ DraftKings   NaN  1588  -65.6 -4.13  -8.8..+0.5         NaN    NaN   NaN
```

## Regulation 3-way line (1,394 games incl. playoffs)

```
3-way prices: 8,808 rows, 1,394 games, books ['betmgm', 'bovada', 'draftkings', 'fanatics', 'fanduel', 'pinnacle', 'williamhill_us']; draws 0.250; model's mean draw probability 0.209
Pinnacle's 3-way hold on these games: 5.05%; DraftKings': 8.20%
                                           rule  EV>=  bets  units    roi           ci  early  late home/draw/away
                             MODEL @ DraftKings  0.02   795  -59.2  -7.45  -16.8..+1.9   -5.5  -9.3  0.45/0.15/0.4
                             MODEL @ DraftKings  0.04   646  -19.9  -3.08  -13.6..+7.4    2.1  -8.3 0.45/0.15/0.41
                             MODEL @ DraftKings  0.06   510  -28.4  -5.57  -17.4..+6.3   -1.7  -9.4 0.44/0.14/0.42
                             MODEL @ DraftKings  0.10   297  -26.1  -8.78  -23.7..+6.1   -5.6 -11.9  0.43/0.1/0.47
                     MODEL @ best bettable book  0.02  1034  -37.2  -3.60  -12.0..+4.8    1.3  -8.5 0.49/0.12/0.39
                     MODEL @ best bettable book  0.04   886  -31.5  -3.56  -12.6..+5.5    0.7  -7.8  0.5/0.11/0.39
                     MODEL @ best bettable book  0.06   735  -44.6  -6.07  -16.0..+3.8   -0.4 -11.8  0.5/0.11/0.39
                     MODEL @ best bettable book  0.10   454  -26.4  -5.82  -18.1..+6.4   -8.4  -3.3 0.51/0.08/0.41
   SHARP-VS-SOFT (Pinnacle no-vig) @ DraftKings  0.02    58   14.4  24.91 -30.0..+79.9   51.2  -1.4    0/0.97/0.03
   SHARP-VS-SOFT (Pinnacle no-vig) @ DraftKings  0.04    15    NaN    NaN          NaN    NaN   NaN            NaN
   SHARP-VS-SOFT (Pinnacle no-vig) @ DraftKings  0.06     6    NaN    NaN          NaN    NaN   NaN            NaN
   SHARP-VS-SOFT (Pinnacle no-vig) @ DraftKings  0.10     0    NaN    NaN          NaN    NaN   NaN            NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.02    96   10.2  10.62 -29.4..+50.7   30.3  -9.1  0.06/0.74/0.2
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.04    23    NaN    NaN          NaN    NaN   NaN            NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.06     9    NaN    NaN          NaN    NaN   NaN            NaN
SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable  0.10     0    NaN    NaN          NaN    NaN   NaN            NaN
                 BLIND always away @ DraftKings   NaN  1394 -108.6  -7.79  -14.5..-1.0    NaN   NaN            NaN
                 BLIND always draw @ DraftKings   NaN  1394   95.9   6.88  -2.9..+16.6    NaN   NaN            NaN
                 BLIND always home @ DraftKings   NaN  1394 -208.4 -14.95  -20.6..-9.3    NaN   NaN            NaN
```

## Read

- **DraftKings' margin sits on the OVER.** Blind overs lose 6.2-13.1% in every
  market; blind unders lose 1.0-6.0% (blocked shots -0.96%, interval spanning
  zero). Selective unders are the structure.
- **Blocked-shot unders: the strongest candidate in the NHL work so far.**
  +6.9% / +9.1% / +16.2% at EV cuts 0.06 / 0.10 / 0.15 at DraftKings (1,065 /
  541 / 192 bets), every interval clear of zero, rising with the cut, both
  halves positive at every cut. 98% unders. Pinnacle does not quote the market,
  so there is no sharp line to be wrong against — which is also why it can be
  soft.
- **Shots-on-goal unders at the high cut:** +18.3% on 497 bets at DraftKings
  (+9.2..+27.5), +13.5% on 758 at the best bettable book, both halves positive.
  Below EV 0.15 it is +1-4% with intervals touching zero.
- **Saves: faded when October was added** (+1-3% at DraftKings, first half
  negative). Not a candidate on this evidence.
- **Points and assists: no edge from this model.** The Pinnacle-vs-soft rule is
  positive on both but on 100-375 bets with intervals of +/-15 points.
- **Anytime scorer: NOT trusted.** The model at the best bettable book reads
  +5.8% to +22.1%, but the halves disagree (+13..+30 early, -1..+14 late), the
  intervals are 17-35 points wide, and the result is carried by a few longshot
  prices. DraftKings quotes only the Yes side (blind Yes: -13.1%).
- **Regulation 3-way: nothing, and one trap.** The model loses 3-9%. Blind
  DRAW shows +6.9% on 1,394 — but 25.0% of 2025-26 games were tied after 60
  minutes against 20.5-23.5% in the eight seasons before (research doc §5);
  at a normal rate that bet loses. DraftKings holds 8.2% on this line,
  Pinnacle 5.05%.
- **ONE SEASON, ONE SNAPSHOT.** Every positive above is a candidate. The 2023-24
  and 2024-25 prices were bought the same evening (mike: "buy them now"); the
  same scripts run on them decide which candidates survive.

# Three seasons of priced props and the regulation line (2026-09-21)

The 2023-24 and 2024-25 prop and 3-way prices were bought the evening of
2026-09-20 (mike: "buy them now"): **2,799 games, 1,373,103 prop rows, 187,626
credits**, 599,969 left on the feed when it finished (the purchase run's own
closing line). Same scripts as above, one season at a time, the model trained
only on seasons before the test season; then every bet pooled across the three
seasons with `scripts/nhl_prop_pool.py` (`--dump` on the priced lab writes the
bet-level rows). Full per-season tables: `scripts/nhl_prop_lab_priced.py
--season 2024|2025|2026`, `scripts/nhl_threeway_lab.py --season ...`.

**A parser defect, found and excluded first.** FanDuel (and in 2023-24
BetRivers) list several lines per player; the shared prop parser keeps one row
per player, so it paired an over from one line with an under from another. The
tell is a two-way quote whose implied probabilities do not sum to a book's
margin. `nhl_prop_lab_priced.coherent` drops any two-way row summing outside
1.00..1.15 and prints what it dropped: **2023-24: 4,540 rows (FanDuel 2,556,
BetRivers 1,977, Bovada 6, DraftKings 1); 2024-25: 4; 2025-26: 8.** Before the
filter the 2023-24 "best bettable book" shots row read +31.1% on 2,293 bets;
after it, -0.9% on 1,000, in line with the DraftKings-only row. The stored rows
are not repaired (that is a re-buy); a mispaired quote whose sum happens to land
inside the band is still there, so the DraftKings-only rows are the clean
reference and the best-book rows carry that caveat.

## Pooled, per bet, three seasons (2023-24 + 2024-25 + 2025-26)

ROI with its 95% interval is over the POOLED bets; each season's ROI and bet
count follow. `under share` is the fraction of bets that were unders.

```
### player_blocked_shots
                      rule  EV>=  bets  units  roi          ci  under share       2023-24       2024-25       2025-26
        MODEL @ DraftKings  0.03  4904  189.6 3.87  +1.1..+6.6         0.97 +3.4% (2,170) +5.8% (1,005) +3.4% (1,729)
        MODEL @ DraftKings  0.06  3470  168.2 4.85  +1.5..+8.2         0.99 +3.3% (1,609)   +5.3% (796) +7.0% (1,065)
        MODEL @ DraftKings  0.10  2056  126.3 6.14 +1.8..+10.5         1.00   +6.6% (973)   +2.4% (542)   +9.1% (541)
        MODEL @ DraftKings  0.15   946   61.0 6.45 -0.1..+13.0         1.00   +4.1% (459)   +3.8% (295)  +16.2% (192)
MODEL @ best bettable book  0.03  7399  266.4 3.60  +1.3..+5.9         0.98 +3.4% (2,254) +4.6% (3,192) +2.3% (1,953)
MODEL @ best bettable book  0.06  5366  235.2 4.38  +1.7..+7.1         0.99 +3.3% (1,671) +4.5% (2,496) +5.6% (1,199)
MODEL @ best bettable book  0.10  3231  177.2 5.48  +2.0..+9.0         1.00 +6.3% (1,016) +4.4% (1,610)   +7.1% (605)
MODEL @ best bettable book  0.15  1480   79.6 5.38 +0.1..+10.6         1.00   +5.1% (485)   +3.2% (777)  +13.8% (218)

### player_assists
                      rule  EV>=  bets  units   roi          ci  under share       2023-24       2024-25       2025-26
        MODEL @ DraftKings  0.03 10445  -67.5 -0.65  -2.8..+1.5         0.58 +0.3% (4,738) -0.4% (2,427) -2.2% (3,280)
        MODEL @ DraftKings  0.06  5199   66.7  1.28  -2.0..+4.6         0.53 +2.7% (2,647) +2.7% (1,017) -2.1% (1,535)
        MODEL @ DraftKings  0.10  2162  121.7  5.63 +0.2..+11.0         0.50 +7.3% (1,215)   +6.0% (350)   +2.0% (597)
        MODEL @ DraftKings  0.15   784   68.0  8.67 -0.5..+17.8         0.53   +8.9% (472)  +11.1% (104)   +7.1% (208)
MODEL @ best bettable book  0.10  2406  147.4  6.13 +1.0..+11.3         0.49 +8.1% (1,337)   +4.4% (409)   +3.3% (660)
MODEL @ best bettable book  0.15   890   74.1  8.32 -0.3..+16.9         0.52   +7.2% (536)  +12.5% (122)   +8.8% (232)

### player_total_saves
                      rule  EV>=  bets  units  roi          ci  under share       2023-24       2024-25       2025-26
        MODEL @ DraftKings  0.06  1793   39.4 2.20  -2.1..+6.5         0.86   +0.4% (779)  +13.0% (213)   +1.0% (801)
        MODEL @ DraftKings  0.10  1366   58.2 4.26  -0.7..+9.2         0.87   +2.5% (579)  +15.5% (186)   +2.5% (601)
        MODEL @ DraftKings  0.15   912   68.6 7.52 +1.5..+13.6         0.88   +8.8% (386)  +16.4% (144)   +2.9% (382)
MODEL @ best bettable book  0.10  2229  111.3 4.99  +1.1..+8.9         0.88   +1.7% (670)   +9.5% (879)   +2.5% (680)
MODEL @ best bettable book  0.15  1567  153.5 9.80 +5.2..+14.4         0.89   +8.7% (466)  +13.3% (672)   +5.4% (429)

### player_shots_on_goal
                      rule  EV>=  bets  units  roi          ci  under share       2023-24       2024-25       2025-26
        MODEL @ DraftKings  0.06  9839  120.0 1.22  -0.7..+3.2         0.79 +0.4% (4,020) +2.5% (2,936) +1.1% (2,883)
        MODEL @ DraftKings  0.10  4503   60.5 1.34  -1.6..+4.3         0.80 +0.3% (1,890) +0.7% (1,305) +3.5% (1,308)
        MODEL @ DraftKings  0.15  1575   90.3 5.73 +0.6..+10.9         0.81   +0.8% (633)   -1.4% (445)  +18.3% (497)
MODEL @ best bettable book  0.10  6827  274.9 4.03  +1.6..+6.5         0.79 +1.7% (2,678) +6.4% (2,187) +4.6% (1,962)
MODEL @ best bettable book  0.15  2588  128.2 4.96  +0.8..+9.1         0.79 -0.9% (1,000)   +4.2% (830)  +13.5% (758)

### player_points
                      rule  EV>=  bets  units   roi          ci  under share       2023-24       2024-25       2025-26
        MODEL @ DraftKings  0.06  6594  -92.2 -1.40  -4.0..+1.2         0.67 -0.4% (2,756) -3.9% (1,597) -0.8% (2,241)
        MODEL @ DraftKings  0.10  2550   27.1  1.06  -3.2..+5.3         0.72 -0.0% (1,173)   +1.3% (491)   +2.4% (886)
        MODEL @ DraftKings  0.15   830   58.8  7.09 -0.7..+14.9         0.75   +4.4% (408)  +28.9% (130)   +1.1% (292)
MODEL @ best bettable book  0.10  3703 -119.6 -3.23  -7.4..+1.0         0.65 -5.8% (1,876)   -3.1% (756) +1.1% (1,071)

### player_goal_scorer_anytime  (Yes only; "under share" is 0 by construction)
                      rule  EV>=  bets  units   roi          ci        2023-24       2024-25        2025-26
        MODEL @ DraftKings  0.06  3199  188.3  5.89 -5.1..+16.8   -0.1% (293)  +30.5% (368)  +3.0% (2,538)
        MODEL @ DraftKings  0.10  1980  211.3 10.67 -4.4..+25.8   +4.5% (161)  +47.5% (199)  +6.8% (1,620)
        MODEL @ DraftKings  0.15  1143  313.0 27.38 +5.1..+49.7   +21.8% (78)  +83.1% (108)  +21.5% (957)
MODEL @ best bettable book  0.06 10232  701.6  6.86 +0.7..+13.0 +8.1% (2,819) +3.8% (2,729)  +7.9% (4,684)
MODEL @ best bettable book  0.10  6656  668.1 10.04 +1.8..+18.3 +10.3% (1,801) +9.0% (1,658) +10.4% (3,197)
MODEL @ best bettable book  0.15  3967  658.3 16.59 +5.2..+28.0 +14.1% (1,039)   +7.1% (906) +22.1% (2,022)
```

Blind betting at DraftKings, every market, every season: always-over loses
6.2% to 25.8% (eighteen cells, all negative); always-under ranges -6.1% to
+11.8%, and the three positive cells are 2024-25 saves (+11.8% on 314 rows),
2024-25 blocked shots (+3.2% on 1,631) and 2023-24 saves (+1.2% on 1,437).

## Regulation 3-way line, three seasons

| | 2023-24 | 2024-25 | 2025-26 |
|---|---|---|---|
| Games priced | 1,400 | 1,398 | 1,394 |
| Tied after 60 minutes | 20.6% | 20.8% | 25.0% |
| Model's mean draw probability | 21.7% | 21.4% | 20.9% |
| DraftKings hold / Pinnacle hold | 7.23% / 4.35% | 8.18% / 4.38% | 8.20% / 5.05% |
| Model at DraftKings, EV >= 0.02..0.10 | -3.1% to -5.8% | -1.7% to -3.3% | -3.1% to -8.8% |
| Model at best bettable book | -2.2% to +3.0% | +0.2% to +7.4% (early +18.5, late -3.6 at 0.10) | -3.6% to -6.1% |
| Blind draw at DraftKings | -6.3% (1,396) | -9.7% (1,396) | +6.9% (1,394) |
| Pinnacle no-vig vs DraftKings, EV >= 0.02 | +6.8% (308), 94% draws | +13.2% (50), 90% draws | +24.9% (58), 97% draws |
| Same, at the best bettable book | +7.9% (692) | +0.0% (325) | +10.6% (96) |

## Read, three seasons

- **Blocked-shot unders survive.** Twelve of twelve DraftKings cells positive,
  pooled +3.9% / +4.8% / +6.1% / +6.5% at EV 0.03 / 0.06 / 0.10 / 0.15 on
  4,904 / 3,470 / 2,056 / 946 bets, intervals clear of zero through 0.10 and
  the return rising with the cut (a plateau, not a peak). 97-100% unders. The
  best-bettable rows agree (+3.6% to +5.5%, all intervals clear of zero) on
  more bets, because the other books quoted the market on more player-games in
  2024-25 than DraftKings did (3,192 vs 1,005 at the 0.03 cut). Weakest
  season 2024-25 at the higher cuts (+2.4% / +3.8%, the thin-DraftKings year).
  Pinnacle still does not quote it.
- **Assists at the 0.10 cut is a second candidate, new with the third season.**
  It looked flat on 2025-26 alone. Pooled +5.6% on 2,162 (+0.2..+11.0), every
  season positive at 0.10 and 0.15, about half overs — so this is not the
  over-margin story, it is the model against the line. Only the pooled
  interval and 2023-24's clear zero; 2025-26 is +2.0% on 597.
- **Saves: no negative cell, and 2024-25 carries it.** Pooled +4.3% / +7.5% at
  0.10 / 0.15 on 1,366 / 912, but 2024-25's +15.5% / +16.4% sit on 186 / 144
  DraftKings bets and the two other seasons are +2.5-2.9% at 0.10. The
  best-book row at 0.15 is +9.8% on 1,567 (+5.2..+14.4) with every season
  above +5%. A candidate on the best-book evidence, thin at DraftKings.
- **Shots on goal did not replicate at DraftKings** (+0.8%, -1.4%, +18.3% at
  0.15; the 2025-26 number is one season of three). At the best bettable book
  it is +4.0% on 6,827 at 0.10 with all three seasons positive (+1.7 / +6.4 /
  +4.6), interval +1.6..+6.5 — real if the best-book rows are, which the
  FanDuel caveat above qualifies.
- **Points: nothing** (negative at 0.03 and 0.06; +7.1% at 0.15 on 830 rests
  on 2024-25's +28.9% on 130).
- **Anytime scorer: at DraftKings still not trusted** (-0.1% / +30.5% / +3.0%
  across seasons at 0.06). **At the best bettable book it is the most
  consistent row in the table:** +10.0% on 6,656 at 0.10, seasons +10.3 /
  +9.0 / +10.4, interval +1.8..+18.3, +16.6% on 3,967 at 0.15 with every
  season above +7%. Yes-only, so the mispairing defect cannot touch it, but
  the payout variance is why the interval is 16 points wide. Worth a check
  that the "best" book's Yes price is one a bettor is actually offered
  (limits, and whether the parser is reading an alternate scorer market).
- **Regulation 3-way: the model loses in all three seasons at DraftKings** and
  is not a candidate. Blind draw was one overtime-heavy season. The
  Pinnacle-no-vig-vs-DraftKings rule is positive in all three (+6.8 / +13.2 /
  +24.9) and almost entirely draws, but on 308 / 50 / 58 bets with intervals
  of 40-80 points; pooled +10% on 416. A structural note, not a model.
- **Frozen game-line candidates (moneyline, puck line):** untested on
  2023-24 -> 2025-26 until the game-line purchase lands (restarted
  2026-09-21 on mike's word, resuming from 2022-03-10).

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
- **Frozen game-line candidates (moneyline, puck line):** tested the same
  night on 2023-24 -> 2025-26 — round three, below. The moneyline did not
  replicate.

# Round three (2026-09-21): the frozen candidates on seasons they never saw

The game-line purchase landed the same night (mike: "im not waiting for oct
for anything"): 1,367 dates, 5,331 snapshots, 1,200,267 rows, 159,930 credits
across the two runs (37,680 on 2026-09-20 before the low-memory kill, 122,130
+ 60 for two timed-out snapshots on 2026-09-21). `scripts/nhl_market_lab3.py`:
the round-two moneyline and puck-line models, unchanged, fit on every season
before the test season, decided against DraftKings' (and separately
Pinnacle's) first pre-game quote and graded at DraftKings' open price; CLV
against Pinnacle's last pre-game quote, no-vig. 2022-23 is included for
completeness but round two selected the candidate partly on it (the archive
covered it to 2022-11-27); **2023-24 -> 2025-26 are the unseen seasons.**

## Pooled over the three unseen seasons (bets, units, ROI; the interval is the
## normal approximation with unit variance, so ± is approximate)

```
rule                              edge>=  bets    units    roi      +-     2022-23  2023-24  2024-25  2025-26
moneyline vs DraftKings open       0.04   1,999   +26.1   +1.3%   4.4      +2.2     -0.4     +8.4     -3.7
moneyline vs DraftKings open       0.06   1,268   +37.6   +3.0%   5.5      +2.0     +4.1    +10.3     -5.0
moneyline vs DraftKings open       0.08     726   +11.6   +1.6%   7.3      +2.8     +4.8     +5.1     -4.7
moneyline vs Pinnacle open         0.06   1,216    -0.7   -0.1%   5.6      +1.3     +5.1     +6.6    -11.2
puck line vs DraftKings open       0.06   1,019   +36.2   +3.6%   6.1      -4.3     -2.0    +10.1     +2.7
puck line vs DraftKings open       0.08     493   +58.0  +11.8%   8.8      -3.9     +1.2    +19.9    +15.5
totals vs DraftKings open          0.04   1,739    -9.0   -0.5%   4.7      -1.8     -3.0     +5.1     -4.4
```

## Read, round three

- **The moneyline candidate did not replicate.** Round two's +8.0% at edge
  0.06 (interval +2.3..+13.6) is +3.0% on 1,268 unseen bets with an interval
  of roughly -2.5..+8.5; one of three seasons is negative (2025-26, -5.0%),
  and 2024-25 (+10.3%) carries the pool. At 0.04 it is +1.3%; at 0.08,
  +1.6%. Decided against Pinnacle's open instead it is -0.1%. **What DID hold
  is the closing-line value**: the bets beat Pinnacle's close 61-67% of the
  time at 0.06 in every season, +0.5 to +0.9 points of no-vig probability.
  The model reads something the opening price lacks; it is not enough to
  beat the price. **Not a model to bet.** A paper-only run at DraftKings'
  open at 0.06 would be the honest next measurement, if any.
- **Puck line: a peak, not a plateau.** +11.8% at 0.08 on 493 is two seasons
  (+19.9, +15.5) against two negative-or-flat, and 0.06 either side reads
  +3.6% / +5.5% with intervals spanning zero. Round two's rule applies.
- **Totals: nothing**, as in rounds one and two.
- **DraftKings' open against Pinnacle's open, no model:** 216-295 bets a
  season at a 2-point gap, -2.9% / +2.2% / +5.9% / +5.9%. Not a rule.

## The full tables

```
===== test season 2023 (2022-23): 1,400 games with inputs, 1,400 with a DraftKings open, 1,399 with a Pinnacle open =====
moneyline, ALL inputs, logistic: fit on 4,788 games

### Moneyline 2023: bet at the DraftKings OPEN price

                                      model  edge>=  bets  units   roi           ci  clv_pts  beat_close  fav share  early  late
               moneyline vs DraftKings open    0.02  1104   13.9  1.26   -4.4..+7.0     0.37        59.7       0.55   -1.2   3.7
               moneyline vs DraftKings open    0.04   808   18.0  2.23   -4.4..+8.9     0.43        60.9       0.56   -3.1   7.5
               moneyline vs DraftKings open    0.06   570   11.5  2.02   -5.9..+9.9     0.54        63.3       0.56   -5.3   9.3
               moneyline vs DraftKings open    0.08   380   10.6  2.78  -7.0..+12.5     0.60        64.2       0.54   -2.4   8.0
               moneyline vs DraftKings open    0.10   229   24.1 10.52  -2.5..+23.5     0.62        63.8       0.52    5.8  15.1
                 moneyline vs Pinnacle open    0.02  1088    2.7  0.24   -5.5..+6.0     0.35        59.4       0.54   -3.0   3.5
                 moneyline vs Pinnacle open    0.04   777    9.9  1.27   -5.6..+8.1     0.43        60.5       0.53   -2.0   4.5
                 moneyline vs Pinnacle open    0.06   541    7.0  1.30   -6.9..+9.5     0.50        62.1       0.52   -7.7  10.3
                 moneyline vs Pinnacle open    0.08   349   21.1  6.05  -4.3..+16.4     0.61        63.6       0.51   -0.4  12.4
                 moneyline vs Pinnacle open    0.10   207   30.1 14.52  +0.7..+28.3     0.56        63.8       0.48    6.1  22.9
Pinnacle open vs DraftKings open (no model)    0.02   216   -6.4 -2.94  -15.0..+9.1     0.44        61.1       0.70   -1.9  -4.0
Pinnacle open vs DraftKings open (no model)    0.04    46    6.2 13.58 -12.5..+39.7     0.62        60.9       0.83   15.9  11.2
Pinnacle open vs DraftKings open (no model)    0.06     9    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.08     0    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.10     0    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN

### Puck line 2023: bet at the DraftKings OPEN price

                       model  edge>=  bets  units    roi           ci  early  late
puck line vs DraftKings open    0.02  1057  -57.1  -5.40  -12.1..+1.3   -4.3  -6.5
puck line vs DraftKings open    0.04   771  -50.4  -6.54  -14.5..+1.4   -5.9  -7.2
puck line vs DraftKings open    0.06   509  -21.7  -4.27  -14.1..+5.6   -3.3  -5.2
puck line vs DraftKings open    0.08   301  -11.8  -3.93  -16.8..+8.9    2.2 -10.0
puck line vs DraftKings open    0.10   164   -8.3  -5.07 -22.9..+12.7   -0.8  -9.3
  puck line vs Pinnacle open    0.02  1065  -58.6  -5.51  -12.1..+1.1   -6.2  -4.8
  puck line vs Pinnacle open    0.04   783  -56.0  -7.15  -14.9..+0.6   -8.8  -5.5
  puck line vs Pinnacle open    0.06   523  -37.3  -7.12  -16.5..+2.3   -6.5  -7.8
  puck line vs Pinnacle open    0.08   336  -23.7  -7.04  -18.7..+4.6   -4.2  -9.8
  puck line vs Pinnacle open    0.10   198  -25.3 -12.75  -27.4..+1.9  -10.7 -14.8

### Totals 2023: inputs without the market's price, bet at the DraftKings OPEN

                    model  edge>=  bets  units   roi           ci  over share
totals vs DraftKings open    0.02   898   -7.2 -0.80   -7.1..+5.5        0.60
totals vs DraftKings open    0.04   548   -9.8 -1.80   -9.9..+6.3        0.65
totals vs DraftKings open    0.06   288   13.5  4.68  -6.5..+15.8        0.74
totals vs DraftKings open    0.08   142   10.6  7.46  -8.4..+23.3        0.82
totals vs DraftKings open    0.10    56   -3.4 -6.08 -31.9..+19.7        0.86

===== test season 2024 (2023-24): 1,400 games with inputs, 1,400 with a DraftKings open, 1,400 with a Pinnacle open =====
moneyline, ALL inputs, logistic: fit on 6,188 games

### Moneyline 2024: bet at the DraftKings OPEN price

                                      model  edge>=  bets  units   roi           ci  clv_pts  beat_close  fav share  early  late
               moneyline vs DraftKings open    0.02  1039  -11.2 -1.08   -6.8..+4.6     0.50        60.4       0.60   -0.4  -1.8
               moneyline vs DraftKings open    0.04   700   -2.6 -0.37   -7.2..+6.5     0.63        62.1       0.62   -0.2  -0.6
               moneyline vs DraftKings open    0.06   442   18.3  4.14  -4.3..+12.6     0.79        67.0       0.62    5.5   2.8
               moneyline vs DraftKings open    0.08   259   12.4  4.79  -6.2..+15.8     0.83        68.3       0.62    0.5   9.0
               moneyline vs DraftKings open    0.10   136    0.5  0.40 -14.8..+15.6     0.77        65.4       0.66   -1.2   2.0
                 moneyline vs Pinnacle open    0.02  1027  -31.6 -3.07   -8.8..+2.7     0.46        58.9       0.59   -1.3  -4.9
                 moneyline vs Pinnacle open    0.04   665   -1.3 -0.20   -7.3..+6.9     0.63        62.0       0.61   -0.1  -0.2
                 moneyline vs Pinnacle open    0.06   420   21.3  5.07  -3.7..+13.8     0.77        65.7       0.60    2.4   7.8
                 moneyline vs Pinnacle open    0.08   241   12.3  5.08  -6.6..+16.7     0.78        66.8       0.58    1.6   8.5
                 moneyline vs Pinnacle open    0.10   110   11.1 10.09  -7.3..+27.4     0.89        68.2       0.63    6.3  13.9
Pinnacle open vs DraftKings open (no model)    0.02   218    4.8  2.21 -10.6..+15.0     0.28        59.6       0.58    0.2   4.2
Pinnacle open vs DraftKings open (no model)    0.04    26    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.06     3    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.08     0    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.10     0    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN

### Puck line 2024: bet at the DraftKings OPEN price

                       model  edge>=  bets  units    roi           ci  early  late
puck line vs DraftKings open    0.02   983  -36.1  -3.68  -10.6..+3.3   -3.2  -4.1
puck line vs DraftKings open    0.04   627  -22.0  -3.51  -12.5..+5.4   -4.4  -2.6
puck line vs DraftKings open    0.06   368   -7.5  -2.03  -13.8..+9.7   -0.5  -3.6
puck line vs DraftKings open    0.08   185    2.3   1.27 -15.4..+17.9   -0.6   3.1
puck line vs DraftKings open    0.10    81   -7.6  -9.38 -33.9..+15.2  -22.9   3.8
  puck line vs Pinnacle open    0.02  1008  -41.0  -4.07  -11.0..+2.8   -0.0  -8.1
  puck line vs Pinnacle open    0.04   678  -16.3  -2.40  -10.9..+6.1   -1.1  -3.7
  puck line vs Pinnacle open    0.06   413   -0.2  -0.05 -11.0..+10.9    2.3  -2.4
  puck line vs Pinnacle open    0.08   238  -24.6 -10.32  -24.1..+3.4   -7.7 -12.9
  puck line vs Pinnacle open    0.10   131   -1.4  -1.07 -19.2..+17.1    2.1  -4.2

### Totals 2024: inputs without the market's price, bet at the DraftKings OPEN

                    model  edge>=  bets  units   roi           ci  over share
totals vs DraftKings open    0.02   850   -7.9 -0.93   -7.5..+5.6        0.41
totals vs DraftKings open    0.04   466  -14.2 -3.04  -11.9..+5.8        0.37
totals vs DraftKings open    0.06   221   -6.2 -2.82 -15.6..+10.0        0.38
totals vs DraftKings open    0.08    84   -6.2 -7.35 -28.3..+13.6        0.46
totals vs DraftKings open    0.10    26    NaN   NaN          NaN         NaN

===== test season 2025 (2024-25): 1,398 games with inputs, 1,398 with a DraftKings open, 1,398 with a Pinnacle open =====
moneyline, ALL inputs, logistic: fit on 7,588 games

### Moneyline 2025: bet at the DraftKings OPEN price

                                      model  edge>=  bets  units   roi           ci  clv_pts  beat_close  fav share  early  late
               moneyline vs DraftKings open    0.02  1003   75.7  7.55  +1.2..+13.9     0.59        60.0       0.46   11.0   4.1
               moneyline vs DraftKings open    0.04   636   53.3  8.38  +0.4..+16.4     0.81        64.0       0.44   10.2   6.5
               moneyline vs DraftKings open    0.06   394   40.7 10.33  +0.1..+20.5     0.94        65.7       0.46   14.2   6.4
               moneyline vs DraftKings open    0.08   215   11.0  5.13  -8.8..+19.0     1.37        70.7       0.40    3.1   7.1
               moneyline vs DraftKings open    0.10   111    2.8  2.52 -16.3..+21.3     1.29        73.0       0.41   -8.6  13.4
                 moneyline vs Pinnacle open    0.02   991   40.6  4.10  -2.3..+10.5     0.47        57.2       0.44    7.8   0.4
                 moneyline vs Pinnacle open    0.04   659   24.2  3.67  -4.2..+11.6     0.61        60.4       0.43    6.3   1.0
                 moneyline vs Pinnacle open    0.06   376   24.9  6.63  -4.1..+17.4     0.75        62.0       0.40   11.9   1.4
                 moneyline vs Pinnacle open    0.08   205    3.8  1.87 -12.6..+16.4     1.01        63.4       0.38    4.8  -1.0
                 moneyline vs Pinnacle open    0.10   101   -9.8 -9.74 -29.9..+10.4     1.39        71.3       0.40   -3.8 -15.5
Pinnacle open vs DraftKings open (no model)    0.02   295   17.4  5.89  -4.9..+16.7     0.71        65.4       0.59    1.8  10.0
Pinnacle open vs DraftKings open (no model)    0.04    60    8.8 14.67  -9.6..+38.9     0.44        68.3       0.65   21.6   7.7
Pinnacle open vs DraftKings open (no model)    0.06    12    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.08     4    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.10     1    NaN   NaN          NaN      NaN         NaN        NaN    NaN   NaN

### Puck line 2025: bet at the DraftKings OPEN price

                       model  edge>=  bets  units   roi          ci  early  late
puck line vs DraftKings open    0.02   970   22.2  2.29  -4.9..+9.4    8.9  -4.4
puck line vs DraftKings open    0.04   584   40.6  6.96 -2.5..+16.4   14.8  -0.9
puck line vs DraftKings open    0.06   352   35.6 10.12 -2.1..+22.3   14.8   5.4
puck line vs DraftKings open    0.08   179   35.7 19.94 +1.9..+38.0   19.8  20.1
puck line vs DraftKings open    0.10    79   19.2 24.34 -4.8..+53.5   26.6  22.2
  puck line vs Pinnacle open    0.02   996   -2.7 -0.27  -7.3..+6.7    7.4  -8.0
  puck line vs Pinnacle open    0.04   629   15.3  2.43 -6.4..+11.3   10.0  -5.1
  puck line vs Pinnacle open    0.06   373   47.9 12.84 +1.3..+24.4   15.4  10.3
  puck line vs Pinnacle open    0.08   204   25.0 12.25 -3.3..+27.8   18.1   6.4
  puck line vs Pinnacle open    0.10   121   19.5 16.15 -3.8..+36.1   25.1   7.3

### Totals 2025: inputs without the market's price, bet at the DraftKings OPEN

                    model  edge>=  bets  units   roi           ci  over share
totals vs DraftKings open    0.02   987   51.8  5.25  -0.7..+11.3        0.09
totals vs DraftKings open    0.04   644   32.6  5.06  -2.4..+12.5        0.06
totals vs DraftKings open    0.06   331    3.7  1.11  -9.2..+11.4        0.02
totals vs DraftKings open    0.08   144   -0.6 -0.45 -16.2..+15.3        0.01
totals vs DraftKings open    0.10    50    5.2 10.32 -16.1..+36.7        0.02

===== test season 2026 (2025-26): 1,394 games with inputs, 1,394 with a DraftKings open, 1,394 with a Pinnacle open =====
moneyline, ALL inputs, logistic: fit on 8,986 games

### Moneyline 2026: bet at the DraftKings OPEN price

                                      model  edge>=  bets  units    roi           ci  clv_pts  beat_close  fav share  early  late
               moneyline vs DraftKings open    0.02  1006  -58.8  -5.84  -12.0..+0.3     0.30        55.7       0.53   -8.3  -3.4
               moneyline vs DraftKings open    0.04   663  -24.6  -3.70  -11.2..+3.8     0.47        59.0       0.52   -8.1   0.7
               moneyline vs DraftKings open    0.06   432  -21.4  -4.96  -14.2..+4.3     0.63        60.9       0.51  -11.7   1.8
               moneyline vs DraftKings open    0.08   252  -11.8  -4.69  -16.8..+7.4     0.69        62.3       0.48  -10.8   1.4
               moneyline vs DraftKings open    0.10   126   -7.4  -5.86 -23.5..+11.8     0.94        69.8       0.44   -3.8  -7.9
                 moneyline vs Pinnacle open    0.02  1006  -66.6  -6.62  -12.7..-0.5     0.21        54.2       0.52   -7.5  -5.8
                 moneyline vs Pinnacle open    0.04   667  -46.5  -6.98  -14.4..+0.5     0.43        57.3       0.52   -8.7  -5.3
                 moneyline vs Pinnacle open    0.06   420  -46.9 -11.17  -20.3..-2.0     0.50        57.4       0.52  -15.5  -6.8
                 moneyline vs Pinnacle open    0.08   246   -3.3  -1.33 -13.5..+10.8     0.45        60.2       0.51   -5.5   2.8
                 moneyline vs Pinnacle open    0.10   119   -5.6  -4.69 -22.9..+13.6     0.69        63.0       0.46   -9.7   0.3
Pinnacle open vs DraftKings open (no model)    0.02   232   13.7   5.91  -7.3..+19.2     0.62        60.3       0.45   17.9  -6.1
Pinnacle open vs DraftKings open (no model)    0.04    36    2.6   7.14 -27.6..+41.9     1.50        77.8       0.28  -12.5  26.8
Pinnacle open vs DraftKings open (no model)    0.06     9    NaN    NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.08     4    NaN    NaN          NaN      NaN         NaN        NaN    NaN   NaN
Pinnacle open vs DraftKings open (no model)    0.10     1    NaN    NaN          NaN      NaN         NaN        NaN    NaN   NaN

### Puck line 2026: bet at the DraftKings OPEN price

                       model  edge>=  bets  units    roi           ci  early  late
puck line vs DraftKings open    0.02   939  -71.2  -7.58  -15.1..-0.0   -9.1  -6.0
puck line vs DraftKings open    0.04   564  -25.7  -4.56  -14.7..+5.5   -6.2  -2.9
puck line vs DraftKings open    0.06   299    8.1   2.72 -11.5..+16.9    2.1   3.3
puck line vs DraftKings open    0.08   129   20.0  15.49  -7.4..+38.3    1.4  29.4
puck line vs DraftKings open    0.10    51    0.0   0.06 -36.7..+36.8  -15.9  15.4
  puck line vs Pinnacle open    0.02   978 -102.2 -10.45  -17.7..-3.2  -10.7 -10.2
  puck line vs Pinnacle open    0.04   626  -52.6  -8.40  -17.6..+0.8  -10.6  -6.2
  puck line vs Pinnacle open    0.06   357   -7.7  -2.14 -14.5..+10.2   -0.6  -3.7
  puck line vs Pinnacle open    0.08   195  -16.0  -8.19  -23.7..+7.3   -9.5  -6.9
  puck line vs Pinnacle open    0.10   111   -0.3  -0.31 -19.3..+18.6   -7.0   6.3

### Totals 2026: inputs without the market's price, bet at the DraftKings OPEN

                    model  edge>=  bets  units   roi           ci  over share
totals vs DraftKings open    0.02  1004  -62.5 -6.22  -12.1..-0.3        0.09
totals vs DraftKings open    0.04   629  -27.4 -4.35  -11.8..+3.1        0.04
totals vs DraftKings open    0.06   332   -4.0 -1.20  -11.4..+9.0        0.02
totals vs DraftKings open    0.08   125    0.4  0.31 -16.5..+17.1        0.02
totals vs DraftKings open    0.10    36    7.3 20.30  -9.8..+50.4        0.03
```

---

# The live artifacts, graded (2026-10-01)

Rounds one to three graded a regularised logistic model. **The two artifacts
`model_registry` says are live had never been put against a price.** This is
that run: `python -m scripts.nhl_live_artifact_grade`. Both were trained
2018-19 -> 2024-25 (`nhl_moneyline` `20260920_131606`,
`nhl_moneyline_regulation` `20260920_133544`), so 2025-26 is the only season
neither has seen and the only one graded. 1,352 games, every one with a
DraftKings and a Pinnacle price.

Each rule is run twice. **As it runs today** is the scorer's decision as
written (`models.scorer._decide`): the probability correction every model
decides on (`model_calibration.promoted_b = -0.259947` for both, taken from the
other models' records because these two have none), then the 0.55 / 0.05 and
0.40 / 0.05 cuts, the 0.20 EV floor, the -200 price floor and the 0.20 edge cap
at DraftKings. **On the model's own probability** is the same with the
correction off. What this does not reproduce: production scores a game when its
line opens, days ahead, and locks it; this decides at the game-day quote.
`clv_pts` / `beat_close` are Pinnacle's last pre-game no-vig probability minus
its first, on the side taken; the blind rows carry the same two columns as the
bar.

```
===== nhl_moneyline 20260920_131606 on 2025-26: 1,352 games with a DraftKings pre-game price (1,352 with a Pinnacle close) =====
log loss: model 0.6884 | DraftKings no-vig 0.6836 | home rate 0.6923   AUC: model 0.5579 | DraftKings 0.5798
model home-win probability quantiles: {0.01: 0.359, 0.1: 0.424, 0.25: 0.471, 0.5: 0.535, 0.75: 0.593, 0.9: 0.644, 0.99: 0.722}; share >= 0.70: 0.019; share within 0.485..0.515: 0.106; share within 0.435..0.565 (the band the correction flips): 0.518

### The production rule on the holdout season

                                                 rule priced at  bets  units   roi           ci  clv_pts  beat_close  early  late  dog share  avg p  win%
AS IT RUNS TODAY (corrected prob, 0.55/0.05, EV 0.20)        dk    30    6.3 20.97 -20.3..+62.2     0.54        60.0   18.5  23.4       1.00  0.492  53.3
AS IT RUNS TODAY (corrected prob, 0.55/0.05, EV 0.20)      best    41    5.0 12.22 -23.5..+47.9     0.23        53.7   13.2  11.2       1.00  0.500  48.8
             same cuts on the model's OWN probability        dk    15    NaN   NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN
             same cuts on the model's OWN probability      best    25    2.6 10.37 -32.2..+52.9    -0.34        56.0   22.9  -1.2       0.92  0.592  52.0

of the 30 as-it-runs bets at DraftKings: 30 are on a side the model itself has under 50% ({'bets': 30, 'units': 6.3, 'roi': 20.97, 'ci': '-20.3..+62.2'}); 0 on a side it has at 50%+ ({})

### Neighbourhood: bet any side whose raw model probability beats DraftKings' implied by the cut (no other gate)

 edge>=  bets  units    roi           ci  clv_pts  beat_close  early  late  dog share  avg p  win%
   0.02   587   -3.0  -0.51   -9.7..+8.7     0.34        55.2    0.0  -1.1       0.67  0.513  45.0
   0.04   341   -1.0  -0.30 -12.6..+12.1     0.40        57.5   -9.1   8.4       0.74  0.518  44.3
   0.05   256  -12.7  -4.98  -19.5..+9.5     0.48        59.8   -6.7  -3.3       0.78  0.516  41.0
   0.06   188   -7.8  -4.13 -21.0..+12.7     0.67        66.0   -6.8  -1.4       0.81  0.517  41.5
   0.08    80   -2.3  -2.83 -28.9..+23.2     0.79        72.5   -0.9  -4.8       0.90  0.524  41.2
   0.10    31   -6.0 -19.48 -62.2..+23.2     0.89        77.4   18.7 -55.3       0.90  0.534  32.3
   0.12    12    NaN    NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN
   0.15     2    NaN    NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN

### Probability floor x edge, raw probability, at DraftKings

 prob>=  edge>=  bets  units    roi           ci  clv_pts  beat_close  early  late  dog share  avg p  win%
   0.50    0.03   258  -30.1 -11.67  -23.6..+0.2     0.31        52.7  -19.8  -3.5       0.47  0.574  45.7
   0.50    0.05   150  -25.4 -16.93  -33.0..-0.9     0.34        56.7  -16.1 -17.8       0.63  0.569  41.3
   0.50    0.08    52   -4.6  -8.89 -38.2..+20.4     0.58        67.3   -6.5 -11.2       0.85  0.562  42.3
   0.55    0.03   159  -14.6  -9.21  -23.6..+5.2     0.10        49.7  -13.0  -5.4       0.18  0.604  49.7
   0.55    0.05    84   -6.0  -7.18 -27.8..+13.4     0.18        54.8  -11.7  -2.6       0.33  0.604  48.8
   0.55    0.08    31   -2.3  -7.33 -43.9..+29.3     0.45        67.7   -3.1 -11.3       0.74  0.589  45.2
   0.60    0.03    67   -2.2  -3.22 -23.8..+17.4    -0.12        46.3  -15.9   9.1       0.04  0.643  56.7
   0.60    0.05    37   -4.8 -12.90 -42.3..+16.5    -0.16        51.4  -18.2  -7.9       0.08  0.639  48.6
   0.60    0.08    11    NaN    NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN
   0.65    0.03    27   -0.2  -0.81 -30.1..+28.5    -0.17        37.0  -25.9  22.5       0.00  0.680  63.0
   0.65    0.05    12    NaN    NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN
   0.65    0.08     2    NaN    NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN
   0.70    0.03     4    NaN    NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN
   0.70    0.05     2    NaN    NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN
   0.70    0.08     0    NaN    NaN          NaN      NaN         NaN    NaN   NaN        NaN    NaN   NaN

### Blind baselines, same games, DraftKings price

           blind  bets  units   roi          ci  clv_pts  beat_close
     always home  1352  -97.3 -7.19 -12.1..-2.3    -0.39        40.8
     always away  1352    9.0  0.67  -5.1..+6.5     0.39        57.5
always favourite  1352 -121.0 -8.95 -13.4..-4.5    -0.19        46.5
 always underdog  1352   38.5  2.85  -3.3..+9.0     0.21        52.7

===== nhl_moneyline_regulation 20260920_133544 on 2025-26: 1,352 games with a DraftKings 3-way price =====
log loss: model 1.0772 | DraftKings no-vig 1.0727 | this season's own class rates 1.0825
model mean probabilities away/draw/home: [0.355 0.22  0.425]; actual: [0.353 0.254 0.393]
after the correction the three probabilities sum to 1.144 on average (min 1.023, max 1.176); raw they sum to 1.000

### The production rule on the holdout season

                                              rule  bets  units    roi           ci  early  late  games  avg raw p home/draw/away
                     AS IT RUNS TODAY @ DraftKings   300  -39.2 -13.08  -27.4..+1.2  -19.7  -6.5    300      0.415    0.43/0/0.57
             AS IT RUNS TODAY @ best bettable book   447  -20.5  -4.59  -16.7..+7.5   -5.5  -3.7    447      0.415    0.49/0/0.51
   same cuts, model's OWN probability @ DraftKings    21   -2.4 -11.19 -66.5..+44.1  -50.0  24.1     21      0.468    0.62/0/0.38
same cuts, model's OWN probability @ best bettable    47   -6.0 -12.66 -49.7..+24.4  -19.1  -6.5     47      0.467    0.74/0/0.26

### Neighbourhood: bet any outcome whose raw model EV at DraftKings clears the cut

 raw EV>=  bets  units    roi           ci  early  late
     0.00   859  -41.8  -4.86  -14.9..+5.1    0.3 -10.0
     0.02   665  -65.0  -9.77  -20.9..+1.3   -4.5 -15.0
     0.05   441  -20.9  -4.73  -18.7..+9.3    4.3 -13.7
     0.10   230  -11.5  -4.98 -24.9..+15.0   -3.4  -6.6
     0.15   105   -8.6  -8.14 -37.6..+21.3   -4.0 -12.2
     0.20    47   -9.5 -20.32 -60.8..+20.2  -13.7 -26.7
     0.30    13    0.1   0.77 -88.7..+90.3    NaN   NaN

### Blind baselines at DraftKings

      blind  bets  units    roi          ci
always away  1352 -114.8  -8.49 -15.3..-1.7
always draw  1352  114.5   8.47 -1.5..+18.4
always home  1352 -202.1 -14.95 -20.7..-9.2

### nhl_moneyline: what the model says, what the correction says, what happened (every side of every game)

                sides  model_says  corrected_says  actually_won
band
[0.0, 0.4)        366       0.357           0.418         0.363
[0.4, 0.435)      286       0.418           0.482         0.510
[0.435, 0.485)    557       0.461           0.526         0.510
[0.485, 0.5)      143       0.493           0.557         0.517
[0.5, 0.515)      143       0.507           0.443         0.483
[0.515, 0.565)    557       0.539           0.474         0.490
[0.565, 0.6)      286       0.582           0.518         0.490
[0.6, 0.65)       237       0.621           0.558         0.612
[0.65, 1.0)       129       0.684           0.625         0.682

### nhl_moneyline_regulation: outcomes under the 0.40 probability floor on the model's own number that the correction lifts over it

669 outcomes | model says 0.368 | corrected says 0.430 | actually happened 0.365
```

## Read, the live artifacts

- **Neither live model made money on the season it had not seen.** The
  moneyline model's log loss is 0.6884 against DraftKings' no-vig 0.6836; every
  row of its raw-edge grid is negative (-0.3% to -19.5% on 31-587 bets) and
  every probability-floor row is negative (-0.8% to -16.9%). The regulation
  model loses at every EV cut with a usable sample (-4.7% to -20.3%). The one
  interval that excludes zero is a losing one. **No cut clears.**
- **Closing-line value is positive, and at the loose cuts it is no better than
  betting blind.** Measured as round three measured it (Pinnacle's last
  pre-game no-vig probability minus its first, on the side taken), the edge
  grid beats the close 55-60% of the time at cuts 0.02-0.05 (+0.3 to +0.5
  points). Blindly taking the away side beat it 57.5% (+0.39) on the same
  games and blind underdogs 52.7% (+0.21): the line moved toward road teams
  this season, and two thirds or more of these bets are underdogs. Only at
  0.06 and above does the grid clear those bars (66-77%, +0.7 to +0.9), on
  188 bets or fewer. Not evidence the model reads the market.
- **As it runs today the moneyline model bets only sides it believes are
  underdogs.** All 30 bets at DraftKings are on a side the model itself has
  under 50%, and all 41 at the best book are at plus money. The mechanism is
  the correction:
  it is a single downward shift fitted on other models' favoured sides, applied
  as `1 - f(1 - p)` below 50%, so a side the model has at 49.3% is decided at
  55.7% and its opponent at 44.3%. On this season those sides won 51.7% (143
  sides); the model's own 49.3% was the nearer number. +21.0% on 30 bets with an
  interval of -20..+62 is not a result, and blind underdogs made +2.9% on the
  same 1,352 games.
- **For the regulation model the correction is simply wrong.** All three
  outcomes sit under 50%, so all three are raised: the corrected probabilities
  of one game sum to 1.144 on average. 669 outcomes are lifted over the 0.40
  floor that would not otherwise clear it; the model said 36.8%, the correction
  said 43.0%, 36.5% happened. As it runs it placed 300 bets at DraftKings for
  -13.1% (447 at the best book, -4.6%), none of them on the draw, in a season
  where blind draws made +8.5%. On its own probability it bets 21 times.
- **In the middle of its range the moneyline model does not separate teams at
  all.** Sides it has at 40-43.5% won 51.0%; sides it has at 56.5-60% won 49.0%.
  Only the tails hold (under 40%: 36.3%; 60-65%: 61.2%; 65%+: 68.2%).

## What the first week of 2026-27 shows about the inputs

`features.feature_engine.build_features_for_game` on the 26 games dated
2026-09-29 -> 10-03 (script-free: the function, the live artifact, one call per
game):

- **Before a team's first game its row is LAST SEASON'S FINAL totals**, and
  goal difference is a running total. The model was fed goal-difference gaps of
  +97, +112 and +106 on opening night and +133 the night after. In the first
  fourteen days of 2025-26 the rows of that season's frame run -23 to +23; its
  earliest game is dated 2025-10-11 and 42 rows were dropped for null inputs,
  the way all 8 of this season's finished games drop today (null home / away
  scoring splits). So the model has not seen a row like this. Three of the five
  opening-night games were stored at 0.697 or higher for the home side (0.708,
  0.755, 0.697); 1.9% of holdout games reach 0.70. "CAR ML" (stored at 0.7546,
  0.7002 when rebuilt today) was one of them.
- **After one game the goals columns are the raw one-game numbers**, compared
  against an opponent still on last season's totals: goals-per-game gaps of
  +2.84 and -3.45, win percentages of 0.00 and 1.00. Shot share, power play and
  penalty kill are blended toward last season (`data/nhl_asof.py`); goals for,
  goals against, goal difference and wins are not.
- **28 of the 32 probable-starter rows since opening night are the league
  average with no player id** (`nhl_goalie_stats`, game_date >= 2026-09-29:
  save% .8959, GAA 2.863, GSAA 0.0 for Vasilevskiy, Sorokin, Saros, Swayman...).
  The starter's name comes from ESPN and is matched to an id only through THIS
  season's summary (`nhl_stats_ingestor._build_goalie_rows`), which is empty in
  week one, so a returning starter is rated as a debutant until he has played.
  The per-game log that holds his last season is never consulted for the id.

---

# Underdogs against favourites, six seasons of stored prices (2026-10-01)

mike, on a proposal to stop the probability correction raising underdog
probabilities: *"Underdog +money bets are more important that favorites. this
has been proven, look in the internets."* Two things were done: the published
record was searched, and the seasons it does not cover were measured here.
`python -m scripts.nhl_underdog_grid` — no model, every game 2020-21 -> 2025-26
with a DraftKings pre-game moneyline in the bought history, one unit a side.
`open` / `close` are DraftKings' first and last pre-game quotes; `best` is the
best open price among the books a member can bet.

```
7,624 games with a DraftKings pre-game moneyline and a favourite, seasons 2020-21 -> 2025-26; per season {2021: 878, 2022: 1340, 2023: 1356, 2024: 1358, 2025: 1356, 2026: 1336}; bettable books ['draftkings', 'fanduel', 'betmgm', 'williamhill_us', 'fanatics', 'betrivers', 'hardrockbet', 'betparx']

### All six seasons, blind

     side priced at  bets  units   roi         ci  clv_pts  beat_close  win%
 underdog      open  7624 -528.8 -6.94 -9.6..-4.3    -0.21        43.3  39.2
 underdog     close  7624 -481.1 -6.31 -9.0..-3.6    -0.21        43.3  39.2
 underdog      best  7624 -330.3 -4.33 -7.1..-1.6    -0.21        43.3  39.2
favourite      open  7624 -169.4 -2.22 -4.0..-0.4     0.21        55.3  60.8
favourite     close  7624 -205.9 -2.70 -4.5..-0.9     0.21        55.3  60.8
favourite      best  7624  -35.5 -0.47 -2.3..+1.4     0.21        55.3  60.8

### By season, DraftKings open

 season      side priced at  bets  units    roi          ci  clv_pts  beat_close  win%
2020-21  underdog      open   878  -86.6  -9.86 -17.6..-2.2    -0.32        42.7  38.5
2020-21 favourite      open   878   -5.3  -0.60  -5.9..+4.7     0.32        55.9  61.5
2021-22  underdog      open  1340 -192.7 -14.38 -20.8..-7.9    -0.38        40.7  35.0
2021-22 favourite      open  1340   46.6   3.48  -0.7..+7.6     0.38        58.1  65.0
2022-23  underdog      open  1356  -84.3  -6.22 -12.8..+0.3    -0.34        40.0  38.3
2022-23 favourite      open  1356  -26.1  -1.93  -6.1..+2.3     0.34        58.4  61.7
2023-24  underdog      open  1358 -112.5  -8.28 -14.6..-2.0    -0.22        42.3  38.7
2023-24 favourite      open  1358  -22.6  -1.67  -5.9..+2.6     0.22        56.3  61.3
2024-25  underdog      open  1356  -81.2  -5.99 -12.3..+0.3    -0.24        42.0  39.8
2024-25 favourite      open  1356  -45.7  -3.37  -7.6..+0.9     0.24        57.0  60.2
2025-26  underdog      open  1336   28.5   2.13  -4.1..+8.3     0.19        52.2  44.7
2025-26 favourite      open  1336 -116.3  -8.70 -13.1..-4.3    -0.19        46.2  55.3

### By season, best bettable open price

 season      side priced at  bets  units    roi          ci  clv_pts  beat_close  win%
2020-21  underdog      best   878  -48.8  -5.56 -13.7..+2.6    -0.32        42.7  38.5
2020-21 favourite      best   878    9.5   1.08  -4.3..+6.4     0.32        55.9  61.5
2021-22  underdog      best  1340 -148.5 -11.09 -17.8..-4.3    -0.38        40.7  35.0
2021-22 favourite      best  1340   71.8   5.36  +1.1..+9.6     0.38        58.1  65.0
2022-23  underdog      best  1356  -62.7  -4.62 -11.3..+2.0    -0.34        40.0  38.3
2022-23 favourite      best  1356   -8.1  -0.60  -4.8..+3.6     0.34        58.4  61.7
2023-24  underdog      best  1358  -87.7  -6.46 -12.9..-0.0    -0.22        42.3  38.7
2023-24 favourite      best  1358    2.1   0.15  -4.1..+4.5     0.22        56.3  61.3
2024-25  underdog      best  1356  -45.8  -3.38  -9.9..+3.1    -0.24        42.0  39.8
2024-25 favourite      best  1356  -20.6  -1.52  -5.8..+2.8     0.24        57.0  60.2
2025-26  underdog      best  1336   63.2   4.73 -1.6..+11.1     0.19        52.2  44.7
2025-26 favourite      best  1336  -90.1  -6.75 -11.3..-2.2    -0.19        46.2  55.3

### Underdogs by DraftKings opening price, with each season's return (bets)

underdog priced priced at  bets  units   roi          ci  clv_pts  beat_close  win%      2020-21      2021-22      2022-23      2023-24      2024-25     2025-26
   +100 to +119      open  1974  -89.6 -4.54  -9.1..+0.0    -0.08        45.7  46.0 -16.2% (250) -11.2% (350)  -8.1% (302)  -6.7% (347)  +2.1% (317) +7.5% (408)
   +120 to +149      open  2331 -152.6 -6.55 -11.2..-1.9    -0.24        44.3  40.4  -5.5% (241) -17.8% (366)  -3.3% (405)  -5.9% (395)  -6.3% (475) -1.6% (449)
   +150 to +199      open  1674 -147.0 -8.78 -14.9..-2.7    -0.24        42.4  33.9 -14.0% (210) -18.3% (320) -10.5% (313)  -2.7% (306)  -9.9% (284) +4.3% (241)
 +200 or longer      open  1016  -86.6 -8.52 -17.9..+0.8    -0.46        35.5  27.1   -9.2% (88)  -7.0% (232)  -1.0% (245) -21.1% (191) -10.8% (173)  -0.9% (87)

### Home and road, DraftKings open

          side priced at  bets  units   roi          ci  clv_pts  beat_close  win%
 home underdog      open  2726 -200.7 -7.36 -11.7..-3.0    -0.38        40.4  40.2
home favourite      open  4898 -133.2 -2.72  -4.9..-0.5     0.12        53.7  61.4
 road underdog      open  4898 -328.1 -6.70 -10.1..-3.3    -0.12        45.0  38.6
road favourite      open  2726  -36.2 -1.33  -4.4..+1.7     0.38        58.2  59.8

### Line shopping: the best bettable open price against Pinnacle's no-vig open

                                      side  games  share where best price beats Pinnacle's fair price  mean EV at best price, %   bets  units  roi          ci  clv_pts  beat_close
                                  underdog 7623.0                                                22.7                     -1.90    NaN    NaN  NaN         NaN      NaN         NaN
 underdog, bet when EV vs Pinnacle >= 0.00    NaN                                                 NaN                       NaN 1743.0   16.4 0.94  -5.1..+7.0    -0.20        44.8
 underdog, bet when EV vs Pinnacle >= 0.02    NaN                                                 NaN                       NaN  900.0    8.9 0.99  -7.6..+9.6    -0.15        47.8
 underdog, bet when EV vs Pinnacle >= 0.04    NaN                                                 NaN                       NaN  511.0   29.5 5.77 -6.0..+17.6    -0.00        50.3
                                 favourite 7623.0                                                16.6                     -1.93    NaN    NaN  NaN         NaN      NaN         NaN
favourite, bet when EV vs Pinnacle >= 0.00    NaN                                                 NaN                       NaN 1267.0   38.9 3.07  -1.5..+7.6     0.29        58.5
favourite, bet when EV vs Pinnacle >= 0.02    NaN                                                 NaN                       NaN  525.0   39.1 7.44 +0.4..+14.5     0.43        61.9
favourite, bet when EV vs Pinnacle >= 0.04    NaN                                                 NaN                       NaN  226.0   13.7 6.05 -4.9..+17.0     0.63        63.7

### Either side, bet at the best bettable open price when it beats Pinnacle's no-vig open by the cut

 EV vs Pinnacle >=  bets  units   roi          ci  clv_pts  beat_close  dog share  early  late     2020-21     2021-22      2022-23     2023-24      2024-25      2025-26
              0.00  3010   55.3  1.84  -2.1..+5.8     0.01        50.5       0.58    0.4   3.3 -1.6% (455) -0.1% (674)  +4.0% (392) -3.4% (433)  +0.2% (548) +12.1% (508)
              0.01  2064   85.7  4.15  -0.8..+9.1     0.03        51.7       0.61    3.2   5.1 -3.2% (307) +3.3% (496) +12.5% (236) -5.4% (284)  +5.6% (399) +12.5% (342)
              0.02  1425   47.9  3.36  -2.7..+9.4     0.06        53.0       0.63    3.3   3.4 +0.1% (201) +4.1% (363)  +6.9% (149) -5.3% (183)  +2.1% (287) +10.8% (242)
              0.03  1034   42.2  4.08 -3.2..+11.3     0.12        54.2       0.66    4.1   4.1 +7.6% (150) +2.8% (283)  +3.1% (100) -0.6% (116)  +6.2% (207)  +4.2% (178)
              0.04   737   43.2  5.86 -3.0..+14.7     0.19        54.4       0.69    5.4   6.4 +14.9% (98) +1.1% (225)   +6.3% (60)  -3.7% (84) +11.2% (146)  +7.3% (124)
              0.06   370   60.2 16.28 +2.9..+29.6     0.16        53.2       0.76   14.4  18.1 +26.7% (43) +9.1% (126)         (28) +17.4% (37)  +24.2% (69)   +8.1% (67)

### The 0.02 cut, by the book whose price was taken

book with the best price  bets  units    roi           ci  clv_pts  beat_close
               betrivers   499   38.7   7.75  -1.8..+17.3     0.43        58.9
                 fanduel   370  -11.7  -3.15  -16.2..+9.9    -0.46        45.1
              draftkings   220    4.1   1.86 -12.8..+16.5     0.42        54.1
                  betmgm   150   14.9   9.95  -7.5..+27.4     0.38        62.0
          williamhill_us   106    5.1   4.82 -20.3..+30.0    -1.24        34.9
             hardrockbet    57   -8.1 -14.15 -41.0..+12.7     0.33        56.1
                fanatics    23    NaN    NaN          NaN      NaN         NaN

DraftKings' moneyline hold at the open on these games: 4.22%
```

## Read, underdogs

- **Blind underdogs lost in five of the last six seasons, at every price.**
  -6.9% at DraftKings' open over 7,624 games against -2.2% for favourites;
  -4.3% against -0.5% at the best bettable price. By season the underdog side
  ran -9.9%, -14.4%, -6.2%, -8.3%, -6.0%, then **+2.1% in 2025-26** (+4.7% at
  the best price), the one season favourites lost more (-8.7%).
- **No price band is positive over the six seasons** (-4.5% to -8.8%). The
  shortest underdogs, +100 to +119, improved every single season: -16.2%,
  -11.2%, -8.1%, -6.7%, +2.1%, +7.5% on 250-408 bets a season. Six points in a
  row is a pattern worth watching and not yet a rule: only the last two are
  positive, on 317 and 408 bets.
- **Home or road makes no difference to the underdog** (-7.4% home, -6.7%
  road).
- **CORRECTED 2026-10-01, the same evening: the "best price against Pinnacle"
  grid below was an artifact, and there is no moneyline rule in it.** The table
  compared each book's FIRST stored quote with Pinnacle's FIRST stored quote.
  Those are not the same moment: a game is first seen in the previous night's
  snapshots at some books and not until the next day at others
  (`odds.created_at` groups the rows of one snapshot; `snapshot_at` is each
  book's own last update). A soft book's stale number against a later Pinnacle
  number is a bet nobody could place. With the two quotes forced within five
  minutes of each other (`scripts/nhl_moneyline_market_lab.py`, next section)
  the rule finds 96 bets in six seasons at a 2% cut and no edge. The `best`
  rows of the blind tables above mix moments the same way and are an upper
  bound on what a bettor got; the DraftKings `open` and `close` rows are one
  book and are unaffected. What was written here before, kept so the retraction
  can be read against it:
- ~~Where the underdog claim does hold is on price, not on side.~~ The best
  bettable underdog price beats Pinnacle's no-vig price in 22.7% of games
  against 16.6% for favourites, so books disagree more on the underdog. Betting
  EITHER side at the best price when it beats Pinnacle's fair price is positive
  at every cut: +1.8% (3,010 bets) at 0.00, +3.4% (1,425) at 0.02, +5.9% (737)
  at 0.04, +16.3% (370) at 0.06; both halves positive at every cut; five of six
  seasons positive at 0.02-0.04; 58-76% of the bets are underdogs; no one book
  carries it. **Against it:** every interval below 0.06 spans zero, 2023-24 is
  negative at every cut up to 0.04, and closing-line value is barely above zero
  (50-54% beat Pinnacle's close). A candidate — the same shape as
  `nfl_opener_spread` — not a model.

## The published record (web search, 2026-10-01; sources listed in that day's session entry)

- **The claim was true on 1990s prices.** Woodland & Woodland 2001 found NHL
  underdogs over-returned in 1990-96, and Gandar, Zuber & Johnson 2004
  confirmed it after correcting the commission arithmetic.
- **The same authors found it gone.** Woodland & Woodland 2011, ten later
  seasons: "the bias is sustained for the first three seasons but disappears in
  the last seven seasons as the market converges to efficiency".
- **Every unfiltered modern figure found has favourites level or ahead**:
  Action Network, 15 seasons from 2005, underdogs -2.4% and favourites -1.6%;
  2017-18, favourites +1.6% and underdogs down nearly 100 units over 1,268
  games; 2021-22 through 652 games, favourites +4.8% and underdogs -19%.
- **Underdogs come out ahead only in filtered cuts from a vendor's own
  database**: road underdogs +105 to +200 with 35% or less of the bets, +5.1%
  over 2005-2012 (Sports Insights); playoff underdogs of +120 or longer, +3.1%
  over 2012-2025 and then -22.1 units in 2025 (VSiN).
- **Nothing published covers 2022-23 onward at real prices**, and nothing
  published measures line shopping by side. The tables above are the only
  numbers for either. Several pages would not load (Lahtinen 2019, the full
  Woodland papers, Paul & Weinbach 2012); what is quoted from them is the
  abstract or a search summary.

---

# The early weeks, backtested (2026-10-01)

Proposed to mike: hold NHL picks until both teams have played ten games,
because the first week's inputs are outside anything the models trained on.
His answer: *"no, this is fucking why we have back testing and seasons worth of
data frmo out data sources."* So the early weeks were backtested, and the
alternative input design was built and tested against the one that is live.
**He was right, and the proposal was wrong: over five seasons the live inputs
do no worse in the early weeks than in the rest of the season, and the
alternative is not an improvement. Nothing was switched.**

`python -m scripts.nhl_early_season_blend` (and `--sweep`, `--first-games`).
Walk-forward with fixed parameters, test seasons 2021-22 -> 2025-26, each fit
on every earlier season from 2018-19. OLD is the live feature list. BLENDED is
`NHL_H2H_FEATURES_BLENDED`: goals for and against, the home / road scoring
splits and a points rate (games not lost in regulation), each
`(n * this season + 25 * last season) / (n + 25)` through
`data.nhl_asof.TeamBook.inputs`, with the running goal-difference total
removed. Three windows: EARLY (a team under 10 games played), FIRST GAMES, and
the REST. **"First games" means the 225 games the old list drops from
training** — the home team has not yet played at home, or the road team on the
road; about 45 a season, of which a team's very first game is a subset.

```
games 2018-19 -> 2025-26: old list 10,034, blended list 10,367 (333 the old list drops for null inputs)
test seasons 2021-22 -> 2025-26: 6,992 games; 225 first games only the blended list can score, 615 other early-season games, 6152 the rest; 6,745 with a DraftKings price

### Accuracy by window (walk-forward, fixed parameters)

                    window  games  home rate  log loss blended  AUC blended  log loss DraftKings  AUC DraftKings  log loss old  AUC old
first games (blended only)    225      0.560            0.6786        0.595               0.6500           0.657           NaN      NaN
  early season, both lists    615      0.535            0.6983        0.577               0.6727           0.609        0.6992    0.578
            rest of season   6152      0.536            0.6864        0.594               0.6596           0.642        0.6828    0.602
all games both lists score   6767      0.536            0.6875        0.593               0.6608           0.639        0.6843    0.600

### Units at DraftKings' first pre-game price, by window

 inputs                     window  edge>=  bets  units   roi           ci
blended   early season, both lists    0.02   409  -17.5 -4.28  -14.1..+5.5
    old   early season, both lists    0.02   430   -2.4 -0.56  -10.4..+9.3
blended first games (blended only)    0.02   150  -11.1 -7.43  -23.0..+8.1
blended             rest of season    0.02  4008 -245.4 -6.12   -9.3..-2.9
    old             rest of season    0.02  4060 -120.0 -2.96   -6.1..+0.2
blended   early season, both lists    0.04   334  -20.7 -6.20  -17.0..+4.6
    old   early season, both lists    0.04   372    0.3  0.07 -10.6..+10.7
blended first games (blended only)    0.04   122   -3.3 -2.74 -20.4..+14.9
blended             rest of season    0.04  3199 -177.0 -5.53   -9.2..-1.9
    old             rest of season    0.04  3235 -122.7 -3.79   -7.4..-0.2
blended   early season, both lists    0.06   264  -15.1 -5.72  -17.8..+6.3
    old   early season, both lists    0.06   288  -14.1 -4.90  -17.0..+7.2
blended first games (blended only)    0.06    84   -3.5 -4.21 -25.8..+17.4
blended             rest of season    0.06  2451 -133.2 -5.43   -9.6..-1.2
    old             rest of season    0.06  2480  -91.9 -3.70   -7.8..+0.4

### The early window season by season

 season  early + first games  log loss old  log loss blended (same games)  log loss blended (all)
2021-22                  169        0.6973                         0.6908                  0.6905
2022-23                  169        0.6995                         0.7517                  0.7321
2023-24                  166        0.7304                         0.6801                  0.6681
2024-25                  169        0.6708                         0.6652                  0.6756
2025-26                  167        0.6988                         0.7025                  0.6982

first games: the blended model's home-win probability ranges 0.262..0.870 (mean 0.572); share at 0.70 or higher 0.240

225 first games, 2021-22 -> 2025-26; 216 with a DraftKings price; rows with a missing old input: 143
goal-difference gap fed to the old model: {0.5: 8.0, 0.9: 79.0, 1.0: 178.0} (absolute, median / 90th / max)

### First games of a season: accuracy

                                      model  games  log loss   AUC  share at 0.70+ or 0.30-
old list, as production scores a first game    225    0.6650 0.628                    0.271
                               blended list    225    0.6786 0.595                    0.258
                          DraftKings no-vig    216    0.6500 0.657                    0.088

### First games of a season: units at DraftKings' first pre-game price

                                      model  edge>=  bets  units   roi           ci
old list, as production scores a first game    0.02   169    4.3  2.53 -12.4..+17.4
                               blended list    0.02   150  -11.1 -7.43  -23.0..+8.1
old list, as production scores a first game    0.04   145    3.8  2.60 -13.7..+18.9
                               blended list    0.04   122   -3.3 -2.74 -20.4..+14.9
old list, as production scores a first game    0.06   112   13.7 12.19  -6.5..+30.9
                               blended list    0.06    84   -3.5 -4.21 -25.8..+17.4


### Log loss by how many games of last season the goals and results columns carry

games of last season carried  first games  early   rest  all both score  AUC all both score  share of first games at 0.70+
                           3       0.6813 0.6954 0.6872          0.6879              0.5912                          0.204
                           5       0.6760 0.6936 0.6858          0.6866              0.5932                          0.191
                          10       0.6527 0.6904 0.6844          0.6849              0.5964                          0.191
                          25       0.6786 0.6983 0.6864          0.6875              0.5925                          0.240
                          50       0.6773 0.6884 0.6834          0.6838              0.5992                          0.200
              old list (raw)          NaN 0.6992 0.6828          0.6843              0.5999                            NaN
```

## Read, the early weeks

- **The early weeks are not a worse time for the live inputs.** In units at
  DraftKings the old list returns -0.6% / +0.1% / -4.9% in the early window
  (288-430 bets) against -3.0% / -3.8% / -3.7% over the rest of the season
  (2,480-4,060 bets). Its log loss is worse early (0.6992 against 0.6828), and
  so is DraftKings' own (0.6727 against 0.6596): early games are harder for
  everyone, not specially hard for this model. A hold was not supported.
- **On the games the old list never trained on, scoring them the way
  production does is the better of the two.** Last season's final row standing
  in: log loss 0.6650, AUC 0.628, +2.5% to +12.2% on 112-169 bets (every
  interval spans zero). Blended: 0.6786, 0.595, -2.7% to -7.4%. DraftKings:
  0.6500. The inputs on those games ARE outside the training range (median
  goal-difference gap 8, 90th percentile 79, largest 178; 27% of them priced
  at 70% or 30% and beyond, against 9% for DraftKings) and it did not cost
  accuracy. 225 games; a replay of the scoring path on rows the rebuild wrote.
- **The blended list is not better anywhere it can be compared.** Same games:
  log loss 0.6875 against 0.6843, AUC 0.593 against 0.600; units worse in both
  windows at every cut (rest of season -6.1% / -5.5% / -5.4%).
- **How much of last season to carry makes no difference.** 3, 5, 10, 25 or 50
  games: 0.6838 to 0.6879 over the games both lists score, in no order. The
  spread between refits (first games 0.6527 to 0.6813 with an identical input
  on those rows) is the noise floor of this comparison. No value was chosen
  from it; 25 matches the shot and special-teams rates.
- **Both models were retrained on the blended list anyway** (`--no-register`,
  Optuna 100 trials, train 2018-19 -> 2024-25) and graded on 2025-26 with
  `scripts/nhl_live_artifact_grade.py --artifact`:

  | 2025-26, at DraftKings | live | retrained on the blended list |
  |---|---|---|
  | moneyline log loss (DraftKings no-vig) | 0.6884 (0.6836), 1,352 games | 0.6906 (0.6828), 1,394 games |
  | moneyline, raw edge >= 0.02 | 587 bets, -0.5% | 610 bets, -10.2% (-18.9..-1.5) |
  | moneyline, raw edge >= 0.04 | 341 bets, -0.3% | 308 bets, -13.0% (-25.4..-0.6) |
  | moneyline, raw edge >= 0.06 | 188 bets, -4.1% | 137 bets, -20.5% (-39.0..-2.0) |
  | regulation log loss | 1.0772 | 1.0783 |
  | regulation, raw EV >= 0.05 | 441 bets, -4.7% | 497 bets, -12.9% (-25.6..-0.1) |
  | regulation, as it runs today | 300 bets, -39.2 units | 320 bets, -55.8 units |

  Worse on every row with a sample. (The candidate column is from the run
  before the script's sums were made order-independent, so its unit figures are
  good to 0.1; a re-run was cancelled twice by the database's statement timeout
  that evening and was not forced.) The candidates were not registered and are
  not in the repo (`models/saved/_baseline/` is ignored); the live artifacts
  and `FEATURE_MAP` are unchanged, and the blended columns are computed on the
  training path only.
- **What stays true from the first write-up, and what does not.** True: before
  a team's first game the scoring path feeds last season's running totals, and
  the live path's home / road scoring split is not the training path's
  (`nhl_stats_ingestor._home_away_goals` reaches back to 1 October of the
  previous calendar year, so it spans two seasons until New Year and one after;
  training uses this season only). Not supported by results: that either one
  makes the early weeks a bad time to bet this model.

---

# The moneyline "best price against Pinnacle" rule, stress-tested: it is not a rule (2026-10-01)

`python -m scripts.nhl_moneyline_market_lab`. The same rule as the grid above
— bet the better-EV side at the best price among the bettable books when it
beats Pinnacle's no-vig probability — with the soft quote and Pinnacle's
required to be within five minutes of each other, decided at each book's first
stored quote ("open") and at its last ("close"). `EV at Pin close` prices the
bet against where Pinnacle closed.

```
7,945 games 2020-21 -> 2025-26; quotes: 122,826 (game, book, open/close) rows; bettable books ['draftkings', 'fanduel', 'betmgm', 'williamhill_us', 'fanatics', 'betrivers', 'hardrockbet', 'betparx']; sharp pinnacle
games with a Pinnacle quote and a simultaneous bettable quote: open 6,142, close 7,887; median bettable books per game at the open 4

### Decided at the OPEN, best bettable price

rule  EV>=  bets  units   roi           ci  early  late  dogs  EV at Pin close  still +EV at close      2020-21     2021-22      2022-23     2023-24     2024-25     2025-26
open  0.00   595  -10.0 -1.69  -11.5..+8.1   -1.6  -1.8  0.70             0.49                51.8 -13.9% (113) -1.3% (149) +17.2% (116) -15.6% (94) -20.0% (80) +42.6% (43)
open  0.01   255   -2.3 -0.88 -17.0..+15.3  -16.4  14.5  0.78             0.95                53.3  -22.4% (54) -13.2% (74)  +47.0% (50) -40.9% (31)  -3.7% (33)        (13)
open  0.02    96    2.4  2.46 -26.6..+31.5    2.8   2.1  0.86             1.98                62.5         (27) -12.6% (39)         (13)        (10)         (6)         (1)
open  0.03    50   -1.8 -3.53 -46.0..+38.9  -12.9   5.9  0.92             2.57                66.0         (15)        (25)          (5)         (5)         (0)         (0)
open  0.04    28    NaN   NaN          NaN    NaN   NaN   NaN              NaN                 NaN          NaN         NaN          NaN         NaN         NaN         NaN
open  0.05    13    NaN   NaN          NaN    NaN   NaN   NaN              NaN                 NaN          NaN         NaN          NaN         NaN         NaN         NaN
open  0.06     8    NaN   NaN          NaN    NaN   NaN   NaN              NaN                 NaN          NaN         NaN          NaN         NaN         NaN         NaN
open  0.08     3    NaN   NaN          NaN    NaN   NaN   NaN              NaN                 NaN          NaN         NaN          NaN         NaN         NaN         NaN

### Decided at the CLOSE, best bettable price

 rule  EV>=  bets  units   roi           ci  early  late  dogs  EV at Pin close  still +EV at close     2020-21      2021-22     2022-23     2023-24     2024-25     2025-26
close  0.00  1266  -17.7 -1.40   -8.1..+5.3   -5.7   2.9  0.75             1.40                99.3 -3.3% (323)  -9.0% (279) +0.0% (163) -0.7% (145) +7.9% (172) +2.9% (184)
close  0.01   571    5.4  0.95  -9.9..+11.8   -8.2  10.0  0.86             2.54               100.0 -3.6% (200) -10.6% (116)  -9.8% (63)  +7.5% (48) +16.8% (66) +20.9% (78)
close  0.02   276   28.5 10.31  -6.2..+26.9   -2.2  22.8  0.93             3.72               100.0 +7.1% (117)   -4.9% (56)        (24)        (18)        (29) +14.3% (32)
close  0.03   149   12.5  8.41 -14.7..+31.5   11.4   5.5  0.94             4.82               100.0 +11.5% (79)  -14.1% (32)        (10)         (4)         (9)        (15)
close  0.04    77   -0.1 -0.08 -33.6..+33.5   11.0 -10.8  0.97             6.14               100.0  +0.5% (48)         (18)         (6)         (2)         (2)         (1)
close  0.05    41    1.5  3.71 -44.8..+52.2    3.3   4.0  1.00             7.62               100.0        (27)         (11)         (1)         (1)         (0)         (1)
close  0.06    27    NaN   NaN          NaN    NaN   NaN   NaN              NaN                 NaN         NaN          NaN         NaN         NaN         NaN         NaN
close  0.08    14    NaN   NaN          NaN    NaN   NaN   NaN              NaN                 NaN         NaN          NaN         NaN         NaN         NaN         NaN

### Decided at the open, quotes NOT required to be simultaneous

         rule  EV>=  bets  units   roi          ci  early  late  dogs  EV at Pin close  still +EV at close
open, any gap  0.00  3047   66.1  2.17  -1.8..+6.1   -0.0   4.4  0.57             2.70                68.9
open, any gap  0.01  2119   91.8  4.33  -0.5..+9.2    3.5   5.1  0.60             3.80                75.9
open, any gap  0.02  1480   54.9  3.71  -2.2..+9.6    4.3   3.1  0.62             4.92                80.6
open, any gap  0.03  1075   52.8  4.91 -2.1..+12.0    4.2   5.6  0.66             5.97                84.0
open, any gap  0.04   764   50.3  6.59 -2.1..+15.2    4.7   8.5  0.69             7.16                86.6
open, any gap  0.05   543   59.2 10.91 +0.4..+21.4   13.6   8.2  0.72             8.30                88.6
open, any gap  0.06   384   60.2 15.69 +2.7..+28.7   13.5  17.9  0.76             9.27                89.8
open, any gap  0.08   190   37.9 19.93 +0.6..+39.2   13.1  26.7  0.78            12.34                95.3
```

- **With simultaneous quotes there is nothing at the open**: -1.7% on 595
  bets at any positive EV, -0.9% on 255 at 1%, +2.5% on 96 at 2%, -3.5% on 50
  at 3%. When the books are read at the same moment they agree with Pinnacle.
- **At the close it is one cell, not a plateau**: +10.3% on 276 at 2%
  (interval -6..+27), with -1.4% at 0%, +0.9% at 1% and -0.1% at 4% around it,
  and the two seasons with 30 or more bets going opposite ways.
- **The third table is the artifact itself**, reproduced by dropping the
  five-minute requirement: +2.2% to +19.9%, every cut positive. That is what
  the earlier section reported.
- DraftKings alone, each book left out in turn, and the split by side are in
  the script's output; none has a sample that says anything (96 bets or fewer).
- **Verdict: no NHL moneyline rule.** The game lines are where the published
  record said they would be — efficient. The lesson for every sharp-against-soft
  backtest in this repo: the two quotes must come from one snapshot.

---

# nhl_prop_blocked_shots: the model that went to production (2026-10-01)

mike: *"just build profitable models."* Of everything in this document, one
result has intervals clear of zero across three seasons and was confirmed on
seasons bought after it was picked out: blocked-shot unders at DraftKings. It
is now `models/nhl_prop_blocked_shots.py` — the lab's Poisson model, moved into
one module that the backtest, the fit and tonight's card all call — and this is
that module's own backtest: `python -m scripts.nhl_prop_blocked_shots_backtest`.
Walk-forward (each season scored by a model fitted on earlier seasons only),
DraftKings' price from the one pre-game snapshot a game, one bet per
player-game.

```
2023-24: fit on 159,628 skater-games; DraftKings priced 4,874 player-games, 4,092 matched to a prediction
2024-25: fit on 205,922 skater-games; DraftKings priced 1,949 player-games, 1,633 matched to a prediction
2025-26: fit on 252,165 skater-games; DraftKings priced 5,405 player-games, 4,699 matched to a prediction

10,424 priced player-games; under prices: median 100, shorter than -200: 0.1%, shorter than -140: 17.8%; lines: {1.5: 8237, 2.5: 2174, 3.5: 7, 0.5: 6}
blind always over: {'bets': 10415, 'units': -1011.4, 'roi': -9.71, 'ci': '-11.5..-7.9'}
blind always under: {'bets': 10418, 'units': -242.1, 'roi': -2.32, 'ci': '-4.2..-0.4'}

### The model's OWN probability, no price floor (the lab's rule)

 EV>=  bets  units  roi          ci  early  late  unders  win%  median price      2023-24      2024-25      2025-26
 0.00  6584   91.1 1.38  -1.0..+3.8    2.0   0.8    0.94  52.3           100 +0.3% (2789) +5.2% (1207) +0.8% (2588)
 0.03  4904  189.6 3.87  +1.1..+6.6    4.1   3.7    0.97  53.3           100 +3.4% (2170) +5.8% (1005) +3.4% (1729)
 0.06  3470  168.2 4.85  +1.5..+8.2    3.2   6.5    0.99  53.5           100 +3.3% (1609)  +5.3% (796) +7.0% (1065)
 0.08  2704  137.7 5.09  +1.3..+8.9    4.4   5.8    0.99  53.3           105 +4.7% (1274)  +3.7% (658)  +6.9% (772)
 0.10  2056  126.3 6.14 +1.8..+10.5    6.0   6.3    1.00  53.5           105  +6.6% (973)  +2.4% (542)  +9.1% (541)
 0.12  1547  105.6 6.83 +1.7..+11.9    6.8   6.9    1.00  53.4           105  +6.9% (748)  +4.2% (422)  +9.6% (377)
 0.15   946   61.0 6.45 -0.1..+13.0    4.0   8.9    1.00  52.9           110  +4.1% (459)  +3.8% (295) +16.2% (192)

### The model's OWN probability, by price floor

 EV>=  floor  bets  units  roi          ci  early  late  unders  win%  median price      2023-24      2024-25      2025-26
 0.03    NaN  4904  189.6 3.87  +1.1..+6.6    4.1   3.7    0.97  53.3           100 +3.4% (2170) +5.8% (1005) +3.4% (1729)
 0.03 -250.0  4904  189.6 3.87  +1.1..+6.6    4.1   3.7    0.97  53.3           100 +3.4% (2170) +5.8% (1005) +3.4% (1729)
 0.03 -200.0  4900  189.2 3.86  +1.1..+6.6    4.1   3.6    0.97  53.3           100 +3.4% (2169) +5.8% (1005) +3.4% (1726)
 0.03 -170.0  4451  176.2 3.96  +1.0..+6.9    3.9   4.0    0.97  51.9           105 +2.6% (1959)  +6.1% (897) +4.4% (1595)
 0.03 -140.0  3892  148.8 3.82  +0.5..+7.1    4.4   3.2    0.97  50.3           110 +2.7% (1664)  +6.6% (788) +3.6% (1440)
 0.06    NaN  3470  168.2 4.85  +1.5..+8.2    3.2   6.5    0.99  53.5           100 +3.3% (1609)  +5.3% (796) +7.0% (1065)
 0.06 -250.0  3470  168.2 4.85  +1.5..+8.2    3.2   6.5    0.99  53.5           100 +3.3% (1609)  +5.3% (796) +7.0% (1065)
 0.06 -200.0  3468  168.8 4.87  +1.5..+8.2    3.1   6.6    0.99  53.5           100 +3.3% (1609)  +5.3% (796) +7.0% (1063)
 0.06 -170.0  3179  157.8 4.96  +1.4..+8.5    2.6   7.3    0.99  52.3           105 +2.4% (1475)  +5.3% (722)  +8.6% (982)
 0.06 -140.0  2775  135.6 4.89  +1.0..+8.8    3.5   6.3    0.99  50.6           110 +2.4% (1243)  +5.4% (634)  +7.9% (898)
 0.10    NaN  2056  126.3 6.14 +1.8..+10.5    6.0   6.3    1.00  53.5           105  +6.6% (973)  +2.4% (542)  +9.1% (541)
 0.10 -250.0  2056  126.3 6.14 +1.8..+10.5    6.0   6.3    1.00  53.5           105  +6.6% (973)  +2.4% (542)  +9.1% (541)
 0.10 -200.0  2054  126.8 6.17 +1.8..+10.5    6.1   6.2    1.00  53.5           105  +6.6% (973)  +2.4% (542)  +9.2% (539)
 0.10 -170.0  1915  121.9 6.36 +1.8..+11.0    5.9   6.9    1.00  52.5           105  +6.5% (910)  +1.2% (501) +11.3% (504)
 0.10 -140.0  1691  112.0 6.62 +1.6..+11.7    6.6   6.7    1.00  51.1           110  +6.9% (779)  +2.0% (452) +10.8% (460)

### The BORROWED correction applied (what a model with no record is given), floor -200

 EV>=  bets  units   roi         ci  early  late  unders  win%  median price      2023-24      2024-25      2025-26
 0.00  7088 -266.0 -3.75 -6.2..-1.3   -4.3  -3.2    0.79  45.9           115 -6.7% (2750) +2.7% (1131) -3.5% (3207)
 0.03  5645 -249.2 -4.42 -7.2..-1.6   -5.7  -3.1    0.84  44.6           120 -8.4% (2204)  +2.7% (929) -3.6% (2512)
 0.06  4481 -135.0 -3.01 -6.2..+0.2   -4.9  -1.2    0.88  44.5           120 -8.9% (1775)  +7.4% (766) -1.7% (1940)
 0.08  3764 -123.5 -3.28 -6.8..+0.2   -4.0  -2.6    0.91  43.8           124 -8.3% (1523)  +9.0% (651) -3.5% (1590)
 0.10  3155 -122.7 -3.89 -7.8..-0.0   -5.9  -1.9    0.93  43.0           126 -9.5% (1295)  +8.6% (543) -3.5% (1317)
 0.12  2595  -66.6 -2.57 -6.9..+1.8   -4.2  -0.9    0.94  43.2           126 -9.1% (1053) +12.0% (465) -2.5% (1077)
 0.15  1847   -0.6 -0.03 -5.2..+5.2   -2.3   2.2    0.96  43.6           130  -6.9% (759) +15.9% (342)  -0.4% (746)

### Claimed against realised, the unders bet at EV >= 0.06 with the -200 floor

model says under  bets  claimed  borrowed correction says  happened
         0.5-0.6  1396    0.545                     0.480     0.497
         0.6-0.7   976    0.649                     0.588     0.621
         0.7-0.8   297    0.723                     0.668     0.650

at EV >= 0.06, floor -200: 3,422 under bets over 403 priced game days (8.5 a day; most on one day 36)
```

## Read, the production model

- **It reproduces the lab to the bet**: 4,904 / 3,470 / 2,056 / 946 bets at
  +3.9% / +4.9% / +6.1% / +6.5%, the numbers in "Three seasons of priced
  props" above.
- **A plateau from 0.03 to 0.12, every season positive at every cut.** Chosen
  floor: **EV >= 0.10** — +6.2% on 2,054 bets with the live price floor
  (interval +1.8..+10.5), halves +6.1% / +6.2%, seasons +6.6% / +2.4% / +9.2%;
  0.08 and 0.12 either side are +5.1% and +6.8% with intervals clear of zero.
- **The -200 price floor removes four bets.** The unders this model takes are
  near even money (median +105); 0.1% of DraftKings' under prices are shorter
  than -200.
- **It must decide on its own probability.** With the correction a model with
  no record is handed, the same three seasons read -2.6% to -4.4% at every cut
  up to 0.12 and flat at 0.15. `config.MODELS_ON_OWN_PROBABILITY`.
- **Its own probability over-claims where it bets**: says 54.5% and delivers
  49.7% (1,396 bets), 64.9% and 62.1% (976), 72.3% and 65.0% (297). That is
  the selection: a bet is where the model disagrees most with the price. It is
  why the realised return (+5 to +6%) is under the 10% the floor asks for, and
  it is what a correction fitted on this model's OWN bets should fix once
  there are enough of them.
- **Volume**: about five bets a game day at 0.10 (2,054 over 403 priced days),
  nearly all unders, and bunched (36 on the busiest day at the 0.06 cut).
- **What production does that the backtest did not**: the backtest's quote was
  taken an hour before the day's FIRST game; the card reads the newest quote on
  each refresh pass and locks the first one that clears. A scratched player is
  void at DraftKings and settles NO_ACTION here; the backtest never saw him.
- **Not yet built**: saves and shots on goal (positive at the best book, thin
  or flat at DraftKings), assists at 0.10, anytime scorer. Same module shape,
  each needs its own sweep.

---

# Saves, shots on goal, assists: three more prop models to production (2026-10-01)

mike: *"build saves, shots on goal and assists models and we need total goals."*
Built as one engine with a Spec per market (`models/nhl_props.py`), backtested
through that module (`python -m scripts.nhl_prop_backtest`), scored by
`scripts/nhl_props_card.py`. Walk-forward on the three priced seasons: each
season scored by a model fitted on earlier seasons only, one pre-game snapshot
a game with every book quoted at the same instant, one bet per player-game.

Three things were decided on these same three seasons, and are said here
rather than left to be found:

1. **Unders only.** At DraftKings every over, blind, loses 9.0% (shots),
   10.4% (assists) and 12.4% (saves); every under loses 2.9%, 3.5% and 0.3%.
   The book's margin sits on the over in every NHL count market, as it did on
   blocked shots. The models' overs lose in shots at every cut and in assists
   at every cut up to 0.15, and are 62 bets in saves at the 0.10 cut ("The
   side the rule does not bet" below).
2. **The best price among the bettable books, FanDuel left out**, not
   DraftKings alone. For saves and assists it changes little. For shots on goal
   it is the difference between a model and no model: at DraftKings alone the
   unders return +3.3% at the 0.10 cut with +0.3% in 2024-25; at the best price
   +5.7% with every season and every half-season positive. FanDuel is out
   because 2,556 of its shots rows fail the coherent-quote check (no other book
   has more than 11) -- the shared parser paired an over from one of its lines
   with an under from another, and the filter can only drop the pairs it can
   see. With FanDuel in, the same cut reads +5.9% on 5,409.
3. **For saves, three more inputs** (home, the goalie's rest, both teams'
   rest), chosen because they lower out-of-sample deviance on the COUNT by
   0.7% (2.176 to 2.160 over the three seasons), not on return. The same test
   added nothing to shots or assists (-0.03% and -0.02% at best), so those two
   run the lab's inputs unchanged.

The floor is **EV >= 0.10 on the model's own probability** for all three, each
on its own grid.

## nhl_prop_saves

```
====================================================================================================
nhl_prop_saves  (player_total_saves, settles on saves; LIVE)
====================================================================================================
player_total_saves: 26,916 quotes; dropped 0 taken after puck drop and 0 incoherent ({})
  2023-24: fit on 8,632 rows, excess variance 0.0303; 2,555 rows to score; mean predicted 26.59 vs actual 26.33
  2024-25: fit on 11,187 rows, excess variance 0.0319; 2,538 rows to score; mean predicted 24.32 vs actual 24.67
  2025-26: fit on 13,725 rows, excess variance 0.0326; 2,537 rows to score; mean predicted 23.45 vs actual 24.11
books shopped: ['draftkings', 'betmgm', 'williamhill_us', 'fanatics', 'betrivers', 'hardrockbet', 'betparx']
priced player-games by season {2024: 1492, 2025: 1618, 2026: 1685} matched to a prediction (unmatched = under 10 games, a name the log does not hold; or a goalie who did not start: void); quotes by book {'hardrockbet': 4172, 'betmgm': 3787, 'draftkings': 3341, 'williamhill_us': 2146, 'fanatics': 212}
DraftKings lines: {25.5: 556, 24.5: 476, 26.5: 462, 27.5: 443, 23.5: 411, 22.5: 304, 28.5: 288, 21.5: 151}
blind always over at DraftKings: {'bets': 3341, 'units': -413.8, 'roi%': -12.39, '95% by day': '-15.6..-9.2', 'win%': 47.1, 'med price': -115, 'claimed': 0.44, 'won': 0.471, '2023-24': '-14.0% (1439) [-12/-16]', '2024-25': '-25.1% (314) [-17/-33]', '2025-26': '-8.5% (1588) [-4/-13]'}
blind always under at DraftKings: {'bets': 3339, 'units': -10.7, 'roi%': -0.32, '95% by day': '-3.5..+2.9', 'win%': 53.0, 'med price': -115, 'claimed': 0.56, 'won': 0.53, '2023-24': '+1.2% (1437) [-1/+3]', '2024-25': '+11.8% (314) [+3/+21]', '2025-26': '-4.1% (1588) [-9/+0]'}

### THE RULE: under only, the best price among the books shopped, the model's OWN probability, floor -200; per season as return (bets) [first half / second half]

 EV>=  bets  units  roi%  95% by day  win%  med price  claimed   won               2023-24                2024-25               2025-26
 0.00  3406   78.7  2.31  -1.1..+5.7  54.3       -115    0.596 0.543   +4.2% (937) [+2/+7]  +5.7% (1268) [+15/-4]  -2.8% (1201) [-8/+2]
 0.03  2908  107.2  3.69  +0.1..+7.2  55.1       -115    0.606 0.551   +5.3% (794) [+1/+9]  +6.7% (1115) [+15/-1]   -0.9% (999) [-6/+4]
 0.05  2591  129.2  4.99  +1.3..+8.7  55.8       -115    0.613 0.558   +5.7% (704) [+4/+7]  +8.2% (1027) [+16/+0]   +0.6% (860) [-4/+6]
 0.06  2404  126.1  5.25  +1.3..+9.1  55.9       -115    0.617 0.559   +6.6% (643) [+5/+8]   +8.5% (972) [+16/+1]   +0.1% (789) [-4/+4]
 0.08  2071  140.6  6.79 +2.5..+11.0  56.7       -115    0.625 0.567   +8.3% (532) [+9/+8]   +9.4% (879) [+18/+1]   +2.1% (660) [+0/+4]
 0.10  1755  136.5  7.77 +3.2..+12.5  57.3       -115    0.633 0.573   +7.3% (448) [+6/+8]  +10.1% (780) [+17/+3]   +4.7% (527) [+0/+9]
 0.12  1467  143.7  9.80 +4.9..+14.8  58.3       -115    0.641 0.583  +9.6% (377) [+12/+7]  +12.0% (673) [+16/+8]  +6.5% (417) [+1/+12]
 0.15  1098  113.7 10.35 +4.3..+16.1  58.6       -115    0.655 0.586  +7.0% (277) [+13/+1] +13.6% (543) [+17/+10]  +7.3% (278) [+2/+13]
 0.20   635   95.0 14.97 +8.0..+22.0  61.1       -115    0.679 0.611 +12.9% (151) [+25/+1] +14.3% (354) [+18/+11] +19.2% (130) [+34/+4]

### The same rule at DraftKings alone

 EV>=  bets  units  roi%  95% by day  win%  med price  claimed   won               2023-24               2024-25               2025-26
 0.00  2291   35.4  1.54  -2.7..+5.7  54.0       -115    0.592 0.540   +4.2% (911) [+1/+7] +12.2% (263) [+1/+24]  -3.2% (1117) [-9/+2]
 0.03  1939   66.1  3.41  -0.8..+7.8  54.9       -115    0.602 0.549   +5.4% (773) [+2/+9] +13.4% (242) [+3/+24]   -0.9% (924) [-7/+5]
 0.05  1699   76.9  4.53  -0.0..+9.0  55.5       -115    0.608 0.555   +5.6% (679) [+4/+7] +13.8% (228) [-2/+30]   +0.9% (792) [-5/+6]
 0.06  1574   76.7  4.88  +0.0..+9.6  55.7       -115    0.612 0.557   +6.3% (619) [+5/+8] +13.1% (221) [-2/+28]   +1.2% (734) [-2/+4]
 0.08  1334   87.0  6.52 +1.2..+11.7  56.6       -115    0.620 0.566  +7.8% (515) [+10/+6] +16.5% (205) [-0/+33]   +2.1% (614) [-4/+8]
 0.10  1110   88.5  7.97 +2.0..+13.7  57.4       -115    0.628 0.574   +7.2% (436) [+7/+7] +14.9% (185) [-1/+31]  +6.1% (489) [-1/+13]
 0.12   916   74.5  8.13 +1.5..+14.5  57.4       -115    0.636 0.574  +8.9% (367) [+11/+7] +11.4% (161) [-5/+28]  +6.1% (388) [-2/+14]
 0.15   644   60.0  9.32 +1.8..+16.7  58.1       -115    0.651 0.581  +7.6% (265) [+14/+1] +15.4% (131) [-0/+31]  +7.9% (248) [+3/+13]
 0.20   344   43.4 12.62 +3.1..+22.3  59.9       -115    0.675 0.599 +12.7% (143) [+25/+1]  +13.1% (89) [-3/+29] +12.2% (112) [+26/-2]

### The side the rule does not bet (over), best price

 EV>=  bets  units   roi%   95% by day  win%  med price  claimed   won                2023-24              2024-25               2025-26
 0.00   301  -40.3 -13.39  -24.5..-2.8  46.5     -115.0    0.571 0.465 -15.3% (138) [-12/-19]  -3.5% (79) [+5/-11] -19.5% (84) [-29/-10]
 0.03   185  -15.8  -8.51  -22.9..+5.0  49.2     -115.0    0.588 0.492   -14.2% (88) [+5/-33]  +6.5% (47) [-3/+16] -12.7% (50) [-38/+13]
 0.05   149   -0.3  -0.23 -15.4..+14.5  53.7     -115.0    0.595 0.537   -0.3% (70) [+10/-10]  +9.3% (39) [+6/+12]  -9.5% (40) [-32/+13]
 0.06   129    7.0   5.41 -11.9..+21.5  56.6     -115.0    0.599 0.566    +2.5% (61) [+10/-5] +13.5% (36) [+2/+25]  +1.8% (32) [-27/+31]
 0.08    94    8.6   9.16 -11.6..+29.0  58.5     -115.0    0.609 0.585     +2.2% (45) [+8/-3]                 (25)                  (24)
 0.10    62    4.8   7.79 -16.7..+32.2  58.1     -115.0    0.625 0.581   -2.2% (32) [+14/-19]                 (18)                  (12)
 0.12    49    4.8   9.86 -19.3..+38.6  59.2     -115.0    0.633 0.592                   (29)                 (13)                   (7)
 0.15    30    1.3   4.35 -34.1..+39.1  56.7     -115.0    0.651 0.567                   (23)                  (5)                   (2)
 0.20    12    NaN    NaN          NaN   NaN        NaN      NaN   NaN                    NaN                  NaN                   NaN

### The rule under the BORROWED correction instead (under, best price, floor -200)

 EV>=  bets  units  roi%  95% by day  win%  med price  claimed   won               2023-24                2024-25                2025-26
 0.00  1906  152.5  8.00 +3.7..+12.2  57.1       -110    0.606 0.571   +5.4% (544) [+6/+4]  +11.5% (775) [+19/+4]   +5.8% (587) [+1/+11]
 0.03  1397  124.2  8.89 +3.8..+13.9  57.6       -110    0.619 0.576  +8.1% (379) [+13/+3]  +12.3% (608) [+19/+6]   +4.5% (410) [-2/+11]
 0.05  1120  100.9  9.01 +3.2..+14.6  57.7       -110    0.631 0.577 +10.1% (298) [+18/+2]  +12.0% (520) [+18/+6]   +2.8% (302) [-5/+10]
 0.06   984  118.0 11.99 +5.8..+17.9  59.2       -110    0.639 0.592 +13.5% (251) [+23/+4]  +14.4% (466) [+21/+8]   +6.3% (267) [+1/+12]
 0.08   758   93.2 12.29 +5.4..+18.8  59.5       -110    0.654 0.595 +10.7% (185) [+19/+3] +14.3% (389) [+19/+10]   +9.7% (184) [+10/+9]
 0.10   565   69.9 12.37 +5.0..+19.7  59.6       -110    0.675 0.596  +7.2% (136) [+22/-7] +14.0% (309) [+14/+14] +14.0% (120) [+10/+18]
 0.12   442   62.2 14.07 +5.5..+22.5  60.6       -115    0.688 0.606  +9.8% (105) [+22/-2] +14.8% (256) [+14/+15]  +17.3% (81) [+12/+22]
 0.15   304   37.7 12.40 +2.5..+22.0  59.9       -115    0.707 0.599  +11.3% (70) [+18/+5]  +12.2% (185) [+16/+8]  +14.8% (49) [+14/+15]
 0.20   168   25.2 15.00 +0.9..+28.3  61.3       -115    0.730 0.613  +16.5% (43) [+24/+9] +11.0% (108) [+12/+10]                   (17)

### Claimed against realised, every priced side at DraftKings

model says  sides  claimed  borrowed says  happened  price implies
 0.30-0.40    806    0.365          0.427     0.423          0.529
 0.40-0.50   2452    0.453          0.517     0.507          0.535
 0.50-0.55   1310    0.525          0.460     0.479          0.532
 0.55-0.60   1142    0.573          0.508     0.510          0.534
 0.60-0.65    596    0.623          0.561     0.557          0.539
 0.65-0.70    210    0.669          0.609     0.633          0.540
 0.70-0.80     77    0.729          0.675     0.610          0.542

### Where the bets land at EV >= 0.10

          book  bets  units  roi%   95% by day  win%  med price  claimed   won             2023-24               2024-25              2025-26
    draftkings   969   74.3  7.66  +1.2..+13.9  57.1     -115.0    0.627 0.571 +8.1% (400) [+7/+9] +15.2% (136) [+9/+21] +4.9% (433) [-1/+11]
        betmgm   627   55.6  8.87  +0.8..+16.5  57.9     -110.0    0.640 0.579                (17)  +8.0% (546) [+23/-7] +16.2% (64) [+4/+29]
   hardrockbet   113   13.3 11.75  -5.2..+31.0  60.2     -115.0    0.648 0.602                 (8) +17.1% (87) [+21/+14]                 (18)
williamhill_us    34   -2.9 -8.46 -39.3..+22.6  50.0     -119.0    0.658 0.500                (23)                  (11)                  (0)
      fanatics    12    NaN   NaN          NaN   NaN        NaN      NaN   NaN                 NaN                   NaN                  NaN

at EV >= 0.10: 1,755 bets over 494 priced game days (3.6 a day; most on one day 19)
```

## nhl_prop_shots_on_goal

```
====================================================================================================
nhl_prop_shots_on_goal  (player_shots_on_goal, settles on shots; LIVE)
====================================================================================================
player_shots_on_goal: 399,757 quotes; dropped 0 taken after puck drop and 2,576 incoherent ({'fanduel': 2556, 'betrivers': 11, 'bovada': 7, 'draftkings': 1})
  2023-24: fit on 43,961 rows, excess variance 0.0000; 46,227 rows to score; mean predicted 1.73 vs actual 1.69
  2024-25: fit on 90,188 rows, excess variance 0.0000; 46,225 rows to score; mean predicted 1.57 vs actual 1.58
  2025-26: fit on 136,413 rows, excess variance 0.0000; 46,125 rows to score; mean predicted 1.51 vs actual 1.56
books shopped: ['draftkings', 'betmgm', 'williamhill_us', 'fanatics', 'betrivers', 'hardrockbet', 'betparx']
priced player-games by season {2024: 18100, 2025: 17420, 2026: 18451} matched to a prediction (unmatched = under 10 games, a name the log does not hold); quotes by book {'draftkings': 51478, 'betmgm': 50523, 'hardrockbet': 46806, 'betrivers': 35107, 'williamhill_us': 30112, 'fanatics': 247}
DraftKings lines: {2.5: 23905, 1.5: 22364, 3.5: 4740, 4.5: 455, 0.5: 9, 5.5: 5}
blind always over at DraftKings: {'bets': 51444, 'units': -4636.2, 'roi%': -9.01, '95% by day': '-9.9..-8.1', 'win%': 49.3, 'med price': -125, 'claimed': 0.493, 'won': 0.493, '2023-24': '-10.7% (17057) [-9/-12]', '2024-25': '-9.9% (16581) [-14/-6]', '2025-26': '-6.5% (17806) [-5/-8]'}
blind always under at DraftKings: {'bets': 51448, 'units': -1501.3, 'roi%': -2.92, '95% by day': '-3.9..-2.0', 'win%': 50.7, 'med price': -105, 'claimed': 0.507, 'won': 0.507, '2023-24': '-1.0% (17059) [-2/+0]', '2024-25': '-2.0% (16583) [+3/-7]', '2025-26': '-5.6% (17806) [-7/-4]'}

### THE RULE: under only, the best price among the books shopped, the model's OWN probability, floor -200; per season as return (bets) [first half / second half]

 EV>=  bets  units  roi%   95% by day  win%  med price  claimed   won               2023-24              2024-25                2025-26
 0.00 22324  370.7  1.66   +0.3..+3.0  53.0       -105    0.556 0.530  +3.5% (6859) [+3/+4] +2.2% (7832) [+4/+1]   -0.5% (7633) [-2/+1]
 0.03 15257  470.9  3.09   +1.4..+4.7  53.4       -105    0.563 0.534  +4.8% (4683) [+4/+5] +4.1% (5436) [+5/+3]   +0.4% (5138) [-1/+1]
 0.05 11337  435.3  3.84   +1.8..+5.8  53.3        100    0.567 0.533  +5.4% (3454) [+4/+7] +5.1% (4020) [+6/+4]   +1.1% (3863) [+0/+2]
 0.06  9695  433.6  4.47   +2.4..+6.6  53.4        100    0.569 0.534  +6.6% (2937) [+4/+9] +5.0% (3455) [+6/+4]   +2.0% (3303) [+2/+2]
 0.08  6833  288.3  4.22   +1.6..+6.8  52.6        105    0.573 0.526  +6.9% (2042) [+7/+7] +4.7% (2437) [+6/+3]   +1.4% (2354) [+2/+1]
 0.10  4707  270.3  5.74   +2.8..+8.7  52.7        105    0.577 0.527 +8.2% (1376) [+5/+11] +4.6% (1692) [+7/+2]   +4.8% (1639) [+7/+3]
 0.12  3157  200.7  6.36   +2.9..+9.9  52.3        110    0.582 0.523  +8.7% (873) [+10/+8] +1.8% (1139) [+2/+2]   +9.1% (1145) [+9/+9]
 0.15  1720  138.0  8.02  +3.2..+12.9  52.0        115    0.591 0.520   +5.2% (452) [+6/+4]  +3.1% (615) [+2/+5] +14.6% (653) [+18/+11]
 0.20   657  120.9 18.40 +10.4..+26.1  55.6        115    0.619 0.556  +8.2% (147) [+2/+14] +8.5% (239) [+5/+12] +32.6% (271) [+38/+27]

### The same rule at DraftKings alone

 EV>=  bets  units  roi%  95% by day  win%  med price  claimed   won              2023-24              2024-25                2025-26
 0.00 18661   48.2  0.26  -1.2..+1.7  52.4       -105    0.556 0.524 +2.3% (5824) [+2/+3] +0.9% (6545) [+2/+0]   -2.3% (6292) [-5/+0]
 0.03 12501  274.7  2.20  +0.4..+4.0  53.1       -105    0.564 0.531 +3.2% (3952) [+2/+4] +3.2% (4403) [+4/+2]   +0.2% (4146) [-1/+1]
 0.05  9184  273.1  2.97  +0.9..+5.0  53.1        100    0.569 0.531 +4.0% (2924) [+3/+5] +4.2% (3202) [+5/+4]   +0.7% (3058) [-1/+2]
 0.06  7770  249.7  3.21  +0.9..+5.5  53.0        100    0.571 0.530 +5.5% (2468) [+5/+6] +3.3% (2691) [+4/+3]   +1.0% (2611) [+1/+1]
 0.08  5375  130.0  2.42  -0.4..+5.1  52.0        105    0.576 0.520 +4.7% (1709) [+5/+5] +0.7% (1857) [+3/-2]   +2.1% (1809) [+2/+2]
 0.10  3606  120.1  3.33  +0.1..+6.4  51.7        105    0.580 0.517 +6.7% (1128) [+5/+8] +0.3% (1243) [+1/-0]   +3.2% (1235) [+4/+2]
 0.12  2380   87.1  3.66  -0.2..+7.4  51.3        110    0.585 0.513  +4.6% (724) [+6/+3]  -1.1% (822) [+3/-5]    +7.5% (834) [+7/+8]
 0.15  1275  103.7  8.14 +2.9..+13.5  52.4        114    0.593 0.524  +5.1% (363) [+6/+4]  -1.1% (432) [-0/-2] +18.8% (480) [+19/+19]
 0.20   462   90.4 19.56 +9.4..+29.2  56.3        115    0.624 0.563 +8.6% (108) [+13/+4]  +1.2% (161) [-2/+5] +41.0% (193) [+51/+31]

### The side the rule does not bet (over), best price

 EV>=  bets  units   roi%  95% by day  win%  med price  claimed   won                2023-24               2024-25               2025-26
 0.00  9164 -432.6  -4.72  -6.6..-2.8  50.7       -114    0.556 0.507   -6.4% (4617) [-4/-9]  -4.0% (2257) [-6/-2]  -2.0% (2290) [-0/-4]
 0.03  5076 -170.3  -3.35  -6.0..-0.8  50.3       -106    0.559 0.503   -5.9% (3112) [-3/-9]  +0.2% (1008) [-1/+2]   +1.1% (956) [+2/+0]
 0.05  3410 -114.3  -3.35  -6.6..-0.1  49.5        100    0.559 0.495   -5.6% (2301) [-3/-8]   +0.7% (589) [-5/+6]   +2.0% (520) [+1/+3]
 0.06  2761  -68.3  -2.47  -6.0..+1.0  49.6        100    0.560 0.496   -5.6% (1953) [-3/-9]   +4.3% (419) [+0/+8]   +6.1% (389) [+4/+9]
 0.08  1844  -71.9  -3.90  -8.2..+0.5  48.0        105    0.560 0.480   -7.4% (1423) [-6/-9]   +5.3% (218) [+5/+6] +11.1% (203) [+2/+21]
 0.10  1210  -58.5  -4.84 -10.2..+1.0  46.5        110    0.559 0.465  -8.8% (1007) [-5/-13] +18.4% (98) [+19/+17] +11.1% (105) [+1/+21]
 0.12   813  -47.8  -5.88 -12.8..+1.0  45.0        114    0.560 0.450   -8.4% (704) [-7/-10] +22.1% (49) [+25/+19]    +0.6% (60) [-2/+3]
 0.15   429  -23.2  -5.41 -14.6..+4.1  45.0        115    0.566 0.450   -9.1% (378) [-10/-8]                  (22)                  (29)
 0.20   123  -18.0 -14.62 -33.0..+4.7  39.0        125    0.572 0.390 -20.4% (107) [-31/-10]                   (4)                  (12)

### The rule under the BORROWED correction instead (under, best price, floor -200)

 EV>=  bets  units  roi% 95% by day  win%  med price  claimed   won              2023-24              2024-25              2025-26
 0.00 26817 -450.2 -1.68 -3.1..-0.3  45.2        120    0.456 0.452 +0.5% (8669) [+1/+0] -0.8% (8971) [+3/-5] -4.7% (9177) [-7/-3]
 0.03 22952 -294.6 -1.28 -2.8..+0.1  44.7        125    0.453 0.447 +1.2% (7423) [+1/+1] -0.9% (7736) [+3/-4] -4.0% (7793) [-6/-2]
 0.05 20132 -209.1 -1.04 -2.6..+0.5  44.5        125    0.452 0.445 +1.2% (6548) [+0/+2] -1.0% (6778) [+2/-4] -3.3% (6806) [-5/-2]
 0.06 18754 -156.4 -0.83 -2.5..+0.8  44.4        126    0.452 0.444 +1.6% (6131) [+0/+3] -1.3% (6313) [+2/-4] -2.8% (6310) [-4/-1]
 0.08 16071 -158.6 -0.99 -2.8..+0.8  44.0        127    0.453 0.440 +0.6% (5301) [+0/+1] -0.7% (5400) [+3/-4] -2.8% (5370) [-4/-1]
 0.10 13361   -6.7 -0.05 -2.0..+1.9  44.1        130    0.454 0.441 +0.4% (4479) [-1/+2] +1.1% (4468) [+3/-1] -1.7% (4414) [-4/+1]
 0.12 10765   40.6  0.38 -1.8..+2.6  44.0        130    0.457 0.440 +3.0% (3640) [+3/+3] +0.6% (3565) [+3/-2] -2.5% (3560) [-3/-2]
 0.15  7414  110.2  1.49 -1.3..+4.2  44.0        130    0.462 0.440 +5.2% (2562) [+5/+5] +1.9% (2462) [+4/+0] -3.0% (2390) [-6/-0]
 0.20  3375   86.1  2.55 -1.7..+6.5  43.8        135    0.474 0.438 +5.1% (1196) [+8/+2] +2.8% (1051) [-0/+6] -0.4% (1128) [-0/-1]

### Claimed against realised, every priced side at DraftKings

model says  sides  claimed  borrowed says  happened  price implies
 0.30-0.40  14063    0.366          0.428     0.390          0.438
 0.40-0.50  36748    0.451          0.516     0.457          0.488
 0.50-0.55  19052    0.525          0.460     0.522          0.557
 0.55-0.60  17697    0.574          0.509     0.566          0.596
 0.60-0.65  10432    0.622          0.559     0.603          0.620
 0.65-0.70   3624    0.669          0.610     0.634          0.634
 0.70-0.80    578    0.719          0.664     0.633          0.640
 0.80-1.00     61    0.846          0.809     0.836          0.491

### Where the bets land at EV >= 0.10

          book  bets  units  roi%  95% by day  win%  med price  claimed   won                2023-24                2024-25                2025-26
    draftkings  2681   99.1  3.70  -0.4..+7.7  51.4      110.0    0.571 0.514    +5.6% (956) [+4/+7]    -0.2% (917) [+0/-1]    +5.9% (808) [+9/+3]
     betrivers  1109   62.6  5.64 -0.6..+11.7  52.5      104.0    0.575 0.525 +11.0% (249) [+11/+11]    +5.7% (410) [+8/+3]    +2.6% (450) [+9/-4]
        betmgm   424   34.7  8.18 -1.6..+17.8  54.2      100.0    0.594 0.542  +13.7% (104) [+8/+19]  +15.6% (182) [+27/+5]   -5.7% (138) [-11/-0]
   hardrockbet   371   51.2 13.79 +3.9..+23.3  58.8     -105.0    0.598 0.588  +27.5% (58) [+25/+30] +15.5% (178) [+12/+19]    +5.6% (135) [+7/+4]
williamhill_us   120   22.4 18.67 +1.5..+36.5  60.0     -109.0    0.597 0.600                    (9)                    (5) +18.6% (106) [+24/+13]
      fanatics     2    NaN   NaN         NaN   NaN        NaN      NaN   NaN                    NaN                    NaN                    NaN

at EV >= 0.10: 4,707 bets over 528 priced game days (8.9 a day; most on one day 54)
```

## nhl_prop_assists

```
====================================================================================================
nhl_prop_assists  (player_assists, settles on assists; LIVE)
====================================================================================================
player_assists: 309,336 quotes; dropped 0 taken after puck drop and 0 incoherent ({})
  2023-24: fit on 159,628 rows, excess variance 0.0000; 46,294 rows to score; mean predicted 0.30 vs actual 0.29
  2024-25: fit on 205,922 rows, excess variance 0.0000; 46,243 rows to score; mean predicted 0.29 vs actual 0.28
  2025-26: fit on 252,165 rows, excess variance 0.0000; 46,141 rows to score; mean predicted 0.29 vs actual 0.29
books shopped: ['draftkings', 'betmgm', 'williamhill_us', 'fanatics', 'betrivers', 'hardrockbet', 'betparx']
priced player-games by season {2024: 18756, 2025: 18918, 2026: 20928} matched to a prediction (unmatched = under 10 games, a name the log does not hold); quotes by book {'draftkings': 57238, 'betmgm': 56412, 'hardrockbet': 52208, 'williamhill_us': 28306, 'fanatics': 232}
DraftKings lines: {0.5: 57046, 1.5: 192}
blind always over at DraftKings: {'bets': 57213, 'units': -5932.1, 'roi%': -10.37, '95% by day': '-11.6..-9.2', 'win%': 34.7, 'med price': 170, 'claimed': 0.348, 'won': 0.347, '2023-24': '-11.7% (18440) [-11/-12]', '2024-25': '-10.2% (18288) [-12/-8]', '2025-26': '-9.3% (20485) [-9/-10]'}
blind always under at DraftKings: {'bets': 57210, 'units': -1991.1, 'roi%': -3.48, '95% by day': '-4.2..-2.8', 'win%': 65.3, 'med price': -225, 'claimed': 0.652, 'won': 0.653, '2023-24': '-2.5% (18435) [-2/-3]', '2024-25': '-3.7% (18290) [-3/-5]', '2025-26': '-4.1% (20485) [-4/-4]'}

### THE RULE: under only, the best price among the books shopped, the model's OWN probability, floor -200; per season as return (bets) [first half / second half]

 EV>=  bets  units  roi%   95% by day  win%  med price  claimed   won                2023-24               2024-25                2025-26
 0.00  8107  -66.8 -0.82   -3.0..+1.4  55.5       -135    0.588 0.555   +1.3% (3069) [+3/-0]  -0.4% (2026) [+2/-2]   -3.2% (3012) [-2/-4]
 0.03  4604   -0.8 -0.02   -2.9..+2.7  54.1       -125    0.585 0.541   +2.8% (1990) [+4/+2]   -0.6% (998) [-0/-1]   -3.2% (1616) [-3/-3]
 0.05  3014   64.9  2.15   -1.5..+5.8  53.8       -115    0.582 0.538   +3.7% (1434) [+5/+3]   +3.9% (594) [+3/+4]    -1.1% (986) [-1/-1]
 0.06  2433   75.9  3.12   -1.0..+7.2  53.6       -110    0.580 0.536   +5.2% (1213) [+5/+5]   +6.4% (449) [+6/+6]    -2.0% (771) [-3/-1]
 0.08  1641  123.1  7.50  +2.5..+12.3  54.6       -105    0.577 0.546    +8.6% (885) [+8/+9] +10.0% (273) [+6/+13]    +4.2% (483) [+2/+7]
 0.10  1063  115.8 10.90  +4.7..+17.2  54.8        105    0.575 0.548  +11.0% (612) [+14/+8] +11.3% (150) [+3/+20]  +10.6% (301) [+6/+15]
 0.12   722  109.0 15.10  +8.0..+22.1  55.7        110    0.574 0.557 +13.6% (438) [+13/+14]  +13.3% (87) [+8/+18] +19.3% (197) [+16/+22]
 0.15   421   86.1 20.44 +11.8..+29.5  58.0        115    0.588 0.580 +14.3% (267) [+15/+14]  +25.7% (41) [+6/+44] +33.1% (113) [+40/+26]
 0.20   206   49.7 24.14 +10.7..+37.5  61.2        115    0.625 0.612 +15.8% (123) [+14/+17]                  (17)  +46.7% (66) [+57/+37]

### The same rule at DraftKings alone

 EV>=  bets  units  roi%   95% by day  win%  med price  claimed   won                2023-24               2024-25                2025-26
 0.00  7621  -64.6 -0.85   -3.1..+1.5  55.4       -135    0.587 0.554   +1.2% (2941) [+3/-1]  +0.1% (1878) [+2/-2]   -3.6% (2802) [-2/-5]
 0.03  4303  -17.0 -0.40   -3.3..+2.6  53.8       -125    0.583 0.538   +2.1% (1902) [+4/-0]   -0.7% (904) [-1/-0]   -3.4% (1497) [-3/-3]
 0.05  2806   32.4  1.15   -2.6..+4.9  53.2       -115    0.580 0.532   +2.3% (1359) [+4/+0]   +3.5% (528) [+4/+3]    -1.9% (919) [-3/-0]
 0.06  2261   58.1  2.57   -1.7..+6.9  53.3       -110    0.578 0.533   +4.5% (1145) [+5/+4]   +6.5% (393) [+5/+8]    -2.6% (723) [-6/+1]
 0.08  1508  102.0  6.76  +1.8..+11.8  54.3       -105    0.576 0.543    +7.3% (829) [+9/+6] +13.2% (234) [+7/+19]    +2.5% (445) [-3/+8]
 0.10   975  109.9 11.27  +4.5..+17.7  54.9        105    0.572 0.549  +11.0% (572) [+15/+7]  +9.4% (131) [-1/+19]  +12.8% (272) [+7/+19]
 0.12   652  105.9 16.24  +8.6..+23.8  56.3        110    0.572 0.563 +13.6% (403) [+14/+13]  +12.6% (75) [+19/+6] +23.9% (174) [+21/+27]
 0.15   377   74.5 19.75 +10.3..+29.1  57.3        114    0.583 0.573 +14.2% (243) [+15/+14]  +16.0% (37) [-3/+34]  +35.0% (97) [+42/+28]
 0.20   170   37.0 21.79  +5.9..+38.0  60.0        114    0.622 0.600  +12.0% (103) [+3/+21]                  (13)  +48.2% (54) [+59/+37]

### The side the rule does not bet (over), best price

 EV>=  bets  units  roi%   95% by day  win%  med price  claimed   won               2023-24              2024-25                2025-26
 0.00  8193 -243.1 -2.97   -6.2..+0.3  34.3        190    0.373 0.343  -4.1% (3484) [-3/-5] -2.1% (2355) [-8/+3]   -2.3% (2354) [-2/-2]
 0.03  4765 -101.1 -2.12   -6.2..+1.9  33.9        195    0.374 0.339  -1.4% (2239) [+0/-3] -2.0% (1248) [-9/+5]   -3.5% (1278) [-6/-1]
 0.05  3280  -71.1 -2.17   -7.2..+2.6  33.4        200    0.375 0.334  +0.8% (1648) [+3/-1] -6.2% (792) [-10/-2]    -4.1% (840) [-7/-2]
 0.06  2698  -34.8 -1.29   -7.0..+4.2  33.5        200    0.376 0.335  +3.0% (1395) [+3/+3] -7.0% (626) [-11/-3]    -4.9% (677) [-5/-5]
 0.08  1790  -36.8 -2.06   -8.8..+4.8  32.5        210    0.376 0.325   +3.1% (946) [+8/-2]  -7.7% (398) [-7/-8]   -8.1% (446) [-13/-3]
 0.10  1189   -3.1 -0.26   -8.9..+8.0  32.5        210    0.377 0.325  +3.8% (653) [+11/-3]  -1.1% (240) [-6/+4]    -8.4% (296) [-9/-8]
 0.12   789  -35.5 -4.50  -15.4..+5.9  30.9        220    0.379 0.309 -1.6% (453) [+11/-14]  -2.6% (145) [-8/+3]  -12.9% (191) [-19/-7]
 0.15   411   -9.4 -2.28 -17.2..+14.1  30.9        220    0.381 0.309 +3.5% (237) [+25/-18]  +6.2% (74) [-7/+19] -22.3% (100) [-29/-15]
 0.20   125   25.1 20.05  -8.2..+50.6  35.2        230    0.386 0.352 +23.6% (66) [+57/-10]                 (26)   +9.7% (33) [+52/-30]

### The rule under the BORROWED correction instead (under, best price, floor -200)

 EV>=  bets  units  roi%  95% by day  win%  med price  claimed   won              2023-24              2024-25                2025-26
 0.00  3475  -62.7 -1.80  -5.6..+1.9  46.7        110    0.484 0.467 -0.6% (1374) [+2/-4]  -1.7% (921) [+2/-5]   -3.3% (1180) [-4/-2]
 0.03  2824  -40.4 -1.43  -5.6..+2.7  45.6        115    0.474 0.456 +0.0% (1064) [+4/-4]  -1.0% (742) [+4/-6]   -3.3% (1018) [-6/-1]
 0.05  2478  -43.0 -1.74  -6.2..+2.6  44.8        120    0.470 0.448  +0.0% (906) [+6/-6]  -3.0% (651) [+1/-7]    -2.6% (921) [-6/+1]
 0.06  2295  -39.8 -1.73  -6.5..+2.9  44.5        120    0.469 0.445  +0.2% (833) [+5/-4]  -3.5% (587) [+1/-8]    -2.4% (875) [-4/-0]
 0.08  1973  -32.7 -1.66  -6.9..+3.5  44.0        124    0.468 0.440  +0.9% (686) [+8/-6]  -3.2% (502) [+1/-7]    -2.9% (785) [-2/-4]
 0.10  1675  -41.4 -2.47  -8.2..+3.1  43.2        126    0.468 0.432  +0.9% (575) [+3/-1] -5.9% (405) [-1/-11]    -3.2% (695) [-2/-4]
 0.12  1421  -18.7 -1.32  -7.6..+5.0  43.3        130    0.468 0.433  +0.0% (497) [+3/-3]  -5.3% (326) [-5/-5]    -0.2% (598) [+3/-3]
 0.15  1081   -0.7 -0.06  -7.2..+7.0  43.4        135    0.472 0.434  -1.4% (393) [+2/-5]  -3.5% (227) [-1/-6]    +2.8% (461) [+7/-2]
 0.20   600   44.6  7.44 -2.9..+17.2  46.0        140    0.484 0.460  +1.9% (241) [+4/-0]  +3.7% (109) [+0/+7] +14.4% (250) [+18/+11]

### Claimed against realised, every priced side at DraftKings

model says  sides  claimed  borrowed says  happened  price implies
 0.30-0.40  22762    0.349          0.410     0.345          0.382
 0.40-0.50  14602    0.444          0.508     0.441          0.480
 0.50-0.55   5914    0.525          0.461     0.527          0.554
 0.55-0.60   8695    0.577          0.513     0.580          0.604
 0.60-0.65  11065    0.625          0.563     0.627          0.654
 0.65-0.70  11690    0.676          0.616     0.682          0.704
 0.70-0.80  18991    0.739          0.686     0.738          0.762
 0.80-1.00    854    0.820          0.779     0.815          0.794

### Where the bets land at EV >= 0.10

       book  bets  units  roi%  95% by day  win%  med price  claimed   won                2023-24              2024-25               2025-26
 draftkings   849   80.2  9.44 +2.1..+16.7  53.9      105.0    0.570 0.539   +8.9% (499) [+14/+3] +6.9% (107) [-0/+14] +11.8% (243) [+3/+20]
     betmgm   187   34.6 18.51 +3.1..+34.1  58.3      115.0    0.582 0.583 +22.8% (103) [+23/+23] +16.6% (40) [-1/+34]  +10.2% (44) [+23/-3]
hardrockbet    26    NaN   NaN         NaN   NaN        NaN      NaN   NaN                    NaN                  NaN                   NaN
   fanatics     1    NaN   NaN         NaN   NaN        NaN      NaN   NaN                    NaN                  NaN                   NaN

at EV >= 0.10: 1,063 bets over 528 priced game days (2.0 a day; most on one day 14)
```

## The opening weeks of a season, each model at its own cut

No hold is applied to any of them (`MIN_GAMES` is ten CAREER rows in the log).
This is what the three seasons say about that, not a proposal:

```
### nhl_prop_saves: the rule at EV >= 0.10, by time into the season
       window  bets  units  roi%   95% by day  win%  med price  claimed   won               2023-24                2024-25               2025-26  share of priced players bet  EV claimed
       week 1    37    4.0 10.69 -30.9..+45.1  59.5       -115    0.640 0.595                  (15)                   (11)                  (11)                        0.252       0.191
       week 2    81   -1.6 -1.92 -22.1..+20.4  51.9       -110    0.634 0.519                  (14)   -10.6% (44) [-6/-15]                  (23)                        0.386       0.201
    weeks 3-4   133    7.1  5.37 -14.8..+25.6  55.6       -115    0.629 0.556                  (21)   +17.5% (78) [-9/+44] -36.2% (34) [-54/-19]                        0.357       0.190
    weeks 5-8   293   63.4 21.65 +11.6..+31.7  64.5       -115    0.638 0.645  +14.4% (69) [-6/+34] +23.8% (162) [+21/+27] +24.0% (62) [+29/+18]                        0.376       0.202
 after week 8  1211   63.5  5.24  -0.2..+10.6  56.0       -115    0.632 0.560   +2.1% (329) [-1/+5]   +5.7% (485) [+17/-6]   +7.3% (397) [+7/+8]                        0.369       0.190
first 2 weeks   118    2.4  2.03 -16.3..+22.2  54.2       -115    0.636 0.542                  (29)   -1.3% (55) [+11/-13] -20.0% (34) [-18/-22]                          NaN         NaN
first 4 weeks   251    9.5  3.80 -10.1..+17.9  55.0       -115    0.632 0.550 +31.6% (50) [+34/+29]   +9.7% (133) [+5/+15] -28.1% (68) [-20/-36]                          NaN         NaN
### nhl_prop_shots_on_goal: the rule at EV >= 0.10, by time into the season
       window  bets  units  roi%  95% by day  win%  med price  claimed   won               2023-24               2024-25               2025-26  share of priced players bet  EV claimed
       week 1   141   13.1  9.32 -3.4..+21.6  54.6        110    0.585 0.546  +13.4% (61) [+7/+19]   +5.4% (60) [-6/+17]                  (20)                        0.101       0.177
       week 2   242   29.1 12.02 -2.8..+27.4  55.4        105    0.584 0.554  +8.4% (54) [-22/+39] +8.4% (139) [+33/-16] +26.2% (49) [+18/+34]                        0.126       0.166
    weeks 3-4   413   15.1  3.66 -4.3..+11.3  51.8        110    0.581 0.518   -3.4% (84) [+9/-16]  +8.4% (249) [+3/+14]    -3.7% (80) [-1/-7]                        0.103       0.168
    weeks 5-8   771   72.6  9.41 +3.0..+16.0  54.7        105    0.578 0.547 +10.8% (193) [+12/+9]  +7.0% (353) [+14/+0] +12.0% (225) [+20/+4]                        0.093       0.157
 after week 8  3140  140.4  4.47  +0.8..+8.3  52.0        105    0.575 0.520  +8.3% (984) [+5/+12]   +2.0% (891) [+4/+0]  +3.2% (1265) [+4/+3]                        0.082       0.157
first 2 weeks   383   42.2 11.03 +0.6..+21.7  55.1        105    0.585 0.551 +11.1% (115) [+21/+1]  +7.5% (199) [+15/+1]  +21.1% (69) [+4/+38]                          NaN         NaN
first 4 weeks   796   57.4  7.20 +0.9..+13.7  53.4        110    0.583 0.534   +4.9% (199) [+3/+7]  +8.0% (448) [+5/+11]  +7.8% (149) [+22/-6]                          NaN         NaN
### nhl_prop_assists: the rule at EV >= 0.10, by time into the season
       window  bets  share of priced players bet  EV claimed  units  roi%   95% by day  win%  med price  claimed   won               2023-24              2024-25               2025-26
       week 1    22                        0.014       0.196    NaN   NaN          NaN   NaN        NaN      NaN   NaN                   NaN                  NaN                   NaN
       week 2    37                        0.018       0.167    2.4  6.50 -25.5..+34.2  54.1     -105.0    0.589 0.541                  (15)                 (13)                   (9)
    weeks 3-4    71                        0.016       0.177   17.7 24.94  +0.2..+52.2  66.2     -115.0    0.627 0.662 +32.7% (31) [+46/+21]                 (16)                  (24)
    weeks 5-8   175                        0.020       0.164    5.4  3.09 -10.1..+16.3  51.4      100.0    0.577 0.514   +1.4% (71) [+11/-8]  +7.3% (47) [-6/+20]    +1.7% (57) [-4/+8]
 after week 8   758                        0.018       0.159   91.4 12.06  +4.3..+19.7  54.7      107.0    0.567 0.547 +10.7% (481) [+20/+2] +19.3% (72) [+9/+29] +12.8% (205) [+6/+19]
first 2 weeks    59                          NaN         NaN    1.3  2.25 -22.2..+26.4  52.5     -105.0    0.606 0.525                  (29)                 (15)                  (15)
first 4 weeks   130                          NaN         NaN   19.0 14.64  -2.7..+32.9  60.0     -110.0    0.617 0.600 +24.7% (60) [+20/+29] -1.3% (31) [-16/+13]  +11.8% (39) [-7/+30]
```

## Read, the three models

- **Saves: +7.8% on 1,755 bets** (interval +3.2..+12.5), seasons +7.3% /
  +10.1% / +4.7%. Clear of zero from 0.05 up and positive in every season from
  0.05 up. It also survives the borrowed correction (+8.0% to +15.0% at every
  cut), so nothing rides on which probability it decides on. A priced goalie
  who did not start is not a bet here and is NO_ACTION in settlement -- one
  rule, in both places.
- **Shots on goal: +5.7% on 4,707 bets** (interval +2.8..+8.7), seasons +8.2%
  / +4.6% / +4.8%, all six half-seasons positive. It is the thinnest of the
  three and the only one that needs the best price to exist. It holds under
  the wider count distribution too (+4.9% on 5,804, every season positive from
  0.10 up). Volume is the thing to know: 8.9 bets a priced game day, 54 on the
  busiest.
- **Assists: +10.9% on 1,063 bets** (interval +4.7..+17.2), seasons +11.0% /
  +11.3% / +10.6%, and the return RISES with the cut (+7.5% at 0.08, +15.1% at
  0.12, +20.4% at 0.15), which is what a real signal does. Under the borrowed
  correction it loses at every cut to 0.15: it must decide on its own number.
- **All three over-claim where they bet**, as blocked shots does: saves says
  63.3% and delivers 57.3%, shots 57.7% and 52.7%, assists 57.5% and 54.8%.
  The returns above are what was realised, so they already carry that. It is
  why a model asking for 10% earns 6-11%.
- **The opening weeks are not worse.** Shots on goal in the first four weeks:
  +7.2% on 796 (interval +0.9..+13.7). Saves: +3.8% on 251, interval -10.1 to
  +17.9, one bad opening (2025-26, -28% on 68) against two good ones -- too few
  bets to say more than "not evidently different". Assists: 130 bets, +14.6%.
- **What the card does on a real slate** (2026-10-01, replayed against that
  night's stored quotes, nothing written): saves 9 bets from 11 priced goalies,
  shots 32 from 118 scored, assists 2 from 117. Nine of eleven goalies is far
  above the backtest's 25-39% in opening weeks. The inputs were checked: on
  the sixteen starts already played this season the model's mean is 23.5
  against 23.6 actual, so it is not biased low. All nine landed at Hard Rock:
  four where it hung a number a save higher than DraftKings, two it alone
  priced, three at the same number and a better price. One night is not a
  sample.
- **Who is skipped.** A priced player whose last game was for neither of
  tonight's teams (an off-season move, until he has played once for the new
  side), and a name two players on one team share. 24 of 142 on 2026-10-01,
  each named in the log.

---

# Total goals, round four: nothing in the full-game number (2026-10-01)

mike: *"we need total goals."* Three rounds above fitted models and found
nothing. This round asks what a model cannot hide behind, on six priced
seasons with simultaneous quotes: `python -m scripts.nhl_totals_lab`.

```
347,307 pre-game totals quotes, 7,920 games, seasons [2021, 2022, 2023, 2024, 2025, 2026]; 6.7 API snapshots a game

### BLIND at DraftKings' FIRST pre-game number (median 26.2h before puck drop)

 side line  bets  units  roi%  95% by day      2020-21       2021-22      2022-23      2023-24      2024-25      2025-26
 over  all  7763 -317.3 -4.09  -6.1..-2.0  -6.9% (770)  +2.1% (1401) -4.5% (1400) -7.8% (1400) -5.8% (1398) -2.9% (1394)
 over  5.5  2374  -43.2 -1.82  -5.4..+1.8  -5.0% (409)   +1.2% (429)  -8.0% (102) -13.3% (149)  -0.3% (648)  +0.4% (637)
 over  6.0  2260  -46.2 -2.04  -5.6..+1.5  -7.9% (241)   +1.9% (662)  -0.9% (512)  -1.4% (533)  -8.8% (312)          (0)
 over  6.5  2970 -203.6 -6.86 -10.2..-3.3 -15.6% (106)   +5.3% (281)  -5.5% (722) -10.5% (668) -11.7% (437)  -5.4% (756)
under  all  7763 -350.3 -4.51  -6.6..-2.5  -2.0% (770) -10.5% (1401) -4.2% (1400) -0.7% (1400) -2.4% (1398) -6.2% (1394)
under  5.5  2374 -164.8 -6.94 -10.7..-3.1  -4.3% (409)  -10.4% (429)  +0.6% (102)  +4.9% (149)  -7.7% (648)  -9.5% (637)
under  6.0  2260 -131.0 -5.80  -9.3..-2.2  +0.1% (241)   -9.9% (662)  -7.0% (512)  -6.6% (533)  +1.5% (312)          (0)
under  6.5  2970  -64.7 -2.18  -5.6..+1.2  +6.4% (106)  -13.4% (281)  -4.1% (722)  +1.7% (668)  +2.4% (437)  -3.5% (756)

### BLIND by price band, FIRST number

 side      price  bets  units  roi%  95% by day      2020-21      2021-22      2022-23      2023-24      2024-25      2025-26
 over -200..-131   259    3.1  1.21 -8.7..+10.8         (10)          (8)         (16)         (26)   +5.3% (43)  +1.1% (156)
 over -130..-116  2324  -48.9 -2.10  -5.7..+1.5  -5.4% (170)  +3.6% (343)  +2.5% (413)  -4.9% (434) -10.9% (521)  +3.6% (443)
 over -115..-106  2160  -94.7 -4.38  -8.4..-0.3  -9.0% (272)  -0.3% (481)  -5.6% (484)  -8.4% (416)  -0.9% (333)  -2.2% (174)
 over  -105..104  2036 -116.7 -5.73  -9.8..-1.4 -10.3% (233)  +5.4% (499) -11.1% (417)  -9.8% (400)  -1.6% (281) -14.4% (206)
 over   105..200   983  -59.2 -6.02 -12.6..+0.6   +2.8% (85)  -10.4% (70)   +3.8% (70) -11.6% (124)  -8.5% (219)  -5.7% (415)
under -200..-131   240  -13.9 -5.81 -16.6..+5.5  -20.5% (61)          (7)         (16)         (22)  -13.3% (50)   +3.4% (84)
under -130..-116  2003   -7.2 -0.36  -4.3..+3.5  +2.5% (250) -11.7% (320)  +3.9% (265)  +1.2% (353)  +1.7% (349)  +0.7% (466)
under -115..-106  2179  -97.2 -4.46  -8.5..-0.4  +0.4% (278)  -9.9% (527)  -0.8% (482)  -0.6% (423)  -9.0% (297)  -7.5% (172)
under  -105..104  2179 -138.1 -6.34 -10.4..-2.4  -2.3% (165) -12.0% (475)  -7.4% (478)  -2.8% (399)  +0.1% (433) -13.3% (229)
under   105..200  1161  -94.1 -8.10 -13.7..-2.5         (16)   -3.8% (72) -16.4% (159)  -1.3% (203)  -2.7% (268) -11.0% (443)

### BLIND at DraftKings' LAST pre-game number (median 0.2h before puck drop)

 side line  bets  units  roi% 95% by day     2020-21       2021-22      2022-23      2023-24      2024-25      2025-26
 over  all  7763 -313.0 -4.03 -6.1..-2.0 -6.6% (770)  +1.8% (1401) -3.4% (1400) -7.6% (1400) -6.0% (1398) -3.6% (1394)
 over  5.5  2493  -89.0 -3.57 -7.2..+0.2 -6.5% (413)   -2.0% (497)  +4.4% (165)  -3.8% (186)  -5.3% (638)  -3.1% (594)
 over  6.0  2083  -43.4 -2.08 -5.9..+1.8 -7.8% (230)   +6.2% (511)  -7.1% (504)  -2.4% (550)  -2.7% (288)          (0)
 over  6.5  2959 -175.6 -5.94 -9.2..-2.8 -11.6% (99)   +1.0% (344)  -3.0% (644) -12.5% (604)  -8.9% (471)  -3.9% (797)
under  all  7763 -341.1 -4.39 -6.5..-2.4 -2.5% (770) -10.3% (1401) -4.8% (1400) -0.9% (1400) -1.6% (1398) -5.4% (1394)
under  5.5  2493 -124.1 -4.98 -8.8..-1.3 -3.1% (413)   -6.7% (497) -13.3% (165)  -5.1% (186)  -2.1% (638)  -5.5% (594)
under  6.0  2083 -121.2 -5.82 -9.7..-1.9 +0.3% (230)  -14.5% (511)  -0.4% (504)  -5.8% (550)  -4.8% (288)          (0)
under  6.5  2959  -84.1 -2.84 -6.1..+0.4  +2.7% (99)   -9.5% (344)  -6.1% (644)  +3.9% (604)  +0.9% (471)  -5.4% (797)

### BLIND by price band, LAST number

 side      price  bets  units  roi%  95% by day      2020-21      2021-22     2022-23      2023-24      2024-25      2025-26
 over -200..-131   382   -5.4 -1.42 -10.6..+7.0         (21)         (19)  +4.7% (45)  -10.3% (76)   -6.9% (41)  -1.3% (180)
 over -130..-116  2301  -60.9 -2.65  -6.2..+0.8 -11.2% (210)  +3.0% (378) -0.7% (401)  -1.4% (431) -10.5% (491)  +3.0% (390)
 over -115..-106  2051 -125.0 -6.10 -10.3..-2.2  -2.4% (218)  +0.7% (418) -6.4% (395) -10.4% (438)  -8.5% (356)  -9.7% (226)
 over  -105..104  2034  -88.8 -4.36  -8.5..-0.3  -7.2% (221)  +2.4% (448) -4.8% (441) -11.5% (359)  -3.9% (300)  -3.5% (265)
 over   105..200   995  -32.9 -3.31  -9.8..+3.5 -10.4% (100)  -0.0% (138) -0.7% (118)   -5.1% (96)  +5.6% (210)  -8.5% (333)
under -200..-131   318  -27.7 -8.70 -17.7..+0.0   -5.4% (75)   +4.6% (38)        (22)         (19)  -36.6% (68)   +4.7% (96)
under -130..-116  1941  -52.8 -2.72  -6.5..+1.4  -0.1% (243)  -6.5% (340) -7.6% (326)  +2.7% (286)  -0.4% (339)  -2.9% (407)
under -115..-106  2059  -53.2 -2.59  -6.6..+1.5  -6.7% (220) -14.4% (402) +0.7% (422)  +3.9% (459)  -1.8% (335)  +1.9% (221)
under  -105..104  2164 -130.1 -6.01 -10.1..-1.8  +3.4% (204) -11.5% (469) -6.2% (423)  -7.9% (398)  +0.8% (413) -11.3% (257)
under   105..200  1281  -77.3 -6.04 -11.4..-0.6         (28)  -8.0% (152) -7.9% (207)  -2.1% (238)  +2.6% (243) -10.4% (413)

soft-book quotes with Pinnacle in the SAME snapshot: 253,918; same number 78.1%

### SHARP-VS-SOFT: the first snapshot Pinnacle's no-vig makes DraftKings's price +EV (same number)

 pin EV>=  bets  units  roi%   95% by day    2020-21      2021-22     2022-23     2023-24     2024-25     2025-26
     0.00   577   11.0   1.9   -6.3..+9.8 +3.4% (67) +21.1% (121) -1.4% (123) -3.4% (149) -10.4% (41)  -7.6% (76)
     0.01   228   -8.4  -3.7  -16.4..+8.3       (21)  +15.5% (54)  +6.8% (44) -32.3% (50)        (22) -15.4% (37)
     0.02    77   -8.4 -10.9 -32.3..+10.7        (5)         (18)        (17)        (17)         (9)        (11)
     0.03    27    NaN   NaN          NaN        NaN          NaN         NaN         NaN         NaN         NaN
     0.04    12    NaN   NaN          NaN        NaN          NaN         NaN         NaN         NaN         NaN

### SHARP-VS-SOFT: the first snapshot Pinnacle's no-vig makes the best soft book's price +EV (same number)

 pin EV>=  bets  units  roi%   95% by day     2020-21     2021-22     2022-23     2023-24     2024-25     2025-26
     0.00  2914   36.1  1.24   -2.3..+4.6 +2.7% (392) +2.3% (622) -3.4% (486) +3.1% (500) +2.0% (405) +0.9% (509)
     0.01  1372   53.6  3.91   -1.1..+9.0 +7.6% (202) +9.2% (354) -1.5% (187) -7.2% (194) +5.2% (194) +5.1% (241)
     0.02   605    1.6  0.27   -7.2..+7.4  +7.4% (99) +4.4% (192) -16.6% (64)  -8.8% (63)  -2.7% (81) +4.1% (106)
     0.03   276    2.2  0.79 -10.3..+12.0  +6.8% (46) +0.3% (121)        (22)        (21)        (25)  -0.0% (41)
     0.04   133   -0.5 -0.38 -18.7..+17.5        (27)  +0.4% (61)        (12)         (8)        (12)        (13)

### OTHER NUMBER: DraftKings hangs a different total from Pinnacle; bet toward Pinnacle's

 side  bets  units  roi% 95% by day     2020-21     2021-22     2022-23     2023-24     2024-25     2025-26
 both  3187   11.5  0.36 -2.5..+3.3 -7.2% (190) -1.7% (506) +2.9% (450) +5.8% (477) -4.5% (648) +2.4% (916)
 over  1657   13.9  0.84 -3.2..+4.8  -3.8% (33) +1.6% (298) +3.1% (270) +1.9% (230) -5.2% (367) +3.6% (459)
under  1530   -2.4 -0.16 -4.6..+4.4 -8.0% (157) -6.5% (208) +2.7% (180) +9.5% (247) -3.7% (281) +1.2% (457)

### OTHER NUMBER: any soft book hangs a different total from Pinnacle; bet toward Pinnacle's

 side  bets  units  roi% 95% by day     2020-21     2021-22     2022-23     2023-24      2024-25      2025-26
 both  5275  -74.9 -1.42 -3.7..+0.7 -6.6% (482) -3.1% (848) +4.4% (919) +0.8% (936) -4.7% (1007) -1.6% (1083)
 over  2564  -27.5 -1.07 -4.2..+2.0 -9.6% (132) +5.2% (377) +3.0% (454) -0.1% (452)  -7.3% (527)  -1.5% (622)
under  2711  -47.3 -1.75 -5.0..+1.4 -5.5% (350) -9.7% (471) +5.8% (465) +1.6% (484)  -1.8% (480)  -1.8% (461)

DraftKings' number moved between its first and last pre-game snapshot in 24.9% of games

### HINDSIGHT (not a rule): the first number, bet only where it later moved that way

  bet  bets  units  roi%  95% by day     2020-21      2021-22     2022-23     2023-24      2024-25     2025-26
 over   899   30.8  3.43  -2.4..+9.0  +0.5% (66) +10.3% (254) +3.4% (126) -8.6% (116)  -2.1% (165) +7.8% (172)
under  1033   48.7  4.72 -0.9..+10.1 +2.9% (101)  -4.7% (219) +6.9% (227) +6.8% (200) +14.5% (159) +2.8% (127)
```

## Read, total goals

- **The margin is on both sides.** Every over loses 4.0-4.1% and every under
  4.4-4.5%, at the first number and the last, across six seasons. No line is
  positive, and the one price band that is (+1.2% on 259 bets, interval -8.7
  to +10.8) is noise. This is what
  separates the total from the props: there the margin sits on the over, and
  a model that says WHICH unders has something to work with. Here there is no
  cheap side.
- **Pinnacle does not disagree with DraftKings often enough to bet.** Same
  number, same snapshot: 577 bets in six seasons at any positive EV, +1.9%
  with an interval from -6.3 to +9.8; at 2% of EV, 77 bets. Shopping every
  soft book gets it to +1.2% on 2,914. That recovers the margin and nothing
  more.
- **A different number from Pinnacle's is not a signal either**: +0.4% on
  3,187 at DraftKings, -1.4% on 5,275 across the soft books.
- **The ceiling is low.** DraftKings' number moves in 24.9% of games. Betting
  the first number ONLY in the games where it later moved that way -- which no
  rule can know in advance -- returns +3.4% and +4.7%, intervals through zero.
  A perfect predictor of line movement would earn less than the prop models
  do. That is the measurement that says stop fitting models to this number.
- **Verdict: no cut clears, and `nhl_over_under` stays untrained.** What would
  have to change is the market, not the model. The NHL results that hold are
  all in markets where the book's margin is one-sided. The total-goals markets
  shaped like that are the derivative ones -- team totals, period totals,
  alternate totals -- and no price for any of them is stored. The feed sells
  them (`team_totals`, `alternate_totals`, `totals_p1`; docs/nhl_market_research.md).

---

# Total goals, round five: team totals, alternate totals, first-period totals (2026-10-02)

mike, 2026-10-01: *"buy the totals data."* Round four ended on a guess: the
full-game total has the book's margin on both sides, the props that work have
it on one, so the total-goals markets worth pricing would be the derivative
ones. This is that guess, bought and graded.

**Bought** (`data/ingestors/nhl_totals_odds_history.py`): one pre-game snapshot
a game, every book at the same instant, 2023-24 to 2025-26. 4,192 games,
264,043 rows, **125,617 credits** (30 a game and 1 a date, as a three-game
probe measured before the run). **Also loaded, free**: goals by period for the
5,257 games after the archive stops (`data/ingestors/nhl_period_scores_api.py`,
the NHL's own score feed; none disagreed with the stored final), without which
a first-period total cannot be graded.

**Graded** by `python -m scripts.nhl_totals_derivatives_lab`:

```
264,043 bought quotes; 526,318 priced sides with a result, 4,192 games, by season {2024: 1400, 2025: 1398, 2026: 1394}; first-period goals known for 4,192 of 4,192 games
```

## Where the margin sits: every over and every under, blind

```
### BLIND, team_totals: every over and every under at hardrockbet (DraftKings does not list it), price floor -200
                                     book  side number  bets  units   roi%   95% by day  win%  med price 2023-24               2024-25                 2025-26
hardrockbet (DraftKings does not list it)  over    all  8575 -653.7  -7.62  -10.2..-5.0  44.4        105     (0) -6.2% (2764) [-10/-2]    -8.3% (5811) [-9/-7]
hardrockbet (DraftKings does not list it) under    all  8328 -577.7  -6.94   -9.6..-4.2  45.1        105     (0)  -4.5% (2764) [-0/-9]   -8.1% (5564) [-10/-6]
hardrockbet (DraftKings does not list it) under    1.5  1076 -215.9 -20.07 -29.1..-10.5  22.3        260     (0)                  (20) -20.6% (1056) [-24/-17]
hardrockbet (DraftKings does not list it)  over    2.5  3335 -132.1  -3.96   -6.8..-1.2  55.4       -140     (0)  -5.1% (1480) [-8/-2]    -3.0% (1855) [-0/-6]
hardrockbet (DraftKings does not list it) under    2.5  4138 -298.4  -7.21  -10.2..-4.2  42.1        120     (0) -5.8% (1480) [-2/-10]   -8.0% (2658) [-10/-6]
hardrockbet (DraftKings does not list it)  over    3.5  3865 -297.7  -7.70  -10.8..-4.6  41.4        120     (0)  -6.1% (1233) [-7/-5]    -8.4% (2632) [-9/-8]
hardrockbet (DraftKings does not list it) under    3.5  3031  -74.4  -2.45   -5.2..+0.3  56.5       -145     (0)  -4.1% (1233) [-3/-6]    -1.3% (1798) [-0/-2]
hardrockbet (DraftKings does not list it)  over    4.5  1333 -227.7 -17.08 -23.9..-10.4  25.1        240     (0) -56.1% (31) [-55/-57]  -16.2% (1302) [-23/-9]

### BLIND, alternate_totals: every over and every under at DraftKings, price floor -200
      book  side number  bets   units   roi%   95% by day  win%  med price                 2023-24                 2024-25                 2025-26
DraftKings  over    all 17549 -3013.1 -17.17 -20.9..-13.2  27.3        245 -16.5% (7497) [-15/-18] -15.9% (4556) [-21/-11] -19.1% (5496) [-19/-19]
DraftKings under    all 13241 -1497.2 -11.31  -15.2..-7.5  31.6        220    -6.5% (5598) [-5/-8]  -11.1% (3458) [-3/-19] -17.9% (4185) [-20/-16]
DraftKings  over    5.5  2139  -174.9  -8.18  -11.4..-4.9  56.8       -160    -8.9% (951) [-8/-10]    -6.9% (448) [-10/-4]    -8.1% (740) [-10/-6]
DraftKings under    5.5  2407  -116.3  -4.83   -9.0..-0.6  42.2        125    -3.3% (1121) [-3/-3]     -4.7% (466) [-2/-7]    -7.0% (820) [-4/-10]
DraftKings  over    6.5  2011  -142.1  -7.07  -11.9..-2.1  42.6        115   -10.8% (738) [-9/-12]    -6.5% (698) [-15/+2]     -3.0% (575) [+1/-7]
DraftKings under    6.5  1936  -105.3  -5.44   -9.2..-1.8  57.4       -155     -3.6% (714) [-6/-1]     -3.2% (659) [+1/-7]   -10.3% (563) [-13/-7]

### BLIND, totals_p1: every over and every under at DraftKings, price floor -200
      book  side number  bets  units  roi% 95% by day  win%  med price               2023-24              2024-25              2025-26
DraftKings  over    all  3989 -278.9 -6.99 -9.7..-4.3  53.1       -135 -9.1% (1203) [-10/-9] -6.4% (1392) [-8/-5] -5.7% (1394) [-6/-6]
DraftKings under    all  3989 -190.6 -4.78 -7.9..-1.6  46.9        105  -1.7% (1203) [-1/-2] -5.4% (1392) [-4/-7] -6.8% (1394) [-7/-7]
```

## Pinnacle against a bettable book, same number, same snapshot

```
### SHARP-VS-SOFT, team_totals, either side: best bettable price, one bet a game per market
 pin EV>=  bets  units  roi%   95% by day  win%  med price 2023-24              2024-25              2025-26
     0.00   222  -14.1 -6.33  -19.1..+6.4  45.9      110.0    (16) -15.0% (51) [-26/-4] -2.9% (155) [-14/+8]
     0.02    42   -1.6 -3.69 -29.2..+21.8  45.2      120.0     (2)                  (6) +0.7% (34) [+17/-15]
     0.04    12    NaN   NaN          NaN   NaN        NaN     NaN                  NaN                  NaN
     0.06     6    NaN   NaN          NaN   NaN        NaN     NaN                  NaN                  NaN
     0.08     1    NaN   NaN          NaN   NaN        NaN     NaN                  NaN                  NaN
     0.10     0    NaN   NaN          NaN   NaN        NaN     NaN                  NaN                  NaN
     0.15     0    NaN   NaN          NaN   NaN        NaN     NaN                  NaN                  NaN

### SHARP-VS-SOFT, alternate_totals, either side: best bettable price, one bet a game per market
 pin EV>=  bets  units  roi%    95% by day  win%  med price              2023-24                2024-25               2025-26
     0.00  1452   72.1  4.97   -4.3..+15.2  29.4      252.0  -3.8% (548) [-5/-3]  +12.5% (471) [-2/+27]  +7.9% (433) [+3/+12]
     0.02   559   22.8  4.08  -12.3..+21.8  22.2      480.0 +9.0% (188) [-5/+23]  +5.3% (165) [-18/+28] -1.4% (206) [-18/+15]
     0.04   251   13.0  5.19  -23.2..+34.9  19.5      520.0   +4.5% (77) [+3/+6]   +3.7% (73) [-34/+40]  +6.8% (101) [-1/+14]
     0.06   117   32.9 28.12  -16.5..+76.9  23.9      525.0  +1.6% (43) [-7/+10] +97.2% (32) [+12/+182]  +2.6% (42) [-73/+79]
     0.08    52   27.9 53.65 -11.8..+132.8  28.8      535.0                 (18)                   (12)                  (22)
     0.10    23    NaN   NaN           NaN   NaN        NaN                  NaN                    NaN                   NaN
     0.15     4    NaN   NaN           NaN   NaN        NaN                  NaN                    NaN                   NaN

### SHARP-VS-SOFT, totals_p1, either side: best bettable price, one bet a game per market
 pin EV>=  bets  units  roi%  95% by day  win%  med price             2023-24               2024-25              2025-26
     0.00   664   37.7  5.68 -2.6..+13.6  49.7      115.0 +5.9% (143) [+4/+8] +8.9% (212) [+31/-13] +3.4% (309) [-4/+11]
     0.02   160   30.9 19.33 +1.9..+37.4  53.8      126.0                (14)  +20.0% (53) [+50/-9] +21.1% (93) [-1/+42]
     0.04    30    NaN   NaN         NaN   NaN        NaN                 NaN                   NaN                  NaN
     0.06     1    NaN   NaN         NaN   NaN        NaN                 NaN                   NaN                  NaN
     0.08     0    NaN   NaN         NaN   NaN        NaN                 NaN                   NaN                  NaN
     0.10     0    NaN   NaN         NaN   NaN        NaN                 NaN                   NaN                  NaN
     0.15     0    NaN   NaN         NaN   NaN        NaN                 NaN                   NaN                  NaN
```

## The market's own view, priced into each derivative

No hockey inputs. A logistic fit on earlier seasons maps the main total, its
no-vig over and the no-vig moneyline to the chance of each derivative outcome
(a whole number gets a separate fit per side, because it can push).

```
main lines for the model: 7,920 games to fit on ({2021: 927, 2022: 1401, 2023: 1400, 2024: 1400, 2025: 1398, 2026: 1394}); 4,177 priced games have a main line no later than their derivative snapshot (median gap 371 min)

### MODEL, team_totals: claimed against realised (the most-quoted book's sides)
model says  sides  claimed  happened  price implies
 0.05-0.20    172    0.192     0.198          0.249
 0.20-0.35   3689    0.273     0.278          0.314
 0.35-0.45   4105    0.406     0.405          0.441
 0.45-0.55   4766    0.500     0.500          0.527
 0.55-0.65   4105    0.594     0.595          0.620
 0.65-0.80   3689    0.727     0.722          0.758
 0.80-0.95    172    0.808     0.802          0.820

### MODEL, team_totals, either side: best bettable price, one bet a game per market, floor -200
 EV>=  bets  units   roi%   95% by day  win%  med price               2023-24              2024-25                2025-26
 0.00  1828  -92.2  -5.04   -9.4..-0.9  50.1     -112.0  -7.2% (515) [+0/-15]  -0.7% (648) [+1/-3]   -7.6% (665) [-12/-4]
 0.02   737  -36.2  -4.91  -12.0..+2.1  49.1     -109.0 -1.4% (211) [+11/-13]  +0.4% (251) [-2/+3]  -12.4% (275) [-18/-7]
 0.04   281  -29.8 -10.59  -22.1..+0.3  45.2      104.0  -1.7% (81) [+20/-23]  -4.7% (95) [+9/-18] -22.8% (105) [-32/-14]
 0.06   127  -10.0  -7.89 -25.8..+10.5  45.7      106.0                  (27) -0.3% (51) [+27/-26]   -20.5% (49) [-39/-2]
 0.08    52   -7.7 -14.73 -40.4..+13.3  40.4      120.0                  (13)                 (18)                   (21)
 0.10    28    NaN    NaN          NaN   NaN        NaN                   NaN                  NaN                    NaN
 0.15     4    NaN    NaN          NaN   NaN        NaN                   NaN                  NaN                    NaN

### MODEL, alternate_totals: claimed against realised (the most-quoted book's sides)
model says  sides  claimed  happened  price implies
 0.05-0.20  16393    0.130     0.141          0.190
 0.20-0.35   9849    0.245     0.241          0.317
 0.35-0.45   6656    0.410     0.422          0.475
 0.45-0.55   8209    0.500     0.500          0.575
 0.55-0.65   6656    0.590     0.578          0.680
 0.65-0.80   9843    0.755     0.759          0.807
 0.80-0.95  11668    0.859     0.846          0.892

### MODEL, alternate_totals, either side: best bettable price, one bet a game per market, floor -200
 EV>=  bets  units  roi%   95% by day  win%  med price              2023-24                2024-25               2025-26
 0.00  1921  -10.9 -0.57   -5.4..+4.1  45.4      102.0  +0.7% (839) [+6/-4]    +0.5% (667) [-6/+7]  -4.8% (415) [-10/+0]
 0.02   901  -25.9 -2.87  -10.3..+4.9  42.3      108.0 -3.1% (428) [+3/-10]  +3.1% (282) [-18/+24] -11.1% (191) [-7/-15]
 0.04   386   38.2  9.90  -3.6..+25.0  43.0      120.0  -0.1% (193) [+4/-4]   +32.0% (98) [-0/+64]   +7.4% (95) [+24/-9]
 0.06   163   28.9 17.74  -5.3..+45.6  40.5      140.0  -4.5% (74) [-15/+6] +65.2% (40) [+19/+111] +12.5% (49) [+37/-11]
 0.08    79   18.2 23.06 -14.9..+68.4  35.4      186.0  -9.7% (34) [-21/+2]                   (21)                  (24)
 0.10    45    7.8 17.31 -32.4..+86.2  33.3      200.0                 (19)                   (12)                  (14)
 0.15     8    NaN   NaN          NaN   NaN        NaN                  NaN                    NaN                   NaN

### MODEL, totals_p1: claimed against realised (the most-quoted book's sides)
model says  sides  claimed  happened  price implies
 0.20-0.35    306    0.296     0.343          0.457
 0.35-0.45   1472    0.420     0.435          0.484
 0.45-0.55   5398    0.500     0.500          0.517
 0.55-0.65   1166    0.576     0.554          0.574

### MODEL, totals_p1, either side: best bettable price, one bet a game per market, floor -200
 EV>=  bets  units  roi%   95% by day  win%  med price              2023-24              2024-25               2025-26
 0.00  2029   -4.9 -0.24   -4.5..+4.2  50.9     -105.0 +5.2% (743) [+10/+1]  -0.5% (691) [+7/-8]  -6.7% (595) [-10/-3]
 0.02  1016  -17.7 -1.75   -8.0..+4.4  49.5     -102.0  +2.7% (361) [+6/-1]  -3.3% (406) [-3/-3]   -5.6% (249) [-8/-3]
 0.04   332   -2.1 -0.64 -11.6..+10.6  48.8      101.0 +1.7% (97) [-11/+14]  -0.2% (144) [+2/-2]    -3.8% (91) [+2/-9]
 0.06   106   10.7 10.07 -10.3..+29.7  51.9      105.0                 (17) -1.5% (50) [+16/-19] +10.3% (39) [-13/+32]
 0.08    28    NaN   NaN          NaN   NaN        NaN                  NaN                  NaN                   NaN
 0.10    13    NaN   NaN          NaN   NaN        NaN                  NaN                  NaN                   NaN
 0.15     0    NaN   NaN          NaN   NaN        NaN                  NaN                  NaN                   NaN
```

## Read, round five

- **The guess was wrong, and that is the finding.** The margin is on both
  sides in all three markets and WIDER than on the main total: team totals
  lose 7.6% on every over and 6.9% on every under, alternate totals 17.2% and
  11.3%, first-period totals 7.0% and 4.8%. Nothing here is shaped like the
  props, where every under blind loses 0-3.5%.
- **The books price these off the main line, correctly.** The market-implied
  fit says what happens (claimed against realised agree in every bucket of
  all three markets) and the book's price sits above it in every bucket.
  A calibrated view of the market cannot beat a price that charges more than
  the main line does: team totals -5.0% on 1,828 bets at any positive EV,
  first period -0.2% on 2,029, alternates -0.6% on 1,921.
- **Three cells are positive, and none is a result** by the standard the prop
  models were held to (every season positive, interval clear of zero, a
  neighbourhood of cuts, bets in the thousands):
  - Alternates, Pinnacle against a soft book at 6%: +28.1% on 117 bets,
    interval -16.5 to +76.9, median price +525, and 2024-25 alone is +97% on
    32. A few five-to-one winners.
  - Alternates, the model at 4%: +9.9% on 386, interval through zero,
    2023-24 flat, and 2024-25's +32.0% is -0 in its first half and +64 in its
    second.
  - First period, Pinnacle against a soft book at 2%: +19.3% on 160 -- the
    only interval in the run clear of zero (+1.9 to +37.4). But 2023-24 has 14
    bets, the two seasons that carry it split +50 / -9 and -1 / +42 by half,
    and at 4% there are 30 bets. One cell, not a neighbourhood. It is the one
    thing worth reading again when 2026-27 has been priced; it is not a model.
- **Verdict: no cut clears in any of the three, and no total-goals model is
  built.** What would have to change is information the market does not have
  -- a confirmed starting goalie before the number moves is the obvious
  candidate -- and four rounds on the main total found none in the logs.
- The one caveat on the model rows: the main line used is the newest STORED
  one at or before the derivative snapshot, and the stored series is sparse
  (a median of about six hours older). A fresher main line would make the
  model agree with the books more, not less.

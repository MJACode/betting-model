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
| 1st-period moneyline / total | archive `1st` column (not yet stored) | same | none; feed from 2023-05-03 | parked: no price |
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

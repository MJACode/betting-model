# NHL moneyline, rebuilt (2026-10-13)

mike: *"What else is missing in the models. How could you miss schedules like
teams playing on the road ... Look at and rebuild the money line model."*

Scripts: `scripts/nhl_moneyline_rebuild.py` (the harness) and
`scripts/nhl_moneyline_rebuild_checks.py` (baselines and robustness). Both read
the database by game id only, cache what they read outside the repo, and write
nothing. Research only: nothing here is registered or deployed.

## What the live model has, and what it was missing

| What decides NHL games | Live `nhl_moneyline` (20260920_131606) | Rebuild | Removing it from the rebuild (log loss change, + = it helps) |
|---|---|---|---|
| Goals for / against | season-to-date + last 5/10 | EWMA, two speeds | +0.00005 (−0.00023..+0.00033): nothing |
| Shot volume and share, finishing | season Corsi only | shots for/against, 5-on-5 attempt share, shooting % | **+0.00386 (+0.00200..+0.00572)**: the most useful group |
| Shot quality (expected goals) | no | no — not stored yet; being fetched from the free NHL play-by-play | — |
| Special teams, penalty volume | PP %, PK % | PP %, PK %, chances drawn / taken, faceoffs | +0.00079 (−0.00039..+0.00197) |
| Goalie quality | season save %, GAA, GSAA of the **previous game's** goalie at decision time | the starter's shrunk save rate and experience | +0.00002 (−0.00076..+0.00080): nothing |
| Goalie workload / rest | no | days since last start, starts in 7 days, share of starts | **−0.00048 (−0.00078..−0.00018): hurts** |
| Rest, back-to-back, road trip | no | yes | **+0.00162 (+0.00057..+0.00267)**: second most useful |
| Travel distance, time zones | no | yes | +0.00018 (−0.00042..+0.00078) |
| Lineup / injuries | six injury inputs, all dead (no NHL injury data before 2026-04-05) | share of regular ice time that dressed, missing points per game | +0.00060 (−0.00031..+0.00152) |
| Home ice by team | home / road scoring splits | home-ice goal margin by team | −0.00009 (−0.00042..+0.00024) |
| Team rating | no | running goal-margin rating | +0.00006 (−0.00019..+0.00032) |
| The market's price | not an input (used only to decide) | the anchored model starts from it | see below |

The ablation is run on the logistic model without the market, 6,972 games
2021-22 → 2025-26. Rest does nothing in the live tree model
(`docs/nhl_market_lab.md`, the rest test of the same day) and is the second
most useful group here — the model design decides whether an input can be used.

## Method

- Inputs from `nhl_team_game_log`, `nhl_goalie_game_log`, `nhl_skater_game_log`
  and `games`, each built from a team's or goalie's PRIOR games only
  (`scripts/nhl_market_lab2.build` plus four new groups).
- **Timing assumption: a game-day decision with the starting goalie and the
  lineup that played.** The goalie input is built the same way the live
  model's training rows already are; production would need the goalie wait
  (`docs/followups.md`). The lineup input uses who dressed, which production
  cannot know at noon — so it is also graded without it.
- Prices: the bought archive (`odds.source = 'odds_api_historical'`), read by
  game id. **Corrected 2026-10-20:** this line used to say the decision was
  at DraftKings' first game-day quote (the 16:00Z snapshot). The grade
  actually decided at each game's FIRST stored quote, and 95.8% of those are
  dated the day before (median lead about 27 hours). Re-graded with the
  goalies who actually started (scratch `goalie_work/ml_common.out`: as-built
  artifact, EV ≥ 0.06, −200 floor, best price, the games all four timings
  share): the 16:00Z game-day quote +5.08% on 1,588 bets (bootstrap 95%
  +0.3..+10.0), the last pre-game quote +5.21% on 1,633 (+0.6..+10.0). Live,
  the model now decides once both starting goalies are confirmed
  (`docs/sports/nhl.md`, 2026-10-20). "Best" = the best price among
  `config.BEST_LINE_BOOKMAKERS` **in that same snapshot**. Closing-line value = Pinnacle's last pre-game no-vig minus its
  first, on the side taken.
- Walk-forward: each test season is fit only on earlier seasons. The penalty is
  chosen on the training seasons (mean log loss over the last three, each fit
  on the seasons before it). A first run chose it on one season and picked a
  weak penalty for 2025-26, which overfit; that run is superseded.
- Models: a regularised logistic on all inputs; regularised trees; and the
  **anchored model** — the same logistic with DraftKings' no-vig log-odds as an
  unpenalised offset, so the inputs can only move the market's number and with
  no signal they shrink back to it.
- One bet per game, on the side whose EV at the price clears the cut, on the
  model's OWN probability.

## Results

Accuracy on the same 6,972 games (lower is better):

```
market only, DraftKings no-vig      0.66152   (Pinnacle no-vig 0.66037)
all inputs, logistic                0.66257   model - DK +0.00105 (-0.00157..+0.00367)
all inputs, regularised trees       0.66869   model - DK +0.00717 (+0.00375..+0.01059)
anchored (market + all inputs)      0.66093   model - DK -0.00059 (-0.00305..+0.00187)
by season, anchored - DK: 2021-22 -0.0050, 2022-23 +0.0023, 2023-24 -0.0003, 2024-25 -0.0053, 2025-26 +0.0054
```

The anchored model at the best bettable price (units, ROI %, 95% interval, CLV
points, % beating the close, ROI by season with bets):

```
EV>=  bets  units   roi          ci  clv  beat  2021-22      2022-23      2023-24     2024-25      2025-26
0.00  4739  145.4  3.07  +0.5..+5.6  0.64 62.8  +5.9 (926)  +3.4 (1102)  +1.0 (908)  +7.3 (888)  -2.3 (915)
0.02  3578  139.2  3.89  +0.9..+6.9  0.72 64.4  +6.5 (697)  +5.6 (896)   +3.1 (674)  +4.8 (633)  -1.1 (678)
0.04  2573  132.3  5.14  +1.6..+8.7  0.80 65.6  +8.2 (464)  +7.2 (723)   +1.5 (459)  +11.5 (434) -2.9 (493)
0.06  1802  135.0  7.49  +3.2..+11.8 0.88 66.5  +11.7 (307) +5.9 (529)   +3.4 (308)  +20.5 (292) -0.7 (366)
0.08  1189   85.7  7.21  +1.8..+12.6 0.97 67.7  +13.7 (194) +5.1 (366)   -0.5 (205)  +22.1 (179) +0.9 (245)
0.10   755   66.5  8.80  +1.9..+15.7 1.05 68.5  +17.2 (113) +1.2 (264)   +8.7 (128)  +23.6 (115) +4.1 (135)
```

Early / late halves at 0.06: +6.8 / +8.2. At DraftKings' own price instead of
the best: +6.96% on 1,681 at 0.06 (+2.5..+11.4).

Without the lineup inputs (what production can know at noon), best price:

```
EV>=  bets  units  roi   ci           2025-26
0.02  3423  153.9  4.50  +1.5..+7.5   +0.3 (655)
0.04  2415  109.8  4.55  +0.9..+8.2   -3.3 (442)
0.06  1567   85.6  5.46  +0.9..+10.0  -3.2 (291)
0.08   988   48.5  4.91  -0.9..+10.8  +0.3 (178)
```

Baselines on the same games at the best price: always the favourite −2.21%
(−4.1..−0.3), always the underdog −6.18%, always home −4.44%. Inside the
anchored model's bets at 0.06: favourites +4.1% on 1,212 (−0.3..+8.5),
underdogs +14.4% on 590 (+5.0..+23.9) — not a favourite bias.

The model without the market loses less than the live one does but is not
better than the market; the trees lose at every cut.

## Read

- **The anchored rebuild is the first NHL moneyline result in this repo that
  holds on seasons it never saw**: a plateau from EV 0.00 to 0.10 with every
  interval clear of zero at the best price, both halves positive, beating
  Pinnacle's close 63-69% of the time, and 5-10 points better than taking the
  favourite blind.
- **The latest season is the weak one**: 2025-26 is −0.7% to −3.3% at the
  middle cuts in every version. One season of ~300 bets carries about ±11
  points, so it neither confirms nor kills the result; the live run on
  2026-27 is the next measurement. The NHL models are live with the go-live
  gate waived (mike, 2026-10-01, `docs/sports/nhl.md`), so the rebuild goes
  live when it is built, not to paper.
- **Not yet in production.** It needs: the inputs computed by the scoring path
  for tonight's games; the listed starting goalie (the goalie wait); a
  game-day decision at a fixed time against DraftKings' price; its own EV floor
  and its own probability (in the first run, deciding the non-market version
  on the correction the live moneyline model uses lost at every cut up to
  0.10). Expected goals from the play-by-play is the next input group.

## The production version, and two checks on it (2026-10-13/14)

`models/nhl_moneyline_anchored.py` is the code production would run; its walk-forward
(`scripts/nhl_moneyline_anchored_backtest.py`) first reproduced the research grade
game by game (max probability difference 0.0). Then one fix: the goalie save rate
was shrunk toward a league rate computed over ALL seasons, later ones included —
a look-ahead that also made tonight's scoring differ from the training rows in the
fourth decimal. As-of, serving matches training on 9,316 of 9,316 inputs checked.
**The numbers it goes live on** (best bettable price, the production −200 floor,
own probability):

```
EV>=  bets   units   roi   ci            clv   beat
0.02  2752  +127.0  4.62  +1.0..+8.2    0.60  61.0
0.04  2020   +93.5  4.63  +0.4..+8.8    0.63  61.7
0.06  1326   +83.2  6.28  +1.1..+11.4   0.67  62.6
0.08   863   +53.1  6.16  -0.3..+12.6   0.70  62.9
```

The −200 floor removes 238 of 1,564 bets at 0.06 and raises the return. Fit for
production on all six priced seasons: 7,900 games, C = 0.003
(`scripts/nhl_moneyline_anchored_train.py`).

**Shot quality (expected goals) adds nothing.** Every NHL shot 2018-19 → 2026-10-12
is now in `nhl_shot_events` (branch `nhl-shot-events`). Scored walk-forward (each
season by an xG model that never saw it, level-corrected as-of) and added as a
seven-input group, paired log loss on the same 6,973 games moves +0.00009
(−0.00028..+0.00047); the betting grid is lower at EV 0.02-0.04 and higher at
0.06-0.10 with lower CLV at four of five cuts, every interval overlapping. The xG
inputs correlate 0.79-0.88 with the shot and save-rate inputs the model already
has. Not adopted (branch `nhl-moneyline-xg-test`, not pushed).

**How strongly it is held to the market matters.** The penalty sits on the edge of
its pre-set grid (C = 0.003 every season). Widened to 0.0001-0.03, the module's own
validation on the last three seasons prefers C = 0.001 (0.667110 against 0.667601;
the market alone 0.667622) — but the walk-forward run with the wider grid is WORSE
out of sample (log loss 0.66155 against 0.66098) and bets less well: EV 0.02 / 0.04
/ 0.06 / 0.08 return +3.8% / +6.9% / +3.2% / +0.7% on 1,687 / 1,049 / 664 / 420
bets with the floor. The grid was fixed before any result was seen and stays; the
honest size of the edge is a range, roughly +3% to +6% a bet, not the single best
row.

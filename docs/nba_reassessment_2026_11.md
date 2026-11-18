# NBA reassessment, 2026-11-11 to 2026-11-18

The durable record of one piece of work: what was asked, the live record, what was researched and
tested, the two rule changes it produced, and what is still open. NBA only. Results are in units
(one unit to win, risk capped at 3). Every number names the file or command it came from. `<R>` is
the research folder, `C:/Users/micha/Documents/betting-model/data/local/research/nba_research`.

## 1. What was asked

mike, 2026-11-18: *"NBA is bleeding money and we've made no changes to improve the models or find
other edge, I don't care what you have to do, just do it."* The reassessment had been running
since 2026-11-11 without a short summary of what it had tried. This file is that summary.

## 2. The live record it started from

Settled NBA bets, 2026-10-20 to 2026-11-17, units on the posted stake (production `picks`, read
2026-11-18): **221 bets, 100-121, -9.63 units.**

| Model | Record | Units |
|---|---|---|
| `nba_prop_projection` | 44-65 | -4.74 (9-20, -6.44 since 2026-11-12) |
| `nba_prop_market` | 5-10 | -4.75 |
| `nba_team_total_luck` | 16-18 | -4.07 |
| `nba_total_luck` | 15-15 | -1.40 |
| `nba_first_half_total_luck` | 12-7 | +4.06 |
| `nba_live_spread_q12` | 7-6 | +0.27 |
| `nba_q1_trend` | 1-0 | +1.00 |

## 3. What was researched

- **266 ideas already graded here were digested** into one list of what is closed and why
  (`<R>/reassess/closed_models_*.md`, `flagship.md`).
- **Nine research angles were read on the web**: academic work, data sources, the 2026 landscape,
  methods, market microstructure, news, odds vendors, professionals, signals (`<R>/reassess/research_*.md`).
- **42 new ideas were judged**: tried before, would the market let it pay, testable on stored data.
  None was proven; the best scored 5 of 10 for being real (`<R>/reassess/ranked_portfolio.md`).
- **The live record was diagnosed** on 2026-11-12 (`<R>/reassess/live_diagnosis.md`); change 2 came from it.

## 4. The twelve registered backtests

Each was written down and frozen before it was graded, then graded once. Four also had an
independent audit and recomputation. Folders: `<R>/reassess/studies/<name>`; each line is from
that study's own `RESULT.md`, and its `AUDIT.md` and `REPLICATION.md` where it has them.

| Study | What it asked | Result |
|---|---|---|
| `2026-11-14-state-sbro` | Bet the full-game under when league scoring has run under the totals for three weeks, on thirteen older seasons with no prices | No cell passes. The lead cell: 171 bets, 75-96-3, a 43.9% win rate |
| `2026-11-14-state-under` | The same under at real prices, 2021-22 to 2025-26 | One cell clears its bars: 377 bets, +53.23 units, +12.87%. They are the same 377 games already read before the test, and the audit says it does not stand as a reason to build |
| `2026-11-14-luck-conditioning` | Do the shooting-luck models' own backtest bets lose in a known class of game? | No test adopted (five fail, one too few). Full-game overs with a team under 20 games: -21.95 units on 212 bets against +11.24 on 205; the interval of the difference reaches below zero |
| `2026-11-14-prop-yardsticks` | A second fair price (Caesars) beside Pinnacle's for the prop under model | Nothing to build. Where both agree: 1,999 bets, +149.49 units, +7.70%, but it is a subset of what the model already bets, and the audit refutes it as a pass to act on |
| `2026-11-14-prop-calibration` | A corrected fair price for props, fitted on earlier seasons | Both cells fail. The bets it adds: 9,951, +114.97 units, +1.01%, interval -1.07% to +3.17% |
| `2026-11-14-live-house-table` | Hold every live NBA model to the six house bars at seven books; and refuse projection bets Pinnacle's price disagrees with | The refusal fails (difference +5.23 points, interval -0.79 to +11.36). `nba_prop_market` clears six of six. `nba_total_luck` fails two as it bet with no wait and clears six of six with the 10-game wait (508 bets, +55.42 units) |
| `2026-11-14-stale-total` | Bet the book still showing the old total after DraftKings or FanDuel moves | One cell of six clears: 676 bets, +64.73 units, +8.68%. The audit refutes it: 144 of those bets used a copy of the slow book more than 5 minutes old, and they made +26.49 of the units |
| `2026-11-14-shot-quality` | Replace shooting luck with shot quality from the league's shot data | Both cells fail. The over cell, 938 bets, +7.51%, does not beat the live cell on the same games (+10.03% on 508) |
| `2026-11-14-tracking-info` | Free player tracking data as an input to the prop projection | The data lowers the fit error for assists, steals and blocks in both test seasons. No priced cell passes: assists overs -0.46% on 5,685 bets, steals +0.94% on 8,881, blocks unders +3.00% on 5,546 |
| `2026-11-14-prop-timing` | Decide the two prop models 20 minutes before tip instead of 55, on this season's 24 game dates | Information only, nothing passes. The under model made +14.64 units more at 20 minutes on paired games; the interval is -18.7 to +51.5 |
| `2026-11-15-prop-refusals` | Refuse prop bets after a late scratch, on a growing role, or on a scorer in a slump | Five of six fail. The late-scratch refusal would have cost the card 62.99 units over three seasons. The slump refusal cleared by a hair (195 bets, -23.95 units); the audit and the recomputation both say it is too few bets and was read before it was registered |
| `2026-11-18-kalshi-price` | mike said on 2026-11-14 he would bet at Kalshi. Would its price, after its fee, have beaten the sportsbooks on the two prop models' own bets? | No: not worth building for price. The nightly card from 2025-11-18, 745 bets: Kalshi better on 4, +0.15 units (95% interval -0.00 to +0.43). Both models' full lists, 22,126 bets: better on 298, +6.16 units (+4.84 to +7.64). This season's 125 live bets: better on 13, +0.36 units (+0.11 to +0.70). Where Kalshi quoted the bet, its price after the fee was a median 3.84 points of implied chance worse than the sportsbook's on the card |

**Read together:** no new model came out of the twelve. Each of the four cells that passed was
refuted by its own audit as a result to act on. What they did show is which existing bets are weak.

## 5. The two changes made (commit trailer `Updated-By: mike`)

### 5.1 `nba_prop_projection` stops betting threes overs

It keeps threes unders and every other cell. A threes over already written stays, settles and counts.

- **The nightly card** (one prop a game across both prop models, six a night), replayed on
  2023-24 to 2025-26 at the seven deciding books: the model's threes overs are 287 card bets,
  -23.08 units, -12.6%, the only losing cell of size on the card. The card without them makes
  +209.60 units against +190.26 with them: +19.34, 95% interval -19.58 to +60.75, by season
  +15.72 / -6.49 / +10.11. Command: `python <R>/scripts/card_variants_2026_11_18.py`.
- **Off the card**, every qualifying bet at seven books: threes overs +0.93% on 6,828 bets,
  interval -1.5% to +3.4% (seasons +1.8% / -0.1% / +1.4%). Every under cell's interval is above
  zero. Command: `python <R>/scripts/proj_by_market_7books.py` (run from `<R>`).
- **Live**: 26 of the model's 109 settled bets (24%) were threes overs, 9-17, -0.64 units, median
  price +158.5 (production `picks`, read 2026-11-18). They are 8.8% of its graded bets
  (6,828 of 77,671). The card ranks by claimed EV, and this cell's claim is the most inflated.
- **How sure:** not proven. The card gain's interval spans zero. Three separate readings point
  the same way, and nothing measured says the cell earns its place.
- **Prices the model lays after the change** (`python <R>/scripts/proj_prices_after_2026_11_18.py`):
  every qualifying bet, min -200, 5th percentile -166, median +105, 95th +165, max +375 (it was +3000:
  that tail was threes overs at 0.5 from one book). Its bets on the nightly card: -194 to +330, median +125.
- **Built how:** the threes cell lists the under only (`models/nba_prop_projection._SIDES`), so
  the over is never offered. No artifact was refitted: the calibration map is per market, not per
  side. The percentile table that shares a night between the two prop models is unchanged,
  because the replay above ranked with it (`models/nba_prop_rank.py`). At most 26 of 51,418
  stored threes propositions could clear the floor on both sides, so the replay and the live
  code differ on almost no bet (`<R>/scripts/threes_both_sides_2026_11_18.py`).

### 5.2 The three shooting-luck total models wait for 10 games again

`nba_total_luck`, `nba_first_half_total_luck` and `nba_team_total_luck` bet no game until both
teams have played 10 games this season. **This reverses mike's instruction of 2026-11-02, on his
instruction of 2026-11-18.**

- **Live, with no wait:** of the three models' first 56 settled bets (through the 2026-11-10
  slate), 50 had a team under 10 games: 21-29, -11.10 units. The other 6 went 5-1, +3.85
  (`<R>/reassess/live_diagnosis.md`, section 3.1).
- **Live, once every team had 10 games** (the fewest any team had played before 2026-11-12 was 10;
  production `games`, read 2026-11-18): 15-6, +8.38 units from 2026-11-12 to 11-17. Full game 7-2,
  +4.81; first half 4-1, +2.85; home team total 4-3, +0.72 (production `picks`). Small sample.
- **The backtest never showed an edge on those games:** the bets the wait keeps out returned
  -0.14% on 211, +4.50% on 80 and -0.03% on 150 (`docs/sports/nba.md`, the replay table). On
  seasons never split this way the direction is the same and not solid (luck-conditioning, above).
- **The house bars:** with no wait the three models fail two, one and three of the six bars at
  seven books. With the wait the full-game model clears all six: 508 bets, +55.42 units
  (study `2026-11-14-live-house-table`).
- **What it changes today:** nothing this season (every team is past 10 games). It stops the same bets next October.
- **Built how:** one number, `models/nba_total_luck.LIVE_MIN_GAMES`, back to 10. A game held for
  the wait is written to the model's decisions table with the reason `early_season`, as it was
  before 2026-11-02. The backtest replays always passed the 10-game population themselves.

## 6. What the data says is the engine

The nightly prop card is where the tested profit is: **2,638 bets, +190.26 units, +8.44%** on
2023-24 to 2025-26 at seven books (`card_variants_2026_11_18.py`). The projection model's unders
are 1,502 of those bets and +173.41 of those units (`proj_prices_after_2026_11_18.py`). Live they
have not paid yet: threes unders 10-17, -4.39 units; rebounds unders 2-9, -6.21 (production
`picks`). Four weeks against three seasons: no change was made to them.

## 7. Leads still open

- **The slow book's total.** On paper a number 1.5 or more points better than the market is worth
  about +2% to +3% a bet. Stored 5-minute rows cannot show it can be bet. The clean test is forward
  on 2026-27, with the slow book read fresh at the decision (`2026-11-14-stale-total/AUDIT.md`).
- **The prop bets Kalshi also lists.** Seen after the Kalshi grade, and not registered. On both
  prop models' full backtest lists for 2025-26 from 2025-11-18, graded at the sportsbooks, the
  bets on a player and line Kalshi also listed returned -1.0% on 4,123 bets. The rest returned
  +4.1% on 18,003. The difference is -5.1 points (95% interval -8.6 to -1.4). This season's 124
  graded live bets point the other way on a small sample. It is a lead to register, not a finding
  (`<R>/reassess/studies/2026-11-18-kalshi-price/RESULT.md`, section 5.4).
- **Tracking data in the projection.** It improves the fit for assists, steals and blocks and no
  priced cell passed. The next test is a refit on a longer history, steals first.
- **A later prop decision time.** Not settled by 24 game dates; about 151 are needed for the
  under model's difference to be told from zero (`2026-11-14-prop-timing/RESULT.md`).

## 8. Data gaps found

- **Four NBA tables have no 2026-27 rows:** the enriched box scores (`nba_player_game_adv`), the
  inactive lists (`nba_game_inactives`), the referee crews (`nba_game_officials`) and the league's
  official injury report (`nba_injury_report`, last report 2026-05-10). A model built on any of
  them cannot run live until its feed is restarted (`<R>/reassess/data_inventory.md`, section 1).
- **The tracking pull is stored only on mike's PC**: 5,110 files, 79.8 MB, under
  `<R>/cache/tracking`. It has to go into Supabase before anything is built on it (CLAUDE.md
  §1b). This work was not allowed to write to production, so that import is still to do.

## 9. Where the research files are

Under `<R>`, on mike's PC and not in git: `reassess/` (the digests, research notes, ranked ideas,
live diagnosis, and `studies/`, one folder a backtest), `scripts/` (every script named here) and
`cache/` (the prices the backtests read). The rules now: `docs/sports/nba.md`. The settings: `docs/thresholds.md`.

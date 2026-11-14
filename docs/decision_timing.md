# Decision timing, measured per model

## The rule (mike, 2026-11-14)

When a model decides is a per-model parameter, chosen by out-of-sample
expected units. "Decide once at a fixed time" and "check every refresh until
it bets" are both candidates; neither is a blanket rule. The pick rule
(CLAUDE.md §1c) locks a BET once it is made. It says nothing about freezing a
game that did not bet, so "EACH GAME DECIDED ONCE (CLAUDE.md 1c)" in a card is
a timing choice, not the pick rule. The method and the hockey evidence for
replaying at the live check rate are in the league-models skill
(`.claude/skills/league-models/references/porting-traps.md`, "When the model
decides").

**No live model's timing changes until mike has seen its result.**

## How a timing is measured

1. Replay the card's own read and decision (never a re-implementation) at
   every candidate time the stored prices allow: each fixed hour, every check
   until it bets with the first BET locking, and the last read before the
   start.
2. Choose the timing on the early seasons; read the chosen one alone on the
   last season. Count the timing as a searched parameter: Benjamini-Hochberg
   over every candidate's one-sided bootstrap p-value on the selection seasons.
3. Report per timing: games in scope, games priced, bets, units by season,
   return with its 95% interval (bet dates resampled), the chance of a
   positive season (a season's worth of bet dates resampled), and CLV against
   Pinnacle's no-vig close.
4. **Clears** means: the timing chosen on the selection seasons survives
   Benjamini-Hochberg at q 0.10 there, and on the last season alone makes
   positive units with a one-sided bootstrap p of 0.10 or less. For the NCAAF
   moneyline this was written down on 2026-11-14 before its 2024 and 2025
   hours were read (only a 2023 trial had run). If no timing clears, say so.
   Never hand the model its best-looking hour.

## The NCAAF moneyline model (`ncaaf_moneyline_market`)

The first replay: `scripts/ncaaf_moneyline_timing.py` (tests:
`tests/test_ncaaf_moneyline_timing.py`). It needs every hour of 2023-2025, so
mike approved the purchase on 2026-11-14 (*"Buy all of it now"*): worker jobs
1316678, 1316679 and 1316680 (keys `ncaaf-hourly-history-2023`, `-2024`,
`-2025`), every hour 00-23 UTC, moneyline and spread, the ten fetched books,
20 credits a snapshot (measured in `api_call_log`), at most 152,640 credits.
The new rows come to mike's PC through `scripts/ncaaf_hourly_extract.py`,
which reads only them, by row id, in throttled slices (a by-hand run of the
nightly copy would re-count the whole `odds` table against production).

**The replay matches the live card.** On the prices stored before the
purchase (14:00 and 23:00 UTC daily), its 14:00 UTC timing holds all 311 of
the research's bets: same game, side, book and price, +14.70 units. Its 23:00
timing holds 110 of the research's 114 evening bets; the other 4 kick off
23:00-23:03 UTC, inside the card's five-minute rule.

**Result (2026-11-14): no timing clears.** The live 14:00 UTC check is the
timing chosen on 2023-2024 (+13.88 units, one-sided p 0.097), but no timing
survives Benjamini-Hochberg at q 0.10, and on 2025 alone the 14:00 check made
+0.81 units on 93 bets (+1.4%, interval -21.0% to +23.0%, p 0.46). No other
hour did better on 2023-2024, so the selection keeps 14:00; and with nothing
clearing, there is no evidence for any hour over another.

- **14:00 UTC, all three seasons:** 311 bets, +14.70 units, +7.8% (interval
  -4.9% to +21.7%), prices +110 to +430 (median +146), 294 road teams; early
  halves +5.29, late halves +9.40 units. These are the research's 311 bets,
  game for game.
- **Its neighbours:** 13:00 UTC made +15.81 units over the three seasons
  (+11.91 on 2023-2024, +3.90 on 2025) on the same number of bets, but
  laid prices up to +2500; 12:00 made +7.53 and 15:00 +3.67. Two adjacent
  hours, not a plateau.
- **Every hour until it bets** (the first BET locks): 951 bets, three times
  as many as 14:00, +8.32 units, +1.6% (interval -6.1% to +9.7%); 2023
  -8.28, 2024 +20.11, 2025 -3.52. It lays -194 to +4500 (median +180), and
  the card's price and EV floors refuse 10 of its bets. The same pattern as
  the hockey regulation moneyline: checking more often finds more bets, not
  better ones.
- **The last read before kickoff:** 356 bets, -1.71 units.
- **After 20:00 UTC** every fixed hour loses on 2023-2024 (fewer games are
  still to kick off).
- **CLV against Pinnacle's no-vig close:** at every fixed hour the bet price
  averages 3% to 4% below the close (14:00: -3.83%, beating the close on
  22.9% of bets). The market moves against these bets after the check. Only
  "every hour until it bets" is near even (-0.35%, 44.6% beat), because it
  bets earlier and at longer prices.
- **Fidelity checks:** at 14:00 the replay holds all 311 research bets (same
  game, side, book and price; largest edge difference 0.0); at 23:00, 110 of
  the research's 114 evening bets, the other 4 kicking off 23:00-23:03 UTC,
  inside the card's five-minute rule. Every bought row's own stamp is within
  a minute of its pull at every UTC hour (median 0.4-0.8 minutes), so no
  quiet hour is thinned by the card's 60-minute window. One real gap: the
  replay's check at hour H reads a snapshot taken about a minute before H;
  the live card at H:05 reads the refresh stored at about H-1:16, some 50
  minutes older.

**Three replay fixes the first full run found** (each pinned by a test in
`tests/test_ncaaf_moneyline_timing.py`):

1. A row's stamp is the market's own last update, so a later pull can hold a
   row stamped before the check. Each check reads only pulls taken by it. On
   these seasons it changed none of the 458,320 decisions (the stamps sit
   within a minute of their pull).
2. The feed listed the 2025-08-23 Iowa State and Kansas State game (Dublin)
   under one home team until 08-21 and the other after. Keeping one id per
   game over the whole history lost a research bet; the replay now decides,
   at each check, the id with more quotes in the hour, as the card does, and
   either id's first BET locks the game.
3. The purchase itself had overwritten the stored kickoff of 1,690 rows of
   2023-2025 games (below). The replay reads kickoffs as they stood before it.

**Every timing** (units are 1 unit to win, risk capped at 3, after the card's
price and EV floors; intervals resample bet dates; "chance of a positive
season" resamples a season's worth of the timing's own bet dates):

**Selection seasons, 2023-2024** (the timing is chosen here):

| Timing | Games in scope | Priced | Bets | 2023 units | 2024 units | Units | Return | 95% interval | p (return <= 0) | Chance of a positive season | CLV vs Pinnacle close | Beat the close |
|-|-|-|-|-|-|-|-|-|-|-|-|-|
| 00:00 UTC | 1572 | 1526 | 227 | +5.39 | +2.38 | +7.77 | +5.7% | -7.7 to +19.2 | 0.2167 | 0.716 | -3.41% | 0.261 |
| 01:00 UTC | 1575 | 1528 | 224 | +3.71 | +3.49 | +7.20 | +5.3% | -7.6 to +19.7 | 0.2303 | 0.704 | -3.47% | 0.26 |
| 02:00 UTC | 1576 | 1529 | 224 | +3.81 | -0.05 | +3.77 | +2.9% | -11.8 to +18.4 | 0.3645 | 0.604 | -3.42% | 0.265 |
| 03:00 UTC | 1578 | 1531 | 223 | +3.83 | +2.02 | +5.85 | +4.5% | -9.6 to +19.7 | 0.2565 | 0.665 | -3.4% | 0.266 |
| 04:00 UTC | 1577 | 1531 | 221 | +2.95 | +2.36 | +5.31 | +4.1% | -9.5 to +18.7 | 0.2923 | 0.662 | -3.35% | 0.264 |
| 05:00 UTC | 1578 | 1531 | 220 | +0.64 | +4.82 | +5.47 | +4.2% | -9.6 to +20.3 | 0.279 | 0.649 | -3.3% | 0.26 |
| 06:00 UTC | 1579 | 1531 | 219 | +2.61 | +5.08 | +7.70 | +6.0% | -7.2 to +20.9 | 0.2105 | 0.727 | -3.07% | 0.271 |
| 07:00 UTC | 1579 | 1531 | 218 | +2.14 | +4.23 | +6.37 | +5.0% | -8.5 to +19.5 | 0.2288 | 0.685 | -3.23% | 0.267 |
| 08:00 UTC | 1579 | 1531 | 212 | +3.72 | +7.01 | +10.72 | +8.6% | -5.4 to +23.9 | 0.1182 | 0.799 | -3.37% | 0.261 |
| 09:00 UTC | 1579 | 1530 | 213 | +1.62 | +7.95 | +9.57 | +7.7% | -6.4 to +22.9 | 0.1435 | 0.776 | -3.38% | 0.255 |
| 10:00 UTC | 1578 | 1530 | 215 | +0.00 | +6.93 | +6.93 | +5.5% | -8.7 to +20.6 | 0.2283 | 0.685 | -3.4% | 0.257 |
| 11:00 UTC | 1579 | 1532 | 215 | +0.14 | +5.42 | +5.56 | +4.4% | -10.6 to +19.8 | 0.2745 | 0.663 | -3.46% | 0.252 |
| 12:00 UTC | 1578 | 1532 | 213 | +0.75 | +5.56 | +6.30 | +5.0% | -8.8 to +20.7 | 0.245 | 0.685 | -3.49% | 0.259 |
| 13:00 UTC | 1578 | 1537 | 209 | -0.71 | +12.62 | +11.91 | +9.6% | -6.1 to +28.0 | 0.1298 | 0.776 | -3.51% | 0.255 |
| 14:00 UTC (live) | 1505 | 1467 | 218 | -2.77 | +16.66 | +13.88 | +10.7% | -5.0 to +27.4 | 0.0968 | 0.827 | -3.75% | 0.253 |
| 15:00 UTC | 1623 | 1566 | 231 | +0.55 | +6.40 | +6.95 | +5.2% | -7.7 to +19.0 | 0.2233 | 0.712 | -3.78% | 0.243 |
| 16:00 UTC | 1439 | 1389 | 194 | +4.67 | +4.12 | +8.78 | +7.6% | -7.2 to +22.2 | 0.1588 | 0.765 | -3.37% | 0.223 |
| 17:00 UTC | 1360 | 1306 | 183 | +1.19 | +3.66 | +4.86 | +4.5% | -9.2 to +18.6 | 0.2687 | 0.688 | -3.32% | 0.198 |
| 18:00 UTC | 1317 | 1267 | 180 | +2.69 | +3.89 | +6.58 | +6.2% | -9.0 to +21.8 | 0.211 | 0.706 | -3.92% | 0.145 |
| 19:00 UTC | 1264 | 1205 | 173 | +0.57 | +8.62 | +9.19 | +9.1% | -5.6 to +24.7 | 0.111 | 0.798 | -3.86% | 0.122 |
| 20:00 UTC | 949 | 904 | 127 | -3.40 | +6.85 | +3.44 | +4.5% | -13.6 to +23.9 | 0.3135 | 0.641 | -3.71% | 0.167 |
| 21:00 UTC | 801 | 760 | 99 | -5.53 | +4.74 | -0.79 | -1.3% | -20.8 to +20.2 | 0.5437 | 0.471 | -3.68% | 0.112 |
| 22:00 UTC | 740 | 707 | 94 | -3.05 | +1.44 | -1.62 | -3.0% | -28.1 to +23.7 | 0.5883 | 0.431 | -3.91% | 0.108 |
| 23:00 UTC | 492 | 487 | 67 | -7.82 | +5.58 | -2.25 | -5.7% | -37.3 to +29.3 | 0.6305 | 0.411 | -4.23% | 0.075 |
| every hour until it bets | 1664 | 1593 | 642 | -8.28 | +20.11 | +11.83 | +3.5% | -6.1 to +13.3 | 0.2415 | 0.7 | -0.69% | 0.457 |
| last read before kickoff | 1664 | 1593 | 245 | -5.71 | +8.84 | +3.12 | +2.2% | -10.7 to +15.2 | 0.377 | 0.591 | -3.8% | 0.123 |

**Confirmation season, 2025** (read after the choice):

| Timing | Bets | Units | Return | 95% interval | p (return <= 0) | CLV vs Pinnacle close |
|-|-|-|-|-|-|-|
| 00:00 UTC | 106 | +2.44 | +3.7% | -16.2 to +21.3 | 0.3317 | -4.43% |
| 01:00 UTC | 105 | +2.74 | +4.2% | -17.1 to +23.5 | 0.3417 | -4.19% |
| 02:00 UTC | 105 | +0.96 | +1.5% | -18.3 to +20.5 | 0.4482 | -4.15% |
| 03:00 UTC | 105 | -1.04 | -1.6% | -22.3 to +17.3 | 0.5683 | -3.84% |
| 04:00 UTC | 106 | -1.34 | -2.1% | -22.1 to +17.0 | 0.5805 | -3.95% |
| 05:00 UTC | 103 | -1.37 | -2.1% | -22.3 to +14.5 | 0.601 | -4.07% |
| 06:00 UTC | 99 | +1.76 | +2.8% | -19.9 to +22.9 | 0.392 | -3.87% |
| 07:00 UTC | 104 | -0.99 | -1.5% | -22.2 to +17.9 | 0.574 | -4.02% |
| 08:00 UTC | 105 | -1.26 | -1.9% | -23.7 to +16.8 | 0.5877 | -3.96% |
| 09:00 UTC | 102 | -0.08 | -0.1% | -23.0 to +18.9 | 0.5145 | -3.89% |
| 10:00 UTC | 102 | +1.79 | +2.8% | -19.2 to +22.7 | 0.3947 | -3.79% |
| 11:00 UTC | 105 | +1.70 | +2.6% | -18.4 to +20.7 | 0.3867 | -3.71% |
| 12:00 UTC | 101 | +1.22 | +1.9% | -18.4 to +19.2 | 0.421 | -3.9% |
| 13:00 UTC | 102 | +3.90 | +6.1% | -12.1 to +24.9 | 0.2435 | -3.89% |
| 14:00 UTC (live) | 93 | +0.81 | +1.4% | -21.0 to +23.0 | 0.4592 | -4.02% |
| 15:00 UTC | 102 | -3.27 | -5.2% | -30.4 to +22.1 | 0.6585 | -3.78% |
| 16:00 UTC | 82 | -1.77 | -3.5% | -33.5 to +27.4 | 0.6082 | -3.66% |
| 17:00 UTC | 70 | -4.42 | -10.2% | -41.3 to +26.7 | 0.7222 | -3.73% |
| 18:00 UTC | 64 | -1.39 | -3.5% | -37.0 to +33.4 | 0.6012 | -3.2% |
| 19:00 UTC | 66 | +1.63 | +4.1% | -26.4 to +38.3 | 0.414 | -0.6% |
| 20:00 UTC | 48 | -1.40 | -4.6% | -40.8 to +37.5 | 0.6048 | -3.71% |
| 21:00 UTC | 45 | -0.71 | -2.6% | -42.6 to +41.8 | 0.5493 | -3.64% |
| 22:00 UTC | 48 | -1.94 | -6.3% | -40.2 to +33.0 | 0.6308 | -3.19% |
| 23:00 UTC | 43 | +0.69 | +2.6% | -39.3 to +45.3 | 0.4582 | -0.1% |
| every hour until it bets | 309 | -3.52 | -2.0% | -14.0 to +11.3 | 0.632 | 0.34% |
| last read before kickoff | 111 | -4.83 | -7.1% | -29.5 to +19.8 | 0.706 | -2.48% |

**What the purchase broke, and the repair.** `run_historical_odds_range`
upserted every snapshot's games, so each snapshot set `commence_time` and
`data_source`. A backfill's snapshots do not arrive in time order: the fill
jobs ran last with early-week snapshots that still carried placeholder times
(Florida at Miami 2025-09-20 went from 23:30 to 16:00 UTC), and post-start
snapshots list the actual start (most of the changes, a few minutes each).
1,690 rows of 2023-2025 games changed kickoff, and CFBD's scored rows among
them had `data_source` set to `live`. The ingestor now lets a history
snapshot set a stored kickoff only inside the 24 hours before the kickoff it
lists, before the game starts, and otherwise only insert a missing game
(`_history_game_rows`). `scripts/restore_ncaaf_kickoffs_20261114.py` put
the 1,690 rows back from the local copy taken at 05:43 UTC that morning,
keeping both values in `games_ncaaf_kickoff_restore_20261114` (row security
on); applied 23:29 UTC, 0 rows still differing. The 116 games the purchase
added keep the kickoff it wrote.

## The inventory of every other model (2026-11-14)

Read only: no paid call, no job. Credits are the arithmetic in
`scripts/decision_timing_inventory_costs.py`, on counts measured that day.
"Missing" means missing at the model's live check rate.

**The facts it rests on, measured:**

- **Refresh passes: 53 per Eastern day.** At :17 past each hour from midnight
  to 4am (5), the 6:00am daily (1), at :17 from 7am to 5pm (11), and every 10
  minutes from 6:00pm to 11:50pm (36) (`docs/cloud_worker.md`, `scheduler.py`).
  The 30-second DraftKings poller also re-scores the MLB, WNBA, NCAAF, UFC and
  NFL game models on any DraftKings change; no history is that fine, so those
  models are priced on the refresh grid.
- **The historical feed's step:** 10 minutes through September 2022, 5 minutes
  from October 2022 (the tennis, NCAAB in-play and EuroLeague ledgers).
- **Billing:** a bulk snapshot is 10 credits a market at up to ten books; a
  per-game call is 10 a market that comes back, and an empty reply costs 0
  (`euroleague_period_fetches`, `ncaaf_derivative_fetches`). Per-game figures
  are ceilings.
- **Balance when read:** 1,779,544 credits (`odds_api_quota`, 18:56 UTC).

**Credits to buy every gap, by sport** (a purchase shared by models counted
once):

| Sport | Credits |
|-|-|
| NBA | 13,653,110 |
| MLB | 10,621,120 |
| NCAAB | 7,589,550 |
| NHL | 7,106,510 |
| NFL | 4,650,550 |
| Tennis | 1,994,390 |
| NCAAF | 853,200 |
| WNBA | 829,300 |
| UFC | 505,770 |
| EuroLeague | 15,360 |
| NCAABW | 0 |
| **Total** | **47,818,860** |

32,465,960 of the total is per-game calls (ceilings). Not included: the MLB
prop models' 2024-2025 holdout seasons, which hold no stored prices
(1,134,970 a model, 11,349,700 for the ten). The NCAAF figure was counted
while the hourly purchase was still running, and falls as its hours land.

**Replayable today at the live check rate, with no purchase (16 models):**
`mlb_live_total_runs` (2025, 5 minutes), `nba_live_spread_q12`,
`ncaab_spread_market`, `ncaab_moneyline_own_spread`, `ncaab_live_spread_h1`,
`ncaab_live_spread_h2`, `ncaab_live_total_h2`, `ncaabw_total_blend`,
`ncaabw_live_total_ht`, `ncaaf_live_total` and `ncaaf_live_win_prob` (2025,
DraftKings only), `nfl_live_leader_ml`, `euroleague_home_ml`,
`euroleague_home_dog_spread`, `euroleague_live_spread_ht`, and
`ufc_open_moneyline` (its noon rule only).

**Replayable today on a coarser grid:** the MLB and WNBA scorer and prop
models (2026, DraftKings only); the NCAAB first-post models (half-hour); the
NCAAB first-half models (4 of their 9 live fetch times); the EuroLeague
period models (their 8 stored times); tennis and `nba_total_luck` (hourly);
NCAAF and NHL (twice daily); the NFL opener and wind models (every 6 hours).

### Per model

P marks a paused model.

**MLB.** Scorer models run on the daily, every refresh pass and the poller;
the first BET locks; each is scored at DraftKings' line, then re-decided at
the best price. Prop models run in `prop-scoring` on the daily and every
refresh pass. Live game-line and prop rows of books other than DraftKings are
thinned to opener, close and newest after 2 days. Refresh passes per season
2021-2026: 11,819 / 11,978 / 11,872 / 12,296 / 12,508 / 11,554; held
snapshots 183 / 183 / 183 / 187 / 186 / 148.

| Model | P | Decides today | Stored history | Missing | Credits | Replay today |
|-|-|-|-|-|-|-|
| mlb_moneyline | | scorer, with starter, schedule, injury and market-move gates | 22Z daily 2021-04 to 2026-08-26; 12Z 2024-03 to 2026-08-26; DraftKings live path 2026 | h2h 2021-2026: 70,957 snapshots | 709,570 | Partly: 2026 at DraftKings |
| mlb_runline | P | scorer | as above, spreads | 70,957 | 709,570 | Partly |
| mlb_over_under | P | scorer | as above; no totals bought before 2024 | 71,506 | 715,060 | Partly |
| mlb_f5_moneyline | | scorer | never bought (no bulk first-five markets); DraftKings live 2026-05-10 to 09-19 | 2026 other books, per game: 56,518 | 565,180 ceiling | Yes at DraftKings, 2026 |
| mlb_f5_over_under | P | scorer | backtests used synthetic lines; DraftKings never quotes it | 2024-2025 per game: 113,497 | 1,134,970 ceiling | No |
| mlb_f5_runline | P | scorer | as above | as above | 1,134,970 ceiling | No |
| mlb_spread_market | | card on the daily and every refresh pass, inserted once | Pinnacle and soft books at 12Z and 22Z to 2026-08-26 | 2026 spreads: 11,406 | inside mlb_runline's | No |
| mlb_total_market | | as above | as above, totals | 2026 totals: 11,406 | inside mlb_over_under's | No |
| mlb_total_public_fade | | card, on the last public-betting row before the start | `public_betting` keeps only the last row, no time series | ticket shares are not sold by the odds feed | 0 | No |
| mlb_live_total_runs | | live loop, about 7 seconds a pass | 2025 DraftKings in-play totals about every 5 minutes; 2026 own feed | none at the feed's 5-minute step | 0 | Yes |
| mlb_prop_batter_runs | | `prop-scoring`, confirmed lineup | DraftKings path from about 2026-04; Pinnacle from 2026-08-27 | 2026 other books per game: 56,518 | 565,180 ceiling | Yes at DraftKings, 2026 |
| mlb_prop_batter_walks | | as above | as above | as above | 565,180 | as above |
| mlb_prop_batter_hits | P | as above | as above | as above | 565,180 | as above |
| mlb_prop_batter_tb | P | as above | as above | as above | 565,180 | as above |
| mlb_prop_batter_sb | P | as above | as above | as above | 565,180 | as above |
| mlb_prop_pitcher_k | P | `prop-scoring`, probable starter, up to 47.8 h ahead | as above | as above | 565,180 | as above |
| mlb_prop_pitcher_hits | P | as above | as above | as above | 565,180 | as above |
| mlb_prop_pitcher_outs | P | as above | as above | as above | 565,180 | as above |
| mlb_prop_pitcher_er | P | as above | as above | as above | 565,180 | as above |
| mlb_prop_pitcher_walks | P | as above | as above | as above | 565,180 | as above |

**WNBA.** Nothing was ever bought. DraftKings lines are kept live from
2026-05-31 and props from 2026-06-01, each with the full path; other books
thinned. Refresh passes 6,678 (2025) and 9,222 (2026).

| Model | P | Decides today | Stored history | Missing | Credits | Replay today |
|-|-|-|-|-|-|-|
| wnba_moneyline | | scorer plus poller | DraftKings, 2026 | h2h 2025-2026: 15,900 | 159,000 | Partly |
| wnba_over_under | P | as above | as above | 2026: 9,222 | 92,220 | Partly |
| wnba_spread | P | as above | as above | 2026: 9,222 | 92,220 | Partly |
| wnba_prop_market | | card every refresh pass, inserted once | Pinnacle and DraftKings kept; other books thinned | 2026 from 08-27: 2,002 passes x 3 markets | 60,060 ceiling | No |
| wnba_prop_player_assists | | `wnba-prop-scoring`, today's games | DraftKings path, 2026 | 2026 other books per game: 8,516 | 85,160 ceiling | Yes at DraftKings, 2026 |
| wnba_prop_player_rebounds | | as above | as above | as above | 85,160 | as above |
| wnba_prop_player_pra | | as above | as above | as above | 85,160 | as above |
| wnba_prop_player_points | P | as above | as above | as above | 85,160 | as above |
| wnba_prop_player_threes | P | as above | as above | as above | 85,160 | as above |

**NBA.** Bought h2h, spreads and totals at 10 books, 15Z to 23Z and 0Z to 4Z,
on 956 dates 2020-12 to 2026-04, plus gap fills; per-game history is one
snapshot 45-75 minutes before tip, 2023-24 to 2025-26. `games` holds no
playoff games, so these counts leave them out. Game-day passes before tip:
104,946, minus 3,690 held: 101,256.

| Model | P | Decides today | Stored history | Missing | Credits | Replay today |
|-|-|-|-|-|-|-|
| nba_total_luck | | once, on its own fetch 60-66 min before tip | bulk totals hourly on game days, 2020-21 to 2025-26 | 56,074 passes, 7,091 held: 48,983 | 489,830 | Partly: hourly; 2026-27 at the full refresh cadence |
| nba_first_half_total_luck | | once, own fetch 45-66 min | one snapshot a game | per game: 101,256 | 1,012,560 ceiling | No |
| nba_team_total_luck | | as above | as above | as above | 1,012,560 | No |
| nba_q1_trend | | as above | as above | as above | 1,012,560 | No |
| nba_q1_trend_ml | | same fetch as nba_q1_trend | as above | as above | 1,012,560 (both: 2,025,120) | No |
| nba_prop_market | | once, first look 45-57 min before tip, at most 6 a night | one snapshot a game; 2026-27 soft books thinned | 101,256 x 5 markets | 5,062,800 ceiling | No |
| nba_prop_projection | | in the same look | as above | 101,256 x 6 markets | 6,075,360 (both, 9 markets: 9,113,040) | No |
| nba_live_spread_q12 | | first fresh quote a game; fetches each hour minus 264 s | in-play rows from the hourly pulls, 2020-21 to 2025-26 | none (the live check is hourly) | 0 | Yes |

**NCAAB and NCAABW.** NCAAB game lines were bought every UTC hour on about
902 dates, 2020-21 to 2025-26; the purchase kept each book's first quote, two
anchors (22Z the day before, 15Z on game day), the last 3 hours before tip,
and every change on a half-hour grid inside 72 hours of tip. The 5-minute
grid inside 72 hours (10-minute in the first two seasons): 221,040 instants,
43,399 held, 177,641 missing. NCAAB history is bought only by the dedicated
buyer (`run_historical_odds_range` refuses NCAAB).

| Model | P | Decides today | Stored history | Missing | Credits | Replay today |
|-|-|-|-|-|-|-|
| ncaab_total_blend | | once, at DraftKings' first posted total while it stands; card every 5 min | totals, half-hour inside 72 h | 177,641 | 1,776,410 | Half-hour yes, 5 min no |
| ncaab_moneyline_first_post | | once, within a minute of a book's first moneyline | h2h and spreads, half-hour inside 72 h | 177,641 x 2 markets | 3,552,820 | Half-hour yes, 5 min no |
| ncaab_spread_market | | once, 15:00 UTC; the card runs hourly | the 15Z anchor at every book; every change at half-hour inside 72 h | none | 0 | Yes |
| ncaab_moneyline_own_spread | | once, 15:00 UTC | as above | none | 0 | Yes |
| ncaab_first_half_spread | | once, on the fetch 10 min before tip | per game at 15Z, 18Z, tip minus 60 and minus 10, 2023-24 to 2025-26 | 6 live fetch times x 18,836 games | 1,130,160 ceiling | Partly: 4 of 9 times |
| ncaab_first_half_total | | once, on the fetch 60 min before tip | as above | as above | 1,130,160 ceiling | Partly |
| ncaab_live_spread_h1 | | first eligible fetch; fetches at :00 and :30 | in-play at 5, 30 and 60 min steps, 2020-21 to 2025-26 | none | 0 | Yes |
| ncaab_live_spread_h2 | | as above | as above | none | 0 | Yes |
| ncaab_live_total_h2 | | as above | as above | none | 0 | Yes |
| ncaabw_total_blend | | once, at DraftKings' first posted total; card every 5 min | every served snapshot, about 5 min apart, 2024-11-12 to 2026-11-09, 17 books | none | 0 | Yes |
| ncaabw_live_total_ht | | first eligible 5-minute read of the break | every in-play quote | none | 0 | Yes |

**NCAAF.** Scorer models run on the daily, every refresh pass and the poller,
with no lead limit. Stored: 14Z and 23Z daily for 2023-2025 at 11 books, and
the hourly purchase above. Refresh passes counted 7,632 (2022), 7,632 with 600
held (2023, mid-purchase), 8,268 with 108 held (2024 and 2025 each).

| Model | P | Decides today | Stored history | Missing | Credits | Replay today |
|-|-|-|-|-|-|-|
| ncaaf_over_under | | scorer; 8-point gap from DraftKings; waits for a forecast | as above | totals 2022-2025: 30,984 | 309,840 | Partly: twice daily |
| ncaaf_spread | | scorer; both openers within 90 minutes of each other | as above | spreads 2023-2025: 23,352 | 233,520 (covers both spread models) | No, except 2023-08-17 to 09-17 |
| ncaaf_spread_premium | | same rule, gap 2.5 points or more | as above | same purchase | inside ncaaf_spread's | No |
| ncaaf_moneyline | P | scorer | as above | h2h 2022-2025: 30,984 | 309,840 | Partly |
| ncaaf_live_total | | first signal a game (`ncaaf_live/serve.py`) | 2025 DraftKings in-play h2h and totals, about every 5 min | none for its season | 0 | Yes, DraftKings only |
| ncaaf_live_win_prob | | as above | as above | none | 0 | Yes, as above |

**NFL.** Pre-game history is the file cache `nfl/data/odds_cache` (6,777
snapshots): spreads 2020-2025, totals and h2h 2023-2025, mostly every 6 hours
from 7 days to 2 days out, plus Tuesday 18Z and the closes. Props per game at
open, 72, 48, 24 and 1 hours out, 2023-2025.

| Model | P | Decides today | Stored history | Missing | Credits | Replay today |
|-|-|-|-|-|-|-|
| nfl_opener_spread | | polls every minute 10 to 2 days out; first qualifying tick | as above; 2026 every minute at 12 books | at the served step: 223,357 minus 3,274 held | 2,200,830 | Partly: every 6 hours |
| nfl_wind_totals | | hourly inside 10 days, every 10 min inside 3 h; fires only inside 4 days | totals 2023-2025; issued forecasts from 2024-01-18 | own cadence 2024-2025: 10,789 minus 1,089 | 97,000 | Partly |
| nfl_live_leader_ml | | first qualifying 5-minute slot | in-play every 5 min, 2024-2025, 10 books | none | 0 | Yes |
| nfl_prop_market | | card hourly at :25; publishes on the 13:00 UTC pass inside 24 h | as above | hourly inside 24 h: 855 games x 24 minus 914 = 19,606 | 1,568,480 ceiling (8 markets) | Partly |
| nfl_prop_tackles_assists | | prop scorer, same tick, 24 h ceiling | as above, DraftKings | 19,606 | 196,060 ceiling | Partly |
| nfl_prop_anytime_td, pass_attempts, pass_completions, pass_tds, pass_yards, rec_yards, receptions, rush_yards | P | prop scorer | as above | inside nfl_prop_market's | 0 extra | Partly |
| nfl_prop_rush_attempts, rush_rec_yards, sacks | P | as above | as above | one extra market each | 196,060 each, ceiling | Partly |

**NHL.** Every refresh pass, plus the 5-minute goalie window when a matchup
becomes known; not on the poller; both goalies confirmed and the price fetched
after it; re-scored until a BET locks. Stored: 16Z on each game date plus the
top of each start hour, 2020-21 to 2025-26; goalie confirmation times only
from 2026-10-20. Refresh passes 78,228, 3,331 held; game-day passes 2023-24
to 2025-26: 114,030 after one held snapshot a game.

| Model | P | Decides today | Stored history | Missing | Credits | Replay today |
|-|-|-|-|-|-|-|
| nhl_moneyline | | scorer, on DraftKings' no-vig price | h2h as above | 2021-22 to 2025-26: 65,604 | 656,040 | Partly |
| nhl_over_under | | card every refresh pass, Pinnacle vs soft books | totals as above | 2020-21 to 2025-26: 74,897 | 748,970 | Partly |
| nhl_puckline | | registered, no artifact; writes nothing | spreads | not applicable | 0 | Not applicable |
| nhl_moneyline_regulation | | scorer, same gate | one snapshot a game, 2023-24 to 2025-26 | per game: 114,030 | 1,140,300 ceiling | No |
| nhl_prop_shots_on_goal | | card, exempt from the goalie gate | one snapshot a game | as above | 1,140,300 | No |
| nhl_prop_assists | | card, gated | as above | as above | 1,140,300 | No |
| nhl_prop_saves | | card, gated; posts about 70 min before puck drop | as above | as above | 1,140,300 | No |
| nhl_prop_blocked_shots | | card, DraftKings only; posts about 70 min before | as above | as above | 1,140,300 | No |

**UFC, EuroLeague, tennis.**

| Model | P | Decides today | Stored history | Missing | Credits | Replay today |
|-|-|-|-|-|-|-|
| ufc_open_moneyline | | card hourly; bets only on the 12:25 UTC run | 12Z daily 2020-06-06 to 2026-06-13 (2,199 days) | hourly checks: 2,199 x 23 | 505,770 | Noon yes, hourly no |
| euroleague_home_ml | | once, on the call 10 min before tip | every snapshot from 30 min before tip, else 15-min steps, 2022-23 to 2026-11-13 | none | 0 | Yes |
| euroleague_home_dog_spread | | as above | as above | none | 0 | Yes |
| euroleague_h1_dog_ml | | once, on the call 10 min before tip | period history at 8 times, 1,170 games | the call 2 min before tip: 512 games | 5,120 ceiling | Yes at the 8 times |
| euroleague_q1_club_share_total | | as above | as above | as above, 2 markets | 10,240 ceiling | Yes at the 8 times |
| euroleague_live_spread_ht | | first eligible 5-minute read of the break | every in-play snapshot | none | 0 | Yes |
| atp_moneyline_shop | | once, 25-35 min before the listed start; card every 10 min | one ask an hour over 128 tournament windows, 2020-08 to 2026-11 | 10-min grid: 115,328 minus 19,221 | 961,070 | Hourly yes, 10 min no |
| wta_moneyline_shop | | as above | as above | 121,489 minus 18,157 | 1,033,320 | as above |

## Found while taking the inventory

- **The NCAAB in-play history purchase stored only the in-play rows.**
  `split_snapshot` (`data/ingestors/ncaab_inplay_history.py`) keeps rows typed
  `in_play` and counts the rest. Its ledger: 103,924 calls, 3,117,720 credits,
  12,976,081 rows stored, 65,717,531 pre-game rows returned and not stored
  (`ncaab_inplay_fetches`, read 2026-11-14). mike's rule of the same day is
  that nothing fetched is deleted. Issue #1341.
- **The MLB 22Z hours bought for 2021-2023 hold no totals,** and their 2021
  spreads come only from Pinnacle and Caesars.
- **2026 soft-book quotes are thinned to opener and close after 2 days** for
  MLB and WNBA game lines and every prop book except DraftKings and Pinnacle,
  so a 2026 replay at every refresh can use only those two.
- **The NBA `games` table holds no playoff games.**
- Stale: `docs/cloud_worker.md` still gives the NFL opener card as daily at
  9:30am with a 1.0-point gap; `docs/sports/ncaab.md` still calls the opener
  grid "not queued".

Not measured: which books quoted first-five totals and spreads in 2024-2025
(only a paid probe answers it); how many NCAAB games hold first-half history
(`count(distinct game_id)` of `odds` where `source =
'odds_api_ncaab_derivative_close'`, on the local copy, not production).

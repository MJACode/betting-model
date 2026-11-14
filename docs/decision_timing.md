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
4. If no timing clears out of sample, say so. Never hand the model its
   best-looking hour.

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

**Result:** issue #1337 until it is written here.

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

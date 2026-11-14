# NBL — Australia's National Basketball League: data, odds capture, models

> **Started 2026-11-14** (mike: *"Invoke model skill and build Australia nbl
> models"*), built with the league-models skill. The sport code is `NBL`.
> Season label: the ENDING year (2026-27 is 2027), which is also ESPN's own
> `season.year`. **No model is live.** This file is the groundwork: what the
> sources hold, the market grid, the purchase and its measured cost, and the
> forward collection. The research starts once the price history is bought,
> and the purchase waits on two things: this groundwork merged (so the odds
> clean-up does not thin what is bought) and mike's yes to the cost against
> the credit balance ("The purchase").

## The one fact that shapes every model here

**BetRivers is the only book a pick may name that prices the NBL.** Every
history snapshot read (2024-12-01, 2025-02-01, 2025-11-23, 2026-01-10,
2026-10-02, at the ten line-shop books and at every region) and today's board
held a BetRivers moneyline, spread and total, and not one DraftKings, FanDuel,
BetMGM, Caesars, Fanatics, Hard Rock or betPARX price. BetRivers priced no
first half, quarter, team total or alternate on six past games across the
three seasons (the per-event history endpoint, an empty answer is free). So
every NBL pick is decided at BetRivers alone, and no market beyond the full
game has a book a pick may name, **on the odds feed**. The scout found
search-index copies of DraftKings, FanDuel and BetMGM NBL pages (undated):
whether DraftKings prices the NBL is read by `scripts/nbl_dk_probe.py`, which
the permission check refuses to run from a session ("Open items").

## What the sources hold (measured 2026-11-14)

| Source | What it holds |
|---|---|
| The odds feed, key `basketball_nbl` | History from **2024-09-24T05:05:38Z**: a history event list at 2020-07-01, 2021-02-01, 2021-12-15, 2022-12-01 and 2023-12-01 answered empty with that snapshot as `next_timestamp`. So 2024-25, 2025-26 and 2026-27 to date. Snapshots five minutes apart (23:50:38, 23:55:38, 00:00:38 on 2024-11-30); none in the FIBA window (2025-11-23 07:35 to 2025-12-01 06:20). Today's board lists the next round only (2 games on 2026-11-14). |
| Its books | Every region, 2025-02-01 and 2026-01-10: BetRivers (moneyline, spread, total), Sportsbet, TAB, TABtouch, PointsBet, PlayUp, Unibet, Coolbet, Betsson, Coral, LeoVegas, Topsport, Marathonbet (moneyline), Ladbrokes, Neds, Betr, BetRight, Boombet (moneyline), Virgin Bet, and the Betfair exchange (moneyline, back and lay, at its three regions). **Pinnacle only from 2026-27** (absent 2024-12, 2025-02, 2025-11, 2026-01; full game on 2026-10-02). 19 books on today's board. |
| Its other markets | Per event only. Today (one 2026-11-15 game): first half (moneyline, spread, total) at five to seven Australian books; first quarter at six or seven; second to fourth quarters and the regulation 3-way at Sportsbet only; team totals (full game and first half) at Unibet and TABtouch; alternates at seven to nine books; odd/even, half-time/full-time, draw-no-bet first half; player props as **alternate ladders only** (points, rebounds, assists, threes, points+rebounds+assists at four to six books; blocks and steals at Sportsbet; double-double and triple-double). **None at BetRivers**, today or in the history read. Pinnacle has alternate spreads and totals in 2026-27. |
| ESPN's site API, league 55 (`basketball/nbl`) | Schedule, finals and quarter scores **from 2022-23** (nothing in 2021's calendar year), and the whole 2026-27 regular season to 2027-02-14 already scheduled. Summaries: player and team box score and 400-500 plays a game (period, game clock, running score, shooter, shot location); **no wall-clock time on plays** (`wallclockAvailable` False), no referees, attendance 0. Venue blank for every 2025-26 and 2026-27 game and for Brisbane's 2024-25 home games. The ranged `dates=` form answers HTTP 400; one call per calendar year works. |
| The NBL's own stats API | Not read: a request carrying the league site's own headers was refused by the permission check (2026-11-14), and it was not retried. The open-source NBL package's data repository (`JaseZiv/nblr_data` GitHub releases) holds play-by-play, box scores and shots from 2015-16 (per-season files to 2022-23, combined files refreshed 2026-11-13, read by the scout); per-match FIBA LiveStats files carry referees and attendance (shape read by the scout on a non-NBL match; untested on the NBL). |
| Prediction markets (not a book a pick may name) | **Kalshi**: NBL game winners from 2025-12-04 (107 games of 2025-26, median 126,016 contracts per team market; 66 settled games of 2026-27, median 46,391), spreads and totals since 2026-09-19 (several lines a game), free hourly bid/ask candles. **Polymarket**: 135 NBL events since 2026-01-09, median volume $24,883, free hourly price history. Both answered the scout's plain requests. |
| Refused or not used | AusSportsBetting's free closing-odds file (2009 on): Cloudflare 403, and its robots.txt names Claude's crawlers, so not fetched. OddsPortal's robots.txt bars past-season pages. hoops.com.au forum 403. |

## What differs from EuroLeague, the closest league we bet

- **Size.** Ten clubs; 165 regular-season games and 14 finals games a season
  from 2025-26 (145 + 14 in 2024-25, 140 + 14 in 2023-24). The feed's window
  holds **404 played games** (159, 179 and 66 so far of 2026-27). About 2,700
  games resolve a return to roughly ±4 points, so 404 resolve roughly ±10:
  **a +6% backtest here is noise until it survives every kill test.**
- **One deciding book** (above), against EuroLeague's five.
- **No sharp book for two of the three seasons.** Closing-line value in
  2024-25 and 2025-26 is measured against the Betfair exchange's moneyline
  and the Australian books' no-vig consensus; Pinnacle from 2026-27.
- **The clock.** Tips 02:00-11:30 UTC (9pm to 6:30am Eastern), at most two a
  UTC day. The refresh passes run hourly overnight Eastern and not between
  6am and 7am, so the forward close comes from the five-minute capture.
- **Rules.** FIBA, four 10-minute quarters and 5-minute overtimes, as
  EuroLeague; 34 of the 710 final games stored (2022-23 to 2026-27) went to
  overtime.
- **In play.** Online in-play betting is illegal in Australia (the scout:
  ACMA; phone and retail only), so the in-play money is offshore and American.
- **Travel.** Perth (UTC+8) and Auckland (UTC+13 in summer) against an east
  coast at UTC+10/+11; the Breakers fly about 86,750 km in 2026-27 against
  Sydney's 38,470 (the scout, basketball.com.au).

## Identity: ESPN owns the games row

`data/ingestors/nbl_teams.py`, `data/ingestors/nbl_espn.py`.

- **Game id** `NBL_<ESPN event id>`. **Club codes** are ESPN's abbreviations
  (ADL, BRI, CNS, HWK, MEL, NZL, PER, PNX, SYD, TAS; ESPN team ids 1-10, the
  same in every season ESPN serves). The feed's names map through
  `config.NBL_ODDS_API_MAP`; its one difference from ESPN is
  "S.E. Melbourne Phoenix". No partial name match is tried: Melbourne has two
  clubs.
- **game_date** is the Australian date (the UTC start plus 10 hours, the same
  calendar day in every NBL city for every stored tip).
- **What reaches `games`**: regular-season and finals games between two NBL
  clubs that are final, in play or still to come. Kept in `nbl_events` only:
  preseason games (and the Shanghai Sharks, a preseason opponent with no
  code), postponed or cancelled ones, three stale 2022-23 events (two left
  "end of period" with no score, Tasmania v Cairns 2022-12-17 and Adelaide v
  Sydney 2023-02-03, and Perth v New Zealand 2022-12-16 left "scheduled"),
  and **one preseason game ESPN labels regular season** (401707730, Cairns v
  Sydney 2024-09-09, ten days before the season opened: with it those two
  clubs show 30 games and the rest 29). A per-season club count warns when
  clubs disagree.
- **Stored 2026-11-14:** 152, 154, 159, 179 and 165 games (2022-23 to
  2026-27; 66 of 2026-27 played), every final scored, every final's quarters
  summing to its score, 2,879 quarter rows; box scores and plays of every
  final game (`nbl_espn_summaries`).

## The market grid

**No row has a priced result yet.** Inputs held for every row: finals,
quarter scores, box scores and plays from 2022-23. Baselines, methods and
results are filled in as the research runs; until the history is bought the
first three rows are "to do".

| Market | Settles on | Prices | Baseline | Method tried | Result | Status |
|---|---|---|---|---|---|---|
| Full-game moneyline | final, overtime included | trial days only (3 days of 2025-12, stored); BetRivers + 9 references from the purchase | to do | to do | none | **to do**: purchase |
| Full-game spread | final margin, overtime included | the same | to do | to do | none | **to do**: purchase |
| Full-game total | both scores, overtime included | the same (BetRivers' total was missing in one 2026-01-10 snapshot) | to do | to do | none | **to do**: purchase |
| First half moneyline, spread, total | quarters 1-2 | Australian books only; no book a pick may name on the feed | | | | **to do**: DraftKings board unread (probe) |
| First quarter moneyline, spread, total | quarter 1 | the same | | | | **to do**: DraftKings board unread |
| Second to fourth quarter, regulation 3-way | that quarter / quarters 1-4 | Sportsbet only | | | | to do: DraftKings board unread |
| Team totals, full game and first half | one club's points | Unibet, TABtouch | | | | to do: DraftKings board unread |
| Alternate spreads and totals | final | seven to nine Australian books; Pinnacle in 2026-27 | | | | to do: DraftKings board unread |
| Odd/even, half-time/full-time, draw no bet | | Australian books | | | | to do: DraftKings board unread |
| In play, and the halftime break | final | the purchase's in-play snapshots (every 5 minutes from 30 minutes before a tip to 2.5 hours after); halftime has no wall clock on ESPN's plays | | | | to do: purchase, and a source that places halftime in time |
| Player props | points, rebounds, assists, threes, combinations, blocks, steals, double-double | alternate ladders at four to six Australian books; no two-way main line | | | | to do: DraftKings board unread |
| Futures (champion) | | Kalshi's `KXNBL` series | | | | parked: settles months later |

## The purchase

`data/ingestors/nbl_odds_history.py`, a fork of the EuroLeague purchase: every
snapshot the feed holds of the full game at the ten books of
`config.NBL_HISTORY_BOOKMAKERS` (BetRivers, Pinnacle, the Betfair exchange and
the seven Australian and European books that priced every sampled game), 30
credits a snapshot (ten named books bill as one region). Pre-game quotes into
`odds` change-only under `odds_api_nbl_history`; in-play quotes into
`nbl_inplay_quotes` under `odds_api_nbl_inplay_history`; both protected from
the clean-up by this branch (`data/prune_odds.PROTECTED_SOURCES`).

**Trial, measured 2026-11-14** at EuroLeague's cadence (every snapshot from 30
minutes before each tip to 2.5 hours after it, one every 15 minutes otherwise),
spool `C:\Users\micha\nbl_spool`:

| UTC day | Games | Snapshots | Credits | Pre-game rows | In-play rows |
|---|---|---|---|---|---|
| 2025-12-13 | 2 | 146 | 4,380 | 1,329 | 609 |
| 2025-12-10 | 1 | 131 | 3,930 | 912 | 328 |
| 2025-12-09 | 0 | 103 | 3,090 | 504 | 0 |

Every event placed on ESPN's schedule, none unmatched. A day with no game
still holds a snapshot every five minutes, so it costs about 70% of a game day.

**The whole history at that cadence**, from the stored schedule (each season
from 10 days before its first game, never before the feed's first snapshot, to
the day after its last) and the three measured day costs, an upper bound
because the feed holds nothing in its quiet windows (the FIBA break above):

| Season | UTC days (no game / one / two) | Credits, at most |
|---|---|---|
| 2026-27 to 2026-11-14 | 67 (23 / 22 / 22) | 253,890 |
| 2025-26 | 211 (90 / 63 / 58) | 779,730 |
| 2024-25 | 182 (81 / 48 / 53) | 671,070 |
| All three | 460 | **1,704,690** |

**The credit position, read 2026-11-14.** 1,833,161 left after the three trial
days (11,400 credits). The platform's median burn is 64,540 a day over 30 days
and 129,905 over 14 (`odds_quota.daily_burn`; the 14-day figure is raised by
this month's purchases, and it is the one the purchase planner uses). The
plan's counter restarted on 2026-11-08 when it moved to 15M; if it renews
monthly from then, the refill is 2026-12-08, 24 days away, and the platform
alone needs about 1.55M of what is left to get there at 64,540 a day. So the
whole history (at most 1.70M) does not fit this cycle: buying it now needs
about 1.9M more credits (the purchase, the platform to the refill and seven
days' reserve, less the balance). Otherwise it runs from the refill, newest
season first, with a floor of seven days of the planner's burn:

    python C:/Users/micha/nbl_research/run_with_db.py data.ingestors.nbl_odds_history --seasons 2025 2027 --spool C:/Users/micha/nbl_spool --fetch --store --chunk-days 30 --reserve-days 7 --pregame-step-min 15

## The forward collection (from the day this merges)

- **The refresh passes** fetch the NBL with every other sport (resolve-only,
  DraftKings gate exempt): twenty books, two regions, 6 credits a pass.
- **The five-minute capture** (`scripts/nbl_odds_capture.py`, scheduler job
  `nbl_odds_capture`, two minutes past each five): the NBL board, stored only
  where a number moved, whenever an NBL game tips within 36 hours (6 credits a
  call). Run once by hand on 2026-11-14 15:02 UTC: 2 events, both placed, 52
  quotes stored, the spread on the home club (Sydney, home favourite at
  -435 on the moneyline, carries -9.5 at BetRivers).
- **ESPN, hourly** (`run_pipeline.py --step nbl-games`, in the hourly and
  overnight passes and the 6am run): the season's schedule and finals, and the
  box score and plays of each newly final game.
- **The odds clean-up keeps the NBL's whole price path** (`PATH_KEPT_SPORTS`).

## The scout (2026-11-14)

No published test of NBL betting markets at real prices, for the NBL or any
FIBA league, was found; no lead grades Strong.

| Lead | Mechanism | Evidence | Experiment on stored prices |
|---|---|---|---|
| BetRivers against the Australian consensus and the exchange | the one book a pick may name, a US book probably pricing off a supplied feed, may lag the market that sets the line | none yet (the mechanism that has held elsewhere here: the books disagree at a fixed moment) | BetRivers' price against the no-vig consensus at fixed times before the tip, and how long BetRivers takes to follow a consensus move |
| Kalshi and Polymarket as second prices | a separate venue with its own price formation; Kalshi's game markets are liquid | data only | each venue's last price before the tip against the books' close: Brier score, and whether the gap pays at BetRivers' price |
| Travel to and from Perth and New Zealand, short turnarounds | the market prices one flat home edge | weak (NBA studies; NBL distances descriptive) | cover rate of visitors at Perth and Auckland, and of a second game within two days of a long flight, at the close |
| Home advantage by venue | the same | weak (a forum's two seasons) | the price's home edge against the margin, by season and venue |
| Late import scratches | one import is a large share of a ten-man rotation; the league's injury list is hand-updated close to tip | noise | capture the list with timestamps going forward; the line move after a change |
| Totals bias, overtime frequency | none found for the NBL | weak (other leagues) | the over rate against the close; overtime rate against the price |
| Referees | crew foul rates | none; crews are not published before the tip | parked |
| Australian books banning winning bettors (Tabcorp, 2026) | if sharp money is limited, the Australian close is less informed | weak (one report) | best-of-books close against a single book's close as a predictor |

## Open items

1. **DraftKings' board (#1330).** `scripts/nbl_dk_probe.py` reads whether DraftKings
   lists the NBL and every market it prices, and stores the answers. mike runs
   it from his terminal on a day with NBL games on the board (the permission
   check refuses DraftKings site reads from a session). It decides whether the
   rows beyond the full game have a book a pick may name.
2. **The purchase (#1331)**, after this merges and on mike's yes (above).
3. **Kalshi's and Polymarket's NBL history (#1332)**, free: store it (a new ingestor;
   the repo's Kalshi recorder reads college football only).
4. **Halftime on the wall clock.** ESPN's plays carry none; the FIBA LiveStats
   files or the in-play quote stamps may place it.
5. Then the research, in the skill's order: baselines, the closest league's
   working methods unchanged, the scout's leads, the invention floor.

# NCAABW — women's college basketball: data, odds capture, models

> **Started 2026-11-09** (mike: *"Take everything we learned about building the
> NCAAB models and now build models for the womens NCAABW - ensure all
> learnings are incorporated, all odds API buys are auto approved"*). The sport
> code is `NCAABW`, the code Discord routing already used (2026-11-03). Season
> label: the ENDING year, as ESPN labels it (2026-27 is 2027). The 2026-27
> season opened Sunday 2026-11-01; ESPN's 2026-11-02 board holds 163 games.
>
> This is the women's twin of `docs/sports/ncaab.md`. Read that first: the
> rules it records (ESPN owns the games row, the home number, decide once,
> evidence and live on the same quotes) hold here unchanged. This file says
> what the women's sources hold, what was built, and where the women's game
> differs.

## What the sources hold (measured 2026-11-09)

The men's models were built on six seasons of paid lines at ten books, with
first-half lines and half-hourly in-play prices. The women's market is a
different size, and every number below was read off the source that day.

| Source | What it holds for women's college basketball |
|---|---|
| The odds feed, key `basketball_wncaab` | History from the games of **2024-11-12** on. No event at all at any date asked before that (eight dates, 2020-12 to 2024-01). So **two finished seasons** of prices, 2024-25 and 2025-26. |
| Its event lists | **2,293 events** from 2024-11-12 to 2026-04-05: 942 in 2024-25, 1,351 in 2025-26. A median **7 a game day**, 18 at the 90th percentile, 39 at the most (261 game days). ESPN's board holds about 6,000 games a season, so the feed lists roughly one game in five. A game first appears a median 3.5 hours before its tip (sampled four times a day). |
| Its books | Twelve priced women's games in 14 history snapshots asked at every region: DraftKings, FanDuel, BetMGM, Caesars, Fanatics (2025-26 only), BetRivers, and six that a pick may never name (ESPN BET, Bally Bet, Fliff, BetOnline, LowVig, Unibet). **Pinnacle, Bovada and betPARX priced none.** DraftKings priced a spread and a total on 87 of 92 pre-game events in the 2024-25 snapshots and 114 of 127 in 2025-26; Caesars 4 and 78; FanDuel 39 and 108; BetMGM mostly totals and moneylines (spreads on 18 and 17). |
| Its other markets | **None.** 17 past games on four dates, asked 20 minutes before the tip for first-half, quarter, second-half, team-total, alternate and player-points lines: BetMGM's first-half moneyline on six Sweet 16 games of 2026-03-27/28, and nothing else. The five games listed live on 2026-11-09 showed the same (BetMGM's first-half moneyline on two). |
| ESPN's site API, `womens-college-basketball` | The same endpoints and shape as the men's: 363 Division I teams, the scoreboard by ET date (118 events on 2026-01-24), a game summary with the box score, player lines and a play-by-play with wallclock times. **Four quarters**: a regulation final is period 4. |
| ESPN's own odds (core API) | One provider a game. On the dates sampled: almost no line before 2021-22; a projection provider on most games of 2021-22; one sportsbook on 122 of 130 finals of 2023-01-14 and 49 of 60 of 2023-12-06; then 4 to 12 games a day from January 2024 (ESPN BET, DraftKings from 2025-26), with an opening and a closing number. Not imported yet (see Open items). |
| sportsdataverse's season files | NCAA's possession box scores `ncaa_wbb_team_box` 2010 to 2027 (the 2027 file held 479 games through 2026-11-08, so it is being built in season), player box scores, and ESPN's play-by-play `espn_womens_college_basketball_pbp` 2004 to 2027. |

**The feed keeps no snapshot while nothing moves, and an ask for a time it has
none at is billed for the one before.** Asked for 2026-01-24 07:00Z, 09:00Z,
12:00Z and 14:00Z it answered each time with its 02:15:38Z snapshot and billed
60 credits each time; asked for 2025-07-15 it answered with 2025-04-06's. The
purchase below walks the feed's own chain (`next_timestamp`) for that reason.

### The market grid

| Market | Settles on | Inputs held | Prices | Status |
|---|---|---|---|---|
| Full-game total | both scores, overtime included | NCAA box scores 2010-27, ESPN finals 2015-16 on | the feed, 2024-25 and 2025-26 | **passes** at DraftKings' first posted total (Research, below); not live yet |
| Full-game spread | final margin, overtime included | the books' own lines | the same | the men's line-shopping rule **fails** here (below) |
| Full-game moneyline | winner, overtime included | each book's own spread | the same | the men's own-spread rule **fails** here (below) |
| In play: spread, total | the final | ESPN play-by-play with wallclock | the feed's snapshots, five minutes apart | second-half total passes a first look, spreads are close; checks outstanding (below) |
| First-half moneyline | the first two quarters | none | BetMGM alone, tournament games | parked: one book, a handful of games |
| First-half spread and total, quarters, team totals, alternates, player props | | | none in the feed | parked: no price source. The men's two first-half models have no women's twin. |

## What differs from the men's game

- **Four 10-minute quarters since 2015-16**, two halves before. Overtime is
  ESPN's period 5 or later (`ncaabw_teams.regulation_periods`); the men's rule
  (period 3 or later) would have marked every women's game as overtime. Stored
  overtime share: 3.9% to 4.6% a season, 2015-16 to 2025-26.
- **ESPN gives a school's women's team its men's team id** (UConn is 41 in
  both), so the women's identity lives in its own tables.
- **The feed names many women's teams the men's way.** ESPN's "Oklahoma State
  Cowgirls" is the feed's "Oklahoma St Cowboys"; ESPN's 21 "Lady ..." mascots
  lose the "Lady". See Feed team names.
- **No sharp book.** Pinnacle does not price the women's board, so there is no
  Pinnacle close to measure closing value against. BetOnline and LowVig are
  the nearest thing, on under half the games.
- **No first-half, quarter or team-total line, and no player prop**, in the
  feed (above).

## Identity: ESPN owns the games row

`data/ingestors/ncaabw_teams.py`, a fork of the men's `ncaab_teams.py`.

- `ncaabw_teams` (ESPN team id, school, slug, mascot), `ncaabw_events` (ESPN
  event id to our game id, both team ids), `ncaabw_venues`. Worker-only.
- Game ids are `NCAABW_<ET date>_<away slug>_<home slug>` in ESPN's
  orientation, written only by `data/ingestors/ncaabw_espn_ingestor.py`.
- The odds feed never mints an NCAABW game. Its events resolve onto ESPN's
  games by the unordered team pair within a day of the tip, and the names are
  swapped first when the feed calls ESPN's away team home, so the stored
  spread is ESPN's home number (CLAUDE.md §4).
- **Stored 2026-11-09:** 61,431 games, 2015-16 to 2026-11-08, every one with
  its event row; 1,069 teams, 363 of them Division I. Games dated today or
  later are left to the worker's own schedule step, so nothing unscored sits
  in `games` before that step runs.

| Season | Games | Scored | Overtime |
|---|---|---|---|
| 2015-16 | 5,618 | 5,617 | 4.1% |
| 2016-17 | 5,622 | 5,608 | 4.1% |
| 2017-18 | 5,630 | 5,630 | 4.4% |
| 2018-19 | 5,658 | 5,658 | 3.9% |
| 2019-20 | 5,436 | 5,434 | 4.6% |
| 2020-21 | 3,825 | 3,823 | 4.3% |
| 2021-22 | 5,536 | 5,534 | 4.2% |
| 2022-23 | 5,828 | 5,828 | 4.5% |
| 2023-24 | 5,867 | 5,866 | 4.0% |
| 2024-25 | 5,924 | 5,923 | 4.0% |
| 2025-26 | 6,000 | 6,000 | 4.3% |
| 2026-27 to 11-08 | 487 | 487 | 1.6% |

**A day's new events are written together.** The men's ingestor writes each
event in its own savepoint, three statements each, and has only ever run on
the worker, beside the database, where a season took 13 minutes. From a laptop
four processes wrote 55 dates between them in 47 minutes. The women's ingestor
writes the day's never-seen events in three statements for the whole day
(`_write_new_events`); a season then took 8 minutes from the same laptop.
Events seen before still take the one-at-a-time path, and a batch that fails
falls back to it.

## Feed team names (2026-11-09)

The census: the 353 team names on the feed's 2,293 events. The men's rules
placed 326. The other 27 names (113 events) are placed by:

- **The "Lady" rule** (`_resolve_shortened_school`): where ESPN's mascot starts
  "Lady", the feed's name without it is accepted, once the school has matched.
  Nine names: "Alabama St Hornets" is ESPN's Alabama State Lady Hornets.
- **Six mascot aliases** (`MASCOT_ALIASES`): Oklahoma State (Cowboys), Montana
  (Grizzlies), Louisiana Tech (Bulldogs), Hawai'i (Rainbow Warriors), Western
  Kentucky (Hilltoppers), Stephen F. Austin (Lumberjacks). Wyoming and McNeese
  (Cowboys) are there by the same pattern; the feed has not named either yet.
- **Twelve overrides** (`config.NCAABW_ODDS_API_MAP`): eleven are names the
  men's feed also uses for the same schools ("UMKC Kangaroos", "Albany Great
  Danes"); the twelfth is "Miss Valley St Delta Devilettes".

All 353 names now place a team. Against the stored schedule, **2,273 of the
2,293 events land on an ESPN game** (47 of them flipped, neutral courts). The
other 20 are pairs ESPN has no game for within a day of the listed tip; the
purchase keeps them raw in `ncaabw_odds_unmatched`.

One thing the resolver would do and the census never asked of it: a name like
"Missouri St Tigers" would land on Missouri (Tigers), because a school that
starts the name and shares the mascot's last word is accepted. No census name
has that shape.

## The odds history purchase

`data/ingestors/ncaabw_odds_history.py`. One purchase, not the men's four:
every bulk snapshot of moneyline, spread and total the feed kept, at the
seventeen books `odds_ingestor.sport_bookmakers_param("NCAABW")` names (the
ten line-shop books and `config.NCAABW_EXTRA_BOOKMAKERS`). Seventeen books are
two regions, so a snapshot bills 60 credits.

- **Fetch.** Each UTC day is its own chain: ask for 00:05, then follow
  `next_timestamp` to the end of the day. One ask per snapshot the feed really
  kept. 2026-01-24 held 148 snapshots, five minutes apart, with one gap of 11
  hours 45 minutes overnight; it cost 8,880 credits and no ask was wasted.
  Answers go to a spool folder with each day's state beside them, so a stopped
  run resumes where each day stopped. Several processes may share a spool; a
  day is claimed with a lock file.
- **Store.** The spool, oldest snapshot first, into Supabase. Pre-game quotes
  go to `odds`, change-only (a book's first quote and every change), source
  `odds_api_ncaabw_history`. In-play quotes go to `ncaabw_inplay_quotes`, every
  one of every snapshot, keyed on the snapshot's own time. Unplaced events go
  raw to `ncaabw_odds_unmatched`. One ledger row a snapshot in
  `ncaabw_odds_snapshots`, in the same transaction.
- **Why in-play quotes have their own table.** The men's sit in `odds` and are
  tied to their snapshot by matching `created_at` to the ledger's `pulled_at`.
  Here the snapshot time is a column, the rows stay out of the table the app
  reads every minute, and a market a book took down is simply absent from that
  snapshot.
- **Credits.** The ceiling is the plan at its most; the floor is seven days of
  the measured daily burn (59,831 a day on 2026-11-09, so 418,817). The balance
  was 14,940,720 at 2026-11-10 00:10Z.
- **What it bought (2026-11-09 to 11-10 03:00Z).** 317 UTC days, 2024-11-10 to
  2026-11-09: **49,527 snapshots, 2,971,620 credits** billed for them, and
  2,580 more for 43 first asks of a day that were answered with the day
  before's last snapshot (the dry run prints both). Not in those figures: the
  fetch was stopped and restarted four times while it was being made faster,
  and a call in flight at a stop was paid for and not recorded, at most 128
  calls (7,680 credits); and 15 answers were asked for again after a state
  file could not be replaced. The balance read 11,952,537 when the last day
  finished. 2024-25 holds 22,861 snapshots, 2025-26 24,592, 2026-27 to date
  2,074.
- **What it holds.** 147,268 pre-game rows on 2,448 games (a first quote and
  every change), 773,059 in-play rows on 2,612 games. DraftKings posted a total
  on 1,772 games and a spread on 1,772; FanDuel 1,608 and 1,612; BetRivers
  1,817 and 2,154; BetMGM 2,054 totals and 542 spreads; Caesars 1,063 and
  1,085; Fanatics 1,093 and 1,093; Hard Rock 18 (it first appears in 2026-27).
  34 team pairs resolved and had no ESPN game.
- **200 games have in-play quotes and no pre-game ones** (37 in 2024-25, 136
  in 2025-26, 27 in 2026-27). Their first quote came a median 15 minutes after
  ESPN's stored tip, and on the 168 with a play-by-play the first play came a
  median 3 minutes after it, so the stored tips are right: the books listed
  those games in play only.
- **A game the feed lists under two events at once keeps one in-play quote per
  book and market** (the table's key). Checked while the store was running: the
  ledger counted 154,933 in-play rows offered and the table held 154,394.
- **Speed, measured.** With a new connection per call, 40 calls in flight kept
  four processes at 0.84 of a core each for 138 snapshots a minute. One
  kept-alive connection per thread made 630 in 33 seconds and met the feed's
  rate limit (HTTP 429, about 1,000 in all), which the meter's shared pause
  absorbs.

Commands (from a checkout with production settings):

    python -m data.ingestors.ncaabw_odds_history --seasons 2025 2027 --spool DIR
    python -m data.ingestors.ncaabw_odds_history --seasons 2025 2027 --spool DIR --fetch --store

**Stored, checked 2026-11-10.** The ledger holds all 49,527 snapshots
(2024-11-12 21:15Z to 2026-11-09 23:55Z). `odds` holds 147,268 pre-game rows
under `odds_api_ncaabw_history` on 2,448 games, the spool's own count game by
game, so the connection that dropped during the store wrote nothing twice.
`ncaabw_inplay_quotes` holds 772,377 rows against 773,059 counted: in 28
snapshots the feed listed an event twice, and the table's key (snapshot, game,
book, market) keeps the first listing. 2,186 events matched no ESPN game and
are kept raw in `ncaabw_odds_unmatched`.

## What runs, and where it lands

| Piece | What | Where |
|---|---|---|
| ESPN schedule and results | Teams, venues, every game, finals for settlement; the daily pipeline refreshes 14 days ahead, every refresh pass fills finals for started games | `data/ingestors/ncaabw_espn_ingestor.py`, steps `ncaabw-schedule` / `ncaabw-results` |
| Live odds | Full-game moneyline, spread and total at the seventeen books on every refresh pass; NCAABW is exempt from the DraftKings-must-list gate, like the men's, so every book's first post is kept | `data/ingestors/odds_ingestor.py` |
| Opener capture | Every 5 minutes, a minute after the men's, change-only; 6 credits a call when a game is listed; no call when no game tips within 36 hours; `RUN_NCAABW_ODDS_CAPTURE=0` stops it | `scripts/ncaabw_odds_capture.py`, job `ncaabw_odds_capture` |
| Price-path retention | NCAABW keeps every book's whole price path | `data/prune_odds.py` (`PATH_KEPT_SPORTS`) |
| Paid history | Every snapshot of 2024-25, 2025-26 and 2026-27 to date (above) | `data/ingestors/ncaabw_odds_history.py` |
| Free history | NCAA possession box scores and season player minutes, 2010 to 2027 | `data/ingestors/ncaabw_sdv_import.py` |
| Box scores, this season | ESPN's summary after each final on the hourly passes (step `ncaabw-box`); NCAA's file once a day (step `ncaabw-ncaa-box`, new contests only) | `data/ingestors/ncaabw_espn_box.py`, `ncaabw_sdv_import.refresh_season` |
| Totals model card | Every 5 minutes, three after each capture tick: decides each game once at DraftKings' first posted total, bets only while it still stands, then publishes; `RUN_NCAABW_TOTAL_CARD=0` stops it | `scripts/ncaabw_total_card.py`, job `ncaabw_total_card` |

## Box scores and period scores (ESPN, from 2026-27)

`data/ingestors/ncaabw_espn_box.py`, a fork of the men's feed. After each
final, ESPN's game summary gives the team box score (two rows in
`ncaabw_team_game_stats`, source `espn_summary`, `contest_id`
`espn:<ESPN event id>`) and the period scores (`ncaabw_period_scores`:
**periods 1 to 4 are the quarters, 5 and later the overtimes**). Step
`ncaabw-box` runs on the hourly refresh passes after `ncaabw-results`; a game
it will not store gets a row in `ncaabw_box_misses`. The possession estimate,
the refusals and the red-run rule are the men's (`docs/sports/ncaab.md`, "Box
scores and period scores"). What differs: a game's length is 40 minutes plus 5
for each period past the fourth, a regulation game must show four periods
(two before 2015-16), and there is no women's player box.

**Two sources, one game.** NCAA's rows (sportsdataverse) and ESPN's can both
hold a game, and this season both do. Keep one source per game, both of its
rows, NCAA's where it holds the game. **ESPN's game id cannot be the key.**
NCAA's rows carry it in three seasons only (read 2026-11-10: 99.6% of 2023-24
rows, 94.3% of 2024-25, 100% of 2025-26, none of any other season, and none
of 2026-27's 958). A row with no id is placed on its game by the date and both
team ids, then by the date within a day, one team and the exact score.
`models.ncaabw_total_blend.place_box` does it, and the totals card and the
build both read through it. On 2026-11-10 it placed all 1,996 stored 2026-27
rows and kept 1,048: NCAA's for 479 games, ESPN's for 45.

**The first real run** (the 2026-27 backfill, 2026-11-09): 525 finals due, 519
stored, 6 refused (5 where the box's made shots do not add up to the final
score, 1 with no shooting numbers). 2,085 period rows: four a game and nine
overtime periods. NCAA's file held 5 of the 6 refused games, which is why the
model reads both sources. `python -m scripts.ncaabw_research.box_coverage`
prints the season's coverage the way the card reads it.

## Open items

- **ESPN's own odds are not imported.** They would add one sportsbook's lines
  on most games of 2022-23 and the first weeks of 2023-24. One call a game to
  ESPN's core API, free.
- **The season's schedule is loaded whole by hand.** The daily step stores 14
  days ahead. 2026-27 was loaded to 2027-03-06 on 2026-11-10 (5,769 games).
  Each October: `python -m data.ingestors.ncaabw_espn_ingestor --backfill
  <first> <last>`. The totals card fails its run, by name, if it was not.
- **NCAA's 2026-27 file is not updated every day.** It held games through
  2026-11-08 on both 2026-11-09 and 2026-11-10.

## The totals model: `ncaabw_total_blend` (live from 2026-11-10)

mike, 2026-11-09: build the women's models from everything learned on the
men's. The men's totals method on the women's games, at the women's own cut.

| | | |
|---|---|---|
| model | ratings refit as of the quote, a correction on shooting luck and style, blended with DraftKings' total | `models/ncaabw_total_blend.py` |
| card | decides each game once at DraftKings' first posted total, only while it still stands | `scripts/ncaabw_total_card.py` |
| frozen numbers | `models/saved/ncaabw_total_blend_2027.json` | `scripts/ncaabw_total_blend_build.py` |
| cut | edge above 0.05: P(win, push left out) minus DraftKings' implied probability | `config.MODEL_EDGE_THRESHOLDS` |
| EV floor / price floor | 0.07 / -200 | `config.MODEL_OWN_EV_FLOOR`, `MODEL_MIN_ODDS` |
| stake | the flat 1 unit to win, risk capped at 3 | no `stake_units` written |
| decided once | a row in `ncaabw_total_decisions`, bet or not | the card |
| settles as | full-game total, overtime included | `tracking/paper_tracker._RULE_MODEL_MARKETS` |
| posts to | the NCAABW channel (`DISCORD_CHANNEL_NCAABW`, set on the worker) | `tracking/signal_publisher` |

**The frozen numbers** (built 2026-11-10). Ratings settings: the men's,
untouched. Stage 2 fitted on 2015-16 to 2025-26. Blend on the 1,730 priced
games of 2024-25 and 2025-26: every game c +0.574, beta 0.677, sigma 15.92;
December on (1,512 games) c +0.260, beta 0.760, sigma 15.81. November has 218
priced games, under the 300 a fit needs, so a November game is priced with the
every-game fit.

**What the build proves.** It reproduces the research tables to the bet (402
bets, 225-177, +29.96 units for 2025-26 on numbers from 2024-25; 453 and
+55.76 for each season on the other's blend; 374 and +75.73 on the blend it
runs on). Then it replays the card's own decision code on all 903 priced games
of 2025-26 with that season's numbers built as the artifact is: 402 bets, the
same 402 games and sides as the replay, none held, none refused by a floor,
largest edge difference 0.00000004. The artifact's `replay` block holds all of
it (its intervals come from its own resample and differ from the tables below
in the first decimal).

**November against December on, at the 0.05 cut:**

| | November | December on |
|---|---|---|
| Each season on the other's blend | 80 bets, 43-37, +2.30 units, +2.61% [-14.8, +19.3] | 373 bets, 221-152, +53.46 units, +13.01% [+3.6, +22.4] |
| The blend it runs on (in sample) | 68 bets, 36-32, +0.77 units, +1.03% [-18.2, +20.4] | 306 bets, 196-110, +74.96 units, +22.25% [+12.0, +32.0] |

November is flat, not losing, and the model bets it (no hold was graded as
better).

**Prices.** Every replayed bet was laid at -115 to -105. DraftKings priced
every women's total it posted in 2024-25 to 2026-27 between -120 and -102.
The floor is -200.

**2026-27 to date, through the card's own reads** (2026-11-10, `python -m
scripts.ncaabw_research.season_to_date`): 42 priced finals. At 0.05: 14 bets,
7-7, -0.75 units. At 0.03: 22 bets, 10-12, -3.25 units. The line's error on
those games is 15.95 points and the model's 15.95.

### In the app (2026-11-10)

NCAABW is a sport chip right after NCAAB on the Picks, Models and Stats tabs,
and the model is "NCAABW Totals" (badge O/U). The Today board reads its picks
7 days ahead, because DraftKings' first total came up to 6 dates before the
game. There are no women's stats and no in-play model; the Stats, Live and
Today boards each say so in words and point at where the picks are. VoiceOver
says "Women's college basketball" wherever a control speaks the sport, so the
men's and women's chips do not sound alike.

- **The prefix trap.** `modelId.startsWith('ncaab')` is true for
  `ncaabw_total_blend`, so both places that file a model under a sport test
  the women's prefix first (`modelMeta.sportOfModel`, `ModelsScreen.sportOf`).
  `tests/test_mobile_ncaabw_in_app.py` fails if a third prefix test appears.
- **The seven extra books.** Bally Bet and Fliff moved to the app's
  reference-only list for every sport, so neither is in the sportsbook picker
  or on a line chip (mike, 2026-11-10: *"get rid of bally and fliff"*). The feed stopped fetching both on 2026-09-20; the only
  newer prices at either are the women's. Read 2026-11-10: of 28 stored book
  sets, none held only those two and 4 held one beside other books. BetOnline,
  LowVig, Unibet and BetWhale were never selectable and now have display
  names.
- **The name on screen is "NCAABW"**, the Discord channel's name. The UX
  review preferred "NCAAW" (ESPN's name), because the code reads as the men's
  plus a letter. mike, 2026-11-10: *"leave it"*.

### What a straight copy of the men's card got wrong

Each was found by running the fork on the stored women's tables before it
went live, and each has a test.

1. **Every team would have been pooled into one.** The model pools a team
   with fewer than 10 games on the season's schedule. The men's schedule is
   stored whole (6,009 games to 2027-03-07). The women's held 1,245 games to
   2026-11-23, so no team had 10 and every game would have been priced off
   one pooled rating. The season was loaded (5,769 games; 363 Division I
   teams, fewest 25 games), and the card now refuses a game with a Division I
   team under 10 stored games and fails its run (`schedule_short`).
2. **Both box sources would have been counted.** See "Two sources, one game".
3. **The blend had no November.** The men's artifact holds a fit per phase.
   The women's November has 218 priced games, so the men's code would have
   refused every November game as `no_blend`. `blend_for` falls back to the
   every-game fit, as the research graded it.
4. **The ranges were the men's.** Totals 90 to 200 (the men's 220; no women's
   total stored is above 179.5) and spreads to 85 either way (the men's 60
   would drop 274 real rows). The edge cap is 0.30: the largest edge over all
   1,730 priced games is 0.2076.
5. **A second stake.** The men's card sizes a bet up when an earlier NCAAB
   bet agrees with it. There is one women's model, so every bet is flat.

## Research (2026-11-09)

Scripts: `scripts/ncaabw_research/` (its README says how to rebuild the cache).
Every table is one unit to win with risk capped at 3 (the house stake), at the
quoted price, with a 95% interval resampled by date. Two priced seasons exist,
so "walk-forward" here means one thing: 2025-26 graded on numbers fitted only
on 2024-25 (and the first week of 2026-27 on both). 2024-25 graded on numbers
from 2025-26 is a second look and is labelled as one.

### Full-game totals: the men's totals model passes

The men's model unchanged (`models/ncaab_total_blend.py`): ratings and the luck
and style correction as of the hour of DraftKings' own time on its first posted
total, blended with that total, priced at DraftKings' two prices. Settings are
the men's; none was tuned on the women's prices.

**The rating model alone** (`totals_a`; 61,408 games from 2015-16, possessions
on 61,146): mean absolute error of the predicted total 13.05 points over
2016-17 to 2026-27, against 15.34 for last season's league average. Its 487
games of 2026-27 were predicted with every team pooled into one (only the
played games of the season were stored then, so no team had 10 on the
schedule); nothing is read from them here.

**Against lines it was never fitted to** (`totals_espn`; ESPN's stored
sportsbook total, one provider, capture time unknown, no usable price, so this
is about information, not profit). In `total - line = c + beta x (model - line)`:

| Season | Games | beta | 95% interval | Error: line | model |
|---|---|---|---|---|---|
| 2022-23 | 4,881 | 0.820 | [0.691, 0.942] | 12.85 | 12.68 |
| 2023-24 | 2,968 | 0.869 | [0.689, 1.044] | 13.13 | 12.93 |

Where the model sat 5 or more points off that line the game landed its side
324-185 in 2022-23 and 309-193 in 2023-24. The men's model never beat a
posted line on raw error; this one does, on those lines.

**At DraftKings' first posted total** (`totals_b`, `totals_c`; 1,772 priced
games: 827 in 2024-25, 903 in 2025-26, 42 in 2026-27). DraftKings first posts
a women's total a median 6.0 hours before the tip in 2024-25 and 4.9 in
2025-26, and that first number stood a median 136 and 85 minutes (the men's
about 30). On these games the model's error is 12.69 against the line's 12.85
in 2024-25, and 12.40 against 12.34 in 2025-26.

*2025-26, walk-forward* (blend fitted on 2024-25: beta 1.05, so it trusts the
model fully and bets over half the games):

| Cut | Bets | Record | Units | ROI | 95% interval |
|---|---|---|---|---|---|
| 0.03 | 516 | 283-233 | +26.33 | +4.63% | [-3.7, +12.1] |
| 0.04 | 462 | 257-205 | +31.13 | +6.12% | [-1.6, +14.1] |
| 0.05 | 402 | 225-177 | +29.96 | +6.77% | [-2.2, +15.1] |
| 0.06 | 345 | 194-151 | +27.59 | +7.26% | [-2.3, +16.8] |
| 0.08 | 276 | 160-116 | +32.16 | +10.57% | [-0.1, +20.9] |

Every over blind lost 0.26% and every under 8.87% on the same 903 games.
Bet lines beat the closing consensus by 0.56 to 0.72 points.

*2024-25, the second look* (blend fitted on 2025-26: beta 0.46): 128 bets at
0.03, 87-41, +42.02 units, +29.89% [16.5, 43.8]; 51 at 0.05, 39-12, +25.80.

*Both seasons, each on the other's blend* (`totals_c`):

| Cut | Bets | Record | Units | ROI | 95% interval |
|---|---|---|---|---|---|
| 0.02 | 785 | 439-346 | +58.02 | +6.72% | [+0.7, +12.6] |
| 0.03 | 644 | 370-274 | +68.35 | +9.64% | [+2.9, +16.1] |
| 0.04 | 538 | 313-225 | +65.23 | +11.02% | [+3.9, +18.5] |
| 0.05 | 453 | 264-189 | +55.76 | +11.18% | [+2.7, +19.3] |
| 0.06 | 378 | 222-156 | +50.09 | +12.03% | [+2.4, +21.0] |
| 0.08 | 286 | 169-117 | +40.06 | +12.71% | [+1.8, +22.9] |

*The blend it would run on in 2026-27* (fitted on both seasons: c +0.57, beta
0.677, sigma 15.92 on 1,730 games; December on c +0.26, beta 0.760, sigma
15.81 on 1,512; November has under 300 games and uses the all-season fit). In
sample for those three numbers:

| Cut | Bets | Units | ROI | 95% interval | 2024-25 | 2025-26 | Share of priced games |
|---|---|---|---|---|---|---|---|
| 0.04 | 484 | +63.89 | +11.99% | [+4.3, +19.5] | 177, +32.2 | 307, +31.7 | 28.0% |
| 0.05 | 374 | +75.73 | +18.39% | [+9.3, +27.5] | 124, +38.0 | 250, +37.7 | 21.6% |
| 0.06 | 283 | +76.96 | +24.69% | [+14.8, +34.6] | 88, +37.6 | 195, +39.4 | 16.4% |

Prices at 0.04: -118 to -105. This paragraph first quoted 2026-27's first
week as 30 bets at 0.03, 20-10, +9.03 units. That was computed with every
team pooled into one and is withdrawn; the season to date is under "The
totals model" below.

**Read before trusting it:**

- **One walk-forward season, and its own interval includes zero** (lower bound
  -3.7% to -0.1% across the cuts). The pooled table clears zero at every cut
  from 0.02 to 0.08, but half of it is 2024-25 on a blend fitted a season
  later (three numbers).
- **The blend is not stable.** Beta was 1.05 on 2024-25 and 0.46 on 2025-26:
  DraftKings' first totals got sharper (their error fell from 12.85 to 12.34).
  If they sharpen again the two-season blend will claim too much.
- **It claims more than it hits.** Each season on the other's blend: claimed
  0.563 won 0.527 (281 games), 0.599 won 0.571 (198), 0.651 won 0.577 (168).
- **November is flat.** At 0.04 on the two-season blend: 81 November bets,
  -3.33% [-21.3, +14.6]; December on, 403 bets, +15.07% [+6.4, +23.3].
- **A first post that stood under 10 minutes** is 30 of the 484 bets at 0.04
  (+46%); the 454 that stood 10 minutes or more made +9.72% [+1.9, +17.5].
- **Overs and unders both pay** at 0.04: overs 310 bets +13.27% [+2.7, +23.6],
  unders 174 bets +9.73% [-2.3, +21.7].

### Full-game spread and moneyline: the men's two market rules fail

`market`. Boards are the newest snapshot at or before the tip less a lead. The
men's final-margin table needs 70,268 games with a closing line; the women's
feed has two seasons, so the margin is a normal around the consensus with a
spread fitted on the earlier season's closes (12.2 points, flat in the size
of the line).

*Spread, line shopping against the consensus, edge above 0.03, three other
books:*

| Lead before tip | 2025-26 (walk-forward) | 2024-25 (second look) |
|---|---|---|
| 10 min | 127 bets, +5.75% [-11.6, +22.8] | 55, -2.81% [-26.4, +18.7] |
| 30 min | 124, -0.84% [-16.7, +15.2] | 49, +1.10% [-23.2, +24.0] |
| 60 min | 118, -5.28% [-22.1, +13.0] | 47, -14.84% [-40.4, +12.1] |
| 120 min | 111, +6.02% [-10.9, +24.3] | 41, +12.07% [-15.2, +37.6] |
| 240 min | 63, -0.91% [-22.8, +22.5] | 24, -28.76% [-64.2, +9.5] |

No lead is positive in both seasons with an interval clear of zero, and the
sign flips between neighbouring leads. The same bets placed at the consensus
line at -110 lost 6.7% and 12.6% (2025-26, 10 and 60 minutes) and 20.2% and
35.0% (2024-25): on the women's board the book that stands apart is more often
right than wrong.

*Moneyline off the book's own spread, -200 or longer, edge above 0.01:*
2025-26 at 10, 30, 60, 120 and 240 minutes: +6.09%, +15.57%, -7.98%, +6.77%,
-25.24% on 54 to 125 bets, every interval spanning zero; 2024-25: -4.06%,
-3.43%, +1.18%, +0.56%, -2.00% on 171 to 267 bets. With favourites shorter
than -200 removed, what is left on a board full of 20-point spreads is long
underdogs (prices to +3500, 21 to 33 winners in 107 to 125 bets). Nothing here.

### In play: a first look (checks outstanding)

`inplay`. A game-state model on the women's clock (four quarters): what is
still to come is normal around the pre-game closing consensus scaled by the
share of regulation left, the surprise so far, and for totals a late-and-close
term; fitted on every 30 seconds of the earlier season's priced games. Out of
sample on 2025-26 the margin's mean error is +0.02 points and the total's
+0.35, spread ratios 1.01 and 1.04. A quote is priced on the play-by-play
state at its own stamp and is eligible at a bettable book, priced -250 to
+250, within 6 points of the other books in its snapshot, with two other
books quoting, and no point scored between its stamp and the snapshot.

The men's decision rule (the first snapshot of the phase holding an eligible
quote decides the rule for the game), EV at or above 0.05:

| Rule | 2025-26 (walk-forward) | 2024-25 (second look) | 2026-27, first week |
|---|---|---|---|
| Total, halftime to two minutes left | 698 bets, +8.75% [+2.2, +15.7] | 305, +12.84% [+2.0, +23.4] | 16, -5.21% |
| Spread, halftime to two minutes left | 405, +6.80% [-2.4, +16.6] | 156, +13.44% [+1.1, +26.6] | 29, -22.90% |
| Spread, first half | 387, +5.69% [-4.3, +15.1] | 219, +0.05% [-12.0, +11.3] | 30, -0.29% |
| Total, first half | 1,082, -5.31% [-11.3, +1.0] | 472, -1.22% [-10.3, +7.5] | 51, -8.64% |

The second-half total is positive at every cut from 0.02 to 0.12 in 2025-26
(lower bounds +0.3 to +2.6). **Not yet done**, each of which the men's in-play
models had to pass: the blind same-side baseline, the bands below and above
the cut, the placebo (another game's model), and the stale-quote checks. The
claimed EV (mean 0.16 at the 0.05 cut) is about twice the return, and the
first week of 2026-27 is negative on every rule (16 to 54 bets each). These
numbers are a reason to finish the checks, not a go-live.

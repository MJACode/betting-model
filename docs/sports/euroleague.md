# EUROLEAGUE — data, odds capture, models

> **Started 2026-11-12** (mike: *"build the euroleague model. all markets
> including 1h and 1q"*), built with the league-models skill. The sport code is
> `EUROLEAGUE`. Season label: the ENDING year (2026-27 is 2027); EuroLeague's
> own code is the starting year (E2026), and the label is threaded from that
> code, never from a date. **No model is live yet**: this file is the
> groundwork, the market grid and the purchase plan.

## What the sources hold (measured 2026-11-12)

| Source | What it holds |
|---|---|
| The odds feed, key `basketball_euroleague` | History from the 2020-21 season (nothing at 2020-06-15; 15 games listed at 2020-10-15). Its event lists, read every second day 2020-09-01 to 2026-11-12, named 2,164 distinct games: 344, 310, 330, 331, 331, 408 and 110 by season (2020-21 to 2026-27 so far; a game moved to another date counts twice there). |
| Its snapshots | One every **5 minutes** on a game day from 2022-23 on (288 on 2022-12-08 and 2025-12-11), every **10 minutes** before that (144 on 2021-03-11; 10 minutes apart on 2021-12-09 and 2022-03-10, 5 minutes on 2022-10-13). A day with nothing moving holds none (2025-12-13). Asked at 05:59, 11:59, 17:59 and 23:59 UTC of every day, a snapshot dated that day answered on 242, 209, 194, 209, 209 and 232 days of the six finished seasons, and 80 of 2026-27's first 104 (8,964 credits, `el_probe7`). |
| Its books (five history snapshots, every region) | 20 books on 2021-03-11, 26 on 2022-12-08, 37 on 2023-12-07, 32 on 2024-12-12, 51 on 2025-12-11. DraftKings priced 8 of 9, 8 of 9, 9 of 9 and 10 of 10 games from 2022-23 on and none in 2020-21; Pinnacle 7, 4, 8, 9 and 10; Bovada on most; FanDuel, BetMGM, BetRivers and Fanatics only in 2025-26. Marathonbet, Unibet and Paddy Power priced every sampled game of every season. **Caesars, Hard Rock and betPARX priced none.** On 12 game days a season read at noon UTC: DraftKings held a moneyline, spread and total on 42 of 42, 49 of 51, 47 of 47, 46 of 46, 61 of 61 and 52 of 52 same-day games, 2021-22 to 2026-27. |
| Its other markets | Only through the per-event endpoint, and only from 2023: a 2022-12 game answered HTTP 422. First half (moneyline, spread, total) at two offshore books in 2024-12; at FanDuel, BetMGM, BetRivers, Fanatics, GTbets, BetUS and MyBookie from 2025-26. First quarter at FanDuel, BetMGM, BetRivers (Fanatics too on one game). FanDuel also posts second-quarter spreads and totals. Team totals (full game and first half), alternate spreads and totals (Pinnacle among them), alternate team totals. **DraftKings priced no period, team-total or alternate market in any sample.** No player prop key answered. |
| Today's board (2026-11-12) | 10 games listed 11-13 to 11-17; 49 books priced at least one. DraftKings, BetMGM and Pinnacle each priced 3 of the 10 (the nearest games): **DraftKings posts late**. |
| EuroLeague's own API (`api-live.euroleague.net`, no key) | `v2/competitions/E/seasons/<code>/games`: a season's every game in one call, with the UTC start, both clubs, the score, the four quarter scores and each overtime, the referees, the venue and a neutral-venue flag. `live.euroleague.net/api` Header, Boxscore (quarter scores, referees, attendance) and PlayByPlay (from 2007-08, per the scout). The whole 2026-27 regular season (380 games) is published. |

### The market grid

Every row gets a verdict. **Status as of 2026-11-12: nothing has been
researched yet, because the price history is not bought** (see "The
purchase"). Inputs held: EuroLeague's finals and quarter scores for 2020-21
on (2,398 games); referees, venue and attendance per game.

| Market | Settles on | Prices | Status |
|---|---|---|---|
| Full-game moneyline | final, overtime included | the feed's full path, 10 books, 2020-21 on | to do (needs the purchase) |
| Full-game spread | final margin, overtime included | the same | to do |
| Full-game total | both scores, overtime included | the same | to do |
| First-half moneyline, spread, total | quarters 1-2 | per-event, 6 books, 2023-24 on (2 offshore books before 2025-26) | to do; trial rows on 3 games stored |
| First-quarter moneyline, spread, total | quarter 1 | per-event, 3 books, 2025-26 on | to do |
| Second-quarter spread and total | quarter 2 | FanDuel only | to do; likely parked (one book) |
| Team totals, full game and first half | one club's points | BetMGM, BetRivers, Fanatics (first half: BetRivers) | to do |
| Alternate spreads and totals | final | BetMGM, BetRivers, Fanatics, Pinnacle | to do |
| Regulation 3-way (a draw after 40 minutes) | quarters 1-4 | `h2h_3_way` at two books on today's board | to do; check depth |
| In play: full game | final | the full path's in-play snapshots (5 minutes) | to do |
| In play: halftime second half | quarters 3-4 | none bought; the per-event endpoint answers in play | to do (needs its own purchase or a live log) |
| Player props | | no player key answered | parked: no price source |
| Futures (champion) | | not checked | parked |

## What differs from the games we already bet

- **FIBA rules:** four 10-minute quarters, 5-minute overtimes. Stored overtime
  share 3.6% to 6.1% a season in the six finished seasons (20 of 328, 13 of 299, 16 of 328, 18 of 331, 12
  of 330, 17 of 402, 5 of 107 so far). Every overtime game was tied after four
  quarters and every regulation tie went to overtime, in every season (the
  stored `went_to_ot` equals `regulation_tie` on all 2,398 games).
- **Totals near 165-176** (Pinnacle's closes on 2025-12-11's ten games).
- **The ids are EuroLeague's**: `EUROLEAGUE_<season code>_<game code>`, which a
  date change cannot split into twins (2020-21 moved several games).
- **Team ids are EuroLeague's three-letter club codes** (MAD, PAN, ULK, TEL
  ...), stable through sponsor renames ("Cazoo Baskonia", "Kosner Baskonia" are
  both BAS).
- **"Home" is not always home.** Read from the stored venues and attendances
  (`euroleague_events`, 2026-11-12): Maccabi Tel Aviv played 53 "home" games in
  Belgrade from 2023-24 on (Aleksandar Nikolic Hall and Belgrade Arena; an
  average attendance of 118, 188, 310 and 218 a season), and one in Limassol;
  Hapoel Tel Aviv 21 in Sofia and Botevgrad (2025-26 on; 816 and 312 on
  average so far in 2026-27); Dubai 6 in Sarajevo and Zenica (2025-26).
  **None is flagged neutral** by EuroLeague's `isNeutralVenue`. The stored
  `neutral_site` is that flag or a Final Four game, so a relocated "home" game
  must be told apart by its venue (an open item, below). 2020-21 was played
  without crowds (Maccabi's home average that season: 624), so a home-edge
  baseline reads it separately.
- **No sharp book problem**: Pinnacle prices most games every season.
- **DraftKings posts nearest the tip and prices no period market**, so a
  first-half or quarter pick names FanDuel, BetMGM, BetRivers or Fanatics, a
  population reported separately (CLAUDE.md §6).
- **The 28 cancelled 2021-22 games** (the Russian clubs' after 2022-02) have an
  event row with status Cancelled and no games row.

## Identity: EuroLeague owns the games row

`data/ingestors/euroleague_teams.py` and `data/ingestors/euroleague_api.py`.

- `euroleague_teams` (club code, newest name, every name carried),
  `euroleague_events` (one row a game: season, phase, round, UTC start, clubs,
  neutral, status, venue, referees, attendance), `euroleague_period_scores`
  (periods 1-4, overtimes 5 on), `euroleague_api_raw` (each season's answer as
  fetched, once per change). Worker-only.
- `games`: sport `EUROLEAGUE`, home_team / away_team the club codes, the
  score filled once (never overwritten), `went_to_ot`, `regulation_tie`,
  `home_win`. Data source `euroleague_api_v2`.
- **The odds feed never mints a EuroLeague game** (`odds_ingestor`
  `RESOLVE_ONLY_SPORTS`). An event is placed on the stored game with the same
  unordered club pair whose start is nearest, within 30 hours; when the feed
  calls EuroLeague's away club home the names are swapped first, so a stored
  spread is the home club's number (CLAUDE.md §4).
- **Feed names** (`config.EUROLEAGUE_ODDS_API_MAP`): the 27 names on the feed's
  2,164 events map to 26 clubs (Fenerbahce appears as "Fenerbahce SK" and
  "Fenerbahçe Beko"). A name outside the map is matched, accent-folded, against
  every name a club has carried, only when exactly one club matches.

**Stored 2026-11-12:**

| Season | Events | Games rows | Scored | Overtime | Neutral | Quarter rows |
|---|---|---|---|---|---|---|
| 2020-21 | 328 | 328 | 328 | 20 | 4 | 1,334 |
| 2021-22 | 327 | 299 | 299 | 13 | 4 | 1,210 |
| 2022-23 | 328 | 328 | 328 | 16 | 4 | 1,328 |
| 2023-24 | 331 | 331 | 331 | 18 | 4 | 1,346 |
| 2024-25 | 330 | 330 | 330 | 12 | 4 | 1,333 |
| 2025-26 | 402 | 402 | 402 | 17 | 3 | 1,631 |
| 2026-27 to 11-12 | 380 | 380 | 107 | 5 | 0 | 433 |

The first write held each season in one transaction of single-row statements
and lost its connection in the fourth season (the transaction was discarded
whole); the writes are batched now (`executemany`), and all seven seasons took
31 seconds.

## The purchase

Two purchases, both bought into Supabase in the same run, both protected from
the odds clean-up (`data/prune_odds.PROTECTED_SOURCES`), and EuroLeague keeps
its whole price path going forward (`PATH_KEPT_SPORTS`).

**1. The full game, every snapshot** (`data/ingestors/euroleague_odds_history.py`,
a fork of the women's college purchase). Moneyline, spread and total at the ten
books of `config.EUROLEAGUE_HISTORY_BOOKMAKERS`: the five a pick may name that
price EuroLeague, Pinnacle and Bovada, and Marathonbet, Unibet and Paddy Power.
Ten named books bill as one region: **30 credits a snapshot** (an eleventh book
billed 60). It walks the feed's own chain a UTC day at a time, spools each
answer, and stores pre-game quotes change-only in `odds` (source
`odds_api_euroleague_history`) and every in-play quote in
`euroleague_inplay_quotes`, with one ledger row a snapshot in
`euroleague_odds_snapshots`.

- **The trial, 2025-12-11:** 288 snapshots, 8,640 credits, 2,963 pre-game rows
  and 2,683 in-play rows, every event placed (0 unresolved names, 0 pairs with
  no game). Read back: all ten books on all ten games, and every home favourite
  carries a negative stored spread (Milan +2.5 and Virtus +3.5 as home
  underdogs).
- **The estimate for every season**, from the census (the share of a day's
  four asks answered within 10 minutes, times 288 or 144 slots, times 30):
  about 0.69M (2026-27 to date), 1.90M, 1.66M, 1.67M, 1.48M, 0.80M and 1.01M,
  newest first: **about 9.2M credits**.

**2. First half, quarters, team totals and alternates**
(`data/ingestors/euroleague_period_history.py`). One per-event call per game
at 24 h, 12 h, 6 h, 3 h, 2 h, 1 h, 30 and 10 minutes before the tip, for the 31
period, team-total and alternate keys, at the ten books of
`config.EUROLEAGUE_PERIOD_BOOKMAKERS`. It bills 10 credits per market a book
actually returns.

- **The trial, the newest date:** 24 answers, 2,633 rows, 2,821 credits
  (about 117 a call, 11 to 13 markets returned).
- **The plan:** 9,360 (game, time) pairs on the 1,170 played games of 2023-24
  to date; at most 2,902,436 credits (every key at every time), **about 1.1M**
  at the trial's rate.

**The floor.** The plan holds 15M credits a cycle; it refilled 2026-11-08 and
11,605,707 were left after the trials. The platform's own burn measured
58,664 a day. Both purchases stop before the balance would fall under 33 days
of that burn (1,935,912): the days to a refill on 12-08 plus the 7-day
reserve. At about 10.3M for both, about 9.7M fits above that floor this
cycle; the oldest days (part of 2020-21) would wait for the refill and resume
from the spool.

**Not started at scale.** Both are waiting on (a) this branch's merge, because
until the clean-up protects these sources in production it would thin bought
first-half rows to an opener and a close, and (b) mike's yes to the spend.

## The forward collection

From the merge, the worker's odds passes pull EuroLeague with every other
sport (`odds_ingestor.SPORT_KEYS`), at the line-shop ten plus
`config.EUROLEAGUE_EXTRA_BOOKMAKERS` (thirteen books, two regions: 6 credits a
pass), resolved onto the stored schedule and kept even when DraftKings has not
posted (`DK_GATE_EXEMPT_SPORTS`). The schedule and finals come from the
`euroleague-games` step (`euroleague_api --current`): in the 6am pipeline
before the odds step, and on every hourly refresh pass. Not yet built: a live
first-half and quarter fetch at the decision times.

## Open items

- A forward first-half and quarter fetch (the per-event endpoint, live).
- Relocated "home" games: a club-arena table, so a home game away from the
  club's own city is known before a model reads home advantage.
- The research: baselines on every grid row, the leads in
  `docs/euroleague_market_audit.md`, then the method search.

Commands (from a checkout with production settings):

    python -m data.ingestors.euroleague_api --seasons 2021 2027 --apply
    python -m data.ingestors.euroleague_odds_history --seasons 2021 2027 --spool DIR --fetch --store --reserve-days 33
    python -m data.ingestors.euroleague_period_history --seasons 2024 2027 --apply --floor 1936000

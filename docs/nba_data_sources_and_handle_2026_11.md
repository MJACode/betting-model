# NBA data sources, and handle / money data across markets (2026-11-26)

mike, 2026-11-26: *"Research other nba data sources - props and game makers as these models have
been weak. Research broadly across all markets reliable data source for handle / money data on
betting - confirm this data would be helpful."*

Two parts. Part A is measured here, on production data (read-only queries, 2026-11-26). Part B is
web research (vendor pages, papers), and every claim in it names its URL. Units are 1 unit to win,
risk capped at 3, at the price stored with the row.

## A. Measured

### A1. The live NBA record this season

`picks`, `sport='NBA'`, `signal_type='BET'`, game dates 2026-10-20 to 2026-11-25, settled, leaving
out `VOID` / `DUPLICATE` and rows marked `downgrade_reason = 'model paused'` (a paused model keeps
writing its BET rows with that marker; every record query leaves them out). This is the `picks`
table, not the Discord-published view (`v_discord_published`).

| Model | Bets | W-L | Units | Return |
|---|---|---|---|---|
| `nba_prop_projection` | 128 | 47-81 | -15.98 | -15.7% |
| `nba_team_total_luck` | 39 | 20-19 | -1.13 | -2.6% |
| `nba_total_luck` | 37 | 18-19 | -2.71 | -6.7% |
| `nba_first_half_total_luck` | 21 | 13-8 | +4.01 | +17.2% |
| `nba_prop_market` | 18 | 6-12 | -5.69 | -33.1% |
| `nba_live_spread_q12` | 15 | 8-7 | +0.17 | +1.0% |
| `nba_prop_first_basket` | 10 | 2-8 | +1.01 | n/a (plus-money) |
| `nba_q1_trend` | 1 | 1-0 | +1.00 | n/a |
| **All** | **269** | **115-154** | **-19.32** | **-7.9%** |

The two prop models are -21.67 of the -19.32 units. Both have been in `config.PAUSED_MODELS`
since the low-volume plan merged (2026-11-22 18:06 UTC); their 21 BET rows since then carry the
pause marker and are not in the table above.

### A2. What splits data is stored

| Table | Source | Window | Timestamped before the start? |
|---|---|---|---|
| `nba_public_splits` (`archive_undated`) | Action Network consensus (book 15) | 2020-12-22 to 2026-11-25, about 7,200 regular-season games | No: the split at the close, known only after tip (`docs/nba_public_splits.md`) |
| `nba_public_splits` (`pregame_poll`) | Action Network consensus | 2026-10-20 to 2026-11-25, 270 games, 45,248 rows | Yes (`observed_at`) |
| `public_betting` | Action Network consensus, MLB | 2026-05-31 to 2026-10-28, 1,541 games | Mostly overwritten after the start; about 136 games pre-commence (`docs/mlb_market_handicap_features.md`) |
| `scoreboard_splits_history` | Action Network consensus: NBA 78 games, NHL 84, NCAAF 88, NFL 19, NCAAB 6 | 2026-11-16 on | Yes (`snapshot_at`) |
| `scoreboard_splits_history` | DraftKings Network (DraftKings' own Handle % and Bets %): NFL 30 games | 2026-11-16 on | Yes |

### A3. Does the NBA closing split predict results at the closing line?

`nba_public_splits`, `archive_undated`, `quality IS NULL`, v2 where it exists else v1, seasons
2020-21 to 2025-26, graded at the consensus line and price stored with the split. Every cell
graded is shown. Break-even at -110 is 52.38%.

**Spreads** (home cover = margin + home number > 0):

| Rule | Bets | Win % | Units | Return |
|---|---|---|---|---|
| Fade the side with tickets >= 60% | 3,960 | 48.99 | -281.0 | -6.56% |
| >= 65% | 2,661 | 49.56 | -156.9 | -5.45% |
| >= 70% | 1,641 | 48.98 | -116.6 | -6.58% |
| >= 75% | 896 | 49.03 | -62.3 | -6.47% |
| >= 80% | 391 | 49.74 | -21.3 | -5.09% |
| Follow money when money % - tickets % >= 10 | 3,241 | 49.75 | -178.3 | -5.08% |
| >= 15 | 2,310 | 50.09 | -110.2 | -4.40% |
| >= 20 | 1,629 | 50.16 | -75.1 | -4.25% |
| >= 30 | 743 | 50.75 | -25.2 | -3.11% |

**Totals:**

| Rule | Bets | Win % | Units | Return |
|---|---|---|---|---|
| Fade over tickets >= 60% (nearly all unders) | 5,127 | 49.90 | -269.6 | -4.83% |
| >= 65% | 4,199 | 49.34 | -271.4 | -5.92% |
| >= 70% | 3,372 | 49.19 | -229.8 | -6.23% |
| >= 75% | 2,642 | 48.95 | -194.2 | -6.73% |
| >= 80% | 2,010 | 48.60 | -163.6 | -7.45% |
| Follow money, gap >= 10 | 3,244 | 51.90 | -31.2 | -0.88% |
| >= 15 | 2,651 | 51.83 | -29.4 | -1.02% |
| >= 20 | 2,126 | 51.83 | -24.1 | -1.04% |
| >= 30 | 1,286 | 51.88 | -13.2 | -0.94% |
| Every under (baseline; this row also holds 2026-27 to date) | 7,114 | 49.66 | | -5.27% |

The gap >= 15 totals cell by season: 51.47% (552 bets), 51.99% (763), 49.93% (735), 54.53% (593),
then **7 bets in 2024-25 and 1 in 2025-26**, because the gap itself disappeared (A4).

**Moneyline:** fade tickets >= 65 / 75 / 85: -4.23% / -5.00% / -3.47% (4,905 / 3,655 / 2,252
bets). Follow money gap >= 15 / 30 / 45: -5.34% / -2.11% / -2.21%.

**Read:** no cell of 24 clears break-even on six seasons. The only cell above a coin flip is the
totals money gap (about 51.9%), below break-even at the consensus price, chosen as the best of
nine, and it cannot be bet any more because the source stopped producing the gap.

### A4. Action Network's money % stopped being a separate measurement after 2023-24

Absolute gap between money % and tickets %, home / over side, closing archive:

| Season | Moneyline median (p90) | Spread median (p90) | Total median (p90) |
|---|---|---|---|
| 2020-21 | 21 (53) | 13 (33) | 18 (44) |
| 2021-22 | 18 (52.6) | 14 (33) | 22 (49) |
| 2022-23 | 19 (49) | 16 (36) | 19 (44) |
| 2023-24 | 19 (58) | 14 (35) | 16 (41) |
| 2024-25 | 8 (26) | 3 (9) | 2 (6) |
| 2025-26 | 6 (22) | 3 (10) | 1 (4) |
| 2026-27 pre-tip polls | 5 (21) | 4 (14) | 3 (9) |

Both endpoints (v1 and v2) show the same break, so it is the source, not our parser. Over the same
November 2026 NFL games, DraftKings Network's Handle % vs Bets % has a median gap of 12 (moneyline),
11 (spread) and 16 (total), against Action Network's 8 / 3 / 1 (`scoreboard_splits_history`,
counted over stored snapshot rows, not games). So since 2024-25 the free Action Network "money %"
is close to a copy of its ticket %, and the "sharp money vs public tickets" reading cannot be made
from it. Why it changed: Part B, B3.

### A5. Does an early split predict where the line goes?

2026-27 NBA pre-tip polls: the last poll at least 4 hours before the listed start (mean 4.5 h)
against the last poll in the final 20 minutes, 251 games.

| Market | corr(tickets lean, move) | corr(money lean, move) | corr(money - tickets, move) | Games where the line moved | Mean move |
|---|---|---|---|---|---|
| Spread (home number) | -0.022 | -0.088 | -0.124 | 95 | 0.51 pt |
| Total | +0.051 | -0.004 | -0.116 | 136 | 0.63 pt |

One standard error is about 0.063. The gap correlation is about two standard errors in both markets
but points the right way on spreads (money on the home side, home number falls) and the wrong way
on totals. Inconclusive. Most games do not move at all in the last 4.5 hours.

### A6. The one splits model that went live

`mlb_total_public_fade` (fade 70%+ over tickets): 33 settled bets, 14-18-1, -5.28 units
(`picks`, read 2026-11-26).

### A7. When the Action Network break happened, and how it compares with DraftKings

- **Date.** Over-side totals, v1 archive, median gap by month: 2023-12 12, 2024-01 16, 2024-02 12,
  2024-03 19, 2024-04 25, then **2024-10 1**, 2024-11 2, 2024-12 2, 2025-01 2. The change happened
  in the 2024 offseason. NBA is the only sport with history that far back, so it is not known
  whether other sports broke on the same date.
- **Same NFL games, both sources** (`scoreboard_splits_history`, last stored snapshot per game,
  19 games, November 2026): correlation of bets % 0.95 on the moneyline, 0.78 on the spread and
  -0.21 on the total. Average over-bets share: DraftKings 67.6%, Action Network 54.3%. That is not
  a swapped side. The two sources describe different bettor pools.
- **DraftKings splits are collected for NFL only.** Every `dk_splits` pass in the worker log
  (2026-11-25 23:20 to 2026-11-26 13:17 UTC) reports `event_groups: {'NFL': '88808'}`. The code
  lists NBA, NHL, MLB and NCAAF (`data/ingestors/dk_splits.SPORTS`), but `discover_event_groups`
  never finds a link for them on the page, so nothing is fetched for them.

## B. Web research

**Confidence limit on this whole part.** Three research passes ran on 2026-11-26. None of them
could open a page: WebFetch was refused for every host tried (vsin.com, dknetwork.draftkings.com,
rotowire.com, opticodds, ideas.repec.org, stat.berkeley.edu), and the shared search budget ran out
before the passes were complete. Every fact below comes from search-result summaries of the page
named, not from the page. Prices in particular must be read off the vendor page before anything
is bought.

### B1. NBA sources not already used

| Source | What it adds | History, and whether dated | Cost | Fit |
|---|---|---|---|---|
| The Odds API historical props (already paid for) | Earlier prop snapshots: the open, line movement, when props post. Our prop history is one snapshot at tip minus 60 | From 2023-05-03, 5-minute snapshots, dated | 10 credits per region, market and event per snapshot. One extra snapshot a game, 5 markets, 1,230 games: 61,500 credits. Balance 964,499 (`odds_api_quota`, 2026-11-26 14:11 UTC) | Props. The only candidate with full, honest history and no new vendor |
| Dunks & Threes EPM API (dunksandthrees.com) | Daily player ratings, game and box-score predictions | Every day since 2001-02, built from data before that date only (their methodology) | Price not found; individual-use licence | Props and game markets. Its published accuracy compares with an unnamed baseline, not the line |
| DARKO (darko.app) | Per-player, per-game minutes and box-score projections; a new market-implied player rating | Back to 1996-97, but described as "retrospective pregame estimates": likely today's model re-run, so a backtest on it is optimistic | No price found; a public MCP endpoint exists | Props (minutes, rates) |
| TheDailyAverage historical projections | DFS projection CSVs saved at 7pm and 10:30pm daily | Dated files since 2018-12-13 | Not found | Props, if the files carry minutes and per-stat columns (not checked) |
| Sleeper pick counts (unofficial scrapers) / prizepicksapi.com | Over and under pick counts on player props: the only prop-level "public" signal found | None; collect from now on | Scraper cents per 1,000 lines; terms not checked | Props |
| Polymarket NBA markets | A second exchange beside Kalshi; NBA reportedly named Kalshi and Polymarket its prediction-market partners on 2026-10-26 (not verified) | Fine-grained price history kept 7 to 90 days only | Free API | Both, after forward collection. One paper on 173 NBA games found the markets efficient (arXiv 2605.00864) |
| SportsDataIO, RotoWire | Projected and confirmed lineups, injuries, news | No as-of history (SportsDataIO says it keeps no point-in-time snapshots) | Not published | Props, forward only |
| Establish The Run | Prop projections; self-reported 2021-22 to 2025-26 prop records of +9.5% to +22.1% (unaudited) | No archive, no API | $89.99 a week (page date unknown) | Not machine-usable |

Two timing facts that bound what any lineup feed can do (from search summaries): **NBA starting
lineups are confirmed 30 minutes before tip** (Board of Governors, 2019-09-20), and **referee crews
are posted about 9:00am ET**. Both NBA prop models decide 45 to 57 minutes before tip, so they can
never see a confirmed lineup; only a projected one.

Screened out: Cleaning the Glass, LEBRON, PBP Stats, Basketball-Reference (all derived from the
nba.com data already stored, or no dated history); Synergy/hustle/matchup endpoints (already in
nba_api, no as-of history); referee tendency sets (one walk-forward backtest reports no edge over
the market, low confidence); ShotQuality (our shot-quality test was null).

### B2. Handle and money sources, all markets

| Source | Whose money | Dated history | Access |
|---|---|---|---|
| Action Network consensus (stored) | Undisclosed panel of books; money % no longer separate since 2024 (A4) | None as a product; we capture our own | Free JSON; PRO reportedly $24.99/month |
| Action Labs (the old Sports Insights / Bet Labs database) | Historically an offshore panel; money % "from one of the sharper offshore sportsbooks" (old SI page) | Back to 2003 per SI; observation times not disclosed; no bulk export found | Reportedly $249.99/month |
| DraftKings Network (stored, NFL only) | DraftKings' own Handle % and Bets %, cumulative since the market opened | None; we capture our own | Free page |
| VSiN, DraftKings view | Same DraftKings data, "updated every 5 minutes" | None found | VSiN Pro, price not verified |
| VSiN, Circa view | **Circa Sports' own handle and bets** (the only Circa source found) | A per-game Circa history URL exists; content not seen | VSiN Pro |
| Covers consensus | Contest picks, not money | Dated pages | Free |
| ScoresAndOdds, SportsBettingDime, Pregame, WiseGuyTeam and others | Undisclosed; ScoresAndOdds shares Action Network's owner (Better Collective); SBD's wording matches Action Network's | None | Free |
| Kalshi trades | Real matched money on Kalshi, every trade timestamped | Public historical trades endpoint | Free API |
| Polymarket trades | Real matched money (international book; a US exchange since Dec 2025) | Timestamped trades on the international data API | Free API |
| Betfair Historical Data | Matched volume and prices, 1-second (Advanced) or tick with order book (Pro) | Since May 2015 | Basic free; US sports sit in an "Other Sports" package whose price was not found; non-US customers, thin on US sports |
| State regulators (NJ, NV, PA) | Statewide totals | Monthly | Free; useless per game |

Not researched (budget): Oddsshark, BetQL, TeamRankings, Pikkit, Juice Reel, SharpAPI, Circa's own site.

### B3. Why Action Network's money % changed

No public statement, changelog or discussion was found (eight searches). The help-centre article
"PRO Money Percentages" was updated 2025-06-20; what changed is not visible. One hypothesis fits
A4 and is unconfirmed: the money % used to come from one sharper book (as Sports Insights' did),
and since 2024 it comes from the same retail panel as the bets %.

### B4. Published evidence on whether splits predict anything

Abstract-level only (no paper was opened):

- **NBA specifically: null.** Paul and Weinbach (2008), *International Journal of Sport Finance*
  3(3), four sportsbooks' betting percentages, NBA 2004-05 to 2006-07: favourites and overs are
  over-bet, and betting against the public does not win more often than efficiency implies.
- Positive results exist only in sample and outside the NBA: NFL spreads 2006-07, the NFL last
  hour, NHL big imbalances (Paul and Weinbach, 2011 and 2012).
- DraftKings Network splits, 1,139 MLB games (Dmochowski 2026, arXiv 2609.06739, preprint): the
  pooled bet-share and outcome link disappears once games are split by which side the book
  favoured.
- Reverse line movement on NCAAF totals is not profitable (Francisco and Moore 2019).
- Line movement at sharp books does carry information (the close beats the open: Gandar et al.
  1998; Buchdahl on 1.67M Pinnacle events), but moves also overshoot (Simon 2024; Moskowitz 2021).
  Any value is in the price before the move, not in following it.
- Exchange takers lose on average (Whelan, Betfair order book): aggressive flow is not, on
  average, informed.
- **No study found tests whether splits add information once the closing price is known, or
  whether splits predict later line movement, or anything on props.** A3 above is that test for
  the NBA at the close, and it is null.
- Practitioner records (Sports Insights, Action Network systems, VSiN) are filters chosen in
  sample, graded at unstated or better-than-market prices. The one out-of-sample season found
  (VSiN, NFL 2025, fading the ticket majority) is 145-133, 52.2%, below break-even at -110.

## C. Verdict

**Handle data: not confirmed helpful. What was measured points the other way.**

1. The free consensus source we already store has no exploitable information about NBA results at
   the close: 24 cells over six seasons, none clears break-even (A3). The one published NBA study
   is null as well.
2. Its money column has not been a separate measurement since the 2024 offseason (A4, A7), so the
   "money against tickets" reading that splits services sell cannot be made from it for NBA.
3. Whether an early split predicts the line is unsettled on 251 games (A5).
4. The live splits model lost (A6).
5. The sources that could still carry information are a single named book's own handle
   (DraftKings, Circa via VSiN) and exchange trade prints (Kalshi, Polymarket), captured with our
   own timestamps. None has a history to backtest, so any test is forward: store from now, then
   grade the early split against Pinnacle's no-vig close (CLV) and against the result.

**NBA: the losses are in the prop models** (-21.67 of -19.32 units, A1). The candidates that could
be tested honestly on history are earlier prop snapshots from The Odds API (already bought, about
61,500 credits per extra snapshot per season) and Dunks & Threes' dated daily ratings (price
unknown). Everything else (lineups, news, pick'em counts, Polymarket) has no usable history and
only pays after forward collection.

## D. Second pass (2026-11-26, mike: "1) yes 2) yes, it doesn't take weeks why can't we get historical data somewhere 3) yes. More and deeper research on data sources")

Everything here was run on the Railway `prop-probe` service (open egress), because the dev
sandbox refuses every data host (agent-proxy HTTP 403) and the request to widen this session's
network was rejected. Probe: `scripts/research_probe_2026_11_26.py`, writes nothing. Its output
is the service's deploy log (deployments `93e9a3bd` and `b14f9fbf`, 2026-11-26).

### D1. When NBA props post at The Odds API (probe, 1,116 credits)

Six games, the latest tip on six dates across the three seasons, `player_points` asked at 30 to 1
hours before tip, then the five markets at 10 and 6 hours. Players listed per book:

| Game | First answer with props | DraftKings players, -10 h / -1 h | Pinnacle at -10 h |
|---|---|---|---|
| GSW @ DEN 2023-11-08 | -30 h | 10 / 14 | 8 |
| BKN @ POR 2024-01-17 | -18 h (5 books, 2-3 players) | 6 / 13 | 3 |
| MEM @ LAL 2024-11-13 | -18 h | 8 / 6 | 8 |
| BKN @ LAC 2025-01-15 | -18 h | 8 / 12 | 9 |
| DEN @ LAC 2025-11-12 | -18 h | 13 / 16 | none (posted by -8 h) |
| WAS @ LAC 2026-01-14 | -24 h (Hard Rock only) | 11 / 13 at -4 h | 11 |

At 30 hours the event is not yet listed (HTTP 404, 4 of 6). Blocks and steals at DraftKings and
FanDuel stay thin at both 10 and 6 hours; Hard Rock, BetMGM and Caesars list them in full by 10.
A call costs 10 credits per market RETURNED, so an empty early answer costs nothing.

**Chosen lead: 10 hours (600 minutes)**, the earliest point at which most books list most
players and Pinnacle was present in 5 of 6. Bought for every 2023-24 to 2025-26 regular-season game.

### D2. The purchase

`python -m data.ingestors.nba_odds_history --props-early --lead-min 600 --seasons 2024 2026
--max-credits 186000 --floor 500000 --apply`, started 14:59 UTC: 3,690 games on 487 dates, about
41 credits a game measured on the first 63. Rows: `nba_prop_odds_early` (worker-only, RLS on,
anon and authenticated have no SELECT, read 2026-11-26); ledger `nba_prop_early_fetches`, one row
per game asked, rows or none. Kept out of `player_prop_odds` so every reader of those seasons
keeps its one snapshot a game.

### D3. Historical money data that exists, measured

| Source | What is there | History | Read from the worker |
|---|---|---|---|
| **Kalshi, KXNBAGAME** (game winner, one YES contract per team) | Every trade: time, YES price, contracts, **taker side**, block flag | Settled events from **2025-04-15** (play-in) to 2026-11-25: 1,785 events; every regular-season month from 2025-10 | Yes. Trades before 2026-09-27 come from `/historical/trades` (the exchange's cutoff that day) |
| Kalshi, KXNBASPREAD / KXNBATOTAL | Same, spread and total ladders | From 2025-10-21, 1,661 events each | Yes |
| Kalshi player props (KXNBASTL, KXNBA3PT, KXNBAPRA, KXNBALADDERPTS, others) | Same | KXNBASTL from 2026-01-13 | Yes |
| **Polymarket NBA games** | Every trade: time, outcome, BUY / SELL, price, size, **the wallet** | Game events from 2024-04 (play-in) and every regular-season month from **2024-10**; volume summed from the event list: 2024-11 222 games $39.5M, 2025-01 214 games $86.4M, 2025-03 329 games $103.4M | Yes, data API **v2** (`/v2/trades?conditionId=`); v1 answers 410 "retired" |
| Wayback Machine (archived DraftKings / VSiN / Action Network splits pages) | Dated page captures | Not measured | **No**: connection refused or timed out on all 10 patterns from Railway; proxy 403 from the sandbox |
| VSiN DraftKings and Circa splits | DraftKings' and Circa's own handle and bets | Not measured | **No**: Cloudflare 403 from Railway |
| Betfair historical data | Matched volume, 1-second or tick | Since 2015; the "Other Sports" package does include basketball, American football, baseball and ice hockey (Betfair support page, read) | **No**: the data site refuses US addresses |

Example sizes (Kalshi): MEM @ GSW 2025-04-15, the MEM contract: 1,324 trades. UTA @ LAC 2026-01-01,
the UTA contract: 29,064 trades and 8.92M contracts, in-game included.

**So historical money data with real timestamps does exist, for free: exchange order flow on every
NBA game since 2025-10 (Kalshi) and 2024-10 (Polymarket).** It is not sportsbook handle; it is
money matched at an exchange, signed by the side that took liquidity. Imported by
`data/ingestors/nba_exchange_flow.py` into `nba_exchange_flow` (15-minute buckets per team, before
the listed start only) and `nba_exchange_flow_fetches`.

### D4. Smaller facts from the same run

- **DraftKings Network splits page:** its HTML carries only NFL's event group (`tb_eg=88808`); the
  sport menu links to content pages, so `dk_splits.discover_event_groups` can never find another
  sport. DraftKings' own ids are already in the repo (`data/ingestors/dk_live_board.LEAGUES`: NBA
  42648, NCAAB 92483, NCAAF 87637).
- **Action Network PRO** (its own page, read 2026-11-26): $14.99 a week, $24.99 a month, $119.99 a
  year. Money percentages are a PRO feature.
- **TheDailyAverage** historical projections: the NBA archive runs to 2019-03-30 only, behind a
  members' login. Not useful for 2023-26.
- **DARKO** (about page): free, updated after every game, history to 1996-97.
- **Dunks & Threes:** API documentation at `/api/v2/documentation`; a subscribe page; no price on
  the pages read in the first run.
- **arXiv 2609.06739** (Dmochowski, submitted 2026-09-06) exists; abstract read.

### D5. The earlier snapshot, graded: `nba_prop_market`'s rule at 10 hours against 1 hour

The purchase finished at 15:46 UTC: 3,690 games, 940,309 rows, 30 games with nothing posted at
10 hours, 7 feed events not in `games`, **182,647 credits** (balance 778,051).

The rule, unchanged from `models/nba_prop_market.py`: Pinnacle's coherent two-way quote (implied
sum 1.00 to 1.15) gives the no-vig under; every soft book in `BEST_LINE_BOOKMAKERS` at Pinnacle's
exact line, its own quote coherent, under at -200 or better; EV = fair under x decimal - 1 > 0;
the best EV per player and market. Graded on the box score (`minutes > 0`; a push is no result),
1 unit to win, risk capped at 3. Same games, same three markets bought early (points, rebounds,
threes), no card cap. Early = `nba_prop_odds_early` (tip minus 10 hours); late = the existing
tip-minus-55-minute purchase in `player_prop_odds`. Queries in this session's scratchpad
(`early_replay.sql`), run per season, read-only.

| Season | Early bets | Early units | Early per bet (90% CI) | Late bets | Late units | Late per bet (90% CI) |
|---|---|---|---|---|---|---|
| 2023-24 | 2,962 | +210.9 | +7.1% (+4.0 to +10.2) | 5,027 | +265.3 | +5.3% (+2.9 to +7.7) |
| 2024-25 | 2,487 | +102.2 | +4.1% (+0.7 to +7.6) | 5,026 | +51.2 | +1.0% (-1.4 to +3.4) |
| 2025-26 | 2,123 | +124.9 | +5.9% (+2.3 to +9.5) | 5,198 | +73.9 | +1.4% (-0.9 to +3.8) |
| **All** | **7,572** | **+438.0** | **+5.8% (+3.8 to +7.7)** | **15,251** | **+390.4** | **+2.6% (+1.2 to +3.9)** |

Return on risk by season, early / late: +6.74% / +4.93%, +3.74% / +0.94%, +5.63% / +1.33%.
By market, all seasons, early: points 3,228 bets, rebounds 2,397, threes 1,947; each positive
every season.

**Closing check, 2025-26:** of 2,201 early candidates, 1,967 have a Pinnacle quote at tip minus 55
minutes. The line moved toward the under bettor on 254 and against on 259; on the 1,454 where it
stayed, the early price's EV against Pinnacle's LATER no-vig under averages **+0.78%** (2.58% at
the bet), and 56.6% are still +EV at that later price.

**Read with care:**
- **Two arms, one population.** The two arms share most propositions, so the difference between
  them is not two independent samples. Early has half the bets because fewer books and fewer
  Pinnacle quotes are up at 10 hours.
- **Results run ahead of the closing check.** Early's results (+5.8% a bet) run well ahead of its
  closing-line value (+0.78%), so part of the gap is likely variance.
- **Limits.** A 10-hour price is quoted with lower limits at most books; whether it can be bet at
  size is not measured.
- **Not a ship decision.** This is a frozen rule applied at a time it was never tuned on, so it
  is out of sample for timing. Moving `nba_prop_market`'s decision time is a model update
  (`Updated-By`), and the model is paused.

### D6. Historical money, tested: Kalshi order flow against Pinnacle (1,437 games)

Imported 2026-11-26 15:53 to 16:33 UTC: **1,494 regular-season games** (2025-10-21 to 2026-11-25),
7,896,928 trades before the listed start, about $727M of contracts bought before tip, 566,956
fifteen-minute rows. 291 settled events did not match a `games` row: October preseason games,
playoff games, one non-NBA opponent (`LIO`) and one event with no markets. Sanity: Kalshi's last
pre-tip home price against Pinnacle's no-vig close, 146 games of 2026-27: correlation 0.9966,
mean absolute gap 1.33 points.

Test (read-only SQL, this session): Pinnacle's no-vig home price at its last snapshot 6 to 12
hours before tip (`p6`) and its last snapshot in the 90 minutes before tip (`pc`). Early flow =
contracts bought on the home team minus the away team, as a share of both, from Kalshi buckets
that closed before Pinnacle's `p6` snapshot. One standard error of a correlation is shown.

| Measure | 2025-26 (1,169 games) | 2026-27 (268) | Both (1,437) |
|---|---|---|---|
| Early flow vs Pinnacle's LATER move (`pc - p6`) | -0.073 | -0.078 | **-0.074** (SE 0.026) |
| Kalshi price minus Pinnacle at `p6`, vs the later move | -0.041 | +0.059 | -0.021 |
| Flow after `p6` vs the move in the same window | +0.124 | +0.236 | +0.145 |
| All pre-tip flow vs result minus Pinnacle's close | +0.034 | +0.125 | +0.050 |
| Price gap at `p6` vs result minus close | -0.012 | +0.074 | +0.004 |

**A trap caught on the way:** taking Kalshi's price "6 hours out" without aligning it to Pinnacle's
snapshot time gave a correlation of **+0.498** with Pinnacle's later move (2026-27, 188 games).
Aligned so every Kalshi trade is strictly before Pinnacle's snapshot, it is **+0.049** on the same
season. Pinnacle's "6 hour" snapshot was often older than Kalshi's last trade, so Kalshi was simply
showing a move that had already happened.

Fading lopsided early flow (back the side the early money did not take) at Pinnacle's `p6`
no-vig price, both seasons:

| Lopsided at least | Games | CLV to Pinnacle close | Result minus fair |
|---|---|---|---|
| 0.2 | 1,172 | +0.22 pts (SE 0.09) | -2.73 pts (SE 1.26) |
| 0.3 | 1,035 | +0.26 (0.09) | -2.44 (1.34) |
| 0.4 | 879 | +0.28 (0.10) | -2.84 (1.43) |
| 0.5 | 715 | +0.33 (0.10) | -3.85 (1.55) |

**Read:** real money with real timestamps is available, and on 1,437 NBA games it tells nothing the
Pinnacle price lacks.
- **Early flow** is followed by Pinnacle moving slightly the other way. That is worth about
  0.3 points of closing value to fade, below any sportsbook margin.
- **Results:** the outcomes lean the opposite way, about 2 standard errors. The two measures
  disagree.
- **Late flow** moves with the line, which it should.

Neither cell is a bet.

### D7. Polymarket, Dunks & Threes, DraftKings splits

**Polymarket import.**
- **First run (16:45 UTC), 1,052 games under `source = 'polymarket'`: incomplete, do not read.**
  Games 2024-10-22 to 2025-03-22, ledgered with at most 500 trades each. The v2 trades API pages
  by cursor only (it answers 400 to an offset, "pages are cursor-only"), and that run read no
  cursor. The rows are kept (no row is deleted) and labelled in the code.
- **The full import** runs under `source = 'polymarket_all'`:
  - it reads the cursor from the body or a header;
  - a read that cannot page raises, and the game is not ledgered;
  - games are fetched one by one by slug (`nba-<away>-<home>-<ET date>`, our codes in lower
    case), because the keyset event list stopped after one page of 100.

**Dunks & Threes** (its own pages, read from the worker 2026-11-26):
- **Price:** Basic $24.95 a year, Premium $49.95 a year, Premium + API $250.00 a year.
- **API (v2):** 90 requests a minute. Endpoints for EPM and skills, team EPM, game predictions and
  box-score predictions. Every row carries `asof_dt` / `update_dt`, and EPM runs from 2001-02.
- **The history is the current model run over past dates.** `epm_source` is "v2 for every date
  currently served", so the as-of history was recomputed by today's model, with hindsight in
  the model, not in the data.
- **Terms:** a personal licence; reproduction and automated copying are prohibited, and so is
  commercial exploitation "except with our express written permission". Using it inside a paid
  app's models needs their written permission.

**DraftKings splits for NBA, NHL and NCAAF.** The page answers for each league when asked by
event group directly: NBA 42648 parsed 5 games, NHL 42133 parsed 7, NCAAF 87637 parsed 10, every
team of the right league (probe `dk2`). `data/ingestors/dk_splits.KNOWN_EVENT_GROUPS` now holds
them; the worker runs master, so they are collected only once this branch is merged. NCAAB
(92483) parsed 10 games, but the ingestor has no NCAAB team matcher yet.

### D8. Historical money, tested: Polymarket order flow against Pinnacle

**The import.** `source = 'polymarket_all'`, 2026-11-26 17:22 to about 18:00 UTC: 2,659 games
ledgered (2,604 read after they were played), 4,587,085 trades before tip, about $902.9M of
shares bought before tip.
- **Trades are taker-only:** the API accepted `takerOnly=true`, so each trade is signed by the
  side that took liquidity.
- **82 slugs not found,** mostly late October 2025.
- **3 games refused** because their trade count was an exact multiple of 500: a full last page
  with `has_more` false and no cursor, refused by design.
- **55 games were ledgered before their tip,** games not yet played on the first corrected run.
  The fix now skips them, and every test here requires the ledger row to postdate the tip.

**The test.** Same as D6, with Pinnacle's `p6` and close, early flow from buckets closed before
`p6`:

| Season | Games | Early flow vs Pinnacle's later move | Flow after `p6` vs the same window's move | All flow vs result minus close |
|---|---|---|---|---|
| 2024-25 | 1,174 | -0.046 (SE 0.029) | +0.203 | +0.005 |
| 2025-26 to 01-14 | 486 | -0.115 (SE 0.045) | +0.156 | -0.092 |
| 2025-26 from 01-15 | 592 | -0.066 (SE 0.041) | +0.145 | +0.107 |

**Read:** the same as Kalshi.
- **Early flow:** Pinnacle then moves slightly against it, in every cut on both exchanges.
- **Late flow:** moves with the line.
- **Results beyond the close:** nothing; the sign flips between the two halves of one season.

## E. Verdict after the second pass

1. **Historical money data exists and is now stored.** Kalshi (1,494 games, 2025-10 on) and
   Polymarket (2,604 played games, 2024-10 on) are real matched money with real timestamps, in
   Supabase (`nba_exchange_flow`).
2. **On about 3,700 game-seasons it carries no information the Pinnacle price lacks.** The one
   consistent effect, early flow followed by a small move the other way, is worth about 0.3
   points of closing value, below any sportsbook margin.
3. **Retail sportsbook handle with history still cannot be bought or rebuilt:**
   - VSiN is Cloudflare-blocked from the worker, and the Wayback Machine refuses it.
   - DraftKings' own splits for NBA, NHL and NCAAF start collecting once this branch is merged.
4. **The earlier prop snapshot is the more promising lead.** `nba_prop_market`'s frozen rule at
   10 hours returned +5.8% a bet on 7,572 bets against +2.6% at 1 hour on the same games, ahead in
   every season. Its 2025-26 value against Pinnacle's later price was +0.78%.

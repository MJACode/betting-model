# Horse racing — scope and design

Planning only. Written 2026-11-15. No ingestor, no model, no `picks` row, and
no code that places a bet or logs into a sportsbook or an ADW (TwinSpires,
TVG, FanDuel Racing, NYRA Bets, and the rest).

Prices and coverage below were read that day from the vendor page named in
the cell, unless the cell says the figure comes from the 2026-11-14 research
note or from a secondary write-up. A cell that was not re-fetched says so.
Nothing here is a threshold, a stake, or a pause.

The repo already takes a sport from a feed to a graded unit. Racing has to
use that path. It is a bad fit for the two-sided tables, and this doc says
where the fit breaks and what to add.

## How a sport already works

Traced from `config.py`, `data/db_setup.py`, `tracking/paper_tracker.py`,
`tracking/published_units.py`, `tracking/discord_notifier.py`, `docs/clv.md`,
`docs/discord.md`, and `.claude/skills/league-models/references/shipping.md`
(the NCAABW and EuroLeague commits are the recent shape of a new sport).

| Step | Where it lives | What it assumes |
|---|---|---|
| Ingest | `data/ingestors/`, `run_pipeline.py`, a scheduler job | A game has two sides. Prices land in `odds` as home/away (and a draw). Bought rows carry a `source` so a re-run imports nothing twice. |
| Schedule row | `games` | `home_team` and `away_team` are required. Settlement of a full-game moneyline reads `home_win`. |
| Decision | a card under `scripts/` or `models/`, gated by `models/honest_ev.gate` and `config.min_ev_for` | One model, one cut, one EV floor. The first BET locks. A later line does not delete or overwrite the row. |
| The pick | `picks` | `pick_side` is home, away, over, or under (or a player key for a prop). `pick_label` must match the fields. The price is `COALESCE(decision_odds, dk_odds)` in American odds. A missing price is not filled in. |
| Units | `published_pick_unit_profit` / `stake_for` | 1 unit to win, risk capped at 3. `result` is WIN, LOSS, PUSH, or NO_ACTION. The published record and the units are the same graded bets. `profit_flat` is not that record: an unpriced pick graded through the settler is treated as −110. |
| CLV | `docs/clv.md`, `clv_method = standard_v2` | Same-book raw price, last pre-start snapshot, same line. Pinnacle's no-vig close is the second number. In-play picks are left out. The public average includes only `standard_v2`. |
| Publish | `config.DISCORD_SPORTS` | `DISCORD_CHANNEL_<SPORT>` or `DISCORD_WEBHOOK_<SPORT>`. Live picks go to `DISCORD_CHANNEL_LIVE_<SPORT>`. The app, Discord, and push read the same `picks` rows. |
| Worker | `scheduler.py` | A card is a job with a `RUN_<X>=0` kill switch and a heartbeat. The Odds API key is for the sports already on that feed. |

UFC is the closest precedent for a sport whose result is not a home score:
`_settle_ufc_picks` bypasses `_compute_result`, and a fight that is never
run is `NO_ACTION` with the row kept. Golf is the closest precedent for a
field: `golf_odds` is its own table, one row per player per market per
snapshot, because `odds` has no column for an 8th runner. Golf was retired
2026-09-08 and is not a model to copy.

What does not fit:

- A race has a field, not a home side and an away side. `odds.home_price` /
  `away_price` cannot hold it. `games.home_win` cannot grade it.
- The price is often a pool dividend or an exchange back price, not an
  American two-way line. Takeout means the raw implied probabilities sum to
  more than 1. There is no Pinnacle close.
- Several horses can be bet in one race, and at most one of them can win
  (a dead heat aside). Two win bets in one race are the side-conflict case
  the other sports already refuse.
- The close is a final tote, an official SP, or a Betfair starting price.
  It is not a row in `odds` with `snapshot_type = 'close'`.
- US tote odds are not on The Odds API. The sports list at
  `https://the-odds-api.com/` (fetched 2026-11-15) has no racing. A racing
  job must not spend `ODDS_API_KEY`.

The published record still has to be `picks`. A side table of "race bets"
that the unit functions never see would be a second ledger. This repo does
not have one.

## 1. Data sources

Thoroughbred only. Harness, quarter horses, Arabians, and greyhounds stay
out until a later scope says otherwise. Dubai cards mix thoroughbred and
Arabian; an ingestor has to keep them apart.

### Prices that were re-read on 2026-11-15

| Source | What it actually covers | Price read that day | Limit that matters here |
|---|---|---|---|
| [JCapper Flex / HDW](http://www.jcapper.com/horseracingdata/) | North American thoroughbred past performances (`.JCP`) and chart files. The search snippet of that page: Silver $5.95 per download day, cap $89/month; Platinum $7.95 per download day, cap $119/month, after 15 download days. The JCapper FAQ on the same site still describes a $119/month unlimited HDW plan. | Those two figures, from the page text returned by search. A direct fetch of the Flex page returned HTTP 500. | No API. Files. The 2026-11-14 note says the server keeps 45 days: not re-checked on the 500 page. Store the file in Supabase the day it is downloaded. |
| [TrackMaster Plus Pro XML](https://www.trackmaster.com/products/thoroughbred/trackmaster_plus_pro) | North American thoroughbred XML, including the fields the software shows. | $5 a card; 20 downloads $49.95/month; unlimited $149.95/month. | Notice on that page, updated 2025-06-09: the TrackMaster copy of the Plus Pro *software* no longer works. Standalone data files on that site still do. One US file vendor, not HDW and TrackMaster together. |
| [Equibase downloadable full charts](https://www.equibase.com/premium/eqpViewSubscription.cfm?Incltxt=eqpViewDownloadableChartsDisplay.cfm) | Chart results, speed figures, final odds. | $219.95 for one month (the page's 1-month row, expiry shown as 2026-12-15). | Results and final odds. Not a live tote and not a past-performance file. |
| Equibase 2023 complimentary set | Full-year 2023 past performances and charts. Registration at `equibase.com/handicappersdata.cfm`. Press release 2024-03-11. | $0 | DRF (2024-03-11) reported the clickwrap: internal, non-commercial testing only, and no public display or dissemination of the data or of analyses or derivatives. That forbids training a model here and then posting its picks. Usable for a private method check only after the agreement Mike signs is read. Not the production store. |
| Equibase industry feed | Official PP, simulcast, tote. | Quote only. Not priced in public. | This is the license if a personal file plan does not allow a published model. |
| [The Racing API coverage](https://www.theracingapi.com/data-coverage) | Three datasets on one page. Core: "UK, Ireland, Hong Kong and global group level thoroughbred races and selected handicaps." North America add-on. Australia add-on. | Pound prices were **not** on the pages fetched 2026-11-15. `/pricing` returned 404. The homepage FAQ says today's cards, odds, and results update every 3 minutes, tomorrow every 15 minutes, and the paid rate limit is 5 requests/second. | Terms (fetched that day): resale forbidden; not for a betting operator or a sportsbook; accounts are individual. The FAQ also lists "betting models, strategies and automated trading programs" as an allowed use. Those two sentences are the license question in §9. |
| [Betfair historical data bulk prices](https://support.developer.betfair.com/hc/en-us/articles/360019984158-Are-bulk-purchase-discounts-available) | Horse racing exchange history. The article was updated 2026-09-24. | Advanced £69/month or £699/year. Pro £230/month or £2,299/year. | A developer-support example of the download API lists GB, IE, and US among countries in one response. That example is not a current coverage count. Australian and New Zealand customers are told, on the Betfair data-science guide, to email before buying from the UK historic site. Pro is 50 ms; Advanced is 1 second. Basic (1-minute, no volume, described as free on that guide) was not on the 2026-09-24 price table. Confirm Basic before treating it as free. |
| [JRA-VAN Data Lab](https://jra-van.jp/buy/) | JRA races, including odds, back to the mid-1980s. A 2026-08 write-up counted 21.6 million records from 1986. | ¥2,090/month, tax included, for the data lab software alone. | Staff post 2025-11-05: JV-Link is a Windows COM component, not a REST API. The Railway worker cannot call it. A Windows machine would have to pull and write Supabase. |
| [Krok Odds API](https://krokodds.com.au/api-access) and [terms](https://krokodds.com.au/terms) | Australian thoroughbred, harness, and greyhound. Fixed odds, tote, Betfair back/lay and BSP, results, form, sectionals. | API plan A$49/month: 50,000 credits, 500 requests/minute, 60-second cache. Free tier 50 credits and 5 requests/minute. Overage A$0.005/credit, opt-in. | Personal, non-transferable. Display inside one's own product is allowed with the attribution line on the same screen. Redistributing the data through Discord, or selling odds, arbitrage, or EV analytics to the public or for a fee, is outside that grant. A private tool that is not offered to the public and is not charged for is permitted. Harness and greyhounds come along; do not score them as thoroughbreds. |
| [Punting Form pricing](https://puntingform.com.au/pricing) | Australian, Hong Kong, and Singapore form. Modeller adds an API, historical Betfair prices, and point-in-time modelling data. | No dollar amount on that page. Modeller is `sales@puntingform.com.au`. | Modeller is personal use. Commercial use is a separate quote. Singapore racing is historical (the club's last meeting was not re-checked here). |
| [turf.bzh API licence](https://www.turf.bzh/api-licence.php) | French programme, runners, live PMU odds, results. The docs say the history starts 2025-02-01 (32,954 races and 376,873 runners as of 2026-10-31). | €49.90 once, and only while a Premium subscription is active. The Premium price was not on the pages read. | 120 requests/minute and 20,000/day. Personal. Not an official PMU feed. |
| PMU official feed | The AGEBAN affiliate charter fetched that day is a sportsbook XML feed, not a racing-results license. [boturfers.fr](https://www.boturfers.fr/blog/comment-recuperer-les-donnees-du-pmu) says the PMU infocentre quotes professionals at tens of thousands of euros a year and that scraping the site is forbidden. | No public price. | Do not scrape PMU. |
| [Emirates Racing Authority](https://emiratesracing.com/) | UAE cards and results (Meydan, Abu Dhabi, Jebel Ali, and the other ERA tracks), thoroughbred and Arabian. | No public API price found. | HTML results. Not a feed. |

### The Racing API, by region

Fetched from the coverage page on 2026-11-15. The homepage hero says "full
data coverage" for the UK, Ireland, Australia, and North America. The FAQ on
the same homepage says the core service is UK, Ireland, and Hong Kong, plus
group races and selected handicaps worldwide, and that the Australia and
North America add-ons are unavailable to new subscribers. The coverage page
matches the FAQ, not the hero. The hero is not the entitlement.

Core dataset, 364,537 results, labelled group-level and selected handicaps
outside UK, Ireland, and Hong Kong. Counts for 2026 are year-to-date on the
day the page was fetched (2026-11-15):

| Region | 2026 | 2025 full year | What that implies |
|---|---:|---:|---|
| Great Britain | 8,730 | 10,123 | The vendor calls GB coverage complete. |
| Ireland | 2,546 | 2,892 | Same, for Ireland. |
| Hong Kong | 737 | 842 | The vendor calls HK coverage complete. 737 against last year's 842, with the season still open, is the full HK card rather than a stakes slice. |
| France | 2,723 | 1,865 | Inside the core set, and larger than a group-race list. The page does not say it is every French race. |
| USA | 199 | 440 | Stakes and selected races only. The full US card is the add-on. |
| Australia | 190 | 403 | Same. The full Australian card is the add-on. |
| UAE | 150 | 223 | Not labelled complete. ERA's own site is the card; this is a slice. |
| Japan | 74 | 147 | Not the JRA calendar. About one graded slice. |
| Germany | 21 | 74 | A slice. |
| Canada | 9 | 41 | A slice. Full Canada is on the North America add-on (2,618 results in 2026). |
| Other regions | 158 | 289 | South Africa, Scandinavia, and the rest are not broken out. |

North America add-on, 133,792 results: USA 31,149 in 2026 and 35,492 in 2025,
Canada 2,618 in 2026. The page says the add-on is required. The FAQ says new
subscribers cannot buy it.

Australia add-on, 341,864 results. The 2026 cells on the state rows add to
27,131 (VIC 7,880, NSW 7,345, QLD 5,955, WA 2,622, SA 2,007, TAS 743, NT 392,
ACT 187). New Zealand is not a state on that table. The FAQ says this add-on
is also closed.

Pound prices, from the 2026-11-14 research note and from an 2026-10-18
review that quotes the same numbers (Free, Basic £27.99, Standard £59.99,
Pro £99.99, full-history add-on £499, US add-on +£49.99, Australia add-on
+£49.99). They were not on a vendor page this session could open. Confirm
them in the dashboard before paying. Standard, per that note, is bookmaker
odds plus 12 months of results. Pro adds odds history. The US add-on being
closed matches the FAQ.

### Regions this plan will not pretend to have a feed for

| Region | What exists | Why it is not in the first build |
|---|---|---|
| Japan | JRA-VAN Data Lab, ¥2,090/month, full history, Windows only. Racing API core: 74 results in 2026. | The worker is Linux. A Windows pull is a separate machine and a separate approval. |
| France, full card | Official PMU feed is quote-only. turf.bzh is cheap, short (from 2025-02-01), and personal. Racing API core holds 2,723 France results in 2026. France Galop's public page that was fetched is a calendar subscription, not a database. | No licensed full-card price path with a history long enough for the backtest in §3. |
| Dubai / UAE | ERA publishes cards and results. Racing API core: 150 results in 2026. | No priced feed found. Seasonal, and Arabian races must not be mixed into a thoroughbred model. |
| Germany, Scandinavia, South Africa | Core "other" and Germany rows above. Goalserve advertises a $200/month horse-racing package covering UK, USA, South Africa, France, and Sweden; the price page still carries a discount "until 30/06/2025". | A reseller page with a stale sale date is not a source of record. |
| South Korea, New Zealand as its own card | Not found as a priced English API this session. NZ may appear inside a Betfair AU file; that was not counted. | Parked. |
| Brisnet | A 2016 Brisnet article lists a Data Plan at $125/month. | That is not a 2026 price. Left unpriced. |
| Horse Racing Nation data files | $299/month in the 2026-11-14 note. | Not re-fetched. |
| Timeform API | "from £500/month" in the 2026-11-14 note, GB/IE. | Not re-fetched. A ratings vendor, not required for the first model. |
| Goalserve, BettorServe, FormFav, horseracedatabase.com | Each claims a wide country list. horseracedatabase.com lists HK from €19.90/month and UK from €29.90/month. | Terms not read, except where a page was fetched. Not the recommendation. |

### Recommendation

**Cheap tier, the one to buy first** if the licenses in §9 come back as
usable for this repo:

| Piece | Role | Cost |
|---|---|---|
| HDW via JCapper Platinum | US and Canadian thoroughbred past performances and result charts, every day the worker runs | $119/month cap |
| The Racing API, core, Standard if the dashboard still sells it at the noted price | UK, Ireland, Hong Kong cards, odds, and results. Group and selected races elsewhere, as a catalogue, not as a model | £59.99/month, unconfirmed on 2026-11-15 |
| Betfair Historical, horse racing, Advanced | Timestamped exchange prices, including the US markets the file actually contains, plus BSP | £69/month, or £699 for 12 months |

Monthly, in the currencies on the invoices: **$119 + £128.99**. The pound
half depends on the Racing API dashboard still showing £59.99. No FX
conversion is stated here because none was looked up.

Equibase's free 2023 year is a method check under whatever agreement is
signed. It is not loaded into the production tables and it does not train a
model whose picks are posted.

**Serious tier**, still one US file vendor:

| Piece | Role | Cost |
|---|---|---|
| HDW Platinum, or TrackMaster unlimited XML | The US file. Pick one. | $119 or $149.95/month |
| Equibase industry quote | If the personal file license does not allow publishing | unknown |
| Equibase charts | Only if the chosen PP file lacks final odds and figures the model needs | $219.95/month, otherwise skip |
| The Racing API Pro, plus the £499 history add-on if more than 12 months is required | Odds history for UK, Ireland, Hong Kong | £99.99/month + £499 once, both unconfirmed this session |
| Betfair Advanced, or Pro if a 1-second grid is too coarse to measure the close | The price path and the BSP | £69 or £230/month |
| Krok API | Australia, only after a commercial reading of §6.1 of their terms against the paid app | A$49/month |
| JRA-VAN | Japan, only with a Windows puller that writes Supabase | ¥2,090/month |

Do not buy the North America or Australia Racing API add-ons until the
dashboard offers them. The coverage is real and the door is shut.

US fixed-odds ADW prices (Monmouth-style fixed odds, a bookmaker's racing
price) were not found as a feed The Odds API or a public API sells. The
bettable US price in this plan is the Betfair back price before the off.
The tote is the close, not the price the pick claims to have taken, except
where §5 says otherwise.

## 2. Schema

New tables, all written by the ingestor in the same run that fetches them,
keyed by `source`, revoked from `anon` and `authenticated`. One idempotent
migration registered in `data/view_migrations.py` `ACTIVE_MIGRATIONS`, ahead
of the two posted-stake migrations that have to stay last. A local file of
the same rows is a cache or it is a bug.

Names below are the proposal. Types follow the repo (text ids, ISO dates,
numeric prices).

`racing_meetings`

- `meeting_id` — `{source}:{country}:{track_code}:{YYYY-MM-DD}`
- `source`, `country`, `region` (`US`, `GB`, `IRE`, `HK`, `AU`, `FR`, `UAE`, `JP`, …)
- `track_code`, `track_name`
- `meeting_date`
- `discipline` — `thoroughbred` for anything this plan scores
- `going`, `weather` — as published that day, with `as_of`

`racing_races`

- `race_id` — stable, from the source's own id when it has one, otherwise
  `{meeting_id}:R{n}`
- `meeting_id`, `race_number`, `post_time` (timezone-aware)
- `distance_m` (store metres; furlongs are a display conversion)
- `surface` (`dirt`, `turf`, `synthetic`, `hurdle`, `chase`)
- `race_class`, `purse`, `race_type` (maiden, claiming, handicap, stakes, group)
- `field_size`, `track_condition`, `status` (`scheduled`, `off`, `official`,
  `abandoned`, `void`)
- `game_id` — unique, the bridge into `games`
- `source`

`racing_runners`

- `(race_id, horse_id)` unique
- `horse_name`, `program_number`, `post_position`
- `jockey_id`, `jockey_name`, `trainer_id`, `trainer_name`
- `weight_lb` or `weight_kg` plus the unit column, `age`, `sex`
- `official_rating` (UK OR, HK rating; null in the US)
- `morning_line_decimal` — a display quote, never a decision price
- `equipment`, `medication`
- `coupled_entry`
- `scratched_at` — null until a scratch is declared
- `source`

`racing_past_performances`

- One row per past start, as that start was known on a card date
- `as_of_date` — the morning the PP was published. A line whose race is the
  race being scored is a leak and is rejected
- `horse_id`, prior `race_id` when we have it, else the chart's own keys
- finish position, beaten lengths, distance, surface, going, class, purse,
  speed figure, pace figures, that day's odds
- `source`

`racing_results` and `racing_result_runners`

- Official after the race: status, finish position, official position after
  any DQ, beaten lengths, dead-heat flag
- Win, place, and show dividends in the pool's own currency and stake unit
  (`dividend_stake`, so a US $2 payoff is not read as a $1 payoff)
- `final_tote_decimal` for win, and place/show when the pool existed
- `source`

`racing_odds_snapshots`

- `(race_id, horse_id, book, market, snapshot_at)` unique
- `market` — `win` or `place` in the first build. Exotic markets get a
  column only when they are in scope
- `book` — `betfair`, `betfair_bsp`, `final_tote`, `sp`, or a named
  bookmaker
- `decimal_odds`, `american_odds` (the exact float, not a rounded integer),
  `size_matched` when the file has it, `pool_amount` when the tote file has it
- `snapshot_type` — `board`, `bsp`, `final_tote`, `sp`
- `source`

`games` gets one row per race so `picks.game_id` still has a parent.
`sport` is `RACING` (North American thoroughbred) or `RACING_INTL`.
`home_team` is the track name, `away_team` is `R{n} {race_name}` truncated
to whatever the column already allows. `season` is the calendar year of
`meeting_date` because `games.season` is a required integer; the racing
season, where it straddles a year, lives on `racing_meetings`. Scores and
`home_win` stay null. The generic settler skips both sport codes the way it
skips `ufc_%`.

### The pick

A graded racing bet is a row in `picks`. The racing tables describe the
race. They do not hold a second record.

| `picks` column | Racing value |
|---|---|
| `sport` | `RACING` or `RACING_INTL` |
| `game_id` | the race's `games` row |
| `model_id` | `racing_us_win` or `racing_intl_win` when those models exist. Not registered by this doc. |
| `pick_side` | horse slug. Not `home` or `away`. |
| `pick_label` | `{Horse Name} win`, produced by one formatter and checked by `tracking/pick_integrity.py` |
| `prop_market` | `racing_win` (later `racing_place`) |
| `player_key` | `horse_id`. Settlement joins on this, as a prop joins on the player. |
| `model_probability` | the probability the bet was sized from, after the Benter blend |
| `dk_odds` / `decision_odds` | American float of the decimal price taken. Round-trip through `_decimal_or_none` has to land back on that decimal. A test pins it. |
| `decision_book` | `betfair` or the named book. `final_tote` only when the bet is a tote bet and a displayed tote price existed at decision time. |
| `dk_implied_prob` | `1 / decimal` of the reference price. Raw, takeout still in it. |
| `edge` | `model_probability − dk_implied_prob` |
| `scored_line` | null. It is the home number for spreads. Place terms do not go here. |
| `signal_type` | `BET`, `AVOID`, or `NONE` |
| `stake_units` | null, so the published stake is 1 unit to win. A different stake is a later decision, asked for by name. |
| `is_live` | true only for a bet taken after the off |

Every runner the model scores gets a row. `BET` is the one horse in that
race, for that model, whose edge and EV both clear and whose price is known.
The other runners are `NONE`, or `AVOID` when the model is shorter than the
market by the cut. `AVOID` means the horse is overbet. It does not mean bet
the rest of the field. Two `BET` rows on the win market of one race cannot
both win, so the card writes one.

The lock is the first `BET` on that runner for that model. A later tote
move leaves the row alone. A scratch of that horse after the bet is
`NO_ACTION`, row kept, same shape as a UFC fight that is never run. A
scratch before the decision means no row for that horse.

`profit_flat` is whatever the shared settler writes. Readers of the racing
record use `published_pick_unit_profit` at `COALESCE(decision_odds, dk_odds)`.
An unpriced runner is not a `BET`. The −110 fallback must not grade one.

## 3. Modeling

The method is the one in the 2026-11-14 note. The papers were not re-read
this session. The implementation has to match this description, and the
backtest has to fail a leakage check before anyone trusts a number.

### Stage 1 — Bolton–Chapman conditional logit

One race is one observation. For runner `i` with features `x_i`,

```
P(i wins) = exp(β · x_i) / Σ_j exp(β · x_j)
```

The softmax is over the horses who are still in at decision time. A
scratched horse is out of the denominator. Coefficients are fit only on
races whose `as_of_date` is before the race, walk-forward by year. A random
split of races is not a test.

Features, all known on the morning of the race, all relative to the field
where the public research treats them that way:

- Last-start speed figure, and a shrunk figure from the last three starts
  on the same surface
- Change in distance, change in surface, change in class (purse or official
  rating)
- Days since last start, with a separate layoff flag
- Post position, as a track-and-distance rate shrunk toward the field
- Early pace and late pace, enough to say whether the field has one
  front-runner or four
- Jockey and trainer strike rates, shrunk, computed from starts strictly
  before this race
- Weight and any apprentice claim
- Age and sex
- Equipment change (blinkers on or off)
- US medication only when the PP still prints it
- Going, joined from the meeting as it stood at `as_of_date`

The public probability is not a stage-1 feature. Putting it there makes
stage 2 untestable.

### Stage 2 — Benter

Fit on a later window than stage 1:

```
logit(p*) = a + b · log(p_model) + c · log(p_public)
```

`p_public` is the implied probability of the price available at the decision
timestamp, normalised by the sum of the field so the takeout is not counted
twice. The bet uses `p*`. A positive `b` that survives the later window is
the evidence the fundamentals add something to the public. A fit with `b`
near 0 and `c` near 1 is a null: the model has no information past the
pool. That result is written down and not re-run without a new feature.

### Harville, later

Out of the first build. When exotics are opened:

```
P(i 1st, j 2nd) = p_i · p_j / (1 − p_i)
```

Harville over-rates a favourite in second. The discount (Benter, or Lo and
Bacon-Shone) is estimated on finishes, not assumed. Exacta, trifecta, and
the multi-race pools (daily double, Pick 3, Pick 6) each need a price that
`stake_for` can grade. A $2 ticket whose dividend is unknown until the pools
close is the tote problem in §5. They stay parked until win and place have
a settled record.

### What the market baseline is

Before any coefficient is fit, the same races report:

- Bet the public favourite, 1 unit to win, at the decision-time price
- Bet in proportion to `p_public`, same stake rule
- The takeout on that pool, from the chart, not from a single assumed 15%

The 2026-11-14 note says takeout is 15% or more. The stored dividend and
the final odds are what we will measure. A model that matches the public
and loses the takeout has not found anything.

### Backtest

- Decision price is the last snapshot at or before the chosen lead (propose
  30 minutes before `post_time`, and report the neighbourhood 60 / 30 / 15 /
  5, not a single peak).
- Final tote and BSP are the closes. They are not the price taken.
- A race with no snapshot before the off is unscored. Morning line does not
  fill it.
- Walk-forward by year. Early years fit, later years grade. Then an
  early/late split inside the graded years.
- Every scored runner is in the file (`BET`, `AVOID`, `NONE`). The cut is
  read off that file.
- Units are `stake_for` at the decision price. Also report return on risk,
  in the same table, so a longshot's small risk is visible. The published
  number is the `stake_for` number.
- Sample size, bet count, and a confidence interval. A cut that adds a sliver
  of units and a pile of bets is the worse cut.
- Each model's own edge cut, probability cut, price floor, and EV floor are
  set from that replay, just under its own written EV. The repo default
  price floor is −200. Laying shorter than that needs an explicit ask, the
  same rule that removed the EuroLeague big-favourite moneyline
  (2026-11-14).
- Leakage checks the backtest must fail before the fix: a PP row dated on
  race day that includes today's finish; a jockey strike rate that includes
  today's ride; a speed figure joined from the result chart of the race
  being scored; final odds used as `p_public` at decision time.

No row is written to `picks` by the backtest. The first `picks` rows are the
live card, after a market clears, and they count.

### Markets, in order

| Market | First build | Settles on |
|---|---|---|
| Win | Yes, if the backtest clears | Official first, after DQ. Dead heat: §6. |
| Place | After win has a settled record | The place definition stored at decision time (US place pool, or a Betfair place market with its own price). UK each-way is two bets and is not this row. |
| Show | Parked | US show pool. Same dividend problem as place. |
| Each-way | Parked | Win leg and place leg would be two `picks` rows sharing a decision id. The unit function has one result per row. |
| Exacta, trifecta, multi-race | Parked, with the Harville note above | A dividend, not a pre-off American price. |

## 4. CLV

`standard_v2` stays the sports average. Racing does not join it. A racing
close is not a Pinnacle two-way price, and mixing the two would move the
number `v_public_track_record` already publishes.

New stamp, proposed `racing_v1`, excluded from the `standard_v2` average
the way older stamps already are. `market_clv_*` stays null. There is no
sharp-book fallback and no tote-for-exchange fallback.

Same arithmetic as `docs/clv.md`, on decimals:

```
taken = 1 / decimal_taken
close = 1 / decimal_close
clv_pct = (decimal_taken / decimal_close − 1) × 100
```

`decimal_taken` is the decision price. `decimal_close` depends on the book
the bet was taken at:

| Bet taken at | Close | If that close is missing |
|---|---|---|
| Betfair back price | Betfair SP (BSP) for that market | `clv_pct` null. Final tote is not filled in. |
| A named bookmaker's fixed price | That book's last pre-off price. Official SP is stored beside it and is not the headline. | null |
| A displayed tote price | Final tote dividend, as a decimal | null |

The snapshot has to be after `created_at` and at or before the off for a
fixed or exchange price. BSP and the final tote are produced at the off.
A bet with `created_at` after the off is in-play and is not in this CLV.

Our own stake is inside a tote pool if the bet was actually placed into it.
At 1 unit on a major pool that impact is small; on a small place pool it is
not. The close is still the published final. We do not invent a
"pool without us" number. The system does not place the bet, so it does not
know the stake went in.

## 5. Grading, units, staking

`stake_for` is unchanged. Conviction is 1 unit to win. Risk is
`1 / (decimal − 1)`, capped at 3. When the cap binds, the win is recomputed
from the capped risk.

| Decimal | American | Risk to win 1u |
|---|---|---|
| 5.0 | +400 | 0.25u |
| 2.0 | +100 | 1u |
| 1.5 | −200 | 2u |
| 1.25 | −400 | 3u risk, 0.75u win |

A 10.0 winner adds +1 unit and risked 0.111. A 10.0 loser subtracts 0.111.
The papers' flat-stake ROI is a different number. The replay prints both.
The record shows `stake_for` only.

`kelly_fraction` is stored, as on every other pick, and does not size the
bet. Tenth-Kelly and a pool-impact cap are a stake change. They wait for an
explicit ask. They are not a second column of "model units."

Settlement is a racing function next to `_settle_ufc_picks`, not a new arm
inside `_compute_result`.

| Outcome | `result` | Units |
|---|---|---|
| Official win (or place, for a place bet), no dead heat | WIN | `published_pick_unit_profit` at the price taken |
| Official loss | LOSS | minus the risk |
| Race abandoned, or our horse scratched, or a void market | NO_ACTION | 0, row kept |
| Dead heat | not WIN and not PUSH | see below |

A dead heat on a fixed or exchange win pays about half the stake at full
odds and loses the other half. Profit is `0.5 × win − 0.5 × risk`, which is
neither WIN nor PUSH nor LOSS. The published function does not know that
result today. The first racing bet is not graded until it does, and until a
test of that function has been watched failing without the change. The taken
price stays immutable. The settlement rule is a result code, not a rewritten
`decision_odds`.

UK Rule 4 (a deduction after a scratch of a different horse) does not apply
to a Betfair matched bet. It does apply to a UK bookmaker fixed price. The
first model takes exchange prices, so Rule 4 is not on the first card. A
later fixed-odds card needs the deduction in the same result code, before
it grades.

Place terms are part of the bet. A US place pool, a Betfair place market,
and a UK bookmaker's "3 places at 1/5" are three different contracts. The
row stores which one it is (`racing_place` plus a terms column on a
`racing_bets` detail table: `places`, `fraction`, `book`). Grading uses
that row, not today's field size.

Coupled entries are one ticket when the pool couples them. The card treats
the entry as one runner in the softmax and one pick.

DQ: official order, not the photo finish.

## 6. Discord, scheduling, cost

Two sports, because the notifier routes on `picks.sport` and the request is
a US channel plus an international channel.

| Sport code | Channel variable | Live variable |
|---|---|---|
| `RACING` | `DISCORD_CHANNEL_RACING` | `DISCORD_CHANNEL_LIVE_RACING` |
| `RACING_INTL` | `DISCORD_CHANNEL_RACING_INTL` | `DISCORD_CHANNEL_LIVE_RACING_INTL` |

Both go in `config.DISCORD_SPORTS`. Both live sports go in
`DISCORD_LIVE_CHANNEL_REQUIRED`, so a missing live channel does not post
into the pre-game channel and mark the pick sent. Creating the channel is a
worker job that has been refused when run unattended. The ask is one
message: the two channels, the two live channels, and the four variables.

Live is real where a price feed updates before the off:

- UK, Ireland, Hong Kong: The Racing API's 3-minute card. A poll in the last
  hour can post a late bet to the international live channel.
- Australia: only if Krok (or an open Australia add-on) is licensed. The
  paid Krok cache is 60 seconds.
- US: no live tote API in the cheap tier. Betfair pre-off prices can move,
  and a US live channel is justified only for those exchange prices. A
  morning pick with no later quote does not get a live post.
- Japan, France-beyond-the-core-slice, Dubai: no live channel until a feed
  exists.

The app, Discord, and push show the same picks. A license that allows a
private Discord post and forbids a paid app means the sport does not publish
on any surface, until the license covers all three. It does not mean a
Discord-only record.

Schedule, all of it behind `RUN_RACING_US=0` and `RUN_RACING_INTL=0`:

| Job | When | What |
|---|---|---|
| File ingest | Once, after the day's HDW or TrackMaster file is available | Parse, write Supabase, stop. The vendor keeps a short window; the database is the copy. |
| Card | A region window, not only the 06:00 ET pipeline. UK first races are morning US time. Australian races are the US night. Hong Kong is US morning. US cards are afternoon and evening ET. | Score, lock, publish. |
| Price poll | Every 15 minutes until 30 minutes out, then every 3 minutes, meeting endpoints rather than one call per runner | Stay inside 5 requests/second. Write snapshots. Do not rescore a locked bet. |
| Settle | After `status = official` | The racing settler. Charts can be amended; a later official change updates the result in place only through the same settler, with the prior result kept in `picks_log`. |
| CLV | The settle pass | Stamp `racing_v1` or leave it null. |

Heartbeats and `MAX_SILENCE` follow the other cards. Active hours differ by
region; a silent Australian night must not page as a dead US job.

Cost and quota:

- Racing does not call The Odds API. The sports quota is unchanged.
- The Racing API at 5 requests/second is enough if each call is a meeting.
  A Saturday in Britain is tens of races, not thousands of calls.
- Krok's 50,000 credits at 1 each for a live call, and 5 for an archive
  call, is the cap to measure on the first week and then set a reserve
  against. No estimate of the burn is stated here.
- HDW is a file download, once a day. Betfair history is a purchased file,
  ingested after it is on disk. Neither is a polling loop.
- Vendor keys are their own Railway variables (`RACING_API_KEY`, and a Krok
  key if that tier is bought). They are not `ODDS_API_KEY`.

No job logs into Betfair Exchange, an ADW, or a sportsbook. Buying the
historical files and dropping them where the ingestor can read them is a
manual step. A later Betfair download-API session is a login and needs its
own approval even if it only reads.

## 7. Phases

Effort is the surface area, not a calendar. Each phase is a PR of the kind
`shipping.md` already describes. A phase that does not clear does not start
the next one.

**Phase 0 — decisions.** No code. The questions in §9. A "yes" on regions
and licenses is what makes phase 1 legal to run.

**Phase 1 — store the files.** Schema and migration in §2. An importer for
HDW (or TrackMaster) and, separately, a private loader for the Equibase 2023
set that refuses to run if a publish flag is set. `source` markers. Tests
that a second run inserts nothing. A worker job that ingests a file already
obtained. No `picks`, no Discord, no model id in `config.py`. This is the
groundwork commit: the sport exists as tables and is dark.

**Phase 2 — the backtest, off to the side.** A script that fits stage 1 and
stage 2, prints the baseline, the neighbourhood, the early/late split, the
units, and the leakage checks. Output is a doc under `docs/`, the way the
UFC audit is a doc. It does not register a model and does not write `picks`.
If `b` is indistinguishable from 0, or no cut beats the public after
takeout, the written result is a null and phase 3 does not start.

**Phase 3 — one live win model, one region.** Whichever region phase 2
cleared, with a timestamped price. Config entries (`ACTION_THRESHOLDS`,
`MODEL_EDGE_THRESHOLDS`, `MODEL_PROB_THRESHOLDS`, `MODEL_MIN_ODDS`,
`MODEL_OWN_EV_FLOOR`, `SCORING_METHODS`), the card, the scheduler job, the
settler, the dead-heat result in the unit function, `racing_v1` CLV, the
Discord variables, the app chip and the UX review. `Updated-By:` on that
commit, from whoever asked to ship it. The first worker run is watched:
heartbeat, first `NONE` rows, first `BET`, the same pick on Discord and in
the app.

**Phase 4 — the other region.** US and international are different sport
codes and different channels. Australia only with a feed we can actually
subscribe to and a license that covers the app. Japan only with the Windows
pull described above. France and Dubai stay parked.

**Phase 5 — place.** Its own model id, its own price, its own terms column.
Each-way and exotics stay parked, with the Harville formula already written
here so the next session does not invent a different one.

**Phase 6 — live channels.** Only the regions whose pre-off feed is in
production. `DISCORD_LIVE_CHANNEL_REQUIRED` from the first live post, not
after a mis-post.

### Risks

| Risk | What it does |
|---|---|
| License vs the paid app | The app, Discord, and push are one surface. A personal-use grant that forbids publishing analytics for a fee blocks the whole sport, not just the app. |
| Equibase 2023 clickwrap | DRF's report of the agreement forbids disseminating derivatives. Loading that year into a model that posts picks is the violation. |
| Add-ons closed | Full US and full Australia on The Racing API are visible on the coverage page and not for sale. HDW and Krok are the substitutes, not the add-on. |
| No US tote tape | A backtest that bets final odds is betting the close. Phase 2 has to refuse that. Races Betfair does not list are not bet. |
| JRA-VAN on Windows | A Linux worker job cannot be the Japan ingestor. |
| Dead heat and the unit function | Grading a dead heat as WIN overstates the payout. Phase 3 waits on the result code. |
| `games` bridge | Anything that settles `RACING` through `home_win` grades nonsense. The exclusion is a test, watched failing. |
| American round-trip | Rounding 3.45 to +245 and back changes the stake. Store the exact float. |
| Takeout | A well-calibrated copy of the public loses the takeout. The baseline table is there so that loss is visible. |
| NONE-row volume | A full US card is on the order of the add-on's 31,149 races in 2026, times the field. The picks table grows by every scored runner. Index `(sport, game_date, model_id)` with the migration, and confirm the settle query still uses it. |
| Amended charts | A DQ after the first official can flip a graded pick. `picks_log` has to show the previous result. |
| Pool impact | Ignored at 1 unit on a major win pool. Revisit before any place-pool or small-track staking change. |

## 8. Decisions needed

These block phase 1 or phase 3. Defaults are not assumed.

1. **Budget.** The cheap stack is $119/month (HDW Platinum) plus £59.99
   (Racing API Standard, confirm on the dashboard) plus £69 (Betfair
   Advanced). Serious tier adds a possible Equibase industry quote, Krok at
   A$49, and JRA-VAN at ¥2,090, and swaps Betfair to £230 if the 1-second
   file is too coarse.
2. **Which region first.** US on HDW + Betfair, or UK/Ireland/Hong Kong on
   The Racing API + Betfair. Australia, Japan, France, and Dubai wait on a
   feed and a license. The recommendation is UK/Ireland/Hong Kong first if
   the Racing API terms in question 3 are acceptable, because the core
   entitlement is actually for sale and the card, the odds, and the results
   are one API. US first if the priority is North American racing and HDW's
   license covers publishing.
3. **Licenses, in writing, before any file is stored or any pick is posted.**
   - HDW / JCapper and TrackMaster: does a personal data plan allow storing
     the files in our database and publishing model picks to a paid app?
   - The Racing API: the FAQ allows betting models; the terms forbid use by
     a betting operator or a sportsbook. Does the paid app fall on the
     allowed side?
   - Equibase 2023: read the clickwrap. If it matches what DRF reported, that
     year stays off the published model.
   - Krok §6.1: EV analytics offered to the public or for a fee is outside
     the A$49 grant. Australia in the app needs a commercial license or it
     stays out.
4. **Price floor.** The repo default is −200. Confirm that a racing
   favourite shorter than that is not bet, unless you want a different floor
   on the `Updated-By` commit.
5. **Channels.** Create `#racing` and `#racing-intl`, plus the two live
   channels, and set the four variables. One ask, when phase 3 is real.
6. **Exchange account.** Historical files can be downloaded by hand and
   ingested with no login code. Say if a Betfair session in the worker is
   ever wanted. It is not part of this plan.

## What was deliberately not designed

Bet placement, ADW logins, sportsbook logins, harness, quarter horses,
Arabians, greyhounds, exotics, each-way, and show. A model that clears is
live. Its graded bets are the units, and the win-loss record is that same set.

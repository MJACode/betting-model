# The market grid, and every route to a price

Step 1 and step 2 of `SKILL.md`. The grid is the first deliverable of a league
build and stays the league's index for as long as we bet it.

## The template

It lives in `docs/sports/<league>.md` under "The market grid". Every row fills
every column, and a row is updated in place as it resolves.

```
| Market | Settles on | Inputs held | Prices (source, books, seasons, pulls a day) | Baseline | Method tried | Result | Status |
```

- **Settles on** names the column, and how the books grade it: overtime in or
  out, regulation only, which period, what voids, how a push is settled.
- **Prices** names the depth, not just the existence: "DraftKings' whole path
  2026, every other book's opener and close only" is a different research
  problem from "13 books, two pulls a day, 2023-2025".
- **Result** is units on bets at real prices with an interval, or the reason
  there is none.
- **Status** is one of: **live** (model id, date), **built, waits for merge**,
  **nothing clears** (link to the table), **parked** (the reason, and what
  would unpark it), **to do**.

Two finished grids to copy the shape from: `docs/sports/ncaabw.md` ("The
market grid", a new league built in two days) and `docs/ncaaf_market_audit.md`
§1 (an audit of a league with years of models).

## The market families — one row each, at least

Ask the feed which of these it actually serves for this league before
deciding a row is empty (the probe below). Leagues differ more than they look:
the women's college game had no period, team-total or prop market in the feed
at all, while the men's had first halves and in-play prices.

| Family | Rows to list | Notes from this repo |
|---|---|---|
| Full game | moneyline; spread (run line, puck line); total | Check overtime. Hockey and soccer also have the regulation 3-way market, a separate price. |
| Periods | first half, second half, quarters, periods, first five innings, first inning, rounds | A period score must be stored and checked before any period market can be graded. Half-time scores rebuilt from play-by-play need two reads that agree. |
| Team totals | full game and by period | Often priced off the full-game line, which makes them a derivative (see `methods.md`). |
| Alternates | alternate spreads and totals, prop ladders | Usually shallow history. A one-sided ladder needs a margin model that varies with the strike. |
| In play | moneyline, spread, total, between-period markets (halftime) | Needs its own price log from day one and its own score feed; check the feed's lag against the book. |
| Player props | every market key the feed serves, grouped by shape: counts and yards (two-way), binary (anytime scorer: one-way), extreme value (longest), rare events | One-way markets cannot be de-vigged: parked unless a two-way reference exists. Whole-number lines push. |
| Fight or match | winner, method of victory, rounds, goes the distance | |
| Prediction markets | Kalshi game contracts (recorded hourly since 2026-09-10) | A second price, not a book a pick can name. |
| Futures, series | | Usually parked: one price a day, settles months later. |

## Prices: the routes, in the order to try them

Write in the grid what each route returned. "We have no lines" is sayable only
after all of them (CLAUDE.md §1b).

1. **What is stored.** `odds` (game lines, every pull), `player_prop_odds`,
   the in-play price logs, Kalshi. Read research volumes off the local mirror
   (`docs/local_ops.md`): `odds` filtered to one league reads in under a minute
   there and costs production nothing. An odds `game_id` often has no score
   (night games, backfill-minted twins): match to the scored row on both team
   names within a day, and de-duplicate the same pull stored twice on
   (game, pull time, book).
2. **What the odds feed sells.** The event list costs nothing. One historical
   call shows how far back the sport key goes and what it costs; history bills
   about ten times the live endpoint, so measure `x-requests-last` on the
   endpoint you will actually use before quoting a cost. The feed keeps no
   snapshot while nothing moves, and asking for a time it has none at is billed
   for the one before: walk its own `next_timestamp` chain.
   **Which markets it serves:** `python -m scripts.probe_market_coverage
   --sport <SPORT> [--markets <key>]` asks one market per call against a live
   event. Stored data cannot tell apart "the key is unsupported", "supported
   but no book prices it" and "served, but we never asked" — all three are an
   empty table (`docs/market_coverage.md`). **A market key the feed refuses
   (HTTP 422) is a market the feed does not carry, not one no book prices.**
   UFC's method, distance and round markets were refused by the feed and
   priced on DraftKings' own board (route 4).
3. **Free archives.** ESPN's core API odds (one provider a game, opening and
   closing numbers, coverage varies by season), closing lines in a stats API
   (the college football stats API carries closes), sportsdataverse season
   files, a prediction market's history. Kalshi and Polymarket keep free
   hourly price history by market (Kalshi with bid and ask): the NBL's game
   markets from 2025-12-04 on Kalshi, liquid (median 126,016 contracts a team
   market in 2025-26), and from 2026-01-09 on Polymarket (2026-11-14). Not a
   book a pick may name; a second price, and a reference where no sharp
   book is in the feed.
   Also the **free public archives** a sport's own community keeps.
   UFC has two (2026-11-13): fight-canon-db (GitHub releases, MIT;
   BestFightOdds open and closing range, 2007+) and the Ultimate UFC
   Dataset (CC BY 4.0; a near-close fight price and method prices by
   fighter, 2012+). Store one in Supabase like a bought one, keyed on
   `source`, before the first table is read from it
   (`data/ingestors/ufc_price_archive.py`).
4. **Each book's own board, and the sport's odds-comparison sites.** Two
   checks, both before any row parks for price:
   - **The book's own board, sub-page by sub-page.** A book prices far more
     than the feed resells. DraftKings' board answers from mike's PC and
     refuses the Railway worker. `data/ingestors/dk_live_board.py` holds the
     client, the board address and the league ids. The board lists its
     categories and sub-pages; read the ones the grid row needs.
   - **Odds-comparison sites that keep each book's history.** BestFightOdds
     keeps the US books' MMA prop prices, with their history, from mid-2021
     (`docs/ufc_market_audit.md`). Read the site's robots.txt first.
     `references/scouting.md` records which sites answered and how. Such a
     page shows each book's last change, not its price at a time: grade at
     it, then re-grade the bets a rule picks at the price its history shows
     for the decision time (`kill-tests.md`, "Is the data right?").
     `data/ingestors/ufc_prop_history.py` is the template: the pages one
     request each, the histories only for the props a test points at.
   Store what is read in Supabase the same run, as for any archive.
5. **Paid providers** other than the feed: `docs/odds_sources.md` prices them.
   More thin books add rejections, not edge; the case for a new provider is a
   book or market we cannot get (a sharp prop book, for example).
6. **The prior season's close**, as a last resort for a baseline.

**Finding a key's windows for a few credits.** When a sport key is only
active part of the year (tennis: one key per tournament), three history event
lists (1 credit each) find a year's window: ask at the end of the year (the
feed answers with the key's last snapshot), then 40 days before that last
snapshot (its `next_timestamp` is the window's first listing, because the
pointer is per key), then at that first listing. When the snapshot before a
window is in the same year, repeat from it: a key can hold two windows a
year. The whole tennis sweep cost 337 credits for 129 windows
(`data/ingestors/tennis_odds_history.sweep_key_year`, 2026-11-13).

**Period, team-total and alternate history** on the feed comes only from the
per-event endpoint, one call per game per time, billed 10 credits per market a book
actually returns (an empty answer is free). How far back it goes differs by
league: EuroLeague's answers from 2023 (HTTP 422 on a 2022-12 game), with
DraftKings in none of it (`docs/sports/euroleague.md`). Ask every market key
the league has ever shown: one no book holds costs nothing.

**When a game moment happened on the wall clock** (halftime, a quarter's
end) is what an in-play model needs against timestamped prices. Play-by-play
often carries only the game clock; look for a feed that stamps events in UTC.
EuroLeague's shot chart (`live.euroleague.net/api/Points`) does: every shot
carries `UTC`, so the last shot of the second quarter and the first of the
third bracket halftime (`data/ingestors/euroleague_shots.py`).

**Price a purchase on days with and without games.** A day with no game
can still hold a snapshot every five minutes: the NBL's cost 3,090 credits
against 3,930 and 4,380 for one- and two-game days at the same cadence
(2026-11-14), so a plan that counts only game days is a third short.

**Buying history.** Plan the credit budget from measured numbers
(`data/ingestors/odds_quota.plan_credit_budget`, which refuses when it cannot
measure), store each pull in Supabase in the same run with a `source` marker
and a fetch ledger, resume by skipping stored work, mirror it, and verify both
copies by row count. Measured purchases have come in well under and well over
plan (a season of in-play snapshots cost 8,360 credits against 373,240 planned
because most were already stored; an alternates backfill cost about 514,000
against about 291,000), so report the spend as measured afterwards too.

**Start the forward log on day one.** Every row that has no history gets its
prices stored from now on, at the times the model would decide, so the next
season can be researched.

## Which book's price counts

- **Fetched** is `LINE_SHOP_BOOKMAKERS`. **Decidable** — a book a pick may
  name — is `BEST_LINE_BOOKMAKERS`. Pinnacle is the sharp reference, never a
  place to bet; Bovada is offshore; betPARX is fetched and never named
  (`CLAUDE.md` §6, `docs/best_line.md`). A backtest that shops across a book
  the live path cannot name is measuring fiction: over half of an early "better
  price" claim pointed at a book a bettor here could not use.
- DraftKings stays the reference for features. A prop DraftKings does not list
  is scored off the first decidable book that does, and those picks are a new
  population, reported separately.
- **Exchanges are excluded** from any shopping in a backtest.
- **Grade at the quoted price.** Props in particular carry heavy margin; a rule
  that wins at -110 and is quoted -130 loses.
- Some leagues have no sharp book at all (the women's college game: no
  Pinnacle). Then closing-line value is measured against the nearest thing,
  and the doc says so.
- **Count the anchor book's coverage before comparing two leagues.**
  DraftKings posted a total on 69 of 701 women's college games (2026-11-03 to
  11-15) against 519 of 681 men's, and its own board agreed (at most 3 women's
  games in play at once), so a DraftKings-only model sees one game in ten.
  Pricing the same model at other books' first totals did not clear
  (`methods.md` §1, `docs/sports/ncaabw.md`).

**Racing's free price routes** (2026-11-15, `docs/sports/racing.md`):
Betfair Australia publishes the ANZ thoroughbred markets free, with no login,
as annual zips and monthly CSVs (`betfair-datascientists.github.io/data/
dataListing/`): one snapshot at the scheduled start, BSP, traded prices to
the off, results; 132,750 races 2020-01 to 2026-10. Kaggle serves public
datasets with an unauthenticated GET
(`kaggle.com/api/v1/datasets/download/{owner}/{slug}`); Hong Kong's final
pools 1997–2005 and 2014–2017 and UK/Ireland starting prices 1988–2026 are
there. GitHub's raw file host serves nch015's Hong Kong set (2016–2018):
the win and place pools every 12 minutes, then every 6 inside about 216
minutes, to about 5.6 minutes before the start; the only free path before
the off found so far. `scripts/horse/fetch_datasets.py` and `store_files.py`
fetch and store all of them (the UK zip in 34 parts of 32 MiB), and the
worker stores each new Betfair month daily (`scripts/horse/betfair_monthly.py`). Racing is
not on the odds feed.

## Sport shapes — starting hypotheses, not facts

When a league is new, the closest shape below suggests what to test first.
Each line is a hypothesis to grade on the league's own prices; none is a
reason to skip a market. A league that fits none of them is a new shape:
define it here when it is built.

- **High-scoring, possession by possession (basketball).** Margins and totals
  are close to continuous, so one empirical margin and total table prices every
  spread, total and moneyline. Here the edges came from the first posted
  total, line shopping, first halves priced off the full game, shooting luck,
  halftime and in-play state, and prop unders against a sharp book; no
  pre-game full-game spread or moneyline has passed in any pro basketball
  search. Women's and men's games differ in periods and overtime.
  **A league with one book a pick may name** (the NBL, 2026-11-14,
  `docs/sports/nbl.md`): BetRivers alone prices it among the US books on the
  feed, full game only, and the sharp book enters the history late (Pinnacle
  from 2026-27), so two seasons measure value against the exchange and the
  local books' consensus. Every derivative row then waits on the book's own
  board (route 4) before it can park.
- **Low-scoring, goal by goal (hockey, soccer).** Count models price the full
  game, the regulation 3-way and the periods together; the starting goalie (or
  keeper) is a gate, priced only after it is confirmed; overtime decides which
  markets a draw settles. In hockey the margin sat on both sides of the total
  and on the over of count props, and the moneyline worked anchored on the
  market.
- **Down and distance (football).** Key numbers on spreads; weather on totals
  (it worked in the pro game, and not in college, where the market already
  moves its total with wind); rest is known weeks ahead; in-play lines are
  re-hung off the pregame number and the clock. Stat-projection props found
  nothing the line lacked; a sharp-reference prop rule did.
- **Starter-dominated (baseball).** The starting pitcher is a gate; first-five
  markets isolate the starters; weather and park move totals; the stored team
  and pitcher stats leaked season-final numbers until rebuilt.
- **One against one (fighting, tennis, golf).** Ratings per competitor; thin
  history per competitor. In UFC the close is efficient, the first posted
  price is not, and duration and method props are priced with heavy margin
  (method: free near-close history 2012+, every blind bet negative; round
  totals: no free history, the feed's from 2021). The odds feed's MMA key
  serves fight winner, round totals, a points spread and Pinnacle's
  alternate totals; it rejects every method, distance and round key
  (`docs/ufc_market_audit.md` §2).
  **Tennis** (`docs/sports/tennis.md`, 2026-11-13): the feed sells it as one
  key per tournament (53 keys, top tiers only, each active only while its
  event runs), so the key list is read from `/v4/sports?all=true` and a key's
  history is a set of yearly windows; most keys enter the feed in 2024 or
  later (the Grand Slams from 2020). The match winner is at every book;
  games spread and total games only at a few (not DraftKings). A free archive
  of results with serve and return counts exists for both tours, and a rating
  model is easy to build and trails the market (Elo's Brier about 0.215
  against Pinnacle's 0.196 in the published comparison). Settlement differs by
  book on a retirement: grade each book at its own rule.
- **A field, priced by a pool or an exchange (horse racing).**
  (`docs/sports/racing.md`, 2026-11-15.) Five to sixteen runners, one
  winner, dead heats in about 0.3–0.4% of races (they split the stake), and
  win, place, show, each-way and exotic markets on one race. **The price
  differs in kind:** a pool pays the final odds, which nobody sees when
  deciding, after 15–18% is taken; an exchange (Betfair) sells a back price
  or BSP, net of 5–10% commission on a win; fixed odds exist only at a few
  books. Grade a pool bet at the final odds and never decide on them. For a
  US bettor almost every price is a pool (no US exchange since 2020; fixed
  odds only in New Jersey and Colorado), so an exchange is a reference, not
  a book. One bet per race per model (two win bets cannot both win). Every
  free price is a close or one snapshot at the scheduled start, and on those
  the pools and the exchange are calibrated, the place markets price
  Harville's bias, and fundamentals added nothing to Hong Kong's final pool.
  Start a new racing jurisdiction from a pre-off price path, not a model.

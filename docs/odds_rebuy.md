# Buying back the line-shop history the cleanup removed (#1384)

mike, 2026-11-15: *"we might as well do all of it from odds api"*, and *"Yes,
build it"*. From 2026-08-15 to 2026-11-14 `data/prune_odds.py` cut every book
except DraftKings (and, for props, Pinnacle) to an opener and a close, for games
more than two days old. `data/ingestors/odds_rebuy.py` buys the middle back
from The Odds API historical endpoints. The Supabase backup restore was
considered and not used.

## How it decides what to buy

- **Which games:** those whose other books hold at most 3 rows per line while
  DraftKings holds more. Measured on the PC copy, these are the games the
  cleanup thinned.
- **When:** the moments the all-books refresh ran (`pipeline_runs`, kinds
  `hourly` and `evening`), rounded up to the API's 5-minute snapshots. It
  does not buy at DraftKings' own capture times: most of those come from
  DraftKings-only pollers. NFL 2026-10 has 25,270 DraftKings timestamps, and
  only 29 of them are shared with another book. Before 2026-08-27, where the
  run log starts, it buys one snapshot an hour.
- **What:** only that game's stored books and markets, strictly between the
  other books' stored opener and close, and before the start.
- **Only moves:** a book's row is kept only where its price or line changed
  since its previous known price. On the first test day, 978 of 1,051 bought
  game-odds rows for one game repeated the row before.
- **The plan runs on the PC copy** (`betting.duckdb`), with no load on Supabase.
  The rows are written to Supabase.

## What a bought row looks like

- **Game odds:** `source = 'odds_api_rebuy'`, protected by name in
  `prune_odds.PROTECTED_SOURCES`.
- **Props:** the table has no source column. The ledger
  `odds_rebuy_requests` records each request's served snapshot, its games,
  books and markets, its credits, the rows it wrote, and how many of the
  bought DraftKings prices matched the stored ones.
- No betslip links or selection ids are requested.
- No `games` row is written.
- A re-run skips every request already in the ledger.

## Tested 2026-11-15/16 (4,552 credits)

The 4,552 credits: 90 on three comparison fetches, 1,650 on game odds and
2,812 on props (the ledger's `credits`, from `x-requests-last`).

- **Against a moment still held in full** (NBA, 2026-11-12 23:20:36 UTC; 30
  credits, so 10 books = 1 region): 107 of 137 book prices matched the stored
  price in force exactly. BetRivers, betPARX, Bovada and Hard Rock matched
  12-18 of 12-18. FanDuel matched 8 of 18 and Pinnacle 1 of 12. Each mismatch
  read was a book that moved within about a minute of the snapshot.
- **On thinned games, written to Supabase** (NHL game odds for 2026-10-14,
  plus every prop moment of NHL_2026-10-23_TBL_COL):
  - game odds: 55 requests, 1,650 credits, 12,934 rows, DraftKings 1,549 of
    1,599 matched;
  - props: 34 requests, 2,812 credits, 4,016 rows, DraftKings 184 of 212
    matched.
  - The latest-line rows and each book's newest pre-game row were unchanged.
  - A re-run bought nothing.
  - The game-odds rows of that day were bought before the only-moves rule
    existed, so about 93% of them repeat the row before. They stay; no data
    is deleted.
- **Row size:** bought rows average 168 bytes (odds) and 212 bytes (props) in
  the table, against 320 and 342 for live rows, because they carry no links.

## The whole plan, 2026-03-01 to 2026-11-13, measured 2026-11-16

| | Requests | Credits |
|---|---|---|
| Game odds: MLB, NHL, NFL, NCAAF, WNBA, UFC | 22,385 | 623,210 |
| Props: NBA 1,958,052; MLB 274,810; NHL 271,152; NCAAF 84,854; WNBA 67,369 | 16,485 | 2,656,237 |
| **Total** | **38,870** | **3,279,447** |

NBA, NCAAB, NCAABW and EuroLeague game odds, and NFL props, have no thinned
game in the window.

A projection from the test's rows per credit, using the only-moves rule:
about 0.3M game-odds rows and 3.8M prop rows, about 1.5 GB with indexes. It
comes from one NHL day and one NHL game, so NBA props may differ.

## Running it

It runs on mike's PC, which holds the copy and the key:

```bat
python -m data.ingestors.odds_rebuy plan --kind prop --sport NBA
python -m data.ingestors.odds_rebuy buy  --kind prop --sport NBA
python -m data.ingestors.odds_rebuy compare --sport NBA --at 2026-11-12T23:25:00Z
```

- `buy` takes its ceiling from the plan's own credit total
  (`odds_quota.plan_credit_budget`). It refuses to start when the run would
  leave less than 7 days of the measured median burn.
- It needs mike's yes on the number before it spends.

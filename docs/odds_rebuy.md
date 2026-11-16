# Buying back the line-shop history the cleanup removed (#1384)

mike, 2026-11-15: *"we might as well do all of it from odds api"*, and *"Yes,
build it"*. On 2026-11-16, to the pieces the first plan left out: *"Yes, add
them"*.

From 2026-08-15 to 2026-11-14, `data/prune_odds.py` cut every book except
DraftKings (and, for props, Pinnacle) down to an opener and a close, for games
more than two days old. Its first runs reached back to March.
`data/ingestors/odds_rebuy.py` buys the rest back from The Odds API historical
endpoints. The Supabase backup restore was considered and not used.

## What it buys: four kinds

| Kind | What | How it is asked for |
|---|---|---|
| `game` | Moneyline, spread and total before the start | One bulk request per refresh moment, covering every thinned game of the sport |
| `extra` | Markets the bulk feed never returns: MLB first five innings, NHL 3-way regulation, alternate spreads and totals, UFC round totals | One request per game per refresh moment |
| `inplay` | Moneyline, spread and total while the game was on | One bulk request every 5 minutes, from the start to DraftKings' last in-play row |
| `prop` | Player props before the start | One request per game per refresh moment |

- **Why in-play is a refill.** Once a game started, the refresh passes kept
  fetching every book, because the bulk feed keeps serving a game under way.
  Outside the NBA, those prices were saved with the pre-game label. The
  cleanup kept each book's opener and its pre-game close only, so every one of
  those rows went. A bought in-play row is labelled `in_play`, the label the
  older history purchases use.
- **Every 5 minutes** is the finest the feed's history keeps. The live loops
  had recorded every few seconds; that detail cannot come back.
- **NHL 3-way** is asked under the feed's key `h2h_3_way` and stored as
  `h2h_3way`, the name the models read.
- **A ladder of alternate lines** keeps every rung as its own line. Alternate
  lines were first collected on 2026-10-29, two ways: once a day under their
  own protected source, which the cleanup never touched, and on every refresh
  pass with no source tag, which the cleanup cut to two or three rungs per
  book.

## How it decides

- **Which games:** those whose other books hold at most 3 rows per line while
  DraftKings holds more, measured on the PC copy. For extra markets the rule is
  read per market, and a market DraftKings never posted (MLB first-five spreads
  and totals) counts. For in-play: DraftKings was followed through the game
  and the other books hold at most 3 rows per line after the start. Props cut
  part-way count too: more than 3 rows per line but at most 6, and under half
  of DraftKings'. That rule added 54 NCAAF games and nothing in any other sport.
- **When, before the start:** the moments the all-books refresh ran
  (`pipeline_runs`, kinds `hourly` and `evening`), rounded up to the feed's
  5-minute snapshots. Not DraftKings' own capture times: most of those come
  from DraftKings-only pollers. NFL 2026-10 has 25,270 DraftKings timestamps,
  29 of them shared with another book. Before 2026-08-27, where the run log
  starts, one snapshot an hour.
- **What:** only that game's stored books and markets, strictly between the
  other books' stored opener and close.
- **Only moves:** a book's row is kept only where its price or line changed
  since its previous known price. On the first test day, 978 of 1,051 bought
  game-odds rows for one game repeated the row before.
- **Game ids come from the schedule** for the sports whose schedule owns them
  (`odds_ingestor.SCHEDULE_RESOLVED_SPORTS`), the way the live pass does it. An
  NFL id is `NFL_<season>_<week>_<away>_<home>`. Without the schedule every NFL
  row would have been filed under an id no game has, and dropped after it was
  paid for. A request whose schedule cannot be read is refused before it is
  bought.
- **The plan runs on the PC copy** (`betting.duckdb`), with no load on Supabase.
  The rows are written to Supabase.

## What a bought row looks like

- **Game odds** (all three game kinds): `source = 'odds_api_rebuy'`, protected
  by name in `prune_odds.PROTECTED_SOURCES`.
- **Props:** the table has no source column. The ledger
  `odds_rebuy_requests` records each request's kind, served snapshot, games,
  books, markets, credits, rows written, and how many bought DraftKings prices
  matched the stored ones.
- No betslip links or selection ids. No `games` row is written.
- A re-run skips every request already in the ledger.

## Tested on production data

**2026-11-15/16, 4,552 credits** (game odds and props):

- **Against a moment still held in full** (NBA, 2026-11-12 23:20:36 UTC; 30
  credits, so 10 books bill as 1 region): 107 of 137 book prices matched the
  stored price in force. BetRivers, betPARX, Bovada and Hard Rock matched every
  price; FanDuel 8 of 18, Pinnacle 1 of 12. Each mismatch read was a book that
  moved within about a minute of the snapshot.
- **NHL game odds for 2026-10-14 and every prop moment of
  NHL_2026-10-23_TBL_COL:** 89 requests, 16,950 rows, DraftKings 1,733 of
  1,811 matched. A re-run bought nothing. That day's game-odds rows were bought
  before the only-moves rule, so about 93% repeat the row before; they stay.
- **Row size:** 168 bytes (odds) and 212 bytes (props) per bought row, against
  320 and 342 for live rows, because they carry no links.

**2026-11-16, 1,192 credits** (the four kinds, a few requests each; 30
credits on one NFL snapshot read raw to explain its zero rows; 60 on the
end-of-game check below):

| Piece | Requests | Credits | Rows | DraftKings matched |
|---|---|---|---|---|
| MLB first five innings | 4 | 121 | 6 | 2 of 3 |
| NHL 3-way and alternates, a day out | 6 | 66 | 0 | — |
| NHL 3-way and alternates, the last hour | 4 | 121 | 69 | 3 of 4 |
| NCAAF alternate lines | 4 | 82 | 965 | — |
| NFL alternate lines | 5 | 101 | 978 | — |
| UFC round totals | 4 | 41 | 1 | 2 of 3 |
| MLB in-play | 8 | 240 | 174 | 15 of 21 |
| NCAAF in-play | 6 | 120 | 70 | 10 of 10 |
| NFL in-play | 6 | 60 | 41 | — |
| NFL game odds, nine days out | 5 | 150 | 0 | 15 of 15 |

- Every stored row has its game. Ladders keep their rungs: the NFL game's
  alternate lines came to 978 rows from 5 requests across 7 books. In-play
  rows are labelled `in_play` and stamped after the start.
- The newest-line table (`latest_odds`) for these games was the same before
  and after: 2,599 rows, same hash.
- **The end of a game is safe too.** The last two in-play snapshots of
  MLB_2026-10-27_MIL_TB (60 credits, 42 rows) became the game's newest
  other-book rows (04:20:15 UTC), and `latest_odds` still held the same 47
  rows with the same hash. The live trigger skips in-play rows
  (`latest_odds_on_insert`, read from the database 2026-11-16).
- **The two pieces with zero rows, read back:**
  - NFL nine days out: FanDuel was the only other book listing the game, and
    its prices (-120/+102, -1.5 at -108/-112, 45.5 at -105/-115) equal its
    stored opener from 21:17:27, so nothing moved.
  - NHL a day out: the feed served its 17:15:36 snapshot, and the first other
    book posted the 3-way at 17:16:27 (Fanatics). No other book was up yet;
    the 11 credits are the event list plus one market.
  - So each game's first request can land just before the other books'
    opener and store nothing. The plan still asks for it.
- The in-play DraftKings mismatches (6 of 21 in MLB) were not read one by one.

## The whole plan, games 2026-03-01 to 2026-11-13, measured 2026-11-16

| Kind | Credits | By sport |
|---|---|---|
| Game odds | 583,570 | MLB 126,420; NHL 141,330; NFL 93,570; NCAAF 108,900; WNBA 69,360; UFC 43,990 |
| Extra markets | 1,078,926 | MLB 223,125; NHL 338,533; NFL 60,730; NCAAF 169,795; WNBA 1,081; UFC 285,662 |
| In-play | 347,320 | MLB 257,670; NCAAF 70,870; NFL 18,780 |
| Props | 2,693,801 | NBA 1,958,052; MLB 274,810; NHL 271,152; NCAAF 122,418; WNBA 67,369 |
| **Total** | **4,703,617** | |

- Nothing is planned for NBA, NCAAB, NCAABW or EuroLeague game odds, extra
  markets or in-play, or for NFL props: the cleanup kept their full history.
- The total counts the test requests too; a run skips them.
- **The total is a ceiling.** It counts every requested market at 10 credits,
  and the feed bills only the markets it returns: the NHL request a day out
  billed 11 where the plan counted 31.

## Running it

It runs on mike's PC, which holds the copy and the key. The plan window
defaults to games from 2026-03-01 to 2026-11-13.

```bat
python -m data.ingestors.odds_rebuy plan --kind extra --sport NHL
python -m data.ingestors.odds_rebuy buy  --kind inplay --sport MLB
python -m data.ingestors.odds_rebuy compare --sport NBA --at 2026-11-12T23:25:00Z
```

- `buy` takes its ceiling from the plan's own credit total
  (`odds_quota.plan_credit_budget`). It refuses to start when the run would
  leave less than 7 days of the measured median burn.
- It needs mike's yes on the number before it spends.

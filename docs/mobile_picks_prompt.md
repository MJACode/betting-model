# Open picks in any Claude chat

**Ask any Claude chat that has the Supabase connector "what are my open
picks?"** Claude reads one view, `public.open_picks`, in project
`vvprgnrmzeekokzkrkfu`:

```sql
SELECT * FROM open_picks;
```

Nothing is pasted anywhere and no claude.ai project is needed (mike,
2026-11-04: *"no pasting anywhere, ever"*). The logic lives in the database, so
it changes in a reviewed migration and every chat reads the new version the
moment it lands.

## What a row is

One open pre-game bet, as the app, Discord and push show it (CLAUDE.md §1b),
ordered by start time.

| Column | What it holds |
|---|---|
| `sport` | MLB, NBA, NHL, NFL, NCAAF, NCAAB, WNBA, UFC |
| `game_date` | the game's date in Eastern time |
| `start_time_et` | the start, e.g. `7:40 PM ET` (empty if the start is unknown) |
| `matchup` | `AWAY @ HOME` (UFC: `A vs B`) |
| `pick` | the pick's label as stored. Quote it word for word and never rebuild the line (CLAUDE.md §00). Older NFL wind and opener labels end in a sizing figure (`· 0.87u`) that is not the stake; the view leaves that figure off, so `stake` is the only unit number on a row |
| `price` | the American price the pick was decided at |
| `book` | the book that price came from |
| `stake` | the published stake in units, e.g. `1.15u to win 1u`: 1 unit to win at that price, never more than 3 units laid, a bare `1u` when there is no price. The same text Discord posts |
| `risk_units`, `to_win_units` | the same stake as two numbers |
| `model` | the model's name as the app shows it |
| `decided_at_et` | when the pick was decided, in Eastern time |
| `pick_id`, `model_id` | for looking a pick up in `picks` |

Every stake and result is in units, never dollars (CLAUDE.md §4). For a record
("how did yesterday go?"), read units and risked from `v_public_track_record`
(per model) or `v_public_track_record_daily` (per day), the record Discord and
the app publish. Never quote `profit_flat` as money: it is stored per 100
staked, so `profit_flat / 100.0` is units at one unit risked, and it is invented
at -110 on a pick with no price.

Zero rows is a valid answer: no open bets right now.

## Which picks are in it

- A `BET`, not graded, pre-game (no in-play picks), for a game that has not
  started. No date horizon: a pick written days ahead is open now.
- Not VOID, not the second copy of one bet (`DUPLICATE`), not written while its
  model was paused, and its model is not paused now.
- **Discord has posted it.** The app, Discord and push show the same picks,
  and the app shows a bet once the channel has it. Discord posts a bet only
  after it clears its model's own cut in `model_action_thresholds` (the table
  `data.threshold_sync` writes from `config.py`) at the price it was decided
  at. A posted bet stays in even if that cut has moved since, the same rule as
  the app's action filter (mike, 2026-10-15 and 10-16).

### Where it can differ from the app, and why

- **A VOID that Discord posted.** The app keeps it on the board until its void
  notice posts. This view leaves every VOID out.
- **A game in progress.** The app's Today board keeps a bet until the game
  ends. This view drops it at the start, as the Discord producer does.
- **A pick further ahead than the app's board looks** (same day for MLB, NBA
  and WNBA; 7 days for UFC, NHL and NCAAB; 11 for NFL; 150 for NCAAF). The view
  has no horizon, like Discord.

Measured on 2026-11-04 at 6:06 PM ET: 23 rows (NBA 6, NFL 5, NHL 5, NCAAF 4,
NCAAB 3), the same 23 picks the app's filter selects, with none on one side
only. No bet that cleared its cut was waiting to be posted.

## Changing it

Edit `data/migrations/open_picks_view_2026_11_04.sql`. The migration skips once
the view's comment matches a hash of its body, so a changed body needs the new
hash in both places; `tests/test_open_picks_view.py` fails with the value to
use. Columns can only be added at the end. The worker applies it on its next
pass (`data.view_migrations`).

## History

Until 2026-11-04 this page held a long prompt and query to paste into a
claude.ai "Betting" project. Matt set one up once; mike has none, and was
wrongly told to paste into it. The copy also went stale whenever the query
changed. The query is now the `open_picks` view.

## Background kept from the old page

**The thresholds table mirrors both pause registers**: `config.PAUSED_MODELS`
(a person's call) and leftover `model_auto_pauses` rows. The 250-bet review no
longer writes that table (mike, 2026-09-14: nothing autopauses).

**DK / multi-book F5 odds coverage (re-measured 2026-09-15):**
- `h2h_1st_5_innings` (F5 ML): DraftKings **does** carry this. The scorer uses
  real DK odds (then the best-line re-check) and skips if there is no real price.
- `totals_1st_5_innings` (F5 O/U): DraftKings' Odds API feed returns **zero**
  rows. FanDuel / BetMGM / William Hill do, and the scorer takes the first
  bettable book in `BEST_LINE_BOOKMAKERS` order. **BET paused** until the
  2026-05-08 leak-era artifacts are retrained on real F5 prices.
- `spreads_1st_5_innings` (F5 RL): same as F5 O/U.

The pipeline schedule (6am ET daily run, hourly and evening refresh passes) is
in `docs/cloud_worker.md`.

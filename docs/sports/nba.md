# NBA — models, data, pipeline

> **Rebuilt 2026-10-15/16 (mike: "build new nba models, remove any previous nba
> models").** The twelve 2026-06-19 models are retired; two prop models replace
> them, and a totals model joined on 2026-10-17 (`nba_total_luck`).
> Every market was graded at real prices against bars written before the first
> grid ran: **`docs/nba_models_2026.md`** (the bars, the market grid, every
> result and what failed). Thresholds: `docs/thresholds.md`, NBA section.

## The models

| Model | What it bets | Status |
|---|---|---|
| `nba_prop_projection` | Steals (over or under), rebounds (under), blocks+steals (over or under), blocks (under), rebounds+assists (under), threes (over or under): each player's projected count — minutes × per-minute rate, a negative-binomial width, a per-market calibration map — priced at the consensus main line, every proposition whose calibrated EV at the best bettable price clears its market's floor. Decided once, in the same 45-57 minute window, after `nba_prop_market`; never a proposition it holds. | **LIVE** (artifact — `models/nba_prop_projection.py`, card `scripts/nba_prop_projection_card.py`, steps `nba-prop-project` / `nba-prop-projection`) |
| `nba_total_luck` | The full-game OVER, when the projected total with the opponents' three-point and free-throw shooting luck taken out is at least 3 points above the plain projected total. At the best bettable price under the market's fair line; each game decided once, on a fetch 60-66 minutes before tip made by its own one-minute job; regular-season games only (the NBA Cup final never counts); both teams need 10 games, so the first bets come in mid-November. | **LIVE** (rule with a parameter artifact — `models/nba_total_luck.py`, card `scripts/nba_total_luck_card.py`, step `nba-total-luck`, job `nba_total_luck_window`) |
| `nba_prop_market` | The UNDER on points, rebounds, assists, threes or PRA, at the best bettable book whose line equals Pinnacle's in the same fetch, when Pinnacle's no-vig under makes that price +EV. Each game decided once, 45-57 minutes before tip; every qualifying proposition, no game or night cap. | **LIVE** (rule — `models/nba_prop_market.py`, card `scripts/nba_prop_market_card.py`, step `nba-prop-market`) |

Graded on 2023-24 → 2025-26, the population it bets (every qualifying
proposition, −200 floor, no double/triple-double): 24,572 bets, +781.3 units,
+2.96%, 90% CI +1.85..+4.05, positive every season (+393.6 / +220.5 / +167.1
units) — about +260 units a season and about 50 bets a night. mike, 2026-10-16:
*"maximize units won"*, so the one-a-game, four-a-night caps it shipped with on
10-15 (+94.9 units over the same seasons) are gone. Expect about +2% per bet
live. It only ever bets unders because that is where the books' margin sits in
every sport this repo has measured: blind NBA overs lose 7.3%, blind unders 2.2%
(505,932 propositions).

**Prices it lays:** the −200 floor; on the graded bet list, min −200, 5th
percentile −143, median −105, 95th +128, max +230. 38% of bets are plus money;
3.5% are −150 or shorter.

**`nba_prop_projection`** (2026-10-16, mike: *"build the projection model"*,
*"maximize units won"*; the evidence is `docs/nba_models_2026.md` §5). Graded
2023-24 → 2025-26, every qualifying proposition, −200 floor: at the five books the
2026-27 feed returns, 66,588 bets, +2,392.8 units, +3.60%, 90% CI +2.93..+4.32,
positive every season (+1,125.2 / +433.3 / +834.4) — about 130 bets on the median
night (362 at most); at all eight bettable books +4.12%; at DraftKings alone +2.46%.
Expect less live: the best cell of a 546-cell search runs high, and most of the edge
is the best price (+1.45% at the second-best book). **Prices it lays:** min −200, 5th
percentile −166, median +108, 95th +170, max +3000; 64% plus money; the +1,600..+3,000
tail is threes overs at 0.5 quoted by one book. **The probability it shows is an upper
bound**: in the band it bets it claimed 0.533 and won 0.501. Assists overs, which the
search chose, are not bet (they failed on 2025-26 and lose at the feed's books).

**`nba_total_luck`** (2026-10-17, mike: *"Find it ... edge like we have with
other sports"*; the evidence is `docs/nba_models_2026.md` 6.6 and 6.7, the
settings `docs/thresholds.md`). Graded walk-forward at bought prices,
2021-22 → 2025-26 pooled: 508 bets, +55.6 units, +10.1%, 95% interval
+2.0..+18.3, every season positive (2020-21, never chosen on, lost 10.4% on
103). About 100 bets a season. **Prices it lays:** -115 to +100, median -110.
The probability it writes is the market's fair chance of the over plus the
+0.0659 this bucket has won above it on those five seasons. The live code
reproduces every one of the lab's 611 bets on the research cache
(`tests/test_nba_total_luck_replay.py`). **It needs every game.** The league's
shooting rates in the gap come from every game of the season before the date,
so a game is declined while any earlier game lacks its final score or its box
score (`models/nba_total_luck.missing_inputs`). The results step
(`data/ingestors/nba_results_ingestor.py`) therefore retries a missing score
or box back to the season's opening, and writes ESPN's "Postponed" onto
`nba_schedule` so the model stops waiting for a game that was not played.

**Each game is decided once.** The first look 45-57 minutes before tip whose
newest prop fetch holds Pinnacle is the game's decision, bets or none, and is
written to `nba_prop_market_decisions` (worker-only) in the same transaction as
its bets. A game with a row there is never looked at again — the backtest
looked at every game once, and re-deciding at every look would bet a wider
population than was graded. A look without Pinnacle is not a decision.

**Retired 2026-10-15** (`config.RETIRED_MODELS`; no bet was ever written, so
nothing is struck): `nba_moneyline`, `nba_over_under`, `nba_spread`,
`nba_prop_player_{points,rebounds,assists,threes,pra,blocks,steals,turnovers,dd}`.
Their feature engines (`features/nba_feature_engine.py`,
`features/nba_prop_feature_engine.py`), artifacts and scorer loop are gone.

## What the research found (one line each; numbers in `docs/nba_models_2026.md` §4)

- **Schedule is already in the line.** Back-to-backs, road trips, travel, time
  zones and altitude add nothing to Pinnacle's price; a home team on a
  back-to-back is priced −1.71 points and did −2.04.
- **Injuries are in the line by tip-60.** The spread moves 2.26 points per 48
  player-minutes ruled out and results moved 2.21.
- **Moneyline, spread, total, first half, first quarter, team totals:** closed
  for 2026-27 by the first search; nothing passes on a season it was not chosen on.
- **The second search** (§6) graded 422 new cells; none passed its strict bars.
  Under the house standard every shipped model was held to (§6.7) one effect
  passed: totals overs on the shooting-luck gap — `nba_total_luck`, live.
- **Projection models** (`models/nba_props.py`, the NHL count recipe) beat naive
  projections but not the books' price on points and the scoring combos; calibrated
  and bet on every qualifying proposition they clear in steals, blocks, rebounds,
  rebounds+assists and threes — `nba_prop_projection`, live (§5).

## Conventions (load-bearing)

- **Season label = ENDING year** (2026 = 2025-26). Threaded explicitly, never
  derived from a date; `odds_ingestor` labels Oct-Dec games `year+1`.
- **game_id = `NBA_<ET date>_<AWAY>_<HOME>`**, 3-letter codes (`config.NBA_TEAMS`).
  ESPN codes differ (GS, NO, NY, SA, UTAH, WSH) and are mapped in
  `data/ingestors/nba_espn_box.py`.
- **Player id = the NBA.com person id.** The worker's ESPN box writer resolves
  ESPN athlete ids through `player_positions` (the only crosswalk), then by name
  on the same team, and stores a rookie it cannot resolve as `espn:<athleteId>`
  so a game is never left unlogged. Do not run the local nba_api game-log job
  over 2026-27: it would give such a rookie a second, numeric row.
- **A player who does not take the court voids** (DraftKings house rule). A
  player who checks in for any time is action.

## Data (all in Supabase)

| Table | What | Written by | Where it runs |
|---|---|---|---|
| `games` | scores, tip-off (`commence_time`), OT, neutral site | `nba_results_ingestor` (ESPN finals) / `nba_schedule_ingestor` | worker, every refresh pass before settle / this machine |
| `nba_player_game_log` | every player's box line | `nba_results_ingestor` (ESPN) for 2026-27; nba_api for 2018-19 → 2025-26 | worker |
| `nba_player_dnp` | ESPN did-not-play reasons | `nba_results_ingestor` | worker |
| `nba_schedule` | NBA.com schedule: arenas, neutral sites, NBA Cup, national TV, OT | `nba_schedule_ingestor` | this machine (stats.nba.com blocks datacenter IPs) |
| `nba_player_game_adv` | starters, exact minutes, +/-, fouls, usage, possessions, DNP reasons | `nba_box_enrich` (sportsdataverse bulk files + stats.nba.com) | this machine, 2018-19 → 2025-26 |
| `nba_game_inactives`, `nba_game_officials` | inactive lists, referee crews | `nba_box_enrich` | this machine |
| `nba_injury_report` | the official league injury report, every PDF since 2018-12-17, stamped with its printed time | `nba_injury_report` | this machine; `--today` exists, not wired on the worker |
| `nba_period_scores` | points by quarter (settles half/quarter bets) | `nba_period_scores` (ESPN scoreboard) | either |
| `odds` (`source='odds_api_historical'`) | game lines 2020-21 → 2025-26, 9 fetches a game date | `nba_odds_history --lines` | one-off purchase |
| `player_prop_odds` | props 2023-24 → 2025-26 (one snapshot at tip-60); live every refresh pass and every window-job tick with a game near | `nba_odds_history --props`; `prop_odds_ingestor` | purchase; worker |
| `nba_prop_market_decisions` | one row per game the NBA prop card decided: when, on which fetch, quotes seen, bets written | `scripts/nba_prop_market_card.py` | worker |
| `nba_prop_projection_decisions` | the same, for `nba_prop_projection`, with the projection it priced | `scripts/nba_prop_projection_card.py` | worker |
| `nba_total_luck_decisions` | one row per game the totals card decided, bet or not: the fetch, its lead, the gap and the reason | `scripts/nba_total_luck_card.py` | worker |
| `nba_prop_projections` | each player's projected mean per card market, his status and projected minutes, for every game projected | `scripts/nba_prop_projection_card.py --project` | worker |
| `nba_injury_asof` | the injury list each game was projected with: the official report 2018-19 → 2025-26 (90,629 rows, 9,076 games, loaded 2026-10-16), then the ESPN pull each 2026-27 projection used | `scripts/nba_prop_projection_card.py` | worker / this machine |
| `odds` (`source='odds_api_nba_derivative_history'`) | 1H / 1Q / team totals 2024-25 → 2025-26 | `nba_odds_history --derivatives` | one-off purchase |
| `odds` (`source='sbr_archive_nba'`, bookmaker `sbr_consensus`) | 2018-19 and 2019-20 regular seasons: spread and total at the open and the close, the closing moneyline (2019-20: openers on 1,057 of 1,059 games, closes on 1,058; one 2018-19 opener, DEN v POR 2018-11-30, was a price run into the number on the page, refused and deleted 2026-10-17; BKN at DEN 2018-11-09's opener of +9.5 against a −8.5 close is almost certainly a page error, kept as printed). No spread or total price (the page has none, stored NULL); `snapshot_at` is synthetic — open = game date 12:00Z, close = tip − 1 minute. Supporting evidence for closing-line checks, never a bar | `nba_sbr_archive --apply` (free Sportsbook Reviews archive, loaded 2026-10-16) | either |

`player_prop_odds.book_last_update` (added 2026-10-16) stores each book's own
clock for its market, for every sport; the NBA card refuses a soft quote more
than 10 minutes behind Pinnacle's.

## Pipeline (worker)

| Step | When | What |
|---|---|---|
| `nba-prop-odds` | every refresh pass (`par`) | live props, 11 markets + 8 alternates, 7 days ahead (blocks+steals and rebounds+assists added 2026-10-16) |
| `nba-prop-market` | right after `nba-prop-odds`; also in the window job | the card: games tipping in 45-57 minutes and not yet decided; every qualifying proposition; a decision row per game decided; a diagnostic line every look |
| `nba-prop-projection` | right after `nba-prop-market` (refresh pass, 6am run, window job) | the projection card: prices the stored projections for games in their window that `nba_prop_market` has decided (or alone from 50 minutes out); a decision row per game |
| `nba-prop-project` | the window job, about 65 minutes before tip | an ESPN injury pull, then the frame over every box line since 2018-19, stored in `nba_prop_projections`; a game 45-62 minutes out with none is projected at once |
| `nba-total-luck` | only in the totals window job, right after its fetch, under a 180-second limit (NOT in the refresh pass) | the totals card: decides a regular-season game on a fetch that landed 60-66 minutes before tip and is at most 5 minutes old; a decision row per game; the over when the gap is 3+ |
| `nba-prop-close` | after the card; also in the window job | a `close` prop snapshot 12-25 minutes before tip for every game holding a bet (CLV; `NBA_PROP_CLOSE_*` in config) |
| window job `nba_prop_window` | every 5 minutes, 24x7 (`scheduler.run_nba_prop_window`) | props for exactly the games 40-62 minutes from tip that either NBA prop model has not decided, then both cards, then any close that is due, then publish, then the projections due; no API call when nothing is near |
| window job `nba_total_luck_window` | every minute, 24x7 (`scheduler.run_nba_total_luck_window`, `scripts/nba_total_luck_window.py`) | when an undecided game is 61-66 minutes from tip: the NBA board (the refresh pass's own NBA odds fetch, 90-second limit), then `nba-total-luck`, then publish; no API call when nothing is due. Six ticks fit the window, so one skipped tick loses nothing. On the refresh pass a skipped tick lost the game: 27 of 504 evening ticks never started over 2026-10-03..16 |
| `nba-results` | every pass, before settle | ESPN finals → `games`, every box line → `nba_player_game_log` |
| box repair (by hand) | from a residential machine, when the totals card logs `box_missing` or `box_mismatch` | `python -m data.ingestors.nba_stats_ingestor --repair-boxes 2027` replaces each game of the season whose box is missing or does not add up to its final score with NBA.com's, one game per transaction, and writes a game only when NBA.com's box adds up. Not `--game-log-date`: it loads every game of the date and doubles any player ESPN stored under a fallback id |
| `settle` | every pass | props via `_settle_prop_picks` (`FROM_PROP_MARKET`, `_NBA_MARKET_STAT`) |

**Every tip time is reached.** The refresh passes (hourly at :17 until 5pm ET,
every 10 minutes from 6pm) put no look 45-57 minutes before a tip at or before
6:00pm ET, so the five-minute window job does: a tip at 1:00pm, 3:30pm, 6:00pm
or 7:00pm ET each gets a look inside its window
(`tests/test_nba_prop_window.py`). With looks every five minutes and tips on the
hour or half hour, the first look inside the window — the decision — lands
55 minutes before tip; the graded snapshots sat 54 (87%) or 64 (13%)
minutes before tip (`docs/nba_models_2026.md` 4.3). Until 2026-10-16 the
window was 45-70 and that first look landed about 70 minutes out, where
nothing was graded. A game no look reached is
still logged `window_missed`, not widened. NBA is no longer in the 30-second
pre-game poller (no NBA game model exists to re-score).

## Rebuilding the data (this machine)

```bash
python -m data.ingestors.nba_schedule_ingestor --seasons 2019 2027
python -m data.ingestors.nba_box_enrich --seasons 2019 2026
python -m data.ingestors.nba_injury_report --backfill --seasons 2019 2026
python -m data.ingestors.nba_period_scores --start 2018-10-16 --end 2026-04-12
python -m data.ingestors.nba_sbr_archive --apply   # free 2018-19 / 2019-20 lines; a re-run writes nothing
python -m scripts.nba_research_cache          # parquet cache in data/local/nba/ (git-ignored)
```

Price history is bought with `python -m data.ingestors.nba_odds_history`
(`--lines` / `--props` / `--derivatives`, `--max-credits`, stops at
`--floor`, resumable). It cost ~900k credits on 2026-10-15; do not re-run it
without a reason — every row is stored.

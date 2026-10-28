# NBA — models, data, pipeline

> **Rebuilt 2026-10-15/16 (mike: "build new nba models, remove any previous nba
> models").** The twelve 2026-06-19 models are retired; two prop models replace
> them, a totals model joined on 2026-10-17 (`nba_total_luck`), and a home
> team-total model from the fourth search of 2026-10-18 (`nba_team_total_luck`).
> Every market was graded at real prices against bars written before the first
> grid ran: **`docs/nba_models_2026.md`** (the bars, the market grid, every
> result and what failed). Thresholds: `docs/thresholds.md`, NBA section.

## The models

| Model | What it bets | Status |
|---|---|---|
| `nba_prop_projection` | Steals (over or under), rebounds (under), blocks+steals (over or under), blocks (under), rebounds+assists (under), threes (over or under): each player's projected count — minutes × per-minute rate, a negative-binomial width, a per-market calibration map — priced at the consensus main line, every proposition whose calibrated EV at the best bettable price clears its market's floor. Decided once, in the same 45-57 minute window and the same look as `nba_prop_market`. One bet a game across both NBA prop models, at most four a night, each bet ranked by its EV percentile within its own model (`scripts/nba_props_card.py`, mike 2026-10-20). | **LIVE** (artifact — `models/nba_prop_projection.py`, card `scripts/nba_prop_projection_card.py`, steps `nba-prop-project` / `nba-props`) |
| `nba_total_luck` | The full-game OVER, when the projected total with the opponents' three-point and free-throw shooting luck taken out is at least 3 points above the plain projected total. At the best bettable price under the market's fair line; each game decided once, on a fetch 60-66 minutes before tip made by its own one-minute job; regular-season games only (the NBA Cup final never counts); both teams need 10 games, so the first bets come in mid-November. | **LIVE** (rule with a parameter artifact — `models/nba_total_luck.py`, card `scripts/nba_total_luck_card.py`, step `nba-total-luck`, job `nba_total_luck_window`) |
| `nba_team_total_luck` | The HOME team total UNDER, when the home team's own part of that shooting-luck gap is at least 2 points toward the under (the away defence's luck, in the home team's points). At the best bettable price under the market's fair line; each game decided once, on this model's own team-total fetch 45-66 minutes before tip, made by the same one-minute job; settled on the home team's final score, overtime included; regular-season games only; both teams need 10 games. | **LIVE** (rule with a parameter artifact — `models/nba_team_total_luck.py`, card `scripts/nba_team_total_luck_card.py`, step `nba-team-total-luck`, job `nba_total_luck_window`) |
| `nba_prop_market` | The UNDER on points, rebounds, assists, threes or PRA, at the best bettable book whose line equals Pinnacle's in the same fetch, when Pinnacle's no-vig under makes that price +EV. Each game decided once, 45-57 minutes before tip. One bet a game across both NBA prop models, at most four a night, each bet ranked by its EV percentile within its own model (`scripts/nba_props_card.py`, mike 2026-10-20). | **LIVE** (rule — `models/nba_prop_market.py`, card `scripts/nba_prop_market_card.py`, step `nba-props`) |

Graded on 2023-24 → 2025-26, the population it bets (every qualifying
proposition, −200 floor, no double/triple-double): 24,572 bets, +781.3 units,
+2.96%, 90% CI +1.85..+4.05, positive every season (+393.6 / +220.5 / +167.1
units) — about +260 units a season and about 50 bets a night, uncapped. That
was the 2026-10-16 rule (*"maximize units won"*). It is replaced: on 2026-10-20,
after opening night wrote 36 NBA prop bets on one game, mike asked for *"only the
strongest picks ... like NHL"*.

Both NBA prop models now write one bet a game between them and at most four a
night, filled in tip order. A bet is ranked by where its EV sits among its own
model's graded EVs, because the two models' EVs are not on one scale
(`scripts/nba_props_card.py`, `models/nba_prop_rank.py`). Graded on the same
three seasons, that gave +153.8 units, +9.69%, about 4 bets a night, this model
on about 30% of them (the grade is in `docs/thresholds.md`). This model alone at
one a game and four a night had made +94.9 units. Expect about +2% per bet live.

It only ever bets unders because that is where the books' margin sits in
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

**`nba_team_total_luck`** (the fourth search, mike, 2026-10-18: a passing cell
is built live; the evidence is `docs/nba_models_2026.md` 8.4, the settings
`docs/thresholds.md`). Graded walk-forward at bought prices, 2023-24 → 2025-26
pooled: 349 bets, 215-134, +64.72 units, +16.6%, 95% interval +6.4..+26.4,
every season positive (+13.9%, +18.7%, +18.0%); 98 to 139 bets a season.
**Plan on about +7.7%**: the same rule on the away team's total made nothing
and is not built, and the two venues pooled made +7.7% on 713 bets. **Prices it
lays:** -122 to +110, median -112. The probability it writes is the market's
fair chance of the under plus the +0.1022 this bucket won above it on those
three seasons. It reads the same ratings, completeness checks and box scores as
`nba_total_luck`, imported rather than copied. Its quotes
come from its own per-event fetch, because the bulk odds call never returns
team totals; the live code reproduces all 349 of the lab's bets on the research
cache (`tests/test_nba_team_total_luck_replay.py`).

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
  for 2026-27 by the first search; nothing passes on a season it was not chosen
  on. The fourth search (below) re-opened them under the house standard.
- **The second search** (§6) graded 422 new cells; none passed its strict bars.
  Under the house standard every shipped model was held to (§6.7) one effect
  passed: totals overs on the shooting-luck gap — `nba_total_luck`, live.
- **The fourth search** (§8) graded 456 pre-game cells under the house standard;
  2 passed, both the shooting-luck gap on derivative markets. The home team
  total under is `nba_team_total_luck`, live. The first-half over is not built:
  its first-half and second-half results point opposite ways, its pass needs
  every deciding book, and over half its bets are games `nba_total_luck`
  already bets (§8.4). The market-anchored model (the NHL recipe) found nothing.
- **Projection models** (`models/nba_props.py`, the NHL count recipe) beat naive
  projections but not the books' price on points and the scoring combos; calibrated
  and bet on every qualifying proposition they clear in steals, blocks, rebounds,
  rebounds+assists and threes — `nba_prop_projection`, live (§5).

## The schedule the models read

**Kept current on the worker every day** (`nba-schedule`,
`data/ingestors/nba_schedule_refresh.py`, since 2026-10-20). Before that the
2026-27 schedule was one load by hand (2026-10-15) that nothing refreshed: the
24 NBA Cup week games the league had not yet set were missing, the knockout
games were placeholders with no teams, and both prop models skipped every game
the schedule did not type as regular season. Measured 2026-10-20: ESPN's
2026-27 schedule holds the same 1,200 games as the stored one, month by month,
at the same tips but one (CHI @ MIL 2026-10-23, where ESPN alone says 4pm ET
and the league's load, the Bucks' release and ticket listings say 7pm CT, so
ESPN never moves a tip on its own word). A tip moves when the odds feed's start
for the game shows it too. The feed lists the books' start, not the league's
tip: of the 46 2026-27 games it had written by 10-20, 8 sat on the tip, 35 ten
minutes after it, 3 more 8 to 22 minutes after, none before. So the feed seconds
ESPN when its start is from a minute before to 30 minutes after ESPN's new tip
and does not fit the stored tip, or sits nearer ESPN's when it fits both. This
matters for a game flexed later: all four NBA models take the earlier of the
schedule's tip and the feed's start, so a 7pm game flexed to 9:30 that the
schedule still held at 7pm would be decided three and a half hours early. A
by-hand NBA.com load still works and replaces any `espn:` row of the games it
writes. **If the scoreboard refuses this month or next, that month is read from
ESPN's other host**, `sports.core.api.espn.com`. The scoreboard host answered
the worker 403 on every day it was probed from 2026-08-08 to 2026-09-30, eight
weeks, while the other host served the WNBA results step throughout. That host
lists games as links: one call per game and one per team. December 2026 read
that way took 209 calls and 170 seconds from the build machine and came back
the same as the scoreboard (172 games, the same ids, the same fields but status
and TV). All nine months would add about 18 minutes to the 6am run, so only the
next two are read; a game further out is read again by the time it is near. It
carries no status or TV inline, so a month read from it records no postponement
and leaves a stored status as it is. A month neither host answers whole is left
as stored, the step goes red, and the health check warns after 36 hours.

**What the prop models price.** Every regular-season game, the Cup quarterfinals
and semifinals included, whether or not the schedule lists it yet (a game the
odds feed wrote on a regular-season day counts, the totals model's rule,
`models.nba_total_luck.regular_season`). **Not the play-in, the playoffs or the
Cup final:** neither prop model has been graded on one. The stored prop history
holds 0 of those 272 games of 2023-24..2025-26 and all 3,690 regular-season
games; grading them means buying those props first. The totals models are
regular season only too (the Cup final never counts).

**Rest.** The projection model's rest, back-to-back, games-in-four-days and
road trip, and every player's history, read every regular-season game in
`games`, listed or not, plus the Cup final once the schedule lists it
(`models.nba_props.regular_game_ids`; ESPN carries the final's note before its
teams are set, so the refresh types it the day they are).
Removing the Cup week from 2023-24..2025-26 put the wrong rest on 30 team-games
a season.

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
| `nba_schedule` | NBA.com schedule: arenas, neutral sites, NBA Cup, national TV, OT; every game type | `nba_schedule_ingestor` (the season's load) / `nba_schedule_refresh` (ESPN, daily) | this machine (stats.nba.com blocks datacenter IPs) / worker, the 6am run |
| `nba_player_game_adv` | starters, exact minutes, +/-, fouls, usage, possessions, DNP reasons | `nba_box_enrich` (sportsdataverse bulk files + stats.nba.com) | this machine, 2018-19 → 2025-26 |
| `nba_game_inactives`, `nba_game_officials` | inactive lists, referee crews | `nba_box_enrich` | this machine |
| `nba_injury_report` | the official league injury report, every PDF since 2018-12-17, stamped with its printed time | `nba_injury_report` | this machine; `--today` exists, not wired on the worker |
| `nba_period_scores` | points by quarter (settles half/quarter bets; feeds the team page's first-quarter card) | `nba_period_scores` (ESPN scoreboard) | worker, the 6am run (`nba-quarters`, from 2026-10-28) / either |
| `nba_team_q1_games` | one row per team per regular-season game: first-quarter points for and against (from `nba_period_scores`), possessions for and against (from `nba_stints` period 1; NULL when the stints' 1Q points miss the quarter score). Read by the app; `v_nba_team_q1_season` ranks it per season and venue | `data/ingestors/nba_team_q1.py` | worker, the 6am run (`nba-quarters`) |
| `odds` (`source='odds_api_historical'`) | game lines 2020-21 → 2025-26, 9 fetches a game date | `nba_odds_history --lines` | one-off purchase |
| `player_prop_odds` | props 2023-24 → 2025-26 (one snapshot at tip-60); live every refresh pass and every window-job tick with a game near | `nba_odds_history --props`; `prop_odds_ingestor` | purchase; worker |
| `nba_prop_market_decisions` | one row per game the NBA prop card decided: when, on which fetch, quotes seen, bets written | `scripts/nba_prop_market_card.py` | worker |
| `nba_prop_projection_decisions` | the same, for `nba_prop_projection`, with the projection it priced | `scripts/nba_prop_projection_card.py` | worker |
| `nba_total_luck_decisions` | one row per game the totals card decided, bet or not: the fetch, its lead, the gap and the reason | `scripts/nba_total_luck_card.py` | worker |
| `nba_team_total_luck_decisions` | one row per game the home team-total card decided, bet or not: the fetch, its lead, the home team's part of the gap, the full-game gap, the best under offer (book, line, price, fair and written probability, fair line), each book's last-update age, and the reason | `scripts/nba_team_total_luck_card.py` | worker |
| `nba_team_total_fetches` | one row per team-total call (the event list, and each game's call, `open` or `close`): when, ok or failed, rows stored, main rows, the books, each book's last-update age, the feed's `x-requests-last` | `data/ingestors/nba_team_total_odds.py` | worker |
| `odds` (`source='odds_api_nba_team_totals_live'`) | live team totals, one per-event call a game: each book's main number under `team_totals_home` / `team_totals_away`, every other line under `team_totals_home_alternate` / `team_totals_away_alternate`; `snapshot_type` `open` for the decision fetch, `close` for the closing snapshot; `created_at` is the fetch instant, `snapshot_at` the book's own last update. The odds prune skips this source (`data/prune_odds.PROTECTED_SOURCES`), which keeps every line | `data/ingestors/nba_team_total_odds.py` | worker |
| `nba_prop_projections` | each player's projected mean per card market, his status and projected minutes, for every game projected | `scripts/nba_prop_projection_card.py --project` | worker |
| `nba_injury_asof` | the injury list each game was projected with: the official report 2018-19 → 2025-26 (90,629 rows, 9,076 games, loaded 2026-10-16), then the ESPN pull each 2026-27 projection used | `scripts/nba_prop_projection_card.py` | worker / this machine |
| `odds` (`source='odds_api_nba_derivative_history'`) | 1H / 1Q / team totals 2023-24 → 2025-26 (2023-24 bought 2026-10-18), one purchase a game about an hour before tip. Every team-total line a book quoted is stored under `team_totals_home` / `team_totals_away`, NOT split like the live feed; the lab and the replay pick each book's main number when they read it. The odds prune skips this source from 2026-10-20: it keeps one row per game, market and book, which would cut a ladder of lines to one or two | `nba_odds_history --derivatives` | one-off purchase |
| `odds` (`source='sbr_archive_nba'`, bookmaker `sbr_consensus`) | 2018-19 and 2019-20 regular seasons: spread and total at the open and the close, the closing moneyline (2019-20: openers on 1,057 of 1,059 games, closes on 1,058; one 2018-19 opener, DEN v POR 2018-11-30, was a price run into the number on the page, refused and deleted 2026-10-17; BKN at DEN 2018-11-09's opener of +9.5 against a −8.5 close is almost certainly a page error, kept as printed). No spread or total price (the page has none, stored NULL); `snapshot_at` is synthetic — open = game date 12:00Z, close = tip − 1 minute. Supporting evidence for closing-line checks, never a bar | `nba_sbr_archive --apply` (free Sportsbook Reviews archive, loaded 2026-10-16) | either |

`player_prop_odds.book_last_update` (added 2026-10-16) stores each book's own
clock for its market, for every sport; the NBA card refuses a soft quote more
than 10 minutes behind Pinnacle's.

## Pipeline (worker)

| Step | When | What |
|---|---|---|
| `nba-prop-odds` | every refresh pass (`par`) | live props, 11 markets + 8 alternates, 7 days ahead (blocks+steals and rebounds+assists added 2026-10-16) |
| `nba-props` | right after `nba-prop-odds`; also in the window job (the old names `nba-prop-market` and `nba-prop-projection` run the same step) | BOTH NBA prop cards in one look: games tipping in 45-57 minutes and not yet decided; every qualifying proposition of both pooled, then one bet a game across both models and `MAX_NBA_PROP_BETS_PER_NIGHT` (4) a night, ranked by each bet's EV percentile within its own model, the night's written bets counted (`scripts/nba_props_card.py`); a decision row per game per model; a diagnostic line every look |
| `nba-prop-project` | the window job, about 65 minutes before tip | an ESPN injury pull, then the frame over every box line since 2018-19, stored in `nba_prop_projections`; a game 45-62 minutes out with none is projected at once |
| `nba-total-luck` | only in the totals window job, right after its fetch, under a 180-second limit (NOT in the refresh pass) | the totals card: decides a regular-season game on a fetch that landed 60-66 minutes before tip and is at most 5 minutes old; a decision row per game; the over when the gap is 3+ |
| `nba-team-total-luck` | only in the totals window job, right after its team-total fetch, under a 180-second limit | the home team-total card: decides a regular-season game on its own team-total fetch that landed 45-66 minutes before tip and is at most 5 minutes old; a decision row per game; the home team total under when the home team's part of the gap is 2+ toward the under |
| `nba-prop-close` | after the card; also in the window job | a `close` prop snapshot 12-25 minutes before tip for every game holding a bet (CLV; `NBA_PROP_CLOSE_*` in config) |
| window job `nba_prop_window` | every 5 minutes, 24x7 (`scheduler.run_nba_prop_window`) | props for exactly the games 40-62 minutes from tip that either NBA prop model has not decided, then both cards, then any close that is due, then publish, then the projections due; no API call when nothing is near |
| window job `nba_total_luck_window` | every minute, 24x7 (`scheduler.run_nba_total_luck_window`; one planning read for both totals models, `scripts/nba_pregame_window.py`) | `nba_total_luck` first, when an undecided game is 61-66 minutes from tip: the NBA board (the refresh pass's own NBA odds fetch, 90-second limit), then `nba-total-luck`. Then `nba_team_total_luck`, when an undecided game is 45-56 minutes from tip: one `team_totals` call per due game (`scripts/nba_team_total_luck_window.py --fetch`, 90-second limit), then `nba-team-total-luck`; and for each game holding its bet, the closing team totals 12-25 minutes before tip (`--close`, 90-second limit, filed `close`, for closing-line value). Then one publish. No API call when nothing is due. Six ticks fit the full-game window and twelve the team-total one, so one skipped tick loses nothing. One job for both, not two: every job opens a database connection each tick for its heartbeat. On the refresh pass a skipped tick lost the game: 27 of 504 evening ticks never started over 2026-10-03..16 |
| `nba-schedule` | the 6am run, before `nba-results` | ESPN's schedule for this month and the next eight (one call a month) → `nba_schedule`: games it lacks under an `espn:` key (the NBA Cup week and knockout games once set, play-in, playoffs), postponements, and a moved tip only when the odds feed shows the same start. Fail-open: a month ESPN does not answer is left as stored; the step goes red and the health check `nba_schedule_refresh` goes STALE after 36 hours with no row confirmed |
| `nba-results` | every pass, before settle | ESPN finals → `games`, every box line → `nba_player_game_log` |
| `nba-quarters` | the 6am run, after view migrations | for the current season: quarter scores for every finished game lacking them (`nba_period_scores`), play-by-play and possessions for every game lacking them (`nba_pbp.fill_gaps`, ESPN summary; refuses past 100 missing), then `nba_team_q1_games` rebuilt for this season and the last. Free ESPN endpoints. Added 2026-10-28: before it, the 2026-27 season had 0 of 56 finished games with quarter scores and no play-by-play after 2026-06-13 |
| box repair (by hand) | from a residential machine, when the totals card logs `box_missing` or `box_mismatch` | `python -m data.ingestors.nba_stats_ingestor --repair-boxes 2027` replaces each game of the season whose box is missing or does not add up to its final score with NBA.com's, one game per transaction, and writes a game only when NBA.com's box adds up. Not `--game-log-date`: it loads every game of the date and doubles any player ESPN stored under a fallback id |
| `settle` | every pass | props via `_settle_prop_picks` (`FROM_PROP_MARKET`, `_NBA_MARKET_STAT`); the two totals models through `paper_tracker._RULE_MODEL_MARKETS`: `nba_total_luck` on the full-game total, `nba_team_total_luck` on the home team's own final score (overtime included; a push when equal) |

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

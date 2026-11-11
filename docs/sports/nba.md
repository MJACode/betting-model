# NBA — models, data, pipeline

> **Rebuilt 2026-10-15/16 (mike: "build new nba models, remove any previous nba
> models").** The twelve 2026-06-19 models are retired; two prop models replace
> them, a totals model joined on 2026-10-17 (`nba_total_luck`), a home
> team-total model from the fourth search of 2026-10-18 (`nba_team_total_luck`),
> and that search's first-half model, built 2026-10-30 (`nba_first_half_total_luck`).
> Every market was graded at real prices against bars written before the first
> grid ran: **`docs/nba_models_2026.md`** (the bars, the market grid, every
> result and what failed). Thresholds: `docs/thresholds.md`, NBA section.

## The models

| Model | What it bets | Status |
|---|---|---|
| `nba_prop_projection` | Steals (over or under), rebounds (under), blocks+steals (over or under), blocks (under), rebounds+assists (under), threes (over or under): each player's projected count — minutes × per-minute rate, a negative-binomial width, a per-market calibration map — priced at the consensus main line, every proposition whose calibrated EV at the best bettable price clears its market's floor. Decided once, in the same 45-57 minute window and the same look as `nba_prop_market`. One bet a game across both NBA prop models, at most six a night (four until 2026-11-04), each bet ranked by its EV percentile within its own model (`scripts/nba_props_card.py`, mike 2026-10-20 and 2026-11-04). | **LIVE** (artifact — `models/nba_prop_projection.py`, card `scripts/nba_prop_projection_card.py`, steps `nba-prop-project` / `nba-props`) |
| `nba_total_luck` | The full-game OVER, when the projected total with the opponents' three-point and free-throw shooting luck taken out is at least 3 points above the plain projected total. At the best bettable price under the market's fair line; each game decided once, on a fetch 60-66 minutes before tip made by its own one-minute job; regular-season games only (the NBA Cup final never counts); each team needs one game (no 10-game wait, 2026-11-02). One NBA game-total bet a game: it decides first, so the first-half over and the home team total under stand aside on a game it bets (`scripts/nba_game_totals_door.py`, mike 2026-11-04). | **LIVE** (rule with a parameter artifact — `models/nba_total_luck.py`, card `scripts/nba_total_luck_card.py`, step `nba-total-luck`, job `nba_total_luck_window`) |
| `nba_first_half_total_luck` | The FIRST-HALF total OVER, when the full-game shooting-luck gap (`nba_total_luck`'s number, unscaled) is at least 2 points and below 3 (from 2026-11-04, mike: at 3 or more `nba_total_luck` bets the same game on the same gap, so this was its twin; `docs/thresholds.md`). At the best bettable price under the market's fair line; each game decided once, on this model's own first-half fetch 45-66 minutes before tip, made by the same one-minute job; settled on Q1 + Q2 points; a game with no trustworthy quarter scores stays pending; regular-season games only; each team needs one game (no 10-game wait, 2026-11-02). One NBA game-total bet a game (`scripts/nba_game_totals_door.py`). | **LIVE** (rule with a parameter artifact — `models/nba_first_half_total_luck.py`, card `scripts/nba_first_half_total_luck_card.py`, step `nba-first-half-total-luck`, job `nba_total_luck_window`) |
| `nba_q1_trend` | The FIRST-QUARTER spread of the hot team: mike's cover-record trend, the "bump it out to L10" step with his season-average check. A team 4-1 or 5-0 against the first-quarter spread over its last 5 games at tonight's venue, against an opponent 2-3 or 1-3 over its last 5 there, both teams' last 10 agreeing by k >= 2, and the hot team's projected first-quarter margin from both teams' season averages covering its number. Each game decided once on this model's own first-quarter fetch 45-66 minutes before tip, at the deciding book with the best EV under the first-quarter market's fair line, -200 floor; settled on period 1 against the HOME number; regular season only. Did NOT pass the house standard (the 200-bet bar): 88 bets, +27.4%. Section "First quarter" below. | **LIVE 2026-11-07** (mike: "I WANT THAT MODEL"; rule with a parameter artifact `models/saved/nba_q1_trend_20261107.pkl`, `models/nba_q1_trend.py`, card `scripts/nba_q1_trend_card.py`, step `nba-q1-trend`, job `nba_total_luck_window`) |
| `nba_team_total_luck` | The HOME team total UNDER, when the home team's own part of that shooting-luck gap is at least 2 points toward the under (the away defence's luck, in the home team's points). At the best bettable price under the market's fair line; each game decided once, on this model's own team-total fetch 45-66 minutes before tip, made by the same one-minute job; settled on the home team's final score, overtime included; regular-season games only; each team needs one game (no 10-game wait, 2026-11-02). One NBA game-total bet a game (`scripts/nba_game_totals_door.py`). | **LIVE** (rule with a parameter artifact — `models/nba_team_total_luck.py`, card `scripts/nba_team_total_luck_card.py`, step `nba-team-total-luck`, job `nba_total_luck_window`) |
| `nba_live_spread_q12` | IN PLAY. The game-state model (IG-2) against the live spread in quarters 1-2: per game, the first fetch holding a fresh quote decides, at the best of the eight deciding books, -200 floor, when the model's EV is 0.05 or better; the fetches are the archive's hourly purchase moments, each hour minus 264 seconds. Settled on the full-game score at the HOME number. The quarter-3 moneyline and spread (`nba_live_ml_q3`, `nba_live_spread_q3`) are held out: they fail the house standard on those fetches. Section "In play" below. | **LIVE 2026-11-04** (artifact `models/saved/nba_live_ig2_2027.json`, `models/nba_live_ig2.py`, loop `models/nba_live_loop.py`, job `nba_live`) |
| `nba_prop_market` | The UNDER on points, rebounds, assists, threes or PRA, at the best bettable book whose line equals Pinnacle's in the same fetch, when Pinnacle's no-vig under makes that price +EV. Each game decided once, 45-57 minutes before tip. One bet a game across both NBA prop models, at most six a night (four until 2026-11-04), each bet ranked by its EV percentile within its own model (`scripts/nba_props_card.py`, mike 2026-10-20 and 2026-11-04). The only NBA model that bets the play-in, the playoffs and the Cup final (below). | **LIVE** (rule — `models/nba_prop_market.py`, card `scripts/nba_prop_market_card.py`, step `nba-props`) |

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

**`nba_first_half_total_luck`** (the fourth search's other passing cell, C1; mike,
2026-10-30: "Build the model that passed."; the evidence is `docs/nba_models_2026.md`
8.3 and 8.4, the settings `docs/thresholds.md`). Graded walk-forward at bought
prices, 2023-24 → 2025-26 pooled: 595 bets, 333-259-3, +51.49 units, +8.0%, 95%
interval +0.4..+15.4, every season positive (+4.0%, +11.6%, +9.9%); 163 to 244 bets
a season. **Prices it lays:** -130 to +114 across all books, -118 to +105 at the four
books whose rows look like main numbers (BetRivers', betPARX's and most of Hard Rock's
rows are not: `docs/nba_models_2026.md` 8.4), median -110; lines 100.0 to 130.5,
median 114.0. The probability it writes is the market's fair chance of the over
plus the +0.0572 this bucket won above it on those three seasons. Its EV floor of
0.00 removes 2 of the 595, both wins, so the graded record under the live rule is
593 bets, +49.49 units, +7.7%. Its ratings, completeness checks and box scores are
`nba_total_luck`'s, imported; its window is `nba_team_total_luck`'s. Its quotes come
from its own per-event fetch, because nothing else stored first-half lines for
2026-27; the live code reproduces all 595 of the lab's bets on the research cache
(`tests/test_nba_first_half_total_luck_replay.py`).

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

## First quarter: mike's cover-record trend, live without passing (mike, 2026-11-07)

**`nba_q1_trend` is live on mike's instruction, not on the house standard.** Every first-quarter search failed
(`docs/nba_models_2026.md` section 13). mike, 2026-11-07: build the first-quarter model ("I WANT THAT MODEL"). The cell
shipped is the one first-quarter cell in any search whose 95% interval sits above zero: the eighth search's "bump it
out to L10" step with the season-average check (section 12, run `2026-10-28-eighth`).

| | Bets | Units | Return | 95% interval |
|---|---|---|---|---|
| 2023-24 .. 2025-26 pooled | 88 (58-29-1) | +26.33 | +27.4% | +8.85% to +44.79% |
| 2023-24 / 2024-25 / 2025-26 | 20 / 32 / 36 | | +21.5% / +49.6% / +11.1% | |

**What it failed, once:** the 200-bet bar (about 29 bets a season); the band just below it lost 5.9% on 88 bets; its
first 44 bets made +42.7% and its last 44 +12.7%; 17 bets at a number no other book hung went 15-1-1 for +13.9 of its
+26.3 units. **Prices it laid:** -125 to +118, median -110 (5th to 95th percentile -122 to +29). Books: DraftKings 38,
FanDuel 30, BetMGM 13, Caesars 3, BetRivers 3, betPARX 1. 63 of the 88 bets were on the away team.

**The replay** (`python -m scripts.nba_q1_trend_replay`): the live `decide()` on the archive reproduces all 88 graded
bets, same game, side, book, line and price, on the books the lab graded with. betPARX has since left the deciding
books (`config.BEST_LINE_BOOKMAKERS`), so on today's books one bet (`NBA_2025-11-12_DEN_LAC`, away +1.5) moves from
betPARX -104 to BetMGM -105.

**The probability:** the market-fair P(cover) plus the cell's uplift, +0.1526 for 2026-27 (58 wins of 88 against a mean
fair probability of 0.5065). On 88 bets that number is large and uncertain; the app's note says to read it as an upper
bound.

**Data it reads:** every team's first-quarter number per game, from the archive (`odds_api_nba_derivative_history`,
2023-24 .. 2025-26), the 2026-27 purchase (spreads_q1 alone, 132 games at tip minus 60, 1,052 rows, 1,337 credits,
2026-11-07) and its own live fetch (`odds_api_nba_first_quarter_live`, one spreads_q1 call per game, at most 1 credit a
call). First-quarter scores from `nba_period_scores` through the first search's check. Read on production 2026-11-07:
2,724 team rows of 2025-26 and 2026-27, 121 of this season's games with a number.

**A game played while the live fetch is down has no number**, and drops out of both teams' records, as an unpriced
game did in the lab. `nba_odds_history._buy_per_event(..., ["spreads_q1"], ...)` at tip minus 60 fills such a game from
the history endpoint; a re-run buys only what is missing.

## In play: the game-state model's quarters 1-2 spread (mike, 2026-11-04)

mike: *"everything goes live now, that's why we do back testing ... and you
continually improve models as you get more data."* The third NBA search's
game-state model (IG-2, `docs/nba_models_2026.md` 7.2-7.3) passed the house
standard in six cells, which are three rules (the EV 0.08 cells sit inside the
0.05 ones). Best of the eight deciding books, -200 floor, one unit to win, risk
capped at 3, 2021-22 to 2025-26.

**Graded on the fetches the loop makes** (2026-11-04, after the independent
review): the archive's hourly purchases only, the rule exactly as shipped,
through the house standard of `docs/nba_models_2026.md` section 9 (bands, 200
placebo runs; `scripts/nba_live_ig2_regrade.py`, then
`scripts/nba_game2_verdict.py --house5`):

| Model | Rule | Bets | Units | ROI | 95% interval | Seasons positive | House standard | Status | Prices laid (min / median / max) |
|---|---|---|---|---|---|---|---|---|---|
| `nba_live_spread_q12` | spread, quarters 1-2, EV >= 0.05 | 1,348 | +96.6 | +6.4% | +1.4 .. +11.3 | 5 of 5 | passes all six bars | **LIVE** | -160 / -114 / +114 |
| `nba_live_ml_q3` | moneyline, quarter 3, EV >= 0.05 | 503 | +26.2 | +8.3% | -2.7 .. +19.3 | 4 of 5 | fails the interval and the bands | held out | -200 / +200 / +3000 |
| `nba_live_spread_q3` | spread, quarter 3, EV >= 0.05 | 813 | +41.2 | +4.5% | -2.0 .. +11.0 | 4 of 5 | fails the interval, the bands and the placebo | held out | -140 / -113 / +125 |

**Only the quarters 1-2 spread is live** (mike, 2026-11-04: the backtest is
the gate). The two quarter-3 models are held out the way the quarter-4 spread
is: not in the loop's rule list, not in config's live models, thresholds or EV
floors, not registered. Their code stays (`models/nba_live_ig2.HELD_OUT_RULES`,
the same decision path), so each is re-graded as this season's in-play prices
and play-by-play accumulate (`scripts/nba_live_ig2_regrade.py` for the held
seasons, `scripts/build_nba_live_ig2_artifact.py --parity-live27` for 2026-27
at the loop's fetch times) and added the day it passes. At EV >= 0.08 neither
is a fallback: the moneyline fails the bands (the 0.05-0.08 band lost 10.4
units on 78 bets), the spread the interval.

The grade that put them forward, beside the shipped rule on every purchase:

| Model | Record 7.3: every purchase, IG-2's own state join | The shipped rule, every purchase |
|---|---|---|
| `nba_live_spread_q12` | 1,475 bets, +103.6, +6.2%, +1.4 .. +11.1, 4 of 5 | 1,417 bets, +87.3, +5.5%, +0.7 .. +10.5, 4 of 5 |
| `nba_live_ml_q3` | 651 bets, +40.1, +10.0%, +0.1 .. +19.9, 5 of 5 | 634 bets, +41.6, +10.8%, +0.9 .. +20.9, 5 of 5 |
| `nba_live_spread_q3` | 1,055 bets, +79.6, +6.7%, +1.2 .. +12.6, 5 of 5 | 991 bets, +59.9, +5.4%, -0.1 .. +11.3, 5 of 5 |

The two columns differ by the rules the 2026-27 search added (the stable state
join, the far-from-Pinnacle and clock-jump rules, `docs/nba_search_ingame27.md`
section 3). 93 to 96% of record 7.3's bets are the same bet; most of the rest
are quotes those rules now drop. Record 7.3 passed the house standard it was
judged under (section 6.7). Under section 9's bands bar, rebuilt from its
nested cuts, all three would fail: -13.3 units on the 638 bets just below the
quarters 1-2 cut, -9.5 on the 106 just above the quarter-3 moneyline cut, -23.8
on the 317 just below the quarter-3 spread cut. Dropping the gap-fill purchases
(the second column to the first table) costs the quarter-3 rules 131 and 178
bets and 15.4 and 18.7 units; the quarters 1-2 spread loses 69 bets and gains
9.3 units.

**Read before trusting it.** Every warning sign written down before the grade
was present: about half of each cell's units came from outlier prices, the
deciding books' own moneyline prices showed no gain from the model, DraftKings
alone lost in 2025-26 in all six cells, and the quarter-3 moneyline bets are
mostly underdogs. 2026-27's re-run on the worker's live prices, every worker
fetch about 10 minutes apart (`docs/nba_search_ingame27.md` section 12), read
the quarter-3 spread +12.0% on 51 bets, the quarter-3 moneyline -22.7% on 29
and the quarters 1-2 spread -5.7% on 36: too few bets to read. At the loop's
own fetch times the same games give 35, 11 and 16 bets (below). Each rule that
ships is judged on its live record.

**Not built: the quarter-4 spread.** It failed the placebo bar in the grade.
Like the two quarter-3 models, the loop does not decide it; it is added the day
a re-grade passes the house standard. The quarters 1-2 and quarter-4 moneylines failed
every bar.

**The rule, as shipped and as re-graded above** (`models/nba_live_ig2.py` calls
the graded code for each step). The model is fit for 2026-27 on every held season, 2020-21 to 2025-26.
The prior is Pinnacle's last coherent pre-tip spread. The game state at a quote
is the last ESPN play logged at or before its stamp, ties broken by play order
(the 2026-27 search's stable join). A quote is fresh only if no point was scored
between its stamp and the fetch, the same holds for its Pinnacle quote, and
Pinnacle quoted within 60 seconds. A game whose first ESPN play is more than 15
minutes before the listed tip, or with a 45-minute clock jump, is refused. A
price between -100 and +100, or a deciding quote more than 6 points (spread) or
0.25 no-vig (moneyline) from its Pinnacle pair, is dropped. Quarters 1-2 means
periods 1-2 live or the break after quarter 1; quarter 3 means period 3 live or
the break after it; the half is neither. Per game and rule, the first fetch
holding a fresh quote decides: the side whose best offer has the higher model
EV, at its best price, when EV >= 0.05 and the price is -200 or better (EV
rounded to 12 decimals first, so a tie between books goes to the same book
whatever the floating-point noise). A fresh
fetch that does not clear the cut spends the rule; a later fetch is never used.
No 10-game wait (the prior is the market's pre-game spread). Regular season only.

**The fetches are the archive's hourly purchases, and only those.** The
archive bought two kinds of in-play fetch. The hourly purchase was requested on
the hour and served the market as it stood 264 seconds earlier (553 s in
2020-21, 549 s in 2021-22). The gap fill was bought at :30, mostly 30 minutes before
a listed tip. The loop can rebuild only the hourly one: in 2026-27
`games.commence_time` holds the actual start, not the listed tip, so a fetch
built from a tip would be a population never graded. It fetches at each hour
minus 264 seconds (`NBA_LIVE_FETCH_OFFSET_SEC`) and at nothing else. A failed
attempt, or one whose ESPN read fails, is retried every 60 seconds up to 240
seconds after that moment (`NBA_LIVE_FETCH_WINDOW_SEC`,
`NBA_LIVE_RETRY_GAP_SEC`), and each failed attempt is a `skipped` row with its
reason. A loop polling every few seconds would decide every game in the first
minute of each phase, which was never graded either.

**What the loop reads live, and how fresh.** `nba_pbp` is written only after a
game is final (`nba_pbp.fill_gaps`, the 6am run), so the loop reads ESPN's free
summary endpoint itself, through the same parsing that wrote the 2026-27 rows
the search graded. ESPN's play wallclock is when it LOGGED a play (74 plays of
`NBA_2026-10-23_LAC_LAL` carry 02:35:53-54), and the grade read plays by that
wallclock. The summary serves a play some seconds after it is logged. Measured
on the 2026-11-04 slate (8 games polled every 5 seconds, 629 plays first seen
live, `%TEMP%/nba_live_build/espn_lag3.py`): a median 34 seconds from wallclock
to first served, 64 at the 90th percentile, 600 at the 99th. For the 134
scoring plays: median 39 seconds, 99th percentile 168, longest 219. Two earlier
runs agree (median 31 seconds on one game, 34 on five).

So the loop reads each game's summary twice and decides on the second read: 170
seconds after the fetch (`NBA_LIVE_PBP_WAIT_SEC`, the scoring plays' 99th
percentile), then 60 seconds later (`NBA_LIVE_PBP_RECHECK_SEC`). It refuses a
game at that fetch, fail closed, when:
- a play logged at or before the quotes' moment appears only on the second read
  (ESPN was publishing late, so the second read may be incomplete too);
- ESPN's header score is ahead of its newest play's running score, on the
  second read and again on a re-read 20 seconds later;
- ESPN's clock ran between the two reads while its newest play is more than 230
  seconds old (`NBA_LIVE_PLAY_LAG_MAX_SEC`).

Replayed on the measured plays (`%TEMP%/nba_live_build/lag_sim.py`, every
minute of each game the poller watched, 153 fetch moments): no scoring play was
missed by both reads, and none caused a skip. Counting every play, 8 moments
(5.2%) are skipped. 28 moments (18.3%) still miss a non-scoring play ESPN served
more than 230 seconds late: 10 of the 629 plays, among them offensive rebounds,
tip shots, substitutions and one technical foul. The model reads the score,
the clock and fouls, so the score is never wrong and substitutions do not enter
it. In 25 of the 28 the state's own play (the last at or before the quote) is
unchanged, in 3 it is a play logged in the same second, and 2 miss the
technical foul (a foul count can be one short). With
the old single read 45 seconds after the fetch, 8 moments (5.2%) missed a
scoring play. Every decision stores `play_lag_s`.

**Replayed on 2026-27's live rows at the loop's fetch times** (95 moments: the
worker's first fetch within 10 minutes after each hour minus 264 seconds), with
each fetch seeing only the plays logged by its served time plus 230 seconds, over
all three graded rules. The loop's decision path makes the same decisions, at
the same fetch, as a replay that knows every play: all 30 quarter-3 moneyline
decisions (11 bets), all 34 quarter-3 spread
decisions (16 bets) and all 78 quarters 1-2 spread decisions (35 bets). It
makes 2 more quarters 1-2 decisions, on `NBA_2026-10-20_PHI_NYK` and
`NBA_2026-10-23_MEM_GSW`, and the first is a bet. Those are the two games the
search left out whole for a 45-minute clock jump (doc 3.2); a live loop sees a
jump only from the moment it happens. **The fetch times are what move the
record.** The search graded every worker fetch, about every 10 minutes, and bet
36, 29 and 51 times. At the loop's fetch times the same plays give 35, 11 and 16
bets, and only 7, 3 and 6 of them are the same bet.
`scripts/build_nba_live_ig2_artifact.py --parity-live27` (`--wait N`,
`--every-fetch`). The fail-closed skip cannot be replayed this way: the archive
does not hold when ESPN published each play.

**Prices, cost, writes.** One bulk Odds API call per instant covers every game:
h2h and spreads, the eight deciding books and Pinnacle (Pinnacle is what the
freshness rule pairs with). Nine books stay inside one region group, so the
feed's markets-times-regions billing gives 2 credits a call (the same NBA call
with totals bills 3, `api_call_log` 2026-11-02 to 11-04); the loop logs the
first call's `x-requests-last`. The 2026-27 schedule has 6 fetch moments a
slate at the median (5 to 11 for the middle 80% of its 159 dates, 14 at most;
each hour minus 264 seconds from the first tip to three hours after the last,
`%TEMP%/nba_live_build/probe_slots2.py`). The loop fetches at a moment only
while a game in progress has a rule not yet decided, so about 12 credits a
night at the median, plus 2 for each retry (at most 5 attempts a moment). Caps:
100 calls and 200 credits a process, the shared `LIVE_DAILY_CREDIT_CAP`
(`live_credit_telemetry`), and no fetch below 1,000 credits left. (A second
floor, 15% of the plan, was removed 2026-11-07, mike: "I dont care about the
odds api balance". At 387,166 of 5,000,000 it stopped the loop after the first
fetch of each night.) `--dry-run` makes no call. The
fetched rows go to `odds` as `in_play`.

**Decided once, recorded once.** Every decision, bet or not, is a row in
`nba_live_decisions`, one per game and rule, never replaced: the state, the
prior, the model's mean and spread, every priced offer, and `play_lag_s` (the
seconds from the newest ESPN play to the decision). A restart reads it, so a
rule spent before a deploy is not decided again, and seeds the loop's memory of
the quotes it already fetched from its own `odds` rows. The loop refuses to
decide while that table is missing. Rows that do not spend a rule sit beside
the decisions: `skipped` (an attempt that could not be read, with the reason)
and `carried` (a fetch with no fresh quote in the phase). A failure inside one
game's evaluation is that game's `declined` row, with the exception text; the
other games go on.

**One game, no two bets that cannot both win** (mike, 2026-10-17). A later
rule's bet that cannot win beside a standing one is declined; two decided in
one pass that cannot both win are both declined. With one live rule it never
fires; it stays for the day a quarter-3 model is added. On the hourly
re-grade's bets of all three it would decline 46 of 2,664, worth +9.40 units: the quarter-3 moneyline falls to
481 bets, +22.0 units, +7.2%; the quarter-3 spread to 789 bets, +36.0 units,
+4.1%; the quarters 1-2 spread is unchanged
(`%TEMP%/nba_live_build/conflicts_hourly.py`). On record 7.3's bets it declined
66 of 3,181, worth +15.98 units.

**Published** to the NBA live Discord channel only, and push, by the loop after
each bet and every 5 minutes while one is standing. The channel is
`DISCORD_CHANNEL_LIVE_NBA` (a channel id; the bot makes a webhook in it) or
`DISCORD_WEBHOOK_LIVE_NBA`. NBA live picks never fall back to the shared live
channel or the NBA pre-game channel (`config.DISCORD_LIVE_CHANNEL_REQUIRED`).
With neither variable set, the loop decides nothing, logs one warning and exits
3 while a game is in progress, so the job reads failed and the failure alerter
fires. A pick is announced only while its game is in progress
(`config.LIVE_ANNOUNCE_WHILE_IN_PROGRESS`): once the game's final score is in
`games`, an unposted NBA live pick is not posted late.

**Watched.** The loop beats `job_heartbeats` every 5 minutes while a slate runs
(11am to 11:30pm ET in `ACTIVE_HOURS_ET`). The next morning `system_health`'s
`nba_live_outputs` check reads the slate (`tracking/nba_live_health.py`). It
reads STALE when a final game has no `nba_live_decisions` row, or when a fetch
moment that needed a fetch has no Odds API call from the loop in
`api_call_log`. A moment needed one when a game was in its first 100 minutes
with a rule not yet decided. A game whose first 100 minutes ended before the
loop's first supervisor tick, and a fetch moment that opened before that tick,
are not scored. That tick is 2026-11-05 11:00 ET: #1180 / #1184 reached
production that morning inside the cron's 3am-11am ET gap, and the 2026-11-04
finals had already ended. A later slate with a missing row or a missing call
still reads STALE.

Settled by the generic game path
(`config.LIVE_MODELS`): the spread against `scored_line`, the HOME number. No
closing-line value in play.

**NBA rows the live pulls receive after the tip are stored `in_play`**
(2026-11-04). The refresh pass keeps receiving a game once it starts, and
stored those rows `open`: on the 15 games of 2026-11-02, 5,735 of 16,508 `open`
full-game NBA rows (35%) were stamped after the listed tip.
`odds_ingestor.LIVE_PULL_IN_PLAY_SPORTS` relabels them at write time. Rows
already stored are left as they are; the repair is
`odds_ingestor.relabel_in_play('NBA', since)`, a production write, not run.
What a reader sees change: the pre-game latest-line views exclude `in_play`
rows, so for an NBA game under way they stop at the last pre-tip quote, and the
refresh pass's in-play prices move to `v_latest_inplay_odds_all_books`, the view
the app reads a live pick's price from.

Build and parity: `scripts/build_nba_live_ig2_artifact.py` (`--build`,
`--parity-held`, `--parity-live27`; after the merge `--store` and
`--register`). On record 7.3's own table the serving decision reproduces every
bet it graded, 1,753 / 768 / 1,210 over 2020-21 to 2025-26, the same book,
side, number and price, both over the whole table and one game at a time
through the loop's own path (`decide`).

## No 10-game wait on the shooting-luck totals (mike, 2026-11-02)

mike: *"Yes, remove it"*, after the same wait came off the NCAAB totals model
(*"we do not need to wait 10 games, I never approved that"*). `nba_total_luck`,
`nba_team_total_luck` and `nba_first_half_total_luck` now price a game once each
team has played one game this season (`models/nba_total_luck.LIVE_MIN_GAMES`). A
team with no game has no number to compute, so about 16 games a season are still
declined `early_season`, on opening night and just after.

The labs and the replays keep the 10-game population (`MIN_GAMES`, passed to
`decide` by each `scripts/nba_*_total_luck_replay.py`), so they still prove the
live code against what the lab graded.

**The replay** (2026-11-02): each model's live `decide` on the research cache of
2026-10-29, at the lab's own decision times, graded by the harness that graded
the evidence, bootstrap by day. "Kept out" is the games the wait used to skip.

| Model | Seasons | Games | Bets | Units | ROI | 95% interval |
|---|---|---|---|---|---|---|
| `nba_total_luck` | 2021-22..2025-26 | **no wait (live)** | **719** | **+55.25** | **+7.07%** | **+0.4..+13.7** |
| | | 10-game wait | 508 | +55.56 | +10.05% | +1.9..+18.3 |
| | | kept out | 211 | -0.31 | -0.14% | -12.3..+11.1 |
| `nba_team_total_luck` | 2023-24..2025-26 | **no wait (live)** | **429** | **+68.73** | **+14.33%** | **+4.8..+23.3** |
| | | 10-game wait | 349 | +64.72 | +16.58% | +6.4..+26.4 |
| | | kept out | 80 | +4.01 | +4.50% | -18.4..+25.1 |
| `nba_first_half_total_luck` | 2023-24..2025-26 | **no wait (live)** | **745** | **+51.44** | **+6.38%** | **-0.5..+13.4** |
| | | 10-game wait | 595 | +51.49 | +8.01% | +0.4..+15.4 |
| | | kept out | 150 | -0.06 | -0.03% | -14.6..+14.0 |

**What it means.** The kept-out games add volume at about break-even: units are
flat to slightly up, and ROI falls. They are not evidence of an edge. No band of
games played is consistently better; each is under 60 bets per model and the
intervals are wide. The team-total model's kept-out count is thin because the
cache has almost no October 2023 team-total prices (3 bets that season).

**Sizing runs ahead of the evidence on these bets.** `model_probability` adds each
model's uplift, measured on games with both teams on 10+. The full-game kept-out
bets won 109 of 211 (0.517) where that uplift assumes about 0.57, so tenth-Kelly
stakes them as if they had the later games' edge.

**The earlier research said wait.** The fifth search (`docs/nba_models_2026.md`
section 9.4, F8) tested an early start with last season blended in, and closed it
on too few bets to tell. This replay is the plain season-to-date number the live
models use, not that blend.

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
  total under is `nba_team_total_luck`, live. The first-half over is
  `nba_first_half_total_luck`, live since mike's call of 2026-10-30; its known
  weaknesses are that its first-half and second-half results point opposite ways,
  its pass needs every deciding book, and over half its bets are games
  `nba_total_luck` already bets (§8.4). The market-anchored model (the NHL recipe)
  found nothing.
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
`models.nba_total_luck.regular_season`). **The play-in, the playoffs and the Cup
final: `nba_prop_market` only.** A pre-registered search graded both prop models
on those 272 games of 2023-24..2025-26 (`docs/nba_search_postseason.md`, branch
`nba-searches-graded`). The rule passed, and none of the projection model's six
cells did. The totals models were graded on the regular season only, and stay
there (the Cup final never counts). How these games arrive and what watches them
is in the next section; the numbers are in `docs/thresholds.md`.

**How a play-in, playoff or Cup final game arrives.** Picks and prices both need a
`games` row (foreign keys), so that row is the route. Three things can write it:

- **The odds feed**, on every NBA event it quotes, normally days ahead. It has written
  NBA rows since 2026-06-17, after the 2026 Finals, so this is **not yet observed** for
  these games. The same sport key's historical event list carried all 272.
- **The schedule refresh, on the game's own day** (`data/ingestors/nba_schedule_refresh.py`,
  6am ET). Never sooner, so a series that ends early leaves no row for a game nobody
  plays. It also lists the game in `nba_schedule` once ESPN sets its teams, and types it:
  ESPN's type 3 playoff, 5 play-in, and a type-2 game is the Cup final when its note says
  "Championship" or when it falls on the date the league's own placeholder gives the final.
  That matters: a listed `regular` row would pass all four other NBA models' gates.
- **Nothing else.** The results step adds a regular-season game only.

The rule takes a game the schedule does not list, on a day only these games fall on: a day
the schedule gives one of them, or after the season's last regular-season day and by June
30. So a failed refresh does not lose it. **A second row for one real game is refused.** A bet
settles on its own id and ESPN's final lands on ESPN's, so a bet on any other row can stay open
for good, and one bet a game counts by id. On a day only these games fall on, an unlisted row is
refused when the schedule lists those two teams, either way round, within two days under another id
with no final (`models.nba_total_luck.listed_twin`; the feed wrote four such rows in the 2026 WNBA
playoffs). **That does not hold on a regular-season day:** an unlisted row there beside a listed regular
game of the same two teams is priced as a regular-season game, as it always has been, and could hold a bet
that strands. The alert names it if it does (`docs/followups.md`).
If the feed has the two teams the other way round from ESPN on the same date (a neutral court)
and ESPN's id has no row, the refresh leaves it that way and the results step scores the feed's
row with each team's own score (`nba_results_ingestor.match_game`).

**Who reads them.** `slate` and everything built on it refuse them: the three total models'
cards and windows, the projection model, the ten-game gates, the ratings. Only
`scripts/nba_prop_market_card.rule_slate` adds them, and `tests/test_nba_postseason_gate.py`
fails on any other reader. That holds for a correctly dated row, and for a row the feed dated onto a
regular-season day once the schedule lists the real game with its teams
(`models.nba_total_luck.postseason_twin`). **Before the schedule lists it, such a row reaches all four other
models and can be bet by them** (`docs/followups.md`). The Cup final's slot has no teams until ESPN sets them.
Results, settlement, closing-line capture and publishing read
`picks` and `games` with no game-type filter, so these bets settle, post and count like any
other, with one exception: a bet whose only start is the odds feed's records no closing-line value
(the tip, below, and `docs/clv.md`). Prices are `player_prop_odds`' `open` rows, the same as any game; never
`nba_postseason_prop_odds`, which is research only.

**What watches them** (`tracking/failure_alerter.py`, all warnings, one key per game):
a game the rule did not decide, regular-season games included (it decided all 92 of
2026-10-20..11-01), `undecided:nba_prop_market:<game>`. A listed game counts only if the
refresh confirmed it on its own date, so an unplayed Game 6 is not named. A refused row,
`refused:nba_prop_market:<game>`. A refused row is one neither read keeps: a row the regular
slate prices (above) is not called refused. An open NBA prop bet of either model over 12 hours past
tip on a game with no final, `stranded:nba_prop:<game>`, which takes a person, one of two ways:

- **The game was played and its final landed on another row.** Do not void: the bet has a real result,
  and section 1c keeps VOID for a row the model should never have produced. Write the final and the box
  lines onto the bet's row, and the next settle pass grades it. There is no command for this yet, as
  there is for NCAAF (`cfbd_ingestor.mirror_stored_finals`; `docs/followups.md`).
- **The game was postponed or cancelled.** The bet has no result, so it settles NO_ACTION:
  `scripts/void_picks.py --game-id <game>`. A bet already posted also needs `--allow-posted` and a
  `config.RECORD_EXCLUSIONS` entry naming who asked. This is by hand, and not automatic as
  `_void_postponed_mlb_picks` is, because `nba_schedule.status_text` has never held a postponed value (0
  rows, all seasons, 2026-11-02), so there is no real row to build or test that trigger against.

**The tip.** Every one of these schedule rows is ESPN's, and ESPN alone sets its tip, where an
NBA.com row needs the feed to second a move. So when ESPN's start sits over 30 minutes before the feed's, it is
read as ESPN's error and the decision window and the closing snapshot are measured from the feed's start. Measuring from
ESPN's would bet hours early, or lose the game when Pinnacle has no price yet. The feed's start ran 2.3 to 20.2 minutes
after the league's on all 107 games it wrote 2026-10-20..11-02 and never before it, while ESPN has been five hours
early (`models.nba_prop_market.postseason_tip`). **If the feed is ever the stale one, this writes the bet after the real
tip**, so the game is named, `start_gap:nba_prop_market:<game>`, and both starts go to the ledger. With no ESPN tip (the Cup
final's slot has none today) the tip is the feed's too, so the first look lands nearer the real tip than anything graded. In
both cases the ledger says `tip_source=feed`, and the bet's closing-line value stays empty, because the feed's start is no
bound for a close. A feed row with home and away the other way round from ESPN reads ESPN's row for its tip.

**Season-long numbers.** Once these games land in `games` and `nba_player_game_log`, the season
stats functions, the team board and the first-quarter card read them as season games. On those
screens that is display only (`docs/followups.md`).

**One regular-season input does move: the Cup final's `games` row changes the two finalists' rest in
`nba_prop_projection` for their next game.** That is about two teams a season. `models.nba_props.team_games`
counts the final once the schedule lists it, as it did before this work, so any writer's row does this. Knicks at
Miami the day after a 12-11 final: rest 4 becomes 1, back-to-back 0 becomes 1, games in four days 1 becomes 2,
road trip 2 becomes 3, and the opponent reads the first two through `opp_rest` and `opp_b2b`. The new
numbers are true, since the finalists did play, but they are not what was graded: none of the Cup finals of
2023-24..2025-26 has a `games` row. Player and team rates do not move (`models.nba_prop_projection.box_from_log` keeps regular-season
games) and neither do the total models (`load_season` filters on the regular season). Play-in and playoff rows
are not in `team_games`. The code is unchanged. Whether the final should count toward rest is mike's call.

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
| `nba_team_stats` | season-to-date team ratings (Off/Def/Net Rtg, pace, eFG%, TOV%) for the app's Teams board and team page; no live model reads it | `nba_team_stats_from_box` (summed `nba_player_game_log` + `games` finals) for 2026-27, from 2026-11-03; `nba_stats_ingestor` (stats.nba.com) before that, and its row wins a shared key | worker, the 6am run (`nba-team-stats-box`, before `refresh-team-board`) / this machine. Box-built ratings run ~0.8 high (no team turnovers in player boxes); Net Rtg correlates 0.9999 with stats.nba.com over 2025-26 |
| `nba_schedule` | NBA.com schedule: arenas, neutral sites, NBA Cup, national TV, OT; every game type | `nba_schedule_ingestor` (the season's load) / `nba_schedule_refresh` (ESPN, daily) | this machine (stats.nba.com blocks datacenter IPs) / worker, the 6am run |
| `nba_player_game_adv` | starters, exact minutes, +/-, fouls, usage, possessions, DNP reasons | `nba_box_enrich` (sportsdataverse bulk files + stats.nba.com) | this machine, 2018-19 → 2025-26 |
| `nba_game_inactives`, `nba_game_officials` | inactive lists, referee crews | `nba_box_enrich` | this machine |
| `nba_injury_report` | the official league injury report, every PDF since 2018-12-17, stamped with its printed time | `nba_injury_report` | this machine; `--today` exists, not wired on the worker |
| `nba_period_scores` | points by quarter (settles half/quarter bets; feeds the team page's first-quarter card) | `nba_period_scores` (ESPN scoreboard) | worker, the 6am run (`nba-quarters`, from 2026-10-28) / either |
| `nba_team_q1_games` | one row per team per regular-season game: first-quarter points for and against (from `nba_period_scores`), possessions for and against (from `nba_stints` period 1; NULL when the stints' 1Q points miss the quarter score). The app reads a capped newest-first slice for Last 5 / Last 10. The Season row and the ranks both read `v_nba_team_q1_season` (full season, per venue) | `data/ingestors/nba_team_q1.py` | worker, the 6am run (`nba-quarters`) |
| `nba_first_basket_games`, `nba_first_basket_players` | the Stats tab's 1st Basket board (Matt, 2026-11-08; stats only, no odds bought, no model). One row per team-game: won the tip (the opening Jumpball's possession side), the jumper, scored first (any score, free throws included), the kind of that score, the team's first field-goal attempt and whether it went in. One row per player-game he played: took / made the team's first shot, scored the game's / team's first basket, jumped / won the tip. Regular season, this season and last. The app reads `v_nba_first_basket_team_season` and `v_nba_first_basket_player_season` | `data/ingestors/nba_first_basket.py`, from `nba_pbp` / `nba_pbp_box` / `nba_pbp_games` | worker, the 6am run (`nba-quarters`, after the play-by-play fill) |
| `odds` (`source='odds_api_historical'`) | game lines 2020-21 → 2025-26, 9 fetches a game date | `nba_odds_history --lines` | one-off purchase |
| `player_prop_odds` | props 2023-24 → 2025-26 (one snapshot at tip-60); live every refresh pass and every window-job tick with a game near | `nba_odds_history --props`; `prop_odds_ingestor` | purchase; worker |
| `nba_prop_market_decisions` | one row per game the NBA prop card decided: when, on which fetch, quotes seen, bets written | `scripts/nba_prop_market_card.py` | worker |
| `nba_prop_projection_decisions` | the same, for `nba_prop_projection`, with the projection it priced | `scripts/nba_prop_projection_card.py` | worker |
| `nba_total_luck_decisions` | one row per game the totals card decided, bet or not: the fetch, its lead, the gap and the reason. Since 2026-11-10 each of the three game-total cards also writes a NONE row to `picks` for every game it SCORED and did not bet (below the cut, refused by a floor, dropped by the one-total-a-game door), so the app's All tab shows it (Matt; `scripts/nba_none_rows.py`). Market-fair probability, no uplift, no stake; not settled | `scripts/nba_total_luck_card.py` | worker |
| `nba_first_half_total_luck_decisions` | one row per game the first-half card decided, bet or not: the fetch, its lead, the full-game gap, the best over offer (book, line, price, fair and written probability, fair line), each book's last-update age, and the reason | `scripts/nba_first_half_total_luck_card.py` | worker |
| `nba_first_half_total_fetches` | one row per first-half call (the event list, and each game's call, `open` or `close`): when, ok or failed, rows stored, main rows, the books, each book's last-update age, the feed's `x-requests-last` | `data/ingestors/nba_first_half_odds.py` | worker |
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
| `nba-props` | right after `nba-prop-odds`; also in the window job (the old names `nba-prop-market` and `nba-prop-projection` run the same step) | BOTH NBA prop cards in one look: games tipping in 45-57 minutes and not yet decided; every qualifying proposition of both pooled, then one bet a game across both models and `MAX_NBA_PROP_BETS_PER_NIGHT` (6) a night, ranked by each bet's EV percentile within its own model, the night's written bets counted (`scripts/nba_props_card.py`); a decision row per game per model; a diagnostic line every look |
| `nba-prop-project` | the window job, about 65 minutes before tip | an ESPN injury pull, then the frame over every box line since 2018-19, stored in `nba_prop_projections`; a game 45-62 minutes out with none is projected at once |
| `nba-total-luck` | only in the totals window job, right after its fetch, under a 180-second limit (NOT in the refresh pass) | the totals card: decides a regular-season game on a fetch that landed 60-66 minutes before tip and is at most 5 minutes old; a decision row per game; the over when the gap is 3+ |
| `nba-team-total-luck` | only in the totals window job, right after its team-total fetch, under a 180-second limit | the home team-total card: decides a regular-season game on its own team-total fetch that landed 45-66 minutes before tip and is at most 5 minutes old; a decision row per game; the home team total under when the home team's part of the gap is 2+ toward the under |
| `nba-prop-close` | after the card; also in the window job | a `close` prop snapshot 12-25 minutes before tip for every game holding a bet (CLV; `NBA_PROP_CLOSE_*` in config) |
| window job `nba_prop_window` | every 5 minutes, 24x7 (`scheduler.run_nba_prop_window`) | props for exactly the games 40-62 minutes from tip that either NBA prop model has not decided, then both cards, then any close that is due, then publish, then the projections due; no API call when nothing is near |
| window job `nba_total_luck_window` | every minute, 24x7 (`scheduler.run_nba_total_luck_window`; one planning read for all three game total models, `scripts/nba_pregame_window.py`) | The three models side by side, each on its own steps in order (`scheduler._run_models_side_by_side`), so a tick lasts as long as its slowest model and one model's slow card moves no other model's fetch. `nba_total_luck`, when an undecided game is 61-66 minutes from tip: the NBA board (the refresh pass's own NBA odds fetch, 90-second limit), then `nba-total-luck`. `nba_team_total_luck`, when an undecided game is 45-56 minutes from tip: one `team_totals` call per due game (`scripts/nba_team_total_luck_window.py --fetch`, 90-second limit), then `nba-team-total-luck`; and for each game holding its bet, the closing team totals 12-25 minutes before tip (`--close`, 90-second limit, filed `close`, for closing-line value). `nba_first_half_total_luck`, the same three steps on its own `totals_h1` call (`scripts/nba_first_half_total_luck_window.py`); no step reads another model's outcome. Then one publish, when all of them are done. No API call when nothing is due. Six ticks fit the full-game window and twelve the team-total one, so one skipped tick loses nothing; with every card killed at its limit each model still gets three attempts a window (56, 52, 48 minutes out). A game that tips with no decision from one of the three is reported by name per model (`tracking/failure_alerter`, `scripts/nba_pregame_window.undecided_games`), as a critical alert, for the next 24 hours. One job for all three, not three: every job opens a database connection each tick for its heartbeat. On the refresh pass a skipped tick lost the game: 27 of 504 evening ticks never started over 2026-10-03..16 |
| `nba-schedule` | the 6am run, before `nba-results` | ESPN's schedule for this month and the next eight (one call a month) → `nba_schedule`: games it lacks under an `espn:` key (the NBA Cup week and knockout games once set, play-in, playoffs), postponements, and a moved tip only when the odds feed shows the same start. A play-in, playoff or Cup final game also gets a `games` row, on its own day only. Fail-open: a month ESPN does not answer is left as stored; the step goes red and the health check `nba_schedule_refresh` goes STALE after 36 hours with no row confirmed |
| `nba-results` | every pass, before settle | ESPN finals → `games`, every box line → `nba_player_game_log` |
| `nba-quarters` | the 6am run, after view migrations | for the current season: quarter scores for every finished game lacking them (`nba_period_scores`), play-by-play and possessions for every game lacking them (`nba_pbp.fill_gaps`, ESPN summary; at most 100 games a run, oldest first, the rest on the next run), then `nba_team_q1_games` rebuilt for this season and the last. One game's summary failing does not drop the games already built. Free ESPN endpoints. Added 2026-10-28: before it, the 2026-27 season had 0 of 56 finished games with quarter scores and no play-by-play after 2026-06-13 |
| box repair (by hand) | from a residential machine, when the totals card logs `box_missing` or `box_mismatch` | `python -m data.ingestors.nba_stats_ingestor --repair-boxes 2027` replaces each game of the season whose box is missing or does not add up to its final score with NBA.com's, one game per transaction, and writes a game only when NBA.com's box adds up. Not `--game-log-date`: it loads every game of the date and doubles any player ESPN stored under a fallback id |
| `settle` | every pass | props via `_settle_prop_picks` (`FROM_PROP_MARKET`, `_NBA_MARKET_STAT`); the two totals models through `paper_tracker._RULE_MODEL_MARKETS`: `nba_total_luck` on the full-game total, `nba_team_total_luck` on the home team's own final score (overtime included; a push when equal), `nba_first_half_total_luck` on Q1 + Q2 from `nba_period_scores` (a push when equal), which the settle step fetches for itself when a pending pick's game has a final and no row, because the 6am run's `nba-quarters` step runs after its settle; a game whose quarters fail the check stays pending, and each settle pass asks ESPN again and replaces its rows only with rows that add up to the stored final (`nba_period_scores.ensure_first_half_period_scores`). A BET with a final and no result is reported at any age (`settlement_lag`, then `settlement_stranded`) |

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

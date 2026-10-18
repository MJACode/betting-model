# NBA models, 2026-27 rebuild — pre-registered bars, the market grid, the results

Asked for by mike on 2026-10-15: retire every previous NBA model, look at every
game and prop market, use every data source we hold or can get, and carry over
what the other sports taught us — schedule (back-to-backs, road trips) named
explicitly.

**This file was written BEFORE any NBA model was graded against a price.** The
bars in §1 are fixed. A model that misses one does not ship, and the grid row
says why. Nothing here is re-thresholded after the fact; a later change to a
bar gets its own dated line and reason.

---

## 1. Pre-registered bars (fixed 2026-10-15, before the first grid)

A candidate ships LIVE (CLAUDE.md §2: every model is live real money) only if
every line holds on the seasons it was NOT fit on:

1. **Graded at real prices.** The deciding price is the best bettable book at
   the same line (`config.BEST_LINE_BOOKMAKERS`); DraftKings alone is reported
   beside it. Pinnacle and Bovada are never a deciding price. No -110 fallback.
2. **Units, one unit to win** (`tracking/discord_notifier.stake_for`: risk =
   1/(decimal−1), capped at 3u). ROI is units won over units risked.
3. **Every scored candidate is graded, not just bets** (CLAUDE.md §7): the
   grid is built over every priced proposition, and a cut is a neighbourhood.
4. **Walk-forward.** Fit on seasons before S, grade S. Props: grade 2023-24,
   2024-25, 2025-26. Game lines: grade 2021-22 through 2025-26. The cut is
   chosen on the earlier graded seasons and **confirmed on 2025-26**, the
   newest season, which is never used to choose anything.
5. **Positive in every graded season** with ≥ 30 bets.
6. **≥ 200 bets at the chosen cut, whole-day bootstrap 90% CI above zero**
   (4,000 resamples, seed 7 — the NHL derivative-totals gate).
7. **Plateau, not a peak:** the cut's neighbours (±1 step on each axis) are
   positive too.
8. **Both date halves positive** (early/late split within the graded window).
9. **Beats the blind baseline on the same side.** If the model bets one side
   more than 70% of the time, it must beat a blind bet on that side at the
   same price and the same cut population — otherwise it is the market lean,
   not the model, and the lean is reported as the finding.
10. **Placebo:** model probabilities shuffled within each date must lose the
    edge.
11. **CLV where a later price exists:** the median bet beats the no-vig sharp
    close (Pinnacle when it quotes the market; the soft-book consensus
    otherwise).
12. **No look-ahead.** Every input is known at the decision timestamp: odds
    bounded `snapshot_at <= decision time < commence_time`; injury status from
    the official report filed before the decision; schedule inputs from the
    schedule (known in advance), never from a result after the opener posted.
13. **Name integrity:** two players sharing a name never share a price
    (the NHL namesake defect, +89.8u phantom).

**Kill criterion:** a market family with no cut passing 4-11 on the graded
seasons is closed for 2026-27 with its grid recorded here. It is not
re-thresholded to find a pass.

---

## 2. Data used (all in Supabase)

| Data | Table | Coverage | How it got there |
|---|---|---|---|
| Games, scores, tip-off, neutral site, OT | `games`, `nba_schedule` | 2018-19 → 2026-27 schedule | nba_api `leaguegamelog` + `scheduleleaguev2` (`data/ingestors/nba_schedule_ingestor.py`) |
| Player box scores | `nba_player_game_log` | 2018-19 → 2025-26 | nba_api |
| Box-score detail (starters, exact minutes, +/-, fouls, inactives, officials) | `nba_player_game_adv`, `nba_game_inactives`, `nba_game_officials` | 2018-19 → 2025-26 | `data/ingestors/nba_box_enrich.py` |
| Official injury report, timestamped | `nba_injury_report` | 2018-12 → 2026-04 | `data/ingestors/nba_injury_report.py` |
| Game lines h2h/spreads/totals, 10 books incl. Pinnacle | `odds` (`source='odds_api_historical'`) | 2020-21 → 2025-26, 9 snapshots per game date | `data/ingestors/nba_odds_history.py --lines` |
| Player props, 14 markets, 10 books | `player_prop_odds` | 2023-24 → 2025-26, one snapshot 60 min before each tip | `data/ingestors/nba_odds_history.py --props` |
| First half / first quarter / team totals | `odds` (`source='odds_api_nba_derivative_history'`) | 2024-25 → 2025-26, one snapshot 60 min before each tip | `data/ingestors/nba_odds_history.py --derivatives` |
| Points by quarter (settles half / quarter bets) | `nba_period_scores` | 2018-19 → 2025-26 | `data/ingestors/nba_period_scores.py` (ESPN scoreboard) |

**Measured coverage, 2026-10-15** (read from the research cache, `scripts/nba_research_cache.py`):

- Game lines: 7,684 fetches, 1,625,824 rows kept; every regular-season game priced — 1,080 games in 2020-21, 1,230 in each season since.
- Props: 1,230 games in each of 2023-24, 2024-25 and 2025-26 (894,575 / 896,610 / 943,774 rows). Points, rebounds, assists, threes, PRA, the three pairs, blocks, steals and the double-double are on 3,680-3,690 of 3,690 games; triple-double 3,554, blocks+steals 3,353, turnovers 2,414.
- Half / quarter / team totals: 2,459-2,460 of 2,460 games in each market.
- Cost: ~900k credits in total (props 499,077; derivatives 172,427; game lines the rest), balance 2,584,357 at 2026-10-16 01:34Z, the floor at 2,200,000 never reached.

## 3. The market grid

Filled in §4 as each row is graded. An empty cell is a to-do.

| Market | Settles on | Inputs | Price source | Blind baseline | Best candidate | Verdict |
|---|---|---|---|---|---|---|
| Moneyline | `games` scores | | `odds` h2h | | | |
| Spread | `games` scores | | `odds` spreads | | | |
| Total | `games` scores (OT counts) | | `odds` totals | | | |
| Points | box `points` | | `player_prop_odds` | | | |
| Rebounds | box `rebounds` | | | | | |
| Assists | box `assists` | | | | | |
| Threes | box `fg3_made` | | | | | |
| Pts+Reb+Ast | sum | | | | | |
| Pts+Reb / Pts+Ast / Reb+Ast | sum | | | | | |
| Blocks / Steals / Blocks+Steals | box | | | | | |
| Turnovers | box `turnovers` | | | | | |
| Double-double / Triple-double | computed | | | | | |
| 1st half / 1st quarter / team totals | not bought yet | | | | | |

## 4. Results (graded 2026-10-15/16)

Every number below was produced by a researcher agent and then rebuilt from the
raw cache by three independent verifiers (timing, prices/grading, statistics).
Full reports, bet lists and code: `C:/Users/micha/AppData/Local/Temp/nba_rebuild/results/`
and `verify/` on the build machine; the lab scripts are committed under `scripts/nba_*_lab.py`.

### 4.1 Game markets — closed for 2026-27

Seasons 2020-21 → 2025-26, 692 + 286 cells (`scripts/nba_game_market_lab.py`, `scripts/nba_game_model_lab.py`).

- **Schedule is in the line.** At Pinnacle's close, holding team strength fixed, a home team
  on the second night of a back-to-back is priced −1.71 points and actually did −2.04
  (residual −0.34, 90% CI −1.30..+0.63); a visitor on one: priced +1.77, did +1.82. Of 22
  schedule residuals (rest, 3-in-4, road-trip game N, travel miles, time zones, altitude,
  early tips …), 2 have an interval clear of zero against ~2.2 expected by chance. Adding the
  whole schedule group to Pinnacle's price changes log loss by −0.08 / −0.00 / +0.16
  thousandths (moneyline / spread / total), every interval covering zero.
- **The published schedule spots do not beat the modern line** (spread, 3pm ET, best price):
  home on a back-to-back vs a rested visitor +0.7% on 753; Denver/Utah hosting a tired
  visitor −0.5% on 138; long-travel back-to-backs +1.1% on 342.
- **Availability is priced.** The 3pm line moves 2.26 points per 48 player-minutes ruled
  out; results moved 2.21 (residual +0.05, CI −0.49..+0.59). Referee crews add nothing.
- **Sharp-vs-soft (the NHL totals rule) does not transfer:** NBA soft books move the number,
  not the price — 274 same-number total disagreements in five seasons, −11%.
- **The one moneyline cell that passed on paper** (away side, Pinnacle no-vig vs best price,
  EV ≥ 0.02: 1,550 bets, +7.1%) was refuted by all three verifiers: 57% of its units came
  from snapshots 4-11 minutes before tip; 26 winning bets were broken William Hill quotes
  (without them the CI crosses zero); it fails Benjamini-Hochberg over the cells searched.
- Blind baselines all lose (−1.1% to −6.7%). Early-season unders lose (−7.6%).

### 4.2 First half / first quarter / team totals — closed for 2026-27

2024-25 and 2025-26, 2,772 cells (`scripts/nba_derivative_lab.py`). Every family's
2024-25-chosen cell fails bar 6. Nearest: home team total, same number, EV ≥ 0.01 —
182 bets, +6.6%, CI −6.3..+19.1. The halftime total is not full/2 in practice (books move
each game ~3 points off it, correctly). Ties void two-way 1H/1Q moneylines at every book.

### 4.3 Player props — one rule ships

**Over-lean, measured:** blind overs lose 7.3% and blind unders 2.2% across 505,932
propositions at the best bettable price — the same lean as NFL, NHL and WNBA.

**Ships: same-line unders against Pinnacle** (`scripts/nba_prop_market_lab.py`).
Under at the best bettable book whose line equals Pinnacle's in the same snapshot, when
Pinnacle's proportional no-vig under makes that price +EV (EV ≥ 0.00), one bet per
(game, player, market):

| | bets | ROI | 90% CI |
|---|---|---|---|
| all three seasons | 25,204 | +2.85% (+771.4 u) | +1.75..+3.96 |
| 2023-24 / 2024-25 / 2025-26 | 8,766 / 8,595 / 7,843 | +4.1 / +2.2 / +2.1% | 2025-26 alone +0.34..+3.85 |
| without Hard Rock | 19,847 | +2.29% | +1.12..+3.46 |
| DraftKings as the only book | 8,209 | +2.12% | +0.32..+3.81 |
| without double-double / triple-double | 24,513 | +2.90% | (positive every season) |

Neighbouring floors +3.1% (0.01) and +2.1% (−0.01); both date halves positive (+3.5 / +2.2);
placebo (Pinnacle shuffled within date and market) mean −1.5%, 95th percentile −1.0%; blind
under on the same 141,087 propositions −1.5%. It survives Bonferroni and Benjamini-Hochberg
over all 1,518 cells searched (p ≈ 9e-6). Every one of the 25,204 bets was regraded from raw
quotes and box scores with zero errors. It was the hypothesis stated before the grid ran (the
cross-sport over-lean plus a sharp reference).

Caveats the verifiers carried, all disclosed rather than hidden:
- **Expect about +2% live, not +2.9%** — the top cell of a search carries winner's curse;
  2025-26 (never used to choose anything) is +2.1%.
- **Bar 11 (closing-line value) could not be measured** — one archived snapshot per game.
  The live card stores a closing snapshot for every bet from night one.
- **Stale soft quotes cannot be ruled out** — the archive stores no per-book update time.
  Where the bet book agrees with the other soft books within half a point, +3.9% on 1,997.
- **Hard Rock** carries ~37% of the units, decaying (+16 / +8 / +3% by season); the rule
  clears without it.

**What ships live (2026-10-16; mike: *"maximize units won"*).** Every qualifying
proposition, one bet per (game, player, market) at the best bettable price, with the
−200 floor and no double/triple-double — no game or night cap. That is the population
graded above: 24,572 bets, +781.3 units, +2.96%, 90% CI +1.85..+4.05, every season
positive (+393.6 / +220.5 / +167.1 units), about +260 units a season, about 50 bets a
night (median 50, most 119). The caps it shipped with on 10-15 (one a game, four a
night) made +94.9 units over the same three seasons. Prices it lays (the same bet
list): min −200, 5th percentile −143, median −105, 95th +128, max +230; 38% of bets
are plus money, 3.5% are −150 or shorter (`C:/Users/micha/AppData/Local/Temp/nba_rebuild/uncapped_stats.py`).

Each game is decided ONCE, as the backtest looked at it once: the first look inside
the 45-57 minute window whose newest fetch holds Pinnacle is the decision, bets or
none, written to `nba_prop_market_decisions`; a game with a row there is never looked
at again. A five-minute job (`scheduler.run_nba_prop_window`) fetches props for the
games 40-62 minutes from tip, so every tip time gets a look in its window.

**Decision timing, measured against the graded snapshots.** The archive's snapshot
sat 54.4 minutes before tip for 87% of bets and 64.4 for 13%. ROI by that lead, same
population: 50-60 minutes 21,252 bets +2.95% (CI +1.77..+4.10); 60-70 minutes 3,146
bets +2.97% (CI +0.09..+5.85; 2025-26 alone +0.25%); nothing was graded at 65-70.
With a look every five minutes and tips on the hour or half hour, the first look
inside 45-70 lands about 70 minutes before tip (`C:/Users/micha/AppData/Local/Temp/nba_rebuild/lead_roi.py`).
The window shipped as 45-70 on 2026-10-16 and was narrowed to **45-57** the same day,
before any NBA game, after the projection model's timing verifier measured it: the first
look now lands 55 minutes before any tip on a five-minute mark, where 87% of the graded
bets were decided.

**Not shipped** (each refuted or not significant once graded on the season it was not chosen
on, or after counting the 1,518 cells searched): the soft-book-consensus rule where Pinnacle
is absent (+1.8%, fails with Hard Rock or FanDuel removed, DraftKings alone −1.05%); the
line-gap rule (+2.2%, 2025-26 alone −1.82..+4.21, profit from 64-minute snapshots only);
every single-market carve-out (rebounds, assists, PRA, points, threes, steals, reb+ast).
Every over rule fails. Double-double and triple-double fail.

### 4.4 Player props — projection models (the NHL recipe)

`models/nba_props.py`, `scripts/nba_prop_model_lab.py`. Minutes model, then per-minute
rates, negative binomial, every input as of the prop snapshot.

- Beats season average, last ten and the weighted mean in 13 of 14 markets before any price;
  triple-double fails and is closed.
- Does **not** beat the books' own price on Brier in points, rebounds, assists and the combos.
- **The teammate-absence hypothesis failed:** absences improve the count fit the most of any
  feature group, but add nothing at the price — books have priced absences an hour before tip.
- Best card: pooled unders, one a game — 3,620 bets, +4.86%, CI +1.8..+7.8, every season
  positive (+42.0 / +25.1 / +79.3 u), DraftKings alone +4.83%. Not claimed as a pass by its
  researcher (bar 11 unmeasurable; variants of the model pick 50-76% of the same bets and
  return +2.9% to +5.0%). Strongest where Pinnacle does not quote: blocks unders +5.78% on
  7,878 (DraftKings alone +5.54%, every season positive). See §4.5 for its verification.

### 4.5 The projection model on the worker's inputs only

The live worker has the ESPN box line (whole minutes, starter flag, counting stats), the
schedule, the props, and an injury table with two statuses (Out, Day-To-Day) — no usage, no
fouls, no Probable, no official report. The model was re-fitted on exactly those inputs
(`scripts/nba_prop_model_verify.py`, the "worker re-fit"): same frame code, the official
report collapsed to the two ESPN statuses, a pre-game roster inferred from the log. The
pooled one-under-a-game card on it: 3,630 bets, +5.57%, CI +2.45..+8.62, every season
positive. That card was the starting point, not what ships: §5 calibrates it and bets
every qualifying proposition.

## 5. The projection model that ships — `nba_prop_projection` (2026-10-16, mike)

mike, 2026-10-16: *"build the projection model"*, *"maximize units won"*. Code:
`models/nba_prop_projection.py` (the rule), `scripts/nba_prop_projection_card.py` (the
card), `scripts/nba_prop_projection_train.py` (the artifact); the search is
`scripts/nba_prop_projection_lab.py`.

**What it is.** The worker re-fit's means (minutes × per-minute rate) through a
negative-binomial width fitted on the season before, then a per-market Platt map,
`logit P(over) = a + b·logit(p_model)`, fitted on main-line (claimed, outcome) pairs of
earlier seasons only. It bets every proposition whose calibrated EV at the best bettable
price clears its market's floor, at the consensus main line only (DraftKings' two-sided
line, else the line most bettable books hang), never a proposition `nba_prop_market`
holds.

**The search.** 546 cells: 13 markets × under / over / both × 14 calibrated-EV floors. Per
market, the cell with the most units on 2023-24 + 2024-25 among cells positive in both;
then bars 4–10 on all three seasons. Seven cells entered; one is dropped (below).

**What ships — six cells:**

| market | sides | floor | bets | units | ROI | 2025-26 alone (90% CI) |
|---|---|---|---|---|---|---|
| Steals | over + under | 0.02 | 19,367 | +848.5 | +4.48% | +4.09% (+1.95..+6.32) |
| Rebounds | under | 0.01 | 19,406 | +610.8 | +3.19% | +2.59% (+0.67..+4.58) |
| Blocks + Steals | over + under | 0.05 | 9,706 | +518.1 | +5.16% | +5.76% (+2.31..+9.36) |
| Blocks | under | 0.02 | 8,526 | +542.4 | +5.79% | +6.87% (+3.41..+10.14) |
| Reb + Ast | under | 0.04 | 9,605 | +393.9 | +4.22% | +3.86% (+0.58..+7.10) |
| Threes | over + under | 0.04 | 16,750 | +496.5 | +3.11% | +4.60% (+2.34..+6.83) |

The pooled card, 2023-24..2025-26, -200 floor, every qualifying proposition, 1 unit to win:

| books | bets | units | ROI | 90% CI | by season (units) | a night (median / most) |
|---|---|---|---|---|---|---|
| the eight bettable | 83,360 | +3,410.1 | +4.12% | +3.49..+4.77 | +1,372.9 / +967.8 / +1,069.4 | 165 / 397 |
| **the five the 2026-27 feed returns** | **66,588** | **+2,392.8** | **+3.60%** | **+2.93..+4.32** | **+1,125.2 / +433.3 / +834.4** | **131 / 362** |
| DraftKings alone | 46,483 | +1,168.0 | +2.46% | +1.65..+3.28 | | |

The feed has returned DraftKings, FanDuel, Fanatics, BetParx and BetRivers for 2026-27
(BetMGM, Caesars and Hard Rock not yet), so the five-book row is the expectation, and
less than that: the best cell of a 546-cell search runs high.

**Prices it lays:** min −200, 5th percentile −166, median +108, 95th +170, max +3000;
64% plus money, 9% at −150 or shorter. 558 bets are longer than +200 (they lose 4.9
units); the +1,600..+3,000 tail is threes overs at 0.5 quoted by one book, at stakes of
a few hundredths of a unit.

**Assists overs are NOT shipped.** The search put them in (0.06 floor, +144.5 units). On
2025-26, the season they were confirmed on, they made +0.74% (CI −2.88..+4.27); the
neighbouring floor lost (−9.4 units) and the late half lost (−15.2). At the five feed
books they are −1.29%, at DraftKings alone −3.51%. Dropping them costs +15.3 units of
2025-26 at eight books and gains units at the books the worker sees.

**What three independent verifiers found** (all three confirmed, 2026-10-16):

- *Statistics.* Reproduced to the bet. Clustering by game, player, player-night or week
  does not move the interval. Placebo (probabilities shuffled within night × market, 100
  times): best −2.62%. Every market-side beats a blind bet on the same side at the card's
  own price mix. Calibration still overclaims in the band bet — claimed 0.533, won 0.501,
  price-implied 0.483 — so **the probability shown is an upper bound**. 85% of bets share a
  player-night with another bet (Blocks + Steals is the sum of two other markets); the
  interval already accounts for it.
- *Prices.* **Most of the edge is the best price.** At the second-best book the card makes
  +1.45%; keeping a bet only when the second-best price also clears its floor, +2.67%
  (CI +1.94..+3.44). In 2025-26, 32% of units came from lines only one book (mostly
  BetParx: steals and blocks) posted; without them the seven-cell research card is
  +3.81% over three seasons. So the live card refuses a quote whose own clock is more than 10 minutes behind
  the freshest book's for the same market in the same fetch — a live deviation the archive
  could not grade (it stored no clock).
- *Timing and leakage.* No input reads past the snapshot (outcome-scramble test: 0 of 57
  inputs move on the first scrambled date). Two live facts: the feed did not request
  blocks+steals or rebounds+assists until 2026-10-16, and the shared decision window put
  the first look 66–70 minutes before tip (both fixed: PR #970). Reports read 60 minutes
  late: +3.57%. The pre-game roster in place of the game's own box: +3.99%.

**Live parity, measured.** The live code path (`scripts/nba_prop_projection_card.project_core`)
replayed three past nights (2025-11-12, 2026-01-15, 2026-03-20; 17 tip-time groups) from the
research cache with the fold-2026 models: 778 of 850 projected players (91.5%) equal the graded
prediction exactly, the rest differ by 1.2% on average (the pre-game roster in place of the
game's own box), and all 675 graded card bets' players were projected. The trainer rebuilds
the graded frame (320,239 rows, no input differs) and refits the fold-2026 models to 0.0
difference on 25,660 predictions. Built from 2022-23 on instead of 2018-19, the means moved
5-7% for one player in a hundred, so the live frame reads every season: 72 seconds per group
here (104 at most).

**Where live differs from what was graded, measured by the pre-merge review (2026-10-16).**
- The graded card excluded every proposition the Pinnacle rule bet at all eight books. Live,
  the rule sees the five books the feed returns, so it holds fewer, and the projection model
  may bet about 313 a season the grade never included (rebounds unders mostly); on the
  archive those graded −1.94% (940 bets, −19.5 units over three seasons).
- The research matched a book's player name against the whole season's rosters. Live only
  knows box lines already played, so a player's first game for a new team (opening night,
  a trade) cannot be matched or bet: 262 of the five-book bets, −8.2 units (−2.99%).
- The live selection, replayed on January 2026's archived quotes with the stored means,
  returns the graded bets bet for bet, and the live projection replays one 2025-26 night's
  graded means exactly (`tests/test_nba_prop_projection_replay.py`, run where the research
  cache exists).

**How it runs.** The five-minute window job projects each game at the tick about 65
minutes before tip (an ESPN injury pull, then the frame; 139 seconds for three games
from this machine against production), storing every player's mean in
`nba_prop_projections`; two ticks later, inside the 45–57 window and after
`nba_prop_market` has decided the game, the card prices those projections on the newest
fetch. Each game is decided once (`nba_prop_projection_decisions`). The injury list each
game was projected with is kept in `nba_injury_asof`, which also holds the 2018-19..2025-26
history from the official report.

## 6. Second search: spread, moneyline and total (pre-registered 2026-10-17, before any grid)

mike, 2026-10-16: *"We need nba spread / ml / totals models … find edge and I don't care how
long it takes."* §4.1 closed these markets for 2026-27 after 978 game-market cells (3,750
counting first half, first quarter and team totals). This search tests only hypotheses that
bring **information the first search never used** — §1's kill criterion forbids re-cutting a
closed family — and each comes from outside evidence (published studies, practitioner methods)
or from a gap the audit of the first search found. Scouting reports: build machine,
`C:/Users/micha/AppData/Local/Temp/nba_game_edge/scout_out/`.

**Written before any cell of this search was graded. Nothing below is changed after a result
is seen; a later change gets its own dated line and reason.**

### 6.1 What is already known, and what that costs this search

- **2025-26 has been looked at.** The first search graded all 3,750 cells on it. It is still
  the confirmation season here (the only priced season left), so the price of looking twice
  is paid in the multiple-testing count (6.4), not hidden.
- **The archive's clock.** A stored price's `snapshot_at` is the book's `last_update`, which
  the feed refreshes on every poll: it sits within 0.41 h of the fetch (p99 0.17–0.28 h). It
  stands in for the fetch time; it does **not** say when a price changed. Movement is read from
  changes in the line or price across fetches.
- **Fetch hours.** Per game date: 22Z the evening before; 15Z, 19Z, 22Z, 23Z; 00Z–03Z next
  UTC day. Nothing 03Z–15Z or 19Z–22Z. 337 afternoon and late tips (16–18Z, 20–21Z, 04Z) have
  no fetch in their last hour. Pinnacle is quoted from 15Z to tip on 96–98% of games; its
  overnight opener is missing on 51–87% of games.
- **2020-21 is its own regime** (crowds, compressed schedule, three injury reports a day,
  10-minute snapshot spacing): graded and reported separately, never used to choose.
- **The injury report** is stamped with its printed time. When each file became downloadable
  is unknown, so a report is treated as known **30 minutes after** its printed time.

### 6.2 Rules every cell is graded under (one shared harness)

1. **Price.** Best bettable price among `config.BEST_LINE_BOOKMAKERS` (8 books; Pinnacle and
   Bovada never a deciding price), two-way quote coherent (implied sum 1.00–1.15), −200 floor.
   DraftKings alone reported beside every result.
2. **What a bettor sees at decision time T:** for each (game, book, market), the newest quote
   with `snapshot_at ≤ T` and no older than 60 minutes; spreads and totals at the number that
   book hangs.
3. **Decision points** (each a separate cell axis): **A** the 15Z fetch (game morning);
   **B** the newest fetch 3–6 h before tip; **C** the newest fetch 60–180 min before tip;
   **D** the newest fetch 45–75 min before tip (where the live NBA cards decide). Never a fetch
   inside the last 15 minutes. Each game decided once per cell.
4. **Units.** One unit to win, risk capped at 3. **A push returns the stake: 0 units, and its
   risk leaves the denominator.** ROI with the stake kept is reported beside.
5. **Seasons.** Models fit on 2018-19 (box scores) or 2020-21 (prices) onward, walk-forward:
   season S predicted by a model fit on seasons before S. **Cuts chosen on 2021-22 → 2024-25;
   confirmed on 2025-26.** 2020-21 reported, never chosen on.
6. **Robustness reported for every cell (not a selection rule):** units on bets whose deciding
   price is still offered at the same number at the next stored fetch; units without the best
   book's single outlier (best price more than 20 cents better than the next book).

### 6.3 The hypothesis families and their cells

Each family's cells are enumerated here; nothing outside this list is a candidate.

| # | Family (new information) | Outside evidence | Markets × sides | Decision points | Cut axis | Cells |
|---|---|---|---|---|---|---|
| F1 | **Team strength independent of the market**: as-of player ratings (box-score plus-minus model, and adjusted plus-minus from free play-by-play stints) × projected minutes, with the injury report; projects margin and total, priced against every posted number through the empirical margin/total distribution | EPM / DARKO / 538 practice; audit gaps 1 and 12 | spread, total, moneyline × 2 sides | A, B, C, D | EV ≥ 0, .01, .02, .03, .05, .08 | 144 |
| F1b | **The same projection predicting the line's move**: bet when the model's projected close differs from the decision line by ≥ k | audit gap 7 | spread, total × 2 | A, B, C | k = 0.5, 1, 1.5, 2 pts | 48 |
| F2 | **Spread-implied win probability against the moneyline**: the spread mapped to a win probability through the empirical margin distribution, compared with each book's moneyline | Moskowitz & Vasudevan 2020 | moneyline × favourite / underdog | A, B, C, D | EV ≥ 0, .01, .02, .03, .05, .08 × reference (Pinnacle spread / consensus spread) | 96 |
| F3 | **Betting against part of each line move** from the first stored quote to the decision | Moskowitz 2021 | spread, total × fade | B, C, D | move ≥ 0.5, 1, 1.5, 2 pts (consensus) | 24 |
| F4 | **Shooting-luck-adjusted ratings**: opponent three-point and free-throw percentage replaced by their expectation; bet the gap between luck-adjusted and raw rating where the line follows the raw | Ringer / Paine on opponent 3P% persistence | spread, total × 2 | A, C | gap ≥ 1, 2, 3, 4 pts | 32 |
| F5 | **Absences valued beyond minutes**: player tier from the as-of ratings, starters out, Questionable as a probability, first game back; bet the gap between the availability-adjusted projection and the line | audit gap 2; practitioner minutes reallocation | spread, total × 2 | B, C, D | gap ≥ 1, 2, 3 pts | 36 |
| F6a | Overtime tail: over when the spread is within k | academic overtime item | total over | B, C | abs(spread) ≤ 1, 2, 3, 4 | 8 |
| F6b | Player points props summed per team against the total and spread (2023-24 on; choose on 2023-24 + 2024-25) | audit gap 6 | spread, total × 2 | D | gap ≥ 2, 4, 6 pts | 12 |
| F6c | Late-season motivation: seed locked, eliminated, tanking (as of the date, from `games`) | Krieger 2015 | spread, against the team | A, C | 3 situations | 6 |
| F6d | One book against itself: moneyline against its own spread; total and spread against its own team totals (2024-25 on) | audit gap 6 | moneyline, total × 2 | C, D | EV ≥ .01, .03 | 16 |

**New cells: 422.**

**Controls, graded and reported, never candidates:** every blind side; win/loss streaks; big
home underdogs; fading the public (Action Network splits, free); early-season unders; the
published schedule spots; the soft-book consensus outlier (the refuted mechanism).

### 6.4 Bars

§1's thirteen bars, unchanged, with three additions fixed now:

- **Multiple testing.** Benjamini–Hochberg at q = 0.05 over **m = 4,172** (this search's 422
  cells plus the first search's 3,750, the earlier ones entered at p = 1), one-sided whole-day
  bootstrap p on 2025-26 alone.
- **Confirmation** is 2025-26 alone: ≥ 200 bets, ROI > 0, 90% CI above zero.
- **Closing-line value is a bar where the archive has a later price** (decision points A–C):
  the median bet beats Pinnacle's last pre-tip no-vig price.

A family with no cell clearing every bar is closed, with its grid recorded here.

### 6.5 Data this search adds (all into Supabase first)

- Free play-by-play with wall-clock times (sportsdataverse ESPN release, 2018-19 → 2025-26):
  stints for adjusted plus-minus, garbage time, shot-level three-point luck.
- Free historical closing lines before 2021 (single book, no timestamps): supporting evidence
  for closing-line-only checks, never a bar.
- Action Network public splits (free GET): controls only.
- **Bought (Odds API history, pre-approved):** the missing fetch hours — 16Z, 17Z, 18Z, 20Z,
  21Z and 04Z on every game date 2020-21 → 2025-26 — so afternoon and late tips get a quote in
  their last hour and decision points C and D cover every tip time. Cost measured on one call
  before buying; balance read before and after.
- **Live game-line history kept from 2026-27 on.** Every NBA price change from every book is
  retained (only exact repeats thinned), so 2026-27 becomes an untouched season and the true
  opener becomes observable.

**Amendment, 2026-10-17, before any cell is graded: the hours alone miss the half-hour tips.**
Measured on the cached archive (full-game moneyline, spread and total; pre-tip quotes only):
the 45–75-minute window (decision point D) is reached on 93% of tips on the hour but on 3% of
the 2,195 tips on the half hour (7:30 ET and the like). Every season sits at 64–72% of games.
A half-hour evening tip's fetches sit 30 and 90 minutes out, and the hours listed above do not
change that. So the purchase also buys, for every game no held fetch reaches, a fetch at
tip − 60 (closes D and C) and tip − 240 (closes B where 3–6 hours is empty), each at the
5-minute snapshot at or before. Seasons are bought in the order 2021-22, 2022-23, 2023-24,
2024-25, 2025-26, 2020-21, so a floor stop leaves the least-needed season short.

Two rules follow, fixed now:

- **A cell's decision time is the fetch instant**, read from the two purchase ledgers
  (`odds_history_pulls` on the hour, `odds_history_fetches` off it). A quote's stamp is the
  book's last update, up to ~25 minutes before the fetch, so it does not name the window.
- **Gate before any D cell is graded:** D is reached on ≥ 95% of games in **every** season cuts
  are chosen on, not on average. A season short of it is reported and not chosen on.

**Amendment, 2026-10-17, before any cell is graded: how each bar is read.** Written into
`scripts/nba_game2_verdict.py` and committed with this line; the labs only emit cells.

- **Each cell bets one side**, so bar 9 applies to every cell. The blind bet is that side on
  every game with a price at that decision point, at the best deciding offer under the
  market's own fair line (Pinnacle's no-vig, else the median of the deciding books), with no
  cut. (The first search compared at the first fetch instead.)
- **Placebo:** the cell's ROI must beat the 95th percentile of 20 placebo runs. Each run
  shuffles the model's fair numbers between games on the same date in the same market (seed =
  run number).
- **Plateau:** the neighbours are the cut one step either side, everything else equal. A
  neighbouring decision point is not a neighbour.
- **Closing-line value** is measured on the choosing seasons' bets.
- **p values:** whole-day bootstrap, 4,000 resamples; any p under 0.01 is recomputed with
  400,000 (same seed), because the best cell's bar is 1.2e-5, finer than 4,000 can show.
- **Fewer choosing seasons where the data starts later:** F6b chooses on 2023-24 and 2024-25;
  F6d's team-total cells on 2024-25 alone.
- **Per-game purchases** (team totals, props) are dated by the feed's own snapshot time and
  count only at D.
- **Open before the verdict runs (mike):** whether the Benjamini–Hochberg p is read on 2025-26
  alone over m = 4,172 (as written above) or on the four choosing seasons over this search's
  cells, with the 2025-26 confirmation bar unchanged. The script computes both; it is run on
  real cells only after that is decided.

**Amendment, 2026-10-17 (second), before any priced season is graded: what the lab reviews
changed.** Each family's lab was reviewed for look-ahead and for drift from §6.3. These follow,
and all land before any cell is graded:

- **The empirical distribution, as §6.3 says** (the first builds used a bell curve). Two
  sources. The market's own pricing (F2, F6a, F6d, the market's fair line, the blind bet,
  closing value) uses the spread of results around Pinnacle's closing number on earlier
  seasons. A projection built without prices (F1, F1b, F5) uses the spread of results around
  that projection on earlier seasons, so it is never priced with the market's smaller error.
  Results are whole numbers: a result placed between two integers is split between them by
  distance, so whole-number lines carry push mass and half-point lines none.
- **Bar 9 is read as §1 words it. This replaces the earlier line "each cell bets one side".**
  When more than 70% of a cell's choosing-season bets fall on one side of home/away,
  favourite/underdog (by the market's fair line at T) or over/under, the cell must beat that
  side bet on every game of its own priced population at that point, with no cut. The
  population is the games its model or rule produced a number for. A dominant side with no
  blind number fails.
- **The 95% gate at D is applied by the harness**, season by season. Every cell row records
  each season's coverage and any season it dropped.
- **A graded run refuses a stale cache:** any season it needs priced on fewer than 90% of
  games, or more than 5% of rows matching no purchase record.
- **Controls are never judged** and do not count in m.
- **A categorical axis has no neighbours** (F6c's situations); bar 7 there reduces to the
  cell's own ROI above zero.
- **Corrections inside the labs:**
  - F4 adjusts only opponent three-point and free-throw percentage. A term regressing each
    team's own three-point percentage came from the build instructions, not §6.3, and is
    removed.
  - F6a's cut reads the posted spread (Pinnacle's, else the deciding books' median), not a
    centre solved from the price.
  - F2 leaves a level reference (pick'em) with no favourite.
  - F6d's "one book against itself" takes both of that book's quotes from the same fetch.
  - F1b's strength is the predicted move (predicted close minus the consensus number at T) in
    the bettor's favour. The build used the offered number minus the predicted close, which
    rewards a soft book's off-consensus number: the refuted outlier mechanism.
- **Lab definitions §6.3 does not fix,** recorded so they are not read as registered: F6c's
  "seed locked", "eliminated" and "tanking" (bottom three after the trade deadline) and its
  deadline dates; F6b's points distribution (the spread of a player's points around his
  season average on earlier seasons); F1's roster, minutes and injury-probability settings
  (in the lab's docstring).

**Coverage after the purchase, 2026-10-17 03:46Z** (before any cell is graded). The purchase
bought 5,736 extra-hour fetches and 1,552 gap fetches: 218,670 credits, balance 2,300,945
afterwards. Measured on the refreshed cache with `python -m scripts.nba_game_harness
--coverage`: the share of each season's games with a decision at each point.

| Season | A (15Z) | B (3–6 h) | C (60–180 min) | D (45–75 min) |
|---|---|---|---|---|
| 2020-21 | 0.996 | 1.000 | 1.000 | 0.996 |
| 2021-22 | 1.000 | 1.000 | 1.000 | 0.994 |
| 2022-23 | 1.000 | 1.000 | 1.000 | 1.000 |
| 2023-24 | 1.000 | 1.000 | 1.000 | 1.000 |
| 2024-25 | 1.000 | 1.000 | 1.000 | 1.000 |
| 2025-26 | 0.999 | 1.000 | 1.000 | 1.000 |

The D gate (≥ 95% in every choosing season) passes in all four. Of 2,733,316 full-game rows,
2,732,723 join their purchase record exactly; 593 (0.02%) were placed by their stamp.

**Amendment, 2026-10-17 (third), before any priced season is graded: what the re-reviews
changed.**

- **The empirical distribution is the spread, not the average miss.** Residuals are
  re-centred on zero before use. Uncentred, a projection's earlier average miss would move its
  centre a second time: measured on 2020-21, about 1 point toward the away team and 1.4–2.3
  points toward the under, on top of a calibration that already corrects it. For the market's
  own pricing, the centre is solved from the price, so this changes nothing there.
- **Only F1 is priced with the projection's own error.** F1b, F5 and F6b cut on a gap in
  points and take the best offer under the market's fair line, like every rule family.
- **Every "gap against the line" is measured against the consensus number at T**
  (Pinnacle's, else the deciding books' median), not against each book's offered number. This
  covers F1b, F5 and F6b. Measured against each book's own number, a soft book's
  off-consensus line raises the gap, which is the refuted outlier mechanism.
- **Two lab definitions recorded:**
  - F6d's team-total distribution is the team's score minus the team total implied by
    Pinnacle's closing spread and total, home and away pooled, on earlier seasons only, with
    no fallback to the season's own games.
  - F2's placebo shuffles the favourite's win probability between games on a date; each game
    keeps its own favourite side.
- **Public splits:** the stored history (2020-21 to 2025-26) is the CLOSING split (measured
  in `docs/nba_public_splits.md`). It is known only after tip, so the public-fade control has
  no pre-tip bets before 2026-27. The 2022-03-09 slate is reversed home-for-away at the source
  and is excluded.

**Amendment, 2026-10-17 (fourth), before any priced season is graded.**

- **A categorical cell is its own population for bar 9.** F6c's situations have no cut inside
  a cell, so the blind comparison runs over the games in that situation only. It asks
  whether betting against the team beats betting the dominant real side (home, away,
  favourite, underdog) in those same games. Threshold families keep every game the rule
  produced a number for. The placebo still moves the flag across every game on the date.
- **Lab definition recorded:** F4's "expectation" for opponent three-point and free-throw
  percentage is the league's rate so far that season, from games final before the date.

### 6.6 Results (graded 2026-10-17): every family closed for 2026-27

All 422 cells were graded walk-forward at bought prices and stored before any return was read
(`nba_game2_cells`, run `2026-10-17-full`). The pass/fail script then ran once on each
multiple-testing basis: **0 of 422 pass on either**, so the open question in §6.4 changes
nothing.

- 113 cells are positive on the choosing seasons, 91 on 2025-26, and 32 on both.
- 342 cells have ≥ 200 bets on the choosing seasons. 4 of them have a 90% interval above zero,
  all in F4.
- 247 cells have ≥ 200 bets in 2025-26. None has a 90% interval above zero there.

The nearest cell in each family (most bets-backed: highest lower interval bound among cells with
≥ 200 choosing-season bets, else the best there is). Units are one unit to win.

| Family | Nearest cell | Choosing seasons: bets, units, ROI (90% CI) | 2025-26: bets, units, ROI | Bars failed |
|---|---|---|---|---|
| F1 player strength | moneyline away, morning, EV ≥ 0.02 | 2,339, +38.2, +2.8% (−1.5..+7.2) | 484, −5.1, −2.0% | 5, 6, 11, confirm, BH |
| F1b predicted move | total under, morning, move ≥ 0.5 | 115, +1.0, +0.8% (−13.6..+15.3) | 6, −0.2 | 6, 7, 8, 11, confirm, BH |
| F2 spread vs moneyline | underdog, consensus, morning, EV ≥ 0.01 | 1,060, +22.6, +9.0% (−1.9..+19.3) | 119, −5.1, −25.0% | 5, 6, 11, confirm, BH |
| F3 fade the move | total, 45–75 min, move ≥ 0.5 | 4,399, −120.2, −2.5% (−4.9..−0.3) | 1,105, −54.7, −4.6% | 5, 6, 7, 8, 10, confirm, BH |
| F4 shooting luck | over, morning, gap ≥ 3 | 426, +49.4, +10.7% (+3.2..+18.2) | 81, +7.6, +8.5% | 11, confirm, BH |
| F5 absences | home spread, 3–6 h, gap ≥ 3 | 381, +32.9, +8.0% (−0.3..+15.9) | 131, +11.7, +8.3% | 6, 7, 11, confirm, BH |
| F6a overtime tail | over, spread within 4 | 1,777, −83.4, −4.3% (−7.9..−0.6) | 403, −47.5, −10.9% | every bar |
| F6b props summed | away spread, gap ≥ 2 | 1,034, −11.5, −1.0% (−5.8..+3.9) | 510, −7.9, −1.5% | 5, 6, 7, 8, 10, confirm, BH |
| F6c motivation | against an eliminated team, morning | 282, +18.5, +6.0% (−3.1..+14.7) | 89, +7.1, +7.3% | 5, 6, 11, confirm, BH |
| F6d one book vs itself | moneyline home, 60–180 min, EV ≥ 0.01 | 1,156, +5.0, +0.4% (−4.6..+5.4) | 266, −27.4, −8.5% | 5, 6, 8, 11, confirm, BH |

**The one near miss is F4 overs**: betting the over in the morning when the luck-adjusted
projection is at least 3 points above the raw one.

- **What it clears:** positive in every choosing season (+15.3%, +5.3%, +2.5%, +20.6%), a
  plateau, both halves, the blind over and the placebo.
- **Why it fails:**
  - **Closing-line value:** the median bet is 2.4% worse than Pinnacle's no-vig close. The
    market moves away from these bets, not toward them.
  - **2025-26 has only 81 bets** (+7.6 units), against the 200 the confirmation needs.
  - **2020-21 lost** 8.5% on 103 bets.
- **Verdict:** closed by §1's kill criterion, because no cut passes bars 4–11.

**A defect found after the results, fixed, with the outcome unchanged.** Six cells with 1–14
bets that all won had a resampled p of exactly 0 and cleared the correction alone; every one
fails the 200-bet bar. Such a cell now enters the correction at p = 1. That only makes the bar
stricter; it is still 0 of 422.

**What comes next is 2026-27.** It is a season nobody has looked at, with every price move kept
from opening night (#985). The grids above, and F4's overs in particular, can be re-graded on it
with the same harness and no new choices.

### 6.7 The house standard, applied to the same 422 cells (2026-10-17, after §6.6 was read)

mike, 2026-10-17: *"Find it … edge like we have with other sports."* The bars in §1 and §6.4
were stricter than any model shipped in this repo was held to. The newest shipped game-market
model, `nhl_moneyline` (`docs/thresholds.md`, 2026-10-13/15), went live on this:

- a walk-forward over its graded seasons pooled;
- a 95% interval above zero;
- seasons mostly positive (its newest season was −3.0%);
- beating the blind bet on the same side;
- a neighbourhood, not a peak;
- closing-line value reported, not a bar.

It had no separate one-season confirmation and no correction across the cells searched.

**This section applies that standard to all 422 cells, once, as one fixed list. It is applied
AFTER the §6.6 results were read, and it is stated before any number under it is computed.**
The labs are re-run unchanged, except that each cell also reports its pooled numbers, and its
bets are written out. A cell passes when all of these hold:

1. **Pooled walk-forward:** every graded season (2021-22 → 2025-26, or the family's own
   seasons per §6.3) together, ≥ 200 bets.
2. **The pooled whole-day bootstrap 95% interval** of ROI is above zero (4,000 resamples, seed 7).
3. **Seasons mostly positive:** of the graded seasons with ≥ 30 bets, all but at most one are
   positive.
4. **Beats the blind same real side**, pooled, over its own priced population (bar 9 as amended
   in §6.4).
5. **Neighbourhood:** every existing neighbour on the cut axis is positive, pooled.
6. **Placebo:** above the 95th percentile of its shuffles (bar 10).

**Reported beside each passing cell, not as bars:**

- pooled closing-line value;
- the blind same side's closing-line value at the same point (to tell a cell's own late drift
  from the market's);
- DraftKings alone;
- the count of cells expected to clear bar 2 by chance (422 × 0.025 ≈ 10.5, before
  correlation).

A cell that passes is built LIVE (CLAUDE.md §2) and judged on its live record.

**Results under the house standard (2026-10-17).** Every lab was re-run unchanged with pooled
numbers and its bets written out (`NBA_GAME2_BETS`). `python -m scripts.nba_game2_verdict
--house`: **4 of 422 cells pass, all one effect: F4's overs.**

| Cell | Bets | Units | ROI | 95% interval | Seasons positive | Closing value (cell / blind over) |
|---|---|---|---|---|---|---|
| over, morning (A), gap ≥ 3 | 507 | +57.0 | +10.3% | +2.2 .. +18.5 | 5 of 5 | −2.35% / −2.80% |
| over, morning (A), gap ≥ 4 | 210 | +29.9 | +13.1% | +0.3 .. +25.7 | 4 of 4 | −2.34% / −2.80% |
| over, 60–180 min (C), gap ≥ 3 | 508 | +55.6 | +10.1% | +2.0 .. +18.3 | 5 of 5 | −2.23% / −2.41% |
| over, 60–180 min (C), gap ≥ 4 | 210 | +31.2 | +13.6% | +1.3 .. +25.6 | 4 of 4 | −2.23% / −2.41% |

- **How to read it.** Only 6 cells clear the 95% interval at all, against about 10.6 expected
  by chance before correlation. Two of the 6 are one-bet artifacts and the other four are this
  one effect. So the interval is not what makes it credible.
- **What does make it credible is the shape:**
  - The return rises with the luck gap at every decision time: +3.8 / +5.7 / +10.3 / +13.1% at
    A, +3.7 / +5.9 / +10.1 / +13.6% at C.
  - Every graded season is positive at gap ≥ 3.
  - It works for overs only (unders are mixed).
  - The mechanism is published: opponents' three-point shooting is mostly luck.
  - The neighbours are positive, though not themselves significant: gap ≥ 2 spans zero. That is a
    neighbourhood by the house definition and a ridge by a stricter one.
- **Closing-line value is not a warning sign.** A line that never moves scores about −2 to −4.5%
  by this measure (the bookmaker's margin). These bets fare slightly better than blind overs at
  the same moment.
- **The profit survives the market's own move.** The diagnostic at D (45–75 minutes, not
  registered) at gap ≥ 3: 506 bets, +53.6 units, +9.7%, interval +1.6 .. +18.1, 5 of 5 seasons.
- **Robustness of the cell that ships (C, gap ≥ 3):**
  - Without single-book outlier prices: +46.8 units.
  - Without BetRivers (+26.5 units on 78 bets): 430 bets, +29.1 units, +6.2%.
  - DraftKings alone: +8.2% on 425 bets over the choosing seasons, +7.0% in 2025-26.
  - Still offered at the next stored fetch: 27.8% of bets.
  - Prices −115 to +100, median −110. 290-214-4.
- **The other near misses fail the house standard:**
  - F5 home spreads (3–6 h, gap ≥ 3): 512 bets, +8.1%, interval −0.4 .. +16.5.
  - F6c against eliminated teams: 371 bets, +6.3%, interval −3.5 .. +16.2, 3 of 5 seasons.

**Shipped LIVE (CLAUDE.md §2):** F4 overs at C, gap ≥ 3. It is judged on its live record.

## 7. Third search: in-game spread, moneyline and total (pre-registered 2026-10-17, before any grid)

mike, 2026-10-17: *"Find it."* Every pre-game idea the outside sweep found repeats a closed family
or rests on weak evidence (ranking: build machine,
`C:/Users/micha/AppData/Local/Temp/nba_game_edge/scout3_ranked.md`).

The new information is in-game. The archive already holds **380,349 in-play quotes** on 7,213
regular-season games, 2020-21 → 2025-26 (Pinnacle on 7,156 of them). They come from the hourly
fetches that land after tip, about two per game, and no cell has ever used them. The in-play
models elsewhere in this repo were judged on calibration and lost (`docs/live_betting.md`), so
this search must first show **information beyond Pinnacle's own live price at the same moment**.
Only then does it run a betting grid.

### 7.1 Data rules

- **Game state at a quote** (score, period, clock, fouls, shooting so far) comes from the ESPN
  play-by-play wall clock (`nba_pbp`) at the quote's stamp, never from `games.commence_time`.
  On 17 games in late October 2025 the first play came more than 60 minutes after the listed
  tip.
- **Step 0, the staleness gate (free).** Test whether points scored in the 60–120 seconds before
  a quote's stamp predict that quote's result, against Pinnacle's live no-vig price.
  - If they do, a quote is used only when no point was scored since the book's last update, and
    only when Pinnacle quoted within 60 seconds of it. This is the NCAAF in-play rule,
    `scripts/ncaaf_inplay_history_backtest.py`.
  - The gate's result is recorded here before any information test runs.
  - **How "predict" is scored (2026-10-17, fixed before the test ran;
    `scripts/nba_ingame_staleness.py`).** Rows: in-play quotes by the play-by-play clock, all
    six seasons, with a Pinnacle quote on the same game and market in the same purchase,
    stamped within 60 seconds. The result is side A (home or over) at the quote's own number on
    the full-game score; pushes are left out. The benchmark is Pinnacle's no-vig probability;
    for spreads and totals only quotes at Pinnacle's own number are used. The predictor is the
    points scored in the 60–120 seconds before the stamp, signed toward side A (home minus
    away; both teams for a total). The statistic is the slope of (result − benchmark) on those
    points, with a whole-day bootstrap 95% interval, per market and pooled. Four panels: every
    book against Pinnacle (the test as written); Pinnacle alone; the 8 deciding books alone;
    the 8 deciding books against their own no-vig price. The rule is imposed when any panel's
    interval, in any market or pooled, lies wholly above zero. An interval wholly below zero is
    over-reaction, not staleness, and imposes nothing. When imposed, the rule covers the
    deciding quote and the Pinnacle quote it is measured against: no point scored between each
    one's stamp and the moment the feed served it.
  - **Result (2026-10-17): the gate fires, so the rule is imposed.**
    `python -m scripts.nba_ingame_staleness` ran on 374,827 in-play quotes built by
    `scripts/nba_ingame_data.py` (2020-21 → 2025-26). It left out 34 games whose play clock is
    broken; in 13 of them, from late October 2025, ESPN stamped a whole half about 24 hours off.
    - Points scored 60–120 seconds before a quote's stamp predict its result against Pinnacle's
      live no-vig price, in every market and every season.
    - Across every book the slope is +0.0159 per point (95% interval +0.0131 to +0.0189, 136,743
      quotes): moneyline +0.0194, spread +0.0196, total +0.0110.
    - On Pinnacle's own quotes it is +0.0154 (+0.0128 to +0.0179).
    - So every in-game family uses a quote only under two conditions. No point was scored between
      its stamp and the moment the feed served it, for the deciding quote and for its Pinnacle
      quote. And Pinnacle quoted within 60 seconds.
    - After the rule, the games per season with a usable deciding-book quote are: Q1–Q2 567–782;
      halftime 114–299; Q3 262–483; Q4 with 6+ minutes left 170–359.
  - **What the diagnostics add (2026-10-17; not part of the gate; `--extra`).**
    - The rule does not remove the effect. On quotes that pass it, the same test gives +0.0170
      (+0.0134 to +0.0205).
    - The lag is in Pinnacle's stored live price. Points from 5–10 minutes before the stamp
      still predict against it (moneyline +0.0106); points from earlier in the game barely do
      (+0.0016).
    - On the same moneyline quotes, Pinnacle's no-vig predicts worse than the deciding book's
      own no-vig: log loss +0.029 (+0.025 to +0.033), worse in every season.
    - The total shows the same split: +0.0134 against Pinnacle's own price, +0.0024 against the
      deciding books' own. A total sits near even money, where the no-vig method cannot cause it.
    - Against their own prices the deciding books show +0.0021 pooled (−0.0004 to +0.0047).
      Their spreads and totals cover zero. Their moneylines do not: +0.0054 (+0.0015 to
      +0.0096), and +0.0067 (+0.0018 to +0.0119) on quotes that pass the rule. So the deciding
      books' own moneyline prices also carry a small lag that the rule does not remove.
    - **What this means for 7.3:** an information test measured against Pinnacle's live price
      alone would be passed by any model that knows the recent score. Measuring it against the
      deciding books' own prices at the same stamp would change this pre-registration, so it is
      not done here.
- **Settlement:** full-game results. A live total is settled on the full-game score; the
  remaining points are the live line minus the points already scored.
- **Prices:** as §6.2, with the best of the 8 deciding books, the −200 floor, DraftKings alone
  beside, and pushes out of the denominator.
- **Seasons:** walk-forward. Choose on 2021-22 → 2024-25, confirm on 2025-26; 2020-21 is
  reported only.

### 7.2 Families (54 cells)

| # | Family | Market × sides | Decision | Cut axis | Cells |
|---|---|---|---|---|---|
| IG-1 | **Totals after in-game shooting luck.** Luck points so far = (3PM − 3PA × expected 3P%) × 3 + (FTM − FTA × expected FT%), both teams, from each team's season-to-date rates before the date. Model remaining points = pace-scaled remainder of Pinnacle's pre-game close, with points so far luck-corrected. Bet under when shooting is hot, over when cold. The opposite direction ("hot halves keep scoring") is graded as a control. | live total × over, under | the first eligible quote in each of three windows: Q2, the halftime break, Q3 | luck gap ≥ 2 / 4 / 6 / 8 points | 24 |
| IG-2 | **Game-state model against the live moneyline and spread.** A walk-forward win-probability and remaining-margin model. Inputs: margin, seconds left, Pinnacle's pre-game close spread as the prior (Stern 1994 variance), team fouls, foul counts of the top-minute players. | live moneyline (inside −200), live spread × the side the model favours | three phases: Q1–Q2, Q3, Q4 with ≥ 6 minutes left | EV ≥ 0.02 / 0.05 / 0.08 | 18 |
| HT-1 | **Halftime.** Rest-of-game total and spread from first-half luck points, first-half pace against the pace the pre-game close implied, team fouls, and the halftime margin. Graded first on the held quotes stamped inside the break (103–271 games a season). | full-game live total and spread at halftime × 2 sides | one quote inside the break | model gap ≥ 1.5 / 3 / 4.5 points | 12 |

#### IG-1: how the lab reads the row above (2026-10-17, written before any IG-1 number)

The row leaves these open, so they are the lab's definitions, not registered ones
(`scripts/nba_ingame_ig1.py`). Nothing below changes after a result is seen.

- **Luck so far (L).** Both teams, from everything the play-by-play shows at or before the
  quote's stamp: 3 × (3PM − 3PA × expected 3P%) + (FTM − FTA × expected FT%).
  - "Expected" is the shooting team's own rate this season, from the box scores
    (`nba_player_game_log`) of its games on earlier dates.
  - Through 2024-25 the official three-point attempts count missed end-of-period heaves, so
    the in-game count includes them too. From 2025-26 both leave them out.
- **The luck gap is L itself, in points.** A cell bets the under when L ≥ g and the over when
  L ≤ −g. The control, `control_ig1_persist`, bets the other way at the same cuts.
- **Population.** Both teams have played at least 10 games this season (CLAUDE.md §3, as F4),
  and Pinnacle has a pre-game closing total.
- **The decision.** For each game and window, the first purchase in that window holding an
  eligible quote. The offers are every eligible quote in that purchase and window, and the
  cut is applied there and nowhere later.
  - Eligible: one of the 8 deciding books, a coherent two-way price, a coherent Pinnacle
    quote in the same purchase within 60 s, and no point scored between stamp and serving
    for either quote (the 7.1 rule).
  - The window is read from the quote's own stamp: Q2 in play; the halftime break; Q3 in
    play, with the break after it.
  - L is read at the earliest stamp among those offers and their Pinnacle quotes.
- **The model (used by the information test only).** Remaining points =
  C·f + w·(P − L − C·(1 − f))·f/(1 − f).
  - C is Pinnacle's pre-game fair total (its close, no-vig, through the harness's empirical
    distribution); f is the share of the 48 minutes still to play; P is the points so far.
  - w is fit per window, by least squares on the seasons before the one predicted.
  - The model's full-game total is M = P + remaining points.
- **The information test (7.3).**
  - Rows: Pinnacle's own coherent live totals that pass the 7.1 rule, the first per game and
    window, read at Pinnacle's stamp.
  - Pinnacle's fair total μ is solved from its no-vig over price at its number, through the
    spread of (final total − Pinnacle's live number) on earlier seasons in the same window.
    2020-21 has no earlier season and uses its own; it is reported, never chosen on.
  - Without the model: μ + a0. With it: μ + a + b·(M − μ). a0, a and b are fit by least
    squares on earlier seasons, per window.
  - The statistic is the mean change in squared error of the final total, with the model
    minus without (below zero = information), whole-day bootstrap 95%, 4,000 resamples,
    seed 7. It is computed on the choosing seasons pooled (each predicted from the seasons
    before it) and on 2025-26 alone.
  - **Closed without a grid** unless the choosing seasons' interval lies wholly below zero.
    2025-26 is reported beside; if its interval covers zero, that is said first.
- **Diagnostics beside the test, never the gate.** 7.1 found that Pinnacle's stored live
  price lags the score by minutes, so a model that only knows the score may pass. So:
  (a) the model with no luck correction (L = 0, its own w) against Pinnacle; (b) the luck term
  added on top of (a); (c) the full model against the deciding books' own fair total (the
  median over books) at their first eligible quote.
- **The grid, only if the test passes.** The harness's `run_cells`. Offers are priced at
  Pinnacle's live fair total through the same distribution; best of the 8 deciding books,
  −200 floor, DraftKings beside. The placebo shuffles L within date, 20 runs. Closing-line
  value and "still offered at the next purchase" are not computed: the next purchase is
  about an hour later, in a different game state.

#### IG-1: the information test (2026-10-17)

`python -m scripts.nba_ingame_ig1` (log: build machine,
`C:/Users/micha/AppData/Local/Temp/nba_game_edge/ingame/ig1_full_log.txt`; numbers in
`info_IG-1.json` beside it). Units are squared points of the final total; below zero means
the model helped.

- **The registered test passes, so the grid runs.** Choosing seasons: −10.5 (95% interval
  −13.7 to −7.2) on 3,573 quotes, against Pinnacle's own error of 187.3. 2025-26 alone:
  −10.1 (−16.4 to −4.1) on 1,141 quotes.
- **But the gain is the score, not the luck.** The three diagnostics:
  - (a) The same model with no luck correction gains the same: −10.2 (−13.5 to −6.8), and
    −10.5 in 2025-26.
  - (b) The luck term added on top of (a) gains nothing: +0.20 (−0.18 to +0.57); 2025-26
    +0.06 (−0.80 to +0.92).
  - (c) Against the deciding books' own prices the full model gains nothing: +0.06 (−0.54
    to +0.65); 2025-26 −0.87 (−2.13 to +0.36).
  - The halftime break, when no one scores and Pinnacle's price has time to catch up, shows
    no gain at all: +0.35 (−2.58 to +3.15).
- **So the registered test was passed by the lag 7.1 found in Pinnacle's stored live
  price**, not by shooting luck. The fitted pace weight w is near zero in every season and
  window (−0.05 to +0.09): luck-corrected scoring so far does not predict the rest of the
  game beyond the pre-game total.
- 2020-21 has no earlier season, so its live-total distribution is its own; it is reported
  only. Games per season with a decision (both teams ≥ 10 games): Q2 410–524, halftime
  89–253, Q3 224–408.

#### IG-1: the grid (2026-10-17) — closed for 2026-27

Same command; cells in `cells_IG-1.parquet`, the verdict in `verdict_house_IG-1.parquet`.

- **0 of 24 cells pass the house standard (§6.7), and none clears its 95% interval**
  (24 × 0.025 = 0.6 expected by chance). 0 of 24 pass the §6.4 bars either (multiple-testing
  count 4,226). None of the 24 control cells ("hot halves keep scoring") clears its interval.
- **The nearest cell is the under in Q3 when shooting has run 4 or more points hot:** 661
  bets 2021-22 → 2025-26, +43.8 units, +5.8%, interval −1.6% to +12.7%.
  - It fails the interval and the seasons bar: 2021-22 −7.6%, 2022-23 −1.9%, 2023-24
    +11.6%, 2024-25 +21.8%, 2025-26 +5.5% (172 bets). 2020-21, reported only: +13.9% on 84.
  - It beats the blind under in the same games (+2.9%), its neighbours are positive (+4.0%
    at 2 points, +2.2% at 6), and it clears the placebo (+5.9% against a 95th percentile of
    +5.3%).
  - DraftKings alone: +1.4% on 409 bets in the choosing seasons, −1.1% in 2025-26.
  - Prices −140 to +110, median −115; 372-289, no pushes.
- **The same direction loses in the other windows:** the Q2 unders lose 1.8% to 4.1% at
  every cut, the halftime unders 4.0% to 11.1%.
- **Verdict:** IG-1 is closed for 2026-27. The information test was passed by Pinnacle's
  lag, not by luck, and the betting grid finds no cell.

### 7.3 Gates and bars

1. **Information first.** For IG-1, IG-2 and HT-1, measure the change in log loss (moneyline)
   or squared error (spread, total) when the family's model is added to Pinnacle's live no-vig
   price at the same stamp. Walk-forward on 2021-22 → 2024-25, then 2025-26 alone. A family
   whose 95% interval covers zero is **closed without a betting grid**.
   - **How HT-1 is scored (2026-10-17, fixed before any HT-1 number was computed;
     `scripts/nba_ingame_ht1.py`).**
     - *Decision quote.* Per game, the first purchase holding a deciding book's spread or total
       stamped inside the halftime break, coherent, with a coherent Pinnacle quote in the same
       purchase stamped within 60 s, and no point scored between either quote's stamp and its
       serving (7.1's rule). Every such deciding-book quote in that purchase is an offer. Both
       teams must have played 10 games this season (CLAUDE.md §3, as F4 applied it).
     - *Game state* at a decision is the plays logged at or before the quote's stamp (the shared
       table). The model is fit on every regular-season game of earlier seasons with a Pinnacle
       pre-game close, from its plays in periods 1–2, not only on games with a halftime quote.
     - *The model* is least squares on the rest-of-game points (total) or rest-of-game home
       margin (spread), fit on seasons before S; 2020-21 has none before it, so its model is fit
       on itself and it is reported only.
       - Total: Pinnacle's pre-game close total; pace, as first-half points minus half that
         close; luck points of both teams; first-half personal fouls of both teams; the size of
         the halftime margin.
       - Spread: Pinnacle's pre-game expected home margin (minus its close spread); that times
         pace, as (first-half points ÷ half the close total − 1); the halftime margin; luck
         points home minus away; personal fouls home minus away.
       - Luck points of a team = 3 × (3PM − 3PA × its 3P%) + (FTM − FTA × its FT%), with its
         rates from its own earlier games this season. Rates and counts both come from the
         play-by-play, with missed end-of-period heaves left out of both.
     - *Pinnacle's live price as a number:* the centre of the final total (or home margin) at
       which Pinnacle's no-vig probability holds at its number. It is solved through the
       empirical spread of (final − Pinnacle's halftime number) on earlier seasons' decision
       games (at least 150; 2020-21 on itself).
     - *The test, per market.* For season S, the base is Pinnacle's centre plus a constant. With
       the model it is Pinnacle's centre plus a constant plus β × (model − Pinnacle's centre).
       The constant and β are fit by least squares on earlier seasons' decision games. The
       statistic is the drop in mean squared error of the final number, in points squared,
       with a whole-day bootstrap 95% interval (4,000 resamples, seed 7). It is computed on
       2021-22 → 2024-25 pooled and on 2025-26 alone. **A market has information only when
       both intervals lie wholly above zero;** otherwise its six cells close without a grid.
     - *Reported beside, never the gate:* the same test for a score-only model (the pre-game
       close and the halftime score, no luck and no fouls). If that model passes too, the gain
       is Pinnacle's lag (7.1), not HT-1's inputs. Also: the same test against the deciding
       books' own median centre; the test with Pinnacle's raw number as its centre; and the
       slope of (result − Pinnacle's no-vig) on points scored in the last 5 minutes of Q2.
     - *The grid, only for a market with information.* Strength = model − Pinnacle's centre,
       in points, from the side's view, the same for every book. A side is bet when its
       strength is at least 1.5 / 3 / 4.5, at its best deciding offer under Pinnacle's halftime
       fair price (the harness's `run_cells`). The placebo shuffles the strength within date,
       20 runs. The house standard (§6.7) judges. "Still offered at the next purchase" and
       closing-line value cannot be measured at halftime and are reported as not measured.
     - **HT-1's result (2026-10-17): closed. Totals show no information; spreads pass the gate
       as written, but the gain is Pinnacle's lag, and none of the 6 spread cells passes the
       house standard.** `python -m scripts.nba_ingame_ht1` (log `ht1/run_log.txt` beside the
       shared table; cells `cells_HT-1.parquet`). Drop in mean squared error of the final
       number when the model is added to Pinnacle's centre; positive means the model helps.
       - Population after the 10-game rule: 573 spread and 574 total decisions in 2021-22 →
         2024-25, 212 and 211 in 2025-26. The state at the stamp equals the game's first half
         on 958 of 959 games.
       - Totals: +0.65 points² (−1.35 to +2.60) on the choosing seasons; −2.17 (−7.70 to
         +3.78) in 2025-26. **Closed without a grid.**
       - Spreads: +3.11 points² (+0.75 to +5.68); +4.70 (+0.33 to +9.46) in 2025-26. The gate
         opens.
       - The score-only model clears the choosing seasons, +2.83 (+0.66 to +5.17), but not
         2025-26, +4.19 (−0.47 to +9.29). So by the line above it does not strictly pass.
       - Three other measurements say the gain is Pinnacle's lag:
         - Against the deciding books' own median centre, the model adds nothing on the
           choosing seasons: −0.005 (−0.18 to +0.17). 2025-26 alone shows +0.44 (+0.05 to
           +0.86), one season, which the rule does not count.
         - On 2021-22 → 2025-26 together, Pinnacle's halftime spread centre has a squared error
           of 115.1 points². The books' own centre has 111.1.
         - The late-Q2 slope below lies above zero.
       - Points scored in Q2's last 5 minutes still predict against Pinnacle's halftime price:
         spread +0.0068 per point (+0.0013 to +0.0124), total +0.0059 (+0.0002 to +0.0118).
       - The spread grid (house standard, `house_verdict`): 0 of 6 pass. No cell reaches 200
         pooled bets; the most is 147 (home, strength ≥ 1.5: −9.97 units, −6.0%, interval
         −21.0% to +10.1%). Away at ≥ 3: 25 bets, +14.34 units, +52.4%, with no season holding
         30 bets. The §6.4 bars, with the count at 4,226: 0 of 6.
   - **How IG-2 is scored (2026-10-17, fixed before any IG-2 number was computed;
     `scripts/nba_ingame_ig2.py`, whose docstring holds every definition).**
     - *Decision.* Per game, market and phase (Q1–Q2, Q3, Q4 with 6:00 or more left; halftime
       is not an IG-2 phase), the first purchase holding a deciding book's moneyline or spread
       quote that passes 7.1's rule. Every such quote in that purchase is an offer. A later
       purchase in the same phase is never used.
     - *The model* (Stern 1994), fit on earlier seasons only: the final home margin is Normal,
       centred on the current margin plus the time-scaled margin Pinnacle's pre-game close
       implies, with adjustments for the current margin, team fouls in the period (and who is
       in the penalty), and the fouls of each side's three top-minute starters. Its variance
       grows with the time left. It is fit on every game's state every 30 s of game time, from
       the play-by-play. 2020-21 has no earlier season, so it is fit on itself and reported only.
     - *The test, per market.* Rows: Pinnacle's own quote at each decision, with the game state
       at its stamp. For each season S, two fits on earlier seasons' rows: Pinnacle's live
       no-vig alone, and Pinnacle plus the model. Moneyline: log loss of the home win. Spread:
       squared error of the final home margin, Pinnacle's margin solved from its own number and
       no-vig. The statistic is the change (with the model minus without), whole-day bootstrap
       95% interval, 4,000 resamples, seed 7, on 2021-22 → 2024-25 pooled and on 2025-26 alone.
       **A market has information only when both intervals lie wholly below zero;** otherwise
       its nine cells close without a grid.
     - *Reported beside, never the gate:* the same test against each deciding book's own
       no-vig price (the prices that would be bet); the same test for the score-and-time model
       alone, without fouls (if it passes too, the gain is Pinnacle's lag from 7.1, not IG-2's
       inputs); and, for each cell that passes the house standard, its price range and its
       units split by whether the bet's side had outscored its opponent in the 2 minutes before
       the quote (the deciding books' own moneyline lag, which the rule does not remove).
     - *The grid, only for a market with information.* The side the model favours (its best
       offer's expected value is the higher), best of the 8 deciding books, −200 floor,
       DraftKings alone beside, expected value ≥ 0.02 / 0.05 / 0.08 (the harness's
       `run_cells`). The blind bets use Pinnacle's live no-vig as the fair price. The placebo
       shuffles the model's disagreement with Pinnacle between games on the same date, 20 runs,
       and adds it back to each game's own Pinnacle price. "Still offered at the next purchase"
       and closing-line value are not measured in play.
     - **IG-2's information test result (2026-10-17): both markets pass the gate as written, so
       the grid runs. The gain is Pinnacle's stored-price lag, not the model's inputs.**
       `python -m scripts.nba_ingame_ig2 --info` (log `ig2_info_log.txt`, numbers
       `ig2_info.json`, both beside the shared table). Change per quote, with the model minus
       without; negative means the model helps.
       - Moneyline log loss: −0.0331 (−0.0403 to −0.0258) on 4,390 decisions in 2021-22 →
         2024-25; −0.0281 (−0.0417 to −0.0144) on 1,304 in 2025-26. Every season is below zero.
       - Spread squared error of the final margin: −11.75 points² (−13.79 to −9.63) on 5,117;
         −13.74 (−17.79 to −10.01) on 1,528 in 2025-26.
       - The model nearly replaces Pinnacle: its weight in the stack is 0.87–1.01. On its own,
         its log loss is 0.522 against Pinnacle's 0.556, and its squared error 102.2 against
         113.9.
       - The score-and-time model without fouls does the same: −0.0330 (−0.0402 to −0.0258)
         and −11.73 (−13.75 to −9.66). The foul inputs add nothing measurable. By the line
         written above, this gain is Pinnacle's lag (7.1), not IG-2's inputs.
       - Against the prices that would be bet (each deciding book's own no-vig), the moneyline
         gain covers zero: −0.0013 (−0.0036 to +0.0009), and +0.0011 (−0.0032 to +0.0054) in
         2025-26. The spread gain does not: −0.80 points² (−1.34 to −0.24), and −1.25 (−2.32 to
         −0.15) in 2025-26.
       - The model fit on 89,650–102,036 game states per season; 17 games whose play-by-play
         final differs from the official score were left out of fitting.
     - **IG-2's grid result (2026-10-17): 6 of 18 cells pass the house standard. Every warning
       sign written down beforehand is present, so the profit may be stale soft-book quotes
       rather than a price a bettor could take.** `python -m scripts.nba_ingame_ig2 --grid`
       (log `ig2_grid_log.txt`; cells `cells_IG-2.parquet`; verdict
       `verdict_house_IG-2.parquet`), and `--detail` for the beside-numbers
       (`ig2_passing_detail.json`). Pooled 2021-22 → 2025-26; 2020-21 is in-sample and left out.

       | Cell | Bets | Units | ROI | 95% interval | Seasons positive | 2025-26 | DraftKings alone, 2021-22 → 2024-25 / 2025-26 | Prices (min / median / max) |
       |---|---|---|---|---|---|---|---|---|
       | spread, Q1–Q2, EV ≥ 0.05 | 1,475 | +103.6 | +6.2% | +1.4 .. +11.1 | 4 of 5 | +6.0% on 334 | +3.9% / −1.3% | −160 / −114 / +114 |
       | spread, Q1–Q2, EV ≥ 0.08 | 948 | +69.5 | +6.5% | +0.4 .. +12.7 | 5 of 5 | +0.2% on 210 | +1.0% / −1.4% | −152 / −114 / +114 |
       | moneyline, Q3, EV ≥ 0.05 | 651 | +40.1 | +10.0% | +0.1 .. +19.9 | 5 of 5 | +6.7% on 159 | −1.5% / −1.1% | −200 / +210 / +3500 |
       | moneyline, Q3, EV ≥ 0.08 | 545 | +49.6 | +15.8% | +3.8 .. +27.4 | 5 of 5 | +13.0% on 134 | +2.1% / −5.1% | −200 / +230 / +3500 |
       | spread, Q3, EV ≥ 0.05 | 1,055 | +79.6 | +6.7% | +1.2 .. +12.6 | 5 of 5 | +5.5% on 286 | +7.2% / −3.6% | −144 / −114 / +125 |
       | spread, Q3, EV ≥ 0.08 | 751 | +76.8 | +9.2% | +2.5 .. +16.2 | 5 of 5 | +2.3% on 227 | +10.6% / −11.9% | −144 / −113 / +125 |

       - The other 12 fail. Every Q1–Q2 and Q4 moneyline cell fails the interval and the season
         count. The Q1–Q2 spread, Q3 moneyline and Q3 spread cells at EV ≥ 0.02 fail the interval
         alone. The Q4 spread cells fail the placebo, two of them the interval as well.
       - 7 of the 18 cells clear the 95% interval, against about 0.5 expected by chance. So the
         effect is systematic. What it is, these say:
       - **Without outlier prices** (a price more than 20 cents better than the next book's, or a
         number no other book hangs; about half of every passing cell's bets), the units fall to
         +21.7 and +22.0 (Q1–Q2 spreads), −4.1 and +8.0 (Q3 moneylines), +42.7 and +41.0 (Q3
         spreads).
       - **Bets on the side that had just outscored its opponent** in the 2 minutes before the
         quote earn more in every cell: Q1–Q2 spread at EV ≥ 0.05, +8.0% on 727 bets against
         +4.5% on 748; Q3 moneyline at EV ≥ 0.05, +18.7% on 277 against +2.5% on 374; Q3 spread
         at EV ≥ 0.05, +8.9% on 507 against +4.7% on 548. That is the deciding books' own lag
         that the freshness rule does not remove (7.1).
       - **DraftKings alone** loses in 2025-26 in all six (−1.1% to −11.9%). The best of 8 books,
         quoted up to 60 s apart during play, picks the price that has moved least.
       - **The Q3 moneyline cells are underdog bets** (516 of 651, and 446 of 545). The blind
         Q3 underdog at the best price earns +6.5% pooled. FanDuel carries the most units in
         every passing cell (+21.5 to +69.6).
       - The information test above already showed that the foul inputs add nothing and that
         against the deciding books' own moneyline prices the model adds nothing.
       - Whether any of these prices could be bet cannot be measured from hourly purchases. A
         book's stamp is its last update, not the moment it set the price, and books suspend
         betting after a score. Section 7.3 item 3 says a passing cell is built LIVE. That needs
         an NBA in-play loop, which does not exist; the decision is the owner's.
2. **Bars for a grid that runs:** the house standard of §6.7. The §6.4 bars and the
   multiple-testing count (now 4,226 with these 54) are reported beside.
3. **A cell that passes is built LIVE.** That needs an NBA in-play loop; `ncaaf_live/` is the
   template.

### 7.4 Purchases, only if a free test shows information

- HT-1's full set of halftime snapshots: 117,270 credits for 2021-22 → 2025-26 (measured grid).
- The 5-minute in-play archive, to replay a rule that bets the first time a price crosses its
  cut: 586,710 credits for moneyline only, 1,760,130 for all three markets.

## 8. Fourth search: pre-game moneyline, spread, total, first half, first quarter, team totals (pre-registered 2026-10-18, before any grid)

mike, 2026-10-18: *"I want pre game ml / spread / totals. Also look at 1q 1H."* The in-game
build was stopped; nothing in-game ships. Two gaps made this search:

- Nothing pre-game outside §6.7 was ever judged under the house standard. That covers the first
  search's 978 full-game cells and its 2,772 first-half / first-quarter / team-total cells.
- The recipe behind the newest profitable game-market model here, `nhl_moneyline`, was never
  tried for NBA. That recipe is the market's own no-vig price as an unpenalised offset, moved
  by an L2 model on prior-game inputs (`models/nhl_moneyline_anchored.py`).

**Bars: the house standard of §6.7, from the start**, applied once to every cell below. The
derivative markets pool their graded seasons (2024-25 and 2025-26, plus 2023-24 once bought).
Expected passes by chance at the interval alone: about 2.5% of cells, reported beside.

**Data added:** 2023-24 first-half, first-quarter and team-total prices at tip − 60, bought
2026-10-18 (~86,000 credits; the floor for this run was 2,000,000).

| # | Family | Markets × sides | Decision | Cut axis | Cells |
|---|---|---|---|---|---|
| P1 | **Market-anchored model (the NHL recipe).** Offset = the market's no-vig at T (Pinnacle, else the deciding books' median): logit for moneylines, centre for spreads and totals. L2 on prior-game inputs only: second-search ratings (box score + adjusted plus-minus), the shooting-luck gap, availability from the injury report, rest / travel / schedule, pace. Walk-forward: fit on seasons before S. | full game: moneyline, spread, total × 2 sides; first half, first quarter: moneyline, spread, total × 2; team totals × over, under | full game at A, C and D; derivative markets at their purchase (D) | EV ≥ 0.02 / 0.04 / 0.06 / 0.08 | 128 |
| P2 | **The first search's market rules, re-graded on the shared harness.** Sharp vs soft at the same number (Pinnacle's no-vig against each deciding book). Off-market number (a deciding book's number differs from Pinnacle's). | the same markets × 2 sides | full game at A, B, C and D; derivative markets at D | same number: EV ≥ 0.00 / 0.01 / 0.02 / 0.03; off-number: gap ≥ 0.5 / 1 / 1.5 / 2 | 256 |
| P3 | **Second-search signals on the derivative markets.** The shooting-luck gap (F4) on first-half totals and team totals. The ratings projection (F1) on first-half and first-quarter moneyline, spread and total. | as named × 2 sides | D | F4: gap ≥ 1 / 2 / 3 / 4; F1: EV ≥ 0.02 / 0.04 / 0.06 / 0.08 | 72 |

**Settlement:** first-half and first-quarter markets settle on the period line scores
(`nba_period_scores`), never on the full-game score. Team totals settle on the team's own score.
**A cell that passes is built LIVE** as a pre-game model.

### 8.1 P1, the market-anchored model: choices fixed before any P1 cell was graded (2026-10-18)

Section 8 names the recipe; these lines fix everything it leaves open. Lab:
`scripts/nba_game4_p1.py`. None of them was chosen from a betting result.

**Seasons**

- **Full game:** 2021-22 → 2025-26 graded and pooled (2025-26 is still reported apart as the
  confirmation season). 2020-21 is a fitting season only: no earlier priced season exists to
  fit it on.
- **First half, first quarter, team totals:** the first season the cache prices is a fitting
  season only, for the same reason. With 2023-24 in the cache, 2024-25 and 2025-26 are graded.
  With the cache as it stood on 2026-10-18 (2024-25 and 2025-26 only), 2025-26 is the only
  graded season. The house standard's "seasons mostly positive" needs two seasons with 30 or
  more bets, so every one of these cells fails it until 2023-24 is in. That is the data, not a
  miss.
- `--full` reads which of these seasons the cache holds from row counts, requires all eight
  markets to hold the same seasons, and refuses a season priced on fewer than 90% of its games
  (a purchase still running).
- A model is fitted only on 300 or more training rows. Fewer means no model and no bet that
  season.

**The model**

- One model per market per decision point, trained on the same decision point's rows from
  earlier seasons. Team totals: one model for both teams' markets, one row per team, with a
  home flag.
- **Moneylines**, every period: `OffsetLogit` and `choose_C` from
  `models/nhl_moneyline_anchored.py`, imported unchanged. The offset is the log-odds of the
  market's no-vig home price, unpenalised. Penalty grid 0.003 to 0.3. The penalty is chosen on
  the last three training seasons that have 800 or more earlier rows, each scored by a fit on
  the seasons before it, by mean log loss. With no such season it is 0.003, the grid's first
  value.
- First-half and first-quarter moneylines are trained on decided periods only. A level period
  voids the two-way bet, so the no-vig price is the home side's chance given a winner.
- **Spreads, totals and team totals** (the centre): the same fit, on squared error.
  - Target: (result − the market's centre) divided by its spread on the training rows.
  - Inputs standardised on the training rows. Intercept unpenalised. Penalty and grid as above.
  - The penalty is chosen by the same rule, scored on mean squared error.
  - The model's centre is the market's centre plus the fitted move, in points.
  - It is priced through the same distribution the market's centre was solved through. A
    model with nothing to say returns the market's fair line exactly.
- **The market's number at T** is the shared harness's: Pinnacle's no-vig where it quotes,
  else the deciding books' median. A centre is solved through the spread of results around
  Pinnacle's last price on seasons before the graded one. For the derivative markets that last
  price is the purchase itself (tip − 60).

**Inputs** (each dated at or before T, built the same way for training and graded rows)

- **Ratings:** the second search's projected home margin and total at T. These are box-score
  plus-minus plus adjusted plus-minus from lineup segments, times projected minutes from the
  injury report (`scripts/nba_game2_projection.py`, its own walk-forward models).
- **Availability:** that projection's absence terms at T: minutes missing by player tier,
  starters out, Questionable or Doubtful exposure, first game back. Home minus away for margin
  models, home plus away for totals. Nobody missing reads 0.
- **Shooting luck:** the second search's gap (luck-adjusted minus raw, margin and total), from
  the season's games before the date. It reads 0 until both teams have 10 games this season.
- **Pace:** each team's as-of pace from the projection, home plus away.
- **Schedule** (`features/nba_schedule_features.py`): each team's rest days, back-to-back,
  third game in four nights, game number on the current road trip, miles travelled, time-zone
  shift; whether the venue is at altitude. Not the road trip's total length, which reads the
  schedule as it was played. Not national TV, which is filled in for three seasons only.
- **Team totals:** the team's own projected points ((total ± margin) / 2) and its own luck gap,
  its own and its opponent's absences and schedule, both paces, and the home flag.
- **Scaled to the period:** for the first half and first quarter, every input measured in
  points is multiplied by the period's share of full-game points, from period scores of
  seasons before the graded one. Within one fit that share is a constant, so after
  standardising it moves no prediction. It only states the inputs in the period's points.
- The first-half, first-quarter and team-total models decide at the per-game purchase (tip − 60,
  inside D's 45–75 minutes). The projection is recomputed at that moment, not taken from the
  full-game D fetch.

**Population**

- The 10-game early-season rule (CLAUDE.md §3) is not applied as a filter. Section 8 registers
  none, and the projection works from the first game on prior-season ratings, which is §3's own
  baseline. The bets in either team's first 10 games are counted beside every cell, so that
  window can be read on its own.
- A game with no model number (no projection, or no market number at T) is not in the cell's
  population, and so not in its blind comparison either.

**Placebo**

- 20 runs, seed = run number. The model's move off the market (in log-odds for moneylines, in
  points for centres) is shuffled between games on the same date in the same market. Each
  shuffled move is added to that game's own market number and re-priced. Shuffling the whole
  probability would hand each game another game's market price, which any model beats.

**Cells**

- Team totals form one group per side and cut (over and under × 4 cuts = 8 cells), both teams'
  markets pooled. One game can carry a bet on each team's total. Every bet keeps its real
  market.
- 72 full-game + 48 first-half and first-quarter + 8 team-total = **128**.

**Smoke run**

- 2020-21 has no earlier priced season. So `--smoke` fits on 2020-21 games dated before
  2021-03-10 (the day the season's second half began) and grades those from that date on. It
  checks the plumbing and is never a result. With one fitting season the penalty falls to
  0.003.
- The first-half, first-quarter and team-total cells run on synthetic games only.

Three more lines, 2026-10-18, still before any P1 cell was graded:

- A fitting season with no season before it (2020-21 for the full game; the first derivative
  season the cache holds) has its centres solved through its own season's spread of results,
  the shared harness's fallback. Those centres are only ever fitted on, never bet.
- With 2025-26 as the only graded derivative season, no choosing season is left. The placebo
  bar is judged on the choosing seasons, so it cannot pass either, as well as "seasons mostly
  positive". Both fail by construction until 2023-24 is in the cache.
- `--full` also refuses when no results folder is named, so P1's cells never land beside the
  second search's 422.

### 8.2 P2, the first search's market rules: choices fixed before any P2 cell was graded (2026-10-18)

Section 8 names the two rules and their cuts; these lines fix everything it leaves open. Lab:
`scripts/nba_game4_p2.py`. None of them was chosen from a betting result. The two rules are the
first search's own code, imported (`sharp_pairs` and `gap_candidates` in
`scripts/nba_game_market_lab.py`). They run on the shared harness's quotes, and only the harness
grades.

**Cells (256)**

- **Same number, 152 cells:** every market × 2 sides × EV ≥ 0.00 / 0.01 / 0.02 / 0.03. The full
  game's moneyline, spread and total at A, B, C and D make 96. The first half's and first
  quarter's at D make 48. Team totals at D make 8.
- **Off number, 104 cells:** spreads and totals only, because a moneyline has no number. The full
  game at A, B, C and D makes 64. The first half and first quarter at D make 32. Team totals at D
  make 8.
- **Team totals:** both teams' markets form one cell per side and cut, as in P1. A game can carry
  a bet on each team's total, and every bet keeps its real market. This is the only way the
  registered 256 adds up.
- One family label, `P2`, with the rule in its own column. So a gap cut is never read as an EV
  cut's neighbour.
- Expected to clear the 95% interval by chance alone: 256 × 0.025 ≈ 6.4 cells, before
  correlation.

**Same number**

- A deciding book is compared with Pinnacle only when both quotes come from the same purchase.
  This is the first search's rule. A soft quote from an earlier purchase could be a line that has
  since moved.
- Spreads and totals pair only at Pinnacle's number. Moneylines always pair.
- Pinnacle's no-vig price is the proportional one. There is no second method, because section 8
  registers no such axis.
- Expected value = Pinnacle's no-vig chance of the side × the book's decimal price − 1. A push is
  ignored, as in the first search. The harness hands a push's stake back and leaves it out of the
  denominator, so this is the value per unit risked when there is no push.
- The best qualifying offer at a deciding book is bet, at −200 or better.

**Off number**

- Again the deciding book and Pinnacle must be in the same purchase.
- The side the gap favours is bet. On a spread it is the side getting the extra points. On a
  total it is the under at a higher number, or the over at a lower one.
- That side's gap is the number the cut reads. The other side of the same quote reads minus the
  gap. A quote at Pinnacle's number reads 0. The gap is read to within 1e-9, as in the first
  search.
- There is no expected-value floor. Section 8 registers the gap alone.
- When several offers qualify, the best expected value is bet. Each offer is priced around
  Pinnacle: the centre is solved from Pinnacle's own number and price at the decision time, and
  the shape is the spread of past results (below). The first search's bell curve is not used.

**Which number a book hangs** (measured by counting quotes in the cache; no result was read)

- Two books, BetRivers and betPARX, list four to seven team-total numbers in one purchase.
- Those two and Hard Rock often list a single first-half or first-quarter number 2 or more points
  from Pinnacle's, while the median book sits within half a point of Pinnacle on most games.
  Their two prices sit about 22 points apart in implied chance, against about 3 for the other
  quotes: alternate lines, not disagreements.
- A book's number is its rung with prices closest to even, the first search's "main" rung. Ties
  go to the lower number.
- In the same-number rule, a book's rung at Pinnacle's number is used when it lists one. The first
  search compared every rung at Pinnacle's number.
- A first-half, first-quarter or team-total spread or total more than 1 point from the median of
  the deciding books' numbers is an alternate line. It is never bet, never a blind bet, and never
  sets the market's fair line. This is the first search's ladder rule (1 point), extended to team
  totals. Pinnacle's quote is never dropped. The full game is not filtered this way: its
  purchases list one number per book and market (in 2024-25, 252 of 586,148 list two; those are
  read at the main rung).

**Pricing.** It orders offers at different numbers, prices the blind bets and names the
favourite. It never sets a rule's own number.

- **Full game:** the harness's. The spread of results around Pinnacle's last pre-game price, on
  seasons before the graded one.
- **First half, first quarter, team totals:** the spread of results around Pinnacle's number at
  the per-game purchase, on earlier seasons holding these prices, once they hold 300 or more
  games.
- The first season the cache prices these markets has no earlier one. It is priced on a stand-in
  that needs no first-half or team-total price, from the seasons before it:
  - first half and first quarter: the period's result around half (or a quarter) of Pinnacle's
    full-game closing spread or total, by minutes played;
  - team totals: F6d's recorded definition, imported. Each team's score around the team total
    Pinnacle's full-game close implies, both teams pooled, 300 or more earlier games.
- A season's own results never price it. A market with no pricing in a season has no blind bet
  and no off-number choice there.

**Seasons and decision points**

- **Full game:** A, B, C and D, the harness's. Choosing seasons 2021-22 → 2024-25, pooled with
  2025-26. 2020-21 is reported apart.
- **First half, first quarter, team totals:** D only, each game's one purchase when it falls 45–75
  minutes before tip.
- Every season the cache prices these markets in is graded: today 2024-25 and 2025-26, and
  2023-24 once its purchase lands. Nothing in P2 is fitted on these prices, so the first priced
  season is graded too (as in P3, unlike P1). The harness's choosing seasons are all of them but
  2025-26.
- `--full` lists these seasons from any row in the cache. So a season bought part-way is named,
  and then refused, because it is priced on fewer than 90% of its games. It always requires
  2024-25 and 2025-26.

**Not measurable on the first-half, first-quarter and team-total markets, reported as such**

- Closing-line value: one purchase per game, so there is no later price.
- "Still offered at the next purchase": there is no next purchase, so it reads 0.

**Placebo:** 20 runs, seed = run number.

- Same number: Pinnacle's no-vig chance is shuffled between games on the same date in the same
  market. Prices and numbers stay.
- Off number: the gap is shuffled among the offers on the same date, in the same market, on the
  same side. A placebo bets other offers at the same rate. Prices stay at the market's fair line.

**Smoke run:** the 160 full-game cells on 2020-21 alone, which checks the plumbing and is never a
result. The 96 first-half, first-quarter and team-total cells run on synthetic games only.

One more line, 2026-10-18, after the 2020-21 smoke and before any other P2 grade. It changes no
cell. `--full` also refuses when no results folder is named, so P2's cells never land beside the
second search's 422, which the pass/fail script would read together.

### 8.3 P3, the second search's signals on the derivative markets: choices fixed before any P3 cell was graded (2026-10-18)

Section 8 names the two signals and their cuts; these lines fix everything it leaves open. Lab:
`scripts/nba_game4_p3.py`. None of them was chosen from a betting result.

**Cells (72)**

- **Shooting luck (F4), 24 cells:** first-half total, home team total and away team total ×
  over / under × gap ≥ 1 / 2 / 3 / 4. The two team totals are separate cells, because that is
  the only way the registered 72 adds up. (P1 pools them; P3 does not.)
- **Ratings projection (F1), 48 cells:** first-half and first-quarter moneyline, spread and
  total × 2 sides × EV ≥ 0.02 / 0.04 / 0.06 / 0.08.
- Each signal carries its own family label (`P3_F4`, `P3_F1`). Both bet the first-half total
  at the same cut positions, so without the labels a gap cut would be read as an EV cut's
  neighbour.
- Expected to clear the 95% interval by chance alone: 72 × 0.025 ≈ 1.8 cells, before
  correlation.

**Decision and seasons**

- Each game's one per-game purchase, used only when it falls 45–75 minutes before tip (D).
  Measured on the cache: it reaches 99.5% of 2024-25 games and 99.0% of 2025-26 games, at a
  median 54 minutes before tip.
- **Graded: every season the cache prices these markets in**, today 2024-25 and 2025-26;
  2023-24 joins when its purchase lands. Nothing in P3 is fitted on derivative prices, so,
  unlike P1, the first priced season is graded too. All graded seasons are pooled. The
  harness's "choosing" seasons (which the placebo bar reads) are all of them but 2025-26.
- `--full` refuses any of these seasons priced on fewer than 90% of its games (a purchase still
  running), and always requires 2024-25 and 2025-26.

**Shooting luck: what the gap is**

- **First-half total:** F4's own full-game number, unscaled: the luck-adjusted minus the raw
  projected game total, in full-game points. The first half's line is taken to follow the
  same raw ratings, so the same number ranks the same games, and the registered cuts keep
  their §6.3 meaning (gap ≥ 3 is the near miss of §6.6 and §6.7). No share is fitted.
- **Team totals:** the team's own part of that number. That is the luck in its opponent's
  defence (the three-point and free-throw shooting the opponent allowed, replaced by the
  league's rate so far), times the game's pace, in that team's points. The home and away parts
  add up to F4's total gap.
- Everything else is F4's: box scores of the same season dated before the game; both teams
  with 10 or more games this season; a side bet at its best deciding offer under the market's
  fair line.

**Ratings projection: the period scaling**

- For each graded season S and each period (first half, first quarter):
  - the period's home margin = a + b × the projection's full-game home margin;
  - the period's total = a + b × the projection's full-game total.
- a and b are least squares on the projection's walk-forward numbers for seasons 2020-21
  through the season before S, at tip − 60, each calibrated by its own season's model. Only
  games whose period scores pass the first search's check are used. 2019-20 is left out: its
  projection has no calibration.
- The projection is priced with its own period error: that same fit's residuals, re-centred,
  as the harness's empirical distribution. Seasons before S only, with no fallback to S.
- **Moneyline:** the chance the period's home margin is above zero, out of above or below
  zero. A level period voids the bet, so that mass is removed.
- The graded number is the projection at the purchase instant; the fit's numbers sit at
  tip − 60. The projection itself (ratings, minutes, the injury report, its calibration) is the
  second search's, unchanged. There is no 10-game rule: F1 never had one.

**The market's own pricing** (the fair line that picks a side's best offer, the blind bets, the
favourite)

- **First-half and first-quarter spreads and totals:** the spread of the period's result around
  a + b × Pinnacle's full-game closing number (the home margin its spread implies, or its
  total). Fit on the seasons before S, from 2020-21; 300 or more earlier games; no fallback.
- **Team totals:** F6d's recorded definition (§6.5, third amendment), imported unchanged.
- The purchases' own prices are not used for this. The first priced season has no earlier one,
  so it would be priced on its own results.
- A season or market with no such pricing stops the run before any cell is graded.

**Not measurable here, reported as such**

- Closing-line value: one purchase per game, so there is no later price.
- "Still offered at the next purchase": there is no next purchase, so it reads 0.

**Placebo:** 20 runs, seed = run number. Shooting luck: the gap is shuffled between games on
the same date in the same market. Projection: its fair numbers are shuffled the same way.
Prices never move.

**Smoke run:** every P3 cell runs on synthetic games only. On real data `--smoke` prints counts
only: the seasons held, D coverage, and the games with a shooting-luck number.

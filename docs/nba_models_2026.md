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

**How it runs.** The five-minute window job projects each game at the tick about 60
minutes before tip (an ESPN injury pull, then the frame), storing every player's mean
in `nba_prop_projections`; at the next tick, inside the 45–57 window and after
`nba_prop_market` has decided the game, the card prices those projections on the newest
fetch. Each game is decided once (`nba_prop_projection_decisions`). The injury list each
game was projected with is kept in `nba_injury_asof`, which also holds the 2018-19..2025-26
history from the official report.

# NBA search: the starters and the first quarter (pre-registered 2026-10-31, before any cell was graded)

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find it"*.
He approved this idea from the sweep of what was missing.

**The idea.** Coaches play their starters more at the start of a game than across the whole of it.
So a team's strength in the first quarter is not its strength over the game: it leans toward its
starters' strength. A team with strong starters and a weak bench should play better than its
full-game number says in the first quarter. If the books set first-quarter numbers mostly from the
full-game number, those teams are mispriced.

**Written before any cell was graded. Nothing below changes after a result is seen; a later change
gets its own dated line and reason.** Lab: `scripts/nba_s_starters.py`. Pass/fail:
`scripts/nba_game2_verdict.py --house5` (`docs/nba_models_2026.md` §9.1's bars), then
`python -m scripts.nba_s_starters --credit`. No data is bought and nothing is written to the
database.

**What was read before this was written.** Prices, lines, minutes and the rating engine's fits, to
fix the rules below and count what they would do. No cell was run on real results, and no win, loss
or unit of any bet this search would place was computed. The lab's clock (section 10) runs on real
offers with made-up scores.

## 1. How much of the first quarter is starters (measured, not assumed)

From the lineup segments (`nba_stints`) and the box score's starter flag, regular season. The flag is
used only for this table. It is not known at decision time and feeds no number the search bets on.

| Season | Team-games | Starters' share of first-quarter minutes | First half | Full game | A starter's first-quarter minutes (of 12) | First half (of 24) | Full game (of 48) |
|---|---|---|---|---|---|---|---|
| 2018-19 | 2,452 | 71.7% | 64.1% | 61.8% | 8.6 | 15.4 | 29.9 |
| 2019-20 | 2,104 | 69.7% | 63.4% | 61.7% | 8.4 | 15.2 | 29.8 |
| 2020-21 | 2,158 | 72.2% | 64.9% | 62.7% | 8.7 | 15.6 | 30.3 |
| 2021-22 | 2,458 | 71.7% | 65.5% | 63.3% | 8.6 | 15.7 | 30.6 |
| 2022-23 | 2,460 | 71.4% | 65.5% | 64.1% | 8.6 | 15.7 | 31.0 |
| 2023-24 | 2,456 | 71.5% | 66.0% | 64.0% | 8.6 | 15.9 | 30.9 |
| 2024-25 | 2,458 | 69.9% | 65.4% | 63.2% | 8.4 | 15.7 | 30.5 |
| 2025-26 | 2,460 | 67.5% | 63.8% | 61.6% | 8.1 | 15.3 | 29.7 |

- **The first quarter is mostly starters, but less than the phrase suggests.** They play 68% to 72% of
  it against 62% to 64% of the game: six to ten points more. Close to a third of the quarter is bench.
- **The first half is close to the game:** two points more, at most three. Any first-half effect has to
  come through that, so those cells carry a small signal by construction.

## 2. What earlier searches did and did not cover

Sections below are `docs/nba_models_2026.md`'s.

| Search | What it tried on first-quarter and first-half markets | Whose minutes it used |
|---|---|---|
| First, §4.2 `derived` | the market's full-game number mapped to the period by one league-wide line | none |
| First, §4.2 `derived_team` | the same, with each team's share of its games' period points | none: results |
| Fourth, §8.3 `P3_F1` | a full-game ratings projection mapped to the period by one league-wide line | the whole rotation's full-game minutes |
| Fifth, §9 `F7` | team scoring and allowed shares from past period scores, shrunk toward the league | none: results |
| Fifth, §9 control | the market's full-game number × the league's period share | none |
| Eighth, §12 | a team's recent first-quarter cover and over/under records | none: results |

**None of them asks who is on the floor.** Each rates a team on its whole rotation or on its results.
§6.3's F5 values starters and absences, but only for full-game lines. The league-share idea has already
failed the house standard (§9.9: 0 of 48 controls), which is why this search is credited only with what
the tilt adds to it (section 8).

## 3. Data

All from the research cache, itself a cache of Supabase (`scripts/nba_research_cache.py`):

- **Period prices:** first-quarter and first-half spreads and totals at each game's one purchase, 45-75
  minutes before tip (decision point D, `H.per_event_times`), 2023-24 to 2025-26 (`odds`, `source =
  'odds_api_nba_derivative_history'`). Measured: 49 to 64 minutes before tip, median 54. The feed holds
  period markets from 2023-05-03, so no earlier season can be graded.
- **Full-game prices at T:** the slate fetches (`odds_api_historical`), read by §9.3's rule: each book's
  main number at the newest fetch at or before T, the fetch at most 60 minutes before T. The seventh
  search's injury-report purchases are left out, as `H.load` leaves them out for every other search.
- **Lineup segments:** `nba_stints`, regular season, five-a-side rows. 196 of 291,522 rows are not five
  a side and are dropped (2,704 seconds in all). 9,504 of 9,522 games fill both first periods within 5
  seconds. The ids match: 202,759 of 202,839 played box-score rows have segment minutes, and a player's
  summed segment minutes correlate 0.996 with his box-score minutes.
- **Ratings, availability:** `nba_player_game_adv`, `nba_player_game_log`, `nba_game_inactives`,
  `nba_injury_report`, through `scripts/nba_game2_projection.py` unchanged.
- **Period scores:** `nba_period_scores` through the first search's check (`H.with_periods`).

## 4. Definitions

**Decision time T:** each game's per-game purchase, kept only when it falls 45-75 minutes before tip.
Who starts is not known at T: lineups confirm later. **Nothing from the game itself is read:** no box
score, no lineup, no period score.

### 4.1 The minutes

For each player on the team's as-of roster or as-of injury report (the engine's `P.availability`):

- **P(plays):** the engine's. Out is 0. Doubtful, Questionable, Probable, Available and not listed are
  rates fit on the seasons before the graded one, by status (or role) and hours to tip. A report counts
  30 minutes after its printed time.
- **Recent minutes when he plays:** in every earlier game he played, his first-quarter minutes and his
  first-half minutes from the segments, time-weighted with the half-life the engine fits for full-game
  minutes (`min_hl`, 3 games). A game he played and sat out of the period counts 0. A game he missed is
  not read. A team-game whose segments miss 60 or 120 player-minutes by more than 1 is not read, so a
  hole in the file never looks like a benched player. Only games dated before today's.
- **Expected minutes in the period** = P(plays) × recent period minutes, rescaled across the team to
  **60 player-minutes (first quarter, nobody above 12)** and **120 (first half, nobody above 24)**, by
  the engine's `P.reallocate`.
- **Expected full-game minutes:** the engine's own (`min_proj`): to 240, its own per-player cap. The
  lab's full-game ratings are held equal to `P.project`'s on real games in `--smoke` and in a test.

**A limit stated now.** Rescaling is proportional. When a starter is Out, his first-quarter minutes
spread over everyone else in proportion to their own. The player who actually takes his place in the
lineup gets too few. No lineup is known at T, so nothing better is available from what is known.

### 4.2 The ratings

**The second search's engine, unchanged** (`scripts/nba_game2_projection.py`): each player's offence
`o` and defence `d` in points per 100 possessions as of T, a box-score rating plus adjusted plus-minus
from the lineup segments, walk-forward (season S fit on seasons before S; the segments refit every 7
days on games before the refit date).

**Its setup fits the two-hour limit, so it is used, not a simpler rating.** Measured 2026-10-30 to 31:
6,026 seconds (100 minutes) for all seven models, 2019-20 to 2025-26, on a machine at 100% CPU with
other labs running. Its fitted output was never saved before. It is now, under the lab's scratch folder
with a fingerprint of the cache and the engine's code, so a re-run reads it and repeats none of it.

### 4.3 The tilt

A team's rating under a set of minutes: O = Σ (minutes / the period's length) × o, and D the same with
d. Every set of weights sums to five players, so two ratings differ only by who plays. A positive D is
a good defence: the engine's efficiency is `eff_home = league + O_home − D_away`.

- **The tilt** = the period-weighted rating minus the full-game-weighted rating, both as of T, offence
  and defence apart: tO and tD, for each team.
- **Margin tilt** = (tO_home − tD_away) − (tO_away − tD_home).
- **Total tilt** = (tO_home − tD_away) + (tO_away − tD_home).
- **In points:** each × the period's possessions / 100. The possessions are the engine's as-of game
  pace (pace_home × pace_away / league) × 12/48 for the first quarter, 24/48 for the first half.

**Added 2026-10-31, before any cell was graded: a game has no tilt unless both teams' expected minutes
reach all three totals (60, 120 and 240), each within 1.** The lab checked the first two and not the
third. A team with exactly five available players fills both periods, since each of them plays all of
it, but stops at five times the engine's per-player cap over the game. Its full-game rating then carries
fewer than five players, so its tilt is a level error and not a change of who plays. What this moved is
in section 11.2.

### 4.4 The projected number

- **The base (no tilt):** §9.3's league-share projection, by calling its code
  (`G5.f7_projection`, `league_only`). The market's full-game fair centres at T, home margin M and total
  Tot (`H.market_fair`: Pinnacle's no-vig, else the deciding books' median), are split into team points
  H = (Tot + M) / 2 and A = (Tot − M) / 2. Period home points = H × the league's period share at home;
  away points = A × the league's share on the road. Each share is every team's period points over final
  points in the previous regular season plus this season before the date. Their difference is the base
  margin, their sum the base total.
- **Projected margin** = base margin + beta × margin tilt points.
- **Projected total** = base total + beta × total tilt points.

### 4.5 Beta

One beta per market (four) and per graded season.

- **Fit by least squares:** the period result minus the base, on the tilt points, over 2020-21 through
  the season before the graded one. **2023-24 reads 2020-21 to 2022-23; 2024-25 adds 2023-24; 2025-26
  adds 2024-25.** A graded season's own results never reach its own beta.
- **The fit's numbers sit at T = tip − 60** (the engine's `REF_LEAD`, §8.3's rule): no earlier season has
  a period purchase, and the full-game numbers come from the slate fetch by the same rule as 4.4. Each
  fit season's tilt comes from that season's own walk-forward model.
- **An intercept is fitted and not used,** so a level bias in the base cannot lean on the slope. The
  projection has no intercept: the level is the control's business.
- **No floor and no cap.** The sign is what was measured. This line was written before any beta was
  read.
- **Fewer than 300 earlier games stops the run.**
- `--full` refuses a refit other than the betas registered in section 11.

### 4.6 The gap and the bet

- **The gap** = the projected centre minus the **period market's fair centre at T**: `H.market_fair` on
  the period quotes, priced by §8.3's market pricing (`P3.period_market_pricing`). A centre is compared
  with a centre. Spreads are the HOME number throughout, so the centre is the home margin: a positive
  gap favours the home team. On totals a positive gap favours the over.
- **The bet** is a rule (§9.3): a side is bet when the gap in its favour reaches the cut, at its best
  deciding offer under the market's fair line. Every book's offer on a side carries the same gap,
  because §6.5 measures gaps against the market, never against each book's own number.
- **Books:** `config.BEST_LINE_BOOKMAKERS`, two-way quote coherent (1.00-1.15), −200 floor, each book's
  main number (`models/nba_book_numbers.visible_numbers`). DraftKings alone is reported beside every
  cell.

### 4.7 Impossible numbers, stated before anything is read

A row outside these ranges is filed wrong. It is dropped before anything is computed, and counted.

| Market | Allowed |
|---|---|
| Full-game total | 175 to 320 |
| First-half total | 85 to 170 |
| First-quarter total | 35 to 80 |
| Full-game spread | ±40 |
| First-half spread | ±25 |
| First-quarter spread | ±15 |

- **The total ranges do not overlap,** so a number filed under another period's market cannot pass.
  (Why it is here: §10.8's 191 rows filed as full-game totals at 9.5 to 107.5 looked like an edge.)
- **A visible main number priced past ±250 on either side** is not a main number and is dropped.

**What it found, read before this was written.**

- **11 of 836,532 stored pre-game full-game total rows:** seven Bovada rows at 1.0 in 2020-21 (Bovada
  never decides a bet); BetMGM at 155.5 three times on a game its book median put at 235.5 (2023-11-24,
  San Antonio at Golden State); William Hill at 136.5 on a game at 236.5 (2026-03-13, Utah at Portland).
- **No period row.** Every stored row is in range: first-quarter spreads −13.5 to 11.5 and totals 47.5
  to 70.5, first-half spreads −23.5 to 20.5 and totals 94.5 to 137.5.
- **The main numbers visible at T:** first-quarter spreads −9.5 to 7.5 and totals 48.5 to 67; first-half
  spreads −14.5 to 13 and totals 97 to 134.5; full-game spreads −24.5 to 21.5 and totals 199 to 262.
  Prices on the period numbers run −205 to +145 (the floor refuses anything under −200), on the full-game
  numbers −135 to +110. None is past ±250.
- **The highest-EV offers under the market's own fair line are disagreements, not bad rows.** The top is
  0.164: first-half total over at FanDuel's 115.5 at −115 (2025-12-03, Denver at Indiana), where Pinnacle
  hangs 119.5 and the other books 116.5 to 117.5. Pinnacle's main number is within 1 point of the deciding
  books' median on at least 98% of games in every market, and at most 3 points off.

## 5. The cells (32)

| Family | Market | Sides | Decision | Gap cuts, in points | Cells |
|---|---|---|---|---|---|
| S1 | first-quarter spread | home, away | D | ≥ 0.25 / 0.5 / 0.75 / 1.0 | 8 |
| S1 | first-quarter total | over, under | D | ≥ 0.25 / 0.5 / 0.75 / 1.0 | 8 |
| S1 | first-half spread (first-half minutes) | home, away | D | ≥ 0.5 / 1 / 1.5 / 2 | 8 |
| S1 | first-half total (first-half minutes) | over, under | D | ≥ 0.5 / 1 / 1.5 / 2 | 8 |
| **Total** | | | | | **32** |

The cuts are §9.2's: the full game's 1 to 4 points scaled by the period's share of the game. They were
fixed by that rule, not by looking at the gaps.

- **Bands (bar 5)** lie between the four cuts. The lowest cut's lower band starts at 0 and the top band
  is open (§9.1).
- **Seasons:** 2023-24, 2024-25 and 2025-26 graded and pooled. 2023-24 and 2024-25 are the choosing
  seasons the placebo reads (`P3.choosing`).
- **Settlement:** first-quarter and first-half points (`nba_period_scores`, `H.with_periods`). A push
  returns the stake and leaves the denominator (§6.2). A game whose period scores fail the check has no
  settlement and no bet.
- **Units:** one unit to win, risk capped at 3 (§6.2).

**A thin cell is still reported.** A cell under 200 pooled bets fails bar 1, and its bets, units, return,
interval and season split are printed anyway. Its answer is "too few games to tell", not "it loses".

## 6. The bars

§9.1's house standard, unchanged, by `python -m scripts.nba_game2_verdict --results DIR --house5`:

1. Pooled over the graded seasons, 200 or more bets.
2. The pooled whole-day bootstrap 95% interval of the return is above zero (4,000 resamples, seed 7).
3. At least two graded seasons have 30 or more bets, and of those all but at most one are positive.
4. Beats the blind bet on its dominant real side, pooled (§6.4's bar 9).
5. The band just below the cut and every band from the cut to the top each have a positive pooled
   return, where they hold 30 or more bets; and the cell's own pooled return is above zero.
6. The cell's return on its choosing seasons beats the 95th percentile of 200 placebo runs, a run with
   no bet counting as 0.

Closing-line value cannot be measured: one purchase per game, so the decision quote is the last one.
"Still offered at the next purchase" reads 0 for the same reason.

## 7. The placebo

**Registered: 200 runs, seeds 1-200. Each game's whole gap is moved to another game on the same date
in the same market** (§9.8's placebo for the control). Each game keeps its own offers and prices. The
cell's rule is then applied to the moved gaps.

**Why not move only the tilt, as §9.3 moved team shares.** A placebo that repeats the real bets is no
null. In the total cells the base's own distance from the market dwarfs the tilt's part, so moving the
tilt would repeat almost every bet and the bar could never be passed. Measured on the real prices, with
no result read: the share of placebo bets that are not the real bets, 10 runs per cell, lowest to
highest cell in each market.

| Market | Whole gap (registered) | The most any shuffle could reach | Tilt moved alone |
|---|---|---|---|
| First-quarter spread | 0.55 to 0.85 | 0.64 to 0.96 | 0.45 to 0.81 |
| First-quarter total | 0.41 to 0.55 | 0.46 to 0.63 | 0.00 to 0.01 |
| First-half spread | 0.66 to 0.90 | 0.76 to 1.00 | 0.25 to 0.67 |
| First-half total | 0.40 to 0.52 | 0.45 to 0.59 | 0.00 to 0.03 |

- **The middle column is a limit of the cell, not of the placebo.** A cell that bets half of a market's
  games repeats half of them under any shuffle, so its limit is 1 minus the share of games it bets. The
  totals' low shares come from that breadth: the first-quarter under at gap 0.25 bets 1,986 of 3,667
  games.
- **A date is not the limit.** 0.14% of the market-game rows are alone on their date, and the median game
  shares its date with 8 others. The registered shuffle sits about 10 points under the limit because
  some nights lean one way together.
- **What this placebo cannot separate, the credit rule does (section 8).** A cell earning only from the
  league-share part beats these shuffles too. It fails credit unless it also beats its control.
- **Reported beside every S1 cell, never a bar:** the same 200 runs with only the tilt moved
  (`tilt_placebo_mean`, `tilt_placebo_p95`), so a cell that passes can be read against what the tilt
  alone was worth. In the total cells that number repeats the cell and says little.

## 8. The control and the credit

- **`S1_league`: the same 32 cells on the base alone** (section 4.4): §9's control with no tilt, on the
  same games as the S1 cells, so the two compare like with like.
- **It is judged under the same six bars, with its own 200 placebo runs.** It carries no `control_`
  prefix so that `--house5`, unedited, judges it. A control that passes is a strategy like any other
  (§9.8) and is built live.
- **Credit.** An S1 cell counts for the starters only when it passes **and** its pooled return beats its
  control's at the same market, side and cut. A control with no bet counts as 0.
- **A total cell earns no credit for the starters (added 2026-10-31, before any cell was graded).** A
  total cell and its control place nearly the same bets: on the first-half over at the lowest cut, 0
  bets are only the cell's and 1 only the control's, of about 1,620. The widest of the 16, the first-half
  under at 2, has 100 and 15 of about 1,700 (section 11.5). One beating the other is then luck on a small
  share of the games, not a reading of the starters. It is settled now because changing it after a result
  would be choosing a rule with the result in view. A total cell is still judged under the six bars and
  reported, and a pass there reads as the league-share idea's. Only the 16 spread cells can earn credit.
- **Read credit from `python -m scripts.nba_s_starters --credit --results DIR`.** The verdict's own
  printed "credited" count knows only §9's control, so for S1 it equals the passes. The lab calls the
  verdict's own function with this search's pairing (`house_verdict_bands(credit={"S1": "S1_league"})`),
  then takes the total cells' credit away, so the verdict script stays as it is.

## 9. Expected passes by chance

32 × 0.025 ≈ 0.8 cells clear bar 2 alone, before correlation; 64 × 0.025 ≈ 1.6 with the control. The
cuts are nested and the two sides of a market mirror each other, so the cells are far from independent.
Bars 3 to 6 make a chance pass rarer still.

**A pass is built live** (`CLAUDE.md` §2) with its own EV floor and the prices it lays stated before it
ships. No first-quarter line is stored for any 2026-27 game (§12.1), so it needs that capture first.

## 10. What the lab does and how long it takes

- `--smoke`: the synthetic checks, then real counts and inputs only, never a graded real bet.
- `--full` refuses unless `NBA_GAME2_GO=1`, `NBA_GAME2_RESULTS` and `NBA_GAME2_BETS` are set and the
  ledger and segments are in the cache. It refuses a cache pricing fewer than 90% of a graded season,
  derivative purchases other than exactly 2023-24 to 2025-26, and a beta refit other than section 11's.
  It writes `cells_S1.parquet` and `cells_S1_league.parquet` only after both families are built, with
  their population tables, gaps and the beta fit. It prints a line per market.
- **A placebo run is a lookup.** A rule's gap is the same for every offer of a side, so the offer a cut
  would bet on a game never changes: each game's bet is graded once and each of the 200 runs reads it
  from arrays. A test, and `--smoke` on real offers with made-up scores, hold this equal to the harness's
  own frame-by-frame path.
- **The clock:** one placebo run on the real offers, with made-up scores in place of the real ones so
  no real bet is graded, is timed in `--smoke`, which prints the projected `--full` time and memory.
- **Bets are saved** through the harness's own column list: no shape column parquet cannot store.
- **What is saved:** under `NBA_S_STARTERS_SCRATCH`, the engine's fitted models, the per-player and
  per-game frames at each T, and the market pricing, each with a fingerprint of the cache files and code
  it came from. All of it is regenerable from the cache. A different fingerprint rebuilds.

## 11. Counts before grading

Counted 2026-10-31 by `python -m scripts.nba_s_starters --smoke` on the research cache, before any
cell was graded. No win, loss or unit of any bet this search would place was computed. Period
results were read only to fit the betas, each from seasons before the one it serves.

### 11.1 Games per season

| Season | Games | A purchase 45-75 minutes before tip | With the full-game numbers at T | With a tilt | With a gap | An injury report known at T |
|---|---|---|---|---|---|---|
| 2023-24 | 1,230 | 1,225 | 1,225 | 1,225 | 1,225 | 1,224 |
| 2024-25 | 1,230 | 1,224 | 1,224 | 1,224 | 1,224 | 1,224 |
| 2025-26 | 1,230 | 1,218 | 1,218 | 1,218 | 1,218 | 1,218 |

No game with a purchase lacks a trusted period score, so none loses its bet for want of a settlement.

### 11.2 The betas (registered)

These are the numbers section 4.5 registers. `--full` stops on any refit more than 0.000001 away from
them. A second build of the frames from the saved engine returned them unchanged.

**Re-registered 2026-10-31, before any cell was graded.** Section 4.3's full-game check took one game out
of the fit: Miami at Houston, 2021-12-31. Miami had exactly five available players, so its period ratings
carried five players and its full-game rating 4.18. The game's first-half margin tilt read 3.72 points
toward Miami, 14 times the spread of all fit games, and that one game moved all 12 slopes. Toronto at
Cleveland (2021-12-26) also misses 240, with four available players, but the period check already had it
out. No graded game has the fault: 0 of 3,667 miss 240, and every saved number for them is unchanged.
Sections 7 and 11.3 to 11.6 are refreshed from the same run. The most any cell's bets moved is from 648
to 628, on the first-half spread's home side at cut 0.5.

| Serves | Fit on | Games | Market | Beta | Standard error | Intercept (not used) | Spread of the tilt points |
|---|---|---|---|---|---|---|---|
| 2023-24 | 2020-21 to 2022-23 | 3,537 | First-quarter spread | 2.107162026982248 | 0.54 | -0.08 | 0.26 |
| | | | First-quarter total | -0.098573933763044 | 0.61 | 0.29 | 0.23 |
| | | | First-half spread | 0.9411084472871227 | 0.73 | -0.25 | 0.25 |
| | | | First-half total | -1.68714999789803 | 0.96 | 0.41 | 0.21 |
| 2024-25 | 2020-21 to 2023-24 | 4,767 | First-quarter spread | 2.203032914132867 | 0.45 | -0.07 | 0.26 |
| | | | First-quarter total | 0.06025273111144231 | 0.53 | 0.09 | 0.22 |
| | | | First-half spread | 0.7863756878703179 | 0.62 | -0.15 | 0.26 |
| | | | First-half total | -0.5410796090850172 | 0.85 | 0.13 | 0.21 |
| 2025-26 | 2020-21 to 2024-25 | 5,997 | First-quarter spread | 2.0280488442860056 | 0.40 | -0.10 | 0.27 |
| | | | First-quarter total | 0.4173753654979911 | 0.49 | 0.06 | 0.21 |
| | | | First-half spread | 1.3755058880342714 | 0.54 | -0.19 | 0.26 |
| | | | First-half total | -0.3293699607192663 | 0.78 | 0.11 | 0.20 |

What the re-registration moved:

| Market | 2023-24 | 2024-25 | 2025-26 |
|---|---|---|---|
| First-quarter spread | 2.153 to 2.107 | 2.235 to 2.203 | 2.054 to 2.028 |
| First-quarter total | -0.049 to -0.099 | 0.098 to 0.060 | 0.449 to 0.417 |
| First-half spread | 1.072 to 0.941 | 0.887 to 0.786 | 1.434 to 1.376 |
| First-half total | -1.474 to -1.687 | -0.385 to -0.541 | -0.197 to -0.329 |

- **The first-quarter spread's slope is about two and clear of zero.** Over earlier seasons, a point of
  tilt came with about two points of first-quarter margin beyond the league-share number.
- **The total slopes cannot be told from zero.** All six sit within 1.8 standard errors of it.

### 11.3 How far the projection sits from the period market

Over all 3,667 decisions, in points. "The books' slope" is the market's centre minus the base, on the
tilt points: how much of a tilt point the books' number already holds. No result is read for it.

| Market | Gap | Gap, control | The tilt's part | Tilt points | Correlation, control's gap with the tilt's part | The books' slope |
|---|---|---|---|---|---|---|
| First-quarter spread | 0.59 | 0.55 | 0.57 | 0.27 | -0.46 | 0.94 |
| First-quarter total | 1.42 | 1.43 | 0.06 | 0.19 | -0.11 | -0.11 |
| First-half spread | 0.68 | 0.70 | 0.28 | 0.27 | -0.27 | 0.71 |
| First-half total | 2.92 | 2.92 | 0.21 | 0.18 | -0.03 | -0.13 |

- **The control's column equals §9.6's** (0.55, 1.43, 0.70, 2.92), so the base is the same number that
  search graded.
- **The search has something to say on the first-quarter spread, some on the first-half spread and
  almost nothing on the totals.** The tilt's part is as large as the control's gap on the first, under
  half of it on the second, and 4% and 7% of it on the two totals.
- **The total cells are their controls** (11.5). Their bets are 94% to 100% the control's, so a total
  cell cannot show what the starters add. They are graded as registered, and section 8 gives them no
  credit.
- **The books already hold the tilt in part.** They move 0.94 of a tilt point on the first-quarter spread
  against the earlier seasons' 2.03 to 2.20, and 0.71 on the first-half spread against 0.79 to 1.38. That
  difference is the whole case for an edge here, and it is what the cells test.

**How well the expected minutes did** (root mean square error per player row at T against what happened;
"flat" is a quarter or a half of his expected full-game minutes).

| Season | Rows | First quarter | Flat | First half | Flat |
|---|---|---|---|---|---|
| 2023-24 | 44,601 | 1.88 | 1.99 | 3.41 | 3.43 |
| 2024-25 | 44,808 | 1.88 | 1.94 | 3.40 | 3.38 |
| 2025-26 | 44,519 | 1.88 | 1.93 | 3.41 | 3.41 |

The first-half minutes are no closer than the flat share, which agrees with section 1.

**Which teams lean furthest.** Mean first-quarter offence plus defence tilt in 2024-25, in points per
100 possessions: Denver +2.44, Oklahoma City +1.96, the Clippers +1.54, the Lakers +1.44, Cleveland
+1.30; San Antonio -0.34, Washington -0.01. Averages across the league sit above zero (offence +0.49,
defence +0.18, all three seasons) because starters rate above benches. Only the difference between two
teams reaches a spread.

### 11.4 Games per band of the gap, each side

A game counts on the side its gap favours. These are games, not bets.

| Market | Side | Below the lowest cut | Band 1 | Band 2 | Band 3 | Top band |
|---|---|---|---|---|---|---|
| First-quarter spread (0.25 / 0.5 / 0.75 / 1) | home | 593 | 548 | 382 | 207 | 185 |
| | away | 639 | 476 | 330 | 155 | 152 |
| First-quarter total (same cuts) | over | 31 | 31 | 71 | 171 | 1,346 |
| | under | 31 | 80 | 158 | 302 | 1,446 |
| First-half spread (0.5 / 1 / 1.5 / 2) | home | 1,087 | 438 | 139 | 44 | 7 |
| | away | 1,084 | 521 | 262 | 64 | 21 |
| First-half total (same cuts) | over | 8 | 5 | 23 | 96 | 1,499 |
| | under | 13 | 23 | 79 | 190 | 1,731 |

Bar 5 judges a band once it has 30 bets. **On the totals the bands below the top hold few games: the cuts
were fixed by §9.2's rule and most games clear all of them.**

### 11.5 The bets each cell would place

An offer at a deciding book at −200 or better; counted, never graded.

| Market | Side | Cut | 2023-24 | 2024-25 | 2025-26 | Pooled | Control, pooled | Share also the control's | Only the cell's | Only the control's |
|---|---|---|---|---|---|---|---|---|---|---|
| First-quarter spread | home | 0.25 | 491 | 455 | 376 | 1,322 | 1,168 | 0.53 | 625 | 471 |
| | | 0.5 | 294 | 281 | 199 | 774 | 614 | 0.39 | 470 | 310 |
| | | 0.75 | 155 | 139 | 98 | 392 | 329 | 0.33 | 263 | 200 |
| | | 1 | 64 | 73 | 48 | 185 | 170 | 0.27 | 135 | 120 |
| | away | 0.25 | 315 | 409 | 389 | 1,113 | 1,019 | 0.49 | 570 | 476 |
| | | 0.5 | 179 | 250 | 208 | 637 | 613 | 0.43 | 360 | 336 |
| | | 0.75 | 75 | 134 | 98 | 307 | 330 | 0.38 | 191 | 214 |
| | | 1 | 39 | 71 | 42 | 152 | 138 | 0.30 | 106 | 92 |
| First-quarter total | over | 0.25 | 568 | 580 | 471 | 1,619 | 1,615 | 1.00 | 4 | 0 |
| | | 0.5 | 563 | 562 | 463 | 1,588 | 1,579 | 0.99 | 9 | 0 |
| | | 0.75 | 557 | 509 | 451 | 1,517 | 1,509 | 0.99 | 9 | 1 |
| | | 1 | 534 | 401 | 411 | 1,346 | 1,327 | 0.98 | 25 | 6 |
| | under | 0.25 | 619 | 625 | 742 | 1,986 | 1,982 | 1.00 | 5 | 1 |
| | | 0.5 | 561 | 608 | 737 | 1,906 | 1,903 | 1.00 | 7 | 4 |
| | | 0.75 | 457 | 562 | 729 | 1,748 | 1,740 | 0.99 | 14 | 6 |
| | | 1 | 268 | 469 | 709 | 1,446 | 1,448 | 0.99 | 14 | 16 |
| First-half spread | home | 0.5 | 187 | 259 | 182 | 628 | 575 | 0.74 | 166 | 113 |
| | | 1 | 49 | 85 | 56 | 190 | 218 | 0.81 | 37 | 65 |
| | | 1.5 | 14 | 26 | 11 | 51 | 76 | 0.84 | 8 | 33 |
| | | 2 | 1 | 5 | 1 | 7 | 9 | 0.71 | 2 | 4 |
| | away | 0.5 | 264 | 255 | 347 | 866 | 839 | 0.79 | 179 | 152 |
| | | 1 | 83 | 114 | 149 | 346 | 393 | 0.84 | 55 | 102 |
| | | 1.5 | 17 | 34 | 33 | 84 | 118 | 0.79 | 18 | 52 |
| | | 2 | 3 | 9 | 9 | 21 | 12 | 0.33 | 14 | 5 |
| First-half total | over | 0.5 | 565 | 586 | 470 | 1,621 | 1,622 | 1.00 | 0 | 1 |
| | | 1 | 563 | 584 | 469 | 1,616 | 1,619 | 1.00 | 1 | 4 |
| | | 1.5 | 554 | 574 | 465 | 1,593 | 1,606 | 1.00 | 1 | 14 |
| | | 2 | 521 | 523 | 453 | 1,497 | 1,531 | 1.00 | 5 | 39 |
| | under | 0.5 | 648 | 632 | 736 | 2,016 | 2,020 | 1.00 | 1 | 5 |
| | | 1 | 629 | 628 | 736 | 1,993 | 1,984 | 0.99 | 14 | 5 |
| | | 1.5 | 572 | 613 | 729 | 1,914 | 1,872 | 0.97 | 56 | 14 |
| | | 2 | 447 | 560 | 717 | 1,724 | 1,639 | 0.94 | 100 | 15 |

- **Seven of the 32 cells cannot reach 200 bets** and fail bar 1 by construction: the first-quarter spread
  at cut 1 on both sides (185, 152), and the first-half spread at 1 (home, 190), 1.5 (51, 84) and 2 (7,
  21). They are graded and reported as "too few games to tell".
- **The first-quarter spread is where the tilt changes the bets:** only 27% to 53% of its bets are also
  the control's. So those eight cells are the real test.
- **The last two columns are what section 8's credit rule rests on.** On the 16 total cells, 0 to 100
  bets are only the cell's and 0 to 39 only the control's. On the first-quarter spread it is 106 to 625
  and 92 to 476; on the first-half spread, 2 to 179 and 4 to 152.
- **2025-26 leans to the under on both totals** (742 under against 471 over at the first quarter's lowest
  cut; 625 against 580 in 2024-25). The cells' bets are the control's there, so the lean comes from the
  league-share base, not the tilt. Bar 4, the blind bet, is what answers it.

### 11.6 What the rest of the smoke run measured

- **The placebo on the real prices** is section 7's table: the mean share of placebo bets differing from
  the real bets is 0.61 for the cells and 0.61 for the controls.
- **The extremes and the impossible-number rule** read as section 4.7 states.
- **The lab's full-game team ratings are the engine's.** The largest difference from `P.project` on 40
  real games per season at their T is 0.00000000000002 points per 100 possessions, and 0 on pace.
- **The clock.** One placebo run takes 0.004 seconds (0.09 to 0.11 frame by frame). The two paths agreed
  on the real offers with made-up scores. One cell without its placebo takes 1.3 to 1.4 seconds. Setup,
  with the engine, the market pricing and the frames saved, took 0.7 minutes.
- **`--full` is projected at 3.5 minutes with everything saved.** With the engine and the market pricing
  gone it is 112 minutes: the engine's 6,026 seconds and the market pricing's 463 as they were built,
  plus those 3.5.
- **Peak memory in `--smoke` was 2.9 GB.** The engine's own build did not record its peak.
- **`--full`'s own path ran on the real cache up to the line before the first cell,** stopped there by a
  scratch script: its coverage check passed and the betas matched. No cell ran.


## 12. Results (graded 2026-11-01)

Run `2026-11-01-starters`, stored in Supabase. 32 cells, and the same 32 on the league share alone as the control.

**0 of the 32 cells pass, and none clears the 95% interval. The family stays closed.** Of the 64 rows, 51 hold 200+
bets, with a median return of -1.82% and 8 positive. The grade took 297 seconds.

| Market | Cells | Most bets | Best units | Best return | Worst return |
|---|---|---|---|---|---|
| First-quarter spread | 8 | 1,322 | +1.22 | +0.6% | -23.4% |
| First-quarter total | 8 | 1,986 | +12.28 | +0.8% | -1.6% |
| First-half spread | 8 | 866 | +2.85 | +37.0% | -8.9% |
| First-half total | 8 | 2,016 | -1.33 | -0.1% | -3.6% |

The first-half spread's +37.0% is 7 bets, and not a near miss. The best cell with a real sample is the
first-quarter total, over, tilt 1.0: 1,346 bets, +12.28 units, +0.8%, interval -4.4% to +6.0%. The league-share
control's best with a real sample is the same market and side at 0.75: 1,509 bets, +7.46 units, +0.4%, interval
-4.3% to +5.5%. So knowing who starts, and how much of the first quarter they play, did not separate from
the market. **This closes the starters idea for the first quarter, and does not close first-quarter betting**:
first-quarter player props and first-quarter team totals have not been graded, because their prices have not been
bought.

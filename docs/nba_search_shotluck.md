# NBA search: shooting luck from shot location (pre-registered 2026-10-30, before any cell was graded)

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find
it"*. This is rank 2 of the sweep that answered him: measure shooting luck from where each shot
was taken, for and against, and bet the gap on full-game totals, full-game spreads and team
totals.

**Written and committed before any cell was graded. Nothing below changes after a result is seen;
a later change gets its own dated line and reason.** Lab: `scripts/nba_s_shotluck.py`. Pass/fail:
`python -m scripts.nba_game2_verdict --results DIR --house5` (the bars of
`docs/nba_models_2026.md` 9.1). No data is bought and nothing is written to the database. "The
record" below means `docs/nba_models_2026.md`.

## 1. What is tested and why

Shooting luck is the only NBA game signal that has passed: the full-game over (record 6.7, live as
`nba_total_luck`) and the home team-total under (record 8.4, live as `nba_team_total_luck`). Both
measure luck crudely: how well a team's opponents happened to shoot threes and free throws,
against the league's rate.

A finer measure exists. A shot's location carries most of what a team controls about its quality.
Whether it drops is largely luck over a few dozen games. Expected points from location separate
the two. A defence that gave up layups and corner threes that happened to miss is luckier than its
three-point percentage says; a defence that forced long twos that happened to drop is unluckier.
Offences have the same luck, and no earlier search graded it. If the market prices totals and
spreads off points scored and allowed as they were played, removing this luck should pick games
better than the crude measure does.

The honest doubt: a team's own shooting is partly skill, so the offence's "luck" holds talent as
well as luck. The gap below removes both anyway, because that is the question the sweep asks, and
a control (section 8) reports the offence and the defence apart.

## 2. What earlier searches covered, and what they did not

| Search | What it graded | Result | What it did not cover |
|---|---|---|---|
| F4 (record 6.3, 6.6, 6.7) | Opponents' three-point and free-throw luck on full-game totals and spreads, at A and C, gap ≥ 1 / 2 / 3 / 4 | 4 of 422 cells pass, all the over: at C, gap ≥ 3, 508 bets, +55.6 units, +10.1%. Spreads fail; listed closed in record 9 | Twos of any kind, shot location, and any offence's luck: F4's offence is "left as played" |
| P3_F4 (record 8.3, 8.4) | The same gap on first-half totals and both team totals, at the per-game purchase | Home team-total under at part ≥ 2: 349 bets, +64.7 units, +16.6%. It would fail the 9.1 band bar: its band from 1 to 2 lost 6.3% on 540 bets | Same as above |
| F8 (record 9.4, 9.9) | The same two signals in the first 10 games, blended with last season | Too few games to tell | Same as above |

**The own-shooting term was never graded.** A term pulling each team's own three-point percentage
toward the league came from the build instructions, not from 6.3, and was removed before any
priced season was graded (record 6.5, corrections inside the labs). So "shooting luck on the spread
failed" in the record is a statement about defence-only luck in threes and free throws. It does
not cover this gap. Shot coordinates have been read only to tell twos from threes and to spot
end-of-period heaves (`data/ingestors/nba_stints.py`, `scripts/nba_ingame_data.py`).

## 3. Data

**Shots:** Supabase `nba_pbp` through `nba_pbp_games`, regular-season games stored against a `games`
row (`season_type = 2`, `in_games`), read once, read-only, by primary key, in chunks of 40 games, on
2026-10-30 (`--pull` regenerates it). Every row with a shot value: 2,135,298 rows over 9,586 games.
The copy is a cache of Supabase at `NBA_SHOTS_CACHE`, default
`C:/Users/micha/AppData/Local/Temp/nba_s/shotluck/`.

**Everything else** comes from the research cache (`NBA_RESEARCH_CACHE`): `nba_games`, `nba_odds`,
`nba_fetch_ledger`, `nba_period_scores`, `nba_player_game_log`.

**Coverage, measured on the pull:**

| Season | Games | Field goals | With coordinates | Free throws | Plays do not add up to the final |
|---|---|---|---|---|---|
| 2018-19 | 1,230 | 219,451 | 100% | 56,759 | 5 |
| 2019-20 | 1,059 | 188,131 | 100% | 48,943 | 1 |
| 2020-21 | 1,080 | 190,967 | 100% | 47,135 | 0 |
| 2021-22 | 1,230 | 216,713 | 100% | 53,779 | 3 |
| 2022-23 | 1,230 | 217,161 | 100% | 57,863 | 5 |
| 2023-24 | 1,230 | 218,685 | 100% | 53,430 | 7 |
| 2024-25 | 1,230 | 219,525 | 100% | 53,313 | 2 |
| 2025-26 | 1,230 | 220,267 | 100% | 57,767 | 3 |
| 2026-27 so far | 67 | 12,004 | 100% | 3,405 | see below |

- Every game the cache holds as final in 2018-19 to 2025-26 has plays (`games` joined to
  `nba_pbp_games`, read 2026-10-30: 1,230 of 1,230, 1,059 of 1,059, and so on).
- **2026-27:** 67 of the 79 final games in `games` have plays (same query, by date, read
  2026-10-30). The 12 without: all 8 of 2026-10-30, which the pipeline has not reached yet, and **all
  4 of 2026-10-27** (`BKN_BOS`, `DET_NYK`, `POR_LAL`, `SAC_SAS`), though games on both sides of that
  date are stored. Flagged, not fixed here. All 67 came through ESPN's summary path
  (`source = 'espn_summary_api'`, `data.ingestors.nba_pbp.fill_gaps`). A live version of this search
  needs every game before the date, as `nba_total_luck` needs every box score.
- **The sweep's "25 of 33 shots" in 2026-27 is not a gap in shot locations.** Those rows include
  free throws, and free throws from the summary path carry no coordinates (0 of 3,405). Every field
  goal does (12,004 of 12,004). Free throws need none here.
- The coordinates agree with the text: distance from the basket at (25, 0) minus the text's "N-foot"
  is within 2 feet on every field goal that states a distance, in every season.
- `shot_value` is the ingestor's (`nba_stints.classify_field_goal`), and it stands over the
  geometry. 218 twos sit 24+ feet out and 15 threes sit under 21.5 feet by coordinates; each keeps
  its stored value.
- Three 2026-27 games (`NBA_2026-10-29_CLE_ATL`, `_SAC_NOP`, `_MEM_POR`) have plays and no score in
  the research cache, which predates them. Coverage only; 2026-27 is not graded.

## 4. Definitions

**Zones, one per shot, by stored value first and location second.** The basket is at (25, 0) in
feet; dx = |x − 25|; d = the distance from the basket.

| Zone | Rule | Attempts per team game, 2018-19 to 2025-26 | League points per attempt |
|---|---|---|---|
| Restricted area | a two, d ≤ 4 | 28.6 falling to 23.9 | 1.27 rising to 1.36 |
| Paint | a two, not above, dx ≤ 8, y ≤ 13.75 | 15.0 rising to 19.2 | 0.80 rising to 0.90 |
| Mid-range | any other two | 13.5 falling to 9.0 | 0.81 to 0.85 |
| Corner three | a three, not a heave, y ≤ 9, dx ≥ 20 | 7.4 rising to 9.7 | 1.14 to 1.18 |
| Above-the-break three | any other three, not a heave | 24.4 rising to 27.2 | 1.04 to 1.08 |
| Free throw | value 1 | 21.7 to 23.5 | 0.77 to 0.78 |
| **Heave** (a seventh zone, added here) | a three with 3 seconds or fewer on the clock and 36 feet or more from the basket, by the text's distance, else the coordinates; made or missed | 0.22 to 0.47 | 0.08 to 0.16 |

- **Why a seventh zone.** The sweep lists six. A half-court heave is a three that drops about one
  time in twenty-five, so counting it above the break would book about a point of "bad luck" for
  each miss and move teams by how often they heave at the buzzer. The feed's count of them also
  jumps in 2025-26 (0.22 to 0.28 a team game before, 0.47 in 2025-26). The clock and distance are
  the repo's own heave rule
  (`scripts/nba_ingame_data.is_heave`). It applies to makes and misses alike, so the zone never
  depends on the outcome.
- A field goal with no coordinates would go to mid-range (a two) or above the break (a three). There
  are none today; the lab counts them.
- A three logged with y ≤ 9 and dx < 20 (7 rows, a bad location) goes above the break by the rule.

**The league's rate in a zone on date D:** points per attempt over this season's games dated before
D. **A zone with fewer than 200 attempts so far this season reads last season's whole-season rate
instead** (2018-19 has no last season and always reads its own).

- **Why not pool earlier seasons, as the sweep words it.** League rates drift: restricted-area shots
  went from 1.27 to 1.36 points in seven seasons. Every team's shots in a drifting season would beat
  a pooled rate, the league's total luck would no longer add to zero, and every game's gap would
  shift the same way, measuring the league's drift instead of any team's luck. A 0.03 drift on 25
  attempts is 0.75 points a team game, or 3 points on a total gap from four terms, as large as the
  cuts.
- By the time both teams have 10 games the league holds about 150 games, and each of the six main
  zones has thousands of attempts. So earlier seasons are the fallback for thin early counts, which
  in practice means the heave zone.
- The smoke run prints the mean gap per season. It should sit near zero.

**A team's luck for and against, on date D, this season, before D:**

    luck_for     = its own points from shots  − sum over zones (its attempts × the zone's rate on D)
    luck_against = opponents' points from shots − sum over zones (their attempts × the zone's rate on D)

**The gap**, built the way `models/nba_total_luck.py` builds it, from its own imported functions
(`team_box`, `as_of_ratings`, `pair_ratings`, `project_ratings`; no file under `models/` changes):

    ortg_adj = ortg_raw − 100 × luck_for / possessions
    drtg_adj = drtg_raw − 100 × luck_against / possessions
    pace     = mean of the two teams' possessions per game
    total    = pace/100 × [ORtg_H + DRtg_A + ORtg_A + DRtg_H − 2 × league rating]
    margin   = pace/100 × [(ORtg_H − DRtg_H) − (ORtg_A − DRtg_A)]
    gap_total  = adjusted total − raw total          gap_margin = adjusted margin − raw margin

Raw ratings, possessions and the league rating are exactly the live model's, from box scores.

**The team's part of the gap**, in that team's own points:

    home part = pace/100 × [(ORtg_H adj − raw) + (DRtg_A adj − raw)]
    away part = pace/100 × [(ORtg_A adj − raw) + (DRtg_H adj − raw)]

Home part + away part = gap_total, and home part − away part = gap_margin; a test pins both.

**Population:** both teams have 10 or more games this season before the date (the live rule,
CLAUDE.md section 3). Only final regular-season games count. Season to date means strictly earlier
Eastern dates, so an afternoon game final before an evening decision on the same date is left out,
as the live model does.

**A game whose plays do not add up.** Where the plays' points differ from either team's stored final
(26 of 9,519 games in 2018-19 to 2025-26, one by 34 points), that game's shots are left out of every
luck sum and every league rate. The team's raw rating still reads the box score, so that game
contributes no adjustment. The count is printed per season.

**Nothing is fitted.** No parameter here is chosen from a price or a result. The 200-attempt fallback
and the zone edges are stated above and do not change.

## 5. The cells (48)

| Family | Market | Sides | Decision | Cut | Cells |
|---|---|---|---|---|---|
| SL | full-game total | over, under | A (the 15Z fetch); C (the newest fetch 60-180 minutes before tip) | gap_total ≥ 1 / 2 / 3 / 4 toward the side | 2 × 2 × 4 = 16 |
| SL | full-game spread (the HOME number) | home, away | A; C | gap_margin ≥ 1 / 2 / 3 / 4 toward the side | 2 × 2 × 4 = 16 |
| SL | home team total | over, under | each game's per-game purchase, 45-75 minutes before tip (D) | home part ≥ 1 / 2 / 3 / 4 toward the side | 2 × 4 = 8 |
| SL | away team total | over, under | D | away part ≥ 1 / 2 / 3 / 4 toward the side | 2 × 4 = 8 |
| **Total** | | | | | **48** |

- **Toward the side:** the over and home read the number as it stands; the under and away read minus
  the number.
- **The price:** the side's best deciding offer under the market's fair line (`H.market_fair`:
  Pinnacle's no-vig where it quotes coherently, else the deciding books' median), −200 floor, books in
  `config.BEST_LINE_BOOKMAKERS`. The gap is the cut; the fair line only chooses the offer. This is the
  rule F4 and P3_F4 used. DraftKings alone is reported beside every cell.
- **The quotes:** full game at A and C through the harness's visible quotes, as F4; team totals at D
  through `models.nba_book_numbers.visible_numbers`, as P3_F4 and the live team-total model.
- **Bands (bar 5):** [0, 1), [1, 2), [2, 3), [3, 4) and 4 up, along the same side.
- **Seasons:** full game, 2021-22 to 2025-26 pooled, with 2021-22 to 2024-25 the choosing seasons the
  placebo reads; 2020-21 reported, never judged. Team totals, 2023-24 to 2025-26 pooled, with 2023-24
  and 2024-25 the choosing seasons.
- **Settlement:** the final score, overtime included. Spread: the home side covers when
  (home − away) + the home number > 0. Team total: that team's own final score, overtime included. A
  push returns the stake.

**Dated line, 2026-10-31: what the 95% coverage check at D counts. The cells, seasons and bars do not
change; nothing has been graded.** Record 6.5 says a choosing season reached on fewer than 95% of its
games at D is reported and not chosen on. That check counts each game's per-game purchase, whatever
markets it holds, as every earlier lab's does. The first version of this lab counted only purchases
holding team totals. It was found by a checker before any grade.

- **What it would have done:** team totals exist on 1,138 of 1,230 games in 2023-24, so it read 92.1%
  there. `--full` would have dropped 2023-24 from all 16 team-total cells and judged them on 2024-25 and
  2025-26, against the three seasons registered above. Only a column in each cell's row would have
  recorded it: `--smoke` did not print it, and section 9's counts pool all three seasons regardless.
- **What the check reads now:** 2023-24 99.6% (1,225 of 1,230 games have a purchase inside the 45-75
  minute window), 2024-25 99.5%, 2025-26 99.0%.
- **What does not move:** a game's decision time differs on 0 of the 3,575 games both ways of counting
  share, and the 74,670 team-total offers are identical, read without any result. The 92 games of
  2023-24 with a purchase and no team total have a decision time and no offer, so they place no bet.
  Games with a decision time in 2023-24 count 1,225, where the old count gave 1,133, and `--full`'s
  population file will read the same frame.
- **The guard:** `--smoke` and `--full` print the seasons each group asks for and what the check keeps,
  and refuse to run if an asked season would drop.

## 6. Impossible numbers (stated before any cell is graded)

Measured on the cache before this was written, prices and numbers only.

1. **A number 40 or more points from the median of the game's stored numbers in that market is not
   that market, and neither the fair line nor an offer may read it** (the rule of record 10.8, applied
   here to the main lines). Full-game totals hold 17 such rows: Bovada at 1.0 (9), BetMGM at 155.5
   (3), 314.5 and 335.5, Caesars at 136.5 (3). Nothing lies between 25 and 80 points from the median,
   so any cut in that gap removes the same rows. Spreads run −25 to +22 and team totals 89.5 to 143.5;
   neither has such a row.
2. **At a decision, a full-game spread or total 5 or more points from the median of the deciding
   books' coherent numbers at that decision is not eligible**, as an offer or in the fair line.
   Pinnacle is never removed by this. Measured over about 176,000 deciding quotes at A and C:

   | Points from the median | Spreads at A | Spreads at C | Totals at A | Totals at C |
   |---|---|---|---|---|
   | ≥ 3 | 2 | 8 | 3 | 5 |
   | ≥ 4 | 1 | 2 | 1 | 0 |
   | ≥ 5 | 1 | 1 | 0 | 0 |

   The two rows it removes: `NBA_2026-03-21_MIA_HOU`, Fanatics at home +9.5 (−450 / +350) against a
   median of −2, priced like an alternate number rather than a main one; and
   `NBA_2021-12-10_BOS_PHX`, FanDuel at home +3.5 against a median of −3.5, the same number with the
   opposite sign. The second is the highest-EV spread offer at C (0.339), so any home cell that fires
   on that game would take it.
3. **Team totals** keep `visible_numbers`' own rule: no deciding book more than 1.0 point from the
   deciding books' median.
4. **Prices:** the harness's two-way coherence (implied sum 1.00 to 1.15) and the −200 floor. The smoke
   run lists every offer past +200.

`--smoke` prints, per market and decision, the extremes of every number and price, the rows each rule
removes, and the 15 highest-EV offers. A number that looks impossible there and passes these rules
stops the run for a dated line here, before any grade.

**Dated line, 2026-10-31: the count in rule 1. No rule changes; nothing has been graded.** The 17 rows
are every stored row. The lab's quotes hold 11 of them, read through the harness's own filters:

- 4 came only in the injury-report purchase, which these cells leave out: BetMGM at 314.5 and 335.5,
  Caesars at 136.5 twice.
- 2 fall at or after tip: Bovada at 1.0 on `NBA_2021-01-02_CLE_ATL` (stamped 9 minutes after tip) and
  on `NBA_2021-04-05_WAS_TOR` (fetched at tip).
- The 11 left are Bovada at 1.0 (7), BetMGM at 155.5 (3) and Caesars at 136.5 (1). The rule removes
  all 11. The median it reads is over the lab's rows, and the same rows fall either way.

## 7. The bars

Section 9.1 of the record, unchanged, through `--house5`:

1. Pooled over the graded seasons, 200 or more bets.
2. The pooled whole-day bootstrap 95% interval of the return is above zero (4,000 resamples, seed 7).
3. At least two graded seasons have 30 or more bets, and of those all but at most one are positive.
4. Beats the blind bet on its dominant real side, pooled.
5. Bands: the band just below the cut and every band from the cut up each have a positive pooled
   return, where they hold 30 or more bets, and the cell's own pooled return is above zero.
6. Placebo: the return on the choosing seasons beats the 95th percentile of 200 shuffles, seeds 1 to
   200. A run that places no bet counts as 0.

Closing-line value is reported, never a bar (A and C only: one purchase per game means D has no later
price). **A thin cell is still reported.** Under 200 pooled bets it fails bar 1, and its bets, units,
return, interval and season split are printed anyway. Its answer is "too few games to tell", not "it
loses".

**Expected passes by chance:** 48 × 0.025 = 1.2 cells clear bar 2 alone, before correlation. Bars 3 to
6 make a chance pass rarer.

**The placebo.** For each decision and market, every game with a gap and an offer has its gap moved to
another game on the same date, by the harness's own within-date shuffle (`H.shuffle_within_date`, seed
= run number). Each game keeps its own prices and result. The shuffle runs over every game with a gap
on that date, not over the games at the cut, so a bet moves to a different game unless the date is
nearly empty. `--smoke` measures that on the real data: the share of placebo bets that are not the real
cell's bets, per family and decision.

## 8. Reported beside, never judged

**Controls (`control_` families: same 48 cells, same offers, no placebo, never candidates):**

- `control_SL_shipped`: the live models' own gap (opponents' threes and free throws), on the same
  games, as the reference.
- `control_SL_added`: **what the new gap adds after removing the shipped gap.** Per market and season S,
  the new number minus b × the shipped number, with b from a least-squares line through the origin on
  the seasons before S (2018-19 onward). Gaps only; no result enters b.
- `control_SL_against` and `control_SL_for`: the zone gap with only the defence's luck removed, and with
  only the offence's.

**Overlap with the live models.** For each cell, the share of its bets the live models make too, by the
same harness on the same offers, counted without any result:

- `nba_total_luck`: full-game total, over, at C, shipped gap ≥ 3;
- `nba_team_total_luck`: home team total, under, at D, shipped home part at or below −2.

Two numbers per cell: the same bet (game, market and side), and the same game (either live model bets
that game).

**What a pass leads to.** It is built live (record section 2) with its own EV floor and the prices it
lays stated first. Only then does the sweep's step 2 apply: re-grading the same cells once with
defender-distance bins pulled from Matt's machine. Not part of this search.

## 9. Counts before grading

Added 2026-10-31 from `python -m scripts.nba_s_shotluck --smoke`, before any cell was graded. These
are counts of games and read of no result. Research cache of 2026-10-29, shots pulled 2026-10-30.

**Bets per cell, pooled** (full game 2021-22 to 2025-26, team totals 2023-24 to 2025-26):

| Decision | Market | Side | ≥ 1 | ≥ 2 | ≥ 3 | ≥ 4 | ≥ 4, fewest in one graded season |
|---|---|---|---|---|---|---|---|
| A | full-game total | over | 2,347 | 2,032 | 1,689 | 1,373 | 239 |
| A | full-game total | under | 2,308 | 1,975 | 1,673 | 1,346 | 246 |
| A | full-game spread | home | 2,399 | 2,115 | 1,824 | 1,573 | 270 |
| A | full-game spread | away | 2,341 | 2,055 | 1,784 | 1,533 | 261 |
| C | full-game total | over | 2,348 | 2,033 | 1,690 | 1,374 | 239 |
| C | full-game total | under | 2,308 | 1,975 | 1,673 | 1,346 | 246 |
| C | full-game spread | home | 2,399 | 2,115 | 1,824 | 1,573 | 270 |
| C | full-game spread | away | 2,342 | 2,056 | 1,785 | 1,534 | 261 |
| D | home team total | over | 1,332 | 1,085 | 864 | 682 | 202 |
| D | home team total | under | 1,325 | 1,075 | 856 | 664 | 197 |
| D | away team total | over | 1,325 | 1,080 | 819 | 626 | 175 |
| D | away team total | under | 1,374 | 1,102 | 885 | 671 | 199 |

Every cell clears 200 pooled bets, so none reads "too few games to tell". 2020-21, reported and never
judged, holds 277 to 427 bets per full-game cell.

**This gap is wide, so a cut of 4 is not a rare event.** Across 2018-19 to 2025-26, per season:

| Number | Mean | Standard deviation | Correlation with the shipped gap |
|---|---|---|---|
| Total gap | −0.09 to +0.11 | 5.1 to 7.3 | 0.09 to 0.44 |
| Margin gap | +0.01 to +0.19 | 6.5 to 7.6 | 0.26 to 0.65 |
| Home part | −0.02 to +0.15 | 4.3 to 5.2 | 0.22 to 0.51 |
| Away part | −0.12 to 0.00 | 4.2 to 5.2 | 0.26 to 0.53 |

The means sit near zero, section 4's check that the league's drift stays out. The over at C and gap ≥ 3
places 1,690 bets here against the shipped gap's 508 at the same cut (record 6.7). The cuts stand as
registered.

**What the new gap adds.** `control_SL_added` subtracts b × the shipped number, with b from earlier
seasons only. Over the graded seasons b runs 0.63 to 0.79 on totals, 1.46 to 1.63 on spreads, 1.07 to
1.13 on the home team total and about 1.08 on the away team total. Its cells are graded by `--full` and by
nothing before it.

**Overlap with the live models:**

| Cells | Same bet, ≥ 1 to ≥ 4 | Same game, ≥ 1 to ≥ 4 |
|---|---|---|
| Full-game over, A and C | 14.7% to 17.5% | 18.6% to 21.4% |
| Home team-total under, D | 18.2% to 23.8% | 24.1% to 27.7% |
| The other 36 cells | none: neither live model bets that side | 12.4% to 29.2% |

So at least three of every four bets in any cell are bets neither live model makes.

**The placebo on the real data,** 20 runs per cell:

| Decision | Placebo bets | Not the real cell's bets | A perfect same-date shuffle | Lowest and highest cell |
|---|---|---|---|---|
| A | 719,360 | 55.9% | 55.9% | 48.0% to 66.6% |
| C | 719,720 | 56.0% | 55.9% | 48.0% to 66.7% |
| D | 315,300 | 59.3% | 59.2% | 50.5% to 70.8% |

By cut: 50.1% at ≥ 1, 55.3% at ≥ 2, 60.2% at ≥ 3, 64.6% at ≥ 4.

- The dates are full: about 7.5 games a date, and 0.1% of full-game games and 0.2% of team-total games are
  alone on theirs.
- **What repeats is the cell's breadth, not a stuck shuffle.** If 3 of a date's 7 games fire for real, a
  shuffled gap lands on one of those 3 with chance 3/7, however well it shuffles. Every cell sits within
  0.004 of that figure, so no shuffle within a date could differ more.
- **Dated line, 2026-10-31: section 7's "a bet moves to a different game unless the date is nearly
  empty" understates this.** The procedure does not change. About half the placebo's bets at ≥ 1 are real
  bets, and any real edge travels with them, so bar 6 asks more of the low cuts than of the high ones.

**Lines and prices the cells can read, after the rules:**

| Market, decision | Numbers | Prices | Highest EV |
|---|---|---|---|
| Spread (home number), A | −24.5 to +21.5 | −135 to +110 | 0.120 |
| Spread (home number), C | −24.5 to +21.5 | −135 to +110 | 0.255 |
| Total, A | 199.0 to 262.5 | −125 to +105 | 0.124 |
| Total, C | 195.5 to 262.0 | −125 to +105 | 0.191 |
| Home team total, D | 94.5 to 135.5 | −164 to +134 | 0.227 |
| Away team total, D | 94.5 to 135.5 | −150 to +112 | 0.160 |

- Rule 1 removes 11 full-game rows and no team-total rows. None of the 11 would be visible at A or C
  even without it. Rule 2 removes 1 row at A and 1 at C, the two named in section 6, and the flipped
  spread's 0.339 is gone from the top of the list. No offer lies past +200.
- **The highest EVs are real numbers read against a Pinnacle quote from before a sudden move, so nothing
  stops the run.** On `NBA_2021-05-16_PHX_SAS` the books went from home +9 to +3.5 by 16:50 UTC, and
  Pinnacle's newest stored quote was still +9 from 16:40. On `NBA_2023-04-08_DEN_UTA` the books went from
  home +5.5 to +10.5 by 18:24 UTC, and Pinnacle stayed at +5.5 until 18:55. The gap decides these cells and
  the fair line only chooses among offers, so a stale fair line cannot start a bet.

**Time and memory, `--full`:** projected 1.64 hours, peak 3.0 GB, with other jobs running on the machine.
One placebo run across the 48 cells takes 13.5 seconds, so the 200 take about 45 minutes. It was measured
on the real offers against invented final scores. An earlier run of the same lab projected 1.30 hours.

**Dated line, 2026-10-31: `--smoke` re-run after section 5's change to what the 95% check counts. Nothing
has been graded.**

- **Every table above stands.** The counts, overlap, placebo and gap files this run wrote are identical,
  row for row, to the run those tables came from. With the clock lines removed, the two printouts differ
  only by the new printout below and the peak memory.
- **The new printout, for both team-total groups:** asks to choose on 2023-24 and 2024-25, keeps both,
  drops nothing. Coverage is 99.59%, 99.51% and 99.02% for 2023-24, 2024-25 and 2025-26. The full-game
  groups keep all four of their choosing seasons.
- **Team totals per season, from the same printout:**

  | Season | Games | Games with team totals | Games with a decision time | Decision times that moved |
  |---|---|---|---|---|
  | 2023-24 | 1,230 | 1,138 | 1,225 | 0 |
  | 2024-25 | 1,230 | 1,229 | 1,224 | 0 |
  | 2025-26 | 1,230 | 1,228 | 1,218 | 0 |

- **Time and memory, `--full`:** projected 1.44 hours, peak 3.1 GB. One placebo run across the 48 cells
  takes 11.9 seconds, so the 200 take about 40 minutes. The same offers measured 1.64 hours on the run
  above, so the clock moves by that much between runs. Another job ran on the machine during both.


## 10. Results (graded 2026-10-31)

Run `2026-10-31-shotluck`, stored in Supabase. 48 cells, 192 controls.

**0 of the 48 cells pass, and none clears the 95% interval. The family stays closed.** All 48 hold 200+ bets. The
median return is -1.44%, with 13 positive.

| Market, side | Cells | Most bets | Best units | Best return | Worst return |
|---|---|---|---|---|---|
| Full-game total, over | 8 | 2,348 | +71.08 | +3.9% | -0.4% |
| Full-game total, under | 8 | 2,308 | -1.67 | -0.1% | -2.4% |
| Spread, home | 8 | 2,399 | +16.29 | +1.0% | -3.7% |
| Spread, away | 8 | 2,342 | -35.04 | -1.8% | -4.1% |
| Away team total, over | 4 | 1,325 | +27.01 | +3.9% | -1.0% |
| Away team total, under | 4 | 1,374 | -48.19 | -5.7% | -7.4% |
| Home team total, over | 4 | 1,332 | +11.53 | +1.5% | -1.4% |
| Home team total, under | 4 | 1,325 | +14.12 | +1.9% | -2.4% |

The nearest miss is the full-game over at decision point C, cut 3: 1,690 bets, +71.08 units, +3.9%, interval
-0.8% to +8.5%. It fails the interval and the bands. The live totals models are unchanged.

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

To be added from `--smoke`, dated, before any cell is graded.

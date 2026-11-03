# NBA search: the popular-team tax (pre-registered 2026-10-30, before any bet in it was graded)

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find
it"*. This is rank 5 of that day's sweep of what is missing.

**The idea.** Casual money lands on the same teams game after game. If books shade those teams'
lines rather than balance them, the popular side is overpriced by a predictable amount. A team's
average share of public tickets in its EARLIER games is known before tip. So: bet against the
habitually backed team when the two teams' popularity differs a lot, on the full-game spread and
moneyline, and bet the total under when both teams habitually draw over tickets.

**Evidence going in.**

- For: popularity persists inside a season. Each team's October-December spread ticket share
  against its January-May share correlates 0.66 / 0.63 / 0.49 / 0.70 / 0.61 / 0.63 across
  2020-21 to 2025-26 (measured 2026-10-30 on the rows in 1 below).
- Against: Feddersen, Humphreys and Soebbing (Journal of Sports Economics 2018, 33,000 NBA games
  1981-2012) found books offer favourable spreads on popular-team games and that informed bettors
  earned no higher return. So the prior is low.

**What earlier searches did and did not cover.**

- The second search graded "fading the public" only as a control. It reads a game's own pre-tip
  ticket split, and the stored history is the closing split, known only after tip, so that control
  has no bets before 2026-27 (`docs/nba_models_2026.md` 6.3, 6.5, third amendment).
- No search has used a team's ticket habit from its earlier games. That is the only thing tested
  here. A game's own closing split is never read for that game.
- The sweep's rank 8 (fade the same game's closing split, labelled as look-ahead) is a different
  idea and is not tested here.

**Written before any bet in this search was graded. Nothing below changes after a result is seen;
a later change gets its own dated line and reason.** Lab: `scripts/nba_s_popular.py`. Tests:
`tests/test_nba_s_popular.py`. Pass or fail: `python -m scripts.nba_game2_verdict --results DIR
--house5`, the bars of `docs/nba_models_2026.md` 9.1, then the credit line in 7. No data is
bought. The builder ran no grade: the lab's `--smoke` reads prices, ticket shares and earlier
results for market pricing only, and whoever runs `--full` grades it.

## 1. Data

- **Prices:** `nba_odds`, full-game spread, moneyline and total, purchased slate fetches, read by
  the shared harness (`H.load`, `scripts/nba_game_harness.py`). 2,598,846 pre-game rows on 7,230
  games, 2020-21 to 2025-26. The seventh search's 5-minute purchase around injury reports is left
  out by `H.load`.
- **Tickets:** `nba_public_splits`, the closing rows: `capture_kind = 'archive_undated'`,
  `endpoint = 'v1'`, `quality IS NULL`, a matched `game_id`, a non-null `tickets_pct`. Games per
  season with such rows: 960 / 1,215 / 1,216 / 1,158 / 1,230 / 1,157 (2020-21 to 2025-26).
  - The `quality` filter removes the reversed 2022-03-09 slate (`reversed_at_source`, 72 rows) and
    the listings rewritten more than 400 minutes after tip (`late_rewrite`, 1,706 rows).
  - **A flagged game can still be bet.** The filter only stops its tickets from counting toward
    later games. Its own price is fine and the rule never reads its own split.
  - A closing split is known only after its game has started, and a later game is decided on a
    later date, so it is known by then (the rule in 2 is strictly earlier dates).
- **National television:** `nba_schedule.national_tv`, regular season. Filled for 274 games of
  2020-21 and 306 of 2025-26; empty for the four seasons between. Report only (8).
- **Read from** the research cache of 2026-10-29 (`NBA_RESEARCH_CACHE`). It is a cache of
  Supabase; the lab writes nothing to it.

**The check the sweep asked for: the total tickets changed at the source.**

- The share of tickets on the over averages 60.0 / 60.2 / 60.9 / 60.3 in 2020-21 to 2023-24 and
  81.8 / 82.2 in 2024-25 and 2025-26. April 2024 is 66.6; October 2024 is 84.5.
- It is not one endpoint: v1 and v2 agree (mean difference 0.00; spread of the difference 0.03 in
  2024-25 and 0.00 in 2025-26). The ticket count cannot separate it, because it is one number per
  game for all three markets. So the stored data shows when it happened and that both endpoints
  carry it. It does not show why.
- Spread tickets show no such step: the home share averages 47.0 to 48.6 in every season.
- **What this search does about it:** the over habit in 2 is measured against the league's own
  mean in the same season, so the level cancels. The habit also persists differently either side
  of the change: October-December against January-May correlates 0.29 / 0.47 / 0.28 / 0.34 before
  it and 0.71 / 0.72 after. So the total cells are also reported on 2021-22 to 2023-24 and on
  2024-25 to 2025-26 apart (8), and a total result is read with that in mind.

**If a cell passes and is built live:** v1 stopped carrying splits on 2026-04-12, so a live model
reads v2's closing rows of earlier games. On 2025-26 v1 and v2 are the same number on spreads and
totals (difference 0.00 on 1,107 games).

## 2. Definitions

- **A team's ticket share in a game:** `tickets_pct` on its side of the full-game SPREAD market.
- **Popularity:** the unweighted mean of that share over the team's earlier games THIS SEASON
  with a clean row, on dates strictly before today's date, with at least 10 such games. Fewer
  than 10 for either team: no number, no bet.
- **The gap:** home popularity minus away popularity, in ticket points. **The popular team** is
  the one with the higher popularity; **against** is the other team. A gap of exactly 0 is no bet.
  Strength is the size of the gap.
- **Both the spread and the moneyline read the spread ticket gap.** Moneyline tickets mostly
  follow the favourite (their spread across games is about twice the spread market's).
- **A team's over habit:** the unweighted mean of the over ticket share in its earlier games this
  season (same rules, at least 10 games), minus the league's mean over the same season's games on
  dates before today.
- **The total's strength:** the SMALLER of the two teams' over habits. The sweep says "both teams'
  mean over-ticket share is high", and the smaller of the two is the plain reading of both. The
  bet is the under.
- **Decision point C:** the newest fetch 60 to 180 minutes before tip (`H.decision_times`). Each
  game is decided once per cell.
- **The price:** the side's best deciding offer (`config.BEST_LINE_BOOKMAKERS`, Pinnacle and
  Bovada never) at that book's own number, under the market's fair line (`H.market_fair`:
  Pinnacle's no-vig where it quotes coherently, else the deciding books' median; priced through
  the spread of results around Pinnacle's close on earlier seasons, `H.close_dist`). A two-way
  quote must be coherent (implied sum 1.00 to 1.15). -200 floor. DraftKings alone is reported
  beside every cell.

### Three changes from the sweep's plan, each made from counts or prices, never a result

1. **The total's cuts are 1 / 2 / 3 points, not 5 / 10 / 15.** Teams differ far less in over habit
   than in popularity. The sweep's cuts would bet 11 / 0 / 0 games in five seasons. At 1 / 2 / 3
   the same rule has 942 / 404 / 159 pooled. The 3-point cell is under 200 bets and is registered
   anyway: its answer is "too few games to tell".
2. **Decision point D is reported, not registered.** The sweep named C and D. On 7,205 of the
   7,219 games with both, they are the same fetch (99.8%; lead 60 minutes at the median and at the
   1st and 99th percentiles of both). Registering both would count one test twice. A live model
   decides at D, so D is run as a diagnostic beside each cell (`control_POP_at_D`,
   `control_POPT_at_D`), never judged.
3. **The sweep's Step 1 was not run before these rules were written.** It regresses the popular
   side's result, minus Pinnacle's no-vig close, on the gap. That reads the results of the games
   this search bets, which is grading. It is written by `--full` as a report (8), never a gate.

### Impossible numbers (fixed before any price was selected for a bet)

- **A full-game total 40 or more points from the median of its game's stored totals is not a
  full-game total and is not eligible.** This is the sixth search's rule (`docs/nba_models_2026.md`
  10.8). In this load it removes 11 rows on 5 games: Bovada 1.0 on three games of 2020-21 (7 rows),
  BetMGM 155.5 on NBA_2023-11-24_SAS_GSW (3 rows), Caesars 136.5 on NBA_2026-03-13_UTA_POR (1 row).
  Nothing lies 20 to 60 points away, so any cut in that range removes the same rows.
- **No stored spread is impossible on its own.** Every number lies between -24.5 and +22 (the HOME
  number), and the largest distance from a game's median stored spread is 15.5 points. Each book's
  numbers move across a game's fetches, so that median cannot catch a row that is wrong at one fetch.
  The next rule does.
- **A spread with home and away swapped (added 2026-10-31, section 10).** A deciding book's spread
  5 or more points from the median of the deciding books' spreads at the same fetch is a swapped
  row, and that book's spread and moneyline at that fetch are not eligible.
  - It needs 3 or more deciding books on the game's spread. With 2, the median is their midpoint and
    cannot say which is wrong. Five games have 2, all in 2020-21, and each pair agrees.
  - It applies at C and at D, before the market's fair line is read. That book's total stays.
  - It removes one book on one game: NBA_2021-12-10_BOS_PHX, FanDuel, at the 02:00Z fetch (tip
    03:00Z). The number is 7.0 points from the median. FanDuel's fetch before it reads home -4.5,
    moneyline -189 / +160. This one reads home +3.5, moneyline home +124 / away -147. Every other
    deciding book and Pinnacle read home -3.5 or -4, moneyline home -156 to -175.
  - The next largest distance is 4.0 (NBA_2021-03-27_DAL_NOP, FanDuel, 2020-21, reported only), so
    any cut above 4 and up to 7 removes the same row.
- **Left in, each measured on prices only:**
  - NBA_2021-01-27_DAL_UTA, BetMGM's moneyline at the decision reads home +115 / away -141, after
    home -141 / away +115 on its earlier fetches, and every other deciding book reads home -135.
    Its spread agrees with the others, so the rule above cannot see it. It stays because it touches
    nothing judged: 2020-21 is reported only, no band or placebo run reads that season, and the
    game's gap of 2.35 is under every cut.
  - NBA_2024-02-05_GSW_BKN, BetMGM's spread at the decision reads home -1.5 at +110 / -135, between
    fetches reading home +1.5 at -115 / -105. It is 3.0 points from the median. No cell bets it on
    the real inputs. In 49 of the 200 placebo runs the game gets the away side at gap 5 or more, and
    the row is that side's best offer, at EV 0.021. One bet at most in each of those runs.
  - On a game near level, a book can sit on the other side of the median without being wrong. Besides
    FanDuel's row, 127 rows at C are 2 or more points from the median and on its other side, the
    BetMGM row above among them. Every one has a median within 1.5 of level and a number within 2 of
    level, and the largest distance is 3.0.
- **Prices:** a price with a size under 100 is not a price (none stored); an incoherent pair is
  never an offer (1 stored).
- **Ticket shares:** a share at or outside 0 and 100 is not a share (none on the clean rows; spread
  sides run 7 to 93, totals 2 to 98).
- **A coherent price far from Pinnacle's stays in, unless the swapped rule above removes it.** The
  highest-EV offers at C are moneylines
  such as NBA_2023-04-08_DEN_UTA home +375 at BetMGM, against Pinnacle's no-vig home chance of
  0.353 (EV 0.68). Five deciding books stored +360 to +375 at that fetch, so it is not one bad
  row, and nothing here says which side was stale. It is eligible. The harness reports each cell's
  units without single-book outlier prices and its units still offered at the next fetch.
  `--smoke` prints these extremes and the top offers.

### The prices these rules lay (read at C, before any grade)

| Market | Lowest | Median | Highest | Bets on the underdog |
|---|---|---|---|---|
| Spread, against the popular team, gap ≥ 5 / 10 / 15 | -120 | -110 | +102 | 81% / 86% / 90% |
| Moneyline, against the popular team, gap ≥ 5 / 10 / 15 | -200 | +220 / +260 / +290 | +2500 / +2250 / +1300 | 86% / 90% / 92% |
| Total under, habit ≥ 1 / 2 / 3 | -115 | -110 | +100 | |

So the moneyline cells are long-price underdog bets, sized to win one unit: a bet at +1300 risks
0.077 units.

## 3. The cells (9)

| Family | Market, side | Decision | Cut | Cells |
|---|---|---|---|---|
| POP | full-game spread, against the popular team (a per-game side) | C | gap ≥ 5 / 10 / 15 | 3 |
| POP | full-game moneyline, against the popular team (a per-game side) | C | gap ≥ 5 / 10 / 15 | 3 |
| POPT | full-game total, under | C | smaller over habit ≥ 1 / 2 / 3 | 3 |
| **Total** | | | | **9** |

## 4. Bands (bar 5)

Along the cut within one market and side. Spread and moneyline: [0, 5), [5, 10), [10, 15), 15+.
Total: [0, 1), [1, 2), [2, 3), 3+. The band just below the cut and every band from the cut up must
be positive where they hold 30 or more pooled bets (`G5.band_columns`). A band's bets are the
cell's own choice at the band's lower edge, less the games still chosen at its upper edge.

## 5. Seasons

2021-22 to 2025-26 graded and pooled. The choosing seasons, which the placebo reads, are 2021-22
to 2024-25 (`H.CHOOSE`). 2020-21 is reported only (`H.REGIME`). Season-to-date numbers start again
each season. The first 10 or so games of each team's season carry no number.

**The pool is not five equal seasons.** Teams' popularity spread varies a lot by season (team
standard deviation 2.9 / 8.3 / 5.0 / 6.1 / 6.2 / 5.4 points for 2020-21 to 2025-26), and the cuts
are in ticket points because the mechanism is. So at gap ≥ 15, 2021-22 holds 237 of the 524 pooled
spread bets and 2022-23 holds 4. Bar 3 reads only seasons with 30 or more bets.

## 6. Settlement

Full-game final scores, overtime counted (`H.grade`). One unit to win, risk capped at 3. A push
returns the stake: 0 units, and its risk leaves the denominator. Spread numbers are the HOME number.

## 7. The bars

`docs/nba_models_2026.md` 9.1, unchanged: 200 or more pooled bets; the pooled whole-day bootstrap
95% interval above zero; at least two seasons with 30 or more bets and all but at most one of them
positive; beats the blind bet on its dominant real side; the bands; the choosing seasons' return
above the 95th percentile of 200 placebo runs.

- **Bar 4 here.** Popular teams are mostly favourites, so 81-92% of POP's bets are underdogs. The
  verdict reads that share and compares each POP cell with the blind underdog on every game with a
  number. Every POPT bet is an under, so it compares with the blind under on the same games.
- **The credit line, added because bar 4's comparison is over all games with a number.** A POP
  cell that passes the six bars is credited to popularity only when its pooled return also beats
  `control_POP_dog` at the same market and cut: the underdog in the SAME games. Otherwise the
  answer is "underdogs in lopsided games", not "popular teams". `python -m scripts.nba_s_popular
  --credit --results DIR` applies it to the verdict's file.
  - **The same games means the games the cell can bet** (made exact 2026-10-31, section 10): those
    where the side against the popular team has a deciding offer at or above the -200 floor. That
    test does not depend on the cut. Without it the moneyline control would also bet games the cell
    cannot, where the team bet against the public is a favourite beyond -200 and the underdog is the
    popular team.
  - **A level market stays in the cell only.** When the market's fair chance is exactly 0.5 there is
    no underdog, so the control has no bet there. The cell's rules do not change, so it keeps those
    games: 6 / 4 / 1 pooled moneyline bets at gap ≥ 5 / 10 / 15, none on the spread.
- **Placebo, 200 runs, seeds 1-200.** Each game's four inputs (both teams' popularity and both
  teams' over share) move together to another game with a number on the same date, by one
  permutation per date. No game keeps its own inputs (changed 2026-10-31, section 10), unless it is
  the only game with a number on its date. Each game keeps its own prices, and the rule is
  recomputed.
  - The shuffle runs over every game with a number on the date, not over the games past a cut.
    Only 0.1-0.5% of games with a number are alone on their date, but 39% of games at gap ≥ 15 are
    the only such game on their date. Shuffling those alone would repeat the real bets. `--smoke`
    prints the share of placebo bets that differ from the real bets.
  - This placebo moves the bet off the underdog as well as off the popular team, because a
    shuffled game's side comes from another game (`--smoke` prints the underdog share of placebo
    bets). So it does not separate popularity from being an underdog. Bar 4 and the credit line do
    that.
- **Closing-line value** is reported, never a bar (`pool_clv_median`, beside the blind side's).
- **A thin cell is still reported.** A cell under 200 pooled bets fails bar 1 and its bets, units,
  return, interval and season split are printed anyway. Its answer is "too few games to tell", not
  "it loses".
- **Expected passes by chance:** 9 × 0.025 ≈ 0.23 cells clear bar 2 alone, before correlation, and
  the three cuts of a market are nested, so fewer distinct tests than that.
- **A pass is built live** (`CLAUDE.md` 2), with its own EV floor and the prices it lays stated
  before it ships.

## 8. Controls and reports (never judged, never a cell)

| Name | What it is |
|---|---|
| `control_POP_with` | spread and moneyline, WITH the popular team, same games and cuts |
| `control_POP_dog` | spread and moneyline, the market's underdog, same cuts, on the games the cell can bet (the credit line, 7) |
| `control_POPT_over` | total, the over, same games and cuts |
| `control_POP_at_D`, `control_POPT_at_D` | the registered cells at decision point D |
| National television report | each registered cell's bets split into national broadcast, NBA TV only and neither, on 2025-26 (and 2020-21 beside it, outside the pool). Those are the only seasons with the flag. Bets, units, return, interval. No bar and no selection reads it. |
| Total tickets report | each POPT cell on 2021-22 to 2023-24 and on 2024-25 to 2025-26 apart (1) |
| Step 1 report | the popular side's (or the under's) result minus Pinnacle's no-vig close at the close's number, a push left out, per band and as a slope per ticket point, with a whole-day bootstrap interval. Graded data, so `--full` only. |

## 9. Counts before grading (measured 2026-10-30, re-counted by the lab 2026-10-31, no result read)

Everything in this section is printed by `python -m scripts.nba_s_popular --smoke` and was read
before any bet was graded. Only the table below stood when the rules were committed; the rest was
added after the lab's first runs.

Bets each cell would place at C with a deciding offer at or above the floor. Counted from the
choice, never the grade:

| Cell | 2020-21 | 2021-22 | 2022-23 | 2023-24 | 2024-25 | 2025-26 | Pooled 2021-22 on |
|---|---|---|---|---|---|---|---|
| Spread, gap ≥ 5 | 256 | 719 | 446 | 579 | 655 | 640 | 3,039 |
| Spread, gap ≥ 10 | 47 | 435 | 100 | 253 | 317 | 333 | 1,438 |
| Spread, gap ≥ 15 | 5 | 237 | 4 | 60 | 93 | 130 | 524 |
| Moneyline, gap ≥ 5 | 250 | 684 | 424 | 566 | 582 | 589 | 2,845 |
| Moneyline, gap ≥ 10 | 47 | 421 | 96 | 250 | 291 | 315 | 1,373 |
| Moneyline, gap ≥ 15 | 5 | 235 | 4 | 58 | 87 | 126 | 510 |
| Total under, habit ≥ 1 | 96 | 146 | 146 | 178 | 250 | 222 | 942 |
| Total under, habit ≥ 2 | 40 | 38 | 59 | 73 | 130 | 104 | 404 |
| Total under, habit ≥ 3 | 14 | 7 | 23 | 34 | 69 | 26 | 159 |

The moneyline counts are lower because the -200 floor removes a price when the team bet against
the public is itself a heavy favourite.

**Games with a number at all** (both teams 10 or more earlier games): 919 of 1,080 / 1,073 of 1,230
/ 1,073 / 1,057 / 1,075 / 1,075, 2020-21 to 2025-26.

**Pooled bets per band, 2021-22 to 2025-26:**

| Cell | Band 1 | Band 2 | Band 3 | Top band |
|---|---|---|---|---|
| Spread | [0, 5): 2,311 | [5, 10): 1,601 | [10, 15): 914 | 15+: 524 |
| Moneyline | [0, 5): 1,943 | [5, 10): 1,472 | [10, 15): 863 | 15+: 510 |
| Total under | [0, 1): 640 | [1, 2): 538 | [2, 3): 245 | 3+: 159 |

**National television, bets by group (national broadcast / NBA TV only / neither).** Every
national-broadcast number is under 200, so the report's answer for each is "too few games to tell".

| Cell | 2025-26 | 2020-21 |
|---|---|---|
| Spread, gap ≥ 5 / 10 / 15 | 116, 27, 497 / 58, 15, 260 / 13, 9, 108 | 36, 22, 198 / 5, 4, 38 / 1, 0, 4 |
| Moneyline, gap ≥ 5 / 10 / 15 | 101, 26, 462 / 50, 15, 250 / 10, 9, 107 | 32, 20, 198 / 5, 4, 38 / 1, 0, 4 |
| Total under, habit ≥ 1 / 2 / 3 | 86, 15, 121 / 47, 6, 51 / 9, 2, 15 | 23, 13, 60 / 11, 3, 26 / 2, 3, 9 |

**The placebo is a null on the real data** (seeds 1-3, all six seasons, under the rule in 10):

| Cell | Real bets | Placebo bets, mean | Placebo bets that are not real bets | Real bets a placebo repeats | Underdog share, real / placebo |
|---|---|---|---|---|---|
| Spread, gap ≥ 5 | 3,295 | 3,295 | 71.3% | 28.7% | 80.7% / 49.6% |
| Spread, gap ≥ 10 | 1,485 | 1,485 | 85.3% | 14.7% | 85.9% / 50.0% |
| Spread, gap ≥ 15 | 529 | 529 | 93.6% | 6.4% | 89.6% / 49.6% |
| Moneyline, gap ≥ 5 | 3,095 | 2,409 | 63.1% | 28.7% | 86.0% / 68.1% |
| Moneyline, gap ≥ 10 | 1,420 | 1,079 | 80.6% | 14.7% | 90.1% / 68.8% |
| Moneyline, gap ≥ 15 | 515 | 389 | 91.4% | 6.5% | 92.4% / 67.2% |
| Total under, habit ≥ 1 | 1,038 | 1,038 | 85.4% | 14.6% | |
| Total under, habit ≥ 2 | 444 | 444 | 93.2% | 6.8% | |
| Total under, habit ≥ 3 | 173 | 173 | 96.3% | 3.7% | |

- The repeats at the lowest cut are the rule's own reach: at gap ≥ 5 the rule fires on most games,
  so a donor from the same night often lands on the same side.
- On the moneyline a placebo places 22-24% fewer bets, because a shuffled side can be a favourite
  beyond the -200 floor. That is also why its underdog share is 67-69%, not about half.

**Extremes of every number read, after the rule for impossible numbers:**

| Number | Lowest | Highest |
|---|---|---|
| Ticket share, clean rows: spread sides / over / under | 7 / 15 / 2 | 93 / 98 / 85 |
| A team's popularity | 26.44 | 72.37 |
| The gap's size | 0.00 | 36.19 |
| A team's mean over share | 43.93 | 92.10 |
| The smaller over habit | -16.78 | +6.77 |
| Deciding offers at C, spread number (HOME) / price | -24.5 / -135 | +21.5 / +110 |
| Deciding offers at C, total number / price | 195.5 / -125 | 262.0 / +105 |
| Deciding offers at C, moneyline price | -200 | +2500 |
| Highest EV on an offer a cell bets: spread / moneyline / total | | 0.251 / 0.676 / 0.075 |

**No rule reads a game that has not started.** The latest tip any game's number reads is at least
20 hours before that game's decision (1st percentile 22, median 47).

**C and D:** 7,230 games have a decision at C and 7,219 at D. Of the 7,219 with both, 7,205 are the
same fetch.

**The swapped rule, counted 2026-10-31:** at C and at D it removes FanDuel's spread and moneyline on
NBA_2021-12-10_BOS_PHX and nothing else. The next distances are 4.0, 3.5 and 3.0 (the `--smoke`
list of farthest spreads). The game is still bet at another book in both markets. The highest
spread EV among all deciding offers at C falls from 0.339 to 0.255. The 0.251 in the table above
counts only bets at the registered cuts and did not move.

**The credit line's games, counted 2026-10-31 from the choice, pooled 2021-22 to 2025-26.** `--smoke`
and `--full` stop if the control holds a game the cell cannot bet, or if a game only the cell bets
is not a level market.

| Cell | Cell's bets | Control's bets | Only the control | Only the cell, all level markets | Games the floor keeps out of both |
|---|---|---|---|---|---|
| Spread, gap ≥ 5 | 3,039 | 3,039 | 0 | 0 | 0 |
| Spread, gap ≥ 10 | 1,438 | 1,438 | 0 | 0 | 0 |
| Spread, gap ≥ 15 | 524 | 524 | 0 | 0 | 0 |
| Moneyline, gap ≥ 5 | 2,845 | 2,839 | 0 | 6 | 194 |
| Moneyline, gap ≥ 10 | 1,373 | 1,369 | 0 | 4 | 65 |
| Moneyline, gap ≥ 15 | 510 | 509 | 0 | 1 | 14 |

**Neither change moved a count above.** The bets per cell and season, the bands, the television
split, the prices, the games with a number, the fetches and the placebo table are the same as the
run before them.

**Run time, measured 2026-10-31 on the real data, sharing the machine with a test run:** the load
and market pricing took 192 seconds. One placebo run across the 9 cells took 1.0 second, so 200 take
about 3.4 minutes. One group of three cells, placebo aside, took 56 seconds, and there are 11 groups,
so about 10 minutes. The written reports took 17 seconds. All of it was graded against made-up
scores (`dummy_games`), so no real result was computed. **Projected `--full`: about 17 minutes, peak
memory 2.81 GB.** The first measurement, with other jobs holding the processor at 100%, projected
about 25 minutes. It prints a progress line per placebo batch and per group.

**To grade it** (the owner runs this; nothing below has been run):

```bash
NBA_RESEARCH_CACHE=C:/Users/micha/documents/bm-nba-q1trend/data/local/nba \
NBA_GAME2_GO=1 NBA_GAME2_RESULTS=C:/Users/micha/AppData/Local/Temp/nba_s/popular/results \
NBA_GAME2_BETS=C:/Users/micha/AppData/Local/Temp/nba_s/popular/results/bets \
PYTHONPATH=. PYTHONIOENCODING=utf-8 python -W ignore -m scripts.nba_s_popular --full
PYTHONPATH=. python -m scripts.nba_game2_verdict --results C:/Users/micha/AppData/Local/Temp/nba_s/popular/results --house5
PYTHONPATH=. python -m scripts.nba_s_popular --credit --results C:/Users/micha/AppData/Local/Temp/nba_s/popular/results
```

## 10. Changes after the first smoke run, before any bet was graded

**2026-10-31: no game keeps its own inputs in the placebo.** The first `--smoke` used a plain
permutation per date. On the real data 62% / 73% / 81% of the placebo's spread bets differed from
the real bets at gap ≥ 5 / 10 / 15 (53% / 66% / 75% on the moneyline, 74% / 81% / 83% on the total).
A plain permutation leaves about one game in eight on its own inputs (956 dates over 7,230 games),
and those games repeat their real bets. A placebo that shares bets with the real rule shares its
luck, which makes the bar harder to read. So each date's permutation now leaves no game in its
place (`no_fixed_points`). This reads no result. The share measured under the new rule is in
section 9.

**2026-10-31: on the moneyline the credit line's underdog control now bets the same games as the
cell.** Sections 7 and 8 registered it as the underdog in the same games, but the code applied only
the gap filter and not the cell's -200 floor. So at gap ≥ 5 / 10 / 15 the moneyline control held
194 / 65 / 14 pooled bets on games the cell cannot bet. On every one of them the underdog was the
popular team, at +176 to +1400, and they were 5.1% / 4.0% / 2.3% of the control's risk. The control
now keeps only games where the side against the popular team has a deciding offer at or above the
floor. Spreads already matched. Level markets stay in the cell only (section 7). A checker found
this by counting prices and the choice. No cell had been graded.

**2026-10-31: a spread with home and away swapped is not an offer.** Section 2 said spreads need no
rule. That was wrong: it measured a game's stored numbers across fetches, and one row was wrong at a
single fetch. FanDuel's row on NBA_2021-12-10_BOS_PHX has home and away swapped on both the spread
and the moneyline. It is coherent, so it stayed eligible, and at the decision it was that game's
best home offer in both markets (EV 0.339 and 0.333). It sat in the band below gap ≥ 5, which bar 5
reads, and in the placebo runs that give the game the home side at a cut, which bar 6 reads. The rule
and what it leaves in are in section 2. A checker found this from prices alone. No cell had been
graded.


## 11. Results (graded 2026-10-31)

Run `2026-10-31-popular`, stored in Supabase. 9 cells and 24 controls.

**0 of the 9 cells pass, and none clears the 95% interval. The family stays closed.**

| Cell | Bets | Units | Return | 95% interval |
|---|---|---|---|---|
| Against the popular team, spread, gap 5 | 3,039 | -74.68 | -2.3% | -5.6% to +1.0% |
| same, gap 10 | 1,438 | -6.09 | -0.4% | -5.5% to +4.5% |
| same, gap 15 | 524 | +21.09 | +3.7% | -4.3% to +11.6% |
| Against the popular team, moneyline, gap 5 | 2,845 | -39.52 | -2.4% | -7.1% to +2.4% |
| same, gap 10 | 1,373 | -10.93 | -1.6% | -8.9% to +5.9% |
| same, gap 15 | 510 | +16.81 | +7.2% | -5.7% to +20.3% |
| Full-game total, under, over habit 1 or more | 942 | -30.04 | -2.9% | -9.2% to +3.2% |
| same, over habit 2 or more | 404 | -53.73 | -12.3% | -21.0% to -2.8% |
| same, over habit 3 or more | 159 | -17.77 | -10.3% | -25.8% to +4.3% |

The return rises with the gap on both markets, and the two largest gaps stop well short of the interval. That
is a pattern in cells this search did not pass, and is not a result. The under at over habit 2 or more loses
clearly. That does not make the over a bet: the opposite side was not a registered cell.

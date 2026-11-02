# NBA postseason search: the two prop models that make money, on games no NBA model was graded on (pre-registered 2026-10-31, before any bet in it was graded)

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find
it"*. The sweep that followed ranked this first: the only two NBA mechanisms that have made money
have never been bet or graded on a play-in, playoff or Cup final game.

**Written before any bet was graded. Nothing below changes after a result is seen; a later change
gets its own dated line and reason.** Lab: `scripts/nba_s_postseason.py`. Pass/fail:
`scripts/nba_game2_verdict.py --house5` (`docs/nba_models_2026.md` 9.1's bars). The prices were
bought with mike's approval (272 games, 243,058 rows, 37,299 credits). Nothing further is bought.

## 1. What is tested, and what earlier searches did and did not cover

- **Tested:** whether `nba_prop_market` and `nba_prop_projection`, unchanged, make money on these
  games. There is no new rule, cut or feature to choose. The question is only whether the
  population carries over. Playoffs shorten rotations and draw more casual money; that could widen
  or shrink the over-lean both models feed on, and only a grade can say which.
- **Their regular-season record:** `nba_prop_market` 24,572 bets, +781.3 units, +2.96% (record
  4.3). `nba_prop_projection` 83,360 bets, +3,410.1 units, +4.12% (record 5).
- **Covered before:** every one of the eight searches graded regular-season games only. The stored
  prop history holds 0 of these 272 games, and `docs/sports/nba.md` says every NBA model skips them.
- **Not tested here:** the two shooting-luck game models. The sweep listed them as "reported only",
  and they need game lines this purchase did not buy.

## 2. Data

| What | Held | Source |
|---|---|---|
| Prop prices | 243,058 rows, 272 games, 14 markets, 10 books, one snapshot a game | `nba_postseason_prop_odds` |
| Games | 2023-24: 82 playoff, 6 play-in, 1 Cup final. 2024-25: 84, 6, 1. 2025-26: 85, 6, 1 | `nba_schedule` (phase, round, tip) |
| Plays | every game's plays | `nba_pbp`, `nba_pbp_games` |
| Who played | starter, ESPN's whole minutes, did not play | `nba_pbp_box` |
| Seconds played, inactive lists | every postseason game | `nba_player_game_adv`, `nba_game_inactives` |
| ESPN's own box score, counting stats | every game | the public sportsdataverse file, section 3.3 |

- The tables not in the research cache are pulled once, read-only, by indexed key, into the
  scratch folder (`--pull`, which regenerates all of them).
- **The moment.** Leads before tip are 54 minutes (150 games), 59 (63) and 64 (59). The one snapshot
  is each game's decision, as the regular-season archive's was (54 for 87% of bets, 64 for 13%).
  The live window of 45-57 minutes would drop 122 games, so it is not applied; each row reports the
  three leads beside the pool.
- **Pinnacle** quotes points, rebounds and assists in 270 of the 272 games, and threes and
  points+rebounds+assists in 179.

## 3. Settlement

`nba_player_game_log` has none of these games, so settlement is built.

### 3.1 The derivation from the play feed

| Stat | Rule |
|---|---|
| Points | the `points` of every scoring play, to `athlete_id_1` |
| Threes | scoring plays with `shot_value` 3, free throws excluded |
| Assists | `athlete_id_2` of a made field goal |
| Rebounds | play types 155 and 156, to `athlete_id_1`; team rebounds name nobody |
| Blocks | `athlete_id_2` of a missed shot whose text reads "blocks" (`athlete_id_1` is the shooter) |
| Steals | `athlete_id_2` of a play whose text reads "steals)" |
| Turnovers | the 22 turnover play types (`TURNOVER_TYPES`), to `athlete_id_1`; "No Turnover" and team turnovers count for nobody |

A heave (type 282) is not a field-goal attempt. It settles nothing; attempts are inputs to the
projection model. A player in ESPN's box who played and has no event is a line of zeros.

### 3.2 The validation on regular-season games: zero was not reached

Against `nba_player_game_log`, every game of 2023-24 to 2025-26. Rows differing, games differing:

| Stat | Rows | Games |
|---|---|---|
| Points | 61 | 30 |
| Rebounds | 585 | 338 |
| Assists | 233 | 127 |
| Threes | 11 | 8 |
| Blocks | 215 | 171 |
| Steals | 402 | 217 |
| Turnovers | 237 | 153 |
| Any of them | | 746 |

The causes read so far are in the feed, not the rule: a stale copy of a scoring play left beside
its replacement, and rebounds or steals credited to a teammate in the plays and not in the final
box. So the play feed alone cannot settle a bet to the standard asked for. **A second source on the
same games is required.**

### 3.3 The second source, and the rule that leaves a game out

ESPN's own box score is public and free
(`sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_<season>.parquet`,
the file the repo's play-by-play ingestor already reads). Against the log it differs in 34 of the
regular-season games. It holds every postseason game.

**A game is left out, and counted, when the derivation and ESPN's box disagree on any of the seven
stats for any player.** A line only one source holds counts as zeros in the other. Both sources
agree on what remains, so the number settled is the same whichever is named. **18 of the 272 are
left out, 254 kept:** 2 play-in and 16 playoff, 0 Cup finals (3 in 2023-24, 10 in 2024-25, 5 in
2025-26). No game differs on points or threes. They differ on rebounds in 10 games, assists 5,
blocks 3, steals 3, turnovers 2.

A game left out keeps its lines as projection-model history. Those inputs are not settlement, and
rows differ by one count.

**This file is not in Supabase.** `nba_pbp_box` keeps minutes only, and this job may not write. It
is read from the scratch folder and refetched by `--pull`.

### 3.4 Voids

The shipped rule (`scripts/nba_prop_market_lab.build_quotes`): a player takes the court when his
minutes are above zero or NBA.com's box gives him seconds. Measured on these games, a missing
seconds value is exactly the not-played rows (1,809 of 1,809). A bet on a player who did not take
the court is void and leaves the record.

### 3.5 Impossible numbers

Fixed before any offer was read. A row is refused and counted, never repaired, when:

- its line is outside the market's range (`LINE_RANGE`: half a point up to well past any single
  game on record), or
- an American price is under 100 or over 10,000 in size, or
- a two-way quote's implied sum is outside 1.00-1.15.

The range is set by hand and not read from the archive, because the archive itself stores a points
line of 113.5. A one-sided quote is not refused here; both rules decide on two-sided quotes only,
as shipped. Measured: 0 lines, 0 prices, 1 incoherent quote refused, of 181,506 rows in the nine
markets the rules read.

## 4. The rules, unchanged

### 4.1 `nba_prop_market` (`models/nba_prop_market.py`)

Points, rebounds, assists, threes, points+rebounds+assists. Pinnacle's proportional no-vig under
in the snapshot, its two-way quote coherent. Every bettable book at Pinnacle's exact line, coherent,
under at -200 or better. EV = fair under × decimal price - 1, floor 0.00. One bet per (game,
player, market), the best EV. **The soft-clock refusal applies:** a book whose clock is more than
10 minutes behind Pinnacle's is refused. The regular-season archive stored no clock and this
purchase does, so the shipped rule can run in full; without it is a control.

### 4.2 `nba_prop_projection` (`models/nba_prop_projection.py`)

| Market | Sides | EV floor |
|---|---|---|
| Steals | over + under | 0.02 |
| Rebounds | under | 0.01 |
| Blocks + steals | over + under | 0.05 |
| Blocks | under | 0.02 |
| Rebounds + assists | under | 0.04 |
| Threes | over + under | 0.04 |

The consensus main line only (DraftKings' two-sided line, else the line most bettable books hang,
ties to the lower). The best bettable price per side at -200 or better. The higher-EV side where
both clear. Never a proposition `nba_prop_market` bets. A quote more than 10 minutes behind the
freshest book's clock in its market is refused.

### 4.3 What the projection model needs for postseason dates

`scripts/nba_prop_projection_train.py` fits, for a season S:

| Part | How | For the postseason of S |
|---|---|---|
| Minutes and rate models | every usable played row, regular seasons 2018-19 to S | no postseason game is fitted on |
| Negative-binomial width | S as predicted by the fit through S-1 | |
| Calibration map | main-line pairs of priced regular seasons up to S | 2023-24: its own pairs. 2024-25: both. 2025-26: all three |

- **2025-26 is the shipped artifact itself** (`models/saved/nba_prop_projection_20261016_091702.pkl`).
  The two earlier postseasons are the same recipe stopped at their season. All fitted games are
  earlier than the games they price.
- **Rebuilt from the cache alone, the recipe reproduces the artifact:** its six widths and six maps
  to every digit printed, on the same 241,731 pairs. Run on the regular seasons, this lab's code
  rebuilds `nba_prop_market`'s 24,572 graded bets and the six cells' 54,571 bets of 2024-25 and
  2025-26, bet for bet.
- **A Cup final is played in December, mid-season.** It reads what a regular-season game of that
  date read: the fit through S-1, its width, and the map of pairs before S. For December 2023 that
  is the season's pairs before that week, with the 2022-23 stand-in for a market holding fewer than
  300, as 2023-24 was graded.

**Inputs at each decision, read as of that game:**

- **The player's and team's earlier games, including earlier games of this postseason.** The same
  frame code as graded, with box lines derived in section 3 added as history. The shipped frame
  filters to regular-season lines (`box_from_log`), so this is a stated difference, and a pass needs
  that filter opened and the results step writing postseason lines.
  - Why not regular-season lines only, the filter as it stands: every row in the conference finals
    and Finals would then read the frame's maximum of 30 days since the player last played. In
    training 2.3% of rows look like that (4,458 of 191,095) and they play 0.874 of their recent
    minutes, against 1.029 for rows under 5 days. Projected minutes fall from 18.3 to 15.8 in the
    conference finals and from 17.2 to 16.2 in the Finals. That is a false reason to bet unders, not
    a test of the model. It is graded anyway, as a control, never judged.
  - Earlier postseasons of 2018-19 to 2022-23 are not in the history.
- **No injury report.** `nba_injury_report`, `nba_injury_asof` and `nba_injury_report_pulls` hold no
  play-in or playoff game of these seasons (2026-05 holds 8 rows on 4 games from one pull, dropped so
  those games read as the others). `injuries` holds NBA rows from 2026-06 only. So every play-in and
  playoff row reads "no report", the frame's own state for an uncovered game, and "never a player
  listed Out" cannot apply.
  - **This is a measured difference from the regular-season grade:** 1.0% of postseason rows are
    covered (the three Cup finals), against every game from 2019-20 on and 67% of 2018-19 in
    training. The model's "no report" branch learned from that part of 2018-19.
  - It does not touch `nba_prop_market`, whose only input is Pinnacle's price. It may hurt the
    projection cells: teammates' absences are unknown to the model and known to the line.
  - A later backfill of the free official reports could be re-run as a control. It never replaces
    this grade.

## 5. The cells

Every cell is decided at the one snapshot, at the best of `config.BEST_LINE_BOOKMAKERS` (eight
books; never Pinnacle or Bovada), one unit to win, risk capped at 3, a push out of the denominator.

| Family | Cell | Side | Cut |
|---|---|---|---|
| PM | `nba_prop_market`, its five markets pooled | under | EV ≥ 0.00 |
| PJ | steals | over + under | EV ≥ 0.02 |
| PJ | rebounds | under | EV ≥ 0.01 |
| PJ | blocks + steals | over + under | EV ≥ 0.05 |
| PJ | blocks | under | EV ≥ 0.02 |
| PJ | rebounds + assists | under | EV ≥ 0.04 |
| PJ | threes | over + under | EV ≥ 0.04 |

**7 cells judged.** No cut is chosen here: each is the shipped floor.

**How a proposition passes through the game harness.** `H.choose` keeps one bet per (game, market)
and `H.grade` settles a "totals" row on the two scores. So each proposition is one synthetic game:
id `<game>|<player>|<market>`, market "totals", home score the stat, away score 0. An over wins
above the line, an under below, a push returns the stake; a void has no row and drops out at the
join. The whole-day bootstrap reads the real date.

**Bands (bar 5), on the EV floor:**

- `nba_prop_market`: [-0.01, 0), [0, 0.01), 0.01 and up.
- Each projection cell, relative to its floor f: [f-0.02, f), [f, f+0.02), [f+0.02, f+0.05),
  [f+0.05, f+0.10), f+0.10 and up. These edges are new, because the projection search graded nested
  floors, not bands. They are wider than its 0.01 grid steps because a 0.01 band here is thin enough
  that one bad night would decide bar 5; EV on this card runs to 0.5 and more, against 0.13 for the
  first rule. Fixed from the two rules' EV scales, before any band was graded.
- A band under 30 bets is reported and not judged.

**Reported beside every row, never bars:** DraftKings alone; the play-in, the playoffs and the Cup
final separately; the three leads; bets void.

## 6. Bars, placebo, controls

**Section 9.1's house standard, unchanged, pooled over the three postseasons:**

1. 200 or more pooled bets.
2. The pooled whole-day bootstrap 95% interval of the return is above zero (4,000 resamples, seed 7).
3. At least two postseasons have 30 or more bets, and of those all but at most one are positive.
4. Beats the blind bet on its dominant side, on the same propositions at the best price. For
   `nba_prop_market` that is a blind under at Pinnacle's line.
5. Each band from section 5 with 30 or more bets is positive, and the cell's own return is above zero.
6. The return on the choosing seasons beats the 95th percentile of 200 placebo runs.

2023-24 and 2024-25 are the choosing seasons bar 6 reads (`P3.choosing`, as section 12 did). Nothing
is fitted or chosen on them. Closing-line value cannot be read from one snapshot a game.

**Placebo, 200 runs, seeds 1-200.** Each proposition keeps its own line, books and prices and takes
another proposition's number, within (date, market):

- `nba_prop_market`: Pinnacle's no-vig under.
- `nba_prop_projection`: the model's mean over its main line, re-priced through the same width and
  map (the projection search's placebo).
- The caps control: both, then the caps run again.

**A (date, market) with fewer than 5 propositions joins the other thin propositions of its (season,
round, market).** The rounds are the play-in, first round, conference semifinals, conference finals,
Finals and Cup final. No proposition is alone in its group on the real data.

**Is the placebo a null on real data? (no result read; 10 seeds; the final run is in section 7)**

| Cell | Placebo bets that are not real bets | Share of propositions the cell bets |
|---|---|---|
| `nba_prop_market` | 0.76 | 0.17 |
| Steals | 0.62 | 0.53 |
| Rebounds | 0.36 | 0.46 |
| Blocks + steals | 0.62 | 0.48 |
| Blocks | 0.32 | 0.38 |
| Rebounds + assists | 0.45 | 0.27 |
| Threes | 0.67 | 0.50 |

It differs on every round, the thin ones included (`nba_prop_market`: 0.80 on the Finals, 0.70 on
the Cup finals). Rebounds and blocks are low for a reason a wider group does not fix: shuffling
within a season, or across all three postseasons, moves their shares by 0.03 at most (rebounds 0.36
to 0.38, blocks 0.32 to 0.34). Those cells bet about half their propositions, and much of the choice
is the price, not the model: the 2025-26 map's slope on rebounds is 0.48 and on rebounds + assists
0.31. So bar 6 there asks whether the model adds to what the price alone selects. A cell earning
from the price alone will not clear it, which is the question it should answer. This is stated now
so it is not read later as a broken bar.

**Controls, graded and reported, never judged** (`control_*` families):

| Control | What |
|---|---|
| `control_PJ_card` | the six cells pooled, caps off, with 200 placebo runs |
| `control_caps_on` | both models through the shipped door (`scripts/nba_props_card.choose`), with 200 placebo runs |
| `control_PM_no_clock`, `control_PJ_no_clock` | the population as the archive graded it, without the clock refusal |
| `control_PJ_frozen_history` | the six cells on regular-season history only (4.3) |

- **Caps.** The door takes one bet a game across both models, strongest first by each model's own EV
  percentile, and four a night. **No date holds more than 4 of these games, so the night cap never
  binds**, and caps on means one a game. Caps off is the seven judged cells.
- **A thin row is still reported.** The play-in (18 games) and the Cup final (3) read "too few games
  to tell", not "it loses".
- **Expected passes by chance:** 7 × 0.025 ≈ 0.18 cells clear bar 2 alone, before correlation. Bars
  3 to 6 make a chance pass rarer still.
- **A pass is built live** (CLAUDE.md 2) with the prices it lays stated first. It needs the results
  step writing postseason box lines and the frame reading them.

## 7. What the lab writes, and how to run it

```
python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_postseason --pull
NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_postseason --smoke
NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<dir> NBA_GAME2_BETS=<dir>/bets NBA_RESEARCH_CACHE=<cache> \
    PYTHONPATH=. python -m scripts.nba_s_postseason --full
python -m scripts.nba_game2_verdict --results <dir> --house5
python -m scripts.nba_s_postseason --report <dir>
```

`--smoke` runs the synthetic checks, then prints on the real data only counts, extremes, the
placebo's differing share and a timed placebo run graded on a table of zeros. It never grades a real
bet. `--full` refuses without its three switches and writes `cells_registered.parquet`,
`cells_controls.parquet` and each cell's bets. Counts before grading follow in a dated section once
the lab's own run has printed them.

### 7.1 Counts before grading (2026-10-31)

Counted by `python -m scripts.nba_s_postseason --smoke`, before any cell was graded. No result of a
bet was read. The timed placebo run grades on a table of zeros, so no result exists to read.

**Found by the first count, fixed before grading.** Nearly every bet counted as void (1,949 of
`nba_prop_market`'s 1,951). `pid_of` built each synthetic game's id with one market name aligned by
row label, so all but the first row of every market's table came out empty. A grade would have
dropped almost every bet without an error. It now builds by position, and
`test_every_synthetic_game_id_is_filled_and_distinct_on_many_rows` fails on the old code.

**2026-10-31: found by a checker, fixed before grading. No cell had been graded and no result of a
bet was read.** Two `nba_prop_market` bets worth exactly nothing were refused, and the rebounds cell
then bet them, which 4.2 forbids. Both are 2025-26 DraftKings unders: Paul George under 5.5 rebounds
at -126 against Pinnacle's +116 / -140, and Julian Champagnie under 4.5 rebounds at +117 against
Pinnacle's -130 / +107. The floor is EV ≥ 0.00 and the shipped rule takes both.

- **Cause.** The lab built the fair under from 1 / decimal, which landed each one rounding step below
  zero (-1.1e-16). The rounding is in the fair price, so sending that price through
  `config.expected_value` returns the same number. The lab now builds it as the shipped
  `fair_under` does. The rules, floors and cells are unchanged.
- **What moved.** The tables below are recounted. `nba_prop_market` 2025-26 533 to 535, pooled 1,951
  to 1,953. Rebounds 2025-26 457 to 455, pooled 1,598 to 1,596. The six cells pooled 8,353 to 8,351.
  The bands and the frozen control's count moved with them. The caps control's counts did not.
- **What now checks it.** The lab's EV equals the shipped gate's to the last bit on all 52,922 offers,
  and on the 53,038 of the no-clock control. `--smoke` runs the shipped `find_bets` game by game on
  these quotes: 1,953 bets, 1,953 in the lab's, the same book, price and line on all of them. The
  older check could not see this, because the research lab's stored list used the same arithmetic.
  48 offers sit on the floor, none just below it. No projection offer is within a rounding step of
  its floor, so this cannot reach those cells.
- **The re-run.** One placebo run of every row took 2.88 seconds, so 200 take 9.6 minutes; `--smoke`'s
  peak was 5.29 GB.

Bets the rule would place, at the best deciding price, in the 254 games kept:

| Cell | Propositions | 2023-24 | 2024-25 | 2025-26 | Pooled | Void | Play-in | Playoffs | Cup final | Unders | Lowest / median / highest price | Top EV |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `nba_prop_market` | 11,400 | 958 | 460 | 535 | **1,953** | 0 | 91 | 1,834 | 28 | 1,953 | -192 / -104 / +210 | 0.13 |
| Steals | 3,377 | 862 | 327 | 615 | **1,804** | 16 | 124 | 1,654 | 26 | 1,309 | -200 / +120 / +390 | 0.53 |
| Rebounds | 3,436 | 571 | 570 | 455 | **1,596** | 15 | 132 | 1,442 | 22 | 1,596 | -166 / +102 / +164 | 0.49 |
| Blocks + steals | 2,625 | 696 | 190 | 367 | **1,253** | 12 | 83 | 1,159 | 11 | 1,033 | -198 / +110 / +360 | 0.53 |
| Blocks | 3,179 | 439 | 348 | 433 | **1,220** | 5 | 60 | 1,156 | 4 | 1,220 | -200 / -105 / +190 | 0.66 |
| Rebounds + assists | 3,416 | 350 | 293 | 270 | **913** | 3 | 55 | 843 | 15 | 913 | -145 / +105 / +146 | 0.34 |
| Threes | 3,134 | 510 | 516 | 539 | **1,565** | 19 | 103 | 1,448 | 14 | 733 | -200 / +120 / +600 | 0.71 |
| Control: the six cells pooled | 19,167 | 3,428 | 2,244 | 2,679 | 8,351 | 70 | 557 | 7,702 | 92 | 6,804 | -200 / +105 / +600 | 0.71 |
| Control: caps on, both models | 27,165 | 86 | 81 | 87 | 254 | 3 | 16 | 235 | 3 | 182 | -160 / +135 / +360 | 0.71 |

- `nba_prop_market`'s void column is 0 because the research code drops a player who did not play
  before it builds offers. The projection cells carry theirs to the grade.
- Every registered cell clears the 200-bet bar on count, and every postseason holds 30 or more bets
  in each cell. The play-in and the Cup final are thin on their own.
- **Caps on:** every kept game has a bet, 234 from the projection model and 20 from the Pinnacle
  rule. Three are void, so 251 would grade.
- **Regular-season history only** (the frozen control) bets 11,351 of the six cells' propositions
  against 8,281 for the graded history, both after voids. That is what section 4.3's false reason to
  bet unders looks like as a count.

**Bets in each band** (a band under 30 is reported, not judged; none is):

| Cell | Just below the cut | Then, upward to the open top band |
|---|---|---|
| `nba_prop_market` | 828 | 667, 1,286 |
| Steals | 333 | 298, 402, 512, 592 |
| Rebounds | 256 | 249, 358, 455, 534 |
| Blocks + steals | 220 | 208, 274, 306, 465 |
| Blocks | 138 | 149, 200, 303, 568 |
| Rebounds + assists | 295 | 254, 290, 264, 105 |
| Threes | 338 | 265, 380, 402, 518 |

**Extremes read.** Lines run 0.5-39.5 on points, 0.5-16.5 rebounds, 0.5-12.5 assists, 0.5-5.5
threes, 2.5-57.5 points+rebounds+assists, 0.5-2.5 steals, 0.5-4.5 blocks, 0.5-6.5 blocks+steals,
1.5-24.5 rebounds+assists; all on the half point. The longest prices on file (-6,600 on a blocks
under, +1,500 on a blocks over, -2,500 on a blocks+steals over) are never laid: the -200 floor
refuses the first and third, and blocks bets unders only. Refused: 0 lines, 0 prices, 1 incoherent
two-way quote. 5,142 one-sided quotes decide nothing, as shipped.

**Highest-EV offers, read one by one.** `nba_prop_market`'s top is 0.13: an assists under at +155
against Pinnacle's 0.444. The projection model's top is 0.71. Eleven of its top twelve are threes
overs at +100 to +350, eight of the twelve at BetMGM and nine in 2024-25. Its regular-season card
reached 0.9981 (`models/nba_prop_rank.py`), so this is inside what it has always shown. None is an
impossible number; none is refused. It is the card's known habit of wide EV on plus-money overs, at
stakes of a unit or less.

**The fit, reproduced.** Widths and maps equal the shipped artifact's in all six markets, on 241,731
pairs against 241,731. `nba_prop_market`: 24,572 rebuilt, 24,572 stored, 24,572 in both. The six
cells on 2024-25 and 2025-26: 54,571, 54,571, 54,571 (2023-24 ran on weekly maps and is not
compared). Those checks read who was bet from the stored lists, never what the bets won.

**The archive's stray line.** One regular-season row holds a points line of 113.5. Neither model's
record is touched: neither bet can reach it. Flagged, not repaired.

**The placebo.** The 20-seed run matches section 6's table to two decimals, no proposition alone in
its group.

**Time and memory.** One placebo run of every row takes 3.18 seconds on real data with the machine
at 100% under other jobs, so 200 runs take 10.6 minutes. A dry run of `--full`'s whole path on the
table of zeros took 86 seconds with 3 placebo runs. `--smoke`'s peak was 5.23 GB. Projected `--full`:
**about 20 minutes** with this scratch folder's fits and frames cached, about 30 from empty.

## 8. Each rule watched failing

Each line was broken once in a copy of the lab's source, and the named test failed. 44 rules; the
first pass caught 43. `threes count twos` was uncaught because no test read a made two, so
`test_a_made_two_is_not_a_three` was added and watched failing. On the unbroken code 58 tests pass.

| Rule broken | Test that failed |
|---|---|
| Assist credited on any shot | `test_an_assist_goes_to_the_passer_on_a_made_shot_only` |
| Block to the shooter | `test_a_block_goes_to_the_blocker_not_the_shooter` |
| Steal to the passer | `test_a_steal_goes_to_the_stealer_and_the_turnover_to_the_passer` |
| Heave counted | `test_a_heave_is_not_a_field_goal_attempt` |
| "No Turnover" row counted | `test_a_no_turnover_row_and_a_team_turnover_count_for_nobody` |
| Offensive rebound dropped | `test_rebounds_are_offensive_plus_defensive_and_team_rebounds_count_for_nobody` |
| A made two counted as a three | `test_a_made_two_is_not_a_three` |
| Free throw not a point | `test_points_threes_and_free_throws_come_from_the_plays` |
| Cross-check ignores a line one source holds | `test_a_line_only_one_source_holds_counts_as_zeros_there` |
| Seconds ignored for a void | `test_a_player_takes_the_court_on_minutes_or_seconds` |
| Synthetic id by label | `test_every_synthetic_game_id_is_filled_and_distinct_on_many_rows` |
| Market rule: any line | `test_the_rule_takes_only_pinnacles_exact_line` |
| Market rule: clock ignored | `test_the_rule_refuses_a_book_ten_minutes_behind_pinnacle` |
| Market rule: unknown clock refused | `test_the_rule_counts_a_book_with_no_clock` |
| Market rule: every market | `test_the_rule_has_five_markets` |
| Market rule: incoherent Pinnacle allowed | `test_the_rule_needs_a_coherent_pinnacle` |
| Market rule: wrong fair price | `test_the_rules_ev_is_pinnacles_no_vig_under_times_the_price` |
| Card: Out player, or too few games, allowed | `test_the_card_never_prices_a_player_out_or_a_row_with_too_few_games` |
| Card: every line | `test_the_card_reads_draftkings_line_else_the_line_most_books_hang` |
| Card: clock ignored | `test_the_card_refuses_a_quote_ten_minutes_behind_the_freshest_of_its_market` |
| Card: a proposition the rule bets, or a side the cell does not bet | `test_the_card_offers_only_each_markets_sides_and_never_a_rule_proposition` |
| Card: map skipped | `test_the_map_moves_the_probability` |
| Card: lower-EV side | `test_a_both_sides_cell_bets_its_higher_ev_side_only` |
| Playoff game reads the earlier fit; artifact not used for 2025-26 | `test_a_playoff_game_reads_the_fit_through_its_season_and_the_shipped_artifact_for_2025_26` |
| Cup final reads a later fit | `test_a_cup_final_reads_the_fit_before_its_season` |
| Cup final map reads its own season | `test_a_cup_final_map_never_reads_its_own_season_after_2023_24_or_a_later_game` |
| Thin group not widened | `test_a_thin_date_joins_the_other_thin_propositions_of_its_round` |
| Shuffle leaves its group | `test_a_shuffle_stays_inside_its_group_and_keeps_every_value` |
| Seed not used | `test_seeds_give_different_shuffles_and_the_same_seed_repeats` |
| Market placebo returns the real prices | `test_on_a_one_game_date_the_placebo_bets_differ_from_the_real_bets` |
| Projection placebo returns the real means | `test_the_projection_placebo_moves_the_mean_and_reprices_it` |
| 20 placebo runs in place of 200 | `test_each_cell_writes_what_the_verdict_reads_and_the_verdict_judges_it` |
| Bad line, bad price, incoherent quote kept | `test_a_line_outside_its_markets_range_is_refused`, `test_an_impossible_price_is_refused`, `test_an_incoherent_two_way_quote_is_refused_and_a_one_sided_one_is_kept_for_the_rules_to_refuse` |
| Caps by raw EV, no game cap | `test_the_caps_take_one_bet_a_game_strongest_by_each_models_own_percentile` |
| `--full` without its switches | `test_full_refuses_without_the_owners_switches` |
| Timing table reads results | `test_the_blind_table_used_to_time_a_run_holds_no_result` |
| A void, or a game left out, stays settled | `test_a_game_left_out_and_a_void_have_no_synthetic_game` |
| A market's stat wrong | `test_a_stat_is_the_markets_own_sum` |
| 2026-10-31: fair under from 1 / decimal (the old code) | `test_an_offer_worth_exactly_nothing_clears_the_floor_as_the_shipped_gate_has_it`, `test_the_rules_ev_equals_the_shipped_gate_to_the_last_bit`, `test_a_rule_bet_worth_exactly_nothing_is_never_a_projection_bet`, `test_the_lab_bets_what_the_shipped_code_bets_at_and_around_zero`, `test_the_synthetic_checks_pass` |
| 2026-10-31: floor above zero, not at it | `test_an_offer_worth_exactly_nothing_clears_the_floor_as_the_shipped_gate_has_it`, `test_the_registered_cells_are_the_rule_and_the_six_market_cells_at_their_shipped_floors` |
| 2026-10-31: a rule bet left on the projection card | `test_a_rule_bet_worth_exactly_nothing_is_never_a_projection_bet` |
| 2026-10-31: comparison to the shipped code ignores the price, or drops what only the lab bets | `test_the_comparison_to_the_shipped_code_finds_a_missing_bet_and_a_different_offer` |
| 2026-10-31: the shipped code run where it bets nothing | `test_the_lab_bets_what_the_shipped_code_bets_at_and_around_zero` |
| 2026-10-31: the floor count counts every offer | `test_floor_ties_counts_offers_a_rounding_step_from_their_floor_and_no_others` |

**Data checked to contain what a test claims.** The first version of the projection placebo test held
one proposition a market, so its shuffle moved nothing; it failed on real code, and now holds six
propositions in one group and asserts that. The two prices that are worth exactly nothing are checked
as exact fractions inside their own test, and the shipped code is run on them, so that test cannot
pass on a price that is merely close.

2026-10-31: the dated rows hold seven breaks, each made once, and all seven were caught. On the
unbroken code 66 tests pass.


## 9. Results (graded 2026-10-31)

Run `2026-10-31-postseason`, stored in Supabase. 7 cells and 5 controls, 272 games, three postseasons.

**1 of the 7 cells passes: `nba_prop_market`'s same-line under, five markets, EV 0.00 or better.**

| Cell | Bets | Units | Return | 95% interval | Seasons positive | Fails |
|---|---|---|---|---|---|---|
| **`nba_prop_market`, under, five markets** | 1,953 | +138.87 | +6.8% | +2.1% to +11.3% | 3 of 3 | none |
| Projection, rebounds + assists, under, EV .04 | 910 | +44.82 | +5.1% | -0.9% to +11.0% | 3 of 3 | interval, bands, placebo |
| Projection, blocks + steals, EV .05 | 1,241 | +36.31 | +2.9% | -2.5% to +8.5% | 2 of 3 | interval, bands |
| Projection, blocks, under, EV .02 | 1,215 | +16.07 | +1.2% | -3.9% to +6.7% | 2 of 3 | interval, bands |
| Projection, threes, EV .04 | 1,546 | +10.16 | +0.7% | -3.9% to +5.3% | 1 of 3 | interval, seasons, bands |
| Projection, rebounds, under, EV .01 | 1,581 | +9.61 | +0.6% | -4.1% to +5.3% | 2 of 3 | interval, bands, placebo |
| Projection, steals, EV .02 | 1,788 | -7.40 | -0.4% | -5.1% to +4.0% | 1 of 3 | interval, seasons, blind, bands |

Controls, never judged: the shipped caps, one bet a game shared by both models and four a night, 251 bets, +12.37
units, +6.7%, -8.7% to +20.9%. The rule with no decision clock, 1,955 bets, +140.87 units, +6.9%. The six
projection cells as one card, 8,281 bets, +109.57 units, +1.3%, -1.2% to +3.9%.

### 9.1 The independent check, 2026-11-01

A separate checker rebuilt the passing cell in plain code from the raw quotes and ESPN's box, using neither this
lab's chooser nor its grader. Scripts are under `%TEMP%/nba_s/verify_postseason/`.

**The result is real as arithmetic and it holds with caveats. It is not what its name suggests.**

- **Rebuilt exactly.** 1,953 bets in both, 0 differences on player, market, line, side, price, book, result, units
  or EV. Nothing reads information from after the decision: the rule's only inputs are one snapshot's prices, 54 to
  64 minutes before tip, and no row is at or after tip.
- **Most of it is a general lean to unders, and the rule does not pick winners.** The blind under over the same
  markets returns +2.69% on 11,314 bets (+0.53% to +4.81%). The cell beats that by 4.09 points (+0.06 to +8.05). But
  its unders beat Pinnacle's fair chance by 2.49 points and the ones it skipped by 3.39, so the rule adds nothing on
  who covers, and stated EV has a correlation of -0.004 with winning above fair. It works as a price filter on top of
  the lean. About +41.4 of the +138.87 units would be there if Pinnacle's fair chance were right; the other 70% came
  from unders winning more often than that.
- **The floor at zero separates nothing.** The band it refuses, EV -3% to just under 0, returns +6.86% on 2,908 bets.
- **Do not plan on +6.8%.** The lean in this sample is larger than in the regular seasons (+3.24 points against
  +1.20). At the regular-season lean the same bets would return about +4.4%.
- **It rests on few events.** 117 bets on players who played under 15 minutes hold +65.51 units; the other 1,836
  return +3.82% (-0.84% to +8.39%). Minutes are known only after the game, so this says where the money sits and is
  not a filter. Removing the top 5 players by units, the best 5 dates, BetMGM's bets, the assists market, or the
  conference semifinals each takes the interval's low end just below zero.
- **FanDuel alone is flat.** Rule re-run on one book: DraftKings +6.54% (-0.40% to +12.93%), BetMGM +8.59%, Caesars
  +5.89%, FanDuel -0.13%. The four main books together: 1,701 bets, +123.13 units, +6.89% (+2.11% to +11.59%).
- **The live caps change everything.** The pass is with every bet placed. The shipped caps place 251 bets, only 20 of
  them this rule's. The rule alone at one bet a game is 251 bets, +23.36 units, +9.71% (-3.82% to +22.81%). Neither
  clears the interval.
- **Prices:** -192 to +210, median -104. 61 bets are worse than -150 and none is worse than -200.
- **Latent, did not fire:** `scripts/nba_prop_market_lab.py:190`, the loose name match, could turn one player into a
  namesake if a priced player were on neither box. All ten pairings it made here read correct. And section 3.3's
  "second source" is ESPN's own box beside ESPN's feed; NBA.com checks points, threes and most assists, while rebounds
  rest on ESPN alone.

# NBA search: props off Pinnacle's line, the soft-book consensus, and a market-anchored prop model (pre-registered 2026-10-30, before any cell was graded)

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find
it"*. The sweep that followed proposed two prop ideas that were never judged under the house
standard (`docs/nba_models_2026.md` section 9.1):

- **(a) Two rules the first search did not ship.** The off-line rule: a deciding book hangs a
  different line from Pinnacle's, and the side the gap favours is bet (record 4.3: +2.2% on
  7,123 bets). The soft-consensus rule: where Pinnacle is absent, a book's price is compared with
  the other books' median at the same line (record 4.3: +1.8% on 17,386 bets).
- **(b) A market-anchored prop model.** Pinnacle's no-vig price (else the soft books' median) as
  an unpenalised offset, moved by the projection model's disagreement and its inputs. This is
  the recipe of the live NHL moneyline model, applied to props.

**Written before any cell was graded. Nothing below changes after a result is seen; a later
change gets its own dated line and reason.** Lab: `scripts/nba_s_propoffline.py`. Pass/fail:
`python -m scripts.nba_game2_verdict --results DIR --house5` (section 9.1's bars). No data is
bought, no Odds API call is made, and nothing is written to the database.

## What earlier searches covered, and what they did not

- **Record 4.3** judged both rules in (a) under section 1's thirteen bars, and did not ship them.
  The off-line rule: 2025-26 alone −1.82 to +4.21, profit from 64-minute snapshots only. The
  consensus rule: fails with Hard Rock or FanDuel removed, DraftKings alone −1.05%.
- **The house standard was never applied to them.** Section 6.7 applied it to the second search's
  422 game-market cells. Sections 8.2 and 9.8 re-judged the first search's game-market rules. No
  prop rule was re-judged. The same stricter bars first rejected the shooting-luck over, which
  then passed the house standard and ships (records 6.6 and 6.7).
- **The anchored recipe was graded on game markets only** (record 8.1 to 8.4: nothing passed).
  The NFL's market-anchored simulation failed, but it anchored the median and sold tails at
  alternate lines (`docs/nfl_prop_method_search.md`). This model stays at the market's own line
  and lets the projection move the price.
- **The shipped projection model is not anchored.** Its probability is mapped from its own log-odds
  (record 5), and it never bets a proposition the Pinnacle rule holds. So the two sources of prop
  edge have never been combined in one number.
- **Not re-judged here:** the first search's single-market carve-outs, its power no-vig variant, and
  the off-line rule measured against the consensus where Pinnacle is absent. The sweep named the
  pooled Pinnacle off-line rule and the consensus rule, and those are what is tested.

## Data

Everything is read from the research cache of 2026-10-30 (a cache of Supabase). A local file this
search creates is regenerable from that cache.

- **Prop quotes:** `nba_props`, the 14 stored markets, one snapshot a game with every book in it,
  2023-24, 2024-25 and 2025-26 (`game_date` before 2026-10-20). 1,230 games a season.
- **The decision:** that snapshot, when it sits 45-75 minutes before tip (decision point D). 3,666
  of 3,690 games qualify: 1,225 / 1,224 / 1,217. Earlier or later snapshots are dropped, not moved.
- **Books:** the eight of `config.BEST_LINE_BOOKMAKERS` decide. Pinnacle is the reference and never
  a deciding price. Bovada is never a deciding price. It counts among "the other books" in the
  consensus rule, as the first search counted it.
- **Names and settlement:** the first search's own table (`scripts/nba_prop_market_lab.build_quotes`,
  imported unchanged). It matches a book's name to one player on the game's two teams and refuses
  namesakes. A player who took no court time voids, and his quotes are not candidates.
- **The projection:** the worker-input re-fit of record 4.5, through `models/nba_props.py` and the
  input lists of `models/nba_prop_projection.py`. Those folds are not on disk any more, so the lab
  refits and caches them. The cache is built from the research cache alone.

**What each lab run reads of a result.** Only the anchored model's fit and the graded run read a
stat line. The fit reads seasons earlier than the one it prices. `--smoke` grades nothing.

## Rules every cell is graded under

Section 6.2's rules, through the shared harness (`scripts/nba_game_harness.py`, `H.run_cells`).

- **One proposition is one "game" to the harness.** A proposition is (game, player, market). It
  gets a row in the harness's games table with the settling stat as its home score and 0 as its
  away score, and its offers are filed under the harness's total market. So the harness's own code
  chooses one bet per proposition, and its own `settle` gives over when the stat is above the line.
  The real game, player and market are kept in a table the bets join to.
- **Price:** the best-EV offer among the deciding books on the cell's side, a coherent two-way quote
  (implied sum 1.00 to 1.15), −200 floor. DraftKings alone is reported beside every cell.
- **Units:** one unit to win, risk capped at 3. A push returns the stake and leaves the denominator.
  No stored line in the window is a whole number (0 of 2,734,959 rows), so no push is expected.
- **One bet per (game, player, market)** in a cell, no game or night cap.

**Impossible numbers, stated up front.** A row is not eligible when:

1. Its name is not a player on either team. Bovada filed "Bkn Nets Alternate Total" as a player
   points prop at 113.5. The name match drops it.
2. It is one-sided or incoherent. Coherence removes the prices like −2,000,000.
3. Either price is beyond ±10,000. A −300,000 under beside a +3,000 over is coherent and means
   nothing.
4. Its line is above the highest number any player has posted in that stat in the stored box scores
   (2018-19 on). `--smoke` prints each ceiling and what it removes.

**A wide gap is not an impossible number, and is not removed.** Pinnacle can be the stale one
(Jonathan Kuminga points + rebounds + assists on 2025-11-12: Pinnacle 23.5, the deciding books
16.5 to 20.5). The price is real, and removing it would change the rule being re-judged. So the bets
are reported beside by gap size, by book, and with offers more than 0.20 above the price's implied
chance taken out (0.20 is `config.MAX_EDGE_CAP`, the pre-game scorer's limit).

## Definitions

**Reference, in family OL.** Pinnacle's coherent two-way quote on the proposition: its line and its
proportional no-vig over.

**Fair price at another line, in family OL.** The first search's: a negative-binomial count, variance
= mean + alpha × mean², alpha fitted per market on box scores of seasons strictly before the graded
one (`nb_alpha`, `NBTable`, imported unchanged). Pinnacle's line and no-vig price fix the mean, and
the distribution gives the chance of over at the book's line. The first search found this overstates
the favoured side by about 1.5 points. It is kept, because this is a re-judging. The cuts are read
with that in mind.

**Off-line offer.** A deciding book's coherent quote whose line differs from Pinnacle's, in the same
snapshot. The gap is the book's line minus Pinnacle's.

**The side the gap favours.** Under when the book's line is above Pinnacle's, over when it is below.
That is the only side bet, as in the first search.

**Consensus fair price, in family CS.** On a proposition with no Pinnacle quote: for each deciding
book's quote, the median proportional no-vig over of the OTHER books (Bovada included) at the same
line, at least 3 of them. The book being bet is left out of its own fair price.

**EV.** The fair chance of the side times the decimal price, minus 1.

**The anchored model (family AN).**

- **Its propositions:** the 12 count markets. Double-doubles and triple-doubles have no projected
  mean and are not in this family.
- **The market's number:** Pinnacle's coherent no-vig over at its line where it quotes (reference
  kind "pinnacle"). Otherwise the deciding books' main line, the first search's `main_line_table`
  (their commonest line; a tie goes to DraftKings' line, then the line nearest the median, then the
  lower one), and their median no-vig over there, at least 3 books (reference kind "consensus"). A
  proposition with neither has no model number.
- **Offset:** the log-odds of that number, unpenalised.
- **Inputs, as of the snapshot** (a report counts as known 30 minutes after its printed time: dated line below):
  1. The projection's disagreement: the log-odds of the projection's chance of over at the
     reference line, less the offset, limited to ±3.
  2. Projected minutes.
  3. Teammates' minutes ruled out, and how that compares with the absences his recent minutes
     were played through (`tm_o_min`, `d_o_min`).
  4. Teammates' minutes listed Questionable (`tm_q_min`), and whether he is (`own_q`).
  5. Opponents' minutes ruled out (`opp_o_min`).
  6. Home, rest and back-to-back.
  7. His team's and the opponent's pace.
  - A report input reads 0 where no report covers the game. Pace and rest missing reads the training
    mean.
- **The fit:** `OffsetLogit` and `choose_C` from `models/nhl_moneyline_anchored.py`, imported
  unchanged. One model per (market, reference kind), on every earlier-season proposition with a
  reference, a player who played, and a stat line. The penalty is chosen by `choose_C`'s rule. With
  one training season it is 0.003, the grid's first value (record 8.1's line). A model needs 300 or
  more training rows. Fewer means no model and no bet that season.
- **The move** is everything the fit adds to the offset, intercept included. The model's chance of
  over is the offset plus the move, back through the logistic.
- **The projection:** two-stage (minutes × per-minute rate, all seven base stats). Fold S is fitted on
  2018-19 through S−1. Each market's width is fitted on season S−1 as predicted by the fold that never
  saw it. Fold S's means are what prices season S, and they are out of sample in every training row.
- **Who is left out:** a player listed Out at the decision (on that same 30-minute read), and a player with fewer than 10
  career games, have no model number (the projection's own rule, record 5).

**Why the anchored model bets only the market's own line.** Its offers are the deciding books' quotes
at the reference line. The first search measured that the count distribution overstates the favoured
side off the line, and the projection search found that a map fitted across lines prices line-shopping
wrongly in the direction that favours the better price (record 5, its lab's main-line rule). Offers off
the reference line are not registered.

## The cells (36)

| Family | Rule | Reference | Sides | Cut on EV | Cells |
|---|---|---|---|---|---|
| OL | The off-line rule, markets pooled | Pinnacle | under, over | ≥ 0.00 / 0.01 / 0.02 / 0.03 / 0.04 / 0.05 | 12 |
| CS | The soft-consensus rule, markets pooled | the other books, Pinnacle absent | under, over | ≥ 0.00 / 0.01 / 0.02 / 0.03 / 0.04 / 0.05 | 12 |
| AN | The anchored model, markets pooled | Pinnacle; else the soft books | under, over (per reference kind) | ≥ 0.01 / 0.02 / 0.04 | 12 |
| **Total** | | | | | **36** |

- The first search's off-line result sits at the under, EV ≥ 0.02 cell. Its consensus result sits at
  the under, EV ≥ 0.00 cell. The over cells are registered because no over rule was ever judged under
  this standard.
- The anchored cuts are the sweep's. The other cuts are the first search's grid, stopping where the
  bet counts thin.

**Bands (bar 5)** run along EV within one family, reference kind and side. OL and CS: from −0.01, edges
0.00 to 0.05, top band open. AN: from 0.00, edges 0.01, 0.02, 0.04, top band open. The band just below
the cut and every band from the cut up must be positive where they hold 30 or more bets.

**Seasons.**

- OL and CS fit nothing but a count width from earlier box scores. 2023-24, 2024-25 and 2025-26 are
  graded and pooled. The choosing seasons, which the placebo reads, are 2023-24 and 2024-25.
- AN has no priced season before 2023-24, so 2023-24 is a fitting season only and is never bet.
  2024-25 and 2025-26 are graded and pooled. 2024-25 is the choosing season the placebo reads. With
  two graded seasons, "all but at most one positive" allows one to lose. That is the bar as written,
  and the season split is printed beside it.

**Settlement.** The stat in `nba_player_game_log`, as the first search settled it: points, rebounds,
assists, threes, the sums, and for the Yes/No markets the double or triple. Over when the stat is above
the line.

## The bars

Section 9.1's house standard, unchanged: 200 or more pooled bets; the pooled whole-day bootstrap 95%
interval above zero (4,000 resamples, seed 7); at least two graded seasons with 30 or more bets and all
but at most one positive; beats the blind bet on its dominant real side, pooled; the bands; the choosing
seasons' return above the 95th percentile of 200 placebo runs. A thin cell is still reported in full. For
a cell under 200 bets the answer is "too few games to tell", not "it loses" (the 9.9 reading).

**The blind bet (bar 4)** is section 6.4's: the cell's side on every proposition in the cell's own
population, no rule and no cut, at the best deciding offer under the market's fair price. For OL and CS
that fair price is the family's own reference. For AN it is the market's number with no move.

## The placebo: 200 runs, seeds 1-200

The lesson of this week: a placebo must be a null on the real data. Each run below moves a proposition's
reading to another proposition, and each proposition keeps its own offers at their real prices.

**OL and CS: the reading moves.**

- A proposition's reading is, for each side, the best EV the rule gives it there, and whether the rule
  has a bet there at all.
- In a run, each proposition takes the whole reading of another proposition on the same date in the same
  market, by one permutation per (date, market).
- Each of its offers then carries the donor's best EV on that side, less that offer's own shortfall from
  the proposition's best offer on that side. So the best-priced offer stays best, as it does in the real
  rule. If the donor's rule has no bet on a side, neither does the proposition.
- For OL this moves the DIRECTION as well as the size. A proposition whose book hung a line below
  Pinnacle's can take a donor that says under, and then it is bet under at its own lower line. That is
  the test: under the null, which side of Pinnacle a book sits on carries no information. With the
  identity permutation the run returns exactly the real bets (a test asserts it).

**Why the first search's own placebo is not reused.** It moved Pinnacle's implied mean between players
(`gap_placebo`). Measured on the real off-line offers, one run: a points mean lands 6.8 points from its
new player's on average. EV runs from −0.87 to +0.63 between the 10th and 90th percentiles, against −0.11
to +0.03 for the real rule. 70% of offers read more than 0.25 from zero, against 0.1%. The under, EV ≥ 0.02
bet count doubles, from 7,058 to 14,769. That null hands a proposition another player's scale, which
section 8.1 rejects for the same reason. It also held each offer's side fixed, so it could not test the
direction.

**AN: the move moves.** As in section 8.1. Each proposition's move goes to another proposition on the same
date, in the same market, with the same reference kind. It is added to the proposition's own offset and
re-priced. The intercept stays in every run, so a cell earning only from the over-lean fails this bar.

**Shuffles are never alone.** Off-line propositions per (date, market): median 21, and 0.04% of them are
alone. `--smoke` prints, for the real data, the share of placebo bets that differ from the real bets, by
cell. A cell where that share is low cannot pass this bar honestly, and the print says so.

**Not measurable, reported as such:** closing-line value and "still offered at the next fetch". There is
one snapshot a game.

## Controls, graded and reported, never judged

- **`control_OL_blind`:** every offer on the side the gap favours, with no EV floor, one for each side.
  The first search found these fail. An OL cell is only interesting if it beats this.
- **`control_AN_lean`:** the anchored model with its inputs removed, the intercept alone, at AN's sides
  and cuts. An AN cell is credited to the projection and its inputs only when it passes and its pooled
  return beats this control's at the same reference kind, side and cut. Otherwise it is credited to the
  over-lean the shipped rule already holds.
- **`control_same_line`:** the shipped Pinnacle rule (`nba_prop_market`), same-line unders at EV ≥ 0.00,
  the five shipped markets. It reproduces record 4.3's 24,572 bets, less the games outside 45-75 minutes.
  Its count is checked in `--smoke`. A graded result far from the record's +781.3 units means a fault in
  this lab, and the run stops being read until it is found.

**Expected passes by chance:** 36 × 0.025 = 0.9 cells clear bar 2 alone, before correlation. The cuts of one
family are nested, so most of the cells are not independent.

## Reported beside every cell, never a bar

- DraftKings alone (the harness's own columns).
- The 54-minute against the 64-minute snapshot (leads 50-60 and 60-70), because the first search's off-line
  profit came from the 64-minute snapshots only.
- Without Hard Rock, and without FanDuel, each re-chosen at the remaining best price.
- By gap size (1, 2, 3 and more) for OL.
- With offers more than 0.20 above the price's implied chance taken out.
- The blind side at the best price at Pinnacle's own line (the first search's comparison).
- **Overlap with the two shipped models:** the share of the cell's bets on a proposition the same-line
  Pinnacle rule holds, the share the projection card holds (2024-25 and 2025-26), and the bets and units
  on propositions neither holds.
- **The prices it lays:** minimum, 5th percentile, median, 95th percentile, maximum.

## What a pass means

A pass is built live (CLAUDE.md section 2), with its own EV floor and the prices it lays stated before it
ships, under the live cards' 10-minute quote-clock refusal. The archive could not see a stale quote (record
4.3), so the live record is what judges it. A passing AN cell that only re-picks what the live models hold
adds nothing, and the overlap above says so.

## Running it

    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_propoffline --smoke
    NBA_RESEARCH_CACHE=<cache> NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        PYTHONPATH=. python -m scripts.nba_s_propoffline --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5

`--smoke` runs the synthetic checks, then on the real cache prints only counts, extremes, the highest-EV
offers, the placebo's difference share, and a timed placebo run on results set to zero. It never grades a
real bet.

`--full` refuses without all three variables. It prints progress and an estimate after each group, writes
one `cells_*.parquet` per group (so a stopped run resumes), the bets, the proposition table and the beside
tables. It is built to finish in about two hours.

## Dated lines, 2026-10-31, before any cell was graded

No cell, cut, side, band, bar or season above changed. These three lines are about how the lab reports.

- **The credit test has its own file.** The verdict's `credited` column cannot read `control_AN_lean`: its credit
  map matches on market, side and cut, with no reference kind, so the Pinnacle and consensus rows would collide.
  There, `credited` equals a pass. `--full` writes `credit_AN.parquet` with each AN cell's return against the control
  at the same reference kind, side and cut. An AN cell is credited when it passes the verdict and `beats_control` is
  true.
- **Small p-values are not re-drawn.** The harness re-draws a p under 0.01 with 400,000 resamples for the first
  search's false-discovery bar, about 40 seconds each on this machine under load (timed 2026-10-31). A smoke run on
  results set to zero never shows that cost, so it would hide up to 68 minutes. Section 9.1's bars do not read that p.
  In this lab's cells `p_choose` and `p_confirm` stay at 4,000 resamples, and the harness is handed back unchanged.
- **"Low" share means under 0.5.** The placebo section says the print names a cell whose share is low. It names any
  cell where a run changes under half its bets.

## Dated line, 2026-10-31, later the same day, before any cell was graded: when a report counts as known

No cell had been graded when this changed, and no cell, cut, side, band, bar or season changed with it.

**The rule: an injury report counts as known 30 minutes after its printed time.** The record's words (section 6.1): when
each file became downloadable is unknown, so a report is treated as known 30 minutes after its printed time. The game-market
anchored model already read reports this way (`INJURY_LAG` in `scripts/nba_game2_projection.py`).

**What was wrong.** This search read a report the moment it was printed, and "as of the snapshot" above never stated a lag. It
inherited that from the shipped projection's own research path (`scripts/nba_prop_projection_train.research_inputs`, and the
default of `scripts/nba_prop_model_verify.py`). The print schedule makes it matter. In the stored report, 2023-24 and 2024-25 are
stamped only on the half hour; 2025-26 is also stamped on the hour, at :15 and at :45. So a snapshot can read a report printed
minutes earlier, and an input read just after print can sit against a price that has not moved yet. A checker found this before
any grade.

**What it reaches.**

- **AN:** the Out filter, `own_q`, `tm_o_min`, `d_o_min`, `tm_q_min`, `opp_o_min`, projected minutes, every projected mean, the
  disagreement and the widths all read the shifted report, in the rows fitted on as well as the rows priced.
- **`control_AN_lean`:** it has no inputs, so it reads the report only through who is left out. Its bets did not change (measured
  in the counts at the end).
- **The overlap column "the share the projection card holds":** this lab rebuilds that card from the same folds, so it moves too.
- **OL, CS and `control_same_line`:** these read no report. Their bets do not change.

**How.** The lab shifts `report_ts` by 30 minutes before the report is compacted, in its own wrapper (`report_as_known`), and
`models/` is untouched. The fold files are named for the lag, so a run under the 30-minute read can never load a fold fitted on
the print-time read. The print-time folds stay on disk under their old names, and nothing reads them.

**Not re-judged here:** the shipped projection's record (records 4.5 and 5) used the print-time read, with reports read 60
minutes late reported beside it. This search does not change or re-measure that record.

The counts that move are at the end of this file, under "Counts under the 30-minute read". The counts straight below were taken
on the print-time read. Their OL, CS and control rows stand. Their AN rows do not, and neither do the AN rows of the placebo and
overlap tables, the card column of the overlap table, or the time and memory line.

## Counts before grading

Counted 2026-10-31 by `python -m scripts.nba_s_propoffline --smoke` on the research cache. Lines, prices and
timestamps only. The model's fit read the seasons before the one it prices, and no bet of any cell was graded.

**The rules, row by row** (a row is one book's quote on one proposition at one line):

| Step | Rows left |
|---|---:|
| Stored rows the first search's table holds | 2,733,240 |
| A named player who took the court, with a stat line | 2,700,136 |
| In the 45-75 minute window | 2,685,992 |
| A coherent two-way quote | 2,415,494 |
| Both prices inside ±10,000, line under the ceiling | 2,415,295 |

The price limit removed 199 rows. The line ceiling removed none. The ceilings, the highest each stat reached in the
stored box scores: points 83, rebounds 31, assists 24, threes 14, points + rebounds + assists 95, points + rebounds 92, points + assists 86, rebounds + assists 45, blocks 10, steals 10, blocks + steals 12, turnovers 12.

**Games with a decision:** 1,225 in 2023-24, 1,224 in 2024-25, 1,217 in 2025-26.

**Bets each cell would place.** AN and its control have no 2023-24 bets, because that season only fits.

| Family | Reference | Side | Cut on EV | 2023-24 | 2024-25 | 2025-26 | Pooled |
|---|---|---|---|---:|---:|---:|---:|
| OL | pinnacle | under | ≥ 0.00 | 1,541 | 4,152 | 5,285 | 10,978 |
| OL | pinnacle | under | ≥ 0.01 | 1,189 | 3,404 | 4,306 | 8,899 |
| OL | pinnacle | under | ≥ 0.02 | 916 | 2,705 | 3,437 | 7,058 |
| OL | pinnacle | under | ≥ 0.03 | 678 | 2,128 | 2,653 | 5,459 |
| OL | pinnacle | under | ≥ 0.04 | 497 | 1,652 | 1,991 | 4,140 |
| OL | pinnacle | under | ≥ 0.05 | 376 | 1,260 | 1,515 | 3,151 |
| control_OL_blind | pinnacle | under | none | 6,957 | 10,122 | 13,792 | 30,871 |
| OL | pinnacle | over | ≥ 0.00 | 1,806 | 4,649 | 4,369 | 10,824 |
| OL | pinnacle | over | ≥ 0.01 | 1,351 | 3,760 | 3,407 | 8,518 |
| OL | pinnacle | over | ≥ 0.02 | 952 | 2,937 | 2,633 | 6,522 |
| OL | pinnacle | over | ≥ 0.03 | 688 | 2,179 | 1,981 | 4,848 |
| OL | pinnacle | over | ≥ 0.04 | 492 | 1,607 | 1,451 | 3,550 |
| OL | pinnacle | over | ≥ 0.05 | 331 | 1,131 | 1,076 | 2,538 |
| control_OL_blind | pinnacle | over | none | 7,559 | 12,220 | 13,661 | 33,440 |
| control_same_line | pinnacle | under | ≥ 0.00 | 8,487 | 8,306 | 7,650 | 24,443 |
| CS | consensus | under | ≥ 0.00 | 5,432 | 5,791 | 6,045 | 17,268 |
| CS | consensus | under | ≥ 0.01 | 3,370 | 3,694 | 3,992 | 11,056 |
| CS | consensus | under | ≥ 0.02 | 2,116 | 2,392 | 2,552 | 7,060 |
| CS | consensus | under | ≥ 0.03 | 1,141 | 1,478 | 1,630 | 4,249 |
| CS | consensus | under | ≥ 0.04 | 696 | 905 | 1,037 | 2,638 |
| CS | consensus | under | ≥ 0.05 | 356 | 565 | 677 | 1,598 |
| CS | consensus | over | ≥ 0.00 | 6,214 | 6,811 | 6,424 | 19,449 |
| CS | consensus | over | ≥ 0.01 | 3,936 | 4,546 | 4,279 | 12,761 |
| CS | consensus | over | ≥ 0.02 | 2,449 | 2,987 | 2,848 | 8,284 |
| CS | consensus | over | ≥ 0.03 | 1,388 | 1,886 | 1,889 | 5,163 |
| CS | consensus | over | ≥ 0.04 | 840 | 1,222 | 1,215 | 3,277 |
| CS | consensus | over | ≥ 0.05 | 478 | 769 | 822 | 2,069 |
| AN | pinnacle | under | ≥ 0.01 | – | 19,138 | 12,628 | 31,766 |
| AN | pinnacle | under | ≥ 0.02 | – | 15,904 | 9,956 | 25,860 |
| AN | pinnacle | under | ≥ 0.04 | – | 10,392 | 5,746 | 16,138 |
| control_AN_lean | pinnacle | under | ≥ 0.01 | – | 17,319 | 11,859 | 29,178 |
| control_AN_lean | pinnacle | under | ≥ 0.02 | – | 13,679 | 9,035 | 22,714 |
| control_AN_lean | pinnacle | under | ≥ 0.04 | – | 7,822 | 4,772 | 12,594 |
| AN | pinnacle | over | ≥ 0.01 | – | 3,490 | 3,262 | 6,752 |
| AN | pinnacle | over | ≥ 0.02 | – | 2,587 | 2,341 | 4,928 |
| AN | pinnacle | over | ≥ 0.04 | – | 1,384 | 1,156 | 2,540 |
| control_AN_lean | pinnacle | over | ≥ 0.01 | – | 1,553 | 1,900 | 3,453 |
| control_AN_lean | pinnacle | over | ≥ 0.02 | – | 1,032 | 1,237 | 2,269 |
| control_AN_lean | pinnacle | over | ≥ 0.04 | – | 420 | 502 | 922 |
| AN | consensus | under | ≥ 0.01 | – | 24,032 | 15,468 | 39,500 |
| AN | consensus | under | ≥ 0.02 | – | 19,619 | 12,091 | 31,710 |
| AN | consensus | under | ≥ 0.04 | – | 12,202 | 7,074 | 19,276 |
| control_AN_lean | consensus | under | ≥ 0.01 | – | 17,156 | 9,063 | 26,219 |
| control_AN_lean | consensus | under | ≥ 0.02 | – | 11,298 | 6,050 | 17,348 |
| control_AN_lean | consensus | under | ≥ 0.04 | – | 4,981 | 2,663 | 7,644 |
| AN | consensus | over | ≥ 0.01 | – | 5,844 | 4,573 | 10,417 |
| AN | consensus | over | ≥ 0.02 | – | 4,348 | 3,415 | 7,763 |
| AN | consensus | over | ≥ 0.04 | – | 2,381 | 1,838 | 4,219 |
| control_AN_lean | consensus | over | ≥ 0.01 | – | 1,483 | 2,249 | 3,732 |
| control_AN_lean | consensus | over | ≥ 0.02 | – | 928 | 1,492 | 2,420 |
| control_AN_lean | consensus | over | ≥ 0.04 | – | 380 | 663 | 1,043 |

**Against the first search's counts:** OL under at EV ≥ 0.02, 7,058 here and 7,123 in the record. CS under at EV ≥ 0.00,
17,268 here and 17,386 in the record. The shipped same-line control, 24,443 here and 24,572 in the record. The first
search had no −200 floor or 45-75 minute window on the first two. These rows differ by under 1% each.

**The extremes of every line and price read, after the rules:**

| Market | Rows | Lowest line | Highest line | Lowest over | Highest over | Lowest under | Highest under |
|---|---:|---:|---:|---:|---:|---:|---:|
| player_assists | 231,787 | 0.5 | 14.5 | -475 | +300 | -450 | +270 |
| player_blocks | 117,013 | 0.5 | 4.5 | -300 | +750 | -2,000 | +210 |
| player_blocks_steals | 66,266 | 0.5 | 5.5 | -275 | +360 | -560 | +210 |
| player_double_double | 38,210 | 0.5 | 0.5 | -5,000 | +2,200 | -10,000 | +900 |
| player_points | 347,851 | 1.5 | 44.5 | -375 | +225 | -400 | +215 |
| player_points_assists | 184,893 | 2.5 | 49.5 | -190 | +215 | -300 | +140 |
| player_points_rebounds | 225,970 | 2.5 | 50.5 | -200 | +525 | -1,000 | +150 |
| player_points_rebounds_assists | 264,059 | 3.5 | 64.5 | -315 | +215 | -305 | +190 |
| player_rebounds | 299,493 | 0.5 | 16.5 | -295 | +320 | -500 | +210 |
| player_rebounds_assists | 176,196 | 1.5 | 25.5 | -224 | +215 | -300 | +165 |
| player_steals | 122,323 | 0.5 | 3.5 | -304 | +375 | -600 | +220 |
| player_threes | 272,593 | 0.5 | 6.5 | -900 | +1,400 | -3,500 | +400 |
| player_triple_double | 2,372 | 0.5 | 0.5 | -233 | +2,000 | -10,000 | +170 |
| player_turnovers | 66,269 | 0.5 | 5.5 | -284 | +300 | -450 | +196 |

**The highest-EV offers stay in, as the rules above say.** The top of each family is a wide gap, not an impossible
number, and each lands in the beside row that takes out offers more than 0.20 above the price's implied chance.

- CS and AN over: Goga Bitadze points + rebounds over 19.5 at BetMGM, +525 on 2024-12-08. EV 2.03 against the other
  books' median of 0.485.
- OL under: Chimezie Metu points under 14.5 at BetMGM, −125 on 2023-12-13, with Pinnacle at 8.5. EV 0.63.
- OL over: Jonathan Kuminga points + rebounds + assists over 16.5 at DraftKings, −114 on 2025-11-12, with Pinnacle at
  23.5. EV 0.58.

**The placebo, on the real data.** Every group's identity permutation returned its real bets. Share of propositions alone
in their group: OL 0.04%, CS 0.08%, AN Pinnacle 0.00%, AN consensus 0.03%. Averaged over three runs:

| Family | Reference | Side | Cut on EV | Real bets | Bets in a run | Share of a run's bets not among the real ones |
|---|---|---|---|---:|---:|---:|
| OL | pinnacle | under | ≥ 0.00 | 10,978 | 10,456 | 0.77 |
| OL | pinnacle | under | ≥ 0.01 | 8,899 | 8,491 | 0.80 |
| OL | pinnacle | under | ≥ 0.02 | 7,058 | 6,738 | 0.84 |
| OL | pinnacle | under | ≥ 0.03 | 5,459 | 5,219 | 0.86 |
| OL | pinnacle | under | ≥ 0.04 | 4,140 | 3,961 | 0.89 |
| OL | pinnacle | under | ≥ 0.05 | 3,151 | 3,031 | 0.90 |
| OL | pinnacle | over | ≥ 0.00 | 10,824 | 10,339 | 0.78 |
| OL | pinnacle | over | ≥ 0.01 | 8,518 | 8,145 | 0.82 |
| OL | pinnacle | over | ≥ 0.02 | 6,522 | 6,258 | 0.85 |
| OL | pinnacle | over | ≥ 0.03 | 4,848 | 4,660 | 0.88 |
| OL | pinnacle | over | ≥ 0.04 | 3,550 | 3,410 | 0.91 |
| OL | pinnacle | over | ≥ 0.05 | 2,538 | 2,442 | 0.93 |
| CS | consensus | under | ≥ 0.00 | 17,268 | 16,873 | 0.82 |
| CS | consensus | under | ≥ 0.01 | 11,056 | 10,782 | 0.86 |
| CS | consensus | under | ≥ 0.02 | 7,060 | 6,882 | 0.89 |
| CS | consensus | under | ≥ 0.03 | 4,249 | 4,127 | 0.91 |
| CS | consensus | under | ≥ 0.04 | 2,638 | 2,561 | 0.93 |
| CS | consensus | under | ≥ 0.05 | 1,598 | 1,553 | 0.93 |
| CS | consensus | over | ≥ 0.00 | 19,449 | 19,252 | 0.80 |
| CS | consensus | over | ≥ 0.01 | 12,761 | 12,623 | 0.85 |
| CS | consensus | over | ≥ 0.02 | 8,284 | 8,191 | 0.88 |
| CS | consensus | over | ≥ 0.03 | 5,163 | 5,103 | 0.90 |
| CS | consensus | over | ≥ 0.04 | 3,277 | 3,237 | 0.92 |
| CS | consensus | over | ≥ 0.05 | 2,069 | 2,045 | 0.93 |
| AN | pinnacle | under | ≥ 0.01 | 31,766 | 31,591 | 0.37 |
| AN | pinnacle | under | ≥ 0.02 | 25,860 | 26,015 | 0.41 |
| AN | pinnacle | under | ≥ 0.04 | 16,138 | 16,800 | 0.50 |
| AN | pinnacle | over | ≥ 0.01 | 6,752 | 7,465 | 0.61 |
| AN | pinnacle | over | ≥ 0.02 | 4,928 | 5,560 | 0.65 |
| AN | pinnacle | over | ≥ 0.04 | 2,540 | 2,953 | 0.71 |
| AN | consensus | under | ≥ 0.01 | 39,500 | 39,333 | 0.51 |
| AN | consensus | under | ≥ 0.02 | 31,710 | 31,677 | 0.55 |
| AN | consensus | under | ≥ 0.04 | 19,276 | 19,698 | 0.64 |
| AN | consensus | over | ≥ 0.01 | 10,417 | 11,180 | 0.69 |
| AN | consensus | over | ≥ 0.02 | 7,763 | 8,399 | 0.72 |
| AN | consensus | over | ≥ 0.04 | 4,219 | 4,619 | 0.77 |

Three cells are low: AN Pinnacle under at all three cuts. The intercept stays in every run on purpose, so that a cell
earning only from the over-lean fails this bar. With no inputs at all, that intercept places 29,178 bets at EV ≥ 0.01 against
the model's 31,766, and the median move is −0.059 log-odds. That fits most of these bets not depending on which move a
proposition reads, though no count here isolates it. In these cells only the bets a run changes can separate the real return
from the placebo's.

Can the bar still say yes? On invented data, 40 runs at each group's lowest cut: with a planted edge, every AN group's real
rule beat its 95th percentile at 0.83 or more of six seeds, and with no edge at none of them, in every family. The invented
world holds no consensus edge, so the CS placebo's power is shown by a hand-built one (`test_a_consensus_edge_beats_its_placebo`).
On a planted off-line edge, cells pass every one of the verdict's six bars (`test_a_planted_edge_can_pass_every_bar_of_the_verdict`).

**Overlap with the two shipped models** (counts only; 0.000 for CS is by construction, since the same-line rule needs Pinnacle):

| Family, lowest cut | Bets | Share on a proposition the same-line rule holds | Share the projection card holds |
|---|---:|---:|---:|
| OL_pinnacle_under | 10,978 | 0.260 | 0.032 |
| OL_pinnacle_over | 10,824 | 0.052 | 0.066 |
| CS_consensus_under | 17,268 | 0.000 | 0.252 |
| CS_consensus_over | 19,449 | 0.000 | 0.215 |
| AN_pinnacle_under | 31,766 | 0.406 | 0.164 |
| AN_pinnacle_over | 6,752 | 0.058 | 0.195 |
| AN_consensus_under | 39,500 | 0.000 | 0.418 |
| AN_consensus_over | 10,417 | 0.000 | 0.169 |

**Time and memory.** One placebo run across all of a group's cuts took 0.5 to 6.2 seconds by group (the median of three runs, on results set to zero). The projected `--full` is 93 minutes of cells plus 3 minutes of loading, measured on this machine under its shared load that morning; two earlier smoke runs that day projected 78 and 105. Peak memory was 4.0 GB, and `--full` adds at most 0.2 GB for one group's 200 placebo runs. The first run on a fresh folder also refits the projection, 11 to 20 minutes a fold on one thread (that refit's logs, 2026-10-31), then caches it.

## Counts under the 30-minute read

Counted 2026-10-31 by `python -m scripts.nba_s_propoffline --smoke`, after the four folds were refitted on the new read. No cell had
been graded and none was. Lines, prices, timestamps and who took the court only; the model's fit read the seasons before the one it
prices. The comparisons with the print-time read come from three one-off scripts in the search's scratch folder (`lagcount.py`,
`lagdiff.py`, `lagplayed.py`), which build on both sets of folds and read no result.

**What did not move.** Between the two smoke runs, 39 of the 51 rows of the bets table above are identical: every OL, CS,
`control_OL_blind`, `control_same_line` and `control_AN_lean` row. Only the 12 AN rows differ. The rule counts, the ceilings and the
extremes are identical too.

**Why the control did not move.** The anchored table holds the same number of rows under both reads, in every season and reference
kind: 91,921 / 73,542 / 54,630 consensus and 44,472 / 47,437 / 40,993 Pinnacle, for 2023-24 / 2024-25 / 2025-26. In those three seasons
908 fold rows are Out at print and not Out 30 minutes later, and none of those players took the court, so the void rule had already
removed them. What moves AN is what it reads about teammates and opponents, and the projection built on that.

**The bets each AN cell would place.**

| Family | Reference | Side | Cut on EV | 2024-25 | 2025-26 | Pooled | Pooled on the print-time read | Share of these bets the print-time read did not place |
|---|---|---|---|---:|---:|---:|---:|---:|
| AN | pinnacle | under | ≥ 0.01 | 19,245 | 12,522 | 31,767 | 31,766 | 0.070 |
| AN | pinnacle | under | ≥ 0.02 | 15,978 | 9,881 | 25,859 | 25,860 | 0.082 |
| AN | pinnacle | under | ≥ 0.04 | 10,326 | 5,758 | 16,084 | 16,138 | 0.103 |
| AN | pinnacle | over | ≥ 0.01 | 3,466 | 3,313 | 6,779 | 6,752 | 0.131 |
| AN | pinnacle | over | ≥ 0.02 | 2,600 | 2,371 | 4,971 | 4,928 | 0.144 |
| AN | pinnacle | over | ≥ 0.04 | 1,423 | 1,205 | 2,628 | 2,540 | 0.185 |
| AN | consensus | under | ≥ 0.01 | 24,270 | 15,453 | 39,723 | 39,500 | 0.087 |
| AN | consensus | under | ≥ 0.02 | 19,731 | 12,096 | 31,827 | 31,710 | 0.099 |
| AN | consensus | under | ≥ 0.04 | 12,236 | 7,061 | 19,297 | 19,276 | 0.119 |
| AN | consensus | over | ≥ 0.01 | 5,884 | 4,656 | 10,540 | 10,417 | 0.140 |
| AN | consensus | over | ≥ 0.02 | 4,342 | 3,373 | 7,715 | 7,763 | 0.146 |
| AN | consensus | over | ≥ 0.04 | 2,409 | 1,813 | 4,222 | 4,219 | 0.154 |
| control_AN_lean | pinnacle | under | ≥ 0.01 | 17,319 | 11,859 | 29,178 | 29,178 | 0.000 |
| control_AN_lean | pinnacle | under | ≥ 0.02 | 13,679 | 9,035 | 22,714 | 22,714 | 0.000 |
| control_AN_lean | pinnacle | under | ≥ 0.04 | 7,822 | 4,772 | 12,594 | 12,594 | 0.000 |
| control_AN_lean | pinnacle | over | ≥ 0.01 | 1,553 | 1,900 | 3,453 | 3,453 | 0.000 |
| control_AN_lean | pinnacle | over | ≥ 0.02 | 1,032 | 1,237 | 2,269 | 2,269 | 0.000 |
| control_AN_lean | pinnacle | over | ≥ 0.04 | 420 | 502 | 922 | 922 | 0.000 |
| control_AN_lean | consensus | under | ≥ 0.01 | 17,156 | 9,063 | 26,219 | 26,219 | 0.000 |
| control_AN_lean | consensus | under | ≥ 0.02 | 11,298 | 6,050 | 17,348 | 17,348 | 0.000 |
| control_AN_lean | consensus | under | ≥ 0.04 | 4,981 | 2,663 | 7,644 | 7,644 | 0.000 |
| control_AN_lean | consensus | over | ≥ 0.01 | 1,483 | 2,249 | 3,732 | 3,732 | 0.000 |
| control_AN_lean | consensus | over | ≥ 0.02 | 928 | 1,492 | 2,420 | 2,420 | 0.000 |
| control_AN_lean | consensus | over | ≥ 0.04 | 380 | 663 | 1,043 | 1,043 | 0.000 |

**What the read changes in the report**, on the games with a snapshot in the window (one more in 2025-26 than the 1,217 with an
eligible row). Across the three seasons, 1,171 of 7,271 (game, team) lists differ.

| | 2023-24 | 2024-25 | 2025-26 |
|---|---:|---:|---:|
| Games | 1,225 | 1,224 | 1,218 |
| Games where a team's Out or Questionable list differs | 236 | 258 | 447 |
| Games with any report at the decision, either read | 1,224 | 1,224 | 1,218 |
| Share of (game, team) reading a report under 30 minutes old, print time | 0.354 | 0.324 | 0.707 |
| The same, 30-minute read | 0.000 | 0.000 | 0.000 |
| Youngest report read, minutes before the decision, 30-minute read | 30.6 | 35.6 | 35.6 |
| Out listed per game, print time / 30-minute read | 7.69 / 7.50 | 8.60 / 8.36 | 8.80 / 8.39 |
| Questionable listed per game (with Doubtful and Probable), print time / 30-minute read | 1.68 / 2.10 | 1.69 / 2.20 | 0.96 / 1.80 |
| Fold rows whose status differs, one row per (game, player) | 515 of 38,994 | 617 of 39,339 | 1,029 of 39,599 |
| Mean `own_q`, print time / 30-minute read | 0.047 / 0.059 | 0.050 / 0.065 | 0.028 / 0.053 |
| Mean `tm_o_min`, print time / 30-minute read | 19.7 / 18.1 | 23.7 / 22.1 | 25.8 / 23.2 |
| Mean `tm_q_min`, print time / 30-minute read | 13.7 / 17.1 | 13.7 / 17.8 | 7.2 / 13.3 |
| Mean `opp_o_min`, print time / 30-minute read | 20.8 / 19.2 | 24.9 / 23.2 | 27.4 / 24.7 |

The gap between the seasons fitted on and the season priced narrows and does not close: mean `tm_q_min` for 2024-25 against 2025-26
was 13.7 against 7.2 and is 17.8 against 13.3. The season split beside the verdict is where that would show.

**The fold's means.** Row by row and season by season, projected minutes moved 0.6 minutes on average and projected points 0.33 to 0.40.
How much of that is the report and how much is a refit's churn was not separated. The move off the market, log-odds, percentiles 1 / 50
/ 99: −0.315, −0.059, +0.179, against −0.318, −0.059, +0.177. 33 of 36 fits have a model, as before. 32 of them chose the penalty 0.003, as
before. The other, blocks + steals against the consensus for 2025-26, chose 0.30 where it chose 0.03; that model prices 6 rows.

**Looked at, not only tested.** Status in the new folds was rebuilt from the raw report with no lab or model code. Over the 117,958 rows of
the three seasons, 0 differ from that rebuild at 30 minutes, and 2,178 differ from the same rebuild at print time. The time a report is
read against is the priced snapshot in all 3,667 games (0 minutes apart at the first and last snapshot of each).

**The highest-EV anchored offers**, on the same rule as above (a wide gap stays in, and lands in the beside row):

- AN consensus over: Goga Bitadze points + rebounds over 19.5 at BetMGM, +525 on 2024-12-08. EV 1.93.
- AN consensus under: Yanic Konan Niederhauser rebounds under 4.5 at BetParx, +123 on 2026-02-08. EV 0.48.
- AN Pinnacle under: Neemias Queta rebounds under 6.5 at FanDuel, +120 on 2025-10-22. EV 0.36.
- AN Pinnacle over: Anfernee Simons assists over 3.5 at Hard Rock, +180 on 2025-10-29. EV 0.29.

**The placebo, AN rows.** OL and CS are unchanged from the table above. Every group's identity permutation returned its real bets. Share of
propositions alone in their group: AN Pinnacle 0.00%, AN consensus 0.03%. Averaged over three runs:

| Reference | Side | Cut on EV | Real bets | Bets in a run | Share of a run's bets not among the real ones |
|---|---|---|---:|---:|---:|
| pinnacle | under | ≥ 0.01 | 31,767 | 31,636 | 0.37 |
| pinnacle | under | ≥ 0.02 | 25,859 | 26,021 | 0.41 |
| pinnacle | under | ≥ 0.04 | 16,084 | 16,670 | 0.49 |
| pinnacle | over | ≥ 0.01 | 6,779 | 7,499 | 0.62 |
| pinnacle | over | ≥ 0.02 | 4,971 | 5,622 | 0.65 |
| pinnacle | over | ≥ 0.04 | 2,628 | 3,011 | 0.71 |
| consensus | under | ≥ 0.01 | 39,723 | 39,523 | 0.51 |
| consensus | under | ≥ 0.02 | 31,827 | 31,844 | 0.55 |
| consensus | under | ≥ 0.04 | 19,297 | 19,830 | 0.63 |
| consensus | over | ≥ 0.01 | 10,540 | 11,312 | 0.69 |
| consensus | over | ≥ 0.02 | 7,715 | 8,433 | 0.72 |
| consensus | over | ≥ 0.04 | 4,222 | 4,654 | 0.76 |

The same three cells are low: AN Pinnacle under at all three cuts, 0.37, 0.41 and 0.49. The paragraph under the print-time table still says
why, with its control count unchanged (29,178 bets at EV ≥ 0.01) and this table's 31,767 for the model's.

**Overlap with the two shipped models** (counts only). The card column moves because this lab rebuilds the card from the same folds. The
shipped card's record was measured on the print-time read, so this column now compares against the card as it would have read the report
30 minutes after print.

| Family, lowest cut | Bets | Share on a proposition the same-line rule holds | Share the projection card holds |
|---|---:|---:|---:|
| OL_pinnacle_under | 10,978 | 0.260 | 0.033 |
| OL_pinnacle_over | 10,824 | 0.052 | 0.066 |
| CS_consensus_under | 17,268 | 0.000 | 0.255 |
| CS_consensus_over | 19,449 | 0.000 | 0.216 |
| AN_pinnacle_under | 31,767 | 0.406 | 0.163 |
| AN_pinnacle_over | 6,779 | 0.058 | 0.198 |
| AN_consensus_under | 39,723 | 0.000 | 0.423 |
| AN_consensus_over | 10,540 | 0.000 | 0.171 |

**Time and memory.** The four folds took 395 to 574 seconds each, as four processes side by side on one thread each, about 4 minutes of that
building the frame (the refit's logs, 2026-10-31). They are cached, so `--full` does not refit. One placebo run across all of a group's cuts
took 0.3 to 1.0 seconds by group. The projected `--full` is 26 minutes of cells plus 1 minute of loading, peak memory 4.1 GB, and at most
0.3 GB more for one group's 200 placebo runs. The smoke run itself took 11 minutes. Smoke runs on this machine that day have now projected
26, 78, 93 and 105 minutes, all inside the two hours, so the range is the figure to plan on.


## Results (graded 2026-10-31)

Run `2026-10-31-propoffline`, stored in Supabase. 36 cells and 15 controls.

**8 of the 36 cells pass the house standard, all unders. An independent check then found none of them is a new model
to build.**

| Cell | Bets | Units | Return | 95% interval | House standard |
|---|---|---|---|---|---|
| Soft-book consensus, same line, under, EV 0.00 | 17,268 | +315.07 | +1.8% | +0.2% to +3.5% | passes |
| same, EV 0.01 | 11,056 | +274.60 | +2.6% | +0.7% to +4.5% | passes |
| same, EV 0.02 | 7,060 | +151.52 | +2.3% | 0.0% to +4.6% | passes |
| same, EV 0.03 | 4,249 | +142.61 | +3.6% | +0.5% to +6.8% | passes |
| Anchored projection, consensus, under, EV 0.01 | 39,723 | +656.14 | +1.5% | +0.4% to +2.6% | passes |
| same, EV 0.02 | 31,827 | +614.33 | +1.8% | +0.6% to +3.0% | passes |
| same, EV 0.04 | 19,297 | +548.59 | +2.7% | +1.2% to +4.3% | passes |
| Anchored projection, Pinnacle, under, EV 0.04 | 16,084 | +578.11 | +3.3% | +1.6% to +5.0% | passes |
| Anchored projection, Pinnacle, under, EV 0.01 | 31,767 | +549.63 | +1.6% | +0.2% to +3.0% | fails bands |
| same, EV 0.02 | 25,859 | +596.88 | +2.1% | +0.6% to +3.6% | fails bands |
| Off Pinnacle's line, under, EV 0.04 | 4,140 | +162.07 | +3.2% | +0.3% to +6.2% | fails bands |
| same, EV 0.05 | 3,151 | +180.99 | +4.7% | +1.5% to +8.1% | fails bands |

### The independent check, 2026-11-02

A separate checker rebuilt three cells in plain code from the raw quotes and box scores, with neither this lab's
chooser nor its grader. Scripts are under `%TEMP%/nba_s/verify_propoffline/`. Each returned 0 differences on player,
market, line, side, price, book and result, and nothing reads information from after the decision apart from the one
input below. **The arithmetic is right. The conclusions a pass would suggest are not.**

| | Consensus, same line, EV 0.01 | Anchored, Pinnacle, EV 0.04 | Off Pinnacle's line, EV 0.05 |
|---|---|---|---|
| Verdict | **Does not hold** | **Holds as a record, is not a new model** | **Does not hold under its standard; a lead** |
| Bets the live rule already makes | 0 | 9,142 (56.8%) | 1,083 (34.4%), at another line |
| Held by neither live model | 7,892, +69.8 units, +0.91% (-1.46% to +3.21%) | 4,281, +52.9 units, +1.13% (-2.19% to +4.43%) | 1,977, +86.9 units, +3.72% (-0.60% to +7.88%) |
| On the five books the feed returns | 891, -54.1 units, -5.99% (-13.17% to +1.01%) | 10,285, +229.2 units, +2.08% (+0.06% to +4.05%) | 2,737, +171.5 units, +5.15% (+1.39% to +8.68%) |
| One bet a game, four a night | 1,829, +105.0 units, +6.44% | 1,248, +26.8 units, +2.17% | 1,266, +107.6 units, +7.14% |

The live rule under the same one-a-game, four-a-night cap makes 1,861 bets, +120.1 units, +6.58%, so no cell improves
on what is already live by more than its own noise.

- **The consensus cell cannot be built on what the live feed returns.** Its median needs books the feed does not
  serve, and it rests on one book being about 14 cents out of line (85% of its bets have only one book clearing).
  Without December 2025 it is +1.94% (-0.04% to +3.94%). Stale quotes, its largest risk, cannot be measured: the
  archive holds no book clocks.
- **The anchored cell mostly is the live rule.** It does not beat its own control once an interval is added: +0.90
  points (-0.66 to +2.41). Its part that is not already live is threes, 1,577 bets, +8.83%, and without threes
  +0.61%. That split was looked for after seeing the result, so it is a question for a new test and not a finding.
- **The off-line cell's bands really do fail.** The two bands below its cut lose (-1.53% on 989 bets, and -1.00%), with
  no plateau. It is the only one of the three that survives both the five-book and the overlap limits, and it does
  so on seasons already known to be good for it before this search was written. It stays closed under this standard.
  2026-27 is the fresh test.
- **None of these seasons is a fresh test for this search:** the off-line and consensus ideas were already known to
  have made money on them.

**Every under rule leans on one situation.** In team-games where a teammate came back from no pre-game roster, the
blind under returns +5.71%, against -2.60% elsewhere. The live rule is +14.60% there and +1.13% elsewhere (-0.50% to
+2.77%). This is a hindsight split and not a rule, but it says where the unders' money comes from.

**Faults the check found, each measured separately on 2026-11-02:** the returning-teammates input reads tonight's box,
and a book's last-listed line can overwrite its main number. The first does not reach a live bet; what it does to the
shipped projection model's record is in `docs/nba_models_2026.md` section 5. The second reaches no bet now: of the
books that can be bet, none lists more than one line a player, and Bovada, which lists seven, cannot be bet
(`docs/followups.md`). Two smaller ones stand here: 15 files of invented bets from the lab's own
synthetic check sit in the bets folder (`scripts/nba_s_propoffline.py:1245`), though the verdict never reads them, and
the verdict's `credited` column reads as credit for the anchored consensus cell at EV 0.04 while it loses to its
control. `credit_AN.parquet` is the column to read.

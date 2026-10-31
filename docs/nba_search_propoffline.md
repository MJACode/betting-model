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
- **Inputs, as of the snapshot:**
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
- **Who is left out:** a player listed Out at the decision, and a player with fewer than 10 career
  games, have no model number (the projection's own rule, record 5).

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

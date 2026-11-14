# The kill tests

Step 6 of `SKILL.md`. Every one of these killed a result in this repo that
looked like an edge, and most of those results had already passed the tests
their authors thought of. Run them on everything that looks positive, and
write the result of each into the study doc, passed or not.

**A test written from the same understanding that produced the model inherits
its blind spot.** These are a battery because each one sees a different way to
be wrong. Fix the decision time, the books and the cut grid **before** looking
at results, and write them down, so they cannot move afterwards.

## The repo's own bar for a cut

From `docs/paused_model_assessment.md`, used on every losing or paused model,
and the floor for a new one:

1. **The whole graded universe**: BET, AVOID and dead-zone NONE alike. A
   BET-only sample contains only picks that already cleared the bar.
2. **25+ settled picks in the cell.** Below that a return is a number, not a
   result.
3. **A plateau, not a peak**: at least 4 of the 8 neighbouring cells positive.
4. **The time split**: positive in both halves of the model's own era.
5. **The era**: a record that spans a retrain describes a blend of the live
   model and dead ones. Re-grade on the artifact that is live
   (`model_registry` where `is_active`).

A confidence interval is printed beside every cell. At small samples nothing
clears one, so it is not a gate, but it stops a headline being read as a
forecast.

## The stricter bar a new search has used

The searches that produced the strongest live models held themselves to more
(`docs/nba_models_2026.md` §1 and §6.7, `docs/nhl_derivative_totals.md`,
"What was graded"):

- pooled walk-forward of **200+ bets**, the interval above zero;
- **2+ seasons of 30+ bets each, all positive**, and both halves positive;
- beats the blind bet on the same side;
- a neighbourhood: a cut counts only if the cuts either side of it clear too;
- a placebo (200 shuffles where it can be shuffled);
- bands, not nested cuts, when reading whether return rises with edge;
- every positive claim checked by a second, independent run.

**Say which bar a model cleared.** mike can and does ship a model that misses
the bar ("build it anyway"); then it ships live, and the reply and the doc say
plainly that it did not pass and by how much. Never present a model that
missed as one that passed, and never use the gap as a reason to hold it back.

**State what the sample can resolve** before reading it: about 2,700 games
resolves a return to roughly ±4 points. A result smaller than that is not a
finding either way.

## Timing and realism

- **The backtest runs what the live path would run.** The same code, the same
  decision time, the same books, the same price. A backtest that shopped
  exchanges, or a book a pick may not name, inflated a live model's return.
  Where possible, replay the live loop's own code over the stored snapshots
  (the halftime-total model was checked this way before it shipped).
- **Grade at the quoted price**, never at -110. Props in particular are
  priced well past -110.
- **An archive's "opening line" is not a book we can bet.** An archive's
  open is the first book to post, often offshore and weeks ahead. Grade the
  same frozen model at each decidable book's own first price, with
  closing-line value against the sharp close. A UFC moneyline model read
  +7.8% on 1,531 archive opens and negative closing-line value at
  DraftKings' first price on 104 bets of our own 2026 store; bought history
  at the deciding books then read +12.85% on 846 (§3c, §3d). A small forward
  sample is not the answer either way: buy the history.
- **Quotes from one moment.** A rule comparing two books needs both quotes
  from the same snapshot. Comparing quotes from different moments manufactured
  edges three times: a best-price-against-the-sharp-book grid, a sharp-against-
  soft totals rule (about +11%, and no bets at all once the quotes had to be
  within 300 seconds of each other), and a public-fade rule whose +25% came
  from a first-quote source the live card never used.
- **Freeze, then read unseen seasons.** Once a candidate is chosen, freeze it
  and grade it unchanged on seasons it never saw (buy them if needed). One
  logistic model's +8.0% became +3.0% on 1,268 unseen bets.
- **Grade the artifact that will run**, not the research model, and check the
  production module reproduces the research grade bet for bet before
  registering it.
- **Fresh quotes only, in play.** A quote the book has not re-hung since the
  last score prices that score twice. An all-quotes table read +1.8% where
  the fresh-only table read -3.4% on the same model and season.
- **The score feed's lag.** Measure our score log against the book's (one
  college feed trailed DraftKings by a median 75 seconds). Grading that waits
  for a confirmed score peeks ahead.
- **Decided before the start.** Bound every market comparison on
  `created_at <= commence_time` and every feature snapshot on
  `snapshot_at <= commence_time`, with in-play rows excluded.
- **Can the live path actually meet the rule's condition?** A spread opener
  rule needed two books' openers captured within 90 minutes of each other; on
  the live feed that held on almost no game, so a rule with a strong backtest
  made one bet in a season. Count how often the condition is met on the live
  feed before calling it shippable.

## Is it the model, or the selection?

- **Placebo.** Re-run the whole selection with the piece that supposedly
  carries the edge replaced by one that should not. If the placebo reproduces
  the result, the result is a selection artifact. Forms used here:
  - swap the sharp reference book for a retail one (a retail placebo beating
    the sharp reference killed two prop attempts);
  - give each game a donor game's model-minus-market opinion;
  - shuffle the accrued in-play state;
  - a naive rolling average in place of the projection;
  - bet the other book's open or close.
- **The information test** (`docs/nfl_prop_information_test.md`). Fit
  `logit P = a + c·logit(book fair) + b·z` on one season and read it on the
  next, where `z` is the model's own opinion. `b` must exclude zero out of
  sample in both pairs, and the blended Brier must beat the book's. A stat
  model that fails it holds nothing the line lacks, whatever its accuracy.
- **A constant probability.** Count the distinct probabilities a model
  outputs at the decision point. A constant turns the EV cut into a pure price
  filter, and because books' prices are calibrated, the cheapest side is then
  the least likely: one such rule lost 8.47% over 3,794 bets and got worse as
  the cut tightened.
- **Shuffled probabilities.** Re-run the grade 50+ times with the model's
  probabilities shuffled across games. The real result must sit outside the
  shuffled spread.
- **Market alone as the control row.** In any ablation by input group, the
  first row is the market's own number with no model. A group that does not
  beat it adds nothing.
- **The hindsight ceiling.** For a rule that trades line movement, ask what a
  perfect predictor of the movement would have earned at real prices. If that
  ceiling is below what the existing models make, the rule cannot be worth
  building.
- **Does return rise with the claimed edge?** A real edge pays more in the
  bigger bands. Where the biggest claimed edges are the worst bets, the model
  is miscalibrated in its tail (a one-sided ladder whose vig correction was a
  constant shift did exactly this).

## Is it one bet repeated?

- **The side split.** Count each side: home and away, favourite and dog, over
  and under. More than about 70% one way is one bet repeated. A spread rule's
  +29.4 units was 337 road teams out of 338 bets, from a small home/away tilt
  in a fitted table. Then run the controls: every bet on that side at the
  consensus, and the rule's own sides re-bet at the consensus price.
- **The price band.** Where in the price range does the profit sit? A
  moneyline rule whose profit came from laying -400 to -2000 was not one mike
  will bet (`-200 max` for that model). Grade with the excluded prices removed
  **before** the best quote is picked, not after.
- **The best dates.** The result without its ten best dates. One moneyline
  rule went from positive to -9.3 units.
- **The other reads.** If the rule is decided at one pull time, read it at
  every other stored pull. Positive at one read only is not a rule.
- **Multiplicity.** When many cells or rules are tried, count them and apply
  Benjamini-Hochberg. 0 of 297 situational cells survived it in one search.

## Is it stable?

- **Walk-forward by season**, fitted only on earlier seasons, each season
  reported. An edge that is 70% one season is one season.
- **The early/late split** inside each season. Every situational edge in one
  search that looked strong pooled collapsed when split; a 61% cell was 70%
  early and 34% late.
- **Seed stability.** Refit under several random seeds. One totals fit moved a
  game's prediction by 1.49 points with the seed, and its walk-forward ran from
  -9.0 to +39.4 units by seed. Ship the seed average if the fit is noisy.
- **Fit on every season available.** A pricing table fitted on two seasons read
  +6.7%; refitted back to 2015 the same rule read -5.6%. Read a walk-forward
  return only from a table fitted on everything the data allows.
- **Era.** On live records, the artifact that is live (above).

## Is the data right?

- **The target counts what the book grades.** Compare our over rate on each
  prop market with the book's implied over rate. A gap of -7.7 points on one
  market (the others were within about 2) was a stat that counted fewer tackles
  than the books grade, and the backtest on it was +22% and fake, because it
  graded against our own undercount.
- **Check the no-vig split before trusting closing value.** Splitting a
  two-way margin in proportion assumes the book loads both sides alike. On
  UFC round totals it loads the under: at the 2.5 line the over won 60.4%
  against a no-vig 57.9% (1,594 fights), and knowing Pinnacle's close in
  advance still lost 2.8% at DraftKings. Closing value against that close
  charges the cheap side about 2.5 points. Compare each side's blind return
  first; if one is near zero and the other carries the whole margin, say so
  beside every CLV number (`docs/ufc_market_audit.md` §4b, §4f).
- **A last recorded price is not a price at a time.** An odds-comparison
  page (BestFightOdds) shows each book's last change. A book that stopped
  moving days early shows an old price, and against a consensus that moved,
  an old price looks like value that was never on offer. Before grading a
  rule at such a price, take the bets it picks and look each up in the
  site's price history at the decision time; report the share whose price
  then equals the last recorded one, by book (`docs/ufc_market_audit.md`
  §5f).
- **Validate the grading before moving a cut.** Recompute outcomes from raw
  scores and reconcile with stored settlements. A sign error in away-side
  spread grading once turned -20.6% into +15%. `scored_line` is the home
  number.
- **Leak signatures**: a win rate above about 55% on a side or total market,
  CLV below 0.5 alongside it, a season that carries everything, a feature with
  implausible importance. Check `count(DISTINCT as_of_date)` per season on
  every stats table, and that no per-entity-season value is constant.
- **Stress the missing inputs.** Score with each input missing and see what the
  model does: a missing weather row priced picks at 0°F, and one totals fit
  moved -11.66 points with no forecast, so the model now refuses to decide.

## What a pass looks like in the doc

One table per surviving rule: bets, record, units, return with interval, CLV,
each season, early/late, side split, price range, and the neighbourhood of
cuts around the chosen one. Then a line per kill test with its result. A rule
that fails a test is written up the same way, and its row in the grid says
which test killed it.

# The stat-based NFL prop models: what has been tried, what the outside world does, and the one method left worth testing

*2026-09-11, at mike's instruction: "Continue to reach the stat model and make
it profitable. Search the catacombs of the internet for the right approach.
What about running simulations. Find a method."*

This is a method, not a result. Nothing below is measured as profitable until
the experiment in §4 is run; the repo's rule (CLAUDE.md §00) is that a number
nobody has measured is not sayable, and the record on these eleven models is
that every confident claim so far has failed out of sample.

---

## 1. What is already on the record, so it is not repeated

Two groups of models share the word "prop" and should not be confused:

| group | what it does | record | status |
|---|---|---|---|
| `nfl_prop_market` (one model, eight markets) | de-vigs Pinnacle (and betonlineag), bets a soft book that disagrees at the same line | 2023-25 corrected 2026-09-11: **1,990 bets, +7.84%, 90% CI (+4.3, +11.4), positive all three seasons**; retail placebo negative | live |
| the eleven `nfl_prop_*` stat models | project a player's stat line from nflverse box scores and compare to DraftKings | walk-forward vs DK's own price, `docs/nfl_props_model.md` §5b: **11 of 11 lose** (best rush_attempts −0.10%, worst anytime_td −14.93%); at live cuts 2023-25: 2,133 bets, −1.90% | live, cuts tightened 2026-09-07 to reduce exposure |

The eleven have been attacked from six directions, each written up and each
closed (`docs/nfl_prop_profitability_search.md`, `docs/nfl_prop_information_test.md`):

1. **The information test** — logit P(over) on the book's fair probability plus
   the model's z-score, fit one season and read the next: the book beats the
   raw model on Brier on all eleven markets, and the model's coefficient never
   clears zero out of sample (five of eleven flip sign). Conclusion, verbatim:
   *"The projections carry no information the DraftKings line does not already
   hold, out of sample, on any of the eleven markets."*
2. **Injury signal** — no market positive in more than one season.
3. **Next Gen Stats features** — first pass +12 to +45% everywhere, which was a
   subset leak; the as-of join grades −5% to −15%.
4. **DraftKings alternate-line ladder** (574,525 rows, 21,153 props held) —
   one-bet-per-proposition pass_yards +16.7% in 2024 and −1.4% in 2025: a 2024
   DK error, not an edge.
5. **Gradient boosting on market features** — 0-1 trees on 8 of 10 markets.
6. **Predicting DK's own line move** — receptions correlation +0.66 but the mean
   move is +0.12 of a line, under the vig.

Two findings from that work are not closed and matter for §3:

- **The models bet ~87% unders** (pass_yards 19 over / 126 under, tackles 9 /
  784), and ten of eleven have a mean P(over) BELOW the realised over rate. A
  model that is 87% one-sided is making one bet repeatedly. Unaudited.
- **The DraftKings main line is flat** (−115/−115 on 5,218 rows; pass_yards
  77% / 72% / 30% flat in 2023 / 24 / 25). At the main line there is no price
  information to trade against; whatever information exists sits in the
  alternates and in the cross-book spread.

And one model that was "not beatable" turned out to be a grading bug: tackles,
once graded on the stat the book actually sells (solo + assisted), reads
**+15.60% over 340 bets, 90% CI (+6.4, +24.8), positive all three seasons,
placebo +0.59%** (`nfl_prop_profitability_search.md` §4). Unpaused 2026-09-09
(#624). It is the only one of the twelve with a clean record, and its edge is a
definitional one — the book's tackle line was built on a different stat than
it settles on — not a projection one.

## 2. What the outside world actually does (and the quality of the evidence)

Searched 2026-09-11. Almost everything returned is marketing. What survives:

| source | what they do | evidence grade | relevance |
|---|---|---|---|
| Rufus Peabody (Massey-Peabody; "basically just does props") | hierarchical: game-level pass attempts by script → routes and target share → a **distribution** for the stat → **compare to the median, not the mean** | B (self-described, reputation attached) | the mean/median trap is real; our models show the OPPOSITE bias, which is a defect to audit, not an edge |
| Unabated, "Profitable prop betting in 3 easy steps" | (1) a projection set you believe is sharp, (2) **simulate** it into a full distribution and read the **median**, (3) shop the price | C (content) | same advice; the load-bearing step is (1), and nobody says where to get it |
| Establish The Run (ETR) | sells projections; claims 228-158 / +14.09% over 2024-25 and beats the close three seasons | B | edge reportedly decays in ~10 minutes; a subscription, not a method |
| OpticOdds, "Monte Carlo vs parametric in prop modelling" | Poisson / negative binomial / normal / log-normal for scans, Monte Carlo for precision at the tails | C (no method detail, no results) | confirms the *shape* of the practice, nothing more |
| Towards Data Science, "Create your own NFL TD props" | Poisson regression with QB and defence random effects, Gamma prior from consensus projections | C — the author: *"almost certainly too simple to beat market lines"* | honest about the ceiling |
| Winkelmann, Ötting, Deutscher & Makarewicz, *J. Sports Econ.* 2024 | simulations show how often a fully efficient market produces "inefficient" seasons at small n; 14 seasons of real data: inefficiencies occur in single seasons, **not persistently** | A | the standard our sweeps already apply — plateau, season split, CI — and the reason the 2024 DK ladder error above is not an edge |
| "Not feeling the buzz" correction study (arXiv 2306.01740) | reproduced a published profitable strategy; most of the profit was one mispriced bet; the rest did not persist after 2020 | A | same lesson |
| Open-source NFL simulators (NFLSimulatoR, nfl-simulation, NFL-play-by-player, DFS optimisers) | play/drive simulators from nflfastR; none prices props or reports a betting record | C | usable as scaffolding for §3, not as evidence |

Nothing found — in academic literature, on GitHub, or in any self-reported
professional record — documents a **from-scratch stat projection built on public
box-score data beating the sportsbook's main line**. The people who say they win
props say they do it with (a) a sharp reference price and line shopping (our
market model), (b) a distribution read against the median at alternate lines,
or (c) speed on news. Nobody says they do it with a better mean.

## 3. The method

**Stop trying to know the middle. The line already knows the middle. Model the
shape, anchor it to the market's median, and sell the shape where the book's
ladder is wrong.**

That is the only construction consistent with all of the evidence above:

- the information test says our projections add nothing at the main line;
- the main line carries no price information anyway (flat −115/−115);
- the outside world's stated method is a *distribution* against the *median*,
  and its stated edge is at alternates and tails;
- the one thing public play-by-play data can plausibly describe better than a
  book's ladder-scaling algorithm is a specific player's **variance and skew** —
  a 12-target slot receiver and a 5-target deep threat can share a 60.5-yard
  median and have completely different 90.5-yard probabilities.

Concretely, a usage-based Monte Carlo per player per game:

1. **Anchor.** Take the market's median for the stat: the de-vigged Pinnacle /
   betonlineag main line (or, when wired, the Kalshi ladder mid —
   `docs/prop_market_research.md` §1). The simulation is *not* allowed to move
   the median. This is the step that encodes the information test.
2. **Simulate the shape from usage, not from the stat.** Per player, from
   nflverse play-by-play (not yet used by any model here —
   `docs/nfl_props_model.md` §6 item 2):
   - targets (or carries) ~ negative binomial, mean from routes × target share,
     dispersion fitted per player over a trailing window;
   - catch given target ~ Beta-binomial on the player's catch rate at his aDOT;
   - yards per catch ~ log-normal (or gamma) fitted on the player's own
     air-yards + YAC distribution — this is where skew lives;
   - touchdowns ~ Poisson on red-zone share, for the anytime market.
   Draw 10,000 games. Rescale the draws so the simulated **median** equals the
   market median from step 1.
3. **Read the ladder.** From the rescaled draws, P(over) at every alternate
   line the book offers. Compare to the book's ladder prices, de-vigged. The bet
   is an alternate line where the simulated tail and the book's tail disagree
   by more than a cut — never the main line, where by construction there is no
   disagreement to have.
4. **Correlated legs, second.** The same draws give joint distributions (QB
   pass yards × WR1 receiving yards); books price same-game parlays with their
   own correlation assumptions. Later, only if step 3 clears.

Why this is not the alternate-ladder experiment already closed (§1 item 4):
that scan had no shape model — it graded one bet per proposition off the raw
ladder against a normal-ish assumption and found a 2024 DK error. This grades
a per-player fitted shape against the ladder, and the placebo (step 4 below)
is what separates "our shape knows something" from "DK's ladder was wrong in
2024".

## 4. The experiment, pre-registered

Zero Odds API credits: every input is already held.

| input | where |
|---|---|
| DK alternate ladders, 2023-25 | `player_prop_odds` alt rows, 574,525 rows / 21,153 props (`nfl_prop_profitability_search.md` §7c) |
| sharp main lines for the anchor | Pinnacle backfill 44,692 rows + betonlineag (2026-09-08) |
| play-by-play for usage and yardage distributions | nflverse PBP (to be loaded; `nfl/data/pbp/` exists in the standalone package) |
| actuals | `nfl_player_game_log` |

Method: walk-forward by season (fit shapes on 2023, grade 2024; fit on 2023-24,
grade 2025), one bet per proposition, real DK alternate prices, cuts swept 3-8pp.

Pre-registered bars, all of which must hold before anything is written to
`config.py`:

1. Positive in **each** graded season, not pooled.
2. 90% CI on ROI excludes zero at a cut carrying ≥ 200 bets, and the two
   neighbouring cuts are positive (plateau, not peak).
3. **Placebo**: replace the per-player fitted shape with a single pooled
   normal of the same median. If the placebo grades the same, the edge is the
   ladder, not the shape, and it is the 2024 DK error again.
4. **Both sides**: the selected bets are not > 70% one direction. An 87%-under
   selection is one bet repeated, and it is the defect §1 flagged.
5. Beats the closing alternate price (CLV) on the median bet.

Kill criterion, stated before the first run: if bars 1-3 fail at every cut,
this line of work closes and the eleven models are paused, and the honest
conclusion is that public data does not price NFL props better than the book.

Cost: one session to build the simulator and the grader, no credits. The
under-bias audit (§1) is a one-hour precondition and should run first, because
if the P(over) arithmetic in `scorer._make_prop_pick` is wrong, every graded
number in §1 is wrong in the same direction.

## 5. RESULTS (2026-09-11, same day, mike: "1 and 2") — the method fails its own bars. Closed.

Run in order, zero credits, everything from `data/local`.

### 5a. The precondition: the 87% under lean is a dispersion mis-fit, not a level bias

From the walk-forward dump (`models.nfl_prop_backtest --all --dump`, 2024-25),
per model over every quoted row: the projection level is within 0-6% of the
realised mean, and correcting it barely moves the side split.

| model | rows | pred / actual mean | model mean P(over) | realised over rate | under share | under share after level fix |
|---|---|---|---|---|---|---|
| pass_attempts | 826 | 1.005 | 45.9% | 46.4% | 61% | 65% |
| pass_completions | 828 | 0.995 | 44.4% | 48.2% | 69% | 67% |
| pass_tds | 916 | 0.957 | 45.0% | 50.1% | 66% | 57% |
| pass_yards | 942 | 1.005 | 46.0% | 50.3% | 70% | 71% |
| rec_yards | 3,177 | 1.005 | 48.2% | 47.6% | 60% | 61% |
| receptions | 3,114 | 1.000 | 47.0% | 47.2% | 61% | 61% |
| rush_attempts | 984 | 0.971 | 43.4% | 47.6% | 67% | 58% |
| rush_rec_yards | 1,916 | 0.951 | 44.3% | 49.2% | 75% | 67% |
| rush_yards | 1,244 | 0.967 | 45.3% | 48.0% | 71% | 64% |
| sacks | 1,747 | 0.943 | 33.0% | 37.4% | 96% | 93% |
| tackles_assists | 2,347 | 0.988 | 43.7% | 45.5% | 72% | 68% |

Two things fall out. The models' P(over) sits 2-5pp under the realised over
rate on the volume markets even when the mean is right, so the lean comes from
the fitted distribution putting too much mass low (zero-inflation and shape),
not from the projection. And **the realised over rate at the main line is
46-48% on almost every market** — the book's line sits a little above the
median, so a blind under is a ~52-53% proposition, about break-even at −110.
That is why under-leaning models have looked "nearly fine" for a year: they
were riding a market lean, not a model.

### 5b. Is DraftKings' alternate ladder mispriced anywhere? No — it is over-priced on the over side everywhere

`scripts/nfl_prop_ladder_calibration.py`. Every DraftKings alternate OVER
quote in the `open` series 2023-25, latest pre-kickoff snapshot per
proposition, 126,546 strike rows over 13,000+ propositions. "adj" is the
implied probability scaled by the main line's two-way de-vig factor, which
under-corrects longshots, so a negative reading at high strikes is conservative.

| strike / main line | n | raw implied | adjusted fair | realised | realised − fair | ROI of every over, blind |
|---|---|---|---|---|---|---|
| 0.00-0.60 | 11,668 | 89.2% | 84.0% | 84.2% | +0.2pp | −5.7% |
| 0.60-0.85 | 16,426 | 76.4% | 71.9% | 69.9% | −2.0pp | −8.6% |
| 0.85-1.15 | 17,412 | 53.0% | 49.9% | 48.1% | −1.8pp | −9.3% |
| 1.15-1.50 | 23,525 | 28.2% | 26.6% | 24.4% | −2.2pp | −14.1% |
| 1.50-2.00 | 23,368 | 16.4% | 15.4% | 13.7% | −1.7pp | −19.6% |
| 2.00+ | 34,147 | 8.2% | 7.7% | 6.2% | −1.5pp | −28.9% |

Every band, every market, every season with ≥ 100 rows reads the same way:
the over hits LESS often than even the vig-adjusted price says. The
favourite-longshot bias, exactly as the literature has it. There is no band
where an over on the ladder is under-priced, and DraftKings quotes no under on
the ladder (0% of 2025 rows), so the side that IS mispriced cannot be bet.
**A shape model against this ladder can only win by finding player-specific
overs the book has under-priced, against a base rate where every over is 1.5
to 2.2pp too dear.**

### 5c. The simulation — three arms, two markets, every cell negative

`scripts/nfl_prop_shape_sim.py`, walk-forward, one bet per proposition at the
largest-edge strike, real DraftKings alternate prices, 10,000 draws per
proposition, anchor from Pinnacle (89%), betonlineag (10%) or DK's own two-way
main (1%).

| market | arm | cut | bets | ROI | 90% CI | 2024 / 2025 |
|---|---|---|---|---|---|---|
| receiving yards | player usage compound | 3% | 2,900 | −10.3% | (−16.5, −4.0) | −3.9% / −20.0% |
| receiving yards | player usage compound | 5% | 1,741 | −17.0% | (−24.9, −8.5) | −2.9% / −25.5% |
| receiving yards | player gamma, own totals | 3% | 2,957 | −10.9% | (−14.9, −7.1) | both negative |
| receiving yards | player gamma, own totals | 5% | 2,268 | −11.8% | (−16.0, −7.5) | both negative |
| receiving yards | **placebo**, pooled gamma | 3% | 3,618 | −21.2% | (−27.7, −14.5) | |
| rushing yards | player usage compound | 3% | 1,571 | −11.0% | (−17.7, −4.0) | −15.7% / −7.0% |
| rushing yards | player usage compound | 5% | 1,017 | −10.6% | (−19.5, −1.3) | −10.3% / −14.4% |
| rushing yards | player gamma, own totals | 3% | 1,698 | −9.8% | (−16.0, −3.5) | both negative |
| rushing yards | player gamma, own totals | 5% | 1,218 | −8.4% | (−15.9, −0.4) | both negative |
| rushing yards | **placebo**, pooled gamma | 3% | 2,107 | −13.2% | (−23.2, −2.8) | |

(2023 carries 60-185 bets per cell, intervals of ±30pp, and is not read.)

Against the pre-registered bars: **bar 1 fails** (no graded season positive
in any cell); **bar 2 fails** (every interval that excludes zero excludes it
on the negative side); **bar 3 is moot** (the placebo loses more, but there
is nothing for it to reproduce). The kill criterion in §4 is met.

The calibration tables say why. The per-player gamma reads 22.0% where the
book's adjusted fair reads 22.2% and reality reads 20.2%; the usage compound
reads 22.0% against 18.3% and 16.3%. The player's own shape knows nothing the
ladder does not already price, and the compound arm's tails run FATTER than
reality (a 16-game usage window carries role changes the book has already
priced out). Selecting on "sim > fair" therefore selects the strikes where the
sim is most wrong, and grades at −10% to −17% against a ladder whose blind
over already runs −6% to −29%.

### 5d. What this closes, and what it leaves

Closed, with this measurement: the stat-based approach in ANY of its forms
tried here — projecting the mean (11/11 lose vs DK, §1), projecting the shape
around the market's mean (this section), and the ladder as a mechanical edge
(§5b). With §1's six angles that is nine attempts, all graded, none positive
out of sample. The honest conclusion is the one the information test already
gave: **public box-score data does not price NFL player props better than
DraftKings does, at the middle or in the tails.**

What is left is not a modelling problem:

- `nfl_prop_market` is the lane that works (+7.84% over 1,990, CI clear of
  zero, three seasons). Its ceiling question is in `docs/followups.md`.
- `nfl_prop_tackles_assists` is the one stat model with a clean record
  (+19.9% on 240 bets in this dump; +15.6% on 340 with placebo in
  `nfl_prop_profitability_search.md` §4) and its edge is definitional, not
  projective. It is live.
- The other ten stat models have no evidence for them and nine graded
  attempts against them. Pausing them is a model update and mike's call; the
  case for keeping them running is only that the tightened cuts limit the
  damage to a measured −1.9% on 2,133 bets.
- The Kalshi ladder as a second exchange-grade reference for the MARKET rule
  (`docs/prop_market_research.md` §1, §6b — built, unwired) is the one lead
  in this area with an A grade that has not been graded yet.

Nothing further from this line of work should be built without a new source
of information the book does not have.

## 6. What NOT to spend credits on

Measured and closed; re-opening any of these needs a new argument, not a new
season:

- more features against the DraftKings main line (information test);
- injuries, NGS, gradient boosting on market features, predicting DK's move;
- buying a projection subscription as the "source of truth" — the only vendor
  claiming to beat the close says the edge lasts minutes, which is a speed
  business the platform is not built for;
- retraining the eleven on more seasons — the holdout MAE and calibration were
  already fine (`nfl_props_model.md` §5a); the problem was never fit quality.

## Sources

- [Unabated — Profitable Prop Betting In 3 Easy Steps](https://unabated.com/articles/profitable-prop-betting-in-3-easy-steps)
- [OpticOdds — Monte Carlo vs. Parametric Distributions in Player Prop Modeling](https://opticodds.com/blog/probability-paths-in-player-prop-modeling)
- [Towards Data Science — Create Your Own NFL Touchdown Props with Python](https://towardsdatascience.com/create-your-own-nfl-touchdown-props-with-python-b3896f19a588/)
- [Winkelmann, Ötting, Deutscher, Makarewicz — Are Betting Markets Inefficient? Evidence From Simulations and Real Data (2024)](https://journals.sagepub.com/doi/10.1177/15270025231204997)
- [Not feeling the buzz: Correction study of mispricing and inefficiency in online sportsbooks (arXiv 2306.01740)](https://arxiv.org/abs/2306.01740)
- [NFLSimulatoR](https://github.com/rtelmore/NFLSimulatoR), [nfl-simulation](https://github.com/dlm1223/nfl-simulation), [NFL-play-by-player](https://github.com/paulcbogdan/NFL-play-by-player)
- Repo: `docs/prop_market_research.md` (Peabody, ETR, Kalshi), `docs/nfl_prop_information_test.md`, `docs/nfl_prop_profitability_search.md`, `docs/nfl_props_model.md` §5-6

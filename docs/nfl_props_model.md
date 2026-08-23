# NFL player props — architecture decision, market shortlist, and validation plan

Status: **models built and assessed on outcomes; NOT yet validated against prices.**
Written 2026-08-23, before any betting result exists, so the bar below cannot be
moved after the fact.

This answers `docs/nfl_props_build_prompt.md`. Everything here is derived from
NFL data, not carried over from the MLB/NBA/WNBA prop models. Where those models
made an assumption that does not survive contact with NFL data, it is called out.

---

## 0. What contradicts the brief

Three things, stated up front.

1. **"Historical prop odds are the gating input" is right, but the gate is worse
   than the brief implies.** The Odds API historical *featured-market* endpoint
   starts 2020-06-06; historical **player props** are a separate, later,
   per-event product. Even with unlimited credits, a prop backfill is bounded by
   how far back per-event snapshots exist and by their timestamp density — and
   density, not credits, is what decides whether a backtest is honest (trap #1:
   a line without a known post time relative to injury news is a leak). NFL prop
   odds collection is being built in a parallel session; this session does not
   duplicate it. **Nothing in this document claims an edge, because no price has
   been joined to a model output yet.**

2. **The platform's existing prop machinery encodes a distributional assumption
   that is wrong for most NFL markets.** Every MLB/NBA/WNBA prop model is
   `count:poisson` + a Poisson CDF at the line. NFL yardage markets have
   variance-to-mean ratios of **27–36** (Poisson requires 1). Even NFL count
   markets are overdispersed (pass attempts 3.7, carries 3.4, receptions 1.7).
   Reusing the Poisson head would produce sharply overconfident P(over) — worst
   exactly in the tails where props are priced. This is the single most important
   finding here and it is measured, not asserted (§2).

3. **Two markets in the brief's list are not merely thin — they have negative
   out-of-sample R².** Field goals made and passing interceptions are predicted
   *worse* than the pooled mean by a tuned model with a full feature set. They
   should be dropped, not thresholded.

---

## 1. The decision: shared feature core, per-market response head

**Not one model. Not fully separate models. A hybrid, and the split is on the
response distribution, not on the features.**

- **Shared:** one feature builder, one training path, one scoring path. Every
  market draws on the same latent — team plays, pace, game script, and the
  player's share of it. There is no evidence for market-specific *feature*
  engineering, and one builder is what makes the walk-forward harness reusable.
- **Separate:** the response family and its dispersion, fitted per market. This
  is forced by the data (§2), not by convenience.

### What was tested and rejected

The obvious "shared usage core" reading of the brief is a **compound model**:
project volume (targets/carries/attempts), project per-play efficiency, and
convolve them into the yardage distribution. It is the generatively correct
form, it shares the volume core with the attempts/receptions markets, and it
gives the zero mass for free (`P(yards = 0) = P(volume = 0)`).

It was implemented (NB volume × Gamma per-unit, closed-form convolution) and
scored against a direct zero-inflated-Gamma model on identical walk-forward
splits, with CRPS (proper, line-free) and with P(over) log-loss at a line ladder
set by a naive rolling-8 baseline so neither candidate is advantaged:

| market | CRPS direct | CRPS compound | compound win | log-loss win |
|---|---|---|---|---|
| receiving yards | 17.650 | 17.570 | +0.45% | −0.25% |
| rushing yards | 19.359 | 19.860 | **−2.58%** | **−2.27%** |
| passing yards | 46.638 | 46.159 | +1.03% | +0.23% |

**Rejected.** The decomposition adds a second estimated quantity (per-play
efficiency) that is close to unforecastable, so the extra structure buys
estimation error, not accuracy. It loses outright on rushing. A wash on two
markets and a loss on the third is not a reason to ship the more complex thing.

### The architecture that ships

| response family | markets | why |
|---|---|---|
| **Negative binomial** | pass attempts, pass completions, carries, receptions, tackles+assists | overdispersed counts (var/mean 1.4–3.7) |
| **Poisson** | pass TDs, defensive sacks | var/mean ≈ 1 — genuinely Poisson |
| **Zero-inflated Gamma** | pass yards, rush yards, receiving yards, rush+rec yards | continuous, right-skewed, var/mean 27–36, real mass at 0 |
| **Calibrated logistic** | anytime TD | binary |

Dispersion (`r` for NB, shape `k` for Gamma, zero mass `p0`) is fitted by method
of moments on **training-fold residuals only** and stored in the model artifact,
so the scorer computes `P(over)` from the same distribution the model was
validated under. Not a global constant.

---

## 2. The measurement behind that decision

All walk-forward: fit on every prior season, test on the named season, seasons
2021–2025 pooled. Source: nflverse weekly player stats, 2015–2025 regular season
(191,345 player-games). Pool per market approximates "a book would hang a line
on this player" via prior-3-game usage.

### 2a. Response distribution — raw dispersion

| market | n | mean | var/mean | zero % |
|---|---|---|---|---|
| passing yards | 5,623 | 228.8 | **35.7** | 1.9 |
| receiving yards | 20,161 | 45.8 | **29.8** | 6.6 |
| rushing yards | 7,328 | 54.6 | **26.7** | 2.2 |
| pass attempts | 5,623 | 31.8 | 3.70 | 1.2 |
| carries | 7,328 | 12.6 | 3.36 | 1.0 |
| completions | 5,623 | 20.5 | 2.76 | 1.8 |
| receptions | 20,161 | 3.9 | 1.67 | 5.8 |
| tackles + assists | 26,028 | 5.2 | 1.37 | 6.1 |
| pass TDs | 5,623 | 1.45 | **0.97** | 24.6 |
| rush TDs | 7,328 | 0.41 | **1.07** | 67.4 |
| rec TDs | 20,161 | 0.29 | **1.01** | 75.2 |
| defensive sacks | 62,268 | 0.13 | 1.20 | 88.4 |
| FG made | 5,398 | 1.66 | 0.89 | 17.2 |

### 2b. Poisson vs negative binomial on identical means

Same fitted mean, only the response family differs. `CalErr` is mean absolute
gap between predicted and realised over-rate across 10 equal-count probability
bins.

| market | log-loss Poisson | log-loss NB | CalErr Poisson | CalErr NB |
|---|---|---|---|---|
| pass attempts | 0.7066 | **0.6714** | 8.31% | **4.96%** |
| pass completions | 0.6951 | **0.6796** | 7.67% | **5.34%** |
| carries | 0.6670 | **0.6531** | 6.46% | **3.11%** |
| receptions | 0.6333 | **0.6320** | 2.75% | **2.46%** |
| tackles + assists | 0.6103 | **0.6097** | 1.21% | **0.76%** |
| pass TDs | 0.5825 | 0.5827 | 2.00% | 1.92% |

NB roughly halves calibration error on every overdispersed market and is a wash
on pass TDs — which is the confirmation that the split is real and not a
free-parameter effect. **Under a Poisson head, pass attempts would be
miscalibrated by 8.3 percentage points.** No threshold recovers that.

### 2c. Predictability, and lift over a rolling-average baseline

`r2_naive` is a rolling-8-game average. Lift over that baseline is the more
decision-relevant number: a book's crude component is a weighted recent average,
so lift is where a model could differ from the number on the screen. It is *not*
a claim about beating a real line.

| market | n test | R² model | R² naive | MAE lift over naive |
|---|---|---|---|---|
| tackles + assists | 11,411 | 0.217 | −0.221 | **16.3%** |
| defensive sacks | 11,734 | 0.069 | −0.004 | **7.6%** |
| pass attempts | 2,624 | 0.194 | 0.043 | **7.1%** |
| passing yards | 2,624 | 0.190 | 0.079 | **6.6%** |
| pass completions | 2,624 | 0.217 | 0.086 | **6.4%** |
| carries | 3,538 | 0.268 | 0.171 | 5.7% |
| pass TDs | 2,624 | 0.112 | 0.017 | 4.5% |
| FG made | 2,516 | **−0.009** | −0.117 | 4.0% |
| rushing yards | 3,538 | 0.127 | 0.081 | 3.5% |
| rush + rec yards | 15,507 | 0.276 | 0.232 | 2.9% |
| receptions | 9,135 | 0.205 | 0.165 | 2.9% |
| receiving yards | 9,135 | 0.196 | 0.167 | 2.3% |
| rush TDs | 3,538 | 0.030 | −0.061 | 1.0% |
| rec TDs | 9,135 | 0.037 | −0.067 | **−0.8%** |
| pass INTs | 2,624 | **−0.016** | −0.135 | 2.1% |

Anytime TD, modelled as a calibrated binary rather than a count, is materially
better than its count R² suggests: AUC 0.654, CalErr 2.3%, and the top predicted
decile realises 47.9% against a 46.9% prediction. Kicking points: R² 0.029.

---

## 3. Market shortlist

### Build and pursue

| market | Odds API key (provisional) | family | why |
|---|---|---|---|
| tackles + assists | `player_tackles_assists` | NB | best signal in the sport (16.3% lift, 8.0% log-loss gain over the best constant), and IDP props get the least modelling attention from books |
| pass attempts | `player_pass_attempts` | NB | 7.1% lift; volume is game-script-driven and our vegas-total/spread features are exactly that |
| pass completions | `player_pass_completions` | NB | 6.4% lift |
| passing yards | `player_pass_yds` | ZI-Gamma | 6.6% lift, highest-liquidity yardage market |
| carries | `player_rush_attempts` | NB | 5.7% lift, R² 0.268 |
| receptions | `player_receptions` | NB | thick market, well-calibrated; low lift — include, but expect it to need the biggest edge threshold |
| receiving yards | `player_reception_yds` | ZI-Gamma | thickest prop market in the sport; low lift is a warning, not a disqualification |
| rush + rec yards | `player_rush_reception_yds` | ZI-Gamma | highest R² of any yardage market (0.276) |
| rushing yards | `player_rush_yds` | ZI-Gamma | modest |
| anytime TD | `player_anytime_td` | logistic | calibrated (2.3% CalErr); the most-juiced NFL prop, so it needs the largest threshold |

### Drop, with reasons

| market | why dropped |
|---|---|
| **field goals made / kicking points** | out-of-sample R² **−0.009** and 0.029. A tuned model is worse than the mean. Kicker output is a function of drives ending in field-goal range — noise at the game level. |
| **passing interceptions** | out-of-sample R² **−0.016**. Rare, defence-driven, and unforecastable from the passer's own history. |
| **rushing TDs / receiving TDs individually** | R² 0.030 / 0.037 and −0.8% lift on rec TDs. Subsumed by anytime TD, which is better posed and better priced. |
| **longest rush / longest reception** | an extreme-value problem: the distribution of a per-game maximum is dominated by the tail of a per-play distribution we cannot forecast. Nothing in the usage features moves the max conditional on the mean. |
| **first TD** | anytime TD already sits at R² 0.03 on the count; first TD adds a sequencing lottery on top and carries the worst hold on the board. |
| **defensive interceptions** | same failure mode as passing INTs, at a lower base rate. |
| **defensive sacks** | *borderline.* 7.6% lift is real, but 88% of player-games are zero and the market is thin with low limits. Modelled (Poisson head) but **paper-only** pending real prices. |

**"We can price it" vs "we can beat it".** Nothing above is a claim of the
second. What §2 establishes is which markets have *forecastable* signal and
which response family is *calibrated*. Whether any of them beats a quoted number
is decided by §5 and cannot be decided before prop odds land.

---

## 4. Data

### In hand and used (free, no key, verified reachable from the worker)

| source | what it gives | cadence |
|---|---|---|
| nflverse `stats_player_week` release CSV | outcome data + usage: targets, target share, air-yards share, WOPR, RACR, air yards, YAC, EPA, full defensive and kicking splits | nightly in season |
| nflverse `nfldata/games.csv` | schedule, **closing spread and total**, roof, surface, temp, wind, rest | nightly |
| nflverse `snap_counts` release CSV | offensive/defensive snap share — the cleanest availability signal | nightly |

The spread and total are the game-script driver and they are legitimately known
pre-game; `implied_team_total = total/2 + team_spread/2` is a feature, and for
the volume markets it is one of the strongest.

### Not used in v1, and what it would buy

nflverse **play-by-play** (`pbp` release, parquet, reachable) gives red-zone
carry/target share, aDOT, route participation and personnel. That matters most
for the TD markets — which are mostly dropped — and would sharpen receptions.
Deferred deliberately: the top market (tackles+assists) needs opponent *offensive*
volume, which the team-game aggregates already provide.

### Prop odds — collected, and priced from a measurement

Built here (`data/ingestors/nfl_prop_odds_ingestor.py`) after confirming
`player_prop_odds` held **zero NFL rows**. Three properties, all cheap now and
expensive to retrofit:

1. **Every book keeps its own row** — the parser runs once per bookmaker.
   Screening books is a selection-time decision; a "best line" baked in at
   ingest makes trap #2 unfixable, and picking the best line across books
   preferentially samples bad data.
2. **The stored snapshot timestamp is the line's, not the run's.** The Odds API
   snaps a historical request to its nearest stored snapshot and reports which
   one it served; that is the timestamp that decides whether a line predates the
   injury news, so it is threaded through to the row.
3. **The game id is resolved, never constructed.** The modelling tables key on
   the nflverse id; the odds feed knows team names and a kickoff instant. An
   unmapped team yields a skipped event, never an orphan row the scorer would
   silently never join to.

**Measured availability and cost** (probes run against the live API, not
estimated):

| probe date | result | credits/event |
|---|---|---|
| 2024-10-06 | 391 rows from 2 events, 11 markets, 5 books | 66 |
| 2023-10-08 | 59 rows from 1 event | 51 |
| 2022-10-09 | **422 on every market — no data** | 1 |
| 2021-10-10 | **422 on every market — no data** | 1 |

So **historical NFL player props begin in 2023**: the usable span is 2023, 2024
and 2025, three seasons. Markets are requested in chunks, which is why a date
with no data costs 1 credit instead of 60.

**Collected (2026-08-23):** the full three seasons are in `player_prop_odds` —
**210,592 rows across 849 games, 11 markets and 5 books**, 2023-09-07 to
2026-02-08, at one pre-game snapshot per game date.

| season | games with a prop line | of |
|---|---|---|
| 2023 | 280 | 285 |
| 2024 | 284 | 285 |
| 2025 | 285 | 285 |

**99.3% coverage.** Kickoff timestamps are present on 100% of 2024/2025/2026
games, so the started-game guard can actually fire — a NULL there would mean a
prop scored against an in-play price, the failure this repo shipped for months
on MLB.

That three-season limit is the binding constraint on validation, not the model:
the walk-forward requirement in §5 has three seasons to work with, so a
per-season split will be thin and an edge concentrated in one of them is one
season, not an edge.

### `games` rows — the FK nobody expects

`player_prop_odds.game_id` and `picks.game_id` both reference `games`, and until
now an NFL game only got a `games` row if it carried a wind or opener pick. The
first production prop insert failed on that constraint, and an NFL prop *pick*
would have failed the same way later. The ingest now writes one `games` row per
NFL game using the same `NFL_{nflverse_id}` id the wind publisher already uses.
Safe on the daily health check: NFL is not in `CRIT_FINALS_SPORTS`, so an
unplayed game with no score is a warning, never a red run.

---

## 5. Validation plan — fixed now, before any result exists

A market graduates from paper to live **only** by clearing all six. Any market
that fails any one of them stays paper regardless of its ROI.

1. **Priced at the juice actually quoted.** Every simulated bet settles at the
   American price on that side, in that book's own row, at the snapshot in force
   at bet time. No −110 fill-ins, ever. A market with no price is not a bet, it
   is a skipped row.
2. **The backtest runs the deployed selection.** Same book screen, same line,
   same timestamp cut-off, same threshold, same pool gate as the live scorer.
   The scorer's own pool function is the one the backtest calls — not a copy.
3. **Timestamp discipline.** A bet may only use a line snapshot strictly before
   its game's kickoff, and the model row may only use stats strictly before that
   game. Any row whose line snapshot post-dates kickoff is dropped, not graded.
4. **Placebo.** Re-run the entire selection with the sharp reference book
   swapped for a soft one. If the placebo reproduces the result, it is a
   selection artifact and the market is dead.
5. **Walk-forward by time, per-season split reported.** Fit on prior seasons,
   bet the next. Any edge that is more than 60% concentrated in one season is
   reported as one season, not an edge.
6. **Beat the right benchmark.** The benchmark is the no-vig probability implied
   by the price paid, not 50%. A market must beat it after the hold, on ≥ 100
   graded bets, with the bootstrap CI on ROI excluding zero.

Two extra rules the props brief demands and this repo has been bitten by:

- **Push handling.** Whole-number receptions and attempts push often. Grading
  must return PUSH (stake returned), and EV at those lines must be computed
  three-way. A model that grades pushes as losses will look wrong; one that
  grades them as wins will look right for the wrong reason.
- **Correlation.** Two props on the same player, or a QB's yards with his WR1's
  yards, are one bet. Until sizing knows this, the card carries at most one leg
  per (game, team) side for correlated markets.

---

## 5a. Trained results — outcomes only, no price involved

Trained 2015–2024, **held out 2025** (a season the models never saw), 25 Optuna
trials per head, dispersion fitted from out-of-fold residuals. Read this as
"is the predictive distribution right", not "does it win money" — no price has
been joined to any of it.

| model | family | holdout n | MAE | CalErr | fitted dispersion |
|---|---|---|---|---|---|
| receptions | NB | 1,635 | 1.72 | **2.54%** | r = 12.6 |
| anytime TD | logistic | 2,813 | — | **2.48%** | AUC 0.657 |
| sacks | Poisson | 2,028 | 0.39 | 3.01% | — |
| tackles + assists | NB | 2,152 | 2.13 | **3.21%** | r = 17.7 |
| receiving yards | ZI-Gamma | 1,635 | 24.24 | **3.49%** | k = 2.06, p0 = 0.064 |
| rush + rec yards | ZI-Gamma | 2,813 | 25.56 | 4.00% | k = 2.13, p0 = 0.054 |
| pass completions | NB | 478 | 4.96 | 5.90% | r = 18.9 |
| pass attempts | NB | 478 | 7.19 | 6.07% | r = 17.2 |
| rushing yards | ZI-Gamma | 633 | 26.94 | 6.24% | k = 2.32, p0 = 0.022 |
| passing yards | ZI-Gamma | 478 | 60.57 | 7.36% | k = 7.22, p0 = 0.017 |
| pass TDs | Poisson | 478 | 0.94 | 8.00% | — |
| carries | NB | 633 | 3.97 | 8.72% | r = 8.99 |

Three things worth reading off this table.

**The fitted dispersions independently reproduce §2a.** Nobody set them: they
are method-of-moments estimates from out-of-fold residuals. Passing yards comes
back with Gamma shape 7.2 — nearly symmetric, matching the −0.30 skew measured
on the raw data — while receiving and rushing yards come back at ~2.1, sharply
right-skewed, also as measured. Every NB `r` lands far below the 500 cap, i.e.
real overdispersion was detected in every count market. The distributional
assumption and the data agree without being made to.

**Calibration tracks sample size, not market quality.** The six best-calibrated
models are the six with 1,600+ holdout rows; the six worst are the QB and RB
markets, where a season is 478–633 rows because only ~28 players per week get a
line. That is a reason to expect the pass-market calibration to improve with
more seasons, and a reason not to trust those four at a tight threshold today.

**The two Poisson rows use a different metric.** `pass_tds` and `sacks` report
the existing Poisson calibration error; the NB and Gamma rows report PIT
calibration, which is line-free and stricter. They are not comparable
across families, only within.

**None of this says a market is beatable.** The best-calibrated model in the
table is still only useful if its number differs from the book's, and that
comparison does not exist yet.

## 5b. Backtest against real prices — the verdicts

Walk-forward by season: fit on every prior season, bet the next. DraftKings,
its own quoted price on each side, no −110 fill-ins, line snapshot required to
pre-date kickoff, three-way push grading, edge measured against the de-vigged
price actually paid. 100-bet floor for a verdict.

**Eleven of twelve markets are not beatable, and the twelfth was a measurement
error.** That is the finding.

| model | bets | win% | ROI | 95% CI | over / under bets | verdict |
|---|---|---|---|---|---|---|
| rush attempts | 685 | 53.14% | −0.10% | (−7.2, +6.5) | 189 / 496 | not beatable |
| sacks | 833 | 62.91% | −1.22% | (−6.7, +4.1) | 3 / 830 | not beatable |
| pass TDs | 251 | 58.17% | −1.20% | (−11.4, +9.3) | 30 / 221 | not beatable |
| receptions | 1,616 | 53.53% | −2.40% | (−6.8, +2.2) | 491 / 1,125 | not beatable |
| rushing yards | 838 | 51.31% | −3.23% | (−9.5, +3.0) | 190 / 648 | not beatable |
| rush + rec yards | 1,288 | 50.93% | −4.46% | (−9.6, +0.8) | 299 / 989 | not beatable |
| pass completions | 478 | 51.05% | −4.52% | (−13.0, +3.6) | 129 / 349 | not beatable |
| passing yards | 493 | 50.51% | −4.92% | (−13.3, +3.5) | 217 / 276 | not beatable |
| receiving yards | 1,887 | 50.13% | −5.58% | (−9.8, −1.5) | 652 / 1,235 | not beatable |
| pass attempts | 473 | 49.89% | −6.19% | (−14.6, +2.3) | 153 / 320 | not beatable |
| anytime TD | 111 | 28.83% | −14.93% | (−40.9, +11.8) | 111 / 0 | not beatable |
| **tackles + assists** | 1,639 | 60.71% | **+13.47%** | (+9.0, +17.9) | 107 / **1,532** | **definitional mismatch, −9.1pp** |

Note the win rates: several markets win well over half their bets and still
lose money. That is the hold, and it is why §5.6 benchmarks against the
de-vigged price rather than 50%.

### The tackles result, and why it is not an edge

+13.47% over 1,639 bets with a confidence interval nowhere near zero, positive
in both seasons, is the strongest-looking number in this whole document. It is
not real, and three measurements say so.

**The placebo earns it too.** Substituting the player's own 8-game rolling
average for the model returns **+10.09% over 1,537 bets**. A rolling average
cannot beat a real market by 10 points. Three quarters of the "edge" survives
deleting the model, so it was never the model's.

**It is one-sided.** 1,532 of 1,639 bets are unders, and the 107 overs lose
18.4%. An edge that only exists on one side of a two-sided market is a clue
that the two sides are not being measured on the same scale.

**Our actual is not the stat the book grades.** Across all 2,347 quoted rows —
independent of which we bet — our computed tackles land over the line **41.1%**
of the time, and average **0.47 below** it, while DraftKings' own de-vigged price
says **50.2%**. That is a **−9.1pp gap, and no other market is past −3.5pp**. So
the model was not finding soft lines; it was counting a smaller number than the
book counts, and betting the under on everything.

Leading hypothesis, not yet confirmed: nflverse's weekly defensive columns are
derived from play-by-play tackle attribution, while books grade off the official
gamebook, and PBP attribution is known to undercount. The size and sign match.
Confirming it means checking our per-game counts against a gamebook source —
that, not a threshold, is the fix.

**This is why the market with the most out-of-sample signal in the sport
(§2c: 16.5% MAE lift, the best in NFL) is the one that must stay paused
hardest.** Its inputs are fine; its target is measured against the wrong ruler,
and the live scorer would make exactly the bet the backtest made.

### The gate that now catches this class of error

The naive check — "is our over-rate near 50%?" — is wrong, and would have
condemned two honest markets: a book sets a yardage or reception line at the
median, but pins sacks and anytime-TD at 0.5 and prices the skew. The benchmark
that holds everywhere is **the book's own de-vigged price**. Measured on the
same run:

| market | our over-rate | book's de-vigged | gap |
|---|---|---|---|
| **tackles + assists** | **41.1%** | **50.2%** | **−9.1pp** |
| pass attempts | 46.4% | 49.9% | −3.5pp |
| anytime TD | 28.7% | 31.8% | −3.1pp |
| rush attempts | 47.6% | 50.2% | −2.6pp |
| receptions | 47.2% | 49.8% | −2.6pp |
| receiving yards | 47.6% | 50.1% | −2.5pp |
| rushing yards | 48.0% | 50.1% | −2.1pp |
| pass TDs | 50.1% | 48.1% | +2.0pp |
| pass completions | 48.2% | 49.8% | −1.6pp |
| rush + rec yards | 49.2% | 50.0% | −0.8pp |
| **sacks** | **37.4%** | **37.9%** | **−0.5pp** |
| passing yards | 50.3% | 50.0% | +0.3pp |

Sacks is the row that proves the benchmark. Its over-rate is 37.4% — nine points
from 50, further out than tackles — and it is **honest**: the book's own price
says 37.9%, because the line is pinned at 0.5 and the skew is priced. Against a
flat-50% check it would have been condemned; against the book it is clean, and
the one genuinely broken market is the only one flagged.

`_verdict` returns `DEFINITIONAL MISMATCH` beyond 5pp, **before** any ROI is
considered — a market cannot buy its way past this gate with a significant
return.

## 5c. The market-relative rule — de-vig the sharp book, bet the soft outlier

The projection models lost to the hold in eleven of twelve markets. That says
our projection is not better than the market's, not that the market is
unbeatable. §5b's own conclusion pointed at features; the bigger miss was
structural, and it is embarrassing in hindsight: **we collected five books and
priced against one of them.**

The construction that is documented to work — and that this repo already runs
live on NFL spreads (§28 opener) — is the opposite. Take a market-making book's
de-vigged price as the estimate of truth and bet wherever a retail book
disagrees by more than the juice. `models/nfl_prop_market.py`.

### Pinnacle is reachable and was never asked for

`config.ODDS_API_REGIONS` was hardcoded to `us`, and Pinnacle is served in `eu`.
Measured 2026-08-23: it quotes **8 of our 12 markets** — everything except rush
attempts, rush+rec yards, sacks and tackles+assists — at roughly 55-65% of
DraftKings' row count, because it prices fewer players per game. **A market
maker declining to quote is itself information**, and those four stay
projection-only. Backfilled 2023-2025: 44,692 Pinnacle rows, ~35k credits.

### Result

Graded against real quoted prices, one bet per proposition, post-kickoff quotes
dropped. At a 5pp threshold, **954 bets, 57.6% wins, +10.33% ROI, CI
(+4.1, +16.3)**, positive in all three seasons.

| min edge | bets | win% | ROI |
|---|---|---|---|
| 2pp | 18,860 | 53.2% | +0.5% |
| 3pp | 9,294 | 54.3% | +3.0% |
| 4pp | 3,844 | 55.3% | +5.0% |
| 5pp | 954 | 57.6% | **+10.3%** |

ROI rises monotonically with the threshold, seven of eight markets are positive,
and the over/under split is 458/496 — balanced, unlike the 93%-unders signature
that gave away the tackles mismatch in §5b.

### Why it is worth believing: the placebo

Swap the sharp reference for each retail book in turn and bet the others:

| reference | bets | ROI | three seasons positive? |
|---|---|---|---|
| **pinnacle** | 1,218 | **+11.95%** | **yes** (12.3 / 11.1 / 11.8) |
| draftkings | 517 | −1.88% | no |
| fanduel | 773 | −0.69% | no |
| betmgm | 1,079 | −14.90% | no |
| williamhill_us | 614 | −0.90% | no |
| espnbet | 369 | −2.50% | no |

If this were generic price dispersion, any reference would work. **None does.**
The edge is specifically Pinnacle's sharpness, which is the claim.

Two alternative explanations were ruled out before the result was believed.
Paired quotes are **98.9% within five minutes, median delta zero**, so this is
simultaneous sharp-vs-soft rather than stale-vs-fresh. And only **equal lines**
are compared: Pinnacle at 5.5 against DraftKings at 6.5 is a different
proposition, and calling that price gap an edge is precisely how §5b's tackles
mismatch manufactured a significant +13% out of a measurement error. 35,107
quotes were discarded on that rule.

### What is fragile: the threshold, not the strategy

Selecting the threshold greedily on 2023-24 picks 6pp (+23.7% on 172 bets), and
6pp applied blind to 2025 returns **−0.46% on 39 bets**. The tail overfits.

At a pre-committed **5pp** it replicates cleanly:

| | bets | ROI |
|---|---|---|
| train 2023-24 | 756 | +10.22% |
| **blind 2025** | 198 | **+10.76%** |

So the strategy holds out of sample; the threshold is not robustly determined by
the data and must not be chased.

### Expectation for 2026

Volume is falling as books tighten — 547 / 209 / 198 bets by season — so the
projection uses recent volume (~204), not the three-season average. Bootstrap of
a 204-bet season, 1u flat, 20,000 draws:

| scenario | HIGH (90th) | MED | LOW (10th) | P(losing season) |
|---|---|---|---|---|
| edge holds | +38.6u | +21.1u | +3.7u | 6% |
| **half the edge** | +23.8u | **+10.5u** | −3.1u | **16%** |
| quarter edge | +16.3u | +5.2u | −6.0u | 27% |

**Plan on the middle row.** This is the strategy books limit fastest, volume is
already declining, and the threshold is fragile as above.

### Timing, and the polling cadence

Every headline number above is measured at ONE snapshot, ~3h before kickoff,
because that is how the backfill was built. A T-24h series was then bought over
40 dates (300 games, ~19.5k credits) to answer the cadence question.

**Correcting the pilot.** A first 48-game pilot appeared to show edge
availability roughly doubling at T-24h. That was sample size, not signal. On
300 games the two offsets are a dead heat:

| offset | quotes | compared | edges | bets | win% | ROI |
|---|---|---|---|---|---|---|
| T-24h | 89,677 | 39,595 | 273 | 205 | 53.2% | +4.05% |
| T-3h | 96,485 | 43,440 | 271 | 200 | 51.5% | +0.73% |

Neither ROI is distinguishable from the other, or from zero, on ~200 bets — the
bootstrap intervals are (−10.0, +17.3) and (−12.9, +14.6). **No offset is
better.**

**What decides the cadence is disjointness, not ROI.** Restricting to the 83
games priced in both series, T-24h found 143 qualifying edges and T-3h found
145, and only **19 of them are the same proposition**. 124 exist only at T-24h,
126 only at T-3h. The edges are transient: they appear, get corrected, and are
replaced. On the 13% that do survive the six hours, the edge barely moves
(median −0.21pp), so a surviving edge is not decaying — it is simply rare.

So a second poll roughly **doubles the number of distinct bets** rather than
re-confirming the first. That is the whole argument for polling twice, and it is
the only part of this that the data supports strongly.

**Cost is not the constraint at this cadence.** ~61 credits per event per poll,
two polls, ~285 games a season ≈ **35k credits**, under 1% of the ~4.9M
remaining. Four polls a game would still be ~70k. What was ruled out earlier was
§28's hourly-from-T-10-days, which is ~1.26M.

**Cadence: poll at T-24h and T-3h, and take an edge when it appears.**

### One caution that outranks the timing question

The 300 sampled games return **+0.73%** at T-3h while the other 754 bets return
**+12.88%**. Both are the same rule at the same offset on the same three
seasons. The full 954-bet number is unchanged and still reproduces exactly, but
that spread is a real reminder of how wide the sampling variance is around
+10.33% — and it is the reason the projection above already plans on half the
edge rather than the point estimate.

The sample was not random: it was the first 8 events per date, which is the
early Sunday window. Slicing the full series by kickoff hour hints the same way
— early 1-4pm ET games +7.55% (450 bets) against 20-24 UTC +16.52% (133) — but
every interval overlaps every other, 371 bets have no kickoff recorded at all,
and this is precisely the kind of after-the-fact slice that manufactured the
tackles result in §5b. **It is a hypothesis to measure forward, not a filter to
apply.** Do not restrict the card by window.

## 5d. Anytime TD: tested, and closed

The largest single bucket in the diagnostics is not line mismatch — it is
one-way quotes: **49,581**, of which anytime TD is essentially all of it.
141,116 anytime-TD rows, **88.7% with no under price**, so proportional de-vig
has nothing to divide and every one of them is discarded. Every other market is
two-way in over 99.9% of rows.

That looked like the biggest opportunity on the board, and there is an
established in-repo technique for it: golf outrights are priced by renormalising
independent probabilities across a field. Anytime TD has the same shape —
Pinnacle prices a median of 16 players per game.

### The measurement that made it worth trying

Measured across 2,872 games: **4.11 distinct rush/rec TD scorers per game**.
Against that, each book's summed implied probability over its own field:

| book | summed implied | overround |
|---|---|---|
| **pinnacle** | 4.71 | **1.145** |
| espnbet | 5.22 | 1.271 |
| fanduel | 6.20 | 1.508 |
| williamhill_us | 6.42 | 1.562 |
| draftkings | 6.61 | 1.607 |
| betmgm | 6.83 | 1.662 |

That is the market-maker-vs-retail gap in its most extreme form anywhere on the
board — Pinnacle holding 14.5% against DraftKings' 60%.

### It still does not work, and the placebo says so

Field de-vig (normalise both books over the players they both price, to a common
total taken from the sharp book's own level) gives, at a 5pp threshold, +2.08%
on 747 bets. Then the placebo:

| sharp reference | bets | ROI |
|---|---|---|
| pinnacle @3pp | 2,779 | −2.43% |
| pinnacle @5pp | 747 | +2.08% |
| pinnacle @7pp | 175 | −16.87% |
| **williamhill_us** | 1,296 | **+3.24%** |
| draftkings | 1,372 | −2.71% |
| betmgm | 1,507 | −4.95% |

Pinnacle is non-monotone in the threshold, sign-flips twice, and is **beaten by
Caesars as the reference**. On the two-way rule no retail reference came close.
Here the choice of sharp book does not matter, which is the signature of no edge.

### And it is not +EV at the price either

Checking directly rather than book-versus-book — Pinnacle's field-normalised
fair probability against the break-even implied by the price actually quoted,
over 50,636 quotes with a Pinnacle counterpart:

| gate | bets | ROI |
|---|---|---|
| edge ≥ 0 | 3,873 | **−27.11%** |
| edge ≥ 2pp | 1,518 | −30.97% |
| edge ≥ 5pp | 189 | −32.80% |

**ROI gets worse as the apparent edge grows** — the exact inverse of the two-way
rule, where it rose monotonically. The mechanism is clear: proportional de-vig
assumes the overround is spread uniformly across outcomes, and on a longshot
market it is not. Favourite-longshot bias concentrates it in the long prices, so
dividing every player by the same 1.145 overstates precisely the players a
retail book prices cheapest, and the "biggest edges" are the most overstated.

**Anytime TD is closed, not unexplored.** The wider lesson is that proportional
de-vig is only defensible across two roughly symmetric sides — which is exactly
what the two-way restriction was already doing, for a reason that had not been
articulated until this failed.

### The other discarded bucket, also closed

35,272 quotes are dropped for sitting on a different number than Pinnacle, 61%
of them within a single point, and that looked like the second-largest gap.
Pricing a line difference properly needs a distribution over the stat — which is
what the twelve projection models produce, and was the most interesting
remaining idea.

It does not need one to be tested, because a subset is decidable without any
model. Where a soft book offers BOTH an easier number and at least as good a
price as the sharp book's own quote on that side, it strictly dominates a bet
already judged fair. **7,347 such quotes exist, and they grade to −0.36% over
5,173 bets** — dead flat, which is the expected result if Pinnacle's prices are
close to fair and dominance recovers only the vig.

Adding a conservative +EV bound (fair at the easier line is at least fair at the
sharp line, so `fair_sharp − breakeven(price)` is a lower bound on the true
edge) leaves **451 bets at +3.52%**, and tightening that bound to 2pp collapses
it to 38 bets at −14.36%. Non-monotone, and 451 bets at +3.5% cannot be
distinguished from zero.

So the line-mismatch bucket is not a hidden reservoir either. Together with
anytime TD, that closes both of the large discarded buckets, and it means the
remaining levers are about **breadth of books**, not cleverer treatment of the
quotes already in hand.

## 5e. The book census — what the API actually serves

Both discarded buckets are closed (§5d), so the remaining lever is breadth of
books. `--census` asks the API with no `bookmakers` param at all, so the regions
govern and the response carries everything. Read-only; it writes nothing to the
odds table and commits its answer to `data/local/book_census.json` so it never
has to be bought twice.

**14 books are served for NFL player props. We were using 6.** Outcomes over
three events, `us,us2,eu,uk`, ranked by coverage of the eight two-way markets
the rule trades:

| book | sharp-market outcomes | markets | |
|---|---|---|---|
| draftkings | 279 | 12 | have |
| **fliff** | **267** | 12 | new |
| fanduel | 261 | 11 | have |
| **fanatics** | **259** | 9 | new |
| **betparx** | **257** | 11 | new |
| **betrivers** | **257** | 11 | new |
| **bovada** | **234** | 11 | new |
| betmgm | 224 | 10 | have |
| **hardrockbet** | **201** | 11 | new |
| williamhill_us | 197 | 6 | have |
| **betonlineag** | **193** | 11 | new |
| espnbet | 186 | 11 | have |
| **ballybet** | **166** | 11 | new |
| pinnacle | 134 | 9 | have |

Four of the eight new books cover the traded markets **better than three of the
six we already use**, and every additional book is an independent chance at an
outlier, which is the mechanism the rule runs on. All eight are being backfilled
for 2023-2025.

### Two things this corrects

**Pinnacle does quote rush attempts.** §5c said it declined four markets; it
declines three — rush+rec yards, sacks and tackles+assists — and quotes rush
attempts thinly (8 outcomes here against 134 across its main markets). Thin
enough to stay out of `SHARP_MARKETS` for now, but the reason is coverage, not
absence.

**Nothing is a clean second market maker for the three it does decline.**
DraftKings has the best sacks and tackles coverage on the board, but a retail
book cannot serve as the truth reference — that is the whole construction.
`betonlineag` is the only plausible sharp-side candidate reaching sacks (36) and
tackles+assists (26), with `hardrockbet` (52 / 38) as the other option worth
testing. Whether either is actually sharp is an empirical question the placebo
answers, and it is the next thing to run after the backfill.

### The rule for switching a book on — fixed before the numbers exist

The sweep is running as this is written, and the criteria are set now so they
cannot be moved to fit the result. This is the same discipline §5 applied to the
projection models, and it exists because "add every book that looks positive" is
how a 14-book board becomes 14 chances to find noise.

A **soft** book goes into `SOFT_BOOKS` when all four hold:

1. **≥ 100 graded bets** as the only soft book. Below that the interval is wider
   than any difference between books.
2. **Not significantly negative** — the bootstrap interval may straddle zero, but
   a book whose upper bound is below zero is losing money and is excluded even
   if it adds volume. Volume is not the objective; volume at the measured edge
   is.
3. **Coverage ≥ 50% of games.** A book reaching a third of the slate contributes
   little and its ROI is mostly sampling noise.
4. **It does not degrade the pooled result** by more than its own interval
   allows, AND is not itself positive. A book can add correlated junk, but a
   book that makes money alone is not doing that. Both halves matter: a flat
   cutoff here was measured excluding a book that returned +6.6% on 260 bets
   over a 1.1pp pooled difference against a ±6pp interval — noise, not a
   finding.

**The criteria apply to books being ADDED, never to prune the incumbent five.**
The +10.33% headline IS the five-book configuration; re-deriving that set from a
rule written afterwards would quietly change the strategy away from the one
validated end to end. The sweep reports incumbents that would fail, so the
information is not hidden — ESPN BET is one, on volume — but it does not act on
them. Removing an incumbent is a separate decision needing its own evidence.

A **sharp reference** faces the bar Pinnacle actually cleared, and nothing
looser: positive at ≥ 100 bets, **positive in every season**, and **not
reproduced when a retail book is substituted for it**. The third clause is the
one that matters — it is what separated Pinnacle from price dispersion, and it
is what killed the anytime-TD field de-vig, where Caesars scored higher as the
"sharp" book than Pinnacle did.

If `betonlineag` or `hardrockbet` clears that bar, rush attempts, rush+rec yards
and sacks open up. If neither does, they are soft books at best and those three
markets stay closed — which is a result, not a gap to be filled by loosening the
bar.

**What will NOT be done regardless of the numbers:** re-cutting the 5pp
threshold, adding per-market thresholds, or filtering by kickoff window. Those
are pre-committed in §5c and the sweep is not evidence about any of them.

## 5f. Does the live card reproduce the record it is sold on?

Every number above is measured by feeding quotes straight into
`models/nfl_prop_market`. The thing that runs on Sunday is
`scripts/nfl_prop_market_card`, which reaches those same quotes through a slate
query, a started-game guard, a soft-book filter and a dedupe. Each of those is a
chance for the live board to diverge from the record, and **none of them would
raise if it did** — the symptom is a different set of bets, not an error.

`scripts/nfl_prop_replay` replays past slates THROUGH THE CARD and grades what
the card chose. Reads the committed cache, so it costs nothing.

| | bets | win% | ROI | CI | seasons |
|---|---|---|---|---|---|
| backtest path (§5c) | 954 | 57.5% | +10.33% | (+4.1, +16.3) | all positive |
| **the live card** | **981** | **57.0%** | **+9.29%** | (+3.4, +15.3) | all positive |

The card is marginally more conservative and lands inside the same interval.
That is the assurance that was missing: what will run is what was measured.

### The scheduled cadence, run through the card

`--cadence` replays the two polls the scheduler will actually make, with the
publisher's insert-once lock, over the 300 games carrying both series:

| | bets | win% | ROI |
|---|---|---|---|
| T-24h only | 184 | 53.8% | +4.71% |
| T-3h only | 198 | 51.5% | +0.76% |
| **both polls** | **372** | 53.0% | +3.39% |

**The second poll roughly doubles the bets** — 372 against ~190 for either alone
— which is the disjointness finding of §5c reproduced through the live path
rather than through raw quotes. That is the robust part and it is the whole case
for polling twice.

The absolute levels are not: every interval here spans zero, and these are the
same 300 sampled games that return +0.73% at T-3h against +12.88% for the rest
of the board. Read the doubling, not the percentages.

### Two real defects it caught first

**The card was filtering its own quotes.** The replay cutoff keyed on comparing
the supplied clock to the wall clock, and the clock is read microseconds before
that comparison — so a LIVE run compared true and silently filtered to its own
start time, dropping every quote stamped later including ones the `--fetch`
immediately before it had just stored.

**Neither loader honoured `snapshot_type`.** Timing experiments are written under
their own labels precisely so they cannot displace the pre-game series, and no
loader enforced it, so a T-24h row (stamped a day earlier, but *later* than a
T-3h row is stamped for a different game) could win "latest snapshot" and put a
stale price in front of the card **and the backtest**. It moved 435 of the
card's selections. Both loaders now default to the pre-game series.

### And one thing about the historical data worth knowing

The backfill anchors every snapshot to 17:00 UTC minus the offset, regardless of
a game's actual kickoff. **Games kicking off before 17:00 UTC — the London
games at 13:30 and 14:30 — therefore have a "T-3h" snapshot taken after they
started.** `grade()` drops those at gate 3, so the headline is not contaminated;
they simply contribute nothing. It also means a replay must tick per kickoff
rather than once per date: one clock for the whole day lets a 9:30am ET London
game pull the window back before the afternoon slate is priced, which on
2025-10-05 discarded all 3,650 quotes and every bet on the card.

## 5g. Breadth and a second market maker — both measured, neither pays

The two levers ranked highest after the closed buckets were more soft books and
a second sharp reference. All 14 books are now backfilled 2023-2025 (916,965
rows). Both answers are negative, and the first contradicts what was predicted.

### More books add volume, not money

| soft set | bets | win% | ROI | **units** |
|---|---|---|---|---|
| the current five | 954 | 57.5% | +10.33% | **+98.6** |
| the eight my criteria pass | 1,442 | 56.4% | +6.93% | **+100.0** |
| all thirteen | 1,585 | 56.0% | +6.72% | **+106.5** |

**51% more bets buy 1.4% more units.** The marginal 488 bets return **+0.29%** —
break-even. Under flat staking that is half again as much capital at risk for
nothing, so it is strictly worse risk-adjusted, and it dilutes the ROI the
strategy is judged on. **No books are being added.**

The mechanism is the dedupe. Every book is an independent chance at an outlier,
but the outliers the new books find are mostly propositions an incumbent already
offered — one opinion, kept once. What is genuinely new is what no incumbent
priced at all: thinner players, worse numbers, no edge.

**This exposes a flaw in the criteria I pre-registered, and it is disclosed
rather than quietly patched.** All four clauses test a book IN ISOLATION —
volume, sign, coverage, and whether it drags the pool while being non-positive.
Not one of them asks whether the enlarged SET earns more, which is the only
question that matters. Betrivers, Fliff and Hardrock each pass on their own and
the set they form does not. The units column is not a threshold anyone tuned; it
is the objective the exercise was for, and it was missing from the rule.

### A second market maker exists, and it does not open the closed markets

`betonlineag` clears the sharp-reference bar on the eight traded markets — **840
bets, +7.68%, positive in all three seasons**, and no retail book reproduces it
(next best is Bovada at +1.67%, and everything else is at or below zero). So the
construction is real and not specific to one book.

But it is not an upgrade and it does not buy what it was wanted for:

| sharp reference | markets | bets | ROI |
|---|---|---|---|
| pinnacle | the 8 traded | 954 | **+10.33%** |
| betonlineag | the 8 traded | 840 | +7.68% |
| betonlineag | **only the 3 Pinnacle declines** | 516 | **−4.97%** |

Rush attempts, rush+rec yards and sacks stay closed — now on evidence rather
than absence.

**That last row was nearly reported as a decisive zero.** The first extended
sweep returned "0 bets" for both references, which reads as "no edge" and means
"could not be measured": `MARKET_STAT` covered only the eight traded markets, so
every bet on the other three had no actual to grade against. `MARKET_STAT` now
covers them and the sweep **refuses** a market it cannot grade rather than
returning an empty result that looks like a finding.

### Where that leaves Week 1

Nothing changes. The configuration going live is the one that was validated:
five soft books, Pinnacle as the reference, eight markets, 5pp. Both of the
levers that looked largest are measured and closed, which is worth more than
either would have been — the remaining honest lever is features, not breadth.

## 6. What exists now, and what is still open

Built this session: schema, ingestion of the three nflverse sources into
Supabase, the feature builder, the NB/Gamma/Poisson/logistic training heads with
stored dispersion, config wiring, the scoring path, and the 12 trained models
above.

The whole chain was exercised end to end against a local Postgres replica —
migration applied, 174k player rows / 6.1k team-game rows / 277k snap rows
ingested from nflverse, features built, all 12 models trained and registered,
and week-1 2026 scoring rows produced for every market. What has NOT run against
Supabase is the migration and the backfill; those need a Supabase-reachable
machine. The trained artifacts are deliberately not committed: they must be
retrained where `model_registry` lives, which is one command per model.

Open, in order:
1. **Fix the tackles target.** It is the sport's best signal and the only market
   whose failure is ours rather than the market's. Reconcile our per-game
   tackle counts against a gamebook source; if the gap is a constant offset the
   market comes straight back, and if it is not, the target is wrong.
2. **Better features, not better thresholds.** Eleven markets lost to the hold,
   not to noise — no cut of a threshold turns −5% into +5%. Play-by-play
   red-zone share, route participation and aDOT are the next real lever.
3. Thresholds. Every NFL threshold in `config.py` today is a **placeholder** and
   is marked as such. They are not tuned and must not be treated as tuned.
   Nothing here has earned tuning yet.
4. Wiring `nfl-prop-scoring` into the daily flow — deliberately CLI-only until a
   market has cleared §5. None has.
4. Play-by-play features (red-zone share, routes, aDOT) as the next lever.

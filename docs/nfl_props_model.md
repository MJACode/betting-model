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
1. **The backtest harness** that joins model output to the collected prices
   under §5. This is now the only thing between the models and a verdict.
2. Thresholds. Every NFL threshold in `config.py` today is a **placeholder** and
   is marked as such. They are not tuned and must not be treated as tuned.
3. Wiring `nfl-prop-scoring` into the daily flow — deliberately CLI-only until a
   market has cleared §5.
4. Play-by-play features (red-zone share, routes, aDOT) as the next lever.

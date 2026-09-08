# The 2025 re-grade and the walk-forward that settled it

> **RESOLVED 2026-09-07: §5b was right.** The walk-forward at the bottom of
> this file returns **−4.32% over 1,554 bets with a 90% CI of (−8.2, −0.4)** —
> excluding zero, negative in all three seasons, on a method that FAVOURS the
> models. The 2025-only section below was underpowered, and the sentence it
> led to — "§5b does not describe these artifacts" — was wrong. Read this file
> for how that was established; act on the walk-forward.

Measured 2026-09-07. **Supersedes `docs/nfl_props_model.md` §5b for the current
models.** §5b is still correct about what it measured; it measured the artifacts
committed in #215, which turned out to be unloadable and were replaced.

## What was run

A full out-of-sample season at real prices. 2025 is the holdout for all twelve
models (trained 2015–2024), and `player_prop_odds` holds 280+ games of real
DraftKings two-way quotes for it.

- pre-game bounded (`snapshot_at <= commence_time`), `in_play` excluded
- P(over) from each model's own response distribution (`_nfl_prop_probs`)
- pushes return the stake and are dropped, never graded as losses
- bet the side clearing that model's **current** `config.py` cut
- flat 1u at the real American price
- 20,000-draw bootstrap for the interval

The cuts are not fitted to this data: `f4bd516f` set them as the top decile of
each market's **edge distribution** on a 2026 board, never swept on outcomes.

## The result

| model | bets | ROI | 90% CI |
|---|---|---|---|
| pass_attempts | 19 | +31.52% | (−0.8, +62.8) |
| pass_completions | 40 | +22.91% | (−1.0, +46.4) |
| rush_rec_yards | 67 | +4.15% | (−15.5, +23.7) |
| rush_yards | 42 | +3.92% | (−18.9, +26.7) |
| sacks | 46 | +2.40% | (−18.5, +22.6) |
| receptions | 164 | −4.55% | (−16.9, +8.2) |
| rec_yards | 118 | −8.38% | (−22.9, +6.1) |
| pass_yards | 29 | −15.15% | (−41.4, +11.1) |
| rush_attempts | 36 | −15.61% | (−41.8, +10.7) |
| **tackles_assists** | **195** | **+22.43%** | **(+12.0, +32.6)** |
| **ALL excl tackles** | **564** | **−1.18%** | **(−7.7, +5.3)** |

**Every interval straddles zero except tackles+assists.**

## The one that does not straddle zero is the one we know is broken

tackles+assists is the only model whose CI excludes zero, and it is the model
whose target is measured against the wrong ruler: our over-rate runs 7.7pp under
DraftKings' own de-vigged price across 7,228 quotes, because nflverse derives
defensive columns from play-by-play attribution while books grade off the
official gamebook (§5b, re-measured 2026-09-07).

This backtest grades against OUR counts, so it reproduces the error rather than
detecting it. **+22.43% with a tight interval is what a measurement error looks
like when you grade it against itself.** It is the strongest number in the table
and the only one that is certainly not real — which is a useful calibration on
how to read the rest.

## What this changes, and what it does not

**Changes:** §5b's "eleven of twelve are not beatable" (−0.10% to −6.19%) does
not describe these artifacts. Excluding tackles the current models grade at
−1.18%, and the interval reaches +5.3%. They are not proven losers.

**Does not change:** they are not proven winners either. Nothing here is
distinguishable from zero. A −1.18% point estimate on 564 bets is a coin flip
about the vig, not an edge.

**And it invalidates the criterion used to pause four of them on 2026-09-07.**
That pause used the gap between our P(over) and DraftKings' de-vigged number
(≤ −6pp). Of the four paused, three grade positive here (rush_yards +3.9%,
rush_rec_yards +4.2%, sacks +2.4%) and one negative (rush_attempts −15.6%) — all
straddling zero. **Distance from DraftKings did not predict ROI**, and with
hindsight it should not have been expected to: being far from the book means
either you are wrong or the book is, and only outcomes separate those. The
pause was roughly neutral rather than harmful, but it was not evidence-based and
should be re-decided on this table rather than on that one.

The reason the DK gap is not edge is visible in the same run. Against REALITY
rather than against the book, three models are near-perfectly calibrated —
receptions +0.1pp, rec_yards +1.0pp, pass_attempts +0.4pp — while DraftKings'
de-vigged price sits 2.4 to 8.1pp ABOVE the realized over-rate on nearly every
market. The book carries a real over-lean. Our models were not wrong to lean
under; they simply do not lean under in the right places often enough to clear
the hold.

## What would actually settle it

The intervals are wide because n is small: one season, 564 bets. §5b got its
bigger samples by walking forward 2021–2025, which the current artifacts cannot
do — 2015–2024 is their training data, so only 2025 is clean.

**The decisive experiment is a walk-forward re-fit**: retrain per season on
prior seasons only and grade each of 2023, 2024, 2025 at real prices. We hold DK
lines for all three (2023: 277–279 games/market, 2024: 282–283, 2025: 280–283).
That is ~3x the sample and would separate −1.18% from zero, or not.

Until that runs, the honest statement is: **the current NFL prop models are
indistinguishable from break-even, and the only confident number in the table
is an artifact of a known measurement error.**

---

## The walk-forward, 2026-09-07 — this is the answer

`scripts/nfl_prop_walkforward.py`. Weights refit per season on prior seasons
only, so 2023 and 2024 become out-of-sample too. Same prices, same cuts, same
grading as above. **Hyperparameters are reused from the shipped artifacts, which
were tuned on 2015–2024 — so this FLATTERS the models and any positive number is
an upper bound.**

| model | bets | win% | ROI | 90% CI |
|---|---|---|---|---|
| sacks | 90 | 63.3% | +8.51% | (−6.2, +22.7) |
| rush_attempts | 97 | 53.6% | +0.36% | (−15.2, +15.9) |
| rush_yards | 114 | 51.8% | −1.94% | (−16.8, +12.9) |
| pass_attempts | 60 | 51.7% | −2.20% | (−21.8, +18.0) |
| rush_rec_yards | 228 | 51.8% | −2.93% | (−13.0, +7.1) |
| receptions | 420 | 50.2% | −3.97% | (−11.6, +3.7) |
| pass_completions | 124 | 50.8% | −5.10% | (−18.8, +8.7) |
| **rec_yards** | **321** | 48.0% | **−9.54%** | **(−18.2, −0.8)** |
| pass_yards | 93 | 47.3% | −11.24% | (−27.4, +4.8) |
| **tackles_assists** | **755** | 64.9% | **+21.26%** | **(+15.9, +26.6)** |
| **ALL excl tackles** | **1,554** | 51.0% | **−4.32%** | **(−8.2, −0.4)** |

By season, excluding tackles: **2023 −1.99%, 2024 −8.95% (CI −15.3, −2.5),
2025 −1.18%.** Negative in all three.

### What it establishes

**The pooled interval excludes zero.** With three seasons instead of one, and a
method that helps them, the distributional models lose about 4.3 units per
hundred bet. §5b's −0.10% to −6.19% was right; the 2025-only read was simply
underpowered, and the wider intervals there were the honest signal that it could
not decide.

**tackles+assists is the control, and it works.** +21.26% with a CI of
(+15.9, +26.6) on 755 bets — by far the most confident number, from the one
model whose target we know is measured against the wrong ruler. Any future
result in this family that looks like that should be treated as a measurement
error until proven otherwise.

**`rec_yards` is individually confirmed losing** (−9.54%, CI excluding zero) on
the second-largest sample. It is also one of the highest-volume models live.

**No individual model is confirmed winning.** `sacks` at +8.51% is the best and
its interval spans (−6.2, +22.7).

### What it does not close

The hyperparameter leak. Closing it means 33 Optuna searches instead of 33
fits — hours rather than minutes. It is worth doing only to sharpen a positive
result, and there is no positive result to sharpen: the leak runs in the models'
favour and they still lose.

---

## anytime_td, graded at last — the twelfth model

Both backtests above silently omitted it. They require a two-way DraftKings
quote so the price can be de-vigged, and anytime TD is **one-sided**: §5d
measured 141,116 rows, 88.7% with no under price. So it sat live and unmeasured,
the only one of the twelve never graded either way.
`scripts/nfl_anytime_td_grade.py` closes that.

Same walk-forward: weights refit per season on prior seasons only, 2023–2025,
real pre-game DraftKings prices. **7,931 quoted player-games.**

| | |
|---|---|
| actual TD rate | **28.6%** |
| our mean P | 26.9% |
| DK implied (vig included) | 31.9% |

The model is close to reality — 1.7pp under, better calibrated than most of the
family. **The book's margin is the +3.2pp gap between its price and the truth**,
and on a 28.6% base rate that margin is 11% of the probability itself. This is
the most heavily juiced market on the board.

| min edge | bets | win% | ROI | 90% CI |
|---|---|---|---|---|
| 2pp | 127 | 33.1% | −9.01% | (−28.1, +10.7) |
| 5pp | 57 | 29.8% | −10.70% | (−40.5, +20.4) |
| 8pp | 24 | 20.8% | −25.62% | (−72.9, +27.7) |
| **16pp (current cut)** | **5** | — | — | — |

### The verdict is "inert", not "losing"

At its live cut — p ≥ 0.37 and edge ≥ 0.16 — it fired **five times in three
seasons**: 0 in 2023, 2 in 2024, 3 in 2025. The cut demands a 16pp edge on a
market whose base rate is 28.6%, i.e. the model must believe 44%+ where the book
prices 28%. That essentially never happens honestly.

So it is not costing anything, and it is not contributing anything. Loosening it
is what would cost: every cut with a usable sample is negative, which is what a
3.2pp margin on a 28.6% event does to a well-calibrated model.

**All twelve NFL prop models are now measured.** Ten lose, one (`tackles_assists`)
is a measurement error, and this one does nothing.

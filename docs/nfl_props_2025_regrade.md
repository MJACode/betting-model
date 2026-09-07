# The 2025 re-grade: §5b's verdict was about artifacts that no longer exist

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

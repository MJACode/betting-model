# When to read the board: near kickoff is the only well-evidenced regime

*Measured 2026-09-08. The rule is `models/nfl_prop_market`; the grader is
`scripts/nfl_prop_two_sharps.py`.*

## The finding

The market-relative rule's edge is **near kickoff**, and the near-kickoff board
is the only offset that is positive in all three seasons with a confidence
interval excluding zero.

Paired on the 649 games carrying a T-72h board — same seasons, same 5pp cut, one
bet per proposition, both references at every offset, the offset the only thing
that differs:

| board | median lead | bets | ROI (`either`) | 90% CI | pinnacle only |
|---|---|---|---|---|---|
| **`open`** | **~7 h** | 586 | **+10.75%** | **(+4.2, +17.3)** | +11.07% |
| `t24` | 24 h | 191 | +5.01% | (−6.9, +16.7) | +5.01% |
| `t48` | 48 h | 1741 | +0.65% | (−3.2, +4.6) | −0.77% |
| `t72` | 72 h | 1083 | +4.54% | (−0.4, +9.5) | **+6.35% (+1.0, +11.7)** |

**THE DECAY IS NOT MONOTONE, and that is the honest shape of it.** T-72h beats
T-48h on both the pooled number and the pinnacle-only arm, where its interval
also excludes zero. An earlier version of this document read the first three
rows as a smooth gradient and argued from it that a 10-day-out board must be
worse still. It cannot: 48 h is a trough, not a floor, and nothing here licenses
extrapolating past 72 h. What the table supports is narrower and still useful —
**`open` is the best-evidenced regime by a clear margin**, and it is the only
row that clears the bar on every test below.

**`open` is not the opening line.** For 2023-2025 it is not polling either:
those rows come from `backfill_nfl_prop_odds`, which anchors at a FIXED
`17:00 UTC` minus `hours_before=3`. Every graded sharp quote in those seasons
sits at **one clock time — 13:55 UTC, 9:55 a.m. ET**, one distinct value per
season. The measured edge has a time of day attached to it, not just a lead
time. The 2026 rows in the same series are live production polling at 51
distinct times, 46-190 h out — a different animal that shares a label.

| snapshot_type | rows | min | p10 | median | p90 | max |
|---|---|---|---|---|---|---|
| `open` (2023-25) | 101,573 | −0.4 h | 3.1 h | **~7 h** | 31.2 h | 36.1 h |
| `open` (2026) | 20,473 | 45.9 h | 70.2 h | 138.0 h | 157.0 h | 190.1 h |
| `t24` | 11,539 | 1.1 h | 21.6 h | 24.1 h | 25.1 h | 56.1 h |
| `t48` | 61,150 | 20.6 h | 24.1 h | 48.1 h | 56.1 h | 80.4 h |

`PREGAME_SNAPSHOT_TYPES = ("open",)` — the production scorer reads this series.

### The mechanism, and where it stops explaining things

Near kickoff the sharp number has settled, so a soft book still disagreeing with
it is holding a genuinely stale price and the disagreement is the edge. That
accounts for `open` being the strongest row, and it accounts for T-48h being
weak: two days out both books are still moving, so a gap between them is mostly
noise that resolves before anyone could collect.

**It does not account for T-72h beating T-48h**, and this document should not
pretend otherwise. Three readings are consistent with the table and are not
separated by the data in hand:

  * T-72h is genuinely different — an early board with thin two-way coverage,
    where a soft book that has bothered to post at all is posting a number it
    has not thought hard about.
  * T-48h has a composition problem: it carries the most bets of any offset
    (1,741 paired) and the weakest 2023 (−4.7% over 761), so a single bad season
    on a board that is disproportionately 2023 could be most of the trough.
  * It is noise. At these interval widths T-48h (−3.2, +4.6) and T-72h
    (−0.4, +9.5) overlap heavily, and neither excludes the other's point
    estimate.

The honest summary is that ONE offset clears every bar — `open` — and the shape
between 24 h and 72 h is not resolved. Anyone tempted to build a lead-time curve
out of these four rows should get more offsets first, not interpolate these.

## What it does NOT say

- **It does not support a smooth decay argument about the 240-hour window.**
  `NFL_PROP_WINDOW_HOURS` was widened 30 → 240 on 2026-09-07. There is no
  measurement at 240 h, and because T-72h beats T-48h the curve cannot be
  extrapolated there. What IS measured: `open` (~7 h) is the best regime by a
  clear margin, and every NFL prop BET written in the 21 days to 2026-09-08 was
  taken past 48 h — `nfl_prop_market`'s three at 137.6-179.8 h — which under the
  §1c first-signal lock makes them permanent at a lead time carrying no positive
  evidence either way. That is an argument for scoring nearer kickoff, not an
  argument that 240 h is worse than 48 h. **mike's call; he set 240
  deliberately.**
- **It does not re-open the credit question.** The window governs which games
  get a card fetched, not what a bet costs.

## The validation

Held to the `.claude/rules/analysis-and-thresholds.md` bar.

**Plateau, not a peak** — ROI rises monotonically with the cut and thins out
after, rather than spiking in one cell (`either`, `open`):

| cut | 3% | 4% | 5% | 6% | 7% | 8% |
|---|---|---|---|---|---|---|
| bets | 2815 | 1411 | 648 | 206 | 53 | 16 |
| ROI | +2.46% | +4.31% | +9.83% | +12.15% | +7.05% | — |

5% is the operating point: the highest cut with a CI excluding zero and every
season positive. 6% is higher still but 206 bets and 2023 negative.

**Time split** — positive in all three seasons at the 5pp cut, which is the test
that killed every situational NCAAF edge.

**The placebo** — swap the two sharp references for retail pairs and grade
identically. A reference is never also bet, so the sets stay disjoint:

| reference pair | bets | ROI | 90% CI | seasons |
|---|---|---|---|---|
| **pinnacle + betonlineag** | 648 | **+9.83%** | **(+3.6, +16.0)** | **all 3 positive** |
| betmgm + espnbet | 340 | +5.95% | (−3.1, +15.0) | 2025-driven |
| williamhill_us + betrivers | 290 | +0.78% | (−9.0, +10.6) | mixed |
| fliff + hardrockbet | 363 | −0.23% | (−9.1, +8.5) | mixed |
| draftkings + fanduel | 368 | −4.86% | (−13.6, +3.8) | mixed |

Only the sharp pair has a CI excluding zero and no losing season. The signal is
specific to the reference, which is what separates it from the sample.

## Reproducing it

```bash
python -m scripts.nfl_prop_two_sharps --min-edge 0.05 --snapshot open
python -m scripts.nfl_prop_two_sharps --min-edge 0.05 --snapshot t48 \
       --only-games-with t48                      # the paired arm
python -m scripts.nfl_prop_two_sharps --min-edge 0.05 --snapshot open \
       --refs betmgm,espnbet                      # the placebo
```

`--snapshot` is load-bearing. Without it the grader takes the newest pre-game
quote of ANY type, and which type that is varies by season: 2023 sharp quotes
were `open` until the T-48h backfill landed, after which they became `t48`. That
confounds the season split with the offset — a season row then answers "which
year" and "measured how far out" at once. It is also what made the pooled number
fall from +6.89% to +2.20% when the backfill arrived, which looked like the rule
weakening and was really two offsets being averaged.

## College football: tested, and the answer is no

The same rule on the NCAAF 2025 prop season (38,979 credits, 541 events,
72,848 rows) — `scripts/ncaaf_prop_market_sweep.py`:

- **The placebo fails.** At the 5pp cut betonlineag ranks 2nd of 6 references
  (+8.31%, 52 bets) behind hardrockbet, a retail book (+13.16%, 114 bets); at
  2pp it ranks 4th of 7. Nothing distinguishes the sharp reference.
- **The board cannot support the test.** Pinnacle covers 59 of 483 games, so
  betonlineag must carry the reference role alone. DraftKings and betrivers post
  no two-way college quotes at all and cannot be de-vigged or bet.
- **More seasons will not fix it.** One season yields ~50 bets at the 5pp cut;
  SE on ROI there is ~9pp. Three seasons gets to ~7pp, and resolving a +8% edge
  needs roughly 1,000 bets — many more seasons than the endpoint sells.

**Do not buy 2023–24 NCAAF props.** The credits already spent bought a clean
negative, which is the answer they were spent to get.

## A construction that does not work, so nobody rebuilds it

The equal-line requirement discards a lot of board: 63,676 NFL propositions
where a sharp and a soft book both quote two-way but at different numbers (on
NCAAF it is 65% of the comparable board). Monotonicity recovers some of that
without any model — for a soft OVER at a line *lower* than the sharp's, the
sharp's de-vigged over-probability is a strict lower bound on the true one, so
the measured edge is conservative and real.

**Yield: 12 bets at 5pp, 26 at 4pp, 61 at 3pp, out of 63,676 propositions.**
Half-point lines only, since on an integer line the de-vigged probabilities are
conditional on "no push at *that* line" and monotonicity across two different
push events is not strict.

The bound *ignores* the line gap rather than harvesting it, so it fires only on
a double mispricing — the soft book pricing its easier number cheaper than the
sharp prices its harder one. That is rare, and the yield is the measurement of
how rare. The next rung, not attempted, is an empirical per-market slope dP/dL
estimated from the sharp book's own (line, fair-probability) pairs — prices
only, no outcomes, so still market-relative rather than projection modelling.

# When to read the board: near kickoff is the only well-evidenced regime

*Measured 2026-09-08. The rule is `models/nfl_prop_market`; the grader is
`scripts/nfl_prop_two_sharps.py`.*

> **CORRECTED 2026-09-11 — the grader behind every table below was dropping
> the near-kickoff quotes it claimed to measure.** `scripts/nfl_prop_two_sharps.py`
> bounded pre-game quotes with `str(snapshot_at) > str(kickoff)`: the snapshot is
> an ISO string with a `T` separator, the kickoff a pandas Timestamp whose `str()`
> has a space, and `'T'` sorts after `' '`. So every quote taken on the SAME UTC
> DATE as the kickoff read as post-kickoff and was silently excluded — which is
> every Sunday-afternoon game read on Sunday morning, the whole 3-7h band the
> `open` series is described by. Measured before the fix: **zero** selected bets
> under 8h, against a series whose lead p10 is 3.1h at every one of 15 books. What
> the tables below had actually measured as "near kickoff" was night games at ~10h
> and Sunday games read on **Saturday** at 28-36h. The fix compares timestamps.
> Corrected numbers are in the section directly below; the original tables are
> kept underneath, struck through in spirit — read them as "what the buggy
> grader saw".

## The corrected finding (2026-09-11)

Same rule, same 5pp cut, same one-bet-per-proposition grading, same soft books,
with the pre-game bound fixed. Session 281.

**Headline, `open` series 2023-25, all games** (`--snapshot open`):

| selection | bets | win% | units | ROI | 90% CI | by season |
|---|---|---|---|---|---|---|
| pinnacle | 1,425 | 56.4% | +109.8 | +7.70% | (+3.5, +11.8) | +8.5 / +5.3 / +8.4 |
| betonlineag | 756 | 55.8% | +73.1 | +9.67% | (+3.7, +15.6) | +2.1 / +11.0 / +17.3 |
| **either** | **1,990** | **56.0%** | **+155.9** | **+7.84%** | **(+4.3, +11.4)** | **+6.4 / +8.2 / +10.1** |
| BOTH | 184 | 57.1% | +21.2 | +11.50% | (−0.4, +23.4) | +5.1 / +3.9 / +29.2 |
| placebo: draftkings + fanduel as the references | 1,086 | 51.6% | +14.7 | +1.35% | (−3.6, +6.3) | −3.6 / −1.0 / +8.1 |

Three times the bets the buggy grader saw (623 → 1,990), a lower ROI (+10.19%
→ +7.84%), a tighter interval that still excludes zero, every season positive,
and a retail placebo that fails as it should. **The edge survives the fix and is
better evidenced than before.** The +9.83% / 648 and +10.75% / 586 figures below
should not be quoted again.

**The same `open` bets split by the bet's own lead** (`--by-lead`, `either`):

| lead band | which games these are | bets | ROI | 90% CI | seasons |
|---|---|---|---|---|---|
| 0-4 h | Sunday 1 pm ET games read Sunday 9:55 am ET | 450 | +2.96% | (−4.6, +10.6) | +5.0 / **−4.5** / +5.7 |
| **4-8 h** | Sunday 4 pm ET games read Sunday morning | **971** | **+9.30%** | **(+4.2, +14.3)** | **+8.2 / +7.5 / +13.9** |
| 8-12 h | Thursday / Sunday / Monday night games read that morning | 394 | +5.60% | (−2.4, +13.6) | +1.8 / +13.6 / +2.2 |
| 12-24 h | — | 2 | thin | | |
| **24-48 h** | Sunday games read **Saturday** morning; Monday night read Sunday | **173** | **+17.45%** | **(+5.5, +29.2)** | **+9.6 / +26.1 / +23.4** |

The band is a kickoff-slot label as much as a lead-time label, because the
2023-25 series is one snapshot per game at 13:55 UTC; read it as both.

**The paired offset table, corrected** (`--only-games-with t72`, `either`):

| board | median lead | bets | ROI | 90% CI | seasons |
|---|---|---|---|---|---|
| **`open`** | 3-36 h (mass at 3-11 h) | **1,915** | **+7.61%** | **(+3.9, +11.2)** | **+6.0 / +7.7 / +10.5** |
| `t24` | 24 h | 187 | +2.12% | (−9.9, +14.1) | — / −4.3 / +7.7 |
| `t48` | 48 h | 1,629 | −0.51% | (−4.4, +3.5) | −5.9 / +0.2 / +6.5 |
| `t72` | 72 h | 1,030 | +4.52% | (−0.5, +9.5) | +5.1 / +0.2 / +6.5 |

### What it says about the ceiling (mike, 2026-09-11: "Market model window should be tighter then, closer to kickoff to where the real edge lives")

The data does not support tightening. Read the lead bands:

- **The last four hours are the WEAKEST band** — +2.96%, interval spanning zero,
  2024 negative. By Sunday morning the soft books have caught up to Pinnacle on
  the 1 pm games; there is less staleness left to sell.
- **4-8 h is the best-evidenced band** (971 bets, +9.30%, CI clear of zero,
  every season positive). A 12 h ceiling would keep it; a 4 h ceiling would
  throw it away and keep the weakest band.
- **The Saturday-morning read of Sunday games is the strongest band of all**
  (+17.45% on 173, CI clear of zero, every season positive), and the current
  24 h ceiling EXCLUDES it. Against that, the separate `t24` series (a backfill
  at ~24.1 h, i.e. Saturday ~1 pm ET) is only +2.12% on 187 bets across two
  seasons, and `t48` is flat. So between 24 h and 48 h the evidence is: strong at
  28-31 h, weak at 24 h, nothing at 48 h — adjacent readings that disagree, on
  173 and 187 bets. Not resolved.

What this licenses: **do not tighten below 24 h.** Whether to *widen* to 36 h to
capture the Saturday-morning band is a real question with real evidence on both
sides, and under the first-signal lock with hourly polling a 36 h ceiling would
lock Sunday games on Saturday morning, exactly where the +17.45% was measured.
That is mike's call; nothing was changed.

---

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

## What shipped (2026-09-08, mike: "do it")

A CEILING on how early a prop pick may be written, separate from the window that
governs how far ahead the board is bought:

| constant | value | governs |
|---|---|---|
| `NFL_PROP_WINDOW_HOURS` | 240 | how far ahead we **buy** the board |
| `NFL_PROP_MAX_LEAD_HOURS` | **24** | how close to kickoff a pick may be **written** |

Buying early is free information; betting early is not. The card had a
started-game FLOOR and no ceiling, which is why every NFL prop BET in the 21
days to 2026-09-08 was taken past 48h and `nfl_prop_market`'s three at
137.6-179.8h — five to seven days out, against a record measured entirely
inside 36h. A game beyond the ceiling is SKIPPED, never dropped: it returns on a
later hourly tick, and no pick is deleted or re-priced, so the §1c lock is
untouched.

**The scorer path got the same ceiling on 2026-09-11** (mike: "we revised
prop models or should have, that was my earlier guidance"). #610 put it on
`scripts/nfl_prop_market_card.py` only; the eleven `nfl_prop_*` models are
written by `models/scorer.run_nfl_prop_scorer`, which kept the floor and no
ceiling and wrote seventeen Week-1 picks five to six days out on 2026-09-07.
`scorer._nfl_prop_too_early` now reads the SAME constant, sits between the
started-game floor and the price read, and skips rather than deletes.
`tests/test_nfl_prop_scorer_lead_ceiling.py` pins the constant, the boundary
and the wiring.

**24 rather than 36**: 36.1h is the measured *maximum* of the `open` series, and
gating there would put the first-signal lock in the tail rather than near the
mass (median ~7h). 12 would be closer to the median and cost volume; that trade
wants its own measurement rather than a guess.

**Assessed against the other models** (§1b), and deliberately NOT applied to
them: the eleven distributional `nfl_prop_*` models score off the same board and
are also writing bets 133-150h out, but their problem is not lead time — they
return "NOT BEATABLE, CI includes zero" at every offset, so a ceiling would
change the volume of a losing lane rather than fix it. Their record is in the
table below.

## The eleven distributional models, for comparison

Backtested 2023-25 at each model's own live cut, one flat unit per bet:

| model | bets | ROI | units | verdict |
|---|---|---|---|---|
| nfl_prop_anytime_td | 12 | −17.90% | −2.15 | not beatable |
| nfl_prop_pass_yards | 145 | −14.90% | −21.60 | not beatable |
| nfl_prop_pass_completions | 199 | −5.29% | −10.53 | not beatable |
| nfl_prop_rush_yards | 176 | −4.80% | −8.44 | not beatable |
| nfl_prop_pass_attempts | 82 | −2.91% | −2.39 | not beatable |
| nfl_prop_rush_rec_yards | 280 | −1.56% | −4.37 | not beatable |
| nfl_prop_receptions | 553 | −1.12% | −6.21 | not beatable |
| nfl_prop_rec_yards | 348 | +0.57% | +2.00 | not beatable |
| nfl_prop_rush_attempts | 225 | +3.61% | +8.12 | not beatable |
| nfl_prop_sacks | 102 | +3.63% | +3.70 | not beatable |
| nfl_prop_pass_tds | 11 | +12.22% | +1.34 | not beatable |
| **total** | **2,133** | **−1.90%** | **−40.53u** | ≈ −13.5u/season |

Every one carries a confidence interval spanning zero. `nfl_prop_tackles_assists`
is excluded and paused: it shows +24.89% and +197.38u, and the backtest itself
rejects it — *"our actual lands over the line 41.5% of the time, the book's own
de-vigged price says 50.2%. That −8.7pp gap is a different stat, not an edge."*

Against all of that, `nfl_prop_market` returns **+63.7u over 648 bets (+9.83%)**,
≈ +21u/season — the only NFL prop model whose interval excludes zero.

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

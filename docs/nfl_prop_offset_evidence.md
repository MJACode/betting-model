# When to read the board: the market-relative rule decays with lead time

*Measured 2026-09-08. The rule is `models/nfl_prop_market`; the grader is
`scripts/nfl_prop_two_sharps.py`.*

## The finding

The market-relative rule's edge is **near kickoff**. It is gone 48 hours out.

Paired on the 433 games that carry both boards, same seasons, same 5pp cut, one
bet per proposition — the offset is the only thing that differs:

| board | median lead | bets | win% | units | ROI | 90% CI |
|---|---|---|---|---|---|---|
| `open` (production poll) | **7.5 h** | 379 | 57.3% | +35.69 | **+9.42%** | **(+1.3, +17.4)** |
| `t48` (backfill) | 48.1 h | 996 | 50.6% | −28.76 | −2.89% | (−7.9, +2.1) |

Unpaired, across every game each board covers, the same split holds — `open`
+9.83% over 648 bets, CI (+3.6, +16.0), positive in all three seasons
(2023 +7.6%, 2024 +11.6%, 2025 +12.1%); `t48` −2.89%. The T-24h board sits
between them at +3.92% over 193 bets, CI (−7.6, +15.7) — too thin to place.

**`open` is not the opening line.** It is the routine production polling series,
and its distribution against kickoff is the whole point:

| snapshot_type | rows | min | p10 | median | p90 | max |
|---|---|---|---|---|---|---|
| `open` | 122,046 | −0.4 h | 3.1 h | **7.5 h** | 134.8 h | 190.1 h |
| `t24` | 11,539 | 1.1 h | 21.6 h | 24.1 h | 25.1 h | 56.1 h |
| `t48` | 61,150 | 20.6 h | 24.1 h | 48.1 h | 56.1 h | 80.4 h |

The grader takes the newest pre-game quote, so on the `open` series it is
reading a price a few hours before kickoff. `PREGAME_SNAPSHOT_TYPES = ("open",)`
— this is exactly what production reads.

### Why this is the expected direction, not a surprise

Near kickoff the sharp number has settled. A soft book still disagreeing with it
at that point is holding a genuinely stale price, and the disagreement is the
edge. Two days out both books are still moving, so a gap between them is mostly
noise that resolves on its own before anyone could have collected.

## What it does NOT say

- **It does not say fire earlier.** It says the opposite, and that bears
  directly on `NFL_PROP_WINDOW_HOURS`, widened 30 → 240 on 2026-09-07. There is
  no measurement at 240 h; the measured gradient runs 48 h negative → 24 h
  ambiguous → ~7 h strongly positive, and extrapolating it puts a 10-day-out
  board worse than the 48-hour one. Under the §1c first-signal lock a pick taken
  at 240 h is permanent, so a wide window locks picks at the lead time with the
  least evidence behind it. **This is a decision for mike, not a change to make
  quietly** — he set 240 deliberately.
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

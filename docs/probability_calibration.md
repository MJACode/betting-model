# Probability calibration — what the models claim vs what happens

> `models/probability_calibration.py`. Fitted daily by pipeline step
> `calibration-fit`; surfaced on pick detail and in the monitor dashboard.

## The finding

Measured 2026-08-30 over the full graded universe (`mv_scored_pick_outcomes` —
BET + AVOID + dead zone, per CLAUDE.md §7), at the probabilities actually bet
(≥0.60), scoped to each model's own active version:

| model | claims | wins | gap |
|---|---|---|---|
| `mlb_prop_pitcher_hits` | 65.8% | 49.6% | **+16.2pp** |
| `wnba_prop_player_points` | 66.5% | 51.5% | +15.0pp |
| `wnba_prop_player_pra` | 66.8% | 54.4% | +12.4pp |
| `mlb_moneyline` | 65.9% | 55.3% | +10.5pp |
| `mlb_prop_pitcher_k` | 67.1% | 59.2% | +7.8pp |
| `mlb_prop_batter_rbi` | 68.6% | 74.7% | **−6.0pp** |

**Twelve models are 6–16pp overconfident; one is under.** It is not a sport, a
market or a model type — it tracks SAMPLE SIZE. The four best-calibrated models
are the four with thousands of graded picks.

## Why it is a map and not a retrain

The same measurement on `mlb_live_total_runs` by season:

| seasons | in/out of sample | gap |
|---|---|---|
| 2022–24 | **in** sample | −2 to −3pp (well calibrated) |
| 2025 | out | +9 to +10pp |
| 2026 | out | +7 to +13pp |

A model fits its training seasons more tightly than any season it has not seen,
and **every live pick is made out of sample**. Retraining moves the boundary,
not the behaviour: 2027 would look exactly like 2025 and 2026 do now. Note also
that the model's POINT estimate is nearly unbiased (−0.072 runs per state on
2026) — what is wrong is turning it into a probability.

## Phase 1 (shipped): stamped, published, not decided on

`picks.model_probability_cal` is stamped at score time — one choke point,
`_insert_picks`, covering pre-game, MLB live and NCAAF live. **The decision path
is untouched**: `edge`, BET/AVOID, Kelly and every threshold still run on the
raw probability.

That is necessity, not caution. `mlb_moneyline`'s cut is 0.72 claimed, which maps
to ~0.62; applying calibration to the decision without re-cutting the thresholds
would take it from ~2 picks a week to none. Every cut in `config.py` was swept on
raw probabilities. Same phasing as `best_line`.

**Phase 2** — re-sweep thresholds on calibrated probabilities and flip the
decision. A model update under §1b: needs a person's call and `Updated-By`.

## What gets published, and what gets refused

A map is applied **only where it demonstrably helps on picks it was not fitted
on** (fit the older half, measure the newer half, compare against leaving it
raw):

**Applied (10):** `pitcher_hits` 12.9→1.3pp, `wnba_points` 10.7→1.5,
`batter_rbi` 7.1→0.7, `pitcher_er` 7.4→1.2, `pitcher_k` 6.8→2.6,
`wnba_rebounds` 6.0→1.8, `wnba_threes` 3.2→1.0, `batter_tb`, `batter_walks`,
`batter_runs`.

**Refused — the map made the held-out half worse:** `mlb_moneyline`,
`mlb_f5_moneyline`, `pitcher_outs`, `pitcher_walks`, `wnba_pra`,
`wnba_assists`, `batter_hits`.

**Refused — too few graded picks in the current era:** `mlb_over_under` (58),
`mlb_runline` (18), `wnba_moneyline` (111).

## Load-bearing design decisions

- **Platt on logits, two parameters** — several models have only a few hundred
  graded picks and the gap is smooth in confidence. Isotonic would fit the tail.
- **Symmetric**: fitted on the preferred side, the other defined as
  `1 − f(1−p)`, or a prop's over and under would not sum to 1.
- **Scoped to the active version.** A map fitted across a version swap describes
  a blend of the live model and its dead predecessor — that alone moved
  `batter_tb` from +4.6pp to +1.2pp and `batter_hits` from +3.2pp to +0.2pp.
- **Documented contamination excluded**: `mlb_over_under` before the NaN-line
  fix and `mlb_runline` before the frozen-bullpen catch-up, both from 07-05.
- **Clean `NONE`-row windows only** (§7 trap 2).
- **Refuses below 150 graded picks.** A map from 40 points is a map of 40 points.
- **`applied` is a COLUMN, not a JSON `LIKE`.** The first version matched
  `payload LIKE '%"applied": true%'` — and `data.db` passes params to psycopg2
  whenever they are not None, an empty tuple included, so a literal `%` becomes
  a format placeholder, the query raises, and `monitoring/store._rows` swallows
  it and returns `[]`. The dashboard silently showed every model as unmapped.

## The go-live gate, which never caught any of this

`_mean_calibration_error` averages absolute error across bins **unweighted** — a
20-sample bin counts as much as a 5,000-sample one — and **across the whole
probability range**, where the mass sits near 0.5 and the models are fine. The
bins that get bet are a small minority and their error is diluted away.

Worse, for Poisson models it was not measuring a probability at all.
`_poisson_calibration_error` checks the COUNT fit; the scorer bets
`P(over) = Poisson tail at the live line`, a serve-time transformation training
never evaluated. `mlb_live_total_runs` shipped on `calibration_score = 0.4846`,
a runs-scale number that cannot be compared to a 5% gate.

Run properly on its own 2025 holdout, 287,334 priced states:

```
legacy cal_error                : 0.0882   FAIL
cal_error_weighted              : 0.0961   FAIL
cal_error_actionable (p >= 0.70): 0.0975   FAIL
```

**The gate did not pass a bad number; it never computed one.**

Added as NEW registry fields — `cal_error` is left untouched so historical rows
keep their meaning:

- `cal_error_weighted` — sample-weighted ECE.
- `cal_error_actionable` — weighted, restricted to `p >=` the model's own
  `MODEL_PROB_THRESHOLDS` entry. The one that decides.
- `poisson_probability_metrics()` — the same three on the DERIVED probability,
  wired into live Poisson training, which logs an ERROR when it fails the 5%
  gate.

Forward half: the `model_calibration` health check measures the LIVE graded
record per model (WARN at 5pp, CRIT at 8pp, n≥150), because a training-time
metric cannot see drift after shipping.

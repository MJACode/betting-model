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

### 2026-09-14 — two CRITs, two different problems (mike)

Health check predicates (decision probability ≥ 0.60, later of version/promotion
date, ≥150 graded):

| model | n | claimed | realised | gap | regime |
|---|---|---|---|---|---|
| `mlb_prop_batter_runs` | 392 | 72.37% | 61.22% | **+11.14pp** | promoted 2026-09-07 |
| `mlb_prop_pitcher_er` | 414 | 66.62% | 55.56% | **+11.06pp** | version 2026-05-13 (no promoted map) |

**batter_runs was the map, not the model.** On the same window, RAW p≥0.60 is
+0.98pp / 251 (65.92% claimed, 64.94% realised). The 09-07 promoted map
(a=1.138, b=0.377) inflates stamped `model_probability_cal` by ~10pp on the
09-04 version, which is already calibrated. Today's candidate (a=1.106, b=0.012,
n=571, era_from 2026-09-04) helps and transfers (1.79→0.42pp). Re-promoted via
worker job `promote-batter-runs-map-2026-09-14`. After that job lands, the
health-check window resets at the new `promoted_at`; it will SKIP until 150
post-regime graded picks accrue (skip budget 45 days). Counterfactual on the
09-08..09-13 window: candidate cal p≥0.60 is +3.11pp / 289.

**pitcher_er is the gate working.** `applied=true` is `helps` alone. Promotion
requires `helps AND transfers`. The 09-14 candidate helps (12.33→6.28pp) and
does not close (6.28 > 6.0). `promoted_at` is set with `promoted=false` because
`demote()` writes the timestamp; it was never in the decision path. A fit on
the current clean window only (08-09+, n=353) is worse on transfer
(13.39→9.34pp), so shrinking `era_from` is not a path. Monthly raw gaps at
p≥0.60: May +6.9 / June +19.8 / Aug +8.8 / Sep +16.1 — the gap is not stable
enough to map. Do not lower `MAX_TRANSFER_GAP_PP`. Do not pause. Do not
tighten `ACTION_THRESHOLDS`. Re-check when a nightly fit reports
`transfers=true`.

The health check now appends an eligibility clause for every flagged model
(re-promote / not eligible / candidate not yet promoted) so these two stop
reading as the same failure.

---

## Phase 2 — the map decides (mike, 2026-08-31)

`config.DECIDE_ON_CALIBRATED_PROB` (default on) makes `models/scorer._make_pick`
compute the BET/AVOID call from the **calibrated** probability:
`edge = calibrated_prob − dk_implied_prob`, with the probability floor applied
to the calibrated number too. The **stored** `picks.edge` and
`picks.model_probability` stay RAW so every historical comparison and every past
threshold sweep remains readable; the calibrated number rides alongside in
`picks.model_probability_cal`.

**A model with no PROMOTED map calibrates to itself**, so this is a no-op for it.
That gate is what keeps the change from re-cutting all ~70 models at once.

### The map was inert in production, and why

`model_calibration` in production had `applied` but **not** `promoted`,
`promoted_a`, `promoted_b`, `promoted_at`. `load_calibrations()` therefore hit
its own except-branch on every call and returned `{}` — so
`model_probability_cal` equalled the raw probability on all 583 picks carrying
it, and the map was doing nothing at all while looking installed.

The cause was in `persist()`: its `LOCKDOWN` and `ADD COLUMN` statements were
each wrapped in `try/except: pass` **without a rollback**. A failed statement
poisons a Postgres transaction, so one failing LOCKDOWN statement silently made
every column ALTER below it fail too. Same hazard the rollback in
`load_calibrations()` already documented. Fixed.

### Measured impact of promoting — READ THIS BEFORE RUNNING `--promote`

Ten models have an endorsed (`applied`) map. Replaying every settled BET they
have ever produced through their own Platt map against their **current**
thresholds:

| model | bets now | after | kept | ROI now | ROI after |
|---|---|---|---|---|---|
| mlb_prop_batter_runs | 393 | 19 | 5% | −3.67% | −7.61% |
| mlb_prop_batter_walks | 371 | 80 | 22% | −1.69% | −2.63% |
| mlb_prop_batter_rbi | 290 | 98 | 34% | −2.10% | −8.47% |
| wnba_prop_player_rebounds | 224 | 2 | 1% | −7.02% | −35.30% |
| wnba_prop_player_points | 216 | 0 | 0% | −7.23% | — |
| mlb_prop_pitcher_k | 188 | 7 | 4% | −1.58% | −34.67% |
| mlb_prop_batter_tb | 152 | 2 | 1% | −11.14% | −39.01% |
| mlb_prop_pitcher_er | 124 | 1 | 1% | −8.14% | +83.33% |
| wnba_prop_player_threes | 80 | 40 | 50% | −22.59% | −20.74% |
| mlb_prop_pitcher_hits | 65 | 0 | 0% | −27.93% | — |

**2,103 bets → 249 (12% kept), and ROI gets WORSE in seven of ten.**

That is not an argument against calibration — it is the arithmetic of applying
a calibrated probability to a threshold that was swept on a raw one. Shrinking
every probability by ~10pp while leaving `min_edge` where it is does not select
a better subset, it selects an arbitrary one. The single "improvement"
(`mlb_prop_pitcher_er`, +83%) is one bet.

**So the maps are deliberately NOT promoted.** The plumbing is in and tested;
promotion is one command (`python -m models.probability_calibration --promote`)
and must be preceded by re-sweeping `MODEL_EDGE_THRESHOLDS` /
`MODEL_PROB_THRESHOLDS` on calibrated probabilities —
`scripts/calibrated_threshold_sweep.py` already exists for exactly that.

## Phase 3 — every model decides on an honest number, and one EV floor selects (mike, 2026-09-19)

mike, after a live NCAAF total and a flood of NFL prop unders on the same
afternoon: *"I want only best of the best in terms of expected value ... these
should not be a volume models it should be a best big bet models."* Not a pick
count — he rejected a top-N the same day — a bar. Two changes, one PR
(`Updated-By: mike`):

1. **Every model carries a map that decides.** The two-parameter Platt fit
   above needs 150 graded picks and a held-out gap under 6pp, and the models
   that overclaim MOST can never clear it: a live model's evidence is one BET
   band above its own floor, a rule has a few dozen settled bets, a new model
   has none. Under phase 2 those kept deciding on the raw claim —
   `ncaaf_live_total` claiming 69.8% and delivering 52.0% over 98 bets,
   `mlb_live_total_runs` 73.0% vs 59.7% over 144 (measured 2026-09-19). So the
   fit is **tiered** (`fit_model`):
   - **Platt** where the record carries it (≥150, helps AND transfers): batter_runs,
     batter_tb, pitcher_walks, runline, four WNBA props — unchanged.
   - **A one-parameter offset on the logit, shrunk toward the pooled offset**
     fitted across every model with ≥25 graded picks, each model counting
     once, the prior worth 150 picks (`fit_offset`, `pooled_prior`,
     `SHRINK_K`). Verified the same way — fitted on the older half, judged on
     the newer half against leaving the number raw. Under 50 graded picks the
     model is prior-dominated by construction and takes the pooled
     correction without a held-out verdict; **n = 0 lands on the pooled
     correction**, so a new model decides on a corrected number from its
     first pick.
   - **Identity** only where neither tier beats raw out of sample
     (mlb_moneyline, mlb_f5_moneyline, batter_hits, batter_walks,
     wnba_moneyline, wnba threes — all within ±3pp raw except wnba_moneyline,
     which UNDERclaims by 9pp and whose offset would push the wrong way).
   - **A third graded source.** `fetch_graded` read the matview, which grades
     MLB and WNBA only, so every NFL, NCAAF, UFC and market-rule model read
     back ZERO — `nfl_prop_market` with 39 settled BETs claiming 55.2% and
     hitting 48.7%, `ncaaf_over_under` 16 claiming 70.2% hitting 43.8%. Those
     now read `picks` (BET rows, not VOID). Same failure `fetch_graded`'s live
     branch fixed on 09-07, one source over.

   Pooled offset on 2026-09-19: **−0.267** on the logit from 21 models — a
   claimed 0.70 becomes 0.641, 0.75 → 0.697. Promotion bar (`promote`,
   `endorsed` in the payload): helps AND transfers for Platt; helps, or
   prior-dominated, for the offset. The offset **helps but does not close** on
   the big overclaimers (ncaaf_live_total 13.3 → 6.3pp held-out, pitcher_k
   16.8 → 9.6, pitcher_hits 21.3 → 14.1, mlb_over_under 19.2 → 12.0): less
   wrong beats raw, and the floor below is what selects, so the transfer bar
   that guarded a prob/edge cut is not the bar here. Stated so it can be
   reversed.

2. **One EV floor, on the calibrated probability, at the deciding price,
   wherever a BET is written.** `config.GLOBAL_MIN_EV` (0.30, his number; 0.20 since 2026-09-20, below),
   `config.min_ev_for(model_id)` = the higher of it and the model's own
   `MODEL_MIN_EV`, `config.expected_value`. Applied AFTER the model's prob/edge
   cut, so it only tightens, and only where a price exists. The paths, each
   with a test in `tests/test_global_ev_floor.py` that fails without the gate:
   `models/scorer._decide` (pre-game, at DK and again at the best price),
   `models/live_scorer.classify_live_signal`, `ncaaf_live/serve.LiveEngine.
   decide_honest` (the NCAAF loop now applies the shared map on top of its
   stage-3 number, which is what the map was fitted on; the stale-line cap
   stays on the raw DK edge), `nfl/live_model/executor.evaluate` (calibrates,
   writes `model_probability_cal`), and the five rule cards through
   `models/honest_ev.gate`: `nfl_prop_market`, `wnba_prop_market`,
   `mlb_game_market`, `mlb_total_public_fade`, NFL wind/opener. The Discord
   "good to" bound solves the same floor on the calibrated probability.
   `model_action_thresholds` has no `min_ev` column and needs none: the floor
   is enforced at write time, so every surface reads the same `picks`.

### The replay — READ THIS BEFORE MOVING THE FLOOR

`scripts/ev_floor_replay.py` replays every model's graded record (the matview
for MLB/WNBA, `picks` for the rest and for the in-play models) through the map
the tiered fit produces today, then applies each floor on the calibrated EV at
the stored price — once on top of the model's current cut (what ships) and
once as the sole selector. Volume is per slate day the model had a graded row;
ROI is split by date halves. Run 2026-09-19 (cut + floor, platform sum):

| floor | bets kept | units | ROI |
|---|---|---|---|
| 0.10 | 258 | +26.2 | +10.1% |
| 0.15 | 160 | +15.6 | +9.8% |
| 0.20 | 102 | +16.0 | +15.7% |
| 0.25 | 40 | +16.1 | +40.4% |
| **0.30** | **13** | **+5.9** | **+45.5%** |
| 0.35 | 3 | −0.4 | −13.7% |

**The floor ALONE — no prob/edge cut — is negative at every level** (0.10:
3,910 bets −9.6%; 0.30: 499 bets −17.8%): high EV at a plus price is a
longshot, and the cuts are what carry the ROI. So the floor stays on TOP of the
cuts, never instead of them.

At 0.30 on honest numbers the board is **13 bets over the whole record** —
`mlb_prop_pitcher_outs` 3, `ncaaf_live_win_prob` 2, `wnba_moneyline` 4,
`wnba_prop_player_assists` 3, `wnba_prop_player_threes` 1. Every de-vig market
rule (`nfl_prop_market`, `wnba_prop_market`, `mlb_spread_market`,
`mlb_total_market`) prices 1–6pp edges by construction and cannot reach a 30%
EV; `mlb_total_public_fade` claims no probability at all (its number IS the
price's implied) so its EV is the vig. Models whose current cut on the honest
number keeps a profitable record that the 0.30 floor then removes:
`mlb_prop_pitcher_walks` (25 bets +25.5% today → 0), `wnba_prop_player_pra`
(39 +23.5% → 0), `ncaaf_live_win_prob` (19 +17.0% → 2), `mlb_live_total_runs`
(13 +42.4% on its 09-09 artifact → 0 through its cut, 2 on the floor alone).
That is the arithmetic of his number, printed before it shipped; the number is
one env variable (`GLOBAL_MIN_EV`) and the table above is where 0.20 and 0.25
sit.

**Moved to 0.20 on 2026-09-20 (mike: "30% is too aggressive then").** The first
NFL Sunday under 0.30 wrote zero NFL bets: the 13:25 UTC `nfl_prop_market` pass
had 4 bets over its edge cut and dropped all 4 (best 0.209), and the largest EV
across all 90 bets that model has ever written is 0.227. Replay re-run that day
(cut + floor, platform sum):

| floor | bets kept | units | ROI |
|---|---|---|---|
| 0.05 | 335 | +6.60 | +2.0% |
| 0.10 | 269 | +19.18 | +7.1% |
| 0.15 | 174 | +11.13 | +6.4% |
| **0.20** | **118** | **+11.52** | **+9.8%** |
| 0.25 | 48 | +13.56 | +28.2% |
| 0.30 | 15 | +6.67 | +44.5% |

All in-sample, on the record the cuts were chosen on. `ncaaf_live_win_prob`
keeps 0.30 through `MODEL_MIN_EV`, because its 0.50/0.16 cut was swept with
0.30 in force. **What 0.20 does NOT do:** `nfl_wind_totals` and
`nfl_opener_spread` still place nothing at any floor. Each has one graded bet,
so its map is the pooled offset (about -0.24), which takes the wind model's
0.574 to 0.510 -- under its own 0.52 cut before any floor applies.

### Operating it

- `python -m models.probability_calibration --promote` after the merge writes
  every endorsed map (Platt or offset) into the `promoted_*` columns. **Then
  redeploy the worker and pollers:** `models.scorer._CAL_CACHE` loads once per
  process, and the live loops are long-lived — a promotion lands in the table
  and a running loop keeps the old map until restart. The 6am pipeline is a
  fresh process.
- The nightly fit and the weekly agent refit CANDIDATES with the pooled prior
  (`fit_pool` first, then `fit_model(..., pool)`); promotion stays a person's
  command. The health check's eligibility note reads the payload's `endorsed`.
- A model's stored `model_probability` stays RAW everywhere; the honest number
  travels in `model_probability_cal` (the NFL live writer and the four
  rule-card INSERTs now carry it too).

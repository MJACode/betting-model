# NCAAF quality assessment — 2026-09-26

Written for Michael. This note inventories every NCAAF lane, says what is
live, and ranks what to keep, leave alone, or hand to a later measurement.
It does not change a cut, a gate, or `PAUSED_MODELS`.

The systematic low-total question on `ncaaf_over_under` (weather, SP+, input
drift) is Model Performance's, on
`bc-ffcbe7e2-9970-5729-9921-c90e98e2e0e4`. The season side split below is
context for the ranking. It is not a root-cause finding and it is not a
proposal to flip the card to overs.

Sources for every number below:

- Registry, cuts, floors, and scorer behaviour: `config.py`, `models/scorer.py`,
  `ncaaf_live/serve.py`, read in this session against `origin/master`
  (`ae6f541b`, 2026-09-25).
- Mechanism and closed search: `docs/sports/ncaaf.md` and
  `docs/thresholds.md`.
- 2026 ledger: the upload `ncaaf_evidence_2026-09-26.json` (as-of 2026-09-26
  ET). This session did not re-query `picks`. The upload's field is `sum_pk`.
  It is reported as stored. It was not divided by 100 and it was not
  re-derived from `profit_flat`.

The go-live gate in CLAUDE.md §2 (≥50 settled, positive flat-bet ROI,
calibration error ≤5%) is per model. The ledger below is priced picks with a
`sum_pk`, not a calibration measurement, and it is not sliced by the date a
cut changed. A lane can be in the live registries and still sit short of that
gate. Nothing in this note pauses one for that.

---

## What is live

No NCAAF `model_id` is in `RETIRED_MODELS`. One is paused.

| model_id | Registry | Status | Scorer kind | Market |
|---|---|---|---|---|
| `ncaaf_over_under` | `MODELS` | **LIVE** | `total_regression` artifact, scored in `models/scorer.py` | totals |
| `ncaaf_spread` | `MODELS` | **LIVE, structurally dormant** on this feed | `cross_book_opener` | spreads, band [1.0, 2.5) |
| `ncaaf_spread_premium` | `MODELS` | **LIVE, structurally dormant** | `cross_book_opener` | spreads, band [2.5, ∞) |
| `ncaaf_moneyline` | `MODELS` | **PAUSED** (`PAUSED_MODELS`) | classifier path if it scored; it does not surface a BET | h2h |
| `ncaaf_live_win_prob` | `LIVE_MODELS` (not `MODELS`) | **LIVE** | `engine` — two-stage LightGBM in `ncaaf_live/engine/remaining.py`, stage-3 pregame correction in `serve.correct_for_pregame` | h2h, in-play |
| `ncaaf_live_total` | `LIVE_MODELS` | **LIVE** (standing instruction: not paused, not capped) | same engine, remaining-points distribution → total PMF | totals, in-play |

`docs/sports/ncaaf.md` still heads the pre-game table "PAPER-FIRST despite
being active". `config.py` records a separate call for the totals rule: Matt
skipped the paper gate on 2026-08-27 ("REAL MONEY from Week 1") after the
four-season scan. The two live lanes were unpaused 2026-09-12 on a 2025
replay. Those are the recorded decisions. This note does not reconcile the
header with the later calls.

### Cuts and floors (what `min_ev_for` returns)

`ACTION_THRESHOLDS` is what the scorer reads. `MODEL_EDGE_THRESHOLDS` and
`MODEL_PROB_THRESHOLDS` mirror the same numbers. The NCAAF live loop reads
`ACTION_THRESHOLDS` through `serve._cut`, then `min_ev_for`.

| model_id | min_prob | min_edge | EV floor that binds | Where the floor lives |
|---|---|---|---|---|
| `ncaaf_over_under` | 0.65 | 0.0 | **0.20** | `MODEL_OWN_EV_FLOOR` (n=20, min written EV +0.218) |
| `ncaaf_spread` | 0.55 | 0.0 | **0.06** | `MODEL_OWN_EV_FLOOR` (n=1, min written EV +0.065) |
| `ncaaf_spread_premium` | 0.58 | 0.0 | **0.20** | absent from `MODEL_OWN_EV_FLOOR` and from `MODEL_MIN_EV`, so `GLOBAL_MIN_EV` |
| `ncaaf_moneyline` | 0.62 | 0.08 | **0.20** | same fallback; paused, so it does not write a BET |
| `ncaaf_live_win_prob` | 0.50 | 0.16 | **0.30** | `MODEL_MIN_EV` 0.30, which is above the global 0.20 |
| `ncaaf_live_total` | 0.73 | 0.12 | **0.24** | `MODEL_MIN_EV` 0.24, which is above the global 0.20 |

Juice: `min_odds_for` is the house default **−200** for every NCAAF model
except `ncaaf_moneyline`, which names **−250** (looser). `threshold_sync`
writes that onto `model_action_thresholds`. `ncaaf_live/serve.py` `_decide`
does not call `min_odds_for` before it writes a row.

Stake multiplier: no NCAAF id is in `MODEL_BET_SIZE_MULTIPLIER`, so the
listed default is 1.0 after tenth-Kelly (cap 5%).

Live volume ceilings in `LIVE_MAX_BETS_PER_WEEK` (`ncaaf_live_total` 20,
`ncaaf_live_win_prob` 10) are **not enforced at score time**. They are the
constraint the calibration recommender optimises under.

### Discord

| Surface | Env | Channel (named in `docs/cloud_worker.md`) | When |
|---|---|---|---|
| Pre-game | `DISCORD_WEBHOOK_NCAAF` | `#ncaaf-picks` | `notify_discord_signals` reads `picks` ⋈ `model_action_thresholds`. NCAAF posts **on game day** (`docs/discord.md`: UFC/GOLF/NCAAF delete-and-rescore until then). |
| In-play | `DISCORD_WEBHOOK_LIVE_NCAAF` | `#ncaaf-live` | `notify_discord_live` at the end of each `ncaaf_live.gameday` pass, through `tracking/publish_filters.live_publishable_sql`. |

One publisher, one key, same cut as the app. A paused lane writes no live
BET (`serve._unless_paused`).

### Last meaningful code (`git log origin/master`)

| Path | Date | Commit | What it was |
|---|---|---|---|
| `scripts/ncaaf_margin_eval.py` | 2026-08-25 | `0ba3adae` | Totals rule goes live as total-regression. Same day the scorer's `total_regression` branch landed. |
| `models/scorer.py` `_opener_rule` | 2026-08-29 | `de7294da` (#261) | Board visibility: a decline writes a watching row. |
| `scripts/ncaaf_search/register_opener.py` | 2026-08-28 | `9bce5350` | Premium tier as a disjoint band. |
| `ncaaf_live/engine/remaining.py` | 2026-08-28 | `2d29c807` | Artifact loader. Not a cut. |
| `features/ncaaf_feature_engine.py` | 2026-09-13 | `76713113` (#698) | FBS registry correction. SP+ required. |
| `ncaaf_live/gameday.py` | 2026-09-19 | `04323813` (#765) | Fourth live staleness guard. |
| `ncaaf_live/serve.py` | 2026-09-19 | `0db4d094` (#775) | `ncaaf_live_win_prob` 0.65/0.10 → 0.50/0.16. Totals cut kept. |
| `models/scorer.py` (file) | 2026-09-25 | `7e42ae31` (#828) | Price pre-filter timeout rollback. Not a selection-rule change. |

---

## How a BET is chosen

### `ncaaf_over_under`

The artifact predicts the **game total from fundamentals**. The market number
is not a feature. Disagreement is `predicted total − DraftKings total`
(`models/scorer.py`, `kind == "total_regression"`). P(over) is the
out-of-sample residual ECDF at that disagreement (`total_over_prob`).

The validated rule is a **symmetric** `|disagreement| ≥ 8` gate, stored as
`d_threshold` on the artifact. The scorer enforces `abs(disagreement) < gate`
directly and forces those games to NONE. The comment on that branch states
why a probability floor alone would be the wrong gate: the residuals are not
centred (mean −0.62 in that comment), so +8 maps to P(over) ≈ 0.65 while −8
maps to P(over) ≈ 0.29 (P(under) ≈ 0.71). A lone 0.65 floor would pass overs
at about +8 and unders at about −5. `min_prob` 0.65 is the P(over) **at the
gate**, not a substitute for the gate. `min_edge` 0.0 because the gate is the
filter.

There is no lead limit (`NCAAF_TOTALS_MAX_LEAD_DAYS` defaults to `inf`). The
first pass where `|pred − DK| ≥ 8` locks the pick.

Walk-forward cited in `config.py` (corrected snapshots, four test seasons):
pooled 295/528, 55.9%, +6.7%. The pooled 95% interval does not clear 52.38%
breakeven. 2025 was the weakest season (47/89, 52.8%, +0.8%).

### `ncaaf_spread` and `ncaaf_spread_premium`

Not a fitted margin model. `kind == "cross_book_opener"` calls `_opener_rule`.
Back the side **Bovada's opener** favours, at **DraftKings' opening number**,
only while that number is still gettable.

Three preconditions, each a decline:

1. Both openers captured within `max_skew_min` (default
   `OPENER_MAX_SKEW_MIN` = 90, env `NCAAF_OPENER_MAX_SKEW_MIN`).
2. DraftKings' current spread still equals its opening spread.
3. `|DK opener − Bovada opener|` clears the band.

Bands in `scripts/ncaaf_search/register_opener.py` `BAND_RECORDS`, disjoint
so one game fires one tier:

| Tier | Band | Backtest (2023–2025, that file) | Flat prob stored |
|---|---|---|---|
| `ncaaf_spread` | [1.0, 2.5) | 706 bets, 56.94%, +8.70%, CI (0.533, 0.605) | 0.5694, floored by min_prob 0.55 |
| `ncaaf_spread_premium` | [2.5, ∞) | 344 bets, 60.47%, +15.43%, CI (0.552, 0.655) | 0.6047, floored by min_prob 0.58 |

A game in the other tier returns no row from this model (`d_threshold_max`).
A precondition failure writes a watching NONE with `downgrade_reason`, except
the sibling-tier decline, which writes nothing.

`docs/sports/ncaaf.md` records why production barely fires: the Odds API
lists next week's games with DraftKings priced and no sharp book; Bovada's
first stored number lands later, by which time DraftKings has left its
opener. Measured 2026-09-07. Mike declined to pause the tiers on 2026-09-10.
They stay live and keep writing watching rows.

The margin-regression spread (the old `ncaaf_margin_eval --fit` path) is
**not** what scores. The search closed it: ~50% across the four-season
walk-forward. `scorer.py` still has a `margin_regression` branch; the live
artifact kind is `cross_book_opener`.

### `ncaaf_live_win_prob` and `ncaaf_live_total`

`scheduler.py` `run_ncaaf_live_loop` runs `python -m ncaaf_live.gameday
--source cfbd` on the pollers service (`RUN_NCAAF_LIVE=0` disables it).

`LiveEngine.price` (`ncaaf_live/serve.py`):

- Skip overtime (`period > MAX_PERIOD`).
- Require a pre-game total and spread on the context.
- **FBS-vs-FBS only** (`ctx.fbs_matchup`). SP+ necessary, classification may
  only veto — the same rule as the pre-game gate.
- Drop a market that is not takeable, that moved at the book with no change
  in our state beyond the cap, or that has not been quiet for
  `LIVE_SETTLED_SEC` (settled-state rule, 2026-09-19).
- Totals lane also requires `seconds_remaining >= TOTAL_MIN_SECONDS` (900).
  Inside that, the lane is closed.

`candidates` prices one state with no threshold:

- Win prob: two-stage remaining-points model → moneyline price, then
  `correct_for_pregame` (stage 3). The corrected probability is what is
  stored and decided on.
- Total: PMF of the final total from the joint remaining distribution.
  P(over) / P(under) at the live line. Pushes (exact land on the line) are
  outside both masses.

`decide_honest` applies the promoted calibration map on top of that
probability, then `_decide`:

- Stale-line cap: `|DK edge| > 0.18` (`MAX_EDGE_CAP` in `serve.py`) declines.
- BET when calibrated `p >= min_prob` and DK `edge >= min_edge` and, when a
  price exists, EV on the DK American price `>= min_ev`.
- AVOID on the other side when the mirrored inequality holds.
- Otherwise nothing is written (no NONE row; the loop would churn it).

**Qualify at DraftKings. Place the bet at the best bettable in-play quote.**
The 2025 replay the cuts were swept on is DraftKings history. A cheaper book
is recorded as the decision price; it is not what clears the floor. Standing
instruction in `docs/sports/ncaaf.md`: do not reopen either half, and do not
pause or cap `ncaaf_live_total`.

The 2026-09-19 win-prob cell (honest map, 0.30 floor on, 2025 replay): 43
bets, 20-23, +38.6%, halves +26.4% / +50.2%, five positive neighbours. It is
a plus-money dog population (calibrated ≥ 0.50 at +160 or longer), not the
favourite population the earlier 2026 forward record was built on.
`docs/thresholds.md` says re-sweep at about 25 forward bets under this cut.

The totals cell 0.73 × EV 0.24 was shipped 2026-09-13 with the FBS gate.
FBS-vs-FBS 2025 replay: 17 bets, +21.3%, 14 of them first half. The same
doc says the replay does not prove the cut is better, and
`docs/thresholds.md` (honest re-sweep, 2025, 504 games) records the totals
cut as **dark under the floor**: 0.73/0.12 takes 0 bets, and no populated
cell reaches 25. The cut was kept.

### `ncaaf_moneyline`

Paused since the classifier holdout (AUC ~0.49–0.50; moneyline parked at
about −12% ROI / 17% calibration error — the pause comment in `config.py`).
The later moneyline scan (`scripts/ncaaf_search/outcome_edge_scan.py`,
written up in `docs/sports/ncaaf.md`) is NULL at real Bovada prices: every
edge cell loses. It stays paused. A paused model still scores NONE rows on
the pre-game path; `_paused_signal` stops it publishing AVOID as a fade.

---

## 2026 ledger (upload only)

| model_id | Priced | W-L | `sum_pk` | Open | Last pick in the upload |
|---|---|---|---|---|---|
| `ncaaf_live_win_prob` | 29 | 19-10 | +168.71 | 0 | 2026-09-25 |
| `ncaaf_live_total` | 98 | 51-47 | −120.4 | 0 | 2026-09-18 |
| `ncaaf_over_under` | 22 | 9-13 | −212.07 | 16, all under | 2026-09-26 |
| `ncaaf_spread` | 1 | 0-1 | (one priced loss) | 0 | — |
| `ncaaf_spread_premium` | 0 | — | — | — | — |
| `ncaaf_moneyline` | 0 | paused | — | — | — |

Quality strings on the same upload:

- `ncaaf_live_win_prob`: recent ROI +18.9% / 65% hit on 23.
- `ncaaf_over_under`: recent ROI −14.8% / 45% on 20. Quality monitor the
  same day: CRIT slate concentration 10/10 open BETs under, and CRIT volume
  spike (10 bets / 3.8u vs a median 2 / 0.8u).
- `ncaaf_live_total` has no recent-ROI string on the upload.

`ncaaf_live_total`'s last pick of 2026-09-18 is the previous Saturday. This
note is dated Saturday 2026-09-26 morning ET, before that day's kickoffs.
Silence since the 18th is what a Saturday sport looks like on a Friday night.
It is not, by itself, evidence the loop is off.

### Under-heavy totals card — context, not a fix

Model Performance's read, restated so this note does not contradict it:

- Season BETs: over 4-2, under 5-11, plus 16 open unders and 0 open overs.
- The gate in code is symmetric ±8. Overs fire in other weeks.
- Raw probability on under BETs clusters near 0.71–0.73, which is what the
  scorer comment says the ECDF does at a large negative disagreement. It is
  not an `nfl_live_prop`-style pair of constants.
- They are looking for systematic low predicted totals. This assessment does
  not open that branch.

What was already measured, and should not be re-mined as if it were new
(`docs/sports/ncaaf.md`, session 280, 2026-09-10):

- On the 2026 board the production artifact predicted a mean 0.85 below
  DraftKings (56.6% of games below), against +0.68 on 2025 games through
  09-20. The lean is spread across scoring and defence inputs. No single
  feature and no NaN column was isolated. Setting every feature to the 2025
  mean predicted 52.9 vs 53.1. The ECDF's −0.62 offset is what turns a small
  mean lean into P(under) > 0.5 on about three quarters of rows.
- The information test at the DraftKings close (`totals_information_test.py`):
  the blend beats the book by ≤ 0.001 Brier. At the close the disagreement
  is at most marginal information.
- Weather spot rules and the issued-forecast haircut were already run. The
  artifact was left unchanged.

The 16 open unders are bets of record. Line movement after the lock does not
retract them (CLAUDE.md §1c).

---

## File map

Start at `docs/sports/ncaaf.md`. This file is the 2026-09-26 ranking on top
of it.

| Question | Where |
|---|---|
| Registries, cuts, pause, EV floors, Discord env names, lead window | `config.py` (`ACTION_THRESHOLDS`, `PAUSED_MODELS`, `MODELS`, `LIVE_MODELS`, `MODEL_OWN_EV_FLOOR`, `MODEL_MIN_EV`, `min_ev_for`) |
| Pre-game BET / watching row | `models/scorer.py` (`total_regression` branch, `_opener_rule`) |
| Features, ECDF helpers | `features/ncaaf_feature_engine.py` |
| Fit the totals artifact | `scripts/ncaaf_margin_eval.py --fit-totals` |
| Opener bands | `scripts/ncaaf_search/register_opener.py`, `opener_strategy.py` |
| Closed search (do not re-mine) | `scripts/ncaaf_search/` — `run_search.py`, `outcome_edge_scan.py`, `totals_lead.py`, `totals_information_test.py`, `totals_input_drift.py`, `totals_weather_source.py`, `weather_totals.py`, `starter_out.py`, `steam_lag.py`, `consensus_gate.py`, `line_move_spots.py`, `situational_spots.py`, `qb.py` |
| Search write-up | `docs/ncaaf_search_findings.md`, `docs/ncaaf_model_plan.md` |
| Live loop | `ncaaf_live/gameday.py`, `scheduler.py` `run_ncaaf_live_loop` |
| Live decision | `ncaaf_live/serve.py` |
| Live model | `ncaaf_live/engine/remaining.py`, `distribution.py`, `pricing.py` |
| Live artifacts | `ncaaf_live/data/artifacts/` (off `model_registry`; `SCORING_METHODS` = `engine`) |
| Totals-lane rebuild / repricing (already run; do not repeat as a new idea) | `scripts/ncaaf_live_total_rebuild.py`, `scripts/ncaaf_live_total_repricing.py` |
| Win-prob dog correction | `scripts/ncaaf_live_dog_correction.py`, `scripts/ncaaf_live_dog_calibration.py` |
| Cut evidence | `docs/thresholds.md` (rows for both live lanes) |
| Ingest | `data/ingestors/cfbd_ingestor.py`, `scripts/ncaaf_weather_backfill.py` |
| Tests that pin the rules | `tests/test_ncaaf_totals_regression.py`, `tests/test_ncaaf_cross_book_opener.py`, `tests/test_ncaaf_margin_eval.py`, `ncaaf_live/tests/test_serve.py`, `ncaaf_live/tests/test_qualify_at_dk.py`, `ncaaf_live/tests/test_pregame_calibration.py` |

---

## What to do, in order

### 1. Leave `ncaaf_live_win_prob` alone

It is the healthy lane on the upload: 19-10, `sum_pk` +168.71, last pick
2026-09-25, recent +18.9% / 65% on 23. The current cut (0.50 / 0.16 / EV
0.30, stage-3 correction, FBS-only, qualify at DraftKings) is the cell that
survived the 2026-09-19 honest re-sweep, and it is a different population
from the favourites that built the early forward record.

Do not loosen it. Do not drop the 0.30 floor to the global 0.20 — the cut
was swept with 0.30 in force, and `MODEL_MIN_EV` is what keeps the global
move from changing this lane. The next measurement already named in
`docs/thresholds.md` is a re-sweep at about 25 forward bets **under this
cut**, not a new grid today.

### 2. Leave `ncaaf_live_total` live, and do not invent another cut here

Lifetime on the upload: 98 priced, 51-47, `sum_pk` −120.4. That sample mixes
cuts. The standing instructions (2026-09-12, repeated in
`docs/sports/ncaaf.md`) are: not paused, not capped, best book places the
bet, qualify at DraftKings.

Six rearrangements of the same engine output were already measured on the
2025 replay and did not produce a production edge (tighter cut above 0.72,
recalibration, stage-2 shrink, per-day cap, smoothing, side/quarter splits).
The honest re-sweep then found the shipped cell dark under the EV floor.
Another threshold PR from this assessment would repeat that work.

The next attempt, already written in the sport doc, is information the model
does not have. `scripts/ncaaf_live_total_rebuild.py` and
`scripts/ncaaf_live_total_repricing.py` are the harnesses that already ran.
`docs/thresholds.md` still asks for a production re-sweep once about 50 bets
have settled **under the 0.73 × 0.24 rules**. Until that sample exists, the
lifetime −120 is a reason to keep the standing instruction in view, not a
reason to pause.

### 3. Keep the `ncaaf_over_under` gate where it is until Model Performance reports

The season card is under-heavy (over 4-2, under 5-11 settled, 16 open unders).
Recent ROI on the upload is −14.8% on 20. The walk-forward that shipped the
rule did not clear breakeven on its confidence interval, and 2025 was already
the weak season. That is a losing forward start on a rule that was sized
small for that reason.

The code's gate is the symmetric ±8 the walk-forward validated. Model
Performance has already said today's 10/10 under slate is not a flipped-side
bug. A "bet the over" change, a pause, or a second root-cause branch would
fight the investigation that owns the low-total hypothesis.

When that investigation lands, the move is an assessment of whatever cause
they name (refit only if `--fit-totals` still clears its kill line — the fit
refuses to register otherwise). The 16 open unders stay in the record either
way.

`ncaaf_over_under`'s own EV floor is already 0.20, equal to the global floor,
because the 20 bets that set it never printed an EV under +0.218. Moving
that floor is not a volume lever on the card that already cleared it.

### 4. Leave both spread tiers live and dormant

One priced `ncaaf_spread` loss. Zero `ncaaf_spread_premium` bets. The
backtest (706 + 344, both bands positive in 2023, 2024, and 2025) was not
measured under the 90-minute simultaneity precondition, because CFBD
`spreadOpen` has no timestamp. Production firing requires Bovada and
DraftKings openers inside 90 minutes **and** DraftKings still on that
number. That is a feed-timing fact, measured 2026-09-07. Loosening the skew
to manufacture bets would bet a different rule from the one that was
validated. Mike already declined a pause (2026-09-10).

`ncaaf_spread_premium` has no `MODEL_OWN_EV_FLOOR` entry because it has
never written a bet. The global 0.20 applies. That is the fallback the floor
comment describes for an unmeasured model. It is not a defect to patch in
this pass: with zero bets there is no written EV to sit under, and a floor
change is a config change this assessment is not making.

### 5. Leave `ncaaf_moneyline` paused

The classifier failed its holdout. The later regression-to-price scan lost
in every edge cell at real prices. Unpausing it is a new model, not a
threshold.

---

## Deliberately not done

- No edit to `PAUSED_MODELS`, `ACTION_THRESHOLDS`, `MODEL_MIN_EV`, or
  `MODEL_OWN_EV_FLOOR`.
- No selection-rule change and no "flip to over" branch.
- No production SQL. The ledger is the 2026-09-26 upload.
- No claim that any lane has cleared the §2 go-live gate. Calibration error
  was not re-measured here.

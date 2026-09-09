# MLB pick volume — where it comes from, and what can be cut

> Measured 2026-09-07 (session 249) at Matt's request: *"far too much volume to
> keep up with on a daily basis, how can we become more efficient while still
> being profitable."*
>
> **Window.** "The past 7-10 days" is read as **2026-08-31 → 2026-09-07** (8
> slate days). That is not a round number chosen for convenience — it is the
> first date on which the current MLB prop configuration existed (#366, the
> market-relative prop rule + the twelve calibrated cuts, both merged
> 2026-08-31). Every number below states its own window.
>
> **Read §1 before any per-model ROI in this file.** No MLB model has more than
> four days of settled record on its current version.

---

## 0. The shape of the problem, in one table

Written MLB BETs per day, `picks` where `signal_type='BET'`:

| Window | pre-game / day | live / day | total |
|---|---|---|---|
| 2026-08-08 → 08-30 (23 days) | 3.4 (78) | 3.0 (69) | **~6** |
| 2026-08-31 → 09-07 (8 days) | 20.6 (165) | 9.0 (63 over 7 nights) | **~30** |

The step is on **2026-08-31**, not gradual. Composition of the 165 pre-game
BETs in the second window:

| model | BETs | share |
|---|---|---|
| `mlb_prop_pitcher_k` | 60 | 36% |
| `mlb_prop_pitcher_hits` | 45 | 27% |
| `mlb_prop_pitcher_outs` | 27 | 16% |
| `mlb_over_under` | 26 | 16% (paused 09-03) |
| everything else (f5, runline, batter_runs, batter_hr) | 7 | 4% |

All 63 live BETs in the window are **`mlb_live_total_runs`**. So ~95% of the
volume is **four models**: three pitcher props and one live total.

---

## 1. Why the 7-10 day record cannot rank these models

Every pre-game MLB model changed version inside the window:

| model | current version live from | settled BETs on it (to 09-07) |
|---|---|---|
| `mlb_moneyline` | 2026-09-04 (#451) | 0 |
| `mlb_f5_moneyline` | 2026-09-04 (#436 retrain, #444 cut) | 0 |
| `mlb_prop_pitcher_k` | 2026-09-04 (#451) | 30 |
| `mlb_prop_pitcher_hits` | 2026-09-05 (#454) | 11 |
| `mlb_prop_pitcher_outs` | 2026-09-05 (#454) | 12 |
| `mlb_prop_batter_runs`, `mlb_prop_batter_walks` | 2026-09-05 (#454) | 0 |
| `mlb_over_under` | paused 2026-09-03 (#436) | — |
| `mlb_live_total_runs` | model 2026-06-14; **cut** 2026-08-30 | 63 |

Per-bet ROI has SE ≈ 1/√n. On these samples that is ±25 to ±40 percentage
points. **Nothing in this window separates one prop model from another on ROI,
and this file never claims it does.** What the window CAN answer — and what the
rest of this file is — is: how many picks are being written, whether the number
that fires matches the number the cut was chosen to produce, and whether the
probabilities the volume is derived from are true.

The one exception is `mlb_live_total_runs`: 63 settled bets on an unchanged
model, splittable in half.

---

## 2. THE PRIMARY FINDING — the calibrated cuts are applied to raw probabilities

On 2026-08-31, twelve models were re-cut on **calibrated** probability sweeps
(`config.py`, `scripts/calibrated_threshold_sweep.py`), and
`DECIDE_ON_CALIBRATED_PROB` was added so the decision would be made on the
calibrated number. `models/scorer.py:1117` says so explicitly.

**That branch is in `classify_edge` only. Player props do not go through
`classify_edge`.** `_make_prop_pick` (`models/scorer.py:2908`) decides on the
RAW number and has no calibration branch:

```
models/scorer.py:2950   signal_type = "BET" if (edge >= bet_thresh and model_prob >= prob_thresh) else "NONE"
```

Ten models carry a promoted calibration map (`model_calibration WHERE
promoted`, all promoted 2026-08-31 17:05 ET): seven `mlb_prop_*` and three
`wnba_prop_*`. **All ten are player-prop models, and all ten are scored through
`_make_prop_pick`** — `run_prop_scorer` (MLB), `run_wnba_prop_scorer`,
`run_nba_prop_scorer`, `run_nfl_prop_scorer` all call it. No game-level model
has a promoted map, and a model with no map calibrates to itself.

**So `DECIDE_ON_CALIBRATED_PROB` has never changed a single production
decision.** It is on by default and it is a no-op everywhere. The "never" is
measured, not assumed: across every pick ever written, **no non-prop model has
a single row where `model_probability_cal IS DISTINCT FROM model_probability`**
— they have no map — and the prop path has no branch that could read one.

Measured in the data, not inferred from the code — each pick stores the
calibrated number it *would* have decided on, in `picks.model_probability_cal`
(`scorer.py:1982`). Restricted to BETs whose stored calibrated number actually
**differs** from the raw one (i.e. a map was live for that pick — see the
second defect below), 2026-08-31 → 09-04, DK-priced:

| model | BETs | fail own `min_prob` or `min_edge` on the calibrated number |
|---|---|---|
| `mlb_prop_pitcher_k` | 31 | **30** |
| `mlb_prop_pitcher_hits` | 26 | **26** |
| `mlb_prop_batter_runs` | 2 | 0 |

**56 of 57 prop BETs — 98% — would not exist if the decision used the
calibrated probability the pick already carries.** Note what that does and does
not say: applying the *2026-08-31 map as promoted* would not halve these two
models, it would very nearly switch them off. The size of the correction is
itself evidence of how far the raw probabilities are from the priced reality.

(Over the wider 09-01 → 09-07 window the same test reads 46 of 95, 48% — but
38 of those 95 rows carry an inert map and pass trivially, so the map-live
figure above is the honest one.)

The gap is visible in the projections too. `config.py:249` records the
`pitcher_k` cut as *"25 bets … ~5.4/wk"*; it is firing **~52/wk**.
`config.py:251` records `pitcher_hits` as *"~19.8/wk"*; it is firing **~39/wk**.

### The second defect — a promoted map can silently go inert

`load_calibrations` (`models/probability_calibration.py:386`) selects
`promoted_a, promoted_b` but keeps only rows whose **candidate** `method` is
`'platt'`. When the weekly refit cannot fit a model it writes `method = NULL`,
and the promoted map is dropped on the next read. That has already happened:

| game_date | `pitcher_k` + `pitcher_hits` picks | with cal ≠ raw |
|---|---|---|
| 08-31 → 09-03 | 166 | 166 |
| 09-04 | 43 | 11 |
| 09-05 → 09-07 | 95 | **0** |

Since 2026-09-05 these two models have had **no calibration at all**, not even
in the stored number. `scorer.py:1120` states the design intent as *"only an
endorsed map bites"*; the observed behaviour is that an un-endorsed refit can
un-bite an endorsed one. Logged as a follow-up.

### The sequencing caveat — do not just flip the switch

The promoted maps were fitted **before** the 09-03/09-05 leak-repair retrains.
Because of the defect above, the two models this file is mostly about are
currently inert, so wiring the flag in today would apply stale maps to
`batter_rbi/runs/tb/walks`, `pitcher_er` and the three WNBA props — *not* to
`pitcher_k` and `pitcher_hits`. Those two need a refit first, and this
morning's ModelCalibration pass says it cannot do one yet:

* `mlb_prop_pitcher_k` — *"only 47 graded picks since 2026-09-03 (need 150) —
  identity map, unfitted"*, raw gap **14.24pp**
* `mlb_prop_pitcher_hits` — *"only 26 graded picks since 2026-09-04 (need 150)
  — identity map, unfitted"*, raw gap **16.87pp**

Both retrained models are still overclaiming by 14-17pp. The leak repair fixed
the point estimate; it did not fix the probability.

---

## 3. The probabilities the volume is derived from are not true

Settled BETs 2026-08-31 → 09-07, DK-priced, `z` = binomial z of wins against
the model's own summed claimed probability:

| model | n | claims | delivers | z | units |
|---|---|---|---|---|---|
| `mlb_live_total_runs` | 63 | 74.0% | 55.6% | **−3.35** | +0.14 |
| `mlb_prop_pitcher_k` | 54 | 65.9% | 42.6% | **−3.64** | −11.51 |
| `mlb_over_under` | 24 | 58.1% | 29.2% | **−2.88** | −10.78 |
| `mlb_prop_pitcher_hits` | 42 | 62.9% | 59.5% | −0.46 | +7.25 |
| `mlb_prop_pitcher_outs` | 24 | 63.9% | 54.2% | −1.00 | +2.69 |

Three of five are miscalibrated at p < 0.005 — and they are the **three
highest-volume models**. `mlb_over_under` is already paused, and this window
independently confirms that call.

**A model that overclaims produces more picks AND worse picks.** Edge is
`model_prob − implied_prob`; inflate the first term and both the count above
the cut and the false confidence of what clears it rise together. Volume is the
symptom here, not the disease.

### What is NOT wrong: line selection

CLV over the same window, `picks.clv_pct`:

| model | n with CLV | mean CLV | beat close |
|---|---|---|---|
| `mlb_prop_pitcher_k` | 43 | **+1.62%** | 34 / 43 |
| `mlb_prop_pitcher_outs` | 21 | **+1.59%** | 14 / 21 |
| `mlb_prop_pitcher_hits` | 37 | **+1.17%** | 22 / 37 |
| `mlb_over_under` | 16 | −0.16% | 13 / 16 |

All three pitcher props beat the closing price, `pitcher_k` included — the
model that is losing money. **This argues against killing `pitcher_k` and for
fixing its probability.** It is picking the right side of the right markets and
then betting far too many of them at far too much implied conviction.

**`mlb_live_total_runs` has CLV on 0 of 63 picks.** No live pick in this repo
has ever had CLV captured, so the one model with enough settled bets to judge
is also the one we cannot judge by the fast-converging measure. Logged as a
follow-up.

---

## 4. THE LIVE MODEL — the cleanest cut on the board

`mlb_live_total_runs`, settled BETs, DK-priced, split by the inning the bet was
taken in. The cut changed on 2026-08-30 (prob ≥ 0.70 + EV ≥ 0.32), so the
current regime starts 08-24 and is split in half:

| inning | half | n | W-L | claims | delivers | units |
|---|---|---|---|---|---|---|
| 1-3 | 08-24 → 08-30 | 21 | 9-12 | 70.8% | 42.9% | **−4.28** |
| 1-3 | 08-31 → 09-06 | 36 | 17-19 | 73.8% | 47.2% | **−5.38** |
| 4+ | 08-24 → 08-30 | 10 | 9-1 | 72.6% | 90.0% | **+6.16** |
| 4+ | 08-31 → 09-06 | 27 | 18-9 | 74.4% | 66.7% | **+5.53** |

Pooled current regime: **innings 1-3 = 26-31, −9.66u**; **innings 4+ = 27-10,
+11.69u**. Both halves agree in sign, in both bands, so this is a plateau and
not a single lucky cell. Innings 4+ is also well calibrated (claims 73.6%,
delivers 73.0%); the entire −3.35 z-score in §3 lives in innings 1-3.

The mechanism is plausible: remaining-runs uncertainty is at its widest before
a starter has been seen, and a Poisson head fitted on full-game data is at its
most overconfident exactly there.

### What this is NOT: the P&L of an inning-4 gate

`LOCK_LIVE_PICKS_AT_FIRST_SIGNAL` is on, and the data confirms it — **94 BETs
across 94 distinct games** since 08-24, exactly one per game. So the "inning 4+"
row is the record of *games whose first qualifying signal happened to arrive in
inning 4 or later*. It is **not** the record a gate would have produced: under a
gate, a game that fired in inning 2 does not disappear, it locks at its first
qualifying signal from inning 4 on — a different line, a different price, and
possibly still a bet.

So both numbers below are upper bounds on the effect, in opposite directions:
the volume saving is **less** than 36 of 63, and +11.69u is **not** the gate's
P&L. What survives cleanly is the calibration split: early-inning signals claim
~73% and deliver ~46% in both halves; late-inning signals are true.

The gate CAN be simulated properly — the MLB live loop writes every in-play
snapshot to `odds` (`snapshot_type='in_play'`; **642,582 totals rows across 188
games since 08-24**), so the model can be replayed pass by pass with the gate
applied and the first qualifying inning-4+ signal graded. That is a worker job,
not a query, and it is the right next step before the gate ships.

**Volume effect (upper bound):** 27 of the 63 live BETs since 08-31 were taken
in inning 4 or later — **3.9/day against 9.0/day**, ≈28/week.

That number matters because `config.LIVE_MAX_BETS_PER_WEEK` sets **30/week**
for this model, added 2026-08-30 when Matt said *"still too many live bets on
MLB"*. Actual: **31 in the week of 08-24, 63 in the week of 08-31.** The
comment at `config.py:556` is candid that *"nothing enforces it at score
time"* — it is an input to the recalibration recommender, not a gate. The
ceiling Matt set is being exceeded 2.1x and no code can currently stop it.

### Secondary, weaker: the Under side

Overs 08-24 → 09-06: 34-25, **+9.97u**. Unders: 15-20, **−7.95u**. But the
Under side was **+5.01u (12-5)** before 08-24, so it fails a time split across
the cut change and is reported here as an observation, not a recommendation.
The inning split does not fail it.

---

## 5. Pre-game — what a daily cap would have done

The currently publishable pre-game set (excluding paused `mlb_over_under` and
retired `mlb_prop_batter_hr`), 2026-08-31 → 09-07, ranked within each day by
the model's own claimed EV (`p·b − (1−p)`):

| kept | picks | units |
|---|---|---|
| everything (~15.6/day) | 125 | **−0.99** |
| top 10 / day | 70 | **+13.03** |
| top 8 / day | 56 | +11.23 |
| top 6 / day | 42 | +10.30 |
| *ranks 11+ only* | 55 | **−14.02** |

The whole loss of the window sits in the low-EV tail. Two honest caveats:

* **In-sample.** The ranking was chosen after seeing the outcomes; 8 days,
  n=70 in the top-10 band. §7's rule applies — this regresses forward.
* **Out-of-window check, 2026-08-09 → 08-30** (the previous regime, ~5
  picks/day so the bands are thin): top-5/day **+3.40u over 63**, ranks 6-10
  **−5.71u over 9**. Same direction, far too little of it to call confirmation.
* **The rank is raw EV, so it structurally favours the most overconfident
  model.** `p·b − (1−p)` reads the same `model_probability` §3 shows to be
  14-17pp hot on two of these models, so a raw-EV cap is not a substitute for
  fixing calibration — it is a bound on the work while that is fixed. A
  calibrated re-rank is not computable across this window: the maps went inert
  on 09-05 (§2), so half the rows have no calibrated number to rank by.

A cap is also the one lever that is a *guarantee* rather than a hope — the same
argument `config.py:585` makes for `LIVE_MAX_SIGNALS_PER_DAY`. It bounds the
work whatever the models do next week, which a threshold cannot.

---

## 6. Redundancy and operator load

**Same pitcher, two markets.** Of 104 (game, pitcher) pairs carrying a pre-game
prop BET since 08-31, **31 carry two markets** — 62 of the 135 player-prop
picks (the other 30 of the 165 are game-level). Collapsing
to one bet per pitcher (highest EV) removes **~3.9 picks/day, 24% of pre-game
volume**. Cost over the window: the two-market group netted −0.27u in total, so
there is no measured cost, and correlated exposure to one start drops.

**Pre-game is batchable; live is not.** 131 of 165 pre-game BETs (79%) were
written **≥6 hours before first pitch**; mean lead 11.3 hours. One morning
sitting captures four fifths of the card. Live BETs cluster 18:00-23:59 ET (47
of 63, 75%) with a 14:00-15:00 afternoon cluster — that is an all-evening
commitment, and it is where the "can't keep up" cost actually lands.

**Hand-off friction is already solved.** `dk_bet_link` is populated on 165/165
pre-game and 63/63 live BETs; `best_bet_link` on 141 and 49.

---

## 7. External — what was checked outside the repo

* **Automating placement is out.** DraftKings' Terms of Use prohibit bots,
  scripts and automated means for placing wagers, with account restriction and
  stake forfeiture as the stated consequence, and there is no public
  bet-placement API. FanDuel and BetMGM carry the same policy. So no route
  exists to make 30 bets/day cheaper to *place* — the efficiency has to come
  from making fewer, better picks.
  ([ToS review](https://terms.law/ToS-Watchdog/sports-betting/draftkings/),
  [DK Terms of Use](https://sportsbook.draftkings.com/legal/nj-terms-of-use))
* Deep links (already at 100% coverage) are the legitimate version of that
  hand-off and are as far as it goes.

---

## 8. What this file does NOT claim

* That `mlb_prop_pitcher_k` should be paused. Its record is 30 settled bets on
  its current version, its CLV is positive, and its measured defect is a
  probability that is 14pp hot — which is a calibration fix, not a pause.
* That any per-model ROI here is evidence of skill or its absence. See §1.
* That the EV-rank cap in §5 will hold out of sample. It is in-sample.
* Anything about the Under side of the live total. See §4.

---

## 9. What shipped, 2026-09-07 (mike)

Matt picked options 1, 2 and 4, with the calibrated maps scoped to those the
weekly pass endorses and the live gate held back for a replay.

**1. The calibrated decision reaches player props.** `_make_prop_pick` gains the
branch `classify_edge` has carried since 2026-08-31. Raw numbers are still what
is stored; the decision edge is `model_probability_cal - dk_implied_prob`.
`tests/test_prop_calibrated_decision.py`, watched to fail on the pre-fix body.

**1b. The promoted slot carries its own method and its own endorsement.**
`load_calibrations` reads `promoted_method` rather than the candidate's
`method`, so a nightly refit can no longer disable a promoted map; `promote()`
now requires **helps AND transfers** rather than `applied` (= helps alone), and
freezes both verdicts at promotion. `demote()` is new — a lever with no off
switch is one nobody pulls. `data/migrations/promotions_endorsed_only_2026_09_07.sql`
re-freezes the four still-endorsed maps on today's fit and demotes six that are
no longer endorsed, guarded on the property it establishes.

Three models are endorsed today and NOT promoted — `mlb_prop_pitcher_walks`
(paused), `wnba_prop_player_assists` and `wnba_prop_player_pra` (both active).
Promoting them is a separate call and was deliberately not taken here.

**4. One BET per pitcher, and an interim daily cap.** `PROP_ONE_BET_PER_PLAYER`
collates the pitcher-prop pool to the highest claimed EV per (game, player);
`PROP_MAX_SIGNALS_PER_DAY` holds `pitcher_k` and `pitcher_hits` to 3 each while
their maps cannot be refit. Both run over the whole slate before anything is
written, which is why the scorer now accumulates instead of inserting per model.
A turned-away BET is written as a NONE carrying `picks.downgrade_reason`, a new
column — an unexplained NONE would be read by the next sweep as the model
declining, which is a number the model never said.

Replayed over the eight days of this window, on the picks actually written:

| stage | BETs | per day | units |
|---|---|---|---|
| as fired | 136 | 17.0 | −1.57 |
| after one-bet-per-player | 102 | 12.8 | +3.65 |
| after the 3+3 cap | 67 | **8.4** | +10.10 |

The **volume** column is exact. The **units** column is in-sample — the ranking
was chosen after seeing the outcomes — and is offered as "this did not cost
anything measurable", not as a forecast.

**2. The live inning gate is NOT shipped — AND THE REPLAY SAYS DO NOT SHIP IT.**

`scripts/live_inning_gate_replay.py` replays the production decision
(`classify_live_signal`, `expected_value`, `build_live_state_row`, the real EV
floor and edge cap) over 169 games of kept state and in-play price since
2026-08-24, taking the first qualifying signal at each candidate gate. Its
grading rule was validated first and agrees with production settlement on 94 of
94 settled BETs.

| gate | bets | W-L | units | ROI | claims | delivers |
|---|---|---|---|---|---|---|
| 1 (ungated) | 120 | 64-56 | −2.89 | −2.4% | 73.5% | 53.3% |
| 2 | 110 | 60-50 | −0.81 | −0.7% | 73.7% | 54.5% |
| 3 | 102 | 58-44 | +3.68 | +3.6% | 73.9% | 56.9% |
| **4** | 94 | 54-40 | **+4.19** | +4.5% | 74.1% | 57.4% |
| 5 | 88 | 47-41 | **−2.70** | −3.1% | 74.2% | 53.4% |
| 6 | 73 | 41-32 | +1.78 | +2.4% | 74.0% | 56.2% |

**Gate 4 is a peak, not a plateau.** Its immediate neighbour one grid step away
flips to −2.70u, which is exactly the shape CLAUDE.md §7 says to refuse: *"a
cell whose eight neighbours flip negative one grid step away is noise."* And the
gate does not fix what §4 said was broken — under gate 4 the model still claims
74.1% and delivers 57.4%.

So the +11.69u in §4's table was, in large part, **selection**: the games whose
first signal happened to arrive after the 4th were a favourable draw, and a gate
that forces the other games to wait does not inherit their record. That is the
question the replay existed to answer, and the answer is no.

### The control, and the second table

The replay bets 120 games where production bet 94. Under the first-signal lock
both write at most one bet per game, so the replay's set should be a SUPERSET of
production's — it sees every snapshot we kept, production saw only the passes it
managed to run. It is not quite:

    +39 games the replay bet and production did not
     13 games production bet and the replay does not   <- a defect in the replay

Those 13 are a fault in here, not in production, and they are unexplained.
Restricted to the 81 games both agree on:

| gate | bets | W-L | units | ROI | delivers |
|---|---|---|---|---|---|
| 1 (ungated) | 81 | 46-35 | +3.11 | +3.8% | 56.8% |
| 2 | 77 | 46-31 | +6.79 | +8.8% | 59.7% |
| **3** | 72 | 45-27 | **+9.86** | +13.7% | 62.5% |
| 4 | 66 | 40-26 | +6.89 | +10.4% | 60.6% |
| 5 | 62 | 34-28 | **−0.36** | −0.6% | 54.8% |
| 6 | 51 | 30-21 | +3.49 | +6.8% | 58.8% |

The ungated row is the control that matters and it passes: +3.11u over 81 games
against production's own +2.03u over 94 on the same window — the replay
reproduces the record it is standing in for.

**And the verdict hardens rather than softens.** The two tables pick DIFFERENT
best gates — 4 unrestricted, 3 restricted — and in both, the cell one step away
from the best is negative. A quantity whose optimum moves when you change the
sample, and whose neighbour flips sign either way, is noise, not a boundary.
Add the 13 unexplained games and this replay is not something to build a live
gate on at all.

**What this does NOT overturn:** the calibration split is unchanged and still
significant — early signals claim ~73% and deliver ~46%, in both time halves.
The model is genuinely broken early. The finding is that GATING is not the
repair; the repair is the probability, the same conclusion §2 and §3 reach for
the pitcher props. `mlb_live_total_runs` has never had a calibration map
promoted, and it is now the most obvious candidate for one.

**Still to come, and dated:** the cap comes off when `pitcher_k` and
`pitcher_hits` have 150 graded picks since their retrains and their maps are
re-promoted. At current volume that is roughly 2026-09-12 to 09-15.

---

## 10. The live calibration map — asked for, measured, NOT promotable yet

Matt, 2026-09-07: *"do the calibration map"*. Three things were wrong before one
could exist, two are now fixed, and the map itself is refused by the module's
own bar rather than by an opinion.

**Defect 3 of the same family: the fit could not SEE a live model.**
`fetch_graded` read `mv_scored_pick_outcomes`, which excludes `is_live` by
construction. So every live lane returned zero rows and the weekly pass printed
*"only 0 graded picks (need 150) — identity map, unfitted"* on every run since
it shipped. That reads as "not enough data yet" and means "this model is
invisible to me". `mlb_live_total_runs` has **126** graded BETs and was
reported as **0**. Fixed: live lanes read `picks` (BET rows, `dk_odds IS NOT
NULL`), and `CLEAN_WINDOWS` is not applied to them — it marks where the
dead-zone NONE rows were deleted, and a live lane never writes NONE, so its
population is that shape in every window and excluding the gap would cost 18 of
the 126 for no correction.

**What the four live lanes actually claim, now that they can be measured:**

| model | graded | overclaims by |
|---|---|---|
| `mlb_live_total_runs` | 126 | **+14.38pp** |
| `ncaaf_live_total` | 48 | **+15.27pp** |
| `ncaaf_live_win_prob` | 6 | +11.97pp |
| `nfl_live_prop` | 0 | — (no settled record, as CLAUDE.md §2 says) |

Every live lane in the repo is 12-15pp hot. None of it was visible yesterday.

**Defect 4: `classify_live_signal` decided on the raw probability** — the third
and last place `DECIDE_ON_CALIBRATED_PROB` had to reach. Fixed, and it is a
**no-op the day it ships** because no live lane has a promoted map. Every floor
now reads the same number, the EV floor included: a probability floor on the
calibrated number beside an EV floor on the raw one would be two cuts aimed at
different quantities.

**And the map itself: NOT promotable, on two independent counts.** Fitted as a
preview on all 126 graded bets:

```
n = 126                       (the module requires 150)
raw gap                       +14.38pp
held-out   18.48pp raw  ->  8.98pp calibrated
helps = True   transfers = FALSE      (the cap is 6.0pp)
```

It **helps and does not close** — the same verdict `mlb_prop_pitcher_er`
carries, whose own note reads *"publish it; do not build a threshold on it
yet"*. Under the promotion bar shipped today (helps AND transfers) it would be
refused even at n = 150.

There is a structural reason to expect that, and it is worth knowing before
waiting on it: a live lane writes BET and AVOID only, never dead-zone NONE rows,
and **live AVOIDs are never settled** — measured, 232 live AVOID rows and 0
graded against 213 graded BETs. So the fit sees one narrow band above the
model's own 0.70 probability floor. A Platt map on a single band is close to a
single offset, and its held-out transfer test may never clear 6pp however many
bets accrue. That is a property of the evidence, not a bar to lower.

**What promotion would do if it happened anyway.** The measured map takes a
claimed 0.74 to **0.598**, and the lane's cut is prob ≥ 0.70 / edge ≥ 0.14 /
EV ≥ 0.32, all swept on RAW numbers. A claim would need to be ~0.83 to reach a
calibrated 0.70. So promoting without re-sweeping the cut on calibrated numbers
takes the lane to approximately zero bets — the same trap the props were in,
run the other way. **Promotion and re-sweep are one decision, not two.**

**Left alone deliberately:** `MIN_GRADED` (150) and `MAX_TRANSFER_GAP_PP` (6.0).
Lowering either to make this map fit would be moving the bar to clear the jump.

---

## 11. "Highest conviction plays only" — the filter does not exist, and on the live lane it is inverted

mike, 2026-09-07: *"20 per day still seems way too high, run the analysis, want
the highest conviction plays only."*

The request assumes the board can be sorted by conviction. **It cannot — and the
one lane where a conviction sort is measurable sorts the wrong way round.** This
section is the measurement, so the next session does not re-derive it.

### 11.1 What the board actually is

Ground truth, MLB `signal_type='BET'`, 2026-08-29 → 09-07, per day:

| Lane | Model | Avg/day | 09-05 | 09-06 | 09-07 |
|---|---|---|---|---|---|
| live | `mlb_live_total_runs` | 9.1 | 9 | 11 | 6 |
| pre-game | `mlb_prop_pitcher_k` | 6.7 | 11 | 9 | 7 |
| pre-game | `mlb_prop_pitcher_hits` | 4.6 | 7 | 4 | 4 |
| pre-game | `mlb_prop_pitcher_outs` | 2.8 | 6 | 6 | 3 |
| pre-game | `mlb_f5_moneyline` | 0.9 | 0 | 0 | 2 |

**The dedupe and the interim cap are deployed but have not governed a board
yet.** Railway shows the worker on master at **2026-09-07T21:58Z**; every
pitcher-prop BET on the 09-07 board was written between 01:54 and 15:20 UTC,
before it. **09-08 is the first slate the cap applies to.** Replaying the merged
logic (dedupe on `player_id`, then top-3-by-claimed-EV within `k` and `hits`)
over 09-01 → 09-07:

| | 09-01 | 09-02 | 09-03 | 09-04 | 09-05 | 09-06 | 09-07 |
|---|---|---|---|---|---|---|---|
| pitcher-prop BETs today | 16 | 15 | 13 | 22 | 24 | 19 | 14 |
| after dedupe | 12 | 12 | 10 | 17 | 15 | 15 | 9 |
| after the cap | 9 | 8 | 5 | 7 | 12 | 11 | 5 |

Mean **17.6 → 8.1/day**. With live unchanged the board lands near **18/day**, not
20 — and pre-game stops being the larger half.

### 11.2 The model's own conviction, graded (08-24 → 09-06, priced BETs)

Claimed-probability bands. **The top band is not the best band in either lane**,
and the overclaim GROWS as the claim rises:

| Lane | Band | n | claims | delivers | gap | units |
|---|---|---|---|---|---|---|
| pre-game | <0.60 | 27 | .567 | .407 | −16.0pp | −2.99 |
| pre-game | 0.60-0.65 | 38 | .628 | .474 | −15.4pp | −2.60 |
| pre-game | **0.65-0.70** | 42 | .673 | .619 | **−5.4pp** | **+6.52** |
| pre-game | 0.70-0.75 | 28 | .723 | .536 | −18.7pp | −1.35 |
| pre-game | 0.75+ | 9 | .765 | .556 | −20.9pp | −0.58 |
| live | 0.65-0.70 † | 17 | .676 | .294 | −38.2pp | −7.33 |
| live | 0.70-0.75 | 54 | .724 | .593 | −13.1pp | +4.58 |
| live | 0.75+ | 34 | .770 | .618 | −15.2pp | +1.89 |

† **Already excluded.** `mlb_live_total_runs` has carried `min_prob: 0.70` since
2026-08-30 (mike), so all 17 of those rows predate the cut and none can recur.
They are here to show the shape, not as a floor to add.

Every unit of pre-game profit sits in the **middle** band. Sorting by the
model's confidence and taking the top selects the most overclaimed bets on the
board — which is what the calibration work already said, now visible in P&L.

**This does not contradict §11.4.** "The top of the confidence sort is bad" and
"top-3 by EV within a model is good" only look opposed: the pre-game 0.70+ band
is about 2 bets a day across every model, so a within-day top-3 draws almost
entirely from the middle band anyway.

### 11.3 The live lane: EV rank is inverted in BOTH halves

Ranking each day's `mlb_live_total_runs` BETs by claimed EV:

| Bucket | half A (08-24..30) | half B (08-31..09-06) | total |
|---|---|---|---|
| top 2 EV/day | −4.34u (n=12, 33.3%) | −0.91u (n=14, 50.0%) | **−5.25u / 26, −20.2%** |
| rank 3-4 | +0.65u (n=5) | −3.16u (n=14) | −2.51u / 19 |
| rank 5+ | +5.58u (n=14, 78.6%) | +4.21u (n=35, 62.9%) | **+9.79u / 49, +20.0%** |

Negative in both halves at the top, positive in both halves at the bottom. **A
live cap that keeps the highest-EV picks would keep precisely the losing ones.**

The interpretable form is price, not rank — the model bets only two price
populations and they diverge cleanly:

| DK price | half A | half B | total |
|---|---|---|---|
| −110 or longer | −1.04u (n=7, 42.9%) | −1.22u (n=7, 42.9%) | **−2.26u / 14, −16.1%** |
| −111 … −160 | +2.93u (n=24, 62.5%) | +1.36u (n=56, 57.1%) | **+4.29u / 80, +5.4%** |

Identical 42.9% win rate in both halves at the cheap price. High EV came from
the longer prices; the longer prices are the losers. **`mlb_live_total_runs` has
no `MODEL_MIN_ODDS` entry** — the props all carry −140.

**Weigh it as a hint.** Only **7** of those 14 sit under the current 0.70 cut
(−1.22u, 42.9%); the other 7 are pre-cut. A price floor and a raised `min_prob`
are also close to the same filter by construction — `LIVE_MAX_EDGE_CAP` 0.20
with `min_edge` 0.14 confines a −110 bet to p ∈ [0.70, 0.724]. Either lever
works, and either is a threshold change.

### 11.4 The pre-game cap does look selective, but it is one window

Replaying dedupe-then-cap over settled results:

| Bucket | n | win rate | units |
|---|---|---|---|
| dropped by dedupe | 28 | .536 | +0.60 |
| kept (top 3 by EV) | 60 | .533 | +3.78 |
| dropped by the cap (rank 4+) | 39 | .410 | −9.27 |

Split by half, **kept top-3** is −3.32u (n=7) then +7.10u (n=53), and the
dropped bucket has **no half-A rows at all** — the cap only binds on high-volume
days, which began 08-31. So this is a single window and fails §7's time split by
absence of data, not by contradiction. **Claim it as a volume control that may
also be selecting; do not claim it selects.**

### 11.5 CLV is the only positive per-model statement available

Current artifacts only, `clv_pct` on BETs:

| Model | n | mean CLV | t |
|---|---|---|---|
| `mlb_prop_pitcher_hits` | 10 | +2.41% | 2.99 |
| `mlb_prop_pitcher_outs` | 11 | +2.38% | 2.91 |
| `mlb_prop_pitcher_k` | 27 | +1.57% | 1.75 |

The props beat the closing line while losing money. That is a model picking the
right side and pricing its confidence wrong — a calibration problem, not a
selection problem, and an argument against pausing them.

`mlb_live_total_runs` has **zero** CLV rows, so the lane carrying half the board
is the one the fast measure cannot see.

### 11.6 A live threshold defect, found here and NOT fixed

`mlb_prop_pitcher_k` (0.58/0.08) and `mlb_prop_pitcher_hits` (0.54/0.08) carry
cuts their own config comments describe as swept on CALIBRATED probabilities
("floor-corrected calibrated sweep"; "on calibrated numbers at 0.54/0.08").
`model_calibration` today has `method IS NULL` for both — no candidate map, and
nothing in the promoted slot. **So both decide on raw numbers against a bar
tuned for calibrated ones.**

**This is a consequence of the endorsed-only migration run earlier today, and it
should not be discovered later.** Both models WERE promoted — `cal_applied` ran
11-13/day through 09-04 — went inert on 09-05 through the §2 defect, and
`promotions_endorsed_only_2026_09_07.sql` then demoted them. The recorded reason
is **`unfitted, 26/150` and `unfitted, 47/150`**: too few graded picks since the
retrain to fit a map at all, not a failed `transfers` verdict. The migration was
right — an unknown map must not decide a bet — but it leaves the mis-scaled cut
standing, and that is why the re-sweep below is a required decision rather than
housekeeping.

The scale is not small. Over 08-31 → 09-04, while the map was still being
applied, `mlb_prop_pitcher_hits` spanned raw **0.3214-0.7757** and calibrated
**0.4226-0.5774** — against a 0.54 cut, the calibrated number admits a narrow
sliver at the top of the range and the raw number admits everything above 0.54.

**This is not the inert-map defect fixed in §2**, which protected the promoted
slot; these models were never promoted (they fail `transfers`). Do NOT read it
as the cause of the volume rise — `k` went 6 → 7 → 11/day across 08-31 → 09-04
while calibration was still being applied, so the rise predates the map loss.

The fix is a decision, not a cleanup: **re-sweep the two cuts on raw
probabilities**, or refit maps that clear helps AND transfers and promote them.
Whichever, it is a threshold change and needs an `Updated-By:` trailer.

### 11.7 What this section does NOT claim

- Not that any MLB model is profitable. On current artifacts every one is
  indistinguishable from zero: `k` −12.9% ± 18.3pp (n=30), `outs` −22.3% ±
  28.9pp (n=12), `hits` +9.9% ± 30.2pp (n=11). **`mlb_live_total_runs` measured
  on its CURRENT cut** (game_date ≥ 08-31, so 0.70 applies to every row) is
  **−0.26u over 69 bets, −0.4% ROI**, claiming .739 and delivering .551 — flat,
  not the +1.88u/n=96 that an 08-24 window reports by including pre-cut bets.
- Not that the middle probability band should become the cut. It is one window,
  it is in-sample, and §7 requires a plateau.
- Not that the live price floor is established. n=14 on the losing side is a
  sign-consistent hint across two halves, not a swept threshold.
- Not that cutting to 5/day buys better bets. **Below roughly 8 pre-game and 9
  live, every further reduction is a volume guarantee and nothing more** — no
  measured ranking separates what remains.

---

## 12. The EV sweep, and the depth mike chose

mike, 2026-09-07, after reading §11: *"I just want the strongest ev picks for
highest overall profitability."* Reaffirmed after the caveat, so it is his call.
This section is what the sweep actually said.

**Read "EV" here as a RANK, not a price.** It is `p·b − (1−p)` on probabilities
running ~15pp hot (§11.2), so no number below is a forecast of return. It
orders picks, which is all the cap asks of it.

### 12.1 An EV FLOOR is not supported — the sweep has no plateau

Post-dedupe pitcher props, 08-24 → 09-06, cumulative min-EV floor. Every bet
already clears 0.14, so the sweep only bites above that:

| min EV | n | /day | ROI | units |
|---|---|---|---|---|
| 0.14 | 99 | 7.1 | +0.3% | +0.33 |
| 0.18 | 80 | 5.7 | +6.0% | +4.83 |
| 0.22 | 70 | 5.0 | +5.1% | +3.54 |
| 0.24 | 61 | 4.4 | +0.8% | +0.49 |
| 0.26 | 53 | 3.8 | +12.7% | +6.73 |
| 0.28 | 49 | 3.5 | +5.9% | +2.90 |
| 0.30 | 39 | 2.8 | +12.6% | +4.91 |
| 0.34 | 27 | 1.9 | −3.9% | −1.04 |

The adjacent cells look similar only because a cumulative sweep shares most of
its rows between neighbours. **Differencing them gives the marginal bucket,
and the marginals alternate sign**: [0.16,0.18) −4.53u, [0.22,0.24) +3.05u,
[0.24,0.26) **−6.24u**, [0.26,0.28) +3.83u, [0.28,0.30) −2.01u, [0.30,0.32)
+3.73u. EV is not monotone with profit anywhere in this window, so the +12.7%
at 0.26 is a peak between two troughs — exactly what §7 says not to ship. **No
`MODEL_MIN_EV` entry was added for the pre-game props.**

### 12.2 A DEPTH is supported, and it is the mechanism already shipped

"Strongest EV picks" is top-N by claimed EV per day — which is precisely what
`apply_prop_daily_cap` already does. The only question is N:

| Depth | n | /day | ROI | units |
|---|---|---|---|---|
| top 1 per model | 22 | 1.6 | +9.6% | +2.12 |
| **top 2 per model** | 43 | **3.1** | **+16.2%** | **+6.96** |
| top 3 per model | 62 | 4.4 | +6.5% | +4.00 |
| top 4 per model | 75 | 5.4 | +5.9% | +4.44 |

Top 2 is the maximum on **both** total units and ROI, which is unusual enough to
be worth stating: tightening past it costs profit as well as volume.

A pooled board-wide cap was measured too and is worse at every depth (top 2 =
+2.95u/20, top 3 = +1.31u/28) — the per-model version keeps a diversification
the pooled one throws away.

### 12.3 The models disagree about depth, and the uniform 2 is a deliberate choice

| Model | top 1 | top 2 | top 3 | uncapped |
|---|---|---|---|---|
| `mlb_prop_pitcher_hits` | +4.80 (7) | **+9.89 (14)** | +9.13 (21) | +5.43 (32) |
| `mlb_prop_pitcher_outs` | +0.30 (6) | +1.74 (11) | +0.90 (16) | **+3.69 (23)** |
| `mlb_prop_pitcher_k` | −2.98 (9) | −4.67 (18) | −6.04 (25) | −8.79 (44) |

`hits` wants 2. **`outs` is BETTER uncapped** — capping it costs ~2u on this
window. `k` is negative at every depth, so the cap reduces a loss rather than
finding an edge; taking only its strongest-EV picks does not rescue it.

Fitting each model its own depth scores +13.58u on this window and was offered
and declined: three parameters fitted to n=14/23/44 in a single window is the
overfit §7 exists to prevent. **The uniform 2 gives up ~2u of in-sample profit
to avoid it.** If `k` is still negative when its calibration map lands, that is a
pause decision on its own evidence, not a depth decision.

### 12.4 Live is closed to this approach — stated once, with the number

`mlb_live_total_runs` on its current 0.70/0.14 cut (game_date ≥ 08-31, n=69):
claimed EV spans **0.321 to 0.385**. The whole board sits inside a **6.4pp
band**, because the prob and edge floors plus the ~15pp inflation put it there.

Split that band at its median (0.341):

| | n | units |
|---|---|---|
| top half by EV | 35 | **−4.99** |
| bottom half by EV | 34 | **+4.72** |

A floor cannot bite (everything clears it), and a top-N would select the losing
half — the same inversion §11.3 found by daily rank and by price, now on the
current-cut population. **mike's call: keep the lane running unfiltered** at
~9/day, −0.26u over 69, and re-open the question when the map is fittable
(~09-10). Any cut here would be a guess dressed as a filter.

---

## 13. The inning gate is still unanswerable — and the reason is a finding of its own (2026-09-08)

mike: *"fix the replay defect and re-run."* The defect is diagnosed and the
replay now refuses to print a gate table while it stands. It is **not fixed**,
because the information needed to fix it was never recorded.

### 13.1 What the 13 missed games actually were

Not a coverage problem. Every game production bet has state rows, in-play DK
prices and a final score, and the missed games pair ~900 snapshots each. The
replay and production disagree about the **model probability**.

Measured on `MLB_2026-09-07_LAA_BOS`, holding the state, the DK line (7.5) and
the price (−118) fixed and varying only the pre-game stats snapshot:

| stats as of | lam | p_over(7.5) | decision |
|---|---|---|---|
| 2026-09-07 (what the replay reads) | 7.853 | 0.5263 | no bet |
| 2026-09-05 | 9.391 | 0.7199 | BET |
| **production recorded** | — | **0.7268** | BET |

### 13.2 The finding that matters more than the gate

Only **six** features differ between those two rows:

| feature | as of 09-07 | as of 09-05 |
|---|---|---|
| `home_team_era` / `home_bullpen_era` | 3.60 | 3.65 |
| `away_team_era` / `away_bullpen_era` | 4.21 | 4.25 |
| `home_runs_last_10` | 4.0 | 3.9 |
| `away_runs_last_10` | 3.2 | 3.4 |

State, weather and line are byte-identical. **A 0.05 change in team ERA and 0.1
to 0.2 in runs-per-last-10 moves expected remaining runs by 1.5 and the over
probability by 19 percentage points** — the difference between no bet and a bet
the model claims at 73%.

That is not a replay artifact. It is `mlb_live_total_runs` being pathologically
sensitive to inputs that drift daily by noise, and it is the most plausible
mechanical account yet of why the model claims ~73% and delivers ~54%: two runs
of the same model on the same game, a day apart, are close to different models.

### 13.3 Why bounding the replay on the pick timestamp does not fix it

`models.live_scorer._pregame_features` memoises on `(game_date, game_id)` in
process, evicting only other dates. A running live loop therefore freezes ONE
feature row per game, computed whenever it first saw that game — a moment
recorded nowhere. `DECISION_LOG_DIR` is NFL-only; no MLB live pick stores its
feature vector or its lambda.

And the obvious bound does not reproduce production either: the newest stats
snapshot available at the 17:55 UTC pick (as-of 09-07, written 10:05 UTC) gives
0.5263 against production's 0.7268. **The information is not in the database.**

**The prerequisite is therefore to record lambda and the feature row on every
live pick.** Until then the gate question cannot be answered by replay, and
§11's inning split stays an observation about a self-selected set.

### 13.4 A second defect, in PRODUCTION, not just the replay

`_pregame_features` passes `_get_dk_odds(conn, game_id, "h2h")` into
`build_mlb_game_features`. For `MLB_2026-09-07_LAA_BOS` that returns
`snapshot_type='in_play'`, home −10000 / away +1380, stamped **19:44 UTC — two
hours after the pick**, read as a pre-game price.

It does not feed the 18 features this model uses, so it is not the bug in §13.1.
But it is CLAUDE.md §6's pre-game/in-play separation broken **in the live
scoring path**, it affects every live model that does use odds-derived features,
and combined with the cache it means whichever in-play moneyline happened to be
current on the first pass is frozen in as "the pre-game line" for the game.
Found, not fixed.

### 13.5 What changed in the script

- Every drop is now named — `no live_game_state rows`, `no DK in_play totals`,
  `pre-game features unavailable`, `no state paired within 120s`, `no signal
  cleared the cut` — so a miss is a diagnosis rather than a silent absence.
- **The control now gates the tables.** It used to print beside them, and on
  2026-09-07 the tables were read and acted on with 13 games missing. The run
  exits 2 and prints nothing unless `--force`.

---

## 14. `mlb_live_total_runs` moves 12.8 points on a rounding error (2026-09-08)

§13.2 reported a 19-point probability swing from one game. mike: *"yes do all
4."* This is the distribution behind that anecdote, measured across every live
BET with `scripts/live_feature_sensitivity.py`.

### 14.1 The measurement

For each settled live BET: take the live state at the moment production picked,
keep the pick's **own** line and price, and recompute the model's probability
with the team-stats snapshot from the game date, one day earlier, and two days
earlier. State, weather, line and price are byte-identical across the three
runs — only the six season-to-date stats features move.

**60 games:**

| | swing in `p_over` |
|---|---|
| median | **0.1281** |
| mean | 0.1714 |
| p90 | 0.3375 |
| max | 0.4864 |

| threshold | games |
|---|---|
| swing > 2% | 59 / 60 (98%) |
| swing > 5% | 55 / 60 (92%) |
| swing > 10% | 41 / 60 (68%) |
| swing > 20% | 22 / 60 (37%) |

### 14.2 What the inputs actually did

Across **720 team-days** since 2026-08-15, a team's season-to-date ERA moves by
a mean of **0.0164 per day** (max 0.12), and `runs_last_10` by **0.295** (max
1.8). These are rounding-level movements in season aggregates — 140-odd games
in, one more game barely shifts them.

**So the model's over probability moves a median of 12.8 points in response to
inputs that move by hundredths.** The swing is not information arriving; it is
the model amplifying noise.

### 14.3 Why this outranks the inning gate

`mlb_live_total_runs` decides on `min_prob 0.70` and `min_edge 0.14`. **A 12.8pp
median swing is comparable to the entire decision margin.** Whether a given game
becomes a BET is substantially determined by which day's stats snapshot the
loop's in-process cache happened to freeze — which is why 14 games could not be
reproduced at all, and why the same pick reads 0.53 or 0.72 depending on nothing
that concerns the game.

This is the most plausible mechanical account of **claims ~73%, delivers ~54%**
(§11.2), and it makes several earlier results conditional:

- **A threshold sweep on this model is measuring the cache as much as the
  model.** The n=150 re-sweep in `docs/thresholds.md` should be read with that
  in mind.
- **The inning gate was never the fix.** A gate reorders which unstable
  probability fires first; it does not make it stable.

### 14.4 What this does NOT establish

- **Not that the other MLB models share it.** They use the same season-to-date
  features, so the same probe should be pointed at them, but that has not been
  done — CLAUDE.md §1b says assess a change against all of them, and this is the
  measurement half of that, not the conclusion.
- **Not a cause.** Whether it is the features (season aggregates that carry
  little signal at this point in a season), the target (remaining runs from a
  full-game-trained head), or the fit, is not established here.
- **Not a recommendation to pause.** The model's settled record on its current
  cut is −1.26u over 70 (z −0.12) — indistinguishable from zero, which is
  exactly what a model driven by input noise would look like, but it is not on
  its own grounds to stop it. That is mike's call.

---

## 15. The anchor the model never had (2026-09-08, mike)

§14 established the defect: `mlb_live_total_runs` moves a median 12.8
probability points on season-to-date stats that drift by hundredths a day. This
section is the fix, and — because a fix asserted is not a fix measured — the
gate it had to clear.

### 15.1 The diagnosis, restated as a missing feature

CLAUDE.md §1b states the live thesis in one line: a live total is priced
**relative to the starting line**. The book re-anchors its live total
mechanically off the pre-game number and the clock; the edge is predicting
where true remaining production deviates from that anchor.

`mlb_live_total_runs` did not carry the anchor. Its 18 features were nine
in-game state columns, six season-to-date stats (`home_team_era`,
`away_team_era`, `home_bullpen_era`, `away_bullpen_era`, `home_runs_last_10`,
`away_runs_last_10`) and three weather columns. The pre-game total appeared
nowhere. The six stats were standing in for the run environment the market had
already priced — and doing it badly enough to move the output 12.8 points on
noise.

### 15.2 Why the feature could not simply be switched on

`total_line` already existed in the MLB feature dict, and it was **empty on
both live paths**, for the same reason in each: it is filled from whichever
market the caller happens to pass as `odds_row`, and both live paths pass
`h2h`.

```
features["total_line"] = odds_row.get("total_line")   # h2h row -> None
```

The pre-game over/under model passes the `totals` row and gets a real number;
every h2h caller gets `None` from the same slot. A feature read from a slot
whose meaning depends on the caller is the "same understanding, same blind
spot" trap in CLAUDE.md §7 — it is filled in one path and empty in the other
with nothing raising.

So the plumbing came first, as its own change: a dedicated
**`pregame_total_line`**, sourced from the TOTALS market explicitly, passed by
both MLB builders (`build_mlb_game_features` and
`_build_mlb_features_from_bulk`) via a separate `totals_row` argument, and
supplied by both live paths — `live_scorer._pregame_features` at serve time and
`build_live_training_dataset` at training time.

### 15.3 Coverage, measured before anything was retrained

A feature that is mostly NULL is not a feature. Games with a leak-guarded
pre-game totals row from DK or `sbr_consensus`, by season:

| Season | Games | With pre-game total | % |
|---|---|---|---|
| 2019 | 2,758 | 2,758 | 100.0 |
| 2020 | 1,109 | 1,109 | 100.0 |
| 2021 | 2,686 | 2,400 | 89.4 |
| 2022 | 2,762 | 2,408 | 87.2 |
| 2023 | 2,763 | 2,436 | 88.2 |
| 2024 | 2,933 | 2,930 | 99.9 |
| 2025 (holdout) | 3,102 | 3,102 | 100.0 |

The 2021-23 gap does **not** delete training rows: the live trainer does
`df[feature_cols].values.astype(float)` with no `dropna`, so a missing line
becomes NaN and XGBoost routes it natively. It does mean the model learns a
"no line" branch that serving never reaches — serve-side coverage is **100% on
every completed day since 2026-08-24**.

One honest caveat: 2019-20 are covered by `sbr_consensus`, not DK, because DK's
feed does not reach back that far. The model absorbs a small systematic book
offset on those seasons.

### 15.4 Train/serve parity — and the bound that was wrong

Building `pregame_total_line` down both paths for the same games is the check
that the two agree. On **60 completed 2026 games: 60 identical, 0 different.**

Getting there turned up a real defect. The training path bounds "pre-game" with
`_is_pregame_snapshot`, which uses the ACTUAL first pitch (clamped by
`trusted_first_pitch`). The serving path's `_pregame_cutoff`, shipped in #606,
bounded on `commence_time` alone — the SCHEDULED start, which over 415 games
lands a mean **18.7 minutes after** the game actually begins. That is the
permissive direction: it admits a quarter-hour of in-play quotes as pre-game,
on the DECISION path, while training excludes them.

`_pregame_cutoff` now uses `pregame_cutoff_sql`, the same bound
`_pregame_cutoff_map`, the odds ingestor and `market_movement` already use.
Blast radius over all 415 games carrying a first pitch:

| Market | Games | Price changed | Price lost |
|---|---|---|---|
| totals | 415 | 0 | 0 |
| h2h | 415 | 3 | 0 |
| spreads | 415 | 3 | 0 |

**A divergence that was NOT this, and was not fixed.** Forty 2025 postseason
games showed 7-8 mismatches that survived the bound fix. They are historical
`sbr_consensus` rows carrying a **date-only** `snapshot_at`: on
`MLB_2025-10-13_SEA_TOR` the `open` (8.0) and `close` (7.0) rows tie exactly,
and the two paths break the tie differently — arbitrarily, and differently
between runs. It is confined to historical sbr rows; DK-priced games have no
ties, which is why 2026 is clean. It was left alone deliberately: preferring
`close` on a tie would rewrite `total_line` in **every** MLB model's training
set, which is a far wider change than this one and belongs to whoever measures
that. Logged in `docs/followups.md`.

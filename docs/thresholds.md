# Learning framework — thresholds, reviews, model adjustments

> **2026-09-09 — every cut below is applied at the DECISION price, not the
> DraftKings price.** (mike: *"we should remove DK only - we want best lines
> for us regardless."*) A pre-game pick is decided, sized and settled at the
> best bettable price at the DraftKings line (`picks.decision_*`;
> `docs/best_line.md` §4). No cut moved with the flip: the best-price sweep
> (`scripts/best_line_threshold_sweep.py`, 12 days of history) found nothing
> shippable, so each cut is simply 0.68pp looser on average (3.61pp at the
> extreme) at the better price. Every number in this file was swept on
> DK-implied edge; a re-sweep on `decision_edge` is the standing weekly task,
> and a cut moves only on the section-7 standards.


> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## The pre-registered forward test (2026-08-31)

Every cut shipped on 2026-08-31 was chosen by sweeping live picks on calibrated
probabilities. That method has a measured track record here, and it is not good:

| Model | Cut set | Claimed | Delivered after | Gap |
|---|---|---|---|---|
| `wnba_moneyline` | 07-02 | +31.9% | −16.1% (28 bets) | −48 pp |
| `wnba_prop_player_assists` | 07-11 | +19.3% | −21.9% (18) | −41 pp |
| `mlb_prop_pitcher_er` | 06-21 | +11.1% | −21.0% (35) | −32 pp |
| `mlb_prop_pitcher_k` | 06-20 | +17.1% | −8.1% (62) | −25 pp |
| `mlb_f5_moneyline` | 06-26 | +9.9% | −3.2% (92) | −13 pp |

**Pooled across every shipped cut: −4.7% over 258 forward bets.** (The other six
have 3–7 forward bets each and swing wildly positive — noise, not evidence.)
Lifetime across all settled pre-game BETs: −9.8% over 3,501.

A sweep picks the best of ~99 grid cells per model. The best of 99 noisy cells is
high because it is lucky as well as because it is good, and only a forward sample
separates those. The plateau requirement and the time split shrink that gap; they
do not close it.

So `tracking/threshold_review.py` runs the test that was agreed **before** the data
arrived, on the Railway worker, daily at 7:45am ET:

- **Milestones, not days.** It acts when the slate crosses 250 settled bets since
  `EPOCH = 2026-08-31`, then 500, 750… A rule re-evaluated every morning is a rule
  that eventually fires on noise — the same multiple-comparison mistake as the
  sweep it checks. The daily cadence is when it *looks*; the milestone is when it
  *decides*.
- **Pause rule.** At a review, a model with ≥ 50 settled bets of its own and ROI
  worse than −5% is paused.
- **No auto-unpause.** Coming back is a person's call with an `Updated-By` trailer.
  A rule that pauses and unpauses on the same noisy number just oscillates.
- **No re-sweeping at the review.** Finding a better cell in the data that just
  failed is fitting the noise twice.
- **Judge the slate, not the winners.** Keeping only the models that worked is the
  same selection bias one level up.

**Where the pause lives.** `model_auto_pauses`, read by `models/scorer.py` through
`_is_paused()` alongside `config.PAUSED_MODELS`. Not in config (a job cannot edit a
version-controlled file) and not in `model_action_thresholds` (the scorer reads
config directly, so a table pause would hide picks in the app while the model kept
betting — and the nightly `threshold_sync` overwrites that table anyway). Reading
the table fails **open**: an unreadable table leaves every model behaving as config
says, because turning a database blip into a platform-wide silence is a worse
outage than the one this prevents.

Kill switch: `RUN_THRESHOLD_REVIEW=0`. Verdicts post to `DISCORD_WEBHOOK_OPS`, and
log at CRITICAL if that is unset — "paused three models and told no one" must not
look like a quiet review.

---

## 17. Learning Framework — Wins, Losses, and Model Adjustments
Matt has asked Claude to track results, learn from them, and propose adjustments — always
explaining the reasoning before making any change. Matt has final approval on all changes.

### Signal Flip Rule (BET → AVOID between refreshes)

With ~42 refresh passes/day (6am full pipeline, hourly 7am–5pm, then every 10 minutes 6pm–11pm ET), a pick can flip signal between refreshes:
- Each refresh **deletes all pre-game picks** and re-scores from scratch
- If a pick was BET at noon but generates AVOID at 2pm, the AVOID replaces it in the DB
- **The AVOID should be honored** — do not bet a pick that has flipped to AVOID
- If a pick was BET but falls into the no-signal zone on a later refresh, it simply disappears

**Settlement rule:** Only picks with `signal_type = 'BET'` at game-start lock time are settled for P&L. AVOID picks are never settled and never count in win rate or ROI tracking. This is enforced in `paper_tracker.py` with `AND p.signal_type = 'BET'` in the settlement query.

### Action Threshold (what Matt actually bets)

Two layers — both defined in `config.py`:

> **Blanket -140 prop price floor (2026-07-22, Matt: "on any prop bets for MLB or WNBA, don't recommend model picks with a betting line over -140"):** EVERY MLB and WNBA player-prop model now carries a `-140` floor in `config.MODEL_MIN_ODDS` (was only pitcher_k / batter_rbi / batter_walks / batter_runs). A prop priced juicier than -140 (e.g. -150, -165) scores NONE, never BET. The per-row "+ DK ≥ -140 price floor" notes below predate this and only cover the original four; the floor now applies to all 17 MLB+WNBA props. Game markets (ML/totals/spreads/F5) and NBA/UFC/NHL/golf are unaffected.

**BET signal thresholds** (`MODEL_PROB_THRESHOLDS` / `MODEL_EDGE_THRESHOLDS`) — scorer uses these to generate a BET:

| Model | Min Prob | Min Edge | Notes |
|---|---|---|---|
| `mlb_moneyline` | 72% | 11% | 2026-07-04 FINAL: REVERTED to the v20260413 model + tightened to its proven live pocket — 2026 full-outcome 27 bets 21-6 +29.5% (0.70-0.72 x 0.11-0.12 corner all +10..+31%). The 07-04 retrain stays registered inactive (its 0.60/0.10 +25% 2025-OOS plateau grades -7.8% on the year's old-model picks — no green-2026 overlap). Old model now scores with fixed bullpen inputs. Re-evaluate the new model spring 2027 |
| `mlb_over_under` | **PAUSED** (cut kept 59%/7%) | | **2026-07-14 RE-PAUSED (Matt: "total runs model is 3-8").** The under-skew watch item materialized. Honest-era live record (>= 07-05) 3-8 / -529u on 11 picks, and it's not variance: mean model P(over) 0.454 vs realized 0.500, avg actual total 9.32 vs 8.59 line — the active model v20260704 was trained through June only and is anchored to a lower run environment than summer. NOT a threshold problem (0.59/0.07 is on the 2025-OOS plateau). Fix = retrain incl. settled July data (2019-2024+2026, holdout 2025); paused meanwhile. Unpause after retrain + fresh 2025 OOS sweep. |
| `mlb_runline` | 68% | 11% | 2026-07-02 CORRECTION #2: the 2026-06-28 loosen to 0.55/0.10 ("48-41 +14.9% plateau") was computed on a sign bug in `v_model_full_outcome_record` (away picks graded with +home_spread instead of −home_spread — flips every one-run game). Corrected (validated 30/31 vs settlements): 0.55/0.10 = 35-56 **-20.6%**; every prob floor <0.68 negative at volume. Corrected optimum **0.68/0.11 = 19 bets 13-6 +20.0%** (pocket 0.68-0.70 × 0.09-0.12 all +6..+20%; 9 away +1.5 / 10 away -1.5). Small sample. 2026-07-04: model swapped to v20260704_121650 (2019-2024+2026, holdout 2025, CalErr 2.95%); cut carried over UNVALIDATED (2025 has no RL prices, 2026 now in-sample; in-sample check 5-0 all away +1.5). Expect ~1-2 picks/month. **2026-08-21 DORMANT (not paused — cannot reach its own floor).** Max live prob across ALL of Aug 2026 = 0.625; last BET 2026-07-19. Weekly max_p 0.757 (wk 06-29) → 0.554 (wk 07-06) — a cliff at the 07-04 bullpen catch-up + 07-05 NaN-line fix, i.e. the pre-July probs this cut was chosen on were inflated by broken live inputs. Honest era (≥07-05, 354 graded, real prices; grading validated 63/63 matview + 138/138 sign convention) = **-6.93%**, both sides negative (away -6.5%/199, home -7.5%/155). No plateau anywhere in the 0.45-0.68 × 0.00-0.20 grid (best 0.51/0.02 = 34 bets 17-17 +8.6%, neighbours flip negative) → **do not loosen; retrain.** |
| `mlb_f5_moneyline` | 67% | 7% | 2026-06-26 full-outcome sweep (validated 104/104): 0.67/0.07 = 105 bets 59-31 65.6% +9.86% — MORE picks AND higher ROI than 0.71/0.0 (70 bets +9.49%) |
| `mlb_f5_over_under` | 65% | 15% | DISABLED — DK does not carry this market |
| `mlb_f5_runline` | 65% | 15% | DISABLED — DK does not carry this market |
| `mlb_prop_pitcher_k`     | 71% | 6% | **+ DK ≥ -140 price floor (2026-07-11)** — full-outcome: capped slice 25 bets 17-8 +20.3% vs +8.9% uncapped; the juice-heavy tail bled. See config.MODEL_MIN_ODDS |
| `mlb_prop_pitcher_hits`  | 65% | 12% | raised 60%/10% (2026-06-03): 14 bets -33.5%, still red (retrain) |
| `mlb_prop_pitcher_er`    | 62% | 8% | **PAUSED 2026-07-11** (Matt) — removed from display/consideration; still scores as NONE rows |
| `mlb_prop_pitcher_outs`  | 60% | 12% | 2026-06-03: 15 bets +3.7% — only profitable pitcher prop |
| `mlb_prop_pitcher_walks` | 60% | 12% | **PAUSED 2026-07-11** (Matt) — removed from display/consideration; still scores as NONE rows |
| `mlb_prop_batter_hits`   | 78% | 10% | raised 60%/8% (2026-06-03): 50 bets +2.0% (was -13%) |
| `mlb_prop_batter_tb`     | 88% | 12% | raised 85%→88% (2026-06-06): 24 bets +6.9% ROI |
| `mlb_prop_batter_hr`     | — | — | **RETIRED 2026-09-02 (matt).** Removed from `PROP_MODELS`, the app and every model total. Final record 256 settled BETs 42-214 (a ~17%-hit longshot market; the +EV filter was anti-predictive against DK's efficient longshot line). Was 22.5% prob-only (2026-06-26), already record-only and already excluded from the public record since 2026-07-04. Picks stay in the DB and keep grading (§1c). |
| `mlb_prop_batter_rbi`    | — | — | **RETIRED 2026-09-02 (matt).** Removed from `PROP_MODELS`, the app and every model total. Lifetime 293 settled BETs 214-79, but only ONE clears the 0.62/0.12 cut it was re-cut to on 2026-08-31 (mike), on the most floor-distorted sweep on the board (47.6% of rows refused by the -140 floor). Previously 47%/16% + -140 floor (2026-07-11); 2026-08-09 clean record after the is_live repair 30 bets 11-19 +14.8%. Picks stay in the DB and keep grading (§1c). |
| `mlb_prop_batter_runs`   | 47% | 16% | **UNPAUSED 2026-08-09** (Matt) — with the -140 floor grades 40 bets 21-19 +24.6%; robust edge≥0.16 band (+15..+25% across prob 0.45-0.50). Evidence is May-June (July/Aug dead-zone rows were destroyed by the retired NONE cleanup) — re-sweep after ~40 clean picks |
| `mlb_prop_batter_sb`     | 18% | 10% | UNCHANGED — v2 retrain 2026-06-12 lifted AUC 0.528→0.567 (opp_team_sb_allowed); still marginal, paper-only, re-sweep after live picks |
| `mlb_prop_batter_walks`  | 45% | 14% | **+ DK ≥ -140 price floor (2026-07-11)** — capped 18 bets +37.0% vs +2.5% uncapped (thin, directional) |

**Action filter** (`ACTION_THRESHOLDS`) — display filter for dashboard and Claude mobile:

| Model | Min Prob | Min Edge | Notes |
|---|---|---|---|
| `mlb_moneyline` | 72% | 11% | 2026-07-04 FINAL: reverted to v20260413 model, 0.72/0.11 = 21-6 +29.5% live |
| `mlb_over_under` | **PAUSED** (cut kept 59%/7%) | | 2026-07-14 RE-PAUSED — summer run-environment drift (live 3-8/-529u; model anchored low vs a 9.32-run summer). Retraining incl. July data; unpause after retrain + fresh 2025 OOS sweep (see BET-signal table above) |
| `mlb_runline` | 68% | 11% | 2026-07-02 CORRECTION #2: the 06-28 0.55/0.10 loosen rested on the view sign bug (corrected: -20.6%/91). New optimum 0.68/0.11 = 19 bets 13-6 +20.0%. 2026-07-04: model swapped to v20260704_121650, cut carried over unvalidated (very low expected volume). **2026-08-21: DORMANT — max live prob in Aug was 0.625 so the 0.68 floor is unreachable; honest-era record -6.93%. Cut held pending the 2019-2025 / holdout-2026 retrain + `scripts/mlb_runline_sweep.py`** |
| `mlb_f5_moneyline` | 67% | 7% | 2026-06-26 sweep: 0.67/0.07 = 105 bets 65.6% +9.86% (more picks + higher ROI than 0.71/0.0) |
| `mlb_prop_pitcher_k`     | 71% | 6% | + DK ≥ -140 price floor (2026-07-11): capped +20.3%/25 |
| `mlb_prop_pitcher_hits`  | 65% | 12% | raised 60%/10% (2026-06-03): still red |
| `mlb_prop_pitcher_er`    | 62% | 8% | **PAUSED 2026-07-11** (Matt) — removed from display/consideration |
| `mlb_prop_pitcher_outs`  | 60% | 12% | 2026-06-03: +3.7% — only profitable pitcher prop |
| `mlb_prop_pitcher_walks` | 60% | 12% | **PAUSED 2026-07-11** (Matt) — removed from display/consideration |
| `mlb_prop_batter_hits`   | 78% | 10% | raised 60%/8% (2026-06-03): +2.0% (was -13%) |
| `mlb_prop_batter_tb`     | 88% | 12% | raised 85%→88% (2026-06-06): 24 bets +6.9% ROI |
| `mlb_prop_batter_hr`     | — | — | RETIRED 2026-09-02 (matt) — see the row above. |
| `mlb_prop_batter_rbi`    | — | — | RETIRED 2026-09-02 (matt) — see the row above. |
| `mlb_prop_batter_runs`   | 47% | 16% | **UNPAUSED 2026-08-09** — with floor +24.6%/40 (May-June evidence; re-sweep after ~40 clean picks) |
| `mlb_prop_batter_sb`     | 18% | 10% | UNCHANGED — v2 retrain 2026-06-12 AUC 0.528→0.567; still marginal, paper-only |
| `mlb_prop_batter_walks`  | 45% | 14% | + DK ≥ -140 price floor (2026-07-11): capped +37.0%/18 (thin) |

*(Updated 2026-06-06 — MLB thresholds re-optimized from this season's settled BET picks (flat ROI at real DK odds) via a full prob×edge sweep, "pause nothing". 3 cuts changed vs 2026-06-03: over_under LOWERED to 68%/12% (+22.2%/18), batter_tb raised to 88%/12% (+6.9%/24), runline lowered to 68%/10% (only positive cut, +1.1%/12). In-sample tuning on small samples — forward ROI will regress; only the high-volume batter props (hits/runs/rbi), moneyline and f5_ml are statistically trustworthy. Pitcher props, SB, HR have no profitable cut — kept live at least-bad cut, flagged for a 2026 retrain. batter_sb v2 retrain (2026-06-12) lifted AUC 0.528→0.567 but stays paper-only. Prior values in git history.)*

All P&L reviews, win rate tracking, and ROI evaluation use **only these filtered picks**.

Query for filtered picks (evaluation starts 2026-04-14):
```sql
SELECT * FROM picks
WHERE signal_type = 'BET'
  AND game_date >= '2026-04-14'
  -- paste the output of:  python -m scripts.emit_threshold_sql
ORDER BY game_date DESC;
```

The per-model OR-block is **generated from `config.py`**, never transcribed —
`python -m scripts.emit_threshold_sql` prints it, reading `ACTION_THRESHOLDS`,
`PAUSED_MODELS`, `PROB_ONLY_MODELS` and `MODEL_MIN_ODDS` so it cannot disagree
with the scorer. The three hand-maintained copies this replaces had drifted by
2026-08-30: The block pasted into Claude mobile carries 42 model ids; `config.py` yields 41. Three are missing (`nba_over_under`, `nba_spread`, `nfl_prop_market`) and four are stale — paused models still listed, which surfaces picks the scorer has stopped making.

### UFC — the first every-pick evaluation (2026-09-05)

Run it yourself: `python -m scripts.ufc_threshold_sweep`.

**Why it did not exist before.** `mv_scored_pick_outcomes` grades the whole
scored universe for MLB and WNBA and **does not cover UFC**, and `picks.result`
is only ever written for BETs (`paper_tracker` settles `signal_type = 'BET'`).
So every UFC number anyone had ever quoted came from a BET-only sample — the
one CLAUDE.md §7 says cannot see what a looser cut would draw from. The script
grades all of it from `ufc_fight_log` + `games` with the same
`rounds_completed` helper production settles with: **135 graded picks** (13 BET,
60 AVOID, 62 NONE) against 10 settled BETs before.

**What it says. Do not loosen these cuts to get more picks into the channel.**

`ufc_total_rounds` (live cut prob ≥ 0.62, edge ≥ 0.08) is **negative in all 42
cells of the grid** — from −19% at the loosest (0.50/0.02, 18 bets) to −100% in
several. The live cut is **−41% over 6 priced bets**. There is no positive cell
to move to. §7's instruction for exactly this shape: say so and retrain, rather
than shipping the least-bad cell.

`ufc_moneyline` (live cut 0.65 / 0.08) is positive only at the loosest cuts and
only on tiny samples — best cell 0.50/0.02 at **+13.9% over 12 bets** — and the
time split kills it: every positive cell earns all of it in the EARLY half
(+67% to +104% on 1–3 bets) with the late half negative (−2% to −20%) in every
single one. No plateau, no sample, no case for a change.

**So the quiet UFC channel is a model problem, not a threshold problem and not
a delivery problem.** Delivery was the bug and is fixed (#505 publishes on
write; #513 verified the webhook points at the UFC channel). What is left is
that the models fire ~3 times on a 13-fight card and the one that fires most
loses money at every cut. The honest next step is a retrain of
`ufc_total_rounds`, or pausing it, and neither is a threshold move.

### UFC total rounds — the retrain did NOT fix it (2026-09-07)

mike: "retrain ufc_total_rounds", after the every-pick evaluation (#514) found
it negative in all 42 cells of its grid. **It was retrained, it was measured on
the regime it loses in, it is worse at the cut it would actually run at, and it
was NOT registered.** The live version is untouched.

**The retrain.** `python -m models.trainer --model ufc_total_rounds --seasons
2012..2025 --holdout 2026 --no-register`, i.e. the same recipe with 2025 folded
into training and the LOSING season as the holdout rather than 2025. Version
`20260907_095926`, 3,179 training rows, holdout 2026 = 193 fights:

| | accuracy | AUC | Brier | cal error | holdout_roi |
|---|---|---|---|---|---|
| retrained, holdout 2026 | 0.611 | 0.613 | 0.2394 | **0.0548** | 0.000 |
| live 20260619, holdout 2025 | 0.6386 | — | — | 0.0384 | 0.000 |

Two things to read there. The calibration error is **0.0548, above the 5%
go-live gate on its own**. And `holdout_roi` is 0.000 AGAIN — `_simulate_flat_roi`
finds no odds to simulate against, so the trainer says nothing about money for
this model, which is why the decision was never going to come from its metrics.

**The acceptance test, stated before the result was seen:** register only if the
2026 grid shows a positive PLATEAU around the live cut with calibration ≤5%.
`scripts/ufc_model_compare.py` scores both artifacts over the same 2026 fights
against the real pre-game DK total (56 of 193 fights carry one):

| cut | live model | retrained |
|---|---|---|
| **0.62 / 0.08 (the live cut)** | **−9.2% over 7** | **−40.0% over 6** |
| 0.60 / 0.08 | −36.5% over 10 | −29.4% over 9 |
| 0.65 / 0.08 | −27.9% over 5 | +20.1% over 3 |
| 0.58 / 0.10 | −7.7% over 10 | +16.0% over 8 |

The retrained model is **worse at the cut it would run at**, and its only
positive cells are at loose probability floors on 3–8 bets whose entire return
lands in the early half — early +39% to +86%, late −14% to −63%, in every one.
No plateau, no sample. That is the same shape §7 warns about and the same shape
#514 found.

**Conclusion: a retrain on this recipe reproduces the failure.** More seasons of
the same 18 features do not make this model's disagreements with DraftKings
profitable. The remaining options are a genuinely different model (features,
target, or recency weighting) or pausing `ufc_total_rounds` — and the second is
a decision, not a fix. Nothing is paused here.

### UFC total rounds — the rebuild, and the two limits that are not the model (2026-09-07)

mike: "rebuild it properly", after the straight retrain came back worse (#539).
Built, measured, **not registered**. `scripts/ufc_rounds_hazard.py`.

**What was built.** A round-level hazard model: `h_r = P(ends in round r | it
reached r)` and `q_r = P(ended before 2:30 | ended in round r)`, so
`P(over N-0.5) = Π(1-h_r for r<N) × (1 - h_N·q_N)`. One model, coherent for
every line DK posts, trained without needing a line at all — which also removes
the synthetic-line labels (`synthetic_round_total` fills 2.5/4.5 when DK never
posted one) that the binary model is partly fitted to. Recency weight
`0.5 ** ((2026 - season)/4)`, fixed a priori, never tuned on the holdout.

**All three models on the same 2026 holdout (193 fights, 56 of them priced):**

| model | cal error | at the live cut 0.62/0.08 | n |
|---|---|---|---|
| live `20260619` | **0.0368** | −9.2% | 7 |
| retrain `20260907` | 0.0548 | −40.0% | 6 |
| hazard rebuild | 0.0420 | −38.3% | 21 |

The hazard model runs long of overs (mean p 0.593 against a 0.539 base rate), so
it fires three times as often and loses three times as much. Accuracy 0.596,
AUC 0.572 — below the binary retrain on both.

**The two limits, measured the same day, and neither is in the model:**

1. **A third of every card cannot be modelled at all.** The hazard needs no
   line, but the binding constraint was never the line — it is fighter history.
   Both formulations train on the same **3,179** fights because a fight is
   skipped when either fighter has fewer than three prior bouts in
   `ufc_fight_log`. Of **916 distinct fighters on 2026 cards, 315 have no
   history rows at all**, and only **12** of those are name-matching artifacts —
   **303 are genuinely absent** from the log.
2. **The money test cannot tell two models apart.** DraftKings UFC totals have
   only been STORED since **2026-06-11**, so the evaluable population is 56
   priced fights and a cut selects 3–21 bets. At n=7 the noise band is about
   ±40 ROI points — wider than every difference in the table above.

**So UFC round totals are limited by DATA, not model form.** Three formulations
now land in the same place. The next move that could actually change the answer
is fight-history coverage — the 303 absent fighters — not a fourth model.
Pausing `ufc_total_rounds` is the standing recommendation; it is a decision and
nothing here is paused.

### Review Cadence

All milestones below count filtered picks from **2026-04-14** onwards only (v8 model evaluation start). Per-model thresholds: ML prob ≥ 72% / edge ≥ 12%; O/U prob ≥ 72% / edge ≥ 15%; RL prob ≥ 70% / edge ≥ 12% (re-optimized 2026-06-03 from settled-pick sweep — see threshold tables above).

| Milestone | What to review |
|---|---|
| Every 10 settled picks | Win rate and ROI by model — flag any model underperforming vs. expectation |
| Every 25 settled picks | Edge calibration — are predicted edges materializing as wins at the right rate? |
| Every 50 settled picks | Full recalibration check — should any model be retrained? |
| Any 5-pick losing streak | Investigate immediately — is it variance or a structural pattern? |

### What triggers a proposed change

Changes are never made without explaining the reasoning to Matt first. Triggers:

- **Win rate below 45% at 25+ picks on a model** — likely miscalibrated or feature-broken
- **High-edge picks (>10%) losing at >60% rate** — edge estimates are inflated; threshold may need raising
- **Systematic pattern** (e.g. all away spread losses, all O/U losses) — structural feature problem
- **CalError drifting above 5%** on live picks — model needs retraining on more recent data
- **New feature opportunity** identified from loss patterns (park factors, bullpen usage, etc.)

### Learning Log

*(Paper trading evaluation starts 2026-04-14 (v8 models). First review after 10 settled filtered picks from that date.)*

---

---

## Dated review criteria (2026-09-08, mike)

mike: *"also yes on n=75 critera."* Written BEFORE the data arrives, which is the
entire point — a criterion agreed after the fact is a re-argument, and §1b
already complains about threshold sweeps being re-litigated.

**These are not enforced by code, deliberately.** Nothing reads them; a dict in
`config.py` that no code path consults is exactly the guard-dead-code-satisfies
pattern §1b warns about. They are a commitment recorded where the evidence
lives, and `config.py` carries a comment pointing here.

**The population is the same for all three, and it is not "rows in `picks`":**

```sql
-- substitute the model_id and its artifact date
SELECT count(*) n,
       count(*) FILTER (WHERE result='WIN') wins,
       round(avg(CASE WHEN dk_odds>0 THEN 100.0/(dk_odds+100)
                      ELSE abs(dk_odds)/(abs(dk_odds)+100.0) END)::numeric,3) breakeven,
       round(sum(CASE WHEN result='WIN'
                      THEN (CASE WHEN dk_odds>0 THEN dk_odds/100.0
                                 ELSE 100.0/abs(dk_odds) END) ELSE -1 END)::numeric,2) units
FROM picks
WHERE model_id = :model AND signal_type='BET'
  AND result IN ('WIN','LOSS') AND dk_odds IS NOT NULL
  AND game_date >= :since;
```

**Breakeven is the mean DK implied probability of the bets actually taken** — not
a fixed 52.4%. These models bet at −140 floors, so their breakeven is well above
even money and a fixed number would mis-call every one of them.

| Model | Since | Trigger | Count at 2026-09-08 | Then |
|---|---|---|---|---|
| `mlb_prop_pitcher_k` | 2026-09-04 | n ≥ 75 | 35 (16W, bx .530, −4.81u, z −0.86) | pause if still below breakeven |
| `mlb_prop_pitcher_outs` | 2026-09-05 | n ≥ 75 | 15 (6W, bx .503, −3.92u, z −0.80) | pause if still below breakeven |
| `mlb_live_total_runs` | ~~2026-08-31~~ **2026-09-09** | ~~n ≥ 150~~ **n ≥ 75** | 0 on the current artifact (the 70 above were the June model, retired 09-09) | re-sweep the cut on the honest replay — see "mlb_live_total_runs cut, 2026-09-09" |

**Why `k` is not paused today**, given it is the largest single loss in the
30-day table at −18.30u/72: **that record spans two artifacts.** Split at the
09-04 retrain, the pre-retrain version is 13/37 (35.1%) at z = −2.36 and the
current one is 16/35 (45.7%) at z = −0.86. The significant loss belongs to a
model that no longer exists. Across ~12 models tested you expect ~0.6 hits at
p<0.05 by chance, so one pre-retrain z of −2.36 is roughly one lucky draw.

**Why `outs` is on the list at all**, having been treated as the healthy one:
the top-2 cap shipped in #572 was swept on the pooled 08-24 → 09-06 window,
where `outs` graded +3.69u uncapped. On its **current artifact** it is −3.92u
over 15. That does not invalidate the cap — different, smaller population — but
it earns the same checkpoint.

**Live carries an addendum.** It has no fast feedback measure at all (there is no
live CLV — `docs/live_betting.md` has the measurement), so the settled count is
the only clock. Report alongside the re-sweep the one live split that survived a
time split, **price bucket**: on the current cut, −110-or-longer is 3/7 (42.9%)
and −111..−160 is 35/62 (56.5%). n=7 is a hint, not a cut; it is listed so the
re-sweep starts from the one place worth looking rather than from nothing.

### The `k` / `hits` mis-scaled cut resolves to the refit, not a re-sweep

`mlb_prop_pitcher_k` (0.58/0.08) and `mlb_prop_pitcher_hits` (0.54/0.08) carry
cuts their config comments describe as swept on CALIBRATED probabilities while
`model_calibration.method` is NULL for both, so they decide on raw numbers
against a calibrated bar (`docs/mlb_volume_efficiency.md` §11.6).

A re-sweep on raw numbers was considered and rejected: it would replace a number
swept on 95 calibrated bets with one swept on 35 and 13 raw ones — **worse
evidence, not better**. The #572 cap already bounds the volume damage to 2/day
each. So the fix is the refit at n ≥ 150 graded since their retrains (47 and 26
at the last weekly pass), expected ~09-12 to 09-15; promotion and a cut re-sweep
are ONE decision, never two.


---

## `nfl_prop_market` cut, 2026-09-12 (mike): one floor → two, over 5pp → 6pp

mike: *"I asked you to find evidence for stat models any way you can... Figure
it out. Find the solution."*

**The two sides of this rule are no longer held to the same edge floor.** The
under keeps its pre-committed 5pp; the over is held to 6pp.
`config.NFL_PROP_MARKET_SIDE_EDGE`.

WHY, AND THE MECHANISM CAME FIRST. NFL prop lines lean over. Measured with no
model in the loop across 27,976 propositions 2023-25 at the best bettable price
(`scripts/nfl_prop_over_lean.py`): blind unders −1.29%, blind overs −7.91%, and
the under hit rate rises with how prominent and widely quoted the proposition is
— 49.7% / 52.2% / 52.6% by tercile against a 52.4% break-even — in all three
seasons separately. The gradient survives at a FLAT −110, so it is a lean in the
line rather than an artifact of shopping.

That predicted the split before the rule's own record was cut by side:

| side | bets | ROI | 90% CI | 2023 / 2024 / 2025 |
|---|---|---|---|---|
| over | 1,092 | +4.11% | (−0.8, +9.0) | +1.1 / +11.1 / +2.1 |
| under | 898 | +12.36% | (+7.2, +17.5) | +12.6 / +4.9 / +21.1 |

and the two curves move oppositely with the cut — over 5pp +4.1%, 6pp +15.8%,
7pp +20.5%; under 5pp +12.4%, 6pp +13.5%, 7pp +12.2%. Monotone on the side that
has to overcome the lean, flat on the side carried by it.

PAIRED, graded end to end:

| | bets | units | ROI | 90% CI | seasons |
|---|---|---|---|---|---|
| one floor (was) | 1,990 | +155.9 | +7.84% | (+4.3, +11.4) | +6.4 / +8.2 / +10.1 |
| **two floors (now)** | **1,248** | **+166.3** | **+13.33%** | **(+8.9, +17.8)** | +13.2 / +12.6 / +14.5 |

More profit from 742 fewer bets, all three seasons positive, and the season
spread tightens from 3.7pp to 1.9pp.

REPLICATION: the under-minus-over gap holds at three independent snapshot
offsets (`open` +8.3pp, `t48` +5.2pp, `t72` +2.2pp).

WHAT IS FITTED: the number 6, off this grid. The mechanism is not. If the over
cut is noise, overs revert to +4.11% and the pairing still returns ~+10.0%.
The one cell against it: 2025 overs at 6pp are −4.2% on 73 bets. Re-measure on
2026 settled bets (`docs/followups.md`). Full evidence:
`docs/nfl_prop_over_lean.md`.

NOT COPIED ACROSS SPORTS. `min_edge_by_side` is opt-in on the shared
`market_relative.find_bets`; the WNBA, MLB and NCAAF ports pass nothing and are
unchanged (CLAUDE.md §1b: mechanics are shared, cuts are measured per model).

## `nfl_opener_spread` cut, 2026-09-11 (mike): |dev| 1.0 → 2.0, gate 0.52 → 0.55

mike: *"the opener needs to be more aggressive, way too many picks, I need
statistical profitability - revise all open picks based on stricter criteria.
What's already settled is fine."*

**The answer to "statistical profitability" is that no cut of this rule has
it.** Stated first so the table below is not read as a finding. What the
sweep does establish is that the 1-point rule was flat, and 2.0 is the only
floor whose row stays positive across the edge grid.

Swept on the selection the live card actually runs — the twelve bettable
books (six of which exist in the 2020-2025 snapshot cache: draftkings,
fanduel, betmgm, williamhill_us, betrivers, fanatics), first qualifying
snapshot, one bet per game, Kelly-sized with sub-0.25u bets skipped — at the
juice actually quoted. `nfl/scripts/opener_cut_sweep.py`, zero credits.
The per-bet probability table it uses was fitted on this same sample
(`opener_spread.DEV_WIN_PROB`), so probabilities are partly in-sample; the ROI
is the realised return of the bets each cut would have taken.

| \|dev\| floor | edge floor | bets | W-L | ROI at price | 95% CI | seasons +ve |
|---|---|---|---|---|---|---|
| 1.0 (old) | 0 | 728 | 387-341 | −0.03% | [−6.9, +6.7] | 4/6 |
| 1.0 | 0.02 | 581 | 294-287 | −3.64% | [−11.2, +4.0] | 2/6 |
| 1.5 | 0 | 268 | 137-131 | −5.09% | [−16.1, +6.0] | 2/6 |
| 1.5 | 0.02 | 216 | 113-103 | −1.22% | [−13.7, +11.7] | 4/6 |
| **2.0 (new)** | **0** | **125** | **72-53** | **+3.97%** | **[−11.8, +19.1]** | **5/6** |
| 2.0 | 0.02 | 112 | 64-48 | +6.22% | [−10.4, +23.1] | 5/6 |
| 2.0 | 0.03 | 92 | 50-42 | +1.50% | [−17.5, +20.7] | 3/6 |
| 2.5 | 0 | 76 | 39-37 | −11.00% | [−30.3, +8.3] | 3/6 |
| 3.0 | 0 | 25 | 12-13 | −28.92% | [−59.0, +0.1] | 0/5 |

By season at 2.0/0: 2020 +0.5% (26), 2021 +18.0% (16), 2022 −28.4% (21),
2023 +9.1% (18), 2024 +22.1% (23), 2025 +5.5% (23).

Read it honestly: 1.5 and 2.5 are both negative, so 2.0 is a ridge rather
than a plateau (§7). Every interval spans zero. A 2.0 floor removes the 83% of
picks that measured −0.03% and keeps roughly 21 bets a season. It does not
make the model a proven earner, and the alternative on the table is pausing
it — that is mike's call, put to him in the session that shipped this.

Two more things the sweep showed, not acted on:

- **An edge floor of 0.04+ is strongly negative at every deviation** (n=38-45,
  −30 to −40%, 0/6 or 1/6 seasons). The bets the DEV_WIN_PROB table likes
  most on bettable books are the ones that lose. That is a calibration
  problem in the table, not a threshold, and it is worth a look before the
  next re-cut.
- On ALL 34 clean books the old 1.0 cut reads +3.68% on 929 bets — the
  difference from −0.03% is entirely books nobody here can bet at.

What changed: `nfl/models/opener_spread.DEPLOY_THRESHOLD` 1.0 → 2.0 (the card
stops writing sub-2.0 rows, rather than the gate hiding rows the card wrote);
`config` min_prob 0.52 → 0.55 for `nfl_opener_spread` (0.5557 at |dev| 2.0
clears, 0.5470 at 1.0 does not — the calibration's original intent, lowered on
2026-08-22); `model_action_thresholds` hand-set to 0.55 the same hour so the
app and Discord apply it before the 6am sync. The seven open Week-1 picks
below 2.0 were voided (`scripts/void_picks.py`, reason on each row); the
settled SF @ LA win stands; BUF @ HOU at |dev| 2.0 stands.

## `mlb_live_total_runs` cut, 2026-09-09 (mike): 0.70 → 0.72

> **Superseded 2026-09-10.** The replay this was swept on paired quotes
> without production's stale-quote guard (in `_get_live_dk_odds` since
> 2026-09-03, #458). On the quotes production can take, the table below is
> 20 bets 12-8, not 34 bets 25-9 — see "The forward check on fresh quotes"
> further down. The cut itself is unchanged pending mike's decision.

mike: *"go with 0.72 and land it."* Chosen from a backtest, not from a settled
record — his instruction, and the right one: the replay is the instrument.

**The model changed on 2026-09-09** (`v20260908_230751`: pre-game total line
in, six season-to-date stats out, honest grouped CV, NB1 tail —
`docs/mlb_volume_efficiency.md` §§15–18). Every threshold it carried was swept
on the OLD model's leaked probabilities, so the cut had to be re-measured on
the new one. `scripts/live_cut_sweep.py` does that: every live state since
2026-07-22 paired with the newest DK in-play total within the age bound, the
new artifact's probability at each, and the production decision — 0.20 cap,
prob floor, edge floor, EV floor, first-signal lock — applied at each grid cell.

**520 games, 47 slates, all of 2026 out-of-sample for the model** (trained
2019–2024, held out 2025). Grading checked against settled `picks.result` on
the 12 same-side overlap games: 12 agree. Zero replay defects, zero blind
moments among the 87 games the old model bet and the new one declined.

| prob / edge / EV | bets | W-L | delivers (90% CI) | breakeven | early / late (split 08-16) | per slate |
|---|---|---|---|---|---|---|
| 0.70 / 0.14 / 0.32 (was) | 48 | 33-15 | 68.8% [57–79] | 54.9% | 13-4 / 20-11 | 2.5 |
| **0.72 / 0.14 / 0.32** | **34** | **25-9** | **73.5% [60–84]** | 55.8% | **9-3 / 16-6** | **1.9** |
| 0.74 / 0.14 / 0.32 | 23 | 18-5 | 78.3% [62–89] | 56.8% | 5-3 / 13-2 | 1.4 |
| 0.76 / 0.14 / 0.32 | 8 | 6-2 | too few | — | — | 0.5 |

**Why 0.72.** It is the centre of a plateau, not a peak: 0.70, 0.72 and 0.74
are all positive and the delivered rate rises monotonically as the floor
tightens, which is what a calibrated probability should do. Its interval's
LOWER bound clears breakeven, and so do both time halves. **0.74 fails the
time split** — its early half is 5-3 with an interval [35%, 84%] that spans
breakeven; the cell's number is carried by the late half, which is the shape
§7 says not to ship. 0.70 is equally supported and simply yields more; 0.72 is
the volume mike asked for.

**Edge and EV floors are untouched, on measurement.** 0.14 → 0.16 changes no
cell at any probability (the prob and EV floors do all the cutting). 0.32 →
0.36 collapses the whole grid to 12 bets; 0.40 to zero. The EV floor is a
cliff, not a dial.

**"Per slate" is the post-08-29 rate, and the reason matters.** Before the
live price log went in, the DK in-play feed was sparse: the replay pairs ~90
snapshots a game before 08-29 and ~800 after. At a ninth of the resolution it
catches far fewer qualifying moments (6.8% of games get a bet vs 18.5%). The
early weeks undercount VOLUME for that reason only; they remain an honest
out-of-sample test of the probability, which is what the early/late column is
for.

**The 0.20 edge cap — measured the same evening, and it stays.** Every bet in
the backtest sits at edge 0.17–0.198, just under a cap set for the old model on
the theory that an implausible edge meant a stale snapshot. At 0.72 the cap
removes **101 of 126** first qualifiers; graded as if taken they go 77-24,
+44u, and uncapped the cut would run 126 bets at 95-31. That number is a trap,
and the trap has a mechanism: our state poller sees a run the instant it
scores, DK's in-play total lags it, and the replay pairs each state with the
newest price AT OR BEFORE it — so right after a scoring play the paired price
predates the run and the "edge" is the run itself, priced twice. The replay
grades on the final score and cannot see this. The test that can
(`cap_stale_test`, mike: *"run the stale quote test now anyway"*), on all 101:

| cap-removed candidates | n | graded as if taken |
|---|---|---|
| score changed between the paired price and the state — phantom | **57** | 51-6, +38.15u |
| quote current | 44 | 26-18, +5.87u |

Re-priced on the **next** DK snapshot, the median edge collapses from
**+0.254 to +0.061**. 35 of 98 keep an edge ≥ 0.14, and those go **19-16,
+0.48u** — nothing. The 63 whose edge evaporates are the ones that "won"
55-8: prices nobody could have taken. Median price age at those candidates
was 31s, p90 73s. **The cap is discarding phantom edges, not the model's
best bets. Not moved, on evidence.**

**The same measurement answers the freshness bound.** `LIVE_ODDS_MAX_AGE_SEC`
is 30s; in-play rows carry a `snapshot_at` stamped at fetch START and land a
mean ~30s later (p90 ~55s, identical on 09-08 and 09-09 — structural, not
load), so the scorer prices roughly half its passes and skips the rest as
stale. Loosening it would admit exactly the 30–70s-old quotes the table above
shows to be phantom. Left alone. It is, however, why replay volume is an
upper bound: the reconstruction evaluates every snapshot, production about
half of them.

**Re-sweep trigger: n ≥ 75 settled BETs on `v20260908_230751`** — about 40
slates at 1.9 a slate. Same population query as the dated criteria above.

## `mlb_live_total_runs` on the bought 2025 in-play history, 2026-09-10 (mike)

mike, 2026-09-09: *"why cant you test this against historical odds api data,
there are thousands of data points"* — then *"yes spend it, run the 2025
backtest."* The Odds API's historical endpoint stores a snapshot every ~5
minutes back to 2022 and an in-progress game's DK total is in it.
`data/ingestors/mlb_inplay_history.py` bought every 5-minute DK in-play totals
snapshot of 2025 (**260,190 credits** by the puller's own count, 210 slate
days, 22,178 served snapshots, 86,194 rows, 2,450 games), `plays` gained the
Stats API's per-play clock (`start_time` / `end_time`), and
`scripts/inplay_history_backtest.py` pairs each quote with the plate
appearance on the field at that instant (before-state; rollover across a
third out; `scripts/inplay_state_align.py`, tested) and runs the production
decision — the same `decide()` as the cut sweep — over the season. The active
artifact was trained through 2024, so **2025 is out of sample**, and at 2,386
games / 183 slates it is four and a half times the 47-slate sweep.

Two checks before reading a number. **Alignment:** over all 78,047 aligned
quotes, at the true clock DK's live total sits above the runs already scored
on 99.68% and (line − runs) tracks half-innings-left at r = 0.949; the clock
shifted −10 / +10 / ±30 min gives r = 0.876 / 0.882 / 0.708 and, shifted
forward, line-below-runs on 5.3% / 11.3%. **Grading (§7):** the plays' own
final (the last play's after-score) disagrees with the `games` row on 31 of
2,386 games — doubleheaders share one game_id so the row can hold game two's
score, and a make-up can overwrite a postponement — so every game is graded on
the plays' final, which is the game the quotes were aligned to. The bought
rows are `bookmaker='draftkings'`, which `data/prune_odds.py` never deletes.

**Two grids, because a quote can be stale.** Every DK market carries its own
`last_update`. When the score moved between that update and the snapshot the
"edge" is the run itself, priced twice — the same phantom-edge mechanism the
cap test found in production (above). "Fresh" = score unchanged since DK's
last update. Fresh-only is the production-realisable rule; all-quotes is what
the live loop pairs today.

| shipped cut 0.72 / 0.14 / 0.32 | bets | W-L | units | delivers (90% CI) | breakeven | early / late (split 07-01) |
|---|---|---|---|---|---|---|
| all quotes | 128 | 85-43 | +25.10 (+19.6%) | 66.4% [59–73] | 55.6% | 67.1% [58–75] / 65.4% [54–75] |
| **fresh quotes only** | 92 | 56-36 | +8.71 (+9.5%) | **60.9% [52–69]** | 55.6% | 60.7% [50–71] / 61.1% [47–73] |

Of the 128, 91 were fresh (55-36, +7.9u) and 37 stale (30-7, +17.2u): the
stale ones carry the all-quotes number. (The fresh-only row's 92 is the first
FRESH qualifier per game, so it is a different first bet in some games, not
the 91 fresh among the 128.) 107 of the 128 are overs. Median price −125,
median edge 0.191; 39 / 49 / 40 bets in innings 1–3 / 4–6 / 7+.

**The grid is flat where the 47-slate sweep rose.** Prob floor 0.70 / 0.72 /
0.74 / 0.76 delivers 66 / 66 / 68 / 65% on all quotes (183 / 128 / 66 / 31
bets) and 62 / 61 / 64 / 67% fresh (127 / 92 / 45 / 21). Tightening the floor
buys volume loss, not accuracy. The edge floor changes nothing at 0.16 and
little at 0.18; 0.20 empties every cell (the cap).

**Why: the probability is over-confident by ~8 points in the band the cut
lives in.** Calibration over the 147,728 fresh candidate sides, claimed →
delivered: 0.65–0.70 → 60.7%, **0.70–0.75 → 66.8%**, 0.75–0.80 → 66.2%,
0.80–0.85 → 89.1%; symmetric on the low side (0.25–0.30 → 33.2%). The rows
are quotes, not independent trials — a game contributes ~30 correlated
quotes — so the honest n is games contributing per band: 1,708 / 911 / 340 /
165 for the four bands above. A claimed 0.72 is a delivered ~0.64. That is why every floor delivers
the same rate: the floor selects on a number that is shifted, not sharpened.

**The 0.20 cap on this grid.** Uncapped, all quotes: 505 bets, 65.7% [62–69],
+115u — the over-cap edges deliver as well as the under-cap ones *when stale
quotes are allowed to count*. Fresh only, uncapped: 265 bets, **57.4%
[52–62]** against 53.6% breakeven, +18u. The cap stays: the wide edges are
mostly phantoms, and the ones that are not are thin.

**What this settles and what it does not.**
- The shipped cut is positive on 2025 in both halves on all quotes, and
  positive but with an interval that **does not clear breakeven** fresh-only.
  It is not moved (no cell does better; §7 says do not ship a peak), and it is
  not the 73.5% the 47 slates showed — that number was carried by stale
  quotes production declines (the forward check below).
- **Volume is not comparable across feeds.** The 5-minute grid sees ~30
  quotes a game; the live loop sees ~800. More quotes mean more first-qualifier
  chances, so per-slate here (0.5 fresh / 0.7 all) is not production's 1.9.
  This test says nothing about the delivered rate on the dense feed; the
  47-slate replay measured that WITHOUT the stale guard, and with it the
  dense feed's fresh record at this cut is 20 bets 12-8 (below).
- **Bettability is unverified.** The historical snapshot holds the price DK
  posted; whether the market was open at that instant is not in the data.
- **The next model update is a calibration map, not a cut** — fit on these
  out-of-sample sides (2,386 games), then re-sweep EV on the calibrated
  probability.
  That is a model update and needs mike's call (`docs/followups.md`).
- **Production already enforces fresh-only.** `_get_live_dk_odds` declines a
  quote whose `snapshot_at` (the market's `last_update`) predates the first
  sight of the current score (`quote_predates_score`). The replay and the
  sweep pair without that guard, so the FRESH row above is the
  production-faithful one and the all-quotes row overstates
  (`docs/followups.md`).

Rerun: `python -m scripts.inplay_history_backtest --season 2025 --rebuild`
(the candidate cache lives in the temp dir; ~8 minutes). Another season is
`mlb_inplay_history --season N --dry-run` first — 2024 would cost about the
same — then `--fill-times N N`.

### The forward check on fresh quotes, and the calibration map (2026-09-10, mike: "yes to all")

**The 47-slate sweep above was carried by stale quotes.** Production declines
a quote that predates the current score (`_get_live_dk_odds`,
`quote_predates_score`); the replay and the sweep never did. With the same
flag applied to the rebuilt 2026 cache (538 games, 49 slates, dense feed):

| shipped cut 0.72 / 0.14 / 0.32, 2026 | bets | W-L | units | delivers (90% CI) | breakeven |
|---|---|---|---|---|---|
| all quotes (what the sweep counted) | 38 | 28-10 | +12.18 | 73.7% [61–84] | 55.7% |
| of which stale (`runs_moved` > 0) | 18 | 16-2 | +10.41 | | |
| of which fresh | 20 | 12-8 | +1.77 | | |
| **first FRESH qualifier per game (what production can take)** | **21** | **12-9** | **+0.77** | **57.1% [40–73]** | 55.3% |

Measured directly on the 38, not by subtraction; the fresh-only row is a
different first bet in some games. On production-faithful quotes the model's
2026 record at this cut is 21 bets at +3.7%, and 2025's is 92 bets at +9.5%
with an interval [52–69] against a 55.6% breakeven. The 73.5% never existed.
The guard landed 2026-09-03 (#458), so the old artifact's production record
08-29..09-02 was made without it and 09-03..09-08 with it.

**The calibration map** (`scripts/live_calibration_sweep.py`): the repo's
two-parameter Platt fitted on 73,854 fresh 2025 preferred-side quotes,
a = 0.8578, b = −0.0787; 0.72 → 0.675, 0.80 → 0.752. Fitted on the older
half it takes the newer half's gap from +2.74pp to −0.19pp: helps AND
transfers, the two bars `promote()` sets. It has no candidate row (the
nightly fit sees 0 graded picks for this lane); `promote_external` writes it
to the promoted columns with its provenance.

**The re-sweep on the calibrated probability, fresh quotes, both seasons**
(cells with their breakeven; 2025 split 07-01, 2026 split 08-16):

| calibrated cut prob / edge / EV | 2025 fresh | early / late | 2026 fresh (forward) | early / late |
|---|---|---|---|---|
| 0.62 / 0.10 / 0.15 | 491 bets, 57.4% [54–61], +5.5%, breakeven 54.5% | 53.6% / 61.8% | 95 bets, 60.0% [52–68], +9.6% | 59.3% / 60.3% |
| 0.66 / 0.08 / 0.15 | 385 bets, 61.8% [58–66], +8.2%, breakeven 57.1% | 57.7% / 66.9% | 82 bets, 58.5% [49–67], +1.6% | 58.3% / 58.6% |
| 0.68 / 0.10 / 0.15 | 220 bets, 63.6% [58–69], +9.5%, breakeven 58.2% | 59.3% / 69.1% | 53 bets, 60.4% [49–71], +4.4% | 52.9% / 63.9% |
| 0.70 / 0.10 / 0.15 | 118 bets, 68.6% [61–75], +15.2%, breakeven 59.8% | 63.8% / 75.5% | 31 bets, 54.8% [40–69], −8.8% | 50.0% / 57.9% |
| 0.70 / 0.12 / 0.20 | 77 bets, 71.4% [62–79], +22.1%, breakeven 58.6% | 67.4% / 76.5% | 20 bets, 45.0% [28–63], −22.5% | 42.9% / 46.2% |

**No cell is a plateau that clears breakeven in both halves of both seasons.**
The 2025 early half sits at or under breakeven at every floor below 0.68; the
tighter cells that look best on 2025 are negative on 2026 at n ≤ 31. The one
cell positive in every split is the loosest, 0.62 / 0.10 / 0.15, at +5.5% and
+9.6% — thin, and its 2025 early half is −1.3%.

**The cut that reproduces today's decisions on the calibrated number** is
prob 0.675 / edge 0.10 / EV 0.24 (searched edge 0.08–0.13 × EV 0.18–0.26):
125 of 2025's 128 raw-cut bets and 36 of 2026's 38, 11 and 4 differing at
the boundary — the map's shift is not constant across probabilities, so no
constant floors reproduce the set exactly. Promoting the map with that
cut changes the published probability to the honest one and (almost) nothing
else. The options are in the session's reply; the choice is mike's.

Production's own record on the new artifact (`picks`, BETs graded) is the
number that supersedes all of this as it accrues. Two slates in it is 0
BETs, with the loop alive (a scorer pass every ~7 s, AVOIDs emitted, the
quote declined as stale on most passes -- pollers logs, 2026-09-11 01:25Z).

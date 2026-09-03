# Learning framework — thresholds, reviews, model adjustments

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

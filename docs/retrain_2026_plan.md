# 2026 Retrain Plan — Red MLB Prop Models

> Scoped 2026-06-06 (session 44), after the threshold re-optimization sweep showed
> 7 MLB prop models have **no profitable cut at any prob/edge threshold** since
> 2026-04-14. Thresholds can't fix them — they need retraining and/or feature work.
> This plan is the source of truth for that effort. Update as phases land.

## The 7 red models (settled BET picks since 2026-04-14, flat ROI at real DK odds)

| Model | Type | Live ROI | Diagnosis | Tier |
|---|---|---|---|---|
| `mlb_prop_batter_hr` | Poisson (prob-only) | **−65%** | Binary AUC 0.617 (discriminates fine) but DK juices HR overs — model edge is already in the price | 3 (structural) |
| `mlb_prop_pitcher_hits` | Poisson | **−33%** | High variance; missing opponent-lineup + defense (BABIP) context | 2 (features) |
| `mlb_prop_pitcher_walks` | Poisson | **−18%** | Missing umpire zone + opponent chase/contact context | 2 (features) |
| `mlb_prop_batter_sb` | Logistic | **−15%** | AUC 0.528 — barely > random; no catcher/pitcher-control features | 2 (rebuild) |
| `mlb_prop_pitcher_er` | Poisson | **−6.3%** | Flat across all cuts; stale window | 1 (refresh) |
| `mlb_prop_pitcher_k` | Poisson | **−1.5%** | Near-breakeven; stale window | 1 (refresh) |
| `mlb_prop_batter_walks` | Poisson | **−1.0%** | Near-breakeven; stale window | 1 (refresh) |

## Root cause shared by all 7: stale training window

`config.SPORTS["MLB"]` trains on **2019–2023**, holds out **2024**. These models were
last trained ~2026-05-13 on data ending 2023. Two full recent seasons (2024, 2025) of
actuals are loaded but unused. Critically, the **pitch clock landed in 2023** and
reshaped pace, IP, walks, and stolen bases — yet 4 of the 5 training seasons are
pre-clock (2019–2022). The models are calibrated to a game that no longer exists.

**Data readiness (verified 2026-06-06):** `player_game_log` and `player_savant_stats`
are fully loaded 2019–2025 (+ partial 2026). Retrain is feasible immediately.
Caveat: only **29 days** of `player_prop_odds` are stored — we cannot train "vs real
DK lines"; models train on game-log actuals and meet real lines only at scoring time.
Keep the hourly prop-odds ingestor running so a real-line validation set accrues.

---

## Phase 0 — Window refresh (config, low risk)

Bump MLB to match the WNBA convention so every future MLB retrain uses fresh data:

```python
# config.py  SPORTS["MLB"]
"train_seasons": list(range(2019, 2025)),  # 2019–2024
"test_season":   2025,                      # 2025 holdout
```

Only affects the **next** retrain of each model (no live behavior change until a model
is actually retrained). Validate live performance against 2026 settled picks separately.

## Phase 1 — Refresh retrain (no feature changes): `pitcher_k`, `pitcher_er`, `batter_walks`

These are marginal/moderate losers with sound feature sets. A fresh window alone may
flip them. Run (locally — retrains run on Matt's machine, ~10–20 min/model; or wire a
GitHub Action mirroring `wnba_train.yml`):

```bash
python -m models.trainer --model mlb_prop_pitcher_k     --seasons 2019 2020 2021 2022 2023 2024 --holdout 2025
python -m models.trainer --model mlb_prop_pitcher_er    --seasons 2019 2020 2021 2022 2023 2024 --holdout 2025
python -m models.trainer --model mlb_prop_batter_walks  --seasons 2019 2020 2021 2022 2023 2024 --holdout 2025
```

**Keep-or-revert gate:** holdout O/U accuracy ≥ prior version AND CalError not worse;
then re-run the live settled-pick sweep (Section 17 method) — keep only if a profitable
cut exists. If still no profitable cut, demote to Tier 2.

## Phase 2 — Feature rebuilds (code + retrain)

### `batter_sb` (AUC 0.528 — effectively random)
Current features lean on sprint speed + rolling SB. Stolen bases are a **matchup** event.
Add to `prop_feature_engine` batter-SB features:
- Opposing **catcher** caught-stealing% / pop time (needs a catcher-defense source).
- Opposing **pitcher** SB-allowed rate / time-to-plate (derive from game logs: SB allowed per opportunity).
- Base/lineup context (leadoff vs bottom, on-base likelihood ahead).
Then retrain. If AUC stays < 0.55, **pause** the model (it's unbeatable as specced).

### `pitcher_hits` (−33%) and `pitcher_walks` (−18%)
Add opponent-quality and environment features:
- Opponent lineup contact% / chase% / K% (hits & walks both swing on this).
- Umpire zone size / walk tendency for `pitcher_walks` (umpire table exists; the K model's
  `ump_k_plus_minus` showed career-average encoding is too coarse — use **ASOF rolling**
  umpire rates this time).
- Park + team defense (BABIP proxy) for `pitcher_hits`.
Retrain with the Phase 0 window. Same keep-or-revert gate.

## Phase 3 — `batter_hr`: structural decision (needs Matt)

The HR model discriminates well (AUC 0.617) but loses 65% because it's **prob-only** and
DK prices the over efficiently. Threshold/feature work won't help if the edge is already
in the line. Options, in order of preference:
1. **Edge-gate it:** remove from `PROB_ONLY_MODELS`, only BET when `model_prob − DK_implied ≥ X`.
   Requires DK HR lines to be present (often missing — see Section 11). Likely fires rarely.
2. **Pause** `mlb_prop_batter_hr` until a real edge is demonstrated on accrued prop-odds history.
3. Keep as-is (informational only). ← current state, −65% if bet.

Recommend (1) gated very tight, else (2). Decide with Matt before coding.

---

## Acceptance criteria (all phases)

A retrained model goes live only if, on the 2025 holdout AND the 2026 live settled picks:
- a prob×edge cut exists with **positive flat ROI** at meaningful volume (≥12 bets), and
- holdout CalError is not materially worse than the prior version.

Otherwise: keep the prior version live at its least-bad cut (current state) and leave the
model flagged here. No model is paused without Matt's sign-off.

## Open questions for Matt
1. Run retrains locally, or should I build an `mlb_prop_retrain.yml` GitHub Action (like
   `wnba_train.yml`) so they're triggerable from mobile?
2. Phase 3 HR: edge-gate, pause, or leave informational?
3. OK to apply the Phase 0 window bump now (affects only the next retrain of each model)?

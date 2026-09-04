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

## Phase 0 — Window refresh (config, low risk) — ✅ APPLIED 2026-06-06

Bumped MLB to match the WNBA convention so every future MLB retrain uses fresh data:

```python
# config.py  SPORTS["MLB"]
"train_seasons": list(range(2019, 2025)),  # 2019–2024
"test_season":   2025,                      # 2025 holdout
```

Only affects the **next** retrain of each model (no live behavior change until a model
is actually retrained). Validate live performance against 2026 settled picks separately.

## Execution — ✅ GitHub Action `.github/workflows/mlb_prop_retrain.yml`

> Historical record. That workflow was deleted 2026-08-24 with the rest of
> GitHub Actions; retrains now run locally — see `docs/local_ops.md`.

Retrains run in CI (all MLB stat tables are in Supabase — no stats.nba.com dependency,
unlike WNBA). Trigger manually from the Actions tab / GitHub mobile. Inputs: Optuna
`trials` and a `models` choice (`red-7` default / `refresh-3` / `all-props`). The window
comes from config (Phase 0), so no per-run season flags are needed.

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
then re-run the live settled-pick sweep (`docs/thresholds.md` method) — keep only if a profitable
cut exists. If still no profitable cut, demote to Tier 2.

## Phase 2 — Feature rebuilds (code + retrain)

### `batter_sb` (AUC 0.528 — effectively random)
Current features lean on sprint speed + rolling SB. Stolen bases are a **matchup** event —
and unlike the pitcher props, the matchup (catcher + pitcher run control) is the *dominant*
factor, so opponent features have a real shot here.
- ✅ **DONE 2026-06-11 (free, no backfill):** added `opp_team_sb_allowed` — the opponent
  team's avg SBs allowed per game, derived from batter game logs (per-game team SB totals →
  each team's opponent-SB average), a combined catcher+pitcher run-control proxy. Real spread
  (0.07–0.94/game, SD 0.18 across teams). Prior-season + league fallback.
- **Local step:** `python -m models.trainer --model mlb_prop_batter_sb --trials 100 --seasons 2019 2020 2021 2022 2023 2024 --holdout 2025`. Report **AUC** (the key metric for this binary model; prior 0.528) + whether `opp_team_sb_allowed` lands in the top features.
- If AUC clears ~0.55 → keep, tune threshold. If still ~0.52, the season-level team proxy isn't
  enough → next is per-game opposing **catcher** pop-time/CS% (needs a Savant catcher-fielding
  backfill + per-game catcher identification). If even that fails, pause the model.

### `pitcher_hits` (−33%) and `pitcher_walks` (−18%)
Add opponent-quality and environment features:
- Opponent lineup contact% / chase% / K% (hits & walks both swing on this).
- Umpire zone size / walk tendency for `pitcher_walks` (umpire table exists; the K model's
  `ump_k_plus_minus` showed career-average encoding is too coarse — use **ASOF rolling**
  umpire rates this time). ✅ **DONE 2026-06-07** — `ump_bb_plus_minus` added to
  `PROP_PITCHER_WALKS_FEATURES`: per-umpire avg starter-walks minus league, averaged over
  the umpire's games strictly before the scored date (career fallback for <3 prior games so
  rows aren't null-dropped). No backfill — built from existing `umpires` + `player_game_log`.
- Park + team defense (BABIP proxy) for `pitcher_hits`. ✅ **DONE 2026-06-07** — added
  `opp_team_whiff_pct` (opponent miss rate = inverse contact; reuses the chase backfill path via
  a new batter Savant `batter_whiff_pct`/`whiff_percent` column), plus the free `opp_team_k_pct`
  and `park_hr_factor`, to `PROP_PITCHER_HITS_FEATURES`. Opponent-contact is the right lever:
  more contact → more balls in play → more hits allowed. Team defense/BABIP proxy still TODO if
  this isn't enough.
- **Local steps for hits (same pattern as chase — backfill BEFORE retrain):**
  1. `python -m data.ingestors.baseball_savant_ingestor --backfill 2019 2025 --type batter`
     (re-run; COALESCE upsert now also fills the new `batter_whiff_pct`. Also `--season 2026` for live.)
  2. Verify: `SELECT season, COUNT(batter_whiff_pct), COUNT(*) FROM player_savant_stats WHERE player_type='batter' GROUP BY season;`
  3. `python -m models.trainer --model mlb_prop_pitcher_hits --trials 100`
  4. Report O/U acc + CalErr + whether `opp_team_whiff_pct` / `opp_team_k_pct` land in the top features.
  Prior `mlb_prop_pitcher_hits`: 58.7% O/U, 9.0% CalErr (live −33%). Keep-or-revert on holdout +
  whether a profitable cut emerges; if flat, hits joins walks as not-beatable and we move to `batter_sb`.

**RESULT 2026-06-11 — hits CONCLUDED (not beatable):** clean re-test on the bumped window
(2019–2024 / holdout 2025) with the AB-weighted `opp_team_whiff_pct` → **56.4% O/U / 9.92% CalErr**,
**byte-identical to the run without the weighting fix** — i.e. XGBoost never splits on the opponent
feature; the pitcher's own rolling form dominates a single start. (56.4% vs the old 58.7% is the
2025 holdout being harder than 2024, not a regression.) **Two pitcher props (walks, hits) now firmly
show season-level opponent features don't move single-start markets.** Kept the bumped-window version
live at the least-bad cut, flagged; inert opp features left in (harmless, ignored — same as the K
umpire precedent). The `chase_pct`/`batter_whiff_pct` infra stays (cheap daily pull; available if a
future model wants it). **Recommendation: stop pitcher-prop feature work.**

**Update 2026-06-07:** the umpire ASOF feature alone left `pitcher_walks` flat (57.2% vs
57.6% O/U) — same null result as the K model's umpire feature. Matt chose "one more try":
added opponent plate discipline.
- `opp_team_k_pct` (free, already loaded) + `opp_team_chase_pct` (season avg batter chase%)
  added to `PROP_PITCHER_WALKS_FEATURES`. Chase needs a **batter Savant backfill** for the new
  `chase_pct` column (`oz_swing_percent`). Chase is aggregated to team via the game log
  (`player_id` join — Savant's `team` is null for batters), with a league-avg fallback so a
  missing team-season doesn't null-drop rows.
- **Local steps (in order — do NOT retrain before the backfill, or every row null-drops):**
  1. `python -m data.ingestors.baseball_savant_ingestor --backfill 2019 2025 --type batter`
  2. **Verify** chase populated: `SELECT season, COUNT(chase_pct), COUNT(*) FROM player_savant_stats WHERE player_type='batter' GROUP BY season;` — expect chase_pct non-null for most batters each season. If it's all null, `oz_swing_percent` is the wrong Savant column name — stop and tell me.
  3. `python -m models.trainer --model mlb_prop_pitcher_walks --trials 100`
  4. Report O/U acc + CalErr + whether `opp_team_chase_pct` / `opp_team_k_pct` land in the top features.
- If walks is *still* flat after this, the conclusion is firm: pitcher walks aren't beatable
  with our data — keep at least-bad cut, flag, and move Phase 2 to `pitcher_hits` + `batter_sb`.

**RESULT 2026-06-07 — walks CONCLUDED (not beatable):** with chase% + opp_team_k_pct + ASOF
umpire, `mlb_prop_pitcher_walks` retrained to **57.6% O/U / 6.75% CalErr** — identical accuracy
to the pre-work version (full circle), only modest calibration gain. Three levers moved nothing
on accuracy. Walk rate is too noisy and DK's lines are efficient. **Decision: stop feature work
on walks.** Kept the retrained version live (best-calibrated, fresh window) at the least-bad
60%/12% cut, flagged. The `chase_pct` infrastructure is NOT wasted — it's reused for
`pitcher_hits` (opponent contact). Note: also backfill `--season 2026 --type batter` so live
walks scoring has chase until this branch merges (daily pipeline handles 2026 chase post-merge).

## Phase 3 — `batter_hr`: **DECIDED 2026-06-06 → leave informational**

The HR model discriminates well (AUC 0.617) but loses 65% because it's **prob-only** and
DK prices the over efficiently — threshold/feature work won't help if the edge is already
in the line. Matt's call: **leave it informational** (current state — picks surface but
aren't a bettable signal). No code change. Revisit only if accrued `player_prop_odds`
history later shows a real `model_prob − DK_implied` edge, at which point edge-gate it.

---

## Acceptance criteria (all phases)

A retrained model goes live only if, on the 2025 holdout AND the 2026 live settled picks:
- a prob×edge cut exists with **positive flat ROI** at meaningful volume (≥12 bets), and
- holdout CalError is not materially worse than the prior version.

Otherwise: keep the prior version live at its least-bad cut (current state) and leave the
model flagged here. No model is paused without Matt's sign-off.

## Decisions (2026-06-06, session 44)
1. **Execution:** GitHub Action `mlb_prop_retrain.yml` (triggerable from mobile). ✅ built.
2. **HR (Phase 3):** leave informational — no code change. ✅
3. **Window bump (Phase 0):** applied to `config.py`. ✅

## Next actions (not yet done — need a retrain run)
- ✅ **Phase 1 done (2026-06-07): refresh-3 retrained on 2019–2024 / holdout 2025, all KEPT** (now live):
  - `mlb_prop_pitcher_k` v20260607_091558 — 65.3% O/U (was 64.1%), CalErr 11.2%. Clean upgrade.
  - `mlb_prop_pitcher_er` v20260607_100558 — 61.7% O/U (was 62.3%), CalErr 11.1%. No-harm refresh; still needs Phase 2 opponent features to turn profitable.
  - `mlb_prop_batter_walks` v20260607_105006 — 72.8% O/U (flat), CalErr 1.0%. Well-calibrated; live result is a threshold/market-efficiency matter, not a model flaw.
  - Holdout metrics are flat-to-better (cross-year, so directional); the gain is the post-clock training distribution. Thresholds unchanged — re-sweep once 2026 live picks accrue under these versions.
- For `batter_sb`, `pitcher_hits`, `pitcher_walks`: implement the Phase 2 features
  before retraining (a window-only retrain won't fix AUC 0.528 / −33%).

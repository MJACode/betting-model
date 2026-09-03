# MLB — model state and player-props plan

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 11a. READ THIS BEFORE ANY NUMBER BELOW — the 2026-09-03 leak repair

**Every AUC, CalError and backtest figure in §11 and §11's F5 section was
measured against leaked tables and is not real.** Two tables carried each
entity's SEASON-FINAL numbers on every historical row:

* `mlb_team_stats` — two snapshots per season, both holding the completed
  season (rebuilt 2026-09-03, Phase 1).
* `mlb_pitcher_stats` — each starter's season-final ERA on EVERY start. Aaron
  Nola's 33 rows for 2024 all read 3.57. `d_starter_era` + `d_starter_era_last3`
  are 40% of `mlb_f5_moneyline`'s importance (rebuilt 2026-09-03, Phase 2).

Full evidence: `docs/team_stats_leak.md`.

### The honest numbers

Walk-forward, train ≤ T and test T+1, on the rebuilt tables:

| model | 2021 | 2022 | 2023 | 2024 | 2025 | **2026** | mean | was |
|---|---|---|---|---|---|---|---|---|
| `mlb_moneyline` | 0.547 | 0.563 | 0.570 | 0.538 | 0.576 | **0.559** | **0.559** | 0.60-0.62 |
| `mlb_f5_moneyline` | 0.523 | 0.583 | 0.567 | 0.565 | 0.566 | **0.536** | **0.557** | 0.63-0.64 |
| `mlb_runline` | 0.513 | 0.572 | 0.579 | 0.460 | 0.618 | **0.588** | 0.555 | 0.53-0.64 |
| `mlb_over_under` | 0.514 | 0.516 | 0.505 | 0.519 | 0.502 | **0.486** | **0.507** | 0.55-0.57 |

**The real MLB signal is worth about 0.55-0.56, not the 0.60-0.64 the leaked
seasons advertised.** The leaked seasons collapsed to the honest season's level
in every model; `mlb_moneyline`'s one honest season ROSE (0.529 → 0.559),
converging on the same place from the other side.

### What changed as a result (2026-09-03, mike)

* **`mlb_over_under` PAUSED.** Below a coin flip in the only honest season
  (0.486), zero of six folds clearing 0.55. Its unpause path is a rebuilt model,
  not a threshold — no cut rescues a classifier that does not rank.
* **`mlb_runline` stays paused.** Mean 0.555 hides a 0.460-0.618 swing with the
  base rate moving 0.364 → 0.495, so the target mix is itself changing. The
  folds do not agree and the mean is not actionable.
* **`era_last3` is now a TRUE rolling window** (27 × ER / outs over the last
  three starts), shared by the daily ingest and the rebuild via
  `data/pitcher_rates.py`. It used to be `AVG(era)` over the last three stored
  rows — a smoothed restatement of `era`.
* **`mlb_f5_moneyline` retrained** on the rebuilt tables. See the F5 section.

## 11. Current Model State (as of 2026-05-08 — v8 MLB + v1 F5 active)
### MLB Models — v8 active (retrained 2026-04-14)

| Model | AUC | CalError | Gate (≤5%) | Holdout rows | Notes |
|---|---|---|---|---|---|
| `mlb_moneyline` | 0.619 | 2.12% | PASS | 1,719 | v8 retrain 2026-04-14 |
| `mlb_over_under` | 0.575 | 4.64% | PASS | 1,882 | v8 retrain 2026-04-14 |
| `mlb_runline` | 0.629 | 5.56% | borderline | 1,712 | v8 retrain 2026-04-14 — above 5% gate but improved from 5.87% |

- Holdout season: 2024. Train seasons: 2019–2023.
- CalError measured with min_samples=20 per bin — standard ECE practice.
- All three models improved AUC vs v6 (0.595→0.619, 0.568→0.575, 0.592→0.629).
- Runline CalError above gate is acceptable-for-now: no backtest bets (no historical runline prices),
  model improves year-over-year, secondary market.

**Feature set (v8 — active):**
- Starter diffs (H2H + runline): `d_starter_era`, `d_starter_k9`, `d_starter_bb9`, `d_starter_era_last3`, `d_starter_k9_last3`
- Starter absolutes (totals): `home/away_starter_era`, `home/away_starter_k9`
- Bullpen workload: `d_bullpen_ip_last3`, `home/away_bullpen_ip_last1`, `home/away_bullpen_ip_last3`
- Weather (totals): `wind_out_component`, `temp_f`, `is_dome_game`
- Weather (runline): `wind_out_component`, `is_dome_game`
- Weather sources: `wind_out_component = wind_mph × cos(wind_dir − hp_to_cf_bearing)`, positive = blowing out toward CF
- Dome logic: fixed domes always closed; retractable closes if temp_f < 50 or precip_mm > 0.3
- Pitcher sources: MLB Stats API (ERA/K9/BB9/WHIP/HR9) + Baseball Savant CSV (SwStr%/CSW%/xERA as xFIP proxy)
- Top v8 moneyline features: `d_starter_era_last3` (14.0%), `d_starter_era` (10.1%), `d_bullpen_era` (8.2%), `d_woba` (7.1%), `d_team_era` (6.5%)
- Top v8 O/U features: `home_starter_era` (8.8%), `away_starter_era` (7.2%), `total_line` (6.6%), `is_dome_game` (5.6%), `temp_f` (5.3%)
- Top v8 runline features: `d_starter_era` (11.4%), `d_starter_era_last3` (10.1%), `d_bullpen_era` (8.3%), `d_team_whip` (6.1%), `d_woba` (6.1%)

**v6 backtest results (2022–2024, 7% ML / 8% O/U thresholds):**

| Model | 2022 (in-sample) | 2023 (in-sample) | 2024 (OOS) |
|---|---|---|---|
| mlb_moneyline | 508 bets / 64.8% / +40.0% | 397 bets / 71.3% / +48.5% | **409 bets / 55.0% / +15.71% — GO-LIVE** |
| mlb_over_under | 257 bets / 72.8% / +41.6% | 152 bets / 74.3% / +43.6% | **178 bets / 63.5% / +24.54% — GO-LIVE** |
| Combined | 765 bets / 67.5% / +40.6% | 549 bets / 72.1% / +47.2% | **587 bets / 57.6% / +18.39% — GO-LIVE** |

Both 2024 OOS models pass all three go-live criteria. In-sample CalErrors (10%+) are expected — model trained on 2019–2023, calibration fitted on CV folds, not full training set. OOS CalError is the honest measure.

**v6 vs v5 on 2024 OOS:**
- Moneyline: CalError 5.38% (v5 FAIL) → 4.88% (v6 PASS); -23 picks, -2.6pp ROI (null skip adds integrity)
- O/U: CalError 2.50% → 1.80%; +3.7pp win rate, +6.5pp ROI (quality improved with null fix)

### v8 Backtest (2024–2025, first 15 games excluded)

Run command: `python -m models.backtester --all --season YYYY`

Backtester now uses bulk loading (same as trainer) — full 3-model backtest runs in ~1-2 min.

| Season | Model | Bets | Win Rate | Flat ROI | Units Profit | CalError | Note |
|---|---|---|---|---|---|---|---|
| 2024 | mlb_moneyline | 292 | 59.2% | +23.5% | +68.7u | 4.0% | OOS holdout |
| 2024 | mlb_over_under | 296 | 58.1% | +13.7% | +40.5u | 3.3% | OOS holdout |
| **2024 Combined** | | **588** | **58.7%** | **+18.6%** | **+109.3u** | **4.0%** | OOS |
| 2025 | mlb_moneyline | 312 | 61.5% | +25.7% | +80.1u | 4.9% | OOS blind |
| 2025 | mlb_over_under | 242 | 59.5% | +15.2% | +36.8u | 4.4% | OOS blind — 87.7% weather coverage |
| **2025 Combined** | | **554** | **60.7%** | **+21.1%** | **+116.9u** | **5.0%** | OOS |

**2024 + 2025 combined (true OOS): 1,142 bets / 59.6% win / +19.8% ROI / +226.1 units**

Runline generates 0 backtest bets in both years — no historical spread prices in SBR data.
Will validate once live DK runline odds have accumulated (~mid-season 2026).

Key observations:
- Two consecutive OOS years at ~19-21% flat ROI confirms the edge is real, not a lucky backtest
- Moneyline improved year-over-year (59.2%→61.5%, +23.5%→+25.7%) — positive drift
- O/U improved year-over-year (58.1%→59.5%, +13.7%→+15.2%) — healthy
- All individual model CalErrors under 5%; 2025 combined barely at 5.0% boundary
- v8 vs prior v6 backtests: moneyline ROI improved substantially (+15.7%→+23.5% on 2024 holdout); O/U generates more picks (178→296) with moderate ROI compression

### Bugs Fixed (2026-04-03 — live scoring session)

**h2h moneyline prices stored as NULL:**
`_parse_outcomes` in `odds_ingestor.py` checked `name == "Home"` / `name == "Away"` but The Odds API
returns full team names (e.g. "St. Louis Cardinals"). Fixed to match against `home_team_name` parameter,
same pattern as `_parse_spread_outcomes`. Result: moneyline picks now generate correctly (12 BETs today
vs 8 before fix).

**Scorer improvements (2026-04-03):**
- Pick labels now include line number: `"DET vs STL Under 7.5"`, `"STL +1.5"` (not generic "Under"/"Spread")
- DK price shown in scorer log: `[BET] DET vs STL Under 7.5 | DK=-104 | model=0.687 | edge=+17.7%`
- `scored_line` stored in picks table (total line or spread at time of scoring)
- `check_line_movement(conn, game_date)` added to `scorer.py` — compares scored odds vs current odds:
  - SKIP: total line moved 0.5+ against the bet direction
  - CAUTION: price steamed 3%+ implied prob against you
- `python run_pipeline.py --step check-lines` — run 1-2 hours before game time to flag line movement

**Batter prop scoring timing fix (2026-05-13):**
Batter props were not generating any picks despite models being trained and prop odds in the DB.
Root cause: `run_batter_prop_scorer` requires confirmed lineup slots (`is_confirmed = TRUE`), but
lineups don't post until 5:30–7pm ET for evening slates. The morning pipeline (11am ET) runs prop
scoring before lineups exist — it logs "no confirmed lineups" and exits cleanly. The midday refreshes
(12pm, 3pm, 6pm, 8pm) previously ran only odds + lineups + game scoring, not prop scoring.
Fix: added `python run_pipeline.py --step prop-scoring` to `refresh_picks.yml` after the lineups
step. Now every refresh attempt batter scoring — it's a no-op if lineups aren't confirmed yet, and
fires picks on the first refresh after they post. Pitcher K props are unaffected (use MLB Stats API
probable starters, not lineup_slots).

**DK HR market availability:** `batter_home_runs` market is not always listed by DK on a given day.
When absent from `player_prop_odds`, HR picks produce 0 picks (no error). HR picks are
opportunistic — they will fire when DK lists the market.

**Accented names cross the two feeds (FIXED 2026-08-30, session 148).** The roster
feeds accent names ("José Ramírez"); the Odds API writes them flat ("Jose Ramirez").
`_get_prop_dk_odds` matched the exact string, so every accented player missed his own
DK price — a NULL-priced row for the PROB_ONLY HR model, and **no row at all** for
every other prop market. Through August 2026 that was 2.8% of accented lineup slots
scored against 58.6% of plain-ASCII ones; lifetime, 0.41% of priced MLB prop picks
carried an accent where accented names are ~9% of a slate. The exact match is still
the fast path; on a miss it falls back to `data.name_match.resolve_feed_name`, which
folds only spelling (diacritics, case, punctuation, generational suffix) and refuses
an ambiguous fold rather than guessing. **Any new cross-feed player join belongs on
that helper** — all five prop lanes share the one lookup, pinned by
`tests/test_prop_name_match.py`.

**Known issues (active):**
- **The pre-game line poller wipes a game's non-BET PROP picks (NOT FIXED — needs a
  decision).** `data/ingestors/pregame_line_poller.py` calls `run_scorer(only_games=…)`
  whenever DK's number on a game moves, and the game scorer's non-BET housekeeping
  delete (`models/scorer.py`, "Housekeeping for the pairs the lock deliberately leaves
  open") is scoped by `game_id`, not by model — so it takes that game's prop NONE and
  AVOID rows with it, and `run_scorer` never re-creates them. Prop rows only come back
  on the next hourly prop pass. Measured: prop non-BET deletes were **0/day through
  2026-08-29 and 8.5k–23k/day from 2026-08-30**, the day the poller shipped. **BET rows
  are never touched** (0 prop BET deletes in that window), so §1c holds for the bet of
  record. Not fixed here because the delete is accidentally load-bearing: `_locked_prop_keys`
  locks on ANY unsettled row including NONE, so without something clearing them a
  dead-zone player could never later fire. The real fix is probably to lock props on
  BET only (matching the game lock) — a model-behaviour change, so it is Matt's call.
- **Pre-lock-era prop prices may include late-snapshot contamination (Apr 14–Jun 25):** in the delete+rescore era the evening passes re-scored props after first pitch against the latest stored DK snapshot, and 10-15% of prop snapshots in that window were post-start. Unlike the lock era (repaired 2026-08-09 via the is_live flag), those rows can't be identified by `created_at` (rewritten every pass). Impact is diluted (most re-scores still read pre-game snapshots) but unquantified — treat pre-July prop sweep ROIs as approximate.

**Resolved:**
- **The Stats board's ODDS column read only `picks` (FIXED 2026-09-03, then
  redirected by Matt the same day).** It joined today's picks by `player_id`, so a
  player DraftKings priced but no model had scored showed "—". Measured 2026-09-03
  14:20 ET: DK priced `batter_hits` for **184 players across all 9 games; 60 held a
  pick.** Matt's direction: *"display all lines regardless of bet status … if they
  select FanDuel we only show FanDuel … it works separately from the models."* So the
  tab's LINE column is now the user's sportsbook (`usePreferredBook`) and only that
  book — no DK fallback — for the line the ruler is on, for players
  (`v_latest_prop_odds_all_books`, one market at a time) AND teams
  (`v_latest_odds_all_books`, the team's own side of its moneyline/spread/total,
  market chosen by the stat). Both bounded to the sport's slate and to games that
  have not started (a started game's "latest" row is a live number — PIT read
  −50000 mid-game). A pick's only remaining role is unlocking "Add to betslip" at
  its own line. **FanDuel posts no `batter_hits` line at all** (2026-09-03), so a
  FanDuel user sees the note "FanDuel doesn't post Hits lines today" rather than a
  column of dashes. Pure logic in `mobile/src/lib/statsOdds.ts`, pinned by
  `mobile/scripts/verify_stats_odds.ts`.
- NHL h2h_3way 422 error (FIXED 2026-06-13): `h2h_3way` is an additional market
  that 422s when included in the bulk `/odds` request (it was killing the whole
  NHL fetch). Now fetched via the per-event endpoint (`_fetch_nhl_3way_per_event`),
  same pattern as UFC round totals. Non-fatal when DK doesn't list it.

**CalError metric fix (2026-04-02):**
`_mean_calibration_error` now requires min_samples=20 per bin (was 0). Bins with <20 samples
at extreme probabilities produce 0.0 or 1.0 actual rates by chance — not real miscalibration.
This is standard ECE practice. The "failures" on first v4 run (moneyline 6.30%, O/U 11.95%)
were entirely driven by 1-5 sample bins; underlying calibration was 1.86% and 2.96%.

**v4 backtest results (2022–2024, at 7%/8% thresholds):**

| Model | 2022 | 2023 | 2024 (OOS) |
|---|---|---|---|
| mlb_moneyline (7%) | 957 bets / 59.9% / +24.5% ROI | 826 bets / 69.6% / +41.9% ROI | 855 bets / 52.9% / +8.7% ROI |
| mlb_over_under (8%) | 858 bets / 62.7% / +21.1% ROI | 726 bets / 65.4% / +26.0% ROI | 710 bets / 55.9% / +8.3% ROI |

**v3 reference (for comparison):**

| Model | AUC (v3) | CalError (v3) | Backtest OOS |
|---|---|---|---|
| mlb_moneyline | 0.544 | 2.03% | -24.68u / 44.0% |
| mlb_over_under | 0.504 | 0.41% | 0 bets |
| mlb_runline | 0.547 | 3.45% | 0 bets |

**Backtester bugs fixed (2026-04-02):**
Three bugs were discovered and fixed during investigation of bad backtest results:
1. Null features filled with 0.0 — backtester was filling missing pitcher features with 0 (ERA=0 is impossible, sent model OOD). Fixed to skip games with any null feature.
2. O/U outcome hardcoded to `won=0` — all O/U picks always showed as losses. Fixed to compare total runs vs total_line.
3. Spreads outcome hardcoded to `won=0` — same issue for runline. Fixed to use margin + spread_home.
4. CalError min_samples=3 in backtester — raised to 20 to match trainer fix.

**Performance note — RESOLVED (2026-04-14):**
Per-game SQL rolling queries were replaced with bulk loading + in-memory dict/bisect lookups
in `feature_engine.py`. Feature build time dropped from ~6 hours → ~3 seconds per model.
The bulk path (`_build_bulk_mlb_lookups` + `_build_mlb_features_from_bulk`) is used during
both training and backtesting; live scoring still uses the per-game `build_mlb_game_features`
path (runs on ~15 games/day, speed not an issue there).
Backtester optimization added session 9: full 3-model backtest runs in ~1-2 min (was ~3 hours).

### F5 Models

> **The v3 table below is superseded — see §11a.** Its `mlb_f5_moneyline` row
> reports AUC 0.691 on a 2024 holdout that was INSIDE its own training seasons
> ("train 2019-2025 excl. 2024 holdout" is not a holdout), measured on top of
> two leaked tables. Two independent reasons the same number is not real. The
> honest figure is a walk-forward mean of 0.557 with 2026 at 0.536.

#### v4 — ACTIVE, retrained 2026-09-03 on the rebuilt tables (mike)

`mlb_f5_moneyline` **v20260903_163809**. Train 2019-2025 (7,952 rows), holdout
**2026** (1,108). Both passed explicitly: `models.trainer` defaults to
`train_seasons` ending **2024** and `test_season` **2025**, so a bare retrain
would have ignored the only honestly-featurised season entirely.

| metric | v4 (honest) | v3 (leaked) |
|---|---|---|
| Holdout AUC | **0.5548** | 0.691 |
| Holdout accuracy | 0.5424 | — |
| Brier | 0.2468 | — |
| CalError | **0.0240 — PASS** (≤5%) | 5.78% borderline |
| Holdout | 2026, outside training | 2024, INSIDE training |

The holdout AUC corroborates the walk-forward 2026 fold (0.5356) rather than
contradicting it, which is what an honest holdout is supposed to do.

**The feature importances are the real story.** Before, `d_starter_era_last3`
(0.213) and `d_starter_era` (0.186) were **40% of the model between them** —
both reading a season-final ERA. Now:

| rank | feature | importance |
|---|---|---|
| 1 | `d_run_differential` | 0.109 |
| 2 | `d_starter_k9` | 0.081 |
| 3 | `d_team_era` | 0.065 |
| 4 | `d_team_whip` | 0.062 |
| 5 | `away_win_pct` | 0.061 |

No feature now exceeds 11%, and **the top feature and the fifth are two of the
eight that used to be CONSTANT ZERO** in every training season — `d_run_differential`
and `away_win_pct` were inert because the leaked team table never varied them,
and XGBoost cannot split on a constant. The Phase 1 rebuild revived them and the
model immediately leant on them. The ERA pair that carried the old model has
fallen out of the top five.

**PAPER ONLY until it clears the go-live gate.** CLAUDE.md §2: ≥50 settled
picks, positive flat-bet ROI, calibration ≤5% — per model, and **a retrain
resets it**. CalError already passes at 2.4%; the other two need live settled
picks. Until then f5 is surfaced but not backed.

#### The threshold sweep, and why it does not produce a threshold

`scripts/mlb_f5_sweep.py`, 2026-09-03. The retrained model scored across 2026 —
the only season carrying DK first-five prices (1,425 priced games) **and** the
season held out of the retrain, so the sweep is genuinely out of sample.
`calibrated_threshold_sweep` could not be used: it replays the LIVE GRADED
record, and every graded pick in `picks` was produced by the OLD artifact.

**Two findings, and the first one is the urgent one.**

**1. The current 0.74 cut fires ZERO bets.** Across 2,036 bettable sides the
model's maximum probability is **0.734**. Not "few" — none:

```
p >= 0.68     19 sides
p >= 0.70      4 sides
p >= 0.72      2 sides
p >= 0.74      0 sides      <- the live cut
```

This is `mlb_runline`'s failure mode exactly: a model that cannot reach its own
floor publishes nothing while looking live in `config.py`,
`model_action_thresholds` and the mobile fallback. **The status quo is not
neutral** — a paper-only model that fires zero picks can never accumulate the
≥50 settled picks §2's gate requires, so 0.74 does not park f5, it strands it.

**2. There is no cut to move it to.** Of 104 grid cells, 50 carry ≥30 bets and
**exactly one of those is positive** (2 of 104 overall):

| min_prob | min_edge | bets | W-L | win% | ROI |
|---|---|---|---|---|---|
| 0.58 | 0.02 | 77 | 46-31 | 59.7% | **+4.09%** |

One positive cell in fifty is what a model with no edge looks like against vig,
not an edge. And that cell fails the plateau test outright — **0 of its 8
neighbours are positive**, which is the precise shape sessions 74 and 87 had to
retract. It survives a time split (first half +0.99%, second half +7.27%), but
surviving one check does not rescue a cell the neighbourhood contradicts.

Average DK implied probability across the sides is 53.2%, so that is the bar.

#### What was shipped, and on whose call

**0.58/0.02, as a PAPER cut (mike, 2026-09-03). These picks are NOT LIVE**, and
that is the premise the whole decision rests on: the retrain reset §2's gate, so
f5 is paper-only and nothing is backed at this cut.

The grid does not support a cut — one positive cell in fifty, failing the
plateau test 0 of 8 — and that is a strong argument against ever making this
**live**. It is not an argument against measuring it. Pausing and shipping a
paper cut differ in exactly one respect: whether the model produces a record to
judge. Pausing produces none, and a paused model cannot clear the gate that
would unpause it. 0.74 had the same effect as pausing without saying so.

The numbers on the record are the FLOORED ones, with `config.MODEL_MIN_ODDS`
applied inside the sweep, because a cell measured on bets below the floor is
measured on bets the scorer refuses:

| | bets | W-L | win% | ROI | halves |
|---|---|---|---|---|---|
| 0.58/0.02, floored | **76** | 45-31 | 59.2% | **+3.52%** | +0.99 / +6.18 |
| unfloored (for comparison) | 77 | 46-31 | 59.7% | +4.09% | +0.99 / +7.27 |

~5.4 bets/week, average price −134, worst −200. The floor removes one bet here,
but the 2026-08-31 slate had a sweep that skipped it recommend four cuts the
corrected one withdrew, so it is applied in the script rather than afterwards.

**Kill criterion, pre-committed so it is not re-argued later:** review at 50
settled picks. If flat-bet ROI is negative there, **pause** — do not widen the
bar looking for a better cell, because the grid already says there isn't one.
Clearing §2 additionally needs positive ROI and calibration ≤5%.

Two tests hold this in place: one pins the cut and records that the evidence is
thin, the other asserts the prob floor stays **below the model's observed
maximum**, which is the check 0.74 failed.

#### v3 (retrained 2026-05-12) — SUPERSEDED, kept for provenance

| Model | AUC | CalError | Gate (≤5%) | Holdout rows | Notes |
|---|---|---|---|---|---|
| `mlb_f5_moneyline` | 0.691 | 5.78% | borderline | 1,470 | v3 retrain 2026-05-12 — train 2019-2025 excl. 2024 holdout |
| `mlb_f5_over_under` | 0.582 | 1.5% | PASS | 1,875 | v1 trained 2026-05-08 — DISABLED (no DK lines) |
| `mlb_f5_runline` | 0.643 | 3.2% | PASS | 1,711 | v1 trained 2026-05-08 — DISABLED (no DK lines) |

**F5 O/U feature set (top 5):** away_starter_era (12.1%), home_starter_era (10.3%), total_line (7.0%), away_team_era (5.8%), home_runs_last_5 (5.7%)
**F5 RL feature set (top 5):** d_starter_era_last3 (19.9%), d_starter_era (16.1%), d_iso (6.8%), d_ops (6.7%), d_woba (5.9%)

**F5 O/U and F5 RL backtests use SYNTHETIC lines** (full_game_total × 0.62, calibrated from 26,443 games).
CalError is measured vs. synthetic lines — will improve once real DK F5 O/U/RL lines accumulate.
The Odds API does not carry F5 O/U or RL for DraftKings — all F5 scoring is prob-only (edge = model_prob − 0.50).

**v1 F5 O/U backtest:**

| Season | Bets | Win Rate | Flat ROI | CalError | Note |
|---|---|---|---|---|---|
| 2024 OOS | 1,410 | 62.3% | +19.0% | 4.49% | PASS |
| 2025 blind | 1,259 | 63.0% | +20.3% | 3.45% | PASS |
| **Combined** | **2,669** | **62.6%** | **+19.6%** | | |

**v1 F5 RL backtest:**

| Season | Bets | Win Rate | Flat ROI | CalError | Note |
|---|---|---|---|---|---|
| 2024 OOS | 853 | 66.9% | +27.8% | 2.51% | PASS |
| 2025 blind | 835 | 63.8% | +21.9% | 2.57% | PASS |
| **Combined** | **1,688** | **65.4%** | **+24.8%** | | |

**Thresholds (prob-only, tune after live validation):**
- F5 O/U: prob ≥ 57%, edge ≥ 7% (action filter same)
- F5 RL: prob ≥ 58%, edge ≥ 8% (action filter same)

**Caveat on pick volume:** F5 O/U at 57%/7% generates ~1,300 picks/season vs ~300 for full-game O/U.
High volume + synthetic lines = backtest ROI should be treated as directional only until real DK F5 lines accumulate.
F5 RL -0.5 has the same binary outcome as F5 ML (home wins F5). Both can fire on the same game — this doubles
exposure on the same outcome. Monitor correlation when reviewing live results.

### Batter Prop Models — v1 active (trained 2026-05-12)

| Model | Method | AUC / O/U Acc | CalError | Holdout rows | Status |
|---|---|---|---|---|---|
| `mlb_prop_batter_hits` | Poisson | 59.8% O/U acc | 1.16% | 31,135 | LIVE |
| `mlb_prop_batter_tb` | Poisson | 59.6% O/U acc | 4.06% | 31,135 | LIVE |
| `mlb_prop_batter_hr` | Poisson | 88.5% O/U acc | 0.77% | 25,473 | **RETIRED 2026-09-02 (matt)** — artifact deleted, registry row inactive, gone from `PROP_MODELS` and the app; picks stay graded |

**Hits top features:** `batting_order` (23.2%), `season_hit_avg` (14.5%), `hits_last10_avg` (10.6%), `opp_team_era` (7.6%), `savant_xba` (7.1%)
**TB top features:** `batting_order` (29.7%), `season_tb_avg` (12.6%), `savant_xslg` (8.1%), `opp_team_era` (7.5%), `savant_hard_hit_pct` (5.3%)
**HR v2 top features:** `season_hr_avg` (19.5%), `hr_last20_avg` (8.8%), `savant_xslg` (8.6%), `savant_barrel_pct` (8.4%), `savant_hard_hit_pct` (8.1%), `batting_order` (6.3%), `savant_launch_angle` (5.2%), `platoon_advantage` (4.8%), `park_hr_factor` (4.8%), `opp_starter_hr9` (3.9%)

HR v2 model: binary AUC 0.617 (top 5% of preds → 25.2% actual HR rate vs 12.2% baseline). Upgraded from v1 (logistic, AUC 0.482). New game-level features: pitcher HR/9, pitcher HR/9 last 3 starts, pitcher groundball%, park HR factor, platoon advantage. NOTE: HR prob range is 10-25% so prob threshold is set to 20% (not the standard 55% which would never fire).

**HR pick_side signal (historical — `mlb_prop_batter_hr` and `mlb_prop_batter_rbi` were RETIRED 2026-09-02, see `config.PROP_MODELS`; their existing rows still follow this convention):** HR picks always use `pick_side = 'over'` — DraftKings HR props are priced as "over 0.5 HRs" with no real under market. `pick_label` format: `"{Player Name} Over 0.5 HR"`. To filter HR BETs for website display: `model_id = 'mlb_prop_batter_hr' AND pick_side = 'over' AND signal_type = 'BET' AND model_probability >= 0.225` (prob-only model — edge is informational, not a filter; see config.PROB_ONLY_MODELS).

**Training data:** 108,195 rows (2019-2023 train), 31,135 holdout (2024). 46% null drop (batters with <5 games of history). `batting_order` being the top feature for both Poisson models makes sense — PA opportunity drives counting stats, and lineup position is a strong PA proxy.

**Thresholds (initial, conservative — tune after 50+ settled picks):**
- Hits: prob ≥ 55%, edge ≥ 5%
- TB: prob ≥ 55%, edge ≥ 5%
- HR: prob ≥ 20%, edge ≥ 5% — HR props have max P(HR) ≈ 25%; standard 55% threshold would never fire

**Scoring:** reads confirmed lineups from `lineup_slots` (populated by lineup_ingestor). Picks write after lineups post (~60-90 min before first pitch). Runs via `run_prop_scorer()` which chains pitcher K → hits → TB → HR.

### NHL Models — code complete, NOT yet trained (2026-06-13)

All four NHL models are registered, wired end-to-end (ingest → features → train →
score → settle), and validated against synthetic data offline. They are NOT
trained on real data yet — the NHL API (`api-web.nhle.com` / `api.nhle.com`) is
blocked by the sandbox egress allowlist, so backfill + training run on Matt's
machine / GitHub Actions (where the API is reachable). Same hand-off pattern as UFC.

| Model | Market | Scores against | Notes |
|---|---|---|---|
| `nhl_moneyline` | h2h | real DK moneyline | home wins incl. OT/SO |
| `nhl_moneyline_regulation` | h2h_3way | real DK 3-way regulation | **3-class** XGBoost (away reg / draw / home reg) — the spec's "regulation market often has better value" play |
| `nhl_over_under` | totals | real DK totals | total goals O/U |
| `nhl_puckline` | spreads | real DK puck line | home covers ±1.5 |

First-time setup (Matt's machine — see Section 24):
```bash
python -m data.ingestors.nhl_stats_ingestor --backfill-games 2019 2025   # games + scores + reg outcomes
python -m data.ingestors.nhl_stats_ingestor --backfill 2019 2025         # team + goalie season snapshots
python -m models.trainer --model nhl_moneyline
python -m models.trainer --model nhl_moneyline_regulation
python -m models.trainer --model nhl_over_under
python -m models.trainer --model nhl_puckline
python -m models.backtester --model nhl_moneyline --season 2025
```

Validated offline (synthetic data): parse_nhl_game OT/regulation encoding, the
bulk feature path (`_build_bulk_nhl_lookups` + `_build_nhl_features_from_bulk`),
the new 3-class `h2h_3way` trainer branch, 3-way scoring (`_score_nhl_3way`
incl. the draw side), and settlement (draw = WIN on OT games). Thresholds in
config are placeholders — tune after 50+ settled picks.

**Goalie last-5 features excluded by design:** `d_goalie_save_pct_last5` /
`d_goalie_gaa_last5` need per-game goalie logs, which aren't backfilled, so they
were null for 100% of training rows (would null-drop the entire matrix). The
season save%/GAA/GSAA diffs already capture goalie quality. The daily ingestor
still computes the last-5 fields for potential future use.

**O/U + puckline need historical lines:** like the MLB runline, the totals and
puckline targets require `total_line`/`spread_home` from the odds table. The NHL
API backfill provides scores (moneyline + regulation train immediately), but O/U
and puckline only train once historical NHL odds are loaded (SBR files in
`data/raw/datawarehouse/nhl/`) or live DK lines accumulate.

---
## 18. Phase 2 — MLB Player Props Plan
Decisions locked in session 14 (2026-05-08). Do not relitigate without new information.

### Scope

All 11 DraftKings player prop markets via The Odds API:

**Pitcher props:** `pitcher_strikeouts`, `pitcher_hits_allowed`, `pitcher_earned_runs`, `pitcher_outs`, `pitcher_walks`

**Batter props:** `batter_hits`, `batter_total_bases`, `batter_home_runs`, `batter_rbis`, `batter_runs_scored`, `batter_stolen_bases`, `batter_walks`

### Model Architecture — Count Projection

Predict expected count per player per game (regression), then compare to DK line using a probability distribution. This is the correct approach for counting stats — one model works across any DG line value.

| Model ID | Target | Method | Notes |
|---|---|---|---|
| `mlb_prop_pitcher_k` | Strikeouts per start | Poisson regression | **Priority 1 — build first** |
| `mlb_prop_pitcher_hits` | Hits allowed per start | Poisson regression | |
| `mlb_prop_pitcher_er` | Earned runs per start | Poisson regression | |
| `mlb_prop_pitcher_outs` | Outs recorded | Poisson regression | |
| `mlb_prop_pitcher_walks` | Walks per game | Poisson regression | |
| `mlb_prop_batter_hits` | Hits per game | Poisson regression | |
| `mlb_prop_batter_tb` | Total bases per game | Poisson regression | |
| `mlb_prop_batter_rbi` | RBIs per game | Poisson regression | RETIRED 2026-09-02 |
| `mlb_prop_batter_runs` | Runs scored per game | Poisson regression | |
| `mlb_prop_batter_hr` | HR per game | Logistic (binary) | Rare event — Poisson breaks down. RETIRED 2026-09-02 |
| `mlb_prop_batter_sb` | Stolen bases per game | Logistic (binary) | Rare event — Poisson breaks down |

Edge = model_prob vs DK implied prob (real DK odds now collected via prop_odds_ingestor).

### Odds Strategy

Collect real DK prop lines via The Odds API daily (prop_odds_ingestor.py is live). Score against real DK lines immediately — no prob-only fallback needed for pitcher Ks since DK carries K props for most starters. Train against real lines once 60+ days of prop line history accumulates.

### Bet Sizing

Tenth-Kelly, capped at 5% of bankroll — same as game-level models. Tune thresholds after 50+ live paper trading picks per model.

### Umpire Data

Include umpire K rate as a feature for pitcher K model. Source: UmpScorecard (free, requires scraping). Worth the complexity — some umpires add 2+ Ks per game vs average.

### Lineup Dependency

Batter prop scoring requires confirmed lineups. Pipeline scoring runs after lineups post (~1 hour before first pitch). This is a timing constraint on when batter picks are available.

### New Infrastructure Required

**New DB tables (all live in Supabase):**
- `player_game_log` — per-player per-game stats (Ks, hits, HR, TB, etc.) — training backbone
- `player_prop_odds` — live DK prop lines by player/date/market
- `player_savant_stats` — Baseball Savant Statcast metrics per player per season (includes `gb_pct` added session 19)
- `umpires` — historical umpire K rates by umpire_id
- `lineup_slots` — confirmed lineup position per player per game
- `player_handedness` — bat_hand + throw_hand per player_id, 4110 rows, backfilled from MLB Stats API (added session 19)

**picks table — additional columns (added session 19–20):**
- `player_id TEXT` — batter's MLBAM player_id (prop picks only; NULL for game-level picks). Join to `player_handedness` for bat_hand.
- `pitcher_throw_hand TEXT` — opposing starter's throw hand at score time ('L', 'R'). Stored directly so the website doesn't need a multi-table join.

**New ingestors (built):**
- `baseball_savant_ingestor.py` — Statcast leaderboard CSV (k%, whiff%, xERA, velo, barrel%, xBA)
- `prop_odds_ingestor.py` — The Odds API player prop markets for DK (all 11 markets, event-level)

**Still needed:**
- (none — all ingestors complete)

### Key Features (pitcher K model — live, v2)

18 features: k_last3/5/10_avg, k_rate_last3/5, ip_last3/5_avg, season_k_avg, k_trend, savant_k_pct, savant_whiff_pct, savant_bb_pct, savant_xera, savant_avg_velocity, opp_team_k_pct, is_dome_game, temp_f, ump_k_plus_minus. Prior-season fallback for season_k_avg when current-season logs unavailable.

**v2 retrain results (2026-05-14, version 20260514_090858):**
- 11,115 training rows (2019-2023), 3,091 holdout (2024)
- 13,447 umpire assignments loaded, 138 unique umpires
- Holdout MAE: 1.803 (v1: 1.80 — flat), RMSE: 2.236 (v1: 2.24 — flat)
- O/U acc: 64.1% (v1: 64.3% — slight decrease), CalError: 11.3% (v1: 11.6% — slight improvement)
- Top 5 features: season_k_avg (17.1%), k_last10_avg (16.7%), k_last5_avg (13.7%), savant_k_pct (6.5%), k_last3_avg (6.4%)
- `ump_k_plus_minus` did NOT appear in top features — career-average encoding too coarse to add signal above rolling K averages already in model
- Model kept live (CalError improved slightly); v3 would need ASOF rolling umpire stats or zone-size/chase-rate features to gain real signal

### Build Sequence

| Phase | Work | Status |
|---|---|---|
| 1 — Foundation | DB tables + game_log backfill + savant_ingestor + prop_odds_ingestor | DONE |
| 2 — Pitcher K model | feature engine + train mlb_prop_pitcher_k + scorer + pipeline wiring | DONE |
| 3 — Batter props (hits/TB/HR) | Feature engine for batters + train hits/TB/HR + scorer wiring | DONE (2026-05-12) |
| 4 — Pitcher hits/ER/outs/walks | Feature engine extended + scorer refactored to config loop + all 4 trained | DONE (2026-05-13) |
| 5 — Remaining batter props | RBIs, runs scored, SBs, walks | DONE (2026-05-13) |

---

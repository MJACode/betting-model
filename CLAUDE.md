# CLAUDE.md — Betting Model Project Context

> This file is read at the start of every session. It gives Claude full context
> about this project so work can resume without re-explaining anything.
> **Update this file after every commit.** Record what changed, why, and any
> threshold or config values that were modified. Keep Section 16, Section 17,
> and the session log at the bottom in sync with the actual code.

---

## 1. Who I Am and How I Work With You

**Matt** is the product area leader. He reviews, approves, and sets direction.
**Claude** acts as the PM and developer — asking clarifying questions, suggesting
alternatives, and building everything. Matt has final say on all decisions.

**Working style:**
- Matt expects Claude to push back with suggestions if something seems off
- Ask clarifying questions before starting any major piece of work
- Keep explanations clear and non-technical where possible
- Matt is building this solo — no engineering team

---

## 2. Project Purpose

Building a **personal sports betting model** targeting **DraftKings** as the
primary sportsbook. The long-term goal is all major US sports with all player
props. Phase 1 covers **MLB and NHL**.

**This is paper trading only until the go-live gate is passed:**
- ≥ 50 picks in paper trading
- Positive flat-bet ROI
- Calibration error ≤ 5%

**Not real money until those gates are cleared.**

---

## 3. Technical Spec Reference

The full approved spec is:
`Bet Repos/Betting Model Platform — Technical Spec v1.2.docx`

Key decisions from the spec (Section 4, decisions log 4.1–4.11):

| Decision | What we chose | Why |
|----------|--------------|-----|
| Historical odds source | SBR (free Excel downloads) | Odds API historical costs 10× credits |
| Database | SQLite (single file) | Simple, local-first, cloud-migratable later |
| Models | 7 XGBoost models (one per sport×market) | Best calibration for tabular sports data |
| Calibration | Platt scaling post-XGBoost | Converts raw scores to real probabilities |
| Hyperparameter tuning | Optuna (Bayesian, 100 trials) | Better than grid search for this use case |
| Bet sizing | Tenth-Kelly, capped at 5% | Quarter-Kelly always hit the cap (flat-betting); tenth-Kelly gives 2-4% bets with real edge-driven differentiation |
| Edge threshold | ±3% for BET/AVOID signals | No-signal zone between −3% and +3% |
| Injuries | 3 scenarios: A (active), B (return ramp), C (opponent edge) | Injuries matter; ramp prevents overconfidence on return |
| Early season rule | No picks until ≥10 games played | Avoids unstable small-sample stats |
| NHL overtime | Two models: full-game ML + regulation-only 3-way | Regulation market often has better value |
| Props | Phase 2 only | Too much data infrastructure needed for Phase 1 |

---

## 4. Current Build State

### What's Built

```
betting-model/
├── CLAUDE.md                          ← this file
├── .env.example                       ← copy to .env, add ODDS_API_KEY
├── config.py                          ← central config, env vars, constants
├── requirements.txt                   ← all Python dependencies
├── run_pipeline.py                    ← master daily orchestrator (9 steps)
│
├── data/
│   ├── db_setup.py                    ← Supabase/Postgres schema (17 tables)
│   └── ingestors/
│       ├── sbr_loader.py              ← SBR Excel historical odds parser
│       ├── injury_ingestor.py         ← ESPN Hidden API + MLB Stats API
│       ├── odds_ingestor.py           ← The Odds API (DraftKings live + F5 ML)
│       ├── prop_odds_ingestor.py      ← The Odds API (DK player prop markets)
│       ├── mlb_stats_ingestor.py      ← MLB Stats API + Baseball Savant + game log
│       ├── nhl_stats_ingestor.py      ← NHL API v1 team/goalie stats
│       ├── weather_ingestor.py        ← Open-Meteo weather (wind/temp/dome)
│       └── baseball_savant_ingestor.py ← Statcast leaderboard CSV (pitcher + batter)
│
├── features/
│   ├── feature_engine.py             ← Feature matrix builder (game models)
│   └── prop_feature_engine.py        ← Feature builder (Poisson prop models)
│
├── models/
│   ├── trainer.py                     ← XGBoost + Optuna (classification + Poisson)
│   ├── scorer.py                      ← BET/AVOID signals: game models + prop models
│   └── backtester.py                  ← Historical simulation + go-live gate
│
├── tracking/
│   └── paper_tracker.py              ← Morning result settler + P&L log
│
├── dashboard/
│   └── app.py                        ← Streamlit 5-tab dashboard
│
└── logs/                             ← Auto-created by run_pipeline.py
```

### What's NOT Built Yet
- Remaining prop models (10 of 11 — pitcher hits/ER/outs/walks; all batter props)
- NHL models (data not loaded, models not trained)
- Lineup ingestor (needed for batter prop scoring — confirmed lineups ~1hr before first pitch)
- Umpire ingestor (umpire K rate feature for pitcher K model)
- Dashboard prop tab

---

## 5. Data Sources

| Source | What it provides | Cost | Notes |
|--------|-----------------|------|-------|
| The Odds API | Live DraftKings lines | ~$79/mo Starter | Key in `.env` as `ODDS_API_KEY` |
| SBR (SportsBookReviewsOnline) | Historical odds 2007–2024 | Free | Manual Excel download |
| MLB Stats API (statsapi) | Team batting/pitching stats, probable starters, game scores | Free | Primary source for all MLB team + pitcher stats. Replaced FanGraphs 2026-04-11. |
| Baseball Savant | SwStr%, CSW%, xERA (xFIP proxy) per pitcher per season | Free | Official MLB property. Joined to MLB Stats API by MLBAM player_id. |
| Open-Meteo | Historical + forecast weather (temp, wind, precip) | Free | No API key needed. Used by weather_ingestor.py. |
| NHL API v1 | Team stats, goalie stats, schedule | Free | Direct HTTP to `api-web.nhle.com` |
| ESPN Hidden API | Injury reports (both sports) | Free | Hidden JSON endpoint, no auth needed |

**FanGraphs / pybaseball — REMOVED (2026-04-11, completed 2026-04-12):**
FanGraphs blocked our IP after repeated scraping during development. Replaced entirely
with MLB Stats API + Baseball Savant for all team and per-pitcher stats. pybaseball is
still in requirements.txt but no longer called anywhere. Do NOT add back any FanGraphs
scraping without a different mechanism.

**Datawarehouse / CSV data (2026-03-31 — updated):**

MLB historical data is now loaded from a flat CSV (`data/raw/datawarehouse/mlb/MLB_Basic.csv`).
This file covers 2009–2025 (40,996 games) in one-row-per-game format. The `sbr_loader`
was extended to support this format alongside the original Excel format.

The raw data folder was renamed from `data/raw/sbr/` → `data/raw/datawarehouse/` to reflect
its role as the source of historical baseball data. Config paths updated in `config.py`.

NHL data not yet loaded — deprioritized in favour of getting MLB working first.

To reload from scratch:
```bash
python -m data.ingestors.sbr_loader        # loads all CSV/xlsx in data/raw/datawarehouse/
```

CSV columns (MLB_Basic.csv):
`game id, date, away team, away score, away ml open, away ml close, over open,
over open odds, over close, over close odds, home team, home score, home ml open,
home ml close, under open, under open odds, under close, under close odds`

MLB runline spread is derived as `spread_home = -1.5` (fixed constant) — the CSV
has no spread column. The `spreads` odds row is written automatically by the loader.

---

## 6. Models Registry

| Model ID | Sport | Market | Target variable |
|----------|-------|--------|----------------|
| `mlb_moneyline` | MLB | Moneyline (h2h) | Home team wins full game |
| `mlb_over_under` | MLB | Totals | Total runs > line |
| `mlb_runline` | MLB | Spreads (±1.5) | Home covers spread |
| `nhl_moneyline` | NHL | Moneyline full game | Home team wins (incl. OT/SO) |
| `nhl_moneyline_regulation` | NHL | 3-way regulation | Home wins in regulation |
| `nhl_over_under` | NHL | Totals | Total goals > line |
| `nhl_puckline` | NHL | Puck line (±1.5) | Home covers spread |

---

## 7. Key Pipeline Commands

```bash
# First-time setup (do once)
python -m data.db_setup
python -m data.ingestors.sbr_loader --sport MLB
python -m data.ingestors.sbr_loader --sport NHL
python -m data.ingestors.mlb_stats_ingestor --backfill 2019 2024
python -m data.ingestors.nhl_stats_ingestor --backfill 2019 2024
python -m data.ingestors.mlb_stats_ingestor --backfill-pitchers 2019 2025
python -m data.ingestors.mlb_stats_ingestor --backfill-bullpen 2019 2025
python -m data.ingestors.weather_ingestor --backfill 2019 2025
python -m models.trainer --all
python -m models.backtester --all --season 2024

# Daily run (scheduled at 7:00 AM)
python run_pipeline.py

# Individual steps
python run_pipeline.py --step injuries
python run_pipeline.py --step odds
python run_pipeline.py --step mlb_stats
python run_pipeline.py --step weather
python run_pipeline.py --step scoring
python run_pipeline.py --step settle

# Preview picks without writing to DB
python run_pipeline.py --dry-run

# Launch dashboard
streamlit run dashboard/app.py
```

---

## 8. Business Logic — Critical Rules

### Edge Signal Classification
```
edge = model_probability − DraftKings_implied_probability

edge ≥ +3%  →  BET signal  (Tenth-Kelly sizing)
edge ≤ −3%  →  AVOID signal (informational only — don't bet the other side blindly)
−3% < edge < +3%  →  No signal (dead zone)
```

### Tenth-Kelly Bet Sizing
```
f_q = 0.10 × (model_prob − implied_prob) / (1 − implied_prob)
max bet = min(f_q × bankroll, 5% of bankroll)
```
Switched from quarter-Kelly (0.25) to tenth-Kelly (0.10) on 2026-05-04.
Quarter-Kelly always exceeded the 5% cap for picks meeting min-edge thresholds (10-14%),
producing identical flat bets on every pick. Tenth-Kelly keeps bets at 2-4% of bankroll
and lets edge size drive differentiation. KELLY_MULTIPLIER in config.py is env-overridable.

### Injury Scenarios
- **Scenario A** — Active injury: penalizes team's expected performance
- **Scenario B** — Return from IL: applies ramp factor (0.70 → 0.85 → 1.00 over 5 games)
- **Scenario C** — Opponent injury: positive edge signal for the other team

### Early Season Rule
No picks are generated until a team has played ≥ 10 games.
Prior-season stats are used as the feature baseline during this window.

### NHL Overtime
Full-game moneyline counts OT/SO results.
Regulation-only model uses a separate 3-way market (Home / Draw / Away).
Regulation market often has better value since casual bettors underweight it.

---

## 9. What Was Rejected and Why

**AlphaPy** — Cloned initially, then rejected because:
- Last updated ~2020, uses deprecated pandas APIs
- Team-level only, no player props support
- Data connectors (Google Finance, IEX, Yahoo) all defunct
- Not worth salvaging — built from scratch instead

**npm `docx` package** — Blocked by workspace network proxy (403 Forbidden).
All Word documents generated with `python-docx` instead.

---

## 10. Learnings From This Project

### What Works Well for Sports Betting Models

**Data:**
- FanGraphs advanced stats (wRC+, xFIP, SwStr%) are far more predictive than raw box score stats
- Corsi% and xGF% are the most predictive NHL features; raw goals are noisy
- Opening line is the most predictive single feature — the market is efficient
- Team stats need at least 10 games before they stabilize (hence the early season rule)
- Injury data is underused in public models — it's a real edge

**Modeling:**
- XGBoost outperforms linear models for sports prediction on tabular data
- Calibration is as important as accuracy for betting — raw XGBoost probabilities are overconfident
- Platt scaling (sigmoid calibration) works well for sports models
- Bayesian hyperparameter search (Optuna) is materially better than grid search for this use case
- One model per sport×market is cleaner than a single multi-output model

**Betting math:**
- Tenth-Kelly (10% of full Kelly) is the right balance for this model's edge distribution — quarter-Kelly always hit the 5% cap, producing flat bets
- Full Kelly is theoretically optimal but in practice too aggressive given model uncertainty
- Flat-bet ROI is the most honest measure of model quality — Kelly ROI can be inflated by variance
- The go-live gate (≥50 picks, positive ROI, cal error ≤5%) prevents going live on lucky backtests

**Architecture:**
- SQLite is underrated for solo projects — no server, single file, cloud-migratable later
- Storing odds as snapshots (open/close) is important — closing line value (CLV) is a key signal
- `PRAGMA journal_mode=WAL` is essential for SQLite when multiple processes read/write

### Package Version Lessons Learned

- **Always verify package versions exist on PyPI before pinning them.** `nhl-api-py==0.8.7` was never published — the package jumped from 0.4.x directly to 2.x. Use `pip index versions nhl-api-py` to check what's actually available before adding to requirements.txt.
- **numpy 1.x does not support Python 3.13+.** Anyone on Python 3.13 (released Oct 2024) needs `numpy>=2.0.0`. When in doubt, use `>=` instead of `==` for packages that release frequently.
- **Python version compatibility is a matrix problem.** Each package declares which Python versions it supports. When a user has a newer Python than a package supports, pip will refuse to install it. Fix: use `>=` version pins or upgrade to a version that explicitly supports the new Python.
- **When requirements.txt fails, read the error carefully.** It usually tells you exactly which versions are available. Pick the latest compatible one.
- **Always use `python -m pip install` not `pip install`.** On Windows with multiple Python versions, `pip` can point to a different Python than `python`. Using `python -m pip` guarantees they match. `ModuleNotFoundError` after a successful-looking install is the symptom of this mismatch.
- **Python 3.14 is very new — use `>=` version pins, never `==` for ML packages.** scikit-learn 1.5.x and xgboost 2.0.x have no pre-built wheels for Python 3.14. When no wheel exists, pip tries to compile from source (C/Cython), which fails on Windows without a full build toolchain. Fix: use `>=` so pip selects the latest version that *does* have a 3.14 wheel. All requirements.txt entries now use `>=` for this reason.
- **Watch for "metadata-generation-failed" errors.** This means pip tried to build a package from source and the C compiler failed. The fix is always to find a newer version of the package that has a pre-built wheel for your Python version.

### What to Watch Out For

- **Look-ahead bias:** Feature engineering must only use data available BEFORE game time.
  The current pipeline uses `as_of_date <= game_date` everywhere — don't break this.
- **SBR data quirks:** V/H row-pair format, inconsistent date formats (YYYYMMDD vs MMDD),
  American odds as strings — sbr_loader.py handles all of these.
- **NHL franchise changes:** Arizona Coyotes → Utah Hockey Club. Maps are maintained
  in both the SBR loader and odds ingestor.
- **Early season small samples:** Stats from games 1–9 are unreliable. Enforced by
  `is_early_season` feature flag and early-season gate in scorer.
- **FanGraphs is permanently blocked and fully removed (2026-04-12):** IP-blocked after heavy
  dev scraping. All stats now come from MLB Stats API (team + pitcher ERA/K9/BB9/WHIP/HR9) and
  Baseball Savant CSV (SwStr%/CSW%/xERA). Do not attempt to re-add FanGraphs scraping.
- **Pitcher backfill uses full-season stats, not as-of-game-date:** MLB Stats API returns the
  final season totals for each season, not a rolling snapshot. This is the same look-ahead
  limitation FanGraphs had. Acceptable for v1 — starters don't swing dramatically mid-season.
- **Weather features are NULL for games without a game_weather row:** The model handles this
  correctly (NULL → row dropped from training; NULL → feature passed as NaN at score time, XGBoost
  handles NaN natively). Run weather backfill before retraining to maximize training rows.
- **MLB Stats API team stats use Jan 1 snapshot dates for historical backfill:**
  The feature engine queries `as_of_date <= game_date`. Backfilled rows must use
  `{season}-01-01` as `as_of_date` (not Oct 1) so in-season games always find a row.
  `backfill_mlb_stats()` now uses this correctly.
- **Retraining against Supabase is slow (~3 hrs for 5 seasons):**
  Feature building makes per-game DB queries. At ~1s/game × 11K games, one model takes
  ~3 hours. Run retrains overnight or optimize with bulk pandas queries before next major
  retrain (see Section 12 performance note).

### What I'd Do Differently

- Build the SBR historical loader first (before the live odds ingestor) — it's the
  training data foundation and everything else depends on it
- Test the DB schema with real data before writing all the ingestors — one schema
  change cascades everywhere
- Add a data validation layer (check for nulls, range checks) before model training

---

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

**Known issues (active):**
- NHL h2h_3way 422 error: The Odds API no longer accepts `h2h_3way` market in the bulk request.
  Fix: move NHL 3-way to a separate API call or use `alternate_spreads`. Low priority until NHL models trained.

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

### F5 Models — v1 active (trained 2026-05-08)

| Model | AUC | CalError | Gate (≤5%) | Holdout rows | Notes |
|---|---|---|---|---|---|
| `mlb_f5_moneyline` | 0.648 | 5.1% | borderline | ~1,700 | v2 retrain 2026-05-04 |
| `mlb_f5_over_under` | 0.582 | 1.5% | PASS | 1,875 | v1 trained 2026-05-08 |
| `mlb_f5_runline` | 0.643 | 3.2% | PASS | 1,711 | v1 trained 2026-05-08 |

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

### NHL Models — Not started
Matt decided to focus on MLB first. NHL data not loaded, NHL models not trained.

---

## 12. Next Sessions — Where to Pick Up

**Paper trading evaluation starts 2026-04-14 (v8 models).**
Pipeline has been running since 2026-04-05 but pre-Apr 14 picks used v6 models
scoring against MLB Stats API features they weren't trained on — results are not
representative. All P&L, win rate, and go-live gate evaluation counts picks from
2026-04-14 onwards only. Old picks remain in the DB but are excluded from all queries.
Query picks via Supabase MCP in Claude mobile (see Section 17).

**After 50 picks — evaluate go-live gate:**
```
≥ 50 picks  +  positive flat-bet ROI  +  CalError ≤ 5%
```
If all three clear on paper trading, Matt approves moving to real money (minimum bets on DraftKings).

**Runline — structurally limited:**
Backtest generates 0 bets — SBR historical data has no runline prices. Model trains fine (AUC 0.592) but no historical edge signal to backtest. Will activate naturally once live odds are flowing via The Odds API.

**2025 data backfill — complete (2026-04-03):**
2025 pitcher stats (4,919 rows) and bullpen stats (16,269 rows) backfilled successfully.
Team stats also loaded (30 rows). 2025 is fully available for backtesting.

**Line movement check — new workflow:**
Re-fetch odds and check for movement 1-2 hours before game time:
```bash
python run_pipeline.py --step odds && python run_pipeline.py --step check-lines
```
SKIP = total line moved 0.5+ against your bet. CAUTION = price steamed 3%+ implied prob against you.

**Next retrain sequence (future use):**
All three MLB models are current (v8, 2026-04-14). When retraining is next needed:
```bash
# Refresh backfills (all idempotent — skip already-done dates)
python -m data.ingestors.mlb_stats_ingestor --backfill-pitchers 2019 2025
python -m data.ingestors.mlb_stats_ingestor --backfill-bullpen 2019 2025
python -m data.ingestors.weather_ingestor --backfill 2024 2025

# Retrain — now takes ~8 min total (bulk feature build, 100 Optuna trials)
python -m models.trainer --model mlb_moneyline
python -m models.trainer --model mlb_over_under
python -m models.trainer --model mlb_runline
```

**Phase 2 (future):**
→ F5 (first 5 innings) betting — separate model, needs F5 odds data source (Matt confirmed future version)
→ NHL: load NHL CSV data, run stats backfill, train 4 NHL models
→ Player props: MLB batter/pitcher props, NHL goals/shots (requires new ingestors)
→ Optuna trials already increased to 100 (session 9) — will take effect on next retrain

---

## 13. Environment

- **Python:** Matt has **Python 3.14** (`C:\Python314\python.exe`) — very new as of 2025
- **Key packages:** xgboost, scikit-learn, optuna, pybaseball, streamlit, plotly,
  loguru, requests, python-dotenv, statsapi, nhl-api-py
- **Project path (Matt's machine):** `C:\Users\Matth\.claude\Bet Repos\betting-model`
- **DB:** Supabase (Postgres) — project ref `vvprgnrmzeekokzkrkfu`. Connection string in `.env` as `DATABASE_URL`. Use the **Session pooler** connection string (port 5432, `aws-1-us-west-2.pooler.supabase.com`) for GitHub Actions — direct connection (port 5432, `db.vvprgnrmzeekokzkrkfu.supabase.co`) only works locally.
- **Models saved to:** `models/saved/` (auto-created by trainer)
- **Network note:** The Cowork sandbox blocks outbound pip/npm. All installs must run
  on Matt's local machine.
- **IMPORTANT — always use `python -m pip install` not `pip install`** on Matt's
  machine. Windows has multiple Python versions; `python -m pip` guarantees pip and
  python point to the same installation. `pip install` alone may install to the wrong one.

---

## 14. Tests

A pytest test suite lives in `tests/`. Run after models are trained (earlier tests are
less useful since pure function tests don't need data, but integration is more meaningful
with a populated DB).

```bash
# Install once
python -m pip install "pytest>=8.0.0"

# Run all tests
python -m pytest tests/ -v

# Run a single file
python -m pytest tests/test_scorer.py -v
```

**Coverage:**

| File | What it tests |
|------|--------------|
| `test_config.py` | Model registry, SPORTS config, threshold constants |
| `test_db_setup.py` | Schema creates all 11 tables, idempotency, column presence |
| `test_sbr_loader.py` | Team name normalization, odds parsing, date parsing, DB insert |
| `test_feature_engine.py` | Injury adjustment, starter-out detection, target computation |
| `test_scorer.py` | Implied prob conversion, Tenth-Kelly sizing, signal classification |
| `test_backtester.py` | Calibration error, P&L evaluation, go-live gate logic |

Tests are pure function tests — no external APIs, no SBR files needed. DB tests use
in-memory SQLite (via `conftest.py` fixture).

---

## 15. Conventions

- All team abbreviations are 3-letter (MLB: `NYY`, `BOS`; NHL: `TOR`, `VGK`)
- Season labels: MLB uses year of play (2024); NHL uses ending year (2024 = 2023–24)
- Dates: always ISO format `YYYY-MM-DD`
- Profit: positive = win, negative = loss
- Edge: always expressed as decimal (0.05 = 5%), not percentage
- `home_win = 1` means home team won the full game
- `home_win_reg = 1` means home team won in regulation (NHL only)

---

## 16. Claude Mobile — Daily Picks Interface

Matt queries picks daily via Claude on his phone. The Supabase MCP is connected to claude.ai.

### Setup
- Supabase integration connected at claude.ai Settings → Integrations
- Claude Project created with picks query and schema context baked in
- Project ID (Supabase): `vvprgnrmzeekokzkrkfu`

### Daily workflow
1. GitHub Actions runs **full pipeline at 11am ET** automatically. Steps (in order):
   - Settle yesterday's picks
   - Injuries
   - Game odds (DK full-game lines) + F5 odds (per-event endpoint, `FETCH_F5_LIVE=1`)
   - Prop odds (all 11 DK player prop markets via event-level endpoint)
   - MLB team stats, NHL stats, weather
   - Game scoring (moneyline, O/U, runline, F5 models)
   - Game log ingestion (yesterday's completed games — feeds prop rolling stats)
   - Prop scoring (pitcher K model — picks written to `picks` table alongside game picks)
2. **Odds refresh runs automatically at 12pm, 3pm, 6pm, and 8pm ET** (full-game odds + game scoring only). Refreshes do NOT re-fetch F5 or prop odds — those lock to the 11am snapshot.
3. Open Claude mobile → Betting project → ask "what are today's picks?"
4. Claude queries Supabase live and returns filtered picks

### Refresh mid-day (when lines move)
1. GitHub mobile → `github.com/MJACode/betting-model` → Actions → **Refresh Picks** → Run workflow
2. Wait ~2 min, then start a new Claude conversation to see updated picks

### Picks filter (action threshold)
Per-model thresholds (updated 2026-05-10 — F5 O/U and F5 RL disabled; prop pitcher K added):
```sql
WHERE signal_type = 'BET'
  AND (
    (model_id = 'mlb_moneyline'        AND model_probability >= 0.62 AND edge >= 0.10)
    OR (model_id = 'mlb_over_under'     AND model_probability >= 0.65 AND edge >= 0.14)
    OR (model_id = 'mlb_runline'        AND model_probability >= 0.65 AND edge >= 0.10)
    OR (model_id = 'mlb_f5_moneyline'   AND model_probability >= 0.65 AND edge >= 0.15)
    OR (model_id = 'mlb_prop_pitcher_k' AND model_probability >= 0.55 AND edge >= 0.05)
  )
```
Zero picks on a given day is valid — means no high-conviction plays.

**DK F5 odds coverage (confirmed 2026-05-10):**
- `h2h_1st_5_innings` (F5 ML): DK **does** carry this. Fetched via per-event endpoint at 11am. Scorer uses real DK odds; skips (no pick) if DK odds are absent. No subscription upgrade needed.
- `totals_1st_5_innings` (F5 O/U): DK does **not** offer this at any tier. **DISABLED** — scorer skips these games entirely (returns no picks). Not a subscription issue.
- `spreads_1st_5_innings` (F5 RL): Same — DK does not offer. **DISABLED** — scorer skips.

F5 O/U and F5 RL will not appear in picks until real DK lines become available. The models are trained and thresholds are set — they are ready to re-enable if DK ever lists these markets.

### Claude Mobile — Full Picks Chart Prompt (paste into project instructions)

This prompt produces a full chart of today's qualifying picks with game time (ET), live DK odds, weather, injury flags, and a Kelly-sized bet recommendation scaled to the bankroll the user provides.

```
You are a sports betting copilot connected to a Supabase database (project ref vvprgnrmzeekokzkrkfu).

When I ask "what are today's picks?" or similar:

1. Ask me for my current bankroll if I haven't given it. Accept any plain number ($1500, 1500, 1.5k).

2. Query the picks table joined to games, game_weather, and the latest live DK odds. Use today's date in America/New_York (ET) — never UTC.

   Use this SQL via the Supabase MCP (replace {today_et} with today's ET date YYYY-MM-DD):

   WITH latest_odds AS (
     SELECT DISTINCT ON (o.game_id, o.market) o.game_id, o.market,
            o.home_price, o.away_price, o.over_price, o.under_price,
            o.spread_home, o.total_line, o.snapshot_at
     FROM odds o
     WHERE o.bookmaker = 'draftkings'
     ORDER BY o.game_id, o.market, o.snapshot_at DESC
   )
   SELECT
     p.pick_id, p.pick_label, p.model_id, p.pick_side,
     p.model_probability, p.dk_implied_prob, p.edge,
     p.dk_odds AS scored_dk_odds, p.scored_line,
     p.kelly_fraction, p.confidence_tier,
     p.injury_flag, p.injury_detail,
     g.home_team, g.away_team, g.commence_time,
     w.temp_f, w.wind_mph, w.wind_dir_deg, w.wind_out_component,
     w.precip_mm, w.is_dome_game, w.venue,
     lo.home_price AS live_home_price, lo.away_price AS live_away_price,
     lo.over_price  AS live_over_price, lo.under_price AS live_under_price,
     lo.spread_home AS live_spread_home, lo.total_line AS live_total_line
   FROM picks p
   JOIN games g ON g.game_id = p.game_id
   LEFT JOIN game_weather w ON w.game_id = p.game_id
   LEFT JOIN latest_odds lo ON lo.game_id = p.game_id
        AND lo.market = CASE
            WHEN p.model_id LIKE '%f5_over_under%' THEN 'totals_1st_5_innings'
            WHEN p.model_id LIKE '%f5_runline%'    THEN 'spreads_1st_5_innings'
            WHEN p.model_id LIKE '%f5_moneyline%'  THEN 'h2h_1st_5_innings'
            WHEN p.model_id LIKE '%over_under%'    THEN 'totals'
            WHEN p.model_id LIKE '%runline%' OR p.model_id LIKE '%puckline%' THEN 'spreads'
            ELSE 'h2h' END
   WHERE p.game_date = '{today_et}'
     AND p.signal_type = 'BET'
     AND (
       (p.model_id = 'mlb_moneyline'        AND p.model_probability >= 0.62 AND p.edge >= 0.10)
       OR (p.model_id = 'mlb_over_under'     AND p.model_probability >= 0.65 AND p.edge >= 0.14)
       OR (p.model_id = 'mlb_runline'        AND p.model_probability >= 0.65 AND p.edge >= 0.10)
       OR (p.model_id = 'mlb_f5_moneyline'   AND p.model_probability >= 0.65 AND p.edge >= 0.15)
       OR (p.model_id = 'mlb_prop_pitcher_k' AND p.model_probability >= 0.55 AND p.edge >= 0.05)
     )
   ORDER BY g.commence_time, p.edge DESC;

3. For each row, compute the bet size from MY bankroll (not bankroll_at_pick):
       bet_size = round(kelly_fraction * my_bankroll, 2)
   kelly_fraction is already capped at 0.05 (5%) by the scorer, so no further cap is needed.

4. Render the result as a single Markdown table with these columns, in this order:

   | Game Time (ET) | Matchup | Pick | Model | Model % | DK Odds | Edge | Conf | Kelly % | Bet ($) | Weather | Injuries | Notes |

   - Game Time (ET): convert commence_time to America/New_York, format "h:mm AM/PM ET"
   - Matchup: "AWY @ HOM"
   - Pick: pick_label as stored
   - Model: short label (ML / O/U / RL / F5 ML / F5 O/U / F5 RL)
   - Model %: model_probability × 100, 1 decimal (e.g. 67.3%)
   - DK Odds: prefer live odds for the pick_side; fall back to scored_dk_odds; "N/A" if both null (F5 prob-only). Display as American format with sign (+150, -110).
   - Edge: edge × 100, 1 decimal, signed (+12.5%)
   - Conf: confidence_tier (HIGH / MED / LOW)
   - Kelly %: kelly_fraction × 100, 1 decimal (e.g. 3.0%)
   - Bet ($): the bet_size you computed in step 3
   - Weather: "Dome" if is_dome_game = 1; otherwise "{temp_f}°F, wind {wind_mph} mph (out {wind_out_component:+.1f})"; "—" if no weather row
   - Injuries: injury_flag if non-empty, else "—". Show injury_detail in a footnote if HIGH-confidence pick has any injury.
   - Notes: flag any F5 pick (model_id starts with 'mlb_f5_') where model_probability is between 0.65 and 0.675 as "⚠ Borderline (F5 only fetched at 11am — may shift if line moves)". Otherwise "—".

5. Below the table, print:
   - Bankroll: ${my_bankroll}
   - Total exposure: $sum(bet_size) and as % of bankroll
   - Number of picks by signal: BET count
   - Borderline F5 count: count of picks flagged ⚠ in Notes
   - Reminder: "Picks may flip to AVOID on later refreshes — re-query before placing bets. F5 picks are fetched once at 11am and do not refresh."

6. If zero rows, say "No picks meet the threshold for {today_et}. Zero picks is a valid signal — no high-conviction plays today."

Important rules:
- Never bet a pick that's flipped to AVOID. Only signal_type = 'BET' rows are returned.
- F5 picks have dk_odds = NULL (no DK F5 lines available). Display as "N/A" — settlement uses -110 for P&L.
- All times in ET. The pipeline uses America/New_York for game_date.
- If the user gives a new bankroll mid-conversation, re-render the table with updated bet sizes.
```

Save this in the Claude Mobile project's "Project Instructions" (claude.ai → Projects → Betting → Instructions). Update whenever thresholds or schema change. The codebase is the source of truth — re-sync the SQL block when `MODEL_PROB_THRESHOLDS` or `MODEL_EDGE_THRESHOLDS` in `config.py` change.

---

## 17. Learning Framework — Wins, Losses, and Model Adjustments

Matt has asked Claude to track results, learn from them, and propose adjustments — always
explaining the reasoning before making any change. Matt has final approval on all changes.

### Signal Flip Rule (BET → AVOID between refreshes)

With 5 daily runs (7am, 12pm, 2pm, 6pm, 8pm ET), a pick can flip signal between refreshes:
- Each refresh **deletes all pre-game picks** and re-scores from scratch
- If a pick was BET at noon but generates AVOID at 2pm, the AVOID replaces it in the DB
- **The AVOID should be honored** — do not bet a pick that has flipped to AVOID
- If a pick was BET but falls into the no-signal zone on a later refresh, it simply disappears

**Settlement rule:** Only picks with `signal_type = 'BET'` at game-start lock time are settled for P&L. AVOID picks are never settled and never count in win rate or ROI tracking. This is enforced in `paper_tracker.py` with `AND p.signal_type = 'BET'` in the settlement query.

### Action Threshold (what Matt actually bets)

Two layers — both defined in `config.py`:

**BET signal thresholds** (`MODEL_PROB_THRESHOLDS` / `MODEL_EDGE_THRESHOLDS`) — scorer uses these to generate a BET:

| Model | Min Prob | Min Edge | Notes |
|---|---|---|---|
| `mlb_moneyline` | 62% | 10% | |
| `mlb_over_under` | 65% | 14% | |
| `mlb_runline` | 65% | 10% | |
| `mlb_f5_moneyline` | 65% | 15% | Real DK odds only — skips if no DK line |
| `mlb_f5_over_under` | 65% | 15% | DISABLED — DK does not carry this market |
| `mlb_f5_runline` | 65% | 15% | DISABLED — DK does not carry this market |
| `mlb_prop_pitcher_k` | 55% | 5% | Poisson regression, conservative initial thresholds |

**Action filter** (`ACTION_THRESHOLDS`) — display filter for dashboard and Claude mobile:

| Model | Min Prob | Min Edge | Notes |
|---|---|---|---|
| `mlb_moneyline` | 62% | 10% | |
| `mlb_over_under` | 65% | 14% | |
| `mlb_runline` | 65% | 10% | |
| `mlb_f5_moneyline` | 65% | 15% | Real DK odds only |
| `mlb_prop_pitcher_k` | 55% | 5% | Tune after 50+ settled picks |

*(Updated 2026-05-10 — F5 O/U and F5 RL removed from action filter (disabled, no DK lines). Prop pitcher K added at conservative 55%/5% initial thresholds.)*

All P&L reviews, win rate tracking, and ROI evaluation use **only these filtered picks**.

Query for filtered picks (evaluation starts 2026-04-14):
```sql
SELECT * FROM picks
WHERE signal_type = 'BET'
  AND game_date >= '2026-04-14'
  AND (
    (model_id = 'mlb_moneyline'        AND model_probability >= 0.62 AND edge >= 0.10)
    OR (model_id = 'mlb_over_under'     AND model_probability >= 0.65 AND edge >= 0.14)
    OR (model_id = 'mlb_runline'        AND model_probability >= 0.65 AND edge >= 0.10)
    OR (model_id = 'mlb_f5_moneyline'   AND model_probability >= 0.65 AND edge >= 0.15)
    OR (model_id = 'mlb_prop_pitcher_k' AND model_probability >= 0.55 AND edge >= 0.05)
  )
ORDER BY game_date DESC;
```

### Review Cadence

All milestones below count filtered picks from **2026-04-14** onwards only (v8 model evaluation start). Per-model thresholds: ML prob ≥ 62% / edge ≥ 10%; O/U prob ≥ 65% / edge ≥ 14%; RL prob ≥ 65% / edge ≥ 10%.

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
| `mlb_prop_batter_rbi` | RBIs per game | Poisson regression | |
| `mlb_prop_batter_runs` | Runs scored per game | Poisson regression | |
| `mlb_prop_batter_hr` | HR per game | Logistic (binary) | Rare event — Poisson breaks down |
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
- `player_savant_stats` — Baseball Savant Statcast metrics per player per season
- `umpires` — historical umpire K rates by umpire_id
- `lineup_slots` — confirmed lineup position per player per game

**New ingestors (built):**
- `baseball_savant_ingestor.py` — Statcast leaderboard CSV (k%, whiff%, xERA, velo, barrel%, xBA)
- `prop_odds_ingestor.py` — The Odds API player prop markets for DK (all 11 markets, event-level)

**Still needed:**
- `lineup_ingestor.py` — confirmed lineups from MLB Stats API
- `umpire_ingestor.py` — umpire assignments + K rates from UmpScorecard

### Key Features (pitcher K model — live)

17 features: k_last3/5/10_avg, k_rate_last3/5, ip_last3/5_avg, season_k_avg, k_trend, savant_k_pct, savant_whiff_pct, savant_bb_pct, savant_xera, savant_avg_velocity, opp_team_k_pct, is_dome_game, temp_f. Prior-season fallback for season_k_avg when current-season logs unavailable.

### Build Sequence

| Phase | Work | Status |
|---|---|---|
| 1 — Foundation | DB tables + game_log backfill + savant_ingestor + prop_odds_ingestor | DONE |
| 2 — Pitcher K model | feature engine + train mlb_prop_pitcher_k + scorer + pipeline wiring | DONE |
| 3 — Batter props | Feature engine for batters + train hits/TB/HR | Next |
| 4 — Remaining props | Remaining pitcher + batter models + dashboard tab | Future |

---

*Last updated: 2026-05-10 (session 15)*

**Session summary (2026-05-10, session 15 — pitcher K prop pipeline complete + F5 O/U and RL disabled):**
- Built `features/prop_feature_engine.py`: Poisson feature builder — 17 features (rolling K avgs, K rates, IP, season avg with prior-season fallback, Savant k%/whiff%/xERA/velo, opponent team K%, dome, temperature). Bulk loads with bisect ASOF lookups. 46% null drop rate in training (new pitchers with no prior data).
- Trained `mlb_prop_pitcher_k` v20260509_201850: 10,503 training rows (2019-2023), 2,917 holdout rows (2024). Best CV Poisson NLL: 2.2302. Holdout MAE: 1.80 Ks, RMSE: 2.24, O/U accuracy: 64.3%, CalError: 11.6%. Top features: k_last10_avg (25.3%), season_k_avg (17.7%), k_last5_avg (11.2%).
- Extended `models/scorer.py` with `run_prop_scorer()`: fetches probable starters via statsapi, builds feature rows, predicts lambda via Poisson regression, converts to P(over/under) via Poisson CDF, compares to real DK implied prob, writes BET/AVOID picks to `picks` table. Tenth-Kelly sizing.
- Fixed `prop_odds_ingestor.py`: The Odds API returns `name="Over"/"Under"` and `description="Player Name"` — the field names are counterintuitive. Prior implementation had them swapped, storing "Over"/"Under" as player_name. Fixed. Re-ran ingestor: 652 rows, 9/10 games covered. Deleted ghost "Over"/"Under" player_name rows from pre-fix run.
- Wired `step_prop_scoring()` and `step_game_log()` into `run_pipeline.py`. Pipeline is now 9 steps: settle, injuries, odds+F5, prop_odds, mlb_stats, nhl_stats, weather, scoring, game_log, prop_scoring.
- Wired daily 2026 game log ingestion: `ingest_game_log_for_date(yesterday)` added to `mlb_stats_ingestor.py`. Idempotent. 2026 season backfill complete (13,456 rows, 35 game dates).
- First live picks (2026-05-09, re-scored with fresh 2026 data): Blake Snell Over 5.5 Ks (+17.3% edge, DK +124, $29), Braxton Ashcraft Under 4.5 Ks (+17.1%, DK +117, $30), Joe Ryan Over 4.5 Ks (+13.5%, DK +120, $23). Directions shifted materially after 2026 backfill (Joe Ryan BET Over initially flipped to AVOID with stale data; Braxton Ashcraft Under flipped to Over after 2026 K backfill). Confirms daily game log ingestion is load-bearing.
- DK F5 line coverage confirmed: h2h_1st_5_innings (F5 ML) available from DK via per-event endpoint at 11am. totals_1st_5_innings (F5 O/U) and spreads_1st_5_innings (F5 RL) not offered by DK at any subscription tier — confirmed by querying odds table.
- Disabled F5 O/U and F5 RL scoring: removed prob-only fallback from scorer. Scorer now returns `[]` (no picks) for any F5 market without real DK odds. `_score_f5_prob_only()` remains in scorer.py for easy re-enable if DK ever lists these markets. F5 ML scoring unchanged — uses real DK odds, skips when absent.
- Updated config.py, Section 16, and Section 17 to reflect disabled F5 O/U/RL and new prop pitcher K thresholds. ACTION_THRESHOLDS and picks filter SQL updated throughout.

**Session summary (2026-05-09, session 14 — F5 live odds + 11am schedule):**
- Diagnosed why no live DK F5 odds were ever stored: F5 markets are "additional markets" on The Odds API and NOT returned by the bulk endpoint. Require the per-event endpoint. Replaced broken bulk F5 call with `_fetch_f5_per_event()`.
- Gated F5 fetch with env var `FETCH_F5_LIVE` — only 11am pipeline triggers it. Mid-day refreshes skip F5.
- Removed 7am cron from `daily_pipeline.yml`. Full pipeline now runs only at 11am ET with `FETCH_F5_LIVE=1`.
- Updated mobile chart prompt with Notes column flagging borderline F5 picks (prob 0.65-0.675).
- Raised all F5 thresholds to 65% prob / 15% edge (was 60%/10%, 57%/7%, 58%/8%). Updated config.py, Section 16 query, Section 17 threshold tables.
- Replaced flat 1% F5 bet sizing with Kelly sizing. At p=0.65: 3.0% of bankroll; at p=0.70: 4.0%; capped at 5%.
- Fixed `picks.dk_odds NOT NULL` constraint: dropped to nullable. F5 prob-only picks insert NULL by design. Updated db_setup.py to match.

**Session summary (2026-05-08, session 15):**
- Built and deployed full Phase 2 player props infrastructure (DB tables, ingestors, game log backfill).
- Applied DB migration to Supabase: 5 new tables live (player_game_log, player_prop_odds, player_savant_stats, umpires, lineup_slots).
- Built `data/ingestors/prop_odds_ingestor.py` and `data/ingestors/baseball_savant_ingestor.py`.
- Added `backfill_player_game_log()` to `mlb_stats_ingestor.py`. Game log backfill 2019-2025 complete.
- Added `PROP_MARKETS_ALL`, `PROP_MODELS`, `SAVANT_BASE_URL` to config.py.

**Session summary (2026-05-08, session 14):**
- Planned full MLB player props infrastructure (Phase 2). Decisions locked in Section 18.
- Architecture: count projection + Poisson regression. One model per prop type (11 models total). HRs and SBs use logistic.
- Build order: pitcher Ks first (most predictable), then batter props, then remaining props.

**Session summary (2026-05-08, session 13):**
- Built full F5 betting infrastructure: mlb_f5_over_under and mlb_f5_runline trained and live.
- Calibrated F5 total line factor from 26,443 historical games: actual factor = 0.6197 (was 0.56 placeholder). Updated F5_TOTAL_FACTOR in config.py to 0.62. All F5 O/U synthetic lines use this.
- Created `data/ingestors/f5_odds_synthesizer.py`: generates synthetic `totals_1st_5_innings` (total_line = fg_total × 0.62) and `spreads_1st_5_innings` (spread_home = -0.5) odds rows for 13,508 historical games. Inserted as bookmaker='sbr_consensus' so bulk feature loader picks them up. Idempotent.
- Fixed odds_ingestor.py: added separate F5 markets API call for MLB after the main bulk fetch. If The Odds API supports F5 lines for DraftKings, they'll be stored automatically. If not (422 or empty), pipeline continues unaffected and scoring falls back to prob-only.
- Fixed backtester.py: added check — synthetic F5 odds rows have total_line/spread_home but no prices. The backtester was finding these rows (dk_odds not None), entering the real-odds path, and generating zero picks because over_price/home_price were None. Added null-prices check before `if not dk_odds:` to force prob-only path for synthetic rows.
- Extended scorer.py `_score_f5_prob_only`: added handlers for `totals_1st_5_innings` (derives synthetic F5 line from full-game odds × F5_TOTAL_FACTOR, uses as scored_line for settlement) and `spreads_1st_5_innings` (fixed spread = -0.5, same label convention as full-game RL).
- Model results (v1, trained 2019–2024 on synthetic lines):
  - mlb_f5_over_under: AUC 0.582, CalError 1.50% (PASS). 2024 OOS: 1,410 picks / 62.3% / +19.0%. 2025 blind: 1,259 picks / 63.0% / +20.3%.
  - mlb_f5_runline: AUC 0.643, CalError 3.24% (PASS). 2024 OOS: 853 picks / 66.9% / +27.8%. 2025 blind: 835 picks / 63.8% / +21.9%.
- Thresholds set conservatively for prob-only scoring: F5 O/U 57%/7%, F5 RL 58%/8%. Tune after 50+ live picks.
- Key caveat: F5 O/U and RL ROI is measured against SYNTHETIC lines. Real win rate may differ. F5 RL has the same binary outcome as F5 ML (home wins F5) — both can fire on the same game, doubling exposure. Monitor correlation in live results.
- F5 O/U generates ~1,300 picks/season at current thresholds — high volume vs full-game models (~300). Treat as directional signal until real DK F5 lines accumulate.

**Session summary (2026-05-04, session 12):**
- Ran F5 linescore backfill: 15,866 games updated across 2019–2025 (home_score_f5/away_score_f5).
- Fixed backtester: F5 moneyline had no historical DK F5 odds so all games were skipped with `continue`.
  Added prob-only path for `h2h_1st_5_innings` matching the scorer: synthetic edge = model_prob - 0.50,
  synthetic DK odds = -110 for ROI calc, flat 1% bet. Added MODEL_PROB_THRESHOLDS + MIN_MODEL_PROB imports.
- Fixed trainer: `str(path.relative_to(...))` used Windows backslashes in model_registry, breaking
  GitHub Actions (Linux). Fixed to `.as_posix()` — no more manual SQL fixes after retrains.
- v1 F5 ML backtest results (trained 2019–2023):
  - 2024 OOS: 686 picks / 62.5% win / +19.4% ROI / CalError 5.3%
  - 2025 blind: 757 picks / 56.8% win / +8.4% ROI / CalError 12.0%
- Retrained F5 ML v2 (2019–2024 train, 2025 holdout): AUC 0.648 / CalError 5.1% on holdout.
  Top features: d_starter_era (18%), d_starter_era_last3 (17%), d_woba (7%), d_iso (7%), d_ops (7%).
- v2 2025 backtest: 818 picks / 56.4% win / +7.6% ROI / CalError 12.4% (still high).
  CalError gap explained: trainer measures full probability distribution (5.1%); backtester measures
  only the filtered high-prob tail (≥60%) where the model is most overconfident. Structural limitation
  of prob-only scoring — no real DK F5 odds to anchor the edge. ROI is still positive so directional
  signal is real. Will improve as live F5 odds accumulate.
- F5 ML is now active in paper trading. All picks going forward use v2 model.

**Session summary (2026-05-03, session 11):**
- Diagnosed why F5 ML picks were never appearing. Three bugs found and fixed:
  1. **Logging crash** (`scorer.py:780`): `p['dk_odds'] > 0` raised `TypeError` when `dk_odds` is `None`
     (prob-only F5 picks). Crash propagated before `conn.commit()` — picks were inserted but rolled back.
     Fixed with a None guard (`if p['dk_odds'] is None: dk_odds_str = "N/A"`).
  2. **model_registry path** (Supabase): F5 model was registered with Windows backslashes
     (`models\\saved\\...`), which fails on GitHub Actions (Linux). Fixed to forward slashes via SQL UPDATE.
  3. **Mobile picks query**: hardcoded SQL in Claude mobile project didn't include `mlb_f5_moneyline`.
     Updated in CLAUDE.md and Section 17 query — must also update the Claude mobile Project instructions manually.
- Confirmed fix: dry run completed with SUCCESS, no crash, F5 O/U/RL warned (no model — expected).
- F5 ML picks will start appearing at next 7am pipeline run. Edge displayed as `model_prob - 0.50` vs fair.
- F5 O/U and F5 RL still untrained (no historical F5 odds). Will tackle with synthetic lines when ready.

**Session summary (2026-04-23, session 10):**
- Updated CLAUDE.md to match current thresholds in `config.py` (runline edge 14% → 10%, moneyline
  action filter clarified as 60%/9% display vs 58%/7% BET signal).
- Added rule: CLAUDE.md must be updated after every commit with what changed and why.
- Latest commit on master: `4140bca` — "Lock picks for started games and update action thresholds"
- Recent threshold changes (from git log):
  - `4140bca`: Locked picks for started games; updated action thresholds
  - `1adf8ff`: O/U and runline action filter set to 65%/14%; moneyline stays 58%/7%
  - `de292fa`: Lowered moneyline/runline scoring and action thresholds to 58%/7%

**Session summary (2026-04-14, session 9):**
- Applied bulk loading optimization to `backtester.py`: imported `_build_bulk_mlb_lookups` +
  `_build_mlb_features_from_bulk` from feature_engine, replaced per-game DB queries with in-memory
  lookups for MLB models. Full 3-model backtest: ~3 hours → ~1-2 min.
- Ran definitive v8 backtests for 2024 + 2025. Results:
  - 2024: 588 BETs, 58.7% win, +18.6% ROI, CalError 4.0% (PASS)
  - 2025: 554 BETs, 60.7% win, +21.1% ROI, CalError 5.0% (borderline)
  - Combined: 1,142 BETs, 59.6% win, +19.8% ROI, +226.1 units
- Ran 2025 weather backfill across multiple passes (Open-Meteo 429 rate limits): 87.7% coverage
  (2,145/2,446 games). Remaining 12.3% are Oct/Nov playoff dates. Will fill on next rate limit reset.
- Completed paper trading milestone review (62 picks, 40+50 checkpoints). Key finding: all 62 picks
  are from v6 model (pre-retrain). Apr 11-13 period (v6 model scoring on MLB Stats API features it
  wasn't trained on) showed 30.8% win rate — model-feature distribution mismatch, not a real signal.
  True v8 paper trading evaluation starts Apr 14.
- O/U dominance flagged: 55/62 paper trading picks (88.7%) are O/U — warrants monitoring with v8 model.
- Increased Optuna trials from 50 to 100 in `trainer.py` — will take effect on next retrain.
- Completed 2025 weather backfill: 100% coverage (2,446/2,446 games). All seasons now fully covered.
- Completed bullpen stats backfill for 2022-2025 (30,425 new rows). Previously only 2019-2021 had
  full coverage; 2022 was 41%, 2024 61%, 2025 0%. All seasons now have 200+ game dates covered.
  Bullpen workload features (`d_bullpen_ip_last3`, `home/away_bullpen_ip_last1/3`) are now live data
  instead of zeros. v8 models were trained with incomplete bullpen data — next retrain (v9) will benefit.

**Session summary (2026-04-14, session 8):**
- Ran pitcher backfill (`--backfill-pitchers 2019 2025`) — all dates already done, 0 new rows (idempotent).
- Ran weather backfill (`--backfill 2019 2025`) — 10,000 rows written for 2019–2023; 2024 coverage was only
  16% (390/2,443 games) due to Open-Meteo 429 rate limits. Re-ran `--backfill 2024 2024` separately;
  2,052 new rows, now 2,441/2,443 (≈100%) coverage for 2024.
- Completed v8 retrain of all 3 MLB models. Results: moneyline AUC 0.619 / CalError 2.12% (PASS),
  O/U AUC 0.575 / CalError 4.64% (PASS), runline AUC 0.629 / CalError 5.56% (borderline — improved
  from 5.87% but above 5% gate; accepted as secondary model with no backtest bets).
- Resolved critical performance issue: feature build was taking 6+ hours per model due to ~165,000
  per-game DB round trips to Supabase. Fixed by adding bulk loading path to `feature_engine.py`:
  `_build_bulk_mlb_lookups()` loads all 8 tables in ~8 queries; per-game loop uses in-memory
  dict/bisect lookups. Feature build now takes ~3 seconds. Live scoring path unchanged.
- Note: first v8 O/U and runline retrains failed with "server closed the connection" — Supabase
  dropping the long-running connection. Resolved by the bulk loading fix above.
- Ran v8 backtests for 2024 + 2025. 2025 O/U showed 0 bets because 2025 weather coverage was 0% at
  the time (Open-Meteo rate limits exhausted before reaching 2025 during the `--backfill 2019 2025` run).
  Fixed in session 9: ran `--backfill 2025 2025` across 3 passes (rate limit ~50 dates/10 min),
  reaching 71.8% (1,757/2,446 games) — Oct/Nov playoff dates remain uncovered.
  v8 2025 O/U backtest result: 213 bets / 57.8% win / +11.9% flat ROI / CalError 4.0% (PASS).

**Session summary (2026-04-12):**
- Completed FanGraphs removal from `mlb_stats_ingestor.py`: replaced `_build_pitcher_rows` and
  `backfill_pitcher_stats` FanGraphs DataFrame lookups with `_fetch_mlb_api_pitcher_stats` +
  `_fetch_savant_pitcher_stats` dict lookups. Normalized-name keyed dict + last-name fallback
  preserves same match coverage. Savant enriches ERA/K9/BB9/WHIP/HR9 with xFIP/SwStr%/CSW%
  using MLBAM player_id as join key (same ID space as MLB Stats API).
- Built `weather_ingestor.py` (new file): all 30 MLB stadiums with lat/lon/hp-to-CF bearing/
  dome flags. `_wind_out_component(mph, dir_deg, bearing)` uses meteorological convention
  (wind_from direction). `_is_dome_game` handles fixed domes + retractable (closes if temp_f < 50
  or precip_mm > 0.3). Open-Meteo archive API for historical (>5 days), forecast API for recent.
  Upserts to `game_weather` table per game_id.
- Created `game_weather` Supabase table (migration applied): game_id (UNIQUE), game_date,
  home_team, venue, temp_f, wind_mph, wind_dir_deg, wind_out_component, precip_mm, is_dome_game.
- Updated `feature_engine.py`: re-added starter features (removed temporarily due to Oct 1
  snapshot bug), added weather features, added `_get_game_weather()` helper.
  - `MLB_H2H_FEATURES` (30 features): +5 starter diffs restored
  - `MLB_TOTALS_FEATURES` (22 features): +4 starter absolutes + wind_out_component/temp_f/is_dome_game
  - `MLB_SPREADS_FEATURES`: inherits H2H + spread_home + wind_out_component + is_dome_game
  - Weather placement rationale: TOTALS primary (wind+temp+dome), RUNLINE moderate (wind+dome), MONEYLINE none
- Updated `run_pipeline.py`: added `step_weather()`, inserted as Step 5/6 between NHL stats and
  scoring. Added `weather` to `--step` CLI choices.
- v8 retrain blocked on backfills: must run `--backfill-pitchers 2019 2025` and weather
  `--backfill 2019 2025` before training. Both commands ready to run.

**Session summary (2026-04-11):**
- Diagnosed under-pick bias: identical model_probability (0.7046) for MIN vs DET on Apr 8 and Apr 9
  confirmed stale team stats — FanGraphs froze Apr 7 due to an IP-level 403 block from heavy dev scraping.
  Not a real signal. Picks from Apr 8-10 are tainted by stale data.
- Replaced FanGraphs/pybaseball entirely with MLB Stats API (`statsapi.mlb.com/api/v1/teams/stats`)
  for all team batting and pitching stats. wOBA computed from linear weights, wRC+ normalized by league
  average (avg wRC+ = 100.0 across all backfilled seasons — verified correct), FIP from components.
  FanGraphs is permanently removed. Do not attempt to re-add it.
- Fixed backfill snapshot date: historical rows were written with `{season}-10-01` as `as_of_date`.
  Feature engine uses `WHERE as_of_date <= game_date`, so October dates excluded all April games
  (fallback to prior season). Fixed to `{season}-01-01` so the snapshot is always before any game.
  Re-ran full backfill 2019-2025 with correct dates.
- Added 2019 to backfill: trainer uses 2019-2023 training seasons; 2019 was missing from prior run.
- Fixed settlement — it had never run. Root cause: `paper_tracker.py` required `g.home_score IS NOT NULL`
  but the live pipeline never populated scores in the games table. Added `_fetch_and_store_scores()`
  to paper_tracker using `statsapi.schedule()`, wired before the picks query. Also fixed:
  - DISTINCT ON (game_id) in both odds subquery JOINs to prevent row multiplication (2401 picks → correct count)
  - UPDATE params changed from SQLite `?` to psycopg2 `%s`
  - Removed `.rowcount` attribute access (not exposed by DBConnection wrapper)
- Settled all 6 days of paper trading after fixes. BET-only record (prob ≥ 65%, edge ≥ 14%):
  34 picks, 16W-17L-1P, -$267 flat, -$67 Kelly. Apr 8-10 tainted by stale data. 34/50 toward gate.
- Started v7 retrain overnight (PID 2611): all 3 MLB models, 20 Optuna trials each, sequential.
  Training takes ~3 hours due to per-game Supabase queries in feature engine (~1s × 11K games).
- Proxy rotation decision: not needed. All remaining data sources are official MLB Stats API,
  NHL Stats API, Odds API (authenticated), or ESPN (low-traffic). FanGraphs was the only
  problematic scraping target and has been permanently eliminated.
- Weather integration: deferred at end of session (paper trading gate not yet passed). Built
  and wired in session 7 (2026-04-12) — see session 7 summary above.

**Session summary (2026-04-05):**
- Fixed ESPN injury API format change: `status` is now a plain string, `athlete` is now `{"$ref": url}`.
  Updated `_fetch_espn_team_injuries` to follow athlete ref for name/id, and updated `ESPN_STATUS_MAP`
  with lowercase variants ("10-day IL", "out", "day-to-day") and "Paternity". 361 MLB + 110 NHL injuries fetched.
- Added FanGraphs retry (1 retry, 10s sleep) and prior-season fallback in all three fetch functions.
  FanGraphs 2026 is now working; fallback protects future 403 days.
- Fixed `::TEXT` cast bug in `data/db.py`: `_NAMED_PARAM_RE` regex was converting `::TEXT` PostgreSQL
  casts into `%(TEXT)s` named params. Added negative lookbehind `(?<!:)` to fix.
- Fixed `decimal.Decimal` type mismatch: Postgres returns NUMERIC as `Decimal`, not `float`. Registered
  `DEC2FLOAT` psycopg2 adapter in `data/db.py` — all NUMERIC columns now return float globally.
- Fixed SQLite `date(?, modifier)` in `feature_engine.py` `_get_bullpen_workload`: replaced with Python
  `timedelta` cutoff. Postgres has no `date()` modifier function.
- Registered v6 model paths in Supabase `model_registry` (relative paths). Updated `load_model()` in
  `trainer.py` to resolve relative paths against project root — same row works locally and on GitHub Actions.
- Fixed Python 3.12 vs 3.14 annotation evaluation: added `import sqlite3` to `injury_ingestor.py`,
  `mlb_stats_ingestor.py`, `nhl_stats_ingestor.py`. Python 3.14 evaluates annotations lazily; 3.12 does not.
- Fixed GitHub Actions database connection: switched `DATABASE_URL` secret to Supabase session pooler
  (`aws-1-us-west-2.pooler.supabase.com:5432`) — direct IPv6 connection unreachable from Actions runners.
- Fixed scorer duplicate picks: scorer now deletes all unsettled picks for `target_date` before
  re-inserting. Prevents duplicates when Refresh Picks workflow runs mid-day.
- Set up Claude mobile integration: Supabase MCP connected to claude.ai, Project created with schema
  context and picks query. Picks filtered to prob ≥ 65% / edge ≥ 14% in Project instructions.
- Added `refresh_picks.yml` GitHub Actions workflow — manual trigger to re-run odds + scoring mid-day
  when lines have moved. Triggered from GitHub mobile app.

**Session summary (2026-04-01, continued):**
- Investigated null feature rates: 7 features null 100% of the time (runs_per_game never populated; all 6 starter features — no historical pitcher data in games table or mlb_pitcher_stats).
- Removed dead features from FEATURE_MAP: d_runs_per_game, d_starter_era/xfip/k9/bb9/era_last3/xfip_last3, home/away_runs_per_game (totals), home/away_starter_era/xfip (totals).
- Changed build_training_dataset: drops null rows instead of imputing with median (~35% of rows dropped — early-season games).
- Changed trainer.py: raises ValueError if feature columns are missing instead of silent 0-fill.
- Retrained all 3 MLB models (v3). CalError improved: moneyline 4.49%→2.03%, O/U 0.59%→0.41%, runline 4.13%→3.45%.
- Clean backtest (no imputation): moneyline OOS -24.68u / 44.0% win (improved from -56.35u). O/U and runline generate 0 bets (correct — no edge without pitcher data; runline backtest also structurally broken without real spread prices).
- Next priority: backfill historical pitcher-game data from MLB Stats API.

**Session summary (2026-04-01, morning):**
- All 3 MLB models finished training overnight (started 2026-03-31, runline completed 2026-04-01 07:38)
- mlb_over_under: AUC 0.503, CalError 0.59% (PASS). Top feature: total_line (model follows market)
- mlb_runline: AUC 0.558, CalError 4.13% (PASS, down from 8.0%). scale_pos_weight=1.735 fixed class imbalance
- Edge diagnosis on 100 sample 2024 games: 44/200 sides clear +3% BET threshold — scorer is working
- CLAUDE.md updated. System is ready for paper trading.

**Session summary (2026-03-31):**
- Renamed `data/raw/sbr/` → `data/raw/datawarehouse/`; updated all path references in `config.py` and `sbr_loader.py`
- Fixed critical scorer bug: `_get_dk_odds` only queried `bookmaker = 'draftkings'`, so no historical SBR games ever returned odds → zero picks. Added `sbr_consensus` fallback. This was the root cause of ROI = 0.0.
- Fixed rolling stats: `runs_last_5`, `runs_last_10` were stale end-of-season snapshot values. Now computed directly from the games table using the exact game date in `feature_engine.py`, so each training row has accurate rolling context.
- Fixed runline class imbalance: added `scale_pos_weight = neg/pos` to both Optuna objective and final XGBClassifier in `trainer.py`. Home covers only ~35% — XGBoost was biased toward predicting away covers.
- Trained `mlb_moneyline`: AUC 0.556 (up from 0.541), CalError 4.49% (PASS). Top features: wRC+, team WHIP, bullpen ERA.
- `mlb_over_under` and `mlb_runline` training was started but feature build is very slow (per-game SQL rolling queries). Optimize before next retrain — see Step 1 in next session notes.

**Session summary (2026-
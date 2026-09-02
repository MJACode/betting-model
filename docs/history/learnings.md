# Learnings and rejected approaches

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

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
## 9. What Was Rejected and Why
**AlphaPy** — Cloned initially, then rejected because:
- Last updated ~2020, uses deprecated pandas APIs
- Team-level only, no player props support
- Data connectors (Google Finance, IEX, Yahoo) all defunct
- Not worth salvaging — built from scratch instead

**npm `docx` package** — Blocked by workspace network proxy (403 Forbidden).
All Word documents generated with `python-docx` instead.

---

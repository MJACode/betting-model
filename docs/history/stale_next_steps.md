# Next-session notes (stale — April 2026 era)

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

> Kept for provenance only. Superseded by later sessions; do not act on it
> without checking `docs/sessions/` first.

## 12. Next Sessions — Where to Pick Up
**Paper trading evaluation starts 2026-04-14 (v8 models).**
Pipeline has been running since 2026-04-05 but pre-Apr 14 picks used v6 models
scoring against MLB Stats API features they weren't trained on — results are not
representative. All P&L, win rate, and go-live gate evaluation counts picks from
2026-04-14 onwards only. Old picks remain in the DB but are excluded from all queries.
Query picks via Supabase MCP in Claude mobile (see `docs/thresholds.md`).

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

**Website (in progress):**
Building a website to display all picks (not just BET signals) so users can filter. Two changes enable this:
- `scorer.py` now writes `signal_type = 'NONE'` rows for dead-zone game and prop picks (kelly_fraction = 0). Previously returned None and discarded. Settlement, paper tracking, and Claude mobile are unaffected — all filter on `signal_type = 'BET'`.
- Website queries the `picks` table without the `signal_type = 'BET'` filter.

**Batter props — next up:**
Lineup ingestor is complete and unblocked. Build order:
1. Batter prop feature engine (`features/prop_feature_engine.py` extension or new file)
2. Train `mlb_prop_batter_hits`, `mlb_prop_batter_tb`, `mlb_prop_batter_hr` (logistic)
3. Wire scoring into `run_prop_scorer()`

**Phase 2 (future):**
→ NHL: load NHL CSV data, run stats backfill, train 4 NHL models
→ Optuna trials already increased to 100 (session 9) — will take effect on next retrain

---

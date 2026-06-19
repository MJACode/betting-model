"""
config.py — Central configuration loader.

All other modules import from here. Never access os.environ directly elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ─────────────────────────────────────────────────────────────────
# Works from any working directory because we resolve relative to this file.
ROOT = Path(__file__).parent.resolve()
load_dotenv(ROOT / ".env")

# ── API Keys ──────────────────────────────────────────────────────────────────
ODDS_API_KEY: str = os.environ.get("ODDS_API_KEY", "")

# ── Database ──────────────────────────────────────────────────────────────────
# DATABASE_URL is the primary connection string used by all production code.
# Format: postgresql://user:password@host:5432/dbname
# Set in .env for local dev; set as Railway env var in production.
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# DB_PATH is kept for backwards compat with tests (in-memory SQLite fixtures).
DB_PATH: Path = ROOT / os.environ.get("DB_PATH", "data/betting_model.db")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

# ── Paper Trading ─────────────────────────────────────────────────────────────
BANKROLL: float = float(os.environ.get("BANKROLL", 1000))
# Evaluation start date — picks before this date are excluded from all P&L and
# go-live gate calculations. Set to when v8 models first ran live.
PAPER_TRADING_START: str = os.environ.get("PAPER_TRADING_START", "2026-04-14")

# ── Thresholds ────────────────────────────────────────────────────────────────
# Global fallback — used when a model has no specific override below.
BET_EDGE_THRESHOLD: float   = float(os.environ.get("BET_EDGE_THRESHOLD",   0.10))
AVOID_EDGE_THRESHOLD: float = float(os.environ.get("AVOID_EDGE_THRESHOLD", 0.10))

# Minimum model probability to generate a BET signal.
MIN_MODEL_PROB: float = float(os.environ.get("MIN_MODEL_PROB", 0.65))

# Per-model action filter — used by dashboard and Claude mobile for display filtering.
ACTION_THRESHOLDS: dict = {
    "mlb_moneyline":      {"min_prob": 0.72, "min_edge": 0.12},  # kept (2026-06-06 sweep: 19 bets +23.2% ROI — best cut)
    "mlb_over_under":     {"min_prob": 0.68, "min_edge": 0.12},  # LOWERED 72%/15%→68%/12% (2026-06-06): 18 bets +22.2% ROI (was +1.0% over 12) — more volume AND higher ROI as data settled
    "mlb_runline":        {"min_prob": 0.68, "min_edge": 0.10},  # LOWERED 70%/12%→68%/10% (2026-06-06): 12 bets +1.1% — only positive cut at volume (overall -13.6% over 19); retrain pending
    "mlb_f5_moneyline":   {"min_prob": 0.68, "min_edge": 0.07},  # kept (2026-06-06: 47 bets +8.4% ROI)
    # mlb_f5_over_under and mlb_f5_runline: DISABLED — DK does not carry these markets.
    # Scorer skips them until real lines are available. Thresholds kept for future re-enable.
    # Prop models — re-optimized 2026-06-06 from this season's settled BET picks (flat ROI at real DK odds).
    # NOTE: in-sample tuning on small samples — forward ROI will regress; only high-volume models are trustworthy.
    "mlb_prop_batter_rbi":    {"min_prob": 0.90, "min_edge": 0.08},  # kept (2026-06-06: 42 bets +8.2% ROI)
    "mlb_prop_batter_runs":   {"min_prob": 0.65, "min_edge": 0.15},  # kept (2026-06-06: 26 bets +10.7% ROI)
    "mlb_prop_batter_hits":   {"min_prob": 0.78, "min_edge": 0.10},  # kept (2026-06-06: 50 bets +2.0% ROI)
    "mlb_prop_batter_tb":     {"min_prob": 0.88, "min_edge": 0.12},  # raised 85%→88% prob (2026-06-06): 24 bets +6.9% ROI (overall -8.8% over 59 at looser cuts)
    "mlb_prop_batter_walks":  {"min_prob": 0.95, "min_edge": 0.10},  # kept (2026-06-06: 12 bets -1.0%, least-bad/rare-fire; retrain)
    "mlb_prop_pitcher_outs":  {"min_prob": 0.60, "min_edge": 0.12},  # kept (2026-06-06: 15 bets +3.7% — only profitable pitcher prop)
    "mlb_prop_pitcher_k":     {"min_prob": 0.62, "min_edge": 0.08},  # kept (2026-06-06: 23 bets -1.5%, no profitable cut at any threshold — retrain)
    "mlb_prop_pitcher_er":    {"min_prob": 0.62, "min_edge": 0.08},  # kept (2026-06-06: 27 bets -6.3% flat across all cuts — retrain)
    "mlb_prop_pitcher_hits":  {"min_prob": 0.65, "min_edge": 0.12},  # kept (2026-06-06: -33% to -36%, no profitable cut — retrain)
    "mlb_prop_pitcher_walks": {"min_prob": 0.60, "min_edge": 0.12},  # kept (2026-06-06: -18% to -33%, no profitable cut — retrain)
    # Binary/rare-event models — prob scale differs from Poisson
    "mlb_prop_batter_hr":     {"min_prob": 0.20, "min_edge": 0.0},   # prob-only (see PROB_ONLY_MODELS); UNCHANGED — 22 bets -65.3%, no threshold fixes it (higher-prob HR picks lost more); flagged for pause/rework.
    "mlb_prop_batter_sb":     {"min_prob": 0.18, "min_edge": 0.10},  # kept (2026-06-06: 18 bets -15.3%, no profitable cut, AUC 0.528 — rebuild)
    # WNBA — placeholder thresholds; retune from the 2025 holdout backtest sweep.
    "wnba_moneyline":            {"min_prob": 0.66, "min_edge": 0.12},
    "wnba_over_under":           {"min_prob": 0.66, "min_edge": 0.12},
    "wnba_spread":               {"min_prob": 0.66, "min_edge": 0.12},
    "wnba_prop_player_points":   {"min_prob": 0.60, "min_edge": 0.08},
    "wnba_prop_player_rebounds": {"min_prob": 0.60, "min_edge": 0.08},
    "wnba_prop_player_assists":  {"min_prob": 0.60, "min_edge": 0.08},
    "wnba_prop_player_threes":   {"min_prob": 0.60, "min_edge": 0.08},
    "wnba_prop_player_pra":      {"min_prob": 0.60, "min_edge": 0.08},
    # NHL — placeholder thresholds; tune after 50+ settled picks. moneyline /
    # over_under / puckline score vs real DK lines. moneyline_regulation scores
    # vs DK's 3-way market — its per-side prob is lower (3 outcomes), hence the
    # 0.40 floor vs 0.55 for the binary markets.
    "nhl_moneyline":            {"min_prob": 0.55, "min_edge": 0.05},
    "nhl_moneyline_regulation": {"min_prob": 0.40, "min_edge": 0.05},
    "nhl_over_under":           {"min_prob": 0.55, "min_edge": 0.05},
    "nhl_puckline":             {"min_prob": 0.55, "min_edge": 0.05},
    # Live (in-play) — conservative placeholders; tune after 50+ settled live picks.
    "mlb_live_win_prob":   {"min_prob": 0.65, "min_edge": 0.10},
    "mlb_live_total_runs": {"min_prob": 0.65, "min_edge": 0.10},
    "mlb_live_runline":    {"min_prob": 0.65, "min_edge": 0.10},
    # NBA — placeholder thresholds; tune after 50+ settled picks. NBA mainlines
    # are the sharpest market we touch, so the game models run a higher edge gate
    # than props; double-double is prob-only (edge ignored, see PROB_ONLY_MODELS).
    "nba_moneyline":             {"min_prob": 0.66, "min_edge": 0.12},
    "nba_over_under":            {"min_prob": 0.66, "min_edge": 0.12},
    "nba_spread":                {"min_prob": 0.66, "min_edge": 0.12},
    "nba_prop_player_points":    {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_rebounds":  {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_assists":   {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_threes":    {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_pra":       {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_blocks":    {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_steals":    {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_turnovers": {"min_prob": 0.60, "min_edge": 0.08},
    "nba_prop_player_dd":        {"min_prob": 0.55, "min_edge": 0.0},   # prob-only
    # UFC — placeholder thresholds; tune after 50+ settled picks.
    # ufc_moneyline scores vs real DK h2h odds. ufc_total_rounds uses real DK
    # round-total lines when the per-event endpoint carries them, else prob-only
    # vs a synthetic line. ufc_method_of_victory is prob-only (no DK odds via
    # The Odds API) — see PROB_ONLY_MODELS.
    "ufc_moneyline":         {"min_prob": 0.65, "min_edge": 0.08},
    "ufc_total_rounds":      {"min_prob": 0.62, "min_edge": 0.08},
    "ufc_method_of_victory": {"min_prob": 0.65, "min_edge": 0.0},
    # GOLF — placeholder thresholds; tune after 50+ settled picks per model.
    # NOTE: golf probabilities live on a MARKET-relative scale, NOT the 0.6+ scale
    # of two-sided sports. A win prob is ~3–15%, a top-10 prob ~10–30%. The min_prob
    # floors below reflect that — do not "fix" them up to 0.6+.
    "golf_outright":  {"min_prob": 0.03, "min_edge": 0.015},
    "golf_top10":     {"min_prob": 0.15, "min_edge": 0.05},
    "golf_top20":     {"min_prob": 0.25, "min_edge": 0.05},
    "golf_make_cut":  {"min_prob": 0.65, "min_edge": 0.05},
    "golf_matchup":   {"min_prob": 0.55, "min_edge": 0.05},
}

# Models where BET signal is decided by model probability alone (edge ignored).
# Use when the market is structurally illiquid/inefficient so DK prices don't
# anchor a meaningful edge — e.g. HR Over 0.5 where DK juices the over heavily
# and there is no real under market. Scorer skips the edge check; dashboard /
# Claude mobile SQL filters drop the edge clause for these models.
PROB_ONLY_MODELS: set = {
    "mlb_prop_batter_hr",
    # Method-of-victory odds are not carried by The Odds API — the model's
    # 3-class probability alone decides the BET signal.
    "ufc_method_of_victory",
    # NBA double-double is a Yes/No market DK juices heavily (and there is no
    # real "No" market to fade) — decide on model probability alone.
    "nba_prop_player_dd",
}
# Models temporarily PAUSED — never emit a BET signal. They are still scored and
# written as NONE rows (so the website can still show the game), but with no
# recommended bet, no settlement, and zero bankroll risk. A paused model is also
# excluded from the mobile action filter and the public track-record views.
# Reversible: remove the model_id here (and clear its `paused` flag in the
# model_action_thresholds table) to re-enable.
PAUSED_MODELS: set = {
    # Batter HR: 29-137 / -66.6% flat ROI across every settled pick under current
    # criteria — the single largest drag on the portfolio, and tightening the
    # threshold makes it worse (higher-prob HR picks lost more). Shipping it to
    # users is the opposite of "help customers win money." Paused pending the v2
    # rework noted in CLAUDE.md §11. Re-enable once it beats break-even on paper.
    "mlb_prop_batter_hr",
}

# Fallback for models not listed above.
ACTION_MIN_PROB: float = float(os.environ.get("ACTION_MIN_PROB", 0.65))
ACTION_MIN_EDGE: float = float(os.environ.get("ACTION_MIN_EDGE", 0.14))
MAX_KELLY_FRACTION: float   = float(os.environ.get("MAX_KELLY_FRACTION",   0.05))
# Kelly multiplier: fraction of full Kelly to bet. Lowered from 0.25 → 0.10 (2026-05-04)
# because quarter-Kelly always exceeded the 5% cap (picks were all flat-bet at 5%).
# Tenth-Kelly keeps bets at 2-4% of bankroll, letting edge size drive differentiation.
KELLY_MULTIPLIER: float     = float(os.environ.get("KELLY_MULTIPLIER",      0.10))
# Edges above this magnitude are almost certainly model noise — filter them out
MAX_EDGE_CAP: float         = float(os.environ.get("MAX_EDGE_CAP",         0.20))

# Per-model BET edge thresholds (override the global default above).
# Derived from 2024 OOS backtest sweep: higher thresholds filter to higher-quality picks.
# Revisit after each retrain — edge distributions shift as features are added.
MODEL_EDGE_THRESHOLDS: dict = {
    "mlb_moneyline":            0.12,   # kept (2026-06-06 sweep: 19 bets +23.2% ROI at 72%/12%)
    "mlb_over_under":           0.12,   # lowered 0.15 → 0.12 (2026-06-06): 68%/12% gives 18 bets +22.2% ROI
    "mlb_runline":              0.10,   # lowered 0.12 → 0.10 (2026-06-06): 68%/10% is the only positive cut at volume (12 bets +1.1%); retrain pending
    "mlb_f5_moneyline":         0.07,   # lowered from 0.15 → 0.10 → 0.07 (2026-05-12) — real DK F5 lines are efficient; 7% is meaningful edge given v3 AUC=0.691
    "mlb_f5_over_under":        0.15,   # DISABLED — DK does not carry totals_1st_5_innings
    "mlb_f5_runline":           0.15,   # DISABLED — DK does not carry spreads_1st_5_innings
    "nhl_moneyline":            0.05,   # placeholder — tune after 50+ settled picks
    "nhl_moneyline_regulation": 0.05,
    "nhl_over_under":           0.05,
    "nhl_puckline":             0.05,
    # Prop models — re-optimized 2026-06-03 from settled-pick sweep (see ACTION_THRESHOLDS for per-model rationale)
    "mlb_prop_pitcher_k":        0.08,
    "mlb_prop_pitcher_hits":     0.12,  # raised 0.10→0.12
    "mlb_prop_pitcher_er":       0.08,
    "mlb_prop_pitcher_outs":     0.12,
    "mlb_prop_pitcher_walks":    0.12,  # raised 0.10→0.12
    "mlb_prop_batter_hits":      0.10,  # raised 0.08→0.10
    "mlb_prop_batter_tb":        0.12,  # kept 0.12 (2026-06-06: 88%/12% gives 24 bets +6.9% ROI)
    "mlb_prop_batter_hr":        0.05,  # v2: HR AUC 0.617; prob-only (edge ignored)
    "mlb_prop_batter_rbi":       0.08,
    "mlb_prop_batter_runs":      0.15,  # raised 0.08→0.15
    "mlb_prop_batter_sb":        0.10,  # raised 0.08→0.10
    "mlb_prop_batter_walks":     0.10,  # raised 0.08→0.10
    # WNBA — placeholder; retune from 2025 holdout backtest sweep.
    "wnba_moneyline":            0.12,
    "wnba_over_under":           0.12,
    "wnba_spread":               0.12,
    "wnba_prop_player_points":   0.08,
    "wnba_prop_player_rebounds": 0.08,
    "wnba_prop_player_assists":  0.08,
    "wnba_prop_player_threes":   0.08,
    "wnba_prop_player_pra":      0.08,
    # NBA — placeholder; tune after live odds accumulate.
    "nba_moneyline":             0.12,
    "nba_over_under":            0.12,
    "nba_spread":                0.12,
    "nba_prop_player_points":    0.08,
    "nba_prop_player_rebounds":  0.08,
    "nba_prop_player_assists":   0.08,
    "nba_prop_player_threes":    0.08,
    "nba_prop_player_pra":       0.08,
    "nba_prop_player_blocks":    0.08,
    "nba_prop_player_steals":    0.08,
    "nba_prop_player_turnovers": 0.08,
    "nba_prop_player_dd":        0.0,    # prob-only — edge ignored at runtime
    # UFC — placeholder; tune after 50+ settled picks.
    "ufc_moneyline":         0.08,
    "ufc_total_rounds":      0.08,
    "ufc_method_of_victory": 0.0,   # prob-only — edge ignored at runtime
    # GOLF — placeholder; tune after 50+ settled picks (market-relative scale).
    "golf_outright":  0.015,
    "golf_top10":     0.05,
    "golf_top20":     0.05,
    "golf_make_cut":  0.05,
    "golf_matchup":   0.05,
    # Live (in-play) — placeholder; in-play markets carry heavier vig, so the
    # edge floor starts higher than the pre-game equivalents.
    "mlb_live_win_prob":   0.10,
    "mlb_live_total_runs": 0.10,
    "mlb_live_runline":    0.10,
}

# Per-model minimum model probability to generate a BET signal.
# Moneyline markets run at a lower floor to surface more picks.
MODEL_PROB_THRESHOLDS: dict = {
    "mlb_moneyline":            0.72,   # kept (2026-06-06 sweep: 19 bets +23.2% ROI)
    "mlb_over_under":           0.68,   # LOWERED 0.72 → 0.68 (2026-06-06): 18 bets +22.2% ROI (more volume AND higher ROI than 0.72/0.15)
    "mlb_runline":              0.68,   # LOWERED 0.70 → 0.68 (2026-06-06): 12 bets +1.1% — only positive cut at volume; retrain pending
    "mlb_f5_moneyline":         0.68,   # raised 0.62 → 0.68 (2026-06-03): 41 bets +4.2% ROI (was -2.6% at 0.62)
    "mlb_f5_over_under":        0.65,   # DISABLED — DK does not carry these markets
    "mlb_f5_runline":           0.65,   # DISABLED — DK does not carry these markets
    "nhl_moneyline":            0.55,
    "nhl_moneyline_regulation": 0.40,   # 3-way market — lower per-side prob
    "nhl_over_under":           0.55,
    "nhl_puckline":             0.55,
    # Prop models — re-optimized 2026-06-03 from settled-pick sweep (see ACTION_THRESHOLDS for per-model rationale)
    "mlb_prop_pitcher_k":        0.62,  # kept; -5.1%, no better cut (retrain)
    "mlb_prop_pitcher_hits":     0.65,  # raised 0.60→0.65; less-bad, still red (retrain)
    "mlb_prop_pitcher_er":       0.62,  # kept; -6.3%, no better cut (retrain)
    "mlb_prop_pitcher_outs":     0.60,  # kept; +3.7%, only profitable pitcher prop
    "mlb_prop_pitcher_walks":    0.60,  # kept prob; edge raised to 0.12; still red (retrain)
    "mlb_prop_batter_hits":      0.78,  # raised 0.60→0.78: 50 bets +2.0% (was -13%)
    "mlb_prop_batter_tb":        0.88,  # raised 0.85→0.88 (2026-06-06): 24 bets +6.9% ROI
    "mlb_prop_batter_hr":        0.20,  # v2 prob-only; UNCHANGED — -65%, tightening worsens it; flagged for pause/rework
    "mlb_prop_batter_rbi":       0.90,  # raised 0.62→0.90: 42 bets +8.2% ROI
    "mlb_prop_batter_runs":      0.65,  # raised 0.62→0.65 (edge→0.15): 26 bets +10.7% ROI
    "mlb_prop_batter_sb":        0.18,  # kept prob; edge raised to 0.10; single-day data, unreliable
    "mlb_prop_batter_walks":     0.95,  # raised 0.62→0.95: least-bad, 12 bets -1.0% (rare-fire; retrain)
    # WNBA — placeholder; retune from 2025 holdout backtest sweep.
    "wnba_moneyline":            0.66,
    "wnba_over_under":           0.66,
    "wnba_spread":               0.66,
    "wnba_prop_player_points":   0.60,
    "wnba_prop_player_rebounds": 0.60,
    "wnba_prop_player_assists":  0.60,
    "wnba_prop_player_threes":   0.60,
    "wnba_prop_player_pra":      0.60,
    # NBA — placeholder; tune after live odds accumulate.
    "nba_moneyline":             0.66,
    "nba_over_under":            0.66,
    "nba_spread":                0.66,
    "nba_prop_player_points":    0.60,
    "nba_prop_player_rebounds":  0.60,
    "nba_prop_player_assists":   0.60,
    "nba_prop_player_threes":    0.60,
    "nba_prop_player_pra":       0.60,
    "nba_prop_player_blocks":    0.60,
    "nba_prop_player_steals":    0.60,
    "nba_prop_player_turnovers": 0.60,
    "nba_prop_player_dd":        0.55,   # prob-only — P(double-double) for stars ~0.4-0.7
    # UFC — placeholder; tune after 50+ settled picks.
    "ufc_moneyline":         0.65,
    "ufc_total_rounds":      0.62,
    "ufc_method_of_victory": 0.65,
    # GOLF — placeholder; tune after 50+ settled picks (market-relative scale).
    "golf_outright":  0.03,
    "golf_top10":     0.15,
    "golf_top20":     0.25,
    "golf_make_cut":  0.65,
    "golf_matchup":   0.55,
    # Live (in-play) — placeholder; tune after 50+ settled live picks.
    "mlb_live_win_prob":   0.65,
    "mlb_live_total_runs": 0.65,
    "mlb_live_runline":    0.65,
}

# ── Live (In-Play) Betting ────────────────────────────────────────────────────
# Phase 1: game-state poller polls MLB live feed for each in-progress game on
# this cadence. Free API — no Odds API credits consumed.
LIVE_POLL_INTERVAL_SEC: int  = int(os.environ.get("LIVE_POLL_INTERVAL_SEC", 15))
# Window in which we treat a game as "live": 15 min before scheduled first pitch
# (warmup updates can move lines) through final out.
LIVE_PREGAME_BUFFER_MIN: int = int(os.environ.get("LIVE_PREGAME_BUFFER_MIN", 15))
# Trigger orchestrator debounce — never more than one FG odds fetch per game
# inside this window (3-run innings still produce only one line-move opportunity).
LIVE_FG_DEBOUNCE_SEC: int    = int(os.environ.get("LIVE_FG_DEBOUNCE_SEC", 60))
# Hard kill switch — orchestrator stops dispatching Odds API calls if today's
# burn would exceed this (Phase 3+). 0 = no cap. Set per tier.
LIVE_DAILY_CREDIT_CAP: int   = int(os.environ.get("LIVE_DAILY_CREDIT_CAP", 0))
# In-play odds older than this are stale — the live scorer skips rather than
# score against a line the book has since moved.
LIVE_ODDS_MAX_AGE_SEC: int   = int(os.environ.get("LIVE_ODDS_MAX_AGE_SEC", 300))
# Live game-state snapshots older than this mean the poller has stopped —
# don't score from a frozen state.
LIVE_STATE_MAX_AGE_SEC: int  = int(os.environ.get("LIVE_STATE_MAX_AGE_SEC", 300))

# Live (in-play) model registry — kept SEPARATE from MODELS so the pre-game
# scorer/trainer/backtester never pick these up. Each entry:
# model_id → (sport, market, model_type, description).
#   binary  → XGBClassifier + Platt; predict_proba[1] = P(outcome)
#   poisson → XGBRegressor count:poisson; predict = expected count REMAINING
LIVE_MODELS = {
    "mlb_live_win_prob":   ("MLB", "h2h",     "binary",
                            "P(home wins) from in-game state + pre-game context"),
    "mlb_live_total_runs": ("MLB", "totals",  "poisson",
                            "Expected runs in the REMAINDER of the game"),
    "mlb_live_runline":    ("MLB", "spreads", "binary",
                            "P(home wins by 2+) — only scored vs a live -1.5 line"),
}

# ── F5 (First 5 Innings) ──────────────────────────────────────────────────────
# Synthetic F5 total line = full_game_total * F5_TOTAL_FACTOR.
# Calibrated 2026-05-08 from 26,443 historical games:
#   avg F5 total = 5.344 runs / avg FG total = 8.623 → factor = 0.6197
# Overridable via env var if recalibration is needed after more data accumulates.
F5_TOTAL_FACTOR: float = float(os.environ.get("F5_TOTAL_FACTOR", 0.62))

# ── Early Season ──────────────────────────────────────────────────────────────
MIN_GAMES_BASELINE: int = int(os.environ.get("MIN_GAMES_BASELINE", 10))

# ── Return-from-Injury Ramp ───────────────────────────────────────────────────
RETURN_RAMP = {
    "early": float(os.environ.get("RETURN_RAMP_EARLY", 0.70)),  # games 1-2
    "mid":   float(os.environ.get("RETURN_RAMP_MID",   0.85)),  # games 3-5
    "full":  float(os.environ.get("RETURN_RAMP_FULL",  1.00)),  # games 6+
}

# ── Scheduling ────────────────────────────────────────────────────────────────
PIPELINE_RUN_TIME: str = os.environ.get("PIPELINE_RUN_TIME", "07:00")

# ── Sport Configuration ───────────────────────────────────────────────────────
SPORTS = {
    "MLB": {
        "odds_api_key":  "baseball_mlb",
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2025)),  # 2019–2024 train (bumped 2026-06-06 — pre-clock 2019-23 window was stale; see docs/retrain_2026_plan.md)
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/mlb",
    },
    "NHL": {
        "odds_api_key":  "icehockey_nhl",
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2025)),  # 2019–2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/nhl",
    },
    "WNBA": {
        "odds_api_key":  "basketball_wnba",
        # Season label = year of play (like MLB). WNBA runs May–Sept.
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2025)),  # 2019–2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/wnba",
    },
    "NBA": {
        "odds_api_key":  "basketball_nba",
        # Season label = ENDING year (like NHL): season 2025 = the 2024-25 season,
        # which spans Oct 2024 – Jun 2025. The stats ingestor converts our int
        # season → the nba_api "YYYY-YY" string. Backfill team-stat snapshots are
        # stamped {season-1}-09-01 (before any Oct game) so the ASOF feature
        # lookup always finds an in-season row.
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2025)),  # 2019–2024 train (=2018-19 .. 2023-24)
        "test_season":   2025,                      # 2025 (=2024-25) held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/nba",
    },
    "UFC": {
        "odds_api_key":  "mma_mixed_martial_arts",
        # Season label = calendar year of the event. Fight history scraped from
        # ufcstats.com back to 2010 so career rolling stats have depth; models
        # train on 2012+ (fighters need ≥3 prior UFC fights to produce a row).
        "seasons":       list(range(2010, 2027)),
        "train_seasons": list(range(2012, 2025)),  # 2012–2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/ufc",
    },
    "GOLF": {
        # odds_api_key is None on purpose — golf odds + stats come from DataGolf,
        # not The Odds API. The odds_ingestor's default sport list never includes
        # GOLF, so this key is never read for golf; it exists only to satisfy the
        # SPORTS schema (test_config.py requires the key to be present).
        "odds_api_key":  None,
        # Season label = calendar year. DataGolf round-level history + strokes
        # gained go back to ~2017; models train on 2017–2024, hold out 2025.
        "seasons":       list(range(2017, 2027)),
        "train_seasons": list(range(2017, 2025)),  # 2017–2024 train
        "test_season":   2025,                      # 2025 held out
        "sbr_dir":       ROOT / "data/raw/datawarehouse/golf",
    },
}

# ── Models Registry ───────────────────────────────────────────────────────────
# Each entry: model_id → (sport, market, description)
MODELS = {
    "mlb_moneyline":            ("MLB", "h2h",      "Home team wins (full game)"),
    "mlb_over_under":           ("MLB", "totals",   "Total runs over/under"),
    "mlb_runline":              ("MLB", "spreads",  "Favored team covers -1.5 run line"),
    "mlb_f5_moneyline":         ("MLB", "h2h_1st_5_innings",      "Home leads after 5 innings"),
    "mlb_f5_over_under":        ("MLB", "totals_1st_5_innings",   "Total runs over/under through 5 innings"),
    "mlb_f5_runline":           ("MLB", "spreads_1st_5_innings",  "Home covers F5 spread"),
    "nhl_moneyline":            ("NHL", "h2h",      "Home team wins incl. OT/SO"),
    "nhl_moneyline_regulation": ("NHL", "h2h_3way", "Regulation result: Home / Draw / Away"),
    "nhl_over_under":           ("NHL", "totals",   "Total goals over/under"),
    "nhl_puckline":             ("NHL", "spreads",  "Favored team covers -1.5 puck line"),
    "wnba_moneyline":           ("WNBA", "h2h",     "Home team wins"),
    "wnba_over_under":          ("WNBA", "totals",  "Total points over/under"),
    "wnba_spread":              ("WNBA", "spreads", "Home team covers the spread"),
    "nba_moneyline":            ("NBA",  "h2h",     "Home team wins"),
    "nba_over_under":           ("NBA",  "totals",  "Total points over/under"),
    "nba_spread":               ("NBA",  "spreads", "Home team covers the spread"),
    # UFC — fighter mapped to the Odds API "home_team" slot is our home side.
    "ufc_moneyline":            ("UFC", "h2h",    "Home-slot fighter wins the fight"),
    "ufc_total_rounds":         ("UFC", "totals", "Fight duration over/under the round line"),
    "ufc_method_of_victory":    ("UFC", "method", "Fight ends by Decision / KO-TKO / Submission (3-class)"),
    # GOLF — per-player markets on one tournament games row (picks carry player_id).
    # All four markets price against real DK odds via DataGolf's betting-tools feed.
    "golf_outright":            ("GOLF", "win",                "Player wins the tournament"),
    "golf_top10":               ("GOLF", "top_10",             "Player finishes in the top 10"),
    "golf_top20":               ("GOLF", "top_20",             "Player finishes in the top 20"),
    "golf_make_cut":            ("GOLF", "make_cut",           "Player makes the cut"),
    "golf_matchup":             ("GOLF", "matchup_tournament", "Player A beats Player B over the tournament"),
}

# ── The Odds API ──────────────────────────────────────────────────────────────
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_API_REGIONS = "us"
ODDS_API_BOOKMAKER = "draftkings"

# ── Action Network (Public Betting Splits) ────────────────────────────────────
# Unofficial JSON scoreboard endpoint — the same data that powers
# actionnetwork.com/mlb/public-betting. No API key required. The ingestor is
# best-effort: any failure is logged and the pipeline continues (same resilient
# pattern as the ESPN hidden API and the F5 odds fetch). Override via env if the
# endpoint or book ids change.
ACTION_NETWORK_BASE: str = os.environ.get(
    "ACTION_NETWORK_BASE",
    "https://api.actionnetwork.com/web/v2/scoreboard",
)
# Book id(s) whose bet/money splits represent "the public". 15 is Action
# Network's consensus pseudo-book. Comma-separated — the first book that carries
# split data for a game wins.
ACTION_NETWORK_BOOK_IDS: str = os.environ.get("ACTION_NETWORK_BOOK_IDS", "15")

# ── ESPN Injury API ───────────────────────────────────────────────────────────
ESPN_INJURY_URLS = {
    "MLB": "https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb/teams/{team_id}/injuries",
    "NHL": "https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/teams/{team_id}/injuries",
    "WNBA": "https://sports.core.api.espn.com/v2/sports/basketball/leagues/wnba/teams/{team_id}/injuries",
    "NBA": "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams/{team_id}/injuries",
}

# ESPN team ID maps — ESPN uses numeric IDs
ESPN_MLB_TEAM_IDS = {
    "ARI": 29, "ATL": 15, "BAL": 1,  "BOS": 2,  "CHC": 16, "CWS": 4,
    "CIN": 17, "CLE": 5,  "COL": 27, "DET": 6,  "HOU": 18, "KC":  7,
    "LAA": 3,  "LAD": 19, "MIA": 28, "MIL": 21, "MIN": 9,  "NYM": 21,
    "NYY": 10, "OAK": 11, "PHI": 22, "PIT": 23, "SD":  25, "SEA": 12,
    "SF":  26, "STL": 24, "TB":  30, "TEX": 13, "TOR": 14, "WSH": 20,
}

# NOTE: these ESPN NHL ids are unverified and have known duplicates — verify
# on a machine with ESPN access before relying on NHL injury resolution.
# `UTA` is the canonical relocated-franchise id (Arizona → Utah), matching the
# UTA convention used in the ingestor/odds/SBR maps. injury_adj degrades to
# neutral when a team id is wrong/missing, so a stale id is non-fatal.
ESPN_NHL_TEAM_IDS = {
    "ANA": 25, "UTA": 53, "BOS": 1,  "BUF": 2,  "CAR": 26, "CBJ": 29,
    "CGY": 20, "CHI": 16, "COL": 21, "DAL": 25, "DET": 17, "EDM": 22,
    "FLA": 13, "LAK": 26, "MIN": 30, "MTL": 8,  "NJD": 1,  "NSH": 18,
    "NYI": 2,  "NYR": 3,  "OTT": 9,  "PHI": 4,  "PIT": 5,  "SEA": 55,
    "SJS": 28, "STL": 19, "TBL": 14, "TOR": 10, "VAN": 23, "VGK": 54,
    "WSH": 15, "WPG": 52,
}

# WNBA canonical 3-letter abbreviations (used by odds + stats ingestors and the
# ESPN map below). 15 franchises as of 2026 (Portland Fire + Toronto Tempo expansion).
WNBA_TEAMS = [
    "ATL", "CHI", "CON", "DAL", "GSV", "IND", "LV",
    "LA", "MIN", "NY", "PDX", "PHX", "SEA", "TOR", "WAS",
]

# The Odds API returns full team names; normalise to WNBA_TEAMS abbrevs.
WNBA_ODDS_API_MAP = {
    "Atlanta Dream":          "ATL",
    "Chicago Sky":            "CHI",
    "Connecticut Sun":        "CON",
    "Dallas Wings":           "DAL",
    "Golden State Valkyries": "GSV",
    "Indiana Fever":          "IND",
    "Las Vegas Aces":         "LV",
    "Los Angeles Sparks":     "LA",
    "Minnesota Lynx":         "MIN",
    "New York Liberty":       "NY",
    "Portland Fire":          "PDX",
    "Phoenix Mercury":        "PHX",
    "Seattle Storm":          "SEA",
    "Toronto Tempo":          "TOR",
    "Washington Mystics":     "WAS",
}

# ESPN numeric team IDs for WNBA injuries — OFFLINE FALLBACK ONLY.
# The injury ingestor resolves ids LIVE from ESPN's WNBA teams endpoint at runtime
# (_fetch_wnba_espn_team_ids), joining on full team name via WNBA_ODDS_API_MAP, so
# all 15 franchises — including the 2025/2026 expansion teams (Golden State
# Valkyries, Portland Fire, Toronto Tempo) — resolve automatically with no
# hardcoded numeric ids. This static map is used only when that endpoint is
# unreachable (e.g. the sandbox allowlist blocks ESPN).
#
# These 12 long-established franchises use ESPN's standard WNBA team ids (ATL=20,
# LV=17, NY=9 independently verified; the rest are the stable ESPN ids for these
# clubs). GSV/PDX/TOR are intentionally omitted here — they're filled by the live
# resolver. The injuries endpoint is league-scoped (.../leagues/wnba/teams/{id}/
# injuries), so any unknown id just 404s and unmapped teams are skipped — both
# degrade gracefully (no wrong-team data is ever fetched).
ESPN_WNBA_TEAM_IDS = {
    "ATL": 20,   # Atlanta Dream
    "CHI": 19,   # Chicago Sky
    "CON": 18,   # Connecticut Sun
    "DAL": 3,    # Dallas Wings
    "IND": 5,    # Indiana Fever
    "LV":  17,   # Las Vegas Aces
    "LA":  6,    # Los Angeles Sparks
    "MIN": 8,    # Minnesota Lynx
    "NY":  9,    # New York Liberty
    "PHX": 11,   # Phoenix Mercury
    "SEA": 14,   # Seattle Storm
    "WAS": 16,   # Washington Mystics
}

# NBA canonical 3-letter abbreviations (used by odds + stats ingestors and the
# ESPN map below). 30 franchises. These match the stats.nba.com / ESPN scheme.
NBA_TEAMS = [
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
]

# The Odds API returns full team names; normalise to NBA_TEAMS abbrevs.
# (Note: The Odds API lists the Clippers as "LA Clippers", Lakers as
# "Los Angeles Lakers".)
NBA_ODDS_API_MAP = {
    "Atlanta Hawks":          "ATL",
    "Boston Celtics":         "BOS",
    "Brooklyn Nets":          "BKN",
    "Charlotte Hornets":      "CHA",
    "Chicago Bulls":          "CHI",
    "Cleveland Cavaliers":    "CLE",
    "Dallas Mavericks":       "DAL",
    "Denver Nuggets":         "DEN",
    "Detroit Pistons":        "DET",
    "Golden State Warriors":  "GSW",
    "Houston Rockets":        "HOU",
    "Indiana Pacers":         "IND",
    "LA Clippers":            "LAC",
    "Los Angeles Clippers":   "LAC",
    "Los Angeles Lakers":     "LAL",
    "Memphis Grizzlies":      "MEM",
    "Miami Heat":             "MIA",
    "Milwaukee Bucks":        "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans":   "NOP",
    "New York Knicks":        "NYK",
    "Oklahoma City Thunder":  "OKC",
    "Orlando Magic":          "ORL",
    "Philadelphia 76ers":     "PHI",
    "Phoenix Suns":           "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings":       "SAC",
    "San Antonio Spurs":      "SAS",
    "Toronto Raptors":        "TOR",
    "Utah Jazz":              "UTA",
    "Washington Wizards":     "WAS",
}

# ESPN numeric team IDs for NBA injuries. Unlike the WNBA list (which has
# expansion-team churn and is resolved live), the 30 NBA franchises are stable,
# so this static map is the primary source; the injury ingestor still overlays
# any ids it can resolve live from ESPN's NBA teams endpoint as a self-heal.
ESPN_NBA_TEAM_IDS = {
    "ATL": 1,  "BOS": 2,  "BKN": 17, "CHA": 30, "CHI": 4,  "CLE": 5,
    "DAL": 6,  "DEN": 7,  "DET": 8,  "GSW": 9,  "HOU": 10, "IND": 11,
    "LAC": 12, "LAL": 13, "MEM": 29, "MIA": 14, "MIL": 15, "MIN": 16,
    "NOP": 3,  "NYK": 18, "OKC": 25, "ORL": 19, "PHI": 20, "PHX": 21,
    "POR": 22, "SAC": 23, "SAS": 24, "TOR": 28, "UTA": 26, "WAS": 27,
}

# ── Player Props ─────────────────────────────────────────────────────────────
# All DK prop markets available via The Odds API event-level endpoint.
# Pitcher props use Poisson regression (count projection).
# Batter SB uses logistic (binary — rare event). HR switched to Poisson (v2).
PROP_MARKETS_PITCHER = [
    "pitcher_strikeouts",
    "pitcher_hits_allowed",
    "pitcher_earned_runs",
    "pitcher_outs",
    "pitcher_walks",
]
PROP_MARKETS_BATTER = [
    "batter_hits",
    "batter_total_bases",
    "batter_home_runs",      # poisson (v2 — pitcher HR/9, gb%, park factor, platoon)
    "batter_rbis",
    "batter_runs_scored",
    "batter_stolen_bases",   # logistic (binary)
    "batter_walks",
]
PROP_MARKETS_ALL = PROP_MARKETS_PITCHER + PROP_MARKETS_BATTER

# WNBA player prop markets (The Odds API basketball player-prop keys).
# All modelled as Poisson count projections.
PROP_MARKETS_WNBA = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",   # PRA combo
]

# NBA player prop markets (The Odds API basketball player-prop keys).
# Counts are Poisson; player_double_double is a binary Yes/No market.
PROP_MARKETS_NBA = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",   # PRA combo
    "player_blocks",
    "player_steals",
    "player_turnovers",
    "player_double_double",             # binary Yes/No (logistic, prob-only)
]

# Prop model IDs — one per market. Trained in Phase 2 after game-log backfill.
PROP_MODELS = {
    "mlb_prop_pitcher_k":    ("MLB", "pitcher_strikeouts",  "poisson",  "Priority 1"),
    "mlb_prop_pitcher_hits": ("MLB", "pitcher_hits_allowed","poisson",  ""),
    "mlb_prop_pitcher_er":   ("MLB", "pitcher_earned_runs", "poisson",  ""),
    "mlb_prop_pitcher_outs": ("MLB", "pitcher_outs",        "poisson",  ""),
    "mlb_prop_pitcher_walks":("MLB", "pitcher_walks",       "poisson",  ""),
    "mlb_prop_batter_hits":  ("MLB", "batter_hits",         "poisson",  ""),
    "mlb_prop_batter_tb":    ("MLB", "batter_total_bases",  "poisson",  ""),
    "mlb_prop_batter_hr":    ("MLB", "batter_home_runs",    "poisson",  "v2: pitcher HR/9, gb%, park factor, platoon"),
    "mlb_prop_batter_rbi":   ("MLB", "batter_rbis",         "poisson",  ""),
    "mlb_prop_batter_runs":  ("MLB", "batter_runs_scored",  "poisson",  ""),
    "mlb_prop_batter_sb":    ("MLB", "batter_stolen_bases", "logistic", "rare event"),
    "mlb_prop_batter_walks": ("MLB", "batter_walks",        "poisson",  ""),
    # WNBA player props — Poisson count projection (one model per market).
    "wnba_prop_player_points":   ("WNBA", "player_points",                   "poisson", ""),
    "wnba_prop_player_rebounds": ("WNBA", "player_rebounds",                 "poisson", ""),
    "wnba_prop_player_assists":  ("WNBA", "player_assists",                  "poisson", ""),
    "wnba_prop_player_threes":   ("WNBA", "player_threes",                   "poisson", ""),
    "wnba_prop_player_pra":      ("WNBA", "player_points_rebounds_assists",  "poisson", "P+R+A combo"),
    # NBA player props — 5 WNBA-equivalents (Poisson) + 4 NBA-specific markets.
    # Double-double is a binary Yes/No outcome (DK juices it heavily) → logistic +
    # prob-only, same treatment as the MLB HR prop. The rest are Poisson counts.
    "nba_prop_player_points":    ("NBA", "player_points",                   "poisson",  ""),
    "nba_prop_player_rebounds":  ("NBA", "player_rebounds",                 "poisson",  ""),
    "nba_prop_player_assists":   ("NBA", "player_assists",                  "poisson",  ""),
    "nba_prop_player_threes":    ("NBA", "player_threes",                   "poisson",  ""),
    "nba_prop_player_pra":       ("NBA", "player_points_rebounds_assists",  "poisson",  "P+R+A combo"),
    "nba_prop_player_blocks":    ("NBA", "player_blocks",                   "poisson",  ""),
    "nba_prop_player_steals":    ("NBA", "player_steals",                   "poisson",  ""),
    "nba_prop_player_turnovers": ("NBA", "player_turnovers",                "poisson",  ""),
    "nba_prop_player_dd":        ("NBA", "player_double_double",            "logistic", "double-double (binary, prob-only)"),
}

# Baseball Savant leaderboard CSV base URL
SAVANT_BASE_URL = "https://baseballsavant.mlb.com/leaderboard/custom"

# ── UFC ───────────────────────────────────────────────────────────────────────
# ufcstats.com is the historical + weekly results source (no official free API).
# Static site, no auth. The ingestor is polite (300ms between requests) and all
# parsers are isolated + fixture-tested so markup changes are a localized fix.
# NOTE (2026-06-11): ufcstats.com moved behind a browser-level Cloudflare
# challenge that even cloudscraper can't solve, so the PRIMARY data path is now
# the ufc_csv_loader (below). The HTML scraper is kept as a documented plan B.
UFCSTATS_BASE_URL: str = os.environ.get("UFCSTATS_BASE_URL", "http://ufcstats.com")

# Primary UFC data source: the Greco1899/scrape_ufc_stats GitHub mirror — a
# maintained repo whose own scheduled scraper keeps 1:1 CSV exports of
# ufcstats.com current (updated weekly after each card). The CSVs preserve the
# ufcstats fight/fighter ids in their URL columns, so rows are identical to
# what the HTML scraper would have produced. UFC_CSV_DIR (optional) points at a
# local directory of the same CSVs for offline/manual use.
UFC_CSV_BASE_URL: str = os.environ.get(
    "UFC_CSV_BASE_URL",
    "https://raw.githubusercontent.com/Greco1899/scrape_ufc_stats/main")
UFC_CSV_DIR: str = os.environ.get("UFC_CSV_DIR", "")

# The Odds API fighter name → ufcstats.com fighter name overrides.
# Fighter identity is matched by slugified full name (lowercase, accents
# stripped, punctuation removed), which handles almost everyone. Add an entry
# here when the books and ufcstats disagree on a name (nicknames, "Jr.",
# transliteration differences). Keys are Odds API names, values ufcstats names.
UFC_NAME_ALIASES: dict = {
    # "Alexander Volkanovski": "Alex Volkanovski",   # (example — not real)
}

# Synthetic round-total lines used when DK round-total odds are absent
# (training, backtest, and prob-only live scoring). The most common DK lines:
# 2.5 rounds for 3-round bouts, 4.5 for 5-round bouts.
UFC_SYNTHETIC_TOTAL_3RD: float = 2.5
UFC_SYNTHETIC_TOTAL_5RD: float = 4.5

# UFC events are weekly, and DK prices fights days in advance — score fights up
# to this many days ahead so picks are visible before fight day (MLB/WNBA stay
# same-day only). Each scoring run re-deletes and re-scores unstarted UFC picks
# in this window, so signal flips are handled the same way as same-day picks.
UFC_SCORE_AHEAD_DAYS: int = int(os.environ.get("UFC_SCORE_AHEAD_DAYS", "7"))

# ── GOLF / DataGolf ───────────────────────────────────────────────────────────
# Golf data + odds come from the DataGolf "Scratch Plus" API (feeds.datagolf.com).
# A single API key unlocks: historical round-level scoring + strokes gained
# (/historical-raw-data/*), the current field (/field-updates), player ids
# (/get-player-list), skill rankings (/preds/get-dg-rankings) and — crucially —
# LIVE DraftKings odds for every weekly PGA event across all four markets via
# the betting-tools feed (/betting-tools/outrights, /betting-tools/matchups).
# The Odds API is NOT used for golf (it only carries the 4 majors, outrights only).
DATAGOLF_API_KEY: str  = os.environ.get("DATAGOLF_API_KEY", "")
DATAGOLF_BASE_URL: str = os.environ.get("DATAGOLF_BASE_URL", "https://feeds.datagolf.com")

# A player must have at least this many measured rounds of history before the
# feature engine will produce a row (the MIN_UFC_FIGHTS / early-season analog —
# rolling strokes-gained is unstable below ~5 events / 20 rounds).
MIN_GOLF_ROUNDS: int = int(os.environ.get("MIN_GOLF_ROUNDS", "20"))

# Tournaments are weekly and DK prices the field days in advance — score picks
# up to this many days before the first round (same look-ahead pattern as UFC).
# Each scoring run re-deletes and re-scores picks for tournaments that have not
# yet teed off, so signal flips are handled like same-day picks.
GOLF_SCORE_AHEAD_DAYS: int = int(os.environ.get("GOLF_SCORE_AHEAD_DAYS", "7"))

# Number of historical player pairs sampled per event to build the matchup
# training set (deterministic — seeded by dg_event_id+season). Kept modest so a
# few dominant pairs can't swamp the binary target.
GOLF_MATCHUP_PAIRS_PER_EVENT: int = int(os.environ.get("GOLF_MATCHUP_PAIRS_PER_EVENT", "15"))

# Team events (alternate-shot / four-ball formats — e.g. the Zurich Classic) have
# no individual finishing positions and must be excluded from ingestion + scoring.
# Matched by DataGolf event name (case-insensitive substring).
GOLF_TEAM_EVENT_MARKERS = ("zurich classic",)

# ── Directories ───────────────────────────────────────────────────────────────
MODELS_DIR    = ROOT / "models" / "saved"
NOTEBOOKS_DIR = ROOT / "notebooks"
RAW_DATA_DIR  = ROOT / "data" / "raw"

# Ensure critical directories exist at import time
for _d in [
    MODELS_DIR,
    RAW_DATA_DIR / "datawarehouse/mlb",
    RAW_DATA_DIR / "datawarehouse/nhl",
    RAW_DATA_DIR / "datawarehouse/wnba",
    RAW_DATA_DIR / "datawarehouse/nba",
    RAW_DATA_DIR / "datawarehouse/ufc",
    RAW_DATA_DIR / "datawarehouse/golf",
]:
    _d.mkdir(parents=True, exist_ok=True)

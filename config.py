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
    "mlb_moneyline":      {"min_prob": 0.72, "min_edge": 0.12},  # raised from 62%/10% → 72%/12% (2026-05-15): live data sweep, 13 bets +28.8% ROI
    "mlb_over_under":     {"min_prob": 0.67, "min_edge": 0.15},  # raised from 65%/14% → 67%/15% (2026-05-15): live data sweep, 14 bets +65.3% ROI
    "mlb_runline":        {"min_prob": 0.70, "min_edge": 0.12},  # raised from 65%/10% → 70%/12% (2026-05-15): live data sweep, 7 bets +25.5% ROI
    "mlb_f5_moneyline":   {"min_prob": 0.62, "min_edge": 0.07},  # real DK odds only (h2h_1st_5_innings, fetched 11am) — lowered from 65%/15% → 62%/7% (2026-05-12): DK F5 market is efficient, 7% is meaningful edge with v3 AUC=0.691
    # mlb_f5_over_under and mlb_f5_runline: DISABLED — DK does not carry these markets.
    # Scorer skips them until real lines are available. Thresholds kept for future re-enable.
    # Prop models — tightened 2026-05-15 based on holdout O/U accuracy + CalError review
    # Tier A (≥62% O/U acc): 62%/8%
    "mlb_prop_pitcher_k":     {"min_prob": 0.62, "min_edge": 0.08},  # 64.1% O/U acc
    "mlb_prop_pitcher_er":    {"min_prob": 0.62, "min_edge": 0.08},  # 62.3% O/U acc
    "mlb_prop_batter_rbi":    {"min_prob": 0.62, "min_edge": 0.08},  # 71.2% O/U acc
    "mlb_prop_batter_runs":   {"min_prob": 0.62, "min_edge": 0.08},  # 62.9% O/U acc
    "mlb_prop_batter_walks":  {"min_prob": 0.62, "min_edge": 0.08},  # 72.8% O/U acc
    # Tier B (59-62%, well-calibrated CalError <5%): 60%/8%
    "mlb_prop_batter_hits":   {"min_prob": 0.60, "min_edge": 0.08},  # 59.8% O/U acc, CalErr 1.2%
    "mlb_prop_batter_tb":     {"min_prob": 0.60, "min_edge": 0.08},  # 59.6% O/U acc, CalErr 4.1%
    # Tier C (58-62%, elevated CalError 9-10%): 60%/10%
    "mlb_prop_pitcher_hits":  {"min_prob": 0.60, "min_edge": 0.10},  # 58.7% O/U acc, CalErr 9.0%
    "mlb_prop_pitcher_walks": {"min_prob": 0.60, "min_edge": 0.10},  # 57.6% O/U acc, CalErr 9.3%
    # Tier D (worst CalError 14.3%): 60%/12% — probs least trustworthy
    "mlb_prop_pitcher_outs":  {"min_prob": 0.60, "min_edge": 0.12},  # 58.4% O/U acc, CalErr 14.3%
    # Binary/rare-event models — prob scale differs from Poisson
    "mlb_prop_batter_hr":     {"min_prob": 0.20, "min_edge": 0.0},   # prob-only (see PROB_ONLY_MODELS) — DK juices HR overs so edge is often negative; surface picks on model % alone
    "mlb_prop_batter_sb":     {"min_prob": 0.18, "min_edge": 0.08},  # AUC 0.528 (marginal); P(SB) range 3-25%
}

# Models where BET signal is decided by model probability alone (edge ignored).
# Use when the market is structurally illiquid/inefficient so DK prices don't
# anchor a meaningful edge — e.g. HR Over 0.5 where DK juices the over heavily
# and there is no real under market. Scorer skips the edge check; dashboard /
# Claude mobile SQL filters drop the edge clause for these models.
PROB_ONLY_MODELS: set = {
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
    "mlb_moneyline":            0.12,   # raised from 0.10 → 0.12 (2026-05-15): live data sweep, 13 bets +28.8% ROI at 72%/12%
    "mlb_over_under":           0.15,   # raised from 0.14 → 0.15 (2026-05-15): live data sweep, 14 bets +65.3% ROI at 67%/15%
    "mlb_runline":              0.12,   # raised from 0.10 → 0.12 (2026-05-15): live data sweep, 7 bets +25.5% ROI at 70%/12%
    "mlb_f5_moneyline":         0.07,   # lowered from 0.15 → 0.10 → 0.07 (2026-05-12) — real DK F5 lines are efficient; 7% is meaningful edge given v3 AUC=0.691
    "mlb_f5_over_under":        0.15,   # DISABLED — DK does not carry totals_1st_5_innings
    "mlb_f5_runline":           0.15,   # DISABLED — DK does not carry spreads_1st_5_innings
    "nhl_moneyline":            0.10,   # placeholder — NHL not yet trained
    "nhl_moneyline_regulation": 0.10,
    "nhl_over_under":           0.10,
    "nhl_puckline":             0.10,
    # Prop models — tightened 2026-05-15 (see ACTION_THRESHOLDS for tier rationale)
    "mlb_prop_pitcher_k":        0.08,
    "mlb_prop_pitcher_hits":     0.10,
    "mlb_prop_pitcher_er":       0.08,
    "mlb_prop_pitcher_outs":     0.12,
    "mlb_prop_pitcher_walks":    0.10,
    "mlb_prop_batter_hits":      0.08,
    "mlb_prop_batter_tb":        0.08,
    "mlb_prop_batter_hr":        0.05,  # v2: HR AUC 0.617; unchanged
    "mlb_prop_batter_rbi":       0.08,
    "mlb_prop_batter_runs":      0.08,
    "mlb_prop_batter_sb":        0.08,
    "mlb_prop_batter_walks":     0.08,
}

# Per-model minimum model probability to generate a BET signal.
# Moneyline markets run at a lower floor to surface more picks.
MODEL_PROB_THRESHOLDS: dict = {
    "mlb_moneyline":            0.72,   # raised from 0.62 → 0.72 (2026-05-15): live data sweep, 13 bets +28.8% ROI at 72%/12%
    "mlb_over_under":           0.67,   # raised from 0.65 → 0.67 (2026-05-15): live data sweep, 14 bets +65.3% ROI at 67%/15%
    "mlb_runline":              0.70,   # raised from 0.65 → 0.70 (2026-05-15): live data sweep, 7 bets +25.5% ROI at 70%/12%
    "mlb_f5_moneyline":         0.62,   # lowered from 0.65 (2026-05-12) — matches full-game ML floor; real DK odds only
    "mlb_f5_over_under":        0.65,   # DISABLED — DK does not carry these markets
    "mlb_f5_runline":           0.65,   # DISABLED — DK does not carry these markets
    "nhl_moneyline":            0.58,
    "nhl_moneyline_regulation": 0.58,
    "nhl_over_under":           0.65,
    "nhl_puckline":             0.58,
    # Prop models — tightened 2026-05-15 (see ACTION_THRESHOLDS for tier rationale)
    "mlb_prop_pitcher_k":        0.62,
    "mlb_prop_pitcher_hits":     0.60,
    "mlb_prop_pitcher_er":       0.62,
    "mlb_prop_pitcher_outs":     0.60,
    "mlb_prop_pitcher_walks":    0.60,
    "mlb_prop_batter_hits":      0.60,
    "mlb_prop_batter_tb":        0.60,
    "mlb_prop_batter_hr":        0.20,  # v2: HR prob range is 10-25%, 55% would never fire (unchanged)
    "mlb_prop_batter_rbi":       0.62,
    "mlb_prop_batter_runs":      0.62,
    "mlb_prop_batter_sb":        0.18,  # logistic — P(SB) range 3-25%; raised from 15%
    "mlb_prop_batter_walks":     0.62,
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
        "train_seasons": list(range(2019, 2024)),
        "test_season":   2024,
        "sbr_dir":       ROOT / "data/raw/datawarehouse/mlb",
    },
    "NHL": {
        "odds_api_key":  "icehockey_nhl",
        "seasons":       list(range(2019, 2026)),
        "train_seasons": list(range(2019, 2024)),
        "test_season":   2024,
        "sbr_dir":       ROOT / "data/raw/datawarehouse/nhl",
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
}

# ESPN team ID maps — ESPN uses numeric IDs
ESPN_MLB_TEAM_IDS = {
    "ARI": 29, "ATL": 15, "BAL": 1,  "BOS": 2,  "CHC": 16, "CWS": 4,
    "CIN": 17, "CLE": 5,  "COL": 27, "DET": 6,  "HOU": 18, "KC":  7,
    "LAA": 3,  "LAD": 19, "MIA": 28, "MIL": 21, "MIN": 9,  "NYM": 21,
    "NYY": 10, "OAK": 11, "PHI": 22, "PIT": 23, "SD":  25, "SEA": 12,
    "SF":  26, "STL": 24, "TB":  30, "TEX": 13, "TOR": 14, "WSH": 20,
}

ESPN_NHL_TEAM_IDS = {
    "ANA": 25, "ARI": 53, "BOS": 1,  "BUF": 2,  "CAR": 26, "CBJ": 29,
    "CGY": 20, "CHI": 16, "COL": 21, "DAL": 25, "DET": 17, "EDM": 22,
    "FLA": 13, "LAK": 26, "MIN": 30, "MTL": 8,  "NJD": 1,  "NSH": 18,
    "NYI": 2,  "NYR": 3,  "OTT": 9,  "PHI": 4,  "PIT": 5,  "SEA": 55,
    "SJS": 28, "STL": 19, "TBL": 14, "TOR": 10, "VAN": 23, "VGK": 54,
    "WSH": 15, "WPG": 52,
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
}

# Baseball Savant leaderboard CSV base URL
SAVANT_BASE_URL = "https://baseballsavant.mlb.com/leaderboard/custom"

# ── Directories ───────────────────────────────────────────────────────────────
MODELS_DIR    = ROOT / "models" / "saved"
NOTEBOOKS_DIR = ROOT / "notebooks"
RAW_DATA_DIR  = ROOT / "data" / "raw"

# Ensure critical directories exist at import time
for _d in [MODELS_DIR, RAW_DATA_DIR / "datawarehouse/mlb", RAW_DATA_DIR / "datawarehouse/nhl"]:
    _d.mkdir(parents=True, exist_ok=True)

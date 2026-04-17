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

# Action filter — used by dashboard for display filtering.
ACTION_MIN_PROB: float = float(os.environ.get("ACTION_MIN_PROB", 0.65))
ACTION_MIN_EDGE: float = float(os.environ.get("ACTION_MIN_EDGE", 0.10))
# Moneyline/runline action filter — lower thresholds to surface more ML picks.
ML_ACTION_MIN_PROB: float = float(os.environ.get("ML_ACTION_MIN_PROB", 0.58))
ML_ACTION_MIN_EDGE: float = float(os.environ.get("ML_ACTION_MIN_EDGE", 0.07))
MAX_KELLY_FRACTION: float   = float(os.environ.get("MAX_KELLY_FRACTION",   0.05))
# Edges above this magnitude are almost certainly model noise — filter them out
MAX_EDGE_CAP: float         = float(os.environ.get("MAX_EDGE_CAP",         0.20))

# Per-model BET edge thresholds (override the global default above).
# Derived from 2024 OOS backtest sweep: higher thresholds filter to higher-quality picks.
# Revisit after each retrain — edge distributions shift as features are added.
MODEL_EDGE_THRESHOLDS: dict = {
    "mlb_moneyline":            0.07,   # lowered from 0.11 to populate more ML picks (2026-04-17)
    "mlb_over_under":           0.10,   # 60% win / +18% ROI OOS at 10% (2024-2025 sweep)
    "mlb_runline":              0.07,   # matches ML threshold
    "nhl_moneyline":            0.10,   # placeholder — NHL not yet trained
    "nhl_moneyline_regulation": 0.10,
    "nhl_over_under":           0.10,
    "nhl_puckline":             0.10,
}

# Per-model minimum model probability to generate a BET signal.
# Moneyline markets run at a lower floor to surface more picks.
MODEL_PROB_THRESHOLDS: dict = {
    "mlb_moneyline":            0.58,
    "mlb_over_under":           0.65,
    "mlb_runline":              0.58,
    "nhl_moneyline":            0.58,
    "nhl_moneyline_regulation": 0.58,
    "nhl_over_under":           0.65,
    "nhl_puckline":             0.58,
}

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
    "nhl_moneyline":            ("NHL", "h2h",      "Home team wins incl. OT/SO"),
    "nhl_moneyline_regulation": ("NHL", "h2h_3way", "Regulation result: Home / Draw / Away"),
    "nhl_over_under":           ("NHL", "totals",   "Total goals over/under"),
    "nhl_puckline":             ("NHL", "spreads",  "Favored team covers -1.5 puck line"),
}

# ── The Odds API ──────────────────────────────────────────────────────────────
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_API_REGIONS = "us"
ODDS_API_BOOKMAKER = "draftkings"

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

# ── Directories ───────────────────────────────────────────────────────────────
MODELS_DIR    = ROOT / "models" / "saved"
NOTEBOOKS_DIR = ROOT / "notebooks"
RAW_DATA_DIR  = ROOT / "data" / "raw"

# Ensure critical directories exist at import time
for _d in [MODELS_DIR, RAW_DATA_DIR / "datawarehouse/mlb", RAW_DATA_DIR / "datawarehouse/nhl"]:
    _d.mkdir(parents=True, exist_ok=True)

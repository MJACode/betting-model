"""
NCAAF live (in-play) model - configuration.

A deliberate PORT of nfl/live_model (see its README for the architecture and
the two silent bugs that shaped it). Standalone package on purpose: nfl/ has
its own models/ and scripts/ dirs that shadow the platform's the moment nfl/
lands on sys.path, so nothing here imports from there. Where a design decision
is inherited, the comment says so; where CFB differs, the difference is the
point of the file.

CFB-specific facts that drive the numbers below:
  * regulation is 3600 seconds, same as the NFL (15-minute quarters)
  * OVERTIME IS NOT SUDDEN DEATH and not clocked: alternating possessions from
    the opponent 25. Even less regulation-shaped than NFL OT, so the same
    decision applies twice as hard - OT states are dropped from training and
    the engine declines to price in-OT games.
  * scoring is higher and wider (2015-2025 FBS average total ~ 55 vs the
    NFL's ~ 44), which the empirical Stage 2 pmf absorbs by construction.
"""

from __future__ import annotations

import os
from pathlib import Path

# Same .env the platform reads - CFBD_API_KEY and ODDS_API_KEY live there.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

PKG_ROOT = Path(__file__).parent
REPO_ROOT = PKG_ROOT.parent

# Large flat files stay out of git (the nfl/ weather-cache precedent).
DATA_DIR = PKG_ROOT / "data"
PBP_DIR = DATA_DIR / "pbp"
ARTIFACT_DIR = DATA_DIR / "artifacts"
SNAP_DIR = DATA_DIR / "snapshots"
for d in (PBP_DIR, ARTIFACT_DIR, SNAP_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── seasons ──────────────────────────────────────────────────────────────────
# 2020 excluded project-wide (COVID). PBP quality before 2015 is untested.
ALL_SEASONS = tuple(s for s in range(2015, 2026) if s != 2020)
TRAIN_SEASONS = tuple(s for s in ALL_SEASONS if s <= 2022)
VALID_SEASONS = (2023, 2024)
HOLDOUT_SEASONS = (2025,)      # never touched until the calibration gates

# ── stage 1 priors (CFB values, measured not copied) ─────────────────────────
# FBS teams run more scrimmage plays than NFL teams; the states builder
# verifies this against the data it loads and warns on drift.
LEAGUE_PLAYS_PER_GAME = 145.0
LEAGUE_PASS_RATE = 0.52
PASS_RATE_PRIOR_PLAYS = 25.0

# ── calibration gates (inherited thresholds; see calibrate.py) ───────────────
GATE_BRIER_MAX = 0.20          # win-probability Brier on the holdout season
GATE_COVERAGE_PP = 2.0         # quantile coverage error, percentage points

# ── odds / snapshots ─────────────────────────────────────────────────────────
ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY") or os.environ.get("ODDS_API_KEY", "")
ODDS_SPORT_KEY = "americanfootball_ncaaf"
SNAPSHOT_BOOK = "draftkings"
# Measured 2026-08-28 against the live API (not the documented formula): one
# historical NCAAF odds snapshot, one market, one bookmaker = 10 credits.
MEASURED_CREDITS_PER_SNAPSHOT = 10

# CFBD, for play-by-play (same key the platform uses).
CFBD_API_KEY = os.environ.get("CFBD_API_KEY", "")
CFBD_BASE_URL = "https://api.collegefootballdata.com"
CFBD_REQUEST_PAUSE = 0.35

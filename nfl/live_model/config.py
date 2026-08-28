"""
Configuration for the NFL live (in-play) model.

Every number a human might want to argue about lives here, not inline in the
engine. Thresholds are seeded from the build spec and are DELIBERATELY
conservative: an in-play model starts with less trust than a pregame model,
because the backtest that justifies it is built on 5-minute snapshots and a
5-minute snapshot flatters any latency-sensitive strategy.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # nfl/
PBP_DIR = ROOT / "data" / "pbp"
ARTIFACT_DIR = ROOT / "data" / "live_model"
CARD_DIR = ROOT / "data" / "cards"

SPORT_KEY = "americanfootball_nfl"

# ------------------------------------------------------------------ seasons
TRAIN_SEASONS = tuple(range(2015, 2023))            # 2015-2022
VALID_SEASONS = (2023, 2024)                        # calibration gates
HOLDOUT_SEASONS = (2025,)                           # never touched until the end

# --------------------------------------------------------------- market keys
# Anchor. Priced, never bet. The devigged live main line is treated as truth
# and the score distribution is recalibrated onto it (engine/pricing.py).
ANCHOR_MARKETS = ("h2h", "spreads", "totals")

# Lane b: derivative game lines that lag the repriced main line.
DERIVATIVE_MARKETS = (
    "alternate_spreads",
    "alternate_totals",
    "team_totals",
    "alternate_team_totals",
    "h2h_h2",
    "spreads_h2",
    "totals_h2",
    "h2h_q3",
    "spreads_q3",
    "totals_q3",
    "h2h_q4",
    "spreads_q4",
    "totals_q4",
)

# Lane c: live player props, repriced lazily against the evolving game script.
PROP_MARKETS = (
    "player_pass_yds",
    "player_pass_attempts",
    "player_pass_completions",
    "player_pass_tds",
    "player_rush_yds",
    "player_rush_attempts",
    "player_reception_yds",
    "player_receptions",
    "player_anytime_td",
)

# Books we can actually get a bet down at. Pinnacle (eu) is a sharp anchor
# only, never an execution venue, and is polled only for the markets where we
# use it as the fair price (lane d).
EXECUTION_REGIONS = "us"
SHARP_REGIONS = "eu"
SHARP_BOOK = "pinnacle"

# ------------------------------------------------------------ poll cadences
# Seconds. The books reprice off the official feed in 1-3s and The Odds API
# republishes featured markets every ~40s and props every ~60s, so polling
# faster than this buys nothing but credits.
POLL_STATE_SEC = 10                 # ESPN game state
POLL_ANCHOR_SEC = 60                # main lines, while any game is live
POLL_DERIVATIVE_SEC = 60            # only for games in a hunt state
POLL_PROP_SEC = 60                  # baseline, matches the ~60s republish
POLL_PROP_TRIGGERED_SEC = 60        # after a game-script trigger fires
POLL_HALFTIME_SEC = 60              # inside the halftime window

# Staleness guards. Acting on a stale quote is how a backtest edge becomes a
# live loss: skip and log rather than guess.
MAX_QUOTE_AGE_SEC = 90
MAX_STATE_AGE_SEC = 45

# ------------------------------------------------------------------- credits
# The live endpoint costs 1 credit per market per region per poll. A full
# Sunday of naive polling would be five figures, so the worker is metered.
# Daily ceiling on live spend. Raised from 4,000 when prop polling went
# continuous, because a cap that halts coverage in the fourth quarter of the
# late window is not a safety net, it is a silent hole in the record.
#
# MEASURED AND PROJECTED, at 1 credit per prop poll per game per minute and
# 3 credits per slate wide anchor poll per minute:
#   one preseason game, ~3h   180 prop  +   540 anchor  =    ~720
#   a full Sunday, ~13 games  2,340 prop + 1,800 anchor =  ~4,140
# 12,000 leaves roughly 3x headroom for a Sunday plus the night game, and at
# that rate the 4.37M credits remaining outlast several NFL seasons.
#
# The 9x saving that makes this affordable is buying only the ONE market the
# deployed lane reads instead of all nine in PROP_MARKETS. Restore the cap
# math before adding a lane that needs a second market.
LIVE_DAILY_CREDIT_CAP = int(os.getenv("NFL_LIVE_DAILY_CREDIT_CAP", "12000"))
BACKTEST_CREDIT_BUDGET = int(os.getenv("NFL_LIVE_BACKTEST_BUDGET", "5000"))

# --------------------------------------------------------------- thresholds
# EV thresholds by lane. Props are wider because the prop model carries more
# model risk than the score distribution; cross-book stale is tighter because
# the fair price is another book's number rather than our own model.
EV_THRESHOLDS = {
    "nfl_live_halftime": 0.04,
    "nfl_live_deriv": 0.04,
    "nfl_live_prop": 0.06,
    "nfl_live_stale": 0.03,
}
MODEL_IDS = tuple(EV_THRESHOLDS)

# ------------------------------------------------------------------- sizing
# Quarter Kelly with a further half haircut, hard capped. See the spec: the
# live model starts with LESS trust than the pregame models, not equal.
KELLY_FRACTION = 0.25
KELLY_HAIRCUT = 0.5
MAX_STAKE_FRACTION = 0.005          # 0.5% of bankroll on any one bet
MAX_DAILY_EXPOSURE_FRACTION = 0.02  # 2% aggregate live exposure per game day

# ------------------------------------------------------------- hunt triggers
# A derivative quote is "lagging" when it has moved less than this share of the
# move the main line implies for it since the last anchor move.
DERIV_LAG_RATIO = 0.5

# Game-script triggers that make props worth re-polling at the faster cadence.
SCRIPT_LEAD_TRIGGER = 10            # points, entering the second half
SCRIPT_PACE_Z_TRIGGER = 1.5         # plays-per-minute z score vs pregame prior

# ------------------------------------------------------------------- engine
SCORE_GRID_MAX = 70                 # final-score support per team, 0..70
MIN_SECONDS_FOR_PRICING = 30        # below this the market is a coin flip on a kneel
PROB_FLOOR = 1e-6

# Anchor blend tolerance: if our implied main line sits further than this from
# the devigged market number we shift the marginals onto the market before
# pricing anything downstream.
ANCHOR_TOL_PROB = 0.005             # 0.5pp on the moneyline
ANCHOR_TOL_POINTS = 0.25            # quarter point on the total

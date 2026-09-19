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
# 10 -> 5 on 2026-09-05 (Matt: "every 5 seconds or less when game starts").
# ESPN game state is NOT an Odds API call -- it costs no credits -- and it is
# what the model reads the game off, so this is the poll that matters and the
# one that was free to tighten. The quote polls below deliberately did NOT
# follow it: see the note there.
POLL_STATE_SEC = 5                  # ESPN game state
# 60 -> 5 on 2026-09-05 (Matt), with the cost stated and accepted.
#
# What 5s buys, precisely: the aggregator republishes featured markets every
# ~40-46s (136 distinct snapshots over 2.5 hours, ~7 consecutive polls served
# the identical payload -- docs/discord.md), so this CANNOT make a quote fresher
# than that floor. What it does buy is catching each new snapshot within 5s of
# it appearing instead of up to 60s later, which is the same trade the MLB live
# loop took when it went to 5s. Do not read it as beating the book.
#
# The prop / derivative / halftime polls below deliberately stay at 60s: the
# prop feed's own republish is ~60s, so the argument above does not carry, and
# each is a per-game cost rather than one slate-wide call.
POLL_ANCHOR_SEC = 5                 # main lines, while any game is live
POLL_DERIVATIVE_SEC = 60            # only for games in a hunt state
POLL_PROP_SEC = 60                  # baseline, matches the ~60s republish
POLL_PROP_TRIGGERED_SEC = 60        # after a game-script trigger fires
POLL_HALFTIME_SEC = 60              # inside the halftime window

# Staleness guards. Acting on a stale quote is how a backtest edge becomes a
# live loss: skip and log rather than guess.
MAX_QUOTE_AGE_SEC = 90
MAX_STATE_AGE_SEC = 45
# How far the book's own number may move, with NO change in the state we can
# see (score, period, possession), before that state is treated as stale and
# the quote declined with reason `book_moved`. The mirror of the pre-score
# guard: that one declines a quote stamped before a score we HAVE seen; this
# one declines a quote that has priced something we have NOT seen yet.
# 2026-09-19, NCAAF: DraftKings went -174 -> +100 on a touchdown the score
# feed reported 23s later, and the loop bet in the gap. The NFL lane gets the
# guard the same day, before its own incident (CLAUDE.md 1b -- one live
# model's change is assessed against all of them). Timeline and rule:
# data/live_quote_guard.py, BookMoveClock.
#
# Keyed by market; a market not listed is not guarded. Moneylines in implied
# probability, everything else in the line's own units. THE PROP CAP IS NOT
# MEASURED: the deployed lane's snapshots live on the worker volume as gzip
# blobs (`nfl_live_prop_snapshots`), which cannot be read from here. 8.0
# attempts is chosen to catch an injury-scale move (a starter leaving takes
# the line down by half) and NOT a long drive (accrual moves it a few
# attempts a possession, and possession is in the state). Every refusal is
# recorded in the decisions log with this reason, so after one Sunday the
# count is a query and the cap moves on that.
BOOK_MOVE_MAX = {
    "h2h": 0.08,
    "spreads": 3.0,
    "totals": 3.0,
    "totals_h2": 3.0,
    "spreads_h2": 3.0,
    "player_pass_attempts": 8.0,
}
# THE SETTLED-STATE RULE (2026-09-19): no bet on a guarded market until the
# book's number and our state have both been still for this long -- the
# quiet version of the defect the cap catches, caught by time rather than by
# size. Same window as NCAAF (ncaaf_live/config.LIVE_SETTLED_SEC, where the
# feed lags were measured); ESPN's NFL feed is the faster one, so this is
# conservative here. `SETTLED_TOL` is what counts as the book moving for the
# clock (juice wobble does not); a market not listed uses 0.0, i.e. any
# change. Refusals are recorded as `not_settled`, so the cost is a query.
SETTLED_SEC = int(os.getenv("NFL_LIVE_SETTLED_SEC", "120"))
SETTLED_TOL = {"h2h": 0.02, "spreads": 0.5, "totals": 0.5, "totals_h2": 0.5,
               "spreads_h2": 0.5, "player_pass_attempts": 0.5}

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
#
# RE-SIZED 2026-09-05 with POLL_ANCHOR_SEC at 5s. The anchor poll is slate-wide
# at ~3 credits, so 12x the rate is 12x that component and nothing else:
#   a full Sunday, ~13h       2,340 prop + 21,600 anchor = ~23,940
# 12,000 would now BIND BY EARLY AFTERNOON, and this file already says why that
# is the worst outcome: "a cap that halts coverage in the fourth quarter of the
# late window is not a safety net, it is a silent hole in the record." 60,000
# keeps ~2.5x headroom over the projection. Season cost is roughly +30k per
# game day, ~1.1M over 18 weeks, against 4.71M remaining and a 46-76k/day burn
# (odds_api_quota, read 2026-09-05) -- affordable, and worth re-reading at the
# midpoint rather than assuming.
#
# The 9x saving that makes this affordable is buying only the ONE market the
# deployed lane reads instead of all nine in PROP_MARKETS. Restore the cap
# math before adding a lane that needs a second market.
LIVE_DAILY_CREDIT_CAP = int(os.getenv("NFL_LIVE_DAILY_CREDIT_CAP", "60000"))
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

# The most juice this lane will lay, as an American price (Matt, 2026-09-05:
# "-140 should be price ceiling"). A quote worse than this is REFUSED before the
# EV test, so the lane never takes the bet at all.
#
# Enforced HERE and not in the display filter, deliberately. The same number in
# config.MODEL_MIN_ODDS would have let the lane bet -250 and then hidden the
# pick from the app, Discord and push -- taken and concealed from the person who
# has to place it, which is the failure #491 fixed. A ceiling the model applies
# is a decision; a ceiling the board applies is a disappearance.
#
# -140 matches the blanket prop floor every MLB and WNBA prop model carries, so
# the live lane lays no more juice than the pre-game ones. It is a RISK rule,
# not a measured cut: a live prop past -140 needs a very high model probability
# to clear the 0.06 EV gate, and that is exactly where the model is least worth
# trusting.
MIN_PRICE = float(os.getenv("NFL_LIVE_MIN_PRICE", "-140"))

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

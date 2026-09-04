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

# ── stage 2 fit rule ─────────────────────────────────────────────────────────
# Chosen on the 2024 PSEUDO-holdout (ncaaf_live.backtest.tune_stage2 + the
# follow-up era probes), never on 2025. The verdict was ERA DRIFT IN SHAPE:
# at a fixed predicted mean, older seasons' outcome distributions are wider
# than modern ones, and restricting the fit window improved 2024 coverage
# monotonically (all-seasons 4.39pp -> 2022-23 2.76pp) while every smoothing
# variant moved nothing (4.4-4.5pp across five candidates) and every
# exponential half-life underperformed the hard window. One season only
# (2.61pp) nearly halves cell support (88/196 thin) for 0.15pp - not worth it.
#
# VARIANT ACCOUNTING: 14 configurations were examined on the 2024 pseudo-
# holdout before this was locked. 2025 was touched exactly twice: the original
# failed gate run, and the single re-run after this rule was fixed.
STAGE2_RECENT_SEASONS = 2          # Stage 2 fits on the N most recent OOS seasons
STAGE2_FIT_KW = {"laplace": 0.5}

# ── live gameday cadence ─────────────────────────────────────────────────────
# SPLIT cadences, restoring the nfl/live_model ancestor's design (its
# POLL_STATE_SEC=10 / POLL_ANCHOR_SEC=60). The first NCAAF port collapsed both
# into a single 45s sleep, which meant the fast, free feed was throttled to the
# speed of the slow, paid one. They are independent:
#
#   STATE is free (ESPN/CFBD) and is what actually moves in-play - a score, a
#   turnover, the clock. Polling it fast is pure upside.
#   ODDS is metered. Every fetch is billed, so its cadence is a spend decision.
#
# Both are env-overridable so a cadence change never needs a code edit.
# The CFBD plan's monthly call allowance, as a NUMBER rather than a prose claim
# about a tier. This exists because the 5s cadence was set against a comment
# asserting a tier the account was not on, and a comment cannot be checked by
# anything. Read the allowance off the CFBD account page -- the ALLOWANCE is the
# fact that matters, not the price or the tier name (both have been reported
# inconsistently). Patreon tiers at time of writing: free 1k / $1 5k / $5 30k /
# $10 75k. test_gameday_cadence asserts the configured cadence fits this number,
# so lowering the poll without raising the plan fails a test instead of failing
# silently in November.
CFBD_MONTHLY_CALL_ALLOWANCE = int(
    os.environ.get("CFBD_MONTHLY_CALL_ALLOWANCE", "125000"))

# THIS IS THE CFBD BILL. One /scoreboard call per pass, so the monthly call
# count is set here and nowhere else (the odds knobs below bill The Odds API,
# which is not the constraint -- 4.36M credits remain).
#
# 15 -> 5 (2026-08-29). Cadence history worth keeping, because it turned on a
# number nobody had actually read: 5s was set on a claim of "$10 / 75k", cut to
# 15s when the plan was reported as Tier 2 (30k), then restored here once the
# CFBD plan page settled it at TIER 4 / 125k. 5s models to ~60k/month realistic
# and ~77k in a busy November -- 62% of the allowance, which fits with real room.
#
# Modelled calls/month vs the 125k allowance:
#     5s ~60k (62% at busy)   10s ~31k (32%)   15s ~21k (22%)
#
# The idle backoff and the no-kickoff-near exit below are what make this
# affordable at all: without them the idle burn ALONE was ~120k/month, 96% of
# this plan before a single game kicked off.
POLL_STATE_SEC = int(os.environ.get("NCAAF_LIVE_POLL_STATE_SEC", "5"))
# 15 -> 5 (2026-08-29, Matt): the last flat wait in the loop. NOTE the real
# bound is the PASS, not this number -- the odds fetch happens inside the state
# loop, so any value at or below POLL_STATE_SEC means "fetch every pass" and
# nothing below 10s buys anything further. So 5 is not a 5s cadence; it is
# "every pass", i.e. worst-case staleness 20s -> 10s. A true 5s odds cadence
# needs POLL_STATE_SEC at 5 too, which roughly doubles the CFBD bill (that is a
# vendor-tier decision, not a code one).
POLL_ODDS_SEC = int(os.environ.get("NCAAF_LIVE_POLL_ODDS_SEC", "5"))
# Floor the odds cadence collapses to when the SCORE CHANGED since the last
# pass. A score is the event that moves a live total, so it is also the moment
# the cached price is most wrong and a pick is most likely to become
# actionable -- waiting out the remaining idle cadence is the last real lag in
# the loop. This mirrors the MLB in-play orchestrator, which fetches on trigger
# events rather than on a flat clock (§21).
#
# Cost is bounded by scoring frequency, not by the floor: a CFB game has ~10-14
# scores, so this adds ~a dozen fetches per game against ~2,900 idle ones. Set
# equal to POLL_ODDS_SEC to disable the trigger.
POLL_ODDS_TRIGGER_SEC = int(
    os.environ.get("NCAAF_LIVE_POLL_ODDS_TRIGGER_SEC", "3"))

# IDLE cadence - and the reason a fast poll is not free after all. CFBD bills by
# the call (free 1,000/month; Patreon tiers 5k / 30k / 75k), and the loop does
# NOT stop polling between games: it initialises its idle clock at startup and
# polls for a full IDLE_EXIT_MINUTES before exiting, after which the */10
# supervisor relaunches it - so it runs at ~86% duty cycle 11am-midnight whether
# or not anything is live. At 10s that is ~4,000 calls on a day with NO GAMES,
# ~120k/month, which exceeds the largest published tier. Nothing needs a 10s
# poll when nothing is live: the fast cadence exists to react to a scoring
# drive, and being up to a minute late to notice a kickoff costs nothing (the
# engine cannot price an opening snap anyway).
POLL_IDLE_SEC = int(os.environ.get("NCAAF_LIVE_POLL_IDLE_SEC", "60"))

# ESPN needs one summary call PER LIVE GAME, so on a 20-game Saturday the
# per-game fan-out - not the loop - is what sets the achievable cadence. These
# are independent GETs; a small pool collapses them into roughly one round
# trip. CFBD carries every game's state in its single scoreboard call and
# ignores this entirely.
SUMMARY_FETCH_WORKERS = int(os.environ.get("NCAAF_LIVE_SUMMARY_WORKERS", "6"))

# ── odds / snapshots ─────────────────────────────────────────────────────────
ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY") or os.environ.get("ODDS_API_KEY", "")
ODDS_SPORT_KEY = "americanfootball_ncaaf"
SNAPSHOT_BOOK = "draftkings"

# Hard stop against a retry bug draining the account, NOT a budget. Sized
# against the WORST realistic case rather than the nominal cadence, because the
# two converged when the odds cadence dropped below the pass: every pass now
# fetches, so a 13-hour Saturday is ~4,700 fetches x ~4 credits = ~19k. 30k left
# only 1.6x headroom and could have bound on a long slate -- at which point the
# age bound below would (correctly, but needlessly) start declining bets. 60k
# restores ~3x and is still ~1.4% of the account balance.
LIVE_ODDS_SESSION_CREDIT_CAP = int(
    os.environ.get("NCAAF_LIVE_CREDIT_CAP", "60000"))

# An in-play price this old is not one you can actually bet, so past this the
# feed reports NO odds rather than handing the engine a frozen line. This is
# what makes hitting the credit cap (or a sustained feed outage) fail SAFE:
# both stop the refresh, and without an age bound the loop would keep pricing
# against a line that stopped moving hours ago. Mirrors the platform's
# LIVE_ODDS_MAX_AGE_SEC.
LIVE_ODDS_MAX_AGE_SEC = int(os.environ.get("NCAAF_LIVE_ODDS_MAX_AGE_SEC", "180"))

# How old DRAFTKINGS' OWN last_update may be before a market is declined.
#
# This is a different quantity from LIVE_ODDS_MAX_AGE_SEC above, and confusing
# the two is what let a four-minute-frozen line get bet. That one bounds OUR
# fetch age and only fires when the loop itself stops; at a 5s cadence it is
# essentially always 0. This one bounds the BOOK's publish age, which is the
# only thing that says whether the price is still on offer.
#
# 90s is the NFL live model's proven value (MAX_QUOTE_AGE_SEC), and it fits
# what DraftKings actually does: measured over 1,687 in-play publishes on
# 2026-08-29 the median gap between republishes was 47s and p90 was 106s. So
# 90s accepts the normal rhythm and rejects a freeze - the Florida State
# market that produced the bad pick had held one number for 275s.
#
# 2026-08-30: the PLATFORM twin of this knob went to 30s on mike's call, after
# a cross-book measurement showed MLB in-play prices on the wrong line 20.5% of
# the time beyond 60s. This one is DELIBERATELY LEFT AT 90, and CLAUDE.md 1b
# requires saying so rather than leaving the difference silent.
#
# The measurement was MLB-only and does not transfer. Baseball reprices between
# pitches; football holds a number between plays and through every clock
# stoppage, which is the normal rhythm here rather than a freeze -- a 30s bound
# would decline the majority of legitimate passes. The same measurement can be
# run for NCAAF against DK's own feed now that the season is on, and this value
# should move on THAT evidence, not on baseball's.
LIVE_QUOTE_MAX_AGE_SEC = int(
    os.environ.get("NCAAF_LIVE_QUOTE_MAX_AGE_SEC", "90"))

# How far the book's publish clock may sit BEHIND the moment we saw the score
# and still be decided on. Zero: a quote stamped before the score is a
# pre-score number, full stop.
#
# This closes the gap the 90s bound above cannot see. On 2026-09-03 the Akron @
# Wake Forest total was bet at 44.5 with a quote 62.2s old -- comfortably
# inside 90 -- 0.6s after the loop saw a touchdown, and DraftKings re-hung at
# 50.5 thirty-eight seconds later. Both bounds are on the quote's AGE, and no
# age bound distinguishes a quiet 62-second-old price from a 62-second-old
# price with a touchdown in the middle of it. The full timeline is in
# models/live_quote_guard.py.
#
# The accepted cost of zero is stated there too: when DK reprices faster than
# CFBD reports the score, a good quote is declined until DK publishes again.
# Raise this only on a measurement of that lag, never to unblock a pick.
#
# HOW LONG THE BLOCK LASTS IS POLL_ODDS_SEC, NOT THIS KNOB. The guard clears
# the moment we SEE the book's re-hang, so the lane reopens within one odds
# cadence of it. At the default 5s ("every pass") that is negligible: on
# 2026-09-03 the re-hang came 37.6s after the score and would have been picked
# up on the next pass. Raising NCAAF_LIVE_POLL_ODDS_SEC lengthens the blind
# window by the same amount, so the two knobs must be read together.
LIVE_SCORE_LAG_TOLERANCE_SEC = float(
    os.environ.get("NCAAF_LIVE_SCORE_LAG_TOLERANCE_SEC", "0"))
# Measured 2026-08-28 against the live API (not the documented formula): one
# historical NCAAF odds snapshot, one market, one bookmaker = 10 credits.
MEASURED_CREDITS_PER_SNAPSHOT = 10

# CFBD, for play-by-play (same key the platform uses).
CFBD_API_KEY = os.environ.get("CFBD_API_KEY", "")
CFBD_BASE_URL = "https://api.collegefootballdata.com"
CFBD_REQUEST_PAUSE = 0.35

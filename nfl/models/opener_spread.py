"""
Opener sharp-vs-soft spread: the frozen rule, its per-bet win probability, and
the selection. Published by the platform as model `nfl_opener_spread`.

This is the MODEL. `scripts/daily_opener_card.py` is the live card that fetches
the board, calls `select_opener_bets`, and writes the CSV the publisher reads.
Keep the rule here and the plumbing there.

THE RULE (unchanged from the corrected backtest)
------------------------------------------------
In the T-7 to T-2 day window — Pinnacle posts around T-6.5, soft books still
carry the numbers they hung days earlier — wherever a clean soft book's HOME
spread deviates from Pinnacle's by at least `DEPLOY_THRESHOLD` points, bet the
side Pinnacle favours AT the soft book's stale number. One bet per game, taken
at the FIRST qualifying moment. The card runs daily, so "first qualifying
moment" is realised at daily resolution; the number corrects only ~4.8% a day,
so daily granularity loses little. LATER RUNS NEVER REPRICE A TAKEN BET — the
edge IS staleness, and waiting destroys it. The publisher enforces that lock.

Unlike the wind rule this is a race. There is nothing left at the close.

EVIDENCE (scripts/backtest_opener.py, 2020-2025, 1,675 games, 35 clean books)
--------------------------------------------------------------------------
RESTATED 2026-08-23 on SIX seasons. The original figure rested on 2023-2025,
which was all the densely-scanned data there was. A 27,300-credit scan added
2020-2022 at the same 6-hourly resolution, and the edge did not survive it.

  |dev| >= 1.0 : n=1,178, ATS 56.88% against 54.60% expected from the number
  bought, so +2.27pp excess [95% CI -0.6, +5.1]; ROI +1.34% [-3.9, +6.4] at
  the juice actually quoted. Both intervals span zero.

  Season ROI: 2020 -2.62%, 2021 -1.78%, 2022 -2.80%, 2023 +4.72%,
  2024 +10.86%, 2025 +0.32%. The three seasons that were added are ALL
  negative, and the DraftKings placebo now returns +0.95pp [-1.7, +3.7]
  against the model's +2.27pp — a gap too small to call.

  Raising the threshold does not rescue it: |dev| >= 2.0 over the same six
  seasons is +2.63% ROI [-6.3, +11.0] on n=356.

WHAT CHANGED, AND WHY THE OLD NUMBER WAS TOO HIGH
-------------------------------------------------
Two things, both corrections rather than new information:

  1. The backtest did not exclude EXCHANGES, but the live card always has.
     Matchbook quotes deep alternate lines that read as enormous "deviations"
     from Pinnacle's main number — in 2020 the selected bets averaged a price
     of about -2,000. Those were never openers, and the deployment would never
     have taken them. Excluding them, as the card does, lowers even the
     original 2023-2025 figure from +6.82% to +5.37%.
  2. Three more seasons of data, all of them worse.

WHAT DID NOT SURVIVE
--------------------
Totals and moneyline were scanned densely across 2023-2025 on the same
6-hourly grid and both are NULL; the totals placebo matches the totals signal
at every threshold. Spreads only.

LIVE, AND SIZED TO THE EVIDENCE
-------------------------------
Kept as a production model by explicit decision (2026-08-23) after the
six-season restatement above. That is a judgement call about an edge whose
interval spans zero, and the sizing is built to survive being wrong:

  * probabilities are the SIX-season ones, ~2.8pp below the three-season table
    they replace, so every stake is smaller at the same deviation;
  * the stake is Kelly-proportional per bet rather than flat, which matters
    enormously here. Over 2020-2025, 89% of picks carry a mean edge of
    +1.59pp and return -0.30%, while the 7% at +3.73pp return +17.13%. A flat
    stake bets those identically. Sizing takes the six-season return from
    +1.28% flat to +5.45% on units staked, risking 366u where flat risked 810u;
  * a quote whose juice has eaten the edge is staked at ZERO, not at 1u.

The honest caveat on that +5.45%: the tier boundaries came from this same
sample, so it is partly in-sample. The direction - bet more when the edge is
bigger - is not in doubt; the magnitude is not validated.

WHAT WOULD RETIRE IT: a 2026 season at or below flat. The profit across six
seasons is nearly all 2024, and 2025 was +0.32%. Paper-track through 2026
(`python -m scripts.nfl_rule_2026_track`, `docs/nfl_rule_2026_track.md`). Do
not raise the unit on a good month — UNIT_PCT stays 0.01, MAX_UNITS stays 4.
Do not unpause the paused XGB / distributional NFL props off this track.
"""

from __future__ import annotations

import os

import pandas as pd

# Books carrying home/away sign flips in the Odds API feed. Screened across 40
# books on 1.4M quotes; see scripts/screen_books.py. This rule selects on
# extremes, so a defect present in 0.4% of rows once supplied 15% of selected
# bets — the exclusion is load-bearing, not hygiene.
DEFECTIVE_BOOKS = {"betanysports", "betsson", "nordicbet", "tipico_de"}

# Exchange prices are gross of ~2% commission and the platform's picks table
# has no way to express that, so the exchange is not bettable here. It was 1 of
# the 29 clean books in the backtest; excluding it is the conservative side.
EXCHANGES = {"matchbook"}

REFERENCE = "pinnacle"

# THE SOFT SIDE MUST BE A BOOK THE READER CAN ACTUALLY BET AT.
#
# Until 2026-09-06 the rule took the largest deviation at ANY clean book, and
# the feed is full of books nobody here holds. Measured on the live Week-1
# board that morning: of seven qualifying bets, the two largest edges were at
# onexbet (+7.32pp) and betus (+5.92pp). mike: "no can't bet on these remove
# them". A pick naming an unplaceable book is worse than no pick — §1c makes it
# permanent, and it enters the track record as a bet that was never available.
#
# THE LIST LIVES IN data_ingest/books.py, because the WIND card needs exactly
# the same one (2026-09-06), and two cards that disagree about which books are
# bettable is the bug rather than the fix.
#
# Imported INSIDE the function, not at module scope. This module is loaded by
# absolute path from places that do not have nfl/ on sys.path (the platform
# test suite, backtests), where a top-level `from data_ingest...` raises
# ModuleNotFoundError and takes the whole model down with it. `evaluate_board`
# imports pick_eval the same way and for the same reason — measured here: a
# module-scope version of this import broke evaluate_board on the first run.
def _bettable_books() -> set[str]:
    """The placement venues. See data_ingest/books.py for the list and why."""
    from data_ingest.books import bettable_books
    return bettable_books()


# |soft_home_line - pinnacle_home_line|, points.
#
# 2.0, NOT 1.0 (mike, 2026-09-11: "the opener needs to be more aggressive, way
# too many picks, I need statistical profitability"). Measured on the selection
# the live card actually runs -- bettable books only, first qualifying
# snapshot, Kelly-skipped -- over 2020-2025 (scripts/opener_cut_sweep.py):
#
#   |dev| >= 1.0   728 bets   -0.03% ROI  [-6.9, +6.7]   4/6 seasons positive
#   |dev| >= 1.5   268 bets   -5.09%      [-16.1, +6.0]  2/6
#   |dev| >= 2.0   125 bets   +3.97%      [-11.8, +19.1] 5/6  (2022 -28% the one loss)
#   |dev| >= 2.5    76 bets  -11.00%      [-30.3, +8.3]  3/6
#
# So the 1-point rule is flat on the books we can bet at, and 2.0 is the only
# floor whose row is positive across the edge grid (0/0.02/0.03 -> +4.0/+6.2/
# +1.5%). It is NOT statistically profitable: no cell in the sweep has an
# interval that excludes zero, and 1.5 and 2.5 are both negative, so this is a
# ridge rather than a plateau. Stated plainly so nobody reads 2.0 as a finding.
# What it does do is stop writing the 83% of picks that measured -0.03%.
#
# This is also what the six-season calibration always intended: DEV_WIN_PROB
# puts |dev| < 2.0 at 0.5470, below the 0.55 platform gate "ON PURPOSE" (the
# note that was on config.py until 2026-08-22). The gate was lowered to 0.52
# that day and the 1-point picks started flowing. Both levers now agree.
DEPLOY_THRESHOLD = 2.0

# THE FIRE WINDOW: T-LEAD_HI_DAYS .. T-LEAD_LO_DAYS.
#
# The early bound was 7.0 — the span the backtest measured — and on 2026-09-06
# that bound was costing real bets. Pinnacle had posted for all 16 Week-1
# games and seven carried a qualifying deviation, but the Sunday slate sat
# 172.5h out (7.19 days), so the card watched them and fired nothing. mike:
# "we need to remove any t-7 rules on nfl opener it needs to be as soon as
# pinnacle Lines are released".
#
# So the early bound is now the CARD'S WATCH HORIZON rather than a number of
# its own: whenever Pinnacle is up and a soft book is stale, the bet is live.
# Pinnacle typically posts ~T-6.5, which is inside the old window anyway — this
# only changes the case where it posts EARLY, which is exactly the case that
# was being dropped.
#
# STATED PLAINLY, BECAUSE IT IS A REAL COST: bets taken before T-7 are outside
# the backtested span. The mechanism is the same one the backtest measured (a
# soft book carrying a number Pinnacle has already moved off), and the edge is
# larger the staler the soft number, so the direction is not in doubt — but the
# +2.27pp excess was never measured out there. Watch these separately.
#
# THE LATE BOUND IS UNCHANGED at T-2, deliberately. mike asked for the T-7 rule
# only, and dropping T-2 as well would be a different model: inside two days
# the soft books have corrected and the backtest has nothing to say about it.
LEAD_LO_DAYS = 2.0
LEAD_HI_DAYS = float(os.environ.get("NFL_OPENER_MAX_LEAD_DAYS", "10"))

# A FRESH NUMBER IS LABELLED, NOT BLOCKED. (mike, 2026-09-22.)
#
# The rule's premise is a STALE number -- a soft book still carrying a spread it
# hung days ago while Pinnacle has moved. Until 2026-09-22 the code measured only
# the deviation NOW and never asked how long the soft book had held its point.
# The first fix on that day was a gate: wait an hour before taking a number that
# had just appeared. mike rejected it -- "You do realize you're trying to win
# bets and money right?" -- and he is right about what the gate did: a book
# that hangs a wrong number for four minutes is the BEST case this model can
# find, not noise, IF the number is placeable, and the gate guaranteed the model
# never caught one. So: the age of the soft number is measured and put ON THE
# PICK ("NEW 0m"), the pick goes out at once, and whether fresh numbers are
# placeable is recorded per pick (scripts/mark_placeable.py) so that question
# is answered by the record rather than by a filter. Speed is the other half:
# the poll runs every minute for real and posts to Discord inside the tick
# (scheduler.run_nfl_opener_card).
#
# Measured that day (docs/sessions/2026-09.md). The Odds API's own snapshots put
# BetMGM on TEN @ NYG at -3.0 for hours, -2.5 from 21:24:26Z, NYG -1 (-105) /
# TEN +1 (-115) from 21:28:26Z, NYG +1 (-108) from 21:31:58Z and -3.0 again from
# 21:45:11Z -- four distinct book updates in 21 minutes, each a coherent
# two-sided quote, while every other book sat at -3. The 21:29Z tick fired
# "TEN @ NYG — NYG -1 (Opener +2 vs Pinnacle, MGM) · 1.96u" and posted it to
# Discord. Nobody could find that number at the book, and whether MGM's own
# site ever showed it is not measurable from here.
#
# HOW RARE, AND HOW LONG THE REAL ONES LAST -- because the cost of waiting is
# the number vanishing while you wait, nothing else (waiting does not worsen a
# number that is still there):
#   * Pre-game (>= 48 h before kickoff), 14 days of minute-level archive, eight
#     bettable books plus Pinnacle: ZERO one-tick >= 2-point blips at any book
#     (an earlier census that said 17-37 per book was counting in-play ticks).
#     The MGM episode is the only sub-hour deviation seen this season (the
#     archive received its ticks hours late: -2.5 to 21:27, -1.0 at 21:29 for
#     one tick, +1.0 from 21:31 to 21:43, -3.0 from 21:45). The archive holds
#     41% of pre-game minutes over those 14 days, so "zero" is a lower bound.
#   * Every other >= 2-point pre-game deviation this season lasted HOURS:
#     CLE @ JAX 2026-09-07 (Pinnacle -7.5 -> -9.5, three soft books stayed at
#     -7.5 for 4 h+ -- the classic stale case; the soft number is old and the
#     pick carries no tag); BUF @ HOU 2026-09-07 (Fanatics moved to HOU -1
#     against Pinnacle +1 and held it ~20 h with DK and MGM following -- it
#     would have read "NEW 0m" at the fire, and it won); ATL @ PIT 2026-09-10
#     (DK -5.5 vs -3.5 for hours).
#   * The one other sub-hour episode found is ALSO BetMGM: CHI @ CAR
#     2026-09-08, CAR +1 from 03:24:43Z (feed snapshots) against +3 at every
#     other book and Pinnacle +2.5, gone by 03:42Z -- 6 to 17 minutes, in an
#     archive gap, and it locked a pick under the 1.0-point rule of the day.
#     Two MGM episodes in 15 days, both under 20 minutes, both a pick.
#   * Backtest, 2020-2025, bettable books, |dev| >= 2.0, first qualifying
#     6-hourly snapshot: the soft number was still there at the NEXT snapshot
#     (median 6 h later) for 75% of the 128 selected bets.
#
# WHAT THE BACKTEST CANNOT SAY. Splitting those 128 bets by whether the soft
# point was already there at the previous 6-hourly snapshot: already-there
# n=41 at -1.7%, new-since n=87 at +7.6%, both intervals spanning zero, every
# sub-class n <= 51. At 6-hourly resolution a 17-minute episode is seen 5% of
# the time, so the backtest contains essentially no glitches to grade and
# cannot rank a filter for them -- which is the other reason the age is a
# label and not a filter: the record of placeable-or-not on fresh numbers
# (scripts/mark_placeable.py) is the only measurement that can settle it.
#
# THE LABEL. `held_minutes` measures how long the soft book has quoted its
# current point. A number under FRESH_MINUTES old is a possible book error and
# the pick says so ("NEW 3m"); an unknown age (no history at all, e.g. the
# first tick after a redeploy with Supabase unreachable) says "age unknown";
# an old number carries no tag. Nothing is skipped. `select_opener_bets` and
# `evaluate_board` both carry the age when given the prior observations, and
# the card always passes them.
FRESH_MINUTES = 60.0

# Pooled validated ATS at the deployment threshold. Kept for reference and as
# the fallback: this is what the card used for EVERY bet until 2026-08-22.
POOLED_MODEL_PROB = 0.5688      # six-season pooled ATS (was 0.5818 on three)

# ---------------------------------------------------------------------------
# PER-BET WIN PROBABILITY BY DEVIATION SIZE
#
# A 3-point deviation is worth far more than a 1-point one, and a single pooled
# number cannot see the difference: it overstates the small deviations that
# make up most of the volume and understates the rare large ones.
#
# Two measured pieces go into this table, and the first is easy to miss.
#
# 1. THE DEVIATION SHRINKS BEFORE IT PAYS. The card sees |soft - pinnacle NOW|,
#    but a bet is worth its advantage against where Pinnacle CLOSES, and the
#    soft book moves most of the way to Pinnacle before then. Measured on the
#    593 selected bets, 2023-2025: mean |dev| 1.406 -> mean realised CLV 0.902,
#    a shrink of 0.641 overall and ~0.56 across the 1.0-2.0 band that carries
#    86% of the volume. Feeding raw |dev| into the win-probability curve would
#    overstate the pooled probability by 1.5pp: 59.67% against a realised
#    58.18%.
#    Six-season knots: |dev| 1.0/1.5/2.0/2.59/7.35 -> shrink
#    0.546/0.642/0.478/0.707/1.000.
# 2. WHAT THE SHRUNK NUMBER IS WORTH, from the empirical margin-versus-close
#    residual distribution (n=7,276, 1999-2025). That distribution carries the
#    key-number atoms, which is why this table has flat stretches rather than a
#    smooth curve. Plus the measured +5.11pp Pinnacle-direction excess.
#
# Sanity check on the whole construction: applied to the 1,178 backtested bets
# it gives a pooled 56.87% against a realised 56.88% - a 0.01pp gap. The
# average is preserved and only the distribution across deviation sizes moves.
# Regenerate with scripts/calibrate_opener.py --emit.
#
# Minimum modelled probability is 0.5470 at |dev| 1.0, BELOW the min_prob
# 0.55 gate in config.py. That is intended: on six seasons a 1-point deviation
# is not worth betting. Since 2026-09-11 the card itself does not fire below
# DEPLOY_THRESHOLD = 2.0 either, so the gate and the rule agree rather than the
# gate silently hiding rows the card wrote.
# ---------------------------------------------------------------------------
DEV_WIN_PROB = {
    1.0: 0.5470, 1.5: 0.5470, 2.0: 0.5557, 2.5: 0.5806, 3.0: 0.5987,
    3.5: 0.6116, 4.0: 0.6259, 4.5: 0.6408, 5.0: 0.6597, 5.5: 0.6711,
    6.0: 0.6975, 6.5: 0.7182, 7.0: 0.7311, 7.5: 0.7519, 8.0: 0.7641,
}

# Descriptive labels for the card and the alert, in probability points of edge
# over the price actually quoted. These COMMUNICATE the size of the predicted
# edge; they do not select. Boundaries sit near the quartiles of the backtested
# edge distribution (p25 +3.0pp, p75 +5.2pp).
EDGE_TIERS = ((3.0, "SMALL"), (5.5, "MEDIUM"), (float("inf"), "LARGE"))

# ---------------------------------------------------------------------------
# STAKING. Lives HERE, not in the publisher, so the card can print the number
# it is telling you to bet. The publisher reads `stake_pct` off the card CSV
# exactly as it already does for wind — one definition, one source of truth.
#
# Validated out-of-sample (walk-forward, calibrate on prior seasons only):
#   flat 1u                     601 bets  601u staked  +23.66u   +3.94%
#   Kelly x1, cap 2, no skip    601 bets  220u staked  +20.98u   +9.52%
#   Kelly x2, cap 4, skip 0.25  463 bets  424u staked  +41.08u   +9.68%
#
# The cap must move WITH the scale: at x2.7 with the cap left at 2, ROI fell to
# +7.58%, because the cap flattens exactly the big-edge bets sizing exists to
# find. Bets under MIN_UNITS are SKIPPED, not floored — a 0.5u floor tested
# out-of-sample added 132u of risk for -0.34u of profit.
# ---------------------------------------------------------------------------
UNIT_PCT = 0.01          # 1 unit = 1% of bankroll. No unit bump (2026 paper-track).
REF_KELLY = 0.0911       # wind's reference bet: lead 3, threshold 11, -110
STAKE_SCALE = 2.0
MAX_UNITS = 4.0          # must be >= 2 * STAKE_SCALE
MIN_UNITS = 0.25         # below this the bet is skipped entirely


def stake_units(model_prob: float, price: float) -> float:
    """
    Units to stake on one opener bet. Returns 0.0 when the bet is too small to
    want, which the caller must treat as "do not bet", not as "bet nothing".
    """
    b = (price / 100.0) if price > 0 else (100.0 / -price)
    if b <= 0:
        return 0.0
    kelly = max(0.0, (b * model_prob - (1 - model_prob)) / b)
    units = min(kelly / REF_KELLY * STAKE_SCALE, MAX_UNITS)
    return round(units, 3) if units >= MIN_UNITS else 0.0


def american_to_prob(px: float) -> float:
    return 100.0 / (px + 100.0) if px > 0 else -px / (-px + 100.0)


def model_prob_for_dev(dev: float) -> float:
    """
    P(win) for a bet taken at |dev| points off Pinnacle. Linear between the
    tabulated knots, clamped at both ends: below 1.0 nothing qualifies, and
    above 8.0 the table is already far outside the sample that fitted it.
    """
    d = abs(float(dev))
    keys = sorted(DEV_WIN_PROB)
    if d <= keys[0]:
        return DEV_WIN_PROB[keys[0]]
    if d >= keys[-1]:
        return DEV_WIN_PROB[keys[-1]]
    for lo, hi in zip(keys, keys[1:]):
        if lo <= d <= hi:
            w = (d - lo) / (hi - lo)
            return DEV_WIN_PROB[lo] + w * (DEV_WIN_PROB[hi] - DEV_WIN_PROB[lo])
    return POOLED_MODEL_PROB


def edge_tier(edge: float) -> str:
    """SMALL / MEDIUM / LARGE for an edge expressed as a probability fraction."""
    pp = float(edge) * 100.0
    for bound, label in EDGE_TIERS:
        if pp < bound:
            return label
    return EDGE_TIERS[-1][1]


def held_minutes(prior, home: str, away: str, book: str, point: float,
                 now) -> float | None:
    """
    How long `book` has been quoting `point` as the HOME spread on this game,
    in minutes, from earlier observations. See FRESH_MINUTES for why.

    `prior` is a long frame of observations: observed_at (UTC), home, away,
    book, point. Any source will do -- the card unions its own minute-level
    board dumps with the Supabase archive -- and the observations need not be
    evenly spaced: what is measured is the time since the book was last seen
    at a DIFFERENT point.

    Returns None when the book has never been seen at this point (no history
    for it at all, or only at other numbers), 0.0 when it has but was last
    seen elsewhere (the number is brand new), otherwise minutes since the
    first observation of the current run at this point. None reads as "age
    unknown" on the pick and 0.0 as "NEW 0m"; nothing is decided on either.
    """
    if prior is None or len(prior) == 0:
        return None
    now = pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    obs = prior[(prior.home == home) & (prior.away == away) & (prior.book == book)]
    if obs.empty:
        return None
    at = pd.to_datetime(obs.observed_at, utc=True, format="mixed", errors="coerce")
    pts = pd.to_numeric(obs.point, errors="coerce")
    keep = at.notna() & pts.notna() & (at <= now)
    if not keep.any():
        return None
    # Series, not .values: a tz-aware column dropped to numpy loses its zone
    # and the subtraction below raises against a tz-aware `now`.
    run = (pd.DataFrame({"at": at[keep].reset_index(drop=True),
                         "pt": pts[keep].reset_index(drop=True)})
           .sort_values("at").reset_index(drop=True))
    same = ((run.pt - float(point)).abs() < 1e-9).tolist()
    if not any(same):
        return None
    last_diff = max((i for i, s in enumerate(same) if not s), default=-1)
    start = last_diff + 1
    if start >= len(run):
        return 0.0            # last seen at another number: this one is new
    since = run.at[start, "at"]
    return float((now - since).total_seconds() / 60.0)


def age_tag(held_min) -> str:
    """The words a pick carries for the age of its number.

    "NEW 3m" under FRESH_MINUTES (a possible book error: move fast, and record
    whether it was placeable), "age unknown" when there is no history, "up 5h"
    otherwise. One function, because the pick label, the printed card and the
    audit-trail reason must all say the same thing.
    """
    if held_min is None or (isinstance(held_min, float) and held_min != held_min):
        return "age unknown"
    m = float(held_min)
    if m < FRESH_MINUTES:
        return f"NEW {m:.0f}m"
    if m < 48 * 60:
        return f"up {m / 60:.0f}h"
    return f"up {m / 1440:.0f}d"


def clean_board(frame: pd.DataFrame) -> pd.DataFrame:
    """The spreads rows this rule is allowed to look at.

    ONE function, called by both the selection and the evaluation, because the
    two must agree about what is on the board. If `evaluate_board` counted a
    book the selection cannot bet, the pick history would record "qualifies"
    for bets that never appear — a discrepancy with no error attached, which
    is the shape §7 keeps warning about.

    Pinnacle is kept regardless of the bettable list: it is the REFERENCE the
    deviation is measured from, never a side to take. Filtering it out here
    would leave the rule with nothing to compare against and silently return
    an empty card.
    """
    if frame.empty:
        return frame
    keep = _bettable_books() | {REFERENCE}
    return frame[(frame.market == "spreads")
                 & (~frame.book.isin(DEFECTIVE_BOOKS | EXCHANGES))
                 & (frame.book.isin(keep))].copy()


def select_opener_bets(frame: pd.DataFrame, sched: pd.DataFrame,
                       threshold: float = DEPLOY_THRESHOLD,
                       prior: pd.DataFrame | None = None, now=None) -> pd.DataFrame:
    """
    Pure selection: long snapshot frame (snapshot_to_frame shape: one row per
    event x book x market x side with home/away sides, price, point) + the
    window schedule -> one bet row per qualifying game.

    Mirrors backtest_opener's "first" variant at this snapshot: qualifying
    books ranked by |dev| descending, top one taken per game.

    `prior` is the observation history `held_minutes` reads; with it every bet
    carries `held_min` (minutes the book has shown this number, None when
    unknown). Without it (the backtest and replay path) `held_min` is None.
    The age never changes WHICH bet is taken -- see FRESH_MINUTES.
    """
    sp = clean_board(frame)
    if sp.empty:
        return pd.DataFrame()
    if now is None:
        now = pd.Timestamp.now(tz="UTC")

    home = sp[sp.side == "home"][["event_id", "home", "away", "book", "price", "point"]]
    away = sp[sp.side == "away"][["event_id", "book", "price"]].rename(
        columns={"price": "px_away"})
    piv = home.rename(columns={"price": "px_home"}).merge(
        away, on=["event_id", "book"], how="inner")

    pin = (piv[piv.book == REFERENCE]
           .groupby(["home", "away"], as_index=False)
           .point.median().rename(columns={"point": "pin_home_line"}))
    if pin.empty:
        return pd.DataFrame()  # Pinnacle not live yet — nothing is decidable

    soft = piv[piv.book != REFERENCE].merge(pin, on=["home", "away"], how="inner")
    soft["dev"] = soft.point - soft.pin_home_line
    soft = soft[soft.dev.abs() >= threshold]
    if soft.empty:
        return pd.DataFrame()

    rows = []
    for r in soft.sort_values("dev", key=lambda s: s.abs(), ascending=False).itertuples():
        game = sched[(sched.home_team == r.home) & (sched.away_team == r.away)]
        if game.empty:
            continue
        game = game.iloc[0]
        bet_home = r.dev > 0            # soft gives home more points than the sharp line
        price = r.px_home if bet_home else r.px_away
        if pd.isna(price):
            continue
        held = None
        if prior is not None:
            held = held_minutes(prior, r.home, r.away, r.book, float(r.point), now)
        side_line = r.point if bet_home else -r.point
        market_prob = american_to_prob(float(price))
        model_prob = model_prob_for_dev(r.dev)
        edge = model_prob - float(market_prob)
        units = stake_units(model_prob, int(price))
        if units <= 0:
            # Too small to want. Skipped rather than floored: the bets that
            # size tiny are the ones carrying almost no edge, and as a group
            # they lose money. The game is simply not locked yet, so a later
            # tick can still take it if the deviation grows.
            continue
        rows.append({
            "game_id": game.game_id,
            "matchup": game.matchup,
            "kick_utc": str(game.kick_utc),
            "lead_days": round(float(game.lead_days), 2),
            "side": "home" if bet_home else "away",
            "bet_team": r.home if bet_home else r.away,
            "book": r.book,
            "price": int(price),
            "side_line": float(side_line),
            "soft_home_line": float(r.point),
            "pin_home_line": float(r.pin_home_line),
            "dev": round(float(r.dev), 2),
            "model_prob": round(model_prob, 4),
            "market_prob": round(float(market_prob), 4),
            "edge": round(edge, 4),
            "edge_pp": round(edge * 100, 2),
            "edge_tier": edge_tier(edge),
            "units": units,
            "stake_pct": round(units * UNIT_PCT * 100, 3),
            "held_min": None if held is None else round(held, 1),
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # One bet per game, largest |dev| first (the "first" variant's tie-break).
    return (out.sort_values("dev", key=lambda s: s.abs(), ascending=False)
            .groupby("game_id", as_index=False).first())


def evaluate_board(frame: pd.DataFrame, sched: pd.DataFrame,
                   threshold: float = DEPLOY_THRESHOLD,
                   prior: pd.DataFrame | None = None, now=None) -> list[dict]:
    """
    Model's current view of EVERY scheduled game on the board, qualifying or
    not. Feeds the locked-pick history; it never selects anything.

    The distinction that matters here is between "no Pinnacle number yet" and
    "Pinnacle is up and the soft books agree with it". The first is the model
    waiting; the second is the model declining. A locked pick that reads
    "deviation gone" is a bet the market has since corrected — expected, and
    exactly what this is for.

    Given `prior`, a qualifying row's reason also says how long the soft book
    has shown its number, so the audit trail reads the same age the pick does.
    """
    from data_ingest.pick_eval import eval_row

    sp = clean_board(frame)
    if now is None:
        now = pd.Timestamp.now(tz="UTC")

    out: list[dict] = []
    for g in sched.itertuples():
        lead_h = getattr(g, "lead_days", None)
        lead_h = None if lead_h is None else float(lead_h) * 24.0
        common = dict(game_id=g.game_id, model_id="nfl_opener_spread",
                      kick_utc=g.kick_utc, lead_hours=lead_h)

        rows = sp[(sp.home == g.home_team) & (sp.away == g.away_team)]
        if rows.empty:
            out.append(eval_row(qualifies=False, reason="no spread quotes on the board",
                                **common))
            continue

        pin = rows[(rows.book == REFERENCE) & (rows.side == "home")]
        if pin.empty:
            out.append(eval_row(qualifies=False,
                                reason="waiting on Pinnacle (posts ~T-6.5 days)",
                                **common))
            continue
        pin_line = float(pin.point.median())

        soft = rows[(rows.book != REFERENCE) & (rows.side == "home")].copy()
        if soft.empty:
            out.append(eval_row(qualifies=False, reason="no clean soft book quoting",
                                current_line=pin_line, **common))
            continue
        soft["dev"] = soft.point - pin_line
        soft = soft.iloc[soft.dev.abs().values.argsort()[::-1]]   # largest first
        best = soft.iloc[0]
        dev = float(best.dev)

        if abs(dev) < threshold:
            out.append(eval_row(
                qualifies=False,
                reason=f"deviation {dev:+.2f} below the {threshold} pt threshold",
                current_line=float(best.point), current_book=best.book,
                current_price=int(best.price), **common))
            continue

        age = ""
        if prior is not None:
            held = held_minutes(prior, g.home_team, g.away_team, best.book,
                                float(best.point), now)
            age = " · " + age_tag(held)

        prob = model_prob_for_dev(dev)
        edge = prob - american_to_prob(float(best.price))
        out.append(eval_row(
            qualifies=edge > 0,
            reason=(f"deviation {dev:+.2f} pts vs Pinnacle {pin_line:+.1f}{age}"
                    if edge > 0 else
                    f"deviation {dev:+.2f} pts but the juice eats it ({edge*100:+.2f}pp)"),
            current_line=float(best.point), current_book=best.book,
            current_price=int(best.price), model_prob=round(prob, 4),
            edge=round(edge, 4), **common))
    return out

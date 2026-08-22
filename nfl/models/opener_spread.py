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

EVIDENCE (scripts/backtest_opener.py, 2023-2025, 853 games, 29 clean books)
--------------------------------------------------------------------------
Restated 2026-08-22 after two method fixes in the backtest: a deterministic
tie-break in the first-qualifying selection, and a benchmark that had been
applying the large-residual side's formula to BOTH sides.

  |dev| >= 1.0 : n=593, ATS 58.18% against 53.07% expected from the number
  bought alone, so +5.11pp excess [95% CI +1.1, +8.9]; ROI +6.82% at actually
  quoted juice [-0.6, +14.3], mean price -125.

  Previously published as +5.78pp and +6.98%. The selection and the win rate
  did not move; only the benchmark and one tie-broken price did.

  Placebo with DraftKings as the reference gives +0.98pp [-2.9, +4.9] — the
  effect is specific to Pinnacle, which is the test that matters.

WHAT DID NOT SURVIVE
--------------------
Totals and moneyline were scanned densely across 2023-2025 on the same
6-hourly grid and both are NULL; the totals placebo matches the totals signal
at every threshold. Spreads only.

LIVE RISK, AND IT IS NOT SMALL
------------------------------
Season ROI: 2023 +4.75%, 2024 +14.31%, 2025 +1.05%. Roughly 70% of three
seasons of profit is 2024, and the most recent season is barely above zero at a
mean quoted price of -125. Either the edge is decaying as early-week pricing
tightens, or 2024 was a high draw. Paper-first, and watch the track.
"""

from __future__ import annotations

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

DEPLOY_THRESHOLD = 1.0   # |soft_home_line - pinnacle_home_line|, points
LEAD_LO_DAYS = 2.0       # the validated window: T-7 to T-2
LEAD_HI_DAYS = 7.0

# Pooled validated ATS at the deployment threshold. Kept for reference and as
# the fallback: this is what the card used for EVERY bet until 2026-08-22.
POOLED_MODEL_PROB = 0.5818

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
# 2. WHAT THE SHRUNK NUMBER IS WORTH, from the empirical margin-versus-close
#    residual distribution (n=7,276, 1999-2025). That distribution carries the
#    key-number atoms, which is why this table has flat stretches rather than a
#    smooth curve. Plus the measured +5.11pp Pinnacle-direction excess.
#
# Sanity check on the whole construction: applied to the 593 backtested bets it
# gives a pooled 58.35% against a realised 58.18%. The average is preserved and
# only the distribution across deviation sizes moves, which is the point.
#
# Minimum modelled probability is 0.5754 at |dev| 1.0, above the min_prob 0.55
# gate in config.py, so this change gates nothing out on its own.
# ---------------------------------------------------------------------------
DEV_WIN_PROB = {
    1.0: 0.5754, 1.5: 0.5754, 2.0: 0.5927, 2.5: 0.6090, 3.0: 0.6271,
    3.5: 0.6400, 4.0: 0.6543, 4.5: 0.6692, 5.0: 0.6881, 5.5: 0.6995,
    6.0: 0.7259, 6.5: 0.7465, 7.0: 0.7595, 7.5: 0.7803, 8.0: 0.7924,
}

# Descriptive labels for the card and the alert, in probability points of edge
# over the price actually quoted. These COMMUNICATE the size of the predicted
# edge; they do not select. Boundaries sit near the quartiles of the backtested
# edge distribution (p25 +3.0pp, p75 +5.2pp).
EDGE_TIERS = ((3.0, "SMALL"), (5.5, "MEDIUM"), (float("inf"), "LARGE"))


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


def select_opener_bets(frame: pd.DataFrame, sched: pd.DataFrame,
                       threshold: float = DEPLOY_THRESHOLD) -> pd.DataFrame:
    """
    Pure selection: long snapshot frame (snapshot_to_frame shape: one row per
    event x book x market x side with home/away sides, price, point) + the
    window schedule -> one bet row per qualifying game.

    Mirrors backtest_opener's "first" variant at this snapshot: qualifying
    books ranked by |dev| descending, top one taken per game.
    """
    sp = frame[(frame.market == "spreads")
               & (~frame.book.isin(DEFECTIVE_BOOKS | EXCHANGES))].copy()
    if sp.empty:
        return pd.DataFrame()

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
        side_line = r.point if bet_home else -r.point
        market_prob = american_to_prob(float(price))
        model_prob = model_prob_for_dev(r.dev)
        edge = model_prob - float(market_prob)
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
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # One bet per game, largest |dev| first (the "first" variant's tie-break).
    return (out.sort_values("dev", key=lambda s: s.abs(), ascending=False)
            .groupby("game_id", as_index=False).first())

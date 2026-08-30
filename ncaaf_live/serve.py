"""
Serve the trained NCAAF live engine: ESPN state -> features -> lane decisions.

THE LICENSES ARE CODE HERE, NOT ADVICE. The 2025 calibration gates passed win
probability outright (Brier 0.115 vs 0.20) and failed total-distribution
shape at 2.60pp vs 2.0 - with the failure localised to tails and the endgame
while the median and early/mid-game states are calibrated (q0.50 -0.04pp,
pregame bucket 1.78pp, buckets 4-5 ~2.85pp, final two minutes 8.84pp). So:

  * MONEYLINE lane: licensed through regulation (gate 1).
  * MAIN TOTAL lane: licensed only with >= TOTAL_MIN_SECONDS of regulation
    left (the region where coverage held), priced at the market's main line
    (median-region CDF), never alternates.
  * OVERTIME: declined entirely - CFB OT is alternating untimed possessions
    and the engine has no distribution for it.
  * Alt lines / team totals / quarters / final-two-minute anything: OFF.

EDGE FLOORS ARE PLACEHOLDERS AND SAY SO. No historical in-play NCAAF edge has
been measured (that is the phase-3 snapshot harness). Week 1 output is a
CALIBRATION SET at minimum size; the floors are set high on purpose so the
loop is quiet rather than busy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import (ARTIFACT_DIR, LEAGUE_PASS_RATE, LIVE_QUOTE_MAX_AGE_SEC,
                     PASS_RATE_PRIOR_PLAYS)
from .engine.distribution import ScoreDistribution
from .engine.pricing import (
    american_to_prob, price_moneyline, total_pmf)
from .engine.remaining import load_models, predict_remaining

log = logging.getLogger(__name__)

# ── lane licenses (from the calibration gates - see module docstring) ────────
TOTAL_MIN_SECONDS = 900          # totals only in buckets 4+ (coverage <= 2.85pp)
MAX_PERIOD = 4                   # never price overtime

# ── placeholder floors, deliberately high (week-1 calibration set) ───────────
TOTAL_MIN_PROB = 0.62
# 0.08 -> 0.12 (2026-08-29, mike). NCAAF live totals are the most volatile
# market this platform prices: measured across one Saturday slate, the line
# moved 2-8 POINTS within ten minutes of a pick, against 0-2 runs for MLB. A
# live pick locks at first signal and is never re-priced, so a number that was
# current when posted can be several points off minutes later. A higher floor
# does not slow the market down; it means fewer, higher-conviction bets are
# exposed to it.
TOTAL_MIN_EDGE = 0.12
ML_MIN_PROB = 0.58
ML_MIN_EDGE = 0.10
# THE EDGE IS A BAND, NOT A FLOOR, AND THE UPPER BOUND IS THE MORE IMPORTANT
# HALF. An edge this large against a LIVE line almost always means the snapshot
# is stale across a score (books suspend during plays) - the classic in-play way
# to lose. Declined loudly, never bet.
#
# 0.25 -> 0.18 (2026-08-29, mike). On the slate that produced the bad Florida
# State pick, the two largest edges were also the two worst immediate line
# moves: 16.5% edge -> the book re-hung 8 points inside two minutes; 14.8% edge
# -> the market went dark before it could be re-measured. The four picks at
# 8.5-9.3% drifted 0-2 points over the same window. Size of disagreement with a
# live book is evidence about OUR snapshot, not about value.
#
# This is still a PROXY for staleness. `market_is_takeable` measures it directly
# off the book's own publish clock and is the real defence; the cap catches what
# a timestamp cannot - a number the book republished but has not yet moved.
MAX_EDGE_CAP = 0.18
KELLY_MULTIPLIER = 0.10          # platform tenth-Kelly
MAX_KELLY_FRACTION = 0.05


def quote_age_seconds(ts, now: datetime | None = None) -> float | None:
    """How long ago DraftKings last published this market, in seconds.

    None means we cannot tell - no timestamp, or one we could not parse. Every
    caller treats that as fresh, deliberately: a feed shape change must not
    silently blank the board. It is logged instead, so the blindness is visible.
    """
    if not isinstance(ts, str):
        return None
    try:
        pub = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - pub).total_seconds()


def market_is_takeable(market: dict | None, label: str, game_id: str,
                       now: datetime | None = None) -> bool:
    """Is this the price a bettor could actually get right now?

    THE FAILURE THIS EXISTS FOR, measured on 2026-08-29. New Mexico State at
    Florida State: DraftKings' live total sat unchanged at 46.5 for four and a
    half minutes of running clock while the loop polled it every five seconds.
    We priced against it, posted Over 46.5 at -120, and 49 seconds later the
    book re-hung at 51.5 and then 54.5. End to end our pipeline took 1.3
    seconds - it was never slow. It was pricing a number the book had stopped
    offering, and nothing in the loop could see that, because the only
    freshness measure was OUR fetch clock.

    A book freezing a market is not a bug in the feed, it is the book taking
    the line down - usually across a score, a review, or the half. Its own
    last_update is the one field that distinguishes "confirming 46.5 every
    twenty seconds" from "froze at 46.5 four minutes ago", and it is free in
    the payload we already pay for.
    """
    if not market:
        return False
    age = quote_age_seconds(market.get("ts"), now)
    if age is None:
        log.debug("%s: %s quote carries no book timestamp - treating as fresh",
                  game_id, label)
        return True
    if age > LIVE_QUOTE_MAX_AGE_SEC:
        log.info("%s: %s quote is %.0fs old at the book (> %ds) - declining; "
                 "a frozen market is one the book is about to re-hang",
                 game_id, label, age, LIVE_QUOTE_MAX_AGE_SEC)
        return False
    return True


@dataclass
class GameContext:
    """Pregame facts from the platform DB, fetched once per gameday."""
    game_id: str
    home: str
    away: str
    commence_time: str | None
    pregame_spread: float | None      # home-relative, negative = home laying
    pregame_total: float | None
    wind_mph: float | None
    is_dome: bool
    game_date: str = ""


class LiveEngine:
    def __init__(self):
        self.models = load_models(ARTIFACT_DIR)
        self.dist = ScoreDistribution.load(ARTIFACT_DIR / "score_distribution.npz")

    # ---------------------------------------------------------------- state
    def feature_row(self, state: dict, ctx: GameContext) -> pd.DataFrame:
        """
        One feature row in the EXACT schema the historical states builder
        emits (state parity: ncaaf_live/backtest/states.py is the contract).
        Missing live fields become NaN - LightGBM routes NaN natively, which
        is the correct degradation.
        """
        period = state["period"]
        clock = float(state["clock_seconds"])
        secs = clock + max(0, 4 - period) * 900
        half_secs = (clock + max(0, 2 - period) * 900 if period <= 2
                     else (clock + max(0, 4 - period) * 900 if period <= 4
                           else 0.0))

        def _sm_rate(passes, plays):
            prior = LEAGUE_PASS_RATE * PASS_RATE_PRIOR_PLAYS
            return (passes + prior) / (plays + PASS_RATE_PRIOR_PLAYS)

        poss = state.get("possession")
        row = {
            "period": float(period),
            "clock_in_period": clock,
            "seconds_remaining": secs,
            "half_seconds_remaining": half_secs,
            "home_score": float(state["home_score"]),
            "away_score": float(state["away_score"]),
            "pregame_spread": (np.nan if ctx.pregame_spread is None
                               else float(ctx.pregame_spread)),
            "pregame_total": (np.nan if ctx.pregame_total is None
                              else float(ctx.pregame_total)),
            "has_ball_home": (1.0 if poss == "home"
                              else (0.0 if poss == "away" else np.nan)),
            "down": (np.nan if state.get("down") is None
                     else float(state["down"])),
            "distance": (np.nan if state.get("distance") is None
                         else float(state["distance"])),
            "yardline_100": (np.nan if state.get("yardline_100") is None
                             else float(state["yardline_100"])),
            "home_timeouts": float(state.get("home_timeouts") or 3),
            "away_timeouts": float(state.get("away_timeouts") or 3),
            # A MISSING drive log (the CFBD scoreboard source) must become
            # NaN, never 0 - "zero plays run mid-game" is a wrong value the
            # trees would believe, while NaN routes to the learned default.
            "plays_run": (np.nan if state.get("plays_run") is None
                          else float(state["plays_run"])),
            "home_pass_rate": _sm_rate(state.get("home_pass_plays") or 0,
                                       state.get("home_plays") or 0),
            "away_pass_rate": _sm_rate(state.get("away_pass_plays") or 0,
                                       state.get("away_plays") or 0),
            "wind_mph": (np.nan if ctx.wind_mph is None
                         else float(ctx.wind_mph)),
            "is_dome": bool(ctx.is_dome),
        }
        return pd.DataFrame([row])

    # ---------------------------------------------------------------- price
    def price(self, state: dict, ctx: GameContext, odds: dict | None,
              now: datetime | None = None) -> list[dict]:
        """
        Lane decisions for one live game. Returns pick dicts (BET/AVOID only)
        ready for models.scorer._insert_picks; empty on every declined
        condition, never a degraded pick.
        """
        period = state["period"]
        if period > MAX_PERIOD:
            return []                                   # OT: declined
        if ctx.pregame_total is None or ctx.pregame_spread is None:
            log.info("%s: no pregame line context - not pricing", ctx.game_id)
            return []

        row = self.feature_row(state, ctx)
        preds = predict_remaining(self.models, row)
        mu_h = float(preds["home_remaining_hat"].iloc[0])
        mu_a = float(preds["away_remaining_hat"].iloc[0])
        secs = float(row["seconds_remaining"].iloc[0])
        hs, as_ = int(state["home_score"]), int(state["away_score"])
        out = self.dist.final_score_pmf(mu_h, mu_a, secs, hs, as_)

        picks: list[dict] = []
        base = {
            "game_id": ctx.game_id, "sport": "NCAAF",
            "game_date": ctx.game_date, "game_time": ctx.commence_time,
            "bankroll_at_pick": 1000.0,
            "injury_flag": None, "injury_detail": None,
            "is_live": True,
            "inning_at_pick": period,           # the period, in the shared column
            "score_diff_at_pick": hs - as_,
        }

        # ── moneyline lane (gate-1 licensed) ────────────────────────────────
        ml = (odds or {}).get("h2h")
        if not market_is_takeable(ml, "h2h", ctx.game_id, now):
            ml = None
        if ml and ml.get("home") is not None and ml.get("away") is not None:
            wp = price_moneyline(out)
            for side, label_team in (("home", ctx.home), ("away", ctx.away)):
                p = float(wp[side])
                price = float(ml[side])
                implied = american_to_prob(price)
                edge = p - implied
                pick = self._decide(p, edge, ML_MIN_PROB, ML_MIN_EDGE)
                if pick:
                    picks.append({**base,
                        "model_id": "ncaaf_live_win_prob",
                        "pick_side": side,
                        "pick_label": f"{label_team} ML (live)",
                        "model_probability": round(p, 4),
                        "dk_implied_prob": round(implied, 4),
                        "edge": round(edge, 4), "dk_odds": price,
                        "scored_line": None, "signal_type": pick,
                        **self._kelly(p, implied, pick)})

        # ── main-total lane (median-region license only) ────────────────────
        tot = (odds or {}).get("total")
        if not market_is_takeable(tot, "totals", ctx.game_id, now):
            tot = None
        if tot and secs >= TOTAL_MIN_SECONDS:
            line = float(tot["line"])
            values, probs = total_pmf(out["joint_remaining"], hs + as_)
            p_over = float(probs[values > line].sum())
            p_under = float(probs[values < line].sum())
            for side, p, price in (("over", p_over, tot.get("over")),
                                   ("under", p_under, tot.get("under"))):
                if price is None:
                    continue
                implied = american_to_prob(float(price))
                edge = p - implied
                pick = self._decide(p, edge, TOTAL_MIN_PROB, TOTAL_MIN_EDGE)
                if pick:
                    picks.append({**base,
                        "model_id": "ncaaf_live_total",
                        "pick_side": side,
                        "pick_label": f"{ctx.away} @ {ctx.home} "
                                      f"{side.capitalize()} {line:g} (live)",
                        "model_probability": round(p, 4),
                        "dk_implied_prob": round(implied, 4),
                        "edge": round(edge, 4), "dk_odds": float(price),
                        "scored_line": line, "signal_type": pick,
                        **self._kelly(p, implied, pick)})
        elif tot and secs < TOTAL_MIN_SECONDS:
            log.debug("%s: totals lane closed (%.0fs left < %s)",
                      ctx.game_id, secs, TOTAL_MIN_SECONDS)
        return picks

    @staticmethod
    def _decide(p: float, edge: float, min_prob: float,
                min_edge: float) -> str | None:
        if abs(edge) > MAX_EDGE_CAP:
            log.warning("edge %+0.3f exceeds the stale-line cap %.2f - "
                        "declining (suspended/stale price is the likely cause)",
                        edge, MAX_EDGE_CAP)
            return None
        if p >= min_prob and edge >= min_edge:
            return "BET"
        if edge <= -min_edge and (1 - p) >= min_prob:
            return "AVOID"
        return None

    @staticmethod
    def _kelly(p: float, implied: float, signal: str) -> dict:
        if signal != "BET" or implied >= 1.0:
            return {"kelly_fraction": 0.0, "recommended_bet": 0.0,
                    "confidence_tier": "LOW"}
        f = KELLY_MULTIPLIER * (p - implied) / (1 - implied)
        f = min(max(f, 0.0), MAX_KELLY_FRACTION)
        tier = "HIGH" if f >= 0.03 else ("MED" if f >= 0.015 else "LOW")
        return {"kelly_fraction": round(f, 6),
                "recommended_bet": round(f * 1000.0, 2),
                "confidence_tier": tier}

"""
Turn model prices and live quotes into decisions.

Three responsibilities, in this order and no other:

  1. REFUSE. Staleness guards, credit guards, exposure guards, inactive
     players, degenerate states. Most of this file is refusal, which is the
     correct shape for a live betting component.
  2. Price the edge and size the stake.
  3. Record the decision, bet or pass, BEFORE anything is alerted. A decision
     that was not written did not happen, and an alert that fired without a
     record cannot be audited afterwards.

EVERY PASS IS RECORDED, not just every bet. Without the passes there is no way
to tell later whether a lane produced no bets because there was no edge or
because a guard was silently eating every candidate. That distinction is the
difference between "the lane is dead" and "the poller has been broken since
week 3", and it is not recoverable after the fact.
"""

from __future__ import annotations

import importlib
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    DERIV_LAG_RATIO, EV_THRESHOLDS, KELLY_FRACTION, KELLY_HAIRCUT,
    MAX_DAILY_EXPOSURE_FRACTION, MAX_QUOTE_AGE_SEC, MAX_STAKE_FRACTION,
    MAX_STATE_AGE_SEC, MIN_PRICE, MIN_SECONDS_FOR_PRICING, SCRIPT_LEAD_TRIGGER,
)
from .engine.pricing import american_to_decimal, american_to_prob
from .state import GameState

log = logging.getLogger(__name__)


def _platform_guard():
    """The shared pre-score staleness guard, imported LAZILY and optionally.

    Three constraints collide here and this is the only shape that satisfies
    all of them:

      * the NFL worker runs with cwd=nfl/, where the repo root is not on
        sys.path until something puts it there (same reason
        workers/gameday.py bootstraps before importing the price log);
      * `nfl/` carries its own `models/` and `data/` directories, so a bare
        top-level import of either resolves to the wrong thing -- which is why
        the guard lives at `data/live_quote_guard.py` and is reached only
        after the root insert;
      * `nfl/` must keep running with no platform present at all.

    So: bootstrap, import, and on failure return None ONCE with a warning. A
    missing platform degrades this lane to the age bound it had before, which
    is the previous behaviour rather than a new failure mode.
    """
    global _GUARD
    if _GUARD is not _UNTRIED:
        return _GUARD
    try:
        root = str(Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
        _GUARD = importlib.import_module("data.live_quote_guard")
    except Exception as exc:                                # noqa: BLE001
        log.warning("pre-score quote guard unavailable (%s) - falling back to "
                    "the age bound alone", exc)
        _GUARD = None
    return _GUARD


_UNTRIED = object()
_GUARD = _UNTRIED


@dataclass
class Decision:
    """One evaluated candidate. `bet` False means we looked and declined."""
    ts: datetime
    game_id: str
    model_id: str
    market: str
    bookmaker: str
    side: str
    line: float | None
    price: float
    model_prob: float
    market_prob: float
    ev: float
    bet: bool
    reason: str
    stake_fraction: float = 0.0
    player: str | None = None
    state_ref: datetime | None = None
    quote_ref: datetime | None = None
    context: dict = field(default_factory=dict)

    def to_row(self) -> dict:
        return {
            "ts": self.ts.isoformat(),
            "game_id": self.game_id,
            "model_id": self.model_id,
            "market": self.market,
            "bookmaker": self.bookmaker,
            "side": self.side,
            "line": self.line,
            "price": self.price,
            "model_prob": self.model_prob,
            "market_prob": self.market_prob,
            "ev": self.ev,
            "bet": self.bet,
            "reason": self.reason,
            "stake_fraction": self.stake_fraction,
            "player": self.player,
            "state_ref": self.state_ref.isoformat() if self.state_ref else None,
            "quote_ref": self.quote_ref.isoformat() if self.quote_ref else None,
            "context": self.context,
        }


# --------------------------------------------------------------------- edge
def expected_value(model_prob: float, american_price: float) -> float:
    """
    EV per unit staked. `model_prob * decimal - 1`.

    Note this is EV on the QUOTED price, not on a devigged fair price. Devig is
    for deciding what is true; EV is for deciding whether the number in front
    of us pays for that truth.
    """
    if not (0.0 < model_prob < 1.0):
        return float("-inf")
    return float(model_prob * american_to_decimal(american_price) - 1.0)


def kelly_stake(model_prob: float, american_price: float) -> float:
    """
    Fraction of bankroll, quarter Kelly with a further haircut and a hard cap.

    The haircut on top of quarter Kelly is not timidity, it is the honest
    response to where the model's numbers come from: a backtest built on
    5-minute snapshots overstates any latency-sensitive edge, so the stake
    should be smaller than the same edge would justify pregame.
    """
    d = american_to_decimal(american_price)
    b = d - 1.0
    if b <= 0 or not (0.0 < model_prob < 1.0):
        return 0.0
    full = (model_prob * b - (1.0 - model_prob)) / b
    if full <= 0:
        return 0.0
    return float(min(full * KELLY_FRACTION * KELLY_HAIRCUT, MAX_STAKE_FRACTION))


# ------------------------------------------------------------------- guards
def state_is_priceable(state: GameState, now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.now(timezone.utc)
    age = (now - state.ts).total_seconds()
    if age > MAX_STATE_AGE_SEC:
        return False, f"stale_state:{age:.0f}s"
    if state.period > 4:
        return False, "overtime_not_modelled"
    if state.seconds_remaining < MIN_SECONDS_FOR_PRICING and not state.is_halftime:
        return False, "too_little_time"
    return True, ""


def quote_is_fresh(quote, now: datetime | None = None,
                   score_seen_at: datetime | None = None) -> tuple[bool, str]:
    """Age is necessary and not sufficient — see models/live_quote_guard.py.

    NCAAF shipped a live total on 2026-09-03 that was 62.2s old against this
    same 90s bound and already extinct: a touchdown had landed 0.6s earlier and
    DraftKings had not re-hung. Football is where this bites hardest, because a
    touchdown moves a full-game total ~6 points in one step, so the NFL lane
    gets the guard BEFORE its season rather than after its own incident
    (CLAUDE.md 1b — a change to one model is assessed against all of them).

    `score_seen_at` is None until a game's score changes, which leaves the age
    bound as the only defence, exactly as before.
    """
    guard = _platform_guard()
    if guard is not None and guard.quote_predates_score(
            getattr(quote, "ts", None), score_seen_at):
        return False, "quote_predates_score"
    age = quote.age_seconds(now)
    if age > MAX_QUOTE_AGE_SEC:
        return False, f"stale_quote:{age:.0f}s"
    return True, ""


# -------------------------------------------------------------- hunt states
def is_hunt_state(state: GameState, *, deriv_lag: float | None = None,
                  script_trigger: bool = False) -> tuple[bool, str]:
    """
    Should this game be paying for derivative and prop polls right now?

    Three ways in, from the build spec: halftime, a derivative quote that has
    failed to keep up with the main line, or a game-script trigger that makes
    the props worth re-pricing.
    """
    if state.is_halftime:
        return True, "halftime"
    if deriv_lag is not None and deriv_lag < DERIV_LAG_RATIO:
        return True, f"deriv_lag:{deriv_lag:.2f}"
    if script_trigger:
        return True, "script_trigger"
    return False, "no_hunt_state"


def script_trigger_fired(state: GameState, pace_z: float | None = None) -> bool:
    """
    A game script change big enough that live props are probably stale.

    Two scores entering the second half is the canonical case: the trailing
    team's pass rate jumps, the leading team's collapses, and every rushing and
    receiving prop in the game is now priced off a script that no longer
    applies.
    """
    if state.period >= 3 and abs(state.score_diff) >= SCRIPT_LEAD_TRIGGER:
        return True
    if pace_z is not None and abs(pace_z) >= 1.5:
        return True
    return False


def derivative_lag(main_move_prob: float, deriv_move_prob: float) -> float:
    """
    How much of the main line's move the derivative has absorbed.

    Below DERIV_LAG_RATIO the derivative has not kept up, which is the entire
    thesis of lane b: the book reprices its main line off the official feed in
    seconds and gets to its second half total when it gets to it.
    """
    if abs(main_move_prob) < 1e-9:
        return 1.0
    return float(abs(deriv_move_prob) / abs(main_move_prob))


# ---------------------------------------------------------------- evaluate
class Executor:
    def __init__(self, bankroll_fraction_used: float = 0.0, recorder=None,
                 alerter=None):
        self.exposure = bankroll_fraction_used
        self.recorder = recorder
        self.alerter = alerter
        self.decisions: list[Decision] = []
        # Fed from `state` inside evaluate(), so no live-loop wiring is needed:
        # GamedayWorker builds ONE Executor at startup (workers/gameday.py:149)
        # and ticks it, so this clock persists across passes. A per-pass
        # Executor would leave every call at first sight and make the guard
        # dead code -- if that construction ever moves, hoist this to module
        # level (the `_WRITTEN` precedent in data/ingestors/live_price_log.py).
        #
        # NOTE _platform_guard() may insert the repo root into sys.path, so
        # constructing an Executor has that side effect -- the same insert
        # workers/gameday.py already performs before its price-log import.
        guard = _platform_guard()
        self._score_clock = guard.ScoreClock() if guard else None

    def evaluate(self, *, state: GameState, quote, model_prob: float,
                 model_id: str, now: datetime | None = None,
                 context: dict | None = None) -> Decision:
        """
        Evaluate one quote against one model price and record the outcome.

        Returns a Decision either way. The caller does not get to skip the
        record by not betting.
        """
        now = now or datetime.now(timezone.utc)
        ctx = dict(context or {})
        # The BOOK's team names ride along on every decision. Quote.home_team
        # explains why they exist at all: "the book's event id and ESPN's event
        # id are unrelated strings, so the only thing the two feeds share is who
        # is playing." `game_id` below is ESPN's, so these names are the ONLY
        # bridge from a decision to the platform's `games` row -- which is what
        # pick_writer.resolve_game_id joins on, and what settlement then needs.
        # Also worth having in the JSONL audit log on its own: a decision log
        # that cannot say who was playing is hard to read back a month later.
        for _k, _v in (("home_team", getattr(quote, "home_team", None)),
                       ("away_team", getattr(quote, "away_team", None))):
            if _v and _k not in ctx:
                ctx[_k] = _v
        market_prob = american_to_prob(quote.price)
        ev = expected_value(model_prob, quote.price)

        def _mk(bet: bool, reason: str, stake: float = 0.0) -> Decision:
            d = Decision(
                ts=now, game_id=state.game_id, model_id=model_id,
                market=quote.market, bookmaker=quote.bookmaker, side=quote.side,
                line=quote.line, price=quote.price, model_prob=model_prob,
                market_prob=market_prob, ev=ev, bet=bet, reason=reason,
                stake_fraction=stake, player=getattr(quote, "player", None),
                state_ref=state.ts, quote_ref=quote.ts, context=ctx,
            )
            self._record(d)
            return d

        ok, why = state_is_priceable(state, now)
        if not ok:
            return _mk(False, why)
        # OUR clock, not `state.ts`. The feed's generation time is EARLIER
        # than our observation, which would narrow the blocked window -- the
        # unsafe direction, and a silent divergence from NCAAF. The guard's
        # contract is deliberately conservative here; see live_quote_guard.
        score_seen_at = self._score_clock.observe(
            state.game_id, (state.home_score, state.away_score),
            now or datetime.now(timezone.utc)) if self._score_clock else None
        ok, why = quote_is_fresh(quote, now, score_seen_at)
        if not ok:
            return _mk(False, why)
        if model_id not in EV_THRESHOLDS:
            return _mk(False, f"unknown_model:{model_id}")
        if not (0.0 < model_prob < 1.0):
            return _mk(False, "degenerate_model_prob")

        # THE JUICE CEILING, before the EV test (Matt, 2026-09-05: "-140 should
        # be price ceiling"). Deliberately not an edge question: a quote past the
        # ceiling is ineligible however good the number looks, because clearing
        # a 0.06 EV gate at -250 requires a model probability high enough that
        # the model is the thing least worth trusting. A more negative American
        # price is more juice, so the test is `<`; a plus price always passes.
        #
        # Refused rather than filtered downstream: this records a PASS with a
        # reason, so the audit log shows the lane looked and declined. The same
        # number in the display filter would have written the bet and hidden it.
        if quote.price < MIN_PRICE:
            return _mk(False, f"price_past_ceiling:{quote.price:.0f}<{MIN_PRICE:.0f}")

        threshold = EV_THRESHOLDS[model_id]
        if ev < threshold:
            return _mk(False, f"below_threshold:{ev:.4f}<{threshold:.4f}")

        stake = kelly_stake(model_prob, quote.price)
        if stake <= 0:
            return _mk(False, "no_kelly_stake")

        headroom = MAX_DAILY_EXPOSURE_FRACTION - self.exposure
        if headroom <= 0:
            return _mk(False, "daily_exposure_cap")
        if stake > headroom:
            stake = headroom
            ctx["stake_clipped_to_headroom"] = True

        self.exposure += stake
        d = _mk(True, "bet", stake)
        self._alert(d)
        return d

    # ------------------------------------------------------------- plumbing
    def _record(self, d: Decision) -> None:
        """
        Persist first, always, and never let persistence break the loop.

        The hot path must not block on Postgres. The recorder is expected to be
        fire and forget with a local fallback queue; if it raises anyway, the
        decision still stands and the worker keeps running.
        """
        self.decisions.append(d)
        if self.recorder is None:
            return
        try:
            self.recorder(d)
        except Exception:                       # noqa: BLE001
            log.exception("decision recorder failed; continuing")

    def _alert(self, d: Decision) -> None:
        if self.alerter is None:
            return
        try:
            self.alerter(d)
        except Exception:                       # noqa: BLE001
            log.exception("alerter failed; the bet is already recorded")

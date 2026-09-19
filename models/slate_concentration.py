"""
Slate-side concentration guard for game-market cards.

WHY THIS EXISTS
---------------
A game-market rule that fires the same pick_side on every (or nearly every)
game on a slate is not a selective edge — it is a board. 2026-09-19
`mlb_total_public_fade` wrote UNDER BET on 12/12 MLB games because public
OVER tickets were 75–95% everywhere. The user was notified of every under
on the card.

This helper runs AFTER candidate BETs for one model on one slate/day are
built and BEFORE INSERT / notify. It is not a second ticket/edge cut and
it does not retract a pick that already exists (§1c).

TRIGGER
-------
n_bet ≥ MIN_BETS (4) AND one pick_side is ≥ MAX_SHARE (70%) of that
model's BET count on the slate.

POLICY
------
`suppress_all` (default, safer): drop every candidate BET. Nothing is
INSERTed; nothing is notified.
`top_k`: keep the K highest-edge rows (default K=2) and drop the rest.

Callers that only ever produce one side (the public-fade card: always
UNDER) will trip this on any slate of 4+ flags. That is the point.

Docs: docs/mlb_total_public_fade.md (first consumer).
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

MIN_BETS = 4
MAX_SHARE = 0.70
TOP_K = 2
POLICY_SUPPRESS_ALL = "suppress_all"
POLICY_TOP_K = "top_k"


@dataclass(frozen=True)
class SlateConcentration:
    """Counts and the keep/drop decision for one model's slate."""

    n_bet: int
    n_under: int
    n_over: int
    by_side: dict[str, int] = field(default_factory=dict)
    concentrated_side: str | None = None
    share: float = 0.0
    triggered: bool = False
    min_bets: int = MIN_BETS
    max_share: float = MAX_SHARE
    policy: str = POLICY_SUPPRESS_ALL
    kept: int = 0
    suppressed: int = 0

    def warn_message(self, model_id: str | None = None) -> str:
        """WARN text. Always includes n_bet / n_under / n_over / threshold."""
        model = f" model={model_id}" if model_id else ""
        return (
            f"slate concentration guard: suppressed {self.suppressed} BET(s) "
            f"(n_bet={self.n_bet} n_under={self.n_under} n_over={self.n_over} "
            f"threshold={self.max_share:.0%} min_bets={self.min_bets} "
            f"side={self.concentrated_side} share={self.share:.0%} "
            f"policy={self.policy}{model})"
        )


def _attr(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _is_bet(item: Any) -> bool:
    sig = _attr(item, "signal_type")
    if sig is None:
        return True
    return str(sig).upper() == "BET"


def _side_of(item: Any, side_of: Callable[[Any], str] | None,
             side_key: str) -> str:
    if side_of is not None:
        return str(side_of(item) or "").strip().lower()
    raw = _attr(item, side_key)
    if raw is None:
        raw = _attr(item, "side")
    return str(raw or "").strip().lower()


def _edge_of(item: Any, edge_of: Callable[[Any], float | None] | None,
             edge_key: str) -> float:
    if edge_of is not None:
        val = edge_of(item)
    else:
        val = _attr(item, edge_key)
    try:
        return float(val)
    except (TypeError, ValueError):
        return float("-inf")


def measure_side_concentration(
    rows: Sequence[Any],
    *,
    side_of: Callable[[Any], str] | None = None,
    side_key: str = "pick_side",
    min_bets: int = MIN_BETS,
    max_share: float = MAX_SHARE,
) -> SlateConcentration:
    """Count BET sides. `triggered` when one side is ≥ max_share of n ≥ min_bets."""
    bets = [r for r in (rows or []) if _is_bet(r)]
    counts: Counter[str] = Counter()
    for r in bets:
        side = _side_of(r, side_of, side_key)
        if side:
            counts[side] += 1
        else:
            counts[""] += 1
    n_bet = len(bets)
    n_under = int(counts.get("under", 0))
    n_over = int(counts.get("over", 0))
    if n_bet == 0:
        return SlateConcentration(n_bet=0, n_under=0, n_over=0, by_side={})
    concentrated_side, top = counts.most_common(1)[0]
    share = top / n_bet
    triggered = n_bet >= min_bets and share >= max_share
    return SlateConcentration(
        n_bet=n_bet,
        n_under=n_under,
        n_over=n_over,
        by_side=dict(counts),
        concentrated_side=concentrated_side or None,
        share=share,
        triggered=triggered,
        min_bets=min_bets,
        max_share=max_share,
        kept=n_bet,
        suppressed=0,
    )


def apply_slate_concentration_guard(
    rows: Sequence[Any],
    *,
    policy: str = POLICY_SUPPRESS_ALL,
    top_k: int = TOP_K,
    side_of: Callable[[Any], str] | None = None,
    edge_of: Callable[[Any], float | None] | None = None,
    side_key: str = "pick_side",
    edge_key: str = "edge",
    min_bets: int = MIN_BETS,
    max_share: float = MAX_SHARE,
    model_id: str | None = None,
    log: bool = True,
) -> tuple[list[Any], SlateConcentration]:
    """Keep or drop candidate BETs for one slate. Non-BET rows pass through.

    `suppress_all` (default) drops every BET when the slate is concentrated.
    `top_k` keeps the `top_k` highest-edge BETs and drops the rest.
    """
    incoming = list(rows or [])
    measured = measure_side_concentration(
        incoming, side_of=side_of, side_key=side_key,
        min_bets=min_bets, max_share=max_share,
    )
    if not measured.triggered:
        return incoming, measured

    non_bets = [r for r in incoming if not _is_bet(r)]
    bets = [r for r in incoming if _is_bet(r)]
    if policy == POLICY_TOP_K:
        ranked = sorted(
            bets,
            key=lambda r: _edge_of(r, edge_of, edge_key),
            reverse=True,
        )
        k = max(0, int(top_k))
        kept_bets = ranked[:k]
    else:
        kept_bets = []

    decision = SlateConcentration(
        n_bet=measured.n_bet,
        n_under=measured.n_under,
        n_over=measured.n_over,
        by_side=measured.by_side,
        concentrated_side=measured.concentrated_side,
        share=measured.share,
        triggered=True,
        min_bets=measured.min_bets,
        max_share=measured.max_share,
        policy=policy,
        kept=len(kept_bets),
        suppressed=measured.n_bet - len(kept_bets),
    )
    if log:
        logger.warning(decision.warn_message(model_id))
    return non_bets + kept_bets, decision

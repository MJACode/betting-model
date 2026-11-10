"""NONE rows for the three NBA game-total cards: every game a card SCORED and
did not bet, written beside its decision so the app's All board shows it.

Matt, 2026-11-10: "NBA all tab should have all bets. Not just signals." The
All board reads `picks`, and until now these cards wrote BET rows only (the
decisions with no bet lived in each card's own ledger, which the app never
reads). On 2026-11-09 that hid 18 scored games behind 6 bets. The NCAAB cards
write the same kind of row (scripts/ncaab_total_card.py, Matt 2026-11-04).

A game is SCORED when the rule computed its gap and found a priced offer:
  gap_below_cut          the gap did not reach the cut
  full_game_model_bets   first half only: the gap is the full-game model's
  bet:                   a bet the price or EV floor refused, or one the
                         one-total-a-game door dropped (another NBA total
                         model already bet the game)
A game declined for missing inputs (scores, boxes, under 10 games) or with no
priced offer was never scored and gets no row; its reason stays in the ledger.

THE NUMBERS ON THE ROW. The line, book and price are the best offer on the
model's side at the decision instant, the same offer a bet would have taken.
The probability is the market-fair one, with no uplift: the uplift is the gap
bucket's, measured only on the games that clear the cut, so claiming it on a
game below the cut would overstate the model. A refused or door-dropped bet
keeps the bet's own probability (uplift included), because that IS the claim
the model made. No stake, no Kelly. Nothing publishes or settles a NONE row as
a bet; the scorer's no-bet clear touches only its own models' rows
(models.scorer._pass_rewritten_models), so these survive to tip.
"""
from __future__ import annotations

from loguru import logger

from models.market_relative import implied
from tracking.pick_integrity import pick_problems

REFERENCE_BOOK = "draftkings"
SCORED = ("gap_below_cut", "full_game_model_bets", "bet:")


def is_scored(detail: str) -> bool:
    return bool(detail) and detail.startswith(SCORED)


def none_row(d, *, model_id: str, sport: str, side: str, market: str,
             games: dict[str, dict], bankroll: float, pause) -> dict | None:
    """One decision -> a NONE picks row, or None when the game was not scored
    or carries no priced offer. Pure given its inputs."""
    from models.scorer import _build_pick_label
    if not is_scored(d.detail):
        return None
    if d.book is None or d.line is None or d.price is None or d.p_fair is None:
        return None
    g = games.get(d.game_id, {})
    home, away = g.get("home", ""), g.get("away", "")
    line, price, book = float(d.line), float(d.price), str(d.book)
    label = _build_pick_label(side, home, away, market, line)
    problems = pick_problems(label, side, line, model_id, home, away)
    if problems:
        logger.error(f"{model_id}: no NONE row for {d.game_id} {label!r}: {'; '.join(problems)}")
        return None
    claimed = d.p_model if d.detail.startswith("bet:") and d.p_model is not None else d.p_fair
    p = float(claimed)
    imp = implied(price)
    edge = round(p - imp, 4)
    at_dk = book == REFERENCE_BOOK
    tip = g.get("tip")
    return {
        "game_id": d.game_id, "model_id": model_id, "sport": sport,
        "game_date": g.get("game_date"),
        "game_time": tip.isoformat() if tip is not None else None,
        "pick_side": side, "pick_label": label,
        "model_probability": round(p, 4), "model_probability_cal": round(p, 4),
        "dk_odds": price if at_dk else None,
        "dk_implied_prob": round(imp, 4) if at_dk else 0.0,
        "edge": edge if at_dk else 0.0,
        "dk_bet_link": None,
        "line_book": None if at_dk else book,
        "scored_line": line,
        "kelly_fraction": 0.0, "recommended_bet": 0.0,
        "bankroll_at_pick": bankroll, "signal_type": "NONE",
        "confidence_tier": "MED",
        "decision_book": book, "decision_odds": price,
        "decision_implied_prob": round(imp, 4), "decision_edge": edge,
        "best_book": None if at_dk else book,
        "best_odds": None if at_dk else price,
        "best_implied_prob": None if at_dk else round(imp, 4),
        "best_edge": None if at_dk else edge,
        "best_bet_link": None,
        "downgrade_reason": pause,
    }


def none_rows(decisions, **kw) -> dict[str, dict]:
    """{game_id: NONE row} for every scored decision. A card's publish writes
    it for any game it writes no BET for: below the cut, refused by a floor,
    or dropped by the one-total-a-game door."""
    out = {}
    for d in decisions:
        row = none_row(d, **kw)
        if row is not None:
            out[d.game_id] = row
    return out

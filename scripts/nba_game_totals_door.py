"""One NBA game-total bet a game, across the three NBA game-total models.

mike, 2026-11-04: "Betting Game Over Under AND individual team totals AND 1H
over under seems duplicative - too many picks. Only select the highest EV one."

The three models -- nba_total_luck (full-game over), nba_team_total_luck (home
team total under) and nba_first_half_total_luck (first-half over) -- all read
the same shooting-luck gap. Graded on 2023-24..2025-26 (docs/nba_models_2026.md
section 14):

  - the full-game over and the first-half over are the SAME bet twice: every
    game the full-game model bet, the first-half model bet too (323 of 323),
    because the first half's cut (gap >= 2) sits below the full game's (gap >= 3).
    Those first-half twins returned +3.7% (90% interval -5.0% to +12.7%) against
    +10.2% for the full-game bet on the same games, and the pair's outcomes are
    correlated 0.5. So the first-half model now bets only below the full-game
    model's cut (models/nba_first_half_total_luck.py, FULL_GAME_GAP_CUT): that
    settles the pair in the model itself, whatever the order the cards run in.
  - the home team total under met either over on 2 of 942 bet games. Those
    point opposite ways (a home team under against a game or half over), so a
    second bet is a partial hedge, paid for with a second vig. This door is what
    keeps them apart.

WHY NOT "THE HIGHEST EV": each model's probability is the market-fair price
plus one fixed uplift per model, so its EV on a game is that constant plus the
price, not a measure of how strong the signal is. One a game by the highest EV
graded +124.4 units; full game first +139.0 (the same 942 games).

THE RULE: a game that already holds a BET from any of the three models gets no
other, whatever became of that bet (a VOIDed one included, as the NBA prop
door counts it). The first model to write a game keeps it. The full-game model
decides 60-66 minutes before tip and the other two 45-56 (scheduler.
run_nba_total_luck_window), so the full game is first; the team total and the
first half decide in the same tick, side by side, and whichever commits first
keeps the game.

HOW: each card's publish takes LOCK_KEY's lock BEFORE its own model's lock, then
re-reads the other two models' BETs inside it. A dropped bet leaves no picks row;
its decision row is still written, with n_bets 0 and the reason in its detail
(reason()), so the offer it would have taken stays in that model's ledger.
"""
from __future__ import annotations

MODEL_IDS = ("nba_total_luck", "nba_team_total_luck", "nba_first_half_total_luck")
MAX_NBA_GAME_TOTAL_BETS_PER_GAME = 1
# One advisory-lock key shared by the three cards. Taken FIRST, before each
# card's own model lock, by every writer that takes it: no cycle can form.
LOCK_KEY = "nba_game_totals_one_a_game"


def lock(conn) -> None:
    """Hold the shared lock until this transaction ends (scripts/nfl_wind_publisher._lock_model)."""
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, LOCK_KEY)


def other_bets(conn, game_ids: list[str], model_id: str) -> dict[str, str]:
    """{game_id: model_id} for each of these games holding a BET from one of the OTHER NBA
    game-total models, whatever became of it. Reads only."""
    if model_id not in MODEL_IDS:
        raise ValueError(f"{model_id} is not an NBA game-total model {MODEL_IDS}")
    others = [m for m in MODEL_IDS if m != model_id]
    if not game_ids:
        return {}
    return {g: m for g, m in conn.execute(
        "SELECT game_id, min(model_id) FROM picks WHERE model_id = ANY(%s) "
        "AND signal_type = 'BET' AND game_id = ANY(%s) GROUP BY game_id",
        (others, list(game_ids))).fetchall()}


def reason(other_model_id: str) -> str:
    """The decision row's note for a bet this rule dropped."""
    return f"one_total_a_game:{other_model_id}_already_bet"

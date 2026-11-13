"""NCAAB agreement sizing: a bet that agrees with an earlier NCAAB bet on the
same game is staked at config.NCAAB_AGREEMENT_STAKE_UNITS to win, not 1u.

mike, 2026-11-06: "I want a pick that has a higher confidence and higher long
term win to be higher units, you can slice this from back testing". The slices
were graded walk-forward on the six NCAAB models' own replays (2023-24 to
2025-26, docs/sports/ncaab.md "Agreement sizing"). Sizing by each bet's own EV,
by the model's stated win chance, by price, or by each model's past record all
failed: they bet more without earning more per unit risked. One signal held:

    a later NCAAB bet on the same game and the same side as an earlier one
    (totals: the same Over/Under, full game or first half; sides: the same
    team, any of the spread, the two moneylines and the first-half spread)

    233 bets, +64.09 units flat, +21.3% (95% interval 10.7 to 31.8), won 67.8%
    against a break-even of 55.5% (Wilson 61.5% to 73.5%); positive in all five
    seasons and in both halves of each; every other bet +6.4% (4.2 to 8.6).

Only the LATER bet is sized up: a written pick is never changed (CLAUDE.md
§1c), and the earlier model could not know. The check reads `picks` inside the
card's own write transaction, so it sees every earlier NCAAB BET. A VOID pick
does not count; a NONE row (priced, not bet) does not count.

The risk cap is unchanged: risk is still at most 3u per pick
(tracking/discord_notifier.MAX_RISK_UNITS), so two bets on one game can lay up
to 6u between them.
"""
from __future__ import annotations

import config

# Which agreements count: the same game, the same family, the same side.
FAMILY = {
    "ncaab_total_blend": "total",
    "ncaab_first_half_total": "total",
    "ncaab_spread_market": "side",
    "ncaab_moneyline_own_spread": "side",
    "ncaab_moneyline_first_post": "side",
    "ncaab_first_half_spread": "side",
}

# How a reader names each model in the reason line: the app's own names
# (mobile/src/lib/modelMeta.ts longLabel), so the card and the Models tab agree.
MODEL_NAME = {
    "ncaab_total_blend": "NCAAB Totals",
    "ncaab_first_half_total": "NCAAB First Half Totals",
    "ncaab_spread_market": "NCAAB Spreads",
    "ncaab_moneyline_own_spread": "NCAAB Moneyline",
    "ncaab_moneyline_first_post": "NCAAB Opening Moneyline",
    "ncaab_first_half_spread": "NCAAB First Half Spreads",
}

STAKE_FIELDS = ("stake_units", "stake_reason")

_EARLIER_SQL = """
    SELECT model_id, pick_label
    FROM picks
    WHERE game_id = %s
      AND model_id = ANY(%s)
      AND pick_side = %s
      AND signal_type = 'BET'
      AND (condition_status IS NULL OR condition_status <> 'VOID')
    ORDER BY pick_id
    LIMIT 1
"""


def agreement(conn, game_id: str, model_id: str, side: str) -> tuple[float | None, str | None]:
    """(stake_units, reason) for a BET of `model_id` on `side` of `game_id`, or
    (None, None) when no earlier NCAAB bet agrees (the flat 1u)."""
    units = float(getattr(config, "NCAAB_AGREEMENT_STAKE_UNITS", 1.0) or 1.0)
    family = FAMILY.get(model_id)
    if family is None or units <= 1.0 or not game_id or not side:
        return None, None
    others = [m for m, f in FAMILY.items() if f == family and m != model_id]
    hit = conn.execute(_EARLIER_SQL, (game_id, others, side)).fetchone()
    if not hit:
        return None, None
    name = MODEL_NAME.get(hit[0], hit[0])
    return units, f"Two models agree: {name} also bet {hit[1]}"


def stamp(conn, row: dict, cols) -> dict:
    """The insert parameters for `row` over `cols`, with stake_units and
    stake_reason set when the row is a BET an earlier NCAAB bet agrees with.
    A NONE row, and a BET nothing agrees with, carry None (1u)."""
    params = {c: row.get(c) for c in cols}
    if row.get("signal_type") == "BET":
        units, reason = agreement(conn, row.get("game_id"), row.get("model_id"), row.get("pick_side"))
        params["stake_units"], params["stake_reason"] = units, reason
        row["stake_units"], row["stake_reason"] = units, reason
    else:
        params["stake_units"] = params["stake_reason"] = None
    return params

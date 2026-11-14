"""
The largest edge a real EuroLeague price gives a EuroLeague model: the guard
a EuroLeague writer reads against a feed typo (the shape of
models/ncaabw_quote_bounds.py, which tells the story: a stored total of 1465.0
for 146.5).

THE RULE. A best edge above the model's EDGE_CAP is a data error: no bet is
written. The halftime spread's line and price checks are the grade's own
(models/euroleague_live_ht.py: |line| <= 70, the side's price between -250 and
+250, within 6 points of the read's median), so no line range is repeated here.

THE CAP, measured 2026-11-13 on the replay of the graded rule
(scripts/build_euroleague_live_ht_artifact.py, 364 bets of 2022-23 to
2026-27): the decision edge (the model's chance less the price's implied
chance) ran 0.027 to 0.166. 0.40 is far above every graded bet, so it cuts
none of them, and far below what a price typo gives (a -110 read as +110 is
an edge near 0.5).
"""
from __future__ import annotations

import math

EDGE_CAP: dict[str, float] = {
    "euroleague_live_spread_ht": 0.40,
    # The five pre-game rules (models/euroleague_pregame.py, 2026-11-14). Their
    # decision edge is the walk-forward uplift less the price's vig, so it sits
    # within a few points of the uplift on every replayed bet
    # (scripts/euroleague_pregame_build.py prints the range). 0.40 is far above
    # every one and far below a price typo's edge.
    "euroleague_home_ml": 0.40,
    "euroleague_heavy_fav_ml": 0.40,
    "euroleague_home_dog_spread": 0.40,
    "euroleague_h1_dog_ml": 0.40,
    "euroleague_q1_club_share_total": 0.40,
}


def edge_problem(edge, model_id: str) -> str | None:
    """Why a model's edge is a data error, or None. A model with no cap here
    is refused outright, so a new EuroLeague writer cannot skip choosing one."""
    cap = EDGE_CAP[model_id]
    if edge is None:
        return None
    e = float(edge)
    if math.isfinite(e) and e > cap:
        return f"edge {e:+.4f} above the data-error cap {cap:g}"
    return None

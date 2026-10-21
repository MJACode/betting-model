"""Rank an NBA prop bet by its EV PERCENTILE WITHIN ITS OWN MODEL. Pure, no I/O.

The NBA prop door (scripts/nba_props_card.py) gives each game ONE bet across both NBA prop
models and the night at most four. mike, 2026-10-20: "Only the strongest picks need to be sent,
like NHL." The two models' EVs are not on one scale:
  - nba_prop_market's EV is Pinnacle's no-vig under times the price: median 0.020;
  - nba_prop_projection's is its own calibrated probability times the price: median 0.083.
Ranked on raw EV, the projection model held 99.7% of the pooled top tenth and the market model
got 0.2% to 1.3% of the one-a-game bets: raw EV switches the market model off. A bet's
percentile within its own model's graded EVs puts the two on one scale. Graded at one a game and
four a night in tip order (2023-24..2025-26) it gave +153.6 units, +9.69% (90% range +5.53 to
+13.74), the market model on 29.8% of the bets (re-run from the breakpoints below: +153.8
units, +9.69%, 4 of 1,867 bets different); raw EV gave +134.0 units, +8.86%. The gap is inside
the noise: the choice is about which models get to bet, not about units.

BREAKPOINTS: each model's EV at the 0th, 1st, ..., 100th percentile (101 values, rounded to 4
decimals) of the bets it would have made at its LIVE rule over 2023-24, 2024-25 and 2025-26:
  nba_prop_market      24,572 bets (best of the 8 bettable books, -200 floor, no double- or
                       triple-doubles), +781.3 units
  nba_prop_projection  66,588 bets (the 5 books the live feed returns, assists overs removed,
                       graded rows only), +2,392.8 units
Built 2026-10-20 by scripts/nba_prop_rank_table.py from the bet lists the cap grade used
(props_market_bets_sharp_ALL_under_prop_0.00.parquet, bets_card_arriving5.parquet). Rerun it
and paste its output here to rebuild the table. No results are used: only each bet's EV.
"""
from __future__ import annotations

from bisect import bisect_right

BREAKPOINTS: dict[str, tuple[float, ...]] = {
    "nba_prop_market": (
        0.0000, 0.0001, 0.0004, 0.0006, 0.0010, 0.0014, 0.0018, 0.0021, 0.0027, 0.0031,
        0.0033, 0.0038, 0.0040, 0.0042, 0.0044, 0.0046, 0.0052, 0.0055, 0.0057, 0.0062,
        0.0067, 0.0072, 0.0077, 0.0079, 0.0083, 0.0084, 0.0089, 0.0093, 0.0097, 0.0099,
        0.0103, 0.0109, 0.0116, 0.0121, 0.0122, 0.0126, 0.0131, 0.0135, 0.0138, 0.0141,
        0.0146, 0.0152, 0.0161, 0.0162, 0.0168, 0.0172, 0.0176, 0.0181, 0.0183, 0.0189,
        0.0198, 0.0202, 0.0206, 0.0212, 0.0216, 0.0220, 0.0225, 0.0232, 0.0240, 0.0245,
        0.0251, 0.0255, 0.0263, 0.0269, 0.0278, 0.0285, 0.0290, 0.0296, 0.0303, 0.0311,
        0.0318, 0.0327, 0.0333, 0.0342, 0.0350, 0.0359, 0.0368, 0.0377, 0.0384, 0.0395,
        0.0407, 0.0419, 0.0428, 0.0440, 0.0453, 0.0463, 0.0476, 0.0489, 0.0506, 0.0522,
        0.0541, 0.0559, 0.0579, 0.0601, 0.0626, 0.0657, 0.0695, 0.0745, 0.0817, 0.0965,
        0.2958,
    ),
    "nba_prop_projection": (
        0.0100, 0.0140, 0.0179, 0.0209, 0.0227, 0.0246, 0.0263, 0.0281, 0.0299, 0.0317,
        0.0336, 0.0353, 0.0372, 0.0390, 0.0405, 0.0416, 0.0426, 0.0437, 0.0448, 0.0460,
        0.0471, 0.0482, 0.0494, 0.0505, 0.0515, 0.0526, 0.0537, 0.0547, 0.0558, 0.0569,
        0.0579, 0.0590, 0.0601, 0.0612, 0.0623, 0.0635, 0.0647, 0.0659, 0.0670, 0.0682,
        0.0693, 0.0705, 0.0717, 0.0731, 0.0744, 0.0758, 0.0770, 0.0785, 0.0799, 0.0814,
        0.0827, 0.0840, 0.0854, 0.0868, 0.0883, 0.0899, 0.0915, 0.0932, 0.0949, 0.0965,
        0.0983, 0.1001, 0.1020, 0.1040, 0.1059, 0.1077, 0.1096, 0.1117, 0.1138, 0.1159,
        0.1181, 0.1205, 0.1228, 0.1253, 0.1278, 0.1306, 0.1336, 0.1365, 0.1396, 0.1427,
        0.1458, 0.1489, 0.1526, 0.1564, 0.1606, 0.1653, 0.1696, 0.1744, 0.1796, 0.1855,
        0.1918, 0.1987, 0.2068, 0.2159, 0.2263, 0.2384, 0.2530, 0.2731, 0.3006, 0.3513,
        0.9981,
    ),
}


def ev_percentile(model_id: str, ev: float) -> float:
    """`ev`'s percentile (0.0-1.0) among `model_id`'s graded EVs, linear between breakpoints.

    Below the lowest breakpoint is 0.0, above the highest is 1.0. Non-decreasing in `ev`. An
    unknown model raises KeyError: a model with no table must not be ranked by accident.
    """
    q = BREAKPOINTS[model_id]
    ev = float(ev)
    if ev <= q[0]:
        return 0.0
    if ev >= q[-1]:
        return 1.0
    hi = bisect_right(q, ev)                 # q[hi - 1] <= ev < q[hi]
    lo = hi - 1
    return (lo + (ev - q[lo]) / (q[hi] - q[lo])) / (len(q) - 1)

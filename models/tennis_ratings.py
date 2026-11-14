"""Tennis player ratings: an Elo on every match, and one per surface.

The standard published form (FiveThirtyEight's tennis Elo, Tennis Abstract's
surface Elo): a player's step size shrinks with the matches they have played,
K = 250 / (n + 5) ** 0.4, a Grand Slam match counts 1.1 times, every player
starts at 1500, and the prediction blends the overall rating with the surface
rating half and half. A walkover is not a match and moves nothing; a
retirement counts as a result.

WHAT IT IS FOR. Not a bet on its own: the published comparison (Clegg and
Cartlidge 2025, 8,375 matches 2023 to 2025-06) puts Elo's Brier score at 0.215
against Pinnacle's 0.196. It is an input: to the information test against the
market's own number, and to the serve-and-return model behind total games.

The ratings are computed as of each match, BEFORE it is played, from matches
that finished earlier; matches in one tournament round on one date are rated
in the archive's own order. The archive dates a tournament by its first
Monday, so a match's date here is that Monday, and ratings inside a
tournament advance round by round.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

START = 1500.0
SURFACES = ("Hard", "Clay", "Grass", "Carpet")
ROUND_ORDER = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3, "R128": 10, "R64": 11, "R32": 12,
               "R16": 13, "QF": 14, "SF": 15, "F": 16, "RR": 13, "BR": 15, "ER": 9}


def k_factor(n: int, slam: bool) -> float:
    return 250.0 / (n + 5) ** 0.4 * (1.1 if slam else 1.0)


def expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


@dataclass
class EloState:
    overall: dict
    surface: dict
    n_overall: dict
    n_surface: dict


def new_state() -> EloState:
    return EloState(defaultdict(lambda: START), defaultdict(lambda: START),
                    defaultdict(int), defaultdict(int))


def order_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Chronological order: tournament Monday, then the round, then the
    archive's own match number."""
    d = df.copy()
    d["_r"] = d["round"].map(ROUND_ORDER).fillna(12)
    return d.sort_values(["tourney_date", "tourney_id", "_r", "match_num"]).drop(columns="_r")


def run_elo(df: pd.DataFrame) -> pd.DataFrame:
    """Pre-match ratings for every archive match (winner and loser columns),
    in the order of order_matches. Returns the frame with w_elo, l_elo,
    w_selo, l_selo, w_n, l_n and p_winner (the blended prediction that the
    listed winner wins). Walkovers carry ratings but do not update them."""
    d = order_matches(df)
    st = new_state()
    cols = {c: np.empty(len(d)) for c in ("w_elo", "l_elo", "w_selo", "l_selo", "w_n", "l_n", "p_winner")}
    for i, (w, l, surf, lvl, score) in enumerate(zip(d["winner_id"].values, d["loser_id"].values,
                                                     d["surface"].values, d["tourney_level"].values,
                                                     d["score"].values)):
        surf = surf if surf in SURFACES else "Hard"
        rw, rl = st.overall[w], st.overall[l]
        sw, sl = st.surface[(w, surf)], st.surface[(l, surf)]
        cols["w_elo"][i], cols["l_elo"][i] = rw, rl
        cols["w_selo"][i], cols["l_selo"][i] = sw, sl
        cols["w_n"][i], cols["l_n"][i] = st.n_overall[w], st.n_overall[l]
        cols["p_winner"][i] = expected((rw + sw) / 2, (rl + sl) / 2)
        if "W/O" in str(score).upper():
            continue
        slam = lvl == "G"
        e = expected(rw, rl)
        st.overall[w] = rw + k_factor(st.n_overall[w], slam) * (1 - e)
        st.overall[l] = rl - k_factor(st.n_overall[l], slam) * (1 - e)
        es = expected(sw, sl)
        st.surface[(w, surf)] = sw + k_factor(st.n_surface[(w, surf)], slam) * (1 - es)
        st.surface[(l, surf)] = sl - k_factor(st.n_surface[(l, surf)], slam) * (1 - es)
        st.n_overall[w] += 1
        st.n_overall[l] += 1
        st.n_surface[(w, surf)] += 1
        st.n_surface[(l, surf)] += 1
    for c, v in cols.items():
        d[c] = v
    return d

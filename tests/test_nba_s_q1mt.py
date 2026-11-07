"""The first-quarter moneyline / total search lab (docs/nba_search_q1mt.md): the moneyline candidates are the step's
own side on the first-quarter moneyline, the check and the fade do what they say, and the total's signal is the
unscaled full-game gap toward the over."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts import nba_s_q1mt as M


def _neutral():
    rows = []
    for g in ("g1", "g2", "g3"):
        for side, p in (("home", -120.0), ("away", 100.0)):
            rows.append({"game_id": g, "market": M.ML, "side": side, "book": "draftkings", "price": p,
                         "p_win": 0.5, "p_push": 0.05, "ev": 0.0})
    return pd.DataFrame(rows)


def _sig():
    w = M.WINDOW
    return pd.DataFrame({"game_id": ["g1", "g2", "g3"], f"pick_{w}": ["home", None, "away"],
                         f"k_{w}": [3.0, np.nan, 5.0], f"chk_{w}": [True, False, False]})


def test_the_moneyline_candidates_are_the_steps_side_on_the_first_quarter_moneyline():
    c = M.ml_cand(_neutral(), _sig(), "none")
    assert set(c["market"]) == {M.ML}
    assert set(c["game_id"]) == {"g1", "g3"}                       # g2 has no pick
    by = c.drop_duplicates("game_id").set_index("game_id")
    assert by.loc["g1", "side_pick"] == "home" and by.loc["g3", "side_pick"] == "away"
    assert by.loc["g1", "strength"] == 3.0 and by.loc["g3", "strength"] == 5.0


def test_the_check_keeps_only_games_that_pass_it_and_the_fade_takes_the_other_team():
    c = M.ml_cand(_neutral(), _sig(), "spread")
    assert set(c["game_id"]) == {"g1"}
    f = M.ml_cand(_neutral(), _sig(), "none", fade=True).drop_duplicates("game_id").set_index("game_id")
    assert f.loc["g1", "side_pick"] == "away" and f.loc["g3", "side_pick"] == "home"


def test_a_nan_pick_is_no_pick():
    s = _sig()
    s[f"pick_{M.WINDOW}"] = pd.Series(["home", np.nan, "away"], dtype=object)
    assert set(M.ml_cand(_neutral(), s, "none")["game_id"]) == {"g1", "g3"}


def test_the_total_signal_is_the_unscaled_gap_toward_the_over():
    proj = pd.DataFrame({"game_id": ["g1", "g2", "g3"], "gap_total": [2.5, np.nan, -3.0]})
    s = M.t_signal(proj).set_index("game_id")
    assert set(s.index) == {"g1", "g3"} and set(s["market"]) == {M.TOTAL}
    assert s.loc["g1", "strength"] == 2.5 and s.loc["g3", "strength"] == -3.0


def test_twelve_cells_are_registered():
    assert sum(M.EXPECTED_CELLS.values()) == 12
    assert len(M.M_CHECKS) * len(M.M_CUTS) == M.EXPECTED_CELLS[M.FAM_M]
    assert 2 * len(M.T_CUTS) == M.EXPECTED_CELLS[M.FAM_T]

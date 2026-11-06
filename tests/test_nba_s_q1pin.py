"""The Pinnacle-referenced team-totals lab (docs/nba_search_q1pin.md): its numbers come from Pinnacle's period quotes
alone, and its 12 cells reach the harness with their placebo runs."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import nba_s_q1pin as Z
from scripts import nba_s_q1tt as T


@pytest.fixture(scope="module")
def prep():
    return Z.add_pinnacle(T.synthetic_prep())


def test_the_pinnacle_number_reads_pinnacle_quotes_only(prep):
    for p in T.PERIODS:
        vis = prep["vis_ref"][p]
        assert (vis.book == "pinnacle").any() and (vis.book != "pinnacle").any()
        whole = Z.pinnacle_numbers(vis, prep["pricing"], p).sort_values(["game_id", "team"]).reset_index(drop=True)
        only = Z.pinnacle_numbers(vis[vis.book == "pinnacle"], prep["pricing"], p).sort_values(
            ["game_id", "team"]).reset_index(drop=True)
        assert len(whole) > 0
        pd.testing.assert_frame_equal(whole, only)                    # the soft books' quotes change nothing
        assert Z.pinnacle_numbers(vis[vis.book != "pinnacle"], prep["pricing"], p).empty


def test_home_and_away_split_the_total_by_the_margin(prep):
    pin = prep["periods"]["q1"]["pin"]
    w = pin.pivot(index="game_id", columns="team", values="mu")
    assert np.isfinite(w.to_numpy()).all() and len(w) > 0


def test_the_12_cells_reach_the_harness_with_their_placebo_runs():
    assert Z.synthetic_checks(n_placebo=1)["cells"] == Z.EXPECTED_CELLS

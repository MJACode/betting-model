"""scripts/nba_game2_verdict: every bar of docs/nba_models_2026.md §6.4, applied
to a hand-built cell table. One good cell passes; each bar, broken alone,
fails it, and fails it for that reason."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_verdict as V


def _cell(k=1, **over):
    row = {"family": "F2", "point": "C", "market": "h2h", "side": "away",
           "cut_index": k, "cut": [0.0, 0.01, 0.02][k],
           "n_choose": 900, "roi_choose": 0.08, "ci_lo_choose": 0.02,
           "seasons_positive": True, "half_early_roi": 0.05, "half_late_roi": 0.09,
           "blind_roi_choose": -0.03, "placebo_rois": [-0.04, -0.01, 0.0, -0.02] * 5,
           # all away; favourites and underdogs split; no totals
           "share_home": 0.0, "share_fav": 0.5, "share_over": np.nan,
           "blind_home": -0.05, "blind_away": -0.03, "blind_fav": -0.04, "blind_dog": -0.02,
           "blind_over": np.nan, "blind_under": np.nan,
           "clv_median": 0.01, "n_confirm": 260, "roi_confirm": 0.10, "ci_lo_confirm": 0.01,
           "p_confirm": 1e-7, "p_choose": 1e-7}
    row.update(over)
    return row


def _grid(**over_mid):
    return pd.DataFrame([_cell(0), _cell(1, **over_mid), _cell(2)])


def _mid(v):
    return v[v["cut_index"] == 1].iloc[0]


def test_a_cell_clearing_every_bar_passes():
    assert bool(_mid(V.verdict(_grid()))["passes"]) is True


@pytest.mark.parametrize("over,bar", [
    ({"seasons_positive": False}, "bar5"),
    ({"n_choose": 199}, "bar6"),
    ({"ci_lo_choose": -0.001}, "bar6"),
    ({"half_late_roi": -0.01}, "bar8"),
    ({"blind_away": 0.09}, "bar9"),
    ({"share_fav": 0.8, "blind_fav": 0.085}, "bar9"),
    ({"share_fav": 0.2, "blind_dog": np.nan}, "bar9"),
    ({"placebo_rois": [0.2] * 20}, "bar10"),
    ({"clv_median": -0.001}, "bar11"),
    ({"n_confirm": 150}, "confirm"),
    ({"ci_lo_confirm": -0.01}, "confirm"),
    ({"p_confirm": 0.01}, "bh"),
])
def test_each_bar_alone_fails_the_cell_for_its_own_reason(over, bar):
    m = _mid(V.verdict(_grid(**over)))
    assert bool(m["passes"]) is False
    assert m["failed"] == bar


def test_a_losing_neighbour_breaks_the_plateau():
    g = _grid()
    g.loc[g["cut_index"] == 2, "roi_choose"] = -0.01
    m = _mid(V.verdict(g))
    assert m["failed"] == "bar7"


def test_closing_value_is_a_bar_at_a_to_c_and_only_reported_at_d():
    g = _grid(clv_median=-0.01).assign(point="D")
    assert bool(_mid(V.verdict(g))["bar11"]) is True


def test_the_two_bh_bases_read_different_p_and_m():
    g = _grid(p_confirm=0.5, p_choose=1e-6)
    conf, cho = V.verdict(g, "confirm"), V.verdict(g, "choose")
    assert _mid(conf)["bh_m"] == 3 + 3750 and _mid(cho)["bh_m"] == 3
    assert bool(_mid(conf)["bh"]) is False and bool(_mid(cho)["bh"]) is True


def test_an_extra_axis_keeps_neighbours_apart():
    a = _grid().assign(axis_ref="pinnacle")
    b = _grid().assign(axis_ref="consensus")
    b.loc[b["cut_index"] == 2, "roi_choose"] = -0.05      # only the consensus grid loses
    v = V.verdict(pd.concat([a, b], ignore_index=True))
    mids = v[v["cut_index"] == 1].set_index("axis_ref")
    assert bool(mids.loc["pinnacle", "bar7"]) and not bool(mids.loc["consensus", "bar7"])


def test_duplicate_cells_are_refused():
    with pytest.raises(AssertionError):
        V.verdict(pd.concat([_grid(), _grid()], ignore_index=True))


def test_a_cell_with_no_dominant_side_is_not_held_to_a_blind_bet():
    m = _mid(V.verdict(_grid(share_home=0.6, share_fav=0.4, blind_home=0.5, blind_away=0.5)))
    assert bool(m["bar9"]) is True


def test_controls_are_reported_by_the_labs_and_never_judged_or_counted():
    g = pd.concat([_grid(), _grid().assign(family="control_blind_home")], ignore_index=True)
    v = V.verdict(g)
    assert set(v["family"]) == {"F2"} and v["bh_m"].iloc[0] == 3 + 3750


def test_an_all_empty_placebo_list_reads_as_no_placebo_not_a_crash():
    g = _grid()
    g["placebo_rois"] = [None, [None, None], [np.nan] * 3]
    m = _mid(V.verdict(g))
    assert m["failed"] == "bar10"

"""scripts/nba_game2_store: a graded run is stored whole, JSON-safe, one row per cell."""
import json

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_store as S


def test_values_are_json_safe_and_nothing_is_lost():
    row = {"a": np.float64("nan"), "b": np.inf, "c": np.int64(3), "d": np.bool_(True),
           "e": np.array([0.1, np.nan]), "f": "x", "g": None}
    out = {k: S._plain(v) for k, v in row.items()}
    assert out == {"a": None, "b": None, "c": 3, "d": True, "e": [0.1, None], "f": "x", "g": None}
    json.dumps(out)


def test_one_row_per_cell_and_a_duplicate_key_is_refused():
    base = {"family": "F2", "point": "C", "market": "h2h", "side": "fav", "cut_index": 0,
            "cut": 0.0, "roi_choose": np.nan, "placebo_rois": np.array([0.1, -0.2])}
    cells = pd.DataFrame([base, {**base, "cut_index": 1, "cut": 0.01}])
    rows = S.cell_rows(cells, "run1")
    assert len(rows) == 2 and {r[2] for r in rows} == {"F2|C|h2h|fav|cut=0.0", "F2|C|h2h|fav|cut=0.01"}
    assert json.loads(rows[0][3])["placebo_rois"] == [0.1, -0.2]
    with pytest.raises(AssertionError):
        S.cell_rows(pd.concat([cells, cells]), "run1")

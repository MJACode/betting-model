"""
Opposing-starter quality on batter rows — computed now, wired at retrain.

WHY
---
Every MLB batter prop model except home runs saw the opposing pitching staff
only as `opp_team_era`. That is a team-level season number: it cannot tell an
ace from a bullpen game, which is the biggest single swing in a hitter's night.
The starter's identity was already resolved on every row for the HR model's v2
features; only the general quality columns were missing.

WHY IT IS NOT LIVE YET
----------------------
A saved model artifact has a fixed feature count. Adding a column to a FEATURE
list without retraining does not improve that model, it stops it loading — and
a model that cannot load stops scoring silently. One missing FEATURE_MAP key
has already produced zero game-level picks league-wide for a day here.

So the columns exist on the row and the intended wiring is declared in
PENDING_RETRAIN_FEATURES; activating it is one edit plus a retrain plus a
committed .pkl.
"""

from __future__ import annotations

from features import prop_feature_engine as fe


def test_the_helper_returns_all_four_columns_even_with_no_starter():
    """A missing starter must yield the keys with None, not an absent key.

    An absent key becomes a missing column in the training matrix, and one
    sparse column plus dropna silently deletes most rows — the failure that
    already cost this repo a model."""
    out = fe._opp_starter_savant({}, None, 2026, training_mode=True)
    assert set(out) == {"opp_starter_k_pct", "opp_starter_bb_pct",
                        "opp_starter_xera", "opp_starter_whiff_pct"}
    assert all(v is None for v in out.values())


def test_it_reads_the_starters_savant_row():
    bulk = {"savant": {("SP1", 2025): {"k_pct": 0.28, "bb_pct": 0.06,
                                       "xera": 3.10, "whiff_pct": 0.31}}}
    out = fe._opp_starter_savant(bulk, "SP1", 2026, training_mode=True)
    assert out["opp_starter_k_pct"] == 0.28
    assert out["opp_starter_bb_pct"] == 0.06
    assert out["opp_starter_xera"] == 3.10
    assert out["opp_starter_whiff_pct"] == 0.31


def test_training_mode_takes_the_prior_season():
    """Leakage: a training row for a 2026 game must not see 2026 aggregates."""
    bulk = {"savant": {("SP1", 2025): {"k_pct": 0.20},
                       ("SP1", 2026): {"k_pct": 0.99}}}
    out = fe._opp_starter_savant(bulk, "SP1", 2026, training_mode=True)
    assert out["opp_starter_k_pct"] == 0.20, "training mode read the current season"


def test_live_mode_prefers_the_current_season():
    bulk = {"savant": {("SP1", 2025): {"k_pct": 0.20},
                       ("SP1", 2026): {"k_pct": 0.30}}}
    out = fe._opp_starter_savant(bulk, "SP1", 2026, training_mode=False)
    assert out["opp_starter_k_pct"] == 0.30


def test_live_mode_falls_back_to_prior_season():
    bulk = {"savant": {("SP1", 2025): {"k_pct": 0.20}}}
    out = fe._opp_starter_savant(bulk, "SP1", 2026, training_mode=False)
    assert out["opp_starter_k_pct"] == 0.20


# ── the wiring is declared, and deliberately not active ──────────────────────

def test_pending_features_are_declared_for_every_batter_model_that_lacked_them():
    for m in ("mlb_prop_batter_hits", "mlb_prop_batter_tb",
              "mlb_prop_batter_rbi", "mlb_prop_batter_runs",
              "mlb_prop_batter_walks"):
        assert m in fe.PENDING_RETRAIN_FEATURES
        assert fe.PENDING_RETRAIN_FEATURES[m]


def test_pending_features_are_NOT_in_the_live_feature_lists():
    """The guard. Adding one of these to a live list without retraining stops
    that model loading, and a model that cannot load stops scoring silently."""
    for model_id, pending in fe.PENDING_RETRAIN_FEATURES.items():
        live = fe.PROP_FEATURE_MAP[model_id]
        overlap = set(pending) & set(live)
        assert not overlap, (
            f"{model_id} lists {sorted(overlap)} but its artifact was not "
            f"retrained — retrain and commit the .pkl in the same change")


def test_the_home_run_model_already_had_its_starter_features():
    """It is excluded from the pending set because it is already done."""
    assert "mlb_prop_batter_hr" not in fe.PENDING_RETRAIN_FEATURES
    assert "opp_starter_hr9" in fe.PROP_FEATURE_MAP["mlb_prop_batter_hr"]


# ── The bulk dict the helpers actually receive ────────────────────────────────
#
# The four assertions above exercise _opp_starter_savant against a hand-built
# bulk dict. That is exactly the fixture-drifts-from-the-producer trap in
# CLAUDE.md §7 ("test the producer's REAL output through the real renderer"),
# and it bit immediately: the batter bulk loader did not build a 'savant' key
# at all -- it loaded pitcher Savant as a bare gb_pct map -- so every batter row
# that knew its opposing starter raised KeyError inside _pitcher_savant, while
# the hand-written fixture passed. These tests run the REAL loader.

class _StubResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _StubConn:
    """Answers each of the loader's queries by matching on its SQL text.

    Returns empty results for everything not named, which is the honest
    default: the loader must survive a table with no rows, and the assertions
    below are about the SHAPE of what it returns, not the data volume.
    """

    def __init__(self, by_table: dict[str, list[tuple]] | None = None):
        self._by_table = by_table or {}
        self.queries: list[str] = []

    def execute(self, sql, params=None):
        self.queries.append(sql)
        for needle, rows in self._by_table.items():
            if needle in sql:
                return _StubResult(rows)
        return _StubResult([])


def _batter_bulk(**by_table):
    from features.prop_feature_engine import _build_bulk_batter_lookups
    return _build_bulk_batter_lookups(_StubConn(by_table), [2024, 2025])


def test_batter_bulk_carries_everything_opp_starter_savant_reads():
    """The real loader's output satisfies the real helper -- no KeyError."""
    from features.prop_feature_engine import _opp_starter_savant

    bulk = _batter_bulk()
    out = _opp_starter_savant(bulk, "starter-1", 2025, training_mode=True)
    assert set(out) == {"opp_starter_k_pct", "opp_starter_bb_pct",
                        "opp_starter_xera", "opp_starter_whiff_pct"}
    assert all(v is None for v in out.values())


def test_opp_starter_savant_reads_real_values_off_the_real_loader():
    """A pitcher Savant row loaded by the loader reaches the batter's features.

    Training mode takes the PRIOR season, so a 2024 row is what a 2025 game
    sees -- asserted here rather than assumed, because a leakage rule that is
    only tested against a fixture is a rule about the fixture.
    """
    from features.prop_feature_engine import _opp_starter_savant

    # SELECT player_id, season, k_pct, bb_pct, whiff_pct,
    #        swstr_pct, csw_pct, xera, avg_velocity, gb_pct
    row_2024 = ("starter-1", 2024, 0.281, 0.061, 0.312, 0.14, 0.30, 3.41, 94.2, 0.44)
    row_2025 = ("starter-1", 2025, 0.999, 0.999, 0.999, 0.99, 0.99, 9.99, 99.9, 0.99)
    bulk = _batter_bulk(**{"player_type = 'pitcher'": [row_2024, row_2025]})

    out = _opp_starter_savant(bulk, "starter-1", 2025, training_mode=True)
    assert out["opp_starter_k_pct"] == 0.281
    assert out["opp_starter_bb_pct"] == 0.061
    assert out["opp_starter_whiff_pct"] == 0.312
    assert out["opp_starter_xera"] == 3.41


def test_starter_gb_pct_still_works_off_the_same_query():
    """The gb_pct map the HR model uses survived being derived, not loaded."""
    from features.prop_feature_engine import _starter_gb_pct

    row_2024 = ("starter-1", 2024, 0.281, 0.061, 0.312, 0.14, 0.30, 3.41, 94.2, 0.44)
    bulk = _batter_bulk(**{"player_type = 'pitcher'": [row_2024]})
    assert _starter_gb_pct(bulk, "starter-1", 2025, training_mode=True) == 0.44

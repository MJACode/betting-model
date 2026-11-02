"""The three NBA game total models price from the table their artifact stores.

Each card is a process of its own, so a table rebuilt by each run was rebuilt on
every tick that decides a game (models/nba_total_luck.py, THE PRICE TABLE IS STORED).
These tests read the committed artifacts: no database, no API.

A full rebuild takes 18 to 41 seconds per model on an idle machine, so here the
stored tables are compared against the real tabulation on every 40th point of the
grid. scripts/nba_pricing_table_embed.py compared every point when the files were
written.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_first_half_total_luck as fh  # noqa: E402
import models.nba_team_total_luck as tt  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_pricing_table_embed as E  # noqa: E402

MODELS = [tl, tt, fh]
STRIDE = 40
LIVE_SEASON = 2027      # 2026-27: the only season a card prices


@pytest.fixture(autouse=True)
def fresh_caches():
    for m in MODELS:
        m._DIST_CACHE.clear()
    yield
    for m in MODELS:
        m._DIST_CACHE.clear()


def _no_tabulating(self, r, t):
    raise AssertionError("the card rebuilt the table")


@pytest.mark.parametrize("mod", MODELS, ids=lambda m: m.MODEL_ID)
def test_a_card_prices_the_live_season_without_tabulating(mod, monkeypatch):
    """RULE: nothing in the card's run builds the table. Rebuilt by each card, the
    team-total model was killed at its 180-second limit on 60 of 74 attempts on the
    worker from 2026-10-24 to 10-31."""
    art = mod.load_artifact()
    assert mod.newest_season(art) + 1 == LIVE_SEASON
    monkeypatch.setattr(H.ResidDist, "_table", _no_tabulating)
    d = mod.pricing_dist(art, LIVE_SEASON)
    win, push, lose = d.probs(np.array([113.0]), np.array([112.5]))
    assert 0.0 < win[0] < 1.0 and push[0] == 0.0 and lose[0] == pytest.approx(1.0 - win[0])
    assert mod.pricing_dist(art, LIVE_SEASON) is d, "once per process"


@pytest.mark.parametrize("mod", MODELS, ids=lambda m: m.MODEL_ID)
def test_the_stored_table_is_what_the_real_tabulation_makes(mod, monkeypatch):
    """RULE: the store changes no probability. The model's own derivation of the
    residuals and the real ResidDist._table run on the artifact without its table, on
    a thinned grid, and must equal the stored numbers exactly."""
    art = mod.load_artifact()
    stored = mod.pricing_dist(art, LIVE_SEASON)
    mod._DIST_CACHE.clear()
    real = H.ResidDist._table

    def thinned(self, r, t):
        grid = self.d
        self.d = grid[::STRIDE]
        try:
            return real(self, r, t)
        finally:
            self.d = grid
    monkeypatch.setattr(H.ResidDist, "_table", thinned)
    built = mod.pricing_dist({k: v for k, v in art.items() if k != "pricing_tables"}, LIVE_SEASON)
    assert built is not stored
    assert (built.mean, built.n, built.sd, built.label) == (
        stored.mean, stored.n, stored.sd, stored.label)
    assert np.array_equal(built.d, stored.d)
    for table in ("win_whole", "push_whole", "win_half"):
        assert np.array_equal(getattr(built, table), getattr(stored, table)[::STRIDE]), table


@pytest.mark.parametrize("mod", MODELS, ids=lambda m: m.MODEL_ID)
def test_only_the_live_season_is_stored_and_a_graded_season_still_builds(mod, monkeypatch):
    """The replays price graded seasons through the lab's own path, not this store."""
    art = mod.load_artifact()
    assert list(art["pricing_tables"]) == [LIVE_SEASON]
    monkeypatch.setattr(H.ResidDist, "_table", _no_tabulating)
    with pytest.raises(AssertionError, match="rebuilt the table"):
        mod.pricing_dist(art, 2026)


def test_the_table_survives_a_pickle_as_plain_python_numbers():
    """RULE: every float round-trips exactly, and the stored file names no numpy
    module. A pickled array names numpy's internals, which differ between numpy
    versions, and this file is written here and opened on the worker. Every other
    key of these artifacts is plain Python already."""
    d = H.ResidDist(np.arange(-30.0, 30.0, 0.5), "made up")
    blob = pickle.dumps(d.state(), protocol=4)
    back = H.ResidDist.from_state(pickle.loads(blob))
    assert E.tables_identical(back, d) and E.probs_identical(back, d)
    assert repr(back) == repr(d)
    assert b"numpy" not in blob


@pytest.mark.parametrize("mod", MODELS, ids=lambda m: m.MODEL_ID)
def test_no_committed_artifact_names_numpy(mod):
    assert b"numpy" not in (ROOT / mod.ARTIFACT_PATH).read_bytes()


def test_the_comparison_used_on_the_files_can_see_a_difference():
    d = H.ResidDist(np.arange(-30.0, 30.0, 0.5), "made up")
    other = H.ResidDist.from_state({**d.state(), "win_half": d.win_half + 1e-12})
    assert not E.tables_identical(other, d) and not E.probs_identical(other, d)
    assert not E.tables_identical(H.ResidDist.from_state({**d.state(), "sd": d.sd + 1}), d)


@pytest.mark.parametrize("mod, rows", [
    (tl, "close_resid"), (tt, "tt_resid"), (fh, "h1_rows")], ids=lambda x: getattr(x, "MODEL_ID", x))
def test_a_refit_stores_the_table_of_the_season_after_its_rows(mod, rows, monkeypatch):
    """with_pricing_table is what each build script calls, on the model's own
    functions, so a refit for 2027-28 stores 2027-28's."""
    art = mod.load_artifact()
    base = {k: v for k, v in art.items() if k != "pricing_tables"}
    monkeypatch.setattr(mod, "pricing_dist", lambda a, s: H.ResidDist.from_state(
        {"mean": 0.0, "n": s, "sd": 1.0, "label": "x", "d": np.zeros(1), "win_whole": np.zeros(1),
         "push_whole": np.zeros(1), "win_half": np.zeros(1)}))
    new = tl.with_pricing_table(base, mod.pricing_dist, mod.newest_season)
    assert list(new["pricing_tables"]) == [LIVE_SEASON]
    assert new["pricing_tables"][LIVE_SEASON]["n"] == LIVE_SEASON
    assert new[rows] is base[rows] and "pricing_tables" not in base


@pytest.mark.parametrize("script", ["nba_total_luck_build", "nba_team_total_luck_build",
                                    "nba_first_half_total_luck_build"])
def test_each_build_script_stores_the_table(script):
    src = (ROOT / "scripts" / f"{script}.py").read_text(encoding="utf-8")
    write, table = src.index("pickle.dump(art"), src.index("with_pricing_table(art")
    assert table < write

"""models/seed_average.SeedAverage: several fits of one regressor behind one `predict`.

The NCAAF totals fit subsamples rows and columns, so the same data fitted
under another random seed predicts a different total (about 1.5 points for one
game, docs/ncaaf_market_audit.md section 4). The shipped model is therefore
the mean of eleven fits, and the scorer must be able to use it without knowing:
its `total_regression` branch calls `float(clf.predict(x)[0])` on one row.

The trap these tests are for is the one that only shows on the worker. The fit
runs as `python -m scripts.ncaaf_margin_eval`, so a class defined in that
script would pickle as `__main__.<name>`: it would load on the machine that
fitted it and nowhere else.
"""

from __future__ import annotations

import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class _Line:
    """A stand-in fitted regressor: value + slope * first column, as float32
    (what xgboost returns). Module-level so it pickles."""

    def __init__(self, value: float, slope: float = 0.0):
        self.value, self.slope = value, slope

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        return (self.value + self.slope * X[:, 0]).astype(np.float32)


def test_predict_is_the_mean_of_the_members():
    from models.seed_average import SeedAverage

    members = [_Line(50.0, 1.0), _Line(53.0, 2.0), _Line(56.0, 0.0)]
    model = SeedAverage(members, seeds=[42, 0, 1])
    X = np.array([[1.0, 9.0], [2.0, 9.0], [-4.0, 9.0]])
    expected = np.mean([m.predict(X) for m in members], axis=0)
    got = model.predict(X)
    assert got.shape == (3,)
    assert got == pytest.approx(expected)
    # 53 + 1*x for these three members, to be sure the helper is not the oracle.
    assert got == pytest.approx([54.0, 55.0, 49.0])


def test_predict_answers_the_scorers_one_row_call():
    """models/scorer.py: `pred_total = float(clf.predict(x)[0])`, x of shape (1, n)."""
    from models.seed_average import SeedAverage

    model = SeedAverage([_Line(40.0), _Line(50.0)], seeds=[42, 0])
    x = np.array([3.0, np.nan, 1.0], dtype=float).reshape(1, -1)
    assert float(model.predict(x)[0]) == pytest.approx(45.0)


def test_member_predictions_keeps_one_row_per_member():
    from models.seed_average import SeedAverage

    model = SeedAverage([_Line(40.0), _Line(50.0), _Line(54.0)], seeds=[42, 0, 1])
    per = model.member_predictions(np.zeros((5, 2)))
    assert per.shape == (3, 5)
    assert per[:, 0] == pytest.approx([40.0, 50.0, 54.0])
    assert model.predict(np.zeros((5, 2))) == pytest.approx(per.mean(axis=0))


def test_it_knows_its_seeds_and_its_size():
    from models.seed_average import SeedAverage

    model = SeedAverage([_Line(1.0), _Line(2.0)], seeds=[42, 0])
    assert len(model) == 2
    assert model.seeds == [42, 0]


def test_an_average_of_nothing_is_refused():
    from models.seed_average import SeedAverage

    with pytest.raises(ValueError):
        SeedAverage([])


def test_seeds_must_line_up_with_members():
    from models.seed_average import SeedAverage

    with pytest.raises(ValueError):
        SeedAverage([_Line(1.0), _Line(2.0)], seeds=[42])


def test_it_pickles_and_reloads_to_the_same_predictions():
    from models.seed_average import SeedAverage

    model = SeedAverage([_Line(50.0, 1.0), _Line(53.0, 2.0)], seeds=[42, 0])
    X = np.array([[1.0], [2.5]])
    back = pickle.loads(pickle.dumps(model))
    assert isinstance(back, SeedAverage)
    assert back.seeds == [42, 0]
    assert back.predict(X) == pytest.approx(model.predict(X))


def test_real_fitted_regressors_average_and_survive_a_pickle():
    """The members that ship are xgboost regressors, and a served row carries NaN
    for a missing feature (models/scorer._feature_value)."""
    from xgboost import XGBRegressor

    from models.seed_average import SeedAverage

    rng = np.random.default_rng(11)
    X = rng.normal(size=(200, 4))
    y = 50 + 6 * X[:, 0] + rng.normal(0, 3, 200)
    members = []
    for seed in (42, 0, 1):
        m = XGBRegressor(n_estimators=20, max_depth=3, subsample=0.8,
                         colsample_bytree=0.8, random_state=seed)
        m.fit(X, y)
        members.append(m)
    model = SeedAverage(members, seeds=[42, 0, 1])

    probe = rng.normal(size=(6, 4))
    probe[0, 2] = np.nan
    each = np.array([m.predict(probe) for m in members], dtype=float)
    assert each.std(axis=0).max() > 0, "the seeds did not move the fit; nothing is averaged"
    assert model.predict(probe) == pytest.approx(each.mean(axis=0))
    assert np.isfinite(model.predict(probe)).all()

    back = pickle.loads(pickle.dumps(model))
    assert np.array_equal(back.predict(probe), model.predict(probe))


def _booster_threads(member) -> str:
    import json
    return json.loads(member.get_booster().save_config())["learner"]["generic_param"]["nthread"]


def _three_real_members(n_jobs=-1):
    from xgboost import XGBRegressor

    rng = np.random.default_rng(5)
    X = rng.normal(size=(300, 5))
    y = 50 + 6 * X[:, 0] - 3 * X[:, 1] + rng.normal(0, 3, 300)
    members = []
    for seed in (42, 0, 1):
        m = XGBRegressor(n_estimators=40, max_depth=4, subsample=0.8,
                         colsample_bytree=0.8, n_jobs=n_jobs, random_state=seed)
        m.fit(X, y)
        members.append(m)
    probe = rng.normal(size=(64, 5))
    probe[::7, 3] = np.nan
    return members, probe


def test_predicting_runs_each_member_on_one_thread_and_changes_no_value():
    """The scorer predicts ONE row per game. A fit made with n_jobs=-1 starts a
    thread pool for that one row, eleven times a game; measured 2026-11-10 that
    was most of a 62 ms predict. One thread per member is 3 to 4 times faster
    on one row and cannot change a number: threads split rows, not the sum of
    one row's trees. So the values are compared to the last bit."""
    from models.seed_average import SeedAverage

    members, probe = _three_real_members()
    want_each = np.array([np.asarray(m.predict(probe), dtype=float) for m in members])
    assert {_booster_threads(m) for m in members} != {"1"}, "fixture is already single-threaded"

    model = SeedAverage(members, seeds=[42, 0, 1])
    assert {_booster_threads(m) for m in model.members} == {"1"}
    assert np.array_equal(model.member_predictions(probe), want_each)
    assert np.array_equal(model.predict(probe), want_each.mean(axis=0))
    one_by_one = np.array([model.predict(probe[i:i + 1])[0] for i in range(len(probe))])
    assert np.array_equal(one_by_one, want_each.mean(axis=0))


def test_an_artifact_pickled_before_this_change_is_single_threaded_once_loaded():
    """The committed artifact was pickled with its members as fitted. Loading
    it has to apply the same setting, or only refits would get it."""
    from models.seed_average import SeedAverage

    members, probe = _three_real_members()
    want = np.array([np.asarray(m.predict(probe), dtype=float) for m in members]).mean(axis=0)
    old_style = SeedAverage.__new__(SeedAverage)           # as pickle rebuilt it before
    old_style.__dict__.update({"members": members, "seeds": [42, 0, 1]})
    blob = pickle.dumps(old_style)
    assert {_booster_threads(m) for m in members} != {"1"}

    back = pickle.loads(blob)
    assert {_booster_threads(m) for m in back.members} == {"1"}
    assert np.array_equal(back.predict(probe), want)


def test_members_that_are_not_boosted_trees_are_left_alone():
    from models.seed_average import SeedAverage

    model = SeedAverage([_Line(40.0), _Line(50.0)], seeds=[42, 0])
    assert pickle.loads(pickle.dumps(model)).predict(np.zeros((1, 1)))[0] == pytest.approx(45.0)


def test_the_scorer_prices_the_average_through_its_total_regression_branch(monkeypatch):
    """End to end through `score_game`, unchanged: the probability must be the
    residual ECDF at (AVERAGE prediction - DraftKings total).

    The members are chosen so the answer depends on averaging: they predict 58,
    62 and 63 against a line of 52.5. The mean, 61, is 8.5 from the line and
    clears the 8-point gate. The first member alone is 5.5 away and would be
    inside it.
    """
    import models.scorer as sc
    from features.ncaaf_feature_engine import total_over_prob
    from models.seed_average import SeedAverage

    # 41 residuals, -20..20: P(over) at +8.5 is 29/41 = 0.707, an edge of 0.18
    # at -110. (A tighter set would cross the scorer's 0.20 stale-line cap,
    # which writes no row at all.)
    residuals = sorted(float(v) for v in range(-20, 21))
    artifact = {"kind": "total_regression",
                "model": SeedAverage([_Line(58.0), _Line(62.0), _Line(63.0)], seeds=[42, 0, 1]),
                "feature_cols": ["home_points_per_game", "wx_wind_mph"],
                "residuals": residuals, "d_threshold": 8.0}
    monkeypatch.setattr(sc, "load_model", lambda mid: artifact)
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: {
        "total_line": 52.5, "over_price": -110, "under_price": -110,
        "spread_home": None, "home_price": None, "away_price": None})
    monkeypatch.setattr(sc, "_get_public_betting",
                        lambda conn, gid, market, side: {
                            "public_bet_pct": None, "public_money_pct": None})

    features = {"home_points_per_game": 31.0, "wx_wind_mph": None,
                "home_team": "Ohio State", "away_team": "Toledo",
                "game_date": "2026-09-05"}
    picks = sc.score_game(None, "NCAAF_2026-09-05_toledo_ohio-state",
                          "ncaaf_over_under", features, bankroll=1000.0,
                          dry_run=True)

    over = [p for p in picks if p["pick_side"] == "over"]
    assert over, "the over row must be generated"
    expected = total_over_prob(residuals, 61.0 - 52.5)
    assert expected == pytest.approx(29 / 41)
    # _make_pick rounds to 4 decimals.
    assert over[0]["model_probability"] == pytest.approx(expected, abs=1e-4)
    assert over[0]["model_probability"] != pytest.approx(
        total_over_prob(residuals, 58.0 - 52.5), abs=1e-4), "priced off one member"
    assert over[0]["scored_line"] == 52.5
    assert "gate" not in (over[0].get("downgrade_reason") or ""), (
        "the average is 8.5 from the line; it was read as inside the 8-point gate")


def test_the_pickle_names_an_importable_module_not_the_script_that_fitted_it(tmp_path):
    """A fresh interpreter with only the repo on its path must load it. That is
    the worker: `models.trainer.load_model` is a bare `pickle.load`."""
    from models.seed_average import SeedAverage

    assert SeedAverage.__module__ == "models.seed_average"

    # Members must be importable there too, so use a class the child process has.
    from sklearn.dummy import DummyRegressor

    members = []
    for value in (40.0, 50.0, 60.0):
        d = DummyRegressor(strategy="constant", constant=value)
        d.fit(np.zeros((2, 1)), np.array([value, value]))
        members.append(d)
    path = tmp_path / "avg.pkl"
    path.write_bytes(pickle.dumps({"kind": "total_regression",
                                   "model": SeedAverage(members, seeds=[42, 0, 1])}))
    code = (
        "import pickle, sys\n"
        "import numpy as np\n"
        f"art = pickle.load(open(r'{path}', 'rb'))\n"
        "print(type(art['model']).__module__, float(art['model'].predict(np.zeros((1, 1)))[0]))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["models.seed_average", "50.0"]

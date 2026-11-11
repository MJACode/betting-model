"""The NCAAF totals fit is the mean of eleven seeds, and fitting never registers.

Two things changed on 2026-11-10 (mike, after docs/ncaaf_market_audit.md
section 4) and each has a way to be silently undone:

1. THE MODEL IS AN AVERAGE. One fit's prediction for a game moves about 1.5
   points with its random seed, so everything read off the fit has to be read
   off the AVERAGE: the out-of-sample residuals the probability comes from,
   the record at the 8-point gate, the kill line. Residuals taken from one
   member would look just as plausible and would describe a model that is not
   the one scoring.

2. FITTING AND REGISTERING ARE TWO STEPS. The old function wrote the file and
   switched `model_registry` in one go, which points the worker at a file it
   does not have until the next deploy. The fit now writes the artifact and
   says what it would register; registering takes the version and runs later.

Most tests here swap the real fit for a stand-in whose prediction depends on
its seed, so "came from the average" has an exact answer. One runs the real
fit, because a stand-in cannot say what the real hyper-parameters are.
"""

from __future__ import annotations

import inspect
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.ncaaf_margin_eval as ev  # noqa: E402
from features.ncaaf_feature_engine import total_over_prob  # noqa: E402

SEEDS = [42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
SEED_STEP = 0.5                                   # points one seed moves the stand-in
AVG_SHIFT = SEED_STEP * sum(SEEDS) / len(SEEDS)   # 3.9545: the average's offset
F0 = ev.TOTAL_FEATURES[0]


WIND = ev.TOTAL_FEATURES.index("wx_wind_mph")
ELEV = ev.TOTAL_FEATURES.index("venue_elevation_ft")


class _Stub:
    """55 + 12 * first feature + 0.5 * seed. Every seed predicts a different
    total, so the average and any single member are told apart exactly.

    NAN_WIND_DROP points come off when the wind is missing: 0 by default, set
    by the tests about a game that has no weather forecast yet."""

    NAN_WIND_DROP = 0.0
    NAN_ELEV_DROP = 0.0          # the same, for a missing venue elevation

    def __init__(self, seed: int):
        self.seed = seed

    def predict(self, X):
        A = X.to_numpy(dtype=float) if hasattr(X, "to_numpy") else np.asarray(X, dtype=float)
        return (55.0 + 12.0 * A[:, 0] + SEED_STEP * self.seed
                - self.NAN_WIND_DROP * np.isnan(A[:, WIND])
                - self.NAN_ELEV_DROP * np.isnan(A[:, ELEV]))


def _frame(seasons=(2021, 2022, 2023, 2024), n=200, flip=(), line="stale"):
    """A synthetic totals frame. The true total follows the stand-in's average;
    the market line only half follows it, so there are games 8+ points away.

    flip : seasons whose totals run the OPPOSITE way to the model (it loses).
    line : "stale" (bets exist) or "model" (the line is the model: no bets).
    """
    rng = np.random.default_rng(7)
    parts = []
    for s in seasons:
        d = pd.DataFrame({c: rng.normal(size=n) for c in ev.TOTAL_FEATURES})
        sign = -1.0 if s in flip else 1.0
        d["_season"] = s
        d["_game_id"] = [f"G{s}_{i}" for i in range(n)]
        d["_total"] = np.round(55.0 + AVG_SHIFT + sign * 12.0 * d[F0] + rng.normal(0, 6, n))
        if line == "model":
            d["_total_line"] = 55.0 + AVG_SHIFT + 12.0 * d[F0]
        else:
            d["_total_line"] = np.round((55.0 + AVG_SHIFT + 2.0 * d[F0]) * 2) / 2
        d["_margin"] = 0.0
        d["_spread_home"] = 0.0
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


@pytest.fixture
def stub_fit(monkeypatch):
    """Replace the real fit; record every call (rows, seed, seasons it saw)."""
    calls = []

    def fit(X, y, random_state=42):
        calls.append({"rows": len(X), "seed": random_state, "index": X.index})
        return _Stub(random_state)

    monkeypatch.setattr(ev, "_fit", fit)
    return calls


@pytest.fixture
def no_database(monkeypatch):
    """Any reach for the database or the frame builder fails the test."""
    import data.db

    def boom(*a, **k):
        raise AssertionError("the fit reached for the database")

    monkeypatch.setattr(data.db, "get_connection", boom)
    monkeypatch.setattr(ev, "build_frames", boom)


def _fit_to(tmp_path, frame, train=(2021, 2022, 2023), holdout=2024):
    path = tmp_path / "frame.pkl"
    frame.to_pickle(path)
    out = tmp_path / "saved"
    res = ev.fit_totals(list(train), holdout, frame_path=path, out_dir=out)
    return res, out


# ── the model is an average ───────────────────────────────────────────────────

def test_the_seeds_are_the_eleven_the_audit_measured():
    assert list(ev.TOTALS_SEEDS) == SEEDS


def test_the_fit_is_eleven_members_one_per_seed(tmp_path, stub_fit, no_database):
    from models.seed_average import SeedAverage

    frame = _frame()
    res, out = _fit_to(tmp_path, frame)
    with open(res["path"], "rb") as f:
        art = pickle.load(f)

    assert art["kind"] == "total_regression"
    assert isinstance(art["model"], SeedAverage)
    assert len(art["model"]) == 11
    assert art["model"].seeds == SEEDS and art["seeds"] == SEEDS

    # Two rounds of eleven: the eval fit on the train seasons only, then the
    # final fit on everything. Each round covers every seed once, in order.
    assert [c["seed"] for c in stub_fit] == SEEDS + SEEDS
    n_train = int(frame["_season"].isin([2021, 2022, 2023]).sum())
    assert [c["rows"] for c in stub_fit] == [n_train] * 11 + [len(frame)] * 11
    for c in stub_fit[:11]:
        assert set(frame.loc[c["index"], "_season"]) == {2021, 2022, 2023}, (
            "the eval fit saw the holdout season: its residuals are in-sample")
    # The members that ship are the FINAL round's, not the eval round's.
    assert [m.seed for m in art["model"].members] == SEEDS


def test_residuals_are_the_averages_not_one_members(tmp_path, stub_fit, no_database):
    frame = _frame()
    res, _ = _fit_to(tmp_path, frame)
    art = res["artifact"]

    hold = frame[frame["_season"] == 2024]
    avg_pred = 55.0 + 12.0 * hold[F0].to_numpy() + AVG_SHIFT
    expected = sorted((hold["_total"].to_numpy() - avg_pred).tolist())
    assert len(art["residuals"]) == len(hold)
    assert art["residuals"] == sorted(art["residuals"])
    assert art["residuals"] == pytest.approx(expected)

    # Seed 42 alone sits 0.5 * (42 - 7.909) = 17.05 points higher, so its
    # residuals are 17 points lower. Guard the guard: the two must differ.
    seed42 = sorted((hold["_total"].to_numpy() - (avg_pred - AVG_SHIFT + SEED_STEP * 42)).tolist())
    assert abs(np.mean(art["residuals"]) - np.mean(seed42)) > 10


def test_the_gate_and_both_arms_are_read_off_the_averages_residuals(tmp_path, stub_fit, no_database):
    res, _ = _fit_to(tmp_path, _frame())
    art = res["artifact"]
    assert art["d_threshold"] == ev.T_THRESHOLD == 8.0
    assert art["prob_at_threshold"] == pytest.approx(total_over_prob(art["residuals"], 8.0))
    assert art["prob_under_at_threshold"] == pytest.approx(
        1.0 - total_over_prob(art["residuals"], -8.0))
    assert art["market"] == "totals"
    assert art["train_seasons"] == [2021, 2022, 2023, 2024]
    assert art["feature_cols"] == list(ev.TOTAL_FEATURES)


def test_the_holdout_record_is_the_averages_record(tmp_path, stub_fit, no_database):
    """What the registry row will say the model did at the gate."""
    frame = _frame()
    res, _ = _fit_to(tmp_path, frame)

    hold = frame[frame["_season"] == 2024]
    avg_pred = 55.0 + 12.0 * hold[F0].to_numpy() + AVG_SHIFT
    want = next(r for r in ev.sweep_total(avg_pred, hold["_total_line"], hold["_total"])
                if r["threshold"] == 8.0)
    reg = res["artifact"]["registry"]
    assert want["bets"] > 30, "fixture no longer puts games at the gate"
    assert reg["holdout_picks"] == want["bets"]
    assert reg["holdout_accuracy"] == pytest.approx(want["win_rate"], abs=1e-4)
    assert reg["holdout_season"] == 2024

    # One member's record at the gate is a different set of games.
    lone = next(r for r in ev.sweep_total(avg_pred - AVG_SHIFT + SEED_STEP * 42,
                                          hold["_total_line"], hold["_total"])
                if r["threshold"] == 8.0)
    assert lone["bets"] != want["bets"]


# ── the kill line still refuses ───────────────────────────────────────────────

def test_a_fit_at_or_below_breakeven_at_the_gate_is_refused(tmp_path, stub_fit, no_database):
    frame = _frame(flip=(2024,))
    path = tmp_path / "frame.pkl"
    frame.to_pickle(path)
    out = tmp_path / "saved"
    with pytest.raises(SystemExit) as exc:
        ev.fit_totals([2021, 2022, 2023], 2024, frame_path=path, out_dir=out)
    assert "breakeven" in str(exc.value)
    assert not out.exists() or not list(out.iterdir()), "a refused fit wrote an artifact"
    # Refused on the eval fit: the final fit never ran.
    assert len(stub_fit) == 11


def test_a_fit_with_no_bets_at_the_gate_is_refused(tmp_path, stub_fit, no_database):
    frame = _frame(line="model")
    path = tmp_path / "frame.pkl"
    frame.to_pickle(path)
    out = tmp_path / "saved"
    with pytest.raises(SystemExit) as exc:
        ev.fit_totals([2021, 2022, 2023], 2024, frame_path=path, out_dir=out)
    assert "No bets" in str(exc.value)
    assert not out.exists() or not list(out.iterdir())


# ── fitting does not register ─────────────────────────────────────────────────

def test_fitting_writes_one_file_and_touches_no_database(tmp_path, stub_fit, no_database):
    saved = ROOT / "models" / "saved"
    before = sorted(p.name for p in saved.glob("*.pkl"))
    res, out = _fit_to(tmp_path, _frame())      # `no_database` raises on any reach
    assert [p.name for p in out.iterdir()] == [f"ncaaf_over_under_{res['version']}.pkl"]
    assert Path(res["path"]).parent == out
    assert sorted(p.name for p in saved.glob("*.pkl")) == before, (
        "a fit pointed at another directory still wrote into models/saved")
    assert res["artifact"]["version"] == res["version"]


def test_the_old_one_step_function_is_gone():
    """`fit_and_register_totals` wrote the file and switched the registry
    together. Nothing may bring that back under the old name."""
    assert not hasattr(ev, "fit_and_register_totals")
    src = inspect.getsource(ev.fit_totals)
    for needle in ("get_connection", "INSERT INTO", "UPDATE model_registry", ".execute("):
        assert needle not in src, f"fit_totals reaches for the registry: {needle}"


def test_the_frame_file_replaces_the_database_read(tmp_path, monkeypatch):
    frame = _frame()
    path = tmp_path / "frame.pkl"
    frame.to_pickle(path)
    monkeypatch.setattr(ev, "build_frames",
                        lambda seasons: (_ for _ in ()).throw(AssertionError("built from the database")))
    got = ev.load_frame([2022, 2023], path)
    assert sorted(got["_season"].unique().tolist()) == [2022, 2023]
    assert len(got) == 400
    # Row order is the file's: the fit subsamples rows, so order is part of it.
    assert got["_game_id"].tolist() == frame[frame["_season"].isin([2022, 2023])]["_game_id"].tolist()


def test_a_frame_file_missing_a_season_is_refused(tmp_path):
    path = tmp_path / "frame.pkl"
    _frame(seasons=(2021, 2022)).to_pickle(path)
    with pytest.raises(SystemExit) as exc:
        ev.load_frame([2021, 2022, 2023], path)
    assert "2023" in str(exc.value)


def test_without_a_frame_file_the_frame_is_built_as_before(monkeypatch):
    asked = []
    monkeypatch.setattr(ev, "build_frames", lambda seasons: asked.append(list(seasons)) or "built")
    assert ev.load_frame([2021, 2022]) == "built"
    assert asked == [[2021, 2022]]


# ── registering is its own step ───────────────────────────────────────────────

class _Conn:
    def __init__(self, events):
        self.events, self.committed, self.closed = events, False, False

    def execute(self, sql, params=None):
        self.events.append(("sql", " ".join(sql.split()), params))
        return self

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


@pytest.fixture
def registry(monkeypatch):
    """A recording stand-in for the database and for the artifact store."""
    import data.db
    import models.trainer as trainer

    events: list = []
    conn = _Conn(events)
    monkeypatch.setattr(data.db, "get_connection", lambda: conn)
    monkeypatch.setattr(trainer, "_store_artifact",
                        lambda c, model_id, version, path: events.append(
                            ("store", model_id, version, Path(path).name)))
    monkeypatch.setattr(ev, "_tracked_by_git", lambda path: True)
    return conn


def _fitted(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "_fit", lambda X, y, random_state=42: _Stub(random_state))
    res, out = _fit_to(tmp_path, _frame())
    return res, out


def test_register_takes_the_version_and_writes_the_row_the_fit_described(tmp_path, monkeypatch, registry):
    res, out = _fitted(tmp_path, monkeypatch)
    version = res["version"]
    assert registry.events == [], "fitting wrote to the registry"

    assert ev.register_totals(version, saved_dir=out) == version

    kinds = [e[0] for e in registry.events]
    assert kinds == ["store", "sql", "sql"], kinds
    # The bytes go in BEFORE the row that names them (models/trainer._register_model).
    assert registry.events[0] == ("store", "ncaaf_over_under", version,
                                  f"ncaaf_over_under_{version}.pkl")
    _, deactivate, _ = registry.events[1]
    assert deactivate.startswith("UPDATE model_registry SET is_active = 0")
    assert "model_id = 'ncaaf_over_under'" in deactivate
    _, insert, params = registry.events[2]
    assert insert.startswith("INSERT INTO model_registry")
    reg = res["artifact"]["registry"]
    assert params == (version, reg["trained_on"], reg["train_seasons"], reg["holdout_season"],
                      reg["holdout_accuracy"], reg["holdout_roi"], reg["holdout_picks"],
                      f"models/saved/ncaaf_over_under_{version}.pkl", reg["notes"])
    assert registry.committed and registry.closed


def test_register_refuses_a_version_with_no_file(tmp_path, registry):
    with pytest.raises(SystemExit) as exc:
        ev.register_totals("20990101_000000", saved_dir=tmp_path)
    assert "20990101_000000" in str(exc.value)
    assert registry.events == []


def test_register_refuses_a_file_git_is_not_tracking(tmp_path, monkeypatch, registry):
    """The worker deploys from git. A registry row naming a file that is in no
    commit is a model that is registered and absent."""
    res, out = _fitted(tmp_path, monkeypatch)
    monkeypatch.setattr(ev, "_tracked_by_git", lambda path: False)
    with pytest.raises(SystemExit) as exc:
        ev.register_totals(res["version"], saved_dir=out)
    assert "git" in str(exc.value)
    assert registry.events == []


def test_register_refuses_a_file_whose_contents_are_another_version(tmp_path, monkeypatch, registry):
    res, out = _fitted(tmp_path, monkeypatch)
    renamed = out / "ncaaf_over_under_20990101_000000.pkl"
    Path(res["path"]).rename(renamed)
    with pytest.raises(SystemExit):
        ev.register_totals("20990101_000000", saved_dir=out)
    assert registry.events == []


def test_register_refuses_an_artifact_of_another_kind(tmp_path, registry):
    path = tmp_path / "ncaaf_over_under_20990101_000000.pkl"
    path.write_bytes(pickle.dumps({"kind": "margin_regression", "version": "20990101_000000",
                                   "model": None}))
    with pytest.raises(SystemExit):
        ev.register_totals("20990101_000000", saved_dir=tmp_path)
    assert registry.events == []


# ── a game with no weather forecast yet ───────────────────────────────────────
#
# Found 2026-11-10 while checking the first eleven-seed artifact: the forecast
# step covers games 7 days out, the model scores any game DraftKings prices,
# and a served row with no weather is NaN. The frame the refit used has ONE
# row with missing weather, so the trees never learned where to send one, and
# the fit put a game with no forecast 11.7 points lower on average (the live
# fit of 2026-08-25: 1.9). Against an 8-point gate that is a bet made of
# nothing. So the fit measures it, and registering refuses when it is that big.

def test_the_fit_measures_what_a_missing_forecast_does_to_the_prediction(
        tmp_path, stub_fit, no_database, monkeypatch):
    monkeypatch.setattr(_Stub, "NAN_WIND_DROP", 11.0)
    res, _ = _fit_to(tmp_path, _frame())
    shift = res["artifact"]["missing_input_shift"]

    assert shift["rows"] == 200                      # the holdout season's games
    weather = shift["groups"]["weather"]
    assert weather["features"] == ["wx_temp_f", "wx_wind_mph", "wx_precip_mm"]
    assert weather["mean"] == pytest.approx(-11.0)
    assert weather["sd"] == pytest.approx(0.0, abs=1e-9)
    assert weather["at_gate_after"] > weather["at_gate_before"] > 0
    venue = shift["groups"]["venue"]
    assert venue["features"] == ["venue_elevation_ft", "is_dome_game", "is_grass"]
    assert venue["mean"] == pytest.approx(0.0, abs=1e-9)
    assert venue["at_gate_after"] == venue["at_gate_before"]
    assert shift["groups"]["weather+venue"]["mean"] == pytest.approx(-11.0)


def test_a_fit_that_ignores_missing_weather_measures_no_shift(tmp_path, stub_fit, no_database):
    res, _ = _fit_to(tmp_path, _frame())
    for group in res["artifact"]["missing_input_shift"]["groups"].values():
        assert group["mean"] == pytest.approx(0.0, abs=1e-9)


# What unlocks such an artifact is the scorer refusing to DECIDE a game whose
# weather is missing (models.scorer.totals_weather_hold). Registration proves
# it by calling it, so these tests put a hold in the scorer or take it out,
# whichever this checkout has.

def _a_working_hold(feature_cols, features):
    import math
    for c in ("wx_temp_f", "wx_wind_mph", "wx_precip_mm"):
        v = features.get(c)
        if c in feature_cols and (v is None or (isinstance(v, float) and math.isnan(v))):
            return "waiting for the weather forecast"
    return None


def _scorer_hold(monkeypatch, hold):
    import models.scorer as sc
    if hold is None:
        monkeypatch.delattr(sc, "totals_weather_hold", raising=False)
    else:
        monkeypatch.setattr(sc, "totals_weather_hold", hold, raising=False)


def test_register_refuses_a_model_a_missing_forecast_moves_past_the_gate(
        tmp_path, monkeypatch, registry):
    monkeypatch.setattr(_Stub, "NAN_WIND_DROP", 11.0)
    res, out = _fitted(tmp_path, monkeypatch)
    _scorer_hold(monkeypatch, None)                     # a scorer with no hold
    with pytest.raises(SystemExit) as exc:
        ev.register_totals(res["version"], saved_dir=out)
    assert "weather" in str(exc.value) and "11.0" in str(exc.value)
    assert registry.events == [], "a refused registration still wrote something"


def test_the_same_model_registers_once_the_scorer_holds_such_a_game(
        tmp_path, monkeypatch, registry):
    monkeypatch.setattr(_Stub, "NAN_WIND_DROP", 11.0)
    res, out = _fitted(tmp_path, monkeypatch)
    _scorer_hold(monkeypatch, _a_working_hold)
    ev.register_totals(res["version"], saved_dir=out)
    assert [e[0] for e in registry.events] == ["store", "sql", "sql"]


@pytest.mark.parametrize("broken", [
    lambda feature_cols, features: None,                           # never holds
    lambda feature_cols, features: "waiting",                      # holds everything
    lambda feature_cols, features: (                               # holds on wind only
        "waiting" if features.get("wx_wind_mph") is None else None),
], ids=["never holds", "holds every game", "ignores temperature and rain"])
def test_a_hold_that_does_not_do_the_job_unlocks_nothing(tmp_path, monkeypatch, registry, broken):
    """Registration calls the hold; a function with the right name is not proof."""
    monkeypatch.setattr(_Stub, "NAN_WIND_DROP", 11.0)
    res, out = _fitted(tmp_path, monkeypatch)
    _scorer_hold(monkeypatch, broken)
    with pytest.raises(SystemExit):
        ev.register_totals(res["version"], saved_dir=out)
    assert registry.events == []


def test_the_weather_hold_does_not_excuse_a_venue_shift(tmp_path, monkeypatch, registry):
    """The hold covers a missing forecast. A model that a missing VENUE alone
    moves past the gate is still refused."""
    monkeypatch.setattr(_Stub, "NAN_ELEV_DROP", 9.0)
    res, out = _fitted(tmp_path, monkeypatch)
    _scorer_hold(monkeypatch, _a_working_hold)
    with pytest.raises(SystemExit) as exc:
        ev.register_totals(res["version"], saved_dir=out)
    assert "venue" in str(exc.value)
    assert registry.events == []


def test_there_is_no_flag_that_registers_it_anyway():
    import inspect as _inspect
    assert "accept_missing_input_shift" not in _inspect.signature(ev.register_totals).parameters
    with pytest.raises(SystemExit):
        ev._build_parser().parse_args(["--register-totals", "v", "--accept-missing-input-shift"])


def test_register_passes_a_shift_smaller_than_the_gate(tmp_path, monkeypatch, registry):
    monkeypatch.setattr(_Stub, "NAN_WIND_DROP", 7.9)
    res, out = _fitted(tmp_path, monkeypatch)
    _scorer_hold(monkeypatch, None)
    ev.register_totals(res["version"], saved_dir=out)
    assert [e[0] for e in registry.events] == ["store", "sql", "sql"]


def test_register_refuses_an_artifact_that_never_measured_it(tmp_path, monkeypatch, registry):
    res, out = _fitted(tmp_path, monkeypatch)
    art = dict(res["artifact"])
    del art["missing_input_shift"]
    Path(res["path"]).write_bytes(pickle.dumps(art))
    with pytest.raises(SystemExit) as exc:
        ev.register_totals(res["version"], saved_dir=out)
    assert "measure" in str(exc.value)
    assert registry.events == []


def test_walk_forward_grades_the_rule_with_no_forecast_two_ways(monkeypatch, stub_fit):
    """What the rule would have done had every game been scored before its
    forecast existed: with the weather missing, and with it set to typical
    weather (the training seasons' medians)."""
    monkeypatch.setattr(_Stub, "NAN_WIND_DROP", 11.0)
    frame = _frame()
    monkeypatch.setattr(ev, "build_frames", lambda seasons: frame)
    res = ev.walk_forward_totals([2021, 2022, 2023, 2024], [2024])
    season = res["seasons"][0]

    hold = frame[frame["_season"] == 2024]
    base = 55.0 + 12.0 * hold[F0].to_numpy() + AVG_SHIFT

    def at8(pred):
        return next(r for r in ev.sweep_total(pred, hold["_total_line"], hold["_total"])
                    if r["threshold"] == 8.0)

    assert season["at_gate"] == at8(base)
    assert season["no_forecast"]["missing"] == at8(base - 11.0)
    assert season["no_forecast"]["typical"] == at8(base)      # a filled value is not missing
    assert season["no_forecast"]["missing"] != season["at_gate"]
    assert season["no_forecast"]["missing_shift"] == pytest.approx(-11.0)


def test_git_tracking_is_measured_not_assumed(tmp_path):
    live = ROOT / "models" / "saved" / "ncaaf_over_under_20260825_204305.pkl"
    assert ev._tracked_by_git(live) is True
    probe = ROOT / "tests" / "_untracked_probe_for_seed_fit.bin"
    probe.write_bytes(b"x")
    try:
        assert ev._tracked_by_git(probe) is False
    finally:
        probe.unlink(missing_ok=True)
    outside = tmp_path / "x.pkl"            # not inside any checkout: unknown, not "no"
    outside.write_bytes(b"x")
    assert ev._tracked_by_git(outside) is None


def test_the_command_line_keeps_the_two_steps_apart():
    parser = ev._build_parser()
    fit = parser.parse_args(["--fit-totals", "--frame", "f.pkl"])
    assert fit.fit_totals and fit.frame == "f.pkl" and fit.register_totals is None
    reg = parser.parse_args(["--register-totals", "20261110_120000"])
    assert reg.register_totals == "20261110_120000" and not reg.fit_totals


# ── the walk-forward reads the average too ────────────────────────────────────

def test_walk_forward_fits_eleven_seeds_on_earlier_seasons_only(monkeypatch, stub_fit):
    frame = _frame()
    monkeypatch.setattr(ev, "build_frames", lambda seasons: frame)
    res = ev.walk_forward_totals([2021, 2022, 2023, 2024], [2023, 2024])

    assert res["gate"] == 8.0, "the totals walk-forward must report the totals gate"
    assert res["seeds"] == SEEDS
    assert [s["season"] for s in res["seasons"]] == [2023, 2024]
    assert [c["seed"] for c in stub_fit] == SEEDS + SEEDS
    for c in stub_fit[:11]:
        assert set(frame.loc[c["index"], "_season"]) == {2021, 2022}
    for c in stub_fit[11:]:
        assert set(frame.loc[c["index"], "_season"]) == {2021, 2022, 2023}


def test_walk_forward_grades_the_average_and_each_seed_separately(monkeypatch, stub_fit):
    frame = _frame()
    monkeypatch.setattr(ev, "build_frames", lambda seasons: frame)
    res = ev.walk_forward_totals([2021, 2022, 2023, 2024], [2024])
    season = res["seasons"][0]

    hold = frame[frame["_season"] == 2024]
    base = 55.0 + 12.0 * hold[F0].to_numpy()

    def at8(pred):
        return next(r for r in ev.sweep_total(pred, hold["_total_line"], hold["_total"])
                    if r["threshold"] == 8.0)

    assert season["at_gate"] == at8(base + AVG_SHIFT)
    assert set(season["by_seed"]) == set(SEEDS)
    assert season["by_seed"][42] == at8(base + SEED_STEP * 42)
    assert season["by_seed"][0] == at8(base)
    assert season["by_seed"][42] != season["at_gate"]
    # Every game's eleven predictions are 0.5 * seed apart: one known spread.
    want_sd = float(np.std([SEED_STEP * s for s in SEEDS], ddof=1))
    assert res["seed_sd_mean"] == pytest.approx(want_sd)
    assert res["seed_sd_p95"] == pytest.approx(want_sd)
    assert res["games"] == len(hold)


def test_units_are_one_unit_to_win_at_minus_110():
    assert ev.units_at_minus_110(235, 426) == pytest.approx(235 - 1.1 * 191)
    assert ev.units_at_minus_110(0, 0) == 0.0


# ── the real fit ──────────────────────────────────────────────────────────────

# `_fit`'s settings as they were for the single fit of 2026-08-25. Only
# `random_state` may differ between the eleven members.
FIXED = {"n_estimators": 700, "learning_rate": 0.03, "max_depth": 5,
         "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 5,
         "objective": "reg:squarederror", "n_jobs": -1}


def test_the_eleven_fits_differ_only_in_their_seed(monkeypatch):
    """Every argument the fit hands xgboost, for each of the eleven members.
    (Eleven real 700-tree fits take minutes; the next test runs one.)"""
    import xgboost

    made = []

    class _Spy:
        def __init__(self, **kw):
            made.append(kw)
            self.kw = kw

        def fit(self, X, y):
            return self

        def predict(self, X):
            return np.full(len(X), float(self.kw["random_state"]))

    monkeypatch.setattr(xgboost, "XGBRegressor", _Spy)
    frame = _frame(seasons=(2021,), n=40)
    X, cols = ev._matrix(frame, ev.TOTAL_FEATURES)
    model = ev._fit_seed_average(X[cols], X["_total"])

    assert [kw["random_state"] for kw in made] == SEEDS
    for kw in made:
        assert {k: v for k, v in kw.items() if k != "random_state"} == FIXED
    assert model.seeds == SEEDS and len(model) == 11
    assert model.predict(X[cols]) == pytest.approx(np.full(40, sum(SEEDS) / 11))


def test_one_real_fit_carries_those_settings_and_its_seed():
    frame = _frame(seasons=(2021,), n=120)
    X, cols = ev._matrix(frame, ev.TOTAL_FEATURES)
    member = ev._fit(X[cols], X["_total"], random_state=7)
    params = member.get_params()
    assert {k: params[k] for k in FIXED} == FIXED
    assert params["random_state"] == 7
    assert np.isfinite(member.predict(X[cols])).all()


def test_the_single_fit_the_spread_paths_use_is_still_seed_42():
    assert inspect.signature(ev._fit).parameters["random_state"].default == 42


# ── the shipped artifact, and the floor that follows it ───────────────────────

def _shipped():
    saved = ROOT / "models" / "saved"
    newest = max(saved.glob("ncaaf_over_under_*.pkl"), key=lambda p: p.stem)
    with open(newest, "rb") as f:
        return newest, pickle.load(f)


def test_the_newest_totals_artifact_is_the_eleven_seed_average():
    from models.seed_average import SeedAverage

    path, art = _shipped()
    assert art["kind"] == "total_regression", path.name
    assert isinstance(art["model"], SeedAverage), (
        f"{path.name} is a single fit: the newest totals artifact must be the seed average")
    assert art["model"].seeds == SEEDS and len(art["model"]) == 11
    for seed, member in zip(SEEDS, art["model"].members):
        params = member.get_params()
        assert params["random_state"] == seed
        assert {k: params[k] for k in FIXED} == FIXED, f"seed {seed}: settings moved"
    assert art["d_threshold"] == 8.0
    assert art["train_seasons"] == [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]
    assert art["feature_cols"] == list(ev.TOTAL_FEATURES)
    assert art["residuals"] == sorted(art["residuals"]) and len(art["residuals"]) == 772
    assert path.stem == f"ncaaf_over_under_{art['version']}"
    assert art["registry"]["holdout_season"] == 2025

    # An ordinary game (the training frame's median of every input) through the
    # scorer's own call must come out near an ordinary total.
    typical = {
        "home_points_per_game": 29.4, "away_points_per_game": 29.1,
        "home_points_allowed_pg": 25.7, "away_points_allowed_pg": 26.0,
        "home_plays_per_game": 69.1, "away_plays_per_game": 69.1,
        "home_epa_per_play_off": 0.18, "away_epa_per_play_off": 0.18,
        "home_epa_per_play_def": 0.14, "away_epa_per_play_def": 0.15,
        "home_sp_offense": 29.2, "away_sp_offense": 28.4,
        "home_sp_defense": 26.7, "away_sp_defense": 27.6,
        "week": 7, "is_neutral_site": 0, "is_conference_game": 1, "game_tier": 0,
        "is_early_season": 0, "venue_elevation_ft": 610.6, "is_dome_game": 0,
        "is_grass": 0, "wx_temp_f": 70.7, "wx_wind_mph": 7.0, "wx_precip_mm": 0.0,
    }
    x = np.array([[typical[c] for c in art["feature_cols"]]], dtype=float)
    assert 50.0 < float(art["model"].predict(x)[0]) < 65.0


def test_the_newest_artifact_registers_only_with_the_weather_hold_in_the_scorer(
        monkeypatch, registry):
    """The real file through the real check, both ways. A missing forecast
    moves the eleven-seed fit 11.66 points, so it must be refused by a scorer
    with no hold and accepted by one that holds such a game. Its venue shift
    (2.05) is under the gate, so the hold is all it needs."""
    path, art = _shipped()
    shift = art["missing_input_shift"]
    assert shift["rows"] > 700, "measured on too few games to mean anything"
    assert abs(shift["groups"]["weather"]["mean"]) >= art["d_threshold"]
    assert abs(shift["groups"]["venue"]["mean"]) < art["d_threshold"]

    _scorer_hold(monkeypatch, None)
    with pytest.raises(SystemExit) as exc:
        ev.register_totals(art["version"])
    assert "weather" in str(exc.value)
    assert registry.events == []

    _scorer_hold(monkeypatch, _a_working_hold)
    ev.register_totals(art["version"])
    assert [e[0] for e in registry.events] == ["store", "sql", "sql"]


def test_this_checkouts_own_scorer_decides_whether_it_registers(registry):
    """No stand-ins: whatever models/scorer.py is in this checkout. With the
    weather hold shipped the artifact registers; without it, it is refused."""
    path, art = _shipped()
    if ev._scorer_holds_missing_weather():
        ev.register_totals(art["version"])
        assert [e[0] for e in registry.events] == ["store", "sql", "sql"]
    else:
        with pytest.raises(SystemExit):
            ev.register_totals(art["version"])
        assert registry.events == []


def test_the_probability_floor_admits_both_arms_exactly_at_the_gate():
    """The scorer enforces the 8-point gate directly; the floor must never
    suppress a pick the gate admits (config.py, beside the entries). Checked
    on every totals artifact in the repo, because between the merge and the
    registration the OLDER one is still the one scoring."""
    import config

    floor = config.MODEL_PROB_THRESHOLDS["ncaaf_over_under"]
    assert config.ACTION_THRESHOLDS["ncaaf_over_under"]["min_prob"] == floor
    saved = ROOT / "models" / "saved"
    seen = 0
    for path in sorted(saved.glob("ncaaf_over_under_*.pkl")):
        with open(path, "rb") as f:
            art = pickle.load(f)
        gate = art["d_threshold"]
        over = total_over_prob(art["residuals"], gate)
        under = 1.0 - total_over_prob(art["residuals"], -gate)
        assert over >= floor, f"{path.name}: an over at +{gate} is {over:.4f}, under the {floor} floor"
        assert under >= floor, f"{path.name}: an under at -{gate} is {under:.4f}, under the {floor} floor"
        seen += 1
    assert seen >= 2, "expected the live artifact and the seed average side by side"

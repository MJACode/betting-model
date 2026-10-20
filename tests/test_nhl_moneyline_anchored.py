"""The rebuilt NHL moneyline (models/nhl_moneyline_anchored.py, mike 2026-10-13/15).

What these pin, each a way the live number could silently stop being the graded one:
  - tonight's inputs are built exactly like the training rows (the as-of property
    the walk-forward's 9,316/9,316 check measured), and no later result leaks back;
  - the model, with nothing to say, returns the market's price;
  - it decides only in the graded window, with both listed goalies, and its
    other rows are NONE with the reason -- never AVOID;
  - the generic trainer cannot overwrite it with the retired design;
  - the committed artifact is the kind the scorer reads.
"""
from __future__ import annotations

import pickle
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
import models.nhl_moneyline_anchored as anc

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "models" / "saved" / "nhl_moneyline_20261013_225002.pkl"
TEAMS = ["BOS", "TOR", "MTL", "OTT"]


def _logs(seed: int = 3, n_dates: int = 70) -> dict:
    """A small league: every date two games, every team one start a game from
    one of two goalies, random box scores."""
    rng = np.random.default_rng(seed)
    team, goalie, games = [], [], []
    nid = 2025020000
    for i in range(n_dates):
        d = (pd.Timestamp("2025-10-07") + pd.Timedelta(days=int(i * 1.5))).strftime("%Y-%m-%d")
        order = rng.permutation(TEAMS)
        for home, away in ((order[0], order[1]), (order[2], order[3])):
            nid += 1
            gid = f"NHL_{d}_{away}_{home}"
            hs, as_ = int(rng.poisson(3.1)), int(rng.poisson(2.9))
            games.append({"game_id": gid, "game_date": d, "season": 2026, "home": home,
                          "away": away, "hs": hs, "as_": as_})
            for t, o, ih, gf, ga in ((home, away, 1, hs, as_), (away, home, 0, as_, hs)):
                sf, sa = int(rng.integers(22, 38)), int(rng.integers(22, 38))
                team.append({"nhl_game_id": nid, "game_id": gid, "team": t, "opponent": o,
                             "season": 2026, "game_date": d, "is_home": ih, "goals_for": gf,
                             "goals_against": ga, "shots_for": sf, "shots_against": sa,
                             "sat_for_5v5": int(rng.integers(35, 60)),
                             "sat_against_5v5": int(rng.integers(35, 60)),
                             "pp_opportunities": int(rng.integers(1, 5)), "pp_goals": int(rng.integers(0, 2)),
                             "times_shorthanded": int(rng.integers(1, 5)),
                             "pp_goals_against": int(rng.integers(0, 2)),
                             "faceoff_win_pct": float(rng.uniform(0.4, 0.6))})
                goalie.append({"nhl_game_id": nid, "game_id": gid, "team": t,
                               "player_id": f"{t}{int(rng.integers(1, 3))}", "game_date": d, "started": 1,
                               "shots_against": sa, "goals_against": ga, "toi_seconds": 3600})
    return {"team": pd.DataFrame(team), "goalie": pd.DataFrame(goalie), "games": pd.DataFrame(games)}


def _served(logs: dict, day: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score `day` the way production does: logs cut to the morning, the games
    as upcoming rows, the goalie who started each as the listed one."""
    cut = {k: v[v.game_date.astype(str).str[:10] < day] for k, v in logs.items()}
    today = logs["games"][logs["games"].game_date == day][["game_id", "game_date", "season", "home", "away"]]
    st = logs["goalie"][logs["goalie"].game_id.isin(today.game_id)][["game_id", "team", "player_id"]]
    today = today.merge(st.rename(columns={"team": "home", "player_id": "home_goalie_id"}), on=["game_id", "home"])
    today = today.merge(st.rename(columns={"team": "away", "player_id": "away_goalie_id"}), on=["game_id", "away"])
    served = anc.build_inputs(cut, upcoming=today)
    return served[served.game_id.isin(today.game_id)].set_index("game_id"), today


def test_tonights_inputs_equal_the_training_rows():
    logs = _logs()
    trained = anc.build_inputs(logs).set_index("game_id")
    checked = 0
    for day in sorted(logs["games"].game_date.unique())[30::7]:
        served, today = _served(logs, day)
        for gid in today.game_id:
            for f in anc.FEATURES:
                a, b = served.at[gid, f], trained.at[gid, f]
                assert (pd.isna(a) and pd.isna(b)) or abs(float(a) - float(b)) < 1e-9, (day, gid, f, a, b)
                checked += 1
    assert checked > 200


def test_a_later_result_cannot_reach_an_earlier_game():
    logs = _logs()
    day = sorted(logs["games"].game_date.unique())[40]
    before = anc.build_inputs(logs).set_index("game_id")
    later = {k: v.copy() for k, v in logs.items()}
    after = later["team"].game_date > day
    later["team"].loc[after, "goals_for"] += 6
    later["team"].loc[after, "shots_for"] += 20
    later["goalie"].loc[later["goalie"].game_date > day, "goals_against"] += 6
    later["games"].loc[later["games"].game_date > day, "hs"] += 6
    changed = anc.build_inputs(later).set_index("game_id")
    for gid in logs["games"][logs["games"].game_date == day].game_id:
        for f in anc.FEATURES:
            a, b = before.at[gid, f], changed.at[gid, f]
            assert (pd.isna(a) and pd.isna(b)) or abs(float(a) - float(b)) < 1e-9, (gid, f)


def test_with_nothing_to_say_it_returns_the_market():
    # 20,000 games of pure noise: what is left of the inputs is sampling noise
    # (measured: mean 0.004-0.007, max 0.022-0.037 over three seeds).
    rng = np.random.default_rng(0)
    n = 20000
    X = rng.normal(size=(n, 5))
    p_mkt = rng.uniform(0.3, 0.7, n)
    y = (rng.uniform(size=n) < p_mkt).astype(float)
    m = anc.OffsetLogit(0.003).fit(X, y, anc.market_logit(p_mkt))
    p = m.predict_proba(X, anc.market_logit(p_mkt))[:, 1]
    assert np.mean(np.abs(p - p_mkt)) < 0.01
    assert np.max(np.abs(p - p_mkt)) < 0.05


@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 10, 16, 10, 0, tzinfo=timezone.utc), "decides on game day"),
    (datetime(2026, 10, 16, 16, 22, tzinfo=timezone.utc), None),
    (datetime(2026, 10, 16, 17, 22, tzinfo=timezone.utc), None),
    (datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc), "window closed"),
    (datetime(2026, 10, 15, 16, 30, tzinfo=timezone.utc), "decides on game day"),
])
def test_the_decision_window(now, expected):
    reason = anc.decision_window("2026-10-16", "2026-10-16T23:00:00Z", now=now)
    assert (reason is None) if expected is None else (expected in reason)


def test_a_matinee_closes_the_window_at_puck_drop():
    now = datetime(2026, 10, 16, 17, 5, tzinfo=timezone.utc)
    assert "window closed" in anc.decision_window("2026-10-16", "2026-10-16T17:00:00Z", now=now)


class _Fixed:
    """A model that says the home side wins 30% of the time, whatever it is told."""

    def predict_proba(self, X, offset):
        return np.array([[0.70, 0.30]])


def _wire(monkeypatch, *, window=None, goalies=("OTT", "STL"), nan=False, stale=()):
    import models.scorer as sc
    artifact = {"kind": anc.KIND, "model": _Fixed(), "feature_cols": list(anc.FEATURES)}
    monkeypatch.setattr(sc, "load_model", lambda mid: artifact)
    # home OTT +150 (0.40), away STL -170 (0.63)
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: {
        "home_price": 150.0, "away_price": -170.0, "spread_home": None, "total_line": None})
    monkeypatch.setattr(sc, "_get_public_betting", lambda conn, gid, market, side: {
        "public_bet_pct": None, "public_money_pct": None})
    for name in ("_stamp_best_game_prices", "_apply_game_injury_gate", "_apply_game_market_gate"):
        monkeypatch.setattr(sc, name, lambda *a, **k: None)
    gid = "NHL_2026-10-16_STL_OTT"
    rows = pd.DataFrame([{f: (np.nan if nan else 0.0) for f in anc.FEATURES}], index=[gid])
    listed = {(gid, t): "1" for t in goalies}
    monkeypatch.setattr(anc, "inputs_for_date", lambda conn, d: (rows, listed, set(stale)))
    monkeypatch.setattr(anc, "decision_window", lambda d, ct, now=None: window)
    return sc.score_game(None, gid, "nhl_moneyline",
                         {"home_team": "OTT", "away_team": "STL", "game_date": "2026-10-16"},
                         bankroll=1000.0, dry_run=True, commence_time="2026-10-16T23:00:00Z")


def test_in_the_window_it_bets_ev_and_never_writes_avoid(monkeypatch):
    picks = {p["pick_side"]: p for p in _wire(monkeypatch)}
    # away: 0.70 at -170 -> EV 0.112 >= 0.06
    assert picks["away"]["signal_type"] == "BET"
    assert picks["away"]["model_probability"] == pytest.approx(0.70, abs=1e-4)
    # home: 0.30 at +150 -> edge -0.10; the stock path calls that AVOID, this rule does not
    assert picks["home"]["signal_type"] == "NONE"
    # the stock tier reads the DraftKings edge (the home row's -0.10 -> LOW);
    # an EV rule carries a fixed MED on every row
    assert {p["confidence_tier"] for p in picks.values()} == {"MED"}


def test_outside_the_window_every_row_is_none_with_the_reason(monkeypatch):
    picks = _wire(monkeypatch, window="decides on game day from 16:00Z, with both listed goalies")
    assert picks and all(p["signal_type"] == "NONE" for p in picks)
    assert all("decides on game day" in (p.get("downgrade_reason") or "") for p in picks)


def test_without_both_listed_goalies_it_does_not_decide(monkeypatch):
    picks = _wire(monkeypatch, goalies=("OTT",))
    assert picks and all(p["signal_type"] == "NONE" for p in picks)
    assert all("listed goalies" in (p.get("downgrade_reason") or "") for p in picks)


def test_without_last_nights_logs_it_does_not_decide(monkeypatch):
    picks = _wire(monkeypatch, stale=("STL",))
    assert picks and all(p["signal_type"] == "NONE" for p in picks)
    assert all("last night's game logs" in (p.get("downgrade_reason") or "") for p in picks)


class _GamesConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        rows = self.rows

        class _R:
            def fetchall(self_inner):
                return rows
        return _R()


def test_a_scheduled_game_missing_from_the_logs_marks_both_teams_stale():
    logs = {"team": pd.DataFrame({"game_id": ["NHL_2026-10-15_BOS_TOR", "NHL_2026-10-15_BOS_TOR"]})}
    conn = _GamesConn([("NHL_2026-10-15_BOS_TOR", "TOR", "BOS"), ("NHL_2026-10-15_STL_OTT", "OTT", "STL")])
    assert anc.stale_teams(conn, logs, "2026-10-16") == {"OTT", "STL"}


def test_a_missing_input_skips_the_game(monkeypatch):
    assert _wire(monkeypatch, nan=True) == []


def test_no_draftkings_price_no_row(monkeypatch):
    import models.scorer as sc
    _wire(monkeypatch)
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: None)
    assert sc.score_game(None, "NHL_2026-10-16_STL_OTT", "nhl_moneyline",
                         {"home_team": "OTT", "away_team": "STL", "game_date": "2026-10-16"},
                         bankroll=1000.0, dry_run=True) == []


def test_the_generic_trainer_refuses_it():
    import models.trainer as tr
    with pytest.raises(ValueError, match="nhl_moneyline_anchored_train"):
        tr.train_model("nhl_moneyline")
    assert "nhl_moneyline" in tr.OWN_FIT_PATH


def test_the_settings_it_was_graded_on():
    m = "nhl_moneyline"
    assert m in config.MODELS_ON_OWN_PROBABILITY
    assert config.min_ev_for(m) == pytest.approx(0.06)
    assert config.MODEL_PROB_THRESHOLDS[m] == 0.0 and config.MODEL_EDGE_THRESHOLDS[m] == 0.0
    assert config.ACTION_THRESHOLDS[m] == {"min_prob": 0.0, "min_edge": 0.0}
    assert config.min_odds_for(m) == -200          # the floor the grade was taken with
    r = "nhl_moneyline_regulation"
    assert config.ACTION_THRESHOLDS[r] == {"min_prob": 0.40, "min_edge": 0.05}


def test_the_committed_artifact_is_the_kind_the_scorer_reads():
    with open(ARTIFACT, "rb") as fh:
        art = pickle.load(fh)
    assert art["kind"] == anc.KIND and art["model_id"] == "nhl_moneyline"
    assert art["feature_cols"] == anc.FEATURES
    assert art["train_seasons"] == list(range(2021, 2027))
    m = art["model"]
    p = m.predict_proba(m.mu.reshape(1, -1), [0.0])[0, 1]     # an average game priced at even
    assert 0.4 < p < 0.6

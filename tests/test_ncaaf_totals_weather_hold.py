"""The NCAAF totals model does not decide a game whose weather forecast is missing.

WHY. The forecast step (run_pipeline.step_ncaaf_weather) writes weather for
games up to 7 days out, once a day, and the totals rule scores any game
DraftKings prices. A game scored before its forecast exists is served with
its three weather inputs missing, and a tree sends a missing value wherever
its training rows happened to teach it: of 7,570 training games one has no
weather. Measured 2026-11-10, a game with no forecast reads 1.9 points low on
the live fit and 11.7 low on the eleven-seed fit, against a gate of 8. That
number is not a prediction, so the model must not bet on it.

THE RULE. While any of the three weather inputs is missing at scoring time
the game's rows are written NONE with the reason, like a schedule hold. A
NONE row never locks, so the first pass after the forecast exists decides the
game. A BET that is already locked is never scored again, so it is never
touched. A dome game has no forecast to wait for: its weather is 72 F, no
wind, no rain in training rows and at serve time alike, so that is what it is
served. Only the totals model reads these inputs, so only it is held.

BUILT AHEAD OF MIKE'S ANSWER (2026-11-10) and kept in one commit so it can be
taken or left on its own.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import models.scorer as scorer  # noqa: E402

WEATHER = ("wx_temp_f", "wx_wind_mph", "wx_precip_mm")
COLS = ["home_points_per_game", "is_dome_game", *WEATHER]
WAIT = "waiting for the weather forecast"
GAME = "NCAAF_2026-11-21_usc_wisconsin"


class _Reg:
    """61 points with the weather known. With ANY weather input missing, 44:
    8.5 under a 52.5 line, which is a bettable under at the gate. So a scorer
    with no hold turns a missing forecast into an under BET."""

    def __init__(self):
        self.seen = []

    def predict(self, x):
        x = np.asarray(x, dtype=float)
        self.seen.append(x.copy())
        return [44.0 if np.isnan(x[0, 2:5]).any() else 61.0]


def _features(**over):
    f = {"home_points_per_game": 31.0, "is_dome_game": 0, "wx_temp_f": 61.0,
         "wx_wind_mph": 9.0, "wx_precip_mm": 0.0, "home_team": "Wisconsin",
         "away_team": "USC", "game_date": "2026-11-21"}
    f.update(over)
    return f


def _no_forecast(**over):
    return _features(wx_temp_f=None, wx_wind_mph=None, wx_precip_mm=None, **over)


def _score(monkeypatch, features, *, model_id="ncaaf_over_under", reg=None, artifact=None,
           paused=False):
    reg = reg or _Reg()
    art = artifact or {"kind": "total_regression", "model": reg, "feature_cols": COLS,
                       "residuals": sorted(float(v) for v in range(-20, 21)),
                       "d_threshold": 8.0}
    odds = {"total_line": 52.5, "over_price": -110.0, "under_price": -110.0,
            "spread_home": -3.5, "home_price": -110.0, "away_price": -110.0}
    monkeypatch.setattr(scorer, "load_model", lambda mid: art)
    monkeypatch.setattr(scorer, "_get_scoring_odds", lambda *a, **k: dict(odds))
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: dict(odds))
    monkeypatch.setattr(scorer, "_get_public_betting", lambda *a, **k: {})
    for name in ("_stamp_best_game_prices", "_apply_game_injury_gate",
                 "_apply_game_market_gate"):
        monkeypatch.setattr(scorer, name, lambda *a, **k: None)
    monkeypatch.setattr(scorer, "_is_paused", lambda mid: paused)
    picks = scorer.score_game(None, GAME, model_id, features, bankroll=1000.0,
                              dry_run=True, commence_time="2026-11-21T20:30:00Z")
    return picks, reg


# ── the hold ──────────────────────────────────────────────────────────────────

def test_with_its_forecast_the_game_is_decided(monkeypatch):
    """The control: 61 against 52.5 is 8.5 over the line, a bet."""
    picks, _ = _score(monkeypatch, _features())
    over = next(p for p in picks if p["pick_side"] == "over")
    assert over["signal_type"] == "BET"
    assert over["model_probability"] == pytest.approx(29 / 41, abs=1e-4)


def test_a_game_with_no_forecast_is_none_with_the_reason_and_no_bet(monkeypatch):
    picks, _ = _score(monkeypatch, _no_forecast())
    assert {p["pick_side"] for p in picks} == {"over", "under"}, (
        "a held game must still write its rows: an empty board and a broken "
        "pipeline look the same")
    assert {p["signal_type"] for p in picks} == {"NONE"}, (
        "a missing forecast was bet: " + str([(p["pick_side"], p["signal_type"]) for p in picks]))
    assert {p["downgrade_reason"] for p in picks} == {WAIT}
    assert all(p["recommended_bet"] == 0.0 and p["kelly_fraction"] == 0.0 for p in picks)
    assert {p["scored_line"] for p in picks} == {52.5}, "the row carries DraftKings' number"


@pytest.mark.parametrize("gone", WEATHER)
def test_one_missing_weather_input_is_enough_to_hold(monkeypatch, gone):
    picks, _ = _score(monkeypatch, _features(**{gone: None}))
    assert picks and {p["signal_type"] for p in picks} == {"NONE"}
    assert {p["downgrade_reason"] for p in picks} == {WAIT}


def test_a_held_row_carries_no_number_from_the_model(monkeypatch):
    """With no forecast the model's number is not a prediction, so it is not
    stored as one: both sides read 0.5. (Storing the real output would also
    lose the row: most such numbers pass the stale-line cap, which writes
    nothing at all.)"""
    picks, reg = _score(monkeypatch, _no_forecast())
    assert {p["model_probability"] for p in picks} == {0.5}
    assert reg.seen == [], "the model was asked to predict a game it may not decide"


def test_a_paused_models_held_row_keeps_the_pause_note(monkeypatch):
    """As a schedule hold does: every paused-row exclusion keys on that note."""
    picks, _ = _score(monkeypatch, _no_forecast(), paused=True)
    assert picks and {p["signal_type"] for p in picks} == {"NONE"}
    assert {p["downgrade_reason"] for p in picks} == {config.PAUSED_NOTE}


def test_a_game_with_no_draftkings_total_writes_nothing_held_or_not(monkeypatch):
    monkeypatch.setattr(scorer, "load_model", lambda mid: {
        "kind": "total_regression", "model": _Reg(), "feature_cols": COLS,
        "residuals": [0.0], "d_threshold": 8.0})
    monkeypatch.setattr(scorer, "_get_scoring_odds", lambda *a, **k: None)
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: None)
    assert scorer.score_game(None, GAME, "ncaaf_over_under", _no_forecast(),
                             bankroll=1000.0, dry_run=True) == []


def test_nan_is_missing_too(monkeypatch):
    picks, _ = _score(monkeypatch, _features(wx_wind_mph=float("nan")))
    assert {p["downgrade_reason"] for p in picks} == {WAIT}


def test_the_same_game_is_decided_on_the_next_pass_once_the_forecast_exists(monkeypatch):
    first, _ = _score(monkeypatch, _no_forecast())
    assert {p["signal_type"] for p in first} == {"NONE"}
    second, _ = _score(monkeypatch, _features())
    over = next(p for p in second if p["pick_side"] == "over")
    assert over["signal_type"] == "BET" and not over.get("downgrade_reason")


def test_a_real_zero_is_weather_not_a_missing_value(monkeypatch):
    """No wind and no rain are 0.0. Only None and NaN are missing."""
    picks, _ = _score(monkeypatch, _features(wx_wind_mph=0.0, wx_precip_mm=0.0))
    assert next(p for p in picks if p["pick_side"] == "over")["signal_type"] == "BET"


# ── a dome game is not held for ever ──────────────────────────────────────────

def test_a_dome_game_with_no_weather_row_is_served_the_dome_values_and_decided(monkeypatch):
    """A dome's weather is 72 F, no wind, no rain in 312 of the 328 dome games
    of the training frame, and the forecast step writes the same for a dome it
    reaches. A dome it never reaches (no coordinates on the venue, or more
    than 7 days out) would wait for a forecast that is not coming."""
    picks, reg = _score(monkeypatch, _no_forecast(is_dome_game=1))
    over = next(p for p in picks if p["pick_side"] == "over")
    assert over["signal_type"] == "BET", over.get("downgrade_reason")
    assert reg.seen[0][0, 2:5].tolist() == [72.0, 0.0, 0.0]
    assert reg.seen[0][0, 1] == 1.0


def test_a_dome_games_own_weather_row_is_not_overwritten(monkeypatch):
    picks, reg = _score(monkeypatch, _features(is_dome_game=1, wx_temp_f=68.0))
    assert reg.seen[0][0, 2:5].tolist() == [68.0, 9.0, 0.0]


def test_an_outdoor_game_is_never_given_the_dome_values(monkeypatch):
    picks, reg = _score(monkeypatch, _no_forecast(is_dome_game=0))
    assert {p["downgrade_reason"] for p in picks} == {WAIT}
    assert reg.seen == []


def test_the_dome_values_are_the_ones_the_weather_step_writes():
    """One convention, three places: the backfill that made the training rows,
    the forecast step, and the scorer."""
    from features.ncaaf_feature_engine import DOME_WEATHER

    assert DOME_WEATHER == {"wx_temp_f": 72.0, "wx_wind_mph": 0.0, "wx_precip_mm": 0.0}
    src = (ROOT / "scripts" / "ncaaf_weather_backfill.py").read_text(encoding="utf-8")
    assert '{"temp_f": 72.0, "wind_mph": 0.0, "precip_mm": 0.0, "is_dome": 1}' in src
    assert "VALUES (%s, %s, %s, %s, 72.0, 0.0, NULL, 0.0, 0.0, 1, %s)" in src


def test_a_neutral_site_game_with_its_forecast_is_decided_like_any_other(monkeypatch):
    """The forecast step fetches a neutral-site game at its own venue, or at
    the home team's usual one until the venue is known, so it gets a row like
    any game. Nothing about the site holds it."""
    picks, _ = _score(monkeypatch, _features(is_neutral_site=1))
    assert next(p for p in picks if p["pick_side"] == "over")["signal_type"] == "BET"


# ── this model only ───────────────────────────────────────────────────────────

def test_only_the_totals_model_reads_the_weather_inputs():
    from features.feature_engine import FEATURE_MAP

    readers = sorted(m for m, cols in FEATURE_MAP.items()
                     if m.startswith("ncaaf") and set(WEATHER) & set(cols))
    assert readers == ["ncaaf_over_under"], readers


def test_another_ncaaf_model_is_not_held_by_a_missing_forecast(monkeypatch):
    """The spread rule on the same game, same missing weather: its rows do not
    carry the weather reason."""
    class _Clf:
        def predict_proba(self, X):
            return np.array([[0.42, 0.58]])

    picks, _ = _score(monkeypatch, _no_forecast(), model_id="ncaaf_moneyline",
                      artifact={"model": _Clf(), "feature_cols": ["home_points_per_game"]})
    assert picks, "the other model wrote nothing"
    assert WAIT not in {p.get("downgrade_reason") for p in picks}


def test_a_total_regression_without_weather_inputs_is_not_held(monkeypatch):
    """The hold is about inputs the model reads. An artifact that does not
    list them has nothing to wait for."""
    class _Flat:
        def predict(self, x):
            return [61.0]

    art = {"kind": "total_regression", "model": _Flat(),
           "feature_cols": ["home_points_per_game"],
           "residuals": sorted(float(v) for v in range(-20, 21)), "d_threshold": 8.0}
    picks, _ = _score(monkeypatch, _no_forecast(), artifact=art)
    assert next(p for p in picks if p["pick_side"] == "over")["signal_type"] == "BET"


def test_the_hold_function_is_the_one_registration_asks():
    """scripts/ncaaf_margin_eval.register_totals calls this to prove a game
    with missing weather cannot be decided, before it lets the eleven-seed
    artifact go live."""
    hold = scorer.totals_weather_hold
    full = {c: 1.0 for c in WEATHER}
    assert hold(list(WEATHER), full) is None
    assert hold(list(WEATHER), {}) == WAIT
    for c in WEATHER:
        assert hold(list(WEATHER), {**full, c: None}) == WAIT
    assert hold(["home_points_per_game"], {}) is None

    import scripts.ncaaf_margin_eval as ev
    assert ev._scorer_holds_missing_weather() is True


# ── a locked BET is untouched, and NONE never locks ───────────────────────────

TODAY = date.today()
NOW = datetime.now(timezone.utc)
SOON = f"NCAAF_{(TODAY + timedelta(days=9)).isoformat()}_usc_wisconsin"


class _Board:
    """Enough of Postgres for run_scorer: one NCAAF game nine days out, priced,
    with no earlier game to wait for, and whatever BETs the picks table holds."""

    def __init__(self, bets=()):
        self.bets = list(bets)
        self._sql = ""
        d9 = (TODAY + timedelta(days=9)).isoformat()
        t9 = (NOW + timedelta(days=9)).isoformat()
        self.board = [(SOON, "NCAAF", 2026, d9, "Wisconsin", "USC", t9)]
        self.schedule = [(SOON, d9, "Wisconsin", "USC", t9, None, None)]

    def execute(self, sql, params=None):
        self._sql = " ".join(sql.split())
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        s = self._sql
        if "commence_time, home_score, away_score FROM games" in s:
            return self.schedule
        if s.startswith("SELECT s.game_id FROM games s"):
            return [(SOON,)]
        if "ORDER BY sport, game_date" in s:
            return self.board
        if "FROM games g" in s and "EXISTS" in s:
            return [(SOON,)]
        if "FROM picks p" in s and "signal_type = 'BET'" in s:
            return self.bets
        return []

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _run(monkeypatch, bets):
    """run_scorer for real (locks on), with score_game replaced by a recorder."""
    conn = _Board(bets)
    monkeypatch.setattr(scorer, "get_connection", lambda: conn)
    monkeypatch.setattr(scorer, "_get_postponed_games", lambda _d: set())
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: {"home_price": -110})
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda *a, **k: 1000.0)
    import features.ncaaf_feature_engine as nfe
    monkeypatch.setattr(nfe, "build_ncaaf_game_features", lambda *a, **k: _no_forecast())
    scored = []

    def _record(conn_, game_id, model_id, *a, **k):
        scored.append((game_id, model_id))
        return []

    monkeypatch.setattr(scorer, "score_game", _record)
    monkeypatch.setattr(scorer, "LOCK_GAME_PICKS_AT_FIRST_RUN", True)
    scorer.run_scorer(TODAY.isoformat(), dry_run=False)
    return scored


def test_a_held_game_is_scored_again_on_every_pass(monkeypatch):
    """Its rows are NONE, and only a BET locks, so nothing stops the next pass
    from deciding it once the forecast is there."""
    scored = _run(monkeypatch, bets=[])
    assert (SOON, "ncaaf_over_under") in scored, scored


def test_a_locked_bet_is_never_scored_again_so_the_hold_cannot_touch_it(monkeypatch):
    """The game has no forecast and a BET already stands on it. The scorer
    does not reach it at all: the bet of record stays as it was written."""
    scored = _run(monkeypatch, bets=[(SOON, "ncaaf_over_under")])
    assert (SOON, "ncaaf_over_under") not in scored, (
        "a locked BET was scored again: the hold could have rewritten it")
    assert any(g == SOON for g, _ in scored), "the game's other models were not scored"

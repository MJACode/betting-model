"""The schedule gate in the generic pre-game scorer (data/schedule_context).

mike, 2026-10-20: "The repo/models should look ahead schedules for all markets
and sports and models."

A pre-game model must not decide while either team still has an earlier game
not played, being played, or played but not yet in the logs its inputs read.
The shapes below are the measured ones: pick 3688041 (Wisconsin vs USC Under
52.5, decided 10-17 10:22Z, 13 hours before Wisconsin played at UCLA), the
WNBA postseason picks written while game N was still on, and a UFC card not
yet in the fight log.

No database: the connection is a stand-in that answers the scorer's reads.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

import config
import models.scorer as scorer

TODAY = date.today()
NOW = datetime.now(timezone.utc)


def _d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _t(hours: float) -> str:
    return (NOW + timedelta(hours=hours)).isoformat()


class _BoardConn:
    """Enough of Postgres for run_scorer: the board, the price pre-filters,
    the stored schedule, the logs and the BET lock read."""

    def __init__(self, board, schedule, *, priced=(), ncaaf_log=(), ufc_cards=(),
                 bets=(), fail_schedule=False):
        self.board = board                    # run_scorer's game list (7-tuples)
        self.schedule = schedule              # games rows, 7 columns
        self.priced = set(priced)
        self.ncaaf_log = list(ncaaf_log)
        self.ufc_cards = list(ufc_cards)
        self.bets = list(bets)
        self.fail_schedule = fail_schedule
        self._sql = ""

    def execute(self, sql, params=None):
        self._sql = " ".join(sql.split())
        if self.fail_schedule and "commence_time, home_score, away_score FROM games" in self._sql:
            raise RuntimeError("statement timeout")
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        s = self._sql
        if "commence_time, home_score, away_score FROM games" in s:
            return self.schedule
        if "FROM ncaaf_team_game_log" in s:
            return self.ncaaf_log
        if "FROM ufc_fight_log" in s:
            return [(c,) for c in self.ufc_cards]
        if s.startswith("SELECT DISTINCT game_id FROM odds"):
            return [(g,) for g in self.priced]
        if "ORDER BY sport, game_date" in s:
            return self.board
        if "FROM games g" in s and "EXISTS" in s:
            return [(g[0],) for g in self.board]          # every board game priced
        if "FROM picks p" in s and "signal_type = 'BET'" in s:
            return self.bets
        return []

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _run(monkeypatch, conn, sport):
    """run_scorer over `conn`; returns {(game_id, model_id): schedule_hold}."""
    monkeypatch.setattr(scorer, "get_connection", lambda: conn)
    monkeypatch.setattr(scorer, "_get_postponed_games", lambda _d: set())
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: {"home_price": -110})
    import features.ncaaf_feature_engine as nfe
    import features.ufc_feature_engine as ufe
    import features.wnba_feature_engine as wfe
    for mod, name in ((nfe, "build_ncaaf_game_features"), (ufe, "build_ufc_game_features"),
                      (wfe, "build_wnba_game_features")):
        monkeypatch.setattr(mod, name, lambda *a, **k: {"f": 1})
    monkeypatch.setattr(scorer, "build_nhl_game_features", lambda *a, **k: {"f": 1})
    seen: dict = {}

    def _score(conn_, game_id, model_id, *a, **k):
        seen[(game_id, model_id)] = k.get("schedule_hold")
        return []
    monkeypatch.setattr(scorer, "score_game", _score)
    scorer.run_scorer(TODAY.isoformat(), dry_run=True)
    models = {m for m, (sp, _, _) in config.MODELS.items() if sp == sport}
    return {k: v for k, v in seen.items() if k[1] in models}


# ── NCAAF: the Wisconsin vs USC shape ────────────────────────────────────────

TARGET = f"NCAAF_{_d(7)}_usc_wisconsin"
UCLA = f"NCAAF_{_d(0)}_wisconsin_ucla"


def _ncaaf(ucla_scored: bool, ucla_logged: bool, ucla_start: float = 13.0):
    board = [(TARGET, "NCAAF", 2026, _d(7), "Wisconsin", "USC", _t(7 * 24))]
    schedule = [
        (TARGET, _d(7), "Wisconsin", "USC", _t(7 * 24), None, None),
        (UCLA, _d(0), "UCLA", "Wisconsin", _t(ucla_start),
         31.0 if ucla_scored else None, 20.0 if ucla_scored else None),
        (f"NCAAF_{_d(-7)}_usc_penn-state", _d(-7), "Penn State", "USC", _t(-7 * 24), 24.0, 17.0),
        (f"NCAAF_{_d(-14)}_michigan-state_wisconsin", _d(-14), "Wisconsin", "Michigan State",
         _t(-14 * 24), 21.0, 14.0),
    ]
    log = [("USC", _d(-7), f"NCAAF_{_d(-7)}_usc_penn-state"),
           ("Wisconsin", _d(-14), f"NCAAF_{_d(-14)}_michigan-state_wisconsin")]
    if ucla_logged:
        log.append(("Wisconsin", _d(0), UCLA))
    return board, schedule, log


def test_an_ncaaf_total_waits_for_a_teams_intermediate_game(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=False, ucla_logged=False)
    holds = _run(monkeypatch, _BoardConn(board, schedule, ncaaf_log=log), "NCAAF")
    assert holds, "no NCAAF model was scored"
    assert set(holds.values()) == {
        f"waiting for Wisconsin's {_d(0)} game to be played and logged"}, holds


def test_an_ncaaf_game_in_progress_still_holds(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=False, ucla_logged=False, ucla_start=-1.0)
    holds = _run(monkeypatch, _BoardConn(board, schedule, ncaaf_log=log), "NCAAF")
    assert all(v and "Wisconsin's" in v for v in holds.values()), holds


def test_played_but_not_logged_still_holds(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=True, ucla_logged=False, ucla_start=-20.0)
    holds = _run(monkeypatch, _BoardConn(board, schedule, ncaaf_log=log), "NCAAF")
    assert all(v and "Wisconsin's" in v for v in holds.values()), holds


def test_once_played_and_logged_the_game_is_decided(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=True, ucla_logged=True, ucla_start=-20.0)
    holds = _run(monkeypatch, _BoardConn(board, schedule, ncaaf_log=log), "NCAAF")
    assert holds and set(holds.values()) == {None}, holds


def test_a_schedule_that_cannot_be_read_fails_closed(monkeypatch):
    board, schedule, log = _ncaaf(ucla_scored=True, ucla_logged=True, ucla_start=-20.0)
    conn = _BoardConn(board, schedule, ncaaf_log=log, fail_schedule=True)
    holds = _run(monkeypatch, conn, "NCAAF")
    assert holds and all(v and "schedule check failed" in v for v in holds.values()), holds


# ── WNBA: game N+1 listed while game N is on ────────────────────────────────

def test_wnba_waits_while_the_previous_game_is_being_played(monkeypatch):
    n1 = f"WNBA_{_d(2)}_ATL_GSV"
    n = f"WNBA_{_d(0)}_ATL_GSV"
    board = [(n1, "WNBA", 2026, _d(2), "GSV", "ATL", _t(48))]
    schedule = [(n1, _d(2), "GSV", "ATL", _t(48), None, None),
                (n, _d(0), "GSV", "ATL", _t(-1.5), None, None),           # on now
                (f"WNBA_{_d(-2)}_GSV_ATL", _d(-2), "ATL", "GSV", _t(-50), 80.0, 75.0)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={n}), "WNBA")
    assert holds and all(
        v == f"waiting for ATL's {_d(0)} game and GSV's {_d(0)} game to be played and logged"
        for v in holds.values()), holds


def test_a_wnba_row_no_book_ever_priced_is_not_a_game(monkeypatch):
    """WNBA_2026-10-03_NY_ATL: unscored, 0 odds rows, 17h from the real game."""
    target = f"WNBA_{_d(3)}_NY_ATL"
    board = [(target, "WNBA", 2026, _d(3), "ATL", "NY", _t(72))]
    schedule = [(target, _d(3), "ATL", "NY", _t(72), None, None),
                (f"WNBA_{_d(-1)}_NY_ATL", _d(-1), "ATL", "NY", _t(-23), None, None),  # phantom
                (f"WNBA_{_d(0)}_NY_ATL", _d(0), "ATL", "NY", _t(-6), 92.0, 88.0)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced=()), "WNBA")
    assert holds and set(holds.values()) == {None}, holds


# ── UFC: a card not in the fight log yet ─────────────────────────────────────

def test_ufc_waits_for_a_fighters_card_to_reach_the_fight_log(monkeypatch):
    target = f"UFC_{_d(5)}_jan-blachowicz_alex-pereira"
    prev = f"UFC_{_d(-2)}_alex-pereira_jiri-prochazka"
    board = [(target, "UFC", 2026, _d(5), "Alex Pereira", "Jan Blachowicz", _t(5 * 24))]
    schedule = [(target, _d(5), "Alex Pereira", "Jan Blachowicz", _t(5 * 24), None, None),
                (prev, _d(-2), "Jiri Prochazka", "Alex Pereira", _t(-50), None, None)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={prev}, ufc_cards=[_d(-30)]),
                 "UFC")
    assert holds and all(
        v == f"waiting for Alex Pereira's {_d(-2)} fight to be played and logged"
        for v in holds.values()), holds
    # The card lands: decided.
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={prev},
                                         ufc_cards=[_d(-30), _d(-2)]), "UFC")
    assert holds and set(holds.values()) == {None}, holds


# ── NHL keeps its own game-day check ─────────────────────────────────────────

def test_nhl_is_not_given_the_generic_gate(monkeypatch):
    gid = f"NHL_{_d(0)}_BOS_TOR"
    board = [(gid, "NHL", 2027, _d(0), "TOR", "BOS", _t(6))]
    schedule = [(gid, _d(0), "TOR", "BOS", _t(6), None, None),
                (f"NHL_{_d(-1)}_BOS_ANA", _d(-1), "ANA", "BOS", _t(-20), None, None)]
    holds = _run(monkeypatch, _BoardConn(board, schedule, priced={f"NHL_{_d(-1)}_BOS_ANA"}),
                 "NHL")
    assert holds and set(holds.values()) == {None}, holds


# ── score_game: what a hold does to the rows ─────────────────────────────────

class _Clf:
    def predict_proba(self, X):
        return np.array([[0.42, 0.58]])


def _stock(monkeypatch, *, hold=None, paused=False):
    """wnba_moneyline on the stock path: a 0.58 home side at +120 (edge 0.125)."""
    monkeypatch.setattr(scorer, "load_model",
                        lambda mid: {"model": _Clf(), "feature_cols": []})
    odds = {"home_price": 120.0, "away_price": -140.0, "spread_home": None,
            "total_line": None}
    monkeypatch.setattr(scorer, "_get_scoring_odds", lambda *a, **k: odds)
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: odds)
    monkeypatch.setattr(scorer, "_get_public_betting", lambda *a, **k: {})
    for name in ("_stamp_best_game_prices", "_apply_game_injury_gate",
                 "_apply_game_market_gate"):
        monkeypatch.setattr(scorer, name, lambda *a, **k: None)
    monkeypatch.setattr(scorer, "_is_paused", lambda mid: paused)
    return scorer.score_game(
        None, "WNBA_2026-10-21_GSV_ATL", "wnba_moneyline",
        {"home_team": "ATL", "away_team": "GSV", "game_date": "2026-10-21"},
        bankroll=1000.0, dry_run=True, commence_time="2026-10-22T00:10:00Z",
        **({"schedule_hold": hold} if hold else {}))


def test_without_a_hold_the_number_is_a_bet(monkeypatch):
    assert "BET" in {p["signal_type"] for p in _stock(monkeypatch)}


def test_a_hold_writes_every_row_none_with_the_reason(monkeypatch):
    why = "waiting for ATL's 2026-10-19 game to be played and logged"
    picks = _stock(monkeypatch, hold=why)
    assert picks and {p["signal_type"] for p in picks} == {"NONE"}
    assert {p["downgrade_reason"] for p in picks} == {why}
    assert all(p["recommended_bet"] == 0.0 for p in picks)


def test_a_paused_models_held_row_keeps_the_pause_note(monkeypatch):
    picks = _stock(monkeypatch, hold="waiting for ATL's 2026-10-19 game to be played and logged",
                   paused=True)
    assert picks and {p["signal_type"] for p in picks} == {"NONE"}
    assert {p["downgrade_reason"] for p in picks} == {config.PAUSED_NOTE}

"""One NHL game never gets two picks that cannot both win (mike, 2026-10-17).

On 2026-10-17 nhl_moneyline_regulation posted "BOS (Regulation)" (locked the
day before) and nhl_moneyline posted "LAK ML" (game day) on the same game:
at most one could win, and a Boston overtime win lost both. "It can't be
both." Two changes, pinned here:

  - the regulation model decides only when the moneyline model does --
    16:00Z-18:00Z on game day, both listed goalies, last night's logs in --
    and writes every other run as NONE with the reason;
  - the side models' rows are held back and checked against each other and
    against any BET already on the game before they are written: a standing
    BET keeps the game (a pick is a pick), and two same-pass BETs that cannot
    both win are both written NONE.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
import models.nhl_moneyline_anchored as anc
import models.scorer as sc

GID = "NHL_2026-10-17_BOS_LAK"


def _pick(model_id, side, label, signal="BET", **kw):
    return {"model_id": model_id, "pick_side": side, "pick_label": label,
            "signal_type": signal, "kelly_fraction": 0.02, "recommended_bet": 20.0,
            "downgrade_reason": None, **kw}


def ml(side, label, **kw):
    return _pick("nhl_moneyline", side, label, **kw)


def reg(side, label, **kw):
    return _pick("nhl_moneyline_regulation", side, label, **kw)


class _Conn:
    """Returns `standing` for the standing-BET read and records the call."""

    def __init__(self, standing=()):
        self.standing = list(standing)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        rows = self.standing

        class _R:
            def fetchall(self_inner):
                return rows
        return _R()


# ── which picks cannot both win ──────────────────────────────────────────────

@pytest.mark.parametrize("a,b,clash", [
    (ml("home", "LAK ML"), reg("away", "BOS (Regulation)"), True),     # 2026-10-17
    (ml("away", "FLA ML"), reg("home", "ANA (Regulation)"), True),     # 2026-10-04, both lost
    (ml("home", "LAK ML"), reg("home", "LAK (Regulation)"), False),    # same team
    (ml("home", "LAK ML"), reg("draw", "BOS @ LAK Draw (Regulation)"), False),  # LAK in OT wins both
    (reg("home", "LAK (Regulation)"), reg("draw", "BOS @ LAK Draw (Regulation)"), True),
    (ml("home", "LAK ML"), ml("away", "BOS ML"), True),
])
def test_which_picks_cannot_both_win(a, b, clash):
    assert sc.picks_cannot_both_win(a, b) is clash
    assert sc.picks_cannot_both_win(b, a) is clash


def test_a_market_not_listed_is_never_a_conflict():
    """MLB first-five moneyline and the full-game run line CAN both win; no
    market outside the table is guessed at."""
    a = _pick("mlb_f5_moneyline", "home", "CLE ML F5")
    b = _pick("mlb_runline", "away", "OAK +1.5")
    assert sc.picks_cannot_both_win(a, b) is False


def test_the_nhl_side_models_are_held_back_and_nothing_else_is():
    """The puck line joined on 2026-11-22 (it has bet nothing since
    2026-08-01, so this changes no pick it has made)."""
    assert sc.side_checked_models() == {"nhl_moneyline", "nhl_moneyline_regulation",
                                        "nhl_puckline"}


# ── the check itself ─────────────────────────────────────────────────────────

def test_tonights_case_a_standing_bet_keeps_the_game():
    """BOS (Regulation) was bet first; LAK ML comes after and is not bet."""
    conn = _Conn([("nhl_moneyline_regulation", "away", "BOS (Regulation)", None)])
    new = [ml("home", "LAK ML"), ml("away", "BOS ML", signal="NONE")]
    assert sc._apply_side_conflicts(conn, GID, new) == 1
    lak = new[0]
    assert lak["signal_type"] == "NONE"
    assert lak["kelly_fraction"] == 0.0 and lak["recommended_bet"] == 0.0
    assert "BOS (Regulation)" in lak["downgrade_reason"]
    assert "already bet" in lak["downgrade_reason"]
    assert new[1]["signal_type"] == "NONE" and new[1]["downgrade_reason"] is None


def test_two_bets_in_the_same_pass_that_cannot_both_win_are_both_dropped():
    conn = _Conn([])
    new = [ml("home", "LAK ML"), reg("away", "BOS (Regulation)")]
    assert sc._apply_side_conflicts(conn, GID, new) == 2
    assert [p["signal_type"] for p in new] == ["NONE", "NONE"]
    assert "BOS (Regulation)" in new[0]["downgrade_reason"]
    assert "LAK ML" in new[1]["downgrade_reason"]
    assert all("neither is bet" in p["downgrade_reason"] for p in new)


@pytest.mark.parametrize("other", [
    reg("home", "LAK (Regulation)"),
    reg("draw", "BOS @ LAK Draw (Regulation)"),
])
def test_bets_that_can_both_win_both_stand(other):
    conn = _Conn([])
    new = [ml("home", "LAK ML"), other]
    assert sc._apply_side_conflicts(conn, GID, new) == 0
    assert [p["signal_type"] for p in new] == ["BET", "BET"]


def test_a_paused_models_bet_neither_holds_nor_loses_the_game():
    """A paused model's BET is not a signal: it must not block a live pick."""
    conn = _Conn([])
    paused = reg("away", "BOS (Regulation)", downgrade_reason=config.PAUSED_NOTE)
    live = ml("home", "LAK ML")
    assert sc._apply_side_conflicts(conn, GID, [live, paused]) == 0
    assert live["signal_type"] == "BET" and paused["signal_type"] == "BET"


def test_no_new_bet_means_no_read():
    conn = _Conn([("nhl_moneyline_regulation", "away", "BOS (Regulation)", None)])
    assert sc._apply_side_conflicts(conn, GID, [ml("home", "LAK ML", signal="NONE")]) == 0
    assert conn.calls == []


def test_the_standing_read_skips_void_and_paused_rows_and_reads_both_models():
    """A voided pick holds nothing (tonight's LAK ML is VOID); a paused one is
    not a signal. The read is the only place those are excluded."""
    conn = _Conn([])
    sc._apply_side_conflicts(conn, GID, [ml("home", "LAK ML")])
    (sql, params), = conn.calls
    assert "condition_status IS DISTINCT FROM 'VOID'" in sql
    assert "downgrade_reason IS DISTINCT FROM" in sql
    assert params[0] == GID
    assert set(params[1]) == {"nhl_moneyline", "nhl_moneyline_regulation", "nhl_puckline",
                              # the rule cards' bets stand too (2026-11-22)
                              "nhl_night_puckline", "nhl_night_total", "nhl_night_moneyline",
                              "nhl_night_regulation", "nhl_over_under"}
    assert params[2] == config.PAUSED_NOTE
    assert "scored_line" in sql


# ── the puck line, the total, and the rule cards (2026-11-22) ───────────────
#
# The NHL best bet a night (models/nhl_best_bet_night.py) bets the puck line,
# the total, the moneyline and the 3-way from its own card. A side model that
# decides after it must see that bet; scored_line is the HOME number.

def pl(side, label, line, **kw):
    return _pick("nhl_puckline", side, label, scored_line=line, **kw)


def night(market, side, label, line=None, **kw):
    mid = {"spreads": "nhl_night_puckline", "totals": "nhl_night_total",
           "h2h": "nhl_night_moneyline", "h2h_3way": "nhl_night_regulation"}[market]
    return _pick(mid, side, label, scored_line=line, **kw)


@pytest.mark.parametrize("a,b,clash", [
    (pl("home", "LAK -1.5", -1.5), ml("away", "BOS ML"), True),
    (pl("home", "LAK -1.5", -1.5), ml("home", "LAK ML"), False),
    (pl("away", "BOS +1.5", -1.5), ml("home", "LAK ML"), False),       # LAK by one wins both
    (pl("away", "BOS +1.5", -1.5), pl("home", "LAK -1.5", -1.5), True),
    (pl("home", "LAK +1.5", 1.5), pl("away", "BOS -1.5", 1.5), True),
    (pl("home", "LAK -1.5", -1.5), reg("draw", "BOS @ LAK Draw (Regulation)"), True),  # OT is by one
    (pl("away", "BOS -1.5", 1.5), reg("draw", "BOS @ LAK Draw (Regulation)"), True),
    (pl("home", "LAK +1.5", 1.5), reg("draw", "BOS @ LAK Draw (Regulation)"), False),
    (pl("home", "LAK -1.5", -1.5), reg("home", "LAK (Regulation)"), False),
    (night("totals", "over", "Over 6.5", 6.5), night("totals", "under", "Under 6.5", 6.5), True),
    (night("totals", "over", "Over 5.5", 5.5), night("totals", "under", "Under 6.5", 6.5), False),
    (night("totals", "over", "Over 6.5", 6.5), night("totals", "under", "Under 5.5", 5.5), True),
    (night("totals", "under", "Under 6.5", 6.5), ml("home", "LAK ML"), False),
    (night("h2h", "home", "LAK ML"), reg("away", "BOS (Regulation)"), True),
    (night("h2h_3way", "draw", "BOS @ LAK Draw (Regulation)"), ml("home", "LAK ML"), False),
])
def test_puck_lines_totals_and_rule_cards(a, b, clash):
    assert sc.picks_cannot_both_win(a, b) is clash
    assert sc.picks_cannot_both_win(b, a) is clash


def test_a_line_that_cannot_be_read_is_not_guessed_at():
    assert sc.picks_cannot_both_win(pl("home", "LAK -1.5", None), ml("away", "BOS ML")) is False


def test_a_standing_night_bet_keeps_the_game_from_a_side_model():
    """The night card bet LAK -1.5 at 3pm; the moneyline model decides BOS ML
    later in the evening's pass, and is not bet."""
    conn = _Conn([("nhl_night_puckline", "home", "LAK -1.5", -1.5)])
    new = [ml("away", "BOS ML")]
    assert sc._apply_side_conflicts(conn, GID, new) == 1
    assert new[0]["signal_type"] == "NONE"
    assert "LAK -1.5" in new[0]["downgrade_reason"]


def test_a_standing_total_never_blocks_a_side():
    conn = _Conn([("nhl_night_total", "under", "Under 6.5", 6.5)])
    new = [ml("away", "BOS ML"), pl("home", "LAK -1.5", -1.5, signal="NONE")]
    assert sc._apply_side_conflicts(conn, GID, new) == 0
    assert new[0]["signal_type"] == "BET"


def test_the_totals_card_reads_the_same_standing_bets():
    conn = _Conn([("nhl_night_total", "over", "Over 6.5", 6.5)])
    under = {"game_id": GID, "model_id": "nhl_over_under", "pick_side": "under",
             "pick_label": "Under 6.5", "scored_line": 6.5}
    held = sc.conflicting_standing_bet(conn, under)
    assert held is not None and held["pick_label"] == "Over 6.5"
    conn = _Conn([("nhl_night_total", "over", "Over 5.5", 5.5)])
    assert sc.conflicting_standing_bet(conn, under) is None


# ── the regulation model decides when the moneyline model does ──────────────

class _ThreeWay:
    """away 0.42 / draw 0.21 / home 0.37 -- BOS (Regulation) on 2026-10-16."""

    def predict_proba(self, X):
        return np.array([[0.42, 0.21, 0.37]])


def _score_regulation(monkeypatch, *, window=None, goalies=("BOS", "LAK"),
                      stale=(), dry_run=True, write=True, inserted=None, matchup=None):
    import models.nhl_goalie_gate as gate
    # `matchup`: the goalie gate's reason; None = both starters confirmed.
    monkeypatch.setattr(gate, "matchup_states", lambda conn, ids, now=None: {g: gate.Matchup(g, matchup) for g in ids})
    monkeypatch.setattr(sc, "load_model", lambda mid: {
        "model": _ThreeWay(), "feature_cols": ["x"]})
    # +195 on BOS in regulation: EV 0.42 x 2.95 - 1 = 0.239, over the 0.20 floor
    monkeypatch.setattr(sc, "_get_dk_odds", lambda conn, gid, market: {
        "away_price": 195.0, "draw_price": 310.0, "home_price": 115.0})
    monkeypatch.setattr(sc, "_get_public_betting", lambda conn, gid, market, side: {
        "public_bet_pct": None, "public_money_pct": None})
    for name in ("_stamp_best_game_prices", "_apply_game_injury_gate"):
        monkeypatch.setattr(sc, name, lambda *a, **k: None)
    listed = {(GID, t): "1" for t in goalies}
    monkeypatch.setattr(anc, "inputs_for_date", lambda conn, d: (pd.DataFrame(), listed, set(stale)))
    monkeypatch.setattr(anc, "decision_window", lambda d, ct, now=None: window)
    if inserted is not None:
        monkeypatch.setattr(sc, "_insert_picks", lambda conn, picks: inserted.extend(picks))
    return sc.score_game(None, GID, "nhl_moneyline_regulation",
                         {"home_team": "LAK", "away_team": "BOS", "game_date": "2026-10-17", "x": 0.0},
                         bankroll=1000.0, dry_run=dry_run, commence_time="2026-10-18T01:10:00Z",
                         write=write)


def test_in_the_window_it_can_bet(monkeypatch):
    picks = {p["pick_side"]: p for p in _score_regulation(monkeypatch)}
    assert picks["away"]["signal_type"] == "BET"


def test_the_day_before_every_row_is_none_with_the_reason(monkeypatch):
    """The 2026-10-16 18:26Z run that locked BOS (Regulation): the day before,
    the game has no goalie row, so the gate cannot call it known."""
    why = "waiting for both confirmed starting goalies (BOS no goalie row yet; LAK no goalie row yet)"
    picks = _score_regulation(monkeypatch, matchup=why)
    assert picks and all(p["signal_type"] == "NONE" for p in picks)
    assert all(p["downgrade_reason"] == why for p in picks)


def test_a_started_game_is_not_decided(monkeypatch):
    picks = _score_regulation(monkeypatch, window="game has started")
    assert picks and all(p["signal_type"] == "NONE" for p in picks)
    assert all("game has started" in p["downgrade_reason"] for p in picks)


def test_without_both_goalies_confirmed_it_does_not_decide(monkeypatch):
    why = "waiting for both confirmed starting goalies (LAK expected)"
    picks = _score_regulation(monkeypatch, matchup=why)
    assert picks and all(p["signal_type"] == "NONE" for p in picks)
    assert all(p["downgrade_reason"] == why for p in picks)


def test_without_last_nights_logs_it_does_not_decide(monkeypatch):
    picks = _score_regulation(monkeypatch, stale=("BOS",))
    assert picks and all(p["signal_type"] == "NONE" for p in picks)
    assert all("last night's game logs" in p["downgrade_reason"] for p in picks)


def test_an_input_failure_fails_closed(monkeypatch):
    def boom(conn, d):
        raise RuntimeError("logs unreadable")
    _score_regulation(monkeypatch)            # wire everything else
    monkeypatch.setattr(anc, "inputs_for_date", boom)
    picks = sc.score_game(None, GID, "nhl_moneyline_regulation",
                          {"home_team": "LAK", "away_team": "BOS", "game_date": "2026-10-17", "x": 0.0},
                          bankroll=1000.0, dry_run=True, commence_time="2026-10-18T01:10:00Z")
    assert picks and all(p["signal_type"] == "NONE" for p in picks)


def test_both_side_models_read_one_gate():
    """The moneyline model's reasons and the regulation model's come from the
    same function, so the two cannot drift onto different moments."""
    import inspect
    assert "_nhl_game_day_reason(" in inspect.getsource(sc._anchored_probability)
    assert "_nhl_game_day_reason(" in inspect.getsource(sc._nhl_regulation_reason)


# ── held back means not written until the check has run ─────────────────────

def test_write_false_returns_the_rows_without_inserting(monkeypatch):
    inserted: list = []
    picks = _score_regulation(monkeypatch, dry_run=False, write=False, inserted=inserted)
    assert picks and inserted == []


def test_write_true_still_inserts(monkeypatch):
    inserted: list = []
    picks = _score_regulation(monkeypatch, dry_run=False, write=True, inserted=inserted)
    assert inserted == picks

"""The EuroLeague pre-game card's pure pieces (scripts/euroleague_pregame_card.py):
when a game is decided, what it is decided on, and the rows it writes.

The run end to end, against a real Postgres, is
tests/test_euroleague_pregame_card_pg.py.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.euroleague_pregame as R  # noqa: E402
from scripts import euroleague_pregame_card as card  # noqa: E402

UTC = timezone.utc
TIP = datetime(2026, 11, 20, 19, 0, tzinfo=UTC)


def games(**kw):
    g = {"season": 2027, "game_date": "2026-11-20", "tip": TIP, "commence_time": TIP.isoformat(),
         "home": "MAD", "away": "PAN", "neutral_site": False, "venue_name": "WIZINK CENTER"}
    g.update(kw)
    return {"G1": g}


ALL = {"G1": R.MODELS}


# ── when ─────────────────────────────────────────────────────────────────────

def test_a_decision_fetch_5_to_10_5_minutes_out_decides_the_game_on_it():
    f = TIP - timedelta(minutes=9, seconds=40)
    due, missed, waiting = card.due_games(games(), {"G1": f}, TIP - timedelta(minutes=9), ALL)
    assert due == {"G1": (f, f)} and not missed and not waiting


def test_a_fetch_older_than_10_5_minutes_is_not_the_decision_fetch():
    f = TIP - timedelta(minutes=12)
    due, missed, waiting = card.due_games(games(), {"G1": f}, TIP - timedelta(minutes=9), ALL)
    assert not due and waiting == ["G1"]


def test_with_no_decision_fetch_by_5_minutes_out_the_full_game_rules_use_the_board_at_tip_minus_10():
    due, missed, waiting = card.due_games(games(), {}, TIP - timedelta(minutes=4, seconds=59), ALL)
    assert due == {"G1": (TIP - timedelta(minutes=10), None)}


def test_a_game_that_tipped_undecided_is_missed():
    due, missed, waiting = card.due_games(games(), {}, TIP + timedelta(minutes=1), ALL)
    assert missed == {"G1": "tipped before it was decided"} and not due


def test_a_game_every_model_has_decided_is_not_looked_at():
    due, missed, waiting = card.due_games(games(), {}, TIP + timedelta(minutes=1), {"G1": ()})
    assert not due and not missed and not waiting


def test_each_model_has_its_own_switch(monkeypatch):
    monkeypatch.setenv("RUN_EUROLEAGUE_HEAVY_FAV_ML", "0")
    monkeypatch.setenv("RUN_EUROLEAGUE_Q1_SHARE_TOTAL", "off")
    assert card.models_on() == (R.HOME_ML, R.HOME_DOG_SPREAD, R.H1_DOG_ML)
    monkeypatch.setenv("RUN_EUROLEAGUE_PREGAME", "false")
    assert not card.enabled()


def test_a_book_the_platform_stopped_listing_is_never_decided_at(monkeypatch):
    monkeypatch.setattr(config, "BEST_LINE_BOOKMAKERS", [b for b in config.BEST_LINE_BOOKMAKERS if b != "fanduel"])
    assert "fanduel" not in card.deciding_books()
    assert "draftkings" in card.deciding_books()


# ── what: the decision fetch's own rows for the period rules ────────────────

def _odds(rows):
    cols = list(card._ODDS_COLS)
    out = []
    for r in rows:
        d = dict.fromkeys(cols)
        d.update(r)
        out.append(d)
    return pd.DataFrame(out, columns=cols)


def test_the_period_rules_read_only_the_decision_fetchs_rows_and_the_full_game_the_board_at_it():
    f = pd.Timestamp(TIP - timedelta(minutes=10))
    early = f - pd.Timedelta(minutes=50)
    fg = _odds([
        {"game_id": "G1", "market": "h2h", "bookmaker": "draftkings", "snapshot_at": early,
         "created_at": early, "home_price": 150, "away_price": -175},
        {"game_id": "G1", "market": "h2h", "bookmaker": "draftkings", "snapshot_at": f - pd.Timedelta(minutes=1),
         "created_at": f, "home_price": 140, "away_price": -165},
    ])
    per = _odds([
        # the decision fetch: the home side is the first-half underdog
        {"game_id": "G1", "market": "h2h_h1", "bookmaker": "fanduel", "snapshot_at": f, "created_at": f,
         "home_price": 130, "away_price": -150},
        # an earlier fetch with the other side the underdog: never read
        {"game_id": "G1", "market": "h2h_h1", "bookmaker": "fanduel", "snapshot_at": early, "created_at": early,
         "home_price": -150, "away_price": 130},
    ])
    art = {"models": {m: {"params": p, "uplift": 0.05} for m, p in (
        (R.HOME_ML, {"min_price": -200.0, "min_season": 2022}), (R.HEAVY_FAV_ML, {"max_price": -500.0}),
        (R.HOME_DOG_SPREAD, {"min_home_line": 0.0}), (R.H1_DOG_ML, {}),
        (R.Q1_SHARE_TOTAL, {"margin": 1.0, "k_share": 40.0, "prior_gap_hours": 3.0}))}}
    out = card.decide(games(), {"G1": (f, f)}, {"G1": (R.HOME_ML, R.H1_DOG_ML)}, fg, per, None,
                      {2027: art}, R.DECIDABLE)
    by = {d.model_id: d for d in out}
    assert by[R.HOME_ML].price == 140.0 and by[R.HOME_ML].status == "bet"
    assert (by[R.H1_DOG_ML].side, by[R.H1_DOG_ML].price) == ("home", 130.0)
    assert by[R.HOME_ML].p_model == pytest.approx(by[R.HOME_ML].p_fair + 0.05)


def test_without_the_decision_fetch_the_period_rules_are_missed_and_the_full_game_rules_say_so():
    t = pd.Timestamp(TIP - timedelta(minutes=10))
    fg = _odds([{"game_id": "G1", "market": "h2h", "bookmaker": "draftkings",
                 "snapshot_at": t - pd.Timedelta(minutes=40), "created_at": t - pd.Timedelta(minutes=40),
                 "home_price": 150, "away_price": -175}])
    art = {"models": {R.HOME_ML: {"params": {"min_price": -200.0, "min_season": 2022}, "uplift": 0.05}}}
    out = card.decide(games(), {"G1": (t, None)}, {"G1": (R.HOME_ML, R.H1_DOG_ML, R.Q1_SHARE_TOTAL)},
                      fg, _odds([]), None, {2027: art}, R.DECIDABLE)
    by = {d.model_id: d for d in out}
    assert by[R.HOME_ML].status == "bet" and "no decision fetch" in by[R.HOME_ML].detail
    assert by[R.H1_DOG_ML].status == "missed" and by[R.Q1_SHARE_TOTAL].status == "missed"


def test_a_season_with_no_artifact_decides_nothing():
    out = card.decide(games(), {"G1": (pd.Timestamp(TIP), None)}, {"G1": (R.HOME_ML,)},
                      _odds([]), _odds([]), None, {}, R.DECIDABLE)
    assert [d.status for d in out] == ["no_artifact"]


# ── the rows ─────────────────────────────────────────────────────────────────

def _decided(model, side, price, line=None, p_fair=0.5, uplift=0.05, dk=None, book="fanduel", status="bet"):
    d = R.Decision("G1", model, status, "x", side=side, book=book, price=price, line=line,
                   p_fair=p_fair, dk_price=dk)
    return R.finish(d, uplift)


def test_a_bet_row_is_written_at_the_bet_books_price_with_draftkings_as_the_reference():
    rows, refused = card.pick_rows([_decided(R.HOME_DOG_SPREAD, "home", -105.0, line=3.5, p_fair=0.49,
                                             uplift=0.09, dk=-110.0)], games(), 1000.0)
    r = rows[0]
    assert not refused
    assert (r["signal_type"], r["pick_side"], r["scored_line"], r["decision_book"], r["decision_odds"]) == \
        ("BET", "home", 3.5, "fanduel", -105.0)
    assert r["pick_label"] == "MAD +3.5"
    assert r["dk_odds"] == -110.0 and r["line_book"] is None
    assert r["model_probability"] == pytest.approx(0.58)
    assert r["decision_edge"] == pytest.approx(0.58 - 105 / 205, abs=1e-4)
    assert r["kelly_fraction"] > 0


def test_a_period_moneylines_label_says_first_half_and_its_line_is_null():
    rows, _ = card.pick_rows([_decided(R.H1_DOG_ML, "away", 140.0, p_fair=0.42)], games(), 1000.0)
    assert rows[0]["pick_label"] == "PAN @ MAD — First Half PAN ML" and rows[0]["scored_line"] is None
    assert rows[0]["line_book"] == "fanduel" and rows[0]["dk_odds"] is None


def test_the_first_quarter_totals_label_says_first_quarter():
    rows, _ = card.pick_rows([_decided(R.Q1_SHARE_TOTAL, "under", -120.0, line=41.5, p_fair=0.5, uplift=0.15)],
                             games(), 1000.0)
    assert rows[0]["pick_label"] == "PAN @ MAD — First Quarter Under 41.5"
    assert rows[0]["scored_line"] == 41.5 and rows[0]["signal_type"] == "BET"


def test_a_scored_game_the_rule_did_not_bet_is_a_none_row_with_no_stake():
    rows, _ = card.pick_rows([_decided(R.HOME_ML, "home", -260.0, status="no_bet", p_fair=0.7)], games(), 1000.0)
    assert rows[0]["signal_type"] == "NONE" and rows[0]["kelly_fraction"] == 0.0
    assert rows[0]["recommended_bet"] == 0.0


def test_an_unscored_decision_writes_no_row():
    rows, _ = card.pick_rows([R.Decision("G1", R.HOME_ML, "not_eligible", "neutral site")], games(), 1000.0)
    assert rows == []


@pytest.mark.parametrize("model,price,why", [
    (R.HOME_ML, -210.0, "below_price_floor"),
    (R.HEAVY_FAV_ML, -4500.0, "below_price_floor"),
])
def test_the_price_floor_turns_a_bet_into_a_none_row(model, price, why):
    rows, refused = card.pick_rows([_decided(model, "home", price, p_fair=0.95, uplift=0.03)], games(), 1000.0)
    assert rows[0]["signal_type"] == "NONE" and refused[("G1", model)].startswith(why)


def test_the_heavy_favourite_floor_admits_minus_4000():
    rows, refused = card.pick_rows([_decided(R.HEAVY_FAV_ML, "home", -4000.0, p_fair=0.965, uplift=0.0737)],
                                   games(), 1000.0)
    assert rows[0]["signal_type"] == "BET", refused


def test_an_ev_under_the_models_own_floor_is_refused():
    floor = config.min_ev_for(R.HOME_DOG_SPREAD)
    rows, refused = card.pick_rows([_decided(R.HOME_DOG_SPREAD, "home", -110.0, line=2.5, p_fair=0.40,
                                             uplift=0.0)], games(), 1000.0)
    assert rows[0]["signal_type"] == "NONE"
    assert "ev_below_floor" in refused[("G1", R.HOME_DOG_SPREAD)], (floor, refused)


def test_an_edge_under_the_cut_every_surface_applies_is_refused(monkeypatch):
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, R.H1_DOG_ML, 0.5)
    monkeypatch.setitem(config.MODEL_OWN_EV_FLOOR, R.H1_DOG_ML, -1.0)
    rows, refused = card.pick_rows([_decided(R.H1_DOG_ML, "home", 140.0, p_fair=0.42)], games(), 1000.0)
    assert rows[0]["signal_type"] == "NONE" and refused[("G1", R.H1_DOG_ML)].startswith("below_edge_cut")


def test_a_price_typo_edge_is_refused_as_a_data_error(monkeypatch):
    monkeypatch.setitem(config.MODEL_OWN_EV_FLOOR, R.HOME_ML, -1.0)
    rows, refused = card.pick_rows([_decided(R.HOME_ML, "home", 900.0, p_fair=0.55, uplift=0.0)], games(), 1000.0)
    assert rows[0]["signal_type"] == "NONE" and "data-error cap" in refused[("G1", R.HOME_ML)]


def test_the_decision_row_carries_the_instant_the_fetch_and_the_lead():
    d = _decided(R.HOME_ML, "home", 120.0)
    t = pd.Timestamp(TIP - timedelta(minutes=9, seconds=30))
    d.extra.update(decision_at=t.isoformat(), fetch_at=t.isoformat())
    row = card.decision_row(d, games(), True, None)
    assert row["lead_min"] == 9.5 and row["n_bets"] == 1 and row["status"] == "bet"
    assert row["fetch_at"] == t.isoformat() and row["model_id"] == R.HOME_ML


def test_a_standing_moneyline_is_read_as_a_moneyline_and_a_spread_as_a_spread():
    class C:
        def execute(self, sql, params):
            self.params = params
            return self

        def fetchall(self):
            return [("G1", R.HOME_ML, "home", None, "MAD ML"),
                    ("G1", "euroleague_live_spread_ht", "away", 3.5, "PAN -3.5 (live)"),
                    ("G1", R.HOME_DOG_SPREAD, "home", 4.5, "MAD +4.5")]
    got = card.standing_full_game(C(), ["G1"])
    assert [(s["market"], s["side"], s["line"]) for s in got] == [
        ("h2h", "home", None), ("spreads", "away", 3.5), ("spreads", "home", 4.5)]

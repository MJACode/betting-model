"""Phase 3 (2026-09-19, mike): every BET on the platform clears one EV floor
on the HONEST probability at the deciding price.

    calibrated_prob x decimal(price) - 1  >=  config.min_ev_for(model_id)

One test per path that writes a BET, each one a pick that clears its model's
prob/edge cut and is refused only by the floor -- so the test fails without
the gate. And one that shows the gate reads the CALIBRATED number: a raw 0.70
that maps to 0.63 does not clear at -110 where the raw would.
"""
from __future__ import annotations

import pytest

import config
from models import honest_ev

M = "mlb_moneyline"
# -110: decimal 1.909. p=0.70 -> EV 0.336 (clears 0.30); p=0.66 -> EV 0.260.
MINUS_110 = -110.0
# A map that shrinks every claim: logit offset -0.3 takes 0.70 -> 0.633.
SHRINK = {"method": "platt", "a": 1.0, "b": -0.3}


@pytest.fixture
def floor_030(monkeypatch):
    monkeypatch.setattr(config, "GLOBAL_MIN_EV", 0.30)
    monkeypatch.setattr(config, "MODEL_MIN_EV", {})
    return 0.30


@pytest.fixture
def identity_maps(monkeypatch):
    import models.scorer as sc
    monkeypatch.setattr(sc, "_CAL_CACHE", {})


@pytest.fixture
def shrink_map(monkeypatch):
    import models.scorer as sc
    monkeypatch.setattr(sc, "_CAL_CACHE", {M: SHRINK, "ncaaf_live_win_prob": SHRINK,
                                           "nfl_live_prop": SHRINK,
                                           "nfl_prop_market": SHRINK})


# ── the accessor and the helper ──────────────────────────────────────────────

def test_the_floor_is_the_global_one_unless_the_model_carries_a_higher_one(monkeypatch):
    monkeypatch.setattr(config, "GLOBAL_MIN_EV", 0.30)
    monkeypatch.setattr(config, "MODEL_MIN_EV", {"a": 0.32, "b": 0.24})
    assert config.min_ev_for("a") == 0.32
    assert config.min_ev_for("b") == 0.30
    assert config.min_ev_for("nobody") == 0.30


def test_the_shipped_floor_is_020_and_the_ncaaf_moneyline_keeps_the_030_it_was_swept_under(monkeypatch):
    # 2026-09-20 (mike: "30% is too aggressive then"). conftest pins the live
    # value out of the way, so the shipped default is read from the source.
    from pathlib import Path
    src = (Path(config.__file__)).read_text(encoding="utf-8")
    assert 'os.environ.get("GLOBAL_MIN_EV", "0.20")' in src
    monkeypatch.setattr(config, "GLOBAL_MIN_EV", 0.20)
    assert config.min_ev_for("nfl_prop_market") == 0.20
    # its 0.50/0.16 cut was swept with a 0.30 floor in force (2026-09-19)
    assert config.min_ev_for("ncaaf_live_win_prob") == 0.30
    assert config.min_ev_for("mlb_live_total_runs") == 0.32


def test_expected_value_is_on_the_quoted_price():
    assert config.expected_value(0.70, -110) == pytest.approx(0.70 * (1 + 100 / 110) - 1)
    assert config.expected_value(0.5, 100) == pytest.approx(0.0)
    assert config.expected_value(0.5, None) is None
    assert config.expected_value(0.5, 0) is None


def test_the_gate_reads_the_calibrated_number(floor_030, shrink_map):
    g = honest_ev.gate(M, 0.70, MINUS_110)
    assert g.cal_prob == pytest.approx(0.6335, abs=1e-3)
    assert g.ev < 0.30 and not g.clears
    assert "ev_below_floor" in g.reason and "0.700->0.633" in g.reason


def test_the_gate_clears_on_the_honest_number_when_it_is_enough(floor_030, identity_maps):
    g = honest_ev.gate(M, 0.70, MINUS_110)
    assert g.clears and g.reason is None


def test_no_price_means_no_floor_can_apply(floor_030, identity_maps):
    assert honest_ev.gate(M, 0.70, None).clears


# ── the pre-game scorer ──────────────────────────────────────────────────────

@pytest.fixture
def open_pregame_cut(monkeypatch):
    import models.scorer as sc
    monkeypatch.setattr(sc, "MODEL_EDGE_THRESHOLDS", {M: 0.05})
    monkeypatch.setattr(sc, "MODEL_PROB_THRESHOLDS", {M: 0.55})
    monkeypatch.setattr(sc, "PAUSED_MODELS", set())
    monkeypatch.setattr(config, "PAUSED_MODELS", set())
    monkeypatch.setattr(sc, "DECIDE_ON_CALIBRATED_PROB", True)
    monkeypatch.setattr(config, "MODEL_MIN_ODDS", {})
    monkeypatch.setattr(config, "DEFAULT_MIN_ODDS", -10000.0)


def _pregame(p, odds=MINUS_110):
    from models.scorer import _decide
    implied = 110 / 210
    return _decide(M, p, implied, p - implied, odds, is_prop=False)


def test_pregame_bet_that_clears_its_cut_is_refused_under_the_floor(
        floor_030, identity_maps, open_pregame_cut):
    assert _pregame(0.70) == "BET"
    # edge 0.136 >= 0.05, prob >= 0.55: the cut says BET. EV 0.26 < 0.30.
    assert _pregame(0.66) == "NONE"


def test_pregame_floor_is_judged_on_the_calibrated_probability(
        floor_030, shrink_map, open_pregame_cut):
    # raw 0.70 clears at -110 (EV 0.336); calibrated 0.632 does not (0.207).
    assert _pregame(0.70) == "NONE"


def test_pregame_avoid_is_untouched_by_the_floor(floor_030, identity_maps, open_pregame_cut):
    from models.scorer import _decide
    implied = 110 / 210
    assert _decide(M, 0.40, implied, 0.40 - implied, MINUS_110, is_prop=False) == "AVOID"


# ── the MLB live loop ────────────────────────────────────────────────────────

def test_live_signal_is_refused_under_the_global_floor(floor_030, identity_maps, monkeypatch):
    from models import live_scorer as ls
    monkeypatch.setattr(ls, "MODEL_PROB_THRESHOLDS", {"mlb_live_total_runs": 0.55})
    monkeypatch.setattr(ls, "MODEL_EDGE_THRESHOLDS", {"mlb_live_total_runs": 0.05})
    monkeypatch.setattr(ls, "PAUSED_MODELS", set())
    monkeypatch.setattr(ls, "DECIDE_ON_CALIBRATED_PROB", True)
    implied = 110 / 210
    assert ls.classify_live_signal("mlb_live_total_runs", 0.70, 0.70 - implied, MINUS_110) == "BET"
    assert ls.classify_live_signal("mlb_live_total_runs", 0.66, 0.66 - implied, MINUS_110) == "NONE"


# ── the NCAAF live loop ──────────────────────────────────────────────────────

def test_ncaaf_live_floors_are_the_platform_accessor():
    """serve reads the floors ONCE at import, so the value depends on the
    environment that imported it; what is pinned is that it reads them
    through the accessor, never MODEL_MIN_EV directly."""
    import inspect
    from ncaaf_live import serve
    src = inspect.getsource(serve)
    assert 'min_ev_for("ncaaf_live_total")' in src
    assert 'min_ev_for("ncaaf_live_win_prob")' in src
    assert 'MODEL_MIN_EV.get("ncaaf_live' not in src


def test_ncaaf_live_decides_on_the_calibrated_probability(floor_030, shrink_map, monkeypatch):
    """The engine's stage-3 number is what the map was fitted on; the map
    applies on top of it and the EV floor reads the result."""
    from ncaaf_live import serve
    implied = 110 / 210
    # raw 0.70 clears prob 0.55 / edge 0.05 / EV 0.30 at -110; honest 0.632 does not.
    assert serve.LiveEngine._decide(0.70, 0.70 - implied, 0.55, 0.05, MINUS_110, 0.30) == "BET"
    assert serve.LiveEngine.decide_honest(
        "ncaaf_live_win_prob", 0.70, implied, 0.55, 0.05, MINUS_110, 0.30) is None
    with_identity = serve.LiveEngine.decide_honest(
        "ncaaf_live_total", 0.70, implied, 0.55, 0.05, MINUS_110, 0.30)
    assert with_identity == "BET"


# ── the NFL live executor ────────────────────────────────────────────────────

def _nfl_fixtures():
    from datetime import datetime, timedelta, timezone
    from dataclasses import replace
    from nfl.live_model import executor as ex
    from nfl.live_model.config import SETTLED_SEC
    from nfl.live_model.feeds.odds_live import Quote
    from nfl.live_model.state import GameState
    now = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)
    st = GameState("g", now, 3, 600, 21, 17, "home", 1, 10, 50, 3, 3, -3.0, 46.0,
                   None, True, 80, 0.6, 0.55)
    q = Quote("g", "player_pass_attempts", "draftkings", "over", MINUS_110, 23.5, now)
    e = ex.Executor()
    # The settled-state rule: a first look is never a bet, so look earlier first.
    earlier = now - timedelta(seconds=SETTLED_SEC + 30)
    e.recorder = e.alerter = None
    e.evaluate(state=replace(st, ts=earlier), quote=replace(q, ts=earlier),
               model_prob=0.5, model_id="nfl_live_prop", now=earlier)
    e.decisions.clear()
    return e, st, q, now


def test_nfl_live_executor_refuses_under_the_global_floor(floor_030, identity_maps):
    e, st, q, now = _nfl_fixtures()
    # 0.62 at -110 is EV 0.18: over the model's own 0.06 bar, under the floor.
    d = e.evaluate(state=st, quote=q, model_prob=0.62, model_id="nfl_live_prop", now=now)
    assert d.bet is False and d.reason.startswith("below_threshold"), d.reason
    assert "<0.3000" in d.reason
    d = e.evaluate(state=st, quote=q, model_prob=0.70, model_id="nfl_live_prop", now=now)
    assert d.bet is True, d.reason


def test_nfl_live_executor_judges_the_calibrated_number(floor_030, shrink_map):
    e, st, q, now = _nfl_fixtures()
    d = e.evaluate(state=st, quote=q, model_prob=0.70, model_id="nfl_live_prop", now=now)
    assert d.bet is False
    assert d.model_prob == pytest.approx(0.70)
    assert d.model_prob_cal == pytest.approx(0.6335, abs=1e-3)


# ── the rule cards ───────────────────────────────────────────────────────────

def test_nfl_prop_market_card_drops_a_bet_under_the_floor(floor_030, identity_maps):
    from models.nfl_prop_market import MarketBet
    from scripts.nfl_prop_market_card import pick_rows
    games = {"G": {"date": "2026-09-20", "kickoff": "2026-09-20T17:00:00Z"}}
    low = MarketBet(game_id="G", player="p1", market="player_receptions", side="over",
                    book="fanduel", line=4.5, price=MINUS_110, fair=0.60, edge=0.05,
                    sharp_price=-120)
    high = MarketBet(game_id="G", player="p2", market="player_receptions", side="over",
                     book="fanduel", line=4.5, price=MINUS_110, fair=0.72, edge=0.15,
                     sharp_price=-140)
    rows = pick_rows([low, high], games, {}, 1000.0)
    assert [r["player_key"] for r in rows] == ["p2"]
    assert rows[0]["model_probability_cal"] == pytest.approx(0.72)


def test_wnba_prop_market_card_drops_a_bet_under_the_floor(floor_030, identity_maps):
    from models.wnba_prop_market import MarketBet
    from scripts.wnba_prop_market_card import pick_rows
    low = MarketBet(game_id="G", player="A Wilson", market="player_points", side="over",
                    book="fanduel", line=20.5, price=MINUS_110, fair=0.60, edge=0.05,
                    sharp_price=-120)
    rows = pick_rows([low], {"G": {}}, {}, {"a wilson": 7}, "2026-09-20", 1000.0)
    assert rows == []


def test_mlb_market_cards_drop_a_bet_under_the_floor(floor_030, identity_maps):
    from models.mlb_game_market import GameMarketBet
    from scripts.mlb_game_market_card import pick_rows
    low = GameMarketBet(game_id="G", market="spreads", side="home", book="fanduel",
                        line=-1.5, price=MINUS_110, fair=0.60, edge=0.05, sharp_price=-120)
    rows = pick_rows([low], {"G": {"home": "NYY", "away": "BOS", "game_date": "2026-09-20"}},
                     {}, 1000.0, "mlb_spread_market", "spreads")
    assert rows == []


def test_nfl_wind_and_opener_rows_drop_a_bet_under_the_floor(floor_030, identity_maps):
    from scripts.nfl_wind_publisher import build_opener_rows, build_rows
    wind = {"game_id": "2026_03_BUF_MIA", "matchup": "BUF @ MIA",
            "kick_utc": "2026-09-20T17:00:00Z", "stadium_id": "x", "lead_days": "3",
            "forecast_wind": "18", "exp_true_wind": "16", "total_line": "44.5",
            "book": "fanduel", "price": "-110", "model_prob": "0.60",
            "market_prob": "0.52", "edge": "0.08", "stake_pct": "1.0", "ev_pct": "5"}
    _, picks = build_rows([wind], 1000.0)
    assert picks == []
    opener = {"game_id": "2026_03_BUF_MIA", "matchup": "BUF @ MIA",
              "kick_utc": "2026-09-20T17:00:00Z", "lead_days": "3", "side": "home",
              "bet_team": "MIA", "book": "fanduel", "price": "-110", "side_line": "-2.5",
              "soft_home_line": "-2.5", "pin_home_line": "-3.5", "dev": "1.0",
              "model_prob": "0.60", "market_prob": "0.52", "edge": "0.08",
              "stake_pct": "1.0"}
    _, picks = build_opener_rows([opener], 1000.0)
    assert picks == []


# ── the Discord "good to" bound ──────────────────────────────────────────────

def test_discord_price_bound_solves_the_global_floor(floor_030):
    from tracking.discord_notifier import price_bound
    # EV floor: dec >= 1.30 / 0.70 = 1.857 -> -116.7 -> the bound is about -116.
    b = price_bound(0.70, M, 0.0, None, -105)
    assert b is not None and -120 <= b <= -115

"""
Tests for the WNBA market-relative prop rule (models/wnba_prop_market) and its
card (scripts/wnba_prop_market_card), plus the settle-map and NB-head wiring.

The drift tripwires matter most: selector vs settler stat maps, and the shared
find_bets machinery staying shared.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import models.wnba_prop_market as mk  # noqa: E402
from scripts.wnba_prop_market_card import (  # noqa: E402
    PRICE_FLOOR,
    apply_price_floor,
    norm_name,
    pick_rows,
    publish,
)


def _q(line=15.5, over=-110, under=-110):
    return {"line": line, "over_price": over, "under_price": under,
            "over_link": None, "under_link": None}


# ── shared machinery / config invariants ──────────────────────────────────────

def test_selection_functions_are_the_nfl_ones():
    """One implementation of de-vig / like-line / dedupe across both sports."""
    import models.nfl_prop_market as nfl
    assert mk.find_bets is nfl.find_bets
    assert mk.best_per_prop is nfl.best_per_prop
    assert mk.devig is nfl.devig
    assert mk.SHARP_BOOK == "pinnacle"


def test_market_stat_maps_cannot_drift():
    from tracking.paper_tracker import _PROP_MARKET_STAT_BY_MODEL, _PROP_STAT_MAP
    assert _PROP_MARKET_STAT_BY_MODEL["wnba_prop_market"] == mk.MARKET_STAT
    assert _PROP_STAT_MAP["wnba_prop_market"] == ("wnba_player", "FROM_PROP_MARKET")
    # every sharp market settles to a real wnba_player_game_log column
    for m in mk.SHARP_MARKETS:
        assert mk.MARKET_STAT[m] in ("points", "rebounds", "assists")


def test_config_registration():
    from config import ACTION_THRESHOLDS, MODEL_MIN_ODDS, PROP_MODELS
    t = ACTION_THRESHOLDS["wnba_prop_market"]
    assert t["min_prob"] == 0.0 and t["min_edge"] == 0.05
    assert MODEL_MIN_ODDS["wnba_prop_market"] == -140
    # deliberately NOT in PROP_MODELS: no artifact to train or health-check
    assert "wnba_prop_market" not in PROP_MODELS


def test_threes_stays_out_of_sharp_markets():
    """Pinnacle declines player_threes; anchoring it elsewhere is not the rule."""
    assert "player_threes" not in mk.SHARP_MARKETS


# ── selection behaviour on WNBA-shaped quotes ─────────────────────────────────

def test_find_bets_flags_soft_outlier_at_5pp():
    quotes = {
        ("g1", "A Wilson", "player_points", "pinnacle"):  _q(over=-135, under=+115),
        ("g1", "A Wilson", "player_points", "draftkings"): _q(over=-105, under=-115),
    }
    bets, diag = mk.find_bets(quotes, min_edge=0.05, soft_books=mk.SOFT_BOOKS)
    assert diag["compared"] == 1
    assert len(bets) == 1 and bets[0].side == "over" and bets[0].book == "draftkings"
    # fair is Pinnacle's de-vigged over prob
    f_over, _ = mk.devig(-135, +115)
    assert abs(bets[0].fair - f_over) < 1e-9


def test_find_bets_enforces_like_lines():
    quotes = {
        ("g1", "A Wilson", "player_points", "pinnacle"):  _q(line=15.5, over=-150, under=+130),
        ("g1", "A Wilson", "player_points", "draftkings"): _q(line=16.5, over=+100, under=-120),
    }
    bets, diag = mk.find_bets(quotes, min_edge=0.01, soft_books=mk.SOFT_BOOKS)
    assert bets == [] and diag["line_mismatch"] == 1


def test_find_bets_ignores_props_without_a_sharp_quote():
    quotes = {("g1", "K Plum", "player_assists", "draftkings"): _q(over=+120, under=-150)}
    bets, diag = mk.find_bets(quotes, min_edge=0.01, soft_books=mk.SOFT_BOOKS)
    assert bets == [] and diag["no_sharp"] == 1


def test_price_floor_drops_juicy_sides():
    quotes = {
        ("g1", "A Wilson", "player_points", "pinnacle"):  _q(over=-200, under=+170),
        ("g1", "A Wilson", "player_points", "draftkings"): _q(over=-150, under=+120),
    }
    bets, _ = mk.find_bets(quotes, min_edge=0.02, soft_books=mk.SOFT_BOOKS)
    assert bets and bets[0].price == -150          # flagged...
    assert apply_price_floor(bets) == []           # ...but under the -140 floor
    assert PRICE_FLOOR == -140


# ── card plumbing ─────────────────────────────────────────────────────────────

def _bet(**kw):
    d = dict(game_id="g1", player="A'ja Wilson", market="player_points",
             side="over", book="draftkings", line=21.5, price=-105,
             fair=0.58, edge=0.06, sharp_price=-140)
    d.update(kw)
    return mk.MarketBet(**d)


def test_pick_rows_fields_and_label():
    games = {"g1": {"home": "LV", "away": "SEA", "commence_time": "2026-09-05T02:00:00Z"}}
    pid = {norm_name("A'ja Wilson"): "12345"}
    rows = pick_rows([_bet()], games, {}, pid, "2026-09-04", bankroll=1000.0)
    assert len(rows) == 1
    r = rows[0]
    assert r["model_id"] == "wnba_prop_market" and r["sport"] == "WNBA"
    assert r["pick_label"] == "A'ja Wilson Over 21.5 Pts (DK)"
    assert r["model_probability"] == 0.58          # Pinnacle's de-vigged number
    assert abs(r["dk_implied_prob"] - 0.52) < 1e-9  # soft book's own de-vig
    assert r["prop_market"] == "player_points" and r["player_id"] == "12345"
    assert r["signal_type"] == "BET" and r["scored_line"] == 21.5


def test_pick_rows_skips_unresolvable_player():
    """No game-log identity -> permanently unsettleable -> skip, never publish."""
    rows = pick_rows([_bet(player="Total Rookie")], {"g1": {}}, {}, {}, "2026-09-04", 1000.0)
    assert rows == []


def test_pick_rows_dk_link_only_for_draftkings():
    games = {"g1": {}}
    pid = {norm_name("A'ja Wilson"): "1"}
    quotes = {("g1", "A'ja Wilson", "player_points", "fanduel"):
              {"line": 21.5, "over_price": -105, "under_price": -115,
               "over_link": "https://fd/x", "under_link": None}}
    rows = pick_rows([_bet(book="fanduel")], games, quotes, pid, "2026-09-04", 1000.0)
    assert rows[0]["dk_bet_link"] is None          # never a cross-book link
    assert "(FD)" in rows[0]["pick_label"]


class _FakeConn:
    """Records INSERTs; answers the insert-once existence probe."""
    def __init__(self):
        self.inserted = []
        self.committed = 0

    def execute(self, sql, params=None):
        class R:
            def __init__(r, row): r._row = row
            def fetchone(r): return r._row
        if sql.strip().startswith("SELECT 1 FROM picks"):
            key = (params[0], params[1], params[2], params[3], params[4])
            hit = any((i["game_id"], i["model_id"], i["player_key"],
                       i["prop_market"], i["pick_side"]) == key for i in self.inserted)
            return R((1,) if hit else None)
        if sql.strip().startswith("INSERT INTO picks"):
            self.inserted.append(dict(params))
            return R(None)
        raise AssertionError(f"unexpected SQL: {sql[:60]}")

    def commit(self): self.committed += 1


def test_publish_is_insert_once():
    games = {"g1": {}}
    pid = {norm_name("A'ja Wilson"): "1"}
    rows = pick_rows([_bet()], games, {}, pid, "2026-09-04", 1000.0)
    conn = _FakeConn()
    assert publish(conn, rows) == 1
    assert publish(conn, rows) == 0                # locked, never re-priced
    assert len(conn.inserted) == 1


# ── NB-head wiring (item 1 of the same change) ────────────────────────────────

def test_nb_head_changes_probs_only_when_nb_r_present():
    from models.scorer import _nfl_prop_probs
    plain = {"model_type": "poisson"}
    nb    = {"model_type": "poisson", "nb_r": 13.56}
    p0 = _nfl_prop_probs(plain, 5.0, 6.5)[0]
    p1 = _nfl_prop_probs(nb, 5.0, 6.5)[0]
    assert p0 != p1                                 # NB actually engages
    # and the NB tail is fatter above the mean+1.5 line
    assert p1 > p0


def test_assists_artifact_carries_nb_head():
    import pickle
    from config import MODELS_DIR
    pkls = sorted(Path(MODELS_DIR).glob("wnba_prop_player_assists_20260831_*.pkl"))
    assert pkls, "NB-head assists artifact missing"
    with open(pkls[-1], "rb") as f:
        art = pickle.load(f)
    assert art["nb_r"] == 13.56
    assert art["feature_cols"]                      # fit untouched


def test_assists_recut_in_config():
    from config import MODEL_EDGE_THRESHOLDS, MODEL_PROB_THRESHOLDS
    assert MODEL_PROB_THRESHOLDS["wnba_prop_player_assists"] == 0.54
    assert MODEL_EDGE_THRESHOLDS["wnba_prop_player_assists"] == 0.02

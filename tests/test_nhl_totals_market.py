"""The live NHL full-game totals model: Pinnacle's no-vig price, bet a bettable
book that lags it at the same number in the same fetch.

`nhl_over_under` is a frozen rule (models/nhl_totals_market.py), not an
artifact. These tests pin the things that would manufacture an edge or lose a
bet without a trace: pairing quotes from two different fetches, comparing two
different numbers, a price under the -200 floor, an incoherent quote, two bets
on one game, a Pinnacle quote the book has since taken down, the borrowed
calibration map that flattens every Pinnacle price to 0.500, the generic
scorer and trainer reaching a rule id, and settlement as a moneyline.
"""
from __future__ import annotations

import pytest

import config
import models.nhl_totals_market as mk

T0 = "2026-10-07 20:17:07.100000+00"
T1 = "2026-10-07 21:00:07.200000+00"
T2 = "2026-10-07 21:10:07.300000+00"
GAME = "NHL_2026-10-08_PHI_OTT"


def _q(book, created, line, over, under, game=GAME, snap=None):
    """One stored totals row, as load_fetch_quotes returns it."""
    return {
        "game_id": game, "book": book, "created_at": created,
        "snapshot_at": snap or created.replace(" ", "T")[:19] + "Z",
        "total_line": line, "over_price": over, "under_price": under,
        "over_link": f"https://{book}/over", "under_link": f"https://{book}/under",
    }


# Pinnacle +104 / -119 at 6.0: no-vig under 0.52573 (the PHI_OTT hit's price).
PIN = _q("pinnacle", T1, 6.0, 104, -119)


def test_the_soft_books_are_the_bettable_books():
    assert mk.SHARP_BOOK == "pinnacle"
    assert mk.SOFT_BOOKS == tuple(
        b for b in config.BEST_LINE_BOOKMAKERS if b != "pinnacle")
    for unbettable in ("pinnacle", "bovada", "espnbet"):
        assert unbettable not in mk.SOFT_BOOKS
    assert mk.MODEL_ID == "nhl_over_under"


def test_a_soft_quote_pairs_only_with_pinnacle_from_the_same_fetch():
    stale = _q("betmgm", T0, 6.0, -115, -105)
    bets, diag = mk.find_bets([PIN, stale])
    assert bets == []
    assert diag["no_pair"] == 1

    same = _q("betmgm", T1, 6.0, -115, -105)
    bets, diag = mk.find_bets([PIN, stale, same])
    assert len(bets) == 1
    b = bets[0]
    assert (b.book, b.side, b.line, b.price) == ("betmgm", "under", 6.0, -105.0)
    assert b.fair == pytest.approx(0.5257, abs=1e-4)
    assert b.ev == pytest.approx(0.0264, abs=1e-4)
    assert b.created_at == T1
    assert diag["bets"] == 1


def test_a_different_number_is_not_the_same_bet():
    bets, diag = mk.find_bets([PIN, _q("betmgm", T1, 6.5, -115, -105)])
    assert bets == []
    assert diag["line_mismatch"] == 1


def test_the_floor_is_the_models_own_and_inclusive(monkeypatch):
    assert config.min_ev_for("nhl_over_under") == 0.01
    # Pinnacle -110 / -110 is 0.5 a side; +102 pays 2.02, so EV is 0.0100.
    even = _q("pinnacle", T1, 6.5, -110, -110)
    at = _q("fanduel", T1, 6.5, 102, -122)
    bets, _ = mk.find_bets([even, at])
    assert len(bets) == 1 and bets[0].ev == pytest.approx(0.0100, abs=1e-12)
    # Pinnacle +108 / -121 and +116 at the soft book: EV 0.0099.
    under = _q("pinnacle", T1, 6.5, 108, -121)
    below = _q("fanduel", T1, 6.5, 116, -140)
    bets, diag = mk.find_bets([under, below])
    assert bets == []
    assert diag["below_ev_floor"] >= 1
    # Inclusive: a floor equal to the EV, to the last bit, still bets.
    p_over, _ = mk.devig(even["over_price"], even["under_price"])
    ev = config.expected_value(p_over, 102)
    monkeypatch.setitem(config.MODEL_OWN_EV_FLOOR, "nhl_over_under", ev)
    assert len(mk.find_bets([even, at])[0]) == 1
    monkeypatch.setitem(config.MODEL_OWN_EV_FLOOR, "nhl_over_under", ev + 1e-9)
    assert mk.find_bets([even, at])[0] == []


def test_price_floor_and_coherence():
    assert config.min_odds_for("nhl_over_under") == -200
    # Pinnacle -250 / +200: no-vig over 0.6818, so -200 is EV +0.0227.
    pin = _q("pinnacle", T1, 6.0, -250, 200)
    bets, diag = mk.find_bets([pin, _q("fanduel", T1, 6.0, -201, 170)])
    assert bets == []
    assert diag["below_price_floor"] == 1
    bets, _ = mk.find_bets([pin, _q("fanduel", T1, 6.0, -200, 170)])
    assert len(bets) == 1 and bets[0].price == -200.0
    # A soft overround of 1.165 is dropped even though -150 would be EV +0.136.
    bets, diag = mk.find_bets([pin, _q("fanduel", T1, 6.0, -150, -130)])
    assert bets == []
    assert diag["soft_incoherent"] == 1
    # Pinnacle at or below a 1.0 overround is not a price to trust: skip.
    flat = _q("pinnacle", T1, 6.0, 100, 100)
    bets, diag = mk.find_bets([flat, _q("fanduel", T1, 6.0, 120, -140)])
    assert bets == []
    assert diag["sharp_incoherent"] == 1


def test_one_bet_a_game_best_ev_ties_by_book_order():
    # Pinnacle -112 / +102: no-vig over 0.5162; -103 is EV +0.0175.
    pin = _q("pinnacle", T1, 6.5, -112, 102)
    br = _q("betrivers", T1, 6.5, -103, -117)
    parx = _q("betparx", T1, 6.5, -103, -117)
    bets, _ = mk.find_bets([pin, parx, br])
    assert len(bets) == 1 and bets[0].book == "betrivers"
    dk = _q("draftkings", T1, 6.5, -103, -117)
    bets, _ = mk.find_bets([pin, parx, br, dk])
    assert len(bets) == 1 and bets[0].book == "draftkings"
    # Over at one book, under at another: the higher EV wins, not book order.
    even = _q("pinnacle", T1, 6.0, -105, -105)
    fd_under = _q("fanduel", T1, 6.0, -125, 105)      # under EV +0.025
    mgm_over = _q("betmgm", T1, 6.0, 110, -130)       # over EV +0.05
    bets, _ = mk.find_bets([even, fd_under, mgm_over])
    assert len(bets) == 1
    assert (bets[0].book, bets[0].side) == ("betmgm", "over")


def test_pinnacle_withdrawn_means_no_bet_this_pass():
    hit = _q("betmgm", T1, 6.0, -115, -105)
    later_fd = _q("fanduel", T2, 6.0, -110, -110)
    bets, diag = mk.find_bets([PIN, hit, later_fd])
    assert bets == []
    assert diag["pinnacle_withdrawn"] == 1
    # The 30-second poller writes DraftKings alone; that is not a new fetch.
    later_dk = _q("draftkings", T2, 6.0, -110, -110)
    bets, diag = mk.find_bets([PIN, hit, later_dk])
    assert len(bets) == 1 and bets[0].book == "betmgm"
    assert diag["pinnacle_withdrawn"] == 0


def test_the_quote_read_is_one_fetch_and_pre_game():
    """The SQL is where the pre-game bound lives; in-play rows are stored as
    'open' too, so both timestamps are bounded on the game's start."""
    import inspect
    src = inspect.getsource(mk.load_fetch_quotes)
    assert "snapshot_type = 'open'" in src
    assert "o.snapshot_at::timestamptz <= g.ct" in src
    assert "o.created_at::timestamptz <= g.ct" in src
    assert "o.created_at = p.created_at" in src
    assert "<> 'draftkings'" in src


def test_it_settles_as_totals_off_the_final_score():
    from tracking import paper_tracker as pt
    assert "nhl_over_under" not in config.MODELS
    assert pt._RULE_MODEL_MARKETS["nhl_over_under"] == "totals"
    assert pt._market_for_pick("nhl_over_under") == "totals"
    # A 4-3 shootout final is stored with the shootout goal: 7 > 6.5.
    result, flat, _ = pt._compute_result(
        "over", "totals", 4, 3, 1, 0, 1, 103, None, 6.5, 100.0)
    assert result == "WIN" and flat == pytest.approx(103.0)
    result, flat, _ = pt._compute_result(
        "under", "totals", 4, 2, 1, 1, 0, -105, None, 6.0, 100.0)
    assert result == "PUSH" and flat == 0.0


def test_decided_on_its_own_probability(monkeypatch):
    """The promoted pooled map (b = -0.26) sends a 0.5257 Pinnacle price to
    0.500, which is EV -0.024 at -105. On its own number it is +0.0264."""
    import models.scorer as sc
    from models.honest_ev import gate
    from models.probability_calibration import apply_calibration

    promoted = {"method": "platt", "a": 1.0, "b": -0.259947}
    assert apply_calibration(0.5257, promoted) == 0.5
    monkeypatch.setattr(sc, "_CAL_CACHE", {"nhl_over_under": promoted})
    g = gate("nhl_over_under", 0.5257, -105)
    assert g.ev == pytest.approx(0.5257 * (1 + 100 / 105) - 1)
    assert g.ev == pytest.approx(0.0264, abs=1e-4)
    assert g.clears
    assert sc._calibrated("nhl_over_under", 0.5257) == 0.5257


def test_the_generic_scorer_and_the_trainer_cannot_reach_it(monkeypatch):
    from features.feature_engine import FEATURE_MAP
    import models.trainer as trainer
    from tracking.system_health import KNOWN_UNTRAINED

    assert "nhl_over_under" not in config.MODELS
    assert "nhl_over_under" not in FEATURE_MAP
    assert "nhl_over_under" not in KNOWN_UNTRAINED
    assert config.scoring_method("nhl_over_under") == "rule"

    def _no_db(*a, **k):
        raise AssertionError("reached the database")

    import data.db
    import features.feature_engine as fe
    monkeypatch.setattr(data.db, "get_connection", _no_db)
    monkeypatch.setattr(fe, "get_connection", _no_db)
    monkeypatch.setattr(trainer, "get_connection", _no_db)
    monkeypatch.setattr(trainer, "_store_artifact", _no_db)
    # The early return for --no-register must not make the refusal vacuous.
    monkeypatch.setattr(trainer, "REGISTER_TRAINED_MODELS", True)
    with pytest.raises(ValueError):
        trainer.train_model("nhl_over_under")
    with pytest.raises(ValueError, match="rule"):
        trainer._register_model("nhl_over_under", "v1", [2025], 2026, {},
                                "models/saved/nhl_over_under_v1.pkl")

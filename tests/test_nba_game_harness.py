"""scripts/nba_game_harness: the rules every cell of the second NBA game-market
search is graded under (docs/nba_models_2026.md §6.2), checked on small games
built by hand so each rule is pinned by its outcome, not by its code."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H

TIP = pd.Timestamp("2024-01-16T00:30:00Z")      # 7:30 ET on 2024-01-15


def _games():
    return pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-01-15",
                          "tip": TIP, "home_team": "BOS", "away_team": "NYK",
                          "home_score": 110, "away_score": 100}])


def _fetches(*leads):
    return pd.DataFrame({"game_id": "G", "tip": TIP,
                         "fetch_at": [TIP - pd.Timedelta(minutes=m) for m in leads],
                         "lead_min": [float(m) for m in leads]})


def _q(book, market, fetch_lead, snap_lead, line, pa, pb):
    return {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "tip": TIP,
            "market": market, "book": book,
            "fetch_at": TIP - pd.Timedelta(minutes=fetch_lead),
            "snapshot_at": TIP - pd.Timedelta(minutes=snap_lead),
            "line": line, "price_a": pa, "price_b": pb, "coherent": True}


def test_each_point_takes_the_newest_fetch_in_its_window_never_the_last_15_minutes():
    f = _fetches(570, 300, 210, 150, 90, 60, 30, 10)
    g = _games()
    got = {p: H.decision_times(f, g, p)["lead_min"].tolist() for p in ("B", "C", "D")}
    assert got == {"B": [210.0], "C": [60.0], "D": [60.0]}
    # nothing between 45 and 75 -> the game has no D decision at all
    assert H.decision_times(_fetches(90, 30, 10), g, "D").empty


def test_point_a_is_the_15z_fetch_on_the_eastern_game_date():
    # 15Z on 2024-01-15 is 570 minutes before a 00:30Z tip on the 16th
    t = H.decision_times(_fetches(600, 570, 300), _games(), "A")
    assert t["T"].tolist() == [pd.Timestamp("2024-01-15T15:00:00Z")]


def test_a_later_fetch_is_invisible_and_an_hour_old_quote_is_stale():
    q = pd.DataFrame([
        _q("fanduel", "spreads", 60, 66, -5.5, -110, -110),       # the fetch at T
        _q("fanduel", "spreads", 30, 64, -6.5, -110, -110),       # later fetch, older stamp
        _q("betmgm", "spreads", 150, 140, -5.0, -110, -110),      # 80 min before T: stale
        _q("caesars", "spreads", 90, 100, -5.0, -105, -115),      # 40 min before T: fresh
    ])
    t = pd.DataFrame({"game_id": ["G"], "T": [TIP - pd.Timedelta(minutes=60)]})
    v = H.visible(q, t).set_index("book")
    assert set(v.index) == {"fanduel", "caesars"}
    assert v.loc["fanduel", "line"] == -5.5


def test_a_push_returns_the_stake_and_leaves_the_denominator():
    g = _games()                                      # home by 10
    bets = pd.DataFrame([
        {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "market": "spreads",
         "side": "home", "line": -10.0, "price": -110.0},       # push
        {"game_id": "G", "season": 2024, "game_date": "2024-01-15", "market": "spreads",
         "side": "home", "line": -9.5, "price": -110.0},        # win 1u, risk 1.1
    ])
    b = H.grade(bets, g)
    assert b["result"].tolist() == ["P", "W"]
    assert b["units"].tolist() == pytest.approx([0.0, 1.0])
    assert H.roi(b) == pytest.approx(1.0 / 1.1)
    assert H.roi(b, kept=True) == pytest.approx(1.0 / 2.2)


def test_the_spread_side_uses_the_home_number():
    # home margin ~ N(+8, 12): home -6.5 should be a favourite to cover,
    # away +6.5 (stored line still -6.5) the complement
    pw, pp = H.side_probs(np.array(["spreads", "spreads"]), np.array(["home", "away"]),
                          np.array([-6.5, -6.5]), mu=[8.0, 8.0], sigma=[12.0, 12.0])
    assert pw[0] > 0.5 and pw[0] + pw[1] == pytest.approx(1.0) and pp.tolist() == [0.0, 0.0]


def _offers():
    rows = [
        # side, book, line, price, p_win
        ("home", "draftkings", -5.5, -110, 0.56),
        ("home", "fanduel", -4.5, -115, 0.60),     # better number, better EV
        ("home", "pinnacle", -4.5, 105, 0.60),     # never deciding
        ("away", "betmgm", -4.5, -250, 0.85),      # best EV of all, but below the -200 floor
    ]
    return pd.DataFrame([{"game_id": "G", "season": 2024, "game_date": "2024-01-15",
                          "T": TIP - pd.Timedelta(minutes=60), "market": "spreads",
                          "side": s, "book": b, "line": l, "price": float(p),
                          "p_win": w, "p_push": 0.0} for s, b, l, p, w in rows])


def test_the_best_ev_offer_wins_across_books_and_numbers_within_the_house_rules():
    pick = H.choose(_offers(), cut=0.0)
    assert len(pick) == 1 and pick.iloc[0]["book"] == "fanduel"
    dk = H.choose(_offers(), cut=0.0, books=("draftkings",))
    assert dk.iloc[0]["book"] == "draftkings"
    assert H.choose(_offers(), cut=0.20).empty


def test_bh_counts_the_untested_cells_in_m():
    p = {"a": 1e-6, "b": 2e-5, "c": 0.01}
    assert H.bh_pass(p, m_total=3) == {"a", "b", "c"}
    # at m = 4,172 the bar for rank 1 is 1.2e-5 and for rank 2 is 2.4e-5
    assert H.bh_pass(p, m_total=4172) == {"a", "b"}
    assert H.bh_pass({"a": 2e-5}, m_total=4172) == set()


def test_rows_join_their_fetch_on_created_at_and_strays_take_the_next_fetch():
    q = pd.DataFrame({"created_at": ["2026-10-15 22:59:14.314171+00", "2026-10-16 01:00:00+00"],
                      "snapshot_at": pd.to_datetime(["2024-01-15T22:54:00Z",
                                                     "2024-01-15T23:20:00Z"], utc=True)})
    led = pd.DataFrame({"requested_at": pd.to_datetime(["2024-01-15T23:00:00Z",
                                                        "2024-01-15T23:30:00Z"], utc=True),
                        "pulled_at": pd.to_datetime(["2026-10-15 22:59:14.314171+00",
                                                     "2026-10-17 00:00:00+00"], utc=True,
                                                    format="mixed")})
    out, notes = H.attach_fetch(q, led)
    assert out["fetch_at"].tolist() == [pd.Timestamp("2024-01-15T23:00:00Z"),
                                        pd.Timestamp("2024-01-15T23:30:00Z")]
    assert notes["rows_matched_on_created_at"] == 1 and notes["rows_placed_by_snapshot"] == 1


def test_an_unmatched_best_price_is_an_outlier_and_a_matched_one_is_not():
    off = _offers()
    off = off[off["book"] != "pinnacle"]
    bets = pd.DataFrame([off.iloc[1]])                          # fanduel -4.5 -115, alone at -4.5
    assert bool(H.outlier_flag(bets, off).iloc[0]) is True
    # a second deciding book (Caesars is williamhill_us in the feed), 5 cents worse
    twin = off.iloc[[1]].assign(book="williamhill_us", price=-120.0)
    assert bool(H.outlier_flag(bets, pd.concat([off, twin])).iloc[0]) is False


def test_the_bootstrap_is_seeded_and_refines_small_p(monkeypatch):
    rng = np.random.default_rng(0)
    days = pd.date_range("2025-10-21", periods=150).astype(str)
    b = pd.DataFrame({"game_date": np.repeat(days, 4), "units": 0.0, "risk": 1.1})
    b["units"] = np.where(rng.random(len(b)) < 0.75, 1.0, -1.1)     # a huge edge
    calls = []
    real = H.boot
    monkeypatch.setattr(H, "boot", lambda x, n=H.N_BOOT, seed=H.SEED: calls.append(n) or real(x, n, seed))
    assert H.p_one_sided(b) < H.P_REFINE_BELOW
    assert calls == [H.N_BOOT, H.P_REFINE_N]
    assert np.array_equal(real(b), real(b))


def test_the_arithmetic_checks_pass():
    H.check()

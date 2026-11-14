"""The five EuroLeague pre-game rules (models/euroleague_pregame.py), on
hand-built boards whose right answer is known.

Each rule is the research's own (scripts/euroleague_research r1_/r2_/r3_), and
the build replays the research bet for bet on the cache
(scripts/euroleague_pregame_build.py; tests/test_euroleague_pregame_build.py
pins its artifact). These pin the pieces that replay rests on: the coherence
filter, the board at an instant, the floor applied before the best price, the
modal number, the rung rules, Pinnacle's ladder, the club shares and the
conflict rule.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.euroleague_pregame as R  # noqa: E402

TIP = pd.Timestamp("2026-11-20T19:00:00Z")
T = TIP - pd.Timedelta(minutes=10)
ART = {"models": {
    R.HOME_ML: {"params": {"min_price": -200.0, "min_season": 2022}, "uplift": 0.05},
    R.HEAVY_FAV_ML: {"params": {"max_price": -500.0}, "uplift": 0.07},
    R.HOME_DOG_SPREAD: {"params": {"min_home_line": 0.0}, "uplift": 0.09},
    R.H1_DOG_ML: {"params": {}, "uplift": 0.05},
    R.Q1_SHARE_TOTAL: {"params": {"margin": 1.0, "k_share": 40.0, "prior_gap_hours": 3.0}, "uplift": 0.15},
}}


def game(gid="G1", season=2027, home="MAD", away="PAN", neutral=False, venue="WIZINK CENTER"):
    return pd.DataFrame([{"game_id": gid, "season": season, "home_code": home, "away_code": away,
                          "neutral_site": neutral, "venue_name": venue, "tip": TIP}])


def fg(rows):
    """(book, market, minutes before tip, a, b, line) -> stored rows."""
    out = []
    for book, market, mins, a, b, line, *gid in rows:
        r = {"game_id": gid[0] if gid else "G1", "market": market, "bookmaker": book,
             "snapshot_at": TIP - pd.Timedelta(minutes=mins), "home_price": None, "away_price": None,
             "spread_home": None, "total_line": None, "over_price": None, "under_price": None}
        if market == "totals":
            r.update(over_price=a, under_price=b, total_line=line)
        else:
            r.update(home_price=a, away_price=b)
            if market == "spreads":
                r["spread_home"] = line
        out.append(r)
    return pd.DataFrame(out)


def board(rows, at=T, gids=("G1",)):
    q = R.prepare_fullgame(fg(rows), pd.Series({g: TIP for g in gids}))
    return R.board_at(q, pd.Series({g: at for g in gids}))


# ── the board ────────────────────────────────────────────────────────────────

def test_an_incoherent_quote_is_dropped_and_the_coherent_one_before_it_stands():
    b = board([("draftkings", "h2h", 60, -150, 130, None),
               ("draftkings", "h2h", 20, -150, -130, None),      # both favourites: incoherent
               ("draftkings", "h2h", 15, -150, 50, None)])       # a price inside -100..+100
    assert len(b) == 1 and b.pa.iloc[0] == -150 and b.pb.iloc[0] == 130


def test_the_board_takes_the_newest_quote_at_or_before_the_instant_never_after():
    b = board([("draftkings", "h2h", 60, -150, 130, None),
               ("draftkings", "h2h", 10, -170, 145, None),       # stamped exactly at T
               ("draftkings", "h2h", 5, -300, 240, None)])       # after T
    assert b.pa.iloc[0] == -170


def test_a_quote_stamped_after_the_tip_is_never_pre_game():
    q = R.prepare_fullgame(fg([("draftkings", "h2h", -5, -150, 130, None)]), pd.Series({"G1": TIP}))
    assert q.empty


def test_power_de_vig_sums_to_one_and_favours_the_favourite_more_than_multiplicative():
    a, b = R.power_fair(R.imp(np.array([-400.0])), R.imp(np.array([300.0])))
    assert abs(a[0] + b[0] - 1) < 1e-9
    mult = R.imp(-400) / (R.imp(-400) + R.imp(300))
    assert a[0] > mult


# ── model 1: the home moneyline ──────────────────────────────────────────────

def test_the_floor_is_applied_before_the_best_price_is_picked():
    b = board([("draftkings", "h2h", 30, -220, 180, None),
               ("fanduel", "h2h", 30, -190, 160, None),
               ("betmgm", "h2h", 30, -195, 165, None)])
    d = R.decide_home_ml(b, game(), ART)[0]
    assert (d.status, d.side, d.book, d.price) == ("bet", "home", "fanduel", -190.0)
    assert d.dk_price == -220.0


def test_every_home_price_shorter_than_the_floor_is_a_none_row_at_the_best_one():
    b = board([("draftkings", "h2h", 30, -260, 210, None), ("fanduel", "h2h", 30, -240, 200, None)])
    d = R.decide_home_ml(b, game(), ART)[0]
    assert (d.status, d.book, d.price) == ("no_bet", "fanduel", -240.0)


def test_a_neutral_site_is_not_priced_by_the_home_rules():
    b = board([("draftkings", "h2h", 30, 120, -140, None),
               ("draftkings", "spreads", 30, -110, -110, 2.5)])
    assert R.decide_home_ml(b, game(neutral=True), ART)[0].status == "not_eligible"
    assert R.decide_home_dog(b, game(neutral=True), ART)[0].status == "not_eligible"


def test_only_the_books_a_pick_may_name_are_read():
    b = board([("pinnacle", "h2h", 30, 150, -170, None), ("bovada", "h2h", 30, 160, -180, None)])
    assert R.decide_home_ml(b, game(), ART)[0].status == "no_quotes"
    b = board([("pinnacle", "h2h", 30, 150, -170, None), ("draftkings", "h2h", 30, 140, -160, None)])
    assert R.decide_home_ml(b, game(), ART)[0].book == "draftkings"


def test_a_tie_in_price_goes_to_the_book_first_in_name_order():
    b = board([("fanduel", "h2h", 30, 140, -160, None), ("betmgm", "h2h", 30, 140, -165, None)])
    assert R.decide_home_ml(b, game(), ART)[0].book == "betmgm"


# ── model 2: the big favourite ───────────────────────────────────────────────

def test_the_favourite_at_minus_500_or_shorter_is_bet_on_either_side_neutral_included():
    b = board([("draftkings", "h2h", 30, 400, -520, None), ("fanduel", "h2h", 30, 380, -500, None)])
    d = R.decide_heavy_fav(b, game(neutral=True), ART)[0]
    # the best away price is FanDuel's -500, still at the cutoff
    assert (d.status, d.side, d.book, d.price) == ("bet", "away", "fanduel", -500.0)


def test_a_best_price_longer_than_minus_500_is_a_none_row_on_the_favourite():
    b = board([("draftkings", "h2h", 30, -520, 400, None), ("betmgm", "h2h", 30, -480, 370, None)])
    d = R.decide_heavy_fav(b, game(), ART)[0]
    assert (d.status, d.side, d.price) == ("no_bet", "home", -480.0)


# ── model 3: the home underdog spread ────────────────────────────────────────

def test_the_modal_number_ties_go_nearest_the_median_then_to_the_lower():
    assert R.modal_line(pd.Series([2.5, 3.5, 3.5, 2.5, 6.5])) == 3.5
    assert R.modal_line(pd.Series([2.5, 3.5])) == 2.5


def test_the_home_underdog_is_bet_on_the_modal_number_at_its_best_price():
    b = board([("draftkings", "spreads", 30, -110, -110, 3.5),
               ("fanduel", "spreads", 30, -105, -115, 3.5),
               ("betmgm", "spreads", 30, 100, -120, 2.5)])
    d = R.decide_home_dog(b, game(), ART)[0]
    assert (d.status, d.line, d.book, d.price) == ("bet", 3.5, "fanduel", -105.0)


def test_a_home_favourite_or_a_pick_em_is_a_none_row():
    for line in (-3.5, 0.0):
        b = board([("draftkings", "spreads", 30, -110, -110, line)])
        assert R.decide_home_dog(b, game(), ART)[0].status == "no_bet"


def test_a_relocated_home_game_is_not_priced():
    b = board([("draftkings", "spreads", 30, -110, -110, 4.5)])
    d = R.decide_home_dog(b, game(home="TEL", venue=" BELGRADE ARENA "), ART)[0]
    assert d.status == "not_eligible" and "R1" in d.detail
    # the same club in its own country is priced
    assert R.decide_home_dog(b, game(home="TEL", venue="MENORA MIVTACHIM ARENA"), ART)[0].status == "bet"


# ── the period fetch ─────────────────────────────────────────────────────────

def per(rows):
    out = []
    for book, market, a, b, line, *gid in rows:
        r = {"game_id": gid[0] if gid else "G1", "market": market, "bookmaker": book,
             "home_price": None, "away_price": None, "spread_home": None, "total_line": None,
             "over_price": None, "under_price": None}
        if market.startswith("totals") or market == R.LADDER_MARKET:
            r.update(over_price=a, under_price=b, total_line=line)
        else:
            r.update(home_price=a, away_price=b, spread_home=line)
        out.append(r)
    return pd.DataFrame(out)


def test_an_off_centre_main_and_one_two_points_from_every_other_book_are_rungs():
    p = R.prepare_period(per([("fanduel", "totals_q1", -110, -110, 41.5),
                              ("betrivers", "totals_q1", -112, -108, 42.0),
                              ("betmgm", "totals_q1", -110, -110, 44.5),     # far from both
                              ("fanatics", "totals_q1", -250, 190, 41.5)]))  # off centre
    flags = dict(zip(p.bookmaker, p.rung))
    assert flags == {"fanduel": False, "betrivers": False, "betmgm": True, "fanatics": True}


def test_a_lone_book_is_never_far():
    p = R.prepare_period(per([("betmgm", "totals_q1", -110, -110, 44.5)]))
    assert not p.rung.iloc[0]


def test_the_first_half_underdog_is_the_side_under_one_half_on_the_mean_no_vig():
    p = R.prepare_period(per([("fanduel", "h2h_h1", -150, 125, None),
                              ("betrivers", "h2h_h1", -145, 130, None),
                              ("pinnacle", "h2h_h1", 200, -240, None)]))   # never read
    d = R.decide_h1_dog(p, game(), ART)[0]
    assert (d.status, d.side, d.book, d.price) == ("bet", "away", "betrivers", 130.0)
    assert 0.40 < d.p_fair < 0.50


def test_a_level_first_half_mean_is_a_pick_em_with_no_bet():
    p = R.prepare_period(per([("fanduel", "h2h_h1", -110, -110, None)]))
    assert R.decide_h1_dog(p, game(), ART)[0].status == "pick_em"


# ── model 5: the club first-quarter share ────────────────────────────────────

def test_pinnacles_ladder_interpolates_at_its_first_crossing_of_one_half():
    lad = per([("pinnacle", R.LADDER_MARKET, -130, 110, 160.5),
               ("pinnacle", R.LADDER_MARKET, -105, -115, 162.5),
               ("pinnacle", R.LADDER_MARKET, 120, -140, 165.5)])
    f = R.ladder_fair(lad)
    pa = R.imp(np.array([-105.0, -115.0]))
    p1 = pa[0] / pa.sum()
    lo = R.imp(-130) / (R.imp(-130) + R.imp(110))
    assert f == pytest.approx(160.5 + (0.5 - lo) * 2.0 / (p1 - lo))


def test_the_anchor_falls_back_to_pinnacles_main_total_then_draftkings():
    fgb = board([("pinnacle", "totals", 30, -110, -110, 163.5),
                 ("draftkings", "totals", 30, -110, -110, 164.5)])
    assert R.anchor(per([]), fgb, "G1") == (163.5, "pinnacle main")
    fgb = board([("draftkings", "totals", 30, -110, -110, 164.5)])
    assert R.anchor(per([]), fgb, "G1") == (164.5, "draftkings main")


def history(n, share, home="MAD", away="PAN", hours=48):
    return pd.DataFrame([{"game_id": f"H{i}", "tip": TIP - pd.Timedelta(hours=hours + i),
                          "home_code": home if i % 2 else away, "away_code": "OLY",
                          "share": share} for i in range(n)]).sort_values("tip").reset_index(drop=True)


def test_a_game_inside_three_hours_of_the_tip_is_not_an_earlier_game():
    h = pd.concat([history(10, 0.25), pd.DataFrame([{"game_id": "X", "tip": TIP - pd.Timedelta(hours=2),
                                                    "home_code": "MAD", "away_code": "OLY", "share": 0.9}])])
    s = R.pair_share(h.sort_values("tip"), TIP, "MAD", "PAN", 40, 3)
    assert s["n_league"] == 10 and s["league"] == pytest.approx(0.25)


def test_the_club_share_shrinks_by_n_over_n_plus_k():
    h = pd.concat([history(20, 0.24, home="ZAL", away="OLY"),
                   pd.DataFrame([{"game_id": f"M{i}", "tip": TIP - pd.Timedelta(hours=10 + i),
                                  "home_code": "MAD", "away_code": "ZAL", "share": 0.30} for i in range(5)])])
    s = R.pair_share(h.sort_values("tip"), TIP, "MAD", "PAN", 40, 3)
    lm = (20 * 0.24 + 5 * 0.30) / 25
    assert s["league"] == pytest.approx(lm)
    assert s["dev_home"] == pytest.approx((5 * 0.30 - 5 * lm) / (5 + 40))
    assert s["dev_away"] == 0.0


def q1_case(line, share=0.26, total=160.0, books=(("fanduel", -115, -105), ("betrivers", -110, -110))):
    rows = [(b, "totals_q1", a, u, line) for b, a, u in books]
    # Pinnacle's ladder crosses one half exactly at `total`
    rows += [("pinnacle", R.LADDER_MARKET, -125, 105, total - 0.5),
             ("pinnacle", R.LADDER_MARKET, 105, -125, total + 0.5)]
    raw = per(rows)
    p = R.prepare_period(raw)
    return R.decide_q1_share(p, raw, board([]), history(60, share), game(), ART)[0]


def test_the_over_is_bet_a_point_or_more_above_the_number_and_the_under_below():
    d = q1_case(39.5, share=0.26)                # about 0.26 x 160 = 41.6
    assert (d.status, d.side) == ("bet", "over")
    assert d.book == "betrivers" and d.price == -110.0   # the best over price on the number
    d = q1_case(43.5, share=0.26)
    assert (d.status, d.side) == ("bet", "under")
    d = q1_case(41.0, share=0.26)                # within a point
    assert d.status == "no_bet"


def test_no_earlier_game_and_no_anchor_record_no_bet():
    raw = per([("fanduel", "totals_q1", -110, -110, 40.5)])
    p = R.prepare_period(raw)
    assert R.decide_q1_share(p, raw, board([]), history(10, 0.25), game(), ART)[0].status == "no_anchor"
    raw = per([("fanduel", "totals_q1", -110, -110, 40.5), ("pinnacle", R.LADDER_MARKET, -125, 105, 159.5),
               ("pinnacle", R.LADDER_MARKET, 105, -125, 160.5)])
    p = R.prepare_period(raw)
    empty = pd.DataFrame({"game_id": [], "tip": pd.to_datetime([], utc=True), "home_code": [],
                          "away_code": [], "share": []})
    assert R.decide_q1_share(p, raw, board([]), empty, game(), ART)[0].status == "no_shares"


# ── one game never carries two bets that cannot both win ────────────────────

def test_home_and_away_moneylines_cannot_both_win():
    a = {"market": "h2h", "side": "home", "line": None}
    b = {"market": "h2h", "side": "away", "line": None}
    assert R.cannot_both_win(a, b)


@pytest.mark.parametrize("line,conflict", [(1.0, True), (0.5, True), (1.5, False), (6.5, False)])
def test_a_home_spread_and_the_away_moneyline(line, conflict):
    a = {"market": "spreads", "side": "home", "line": line}
    b = {"market": "h2h", "side": "away", "line": None}
    assert R.cannot_both_win(a, b) is conflict


def test_a_period_bet_never_conflicts_with_a_full_game_bet():
    a = {"market": "h2h_h1", "side": "away", "line": None}
    b = {"market": "h2h", "side": "home", "line": None}
    assert not R.cannot_both_win(a, b)


def _bet(model, side, line=None, gid="G1"):
    return R.Decision(gid, model, "bet", "x", side=side, price=-110.0, line=line)


def test_two_bets_in_one_pass_that_cannot_both_win_are_both_written_none():
    ds = [_bet(R.HOME_ML, "home"), _bet(R.HEAVY_FAV_ML, "away"), _bet(R.H1_DOG_ML, "home"),
          _bet(R.HOME_DOG_SPREAD, "home", 9.5)]
    R.resolve_conflicts(ds, standing=[])
    assert [d.status for d in ds] == ["no_bet", "no_bet", "bet", "bet"]
    assert "same pass" in ds[0].detail


def test_a_standing_bet_keeps_the_game():
    ds = [_bet(R.HOME_ML, "home"), _bet(R.HOME_ML, "home", gid="G2")]
    R.resolve_conflicts(ds, standing=[{"game_id": "G1", "model_id": "euroleague_live_spread_ht",
                                       "market": "spreads", "side": "away", "line": 3.5, "label": "PAN -3.5"}])
    assert [d.status for d in ds] == ["no_bet", "bet"]
    assert "already bet" in ds[0].detail


# ── the probability ──────────────────────────────────────────────────────────

def test_the_uplift_is_the_win_share_less_the_mean_no_vig_before_the_season_pushes_out():
    bets = pd.DataFrame({"season": [2026, 2026, 2026, 2026, 2027], "res": [1, -1, 1, 0, -1],
                         "p_fair": [0.5, 0.5, 0.4, 0.9, 0.5]})
    u, n = R.uplift_from(bets, 2027)
    assert n == 3 and u == pytest.approx(2 / 3 - (0.5 + 0.5 + 0.4) / 3)
    assert R.uplift_from(bets, 2026) == (None, 0)


def test_the_probability_is_clipped_and_ev_and_edge_follow_it():
    d = R.finish(R.Decision("G1", R.HEAVY_FAV_ML, "bet", side="home", price=-4000.0, p_fair=0.97), 0.07)
    assert d.p_model == 0.99
    assert d.ev == pytest.approx(0.99 * (1 + 100 / 4000) - 1)
    assert d.edge == pytest.approx(0.99 - 4000 / 4100)


def test_the_artifact_for_another_season_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "ARTIFACT_DIR", tmp_path)
    (tmp_path / "euroleague_pregame_2028.json").write_text('{"season": 2027}', encoding="utf-8")
    with pytest.raises(ValueError):
        R.load_artifact(2028)
    with pytest.raises(FileNotFoundError):
        R.load_artifact(2029)

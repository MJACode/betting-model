"""scripts/nba_s_fav200: the search on moneyline favourites shorter than -200
(docs/nba_search_fav200.md). Every rule is pinned on hand-built or synthetic games
by its outcome, and each test was watched failing once with its rule broken. No real
price or result is read."""
import os

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_verdict as V
from scripts import nba_game_harness as H
from scripts import nba_s_fav200 as F

TIP = pd.Timestamp("2024-01-16T00:30:00Z")
FETCH = pd.Timestamp("2024-01-15T23:30:00Z")


def quote(game, book, pa, pb, market="h2h", line=np.nan, fetch=FETCH):
    return {"game_id": game, "season": 2024, "game_date": "2024-01-15", "tip": TIP, "market": market, "book": book,
            "snapshot_at": fetch - pd.Timedelta(minutes=5), "fetch_at": fetch, "line": line,
            "price_a": float(pa), "price_b": float(pb), "coherent": True}


def offers_of(prices: dict, game="g", side="home", date="2024-01-15") -> list[dict]:
    """A favourite's offers, book -> price, with what H.choose reads."""
    return [{"game_id": game, "season": 2024, "game_date": date, "market": "h2h", "book": b, "side": side,
             "side_pick": side, "price": float(p), "line": np.nan, "p_win": 0.9, "p_push": 0.0,
             "ev": 0.9 * float(H.dec(np.array([float(p)]))[0]) - 1.0, "mu": np.nan,
             "p_home": 0.9 if side == "home" else 0.1} for b, p in prices.items()]


# ── the cells ───────────────────────────────────────────────────────────────

def test_the_registered_cells_are_12_blind_16_same_number_and_12_model():
    specs = F.cell_specs()
    assert len(specs) == 40
    blind = [s for s in specs if s[0] == F.FAVB]
    assert len(blind) == 12 and {s[1] for s in blind} == set("ABCD") and {s[2] for s in blind} == set(F.BANDS)
    same = [s for s in specs if s[0] == F.FAVP2]
    assert len(same) == 16 and {s[1] for s in same} == set("ABCD") and {s[4] for s in same} == {0.0, 0.01, 0.02, 0.03}
    model = [s for s in specs if s[0] == F.FAVP1]
    assert len(model) == 12 and {s[1] for s in model} == set("ACD") and {s[4] for s in model} == {0.02, 0.04, 0.06, 0.08}


def test_controls_are_labelled_so_the_verdict_never_judges_them():
    specs = F.control_specs()
    assert len(specs) == 40
    assert all(s[0].startswith(V.CONTROL_PREFIX) for s in specs)
    assert not {s[0] for s in specs} & set(V.JUDGED_CONTROLS_5)


# ── the bands, the range, the floor ─────────────────────────────────────────

@pytest.mark.parametrize("price,band", [(-200.0, None), (-201.0, "200_300"), (-300.0, "200_300"), (-301.0, "300_500"),
                                        (-500.0, "300_500"), (-501.0, "500_up"), (-5000.0, "500_up"), (-150.0, None)])
def test_each_price_sits_in_the_band_the_document_names(price, band):
    kf = F.keyed(pd.DataFrame(offers_of({"fanduel": price})))
    got = [name for name, (lo, hi) in F.BANDS.items() if F.band_flags(kf, lo, hi)[0] == 1.0]
    assert got == ([] if band is None else [band])


def test_a_game_with_a_better_book_inside_the_old_floor_is_not_bet_at_the_worse_book():
    # fanduel -190 is inside every earlier search; nobody would take betmgm's -205 there
    x = pd.DataFrame(offers_of({"fanduel": -190.0, "betmgm": -205.0}))
    assert F.best_in_range(x, *F.RULE_RANGE).empty
    # the opposite shape stays: its best offer is short of -200, and the bet is that best offer
    y = pd.DataFrame(offers_of({"fanduel": -205.0, "betmgm": -240.0}, game="h"))
    kept = F.best_in_range(y, *F.RULE_RANGE)
    assert len(kept) == 2
    with F.price_floor(F.RULE_FLOOR):
        assert H.choose(kept, -np.inf, sides=[F.SIDE])["price"].tolist() == [-205.0]


def test_the_rule_range_stops_at_the_minus_1000_floor():
    x = pd.DataFrame(offers_of({"fanduel": -1000.0}, game="a") + offers_of({"fanduel": -1001.0}, game="b"))
    assert set(F.best_in_range(x, *F.RULE_RANGE)["game_id"]) == {"a"}


def test_the_floor_reaches_the_choice_and_the_blind_bet_and_comes_back():
    f = pd.DataFrame(offers_of({"fanduel": -600.0}))
    games = pd.DataFrame({"game_id": ["g"], "home_score": [110.0], "away_score": [100.0]})
    assert H.choose(f, 0.0, sides=[F.SIDE]).empty                    # the house floor shuts it out
    with F.price_floor(F.RULE_FLOOR):
        assert len(H.choose(f, 0.0, sides=[F.SIDE])) == 1
        assert len(H.blind_side(f, F.SIDE, games)) == 1              # the blind comparison reads it too
    assert H.PRICE_FLOOR == float(H.config.DEFAULT_MIN_ODDS)
    with pytest.raises(ValueError):
        with F.price_floor(F.NO_FLOOR):
            raise ValueError
    assert H.PRICE_FLOOR == float(H.config.DEFAULT_MIN_ODDS)


def test_the_cap_arithmetic_as_the_document_states_it():
    r, w = H.risk_win(np.array([-200.0, -300.0, -400.0, -500.0, -1000.0, -2000.0]))
    assert np.allclose(r, [2.0, 3.0, 3.0, 3.0, 3.0, 3.0])
    assert np.allclose(w, [1.0, 1.0, 0.75, 0.6, 0.3, 0.15])


# ── the favourite ───────────────────────────────────────────────────────────

def test_the_favourite_comes_from_the_market_line_and_never_from_the_result():
    q = pd.DataFrame([quote("g", "pinnacle", -400, 330), quote("g", "fanduel", -420, 340),
                      quote("h", "pinnacle", 500, -650), quote("h", "fanduel", 520, -700)])
    t = pd.DataFrame({"game_id": ["g", "h"], "T": [FETCH, FETCH]})
    vis = H.visible(q, t)
    fair = H.market_fair(vis, {})
    fv = F.favourites(H.fair_offers(H.offers(vis), fair)).set_index("game_id")
    assert fv.loc["g", "fav"] == "home" and fv.loc["h", "fav"] == "away"
    games = pd.DataFrame({"game_id": ["g", "h"], "home_score": [90.0, 120.0], "away_score": [120.0, 90.0]})
    off = F.on_side(H.fair_offers(H.offers(vis), fair), fv.reset_index())
    # both favourites lost; they are still the sides bet, at their real side
    picked = H.choose(off, -np.inf, sides=[F.SIDE], floor=F.NO_FLOOR).set_index("game_id")
    assert picked.loc["g", "side"] == "home" and picked.loc["h", "side"] == "away"
    assert H.grade(picked.reset_index(), games)["result"].tolist() == ["L", "L"]


def test_a_moneyline_settles_on_the_final_score_and_an_away_favourite_wins_with_the_away_team():
    games = pd.DataFrame({"game_id": ["g"], "home_score": [101.0], "away_score": [108.0]})
    bets = pd.DataFrame({"game_id": ["g"], "market": ["h2h"], "side": ["away"], "line": [np.nan], "price": [-500.0]})
    g = H.grade(bets, games)
    assert g["result"].tolist() == ["W"] and np.isclose(g["units"].iloc[0], 0.6) and np.isclose(g["risk"].iloc[0], 3.0)


def test_the_spread_control_reads_the_home_number():
    # an away favourite at -5.5 is stored +5.5: away by 6 covers, away by 5 does not
    games = pd.DataFrame({"game_id": ["g", "h"], "home_score": [100.0, 100.0], "away_score": [106.0, 105.0]})
    bets = pd.DataFrame({"game_id": ["g", "h"], "market": ["spreads"] * 2, "side": ["away"] * 2, "line": [5.5, 5.5],
                         "price": [-110.0, -110.0]})
    assert H.grade(bets, games)["result"].tolist() == ["W", "L"]


# ── impossible numbers ──────────────────────────────────────────────────────

def _fetch(*rows):
    return pd.DataFrame(list(rows))


def test_a_swapped_moneyline_quote_is_dropped_and_its_game_keeps_the_true_best_price():
    q = _fetch(quote("g", "pinnacle", -400, 330), quote("g", "draftkings", -420, 340), quote("g", "betmgm", -410, 330),
               quote("g", "fanduel", 330, -400))             # two prices swapped
    bad = F.bad_moneyline(q)
    assert bad.tolist() == [False, False, False, True]


def test_a_bad_pinnacle_quote_is_dropped_too():
    q = _fetch(quote("g", "pinnacle", 300, -400), quote("g", "draftkings", -420, 340), quote("g", "betmgm", -410, 330),
               quote("g", "fanduel", -400, 320))
    assert F.bad_moneyline(q).tolist() == [True, False, False, False]


def test_a_fetch_with_fewer_than_four_books_cannot_be_judged_and_is_kept():
    q = _fetch(quote("g", "draftkings", -420, 340), quote("g", "betmgm", -410, 330), quote("g", "fanduel", 330, -400))
    assert not F.bad_moneyline(q).any()


def test_a_real_but_wide_quote_is_kept():
    # about 10 points of no-vig chance off the median: unusual, not impossible
    q = _fetch(quote("g", "pinnacle", -400, 330), quote("g", "draftkings", -420, 340), quote("g", "betmgm", -410, 330),
               quote("g", "fanduel", -240, 200))
    assert not F.bad_moneyline(q).any()


def test_a_price_inside_100_is_not_a_price():
    q = _fetch(quote("g", "pinnacle", -400, 50), quote("g", "draftkings", -420, 340))
    assert F.bad_moneyline(q).tolist() == [True, False]


def test_a_spread_far_from_its_fetch_or_with_a_flipped_sign_is_dropped():
    rows = [quote("g", b, -110, -110, market="spreads", line=-7.5) for b in ("pinnacle", "draftkings", "betmgm")]
    rows.append(quote("g", "fanduel", -110, -110, market="spreads", line=7.5))
    rows.append(quote("g", "betrivers", -110, -110, market="spreads", line=-8.5))
    assert F.bad_spread(_fetch(*rows)).tolist() == [False, False, False, True, False]


# ── the placebo ─────────────────────────────────────────────────────────────

def test_the_week_shuffle_is_a_permutation_inside_each_week_and_repeats_with_its_seed():
    block = np.array([0, 0, 0, 1, 1, 2, 2, 2, 2, 2])
    p = F.block_perm(block, 3)
    assert sorted(p) == list(range(10)) and (block[p] == block).all()
    assert (F.block_perm(block, 3) == p).all() and not all((F.block_perm(block, s) == p).all() for s in (4, 5, 6))


def _week_of_lone_candidates() -> F.Keyed:
    """A week with one candidate game per date: the shape a same-date shuffle cannot move."""
    rows = []
    for i, day in enumerate(("2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19", "2024-01-20")):
        rows += offers_of({"fanduel": -250.0 - i, "betmgm": -260.0 - i}, game=f"g{i}", date=day)
    return F.keyed(pd.DataFrame(rows))


def test_a_candidate_alone_on_its_date_still_moves_under_the_week_shuffle():
    kf = _week_of_lone_candidates()
    ev = np.where(kf.frame["game_id"] == "g0", 0.05, -0.03)      # one game's rule fires
    kf = F.keyed(kf.frame.assign(ev=ev))
    with F.price_floor(F.RULE_FLOOR):
        real = H.choose(kf.frame, 0.02, sides=[F.SIDE])
        week = F.differ_share(real, (H.choose(F.ev_builder(kf)(s), 0.02, sides=[F.SIDE]) for s in range(1, 41)))
        date = F.differ_share(real, (H.choose(F.ev_builder(kf, kf.date)(s), 0.02, sides=[F.SIDE]) for s in range(1, 41)))
    assert list(real["game_id"]) == ["g0"]
    assert date == 0.0                                           # same-date repeats the real bet every run
    assert week > 0.6


def test_differ_share_counts_only_bets_on_a_game_the_cell_does_not_bet():
    real = pd.DataFrame({"game_id": ["a", "b"], "season": 2024})
    runs = [pd.DataFrame({"game_id": ["a", "c", "d", "e"], "season": 2024})]
    assert F.differ_share(real, runs) == 0.75


def _blind_frame() -> F.Keyed:
    rows = []
    for i, price in enumerate((-110.0, -150.0, -250.0, -280.0, -400.0, -700.0)):
        rows += offers_of({"fanduel": price, "betmgm": price - 10.0}, game=f"g{i}", date=f"2024-01-{15 + i % 3}")
    return F.keyed(pd.DataFrame(rows))


def test_a_blind_placebo_moves_the_band_to_other_favourites_and_leaves_every_price_where_it_was():
    kf = _blind_frame()
    lo, hi = F.BANDS["200_300"]
    real = F.blind_cand(kf, lo, hi)
    assert real.loc[real["strength"] == 1.0, "game_id"].drop_duplicates().tolist() == ["g2", "g3"]
    runs = [F.blind_builder(kf, lo, hi)(s) for s in range(1, 21)]
    for pc in runs:
        assert (pc["price"].to_numpy() == kf.frame["price"].to_numpy()).all()
        # one flag per game, and the same count as the real cell
        assert pc.groupby("game_id")["strength"].nunique().max() == 1
        assert pc.drop_duplicates("game_id")["strength"].sum() == 2.0
    moved = {tuple(pc.loc[pc["strength"] == 1.0, "game_id"].drop_duplicates()) for pc in runs}
    assert len(moved) > 1


def test_a_same_number_placebo_keeps_the_rate_the_prices_and_each_offers_gap_to_its_best():
    rows = []
    for i in range(6):
        rows += offers_of({"fanduel": -250.0 - i, "betmgm": -270.0 - i}, game=f"g{i}")
    kf = F.keyed(pd.DataFrame(rows))
    # two of six games fire; each game's second book sits 0.01 under its best
    ev = np.repeat([0.05, -0.03, -0.02, -0.04, -0.01, 0.03], 2) + np.tile([0.0, -0.01], 6)
    kf = F.keyed(kf.frame.assign(ev=ev))
    cut = 0.01
    real_n = kf.frame.groupby("game_id")["ev"].max().ge(cut).sum()
    for s in range(1, 11):
        pc = F.ev_builder(kf)(s)
        assert (pc["price"].to_numpy() == kf.frame["price"].to_numpy()).all()
        assert pc.groupby("game_id")["ev"].max().ge(cut).sum() == real_n
        gap = pc.groupby("game_id")["ev"].max() - pc.groupby("game_id")["ev"].min()
        gap0 = kf.frame.groupby("game_id")["ev"].max() - kf.frame.groupby("game_id")["ev"].min()
        assert np.allclose(gap.sort_index().to_numpy(), gap0.sort_index().to_numpy())


def _model_keyed() -> F.Keyed:
    rows = []
    for i, (price, mkt, mv) in enumerate(((-250.0, 0.70, 0.30), (-400.0, 0.79, -0.20), (-300.0, 0.74, 0.05))):
        rows += offers_of({"fanduel": price, "betmgm": price - 15.0}, game=f"g{i}")
        for r in rows[-2:]:
            r.update(p_mkt=mkt, move_fav=mv)
    x = pd.DataFrame(rows)
    p = 1.0 / (1.0 + np.exp(-(F._logit(x["p_mkt"]) + x["move_fav"].to_numpy())))
    return F.keyed(x.assign(p_win=p, ev=p * H.dec(x["price"]) - 1.0))


def test_a_model_placebo_with_each_game_keeping_its_own_move_is_the_model(monkeypatch):
    kf = _model_keyed()
    monkeypatch.setattr(F, "block_perm", lambda block, seed: np.arange(len(block)))
    pc = F.move_builder(kf)(1)
    assert np.allclose(pc["ev"], kf.frame["ev"]) and np.allclose(pc["p_win"], kf.frame["p_win"])


def test_a_model_placebo_adds_another_games_move_to_this_games_own_market_chance(monkeypatch):
    kf = _model_keyed()
    monkeypatch.setattr(F, "block_perm", lambda block, seed: np.array([1, 2, 0]))
    pc = F.move_builder(kf)(1).drop_duplicates("game_id").set_index("game_id")
    # g0's own market chance 0.70 with g1's move -0.20
    want = 1.0 / (1.0 + np.exp(-(np.log(0.70 / 0.30) - 0.20)))
    assert np.isclose(pc.loc["g0", "p_win"], want)
    assert pc.loc["g0", "price"] == -250.0


def test_the_model_moves_toward_the_favourite_whichever_side_it_is():
    # the same home-side move helps a home favourite and hurts an away favourite
    fair = pd.DataFrame({"game_id": ["h", "a"], "market": "h2h", "mu": np.nan, "sigma": np.nan,
                         "p_home": [0.80, 0.20], "ref": "pinnacle"})
    off = pd.DataFrame([{**offers_of({"fanduel": -300.0}, game="h", side="home")[0], "T": FETCH},
                        {**offers_of({"fanduel": -300.0}, game="a", side="away")[0], "T": FETCH}])
    off = off.drop(columns=["p_win", "p_push", "ev", "mu", "p_home", "side_pick"])
    moves = pd.DataFrame({"game_id": ["h", "a"], "market": "h2h", "season": 2024, "move": [0.4, 0.4]})
    pt = type("Pt", (), {"fair": fair, "off": off, "neutral": off.merge(fair, on=["game_id", "market"]).assign(p_win=0.7, p_push=0.0, ev=0.0)})
    fv = pd.DataFrame({"game_id": ["h", "a"], "fav": ["home", "away"], "dog": ["away", "home"]})
    kf, _ = F.model_cands(pt, moves, fv)
    x = kf.frame.set_index("game_id")
    assert np.isclose(x.loc["h", "move_fav"], 0.4) and np.isclose(x.loc["a", "move_fav"], -0.4)
    assert np.isclose(x.loc["h", "p_mkt"], 0.80) and np.isclose(x.loc["a", "p_mkt"], 0.80)
    assert x.loc["h", "p_win"] > 0.80 > x.loc["a", "p_win"]


def test_the_placebo_bets_other_games_on_a_world_with_several_games_a_date():
    fr = F.frames_at(F.prep_from(F.synthetic_world(seasons=(2024, 2025, 2026), dates=20)), "C")
    d = pd.DataFrame(F.differ_rows(fr, seeds=(1, 2, 3, 4, 5)))
    blind = d[d["family"] == F.FAVB]
    assert len(blind) == 3 and (blind["real_bets"] >= 30).all()
    assert (blind["differ_week"] > 0.5).all()


# ── the same-number rule's two chances ──────────────────────────────────────

def test_each_offer_carries_its_own_proportional_and_power_chance():
    rows = [quote("g", "pinnacle", -400, 330), quote("g", "fanduel", -360, 280), quote("g", "betmgm", -450, 340),
            quote("h", "pinnacle", 500, -650), quote("h", "fanduel", 480, -600)]
    q = pd.DataFrame(rows)
    t = pd.DataFrame({"game_id": ["g", "h"], "T": [FETCH, FETCH]})
    from scripts import nba_game4_p2 as P2
    pt = P2.point_frames(P2.main_rungs(q), P2.rungs_at_pinnacle(q), t, {})
    prop, powr = F.same_cands(pt, F.favourites(pt.neutral))
    ia, ib = float(H.imp(np.array([-400.0]))[0]), float(H.imp(np.array([330.0]))[0])
    # g's favourite is home: every g offer reads Pinnacle's own chance, at its own price
    x = prop.frame[prop.frame["game_id"] == "g"].set_index("book")
    assert np.allclose(x["p_win"], ia / (ia + ib))
    assert np.isclose(x.loc["fanduel", "ev"], ia / (ia + ib) * float(H.dec(np.array([-360.0]))[0]) - 1.0)
    # h's favourite is away: the chance is the away side's, not the home side's
    y = prop.frame[prop.frame["game_id"] == "h"].set_index("book")
    assert y.loc["fanduel", "side"] == "away" and y.loc["fanduel", "price"] == -600.0 and y.loc["fanduel", "p_win"] > 0.8
    # the power method moves a short favourite up, row by row, and the frames are the same offers
    assert (powr.frame["p_win"].to_numpy() > prop.frame["p_win"].to_numpy()).all()
    assert (powr.frame["price"].to_numpy() == prop.frame["price"].to_numpy()).all()
    with F.price_floor(F.RULE_FLOOR):
        assert H.choose(prop.frame, -np.inf, sides=[F.SIDE]).set_index("game_id").loc["g", "price"] == -360.0


# ── what is reported beside a cell ──────────────────────────────────────────

def test_lone_best_reads_each_bet_at_its_own_row_whatever_its_index():
    cand = pd.DataFrame(offers_of({"fanduel": -250.0, "betmgm": -260.0}, game="near")
                        + offers_of({"fanduel": -250.0, "betmgm": -400.0}, game="far")
                        + offers_of({"fanduel": -300.0}, game="only"))
    bets = pd.DataFrame(offers_of({"fanduel": -250.0}, game="far") + offers_of({"fanduel": -250.0}, game="near")
                        + offers_of({"fanduel": -300.0}, game="only"), index=[7, 3, 11])
    assert F.lone_best(bets, cand).tolist() == [True, False, True]


def test_the_no_cap_return_is_one_unit_to_win_at_every_price():
    g = pd.DataFrame({"game_id": ["a", "b"], "season": 2024, "market": "h2h", "side": "home", "price": [-1000.0, -300.0],
                      "result": ["W", "L"], "units": [0.3, -3.0], "risk": [3.0, 3.0], "risk_kept": [3.0, 3.0]})
    cand = pd.DataFrame(offers_of({"fanduel": -1000.0}, game="a") + offers_of({"fanduel": -300.0}, game="b"))
    out = F.report_columns(g, cand, set())
    # one to win: +1 at -1000 risking 10, -3 at -300 risking 3. (1 - 3) / 13
    assert np.isclose(out["roi_no_cap"], -2.0 / 13.0)
    assert out["pb_500_1000_n"] == 1 and out["pb_200_300_n"] == 1 and out["pb_1000_up_n"] == 0


def test_the_blind_cell_writes_its_bands_with_the_band_below_first():
    x = pd.DataFrame(offers_of({"fanduel": -200.0}, game="edge") + offers_of({"fanduel": -250.0}, game="own")
                     + offers_of({"fanduel": -400.0}, game="next") + offers_of({"fanduel": -1500.0}, game="top")
                     + offers_of({"fanduel": -140.0}, game="out"))
    games = pd.DataFrame({"game_id": ["edge", "own", "next", "top", "out"], "season": 2024, "home_score": 110.0, "away_score": 100.0})
    with F.price_floor(F.NO_FLOOR):
        out = F.price_band_columns(x, F.SIDE, F.BLIND_BOUNDS["200_300"], games, (2024,))
    assert [out[f"band{i}_n"] for i in range(4)] == [1, 1, 1, 1]
    assert out["band_slots"] == 4
    # -200 itself reads as the band below, never as the first new band
    assert out["band0_hi"] == -150.0 and out["band0_lo"] == -200.0
    row = pd.Series(out)
    assert V.bands_ok(row)
    row["band2_roi"] = -0.1
    row["band2_n"] = 30
    assert not V.bands_ok(row)


# ── a run on a made-up world, the path --full takes ─────────────────────────

@pytest.fixture(scope="module")
def world(tmp_path_factory):
    bets = tmp_path_factory.mktemp("bets")
    os.environ[F.BETS_ENV] = str(bets)
    try:
        # one decision point: --full's own check_rows covers all four; a fit needs scipy, slow to import
        r = F.run_world(F.synthetic_world(dates=10), seeds=(1, 2), points=("C",))
    finally:
        os.environ.pop(F.BETS_ENV, None)
    r["bets"] = bets
    return r


def test_the_world_holds_what_the_checks_claim_it_covers():
    data = F.synthetic_world(seasons=(2025, 2026), dates=12)
    ml = data.quotes[data.quotes["market"] == F.MARKET]
    assert F.bad_moneyline(ml).sum() > 0
    assert (data.quotes["market"] == F.SPREADS).any()
    fr = F.frames_at(F.prep_from(data), "C")
    best = fr.blind.per_game_max(fr.blind.frame["price"].to_numpy(float))
    for lo, hi in F.BANDS.values():
        assert ((best >= lo) & (best < hi)).sum() >= 10
    assert (fr.same.frame.groupby("game_id")["ev"].max() >= 0).sum() >= 1
    # a swapped row was in the world and did not reach a decision
    assert len(fr.blind.frame) > 0 and fr.blind.frame["price"].max() < 0


def test_every_registered_cell_and_control_runs_and_nothing_else(world):
    F.check_rows(world["rows"], [s for s in F.cell_specs() if s[1] == "C"], "judged")
    F.check_rows(world["controls"], [s for s in F.control_specs() if s[1] == "C"], "controls")
    with pytest.raises(AssertionError):
        F.check_rows(world["rows"][1:], [s for s in F.cell_specs() if s[1] == "C"], "judged")


def test_a_judged_cell_bets_only_the_favourite_inside_its_range(world, tmp_path):
    files = sorted(world["bets"].rglob("*.parquet"))
    assert files
    fams = {p.parent.name for p in files}
    assert {f"{F.FAVB}_200_300", f"{F.FAVB}_300_500", f"{F.FAVB}_500_up"} <= fams and F.FAVP2 in fams and F.FAVP1 in fams
    for p in files:
        fam = p.parent.name
        if fam.startswith("control_"):
            continue
        b = pd.read_parquet(p)                                   # parquet stores it, and reads it back
        assert not {"sigma", "sigma1"} & set(b.columns)
        assert b["market"].eq("h2h").all() and b["side"].isin(["home", "away"]).all()
        if fam == f"{F.FAVB}_200_300":
            assert b["price"].between(-300.0, -201.0).all()
        elif fam == f"{F.FAVB}_300_500":
            assert b["price"].between(-500.0, -301.0).all()
        elif fam == f"{F.FAVB}_500_up":
            assert (b["price"] < -500.0).all()
        else:
            assert b["price"].between(-1000.0, -201.0).all(), fam
    fair = pd.read_parquet(next(p for p in files if p.parent.name == F.FAVB + "_500_up"))
    # a bet is on the side the world made the favourite, shown by its price
    assert (fair["price"] < 0).all()


def test_the_underdog_control_bets_the_other_side_of_the_same_games(world):
    files = sorted((world["bets"] / f"{F.C_DOG}_300_500").glob("*.parquet"))
    dog = pd.concat(pd.read_parquet(p) for p in files)
    fav = pd.concat(pd.read_parquet(p) for p in sorted((world["bets"] / f"{F.FAVB}_300_500").glob("*.parquet")))
    x = dog.merge(fav[["game_id", "point", "side"]], on=["game_id", "point"], suffixes=("_dog", "_fav"))
    assert len(x) > 0 and (x["side_dog"] != x["side_fav"]).all()
    assert (dog["price"] > 0).all()


def test_the_spread_control_bets_the_favourite_at_its_home_number(world):
    files = sorted(world["bets"].glob(f"{F.C_SPREAD}_*/*.parquet"))
    assert files, "the spread control placed no bet: the world does not cover it"
    b = pd.concat(pd.read_parquet(p) for p in files)
    assert b["market"].eq(F.SPREADS).all()
    # the world stores a favourite's number at home as minus, at away as plus
    assert (b.loc[b["side"] == "home", "line"] < 0).all() and (b.loc[b["side"] == "away", "line"] > 0).all()
    assert (b["side"] == "home").any() and (b["side"] == "away").any()


def test_the_blind_comparison_of_a_band_is_favourites_at_large_not_itself(world):
    d = pd.DataFrame([r for r in world["rows"] if r["family"] == F.FAVB])
    assert (d["pool_share_fav"] == 1.0).all()
    assert d["blind_pool_fav"].notna().all()
    assert (d["population_games"] > d["pool_n"]).all()
    assert not np.allclose(d["blind_pool_fav"], d["pool_roi"])


def test_the_verdict_reads_the_cells_back_and_judges_only_the_registered_cells(world, tmp_path):
    for fam in {r["family"] for r in world["rows"]}:
        F.write_family(world["rows"], fam, tmp_path)
    for fam in {r["family"] for r in world["controls"]}:
        F.write_family(world["controls"], fam, tmp_path)
    cells = V.load_cells(tmp_path)
    assert len(cells) == 21                                  # 11 judged and 10 controls at one point
    h = V.house_verdict_bands(cells, n_placebo=2)
    assert len(h) == 11 and not h["family"].astype(str).str.startswith("control_").any()
    assert h["key"].is_unique
    assert {f"band{i}_n" for i in range(4)} <= set(h.columns)


def test_a_planted_edge_is_found_and_a_world_with_none_is_not():
    point, band = "C", "300_500"
    seeds = tuple(range(1, 31))

    def cell(plant):
        data = F.synthetic_world(seed=23, dates=40, plant=plant)
        prep = F.prep_from(data)
        fr = F.frames_at(prep, point)
        return F.emit_blind(prep.ml, point, fr.times, fr.blind, prep.close, seeds, set(), bands=(band,))[0]
    planted = cell({-280.0: 0.12, -350.0: 0.12})             # the two fair prices that land in this band
    assert planted["pool_ci95_lo"] > 0
    assert planted["roi_choose"] > np.percentile(planted["placebo_rois"], 95)
    none = cell(None)
    assert none["pool_ci95_lo"] < 0


# ── the guards ──────────────────────────────────────────────────────────────

def test_inside_a_no_result_run_a_grade_on_real_scores_stops_the_run():
    games = pd.DataFrame({"game_id": ["g"], "season": 2024, "game_date": "2024-01-15", "tip": TIP, "home_team": "A",
                          "away_team": "B", "home_score": [110.0], "away_score": [100.0]})
    bets = pd.DataFrame({"game_id": ["g"], "market": ["h2h"], "side": ["home"], "line": [np.nan], "price": [-300.0]})
    with F.only_random_scores():
        with pytest.raises(RuntimeError):
            H.grade(bets, games)
        blinded = F.blind_scores(games)
        assert len(H.grade(bets, blinded)) == 1
    assert len(H.grade(bets, games)) == 1                    # and the harness is back afterwards


def test_random_scores_keep_nothing_of_the_real_ones_and_never_tie():
    games = pd.DataFrame({"game_id": [f"g{i}" for i in range(500)], "home_score": 300.0, "away_score": 300.0})
    b = F.blind_scores(games)
    assert (b["home_score"] != 300.0).all() and (b["home_score"] != b["away_score"]).all()
    assert b.attrs[F.BLINDED] is True and not games.attrs.get(F.BLINDED)


def test_the_projection_counts_200_placebo_runs_for_every_cell():
    times = {"frames_A": 0.0, "blind_cell_with_1_placebo": 0.0, "same_4_cells_with_1_placebo": 0.0,
             "controls_at_one_point": 0.0, "placebo_blind": 1.0, "placebo_same": 1.0}
    p = F.projection(times, skip_model=True)
    assert p["blind_s"] == 12 * 200 and p["same_s"] == 16 * 200
    assert p["total_minutes"] == (12 + 16) * 200 / 60
    times.update(model_setup=0.0, model_4_cells_with_1_placebo=0.0, placebo_model=1.0)
    assert F.projection(times, skip_model=False)["model_s"] == 12 * 200


def test_the_placebo_cost_is_the_extra_time_of_the_extra_seeds_per_cell(monkeypatch):
    clock, calls = [0.0], []
    monkeypatch.setattr(F.time, "perf_counter", lambda: clock[0])

    def run(seeds):
        calls.append(len(seeds))
        clock[0] += 7.0 + 0.5 * len(seeds)                   # one cell's report, then its placebo runs
    assert F.placebo_cost(run, cells=2, extra=4) == pytest.approx(0.5 / 2)
    assert calls == [5, 1]                                   # the longer call first


@pytest.mark.parametrize("missing", [F.GO_ENV, F.RESULTS_ENV, F.BETS_ENV])
def test_full_refuses_without_each_setting(missing, tmp_path, monkeypatch):
    (tmp_path / "nba_fetch_ledger.parquet").write_bytes(b"")
    (tmp_path / F.P.STINTS_FILE).write_bytes(b"")
    for k in (F.GO_ENV, F.RESULTS_ENV, F.BETS_ENV):
        monkeypatch.setenv(k, "1")
    assert F.refuse_full(tmp_path) == []
    monkeypatch.delenv(missing)
    assert any(missing in w for w in F.refuse_full(tmp_path))
    with pytest.raises(SystemExit):
        F.full(tmp_path)

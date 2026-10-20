"""scripts/nba_game4_p2: the first search's market rules re-graded on the shared
harness (docs/nba_models_2026.md §8, choices in §8.2). Every rule is pinned on
small games built by hand, by its outcome rather than its code; nothing here
reads a priced season."""
import numpy as np
import pandas as pd
import pytest

from scripts import nba_game_harness as H
from scripts import nba_game4_p2 as P

TIP = pd.Timestamp("2024-01-16T00:30:00Z")          # 7:30 ET on 2024-01-15

# symmetric empirical distributions: a balanced price at a number solves to it
_R = np.random.default_rng(11).normal(0, 1, 1000)
EMP_SP = H.ResidDist(np.r_[_R, -_R] * 12.0, "test spreads")
EMP_TOT = H.ResidDist(np.r_[_R, -_R] * 18.0, "test totals")
EMP_TT = H.ResidDist(np.r_[_R, -_R] * 10.0, "test team totals")
SIG = {(2024, "spreads"): EMP_SP, (2024, "totals"): EMP_TOT,
       **{(2024, m): EMP_TT for m in P.TT_MARKETS},
       **{(2024, m): EMP_SP for m in ("spreads_h1", "spreads_q1")},
       **{(2024, m): EMP_TOT for m in ("totals_h1", "totals_q1")}}


def _game(gid, day, hs, aw, season=2024):
    tip = TIP + pd.Timedelta(days=day)
    return {"game_id": gid, "season": season,
            "game_date": (tip - pd.Timedelta(hours=5)).strftime("%Y-%m-%d"), "tip": tip,
            "home_team": f"H{gid}", "away_team": f"A{gid}", "home_score": float(hs),
            "away_score": float(aw)}


def _q(g, book, market, lead, line, pa, pb, coherent=True):
    return {"game_id": g["game_id"], "season": g["season"], "game_date": g["game_date"],
            "tip": g["tip"], "market": market, "book": book,
            "fetch_at": g["tip"] - pd.Timedelta(minutes=lead),
            "snapshot_at": g["tip"] - pd.Timedelta(minutes=lead + 5),
            "line": np.nan if line is None else float(line), "price_a": float(pa),
            "price_b": float(pb), "coherent": coherent}


def _data(games, quotes):
    g = pd.DataFrame(games)
    q = pd.DataFrame(quotes)
    f = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    return H.Data(games=g, quotes=q, fetches=f.reset_index(drop=True))


def _times(games, lead):
    return pd.DataFrame({"game_id": [g["game_id"] for g in games],
                         "T": [g["tip"] - pd.Timedelta(minutes=lead) for g in games],
                         "lead_min": float(lead)})


def _point(quotes, games, lead, sig=SIG):
    q = pd.DataFrame(quotes)
    return P.point_frames(P.main_rungs(q), P.rungs_at_pinnacle(q), _times(games, lead), sig)


def _row(rows, rule, market, side, cut):
    got = [r for r in rows if (r["axis_rule"], r["market"], r["side"]) == (rule, market, side)
           and r["cut"] == pytest.approx(cut)]
    assert len(got) == 1
    return got[0]


# ── the cells ───────────────────────────────────────────────────────────────

def test_the_registered_cells_are_256_with_team_totals_pooled_and_no_moneyline_off_number():
    plan = P.cell_plan()
    assert len(plan) == 256 == P.EXPECTED_CELLS
    same = [c for c in plan if c[0] == "same_number"]
    off = [c for c in plan if c[0] == "off_number"]
    assert (len(same), len(off)) == (152, 104)
    assert {c[2] for c in off} == {"spreads", "totals", "spreads_h1", "totals_h1", "spreads_q1",
                                  "totals_q1", "team_totals"}
    assert {c[3] for c in plan if c[2] == "team_totals"} == {"over", "under"}
    assert {c[1] for c in plan if c[2] in P.DERIV_LABELS} == {"D"}
    assert {c[1] for c in plan if c[2] in P.FULL_MARKETS} == {"A", "B", "C", "D"}
    assert {c[5] for c in same} == {0.0, 0.01, 0.02, 0.03}
    assert {c[5] for c in off} == {0.5, 1.0, 1.5, 2.0}


def test_the_cell_table_must_be_exactly_the_registered_cells():
    rows = [{"family": "P2", "axis_rule": r, "point": p, "market": m, "side": s, "cut_index": k,
             "cut": c} for r, p, m, s, k, c in P.cell_plan()]
    assert len(P.check_cells(rows)) == 256
    with pytest.raises(AssertionError):
        P.check_cells(rows[:-1])
    bad = [dict(x) for x in rows]
    bad[0]["market"] = "team_totals_home"
    with pytest.raises(AssertionError):
        P.check_cells(bad)


# ── which quote is a book's number ──────────────────────────────────────────

LADDER = [(110.5, -139, 108), (111.5, -112, -112), (112.5, 105, -135), (113.5, 125, -160)]


def _ladder(book="betrivers", rungs=LADDER, market="team_totals_home", lead=60):
    g = _game("G", 0, 110, 100)
    return [_q(g, book, market, lead, ln, a, b) for ln, a, b in rungs]


def test_a_book_hanging_several_rungs_is_read_at_its_most_even_rung():
    q = pd.DataFrame(_ladder())
    assert P.main_rungs(q)["line"].tolist() == [111.5]
    # an incoherent rung is never the main one, even when its prices look even
    inc = pd.DataFrame(_ladder() + [_q(_game("G", 0, 110, 100), "betrivers", "team_totals_home",
                                       60, 109.5, 150, 150, coherent=False)])
    assert P.main_rungs(inc)["line"].tolist() == [111.5]
    # two equally even rungs: the lower number, whatever the row order
    tie = pd.DataFrame(_ladder(rungs=[(112.5, -110, -110), (111.5, -110, -110)]))
    assert P.main_rungs(tie)["line"].tolist() == [111.5]
    assert P.main_rungs(tie.iloc[::-1])["line"].tolist() == [111.5]


def test_the_same_number_rule_reads_a_ladder_books_rung_at_pinnacles_number():
    g = _game("G", 0, 110, 100)
    q = pd.DataFrame(_ladder() + [_q(g, "pinnacle", "team_totals_home", 60, 112.5, -110, -110),
                                  _q(g, "fanduel", "team_totals_home", 60, 111.5, -110, -110)])
    got = P.rungs_at_pinnacle(q).set_index("book")["line"].to_dict()
    # betrivers hangs 112.5 (not its main rung); fanduel hangs only 111.5, its main
    assert got == {"betrivers": 112.5, "fanduel": 111.5, "pinnacle": 112.5}
    assert P.main_rungs(q).set_index("book")["line"].to_dict()["betrivers"] == 111.5


def _vis(rows):
    q = pd.DataFrame(rows)
    return q.assign(T=q["fetch_at"])


def test_a_derivative_rung_more_than_a_point_off_the_deciding_median_is_a_ladder():
    g = _game("G", 0, 110, 100)
    v = _vis([_q(g, "fanduel", "spreads_h1", 60, -2.0, -110, -110),
              _q(g, "draftkings", "spreads_h1", 60, -2.5, -110, -110),
              _q(g, "betmgm", "spreads_h1", 60, -1.0, -110, -110),      # 1.0 off the median: kept
              _q(g, "hardrockbet", "spreads_h1", 60, 1.5, -165, 130),   # 3.5 off: a ladder rung
              _q(g, "pinnacle", "spreads_h1", 60, 2.0, -110, -110),     # Pinnacle is never dropped
              _q(g, "fanduel", "spreads", 60, 9.0, -110, -110),         # the full game has no ladders
              _q(g, "draftkings", "spreads", 60, -3.0, -110, -110),
              _q(g, "betmgm", "spreads", 60, -3.0, -110, -110)])
    drop = P.ladder_mask(v, v)
    assert v.loc[drop, "book"].tolist() == ["hardrockbet"]


# ── the rules: pairing in one fetch, at one number ──────────────────────────

def _two_games():
    # G1 home wins by 10, G2 home loses by 3. Decision C at tip - 120.
    g1, g2 = _game("G1", 0, 110, 100), _game("G2", 1, 100, 103)
    q = [_q(g1, "pinnacle", "spreads", 120, -5.5, -120, 100),        # home share .5217
         _q(g1, "fanduel", "spreads", 120, -5.5, -105, -115),        # same number, EV .0186
         _q(g1, "draftkings", "spreads", 120, -5.0, -110, -110),     # home gets half a point more
         _q(g1, "betmgm", "spreads", 150, -5.5, 120, -150),          # an older fetch: never paired
         _q(g1, "pinnacle", "h2h", 120, None, -250, 210),
         _q(g1, "fanduel", "h2h", 120, None, -240, 200),
         _q(g2, "pinnacle", "totals", 120, 220.5, -110, -110),
         _q(g2, "fanduel", "totals", 120, 222.5, -110, -110),        # a higher total: under +2
         _q(g2, "draftkings", "totals", 120, 220.5, -108, -112)]
    return [g1, g2], q


def test_same_number_pairs_only_books_at_pinnacles_number_in_pinnacles_fetch():
    games, q = _two_games()
    c = P.same_number_cand(_point(q, games, 120))
    sp = c[c["market"] == "spreads"]
    assert set(sp["book"]) == {"fanduel"}                    # not draftkings (-5.0), not betmgm (old fetch)
    home = sp[sp["side"] == "home"].iloc[0]
    share = H.imp(-120) / (H.imp(-120) + H.imp(100))
    assert home["p_win"] == pytest.approx(share)
    assert home["ev"] == pytest.approx(share * H.dec(-105) - 1)
    assert home["p_push"] == 0.0
    assert set(c.loc[c["market"] == "h2h", "book"]) == {"fanduel"}   # a moneyline pairs at any number
    tot = c[c["market"] == "totals"]
    assert set(tot["book"]) == {"draftkings"} and set(tot["side"]) == {"over", "under"}


def test_the_rules_never_see_a_score():
    games, q = _two_games()
    v = _point(q, games, 120).vis_main
    o = P.to_first_search(v[v["market"] == "spreads"])
    assert o["home_score"].isna().all() and o["away_score"].isna().all()


def test_the_adapter_restores_each_derivative_market_and_its_sides():
    g = _game("G", 0, 110, 100)
    rows = [_q(g, b, m, 60, ln, a, bb) for b in ("pinnacle", "fanduel")
            for m, ln, a, bb in (("team_totals_away", 106.5, -115, -105), ("spreads_q1", -1.5, -105, -115),
                                 ("h2h_h1", None, -130, 110))]
    x = P.pairs(_vis(rows), same_number=True).set_index(["market", "side"])
    assert set(x.index) == {("team_totals_away", "over"), ("team_totals_away", "under"),
                            ("spreads_q1", "home"), ("spreads_q1", "away"),
                            ("h2h_h1", "home"), ("h2h_h1", "away")}
    assert x.loc[("team_totals_away", "under"), "price"] == -105
    assert x.loc[("spreads_q1", "home"), "line"] == -1.5
    assert x.loc[("h2h_h1", "away"), "price"] == 110
    assert set(x["book"]) == {"fanduel"}
    assert x["T"].iloc[0] == g["tip"] - pd.Timedelta(minutes=60)


def test_the_off_number_strength_is_the_gap_on_the_side_it_favours():
    games, q = _two_games()
    c = P.off_number_cand(_point(q, games, 120)).set_index(["market", "book", "side"])["strength"]
    # spreads: draftkings home -5.0 against Pinnacle's -5.5 favours home by half a point
    assert c[("spreads", "draftkings", "home")] == pytest.approx(0.5)
    assert c[("spreads", "draftkings", "away")] == pytest.approx(-0.5)
    assert c[("spreads", "fanduel", "home")] == 0.0                   # at Pinnacle's number
    # totals: fanduel's 222.5 against 220.5 favours the under by two
    assert c[("totals", "fanduel", "under")] == pytest.approx(2.0)
    assert c[("totals", "fanduel", "over")] == pytest.approx(-2.0)
    assert "h2h" not in c.index.get_level_values("market")
    assert "betmgm" not in c.index.get_level_values("book")


def test_off_number_offers_are_priced_around_pinnacles_centre():
    games, q = _two_games()
    c = P.off_number_cand(_point(q, games, 120)).set_index(["market", "book", "side"])
    at_pin = c.loc[("spreads", "fanduel", "home")]
    share = H.imp(-120) / (H.imp(-120) + H.imp(100))
    assert at_pin["p_win"] / (1 - at_pin["p_push"]) == pytest.approx(share, abs=2e-3)
    # half a point more for home (draftkings -5.0) turns a 5-point win from a loss into a push
    dk = c.loc[("spreads", "draftkings", "home")]
    assert dk["p_push"] > 0.0 and at_pin["p_push"] == 0.0
    assert 1 - dk["p_win"] - dk["p_push"] < 1 - at_pin["p_win"]
    tot = c.loc[("totals", "fanduel", "under")]
    assert tot["p_win"] > 0.5                                       # under 222.5 when the centre is 220.5


# ── whole cells, graded ─────────────────────────────────────────────────────

def test_both_rules_grade_their_bets_in_units(tmp_path, monkeypatch):
    games, q = _two_games()
    data = _data(games, q)
    pt = _point(q, games, 120)
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path))
    rows, pop = P.point_cells(data, "C", pt, P.FULL_MARKETS, None, None, H.CHOOSE, runs=2)
    assert len(rows) == 6 * 4 + 4 * 4                                # 24 same-number, 16 off-number
    s0 = _row(rows, "same_number", "spreads", "home", 0.0)
    assert (s0["n_choose"], s0["units_choose"]) == (1, pytest.approx(1.0))   # fanduel -5.5 covers
    assert _row(rows, "same_number", "spreads", "home", 0.02)["n_choose"] == 0
    o = _row(rows, "off_number", "spreads", "home", 0.5)
    assert (o["n_choose"], o["units_choose"]) == (1, pytest.approx(1.0))     # draftkings -5.0 covers
    assert _row(rows, "off_number", "spreads", "home", 1.0)["n_choose"] == 0
    u = _row(rows, "off_number", "totals", "under", 2.0)               # 203 under 222.5 wins
    assert (u["n_choose"], u["units_choose"]) == (1, pytest.approx(1.0))
    assert _row(rows, "off_number", "totals", "over", 0.5)["n_choose"] == 0
    # each rule's bets in its own folder
    assert {p.parent.name for p in tmp_path.rglob("bets_*.parquet")} == {"P2_same_number",
                                                                        "P2_off_number"}
    assert {r["axis_rule"] for r in rows} == {"same_number", "off_number"}


def _tt_games():
    g1, g2 = _game("G1", 0, 112, 101), _game("G2", 1, 99, 120)
    q = []
    for g in (g1, g2):
        for m, n in (("team_totals_home", 105.5), ("team_totals_away", 108.5)):
            q.append(_q(g, "pinnacle", m, 60, n, -110, -110))
            q.append(_q(g, "fanduel", m, 60, n, 100, -125))             # over at +100: EV 0
    return [g1, g2], q


def test_team_totals_are_one_cell_per_side_over_both_teams():
    games, q = _tt_games()
    data = _data(games, q)
    pt = _point(q, games, 60)
    rows, _ = P.point_cells(data, "D", pt, (P.TT_LABEL,), None, None, H.CHOOSE, runs=2)
    assert {r["market"] for r in rows} == {"team_totals"} and len(rows) == 2 * 4 + 2 * 4
    over = _row(rows, "same_number", "team_totals", "over", 0.0)
    # four bets at +100: G1 home 112 (W), G1 away 101 (L), G2 home 99 (L), G2 away 120 (W)
    assert over["n_choose"] == 4 and over["units_choose"] == pytest.approx(0.0)


# ── placebos ────────────────────────────────────────────────────────────────

def test_the_same_number_placebo_moves_pinnacles_share_within_a_date_only():
    games = [_game("A", 0, 1, 0), _game("B", 0, 1, 0), _game("C", 1, 1, 0)]
    gdf = pd.DataFrame(games)
    cand = pd.DataFrame([{"game_id": g, "market": "h2h", "side": s, "book": "fanduel",
                          "price": -110.0, "p_win": p if s == "home" else 1 - p}
                         for g, p in (("A", 0.6), ("B", 0.4), ("C", 0.7)) for s in ("home", "away")])
    swapped = False
    for r in range(20):
        pl = P.same_number_placebo(cand, gdf, r)
        home = pl[pl["side"] == "home"].set_index("game_id")["p_win"]
        away = pl[pl["side"] == "away"].set_index("game_id")["p_win"]
        assert (home + away).to_numpy() == pytest.approx(1.0)
        assert home["C"] == pytest.approx(0.7)                          # alone on its date
        assert sorted(home[["A", "B"]].round(6)) == [0.4, 0.6]
        assert (pl["price"] == cand["price"]).all()
        assert pl["ev"].to_numpy() == pytest.approx(pl["p_win"] * H.dec(-110) - 1)
        swapped |= home["A"] == pytest.approx(0.4)
    assert swapped


def test_the_off_number_placebo_permutes_the_gap_within_date_market_and_side():
    rows = []
    for d, day in (("2024-01-15", 0), ("2024-01-16", 1)):
        for i, s in enumerate((0.0, 0.5, 1.0, 2.0, -1.0)):
            for side, sgn in (("home", 1), ("away", -1)):
                rows.append({"game_id": f"{d}-{i}", "game_date": d, "market": "spreads", "side": side,
                             "book": "fanduel", "price": -110.0, "strength": sgn * s + day * 10})
    cand = pd.DataFrame(rows)
    moved = False
    for r in range(20):
        pl = P.off_number_placebo(cand, r)
        for key, grp in cand.groupby(["game_date", "market", "side"]):
            got = pl.set_index(["game_date", "market", "side"]).loc[key, "strength"]
            assert sorted(got) == sorted(grp["strength"])
        assert (pl["price"] == cand["price"]).all()
        moved |= not np.allclose(pl["strength"], cand["strength"])
    assert moved


# ── pricing ─────────────────────────────────────────────────────────────────

def test_the_proxy_reads_the_period_share_of_pinnacles_full_game_close():
    g = pd.DataFrame([_game("G", 0, 115, 105)])
    per = pd.DataFrame([{"game_id": "G", "period": i + 1, "home_points": h, "away_points": a}
                        for i, (h, a) in enumerate(((30, 25), (30, 25), (25, 30), (30, 25)))])
    gp = H.with_periods(g, periods=per)
    close = pd.DataFrame([{"game_id": "G", "season": 2024, "market": "spreads", "close_line": -6.0},
                          {"game_id": "G", "season": 2024, "market": "totals", "close_line": 220.0}])
    r = P.proxy_resid(close, gp).set_index("market")["resid"]
    # half: +10 margin around 0.5 x 6; 110 around 110. Quarter: +5 around 1.5; 55 around 55.
    assert r["spreads_h1"] == pytest.approx(7.0) and r["totals_h1"] == pytest.approx(0.0)
    assert r["spreads_q1"] == pytest.approx(3.5) and r["totals_q1"] == pytest.approx(0.0)
    # team totals: home 115 around (220 + 6) / 2 = 113, away 105 around 107
    assert sorted(r["team_totals_home"].tolist()) == pytest.approx([-2.0, 2.0])
    assert sorted(r["team_totals_away"].tolist()) == pytest.approx([-2.0, 2.0])


def _pricing_world(n=60, seed=1):
    """Seasons 2024 (no derivative price), 2025, 2026; each game has periods,
    a full-game Pinnacle close and a first-half Pinnacle number."""
    rng = np.random.default_rng(seed)
    games, per, close, dclose = [], [], [], []
    for s in (2024, 2025, 2026):
        for i in range(n):
            gid = f"{s}-{i}"
            hq, aq = rng.integers(20, 36, 4), rng.integers(20, 36, 4)
            games.append({"game_id": gid, "season": s, "home_score": float(hq.sum()),
                          "away_score": float(aq.sum())})
            per += [{"game_id": gid, "period": p + 1, "home_points": int(hq[p]),
                     "away_points": int(aq[p])} for p in range(4)]
            close += [{"game_id": gid, "season": s, "market": "spreads", "close_line": -2.0},
                      {"game_id": gid, "season": s, "market": "totals", "close_line": 224.0}]
            if s > 2024:
                dclose.append({"game_id": gid, "season": s, "market": "spreads_h1", "close_line": -1.0,
                               "close_fa": 0.5})
    gp = H.with_periods(pd.DataFrame(games), periods=pd.DataFrame(per))
    return gp, pd.DataFrame(close), pd.DataFrame(dclose)


def test_derivative_pricing_is_walk_forward_and_never_reads_its_own_season():
    gp, close, dclose = _pricing_world()
    sig, src = P.derivative_pricing(dclose, gp, close, (2025, 2026), min_games=50)
    assert src[(2025, "spreads_h1")] == "proxy"                  # no earlier derivative season
    assert src[(2026, "spreads_h1")] == "derivative"             # 2025's purchases price 2026
    assert sig[(2026, "spreads_h1")].n == 60 and sig[(2025, "spreads_h1")].n == 60
    assert src[(2025, "team_totals_home")] == "proxy" and (2026, "totals_h1") in sig
    # a season's own results never move its own pricing
    gp2 = gp.copy()
    own = gp2["season"] == 2026
    gp2.loc[own, ["home_h1", "home_score"]] += 40.0
    sig2, _ = P.derivative_pricing(dclose, gp2, close, (2025, 2026), min_games=50)
    for m in ("spreads_h1", "totals_h1", "team_totals_home"):
        assert sig2[(2026, m)].sd == pytest.approx(sig[(2026, m)].sd)
        assert sig2[(2025, m)].sd == pytest.approx(sig[(2025, m)].sd)
    # too few earlier games: no pricing at all rather than the season's own
    sig3, src3 = P.derivative_pricing(dclose, gp, close, (2025,), min_games=61)
    assert (2025, "spreads_h1") not in sig3 and not src3


# ── loading guards ──────────────────────────────────────────────────────────

def test_a_season_bought_part_way_is_named_and_refused(tmp_path):
    games = pd.DataFrame([{"game_id": f"G{s}{i}", "season": s, "game_date": f"{s - 1}-12-0{i + 1}",
                           "tip": pd.Timestamp(f"{s - 1}-12-0{i + 1}T00:30:00Z")}
                          for s in (2025, 2026) for i in range(2)])
    rows = [{"game_id": gid, "market": "totals_h1", "bookmaker": "fanduel", "snapshot_type": "open",
             "snapshot_at": str(t - pd.Timedelta(minutes=60)), "source": H.PER_EVENT_SOURCE,
             "home_price": None, "away_price": None, "spread_home": None, "total_line": 110.5,
             "over_price": -110.0, "under_price": -110.0}
            for gid, t in zip(games["game_id"], games["tip"]) if gid != "G20251"]
    pd.DataFrame(rows).to_parquet(tmp_path / "nba_odds.parquet")
    held = P.derivative_seasons(games, cache=tmp_path)
    assert held == [2025, 2026]                                   # 2025 half bought is still named
    with pytest.raises(RuntimeError, match="too few games"):
        H.load_per_event(games, cache=tmp_path, require_seasons=held)


def _no_real_load(monkeypatch):
    """A broken guard must fail the test, never start a graded run."""
    def stop(*a, **k):
        raise RuntimeError("reached the graded load")
    monkeypatch.setattr(P, "load_full", stop)


def test_full_refuses_without_the_owners_go(monkeypatch, tmp_path):
    _no_real_load(monkeypatch)
    monkeypatch.delenv("NBA_GAME2_GO", raising=False)
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(tmp_path))
    with pytest.raises(SystemExit, match="NBA_GAME2_GO"):
        P.run("full")


def test_full_refuses_an_unnamed_results_folder(monkeypatch):
    # the default folder holds the second search's 422 cells; the verdict reads every cells_*.parquet
    _no_real_load(monkeypatch)
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.delenv("NBA_GAME2_RESULTS", raising=False)
    with pytest.raises(SystemExit, match="NBA_GAME2_RESULTS"):
        P.run("full")
    P.results_guard(False, env={})                         # the smoke may use the default


# ── the derivative cells end to end on synthetic games ──────────────────────

def test_the_96_derivative_cells_run_on_synthetic_games():
    g, fc, pe = P.synthetic_world(seed=2, per_season=80)
    rows, pop, src = P.derivative_cells(g, pe, fc, runs=2, min_games=50)
    df = pd.DataFrame(rows)
    assert len(df) == 96
    assert set(df["point"]) == {"D"} and set(df["choose_seasons"]) == {"2025"}
    assert src["2025 spreads_h1"] == "proxy" and src["2026 spreads_h1"] == "derivative"
    assert df["n_choose"].sum() > 0 and df["n_confirm"].sum() > 0
    assert set(df["market"]) == set(P.DERIV_LABELS)
    # betrivers' first-half rung 3 points off the others is a ladder; its team-total ladder is read once
    pt = P.point_frames(P.main_rungs(pe), P.rungs_at_pinnacle(pe), H.per_event_times(pe, "D"), {})
    br = pt.vis_main[pt.vis_main["book"] == "betrivers"]
    assert "spreads_h1" not in set(br["market"])
    assert not br.duplicated(["game_id", "market"]).any() and "team_totals_home" in set(br["market"])


def test_the_shared_main_number_view_keeps_one_number_per_book_and_no_ladder():
    """P1 and P3 import this (sections 8.1 and 8.3, 2026-10-18)."""
    g = _game("G", 0, 110, 100)
    q = pd.DataFrame(list(reversed(_ladder())) + [
        _q(g, "pinnacle", "team_totals_home", 60, 111.5, -110, -110),
        _q(g, "hardrockbet", "spreads_h1", 60, 1.5, -165, 130),
        _q(g, "fanduel", "spreads_h1", 60, -2.0, -110, -110),
        _q(g, "draftkings", "spreads_h1", 60, -2.0, -110, -110)])
    times = pd.DataFrame({"game_id": ["G"], "T": [g["tip"] - pd.Timedelta(minutes=60)]})
    v = P.visible_numbers(q, times)
    assert not v.duplicated(["game_id", "market", "book"]).any()
    got = v.set_index(["market", "book"])["line"].to_dict()
    assert got[("team_totals_home", "betrivers")] == 111.5
    assert ("spreads_h1", "hardrockbet") not in got


def test_full_refuses_without_a_bets_folder(monkeypatch, tmp_path):
    _no_real_load(monkeypatch)
    monkeypatch.setenv("NBA_GAME2_GO", "1")
    monkeypatch.setenv("NBA_GAME2_RESULTS", str(tmp_path))
    monkeypatch.delenv("NBA_GAME2_BETS", raising=False)
    with pytest.raises(SystemExit, match="NBA_GAME2_BETS"):
        P.run("full")

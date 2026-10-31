"""The off-line / soft-consensus / anchored prop search's lab (docs/nba_search_propoffline.md): each rule
the doc registers, on hand-built rows and on the invented world. Each test here was run once with its rule
broken and watched failing (the mutation list is in the search's report)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import nba_game2_luck as L
from scripts import nba_game2_verdict as V
from scripts import nba_game_harness as H
from scripts import nba_s_propoffline as S


def quote(book, line, over, under, prop=1, season=2024, date="2024-01-02", market="player_points", **extra):
    od, ud = float(H.dec(over)), float(H.dec(under))
    return {"game_id": f"G{prop}", "player_id": f"P{prop}", "market": market, "prop_id": prop, "season": season,
            "game_date": date, "bookmaker": book, "line": float(line), "over_price": float(over),
            "under_price": float(under), "od": od, "ud": ud, "T": pd.Timestamp("2024-01-02 23:00", tz="UTC"),
            "p": (1 / od) / (1 / od + 1 / ud), "player_name": f"N{prop}", "lead_min": 54.4,
            "snapshot_at": "2024-01-02T23:00:00Z", **extra}


class FlatTable:
    """A stand-in count table: the mean is the number; P(over L) falls by 0.04 a point from 0.5 at the mean."""

    def mu_from(self, line, p):
        return np.asarray(line, float) + (np.asarray(p, float) - 0.5) / 0.04

    def p_over(self, line, mu):
        return 0.5 + 0.04 * (np.asarray(mu, float) - np.asarray(line, float))


TABS = {("player_points", 2024): FlatTable()}


@pytest.fixture
def fast_boot(monkeypatch):
    """The plumbing tests walk every group through H.run_cells, and 4,000 resamples per cell are most of their
    time. No test here reads an interval's width, so 200 will do."""
    monkeypatch.setattr(H.boot, "__defaults__", (200, H.SEED))


# ── registered shape ────────────────────────────────────────────────────────

def test_the_registered_cells_are_36():
    assert len(S.registered_cells()) == S.EXPECTED_CELLS == 36


def test_placebo_is_200_runs_seeds_1_to_200():
    assert S.PLACEBO_SEEDS == tuple(range(1, 201))


def test_the_synthetic_world_holds_every_family():
    # a check that claims to cover a family has to have that family's offers in its data
    groups, _, _, _ = S.world_groups(S.synthetic_world())
    held = {g.family for g in groups if len(g.cand)}
    assert all(np.isfinite(g.cand["ev"]).all() for g in groups)
    assert {S.FAMILY_OL, S.FAMILY_CS, S.FAMILY_AN, S.CONTROL_OL, S.CONTROL_AN, S.CONTROL_SAME} <= held
    refs = {(g.family, g.ref) for g in groups if len(g.cand)}
    assert (S.FAMILY_AN, "pinnacle") in refs and (S.FAMILY_AN, "consensus") in refs


# ── impossible numbers ──────────────────────────────────────────────────────

def _q(**over):
    base = {"usable": True, "x": 20.0, "lead_min": 54.4, "coherent": True, "over_price": -110.0, "under_price": -110.0,
            "market": "player_points", "line": 20.5, "player_id": "P", "od": 1.909, "ud": 1.909}
    base.update(over)
    return base


def test_eligible_removes_each_impossible_number():
    rows = pd.DataFrame([_q(), _q(usable=False), _q(x=np.nan), _q(lead_min=30.0), _q(lead_min=80.0), _q(coherent=False),
                         _q(under_price=-300000.0), _q(over_price=12000.0), _q(line=113.5)])
    r, notes = S.eligible(rows, {"player_points": 73.0})
    assert len(r) == 1 and r["line"].iloc[0] == 20.5
    assert notes["removed_price_limit"] == 2 and notes["removed_line_ceiling"] == 1


def test_box_ceiling_reads_the_sum_for_combined_markets():
    log = pd.DataFrame({"points": [30.0, 10.0], "rebounds": [5.0, 20.0], "assists": [5.0, 9.0], "fg3_made": 1.0,
                        "blocks": 0.0, "steals": 0.0, "turnovers": 0.0})
    c = S.box_ceilings(log)
    assert c["player_points"] == 30.0 and c["player_points_rebounds"] == 35.0
    assert c["player_points_rebounds_assists"] == 40.0 and c["player_double_double"] == 1.0


# ── one proposition is one game to the harness ──────────────────────────────

def test_the_harness_settles_a_proposition_on_its_stat():
    props = pd.DataFrame({"prop_id": [0, 1], "season": 2024, "game_date": "2024-01-02", "T": pd.Timestamp("2024-01-02", tz="UTC")})
    games = S.games_table(props, np.array([23.0, 20.0]))
    bets = pd.DataFrame({"game_id": [0, 0, 1, 1], "market": S.HMARKET, "side": ["over", "under", "over", "under"],
                         "line": 22.5, "price": -110.0, "season": 2024, "game_date": "2024-01-02"})
    assert H.grade(bets, games)["result"].tolist() == ["W", "L", "L", "W"]


def test_the_timed_games_table_holds_no_real_stat():
    props = pd.DataFrame({"prop_id": [0, 1], "season": 2024, "game_date": "2024-01-02", "T": pd.Timestamp("2024-01-02", tz="UTC")})
    g = S.games_table(props, None)
    assert (g["home_score"] == 0).all() and (g["away_score"] == 0).all()


def test_offers_are_attached_by_position_not_by_label():
    q = pd.DataFrame([quote("draftkings", 20.5, -110, -110, prop=1), quote("fanduel", 21.5, -110, -110, prop=2)])
    q.index = [7, 3]                                    # a filtered frame's own index
    out = S.long_offers(q, np.array([0.60, 0.40]))
    over = out[out["side"] == "over"].set_index("game_id")
    assert over.loc[1, "p_win"] == 0.60 and over.loc[2, "p_win"] == 0.40
    under = out[out["side"] == "under"].set_index("game_id")
    assert under.loc[1, "p_win"] == pytest.approx(0.40)


def test_fill_inputs_reads_by_position_and_never_invents_a_report():
    tr = pd.DataFrame({"tm_o_min": [10.0, 30.0], "rest": [1.0, 3.0], "pace_l": [np.nan, np.nan]}, index=[5, 9])
    rows = pd.DataFrame({"tm_o_min": [np.nan, 4.0], "rest": [np.nan, 7.0], "pace_l": [np.nan, 99.0]}, index=[100, 2])
    x = S.fill_inputs(tr, rows, ["tm_o_min", "rest", "pace_l"])
    assert x[:, 0].tolist() == [0.0, 4.0]               # a report input with no report reads 0
    assert x[:, 1].tolist() == [2.0, 7.0]               # anything else reads the training mean
    assert x[:, 2].tolist() == [0.0, 99.0]              # and an input never seen in training cannot stay missing


# ── OL ──────────────────────────────────────────────────────────────────────

def _ol_rows():
    return pd.DataFrame([
        quote("pinnacle", 20.5, -110, -110, prop=1),
        quote("draftkings", 20.5, -105, -115, prop=1),       # on Pinnacle's line: not an off-line offer
        quote("betrivers", 21.5, -110, -110, prop=1),        # above: under is the side
        quote("fanduel", 19.5, -110, -110, prop=1),          # below: over is the side
    ])


def test_gap_side_is_under_above_and_over_below():
    side = np.array(["under", "over", "under", "over"], dtype=object)
    gap = np.array([1.0, 1.0, -1.0, -1.0])
    assert S.gap_side(side, gap).tolist() == [True, False, False, True]


def test_off_line_candidates_are_only_the_side_the_gap_favours():
    uni, _ = S.offline_offers(S.pinnacle_quotes(_ol_rows(), TABS))
    assert set(uni["book"]) == {"betrivers", "fanduel"}          # the on-line book is out
    cand = uni[uni["cand"]].set_index("book")
    assert cand.loc["betrivers", "side"] == "under" and cand.loc["fanduel", "side"] == "over"


def test_off_line_fair_is_read_from_pinnacle_at_the_books_line():
    uni, _ = S.offline_offers(S.pinnacle_quotes(_ol_rows(), TABS))
    u = uni[(uni["book"] == "betrivers") & (uni["side"] == "under")].iloc[0]
    # Pinnacle no-vig 0.5 at 20.5: mean 20.5; over 21.5 is 0.46; under 0.54; -110 pays 1.909
    assert u["p_win"] == pytest.approx(0.54)
    assert u["ev"] == pytest.approx(0.54 * float(H.dec(-110)) - 1)


def test_the_book_being_bet_never_sets_pinnacles_reference():
    # moving the off-line book's own price must not move its fair chance
    a = _ol_rows()
    b = pd.DataFrame([quote("pinnacle", 20.5, -110, -110, prop=1), quote("draftkings", 20.5, -105, -115, prop=1),
                      quote("betrivers", 21.5, 150, -180, prop=1), quote("fanduel", 19.5, -110, -110, prop=1)])
    fa = S.offline_offers(S.pinnacle_quotes(a, TABS))[0].query("book == 'betrivers' and side == 'under'")["p_win"].iloc[0]
    fb = S.offline_offers(S.pinnacle_quotes(b, TABS))[0].query("book == 'betrivers' and side == 'under'")["p_win"].iloc[0]
    assert fa == fb


# ── CS ──────────────────────────────────────────────────────────────────────

def test_consensus_leaves_out_the_book_being_bet():
    r = pd.DataFrame([quote("draftkings", 20.5, 140, -160), quote("fanduel", 20.5, -110, -110),
                      quote("betmgm", 20.5, -120, 100), quote("bovada", 20.5, -130, 110)])
    c = S.consensus_offers(r)
    dk = c[(c["book"] == "draftkings") & (c["side"] == "over")].iloc[0]
    others = r.loc[r["bookmaker"] != "draftkings", "p"]
    assert dk["p_win"] == pytest.approx(float(others.median()))   # the others' median, not with its own price in it
    assert dk["p_win"] != pytest.approx(float(r["p"].median()))


def test_consensus_needs_three_other_books_at_the_same_line():
    r = pd.DataFrame([quote("draftkings", 20.5, -110, -110), quote("fanduel", 20.5, -110, -110),
                      quote("betmgm", 20.5, -110, -110), quote("bovada", 21.5, -110, -110)])
    assert S.consensus_offers(r).empty                           # two others at 20.5; one at 21.5


def test_consensus_skips_a_proposition_pinnacle_quotes():
    r = pd.DataFrame([quote("draftkings", 20.5, -110, -110), quote("fanduel", 20.5, -110, -110),
                      quote("betmgm", 20.5, -110, -110), quote("bovada", 20.5, -110, -110),
                      quote("pinnacle", 20.5, -110, -110)])
    assert S.consensus_offers(r).empty


# ── the placebos ────────────────────────────────────────────────────────────

def test_a_reading_stays_inside_its_date_and_market():
    groups = np.array([0, 0, 0, 1, 1, 2, 2, 2, 2])
    for seed in range(1, 6):
        perm = S.permute_within(groups, np.random.default_rng(seed))
        assert (groups[perm] == groups).all() and sorted(perm.tolist()) == list(range(len(groups)))


def _reading_rows():
    rows = []
    # prop 1: its book sits above Pinnacle, so the real rule bets under. prop 2: below, so over.
    for prop, book, line, cand_side, ev_u, ev_o in ((1, "betrivers", 21.5, "under", 0.03, -0.10),
                                                    (2, "fanduel", 19.5, "over", -0.09, 0.05)):
        for side, ev in (("under", ev_u), ("over", ev_o)):
            rows.append({"game_id": prop, "market": S.HMARKET, "side": side, "book": book, "price": -110.0, "line": line,
                         "season": 2024, "game_date": "2024-01-02", "T": pd.Timestamp("2024-01-02"), "prop_market": "player_points",
                         "ev": ev, "cand": side == cand_side})
    return pd.DataFrame(rows)


def test_the_identity_returns_the_real_bets():
    uni = _reading_rows()
    rd = S.Reading(uni, S.EV_LOWEST)
    for side in ("under", "over"):
        real = uni[uni["cand"] & (uni["side"] == side)]
        got = rd.frame(side, None)
        assert got["game_id"].tolist() == real["game_id"].tolist() and got["ev"].tolist() == pytest.approx(real["ev"].tolist())


def test_a_donor_sends_a_proposition_to_the_side_its_own_rule_did_not_bet():
    uni = _reading_rows()
    rd = S.Reading(uni, S.EV_LOWEST)
    rd.perm = lambda seed: np.array([1, 0])             # the two propositions swap readings
    under = rd.frame("under", 7)
    # prop 2's own rule bets over; with prop 1's reading it is bet under at its own line, carrying 0.03
    assert under["game_id"].tolist() == [2] and under["ev"].iloc[0] == pytest.approx(0.03)
    assert under["line"].iloc[0] == 19.5 and under["book"].iloc[0] == "fanduel"
    over = rd.frame("over", 7)
    assert over["game_id"].tolist() == [1] and over["ev"].iloc[0] == pytest.approx(0.05)


def test_the_best_priced_offer_stays_best_under_a_donor():
    rows = _reading_rows()
    extra = rows[(rows["game_id"] == 2) & (rows["side"] == "over")].assign(book="draftkings", ev=0.02)   # 0.03 short of the best
    uni = pd.concat([rows, extra], ignore_index=True)
    rd = S.Reading(uni, -0.5)
    rd.perm = lambda seed: np.array([1, 0])
    # prop 1 has no second book, so swap the other way: prop 2 keeps its own offers and takes prop 1's over reading (none)
    assert rd.frame("over", 7)["game_id"].tolist() == [1]
    rd2 = S.Reading(uni, -0.5)
    got = rd2.frame("over", None).set_index("book")
    assert got.loc["fanduel", "ev"] == pytest.approx(0.05) and got.loc["draftkings", "ev"] == pytest.approx(0.02)


def test_an_offer_below_the_price_floor_is_never_read():
    rows = _reading_rows()
    rows.loc[rows["book"] == "betrivers", "price"] = -250.0
    rd = S.Reading(rows, S.EV_LOWEST)
    assert rd.frame("under", None).empty


def test_the_move_goes_to_another_proposition_and_is_re_priced_on_its_own_offset():
    table = pd.DataFrame({"offset": [0.0, 1.0], "game_date": "2024-01-02", "market": "player_points", "ref": "pinnacle"})
    rows = []
    for t in (0, 1):
        for side, p in (("over", -110.0), ("under", -110.0)):
            rows.append({"game_id": t, "market": S.HMARKET, "side": side, "book": "draftkings", "price": p, "line": 20.5,
                         "season": 2025, "game_date": "2024-01-02", "T": pd.Timestamp("2024-01-02"), "tidx": t})
    ms = S.MoveShuffle(pd.DataFrame(rows), table, np.array([0.5, -0.2]), -1.0)
    # rows run over, under, over, under: positions 0 and 2 are each proposition's over
    p, ev = ms.priced(None)
    assert p[0] == pytest.approx(float(S.expit(0.5))) and p[2] == pytest.approx(float(S.expit(1.0 - 0.2)))
    assert p[1] == pytest.approx(1 - float(S.expit(0.5)))
    assert ev[0] == pytest.approx(p[0] * float(H.dec(-110)) - 1)
    ms.perm = lambda seed: np.array([1, 0])
    p, _ = ms.priced(3)
    assert p[0] == pytest.approx(float(S.expit(0.0 - 0.2))) and p[2] == pytest.approx(float(S.expit(1.0 + 0.5)))
    # the frame's offers are the proposition's own, whatever move it reads
    assert set(ms.frame("over", 3)["line"]) == {20.5}


def test_the_move_shuffle_stays_inside_date_market_and_reference():
    table = pd.DataFrame({"offset": 0.0, "game_date": ["d1", "d1", "d1", "d2"], "market": ["m", "m", "n", "m"],
                          "ref": ["pinnacle", "consensus", "pinnacle", "pinnacle"]})
    rows = [{"game_id": t, "market": S.HMARKET, "side": "over", "book": "draftkings", "price": -110.0, "line": 20.5,
             "season": 2025, "game_date": "d", "T": pd.Timestamp("2024-01-02"), "tidx": t} for t in range(4)]
    ms = S.MoveShuffle(pd.DataFrame(rows), table, np.array([0.1, 0.2, 0.3, 0.4]), -1.0)
    assert len(set(ms.groups.tolist())) == 4            # nothing here shares all three, so nothing can move
    assert ms.perm(1).tolist() == [0, 1, 2, 3]


def _real_and_placebo(world, family, side, ref):
    groups, props, stat, _ = S.world_groups(world)
    games = S.games_table(props, stat)
    g = next(x for x in groups if x.family == family and x.side == side and x.ref == ref)
    cut = g.cuts[0]
    real = H.roi(H.grade(H.choose(g.cand, cut, sides=[side]), games))
    pl = [H.roi(H.grade(H.choose(g.placebo.frame(side, s), cut, sides=[side]), games)) for s in range(1, 41)]
    return real, np.nanpercentile(pl, 95), g, cut


def test_a_real_edge_beats_the_placebo_and_a_flat_world_does_not():
    real, p95, g, cut = _real_and_placebo(S.synthetic_world(seed=2, edge=True), S.FAMILY_OL, "under", "pinnacle")
    assert real > p95
    real0, p950, _, _ = _real_and_placebo(S.synthetic_world(seed=2, edge=False, market_sd=0.0), S.FAMILY_OL, "under", "pinnacle")
    assert real0 < p950 and real0 < real
    # the null is a null: most of a run's bets are not the real ones
    bets = H.choose(g.cand, cut, sides=["under"])
    run = H.choose(g.placebo.frame("under", 1), cut, sides=["under"])
    keys = set(zip(bets["game_id"], bets["book"]))
    assert np.mean([(a, b) not in keys for a, b in zip(run["game_id"], run["book"])]) > 0.4


def test_a_consensus_edge_beats_its_placebo():
    # on three propositions in ten one book strays and the others hold the truth: the rule has a real edge there,
    # and a placebo that hands its readings to the propositions with no stray has none. Built by hand: the invented
    # world clips its prices, which pays any bet at the extremes whatever its reading says.
    rng = np.random.default_rng(5)
    n = 6000
    rows, stat = [], []
    for prop in range(n):
        p = rng.uniform(0.40, 0.60)
        stat.append(30.0 if rng.random() < p else 10.0)
        stray = float(rng.choice([-0.12, 0.12])) if rng.random() < 0.3 else 0.0
        for k, bk in enumerate(("draftkings", "fanduel", "betmgm", "betrivers", "fanatics")):
            pf = p + rng.normal(0, 0.005) + (stray if k == 0 else 0.0)
            rows.append(quote(bk, 20.5, S._american(pf * 1.035), S._american((1 - pf) * 1.035), prop=prop,
                              date=f"2024-01-{1 + prop % 25:02d}"))
    uni = S.consensus_offers(pd.DataFrame(rows))
    rd = S.Reading(uni, S.EV_LOWEST)
    props = pd.DataFrame({"prop_id": np.arange(n), "season": 2024, "game_date": "2024-01-02", "T": pd.Timestamp("2024-01-02", tz="UTC")})
    games = S.games_table(props, np.array(stat))
    real = H.roi(H.grade(H.choose(uni[uni["side"] == "under"], 0.0, sides=["under"]), games))
    pl = [H.roi(H.grade(H.choose(rd.frame("under", s), 0.0, sides=["under"]), games)) for s in range(1, 41)]
    assert real > np.percentile(pl, 95)


def test_a_better_projection_beats_the_anchored_placebo():
    # the projection knows the player's night and the market does not: only the real move carries that. Over,
    # because this world's market leans high and an under earns from that lean with or without a move (a shuffled
    # move keeps the offset, as it should, so the under's contrast is thin at some seeds here)
    real, p95, _, _ = _real_and_placebo(S.synthetic_world(seed=2), S.FAMILY_AN, "over", "pinnacle")
    assert real > p95


def test_low_share_is_said_in_words():
    pl = pd.DataFrame({"family": ["AN", "OL"], "ref": ["pinnacle", "pinnacle"], "side": ["under", "under"], "cut": [0.01, 0.0],
                       "share_differ": [0.37, 0.77]})
    note = S.low_share_note(pl)
    assert note.startswith("LOW") and "AN pinnacle under EV >= 0.01 (0.37)" in note and "OL" not in note.split("(0.37)")[1]
    assert not S.low_share_note(pl.iloc[[1]]).startswith("LOW")


# ── AN ──────────────────────────────────────────────────────────────────────

def _model_table(n=800):
    rng = np.random.default_rng(3)
    t = pd.DataFrame({"prop_id": np.arange(n), "market": "player_points", "ref": "pinnacle",
                      "season": np.repeat([2024, 2025], n // 2), "Lref": 20.5, "offset": rng.normal(0, 0.4, n),
                      "disagree": rng.normal(0, 0.5, n), "tm_o_min": rng.normal(10, 5, n)})
    stat = np.where(rng.random(n) < S.expit(t["offset"] + 0.8 * t["disagree"]), 30.0, 10.0)
    return t, stat


def test_the_fit_never_reads_the_graded_season():
    t, stat = _model_table()
    a, _ = S.fit_moves(t, stat, inputs=["disagree", "tm_o_min"], graded=(2025,))
    other = stat.copy()
    other[t["season"] == 2025] = 30.0 - other[t["season"] == 2025] + 10.0     # every graded result flipped
    b, _ = S.fit_moves(t, other, inputs=["disagree", "tm_o_min"], graded=(2025,))
    assert np.nanmax(np.abs(a - b)) == 0.0
    # and the earlier season is read
    other = stat.copy()
    other[t["season"] == 2024] = 40.0 - other[t["season"] == 2024]
    c, _ = S.fit_moves(t, other, inputs=["disagree", "tm_o_min"], graded=(2025,))
    assert np.nanmax(np.abs(a - c)) > 0.01


def test_a_season_is_never_given_a_move_from_its_own_fit():
    t, stat = _model_table()
    m, notes = S.fit_moves(t, stat, inputs=["disagree"], graded=(2024, 2025))
    assert np.isnan(m[(t["season"] == 2024).to_numpy()]).all()     # 2023-24 has nothing before it
    assert np.isfinite(m[(t["season"] == 2025).to_numpy()]).all()
    assert [n["fitted"] for n in notes] == [False, True]


def test_a_model_needs_300_training_rows():
    t, stat = _model_table(n=500)
    m, notes = S.fit_moves(t, stat, inputs=["disagree"], graded=(2025,))
    assert np.isnan(m).all() and notes[0]["fitted"] is False


def test_the_offset_is_not_penalised():
    # the penalty can shrink the inputs to nothing; the market's number must remain in the price
    t, stat = _model_table()
    lean, _ = S.fit_moves(t, stat, inputs=(), graded=(2025,))
    v = lean[np.isfinite(lean)]
    assert v.max() - v.min() < 1e-9                     # with no inputs the move is one number: the intercept


def test_disagreement_is_the_projection_against_the_offset_at_the_reference_line():
    ref = pd.DataFrame({"prop_id": [0], "Lref": [20.5], "p_ref": [0.6], "ref": ["pinnacle"]})
    props = pd.DataFrame({"prop_id": [0], "game_id": ["g"], "player_id": ["p"], "market": ["player_points"], "season": [2025],
                          "game_date": ["2024-12-01"]})
    preds = pd.DataFrame({"game_id": ["g"], "player_id": ["p"], "season": [2025], "status": ["Listed none"], "is_home": [1.0],
                          **{f"mu_{s}": [1.0] for s in S.nb.BASE_STATS if s != "points"}, "mu_points": [20.5]})
    t = S.anchored_table(ref, props, preds, {("player_points", 2025): 0.0})
    offset = float(S.logit(0.6))
    want = float(S.logit(S.nb.p_over(np.array([20.5]), np.array([20.5]), 0.0))[0]) - offset
    assert t["disagree"].iloc[0] == pytest.approx(want) and t["offset"].iloc[0] == pytest.approx(offset)
    # a combined market sums its base stats' means
    assert S.market_mean(preds, "player_points_assists")[0] == pytest.approx(21.5)


def test_a_player_listed_out_has_no_model_number():
    ref = pd.DataFrame({"prop_id": [0], "Lref": [20.5], "p_ref": [0.5], "ref": ["pinnacle"]})
    props = pd.DataFrame({"prop_id": [0], "game_id": ["g"], "player_id": ["p"], "market": ["player_points"], "season": [2025],
                          "game_date": ["2024-12-01"]})
    preds = pd.DataFrame({"game_id": ["g"], "player_id": ["p"], "season": [2025], "status": ["Out"], "is_home": [1.0],
                          **{f"mu_{s}": [1.0] for s in S.nb.BASE_STATS}})
    assert S.anchored_table(ref, props, preds, {("player_points", 2025): 0.0}).empty


def test_the_anchored_model_bets_only_at_the_reference_line():
    r = pd.DataFrame([quote("draftkings", 20.5, -110, -110, prop=0, season=2025), quote("fanduel", 21.5, -110, -110, prop=0, season=2025),
                      quote("bovada", 20.5, -110, -110, prop=0, season=2025)])
    table = pd.DataFrame({"prop_id": [0], "Lref": [20.5], "p_ref": [0.5]})
    o = S.anchored_offers(r, table)
    assert set(o["book"]) == {"draftkings"}


def test_consensus_reference_needs_three_deciding_books_and_pinnacle_comes_first():
    # prop 1 has Pinnacle AND three deciding books at another line: it still has one reference, Pinnacle's
    r = pd.DataFrame([quote("pinnacle", 20.5, -110, -110, prop=1), quote("draftkings", 21.5, -110, -110, prop=1),
                      quote("fanduel", 21.5, -110, -110, prop=1), quote("betmgm", 21.5, -110, -110, prop=1),
                      quote("draftkings", 30.5, -130, 110, prop=2), quote("fanduel", 30.5, -110, -110, prop=2),
                      quote("betmgm", 30.5, -110, -110, prop=2), quote("draftkings", 40.5, -110, -110, prop=3),
                      quote("fanduel", 40.5, -110, -110, prop=3)])
    t = S.references(r)
    assert (t["prop_id"] == 1).sum() == 1
    t = t.set_index("prop_id")
    assert t.loc[1, "ref"] == "pinnacle" and t.loc[1, "Lref"] == 20.5
    assert t.loc[2, "ref"] == "consensus" and t.loc[2, "Lref"] == 30.5 and t.loc[2, "p_ref"] == pytest.approx(0.5)
    assert 3 not in t.index


def test_the_card_overlap_uses_earlier_seasons_maps_and_leaves_out_what_the_rule_holds():
    rows, pr = [], []
    rng = np.random.default_rng(4)
    stat = []
    for i in range(400):
        season = 2024 if i < 200 else 2025
        rows.append(quote("draftkings", 5.5, -110, -110, prop=i, season=season, market="player_rebounds"))
        pr.append({"game_id": f"G{i}", "player_id": f"P{i}", "season": season, "status": "Listed none", "played": True,
                   **{f"mu_{s}": 1.0 for s in S.nb.BASE_STATS}, "mu_rebounds": 2.0 + 0.16 * (i % 50)})
        stat.append(float(rng.poisson(2.0 + 0.16 * (i % 50))))
    r = pd.DataFrame(rows)
    props = r[["prop_id", "game_id", "player_id", "market", "season"]].reset_index(drop=True)
    widths = {("player_rebounds", 2024): 0.05, ("player_rebounds", 2025): 0.05}
    stat = np.array(stat)
    held = S.card_propositions(r, props, pd.DataFrame(pr), widths, stat, set())
    assert held and all(k >= 200 for k in held)         # 2023-24 has no earlier map, so nothing there is held
    some = next(iter(held))
    assert some not in S.card_propositions(r, props, pd.DataFrame(pr), widths, stat, {some})
    # season 2025's map reads 2024's results and never its own
    mine = stat.copy()
    mine[200:] = 20.0 - mine[200:]
    assert S.card_propositions(r, props, pd.DataFrame(pr), widths, mine, set()) == held
    earlier = stat.copy()
    earlier[:200] = 20.0 - earlier[:200]
    assert S.card_propositions(r, props, pd.DataFrame(pr), widths, earlier, set()) != held


# ── when a report counts as known (dated line of the doc) ───────────────────

class _Stop(Exception):
    """Raised where a test has seen what it came for: the frame's models are never fitted."""


def _tip(k: int) -> pd.Timestamp:
    return pd.Timestamp("2024-11-01 00:00", tz="UTC") + pd.Timedelta(days=k)


REPORTED = 14                                           # games with no report before this one: the ten-game rule is met
SNAPSHOT_LEAD = 55                                      # not the 60 a game with no prop snapshot falls back on


def _before(k: int, minutes: int) -> pd.Timestamp:
    """`minutes` before game k's decision, its prop snapshot."""
    return _tip(k) - pd.Timedelta(minutes=SNAPSHOT_LEAD + minutes)


def _tiny_raw() -> dict:
    """A small cache in the stored tables' shape: LAL at GSW every day, five players a side, every one plays.

    Game 14: LAL's report 90 minutes before the decision lists L1 Questionable, its report 20 minutes before lists him
    Out. GSW's report 90 minutes before lists G1 Out, its report exactly 30 minutes before lists him Questionable.
    Game 15: the only report is LAL's, 10 minutes before the decision, listing L2 Out. Game 16: no report. Game LIVE: its
    prop row is dated past the research window, so its decision is the fallback, not its snapshot."""
    games, sched, props, log = [], [], [], []
    for k in range(REPORTED + 3):
        gid, date = f"G{k}", str(_tip(k))[:10]
        games.append({"game_id": gid, "season": 2025, "game_date": date, "commence_time": _tip(k).isoformat(),
                      "home_team": "LAL", "away_team": "GSW", "home_score": 100, "away_score": 95})
        sched.append({"game_id": gid, "season": 2025, "game_date": date, "game_type": "regular"})
        props.append({"game_id": gid, "game_date": date, "snapshot_at": _before(k, 0).isoformat()})
        for team in ("LAL", "GSW"):
            for n in range(1, 6):
                log.append({"game_id": gid, "player_id": f"{team[0]}{n}", "season": 2025, "game_date": date, "team": team,
                            "player_name": f"{team} Player{n}", "is_starter": True, "minutes": 30.0 + n, "points": 15.0,
                            "rebounds": 5.0, "offensive_reb": 1.0, "defensive_reb": 4.0, "assists": 3.0, "steals": 1.0,
                            "blocks": 1.0, "turnovers": 2.0, "fg_made": 6.0, "fg_att": 13.0, "fg3_made": 1.0, "fg3_att": 4.0,
                            "ft_made": 2.0, "ft_att": 3.0})
    games.append({"game_id": "LIVE", "season": 2027, "game_date": "2026-10-21", "commence_time": "2026-10-22T00:00:00+00:00",
                  "home_team": "LAL", "away_team": "GSW", "home_score": None, "away_score": None})
    sched.append({"game_id": "LIVE", "season": 2027, "game_date": "2026-10-21", "game_type": "regular"})
    props.append({"game_id": "LIVE", "game_date": "2026-10-21", "snapshot_at": "2026-10-21T23:05:00+00:00"})
    report = [("G14", "LAL", _before(14, 90), "L1", "LAL Player1", "Questionable"),
              ("G14", "LAL", _before(14, 20), "L1", "LAL Player1", "Out"),
              ("G14", "GSW", _before(14, 90), "G1", "GSW Player1", "Out"),
              ("G14", "GSW", _before(14, 30), "G1", "GSW Player1", "Questionable"),
              ("G15", "LAL", _before(15, 10), "L2", "LAL Player2", "Out")]
    return {"nba_games": pd.DataFrame(games), "nba_schedule": pd.DataFrame(sched), "nba_props": pd.DataFrame(props),
            "nba_player_game_log": pd.DataFrame(log),
            "nba_injury_report": pd.DataFrame(report, columns=["game_id", "team", "report_ts", "player_id", "player_name", "status"])}


def _keep_thread_setting(monkeypatch) -> None:
    for d in (S.nb.XGB_MIN, S.nb.XGB_COUNT):
        monkeypatch.setitem(d, "n_jobs", d["n_jobs"])   # fold_predictions sets it: put back for the next test


def _frame_the_folds_read(monkeypatch, work) -> pd.DataFrame:
    """The frame the real fold_predictions builds from the tiny cache, stopped before any model is fitted."""
    raw, seen, real = _tiny_raw(), {}, S.nb.build_frame

    def spy(data, dec, **kw):
        seen["frame"] = real(data, dec, **kw)
        raise _Stop

    monkeypatch.setattr(S.nb, "load_cache", lambda *a, **k: raw)
    monkeypatch.setattr(S.nb, "build_frame", spy)
    _keep_thread_setting(monkeypatch)
    with pytest.raises(_Stop):
        S.fold_predictions(work, work)
    return seen["frame"].set_index(["game_id", "player_id"])


def test_the_folds_read_a_report_30_minutes_after_it_is_printed(monkeypatch, tmp_path):
    fr = _frame_the_folds_read(monkeypatch, tmp_path)
    # printed 20 minutes before the decision: not known yet, so the report 90 minutes before is the one read
    assert fr.loc[("G14", "L1"), "status"] == "Questionable"
    assert fr.loc[("G14", "L1"), "own_q"] == 1.0
    assert fr.loc[("G14", "L2"), "tm_q_min"] > 0 and fr.loc[("G14", "L2"), "tm_o_min"] == 0
    # printed exactly 30 minutes before: known
    assert fr.loc[("G14", "G1"), "status"] == "Questionable"
    assert fr.loc[("G14", "L2"), "opp_o_min"] == 0
    # a game whose only report is under 30 minutes old has no report at all at the decision
    assert pd.isna(fr.loc[("G15", "L2"), "status"]) and pd.isna(fr.loc[("G15", "L2"), "own_q"])
    assert pd.isna(fr.loc[("G15", "L3"), "tm_o_min"])


def test_the_lag_is_the_records():
    assert pd.Timedelta(minutes=S.REPORT_LAG_MIN) == S.P.INJURY_LAG == pd.Timedelta(minutes=30)


def test_the_shift_lands_before_the_report_is_compacted():
    # shifted after compacting, the report 90 minutes before is already gone, and L1 reads as not listed at all
    raw = _tiny_raw()
    dec = pd.DataFrame({"game_id": ["G14"], "decision_ts": [_before(14, 0)]})

    def lal(lag):
        got = S.nb.injury_asof(S.report_as_known(raw["nba_injury_report"], dec, lag), dec)
        got = got[got["team"] == "LAL"]
        return dict(zip(got["player_id"], got["status"]))

    assert lal(30) == {"L1": "Questionable"}
    assert lal(0) == {"L1": "Out"}


def test_the_labs_inputs_are_the_shipped_research_path_but_for_the_lag(monkeypatch, tmp_path):
    # the lab holds its own copy of research_inputs' lines: at lag 0 it has to be the same path
    from scripts.nba_prop_projection_train import research_inputs
    raw = _tiny_raw()
    monkeypatch.setattr(S.nb, "load_cache", lambda *a, **k: raw)
    ours, dec_ours = S.lab_inputs(tmp_path, lag_min=0)
    theirs, dec_theirs = research_inputs(tmp_path)
    pd.testing.assert_frame_equal(dec_ours, dec_theirs)
    assert set(ours) == set(theirs)
    for k in ours:
        pd.testing.assert_frame_equal(ours[k], theirs[k])
    lagged, _ = S.lab_inputs(tmp_path)
    assert not lagged["nba_injury_report"].equals(ours["nba_injury_report"])   # and the default is not lag 0


def _fake_pred(season: int) -> pd.DataFrame:
    cols = list(S.FRAME_KEEP) + ["min_hat"] + [f"mu_{st}" for st in S.nb.BASE_STATS]
    d = {c: [1.0] for c in cols}
    d.update({"game_id": [f"F{season}"], "player_id": ["1"], "season": [season], "played": [True], "status": ["Listed none"]})
    return pd.DataFrame(d)


def test_folds_fitted_on_the_print_time_read_are_never_reused(monkeypatch, tmp_path):
    # the old names on disk: a run that returns these has read the print-time folds without a word
    for season in S.FOLDS:
        _fake_pred(season).to_parquet(tmp_path / f"pred_{season}.parquet")

    def reached(*a, **k):
        raise _Stop

    monkeypatch.setattr(S.nb, "load_cache", reached)
    _keep_thread_setting(monkeypatch)
    with pytest.raises(_Stop):                          # it goes and rebuilds them
        S.fold_predictions(tmp_path, tmp_path)


def _stub_models(monkeypatch, raw) -> None:
    monkeypatch.setattr(S.nb, "load_cache", lambda *a, **k: raw)
    monkeypatch.setattr(S.nb, "fit_minutes", lambda tr, cols=None: None)
    monkeypatch.setattr(S.nb, "predict_minutes", lambda m, te: np.full(len(te), 30.0))
    monkeypatch.setattr(S.nb, "fit_rate", lambda tr, st, cols=None: None)
    monkeypatch.setattr(S.nb, "predict_rate_mean", lambda m, te, mins: np.full(len(te), 5.0))
    monkeypatch.setattr(S, "FOLDS", (2025,))
    _keep_thread_setting(monkeypatch)


def test_parts_of_a_print_time_fold_are_never_resumed(monkeypatch, tmp_path):
    # a stopped refit resumes from its parts: the old names must not feed a new fold
    _stub_models(monkeypatch, _tiny_raw())
    clean, old = tmp_path / "clean", tmp_path / "old"
    clean.mkdir()
    old.mkdir()
    n = len(S.fold_predictions(clean, clean))
    assert n > 0
    np.save(old / "part_2025_minutes.npy", np.full(n, -999.0))
    for st in S.nb.BASE_STATS:
        np.save(old / f"part_2025_{st}.npy", np.full(n, -999.0))
    got = S.fold_predictions(old, old)
    assert (got["min_hat"] == 30.0).all() and (got["mu_points"] == 5.0).all()


def test_a_fold_on_this_read_is_kept_and_read_back(monkeypatch, tmp_path):
    # the resume still works: built once, then no rebuild
    _stub_models(monkeypatch, _tiny_raw())
    a = S.fold_predictions(tmp_path, tmp_path)

    def reached(*x, **k):
        raise AssertionError("rebuilt a fold it already holds")

    monkeypatch.setattr(S.nb, "load_cache", reached)
    b = S.fold_predictions(tmp_path, tmp_path)
    pd.testing.assert_frame_equal(a, b)


# ── end to end: through the harness, the files and the verdict ──────────────

def test_credit_compares_each_anchored_cell_with_its_own_reference_kind():
    rows = []
    for fam, ref, roi in ((S.FAMILY_AN, "pinnacle", 0.05), (S.CONTROL_AN, "pinnacle", 0.08), (S.FAMILY_AN, "consensus", 0.05),
                          (S.CONTROL_AN, "consensus", 0.01)):
        rows.append({"family": fam, "axis_ref": ref, "side": "under", "cut_index": 0, "cut": 0.01, "pool_roi": roi})
    rows.append({"family": S.FAMILY_AN, "axis_ref": "pinnacle", "side": "over", "cut_index": 0, "cut": 0.01, "pool_roi": 0.02})
    t = S.credit_table(pd.DataFrame(rows)).set_index(["axis_ref", "side"])
    assert not t.loc[("pinnacle", "under"), "beats_control"]         # 0.05 under its own control's 0.08
    assert t.loc[("consensus", "under"), "beats_control"]            # 0.05 over its own control's 0.01
    assert t.loc[("pinnacle", "over"), "beats_control"]              # a control with no bet counts as 0


def test_a_strong_cell_never_runs_the_slow_refinement(monkeypatch):
    # the planted edge's p is far under the refinement's limit, so only the switch keeps its 400,000 draws away
    groups, props, stat, _ = S.world_groups(S.synthetic_world(seed=2))
    games, times = S.games_table(props, stat), S.times_table(props)
    g = next(x for x in groups if x.family == S.FAMILY_OL and x.side == "under")
    draws = []
    real_boot = H.boot

    def spy(b, n=200, seed=H.SEED):
        draws.append(n)
        return real_boot(b, n=200, seed=seed)

    monkeypatch.setattr(H, "boot", spy)
    before = H.P_REFINE_BELOW
    rows = S.emit(g, games, times, seeds=())
    assert draws and max(draws) == 200 and min(r["p_choose"] for r in rows) < before
    assert H.P_REFINE_BELOW == before                   # every other lab in the process keeps the harness as it was


def test_a_planted_edge_can_pass_every_bar_of_the_verdict(fast_boot):
    # a bar the prop-as-game encoding left dead would never say yes: on a planted edge it has to
    groups, props, stat, _ = S.world_groups(S.synthetic_world(seed=2))
    games, times = S.games_table(props, stat), S.times_table(props)
    g = next(x for x in groups if x.family == S.FAMILY_OL and x.side == "under")
    seeds = tuple(range(1, 21))
    cells = pd.DataFrame(S.emit(g, games, times, seeds=seeds))
    h = V.house_verdict_bands(cells, n_placebo=len(seeds))
    assert h["house5_passes"].any(), h["house5_failed"].tolist()
    assert (h["gate_dropped"] == "").all() and (h["choose_seasons"] == "2024,2025").all()


def test_cells_and_bets_are_written_and_the_verdict_reads_them(tmp_path, monkeypatch, fast_boot):
    bets = tmp_path / "bets"
    monkeypatch.setenv(S.BETS_ENV, str(bets))
    groups, props, stat, _ = S.world_groups(S.synthetic_world())
    games, times = S.games_table(props, stat), S.times_table(props)
    seeds = (1, 2, 3)
    all_rows = []
    for g in groups:
        rows = S.emit(g, games, times, seeds=seeds if g.placebo is not None else ())
        L.write_cells(rows, tmp_path / f"cells_{g.name}.parquet")
        all_rows += rows
    cells = V.load_cells(tmp_path)
    assert len(cells) == len(all_rows)
    assert (cells["gate_dropped"] == "").all()          # no season lost to the coverage gate
    assert set(cells.loc[cells["family"] == S.FAMILY_OL, "choose_seasons"]) == {"2024,2025"}
    assert set(cells.loc[cells["family"] == S.FAMILY_CS, "choose_seasons"]) == {"2024,2025"}
    assert set(cells.loc[cells["family"] == S.FAMILY_AN, "choose_seasons"]) == {"2025"}
    assert set(cells.loc[cells["family"] == S.FAMILY_AN, "pool_seasons"]) == {"2025,2026"}
    h = V.house_verdict_bands(cells, n_placebo=len(seeds))
    assert len(h) == S.EXPECTED_CELLS                   # the controls are not judged
    assert {"axis_ref", "axis_rule", "house5_passes", "h5_bands", "h6_placebo"} <= set(h.columns)
    f = sorted(bets.glob("bets_*.parquet"))
    assert f, "no bet file: a passing cell's figures read them"
    b = pd.read_parquet(f[0])
    assert {"game_id", "side", "book", "line", "price", "units", "result", "cut"} <= set(b.columns)
    assert not {"sigma", "mu", "p_home"} & set(b.columns)


def test_smoke_grades_nothing_real(monkeypatch, capsys, fast_boot):
    # the only H.grade in the smoke's body is on the all-zero table
    world = S.synthetic_world()
    seen = []
    real_grade = H.grade

    def guard(bets, games):
        seen.append(float(games["home_score"].abs().sum()))
        return real_grade(bets, games)

    monkeypatch.setattr(H, "grade", guard)
    out = S.smoke_report(S.world_prep(world), world["preds"])
    assert seen and max(seen) == 0.0
    assert {"bets_pooled"} <= set(out["counts"].columns) and "units" not in out["counts"].columns
    printed = capsys.readouterr().out
    assert "share_differ" in printed and "projected_seconds" in printed


def test_full_writes_every_file_and_a_stopped_run_resumes(monkeypatch, tmp_path, capsys, fast_boot):
    # the real path through full(), on the invented world
    world = S.synthetic_world()
    out = tmp_path / "results"
    monkeypatch.setenv(S.GO_ENV, "1")
    monkeypatch.setenv(S.RESULTS_ENV, str(out))
    monkeypatch.setenv(S.BETS_ENV, str(out / "bets"))
    (tmp_path / "nba_props.parquet").write_bytes(b"x")
    monkeypatch.setattr(S, "synthetic_checks", lambda: {"synthetic_checks": "pass"})
    monkeypatch.setattr(S, "prepare", lambda cache, work: S.world_prep(world))
    monkeypatch.setattr(S, "fold_predictions", lambda cache, work: world["preds"])
    monkeypatch.setattr(S, "PLACEBO_SEEDS", (1, 2, 3))
    S.full(tmp_path, tmp_path)
    cells = sorted(out.glob("cells_*.parquet"))
    assert len(cells) == 15 and len(sorted(out.glob("beside_*.parquet"))) == 15
    for f in ("props.parquet", "model_rows.parquet", "model_fits.parquet", "credit_AN.parquet"):
        assert (out / f).exists(), f
    assert sorted((out / "bets").glob("bets_*.parquet"))
    credit = pd.read_parquet(out / "credit_AN.parquet")
    assert len(credit) == 12 and set(credit["axis_ref"]) == {"pinnacle", "consensus"}
    h = V.house_verdict_bands(V.load_cells(out), n_placebo=3)
    assert len(h) == S.EXPECTED_CELLS
    # one finished group is removed: only that one is redone
    gone = cells[0]
    kept = cells[1]
    gone.unlink()
    stamp = kept.stat().st_mtime_ns
    capsys.readouterr()
    S.full(tmp_path, tmp_path)
    printed = capsys.readouterr().out
    assert gone.exists() and kept.stat().st_mtime_ns == stamp
    assert printed.count("already written, skipped") == 14


def test_full_refuses_without_its_three_variables(monkeypatch, tmp_path):
    for k in (S.GO_ENV, S.RESULTS_ENV, S.BETS_ENV):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "nba_props.parquet").write_bytes(b"x")
    why = " ".join(S.refuse_full(tmp_path))
    assert S.GO_ENV in why and S.RESULTS_ENV in why and S.BETS_ENV in why
    with pytest.raises(SystemExit):
        S.full(tmp_path, tmp_path)
    monkeypatch.setenv(S.GO_ENV, "1")
    monkeypatch.setenv(S.RESULTS_ENV, str(tmp_path / "r"))
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path / "b"))
    assert S.refuse_full(tmp_path) == []

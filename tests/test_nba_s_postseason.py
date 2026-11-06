"""The postseason search's lab (docs/nba_search_postseason.md): settlement from the play feed, both
shipped rules on these games, how a proposition passes through the game harness, the placebo as a
null on thin dates, the caps and which fit a game reads. Synthetic data, no cache, no network, no
database. Each rule test below was watched failing with its rule broken (the mutation list is in
the search's doc, section 8)."""
from __future__ import annotations

from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from models import nba_prop_market as PM
from models import nba_prop_projection as pj
from models import nba_props as nb
from models.honest_ev import gate
from scripts import nba_game_harness as H
from scripts import nba_s_postseason as S
from scripts.nba_game2_verdict import house_verdict_bands


@pytest.fixture(scope="module")
def lines():
    plays, box, ids = S.synthetic_plays()
    return S.derive_lines(plays, box, ids).set_index("espn_id")


# ── settlement ──────────────────────────────────────────────────────────────

def test_points_threes_and_free_throws_come_from_the_plays(lines):
    assert (lines.loc[1, "points"], lines.loc[1, "fg3_made"], lines.loc[1, "fg3_att"]) == (3, 1, 2)
    assert (lines.loc[2, "points"], lines.loc[2, "ft_made"], lines.loc[2, "ft_att"]) == (3, 1, 2)


def test_a_made_two_is_not_a_three(lines):
    assert lines.loc[2, "fg_made"] == 1 and lines.loc[2, "fg3_made"] == 0


def test_an_assist_goes_to_the_passer_on_a_made_shot_only(lines):
    assert lines.loc[2, "assists"] == 1 and lines.loc[1, "assists"] == 0


def test_a_block_goes_to_the_blocker_not_the_shooter(lines):
    assert lines.loc[1, "blocks"] == 1 and lines.loc[2, "blocks"] == 0


def test_a_steal_goes_to_the_stealer_and_the_turnover_to_the_passer(lines):
    assert lines.loc[1, "steals"] == 1 and lines.loc[2, "steals"] == 0
    assert lines.loc[2, "turnovers"] == 1


def test_a_no_turnover_row_and_a_team_turnover_count_for_nobody(lines):
    assert lines.loc[1, "turnovers"] == 1        # the offensive foul, not the "No Turnover" row


def test_a_heave_is_not_a_field_goal_attempt(lines):
    assert lines.loc[1, "fg_att"] == 2 and lines.loc[1, "fg3_att"] == 2


def test_rebounds_are_offensive_plus_defensive_and_team_rebounds_count_for_nobody(lines):
    assert lines.loc[2, "rebounds"] == 2 and lines.loc[2, "offensive_reb"] == 1 and lines.loc[1, "rebounds"] == 1


def test_a_played_player_with_no_event_is_zeros_and_a_scratch_has_no_line(lines):
    assert lines.loc[3, "points"] == 0 and lines.loc[3, "minutes"] == 2.0
    assert 4 not in lines.index


def test_the_cross_check_finds_a_game_differing_on_one_stat_of_one_player(lines):
    a = lines.reset_index()
    b = a.copy()
    b.loc[b.espn_id == 2, "steals"] = 1.0
    c = S.compare_lines(a, b, ["game_id", "espn_id"])
    assert c["games"] == {"G"} and c["by_stat"]["steals"] == (1, 1) and c["by_stat"]["rebounds"] == (0, 0)


def test_a_line_only_one_source_holds_counts_as_zeros_there(lines):
    a = lines.reset_index()
    extra = a[a.espn_id == 1].assign(espn_id=99, points=4.0)
    c = S.compare_lines(a, pd.concat([a, extra], ignore_index=True), ["game_id", "espn_id"])
    assert c["by_stat"]["points"] == (1, 1)
    zero = a[a.espn_id == 3].assign(espn_id=98)
    z = S.compare_lines(a, pd.concat([a, zero], ignore_index=True), ["game_id", "espn_id"])
    assert z["games"] == set()                   # a line of zeros in one source is not a difference


def test_a_player_takes_the_court_on_minutes_or_seconds():
    lines_ = pd.DataFrame({"game_id": "G", "player_id": ["1", "2", "3"], "minutes": [0.0, 0.0, 12.0]})
    adv = pd.DataFrame({"game_id": "G", "player_id": ["1", "2", "3"], "seconds_played": [20.0, 0.0, np.nan]})
    a = S.take_court(lines_, adv, ["G"]).set_index("player_id").action
    assert a["1"] and not a["2"] and a["3"]


def test_a_stat_is_the_markets_own_sum():
    r = pd.DataFrame({"rebounds": [3.0], "assists": [4.0], "blocks": [1.0], "steals": [2.0], "points": [10.0],
                      "fg3_made": [2.0]})
    assert S.stat_of(r, "player_rebounds_assists").iloc[0] == 7
    assert S.stat_of(r, "player_blocks_steals").iloc[0] == 3
    assert S.stat_of(r, "player_points_rebounds_assists").iloc[0] == 17
    assert S.stat_of(r, "player_threes").iloc[0] == 2


def test_a_game_left_out_and_a_void_have_no_synthetic_game():
    ln = pd.DataFrame({"game_id": ["A", "A", "B"], "player_id": ["1", "2", "1"], **{c: 1.0 for c in S.BOX_STATS}})
    act = pd.DataFrame({"game_id": ["A", "A", "B"], "player_id": ["1", "2", "1"], "action": [True, False, True]})
    g = pd.DataFrame({"game_id": ["A", "B"], "season": [2024, 2024], "game_date": ["d", "d"]})
    sg = S.settled_games(ln, act, g, {"A"}, markets=("player_steals",))
    assert list(sg.game_id) == ["A|1|player_steals"]


def test_every_synthetic_game_id_is_filled_and_distinct_on_many_rows():
    ln = pd.DataFrame({"game_id": ["A", "A", "A"], "player_id": ["1", "2", "3"], **{c: 1.0 for c in S.BOX_STATS}})
    act = pd.DataFrame({"game_id": ["A", "A", "A"], "player_id": ["1", "2", "3"], "action": True})
    g = pd.DataFrame({"game_id": ["A"], "season": [2024], "game_date": ["d"]})
    sg = S.settled_games(ln, act, g, {"A"}, markets=("player_steals", "player_blocks"))
    assert sg.game_id.notna().all() and sg.game_id.is_unique and len(sg) == 6
    assert S.pid_of(["A", "B"], ["1", "2"], "m").tolist() == ["A|1|m", "B|2|m"]
    assert S.pid_of(["A", "B"], ["1", "2"], ["m", "n"]).tolist() == ["A|1|m", "B|2|n"]


def test_an_offer_and_its_settled_game_share_one_id(market):
    r = S.with_lead(S.market_rows(market[0], clock=False), {"G": "2024-04-20T23:00:00Z"})
    off = S.offers_frame(r, market[1], S.RULE_ID)
    ln = pd.DataFrame({"game_id": "G", "player_id": ["P1", "P2"], **{c: 3.0 for c in S.BOX_STATS}})
    act = pd.DataFrame({"game_id": "G", "player_id": ["P1", "P2"], "action": True})
    sg = S.settled_games(ln, act, market[1], {"G"}, markets=("player_points", "player_rebounds"))
    assert set(off.game_id) <= set(sg.game_id)


def test_the_blind_table_used_to_time_a_run_holds_no_result():
    ln = pd.DataFrame({"game_id": ["A"], "player_id": ["1"], **{c: 5.0 for c in S.BOX_STATS}})
    act = pd.DataFrame({"game_id": ["A"], "player_id": ["1"], "action": [True]})
    g = pd.DataFrame({"game_id": ["A"], "season": [2024], "game_date": ["d"]})
    assert S.settled_games(ln, act, g, {"A"}, markets=("player_steals",)).home_score.iloc[0] == 5.0
    assert S.settled_games(ln, act, g, {"A"}, markets=("player_steals",), blind=True).home_score.iloc[0] == 0.0


# ── nba_prop_market, as shipped ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def market():
    return S.synthetic_market()


def test_the_rule_takes_only_pinnacles_exact_line(market):
    r = S.market_rows(market[0], clock=True)
    assert ("P1", "fanduel") not in set(zip(r.player_id, r.bookmaker))
    assert ("P1", "draftkings") in set(zip(r.player_id, r.bookmaker))


def test_the_rule_refuses_a_book_ten_minutes_behind_pinnacle(market):
    with_clock = S.market_rows(market[0], clock=True)
    no_clock = S.market_rows(market[0], clock=False)
    assert ("P2", "betmgm") not in set(zip(with_clock.player_id, with_clock.bookmaker))
    assert ("P2", "betmgm") in set(zip(no_clock.player_id, no_clock.bookmaker))


def test_the_rule_counts_a_book_with_no_clock(market):
    q = market[0].copy()
    q.loc[q.bookmaker == "betmgm", "book_last_update"] = None
    r = S.market_rows(q, clock=True)
    assert ("P2", "betmgm") in set(zip(r.player_id, r.bookmaker))


def test_the_rule_has_five_markets(market):
    assert "player_double_double" not in set(S.market_rows(market[0], clock=False).market)
    assert set(S.PM.MARKETS) == {"player_points", "player_rebounds", "player_assists", "player_threes",
                                 "player_points_rebounds_assists"}


def test_the_rule_needs_a_coherent_pinnacle(market):
    assert "P4" not in set(S.market_rows(market[0], clock=False).player_id)


def test_the_rules_ev_is_pinnacles_no_vig_under_times_the_price(market):
    r = S.with_lead(S.market_rows(market[0], clock=False), {"G": "2024-04-20T23:00:00Z"})
    off = S.offers_frame(r, market[1], S.RULE_ID)
    p = S.MarketPricer(off, r.fair_under.to_numpy()).priced()
    x = p[(p.player_id == "P1") & (p.book == "draftkings")].iloc[0]
    assert x.p_win == pytest.approx(0.5) and x.ev == pytest.approx(0.5 * 2.05 - 1)
    assert x.lead_min == pytest.approx(54.0)


# Pinnacle's over, Pinnacle's under, DraftKings' under. Each is worth exactly nothing: Paul George
# under 5.5 rebounds on 2026-04-21 is 63/113 x 113/63, Julian Champagnie under 4.5 rebounds on
# 2026-06-10 is 100/217 x 217/100.
WORTH_NOTHING = [(116.0, -140.0, -126.0), (-130.0, 107.0, 117.0)]


def _exact_ev(over, under, price):
    def dec(a):
        a = Fraction(int(a))
        return 1 + (a / 100 if a > 0 else 100 / abs(a))
    io, iu = 1 / dec(over), 1 / dec(under)
    return iu / (io + iu) * dec(price) - 1


def _rule_quotes(props):
    """props: (player, Pinnacle over, Pinnacle under, DraftKings under). DraftKings' over keeps its
    two-way quote coherent, so the shipped code reads the same offer."""
    base = {"game_id": "G", "season": 2024, "game_date": "2024-04-20", "snapshot_at": "2024-04-20T22:06:00Z",
            "usable": True, "x": 10.0, "has_o": True, "has_u": True, "coherent": True, "market": "player_rebounds",
            "line": 5.5, "book_last_update": "2024-04-20T22:05:00Z"}

    def row(pl, book, over, under):
        return {**base, "player_id": pl, "player_name": f"Player {pl}", "bookmaker": book, "over_price": over,
                "under_price": under, "od": float(nb.decimal(over)), "ud": float(nb.decimal(under))}
    rows = []
    for pl, po, pu, px in props:
        rows += [row(pl, "pinnacle", po, pu), row(pl, "draftkings", 100.0 if px < 0 else -140.0, px)]
    return pd.DataFrame(rows)


def _priced_rule(props):
    r = S.with_lead(S.market_rows(_rule_quotes(props), clock=False), {"G": "2024-04-20T23:00:00Z"})
    return S.MarketPricer(S.offers_frame(r, _meta(), S.RULE_ID), r.fair_under.to_numpy()).priced()


@pytest.mark.parametrize("over,under,price", WORTH_NOTHING)
def test_an_offer_worth_exactly_nothing_clears_the_floor_as_the_shipped_gate_has_it(over, under, price):
    assert _exact_ev(over, under, price) == 0
    shipped = gate(S.RULE_ID, PM.fair_under({"over_price": over, "under_price": under}), price)
    assert shipped.ev == 0.0 and shipped.clears
    bets = S.qualifying(_priced_rule([("P", over, under, price)]), S.PM_FLOOR, "under")
    assert list(bets.game_id) == ["G|P|player_rebounds"] and bets.ev.iloc[0] == shipped.ev


def test_the_rules_ev_equals_the_shipped_gate_to_the_last_bit():
    rng = np.random.default_rng(11)
    prices = np.r_[np.arange(-300.0, -99.0), np.arange(100.0, 301.0)]
    props = [(str(i), *rng.choice(prices, 3)) for i in range(3000)]
    lab = _priced_rule(props).set_index("player_id").ev
    assert len(lab) == len(props)
    differ = [pl for pl, po, pu, px in props
              if lab[pl] != gate(S.RULE_ID, PM.fair_under({"over_price": po, "under_price": pu}), px).ev]
    assert differ == []


@pytest.mark.parametrize("over,under,price", WORTH_NOTHING)
def test_a_rule_bet_worth_exactly_nothing_is_never_a_projection_bet(over, under, price):
    bets = S.qualifying(_priced_rule([("1", over, under, price)]), S.PM_FLOOR, "under")
    at = S.card_rows(_card_q(), clock=False)
    assert "1" in set(S.card_offers(at, _means(), _inputs(), set(), _meta()).player_id)
    assert "1" not in set(S.card_offers(at, _means(), _inputs(), S.rule_keys_of(bets), _meta()).player_id)


def test_the_lab_bets_what_the_shipped_code_bets_at_and_around_zero():
    props = [("1", *WORTH_NOTHING[0]), ("2", *WORTH_NOTHING[1]), ("3", -110.0, -110.0, -115.0), ("4", -110.0, -110.0, 105.0)]
    q = _rule_quotes(props)
    shipped = S.shipped_rule_bets(q, q[["game_id", "player_name", "player_id"]].drop_duplicates(), {"G": ("AAA", "BBB")})
    assert sorted(shipped.game_id) == [f"G|{p}|player_rebounds" for p in ("1", "2", "4")]
    c = S.compare_to_shipped(S.qualifying(_priced_rule(props), S.PM_FLOOR, "under"), shipped)
    assert (c["shipped_only"], c["lab_only"], c["in_both"], c["same_book_price_line"]) == ([], [], 3, 3)


def test_the_comparison_to_the_shipped_code_finds_a_missing_bet_and_a_different_offer():
    ship = pd.DataFrame({"game_id": ["a", "b", "c"], "book": "draftkings", "price": [-110.0, -110.0, 100.0], "line": 5.5, "ev": 0.0})
    lab = pd.DataFrame({"game_id": ["a", "b", "d"], "book": "draftkings", "price": [-110.0, -105.0, 100.0], "line": 5.5})
    c = S.compare_to_shipped(lab, ship)
    assert (c["shipped_only"], c["lab_only"], c["in_both"], c["same_book_price_line"]) == (["c"], ["d"], 2, 1)


def test_floor_ties_counts_offers_a_rounding_step_from_their_floor_and_no_others():
    pm = pd.DataFrame({"ev": [0.0, -1.1e-16, 2.2e-16, 0.004, -0.004]})
    pjf = pd.DataFrame({"real_market": ["player_steals"] * 3, "margin": [-1.1e-16, 0.0, 0.001]})
    prep = {"pm_pricer": SimpleNamespace(priced=lambda: pm), "pj_pricer": SimpleNamespace(priced=lambda: pjf)}
    out = S.floor_ties(prep)
    assert out[S.LABEL_PM] == {"at_the_floor": 3, "just_below": 1}
    assert out["player_steals"] == {"at_the_floor": 2, "just_below": 1}


def test_the_rule_bets_one_under_a_proposition_at_the_best_price_above_the_floor():
    off = pd.DataFrame({"game_id": ["a"] * 3 + ["b"], "market": "totals", "side": "under",
                        "book": ["draftkings", "fanduel", "betmgm", "fanduel"],
                        "price": [100.0, 105.0, 110.0, -210.0], "ev": [0.0, 0.025, 0.05, 0.5], "line": 5.5})
    b = S.qualifying(off[off.book != "x"], 0.0, "under")
    assert list(zip(b.game_id, b.book)) == [("a", "betmgm")]    # "b" lays beyond -200


def test_offers_read_their_game_by_position_on_a_filtered_index(market):
    r = S.with_lead(S.market_rows(market[0], clock=False), {"G": "2024-04-20T23:00:00Z"})
    r.index = np.arange(100, 100 + len(r))
    off = S.offers_frame(r, market[1], S.RULE_ID)
    assert off.season.tolist() == [2024] * len(r) and off.phase.tolist() == ["playoffs"] * len(r)
    assert off.game_id.iloc[0] == f"G|{r.player_id.iloc[0]}|{r.market.iloc[0]}"


# ── a proposition through the harness ───────────────────────────────────────

def test_a_prop_settles_through_the_harness_over_under_push_and_void():
    bets = pd.DataFrame({"game_id": ["a", "b", "c", "d", "e"], "market": "totals",
                         "side": ["over", "under", "under", "over", "under"], "line": [5.5, 5.5, 5.0, 5.5, 5.5],
                         "price": -110.0, "season": 2024, "game_date": "d", "book": "draftkings"})
    games = pd.DataFrame({"game_id": ["a", "b", "c", "d"], "home_score": [6.0, 5.0, 5.0, 5.0], "away_score": 0.0})
    g = H.grade(bets, games).set_index("game_id")
    assert list(g.result) == ["W", "W", "P", "L"] and "e" not in g.index
    assert g.loc["c", "risk"] == 0.0 and g.loc["c", "units"] == 0.0
    assert g.loc["a", "units"] == pytest.approx(1.0)


def test_each_cell_writes_what_the_verdict_reads_and_the_verdict_judges_it():
    h = S.synthetic_harness()
    v, r = h["verdict"], h["row"]
    assert len(r["placebo_rois"]) == 200
    assert r["pool_n"] > 200 and r["pool_seasons"] == "2024,2025,2026" and r["choose_seasons"] == "2024,2025"
    assert r["band0_lo"] == pytest.approx(0.0) and r["band1_lo"] == pytest.approx(0.02) and np.isinf(r["band4_hi"])
    assert np.isfinite(r["blind_pool_under"]) and v["h4_blind"] in (True, False) and "house5_passes" in v.index
    assert r["phase_playoffs_n"] == r["pool_n"] and r["lead_54_n"] == r["pool_n"] and r["dk_pool_n"] == r["pool_n"]
    assert np.isnan(r["share_still_offered"])    # one snapshot a game: unknowable, not zero


def test_the_verdict_refuses_a_cell_with_the_wrong_placebo_count():
    h = S.synthetic_harness()
    bad = dict(h["row"])
    bad["placebo_rois"] = bad["placebo_rois"][:20]
    with pytest.raises(ValueError):
        house_verdict_bands(pd.DataFrame([bad]))


def test_a_band_with_a_loss_fails_bar_five_and_a_thin_band_is_not_judged():
    h = S.synthetic_harness()
    r = dict(h["row"])
    r.update({"band2_n": 40, "band2_roi": -0.1})
    assert not bool(house_verdict_bands(pd.DataFrame([r])).iloc[0]["h5_bands"])
    r.update({"band2_n": 29, "band2_roi": -0.1, **{f"band{i}_roi": 0.05 for i in (0, 1, 3, 4)}})
    assert bool(house_verdict_bands(pd.DataFrame([r])).iloc[0]["h5_bands"]) == bool(r["pool_roi"] > 0)


def test_saved_bets_have_no_object_column_parquet_cannot_store(tmp_path, monkeypatch):
    monkeypatch.setenv(S.BETS_ENV, str(tmp_path))
    monkeypatch.setenv("NBA_GAME2_BETS", str(tmp_path))
    S.synthetic_harness()
    files = list(tmp_path.glob("bets_*.parquet"))
    assert files
    d = pd.read_parquet(files[0])
    assert {"game_id", "side", "price", "line", "result", "units", "risk"} <= set(d.columns)
    assert not {"sigma", "sigma1"} & set(d.columns)


# ── nba_prop_projection, as shipped ─────────────────────────────────────────

def _card_q():
    rows = []

    def q(player, market, book, line, over, under, status=None, usable=True, clock="2024-04-20T22:05:00Z"):
        rows.append({"game_id": "G", "player_id": player, "market": market, "bookmaker": book, "line": line,
                     "over_price": over, "under_price": under, "two_sided": True, "usable": usable, "status": status,
                     "snapshot_at": "2024-04-20T22:06:00Z", "book_last_update": clock, "lead_min": 54.0, "season": 2024,
                     "played": True, "actual": 1.0})
    q("1", "player_rebounds", "draftkings", 5.5, -110, -110)
    q("1", "player_rebounds", "fanduel", 5.5, -115, -105)
    q("1", "player_rebounds", "betmgm", 6.5, 120, -150)
    q("2", "player_steals", "fanduel", 1.5, 120, -150)      # no DraftKings: two books at 1.5 beat one at 0.5
    q("2", "player_steals", "betmgm", 1.5, 125, -155)
    q("2", "player_steals", "betrivers", 0.5, -200, 150)
    q("3", "player_blocks", "draftkings", 0.5, -110, -110, status="Out")
    q("4", "player_blocks", "draftkings", 0.5, -110, -110, usable=False)
    q("5", "player_threes", "draftkings", 2.5, -110, -110, clock="2024-04-20T21:40:00Z")
    q("5", "player_threes", "fanduel", 2.5, -115, -105)
    return pd.DataFrame(rows)


def _meta():
    return pd.DataFrame({"game_id": ["G"], "season": [2024], "game_date": ["2024-04-20"], "phase": ["playoffs"],
                         "round": ["first_round"], "commence_time": ["2024-04-20T23:00:00Z"]})


def test_the_card_reads_draftkings_line_else_the_line_most_books_hang():
    at = S.card_rows(_card_q(), clock=False)
    lines_ = dict(zip(at.player_id, at.line))
    assert lines_["1"] == 5.5 and lines_["2"] == 1.5
    assert 6.5 not in set(at.line) and 0.5 not in set(at[at.player_id == "2"].line)


def test_the_card_never_prices_a_player_out_or_a_row_with_too_few_games():
    at = S.card_rows(_card_q(), clock=False)
    assert "3" not in set(at.player_id) and "4" not in set(at.player_id)


def test_the_card_refuses_a_quote_ten_minutes_behind_the_freshest_of_its_market():
    a, b = S.card_rows(_card_q(), clock=True), S.card_rows(_card_q(), clock=False)
    assert ("5", "draftkings") not in set(zip(a.player_id, a.bookmaker))
    assert ("5", "draftkings") in set(zip(b.player_id, b.bookmaker))


def _inputs():
    width = dict.fromkeys(pj.MARKETS, 0.1)
    mp = dict.fromkeys(pj.MARKETS, (0.0, 1.0))
    return {"G": (None, width, mp)}


def _means():
    return pd.DataFrame({"game_id": "G", "player_id": ["1", "2", "5"],
                         **{f"mu_{m}": [5.0, 2.5, 3.5] for m in pj.MARKETS}})


def test_the_card_offers_only_each_markets_sides_and_never_a_rule_proposition():
    at = S.card_rows(_card_q(), clock=False)
    off = S.card_offers(at, _means(), _inputs(), set(), _meta())
    assert set(off[off.real_market == "player_rebounds"].side) == {"under"}
    assert set(off[off.real_market == "player_steals"].side) == {"over", "under"}
    held = S.card_offers(at, _means(), _inputs(), {("G", "2", "player_steals")}, _meta())
    assert "2" not in set(held.player_id)


def test_the_cards_ev_is_the_calibrated_probability_times_the_price():
    at = S.card_rows(_card_q(), clock=False)
    off = S.card_offers(at, _means(), _inputs(), set(), _meta())
    p = S.ProjectionPricer(off).priced()
    x = p[(p.player_id == "1") & (p.book == "draftkings")].iloc[0]
    want = 1 - float(nb.p_over(np.array([5.0]), np.array([5.5]), 0.1)[0])
    assert x.p_win == pytest.approx(want) and x.ev == pytest.approx(want * (1 + 100 / 110) - 1)
    assert x.floor == pytest.approx(pj.CARD["player_rebounds"][1]) and x.margin == pytest.approx(x.ev - x.floor)


def test_the_map_moves_the_probability():
    at = S.card_rows(_card_q(), clock=False)
    width = dict.fromkeys(pj.MARKETS, 0.1)
    plain = S.card_offers(at, _means(), {"G": (None, width, dict.fromkeys(pj.MARKETS, (0.0, 1.0)))}, set(), _meta())
    tilted = S.card_offers(at, _means(), {"G": (None, width, dict.fromkeys(pj.MARKETS, (0.5, 1.0)))}, set(), _meta())
    a = S.ProjectionPricer(plain).priced()
    b = S.ProjectionPricer(tilted).priced()
    assert (a[a.side == "under"].p_win > b[b.side == "under"].p_win).all()


def test_a_both_sides_cell_bets_its_higher_ev_side_only():
    at = S.card_rows(_card_q(), clock=False)
    off = S.card_offers(at, _means(), _inputs(), set(), _meta())
    p = S.ProjectionPricer(off[off.real_market == "player_steals"]).priced()
    b = H.choose(p, -np.inf, sides=[S.SIDE_BOTH])
    assert len(b) == 1
    top = p[p.price >= H.PRICE_FLOOR].sort_values("ev", ascending=False).iloc[0]
    assert b.side.iloc[0] == top.side and b.book.iloc[0] == top.book


def test_a_playoff_game_reads_the_fit_through_its_season_and_the_shipped_artifact_for_2025_26():
    pg = pd.DataFrame({"game_id": ["a", "b", "c"], "season": [2024, 2025, 2026], "phase": "playoffs",
                       "game_date": ["2024-05-01", "2025-05-01", "2026-05-01"]})
    folds = {2023: "f23", 2024: "f24", 2025: "f25"}
    alphas = {2023: "a23", 2024: "a24", 2025: "a25", 2026: "a26"}
    inp = S.model_inputs(pg, folds, alphas, {2024: "m24", 2025: "m25", 2026: "m26"}, None, "shipped")
    assert inp["a"] == ("f24", "a24", "m24") and inp["b"] == ("f25", "a25", "m25") and inp["c"] == ("shipped", "a26", "m26")


def test_a_cup_final_reads_the_fit_before_its_season(monkeypatch):
    pg = pd.DataFrame({"game_id": ["c"], "season": [2025], "phase": "cup_final", "game_date": ["2024-12-17"]})
    monkeypatch.setattr(S, "cup_map", lambda pairs, season, day, proxy=None: f"map{season}")
    inp = S.model_inputs(pg, {2024: "f24"}, {2024: "a24"}, {}, None, "shipped")
    assert inp["c"] == ("f24", "a24", "map2025")


def test_a_cup_final_map_never_reads_its_own_season_after_2023_24_or_a_later_game():
    n = 400
    pairs = pd.DataFrame({"season": [2024] * n + [2025] * n, "market": "player_steals",
                          "p": np.linspace(0.2, 0.8, 2 * n), "y": (np.arange(2 * n) % 3 == 0).astype(float),
                          "game_date": (["2023-11-01"] * n) + (["2024-11-01"] * n)})
    a = S.cup_map(pairs, 2025, "2024-12-17")
    b = nb.fit_platt(pairs[pairs.season == 2024].p.values, pairs[pairs.season == 2024].y.values)
    assert a["player_steals"] == pytest.approx(b)
    assert S.cup_map(pairs, 2024, "2023-10-20") == {}
    assert S.cup_map(pairs, 2024, "2023-10-20", {"player_steals": (0.1, 0.9)}) == {"player_steals": (0.1, 0.9)}
    later = S.cup_map(pairs, 2024, "2023-12-09", {"player_steals": (0.1, 0.9)})
    assert later["player_steals"] != (0.1, 0.9)     # 400 pairs from before that week: the season's own map


def test_the_rounds_are_read_from_every_label_the_schedule_uses():
    want = {"West - First Round": "first_round", "East First Round": "first_round",
            "East - Conf. Semifinals": "conf_semis", "West Conf. Semifinals": "conf_semis",
            "East - Conf. Finals": "conf_finals", "West Conf. Finals": "conf_finals", "NBA Finals": "finals"}
    for label, name in want.items():
        assert S.round_of(label) == name


def test_the_schedule_must_hold_every_purchased_game():
    sched = pd.DataFrame({"game_id": ["a"], "game_type": ["playoff"], "game_label": ["NBA Finals"], "season": [2024],
                          "game_date": ["d"], "commence_time": ["t"], "home_team": ["A"], "away_team": ["B"]})
    assert S.postseason_games(sched, pd.DataFrame({"game_id": ["a"]})).phase.iloc[0] == "playoffs"
    with pytest.raises(RuntimeError):
        S.postseason_games(sched, pd.DataFrame({"game_id": ["a", "b"]}))


# ── impossible numbers ──────────────────────────────────────────────────────

def test_a_line_outside_its_markets_range_is_refused():
    t = pd.DataFrame({"market": "player_points", "line": [20.5, 99.5], "over_price": -110.0, "under_price": -110.0})
    kept, n = S.refuse_bad_rows(t, {"player_points": (0.5, 60.5)})
    assert list(kept.line) == [20.5] and n["line_outside_range"] == 1


def test_an_impossible_price_is_refused():
    t = pd.DataFrame({"market": "player_points", "line": 20.5, "over_price": [-40000.0, 40.0], "under_price": [30000.0, -110.0]})
    kept, n = S.refuse_bad_rows(t, {"player_points": (0.5, 60.5)})
    assert kept.empty and n["impossible_price"] == 2


def test_an_incoherent_two_way_quote_is_refused_and_a_one_sided_one_is_kept_for_the_rules_to_refuse():
    t = pd.DataFrame({"market": "player_points", "line": 20.5, "over_price": [200.0, -110.0], "under_price": [200.0, np.nan]})
    kept, n = S.refuse_bad_rows(t, {"player_points": (0.5, 60.5)})
    assert len(kept) == 1 and np.isnan(kept.under_price.iloc[0]) and n["incoherent_two_way"] == 1
    assert n["one_sided_not_decided_on"] == 1


# ── the placebo is a null on thin dates (lesson 2) ──────────────────────────

def _keys():
    return pd.DataFrame({"game_date": ["d1"] * 6 + ["d2"] * 2 + ["d3"] * 2, "real_market": "m", "season": 2024,
                         "round": ["finals"] * 6 + ["conf_finals"] * 4})


def test_a_thin_date_joins_the_other_thin_propositions_of_its_round():
    g = S.placebo_groups(_keys())
    assert g[0] == g[5] and g[6] == g[7] == g[8] == g[9] and g[0] != g[6]


def test_a_shuffle_stays_inside_its_group_and_keeps_every_value():
    g = S.placebo_groups(_keys())
    v = np.arange(10.0)
    for seed in (1, 2, 3):
        s = S.shuffled(v, g, seed)
        assert sorted(s[:6]) == sorted(v[:6]) and sorted(s[6:]) == sorted(v[6:])


def test_seeds_give_different_shuffles_and_the_same_seed_repeats():
    g = S.placebo_groups(_keys())
    v = np.arange(10.0)
    assert not np.array_equal(S.shuffled(v, g, 1), S.shuffled(v, g, 2))
    assert np.array_equal(S.shuffled(v, g, 7), S.shuffled(v, g, 7))
    assert S.PLACEBO_SEEDS == tuple(range(1, 201))


def _one_game_cell(n=6):
    """A real shape: one game on its date, n propositions priced by Pinnacle at near-even prices."""
    rows = []
    for i in range(n):
        rows.append({"game_id": f"G|{i}|player_points", "real_game": "G", "player_id": str(i),
                     "real_market": "player_points", "market": "totals", "side": "under", "book": "draftkings",
                     "line": 10.5, "price": -110.0, "season": 2026, "game_date": "2026-06-05", "T": "t", "lead_min": 54.0,
                     "phase": "playoffs", "round": "finals", "mu": np.nan, "p_home": np.nan, "model": S.RULE_ID, "p_push": 0.0})
    off = pd.DataFrame(rows)
    fair = np.array([0.60, 0.40, 0.44, 0.46, 0.45, 0.43])[:n]
    return off, fair


def test_on_a_one_game_date_the_placebo_bets_differ_from_the_real_bets():
    off, fair = _one_game_cell()
    p = S.MarketPricer(off, fair)
    real = S.qualifying(p.priced(), 0.0, "under")
    assert list(real.player_id) == ["0"]        # the one proposition the rule bets
    shares = [S.differing_share(real, S.qualifying(p.placebo(s), 0.0, "under")) for s in range(1, 41)]
    assert np.nanmean(shares) > 0.7


def test_the_projection_placebo_moves_the_mean_and_reprices_it():
    base_q = _card_q().iloc[[0]]
    q = pd.concat([base_q.assign(player_id=str(i)) for i in range(6)], ignore_index=True)
    means = pd.DataFrame({"game_id": "G", "player_id": [str(i) for i in range(6)],
                          **{f"mu_{m}": [3.0, 4.0, 5.0, 6.0, 7.0, 8.0] for m in pj.MARKETS}})
    off = S.card_offers(S.card_rows(q, clock=False), means, _inputs(), set(), _meta())
    p = S.ProjectionPricer(off)
    assert len(p.keys) == 6 and pd.Series(p.groups).nunique() == 1  # one (date, market) of six propositions
    base = p.priced()
    moved = [p.placebo(s) for s in range(1, 6)]
    assert any(not np.allclose(m.p_win, base.p_win) for m in moved)
    # every mean stays in play: the same six probabilities, only on other propositions
    assert all(np.allclose(sorted(m.p_win), sorted(base.p_win)) for m in moved)
    # a proposition's own line, price and side never move
    assert all((m.line.values == base.line.values).all() and (m.price.values == base.price.values).all() for m in moved)


def test_the_differing_share_counts_a_new_proposition_or_a_new_side():
    real = pd.DataFrame({"game_id": ["a", "b"], "side": ["under", "under"]})
    pl = pd.DataFrame({"game_id": ["a", "b", "c"], "side": ["under", "over", "under"]})
    assert S.differing_share(real, pl) == pytest.approx(2 / 3)


# ── the caps ────────────────────────────────────────────────────────────────

def _bets(rows):
    return pd.DataFrame([{"model": m, "ev": e, "player_id": p, "real_market": "player_steals", "side": "under",
                          "line": 1.5, "real_game": g, "game_date": d, "game_id": f"{g}|{p}|player_steals"}
                         for m, e, p, g, d in rows])


def test_the_caps_take_one_bet_a_game_strongest_by_each_models_own_percentile():
    # raw EV favours the projection; by its own table 0.03 is the rule's 70th percentile, 0.05 the
    # projection's 25th, so the rule's bet is the stronger
    b = _bets([(S.RULE_ID, 0.03, "1", "G", "d"), (S.PROJECTION_ID, 0.05, "2", "G", "d")])
    assert list(S.apply_caps(b)) == ["G|1|player_steals"]


def test_the_caps_allow_the_shipped_number_a_night():
    """The control is the shipped door's own choose(): four a night until 2026-11-04, six since."""
    from scripts.nba_props_card import MAX_NBA_PROP_BETS_PER_NIGHT as k
    n = k + 2
    b = _bets([(S.RULE_ID, 0.01 * i, str(i), f"G{i}", "d") for i in range(1, n + 1)])
    picks = S.apply_caps(b)
    assert len(picks) == k and f"G{n}|{n}|player_steals" in picks and "G1|1|player_steals" not in picks


def test_the_capped_frame_marks_the_written_propositions_with_their_sides():
    k = {"real_game": "G", "real_market": "player_steals", "market": "totals", "book": "draftkings", "line": 1.5,
         "price": -110.0, "season": 2024, "game_date": "d", "T": "t", "lead_min": 54.0, "phase": "playoffs",
         "round": "first_round", "mu": np.nan, "p_home": np.nan, "p_push": 0.0, "p_win": 0.5}
    a = pd.DataFrame([{**k, "game_id": "G|1|player_steals", "player_id": "1", "side": "under", "model": S.RULE_ID, "ev": 0.03}])
    b = pd.DataFrame([{**k, "game_id": "G|2|player_steals", "player_id": "2", "side": "over", "model": S.PROJECTION_ID,
                       "ev": 0.05, "side_pick": "over", "margin": 0.03},
                      {**k, "game_id": "G|2|player_steals", "player_id": "2", "side": "under", "model": S.PROJECTION_ID,
                       "ev": -0.2, "side_pick": "over", "margin": -0.22}])
    c = S.capped_frame(a, b)
    picked = S.qualifying(c, 1.0, S.SIDE_CARD, "capped")
    assert list(picked.game_id) == ["G|1|player_steals"] and list(picked.side) == ["under"]


# ── the run ─────────────────────────────────────────────────────────────────

def test_full_refuses_without_the_owners_switches(monkeypatch):
    for v in (S.GO_ENV, S.RESULTS_ENV, S.BETS_ENV):
        monkeypatch.delenv(v, raising=False)
    assert len(S.refuse_full()) == 3
    with pytest.raises(SystemExit):
        S.full(H.CACHE, S.work_dir())
    monkeypatch.setenv(S.GO_ENV, "1")
    monkeypatch.setenv(S.RESULTS_ENV, "x")
    monkeypatch.setenv(S.BETS_ENV, "y")
    assert S.refuse_full() == []


def test_the_registered_cells_are_the_rule_and_the_six_market_cells_at_their_shipped_floors():
    assert S.EXPECTED_CELLS == 1 + len(pj.CARD) == 7
    assert S.PM_FLOOR == 0.0
    assert {m: v[1] for m, v in pj.CARD.items()} == {
        "player_steals": 0.02, "player_rebounds": 0.01, "player_blocks_steals": 0.05, "player_blocks": 0.02,
        "player_rebounds_assists": 0.04, "player_threes": 0.04}
    assert S.PM_BANDS == [(-0.01, 0.0), (0.0, 0.01), (0.01, np.inf)]
    assert S.pj_bounds(0.04)[0] == pytest.approx((0.02, 0.04)) and np.isinf(S.pj_bounds(0.04)[-1][1])


def test_the_report_switch_reads_a_results_folder(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(S, "report", lambda p: seen.setdefault("p", p))
    S.main(["--report", str(tmp_path)])
    assert seen["p"] == tmp_path


def test_the_synthetic_checks_pass():
    assert S.synthetic_checks() == {"synthetic_checks": "pass"}

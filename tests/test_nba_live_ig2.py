"""The NBA in-play model (models/nba_live_ig2.py): the graded rule, live.

Each test is written from a rule in docs/nba_models_2026.md 7.1 / 7.3 or
docs/nba_search_ingame27.md section 3, on a synthetic game
(tests/_nba_live_synth.py) where that one rule is broken:
  * the artifact reproduces its golden grid (the graded code's own numbers);
  * FRESH: a point scored between a quote's stamp and its fetch's served time
    makes it ineligible, for the deciding quote and for its Pinnacle quote;
    Pinnacle more than 60 s away makes it ineligible;
  * the phase is read at the quote's own stamp; a live period with no newer
    play is live, not postgame; the half is no phase; a period whose first
    action has not been logged has not started;
  * rule 5 (first play 15+ min before the listed tip), rule 6 (a 45-minute
    clock jump), rules 3-4 (a deciding quote far from its Pinnacle pair);
  * a fetch with no eligible quote is not a decision; an eligible one that
    does not clear the cut is (and spends the rule); the -200 floor; the side
    is the model's even when its best price is below the floor;
  * a stamp seen in an earlier fetch is dropped;
  * the label agrees with the side and the HOME number (pick_integrity);
  * two bets that cannot both win.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from tests import _nba_live_synth as S
import models.nba_live_ig2 as M
from data.ingestors.nba_live_feed import plays_from_summary, rows_from_events, starters_from_summary


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


def lab():
    return M._lab()


EMPTY_HIST = pd.DataFrame(columns=["espn_id", "minutes", "game_date", "season"])


def pipeline(plays, books, fetched, known_after_s=45.0, tip=None):
    """The serving pipeline on one fetch: rows -> quotes -> plays known at
    fetched + wait -> prepare. Returns qt."""
    _G, _H, _D, L = lab()
    rows = pd.DataFrame(rows_from_events(S.events(books), fetched))
    rows["created_at"] = fetched.isoformat()
    summ = S.summary(plays, known_until=fetched + timedelta(seconds=known_after_s))
    got = plays_from_summary(summ, S.EVENT_ID, S.GAME_ID, 2027, S.GAME_DATE, "BOS", "NYK")
    pbp = pd.DataFrame(got[0])
    pl, wild = L.live_plays(pbp)
    assert not wild
    top = M.top_players(S.GAME_ID, S.EVENT_ID, starters_from_summary(summ, "BOS", False), EMPTY_HIST,
                        S.GAME_DATE, 2027)
    g = S.games_frame()
    if tip is not None:
        g["tip"] = pd.Timestamp(tip)
    q, _d, _n = M.fetch_quotes(rows, g, set())
    qt, _notes = M.prepare(q, pl, pbp, top, g)
    return qt


def q2_books(w, pin_dt=3, dk_spread=(-3.5, -105, -115), fd_spread=(-2.5, -120, 100), pin_spread=(-3.5, -110, -110)):
    stamp = w + timedelta(seconds=5)
    return [S.book("pinnacle", stamp - timedelta(seconds=pin_dt), h2h=(-150, 130), spread=pin_spread),
            S.book("draftkings", stamp, h2h=(-140, 120), spread=dk_spread),
            S.book("fanduel", stamp, h2h=(-145, 125), spread=fd_spread)]


SPREAD_Q12 = M.RULE_BY_ID[M.SPREAD_Q12]
ML_Q3 = M.RULE_BY_ID[M.ML_Q3]
SPREAD_Q3 = M.RULE_BY_ID[M.SPREAD_Q3]


# ─── the artifact ──────────────────────────────────────────────────────────────

def test_the_artifact_reproduces_its_golden_grid(art):
    """The loaded artifact gives the means, spreads, win chances, spread
    prices and priors the graded code computed when it was built."""
    G, H, _D, _L = lab()
    from scripts.build_nba_live_ig2_artifact import golden_frame
    g = art.raw["golden"]
    f = G.features(golden_frame())
    mean, sd = art.model.predict(f)
    np.testing.assert_allclose(mean, g["mean"], rtol=0, atol=1e-9)
    np.testing.assert_allclose(sd, g["sd"], rtol=0, atol=1e-9)
    np.testing.assert_allclose(G.p_home_from(mean, sd), g["p_home"], rtol=0, atol=1e-9)
    for row in g["spreads"]:
        i = row["state"]
        w, p = H.side_probs(np.array(["spreads"]), np.array([row["side"]]), np.array([row["line"]]),
                            mu=np.array([mean[i]]), sigma=np.array([sd[i]]))
        assert abs(w[0] - row["p_win"]) < 1e-9 and abs(p[0] - row["p_push"]) < 1e-9
    pri = [M.prior_margin(art, line, fa) for line, fa in g["closes"]]
    np.testing.assert_allclose(pri, g["prior_mu"], rtol=0, atol=1e-9)


def test_the_artifact_is_the_season_2027_fit_on_every_held_season(art):
    sm = art.raw["state_model"]
    assert sm["season"] == 2027 and art.model.S == 2027
    assert sm["train_seasons"] == [2021, 2022, 2023, 2024, 2025, 2026]
    assert list(sm["cols"]) == list(lab()[0].FEATURES)
    assert art.raw["model_ids"] == list(M.MODEL_IDS)


def test_an_artifact_of_another_kind_is_refused(art):
    bad = dict(art.raw, kind="something_else")
    with pytest.raises(ValueError):
        M.artifact_from_dict(bad)


# ─── freshness (record 7.1) ────────────────────────────────────────────────────

def test_a_fresh_quote_in_quarter_2_is_eligible_and_decides(art):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)              # the made shot at 7:00 of Q2
    qt = pipeline(plays, q2_books(w), w + timedelta(seconds=20))
    el = M.eligible_for(qt, SPREAD_Q12)
    assert set(el["book"]) == {"draftkings", "fanduel"}
    d = M.decide(el, SPREAD_Q12, art.models, mu_pre=2.0)
    assert d is not None and d.bet and d.pick["book"] == "fanduel" and d.pick["side"] == "away"
    assert M.eligible_for(qt, SPREAD_Q3).empty and M.eligible_for(qt, ML_Q3).empty


def test_a_point_after_the_stamp_makes_the_quote_ineligible(art):
    """The deciding books stamped at w+5; a basket logged at w+12, before the
    fetch was served at w+20, means their price predates the score."""
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    extra = [{"period": 2, "clock_s": 412.0, "wallclock": w + timedelta(seconds=12), "team": "A", "points": 2}]
    plays2 = S.build_plays(extra=extra)
    qt = pipeline(plays2, q2_books(w), w + timedelta(seconds=20))
    assert M.eligible_for(qt, SPREAD_Q12).empty
    assert M.decide(M.eligible_for(qt, SPREAD_Q12), SPREAD_Q12, art.models, mu_pre=2.0) is None


def test_a_point_after_pinnacles_stamp_alone_makes_the_pair_ineligible():
    """Pinnacle stamped 10 s before the deciding books; a basket between the
    two stamps leaves the deciding quotes fresh and Pinnacle's stale."""
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    books = q2_books(w, pin_dt=0)
    books[0] = S.book("pinnacle", w + timedelta(seconds=1), h2h=(-150, 130), spread=(-3.5, -110, -110))
    extra = [{"period": 2, "clock_s": 418.0, "wallclock": w + timedelta(seconds=3), "team": "A", "points": 1}]
    qt = pipeline(S.build_plays(extra=extra), books, w + timedelta(seconds=20))
    dk = qt[(qt["book"] == "draftkings") & (qt["market"] == "spreads")].iloc[0]
    assert dk["pts_since_stamp"] == 0 and dk["pin_pts_since"] > 0
    assert M.eligible_for(qt, SPREAD_Q12).empty


def test_pinnacle_more_than_60_seconds_away_makes_the_quote_ineligible():
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    books = q2_books(w)
    books[1] = S.book("draftkings", w + timedelta(seconds=5 + 62), h2h=(-140, 120), spread=(-3.5, -105, -115))
    books[2] = S.book("fanduel", w + timedelta(seconds=5 + 62), h2h=(-145, 125), spread=(-2.5, -120, 100))
    qt = pipeline(plays, books, w + timedelta(seconds=40 + 62))
    assert M.eligible_for(qt, SPREAD_Q12).empty


def test_the_wait_lets_a_late_published_basket_count():
    """The rule reads plays logged up to the served time. A basket logged at
    w+12 but published 30 s later is seen when the loop waits 45 s, missed
    when it reads at once; the wait is what makes the live read equal the
    grade's."""
    w = S.wall_of(S.build_plays(), 2, 420.0)
    extra = [{"period": 2, "clock_s": 412.0, "wallclock": w + timedelta(seconds=12), "team": "A", "points": 2}]
    plays = S.build_plays(extra=extra)
    fetched = w + timedelta(seconds=20)
    # read at once: only plays logged by the fetch are known -- this simulates
    # the basket not yet published by keeping the read at w+11
    early = pipeline(plays, q2_books(w), fetched, known_after_s=-9)
    late = pipeline(plays, q2_books(w), fetched, known_after_s=45)
    assert not M.eligible_for(early, SPREAD_Q12).empty
    assert M.eligible_for(late, SPREAD_Q12).empty


# ─── phases and the live game's bounds ─────────────────────────────────────────

def test_a_quote_after_the_newest_play_of_a_live_period_is_live_not_postgame():
    """On a game in progress the newest play is not the end of the game."""
    _G, _H, D, L = lab()
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    fetched = w + timedelta(seconds=20)
    summ = S.summary(plays, known_until=w)            # nothing logged after w
    pbp = pd.DataFrame(plays_from_summary(summ, S.EVENT_ID, S.GAME_ID, 2027, S.GAME_DATE, "BOS", "NYK")[0])
    pl, _ = L.live_plays(pbp)
    q = pd.DataFrame({"game_id": [S.GAME_ID], "stamp": [pd.Timestamp(fetched)], "label": ["in_play"]})
    assert D.label_phase(q, M.live_bounds(pl), "stamp").iloc[0] == "live"
    assert D.label_phase(q, D.phase_bounds(pl), "stamp").iloc[0] == "postgame"   # the finished-game reading


def test_halftime_is_no_phase_even_before_quarter_3_has_an_action_play():
    """ESPN logs quarter 3's 12:00 substitution as quarter 2 ends. Read as a
    finished game it would start quarter 3 at once and call the half 'live
    quarter 3'; the live bounds keep it the half until a real play."""
    _G, _H, D, L = lab()
    plays = S.build_plays()
    end2 = next(p for p in plays if p["period"]["number"] == 2 and p["type"]["text"] == "End Period")
    t_end2 = pd.Timestamp(end2["wallclock"])
    stamp = t_end2 + pd.Timedelta(minutes=5)
    summ = S.summary(plays, known_until=stamp.to_pydatetime())
    pbp = pd.DataFrame(plays_from_summary(summ, S.EVENT_ID, S.GAME_ID, 2027, S.GAME_DATE, "BOS", "NYK")[0])
    pl, _ = L.live_plays(pbp)
    q = pd.DataFrame({"game_id": [S.GAME_ID], "stamp": [stamp], "label": ["in_play"]})
    assert D.label_phase(q, M.live_bounds(pl), "stamp").iloc[0] == "halftime"
    assert D.label_phase(q, D.phase_bounds(pl), "stamp").iloc[0] != "halftime"   # what the fix is for


def test_live_bounds_equal_the_finished_game_once_final():
    _G, _H, D, L = lab()
    plays = S.build_plays()
    pbp = pd.DataFrame(plays_from_summary(S.summary(plays), S.EVENT_ID, S.GAME_ID, 2027, S.GAME_DATE,
                                          "BOS", "NYK")[0])
    pl, _ = L.live_plays(pbp)
    a = M.live_bounds(pl, final_games={S.GAME_ID}).reset_index(drop=True)
    b = D.phase_bounds(pl).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_a_quarter_3_quote_feeds_the_quarter_3_rules_only(art):
    plays = S.build_plays()
    w = S.wall_of(plays, 3, 420.0)
    qt = pipeline(plays, q2_books(w), w + timedelta(seconds=20))
    assert M.eligible_for(qt, SPREAD_Q12).empty
    assert not M.eligible_for(qt, SPREAD_Q3).empty and not M.eligible_for(qt, ML_Q3).empty


# ─── the clock rules and the impossible numbers ───────────────────────────────

def test_rule_5_a_first_play_15_minutes_before_the_listed_tip_refuses_the_game():
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    # the listed tip 21 minutes after the first play (an ESPN clock an hour early is the real case)
    qt = pipeline(plays, q2_books(w), w + timedelta(seconds=20), tip=S.FIRST + timedelta(minutes=16))
    assert qt.empty or M.eligible_for(qt, SPREAD_Q12).empty
    ok = pipeline(plays, q2_books(w), w + timedelta(seconds=20), tip=S.FIRST + timedelta(minutes=14))
    assert not M.eligible_for(ok, SPREAD_Q12).empty


def test_rule_6_a_45_minute_clock_jump_refuses_the_game():
    w = S.wall_of(S.build_plays(), 2, 420.0)
    # every play from index 10 (in quarter 1) logged 46 minutes later
    jumped = S.build_plays(shift_after=(10, timedelta(minutes=46)))
    w_j = S.wall_of(jumped, 2, 420.0)
    qt = pipeline(jumped, q2_books(w_j), w_j + timedelta(seconds=20))
    assert M.eligible_for(qt, SPREAD_Q12).empty
    small = S.build_plays(shift_after=(10, timedelta(minutes=44)))
    w_s = S.wall_of(small, 2, 420.0)
    assert not M.eligible_for(pipeline(small, q2_books(w_s), w_s + timedelta(seconds=20)), SPREAD_Q12).empty
    assert w is not None


def test_rule_3_a_deciding_spread_more_than_6_points_from_pinnacle_is_dropped():
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    qt = pipeline(plays, q2_books(w, fd_spread=(+4.0, -110, -110)), w + timedelta(seconds=20))
    assert set(M.eligible_for(qt, SPREAD_Q12)["book"]) == {"draftkings"}    # FanDuel 7.5 from -3.5


def test_rule_1_a_price_between_minus_100_and_plus_100_is_dropped():
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    # +95 / -105 sums to a coherent 1.02, so only rule 1 can drop it
    qt = pipeline(plays, q2_books(w, fd_spread=(-2.5, 95, -105)), w + timedelta(seconds=20))
    assert "fanduel" not in set(M.eligible_for(qt, SPREAD_Q12)["book"])
    ok = pipeline(plays, q2_books(w, fd_spread=(-2.5, 105, -115)), w + timedelta(seconds=20))
    assert "fanduel" in set(M.eligible_for(ok, SPREAD_Q12)["book"])


# ─── the decision ──────────────────────────────────────────────────────────────

def test_no_eligible_quote_is_not_a_decision_but_a_miss_of_the_cut_is(art):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    qt = pipeline(plays, q2_books(w, fd_spread=(-3.5, -112, -108)), w + timedelta(seconds=20))
    el = M.eligible_for(qt, SPREAD_Q12)
    assert M.decide(el.iloc[0:0], SPREAD_Q12, art.models, mu_pre=2.0) is None
    d = M.decide(el, SPREAD_Q12, art.models, mu_pre=2.0, cut=5.0)
    assert d is not None and not d.bet                      # decided: the rule is spent


def test_the_floor_refuses_a_price_shorter_than_minus_200(art):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    qt = pipeline(plays, q2_books(w), w + timedelta(seconds=20))
    el = M.eligible_for(qt, SPREAD_Q12)
    d = M.decide(el, SPREAD_Q12, art.models, mu_pre=2.0)
    assert d.bet and d.pick["price"] == 100
    worse = M.decide(el, SPREAD_Q12, art.models, mu_pre=2.0, floor=101.0)
    assert not worse.bet


def test_the_side_is_the_models_even_when_its_best_price_is_under_the_floor(art):
    """G.with_side_pick chooses the side before the floor: if the favoured
    side's best offer is shorter than the floor, the other side is not bet."""
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    qt = pipeline(plays, q2_books(w), w + timedelta(seconds=20))
    el = M.eligible_for(qt, SPREAD_Q12)
    cand = M.priced_offers(el.assign(mu_pre=2.0), art.models)
    side = cand["side_pick"].iloc[0]
    best = cand[cand["side"] == side]["price"].max()
    d = M.decide(el, SPREAD_Q12, art.models, mu_pre=2.0, floor=best + 1, cut=-1.0)
    assert not d.bet


def test_a_missing_prior_is_a_refusal_never_zero(art):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    el = M.eligible_for(pipeline(plays, q2_books(w), w + timedelta(seconds=20)), SPREAD_Q12)
    d = M.decide(el, SPREAD_Q12, art.models, mu_pre=None)
    assert d is not None and not d.bet and "prior" in d.reason


def test_a_stamp_seen_in_an_earlier_fetch_is_dropped():
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    seen: set = set()
    for i, fetched in enumerate((w + timedelta(seconds=20), w + timedelta(seconds=80))):
        rows = pd.DataFrame(rows_from_events(S.events(q2_books(w)), fetched))
        rows["created_at"] = fetched.isoformat()
        q, _d, notes = M.fetch_quotes(rows, S.games_frame(), seen)
        assert (len(q) == 6) if i == 0 else (len(q) == 0 and notes["rows_stamp_seen_in_earlier_fetch"] == 6)


def test_the_platform_ev_gate_never_reads_below_the_rules_ev():
    """model_probability is P(win | no push): its config.expected_value is
    the rule's EV / (1 - p_push), never lower."""
    import config
    for p_win, p_push, price in ((0.5, 0.06, -110), (0.55, 0.0, -120), (0.47, 0.05, 105)):
        d = M.american_to_decimal(price)
        ev_rule = p_win * (d - 1) - (1 - p_win - p_push)
        ev_gate = config.expected_value(M.prob_no_push(p_win, p_push), price)
        assert ev_gate >= ev_rule - 1e-12


# ─── words and numbers ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("rule,side,line,label", [
    (SPREAD_Q12, "home", -4.5, "BOS -4.5 (live)"),
    (SPREAD_Q12, "away", -4.5, "NYK +4.5 (live)"),
    (SPREAD_Q3, "away", 3.0, "NYK -3 (live)"),
    (ML_Q3, "away", None, "NYK ML (live)"),
])
def test_the_label_agrees_with_the_side_and_the_home_number(rule, side, line, label):
    from tracking.pick_integrity import pick_problems
    got = M.pick_label(rule, side, line, "BOS", "NYK")
    assert got == label
    assert pick_problems(got, side, line, rule.model_id, "BOS", "NYK") == []
    if line is not None:     # the number un-flipped is caught
        wrong = f"{'BOS' if side == 'home' else 'NYK'} {line:+g} (live)" if side == "away" else None
        if wrong:
            assert pick_problems(wrong, side, line, rule.model_id, "BOS", "NYK")


@pytest.mark.parametrize("a,b,cannot", [
    ({"market": "h2h", "side": "home", "line": None}, {"market": "h2h", "side": "away", "line": None}, True),
    ({"market": "spreads", "side": "home", "line": -3.5}, {"market": "spreads", "side": "away", "line": -6.5}, False),
    ({"market": "spreads", "side": "home", "line": -6.5}, {"market": "spreads", "side": "away", "line": -3.5}, True),
    ({"market": "h2h", "side": "away", "line": None}, {"market": "spreads", "side": "home", "line": -2.5}, True),
    ({"market": "h2h", "side": "home", "line": None}, {"market": "spreads", "side": "away", "line": -2.5}, False),
    ({"market": "h2h", "side": "home", "line": None}, {"market": "spreads", "side": "away", "line": 0.5}, True),
    # home +0.5 wins on a margin of 0 or more, away -0.5 on 0 or less: only a
    # tie wins both, and a game never ends tied
    ({"market": "spreads", "side": "home", "line": 0.5}, {"market": "spreads", "side": "away", "line": -0.5}, True),
])
def test_two_bets_that_cannot_both_win(a, b, cannot):
    """Home -6.5 needs a 7-point win, away +3.5 a loss by 3 or less: never
    both. Home ML and away -0.5 (home +0.5) cannot both win either: overtime
    leaves no tie."""
    assert M.cannot_both_win(a, b) is cannot
    assert M.cannot_both_win(b, a) is cannot


def test_an_ev_tie_goes_to_the_earlier_book_whatever_the_floating_point_noise():
    """Two books at the same number and price have the same EV; the tie goes
    to the earlier book in BEST_LINE_BOOKMAKERS (H.choose). In a one-game frame
    the later book's EV can come out 4e-16 higher, and the noise then chose the
    book (3 of 1,753 graded bets, independent review). EV is rounded first."""
    cand = pd.DataFrame([
        {"game_id": "g", "market": "spreads", "side": "away", "side_pick": "away", "book": "draftkings",
         "line": -2.5, "price": -110.0, "p_win": 0.56, "p_push": 0.0, "ev": 0.069090909090909},
        {"game_id": "g", "market": "spreads", "side": "away", "side_pick": "away", "book": "betrivers",
         "line": -2.5, "price": -110.0, "p_win": 0.56, "p_push": 0.0, "ev": 0.069090909090909 + 4e-16},
    ])
    b = M.choose_bets(cand, 0.05, -200.0)
    assert list(b["book"]) == ["draftkings"]

"""The tennis match-winner decision (models/tennis_moneyline_shop.py)."""
import pytest

from models import tennis_common as tc
from models import tennis_moneyline_shop as ms

ATP = "tennis_atp_paris_masters"
SLAM = "tennis_atp_us_open"
WTA = "tennis_wta_finals"


def test_power_devig_sums_to_one_and_gives_the_longshot_less():
    pa, pb = ms.power_devig(-400, 300)
    assert pa + pb == pytest.approx(1.0, abs=1e-9)
    ma, mb = tc.no_vig_pair(-400, 300)
    assert pb < mb and pa > ma


def test_power_devig_of_a_fair_pair_is_the_pair():
    pa, pb = ms.power_devig(100, 100)
    assert pa == pytest.approx(0.5) and pb == pytest.approx(0.5)


def test_best_of_five_only_at_the_mens_slams():
    assert ms.best_of(SLAM) == 5
    assert ms.best_of(ATP) == 3
    assert ms.best_of("tennis_wta_us_open") == 3


def test_tours():
    assert ms.tour_of(ATP) == "ATP" and ms.tour_of(WTA) == "WTA"
    assert ms.tour_of("basketball_nba") is None


@pytest.mark.parametrize("book,expected", [
    ("draftkings", 0.01),                    # the retiree's bet is void: stake back
    ("fanduel", 0.0),                        # the retiree loses: nothing
    ("betmgm", 0.0),
    ("williamhill_us", 0.01 - 0.01 * 1.5),   # every bet void: stake back, and a win lost
    ("betrivers", 0.01 - 0.01 * 1.5),        # rule not read: graded as every bet void
])
def test_retirement_term_follows_the_books_own_rule(book, expected):
    assert ms.retirement_term(book, 0.01, 2.5) == pytest.approx(expected)


def test_decide_takes_the_best_ev_across_books_and_sides():
    ref = ms.Quote("pinnacle", -150, 135)
    quotes = [ms.Quote("fanduel", -160, 150), ms.Quote("betmgm", -155, 145)]
    c = ms.decide(quotes, ref, ATP)
    pa, pb = ms.power_devig(-150, 135)
    assert c.side == "b" and c.book == "fanduel" and c.price == 150
    assert c.ev == pytest.approx(pb * 2.5 - 1)
    assert c.bet is (c.ev >= ms.EV_MIN)


def test_decide_adds_draftkings_retirement_option():
    ref = ms.Quote("pinnacle", -150, 135)
    c = ms.decide([ms.Quote("draftkings", -160, 150)], ref, WTA)
    pa, pb = ms.power_devig(-150, 135)
    assert c.ev == pytest.approx(pb * 2.5 - 1 + ms.RETIRE_RATE[("WTA", 3)])


def test_decide_skips_a_price_below_the_floor_and_an_ev_at_the_cap():
    ref = ms.Quote("pinnacle", -700, 500)
    # -520 is below the floor; +700 against a fair ~+560 is EV above the cap
    c = ms.decide([ms.Quote("fanduel", -520, 700)], ref, ATP)
    assert c.bet is False and c.reason == "no_quote_in_range"


def test_decide_reports_a_quote_below_the_cut():
    ref = ms.Quote("pinnacle", -110, -110)
    c = ms.decide([ms.Quote("fanduel", -115, -105)], ref, ATP)
    assert c.bet is False and c.reason == "below_ev_min"


def test_decide_ignores_books_a_pick_may_not_name():
    ref = ms.Quote("pinnacle", -110, -110)
    c = ms.decide([ms.Quote("bovada", 150, 150), ms.Quote("betparx", 150, 150)], ref, ATP)
    assert c.reason == "no_decidable_quote"


def test_decide_needs_a_reference_and_a_tennis_key():
    q = [ms.Quote("fanduel", -110, -110)]
    assert ms.decide(q, None, ATP) is None
    assert ms.decide(q, ms.Quote("pinnacle", -110, -110), "basketball_nba") is None


def test_one_model_per_tour():
    assert ms.MODEL_IDS == {"ATP": "atp_moneyline_shop", "WTA": "wta_moneyline_shop"}

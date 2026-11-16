"""Discord names the book as a link to the bet the app already opens.

The URL is fillBetslipLink plus, for BetMGM, the sportsapp path on the
www.<state> host the app's alternate already builds. Massachusetts, because
that is the state the posts are read from. No request leaves the process.
"""
from __future__ import annotations

import tracking.book_slip_links as links
from tracking.book_slip_links import discord_book_target, fill_betslip_link
from tracking.discord_notifier import (
    _booked_price, _free_pick_embed, _picks_embed, _signal_field,
)


DK = "https://sportsbook.draftkings.com/?outcomes=0HC84998421N1950_1"
FD = "https://sportsbook.fanduel.com/addToBetslip?marketId=42.579972737&selectionId=484735"
MGM = ("https://sports.{state}.betmgm.com/en/sports"
       "?options=19976337-1562536174-2307719716&type=Single")
MGM_MA = ("https://www.ma.betmgm.com/en/sportsapp/sports"
          "?options=19976337-1562536174-2307719716&type=Single")
CZR = ("https://sportsbook.caesars.com/us/{state}/bet/betslip"
       "?selectionIds=00089d98-6c2a-3493-920d-b8fdd3b7c660")
RIVERS = ("https://{state}.betrivers.com/?page=sportsbook"
          "#event/1027397927?coupon={pickType}|4372845443|{wagerAmount}")
ROCK = "https://app.hardrock.bet/?deep_link_value=betslip/1006158484898709903"
ESPN = ("https://sportsbook.thescore.bet/"
        "?market_selection_id[0]=f885f2f3-ff1e-405c-854f-71f6234a56bc")


def _sig(**over):
    base = {
        "label": "BOS @ NYK Under 220.5", "sport": "NBA",
        "model_id": "nba_total_luck", "dk_odds": -110.0, "kelly": 0.02,
        "home": "NYK", "away": "BOS", "commence": None, "posted_at": None,
        "bet_link": DK,
    }
    base.update(over)
    return base


def test_fill_matches_the_app_for_the_stored_shapes():
    """The same strings verify_book_links.ts pins, filled with Massachusetts."""
    assert fill_betslip_link(DK, None) == DK
    assert fill_betslip_link(FD, None) == FD
    assert fill_betslip_link(MGM, None) is None
    assert fill_betslip_link(MGM, "MA") == (
        "https://sports.ma.betmgm.com/en/sports"
        "?options=19976337-1562536174-2307719716&type=Single")
    assert "/us/ma/bet/betslip" in fill_betslip_link(CZR, "ma")
    assert fill_betslip_link(RIVERS, "ma") == (
        "https://ma.betrivers.com/?page=sportsbook"
        "#event/1027397927?coupon=single|4372845443|")
    assert fill_betslip_link("NaN", "ma") is None
    assert fill_betslip_link("https://x.example/{foo}/bet", "ma") is None


def test_each_book_with_an_outcome_id_is_a_slip():
    cases = {
        "DraftKings": (_sig(), DK),
        "FanDuel": (_sig(best_book="fanduel", best_odds=-105,
                         best_bet_link=FD), FD),
        "BetMGM": (_sig(best_book="betmgm", best_odds=-105, best_bet_link=MGM),
                   MGM_MA),
        "Caesars": (_sig(best_book="williamhill_us", best_odds=-105,
                         best_bet_link=CZR),
                    "https://sportsbook.caesars.com/us/ma/bet/betslip"
                    "?selectionIds=00089d98-6c2a-3493-920d-b8fdd3b7c660"),
        "BetRivers": (_sig(best_book="betrivers", best_odds=-105,
                           best_bet_link=RIVERS),
                      "https://ma.betrivers.com/?page=sportsbook"
                      "#event/1027397927?coupon=single|4372845443|"),
        "Hard Rock Bet": (_sig(best_book="hardrockbet", best_odds=-105,
                               best_bet_link=ROCK), ROCK),
        "ESPN BET": (_sig(best_book="espnbet", best_odds=100, best_bet_link=ESPN),
                     ESPN),
    }
    for name, (sig, url) in cases.items():
        got, kind = discord_book_target(sig, name)
        assert kind == "slip", name
        assert got == url, name


def test_a_new_jersey_host_is_rewritten_to_massachusetts():
    nj = MGM.replace("{state}", "nj")
    url, kind = discord_book_target(
        _sig(best_book="betmgm", best_odds=-105, best_bet_link=nj), "BetMGM")
    assert kind == "slip"
    assert url == MGM_MA
    caesars_nj = CZR.replace("{state}", "nj")
    url, kind = discord_book_target(
        _sig(best_book="williamhill_us", best_odds=-105, best_bet_link=caesars_nj),
        "Caesars")
    assert kind == "slip" and "/us/ma/" in url and "/us/nj/" not in url


def test_a_soft_book_card_opens_that_books_stored_link():
    """Wind and opener rows name FanDuel while the link sits on dk_bet_link."""
    sig = _sig(best_book=None, best_odds=None, decision_book="fanduel",
               bet_link=FD)
    url, kind = discord_book_target(sig, "FanDuel")
    assert kind == "slip" and url == FD


def test_a_draftkings_slip_is_not_handed_to_fanduel():
    """The row stores DraftKings' link in dk_bet_link even when FanDuel decided."""
    sig = _sig(best_book="fanduel", best_odds=-105, best_bet_link=None,
               decision_book="fanduel", bet_link=DK)
    url, kind = discord_book_target(sig, "FanDuel")
    assert kind == "page"
    assert url == "https://sportsbook.fanduel.com/"
    assert "draftkings" not in url


def test_a_fanduel_slip_is_not_handed_to_draftkings():
    sig = _sig(best_book="fanduel", best_odds=-115, best_bet_link=FD)
    url, kind = discord_book_target(sig, "DraftKings")
    assert kind == "slip" and url == DK


def test_a_regional_fanduel_host_is_not_a_slip():
    regional = "https://nj.sportsbook.fanduel.com/addToBetslip?marketId=1&selectionId=2"
    url, kind = discord_book_target(
        _sig(best_book="fanduel", best_odds=-105, best_bet_link=regional),
        "FanDuel")
    assert kind == "page"
    assert url == "https://sportsbook.fanduel.com/"


def test_fanatics_and_betparx_have_no_outcome_link():
    fan, fan_kind = discord_book_target(
        _sig(best_book="fanatics", best_odds=-105, best_bet_link="NaN"),
        "Fanatics")
    assert fan_kind == "page" and fan == "https://sportsbook.fanatics.com/"
    parx, parx_kind = discord_book_target(
        _sig(best_book="betparx", best_odds=-105, best_bet_link=None),
        "betPARX")
    assert parx_kind == "page" and parx == "https://www.betparx.com/"


def test_an_unknown_book_stays_plain_text():
    url, kind = discord_book_target(
        _sig(best_book="fliff", best_odds=-105, best_bet_link=None), "Fliff")
    assert url is None and kind == "plain"


def test_a_broken_link_does_not_raise_and_the_price_still_renders():
    class Boom(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("https://discord.com/api/webhooks/secret")

    url, kind = discord_book_target(Boom(x=1), "DraftKings")
    assert url is None and kind == "plain"
    text = _booked_price({"bet_link": DK}, -110, "DraftKings")
    assert text.startswith("-110 @ [DraftKings](")

    def explode(*_a, **_k):
        raise RuntimeError("webhook")

    links.discord_book_target = explode
    try:
        field = _signal_field(_sig())
    finally:
        links.discord_book_target = discord_book_target
    assert "-110 @ DraftKings" in field["value"]
    assert "webhook" not in field["value"]
    assert "](" not in field["value"].split("\n")[-1]


def test_the_price_line_is_not_one_code_span():
    field = _signal_field(_sig(best_book="fanduel", best_odds=-105,
                               best_bet_link=FD))
    price = field["value"].split("\n")[-1]
    assert price.startswith(
        "-105 @ [FanDuel](https://sportsbook.fanduel.com/addToBetslip")
    assert not price.startswith("`")
    assert "**1" in price


def test_the_score_link_stays_on_the_matchup_line():
    field = _signal_field(_sig(
        sport="NCAAB", home="Louisville", away="UConn",
        game_date="2026-11-16", label="UConn @ Louisville under 122.5",
        best_book="fanduel", best_odds=-105, best_bet_link=FD,
    ), slate_date="2026-11-16")
    matchup, price = field["value"].split("\n", 1)
    assert matchup.startswith(
        "[UConn @ Louisville](https://www.espn.com/mens-college-basketball/")
    assert price.startswith("-105 @ [FanDuel](")
    assert field["name"] == "UConn @ Louisville under 122.5"
    embed = _picks_embed("NCAAB", [_sig(
        sport="NCAAB", home="Louisville", away="UConn",
        game_date="2026-11-16", label="UConn @ Louisville under 122.5",
        best_book="fanduel", best_odds=-105, best_bet_link=FD,
    )], "2026-11-16")
    assert "](" not in embed["title"]
    assert "](" not in embed["fields"][0]["name"]


def test_the_free_pick_and_a_live_field_use_the_same_link():
    free = _free_pick_embed(_sig(
        label="BOS @ NYK Under 220.5", lock_key="k", posted_at=None,
        commence="2026-11-16T00:00:00Z",
    ), "2026-11-16")
    assert "-110 @ [DraftKings](" + DK + ")" in free["fields"][0]["value"]
    assert "](" not in free["title"]
    live = _signal_field(_sig(live=True, posted_at="2026-11-16T18:00:00Z"))
    assert "-110 @ [DraftKings](" + DK + ")" in live["value"]


def test_a_link_that_would_not_fit_is_dropped_and_the_pick_still_renders(monkeypatch):
    from tracking import discord_notifier as dn
    monkeypatch.setattr(dn, "_FIELD_VALUE_MAX", 80)
    field = _signal_field(_sig())
    assert len(field["value"]) <= 80
    assert "-110 @ DraftKings" in field["value"]
    assert "](http" not in field["value"]


def test_every_pick_producer_selects_the_link_it_renders():
    import inspect
    from tracking import discord_notifier as dn
    for name in ("_new_signals", "_locked_signals", "_free_pick_candidates",
                 "_new_live_signals"):
        src = inspect.getsource(getattr(dn, name))
        assert "dk_bet_link" in src and "best_bet_link" in src, name
    void = inspect.getsource(dn._void_rows_sql)
    assert "p.dk_bet_link" in void and "p.best_bet_link" in void


def test_the_module_does_not_call_the_network():
    src = open(links.__file__, encoding="utf-8").read()
    assert "requests" not in src
    assert "urlopen" not in src

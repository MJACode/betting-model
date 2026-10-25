"""Pick labels name the bet. The book is a column.

Matt, 2026-10-23: Discord matches the simple names. A new label keeps the
team or player, the side and the line, and drops "(Opener … vs Pinnacle,
BOOK)", "(Wind N mph, BOOK)" and "(BOOK)". Rows already stored keep the
old text, so every reader still parses it.

Nothing here posts, writes, or grades a live pick.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import discord_notifier as dn  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402
from tracking import push_notifier as push  # noqa: E402
from tracking import x_publisher as xp  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

OLD_OPENER = "TEN @ NYG — NYG -1 (Opener +2 vs Pinnacle, MGM) · 1.96u · NEW 0m"
NEW_OPENER = "TEN @ NYG — NYG -1 · 1.96u · NEW 0m"
OLD_WIND = "NYJ @ MIA Under 43.5 (Wind 14 mph, FD) · 1.00u"
NEW_WIND = "NYJ @ MIA Under 43.5 · 1.00u"
OLD_PROP = "Jadarian Price Over 1.5 Rec (FD)"
NEW_PROP = "Jadarian Price Over 1.5 Rec"
OLD_WNBA = "A'ja Wilson Over 21.5 Pts (DK)"
NEW_WNBA = "A'ja Wilson Over 21.5 Pts"


def _sig(**kw):
    base = {
        "sport": "NFL", "dk_odds": -105.0, "kelly": 0.02,
        "home": "NYG", "away": "TEN", "commence": None, "posted_at": None,
        "best_book": None, "best_odds": None,
    }
    base.update(kw)
    return base


def test_an_old_label_still_names_its_book():
    assert dn.book_for_pick(_sig(
        model_id="nfl_opener_spread", label=OLD_OPENER)) == "BetMGM"
    assert dn.book_for_pick(_sig(
        model_id="nfl_wind_totals", label=OLD_WIND, dk_odds=-110.0)) == "FanDuel"
    # Master did not parse a prop suffix. The price line stayed DraftKings.
    assert dn.book_for_pick(_sig(
        model_id="nfl_prop_market", label=OLD_PROP, dk_odds=-120.0)) == "DraftKings"
    assert dn.book_for_pick(_sig(
        model_id="wnba_prop_market", label=OLD_WNBA, dk_odds=-105.0)) == "DraftKings"
    # An abbreviation the map does not know is shown as written.
    assert dn.book_for_pick(_sig(
        model_id="nfl_wind_totals",
        label="NYJ @ MIA Under 43.5 (Wind 14 mph, XYZ) · 1.00u")) == "XYZ"
    assert dn.book_for_pick(_sig(
        model_id="nfl_prop_market", label="A Player Over 1.5 Rec (fliff)",
        dk_odds=110.0)) == "DraftKings"


def test_a_parenthesis_that_is_not_a_book_is_not_a_book():
    assert dn.book_for_pick(_sig(
        model_id="mlb_f5_moneyline", label="NYY ML (F5)",
        dk_odds=-130.0)) == "DraftKings"
    assert dn.book_for_pick(_sig(
        model_id="nhl_moneyline", label="Boston Bruins (Regulation)",
        dk_odds=-140.0)) == "DraftKings"


def test_a_new_label_reads_the_column_and_only_when_it_is_that_price():
    taken = _sig(model_id="nfl_opener_spread", label=NEW_OPENER,
                 decision_book="betmgm", decision_odds_raw=-105.0)
    assert dn.book_for_pick(taken) == "BetMGM"
    # A decision at a different number must not rename dk_odds.
    other = _sig(model_id="mlb_spread_market", label="BOS +1.5",
                 dk_odds=-110.0, decision_book="fanduel",
                 decision_odds_raw=-105.0)
    assert dn.book_for_pick(other) == "DraftKings"
    # No column and no parenthesis: the platform default, and only with a price.
    assert dn.book_for_pick(_sig(
        model_id="nfl_wind_totals", label=NEW_WIND)) == "DraftKings"
    assert dn.book_for_pick(_sig(
        model_id="nfl_wind_totals", label=NEW_WIND, dk_odds=None)) is None
    # An explicit book still wins.
    assert dn.book_for_pick(_sig(
        book="fd", decision_book="draftkings", decision_odds_raw=-105.0,
        label=NEW_OPENER, model_id="nfl_opener_spread")) == "FanDuel"
    # A prop whose decision price is a different number does not rename dk_odds.
    assert dn.book_for_pick(_sig(
        model_id="nfl_prop_market", label=NEW_PROP, dk_odds=-120.0,
        decision_book="fanduel", decision_odds_raw=-105.0)) == "DraftKings"


def test_the_discord_embed_names_the_book_and_not_the_annotation():
    opener = _sig(model_id="nfl_opener_spread", label=NEW_OPENER,
                  decision_book="betmgm", decision_odds_raw=-105.0)
    wind = _sig(model_id="nfl_wind_totals", label=NEW_WIND,
                home="MIA", away="NYJ", dk_odds=-110.0,
                decision_book="fanduel", decision_odds_raw=-110.0)
    embed = dn._picks_embed("NFL", [opener, wind], "2026-10-23")
    names = [f["name"] for f in embed["fields"]]
    assert names == [NEW_OPENER, NEW_WIND]
    blob = json.dumps(embed)
    assert "Pinnacle" not in blob
    assert "Opener" not in blob
    assert "Wind" not in blob
    assert "@ BetMGM" in embed["fields"][0]["value"]
    assert "@ FanDuel" in embed["fields"][1]["value"]
    # A stored opener label still puts BetMGM on the price line.
    old = dn._signal_field(_sig(model_id="nfl_opener_spread", label=OLD_OPENER))
    assert old["name"] == OLD_OPENER
    assert "@ BetMGM" in old["value"]


def test_the_line_check_passes_for_both_label_shapes():
    assert pick_problems(OLD_OPENER, "home", -1.0, "nfl_opener_spread",
                         home="NYG", away="TEN") == []
    assert pick_problems(NEW_OPENER, "home", -1.0, "nfl_opener_spread",
                         home="NYG", away="TEN") == []
    assert pick_problems(OLD_WIND, "under", 43.5, "nfl_wind_totals",
                         home="MIA", away="NYJ") == []
    assert pick_problems(NEW_WIND, "under", 43.5, "nfl_wind_totals",
                         home="MIA", away="NYJ") == []
    assert pt._bet_price_and_book(
        "nfl_opener_spread", -105.0, None, None, OLD_OPENER) == (-105.0, "betmgm")
    assert pt._bet_price_and_book(
        "nfl_opener_spread", -105.0, -105.0, "betmgm", NEW_OPENER) == (-105.0, "betmgm")
    assert pt._bet_price_and_book(
        "nfl_wind_totals", -110.0, None, None, OLD_WIND) == (-110.0, "fanduel")
    assert pt._bet_price_and_book(
        "nfl_wind_totals", -110.0, -110.0, "fanduel", NEW_WIND) == (-110.0, "fanduel")
    assert pt._bet_price_and_book(
        "nfl_prop_market", -120.0, None, None, OLD_PROP) == (-120.0, "fanduel")
    assert pt._bet_price_and_book(
        "nfl_prop_market", -120.0, -120.0, "fanduel", NEW_PROP) == (-120.0, "fanduel")
    assert pt._bet_price_and_book(
        "wnba_prop_market", -105.0, None, None, OLD_WNBA) == (-105.0, "draftkings")
    assert pt._bet_price_and_book(
        "wnba_prop_market", -105.0, -105.0, "draftkings", NEW_WNBA) == (
            -105.0, "draftkings")


def test_x_names_the_book_the_soft_price_came_from():
    """A new label no longer carries FD or MGM. The tweet has to."""
    wind = xp._publish_price(_sig(
        model_id="nfl_wind_totals", label=NEW_WIND, dk_odds=-110.0,
        decision_book="fanduel", decision_odds_raw=-110.0))
    assert wind == (-110.0, "FanDuel")
    opener = xp._publish_price(_sig(
        model_id="nfl_opener_spread", label=NEW_OPENER,
        decision_book="betmgm", decision_odds_raw=-105.0))
    assert opener == (-105.0, "BetMGM")
    # Equal is not strictly better, so the published number stays dk_odds
    # and the book stays the one that number came from.
    not_better = xp._publish_price(_sig(
        model_id="nfl_wind_totals", label=NEW_WIND, dk_odds=-110.0,
        decision_book="fanduel", decision_odds_raw=-110.0,
        best_book="betmgm", best_odds=-110.0))
    assert not_better == (-110.0, "FanDuel")
    # A strictly better price still wins, on the book that has it.
    better = xp._publish_price(_sig(
        model_id="nfl_wind_totals", label=NEW_WIND, dk_odds=-110.0,
        decision_book="fanduel", decision_odds_raw=-110.0,
        best_book="betmgm", best_odds=-105.0))
    assert better == (-105.0, "BetMGM")
    # An old row with no decision columns: the label still names the book,
    # and this surface does not parse it.
    old = xp._publish_price(_sig(
        model_id="nfl_wind_totals", label=OLD_WIND, dk_odds=-110.0))
    assert old == (-110.0, "DraftKings")
    assert xp._publish_price({"dk_odds": -110, "best_book": None,
                              "best_odds": None}) == (-110, "DraftKings")
    assert xp._publish_price({"dk_odds": None, "best_book": None,
                              "best_odds": None}) == (None, None)
    tweet = xp.render_pick(_sig(
        model_id="nfl_opener_spread", label=NEW_OPENER,
        decision_book="betmgm", decision_odds_raw=-105.0,
        game_date="2026-10-23"))
    assert NEW_OPENER in tweet
    assert "at BetMGM" in tweet
    assert "DraftKings" not in tweet
    assert "Pinnacle" not in tweet and "Opener" not in tweet


def test_an_mlb_decision_book_does_not_rename_draftkings():
    """Master printed DraftKings whenever the best price was absent, equal
    or worse, including a row that already stored decision_book."""
    row = _sig(model_id="mlb_spread_market", label="BOS +1.5",
               sport="MLB", dk_odds=-110.0, decision_book="fanduel",
               decision_odds_raw=-110.0, home="BOS", away="NYY")
    assert dn.book_for_pick(row) == "DraftKings"
    assert dn.publish_price(row) == (-110.0, "DraftKings")
    equal = dict(row, best_book="fanduel", best_odds=-110.0)
    assert dn.publish_price(equal) == (-110.0, "DraftKings")
    worse = dict(row, best_book="betmgm", best_odds=-130.0)
    assert dn.publish_price(worse) == (-110.0, "DraftKings")
    assert xp._publish_price(row) == (-110.0, "DraftKings")
    # The column still names the book on a card that stored a soft-book price.
    assert dn.publish_price(_sig(
        model_id="nfl_wind_totals", label=NEW_WIND, dk_odds=-110.0,
        decision_book="fanduel", decision_odds_raw=-110.0,
        home="MIA", away="NYJ")) == (-110.0, "FanDuel")


def test_fd_and_mgm_prices_are_named_on_discord_and_x():
    """Wind, opener and prop cards store the soft book's price in dk_odds.
    Both surfaces name that book when decision_odds is the same number."""
    cases = (
        ("nfl_wind_totals", NEW_WIND, "fanduel", -110.0, "FanDuel", "NFL"),
        ("nfl_wind_totals", NEW_WIND, "betmgm", -115.0, "BetMGM", "NFL"),
        ("nfl_opener_spread", NEW_OPENER, "fanduel", -108.0, "FanDuel", "NFL"),
        ("nfl_opener_spread", NEW_OPENER, "betmgm", -105.0, "BetMGM", "NFL"),
        ("nfl_prop_market", NEW_PROP, "fanduel", -120.0, "FanDuel", "NFL"),
        ("nfl_prop_market", NEW_PROP, "betmgm", -125.0, "BetMGM", "NFL"),
        ("wnba_prop_market", NEW_WNBA, "fanduel", -110.0, "FanDuel", "WNBA"),
        ("wnba_prop_market", NEW_WNBA, "betmgm", -115.0, "BetMGM", "WNBA"),
    )
    for model, label, book, odds, shown, sport in cases:
        row = _sig(model_id=model, label=label, sport=sport, dk_odds=odds,
                   decision_book=book, decision_odds_raw=odds)
        assert dn.book_for_pick(row) == shown
        assert dn.publish_price(row) == (odds, shown)
        assert xp._publish_price(row) == (odds, shown)
        tweet = xp.render_pick(dict(row, game_date="2026-10-23"))
        assert f"at {shown}" in tweet
        embed = dn._signal_field(row)
        assert embed["name"] == label
        assert f"@ {shown}" in embed["value"]


def test_push_still_reads_both_labels():
    body = push._summary_body([OLD_OPENER, NEW_WIND])
    assert OLD_OPENER in body and NEW_WIND in body
    assert "Wind" not in NEW_WIND


def test_the_producers_select_the_book_column():
    new = inspect.getsource(dn._new_signals)
    locked = inspect.getsource(dn._locked_signals)
    free = inspect.getsource(dn._free_pick_candidates)
    for src in (new, locked):
        assert "p.decision_book" in src
        assert "p.decision_odds AS decision_odds_raw" in src
    assert "pk.decision_book" in free and "pk.decision_odds" in free
    assert '"decision_book": r[' in new
    assert '"decision_odds_raw": r[' in new

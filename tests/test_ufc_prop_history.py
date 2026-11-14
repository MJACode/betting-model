"""The UFC prop price crawl: how it reads a BestFightOdds event page and a
price history, and how it places a fight on our fight log. No test here
reaches the site or a database. The page fixture is a trimmed copy of the
real UFC Fight Night 190 page (2021-06-26), saved 2026-11-13."""
from __future__ import annotations

import base64
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from data.ingestors import ufc_prop_history as H

FIXTURE = Path(__file__).parent / "fixtures" / "bfo_event_ufc_fn190_excerpt.html"
# The site's real answer for DraftKings' "Saint-Denis wins by TKO/KO" history
# (book 22, fight 36053, prop 8, fighter 1), saved 2026-11-13.
REAL_CHART = ("LExRPzI+NlFpUXNDMjdFejo/OERRW1E1MkUyUWksTFFJUWlgZmFmYWVhZV9mX19fW1FKUWlgXWhfaF9oW1E1"
              "MkUyezIzNj1EUWlMUUlRaWhOTltMUUlRaWBmYWZjY2RmYmFfX19bUUpRaWBdZ2VoZGZOW0xRSVFpYGZhZmRh"
              "YmNnZV9fX1tRSlFpYF1oX2hfaFtRNTJFMnsyMzY9RFFpTFFJUWlcaE5OLk4u")


@pytest.fixture(scope="module")
def page():
    return H.parse_event(FIXTURE.read_text(encoding="utf-8"))


def _cell(page, book, pt, team, side):
    got = [c for c in page.cells if (c.book_id, c.prop_type, c.team, c.side) == (book, pt, team, side)]
    assert len(got) <= 1
    return got[0] if got else None


def test_the_page_date_comes_from_the_title(page):
    assert page.event_date == date(2021, 6, 26)


def test_the_page_names_its_books_by_id(page):
    assert page.books[22] == "DraftKings" and page.books[24] == "Caesars"
    assert page.books[21] == "FanDuel" and len(page.books) == 9


def test_a_fight_is_its_two_fighter_rows_in_page_order(page):
    assert [(f.matchup_id, f.fighter1_name, f.fighter1_bfo_slug, f.fighter2_name,
             f.fighter2_bfo_slug) for f in page.fights] == [
        (22454, "Alexander Volkov", "alexander-volkov-2439", "Ciryl Gane", "ciryl-gane-9273")]


def test_every_book_s_fight_winner_price_is_read(page):
    assert _cell(page, 22, 0, 0, 1).price == 125          # DraftKings, Volkov
    assert _cell(page, 22, 0, 0, 2).price == -155         # DraftKings, Gane
    assert _cell(page, 21, 0, 0, 2).price == -176         # FanDuel, Gane
    assert sum(1 for c in page.cells if c.prop_type == 0) == 14


def test_prop_cells_carry_type_fighter_side_and_an_unescaped_label(page):
    over = _cell(page, 24, 32, 0, 1)
    assert (over.label, over.price) == ("Over 1½ rounds", -350)   # escaped twice on the page
    nogo = _cell(page, 22, 1, 0, 1)
    assert (nogo.label, nogo.price) == ("Fight goes to decision", -106)
    assert _cell(page, 25, 1, 0, 2).label == "Fight doesn't go to decision"
    assert _cell(page, 22, 11, 2, 1).price == 188         # DraftKings, Gane by decision
    assert _cell(page, 25, 11, 1, 2).price == -670        # BetRivers, not Volkov by decision


def test_a_book_that_shows_n_a_has_no_cell(page):
    # DraftKings priced "goes to decision" but not "doesn't", and no KO price for Volkov
    assert _cell(page, 22, 1, 0, 2) is None
    assert _cell(page, 22, 8, 1, 1) is None
    assert len(page.cells) == 39


@pytest.mark.parametrize("text,want", [("+138", 138), ("-176", -176), ("−176", -176),
                                       ("EV", 100), ("n/a", None), ("", None)])
def test_american_prices_read_every_minus_sign(text, want):
    assert H.american(text) == want


def test_the_sitemap_keeps_ufc_cards_and_drops_the_bjj_events():
    xml = ("<urlset><url><loc>https://www.bestfightodds.com/events/ufc-281-2529</loc></url>"
           "<url><loc>https://www.bestfightodds.com/events/ufc-bjj-13-4434</loc></url>"
           "<url><loc>https://www.bestfightodds.com/events/pfl-10-2530</loc></url>"
           "<url><loc>https://www.bestfightodds.com/events/ufc-3427</loc></url></urlset>")
    assert H.sitemap_events(xml) == [(2529, "ufc-281-2529"), (3427, "ufc-3427")]


def test_a_real_price_history_decodes_to_timed_decimal_prices():
    (name, pts), = H.decode_chart(REAL_CHART)
    assert name == "DraftKings"
    assert [(t.strftime("%Y-%m-%dT%H:%M"), round(d, 5)) for t, d in pts] == [
        ("2024-09-25T11:10", 1.90909), ("2024-09-27T14:02", 1.86957), ("2024-09-28T11:38", 1.90909)]
    assert [H.decimal_to_american(d) for _, d in pts] == [-110, -115, -110]


def test_an_empty_history_is_no_series():
    assert H.decode_chart("[]") == []


def test_the_decoder_is_the_inverse_of_the_site_s_encoding():
    rot = H.ROT
    text = json.dumps([{"name": "Ref", "data": [{"x": 1_700_000_000_000, "y": 2.5}]}])
    enc = "".join(rot[(rot.index(c) + 47) % 94] if c in rot else c for c in text)
    raw = base64.b64encode(enc.encode()).decode()
    (name, pts), = H.decode_chart(raw)
    assert name == "Ref" and pts == [(datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc), 2.5)]


def test_history_rows_are_change_points_with_american_prices():
    rows = H.tick_rows("22_36053_8_1_1", REAL_CHART)
    assert [(r[0], r[1], r[2], r[3], r[4], r[5], r[8]) for r in rows] == [
        (36053, 22, "draftkings", 8, 1, 1, -110), (36053, 22, "draftkings", 8, 1, 1, -115),
        (36053, 22, "draftkings", 8, 1, 1, -110)]


def _placer():
    # the log lists Gane first: placement must not depend on position
    return H.FightPlacer([("UFC_2021-06-26_ciryl-gane_alexander-volkov", "2021-06-26", "id-gane", "Ciryl Gane"),
                          ("UFC_2021-06-26_ciryl-gane_alexander-volkov", "2021-06-26", "id-volk", "Alexander Volkov")])


def test_a_fight_is_placed_by_its_slug_pair_and_each_fighter_by_slug(page):
    assert _placer()(page.fights[0], date(2021, 6, 26)) == (
        "UFC_2021-06-26_ciryl-gane_alexander-volkov", "id-volk", "id-gane")


def test_the_site_s_own_slug_places_a_fighter_whose_name_is_spelled_differently():
    f = H.Fight(1, "Alex Volkov", "alexander-volkov-2439", "Ciryl Gane", "ciryl-gane-9273")
    assert _placer()(f, date(2021, 6, 27))[1] == "id-volk"


def test_a_fight_outside_two_days_or_with_a_stranger_is_not_placed():
    f = H.Fight(1, "Alexander Volkov", None, "Ciryl Gane", None)
    assert _placer()(f, date(2021, 7, 3)) is None
    assert _placer()(H.Fight(1, "Alexander Volkov", None, "Somebody Else", None),
                     date(2021, 6, 26)) is None


def test_an_unplaced_fight_is_kept_with_no_game_id(page):
    empty = H.FightPlacer([])
    fights, cells = H.page_rows(2109, "ufc-fight-night-190-gane-vs-volkov-2109",
                                "2026-11-13T00:00:00Z", page, empty)
    assert fights[0][0] == 22454 and fights[0][8] is None
    assert len(cells) == 39 and {c[2] for c in cells} >= {"draftkings", "williamhill_us"}


def _placer_saint():
    return H.FightPlacer([("UFC_2021-06-26_tanner-boser_ovince-saint-preux", "2021-06-26", "id-boser", "Tanner Boser"),
                          ("UFC_2021-06-26_tanner-boser_ovince-saint-preux", "2021-06-26", "id-osp", "Ovince Saint Preux")])


def test_a_fighter_spelled_close_is_placed_when_his_opponent_matches_exactly():
    f = H.Fight(23299, "Ovince St. Preux", "ovince-st-preux-1788", "Tanner Boser", "tanner-boser-7638")
    assert _placer_saint()(f, date(2021, 6, 26)) == (
        "UFC_2021-06-26_tanner-boser_ovince-saint-preux", "id-osp", "id-boser")


def test_a_different_opponent_is_never_placed_by_likeness():
    # the bout the page lists fell through and the log holds the replacement
    f = H.Fight(1, "Marcus Alvarez", None, "Tanner Boser", None)
    assert _placer_saint()(f, date(2021, 6, 26)) is None


def test_a_2026_page_whose_title_has_no_date_is_dated_by_its_start_date():
    page = FIXTURE.read_text(encoding="utf-8").replace(
        "\u2013 Jun 26, 2021 | Best Fight Odds", "Chimaev vs Strickland Betting Odds").replace(
        "</head>", '<script type="application/ld+json">{"startDate": "2026-05-09"}</script></head>')
    assert "2021 | Best" not in page
    assert H.parse_event(page).event_date == date(2026, 5, 9)


def test_a_page_with_no_date_anywhere_is_refused():
    page = FIXTURE.read_text(encoding="utf-8").replace("\u2013 Jun 26, 2021 | Best Fight Odds", "Odds")
    with pytest.raises(ValueError):
        H.parse_event(page)


def test_a_page_dated_only_by_its_table_header_takes_the_fetch_year():
    page = FIXTURE.read_text(encoding="utf-8").replace("– Jun 26, 2021 | Best Fight Odds", "Odds")
    page = page.replace("<thead>", '<span class="table-header-date">August 1st</span><thead>', 1)
    assert H.parse_event(page, today=date(2026, 11, 14)).event_date == date(2026, 8, 1)
    # a header date months ahead of the fetch is last year's card
    assert H.parse_event(page, today=date(2027, 2, 1)).event_date == date(2026, 8, 1)
    assert H.parse_event(page, today=date(2026, 7, 20)).event_date == date(2026, 8, 1)


@pytest.mark.parametrize("bfo,log", [("Kenan Song", "Song Kenan"), ("Qileng Aori", "Aoriqileng"),
                                     ("Kang Kyung-Ho", "Kyung Ho Kang"), ("Seung Woo Choi", "SeungWoo Choi"),
                                     ("Kai Kamaka III", "Kai Kamaka"), ("Bobby Green", "King Green")])
def test_a_name_ufcstats_orders_or_spells_otherwise_still_meets_it(bfo, log):
    assert H.compact(H.slugify(log)) in H.name_slugs(bfo, None)


def test_name_orders_do_not_make_two_different_fighters_meet():
    assert H.compact(H.slugify("Daniel Rodriguez")) not in H.name_slugs("Pete Rodriguez", None)


@pytest.mark.parametrize("error", [ConnectionResetError(10054, "forcibly closed"), TimeoutError("timed out"),
                                   H.http.client.IncompleteRead(b"")])
def test_a_dropped_connection_is_one_failed_history_not_the_end_of_the_run(tmp_path, monkeypatch, error):
    """2026-11-14: a reset connection 1,500 histories in ended the run before it
    stored anything. A failed request is counted; the rest are still asked."""
    calls = []

    def fake_get(path, xhr=False):
        calls.append(path)
        if len(calls) == 1:
            raise error
        return REAL_CHART

    monkeypatch.setattr(H, "_get", fake_get)
    jobs = [(22, 36053, 8, 1, 1), (22, 36054, 8, 1, 1)]
    stats = H.fetch_charts(tmp_path, jobs, set(), pause=0)
    assert stats == {"asked": 2, "spooled": 1, "failed": 1, "already": 0}
    assert not H.chart_path(tmp_path, H.chart_key(*jobs[0])).exists()
    assert H.chart_path(tmp_path, H.chart_key(*jobs[1])).exists()


def test_a_dropped_connection_on_a_page_is_one_failed_page(tmp_path, monkeypatch):
    def fake_get(path, xhr=False):
        raise ConnectionResetError(10054, "forcibly closed")

    monkeypatch.setattr(H, "_get", fake_get)
    stats = H.fetch_pages(tmp_path, [(2109, "ufc-fight-night-190-2109")], date(2026, 11, 14), set(), pause=0)
    assert stats["failed"] == 1 and stats["spooled"] == 0

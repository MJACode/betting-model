"""Another book's live number from its own page (models/book_live_quotes.py;
mike, 2026-11-26: "We want best line"; issue #1644).

Pinned here, each gate a quote must pass before any model may bet it:
  * the book's newest answer was clean and its PAGE time (read time less the
    answer's age) is within DraftKings' 8 s, so a cached page 30 s old does not
    qualify however recently we fetched it;
  * the number is on offer at the newest row (a suspended market is not);
  * its start is known: never a first row after a feed start, never a row
    with no previous read;
  * `stamp` is the PREVIOUS read's page time (the book set the number after
    it), `shown` the first read that showed it; held once a later read exists;
  * a spread stays the HOME number with each side's price.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from models import book_live_quotes as Q

T0 = datetime(2026, 11, 26, 22, 0, 0, tzinfo=timezone.utc)


def at(s):
    return pd.Timestamp(T0 + timedelta(seconds=s))


def row(book, s, *, age=None, after_start=False, prev=None, prev_age=None, spread=(-4.5, -110.0, -110.0),
        total=(140.5, -115.0, -105.0), ml=(-200.0, 165.0), gid="G1"):
    sh, shp, sap = spread if spread is not None else (None, None, None)
    tl, op, up = total if total is not None else (None, None, None)
    hm, am = ml if ml is not None else (None, None)
    return {"book": book, "game_id": gid, "read_at": at(s), "page_age_s": age, "after_start": after_start,
            "spread_home": sh, "spread_home_price": shp, "spread_away_price": sap,
            "total_line": tl, "over_price": op, "under_price": up, "home_ml": hm, "away_ml": am,
            "prev_read_at": None if prev is None else at(prev), "prev_page_age_s": prev_age}


def feed(book, s, *, ok=True, age=None):
    return {"book": book, "last_read_at": at(s), "ok": ok, "page_age_s": age}


def quotes(rows, feeds, now, markets=("spreads", "totals", "h2h")):
    return Q.current_quotes(pd.DataFrame(rows), pd.DataFrame(feeds), at(now), markets)


def test_a_fresh_on_offer_number_is_a_quote_stamped_at_the_read_before_it():
    rows = [row("betrivers", 0, after_start=True),
            row("betrivers", 10, prev=8, spread=(-5.5, -112.0, -108.0))]
    q = quotes(rows, [feed("betrivers", 14)], 15, markets=("spreads",))
    [r] = q.to_dict("records")
    assert (r["book"], r["market"], r["spread_home"], r["home_price"], r["away_price"]) == \
        ("betrivers", "spreads", -5.5, -112.0, -108.0)
    assert r["stamp"] == at(8) and r["shown"] == at(10) and r["held"]


def test_a_cdn_copy_is_stamped_on_the_pages_own_clock():
    rows = [row("fanduel", 0, after_start=True),
            row("fanduel", 40, age=12, prev=38, prev_age=30, spread=(-5.5, -112.0, -108.0))]
    q = quotes(rows, [feed("fanduel", 45, age=1)], 46, markets=("spreads",))
    [r] = q.to_dict("records")
    assert r["stamp"] == at(8) and r["shown"] == at(28)       # 38 - 30 and 40 - 12


def test_a_cached_page_older_than_draftkings_bound_does_not_qualify():
    rows = [row("fanduel", 0, after_start=True), row("fanduel", 10, prev=8, spread=(-5.5, -112.0, -108.0))]
    assert quotes(rows, [feed("fanduel", 20, age=13)], 21).empty          # page time 7: 14 s old
    assert len(quotes(rows, [feed("fanduel", 20, age=5)], 21)) > 0        # page time 15: 6 s old


def test_a_refused_or_stale_feed_gives_nothing():
    rows = [row("betrivers", 0, after_start=True), row("betrivers", 10, prev=8, spread=(-5.5, -112.0, -108.0))]
    assert quotes(rows, [feed("betrivers", 14, ok=False)], 15).empty
    assert quotes(rows, [feed("betrivers", 14)], 30).empty                 # last read 16 s ago


def test_a_suspended_market_is_not_on_offer_and_the_others_still_are():
    rows = [row("betrivers", 0, after_start=True),
            row("betrivers", 10, prev=8, spread=None, total=(141.5, -110.0, -110.0))]
    q = quotes(rows, [feed("betrivers", 14)], 15)
    assert set(q["market"]) == {"totals"}                 # h2h unchanged since the start row: unknown


def test_a_number_unchanged_since_a_start_is_never_a_quote():
    rows = [row("betrivers", 0, after_start=True), row("betrivers", 10, prev=8, total=(141.5, -110.0, -110.0))]
    q = quotes(rows, [feed("betrivers", 14)], 15)
    assert set(q["market"]) == {"totals"}                 # the spread is still the start row's


def test_a_row_with_no_previous_read_is_never_a_quote():
    rows = [row("betrivers", 0, after_start=True), row("betrivers", 10, spread=(-5.5, -112.0, -108.0))]
    assert quotes(rows, [feed("betrivers", 14)], 15, markets=("spreads",)).empty


def test_the_stamp_is_where_the_current_number_first_appeared():
    rows = [row("betrivers", 0, after_start=True),
            row("betrivers", 10, prev=8, spread=(-5.5, -112.0, -108.0)),
            row("betrivers", 20, prev=18, spread=(-5.5, -112.0, -108.0), total=(142.5, -110.0, -110.0))]
    q = quotes(rows, [feed("betrivers", 24)], 25, markets=("spreads", "totals"))
    by = {r["market"]: r for r in q.to_dict("records")}
    assert by["spreads"]["stamp"] == at(8) and by["totals"]["stamp"] == at(18)


def test_a_number_that_came_back_after_a_suspension_is_stamped_on_its_return():
    rows = [row("betrivers", 0, after_start=True),
            row("betrivers", 10, prev=8, spread=(-5.5, -112.0, -108.0)),
            row("betrivers", 20, prev=18, spread=None),
            row("betrivers", 30, prev=28, spread=(-5.5, -112.0, -108.0))]
    [r] = quotes(rows, [feed("betrivers", 34)], 35, markets=("spreads",)).to_dict("records")
    assert r["stamp"] == at(28)


def test_not_held_until_a_later_read_shows_it_again():
    rows = [row("betrivers", 0, after_start=True), row("betrivers", 10, prev=8, spread=(-5.5, -112.0, -108.0))]
    [r] = quotes(rows, [feed("betrivers", 10)], 11, markets=("spreads",)).to_dict("records")
    assert not r["held"]


def test_rows_after_the_decision_time_are_not_read():
    rows = [row("betrivers", 0, after_start=True), row("betrivers", 10, prev=8, spread=(-5.5, -112.0, -108.0))]
    assert quotes(rows, [feed("betrivers", 9)], 9.5, markets=("spreads",)).empty


def test_a_moneyline_quote_has_home_and_away_prices_and_no_line():
    rows = [row("betrivers", 0, after_start=True), row("betrivers", 10, prev=8, ml=(-250.0, 200.0))]
    [r] = quotes(rows, [feed("betrivers", 14)], 15, markets=("h2h",)).to_dict("records")
    assert (r["home_price"], r["away_price"]) == (-250.0, 200.0) and np.isnan(r["spread_home"])


def test_only_the_named_books_are_read():
    rows = [row("betmgm", 0, after_start=True), row("betmgm", 10, prev=8, spread=(-5.5, -112.0, -108.0))]
    assert quotes(rows, [feed("betmgm", 14)], 15).empty


def test_the_bound_is_draftkings_own():
    from models import ncaab_live_dk as DK
    assert Q.FEED_MAX_AGE_SEC == DK.FEED_MAX_AGE_SEC


def test_the_reader_columns_are_the_feeds():
    from data.ingestors import book_live_boards as L
    assert set(Q.ROW_COLS) - {"after_start"} <= set(L.READS_COLS)
    assert set(Q.ROW_COLS[5:13]) == set(L.READ_LINE_COLS)

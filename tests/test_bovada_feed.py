"""Bovada as the second live source: the parse, and the things it must refuse.

Bovada was the only book of seven that answered the Railway worker (2026-08-31),
so it is the only direct feed that can run always-on. It is a BEST-LINE source
only -- the models decide on DraftKings (CLAUDE.md section 6) -- and these tests
pin that separation structurally rather than by convention.

The payload shapes below are taken from a real live coupon, not invented.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from data.ingestors import bovada_direct_feed as b

ROOT = Path(__file__).parent.parent


def _price(american, handicap=None):
    return {"american": american, "handicap": handicap, "decimal": None}


def _mkt(desc, outcomes, live=True, status="O"):
    return {"description": desc, "status": status,
            "period": {"description": "Live Game", "live": live},
            "outcomes": outcomes}


def _coupon(markets, ev_live=True, last_modified=1788142646954):
    return [{"events": [{
        "description": "Cincinnati Reds @ Chicago Cubs",
        "live": ev_live, "status": "O", "lastModified": last_modified,
        "displayGroups": [{"markets": markets}]}]}]


def _out(t, american, handicap=None, status="O"):
    return {"type": t, "status": status, "description": t,
            "price": _price(american, handicap)}


# -- the parse ----------------------------------------------------------------

def test_the_runline_stores_the_HOME_number():
    """Bovada carries the handicap per outcome with opposite signs (away -2.5,
    home +2.5). scored_line is always the HOME figure in this repo -- taking the
    away one flips the sign on every spread, which has produced a wrong
    threshold twice."""
    recs = b.parse_coupon(_coupon([_mkt("Runline", [
        _out("A", "-350", "-2.5"), _out("H", "+250", "2.5")])]))
    assert len(recs) == 1
    r = recs[0]
    assert r["market"] == "spreads"
    assert r["line"] == 2.5, "the home handicap, not the away one"
    assert (r["home_price"], r["away_price"]) == (250, -350)


def test_totals_and_moneyline_map_across():
    recs = {r["market"]: r for r in b.parse_coupon(_coupon([
        _mkt("Total", [_out("O", "-115", "11.5"), _out("U", "-115", "11.5")]),
        _mkt("Moneyline", [_out("A", "-7500"), _out("H", "+1500")])]))}
    assert recs["totals"]["line"] == 11.5
    assert (recs["totals"]["over_price"], recs["totals"]["under_price"]) == (-115, -115)
    assert (recs["h2h"]["home_price"], recs["h2h"]["away_price"]) == (1500, -7500)


def test_the_leading_plus_is_parsed_not_dropped():
    """+250 must be 250, not None. The sibling DK feed had the mirror bug: a
    UNICODE minus that int() could not read."""
    assert b._american(_price("+250")) == 250
    assert b._american(_price("-350")) == -350
    assert b._american(_price("−140")) == -140, "unicode minus"


def test_a_missing_american_falls_back_to_decimal():
    assert b._american({"american": None, "decimal": "2.5"}) == 150
    assert b._american({"american": None, "decimal": "1.5"}) == -200


def test_last_modified_is_milliseconds():
    """Reading it as seconds dates every row to 1970 and makes every quote look
    infinitely stale, which the age gate would then decline forever."""
    assert b._stamp(1788142646954).startswith("2026-")
    assert b._stamp(None) is None
    assert b._stamp("nonsense") is None


def test_the_book_clock_is_preferred_over_ours():
    """Bovada publishes lastModified, so unlike DK direct this feed's
    snapshot_at means the same thing it does for aggregator rows."""
    rec = b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", "8.5"), _out("U", "-110", "8.5")])]))[0]
    row = b._row_for(rec, "G", "OUR-CLOCK")
    assert row["snapshot_at"] == rec["published_at"] != "OUR-CLOCK"


def test_a_missing_publish_stamp_falls_back_to_our_clock():
    """It must never make a stale quote look fresh -- it makes it look exactly
    as fresh as our read, which is the honest floor."""
    rec = b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", "8.5"), _out("U", "-110", "8.5")])],
        last_modified=None))[0]
    assert b._row_for(rec, "G", "OUR-CLOCK")["snapshot_at"] == "OUR-CLOCK"


# -- the refusals -------------------------------------------------------------

def test_a_market_with_one_side_suspended_is_dropped_not_half_written():
    """Observed live: the Reds at -7500 had their side suspended ('S') while the
    Cubs stayed open. A two-way market with one side off the board is not a
    quote you can shop, and writing half of it would invent a price."""
    recs = b.parse_coupon(_coupon([_mkt("Moneyline", [
        _out("A", "-7500", status="S"), _out("H", "+1500")])]))
    assert recs == []


def test_a_suspended_market_is_dropped():
    recs = b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", "8.5"), _out("U", "-110", "8.5")], status="S")]))
    assert recs == []


def test_pre_game_markets_are_not_taken_as_in_play():
    """The EVENT flag stays true while bovada also publishes the pre-game market
    for the same game, so the market period must agree. Taking the event flag
    alone would write a pre-game number as an in-play one."""
    assert b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", "8.5"), _out("U", "-110", "8.5")], live=False)])) == []


def test_a_non_live_event_is_skipped_when_live_only():
    assert b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", "8.5"), _out("U", "-110", "8.5")])],
        ev_live=False)) == []


def test_a_market_we_do_not_understand_is_ignored():
    assert b.parse_coupon(_coupon([_mkt("Team Total Runs", [
        _out("O", "-110", "4.5"), _out("U", "-110", "4.5")])])) == []


def test_a_total_with_no_line_is_dropped():
    assert b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", None), _out("U", "-110", None)])])) == []


def test_an_empty_payload_is_not_a_crash():
    for junk in ([], None, [{}], [{"events": []}]):
        assert b.parse_coupon(junk) == []


# -- the invariant ------------------------------------------------------------

def test_rows_are_written_as_bovada_so_the_decision_path_cannot_see_them():
    """CLAUDE.md section 6: the models only ever DECIDE on DraftKings, because
    every threshold was swept on DK-implied edge and best-of-N runs ~2pp
    cheaper. Writing these as 'bovada' makes that structural -- _get_live_dk_odds
    filters to draftkings and can never pick them up."""
    rec = b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", "8.5"), _out("U", "-110", "8.5")])]))[0]
    row = b._row_for(rec, "G", "T")
    assert row["bookmaker"] == "bovada"
    assert row["source"] == "bovada_direct"
    assert row["snapshot_type"] == "in_play"


def test_the_dedup_key_ignores_the_clock():
    rec = b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", "8.5"), _out("U", "-110", "8.5")])]))[0]
    assert b._seen_key(b._row_for(rec, "G", "T1")) == \
        b._seen_key(b._row_for(rec, "G", "T2"))


def test_a_price_move_is_a_new_quote():
    a = b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-110", "8.5"), _out("U", "-110", "8.5")])]))[0]
    c = b.parse_coupon(_coupon([_mkt("Total", [
        _out("O", "-105", "8.5"), _out("U", "-115", "8.5")])]))[0]
    assert b._seen_key(b._row_for(a, "G", "T")) != b._seen_key(b._row_for(c, "G", "T"))


def test_the_feed_is_off_by_default():
    sched = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert 'os.environ.get("RUN_BOVADA_FEED", "0") != "0"' in sched
    assert "RUN_BOVADA_FEED=0" in sched, "the off state must log why"


def test_the_insert_rolls_back_per_row():
    assert "conn.rollback()" in inspect.getsource(b.poll_once)


def test_a_run_that_writes_nothing_is_not_reported_as_success():
    src = inspect.getsource(b.run)
    assert 'level = "info" if totals["written"] or dry_run else "warning"' in src


# -- the shared team map ------------------------------------------------------

def test_both_feeds_use_one_team_map():
    """It was a private copy in the DK feed until 2026-08-31, and two bugs had
    already been found in it. A fix that lands in one feed and not the other is
    exactly what section 1b exists to prevent."""
    for rel in ("data/ingestors/dk_direct_feed.py",
                "data/ingestors/bovada_direct_feed.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "book_team_map" in src, f"{rel} rolls its own team map"

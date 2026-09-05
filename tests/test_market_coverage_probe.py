"""Which books serve which prop markets — the audit that stored data cannot do.

Matt, 2026-09-05: "Check all the sportsbooks we get betting lines for and see
if they publish stats under different keys and sync everything up with the
stats tab."

The prompt was FanDuel and Caesars showing nothing on the MLB hits board. They
price hits for every hitter on the slate and publish them ONLY under
`batter_hits_alternate`, never returning a single `batter_hits` row — so their
column was blank until alternates shipped.

What is pinned here is the part that is easy to get subtly wrong: a market we
never REQUEST has no rows, and no query over stored data can tell "no book
prices this" from "we never asked". The probe exists to ask, so it must ask
about the right keys, cost what it claims, and write nothing.
"""

import inspect

import pytest

import config
from scripts import probe_market_coverage as p


def test_the_probe_asks_about_every_market_we_pull_and_its_alternate():
    for sport in ("MLB", "WNBA", "NBA", "NFL", "NCAAF"):
        cand = p.candidate_markets(sport)
        for m in p._standard_markets(sport):
            assert m in cand, f"{sport}: {m} not asked"
            assert f"{m}_alternate" in cand, f"{sport}: {m}_alternate not asked"


def test_it_asks_about_the_board_columns_that_are_permanently_blank():
    """A blank column is either "no book prices it" or "we never asked", and
    those look identical until someone asks."""
    mlb = p.candidate_markets("MLB")
    assert "batter_doubles" in mlb and "batter_at_bats" in mlb
    wnba = p.candidate_markets("WNBA")
    # NBA pulls steals/blocks/turnovers; the WNBA board shows those columns and
    # the WNBA pull has never included them.
    for m in ("player_steals", "player_blocks"):
        assert m in wnba, f"WNBA never asks about {m}"
        assert m not in config.PROP_MARKETS_WNBA, "sanity: that is the gap"
        assert m in config.PROP_MARKETS_NBA, "sanity: NBA already pulls it"


def test_no_market_is_asked_about_twice():
    for sport in ("MLB", "WNBA", "NBA", "NFL", "NCAAF"):
        cand = p.candidate_markets(sport)
        assert len(cand) == len(set(cand)), f"{sport} asks a market twice"


def test_one_market_per_call_so_a_rejected_key_is_identified_exactly():
    src = inspect.getsource(p.probe)
    assert '"markets": market,' in src, "a chunk would hide which key was rejected"
    assert "unsupported.append(market)" in src


def test_the_probe_writes_nothing():
    src = inspect.getsource(p)
    for forbidden in ("_insert_prop_odds", "INSERT INTO", "executemany"):
        assert forbidden not in src, f"a probe that writes is a pull with a nice name ({forbidden})"


def test_it_reports_supported_but_empty_apart_from_unsupported():
    """"The API does not know this key" and "no book priced it today" are
    different answers and lead to different decisions."""
    src = inspect.getsource(p.probe)
    assert '"unsupported_keys": unsupported' in src
    assert '"empty_but_supported"' in src


def test_only_books_we_asked_for_are_ever_counted():
    src = inspect.getsource(p.probe)
    assert "if key not in LINE_SHOP_BOOKMAKERS:" in src


def test_the_job_validates_its_sport_and_market_list():
    from tracking.job_queue import JOBS, _validate_market_coverage as v
    assert "market_coverage" in JOBS
    assert v({"sport": "mlb"}) == {"sport": "MLB", "markets": None}
    assert v({"sport": "MLB", "markets": ["batter_hits"]})["markets"] == ["batter_hits"]
    # An explicit empty list is a caller error, never a full sweep: `or None`
    # would have quietly turned one into the other.
    with pytest.raises(ValueError):
        v({"sport": "MLB", "markets": []})
    with pytest.raises(ValueError):
        v({"sport": "MLB", "markets": "batter_hits"})
    with pytest.raises(ValueError):
        v({"sport": "CRICKET"})

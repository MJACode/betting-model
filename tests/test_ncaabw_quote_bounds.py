"""A feed typo never becomes an NCAABW bet (models/ncaabw_quote_bounds.py).

A fork of tests/test_ncaab_quote_bounds.py (2026-11-10), cut to the one live
women's card, the totals card. The men's history holds a DraftKings full-game
total of 1465.0 for 146.5; a live one would have priced the under near 100%.
These pin that a quote outside the women's measured range (a 1465.0 total, a
price beyond +/-100000) is dropped before anything prices it, is logged with
its game, book and value, is counted on the run's line, and places no bet;
that an absurd edge from an in-range quote is not a bet either and fails the
run; and that the guard leaves a real slate alone (the extremes the women's
history holds stay quotes).

The build's replay is the proof that the bounds remove nothing real:
DraftKings' women's totals of 2024-25 to 2026-27 held no row outside the range
("dropped as data errors: 0", scripts/ncaabw_total_blend_build.py).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")


@pytest.fixture()
def logs():
    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="WARNING", format="{message}")
    yield lines
    logger.remove(sink)


# ── the bounds ───────────────────────────────────────────────────────────────

def test_each_market_has_its_measured_range():
    from models import ncaabw_quote_bounds as qb
    # the women's own ranges, not the men's (totals to 220, spreads to +/-60): the feed
    # carries no women's first-half line, so there is no first-half range
    assert qb.LINE_RANGE == {"totals": (90.0, 200.0), "spreads": (-85.0, 85.0)}
    import models.ncaabw_total_blend as nb
    assert nb.TOTAL_RANGE == qb.LINE_RANGE["totals"]          # one number, two readers
    assert qb.MAX_ABS_PRICE == 100_000
    # the replay's largest edge over every priced game is 0.2076, so not the men's 0.25
    # the halftime total's largest replayed edge is 0.371 (967 bets), so 0.40
    assert qb.EDGE_CAP == {"ncaabw_total_blend": 0.30, "ncaabw_live_total_ht": 0.40}


def test_a_typo_is_a_data_error_and_the_extremes_history_holds_are_not():
    from models import ncaabw_quote_bounds as qb
    assert "outside 90 to 200" in qb.problem("totals", 1465.0, (-110, -110))
    assert qb.problem("totals", 146.5, (-110, -110)) is None
    assert qb.problem("totals", 179.5, (-1430, 1030)) is None         # history's highest, its widest prices
    assert qb.problem("totals", 107.5, (-110, -110)) is None           # DraftKings' lowest
    assert "outside 90 to 200" in qb.problem("totals", 41.5, (-110, -110))   # the one stored row under 100
    assert "outside -85 to 85" in qb.problem("spreads", -335.0, (-110, -110))
    assert qb.problem("spreads", -73.5, (-110, -110)) is None          # history's widest: the men's +/-60 would drop it
    assert qb.problem("spreads", 70.5, (-110, -110)) is None
    assert "beyond +/-100000" in qb.problem("h2h", None, (-190, 250000))
    assert qb.problem("h2h", None, (-100000, 5000)) is None             # the women's moneylines reach it
    # a missing value is the loaders' to drop, not a data error
    assert qb.problem("totals", float("nan"), (None, -110)) is None
    with pytest.raises(ValueError):
        qb.problem("total", 140.5, ())


def test_split_keeps_order_and_says_why():
    from models import ncaabw_quote_bounds as qb
    q = pd.DataFrame({"game_id": ["g", "g", "g"], "bookmaker": ["a", "b", "c"],
                      "line": [-4.5, -335.0, float("nan")], "p1": [-110, -110, -110],
                      "p2": [-110, 250000, -110]})
    kept, bad = qb.split(q, "spreads")
    assert list(kept["bookmaker"]) == ["a", "c"]
    assert list(bad["bookmaker"]) == ["b"] and bad["why"].iloc[0] == "line -335 outside -85 to 85"
    (line,) = qb.describe(bad)
    assert line == "g b spreads line -335 prices -110/+250000: line -335 outside -85 to 85"


# ── the totals card ──────────────────────────────────────────────────────────

def _totals_run(monkeypatch, line=125.5, op=-110, up=-110):
    """The totals card with this quote as both DraftKings' first post and its
    standing number (models/ncaabw_total_card: a first post is bet only while
    it stands)."""
    from tests.test_ncaabw_total_blend import _art, _card_run, _prepared, _quote, _season
    games, box = _season()
    sg, _ = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    card, calls, now, (_, t, at) = _card_run(monkeypatch, art)
    gid = t["game_id"].iloc[0]
    q = {gid: _quote(gid, line=line, at=at, op=op, up=up)}
    monkeypatch.setattr(card, "load_first_posts", lambda conn, g, now: {
        x: v for x, v in q.items() if x in g})
    monkeypatch.setattr(card, "load_quotes", lambda conn, g, now: {
        x: v for x, v in q.items() if x in g})
    return card, calls, now, gid


def test_a_1465_total_is_never_priced_and_the_game_waits(monkeypatch, logs):
    card, calls, now, gid = _totals_run(monkeypatch, line=1465.0)
    out = card.run_card(do_publish=True, now=now)
    assert out["bets"] == 0 and out["diag"]["out_of_range"] == 1
    assert calls == [] or calls == [["out_of_range"]]      # nothing FINAL: it waits
    assert "out_of_range" not in card.FINAL
    assert any(gid in x and "1465" in x for x in logs)


def test_a_1465_first_post_that_reached_the_decision_is_not_priced():
    """The first-post read skips a typo in SQL; the decision refuses one that
    reached it anyway (a loader slip), so no route prices it."""
    import models.ncaabw_total_blend as nb
    from tests.test_ncaabw_total_blend import _art, _late_target, _prepared, _quote, _season
    games, box = _season()
    sg, b = _prepared(games, box)
    t, at = _late_target(sg)
    gid = t["game_id"].iloc[0]
    (d,) = nb.decide(t, {gid: _quote(gid, line=1465.0, at=at)}, sg, b,
                     _art(sorted(set(sg["home_espn_id"]))), 0.05)
    assert d.status == "out_of_range" and d.priced is None
    assert "line 1465 outside 90 to 200" in d.detail


def test_a_first_post_priced_beyond_100000_is_not_priced_and_waits(monkeypatch, logs):
    card, calls, now, gid = _totals_run(monkeypatch, line=125.5, op=250000, up=-110)
    out = card.run_card(do_publish=True, now=now)
    assert out["bets"] == 0 and out["diag"]["out_of_range"] == 1
    assert any(gid in x and "price +250000 beyond +/-100000" in x for x in logs)


def test_a_normal_total_still_bets(monkeypatch, logs):
    card, calls, now, gid = _totals_run(monkeypatch, line=125.5)
    out = card.run_card(do_publish=True, now=now)
    assert out["bets"] == 1 and calls == [["bets"]] and out["diag"]["out_of_range"] == 0


def test_an_absurd_total_edge_is_not_a_bet_and_fails_the_run(monkeypatch, logs):
    # an in-range total at an in-range price that no real book would hang:
    # the over at +900 against a model far over the line
    card, calls, now, gid = _totals_run(monkeypatch, line=125.5, op=900, up=-2000)
    with pytest.raises(card.CardIncomplete, match="edge_cap"):
        card.run_card(do_publish=True, now=now)
    assert calls == [] or "bets" not in calls[0]
    assert any("data-error cap 0.3" in x for x in logs)


def test_a_total_the_mens_range_allows_and_the_womens_does_not_waits(monkeypatch, logs):
    """205.5 is a men's total. No women's total stored is above 179.5, so a
    women's 205.5 is read as a feed error, not priced."""
    card, calls, now, gid = _totals_run(monkeypatch, line=205.5)
    out = card.run_card(do_publish=True, now=now)
    assert out["bets"] == 0 and out["diag"]["out_of_range"] == 1
    assert any(gid in x and "205.5" in x for x in logs)

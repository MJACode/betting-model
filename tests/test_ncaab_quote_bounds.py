"""A feed typo never becomes an NCAAB bet (models/ncaab_quote_bounds.py).

Found 2026-11-03: the odds feed held a DraftKings full-game total of 1465.0
(NCAAB_2023-03-17_providence_kentucky; the book's next row is 146.5). The
totals card skipped only a missing line or price, so a live 1465.0 would have
priced the under near 100% and been written as a bet. These pin, for each of
the four live NCAAB cards, that a quote outside its plausible range (a 1465.0
total, a -335 spread, a first-half spread of -45.5, a +250000 moneyline) is
dropped before anything prices it, is logged with its game, book and value,
is counted on the run's line, and places no bet; that an absurd edge from an
in-range quote is not a bet either and fails the run; and that the guard
leaves a real slate alone (the extremes history holds stay quotes).

The replays are the proof that the bounds remove nothing real: every card's
replay over 2021-2026 gave the same bets with and without them (the session
log, docs/sessions/2026-11.md).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

UTC = timezone.utc


@pytest.fixture()
def logs():
    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="WARNING", format="{message}")
    yield lines
    logger.remove(sink)


# ── the bounds ───────────────────────────────────────────────────────────────

def test_each_market_has_its_measured_range():
    from models import ncaab_quote_bounds as qb
    assert qb.LINE_RANGE == {"totals": (90.0, 220.0), "spreads": (-60.0, 60.0),
                             "totals_h1": (40.0, 120.0), "spreads_h1": (-35.0, 35.0)}
    import models.ncaab_total_blend as nb
    assert nb.TOTAL_RANGE == qb.LINE_RANGE["totals"]          # one number, two readers
    assert qb.MAX_ABS_PRICE == 100_000
    assert qb.EDGE_CAP == {"ncaab_total_blend": 0.25, "ncaab_spread_market": 0.25,
                           "ncaab_moneyline_own_spread": 0.25, "ncaab_first_half_spread": 0.60,
                           "ncaab_first_half_total": 0.50,
                           # the opening moneyline model (models/ncaab_moneyline_first_post.py):
                           # its replay's bets reached 0.2416, so not 0.25
                           "ncaab_moneyline_first_post": 0.40,
                           # the in-play rules (models/ncaab_live_ig.py): the largest edge
                           # over 61,019 graded decisions was 0.453
                           "ncaab_live_spread_h1": 0.50, "ncaab_live_spread_h2": 0.50,
                           "ncaab_live_total_h2": 0.50}


def test_a_typo_is_a_data_error_and_the_extremes_history_holds_are_not():
    from models import ncaab_quote_bounds as qb
    assert "outside 90 to 220" in qb.problem("totals", 1465.0, (-110, -110))
    assert qb.problem("totals", 146.5, (-110, -110)) is None
    assert qb.problem("totals", 194.0, (-4500, 400)) is None          # history's highest, its widest prices
    assert "outside -60 to 60" in qb.problem("spreads", -335.0, (-110, -110))
    assert qb.problem("spreads", -47.5, (-375, 285)) is None           # history's widest
    assert "outside 40 to 120" in qb.problem("totals_h1", 7.5, (-110, -110))
    assert qb.problem("totals_h1", 75.0, (-110, -110)) is None
    assert "outside -35 to 35" in qb.problem("spreads_h1", -45.5, (-110, -110))
    assert qb.problem("spreads_h1", -27.5, (-286, 188)) is None
    assert "beyond +/-100000" in qb.problem("h2h", None, (-190, 250000))
    assert qb.problem("h2h", None, (-100000, 5000)) is None             # 975 such prices in history
    # a missing value is the loaders' to drop, not a data error
    assert qb.problem("totals", float("nan"), (None, -110)) is None
    with pytest.raises(ValueError):
        qb.problem("total", 140.5, ())


def test_split_keeps_order_and_says_why():
    from models import ncaab_quote_bounds as qb
    q = pd.DataFrame({"game_id": ["g", "g", "g"], "bookmaker": ["a", "b", "c"],
                      "line": [-4.5, -335.0, float("nan")], "p1": [-110, -110, -110],
                      "p2": [-110, 250000, -110]})
    kept, bad = qb.split(q, "spreads")
    assert list(kept["bookmaker"]) == ["a", "c"]
    assert list(bad["bookmaker"]) == ["b"] and bad["why"].iloc[0] == "line -335 outside -60 to 60"
    (line,) = qb.describe(bad)
    assert line == "g b spreads line -335 prices -110/+250000: line -335 outside -60 to 60"


# ── the totals card ──────────────────────────────────────────────────────────

def _totals_run(monkeypatch, line=125.5, op=-110, up=-110):
    """The totals card with this quote as both DraftKings' first post and its
    standing number (models/ncaab_total_card: a first post is bet only while
    it stands)."""
    from tests.test_ncaab_total_blend import _art, _card_run, _prepared, _quote, _season
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
    import models.ncaab_total_blend as nb
    from tests.test_ncaab_total_blend import _art, _late_target, _prepared, _quote, _season
    games, box = _season()
    sg, b = _prepared(games, box)
    t, at = _late_target(sg)
    gid = t["game_id"].iloc[0]
    (d,) = nb.decide(t, {gid: _quote(gid, line=1465.0, at=at)}, sg, b,
                     _art(sorted(set(sg["home_espn_id"]))), 0.04)
    assert d.status == "out_of_range" and d.priced is None
    assert "line 1465 outside 90 to 220" in d.detail


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
    assert any("data-error cap 0.25" in x for x in logs)


# ── the spread card ──────────────────────────────────────────────────────────

FLAT = [("g", b, 30, -10.0, -110, -110) for b in
        ("draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers")]


def test_a_minus_335_spread_is_dropped_before_the_consensus(monkeypatch, logs):
    from tests.test_ncaab_spread_market import GAMES, _rows, _wire
    rows = _rows(FLAT + [("g", "hardrockbet", 30, -335.0, -110, -110)])
    card, got = _wire(monkeypatch, dict(GAMES), rows=rows)
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    (d,) = got["decisions"]
    # No bet; the game priced on the clean books is a NONE row (the All board),
    # never at the dropped quote's book.
    assert out["bets"] == 0 and d.status == "below_cut"
    assert [(r["signal_type"], r["decision_book"]) for r in got["rows"]] == [("NONE", d.best["bookmaker"])]
    assert d.best["bookmaker"] != "hardrockbet" and d.best["cons"] == -10.0
    assert out["diag"]["quotes_dropped"] == 1
    assert {q["book"]: q["flag"] for q in d.quotes}["hardrockbet"] == "out_of_range"
    assert "hardrockbet -335 (line -335 outside -60 to 60)" in d.detail
    assert any("g hardrockbet spreads line -335" in x for x in logs)


def test_a_dropped_quote_is_not_replaced_by_the_books_older_row():
    import models.ncaab_book_quotes as bq
    from tests.test_ncaab_spread_market import _rows
    rows = _rows([("g", "fanduel", 50, -9.5, -110, -110), ("g", "fanduel", 10, -335.0, -110, -110),
                  ("g", "betmgm", 10, -10.0, -110, -110)])
    q = bq.standing_quotes(rows)
    assert list(q["bookmaker"]) == ["betmgm"]
    assert list(bq.dropped_quotes(rows)["line"]) == [-335.0]


def test_a_normal_spread_slate_still_bets(monkeypatch):
    from tests.test_ncaab_spread_market import GAMES, GOOD, _rows, _wire
    card, got = _wire(monkeypatch, dict(GAMES), rows=_rows(GOOD))
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert out["bets"] == 1 and got["rows"][0]["decision_book"] == "betrivers"
    assert out["diag"]["quotes_dropped"] == 0


def test_an_absurd_spread_edge_is_recorded_not_bet_and_fails_the_run(monkeypatch, logs):
    from tests.test_ncaab_spread_market import GAMES, _rows, _wire
    rows = _rows(FLAT[:4] + [("g", "betrivers", 30, -10.0, -110, +900)])
    card, got = _wire(monkeypatch, dict(GAMES), rows=rows)
    with pytest.raises(card.CardIncomplete, match="edge_cap"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    (d,) = got["decisions"]
    assert d.status == "edge_cap" and got["rows"] == [] and "edge_cap" in card.FINAL
    assert any("data-error cap 0.25" in x for x in logs)


# ── the moneyline card ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ml_table():
    import models.ncaab_moneyline_own_spread as om
    return om.load_artifact()["table"]


def test_a_250000_moneyline_is_dropped_and_never_bet(monkeypatch, logs, ml_table):
    from tests.test_ncaab_moneyline_own_spread import GAMES, _wire
    # Hard Rock's typo: -300000 / +250000, its own spread home -25. Without the
    # bound the pair passes the implied-sum check (1.0001) and the +250000 side
    # is priced off the spread.
    sp = [("g", b, 20, -25.5, -110.0, -110.0) for b in ("draftkings", "fanduel", "hardrockbet")]
    ml = [("g", "hardrockbet", 10, None, -300000.0, 250000.0),
          ("g", "draftkings", 10, None, -10000.0, 2500.0),
          ("g", "fanduel", 10, None, -10000.0, 2500.0)]
    card, got = _wire(monkeypatch, ml_table, dict(GAMES), ml=ml, sp=sp)
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    (d,) = got["decisions"]
    # No bet; any row is NONE and never at the dropped quote's book.
    assert out["bets"] == 0
    assert all(r["signal_type"] == "NONE" and r["decision_book"] != "hardrockbet" for r in got["rows"])
    assert not (d.best and d.best.get("bookmaker") == "hardrockbet")
    assert out["diag"]["quotes_dropped"] == 1
    assert any(q.get("flags") == ["out_of_range"] and q["book"] == "hardrockbet" for q in d.quotes)
    assert any("g hardrockbet h2h prices -300000/+250000" in x for x in logs)


def test_a_minus_100000_moneyline_is_still_a_quote(ml_table):
    import models.ncaab_book_quotes as bq
    from tests.test_ncaab_moneyline_own_spread import _rows
    rows = _rows([("g", "draftkings", 10, None, -100000.0, 5000.0)])
    import models.ncaab_moneyline_own_spread as om
    assert len(bq.standing_quotes(rows, books=om.REF_BOOKS, need_line=False)) == 1
    assert not len(bq.dropped_quotes(rows, books=om.REF_BOOKS, need_line=False))


def test_an_absurd_moneyline_edge_is_recorded_not_bet_and_fails_the_run(monkeypatch, logs, ml_table):
    from tests.test_ncaab_moneyline_own_spread import GAMES, _wire
    sp = [("g", "betrivers", 20, -1.0, -110.0, -110.0)]
    ml = [("g", "betrivers", 10, None, -1200.0, 900.0)]     # an even game's dog at +900
    card, got = _wire(monkeypatch, ml_table, dict(GAMES), ml=ml, sp=sp)
    with pytest.raises(card.CardIncomplete, match="edge_cap"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    (d,) = got["decisions"]
    assert d.status == "edge_cap" and got["rows"] == [] and "edge_cap" in card.FINAL
    assert any("data-error cap 0.25" in x for x in logs)


# ── the first-half spread card ───────────────────────────────────────────────

HOME, AWAY = "Kansas", "Duke"
GID = "NCAAB_2026-11-10_duke_kansas"
TIP = datetime(2026, 11, 11, 0, 0, tzinfo=UTC)


def _fh_quotes(*rows):
    return pd.DataFrame([{"game_id": GID, "bookmaker": b, "spread_home": ln, "home_price": hp,
                          "away_price": ap, "home_link": f"{b}/h", "away_link": f"{b}/a",
                          "snapshot_at": "x"} for b, ln, hp, ap in rows])


def _fht_quotes(*rows):
    return pd.DataFrame([{"game_id": GID, "bookmaker": b, "total_line": ln, "over_price": op,
                          "under_price": up, "over_link": f"{b}/o", "under_link": f"{b}/u",
                          "snapshot_at": "x"} for b, ln, op, up in rows])


class _Null:
    def close(self):
        pass


def _fh_wire(monkeypatch, quotes, fetch_at, fg=None, total=False):
    """run_card read through stubs: one game, one decision fetch at fetch_at.
    total=True runs the first-half total card instead of the spread card."""
    from scripts import ncaab_first_half_spread_card as spread_card
    from scripts import ncaab_first_half_total_card as total_card
    from scripts import ncaab_first_half_window as win
    import models.scorer as scorer
    import models.ncaab_first_half_spread as fh
    import models.ncaab_first_half_total as ft
    if total:
        from tests.test_ncaab_first_half_total import T
        card, mod = total_card, ft
        art = {"map": {"a": -2.0, "b": 0.485}, "_T": T,
               "tilt": {"alpha": 0.0, "beta": 0.0, "k": 236.0, "w_prev": 0.5},
               "prior_team_sums": {}}
        fg = fg or {"cons": 140.0, "nb": 5}
    else:
        from tests.test_ncaab_first_half_spread import T
        card, mod = spread_card, fh
        art = {"map": {"a": 0.0, "b": 0.56}, "_T": T,
               "tilt": {"alpha": 0.0, "beta": 0.0, "k": 782.2, "w_prev": 0.5},
               "prior_team_sums": {}}
        fg = fg or {"cons": -8.0, "nb": 5}
    got = {}
    monkeypatch.setenv("RUN_NCAAB_FIRST_HALF", "1")
    monkeypatch.setattr(card, "enabled", lambda: True)
    monkeypatch.setattr(card, "get_connection", lambda: _Null())
    slate = {GID: {"season": 2027, "game_date": "2026-11-10", "tip": TIP,
                   "commence_time": "2026-11-11T00:00:00Z", "home": HOME, "away": AWAY}}
    monkeypatch.setattr(win, "slate", lambda conn, now: slate)
    monkeypatch.setattr(win, "listed", lambda conn, ids: set(ids))
    monkeypatch.setattr(card, "ensure_decisions_table", lambda conn: None)
    monkeypatch.setattr(card, "decided_games", lambda conn, ids: set())
    monkeypatch.setattr(card.feed, "decision_fetches",
                        lambda conn, ids, now, **kw: {GID: (fetch_at, {})})
    monkeypatch.setattr(card, "decision_quotes", lambda conn, cuts: quotes)
    monkeypatch.setattr(card, "fg_consensus", lambda conn, cuts: {GID: fg})
    monkeypatch.setattr(card, "artifact", lambda season: art)
    tg = pd.DataFrame(columns=list(spread_card.TEAM_COLS))
    sg = pd.DataFrame({"game_id": pd.Series(dtype=object), "home_team": pd.Series(dtype=object),
                       "away_team": pd.Series(dtype=object), "home_score": pd.Series(dtype=float),
                       "tip": pd.Series(dtype="datetime64[ns, UTC]")})
    monkeypatch.setattr(card, "team_games", lambda conn, season, now, write: (tg, sg))
    monkeypatch.setattr(mod, "team_effects", lambda res, season, prior, targets, k, w: pd.DataFrame(
        {"game_id": [GID], "tau_home": [0.0], "tau_away": [0.0], "n_home": [0], "n_away": [0]}))
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    monkeypatch.setattr(card, "publish", lambda conn, rows, decided: got.update(
        rows=rows, decided=decided) or (len(rows), len(decided)))
    return card, got


GENEROUS = ("fanduel", -1.5, +100, -120)     # M = +8 makes home -1.5 at even money a bet


def test_a_normal_first_half_fetch_still_bets(monkeypatch):
    card, got = _fh_wire(monkeypatch, _fh_quotes(GENEROUS), TIP - timedelta(minutes=10))
    out = card.run_card(do_publish=True, now=TIP - timedelta(minutes=9, seconds=30))
    assert out["bets"] == 1 and got["rows"][0]["decision_book"] == "fanduel"
    assert out["diag"]["quotes_dropped"] == 0


def test_a_first_half_line_beyond_35_is_dropped_and_never_bet(monkeypatch, logs):
    q = _fh_quotes(("betmgm", -45.5, -110, -110), ("draftkings", -4.5, -110, -110))
    card, got = _fh_wire(monkeypatch, q, TIP - timedelta(minutes=10))
    out = card.run_card(do_publish=True, now=TIP - timedelta(minutes=9, seconds=30))
    (rec,) = got["decided"]
    # No bet; any row is NONE at the decision's book, never the dropped one.
    assert out["bets"] == 0 and rec["book"] != "betmgm"
    assert all(r["signal_type"] == "NONE" and r["decision_book"] == rec["book"] for r in got["rows"])
    assert out["diag"]["quotes_dropped"] == 1
    assert "betmgm -45.5 (line -45.5 outside -35 to 35)" in rec["detail"]
    assert any(f"{GID} betmgm spreads_h1 line -45.5" in x for x in logs)


def test_an_absurd_first_half_edge_is_recorded_not_bet_and_fails_the_run(monkeypatch, logs):
    q = _fh_quotes(("fanduel", -1.5, +5000, -120))
    card, got = _fh_wire(monkeypatch, q, TIP - timedelta(minutes=10))
    with pytest.raises(card.CardIncomplete, match="data-error cap"):
        card.run_card(do_publish=True, now=TIP - timedelta(minutes=9, seconds=30))
    (rec,) = got["decided"]
    assert rec["status"] == "edge_cap" and got["rows"] == [] and rec["n_bets"] == 0


def test_a_full_game_spread_typo_never_enters_the_first_half_consensus():
    import models.ncaab_first_half_spread as fh
    t = pd.Timestamp(datetime(2026, 11, 10, 20, tzinfo=UTC))
    rows = pd.DataFrame([("g", "draftkings", t, -4.0), ("g", "fanduel", t, -4.0),
                         ("g", "betmgm", t, -335.0)], columns=["game_id", "bookmaker", "ts", "line"])
    cut = pd.DataFrame({"game_id": ["g"], "cutoff": [t + pd.Timedelta(hours=1)]})
    c = fh.asof_consensus(rows, cut, market="spreads")
    assert c.iloc[0]["cons"] == -4.0 and c.iloc[0]["nb"] == 2
    tot = rows.assign(line=[146.5, 145.5, 1465.0])
    assert fh.asof_consensus(tot, cut, market="totals").iloc[0]["cons"] == 146.0


def test_the_card_reads_the_full_game_consensus_through_the_bounds(logs):
    from scripts import ncaab_first_half_spread_card as card
    cut = datetime(2026, 11, 10, 23, 50, tzinfo=UTC)

    class C:
        def execute(self, sql, params):
            class R:
                def fetchall(self_inner):
                    return [("g", "draftkings", "2026-11-10T23:00:00Z", -4.0),
                            ("g", "fanduel", "2026-11-10T23:00:00Z", -5.0),
                            ("g", "betmgm", "2026-11-10T23:00:00Z", -335.0)]
            return R()
    got = card.fg_consensus(C(), {"g": cut})
    assert got == {"g": {"cons": -4.5, "nb": 2}}
    assert any("g betmgm spreads line -335" in x for x in logs)


# ── the first-half card's freshness guard (the first-half total card's rule) ─

def test_a_decision_fetch_more_than_five_minutes_old_is_missed_never_bet(monkeypatch):
    """The fetch landed ten minutes before tip, inside its window, but the run
    came six minutes later: its prices may be gone, so the game is missed."""
    card, got = _fh_wire(monkeypatch, _fh_quotes(GENEROUS), TIP - timedelta(minutes=10))
    with pytest.raises(card.CardIncomplete, match="more than 5 minutes after it"):
        card.run_card(do_publish=True, now=TIP - timedelta(minutes=4))
    assert "rows" not in got or got["rows"] == []
    assert card.MAX_DECISION_DELAY_MIN == 5.0


def test_a_decision_fetch_five_minutes_old_still_decides(monkeypatch):
    card, got = _fh_wire(monkeypatch, _fh_quotes(GENEROUS), TIP - timedelta(minutes=10))
    out = card.run_card(do_publish=True, now=TIP - timedelta(minutes=5))
    assert out["bets"] == 1


# ── the first-half total card (live from 2026-11-03, PR #1137) ───────────────

FHT_AT = TIP - timedelta(minutes=60)
FHT_NOW = TIP - timedelta(minutes=59, seconds=30)
UNDER = ("fanduel", 69.5, -120, +100)      # T 140 makes mu 65.9: the under at even money bets


def test_a_normal_first_half_total_still_bets(monkeypatch):
    card, got = _fh_wire(monkeypatch, _fht_quotes(UNDER), FHT_AT, total=True)
    out = card.run_card(do_publish=True, now=FHT_NOW)
    assert out["bets"] == 1 and got["rows"][0]["decision_book"] == "fanduel"
    assert out["diag"]["quotes_dropped"] == 0


def test_a_first_half_total_of_7_5_is_dropped_and_never_bet(monkeypatch, logs):
    q = _fht_quotes(("betmgm", 7.5, -110, -110), ("draftkings", 66.0, -110, -110))
    card, got = _fh_wire(monkeypatch, q, FHT_AT, total=True)
    out = card.run_card(do_publish=True, now=FHT_NOW)
    (rec,) = got["decided"]
    # No bet; any row is NONE at the decision's book, never the dropped one.
    assert out["bets"] == 0 and rec["book"] != "betmgm"
    assert all(r["signal_type"] == "NONE" and r["decision_book"] == rec["book"] for r in got["rows"])
    assert out["diag"]["quotes_dropped"] == 1
    assert "betmgm 7.5 (line 7.5 outside 40 to 120)" in rec["detail"]
    assert any(f"{GID} betmgm totals_h1 line 7.5" in x for x in logs)


def test_an_absurd_first_half_total_edge_is_recorded_not_bet_and_fails_the_run(monkeypatch, logs):
    q = _fht_quotes(("fanduel", 69.5, -120, +5000))
    card, got = _fh_wire(monkeypatch, q, FHT_AT, total=True)
    with pytest.raises(card.CardIncomplete, match="data-error cap"):
        card.run_card(do_publish=True, now=FHT_NOW)
    (rec,) = got["decided"]
    assert rec["status"] == "edge_cap" and got["rows"] == [] and rec["n_bets"] == 0


def test_the_total_card_reads_the_full_game_total_through_the_bounds(logs):
    from scripts import ncaab_first_half_total_card as card
    cut = datetime(2026, 11, 10, 23, 0, tzinfo=UTC)

    class C:
        def execute(self, sql, params):
            class R:
                def fetchall(self_inner):
                    return [("g", "draftkings", "2026-11-10T22:30:00Z", 146.5),
                            ("g", "fanduel", "2026-11-10T22:30:00Z", 145.5),
                            ("g", "betmgm", "2026-11-10T22:30:00Z", 1465.0)]
            return R()
    got = card.fg_consensus(C(), {"g": cut})
    assert got == {"g": {"cons": 146.0, "nb": 2}}
    assert any("g betmgm totals line 1465" in x for x in logs)

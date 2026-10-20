"""Closing-line value for a home team-total bet (nba_team_total_luck).

The only team-total rows a game has are the ones this model's own feed wrote
(data/ingestors/nba_team_total_odds.py): the decision fetch about 55 minutes
before tip, filed 'open', and the closing snapshot 12-25 minutes before tip,
filed 'close'. The decision fetch is the price the bet was taken at, so it can
never be its close. Read as one, a game whose close was never stored (the call
failed, or the bet book pulled the market before it) got a closing-line value
of exactly 0.0 and "did not beat the close", stamped final and never revisited.
So a team total's close is read from 'close' rows only, in the Python capture
(tracking/paper_tracker._closing_odds) and in the SQL recompute
(data/migrations/clv_standard_v2_2026_10_14.sql). A pick with no close is left
unmeasured.

The rows here are built by the feed's own parser from hand-made responses; the
connection is tests/test_clv_price_taken.py's fake, which also honours the
snapshot_type filter. No network, no database.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from data.ingestors.nba_team_total_odds import event_rows  # noqa: E402
from tests.test_clv_price_taken import _Conn, _pick  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402
from tracking.clv_math import same_book_clv  # noqa: E402

GID = "NBA_2026-10-10_BOS_MIL"
TIP = "2026-10-10T23:30:00Z"
DECIDE_AT = datetime(2026, 10, 10, 22, 35, tzinfo=timezone.utc)   # 55 minutes out
CLOSE_AT = datetime(2026, 10, 10, 23, 12, tzinfo=timezone.utc)    # 18 minutes out
S_DEC, S_CLO = "2026-10-10T22:33:00Z", "2026-10-10T23:10:00Z"
MIGRATION = ROOT / "data" / "migrations" / "clv_standard_v2_2026_10_14.sql"

_SNAP = re.compile(r"snapshot_type\s*(=|!=|<>)\s*'(\w+)'")


class _SnapConn(_Conn):
    """_Conn, plus the snapshot_type condition of each odds read. A read that
    names no snapshot_type would take an in-play row, so it is refused."""

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "FROM odds" not in s:
            return super().execute(sql, params)
        m = _SNAP.search(s)
        assert m, f"an odds read with no snapshot_type condition: {s[:120]}"
        op, kind = m.groups()
        keep = self.quotes
        self.quotes = [q for q in keep
                       if (q[3].get("snapshot_type") == kind) == (op == "=")]
        try:
            return super().execute(sql, params)
        finally:
            self.quotes = keep


def _oc(side, team, price, point):
    return {"name": side, "description": team, "price": price, "point": point}


def _book(key, stamp, rungs):
    """One book's team totals: `rungs` (point, over, under) for Milwaukee, the
    home team, and one Boston rung."""
    outs = []
    for point, over, under in rungs:
        outs += [_oc("Over", "Milwaukee Bucks", over, point),
                 _oc("Under", "Milwaukee Bucks", under, point)]
    outs += [_oc("Over", "Boston Celtics", -110, 110.5), _oc("Under", "Boston Celtics", -110, 110.5)]
    return {"key": key, "last_update": stamp,
            "markets": [{"key": "team_totals", "last_update": stamp, "outcomes": outs}]}


# FanDuel, the book taken, hangs one number; Pinnacle the same number.
DECISION = [_book("fanduel", S_DEC, [(115.5, -112, -108)]),
            _book("pinnacle", S_DEC, [(115.5, -110, -104)])]


def _quotes(close_books):
    """The odds rows the feed stores for the decision fetch, and for the close
    when `close_books` is not None, as _Conn's (book, market, at, cols)."""
    out = []
    for kind, books, at in (("open", DECISION, DECIDE_AT), ("close", close_books, CLOSE_AT)):
        if books is None:
            continue
        main, alt, _ages = event_rows({"bookmakers": books}, GID, "MIL", "BOS", kind, at)
        for r in main + alt:
            cols = {k: r.get(k) for k in ("home_price", "away_price", "draw_price",
                                          "spread_home", "total_line", "over_price",
                                          "under_price")}
            out.append((r["bookmaker"], r["market"], r["snapshot_at"],
                        {**cols, "snapshot_type": r["snapshot_type"]}))
    return out


def _team_total_pick(**kw):
    base = dict(pick_id=7, game_id=GID, model_id="nba_team_total_luck", pick_side="under",
                dk_odds=None, commence_time=TIP,
                pick_label="BOS @ MIL — MIL Team Total Under 115.5", scored_line=115.5,
                created_at="2026-10-10 22:36:00+00", prop_market=None, clv_method=None,
                decision_odds=-108.0, decision_book="fanduel", game_date="2026-10-10",
                game_time=TIP)
    base.update(kw)
    return base


def _capture(close_books, **kw):
    conn = _SnapConn([_team_total_pick(**kw)], _quotes(close_books))
    n = pt._capture_clv(conn, "2026-10-10", "TS")
    return n, conn.updates


def test_a_close_at_the_same_number_is_graded_against_the_bet_book_s_close():
    n, (u,) = _capture([_book("fanduel", S_CLO, [(115.5, 100, -120)]),
                        _book("pinnacle", S_CLO, [(115.5, 102, -116)])])
    assert n == 1
    assert (u["clv_pct"], u["clv_beat_close"]) == (same_book_clv(-108.0, -120)[0], True)
    assert (u["closing_dk_odds"], u["closing_line"], u["clv_close_book"]) == (-120, 115.5, "fanduel")
    assert u["pinnacle_close_odds"] == -116 and u["market_clv_pct"] is not None


def test_with_no_close_stored_the_pick_is_left_unmeasured():
    """RULE: the decision fetch is not the close. Watched failing on the old
    read, which wrote clv_pct 0.0 and clv_beat_close False off the pick's own
    quote, and the market-edge column off Pinnacle's decision quote."""
    n, updates = _capture(None)
    assert (n, updates) == (0, [])


def test_a_close_without_the_bet_book_measures_only_the_market_edge():
    """FanDuel pulled its team total before the close; Pinnacle still hung
    one. The headline is not measured (not 0.0), the market edge is, and the
    capture does not crash on the missing bet-book close."""
    n, (u,) = _capture([_book("pinnacle", S_CLO, [(115.5, 102, -116)])])
    assert n == 1
    assert (u["clv_pct"], u["clv_beat_close"], u["closing_dk_odds"], u["clv_close_book"]) == (
        None, None, None, None)
    assert u["pinnacle_close_odds"] == -116 and u["market_clv_pct"] is not None


def test_a_number_that_moved_at_the_close_is_line_value_not_price_value():
    """FanDuel's main number moved 115.5 -> 114.5 (its 115.5 now an alternate
    rung): one point toward the under, and no same-number price comparison."""
    n, (u,) = _capture([_book("fanduel", S_CLO, [(113.5, -135, 105), (114.5, -110, -110),
                                                  (115.5, 120, -150)]),
                        _book("pinnacle", S_CLO, [(114.5, -108, -106)])])
    assert n == 1
    assert (u["clv_pct"], u["line_clv_pts"], u["closing_line"]) == (None, 1.0, 114.5)
    assert u["pinnacle_close_odds"] is None and u["market_clv_pct"] is None


def test_every_other_market_still_reads_its_newest_pre_game_row():
    """The close-only read is the team totals' own: a full-game total's
    newest pre-game row, filed 'open', is still its close."""
    q = [("betmgm", "totals", "2026-09-20T23:00:00Z",
          dict(total_line=8.5, over_price=-118, under_price=-102, snapshot_type="open")),
         ("betmgm", "totals", "2026-09-20T23:01:00Z",
          dict(total_line=8.5, over_price=-150, under_price=120, snapshot_type="in_play"))]
    conn = _SnapConn([_pick()], q)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    assert conn.updates[0]["closing_dk_odds"] == -118


@pytest.mark.parametrize("model_id, market, side, line", [
    ("mlb_over_under", "totals", "over", 8.5),
    ("nba_team_total_luck", "team_totals_home", "under", 115.5),
])
def test_a_line_pick_with_only_a_pinnacle_close_does_not_crash(model_id, market, side, line):
    """The bet book has no pre-start row, Pinnacle has one at the number. The
    capture used to raise AttributeError reading the bet book's line off
    None, and settle_picks runs the capture before it grades, so one such
    pick stopped game settlement for the date."""
    q = [("pinnacle", market, "2026-09-20T23:00:00Z",
          dict(total_line=line, over_price=-110, under_price=-104, snapshot_type="close"))]
    p = _pick(model_id=model_id, pick_side=side, scored_line=line, decision_book="fanduel")
    conn = _SnapConn([p], q)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    (u,) = conn.updates
    assert (u["clv_pct"], u["closing_line"], u["line_clv_pts"]) == (None, None, None)
    assert u["pinnacle_close_odds"] == (-110 if side == "over" else -104)


def test_a_clv_failure_does_not_stop_settlement(monkeypatch):
    """RULE: closing-line value is optional, grading is not. A capture that
    raises is rolled back to its savepoint (tracking.paper_tracker._clv_attempt),
    and the game, prop, UFC and golf picks are still graded on the same pass."""
    calls: list[str] = []

    class Conn:
        def execute(self, sql, *a, **k):
            calls.append(" ".join(str(sql).split()[:3]))

        def commit(self):
            calls.append("commit")

        def rollback(self):
            calls.append("rollback")

        def close(self):
            pass

    def boom(*a, **k):
        calls.append("capture")
        raise AttributeError("'NoneType' object has no attribute 'get'")

    zero = (0, 0, 0, 0, 0.0, 0.0)
    monkeypatch.setattr(pt, "get_connection", lambda: Conn())
    for name in ("_fetch_and_store_scores", "_void_postponed_mlb_picks", "_heal_stranded_mlb",
                 "_backfill_clv"):
        monkeypatch.setattr(pt, name, lambda *a, **k: None)
    monkeypatch.setattr(pt, "_capture_clv", boom)
    for name in ("_settle_game_picks_window", "_settle_prop_picks_window", "_settle_ufc_picks",
                 "_settle_golf_picks"):
        monkeypatch.setattr(pt, name, lambda *a, _n=name, **k: calls.append(_n) or zero)
    import data.ingestors.cfbd_ingestor as cfbd
    import data.ingestors.prop_box_scores as box
    import tracking.opening_signals as opening
    import tracking.parlay_track_record as parlay
    monkeypatch.setattr(cfbd, "mirror_stored_finals", lambda *a, **k: None)
    monkeypatch.setattr(box, "ensure_prop_box_scores", lambda *a, **k: {})
    monkeypatch.setattr(opening, "settle_opening_signals", lambda *a, **k: None)
    monkeypatch.setattr(parlay, "settle_parlay_track_record", lambda *a, **k: None)
    pt.settle_picks("2026-10-10")
    assert {"_settle_game_picks_window", "_settle_prop_picks_window", "_settle_ufc_picks",
            "_settle_golf_picks"} <= set(calls)
    before = calls[:calls.index("_settle_game_picks_window")]
    assert "capture" in before
    assert "ROLLBACK TO SAVEPOINT" in before[before.index("capture"):]


def _lateral(sql: str, alias: str) -> str:
    """The body of the LATERAL subquery the recompute names `alias`."""
    end = sql.index(f") {alias} ON TRUE")
    start = sql.rindex("LEFT JOIN LATERAL (", 0, end)
    return " ".join(sql[start:end].split())


@pytest.mark.parametrize("alias", ["bs", "bm", "ps"])
def test_the_sql_recompute_reads_a_team_total_close_from_close_rows_only(alias):
    """The migration's recompute (run on every apply) reads the bet book's
    close at the number (bs), its latest main number (bm) and Pinnacle's
    close (ps): each takes only 'close' rows for a team total, and every
    other market keeps its pre-game rows. Text, because the recompute runs
    only in Postgres; checked there with EXPLAIN."""
    body = _lateral(MIGRATION.read_text(encoding="utf-8"), alias)
    assert ("(s.game_market LIKE 'team_totals%' AND o.snapshot_type = 'close') OR "
            "(s.game_market NOT LIKE 'team_totals%' AND o.snapshot_type <> 'in_play')") in body

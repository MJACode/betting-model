"""The NCAAF in-play loop, the fast way (ncaaf_live/gameday.py; mike,
2026-11-13: "Move everything over to the fast way").

Pinned here:
  * DraftKings' moneyline and total come from its own board, each stamped
    where the board first showed it (the book's last_update meant the same);
  * the quote then carries DraftKings as its only book, so the engine decides
    at no stale copy of another book;
  * the game's DraftKings score travels with the quote: the loop prices a game
    only while it equals our state's score;
  * a stale feed, no feed or a failed read is None: the provider, as before.
"""
from __future__ import annotations

import pandas as pd

from ncaaf_live import gameday as GD

T0 = pd.Timestamp("2026-11-14T20:00:00Z")


def row(sec, h, a, ml=(-150.0, 130.0), total=(51.5, -110.0, -110.0)):
    return {"game_id": "g1", "read_at": T0 + pd.Timedelta(seconds=sec), "period_label": "2nd Quarter",
            "period": 2, "clock_s": 300.0, "home_score": h, "away_score": a, "spread_home": None,
            "spread_home_price": None, "spread_away_price": None, "total_line": total[0],
            "over_price": total[1], "under_price": total[2], "home_ml": ml[0], "away_ml": ml[1]}


class Src:
    def __init__(self, rows, last, ok=True, boom=False):
        self.rows, self.last, self.ok, self.boom = rows, last, ok, boom
        self.reset = lambda: None

    def last_read(self):
        if self.boom:
            raise RuntimeError("db down")
        return self.last, self.ok

    def reads(self, ids):
        return pd.DataFrame([r for r in self.rows if r["game_id"] in ids])


def test_the_board_gives_draftkings_markets_stamped_where_first_shown_and_its_score(monkeypatch):
    now = pd.Timestamp.now(tz="UTC")
    rows = [row(0, 7, 3), row(10, 7, 3, ml=(-160.0, 135.0)), row(20, 14, 3, ml=(-260.0, 210.0))]
    rows = [{**r, "read_at": now - pd.Timedelta(seconds=30) + (r["read_at"] - T0)} for r in rows]
    d = GD.dk_board_now(Src(rows, now - pd.Timedelta(seconds=2)), ["g1"])["g1"]
    assert d["score"] == (14, 3)
    assert (d["h2h"]["home"], d["h2h"]["away"]) == (-260, 210)
    assert pd.Timestamp(d["h2h"]["ts"]) == rows[2]["read_at"]       # the read that first showed it
    assert d["total"]["line"] == 51.5 and pd.Timestamp(d["total"]["ts"]) == rows[0]["read_at"]


def test_a_stale_feed_no_feed_or_a_failed_read_leaves_the_provider():
    now = pd.Timestamp.now(tz="UTC")
    assert GD.dk_board_now(Src([row(0, 7, 3)], now - pd.Timedelta(seconds=60)), ["g1"]) is None
    assert GD.dk_board_now(Src([row(0, 7, 3)], now, ok=False), ["g1"]) is None
    assert GD.dk_board_now(Src([], now, boom=True), ["g1"]) is None
    assert GD.dk_board_now(None, ["g1"]) is None


def test_the_quote_carries_draftkings_as_its_only_book():
    provider = {"h2h": {"home": -140, "away": 120, "ts": "old"}, "total": None, "commence_time": "x",
                "books": {"draftkings": {"h2h": {"home": -140, "away": 120, "ts": "old"}, "total": None},
                          "fanduel": {"h2h": {"home": -120, "away": 100, "ts": "old"}, "total": None}}}
    d = {"score": (14, 3), "h2h": {"home": -260, "away": 210, "ts": "new"}, "total": None}
    q = GD.with_dk(provider, d)
    assert q["h2h"]["ts"] == "new" and set(q["books"]) == {"draftkings"}
    assert q["commence_time"] == "x" and provider["books"]["fanduel"]          # the provider's left as it was
    assert set(GD.with_dk(None, d)["books"]) == {"draftkings"}                  # a game the provider lacked

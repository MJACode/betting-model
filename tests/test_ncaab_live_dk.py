"""NCAAB in-play bets decided on DraftKings' own board, within seconds
(mike, 2026-11-12: "This is live betting ... as close to Real time as possible").

Pinned here:
  * the feed (data/ingestors/dk_live_board.py) reads DraftKings' real board
    (a 2026-11-13 read, three live games): our home and away, the score, the
    clock, both sides' prices; a flipped game turns over; a row is written
    only when the score, period or a line changes; a game off the board and a
    suspended market leave no line behind; a refused read is a failed beat;
  * the quotes (models/ncaab_live_dk.py) carry the grade's rule: the stamp is
    the read where the number first showed, the state is DraftKings' score and
    clock at that read, a basket since the stamp makes it ineligible, and a
    quote first seen on the newest read is not yet confirmed;
  * the loop decides on DraftKings' board at the window's first tick, with no
    ESPN wait and no odds-provider call, at DraftKings' price; a stale feed
    falls back to the slow path; an unconfirmed quote waits one read.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from data.ingestors import dk_live_board as B
from models import ncaab_live_dk as DK
import models.ncaab_live_ig as M
import models.ncaab_live_loop as LP
from tests import _ncaab_live_synth as S
from tests.test_ncaab_live_loop import Clock, Db, FakeConn, FakeEspn, FakeFeed, books, slots_at

FIXTURE = Path(__file__).parent / "fixtures" / "dk_ncaab_board_2026-11-13.json"


def board():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ─── the feed ─────────────────────────────────────────────────────────────────

def test_the_real_board_parses_to_our_sides_score_clock_and_prices():
    evs = {e.name: e for e in B.parse_board(board())}
    assert set(evs) == {"West Florida @ Alabama A&M", "Montana State @ BYU", "New Mexico State @ UTEP"}
    byu = evs["Montana State @ BYU"]
    assert (byu.home_name, byu.away_name) == ("BYU", "Montana State")
    assert (byu.home_score, byu.away_score) == (70, 56)
    assert (byu.period_label, byu.period, byu.clock_s, byu.clock_running) == ("2nd Half", 2, 471.0, True)
    assert (byu.spread_home, byu.spread_home_price, byu.spread_away_price) == (-18.5, -125.0, -105.0)
    assert (byu.total_line, byu.over_price, byu.under_price) == (161.5, -105.0, -125.0)
    assert evs["West Florida @ Alabama A&M"].period == 3            # overtime: in no rule's phase
    assert evs["New Mexico State @ UTEP"].clock_running is False


def test_a_flipped_game_swaps_the_sides_and_turns_the_spread_over():
    byu = next(e for e in B.parse_board(board()) if e.home_name == "BYU")
    r = B.oriented(byu, flipped=True)
    assert (r["home_score"], r["away_score"]) == (56, 70)
    assert (r["spread_home"], r["spread_home_price"], r["spread_away_price"]) == (18.5, -105.0, -125.0)


def test_a_suspended_market_is_no_line():
    b = board()
    for m in b["markets"]:
        if m["name"] == "Spread":
            m["tags"] = list(m.get("tags") or []) + ["Suspended"]
    assert all(e.spread_home is None and e.total_line is not None for e in B.parse_board(b))


class Resp:
    def __init__(self, code, body=None):
        self.status_code, self._body = code, body

    def json(self):
        return self._body


class Sess:
    def __init__(self, bodies):
        self.bodies = list(bodies)

    def get(self, url, timeout=None):
        b = self.bodies.pop(0)
        return b if isinstance(b, Resp) else Resp(200, b)


class WriteConn:
    def __init__(self):
        self.rows, self.beats = [], []

    def executemany(self, sql, rows):
        self.rows.extend(dict(r) for r in rows)

    def execute(self, sql, params=None):
        if "dk_live_feed" in sql:
            self.beats.append(params)
        return self

    def commit(self):
        pass

    def close(self):
        pass


def make_board(bodies, clock):
    conn = WriteConn()
    ids = {"Alabama A&M": "G_AAMU", "BYU": "G_BYU", "UTEP": "G_UTEP"}
    b = B.Board("NCAAB", lambda: conn, lambda sport: Sess(bodies),
                lambda c: (lambda home, away, start: (ids[home], False) if home in ids else None), clock=clock)
    return b, conn


def test_a_row_is_written_only_when_the_score_or_a_line_changes():
    t = [pd.Timestamp("2026-11-13T03:00:00Z")]
    same = board()
    moved = board()
    for s in moved["selections"]:
        if s.get("outcomeType") == "Home" and s.get("points") == -18.5:
            s["displayOdds"]["american"] = "−130"
    gone = json.loads(json.dumps(moved))
    gone["events"] = [e for e in gone["events"] if e["name"] != "New Mexico State @ UTEP"]
    b, conn = make_board([board(), same, moved, gone, Resp(403)], clock=lambda: t[0])
    assert b.read()["written"] == 3 and len(conn.rows) == 3
    t[0] += pd.Timedelta(seconds=2.5)
    assert b.read()["written"] == 0                                  # nothing changed: the beat only
    t[0] += pd.Timedelta(seconds=2.5)
    assert b.read()["written"] == 1 and conn.rows[-1]["game_id"] == "G_BYU"
    assert conn.rows[-1]["spread_home_price"] == -130.0
    t[0] += pd.Timedelta(seconds=2.5)
    assert b.read()["written"] == 1
    last = conn.rows[-1]
    assert last["game_id"] == "G_UTEP" and last["spread_home"] is None and last["total_line"] is None
    assert last["home_score"] == 41                                  # the score it left with
    t[0] += pd.Timedelta(seconds=2.5)
    res = b.read()
    assert res["ok"] is False and conn.beats[-1][2] is False and "403" in conn.beats[-1][5]
    assert len(conn.beats) == 5                                      # every read beats, refused or not


# ─── the quotes ───────────────────────────────────────────────────────────────

T0 = pd.Timestamp("2026-11-13T00:00:00Z")


def read(sec, h, a, spread=(-6.5, -110.0, -110.0), total=(150.5, -110.0, -110.0), label="1st Half",
         clock=600.0, gid=S.GAME_ID):
    return {"game_id": gid, "read_at": T0 + pd.Timedelta(seconds=sec), "period_label": label,
            "period": B.period_of(label), "clock_s": 0.0 if label == "Halftime" else clock,
            "home_score": h, "away_score": a, "spread_home": spread[0], "spread_home_price": spread[1],
            "spread_away_price": spread[2], "total_line": total[0], "over_price": total[1],
            "under_price": total[2]}


def fouls(gid=S.GAME_ID):
    return {gid: pd.DataFrame({"game_id": [gid], "wallclock": [T0 - pd.Timedelta(minutes=5)],
                               "play_no": [1], "h_tf": [3], "a_tf": [8]})}


def test_the_stamp_is_the_first_read_of_the_number_and_the_state_is_dk_at_that_read():
    reads = pd.DataFrame([read(0, 12, 6, spread=(-5.5, -110.0, -110.0)), read(5, 14, 6, clock=590.0),
                          read(9, 14, 6, total=(151.5, -110.0, -110.0), clock=585.0)])
    qs = DK.quote_states_dk(reads, T0 + pd.Timedelta(seconds=12), fouls()).set_index("market")
    sp = qs.loc["spreads"]
    assert sp["stamp"] == T0 + pd.Timedelta(seconds=5) and sp["spread_home"] == -6.5
    assert (sp["h_pts"], sp["a_pts"], sp["clock_s"], sp["pts_since"]) == (14, 6, 590.0, 0.0)
    assert (sp["h_tf"], sp["a_tf"]) == (3.0, 8.0) and bool(sp["held"]) is True
    to = qs.loc["totals"]
    assert to["stamp"] == T0 + pd.Timedelta(seconds=9) and to["total_line"] == 151.5


def test_a_basket_since_the_stamp_and_an_unconfirmed_quote_are_flagged():
    reads = pd.DataFrame([read(0, 14, 6), read(5, 16, 6, total=(151.5, -110.0, -110.0))])
    qs = DK.quote_states_dk(reads, T0 + pd.Timedelta(seconds=5), fouls()).set_index("market")
    assert qs.loc["spreads", "pts_since"] == 2.0                 # the spread still stands from before the basket
    assert bool(qs.loc["totals", "held"]) is False               # first seen on the newest read


def test_halftime_is_the_break_and_reads_as_the_second_half_phase():
    reads = pd.DataFrame([read(0, 40, 30, label="Halftime")])
    qs = DK.quote_states_dk(reads, T0 + pd.Timedelta(seconds=3), fouls())
    prior = pd.DataFrame([{"game_id": S.GAME_ID, "mu_pre": 12.0, "T_pre": 145.0}])
    el = M.eligible_quotes(qs, prior, (DK.BOOK,))
    assert set(el["phase"]) == {"H2"} and set(qs["type_text"]) == {"End Period"}


def test_a_game_without_espn_fouls_is_left_out():
    reads = pd.DataFrame([read(0, 14, 6)])
    assert DK.quote_states_dk(reads, T0 + pd.Timedelta(seconds=3), {}).empty


def test_the_feed_is_trusted_only_while_its_last_read_is_seconds_old():
    assert DK.feed_is_live((T0, True), T0 + pd.Timedelta(seconds=DK.FEED_MAX_AGE_SEC))
    assert not DK.feed_is_live((T0, True), T0 + pd.Timedelta(seconds=DK.FEED_MAX_AGE_SEC + 1))
    assert not DK.feed_is_live((T0, False), T0)
    assert not DK.feed_is_live(None, T0)


# ─── the loop ─────────────────────────────────────────────────────────────────

class FakeDk:
    def __init__(self, last, rows):
        self.last, self.rows = last, rows
        self.calls = 0

    def last_read(self):
        self.calls += 1
        return self.last() if callable(self.last) else self.last

    def reads(self, ids):
        rows = self.rows() if callable(self.rows) else self.rows
        return pd.DataFrame([r for r in rows if r["game_id"] in ids])


def dk_window(art, monkeypatch, *, feed_age=1.0, stamp_after=5.0, rows=None):
    """The standard synthetic game (first half, 10:00 left, Duke 14-6) with
    DraftKings showing Duke -6.5 -110 / total 150.5 since `stamp_after`
    seconds after Duke's basket; the window opens 20 s after the basket."""
    plays = S.build_plays()
    w = S.wall_of(plays, 1, 600.0)
    slot = w + timedelta(seconds=20)
    db = Db().install(monkeypatch)
    clock = Clock(slot)
    stamp = pd.Timestamp(w) + pd.Timedelta(seconds=stamp_after)
    base = rows or [{"game_id": S.GAME_ID, "read_at": stamp, "period_label": "1st Half", "period": 1,
                     "clock_s": 595.0, "home_score": 14, "away_score": 6, "spread_home": -6.5,
                     "spread_home_price": -110.0, "spread_away_price": -110.0, "total_line": 150.5,
                     "over_price": -110.0, "under_price": -110.0}]
    dk = FakeDk(lambda: (pd.Timestamp(clock.now) - pd.Timedelta(seconds=feed_age), True), base)
    loop = LP.Loop(art, FakeEspn(plays, clock), FakeFeed(clock, lambda now: books(w + timedelta(seconds=5))),
                   lambda: FakeConn(), wait=90.0, recheck=60.0, sleep=clock.sleep, clock=clock,
                   slate_dates=lambda: [S.GAME_DATE], slots=slots_at(slot),
                   resolver_factory=lambda: (lambda home, away, commence: (S.GAME_ID, False)), dk=dk)
    return loop, db, clock, slot, dk


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


def test_the_window_decides_on_draftkings_board_at_once_with_no_wait_and_no_provider_call(art, monkeypatch):
    loop, db, clock, slot, dk = dk_window(art, monkeypatch)
    res = loop.tick()
    assert clock.now == slot                                         # no ESPN wait, no sleep at all
    assert loop.feed.calls == 0                                      # no odds-provider call
    row = db.ledger[(S.GAME_ID, M.SPREAD_H1)]
    assert row["outcome"] == "bet" and "DraftKings board" in row["reason"]
    assert pd.Timestamp(row["fetch_at"]) == pd.Timestamp(slot) - pd.Timedelta(seconds=1.0)
    p = db.picks[0]
    assert p["pick_label"] == "Duke -6.5 (live)" and p["scored_line"] == -6.5
    assert p["decision_book"] == "draftkings" and p["decision_odds"] == -110.0
    assert res["decisions"] == 1 and not res.get("fast")


def test_a_stale_draftkings_feed_falls_back_to_the_slow_path(art, monkeypatch):
    loop, db, clock, slot, dk = dk_window(art, monkeypatch, feed_age=DK.FEED_MAX_AGE_SEC + 5)
    loop.tick()
    assert loop.feed.calls == 1                                      # the provider fetch, as before
    assert (clock.now - slot).total_seconds() >= 150.0               # and the ESPN waits
    assert "DraftKings board" not in db.ledger[(S.GAME_ID, M.SPREAD_H1)]["reason"]


def test_a_quote_first_seen_on_the_newest_read_waits_one_read(art, monkeypatch):
    loop, db, clock, slot, dk = dk_window(art, monkeypatch, feed_age=0.0, stamp_after=20.0)
    res = loop.tick()                                                # the stamp IS the feed's last read
    assert res.get("fast") is True and db.ledger == {} and loop.feed.calls == 0
    clock.now = slot + timedelta(seconds=2.5)                        # the feed reads again; same number
    res = loop.tick()
    assert db.ledger[(S.GAME_ID, M.SPREAD_H1)]["outcome"] == "bet" and loop.feed.calls == 0
    assert not res.get("fast")


def test_a_basket_draftkings_has_not_repriced_waits_then_is_skipped_for_the_window(art, monkeypatch):
    plays = S.build_plays()
    w = pd.Timestamp(S.wall_of(plays, 1, 600.0))
    common = {"game_id": S.GAME_ID, "period_label": "1st Half", "period": 1, "clock_s": 595.0,
              "spread_home": -6.5, "spread_home_price": -110.0, "spread_away_price": -110.0,
              "total_line": 150.5, "over_price": -110.0, "under_price": -110.0}
    rows = [{**common, "read_at": w + pd.Timedelta(seconds=5), "home_score": 14, "away_score": 6},
            {**common, "read_at": w + pd.Timedelta(seconds=15), "home_score": 16, "away_score": 6}]
    loop, db, clock, slot, dk = dk_window(art, monkeypatch, rows=rows)
    assert loop.tick().get("fast") is True and db.ledger == {}
    clock.now = slot + timedelta(seconds=LP.DK_MAX_WAIT_SEC + 1)
    loop.tick()
    assert db.ledger == {} and db.skips and "not repriced" in db.skips[-1]["reason"]
    assert loop.feed.calls == 0                                      # done for the window, not re-decided slowly


def test_no_eligible_draftkings_quote_carries_the_game_and_the_slow_path_does_not_retry_it(art, monkeypatch):
    plays = S.build_plays()
    w = pd.Timestamp(S.wall_of(plays, 1, 600.0))
    rows = [{"game_id": S.GAME_ID, "read_at": w + pd.Timedelta(seconds=5), "period_label": "1st Half",
             "period": 1, "clock_s": 595.0, "home_score": 14, "away_score": 6, "spread_home": None,
             "spread_home_price": None, "spread_away_price": None, "total_line": None, "over_price": None,
             "under_price": None}]
    loop, db, clock, slot, dk = dk_window(art, monkeypatch, rows=rows)
    loop.tick()
    assert db.ledger == {} and db.carried and "DraftKings" in db.carried[-1]["reason"]
    assert loop.feed.calls == 0

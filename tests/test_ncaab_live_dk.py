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
        self.rows, self.beats, self.odds = [], [], []

    def executemany(self, sql, rows):
        # the board's lines also go to `odds` (dk_live_board.ODDS_LOG_SPORTS)
        (self.odds if "INSERT INTO odds" in sql else self.rows).extend(dict(r) for r in rows)

    def execute(self, sql, params=None):
        if "dk_live_feed" in sql:
            self.beats.append(params)
        return self

    def commit(self):
        pass

    def rollback(self):
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


# ─── as fast as it can safely go (mike, 2026-11-12: "can it run even faster") ─

def test_the_feed_reads_every_second_and_backs_off_on_a_refusal_then_comes_back():
    assert B.POLL_SEC == 1.0
    g = B.next_gap(1.0, refused=True, quiet_s=0.0, base=1.0)
    assert g == 2.0 and B.next_gap(4.0, True, 0.0, 1.0) == B.MAX_POLL_SEC
    assert B.next_gap(2.0, refused=False, quiet_s=30.0, base=1.0) == 2.0     # not quiet long enough
    assert B.next_gap(2.0, refused=False, quiet_s=61.0, base=1.0) == 1.0
    assert B.next_gap(1.0, refused=False, quiet_s=600.0, base=1.0) == 1.0    # never under the base


def test_a_second_feed_on_the_machine_finds_the_lock_and_exits():
    first = B.single_instance(port=47299)
    try:
        assert first is not None and B.single_instance(port=47299) is None
    finally:
        first.close()
    again = B.single_instance(port=47299)
    assert again is not None
    again.close()


def test_the_loop_wakes_at_the_window_not_on_its_next_tick():
    from datetime import datetime, timezone
    s = LP.Slots()                                        # each :00 and :30 minus 262 s
    at = datetime(2026, 11, 13, 3, 55, 0, tzinfo=timezone.utc)
    assert LP.seconds_to_next_window(s, at) == pytest.approx(38.0)            # opens 03:55:38
    assert LP.seconds_to_next_window(s, datetime(2026, 11, 13, 3, 56, 0, tzinfo=timezone.utc)) == 0.0


# ─── best line: another book's own page on the fast path (issue #1644) ───────
#
# mike, 2026-11-26: "We want best line". Pinned: a better price at another
# book's own page is the bet when it passes the book's gates; a number the
# book put up before the last basket, one far from DraftKings' number, and one
# not yet confirmed are dropped, never waited on; DraftKings' own bet is
# unchanged when nothing elsewhere beats it; a failed read of the other books
# leaves the window DraftKings only.

def book_quote(w, *, book="fanduel", stamp=6.0, shown=7.0, held=True, spread=(-6.5, 105.0, -125.0)):
    return {"game_id": S.GAME_ID, "market": "spreads", "book": book,
            "stamp": pd.Timestamp(w) + pd.Timedelta(seconds=stamp),
            "shown": pd.Timestamp(w) + pd.Timedelta(seconds=shown), "held": held,
            "spread_home": spread[0], "home_price": spread[1], "away_price": spread[2],
            "total_line": float("nan"), "over_price": float("nan"), "under_price": float("nan")}


class FakeBooks:
    def __init__(self, rows=None, fail=False):
        self.rows, self.fail, self.calls = rows or [], fail, 0

    def quotes(self, game_ids, at, markets=("spreads", "totals")):
        self.calls += 1
        if self.fail:
            raise RuntimeError("book_live_reads unreachable")
        from models import book_live_quotes as OB
        return pd.DataFrame([r for r in self.rows if r["game_id"] in game_ids], columns=OB.QUOTE_COLS)


def best_line_window(art, monkeypatch, quotes=None, fail=False, early_row=False):
    plays = S.build_plays()
    w = pd.Timestamp(S.wall_of(plays, 1, 600.0))
    rows = None
    if early_row:                      # DraftKings before Duke's basket: 12-6, -5.5 / 149.5
        common = {"game_id": S.GAME_ID, "period_label": "1st Half", "period": 1,
                  "spread_home_price": -110.0, "spread_away_price": -110.0,
                  "over_price": -110.0, "under_price": -110.0}
        rows = [{**common, "read_at": w - pd.Timedelta(seconds=10), "clock_s": 610.0, "home_score": 12,
                 "away_score": 6, "spread_home": -5.5, "total_line": 149.5},
                {**common, "read_at": w + pd.Timedelta(seconds=5), "clock_s": 595.0, "home_score": 14,
                 "away_score": 6, "spread_home": -6.5, "total_line": 150.5}]
    loop, db, clock, slot, dk = dk_window(art, monkeypatch, rows=rows)
    loop.books = FakeBooks(quotes(w) if quotes else [], fail=fail)
    return loop, db, w


def test_a_better_price_on_another_books_own_page_is_the_bet(art, monkeypatch):
    loop, db, _w = best_line_window(art, monkeypatch, quotes=lambda w: [book_quote(w)])
    loop.tick()
    row = db.ledger[(S.GAME_ID, M.SPREAD_H1)]
    assert row["outcome"] == "bet" and "fanduel's own page" in row["reason"]
    p = db.picks[0]
    assert p["pick_label"] == "Duke -6.5 (live)" and p["scored_line"] == -6.5
    assert (p["decision_book"], p["decision_odds"]) == ("fanduel", 105.0)
    assert p["dk_odds"] == -110.0 and p["line_book"] is None      # DraftKings hung the same number


def test_a_number_the_book_put_up_before_the_last_basket_is_not_taken(art, monkeypatch):
    # FanDuel's previous read (its stamp) was 5 s before Duke's basket
    loop, db, _w = best_line_window(art, monkeypatch, early_row=True,
                                    quotes=lambda w: [book_quote(w, stamp=-5.0, shown=7.0)])
    loop.tick()
    p = db.picks[0]
    assert (p["decision_book"], p["decision_odds"]) == ("draftkings", -110.0)
    assert "own page" not in db.ledger[(S.GAME_ID, M.SPREAD_H1)]["reason"]


def test_a_number_far_from_draftkings_is_not_taken(art, monkeypatch):
    loop, db, _w = best_line_window(art, monkeypatch,
                                    quotes=lambda w: [book_quote(w, spread=(-13.5, 150.0, -180.0))])
    loop.tick()
    assert db.picks[0]["decision_book"] == "draftkings"


def test_an_unconfirmed_number_elsewhere_neither_bets_nor_holds_the_game(art, monkeypatch):
    loop, db, _w = best_line_window(art, monkeypatch, quotes=lambda w: [book_quote(w, held=False)])
    res = loop.tick()
    assert not res.get("fast")                                   # decided now, not held a read
    assert db.picks[0]["decision_book"] == "draftkings"


def test_a_worse_price_elsewhere_leaves_draftkings_bet_exactly_as_it_was(art, monkeypatch):
    base_loop, base_db, _w = best_line_window(art, monkeypatch)
    base_loop.tick()
    loop, db, _w = best_line_window(art, monkeypatch,
                                    quotes=lambda w: [book_quote(w, spread=(-6.5, -120.0, 100.0))])
    loop.tick()
    keep = ("pick_label", "decision_book", "decision_odds", "scored_line", "model_probability", "decision_edge")
    assert {k: db.picks[0][k] for k in keep} == {k: base_db.picks[0][k] for k in keep}
    assert "own page" not in db.ledger[(S.GAME_ID, M.SPREAD_H1)]["reason"]


def test_a_failed_read_of_the_other_books_leaves_the_window_draftkings_only(art, monkeypatch):
    loop, db, _w = best_line_window(art, monkeypatch, fail=True)
    loop.tick()
    assert loop.books.calls == 1 and db.picks[0]["decision_book"] == "draftkings"


def test_a_book_the_platform_does_not_let_a_pick_name_is_never_the_bet(art, monkeypatch):
    import config
    monkeypatch.setattr(config, "BEST_LINE_BOOKMAKERS", [b for b in config.BEST_LINE_BOOKMAKERS if b != "fanduel"])
    loop, db, _w = best_line_window(art, monkeypatch, quotes=lambda w: [book_quote(w)])
    loop.tick()
    assert db.picks[0]["decision_book"] == "draftkings"


def test_another_books_state_is_draftkings_board_at_first_sight_and_its_basket_rule_runs_from_its_stamp():
    reads = pd.DataFrame([read(0, 12, 6, spread=(-5.5, -110.0, -110.0)), read(5, 14, 6, clock=590.0),
                          read(9, 14, 6, clock=585.0)])
    fetch = T0 + pd.Timedelta(seconds=20)
    q = pd.DataFrame([{"game_id": S.GAME_ID, "market": "spreads", "book": "betrivers",
                       "stamp": T0 + pd.Timedelta(seconds=6), "shown": T0 + pd.Timedelta(seconds=9.5),
                       "held": True, "spread_home": -6.5, "home_price": -105.0, "away_price": -115.0,
                       "total_line": float("nan"), "over_price": float("nan"), "under_price": float("nan")}])
    dk_qs = DK.quote_states_dk(reads, fetch, fouls())
    [r] = DK.quote_states_books(q, reads, fetch, fouls(), dk_qs).to_dict("records")
    assert (r["book"], r["clock_s"], r["h_pts"], r["a_pts"], r["pts_since"]) == ("betrivers", 585.0, 14, 6, 0.0)
    assert r["fetch_at"] == fetch and r["stamp"] == T0 + pd.Timedelta(seconds=9.5)
    stale = q.assign(stamp=T0 + pd.Timedelta(seconds=2))          # set before the 14-6 basket at 5 s
    assert DK.quote_states_books(stale, reads, fetch, fouls(), dk_qs).empty
    early = q.assign(stamp=T0 - pd.Timedelta(seconds=30))         # no DraftKings read that early
    assert DK.quote_states_books(early, reads, fetch, fouls(), dk_qs).empty
    assert DK.quote_states_books(q, reads, fetch, {}, dk_qs).empty  # no ESPN fouls: fail closed


def test_another_books_number_must_have_stood_ten_seconds_before_it_decides():
    # a book can move for a basket before DraftKings' board shows the score
    reads = pd.DataFrame([read(0, 12, 6, spread=(-5.5, -110.0, -110.0)), read(5, 14, 6, clock=590.0),
                          read(20, 14, 6, clock=575.0)])
    q = pd.DataFrame([{"game_id": S.GAME_ID, "market": "spreads", "book": "betrivers",
                       "stamp": T0 + pd.Timedelta(seconds=6), "shown": T0 + pd.Timedelta(seconds=8),
                       "held": True, "spread_home": -6.5, "home_price": -105.0, "away_price": -115.0,
                       "total_line": float("nan"), "over_price": float("nan"), "under_price": float("nan")}])
    stood = DK.quote_states_books(q, reads, T0 + pd.Timedelta(seconds=18), fouls())
    young = DK.quote_states_books(q, reads, T0 + pd.Timedelta(seconds=17), fouls())
    assert len(stood) == 1 and young.empty and DK.CONFIRM_SEC == 10.0

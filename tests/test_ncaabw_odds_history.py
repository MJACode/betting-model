"""The NCAABW odds history purchase (data/ingestors/ncaabw_odds_history.py):
what it asks the feed for, what it keeps of each answer, and that neither the
pruner nor the API roles can reach what it bought.

The contract: every snapshot the feed kept, each asked for ONCE by walking the
feed's own chain (an ask for a time with no snapshot is billed for the one
before). Pre-game quotes are stored change-only in `odds`; every in-play quote
of every snapshot in its own table, keyed on the snapshot; an event that lands
on no ESPN game is kept raw. No call is made here.
"""
from __future__ import annotations

import copy
import gzip
import json
from datetime import date, datetime

import pytest

import config
from data import anon_readable, prune_odds
from data.ingestors import ncaabw_odds_history as H
from data.ingestors import odds_ingestor


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _team(espn_id, school, mascot):
    return {"espn_id": espn_id, "school": school, "slug": school.lower().replace(" ", "-"),
            "mascot": mascot, "display_name": f"{school} {mascot}", "short_name": school,
            "abbreviation": None, "is_d1": True, "alt": []}


REGISTRY = [_team(41, "UConn", "Huskies"), _team(2550, "Seton Hall", "Pirates"),
            _team(2579, "South Carolina", "Gamecocks"), _team(99, "LSU", "Tigers")]
UCONN_SHU = "NCAABW_2026-01-24_uconn_seton-hall"          # UConn AT Seton Hall, 17:00Z tip
LSU_SC = "NCAABW_2026-01-24_lsu_south-carolina"           # neutral: the feed calls LSU home
GAMES = [
    {"game_id": UCONN_SHU, "game_date": "2026-01-24", "commence_time": "2026-01-24T17:00:00Z",
     "home_espn_id": 2550, "away_espn_id": 41},
    {"game_id": LSU_SC, "game_date": "2026-01-24", "commence_time": "2026-01-24T20:00:00Z",
     "home_espn_id": 2579, "away_espn_id": 99},
]
TIPS = {g["game_id"]: g["commence_time"] for g in GAMES}


def _book(key, updated, home, away, spread=None, total=None):
    markets = [{"key": "h2h", "last_update": updated, "outcomes": [
        {"name": home[0], "price": home[1]}, {"name": away[0], "price": away[1]}]}]
    if spread is not None:
        markets.append({"key": "spreads", "last_update": updated, "outcomes": [
            {"name": home[0], "price": -110, "point": spread},
            {"name": away[0], "price": -110, "point": -spread}]})
    if total is not None:
        markets.append({"key": "totals", "last_update": updated, "outcomes": [
            {"name": "Over", "price": -110, "point": total},
            {"name": "Under", "price": -110, "point": total}]})
    return {"key": key, "markets": markets}


def _event(eid, home, away, tip, books):
    return {"id": eid, "home_team": home, "away_team": away, "commence_time": tip,
            "bookmakers": books}


def _body(stamp, events, nxt=None):
    return {"timestamp": stamp, "next_timestamp": nxt, "data": events}


def _resolver():
    return H.EventResolver(REGISTRY, GAMES)


SHU = ("Seton Hall Pirates", 2500)
UCONN = ("UConn Huskies", -10000)


# ── the plan: which days ─────────────────────────────────────────────────────

def test_a_season_runs_from_two_days_before_its_first_game_to_the_day_after_its_last():
    games = [{"game_date": "2025-11-03"}, {"game_date": "2026-04-05"}]
    days = H.season_days(games, now=_t("2026-11-09T00:00:00Z"))[2026]
    assert days[0] == date(2025, 11, 1) and days[-1] == date(2026, 4, 6)
    assert len(days) == (date(2026, 4, 6) - date(2025, 11, 1)).days + 1


def test_no_day_is_asked_before_the_feeds_first_or_after_today():
    # 2024-25 opened 2024-11-04, but the feed's first women's tip is 2024-11-12
    old = H.season_days([{"game_date": "2024-11-04"}, {"game_date": "2025-04-06"}],
                        now=_t("2026-11-09T00:00:00Z"))[2025]
    assert old[0] == H.FIRST_HISTORY_DAY == date(2024, 11, 10)
    # a season still being played stops today
    live = H.season_days([{"game_date": "2026-11-02"}, {"game_date": "2027-03-01"}],
                         now=_t("2026-11-09T01:17:30Z"))[2027]
    assert live[0] == date(2026, 10, 31) and live[-1] == date(2026, 11, 9)


# ── step 1: walking the feed's chain ─────────────────────────────────────────

class _Resp:
    status_code = 200

    def __init__(self, body, billed=60):
        self._body, self.headers = body, {"x-requests-last": str(billed)}

    def json(self):
        return self._body


class _Fetched:
    def __init__(self, response):
        self.response, self.attempts = response, [response]


class _Feed:
    """The feed's rule: an ask is answered with the latest snapshot at or
    before it, and each answer names the next snapshot held."""

    def __init__(self, stamps):
        self.stamps = sorted(_t(s) for s in stamps)
        self.asked = []

    def __call__(self, params):
        when = _t(params["date"])
        self.asked.append(params["date"])
        ts = [s for s in self.stamps if s <= when][-1]
        later = [s for s in self.stamps if s > ts]
        nxt = later[0].strftime("%Y-%m-%dT%H:%M:%SZ") if later else None
        return _Fetched(_Resp(_body(ts.strftime("%Y-%m-%dT%H:%M:%SZ"), [{"id": "e"}], nxt)))


DAY = date(2026, 1, 24)
FAR = _t("2026-06-01T00:00:00Z")


def test_a_day_is_walked_snapshot_by_snapshot_and_never_asked_for_a_time_between(tmp_path):
    """The night gap is where a clock grid pays for the same snapshot again
    and again: the feed kept 02:15:38 and then nothing until 14:00:37."""
    feed = _Feed(["2026-01-23T23:55:37Z", "2026-01-24T00:00:37Z", "2026-01-24T00:05:37Z",
                  "2026-01-24T02:15:38Z", "2026-01-24T14:00:37Z", "2026-01-24T23:55:37Z",
                  "2026-01-25T00:00:37Z"])
    paid = H.walk_day(feed, tmp_path, DAY, FAR)
    assert feed.asked == ["2026-01-24T00:05:00Z", "2026-01-24T00:05:37Z", "2026-01-24T02:15:38Z",
                          "2026-01-24T14:00:37Z", "2026-01-24T23:55:37Z"]
    assert len(paid) == 5
    state = H.read_state(tmp_path, DAY)
    assert state["done"] and state["wasted_credits"] == 0
    assert [s["ts"] for s in state["snapshots"]] == [
        "2026-01-24T00:00:37Z", "2026-01-24T00:05:37Z", "2026-01-24T02:15:38Z",
        "2026-01-24T14:00:37Z", "2026-01-24T23:55:37Z"]
    assert all(s["credits"] == 60 for s in state["snapshots"])
    # each answer is on disk under its own snapshot time
    with gzip.open(H.snapshot_path(tmp_path, _t("2026-01-24T02:15:38Z")), "rt",
                   encoding="utf-8") as fh:
        assert json.load(fh)["timestamp"] == "2026-01-24T02:15:38Z"
    # a done day is never asked again
    assert H.walk_day(feed, tmp_path, DAY, FAR) == [] and len(feed.asked) == 5


def test_a_first_answer_from_an_earlier_day_is_not_stored_and_is_counted(tmp_path):
    """Nothing on the board at midnight UTC: the 00:05 ask is answered with
    yesterday's last snapshot. It is not this day's, and its next_timestamp
    says where this day starts."""
    feed = _Feed(["2026-01-23T04:10:37Z", "2026-01-24T15:00:37Z", "2026-01-25T16:00:37Z"])
    H.walk_day(feed, tmp_path, DAY, FAR)
    state = H.read_state(tmp_path, DAY)
    assert feed.asked == ["2026-01-24T00:05:00Z", "2026-01-24T15:00:37Z"]
    assert [s["ts"] for s in state["snapshots"]] == ["2026-01-24T15:00:37Z"]
    assert state["wasted_credits"] == 60 and state["done"]


def test_a_day_with_no_snapshot_at_all_costs_one_ask(tmp_path):
    feed = _Feed(["2026-01-23T04:10:37Z", "2026-01-25T16:00:37Z"])
    H.walk_day(feed, tmp_path, DAY, FAR)
    state = H.read_state(tmp_path, DAY)
    assert feed.asked == ["2026-01-24T00:05:00Z"]
    assert state["done"] and state["snapshots"] == [] and state["wasted_credits"] == 60


def test_the_present_day_stays_open_and_resumes_after_its_last_snapshot(tmp_path):
    feed = _Feed(["2026-01-24T00:00:37Z", "2026-01-24T00:05:37Z"])
    H.walk_day(feed, tmp_path, DAY, FAR)
    state = H.read_state(tmp_path, DAY)
    assert not state["done"] and state["next"] == "2026-01-24T00:10:37Z"
    assert len(state["snapshots"]) == 2
    # later the feed holds more: the walk picks up after what it has and
    # stores no snapshot twice
    feed.stamps += [_t("2026-01-24T00:10:37Z"), _t("2026-01-25T00:00:37Z")]
    H.walk_day(feed, tmp_path, DAY, FAR)
    state = H.read_state(tmp_path, DAY)
    assert state["done"]
    assert [s["ts"] for s in state["snapshots"]] == [
        "2026-01-24T00:00:37Z", "2026-01-24T00:05:37Z", "2026-01-24T00:10:37Z"]


def test_a_failed_call_stops_the_day_where_it_is_and_a_rerun_resumes(tmp_path):
    feed = _Feed(["2026-01-24T00:00:37Z", "2026-01-24T00:05:37Z", "2026-01-25T00:00:37Z"])
    calls = {"n": 0}

    def flaky(params):
        calls["n"] += 1
        if calls["n"] == 2:
            bad = _Resp({}, 0)
            bad.status_code = 500
            return _Fetched(bad)
        return feed(params)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        H.walk_day(flaky, tmp_path, DAY, FAR)
    state = H.read_state(tmp_path, DAY)
    assert not state["done"] and [s["ts"] for s in state["snapshots"]] == ["2026-01-24T00:00:37Z"]
    H.walk_day(feed, tmp_path, DAY, FAR)
    assert H.read_state(tmp_path, DAY)["done"]
    assert len(H.read_state(tmp_path, DAY)["snapshots"]) == 2


def test_nothing_is_asked_past_the_present(tmp_path):
    feed = _Feed(["2026-01-24T00:00:37Z", "2026-01-24T00:05:37Z", "2026-01-24T00:10:37Z"])
    H.walk_day(feed, tmp_path, DAY, stop_at=_t("2026-01-24T00:06:00Z"))
    assert feed.asked == ["2026-01-24T00:05:00Z", "2026-01-24T00:05:37Z"]
    assert not H.read_state(tmp_path, DAY)["done"]


def test_a_day_another_process_is_walking_is_left_alone(tmp_path):
    """Two processes on one spool must not both pay for a day's snapshots."""
    feed = _Feed(["2026-01-24T00:00:37Z", "2026-01-24T00:05:37Z", "2026-01-25T00:00:37Z"])
    lock = H._take_day(tmp_path, DAY)
    assert lock is not None and H._take_day(tmp_path, DAY) is None
    assert H.walk_day(feed, tmp_path, DAY, FAR) == [] and feed.asked == []
    lock.unlink()
    assert len(H.walk_day(feed, tmp_path, DAY, FAR)) == 2
    assert not lock.exists()                      # released when the day is finished


def test_a_dead_process_s_lock_is_taken_over_and_a_failed_day_releases_its_own(tmp_path):
    import os
    import time
    feed = _Feed(["2026-01-24T00:00:37Z", "2026-01-25T00:00:37Z"])
    lock = H._take_day(tmp_path, DAY)
    old = time.time() - H.LOCK_STALE_S - 5
    os.utime(lock, (old, old))
    assert len(H.walk_day(feed, tmp_path, DAY, FAR)) == 1 and H.read_state(tmp_path, DAY)["done"]

    def boom(params):
        raise RuntimeError("network down")
    other = date(2026, 1, 25)
    with pytest.raises(RuntimeError):
        H.walk_day(boom, tmp_path, other, FAR)
    assert H._take_day(tmp_path, other) is not None   # the failed walk left no lock behind


def test_what_a_day_hands_back_bills_the_same_and_holds_no_body(tmp_path):
    """The meter reads x-requests-last and x-requests-remaining off each paid
    answer. The body is dropped; the billing must survive, whatever case the
    feed spells its headers in."""
    class Resp(_Resp):
        def __init__(self, body):
            super().__init__(body)
            self.headers = {"X-Requests-Last": "60", "X-Requests-Remaining": "14900000",
                            "X-Requests-Used": "100000"}
            self.content = b"x" * 1000

    feed = _Feed(["2026-01-24T00:00:37Z", "2026-01-25T00:00:37Z"])
    real = feed.__call__

    def fetch(params):
        f = real(params)
        f.response = Resp(f.response.json())
        f.attempts = [f.response]
        return f

    (f,) = H.walk_day(fetch, tmp_path, DAY, FAR)
    assert f.response is None
    (a,) = f.attempts
    assert not hasattr(a, "content") and a.status_code == 200
    assert a.headers.get("x-requests-last") == "60"
    assert a.headers.get("x-requests-remaining") == "14900000"
    from data.ingestors.ncaab_odds_history import PoolMeter
    meter = PoolMeter(10_000, 0, workers=1)
    meter.settle(f)
    assert meter.spent == 60 and meter.remaining == 14_900_000


def test_a_state_file_another_process_holds_open_is_retried_not_lost(tmp_path, monkeypatch):
    """Windows refuses to replace a file another process is reading. The write
    waits and tries again, so the day's walk goes on."""
    from pathlib import Path
    real = Path.replace
    refusals = {"left": 3}

    def replace(self, target):
        if self.suffix == ".tmp" and refusals["left"]:
            refusals["left"] -= 1
            raise PermissionError(5, "Access is denied")
        return real(self, target)
    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    feed = _Feed(["2026-01-24T00:00:37Z", "2026-01-25T00:00:37Z"])
    H.walk_day(feed, tmp_path, DAY, FAR)
    assert refusals["left"] == 0 and H.read_state(tmp_path, DAY)["done"]


def test_the_spool_lists_snapshots_oldest_first_across_days(tmp_path):
    feed = _Feed(["2026-01-23T23:55:37Z", "2026-01-24T23:55:37Z", "2026-01-25T00:00:37Z",
                  "2026-01-26T00:00:37Z"])
    H.walk_day(feed, tmp_path, date(2026, 1, 25), FAR)
    H.walk_day(feed, tmp_path, DAY, FAR)
    got = H.spool_snapshots(tmp_path, [date(2026, 1, 25), DAY])
    assert [s["ts"] for s in got] == [_t("2026-01-24T23:55:37Z"), _t("2026-01-25T00:00:37Z")]
    assert all(s["path"].exists() for s in got)


# ── what is kept of one snapshot ─────────────────────────────────────────────

def test_a_pre_game_quote_is_stored_once_and_again_only_when_it_moves():
    keeper, res = H.ChangeKeeper(), _resolver()
    ev = _event("e1", "Seton Hall Pirates", "UConn Huskies", "2026-01-24T17:00:00Z",
                [_book("draftkings", "2026-01-24T14:01:00Z", SHU, UCONN, spread=35.5, total=134.5)])
    first = H.split_snapshot(_body("2026-01-24T14:05:38Z", [ev]), res, TIPS, keeper)
    assert len(first["pregame"]) == 3 and not first["inplay"] and not first["lost"]
    assert {r["source"] for r in first["pregame"]} == {H.PREGAME_SOURCE}
    assert {r["game_id"] for r in first["pregame"]} == {UCONN_SHU}
    spread = next(r for r in first["pregame"] if r["market"] == "spreads")
    assert spread["spread_home"] == 35.5 and spread["snapshot_at"] == "2026-01-24T14:01:00Z"
    # the same quote five minutes later: nothing stored
    again = H.split_snapshot(_body("2026-01-24T14:10:38Z", [ev]), res, TIPS, keeper)
    assert not again["pregame"] and not again["inplay"]
    # the spread moves: that one row is stored
    moved = copy.deepcopy(ev)
    moved["bookmakers"] = [_book("draftkings", "2026-01-24T14:12:00Z", SHU, UCONN,
                                 spread=36.5, total=134.5)]
    third = H.split_snapshot(_body("2026-01-24T14:15:38Z", [moved]), res, TIPS, keeper)
    assert [(r["market"], r["spread_home"]) for r in third["pregame"]] == [("spreads", 36.5)]


def test_a_neutral_court_event_is_stored_in_espns_orientation():
    """The feed calls LSU home; ESPN's home is South Carolina. spread_home is
    ESPN's home team's number (CLAUDE.md section 4) and home_price its price."""
    ev = _event("e2", "LSU Tigers", "South Carolina Gamecocks", "2026-01-24T20:00:00Z",
                [_book("fanduel", "2026-01-24T15:00:00Z", ("LSU Tigers", 180),
                       ("South Carolina Gamecocks", -220), spread=5.5)])
    part = H.split_snapshot(_body("2026-01-24T15:00:38Z", [ev]), _resolver(), TIPS,
                            H.ChangeKeeper())
    rows = {r["market"]: r for r in part["pregame"]}
    assert rows["h2h"]["game_id"] == LSU_SC
    assert rows["h2h"]["home_price"] == -220 and rows["h2h"]["away_price"] == 180
    assert rows["spreads"]["spread_home"] == -5.5


def test_every_in_play_quote_of_every_snapshot_is_kept():
    keeper, res = H.ChangeKeeper(), _resolver()
    ev = _event("e1", "Seton Hall Pirates", "UConn Huskies", "2026-01-24T17:00:00Z",
                [_book("draftkings", "2026-01-24T17:31:00Z", SHU, UCONN, spread=41.5, total=130.5)])
    a = H.split_snapshot(_body("2026-01-24T17:35:38Z", [ev]), res, TIPS, keeper)
    assert len(a["inplay"]) == 3 and not a["pregame"] and a["events_in_play"] == 1
    assert {r["source"] for r in a["inplay"]} == {H.INPLAY_SOURCE}
    # the same in-play quote in the next snapshot is kept again: the row says
    # the book still listed it then
    b = H.split_snapshot(_body("2026-01-24T17:40:38Z", [ev]), res, TIPS, keeper)
    assert len(b["inplay"]) == 3
    row = H._inplay_tuple(b["served"], next(r for r in b["inplay"] if r["market"] == "spreads"))
    assert row == (_t("2026-01-24T17:40:38Z"), UCONN_SHU, "draftkings", "spreads",
                   _t("2026-01-24T17:31:00Z"), -110, -110, 41.5, None, None, None,
                   H.INPLAY_SOURCE)


def test_a_started_games_last_pre_game_quote_stays_pre_game():
    """A book that stopped updating before the tip: its quote was made before
    the game, so it is a pre-game row (and a repeat is not stored)."""
    keeper, res = H.ChangeKeeper(), _resolver()
    ev = _event("e1", "Seton Hall Pirates", "UConn Huskies", "2026-01-24T17:00:00Z",
                [_book("betmgm", "2026-01-24T16:58:00Z", SHU, UCONN, total=134.5)])
    a = H.split_snapshot(_body("2026-01-24T17:15:38Z", [ev]), res, TIPS, keeper)
    assert len(a["pregame"]) == 2 and not a["inplay"]
    b = H.split_snapshot(_body("2026-01-24T17:20:38Z", [ev]), res, TIPS, keeper)
    assert not b["pregame"] and not b["inplay"]


def test_the_womens_extra_books_are_kept_and_an_unlisted_book_is_not():
    ev = _event("e1", "Seton Hall Pirates", "UConn Huskies", "2026-01-24T17:00:00Z", [
        _book("fliff", "2026-01-24T14:00:00Z", SHU, UCONN),
        _book("lowvig", "2026-01-24T14:00:00Z", SHU, UCONN),
        _book("mybookieag", "2026-01-24T14:00:00Z", SHU, UCONN)])
    part = H.split_snapshot(_body("2026-01-24T14:05:38Z", [ev]), _resolver(), TIPS,
                            H.ChangeKeeper())
    assert sorted(r["bookmaker"] for r in part["pregame"]) == ["fliff", "lowvig"]


def test_an_event_no_espn_game_answers_to_is_kept_raw_and_counted_once():
    res = _resolver()
    ev = _event("e9", "Nowhere State Owls", "UConn Huskies", "2026-01-24T19:00:00Z",
                [_book("draftkings", "2026-01-24T14:00:00Z", ("Nowhere State Owls", 900),
                       UCONN)])
    part = H.split_snapshot(_body("2026-01-24T14:05:38Z", [ev]), res, TIPS, H.ChangeKeeper())
    assert not part["pregame"] and [e["id"] for e in part["lost"]] == ["e9"]
    assert res.unresolved_names == {"Nowhere State Owls": 1}
    H.split_snapshot(_body("2026-01-24T14:10:38Z", [ev]), res, TIPS, H.ChangeKeeper())
    assert res.unresolved_names == {"Nowhere State Owls": 1}


# ── step 2: the store ────────────────────────────────────────────────────────

class _Conn:
    """Records what is written. `ledgered` is what the ledger already holds
    when a batch asks (the store's own check before it writes)."""

    def __init__(self, ledgered=()):
        self.statements, self.commits, self.ledgered = [], 0, list(ledgered)

    def execute(self, sql, params=()):
        if sql.lstrip().startswith("SELECT snapshot_ts"):
            self._rows = [(ts,) for ts in self.ledgered if ts in params[0]]
            return self
        self.statements.append((" ".join(sql.split())[:48], params))
        return self

    def fetchall(self):
        return self._rows

    def executemany(self, sql, rows):
        self.statements.append((" ".join(sql.split())[:48], list(rows)))

    def commit(self):
        self.commits += 1

    def kinds(self):
        return [s.split("(")[0].strip() for s, _ in self.statements]


def _spool(tmp_path, bodies):
    """Write bodies as a walked day would and return the snapshot list."""
    snaps = []
    for body in bodies:
        ts = _t(body["timestamp"])
        path = H.snapshot_path(tmp_path, ts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(body, fh)
        snaps.append({"ts": ts, "asked": body["timestamp"], "credits": 60,
                      "events": len(body["data"]), "path": path})
    return snaps


def _three_snapshots(tmp_path):
    pre = _event("e1", "Seton Hall Pirates", "UConn Huskies", "2026-01-24T17:00:00Z",
                 [_book("draftkings", "2026-01-24T16:00:00Z", SHU, UCONN, spread=35.5)])
    live = _event("e1", "Seton Hall Pirates", "UConn Huskies", "2026-01-24T17:00:00Z",
                  [_book("draftkings", "2026-01-24T17:09:00Z", SHU, UCONN, spread=40.5)])
    return _spool(tmp_path, [_body("2026-01-24T16:00:37Z", [pre]),
                             _body("2026-01-24T16:05:37Z", [pre]),
                             _body("2026-01-24T17:10:37Z", [live])])


def _stats():
    return {k: 0 for k in ("stored", "pregame_rows", "inplay_rows", "unmatched_events",
                           "errors", "already_stored")}


def test_each_snapshot_is_written_with_its_ledger_row_and_in_play_rows_go_to_their_table(tmp_path):
    conn, stats = _Conn(), _stats()
    H.store_season(conn, _three_snapshots(tmp_path), _resolver(), TIPS, set(), stats)
    assert conn.kinds() == [
        "INSERT INTO odds",                      # 16:00:37: the first quotes
        "INSERT INTO ncaabw_odds_snapshots",
        "INSERT INTO ncaabw_odds_snapshots",     # 16:05:37: nothing moved, ledger only
        "INSERT INTO ncaabw_inplay_quotes",      # 17:10:37: in play
        "INSERT INTO ncaabw_odds_snapshots",
    ]
    assert conn.commits == 1                     # one transaction for the batch
    assert stats["stored"] == 3 and stats["pregame_rows"] == 2 and stats["inplay_rows"] == 2
    ledger = [p for s, p in conn.statements if s.startswith("INSERT INTO ncaabw_odds_snapshots")]
    assert [row[0] for row in ledger] == [_t("2026-01-24T16:00:37Z"), _t("2026-01-24T16:05:37Z"),
                                          _t("2026-01-24T17:10:37Z")]
    assert all(row[-1] == 60 for row in ledger)                 # credits as billed
    inplay = next(p for s, p in conn.statements if s.startswith("INSERT INTO ncaabw_inplay"))
    assert {r[0] for r in inplay} == {_t("2026-01-24T17:10:37Z")}    # keyed on the snapshot


def test_a_rerun_writes_only_what_the_ledger_lacks_and_remembers_what_came_before(tmp_path):
    """The first two snapshots are in the ledger. They are still read, so the
    third's unchanged pre-game quote is not stored as if new."""
    snaps = _three_snapshots(tmp_path)
    pre_again = _event("e1", "Seton Hall Pirates", "UConn Huskies", "2026-01-24T17:00:00Z",
                       [_book("draftkings", "2026-01-24T16:00:00Z", SHU, UCONN, spread=35.5)])
    snaps[2:] = _spool(tmp_path, [_body("2026-01-24T16:10:37Z", [pre_again])])
    conn, stats = _Conn(), _stats()
    held = {_t("2026-01-24T16:00:37Z"), _t("2026-01-24T16:05:37Z")}
    H.store_season(conn, snaps, _resolver(), TIPS, held, stats)
    assert conn.kinds() == ["INSERT INTO ncaabw_odds_snapshots"]
    assert stats["already_stored"] == 2 and stats["stored"] == 1 and stats["pregame_rows"] == 0


def test_a_replayed_batch_does_not_store_a_snapshot_whose_commit_had_landed(tmp_path):
    """The connection dropped at the commit and the batch is run again. The
    first snapshot's ledger row is there, so its rows are too: only the others
    are written. Without the check its quotes would sit in `odds` twice."""
    snaps = _three_snapshots(tmp_path)
    conn, stats = _Conn(ledgered=[_t("2026-01-24T16:00:37Z")]), _stats()
    H.store_season(conn, snaps, _resolver(), TIPS, set(), stats)
    assert conn.kinds() == [
        "INSERT INTO ncaabw_odds_snapshots",     # 16:05:37, nothing moved
        "INSERT INTO ncaabw_inplay_quotes",      # 17:10:37
        "INSERT INTO ncaabw_odds_snapshots",
    ]
    assert "INSERT INTO odds" not in conn.kinds()


def test_a_spool_file_that_holds_another_snapshot_stops_the_store(tmp_path):
    snaps = _three_snapshots(tmp_path)
    snaps[0]["ts"] = _t("2026-01-24T15:55:37Z")
    with pytest.raises(RuntimeError, match="named"):
        H.store_season(_Conn(), snaps, _resolver(), TIPS, set(), _stats())


class _CountConn:
    """Answers the two counts check_resume asks for."""

    def __init__(self, in_odds, ledgered):
        self.answers, self.sql = [in_odds, ledgered], []

    def execute(self, sql, params=()):
        self.sql.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return (self.answers.pop(0),)

    def commit(self):
        pass


def test_a_lost_ledger_refuses_the_store_rather_than_storing_every_row_twice():
    with pytest.raises(H.LedgerMismatch, match="store them again"):
        H.check_resume(_CountConn(in_odds=147_268, ledgered=0), 2025, 2027)
    conn = _CountConn(in_odds=1_000, ledgered=1_000)
    assert H.check_resume(conn, 2025, 2027) == (1_000, 1_000)
    # the marker is read back through the seasons' game ids, not a scan by source
    sql, params = conn.sql[0]
    assert "source = %s" in sql and "ncaabw_events" in sql and params[0] == H.PREGAME_SOURCE


# ── nothing else can reach what was bought ───────────────────────────────────

def test_the_prune_protects_both_sources_and_keeps_the_womens_price_path():
    for src in (H.PREGAME_SOURCE, H.INPLAY_SOURCE):
        assert src in prune_odds.PROTECTED_SOURCES, src
    assert "NCAABW" in prune_odds.PATH_KEPT_SPORTS


def test_the_ledger_the_in_play_quotes_and_the_raw_store_are_worker_only():
    for table in (H.LEDGER, H.INPLAY_TABLE, H.UNMATCHED,
                  "ncaabw_teams", "ncaabw_events", "ncaabw_venues"):
        assert table in anon_readable.WORKER_ONLY_TABLES, table
        assert table not in anon_readable.ANON_READABLE


def test_the_call_asks_for_seventeen_books_and_the_mens_call_is_unchanged():
    books = odds_ingestor.sport_bookmakers_param("NCAABW").split(",")
    assert len(books) == len(set(books)) == 17
    assert set(config.NCAABW_EXTRA_BOOKMAKERS) < set(books)
    assert set(config.LINE_SHOP_BOOKMAKERS) < set(books)
    # 11 to 20 books bill two regions: 10 x 3 markets x 2
    assert H.SNAPSHOT_COST == 60 and 10 < len(books) <= 20
    for sport in ("NCAAB", "NBA", "MLB", "NFL"):
        assert odds_ingestor.sport_bookmakers_param(sport) == config.ODDS_API_BOOKMAKERS_PARAM
    assert H._params(_t("2026-01-24T17:00:00Z")) == {
        "date": "2026-01-24T17:00:00Z", "markets": "h2h,spreads,totals",
        "bookmakers": ",".join(books), "oddsFormat": "american"}


def test_a_days_reserve_is_every_slot_it_could_hold():
    assert H.DAY_SLOTS == 288 and H.DAY_MAX_COST == 289 * 60


def test_no_extra_book_is_a_book_a_pick_may_name():
    assert not set(config.NCAABW_EXTRA_BOOKMAKERS) & set(config.BEST_LINE_BOOKMAKERS)


@pytest.mark.parametrize("sport", ["NCAAB", "NBA"])
def test_another_sport_never_stores_a_womens_extra_book(sport):
    ev = _event("x", "Home Team", "Away Team", "2026-01-24T17:00:00Z",
                [_book("fliff", "2026-01-24T14:00:00Z", ("Home Team", -120), ("Away Team", 100)),
                 _book("draftkings", "2026-01-24T14:00:00Z", ("Home Team", -120),
                       ("Away Team", 100))])
    _, rows = odds_ingestor._process_events([ev], sport, "open", "2026-01-24T14:05:00Z",
                                            resolve_game_id=lambda h, a, c: ("G", False))
    assert {r["bookmaker"] for r in rows} == {"draftkings"}


def test_the_feeds_sport_key_is_the_one_the_feed_lists():
    """The feed's key is basketball_wncaab (its /sports list, 2026-11-09). A
    wrong key answers 404 'Unknown sport' on every call and stores nothing."""
    from data.ingestors import ncaabw_teams
    assert ncaabw_teams.ODDS_API_SPORT_KEY == "basketball_wncaab"
    assert odds_ingestor.SPORT_KEYS["NCAABW"] == "basketball_wncaab"
    assert H.BASE.endswith("/historical/sports/basketball_wncaab")

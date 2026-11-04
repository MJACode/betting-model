"""The closing prop snapshot for nba_prop_market bets (data/ingestors/nba_prop_close_ingestor.py).

Bar 11 (closing-line value) could not be measured on the archive the rule was
graded on, so every bet gets one later snapshot 12-25 minutes before tip,
filed 'close' where no card reads it. Nothing here calls the feed: the HTTP
layer is replaced, and the credit count is what the mocked `x-requests-last`
header says, which is exactly what the live run reports.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import data.ingestors.nba_prop_close_ingestor as ing

TIP = datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc)
GID = "NBA_2026-10-21_GSW_LAL"


# ── the gate ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("minutes_before,expected", [
    (30, False), (26, False), (25, True), (18, True), (13, True), (12, False), (5, False),
])
def test_only_twelve_to_twenty_five_minutes_before_tip(minutes_before, expected):
    now = TIP - timedelta(minutes=minutes_before)
    assert ing.due(TIP, now, has_bet=True, close_taken=False) is expected


def test_only_a_game_holding_a_bet_and_only_once():
    now = TIP - timedelta(minutes=18)
    assert ing.due(TIP, now, has_bet=False, close_taken=False) is False
    assert ing.due(TIP, now, has_bet=True, close_taken=True) is False


def test_the_ten_minute_evening_passes_always_land_one_inside():
    """A pass every ten minutes from any offset hits the 13-minute window once."""
    for offset in range(10):
        start = TIP - timedelta(minutes=40) + timedelta(minutes=offset)
        hits, taken = 0, False
        now = start
        while now < TIP:
            if ing.due(TIP, now, has_bet=True, close_taken=taken):
                hits += 1
                taken = True
            now += timedelta(minutes=10)
        assert hits == 1, offset


def test_the_close_is_filed_where_no_card_reads_it():
    import inspect

    import models.nba_prop_market as mk
    assert ing.SNAPSHOT_TYPE == "close"
    assert "snapshot_type = 'open'" in inspect.getsource(mk.load_quotes)


# ── one run, mocked end to end ───────────────────────────────────────────────

class _Resp:
    def __init__(self, body, credits, status=200):
        self._body, self.status_code, self.text = body, status, ""
        self.headers = {"x-requests-last": str(credits), "x-requests-remaining": "100000"}

    def json(self):
        return self._body


EVENTS = [{"id": "ev1", "home_team": "Los Angeles Lakers", "away_team": "Golden State Warriors",
           "commence_time": "2026-10-22T00:00:00Z"}]
BOARD = {"bookmakers": [
    {"key": "fanduel", "last_update": "2026-10-21T23:40:00Z", "markets": [
        {"key": "player_points", "last_update": "2026-10-21T23:41:00Z", "outcomes": [
            {"name": "Over", "description": "Stephen Curry", "price": -120, "point": 24.5},
            {"name": "Under", "description": "Stephen Curry", "price": +100, "point": 24.5}]}]},
    {"key": "pinnacle", "last_update": "2026-10-21T23:42:00Z", "markets": [
        {"key": "player_points", "outcomes": [
            {"name": "Over", "description": "Stephen Curry", "price": -112, "point": 24.5},
            {"name": "Under", "description": "Stephen Curry", "price": -108, "point": 24.5}]}]},
]}


class _Conn:
    def __init__(self, closes=(), bets=None, listed=()):
        self.closes, self.inserted, self.commits = set(closes), [], 0
        self.bets = bets if bets is not None else [
            (GID, "player_points", "LAL", "GSW", "2026-10-21",
             "2026-10-22T00:10:00+00:00", "2026-10-22T00:00:00+00:00")]
        self.listed = list(listed)

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self._rows = []
        if "FROM picks p" in s:
            self._rows = self.bets
        elif s.startswith("SELECT game_id, commence_time, game_type FROM nba_schedule"):
            self._rows = [r for r in self.listed if r[0] in params[0]]
        elif "snapshot_type = %s" in s:
            self._rows = [(g,) for g in params[0] if g in self.closes]
        return self

    def executemany(self, sql, rows):
        self.inserted.extend(rows)

    def fetchall(self):
        return self._rows

    def commit(self):
        self.commits += 1

    def close(self):
        pass


@pytest.fixture
def wired(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, dict(params or {})))
        if url.endswith("/events"):
            return _Resp(EVENTS, 0)
        return _Resp(BOARD, 1)

    monkeypatch.setattr(ing.requests, "get", fake_get)
    monkeypatch.setattr(ing, "ODDS_API_KEY", "test-key")
    monkeypatch.setattr(ing, "persist_quota", lambda c: None)
    monkeypatch.setattr(ing, "record_quota_headers", lambda r: None)
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)
    import data.ingestors.prop_odds_ingestor as poi
    monkeypatch.setattr(poi, "_book_last_update_ready", True)
    return calls


def test_a_due_close_buys_one_call_of_the_bet_markets_and_reports_its_credits(monkeypatch, wired):
    conn = _Conn()
    monkeypatch.setattr(ing, "get_connection", lambda: conn)
    out = ing.run_nba_prop_close_ingestor(now=TIP - timedelta(minutes=18))
    paid = [c for c in wired if "/events/" in c[0]]
    assert len(paid) == 1
    assert paid[0][1]["markets"] == "player_points"          # the bet market only
    # The credit cost per game is what the feed's header says: one market at
    # the fetched books billed 1 here, and the run reports exactly that.
    assert out["credits_by_game"] == {GID: 1} and out["credits"] == 1
    assert out["bought"] == 1 and conn.commits == 1
    assert {r["snapshot_type"] for r in conn.inserted} == {"close"}
    assert {r["bookmaker"] for r in conn.inserted} == {"fanduel", "pinnacle"}
    by_book = {r["bookmaker"]: r for r in conn.inserted}
    # The market's own clock, else the bookmaker's.
    assert by_book["fanduel"]["book_last_update"] == "2026-10-21T23:41:00Z"
    assert by_book["pinnacle"]["book_last_update"] == "2026-10-21T23:42:00Z"
    assert not conn.inserted[0]["snapshot_at"].endswith("Z")   # backfilled_dates reads 'Z' as history


def test_a_close_already_held_is_not_bought_again(monkeypatch, wired):
    conn = _Conn(closes={GID})
    monkeypatch.setattr(ing, "get_connection", lambda: conn)
    out = ing.run_nba_prop_close_ingestor(now=TIP - timedelta(minutes=18))
    assert out["due"] == 0 and wired == [] and conn.inserted == []


def test_a_pass_outside_the_window_spends_nothing(monkeypatch, wired):
    conn = _Conn()
    monkeypatch.setattr(ing, "get_connection", lambda: conn)
    out = ing.run_nba_prop_close_ingestor(now=TIP - timedelta(minutes=40))
    assert wired == [] and out["credits"] == 0


def test_the_tip_is_the_schedules_not_the_feeds_later_one(monkeypatch, wired):
    """The picks row joins games (00:10, the feed's) and nba_schedule (00:00):
    at 23:46 the schedule's tip is 14 minutes away, the feed's 24."""
    conn = _Conn()
    monkeypatch.setattr(ing, "get_connection", lambda: conn)
    games = ing.bet_games(conn, TIP - timedelta(minutes=14))
    assert games[GID]["tip"] == TIP


def _bet(gid=GID, feed=TIP, sched=None, home="LAL", away="GSW"):
    return [(gid, "player_points", home, away, "2026-10-21", feed.isoformat(), sched.isoformat() if sched else None)]


@pytest.mark.parametrize("kind,espn_early_is_used", [("playoff", False), ("playin", False), ("cup_final", False),
                                                     ("regular", True)])
def test_a_false_early_start_does_not_buy_a_postseason_close_hours_ahead(kind, espn_early_is_used):
    """The close follows the tip the bet's card decided on. On a postseason row a start five hours before
    the feed's is read as ESPN's error, and the close is bought before the feed's start. A regular-season
    row is the league's, and stays on the earlier."""
    espn = TIP - timedelta(hours=5)
    conn = _Conn(bets=_bet(feed=TIP, sched=espn), listed=[(GID, espn.isoformat(), kind)])
    at_espn = ing.bet_games(conn, espn - timedelta(minutes=14))
    at_feed = ing.bet_games(conn, TIP - timedelta(minutes=14))
    if espn_early_is_used:
        assert at_espn[GID]["tip"] == espn and at_feed == {}
    else:
        assert at_espn == {} and at_feed[GID]["tip"] == TIP


def test_a_bet_on_a_row_the_other_way_round_reads_espns_tip():
    """The feed's start is 15 minutes late here, so the close 12-25 minutes before it could land after
    the real tip."""
    feed_id, espn_id = "NBA_2026-10-21_LAL_GSW", "NBA_2026-10-21_GSW_LAL"
    conn = _Conn(bets=_bet(gid=feed_id, feed=TIP + timedelta(minutes=15), home="GSW", away="LAL"),
                 listed=[(espn_id, TIP.isoformat(), "cup_final")])
    assert ing.bet_games(conn, TIP - timedelta(minutes=14))[feed_id]["tip"] == TIP


def test_a_bet_with_only_the_feeds_start_is_still_bought_on_it():
    """No close is lost: its closing-line value stays empty (tests/test_nba_clv_feed_start.py), and the
    row is there if the schedule's tip arrives."""
    conn = _Conn(bets=_bet(feed=TIP), listed=[])
    assert ing.bet_games(conn, TIP - timedelta(minutes=14))[GID]["tip"] == TIP


def test_the_step_is_wired_into_the_refresh_pass():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sh = (root / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    assert "\nstep nba-prop-close\n" in sh
    rp = (root / "run_pipeline.py").read_text(encoding="utf-8")
    assert '"nba-prop-close": lambda: step_nba_prop_close()' in rp

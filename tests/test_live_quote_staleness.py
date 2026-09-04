"""
The book's own publish clock, and what happens when it stops.

THE INCIDENT THIS PINS (2026-08-29, New Mexico State at Florida State).
DraftKings' live total held 46.5 for 4m35s of running clock. The loop polled it
every 5 seconds, priced against it, and posted Over 46.5 at -120. End to end the
pipeline took 1.3 seconds — it was never slow. 49 seconds later the book re-hung
at 51.5, then 54.5. Every freshness guard in the loop measured OUR fetch age,
which was 0.6s, so nothing could see that the price was no longer on offer.

The field that distinguishes "confirming 46.5 every twenty seconds" from "froze
at 46.5 four minutes ago" is the book's `last_update`, which the NCAAF feed was
discarding. These tests exist so it cannot be discarded again.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ncaaf_live.feeds.odds_live import parse_event_odds       # noqa: E402
from ncaaf_live.serve import (market_is_takeable,             # noqa: E402
                              quote_age_seconds)
from data.ingestors.live_price_log import (                   # noqa: E402
    quote_from_nfl_quotes, rows_from_quote)

NOW = datetime(2026, 8, 29, 23, 58, 16, tzinfo=timezone.utc)


def _iso(delta_sec: float) -> str:
    return (NOW - timedelta(seconds=delta_sec)).isoformat().replace(
        "+00:00", "Z")


def _event(total_ts=None, h2h_ts=None, book_ts=None):
    return {
        "home_team": "Florida State", "away_team": "New Mexico State",
        "commence_time": "2026-08-29T23:00:00Z",
        "bookmakers": [{
            "key": "draftkings", "last_update": book_ts,
            "markets": [
                {"key": "totals", "last_update": total_ts, "outcomes": [
                    {"name": "Over", "point": 46.5, "price": -120},
                    {"name": "Under", "point": 46.5, "price": -110}]},
                {"key": "h2h", "last_update": h2h_ts, "outcomes": [
                    {"name": "Florida State", "price": -2000},
                    {"name": "New Mexico State", "price": 1100}]},
            ]}]}


# ── the parser must carry the field at all ───────────────────────────────────

def test_parser_carries_the_books_publish_time_per_market():
    rec = parse_event_odds([_event(total_ts=_iso(275), h2h_ts=_iso(12))])
    key = ("Florida State", "New Mexico State")
    assert rec[key]["total"]["ts"] == _iso(275)
    assert rec[key]["h2h"]["ts"] == _iso(12)


def test_markets_are_timestamped_independently():
    """DraftKings suspends the total and the moneyline separately, so one can
    be minutes stale while the other is current. A single per-event timestamp
    would let a frozen total ride in on a fresh moneyline."""
    rec = parse_event_odds([_event(total_ts=_iso(275), h2h_ts=_iso(3))])
    key = ("Florida State", "New Mexico State")
    assert rec[key]["total"]["ts"] != rec[key]["h2h"]["ts"]


def test_bookmaker_timestamp_is_the_fallback():
    rec = parse_event_odds([_event(book_ts=_iso(30))])
    key = ("Florida State", "New Mexico State")
    assert rec[key]["total"]["ts"] == _iso(30)
    assert rec[key]["h2h"]["ts"] == _iso(30)


def test_prices_still_parse_unchanged():
    rec = parse_event_odds([_event(total_ts=_iso(5))])
    tot = rec[("Florida State", "New Mexico State")]["total"]
    assert (tot["line"], tot["over"], tot["under"]) == (46.5, -120, -110)


# ── the guard ────────────────────────────────────────────────────────────────

def test_the_florida_state_market_would_now_be_declined():
    """275s frozen: the exact market that produced the bad pick."""
    assert not market_is_takeable({"line": 46.5, "ts": _iso(275)},
                                  "totals", "g", NOW)


def test_a_normally_refreshing_market_is_taken():
    """DraftKings republishes an in-play total every 47s at the median; a bound
    that rejected that rhythm would be an outage, not a guard."""
    assert market_is_takeable({"line": 46.5, "ts": _iso(47)}, "totals", "g", NOW)
    assert market_is_takeable({"line": 46.5, "ts": _iso(85)}, "totals", "g", NOW)


def test_a_missing_timestamp_is_treated_as_fresh_not_blocked():
    """A feed shape change must not silently blank the board — it is logged
    instead, so the blindness is visible rather than total."""
    assert market_is_takeable({"line": 46.5}, "totals", "g", NOW)
    assert market_is_takeable({"line": 46.5, "ts": "not-a-time"},
                              "totals", "g", NOW)
    assert quote_age_seconds("not-a-time", NOW) is None
    assert quote_age_seconds(None, NOW) is None


def test_an_absent_market_is_not_takeable():
    assert not market_is_takeable(None, "totals", "g", NOW)
    assert not market_is_takeable({}, "totals", "g", NOW)


def test_a_naive_timestamp_is_read_as_utc_not_local():
    """Mixing a naive timestamp with an aware now raises; reading it as local
    time would silently shift the age by the offset."""
    naive = (NOW - timedelta(seconds=20)).replace(tzinfo=None).isoformat()
    assert abs(quote_age_seconds(naive, NOW) - 20) < 1


# ── the audit trail records the book's clock, not ours ───────────────────────

def test_price_log_stamps_the_books_publish_time():
    """A log stamped with our clock shows a frozen price refreshing every five
    seconds — the same illusion, written down."""
    quote = {"total": {"line": 46.5, "over": -120, "under": -110,
                       "ts": _iso(275)},
             "h2h": {"home": -2000, "away": 1100, "ts": _iso(4)}}
    rows = {r["market"]: r for r in
            rows_from_quote("g", "NCAAF", quote, "draftkings", _iso(0))}
    assert rows["totals"]["snapshot_at"] == _iso(275)
    assert rows["h2h"]["snapshot_at"] == _iso(4)


def test_price_log_falls_back_to_our_clock_without_one():
    quote = {"total": {"line": 46.5, "over": -120, "under": -110}}
    rows = rows_from_quote("g", "NCAAF", quote, "draftkings", _iso(0))
    assert rows[0]["snapshot_at"] == _iso(0)


# ── NFL: the last live lane with no audit trail ──────────────────────────────

class _Q:
    def __init__(self, market, side, price, line=None, book="draftkings",
                 ts=None, home="Green Bay Packers", away="Chicago Bears"):
        self.market, self.side, self.price, self.line = market, side, price, line
        self.bookmaker, self.ts = book, ts
        self.home_team, self.away_team = home, away


def test_nfl_flat_quotes_fold_into_the_shared_row_shape():
    quotes = [_Q("totals", "over", -110, 44.5, ts=_iso(10)),
              _Q("totals", "under", -110, 44.5, ts=_iso(10)),
              _Q("h2h", "home", -150, ts=_iso(10)),
              _Q("h2h", "away", 130, ts=_iso(10)),
              _Q("spreads", "home", -110, -3.5, ts=_iso(10)),
              _Q("spreads", "away", -110, 3.5, ts=_iso(10))]
    q = quote_from_nfl_quotes(quotes, "draftkings")
    assert q["total"] == {"over": -110, "under": -110, "line": 44.5,
                          "ts": _iso(10)}
    assert q["h2h"]["home"] == -150 and q["h2h"]["away"] == 130
    assert q["spread"]["line"] == -3.5
    rows = rows_from_quote("NFL_2026_1_CHI_GB", "NFL", q, "draftkings", _iso(0))
    assert {r["market"] for r in rows} == {"h2h", "totals", "spreads"}
    assert all(r["snapshot_at"] == _iso(10) for r in rows)
    assert all(r["snapshot_type"] == "in_play" for r in rows)


def test_nfl_fold_keeps_one_book_only():
    """The log records what we priced against; mixing two books' prices into
    one row would invent a quote nobody offered."""
    quotes = [_Q("totals", "over", -110, 44.5, book="draftkings"),
              _Q("totals", "over", -105, 45.5, book="fanduel")]
    assert quote_from_nfl_quotes(quotes, "fanduel")["total"]["line"] == 45.5
    assert quote_from_nfl_quotes(quotes, "draftkings")["total"]["line"] == 44.5


def test_nfl_quotes_map_to_the_platform_game_id():
    from data.ingestors.nfl_live_price_log import rows_for_quotes
    index = {("GB", "CHI"): "NFL_2026_1_CHI_GB"}
    rows = rows_for_quotes([_Q("totals", "over", -110, 44.5, ts=_iso(9)),
                            _Q("totals", "under", -110, 44.5, ts=_iso(9))],
                           index, _iso(0))
    assert [r["game_id"] for r in rows] == ["NFL_2026_1_CHI_GB"]


def test_an_unmapped_nfl_game_is_skipped_not_guessed():
    """odds.game_id is a foreign key, and a guessed mapping writes prices onto
    the wrong game — worse than no audit row."""
    from data.ingestors.nfl_live_price_log import rows_for_quotes
    index = {("GB", "CHI"): "NFL_2026_1_CHI_GB"}
    assert rows_for_quotes(
        [_Q("totals", "over", -110, 44.5, home="Detroit Lions",
            away="Minnesota Vikings")], index, _iso(0)) == []
    assert rows_for_quotes(
        [_Q("totals", "over", -110, 44.5, home="Not A Team",
            away="Chicago Bears")], index, _iso(0)) == []


# ── one row per publish, not one per poll ────────────────────────────────────

class _Conn:
    def __init__(self, fail=False):
        self.batches, self.commits, self.fail = [], 0, fail

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def _write(conn, rows, monkeypatch, fail=False):
    import data.ingestors.odds_ingestor as oi
    from data.ingestors import live_price_log as lpl

    def _ins(_c, rs):
        if fail:
            raise RuntimeError("insert failed")
        conn.batches.append(list(rs))
    monkeypatch.setattr(oi, "_insert_odds", _ins)
    return lpl.record_live_prices(conn, rows, known_game_ids={"g"})


def _rows(ts):
    return rows_from_quote("g", "NCAAF",
                           {"total": {"line": 46.5, "over": -120,
                                      "under": -110, "ts": ts}},
                           "draftkings", ts)


def test_repolling_one_publish_writes_one_row(monkeypatch):
    """Polling runs 5s against a 47s median republish. Without this the log
    stores ~10 identical rows per publish and stops reading as a price
    history."""
    from data.ingestors import live_price_log as lpl
    lpl._WRITTEN.clear()
    conn = _Conn()
    assert _write(conn, _rows(_iso(30)), monkeypatch) == 1
    for _ in range(8):
        assert _write(conn, _rows(_iso(30)), monkeypatch) == 0
    assert _write(conn, _rows(_iso(5)), monkeypatch) == 1
    assert len(conn.batches) == 2


def test_a_failed_write_is_retried_not_lost(monkeypatch):
    """Marking a publish written on the way in would drop it permanently the
    one time the insert fails."""
    from data.ingestors import live_price_log as lpl
    lpl._WRITTEN.clear()
    conn = _Conn()
    assert _write(conn, _rows(_iso(30)), monkeypatch, fail=True) == 0
    assert _write(conn, _rows(_iso(30)), monkeypatch) == 1


def test_duplicates_inside_one_batch_collapse(monkeypatch):
    from data.ingestors import live_price_log as lpl
    lpl._WRITTEN.clear()
    conn = _Conn()
    assert _write(conn, _rows(_iso(30)) + _rows(_iso(30)), monkeypatch) == 1


def test_a_game_with_no_games_row_is_never_written(monkeypatch):
    """The foreign key that took the MLB live loop down the day the floor
    fetch shipped."""
    from data.ingestors import live_price_log as lpl
    lpl._WRITTEN.clear()
    conn = _Conn()
    import data.ingestors.odds_ingestor as oi
    monkeypatch.setattr(oi, "_insert_odds",
                        lambda _c, rs: conn.batches.append(list(rs)))
    rows = rows_from_quote("unknown", "NCAAF",
                           {"total": {"line": 46.5, "over": -120,
                                      "under": -110, "ts": _iso(5)}},
                           "draftkings", _iso(5))
    assert lpl.record_live_prices(conn, rows, known_game_ids={"g"}) == 0
    assert conn.batches == []


# ── the wiring must actually resolve from the worker's own cwd ───────────────

def test_nfl_hook_resolves_from_the_workers_cwd():
    """The NFL worker runs with cwd=nfl/, where `nfl/data/` (odds_cache,
    games.csv) sits on sys.path as a namespace package called `data`. A bare
    `from data.ingestors...` there raises ModuleNotFoundError, the caller
    swallows it, and the wiring looks present while doing nothing forever.

    This runs the real hook from the real cwd. An empty quote list returns
    before any connection is opened, so the only thing under test is whether
    the import lands on the platform package."""
    import subprocess
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'.');"
         "from live_model.workers.gameday import _record_live_prices;"
         "_record_live_prices([]); print('RESOLVED-OK')"],
        cwd=str(root / "nfl"), capture_output=True, text=True, timeout=300)
    assert "RESOLVED-OK" in out.stdout, (out.stdout, out.stderr[-2000:])


# ─────────────────────────────────────────────────────────────────────────────
# THE SECOND INCIDENT (2026-09-03, Akron at Wake Forest) — a quote that was
# YOUNG and still extinct. Every timestamp below is measured, not constructed:
# DraftKings' publish clock and its re-hang come from `odds`, the pick time from
# `picks_log`, and the score-detection time from the pollers service log line
# "score change seen - pulling odds now (3s floor)".
#
#   23:51:42.0  DK publishes the live total at 44.5, Over -105
#   ~23:52:2x   Wake Forest scores a touchdown (ESPN drive wallclock)
#   23:52:43.6  the loop SEES the score and pulls odds at the 3s floor
#   23:52:44.2  we post Over 44.5 at -105, edge +15.77%
#   23:53:21.0  DK re-hangs at 50.5
#
# At pick time the quote was 62.2s old against a 90s cap (61.6s at the moment
# the score was seen) and the edge 0.1577 against a 0.18 cap, so BOTH existing
# guards passed it — correctly, on what they measure.
# ─────────────────────────────────────────────────────────────────────────────

from ncaaf_live.serve import LIVE_QUOTE_MAX_AGE_SEC              # noqa: E402
from data.live_quote_guard import (ScoreClock,                 # noqa: E402
                                     quote_predates_score)

WF_QUOTE_TS = "2026-09-03T23:51:42Z"       # DK's last_update on the 44.5
WF_SCORE_SEEN = datetime(2026, 9, 3, 23, 52, 43, 643000, tzinfo=timezone.utc)
WF_PICK_TIME = datetime(2026, 9, 3, 23, 52, 44, 234000, tzinfo=timezone.utc)
WF_REHANG_TS = "2026-09-03T23:53:21Z"      # DK's next publish, at 50.5


def _wf_total(ts):
    return {"line": 44.5, "over": -105, "under": -125, "ts": ts}


def test_the_old_guards_would_still_pass_the_wake_forest_quote():
    """The control. Without a score, the 44.5 is takeable — which is precisely
    why this pick shipped. If this assertion ever flips, the new guard is not
    what is catching the incident below and the test proves nothing."""
    age = quote_age_seconds(WF_QUOTE_TS, WF_PICK_TIME)
    assert 62.0 < age < 62.5                      # 62.2s, measured
    assert age < LIVE_QUOTE_MAX_AGE_SEC           # inside the 90s cap
    assert market_is_takeable(_wf_total(WF_QUOTE_TS), "totals", "g",
                              WF_PICK_TIME, score_seen_at=None)


def test_quote_published_before_the_score_is_declined():
    """The fix. Same quote, same instant — but we have seen the touchdown."""
    assert quote_predates_score(WF_QUOTE_TS, WF_SCORE_SEEN)
    assert not market_is_takeable(_wf_total(WF_QUOTE_TS), "totals", "g",
                                  WF_PICK_TIME, score_seen_at=WF_SCORE_SEEN)


def test_the_rehung_quote_is_takeable_again():
    """Self-clearing: the block lasts exactly until the book republishes, so a
    real post-score price is never held back."""
    after = datetime(2026, 9, 3, 23, 53, 25, tzinfo=timezone.utc)
    assert not quote_predates_score(WF_REHANG_TS, WF_SCORE_SEEN)
    assert market_is_takeable(_wf_total(WF_REHANG_TS), "totals", "g",
                              after, score_seen_at=WF_SCORE_SEEN)


def test_unknown_timestamps_are_not_treated_as_stale():
    """Fail OPEN, matching `quote_age_seconds`: a feed shape change must not
    silently blank the board. The age bound still applies underneath."""
    assert not quote_predates_score(None, WF_SCORE_SEEN)
    assert not quote_predates_score("not-a-time", WF_SCORE_SEEN)
    assert not quote_predates_score(WF_QUOTE_TS, None)


def test_score_clock_reports_no_event_at_first_sight():
    """A game APPEARING is not a score. Same rule `scores_moved` already
    applies — otherwise every market is declined at kickoff."""
    clock = ScoreClock()
    t0 = datetime(2026, 9, 3, 23, 0, tzinfo=timezone.utc)
    assert clock.observe("g", (0, 0), t0) is None
    assert clock.observe("g", (0, 0), t0 + timedelta(seconds=5)) is None


def test_score_clock_stamps_the_change_and_holds_it():
    clock = ScoreClock()
    t0 = datetime(2026, 9, 3, 23, 0, tzinfo=timezone.utc)
    clock.observe("g", (0, 10), t0)
    scored = t0 + timedelta(seconds=30)
    assert clock.observe("g", (0, 17), scored) == scored
    # Held until the NEXT change, so the guard stays armed across later passes.
    assert clock.observe("g", (0, 17), scored + timedelta(seconds=9)) == scored


def test_score_clock_ignores_a_dropped_score_field():
    """A feed that blanks the score for one pass must not read as a change when
    it comes back."""
    clock = ScoreClock()
    t0 = datetime(2026, 9, 3, 23, 0, tzinfo=timezone.utc)
    clock.observe("g", (0, 10), t0)
    assert clock.observe("g", (None, None), t0 + timedelta(seconds=5)) is None
    assert clock.observe("g", (0, 10), t0 + timedelta(seconds=10)) is None


def test_score_clock_keeps_games_independent():
    clock = ScoreClock()
    t0 = datetime(2026, 9, 3, 23, 0, tzinfo=timezone.utc)
    clock.observe("a", (0, 0), t0)
    clock.observe("b", (0, 0), t0)
    scored = t0 + timedelta(seconds=20)
    assert clock.observe("a", (7, 0), scored) == scored
    assert clock.observe("b", (0, 0), scored) is None

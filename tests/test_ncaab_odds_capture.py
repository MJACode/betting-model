"""The NCAAB odds capture (scripts/ncaab_odds_capture.py) and its job.

What is pinned here, and why each one matters:
  * CHANGE-ONLY. Every five minutes the whole board is ~4,500 rows; written
    whole that floods odds. Only a never-seen key or a moved price is written,
    and the comparison is by number, because latest_odds hands back Decimal.
  * STARTED GAMES ARE DROPPED. Their prices are in-play (CLAUDE.md §6).
  * NOTHING IS SPENT WHEN NOTHING CAN BE STORED: off-season (no tip within 36
    hours), no resolver, or the kill switch -- no Odds API call in any of them.
  * THE JOB is registered every five minutes on the pipeline service, watched
    by the heartbeat, and a failed run raises so the heartbeat says so.

odds_ingestor._process_events is STUBBED throughout. Teaching it the
(game_id, flipped) resolver and exempting NCAAB from the DraftKings gate is
another change; these tests pin only what this script hands it and what it
does with what comes back.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import scripts.ncaab_odds_capture as cap
from data.ingestors import ncaab_teams
from data.ingestors import odds_ingestor

NOW = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)          # 10:00 ET
G1 = "NCAAB_2026-11-05_kansas_kentucky"
G2 = "NCAAB_2026-11-05_duke_unc"


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class _Cur:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)


class FakeConn:
    """Answers the two reads the script makes itself: ncaab_events (the
    upcoming-games guard) and latest_odds (the stored quotes)."""

    def __init__(self, events=(), latest=(), events_error=None):
        self.events, self.latest, self.events_error = list(events), list(latest), events_error
        self.queries: list = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        # A read opens a transaction (get_connection leaves autocommit off);
        # commit or rollback ends it. The network call must never see one open.
        self.in_txn = False

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        self.in_txn = True
        if "FROM ncaab_events" in sql:
            if self.events_error:
                raise self.events_error
            return _Cur(self.events)
        if "FROM latest_odds" in sql:
            return _Cur(self.latest)
        raise AssertionError(f"unexpected SQL: {sql}")

    def commit(self):
        self.commits += 1
        self.in_txn = False

    def rollback(self):
        self.rollbacks += 1
        self.in_txn = False

    def close(self):
        self.closed = True


def _row(game_id, market, book, **prices):
    base = {c: None for c in cap.PRICE_COLS}
    base.update(prices)
    return {"game_id": game_id, "sport": "NCAAB", "market": market, "bookmaker": book,
            "snapshot_type": "open", "snapshot_at": "2026-11-05T14:58:00Z", **base}


def _event(home, away, tip, rows):
    """A feed event. `_rows` is test-only: the rows the stubbed parser emits
    for it once it resolves."""
    return {"id": f"{away}@{home}", "home_team": home, "away_team": away,
            "commence_time": _iso(tip), "bookmakers": [{"key": "draftkings"}],
            "_rows": rows}


@pytest.fixture
def wired(monkeypatch):
    """The script with every outside call stubbed and recorded."""
    rec = {"get_odds": [], "process": [], "inserted": [], "resolver_args": [],
           "resolver_days_fwd": [], "quota": []}
    feed: list = []
    table = {("Kentucky Wildcats", "Kansas Jayhawks"): (G1, False),
             ("North Carolina Tar Heels", "Duke Blue Devils"): (G2, True)}

    def make_resolver(conn, around_date, days_back=2, days_fwd=10):
        rec["resolver_args"].append(around_date)
        rec["resolver_days_fwd"].append(days_fwd)
        return lambda home, away, ct: table.get((home, away))

    def get_odds(sport_key, markets):
        rec["get_odds"].append((sport_key, list(markets)))
        return list(feed)

    def process(events, sport, snapshot_type, snapshot_at, include_3way=False,
                resolve_game_id=None):
        rec["process"].append({"events": [e["id"] for e in events], "sport": sport,
                               "snapshot_type": snapshot_type, "snapshot_at": snapshot_at})
        rows = []
        for ev in events:
            hit = resolve_game_id(ev["home_team"], ev["away_team"], ev["commence_time"])
            if hit:
                gid, _flipped = hit
                rows.extend({**r, "game_id": gid} for r in ev["_rows"])
        return [], rows

    def insert(conn, rows):
        rec["inserted"].extend(rows)
        return len(rows)

    monkeypatch.setattr(ncaab_teams, "make_resolver", make_resolver)
    monkeypatch.setattr(odds_ingestor, "_get_odds", get_odds)
    monkeypatch.setattr(odds_ingestor, "_process_events", process)
    monkeypatch.setattr(odds_ingestor, "_insert_odds", insert)
    monkeypatch.setattr(cap.config, "today_et", lambda: "2026-11-05")
    # Records whether a transaction was still open when the quota row was
    # written: after a failed write it must have been rolled back first.
    monkeypatch.setattr(cap, "persist_quota",
                        lambda conn: rec["quota"].append(conn.in_txn))
    rec["feed"] = feed
    return rec


def _upcoming():
    """ncaab_events rows: one game tipping tonight."""
    return [("2026-11-05", "2026-11-06T00:00Z")]


# ── change-only ──────────────────────────────────────────────────────────────

def test_only_new_and_changed_rows_are_written(wired):
    same = _row(G1, "h2h", "draftkings", home_price=-150, away_price=130)
    moved = _row(G1, "spreads", "draftkings", spread_home=-3.5, home_price=-110, away_price=-110)
    fresh = _row(G1, "totals", "fanduel", total_line=141.5, over_price=-110, under_price=-110)
    wired["feed"].append(_event("Kentucky Wildcats", "Kansas Jayhawks",
                                NOW + timedelta(hours=9), [same, moved, fresh]))
    # latest_odds is NUMERIC: psycopg hands back Decimal. -150 must equal
    # Decimal('-150'), or every tick rewrites the whole board.
    nulls = [None] * 7

    def stored(market, book, **p):
        vals = dict(zip(cap.PRICE_COLS, nulls))
        vals.update(p)
        return (G1, market, book, *[vals[c] for c in cap.PRICE_COLS])
    conn = FakeConn(events=_upcoming(), latest=[
        stored("h2h", "draftkings", home_price=Decimal("-150"), away_price=Decimal("130")),
        stored("spreads", "draftkings", spread_home=Decimal("-3.0"),
               home_price=Decimal("-110"), away_price=Decimal("-110")),
    ])
    counts = cap.capture(conn, NOW)
    assert [(_r["market"], _r["bookmaker"]) for _r in wired["inserted"]] == [
        ("spreads", "draftkings"), ("totals", "fanduel")]
    assert counts["new"] == 1 and counts["changed"] == 1 and counts["unchanged"] == 1
    assert counts["inserted"] == 2 and conn.commits == 1


def test_the_stored_quotes_are_one_read_keyed_on_the_games_in_hand(wired):
    wired["feed"].extend([
        _event("Kentucky Wildcats", "Kansas Jayhawks", NOW + timedelta(hours=9),
               [_row(G1, "h2h", "draftkings", home_price=-150, away_price=130)]),
        _event("North Carolina Tar Heels", "Duke Blue Devils", NOW + timedelta(hours=10),
               [_row(G2, "h2h", "draftkings", home_price=-120, away_price=100)]),
    ])
    conn = FakeConn(events=_upcoming())
    cap.capture(conn, NOW)
    reads = [(s, p) for s, p in conn.queries if "FROM latest_odds" in s]
    assert len(reads) == 1
    sql, params = reads[0]
    assert "game_id = ANY(%s)" in sql
    assert params == (sorted([G1, G2]),)


def test_an_unchanged_board_writes_nothing_and_is_not_a_failure(wired):
    row = _row(G1, "h2h", "draftkings", home_price=-150, away_price=130)
    wired["feed"].append(_event("Kentucky Wildcats", "Kansas Jayhawks",
                                NOW + timedelta(hours=9), [row]))
    conn = FakeConn(events=_upcoming(),
                    latest=[(G1, "h2h", "draftkings",
                             *["-150.0" if c == "home_price" else "130" if c == "away_price"
                               else None for c in cap.PRICE_COLS])])
    counts = cap.capture(conn, NOW)
    assert wired["inserted"] == [] and conn.commits == 0
    assert counts["unchanged"] == 1 and counts["inserted"] == 0


def test_split_changes_writes_a_key_quoted_twice_in_one_fetch_once():
    a = _row(G1, "h2h", "draftkings", home_price=-150)
    to_write, counts = cap.split_changes([a, dict(a)], {})
    assert to_write == [a]
    assert counts == {"new": 1, "changed": 0, "unchanged": 1}


def test_a_link_or_selection_id_alone_is_not_a_change():
    a = {**_row(G1, "h2h", "draftkings", home_price=-150), "home_link": "x", "home_sid": "1"}
    b = {**a, "home_link": "y", "home_sid": "2"}
    _, counts = cap.split_changes([b], {cap._key(a): cap._fingerprint(a)})
    assert counts["unchanged"] == 1


# ── what goes to the parser ──────────────────────────────────────────────────

def test_the_parser_gets_ncaab_open_the_fetch_time_and_a_counting_resolver(wired):
    wired["feed"].extend([
        _event("Kentucky Wildcats", "Kansas Jayhawks", NOW + timedelta(hours=9), []),
        _event("Nowhere State", "Somewhere A&M", NOW + timedelta(hours=9), []),
    ])
    counts = cap.capture(FakeConn(events=_upcoming()), NOW)
    assert wired["get_odds"] == [("basketball_ncaab", ["h2h", "spreads", "totals"])]
    (call,) = wired["process"]
    assert call["sport"] == "NCAAB" and call["snapshot_type"] == "open"
    # The feed's own '...Z' shape: snapshot_at is TEXT and the latest_odds
    # trigger keeps the newest row by comparing it as text.
    assert call["snapshot_at"] == "2026-11-05T15:00:00Z"
    assert counts["resolved"] == 1 and counts["unresolved"] == 1
    assert wired["resolver_args"] == ["2026-11-05"]          # config.today_et()
    assert wired["resolver_days_fwd"] == [cap.RESOLVER_DAYS_FWD]
    assert "failed" not in counts                            # one did resolve


def test_started_games_are_dropped_before_parsing(wired):
    wired["feed"].extend([
        _event("Kentucky Wildcats", "Kansas Jayhawks", NOW - timedelta(minutes=1),
               [_row(G1, "h2h", "draftkings", home_price=-900)]),
        _event("North Carolina Tar Heels", "Duke Blue Devils", NOW,     # tipping now
               [_row(G2, "h2h", "draftkings", home_price=-400)]),
        {**_event("North Carolina Tar Heels", "Duke Blue Devils", NOW, []),
         "id": "no-time", "commence_time": "TBD"},
        _event("North Carolina Tar Heels", "Duke Blue Devils", NOW + timedelta(minutes=1),
               [_row(G2, "spreads", "draftkings", spread_home=2.5)]),
    ])
    counts = cap.capture(FakeConn(events=_upcoming()), NOW)
    assert counts["events"] == 4 and counts["started"] == 3
    (call,) = wired["process"]
    assert len(call["events"]) == 1
    assert [(r["game_id"], r["market"]) for r in wired["inserted"]] == [(G2, "spreads")]


def test_events_past_the_resolver_window_are_set_aside_not_counted_unresolved(wired, monkeypatch):
    # today 2026-11-05, days_fwd 10, one day of skew: 2026-11-16 ET is the
    # last date that can still resolve. 2026-11-17 cannot, on any tick today.
    monkeypatch.setattr(cap, "RESOLVER_DAYS_FWD", 10)
    last_in = datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)      # 22:00 ET Nov 16
    first_out = datetime(2026, 11, 17, 23, 0, tzinfo=timezone.utc)   # 18:00 ET Nov 17
    wired["feed"].extend([
        _event("Kentucky Wildcats", "Kansas Jayhawks", NOW + timedelta(hours=9), []),
        {**_event("Nowhere State", "Somewhere A&M", last_in, []), "id": "in"},
        {**_event("Nowhere State", "Somewhere A&M", first_out, []), "id": "out"},
    ])
    counts = cap.capture(FakeConn(events=_upcoming()), NOW)
    (call,) = wired["process"]
    assert "out" not in call["events"] and "in" in call["events"]
    assert counts["beyond_window"] == 1
    assert counts["resolved"] == 1 and counts["unresolved"] == 1


def test_the_resolver_and_the_window_share_one_bound(wired, monkeypatch):
    """Widening RESOLVER_DAYS_FWD widens both, so an event the resolver could
    now reach is never set aside by a stale bound."""
    monkeypatch.setattr(cap, "RESOLVER_DAYS_FWD", 14)
    tip = datetime(2026, 11, 19, 23, 0, tzinfo=timezone.utc)          # 18:00 ET Nov 19
    wired["feed"].append({**_event("Nowhere State", "Somewhere A&M", tip, []), "id": "d14"})
    counts = cap.capture(FakeConn(events=_upcoming()), NOW)
    assert wired["resolver_days_fwd"] == [14]
    assert counts["beyond_window"] == 0 and wired["process"][0]["events"] == ["d14"]


def test_drop_beyond_window_reads_the_eastern_date():
    # 03:30Z on Nov 17 is 22:30 ET on Nov 16: inside, though its UTC date is not.
    ev = {"commence_time": "2026-11-17T03:30:00Z"}
    keep, beyond = cap.drop_beyond_window([ev], "2026-11-05", days_fwd=10)
    assert keep == [ev] and beyond == 0
    keep, beyond = cap.drop_beyond_window([ev], "2026-11-05", days_fwd=9)
    assert keep == [] and beyond == 1


def test_the_network_call_never_runs_inside_an_open_transaction(wired, monkeypatch):
    """The guard and the resolver read; their transaction must end before the
    call (data/db.release_read), or the tick sits idle in transaction holding
    AccessShareLock on ncaab_events across a network round trip."""
    conn = FakeConn(events=_upcoming())
    open_at_call = []

    def resolver_that_reads(c, around_date, **kw):
        c.execute("SELECT game_id FROM ncaab_events")
        return lambda *a: None

    def get_odds(sport_key, markets):
        open_at_call.append(conn.in_txn)
        return []
    monkeypatch.setattr(ncaab_teams, "make_resolver", resolver_that_reads)
    monkeypatch.setattr(odds_ingestor, "_get_odds", get_odds)
    cap.capture(conn, NOW)
    assert open_at_call == [False]


# ── a broken join is a failure, not a quiet board ────────────────────────────

def test_nothing_resolving_is_a_failed_tick(wired, monkeypatch):
    tip = datetime.now(timezone.utc) + timedelta(hours=2)      # main() reads the real clock
    wired["feed"].extend([
        _event("Nowhere State", "Somewhere A&M", tip, []),
        _event("Elsewhere Tech", "Anywhere U", tip + timedelta(hours=1), []),
    ])
    monkeypatch.setattr(cap.config, "today_et",
                        lambda: tip.astimezone(cap._ET).date().isoformat())
    conn = FakeConn(events=[(tip.strftime("%Y-%m-%d"), _iso(tip))])
    monkeypatch.setattr(cap, "get_connection", lambda *a, **k: conn)
    assert cap.main() == 1
    assert wired["process"] and wired["inserted"] == []
    counts = cap.capture(FakeConn(events=[(tip.strftime("%Y-%m-%d"), _iso(tip))]))
    assert counts["resolved"] == 0 and counts["unresolved"] == 2
    assert counts["failed"] == "nothing resolved"


@pytest.mark.parametrize("feed", ["empty", "started-only", "beyond-only"])
def test_a_board_with_nothing_in_range_is_not_a_failure(wired, feed):
    """No book has posted yet, everything listed has tipped, or everything
    listed is past the resolver's reach: nothing to resolve, nothing broken."""
    if feed == "started-only":
        wired["feed"].append(_event("Nowhere State", "Somewhere A&M",
                                    NOW - timedelta(minutes=5), []))
    if feed == "beyond-only":
        wired["feed"].append(_event("Nowhere State", "Somewhere A&M",
                                    NOW + timedelta(days=20), []))
    counts = cap.capture(FakeConn(events=_upcoming()), NOW)
    assert "failed" not in counts


# ── the credit headers are stored ────────────────────────────────────────────

def test_the_credit_headers_are_stored_after_a_tick_and_after_a_failed_one(wired, monkeypatch):
    tip = datetime.now(timezone.utc) + timedelta(hours=2)      # main() reads the real clock
    monkeypatch.setattr(cap.config, "today_et",
                        lambda: tip.astimezone(cap._ET).date().isoformat())
    wired["feed"].append(_event("Kentucky Wildcats", "Kansas Jayhawks", tip,
                                [_row(G1, "h2h", "draftkings", home_price=-150)]))
    conn = FakeConn(events=[(tip.strftime("%Y-%m-%d"), _iso(tip))])
    monkeypatch.setattr(cap, "get_connection", lambda *a, **k: conn)
    assert cap.main() == 0
    assert wired["quota"] == [False] and conn.closed

    def boom(conn, rows):
        raise RuntimeError("insert failed")
    monkeypatch.setattr(odds_ingestor, "_insert_odds", boom)
    conn2 = FakeConn(events=[(tip.strftime("%Y-%m-%d"), _iso(tip))])
    monkeypatch.setattr(cap, "get_connection", lambda *a, **k: conn2)
    with pytest.raises(RuntimeError, match="insert failed"):
        cap.main()
    # Stored again, and only after the failed write's transaction was cleared.
    assert wired["quota"] == [False, False] and conn2.closed


# ── nothing spent when nothing can be stored ─────────────────────────────────

def test_no_resolver_writes_nothing_and_makes_no_call(wired, monkeypatch):
    monkeypatch.setattr(ncaab_teams, "make_resolver", lambda conn, d, **kw: None)
    conn = FakeConn(events=_upcoming())
    counts = cap.capture(conn, NOW)
    assert counts["skipped"] == "no resolver"
    assert wired["get_odds"] == [] and wired["process"] == [] and wired["inserted"] == []
    assert conn.commits == 0


@pytest.mark.parametrize("events,error", [
    ([], None),                                           # off-season
    ([("2026-11-06", "2026-11-07T03:30Z")], None),        # 36.5 hours out
    ([("2026-11-05", "2026-11-05T14:00Z")], None),        # already tipped
    ([], RuntimeError('relation "ncaab_events" does not exist')),
])
def test_no_game_within_36_hours_makes_no_call(wired, events, error):
    conn = FakeConn(events=events, events_error=error)
    counts = cap.capture(conn, NOW)
    assert counts["skipped"] == "no upcoming games"
    assert wired["get_odds"] == [] and wired["resolver_args"] == []
    assert not any("latest_odds" in s for s, _ in conn.queries)


@pytest.mark.parametrize("events", [
    [("2026-11-06", "2026-11-07T02:30Z")],                # 35.5 hours out
    [("2026-11-05", None)],                               # tip not posted yet
])
def test_a_game_within_36_hours_makes_the_call(wired, events):
    cap.capture(FakeConn(events=events), NOW)
    assert len(wired["get_odds"]) == 1


def test_the_guard_reads_the_eastern_dates_the_window_spans():
    late = datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc)   # 22:00 ET, Nov 4
    conn = FakeConn()
    assert cap.has_upcoming_games(conn, late) is False
    ((sql, params),) = conn.queries
    assert "FROM ncaab_events" in sql
    assert params == ("2026-11-04", "2026-11-06")              # +36h = 10:00 ET Nov 6


def test_the_kill_switch_stops_the_tick_before_any_read(monkeypatch, wired):
    opened = []
    monkeypatch.setattr(cap, "get_connection", lambda *a, **k: opened.append(1))
    for off in ("0", "false", "OFF", "no"):
        monkeypatch.setenv("RUN_NCAAB_ODDS_CAPTURE", off)
        assert cap.main() == 0
    assert opened == [] and wired["get_odds"] == []


def test_the_capture_is_on_by_default(monkeypatch, wired):
    monkeypatch.delenv("RUN_NCAAB_ODDS_CAPTURE", raising=False)
    conn = FakeConn()
    monkeypatch.setattr(cap, "get_connection", lambda *a, **k: conn)
    assert cap.main() == 0
    assert any("FROM ncaab_events" in s for s, _ in conn.queries)
    assert conn.closed


def test_a_failed_call_exits_non_zero(monkeypatch, wired):
    def boom(sport_key, markets):
        raise RuntimeError("Odds API 500")
    monkeypatch.setattr(odds_ingestor, "_get_odds", boom)
    tip = datetime.now(timezone.utc) + timedelta(hours=2)      # main() reads the real clock
    conn = FakeConn(events=[(tip.strftime("%Y-%m-%d"), _iso(tip))])
    monkeypatch.setattr(cap, "get_connection", lambda *a, **k: conn)
    with pytest.raises(RuntimeError, match="Odds API 500"):
        cap.main()
    assert conn.closed


# ── the job ──────────────────────────────────────────────────────────────────

def _jobs(monkeypatch):
    from tests.test_nba_prop_window import _jobs as jobs     # one copy of the helper
    return jobs(monkeypatch)


def test_the_job_runs_every_five_minutes_on_the_pipeline_service_and_is_watched(monkeypatch):
    import scheduler
    from tests.test_nba_prop_window import _fires
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["ncaab_odds_capture"]
    assert job.name.startswith("NCAAB odds capture")
    assert job.max_instances == 1 and job.coalesce is True
    assert job.misfire_grace_time == 120
    start = datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)        # overnight ET
    assert len(_fires(job, start, start + timedelta(minutes=59))) == 12
    assert "ncaab_odds_capture" in scheduler._PIPELINE_JOBS
    assert "ncaab_odds_capture" not in scheduler._POLLER_JOBS
    assert MAX_SILENCE["ncaab_odds_capture"] == 20


def test_the_job_runs_the_script_and_raises_when_it_does_not_finish(monkeypatch):
    import scheduler
    ran = []
    monkeypatch.setattr(scheduler, "_run",
                        lambda cmd, label, **kw: ran.append((cmd, label, kw)) or "ok")
    scheduler.run_ncaab_odds_capture()
    ((cmd, label, kw),) = ran
    assert cmd[-2:] == ["-m", "scripts.ncaab_odds_capture"]
    assert kw["timeout"] == scheduler.NCAAB_ODDS_CAPTURE_TIMEOUT_S
    for outcome in ("fail", "timeout", "error"):
        monkeypatch.setattr(scheduler, "_run", lambda cmd, label, o=outcome, **kw: o)
        with pytest.raises(RuntimeError, match=outcome):
            scheduler.run_ncaab_odds_capture()


def test_the_job_writes_no_picks_so_publishes_nothing():
    import inspect
    import scheduler
    assert "_publish_new_signals" not in inspect.getsource(scheduler.run_ncaab_odds_capture)


def test_the_capture_window_matches_the_refresh_pass_window():
    """Both NCAAB odds writers resolve the same 30 days ahead, so an opener
    the capture can store is one the refresh pass can store too."""
    import inspect
    import data.ingestors.odds_ingestor as oi
    assert cap.RESOLVER_DAYS_FWD == 30
    assert "days_fwd=30" in inspect.getsource(oi._ncaab_resolver)

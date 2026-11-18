"""The archive move (#1345) picks only rows nothing in Supabase needs.

scripts/archive_rows.py writes one rule for both engines. These tests run its
DuckDB form on a small copy; the Postgres form is checked against it on
production before any row is removed (count and fingerprint per game must be
equal, or the game is refused).
"""
from __future__ import annotations

import datetime as dt

import pytest

duckdb = pytest.importorskip("duckdb")

from scripts import archive_rows as ar  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
REAL_ALLOWED = set(ar.ALLOWED)


@pytest.fixture(autouse=True)
def _mechanics_with_props_allowed(monkeypatch):
    """These tests drive the tool's mechanics on prop rows. Whether a move is
    allowed today is its own test, which uses the real list."""
    monkeypatch.setattr(ar, "ALLOWED", {("player_prop_odds", "repeat")})


def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def copy():
    con = duckdb.connect()
    con.execute("CREATE TABLE games (game_id VARCHAR, commence_time VARCHAR)")
    con.execute("""CREATE TABLE player_prop_odds (prop_id BIGINT, game_id VARCHAR,
        player_name VARCHAR, market VARCHAR, bookmaker VARCHAR, snapshot_type VARCHAR,
        snapshot_at VARCHAR, line DOUBLE, over_price DOUBLE, under_price DOUBLE)""")
    con.execute("""CREATE TABLE odds (odds_id BIGINT, game_id VARCHAR, market VARCHAR,
        bookmaker VARCHAR, snapshot_type VARCHAR, snapshot_at VARCHAR, source VARCHAR,
        home_price DOUBLE, away_price DOUBLE, draw_price DOUBLE, spread_home DOUBLE,
        total_line DOUBLE, over_price DOUBLE, under_price DOUBLE, sport VARCHAR)""")
    return con


def _game(con, gid, start):
    con.execute("INSERT INTO games VALUES (?, ?)", [gid, start.isoformat()])


_ids = iter(range(1, 10_000))


def _prop(con, gid, t, over, typ="open", market="player_points", line=20.5, book="fanduel"):
    pid = next(_ids)
    con.execute("INSERT INTO player_prop_odds VALUES (?, ?, 'A', ?, ?, ?, ?, ?, ?, ?)",
                [pid, gid, market, book, typ, _iso(t), line, over, -over])
    return pid


def _picked(con, table, rule, games):
    spec = ar.SPECS[table]
    sql = ar.rule_sql(spec, rule, ar.Dialect("dk"))
    return sorted(r[0] for r in con.execute(sql, ar._params(ar.Dialect("dk"), rule, games, NOW)).fetchall())


def test_a_repeat_moves_but_the_opener_and_the_close_stay(copy):
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)
    h = lambda m: start - dt.timedelta(hours=10) + dt.timedelta(minutes=m)   # noqa: E731
    opener = _prop(copy, "G", h(0), 100)
    repeat = _prop(copy, "G", h(10), 100)          # the same price again
    _prop(copy, "G", h(20), 110)                   # a move
    close = _prop(copy, "G", h(30), 110)           # a repeat, but the last pre-game row
    _prop(copy, "G", start + dt.timedelta(minutes=5), 130, typ="in_play")
    inplay_repeat = _prop(copy, "G", start + dt.timedelta(minutes=10), 130, typ="in_play")
    assert _picked(copy, "player_prop_odds", "repeat", ["G"]) == [repeat, inplay_repeat]
    assert opener not in _picked(copy, "player_prop_odds", "repeat", ["G"])
    assert close not in _picked(copy, "player_prop_odds", "repeat", ["G"])


def test_each_rung_of_an_alternate_line_is_its_own_proposition(copy):
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)
    t = lambda m: start - dt.timedelta(hours=5) + dt.timedelta(minutes=m)    # noqa: E731
    picked = []
    for line, price in ((9.5, 300), (14.5, 600)):
        _prop(copy, "G", t(0), price, market="player_points_alternate", line=line)
        picked.append(_prop(copy, "G", t(10), price, market="player_points_alternate", line=line))
        _prop(copy, "G", t(20), price, market="player_points_alternate", line=line)  # close
    # without the rung, 14.5 would look like a move from 9.5 and 9.5 like a move back
    assert _picked(copy, "player_prop_odds", "repeat", ["G"]) == sorted(picked)


def test_a_game_from_the_last_three_days_is_left_whole(copy):
    start = NOW - dt.timedelta(days=1)
    _game(copy, "G", start)
    for m in (0, 10, 20, 30):
        _prop(copy, "G", start - dt.timedelta(hours=2) + dt.timedelta(minutes=m), 100)
    assert _picked(copy, "player_prop_odds", "repeat", ["G"]) == []


def test_after_90_days_only_the_opener_and_the_close_stay(copy):
    start = NOW - dt.timedelta(days=100)
    _game(copy, "G", start)
    h = lambda m: start - dt.timedelta(hours=10) + dt.timedelta(minutes=m)   # noqa: E731
    ids = [_prop(copy, "G", h(m), 100 + m) for m in (0, 10, 20, 30)]       # every row a move
    after = _prop(copy, "G", start + dt.timedelta(minutes=5), 200, typ="in_play")
    assert _picked(copy, "player_prop_odds", "old", ["G"]) == sorted(ids[1:3] + [after])
    # the repeat rule alone moves none of them: each is a move
    assert _picked(copy, "player_prop_odds", "repeat", ["G"]) == []


def test_game_odds_repeat_compares_every_price_and_line(copy):
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)

    def row(m, home, total=None, market="h2h"):
        oid = next(_ids)
        copy.execute("INSERT INTO odds VALUES (?, 'G', ?, 'betmgm', 'open', ?, NULL, ?, ?, NULL, NULL, ?, NULL, NULL, 'NBA')",
                     [oid, market, _iso(start - dt.timedelta(hours=3) + dt.timedelta(minutes=m)),
                      home, -home, total])
        return oid
    row(0, -120)
    rep = row(10, -120)
    row(20, -125)
    row(30, -125)       # close
    assert _picked(copy, "odds", "repeat", ["G"]) == [rep]


def test_the_file_holds_exactly_the_picked_rows_and_reads_back_alike(copy, tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "ARCHIVE_ROOT", tmp_path)
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)
    h = lambda m: start - dt.timedelta(hours=10) + dt.timedelta(minutes=m)   # noqa: E731
    for m, p in ((0, 100), (10, 100), (20, 100), (30, 110), (40, 110)):
        _prop(copy, "G", h(m), p)
    spec = ar.SPECS["player_prop_odds"]
    mine = ar.copy_selection(copy, spec, "repeat", ["G"], NOW)
    path = ar.file_path("player_prop_odds", "repeat", "2026-11-06")
    ar.write_file(copy, spec, "repeat", ["G"], NOW, path)
    assert mine["G"][0] == 2
    assert ar.file_selection(spec, path) == mine


def test_a_removal_is_refused_when_postgres_picks_other_rows():
    class Conn:
        def __init__(self):
            self.rolled = False

        def execute(self, sql, params=None):
            class R:
                rowcount = 0

                def fetchone(self):
                    return (3, "999")
            return R()

        def rollback(self):
            self.rolled = True

        def commit(self):
            raise AssertionError("nothing may be committed")
    conn = Conn()
    with pytest.raises(RuntimeError, match="nothing removed"):
        ar.remove_game(conn, ar.SPECS["odds"], "repeat", "G", (2, 111), NOW)
    assert conn.rolled


@pytest.mark.parametrize("table,rule", [("odds", "repeat"), ("odds", "old"), ("player_prop_odds", "old"),
                                        ("player_prop_odds", "repeat")])
def test_a_move_with_a_reader_that_would_break_is_refused(table, rule, monkeypatch):
    # Prop repeats too since 2026-11-18: the app's "At pick" price read them (#1458).
    monkeypatch.setattr(ar, "ALLOWED", REAL_ALLOWED)
    with pytest.raises(SystemExit, match="may not move yet"):
        ar.check_allowed(table, rule)


# One repeat in each group of game-odds rows a reader needs whole, and the same
# repeat in a group nothing needs. Only the last may move.
KEPT_WHOLE = [
    ("MLB", "h2h", "open", None),                                   # market_movement's mkt_snapshots
    ("MLB", "totals", "close", None),
    ("MLB", "totals", "in_play", "historical_inplay|req=a|served=b"),  # a paid in-play buyer's rows
    ("NCAAF", "h2h", "in_play", "historical_inplay|req=a|served=b"),
    ("NCAAB", "h2h", "in_play", "odds_api_ncaab_inplay_history"),
    ("NBA", "spreads", "in_play", None),                            # the NBA in-play model's fetch groups
    ("NHL", "totals", "open", "odds_api_historical"),               # the NHL totals lab
    ("NFL", "h2h", "open", "nfl_odds_cache|served=2025-09-07T16:00:00Z"),  # the cache import
]
MOVES = [
    ("NBA", "h2h", "open", None),
    ("MLB", "alternate_totals", "open", None),
    ("MLB", "totals", "in_play", None),
    ("NHL", "totals", "open", None),
    ("NHL", "h2h", "open", "odds_api_historical"),
]


def _odds_path(con, gid, start, sport, market, typ, source):
    """Four rows at one price: opener, repeat, repeat, close. Returns the middle two."""
    ids = []
    for m in (0, 10, 20, 30):
        t = start - dt.timedelta(hours=3) + dt.timedelta(minutes=m)
        if typ == "in_play":
            t = start + dt.timedelta(minutes=m)
        oid = next(_ids)
        con.execute("INSERT INTO odds VALUES (?, ?, ?, 'draftkings', ?, ?, ?, -120, 100, NULL, NULL, 8.5, -110, -110, ?)",
                    [oid, gid, market, typ, _iso(t), source, sport])
        ids.append(oid)
    return ids[1:3] if typ != "in_play" else ids[1:]


@pytest.mark.parametrize("sport,market,typ,source", KEPT_WHOLE)
def test_game_odds_a_reader_needs_whole_never_move(copy, sport, market, typ, source):
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)
    _odds_path(copy, "G", start, sport, market, typ, source)
    assert _picked(copy, "odds", "repeat", ["G"]) == []


@pytest.mark.parametrize("sport,market,typ,source", MOVES)
def test_game_odds_repeats_nothing_needs_whole_move(copy, sport, market, typ, source):
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)
    reps = _odds_path(copy, "G", start, sport, market, typ, source)
    assert _picked(copy, "odds", "repeat", ["G"]) == sorted(reps)


def test_the_postgres_keep_list_is_the_duckdb_one_with_its_percent_doubled():
    spec = ar.SPECS["odds"]
    assert spec.keep_pg == spec.keep_dk.replace("%", "%%")
    assert "historical_inplay%%" in spec.keep_pg
    assert ar.SPECS["player_prop_odds"].keep_pg == "FALSE"


def test_a_dropped_connection_retries_the_date_on_a_new_one(monkeypatch):
    from data.db import ConnectionLost
    calls = []

    def prepare(copy, conn, table, rule, date, now, log, **kw):
        calls.append((conn, date))
        if conn == "first":
            raise ConnectionLost("server closed the connection unexpectedly")
        return {"rows": 5, "refused": [], "ready": 1}

    class Old:
        def close(self):
            pass
    monkeypatch.setattr(ar, "prepare", prepare)
    monkeypatch.setattr(ar, "_storage", lambda: (_ for _ in ()).throw(RuntimeError("no key")))
    first = Old()
    calls.clear()
    seq = iter(["second"])
    out = ar.run(None, "first", "player_prop_odds", "repeat", "2026-06-30", "2026-06-30", NOW,
                 log=lambda *_: None, connect=lambda: next(seq))
    assert [c for _, c in calls] == ["2026-06-30", "2026-06-30"]
    assert out["dates"] == 1 and out["prepared_rows"] == 5
    with pytest.raises(ConnectionLost):
        ar.run(None, "first", "player_prop_odds", "repeat", "2026-06-30", "2026-06-30", NOW,
               log=lambda *_: None)


def _timeout():
    import psycopg2.errors
    return psycopg2.errors.QueryCanceled("canceling statement due to statement timeout")


def test_a_statement_timeout_is_not_retried_as_a_dropped_connection(monkeypatch):
    # 2026-09-10 timed out and was read again, twice, at the same size.
    calls = []

    def prepare(copy, conn, table, rule, date, now, log, **kw):
        calls.append(date)
        raise _timeout()
    monkeypatch.setattr(ar, "prepare", prepare)
    monkeypatch.setattr(ar, "_storage", lambda: (_ for _ in ()).throw(RuntimeError("no key")))
    import psycopg2.errors
    with pytest.raises(psycopg2.errors.QueryCanceled):
        ar.run(None, "first", "player_prop_odds", "repeat", "2026-09-10", "2026-09-10", NOW,
               log=lambda *_: None, connect=lambda: "second")
    assert calls == ["2026-09-10"]


class _Conn:
    """Records every statement; answers the ledger read with `ledger`."""

    def __init__(self, ledger=(), active=0, app_s=0.0):
        self.sql = []
        self.ledger = list(ledger)
        self.active = active if callable(active) else (lambda: active)
        self.app_s = app_s if callable(app_s) else (lambda: app_s)
        self.lock_free = True

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        conn = self

        class R:
            rowcount = 0

            def fetchall(self):
                return conn.ledger if "FROM archive_batches" in sql else []

            def fetchone(self):
                if "pg_try_advisory_lock" in sql:
                    return (conn.lock_free,)
                return (conn.active(), conn.app_s()) if "pg_stat_activity" in sql else (0, "0")
        return R()

    def rollback(self):
        pass

    def commit(self):
        pass


def test_prepare_reads_the_pc_copy_only(copy, tmp_path, monkeypatch):
    # The daytime pass that also picked every game in Postgres coincided with
    # 178 statement timeouts on 2026-11-16. The removal checks Postgres anyway.
    monkeypatch.setattr(ar, "ARCHIVE_ROOT", tmp_path)
    monkeypatch.setattr(ar, "ensure_ledger", lambda conn: None)
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)
    for m, p in ((0, 100), (10, 100), (20, 110)):
        _prop(copy, "G", start - dt.timedelta(hours=5) + dt.timedelta(minutes=m), p)
    day = start.astimezone(ar.ET).date().isoformat()
    conn = _Conn()
    out = ar.prepare(copy, conn, "player_prop_odds", "repeat", day, NOW, log=lambda *_: None)
    assert out["ready"] == 1 and out["refused"] == []
    assert not [s for s, _ in conn.sql if "player_prop_odds t" in s], "prepare read Postgres"
    inserts = [p for s, p in conn.sql if "INSERT INTO archive_batches" in s]
    assert len(inserts) == 1 and inserts[0][-1] is None


def _stored(copy, tmp_path, monkeypatch, games):
    monkeypatch.setattr(ar, "ARCHIVE_ROOT", tmp_path)
    start = NOW - dt.timedelta(days=10)
    for g in games:
        _game(copy, g, start)
        for m in (0, 10, 20):
            _prop(copy, g, start - dt.timedelta(hours=5) + dt.timedelta(minutes=m), 100)
    spec = ar.SPECS["player_prop_odds"]
    day = "2026-11-06"
    path = ar.file_path("player_prop_odds", "repeat", day)
    ar.write_file(copy, spec, "repeat", list(games), NOW, path)
    sel = ar.file_selection(spec, path)
    digest = ar.sha256(path)
    ledger = [(g, sel[g][0], str(sel[g][1]), digest, NOW, None, None) for g in games]
    return day, ledger


def test_a_slow_game_is_noted_and_skipped_and_the_rest_still_go(copy, tmp_path, monkeypatch):
    day, ledger = _stored(copy, tmp_path, monkeypatch, ["SLOW", "BAD", "OK"])
    monkeypatch.setattr(ar, "wait_for_quiet", lambda *a, **k: True, raising=False)

    def remove_game(conn, spec, rule, game, want, now):
        if game == "SLOW":
            raise _timeout()
        if game == "BAD":
            raise RuntimeError("BAD: Postgres picks 3 rows; nothing removed")
        return want[0]
    monkeypatch.setattr(ar, "remove_game", remove_game)
    conn = _Conn(ledger)
    out = ar.remove(conn, "player_prop_odds", "repeat", day, NOW, log=lambda *_: None)
    assert out["removed"] == 1 and out["games"] == 1
    assert {g for g, _ in out["skipped"]} == {"SLOW", "BAD"}
    notes = {p[-1]: p[0] for s, p in conn.sql if "SET note" in s}
    assert notes["SLOW"].startswith("removal timed out")
    assert notes["BAD"].startswith("refused at removal")


def test_a_game_that_timed_out_is_tried_again_the_next_night(copy, tmp_path, monkeypatch):
    day, ledger = _stored(copy, tmp_path, monkeypatch, ["SLOW"])
    g, n, c, sha, stored, removed, _ = ledger[0]
    monkeypatch.setattr(ar, "wait_for_quiet", lambda *a, **k: True, raising=False)
    monkeypatch.setattr(ar, "remove_game", lambda conn, spec, rule, game, want, now: want[0])
    for note, gone in (("removal timed out after 900s at 2026-11-17T07:00:00Z; left in Supabase", 1),
                       ("refused at removal: Postgres picks 3 rows", 0)):
        conn = _Conn([(g, n, c, sha, stored, removed, note)])
        out = ar.remove(conn, "player_prop_odds", "repeat", day, NOW, log=lambda *_: None)
        assert out["removed"] == gone


def _clock(start_et):
    t = [start_et.astimezone(UTC)]

    def clock():
        return t[0]

    def sleeper(s):
        t[0] = t[0] + dt.timedelta(seconds=s)
    return clock, sleeper, t


def test_removals_run_only_in_the_overnight_quiet_window():
    def at(h, m):
        return dt.datetime(2026, 11, 17, h, m, tzinfo=ar.ET)
    # midday: no removal, and nothing waits
    clock, sleeper, t = _clock(at(14, 0))
    assert ar.wait_for_quiet(_Conn(), clock, sleeper, log=lambda *_: None) is False
    assert t[0] == at(14, 0).astimezone(UTC)
    # 02:00, quiet: go now
    clock, sleeper, t = _clock(at(2, 0))
    assert ar.wait_for_quiet(_Conn(), clock, sleeper, log=lambda *_: None) is True
    assert t[0] == at(2, 0).astimezone(UTC)
    # 02:16: the refresh pass runs; wait for 02:28
    clock, sleeper, t = _clock(at(2, 16))
    assert ar.wait_for_quiet(_Conn(), clock, sleeper, log=lambda *_: None) is True
    assert t[0] == at(2, 28).astimezone(UTC)
    # busy, then quiet
    seen = iter([9, 9, 2])
    clock, sleeper, t = _clock(at(3, 0))
    assert ar.wait_for_quiet(_Conn(active=lambda: next(seen)), clock, sleeper, log=lambda *_: None)
    assert t[0] == (at(3, 0) + dt.timedelta(seconds=2 * ar.BUSY_SLEEP_S)).astimezone(UTC)
    # 05:29 busy until the window closes: stop, do not run into the 06:00 pipeline
    clock, sleeper, t = _clock(at(5, 29))
    assert ar.wait_for_quiet(_Conn(active=9), clock, sleeper, log=lambda *_: None) is False


def test_no_row_is_removed_outside_the_window(copy, tmp_path, monkeypatch):
    day, ledger = _stored(copy, tmp_path, monkeypatch, ["G"])
    called = []
    monkeypatch.setattr(ar, "remove_game", lambda *a: called.append(a) or 1)
    clock, sleeper, _ = _clock(dt.datetime(2026, 11, 17, 14, 0, tzinfo=ar.ET))
    out = ar.remove(_Conn(ledger), "player_prop_odds", "repeat", day, NOW, log=lambda *_: None,
                    clock=clock, sleeper=sleeper)
    assert called == [] and out["stopped"]


class _Storage:
    """Storage that refuses any object over `limit` bytes, like HTTP 413."""

    def __init__(self, limit, corrupt=None):
        self.objects, self.limit, self.corrupt = {}, limit, corrupt

    def _r(self, code, content=b"", js=None):
        class R:
            status_code = code
            text = ""

            def json(self):
                return js or {}
        r = R()
        r.content = content
        return r

    def get(self, url, timeout=None):
        if "/bucket/" in url:
            return self._r(200, js={"public": False})
        name = url.split("/object/archive/", 1)[1]
        body = self.objects.get(name)
        if body is not None and name == self.corrupt:
            body = body[:-1] + b"?"
        return self._r(200 if body is not None else 404, body or b"")

    def post(self, url, data=None, timeout=None, headers=None):
        body = data if isinstance(data, bytes) else data.read()
        if len(body) > self.limit:
            return self._r(400)
        self.objects[url.split("/object/archive/", 1)[1]] = body
        return self._r(200)


def test_a_file_over_the_storage_limit_goes_up_in_parts(tmp_path, monkeypatch):
    # 2026-09-13 (70.5 MB) and 2026-09-20 (52.9 MB) were refused whole.
    monkeypatch.setattr(ar, "PART_BYTES", 10)
    f = tmp_path / "2026-09-13.parquet"
    f.write_bytes(bytes(range(256)) * 1)            # 256 bytes, 26 parts of 10
    st = _Storage(limit=12)
    digest = ar.upload_and_check(f, "p/2026-09-13.parquet", storage=(st, "https://x"))
    assert digest == ar.sha256(f)
    assert sorted(st.objects) == ar.part_names("p/2026-09-13.parquet", 256)
    assert b"".join(st.objects[n] for n in ar.part_names("p/2026-09-13.parquet", 256)) == f.read_bytes()
    # a small file stays one object, under its own name
    small = tmp_path / "small.parquet"
    small.write_bytes(b"abc")
    ar.upload_and_check(small, "p/small.parquet", storage=(st, "https://x"))
    assert st.objects["p/small.parquet"] == b"abc"
    # one bad byte in one part read back: refused
    st2 = _Storage(limit=12, corrupt="p/2026-09-13.parquet.part-007")
    with pytest.raises(RuntimeError, match="differs"):
        ar.upload_and_check(f, "p/2026-09-13.parquet", storage=(st2, "https://x"))


def test_now_mode_runs_in_the_daytime_but_waits_for_slow_app_reads():
    # mike, 2026-11-16: "why cant you just fuckin run it now". App reads give
    # up at 8 s, so a removal waits while one has run 2 s.
    def at(h, m):
        return dt.datetime(2026, 11, 16, h, m, tzinfo=ar.ET)
    clock, sleeper, t = _clock(at(18, 40))
    assert ar.wait_for_quiet(_Conn(), clock, sleeper, log=lambda *_: None, anytime=True) is True
    assert t[0] == at(18, 40).astimezone(UTC)
    slow = iter([5.0, 3.1, 0.4])
    clock, sleeper, t = _clock(at(18, 40))
    assert ar.wait_for_quiet(_Conn(app_s=lambda: next(slow)), clock, sleeper,
                             log=lambda *_: None, anytime=True) is True
    assert t[0] > at(18, 40).astimezone(UTC)
    # the morning window still closes it: 06:00 waits past 07:16 and the 07:17 refresh
    clock, sleeper, t = _clock(at(6, 0))
    assert ar.wait_for_quiet(_Conn(), clock, sleeper, log=lambda *_: None, anytime=True) is True
    assert t[0] == at(7, 28).astimezone(UTC)
    # without --now, the daytime is still closed
    clock, sleeper, t = _clock(at(18, 40))
    assert ar.wait_for_quiet(_Conn(), clock, sleeper, log=lambda *_: None) is False


def test_now_mode_rests_after_each_game_as_long_as_it_took(copy, tmp_path, monkeypatch):
    day, ledger = _stored(copy, tmp_path, monkeypatch, ["A", "B"])
    clock, sleeper, t = _clock(dt.datetime(2026, 11, 16, 18, 40, tzinfo=ar.ET))
    rests = []

    def remove_game(conn, spec, rule, game, want, now):
        t[0] = t[0] + dt.timedelta(seconds=30)      # each game takes 30 s
        return want[0]

    def sleep(s):
        rests.append(s)
        sleeper(s)
    monkeypatch.setattr(ar, "remove_game", remove_game)
    out = ar.remove(_Conn(ledger), "player_prop_odds", "repeat", day, NOW, log=lambda *_: None,
                    clock=clock, sleeper=sleep, anytime=True)
    assert out["games"] == 2 and rests == [30.0, 30.0]


def test_a_second_removal_run_does_nothing_while_one_is_running(monkeypatch):
    called = []
    monkeypatch.setattr(ar, "remove", lambda *a, **k: called.append(a))
    conn = _Conn([("2026-11-06",)])
    conn.lock_free = False
    out = ar.remove_pending(conn, "player_prop_odds", "repeat", NOW, log=lambda *_: None)
    assert out["stopped"] == "another removal is running" and called == []


def test_one_market_at_a_time_picks_exactly_what_the_whole_game_picks(copy):
    # A large game is removed one market a transaction (2026-11-16: one
    # 408,831-row game held the disk 395 s). The rule never compares across
    # markets, so the markets' picks must add up to the game's, row for row.
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)
    h = lambda m: start - dt.timedelta(hours=5) + dt.timedelta(minutes=m)   # noqa: E731
    for market in ("player_points", "player_rebounds", "player_points_alternate"):
        for m, p in ((0, 100), (10, 100), (20, 120), (30, 120), (40, 120)):
            _prop(copy, "G", h(m), p, market=market)
    spec = ar.SPECS["player_prop_odds"]
    dk = ar.Dialect("dk")
    whole = sorted(r[0] for r in copy.execute(ar.rule_sql(spec, "repeat", dk),
                                              ar._params(dk, "repeat", ["G"], NOW)).fetchall())
    parts = []
    for market in ("player_points", "player_rebounds", "player_points_alternate"):
        parts += [r[0] for r in copy.execute(ar.rule_sql(spec, "repeat", dk, by_market=True),
                                             ar._params(dk, "repeat", ["G"], NOW, market)).fetchall()]
    assert whole and sorted(parts) == whole


class _MarketConn(_Conn):
    """Postgres as seen by remove_market: per market, what the rule picks now
    and how many archived rows are still there."""

    def __init__(self, picks, left):
        super().__init__()
        self.picks, self.left, self.market, self.deleted = picks, left, None, []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        conn = self
        if "CREATE TEMP TABLE archive_pick" in sql:
            self.market = params[1]

        class R:
            rowcount = 0

            def fetchall(self):
                return conn.ledger if "FROM archive_batches" in sql else []

            def fetchone(self):
                if "FROM archive_pick" in sql:
                    return conn.picks[conn.market]
                if "= ANY(%s)" in sql:
                    return (conn.left[conn.market],)
                return (conn.active(), conn.app_s()) if "pg_stat_activity" in sql else (0, "0")
        r = R()
        if sql.startswith("DELETE"):
            r.rowcount = self.picks[self.market][0]
            self.deleted.append(self.market)
        return r


def test_a_large_game_goes_one_market_at_a_time_and_resumes(copy, tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "ARCHIVE_ROOT", tmp_path)
    monkeypatch.setattr(ar, "SPLIT_ROWS", 1)
    start = NOW - dt.timedelta(days=10)
    _game(copy, "G", start)
    for market in ("player_points", "player_rebounds"):
        for m in (0, 10, 20, 30):
            _prop(copy, "G", start - dt.timedelta(hours=5) + dt.timedelta(minutes=m), 100, market=market)
    spec = ar.SPECS["player_prop_odds"]
    day = "2026-11-06"
    path = ar.file_path("player_prop_odds", "repeat", day)
    ar.write_file(copy, spec, "repeat", ["G"], NOW, path)
    fm = ar.file_markets(spec, path, "G")
    n, c = ar.file_selection(spec, path)["G"]
    ledger = [("G", n, str(c), ar.sha256(path), NOW, None, None)]
    monkeypatch.setattr(ar, "wait_for_quiet", lambda *a, **k: True)
    # points was removed by a run that stopped part-way; rebounds is still there
    conn = _MarketConn(picks={"player_points": (0, "0"),
                              "player_rebounds": (fm["player_rebounds"][0], str(fm["player_rebounds"][1]))},
                       left={"player_points": 0, "player_rebounds": fm["player_rebounds"][0]})
    conn.ledger = ledger
    out = ar.remove(conn, "player_prop_odds", "repeat", day, NOW, log=lambda *_: None)
    assert conn.deleted == ["player_rebounds"]
    assert out["games"] == 1 and out["removed"] == fm["player_rebounds"][0]
    done = [p for s, p in conn.sql if "SET removed_at" in s]
    assert done == [(n, "player_prop_odds", "repeat", "G")]
    # a market Postgres disagrees on: nothing deleted, the game noted and kept
    bad = _MarketConn(picks={"player_points": (fm["player_points"][0], "999"),
                             "player_rebounds": (fm["player_rebounds"][0], str(fm["player_rebounds"][1]))},
                      left={"player_points": fm["player_points"][0], "player_rebounds": 0})
    bad.ledger = ledger
    out = ar.remove(bad, "player_prop_odds", "repeat", day, NOW, log=lambda *_: None)
    assert bad.deleted == [] and out["games"] == 0
    assert any(p[0].startswith("refused at removal") for s, p in bad.sql if "SET note" in s)
    assert not [p for s, p in bad.sql if "SET removed_at" in s]


# ── Bulk (game odds, 2026-11-18): one pass of the copy; small games together ──

def _two_days_of_props(copy):
    days = []
    for gid, back in (("A", 10), ("B", 10), ("C", 11)):
        start = NOW - dt.timedelta(days=back)
        _game(copy, gid, start)
        for m, p in ((0, 100), (10, 100), (20, 100), (30, 110)):
            _prop(copy, gid, start - dt.timedelta(hours=5) + dt.timedelta(minutes=m), p)
        days.append(start.astimezone(ar.ET).date().isoformat())
    return sorted(set(days))


def test_bulk_prepare_writes_what_prepare_writes_date_by_date(copy, tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "ensure_ledger", lambda conn: None)
    days = _two_days_of_props(copy)
    assert len(days) == 2
    monkeypatch.setattr(ar, "ARCHIVE_ROOT", tmp_path / "one")
    for day in days:
        ar.prepare(copy, _Conn(), "player_prop_odds", "repeat", day, NOW, log=lambda *_: None)
    one = {d: ar.file_selection(ar.SPECS["player_prop_odds"],
                                ar.file_path("player_prop_odds", "repeat", d)) for d in days}
    monkeypatch.setattr(ar, "ARCHIVE_ROOT", tmp_path / "bulk")
    conn = _Conn()
    out = ar.prepare_range(copy, conn, "player_prop_odds", "repeat", days[0], days[-1], NOW,
                           log=lambda *_: None)
    bulk = {d: ar.file_selection(ar.SPECS["player_prop_odds"],
                                 ar.file_path("player_prop_odds", "repeat", d)) for d in days}
    assert bulk == one and out["dates"] == 2 and out["games"] == 3
    # one ledger statement per date, holding every game of that date
    inserts = [p for s, p in conn.sql if "INSERT INTO archive_batches" in s]
    assert len(inserts) == 2
    assert sorted(g for p in inserts for g in p[5]) == ["A", "B", "C"]


def test_bulk_prepare_never_rewrites_a_date_already_in_storage(copy, tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "ensure_ledger", lambda conn: None)
    monkeypatch.setattr(ar, "ARCHIVE_ROOT", tmp_path)
    days = _two_days_of_props(copy)
    conn = _Conn(ledger=[(days[0],)])          # the ledger: days[0] is already stored
    out = ar.prepare_range(copy, conn, "player_prop_odds", "repeat", days[0], days[-1], NOW,
                           log=lambda *_: None)
    assert out["dates"] == 1
    assert not ar.file_path("player_prop_odds", "repeat", days[0]).exists()
    assert ar.file_path("player_prop_odds", "repeat", days[1]).exists()


class _BatchConn(_Conn):
    """Postgres as remove_batch sees it: what the rule picks per game now."""

    def __init__(self, picks):
        super().__init__()
        self.picks, self.deleted, self.marked = picks, None, None

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        conn = self

        class R:
            rowcount = 0

            def fetchall(self):
                if "FROM archive_pick GROUP BY game_id" in sql:
                    return [(g, n, c) for g, (n, c) in conn.picks.items()]
                return []
        r = R()
        if sql.startswith("DELETE"):
            self.deleted = list(params[0])
            r.rowcount = sum(self.picks[g][0] for g in params[0])
        if "SET removed_at" in sql:
            self.marked = list(params[0])
        return r


def test_a_batch_removes_only_the_games_postgres_agrees_on():
    wants = {"A": (3, 111), "B": (2, 222), "C": (4, 333)}
    conn = _BatchConn({"A": (3, "111"), "B": (2, "999"), "C": (4, "333")})   # B's rows changed
    got, refused = ar.remove_batch(conn, ar.SPECS["odds"], "repeat", wants, NOW)
    assert got == 7 and set(refused) == {"B"}
    assert conn.deleted == ["A", "C"] and conn.marked == ["A", "C"]


def test_a_batch_where_postgres_agrees_on_nothing_deletes_nothing():
    conn = _BatchConn({"A": (1, "5")})
    got, refused = ar.remove_batch(conn, ar.SPECS["odds"], "repeat", {"A": (3, 111)}, NOW)
    assert got == 0 and set(refused) == {"A"} and conn.deleted is None


def test_batched_removal_groups_small_games_and_notes_the_refused(copy, tmp_path, monkeypatch):
    day, ledger = _stored(copy, tmp_path, monkeypatch, ["A", "B", "C", "D", "E"])
    monkeypatch.setattr(ar, "wait_for_quiet", lambda *a, **k: True)
    monkeypatch.setattr(ar, "BATCH_GAMES", 2)
    calls = []

    def remove_batch(conn, spec, rule, wants, now):
        calls.append(sorted(wants))
        bad = {g: f"{g}: Postgres picks other rows" for g in wants if g == "D"}
        return sum(w[0] for g, w in wants.items() if g not in bad), bad
    monkeypatch.setattr(ar, "remove_batch", remove_batch)
    conn = _Conn(ledger)
    out = ar.remove(conn, "player_prop_odds", "repeat", day, NOW, log=lambda *_: None,
                    batch_rows=10_000)
    assert calls == [["A", "B"], ["C", "D"], ["E"]]
    assert out["games"] == 4 and [g for g, _ in out["skipped"]] == ["D"]
    notes = {p[-1]: p[0] for s, p in conn.sql if "SET note" in s}
    assert notes["D"].startswith("refused at removal")

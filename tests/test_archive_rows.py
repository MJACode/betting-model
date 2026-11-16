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
        total_line DOUBLE, over_price DOUBLE, under_price DOUBLE)""")
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
        copy.execute("INSERT INTO odds VALUES (?, 'G', ?, 'betmgm', 'open', ?, NULL, ?, ?, NULL, NULL, ?, NULL, NULL)",
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


@pytest.mark.parametrize("table,rule", [("odds", "repeat"), ("odds", "old"), ("player_prop_odds", "old")])
def test_a_move_with_a_reader_that_would_break_is_refused(table, rule):
    with pytest.raises(SystemExit, match="may not move yet"):
        ar.check_allowed(table, rule)
    ar.check_allowed("player_prop_odds", "repeat")


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

    def __init__(self, ledger=(), active=0):
        self.sql = []
        self.ledger = list(ledger)
        self.active = active if callable(active) else (lambda: active)

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        conn = self

        class R:
            rowcount = 0

            def fetchall(self):
                return conn.ledger if "FROM archive_batches" in sql else []

            def fetchone(self):
                return (conn.active(),) if "pg_stat_activity" in sql else (0, "0")
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

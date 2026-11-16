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

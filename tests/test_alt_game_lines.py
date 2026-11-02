"""Alternate spreads and totals (Matt, 2026-10-29): data/ingestors/alt_game_lines.py
and add_alt_game_lines_2026_10_29.sql.

What it pins:
  - a spread rung is the HOME number with both prices; a rung missing a side
    is not stored; totals need both sides
  - only line-shop books are kept, every row carries SOURCE
  - the window fails closed and never buys a game that has started
  - the game id is the live pass's: built for minted sports, asked of the
    schedule (with the flip) for resolver sports, never minted for NCAAB
  - the source is protected from the pruner, the migration is active, and the
    app may read the table
  - on a scratch Postgres: a re-fetch REPLACES the game's ladder, anon can
    read it, and a second pass of the migration is a no-op
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from data.ingestors import alt_game_lines as alt

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "data" / "migrations" / "add_alt_game_lines_2026_10_29.sql").read_text(encoding="utf-8")

SPREADS = {
    "key": "alternate_spreads", "last_update": "2026-10-29T10:00:00Z",
    "outcomes": [
        {"name": "Buffalo Bills", "point": -3.5, "price": -110, "link": "hb35"},
        {"name": "Kansas City Chiefs", "point": 3.5, "price": -110, "link": "ak35"},
        {"name": "Buffalo Bills", "point": -6.5, "price": 160},
        {"name": "Kansas City Chiefs", "point": 6.5, "price": -190},
        {"name": "Buffalo Bills", "point": -9.5, "price": 260},   # no away side
    ],
}
TOTALS = {
    "key": "alternate_totals",
    "outcomes": [
        {"name": "Over", "point": 47.5, "price": -110},
        {"name": "Under", "point": 47.5, "price": -110},
        {"name": "Over", "point": 51.5, "price": 150},            # no under
    ],
}


def test_a_spread_rung_is_the_home_number_with_both_prices():
    rows = alt.parse_ladder([SPREADS], "Buffalo Bills")
    got = sorted((r["spread_home"], r["home_price"], r["away_price"]) for r in rows)
    assert got == [(-6.5, 160, -190), (-3.5, -110, -110)]
    r35 = next(r for r in rows if r["spread_home"] == -3.5)
    assert (r35["home_link"], r35["away_link"], r35["snapshot_at"]) == ("hb35", "ak35", "2026-10-29T10:00:00Z")


def test_a_total_needs_both_sides():
    rows = alt.parse_ladder([TOTALS], "Buffalo Bills")
    assert [(r["total_line"], r["over_price"], r["under_price"]) for r in rows] == [(47.5, -110, -110)]


def test_only_line_shop_books_and_every_row_carries_the_source():
    body = {"bookmakers": [
        {"key": "draftkings", "markets": [SPREADS, TOTALS]},
        {"key": "not_a_book", "markets": [SPREADS]},
    ]}
    rows = alt.event_rows(body, "NFL_2026-11-01_KC_BUF", "NFL", "Buffalo Bills",
                          datetime(2026, 10, 29, 11, tzinfo=timezone.utc))
    assert {r["bookmaker"] for r in rows} == {"draftkings"}
    assert len(rows) == 3
    assert all(r["source"] == alt.SOURCE and r["snapshot_type"] == "open" for r in rows)
    assert set(rows[0]) == set(alt._ODDS_KEYS)
    # A market with no last_update takes the fetch time.
    assert next(r for r in rows if r["market"] == "alternate_totals")["snapshot_at"] == "2026-10-29T11:00:00Z"


def test_the_window_fails_closed_and_never_buys_a_started_game():
    now = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
    at = lambda h: {"commence_time": (now + timedelta(hours=h)).isoformat()}
    assert alt.in_window(at(5), now)
    assert not alt.in_window(at(-1), now)            # started
    assert not alt.in_window(at(24 * 3 + 1), now)    # past the window
    assert not alt.in_window({}, now)                # undatable: not bought
    assert not alt.in_window({"commence_time": "soon"}, now)


def test_the_game_id_is_the_live_passes():
    ev = {"home_team": "Boston Celtics", "away_team": "New York Knicks",
          "commence_time": "2026-10-30T23:30:00Z"}
    gid, home = alt.game_for_event("NBA", ev)
    assert gid == "NBA_2026-10-30_NYK_BOS" and home == "Boston Celtics"
    # A late tip is still the Eastern date.
    late = {**ev, "commence_time": "2026-10-31T02:30:00Z"}
    assert alt.game_for_event("NBA", late)[0] == "NBA_2026-10-30_NYK_BOS"


def test_a_resolver_sport_asks_the_schedule_and_honours_the_flip():
    ev = {"home_team": "Duke", "away_team": "UNC", "commence_time": "2026-11-05T00:00:00Z"}
    assert alt.game_for_event("NCAAB", ev, lambda h, a, t: ("NCAAB_X", True)) == ("NCAAB_X", "UNC")
    assert alt.game_for_event("NCAAB", ev, lambda h, a, t: None) is None
    assert alt.game_for_event("NCAAB", ev) is None   # never minted


def test_the_source_is_protected_the_migration_active_and_the_table_readable():
    from data.anon_readable import ANON_READABLE
    from data.prune_odds import PROTECTED_SOURCES
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert alt.SOURCE in PROTECTED_SOURCES
    assert "add_alt_game_lines_2026_10_29.sql" in ACTIVE_MIGRATIONS
    assert alt.STATE_TABLE in ANON_READABLE


def test_the_daily_pipeline_runs_it_after_the_opening_odds():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    odds = src.index('results["odds"] = step_odds(run_date, snapshot_type="open")')
    assert odds < src.index('results["alt_game_lines"] = step_alt_game_lines(run_date)')
    assert '"alt-game-lines": lambda: step_alt_game_lines(run_date)' in src
    assert "return step_succeeded(summary)" in src


def test_one_failed_game_does_not_fail_the_step():
    assert alt.step_succeeded({"games": 4, "failed": 1})
    assert not alt.step_succeeded({"games": 0, "failed": 3})
    assert alt.step_succeeded({"games": 0, "failed": 0, "skipped": "ALT_GAME_LINES_ENABLED=0"})
    assert alt.step_succeeded({"games": 0, "failed": 0, "skipped": "no state table"})
    assert not alt.step_succeeded({
        "games": 0, "failed": 0,
        "skipped": "ALT_GAME_LINES_MAX_GAMES='no' is not a non-negative integer; nothing bought"})


def test_a_duplicate_point_is_logged_and_kept_once():
    from loguru import logger
    rows = _rows(SPREADS) + [_rows(SPREADS)[0]]
    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        payload = alt._state_payload("NFL_2026-11-01_KC_BUF", "2026-11-01", rows)
    finally:
        logger.remove(sink)
    assert len(payload) == len(rows) - 1
    assert any("duplicate ladder point" in m for m in messages)


def test_a_started_game_loses_its_ladder_and_a_future_one_keeps_it():
    now = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
    seen = []

    class Cur:
        def fetchall(self):
            return [
                ("G1", "2026-10-29T11:00:00Z"),
                ("G1", "2026-10-29T11:00:00Z"),
                ("G2", "2099-01-01T00:00:00Z"),
                ("G3", None),
                ("G4", "not-a-time"),
            ]

    class Conn:
        def execute(self, sql, params=None):
            seen.append((sql, params))
            return Cur()

    assert alt.drop_started_ladders(Conn(), now) == 1
    assert "DELETE" in seen[-1][0] and seen[-1][1] == (["G1"],)
    assert not alt._started(None, now)
    assert not alt._started("soon", now)
    assert alt._started("2026-10-29T12:00:00Z", now)


def test_the_flag_buys_nothing(monkeypatch):
    monkeypatch.setenv("ALT_GAME_LINES_ENABLED", "0")
    called = []
    monkeypatch.setattr(alt, "_list_events", lambda *a, **k: called.append("list") or [])
    monkeypatch.setattr(alt, "_get_event_odds", lambda *a, **k: called.append("odds") or {})
    summary = alt.run(sports=("NBA",), conn=object())
    assert called == []
    assert summary["skipped"] == "ALT_GAME_LINES_ENABLED=0"
    assert summary["games"] == 0
    assert alt.step_succeeded(summary)
    assert alt.plan(object(), ("NBA",)) == {"NBA": []}


def test_a_bad_cap_buys_nothing_and_fails_the_step(monkeypatch):
    monkeypatch.setenv("ALT_GAME_LINES_MAX_GAMES", "no")
    called = []
    monkeypatch.setattr(alt, "_list_events", lambda *a, **k: called.append("list") or [])
    summary = alt.run(sports=("NBA",), conn=object())
    assert called == []
    assert str(summary["skipped"]).startswith("ALT_GAME_LINES_MAX_GAMES")
    assert not alt.step_succeeded(summary)


class _RunConn:
    def execute(self, sql, params=None):
        class Cur:
            def fetchall(self):
                return []
            def fetchone(self):
                return None
        return Cur()

    def commit(self):
        return None

    def rollback(self):
        return None


def _patch_run(monkeypatch, match):
    monkeypatch.setattr(alt, "ensure_ledger", lambda conn: None)
    monkeypatch.setattr(alt, "_state_table_exists", lambda conn: True)
    monkeypatch.setattr(alt, "drop_started_ladders", lambda conn, now: 0)
    monkeypatch.setattr(alt, "_list_events", lambda sport_key: [{"id": "e"}])
    monkeypatch.setattr(alt, "_match", match)
    monkeypatch.setattr(alt.odds_quota, "latest", lambda: None)
    monkeypatch.setattr(alt.time, "sleep", lambda *_: None)


def test_the_cap_stops_after_one_game_and_does_not_list_the_next_sport(monkeypatch):
    monkeypatch.setenv("ALT_GAME_LINES_MAX_GAMES", "1")
    monkeypatch.delenv("ALT_GAME_LINES_ENABLED", raising=False)
    listed, fetched = [], []

    def match(conn, sport, events, now):
        return [("G1", "e1", "Home", "2099-01-01"), ("G2", "e2", "Home", "2099-01-01")]

    _patch_run(monkeypatch, match)
    monkeypatch.setattr(alt, "_list_events", lambda sport_key: listed.append(sport_key) or [{"id": "e"}])

    def get_event(sport_key, event_id, markets):
        fetched.append(event_id)
        return {"bookmakers": []}

    monkeypatch.setattr(alt, "_get_event_odds", get_event)
    summary = alt.run(sports=("NBA", "NHL"), conn=_RunConn())
    assert fetched == ["e1"]
    assert len(listed) == 1
    assert summary["capped"] == 1
    assert summary["capped_sports"] == 1
    assert summary["games"] == 1
    assert "skipped" not in summary


def test_unset_cap_buys_every_game_in_the_window(monkeypatch):
    monkeypatch.delenv("ALT_GAME_LINES_MAX_GAMES", raising=False)
    monkeypatch.delenv("ALT_GAME_LINES_ENABLED", raising=False)
    fetched = []

    def match(conn, sport, events, now):
        return [("G1", "e1", "Home", "2099-01-01"), ("G2", "e2", "Home", "2099-01-01")]

    _patch_run(monkeypatch, match)
    monkeypatch.setattr(alt, "_get_event_odds", lambda sport_key, event_id, markets: fetched.append(event_id) or {"bookmakers": []})
    summary = alt.run(sports=("NBA",), conn=_RunConn())
    assert fetched == ["e1", "e2"]
    assert summary["games"] == 2
    assert summary["capped"] == 0


def test_every_all_books_read_names_a_main_market():
    """#1083 put MAIN_GAME_ODDS_MARKETS on the board reads. #1084's daily
    insert still lands one alternate rung per book in latest_odds, so a new
    unfiltered read of the view would page that rung onto a board."""
    text = (ROOT / "mobile" / "src" / "lib" / "queries.ts").read_text(encoding="utf-8")
    needle = ".from('v_latest_odds_all_books')"
    start = 0
    found = 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            break
        found += 1
        window = text[i:i + 1200]
        nxt = window.find(".from('", len(needle))
        block = window if nxt < 0 else window[:nxt]
        assert ".in('market'" in block or ".eq('market'" in block, block[:240]
        assert "alternate_spreads" not in block and "alternate_totals" not in block
        start = i + len(needle)
    assert found >= 9
    fn = text[text.index("export async function fetchGameLineRows"):]
    fn = fn[:fn.index("\nexport ")]
    assert "pregameLadderVisible" in fn
    assert fn.index("pregameLadderVisible") < fn.index(".from('alt_game_lines')")


# ── scratch Postgres ─────────────────────────────────────────────────────────

def _scratch():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    try:
        dsn = cluster.start()
    except Exception as exc:
        cluster.stop()
        pytest.skip(f"scratch cluster did not start: {exc}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return cluster, conn


SCHEMA = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END $$;
CREATE TABLE games (game_id text primary key, sport text, game_date text);
INSERT INTO games VALUES ('NFL_2026-11-01_KC_BUF', 'NFL', '2026-11-01');
"""


class _Conn:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=None):
        cur = self.raw.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, rows):
        cur = self.raw.cursor()
        cur.executemany(sql, rows)
        return cur

    def commit(self):
        pass        # autocommit

    def rollback(self):
        pass


@pytest.fixture(scope="module")
def db():
    cluster, conn = _scratch()
    try:
        cur = conn.cursor()
        cur.execute(SCHEMA)
        cur.execute(MIGRATION)
        yield conn
    finally:
        conn.close()
        cluster.stop()


def _rows(spreads):
    body = {"bookmakers": [{"key": "draftkings", "markets": [spreads, TOTALS]}]}
    return alt.event_rows(body, "NFL_2026-11-01_KC_BUF", "NFL", "Buffalo Bills",
                          datetime(2026, 10, 29, 11, tzinfo=timezone.utc))


def test_a_refetch_replaces_the_games_ladder(db):
    c = _Conn(db)
    alt._replace_state(c, "NFL_2026-11-01_KC_BUF", "2026-11-01", _rows(SPREADS))
    one_rung = {**SPREADS, "outcomes": SPREADS["outcomes"][:2]}
    alt._replace_state(c, "NFL_2026-11-01_KC_BUF", "2026-11-01", _rows(one_rung))
    cur = db.cursor()
    cur.execute("SELECT market, point, spread_home, total_line, game_date FROM alt_game_lines "
                "ORDER BY market, point")
    assert cur.fetchall() == [("alternate_spreads", -3.5, -3.5, None, "2026-11-01"),
                              ("alternate_totals", 47.5, None, 47.5, "2026-11-01")]


def test_anon_can_read_the_ladder_and_cannot_write_it(db):
    cur = db.cursor()
    cur.execute("SET ROLE anon")
    try:
        cur.execute("SELECT count(*) FROM alt_game_lines")
        assert cur.fetchone()[0] == 2
        with pytest.raises(Exception):
            cur.execute("DELETE FROM alt_game_lines")
    finally:
        db.rollback() if not db.autocommit else None
        cur.execute("RESET ROLE")


def test_a_second_pass_of_the_migration_is_a_no_op(db):
    cur = db.cursor()
    cur.execute("SELECT count(*) FROM alt_game_lines")
    before = cur.fetchone()[0]
    cur.execute(MIGRATION)
    cur.execute("SELECT count(*) FROM alt_game_lines")
    assert cur.fetchone()[0] == before
    cur.execute("SELECT count(*) FROM pg_policies WHERE tablename = 'alt_game_lines'")
    assert cur.fetchone()[0] == 1


def test_the_refresh_pass_replaces_the_ladder_and_ledgers_its_credits(db):
    """store_pass_ladders on a transactional connection, the shape the odds
    pass hands it: the ladder for the bought game is replaced, the pass is
    ledgered with the measured credits, and nothing commits until the pass
    does."""
    import psycopg2
    # The ledger first, on the autocommit connection. On this sandbox's
    # Postgres 16, ddl_guard's first catalog query (PG17's MAINTAIN) fails and
    # rolls the connection back, which on a transactional connection would
    # undo the CREATE before lock_down runs; production is Postgres 17.
    alt.ensure_ledger(_Conn(db))
    dsn = db.get_dsn_parameters()
    raw = psycopg2.connect(host=dsn.get("host"), port=dsn.get("port"),
                           user=dsn.get("user"), dbname=dsn.get("dbname"))
    try:
        class _TxConn(_Conn):
            def commit(self):
                self.raw.commit()

            def rollback(self):
                self.raw.rollback()

        c = _TxConn(raw)
        rows = [dict(r, source=None) for r in _rows(SPREADS)]
        out = alt.store_pass_ladders(c, "NFL", rows, {"calls": 1, "credits": 2.0},
                                     datetime(2026, 10, 30, 12, tzinfo=timezone.utc))
        raw.commit()
        assert out == {"games": 1, "rows": len(rows)}
        cur = raw.cursor()
        cur.execute("SELECT count(*) FROM alt_game_lines WHERE game_id = 'NFL_2026-11-01_KC_BUF'")
        assert cur.fetchone()[0] == len(rows)
        cur.execute("SELECT endpoint, credits_last, rows_stored FROM alt_game_line_fetches "
                    "WHERE endpoint = 'pass'")
        assert cur.fetchall() == [("pass", 2.0, len(rows))]
    finally:
        raw.close()


def test_a_failed_refresh_still_ledgers_the_spend(db, monkeypatch):
    """Review of #1093, M1: the ladder refresh fails, the ladder rows roll
    back, and the pass's credits are still ledgered, as ok = False."""
    import psycopg2
    alt.ensure_ledger(_Conn(db))
    dsn = db.get_dsn_parameters()
    raw = psycopg2.connect(host=dsn.get("host"), port=dsn.get("port"),
                           user=dsn.get("user"), dbname=dsn.get("dbname"))
    try:
        class _TxConn(_Conn):
            def commit(self):
                self.raw.commit()

            def rollback(self):
                self.raw.rollback()

        def broken(*a, **k):
            raise RuntimeError("disk full")
        monkeypatch.setattr(alt, "_replace_state", broken)
        rows = [dict(r, source=None) for r in _rows(SPREADS)]
        out = alt.store_pass_ladders(_TxConn(raw), "NFL", rows, {"calls": 1, "credits": 2.0},
                                     datetime(2026, 10, 30, 13, tzinfo=timezone.utc))
        raw.commit()
        assert out == {"games": 0, "rows": 0}
        cur = raw.cursor()
        cur.execute("SELECT ok, credits_last, detail FROM alt_game_line_fetches "
                    "WHERE endpoint = 'pass' AND requested_at = '2026-10-30T13:00:00Z'")
        ok, credits, detail = cur.fetchone()
        assert ok is False and credits == 2.0 and "disk full" in detail
    finally:
        raw.close()

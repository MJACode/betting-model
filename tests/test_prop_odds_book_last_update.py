"""Every prop odds row carries the book's own clock (2026-10-16).

`snapshot_at` is OUR fetch time and is the same for every book in a fetch, so
it cannot tell a book that re-priced a minute ago from one that has not moved
in an hour. The NBA prop rule refuses a soft quote whose clock is more than 10
minutes behind Pinnacle's; it needs the clock stored. The writer is shared by
every sport's prop pull, so the column is added once, guarded, and read with
.get() so a caller that builds rows without it still inserts.
"""
from __future__ import annotations

import data.ingestors.prop_odds_ingestor as ing

MARKETS = [
    {"key": "player_points", "last_update": "2026-10-21T23:41:00Z", "outcomes": [
        {"name": "Over", "description": "Stephen Curry", "price": -120, "point": 24.5},
        {"name": "Under", "description": "Stephen Curry", "price": +100, "point": 24.5}]},
    {"key": "player_rebounds", "outcomes": [
        {"name": "Over", "description": "Stephen Curry", "price": -110, "point": 5.5},
        {"name": "Under", "description": "Stephen Curry", "price": -110, "point": 5.5}]},
]


def _parse(**kw):
    return ing._parse_prop_markets(MARKETS, "NBA_2026-10-21_GSW_LAL", "2026-10-21", "open",
                                   "2026-10-21T23:43:00+00:00",
                                   allowed_markets={"player_points", "player_rebounds"},
                                   bookmaker="fanduel", **kw)


def test_the_markets_own_clock_is_stored_else_the_books():
    rows = {r["market"]: r for r in _parse(book_last_update="2026-10-21T23:30:00Z")}
    assert rows["player_points"]["book_last_update"] == "2026-10-21T23:41:00Z"
    assert rows["player_rebounds"]["book_last_update"] == "2026-10-21T23:30:00Z"


def test_no_clock_anywhere_is_none_not_our_fetch_time():
    rows = {r["market"]: r for r in _parse()}
    assert rows["player_rebounds"]["book_last_update"] is None


class _Conn:
    def __init__(self, has_column):
        self.has_column, self.sql, self.rows = has_column, [], []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.sql.append(s)
        self._one = None
        if "FROM pg_class" in s:
            # relrowsecurity, columns, indexes, privileged roles
            cols = ["prop_id", "game_id"] + (["book_last_update"] if self.has_column else [])
            self._one = (False, cols, [], 0)
        return self

    def fetchone(self):
        return self._one

    def executemany(self, sql, rows):
        self.sql.append(" ".join(sql.split()))
        self.rows.extend(rows)


def test_the_column_is_added_only_when_the_catalog_lacks_it(monkeypatch):
    monkeypatch.setattr(ing, "_book_last_update_ready", False)
    have = _Conn(has_column=True)
    ing._insert_prop_odds(have, _parse())
    assert not any("ALTER TABLE" in s for s in have.sql)

    monkeypatch.setattr(ing, "_book_last_update_ready", False)
    lack = _Conn(has_column=False)
    ing._insert_prop_odds(lack, _parse())
    alters = [i for i, s in enumerate(lack.sql) if "ALTER TABLE player_prop_odds" in s]
    assert len(alters) == 1 and "ADD COLUMN IF NOT EXISTS book_last_update TEXT" in lack.sql[alters[0]]
    assert "lock_timeout" in lack.sql[alters[0] - 1]          # bounded wait
    insert = next(i for i, s in enumerate(lack.sql) if s.startswith("INSERT INTO player_prop_odds"))
    assert alters[0] < insert

    # Once known, never asked again in this process.
    again = _Conn(has_column=False)
    ing._insert_prop_odds(again, _parse())
    assert not any("pg_class" in s or "ALTER" in s for s in again.sql)


def test_a_row_built_without_the_key_still_inserts_as_null(monkeypatch):
    monkeypatch.setattr(ing, "_book_last_update_ready", True)
    conn = _Conn(has_column=True)
    row = {k: v for k, v in _parse()[0].items() if k != "book_last_update"}
    ing._insert_prop_odds(conn, [row])
    assert conn.rows[0]["book_last_update"] is None
    assert "book_last_update" in conn.sql[-1]

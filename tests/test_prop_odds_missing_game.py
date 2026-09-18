"""One unknown games row must not roll back the rest of a prop-odds pass.

Hourly 2026-09-18 07:17Z: Odds API listed SEA @ COL, the ingestor minted
MLB_2026-09-18_SEA_COL, and INSERT into player_prop_odds hit
player_prop_odds_game_id_fkey. Inserts share one transaction and only
commit at the end, so that one orphan aborted every MLB prop row from the
pass. Same constraint, same shape, 2026-09-08 TEX_SEA / 2026-09-09 TOR_OAK
/ 2026-09-13 CWS_STL.

The harden: skip (and warn) events whose game_id is not in `games` BEFORE
the paid per-event call; commit the events that do insert; a leftover FK
must not take the others down.
"""
from __future__ import annotations

import data.ingestors.prop_odds_ingestor as ing
from psycopg2 import IntegrityError


DATE = "2026-09-18"
ORPHAN_ID = "MLB_2026-09-18_SEA_COL"   # the production DETAIL key
BOS_NYY = "MLB_2026-09-18_BOS_NYY"
LAD_SF = "MLB_2026-09-18_LAD_SF"

_PROPS = [("draftkings", [{
    "key": "batter_hits",
    "outcomes": [
        {"name": "Over", "description": "Judge", "price": -110, "point": 1.5},
        {"name": "Under", "description": "Judge", "price": -110, "point": 1.5},
    ],
}])]


def _event(eid: str, away_name: str, home_name: str) -> dict:
    return {
        "id": eid,
        "home_team": home_name,
        "away_team": away_name,
        "commence_time": "2026-09-19T00:11:00Z",
        "game_date": DATE,
    }


EVENTS = [
    _event("ev-bos", "Boston Red Sox", "New York Yankees"),
    _event("ev-sea", "Seattle Mariners", "Colorado Rockies"),  # orphan
    _event("ev-lad", "Los Angeles Dodgers", "San Francisco Giants"),
]


class _R:
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._one


class FakeConn:
    """games lookup + player_prop_odds insert, with optional FK on one id."""

    def __init__(self, known, reject_insert=None):
        self.known = set(known)
        self.reject_insert = set(reject_insert or [])
        self.pending: list[dict] = []
        self.committed: list[dict] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if "FROM games" in text and "game_id" in text:
            ids = list(params[0]) if params else []
            return _R(rows=[(i,) for i in ids if i in self.known])
        return _R()

    def executemany(self, sql, rows):
        for row in rows:
            gid = row["game_id"]
            if gid in self.reject_insert or gid not in self.known:
                raise IntegrityError(
                    'insert or update on table "player_prop_odds" violates '
                    'foreign key constraint "player_prop_odds_game_id_fkey"\n'
                    f'DETAIL:  Key (game_id)=({gid}) is not present in table '
                    '"games".\n'
                )
            self.pending.append(row)

    def commit(self):
        self.commits += 1
        self.committed.extend(self.pending)
        self.pending = []

    def rollback(self):
        self.rollbacks += 1
        self.pending = []

    def close(self):
        pass


def _run(monkeypatch, conn, events=EVENTS):
    fetched: list[str] = []

    def fake_props(event_id, markets, sport_key=None):
        fetched.append(event_id)
        return _PROPS

    monkeypatch.setattr(ing, "get_connection", lambda: conn)
    monkeypatch.setattr(ing, "persist_quota", lambda c: None)
    monkeypatch.setattr(ing, "alt_markets_due", lambda *a, **k: False)
    monkeypatch.setattr(ing, "_get_events", lambda *a, **k: events)
    monkeypatch.setattr(ing, "_get_event_props", fake_props)
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)
    result = ing.run_prop_odds_ingestor(
        target_date=DATE, snapshot_type="open", sport="MLB", days_ahead=0,
    )
    return result, fetched


def test_event_with_no_games_row_is_skipped_and_others_still_insert(monkeypatch):
    """THE PRODUCTION FAILURE. SEA @ COL is not in games; BOS @ NYY and
    LAD @ SF are. The orphan is warned and skipped; the other two insert;
    the pass does not raise; the paid event call is not spent on the orphan.
    """
    warnings: list[str] = []
    sink = ing.logger.add(
        lambda m: warnings.append(m.record["message"]), level="WARNING")
    conn = FakeConn(known={BOS_NYY, LAD_SF})
    try:
        result, fetched = _run(monkeypatch, conn)
    finally:
        ing.logger.remove(sink)

    assert result["events"] == 2
    assert result["prop_rows"] == 2
    inserted = {r["game_id"] for r in conn.committed}
    assert inserted == {BOS_NYY, LAD_SF}
    assert ORPHAN_ID not in inserted
    assert fetched == ["ev-bos", "ev-lad"], fetched
    joined = "\n".join(warnings)
    assert ORPHAN_ID in joined
    assert "Seattle Mariners @ Colorado Rockies" in joined
    assert DATE in joined
    assert "skipping rather than failing the sport pass" in joined


def test_fk_on_insert_does_not_unwrite_the_events_that_already_landed(monkeypatch):
    """Backstop for the actual abort: the INSERT raises the production
    IntegrityError after the pre-check treated the id as known. Earlier
    events stay committed; later events still insert; the pass does not raise.
    """
    conn = FakeConn(
        known={BOS_NYY, ORPHAN_ID, LAD_SF},
        reject_insert={ORPHAN_ID},
    )
    result, fetched = _run(monkeypatch, conn)
    assert fetched == ["ev-bos", "ev-sea", "ev-lad"]
    assert result["events"] == 2
    inserted = {r["game_id"] for r in conn.committed}
    assert inserted == {BOS_NYY, LAD_SF}
    assert conn.rollbacks >= 1


def test_is_missing_game_fk_matches_the_production_error():
    exc = IntegrityError(
        'insert or update on table "player_prop_odds" violates foreign key '
        'constraint "player_prop_odds_game_id_fkey"\n'
        'DETAIL:  Key (game_id)=(MLB_2026-09-18_SEA_COL) is not present in '
        'table "games".\n'
    )
    assert ing._is_missing_game_fk(exc)
    assert not ing._is_missing_game_fk(RuntimeError("network dropped"))
    assert not ing._is_missing_game_fk(IntegrityError("duplicate key"))

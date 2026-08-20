"""
Tests for the NFL DK line-snapshot path (session 121):
nfl/data_ingest/line_snapshots.dk_line_rows (pure, pandas-free) and the
platform publisher's snapshot_row_params + publish_line_snapshots.
"""

import csv as _csv
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
# The nfl/ package root — data_ingest is unique to it (no platform collision).
sys.path.insert(0, str(_ROOT / "nfl"))

from data_ingest.line_snapshots import dk_line_rows  # noqa: E402
from scripts.nfl_wind_publisher import (  # noqa: E402
    publish_line_snapshots,
    snapshot_row_params,
)


SCHED = [
    {"game_id": "2026_02_NYJ_MIA", "home_team": "MIA", "away_team": "NYJ",
     "kick_utc": "2026-09-20 17:00:00+00:00"},
    {"game_id": "2026_02_DAL_PHI", "home_team": "PHI", "away_team": "DAL",
     "kick_utc": "2026-09-21 00:20:00+00:00"},
]


def _rec(**over):
    rec = {
        "home": "MIA", "away": "NYJ", "book": "draftkings", "market": "totals",
        "side": "Over", "price": -110, "point": 43.5,
    }
    rec.update(over)
    return rec


class TestDkLineRows:
    def test_totals_two_sides_one_row(self):
        rows = dk_line_rows(
            [_rec(), _rec(side="Under", price=-105)],
            SCHED, "totals", "2026-09-17T13:00:00+00:00",
        )
        assert len(rows) == 1
        r = rows[0]
        assert r["game_id"] == "2026_02_NYJ_MIA"
        assert r["matchup"] == "NYJ @ MIA"
        assert r["market"] == "totals"
        assert r["total_line"] == 43.5
        assert r["over_price"] == -110 and r["under_price"] == -105
        assert r["spread_home"] is None and r["home_price"] is None
        assert r["snapshot_at"] == "2026-09-17T13:00:00+00:00"

    def test_spreads_home_relative(self):
        rows = dk_line_rows(
            [
                _rec(market="spreads", side="home", price=-108, point=-3.5),
                _rec(market="spreads", side="away", price=-112, point=3.5),
            ],
            SCHED, "spreads", "t",
        )
        assert len(rows) == 1
        r = rows[0]
        assert r["spread_home"] == -3.5          # HOME spread, the settle convention
        assert r["home_price"] == -108 and r["away_price"] == -112
        assert r["total_line"] is None

    def test_non_dk_books_ignored(self):
        rows = dk_line_rows([_rec(book="fanduel")], SCHED, "totals", "t")
        assert rows == []

    def test_unscheduled_game_ignored(self):
        rows = dk_line_rows(
            [_rec(home="SEA", away="NE")], SCHED, "totals", "t",
        )
        assert rows == []

    def test_missing_line_dropped(self):
        # A DK quote with a NaN point can't feed movement display.
        rows = dk_line_rows(
            [_rec(point=float("nan")), _rec(side="Under", point=float("nan"))],
            SCHED, "totals", "t",
        )
        assert rows == []

    def test_wrong_market_records_ignored(self):
        rows = dk_line_rows(
            [_rec(market="spreads", side="home", point=-3.5)],
            SCHED, "totals", "t",
        )
        assert rows == []


def _csv_row(**over):
    row = {
        "game_id": "2026_02_NYJ_MIA", "matchup": "NYJ @ MIA",
        "kick_utc": "2026-09-20 17:00:00+00:00", "market": "totals",
        "spread_home": "", "total_line": "43.5",
        "home_price": "", "away_price": "", "over_price": "-110",
        "under_price": "-105", "snapshot_at": "2026-09-17T13:00:00+00:00",
    }
    row.update(over)
    return row


class TestSnapshotRowParams:
    def test_happy_path(self):
        p = snapshot_row_params(_csv_row())
        assert p["game_id"] == "NFL_2026_02_NYJ_MIA"
        assert p["market"] == "totals"
        assert p["total_line"] == 43.5
        assert p["over_price"] == -110.0 and p["under_price"] == -105.0
        assert p["spread_home"] is None and p["home_price"] is None

    def test_empty_strings_become_none(self):
        p = snapshot_row_params(_csv_row(over_price="", under_price=" "))
        assert p["over_price"] is None and p["under_price"] is None

    def test_bad_market_skipped(self):
        assert snapshot_row_params(_csv_row(market="h2h")) is None

    def test_garbage_price_skipped(self):
        assert snapshot_row_params(_csv_row(over_price="abc")) is None


def _write_snapshot_csv(tmp_path, rows):
    path = tmp_path / "line_snapshots_2026-09-17.csv"
    with open(path, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow(r)


class TestPublishLineSnapshots:
    def test_inserts_guarded_rows(self, monkeypatch, tmp_path):
        import data.db as db
        from scripts import nfl_wind_publisher as pub

        executed = []

        class FakeConn:
            def execute(self, sql, params=None):
                executed.append((" ".join(sql.split()), params))
                class R:
                    def fetchone(self_r):
                        return None
                    def fetchall(self_r):
                        return []
                return R()
            def commit(self):
                executed.append(("COMMIT", None))
            def close(self):
                pass

        monkeypatch.setattr(db, "get_connection", lambda: FakeConn())
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        _write_snapshot_csv(tmp_path, [
            _csv_row(),
            _csv_row(market="spreads", spread_home="-3.5", total_line="",
                     home_price="-108", away_price="-112",
                     over_price="", under_price=""),
        ])

        n = pub.publish_line_snapshots("2026-09-17")
        assert n == 2
        inserts = [(s, p) for s, p in executed if s.startswith("INSERT INTO odds")]
        assert len(inserts) == 2
        sql, params = inserts[0]
        # Only games a card has published exist — and re-flushing must no-op.
        assert "WHERE EXISTS (SELECT 1 FROM games" in sql
        assert "AND NOT EXISTS" in sql
        assert "'draftkings'" in sql and "'open'" in sql and "'NFL'" in sql
        assert params["game_id"] == "NFL_2026_02_NYJ_MIA"
        assert executed[-1][0] == "COMMIT"

    def test_no_csv_touches_nothing(self, monkeypatch, tmp_path):
        import data.db as db
        from scripts import nfl_wind_publisher as pub
        monkeypatch.setattr(db, "get_connection",
                            lambda: (_ for _ in ()).throw(AssertionError("no DB touch")))
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        assert publish_line_snapshots("2026-09-17") == 0

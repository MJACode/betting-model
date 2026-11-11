"""The one-time recompute of picks stamped measured with an empty close.

Dry run is the default. --apply is the only write. Nothing here opens a
database.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from scripts.recompute_empty_clv import empty_close_picks, recompute_empty_clv  # noqa: E402
from tracking.clv_math import CLV_METHOD_STANDARD  # noqa: E402


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows):
        self.rows = rows
        self.statements: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), tuple(params)))
        if sql.lstrip().upper().startswith("SELECT"):
            return _Res(self.rows)
        return _Res([])


ROWS = [
    (101, "2026-11-03", "NCAAB_2026-11-03_DUKE_UNC", "ncaab_first_half_total"),
    (102, "2026-11-03", "NCAAB_2026-11-03_DUKE_UNC", "ncaab_first_half_spread"),
    (103, "2026-11-02", "NBA_2026-11-02_BOS_MIL", "nba_first_half_total_luck"),
]


def test_the_selector_requires_an_empty_standard_v2_close():
    conn = _Conn(ROWS)
    assert empty_close_picks(conn) == ROWS
    sql, params = conn.statements[0]
    assert params[0] == CLV_METHOD_STANDARD
    for col in ("closing_dk_odds", "closing_line", "clv_pct", "clv_pp",
                "line_clv_pts", "market_clv_pct", "market_clv_pp",
                "pinnacle_close_odds", "clv_close_book"):
        assert f"p.{col} IS NULL" in sql
    assert "UPDATE" not in sql


def test_date_and_sport_narrow_the_read():
    conn = _Conn(ROWS[:2])
    empty_close_picks(conn, game_date="2026-11-03", sport="ncaab")
    sql, params = conn.statements[0]
    assert "p.game_date = %s" in sql
    assert "split_part(p.game_id, '_', 1) = %s" in sql
    assert params == (CLV_METHOD_STANDARD, "2026-11-03", "NCAAB")


def test_a_dry_run_writes_nothing():
    conn = _Conn(ROWS)
    seen = []
    summary = recompute_empty_clv(conn, apply=False, capture=lambda *a: seen.append(a))
    assert summary["apply"] is False
    assert summary["count"] == 3
    assert summary["pick_ids"] == [101, 102, 103]
    assert summary["dates"] == ["2026-11-03", "2026-11-02"]
    assert seen == []
    assert all(not sql.startswith("UPDATE") for sql, _ in conn.statements)


def test_apply_clears_only_the_empty_stamp_and_recaptures_each_date():
    conn = _Conn(ROWS)
    seen = []

    def capture(conn_, day, stamp):
        seen.append((day, stamp))
        return 1

    summary = recompute_empty_clv(
        conn, apply=True, game_date="2026-11-03", sport="NCAAB",
        captured_at="TS", capture=capture)
    assert summary["captured"] == 2
    updates = [s for s in conn.statements if s[0].startswith("UPDATE")]
    assert len(updates) == 1
    sql, params = updates[0]
    assert "clv_method = NULL" in sql
    assert "p.pick_id = ANY(%s)" in sql
    assert "p.closing_dk_odds IS NULL" in sql
    assert params[0] == [101, 102, 103]
    assert params[1] == CLV_METHOD_STANDARD
    assert seen == [("2026-11-03", "TS"), ("2026-11-02", "TS")]

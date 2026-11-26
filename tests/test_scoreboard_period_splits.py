"""Action Network consensus splits per period (Matt, 2026-11-26: "Yes on splits", polled hourly).

Built on worker_jobs 1698627, which counted Action Network's 0/0 placeholder as a split. Corrected the same day:
counting only non-zero shares (worker_jobs 1717775) consensus serves no period split, and the hourly passes stored
0 period rows (data/ingestors/scoreboard_splits.py, the comment above PERIODS_BY_SPORT). These tests pin the
parser and the storage names, so a period split is stored correctly on the day one is served.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from data.ingestors import scoreboard_splits as ss
from tests._node import NODE, node_strips_types
from tests.test_scoreboard_splits import BEFORE, CAR_GB, GAMES, _Conn, _game

ROOT = Path(__file__).resolve().parents[1]
MIG = "scoreboard_splits_period_markets_2026_11_26.sql"
# 14:17 ET on BEFORE's day: inside the hourly window. 14:05 ET: outside.
IN_WINDOW = datetime(2026, 10, 29, 18, 17, tzinfo=timezone.utc)
OUT_WINDOW = datetime(2026, 10, 29, 18, 5, tzinfo=timezone.utc)


def _period_game(period: str) -> dict:
    g = copy.deepcopy(_game(CAR_GB))
    block = g["markets"]["15"]
    g["markets"]["15"] = {period: block.pop("event")}
    return g


def test_period_rows_carry_the_odds_tables_period_names():
    rows = ss.build_rows("NFL", {"games": [_period_game("firstquarter")]}, GAMES, BEFORE, None, "firstquarter")
    assert rows and {r["market"] for r in rows} <= {"h2h_q1", "spreads_q1", "totals_q1"}
    full = ss.build_rows("NFL", {"games": [_game(CAR_GB)]}, GAMES, BEFORE)
    # Same numbers, period name added; the full-game block is not read as a period.
    assert sorted((r["market"].rsplit("_q1", 1)[0], r["side"], r["bet_pct"]) for r in rows) == \
        sorted((r["market"], r["side"], r["bet_pct"]) for r in full)
    assert ss.build_rows("NFL", {"games": [_game(CAR_GB)]}, GAMES, BEFORE, None, "firstquarter") == []


def test_every_period_suffix_matches_the_history_check():
    sql = (ROOT / "data" / "migrations" / MIG).read_text(encoding="utf-8")
    pat = re.search(r"CHECK \(market ~ '([^']+)'\)", sql).group(1)
    for periods in ss.PERIODS_BY_SPORT.values():
        for p in periods:
            for base in ("h2h", "spreads", "totals"):
                assert re.search(pat, f"{base}_{ss.PERIOD_SUFFIX[p]}"), (base, p)
    for bad in ("team_totals_home", "spreads_q1_alternate", "totals_q5"):
        assert not re.search(pat, bad)


class _PeriodConn(_Conn):
    def __init__(self, storable=True):
        super().__init__()
        self.storable = storable

    def execute(self, sql, params=None):
        if "pg_constraint" in sql:
            return type(super().execute("SELECT to_regclass('x')"))([(self.storable,)])
        return super().execute(sql, params)


def _run(now, monkeypatch, storable=True):
    calls = []

    def fetch(sport, day):
        calls.append((sport, day, "event"))
        return {"games": [_game(CAR_GB)]}

    def fetch_period(sport, day, period):
        calls.append((sport, day, period))
        return {"games": [_period_game(period)]}

    monkeypatch.setattr(ss.time, "sleep", lambda s: None)
    conn = _PeriodConn(storable)
    out = ss.run(conn, now=now, fetch=fetch, fetch_period=fetch_period)
    return calls, conn, out


def test_periods_are_fetched_on_the_hourly_window_only(monkeypatch):
    # The mechanism, on the NFL fixture; which sports are asked is pinned below.
    monkeypatch.setitem(ss.PERIODS_BY_SPORT, "NFL", ("firsthalf", "firstquarter"))
    calls, conn, out = _run(IN_WINDOW, monkeypatch)
    assert [c[2] for c in calls] == ["event", *ss.PERIODS_BY_SPORT["NFL"]]
    assert {r["market"] for r in conn.rows} >= {"spreads", "totals_q1", "spreads_h1"}
    assert ss.PERIODS_BY_SPORT["NFL"] == ("firsthalf", "firstquarter")
    calls, _, _ = _run(OUT_WINDOW, monkeypatch)
    assert [c[2] for c in calls] == ["event"]


def test_no_period_is_fetched_until_the_check_allows_it(monkeypatch):
    monkeypatch.setitem(ss.PERIODS_BY_SPORT, "NFL", ("firstquarter",))
    calls, conn, _ = _run(IN_WINDOW, monkeypatch, storable=False)
    assert [c[2] for c in calls] == ["event"]
    assert {r["market"] for r in conn.rows} <= {"h2h", "spreads", "totals"}


def test_a_caller_with_its_own_fetch_gets_no_periods(monkeypatch):
    monkeypatch.setattr(ss.time, "sleep", lambda s: None)
    seen = []
    ss.run(_Conn(), now=IN_WINDOW, fetch=lambda s, d: seen.append(s) or {"games": [_game(CAR_GB)]})
    assert seen == ["NFL"]


def test_migration_guard_is_the_named_constraint():
    sql = (ROOT / "data" / "migrations" / MIG).read_text(encoding="utf-8")
    assert sql.index("RETURN;") < sql.index("ALTER TABLE")
    assert "pg_get_constraintdef" not in sql
    assert "conname = 'scoreboard_splits_history_market_period_check'" in sql
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index("scoreboard_splits_dk_history_2026_11_16.sql") < ACTIVE_MIGRATIONS.index(MIG)


def test_ncaab_is_polled():
    assert "NCAAB" in ss.SPORTS


def test_only_sports_not_measured_empty_are_asked_for_periods(monkeypatch):
    """splits-nonzero-probe-2026-11-26: no non-zero consensus period split for NFL, NCAAF or NCAAB
    (Matt, "Ok"). NBA and NHL stay until the 11-27 probe measures them."""
    assert set(ss.PERIODS_BY_SPORT) == {"NBA", "NHL"}
    calls, _, _ = _run(IN_WINDOW, monkeypatch)
    assert [c[2] for c in calls] == ["event"]          # the NFL fixture: full game only


def test_mcp_labels_period_splits():
    if not node_strips_types():
        import pytest
        pytest.skip("node >= 22.6 not available")
    src = (ROOT / "supabase" / "functions" / "mcp" / "index.ts").read_text(encoding="utf-8")
    start = src.index("const SPLIT_KINDS")
    body = src[start:src.index("// The game behind a game id")]
    script = body + "\nconsole.log(JSON.stringify(['h2h','spreads_q1','totals_h1','h2h_p1','totals_h2','core_x']" \
                    ".map(splitsKey)));\n"
    out = subprocess.run([NODE, "--experimental-strip-types", "--no-warnings", "--input-type=module-typescript"],
                         input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["moneyline", "1Q spread", "1H total", "1P moneyline", "2H total", "core_x"]

"""injury_status_current: the one-row-per-player table the Stats board reads.

Matt, 2026-10-23: Romeo Doubs ranked #3 on NFL Anytime TD while on Injured
Reserve. The ingestor now keeps a current-status table beside its log; these
pin what it folds, what it drops, and when a pull may clear a team.
"""
from __future__ import annotations

import io
import os
import subprocess

import pytest

from data.anon_readable import ANON_READABLE
from data.ingestors import injury_ingestor as ing
from data.view_migrations import ACTIVE_MIGRATIONS
from tests._node import tsx_cmd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOBILE = os.path.join(ROOT, "mobile")
MIGRATION = "add_injury_status_current_2026_10_23.sql"


def _row(**kw):
    base = dict(sport="NFL", team="NE", player_name="Romeo Doubs", player_id="1",
                status="Out", injury_type="Injured Reserve", scenario="A",
                status_ts="2026-10-19T23:53Z")
    base.update(kw)
    return base


class FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append(("execute", " ".join(sql.split()), params))

    def executemany(self, sql, rows):
        self.calls.append(("executemany", " ".join(sql.split()), list(rows)))


def test_doubs_folds_to_one_ir_row():
    rows = ing.current_status_rows([_row()])
    assert rows == [{
        "sport": "NFL", "team": "NE", "player_key": "romeo doubs",
        "player_name": "Romeo Doubs", "player_id": "1", "status": "Out",
        "injury_type": "Injured Reserve", "status_ts": "2026-10-19T23:53Z",
    }]


def test_returning_and_active_never_reach_the_app():
    rows = ing.current_status_rows([
        _row(player_name="Back Again", scenario="B", status="Returning"),
        # A ramp row is never an absence, whatever status it carries.
        _row(player_name="Ramp Row", scenario="B", status="Out"),
        _row(player_name="Cleared Guy", status="Active"),
        _row(player_name="No Team", team=None),
    ])
    assert rows == []


def test_a_player_listed_twice_keeps_the_worse_status():
    rows = ing.current_status_rows([
        _row(sport="MLB", team="NYY", player_name="Gerrit Cole", status="Day-To-Day"),
        _row(sport="MLB", team="NYY", player_name="Gerrit Cole", status="IL60"),
        _row(sport="MLB", team="NYY", player_name="Gerrit Cole", status="IL15"),
    ])
    assert [r["status"] for r in rows] == ["IL60"]


def test_the_key_is_the_apps_name_fold():
    rows = ing.current_status_rows([_row(player_name="Odell Beckham Jr.")])
    assert rows[0]["player_key"] == "odell beckham"


def test_a_healthy_pull_replaces_the_whole_sport():
    rows = [_row(team=f"T{i}", player_name=f"P {i}") for i in range(20)]
    conn = FakeConn()
    n = ing._replace_current_status(conn, "NFL", rows, teams_expected=32)
    assert n == 20
    kind, sql, params = conn.calls[0]
    assert sql == "DELETE FROM injury_status_current WHERE sport = %s" and params == ("NFL",)
    assert conn.calls[1][0] == "executemany" and len(conn.calls[1][2]) == 20


def test_a_degraded_pull_only_replaces_the_teams_that_answered():
    rows = [_row(team="NE"), _row(team="BUF", player_name="Josh Allen")]
    conn = FakeConn()
    ing._replace_current_status(conn, "NFL", rows, teams_expected=32)
    kind, sql, params = conn.calls[0]
    assert "team = ANY(%s)" in sql
    assert params == ("NFL", ["BUF", "NE"])


def test_an_empty_pull_writes_nothing():
    conn = FakeConn()
    assert ing._replace_current_status(conn, "NFL", [], teams_expected=32) == 0
    assert conn.calls == []


def test_the_table_is_migrated_and_readable_by_the_app():
    assert MIGRATION in ACTIVE_MIGRATIONS
    assert "injury_status_current" in ANON_READABLE
    sql = io.open(os.path.join(ROOT, "data", "migrations", MIGRATION), encoding="utf-8").read()
    assert "to_regclass('public.injury_status_current') IS NULL" in sql
    assert "REVOKE ALL ON public.injury_status_current FROM anon, authenticated" in sql
    assert "FOR SELECT TO anon, authenticated USING (true)" in sql


def test_a_current_status_failure_cannot_cost_the_log():
    """The log commits first; the current table writes in its own try after."""
    src = io.open(ing.__file__, encoding="utf-8").read()
    body = src[src.index("def run_injury_ingestor"):]
    assert body.index("conn.commit()") < body.index("_replace_current_status(")
    assert "injury_status_current not updated" in body


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_board_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_injury_status.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

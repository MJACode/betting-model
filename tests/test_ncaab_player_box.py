"""Men's college basketball player box scores (data/ingestors/ncaab_player_box.py)
and the Stats-tab SQL behind them (add_ncaab_player_game_log_2026_11_03.sql).

The ESPN payload here is the stored team-box fixture (summary_401825519.json:
Rutgers 68, Maryland 57) with a `boxscore.players` block added in the shape the
NBA summary fixture carries (tests/fixtures/espn_nba_summary_401811026.json:
labels MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK, OREB, DREB, PF, +/-).
The college fixtures were trimmed to team rows, so that shape is ESPN's NBA
one; the first backfill run on the worker is what measures the college one,
and a summary that differs is refused and counted, never stored wrong.

The Postgres half runs against LATEST_LINE_TEST_DSN or a scratch cluster and
SKIPS where neither exists.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data.ingestors import ncaab_espn_box as box
from data.ingestors import ncaab_player_box as pbox

ROOT = Path(__file__).parent.parent
FIX = Path(__file__).parent / "fixtures" / "ncaab_espn_box"
SUMMARY = json.loads((FIX / "summary_401825519.json").read_text(encoding="utf-8"))
MIGRATION = (ROOT / "data" / "migrations" / pbox.MIGRATION).read_text(encoding="utf-8")
GAME_ID = "NCAAB_2026-02-15_maryland_rutgers"
NOW = datetime(2026, 2, 16, 15, 0, tzinfo=timezone.utc)

LABELS = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB",
          "PF", "+/-"]


def _ath(pid, name, mins, pts, fg="0-0", tp="0-0", ft="0-0", reb=0, ast=0, starter=False,
         dnp=False):
    stats = [] if dnp else [str(mins), str(pts), fg, tp, ft, str(reb), str(ast), "1", "0", "0",
                            "0", str(reb), "2", "+0"]
    return {"athlete": {"id": pid, "displayName": name, "position": {"abbreviation": "G"}},
            "starter": starter, "didNotPlay": dnp, "reason": "COACH'S DECISION", "stats": stats}


def _team(tid, athletes):
    return {"team": {"id": str(tid)}, "statistics": [{"labels": LABELS, "athletes": athletes}]}


def summary(home_pts=(30, 20, 18), away_pts=(40, 17)):
    js = copy.deepcopy(SUMMARY)
    home = [_ath(f"h{i}", f"Home {i}", 30, p, starter=i < 2) for i, p in enumerate(home_pts)]
    home.append(_ath("hdnp", "Home Bench", 0, 0, dnp=True))
    # Benched with MIN '--' and every count zero: the NBA parser's no-minutes rule.
    home.append({"athlete": {"id": "hnm", "displayName": "Home NoMin"}, "starter": False,
                 "didNotPlay": False,
                 "stats": ["--", "0", "0-0", "0-0", "0-0", "0", "0", "0", "0", "0", "0", "0",
                           "0", "+0"]})
    away = [_ath(f"a{i}", f"Away {i}", 30, p, fg="10-20", tp="2-5", ft="4-6", reb=7, ast=3)
            for i, p in enumerate(away_pts)]
    js["boxscore"]["players"] = [_team(164, home), _team(120, away)]
    return js


GAME = {"espn_event_id": 401825519, "game_id": GAME_ID, "season": 2026,
        "game_date": "2026-02-15", "commence_time": "2026-02-15T17:00:00Z",
        "home_espn_id": 164, "away_espn_id": 120, "home_team": "Rutgers",
        "away_team": "Maryland", "home_score": 68, "away_score": 57, "went_to_ot": 0}


# ── parsing ──────────────────────────────────────────────────────────────────

def test_players_who_played_are_read_by_label():
    by_team = pbox.parse_players(summary())
    assert sorted(by_team) == [120, 164]
    assert [p["player_id"] for p in by_team[164]] == ["h0", "h1", "h2"]   # DNP + no-minutes out
    a0 = by_team[120][0]
    assert (a0["points"], a0["fg_made"], a0["fg_att"], a0["fg3_made"], a0["fg3_att"],
            a0["ft_made"], a0["ft_att"], a0["rebounds"], a0["assists"], a0["minutes"],
            a0["fouls"], a0["position"]) == (40, 10, 20, 2, 5, 4, 6, 7, 3, 30.0, 2, "G")
    assert by_team[164][0]["is_starter"] == 1 and by_team[164][2]["is_starter"] == 0


def test_rows_carry_the_stored_school_names_and_season():
    rows = [dict(zip(pbox.COLS, r)) for r in pbox.player_rows(GAME, summary())]
    assert len(rows) == 5
    assert {r["team"] for r in rows if r["team_espn_id"] == 164} == {"Rutgers"}
    assert {r["team"] for r in rows if r["team_espn_id"] == 120} == {"Maryland"}
    assert {(r["game_id"], r["season"], r["game_date"], r["source"]) for r in rows} == {
        (GAME_ID, 2026, "2026-02-15", "espn_summary")}


def test_points_that_do_not_add_to_the_final_are_refused():
    with pytest.raises(pbox.Refused, match="players score 67, final 68"):
        pbox.player_rows(GAME, summary(home_pts=(30, 20, 17)))


def test_a_box_for_other_teams_is_refused():
    js = summary()
    js["boxscore"]["players"][1]["team"]["id"] = "999"
    with pytest.raises(pbox.Refused, match="stored pair"):
        pbox.player_rows(GAME, js)


def test_a_summary_for_another_event_is_refused():
    with pytest.raises(pbox.Refused, match="401825519, not 1"):
        pbox.player_rows(dict(GAME, espn_event_id=1), summary())


def test_a_summary_with_no_player_block_is_refused_not_raised():
    """The team-box fixtures carry no players. store_from_summary records it
    and returns; the team box that called it is already committed."""
    class Conn:
        def __init__(self):
            self.sql = []

        def execute(self, sql, params=None):
            self.sql.append(sql)

    import data.ingestors.ncaab_player_box as m
    c = Conn()
    orig = m.call_in_savepoint
    m.call_in_savepoint = lambda conn, name, fn: fn()
    try:
        n, reason = pbox.store_from_summary(c, GAME, copy.deepcopy(SUMMARY), NOW)
    finally:
        m.call_in_savepoint = orig
    assert n == 0 and "stored pair" in reason
    assert any(pbox.MISSES_TABLE in s for s in c.sql)
    assert not any(s.startswith("INSERT INTO ncaab_player_game_log") for s in c.sql)


# ── the backfill job ─────────────────────────────────────────────────────────

def test_the_players_backfill_is_held_to_this_season_and_last():
    from tracking import job_queue as q
    _, validate = q.JOBS["ncaab_box_backfill"]
    assert validate({"kind": "players"}) == {"kind": "players", "first": 2026, "last": 2027}
    for bad in ({"kind": "players", "first": 2025}, {"kind": "players", "last": 2028}):
        with pytest.raises(ValueError):
            validate(bad)


def test_the_players_job_runs_the_player_module(monkeypatch):
    from tracking import job_queue as q
    seen = {}
    monkeypatch.setattr(q, "_run_script_main",
                        lambda mod, argv: seen.update(mod=mod, argv=argv) or "ok")
    q._job_ncaab_box_backfill(kind="players", first=2026, last=2027)
    assert seen == {"mod": "data.ingestors.ncaab_player_box",
                    "argv": ["--seasons", "2026", "2027"]}


def test_the_migration_is_on_the_active_list():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert pbox.MIGRATION in ACTIVE_MIGRATIONS


# ── Postgres ─────────────────────────────────────────────────────────────────

psycopg2 = pytest.importorskip("psycopg2")

from data.anon_readable import API_ROLES, lock_down_sql  # noqa: E402
from data.db import DBConnection  # noqa: E402
from data.ingestors import ncaab_teams as nt  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

GAMES_DDL = """
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL,
    game_date TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_score NUMERIC, away_score NUMERIC, commence_time TEXT, went_to_ot INTEGER)
"""


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-player-pg-") as d:
        yield d


@pytest.fixture()
def raw(dsn):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    for role in API_ROLES:
        cur.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    f"'{role}') THEN CREATE ROLE {role}; END IF; END $$")
    cur.execute("DROP VIEW IF EXISTS v_player_season_totals_ncaab")
    cur.execute("DROP TABLE IF EXISTS games, ncaab_events, ncaab_player_game_log, "
                "ncaab_player_box_misses")
    cur.execute(GAMES_DDL)
    cur.execute(nt.EVENTS_DDL)
    cur.execute("INSERT INTO games VALUES (%s, 'NCAAB', 2026, '2026-02-15', 'Rutgers', "
                "'Maryland', 68, 57, '2026-02-15T17:00:00Z', 0)", (GAME_ID,))
    cur.execute("INSERT INTO ncaab_events (espn_event_id, game_id, season, game_date, "
                "commence_time, home_espn_id, away_espn_id) VALUES (401825519, %s, 2026, "
                "'2026-02-15', '2026-02-15T17:00:00Z', 164, 120)", (GAME_ID,))
    try:
        yield conn
    finally:
        conn.close()


def test_the_migration_applies_twice_and_opens_only_reads(raw):
    cur = raw.cursor()
    cur.execute(MIGRATION)
    cur.execute(MIGRATION)                     # the second pass returns on a catalog read
    cur.execute("SELECT has_table_privilege('anon', 'ncaab_player_game_log', 'SELECT'), "
                "has_table_privilege('anon', 'ncaab_player_game_log', 'INSERT'), "
                "has_table_privilege('anon', 'ncaab_player_box_misses', 'SELECT'), "
                "has_table_privilege('anon', 'v_player_season_totals_ncaab', 'SELECT')")
    assert cur.fetchone() == (True, False, False, True)
    for fn in ("player_window_totals_ncaab(integer, integer)",
               "player_recent_games_ncaab(integer, integer, text[])",
               "player_season_stat_values_ncaab(integer, text)",
               "player_h2h_stat_values_ncaab(integer[], text, text[], text[])"):
        cur.execute("SELECT has_function_privilege('anon', %s, 'EXECUTE')", (fn,))
        assert cur.fetchone() == (True,), fn


def test_a_backfill_stores_once_and_the_stats_reads_answer(raw, dsn):
    raw.cursor().execute(MIGRATION)
    calls = []

    def get_json(url, params):
        calls.append(params)
        return summary()

    conn = DBConnection(psycopg2.connect(dsn), url=dsn)
    try:
        t = pbox.run_backfill(2026, 2026, now=NOW, get_json=get_json,
                              connect=lambda: conn, sleep=0)
    finally:
        conn._conn.close()
    assert (t["games_stored"], t["player_rows"], t["failed"]) == (1, 5, [])
    conn = DBConnection(psycopg2.connect(dsn), url=dsn)
    try:
        again = pbox.run_backfill(2026, 2026, now=NOW, get_json=get_json,
                                  connect=lambda: conn, sleep=0)
    finally:
        conn._conn.close()
    assert again["due"] == 0 and len(calls) == 1    # nothing fetched twice

    cur = raw.cursor()
    cur.execute("SELECT player_name, team, games_played, points, threes, pra "
                "FROM v_player_season_totals_ncaab WHERE player_id = 'a0'")
    assert cur.fetchone() == ("Away 0", "Maryland", 1, 40, 2, 50)
    cur.execute("SELECT count(*) FROM player_window_totals_ncaab(2026, 10)")
    assert cur.fetchone() == (5,)
    cur.execute("SELECT player_id, rn, points FROM player_recent_games_ncaab(2026, 10, "
                "ARRAY['Maryland']) ORDER BY player_id")
    assert cur.fetchall() == [("a0", 1, 40), ("a1", 1, 17)]
    cur.execute("SELECT \"values\" FROM player_season_stat_values_ncaab(2026, 'points') "
                "WHERE player_id = 'h0'")
    assert [float(v) for v in cur.fetchone()[0]] == [30.0]
    cur.execute("SELECT opponent, games, dates FROM player_h2h_stat_values_ncaab("
                "ARRAY[2026], 'points', ARRAY['Rutgers'], ARRAY['Maryland']) "
                "WHERE player_id = 'h1'")
    assert cur.fetchone() == ("Maryland", 1, ["2026-02-15"])


def test_a_refused_game_is_recorded_and_stores_nothing(raw, dsn):
    raw.cursor().execute(MIGRATION)
    conn = DBConnection(psycopg2.connect(dsn), url=dsn)
    try:
        t = pbox.run_backfill(2026, 2026, now=NOW,
                              get_json=lambda u, p: summary(home_pts=(1, 2, 3)),
                              connect=lambda: conn, sleep=0)
    finally:
        conn._conn.close()
    assert (t["games_stored"], t["refused"]) == (0, 1)
    cur = raw.cursor()
    cur.execute("SELECT count(*) FROM ncaab_player_game_log")
    assert cur.fetchone() == (0,)
    cur.execute("SELECT attempts, reason FROM ncaab_player_box_misses")
    attempts, reason = cur.fetchone()
    assert attempts == 1 and "players score 6, final 68" in reason


def test_the_team_box_feed_stores_players_from_its_own_call(raw, dsn):
    """A new final costs one ESPN call: the team feed hands its payload over."""
    from data.ingestors import ncaab_sdv_import as sdv
    cur = raw.cursor()
    cur.execute("DROP TABLE IF EXISTS ncaab_team_game_stats, ncaab_player_season, "
                "ncaab_period_scores, ncaab_box_misses")
    cur.execute(MIGRATION)
    calls = []

    def get_json(url, params):
        calls.append(params)
        return summary()

    # Created here rather than through sdv.ensure_tables: on Postgres 16 (this
    # sandbox; production is 17) the guard's first catalog query names the
    # 17-only MAINTAIN privilege, and its rollback undoes the CREATE it guards.
    for ddl in (sdv.TEAM_DDL, sdv.TEAM_INDEX, sdv.PLAYER_DDL, box.PERIODS_DDL,
                box.PERIODS_INDEX, box.MISSES_DDL):
        cur.execute(ddl)
    for t in (sdv.TEAM_TABLE, sdv.PLAYER_TABLE, "ncaab_period_scores", "ncaab_box_misses"):
        for stmt in lock_down_sql(t):
            cur.execute(stmt)
    conn = DBConnection(psycopg2.connect(dsn), url=dsn)
    try:
        t = box.run_box_backfill(2026, 2026, now=NOW, get_json=get_json,
                                 connect=lambda: conn, sleep=0)
    finally:
        conn._conn.close()
    assert (t["games_stored"], t["box_rows"], t["player_rows"]) == (1, 2, 5)
    assert len(calls) == 1
    cur.execute("SELECT count(*) FROM ncaab_player_game_log")
    assert cur.fetchone() == (5,)
    # The catch-up then finds nothing due, so it makes no call either.
    conn = DBConnection(psycopg2.connect(dsn), url=dsn)
    try:
        r = pbox.run_backfill(2026, 2026, now=NOW, get_json=get_json,
                              connect=lambda: conn, sleep=0)
    finally:
        conn._conn.close()
    assert r["due"] == 0 and len(calls) == 1

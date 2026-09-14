"""The CFBD play round trip through Supabase, and why it exists.

`ncaaf_live/backtest/pull_pbp` wrote per-season parquet into a GITIGNORED
directory, so the states corpus the live engine was trained on existed on
exactly one laptop -- and the laptop that has to run the 2025 in-play replay
holds no CFBD_API_KEY (it is a Railway variable; the connector redacts values
and there is no CLI here). The worker fetches, `ncaaf_plays` carries it, any
machine reads it back.

What has to hold for that to be safe: the round trip must return the CFBD
SPELLING states.py consumes, it must not quietly lose a column, and a re-run
must not duplicate a play.
"""
from __future__ import annotations

import pandas as pd
import pytest

from ncaaf_live.backtest.pull_pbp import (
    DB_COLUMNS, DB_TO_CFBD, load_season_from_db, store_season)


def _plays(n=3, season=2025):
    # CFBD play ids are unique across seasons; the fixture has to be too, or a
    # second season silently overwrites the first in the fake store.
    return pd.DataFrame([{
        "id": f"{season}p{i}", "gameId": f"{season}401welcome", "driveId": f"d{i}",
        "playNumber": i, "period": 1, "clock_minutes": 14, "clock_seconds": 30,
        "offense": "Ohio State", "defense": "Ball State",
        "home": "Ohio State", "away": "Ball State",
        "offenseScore": 7 * i, "defenseScore": 0,
        "offenseTimeouts": 3, "defenseTimeouts": 3,
        "down": 1, "distance": 10, "yardsToGoal": 75, "yardsGained": 4,
        "playType": "Rush", "scoring": False,
        "wallclock": f"2025-09-06T16:0{i}:00.000Z",
        "season": season, "week": 2, "season_type": "regular",
    } for i in range(n)])


class _Conn:
    """Records what executemany was handed, and replays it on SELECT."""

    def __init__(self):
        self.rows: dict = {}
        self.sql = None
        self.commits = 0
        self._select = None

    def executemany(self, sql, rows):
        self.sql = sql
        for r in rows:                      # ON CONFLICT DO UPDATE, in miniature
            self.rows[r["play_id"]] = r

    def execute(self, sql, params=None):
        self._select = (sql, params)
        return self

    def fetchall(self):
        sql, params = self._select
        names = [c.strip() for c in
                 sql.split("SELECT", 1)[1].split("FROM", 1)[0].split(",")]
        season = params[0]
        return [tuple(r.get(n) for n in names) for r in self.rows.values()
                if r.get("season") == season]

    def commit(self):
        self.commits += 1


# ── the map ──────────────────────────────────────────────────────────────────

def test_the_map_is_a_bijection_so_a_round_trip_cannot_collide():
    assert len(DB_TO_CFBD) == len(DB_COLUMNS)
    assert {DB_TO_CFBD[v] for v in DB_COLUMNS.values()} == set(DB_COLUMNS)


def test_every_column_the_puller_keeps_has_a_home_in_the_table():
    """A KEEP column with no DB_COLUMNS entry is dropped on the way in, and the
    states builder would then fail on a machine reading from the DB while
    working fine on the laptop with the parquet -- the worst shape of bug."""
    from ncaaf_live.backtest.pull_pbp import KEEP
    derived = {"clock_minutes", "clock_seconds", "season", "week", "season_type"}
    for col in KEEP:
        if col == "clock":                  # flattened at pull time
            continue
        assert col in DB_COLUMNS, f"{col} would be dropped on the way to the DB"
    assert derived <= set(DB_COLUMNS)


def test_the_stored_columns_match_the_migration():
    import io
    sql = io.open("data/migrations/add_ncaaf_plays.sql", encoding="utf-8").read()
    for db_col in DB_COLUMNS.values():
        assert f"      {db_col} " in sql or f"      {db_col}\n" in sql, \
            f"{db_col} is mapped but not declared in the migration"


# ── the round trip ───────────────────────────────────────────────────────────

def test_a_season_survives_the_round_trip_in_the_cfbd_spelling():
    conn = _Conn()
    got = store_season(conn, 2025, _plays(3))
    assert (got["season"], got["plays"], got["games"]) == (2025, 3, 1)
    assert conn.commits == 1

    back = load_season_from_db(conn, 2025)
    assert len(back) == 3
    # states.py reads these names; if the rename drifts it breaks there, not here
    for cfbd_name in ("gameId", "playNumber", "offenseScore", "yardsToGoal",
                      "playType", "wallclock", "clock_minutes"):
        assert cfbd_name in back.columns
    assert back["offenseScore"].tolist() == [0, 7, 14]
    assert back["playNumber"].dtype.kind in "if"        # numeric, not text


def test_a_rerun_updates_rather_than_duplicating():
    conn = _Conn()
    store_season(conn, 2025, _plays(3))
    store_season(conn, 2025, _plays(3))
    assert len(conn.rows) == 3
    assert "ON CONFLICT (play_id) DO UPDATE" in conn.sql


def test_cfbd_serving_one_play_twice_does_not_break_the_write():
    """executemany raises on two rows with the same key in ONE batch -- the
    ON CONFLICT clause only covers rows already in the table."""
    conn = _Conn()
    doubled = pd.concat([_plays(2), _plays(2)], ignore_index=True)
    got = store_season(conn, 2025, doubled)
    assert got["plays"] == 2


def test_a_season_with_no_plays_writes_nothing_and_says_so():
    conn = _Conn()
    assert store_season(conn, 2025, pd.DataFrame()) == {
        "season": 2025, "plays": 0, "games": 0}      # no ranges: nothing seen
    assert conn.commits == 0


def test_load_is_scoped_to_the_season_asked_for():
    conn = _Conn()
    store_season(conn, 2025, _plays(2, season=2025))
    store_season(conn, 2024, _plays(2, season=2024))
    assert len(load_season_from_db(conn, 2025)) == 2
    assert load_season_from_db(conn, 2023).empty


# ── the fallback that makes a keyless machine work ───────────────────────────

def test_load_pbp_falls_back_to_the_db_when_the_parquet_is_missing(monkeypatch,
                                                                   tmp_path):
    from ncaaf_live.backtest import states
    monkeypatch.setattr(states, "PBP_DIR", tmp_path)      # no parquet anywhere
    conn = _Conn()
    store_season(conn, 2025, _plays(3))
    got = states.load_pbp([2025], conn=conn)
    assert len(got) == 3 and "gameId" in got.columns


def test_a_season_in_neither_place_is_an_error_not_a_short_corpus():
    """Returning fewer seasons than asked for would train or replay on a
    corpus nobody chose, and nothing downstream would notice."""
    from ncaaf_live.backtest import states
    with pytest.raises(FileNotFoundError) as e:
        states.load_pbp([1999], conn=_Conn())
    assert "1999" in str(e.value) and "--to-db" in str(e.value)


# ── the worker job ───────────────────────────────────────────────────────────

def test_the_job_type_is_registered_and_validates_its_seasons():
    from tracking.job_queue import JOBS as JOB_REGISTRY
    assert "ncaaf_pbp_pull" in JOB_REGISTRY
    _, validate = JOB_REGISTRY["ncaaf_pbp_pull"]
    assert validate({"seasons": [2025]}) == {"seasons": [2025]}
    assert validate({"seasons": ["2025"]}) == {"seasons": [2025]}
    for bad in ({"seasons": []}, {"seasons": [2014]}, {"seasons": [2099]},
                {"seasons": list(range(2015, 2030))}, {}):
        with pytest.raises(ValueError):
            validate(bad)


def test_the_declared_job_names_a_real_type_and_valid_args():
    import io
    import json
    from tracking.job_queue import JOBS as JOB_REGISTRY
    jobs = json.load(io.open("jobs/declared_jobs.json", encoding="utf-8"))
    job = next(j for j in jobs if j["key"] == "ncaaf-pbp-2025-for-the-inplay-replay")
    assert job["job_type"] in JOB_REGISTRY
    JOB_REGISTRY[job["job_type"]][1](job["args"])


# ── a partial corpus must not wear the full corpus's name ────────────────────

def test_a_one_season_build_gets_its_own_filename():
    """train_engine fits on states_all.parquet. A one-season file at that path
    would train the engine on a corpus nobody chose while every diagnostic the
    builder prints still read fine -- the same failure load_pbp refuses on the
    way in."""
    from ncaaf_live.backtest.build_states import out_path
    from ncaaf_live.backtest.train_engine import STATES_PATH
    from ncaaf_live.config import ALL_SEASONS

    assert out_path(None) == STATES_PATH
    assert out_path(list(ALL_SEASONS)) == STATES_PATH
    assert out_path([2025]) != STATES_PATH
    assert out_path([2025]).name == "states_2025.parquet"
    assert out_path([2024, 2025]).name == "states_2024-2025.parquet"
    assert out_path([2025], "/tmp/x.parquet").name == "x.parquet"


# ── the column Postgres refuses to name ──────────────────────────────────────

def test_a_value_past_bigint_is_seen_and_reported_not_silently_dropped():
    """The 2026-09-12 failure, pinned. `NumericValueOutOfRange` arrives with no
    column, no value and no row, so both failed runs were undiagnosable from
    their own tracebacks. The scan has to SEE a value past 2^63 and carry it
    into the job result -- a range report that loses the outlier is the one
    thing worse than no report."""
    from ncaaf_live.backtest.pull_pbp import BIGINT_MAX, _report_ranges
    df = _plays(3).rename(columns=DB_COLUMNS)
    df["play_id"] = df["play_id"].astype(str)
    df["game_id_cfbd"] = df["game_id_cfbd"].astype(str)
    df["yards_gained"] = df["yards_gained"].astype(object)
    df.loc[1, "yards_gained"] = 2 ** 70

    ranges = _report_ranges(df, 2025)
    assert ranges["yards_gained"][1] == 2 ** 70      # exact, not a float
    assert ranges["yards_gained"][1] > BIGINT_MAX


def test_the_scan_survives_nulls_and_non_numeric_cells():
    """It walks raw objects, so it must not die on what a feed actually sends."""
    from ncaaf_live.backtest.pull_pbp import _extremes
    assert _extremes([None, 3, float("nan"), "7", 1]) == (1, 7)
    assert _extremes([None, None]) == (None, None)
    assert _extremes([]) == (None, None)


def test_ordinary_values_report_their_range_and_never_raise():
    from ncaaf_live.backtest.pull_pbp import _report_ranges
    df = _plays(5).rename(columns=DB_COLUMNS)
    got = _report_ranges(df, 2025)
    assert got["period"] == [1, 1]


def test_a_stored_season_reports_the_ranges_it_saw():
    """So the next surprise is visible in the job result before it is fatal."""
    conn = _Conn()
    got = store_season(conn, 2025, _plays(4))
    assert got["ranges"]["period"] == [1, 1]
    assert got["ranges"]["offense_score"] == [0, 21]


def test_every_numeric_column_in_the_table_is_range_checked():
    """A column added to the table but not to NUMERIC_COLUMNS would overflow
    with exactly the unnamed error this check exists to replace."""
    import io
    import re
    from ncaaf_live.backtest.pull_pbp import NUMERIC_COLUMNS
    sql = io.open("data/migrations/widen_ncaaf_plays_ints.sql",
                  encoding="utf-8").read()
    block = sql.split("ARRAY[", 1)[1].split("]", 1)[0]
    widened = set(re.findall(r"'([a-z_]+)'", block))
    assert set(NUMERIC_COLUMNS) == widened

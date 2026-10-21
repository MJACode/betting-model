"""The NFL schedule is re-read between daily runs, and at boot (2026-10-21).

WHY THIS FILE EXISTS

Every NFL pre-game job reads its slate from the games table, and the only
writer of those rows was the 6am ET daily ingest. Two gaps followed:

  * a playoff matchup nflverse lists overnight reached the opener model 6 to
    18 hours late. For the 2025 wild card nflverse's commit history has five
    games by 2026-01-05 04:39Z and the sixth at 16:30Z; the 6am run is ~11:00Z;
  * the deploy that added the venue columns left them empty until the next
    6am run, and the wind model places no bet on a game whose venue is not
    established, so it would have bet nothing for most of a day.

The refresh writes only games that have not kicked off, inside 14 days, and on
an existing row it moves only when and where the game is played. The spread,
total, roof, temperature and wind on those rows are NFL prop model features,
and a schedule refresh four times an hour must not change what those models
score on.

The upsert tests run the module's own SQL on SQLite, which implements the same
INSERT ... ON CONFLICT DO UPDATE, so they test what the statement does rather
than what its text looks like.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from data.ingestors import nfl_props_data_ingestor as ing   # noqa: E402

# Thursday 2026-10-22 12:00 ET.
NOW = datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc)


def _game(gid, away, home, gameday, gametime, *, season="2026", week="8",
          game_type="REG", home_score="", spread="-3.0", total="44.5",
          roof="outdoors", stadium_id="", stadium="", location="Home"):
    return gid, {
        "game_id": gid, "season": season, "week": week, "game_type": game_type,
        "gameday": gameday, "gametime": gametime, "home_team": home,
        "away_team": away, "home_score": home_score,
        "away_score": "" if home_score == "" else "17", "location": location,
        "spread_line": spread, "total_line": total, "roof": roof,
        "surface": "grass", "temp": "", "wind": "", "div_game": "0",
        "stadium_id": stadium_id, "stadium": stadium,
    }


SCHEDULE = dict([
    # kicked off an hour ago, no score yet: the refresh must not touch it
    _game("2026_08_MIN_LAC", "MIN", "LAC", "2026-10-22", "11:00"),
    # played and scored
    _game("2026_07_NYG_PHI", "NYG", "PHI", "2026-10-19", "20:15", home_score="24"),
    # ahead, inside 14 days
    _game("2026_08_BUF_NE", "BUF", "NE", "2026-10-25", "13:00",
          stadium_id="BOS00", stadium="Gillette Stadium"),
    _game("2026_07_PIT_NO", "PIT", "NO", "2026-10-25", "09:30", week="7",
          roof="dome", stadium_id="PAR00", stadium="Stade de France",
          location="Neutral"),
    # ahead, but past 14 days
    _game("2026_11_KC_DEN", "KC", "DEN", "2026-11-15", "16:25"),
    # no kickoff time yet
    _game("2026_10_TBD_TBD", "SEA", "SF", "2026-11-01", ""),
    # an old season
    _game("2019_01_GB_CHI", "GB", "CHI", "2019-09-05", "20:20", season="2019",
          home_score="3"),
])


# ── Which games the refresh writes ───────────────────────────────────────────

def test_only_games_ahead_and_inside_the_horizon_are_written():
    rows = ing.upcoming_schedule_rows(SCHEDULE, now=NOW)
    assert {r["game_id"] for r in rows} == {"NFL_2026_08_BUF_NE", "NFL_2026_07_PIT_NO"}
    assert len(rows) == 4                    # both teams of each game


def test_a_wild_card_in_january_carries_last_years_season_label():
    """nflverse labels a January playoff game with the season it ends."""
    wc = dict([_game("2026_19_GB_CHI", "GB", "CHI", "2027-01-16", "16:30",
                     week="19", game_type="WC", stadium_id="CHI98",
                     stadium="Soldier Field")])
    rows = ing.upcoming_schedule_rows(
        wc, now=datetime(2027, 1, 11, 12, 0, tzinfo=timezone.utc))
    assert [r["season_type"] for r in rows] == ["WC", "WC"]
    assert {r["season"] for r in rows} == {2026}


def test_a_naive_now_is_read_as_utc():
    assert len(ing.upcoming_schedule_rows(SCHEDULE, now=NOW.replace(tzinfo=None))) == 4


# ── What the refresh does to the rows it writes (SQLite, the module's SQL) ──

class _Lite:
    """The repo's connection interface over SQLite, psycopg paramstyle
    translated. The catalog probe is Postgres-only and is set per test."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.order: list[str] = []
        cols = ", ".join(ing.TEAM_COLUMNS)
        self.db.execute(f"CREATE TABLE nfl_team_game_stats ({cols}, UNIQUE(game_id, team))")
        self.db.execute("""CREATE TABLE games (game_id PRIMARY KEY, sport, season,
            game_date, home_team, away_team, commence_time, home_score, away_score,
            home_win, week, neutral_site, data_source)""")

    @staticmethod
    def _sql(sql):
        return re.sub(r"%\((\w+)\)s", r":\1", sql)

    def execute(self, sql, params=()):
        return self.db.execute(self._sql(sql), params)

    def executemany(self, sql, rows):
        self.order.append(re.search(r"INSERT INTO (\w+)", sql).group(1))
        return self.db.executemany(self._sql(sql), rows)

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def close(self):
        pass

    def team(self, gid, team, col):
        return self.db.execute(
            f"SELECT {col} FROM nfl_team_game_stats WHERE game_id = ? AND team = ?",
            (gid, team)).fetchone()[0]


@pytest.fixture()
def lite(monkeypatch):
    monkeypatch.setattr(ing, "_has_venue_columns", lambda conn: True)
    return _Lite()


def test_an_existing_row_moves_its_kickoff_and_venue_and_keeps_its_model_inputs(lite):
    """The prop models read spread, total, roof, temp and wind off these rows.

    The daily ingest wrote the BUF @ NE row with a -3 spread and a 1pm
    kickoff. nflverse has since moved the game to 4:25pm and the spread to
    -6.5. The refresh must move the kickoff and leave the spread for the
    daily run: four writes an hour must not change what a prop model scores.
    """
    daily = {k: dict(v) for k, v in SCHEDULE.items()}
    ing.refresh_upcoming_schedule(conn=lite, schedule=daily, now=NOW)
    assert lite.team("NFL_2026_08_BUF_NE", "NE", "spread_line") == -3.0

    moved = {k: dict(v) for k, v in SCHEDULE.items()}
    moved["2026_08_BUF_NE"].update(gametime="16:25", spread_line="-6.5",
                                   total_line="47.5", roof="closed")
    ing.refresh_upcoming_schedule(conn=lite, schedule=moved, now=NOW)

    assert lite.team("NFL_2026_08_BUF_NE", "NE", "commence_time").startswith(
        "2026-10-25T20:25")
    for col, kept in (("spread_line", -3.0), ("total_line", 44.5), ("roof", "outdoors")):
        assert lite.team("NFL_2026_08_BUF_NE", "NE", col) == kept, col
    assert lite.db.execute("SELECT commence_time FROM games WHERE game_id = ?",
                           ("NFL_2026_08_BUF_NE",)).fetchone()[0].startswith(
        "2026-10-25T20:25")


def test_a_row_the_deploy_left_without_a_venue_gets_one(lite):
    """The boot run's reason for existing: rows written before the venue
    columns existed carry none, and the wind model will not bet them."""
    ing.refresh_upcoming_schedule(conn=lite, schedule=SCHEDULE, now=NOW)
    lite.db.execute("UPDATE nfl_team_game_stats SET stadium_id = NULL, stadium = NULL, "
                    "location = NULL")
    ing.refresh_upcoming_schedule(conn=lite, schedule=SCHEDULE, now=NOW)
    assert (lite.team("NFL_2026_07_PIT_NO", "NO", "stadium"),
            lite.team("NFL_2026_07_PIT_NO", "NO", "location")) == ("Stade de France", "Neutral")


def test_a_new_game_is_inserted_whole_and_games_comes_first(lite):
    """A wild card nflverse lists overnight: first sight is a full row, as the
    daily run would write it, and the games row lands first (prop odds and
    picks carry a foreign key to it)."""
    ing.refresh_upcoming_schedule(conn=lite, schedule=SCHEDULE, now=NOW)
    assert lite.team("NFL_2026_08_BUF_NE", "BUF", "spread_line") == -3.0
    assert lite.team("NFL_2026_08_BUF_NE", "BUF", "is_home") == 0
    assert lite.order[0] == "games"
    got = lite.db.execute("SELECT week, neutral_site, data_source FROM games "
                          "WHERE game_id = ?", ("NFL_2026_07_PIT_NO",)).fetchone()
    assert got == (7, 1, "nflverse")


def test_a_game_that_has_started_is_not_touched(lite):
    lite.db.execute("INSERT INTO nfl_team_game_stats (game_id, team, pass_attempts, "
                    "commence_time) VALUES ('NFL_2026_08_MIN_LAC', 'LAC', 21, 'kept')")
    ing.refresh_upcoming_schedule(conn=lite, schedule=SCHEDULE, now=NOW)
    assert lite.team("NFL_2026_08_MIN_LAC", "LAC", "commence_time") == "kept"
    assert lite.team("NFL_2026_08_MIN_LAC", "LAC", "pass_attempts") == 21


def test_without_the_venue_columns_the_schedule_still_lands(monkeypatch):
    """A boot whose column migration failed: kickoffs still move."""
    monkeypatch.setattr(ing, "_has_venue_columns", lambda conn: False)
    lite = _Lite()
    lite.db.execute("DROP TABLE nfl_team_game_stats")
    cols = ", ".join(c for c in ing.TEAM_COLUMNS if c not in ing.VENUE_COLUMNS)
    lite.db.execute(f"CREATE TABLE nfl_team_game_stats ({cols}, UNIQUE(game_id, team))")
    got = ing.refresh_upcoming_schedule(conn=lite, schedule=SCHEDULE, now=NOW)
    assert got == {"games": 2, "teams": 4}
    assert lite.team("NFL_2026_08_BUF_NE", "NE", "commence_time").startswith("2026-10-25T17:00")


# ── The scheduler job ────────────────────────────────────────────────────────

def _jobs(monkeypatch, role="all", on=True):
    import scheduler
    from tracking import job_heartbeat as jh
    marked = []
    monkeypatch.setattr(jh, "mark_disabled", lambda jid, *a, **k: marked.append(jid))
    monkeypatch.setattr(jh, "seed", lambda jid: None)
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", role)
    monkeypatch.setattr(scheduler, "RUN_NFL_SCHEDULE_REFRESH", on, raising=False)
    sched = scheduler.build_scheduler()
    return {j.id: j for j in sched.get_jobs()}, marked


def test_the_refresh_runs_every_15_minutes_and_once_at_boot(monkeypatch):
    jobs, _ = _jobs(monkeypatch)
    job = jobs["nfl_schedule_refresh"]
    assert "minute='5-59/15'" in str(job.trigger)
    first = job.next_run_time
    now = datetime.now(first.tzinfo)
    assert timedelta(0) < first - now <= timedelta(seconds=31), first


def test_the_refresh_belongs_to_the_pipeline_service(monkeypatch):
    jobs, _ = _jobs(monkeypatch, role="pipeline")
    assert "nfl_schedule_refresh" in jobs
    jobs, marked = _jobs(monkeypatch, role="pollers")
    assert "nfl_schedule_refresh" not in jobs and "nfl_schedule_refresh" not in marked


def test_switched_off_it_is_marked_disabled_not_silent(monkeypatch):
    jobs, marked = _jobs(monkeypatch, role="pipeline", on=False)
    assert "nfl_schedule_refresh" not in jobs
    assert "nfl_schedule_refresh" in marked


def test_the_job_runs_the_schedule_only_ingest_with_a_bound(monkeypatch):
    import scheduler
    calls = []
    monkeypatch.setattr(scheduler, "_run",
                        lambda cmd, label, **kw: calls.append((cmd, label, kw)) or "ok")
    scheduler.run_nfl_schedule_refresh()
    (cmd, label, kw), = calls
    assert cmd[1:] == ["-m", "data.ingestors.nfl_props_data_ingestor", "--schedule-only"]
    assert kw.get("timeout") and kw["timeout"] <= 600

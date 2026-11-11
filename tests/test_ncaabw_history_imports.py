"""The NCAABW history import (data/ingestors/ncaabw_sdv_import.py): NCAA's team
box scores and season player minutes from sportsdataverse's season files.

A fork of the sportsdataverse half of tests/test_ncaab_history_imports.py. The
women's files have the men's shape (checked 2026-11-09: the 2025-26 team box
holds 12,038 rows on 6,019 contests under the same columns), so the same rows
exercise the same parser. The men's free line archives have no women's twin.
"""
from __future__ import annotations

import pandas as pd

from data.ingestors import ncaabw_sdv_import as si


def test_the_files_read_are_the_womens():
    assert si.TEAM_BOX_URL.endswith("/ncaa_wbb_team_box/ncaa_wbb_team_box_{season}.parquet")
    assert si.SCHEDULE_URL.endswith("/ncaa_wbb_schedule/ncaa_wbb_schedule_{season}.parquet")
    assert si.PLAYER_BOX_URL.endswith("/ncaa_wbb_player_box/ncaa_wbb_player_box_{season}.parquet")
    assert (si.TEAM_TABLE, si.PLAYER_TABLE) == ("ncaabw_team_game_stats", "ncaabw_player_season")


def test_team_box_rows_key_on_the_ncaa_contest_and_carry_the_opponent():
    # ESPN's game id is NULL before 2022-23, so the key is (contest, team name).
    df = pd.DataFrame([
        {"contest_id": "10039", "team": "Vanderbilt", "home": "Vanderbilt", "away": "Austin Peay",
         "espn_game_id": None, "team_espn_team_id": "238", "home_espn_team_id": "238",
         "away_espn_team_id": "2046", "team_ncaa_team_id": "111240",
         "home_ncaa_team_id": "111240", "away_ncaa_team_id": "110954",
         "o_poss": 66, "pts": 85, "to": 8},
        {"contest_id": "10039", "team": "Austin Peay", "home": "Vanderbilt", "away": "Austin Peay",
         "espn_game_id": None, "team_espn_team_id": "2046", "home_espn_team_id": "238",
         "away_espn_team_id": "2046", "team_ncaa_team_id": "110954",
         "home_ncaa_team_id": "111240", "away_ncaa_team_id": "110954",
         "o_poss": 67, "pts": 79, "to": 14},
        {"contest_id": "10039", "team": "Austin Peay", "o_poss": 99, "pts": 0, "to": 0},
        {"contest_id": "10040", "team": "Some D-II School", "home": "Oakland",
         "away": "Some D-II School", "team_espn_team_id": None, "o_poss": 60, "pts": 50, "to": 5},
    ])
    rows = si.team_rows(df, 2018, {"10039": "2017-11-10"})
    got = [(r["contest_id"], r["team"], r["team_espn_id"], r["opp_espn_id"], r["is_home"], r["tov"])
           for r in rows]
    assert got == [("10039", "Vanderbilt", 238, 2046, True, 8.0),
                   ("10039", "Austin Peay", 2046, 238, False, 14.0),
                   ("10040", "Some D-II School", None, None, False, 5.0)]
    assert rows[0]["game_date"] == "2017-11-10" and rows[0]["espn_game_id"] is None
    assert all(r["source"] == si.SOURCE for r in rows)


def test_schedule_dates_are_iso():
    df = pd.DataFrame([{"contest_id": "10039", "game_date": "11/10/2017"},
                       {"contest_id": "x", "game_date": ""}])
    assert si.schedule_dates(df) == {"10039": "2017-11-10"}


def test_player_seasons_sum_by_team_and_folded_name():
    df = pd.DataFrame([
        {"espn_game_id": "1", "team_espn_team_id": "150", "clean_name": "C.J. Walker", "mins": 20, "pts": 10},
        {"espn_game_id": "2", "team_espn_team_id": "150", "clean_name": "CJ Walker", "mins": 25, "pts": 12},
        {"espn_game_id": "2", "team_espn_team_id": "151", "clean_name": "CJ Walker", "mins": 5, "pts": 0},
    ])
    rows = {(r["team_espn_id"], r["player_key"]): r for r in si.player_rows(df, 2026)}
    duke = rows[(150, "cj walker")]
    assert duke["games"] == 2 and duke["mins"] == 45 and duke["pts"] == 22
    assert rows[(151, "cj walker")]["mins"] == 5


def test_player_key_folds_accents_case_and_punctuation():
    assert si.player_key("José O'Neal Jr.") == "jose oneal jr"


# ── the daily read of this season's file (the totals model's second box source) ──

class _BoxConn:
    """The stored (contest, team) keys of a season, and what was inserted."""

    def __init__(self, stored=()):
        self.stored, self.inserted, self.commits, self.sql = set(stored), [], 0, []

    def execute(self, sql, params=()):
        self.sql.append(" ".join(sql.split()))
        rows = sorted(self.stored) if sql.lstrip().startswith("SELECT contest_id, team") else []

        class R:
            def fetchall(self_inner):
                return rows

            def fetchone(self_inner):
                return rows[0] if rows else None
        return R()

    def executemany(self, sql, rows):
        assert "ON CONFLICT (contest_id, team) DO NOTHING" in sql
        self.inserted += [(r["contest_id"], r["team"]) for r in rows]

    def commit(self):
        self.commits += 1


def _file(*contests):
    return pd.DataFrame([{"contest_id": c, "team": t, "home": "H" + c, "away": "A" + c,
                          "o_poss": 66, "pts": 70, "to": 9}
                         for c in contests for t in ("H" + c, "A" + c)])


def test_the_daily_read_stores_only_contests_not_stored_yet(monkeypatch):
    """A stored row is never rewritten: by March the file holds about 12,000
    rows, and a daily update of every one of them would rewrite the season
    each morning. A day with nothing new writes nothing."""
    monkeypatch.setattr(si, "ensure_tables", lambda conn: None)
    files = {si.TEAM_BOX_URL.format(season=2027): _file("1", "2", "3"),
             si.SCHEDULE_URL.format(season=2027): pd.DataFrame(
                 [{"contest_id": "3", "game_date": "11/09/2026"}])}
    monkeypatch.setattr(si, "_fetch_parquet", lambda url: files.get(url))
    conn = _BoxConn(stored=[("1", "H1"), ("1", "A1"), ("2", "H2"), ("2", "A2")])
    out = si.refresh_season(conn, 2027)
    assert out == {"season": 2027, "file_rows": 6, "new_rows": 2}
    assert conn.inserted == [("3", "H3"), ("3", "A3")]
    (read,) = [q for q in conn.sql if q.startswith("SELECT contest_id, team")]
    assert "WHERE season = %s AND source = %s" in read
    again = _BoxConn(stored=conn.stored | set(conn.inserted))
    assert si.refresh_season(again, 2027)["new_rows"] == 0 and again.inserted == []


def test_a_season_with_no_file_yet_is_not_an_error(monkeypatch):
    monkeypatch.setattr(si, "_fetch_parquet", lambda url: None)
    conn = _BoxConn()
    assert si.refresh_season(conn, 2028) == {"season": 2028, "file_rows": 0, "new_rows": 0,
                                             "team_missing": True}
    assert conn.sql == [] and conn.inserted == []


def test_the_daily_step_reads_the_season_the_date_falls_in(monkeypatch):
    import run_pipeline
    seen = []
    monkeypatch.setattr(si, "refresh_season", lambda conn, season: seen.append(season) or {"season": season})

    class C:
        def close(self):
            seen.append("closed")
    assert si.run_refresh("2026-11-10", connect=lambda: C()) == {"season": 2027}
    assert si.run_refresh("2027-03-01", connect=lambda: C()) == {"season": 2027}
    assert seen == [2027, "closed", 2027, "closed"]
    # the pipeline step: green on a read, red when it raises, never a crash
    monkeypatch.setattr(si, "run_refresh", lambda run_date: {"season": 2027, "new_rows": 0})
    assert run_pipeline.step_ncaabw_ncaa_box("2026-11-10") is True
    monkeypatch.setattr(si, "run_refresh", lambda run_date: (_ for _ in ()).throw(RuntimeError("404")))
    assert run_pipeline.step_ncaabw_ncaa_box("2026-11-10") is False

"""
The NHL as-of features must never contain the game they describe.

Until 2026-09-20 the goalie row a 2024-25 training game read was dated
2024-10-01 and held the goalie's FINAL 2024-25 line (Swayman .8921 / 3.1145 —
the NHL API's season-final figures, to the digit), and "GSAA" was a copy of
GAA. `data/nhl_asof.py` now builds every goalie and team-rate number from the
per-game logs, strictly before the date asked about. These tests pin that,
and the row builders that feed it.
"""
from __future__ import annotations

import pytest

from data.nhl_asof import (GOALIE_PRIOR_SHOTS, TEAM_PRIOR_GAMES, GoalieBook,
                           TeamBook)


def _g(pid, date, season, sa, ga, team="BOS", started=1, gid=None, toi=3600):
    return {"nhl_game_id": gid or int(date.replace("-", "")), "player_id": pid,
            "player_name": f"G{pid}", "game_id": f"NHL_{date}_X_{team}",
            "season": season, "game_date": date, "team": team, "started": started,
            "toi_seconds": toi, "shots_against": sa, "goals_against": ga}


LEAGUE = [_g(99, f"2023-11-{d:02d}", 2024, 30, 3, team="LG") for d in range(1, 29)]


class TestGoalieAsOf:
    def test_a_games_own_result_is_not_in_its_row(self):
        """The whole point. A 10-goal disaster on the 15th must be invisible on
        the 15th and visible on the 16th."""
        rows = LEAGUE + [_g(1, "2024-10-10", 2025, 30, 2),
                         _g(1, "2024-10-15", 2025, 30, 10)]
        book = GoalieBook(rows)
        on_the_day = book.asof(1, 2025, "2024-10-15")
        day_after = book.asof(1, 2025, "2024-10-16")
        miss = 1 - book.league(2025, "2024-10-15")["sv"]   # the league includes him
        assert on_the_day["gsaa"] == pytest.approx(30 * miss - 2, abs=0.01)
        assert day_after["gsaa"] < on_the_day["gsaa"] - 6
        assert day_after["save_pct"] < on_the_day["save_pct"]

    def test_a_goalie_with_no_history_reads_as_league_average_not_as_nothing(self):
        book = GoalieBook(LEAGUE)
        line = book.asof(424242, 2025, "2024-10-10")
        assert line["save_pct"] == pytest.approx(0.9, abs=1e-4)
        assert line["gaa"] == pytest.approx(3.0, abs=1e-3)
        assert line["gsaa"] == 0 and line["gsaa_last5"] == 0

    def test_gsaa_is_goals_saved_above_average_not_a_copy_of_gaa(self):
        rows = LEAGUE + [_g(1, "2024-10-10", 2025, 40, 1)]
        book = GoalieBook(rows)
        line = book.asof(1, 2025, "2024-10-12")
        miss = 1 - book.league(2025, "2024-10-12")["sv"]
        assert line["gsaa"] == pytest.approx(40 * miss - 1, abs=0.01)   # about +3 goals
        assert 2.5 < line["gsaa"] < 3.5
        assert line["gsaa"] != line["gaa"]

    def test_gsaa_is_this_season_only_but_the_rates_reach_back_a_season(self):
        rows = LEAGUE + [_g(1, "2023-12-01", 2024, 1000, 50)]   # .950 last year
        book = GoalieBook(rows)
        line = book.asof(1, 2025, "2024-10-10")
        assert line["gsaa"] == 0
        lg = book.league(2025, "2024-10-10")["sv"]
        expected = (950 + GOALIE_PRIOR_SHOTS * lg) / (1000 + GOALIE_PRIOR_SHOTS)
        assert line["save_pct"] == pytest.approx(expected, abs=2e-4)

    def test_two_seasons_back_is_out_of_the_window(self):
        rows = LEAGUE + [_g(1, "2022-12-01", 2023, 1000, 50)]
        line = GoalieBook(rows).asof(1, 2025, "2024-10-10")
        assert line["save_pct"] == pytest.approx(0.9, abs=1e-4)

    def test_last5_counts_starts_only(self):
        rows = LEAGUE + [_g(1, f"2024-10-{d:02d}", 2025, 30, 0) for d in range(1, 8)]
        rows.append(_g(1, "2024-10-09", 2025, 5, 5, started=0, toi=600))  # relief, shelled
        book = GoalieBook(rows)
        line = book.asof(1, 2025, "2024-10-20")
        miss = 1 - book.league(2025, "2024-10-20")["sv"]
        # five clean starts of 30 shots; the 5-goal relief outing is not a start
        assert line["gsaa_last5"] == pytest.approx(150 * miss, abs=0.01)

    def test_the_starter_is_the_one_who_started(self):
        rows = [_g(1, "2024-10-10", 2025, 10, 4, started=1, toi=1200),
                _g(2, "2024-10-10", 2025, 25, 1, started=0, toi=2400, gid=20241010)]
        book = GoalieBook(rows)
        assert book.starter("BOS", "NHL_2024-10-10_X_BOS")["player_id"] == 1
        assert book.starter("BOS", "NHL_1999-01-01_X_BOS") is None

    def test_no_league_data_means_no_row_rather_than_an_invented_one(self):
        assert GoalieBook([]).asof(1, 2025, "2024-10-10") == {}


def _t(team, date, season, saf, saa, ppo=4, ppg=1, tsh=4, ppga=1, sf=30, sa=30):
    return {"nhl_game_id": int(date.replace("-", "")), "team": team, "season": season,
            "game_date": date, "shots_for": sf, "shots_against": sa,
            "sat_for_5v5": saf, "sat_against_5v5": saa,
            "pp_opportunities": ppo, "pp_goals": ppg,
            "times_shorthanded": tsh, "pp_goals_against": ppga}


class TestTeamRatesAsOf:
    PRIOR = [_t("BOS", f"2023-11-{d:02d}", 2024, 60, 40) for d in range(1, 11)]  # 60%

    def test_opening_night_is_last_seasons_final(self):
        book = TeamBook(self.PRIOR)
        r = book.asof("BOS", 2025, "2024-10-08")
        assert r["corsi_for_pct"] == pytest.approx(60.0)
        assert r["power_play_pct"] == pytest.approx(0.25)
        assert r["penalty_kill_pct"] == pytest.approx(0.75)

    def test_the_rate_moves_during_the_season_and_excludes_the_day_itself(self):
        cur = [_t("BOS", f"2024-10-{d:02d}", 2025, 40, 60) for d in (10, 12, 14)]
        book = TeamBook(self.PRIOR + cur)
        on_14th = book.asof("BOS", 2025, "2024-10-14")     # two games in
        on_15th = book.asof("BOS", 2025, "2024-10-15")     # three
        want = (2 * 40.0 + TEAM_PRIOR_GAMES * 60.0) / (2 + TEAM_PRIOR_GAMES)
        assert on_14th["corsi_for_pct"] == pytest.approx(want, abs=1e-3)
        assert on_15th["corsi_for_pct"] < on_14th["corsi_for_pct"]

    def test_an_expansion_team_starts_from_the_league_not_from_nothing(self):
        book = TeamBook(self.PRIOR)
        assert book.asof("SEA", 2025, "2024-10-08")["corsi_for_pct"] == pytest.approx(60.0)

    def test_no_data_at_all_is_none_not_zero(self):
        assert TeamBook([]).asof("BOS", 2025, "2024-10-08")["corsi_for_pct"] is None


class TestLogRowBuilders:
    def test_a_team_row_carries_the_opponents_shot_attempts(self):
        from data.ingestors.nhl_game_logs import build_team_rows
        summ = [{"gameId": 7, "teamId": 1, "opponentTeamAbbrev": "NYR", "homeRoad": "H",
                 "gameDate": "2024-10-09", "goalsFor": 0, "goalsAgainst": 6,
                 "shotsForPerGame": 31.0, "shotsAgainstPerGame": 40.0},
                {"gameId": 7, "teamId": 2, "opponentTeamAbbrev": "PIT", "homeRoad": "R",
                 "gameDate": "2024-10-09", "goalsFor": 6, "goalsAgainst": 0,
                 "shotsForPerGame": 40.0, "shotsAgainstPerGame": 31.0}]
        rt = [{"gameId": 7, "teamId": 1, "totalShotAttempts": 72},
              {"gameId": 7, "teamId": 2, "totalShotAttempts": 69}]
        rows = {r["team"]: r for r in build_team_rows(
            summ, rt, [], [], [], {1: "PIT", 2: "NYR"}, 2025, 2, "t")}
        assert rows["PIT"]["shot_attempts_against"] == 69
        assert rows["NYR"]["shot_attempts_against"] == 72
        assert rows["PIT"]["game_id"] == rows["NYR"]["game_id"] == "NHL_2024-10-09_NYR_PIT"

    def test_arizona_folds_into_utah(self):
        from data.ingestors.nhl_game_logs import build_goalie_rows
        rows = build_goalie_rows([{"gameId": 1, "playerId": 5, "goalieFullName": "X",
                                   "teamAbbrev": "ARI", "opponentTeamAbbrev": "VGK",
                                   "homeRoad": "R", "gameDate": "2023-11-01",
                                   "gamesStarted": 1, "wins": 1, "timeOnIce": 3600,
                                   "shotsAgainst": 30, "saves": 28, "goalsAgainst": 2}],
                                 2024, 2, "t")
        assert rows[0]["team"] == "UTA" and rows[0]["game_id"] == "NHL_2023-11-01_UTA_VGK"
        assert rows[0]["decision"] == "W" and rows[0]["started"] == 1

    def test_a_capped_page_is_refused_not_stored(self, monkeypatch):
        from data.ingestors import nhl_game_logs as gl

        class _R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"total": 10_000, "data": [{}] * 10_000}

        monkeypatch.setattr(gl.requests, "get", lambda *a, **k: _R())
        monkeypatch.setattr(gl, "PAUSE", 0)
        with pytest.raises(RuntimeError, match="cap"):
            gl._fetch("skater/summary", "x")

    def test_the_skater_pull_is_split_into_windows_that_cover_every_day_once(self):
        from data.ingestors.nhl_game_logs import _windows
        w = list(_windows("2024-10-04", "2024-10-20"))
        assert w[0][0] == "2024-10-04" and w[-1][1] == "2024-10-20"
        for (_, hi), (lo, _) in zip(w, w[1:]):
            assert lo > hi


class TestOpeningNightIsEarlySeason:
    """Until 2026-09-20 a team's first game of a season read last season's
    final row — `games_played 82` — and `is_early_season` came out 0."""

    def test_the_prior_season_stand_in_is_marked(self):
        from features.feature_engine import _blk_nhl_asof
        store = {("BOS", 2026): (["2026-04-10"], [{"games_played": 82, "wins": 33}])}
        row = _blk_nhl_asof(store, "BOS", 2027, "2026-09-29")
        assert row["games_played"] == 82 and row["_prior_season"] is True

    def test_a_current_season_row_is_not(self):
        from features.feature_engine import _blk_nhl_asof
        store = {("BOS", 2027): (["2026-10-05"], [{"games_played": 3}])}
        assert "_prior_season" not in _blk_nhl_asof(store, "BOS", 2027, "2026-10-06")


class TestReturningStarterIsNamedFromTheLog:
    """ESPN names the probable starter; the season summary can put an id to the
    name only once he has played THIS season. In week one that left a returning
    starter rated as a debutant: 28 of the 32 rows written 2026-09-29 -> 10-01
    carried the league-average line (Vasilevskiy, Sorokin, Saros...)."""

    def _book(self):
        rows = LEAGUE + [dict(_g(7, "2024-03-01", 2024, 900, 60), player_name="Andrei Vasilevskiy"),
                         dict(_g(8, "2024-03-02", 2024, 30, 3), player_name="Jakub Dobeš")]
        return GoalieBook(rows)

    def test_last_seasons_starter_is_found_before_his_first_game_this_season(self):
        book = self._book()
        pid = book.player_named("Andrei Vasilevskiy", 2025, "2024-10-08")
        assert pid == 7
        line = book.asof(pid, 2025, "2024-10-08")
        league = book.asof(None, 2025, "2024-10-08")
        assert line["save_pct"] > league["save_pct"]          # his own .933, not the league's .900

    def test_accents_and_case_do_not_break_the_match(self):
        assert self._book().player_named("JAKUB DOBES", 2025, "2024-10-08") == 8

    def test_an_unknown_name_is_none_never_somebody_else(self):
        book = self._book()
        assert book.player_named("Nobody Atall", 2025, "2024-10-08") is None
        assert book.player_named("", 2025, "2024-10-08") is None
        assert book.player_named(None, 2025, "2024-10-08") is None

    def test_a_name_from_two_seasons_back_is_not_reached_for(self):
        """The rating window is this season and last; a name older than that
        has no line to give and must not be matched to one."""
        assert self._book().player_named("Andrei Vasilevskiy", 2026, "2025-10-08") is None

    def test_a_game_on_or_after_the_date_asked_about_does_not_name_him(self):
        book = GoalieBook(LEAGUE + [dict(_g(9, "2024-10-08", 2025, 30, 2), player_name="New Guy")])
        assert book.player_named("New Guy", 2025, "2024-10-08") is None
        assert book.player_named("New Guy", 2025, "2024-10-09") == 9

"""
The ET/UTC duplicate games row, and the score mirroring that settles it.

The odds ingestor dates a game by its EASTERN kickoff; cfbd_ingestor.parse_games
dates it by CFBD's UTC start_date. A night game therefore exists twice, picks
attach to the odds row and the final lands on the CFBD row — so an evening NCAAF
pick could never settle. These pin the mirroring that closes that gap.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.cfbd_ingestor import (  # noqa: E402
    alias_score_updates,
    mirror_scores_to_alias_rows,
)


def _cfbd(game_id, date, home, away, hs, as_):
    return {"game_id": game_id, "game_date": date, "home_team": home,
            "away_team": away, "home_score": hs, "away_score": as_,
            "home_win": None if hs == as_ else int(hs > as_)}


def _row(game_id, date, home, away, home_score=None):
    return {"game_id": game_id, "game_date": date, "home_team": home,
            "away_team": away, "home_score": home_score}


# ── the production case ──────────────────────────────────────────────────────

def test_the_reported_unlv_game_gets_its_final_mirrored():
    """
    2026-08-29, 10:19pm ET. The live totals pick sat on the ET row with no
    score; CFBD wrote 21-27 to the UTC row. Settlement graded neither.
    """
    updates = alias_score_updates(
        [_cfbd("NCAAF_2026-08-30_memphis_unlv", "2026-08-30", "UNLV", "Memphis", 21, 27)],
        [_row("NCAAF_2026-08-29_memphis_unlv", "2026-08-29", "UNLV", "Memphis")],
    )
    assert len(updates) == 1
    upd = updates[0]
    assert upd["game_id"] == "NCAAF_2026-08-29_memphis_unlv"
    assert (upd["home_score"], upd["away_score"]) == (21, 27)
    assert upd["home_win"] == 0          # Memphis (away) won → Over 36.5 grades


def test_a_daytime_game_has_no_duplicate_and_is_untouched():
    """The ET and UTC dates agree before ~8pm ET, so there is nothing to mirror."""
    assert alias_score_updates(
        [_cfbd("NCAAF_2026-08-29_north-carolina_tcu", "2026-08-29", "TCU",
               "North Carolina", 10, 15)],
        [_row("NCAAF_2026-08-29_north-carolina_tcu", "2026-08-29", "TCU",
              "North Carolina", 10)],
    ) == []


# ── matching rules ───────────────────────────────────────────────────────────

def test_scores_are_swapped_when_the_duplicate_row_has_the_teams_reversed():
    upd = alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_b_a", "2026-09-06", "A", "B", 30, 17)],
        [_row("NCAAF_2026-09-05_a_b", "2026-09-05", "B", "A")],
    )[0]
    assert (upd["home_score"], upd["away_score"]) == (17, 30)
    assert upd["home_win"] == 0


def test_the_same_matchup_a_year_later_is_never_mirrored():
    """Annual rivalries repeat the slug pair — only the date window separates them."""
    assert alias_score_updates(
        [_cfbd("NCAAF_2026-11-28_michigan_ohio-state", "2026-11-28",
               "Ohio State", "Michigan", 30, 24)],
        [_row("NCAAF_2025-11-29_michigan_ohio-state", "2025-11-29",
              "Ohio State", "Michigan")],
    ) == []


def test_a_two_day_gap_is_outside_the_window():
    assert alias_score_updates(
        [_cfbd("NCAAF_2026-09-07_b_a", "2026-09-07", "A", "B", 30, 17)],
        [_row("NCAAF_2026-09-05_b_a", "2026-09-05", "A", "B")],
    ) == []


def test_a_row_that_already_has_a_final_is_never_overwritten():
    """A mirrored score is an inference; it must not clobber a real result."""
    assert alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_b_a", "2026-09-06", "A", "B", 30, 17)],
        [_row("NCAAF_2026-09-05_b_a", "2026-09-05", "A", "B", home_score=41)],
    ) == []


def test_accented_and_punctuated_names_match_through_the_slug():
    """San José State / Hawai'i / Texas A&M all appeared in week-1 picks."""
    upd = alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_san-jose-state_hawai-i", "2026-09-06",
               "Hawai'i", "San José State", 24, 21)],
        [_row("NCAAF_2026-09-05_san-jose-state_hawai-i", "2026-09-05",
              "Hawai’i", "San Jose State")],
    )[0]
    assert (upd["home_score"], upd["away_score"]) == (24, 21)


def test_a_tie_mirrors_with_a_null_home_win():
    upd = alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_b_a", "2026-09-06", "A", "B", 21, 21)],
        [_row("NCAAF_2026-09-05_b_a", "2026-09-05", "A", "B")],
    )[0]
    assert upd["home_win"] is None


def test_conflicting_finals_leave_the_row_unscored_rather_than_guessing():
    updates = alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_b_a", "2026-09-06", "A", "B", 30, 17),
         _cfbd("NCAAF_2026-09-07_b_a", "2026-09-07", "A", "B", 10, 3)],
        [_row("NCAAF_2026-09-06_b_a2", "2026-09-06", "A", "B")],
    )
    assert updates == []


@pytest.mark.parametrize("bad", [
    {"home_team": None, "away_team": "B"},
    {"home_team": "A", "away_team": ""},
    {"home_team": "A", "away_team": "A"},
])
def test_unusable_team_names_are_skipped(bad):
    row = _row("NCAAF_2026-09-05_x_y", "2026-09-05", "A", "B")
    row.update(bad)
    assert alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_b_a", "2026-09-06", "A", "B", 30, 17)], [row]
    ) == []


def test_an_unparseable_date_is_skipped_rather_than_raising():
    assert alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_b_a", "2026-09-06", "A", "B", 30, 17)],
        [_row("NCAAF_bad_b_a", "not-a-date", "A", "B")],
    ) == []


def test_an_unscored_source_row_mirrors_nothing():
    assert alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_b_a", "2026-09-06", "A", "B", None, None)],
        [_row("NCAAF_2026-09-05_b_a", "2026-09-05", "A", "B")],
    ) == []


# ── the DB writer ────────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    """Records writes; returns the window query's rows."""

    def __init__(self, window_rows):
        self.window_rows = window_rows
        self.writes: list[tuple[str, dict]] = []
        self.commits = 0

    def execute(self, sql, params=None):
        if "UPDATE games" in sql:
            self.writes.append((sql, params))
            return _FakeCursor([])
        return _FakeCursor(self.window_rows)

    def commit(self):
        self.commits += 1


def test_writer_updates_the_duplicate_row_and_commits():
    conn = _FakeConn([("NCAAF_2026-08-29_memphis_unlv", "2026-08-29",
                       "UNLV", "Memphis", None)])
    n = mirror_scores_to_alias_rows(
        conn, [_cfbd("NCAAF_2026-08-30_memphis_unlv", "2026-08-30",
                     "UNLV", "Memphis", 21, 27)])
    assert n == 1 and conn.commits == 1
    sql, params = conn.writes[0]
    assert params == {"game_id": "NCAAF_2026-08-29_memphis_unlv",
                      "home_score": 21, "away_score": 27, "home_win": 0}
    # The guard belongs in the statement too, so a concurrent real final wins.
    assert "home_score IS NULL" in sql


def test_writer_never_touches_the_db_when_there_is_nothing_to_mirror():
    conn = _FakeConn([])
    assert mirror_scores_to_alias_rows(conn, []) == 0
    assert conn.writes == [] and conn.commits == 0

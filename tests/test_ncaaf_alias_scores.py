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


# ── the WRONG-OPPONENT duplicate row (2026-09-07) ─────────────────────────────
#
# Two ways the odds ingestor writes a row whose opponent name differs from
# CFBD's for the same game: an FCS name that prefix-resolved to an FBS school
# ("Indiana" for Indiana State - six live BETs on 2026-09-04/05 sat unsettled
# this way), and an unresolved name that kept its mascot ("Abilene Christian
# Wildcats"). Neither shares the slug pair, so the exact pass above never saw
# them. Home team + a day identifies a college football game; the other side
# must be an EXTENDED slug, not merely different.

def test_the_purdue_game_mislabelled_as_indiana_gets_its_final():
    updates = alias_score_updates(
        [_cfbd("NCAAF_2026-09-04_indiana-state_purdue", "2026-09-04",
               "Purdue", "Indiana State", 44, 19)],
        [_row("NCAAF_2026-09-04_indiana_purdue", "2026-09-04", "Purdue", "Indiana")],
    )
    assert [(u["game_id"], u["home_score"], u["away_score"], u["home_win"])
            for u in updates] == [("NCAAF_2026-09-04_indiana_purdue", 44, 19, 1)]


def test_an_unresolved_name_that_kept_its_mascot_gets_its_final():
    updates = alias_score_updates(
        [_cfbd("NCAAF_2026-09-05_abilene-christian_texas-tech", "2026-09-05",
               "Texas Tech", "Abilene Christian", 52, 7)],
        [_row("NCAAF_2026-09-05_abilene-christian-wildcats_texas-tech",
              "2026-09-05", "Texas Tech", "Abilene Christian Wildcats")],
    )
    assert [u["game_id"] for u in updates] == \
        ["NCAAF_2026-09-05_abilene-christian-wildcats_texas-tech"]


def test_the_byu_game_a_day_apart_and_both_of_its_rows():
    """Utah Tech @ BYU kicked at 8:02pm ET 2026-09-05. The live loop wrote
    'Utah' rows dated 09-05 AND 09-06; CFBD's final is on 09-06."""
    updates = alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_utah-tech_byu", "2026-09-06", "BYU", "Utah Tech", 63, 7)],
        [_row("NCAAF_2026-09-05_utah_byu", "2026-09-05", "BYU", "Utah"),
         _row("NCAAF_2026-09-06_utah_byu", "2026-09-06", "BYU", "Utah")],
    )
    assert sorted(u["game_id"] for u in updates) == \
        ["NCAAF_2026-09-05_utah_byu", "NCAAF_2026-09-06_utah_byu"]
    assert all((u["home_score"], u["away_score"]) == (63, 7) for u in updates)


def test_a_loose_match_swaps_scores_when_the_row_is_reversed():
    updates = alias_score_updates(
        [_cfbd("NCAAF_2026-09-04_indiana-state_purdue", "2026-09-04",
               "Purdue", "Indiana State", 44, 19)],
        [_row("X", "2026-09-04", "Indiana", "Purdue")],
    )
    assert (updates[0]["home_score"], updates[0]["away_score"]) == (19, 44)
    assert updates[0]["home_win"] == 0


def test_an_exact_match_beats_a_loose_one_for_the_same_row():
    """If a row matches one final exactly it must not ALSO collect a loose
    claim from another and be refused as conflicting."""
    updates = alias_score_updates(
        [_cfbd("NCAAF_2026-09-06_utah_byu", "2026-09-06", "BYU", "Utah", 20, 17),
         _cfbd("NCAAF_2026-09-06_utah-tech_byu", "2026-09-06", "BYU", "Utah Tech", 63, 7)],
        [_row("NCAAF_2026-09-05_utah_byu", "2026-09-05", "BYU", "Utah")],
    )
    assert [(u["home_score"], u["away_score"]) for u in updates] == [(20, 17)]


def test_a_merely_different_opponent_is_not_the_same_game():
    """Same home team and day, but 'Georgia' does not extend 'Alabama'."""
    assert alias_score_updates(
        [_cfbd("A", "2026-09-05", "Florida", "Alabama", 24, 21)],
        [_row("B", "2026-09-05", "Florida", "Georgia")],
    ) == []


def test_a_bare_substring_is_not_an_extension():
    """'utah' must not claim 'utahns' - extension is by whole hyphenated word."""
    assert alias_score_updates(
        [_cfbd("A", "2026-09-05", "BYU", "Utahns", 1, 0)],
        [_row("B", "2026-09-05", "BYU", "Utah")],
    ) == []


def test_two_loose_finals_for_one_row_are_refused():
    updates = alias_score_updates(
        [_cfbd("A", "2026-09-05", "BYU", "Utah Tech", 63, 7),
         _cfbd("B", "2026-09-06", "BYU", "Utah State", 30, 10)],
        [_row("C", "2026-09-05", "BYU", "Utah")],
    )
    assert updates == []


def test_stored_finals_are_mirrored_without_a_cfbd_pull():
    """settle_picks runs hourly; the CFBD results pull runs once at 6am. The
    stored-final mirror closes that gap from what the table already holds."""
    from data.ingestors.cfbd_ingestor import mirror_stored_finals

    class _Conn(_FakeConn):
        def execute(self, sql, params=None):
            if "home_score IS NOT NULL" in sql:          # the scored-rows read
                return _FakeCursor([
                    ("NCAAF_2026-09-04_indiana-state_purdue", "2026-09-04",
                     "Purdue", "Indiana State", 44, 19)])
            return super().execute(sql, params)

    conn = _Conn([("NCAAF_2026-09-04_indiana_purdue", "2026-09-04",
                   "Purdue", "Indiana", None)])
    assert mirror_stored_finals(conn, "2026-09-07") == 1
    _sql, params = conn.writes[0]
    assert params["game_id"] == "NCAAF_2026-09-04_indiana_purdue"
    assert (params["home_score"], params["away_score"]) == (44, 19)

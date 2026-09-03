"""The shared book-name -> team-abbreviation map.

Tested once, in one place, because it is shared by every direct book feed and
because two bugs have already been found in it -- both by tests, neither by
review:

  1. Matching on the abbreviation PREFIX of the book's string. DraftKings
     writes "NY Yankees" and "NY Mets", both yielding "NY", so one game is
     dropped or the WRONG one matches. "CHI White Sox" is our CWS, which a
     prefix never reaches.
  2. The nickname map that replaced it said ATH for the Athletics, where the
     games table uses OAK. A map that is internally tidy but disagrees with our
     own ids matches nothing -- which looks exactly like a quiet slate.

A wrongly matched game writes one team's price onto another team's row and
nothing downstream can tell. A dropped game costs one market and shows in a
counter. So every ambiguity here must resolve to None.
"""
from __future__ import annotations

from data.ingestors.book_team_map import (MLB_NICKNAMES, abbr_from_team_string,
                                          resolve_game_id, split_matchup)


class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return self._rows


# -- the cases prefix matching gets wrong -------------------------------------

def test_the_two_new_york_clubs_do_not_collapse():
    assert abbr_from_team_string("NY Yankees") == "NYY"
    assert abbr_from_team_string("NY Mets") == "NYM"


def test_the_two_chicago_clubs_do_not_collapse():
    assert abbr_from_team_string("CHI White Sox") == "CWS"
    assert abbr_from_team_string("CHI Cubs") == "CHC"


def test_white_sox_is_not_shadowed_by_a_shorter_nickname():
    """Longest-first matching. If a shorter suffix ever wins, "White Sox"
    silently becomes some other club."""
    assert abbr_from_team_string("Chicago White Sox") == "CWS"
    assert abbr_from_team_string("Boston Red Sox") == "BOS"


def test_the_athletics_use_the_abbreviation_the_database_uses():
    assert abbr_from_team_string("Athletics") == "OAK"
    assert abbr_from_team_string("Oakland Athletics") == "OAK"


# -- both books' naming styles ------------------------------------------------

def test_draftkings_and_bovada_formats_resolve_the_same():
    """DK writes "BOS Red Sox", bovada writes "Boston Red Sox"."""
    for dk, bov in [("BOS Red Sox", "Boston Red Sox"),
                    ("LA Dodgers", "Los Angeles Dodgers"),
                    ("WAS Nationals", "Washington Nationals"),
                    ("TOR Blue Jays", "Toronto Blue Jays")]:
        assert abbr_from_team_string(dk) == abbr_from_team_string(bov)
        assert abbr_from_team_string(dk) is not None


# -- refusals -----------------------------------------------------------------

def test_an_unrecognised_club_is_refused_not_guessed():
    assert abbr_from_team_string("Sacramento Whatevers") is None
    assert abbr_from_team_string("") is None
    assert abbr_from_team_string(None) is None


def test_the_matchup_split_is_away_at_home():
    """Silently reversing home and away is the same class of unrecoverable
    error as matching the wrong game."""
    assert split_matchup("Cincinnati Reds @ Chicago Cubs") == ("CIN", "CHC")
    assert split_matchup("BOS Red Sox @ NY Yankees") == ("BOS", "NYY")


def test_a_string_with_no_at_sign_is_refused():
    assert split_matchup("some futures market") == (None, None)
    assert split_matchup("") == (None, None)


def test_an_ambiguous_game_resolves_to_none():
    rows = [("MLB_A", "BOS", "NYY"), ("MLB_B", "BOS", "NYY")]
    assert resolve_game_id(_Conn(rows), "MLB", "BOS Red Sox @ NY Yankees",
                           ["2026-08-30"], {}) is None


def test_a_unique_game_resolves():
    rows = [("MLB_2026-08-30_BOS_NYY", "BOS", "NYY"), ("MLB_X", "SD", "TB")]
    assert resolve_game_id(_Conn(rows), "MLB", "BOS Red Sox @ NY Yankees",
                           ["2026-08-30"], {}) == "MLB_2026-08-30_BOS_NYY"


def test_a_non_mlb_sport_is_refused_rather_than_guessed():
    """NCAAF ids are CFBD school names and need their own map."""
    assert resolve_game_id(_Conn([]), "NCAAF", "Ohio State @ Michigan",
                           ["2026-08-30"], {}) is None


# -- the map itself -----------------------------------------------------------

def test_every_club_is_mapped_exactly_once():
    assert len(MLB_NICKNAMES) == 30
    assert len(set(MLB_NICKNAMES.values())) == 30, "two nicknames share an abbr"


def test_the_abbreviations_are_the_ones_the_games_table_uses():
    from data.ingestors.mlb_stats_ingestor import STATSAPI_TEAM_IDS
    ours = set(STATSAPI_TEAM_IDS.values())
    assert set(MLB_NICKNAMES.values()) == ours, (
        set(MLB_NICKNAMES.values()) ^ ours)

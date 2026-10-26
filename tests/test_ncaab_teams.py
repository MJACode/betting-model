"""NCAAB identity: slugs, season labels, ET dates, the name resolver and the
odds-event join onto ESPN's schedule (data/ingestors/ncaab_teams.py)."""

import pytest

import config
from data.ingestors import ncaab_teams as nt


def _t(espn_id, school, mascot, display=None, short=None, alt=()):
    return {"espn_id": espn_id, "school": school, "slug": nt.ncaab_slug(school),
            "mascot": mascot, "display_name": display or f"{school} {mascot}",
            "short_name": short, "abbreviation": None, "is_d1": True, "alt": list(alt)}


REGISTRY = [
    _t(150, "Duke", "Blue Devils"),
    _t(9, "Arizona State", "Sun Devils"),
    _t(96, "Kentucky", "Wildcats"),
    _t(2306, "Kansas State", "Wildcats"),
    _t(2305, "Kansas", "Jayhawks"),
    _t(12, "Arizona", "Wildcats"),
    _t(41, "UConn", "Huskies", alt=("Connecticut Huskies",)),
    _t(2390, "Miami", "Hurricanes"),
    _t(193, "Miami (OH)", "RedHawks"),
    _t(2608, "Saint Mary's", "Gaels"),
    _t(2000, "Abilene Christian", "Wildcats"),
]


def test_slugs_are_the_ncaaf_rule():
    assert nt.ncaab_slug("Miami (OH)") == "miami-oh"
    assert nt.ncaab_slug("Texas A&M") == "texas-a-m"
    assert nt.ncaab_slug("Saint Mary's") == "saint-mary-s"
    assert nt.ncaab_slug("San José State") == "san-jose-state"
    assert nt.build_ncaab_game_id("2026-11-03", "kansas-state", "kentucky") == \
        "NCAAB_2026-11-03_kansas-state_kentucky"


def test_season_is_the_ending_year_espn_uses():
    assert nt.ncaab_season_label("2026-11-01") == 2027
    assert nt.ncaab_season_label("2026-12-31") == 2027
    assert nt.ncaab_season_label("2027-01-10") == 2027
    assert nt.ncaab_season_label("2027-04-05") == 2027


def test_a_late_west_coast_tip_files_on_its_eastern_date():
    assert nt.eastern_game_date("2026-11-04T02:30:00Z") == "2026-11-03"
    assert nt.eastern_game_date("2026-11-02T04:59Z") == "2026-11-01"
    assert nt.eastern_game_date("2026-11-03") == "2026-11-03"


@pytest.mark.parametrize("name,espn_id", [
    ("Duke Blue Devils", 150),
    ("Arizona State Sun Devils", 9),
    ("Kentucky Wildcats", 96),
    ("Kansas State Wildcats", 2306),
    ("Kansas Jayhawks", 2305),
    ("Arizona Wildcats", 12),
    ("UConn Huskies", 41),
    ("Connecticut Huskies", 41),          # alternate name
    ("Miami Hurricanes", 2390),
    ("Miami (OH) RedHawks", 193),
    ("Saint Mary's Gaels", 2608),
    ("Saint Marys Gaels", 2608),          # punctuation folded
    ("Abilene Christian Wildcats", 2000),
])
def test_feed_names_resolve_to_the_right_school(name, espn_id):
    assert nt.resolve_team_name(name, REGISTRY) == espn_id


def test_a_school_that_only_prefixes_the_name_is_not_a_match():
    # "Kansas" prefixes "Kansas Christian Falcons" but the rest is not the
    # Jayhawks: a different school, never Kansas (NCAAF's Indiana State trap).
    assert nt.resolve_team_name("Kansas Christian Falcons", REGISTRY) is None
    assert nt.resolve_team_name("Arizona Christian Firestorm", REGISTRY) is None


def test_a_shortened_mascot_still_resolves_by_prefix():
    reg = REGISTRY + [_t(62, "Hawai'i", "Rainbow Warriors")]
    assert nt.resolve_team_name("Hawaii Warriors", reg) == 62


def test_an_ambiguous_name_resolves_to_nothing_rather_than_a_guess():
    # Two registry rows claim the same school and mascot: refuse to pick.
    reg = REGISTRY + [_t(999, "Kentucky", "Wildcats")]
    assert nt.resolve_team_name("Kentucky Wildcats", reg) is None
    # A shared display name that school + mascot tells apart still resolves.
    reg = REGISTRY + [_t(998, "Kentucky", "Colonels", display="Kentucky Wildcats")]
    assert nt.resolve_team_name("Kentucky Wildcats", reg) == 96


def test_the_override_map_wins_and_is_an_espn_id(monkeypatch):
    monkeypatch.setattr(config, "NCAAB_ODDS_API_MAP", {"UNC Wilmington Seahawks": "350"})
    assert nt.resolve_team_name("UNC Wilmington Seahawks", REGISTRY) == 350


def test_an_unknown_name_or_empty_registry_resolves_to_nothing():
    assert nt.resolve_team_name("Nowhere Tech Nobodies", REGISTRY) is None
    assert nt.resolve_team_name("Duke Blue Devils", []) is None
    assert nt.resolve_team_name("", REGISTRY) is None


GAMES = [
    {"game_id": "NCAAB_2026-11-25_duke_kansas", "game_date": "2026-11-25",
     "commence_time": "2026-11-26T00:00:00Z", "home_espn_id": 2305, "away_espn_id": 150},
    {"game_id": "NCAAB_2026-11-03_kansas-state_kentucky", "game_date": "2026-11-03",
     "commence_time": "2026-11-04T00:00:00Z", "home_espn_id": 96, "away_espn_id": 2306},
]


def test_an_event_in_espns_orientation_is_not_flipped():
    hit = nt.match_event(GAMES, 2305, 150, "2026-11-26T00:00:00Z")
    assert hit == ("NCAAB_2026-11-25_duke_kansas", False)


def test_a_neutral_court_event_the_feed_orients_the_other_way_is_flipped():
    # The feed calls Duke home; ESPN calls Kansas home. Same game, one row,
    # and the caller must swap home and away before parsing outcomes.
    hit = nt.match_event(GAMES, 150, 2305, "2026-11-26T00:00:00Z")
    assert hit == ("NCAAB_2026-11-25_duke_kansas", True)


def test_a_utc_dated_tip_still_finds_its_eastern_game():
    assert nt.match_event(GAMES, 96, 2306, "2026-11-04T02:30:00Z")[0] == \
        "NCAAB_2026-11-03_kansas-state_kentucky"


def test_no_match_outside_the_window_or_for_an_unresolved_side():
    assert nt.match_event(GAMES, 96, 2306, "2026-11-08T00:00:00Z") is None
    assert nt.match_event(GAMES, None, 2306, "2026-11-04T00:00:00Z") is None
    assert nt.match_event(GAMES, 96, 96, "2026-11-04T00:00:00Z") is None


def test_a_rematch_inside_the_window_goes_to_the_nearer_tip_and_a_tie_to_nothing():
    games = [
        {"game_id": "A", "game_date": "2027-03-12", "commence_time": "2027-03-12T23:00:00Z",
         "home_espn_id": 1, "away_espn_id": 2},
        {"game_id": "B", "game_date": "2027-03-13", "commence_time": "2027-03-13T23:00:00Z",
         "home_espn_id": 2, "away_espn_id": 1},
    ]
    assert nt.match_event(games, 2, 1, "2027-03-13T22:00:00Z") == ("B", False)
    tie = [dict(games[0]), dict(games[0], game_id="C")]
    assert nt.match_event(tie, 1, 2, "2027-03-12T23:00:00Z") is None


class _Conn:
    def __init__(self, teams, events):
        self.teams, self.events = teams, events

    def execute(self, sql, params=()):
        self.sql = sql
        return self

    def fetchall(self):
        if "FROM ncaab_teams" in self.sql:
            return self.teams
        return self.events

    def rollback(self):
        pass


def test_the_resolver_joins_feed_names_to_scheduled_games():
    nt.reset_registry_cache()
    conn = _Conn(
        teams=[(150, "Duke", "duke", "Blue Devils", "Duke Blue Devils", "Duke", "DUKE", True, None),
               (2305, "Kansas", "kansas", "Jayhawks", "Kansas Jayhawks", "Kansas", "KU", True, None)],
        events=[("NCAAB_2026-11-25_duke_kansas", "2026-11-25", "2026-11-26T00:00:00Z", 2305, 150)])
    try:
        resolve = nt.make_resolver(conn, "2026-11-25")
        assert resolve("Duke Blue Devils", "Kansas Jayhawks", "2026-11-26T00:00:00Z") == \
            ("NCAAB_2026-11-25_duke_kansas", True)
        assert resolve("Nowhere Tech", "Kansas Jayhawks", "2026-11-26T00:00:00Z") is None
    finally:
        nt.reset_registry_cache()


def test_no_registry_or_no_schedule_means_no_resolver():
    nt.reset_registry_cache()
    try:
        assert nt.make_resolver(_Conn(teams=[], events=[]), "2026-11-25") is None
        nt.reset_registry_cache()
        conn = _Conn(teams=[(150, "Duke", "duke", "Blue Devils", "Duke Blue Devils",
                             "Duke", "DUKE", True, None)], events=[])
        assert nt.make_resolver(conn, "2026-11-25") is None
    finally:
        nt.reset_registry_cache()

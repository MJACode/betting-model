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


def test_an_empty_registry_read_is_not_cached():
    """A worker job that looks before the ESPN backfill creates the table must
    not leave the empty answer behind for every later job in the process."""
    nt.reset_registry_cache()
    try:
        empty = _Conn(teams=[], events=[])
        assert nt.load_registry(empty) == []
        filled = _Conn(teams=[(150, "Duke", "duke", "Blue Devils", "Duke Blue Devils",
                               "Duke", "DUKE", True, None)], events=[])
        assert [t["espn_id"] for t in nt.load_registry(filled)] == [150]
        # a filled read IS cached: the next call does not read again
        assert [t["espn_id"] for t in nt.load_registry(empty)] == [150]
    finally:
        nt.reset_registry_cache()


# ── the feed's shortened school names (2026-10-29) ───────────────────────────
#
# The 2026-10-29 history purchase (worker job 805227) kept 137,007 event
# snapshots raw in ncaab_odds_unmatched because 82 feed names placed no team.
# These rows are copied from production ncaab_teams as read on 2026-10-29:
# every team those names belong to, and every row the resolver could weigh
# against them (a school that starts the name, a school or short name equal
# to one of its spellings). On every name below the answer is the same as on
# the full 1,348-row registry.

def _row(espn_id, school, mascot, display, short, abbr, d1):
    return {"espn_id": espn_id, "school": school, "slug": nt.ncaab_slug(school),
            "mascot": mascot, "display_name": display, "short_name": short,
            "abbreviation": abbr, "is_d1": d1, "alt": []}


PRODUCTION_ROWS = [_row(*r) for r in (
    # (espn_id, school, mascot, display_name, short_name, abbreviation, is_d1)
    (8, 'Arkansas', 'Razorbacks', 'Arkansas Razorbacks', 'Arkansas', 'ARK', True),
    (9, 'Arizona State', 'Sun Devils', 'Arizona State Sun Devils', 'Arizona St', 'ASU', True),
    (12, 'Arizona', 'Wildcats', 'Arizona Wildcats', 'Arizona', 'ARIZ', True),
    (16, 'Sacramento State', 'Hornets', 'Sacramento State Hornets', 'Sacramento St', 'SAC', True),
    (21, 'San Diego State', 'Aztecs', 'San Diego State Aztecs', 'San Diego St', 'SDSU', True),
    (23, 'San José State', 'Spartans', 'San José State Spartans', 'San José St', 'SJSU', True),
    (25, 'California', 'Golden Bears', 'California Golden Bears', 'California', 'CAL', True),
    (36, 'Colorado State', 'Rams', 'Colorado State Rams', 'Colorado St', 'CSU', True),
    (38, 'Colorado', 'Buffaloes', 'Colorado Buffaloes', 'Colorado', 'COLO', True),
    (44, 'American University', 'Eagles', 'American University Eagles', 'American', 'AMER', True),
    (45, 'George Washington', 'Revolutionaries', 'George Washington Revolutionaries', 'G Washington', 'GW', True),
    (48, 'Delaware', 'Blue Hens', 'Delaware Blue Hens', 'Delaware', 'DEL', True),
    (52, 'Florida State', 'Seminoles', 'Florida State Seminoles', 'Florida St', 'FSU', True),
    (55, 'Jacksonville State', 'Gamecocks', 'Jacksonville State Gamecocks', 'Jax State', 'JXST', True),
    (57, 'Florida', 'Gators', 'Florida Gators', 'Florida', 'FLA', True),
    (61, 'Georgia', 'Bulldogs', 'Georgia Bulldogs', 'Georgia', 'UGA', True),
    (77, 'Northwestern', 'Wildcats', 'Northwestern Wildcats', 'Northwestern', 'NU', True),
    (80, 'Chicago', 'Maroons', 'Chicago Maroons', 'Chicago', 'CHI', False),
    (84, 'Indiana', 'Hoosiers', 'Indiana Hoosiers', 'Indiana', 'IU', True),
    (85, 'IU Indianapolis', 'Jaguars', 'IU Indianapolis Jaguars', 'IU Indy', 'IUIN', True),
    (93, 'Murray State', 'Racers', 'Murray State Racers', 'Murray St', 'MUR', True),
    (104, 'Boston University', 'Terriers', 'Boston University Terriers', 'Boston U', 'BU', True),
    (116, "Mount St. Mary's", 'Mountaineers', "Mount St. Mary's Mountaineers", 'Mount St Marys', 'MSM', True),
    (127, 'Michigan State', 'Spartans', 'Michigan State Spartans', 'Michigan St', 'MSU', True),
    (130, 'Michigan', 'Wolverines', 'Michigan Wolverines', 'Michigan', 'MICH', True),
    (140, 'Kansas City', 'Roos', 'Kansas City Roos', 'Kansas City', 'KC', True),
    (142, 'Missouri', 'Tigers', 'Missouri Tigers', 'Missouri', 'MIZ', True),
    (147, 'Montana State', 'Bobcats', 'Montana State Bobcats', 'Montana St', 'MTST', True),
    (149, 'Montana', 'Grizzlies', 'Montana Grizzlies', 'Montana', 'MONT', True),
    (150, 'Duke', 'Blue Devils', 'Duke Blue Devils', 'Duke', 'DUKE', True),
    (155, 'North Dakota', 'Fighting Hawks', 'North Dakota Fighting Hawks', 'North Dakota', 'UND', True),
    (166, 'New Mexico State', 'Aggies', 'New Mexico State Aggies', 'New Mexico St', 'NMSU', True),
    (167, 'New Mexico', 'Lobos', 'New Mexico Lobos', 'New Mexico', 'UNM', True),
    (197, 'Oklahoma State', 'Cowboys', 'Oklahoma State Cowboys', 'Oklahoma St', 'OKST', True),
    (201, 'Oklahoma', 'Sooners', 'Oklahoma Sooners', 'Oklahoma', 'OU', True),
    (204, 'Oregon State', 'Beavers', 'Oregon State Beavers', 'Oregon St', 'ORST', True),
    (233, 'South Dakota', 'Coyotes', 'South Dakota Coyotes', 'South Dakota', 'SDAK', True),
    (245, 'Texas A&M', 'Aggies', 'Texas A&M Aggies', 'Texas A&M', 'TA&M', True),
    (248, 'Houston', 'Cougars', 'Houston Cougars', 'Houston', 'HOU', True),
    (251, 'Texas', 'Longhorns', 'Texas Longhorns', 'Texas', 'TEX', True),
    (264, 'Washington', 'Huskies', 'Washington Huskies', 'Washington', 'WASH', True),
    (265, 'Washington State', 'Cougars', 'Washington State Cougars', 'Washington St', 'WSU', True),
    (278, 'Fresno State', 'Bulldogs', 'Fresno State Bulldogs', 'Fresno St', 'FRES', True),
    (282, 'Indiana State', 'Sycamores', 'Indiana State Sycamores', 'Indiana St', 'INST', True),
    (294, 'Jacksonville', 'Dolphins', 'Jacksonville Dolphins', 'Jacksonville', 'JAX', True),
    (299, 'Long Beach State', 'Beach', 'Long Beach State Beach', 'Long Beach St', 'LBSU', True),
    (301, 'San Diego', 'Toreros', 'San Diego Toreros', 'San Diego', 'USD', True),
    (325, 'Cleveland State', 'Vikings', 'Cleveland State Vikings', 'Cleveland St', 'CLE', True),
    (333, 'Alabama', 'Crimson Tide', 'Alabama Crimson Tide', 'Alabama', 'ALA', True),
    (338, 'Kennesaw State', 'Owls', 'Kennesaw State Owls', 'Kennesaw St', 'KENN', True),
    (344, 'Mississippi State', 'Bulldogs', 'Mississippi State Bulldogs', 'Mississippi St', 'MSST', True),
    (356, 'Illinois', 'Fighting Illini', 'Illinois Fighting Illini', 'Illinois', 'ILL', True),
    (357, 'Texas A&M-Corpus Christi', 'Islanders', 'Texas A&M-Corpus Christi Islanders', 'Texas A&M-CC', 'AMCC', True),
    (399, 'UAlbany', 'Great Danes', 'UAlbany Great Danes', 'UAlbany', 'UALB', True),
    (2011, 'Alabama State', 'Hornets', 'Alabama State Hornets', 'Alabama St', 'ALST', True),
    (2016, 'Alcorn State', 'Braves', 'Alcorn State Braves', 'Alcorn St', 'ALCN', True),
    (2026, 'App State', 'Mountaineers', 'App State Mountaineers', 'App State', 'APP', True),
    (2031, 'Little Rock', 'Trojans', 'Little Rock Trojans', 'Little Rock', 'LR', True),
    (2032, 'Arkansas State', 'Red Wolves', 'Arkansas State Red Wolves', 'Arkansas St', 'ARST', True),
    (2115, 'Central Connecticut', 'Blue Devils', 'Central Connecticut Blue Devils', 'C Connecticut', 'CCSU', True),
    (2130, 'Chicago State', 'Cougars', 'Chicago State Cougars', 'Chicago St', 'CHST', True),
    (2154, 'Coppin State', 'Eagles', 'Coppin State Eagles', 'Coppin St', 'COPP', True),
    (2169, 'Delaware State', 'Hornets', 'Delaware State Hornets', 'Delaware St', 'DSU', True),
    (2193, 'East Tennessee State', 'Buccaneers', 'East Tennessee State Buccaneers', 'ETSU', 'ETSU', True),
    (2229, 'Florida International', 'Panthers', 'Florida International Panthers', 'FIU', 'FIU', True),
    (2239, 'Cal State Fullerton', 'Titans', 'Cal State Fullerton Titans', 'Fullerton', 'CSUF', True),
    (2247, 'Georgia State', 'Panthers', 'Georgia State Panthers', 'Georgia St', 'GAST', True),
    (2253, 'Grand Canyon', 'Lopes', 'Grand Canyon Lopes', 'Grand Canyon', 'GCU', True),
    (2277, 'Houston Christian', 'Huskies', 'Houston Christian Huskies', 'Hou Christian', 'HCU', True),
    (2287, 'Illinois State', 'Redbirds', 'Illinois State Redbirds', 'Illinois St', 'ILST', True),
    (2296, 'Jackson State', 'Tigers', 'Jackson State Tigers', 'Jackson St', 'JKST', True),
    (2305, 'Kansas', 'Jayhawks', 'Kansas Jayhawks', 'Kansas', 'KU', True),
    (2306, 'Kansas State', 'Wildcats', 'Kansas State Wildcats', 'Kansas St', 'KSU', True),
    (2350, 'Loyola Chicago', 'Ramblers', 'Loyola Chicago Ramblers', 'Loyola Chicago', 'LUC', True),
    (2352, 'Loyola Maryland', 'Greyhounds', 'Loyola Maryland Greyhounds', 'Loyola MD', 'L-MD', True),
    (2377, 'McNeese', 'Cowboys', 'McNeese Cowboys', 'McNeese', 'MCN', True),
    (2400, 'Mississippi Valley State', 'Delta Devils', 'Mississippi Valley State Delta Devils', 'Miss Valley St', 'MVSU', True),
    (2413, 'Morehead State', 'Eagles', 'Morehead State Eagles', 'Morehead St', 'MORE', True),
    (2415, 'Morgan State', 'Bears', 'Morgan State Bears', 'Morgan St', 'MORG', True),
    (2443, 'LSU New Orleans', 'Privateers', 'LSU New Orleans Privateers', 'LSU N Orleans', 'NOLA', True),
    (2449, 'North Dakota State', 'Bison', 'North Dakota State Bison', 'N Dakota St', 'NDSU', True),
    (2450, 'Norfolk State', 'Spartans', 'Norfolk State Spartans', 'Norfolk St', 'NORF', True),
    (2458, 'Northern Colorado', 'Bears', 'Northern Colorado Bears', 'N Colorado', 'UNCO', True),
    (2463, 'Cal State Northridge', 'Matadors', 'Cal State Northridge Matadors', 'CSU Northridge', 'CSUN', True),
    (2466, 'Northwestern State', 'Demons', 'Northwestern State Demons', "N'Western St", 'NWST', True),
    (2483, 'Oregon', 'Ducks', 'Oregon Ducks', 'Oregon', 'ORE', True),
    (2501, 'Portland', 'Pilots', 'Portland Pilots', 'Portland', 'PORT', True),
    (2502, 'Portland State', 'Vikings', 'Portland State Vikings', 'Portland St', 'PRST', True),
    (2504, 'Prairie View A&M', 'Panthers', 'Prairie View A&M Panthers', 'Prairie View', 'PV', True),
    (2546, 'Southeast Missouri State', 'Redhawks', 'Southeast Missouri State Redhawks', 'SE Missouri', 'SEMO', True),
    (2547, 'Seattle U', 'Redhawks', 'Seattle U Redhawks', 'Seattle U', 'SEA', True),
    (2569, 'South Carolina State', 'Bulldogs', 'South Carolina State Bulldogs', 'SC State', 'SCST', True),
    (2571, 'South Dakota State', 'Jackrabbits', 'South Dakota State Jackrabbits', 'S Dakota St', 'SDST', True),
    (2579, 'South Carolina', 'Gamecocks', 'South Carolina Gamecocks', 'South Carolina', 'SC', True),
    (2597, 'St. Francis Brooklyn', 'Terriers', 'St. Francis Brooklyn Terriers', 'St Francis BK', 'SFBK', False),
    (2598, 'Saint Francis', 'Red Wolves', 'Saint Francis Red Wolves', 'Saint Francis', 'SFPA', False),
    (2623, 'Missouri State', 'Bears', 'Missouri State Bears', 'Missouri St', 'MOST', True),
    (2630, 'UT Martin', 'Skyhawks', 'UT Martin Skyhawks', 'UT Martin', 'UTM', True),
    (2633, 'Tennessee', 'Volunteers', 'Tennessee Volunteers', 'Tennessee', 'TENN', True),
    (2634, 'Tennessee State', 'Tigers', 'Tennessee State Tigers', 'Tennessee St', 'TNST', True),
    (2674, 'Valparaiso', 'Beacons', 'Valparaiso Beacons', 'Valparaiso', 'VAL', True),
    (2714, 'Western State Colorado University', 'Mountaineers', 'Western State Colorado University Mountaineers', 'Western St.', 'WCK', False),
    (2724, 'Wichita State', 'Shockers', 'Wichita State Shockers', 'Wichita St', 'WICH', True),
    (2750, 'Wright State', 'Raiders', 'Wright State Raiders', 'Wright St', 'WRST', True),
    (2754, 'Youngstown State', 'Penguins', 'Youngstown State Penguins', 'Youngstown St', 'YSU', True),
    (2837, 'East Texas A&M', 'Lions', 'East Texas A&M Lions', 'East Texas A&M', 'ETAM', True),
    (2856, 'California Baptist', 'Lancers', 'California Baptist Lancers', 'CA Baptist', 'CBU', True),
    (2870, 'Purdue Fort Wayne', 'Mastodons', 'Purdue Fort Wayne Mastodons', 'Purdue FW', 'PFW', True),
    (2934, 'Cal State Bakersfield', 'Roadrunners', 'Cal State Bakersfield Roadrunners', 'Bakersfield', 'CSUB', True),
    (3101, 'Utah Tech', 'Trailblazers', 'Utah Tech Trailblazers', 'Utah Tech', 'UTU', True),
    (6446, 'LIU Brooklyn', 'Liu Brooklyn', 'LIU Brooklyn Liu Brooklyn', 'Liu Brooklyn', None, False),
    (111926, 'Regent', 'Royals', 'Regent Royals', 'Regent', 'RGNT', False),
    (112358, 'Long Island University', 'Sharks', 'Long Island University Sharks', 'Long Island', 'LIU', True),
    (112694, 'Western Colorado', 'Mountaineers', 'Western Colorado Mountaineers', 'W Colorado', 'WCOL', False),
    (131784, 'Regent', 'Regent Royals', 'Regent Regent Royals', 'Regent', 'RGNT', False),
    (134850, 'Wright State - Lake', 'Lakers', 'Wright State - Lake Lakers', 'Wright State -', 'WRI', False),
)]

# Each feed name the purchase could not place -> the ESPN team ESPN's schedule
# plays it as (its event's other team resolved, ESPN's game on the event's
# date). BY_RULE are placed by the shortened-school rule, BY_OVERRIDE only by
# config.NCAAB_ODDS_API_MAP (a renamed school or mascot, or nothing in common).
BY_RULE = [
    ('Alabama St Hornets', 2011),
    ('Alcorn St Braves', 2016),
    ('American Eagles', 44),
    ('Arizona St Sun Devils', 9),
    ('Arkansas St Red Wolves', 2032),
    ('Boston Univ. Terriers', 104),
    ('CSU Bakersfield Roadrunners', 2934),
    ('CSU Fullerton Titans', 2239),
    ('CSU Northridge Matadors', 2463),
    ('Cal Baptist Lancers', 2856),
    ('Chicago St Cougars', 2130),
    ('Cleveland St Vikings', 325),
    ('Colorado St Rams', 36),
    ('Coppin St Eagles', 2154),
    ('Delaware St Hornets', 2169),
    ('East Tennessee St Buccaneers', 2193),
    ("Florida Int'l Golden Panthers", 2229),
    ('Florida St Seminoles', 52),
    ('Fresno St Bulldogs', 278),
    ('Georgia St Panthers', 2247),
    ('Grand Canyon Antelopes', 2253),
    ('Illinois St Redbirds', 2287),
    ('Indiana St Sycamores', 282),
    ('Jackson St Tigers', 2296),
    ('Jacksonville St Gamecocks', 55),
    ('Kansas St Wildcats', 2306),
    ('Kennesaw St Owls', 338),
    ('Loyola (Chi) Ramblers', 2350),
    ('Loyola (MD) Greyhounds', 2352),
    ('Michigan St Spartans', 127),
    ('Miss Valley St Delta Devils', 2400),
    ('Mississippi St Bulldogs', 344),
    ('Missouri St Bears', 2623),
    ('Montana St Bobcats', 147),
    ('Morehead St Eagles', 2413),
    ('Morgan St Bears', 2415),
    ("Mt. St. Mary's Mountaineers", 116),
    ('Murray St Racers', 93),
    ('N Colorado Bears', 2458),
    ('New Mexico St Aggies', 166),
    ('Norfolk St Spartans', 2450),
    ('North Dakota St Bison', 2449),
    ('Northwestern St Demons', 2466),
    ('Oklahoma St Cowboys', 197),
    ('Oregon St Beavers', 204),
    ('Portland St Vikings', 2502),
    ('Prairie View Panthers', 2504),
    ('SE Missouri St Redhawks', 2546),
    ('Sacramento St Hornets', 16),
    ('San Diego St Aztecs', 21),
    ('San José St Spartans', 23),
    ('South Carolina St Bulldogs', 2569),
    ('South Dakota St Jackrabbits', 2571),
    ('St. Francis BKN Terriers', 2597),
    ('Tennessee St Tigers', 2634),
    ('Texas A&M-CC Islanders', 357),
    ('Washington St Cougars', 265),
    ('Wichita St Shockers', 2724),
    ('Wright St Raiders', 2750),
    ('Youngstown St Penguins', 2754),
]
BY_OVERRIDE = [
    ('Albany Great Danes', 399),
    ('Appalachian St Mountaineers', 2026),
    ('Arkansas-Little Rock Trojans', 2031),
    ('Dixie State Trailblazers', 3101),
    ('Fort Wayne Mastodons', 2870),
    ('GW Revolutionaries', 45),
    ('George Washington Colonials', 45),
    ('Houston Baptist Huskies', 2277),
    ('IUPUI Jaguars', 85),
    ('LIU Brooklyn Blackbirds', 112358),
    ('LIU Sharks', 112358),
    ('Long Beach St 49ers', 299),
    ('Mcneese St Mcneese', 2377),
    ('New Orleans Privateers', 2443),
    ('Seattle Redhawks', 2547),
    ('St. Francis (PA) Red Flash', 2598),
    ('Tenn-Martin Skyhawks', 2630),
    ('Texas A&M-Commerce Lions', 2837),
    ('UMKC Kangaroos', 140),
    ('Valparaiso Crusaders', 2674),
]


@pytest.mark.parametrize("name,espn_id", BY_RULE + BY_OVERRIDE)
def test_every_name_the_purchase_could_not_place_now_resolves(name, espn_id):
    assert nt.resolve_team_name(name, PRODUCTION_ROWS) == espn_id


@pytest.mark.parametrize("name,espn_id", BY_RULE)
def test_the_shortened_school_rule_places_these_without_an_override(monkeypatch, name, espn_id):
    monkeypatch.setattr(config, "NCAAB_ODDS_API_MAP", {})
    assert nt.resolve_team_name(name, PRODUCTION_ROWS) == espn_id


@pytest.mark.parametrize("name,espn_id", BY_OVERRIDE)
def test_a_renamed_school_resolves_only_through_its_override(monkeypatch, name, espn_id):
    """No rule places these, so none can land on the school the name starts
    with: "LIU Brooklyn Blackbirds" is ESPN 112358, never 6446 'LIU Brooklyn';
    "Arkansas-Little Rock" is not Arkansas (8), "Houston Baptist" not Houston
    (248), "Tenn-Martin" not Tennessee (2633), "Texas A&M-Commerce" neither
    Texas A&M (245) nor Texas (251)."""
    assert config.NCAAB_ODDS_API_MAP.get(name) == espn_id
    monkeypatch.setattr(config, "NCAAB_ODDS_API_MAP", {})
    assert nt.resolve_team_name(name, PRODUCTION_ROWS) is None


def test_every_override_is_an_espn_id_in_the_registry():
    ids = {r["espn_id"] for r in PRODUCTION_ROWS}
    assert config.NCAAB_ODDS_API_MAP, "the override map is empty"
    for name, espn_id in config.NCAAB_ODDS_API_MAP.items():
        assert isinstance(espn_id, int) and espn_id in ids, name


def test_the_two_ambiguous_feed_names_still_resolve_to_nothing():
    # two 'Regent' rows (111926 Royals, 131784 'Regent Royals'); two Colorado
    # Mountaineers (2714, 112694), neither of them the feed's school
    assert nt.resolve_team_name("Regent University Royals", PRODUCTION_ROWS) is None
    assert nt.resolve_team_name("Western State Colorado Mountaineers", PRODUCTION_ROWS) is None


def test_a_school_and_mascot_two_teams_share_resolves_to_nothing():
    twin = _row(990001, "Alabama State College", "Hornets", "Alabama State College Hornets",
                "Alabama St", None, False)
    assert nt.resolve_team_name("Alabama St Hornets", PRODUCTION_ROWS + [twin]) is None


def test_a_spelling_two_teams_share_is_skipped_when_only_one_carries_the_mascot():
    # 'Wright State' is 2750's school AND 134850's short name ('Wright State -');
    # the short name 'Wright St' is 2750's alone, and only 2750 are the Raiders
    assert nt.resolve_team_name("Wright St Raiders", PRODUCTION_ROWS) == 2750


def test_a_name_that_resolved_before_keeps_its_team_where_the_new_rule_disagrees():
    """The new rule runs LAST. 'Central Connecticut St Blue Devils' has always
    resolved to 2115 through the school prefix. On a registry that also holds
    a 'Central Connecticut State', the new rule ALONE would answer that team;
    the full resolver must still answer 2115."""
    other = _row(990002, "Central Connecticut State", "Blue Devils",
                 "Central Connecticut State Blue Devils", None, None, False)
    reg = PRODUCTION_ROWS + [other]
    name = "Central Connecticut St Blue Devils"
    assert nt._resolve_shortened_school(nt._fold(name), reg) == 990002
    assert nt.resolve_team_name(name, reg) == 2115
    assert nt.resolve_team_name("Kansas State Wildcats", reg) == 2306
    assert nt.resolve_team_name("Duke Blue Devils", reg) == 150


def test_a_mascot_alias_belongs_to_its_own_team_only():
    assert nt.resolve_team_name("Grand Canyon Antelopes", PRODUCTION_ROWS) == 2253
    assert nt.resolve_team_name("Florida Int'l Golden Panthers", PRODUCTION_ROWS) == 2229
    # Kansas State are not Antelopes: the alias is Grand Canyon's, not the word's
    assert nt.resolve_team_name("Kansas St Antelopes", PRODUCTION_ROWS) is None

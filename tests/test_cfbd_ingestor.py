"""
Pure-parser tests for the CFBD (NCAAF) ingestor.

No network, no DB — these pin the transform layer so that when the backfill
runs against a real key it either works or fails in one isolated, obvious
place. Fixtures use BOTH camelCase and snake_case key spellings because the
exact CFBD field names could not be confirmed from the dev sandbox; the
parsers read through _pick(), which accepts either.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.cfbd_ingestor import (  # noqa: E402
    _local_aggregates, _possession_seconds, _split_ratio,
    build_ncaaf_game_id, ncaaf_season_for_date, ncaaf_slug,
    parse_advanced_stats, parse_games, parse_lines, parse_ratings,
    parse_returning, parse_talent, parse_team_game_stats, parse_teams,
    shrink_to_prior,
)


# ── Identity / season conventions ─────────────────────────────────────────────

@pytest.mark.parametrize("school,expected", [
    ("Ohio State", "ohio-state"),
    ("Miami (OH)", "miami-oh"),
    ("Texas A&M", "texas-a-m"),
    ("San José State", "san-jose-state"),
    ("UL Monroe", "ul-monroe"),
])
def test_slug(school, expected):
    assert ncaaf_slug(school) == expected


def test_game_id_uses_slugs_not_raw_names():
    gid = build_ncaaf_game_id("2025-09-06", "Miami (OH)", "Texas A&M")
    assert gid == "NCAAF_2025-09-06_miami-oh_texas-a-m"
    assert " " not in gid


def test_january_games_belong_to_the_prior_season():
    """The load-bearing season footgun: a January bowl is the PRIOR season."""
    assert ncaaf_season_for_date("2026-01-19") == 2025
    assert ncaaf_season_for_date("2026-02-01") == 2025
    assert ncaaf_season_for_date("2025-08-30") == 2025
    assert ncaaf_season_for_date("2025-11-29") == 2025


# ── Prior shrinkage ───────────────────────────────────────────────────────────

def test_shrinkage_weights_prior_heavily_early_and_fades_late():
    early = shrink_to_prior(in_season=10.0, prior=0.0, games_played=0, k=4)
    mid   = shrink_to_prior(in_season=10.0, prior=0.0, games_played=4, k=4)
    late  = shrink_to_prior(in_season=10.0, prior=0.0, games_played=12, k=4)
    assert early == 0.0            # no games played → all prior
    assert mid == pytest.approx(5.0)   # k games played → half and half
    assert late > mid                  # converges toward the in-season value
    assert late < 10.0


def test_shrinkage_returns_whichever_side_exists():
    assert shrink_to_prior(None, 3.0, 5) == 3.0
    assert shrink_to_prior(7.0, None, 5) == 7.0
    assert shrink_to_prior(None, None, 5) is None


# ── Games ─────────────────────────────────────────────────────────────────────

_GAMES = [
    {"id": 401, "season": 2025, "week": 2, "seasonType": "regular",
     "startDate": "2025-09-06T16:00:00.000Z", "homeTeam": "Ohio State",
     "awayTeam": "Michigan", "homePoints": 31, "awayPoints": 17,
     "neutralSite": False, "conferenceGame": True, "completed": True,
     "homeClassification": "fbs", "awayClassification": "fbs"},
    {"id": 402, "season": 2025, "week": 2, "season_type": "regular",
     "start_date": "2025-09-06T20:00:00.000Z", "home_team": "Alabama",
     "away_team": "Mercer", "home_points": None, "away_points": None,
     "neutral_site": True, "conference_game": False, "completed": False,
     "home_classification": "fbs", "away_classification": "fcs"},
]


def test_parse_games_handles_both_key_spellings_and_unplayed_games():
    rows = parse_games(_GAMES)
    assert len(rows) == 2
    a, b = rows
    assert a["game_id"] == "NCAAF_2025-09-06_michigan_ohio-state"
    assert (a["home_score"], a["away_score"], a["home_win"]) == (31.0, 17.0, 1)
    assert (a["week"], a["neutral_site"], a["conference_game"]) == (2, 0, 1)
    # snake_case fixture parses identically; an unplayed game keeps NULL scores
    assert b["home_team"] == "Alabama"
    assert b["home_score"] is None and b["home_win"] is None
    assert b["neutral_site"] == 1
    assert b["_away_classification"] == "fcs"


def test_parse_games_skips_rows_without_a_start_date():
    assert parse_games([{"homeTeam": "A", "awayTeam": "B"}]) == []


def test_parse_games_leaves_home_win_null_on_a_tie():
    rows = parse_games([{**_GAMES[0], "homePoints": 21, "awayPoints": 21}])
    assert rows[0]["home_win"] is None


# ── Lines (the reason this sport is buildable) ────────────────────────────────

_LINES = [{
    "startDate": "2025-09-06T16:00:00.000Z",
    "homeTeam": "Ohio State", "awayTeam": "Michigan",
    "lines": [
        {"provider": "Bovada", "spread": -6.5, "overUnder": 51.5},
        {"provider": "consensus", "spread": -7.0, "overUnder": 52.5,
         "homeMoneyline": -280, "awayMoneyline": 230,
         "overPrice": -110, "underPrice": -110},
    ],
}]


def test_parse_lines_selects_the_configured_provider_and_all_three_markets():
    rows = parse_lines(_LINES, "consensus")
    by_market = {r["market"]: r for r in rows}
    assert set(by_market) == {"spreads", "totals", "h2h"}
    # spread is HOME-relative and is NOT sign-flipped — settlement grades
    # margin + spread_home, so a home favourite must stay negative.
    assert by_market["spreads"]["spread_home"] == -7.0
    assert by_market["totals"]["total_line"] == 52.5
    assert by_market["h2h"]["home_price"] == -280
    assert all(r["bookmaker"] == "cfbd_consensus" for r in rows)
    # snapshot_at is the game date → unambiguously pre-game for the archive
    assert all(r["snapshot_at"] == "2025-09-06" for r in rows)


def test_parse_lines_ignores_other_providers():
    assert parse_lines(_LINES, "DraftKings") == []


def test_parse_lines_emits_only_the_markets_present():
    payload = [{**_LINES[0], "lines": [{"provider": "consensus", "spread": -3.5}]}]
    rows = parse_lines(payload, "consensus")
    assert [r["market"] for r in rows] == ["spreads"]


# ── Box scores ────────────────────────────────────────────────────────────────

_TEAM_GAMES = [{
    "id": 401,
    "teams": [
        {"school": "Ohio State", "homeAway": "home", "points": 31, "stats": [
            {"category": "totalYards", "stat": "455"},
            {"category": "rushingYards", "stat": "180"},
            {"category": "netPassingYards", "stat": "275"},
            {"category": "totalPlays", "stat": "68"},
            {"category": "possessionTime", "stat": "31:24"},
            {"category": "thirdDownEff", "stat": "7-13"},
            {"category": "totalPenaltiesYards", "stat": "5-45"},
            {"category": "turnovers", "stat": "1"},
            {"category": "sacks", "stat": "3"},
        ]},
        {"school": "Michigan", "homeAway": "away", "points": 17, "stats": [
            {"category": "totalYards", "stat": "310"},
            {"category": "totalPlays", "stat": "62"},
            {"category": "turnovers", "stat": "2"},
        ]},
    ],
}]

_ID_MAP = {401: "NCAAF_2025-09-06_michigan_ohio-state"}
_META = {"NCAAF_2025-09-06_michigan_ohio-state": {
    "season": 2025, "week": 2, "season_type": "regular",
    "game_date": "2025-09-06", "neutral_site": 0, "conference_game": 1}}


def test_parse_team_game_stats_builds_one_row_per_team():
    rows = parse_team_game_stats(_TEAM_GAMES, _ID_MAP, _META)
    assert len(rows) == 2
    home = next(r for r in rows if r["team"] == "Ohio State")
    assert home["opponent"] == "Michigan"
    assert (home["points"], home["points_allowed"]) == (31, 17)
    assert home["total_yards"] == 455
    assert home["plays"] == 68
    assert home["possession_seconds"] == 31 * 60 + 24
    assert (home["third_down_conv"], home["third_down_att"]) == (7, 13)
    assert (home["penalties"], home["penalty_yards"]) == (5, 45)
    assert home["is_home"] == 1
    assert home["season"] == 2025 and home["week"] == 2


def test_parse_team_game_stats_skips_games_missing_from_the_id_map():
    assert parse_team_game_stats(_TEAM_GAMES, {}, _META) == []


@pytest.mark.parametrize("raw,expected", [("7-13", (7, 13)), ("", (None, None)),
                                          (None, (None, None)), ("junk", (None, None))])
def test_split_ratio(raw, expected):
    assert _split_ratio(raw) == expected


@pytest.mark.parametrize("raw,expected", [("31:24", 1884), (600, 600), (None, None)])
def test_possession_seconds(raw, expected):
    assert _possession_seconds(raw) == expected


# ── Ratings / talent / advanced ───────────────────────────────────────────────

def test_parse_ratings_sp_srs_elo():
    sp = parse_ratings([{"team": "Georgia", "rating": 28.4,
                         "offense": {"rating": 40.1}, "defense": {"rating": 11.7},
                         "specialTeams": {"rating": 0.9}}], "sp")
    assert sp["Georgia"]["sp_overall"] == 28.4
    assert sp["Georgia"]["sp_defense"] == 11.7
    assert parse_ratings([{"team": "Georgia", "rating": 19.2}], "srs")["Georgia"]["srs"] == 19.2
    assert parse_ratings([{"team": "Georgia", "elo": 2100}], "elo")["Georgia"]["elo"] == 2100


def test_parse_talent_and_returning():
    assert parse_talent([{"school": "Georgia", "talent": 985.2}])["Georgia"] == 985.2
    assert parse_returning([{"team": "Georgia", "totalPPA": 412.5}])["Georgia"] == 412.5


def test_parse_advanced_stats_flattens_offense_and_defense():
    adv = parse_advanced_stats([{
        "team": "Georgia",
        "offense": {"ppa": 0.21, "successRate": 0.47, "explosiveness": 1.32,
                    "havoc": {"total": 0.14}, "fieldPosition": {"averageStart": 30.2}},
        "defense": {"ppa": -0.05, "successRate": 0.36, "explosiveness": 1.05,
                    "havoc": {"total": 0.21}, "fieldPosition": {"averageStart": 26.1}},
    }])["Georgia"]
    assert adv["epa_per_play_off"] == 0.21
    assert adv["epa_per_play_def"] == -0.05
    assert adv["success_rate_off"] == 0.47
    assert adv["havoc_rate"] == 0.21          # havoc_rate = the DEFENSE's havoc
    assert adv["explosiveness_def"] == 1.05


# ── Local aggregates (the leak boundary) ──────────────────────────────────────

_LOG = [
    {"team": "Ohio State", "week": 1, "game_date": "2025-08-30", "points": 40,
     "points_allowed": 10, "plays": 70, "possession_seconds": 1800,
     "third_down_conv": 8, "third_down_att": 14, "turnovers": 0},
    {"team": "Ohio State", "week": 2, "game_date": "2025-09-06", "points": 31,
     "points_allowed": 17, "plays": 68, "possession_seconds": 1884,
     "third_down_conv": 7, "third_down_att": 13, "turnovers": 1},
]


def test_local_aggregates_computes_season_to_date_form():
    agg = _local_aggregates(_LOG)["Ohio State"]
    assert agg["games_played"] == 2
    assert agg["points_per_game"] == pytest.approx(35.5)
    assert agg["points_allowed_pg"] == pytest.approx(13.5)
    assert agg["point_differential"] == pytest.approx(22.0)
    assert agg["plays_per_game"] == pytest.approx(69.0)
    assert agg["third_down_rate_off"] == pytest.approx(15 / 27, abs=1e-4)
    assert (agg["wins"], agg["losses"]) == (2, 0)


def test_local_aggregates_does_no_date_filtering_of_its_own():
    """
    The caller owns the leak boundary — passing only prior weeks must be the
    ONLY thing that limits the window, so there is one place to get it wrong.
    """
    agg = _local_aggregates([r for r in _LOG if r["week"] < 2])["Ohio State"]
    assert agg["games_played"] == 1
    assert agg["points_per_game"] == pytest.approx(40.0)


def test_parse_teams_joins_alt_names():
    rows = parse_teams([{"school": "Miami", "mascot": "Hurricanes",
                         "conference": "ACC", "abbreviation": "MIA",
                         "alt_name1": "Miami (FL)", "altName2": "The U"}])
    assert rows[0]["school"] == "Miami"
    assert "Miami (FL)" in rows[0]["alt_names"]
    assert rows[0]["classification"] == "fbs"


# ── Odds API name resolution ──────────────────────────────────────────────────

@pytest.fixture
def schools(monkeypatch):
    """Seed the school cache directly so the resolver needs no DB."""
    from data.ingestors import cfbd_ingestor as cf
    monkeypatch.setattr(cf, "_SCHOOL_CACHE", [
        {"school": "Ohio State", "mascot": "Buckeyes", "alt": []},
        {"school": "Miami", "mascot": "Hurricanes", "alt": ["Miami (FL)"]},
        {"school": "Miami (OH)", "mascot": "RedHawks", "alt": []},
        {"school": "Texas", "mascot": "Longhorns", "alt": []},
        {"school": "Texas A&M", "mascot": "Aggies", "alt": []},
    ])
    return cf


def test_resolver_strips_the_mascot(schools):
    assert schools.resolve_odds_api_school("Ohio State Buckeyes") == "Ohio State"


def test_resolver_accepts_a_bare_school_name(schools):
    assert schools.resolve_odds_api_school("Texas") == "Texas"


def test_resolver_prefers_the_longest_matching_school(schools):
    """'Texas A&M Aggies' must not collapse to 'Texas'."""
    assert schools.resolve_odds_api_school("Texas A&M Aggies") == "Texas A&M"


def test_resolver_distinguishes_the_two_miamis(schools):
    assert schools.resolve_odds_api_school("Miami (OH) RedHawks") == "Miami (OH)"
    assert schools.resolve_odds_api_school("Miami Hurricanes") == "Miami"


def test_resolver_uses_alt_names(schools):
    assert schools.resolve_odds_api_school("Miami (FL)") == "Miami"


def test_resolver_config_override_wins(schools, monkeypatch):
    import config
    monkeypatch.setattr(config, "NCAAF_ODDS_API_MAP", {"Miami Hurricanes": "Miami (OH)"})
    assert schools.resolve_odds_api_school("Miami Hurricanes") == "Miami (OH)"


def test_resolver_falls_back_to_the_input_unchanged(schools):
    """
    An unresolved name must pass through, not guess: the resulting game_id then
    simply won't match a stats row and the scorer skips the game — far safer
    than silently attaching odds to the wrong team.
    """
    assert schools.resolve_odds_api_school("Directional State Aardvarks") == \
        "Directional State Aardvarks"


def test_resolver_is_identity_when_the_registry_is_empty(monkeypatch):
    from data.ingestors import cfbd_ingestor as cf
    monkeypatch.setattr(cf, "_SCHOOL_CACHE", [])
    assert cf.resolve_odds_api_school("Ohio State Buckeyes") == "Ohio State Buckeyes"


# ── Snapshot assembly ─────────────────────────────────────────────────────────

def test_day_before_is_the_snapshot_leak_boundary():
    from data.ingestors.cfbd_ingestor import _day_before
    assert _day_before("2025-09-06") == "2025-09-05"
    assert _day_before("2025-01-01") == "2024-12-31"


def test_stat_row_shrinks_toward_the_prior_and_keeps_ratings_prior_season():
    from data.ingestors.cfbd_ingestor import _stat_row
    prior = {"sp_overall": 20.0, "talent": 900.0,
             "_prior_adv": {"epa_per_play_off": 0.10}}
    row = _stat_row("Ohio State", 2025, "2025-09-05", gp=4,
                    prior=prior, adv={"epa_per_play_off": 0.30},
                    local={"points_per_game": 35.0, "wins": 4, "losses": 0},
                    elo={"Ohio State": {"elo": 2100}},
                    team_meta={"conference": "Big Ten", "classification": "fbs"})
    # ratings are the PRIOR season's, held constant (current-season SP+ would
    # be computed from the very games we are predicting)
    assert row["sp_overall"] == 20.0
    assert row["elo"] == 2100          # ...except Elo, which is week-indexed
    # 4 games at k=4 → half in-season, half prior
    assert row["epa_per_play_off"] == pytest.approx(0.20)
    assert row["wins"] == 4
    assert row["conference"] == "Big Ten"


def test_preseason_row_carries_prior_only():
    from data.ingestors.cfbd_ingestor import _stat_row
    row = _stat_row("Ohio State", 2025, "2025-08-01", gp=0,
                    prior={"sp_overall": 20.0, "_prior_adv": {"epa_per_play_off": 0.10}},
                    adv={}, local={}, elo={}, team_meta={})
    assert row["games_played"] == 0
    assert row["epa_per_play_off"] == 0.10   # entirely the prior — week 1 is usable


def test_preseason_row_uses_prior_season_scoring_so_week_one_survives_dropna():
    """
    Without a prior-season local fallback the preseason row has no points-per-
    game, and since the training builder drops any row with a null feature,
    EVERY week-1 game (~16% of a season) would vanish from the matrix.
    """
    from data.ingestors.cfbd_ingestor import _stat_row
    row = _stat_row("Ohio State", 2025, "2025-08-01", gp=0,
                    prior={"sp_overall": 20.0, "_prior_adv": {}},
                    adv={}, local={}, elo={}, team_meta={},
                    prior_local={"points_per_game": 34.2, "points_allowed_pg": 17.1,
                                 "plays_per_game": 70.0})
    assert row["points_per_game"] == 34.2
    assert row["points_allowed_pg"] == 17.1
    assert row["plays_per_game"] == 70.0
    assert row["points_last_3"] == 34.2      # no games yet → prior-season rate


def test_in_season_row_blends_prior_and_current_scoring():
    from data.ingestors.cfbd_ingestor import _stat_row
    row = _stat_row("Ohio State", 2025, "2025-09-20", gp=4,
                    prior={"_prior_adv": {}}, adv={},
                    local={"games_played": 4, "points_per_game": 40.0,
                           "points_last_3": 42.0},
                    elo={}, team_meta={},
                    prior_local={"points_per_game": 30.0})
    assert row["points_per_game"] == pytest.approx(35.0)   # k=4 → half and half
    assert row["points_last_3"] == 42.0                    # real form once played

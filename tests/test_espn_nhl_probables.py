"""ESPN NHL probableStartingGoalie overlay — NHL schedule has none.

Measured 2026-09-14: api-web.nhle.com /v1/schedule/now listed 43 games and
zero `probableGoalie` fields. ESPN core competitor.probables carries
`probableStartingGoalie` with status.type `expected` and an athlete $ref.
"""
from __future__ import annotations

from pathlib import Path

from data.ingestors.espn_probables import (
    CORE_NHL_EVENTS_URL,
    fetch_espn_nhl_probables,
    parse_probable,
)
from data.ingestors.odds_ingestor import NHL_ODDS_API_MAP


def test_events_url_is_core_not_site():
    assert "sports.core.api.espn.com" in CORE_NHL_EVENTS_URL
    assert "hockey/leagues/nhl/events" in CORE_NHL_EVENTS_URL
    assert "site.api.espn.com" not in CORE_NHL_EVENTS_URL


def test_parse_probable_joins_display_name_to_our_abbrev():
    """LA Kings / Utah Mammoth: ESPN abbrev is not our id."""
    parsed = parse_probable(
        [{"name": "probableStartingGoalie", "playerId": 5571,
          "status": {"type": "expected"}}],
        {"displayName": "Sergei Bobrovsky", "id": "5571"},
        {"displayName": "Florida Panthers", "abbreviation": "FLA"},
    )
    assert parsed["team"] == "FLA"
    assert parsed["player_name"] == "Sergei Bobrovsky"
    assert parsed["designation"] == "expected"

    kings = parse_probable(
        [{"name": "probableStartingGoalie", "playerId": 1,
          "status": {"type": "confirmed"}}],
        {"displayName": "Darcy Kuemper"},
        {"displayName": "Los Angeles Kings", "abbreviation": "LA", "name": "Kings"},
    )
    assert kings["team"] == "LAK"
    assert kings["designation"] == "confirmed"

    utah = parse_probable(
        [{"name": "probableStartingGoalie", "playerId": 2,
          "status": {"type": "expected"}}],
        {"displayName": "Karel Vejmelka"},
        {"displayName": "Utah Mammoth", "abbreviation": "UTA"},
    )
    assert utah["team"] == "UTA"
    assert "Utah Mammoth" in NHL_ODDS_API_MAP


def test_parse_probable_skips_missing_name_or_slot():
    assert parse_probable([], {"displayName": "X"}, {"displayName": "Boston Bruins"}) is None
    assert parse_probable(
        [{"name": "probableStartingGoalie"}],
        {},
        {"displayName": "Boston Bruins"},
    ) is None


def test_fetch_uses_injected_fetch_and_keys_by_our_abbrev():
    events = "https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events?dates=20260919&limit=50"
    ev_ref = "https://sports.core.api.espn.com/event/1"
    comp_ref = "https://sports.core.api.espn.com/comp/fla"
    team_ref = "https://sports.core.api.espn.com/team/fla"
    ath_ref = "https://sports.core.api.espn.com/ath/5571"
    docs = {
        events: {"items": [{"$ref": ev_ref}]},
        ev_ref: {"competitions": [{"competitors": [{"$ref": comp_ref}]}]},
        comp_ref: {
            "team": {"$ref": team_ref},
            "probables": [{
                "name": "probableStartingGoalie",
                "playerId": 5571,
                "athlete": {"$ref": ath_ref},
                "status": {"type": "expected"},
            }],
        },
        team_ref: {"displayName": "Florida Panthers", "abbreviation": "FLA"},
        ath_ref: {"displayName": "Sergei Bobrovsky", "id": "5571"},
    }

    def fetch(url):
        url = url.replace("http://", "https://")
        if url not in docs:
            raise RuntimeError(f"unexpected fetch: {url}")
        return docs[url]

    out = fetch_espn_nhl_probables("2026-09-19", fetch=fetch)
    assert out["FLA"]["player_name"] == "Sergei Bobrovsky"
    assert out["FLA"]["designation"] == "expected"


def test_fetch_fail_open():
    def boom(url):
        raise RuntimeError("blocked")
    assert fetch_espn_nhl_probables("2026-09-19", fetch=boom) == {}


def test_nhl_stats_ingestor_calls_the_overlay():
    src = Path(__file__).parent.parent.joinpath(
        "data/ingestors/nhl_stats_ingestor.py").read_text(encoding="utf-8")
    assert "fetch_espn_nhl_probables" in src
    assert "espn_probables.get(team_abbrev)" in src

"""NFL ESPN injury ingest: same path as MLB/NHL/WNBA/NBA, with a date stamp.

Measured 2026-09-14 against sports.core.api.espn.com:
  * /v2/sports/football/leagues/nfl/teams listed 32 teams (ARI=22 … WAS=28)
  * /teams/12/injuries returned 200; each injury doc has `date`, `status`,
    `type.description`
  * Statuses seen: Active, Out, Questionable, Doubtful, Injured Reserve
  * site.api.espn.com 403'd from this sandbox (same host the worker lost
    in 2026-08-05), so NFL resolves team ids from core, not site.

Active must never be stored as Out — that was the unmapped default and
would veto healthy players. Doubtful stays Doubtful (the veto's other
key); it used to collapse to Day-To-Day.
"""
from __future__ import annotations

from pathlib import Path

import data.ingestors.injury_ingestor as inj
from config import ESPN_INJURY_URLS, ESPN_NFL_TEAM_IDS, NFL_ODDS_API_MAP


def test_nfl_is_on_the_espn_injury_url_map():
    url = ESPN_INJURY_URLS["NFL"]
    assert "football/leagues/nfl/teams/{team_id}/injuries" in url
    assert set(ESPN_INJURY_URLS) >= {"MLB", "NHL", "WNBA", "NBA", "NFL"}


def test_static_nfl_map_is_32_teams_on_our_abbrevs():
    """Measured core ids, keyed as LA/WAS not ESPN's LAR/WSH."""
    assert len(ESPN_NFL_TEAM_IDS) == 32
    assert ESPN_NFL_TEAM_IDS["LA"] == 14
    assert ESPN_NFL_TEAM_IDS["WAS"] == 28
    assert ESPN_NFL_TEAM_IDS["GB"] == 9
    assert ESPN_NFL_TEAM_IDS["KC"] == 12
    assert "LAR" not in ESPN_NFL_TEAM_IDS
    assert "WSH" not in ESPN_NFL_TEAM_IDS
    ours = set(NFL_ODDS_API_MAP.values())
    assert set(ESPN_NFL_TEAM_IDS) <= ours
    assert set(ESPN_NFL_TEAM_IDS) == {
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
        "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
        "LAC", "LA", "LV", "MIA", "MIN", "NE", "NO", "NYG",
        "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS",
    }


def test_default_injury_run_includes_nfl():
    src = Path(inj.__file__).read_text(encoding="utf-8")
    assert '["MLB", "NHL", "WNBA", "NBA", "NFL"]' in src
    assert '"NFL"' in src.split("choices=")[1].split("]")[0]


def test_doubtful_stays_doubtful_not_day_to_day():
    assert inj.ESPN_STATUS_MAP["Doubtful"] == "Doubtful"
    assert inj.ESPN_STATUS_MAP["doubtful"] == "Doubtful"
    assert inj.SEVERITY_WEIGHTS["Doubtful"] == inj.SEVERITY_WEIGHTS["Day-To-Day"]


def test_injured_reserve_maps_to_out_and_active_does_not():
    assert inj.ESPN_STATUS_MAP["Injured Reserve"] == "Out"
    assert inj.ESPN_STATUS_MAP["Active"] == "Active"
    assert inj.ESPN_STATUS_MAP["active"] == "Active"


def test_nfl_name_join_uses_our_abbrevs_not_espns():
    rams = {"displayName": "Los Angeles Rams", "location": "Los Angeles",
            "name": "Rams", "abbreviation": "LAR"}
    was = {"displayName": "Washington Commanders", "location": "Washington",
           "name": "Commanders", "abbreviation": "WSH"}
    assert inj._nfl_espn_team_to_abbrev(rams) == "LA"
    assert inj._nfl_espn_team_to_abbrev(was) == "WAS"


def _fake_fetch(docs):
    def fetch(url):
        if url not in docs:
            raise RuntimeError(f"unexpected fetch: {url}")
        doc = docs[url]
        if isinstance(doc, Exception):
            raise doc
        return doc
    return fetch


def test_core_nfl_team_ids_resolve_lar_and_wsh_to_ours():
    docs = {
        inj.CORE_NFL_TEAMS_URL: {"items": [
            {"$ref": "http://core/teams/14"},
            {"$ref": "https://core/teams/28"},
        ]},
        "https://core/teams/14": {
            "id": "14", "displayName": "Los Angeles Rams",
            "location": "Los Angeles", "name": "Rams"},
        "https://core/teams/28": {
            "id": "28", "displayName": "Washington Commanders",
            "location": "Washington", "name": "Commanders"},
    }
    resolved = inj._fetch_nfl_espn_team_ids_core(fetch=_fake_fetch(docs))
    assert resolved == {"LA": 14, "WAS": 28}


def test_core_nfl_listing_failure_returns_empty():
    docs = {inj.CORE_NFL_TEAMS_URL: RuntimeError("403")}
    assert inj._fetch_nfl_espn_team_ids_core(fetch=_fake_fetch(docs)) == {}


def test_nfl_active_rows_are_dropped_and_out_keeps_espn_date(monkeypatch):
    monkeypatch.setattr(inj, "_espn_team_ids", lambda sport: {"CIN": 4})
    monkeypatch.setattr(inj, "_seed_athlete_cache", lambda: 0)
    monkeypatch.setattr(inj, "_fetch_espn_team_injuries", lambda sport, ab, tid: [
        {"player_name": "Ja'Marr Chase", "player_id": "1",
         "raw_status": "Out", "injury_type": "out",
         "status_ts": "2026-09-13T18:14Z"},
        {"player_name": "Joe Burrow", "player_id": "2",
         "raw_status": "Active", "injury_type": "active",
         "status_ts": "2026-09-12T19:46Z"},
        {"player_name": "Tee Higgins", "player_id": "3",
         "raw_status": "Doubtful", "injury_type": "doubtful",
         "status_ts": "2026-09-13T13:41Z"},
    ])
    rows = inj.fetch_espn_injuries("NFL", "2026-09-14")
    names = {r["player_name"]: r for r in rows}
    assert "Joe Burrow" not in names
    assert names["Ja'Marr Chase"]["status"] == "Out"
    assert names["Ja'Marr Chase"]["status_ts"] == "2026-09-13T18:14Z"
    assert names["Tee Higgins"]["status"] == "Doubtful"


def test_injury_fetch_raises_the_page_limit():
    """Without limit=200 NFL's 50-70 row lists lose Out/Doubtful on page 2."""
    src = Path(inj.__file__).read_text(encoding="utf-8")
    assert "limit=200" in src


def test_upsert_writes_status_ts():
    src = Path(inj.__file__).read_text(encoding="utf-8")
    assert "status_ts" in src
    assert "%(status_ts)s" in src

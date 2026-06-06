"""Pure-function tests for the live odds ingestor event-matching (no network)."""

from data.ingestors.live_odds_ingestor import _event_to_game_id


def _event(commence, home, away, eid="evt1"):
    return {"id": eid, "commence_time": commence, "home_team": home, "away_team": away}


def test_event_to_game_id_matches_our_format():
    # 2026-06-06 23:05 UTC → 7:05pm ET, still 2026-06-06 ET
    ev = _event("2026-06-06T23:05:00Z", "Boston Red Sox", "New York Yankees")
    gid = _event_to_game_id(ev)
    assert gid == "MLB_2026-06-06_NYY_BOS"


def test_event_to_game_id_uses_eastern_date():
    # 2026-06-07 02:10 UTC is still 2026-06-06 in ET (10:10pm)
    ev = _event("2026-06-07T02:10:00Z", "Los Angeles Dodgers", "San Diego Padres")
    gid = _event_to_game_id(ev)
    assert gid == "MLB_2026-06-06_SD_LAD"


def test_event_to_game_id_bad_commence_returns_none():
    ev = _event("not-a-timestamp", "Boston Red Sox", "New York Yankees")
    assert _event_to_game_id(ev) is None


def test_event_to_game_id_unknown_team_uses_fuzzy_fallback():
    # _normalize_team falls back to a fuzzy 3-letter abbrev for unknown names,
    # so a game_id is still produced — it just won't match a real game in our DB.
    ev = _event("2026-06-06T23:05:00Z", "Nonexistent Club", "New York Yankees")
    gid = _event_to_game_id(ev)
    assert gid is not None and gid.startswith("MLB_2026-06-06_NYY_")

"""Matchup links on Discord pick posts.

The link is markdown in the embed field value. Discord does not link a field
name or an embed title, and a bare URL in message content would unfurl a
preview, so the URL stays inside the masked link.

Resolution is pure here: a fake scoreboard stands in for ESPN. Nothing in
this file calls the network.
"""
from __future__ import annotations

import pytest

from tracking import discord_notifier as dn
from tracking import score_links as sl


@pytest.fixture(autouse=True)
def _fresh_cache():
    sl.clear_cache()
    yield
    sl.clear_cache()


def _ncaab(**over):
    base = {
        "lock_key": "NCAAB_2026-11-16_louisville_uconn:ncaab_total",
        "label": "UConn @ Louisville under 122.5",
        "sport": "NCAAB", "model_id": "ncaab_total",
        "home": "Louisville", "away": "UConn",
        "game_date": "2026-11-16",
        "commence": "2026-11-17T00:00:00+00:00",
        "dk_odds": -110.0, "kelly": 0.02,
    }
    base.update(over)
    return base


def _board(event_id, home, away, *, extra=None):
    events = [{
        "id": event_id,
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "team": home},
                {"homeAway": "away", "team": away},
            ],
        }],
    }]
    if extra:
        events.append(extra)
    return {"events": events}


def _louis():
    return {"abbreviation": "LOU", "location": "Louisville",
            "displayName": "Louisville Cardinals"}


def _uconn():
    return {"abbreviation": "CONN", "location": "UConn",
            "displayName": "UConn Huskies"}


def test_a_stored_event_id_is_the_gamecast_and_the_label_stays_plain():
    sig = _ncaab(espn_event_id="401000001")
    field = dn._signal_field(sig)
    assert field["name"] == "UConn @ Louisville under 122.5"
    assert field["value"].split("\n")[0].startswith(
        "[UConn @ Louisville](https://www.espn.com/mens-college-basketball/"
        "game/_/gameId/401000001)")
    assert " · " in field["value"].split("\n")[0]


def test_no_event_id_falls_back_to_the_sport_scoreboard():
    field = dn._signal_field(_ncaab())
    line = field["value"].split("\n")[0]
    assert line.startswith(
        "[UConn @ Louisville](https://www.espn.com/mens-college-basketball/"
        "scoreboard/_/date/20261116)")
    assert "/game/" not in line


def test_a_scoreboard_match_replaces_the_fallback_and_is_cached():
    calls = []

    def fetch(sport, day, timeout):
        calls.append((sport, day, timeout))
        assert timeout > 0
        assert timeout <= 0.8
        return _board("401918949", _louis(), _uconn())

    one = _ncaab()
    two = _ncaab(label="UConn @ Louisville -3.5",
                 lock_key="NCAAB_2026-11-16_louisville_uconn:ncaab_spread")
    sl.attach([one, two], fetch=fetch)
    assert calls == [("NCAAB", "20261116", calls[0][2])]
    game = ("https://www.espn.com/mens-college-basketball/game/"
            "_/gameId/401918949")
    assert one["score_url"] == game
    assert two["score_url"] == game
    sl.attach([_ncaab()], fetch=fetch)
    assert len(calls) == 1, "a second batch for the same board must not fetch"


def test_two_matching_games_stay_on_the_scoreboard():
    def fetch(sport, day, timeout):
        return _board("401918949", _louis(), _uconn(), extra={
            "id": "401918950",
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": _louis()},
                    {"homeAway": "away", "team": _uconn()},
                ],
            }],
        })

    sig = _ncaab()
    sl.attach([sig], fetch=fetch)
    assert sig["score_url"].endswith("/scoreboard/_/date/20261116")
    assert "gameId" not in sig["score_url"]


def test_a_failed_lookup_posts_the_scoreboard_and_does_not_raise():
    def fetch(sport, day, timeout):
        raise TimeoutError("timed out")

    sig = _ncaab()
    sl.attach([sig], fetch=fetch)
    assert sig["score_url"].endswith("/scoreboard/_/date/20261116")
    field = dn._signal_field(sig)
    assert field["name"] == "UConn @ Louisville under 122.5"
    assert "scoreboard/_/date/20261116" in field["value"]


def test_an_http_miss_is_cached_so_the_next_post_does_not_wait():
    calls = []

    def fetch(sport, day, timeout):
        calls.append(1)
        return None

    sl.attach([_ncaab()], fetch=fetch)
    sl.attach([_ncaab()], fetch=fetch)
    assert calls == [1]


def test_a_stored_row_is_used_and_the_network_is_not():
    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params
            return self

        def fetchone(self):
            if "to_regclass" in self.sql and self.params == ("public.ncaab_events",):
                return ("ncaab_events",)
            return None

        def fetchall(self):
            if "FROM ncaab_events" in self.sql:
                return [("NCAAB_2026-11-16_louisville_uconn", "401918949")]
            return []

    def fetch(*_a, **_k):
        raise AssertionError("stored id must not hit the network")

    sig = _ncaab()
    sl.attach([sig], Conn(), fetch=fetch)
    assert sig["score_url"].endswith("/game/_/gameId/401918949")


def test_a_bad_stored_id_cannot_become_a_url():
    assert sl.game_url("NCAAB", "401918949');drop") is None
    assert sl.game_url("NCAAB", "not-an-id") is None
    assert sl.game_url("NCAAB", "12") is None
    assert sl.mask("UConn @ Louisville", "https://evil.example/game") == \
        "UConn @ Louisville"


def test_mlb_accepts_espn_abbreviations_that_are_not_ours():
    payload = _board("401000111",
                     {"abbreviation": "CHW", "displayName": "Chicago White Sox"},
                     {"abbreviation": "NYY", "displayName": "New York Yankees"})
    events = sl.parse_events("MLB", payload)
    assert sl.match_event("MLB", "CWS", "NYY", events) == "401000111"
    assert sl.game_url("MLB", "401000111") == \
        "https://www.espn.com/mlb/game/_/gameId/401000111"


def test_euroleague_uses_the_league_page_from_our_game_id():
    def fetch(*_a, **_k):
        raise AssertionError("euroleague id is already on the row")

    sig = {"sport": "EUROLEAGUE", "game_id": "EUROLEAGUE_E2025_294",
           "home": "PAN", "away": "MAD", "game_date": "2026-01-10",
           "label": "MAD @ PAN -3.5"}
    sl.attach([sig], fetch=fetch)
    assert sig["score_url"] == (
        "https://www.euroleaguebasketball.net/euroleague/game-center/"
        "?gamecode=294&seasoncode=E2025")


def test_ufc_falls_back_to_ufcstats_without_a_fetch():
    def fetch(*_a, **_k):
        raise AssertionError("ufc has no espn id to look up")

    sig = {"sport": "UFC", "home": "Fighter B", "away": "Fighter A",
           "game_date": "2026-11-16", "label": "Fighter A vs Fighter B"}
    sl.attach([sig], fetch=fetch)
    assert sig["score_url"] == "http://ufcstats.com/statistics/events/upcoming"
    field = dn._signal_field(sig)
    assert field["value"].split("\n")[0].startswith(
        "[Fighter A vs Fighter B](http://ufcstats.com/statistics/events/upcoming)")


def test_tennis_matches_on_player_names_and_golf_uses_the_leaderboard():
    payload = {"events": [{"id": "189-2026", "groupings": [{"competitions": [{
        "id": "401234567",
        "competitors": [
            {"athlete": {"displayName": "Jannik Sinner"}},
            {"athlete": {"displayName": "Carlos Alcaraz"}},
        ],
    }]}]}]}
    events = sl.parse_events("ATP", payload)
    assert sl.match_event("ATP", "Carlos Alcaraz", "Jannik Sinner", events) == \
        "401234567"
    assert sl.game_url("ATP", "401234567") == \
        "https://www.espn.com/tennis/match/_/gameId/401234567"
    assert sl.scoreboard_url("ATP", "2026-11-16") == \
        "https://www.espn.com/tennis/scoreboard/_/date/20261116"
    assert sl.scoreboard_url("GOLF", None) == \
        "https://www.espn.com/golf/leaderboard"


def test_parentheses_in_the_matchup_stay_plain_text():
    sig = _ncaab(home="Miami (OH)", away="Dayton", espn_event_id="401918949",
                 label="Dayton @ Miami (OH) under 140.5")
    field = dn._signal_field(sig)
    assert field["value"].split("\n")[0].startswith("Dayton @ Miami (OH)")
    assert "](" not in field["value"].split("\n")[0]


def test_a_lookup_that_blows_up_does_not_drop_the_pick():
    class Conn:
        def execute(self, sql, params=None):
            if "to_regclass" in sql:
                raise RuntimeError("relation missing")
            return self

        def fetchone(self):
            return None

        def fetchall(self):
            return []

    sig = _ncaab()
    other = _ncaab(lock_key="other:ncaab_total", label="other")
    sl.attach([sig, other], Conn(), fetch=lambda *_a, **_k: None)
    assert sig["lock_key"].endswith(":ncaab_total")
    assert other["label"] == "other"
    assert sig["score_url"].endswith("/scoreboard/_/date/20261116")


def test_the_post_keeps_the_link_inside_the_embed_field(monkeypatch):
    """No message content, so Discord has no bare URL to unfurl. The title
    is plain. The matchup link is the field value."""
    seen = {}

    def _post(_url, payload):
        seen.update(payload)
        return "m1"

    nfl = {
        "label": "NYJ @ MIA Under 47.5", "sport": "NFL",
        "home": "MIA", "away": "NYJ", "game_date": "2026-11-16",
        "commence": "2026-11-16T18:00:00+00:00",
        "dk_odds": -110.0, "kelly": 0.02,
        "espn_event_id": "401000002",
    }
    monkeypatch.setattr(dn, "_post", _post)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    dn._post_picks("http://hook.example/not-a-secret", "NFL", [nfl],
                   "2026-11-16")
    assert "content" not in seen
    assert "](http" not in seen["embeds"][0]["title"]
    value = seen["embeds"][0]["fields"][0]["value"]
    assert value.split("\n")[0].startswith(
        "[NYJ @ MIA](https://www.espn.com/nfl/game/_/gameId/401000002)")
    # The webhook URL is not part of the body.
    assert "hook.example" not in value


def test_nfl_and_ncaab_examples_render_the_matchup_as_the_link():
    """The two lines the pull request quotes. Field name is the pick.
    Field value leads with the linked matchup."""
    ncaab = dn._signal_field(_ncaab(espn_event_id="401000001"))
    nfl = dn._signal_field({
        "label": "NYJ @ MIA Under 47.5", "sport": "NFL",
        "home": "MIA", "away": "NYJ", "game_date": "2026-11-16",
        "commence": "2026-11-16T18:00:00+00:00",
        "dk_odds": -110.0, "kelly": 0.02, "espn_event_id": "401000002",
    })
    assert ncaab["value"].split("\n")[0].startswith(
        "[UConn @ Louisville](https://www.espn.com/mens-college-basketball/"
        "game/_/gameId/401000001) · ")
    assert nfl["value"].split("\n")[0].startswith(
        "[NYJ @ MIA](https://www.espn.com/nfl/game/_/gameId/401000002) · ")
    assert nfl["name"] == "NYJ @ MIA Under 47.5"

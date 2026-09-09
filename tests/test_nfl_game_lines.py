"""The NFL game-line ingest resolves onto the schedule and never invents a game.

WHY THIS FILE EXISTS. Adding "NFL" to `odds_ingestor.SPORT_KEYS` is one line and
it is a trap. `_build_game_id` mints `NFL_2026-09-09_NE_SEA` from the date and
the two abbrevs; the real row, written by the nflverse schedule, is
`NFL_2026_01_NE_SEA` -- season and week. Let the ingestor upsert games for the
NFL and every slate grows sixteen phantom rows carrying odds no pick, no settle
and no board will ever join to, which is the `mlb_phantom_utc_rows_2026_09_07`
shape arrived at deliberately.

The measured state that made this necessary (2026-09-09, the season opener):
`odds` held `spreads` from `draftkings` and nothing else for every NFL game in
the week, against h2h + spreads + totals across 14 books for MLB and NCAAF.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.ingestors.odds_ingestor as oi


SEA_NE = {
    "id": "evt1",
    "commence_time": "2026-09-10T00:20:00Z",   # 8:20pm ET on the 9th
    "home_team": "Seattle Seahawks",
    "away_team": "New England Patriots",
    "bookmakers": [
        {
            "key": "draftkings",
            "markets": [
                {"key": "h2h", "last_update": "2026-09-09T21:00:00Z",
                 "outcomes": [{"name": "Seattle Seahawks", "price": -150},
                              {"name": "New England Patriots", "price": 130}]},
                {"key": "totals", "last_update": "2026-09-09T21:00:00Z",
                 "outcomes": [{"name": "Over", "price": -110, "point": 43.5},
                              {"name": "Under", "price": -110, "point": 43.5}]},
            ],
        },
        {
            "key": "fanduel",
            "markets": [
                {"key": "h2h", "last_update": "2026-09-09T21:00:00Z",
                 "outcomes": [{"name": "Seattle Seahawks", "price": -148},
                              {"name": "New England Patriots", "price": 126}]},
            ],
        },
    ],
}

REAL_GAME_ID = "NFL_2026_01_NE_SEA"


def _resolver(hits=None):
    """Stands in for the schedule. Returns the real id for SEA-NE only."""
    hits = {("Seattle Seahawks", "New England Patriots")} if hits is None else hits

    def resolve(home_name, away_name, commence_time):
        return REAL_GAME_ID if (home_name, away_name) in hits else None

    return resolve


class TestNflResolvesOntoTheSchedule:
    def test_the_sport_is_pulled_at_all(self):
        """The whole point: NFL had no entry, so no h2h and no totals existed."""
        assert oi.SPORT_KEYS.get("NFL") == "americanfootball_nfl"

    def test_odds_carry_the_scheduled_game_id_not_a_minted_one(self):
        _, odds = oi._process_events([SEA_NE], "NFL", "open", "2026-09-09T21:00:00Z",
                                     resolve_game_id=_resolver())
        assert odds, "no odds rows produced"
        assert {r["game_id"] for r in odds} == {REAL_GAME_ID}
        # The id this file would have invented, spelled out so the test fails
        # loudly rather than on a set comparison nobody reads.
        minted = oi._build_game_id("NFL", "2026-09-09", "NE", "SEA")
        assert minted != REAL_GAME_ID
        assert all(r["game_id"] != minted for r in odds)

    def test_it_writes_no_games_row_for_the_nfl(self):
        games, odds = oi._process_events([SEA_NE], "NFL", "open", "2026-09-09T21:00:00Z",
                                         resolve_game_id=_resolver())
        assert games == [], f"the NFL schedule is not ours to write: {games}"
        assert odds

    def test_an_unresolvable_event_is_dropped_whole(self):
        """Not filed under an invented id, and not half-written either."""
        games, odds = oi._process_events([SEA_NE], "NFL", "open", "2026-09-09T21:00:00Z",
                                         resolve_game_id=_resolver(hits=set()))
        assert games == []
        assert odds == []

    def test_both_missing_markets_come_through(self):
        """h2h and totals are what the NFL never had; spreads it already had."""
        _, odds = oi._process_events([SEA_NE], "NFL", "open", "2026-09-09T21:00:00Z",
                                     resolve_game_id=_resolver())
        assert {r["market"] for r in odds} >= {"h2h", "totals"}

    def test_line_shop_books_come_through_not_just_draftkings(self):
        _, odds = oi._process_events([SEA_NE], "NFL", "open", "2026-09-09T21:00:00Z",
                                     resolve_game_id=_resolver())
        assert {r["bookmaker"] for r in odds} >= {"draftkings", "fanduel"}

    def test_team_names_resolve_to_our_abbrevs(self):
        assert oi._normalize_team("Seattle Seahawks", "NFL") == "SEA"
        assert oi._normalize_team("New England Patriots", "NFL") == "NE"


class TestEveryOtherSportStillMintsItsOwn:
    """The resolver is opt-in. For MLB and the rest this ingestor IS the
    schedule, so removing their games row would empty the board."""

    def test_mlb_still_writes_its_games_row(self):
        event = dict(SEA_NE)
        event = {**event,
                 "home_team": "Seattle Mariners",
                 "away_team": "Boston Red Sox",
                 "bookmakers": [SEA_NE["bookmakers"][0]]}
        # The h2h outcome names have to match for the price to land, but the
        # games row is written regardless and that is what this asserts.
        games, _ = oi._process_events([event], "MLB", "open", "2026-09-09T21:00:00Z")
        assert len(games) == 1
        assert games[0]["game_id"].startswith("MLB_")
        assert games[0]["sport"] == "MLB"


class TestTheResolverFailsClosed:
    def test_no_schedule_means_no_resolver_rather_than_a_fallback(self, monkeypatch):
        """A resolver we could not build is not permission to invent games."""
        class _Conn:
            def execute(self, *a, **k):
                raise RuntimeError("no database")

        assert oi._nfl_resolver(_Conn(), "2026-09-09") is None

    def test_an_empty_schedule_window_also_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            "data.ingestors.nfl_prop_odds_ingestor._load_nfl_games",
            lambda conn, start, end: {},
        )
        assert oi._nfl_resolver(object(), "2026-09-09") is None

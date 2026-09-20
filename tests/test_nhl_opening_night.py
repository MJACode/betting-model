"""
Four defects, all measured 2026-09-20, nine days before the first NHL game this
pipeline would ever score (docs/nhl_market_research.md §1). Each test below
was run against the code as it stood and FAILED before the fix went in.

1. The 2026-27 season opens 2026-09-29. `month >= 10` filed 09-29/30 under
   season 2026 and the rest of opening week under 2027.
2. The odds feed sends 'Montréal Canadiens' and 'St Louis Blues'; the name map
   holds 'Montreal' and 'St. Louis', and the fallback invented CAN and BLU.
3. The goalie summary carries `playerId` and no `goalieId` key, so an empty id
   matched the first row and every starter got one goalie's numbers.
4. The regulation 3-way line was requested under OUR market name. The feed's
   key is `h2h_3_way`; ours, in `odds.market`, stays `h2h_3way`.
"""
from __future__ import annotations

import pytest


class TestSeasonLabel:
    @pytest.mark.parametrize("game_date, season", [
        ("2026-09-29", 2027),   # opening night 2026-27
        ("2026-09-30", 2027),
        ("2026-10-01", 2027),
        ("2027-04-10", 2027),   # last day of the regular season
        ("2027-06-10", 2027),   # playoffs
        ("2021-07-07", 2021),   # the latest a season has ever ended
        ("2020-09-28", 2020),   # bubble Cup final: a September that is NOT new
        ("2025-10-07", 2026),
    ])
    def test_a_date_maps_to_its_ending_year(self, game_date, season):
        from data.season_labels import nhl_season_label
        assert nhl_season_label(game_date) == season

    def test_opening_week_is_one_season(self):
        from data.season_labels import nhl_season_label
        week = ["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-03"]
        assert len({nhl_season_label(d) for d in week}) == 1

    def test_no_nhl_call_site_still_derives_the_label_from_october(self):
        """The rule lived in four places; a fifth would bring the bug back."""
        import io
        import re
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent
        offenders = []
        for rel in ("run_pipeline.py", "data/ingestors/odds_ingestor.py",
                    "data/ingestors/nhl_stats_ingestor.py"):
            lines = io.open(repo / rel, encoding="utf-8").read().splitlines()
            for n, text in enumerate(lines, 1):
                # The NBA really does open in October; only its own line may say so.
                if re.search(r"month\s*>=\s*10", text) and (
                        "NHL" in text or '"NBA"' not in text):
                    offenders.append(f"{rel}:{n}")
        assert offenders == []


class TestOddsFeedTeamNames:
    @pytest.mark.parametrize("feed_name, team", [
        ("Montréal Canadiens", "MTL"),      # as logged by the worker
        ("Montreal Canadiens", "MTL"),
        ("St Louis Blues", "STL"),          # as logged by the worker
        ("St. Louis Blues", "STL"),
        ("Utah Mammoth", "UTA"),
    ])
    def test_the_feeds_spelling_resolves(self, feed_name, team):
        from data.ingestors.odds_ingestor import _normalize_team
        assert _normalize_team(feed_name, "NHL") == team

    def test_every_mapped_name_still_maps_to_itself(self):
        from data.ingestors.odds_ingestor import NHL_ODDS_API_MAP, _normalize_team
        for name, team in NHL_ODDS_API_MAP.items():
            assert _normalize_team(name, "NHL") == team


class TestGoalieLookup:
    SUMMARY = [   # the API's shape: `playerId`, `teamAbbrevs`, NO `goalieId`
        {"playerId": 1, "goalieFullName": "Worst Goalie", "teamAbbrevs": "SJS",
         "gamesPlayed": 2, "savePct": 0.7143, "goalsAgainstAverage": 8.8999},
        {"playerId": 8476883, "goalieFullName": "Andrei Vasilevskiy",
         "teamAbbrevs": "TBL", "gamesPlayed": 63, "savePct": 0.9213,
         "goalsAgainstAverage": 2.18},
        {"playerId": 8480280, "goalieFullName": "Jeremy Swayman",
         "teamAbbrevs": "BOS", "gamesPlayed": 58, "savePct": 0.8921,
         "goalsAgainstAverage": 3.1145},
        {"playerId": 2, "goalieFullName": "Boston Backup", "teamAbbrevs": "NYR, BOS",
         "gamesPlayed": 20, "savePct": 0.9, "goalsAgainstAverage": 2.9},
    ]

    def _rows(self, monkeypatch, probables):
        from data.ingestors import nhl_stats_ingestor as ni
        from data.ingestors import espn_probables as ep

        monkeypatch.setattr(ni, "_fetch_goalie_season_stats", lambda s: self.SUMMARY)
        monkeypatch.setattr(ni, "_fetch_today_schedule", lambda d: [
            {"homeTeam": {"abbrev": "BOS"}, "awayTeam": {"abbrev": "TBL"}}])
        monkeypatch.setattr(ep, "fetch_espn_nhl_probables", lambda d: probables)

        # The NUMBERS come from the per-game log (data/nhl_asof.py); the season
        # summary only names the goalie. Swayman .900 on 300 shots last season,
        # Vasilevskiy .930, the backup busier THIS season than either.
        from data.nhl_asof import GoalieBook

        def g(pid, name, team, d, season, sa, ga):
            return {"nhl_game_id": hash((pid, d)) % 10**9, "player_id": pid,
                    "player_name": name, "game_id": f"NHL_{d}_X_{team}", "season": season,
                    "game_date": d, "team": team, "started": 1, "toi_seconds": 3600,
                    "shots_against": sa, "goals_against": ga}
        log = ([g(8480280, "Jeremy Swayman", "BOS", f"2026-01-{d:02d}", 2026, 30, 3)
                for d in range(1, 11)]
               + [g(8476883, "Andrei Vasilevskiy", "TBL", f"2026-01-{d:02d}", 2026, 30, 2)
                  for d in range(1, 11)])
        monkeypatch.setattr(ni, "_goalie_book", lambda conn, season: GoalieBook(log))

        class _Conn:
            def execute(self, *a, **k):
                return self

            def fetchone(self):
                return None

        return {r["team"]: r for r in ni._build_goalie_rows(2027, "2026-09-29", _Conn())}

    def test_two_starters_get_their_own_numbers(self, monkeypatch):
        rows = self._rows(monkeypatch, {
            "BOS": {"player_name": "Jeremy Swayman"},
            "TBL": {"player_name": "Andrei Vasilevskiy"}})
        assert rows["TBL"]["save_pct"] > rows["BOS"]["save_pct"]
        assert rows["BOS"]["gsaa"] == 0 and rows["TBL"]["gsaa"] == 0   # new season
        assert rows["BOS"]["gsaa"] != rows["BOS"]["gaa"], "GSAA was a copy of GAA"
        assert rows["BOS"]["player_id"] == "8480280"
        assert rows["TBL"]["player_id"] == "8476883"

    def test_an_unknown_starter_reads_as_league_average_not_as_the_first_row(self, monkeypatch):
        rows = self._rows(monkeypatch, {"BOS": {"player_name": "Rookie Callup"},
                                        "TBL": {"player_name": "Andrei Vasilevskiy"}})
        # A debut reads as the league's rate — the same for anyone unknown, and
        # never the numbers of whichever goalie the API happened to list first.
        assert rows["BOS"]["player_id"] is None
        assert rows["BOS"]["save_pct"] == pytest.approx(
            550 / 600, abs=1e-3)                # league: 600 shots, 50 goals
        assert rows["BOS"]["save_pct"] != pytest.approx(0.7143)

    def test_with_no_probable_the_team_falls_back_to_its_busiest_goalie(self, monkeypatch):
        rows = self._rows(monkeypatch, {})
        assert rows["BOS"]["player_name"] == "Jeremy Swayman"   # the goalie BOS has used
        assert rows["TBL"]["player_name"] == "Andrei Vasilevskiy"

    def test_accents_do_not_break_the_name_match(self):
        from data.ingestors.nhl_stats_ingestor import _same_goalie_name
        assert _same_goalie_name("Juuse Saros", "juuse saros")
        assert _same_goalie_name("Jakub Dobeš", "Jakub Dobes")
        assert not _same_goalie_name("", "")


class TestThreeWayMarketKey:
    def test_the_feed_is_asked_under_its_key_and_rows_are_stored_under_ours(
            self, monkeypatch):
        from data.ingestors import odds_ingestor as oi

        asked = []
        monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
        monkeypatch.setattr(oi, "_list_events", lambda sk: [{"id": "ev0"}])

        def fake_event_odds(sport_key, event_id, markets, *a, **k):
            asked.extend(markets)
            return {
                "id": "ev0", "commence_time": "2026-09-29T23:10:00Z",
                "home_team": "Toronto Maple Leafs", "away_team": "Montréal Canadiens",
                "bookmakers": [{"key": "draftkings", "markets": [{
                    "key": "h2h_3_way", "last_update": "2026-09-29T15:00:00Z",
                    "outcomes": [{"name": "Toronto Maple Leafs", "price": 105},
                                 {"name": "Montréal Canadiens", "price": 240},
                                 {"name": "Draw", "price": 330}]}]}]}

        monkeypatch.setattr(oi, "_get_event_odds", fake_event_odds)
        rows = oi._fetch_nhl_3way_per_event("icehockey_nhl", "open",
                                            "2026-09-29T15:00:00Z")
        assert asked == ["h2h_3_way"], "the feed does not know our name for it"
        assert rows, "the 3-way rows were parsed and then filtered away"
        assert {r["market"] for r in rows} == {"h2h_3way"}
        assert rows[0]["draw_price"] == 330
        assert rows[0]["game_id"] == "NHL_2026-09-29_MTL_TOR"

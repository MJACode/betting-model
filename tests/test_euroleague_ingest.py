"""EuroLeague groundwork: identity, the results parser, the odds resolver, and
the period-market parser (data/ingestors/euroleague_*.py)."""
from __future__ import annotations

import pytest

import config
from data.ingestors import euroleague_api as ea
from data.ingestors import euroleague_period_history as ep
from data.ingestors import euroleague_teams as et
from data.ingestors import odds_ingestor as oi


# ── identity ─────────────────────────────────────────────────────────────────

def test_season_label_is_the_ending_year():
    assert et.season_label("E2024") == 2025
    assert et.season_code(2025) == "E2024"
    with pytest.raises(ValueError):
        et.season_label("2024")


def test_game_id_is_the_league_identifier():
    assert et.build_game_id("E2024_294") == "EUROLEAGUE_E2024_294"
    with pytest.raises(ValueError):
        et.build_game_id("2024-10-03_BER_PAN")


def test_every_feed_name_in_the_census_maps_to_a_club():
    et.reset_registry_cache()
    for name, code in config.EUROLEAGUE_ODDS_API_MAP.items():
        assert et.resolve_team_name(name) == code
    # accent-folded: the feed has written both spellings of these clubs
    assert et.resolve_team_name("Zalgiris") == "ZAL"
    assert et.resolve_team_name("Fenerbahce Beko") == "ULK"
    assert et.resolve_team_name("Besiktas JK") == "BES"


def test_an_unknown_name_resolves_by_a_stored_name_only_when_one_club_matches():
    et.reset_registry_cache()
    reg = [{"code": "TEL", "name": "Maccabi Rapyd Tel Aviv", "names": ["Maccabi Playtika Tel Aviv"]},
           {"code": "HTA", "name": "Hapoel IBI Tel Aviv", "names": []},
           {"code": "BAS", "name": "Kosner Baskonia Vitoria-Gasteiz",
            "names": ["Cazoo Baskonia Vitoria-Gasteiz"]}]
    assert et.resolve_team_name("Kosner Baskonia Vitoria-Gasteiz", reg) == "BAS"
    assert et.resolve_team_name("Baskonia", reg) == "BAS"
    assert et.resolve_team_name("Tel Aviv", reg) is None       # two clubs
    assert et.resolve_team_name("Nowhere BC", reg) is None


GAMES = [
    {"game_id": "EUROLEAGUE_E2025_141", "home_code": "TEL", "away_code": "ASV",
     "commence_time": "2025-12-11T17:00:00+00:00", "game_date": "2025-12-11"},
    {"game_id": "EUROLEAGUE_E2025_250", "home_code": "ASV", "away_code": "TEL",
     "commence_time": "2026-02-20T19:00:00+00:00", "game_date": "2026-02-20"},
]


def test_match_event_places_the_pair_nearest_the_start_and_says_when_flipped():
    assert et.match_event(GAMES, "TEL", "ASV", "2025-12-11T17:00:00Z") == (
        "EUROLEAGUE_E2025_141", False)
    # the feed calling EuroLeague's away club home
    assert et.match_event(GAMES, "ASV", "TEL", "2025-12-11T17:05:00Z") == (
        "EUROLEAGUE_E2025_141", True)
    # the return meeting, months later, is the other game
    assert et.match_event(GAMES, "ASV", "TEL", "2026-02-20T19:00:00Z") == (
        "EUROLEAGUE_E2025_250", False)
    # outside the window: no game, never an invented one
    assert et.match_event(GAMES, "TEL", "ASV", "2025-12-14T17:00:00Z") is None
    assert et.match_event(GAMES, "TEL", "TEL", "2025-12-11T17:00:00Z") is None


def test_the_odds_ingestor_never_mints_a_euroleague_game():
    assert "EUROLEAGUE" in oi.RESOLVE_ONLY_SPORTS
    assert "EUROLEAGUE" in oi.SCHEDULE_RESOLVED_SPORTS
    ev = [{"id": "x", "commence_time": "2025-12-11T17:00:00Z", "home_team": "Maccabi Tel Aviv",
           "away_team": "ASVEL Lyon Villeurbanne", "bookmakers": []}]
    games, rows = oi._process_events(ev, "EUROLEAGUE", "open", "2025-12-11T12:00:00Z")
    assert games == [] and rows == []


def test_a_flipped_event_stores_the_home_clubs_spread():
    resolver = et.Resolver([], GAMES)
    ev = [{"id": "x", "commence_time": "2025-12-11T17:00:00Z",
           "home_team": "ASVEL Lyon Villeurbanne", "away_team": "Maccabi Tel Aviv",
           "bookmakers": [{"key": "pinnacle", "last_update": "2025-12-11T16:00:00Z",
                           "markets": [{"key": "spreads", "last_update": "2025-12-11T16:00:00Z",
                                        "outcomes": [
                                            {"name": "Maccabi Tel Aviv", "price": -110, "point": -7.5},
                                            {"name": "ASVEL Lyon Villeurbanne", "price": -110,
                                             "point": 7.5}]}]}]}]
    games, rows = oi._process_events(ev, "EUROLEAGUE", "open", "2025-12-11T16:05:00Z",
                                     resolve_game_id=resolver)
    assert games == []
    (row,) = [r for r in rows if r["market"] == "spreads"]
    assert row["game_id"] == "EUROLEAGUE_E2025_141"
    assert float(row["spread_home"]) == -7.5           # TEL, EuroLeague's home club


# ── the results parser ───────────────────────────────────────────────────────

def _api_game(**kw):
    g = {"identifier": "E2024_321", "gameCode": 321, "season": {"code": "E2024"},
         "phaseType": {"code": "PO"}, "round": 2, "played": True, "gameStatus": "Confirmed",
         "utcDate": "2025-04-24T18:00:00Z", "localDate": "2025-04-24T21:00:00",
         "isNeutralVenue": False, "audience": 9000, "venue": {"code": "V", "name": "Arena"},
         "referee1": {"name": "A"}, "referee2": {"name": "B"}, "referee3": None,
         "local": {"club": {"code": "PAN", "name": "Panathinaikos"}, "score": 88,
                   "partials": {"partials1": 18, "partials2": 22, "partials3": 21,
                                "partials4": 19, "extraPeriods": {"1": 8}}},
         "road": {"club": {"code": "MAD", "name": "Real Madrid"}, "score": 98,
                  "partials": {"partials1": 20, "partials2": 26, "partials3": 17,
                               "partials4": 17, "extraPeriods": {"1": 18}}}}
    g.update(kw)
    return g


def test_parse_game_reads_quarters_overtime_and_the_label():
    r = ea.parse_game(_api_game())
    assert r["game_id"] == "EUROLEAGUE_E2024_321" and r["season"] == 2025
    assert r["periods"] == [(1, 18, 20), (2, 22, 26), (3, 21, 17), (4, 19, 17), (5, 8, 18)]
    assert ea.results(r) == (0, 1, 1)          # away win, overtime, tied after four
    assert r["referees"] == ["A", "B"]
    assert r["game_date"] == "2025-04-24"


def test_parse_game_refuses_quarters_that_do_not_sum_to_the_score():
    g = _api_game()
    g["local"]["score"] = 87
    with pytest.raises(ValueError):
        ea.parse_game(g)


def test_a_final_four_game_is_neutral_and_a_cancelled_game_is_not_played():
    assert ea.parse_game(_api_game(phaseType={"code": "FF"}))["neutral_site"] is True
    c = ea.parse_game(_api_game(played=False, gameStatus="Cancelled"))
    assert c["played"] is False and ea.results(c) is None


# ── the period-market parser ─────────────────────────────────────────────────

def test_period_parser_keys_spreads_on_the_home_number_and_picks_the_main_rung():
    markets = [
        {"key": "spreads_h1", "last_update": "t", "outcomes": [
            {"name": "Home FC", "price": -110, "point": -3.5},
            {"name": "Away FC", "price": -110, "point": 3.5}]},
        {"key": "totals_q1", "last_update": "t", "outcomes": [
            {"name": "Over", "price": -110, "point": 42.5},
            {"name": "Under", "price": -110, "point": 42.5},
            {"name": "Over", "price": -150, "point": 40.5},
            {"name": "Under", "price": 120, "point": 40.5}]},
        {"key": "team_totals", "last_update": "t", "outcomes": [
            {"name": "Over", "description": "Away FC", "price": -115, "point": 80.5},
            {"name": "Under", "description": "Away FC", "price": -105, "point": 80.5}]},
        {"key": "odd_even_q1", "outcomes": [{"name": "Odd", "price": -110}]},
    ]
    rows = ep.parse_book(markets, "Home FC", "Away FC")
    for r in rows:
        r["bookmaker"] = "fanduel"
    rows = ep.split_main(rows)
    by = {(r["market"], r.get("spread_home") if r.get("spread_home") is not None
           else r.get("total_line")): r for r in rows}
    assert by[("spreads_h1", -3.5)]["home_price"] == -110
    assert ("totals_q1", 42.5) in by and ("totals_q1_alternate", 40.5) in by
    assert ("team_totals_away", 80.5) in by
    assert not any(r["market"].startswith("odd_even") for r in rows)


def test_period_purchase_asks_only_times_before_the_tip_and_skips_done_pairs():
    from datetime import datetime, timezone
    g = {"game_id": "G", "commence_time": "2026-11-06T19:00:00+00:00"}
    now = datetime(2026, 11, 6, 18, 1, tzinfo=timezone.utc)
    todo = ep.plan([g], {("G", "T-1440")}, now)
    marks = [m for _, m, _ in todo]
    assert "T-1440" not in marks                 # done
    assert "T-60" in marks and "T-30" not in marks   # 18:30 is not past at 18:01
    assert all(t < now for _, _, t in todo)


def test_the_chunked_history_runs_newest_season_first_and_newest_chunk_first():
    from datetime import date, datetime, timezone
    from data.ingestors import euroleague_odds_history as eh
    games = [{"season": 2026, "game_date": "2025-10-01"}, {"season": 2026, "game_date": "2025-10-25"},
             {"season": 2027, "game_date": "2026-10-01"}, {"season": 2027, "game_date": "2026-10-20"}]
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    plan = eh.chunk_plan(games, now, 2026, 2027, chunk_days=10)
    assert [s for s, _ in plan] == sorted([s for s, _ in plan], reverse=True)
    first_season = [d for s, d in plan if s == 2027]
    assert first_season[0][-1] == date(2026, 10, 21)          # the season's newest day leads
    assert all(c == sorted(c) for _, c in plan)
    days = [d for _, c in plan for d in c]
    assert len(days) == len(set(days))                        # no day twice
    assert min(d for s, c in plan if s == 2027 for d in c) == date(2026, 9, 21)   # LEAD_DAYS before


def test_the_15_minute_rule_keeps_every_snapshot_near_and_during_games():
    from datetime import datetime, timedelta, timezone
    from data.ingestors import euroleague_odds_history as eh
    Z = timezone.utc
    tips = [datetime(2025, 12, 11, 19, 5, tzinfo=Z), datetime(2025, 12, 11, 20, 0, tzinfo=Z)]
    step = timedelta(minutes=15)
    t = lambda h, m: datetime(2025, 12, 11, h, m, tzinfo=Z)
    # the morning: one every 15 minutes
    assert eh.next_ask(t(9, 0), t(9, 5), tips, step) == t(9, 15)
    # never past the start of the window before the first tip (18:35)
    assert eh.next_ask(t(18, 25), t(18, 30), tips, step) == t(18, 35)
    # inside the window, and while games are in play: every snapshot
    assert eh.next_ask(t(18, 40), t(18, 45), tips, step) == t(18, 45)
    assert eh.next_ask(t(21, 0), t(21, 5), tips, step) == t(21, 5)
    # after the last game's window (22:30): back to 15 minutes
    assert eh.next_ask(t(22, 40), t(22, 45), tips, step) == t(22, 55)
    # no step: every snapshot, as before
    assert eh.next_ask(t(9, 0), t(9, 5), tips, None) == t(9, 5)
    # the asks only move forward, even across a gap in the feed
    assert eh.next_ask(t(9, 0), t(11, 0), tips, step) == t(11, 0)


def test_a_walk_with_the_step_asks_fewer_times_and_keeps_the_close(tmp_path):
    from datetime import date, datetime, timedelta, timezone
    from data.ingestors import euroleague_odds_history as eh
    Z = timezone.utc
    day = date(2025, 12, 11)
    tip = datetime(2025, 12, 11, 19, 5, tzinfo=Z)

    class R:
        status_code = 200
        headers = {"x-requests-last": "30"}

        def __init__(self, body):
            self._b = body

        def json(self):
            return self._b

    class F:
        def __init__(self, r):
            self.response, self.attempts = r, [r]

    asked = []

    def fetch(params):
        a = datetime.fromisoformat(params["date"].replace("Z", "+00:00"))
        asked.append(a)
        ts = a - timedelta(minutes=a.minute % 5, seconds=a.second)      # a snapshot every 5 min
        nxt = ts + timedelta(minutes=5)
        return F(R({"timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "next_timestamp": nxt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "data": [{"id": "e", "commence_time": "2025-12-11T19:05:00Z"}]}))

    eh.walk_day(fetch, tmp_path, day, datetime(2025, 12, 12, 1, tzinfo=Z), [tip],
                timedelta(minutes=15))
    kept = {datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
            for s in eh.read_state(tmp_path, day)["snapshots"]}
    assert eh.read_state(tmp_path, day)["done"]
    assert len(asked) < 288 / 2
    # every 5-minute snapshot from 30 minutes before the tip to 2.5 hours after
    t = tip - timedelta(minutes=30)
    while t <= tip + timedelta(hours=2, minutes=30):
        if t.minute % 5 == 0:
            assert t in kept, t
        t += timedelta(minutes=5)


def test_the_shot_chart_parser_reads_the_wall_clock_and_the_home_score():
    from datetime import datetime, timezone
    from data.ingestors import euroleague_shots as es
    body = {"Rows": [
        {"NUM_ANOT": 89, "TEAM": "ASV       ", "ID_PLAYER": "P002100   ", "PLAYER": "DE COLO, NANDO",
         "ID_ACTION": "2FGM", "POINTS": 2, "COORD_X": -294, "COORD_Y": 313, "ZONE": "D",
         "FASTBREAK": "0", "SECOND_CHANCE": "1", "POINTS_OFF_TURNOVER": "0", "MINUTE": 1,
         "CONSOLE": "09:39", "POINTS_A": 0, "POINTS_B": 2, "UTC": "20251211190842"},
        {"NUM_ANOT": None, "UTC": "x"},
        {"NUM_ANOT": 90, "ID_ACTION": "3FGA", "POINTS": 0, "UTC": "bad"}]}
    rows = es.parse("EUROLEAGUE_E2025_141", body)
    assert len(rows) == 2
    r = dict(zip(es.COLS, rows[0]))
    assert r["shot_utc"] == datetime(2025, 12, 11, 19, 8, 42, tzinfo=timezone.utc)
    assert r["team"] == "ASV" and r["player_id"] == "P002100"
    assert (r["points_home"], r["points_away"]) == (0, 2)       # A is EuroLeague's home club
    assert r["second_chance"] is True and r["fastbreak"] is False
    assert dict(zip(es.COLS, rows[1]))["shot_utc"] is None      # an unreadable stamp is None

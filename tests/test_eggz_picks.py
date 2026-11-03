"""Eggz's channel: parse, cursor, grade, and a recap that stays off #results."""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import eggz_picks as eg  # noqa: E402


def test_a_side_a_spread_a_total_and_a_prop_parse():
    body = "\n".join([
        "NYY @ BOS",
        "NYY -1.5 -110",
        "Over 8.5 -105",
        "Aaron Judge over 1.5 hits -120",
        "2u NYY ML -130",
    ])
    legs, reviews = eg.parse_message(body)
    assert reviews == []
    assert [leg["market"] for leg in legs] == ["spreads", "totals", "prop", "h2h"]
    spread, total, prop, ml = legs
    assert spread["line"] == -1.5 and spread["price"] == -110
    assert spread["team_text"].upper().startswith("NYY")
    assert total["side"] == "over" and total["line"] == 8.5 and total["price"] == -105
    assert total["away_text"] == "NYY" and total["home_text"] == "BOS"
    assert prop["player_name"] == "Aaron Judge"
    assert prop["side"] == "over" and prop["line"] == 1.5
    assert prop["prop_market"] == "batter_hits" and prop["price"] == -120
    assert ml["stake_units"] == 2 and ml["price"] == -130
    assert ml["team_text"].upper().startswith("NYY")


OCT18 = "NHL Sunday Oct. 18\nMIN Wild 60 Minute ML (-110) 1U✅"
OCT20 = (
    "NHL Tuesday Oct. 20\n"
    "All 1U\n"
    "MTL Canadians 60 Minute ML (-130) \n"
    "NY Islanders ML (-155) \n"
    "NJ Devils ML (-120) \n"
    "CBJ Blue Jackets ML (-162) \n"
    "EDM Oilers ML (-135)"
)
_POSTED_OCT18 = datetime(2026, 10, 18, 3, 28, 45, tzinfo=timezone.utc)
_POSTED_OCT20 = datetime(2026, 10, 20, 16, 6, 51, tzinfo=timezone.utc)


def test_the_oct_18_wild_post_is_a_regulation_moneyline():
    legs, reviews = eg.parse_message(OCT18, _POSTED_OCT18)
    assert reviews == []
    assert len(legs) == 1
    leg = legs[0]
    assert leg["market"] == "h2h_3way"
    assert leg["price"] == -110
    assert leg["stake_units"] == 1
    assert leg["team_text"] == "MIN Wild"
    assert leg["sport_hint"] == "NHL"
    assert leg["slate_date"] == "2026-10-18"
    assert "✅" not in leg["team_text"]


def test_the_oct_20_slate_keeps_one_regulation_line_and_four_moneylines():
    legs, reviews = eg.parse_message(OCT20, _POSTED_OCT20)
    assert reviews == []
    assert [leg["market"] for leg in legs] == [
        "h2h_3way", "h2h", "h2h", "h2h", "h2h",
    ]
    assert [leg["price"] for leg in legs] == [-130, -155, -120, -162, -135]
    assert [leg["stake_units"] for leg in legs] == [1, 1, 1, 1, 1]
    assert legs[0]["team_text"] == "MTL Canadians"
    assert [leg["sport_hint"] for leg in legs] == ["NHL"] * 5
    assert [leg["slate_date"] for leg in legs] == ["2026-10-20"] * 5
    assert {leg["team_text"] for leg in legs[1:]} == {
        "NY Islanders", "NJ Devils", "CBJ Blue Jackets", "EDM Oilers",
    }


def test_regulation_wording_and_a_message_stake_do_not_become_reviews():
    posted = _POSTED_OCT20
    for line in ("BOS 60 min ML -150", "BOS Reg ML -150", "BOS 3-way -150",
                 "BOS 3 way ML +120"):
        legs, reviews = eg.parse_message(f"NHL Oct. 20\n{line}", posted)
        assert reviews == [], line
        assert legs[0]["market"] == "h2h_3way", line
        assert legs[0]["team_text"] == "BOS"
    legs, reviews = eg.parse_message(
        "NHL Tuesday Oct. 20\nAll 2U\nEDM Oilers ML -135", posted)
    assert reviews == []
    assert legs[0]["market"] == "h2h"
    assert legs[0]["stake_units"] == 2
    assert legs[0]["price"] == -135


def test_canadians_and_a_one_edit_nickname_resolve_to_montreal():
    hits = eg._teams_in("Canadians")
    assert ("canadians", "NHL", "MTL") in hits
    assert eg._fuzzy_one("Canadien", "NHL") == "MTL"


def test_min_wild_on_the_nhl_slate_is_not_the_nfl_team():
    legs, reviews = eg.parse_message(OCT18, _POSTED_OCT18)
    assert reviews == []
    calls = []

    class Conn:
        def execute(self, sql, params=None):
            calls.append(params)
            self.params = params
            return self

        def fetchall(self):
            sport = self.params[0]
            if sport == "NHL" and "MIN" in self.params and "2026-10-18" in self.params:
                return [(
                    "NHL_2026-10-18_CBJ_MIN", "NHL", "2026-10-18", "MIN", "CBJ",
                    "2026-10-18T22:00:00Z", 2, 1, 1, 1, 0,
                )]
            if sport == "NFL":
                return [(
                    "NFL_2026-10-18_MIN_GB", "NFL", "2026-10-18", "GB", "MIN",
                    "2026-10-18T17:00:00Z", None, None, None, None, 0,
                )]
            return []

        def fetchone(self):
            return None

    game, reason = eg._match_leg(Conn(), legs[0], _POSTED_OCT18)
    assert reason is None
    assert game["game_id"] == "NHL_2026-10-18_CBJ_MIN"
    assert game["side"] == "home"
    assert all(call[0] != "NFL" for call in calls)


def _reg_conn(periods, game, side="home"):
    """Pending 60-minute leg. `game` is the games-table row the grader reads."""
    reviews, graded = [], []

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params
            if "SET status = 'needs_review'" in sql:
                reviews.append(params)
            if sql.startswith("UPDATE capper_picks SET status = 'graded'"):
                graded.append(params)
            return self

        def fetchall(self):
            if "nhl_period_scores" in self.sql:
                return periods
            if "status = 'pending'" in self.sql:
                return [(
                    8, "NHL_2026-10-18_CBJ_MIN", "h2h_3way", side, None, -110, 1,
                    None, None, None, "2026-10-18T22:00:00Z", "NHL",
                )]
            return []

        def fetchone(self):
            if "RETURNING" in self.sql:
                return (1,)
            if "FROM games" in self.sql:
                return game
            return None

        def commit(self):
            pass

    return Conn(), reviews, graded


def test_period_scores_grade_the_side_and_a_tie_is_a_loss():
    # Periods still win when they exist, including over a regulation home win
    # stored on the games row.
    final = (2, 1, 1, 1, 0, "2026-10-18T22:00:00Z", "2026-10-18")
    conn, reviews, graded = _reg_conn([(1, 1, 0, 0, 1, 0)], final)
    assert eg.grade_pending(conn) == 1
    assert reviews == []
    assert graded[0][0] == "WIN"
    assert abs(graded[0][1] - 1.0) < 1e-9

    conn, reviews, graded = _reg_conn([(1, 0, 0, 0, 1, 0)], final)
    assert eg.grade_pending(conn) == 1
    assert graded[0][0] == "LOSS"


def test_an_overtime_game_is_a_loss_for_both_sides_when_period_scores_are_missing():
    # went_to_ot = 1 is a regulation tie. home_win_reg is 0 on those games.
    ot = (3, 2, 1, 0, 1, "2026-10-18T22:00:00Z", "2026-10-18")
    for side in ("home", "away"):
        conn, reviews, graded = _reg_conn([], ot, side)
        assert eg.grade_pending(conn) == 1
        assert reviews == []
        assert graded[0][0] == "LOSS"
        assert abs(graded[0][1] - -1.1) < 1e-9
        assert abs(graded[0][2] - 1.1) < 1e-9


def test_a_regulation_win_comes_from_home_win_reg_when_period_scores_are_missing():
    reg = (2, 1, 1, 1, 0, "2026-10-18T22:00:00Z", "2026-10-18")
    conn, reviews, graded = _reg_conn([], reg, "home")
    assert eg.grade_pending(conn) == 1
    assert reviews == []
    assert graded[0][0] == "WIN"
    assert abs(graded[0][1] - 1.0) < 1e-9
    assert abs(graded[0][2] - 1.1) < 1e-9

    conn, reviews, graded = _reg_conn([], reg, "away")
    assert eg.grade_pending(conn) == 1
    assert graded[0][0] == "LOSS"

    away_reg = (1, 2, 0, 0, 0, "2026-10-18T22:00:00Z", "2026-10-18")
    conn, reviews, graded = _reg_conn([], away_reg, "away")
    assert eg.grade_pending(conn) == 1
    assert graded[0][0] == "WIN"


def test_missing_regulation_fields_stay_needs_review_and_a_live_game_stays_pending():
    commence = "2026-10-18T22:00:00Z"
    for game in (
        (2, 1, 1, None, 0, commence, "2026-10-18"),
        (2, 1, 1, 1, None, commence, "2026-10-18"),
        (2, 1, 1, None, None, commence, "2026-10-18"),
    ):
        conn, reviews, graded = _reg_conn([], game)
        eg.grade_pending(conn)
        assert reviews[0][0] == "no_regulation_score"
        assert graded == []

    # Oct 20 rows stored went_to_ot = 0 before the game was final.
    conn, reviews, graded = _reg_conn(
        [], (None, None, None, None, 0, commence, "2026-10-20"))
    assert eg.grade_pending(conn) == 0
    assert reviews == []
    assert graded == []


def test_period_scores_outrank_an_overtime_flag():
    # Periods say the home side won in regulation. went_to_ot = 1 would have
    # been a loss for both sides. The period row is the grade.
    ot = (3, 2, 1, 0, 1, "2026-10-18T22:00:00Z", "2026-10-18")
    conn, reviews, graded = _reg_conn([(2, 0, 0, 0, 0, 0)], ot, "home")
    assert eg.grade_pending(conn) == 1
    assert reviews == []
    assert graded[0][0] == "WIN"


def test_a_stored_needs_review_message_is_reparsed_and_a_parsed_one_is_not(monkeypatch):
    seen = []
    monkeypatch.setattr(
        eg, "_replace_legs",
        lambda conn, mid, body, posted: seen.append(mid))

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            return self

        def fetchall(self):
            if "FROM capper_messages" in self.sql:
                return [
                    ("old", OCT18, "2026-10-18T03:28:45+00:00", "needs_review"),
                    ("done", "NYY ML -115", "2026-10-20T17:00:00+00:00", "parsed"),
                ]
            return []

        def fetchone(self):
            return None

        def commit(self):
            pass

    assert eg.reparse_stored(Conn()) == 1
    assert seen == ["old"]


def test_a_missing_price_stays_missing_and_the_stake_defaults_to_one():
    legs, reviews = eg.parse_message("NYY ML")
    assert reviews == []
    assert legs[0]["price"] is None
    assert legs[0]["stake_units"] == 1


def test_a_line_that_is_not_a_pick_is_kept_for_review():
    legs, reviews = eg.parse_message("NYY ML -115\nlets ride")
    assert len(legs) == 1
    assert reviews[0]["reason"] == "unparsed"
    assert "lets ride" in reviews[0]["raw"]


def test_an_empty_message_is_not_dropped():
    legs, reviews = eg.parse_message("   ")
    assert legs == []
    assert reviews[0]["reason"] == "empty"


def test_a_total_without_a_game_is_unmatched():
    legs, _ = eg.parse_message("Over 8.5 -110")
    game, reason = eg._match_leg(None, legs[0], datetime.now(timezone.utc))
    assert game is None and reason == "no_matchup"


def test_a_post_after_the_start_is_not_a_bet():
    posted = datetime(2026, 10, 20, 23, 30, tzinfo=timezone.utc)
    game = {"sport": "MLB", "commence": posted - timedelta(minutes=20)}
    chosen, reason = eg.choose_game([game], posted)
    assert chosen is None and reason == "posted_after_start"


def test_two_sports_in_the_window_are_not_a_guess():
    posted = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
    games = [
        {"sport": "MLB", "commence": posted + timedelta(hours=4)},
        {"sport": "NBA", "commence": posted + timedelta(hours=6)},
    ]
    chosen, reason = eg.choose_game(games, posted)
    assert chosen is None and reason == "ambiguous_team"


def test_the_soonest_future_game_is_the_one_that_has_not_started():
    posted = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
    later = {"sport": "MLB", "commence": posted + timedelta(days=2), "game_id": "later"}
    soon = {"sport": "MLB", "commence": posted + timedelta(hours=5), "game_id": "soon"}
    chosen, reason = eg.choose_game([later, soon], posted)
    assert reason is None and chosen["game_id"] == "soon"


def test_an_away_spread_is_stored_as_the_home_number():
    posted = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
    commence = posted + timedelta(hours=5)

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            return self

        def fetchall(self):
            return [(
                "MLB_2026-10-20_NYY_BOS", "MLB", "2026-10-20", "BOS", "NYY",
                commence.isoformat(), None, None, None, None, 0,
            )]

    legs, _ = eg.parse_message("NYY -1.5 -110")
    game, reason = eg._match_leg(Conn(), legs[0], posted)
    assert reason is None
    assert game["side"] == "away"
    assert legs[0]["line"] == 1.5


def test_units_use_the_stated_stake_and_do_not_invent_a_price():
    profit, risked = eg.units_for_result(1, None, "LOSS")
    assert (profit, risked) == (-1.0, 1.0)
    profit, risked = eg.units_for_result(1, -110, "LOSS")
    assert abs(risked - 1.1) < 1e-9
    assert abs(profit - -1.1) < 1e-9
    profit, risked = eg.units_for_result(2, -110, "WIN")
    assert abs(profit - 2.0) < 1e-9
    assert abs(risked - 2.2) < 1e-9
    assert eg.units_for_result(1, -110, "PUSH") == (0.0, 0.0)


def test_the_cursor_moves_past_every_message_and_the_next_poll_starts_after_it(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_EGGZ_CHANNEL_ID", "chan")
    monkeypatch.setattr(eg.config, "DISCORD_EGGZ_AUTHOR_ID", "eggz-id")
    monkeypatch.setattr(eg, "_token", lambda: "bot")
    seen = []

    def fetch(channel, after=None, before=None):
        seen.append({"after": after, "before": before})
        if len(seen) == 1:
            return [
                {"id": "200", "author": {"id": "someone"}, "content": "nope",
                 "timestamp": "2026-10-20T18:00:00+00:00"},
                {"id": "100", "author": {"id": "eggz-id", "username": "jack_mehoff123",
                                         "global_name": "Dr. Eggz"},
                 "content": "NYY ML -115",
                 "timestamp": "2026-10-20T17:00:00+00:00"},
            ]
        return []

    class Conn:
        def __init__(self):
            self.cursor = None
            self.messages = {}
            self.picks = []

        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params or ()
            if "INSERT INTO capper_ingest_cursor" in sql:
                self.cursor = (params[1], params[2], params[3])
            elif "INSERT INTO capper_messages" in sql:
                self.messages[params[0]] = (params[5], None)
            elif "INSERT INTO capper_picks" in sql:
                self.picks.append(params)
            return self

        def fetchone(self):
            if "FROM capper_ingest_cursor" in self.sql:
                return self.cursor
            if "FROM capper_messages WHERE message_id" in self.sql:
                return self.messages.get(self.params[0])
            if "status = 'graded'" in self.sql:
                return None
            if "FROM push_sent" in self.sql:
                return None
            return None

        def fetchall(self):
            return []

        def commit(self):
            pass

    conn = Conn()
    assert eg.ingest_messages(conn, fetch) == 1
    assert "someone" not in str(conn.messages)
    assert "100" in conn.messages
    assert conn.picks and conn.picks[0][2] == "needs_review"
    seen.clear()
    eg.ingest_messages(conn, fetch)
    assert seen[0]["after"] == "200"


def test_a_final_moneyline_uses_the_settler_result(monkeypatch):
    monkeypatch.setattr(eg, "_closing_odds", lambda *a, **k: None)
    updates = []

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params
            if sql.startswith("UPDATE capper_picks SET status = 'graded'"):
                updates.append(params)
            return self

        def fetchall(self):
            if "status = 'pending'" in self.sql:
                return [(
                    7, "MLB_2026-10-20_NYY_BOS", "h2h", "home", None, -110, 1,
                    None, None, None, "2026-10-20T23:00:00+00:00", "MLB",
                )]
            return []

        def fetchone(self):
            if "FROM games" in self.sql:
                return (5, 2, 1, None, 0, "2026-10-20T23:00:00+00:00", "2026-10-20")
            return None

        def commit(self):
            pass

    assert eg.grade_pending(Conn()) == 1
    result, profit, risked = updates[0][:3]
    assert result == "WIN"
    assert abs(profit - 1.0) < 1e-9
    assert abs(risked - 1.1) < 1e-9


def _grade_conn(pending_row, log_rows):
    reviews = []

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params
            if sql.startswith("UPDATE") and "needs_review" in sql:
                reviews.append(params)
            return self

        def fetchall(self):
            if "status = 'pending'" in self.sql:
                return [pending_row]
            if "player_game_log" in self.sql:
                return log_rows
            return []

        def fetchone(self):
            if "RETURNING" in self.sql:
                return (1,)
            if "FROM games" in self.sql:
                return (24, 17, 1, None, 0, "2026-10-19T20:00:00+00:00", "2026-10-19")
            return None

        def commit(self):
            pass

    return Conn(), reviews


def test_an_empty_nfl_log_stays_pending():
    """No box score yet is not a grade and not a review. The recap waits."""
    row = (
        9, "NFL_2026-10-19_BUF_KC", "prop", "over", 250.5, -110, 1,
        "Josh Allen", "passing_yards", None, "2026-10-19T20:00:00+00:00", "NFL",
    )
    conn, reviews = _grade_conn(row, [])
    assert eg.grade_pending(conn) == 0
    assert reviews == []


def test_an_mlb_prop_waits_when_the_log_is_not_in_yet():
    row = (
        8, "MLB_2026-10-20_NYY_BOS", "prop", "over", 1.5, -120, 1,
        "Aaron Judge", "hits", "batter_hits", "2026-10-20T23:00:00+00:00", "MLB",
    )
    conn, reviews = _grade_conn(row, [])
    assert eg.grade_pending(conn) == 0
    assert reviews == []


def test_the_all_time_line_stops_at_the_period_and_posts_on_every_span(monkeypatch):
    """A graded leg after the period is not in the all-time line. A graded
    leg inside it is, including one whose grade landed after the period.
    Day, week, and month each carry the line. pending and needs_review do not."""
    import sqlite3

    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append(body) or "91")

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, status TEXT, result TEXT, game_date TEXT,
        sport TEXT, price REAL, clv_pct REAL, units REAL, risked REAL,
        graded_at TEXT, posted_at TEXT,
        capper_key TEXT DEFAULT 'eggz', parlay_id INTEGER)""")
    db.execute("""CREATE TABLE games (
        game_id TEXT, sport TEXT, game_date TEXT,
        home_score INT, away_score INT, commence_time TEXT)""")
    db.execute("""CREATE TABLE push_sent (
        lock_key TEXT, kind TEXT, sent_at TEXT, message_id TEXT,
        UNIQUE (lock_key, kind))""")
    legs = [
        (1, "graded", "LOSS", "2026-10-12", "NHL", -130, -1.3, 1.3,
         "2026-10-13T11:00:00+00:00"),
        (2, "graded", "WIN", "2026-10-18", "NHL", -110, 1.0, 1.1,
         "2026-10-21T01:56:24+00:00"),
        (3, "graded", "WIN", "2026-10-20", "NHL", -135, 1.0, 1.35,
         "2026-10-21T04:23:21+00:00"),
        (4, "pending", None, "2026-10-21", "NHL", -110, None, None, None),
        (5, "needs_review", "WIN", "2026-09-30", "NHL", -110, 5.0, 1.1, None),
    ]
    db.executemany(
        "INSERT INTO capper_picks (id, status, result, game_date, sport, "
        "price, units, risked, graded_at) VALUES (?,?,?,?,?,?,?,?,?)",
        legs)

    class Conn:
        def execute(self, sql, params=None):
            return db.execute(sql.replace("%s", "?"), tuple(params or ()))

        def commit(self):
            db.commit()

    conn = Conn()
    assert "downgrade_reason" not in eg._GRADED_LEGS
    assert "paused" not in eg._GRADED_LEGS
    assert eg._post_window(
        conn, "day", "2026-10-18", "2026-10-18", "Oct 18") == 1
    assert eg._post_window(
        conn, "week", "2026-10-12", "2026-10-18", "Week of Oct 12-18") == 1
    assert eg._post_window(
        conn, "month", "2026-10-01", "2026-10-18", "October") == 1
    assert eg._post_window(
        conn, "day", "2026-10-12", "2026-10-12", "Oct 12") == 1

    def all_time(body):
        fields = body["embeds"][0]["fields"]
        return next(f for f in fields if "All-time" in f["name"])

    # Oct 18 day, the week, and the month stop before the Oct 20 win.
    for body in posted[:3]:
        field = all_time(body)
        assert "since 2026-10-12" in field["name"]
        assert "1-1" in field["value"]
        assert "-0.30u" in field["value"] and "ROI" in field["value"]
        assert "2 settled" in field["value"]
        assert "2-1" not in field["value"]
        assert "+5.00u" not in field["value"]
        assert "footer" not in body["embeds"][0]
    # The Oct 12 day does not include the Oct 18 win graded on Oct 21.
    oct12 = all_time(posted[3])
    assert "0-1" in oct12["value"]
    assert "1 settled" in oct12["value"]
    assert "+5.00u" not in oct12["value"]
    oct18 = posted[0]["embeds"][0]
    assert "1-0" in oct18["description"]
    assert "NHL (all-time)" in [f["name"] for f in oct18["fields"]]


def test_the_embed_names_eggz_and_states_units_and_roi():
    rows = [("MLB", "eggz", "WIN", None, -110, 4.0, False, 1.0, 1.1),
            ("MLB", "eggz", "LOSS", None, -110, None, False, -1.1, 1.1)]
    embed = eg.eggz_embed("Oct 19", rows, pending=0)
    assert embed["title"] == "\U0001F4CA Eggz — Oct 19"
    assert "1-1" in embed["description"]
    assert "+1.00u" not in embed["description"] or "-0.10u" in embed["description"]
    assert "ROI" in embed["description"]
    assert embed["fields"][0]["name"] == "MLB"
    assert eg.eggz_embed("Oct 19", rows, pending=2) is None


def test_the_recap_posts_only_to_his_webhook_and_only_once(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append((url, body)) or "55")

    class Conn:
        def __init__(self):
            self.sent = set()

        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params or ()
            if "INSERT INTO push_sent" in sql:
                self.sent.add((params[0], params[1]))
            return self

        def fetchone(self):
            if "push_sent" in self.sql and "SELECT" in self.sql:
                return (1,) if (self.params[0], self.params[1]) in self.sent else None
            if "COUNT" in self.sql:
                return (0,)
            return None

        def fetchall(self):
            return [("MLB", "eggz", "WIN", None, -110, 1.0, False, 1.0, 1.1)]

        def commit(self):
            pass

    conn = Conn()
    assert eg._post_window(conn, "day", "2026-10-19", "2026-10-19", "Oct 19") == 1
    assert eg._post_window(conn, "day", "2026-10-19", "2026-10-19", "Oct 19") == 0
    assert len(posted) == 1
    assert posted[0][0] == "https://discord.test/eggz"
    assert "Eggz" in posted[0][1]["embeds"][0]["title"]
    assert ("discord_eggz_results_day:2026-10-19", "discord_eggz_results_day") in conn.sent


def test_an_unset_webhook_posts_nothing(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "")
    assert eg.post_eggz_recaps(datetime(2026, 10, 20, 12, 0, tzinfo=eg.ET)) == 0


def test_a_live_game_on_the_slate_date_holds_the_recap(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append(body) or "55")

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params or ()
            return self

        def fetchone(self):
            if "FROM games" in self.sql:
                return (1,)
            if "COUNT" in self.sql:
                return (0,)
            return None

        def fetchall(self):
            return [("NHL", "eggz", "WIN", None, -110, 1.0, False, 1.0, 1.1)]

        def commit(self):
            pass

    assert eg._post_window(Conn(), "day", "2026-10-20", "2026-10-20", "Oct 20") == 0
    assert posted == []


def test_a_utc_instant_after_8pm_et_does_not_recap(monkeypatch):
    """01:50 UTC on Oct 21 is 9:50pm ET on Oct 20. The morning window is closed."""
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    calls = []
    monkeypatch.setattr(eg, "ingest_messages", lambda conn: None)
    monkeypatch.setattr(eg, "grade_pending", lambda conn: 0)
    monkeypatch.setattr(
        eg, "_post_window",
        lambda conn, span, start, end, heading, dry_run=False, now=None: calls.append(
            (span, start, end)) or 0)

    class Conn:
        def close(self):
            pass

    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: Conn())
    now = datetime(2026, 10, 21, 1, 50, tzinfo=timezone.utc)
    assert eg.post_eggz_recaps(now) == 0
    assert calls == []


def test_a_utc_morning_recaps_yesterday_in_new_york(monkeypatch):
    """15:00 UTC on Oct 21 is 11:00am ET. Yesterday is Oct 20."""
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    calls = []
    monkeypatch.setattr(eg, "ingest_messages", lambda conn: None)
    monkeypatch.setattr(eg, "grade_pending", lambda conn: 0)
    monkeypatch.setattr(
        eg, "_post_window",
        lambda conn, span, start, end, heading, dry_run=False, now=None: calls.append(
            (span, start, end)) or 0)

    class Conn:
        def close(self):
            pass

    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: Conn())
    now = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)
    assert eg.post_eggz_recaps(now) == 0
    days = [call for call in calls if call[0] == "day"]
    assert days[0] == ("day", "2026-10-14", "2026-10-14")
    assert days[-1] == ("day", "2026-10-20", "2026-10-20")
    assert len(days) == 7
    assert all(call[1] != "2026-10-21" for call in calls)


def test_a_missed_eggz_day_posts_the_next_morning_for_that_date(monkeypatch):
    """Oct 18 missed its morning. The morning of Oct 21 posts that date.
    The evening does not."""
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append(body) or "88")
    monkeypatch.setattr(eg, "ingest_messages", lambda conn: None)
    monkeypatch.setattr(eg, "grade_pending", lambda conn: 0)

    class Conn:
        def __init__(self):
            self.sent = set()
            self.sql = ""
            self.params = ()

        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params or ()
            if "INSERT INTO push_sent" in sql:
                self.sent.add((params[0], params[1]))
            return self

        def fetchone(self):
            if "push_sent" in self.sql and "SELECT" in self.sql:
                return (1,) if (self.params[0], self.params[1]) in self.sent else None
            if "COUNT" in self.sql:
                return (0,)
            return None

        def fetchall(self):
            if self.params[:2] == ("2026-10-18", "2026-10-18"):
                return [("NHL", "eggz", "WIN", None, -110, 1.0, False, 1.0, 1.1)]
            return []

        def commit(self):
            pass

        def close(self):
            pass

    conn = Conn()
    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: conn)
    evening = datetime(2026, 10, 20, 21, 56, tzinfo=eg.ET)
    assert eg.post_eggz_recaps(evening) == 0
    assert posted == [] and conn.sent == set()
    morning = datetime(2026, 10, 21, 8, 0, tzinfo=eg.ET)
    assert eg.post_eggz_recaps(morning) == 1
    assert ("discord_eggz_results_day:2026-10-18",
            "discord_eggz_results_day") in conn.sent
    assert "Oct 18" in posted[0]["embeds"][0]["title"]


def test_before_6am_et_the_daily_recap_does_not_run(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    calls = []
    monkeypatch.setattr(eg, "ingest_messages", lambda conn: None)
    monkeypatch.setattr(eg, "grade_pending", lambda conn: 0)
    monkeypatch.setattr(
        eg, "_post_window",
        lambda conn, span, start, end, heading, dry_run=False, now=None: (
            calls.append(span) or 0))

    class Conn:
        def close(self):
            pass

    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: Conn())
    assert eg.post_eggz_recaps(datetime(2026, 10, 21, 5, 59, tzinfo=eg.ET)) == 0
    assert "day" not in calls


def test_an_evening_live_game_holds_the_week_until_the_next_morning(monkeypatch):
    """9:56pm ET with NHL in progress posts nothing. The next morning posts the week."""
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append(body) or "77")
    monkeypatch.setattr(eg, "ingest_messages", lambda conn: None)
    monkeypatch.setattr(eg, "grade_pending", lambda conn: 0)

    class Conn:
        def __init__(self):
            self.sent = set()
            self.sql = ""
            self.params = ()
            self.live = "2026-10-20T19:00:00-04:00"

        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params or ()
            if "INSERT INTO push_sent" in sql:
                self.sent.add((params[0], params[1]))
            return self

        def fetchone(self):
            if "push_sent" in self.sql and "SELECT" in self.sql:
                return (1,) if (self.params[0], self.params[1]) in self.sent else None
            if "COUNT" in self.sql:
                return (0,)
            return None

        def fetchall(self):
            if "commence_time" in self.sql:
                return [(self.live,)]
            if self.params[:2] == ("2026-10-12", "2026-10-18"):
                return [("NHL", "eggz", "WIN", None, -110, 1.0, False, 1.0, 1.1)]
            return []

        def commit(self):
            pass

        def close(self):
            pass

    conn = Conn()
    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: conn)
    evening = datetime(2026, 10, 20, 21, 56, tzinfo=eg.ET)
    assert eg.post_eggz_recaps(evening) == 0
    assert posted == [] and conn.sent == set()

    # 10:00am, and the sport is still in progress. Still no ledger row.
    conn.live = "2026-10-21T09:00:00-04:00"
    held = datetime(2026, 10, 21, 10, 0, tzinfo=eg.ET)
    assert eg.post_eggz_recaps(held) == 0
    assert posted == [] and conn.sent == set()

    # Next morning. That start is outside the live horizon. The week posts.
    conn.live = "2026-10-21T09:00:00-04:00"
    morning = datetime(2026, 10, 22, 8, 0, tzinfo=eg.ET)
    assert eg.post_eggz_recaps(morning) == 1
    assert len(posted) == 1
    assert ("discord_eggz_results_week:2026-10-12",
            "discord_eggz_results_week") in conn.sent
    assert eg.post_eggz_recaps(morning) == 0
    assert len(posted) == 1


def test_the_main_recap_waits_while_a_game_on_that_date_is_unfinished(monkeypatch):
    from tracking import discord_notifier as dn
    posted = []
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    monkeypatch.setattr(dn, "_post", lambda url, body: posted.append(body) or "99")

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            return self

        def fetchone(self):
            if "FROM games" in self.sql:
                return (1,)
            return None

        def fetchall(self):
            return [("NHL", "nhl_moneyline", "WIN", 0.02, -110, None, False, 1.0, 1.1)]

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(dn, "get_connection", lambda: Conn())
    morning = datetime(2026, 10, 21, 8, 0, tzinfo=dn.ET)
    assert dn.notify_discord_results(game_date="2026-10-20", now=morning) == 0
    assert dn.notify_discord_period(
        "week", date(2026, 10, 12), date(2026, 10, 18),
        "Week of Oct 12-18", now=morning) == 0
    assert posted == []


def test_the_job_is_on_the_pipeline_and_settle_posts_the_recap():
    import scheduler
    assert "eggz_ingest" in scheduler._PIPELINE_JOBS
    job = {j.id: j for j in scheduler.build_scheduler().get_jobs()}["eggz_ingest"]
    assert "15" in str(job.trigger)
    src = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")
    assert "post_eggz_recaps" in src
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert "add_capper_picks_2026_10_20.sql" in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


OCT22 = (
    "Thursday Oct. 22\nAll 1U\n\nNHL\n"
    "NSH Predators ML (+122)🗑️\nPIT Penguins ML (-112)✅\n\nNFL\n"
    "A.J. Brown (NE) O5.5 Receptions (+116)🗑️\n\nNBA\n"
    "E.J. Edgecombe (PHI) O11.5 Points (+100)🗑️"
)
OCT23 = (
    "Friday Oct. 22\nAll 1U\n\nNBA \nORL Magic ML (-118)🗑️\n\nNCAAF\n"
    "Tulsa ML (-115)🗑️"
)
OCT24 = (
    "Saturday Oct. 24\n\nNCAAF\nALL 1U\nSouth Carolina ML (-130)\n"
    "Texas -3 (-112)\n\nNHL\nPHI Flyers ML (-122)\n"
    "WSH Capitals ML (-125)\nUTA Mammoth ML (-142)"
)
_POSTED_OCT22 = datetime(2026, 10, 22, 17, 54, 0, tzinfo=timezone.utc)
_POSTED_OCT23 = datetime(2026, 10, 23, 22, 53, 29, tzinfo=timezone.utc)


def test_a_date_without_a_sport_is_a_slate_header():
    header = eg._slate_header("Friday Oct. 22", _POSTED_OCT23)
    assert header == {"slate_date": "2026-10-22"}
    assert "sport" not in header
    legs, reviews = eg.parse_message("Friday Oct. 22\nNCAAF\nTulsa ML (-115)", _POSTED_OCT23)
    assert reviews == []
    assert legs[0]["sport_hint"] == "NCAAF"
    assert legs[0]["slate_date"] == "2026-10-22"
    assert legs[0]["team_text"] == "Tulsa"
    assert legs[0]["price"] == -115


def test_the_oct_22_and_oct_23_posts_parse_with_nothing_dropped():
    legs, reviews = eg.parse_message(OCT22, _POSTED_OCT22)
    assert reviews == []
    assert [leg["market"] for leg in legs] == ["h2h", "h2h", "prop", "prop"]
    nsh, pit, brown, edge = legs
    assert nsh["team_text"] == "NSH Predators" and nsh["price"] == 122
    assert nsh["sport_hint"] == "NHL" and nsh["slate_date"] == "2026-10-22"
    assert pit["team_text"] == "PIT Penguins" and pit["price"] == -112
    assert brown["player_name"] == "A.J. Brown"
    assert brown["team_text"] == "NE" and brown["side"] == "over"
    assert brown["line"] == 5.5 and brown["price"] == 116
    assert brown["prop_stat"] == "receptions" and brown["sport_hint"] == "NFL"
    assert edge["player_name"] == "E.J. Edgecombe"
    assert edge["team_text"] == "PHI" and edge["side"] == "over"
    assert edge["line"] == 11.5 and edge["price"] == 100
    assert edge["prop_stat"] == "points" and edge["sport_hint"] == "NBA"
    assert [leg["stake_units"] for leg in legs] == [1, 1, 1, 1]

    legs, reviews = eg.parse_message(OCT23, _POSTED_OCT23)
    assert reviews == []
    assert [leg["team_text"] for leg in legs] == ["ORL Magic", "Tulsa"]
    assert [leg["price"] for leg in legs] == [-118, -115]
    assert [leg["sport_hint"] for leg in legs] == ["NBA", "NCAAF"]
    assert [leg["slate_date"] for leg in legs] == ["2026-10-22", "2026-10-22"]

    legs, reviews = eg.parse_message(OCT22 + "\nlets ride", _POSTED_OCT22)
    assert len(legs) == 4
    assert reviews[0]["reason"] == "unparsed"
    assert "lets ride" in reviews[0]["raw"]

    posted24 = datetime(2026, 10, 24, 15, 59, 4, tzinfo=timezone.utc)
    legs, reviews = eg.parse_message(OCT24, posted24)
    assert reviews == []
    carolina, texas, phi, wsh, uta = legs
    assert carolina["market"] == "h2h" and carolina["team_text"] == "South Carolina"
    assert carolina["price"] == -130 and carolina["sport_hint"] == "NCAAF"
    assert carolina["slate_date"] == "2026-10-24"
    assert texas["market"] == "spreads" and texas["team_text"] == "Texas"
    assert texas["line"] == -3 and texas["price"] == -112
    assert [leg["team_text"] for leg in (phi, wsh, uta)] == [
        "PHI Flyers", "WSH Capitals", "UTA Mammoth",
    ]


def _army_tulsa(game_id, game_date, commence, home_score, away_score):
    home_win = None
    if home_score is not None and away_score is not None:
        home_win = 1 if float(home_score) > float(away_score) else 0
    return (
        game_id, "NCAAF", game_date, "Tulsa", "Army", commence,
        home_score, away_score, home_win, None, 0,
    )


class _SlateConn:
    """School-name lookup. A query pinned to the slate date returns nothing."""

    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = ()

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params or ()
        return self

    def fetchall(self):
        if "game_date = %s" in self.sql:
            return []
        return list(self.rows)

    def fetchone(self):
        return None


def test_a_school_name_is_matched_exactly():
    """'Texas' is not Texas Tech, Texas A&M, or Texas State."""
    posted = datetime(2026, 10, 24, 15, 59, tzinfo=timezone.utc)
    legs, reviews = eg.parse_message(
        "Saturday Oct. 24\nNCAAF\nTexas -3 (-112)", posted)
    assert reviews == []
    seen = []

    class Conn:
        def execute(self, sql, params=None):
            seen.append((sql, params))
            self.sql = sql
            return self

        def fetchall(self):
            if "game_date = %s" in self.sql:
                return [(
                    "NCAAF_2026-10-24_ole-miss_texas", "NCAAF", "2026-10-24",
                    "Texas", "Ole Miss", "2026-10-24T23:30:00+00:00",
                    None, None, None, None, 0,
                )]
            return []

        def fetchone(self):
            return None

    game, reason = eg._match_leg(Conn(), legs[0], posted)
    assert reason is None
    assert game["game_id"] == "NCAAF_2026-10-24_ole-miss_texas"
    assert game["side"] == "home"
    assert legs[0]["line"] == -3
    sql, params = seen[0]
    assert "lower(home_team) = lower(%s)" in sql
    assert "lower(away_team) = lower(%s)" in sql
    assert params[0] == "NCAAF"
    assert params[1] == "Texas" and params[2] == "Texas"


def test_tulsa_matches_the_odds_twin_when_the_slate_date_is_wrong():
    et = _army_tulsa(
        "NCAAF_2026-10-23_army_tulsa", "2026-10-23",
        "2026-10-24T00:36:33+00:00", 35, 38)
    utc = _army_tulsa(
        "NCAAF_2026-10-24_army_tulsa", "2026-10-24",
        "2026-10-24T00:30:00+00:00", 35, 38)
    legs, reviews = eg.parse_message("Friday Oct. 22\nNCAAF\nTulsa ML (-115)", _POSTED_OCT23)
    assert reviews == []
    game, reason = eg._match_leg(_SlateConn([et, utc]), legs[0], _POSTED_OCT23)
    assert reason is None
    assert game["game_id"] == "NCAAF_2026-10-23_army_tulsa"
    assert game["side"] == "home"
    assert game["game_date"] == "2026-10-23"


def test_a_twin_with_one_final_uses_the_scored_row():
    posted = datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc)
    kick = posted + timedelta(hours=6)
    bare = {
        "sport": "NCAAF", "home_team": "Tulsa", "away_team": "Army",
        "commence": kick, "game_id": "NCAAF_2026-10-23_army_tulsa",
        "game_date": "2026-10-23", "home_score": None, "away_score": None,
    }
    scored = {
        **bare, "commence": kick + timedelta(minutes=6),
        "game_id": "NCAAF_2026-10-24_army_tulsa", "game_date": "2026-10-24",
        "home_score": 35, "away_score": 38,
    }
    chosen, reason = eg.choose_game([bare, scored], posted)
    assert reason is None
    assert chosen["game_id"] == "NCAAF_2026-10-24_army_tulsa"


def test_two_games_and_a_later_kick_are_not_collapsed():
    posted = datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc)
    kick = posted + timedelta(hours=4)
    tulsa = {
        "sport": "NCAAF", "home_team": "Tulsa", "away_team": "Army",
        "commence": kick, "game_id": "early", "game_date": "2026-10-23",
        "home_score": 1, "away_score": 0,
    }
    later = {**tulsa, "commence": kick + timedelta(hours=5), "game_id": "late"}
    chosen, reason = eg.choose_game([tulsa, later], posted)
    assert chosen is None and reason == "ambiguous_game"
    other = {**tulsa, "away_team": "Navy", "commence": kick + timedelta(hours=2),
             "game_id": "other"}
    chosen, reason = eg.choose_game([tulsa, other], posted)
    assert chosen is None and reason == "ambiguous_game"


def test_an_nfl_receptions_prop_grades_from_the_log():
    graded = []

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params
            if sql.startswith("UPDATE capper_picks SET status = 'graded'"):
                graded.append(params)
            return self

        def fetchall(self):
            if "FROM capper_messages" in self.sql:
                return []
            if "game_id IS NOT NULL" in self.sql:
                return [(
                    9, "NFL_2026_07_NE_CHI", "prop", "over", 5.5, 116, 1,
                    "A.J. Brown", "receptions", "player_receptions",
                    "2026-10-23T00:15:00+00:00", "NFL",
                )]
            if "nfl_player_game_log" in self.sql:
                return [("A.J. Brown", 3)]
            return []

        def fetchone(self):
            if "FROM games" in self.sql:
                return (24, 35, 0, None, 0, "2026-10-23T00:15:00+00:00", "2026-10-22")
            if "RETURNING" in self.sql:
                return (1,)
            return None

        def commit(self):
            pass

    assert eg.grade_pending(Conn()) == 1
    result, profit, risked = graded[0][:3]
    expect, expect_risk = eg.units_for_result(1, 116, "LOSS")
    assert result == "LOSS"
    assert abs(profit - expect) < 1e-9
    assert abs(risked - expect_risk) < 1e-9
    assert abs(expect - -0.8620689655172413) < 1e-9


def test_a_player_missing_from_the_log_is_not_a_silent_no_action():
    """The log says VJ Edgecombe. The post says E.J. Edgecombe. No guess."""
    calls = []

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params
            calls.append((sql, params))
            return self

        def fetchall(self):
            if "FROM capper_messages" in self.sql:
                return []
            if "game_id IS NOT NULL" in self.sql:
                return [(
                    4, "NBA_2026-10-22_CLE_PHI", "prop", "over", 11.5, 100, 1,
                    "E.J. Edgecombe", "points", "player_points",
                    "2026-10-23T00:00:00+00:00", "NBA",
                )]
            if "nba_player_game_log" in self.sql:
                return [("VJ Edgecombe", 11)]
            return []

        def fetchone(self):
            if "FROM games" in self.sql:
                return (110, 108, 1, None, 0, "2026-10-23T00:00:00+00:00", "2026-10-22")
            if "RETURNING" in self.sql:
                return (1,)
            return None

        def commit(self):
            pass

    assert eg.grade_pending(Conn()) == 1
    reviews = [params for sql, params in calls
               if "SET status = 'needs_review'" in sql]
    assert reviews == [("player_not_in_log", 4)]
    assert not any("NO_ACTION" in sql for sql, _params in calls)


def test_tulsa_moneyline_grades_as_a_home_loss(monkeypatch):
    monkeypatch.setattr(eg, "_closing_odds", lambda *a, **k: None)
    graded = []

    class Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params
            if sql.startswith("UPDATE capper_picks SET status = 'graded'"):
                graded.append(params)
            return self

        def fetchall(self):
            if "FROM capper_messages" in self.sql:
                return []
            if "game_id IS NOT NULL" in self.sql:
                return [(
                    8, "NCAAF_2026-10-23_army_tulsa", "h2h", "home", None, -115, 1,
                    None, None, None, "2026-10-24T00:36:33+00:00", "NCAAF",
                )]
            return []

        def fetchone(self):
            if "FROM games" in self.sql:
                return (35, 38, 0, None, 0, "2026-10-24T00:36:33+00:00", "2026-10-23")
            return None

        def commit(self):
            pass

    assert eg.grade_pending(Conn()) == 1
    result, profit, risked = graded[0][:3]
    expect, expect_risk = eg.units_for_result(1, -115, "LOSS")
    assert result == "LOSS"
    assert abs(profit - expect) < 1e-9 and abs(expect - -1.15) < 1e-9
    assert abs(risked - expect_risk) < 1e-9


def test_the_all_time_block_matches_the_main_recap():
    from tracking.discord_notifier import render_all_time_fields
    day = [("NCAAF", "eggz", "LOSS", None, -115, None, False, -1.15, 1.15)]
    all_rows = day + [
        ("NBA", "eggz", "LOSS", None, -118, 1.5, False, -1.18, 1.18),
    ]
    embed = eg.eggz_embed("Oct 23", day, pending=0, all_time=all_rows, since="2026-10-18")
    assert embed["fields"][1:] == render_all_time_fields(all_rows, "2026-10-18")
    overall = embed["fields"][1]
    assert "All-time" in overall["name"] and "2026-10-18" in overall["name"]
    assert "2 settled" in overall["value"]
    assert "beat close" in overall["value"]
    assert "NBA (all-time)" in [f["name"] for f in embed["fields"]]
    assert "NCAAF (all-time)" in [f["name"] for f in embed["fields"]]
    assert "footer" not in embed
    assert eg.eggz_embed("Oct 23", day, pending=1, all_time=all_rows) is None


def _sqlite():
    import sqlite3
    db = sqlite3.connect(":memory:")

    class Conn:
        def execute(self, sql, params=None):
            return db.execute(sql.replace("%s", "?"), tuple(params or ()))

        def commit(self):
            db.commit()

        def close(self):
            pass

    return db, Conn


def test_a_needs_review_leg_holds_the_recap(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append(body) or "1")
    db, Conn = _sqlite()
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, status TEXT, result TEXT, game_date TEXT,
        sport TEXT, price REAL, clv_pct REAL, units REAL, risked REAL,
        posted_at TEXT, capper_key TEXT DEFAULT 'eggz', parlay_id INTEGER)""")
    db.execute("""CREATE TABLE games (
        game_id TEXT, sport TEXT, game_date TEXT,
        home_score INT, away_score INT, commence_time TEXT)""")
    db.execute("""CREATE TABLE push_sent (
        lock_key TEXT, kind TEXT, sent_at TEXT, message_id TEXT,
        UNIQUE (lock_key, kind))""")
    db.execute(
        "INSERT INTO capper_picks (id, status, result, game_date, sport, price, "
        "clv_pct, units, risked, posted_at) VALUES (1,'graded','WIN','2026-10-22',"
        "'NHL',-112,NULL,1,1.12,'2026-10-22T17:54:00+00:00')")
    db.execute(
        "INSERT INTO capper_picks (id, status, result, game_date, sport, price, "
        "clv_pct, units, risked, posted_at) VALUES (2,'needs_review',NULL,"
        "'2026-10-22','NFL',116,NULL,NULL,NULL,'2026-10-22T17:54:00+00:00')")
    conn = Conn()
    assert eg._post_window(conn, "day", "2026-10-22", "2026-10-22", "Oct 22") == 0
    assert posted == []
    assert db.execute("SELECT COUNT(*) FROM push_sent").fetchone()[0] == 0


def test_an_undated_needs_review_holds_the_new_york_day():
    db, Conn = _sqlite()
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, status TEXT, game_date TEXT, posted_at TEXT,
        capper_key TEXT DEFAULT 'eggz', parlay_id INTEGER)""")
    db.execute(
        "INSERT INTO capper_picks (id, status, game_date, posted_at) "
        "VALUES (1,'needs_review',NULL,'2026-10-23T02:00:00+00:00')")
    conn = Conn()
    assert eg._unresolved_in(conn, "2026-10-22", "2026-10-22") == 1
    assert eg._unresolved_in(conn, "2026-10-23", "2026-10-23") == 0
    db.execute("UPDATE capper_picks SET posted_at = '2026-10-24T16:00:00+00:00'")
    assert eg._unresolved_in(conn, "2026-10-22", "2026-10-22") == 0
    assert eg._unresolved_in(conn, "2026-10-24", "2026-10-24") == 1


def test_reparse_leaves_a_graded_leg_and_keeps_an_unparsed_line(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_OPS", "")
    db, Conn = _sqlite()
    db.execute("""CREATE TABLE capper_messages (
        message_id TEXT PRIMARY KEY, body TEXT, posted_at TEXT,
        parse_status TEXT, parse_note TEXT, capper_key TEXT DEFAULT 'eggz')""")
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, message_id TEXT, line_no INTEGER, status TEXT,
        review_reason TEXT, sport TEXT, game_id TEXT, game_date TEXT,
        home_team TEXT, away_team TEXT, commence_time TEXT, market TEXT,
        side TEXT, line REAL, price REAL, stake_units REAL, player_name TEXT,
        prop_stat TEXT, prop_market TEXT, posted_at TEXT, result TEXT,
        units REAL, risked REAL, capper_key TEXT DEFAULT 'eggz',
        parlay_id INTEGER, UNIQUE (message_id, line_no))""")
    db.execute("""CREATE TABLE push_sent (
        lock_key TEXT, kind TEXT, sent_at TEXT, message_id TEXT,
        UNIQUE (lock_key, kind))""")
    body = "EDM Oilers ML -135\nlets ride"
    posted = "2026-10-20T16:06:51+00:00"
    db.execute(
        "INSERT INTO capper_messages "
        "(message_id, body, posted_at, parse_status, parse_note) "
        "VALUES ('m1',?,?, 'needs_review','old')",
        (body, posted))
    db.execute(
        "INSERT INTO capper_picks (id, message_id, line_no, status, result, "
        "units, price, stake_units, posted_at) VALUES "
        "(10,'m1',1,'graded','WIN',99,-135,1,?)", (posted,))
    db.execute(
        "INSERT INTO capper_picks (id, message_id, line_no, status, "
        "review_reason, stake_units, posted_at) VALUES "
        "(11,'m1',3,'needs_review','unparsed: gone',1,?)", (posted,))

    def fake_match(conn, leg, posted_at):
        return {
            "sport": "NHL", "game_id": "NHL_2026-10-20_MIN_EDM",
            "game_date": "2026-10-20", "home_team": "EDM", "away_team": "MIN",
            "commence_time": "2026-10-21T00:00:00+00:00", "side": "home",
        }, None

    monkeypatch.setattr(eg, "_match_leg", fake_match)
    assert eg.reparse_stored(Conn()) == 1
    row = db.execute(
        "SELECT status, result, units FROM capper_picks WHERE id = 10"
    ).fetchone()
    assert row == ("graded", "WIN", 99)
    gone = db.execute("SELECT id FROM capper_picks WHERE line_no = 3").fetchone()
    assert gone is None
    review = db.execute(
        "SELECT status, review_reason FROM capper_picks WHERE line_no = 2"
    ).fetchone()
    assert review[0] == "needs_review"
    assert review[1].startswith("unparsed:")
    assert "lets ride" in review[1]


def _recap_db():
    db, Conn = _sqlite()
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, status TEXT, result TEXT, game_date TEXT,
        sport TEXT, price REAL, clv_pct REAL, units REAL, risked REAL,
        stake_units REAL, review_reason TEXT, posted_at TEXT, graded_at TEXT,
        capper_key TEXT DEFAULT 'eggz', parlay_id INTEGER)""")
    db.execute("""CREATE TABLE games (
        game_id TEXT, sport TEXT, game_date TEXT,
        home_score INT, away_score INT, commence_time TEXT)""")
    db.execute("""CREATE TABLE push_sent (
        lock_key TEXT, kind TEXT, sent_at TEXT, message_id TEXT,
        UNIQUE (lock_key, kind))""")
    return db, Conn


def test_restate_posts_corrected_and_keeps_the_sent_row(monkeypatch):
    monkeypatch.setitem(eg.config.RECORD_RESTATEMENT_APPROVALS, "2026-10-23", "test")
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append(body) or "77")
    db, Conn = _recap_db()
    db.execute(
        "INSERT INTO capper_picks (id, status, result, game_date, sport, price, "
        "units, risked) VALUES (1,'graded','LOSS','2026-10-23','NCAAF',-115,-1.15,1.15)")
    sent_at = "2026-10-24T10:19:22-04:00"
    db.execute(
        "INSERT INTO push_sent VALUES (?,?,?,?)",
        ("discord_eggz_results_day:2026-10-23", "discord_eggz_results_day",
         sent_at, "1563557520860119051"))
    import data.db
    monkeypatch.setattr(data.db, "get_connection", Conn)
    assert eg.restate_eggz_day("2026-10-23") == 1
    title = posted[0]["embeds"][0]["title"]
    description = posted[0]["embeds"][0]["description"]
    assert title.endswith("Corrected")
    assert description.startswith("Corrected. The earlier post for this day left graded picks out.")
    assert "0-1" in description and "-1.15u" in description
    locks = db.execute("SELECT lock_key, kind FROM push_sent ORDER BY kind").fetchall()
    assert ("discord_eggz_results_day:2026-10-23", "discord_eggz_results_day") in locks
    assert any(kind == "discord_eggz_results_day_restate" for _key, kind in locks)
    assert eg.restate_eggz_day("2026-10-23") == 0
    assert len(posted) == 1


def test_restate_dry_run_and_an_unresolved_leg_post_nothing(monkeypatch):
    for day in ("2026-10-21", "2026-10-22"):
        monkeypatch.setitem(eg.config.RECORD_RESTATEMENT_APPROVALS, day, "test")
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append(body) or "77")
    db, Conn = _recap_db()
    db.execute(
        "INSERT INTO capper_picks (id, status, result, game_date, sport, price, "
        "units, risked) VALUES (1,'graded','WIN','2026-10-22','NHL',-112,1,1.12)")
    db.execute(
        "INSERT INTO push_sent VALUES (?,?,?,?)",
        ("discord_eggz_results_day:2026-10-22", "discord_eggz_results_day",
         "2026-10-23T06:03:01-04:00", "1"))
    import data.db
    monkeypatch.setattr(data.db, "get_connection", Conn)
    assert eg.restate_eggz_day("2026-10-22", dry_run=True) == 1
    assert posted == []
    assert db.execute("SELECT COUNT(*) FROM push_sent").fetchone()[0] == 1
    db.execute(
        "INSERT INTO capper_picks (id, status, game_date, sport) "
        "VALUES (2,'needs_review','2026-10-22','NBA')")
    assert eg.restate_eggz_day("2026-10-22", dry_run=True) == 0
    assert eg.restate_eggz_day("2026-10-22") == 0
    assert posted == []
    assert db.execute("SELECT COUNT(*) FROM push_sent").fetchone()[0] == 1
    assert eg.restate_eggz_day("2026-10-21") == 0


def test_settle_manual_uses_the_stored_price_and_refuses_a_graded_row():
    db, Conn = _sqlite()
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, status TEXT, result TEXT, game_date TEXT,
        price REAL, stake_units REAL, units REAL, risked REAL,
        review_reason TEXT, graded_at TEXT,
        capper_key TEXT DEFAULT 'eggz', parlay_id INTEGER)""")
    db.execute(
        "INSERT INTO capper_picks (id, status, game_date, price, stake_units) "
        "VALUES (7,'needs_review','2026-10-22',100,1)")
    db.execute(
        "INSERT INTO capper_picks (id, status, game_date, price, stake_units) "
        "VALUES (8,'needs_review','2026-10-22',NULL,1)")
    db.execute(
        "INSERT INTO capper_picks (id, status, result, game_date, price, stake_units) "
        "VALUES (9,'graded','WIN','2026-10-22',-110,1)")
    db.execute(
        "INSERT INTO capper_picks (id, status, price, stake_units) "
        "VALUES (10,'needs_review',-115,1)")
    conn = Conn()
    preview = eg.settle_manual(conn, 7, "loss", "VJ Edgecombe logged 11 points", apply=False)
    assert preview["applied"] is False
    assert preview["result"] == "LOSS"
    assert preview["units"] == -1.0 and preview["risked"] == 1.0
    assert db.execute("SELECT status FROM capper_picks WHERE id = 7").fetchone()[0] == "needs_review"
    applied = eg.settle_manual(conn, 7, "LOSS", "VJ Edgecombe logged 11 points")
    assert applied["applied"] is True
    row = db.execute(
        "SELECT status, result, units, risked, review_reason FROM capper_picks WHERE id = 7"
    ).fetchone()
    assert row[0] == "graded" and row[1] == "LOSS"
    assert row[2] == -1.0 and row[3] == 1.0
    assert row[4].startswith("manual: VJ Edgecombe")
    bare = eg.settle_manual(conn, 8, "LOSS", "no price was on the post")
    assert bare["units"] == -1.0 and bare["risked"] == 1.0
    try:
        eg.settle_manual(conn, 9, "LOSS", "already graded")
        raised = False
    except eg.EggzSettleError:
        raised = True
    assert raised
    assert db.execute("SELECT result FROM capper_picks WHERE id = 9").fetchone()[0] == "WIN"
    for bad in (("PUSHY", "note"), ("WIN", "  ")):
        try:
            eg.settle_manual(conn, 8, bad[0], bad[1])
            raised = False
        except eg.EggzSettleError:
            raised = True
        assert raised
    try:
        eg.settle_manual(conn, 10, "LOSS", "no slate")
        raised = False
    except eg.EggzSettleError as exc:
        raised = True
        assert "game_date" in str(exc)
    assert raised
    assert db.execute("SELECT status FROM capper_picks WHERE id = 10").fetchone()[0] == "needs_review"


def test_the_record_script_does_not_write_without_apply(monkeypatch, capsys):
    from scripts import eggz_record
    db, Conn = _sqlite()
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, status TEXT, result TEXT, game_date TEXT,
        sport TEXT, market TEXT, player_name TEXT, side TEXT, price REAL,
        stake_units REAL, units REAL, risked REAL, review_reason TEXT,
        graded_at TEXT, posted_at TEXT,
        capper_key TEXT DEFAULT 'eggz', parlay_id INTEGER)""")
    db.execute(
        "INSERT INTO capper_picks (id, status, review_reason, game_date, sport, "
        "market, player_name, side, price, stake_units) VALUES "
        "(4,'needs_review','player_not_in_log','2026-10-22','NBA','prop',"
        "'E.J. Edgecombe','over',100,1)")
    import data.db
    monkeypatch.setattr(data.db, "get_connection", Conn)
    graded = []
    monkeypatch.setattr(eggz_record, "grade_pending", lambda conn: graded.append(1) or 0)
    assert eggz_record.main(["grade"]) == 0
    assert graded == []
    assert "dry-run" in capsys.readouterr().out
    assert eggz_record.main(["grade", "--apply"]) == 0
    assert graded == [1]
    assert eggz_record.main([
        "settle", "--id", "4", "--result", "LOSS",
        "--note", "VJ Edgecombe logged 11 points",
    ]) == 0
    assert db.execute("SELECT status FROM capper_picks WHERE id = 4").fetchone()[0] == "needs_review"
    assert eggz_record.main([
        "settle", "--id", "4", "--result", "LOSS",
        "--note", "VJ Edgecombe logged 11 points", "--apply",
    ]) == 0
    assert db.execute(
        "SELECT status, result FROM capper_picks WHERE id = 4"
    ).fetchone() == ("graded", "LOSS")
    calls = []
    monkeypatch.setattr(
        eggz_record, "restate_eggz_day",
        lambda game_date, dry_run=False, now=None: calls.append(dry_run) or 1)
    assert eggz_record.main(["restate", "2026-10-22"]) == 0
    assert calls == [True]
    assert eggz_record.main(["restate", "2026-10-23", "--apply"]) == 0
    assert calls == [True, False]


def test_a_parlay_is_one_bet_at_the_stated_price_and_stake():
    posted = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
    body = "\n".join([
        "NBA Oct. 24",
        "LAL @ BOS",
        "3 leg parlay +450 1u",
        "Lakers -3.5 -110",
        "- Celtics ML -150",
        "Over 220.5",
    ])
    legs, reviews = eg.parse_message(body, posted)
    assert reviews == []
    assert len(legs) == 3
    header = legs[0]["parlay_header"]
    assert header["ok"] is True
    assert header["price"] == 450
    assert header["stake_units"] == 1
    assert all(leg["parlay_header"] is header for leg in legs)
    assert [leg["market"] for leg in legs] == ["spreads", "h2h", "totals"]
    assert legs[0]["line"] == -3.5 and legs[0]["price"] == -110
    assert legs[1]["team_text"] == "Celtics"
    assert "parlay_header" not in eg.parse_message(OCT18, _POSTED_OCT18)[0][0]


def test_an_unparsed_parlay_line_is_kept_and_not_booked_as_singles():
    body = "\n".join([
        "PARLAY +450 2u",
        "Lakers -3.5",
        "lets ride",
        "Celtics ML",
    ])
    legs, reviews = eg.parse_message(body)
    assert reviews == [{"line_no": 3, "raw": "lets ride", "reason": "unparsed"}]
    assert len(legs) == 2
    assert legs[0]["parlay_header"]["ok"] is False
    assert legs[0]["parlay_header"]["stake_units"] == 2
    assert legs[0]["parlay_header"]["price"] == 450

    bare, bare_reviews = eg.parse_message("PARLAY")
    assert bare == []
    assert bare_reviews[0]["reason"] == "unparsed"
    assert "PARLAY" in bare_reviews[0]["raw"]

    robin_legs, robin_reviews = eg.parse_message(
        "round robin +400 1u\nLakers -3.5\nCeltics ML")
    assert robin_reviews == []
    assert len(robin_legs) == 2
    assert robin_legs[0]["parlay_header"]["ok"] is False
    assert robin_legs[0]["parlay_header"]["broken"] is True


def test_parlaymatt_unset_does_not_read_or_post(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_PARLAYMATT_CHANNEL_ID", "")
    monkeypatch.setattr(eg.config, "DISCORD_PARLAYMATT_AUTHOR_ID", "")
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_PARLAYMATT", "")
    monkeypatch.setattr(eg, "_token", lambda: "bot")

    def boom(*_a, **_k):
        raise AssertionError("discord was called")

    monkeypatch.setattr(eg.requests, "get", boom)
    assert eg.configured_to_read(eg.PARLAYMATT) is False
    assert eg.configured_to_post(eg.PARLAYMATT) is False
    assert eg.post_parlaymatt_recaps(
        datetime(2026, 10, 20, 12, 0, tzinfo=eg.ET)) == 0
    eg.run_parlaymatt_ingest()


def test_parlaymatt_ingest_keeps_his_author_and_eggz_kinds_stay(monkeypatch):
    monkeypatch.setattr(eg.config, "DISCORD_PARLAYMATT_CHANNEL_ID", "pm-chan")
    monkeypatch.setattr(eg.config, "DISCORD_PARLAYMATT_AUTHOR_ID", "1186644933180923904")
    monkeypatch.setattr(eg, "_token", lambda: "bot")
    seen = []

    def fetch(channel, after=None, before=None):
        seen.append(channel)
        if len(seen) == 1:
            return [
                {"id": "9", "author": {"id": "someone-else"}, "content": "nope",
                 "timestamp": "2026-10-24T18:00:00+00:00"},
                {"id": "8", "author": {"id": "1186644933180923904",
                                       "username": "parlaymatt"},
                 "content": "PARLAY +450 1u\nLakers -3.5\nCeltics ML",
                 "timestamp": "2026-10-24T17:00:00+00:00"},
            ]
        return []

    class Conn:
        def __init__(self):
            self.cursor = None
            self.messages = {}
            self.picks = []

        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params or ()
            if "INSERT INTO capper_ingest_cursor" in sql:
                self.cursor = (params[1], params[2], params[3])
            elif "INSERT INTO capper_messages" in sql:
                self.messages[params[0]] = params
            elif "INSERT INTO capper_picks" in sql:
                self.picks.append((sql, params))
            return self

        def fetchone(self):
            if "FROM capper_ingest_cursor" in self.sql:
                return self.cursor
            if "FROM capper_messages WHERE message_id" in self.sql:
                return None
            if "status = 'graded'" in self.sql:
                return None
            if "FROM push_sent" in self.sql:
                return None
            if "RETURNING" in self.sql:
                return (1,)
            return None

        def fetchall(self):
            return []

        def commit(self):
            pass

    conn = Conn()
    assert eg.ingest_messages(conn, fetch, eg.PARLAYMATT) == 1
    assert seen[0] == "pm-chan"
    assert "8" in conn.messages
    assert conn.messages["8"][-1] == "parlaymatt"
    assert "9" not in conn.messages
    assert any("'parlay'" in sql for sql, _params in conn.picks)
    assert any("parlaymatt" in params for _sql, params in conn.picks)
    assert "discord_eggz_results" in eg.EGGZ.results_prefix
    assert eg.PARLAYMATT.results_prefix == "discord_parlaymatt_results"
    assert eg.EGGZ.review_kind == "eggz_review"
    assert "'eggz'" in eg._GRADED_LEGS
    assert "discord_eggz" not in eg._graded_legs(eg.PARLAYMATT)


def test_a_graded_parlay_counts_once_and_his_all_time_starts_at_his_first(monkeypatch):
    import sqlite3
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_PARLAYMATT", "https://discord.test/pm")
    monkeypatch.setattr(eg.config, "DISCORD_WEBHOOK_EGGZ", "https://discord.test/eggz")
    posted = []
    monkeypatch.setattr(eg, "_post", lambda url, body: posted.append((url, body)) or "55")
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, status TEXT, result TEXT, game_date TEXT,
        sport TEXT, market TEXT, price REAL, clv_pct REAL, units REAL,
        risked REAL, stake_units REAL, posted_at TEXT, parlay_id INTEGER,
        capper_key TEXT, message_id TEXT, line_no INTEGER)""")
    db.execute("""CREATE TABLE games (
        game_id TEXT, sport TEXT, game_date TEXT,
        home_score INT, away_score INT, commence_time TEXT)""")
    db.execute("""CREATE TABLE push_sent (
        lock_key TEXT, kind TEXT, sent_at TEXT, message_id TEXT,
        UNIQUE (lock_key, kind))""")
    db.executemany(
        "INSERT INTO capper_picks (id, status, result, game_date, sport, market, "
        "price, units, risked, stake_units, capper_key, parlay_id, message_id, "
        "line_no) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "graded", "WIN", "2026-10-18", "NBA", "parlay", 450, 1.0, 0.2222,
             1, "parlaymatt", None, "m", 1),
            (2, "graded", "WIN", "2026-10-18", "NBA", "spreads", -110, 9.0, 9.0,
             1, "parlaymatt", 1, "m", 2),
            (3, "graded", "WIN", "2026-10-18", "NBA", "h2h", -110, 9.0, 9.0,
             1, "parlaymatt", 1, "m", 3),
            (4, "graded", "LOSS", "2026-10-18", "NHL", "h2h", -110, -1.1, 1.1,
             1, "eggz", None, "e", 1),
        ])

    class Conn:
        def execute(self, sql, params=None):
            return db.execute(sql.replace("%s", "?"), tuple(params or ()))

        def commit(self):
            db.commit()

    conn = Conn()
    assert eg._post_window(
        conn, "day", "2026-10-18", "2026-10-18", "Oct 18",
        capper=eg.PARLAYMATT) == 1
    assert eg._post_window(
        conn, "day", "2026-10-18", "2026-10-18", "Oct 18") == 1
    pm, eggz = posted
    assert pm[0] == "https://discord.test/pm"
    assert pm[1]["embeds"][0]["title"] == "\U0001F4CA ParlayMatt — Oct 18"
    assert "1-0" in pm[1]["embeds"][0]["description"]
    assert "+9.00u" not in pm[1]["embeds"][0]["description"]
    assert "since 2026-10-18" in pm[1]["embeds"][0]["fields"][-1]["name"] or any(
        "since 2026-10-18" in f["name"] for f in pm[1]["embeds"][0]["fields"])
    assert eggz[0] == "https://discord.test/eggz"
    assert eggz[1]["embeds"][0]["title"] == "\U0001F4CA Eggz — Oct 18"
    assert "0-1" in eggz[1]["embeds"][0]["description"]
    assert "+1.00u" not in eggz[1]["embeds"][0]["description"]
    locks = db.execute("SELECT lock_key, kind FROM push_sent").fetchall()
    assert ("discord_parlaymatt_results_day:2026-10-18",
            "discord_parlaymatt_results_day") in locks
    assert ("discord_eggz_results_day:2026-10-18",
            "discord_eggz_results_day") in locks


def test_parlay_rollup_uses_the_stated_price_not_the_leg_prices():
    import sqlite3
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE capper_picks (
        id INTEGER PRIMARY KEY, status TEXT, result TEXT, market TEXT,
        price REAL, stake_units REAL, units REAL, risked REAL,
        parlay_id INTEGER, capper_key TEXT, graded_at TEXT, review_reason TEXT,
        clv_pct REAL, closing_price REAL, clv_beat_close INTEGER)""")
    db.execute(
        "INSERT INTO capper_picks (id, status, market, price, stake_units, capper_key) "
        "VALUES (1,'pending','parlay',450,1,'parlaymatt')")
    db.execute(
        "INSERT INTO capper_picks (id, status, result, market, price, parlay_id, capper_key) "
        "VALUES (2,'graded','WIN','spreads',-110,1,'parlaymatt')")
    db.execute(
        "INSERT INTO capper_picks (id, status, result, market, price, parlay_id, capper_key) "
        "VALUES (3,'graded','LOSS','h2h',-150,1,'parlaymatt')")

    class Conn:
        def execute(self, sql, params=None):
            return db.execute(sql.replace("%s", "?"), tuple(params or ()))

        def commit(self):
            pass

    assert eg._grade_parlays(Conn(), eg.PARLAYMATT) == 1
    row = db.execute(
        "SELECT status, result, units, risked FROM capper_picks WHERE id = 1"
    ).fetchone()
    profit, risked = eg.units_for_result(1, 450, "LOSS")
    assert row[0] == "graded" and row[1] == "LOSS"
    assert abs(row[2] - profit) < 1e-9
    assert abs(row[3] - risked) < 1e-9
    assert db.execute(
        "SELECT status FROM capper_picks WHERE id = 2").fetchone()[0] == "graded"


def test_parlaymatt_is_on_the_same_schedule_and_the_migration_is_registered():
    import scheduler
    src = Path(scheduler.__file__).read_text(encoding="utf-8")
    assert "run_parlaymatt_ingest" in src
    assert "post_parlaymatt_recaps" in src
    pipe = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")
    assert "post_parlaymatt_recaps" in pipe
    assert "post_eggz_recaps" in pipe
    from data.view_migrations import ACTIVE_MIGRATIONS
    name = "capper_parlaymatt_2026_10_28.sql"
    assert name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    assert ACTIVE_MIGRATIONS.index(name) < len(ACTIVE_MIGRATIONS) - 2


def test_the_record_script_accepts_parlaymatt_and_still_defaults_to_eggz(monkeypatch):
    from scripts import eggz_record
    seen = []
    monkeypatch.setattr(
        eggz_record, "grade_pending",
        lambda conn, capper=eg.EGGZ: seen.append(capper.key) or 0)
    monkeypatch.setattr(eggz_record, "open_legs", lambda conn, capper=eg.EGGZ: [])

    class Conn:
        def close(self):
            pass

    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: Conn())
    assert eggz_record.main(["grade", "--apply"]) == 0
    assert seen == ["eggz"]
    assert eggz_record.main(["--capper", "parlaymatt", "grade", "--apply"]) == 0
    assert seen == ["eggz", "parlaymatt"]
    assert eggz_record.main(["grade", "--capper", "parlaymatt", "--apply"]) == 0
    assert seen == ["eggz", "parlaymatt", "parlaymatt"]

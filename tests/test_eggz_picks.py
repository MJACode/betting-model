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


def test_a_non_mlb_prop_on_a_final_is_marked_for_review():
    row = (
        9, "NFL_2026-10-19_BUF_KC", "prop", "over", 250.5, -110, 1,
        "Josh Allen", "passing_yards", None, "2026-10-19T20:00:00+00:00", "NFL",
    )
    conn, reviews = _grade_conn(row, [])
    assert eg.grade_pending(conn) == 1
    assert reviews[0][0] == "prop_not_graded"


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
        graded_at TEXT)""")
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
        (5, "needs_review", "WIN", "2026-10-12", "NHL", -110, 5.0, 1.1, None),
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

    def footer(body):
        return body["embeds"][0]["footer"]["text"]

    # Oct 18 day, the week, and the month stop before the Oct 20 win.
    for body in posted[:3]:
        text = footer(body)
        assert text.startswith("All-time: 1-1")
        assert "-0.30u" in text and "ROI" in text
        assert "2-1" not in text
    # The Oct 12 day does not include the Oct 18 win graded on Oct 21.
    assert footer(posted[3]).startswith("All-time: 0-1")
    assert "+5.00u" not in footer(posted[3])
    oct18 = posted[0]["embeds"][0]
    assert "1-0" in oct18["description"]
    assert oct18["footer"]["text"].startswith("All-time: 1-1")


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

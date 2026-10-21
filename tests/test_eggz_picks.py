"""Eggz's channel: parse, cursor, grade, and a recap that stays off #results."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
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
            if "needs_review" in sql:
                reviews.append(params)
            return self

        def fetchall(self):
            if "status = 'pending'" in self.sql:
                return [pending_row]
            if "player_game_log" in self.sql:
                return log_rows
            return []

        def fetchone(self):
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

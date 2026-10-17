"""A results recap stores the Discord message id _post already returns.

_post appends ?wait=true. notify_discord_results used to discard that id, so
every discord_results and discord_results_restate row had a null message_id
(45 + 16, measured 2026-10-14).
"""
from __future__ import annotations

import inspect

from tracking import discord_notifier as dn


class _Conn:
    def __init__(self):
        self.inserts: list[tuple] = []

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = tuple(params or ())
        if "INSERT INTO push_sent" in sql:
            self.inserts.append(self.params)
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return [("NHL", "nhl_moneyline", "WIN", 0.02, -110.0, None, False)]

    def commit(self):
        pass

    def close(self):
        pass


def test_the_recap_insert_writes_message_id():
    src = inspect.getsource(dn.notify_discord_results)
    assert "message_id" in src
    assert "_POST_OK_NO_ID" in src
    assert "wait=true" in inspect.getsource(dn._post)


def test_a_posted_recap_ledgers_the_id_wait_returned(monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    monkeypatch.setattr(dn, "_post", lambda url, payload: "99887766")

    assert dn.notify_discord_results(game_date="2026-10-05") == 1
    (lock_key, kind, _sent, message_id) = conn.inserts[0]
    assert lock_key == "discord_results:2026-10-05"
    assert kind == "discord_results"
    assert message_id == "99887766"


def test_a_204_with_no_id_is_not_a_finished_recap(monkeypatch):
    """A body with no id used to be ledgered as posted. That row then blocked
    every retry, and the message could not be opened. It is a failure."""
    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")

    def no_id(url, payload):
        dn._last_delivery["status"] = 204
        dn._last_delivery["detail"] = "no message id"
        return dn._POST_OK_NO_ID

    monkeypatch.setattr(dn, "_post", no_id)
    assert dn.notify_discord_results(game_date="2026-10-04") == 0
    assert [row[1] for row in conn.inserts] == ["discord_results_error"]
    assert "no message id" in conn.inserts[0][3]
    assert "HTTP 204" in conn.inserts[0][3]


def test_a_rejected_post_is_recorded_and_the_next_pass_sends(monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    calls = {"n": 0}

    def post(url, payload):
        calls["n"] += 1
        if calls["n"] == 1:
            dn._last_delivery["status"] = 400
            dn._last_delivery["detail"] = (
                "Invalid Form Body https://discord.com/api/webhooks/9/secret")
            return None
        return "555"

    monkeypatch.setattr(dn, "_post", post)
    assert dn.notify_discord_results(game_date="2026-10-04") == 0
    assert dn.notify_discord_results(game_date="2026-10-04") == 1
    kinds = [row[1] for row in conn.inserts]
    assert kinds == ["discord_results_error", "discord_results"]
    assert conn.inserts[0][3].startswith("HTTP 400")
    assert "secret" not in conn.inserts[0][3]
    assert "api/webhooks" not in conn.inserts[0][3]
    assert conn.inserts[1][3] == "555"


def test_a_restate_that_raises_is_recorded(monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(
        dn, "recaps_needing_restatement",
        lambda conn, through=None, **kw: [{
            "game_date": "2026-10-13",
            "published_at": "2026-10-14T06:02:45.951539-04:00",
            "late": 2, "settled": 7,
        }])

    def boom(*a, **k):
        raise RuntimeError("embed blew up")

    monkeypatch.setattr(dn, "notify_discord_results", boom)
    monkeypatch.setattr(
        "tracking.x_publisher.notify_x_results", lambda *a, **k: 0)
    assert dn.restate_published_recaps(through="2026-10-14") == 0
    assert conn.inserts[0][1] == "discord_results_restate_error"
    assert "embed blew up" in conn.inserts[0][3]


def test_a_restatement_stores_its_own_id(monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    monkeypatch.setattr(dn, "_post", lambda url, payload: "112233")
    restate = {"published_at": "2026-10-06T07:26:00-04:00", "late": 1, "settled": 2}

    assert dn.notify_discord_results(game_date="2026-10-05", restate=restate) == 1
    lock_key, kind, _sent, message_id = conn.inserts[0]
    assert kind == "discord_results_restate"
    assert lock_key.startswith("discord_results_restate:2026-10-05:")
    assert message_id == "112233"

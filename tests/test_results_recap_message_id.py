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


def test_a_204_with_no_id_is_stored_as_null(monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    monkeypatch.setattr(dn, "_post", lambda url, payload: dn._POST_OK_NO_ID)

    assert dn.notify_discord_results(game_date="2026-10-04") == 1
    assert conn.inserts[0][3] is None
    assert conn.inserts[0][1] == "discord_results"


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

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


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = {} if payload is None else payload
        self.text = text

    def json(self):
        if self.status_code == 204:
            raise ValueError("no body")
        return self._payload


def _silence_alert(monkeypatch):
    sent = []

    def alert(title, detail, recovery=False, post=None):
        sent.append((title, detail))
        return True

    monkeypatch.setattr("tracking.watch_util.post_ops_alert", alert)
    return sent


def test_a_204_with_no_id_is_not_a_finished_recap(monkeypatch):
    """A body with no id used to be ledgered as posted. That row then blocked
    every retry, and the message could not be opened. It is a failure."""
    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    monkeypatch.setattr(dn.requests, "post", lambda *a, **k: _Resp(204))
    _silence_alert(monkeypatch)
    assert dn.notify_discord_results(game_date="2026-10-04") == 0
    assert [row[1] for row in conn.inserts] == ["discord_results_error"]
    assert "no message id" in conn.inserts[0][3]
    assert "HTTP 204" in conn.inserts[0][3]


def test_a_rejected_post_is_recorded_and_the_next_pass_sends(monkeypatch):
    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    alerts = _silence_alert(monkeypatch)
    calls = {"n": 0}

    def post(url, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp(
                400,
                text="Invalid Form Body https://discord.com/api/webhooks/9/secret")
        return _Resp(200, {"id": "555"})

    monkeypatch.setattr(dn.requests, "post", post)
    assert dn.notify_discord_results(game_date="2026-10-04") == 0
    assert dn.notify_discord_results(game_date="2026-10-04") == 1
    kinds = [row[1] for row in conn.inserts]
    assert kinds == ["discord_results_error", "discord_results"]
    assert conn.inserts[0][3].startswith("HTTP 400")
    assert "secret" not in conn.inserts[0][3]
    assert "api/webhooks" not in conn.inserts[0][3]
    assert "no message id" not in conn.inserts[0][3]
    assert conn.inserts[1][3] == "555"
    assert alerts == []


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


class _Ledger:
    """Remembers push_sent rows so a later pass can see the error row."""

    def __init__(self):
        self.rows: dict[tuple, str] = {}
        self.inserts: list[tuple] = []
        self.sql = ""
        self.params: tuple = ()

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = tuple(params or ())
        if "INSERT INTO push_sent" in sql:
            lock_key, kind, _sent, message_id = self.params[:4]
            self.rows[(lock_key, kind)] = message_id
            self.inserts.append(self.params)
        return self

    def fetchone(self):
        if "push_sent" not in self.sql or len(self.params) < 2:
            return None
        key = (self.params[0], self.params[1])
        if key not in self.rows:
            return None
        if "SELECT 1" in self.sql:
            return (1,)
        return (self.rows[key],)

    def fetchall(self):
        return [("NHL", "nhl_moneyline", "WIN", 0.02, -110.0, None, False)]

    def commit(self):
        pass

    def close(self):
        pass


def test_a_success_with_no_message_id_posts_once_and_alerts_once(monkeypatch):
    """Discord said success and gave no id. Later passes must not post again,
    and the ops alert fires once."""
    conn = _Ledger()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    alerts = _silence_alert(monkeypatch)
    posts = []

    def post(url, json=None, timeout=None):
        posts.append(url)
        if len(posts) > 1:
            return _Resp(200, {"id": "should-not-be-sent"})
        return _Resp(200, {})

    monkeypatch.setattr(dn.requests, "post", post)
    for _ in range(40):
        assert dn.notify_discord_results(game_date="2026-10-04") == 0
    assert len(posts) == 1
    assert len(alerts) == 1
    assert "no message id" in alerts[0][1]
    assert "api/webhooks" not in alerts[0][1]
    assert [row[1] for row in conn.inserts] == ["discord_results_error"]
    assert "no message id" in conn.inserts[0][3]
    assert "discord_results" not in {row[1] for row in conn.inserts}


def test_pipeline_watch_shows_the_recap_error_kinds():
    import inspect

    from tracking.pipeline_watch import findings_from_delivery, run_watch

    out = findings_from_delivery([
        ("discord_results", 1, "2026-10-14T06:00:00-04:00"),
        ("discord_results_error", 1, "2026-10-14T06:01:00-04:00"),
        ("discord_results_restate_error", 2, "2026-10-14T07:01:00-04:00"),
    ])
    assert any(f.startswith("`discord_results_error`") for f in out)
    assert any(f.startswith("`discord_results_restate_error`") for f in out)
    assert not any(f.startswith("`discord_results` ") for f in out)
    assert "findings_from_delivery" in inspect.getsource(run_watch)


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

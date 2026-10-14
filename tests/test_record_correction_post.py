"""The 2026-10-14 record correction posts once, with the words fixed.

A retry must not send a surface that push_sent already holds. An unread
ledger must not send anything. The pin is allowed to fail.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from scripts import post_record_correction as rc  # noqa: E402
from tracking import job_queue as jq  # noqa: E402
from tracking.x_publisher import _assert_no_link  # noqa: E402

EXACT = (
    "**Record correction.** We audited every pick since Sep 1, and no pick was "
    "graded wrong. Our recaps had been counting 109 picks that were never "
    "posted, and those went 41-68. They're out now, so the record only counts what you saw. "
    "Corrected all-time: **431-375-2, +16.92u**. "
    "MLB 193-187-2 (\u221215.45u), NCAAF 96-83 (+3.44u), NFL 33-38 (\u221210.92u), "
    "NHL 63-46 (+13.58u), WNBA 45-21 (+25.27u), UFC 1-0 (+1.00u). "
    "Props now grade the night of the game, so no more morning restatements."
)

WEBHOOK = "https://discord.com/api/webhooks/999/supersecretvalue"


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class Ledger:
    def __init__(self, rows=None, fail_read=False, fail_write_kinds=()):
        self.rows = dict(rows or {})
        self.fail_read = fail_read
        self.fail_write_kinds = set(fail_write_kinds)
        self.log: list[tuple] = []

    def execute(self, sql, params=None):
        kind = params[1]
        head = sql.lstrip().split(None, 1)[0].upper()
        self.log.append((head, kind))
        if head == "SELECT":
            if self.fail_read:
                raise RuntimeError("db down")
            if kind not in self.rows:
                return _Result(None)
            return _Result((self.rows[kind],))
        if head == "INSERT":
            if kind in self.fail_write_kinds:
                raise RuntimeError("db down")
            self.rows.setdefault(kind, params[3])
            return _Result(None)
        raise AssertionError(sql)

    def commit(self):
        self.log.append(("COMMIT", None))

    def close(self):
        self.log.append(("CLOSE", None))


def _publish(conn, monkeypatch, *, post, tweet, pin_status="failed",
             can_post=True):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_RESULTS", WEBHOOK)
    pins = []

    def place(url):
        assert url == WEBHOOK
        return ("guild", "chan")

    def pin(channel_id, message_id):
        pins.append((channel_id, message_id))
        return {"status": pin_status, "reason": "HTTP 403"}

    result = rc.publish_record_correction(
        conn, post=post, tweet=tweet, place=place, pin=pin,
        can_post=lambda: can_post)
    return result, pins


def test_the_words_are_the_approved_text_and_the_x_split_keeps_them():
    assert rc.DISCORD_TEXT == EXACT
    assert "(\u221215.45u)" in rc.DISCORD_TEXT
    assert "(\u221210.92u)" in rc.DISCORD_TEXT
    head, tail = rc.x_posts()
    plain = EXACT.replace("**", "")
    assert head + " " + tail == plain
    assert "**" not in head and "**" not in tail
    assert len(rc.DISCORD_TEXT) == 474
    assert len(plain) == 466
    assert len(head) == 265
    assert len(tail) == 200
    assert len(plain) > 280
    assert len(head) <= 280 and len(tail) <= 280
    assert tail.startswith("MLB ")
    assert tail.endswith("restatements.")
    _assert_no_link(head)
    _assert_no_link(tail)


def test_a_split_that_drops_characters_or_exceeds_280_is_refused():
    with pytest.raises(RuntimeError, match="per-sport"):
        rc.x_posts("no sport line here")
    with pytest.raises(RuntimeError, match="dropped"):
        rc.x_posts("hello  MLB rest")
    with pytest.raises(RuntimeError, match="does not fit"):
        rc.x_posts("short " + ("x" * 300) + " MLB tail")


def test_discord_payload_is_only_the_content_field(monkeypatch):
    seen = {}

    def fake(url, payload):
        seen["url"] = url
        seen["payload"] = payload
        return "42"

    monkeypatch.setattr("tracking.discord_notifier._post", fake)
    assert rc._real_post(WEBHOOK, rc.DISCORD_TEXT) == "42"
    assert seen["payload"] == {"content": rc.DISCORD_TEXT}


def test_the_tweet_wrapper_threads_the_reply(monkeypatch):
    seen = {}

    def fake(text, dry_run=False, reply_to=None):
        seen.update(text=text, dry_run=dry_run, reply_to=reply_to)
        return "99"

    monkeypatch.setattr("tracking.x_publisher.post_tweet", fake)
    assert rc._real_tweet("hello", "99") == "99"
    assert seen == {"text": "hello", "dry_run": False, "reply_to": "99"}


def test_each_surface_is_ledgered_before_the_next_one_is_sent(monkeypatch):
    conn = Ledger()
    sent = []

    def post(url, text):
        sent.append(("discord", text))
        assert ("INSERT", rc.KIND_DISCORD) not in conn.log
        assert conn.log[:3] == [
            ("SELECT", rc.KIND_DISCORD),
            ("SELECT", rc.KIND_X),
            ("SELECT", rc.KIND_X_REPLY),
        ]
        return "111"

    def tweet(text, reply_to):
        sent.append(("x", text, reply_to))
        return "222" if reply_to is None else "333"

    result, pins = _publish(conn, monkeypatch, post=post, tweet=tweet)
    assert [s[0] for s in sent] == ["discord", "x", "x"]
    assert sent[0][1] == EXACT
    head, tail = rc.x_posts()
    assert sent[1] == ("x", head, None)
    assert sent[2] == ("x", tail, "222")
    assert conn.log.index(("INSERT", rc.KIND_DISCORD)) < conn.log.index(("COMMIT", None))
    # The first tweet is inserted only after Discord's commit, and the reply
    # only after the first tweet's commit.
    inserts = [kind for op, kind in conn.log if op == "INSERT"]
    assert inserts == [rc.KIND_DISCORD, rc.KIND_X, rc.KIND_X_REPLY]
    assert result["discord_url"] == "https://discord.com/channels/guild/chan/111"
    assert result["pin"]["status"] == "failed"
    assert result["tweet_url"] == "https://x.com/signalbasepicks/status/222"
    assert result["reply_url"] == "https://x.com/signalbasepicks/status/333"
    assert pins == [("chan", "111")]
    blob = json.dumps(result)
    assert "supersecretvalue" not in blob
    assert "api/webhooks" not in blob


def test_a_second_run_does_not_send_again(monkeypatch):
    conn = Ledger(rows={
        rc.KIND_DISCORD: "111",
        rc.KIND_X: "222",
        rc.KIND_X_REPLY: "333",
    })
    sent = []
    result, pins = _publish(
        conn, monkeypatch,
        post=lambda *a: sent.append("discord"),
        tweet=lambda *a: sent.append("x"),
        pin_status="pinned")
    assert sent == []
    assert ("INSERT", rc.KIND_DISCORD) not in conn.log
    assert result["discord_url"].endswith("/111")
    assert result["tweet_url"].endswith("/222")
    assert result["reply_url"].endswith("/333")
    assert result["pin"]["status"] == "pinned"
    assert pins == [("chan", "111")]


def test_an_unread_ledger_posts_nothing(monkeypatch):
    conn = Ledger(fail_read=True)
    sent = []
    with pytest.raises(rc.LedgerUnread):
        _publish(conn, monkeypatch,
                 post=lambda *a: sent.append("discord") or "1",
                 tweet=lambda *a: sent.append("x") or "2")
    assert sent == []
    assert not any(op == "INSERT" for op, _ in conn.log)


def test_a_failed_discord_ledger_does_not_send_x(monkeypatch):
    conn = Ledger(fail_write_kinds={rc.KIND_DISCORD})
    tweets = []
    result, _ = _publish(
        conn, monkeypatch,
        post=lambda url, text: "111",
        tweet=lambda *a: tweets.append(a) or "222")
    assert tweets == []
    assert "discord_correction write failed" in result["ledger"]
    assert result["discord_message_id"] == "111"


def test_a_missing_x_credential_does_not_tweet_and_keeps_discord(monkeypatch):
    conn = Ledger()
    tweets = []
    with pytest.raises(RuntimeError, match="X publisher is off"):
        _publish(conn, monkeypatch, post=lambda url, text: "111",
                 tweet=lambda *a: tweets.append(a), can_post=False)
    assert tweets == []
    assert conn.rows[rc.KIND_DISCORD] == "111"
    assert rc.KIND_X not in conn.rows


def test_a_retry_sends_only_the_missing_reply(monkeypatch):
    conn = Ledger(rows={rc.KIND_DISCORD: "111", rc.KIND_X: "222"})
    tweets = []

    def tweet(text, reply_to):
        tweets.append((text, reply_to))
        return "333"

    result, _ = _publish(conn, monkeypatch, post=lambda *a: "nope", tweet=tweet)
    assert tweets == [(rc.x_posts()[1], "222")]
    assert result["reply_url"].endswith("/333")
    assert result["tweet_url"].endswith("/222")


def test_pin_without_a_bot_token_is_a_failure_and_does_not_call_discord(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    def boom(*a, **k):
        raise AssertionError("Discord was called")

    monkeypatch.setattr("requests.put", boom)
    got = rc._pin("55", "66")
    assert got["status"] == "failed"
    assert "DISCORD_BOT_TOKEN" in got["reason"]


def test_a_rejected_pin_is_reported_without_the_token(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-secret-value")
    seen = {}

    class Resp:
        status_code = 403
        text = "missing"

    def fake_put(url, headers=None, timeout=None):
        seen["url"] = url
        seen["auth"] = headers["Authorization"]
        return Resp()

    monkeypatch.setattr("requests.put", fake_put)
    got = rc._pin("55", "66")
    assert got == {"status": "failed", "reason": "HTTP 403"}
    assert seen["url"] == "https://discord.com/api/v10/channels/55/pins/66"
    assert seen["auth"] == "Bot bot-secret-value"
    assert "bot-secret-value" not in json.dumps(got)


def test_the_job_takes_no_text_and_is_declared_once():
    fn, validate = jq.JOBS["publish_record_correction"]
    assert fn is jq._job_publish_record_correction
    assert validate({}) == {}
    with pytest.raises(ValueError, match="no arguments"):
        validate({"text": "different words"})
    src = inspect.getsource(fn)
    assert "publish_record_correction(conn)" in src
    assert "kw[" not in src
    entries = json.loads((config.ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    matches = [e for e in entries if e["key"] == "record-correction-2026-10-14"]
    assert len(matches) == 1
    assert matches[0]["job_type"] == "publish_record_correction"
    assert matches[0]["args"] == {}
    validate(matches[0]["args"])


def test_the_oct13_line_posts_once_on_each_surface(monkeypatch):
    assert rc.OCT13_LINE == "Oct 13 corrected: NHL 7-2, +5.72u (+83.1% ROI)."
    assert len(rc.OCT13_LINE) <= 280
    _assert_no_link(rc.OCT13_LINE)
    conn = Ledger()
    sent = []

    def post(url, text):
        sent.append(("discord", text))
        assert conn.log[:2] == [
            ("SELECT", rc.KIND_DISCORD),
            ("SELECT", rc.KIND_X),
        ]
        return "444"

    def tweet(text, reply_to):
        sent.append(("x", text, reply_to))
        return "555"

    monkeypatch.setattr(config, "DISCORD_WEBHOOK_RESULTS", WEBHOOK)
    result = rc.publish_oct13_line(
        conn, post=post, tweet=tweet,
        place=lambda url: ("guild", "chan"), can_post=lambda: True)
    assert sent == [("discord", rc.OCT13_LINE), ("x", rc.OCT13_LINE, None)]
    assert result["discord_url"] == "https://discord.com/channels/guild/chan/444"
    assert result["tweet_url"] == "https://x.com/signalbasepicks/status/555"
    assert "supersecretvalue" not in json.dumps(result)
    again = []
    result2 = rc.publish_oct13_line(
        conn, post=lambda *a: again.append("d"),
        tweet=lambda *a: again.append("x"),
        place=lambda url: ("guild", "chan"), can_post=lambda: True)
    assert again == []
    assert result2["tweet_url"].endswith("/555")


def test_the_oct13_line_does_not_tweet_when_the_discord_ledger_fails(monkeypatch):
    conn = Ledger(fail_write_kinds={rc.KIND_DISCORD})
    tweets = []
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_RESULTS", WEBHOOK)
    result = rc.publish_oct13_line(
        conn, post=lambda url, text: "444",
        tweet=lambda *a: tweets.append("x") or "555",
        place=lambda url: ("guild", "chan"), can_post=lambda: True)
    assert tweets == []
    assert result["ledger"] == "discord follow-up write failed; X was not sent"
    assert result["discord_message_id"] == "444"
    assert result["tweet_id"] is None


def test_the_oct13_line_does_not_tweet_when_x_is_off(monkeypatch):
    conn = Ledger()
    tweets = []
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_RESULTS", WEBHOOK)
    with pytest.raises(RuntimeError, match="X publisher is off"):
        rc.publish_oct13_line(
            conn, post=lambda url, text: "444",
            tweet=lambda *a: tweets.append("x"),
            place=lambda url: ("guild", "chan"), can_post=lambda: False)
    assert tweets == []
    assert conn.rows[rc.KIND_DISCORD] == "444"
    assert rc.KIND_X not in conn.rows


def test_the_oct13_job_takes_no_text_and_is_declared_once():
    fn, validate = jq.JOBS["publish_oct13_nhl_line"]
    assert fn is jq._job_publish_oct13_nhl_line
    assert validate({}) == {}
    with pytest.raises(ValueError, match="no arguments"):
        validate({"text": "different"})
    entries = json.loads((config.ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    matches = [e for e in entries if e["key"] == "oct13-nhl-line-2026-10-14"]
    assert len(matches) == 1
    assert matches[0]["args"] == {}
    validate(matches[0]["args"])


def test_the_job_calls_the_poster_and_closes_its_connection(monkeypatch):
    closed = []

    class Conn:
        def close(self):
            closed.append(True)

    monkeypatch.setattr("data.db.get_connection", lambda: Conn())
    monkeypatch.setattr(
        "scripts.post_record_correction.publish_record_correction",
        lambda conn: {"discord_url": "u", "pin": {"status": "failed"}})
    result = jq._job_publish_record_correction()
    assert result["discord_url"] == "u"
    assert closed == [True]

"""Manual posts to @SignalBasePicks.

The pick slate and the recap stay on their own functions and their own
ledger. These tests are the queue: one send per claimed row, replies in
position order, and no second send after a tweet id exists.
"""

from __future__ import annotations

import copy
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tracking import social_posts as sp
from tracking.x_publisher import TweetDelivery

ROOT = Path(__file__).parent.parent
MIG = ROOT / "data" / "migrations" / "social_post_queue_2026_10_20.sql"
NOW = datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)

POST_1 = """📒 SignalBase all-time ledger (since Aug 29):

468-398-3 · +30.35u · +3.1% ROI
Beat the closing line on 267 of 490 CLV-graded picks (54.5%)

Every graded pick counts toward units. Wins and losses.

By sport 🧵👇"""

POST_2 = """Where it's made money:
🏀 WNBA 46-24, +23.48u
🏒 NHL 76-56, +16.01u
🏈 NCAAF 109-90, +10.20u
🥊 UFC 1-0, +1.00u

Where it hasn't (yet):
⚾ MLB 193-187-2, −15.45u
🏈 NFL 43-41-1, −4.90u

We post both."""

POST_3 = """Why CLV matters more than a hot week: if you keep getting a better number than where the market closes, the edge is real even through a bad night.

Full pick log + tonight's card in Discord 👇
discord.gg/Sge4Djj2xT"""


def _creds(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for name in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(name, "x")


class _Rows:
    def __init__(self, records):
        self._records = records

    def fetchall(self):
        return list(self._records)

    def fetchone(self):
        return self._records[0] if self._records else None


class QueueConn:
    """Applies the module's SQL to an in-memory list. Rollback restores the
    snapshot taken at the first statement of the transaction."""

    def __init__(self, rows):
        self.rows = rows
        self._snap = None
        self.closed = False

    def execute(self, sql, params=None):
        params = tuple(params or ())
        if self._snap is None:
            self._snap = copy.deepcopy(self.rows)
        if sql == sp.LOAD_SQL:
            ordered = sorted(self.rows, key=lambda r: (r["thread_key"], r["position"]))
            return _Rows([tuple(r[c] for c in sp._COLUMNS) for r in ordered])
        if sql == sp.RELOAD_SQL:
            found = [r for r in self.rows if r["id"] == params[0]]
            return _Rows([tuple(r[c] for c in sp._COLUMNS) for r in found])
        if sql == sp.CLAIM_SQL:
            when, row_id = params
            hit = self._one(row_id, status="queued", tweet_id=None)
            if hit is None:
                return _Rows([])
            hit["status"] = "posting"
            hit["claimed_at"] = when
            hit["error"] = None
            return _Rows([(hit["id"],)])
        if sql == sp.FAIL_QUEUED_SQL:
            error, row_id = params
            hit = self._one(row_id, status="queued", tweet_id=None)
            if hit is None:
                return _Rows([])
            hit["status"] = "failed"
            hit["error"] = error
            return _Rows([(hit["id"],)])
        if sql == sp.FINISH_SQL:
            (status, error, tweet_id, tweet_url, posted_at, pin_status, pin_note,
             claimed_at, row_id) = params
            hit = self._one(row_id, status="posting", tweet_id=None)
            if hit is None:
                return _Rows([])
            hit.update(status=status, error=error, tweet_id=tweet_id, tweet_url=tweet_url,
                       posted_at=posted_at, pin_status=pin_status, pin_note=pin_note,
                       claimed_at=claimed_at)
            return _Rows([(hit["id"],)])
        if sql == sp.HEAL_SQL:
            url, posted_at, pin_status, pin_note, row_id = params
            found = [r for r in self.rows
                     if r["id"] == row_id and r["tweet_id"] and r["status"] != "posted"]
            if not found:
                return _Rows([])
            hit = found[0]
            hit.update(status="posted", tweet_url=url, posted_at=posted_at,
                       pin_status=pin_status, pin_note=pin_note)
            return _Rows([(hit["id"],)])
        if sql == sp.SAVE_MEDIA_SQL:
            media_ids, row_id = params
            hit = self._one(row_id, status="posting", tweet_id=None)
            if hit is None:
                return _Rows([])
            hit["media_ids"] = list(media_ids)
            return _Rows([(hit["id"],)])
        if sql == sp.EXISTS_SQL:
            found = [r for r in self.rows if r["thread_key"] == params[0]]
            return _Rows([(1,)] if found else [])
        if sql == sp.INSERT_SQL:
            (thread_key, position, body, allow_link, pin, scheduled_at,
             media_urls, reply_to_tweet_id) = params
            new_id = max((r["id"] for r in self.rows), default=0) + 1
            self.rows.append(_blank(
                new_id, thread_key, position, body, allow_link=allow_link, pin=pin,
                scheduled_at=scheduled_at, media_urls=media_urls,
                reply_to_tweet_id=reply_to_tweet_id))
            return _Rows([(new_id,)])
        raise AssertionError(f"unexpected SQL: {sql}")

    def _one(self, row_id, *, status, tweet_id):
        for row in self.rows:
            if row["id"] == row_id and row["status"] == status and row["tweet_id"] == tweet_id:
                return row
        return None

    def commit(self):
        self._snap = None

    def rollback(self):
        if self._snap is not None:
            self.rows = self._snap
            self._snap = None

    def close(self):
        self.closed = True


def _blank(row_id, thread, position, body, **overrides):
    row = {
        "id": row_id,
        "thread_key": thread,
        "position": position,
        "body": body,
        "allow_link": False,
        "pin": False,
        "scheduled_at": NOW,
        "status": "queued",
        "tweet_id": None,
        "claimed_at": None,
        "tweet_url": None,
        "posted_at": None,
        "pin_status": None,
        "pin_note": None,
        "error": None,
        "media_urls": None,
        "media_ids": None,
        "reply_to_tweet_id": None,
    }
    row.update(overrides)
    return row


class Poster:
    def __init__(self, outcomes=None, ids=None):
        self.calls = []
        self.outcomes = list(outcomes or [])
        self.ids = list(ids or ["111", "222", "333", "444"])

    def __call__(self, text, reply_to=None, allow_link=False, dry_run=False,
                 media_ids=None):
        self.calls.append({"text": text, "reply_to": reply_to, "allow_link": allow_link,
                           "dry_run": dry_run, "media_ids": media_ids})
        outcome = self.outcomes.pop(0) if self.outcomes else "posted"
        if outcome == "raise":
            raise RuntimeError("boom")
        if outcome == "posted":
            return TweetDelivery(self.ids.pop(0), False, "posted", "")
        if outcome == "rate_limited":
            return TweetDelivery(None, True, "rate_limited", "HTTP 429")
        if outcome == "rejected":
            return TweetDelivery(None, False, "rejected", "HTTP 400 no")
        if outcome == "transport":
            return TweetDelivery(None, False, "transport", "timed out")
        raise AssertionError(outcome)


def _drain(conn, poster, monkeypatch, now=NOW, fetch=None, upload=None):
    _creds(monkeypatch)
    return sp.drain_social_posts(
        conn, now=now, deliver=poster, fetch_image=fetch, upload_image=upload)


def test_a_thread_posts_in_order_and_a_second_drain_sends_nothing(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First", pin=True),
        _blank(2, "t", 2, "Second"),
        _blank(3, "t", 3, "Third", allow_link=False),
    ])
    poster = Poster()
    result = _drain(conn, poster, monkeypatch)
    assert result["posted"] == 3
    assert [c["reply_to"] for c in poster.calls] == [None, "111", "222"]
    assert [c["text"] for c in poster.calls] == ["First", "Second", "Third"]
    by_id = {r["id"]: r for r in conn.rows}
    assert by_id[1]["status"] == "posted"
    assert by_id[1]["tweet_id"] == "111"
    assert by_id[1]["tweet_url"] == "https://x.com/signalbasepicks/status/111"
    assert by_id[1]["pin_status"] == "unsupported"
    assert "by hand" in by_id[1]["pin_note"]
    assert by_id[1]["tweet_url"] in by_id[1]["pin_note"]
    assert by_id[2]["pin_status"] == "not_requested"
    assert by_id[2]["tweet_id"] == "222"
    assert by_id[3]["tweet_id"] == "333"
    again = Poster()
    second = _drain(conn, again, monkeypatch)
    assert second["posted"] == 0
    assert again.calls == []


def test_a_later_post_replies_to_the_id_already_stored(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First", status="posted", tweet_id="900"),
        _blank(2, "t", 2, "Second"),
    ])
    poster = Poster(ids=["901"])
    result = _drain(conn, poster, monkeypatch)
    assert result["posted"] == 1
    assert poster.calls == [{"text": "Second", "reply_to": "900", "allow_link": False,
                             "dry_run": False, "media_ids": None}]


def test_a_row_that_already_has_a_tweet_id_is_not_sent(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First", status="queued", tweet_id="900"),
    ])
    poster = Poster()
    result = _drain(conn, poster, monkeypatch)
    assert poster.calls == []
    assert result["posted"] == 0
    assert conn.rows[0]["status"] == "posted"
    assert conn.rows[0]["tweet_url"] == "https://x.com/signalbasepicks/status/900"


def test_a_fresh_claim_is_not_posted_again(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First", status="posting", claimed_at=NOW),
    ])
    poster = Poster()
    _drain(conn, poster, monkeypatch)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "posting"


def test_an_expired_claim_becomes_uncertain_and_is_not_retried(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First", status="posting",
               claimed_at=NOW - timedelta(minutes=11)),
    ])
    poster = Poster()
    _drain(conn, poster, monkeypatch)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "uncertain"
    again = Poster()
    _drain(conn, again, monkeypatch)
    assert again.calls == []
    assert conn.rows[0]["status"] == "uncertain"


def test_a_rate_limit_requeues_and_the_next_drain_continues_the_thread(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First"),
        _blank(2, "t", 2, "Second"),
        _blank(3, "t", 3, "Third"),
    ])
    poster = Poster(outcomes=["posted", "rate_limited"])
    result = _drain(conn, poster, monkeypatch)
    assert result["posted"] == 1
    assert len(poster.calls) == 2
    assert conn.rows[0]["status"] == "posted"
    assert conn.rows[1]["status"] == "queued"
    assert conn.rows[1]["tweet_id"] is None
    assert conn.rows[2]["status"] == "queued"
    nxt = Poster(ids=["222", "333"])
    second = _drain(conn, nxt, monkeypatch)
    assert second["posted"] == 2
    assert [c["reply_to"] for c in nxt.calls] == ["111", "222"]


def test_a_transport_error_is_not_retried(monkeypatch):
    conn = QueueConn([_blank(1, "t", 1, "First")])
    poster = Poster(outcomes=["transport"])
    _drain(conn, poster, monkeypatch)
    assert conn.rows[0]["status"] == "uncertain"
    again = Poster()
    _drain(conn, again, monkeypatch)
    assert again.calls == []


def test_a_raised_deliver_is_not_retried(monkeypatch):
    conn = QueueConn([_blank(1, "t", 1, "First")])
    poster = Poster(outcomes=["raise"])
    _drain(conn, poster, monkeypatch)
    assert conn.rows[0]["status"] == "uncertain"
    again = Poster()
    _drain(conn, again, monkeypatch)
    assert again.calls == []


def test_an_http_rejection_fails_and_is_not_retried(monkeypatch):
    conn = QueueConn([_blank(1, "t", 1, "First")])
    poster = Poster(outcomes=["rejected"])
    _drain(conn, poster, monkeypatch)
    assert conn.rows[0]["status"] == "failed"
    assert "400" in conn.rows[0]["error"]
    again = Poster()
    _drain(conn, again, monkeypatch)
    assert again.calls == []


def test_a_url_without_allow_link_is_not_sent(monkeypatch):
    conn = QueueConn([_blank(1, "t", 1, "Join discord.gg/example")])
    poster = Poster()
    _drain(conn, poster, monkeypatch)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "failed"
    assert "allow_link" in conn.rows[0]["error"]


def test_allow_link_sends_the_url(monkeypatch):
    conn = QueueConn([_blank(1, "t", 1, POST_3, allow_link=True)])
    poster = Poster(ids=["777"])
    _drain(conn, poster, monkeypatch)
    assert poster.calls[0]["allow_link"] is True
    assert poster.calls[0]["text"] == POST_3
    assert conn.rows[0]["tweet_id"] == "777"


def test_an_overlong_post_is_not_sent(monkeypatch):
    conn = QueueConn([_blank(1, "t", 1, "x" * 281)])
    poster = Poster()
    _drain(conn, poster, monkeypatch)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "failed"


def test_a_position_gap_stops_the_thread(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First"),
        _blank(3, "t", 3, "Third"),
    ])
    poster = Poster()
    _drain(conn, poster, monkeypatch)
    assert [c["text"] for c in poster.calls] == ["First"]
    assert conn.rows[1]["status"] == "failed"
    assert "gap" in conn.rows[1]["error"]


def test_a_future_row_waits(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First", scheduled_at=NOW + timedelta(hours=2)),
    ])
    poster = Poster()
    result = _drain(conn, poster, monkeypatch)
    assert poster.calls == []
    assert result["posted"] == 0
    assert conn.rows[0]["status"] == "queued"


def test_dry_run_writes_nothing_and_does_not_send(monkeypatch):
    monkeypatch.delenv("X_API_KEY", raising=False)
    conn = QueueConn([
        _blank(1, "t", 1, "First"),
        _blank(2, "t", 2, "Second"),
    ])
    poster = Poster()
    result = sp.drain_social_posts(conn, dry_run=True, now=NOW, deliver=poster)
    assert result["status"] == "dry_run"
    assert [item["status"] for item in result["results"]] == ["would_post", "would_post"]
    assert result["results"][1]["reply_to"] == "dry-run-1"
    assert poster.calls == []
    assert [r["status"] for r in conn.rows] == ["queued", "queued"]


def test_the_kill_switch_posts_nothing(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "0")
    for name in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(name, "x")
    conn = QueueConn([_blank(1, "t", 1, "First")])
    poster = Poster()
    result = sp.drain_social_posts(conn, now=NOW, deliver=poster)
    assert result["status"] == "skipped"
    assert poster.calls == []
    assert conn.rows[0]["status"] == "queued"


def test_a_missing_table_is_a_no_op(monkeypatch):
    _creds(monkeypatch)

    class Missing:
        def execute(self, *args, **kwargs):
            raise RuntimeError('relation "social_post_queue" does not exist')

        def close(self):
            pass

    result = sp.drain_social_posts(Missing(), now=NOW, deliver=Poster())
    assert result == {"status": "no_table", "posted": 0, "results": []}


def test_enqueue_inserts_a_thread_and_refuses_a_second_copy():
    conn = QueueConn([])
    ids = sp.enqueue(conn, "weekly", ["One", "Two"], pin_root=True)
    assert ids == [1, 2]
    assert conn.rows[0]["pin"] is True
    assert conn.rows[1]["pin"] is False
    assert conn.rows[0]["status"] == "queued"
    with pytest.raises(sp.QueueRejected, match="already"):
        sp.enqueue(conn, "weekly", ["Again"])
    assert len(conn.rows) == 2


def test_enqueue_refuses_a_url_unless_allow_link_is_set():
    conn = QueueConn([])
    with pytest.raises(sp.QueueRejected, match="URL"):
        sp.enqueue(conn, "link", ["see discord.gg/example"])
    assert conn.rows == []
    ids = sp.enqueue(conn, "link", ["plain", "see discord.gg/example"], allow_link=True)
    assert ids == [1, 2]
    assert conn.rows[0]["allow_link"] is False
    assert conn.rows[1]["allow_link"] is True


def test_the_seed_is_the_draft_text_and_stays_queued():
    sql = MIG.read_text(encoding="utf-8")
    assert sql.count("$mig$") == 2
    assert sql.index("RETURN;") < sql.index("INSERT INTO public.social_post_queue")
    bodies = []
    for i in (1, 2, 3):
        tag = f"$ledger{i}$"
        start = sql.index(tag) + len(tag)
        bodies.append(sql[start:sql.index(tag, start)])
    assert bodies == [POST_1, POST_2, POST_3]
    assert "\u2212" in POST_2
    assert "−15.45u" in bodies[1] and "−4.90u" in bodies[1]
    assert "false, true" in sql
    assert "true, false" in sql
    assert "status" not in sql.split("INSERT INTO public.social_post_queue", 1)[1].split("VALUES", 1)[0]
    assert "REVOKE ALL ON public.social_post_queue FROM anon, authenticated;" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "all-time-ledger-2026-10-20" in sql


def test_the_migration_is_registered_and_does_not_become_last():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    assert ACTIVE_MIGRATIONS.index(MIG.name) < len(ACTIVE_MIGRATIONS) - 1


def test_the_cli_defaults_to_a_dry_run():
    """A stray `python -m tracking.social_posts` must not post. --drain is the
    flag that sends, same shape as the X smoke test."""
    src = (ROOT / "tracking" / "social_posts.py").read_text(encoding="utf-8")
    main = src[src.index("def main("):]
    assert '"--drain", action="store_true"' in main
    assert "dry_run=not args.drain" in main


def test_the_pick_and_recap_paths_do_not_opt_into_links():
    from tracking import x_publisher as xp
    for fn in (xp._post_released_picks, xp.notify_x_results, xp.notify_x_period):
        src = inspect.getsource(fn)
        assert "allow_link" not in src, fn.__name__
        assert "media_ids" not in src, fn.__name__
        assert "upload_tweet_image" not in src, fn.__name__
    queue = inspect.getsource(sp.drain_social_posts)
    assert "notify_x_picks" not in queue
    assert "notify_x_results" not in queue
    module = (ROOT / "tracking" / "social_posts.py").read_text(encoding="utf-8")
    assert "requests" not in module


def test_the_new_job_does_not_move_the_existing_schedules():
    import scheduler
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert src.count("CronTrigger(hour=6, minute=0, timezone=TIMEZONE)") == 1
    assert 'id="daily_pipeline"' in src
    jobs = {j.id: j for j in scheduler.build_scheduler().get_jobs()}
    assert "social_post_queue" in jobs
    assert "job_queue" in jobs
    assert "daily_pipeline" in jobs
    assert "*/5" in str(jobs["social_post_queue"].trigger)
    assert "*/5" in str(jobs["job_queue"].trigger)
    daily = str(jobs["daily_pipeline"].trigger)
    assert "hour='6'" in daily
    assert "minute='0'" in daily
    from tracking.job_heartbeat import MAX_SILENCE
    assert MAX_SILENCE["social_post_queue"] == 30


def test_allow_link_is_off_on_the_pick_client(monkeypatch):
    """The optional flag must not weaken the default. A URL still never leaves
    the pick path, and the manual flag still posts only to /2/tweets."""
    from tracking import x_publisher as xp
    _creds(monkeypatch)
    sent = []

    class _R:
        status_code = 201

        def json(self):
            return {"data": {"id": "55"}}

    def _post(url, json=None, headers=None, timeout=None):
        sent.append((url, json))
        return _R()

    monkeypatch.setattr(xp.requests, "post", _post)
    assert xp.post_tweet("see discord.gg/example") is None
    assert sent == []
    assert xp.post_tweet("see discord.gg/example", allow_link=True) == "55"
    assert sent[0][0] == xp.X_POST_URL
    assert sent[0][1]["text"] == "see discord.gg/example"
    assert "reply" not in sent[0][1]
    assert "media" not in sent[0][1]


def test_a_5xx_is_transport_and_not_a_tweet_id(monkeypatch):
    from tracking import x_publisher as xp
    _creds(monkeypatch)

    class _R:
        status_code = 503
        text = "unavailable"

        def json(self):
            return {"data": {"id": "should-not-be-used"}}

    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: _R())
    delivered = xp.deliver_tweet("hello")
    assert delivered.outcome == "transport"
    assert delivered.tweet_id is None
    assert xp.post_tweet("hello") is None


CARD = "https://cdn.example/card.png"
CARD_2 = "https://cdn.example/card-2.png"


class _Fetcher:
    def __init__(self, outcome="fetched", detail=""):
        self.urls = []
        self.outcome = outcome
        self.detail = detail

    def __call__(self, url):
        self.urls.append(url)
        from tracking.x_publisher import ImageFetch
        if self.outcome != "fetched":
            return ImageFetch(None, None, self.outcome, self.detail)
        return ImageFetch(b"\x89PNG\r\n\x1a\n", "image/png", "fetched", "")


class _Uploader:
    def __init__(self, ids=("11", "22", "33", "44"), fail_at=None, rate_at=None):
        self.calls = []
        self.ids = list(ids)
        self.fail_at = fail_at
        self.rate_at = rate_at

    def __call__(self, content, media_type):
        from tracking.x_publisher import MediaUpload
        self.calls.append({"type": media_type, "n": len(content)})
        n = len(self.calls)
        if self.rate_at == n:
            return MediaUpload(None, "rate_limited", "HTTP 429")
        if self.fail_at == n:
            return MediaUpload(None, "rejected", "HTTP 400 bad image")
        return MediaUpload(self.ids.pop(0), "uploaded", "")


def _no_network(url):
    raise AssertionError(f"fetched {url}")


def test_an_image_is_uploaded_then_attached(monkeypatch):
    conn = QueueConn([_blank(1, "card", 1, "Tonight's card", media_urls=[CARD, CARD_2])])
    poster = Poster(ids=["900"])
    fetch, upload = _Fetcher(), _Uploader()
    result = _drain(conn, poster, monkeypatch, fetch=fetch, upload=upload)
    assert result["posted"] == 1
    assert fetch.urls == [CARD, CARD_2]
    assert len(upload.calls) == 2
    assert poster.calls[0]["media_ids"] == ["11", "22"]
    assert poster.calls[0]["reply_to"] is None
    assert conn.rows[0]["status"] == "posted"
    assert conn.rows[0]["media_ids"] == ["11", "22"]
    assert conn.rows[0]["tweet_id"] == "900"


def test_a_failed_upload_does_not_tweet(monkeypatch):
    conn = QueueConn([_blank(1, "card", 1, "Tonight's card", media_urls=[CARD])])
    poster = Poster()
    upload = _Uploader(fail_at=1)
    result = _drain(conn, poster, monkeypatch, fetch=_Fetcher(), upload=upload)
    assert poster.calls == []
    assert result["posted"] == 0
    assert conn.rows[0]["status"] == "failed"
    assert conn.rows[0]["tweet_id"] is None
    assert "not posted" in conn.rows[0]["error"]
    assert conn.rows[0]["media_ids"] is None


def test_a_partial_upload_is_not_repeated_on_requeue(monkeypatch):
    conn = QueueConn([_blank(1, "card", 1, "Tonight's card", media_urls=[CARD, CARD_2])])
    poster = Poster()
    first_fetch, first_upload = _Fetcher(), _Uploader(fail_at=2)
    _drain(conn, poster, monkeypatch, fetch=first_fetch, upload=first_upload)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "failed"
    assert conn.rows[0]["media_ids"] == ["11"]
    assert conn.rows[0]["tweet_id"] is None
    conn.rows[0]["status"] = "queued"
    conn.rows[0]["error"] = None
    conn.rows[0]["claimed_at"] = None
    again = Poster(ids=["901"])
    second_fetch, second_upload = _Fetcher(), _Uploader(ids=["22"])
    result = _drain(conn, again, monkeypatch, fetch=second_fetch, upload=second_upload)
    assert second_fetch.urls == [CARD_2]
    assert len(second_upload.calls) == 1
    assert again.calls[0]["media_ids"] == ["11", "22"]
    assert result["posted"] == 1
    assert conn.rows[0]["tweet_id"] == "901"


def test_a_tweet_rate_limit_after_upload_does_not_upload_again(monkeypatch):
    conn = QueueConn([_blank(1, "card", 1, "Tonight's card", media_urls=[CARD])])
    poster = Poster(outcomes=["rate_limited"])
    fetch, upload = _Fetcher(), _Uploader()
    _drain(conn, poster, monkeypatch, fetch=fetch, upload=upload)
    assert len(upload.calls) == 1
    assert conn.rows[0]["status"] == "queued"
    assert conn.rows[0]["media_ids"] == ["11"]
    assert conn.rows[0]["tweet_id"] is None
    again = Poster(ids=["903"])
    result = _drain(conn, again, monkeypatch, fetch=_no_network, upload=_no_network)
    assert result["posted"] == 1
    assert again.calls[0]["media_ids"] == ["11"]
    assert conn.rows[0]["tweet_id"] == "903"


def test_stored_media_ids_are_not_uploaded_again(monkeypatch):
    conn = QueueConn([_blank(
        1, "card", 1, "Tonight's card",
        media_urls=[CARD], media_ids=["11"])])
    poster = Poster(ids=["902"])
    _drain(conn, poster, monkeypatch, fetch=_no_network, upload=_no_network)
    assert poster.calls[0]["media_ids"] == ["11"]
    assert conn.rows[0]["tweet_id"] == "902"


def test_a_row_that_already_has_a_tweet_id_does_not_upload(monkeypatch):
    conn = QueueConn([_blank(
        1, "card", 1, "Tonight's card", status="queued", tweet_id="900",
        media_urls=[CARD], media_ids=["11"])])
    poster = Poster()
    _drain(conn, poster, monkeypatch, fetch=_no_network, upload=_no_network)
    assert poster.calls == []
    assert conn.rows[0]["tweet_id"] == "900"


def test_more_than_four_images_fails_without_uploading(monkeypatch):
    urls = [f"https://cdn.example/{i}.png" for i in range(5)]
    conn = QueueConn([_blank(1, "card", 1, "Tonight's card", media_urls=urls)])
    poster = Poster()
    result = _drain(conn, poster, monkeypatch, fetch=_no_network, upload=_no_network)
    assert poster.calls == []
    assert result["posted"] == 0
    assert conn.rows[0]["status"] == "failed"
    assert "4" in conn.rows[0]["error"]
    assert conn.rows[0]["tweet_id"] is None


def test_a_non_https_image_fails_without_uploading(monkeypatch):
    conn = QueueConn([_blank(
        1, "card", 1, "Tonight's card", media_urls=["http://cdn.example/card.png"])])
    poster = Poster()
    _drain(conn, poster, monkeypatch, fetch=_no_network, upload=_no_network)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "failed"
    assert "https" in conn.rows[0]["error"]


def test_a_rate_limit_after_one_upload_keeps_that_id(monkeypatch):
    conn = QueueConn([_blank(1, "card", 1, "Tonight's card", media_urls=[CARD, CARD_2])])
    poster = Poster()
    upload = _Uploader(rate_at=2)
    _drain(conn, poster, monkeypatch, fetch=_Fetcher(), upload=upload)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "queued"
    assert conn.rows[0]["media_ids"] == ["11"]
    assert conn.rows[0]["tweet_id"] is None


def test_an_upload_rate_limit_requeues_and_does_not_tweet(monkeypatch):
    conn = QueueConn([
        _blank(1, "card", 1, "Tonight's card", media_urls=[CARD]),
        _blank(2, "other", 1, "Later"),
    ])
    poster = Poster()
    upload = _Uploader(rate_at=1)
    result = _drain(conn, poster, monkeypatch, fetch=_Fetcher(), upload=upload)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "queued"
    assert conn.rows[0]["tweet_id"] is None
    assert conn.rows[1]["status"] == "queued"
    assert result["posted"] == 0
    assert any(item["status"] == "queued" for item in result["results"])


def test_a_null_reply_target_keeps_the_thread_chain(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First"),
        _blank(2, "t", 2, "Second"),
    ])
    poster = Poster()
    _drain(conn, poster, monkeypatch)
    assert [c["reply_to"] for c in poster.calls] == [None, "111"]
    assert [c["media_ids"] for c in poster.calls] == [None, None]


def test_a_reply_target_is_used_and_the_next_post_still_chains(monkeypatch):
    conn = QueueConn([
        _blank(1, "t", 1, "First", reply_to_tweet_id="555"),
        _blank(2, "t", 2, "Second"),
    ])
    poster = Poster()
    _drain(conn, poster, monkeypatch)
    assert [c["reply_to"] for c in poster.calls] == ["555", "111"]


def test_a_bad_reply_target_fails_without_posting(monkeypatch):
    conn = QueueConn([_blank(1, "t", 1, "First", reply_to_tweet_id="nope")])
    poster = Poster()
    _drain(conn, poster, monkeypatch, fetch=_no_network, upload=_no_network)
    assert poster.calls == []
    assert conn.rows[0]["status"] == "failed"
    assert "reply_to_tweet_id" in conn.rows[0]["error"]


def test_dry_run_does_not_fetch_or_upload(monkeypatch):
    conn = QueueConn([_blank(1, "card", 1, "Tonight's card", media_urls=[CARD],
                             reply_to_tweet_id="555")])
    poster = Poster()
    result = sp.drain_social_posts(
        conn, dry_run=True, now=NOW, deliver=poster,
        fetch_image=_no_network, upload_image=_no_network)
    assert result["results"][0]["status"] == "would_post"
    assert result["results"][0]["reply_to"] == "555"
    assert poster.calls == []
    assert conn.rows[0]["status"] == "queued"
    assert conn.rows[0]["media_ids"] is None


def test_enqueue_stores_images_and_a_reply_target():
    conn = QueueConn([])
    ids = sp.enqueue(
        conn, "pick-card-2026-10-21", ["Tonight's card"],
        media_urls=[CARD], reply_to_tweet_id="1234567890")
    assert ids == [1]
    assert conn.rows[0]["media_urls"] == [CARD]
    assert conn.rows[0]["reply_to_tweet_id"] == "1234567890"
    assert conn.rows[0]["media_ids"] is None
    assert conn.rows[0]["status"] == "queued"
    with pytest.raises(sp.QueueRejected, match="https"):
        sp.enqueue(conn, "bad-card", ["x"], media_urls=["http://cdn.example/a.png"])
    with pytest.raises(sp.QueueRejected, match="4"):
        sp.enqueue(conn, "too-many", ["x"], media_urls=[f"https://cdn.example/{i}.png" for i in range(5)])
    assert len(conn.rows) == 1


def test_the_media_migration_is_registered_after_the_table():
    from data.view_migrations import ACTIVE_MIGRATIONS
    media = "social_post_media_2026_10_20.sql"
    table = "social_post_queue_2026_10_20.sql"
    assert media in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(table) < ACTIVE_MIGRATIONS.index(media)
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    sql = (ROOT / "data" / "migrations" / media).read_text(encoding="utf-8")
    assert sql.count("$mig$") == 2
    assert sql.index("RETURN;") < sql.index("ALTER TABLE")
    assert "media_urls" in sql and "media_ids" in sql and "reply_to_tweet_id" in sql
    assert "INSERT" not in sql
    assert "all-time-ledger" not in sql


def test_the_cli_can_enqueue_one_image_without_posting(monkeypatch, tmp_path):
    body = tmp_path / "card.txt"
    body.write_text("Tonight's card", encoding="utf-8")
    conn = QueueConn([])
    monkeypatch.setattr("data.db.get_connection", lambda: conn)
    code = sp.main([
        "--enqueue", "--thread-key", "pick-card-2026-10-21",
        "--body-file", str(body),
        "--media-url", CARD,
        "--reply-to", "1234567890",
    ])
    assert code == 0
    assert conn.closed
    assert conn.rows[0]["media_urls"] == [CARD]
    assert conn.rows[0]["reply_to_tweet_id"] == "1234567890"
    assert conn.rows[0]["status"] == "queued"

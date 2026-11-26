"""A book rate limiting or refusing our live reads: the episode rows mike's
machine writes (data/ingestors/book_throttle.py), the readers that feed them
(book_live_boards.py, dk_live_board.py), and the worker's ops alert
(tracking/book_throttle_watch.py).

mike, 2026-11-26: "Can you add a red alert that goes to the ops channel if you
detect that the book is rate limiting or throttling our connection?"
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from data.ingestors import book_live_boards as L
from data.ingestors import book_throttle as T
from data.ingestors import dk_live_board as B
from tracking import book_throttle_watch as W

T0 = datetime(2026, 11, 26, 23, 0, tzinfo=timezone.utc)


def tracker(threshold=3):
    t = [T0]
    tr = T.ThrottleTracker(threshold, clock=lambda: t[0], host="MAHome")
    return tr, t


# ── The tracker ──────────────────────────────────────────────────────────────

def test_one_429_opens_an_episode_at_once_and_a_clean_read_clears_it():
    tr, t = tracker()
    row = tr.observe("fanduel", "NBA", clean=False, reason=T.RATE_LIMITED, status=429, poll_s=1.0)
    assert row is not None and (row["kind"], row["reason"], row["status"], row["poll_s"]) == \
        ("throttled", "rate_limited", 429, 1.0)
    assert tr.observe("fanduel", "NBA", clean=False, reason=T.RATE_LIMITED, status=429) is None   # same episode
    t[0] += timedelta(seconds=40)
    done = tr.observe("fanduel", "NBA", clean=True, reason=None, status=200)
    assert done["kind"] == "cleared" and done["episode"] == row["episode"] and "40 s" in done["detail"]
    assert tr.observe("fanduel", "NBA", clean=True, reason=None, status=200) is None             # healthy: nothing
    assert [r["kind"] for r in tr.pending] == ["throttled", "cleared"]


def test_a_403_opens_only_after_the_readers_own_back_off_count():
    tr, _ = tracker(threshold=3)
    assert tr.observe("betrivers", "NHL", clean=False, reason=T.REFUSED, status=403) is None
    assert tr.observe("betrivers", "NHL", clean=False, reason=T.REFUSED, status=403) is None
    # a 404 between them is a broken page: neither push-back nor a clean answer
    assert tr.observe("betrivers", "NHL", clean=False, reason=None, status=404) is None
    row = tr.observe("betrivers", "NHL", clean=False, reason=T.REFUSED, status=403)
    assert row["kind"] == "throttled" and row["in_a_row"] == 3


def test_a_clean_read_resets_the_count_so_scattered_refusals_never_page():
    tr, _ = tracker(threshold=3)
    for _ in range(5):
        tr.observe("fanduel", "NBA", clean=False, reason=T.REFUSED, status=403)
        tr.observe("fanduel", "NBA", clean=False, reason=T.REFUSED, status=403)
        tr.observe("fanduel", "NBA", clean=True, reason=None, status=200)
    assert tr.pending == []


def test_timeouts_in_a_row_are_possible_throttling():
    tr, _ = tracker(threshold=3)
    rows = [tr.observe("fanduel", "NBA", clean=False, reason=T.reason_for(None, False, answered=False))
            for _ in range(3)]
    assert rows[:2] == [None, None] and rows[2]["reason"] == "no_answer"


def test_reason_for_reads_the_status_and_the_readers_verdict():
    assert T.reason_for(429, False) == "rate_limited"
    assert T.reason_for(403, False) == "refused" and T.reason_for(503, False) == "refused"
    assert T.reason_for(200, True) == "refused"                  # a 200 bot-challenge page
    assert T.reason_for(None, False, answered=False) == "no_answer"
    for s in (200, 400, 404, 500):
        assert T.reason_for(s, False) is None


def test_a_bench_is_recorded_only_inside_an_episode():
    tr, _ = tracker(threshold=5)
    assert tr.backoff("draftkings", "NCAAB", 120) is None      # a run of 500s benches too: not throttling
    for _ in range(5):
        tr.observe("draftkings", "NCAAB", clean=False, reason=T.REFUSED, status=403)
    row = tr.backoff("draftkings", "NCAAB", 120, poll_s=4.0)
    assert row["kind"] == "backoff" and "120 s" in row["detail"]
    assert row["episode"] == tr.open["draftkings"]["episode"]


class Conn:
    def __init__(self, fail=False):
        self.sql, self.fail, self.commits, self.rollbacks = [], fail, 0, 0

    def execute(self, sql, params=None):
        if self.fail and "INSERT INTO book_throttle_events" in sql:
            raise RuntimeError("connection reset")
        self.sql.append((sql, params))
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def inserted(conn):
    cols = T.COLS[1:]
    return [dict(zip(cols, p)) for sql, p in conn.sql if "INSERT INTO book_throttle_events" in sql]


def test_a_failed_write_keeps_the_rows_for_the_next_flush():
    tr, _ = tracker()
    tr.table_ready = True
    tr.observe("fanduel", "NBA", clean=False, reason=T.RATE_LIMITED, status=429)
    bad = Conn(fail=True)
    assert tr.flush(bad) == 0 and bad.rollbacks == 1 and len(tr.pending) == 1
    good = Conn()
    assert tr.flush(good) == 1 and tr.pending == []
    assert [(r["book"], r["kind"], r["status"], r["host"]) for r in inserted(good)] == \
        [("fanduel", "throttled", 429, "MAHome")]


# ── The other books' thread ──────────────────────────────────────────────────

class Resp:
    def __init__(self, code, text=""):
        self.status_code, self.text = code, text


class Sess:
    def __init__(self, answer):
        self.answer, self.urls = answer, []

    def get(self, url, timeout=None, headers=None):
        self.urls.append(url)
        a = self.answer(url)
        if isinstance(a, Exception):
            raise a
        return a


def book_feeds(answer, live=("NBA",)):
    t = [0.0]
    conn, sess = Conn(), Sess(answer)
    f = L.BookFeeds(lambda: conn, lambda: list(live), session_factory=lambda: sess, resolvers={},
                    odds_log=lambda c, r: 0, monotonic=lambda: t[0], sleep=lambda _s: None,
                    clock=lambda: T0)
    f.ready, f.games_live = True, (1e18, set())
    f.throttle.table_ready = True
    return f, conn, t


def test_a_book_answering_429_writes_one_throttled_row_then_cleared():
    state = {"code": 429}
    f, conn, t = book_feeds(lambda url: Resp(state["code"], "Too Many Requests") if "fanduel" in url
                            else Resp(200, "{}"))
    f.pass_once()
    t[0] += 60
    rows = [r for r in inserted(conn) if r["book"] == "fanduel"]
    assert [(r["kind"], r["reason"], r["status"], r["poll_s"]) for r in rows] == \
        [("throttled", "rate_limited", 429, L.POLL_SEC)]
    state["code"] = 200
    f.pass_once()
    rows = [r for r in inserted(conn) if r["book"] == "fanduel"]
    assert [r["kind"] for r in rows] == ["throttled", "cleared"]


def test_three_refusals_write_the_episode_and_the_bench():
    f, conn, t = book_feeds(lambda url: Resp(403, "<html>Access Denied</html>") if "fanduel" in url
                            else Resp(200, "{}"))
    for _ in range(L.REFUSALS_BEFORE_BACKOFF):
        f.pass_once()
        t[0] += 60
    rows = [r for r in inserted(conn) if r["book"] == "fanduel"]
    assert [r["kind"] for r in rows] == ["throttled", "backoff"]
    assert rows[0]["in_a_row"] == L.REFUSALS_BEFORE_BACKOFF and rows[0]["status"] == 403


def test_one_shared_answer_is_one_observation_not_one_per_sport():
    """NBA, NCAAB and NCAABW share BetRivers' one answer: two refused answers
    are two refusals, not six, so no episode opens."""
    f, conn, t = book_feeds(lambda url: Resp(403, "denied") if "kambicdn" in url else Resp(200, "{}"),
                            live=("NBA", "NCAAB", "NCAABW"))
    for _ in range(L.REFUSALS_BEFORE_BACKOFF - 1):
        f.pass_once()
        t[0] += 60
    assert [r for r in inserted(conn) if r["book"] == "betrivers"] == []
    assert f.throttle.in_a_row["betrivers"] == L.REFUSALS_BEFORE_BACKOFF - 1


def test_a_healthy_book_writes_no_throttle_rows():
    f, conn, t = book_feeds(lambda url: Resp(200, "{}"))
    for _ in range(5):
        f.pass_once()
        t[0] += 60
    assert inserted(conn) == []


def test_the_board_restarts_when_the_throttle_module_changes():
    assert "data/ingestors/book_throttle.py" in B.FEED_FILES


# ── DraftKings' board ────────────────────────────────────────────────────────

def test_draftkings_refusals_open_an_episode_and_the_bench_is_recorded():
    tr, _ = tracker(threshold=B.REFUSALS_BEFORE_BACKOFF)
    tr.table_ready = True
    conn = Conn()
    plan = B.Pacer(["NCAAB"], 1.0, clock=lambda: 0.0)

    class Board:
        refusals = 0
    board = Board()
    benched = []
    for _ in range(B.REFUSALS_BEFORE_BACKOFF):
        board.refusals += 1
        res = {"ok": False, "live": 0, "matched": 0, "written": 0, "detail": "HTTP 403", "status": 403}
        backed = plan.done("NCAAB", res, board)
        benched.append(backed)
        B.note_throttle(tr, "NCAAB", res, 1.0, backed, lambda: conn)
    assert benched == [False] * (B.REFUSALS_BEFORE_BACKOFF - 1) + [True]
    assert [(r["book"], r["kind"]) for r in inserted(conn)] == [("draftkings", "throttled"),
                                                                ("draftkings", "backoff")]
    ok = {"ok": True, "live": 1, "matched": 1, "written": 1, "status": 200}
    B.note_throttle(tr, "NCAAB", ok, 1.0, False, lambda: conn)
    assert inserted(conn)[-1]["kind"] == "cleared"


def test_draftkings_not_listed_and_unparsable_reads_are_not_push_back():
    tr, _ = tracker(threshold=1)
    tr.table_ready = True
    conn = Conn()
    B.note_throttle(tr, "EUROLEAGUE", {"ok": True, "detail": B.NOT_LISTED, "asked": False}, 30, False,
                    lambda: conn)
    B.note_throttle(tr, "NBA", {"ok": False, "detail": "unparsable board: ValueError"}, 1.0, False,
                    lambda: conn)
    assert inserted(conn) == [] and tr.in_a_row.get("draftkings", 0) == 0


def test_a_draftkings_timeout_counts_as_no_answer():
    tr, _ = tracker(threshold=1)
    tr.table_ready = True
    conn = Conn()
    B.note_throttle(tr, "NBA", {"ok": False, "detail": "Timeout: read timed out", "status": None}, 1.0,
                    False, lambda: conn)
    assert [r["reason"] for r in inserted(conn)] == ["no_answer"]


def test_note_throttle_never_raises():
    tr, _ = tracker(threshold=1)

    def boom():
        raise RuntimeError("no database")
    B.note_throttle(tr, "NBA", {"ok": False, "detail": "HTTP 429", "status": 429}, 1.0, False, boom)


# ── The worker's ops alert ───────────────────────────────────────────────────

class WatchConn:
    """Answers the watch's four reads from in-memory tables."""

    def __init__(self, events, raw_ok_books=("fanduel",), table=True):
        self.events, self.raw_ok, self.table = events, set(raw_ok_books), table
        self.sent: set[tuple] = set()
        self._rows = []

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            self._rows = [(self.table,)]
        elif "FROM book_throttle_events" in sql:
            since = params[0]
            self._rows = [tuple(e[c] for c in W.COLS) for e in self.events if e["at"] > since]
        elif "SELECT lock_key FROM push_sent" in sql:
            self._rows = [(k,) for k, kind in self.sent if k in params[2]]
        elif "FROM book_live_raw" in sql:
            self._rows = [(1,)] if params[0] in self.raw_ok else []
        elif "INSERT INTO push_sent" in sql:
            self.sent.add((params[0], params[1]))
            self._rows = []
        return self

    def fetchall(self):
        return self._rows

    def commit(self):
        pass

    def rollback(self):
        pass


def ev(i, kind, book="fanduel", at=T0, reason="rate_limited", status=429, detail=""):
    return {"id": i, "at": at, "host": "MAHome", "book": book, "sport": "NBA", "kind": kind,
            "reason": reason, "status": status, "in_a_row": 1, "poll_s": 1.0,
            "episode": f"{book}|{T0.isoformat()}", "detail": detail}


@pytest.fixture
def posts(monkeypatch):
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "https://ops.example/webhook")
    sent = []
    return sent, (lambda url, payload: sent.append((url, payload)) or "msg-id")


def test_a_new_episode_posts_one_red_alert_to_ops_and_never_again(posts):
    sent, post = posts
    conn = WatchConn([ev(1, "throttled")])
    r = W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=1), post=post)
    assert len(r["alerted"]) == 1 and len(sent) == 1
    url, payload = sent[0]
    emb = payload["embeds"][0]
    assert url == "https://ops.example/webhook"
    assert emb["color"] == 0xE74C3C                                 # red
    assert "FanDuel is rate limiting our live reads" in emb["title"]
    assert "HTTP 429" in emb["description"] and "1 s" in emb["description"]
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=3), post=post)
    assert len(sent) == 1                                          # ledgered: no second page


def test_the_all_clear_is_green_and_posts_once(posts):
    sent, post = posts
    conn = WatchConn([ev(1, "throttled")])
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=1), post=post)
    conn.events.append(ev(2, "cleared", at=T0 + timedelta(minutes=5), detail="answered cleanly again after 300 s"))
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=6), post=post)
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=8), post=post)
    assert len(sent) == 2
    emb = sent[1][1]["embeds"][0]
    assert emb["color"] == 0x2ECC71 and "answering our live reads again" in emb["title"]


def test_an_episode_that_cleared_between_ticks_is_one_red_message_saying_so(posts):
    sent, post = posts
    conn = WatchConn([ev(1, "throttled"), ev(2, "cleared", at=T0 + timedelta(seconds=20),
                                               detail="answered cleanly again after 20 s")])
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=1), post=post)
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=3), post=post)
    assert len(sent) == 1
    emb = sent[0][1]["embeds"][0]
    assert emb["color"] == 0xE74C3C and "(answering again)" in emb["title"]
    assert "after 20 s" in emb["description"]


def test_a_book_that_never_answered_is_a_standing_block_not_a_page(posts):
    sent, post = posts
    conn = WatchConn([ev(1, "throttled", book="williamhill_us", reason="refused", status=403)],
                     raw_ok_books=())
    r = W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=1), post=post)
    assert sent == [] and len(r["skipped"]) == 1


def test_draftkings_always_pages_and_names_the_loop_that_reads_it(posts):
    sent, post = posts
    conn = WatchConn([ev(1, "throttled", book="draftkings", reason="refused", status=403)], raw_ok_books=())
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=1), post=post)
    emb = sent[0][1]["embeds"][0]
    assert "DraftKings is refusing our live reads" in emb["title"] and "NCAAB" in emb["description"]


def test_a_failed_post_is_not_ledgered_and_is_tried_again(posts):
    sent, post = posts
    conn = WatchConn([ev(1, "throttled")])
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=1), post=lambda u, p: None)
    assert conn.sent == set()
    W.run_book_throttle_watch(conn=conn, now=T0 + timedelta(minutes=3), post=post)
    assert len(sent) == 1


def test_no_table_yet_and_a_quiet_night_post_nothing(posts):
    sent, post = posts
    assert W.run_book_throttle_watch(conn=WatchConn([], table=False), now=T0, post=post)["alerted"] == []
    assert W.run_book_throttle_watch(conn=WatchConn([]), now=T0, post=post)["alerted"] == []
    assert sent == []


def test_the_watch_never_raises():
    class Broken:
        def execute(self, *a, **k):
            raise RuntimeError("down")

        def rollback(self):
            raise RuntimeError("down")
    r = W.run_book_throttle_watch(conn=Broken(), now=T0, post=lambda u, p: "x")
    assert r["alerted"] == []


def test_the_watch_is_scheduled_on_the_pipeline_service():
    import scheduler
    assert "book_throttle_watch" in scheduler._PIPELINE_JOBS
    src = open(scheduler.__file__, encoding="utf-8").read()
    assert 'id="book_throttle_watch"' in src and "run_book_throttle_watch," in src


def test_the_test_alert_is_the_real_red_and_green_message_titled_test(posts):
    sent, post = posts
    r = W.post_test_alerts(post=post)
    assert r == {"red_posted": True, "green_posted": True}
    red, green = (p["embeds"][0] for _u, p in sent)
    assert all(u == "https://ops.example/webhook" for u, _p in sent)
    assert red["color"] == 0xE74C3C and red["title"].endswith("TEST: FanDuel is rate limiting our live reads")
    assert green["color"] == 0x2ECC71 and "TEST: FanDuel is answering" in green["title"]
    assert "HTTP 429" in red["description"] and "Test message" in red["description"]


def test_the_test_alert_is_an_allowlisted_job_and_declared_once():
    import json
    from tracking import job_queue as q
    fn, validate = q.JOBS["book_throttle_test_alert"]
    assert validate({}) == {}
    with pytest.raises(ValueError):
        validate({"x": 1})
    declared = json.load(open("jobs/declared_jobs.json", encoding="utf-8"))
    assert [d["key"] for d in declared if d["job_type"] == "book_throttle_test_alert"] == \
        ["book-throttle-test-alert-2026-11-26"]

"""The @SignalBasePicks profile update.

One queued row, applied once, by the same 5-minute job as the post queue.
Pick posts, recap posts, and the post drain do not call it.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tracking import social_profile as sp
from tracking.x_publisher import ProfileUpdate

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "social_profile_update_2026_10_20.sql"
NOW = datetime(2026, 10, 20, 23, 0, tzinfo=timezone.utc)

NAME = "SignalBase | Model Picks + CLV"
DESC = (
    "Model-driven picks: NHL, NFL, CFB, NBA & more. Every posted pick graded, "
    "every closing line tracked. Full record below. Discord: discord.gg/Sge4Djj2xT · 21+"
)
URL = (
    "https://docs.google.com/spreadsheets/d/1FaUkZnjirMrh0G3Je3RpNoO6d9wq6CcKGZr9bbSovXo/"
    "edit?usp=sharing"
)


def _creds(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(key, "x")


class _Rows:
    def __init__(self, records):
        self._records = records

    def fetchall(self):
        return list(self._records)

    def fetchone(self):
        return self._records[0] if self._records else None


class ProfileConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        params = tuple(params or ())
        if sql == sp.LOAD_SQL:
            queued = sorted((r for r in self.rows if r["status"] == "queued"),
                            key=lambda r: r["id"])
            return _Rows([(r["id"],) for r in queued])
        if sql == sp.CLAIM_SQL:
            row_id = params[0]
            for row in self.rows:
                if row["id"] == row_id and row["status"] == "queued":
                    row["status"] = "failed"
                    row["error"] = "claimed"
                    return _Rows([(row["id"], row["name"], row["description"], row["url"])])
            return _Rows([])
        if sql == sp.FINISH_SQL:
            status, response, error, applied_at, row_id = params
            for row in self.rows:
                if (row["id"] == row_id and row["status"] == "failed"
                        and row["error"] == "claimed"):
                    row.update(status=status, response=response, error=error,
                               applied_at=applied_at)
                    return _Rows([(row["id"],)])
            return _Rows([])
        if sql == sp.RELEASE_SQL:
            row_id = params[0]
            for row in self.rows:
                if (row["id"] == row_id and row["status"] == "failed"
                        and row["error"] == "claimed"):
                    row["status"] = "queued"
                    row["error"] = None
                    return _Rows([(row["id"],)])
            return _Rows([])
        raise AssertionError(sql)

    def commit(self):
        return None


def _row(**overrides):
    row = {
        "id": 1, "name": NAME, "description": DESC, "url": URL,
        "status": "queued", "response": None, "error": None, "applied_at": None,
    }
    row.update(overrides)
    return row


class Updater:
    def __init__(self, outcome="updated", detail="", body='{"name":"ok"}'):
        self.calls = []
        self.outcome = outcome
        self.detail = detail
        self.body = body

    def __call__(self, *, name, description, url):
        self.calls.append({"name": name, "description": description, "url": url})
        if self.outcome == "raise":
            raise RuntimeError("boom")
        return ProfileUpdate(self.outcome, self.detail, self.body)


def _drain(conn, updater, monkeypatch):
    _creds(monkeypatch)
    return sp.drain_social_profile(conn, update=updater, now=NOW)


def test_a_queued_profile_is_applied_once(monkeypatch):
    conn = ProfileConn([_row()])
    updater = Updater()
    result = _drain(conn, updater, monkeypatch)
    assert result["applied"] == 1
    assert updater.calls == [{"name": NAME, "description": DESC, "url": URL}]
    assert conn.rows[0]["status"] == "done"
    assert conn.rows[0]["response"] == '{"name":"ok"}'
    assert conn.rows[0]["error"] is None
    assert conn.rows[0]["applied_at"] == NOW
    again = Updater()
    second = _drain(conn, again, monkeypatch)
    assert second["applied"] == 0
    assert again.calls == []


def test_a_4xx_is_failed_and_not_retried(monkeypatch):
    conn = ProfileConn([_row()])
    updater = Updater(outcome="rejected", detail="HTTP 403 Forbidden", body="Forbidden")
    _drain(conn, updater, monkeypatch)
    assert conn.rows[0]["status"] == "failed"
    assert conn.rows[0]["applied_at"] is None
    assert "403" in conn.rows[0]["error"]
    assert conn.rows[0]["response"] == "Forbidden"
    again = Updater()
    _drain(conn, again, monkeypatch)
    assert again.calls == []


def test_a_429_is_a_4xx_and_is_not_retried(monkeypatch):
    conn = ProfileConn([_row()])
    updater = Updater(outcome="rejected", detail="HTTP 429 slow down")
    _drain(conn, updater, monkeypatch)
    assert conn.rows[0]["status"] == "failed"
    again = Updater()
    _drain(conn, again, monkeypatch)
    assert again.calls == []


def test_a_5xx_is_failed_and_not_retried(monkeypatch):
    conn = ProfileConn([_row()])
    updater = Updater(outcome="transport", detail="HTTP 503 unavailable")
    _drain(conn, updater, monkeypatch)
    assert conn.rows[0]["status"] == "failed"
    assert "503" in conn.rows[0]["error"]
    again = Updater()
    _drain(conn, again, monkeypatch)
    assert again.calls == []


def test_a_raised_update_is_failed_and_not_retried(monkeypatch):
    conn = ProfileConn([_row()])
    _drain(conn, Updater(outcome="raise"), monkeypatch)
    assert conn.rows[0]["status"] == "failed"
    assert "boom" in conn.rows[0]["error"]
    again = Updater()
    _drain(conn, again, monkeypatch)
    assert again.calls == []


def test_the_kill_switch_leaves_the_row_queued(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "0")
    for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(key, "x")
    conn = ProfileConn([_row()])
    updater = Updater()
    result = sp.drain_social_profile(conn, update=updater, now=NOW)
    assert result["status"] == "skipped"
    assert updater.calls == []
    assert conn.rows[0]["status"] == "queued"


def test_a_missing_table_is_a_no_op(monkeypatch):
    _creds(monkeypatch)

    class _Gone:
        def execute(self, *args):
            raise RuntimeError('relation "social_profile_update" does not exist')

        def commit(self):
            return None

    result = sp.drain_social_profile(_Gone(), update=Updater(), now=NOW)
    assert result["status"] == "no_table"
    assert result["applied"] == 0


def test_a_skipped_update_puts_the_row_back(monkeypatch):
    conn = ProfileConn([_row()])
    updater = Updater(outcome="skipped", detail="RUN_X_PUBLISHER=0")
    result = _drain(conn, updater, monkeypatch)
    assert result["applied"] == 0
    assert conn.rows[0]["status"] == "queued"
    assert conn.rows[0]["error"] is None


def test_form_params_are_in_the_signature_and_not_in_the_header():
    from tracking import x_publisher as xp
    creds = ("ck", "cs", "tok", "sec")
    plain = xp._auth_header("POST", xp.X_PROFILE_URL, creds, nonce="n", timestamp="1")
    empty = xp._auth_header(
        "POST", xp.X_PROFILE_URL, creds, nonce="n", timestamp="1", extra_params={})
    formed = xp._auth_header(
        "POST", xp.X_PROFILE_URL, creds, nonce="n", timestamp="1",
        extra_params={"name": NAME, "description": DESC, "url": URL})
    assert plain == empty
    assert formed != plain
    assert "oauth_signature" in formed
    assert "name=" not in formed
    assert "description" not in formed
    assert "discord.gg" not in formed
    base = xp.signature_base_string("POST", xp.X_PROFILE_URL, {
        "oauth_consumer_key": "ck",
        "oauth_nonce": "n",
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": "1",
        "oauth_token": "tok",
        "oauth_version": "1.0",
        "name": NAME,
        "description": DESC,
        "url": URL,
    })
    assert xp._quote(xp._quote(NAME)) in base
    assert xp._quote(xp._quote(DESC)) in base
    assert xp._quote(xp._quote(URL)) in base


def test_update_profile_posts_the_form_and_a_4xx_does_not_look_like_success(monkeypatch):
    from tracking import x_publisher as xp
    _creds(monkeypatch)
    sent = []

    class _R:
        def __init__(self, status, text):
            self.status_code = status
            self.text = text

    def _post(url, data=None, headers=None, timeout=None):
        sent.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
        if len(sent) == 1:
            return _R(200, '{"screen_name":"SignalBasePicks","name":"SignalBase"}')
        return _R(403, '{"errors":[{"message":"Your credentials do not allow access to this resource"}]}')

    monkeypatch.setattr(xp.requests, "post", _post)
    ok = xp.update_profile(name=NAME, description=DESC, url=URL)
    assert ok.outcome == "updated"
    assert sent[0]["url"] == "https://api.x.com/1.1/account/update_profile.json"
    assert sent[0]["data"] == {"name": NAME, "description": DESC, "url": URL}
    assert sent[0]["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert sent[0]["headers"]["Authorization"].startswith("OAuth ")
    assert "name=" not in sent[0]["headers"]["Authorization"]
    refused = xp.update_profile(name=NAME, description=DESC, url=URL)
    assert refused.outcome == "rejected"
    assert "403" in refused.detail
    assert "do not allow access" in refused.detail
    assert xp.update_profile(name="x" * 51).outcome == "rejected"
    assert len(sent) == 2


def test_a_tweet_still_signs_without_form_params(monkeypatch):
    from tracking import x_publisher as xp
    _creds(monkeypatch)
    seen = {}
    real = xp._auth_header

    def _header(*args, **kwargs):
        seen["extra"] = kwargs.get("extra_params")
        return real(*args, **kwargs)

    class _R:
        status_code = 201
        text = ""

        def json(self):
            return {"data": {"id": "55"}}

    monkeypatch.setattr(xp, "_auth_header", _header)
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: _R())
    assert xp.deliver_tweet("hello").tweet_id == "55"
    assert seen["extra"] is None


def test_pick_recap_and_the_post_drain_do_not_update_the_profile():
    from tracking import social_posts
    from tracking import x_publisher as xp
    for fn in (xp._post_released_picks, xp.notify_x_results, xp.notify_x_period,
               xp.deliver_tweet, xp.post_tweet):
        src = inspect.getsource(fn)
        assert "update_profile" not in src, fn.__name__
        assert "X_PROFILE_URL" not in src, fn.__name__
    drain = inspect.getsource(social_posts.drain_social_posts)
    assert "drain_social_profile" not in drain
    assert "update_profile" not in drain


def test_the_five_minute_job_applies_the_profile_and_keeps_its_trigger():
    import scheduler
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert src.count("CronTrigger(hour=6, minute=0, timezone=TIMEZONE)") == 1
    job = src[src.index("def run_social_post_queue"):src.index("def run_job_queue")]
    assert "drain_social_posts" in job
    assert "drain_social_profile" in job
    jobs = {j.id: j for j in scheduler.build_scheduler().get_jobs()}
    assert "*/5" in str(jobs["social_post_queue"].trigger)
    daily = str(jobs["daily_pipeline"].trigger)
    assert "hour='6'" in daily
    assert "minute='0'" in daily


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_the_seed_fits_and_the_guard_uses_to_regclass():
    from data.view_migrations import ACTIVE_MIGRATIONS
    sql = MIG.read_text(encoding="utf-8")
    code = _code(sql)
    assert len(NAME) <= 50
    assert len(DESC) <= 160
    assert len(NAME) == 30
    assert len(DESC) == 156
    assert len(URL) == 100
    assert NAME in sql and DESC in sql and URL in sql
    assert "::regclass" not in code
    assert "to_regclass('public.social_profile_update') IS NOT NULL" in code
    assert code.index("RETURN;") < code.index("CREATE TABLE")
    assert code.index("RETURN;") < code.index("INSERT INTO public.social_profile_update")
    assert "WHERE NOT EXISTS (SELECT 1 FROM public.social_profile_update)" in code
    assert code.count("$mig$") == 2
    name = "social_profile_update_2026_10_20.sql"
    assert name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index("social_post_media_2026_10_20.sql") < ACTIVE_MIGRATIONS.index(name)
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    docs = (ROOT / "docs" / "social_posts.md").read_text(encoding="utf-8")
    assert NAME in docs and DESC in docs and URL in docs


def test_profile_migration_applies_on_an_empty_database_and_does_not_reseed():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin
    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    try:
        dsn = cluster.start()
    except Exception as exc:
        cluster.stop()
        pytest.skip(f"scratch cluster did not start: {exc}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    sql = MIG.read_text(encoding="utf-8")
    try:
        cur = conn.cursor()
        cur.execute("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                CREATE ROLE anon NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                CREATE ROLE authenticated NOLOGIN;
              END IF;
            END $$
        """)
        cur.execute(sql)
        cur.execute(sql)
        cur.execute("SELECT name, description, url, status FROM public.social_profile_update ORDER BY id")
        assert cur.fetchall() == [(NAME, DESC, URL, "queued")]
        cur.execute("DELETE FROM public.social_profile_update")
        cur.execute(sql)
        cur.execute("SELECT count(*) FROM public.social_profile_update")
        assert cur.fetchone()[0] == 0
    finally:
        conn.close()
        cluster.stop()

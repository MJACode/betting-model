"""Tests for the real-time pipeline monitor (monitoring/).

The load-bearing ones are the redaction tests and the bind guard: this feature
persists every outbound URL and, on the worker, serves pipeline internals over a
public Railway URL. Both are places where a mistake is silent.
"""

import http.server
import json
import re
import threading
import time
import urllib.error
import urllib.request

import pytest

from monitoring import probe, registry, server, store


# ── registry ─────────────────────────────────────────────────────────────────

def test_specific_host_beats_generic():
    assert registry.classify("https://sports.core.api.espn.com/v2/x")[1] == "ESPN (core)"
    assert registry.classify("https://site.api.espn.com/y")[1] == "ESPN (site)"
    # a host we have not named still classifies (as itself) rather than vanishing
    assert registry.classify("https://api.newfeed.io/v1")[1] == "api.newfeed.io"


def test_paid_apis_are_the_metered_ones():
    paid = registry.paid_apis()
    assert "The Odds API" in paid and "CFBD" in paid and "DataGolf" in paid
    assert "ESPN (site)" not in paid


def test_garbage_url_does_not_raise():
    assert registry.classify("not a url")[1] in ("other", "")


# ── redaction ────────────────────────────────────────────────────────────────

def test_query_is_dropped_except_the_allowlist():
    path, sport = probe._redact(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
        "?apiKey=SECRET&markets=h2h&regions=us&daysFrom=3")
    assert "SECRET" not in path and "apiKey" not in path
    assert "markets=h2h" in path and "regions=us" in path
    assert sport == "MLB"


def test_sport_is_read_from_the_path_when_absent_from_params():
    assert probe._redact("https://api.x.com/v4/sports/americanfootball_ncaaf/odds")[1] == "NCAAF"


@pytest.mark.parametrize("raw,forbidden", [
    ("Max retries exceeded with url: /v1/x?key=SECRET (Caused by ...)", "SECRET"),
    ("HTTPSConnectionPool: https://a.com/b?apiKey=SECRET&x=1 failed", "SECRET"),
    ("auth failed token=SECRET", "SECRET"),
])
def test_error_text_is_scrubbed(raw, forbidden):
    assert forbidden not in (probe._scrub(raw) or "")


def test_scrub_keeps_the_useful_part():
    out = probe._scrub("ConnectionError: Max retries exceeded with url: /v1/x?key=S")
    assert "ConnectionError" in out and "Max retries" in out


# ── credits ──────────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, used=None, remaining=None):
        self.headers = {}
        if used is not None:
            self.headers["x-requests-used"] = str(used)
        if remaining is not None:
            self.headers["x-requests-remaining"] = str(remaining)


def test_credits_are_the_delta_of_requests_used(monkeypatch):
    monkeypatch.setattr(probe, "_last_used", None, raising=False)
    assert probe._credits_from(_Resp(100, 900)) == (None, 900.0)   # no baseline yet
    assert probe._credits_from(_Resp(104, 896)) == (4.0, 896.0)
    assert probe._credits_from(_Resp(105, 895)) == (1.0, 895.0)


def test_billing_reset_reports_no_credits_rather_than_a_negative(monkeypatch):
    monkeypatch.setattr(probe, "_last_used", 500.0, raising=False)
    credits, remaining = probe._credits_from(_Resp(3, 4999997))
    assert credits is None and remaining == 4999997.0


def test_missing_headers_are_not_an_error(monkeypatch):
    monkeypatch.setattr(probe, "_last_used", None, raising=False)
    assert probe._credits_from(_Resp()) == (None, None)


# ── the patch ────────────────────────────────────────────────────────────────

@pytest.fixture
def http_server():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            code = 503 if self.path.startswith("/boom") else 200
            body = b'{"ok":true}'
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("x-requests-used", self.headers.get("X-Used", "10"))
            self.send_header("x-requests-remaining", "999")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _drain_dicts():
    return [dict(zip(store.INSERT_COLUMNS, r)) for r in probe._drain()]


def test_probe_records_without_changing_the_response(http_server, monkeypatch):
    import requests
    monkeypatch.setattr(probe, "_last_used", None, raising=False)
    probe.install("test", start_writer=False)
    probe._drain()

    r = requests.get(http_server + "/v4/sports/baseball_mlb/odds",
                     params={"apiKey": "SECRET", "markets": "h2h"})
    assert r.status_code == 200 and r.json() == {"ok": True}   # unchanged

    rows = _drain_dicts()
    assert len(rows) == 1
    assert rows[0]["status"] == 200 and rows[0]["ok"] is True
    assert rows[0]["api"] == "other" or rows[0]["host"].startswith("127.0.0.1")
    assert "SECRET" not in json.dumps(rows, default=str)


def test_probe_records_failures_and_transport_errors(http_server):
    import requests
    probe.install("test", start_writer=False)
    probe._drain()

    requests.get(http_server + "/boom")
    with pytest.raises(Exception):
        requests.get("http://127.0.0.1:1/dead", params={"key": "SECRET"}, timeout=0.4)

    rows = _drain_dicts()
    assert [r["status"] for r in rows] == [503, None]
    assert rows[0]["ok"] is False and rows[1]["ok"] is False
    assert rows[1]["error"]                       # the transport failure is captured
    assert "SECRET" not in json.dumps(rows, default=str)


def test_install_is_idempotent():
    probe.install("test", start_writer=False)
    assert probe.install("test", start_writer=False) is False


def test_kill_switch(monkeypatch):
    monkeypatch.setenv("PIPELINE_TELEMETRY", "0")
    monkeypatch.setattr(probe, "_installed", False, raising=False)
    assert probe.install("test", start_writer=False) is False


def test_queue_overflow_drops_the_oldest_not_the_newest(monkeypatch):
    import queue as _q
    monkeypatch.setattr(probe, "_q", _q.Queue(maxsize=3), raising=False)
    for i in range(6):
        probe._enqueue((i,))
    kept = [r[0] for r in probe._drain()]
    assert kept == [3, 4, 5]


def test_insert_sql_and_columns_cannot_drift():
    assert store.INSERT_SQL.count("?") == len(store.INSERT_COLUMNS)
    cols = re.search(r"\(([^)]*)\)\s*VALUES", store.INSERT_SQL, re.S).group(1)
    assert [c.strip() for c in cols.split(",")] == list(store.INSERT_COLUMNS)


# ── server ───────────────────────────────────────────────────────────────────

class FakeConn:
    """Every read in store.py goes through conn.execute(...).fetchall()."""
    def __init__(self, rows=()):
        self.rows = rows
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append(sql)
        outer = self

        class C:
            def fetchall(self_inner):
                return list(outer.rows)
            def fetchone(self_inner):
                return (outer.rows or [None])[0]
        return C()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_store_reads_never_raise_on_a_broken_connection():
    class Broken(FakeConn):
        def execute(self, sql, params=None):
            raise RuntimeError("connection closed")

    c = Broken()
    assert store.recent_calls(c) == []
    assert store.api_rollup(c) == []
    assert store.health(c) == []
    assert store.quota(c) is None
    assert store.prune(c) == 0


@pytest.fixture
def live_server(monkeypatch):
    monkeypatch.setattr(server, "_connect", lambda: FakeConn())
    srv = server.build_server("127.0.0.1", 0, "s3cret")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def test_refuses_a_public_bind_without_a_token():
    with pytest.raises(RuntimeError, match="MONITOR_TOKEN"):
        server.build_server("0.0.0.0", 0, None)


def test_loopback_without_a_token_is_allowed():
    srv = server.build_server("127.0.0.1", 0, None)
    srv.server_close()


def test_token_is_required(live_server):
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(live_server + "/api/snapshot")
    assert e.value.code == 401
    with pytest.raises(urllib.error.HTTPError):
        _get(live_server + "/api/snapshot?token=wrong")
    status, body = _get(live_server + "/api/snapshot?token=s3cret")
    assert status == 200 and "cursors" in json.loads(body)


def test_healthz_needs_no_token(live_server):
    status, body = _get(live_server + "/healthz")
    assert status == 200 and json.loads(body)["ok"] is True


def test_dashboard_is_served(live_server):
    status, body = _get(live_server + "/?token=s3cret")
    assert status == 200 and b"<canvas id=\"timeline\"" in body


def test_stream_opens_with_a_snapshot_event(live_server):
    req = urllib.request.Request(live_server + "/api/stream?token=s3cret")
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.headers["Content-Type"] == "text/event-stream"
        deadline = time.time() + 5
        chunk = b""
        while b"\n\n" not in chunk and time.time() < deadline:
            chunk += r.read(1)
    assert chunk.startswith(b"event: snapshot\ndata: ")
    payload = json.loads(chunk.split(b"data: ", 1)[1])
    assert set(payload) >= {"calls", "picks", "rollup", "health", "cursors"}


# ── curl_cffi (a second HTTP stack, used by the DK freshness collector) ──────

curl_cffi = pytest.importorskip("curl_cffi", reason="curl_cffi is optional")


def test_curl_cffi_calls_are_recorded_and_redacted(http_server):
    """Patching requests does not reach curl_cffi — it replays a browser TLS
    fingerprint through its own stack. A feed that records nothing looks exactly
    like a feed that is down, which is the confusion this dashboard removes."""
    from curl_cffi import requests as cc

    probe.install("test", start_writer=False)
    probe._patch_curl_cffi()
    probe._drain()

    s = cc.Session()
    r = s.get(http_server + "/x", params={"key": "SECRET", "sport": "baseball_mlb"})
    assert r.status_code == 200 and r.json() == {"ok": True}   # unchanged

    rows = _drain_dicts()
    assert len(rows) == 1 and rows[0]["ok"] is True and rows[0]["sport"] == "MLB"
    assert "SECRET" not in json.dumps(rows, default=str)


def test_curl_cffi_is_patched_only_once(http_server):
    from curl_cffi import requests as cc

    probe.install("test", start_writer=False)
    probe._patch_curl_cffi()
    probe._patch_curl_cffi()          # a second install must not double-wrap
    probe._drain()

    cc.Session().get(http_server + "/x")
    assert len(probe._drain()) == 1


# ── coverage tripwire ────────────────────────────────────────────────────────
# The probe only sees a process that installs it, and the scheduler shells out
# for everything. A new job added without the two-line bootstrap is invisible —
# and invisible looks exactly like "that feed is down". These are source-level
# checks because the failure is silent at runtime.

from pathlib import Path                                            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Every long-running or scheduler-invoked entrypoint that makes HTTP calls.
INSTRUMENTED_ENTRYPOINTS = [
    "run_pipeline.py",
    "scheduler.py",
    "data/ingestors/live_trigger_orchestrator.py",
    "ncaaf_live/gameday.py",
    "nfl/live_model/workers/gameday.py",
    "nfl/scripts/weekly_wind_card.py",
    "nfl/scripts/daily_opener_card.py",
    "scripts/nfl_pick_monitor.py",
    "scripts/nfl_prop_market_card.py",
]


@pytest.mark.parametrize("rel", INSTRUMENTED_ENTRYPOINTS)
def test_entrypoint_installs_the_probe(rel):
    src = (ROOT / rel).read_text()
    assert "monitoring.probe import install" in src, (
        f"{rel} makes HTTP calls but never installs the telemetry probe — its "
        f"traffic would be invisible on the dashboard"
    )


def test_scheduler_does_not_invoke_an_uninstrumented_script():
    """Any `python -m scripts.X` the scheduler runs must be in the list above."""
    sched = (ROOT / "scheduler.py").read_text()
    referenced = set(re.findall(r'"(scripts\.[a-z_]+)"', sched))
    listed = {e.replace("/", ".").removesuffix(".py") for e in INSTRUMENTED_ENTRYPOINTS}
    # nfl_wind_publisher is DB-only (no HTTP), so it is legitimately exempt.
    exempt = {"scripts.nfl_wind_publisher"}
    missing = referenced - listed - exempt
    assert not missing, f"scheduler runs {missing} with no telemetry probe"


def test_probe_bootstraps_are_guarded():
    """A monitoring import failure must never stop the process it rides in."""
    for rel in INSTRUMENTED_ENTRYPOINTS:
        src = (ROOT / rel).read_text()
        i = src.index("monitoring.probe import install")
        window = src[max(0, i - 400):i + 400]
        assert "try:" in window and "except Exception" in window, rel


# ── operational panels ───────────────────────────────────────────────────────

from monitoring import cache, discord_stats                        # noqa: E402


def _perf_rows(*rows):
    """(model_id, sport, settled, wins, losses, pushes, priced, units, last)"""
    return FakeConn(rows)


def test_roi_denominator_excludes_pushes():
    """A push returns the stake, so it was never risked. Counting it deflates
    ROI on models with many pushes (f5 moneyline pushes 25 of 221)."""
    m = store.model_performance(
        _perf_rows(("m", "MLB", 100, 50, 30, 20, 100, 8.0, "2026-08-29")))[0]
    assert m["roi_pct"] == pytest.approx(8.0 / 80 * 100)


def test_a_record_only_model_reports_no_roi():
    """batter HR settles hundreds of picks and prices almost none. An ROI over
    the priced few, printed beside the full record, reads as the record's ROI."""
    m = store.model_performance(
        _perf_rows(("mlb_prop_batter_hr", "MLB", 252, 42, 210, 0, 0, 0, "x")))[0]
    assert m["roi_pct"] is None


def test_partially_priced_model_keeps_its_denominator_visible():
    m = store.model_performance(
        _perf_rows(("mlb_prop_batter_hr", "MLB", 252, 42, 210, 0, 20, 2.58, "x")))[0]
    assert m["priced"] == 20 and m["settled"] == 252
    assert m["roi_pct"] == pytest.approx(2.58 / 20 * 100)


def test_perf_reads_the_matview_not_the_expensive_view():
    """v_model_full_outcome_record is 1,596ms / 568k buffer hits — it cannot sit
    behind a dashboard at any poll rate. The matview is the same grading."""
    conn = FakeConn()
    store.model_performance(conn)
    assert "mv_scored_pick_outcomes" in conn.queries[0]
    assert "v_model_full_outcome_record" not in conn.queries[0]


def test_slow_panels_are_bounded_on_an_indexed_column():
    """picks.created_at is TEXT: the timestamptz cast is unindexable and costs a
    seq scan. Every picks query the dashboard runs must bound on game_date."""
    conn = FakeConn()
    store.picks_over_time(conn)
    store.pick_counts(conn)
    for sql in conn.queries:
        assert "game_date >=" in sql, sql


def test_roster_reports_a_registered_but_untrained_model():
    """NHL totals and the golf models are registered with thresholds and no
    artifact. That is a real state and worth seeing before score time."""
    conn = FakeConn([("nhl_over_under", False, False, 0.55, 0.05, None,
                      None, None, None, None, None)])
    m = store.model_roster(conn)[0]
    assert m["model_id"] == "nhl_over_under" and m["version"] is None


# ── cache ────────────────────────────────────────────────────────────────────

def test_cache_serves_within_ttl_and_recomputes_after():
    cache.clear()
    calls = []
    fn = lambda: (calls.append(1), len(calls))[1]
    assert cache.cached("k", 60, fn) == 1
    assert cache.cached("k", 60, fn) == 1        # shared, not recomputed
    assert len(calls) == 1
    assert cache.cached("k", -1, fn) == 2        # expired
    assert len(calls) == 2


def test_cache_serves_stale_rather_than_failing():
    """A dropped pooler connection must not blank a panel that has a value."""
    cache.clear()
    cache.cached("k", 60, lambda: "good")

    def boom():
        raise RuntimeError("connection closed")

    assert cache.cached("k", -1, boom) == "good"


def test_cache_raises_when_it_has_nothing_to_fall_back_on():
    cache.clear()
    with pytest.raises(RuntimeError):
        cache.cached("cold", 60, lambda: (_ for _ in ()).throw(RuntimeError("x")))


def test_cache_reports_age():
    cache.clear()
    assert cache.age("k") is None
    cache.cached("k", 60, lambda: 1)
    assert 0 <= cache.age("k") < 5


# ── discord ──────────────────────────────────────────────────────────────────

def test_discord_names_the_missing_variables(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    d = discord_stats.guild_stats()
    assert d["configured"] is False
    assert "DISCORD_BOT_TOKEN" in d["reason"] and "DISCORD_GUILD_ID" in d["reason"]
    assert "write-only" in d["reason"], "must say WHY a webhook cannot do this"
    assert discord_stats.configured() is False


@pytest.mark.parametrize("code,phrase", [
    (401, "token"), (403, "not a member"), (404, "no guild"), (429, "rate-limited"),
])
def test_discord_failures_are_distinguishable(monkeypatch, code, phrase):
    """'unavailable' is useless; a wrong token and an uninvited bot need
    different fixes."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "t")
    monkeypatch.setenv("DISCORD_GUILD_ID", "1")

    class R:
        status_code = code
        def json(self): return {}
        def raise_for_status(self): raise AssertionError("should not get here")

    monkeypatch.setattr(discord_stats.requests, "get", lambda *a, **k: R())
    assert phrase in discord_stats.guild_stats()["reason"]


def test_discord_success_parses_counts(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "t")
    monkeypatch.setenv("DISCORD_GUILD_ID", "1")

    class R:
        status_code = 200
        def json(self):
            return {"name": "Signalbase", "approximate_member_count": 412,
                    "approximate_presence_count": 57}
        def raise_for_status(self): pass

    monkeypatch.setattr(discord_stats.requests, "get", lambda *a, **k: R())
    d = discord_stats.guild_stats()
    assert d == {"configured": True, "name": "Signalbase", "members": 412, "online": 57}


def test_discord_never_raises(monkeypatch):
    """One panel on a dashboard must not be able to take the tick down."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "t")
    monkeypatch.setenv("DISCORD_GUILD_ID", "1")

    def boom(*a, **k):
        raise ConnectionError("discord is down")

    monkeypatch.setattr(discord_stats.requests, "get", boom)
    assert "ConnectionError" in discord_stats.guild_stats()["reason"]


def test_ops_payload_is_cached_not_requeried(monkeypatch):
    """Five viewers must cost what one costs — the panels are shared."""
    cache.clear()
    monkeypatch.setattr(discord_stats, "guild_stats", lambda: {"configured": False})
    conn = FakeConn()
    first = server.ops(conn)
    n = len(conn.queries)
    server.ops(conn)
    server.ops(conn)
    assert len(conn.queries) == n, "ops re-queried inside its TTL"
    assert set(first) >= {"models", "perf", "series", "community", "discord", "ages"}

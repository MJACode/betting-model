"""The monitoring HTTP server: dashboard + JSON snapshot + SSE event stream.

RUNS IN TWO PLACES, ONE CODEBASE
  * inside the Railway worker, as a daemon thread started by scheduler.py, so
    the dashboard is reachable from a phone at the service's public URL;
  * on Matt's machine via `python -m monitoring`, pointed at the same Supabase.
Both read the same tables, so the local viewer keeps working when the worker is
down — which is exactly when you want it.

WHY IT TAILS THE DATABASE RATHER THAN AN IN-PROCESS BUS
The scheduler shells out for every pass, so the calls happen in child processes.
The database is the only rendezvous. The probe flushes every 0.75s and the
stream polls every second, so end-to-end latency is ~1-2s.

SECURITY
Binding anything other than loopback REQUIRES MONITOR_TOKEN, and the server
refuses to start otherwise rather than exposing pipeline internals on a public
Railway URL. The token is compared with compare_digest. EventSource cannot set
headers, so the token is also accepted as a query param — which is why the
dashboard is served from the same origin and the token never leaves it.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
import threading
import time
from datetime import datetime, date
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitoring import cache, discord_stats, store  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"

POLL_SEC = float(os.environ.get("MONITOR_POLL_SEC", "1.0"))
# TTLs for the operational panels. These read far more than the live feed does,
# and they change far more slowly — model records move at settlement, once a
# day. The cache is shared across viewers, so N people watching cost the same
# as one. See monitoring/cache.py.
TTL_ROSTER  = float(os.environ.get("MONITOR_TTL_ROSTER", "60"))
TTL_PERF    = float(os.environ.get("MONITOR_TTL_PERF", "300"))
TTL_SERIES  = float(os.environ.get("MONITOR_TTL_SERIES", "120"))
TTL_COMM    = float(os.environ.get("MONITOR_TTL_COMMUNITY", "300"))
TTL_DISCORD = float(os.environ.get("MONITOR_TTL_DISCORD", "600"))
# The calibration report is recomputed by a pipeline step, not by the
# dashboard, so this TTL only governs how stale the READ may be.
TTL_LIVECAL = float(os.environ.get("MONITOR_TTL_LIVECAL", "300"))
META_EVERY_SEC = float(os.environ.get("MONITOR_META_SEC", "10"))
MAX_STREAMS = int(os.environ.get("MONITOR_MAX_STREAMS", "6"))

_streams = threading.Semaphore(MAX_STREAMS)


def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def dumps(obj) -> bytes:
    return json.dumps(obj, default=_json_default, separators=(",", ":")).encode()


def _connect():
    from data.db import get_connection
    return get_connection()


def snapshot(conn, window_min: int = 60) -> dict:
    """Everything the dashboard needs for a cold start, in one round trip."""
    calls = store.recent_calls(conn, limit=150)
    picks = store.recent_picks(conn, limit=40)
    return {
        "calls": calls,
        "picks": picks,
        "rollup": store.api_rollup(conn, window_min),
        "timeline": store.call_timeline(conn, window_min),
        "pick_counts": store.pick_counts(conn, 24),
        "runs": store.recent_runs(conn, 10),
        "health": store.health(conn),
        "quota": store.quota(conn),
        "ops": ops(conn),
        "cursors": {
            "call_id": calls[-1]["call_id"] if calls else 0,
            "pick_id": picks[-1]["pick_id"] if picks else 0,
        },
        "server_time": datetime.now().astimezone().isoformat(),
    }


def meta(conn, window_min: int = 60) -> dict:
    return {
        "rollup": store.api_rollup(conn, window_min),
        "timeline": store.call_timeline(conn, window_min),
        "pick_counts": store.pick_counts(conn, 24),
        "runs": store.recent_runs(conn, 10),
        "health": store.health(conn),
        "quota": store.quota(conn),
        "ops": ops(conn),
        "server_time": datetime.now().astimezone().isoformat(),
    }


def ops(conn) -> dict:
    """The operational half: model roster, performance, picks over time,
    audience. Every panel is behind its own TTL so this can ride the same 10s
    meta tick as the live feed without reading the database on every one."""
    return {
        "models":     cache.cached("roster", TTL_ROSTER, lambda: store.model_roster(conn)),
        "perf":       cache.cached("perf", TTL_PERF, lambda: store.model_performance(conn)),
        "series":     cache.cached("series", TTL_SERIES, lambda: store.picks_over_time(conn)),
        "community":  cache.cached("community", TTL_COMM, lambda: store.community(conn)),
        "livecal":    cache.cached("livecal", TTL_LIVECAL,
                                   lambda: store.live_calibration(conn)),
        # The Discord call leaves the process, so it gets the longest TTL and
        # can never block a tick — guild_stats never raises.
        "discord":    cache.cached("discord", TTL_DISCORD, discord_stats.guild_stats),
        "ages": {k: cache.age(k)
                 for k in ("roster", "perf", "series", "community", "discord",
                           "livecal")},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "signalbase-monitor"
    protocol_version = "HTTP/1.1"

    # ── plumbing ────────────────────────────────────────────────────────────
    def log_message(self, *args):  # keep the worker log about the pipeline
        pass

    def _authorised(self, qs: dict) -> bool:
        token = self.server.monitor_token
        if not token:
            return True                     # loopback-only mode, enforced at bind
        supplied = (self.headers.get("X-Monitor-Token")
                    or (qs.get("token") or [""])[0])
        return hmac.compare_digest(str(supplied), str(token))

    def _send(self, code: int, body: bytes, ctype: str, extra: dict = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ── routes ──────────────────────────────────────────────────────────────
    def do_GET(self):
        parts = urlsplit(self.path)
        route, qs = parts.path, parse_qs(parts.query)

        if route == "/healthz":                     # unauthenticated liveness
            return self._send(200, b'{"ok":true}', "application/json")

        if not self._authorised(qs):
            return self._send(401, b'{"error":"unauthorised"}', "application/json")

        if route in ("/", "/index.html"):
            html = (STATIC / "dashboard.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")

        if route == "/api/snapshot":
            conn = None
            try:
                conn = _connect()
                return self._send(200, dumps(snapshot(conn, self._window(qs))),
                                  "application/json")
            except Exception as exc:
                return self._send(500, dumps({"error": str(exc)[:200]}),
                                  "application/json")
            finally:
                self._close(conn)

        if route == "/api/stream":
            return self._stream(qs)

        return self._send(404, b'{"error":"not found"}', "application/json")

    @staticmethod
    def _window(qs) -> int:
        try:
            return max(5, min(1440, int((qs.get("window") or ["60"])[0])))
        except Exception:
            return 60

    @staticmethod
    def _close(conn):
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    # ── SSE ─────────────────────────────────────────────────────────────────
    def _stream(self, qs):
        if not _streams.acquire(blocking=False):
            return self._send(503, b'{"error":"too many streams"}',
                              "application/json")
        conn = None
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            window = self._window(qs)
            conn = _connect()
            snap = snapshot(conn, window)
            self._event("snapshot", snap)
            call_cur = snap["cursors"]["call_id"]
            pick_cur = snap["cursors"]["pick_id"]
            last_meta = time.time()

            while True:
                time.sleep(POLL_SEC)
                calls = store.calls_since(conn, call_cur)
                if calls:
                    call_cur = calls[-1]["call_id"]
                    self._event("calls", calls)
                picks = store.picks_since(conn, pick_cur)
                if picks:
                    pick_cur = picks[-1]["pick_id"]
                    self._event("picks", picks)
                now = time.time()
                if now - last_meta >= META_EVERY_SEC:
                    last_meta = now
                    self._event("meta", meta(conn, window))
                elif not calls and not picks:
                    # keeps proxies and phones from dropping an idle stream
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            pass
        finally:
            self._close(conn)
            _streams.release()

    def _event(self, name: str, payload) -> None:
        self.wfile.write(f"event: {name}\ndata: ".encode() + dumps(payload) + b"\n\n")
        self.wfile.flush()


def build_server(host: str, port: int, token: str | None) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1") and not token:
        raise RuntimeError(
            "Refusing to bind %s without MONITOR_TOKEN — this dashboard exposes "
            "pipeline internals. Set MONITOR_TOKEN, or bind 127.0.0.1." % host
        )
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    srv.monitor_token = token
    return srv


def serve_in_thread() -> ThreadingHTTPServer | None:
    """Start the dashboard alongside the scheduler. Never raises into the caller —
    a monitoring failure must not stop the pipeline it is monitoring."""
    if os.environ.get("RUN_MONITOR", "1") == "0":
        return None
    try:
        port = int(os.environ.get("MONITOR_PORT") or os.environ.get("PORT") or 8080)
        token = os.environ.get("MONITOR_TOKEN") or None
        host = "0.0.0.0" if token else "127.0.0.1"
        srv = build_server(host, port, token)
        threading.Thread(target=srv.serve_forever, name="monitor-http",
                         daemon=True).start()
        return srv
    except Exception as exc:
        from loguru import logger
        logger.warning(f"Monitor dashboard not started: {exc}")
        return None

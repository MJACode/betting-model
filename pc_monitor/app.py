"""The collector and the local web server behind the This PC window.

Three collector threads fill one shared table of panels, each stamped with when
it was last read and the error it last hit:

  * local     every second: processes, the in-play feed's log, the backup's
              progress, the tennis logs (each on its own interval);
  * tasks     every 30 s: Task Scheduler, one hidden PowerShell call;
  * database  every second: dk_live_feed every 2 s, the per-minute counts every
              15 s, tennis and backup rows every 60 s.

The database has its own thread so a hung connection never stops the local
panels. `view()` joins the panels into what the page shows, judging each one
against the current time. Nothing is written to disk except the app's own log.
"""

from __future__ import annotations

import collections
import json
import os
import secrets
import socket
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from pc_monitor import readers as R
from pc_monitor import sources as S

STATIC = Path(__file__).resolve().parent / "static"
APP_ID = "pc_monitor"
# /healthz carries this from the build that checks origin/master by itself
# (pc_monitor/__main__.watch_master). DraftKings' feed restarts a monitor whose
# /healthz lacks it (dk_live_board.PC_MONITOR_SELF_UPDATE; a test keeps them equal).
SELF_UPDATE = 1
# Collect while a window has asked for data within this long.
VIEWER_TIMEOUT_S = 60.0


def log(msg: str) -> None:
    try:
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)
    except Exception:  # noqa: BLE001
        pass


class Panels:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._p: dict[str, dict[str, Any]] = {}

    def put(self, name: str, data: Any = None, error: str | None = None) -> None:
        with self._lock:
            cur = self._p.setdefault(name, {"data": None, "read_at": None, "error": None, "failed_at": None})
            if error is None:
                cur.update(data=data, read_at=time.time(), error=None, failed_at=None)
            else:
                cur.update(error=error, failed_at=time.time())

    def get(self, name: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._p.get(name) or {"data": None, "read_at": None, "error": None, "failed_at": None})

    def all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {k: dict(v) for k, v in self._p.items()}


def _err(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:160]}"


class Collector:
    def __init__(self, stay: bool = False) -> None:
        self.panels = Panels()
        self.stay = stay
        self.last_viewer = time.time()
        self.stop = threading.Event()
        self._due: dict[str, float] = {}
        self._cache: dict[str, tuple[Any, Any]] = {}
        self.procs: S.ProcessTable | None = None
        # The phone page (pc_monitor_state): this PC's row, its link's token,
        # and when the view was last written there.
        self.host = socket.gethostname()
        self.phone_token: str | None = None
        self._demand_age: float | None = None
        self._last_publish: float | None = None
        # The stream of API calls and data movement: newest last, in memory only.
        self.events: collections.deque = collections.deque(maxlen=400)
        self._events_lock = threading.Lock()
        self._call_cursor: int | None = None
        self._save_cursor: int | None = None
        self.pc_sources: set[str] = set(R.PC_CALL_SOURCES)
        self._copy_table: str | None = None
        self._tennis_seen: set[tuple] | None = None

    def add_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        with self._events_lock:
            self.events.extend(events)
            snapshot = list(self.events)
        self.panels.put("events", snapshot)

    def _read_stream(self, db: S.Database) -> None:
        """New API calls every second, the PC's saved rows every 2 s, and the
        per-provider counts every 10 s."""
        if self._due_now("db_calls", 1):
            if self._call_cursor is None:
                rows = list(reversed(db.rows(S.SQL_CALLS_RECENT)))
            else:
                rows = db.rows(S.SQL_CALLS_SINCE, (self._call_cursor,))
            if rows:
                self._call_cursor = rows[-1][0]
                self.add_events([R.call_event(r, self.pc_sources) for r in rows])
            self.panels.put("calls", {"cursor": self._call_cursor})
        if self._due_now("db_saves", 2):
            if self._save_cursor is None:
                self._save_cursor = db.rows(S.SQL_SAVES_START)[0][0]
            else:
                rows = db.rows(S.SQL_SAVES_SINCE, (self._save_cursor,))
                if rows:
                    self._save_cursor = rows[-1][0]
                    self.add_events([R.save_event(r) for r in rows])
        if self._due_now("db_call_buckets", 10):
            self.panels.put("call_buckets", db.rows(S.SQL_CALL_BUCKETS))

    def _local_events(self) -> None:
        """Backup and tennis moments, from the panels the local loop reads."""
        procs = self.panels.get("processes").get("data") or []
        for p in procs:
            m = R.module_of(p.get("cmdline"))
            if m:
                self.pc_sources.add(m)
        b = self.panels.get("backup").get("data") or {}
        prog = b.get("progress") or {}
        age = time.time() - (R.parse_iso(prog.get("now")) or 0)
        table = prog.get("table") if age < R.PROGRESS_FRESH_SEC else None
        if table and table != self._copy_table and self._copy_table is not None:
            self.add_events([{"id": f"b{prog.get('now')}{table}", "at": R.parse_iso(prog.get("now")),
                              "kind": "backup", "where": "pc", "provider": "Supabase", "ok": True,
                              "what": f"backup copying {table} ({int(prog.get('rows_pulled') or 0):,} rows so far)"}])
        if table or self._copy_table is None:
            self._copy_table = table or ""
        t = self.panels.get("tennis").get("data") or {}
        passes = t.get("passes") or []
        seen = {(p.get("start_at"), n) for p in passes for n in (p.get("collectors") or {})}
        if self._tennis_seen is not None and passes:
            last = passes[-1]
            new = []
            for name, ex in (last.get("collectors") or {}).items():
                if (last.get("start_at"), name) not in self._tennis_seen:
                    summary = ((t.get("collectors") or {}).get(name) or {}).get("summary") or {}
                    new.append({"id": f"t{last.get('start_at')}{name}", "at": ex.get("at"), "kind": "tennis",
                                "where": "pc", "provider": name, "ok": ex.get("exit_code") in (0, None),
                                "what": f"tennis {name} pass finished: "
                                        + ", ".join(f"{k} {v}" for k, v in summary.items() if k != "seen_at")})
            self.add_events(new)
        if passes:
            self._tennis_seen = seen

    def phone_url(self) -> str | None:
        return f"{S.PUBLIC_BASE}/pc/?token={self.phone_token}" if self.phone_token else None

    def _publish(self, db: S.Database) -> None:
        """Write the page's view to this PC's row: every 2 s while a phone is
        watching, once a minute otherwise. The token is never in the view."""
        if self.phone_token is None:
            self.phone_token = db.write(S.SQL_PHONE_ROW, (self.host, secrets.token_urlsafe(24)))[0][0]
        if self._due_now("db_demand", R.PUBLISH_FAST_SEC):
            rows = db.rows(S.SQL_DEMAND, (self.host,))
            self._demand_age = rows[0][0] if rows else None
        interval = R.publish_interval(self._demand_age)
        if self._last_publish is not None and time.time() - self._last_publish < interval:
            return
        payload = view(self.panels.all(), time.time(), pc_sources=self.pc_sources, stream_limit=60)
        payload["host"] = self.host
        db.write(S.SQL_PUBLISH, (json.dumps(payload, default=str), self.host))
        self._last_publish = time.time()
        self.panels.put("publish", {"at": self._last_publish, "every_s": interval,
                                    "phone_watching": interval == R.PUBLISH_FAST_SEC})

    # ── scheduling ──────────────────────────────────────────────────────────
    def active(self) -> bool:
        return self.stay or time.time() - self.last_viewer < VIEWER_TIMEOUT_S

    def _due_now(self, key: str, every: float) -> bool:
        t = time.time()
        if t >= self._due.get(key, 0):
            self._due[key] = t + every
            return True
        return False

    def _run(self, name: str, fn: Callable[[], Any], *, db: bool = False) -> None:
        try:
            self.panels.put(name, fn())
        except Exception as exc:  # noqa: BLE001
            self.panels.put(name, error=type(exc).__name__ if db else _err(exc))
            if not db:
                log(f"{name} failed: {traceback.format_exc(limit=3)}")

    def _cached_text(self, key: str, path: Path) -> str:
        """A file's text, re-read only when its size or write time changes."""
        info = S.file_info(path)
        sig = (info["size"], info["mtime"]) if info else None
        hit = self._cache.get(key)
        if hit and hit[0] == sig and hit[1][0] == str(path):
            return hit[1][1]
        text, _ = S.read_text(path)
        self._cache[key] = (sig, (str(path), text))
        return text

    def start(self) -> None:
        for target, name in ((self._local_loop, "local"), (self._task_loop, "tasks"), (self._db_loop, "db")):
            threading.Thread(target=target, name=f"pc-monitor-{name}", daemon=True).start()

    # ── local ───────────────────────────────────────────────────────────────
    def _scripts(self) -> list[str]:
        tasks = self.panels.get("tasks").get("data") or []
        return sorted({t["script"] for t in tasks if t.get("script")})

    def _local_loop(self) -> None:
        while not self.stop.is_set():
            if self.active():
                if self.procs is None:
                    try:
                        self.procs = S.ProcessTable()
                    except Exception as exc:  # noqa: BLE001
                        self.panels.put("processes", error=_err(exc))
                if self.procs is not None:
                    if self._due_now("discover", 5):
                        self._run("discover", lambda: self.procs.discover(self._scripts()) or True)
                    self._run("processes", self.procs.sample)
                if self._due_now("feed_log", 2):
                    self._run("feed_log", self._read_feed_log)
                if self._due_now("launcher_log", 5):
                    self._run("launcher_log", self._read_launcher_log)
                if self._due_now("backup", 2):
                    self._run("backup", S.backup_files)
                if self._due_now("tables_done", 15):
                    self._run("tables_done", self._read_tables_done)
                if self._due_now("tennis", 10):
                    self._run("tennis", self._read_tennis)
                if self._due_now("stderr", 30):
                    self._run("stderr", self._read_stderr)
                try:
                    self._local_events()
                except Exception:  # noqa: BLE001
                    log(f"stream events failed: {traceback.format_exc(limit=3)}")
            self.stop.wait(1.0)

    def _feed_log_path(self) -> Path | None:
        for p in self.panels.get("processes").get("data") or []:
            if p.get("role") == "dk_feed":
                v = R.arg_value(p.get("cmdline"), "--log")
                if v:
                    return Path(v)
        return S.newest(S.LOG_DIR, "dk_live_board_feed_*.log")

    def _read_feed_log(self) -> dict[str, Any]:
        path = self._feed_log_path()
        if path is None or not path.exists():
            return {"path": None}
        text = self._cached_text("feed_log", path)
        summary = R.feed_log_summary(R.parse_log_lines(text.splitlines()))
        summary["path"] = str(path)
        return summary

    def _read_launcher_log(self) -> dict[str, Any]:
        path = S.newest(S.LOG_DIR, "dk_live_board_2*.log")
        if path is None:
            return {"runs": []}
        return {"path": str(path), "runs": R.parse_launcher_log(self._cached_text("launcher_log", path).splitlines())}

    def _read_tables_done(self) -> Any:
        b = self.panels.get("backup").get("data") or {}
        return S.tables_done_since(R.parse_iso((b.get("progress") or {}).get("started_at")))

    def _read_tennis(self) -> dict[str, Any]:
        out: dict[str, Any] = {"passes": [], "collectors": {}}
        path = S.newest(S.LOG_DIR, "tennis_feeds_2*.log")
        if path:
            out["passes"] = R.parse_tennis_passes(self._cached_text("tennis_passes", path).splitlines())[-8:]
        for name in ("dk", "pinnacle", "tennisexplorer"):
            p = S.newest(S.LOG_DIR, f"tennis_feeds_{name}_2*.log")
            info = S.file_info(p) if p else None
            out["collectors"][name] = {
                "summary": R.last_json_line(S.read_text(p, 20_000)[0]) if p else None,
                "written_at": info["mtime"] if info else None}
        return out

    def _read_stderr(self) -> list[dict[str, Any]]:
        since = time.time() - 24 * 3600
        return S.stderr_files(["dk_live_board_stderr_*.log", "dk_live_board_git_*.log",
                               "tennis_feeds_git_*.log", "tennis_feeds_dk_stderr_*.log",
                               "tennis_feeds_pinnacle_stderr_*.log",
                               "tennis_feeds_tennisexplorer_stderr_*.log"], since)

    # ── tasks ───────────────────────────────────────────────────────────────
    def _task_loop(self) -> None:
        while not self.stop.is_set():
            if self.active() and self._due_now("tasks", 30):
                self._run("tasks", lambda: R.parse_tasks(S.read_tasks()))
            self.stop.wait(1.0)

    # ── database ────────────────────────────────────────────────────────────
    def _db_loop(self) -> None:
        db = S.Database()
        backoff = 0.0
        while not self.stop.is_set():
            if not self.active():
                db.close()
                self.stop.wait(1.0)
                continue
            if backoff and time.time() < backoff:
                self.stop.wait(1.0)
                continue
            try:
                if self._due_now("db_feed", 2):
                    rows = db.rows(S.SQL_FEED)
                    self.panels.put("db_feed", [
                        {"sport": r[0], "age_s": r[1], "ok": r[2], "live_events": r[3],
                         "matched": r[4], "detail": r[5], "db_now": r[6]} for r in rows])
                if self._due_now("db_books", 5):
                    # Its own try: a books read that fails (the table not made
                    # yet) costs only this panel. rows() reconnects next time.
                    try:
                        rows = db.rows(S.SQL_BOOKS)
                        self.panels.put("db_books", [
                            {"book": r[0], "sport": r[1], "age_s": r[2], "ok": r[3], "status": r[4],
                             "live_events": r[5], "matched": r[6], "written": r[7], "detail": r[8]} for r in rows])
                    except Exception as exc:  # noqa: BLE001
                        self.panels.put("db_books", error=type(exc).__name__)
                if self._due_now("db_minutes", 15):
                    sports = [r["sport"] for r in (self.panels.get("db_feed").get("data") or [])]
                    rows = db.rows(S.SQL_MINUTES, (sports,)) if sports else []
                    self.panels.put("db_minutes", [{"sport": r[0], "ago_min": r[1], "rows": r[2]} for r in rows])
                if self._due_now("db_tennis", 60):
                    r = db.rows(S.SQL_TENNIS)[0]
                    self.panels.put("db_tennis", {"rows_hour": r[0], "last_at": r[1]})
                if self._due_now("db_backup", 60):
                    rows = db.rows(S.SQL_BACKUP)
                    self.panels.put("db_backup", {
                        "snapshot_id": rows[0][0], "taken_at": rows[0][1], "pass_id": rows[0][2],
                        "kind": rows[0][3], "rows_pulled": rows[0][4], "local_tables": rows[0][5],
                        "local_rows": rows[0][6]} if rows else None)
                self._read_stream(db)
                try:
                    self._publish(db)
                except Exception as exc:  # noqa: BLE001
                    self.panels.put("publish", error=type(exc).__name__)
                    log(f"phone publish failed ({type(exc).__name__})")
                    db.close()
                self.panels.put("db", {"connected": True})
                backoff = 0.0
            except Exception as exc:  # noqa: BLE001
                # Type only: a connection error's message can carry the address.
                self.panels.put("db", error=type(exc).__name__)
                log(f"database read failed ({type(exc).__name__})")
                self._due.pop("db_feed", None)
                backoff = time.time() + 15
            self.stop.wait(1.0)


# ── the view ────────────────────────────────────────────────────────────────

def _local_minute(t: float) -> int:
    d = datetime.fromtimestamp(t)
    return d.hour * 60 + d.minute


def _window_text(window: dict | None) -> str | None:
    if not window:
        return None
    s = window["start_minute"]
    e = (s + window["duration_s"] // 60) % 1440
    return f"{s // 60:02d}:{s % 60:02d} to {e // 60:02d}:{e % 60:02d}"


# How old each panel may get before what it holds is no longer shown as
# current: a few of its read intervals. Past it, its judgements turn grey and
# say how long it has not been read (a database that dropped, or a window
# reopened after the collectors paused).
STALE_AFTER_S = {"processes": 10, "feed_log": 15, "launcher_log": 30, "backup": 15, "tennis": 60,
                 "tables_done": 60, "tasks": 120, "db_feed": 10, "db_minutes": 60, "db_tennis": 240,
                 "db_books": 20,
                 "db_backup": 240, "stderr": 120, "calls": 10, "call_buckets": 60}


def stale_for(p: dict[str, Any], name: str, now: float) -> float | None:
    """Seconds since the panel was last read, when that is past its limit;
    None while it is current. A panel never read counts as stale from start."""
    ra = p.get("read_at")
    if ra is None:
        return float("inf") if p.get("error") else None
    age = now - ra
    return age if age > STALE_AFTER_S.get(name, 60) else None


def _stamp(p: dict[str, Any], name: str | None = None, now: float | None = None) -> dict[str, Any]:
    out = {"read_at": p.get("read_at"), "error": p.get("error"), "failed_at": p.get("failed_at")}
    if name and now is not None:
        s = stale_for(p, name, now)
        out["stale_s"] = None if s is None or s == float("inf") else s
    return out


def flow_view(panels: dict[str, dict[str, Any]], now: float, pc_sources: set[str],
              stream_limit: int, sports: list[dict[str, Any]], backup_copy: dict | None) -> dict[str, Any]:
    """The "API calls and data movement" section: the newest events, calls per
    10 s by provider, and the rates the flow diagram draws."""
    g = lambda k: panels.get(k) or {}  # noqa: E731
    events = g("events").get("data") or []
    newest = sorted(events, key=lambda e: e.get("at") or 0, reverse=True)[:stream_limit]
    credits_left = next((e["credits_left"] for e in reversed(events)
                         if e.get("credits_left") is not None), None)
    return {
        "events": newest,
        "timeline": R.call_timeline(g("call_buckets").get("data") or [], now, pc_sources),
        "saved_last_min": sum(s.get("rows_last_min") or 0 for s in sports),
        "backup_rows_per_s": (backup_copy or {}).get("rows_per_s"),
        "backup_table": (backup_copy or {}).get("table"),
        "odds_api_credits_left": credits_left,
        "slots": list(R.PROVIDER_SLOTS),
        "sources": {"calls": _stamp(g("calls"), "calls", now),
                    "call_buckets": _stamp(g("call_buckets"), "call_buckets", now)},
    }


def books_view(db_books: dict[str, Any], sports: list[dict[str, Any]], now: float) -> dict[str, Any]:
    """Live lines by sportsbook: DraftKings' own board (its dk_live_feed rows,
    already judged in `sports`) and every other book's last read per league
    (book_live_feed), one row each, books in the page's order."""
    order = ["draftkings", *R.BOOK_KINDS]
    stale = stale_for(db_books, "db_books", now)
    db_age = (now - db_books["read_at"]) if db_books.get("read_at") else 0
    rows = []
    for s in sports:
        if s.get("age_s") is None and s.get("detail") == "no row yet":
            continue
        rows.append({"book": "draftkings", "name": R.BOOK_NAMES["draftkings"], "kind": "parsed",
                     "sport": s.get("sport"), "age_s": s.get("age_s"), "http": None,
                     "live_events": s.get("live_events") or 0, "matched": s.get("matched") or 0,
                     "written": s.get("rows_last_min"), "written_what": "rows saved, last minute",
                     "rows_hour": s.get("rows_hour"), "minutes": s.get("minutes"),
                     "status": s.get("status") or {"tone": "idle", "text": ""}})
    for r in db_books.get("data") or []:
        book = r.get("book")
        kind = R.BOOK_KINDS.get(book)
        row = dict(r)
        if row.get("age_s") is not None:
            row["age_s"] = row["age_s"] + db_age
        if stale is not None:
            status = {"tone": "idle", "text": "not read from the database lately" if stale == float("inf")
                      else f"not read from the database for {int(stale)} s"}
        else:
            status = R.book_status(row, kind)
        rows.append({"book": book, "name": R.BOOK_NAMES.get(book, book), "kind": kind or "unknown",
                     "sport": "home page" if r.get("sport") == "*" else r.get("sport"),
                     "age_s": row.get("age_s"), "http": r.get("status"),
                     "live_events": r.get("live_events") or 0, "matched": r.get("matched") or 0,
                     "written": r.get("written"), "written_what": "lines changed, last read",
                     "detail": r.get("detail"), "status": status})
    rank = {b: i for i, b in enumerate(order)}
    rows.sort(key=lambda x: (rank.get(x["book"], len(rank)), str(x["sport"])))
    return {"rows": rows, "source": _stamp(db_books, "db_books", now) if db_books else None}


def view(panels: dict[str, dict[str, Any]], now: float, pc_sources: set[str] | None = None,
         stream_limit: int = 150) -> dict[str, Any]:
    """Everything the page shows, judged against `now`."""
    g = lambda k: panels.get(k) or {}  # noqa: E731
    st = lambda k: _stamp(g(k), k, now)  # noqa: E731
    tasks = g("tasks").get("data") or []
    by_script = {t["script"]: t for t in tasks if t.get("script")}
    procs = g("processes").get("data") or []

    def job_procs(script: str | None) -> list[dict[str, Any]]:
        if not script:
            return []
        return [p for p in procs if p.get("role") in ("launcher:" + script, "child:" + script)]

    def strip(ps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in p.items() if k != "cmdline"} for p in ps]

    # In-play feed
    dk_task = by_script.get("dk_live_board_run.ps1")
    feed_proc = next((p for p in procs if p.get("role") == "dk_feed"), None)
    window = dk_task.get("window") if dk_task else None
    in_window = R.in_daily_window(_local_minute(now), window["start_minute"], window["duration_s"]) if window else None
    runs = (g("launcher_log").get("data") or {}).get("runs") or []
    today0 = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    feed_log = g("feed_log").get("data") or {}
    db_feed = g("db_feed")
    minutes: dict[str, list[int]] = {}
    for r in g("db_minutes").get("data") or []:
        if 0 <= (r.get("ago_min") or 0) < 60:
            minutes.setdefault(r["sport"], [0] * 60)[r["ago_min"]] = r["rows"]
    # The feed's ages are read every 2 s; age them by the time since that read.
    db_age = (now - db_feed["read_at"]) if db_feed.get("read_at") else 0
    feed_stale = stale_for(db_feed, "db_feed", now)
    procs_stale = stale_for(g("processes"), "processes", now)
    sports = []
    rows_in = list(db_feed.get("data") or [])
    if db_feed.get("data") is not None:
        # Every league the feed reads, with or without a row: a league
        # DraftKings has never listed would otherwise not be on the page.
        have = {r.get("sport") for r in rows_in}
        rows_in += [{"sport": sp, "age_s": None, "ok": None, "live_events": 0, "matched": 0,
                     "detail": "no row yet"} for sp in R.FEED_LEAGUES if sp not in have]
        rows_in.sort(key=lambda r: str(r.get("sport")))
    for r in rows_in:
        row = dict(r)
        if row.get("age_s") is not None:
            row["age_s"] = row["age_s"] + db_age
        if feed_stale is not None:
            # Old rows are not evidence the feed is late: say what is known.
            row["status"] = {"tone": "idle", "text": f"not read from the database for {int(feed_stale)} s"}
        else:
            row["status"] = R.sport_status(row, feed_proc is not None)
        m = minutes.get(r["sport"], [0] * 60)
        row["minutes"] = m
        row["rows_last_min"] = m[0]
        row["rows_hour"] = sum(m)
        sports.append(row)
    if procs_stale is not None:
        presence = {"tone": "idle", "text": "unknown: processes not read for "
                    + ("a while" if procs_stale == float("inf") else f"{int(procs_stale)} s")}
    else:
        presence = R.feed_presence(feed_proc is not None, now, in_window, runs, _window_text(window))
    feed = {
        "task": dk_task,
        "presence": presence,
        "process": strip([feed_proc])[0] if feed_proc else None,
        "launcher": strip(job_procs("dk_live_board_run.ps1")),
        "log": {k: feed_log.get(k) for k in ("path", "last_line_at", "started_at", "last_read", "rate", "stopped")},
        "problems": feed_log.get("problems") or [],
        "runs_today": [r for r in runs if (r.get("start_at") or 0) >= today0],
        "sports": sports,
        "sources": {"feed_log": st("feed_log"), "db_feed": st("db_feed"),
                    "db_minutes": st("db_minutes"), "launcher_log": st("launcher_log")},
    }

    books = books_view(g("db_books"), sports, now)

    # Backup
    bk_task = by_script.get("local_mirror_run.ps1")
    b = g("backup").get("data") or {}
    status = R.backup_status(b.get("pass_id"), b.get("files") or {}, b.get("progress"), b.get("progress_mtime"),
                             b.get("state"), now, bool(bk_task and bk_task.get("state") == "Running"))
    if (bs := stale_for(g("backup"), "backup", now)) is not None and bs != float("inf"):
        status["warnings"].append(f"the backup's files have not been read for {int(bs)} s")
    backup = {
        "task": bk_task, "status": status,
        "tables_done": g("tables_done").get("data") if status.get("copy") else None,
        "tables_total": b.get("tables_total"),
        "report": R.parse_report(b.get("report_text")),
        "db_row": g("db_backup").get("data"),
        "errors": b.get("errors") or [],
        "processes": strip(job_procs("local_mirror_run.ps1")),
        "sources": {"files": st("backup"), "db_backup": st("db_backup")},
    }

    # Tennis
    tn_task = by_script.get("tennis_feeds_run.ps1")
    t = g("tennis").get("data") or {}
    tennis = {
        "task": tn_task, "passes": list(reversed(t.get("passes") or [])),
        "collectors": t.get("collectors") or {},
        "db": g("db_tennis").get("data"),
        "processes": strip(job_procs("tennis_feeds_run.ps1")),
        "sources": {"logs": st("tennis"), "db_tennis": st("db_tennis")},
    }

    known = {"dk_live_board_run.ps1", "local_mirror_run.ps1", "tennis_feeds_run.ps1"}
    others = [{"task": tk, "processes": strip(job_procs(tk.get("script")))}
              for tk in tasks if tk.get("script") not in known]

    db = g("db")
    flow = flow_view(panels, now, pc_sources or set(R.PC_CALL_SOURCES), stream_limit,
                     sports, status.get("copy"))
    return {
        "app": APP_ID, "now": now, "flow": flow,
        "db": {"connected": db.get("error") is None and db.get("read_at") is not None
               and feed_stale is None, **_stamp(db)},
        "feed": feed, "books": books, "backup": backup, "tennis": tennis, "other_tasks": others,
        "tasks": tasks, "tasks_source": st("tasks"),
        "processes": strip(procs), "processes_source": st("processes"),
        "stderr": g("stderr").get("data") or [],
    }


# ── HTTP ────────────────────────────────────────────────────────────────────

def _json_default(o: Any) -> Any:
    return str(o)


class Handler(BaseHTTPRequestHandler):
    server_version = "pc-monitor"

    def log_message(self, *args: Any) -> None:  # stderr may be a file, or nothing
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_GET(self) -> None:  # noqa: N802
        # Answer only to the loopback names, so a web page that re-points its
        # own domain at 127.0.0.1 cannot read this one.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if host not in ("127.0.0.1", "localhost"):
            return self._send(403, b'{"error":"forbidden"}', "application/json")
        route = self.path.split("?", 1)[0]
        collector: Collector = self.server.collector  # type: ignore[attr-defined]
        if route == "/healthz":
            return self._send(200, json.dumps({"app": APP_ID, "self_update": SELF_UPDATE,
                                               "pid": os.getpid()}).encode(), "application/json")
        if route in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if route == "/api/state":
            collector.last_viewer = time.time()
            try:
                v = view(collector.panels.all(), time.time(), pc_sources=collector.pc_sources)
                # Only the PC's own window gets the phone link; the copy
                # written for the phone (Collector._publish) never has it.
                pub = collector.panels.get("publish")
                v["phone"] = {"url": collector.phone_url(), "last_sent_at": (pub.get("data") or {}).get("at"),
                              "watching": (pub.get("data") or {}).get("phone_watching"),
                              "error": pub.get("error")}
                body = json.dumps(v, default=_json_default)
            except Exception as exc:  # noqa: BLE001
                log(f"view failed: {traceback.format_exc(limit=4)}")
                return self._send(500, json.dumps({"error": _err(exc)}).encode(), "application/json")
            return self._send(200, body.encode(), "application/json")
        if route == "/api/phone-qr.svg":
            url = collector.phone_url()
            if not url:
                return self._send(404, b'{"error":"no phone link yet"}', "application/json")
            from pc_monitor.qr import svg
            return self._send(200, svg(url).encode(), "image/svg+xml")
        return self._send(404, b'{"error":"not found"}', "application/json")


def build_server(port: int, collector: Collector) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    srv.collector = collector  # type: ignore[attr-defined]
    return srv


def watch_idle(srv: ThreadingHTTPServer, collector: Collector, idle_exit_s: float) -> None:
    """Shut the server down once no window has asked for data for idle_exit_s."""
    def loop() -> None:
        while not collector.stop.wait(5.0):
            if time.time() - collector.last_viewer > idle_exit_s:
                log(f"no window for {idle_exit_s / 60:.0f} min - exiting")
                collector.stop.set()
                srv.shutdown()
                return
    threading.Thread(target=loop, name="pc-monitor-idle", daemon=True).start()
